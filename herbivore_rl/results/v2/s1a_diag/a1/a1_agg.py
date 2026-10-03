"""S1-a 진단 A1 집계 — raw/*.npz (a1_behavior.py run) → a1_summary.json 과 표 출력.

    # herbivore_rl/ 에서
    python results/v2/s1a_diag/a1/a1_agg.py --seeds eval

- 모델 값 = 그 모델의 시드 20개를 개체-스텝으로 합친 비율(전체 행 열은 시드 평균). 묶음 값 = 모델 값의 단순 평균(좋음 9, 나쁨 4).
  차의 t 는 모델 단위 Welch t 다(시드·개체-스텝 단위가 아니다). 경계(s21)는 묶음에 넣지 않고 따로 적는다.
- 아사 유형(사망 직전 100스텝 창, 결과 뒤 기술 정의): 정지형 = 명령 정지 비율 ≥ 0.5, 걷기·먹이 없음형 = 정지 < 0.5 이고
  food_density 평균 < 0.05, 걷기·먹이 있음형 = 정지 < 0.5 이고 food_density ≥ 0.05.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import a1_behavior as A  # noqa: E402
import numpy as np  # noqa: E402

BC = {c: i for i, c in enumerate(A.BIN_COLS)}
DC = {c: i for i, c in enumerate(A.DEATH_COLS)}
FC = {c: i for i, c in enumerate(A.FINE_COLS)}
ROW_COLS = ("g_gamma", "starve_rate", "predation_rate", "survival", "repro", "hungry_frac", "stop_frac_cmd",
            "walk_frac_cmd", "run_frac_cmd", "stall_frac", "p_stop_hungry", "p_stop_full", "b1", "b8",
            "intake_per_step", "drain_per_step")
FOOD_LBL = ("f<0.05", "0.05-0.2", "f>=0.2")
WIN = ((0, 10), (10, 50), (50, 100), (100, 200), (200, 400))


def bin_label(k: int) -> str:
    h, f, p = k // 6, (k // 2) % 3, k % 2
    return f"{'배고픔' if h == 0 else '배부름'}|{FOOD_LBL[f]}|{'보임' if p else '안보임'}"


def load_model(model, mode, seeds):
    jobs = [A.load_job(model, mode, s) for s in seeds]
    jobs = [j for j in jobs if j is not None]
    if not jobs:
        return None
    out = dict(
        n_seeds=len(jobs), rows=[j["row"] for j in jobs],
        bins=sum(j["bins"] for j in jobs), fine=sum(j["fine"] for j in jobs),
        tr_sum=sum(j["tr_sum"] for j in jobs), tr_n=sum(j["tr_n"] for j in jobs),
        death_rows=np.concatenate([j["death_rows"] for j in jobs]),
        ep={k: sum(j["ep"][k] for j in jobs) for k in jobs[0]["ep"]},
    )
    return out


def ratio(x, y):
    return float(x) / float(y) if y else float("nan")


def bin_metrics(b: np.ndarray, total: float) -> dict:
    n = b[BC["n"]]
    m = dict(occ=ratio(n, total), n=float(n))
    for c in ("cmd_stop", "cmd_walk", "cmd_run", "act_stop", "forage", "cohesion", "flee_dist", "cover", "speed_a",
              "intake", "drain", "cell_food", "flat_grad", "kin", "in_cover"):
        m[c] = ratio(b[BC[c]], n)
    m["net"] = m["intake"] - m["drain"] if n else float("nan")
    m["cos_grad"] = ratio(b[BC["cos_sum"]], b[BC["cos_n"]])
    m["starve_per_step"] = ratio(b[BC["starve_next"]], n)
    return m


def death_types(dr: np.ndarray) -> dict:
    if len(dr) == 0:
        return dict(n=0)
    stop = dr[:, DC["last_cmd_stop"]]
    food = dr[:, DC["last_food_density"]]
    cellf = dr[:, DC["last_cell_food"]]
    t_stop = stop >= 0.5
    t_wn = (~t_stop) & (food < 0.05)
    t_wf = (~t_stop) & (food >= 0.05)
    n = len(dr)
    out = dict(
        n=int(n), share_stop=float(t_stop.mean()), share_walk_nofood=float(t_wn.mean()),
        share_walk_food=float(t_wf.mean()),
        stop_on_emptycell=ratio((t_stop & (cellf < 0.01)).sum(), t_stop.sum()),
        age_median=float(np.median(dr[:, DC["age"]])),
        never_fed=float((dr[:, DC["life_max_e"]] <= 0.5 + 1e-9).mean()),
        life_max_e_median=float(np.median(dr[:, DC["life_max_e"]])),
    )
    for c in A.TV:
        out[f"last_{c}"] = float(dr[:, DC[f"last_{c}"]].mean())
    for c in A.LIFE_V:
        out[f"life_{c}"] = float(dr[:, DC[f"life_{c}"]].mean())
    return out


def traj_windows(tr_sum, tr_n) -> dict:
    out = {}
    for lo, hi in WIN:
        n = tr_n[lo:hi].sum()
        s = tr_sum[lo:hi].sum(0)
        out[f"{lo}-{hi}"] = {c: ratio(s[i], n) for i, c in enumerate(A.TV)}
        out[f"{lo}-{hi}"]["n"] = float(n)
    return out


def fine_curves(f: np.ndarray) -> dict:
    """에너지 10칸별 P(명령 정지)·forage·순에너지, 안 보임만. 먹이 두 묶음(<0.05, ≥0.05)과 전체."""
    nf = len(A.FINE_F_EDGES) + 1
    F = f.reshape(A.FINE_E, nf, 2, len(A.FINE_COLS))[:, :, 0, :]     # 안 보임
    groups = {"all": slice(0, nf), "f<0.05": slice(0, 2), "f>=0.05": slice(2, nf)}
    out = {}
    for name, sl in groups.items():
        G = F[:, sl, :].sum(1)
        n = G[:, FC["n"]]
        out[name] = dict(
            n=n.tolist(),
            p_stop=[ratio(G[e, FC["cmd_stop"]], n[e]) for e in range(A.FINE_E)],
            p_run=[ratio(G[e, FC["cmd_run"]], n[e]) for e in range(A.FINE_E)],
            forage=[ratio(G[e, FC["forage"]], n[e]) for e in range(A.FINE_E)],
            cover=[ratio(G[e, FC["cover"]], n[e]) for e in range(A.FINE_E)],
            net=[ratio(G[e, FC["intake"]] - G[e, FC["drain"]], n[e]) for e in range(A.FINE_E)],
        )
    return out


def summarize(model, mode, seeds):
    d = load_model(model, mode, seeds)
    if d is None:
        return None
    rows = d["rows"]
    whole = {c: float(np.nanmean([r[c] for r in rows])) for c in ROW_COLS}
    b = d["bins"]
    total = b[:, BC["n"]].sum()
    allm = bin_metrics(b.sum(0), total)
    whole.update({f"mean_{c}": allm[c] for c in ("forage", "cohesion", "flee_dist", "cover", "cos_grad", "in_cover",
                                                 "cell_food", "kin")})
    bins = {bin_label(k): bin_metrics(b[k], total) for k in range(A.N_BIN)}
    # 묶은 구간: 배고픔×먹이(보임 합침), 배고픔(먹이·보임 합침)
    merged = {}
    for h in (0, 1):
        hb = b[[k for k in range(A.N_BIN) if k // 6 == h]].sum(0)
        merged[("배고픔" if h == 0 else "배부름") + "|전체"] = bin_metrics(hb, total)
        for f in range(3):
            fb = b[[k for k in range(A.N_BIN) if k // 6 == h and (k // 2) % 3 == f]].sum(0)
            merged[("배고픔" if h == 0 else "배부름") + f"|{FOOD_LBL[f]}|전체"] = bin_metrics(fb, total)
    ep = d["ep"]
    crisis = dict(lives=ep["lives"], hit02_per_life=ratio(ep["hit02"], ep["lives"]),
                  p_starve_given_hit=ratio(ep["hit02_starve"], ep["hit02"]),
                  p_caught_given_hit=ratio(ep["hit02_caught"], ep["hit02"]),
                  p_recover_given_hit=ratio(ep["hit02_recover"], ep["hit02"]),
                  starve_share_from_crisis=ratio(ep["hit02_starve"], ep["starve"]))
    return dict(n_seeds=d["n_seeds"], whole=whole, bins=bins, merged=merged, crisis=crisis,
                death=death_types(d["death_rows"]), traj=traj_windows(d["tr_sum"], d["tr_n"]),
                fine=fine_curves(d["fine"]))


def welch(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((b.mean() - a.mean()) / se) if se > 0 else float("nan")


def group_cmp(per, mode, getter):
    good = [getter(per[m][mode]) for m, g in A.MODELS.items() if g == "good" and per.get(m, {}).get(mode)]
    bad = [getter(per[m][mode]) for m, g in A.MODELS.items() if g == "bad" and per.get(m, {}).get(mode)]
    return dict(good=float(np.nanmean(good)), bad=float(np.nanmean(bad)), diff=float(np.nanmean(bad) - np.nanmean(good)),
                t=welch(good, bad), good_min=float(np.nanmin(good)), good_max=float(np.nanmax(good)),
                bad_vals=[float(x) for x in bad])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", default="eval", choices=list(A.SEED_SETS))
    a = p.parse_args()
    seeds = A.SEED_SETS[a.seeds]
    per = {}
    for m in A.MODELS:
        per[m] = {}
        for md in A.MODES:
            s = summarize(m, md, seeds)
            if s is not None:
                per[m][md] = s
    # 묶음 비교
    groups = {}
    for md in A.MODES:
        g = {}
        for c in ROW_COLS + ("mean_forage", "mean_cohesion", "mean_flee_dist", "mean_cover", "mean_cos_grad",
                             "mean_in_cover", "mean_cell_food", "mean_kin"):
            g[f"whole.{c}"] = group_cmp(per, md, lambda s, c=c: s["whole"][c])
        for bl in list(per["v2_1_s0"][md]["bins"]) + list(per["v2_1_s0"][md]["merged"]):
            src = "bins" if bl in per["v2_1_s0"][md]["bins"] else "merged"
            for c in ("occ", "cmd_stop", "cmd_walk", "cmd_run", "forage", "cohesion", "flee_dist", "cover",
                      "intake", "drain", "net", "cell_food", "cos_grad", "in_cover"):
                g[f"{src}.{bl}.{c}"] = group_cmp(per, md, lambda s, bl=bl, c=c, src=src: s[src][bl][c])
        for c in ("hit02_per_life", "p_starve_given_hit", "p_recover_given_hit", "starve_share_from_crisis"):
            g[f"crisis.{c}"] = group_cmp(per, md, lambda s, c=c: s["crisis"][c])
        for c in ("share_stop", "share_walk_nofood", "share_walk_food", "age_median", "never_fed",
                  "last_food_density", "last_cell_food", "last_forage", "last_cmd_stop", "last_intake", "last_cover",
                  "last_kin", "last_cohesion"):
            g[f"death.{c}"] = group_cmp(per, md, lambda s, c=c: s["death"].get(c, float("nan")))
        for w in WIN:
            wl = f"{w[0]}-{w[1]}"
            for c in ("energy", "food_density", "cell_food", "cmd_stop", "cmd_run", "forage", "cover", "intake",
                      "drain", "cos_grad"):
                g[f"traj.{wl}.{c}"] = group_cmp(per, md, lambda s, wl=wl, c=c: s["traj"][wl][c])
        groups[md] = g
    out = dict(seeds=a.seeds, seed_list=seeds, models=A.MODELS, per_model=per, groups=groups)
    path = A.OUT / f"a1_summary_{a.seeds}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"써짐: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
