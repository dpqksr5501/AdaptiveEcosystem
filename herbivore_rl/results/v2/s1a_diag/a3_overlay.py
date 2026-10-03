"""A3 원인 가설 검사 — 반사실 규칙 덧씌우기와 실제 세계 표본 (학습 없음, S1-a 진단 상자).

코어 코드(env/, env_v2/, policies/, diagnose_v2.py, probe_v2.py, train_v2.py, configs/)는 고치지 않는다. 이 파일은
`env_v2.rollout.rollout` 과 같은 순서로 세계를 돌리되 (1) 래퍼가 세계 상태(개체 발밑 먹이)를 읽을 수 있게 하고
(2) 슬롯·스텝별 상태를 남겨 할인 리턴을 상태별로 나눠 본다. 덧씌우기가 없으면 G_γ·아사율이 `diagnose_v2 ablate`
C0 와 같아야 한다(`--verify` 로 확인).

규칙 (래퍼 factory "a3_overlay:rule_overlay", probe_v2:obs_take 와 같은 꼴 f(base, spec, seed)):
  (a) 배고프고(결정 때 energy < 0.5·max) 발밑 셀 먹이 < 0.05 면 speed 열 ← 0.5 (걷기 칸 [1/3, 2/3))
  (b) 배고프면 forage 열 ← 1.0
  (c) (a) + (b)
  mask_mod k > 1 이면 슬롯 i % k == 0 (128 중 16) 에만 규칙을 건다 — 소수 침입(개체 하나가 바꿨을 때의 이득, PPO 의
  개체별 기울기가 보는 비교).
발밑 먹이는 관측에 없다(관측 0 은 see_r 반경 평균). 그래서 래퍼는 `bind_world` 로 받은 세계에서 읽는다 — 진단 전용이다.

실행 (herbivore_rl 에서):
  python results/v2/s1a_diag/a3_overlay.py run --budget-s 540 --workers 6     # 남은 잡을 예산 안에서 돌린다(이어 하기)
  python results/v2/s1a_diag/a3_overlay.py verify                           # 덧씌우기 없음 = ablate C0 확인
  python results/v2/s1a_diag/a3_overlay.py summary                          # a3_overlay_summary.json
산출: results/v2/s1a_diag/a3_rows.jsonl (잡 하나 = 한 줄), a3_overlay_summary.json, a3_verify.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
H = HERE.parents[2]                     # herbivore_rl
for _p in (str(H), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from env.rollout import _init_worker  # noqa: E402
from env_v2.config import load_v2_config  # noqa: E402
from env_v2.rollout import (GAIT_COLUMNS, build_policy, discounted_return_to_go,  # noqa: E402
                            forward_done, tail_steps)
from env_v2.world import GAIT_RUN, GAIT_STOP, GAIT_WALK, HUNGRY, World  # noqa: E402

GAMMA = 0.9916661555611042
CFG_PATH = H / "configs" / "v2_1.yaml"
CKPT = H / "ckpt" / "v2"
ROWS = HERE / "a3_rows.jsonl"
EVAL_SEEDS = list(range(10000, 10020))
STEPS = 5000
FOOT_FOOD = 0.05            # 규칙 (a)의 '발밑 먹이 적음' 문턱 (셀 먹이, 용량 최대 1)
WALK_VALUE = 0.5            # 걷기 칸 [1/3, 2/3) 의 가운데
FORAGE_HIGH = 1.0           # 규칙 (b)의 forage 값
INVADE_MOD = 8              # 소수 침입: 슬롯 i % 8 == 0 (16/128)
LAST_K = 50                 # 아사 직전 정지 비율을 보는 창

MODELS = {
    # 이름: (분류, 학습 --threads)
    "v2_1c_s30": ("bad", 1), "v2_1c_s31": ("bad", 1), "v2_1c_s33": ("bad", 1), "v2_2r_t0_s24": ("bad", 1),
    "v2_2r_t0_s21": ("border", 1),
    "v2_1_s0": ("good", 3), "v2_1_s1": ("good", 3), "v2_1_s2": ("good", 3),
    "v2_1c_s32": ("good", 1), "v2_1c_s34": ("good", 1),
    "v2_2r_t0_s20": ("good", 1), "v2_2r_t0_s22": ("good", 1), "v2_2r_t0_s23": ("good", 1),
    "v2_2r_t0_s25": ("good", 1),
}
# 조건: (규칙, mask_mod). base 는 덧씌우기 없음.
CONDS = {"base": (None, 1), "a": ("a", 1), "b": ("b", 1), "c": ("c", 1),
         "ia": ("a", INVADE_MOD), "ib": ("b", INVADE_MOD), "ic": ("c", INVADE_MOD)}
MODES = ("det", "k24")


# --------------------------------------------------------------------- #
# 래퍼 (factory)
# --------------------------------------------------------------------- #


class RuleOverlay:
    """규칙 (a)·(b)·(c) 덧씌우기. 세계를 `bind_world` 로 받아 결정 때 에너지·발밑 먹이를 읽는다."""

    def __init__(self, base, spec):
        self.base = base
        self.rule = spec["rule"]
        if self.rule not in ("a", "b", "c"):
            raise ValueError(f"rule 은 a·b·c 중 하나: {self.rule!r}")
        self.mask_mod = int(spec.get("mask_mod", 1))
        self.foot = float(spec.get("foot_food", FOOT_FOOD))
        self.walk = float(spec.get("walk_value", WALK_VALUE))
        self.forage_hi = float(spec.get("forage_high", FORAGE_HIGH))
        self.world = None
        self.mask = None
        self.n_calls = 0
        self.n_trig_a = 0
        self.n_trig_b = 0
        self.n_changed_speed = 0     # 규칙 (a)가 실제로 명령 칸을 바꾼 수 (정지·뛰기 → 걷기)

    def bind_world(self, w) -> None:
        self.world = w
        self.mask = (np.arange(w.N) % self.mask_mod) == 0
        self.i_forage = w.act_names.index("forage")
        self.i_speed = w.act_names.index("speed")
        self.t_walk, self.t_run = w._sp["thresholds"]

    def __call__(self, obs):
        a = np.array(self.base(obs), dtype=np.float64)
        w = self.world
        if w is None:
            raise RuntimeError("RuleOverlay 는 bind_world 로 세계를 받아야 한다 (a3_overlay.traced_rollout)")
        hungry = (w.energy < HUNGRY * w.cfg.max_energy) & self.mask
        self.n_calls += len(a)
        if self.rule in ("a", "c"):
            ix, iy = w._cell_index(w.pos)
            ca = hungry & (w.food[iy, ix] < self.foot)
            s = a[:, self.i_speed]
            self.n_changed_speed += int((ca & ((s < self.t_walk) | (s >= self.t_run))).sum())
            a[ca, self.i_speed] = self.walk
            self.n_trig_a += int(ca.sum())
        if self.rule in ("b", "c"):
            a[hungry, self.i_forage] = self.forage_hi
            self.n_trig_b += int(hungry.sum())
        return a

    def observe_done(self, done):
        forward_done(self.base, done)


def rule_overlay(base, spec, seed):
    return RuleOverlay(base, spec)


# --------------------------------------------------------------------- #
# 기록하는 세계·롤아웃
# --------------------------------------------------------------------- #


class TracedWorld(World):
    """리스폰 직전에 아사 슬롯을 남긴다(동역학·난수 소비는 World 그대로)."""

    def _respawn(self, dead):
        st = np.zeros(self.N, dtype=bool)
        st[dead] = self.energy[dead] <= 0.0
        self.last_starved = st
        super()._respawn(dead)


def _find(policy, attr):
    """래퍼 사슬에서 `attr` 를 가진 첫 정책."""
    p, seen = policy, 0
    while p is not None and seen < 10:
        if hasattr(p, attr):
            return p
        p = getattr(p, "base", None) or getattr(p, "policy", None)
        seen += 1
    return None


def traced_rollout(cfg, policy, seed: int, steps: int, gamma: float = GAMMA) -> dict:
    w = TracedWorld(cfg, seeds=[seed])
    ov = _find(policy, "bind_world")
    if ov is not None:
        ov.bind_world(w)
    N, A = w.N, w.act_dim
    i_forage, i_speed = w.act_names.index("forage"), w.act_names.index("speed")
    rew = np.empty((steps, N))
    done = np.zeros((steps, N), dtype=bool)
    starved = np.zeros((steps, N), dtype=bool)
    S = np.empty((steps, N), dtype=bool)           # 결정 때 배고픔 & 발밑 먹이 < 0.05
    hung = np.empty((steps, N), dtype=bool)
    food_ok = np.empty((steps, N), dtype=bool)     # 결정 때 발밑 먹이 ≥ 0.05
    incov = np.empty((steps, N), dtype=bool)
    capzero = np.empty((steps, N), dtype=bool)     # 발밑 셀 용량 0 (먹이가 다시 자라지 않는 빈 땅)
    energy = np.empty((steps, N), dtype=np.float32)
    gait = np.empty((steps, N), dtype=np.int8)
    repro = np.zeros((steps, N), dtype=bool)
    repro_cd_max = int(cfg.repro_cd)
    act_sum, act_h_sum, n_h = np.zeros(A), np.zeros(A), 0
    done_hook = getattr(policy, "observe_done", None)
    for t in range(steps):
        obs = w.observe()
        e = w.energy
        h = e < HUNGRY * cfg.max_energy
        ix, iy = w._cell_index(w.pos)
        foot = w.food[iy, ix]
        hung[t] = h
        S[t] = h & (foot < FOOT_FOOD)
        food_ok[t] = foot >= FOOT_FOOD
        incov[t] = w._g["in_cover"]
        capzero[t] = w.food_cap[iy, ix] <= 0.0
        energy[t] = e
        a = np.asarray(policy(obs), dtype=np.float64)
        w._check_action(a)
        act_sum += a.sum(0)
        act_h_sum += a[h].sum(0)
        n_h += int(h.sum())
        w.last_starved = None
        _, r, d, _ = w.step(a)
        rew[t], done[t] = r, d
        gait[t] = w.gait
        repro[t] = (w.repro_cd == repro_cd_max) & ~d     # 이번 스텝 번식 (번식 뒤 쿨다운이 막 최대값)
        if d.any():
            starved[t] = w.last_starved
        if done_hook is not None:
            done_hook(d)

    tail = tail_steps(gamma)
    T = steps - tail
    G = discounted_return_to_go(rew, done, gamma)
    Gv = G[:T]
    grp = (np.arange(N) % INVADE_MOD) == 0
    s = w.stats()
    gs = w.gait_stats()
    row = {"seed": int(seed)}
    row.update({k: float(v) for k, v in s.items()})
    row.update((c, float(gs[c])) for c in GAIT_COLUMNS)
    row["g_gamma"] = float(Gv.mean())
    row["starve_rate"] = float(starved.sum() / (steps * N))
    row["g_gamma_grp"] = float(Gv[:, grp].mean())          # 슬롯 i % 8 == 0 (침입 조건의 침입자)
    row["g_gamma_rest"] = float(Gv[:, ~grp].mean())
    row["starve_rate_grp"] = float(starved[:, grp].sum() / (steps * grp.sum()))
    row["starve_rate_rest"] = float(starved[:, ~grp].sum() / (steps * (~grp).sum()))
    caught = done & ~starved
    row["pred_rate_grp"] = float(caught[:, grp].sum() / (steps * grp.sum()))
    row["pred_rate_rest"] = float(caught[:, ~grp].sum() / (steps * (~grp).sum()))
    row["repro_rate_grp"] = float(repro[:, grp].sum() / (steps * grp.sum()))
    row["repro_rate_rest"] = float(repro[:, ~grp].sum() / (steps * (~grp).sum()))
    row["repro_rate"] = float(repro.sum() / (steps * N))
    # 보상 정의 반사실: 같은 궤적을 v1 획득량 보상(net_energy_reward false)으로 다시 셈한다.
    # 순변화 e_new − e_prev = (e_new − e_drained) − drain 이라 획득량 보상 = 순변화 보상 + drain[실제 보행].
    Dr = cfg.energy_drain * w._sp["drain_mult"][gait]
    Gg = discounted_return_to_go(rew + Dr, done, gamma)[:T]
    row["g_gain"] = float(Gg.mean())
    row["g_gain_grp"] = float(Gg[:, grp].mean())
    row["g_gain_rest"] = float(Gg[:, ~grp].mean())
    del Gg, Dr
    # 긴 지평 참고: γ = 0.998 (꼬리 2500) 로 같은 보상열을 할인한다 (학습 γ 가 아니다)
    g2 = 0.998
    T2 = steps - tail_steps(g2)
    if T2 > 0:
        G2 = discounted_return_to_go(rew, done, g2)[:T2]
        row["g998"] = float(G2.mean())
        row["g998_grp"] = float(G2[:, grp].mean())
        row["g998_rest"] = float(G2[:, ~grp].mean())
        del G2
    row["act_mean"] = (act_sum / (steps * N)).tolist()
    row["act_mean_hungry"] = (act_h_sum / max(n_h, 1)).tolist()
    row["S_frac"] = float(S.mean())
    if ov is not None:
        row["trig_a_frac"] = ov.n_trig_a / max(ov.n_calls, 1)
        row["trig_b_frac"] = ov.n_trig_b / max(ov.n_calls, 1)
        row["changed_speed_frac"] = ov.n_changed_speed / max(ov.n_calls, 1)

    # ---- 실제 세계 표본 (H-지평): 배고프고 발밑 먹이 적은 상태 S 에서 보행별 할인 리턴·이후 결과 ----
    # 생의 끝 유형(뒤에서 앞으로): 1 아사, 0 피식, -1 롤아웃 안에서 안 끝남
    end = np.full((steps, N), -1, dtype=np.int8)
    nxt = np.full(N, -1, dtype=np.int8)
    # 다음 '발밑 먹이 ≥ 0.05' 까지 스텝(같은 생 안). 없으면 큰 값
    BIG = 10 ** 6
    ttf = np.empty((steps, N), dtype=np.int64)
    nf = np.full(N, BIG, dtype=np.int64)
    for t in range(steps - 1, -1, -1):
        d = done[t]
        nxt = np.where(d, starved[t].astype(np.int8), nxt)
        end[t] = nxt
        nf = np.where(food_ok[t], 0, np.where(d, BIG, np.minimum(nf + 1, BIG)))
        ttf[t] = nf
    Sv, gv, endv, ttfv = S[:T], gait[:T], end[:T], ttf[:T]
    samp = {}
    for name, gcode in (("stop", GAIT_STOP), ("walk", GAIT_WALK), ("run", GAIT_RUN)):
        m = Sv & (gv == gcode)
        n = int(m.sum())
        samp[name] = {
            "n": n,
            "G_sum": float(Gv[m].sum()),
            "end_starve": int((endv[m] == 1).sum()), "end_pred": int((endv[m] == 0).sum()),
            "ttf_le120": int((ttfv[m] <= 120).sum()), "ttf_le350": int((ttfv[m] <= 350).sum()),
            "ttf_sum_le600": float(np.minimum(ttfv[m], 600).sum()),
            "energy_sum": float(energy[:T][m].sum()),
            "in_cover": int(incov[:T][m].sum()), "capzero": int(capzero[:T][m].sum()),
        }
    # 비교용: 배고프고 발밑 먹이 충분한 상태, 배부른 상태
    for name, m in (("hungry_food", hung[:T] & food_ok[:T]), ("full", ~hung[:T])):
        samp[name] = {"n": int(m.sum()), "G_sum": float(Gv[m].sum()),
                      "end_starve": int((endv[m] == 1).sum()), "end_pred": int((endv[m] == 0).sum())}
    row["S_samples"] = samp

    # ---- 아사 지점 모습 ----
    ts, js = np.nonzero(starved)
    if len(ts):
        last_stop = [float((gait[max(0, t - LAST_K + 1): t + 1, j] == GAIT_STOP).mean()) for t, j in zip(ts, js)]
        row["starve_site"] = {
            "n": int(len(ts)),
            "in_cover": float(incov[ts, js].mean()),
            "capzero": float(capzero[ts, js].mean()),
            "last50_stop_mean": float(np.mean(last_stop)),
            "last50_stop_ge_half": float(np.mean(np.asarray(last_stop) >= 0.5)),
        }
    else:
        row["starve_site"] = {"n": 0}
    return row


# --------------------------------------------------------------------- #
# 잡
# --------------------------------------------------------------------- #


def job_spec(model: str, mode: str, cond: str) -> dict:
    base = {"kind": "learned", "model": str(CKPT / f"{model}.zip")}
    if mode == "k24":
        base.update(mode="hold", hold_k=24)
    rule, mod = CONDS[cond]
    if rule is None:
        return base
    return {"policy": base, "wrap": [{"factory": "a3_overlay:rule_overlay", "rule": rule, "mask_mod": mod}]}


def run_job(args):
    model, mode, cond, seed, steps = args
    t0 = time.time()
    cfg = load_v2_config(CFG_PATH)
    pol = build_policy(job_spec(model, mode, cond), seed)
    row = traced_rollout(cfg, pol, seed, steps)
    row.update(model=model, mode=mode, cond=cond, steps=steps, elapsed_s=round(time.time() - t0, 2))
    return row


def job_key(model, mode, cond, seed) -> str:
    return f"{model}|{mode}|{cond}|{seed}"


def load_rows(path: Path = ROWS) -> list[dict]:
    """잡 하나에 한 줄. 같은 잡이 여러 번 있으면 마지막 줄을 쓴다(--redo-missing 으로 다시 돈 잡)."""
    if not path.exists():
        return []
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                out[job_key(r["model"], r["mode"], r["cond"], r["seed"])] = r
    return list(out.values())


def plan(priority: str = "default") -> list[tuple]:
    """잡 순서: 나쁨·경계 전체 덧씌우기(결정·K24) → 나쁨·경계 침입(결정) → 좋은 모델 전체 덧씌우기(결정·K24)
    → 좋은 모델 침입(결정) → 침입(K24)."""
    bad = [m for m, (c, _) in MODELS.items() if c != "good"]
    good = [m for m, (c, _) in MODELS.items() if c == "good"]
    jobs = []
    for group in (bad, good):
        for mode in MODES:
            for m in group:
                for cond in ("base", "a", "b", "c"):
                    jobs += [(m, mode, cond, s) for s in EVAL_SEEDS]
        for m in group:
            for cond in ("ia", "ib", "ic"):
                jobs += [(m, "det", cond, s) for s in EVAL_SEEDS]
    for m in bad + good:
        for cond in ("ia", "ib", "ic"):
            jobs += [(m, "k24", cond, s) for s in EVAL_SEEDS]
    return jobs


def cmd_run(args) -> int:
    done_keys = {job_key(r["model"], r["mode"], r["cond"], r["seed"]) for r in load_rows()
                 if not args.redo_missing or args.redo_missing in r}
    todo = [j for j in plan() if job_key(*j) not in done_keys]
    if args.skip_k24_invade:
        todo = [j for j in todo if not (j[1] == "k24" and j[2].startswith("i"))]
    if args.only_models:
        keep = set(args.only_models.split(","))
        todo = [j for j in todo if j[0] in keep]
    if args.only_conds:
        keep = set(args.only_conds.split(","))
        todo = [j for j in todo if j[2] in keep]
    print(f"남은 잡 {len(todo)} (끝난 잡 {len(done_keys)})", flush=True)
    if not todo:
        return 0
    t0 = time.time()
    est = 25.0                      # 잡 하나 예상 시간(초). 끝난 잡으로 갱신
    times = []
    n_done = 0
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker) as ex, \
            open(ROWS, "a", encoding="utf-8") as fout:
        it = iter(todo)
        pend = set()

        def submit_more():
            while len(pend) < args.workers:
                if time.time() - t0 + est > args.budget_s:
                    return
                j = next(it, None)
                if j is None:
                    return
                pend.add(ex.submit(run_job, (*j, STEPS)))

        submit_more()
        while pend:
            fin, _ = wait(pend, return_when=FIRST_COMPLETED)
            for f in fin:
                pend.discard(f)
                row = f.result()
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                fout.flush()
                times.append(row["elapsed_s"])
                n_done += 1
            est = float(np.percentile(times, 90)) * 1.1 if times else est
            submit_more()
    print(f"이번 실행 {n_done} 잡, {time.time() - t0:.0f}s, 잡당 중앙 {np.median(times):.1f}s", flush=True)
    return 0


def cmd_verify(args) -> int:
    """덧씌우기 없는 기록 롤아웃이 diagnose_v2 ablate C0 와 같은지 (s30·s31 결정·K24, 시드 3개)."""
    out = []
    for model, mode, diag in (("v2_1c_s30", "det", "diag_v2_1c_s30"), ("v2_1c_s30", "k24", "diag_v2_1c_s30_hold24"),
                              ("v2_1c_s31", "det", "diag_v2_1c_s31")):
        ref = {r["seed"]: r for r in json.loads((H / "results" / "v2" / diag / "ablate.json")
                                                .read_text(encoding="utf-8"))["per_seed"]["C0"]}
        for seed in EVAL_SEEDS[:3]:
            row = run_job((model, mode, "base", seed, STEPS))
            r = ref[seed]
            out.append({"model": model, "mode": mode, "seed": seed,
                        "g_gamma": row["g_gamma"], "g_gamma_ref": r["g_gamma"],
                        "starve_rate": row["starve_rate"], "starve_rate_ref": r["starve_rate"],
                        "p_stop_hungry": row["p_stop_hungry"], "p_stop_hungry_ref": r["p_stop_hungry"],
                        "same": bool(abs(row["g_gamma"] - r["g_gamma"]) < 1e-9 and
                                     abs(row["starve_rate"] - r["starve_rate"]) < 1e-12)})
            print(out[-1], flush=True)
    (HERE / "a3_verify.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if all(o["same"] for o in out) else 1


# --------------------------------------------------------------------- #
# 요약
# --------------------------------------------------------------------- #

METRICS_VS = ("g_gamma", "starve_rate", "predation_rate", "survival", "repro", "g_gamma_grp", "g_gamma_rest",
              "starve_rate_grp", "starve_rate_rest", "pred_rate_grp", "pred_rate_rest", "repro_rate_grp",
              "repro_rate_rest", "g998", "g998_grp", "g998_rest", "g_gain", "g_gain_grp", "g_gain_rest")
METRICS = ("g_gamma", "starve_rate", "predation_rate", "survival", "repro", "stop_frac", "walk_frac", "run_frac",
           "p_stop_hungry", "hungry_frac", "intake_per_step", "drain_per_step", "cover_frac", "b1",
           "g_gamma_grp", "g_gamma_rest", "starve_rate_grp", "starve_rate_rest", "pred_rate_grp", "pred_rate_rest",
           "S_frac", "repro_rate", "repro_rate_grp", "repro_rate_rest", "g998", "g998_grp", "g998_rest",
           "g_gain", "g_gain_grp", "g_gain_rest")


def paired(x: np.ndarray, y: np.ndarray) -> dict:
    d = np.asarray(x, dtype=np.float64) - np.asarray(y, dtype=np.float64)
    n = len(d)
    sd = float(d.std(ddof=1)) if n > 1 else float("nan")
    t = float(d.mean() / (sd / math.sqrt(n))) if n > 1 and sd > 0 else float("nan")
    return {"diff": float(d.mean()), "sd": sd, "t": t, "n": n,
            "ci95": [float(d.mean() - 2.093 * sd / math.sqrt(n)), float(d.mean() + 2.093 * sd / math.sqrt(n))]}


def cmd_summary(args) -> int:
    rows = load_rows()
    by = {}
    for r in rows:
        by.setdefault((r["model"], r["mode"], r["cond"]), {})[r["seed"]] = r
    out = {"generated_by": "results/v2/s1a_diag/a3_overlay.py summary", "n_rows": len(rows),
           "eval_seeds": EVAL_SEEDS, "steps": STEPS, "gamma": GAMMA, "tail": tail_steps(GAMMA),
           "rules": {"a": f"energy<0.5 & foot food<{FOOT_FOOD} -> speed={WALK_VALUE}",
                     "b": f"energy<0.5 -> forage={FORAGE_HIGH}", "c": "a+b",
                     "invade": f"slots i % {INVADE_MOD} == 0 only (16/128); grp = invaders, rest = residents"},
           "models": {}}
    for model, (cls, threads) in MODELS.items():
        mo = {"class": cls, "threads": threads, "modes": {}}
        for mode in MODES:
            base = by.get((model, mode, "base"))
            if not base:
                continue
            md = {}
            for cond in CONDS:
                cur = by.get((model, mode, cond))
                if not cur:
                    continue
                seeds = sorted(set(cur) & set(base))
                ent = {"n_seeds": len(seeds)}
                for k in METRICS:
                    if all(k in cur[s] for s in seeds):
                        ent[k] = float(np.mean([cur[s][k] for s in seeds]))
                ent["act_mean"] = np.mean([cur[s]["act_mean"] for s in seeds], 0).round(4).tolist()
                ent["act_mean_hungry"] = np.mean([cur[s]["act_mean_hungry"] for s in seeds], 0).round(4).tolist()
                for k in ("trig_a_frac", "trig_b_frac", "changed_speed_frac"):
                    if k in cur[seeds[0]]:
                        ent[k] = float(np.mean([cur[s][k] for s in seeds]))
                if cond != "base":
                    ent["vs_base"] = {k: paired([cur[s][k] for s in seeds], [base[s][k] for s in seeds])
                                      for k in METRICS_VS if all(k in cur[s] and k in base[s] for s in seeds)}
                # 상태 S 표본 합산
                agg = {}
                for s in seeds:
                    for g, v in cur[s]["S_samples"].items():
                        a = agg.setdefault(g, {})
                        for kk, vv in v.items():
                            a[kk] = a.get(kk, 0) + vv
                samp = {}
                for g, a in agg.items():
                    n = a["n"]
                    e = {"n": n, "G_mean": a["G_sum"] / n if n else None}
                    ends = a["end_starve"] + a["end_pred"]
                    e["p_end_starve"] = a["end_starve"] / ends if ends else None
                    for kk in ("ttf_le120", "ttf_le350", "in_cover", "capzero"):
                        if kk in a:
                            e[kk.replace("ttf_", "p_ttf_") if kk.startswith("ttf") else "p_" + kk] = \
                                a[kk] / n if n else None
                    if "ttf_sum_le600" in a:
                        e["ttf_mean_cap600"] = a["ttf_sum_le600"] / n if n else None
                    if "energy_sum" in a:
                        e["energy_mean"] = a["energy_sum"] / n if n else None
                    samp[g] = e
                ent["S_samples"] = samp
                sites = [cur[s]["starve_site"] for s in seeds if cur[s]["starve_site"]["n"]]
                if sites:
                    nn = sum(x["n"] for x in sites)
                    ent["starve_site"] = {"n": nn, **{k: sum(x[k] * x["n"] for x in sites) / nn
                                                      for k in ("in_cover", "capzero", "last50_stop_mean",
                                                                "last50_stop_ge_half")}}
                md[cond] = ent
            mo["modes"][mode] = md
        out["models"][model] = mo
    # 묶음: 나쁨 4 / 좋음 9 평균 차 (시드·모델 평균)
    groups = {}
    for cls in ("bad", "good", "border"):
        names = [m for m, (c, _) in MODELS.items() if c == cls]
        for mode in MODES:
            for cond in CONDS:
                if cond == "base":
                    continue
                vals = []
                for m in names:
                    e = out["models"].get(m, {}).get("modes", {}).get(mode, {}).get(cond)
                    if e and "vs_base" in e:
                        vals.append((m, e["vs_base"]["g_gamma"]["diff"], e["vs_base"]["starve_rate"]["diff"],
                                     e["vs_base"]["g_gamma_grp"]["diff"]))
                if vals:
                    groups[f"{cls}|{mode}|{cond}"] = {
                        "models": [v[0] for v in vals],
                        "dG_mean": float(np.mean([v[1] for v in vals])),
                        "dG_min": float(np.min([v[1] for v in vals])),
                        "dStarve_mean": float(np.mean([v[2] for v in vals])),
                        "dG_grp_mean": float(np.mean([v[3] for v in vals])),
                    }
    out["groups"] = groups
    (HERE / "a3_overlay_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"rows {len(rows)} → a3_overlay_summary.json")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=6)
    r.add_argument("--budget-s", type=float, default=540.0)
    r.add_argument("--only-models", default="")
    r.add_argument("--only-conds", default="")
    r.add_argument("--redo-missing", default="", help="이 열이 없는 줄은 끝나지 않은 잡으로 본다")
    r.add_argument("--skip-k24-invade", action="store_true")
    sub.add_parser("verify")
    sub.add_parser("summary")
    args = ap.parse_args(argv)
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    return {"run": cmd_run, "verify": cmd_verify, "summary": cmd_summary}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
