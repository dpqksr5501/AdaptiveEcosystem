"""A3 H-지평 실제 세계 표본 — 같은 상태에서 '멈추기' 대 '걷기' 갈래의 할인 리턴 (학습 없음).

정책을 결정 모드로 t0 스텝까지 돌린 뒤, 배고프고(energy < 0.5) 발밑 먹이 < 0.05 인 개체(상태 S) 중 최대 16마리를
초점 개체로 고른다. 세계를 통째로 복사(deepcopy — 난수 상태까지)해 두 갈래를 만든다:
  stop: 초점 개체의 speed 열을 처음 K 스텝 동안 0 (정지 칸)으로 고정
  walk: 같은 K 스텝 동안 0.5 (걷기 칸)으로 고정
K 스텝 뒤에는 정책 그대로이고, 나머지 개체는 내내 정책 그대로다. 초점 개체의 보상을 t0 부터 600 스텝(또는 그 개체가
죽을 때까지) γ(학습값)로 할인해 더한다 — PPO 가 비교하는 Q(S, 정지 K 스텝) 대 Q(S, 걷기 K 스텝)의 표본이다.
같은 난수 상태에서 출발하므로 갈래 차는 초점 개체의 선택에서만 시작된다(이후 상호작용으로 퍼진다).

실행(herbivore_rl 에서): python results/v2/s1a_diag/a3_branch.py --workers 6
산출: results/v2/s1a_diag/a3_branch.json
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
H = HERE.parents[2]
for _p in (str(H), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from env.rollout import _init_worker  # noqa: E402
from env_v2.config import load_v2_config  # noqa: E402
from env_v2.rollout import build_policy  # noqa: E402
from env_v2.world import HUNGRY  # noqa: E402

from a3_overlay import CFG_PATH, CKPT, FOOT_FOOD, GAMMA, MODELS, TracedWorld  # noqa: E402

OUT = HERE / "a3_branch.json"
SEEDS = list(range(10000, 10005))
T0S = (1000, 2000, 3000, 4000)
KS = (30, 120)
HORIZON = 600
N_FOCAL = 16
BRANCH_MODELS = ["v2_1c_s30", "v2_1c_s31", "v2_1c_s33", "v2_2r_t0_s24", "v2_1_s0", "v2_1c_s34", "v2_2r_t0_s20"]


def run_branch(w0, pol, focal, i_speed, val, K):
    w = copy.deepcopy(w0)
    n = len(focal)
    G = np.zeros(n)
    alive = np.ones(n, dtype=bool)
    starved = np.zeros(n, dtype=bool)
    caught = np.zeros(n, dtype=bool)
    ttf = np.full(n, -1)
    repro = np.zeros(n)
    disc = 1.0
    for k in range(HORIZON):
        ix, iy = w._cell_index(w.pos)
        ok = (w.food[iy, ix] >= FOOT_FOOD)[focal] & alive & (ttf < 0)
        ttf[ok] = k
        a = np.array(pol(w.observe()), dtype=np.float64)
        if k < K:
            a[focal, i_speed] = val
        w.last_starved = None
        _, r, d, _ = w.step(a)
        G += disc * r[focal] * alive
        rep = (w.repro_cd == int(w.cfg.repro_cd)) & ~d
        repro += rep[focal] * alive
        df = d[focal] & alive
        if df.any():
            st = w.last_starved[focal]
            starved |= df & st
            caught |= df & ~st
        alive &= ~d[focal]
        disc *= GAMMA
        if not alive.any():
            break
    return G, starved, caught, ttf, repro


def job(args):
    model, seed = args
    t_start = time.time()
    cfg = load_v2_config(CFG_PATH)
    pol = build_policy({"kind": "learned", "model": str(CKPT / f"{model}.zip")}, seed)
    w = TracedWorld(cfg, seeds=[seed])
    i_speed = w.act_names.index("speed")
    rng = np.random.default_rng([seed, 777])
    t = 0
    recs = []
    for t0 in T0S:
        while t < t0:
            w.step(np.asarray(pol(w.observe()), dtype=np.float64))
            t += 1
        h = w.energy < HUNGRY * cfg.max_energy
        ix, iy = w._cell_index(w.pos)
        S = h & (w.food[iy, ix] < FOOT_FOOD)
        cand = np.flatnonzero(S)
        if not len(cand):
            continue
        focal = np.sort(rng.choice(cand, min(N_FOCAL, len(cand)), replace=False))
        # 정책이 지금 고를 보행 명령(결정 모드)
        a_now = np.asarray(pol(w.observe()), dtype=np.float64)[focal, i_speed]
        t_walk, t_run = w._sp["thresholds"]
        cmd_now = (a_now >= t_walk).astype(int) + (a_now >= t_run).astype(int)
        for K in KS:
            arms = {}
            for arm, val in (("stop", 0.0), ("walk", 0.5)):
                G, st, ca, ttf, rp = run_branch(w, pol, focal, i_speed, val, K)
                arms[arm] = {"G": G.tolist(), "starved": st.tolist(), "caught": ca.tolist(), "ttf": ttf.tolist(),
                             "repro": rp.tolist()}
            recs.append({"t0": t0, "K": K, "focal": focal.tolist(), "energy": w.energy[focal].tolist(),
                         "in_cover": w._g["in_cover"][focal].tolist(),
                         "capzero": (w.food_cap[iy, ix][focal] <= 0).tolist(),
                         "policy_cmd": cmd_now.tolist(), "arms": arms})
    return {"model": model, "seed": seed, "recs": recs, "elapsed_s": round(time.time() - t_start, 1)}


def tstat(d):
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    if n < 2:
        return {"n": n, "mean": float(d.mean()) if n else None}
    sd = d.std(ddof=1)
    return {"n": n, "mean": float(d.mean()), "sd": float(sd), "t": float(d.mean() / (sd / math.sqrt(n)))}


def summarize(rows):
    out = {}
    for model in BRANCH_MODELS:
        mrows = [r for r in rows if r["model"] == model]
        ent = {"class": MODELS[model][0]}
        for K in KS:
            G_s, G_w, st_s, st_w, ca_s, ca_w, e0, seed_means, pol_stop = [], [], [], [], [], [], [], [], []
            ttf_s, ttf_w, rp_s, rp_w, lowE = [], [], [], [], []
            for r in mrows:
                sm = []
                for rec in r["recs"]:
                    if rec["K"] != K:
                        continue
                    a, b = rec["arms"]["stop"], rec["arms"]["walk"]
                    G_s += a["G"]
                    G_w += b["G"]
                    st_s += a["starved"]
                    st_w += b["starved"]
                    ca_s += a["caught"]
                    ca_w += b["caught"]
                    e0 += rec["energy"]
                    pol_stop += [c == 0 for c in rec["policy_cmd"]]
                    ttf_s += [x if x >= 0 else HORIZON for x in a["ttf"]]
                    ttf_w += [x if x >= 0 else HORIZON for x in b["ttf"]]
                    rp_s += a["repro"]
                    rp_w += b["repro"]
                    sm += list(np.asarray(b["G"]) - np.asarray(a["G"]))
                if sm:
                    seed_means.append(float(np.mean(sm)))
            d = np.asarray(G_w) - np.asarray(G_s)
            e0 = np.asarray(e0)
            ent[f"K{K}"] = {
                "n_focal": len(d), "G_stop": float(np.mean(G_s)), "G_walk": float(np.mean(G_w)),
                "walk_minus_stop": tstat(d), "walk_minus_stop_seed_means": tstat(seed_means),
                "walk_minus_stop_e_lt_0.25": tstat(d[e0 < 0.25]), "walk_minus_stop_e_ge_0.25": tstat(d[e0 >= 0.25]),
                "p_walk_better": float((d > 0).mean()),
                "starve_stop": float(np.mean(st_s)), "starve_walk": float(np.mean(st_w)),
                "pred_stop": float(np.mean(ca_s)), "pred_walk": float(np.mean(ca_w)),
                "ttf_mean_cap600_stop": float(np.mean(ttf_s)), "ttf_mean_cap600_walk": float(np.mean(ttf_w)),
                "p_food_le120_stop": float(np.mean(np.asarray(ttf_s) <= 120)),
                "p_food_le120_walk": float(np.mean(np.asarray(ttf_w) <= 120)),
                "repro_stop": float(np.mean(rp_s)), "repro_walk": float(np.mean(rp_w)),
                "energy0_mean": float(e0.mean()), "policy_cmd_stop_frac": float(np.mean(pol_stop)),
            }
        out[model] = ent
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)
    jobs = [(m, s) for m in BRANCH_MODELS for s in SEEDS]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker) as ex:
        rows = list(ex.map(job, jobs))
    res = {"generated_by": "results/v2/s1a_diag/a3_branch.py", "seeds": SEEDS, "t0s": T0S, "Ks": KS,
           "horizon": HORIZON, "n_focal": N_FOCAL, "gamma": GAMMA, "foot_food": FOOT_FOOD,
           "elapsed_s": round(time.time() - t0, 1), "summary": summarize(rows), "rows": rows}
    OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    for m, e in res["summary"].items():
        for K in KS:
            k = e[f"K{K}"]
            print(m, e["class"], K, k["n_focal"], round(k["G_stop"], 3), round(k["G_walk"], 3),
                  k["walk_minus_stop"], k["walk_minus_stop_seed_means"], round(k["starve_stop"], 3),
                  round(k["starve_walk"], 3), round(k["p_food_le120_stop"], 3), round(k["p_food_le120_walk"], 3),
                  round(k["policy_cmd_stop_frac"], 3))
    print("elapsed", res["elapsed_s"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
