"""RL(s3)·FSM·R_base 는 실제로 얼마나 다르게 행동하나 — 반사실 불일치율과 '보이는' 지표 (탐색, 판정 아님).

사용자가 results/v3/r1b/replay_rl_vs_fsm.mp4(지도 전체, 128점, 1800스텝 stride 3 = 12배속)를 보고 'RL 이나 FSM 이나 별 차이
안 보인다'고 했다. 이 스크립트는 그 차이를 숫자로 잰다. 과장하지 않는다 — 작으면 작다고 적는다.

판정 세계 configs/v3_r1_on.yaml, 평가 시드 10100~10107 × 3000스텝(R1b 평가 시드의 앞 8개).

1. 반사실 불일치: 정책 하나(driver)가 세계를 움직이고, 결정 시점(rep_peek reads)이고 마스크가 두 칸 이상인 개체-스텝마다
   같은 관측으로 나머지 정책의 요청도 묻는다. 세 정책 모두 세계마다 한 번 만들어 매 스텝 부른다(내부 상태가 있으면 같은
   호출 순서로 진행). 묻기만 하는 호출은 세계를 바꾸지 않는다(rep_peek 은 순수 함수, FSM·R_base 는 상태가 없다 —
   `--check` 가 궤적이 비트 단위로 같은지 확인한다). 실행기는 마스크를 보지 않으므로 결정 시점의 요청이 곧 실제 행동이다
   (마스크 밖 요청 수도 센다).
2. 보이는 지표: 같은 롤아웃에서 행동 시간 비율, 동시에 먹기가 아닌 개체 수(평균·p95), 행동 지속 시간(초, 중앙값·p90),
   '무리 반응'(1초(8스텝) 안에 먹기 → 다른 행동 전환이 K 개체 이상) 분당 횟수, 최근접 이웃 거리·무리 퍼짐, 뛰는 개체 비율,
   은신처 안 비율, 피식·아사. 영상과 같은 창(시드 10100, 0~1800스텝, 3스텝마다 1프레임)의 프레임당 점 수도 낸다.

    python results/v3/r1b/visual/divergence.py              # 시뮬레이션 + divergence.json + divergence.md
    python results/v3/r1b/visual/divergence.py --report-only # divergence.json 에서 divergence.md 만 다시 쓴다
    python results/v3/r1b/visual/divergence.py --video-only  # 영상 창(시드 10100, 1800스텝)만 다시 돌려 프레임별 점 수를 더한다
    python results/v3/r1b/visual/divergence.py --check      # 묻기 호출이 궤적을 바꾸지 않는지 확인만

대표 숫자(결론 문단): 시간 비율·굶음·무리 점수는 R1b 20시드 판정(`results/v3/r1b/judge/s3.json`)을 쓰고, 이 스크립트의
8시드 값은 표와 각주에 둔다(`summary` 키에 출처와 함께 적는다). 근접 장면 후보 1498개(`scenes/candidates.json`)의 포획
비율도 읽기만 한다.

(herbivore_rl/ 에서 실행. 기존 파일은 바꾸지 않는다.)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

CONFIG = "configs/v3_r1_on.yaml"
SEEDS = list(range(10100, 10108))
STEPS = 3000
RL_PATH = "ckpt/v3/v3_r1_g995_s3_20m.zip"
POLICIES = ("rl", "fsm", "rbase")
LABEL = {"rl": "RL s3", "fsm": "FSM", "rbase": "R_base"}
BEH = ("GRAZE", "FLEE", "HIDE", "FREEZE")
BEH_KO = ("먹기", "도망", "숨기", "얼기")
WIN_STEPS = 8                     # 1초 ≈ 7.5스텝 → 8스텝 창
HERD_K = (5, 10, 20)
SPATIAL_EVERY = 5
VIDEO_SEED, VIDEO_STEPS, VIDEO_STRIDE = 10100, 1800, 3
VIDEO_FPS = 30
PAUSE_SEC = (7.0, 14.0)           # 멈춰 볼 영상 시각(초) — 프레임 = 초 × 30, 스텝 = 프레임 × 3
JUDGE = "results/v3/r1b/judge/s3.json"
SCENES_SELECT = "results/v3/r1b/visual/scenes/select.json"
SCENES_CANDIDATES = "results/v3/r1b/visual/scenes/candidates.json"

# 결정 행 열
C_SEEN, C_DIST, C_APP, C_COV, C_INC, C_EN, C_CUR, C_RL, C_FSM, C_RB, C_MASK, C_T, C_REC, C_SEED = range(14)
POL_COL = {"rl": C_RL, "fsm": C_FSM, "rbase": C_RB}


def _specs():
    rl = {"kind": "rep_learned", "path": str(ROOT / RL_PATH)}
    fsm = json.loads((ROOT / "results/v3/r1b/fsm_spec.json").read_text(encoding="utf-8"))
    rb = json.loads((ROOT / "results/v3/r1b/rbase_spec.json").read_text(encoding="utf-8"))
    return {"rl": rl, "fsm": fsm, "rbase": rb}


def _job(args):
    driver, seed, steps, query = args
    import env.torch_init  # noqa: F401
    import env_v2.rollout as ro
    import repertoire_rules as rr
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import action_mask
    from env_v2.repertoire import GRAZE
    from env_v2.world import World

    cfg = load_v2_config(ROOT / CONFIG)
    geo = rr._geom(cfg)
    w = World(cfg, seeds=[seed])
    specs = _specs()
    pols = {}
    for name in POLICIES:
        if name == driver or query:
            pols[name] = ro.build_policy(specs[name], seed)
            ro.forward_bind(pols[name], w)
    rl_params = pols["rl"].params if "rl" in pols else None
    names = list(w.obs_names)
    i_pc, i_rec = names.index("pred_count"), names.index("threat_recency")
    N = w.N
    step_sec = float(cfg.policy_interval) / 60.0

    rows = []
    n_reads = n_reads_seen = n_out_mask_fsm = n_out_mask_rb = n_rl_mask_mismatch = 0
    beh_counts = np.zeros((steps, 5), dtype=np.int16)
    gait_counts = np.zeros((steps, 3), dtype=np.int16)
    trans = np.zeros(steps, dtype=np.int16)          # 먹기 → 다른 행동 (같은 개체)
    switches = np.zeros(steps, dtype=np.int16)       # 행동이 바뀐 개체 (리스폰 제외)
    seen_n = np.zeros(steps, dtype=np.int16)         # 결정 관측에서 위협이 보이는 개체
    known_n = np.zeros(steps, dtype=np.int16)        # 위협을 '아는' 개체(보임 또는 기억 ≥ 0.2)
    in_cov = np.zeros(steps, dtype=np.int16)
    deaths_n = np.zeros(steps, dtype=np.int16)
    beh_cov = np.zeros((steps, 5), dtype=np.int16)   # 행동별 은신처 안 개체 수
    hide_arrived = np.zeros(steps, dtype=np.int16)   # 도착해 웅크린 HIDE
    sp_t = list(range(0, steps, SPATIAL_EVERY))
    nn_mean = np.zeros(len(sp_t))
    spread = np.zeros(len(sp_t))
    bout_b, bout_len = [], []

    cur = np.asarray(w.behavior, dtype=np.int64).copy()
    start = np.zeros(N, dtype=np.int64)
    left_cens = np.ones(N, dtype=bool)
    prev_b = cur.copy()
    prev_dead = np.zeros(N, dtype=bool)
    k_sp = 0
    for t in range(steps):
        obs = w.observe()
        acts = {}
        if query:
            pk = w.rep_peek()
            reads = np.asarray(pk["reads"], dtype=bool)
            m = action_mask(pk, obs, rl_params, obs_names=w.obs_names)
            for name, p in pols.items():
                acts[name] = np.asarray(p(obs), dtype=np.float64)[:, 0].astype(np.int64)
            if not np.array_equal(pols["rl"].last_mask, m):
                n_rl_mask_mismatch += 1
            nopt = m.sum(1)
            keep = reads & (nopt >= 2)
            n_reads += int(reads.sum())
            seen_all = obs[:, i_pc] > 0
            n_reads_seen += int((reads & seen_all).sum())
            if keep.any():
                f = rr.features_of_obs(obs[keep], geo)
                code = (m[keep].astype(np.int64) * (1 << np.arange(5))).sum(1)
                a_f, a_b = acts["fsm"][keep], acts["rbase"][keep]
                mk = m[keep]
                n_out_mask_fsm += int((~mk[np.arange(len(a_f)), a_f]).sum())
                n_out_mask_rb += int((~mk[np.arange(len(a_b)), a_b]).sum())
                rows.append(np.stack([
                    f["seen"].astype(np.float64), np.where(np.isfinite(f["dist"]), f["dist"], 99.0), f["approach"],
                    f["cover_d"], f["in_cover"].astype(np.float64), f["energy"],
                    np.asarray(pk["behavior"])[keep].astype(np.float64),
                    acts["rl"][keep].astype(np.float64), a_f.astype(np.float64), a_b.astype(np.float64),
                    code.astype(np.float64), np.full(int(keep.sum()), float(t)), obs[keep, i_rec].astype(np.float64),
                    np.full(int(keep.sum()), float(seed))], 1).astype(np.float32))
        else:
            acts[driver] = np.asarray(pols[driver](obs), dtype=np.float64)[:, 0].astype(np.int64)
        seen_n[t] = int((obs[:, i_pc] > 0).sum())
        known_n[t] = int(((obs[:, i_pc] > 0) | (obs[:, i_rec] >= 0.2)).sum())
        a = acts[driver].astype(np.float64)[:, None]
        _, _, d, _ = w.step(a)
        for p in pols.values():
            ro.forward_done(p, d)
        d = np.asarray(d, dtype=bool)

        b = np.asarray(w.behavior, dtype=np.int64)
        beh_counts[t] = np.bincount(b, minlength=5)[:5]
        gait_counts[t] = np.bincount(np.asarray(w.gait, dtype=np.int64), minlength=3)[:3]
        alive_cont = ~prev_dead
        trans[t] = int(((prev_b == GRAZE) & (b != GRAZE) & alive_cont).sum())
        switches[t] = int(((prev_b != b) & alive_cont).sum())
        ic = np.asarray(w._in_cover(w.pos), dtype=bool)
        in_cov[t] = int(ic.sum())
        beh_cov[t] = np.bincount(b[ic], minlength=5)[:5]
        hide_arrived[t] = int(((b == 2) & np.asarray(w._rs.arrived, dtype=bool)).sum())
        deaths_n[t] = int(d.sum())      # 사망(피식 + 아사). 구분은 롤아웃 끝의 World 누적 카운터로
        # 행동 지속(bout): 행동이 바뀌거나 직전 스텝에 죽은 슬롯(새 개체)이면 이전 bout 을 닫는다
        changed = (b != cur) | prev_dead
        idx = np.flatnonzero(changed)
        if len(idx):
            v = idx[~left_cens[idx]]
            if len(v):
                bout_b.append(cur[v].astype(np.int8))
                bout_len.append((t - start[v]).astype(np.int32))
            cur[idx] = b[idx]
            start[idx] = t
            left_cens[idx] = False
        if k_sp < len(sp_t) and sp_t[k_sp] == t:
            p = np.asarray(w.pos, dtype=np.float64)
            D = np.sqrt(((p[:, None, :] - p[None, :, :]) ** 2).sum(-1))
            np.fill_diagonal(D, np.inf)
            nn_mean[k_sp] = float(D.min(1).mean())
            spread[k_sp] = float(np.sqrt(((p - p.mean(0)) ** 2).sum(1).mean()))
            k_sp += 1
        prev_b = b.copy()
        prev_dead = d

    out = dict(driver=driver, seed=int(seed), steps=int(steps), N=int(N), step_sec=step_sec,
               world_size=float(w.size),
               rows=(np.concatenate(rows) if rows else np.empty((0, 14), np.float32)),
               n_reads=n_reads, n_reads_seen=n_reads_seen, n_out_mask_fsm=n_out_mask_fsm,
               n_out_mask_rb=n_out_mask_rb, n_rl_mask_mismatch=n_rl_mask_mismatch,
               beh_counts=beh_counts, gait_counts=gait_counts, trans=trans, switches=switches, seen_n=seen_n,
               known_n=known_n, in_cov=in_cov, deaths=deaths_n, beh_cov=beh_cov, hide_arrived=hide_arrived,
               pred_deaths=int(w._pred_deaths), starve_deaths=int(w._starve_deaths),
               nn_mean=nn_mean, spread=spread,
               bout_b=(np.concatenate(bout_b) if bout_b else np.empty(0, np.int8)),
               bout_len=(np.concatenate(bout_len) if bout_len else np.empty(0, np.int32)))
    return out


def _check(seed: int = 10100, steps: int = 400) -> dict:
    """묻기 호출(다른 두 정책 + rep_peek)이 궤적을 바꾸지 않는가 — 정책마다 묻기 없이/있이 돌려 위치·행동을 비교한다."""
    res = {}
    for drv in POLICIES:
        a = _job((drv, seed, steps, False))
        b = _job((drv, seed, steps, True))
        res[drv] = bool(np.array_equal(a["beh_counts"], b["beh_counts"]) and np.array_equal(a["nn_mean"], b["nn_mean"])
                        and np.array_equal(a["gait_counts"], b["gait_counts"]))
    return res


# --------------------------------------------------------------------- #
# 집계
# --------------------------------------------------------------------- #


def _rate(x, y):
    n = int(len(x))
    return {"n": n, "rate": (float((x != y).mean()) if n else None)}


def _dist4(a):
    n = len(a)
    return [float((a == k).mean()) if n else None for k in range(4)]


BINS = {
    "all": lambda r: np.ones(len(r), bool),
    "seen": lambda r: r[:, C_SEEN] > 0,
    "not_seen": lambda r: r[:, C_SEEN] <= 0,
    "in_cover": lambda r: r[:, C_INC] > 0,
    "not_in_cover": lambda r: r[:, C_INC] <= 0,
    "seen_in_cover": lambda r: (r[:, C_SEEN] > 0) & (r[:, C_INC] > 0),
    "seen_not_in_cover": lambda r: (r[:, C_SEEN] > 0) & (r[:, C_INC] <= 0),
    "seen_dist_lt4": lambda r: (r[:, C_SEEN] > 0) & (r[:, C_DIST] < 4.0),
    "seen_dist_4_8": lambda r: (r[:, C_SEEN] > 0) & (r[:, C_DIST] >= 4.0) & (r[:, C_DIST] < 8.0),
    "seen_dist_ge8": lambda r: (r[:, C_SEEN] > 0) & (r[:, C_DIST] >= 8.0),
    "seen_app_ge09": lambda r: (r[:, C_SEEN] > 0) & (r[:, C_APP] >= 0.9),
    "seen_app_07_09": lambda r: (r[:, C_SEEN] > 0) & (r[:, C_APP] >= 0.7) & (r[:, C_APP] < 0.9),
    "seen_app_lt07": lambda r: (r[:, C_SEEN] > 0) & (r[:, C_APP] < 0.7),
}
BIN_KO = {
    "all": "전체", "seen": "위협이 보임", "not_seen": "위협이 안 보임(기억만)", "in_cover": "은신처 안",
    "not_in_cover": "은신처 밖", "seen_in_cover": "보임 & 은신처 안", "seen_not_in_cover": "보임 & 은신처 밖",
    "seen_dist_lt4": "보임 & 거리 < 4", "seen_dist_4_8": "보임 & 거리 4~8", "seen_dist_ge8": "보임 & 거리 ≥ 8",
    "seen_app_ge09": "보임 & 빠르게 다가옴(≥ 0.9)", "seen_app_07_09": "보임 & 접근 0.7~0.9",
    "seen_app_lt07": "보임 & 느림(< 0.7)",
}


def disagreement(results: list[dict], driver: str) -> dict:
    rs = [r for r in results if r["driver"] == driver]
    R = np.concatenate([r["rows"] for r in rs])
    agent_steps = sum(r["steps"] * r["N"] for r in rs)
    sim_sec = sum(r["steps"] * r["step_sec"] for r in rs)
    others = [p for p in POLICIES if p != driver]
    pairs = [("rl", "fsm"), ("rl", "rbase"), ("fsm", "rbase")]
    out = dict(driver=driver, n_rows=int(len(R)), agent_steps=int(agent_steps),
               n_reads=int(sum(r["n_reads"] for r in rs)), n_reads_seen=int(sum(r["n_reads_seen"] for r in rs)),
               choice_share=float(len(R) / agent_steps),
               out_of_mask={"fsm": int(sum(r["n_out_mask_fsm"] for r in rs)),
                            "rbase": int(sum(r["n_out_mask_rb"] for r in rs))},
               rl_mask_mismatch_steps=int(sum(r["n_rl_mask_mismatch"] for r in rs)), queried=others)
    bins = {}
    for bn, fn in BINS.items():
        sel = fn(R)
        Rb = R[sel]
        e = {"n": int(sel.sum()), "share_of_rows": float(sel.mean()) if len(R) else None}
        for a, b in pairs:
            e[f"{a}_vs_{b}"] = _rate(Rb[:, POL_COL[a]], Rb[:, POL_COL[b]])["rate"]
        e["dist"] = {p: _dist4(Rb[:, POL_COL[p]].astype(np.int64)) for p in POLICIES}
        # 각자 자기 행동 비율대로 서로 무관하게 골랐을 때의 불일치(기준선) = 1 − Σ_k p_a(k)·p_b(k)
        for a, b in pairs:
            if e["n"]:
                pe = float(np.dot(e["dist"][a], e["dist"][b]))
                po = 1.0 - e[f"{a}_vs_{b}"]
                e[f"{a}_vs_{b}_chance"] = 1.0 - pe
                e[f"{a}_vs_{b}_kappa"] = (po - pe) / (1.0 - pe) if pe < 1.0 else None
        bins[bn] = e
    out["bins"] = bins
    # 시간당 불일치 수(무리 전체): 세계 하나에서 초당 몇 번의 결정이 달랐을까
    out["per_sec_world"] = {f"{a}_vs_{b}": float((R[:, POL_COL[a]] != R[:, POL_COL[b]]).sum() / sim_sec)
                            for a, b in pairs}
    out["per_agent_time"] = {f"{a}_vs_{b}": float((R[:, POL_COL[a]] != R[:, POL_COL[b]]).sum() / agent_steps)
                             for a, b in pairs}
    # 시드별 범위
    per_seed = {}
    for a, b in pairs:
        v = []
        for r in rs:
            x = r["rows"]
            v.append(float((x[:, POL_COL[a]] != x[:, POL_COL[b]]).mean()) if len(x) else float("nan"))
        per_seed[f"{a}_vs_{b}"] = {"min": float(np.nanmin(v)), "max": float(np.nanmax(v)), "values": v}
    out["per_seed"] = per_seed
    # 혼동표 (행 = 앞 정책, 열 = 뒤 정책), 전체와 '보임'
    conf = {}
    for a, b in [("rl", "fsm"), ("rl", "rbase")]:
        for bn in ("all", "seen"):
            Rb = R[BINS[bn](R)]
            M = np.zeros((4, 4), dtype=np.int64)
            np.add.at(M, (Rb[:, POL_COL[a]].astype(np.int64), Rb[:, POL_COL[b]].astype(np.int64)), 1)
            conf[f"{a}_x_{b}_{bn}"] = M.tolist()
    out["confusion"] = conf
    return out


def _bout_stats(lens_steps: np.ndarray, step_sec: float) -> dict:
    if len(lens_steps) == 0:
        return {"n": 0, "median_s": None, "p90_s": None, "mean_s": None}
    s = lens_steps.astype(np.float64) * step_sec
    return {"n": int(len(s)), "median_s": float(np.median(s)), "p90_s": float(np.percentile(s, 90)),
            "mean_s": float(s.mean())}


def _herd_events(trans: np.ndarray, k: int) -> int:
    """1초(WIN_STEPS) 창 안 먹기→다른 행동 전환 합이 k 이상으로 올라선 횟수(올라선 순간만 센다)."""
    c = np.convolve(trans.astype(np.int64), np.ones(WIN_STEPS, dtype=np.int64))[:len(trans)]
    hit = c >= k
    return int((hit & ~np.r_[False, hit[:-1]]).sum())


def visibility(results: list[dict], driver: str) -> dict:
    rs = sorted([r for r in results if r["driver"] == driver], key=lambda r: r["seed"])
    step_sec = rs[0]["step_sec"]
    N = rs[0]["N"]
    BC = np.concatenate([r["beh_counts"] for r in rs]).astype(np.float64)        # (S·T, 5)
    GC = np.concatenate([r["gait_counts"] for r in rs]).astype(np.float64)
    tot = BC.sum()
    non_graze = N - BC[:, 0]
    minutes = sum(r["steps"] for r in rs) * step_sec / 60.0
    out = dict(policy=driver,
               behavior_share={BEH[k]: float(BC[:, k].sum() / tot) for k in range(4)},
               non_graze_agents={"mean": float(non_graze.mean()), "p95": float(np.percentile(non_graze, 95)),
                                 "max": float(non_graze.max()),
                                 "frac_steps_ge5": float((non_graze >= 5).mean()),
                                 "frac_steps_ge10": float((non_graze >= 10).mean())},
               per_behavior_agents_mean={BEH[k]: float(BC[:, k].mean()) for k in range(4)},
               per_behavior_agents_p95={BEH[k]: float(np.percentile(BC[:, k], 95)) for k in range(4)},
               gait_share={"stop": float(GC[:, 0].sum() / GC.sum()), "walk": float(GC[:, 1].sum() / GC.sum()),
                           "run": float(GC[:, 2].sum() / GC.sum())},
               running_agents={"mean": float(GC[:, 2].mean()), "p95": float(np.percentile(GC[:, 2], 95)),
                               "max": float(GC[:, 2].max())},
               in_cover_share=float(np.concatenate([r["in_cov"] for r in rs]).sum() / tot),
               threat_seen_share=float(np.concatenate([r["seen_n"] for r in rs]).sum() / tot),
               threat_known_share=float(np.concatenate([r["known_n"] for r in rs]).sum() / tot),
               switches_per_sec_world=float(sum(r["switches"].sum() for r in rs) / (minutes * 60.0)),
               graze_exits_per_sec_world=float(sum(r["trans"].sum() for r in rs) / (minutes * 60.0)),
               herd_events_per_min={str(k): float(sum(_herd_events(r["trans"], k) for r in rs) / minutes)
                                    for k in HERD_K},
               max_graze_exits_in_1s=int(max(np.convolve(r["trans"].astype(np.int64),
                                                         np.ones(WIN_STEPS, dtype=np.int64)).max() for r in rs)),
               nn_dist_mean=float(np.mean([r["nn_mean"].mean() for r in rs])),
               spread_rms=float(np.mean([r["spread"].mean() for r in rs])),
               nn_dist_per_seed=[float(r["nn_mean"].mean()) for r in rs],
               spread_per_seed=[float(r["spread"].mean()) for r in rs],
               world_size_per_seed=[r["world_size"] for r in rs],
               pred_deaths_per_min=float(sum(r["pred_deaths"] for r in rs) / minutes),
               starve_deaths_per_min=float(sum(r["starve_deaths"] for r in rs) / minutes),
               pred_deaths_per_seed=[int(r["pred_deaths"]) for r in rs],
               starve_deaths_per_seed=[int(r["starve_deaths"]) for r in rs],
               non_graze_share_per_seed=[float(1.0 - r["beh_counts"][:, 0].sum() / r["beh_counts"].sum()) for r in rs],
               minutes=float(minutes))
    BCOV = np.concatenate([r["beh_cov"] for r in rs]).astype(np.float64)
    out["in_cover_share_by_behavior"] = {BEH[k]: (float(BCOV[:, k].sum() / BC[:, k].sum()) if BC[:, k].sum() else None)
                                         for k in range(4)}
    non_graze_tot = BC[:, 1:4].sum()
    out["non_graze_in_cover_share"] = float(BCOV[:, 1:4].sum() / non_graze_tot) if non_graze_tot else None
    HA = np.concatenate([r["hide_arrived"] for r in rs]).astype(np.float64)
    out["hide_crouched_share"] = float(HA.sum() / BC[:, 2].sum()) if BC[:, 2].sum() else None
    bb = np.concatenate([r["bout_b"] for r in rs]).astype(np.int64)
    bl = np.concatenate([r["bout_len"] for r in rs])
    out["bouts"] = {BEH[k]: _bout_stats(bl[bb == k], step_sec) for k in range(4)}
    out["bouts_per_agent_min"] = {BEH[k]: float((bb == k).sum() / (minutes * N)) for k in range(4)}
    # 영상 창: 시드 10100, 0~1800스텝, 3스텝마다
    vr = [r for r in rs if r["seed"] == VIDEO_SEED]
    if vr:
        v = vr[0]["beh_counts"][:VIDEO_STEPS:VIDEO_STRIDE].astype(np.float64)
        g = vr[0]["gait_counts"][:VIDEO_STEPS:VIDEO_STRIDE].astype(np.float64)
        vc = vr[0]["beh_cov"][:VIDEO_STEPS:VIDEO_STRIDE].astype(np.float64)
        ng = N - v[:, 0]
        out["video_window"] = {
            "frames": int(len(v)),
            "non_graze_dots_mean": float(ng.mean()), "non_graze_dots_p95": float(np.percentile(ng, 95)),
            "non_graze_dots_max": float(ng.max()),
            "frac_frames_ge5": float((ng >= 5).mean()), "frac_frames_ge10": float((ng >= 10).mean()),
            "frac_frames_zero": float((ng == 0).mean()),
            "dots_mean": {BEH[k]: float(v[:, k].mean()) for k in range(4)},
            "running_dots_mean": float(g[:, 2].mean()),
            "share_non_graze": float(ng.sum() / (N * len(v))),
            "non_graze_in_cover_share": float(vc[:, 1:4].sum() / max(ng.sum(), 1.0)),
            "hide_dots_in_cover_mean": float(vc[:, 2].mean()),
            "frac_frames_hide_ge20": float((v[:, 2] >= 20).mean()),
            "frac_frames_freeze_ge5": float((v[:, 3] >= 5).mean()),
        }
    return out


def video_compare(results: list[dict]) -> dict:
    """영상 창(시드 10100, 0~1800, 3스텝마다)에서 정책별 프레임마다 점 수와 RL–FSM 차이.

    프레임 i = 영상 i/30 초 = 스텝 3i 의 행동(`replay_v2.collect` 는 스텝 3i 를 실행한 뒤의 행동을 그린다 — 여기
    beh_counts[3i] 와 같다)."""
    def series(drv):
        r = [x for x in results if x["driver"] == drv and x["seed"] == VIDEO_SEED]
        if not r:
            return None, None
        v = r[0]["beh_counts"][:VIDEO_STEPS:VIDEO_STRIDE].astype(np.int64)
        return v, r[0]
    a, ra = series("rl")
    b, rb_ = series("fsm")
    if a is None or b is None:
        return {}
    c, rc = series("rbase")
    N = results[0]["N"]
    da = (N - a[:, 0]) - (N - b[:, 0])
    dh = a[:, 2] - b[:, 2]
    step_sec = results[0]["step_sec"]
    t_sec = np.arange(len(a)) * VIDEO_STRIDE * step_sec
    # FSM 숨기 점이 20 개 이상인 구간(영상 초)
    hi = b[:, 2] >= 20
    segs, start = [], None
    for i, h in enumerate(np.r_[hi, False]):
        if h and start is None:
            start = i
        elif not h and start is not None:
            segs.append([float(t_sec[start]), float(t_sec[i - 1]), float(start / VIDEO_FPS),
                         float((i - 1) / VIDEO_FPS)])
            start = None
    pols = {"rl": (a, ra), "fsm": (b, rb_)}
    if c is not None:
        pols["rbase"] = (c, rc)
    per_frame = {d: {"non_graze": (N - v[:, 0]).tolist(), "flee": v[:, 1].tolist(), "hide": v[:, 2].tolist(),
                     "freeze": v[:, 3].tolist()} for d, (v, _) in pols.items()}
    paused = []
    for s in PAUSE_SEC:
        i = int(round(s * VIDEO_FPS))
        if i < len(a):
            paused.append({"video_sec": s, "frame": i, "step": i * VIDEO_STRIDE,
                           **{d: {"non_graze": int(N - v[i, 0]), "flee": int(v[i, 1]), "hide": int(v[i, 2]),
                                  "freeze": int(v[i, 3]), "hide_pct": round(100.0 * float(v[i, 2]) / N, 1)}
                              for d, (v, _) in pols.items()}})
    seen = {d: float(r["seen_n"][:VIDEO_STEPS].sum() / (min(VIDEO_STEPS, len(r["seen_n"])) * N))
            for d, (_, r) in pols.items()}
    return {"frames": int(len(a)),
            "mean_non_graze_dots": {d: float((N - v[:, 0]).mean()) for d, (v, _) in pols.items()},
            "non_graze_diff_rl_minus_fsm": {"mean": float(da.mean()), "frac_abs_ge10": float((np.abs(da) >= 10).mean()),
                                            "frac_abs_ge20": float((np.abs(da) >= 20).mean()),
                                            "frac_fsm_more_by_ge20": float((-da >= 20).mean())},
            "hide_diff_rl_minus_fsm": {"mean": float(dh.mean()), "frac_abs_ge10": float((np.abs(dh) >= 10).mean())},
            "frac_frames_fsm_hide_ge20": float(hi.mean()),
            "fsm_hide_ge20_segments_sim_sec_and_video_sec": segs,
            "threat_seen_share_window": seen,
            "paused": paused,
            "per_frame": per_frame,
            "video_fps": VIDEO_FPS, "speedup": float(VIDEO_STRIDE * step_sec * VIDEO_FPS)}


def judge_ref() -> dict:
    """R1b 20시드 판정(읽기만): 시간 비율·굶음·무리 점수·t. RL − R_base 의 짝 t 는 시드별 G_γ 로 다시 계산한다."""
    d = json.loads((ROOT / JUDGE).read_text(encoding="utf-8"))
    P = d["pooled"]
    pol = ("rl", "fsm", "rbase", "c_graze")
    g = {p: {e["seed"]: e["g_gamma"] for e in d["per_seed"][p]} for p in ("rl", "rbase")}
    seeds = sorted(g["rl"])
    diff = np.array([g["rl"][s] - g["rbase"][s] for s in seeds])
    t_rb = float(diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))))
    return {"source": JUDGE, "seeds": f"{d['meta']['seeds'][0]}~{d['meta']['seeds'][-1]}", "n_seeds": len(d["meta"]["seeds"]),
            "steps": d["meta"]["steps"],
            "use": {p: P[p]["use"] for p in pol},
            "non_graze": {p: 1.0 - P[p]["use"]["graze"] for p in pol},
            "starve_rate": {p: P[p]["starve_rate"] for p in pol},
            "pred_rate": {p: P[p]["pred_rate"] for p in pol},
            "g_gamma": {p: P[p]["g_gamma"] for p in pol},
            "t_rl_minus_fsm": float(d["perf"]["t"]), "t_rl_minus_rbase": t_rb,
            "starve_ratio_rl_over_fsm": P["rl"]["starve_rate"] / P["fsm"]["starve_rate"],
            "starve_ratio_rl_over_rbase": P["rl"]["starve_rate"] / P["rbase"]["starve_rate"]}


def scenes_ref() -> dict | None:
    """근접 장면 후보(scenes.py search, 1498개 순간, 읽기만): 20초 안 초점 개체 포획 비율, RL–FSM 불일치 분포."""
    sp, cp = ROOT / SCENES_SELECT, ROOT / SCENES_CANDIDATES
    if not (sp.exists() and cp.exists()):
        return None
    s = json.loads(sp.read_text(encoding="utf-8"))["summary"]
    C = json.loads(cp.read_text(encoding="utf-8"))["candidates"]
    nf = sum(len(c["focus"]) for c in C)
    return {"source": SCENES_CANDIDATES, "n": len(C),
            "caught_rate_focus_20s": {p: sum(c["metrics"]["caught_focus"][p] for c in C) / nf for p in POLICIES},
            "frac_d_rl_fsm_below": s["frac_d_rl_fsm_below"],
            "median_d_rl_fsm": s["quantiles_10_25_50_75_90"]["d_rl_fsm"][2]}


# --------------------------------------------------------------------- #
# 보고서
# --------------------------------------------------------------------- #


def _pct(x, nd=1):
    return "—" if x is None else f"{100.0 * x:.{nd}f}%"


def _f(x, nd=1):
    return "—" if x is None else f"{x:.{nd}f}"


def _beh4(p, nd=1):
    return " / ".join(_pct(x, nd) for x in p)


def _cell(M, i, j):
    return int(np.asarray(M)[i, j])


def _t(x: float) -> str:
    return f"{x:.2f}".replace("-", "−")


def facts(res: dict) -> dict:
    """결론 문단·json summary 가 함께 쓰는 숫자. 시간 비율·굶음·무리 점수는 20시드 판정, 나머지는 이 탐색."""
    meta, D, V, VC = res["meta"], res["disagreement"], res["visibility"], res.get("video_compare", {})
    N = meta["N"]
    J = judge_ref()
    S = scenes_ref()
    rlw = D["rl"]
    b_all, b_seen = rlw["bins"]["all"], rlw["bins"]["seen"]
    vr, vf = V["rl"], V["fsm"]
    M = np.asarray(rlw["confusion"]["rl_x_fsm_all"])
    n_dis_f = int(M.sum() - np.trace(M))
    vid = None
    if VC.get("paused"):
        vid = dict(mean_non_graze=VC["mean_non_graze_dots"],
                   gap_mean=VC["mean_non_graze_dots"]["fsm"] - VC["mean_non_graze_dots"]["rl"],
                   frac_fsm_more_by_ge20=VC["non_graze_diff_rl_minus_fsm"]["frac_fsm_more_by_ge20"],
                   frac_fsm_hide_ge20=VC["frac_frames_fsm_hide_ge20"],
                   paused=[{"video_sec": p["video_sec"], "step": p["step"], "fsm_hide": p["fsm"]["hide"],
                            "rl_hide": p["rl"]["hide"], "fsm_non_graze": p["fsm"]["non_graze"],
                            "rl_non_graze": p["rl"]["non_graze"]} for p in VC["paused"]],
                   threat_seen_rl=VC["threat_seen_share_window"]["rl"])
    return dict(
        N=N, judge=J, scenes=S, video=vid,
        fsm_over_rl_non_graze=J["non_graze"]["fsm"] / J["non_graze"]["rl"],
        fsm_hide_bout=vf["bouts"]["HIDE"], fsm_hide_in_cover=vf["in_cover_share_by_behavior"]["HIDE"],
        fsm_hide_crouched=vf["hide_crouched_share"],
        rl_bout_median_s={b: vr["bouts"][b]["median_s"] for b in ("FLEE", "HIDE", "FREEZE")},
        split_agents_per_step=rlw["per_agent_time"]["rl_vs_fsm"] * N,
        split_agents_per_step_rbase=rlw["per_agent_time"]["rl_vs_rbase"] * N,
        separate_gap_8seeds=vf["non_graze_agents"]["mean"] - vr["non_graze_agents"]["mean"],
        dis=dict(rl_fsm=b_all["rl_vs_fsm"], rl_fsm_chance=b_all["rl_vs_fsm_chance"], rl_rbase=b_all["rl_vs_rbase"],
                 rl_rbase_chance=b_all["rl_vs_rbase_chance"], rl_fsm_seen=b_seen["rl_vs_fsm"],
                 rl_fsm_graze_vs_hide=_cell(M, 0, 2) / max(n_dis_f, 1)),
        threat_seen_8seeds_rl=vr["threat_seen_share"],
        speedup=VC.get("speedup", 12.0),
    )


def headline(F: dict) -> tuple[str, list[str], str]:
    """(굵은 첫 문장, 번호 항목, 한 줄 요약) — 마크다운."""
    J, vid, sp = F["judge"], F["video"], F["speedup"]
    ng = J["non_graze"]
    ratio = F["fsm_over_rl_non_graze"]
    top = (f"**RL 과 FSM 은 꽤 다르다. 가장 큰 차이는 FSM 이 RL 보다 약 {ratio:.0f}배 자주 먹기를 멈추고, 그때 주로 "
           "은신처에 숨는다는 것이다. 정말 비슷한 쪽은 RL 과 R_base(먹다가 가까우면 도망)다.**")
    hb = F["fsm_hide_bout"]
    items = [
        f"**FSM 은 RL 보다 약 {ratio:.0f}배 자주 먹기를 멈춘다.** 20시드 판정(시드 {J['seeds']} × {J['steps']}스텝)에서 "
        f"먹기가 아닌 시간은 RL {_pct(ng['rl'])}, FSM {_pct(ng['fsm'])}, R_base {_pct(ng['rbase'])}다. FSM 은 멈출 때 "
        f"대부분 숨는다(숨기 {_pct(J['use']['fsm']['hide'])}, 도망 {_pct(J['use']['fsm']['flee'], 0)}). 한 번 숨으면 평균 "
        f"{hb['mean_s']:.1f}초, 길면(상위 10%) {hb['p90_s']:.1f}초 이어진다(3절, 8시드)."]
    if vid:
        p = vid["paused"]
        items.append(
            f"**사용자가 본 영상에서도 차이는 있다. 멈춰 보면 보인다.** 영상과 같은 창(시드 {VIDEO_SEED}, 0~{VIDEO_STEPS}"
            f"스텝, {sp:.0f}배속)에서 한 프레임의 '먹기가 아닌 점'은 평균 FSM {vid['mean_non_graze']['fsm']:.1f}개, RL "
            f"{vid['mean_non_graze']['rl']:.1f}개다. 프레임의 {_pct(vid['frac_fsm_more_by_ge20'], 0)}에서 FSM 쪽이 20개 이상 "
            "많다. " + "·".join(f"{x['video_sec']:.0f}" for x in p) + f"초 장면을 멈추면 FSM 은 {F['N']}마리 중 "
            + "·".join(str(x["fsm_hide"]) for x in p) + "마리가 파랑(숨기)이고 RL 은 "
            + "·".join(str(x["rl_hide"]) for x in p) + "마리다. 영상 아래 띠 그래프에서는 FSM 쪽 파란 띠가 확연하다. 다만 이 "
            f"시드는 위협이 많은 편이라(RL 세계에서 위협이 보이는 개체 시간 {_pct(vid['threat_seen_rl'])}, 8시드 평균 "
            f"{_pct(F['threat_seen_8seeds_rl'])}) 차이가 평소보다 크다.")
    lo, hi = min(F["rl_bout_median_s"].values()), max(F["rl_bout_median_s"].values())
    items += [
        "**그런데도 비슷해 보인 이유는 이렇게 짐작한다.** 보인 차이가 'RL 이 똑똑하게 움직인다'가 아니라 'FSM 이 더 숨는다'"
        f"였다. 또 FSM 의 숨는 시간 중 {_pct(F['fsm_hide_in_cover'], 0)}는 어두운 은신처 원 안이고 "
        f"{_pct(F['fsm_hide_crouched'], 0)}는 멈춰 웅크린 상태라, {sp:.0f}배속으로 지나가면 눈에 덜 띌 수 있다. 사람 눈에 "
        "어떻게 보이는지는 재지 않았다.",
        f"**RL 만의 행동은 드물고 짧다.** RL 의 도망·숨기·얼기는 합쳐서 시간의 약 {100 * ng['rl']:.0f}%(판정 "
        f"{_pct(ng['rl'])})이고, 한 번에 중앙값 {lo:.1f}~{hi:.1f}초라 {sp:.0f}배속(30fps)에서는 {lo / sp * 30:.0f}~"
        f"{hi / sp * 30:.0f}프레임 깜빡이고 지나간다. 위협이 안 보이고 기억만 있을 때는 세 정책 모두 100% 먹는다.",
        f"**RL 은 R_base 와 닮았다.** 고르는 순간의 불일치가 RL–R_base {_pct(F['dis']['rl_rbase'])}로, 두 정책이 각자 비율"
        f"대로 아무렇게나 골랐을 때({_pct(F['dis']['rl_rbase_chance'])})보다 낮다. RL–FSM 은 {_pct(F['dis']['rl_fsm'])}"
        f"(아무렇게나 {_pct(F['dis']['rl_fsm_chance'])})다. 무리 점수도 RL({J['g_gamma']['rl']:.3f})과 R_base"
        f"({J['g_gamma']['rbase']:.3f}) 사이에 유의한 차이가 없다(짝 t {_t(J['t_rl_minus_rbase'])}, {J['n_seeds']}시드). 그래서 "
        "RL 화면은 '그냥 먹다가 가끔 짧게 반응하는 무리'로 보인다.",
    ]
    res_line = (f"**결과({J['n_seeds']}시드 판정).** 잡아먹히는 비율은 셋이 거의 같다(1000 개체-스텝당 RL "
                f"{J['pred_rate']['rl'] * 1000:.2f}·FSM {J['pred_rate']['fsm'] * 1000:.2f}·R_base "
                f"{J['pred_rate']['rbase'] * 1000:.2f}). 굶어 죽는 비율은 RL 이 FSM 보다 약 "
                f"{100 * (1 - J['starve_ratio_rl_over_fsm']):.0f}% 낮고, R_base 와는 비슷하다(차이 약 "
                f"{abs(100 * (1 - J['starve_ratio_rl_over_rbase'])):.0f}%). 무리 점수는 RL({J['g_gamma']['rl']:.3f})이 FSM"
                f"({J['g_gamma']['fsm']:.3f})보다 높고(t {_t(J['t_rl_minus_fsm'])}), R_base({J['g_gamma']['rbase']:.3f})는 "
                "넘지 못한다.")
    S = F["scenes"]
    if S:
        cr = S["caught_rate_focus_20s"]
        res_line += (f" 위협이 무리에 다가온 {S['n']}개 순간(근접 장면 후보)에서 20초 안에 잡힌 비율도 RL {_pct(cr['rl'])}·"
                     f"FSM {_pct(cr['fsm'])}·R_base {_pct(cr['rbase'])}로 거의 같다.")
    items.append(res_line)
    one = ("한 줄로: **차이는 'FSM 은 숨고 RL 은 계속 먹는다'이다. RL 은 '먹다가 가까우면 도망'(R_base)과 거의 같게 "
           "행동해서, 지금 세계에서는 'RL 이 FSM 보다 똑똑해 보이는' 화면이 나오기 어렵다.**")
    return top, items, one


def footnotes(F: dict, res: dict) -> list[str]:
    """같은 질문에 숫자가 여럿인 이유."""
    V = res["visibility"]
    vf = V["fsm"]
    ng8 = {p: 1.0 - V[p]["behavior_share"]["GRAZE"] for p in POLICIES}
    vid = F["video"]
    return [
        f"시간 비율의 대표 값은 20시드 판정(`{JUDGE}`)이다. 3절 표는 이 탐색(시드 10100~10107 × 3000스텝)에서 잰 값이라 "
        f"조금 다르다 — 먹기가 아닌 시간 RL {_pct(ng8['rl'])}·FSM {_pct(ng8['fsm'])}·R_base {_pct(ng8['rbase'])}. 시드가 "
        f"짧고 적어서 FSM 쪽이 크게 나왔다(FSM 은 시드별 {_pct(min(vf['non_graze_share_per_seed']), 0)}~"
        f"{_pct(max(vf['non_graze_share_per_seed']), 0)}로 흔들린다).",
        f"'한 순간에 다르게 보이는 점의 수'는 두 가지다. (가) 2절의 '한 스텝에 선택이 갈리는 개체' "
        f"{F['split_agents_per_step']:.1f}마리는 결정 시점의 선택만 센다. FSM 의 숨기는 한 번 고르면 잠금 동안(가는 시간 + "
        f"12스텝) 이어지는데 이것을 세지 않으므로 화면의 차이보다 작다. (나) 같은 시드를 정책마다 따로 돌렸을 때 먹기가 아닌 "
        f"개체 수의 차이(FSM − RL)는 평균 약 {F['separate_gap_8seeds']:.0f}마리(8시드)"
        + (f", 영상 창에서 약 {vid['gap_mean']:.0f}마리" if vid else "") + "다. 화면에서 보는 차이는 (나)다.",
        f"'RL 과 FSM 이 다른 선택을 하는 비율'도 재는 방법에 따라 다르다. 2절은 실제 결정 순간마다 같은 관측을 물은 값(위협이 "
        f"보일 때 {_pct(F['dis']['rl_fsm_seen'], 0)})이고, `design_options.md` 1-4절의 44% 는 결정 지도(탐색 시드 "
        "12000~12007)에서 칸별 행동 비율이 겹치지 않는 몫이다.",
        "굶음은 판정(20시드)의 개체-스텝당 비율로 비교한다. 3절의 분당 수(8시드)와 영상 머리말의 '54 대 86'(시드 하나, "
        "900스텝까지)은 차이를 크게 보이게 한다.",
    ]


def summary(res: dict) -> dict:
    """divergence.json 의 summary 키: 결론 문장(마크다운 기호 없음)과 그 숫자·출처."""
    F = facts(res)
    top, items, one = headline(F)

    def strip(s):
        return s.replace("**", "")

    J, S, vid = F["judge"], F["scenes"], F["video"]
    nums = dict(
        non_graze_share_judge20=J["non_graze"], fsm_hide_share_judge20=J["use"]["fsm"]["hide"],
        fsm_over_rl_non_graze=F["fsm_over_rl_non_graze"],
        fsm_hide_bout_mean_s_8seeds=F["fsm_hide_bout"]["mean_s"], fsm_hide_bout_p90_s_8seeds=F["fsm_hide_bout"]["p90_s"],
        video_window=vid,
        agents_whose_choice_splits_in_one_step_8seeds=F["split_agents_per_step"],
        separate_rollout_non_graze_gap_fsm_minus_rl_8seeds=F["separate_gap_8seeds"],
        separate_rollout_non_graze_gap_fsm_minus_rl_video=(vid or {}).get("gap_mean"),
        disagreement_decision_rows_8seeds=F["dis"],
        rl_bout_median_s_8seeds=F["rl_bout_median_s"],
        g_gamma_judge20=J["g_gamma"], t_rl_minus_fsm=J["t_rl_minus_fsm"], t_rl_minus_rbase=J["t_rl_minus_rbase"],
        starve_rate_judge20=J["starve_rate"], starve_ratio_rl_over_fsm=J["starve_ratio_rl_over_fsm"],
        starve_ratio_rl_over_rbase=J["starve_ratio_rl_over_rbase"], pred_rate_judge20=J["pred_rate"],
        scene_candidates=S)
    return dict(headline_ko=[strip(top)] + [f"{i}. {strip(x)}" for i, x in enumerate(items, 1)] + [strip(one)],
                footnotes_ko=[strip(x) for x in footnotes(F, res)],
                numbers=nums,
                sources={"judge20": JUDGE, "this_run": "시드 10100~10107 × 3000스텝 (meta)",
                         "video_window": f"시드 {VIDEO_SEED}, 0~{VIDEO_STEPS}스텝, {VIDEO_STRIDE}스텝마다 (video_compare)",
                         "scene_candidates": SCENES_CANDIDATES})


def render(res: dict) -> str:
    meta, D, V, VC = res["meta"], res["disagreement"], res["visibility"], res.get("video_compare", {})
    N = meta["N"]
    F = facts(res)
    J = F["judge"]
    rlw = D["rl"]
    b_all, b_seen = rlw["bins"]["all"], rlw["bins"]["seen"]
    # 불일치 구성
    M = np.asarray(rlw["confusion"]["rl_x_fsm_all"])
    n_dis_f = int(M.sum() - np.trace(M))
    g_h = _cell(M, 0, 2)
    Mb = np.asarray(rlw["confusion"]["rl_x_rbase_all"])
    n_dis_b = int(Mb.sum() - np.trace(Mb))
    g_f = _cell(Mb, 0, 1)
    vr, vf, vb = V["rl"], V["fsm"], V["rbase"]
    wr, wf, wb = vr["video_window"], vf["video_window"], vb["video_window"]
    near4 = rlw["bins"]["seen_dist_lt4"]
    closer = sum(1 for x, y in zip(rlw["per_seed"]["rl_vs_rbase"]["values"], rlw["per_seed"]["rl_vs_fsm"]["values"])
                 if x < y)
    sp = VC.get("speedup", 12.0)
    L = []
    A = L.append
    A("# RL·FSM·R_base 는 실제로 얼마나 다르게 행동하나")
    A("")
    A("- 날짜: 2026-10-07. 탐색이다(판정 아님). 스크립트: `results/v3/r1b/visual/divergence.py`, 숫자: `divergence.json`"
      "(결론 문장과 그 숫자는 `summary` 키).")
    A(f"- 세계: `{meta['config']}`, 평가 시드 {meta['seeds'][0]}~{meta['seeds'][-1]} ({len(meta['seeds'])}개) × "
      f"{meta['steps']}스텝, 세계마다 {N}마리. 1스텝 = {meta['step_sec']:.4f}초.")
    A(f"- 대표 숫자: 시간 비율·굶음·잡아먹힘·무리 점수는 R1b 20시드 판정(`{JUDGE}`, 시드 {J['seeds']} × {J['steps']}"
      "스텝)을 쓴다. 나머지(같은 순간의 선택, 영상 창, 행동 지속 시간)는 이 탐색에서 잰 값이다. 값이 여럿인 이유는 1절 끝 각주.")
    A("- 정책: RL 출시 모델 s3(argmax), FSM(숨기 > 가까우면 얼기 > 먹다가 도망 — 도망 조건이 늘 얼기 조건 안에 들어서 "
      "FSM 은 실제로 도망을 고르지 않는다), R_base(먹다가 위협이 4 안이거나 빠르게 다가오면 도망).")
    A("")
    A("## 1. 결론")
    A("")
    top, items, one = headline(F)
    A(top)
    A("")
    for i, x in enumerate(items, 1):
        A(f"{i}. {x}")
    A("")
    A(one)
    A("")
    A("**같은 질문에 숫자가 여럿인 이유(각주)**")
    A("")
    for x in footnotes(F, res):
        A(f"- {x}")
    A("")
    A("## 2. 같은 순간, 다른 선택 (반사실 불일치)")
    A("")
    A("RL 이 세계를 움직이고, 결정 시점(실행기가 요청을 읽는 순간)이면서 고를 수 있는 행동이 두 개 이상인 개체-스텝마다 "
      "같은 관측을 FSM·R_base 에도 물었다. 묻기만 하는 호출은 세계를 바꾸지 않는다(궤적이 비트 단위로 같음을 확인했다). "
      f"FSM·R_base 의 요청이 마스크 밖인 경우는 0번이었다(FSM {rlw['out_of_mask']['fsm']}, R_base "
      f"{rlw['out_of_mask']['rbase']}) — 실행기는 결정 시점의 요청을 그대로 따르므로 요청이 곧 실제 행동이다.")
    A("")
    A("이 절은 '그 한 순간'의 선택만 비교한다. FSM 의 숨기는 한 번 고르면 잠금 동안 이어지는데 그 시간은 세지 않으므로, "
      "화면에 보이는 차이는 이보다 크다(3·4절).")
    A("")
    A("행동 비율은 먹기 / 도망 / 숨기 / 얼기 순서다. 거리는 보이는 가장 가까운 위협까지(세계 길이), 접근은 접근 관측이다.")
    A("")
    A("| 상황 | 결정 수 | RL≠FSM | RL≠R_base | RL 이 고른 행동 | FSM 이 고른 행동 | R_base 가 고른 행동 |")
    A("|---|---|---|---|---|---|---|")
    order = ["all", "not_seen", "seen", "seen_in_cover", "seen_not_in_cover", "seen_dist_lt4", "seen_dist_4_8",
             "seen_dist_ge8", "seen_app_ge09", "seen_app_07_09", "seen_app_lt07", "in_cover", "not_in_cover"]
    for bn in order:
        e = rlw["bins"][bn]
        A(f"| {BIN_KO[bn]} | {e['n']:,} | {_pct(e['rl_vs_fsm'])} | {_pct(e['rl_vs_rbase'])} | "
          f"{_beh4(e['dist']['rl'], 0)} | {_beh4(e['dist']['fsm'], 0)} | {_beh4(e['dist']['rbase'], 0)} |")
    A("")
    A(f"- RL–FSM 불일치 {n_dis_f:,}건 가운데 'RL 먹기, FSM 숨기'가 {g_h:,}건({_pct(g_h / max(n_dis_f, 1), 0)})이다.")
    A(f"- RL–R_base 불일치 {n_dis_b:,}건 가운데 'RL 먹기, R_base 도망'이 {g_f:,}건({_pct(g_f / max(n_dis_b, 1), 0)})이다. "
      f"위협이 4 안에 보일 때 R_base 는 100% 도망가지만 RL 은 먹기 {_pct(near4['dist']['rl'][0], 0)}, 도망 "
      f"{_pct(near4['dist']['rl'][1], 0)}, 숨기 {_pct(near4['dist']['rl'][2], 0)}, 얼기 {_pct(near4['dist']['rl'][3], 0)}"
      f"다. 하지만 이 상황은 전체 개체-시간의 {_pct(near4['n'] / rlw['agent_steps'], 1)}뿐이다.")
    A(f"- '각자 비율대로 아무렇게나 골랐을 때'의 불일치(기준선)와 비교: 전체에서 RL≠R_base 실제 {_pct(b_all['rl_vs_rbase'])} "
      f"대 기준선 {_pct(b_all['rl_vs_rbase_chance'])}, RL≠FSM 실제 {_pct(b_all['rl_vs_fsm'])} 대 기준선 "
      f"{_pct(b_all['rl_vs_fsm_chance'])}. 위협이 보일 때 RL≠R_base {_pct(b_seen['rl_vs_rbase'])} 대 "
      f"{_pct(b_seen['rl_vs_rbase_chance'])}, RL≠FSM {_pct(b_seen['rl_vs_fsm'])} 대 {_pct(b_seen['rl_vs_fsm_chance'])}. "
      "즉 RL 의 선택은 R_base 의 '언제'와 어느 정도 겹치지만(기준선보다 확실히 낮다), FSM 의 '언제'와는 거의 겹치지 않는다. "
      "세 정책이 다른 가장 큰 이유는 '언제'보다 '얼마나 자주' 먹기를 멈추느냐다.")
    A(f"- 한 스텝에 선택이 갈리는 개체: 평균 RL≠FSM {F['split_agents_per_step']:.1f}마리, RL≠R_base "
      f"{F['split_agents_per_step_rbase']:.1f}마리({N}마리 중). 이것은 고르는 순간만 센 값이라, 화면에 보이는 '먹기가 아닌 "
      f"점'의 차이(따로 돌린 세계에서 FSM − RL 평균 약 {F['separate_gap_8seeds']:.0f}마리, 3절)보다 작다.")
    A(f"- 시드별 범위(RL 이 움직이는 세계, 8시드): RL≠FSM {_pct(rlw['per_seed']['rl_vs_fsm']['min'], 0)}~"
      f"{_pct(rlw['per_seed']['rl_vs_fsm']['max'], 0)}, RL≠R_base {_pct(rlw['per_seed']['rl_vs_rbase']['min'], 0)}~"
      f"{_pct(rlw['per_seed']['rl_vs_rbase']['max'], 0)}. RL 이 FSM 보다 R_base 에 가까운 시드: {closer}/"
      f"{len(rlw['per_seed']['rl_vs_fsm']['values'])}.")
    A("")
    A("**거꾸로 확인** — 다른 정책이 세계를 움직일 때도 같은 결론인가:")
    A("")
    A("| 세계를 움직인 정책 | 고를 수 있는 결정 비율 | RL≠FSM (전체 / 위협 보임) | RL≠R_base (전체 / 위협 보임) | "
      "한 스텝에 선택이 갈리는 개체 RL≠FSM | 한 스텝에 선택이 갈리는 개체 RL≠R_base |")
    A("|---|---|---|---|---|---|")
    for drv in POLICIES:
        d = D[drv]
        A(f"| {LABEL[drv]} | {_pct(d['choice_share'])} | {_pct(d['bins']['all']['rl_vs_fsm'])} / "
          f"{_pct(d['bins']['seen']['rl_vs_fsm'])} | {_pct(d['bins']['all']['rl_vs_rbase'])} / "
          f"{_pct(d['bins']['seen']['rl_vs_rbase'])} | {d['per_agent_time']['rl_vs_fsm'] * N:.1f} | "
          f"{d['per_agent_time']['rl_vs_rbase'] * N:.1f} |")
    A("")
    A("FSM 이 움직이는 세계에서 RL–FSM 불일치가 더 큰 것은 FSM 이 개체를 은신처로 모아 '은신처 안 + 위협 보임' 순간이 "
      "많아지기 때문이다(그 칸에서 FSM 은 100% 숨고 RL 은 대부분 먹는다).")
    A("")
    A("## 3. 눈에 보이는 지표 (같은 시드에서 정책마다 따로 돌림, 8시드)")
    A("")
    A("| 지표 | RL s3 | FSM | R_base |")
    A("|---|---|---|---|")

    def row(name, f):
        A(f"| {name} | {f(vr)} | {f(vf)} | {f(vb)} |")

    row("시간 비율 먹기 / 도망 / 숨기 / 얼기", lambda v: _beh4([v["behavior_share"][b] for b in BEH]))
    row("동시에 먹기가 아닌 개체 (평균 / 95% / 최대, 128마리 중)",
        lambda v: f"{v['non_graze_agents']['mean']:.1f} / {v['non_graze_agents']['p95']:.0f} / "
                  f"{v['non_graze_agents']['max']:.0f}")
    row("먹기가 아닌 개체가 10마리 이상인 시간", lambda v: _pct(v["non_graze_agents"]["frac_steps_ge10"], 0))
    row("먹기가 아닌 개체 중 은신처 안", lambda v: _pct(v["non_graze_in_cover_share"], 0))
    for k, b in enumerate(BEH):
        row(f"{BEH_KO[k]} 한 번 지속 (중앙값 / 90%, 초)",
            lambda v, b=b: ("—" if v["bouts"][b]["n"] == 0 else
                            f"{v['bouts'][b]['median_s']:.1f} / {v['bouts'][b]['p90_s']:.1f}"))
    row("숨기 한 번 지속 평균 (초)",
        lambda v: "—" if v["bouts"]["HIDE"]["n"] == 0 else f"{v['bouts']['HIDE']['mean_s']:.1f}")
    row("개체 하나가 1분에 시작하는 도망 / 숨기 / 얼기 횟수",
        lambda v: " / ".join(f"{v['bouts_per_agent_min'][b]:.2f}" for b in ("FLEE", "HIDE", "FREEZE")))
    row("무리 반응: 1초 안에 10마리 이상 먹기를 멈춤 (분당)", lambda v: f"{v['herd_events_per_min']['10']:.1f}")
    row("무리 반응: 1초 안에 20마리 이상 (분당)", lambda v: f"{v['herd_events_per_min']['20']:.1f}")
    row("1초 안에 먹기를 멈춘 최대 개체 수", lambda v: f"{v['max_graze_exits_in_1s']}")
    row("가장 가까운 이웃까지 평균 거리", lambda v: f"{v['nn_dist_mean']:.2f}")
    row("무리 퍼짐 (중심에서 RMS 거리)", lambda v: f"{v['spread_rms']:.1f}")
    row("보행 정지 / 걷기 / 뛰기 (시간 비율)",
        lambda v: f"{_pct(v['gait_share']['stop'], 0)} / {_pct(v['gait_share']['walk'], 0)} / "
                  f"{_pct(v['gait_share']['run'])}")
    row("뛰는 개체 (평균 / 95%)",
        lambda v: f"{v['running_agents']['mean']:.1f} / {v['running_agents']['p95']:.0f}")
    row("은신처 안에 있는 시간", lambda v: _pct(v["in_cover_share"], 0))
    row("위협이 보이는 시간 (개체 기준)", lambda v: _pct(v["threat_seen_share"]))
    row("행동이 바뀌는 횟수 (세계 전체, 초당)", lambda v: f"{v['switches_per_sec_world']:.1f}")
    row("잡아먹힘 / 굶어 죽음 (세계 하나, 분당)",
        lambda v: f"{v['pred_deaths_per_min']:.1f} / {v['starve_deaths_per_min']:.1f}")
    A("")
    ng = {p: 1.0 - V[p]["behavior_share"]["GRAZE"] for p in POLICIES}
    jn = J["non_graze"]
    A(f"- 정책 사이에 크게 다른 것: 먹기가 아닌 시간(RL {_pct(ng['rl'])}·FSM {_pct(ng['fsm'])}·R_base {_pct(ng['rbase'])} — "
      f"판정 20시드로는 {_pct(jn['rl'])}·{_pct(jn['fsm'])}·{_pct(jn['rbase'])}), 그 대부분인 FSM 의 숨기(시간의 "
      f"{_pct(vf['behavior_share']['HIDE'])}, RL {_pct(vr['behavior_share']['HIDE'])}), 동시에 먹기가 아닌 개체 수(평균 FSM "
      f"{vf['non_graze_agents']['mean']:.1f} 대 RL {vr['non_graze_agents']['mean']:.1f} — 차이 약 "
      f"{F['separate_gap_8seeds']:.0f}마리), 큰 무리 반응(20마리 이상, 분당 FSM {vf['herd_events_per_min']['20']:.1f}·"
      f"R_base {vb['herd_events_per_min']['20']:.1f}·RL {vr['herd_events_per_min']['20']:.1f}).")
    A(f"- 거의 같은 것: 가장 가까운 이웃까지 거리({vr['nn_dist_mean']:.2f}·{vf['nn_dist_mean']:.2f}·"
      f"{vb['nn_dist_mean']:.2f}), 무리 퍼짐({vr['spread_rms']:.1f}·{vf['spread_rms']:.1f}·{vb['spread_rms']:.1f}), "
      f"잡아먹히는 속도(분당 {vr['pred_deaths_per_min']:.0f}·{vf['pred_deaths_per_min']:.0f}·"
      f"{vb['pred_deaths_per_min']:.0f}).")
    A(f"- 작은 차이: 뛰는 개체(평균 {vr['running_agents']['mean']:.1f}·{vf['running_agents']['mean']:.1f}·"
      f"{vb['running_agents']['mean']:.1f}마리 — R_base 가 RL 의 두 배쯤이지만 {N}마리 중 2마리 남짓), 굶어 죽음(분당 "
      f"{vr['starve_deaths_per_min']:.1f}·{vf['starve_deaths_per_min']:.1f}·{vb['starve_deaths_per_min']:.1f} — 판정 "
      f"20시드로는 RL 이 FSM 보다 약 {100 * (1 - J['starve_ratio_rl_over_fsm']):.0f}% 적고 R_base 와 비슷하다).")
    A(f"- RL 은 도망보다 얼기를 많이 쓴다(얼기 시간 {_pct(vr['behavior_share']['FREEZE'])}, 도망 "
      f"{_pct(vr['behavior_share']['FLEE'])}). 얼기는 멈춰 서는 행동이라, 먹으려고 멈춘 초록 점과 움직임으로는 구분되지 "
      "않고 색(흰색)과 '!' 표시로만 구분된다.")
    A("")
    A(f"## 4. 사용자가 본 영상과 같은 창 (시드 {meta['video']['seed']}, 0~{meta['video']['steps']}스텝, "
      f"{meta['video']['stride']}스텝마다 1프레임 = 약 {sp:.0f}배속)")
    A("")
    A("| 프레임마다 | RL s3 | FSM | R_base |")
    A("|---|---|---|---|")

    def vrow(name, f):
        A(f"| {name} | {f(wr)} | {f(wf)} | {f(wb)} |")

    vrow("먹기가 아닌 점 (평균 / 95% / 최대)",
         lambda w: f"{w['non_graze_dots_mean']:.1f} / {w['non_graze_dots_p95']:.0f} / {w['non_graze_dots_max']:.0f}")
    vrow("도망(주황) / 숨기(파랑) / 얼기(흰색) 점 평균",
         lambda w: " / ".join(f"{w['dots_mean'][b]:.1f}" for b in ("FLEE", "HIDE", "FREEZE")))
    vrow("먹기가 아닌 점 중 은신처(어두운 원) 안", lambda w: _pct(w["non_graze_in_cover_share"], 0))
    vrow("먹기가 아닌 점이 10개 이상인 프레임", lambda w: _pct(w["frac_frames_ge10"], 0))
    vrow("숨는 점이 20개 이상인 프레임", lambda w: _pct(w["frac_frames_hide_ge20"], 0))
    vrow("얼어 있는 점이 5개 이상인 프레임", lambda w: _pct(w["frac_frames_freeze_ge5"], 0))
    vrow("뛰는 점 평균", lambda w: f"{w['running_dots_mean']:.1f}")
    A("")
    if VC:
        segs = VC["fsm_hide_ge20_segments_sim_sec_and_video_sec"]
        seg_txt = ", ".join(f"{s[2]:.1f}~{s[3]:.1f}초" for s in segs)
        nd = VC["non_graze_diff_rl_minus_fsm"]
        A(f"- 같은 프레임끼리 비교하면 '먹기가 아닌 점'은 FSM 이 평균 {-nd['mean']:.1f}개 많다. 차이가 10개 이상인 프레임이 "
          f"{_pct(nd['frac_abs_ge10'], 0)}, 20개 이상인 프레임이 {_pct(nd['frac_abs_ge20'], 0)}다. 차이는 거의 모두 FSM 쪽 "
          "숨기다.")
        for p in VC.get("paused", []):
            A(f"- 영상 {p['video_sec']:.0f}초(프레임 {p['frame']}, 스텝 {p['step']})에서 멈추면: 숨기(파랑) FSM "
              f"{p['fsm']['hide']}마리({p['fsm']['hide_pct']:.0f}%) 대 RL {p['rl']['hide']}마리({p['rl']['hide_pct']:.0f}%), "
              f"먹기가 아닌 점 FSM {p['fsm']['non_graze']} 대 RL {p['rl']['non_graze']}"
              + (f", R_base {p['rbase']['non_graze']}" if "rbase" in p else "") + ".")
        A(f"- FSM 에서 숨는 점이 20개 이상인 구간은 영상 시간으로 {seg_txt}이다(20초 영상, 프레임의 "
          f"{_pct(VC.get('frac_frames_fsm_hide_ge20', wf['frac_frames_hide_ge20']), 0)}). 이 구간에서 FSM 화면의 은신처 원 "
          "안에 파란 점이 모여 있다. 차이를 보려면 이 구간을 멈춰 보면 된다.")
        if VC.get("threat_seen_share_window"):
            ts = VC["threat_seen_share_window"]
            A(f"- 이 창은 위협이 많은 편이다: 위협이 보이는 개체 시간 RL 세계 {_pct(ts['rl'])}·FSM 세계 {_pct(ts['fsm'])} "
              f"(8시드 평균 RL {_pct(vr['threat_seen_share'])}·FSM {_pct(vf['threat_seen_share'])}). 그래서 평소보다 차이가 "
              "크다.")
    fz = vr['bouts']['FREEZE']['median_s']
    A(f"- RL 과 R_base 는 먹기가 아닌 점 수가 비슷하지만(평균 {wr['non_graze_dots_mean']:.1f} 대 "
      f"{wb['non_graze_dots_mean']:.1f}) 색과 움직임이 다르다: R_base 는 주황(뛰어 달아남) {wb['dots_mean']['FLEE']:.1f}개, "
      f"RL 은 흰색(제자리 얼기) {wr['dots_mean']['FREEZE']:.1f}개·파랑 {wr['dots_mean']['HIDE']:.1f}개·주황 "
      f"{wr['dots_mean']['FLEE']:.1f}개. 뛰는 점은 R_base {wb['running_dots_mean']:.1f}개, RL {wr['running_dots_mean']:.1f}개다.")
    A(f"- RL 의 얼기(흰 점)는 프레임마다 평균 {wr['dots_mean']['FREEZE']:.1f}개지만, 한 번에 중앙값 {fz:.1f}초(영상 약 "
      f"{fz / sp * 30:.0f}프레임) 뒤 다시 초록으로 돌아간다.")
    A("")
    A("## 5. 영상에서 차이가 덜 보였던 이유 — 짐작")
    A("")
    A("사람 눈에 어떻게 보이는지는 재지 않았다. 아래는 숫자로 뒷받침되는 짐작이다.")
    A("")
    A("1. 보인 차이가 'FSM 이 더 숨는다'였다. 'RL 이 무언가를 잘한다'는 장면이 아니어서, 차이를 찾으려고 RL 쪽을 보면 "
      "'그냥 먹는 무리'만 보인다.")
    A(f"2. FSM 의 숨는 점은 수로는 크게 다르지만(영상 창 프레임당 {wf['dots_mean']['HIDE']:.1f}개 대 "
      f"{wr['dots_mean']['HIDE']:.1f}개), {_pct(vf['in_cover_share_by_behavior']['HIDE'], 0)}가 어두운 은신처 원 안이고 "
      f"{_pct(vf['hide_crouched_share'], 0)}가 멈춰 웅크린 상태다. 어두운 원 안에 가만히 있는 파란 점이라 빠르게 지나가면 "
      "덜 띌 수 있다(색 대비는 재지 않았다).")
    A(f"3. RL 의 반응은 한 번에 중앙값 {min(F['rl_bout_median_s'].values()):.1f}~"
      f"{max(F['rl_bout_median_s'].values()):.1f}초라 {sp:.0f}배속에서는 깜빡임처럼 지나간다. 얼기는 멈춤이라 움직임으로도 "
      "드러나지 않는다.")
    A("4. 모두 대부분 먹고, 먹기는 세 정책이 같은 조향 코드를 쓴다. 그래서 점이 움직이는 모양, 무리 간격, 퍼짐이 같다.")
    A(f"5. 뛰는 개체는 세 정책 모두 드물다({N}마리 중 평균 {vr['running_agents']['mean']:.1f}·"
      f"{vf['running_agents']['mean']:.1f}·{vb['running_agents']['mean']:.1f}마리). '도망치는 무리'라는 눈에 띄는 장면이 "
      "거의 없다.")
    A("")
    A("## 6. 한계")
    A("")
    A("- 탐색이다. 판정이 아니고, 사전 등록한 지표가 아니다. 출시 모델 s3 하나만 쟀다(argmax).")
    A(f"- 시드 8개 × {meta['steps']}스텝이다. R1b 판정(시드 20개 × 10000스텝)의 FSM 숨기 "
      f"{_pct(J['use']['fsm']['hide'])}와 여기 {_pct(vf['behavior_share']['HIDE'])}가 다른 것처럼, 시드에 따라 값이 꽤 "
      f"흔들린다(FSM 의 먹기가 아닌 시간 비율은 시드별 {_pct(min(vf['non_graze_share_per_seed']), 0)}~"
      f"{_pct(max(vf['non_graze_share_per_seed']), 0)}). 그래서 결론의 시간 비율은 판정 값을 쓴다.")
    A("- 반사실 불일치는 '그 한 순간'의 선택만 비교한다. 다른 선택을 했다면 그 뒤에 무엇이 달라졌을지(잠금 12스텝, 위치 변화)는 "
      "세지 않는다. 또 잠금이 끝난 뒤에는 먹는 개체가 매 스텝 결정 시점이라, 위협 옆에서 오래 먹는 개체가 결정 수에 크게 "
      "들어간다.")
    A("- 영상 창 숫자는 시드 하나(10100)다. 이 시드는 위협이 많은 편이라 평균적인 세계보다 차이가 크게 나온다.")
    A("- 무리 반응은 '1초(8스텝) 창 안에 먹기 → 다른 행동 전환이 K마리 이상'으로 정의했다. 같은 위협에 대한 반응인지(공간적으로 "
      "모여 있는지)는 보지 않았다.")
    A("")
    return "\n".join(L) + "\n"


def write_report(res: dict, path: Path) -> None:
    path.write_text(render(res), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    ap.add_argument("--out", default=str(HERE / "divergence.json"))
    ap.add_argument("--md", default=str(HERE / "divergence.md"))
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--video-only", action="store_true",
                    help="영상 창(시드 10100, 1800스텝)만 세 정책으로 다시 돌려 video_compare(프레임별 점 수)를 바꾼다")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        print("묻기 호출이 궤적을 바꾸지 않음:", _check())
        return 0
    if a.video_only:
        res = json.loads(Path(a.out).read_text(encoding="utf-8"))
        with ProcessPoolExecutor(len(POLICIES)) as ex:
            vres = list(ex.map(_job, [(drv, VIDEO_SEED, VIDEO_STEPS, False) for drv in POLICIES]))
        vc = video_compare(vres)
        # 같은 세계인가: 8시드 실행(묻기 포함, 3000스텝)의 영상 창 평균과 같아야 한다
        for drv in POLICIES:
            old = res["visibility"][drv]["video_window"]["non_graze_dots_mean"]
            new = vc["mean_non_graze_dots"][drv]
            assert abs(old - new) < 1e-9, (drv, old, new)
        res["video_compare"] = vc
        print("영상 창 다시 잼:", {d: round(v, 2) for d, v in vc["mean_non_graze_dots"].items()},
              "멈춘 장면:", [(p["video_sec"], p["fsm"]["hide"], p["rl"]["hide"]) for p in vc["paused"]], flush=True)
        res["summary"] = summary(res)
        Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        write_report(res, Path(a.md))
        print("저장", a.out, a.md)
        return 0
    if not a.report_only:
        t0 = time.time()
        check = _check(steps=300)
        print("묻기 호출 궤적 동일:", check, flush=True)
        jobs = [(drv, s, a.steps, True) for drv in POLICIES for s in a.seeds]
        with ProcessPoolExecutor(a.workers) as ex:
            results = list(ex.map(_job, jobs))
        print(f"시뮬레이션 {time.time() - t0:.0f}초", flush=True)
        res = dict(meta=dict(config=CONFIG, seeds=a.seeds, steps=a.steps, rl=RL_PATH,
                             fsm="results/v3/r1b/fsm_spec.json", rbase="results/v3/r1b/rbase_spec.json",
                             step_sec=results[0]["step_sec"], N=results[0]["N"], win_steps=WIN_STEPS,
                             video=dict(seed=VIDEO_SEED, steps=VIDEO_STEPS, stride=VIDEO_STRIDE),
                             check_no_interference=check,
                             note="결정 행 = 결정 시점(rep_peek reads) & 마스크 두 칸 이상. 거리 = 보이는 가장 가까운 위협"),
                   disagreement={drv: disagreement(results, drv) for drv in POLICIES},
                   visibility={drv: visibility(results, drv) for drv in POLICIES},
                   video_compare=video_compare(results))
        Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        print("저장", a.out)
    res = json.loads(Path(a.out).read_text(encoding="utf-8"))
    res["summary"] = summary(res)
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    write_report(res, Path(a.md))
    print("저장", a.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
