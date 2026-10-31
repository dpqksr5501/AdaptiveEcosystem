"""S1-a 진단 A1 — 행동 특징 (학습 없음). 좋은·나쁜 v2.1 모델이 어떤 상태에서 다르게 행동하나.

    # herbivore_rl/ 에서
    python results/v2/s1a_diag/a1/a1_behavior.py run --seeds eval --workers 6      # 롤아웃 (잡마다 raw/*.npz, 있으면 건너뜀)
    python results/v2/s1a_diag/a1/a1_behavior.py check                              # 기존 진단 행과 G_γ·gait 열 재현 대조
    python results/v2/s1a_diag/a1/a1_behavior.py agg                                # 묶음 집계 → a1_summary.json

- 롤아웃은 `env_v2/rollout.py` rollout() 과 같은 줄이다(세계 = World 하위 클래스, 난수를 더 쓰지 않는다). 하위 클래스는
  `_accumulate`·`_gait_accumulate` 를 부른 뒤 그 스텝의 섭취·대사·사망 배열을 붙잡아 둘 뿐이다. 코어 코드는 고치지 않는다.
- 상태 구간(결정 때 상태): 배고픔 energy<0.5 / ≥0.5 × 관측 0 food_density [0,0.05) / [0.05,0.2) / ≥0.2 × 포식자 보임(관측 1 > 0).
  구간마다 명령·실제 보행 수, 행동 5열 합, 섭취·대사 합, 칸 먹이(발밑 셀의 실제 먹이) 합, 이동 방향과 먹이 기울기의 cos 합.
- 아사 개체: 개체별 고리 버퍼(400스텝)로 사망 직전 궤적을 사망 스텝 기준으로 맞춰 더하고, 사망마다 요약 행을 남긴다.
- 위기 일화: 한 생애에서 energy < 0.2 에 처음 닿은 개체의 결말(아사·피식·energy ≥ 0.5 회복·끝까지 미결).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]                    # herbivore_rl
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

OUT = HERE.parent
RAW = OUT / "raw"
CONFIG = ROOT / "configs" / "v2_1.yaml"
GAMMA = 0.9916661555611042
STEPS = 5000
SEED_SETS = {"eval": list(range(10000, 10020)), "explore20": list(range(12000, 12020))}
MODES = {"det": {}, "k24": {"mode": "hold", "hold_k": 24}}

# 좋음·나쁨·경계 (stage1_close.md 8절 구분, 결정 모드)
MODELS = {
    "v2_1_s0": "good", "v2_1_s1": "good", "v2_1_s2": "good",
    "v2_2r_t0_s20": "good", "v2_2r_t0_s22": "good", "v2_2r_t0_s23": "good", "v2_2r_t0_s25": "good",
    "v2_1c_s32": "good", "v2_1c_s34": "good",
    "v2_2r_t0_s24": "bad", "v2_1c_s30": "bad", "v2_1c_s31": "bad", "v2_1c_s33": "bad",
    "v2_2r_t0_s21": "border",
}

HUNGRY = 0.5
FOOD_EDGES = (0.05, 0.2)                 # 관측 0 구간 경계
N_BIN = 2 * 3 * 2                        # [배고픔 0/배부름 1] × 먹이 3 × [안 보임 0/보임 1]
FINE_E = 10                              # 세밀 격자: 에너지 10칸 × 먹이 6칸 × 보임 2
FINE_F_EDGES = (0.02, 0.05, 0.1, 0.2, 0.3)
N_FINE = FINE_E * (len(FINE_F_EDGES) + 1) * 2
RING = 400                               # 사망 직전 궤적 길이
LAST = 100                               # 사망 요약의 '직전' 창
KEEP_TRAJ = 3                            # 잡마다 원 궤적 몇 개를 남긴다

# 고리 버퍼 변수 (결정 때 값 + 그 스텝의 결과)
TV = ("energy", "food_density", "cell_food", "pred_seen", "cmd_stop", "cmd_walk", "cmd_run", "act_stop",
      "forage", "cohesion", "flee_dist", "cover", "speed_a", "intake", "drain", "kin", "cos_grad", "flat_grad")
TVI = {k: i for i, k in enumerate(TV)}
LIFE_V = ("food_density", "cell_food", "cmd_stop", "cmd_run", "forage", "intake")
DEATH_COLS = ("age", "life_max_e", "hit02_age") + tuple(f"last_{k}" for k in TV) + tuple(f"life_{k}" for k in LIFE_V)

# 구간 누적 열
BIN_COLS = ("n", "cmd_stop", "cmd_walk", "cmd_run", "act_stop", "act_walk", "act_run",
            "forage", "cohesion", "flee_dist", "cover", "speed_a",
            "intake", "drain", "cell_food", "cos_sum", "cos_n", "flat_grad", "kin", "in_cover", "starve_next")
FINE_COLS = ("n", "cmd_stop", "cmd_walk", "cmd_run", "forage", "cohesion", "cover", "intake", "drain")


def job_name(model: str, mode: str, seed: int) -> str:
    return f"{model}__{mode}__{seed}"


def spec_of(model: str, mode: str) -> dict:
    """mode = 바탕 모드(det·k24) + 선택 개입 '+F8' 등. 스펙은 바탕 모드만 담는다(개입은 run_job 이 바깥에 씌운다)."""
    return {"kind": "learned", "model": str(ROOT / "ckpt" / "v2" / f"{model}.zip"), **MODES[mode.split("+")[0]]}


# 개입(학습 없음, 결과 뒤 확인): 행동 열을 바꿔 끼운다. F8 = forage 0.8 고정, F1 = forage 0.1 고정,
# NS = 명령 정지(speed < 1/3)를 걷기 값 0.5 로 바꿈(걷기·뛰기 명령은 그대로), CV = cover 0.2 고정(좋은 묶음 평균 0.23 근처)
INTERV = ("F8", "F1", "NS", "CV")


class Interv:
    def __init__(self, base, kinds):
        self.base, self.kinds = base, list(kinds)
        for k in self.kinds:
            if k not in INTERV:
                raise ValueError(f"모르는 개입 {k}")

    def __call__(self, obs):
        a = np.array(self.base(obs), dtype=np.float64)
        if "F8" in self.kinds:
            a[:, 0] = 0.8
        if "F1" in self.kinds:
            a[:, 0] = 0.1
        if "NS" in self.kinds:
            a[:, 4] = np.where(a[:, 4] < 1.0 / 3.0, 0.5, a[:, 4])
        if "CV" in self.kinds:
            a[:, 3] = 0.2
        return a

    def observe_done(self, done):
        from env_v2.rollout import forward_done
        forward_done(self.base, done)


# --------------------------------------------------------------------- #
# 롤아웃 (워커)
# --------------------------------------------------------------------- #


def _make_world_cls():
    from env_v2.world import World

    class DiagWorld(World):
        """World 그대로. 스텝 안에서 이미 계산한 섭취·대사·사망 배열을 붙잡아 둘 뿐이다(난수·상태를 바꾸지 않는다)."""

        def _accumulate(self, a, rew, repro, caught, starved, done):
            super()._accumulate(a, rew, repro, caught, starved, done)
            self.d_caught = np.array(caught, dtype=bool)
            self.d_starved = np.array(starved, dtype=bool)

        def _gait_accumulate(self, e_prev, intake, drain):
            super()._gait_accumulate(e_prev, intake, drain)
            self.d_intake = np.array(intake, dtype=np.float64)
            self.d_drain = np.array(drain, dtype=np.float64)

    return DiagWorld


def run_job(model: str, mode: str, seed: int, steps: int = STEPS) -> dict:
    import env.torch_init  # noqa: F401
    from env_v2.config import load_v2_config
    from env_v2.rollout import GAIT_COLUMNS, build_policy, g_gamma
    from env_v2.world import GAIT_RUN, GAIT_STOP, GAIT_WALK

    cfg = load_v2_config(CONFIG)
    policy = build_policy(spec_of(model, mode), seed)
    kinds = mode.split("+")[1:]
    if kinds:
        policy = Interv(policy, kinds)
    W = _make_world_cls()
    w = W(cfg, seeds=[seed])
    N = w.N
    rew = np.empty((steps, N), dtype=np.float64)
    done_all = np.empty((steps, N), dtype=bool)
    hook = getattr(policy, "observe_done", None)

    bins = np.zeros((N_BIN, len(BIN_COLS)))
    fine = np.zeros((N_FINE, len(FINE_COLS)))
    ring = np.zeros((RING, N, len(TV)), dtype=np.float32)
    age = np.zeros(N, dtype=np.int64)
    life_sum = np.zeros((N, len(LIFE_V)))
    life_max_e = np.full(N, float(cfg.init_energy))
    hit02_age = np.full(N, -1, dtype=np.int64)
    crisis = np.zeros(N, dtype=np.int8)      # 0 평시, 1 위기(<0.2 뒤 미회복), 2 회복(≥0.5)
    tr_sum = np.zeros((RING, len(TV)))
    tr_n = np.zeros(RING, dtype=np.int64)
    death_rows: list[np.ndarray] = []
    raw_traj: list[np.ndarray] = []
    lives = N
    ep = dict(hit02=0, hit02_starve=0, hit02_caught=0, hit02_recover=0, hit02_censored=0,
              lives=0, starve=0, caught=0)
    life_idx = [TVI[k] for k in LIFE_V]
    last_bin = np.zeros(N, dtype=np.int64)
    fe = np.asarray(FOOD_EDGES)
    ffe = np.asarray(FINE_F_EDGES)
    ar = np.arange(N)

    for t in range(steps):
        obs = w.observe()
        g = w._g
        e_prev = w.energy.copy()
        ix, iy = w._cell_index(w.pos)
        cell_food = w.food[iy, ix].copy()
        grad = g["food_grad"].copy()
        in_cover = g["in_cover"].copy()
        a = np.asarray(policy(obs), dtype=np.float64)
        w._check_action(a)
        _, r, d, _ = w.step(a)
        rew[t], done_all[t] = r, d
        if hook is not None:
            hook(d)

        cmd = w.gait_cmd.astype(np.int64)
        gait = w.gait.astype(np.int64)
        intake, drain = w.d_intake, w.d_drain
        vel = w.vel
        vn = np.sqrt((vel * vel).sum(1))
        gn = np.sqrt((grad * grad).sum(1))
        flat = gn <= 1e-12
        moving = vn > 1e-12
        cosv = np.where(moving & ~flat, (vel * grad).sum(1) / np.maximum(vn, 1e-12) / np.maximum(gn, 1e-12), 0.0)
        cos_ok = moving & ~flat
        hungry = e_prev < HUNGRY
        food = obs[:, 0].astype(np.float64)
        seen = obs[:, 1] > 0
        b = ((1 - hungry.astype(np.int64)) * 3 + np.digitize(food, fe)) * 2 + seen
        last_bin = b
        cols = np.stack([
            np.ones(N), cmd == GAIT_STOP, cmd == GAIT_WALK, cmd == GAIT_RUN,
            gait == GAIT_STOP, gait == GAIT_WALK, gait == GAIT_RUN,
            a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4],
            intake, drain, cell_food, cosv, cos_ok, flat, obs[:, 3], in_cover, w.d_starved,
        ], 1).astype(np.float64)
        np.add.at(bins, b, cols)
        fb = (np.minimum((e_prev * FINE_E).astype(np.int64), FINE_E - 1) * (len(ffe) + 1)
              + np.digitize(food, ffe)) * 2 + seen
        fcols = np.stack([np.ones(N), cmd == GAIT_STOP, cmd == GAIT_WALK, cmd == GAIT_RUN,
                          a[:, 0], a[:, 1], a[:, 3], intake, drain], 1).astype(np.float64)
        np.add.at(fine, fb, fcols)

        tv = np.stack([e_prev, food, cell_food, seen, cmd == GAIT_STOP, cmd == GAIT_WALK, cmd == GAIT_RUN,
                       gait == GAIT_STOP, a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4], intake, drain,
                       obs[:, 3], cosv, flat], 1)
        ring[t % RING] = tv
        age += 1
        life_sum += tv[:, life_idx]
        life_max_e = np.maximum(life_max_e, e_prev)
        # 위기 일화: 결정 때 에너지로 판정 (생애 첫 <0.2 만 센다)
        new_hit = (hit02_age < 0) & (e_prev < 0.2)
        hit02_age[new_hit] = age[new_hit]
        crisis[new_hit] = 1
        ep["hit02"] += int(new_hit.sum())
        rec = (crisis == 1) & (e_prev >= 0.5)
        crisis[rec] = 2
        ep["hit02_recover"] += int(rec.sum())

        if d.any():
            dead = np.flatnonzero(d)
            st = w.d_starved[dead]
            ca = w.d_caught[dead]
            ep["starve"] += int(st.sum())
            ep["caught"] += int(ca.sum())
            in_crisis = crisis[dead] == 1
            ep["hit02_starve"] += int((in_crisis & st).sum())
            ep["hit02_caught"] += int((in_crisis & ~st & ca).sum())
            for i in dead[st]:
                L = int(min(age[i], RING))
                idx = (t - np.arange(L)) % RING
                traj = ring[idx, i, :].astype(np.float64)       # k = 0 이 사망 스텝
                tr_sum[:L] += traj
                tr_n[:L] += 1
                m = min(L, LAST)
                row = np.concatenate([[age[i], life_max_e[i], hit02_age[i]], traj[:m].mean(0),
                                      life_sum[i] / age[i]]).astype(np.float32)
                death_rows.append(row)
                if len(raw_traj) < KEEP_TRAJ and age[i] >= 50:
                    tt = np.full((RING, len(TV)), np.nan, dtype=np.float32)
                    tt[:L] = traj
                    raw_traj.append(tt)
            lives += len(dead)
            age[dead] = 0
            life_sum[dead] = 0.0
            life_max_e[dead] = float(cfg.init_energy)
            hit02_age[dead] = -1
            crisis[dead] = 0
    ep["hit02_censored"] = int((crisis == 1).sum())
    ep["lives"] = int(lives)

    s = w.stats()
    s["seed"] = int(seed)
    s["g_gamma"] = g_gamma(rew, done_all, GAMMA)
    deaths = w._pred_deaths + w._starve_deaths
    s["starve_rate"] = w._starve_deaths / max(steps * N, 1)
    s["starve_share"] = w._starve_deaths / deaths if deaths else float("nan")
    gs = w.gait_stats()
    s.update((c, gs[c]) for c in GAIT_COLUMNS)
    s["world_size"] = float(w.size)
    s["M"] = int(w.M)
    s["pred_speed_mult"] = float(w.pred_speed_mult)
    s["food_regen_mult"] = float(w.food_regen_mult)
    s["cover_frac"] = float(w.cover_frac_actual)
    return dict(
        row={k: (float(v) if k != "seed" else int(v)) for k, v in s.items()},
        bins=bins, fine=fine, tr_sum=tr_sum, tr_n=tr_n,
        death_rows=np.asarray(death_rows, dtype=np.float32).reshape(-1, len(DEATH_COLS)),
        raw_traj=np.asarray(raw_traj, dtype=np.float32).reshape(-1, RING, len(TV)),
        ep=ep,
    )


def _worker(args):
    model, mode, seed, out = args
    t0 = time.time()
    res = run_job(model, mode, seed)
    tmp = Path(str(out) + ".tmp.npz")
    np.savez_compressed(tmp, row=json.dumps(res["row"]), ep=json.dumps(res["ep"]), bins=res["bins"],
                        fine=res["fine"], tr_sum=res["tr_sum"], tr_n=res["tr_n"],
                        death_rows=res["death_rows"], raw_traj=res["raw_traj"])
    tmp.replace(out)
    return model, mode, seed, time.time() - t0


def _init():
    from env.rollout import _init_worker
    _init_worker()


def cmd_run(a) -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    seeds = SEED_SETS[a.seeds]
    models = a.models or list(MODELS)
    modes = a.modes or list(MODES)
    jobs = []
    for m in models:
        for md in modes:
            for s in seeds:
                out = RAW / f"{job_name(m, md, s)}.npz"
                if not out.exists():
                    jobs.append((m, md, s, out))
    if a.limit:
        jobs = jobs[: a.limit]
    print(f"잡 {len(jobs)}개 (워커 {a.workers})", flush=True)
    t0 = time.time()
    if a.workers <= 1:
        for j in jobs:
            print(*_worker(j), flush=True)
    else:
        with ProcessPoolExecutor(max_workers=a.workers, initializer=_init) as ex:
            futs = [ex.submit(_worker, j) for j in jobs]
            for k, f in enumerate(as_completed(futs)):
                m, md, s, dt = f.result()
                print(f"[{k + 1}/{len(jobs)}] {m} {md} {s} {dt:.1f}s  (경과 {time.time() - t0:.0f}s)", flush=True)
    return 0


# --------------------------------------------------------------------- #
# 재현 대조
# --------------------------------------------------------------------- #


def load_job(model, mode, seed):
    p = RAW / f"{job_name(model, mode, seed)}.npz"
    if not p.exists():
        return None
    z = np.load(p, allow_pickle=False)
    return dict(row=json.loads(str(z["row"])), ep=json.loads(str(z["ep"])), bins=z["bins"], fine=z["fine"],
                tr_sum=z["tr_sum"], tr_n=z["tr_n"], death_rows=z["death_rows"], raw_traj=z["raw_traj"])


def cmd_check(a) -> int:
    """기존 진단 행(결정 C0·K24 C0, rev/hold_k24 v2.1 s0~2, inv4 h234 T0)과 같은 시드의 열을 비교한다."""
    RES = ROOT / "results" / "v2"
    ref = {}
    for s in (30, 31, 32, 33, 34):
        for suf, md in (("", "det"), ("_hold24", "k24")):
            p = RES / f"diag_v2_1c_s{s}{suf}" / "ablate.json"
            for r in json.load(open(p, encoding="utf-8"))["per_seed"]["C0"]:
                ref[(f"v2_1c_s{s}", md, r["seed"])] = r
    hk = json.load(open(RES / "rev" / "hold_k24.json", encoding="utf-8"))["per_seed"]
    for m in ("v2_1_s0", "v2_1_s1", "v2_1_s2"):
        for md0, md in (("det", "det"), ("hold24", "k24")):
            for r in hk[m][md0]:
                ref[(m, md, r["seed"])] = r
    with open(RES / "v2_2r_explore" / "inv4" / "h234_rows.jsonl", encoding="utf-8") as f:
        for line in f:
            x = json.loads(line)
            if x["model"].startswith("T0_") and "|C0|" in x["key"]:
                md = "det" if x["key"].endswith("|det") else ("k24" if x["key"].endswith("|hold") else None)
                if md:
                    ref[(f"v2_2r_t0_{x['model'][3:]}", md, x["seed"])] = x["row"]
    cols = ("g_gamma", "starve_rate", "predation_rate", "stop_frac_cmd", "b1", "b8")
    n, worst = 0, {c: 0.0 for c in cols}
    for (m, md, s), r in sorted(ref.items()):
        j = load_job(m, md, s)
        if j is None:
            continue
        n += 1
        for c in cols:
            if c in r and c in j["row"]:
                worst[c] = max(worst[c], abs(float(r[c]) - float(j["row"][c])))
    print(f"대조 잡 {n}개, 열별 최대 절대차: " + ", ".join(f"{c} {v:.3g}" for c, v in worst.items()))
    out = OUT / "a1_check.json"
    json.dump({"n_jobs": n, "max_abs_diff": worst}, open(out, "w", encoding="utf-8"), indent=1)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--seeds", default="eval", choices=list(SEED_SETS))
    r.add_argument("--models", nargs="*")
    r.add_argument("--modes", nargs="*", help="det, k24, 또는 개입 det+F8, det+NS, det+F8+NS, det+F1 ...")
    r.add_argument("--workers", type=int, default=6)
    r.add_argument("--limit", type=int, default=0)
    sub.add_parser("check")
    a = p.parse_args()
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "check":
        return cmd_check(a)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
