"""S1-a 진단 A2 — 결과 쪽 지표가 언제 갈리는지 시간축으로 본다 → a2/timecourse.json.

    # herbivore_rl/ 에서 (a2_extract.py 다음)
    python results/v2/s1a_diag/a2/a2_timecourse.py

- 지표: rollout/reward_per_step, world/mean_energy, act/forage_mean, policy/forage_log_std, act/forage_std,
  gait/stop, act/speed_mean, act/flee_dist_mean, world/kill_ema, world/in_cover_frac, train/value_loss, probe/p_stop
- 값: (T − 1M, T + 32768] 평균(롤아웃 약 31개). T = 1, 1.5, …, 20M
- 시점마다: 좋음 9 · 나쁨 4 의 AUC(P(나쁨 < 좋음)), 문턱 하나로 맞힌 최대 수(13개 중), 묶음 평균
- 갈림 시점(결과 뒤 기술):
  · 묶음: AUC 가 0.9 이상(또는 0.1 이하)으로 끝까지 머무는 첫 T, 문턱 맞힘이 13/13 으로 끝까지 머무는 첫 T
  · 모델별: 나쁜 모델 값이 좋은 9모델 범위 밖(방향은 20M 의 나쁨 쪽)으로 나가 끝까지 머무는 첫 T
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
D = json.loads((HERE.parent / "curves.json").read_text(encoding="utf-8"))
MODELS = D["models"]
LAB = D["labels"]
TAGS = ["rollout/reward_per_step", "world/mean_energy", "act/forage_mean", "policy/forage_log_std", "act/forage_std",
        "gait/stop", "act/speed_mean", "act/flee_dist_mean", "world/kill_ema", "world/in_cover_frac",
        "train/value_loss", "probe/p_stop"]
GRID = [x / 2 for x in range(2, 41)]
W = 1.0e6
SLACK = 32768


def val(m, tag, T):
    v = D["tb"][m].get(tag)
    if v is None:
        return np.nan
    a = np.asarray(v)
    k = (a[:, 0] > T * 1e6 - W) & (a[:, 0] <= T * 1e6 + SLACK)
    return float(a[k, 1].mean()) if k.any() else np.nan


def best13(x, y):
    o = np.argsort(x)
    ys = y[o]
    n, nb = len(x), y.sum()
    cb = np.concatenate([[0], np.cumsum(ys)])
    k = np.arange(n + 1)
    return int(max((cb + (n - k) - (nb - cb)).max(), ((k - cb) + (nb - cb)).max()))


def first_stay(flags, grid):
    """flags[i] 가 i 부터 끝까지 모두 참인 첫 grid 값. 없으면 None."""
    for i in range(len(flags)):
        if all(flags[i:]):
            return grid[i]
    return None


def main() -> int:
    out = {"grid": GRID, "W": W, "tags": {}}
    for tag in TAGS:
        ms = [m for m in MODELS if tag in D["tb"][m]]
        lab = [m for m in ms if LAB[m] != "border"]
        y = np.array([LAB[m] == "bad" for m in lab], int)
        V = {m: [val(m, tag, T) for T in GRID] for m in ms}
        aucs, bests, gm, bm = [], [], [], []
        for i, T in enumerate(GRID):
            x = np.array([V[m][i] for m in lab])
            xb, xg = x[y == 1], x[y == 0]
            aucs.append(float((xb[:, None] < xg[None, :]).mean()))
            bests.append(best13(x, y))
            gm.append(float(xg.mean()))
            bm.append(float(xb.mean()))
        low_bad = aucs[-1] >= 0.5                       # 20M 에서 나쁨이 아래쪽이면 True
        auc_flag = [(a >= 0.9) if low_bad else (a <= 0.1) for a in aucs]
        per_bad = {}
        goods = [m for m in lab if LAB[m] == "good"]
        for m in lab:
            if LAB[m] != "bad":
                continue
            fl = []
            for i in range(len(GRID)):
                g = [V[q][i] for q in goods]
                fl.append(V[m][i] < min(g) if low_bad else V[m][i] > max(g))
            per_bad[m] = first_stay(fl, GRID)
        out["tags"][tag] = {"n_models": len(ms), "n_labeled": len(lab), "bad_side_at_20M": "low" if low_bad else "high",
                            "auc": aucs, "best": bests, "good_mean": gm, "bad_mean": bm, "values": V,
                            "auc_stay_from": first_stay(auc_flag, GRID),
                            "perfect_stay_from": first_stay([b == len(lab) for b in bests], GRID),
                            "per_bad_outside_good_from": per_bad}
        print(f"{tag:26s} n{len(lab):2d} bad={'low' if low_bad else 'high'} AUC>=.9 from {first_stay(auc_flag, GRID)} "
              f"perfect from {first_stay([b == len(lab) for b in bests], GRID)} per-bad {per_bad}")
        print("   AUC " + " ".join(f"{T:g}:{a:.2f}" for T, a in zip(GRID, aucs) if T in (1, 2, 3, 5, 7, 10, 12, 14, 16, 18, 20)))
        print("   good " + " ".join(f"{T:g}:{a:+.4f}" for T, a in zip(GRID, gm) if T in (1, 2, 3, 5, 7, 10, 12, 14, 16, 18, 20)))
        print("   bad  " + " ".join(f"{T:g}:{a:+.4f}" for T, a in zip(GRID, bm) if T in (1, 2, 3, 5, 7, 10, 12, 14, 16, 18, 20)))
    (HERE.parent / "timecourse.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
