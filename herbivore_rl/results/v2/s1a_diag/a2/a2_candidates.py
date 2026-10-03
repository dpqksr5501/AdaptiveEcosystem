"""S1-a 진단 A2 — 조기 감지 규칙 후보의 성적표 → a2/candidates.json.

    # herbivore_rl/ 에서 (a2_signals.py 다음)
    python results/v2/s1a_diag/a2/a2_candidates.py

- 후보 1: 시점 T(1·2·3·5·10M)마다 a2_signals 의 13모델 최고 지표(best → loo → |auc−0.5| 순, 결과 뒤 선택)
- 후보 2: 결과 쪽 지표(미리 고른 4개: rollout/reward_per_step, world/mean_energy, act/forage_mean, probe/p_stop)의 win 값
- 열: best/13(탐침은 /10), loo, 단일 지표 정확 p(라벨 배정 715(탐침 210)가지 중 best 가 관측 이상인 비율, 지표 선택 보정 없음),
  시점 다중 보정 p_fw(그 시점 지표 전체 최댓값 기준, a2_signals), 스레드 1 부분 best/10,
  같은 문턱·방향을 a2_signals 시점 목록의 앞뒤 시점과 20M 에 그대로 대었을 때 맞힌 수(안정성), 경계 s21 예측
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
S = json.loads((HERE.parent / "signals.json").read_text(encoding="utf-8"))
C = json.loads((HERE.parent / "curves.json").read_text(encoding="utf-8"))
LAB = C["labels"]
MODELS = C["models"]
THREADS = {m: C["meta"][m]["threads"] for m in MODELS}
MAIN = [1, 2, 3, 5, 10]
FIXED = ["win:rollout/reward_per_step", "win:world/mean_energy", "win:act/forage_mean", "win:probe/p_stop"]


def labelings(n, k):
    out = []
    for c in itertools.combinations(range(n), k):
        y = np.zeros(n, int)
        y[list(c)] = 1
        out.append(y)
    return np.array(out)


def best_of(x, Y):
    o = np.argsort(x)
    ys = Y[:, o]
    n = len(x)
    k = np.arange(n + 1)
    cb = np.concatenate([np.zeros((len(Y), 1), int), np.cumsum(ys, 1)], 1)
    nb = ys.sum(1, keepdims=True)
    return np.maximum((cb + (n - k) - (nb - cb)).max(1), ((k - cb) + (nb - cb)).max(1))


TS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20]


def _nb(T):
    """a2_signals 시점 목록에서 T 의 앞·뒤 시점과 20M."""
    i = TS.index(T)
    return sorted({TS[j] for j in (i - 1, i + 1) if 0 <= j < len(TS)} | {20})


def apply(feat, T, dr, thr, models):
    v = S["values"][feat].get(str(T))
    if v is None:
        return None
    ok = 0
    for m in models:
        x = v[m]
        pred = (x < thr) if dr == "low" else (x > thr)
        ok += int(pred == (LAB[m] == "bad"))
    return ok


def main() -> int:
    rows = []
    for T in MAIN:
        bt = S["by_T"][str(T)]
        top = sorted(bt["all13"].items(), key=lambda kv: (-kv[1]["best"], -kv[1]["loo"], -abs(kv[1]["auc"] - 0.5)))[0][0]
        for feat, src in [(top, "top"), *[(f, "fixed") for f in FIXED]]:
            probe = "probe/" in feat
            r = (bt["threads1"] if probe else bt["all13"])[feat]
            ms = [m for m in MODELS if LAB[m] != "border" and (not probe or THREADS[m] == 1)]
            x = np.array([S["values"][feat][str(T)][m] for m in ms])
            y = np.array([LAB[m] == "bad" for m in ms], int)
            Y = labelings(len(ms), int(y.sum()))
            p1 = float((best_of(x, Y) >= r["best"]).mean())
            t1 = bt["threads1"][feat]
            border = S["values"][feat][str(T)]["v2_2r_t0_s21"]
            row = {"T": T, "feat": feat, "src": src, "n": len(ms), "best": r["best"], "loo": r["loo"], "auc": r["auc"],
                   "dir": r["dir"], "thr": r["thr"], "rho": r.get("rho"), "p_single": p1,
                   "p_fw_T": bt["fw"]["threads1_all" if probe else "all"]["p_fw"], "threads1_best": t1["best"],
                   "border_pred_bad": bool((border < r["thr"]) if r["dir"] == "low" else (border > r["thr"])),
                   "same_rule_at": {str(T2): apply(feat, T2, r["dir"], r["thr"], ms)
                                    for T2 in _nb(T)}}
            rows.append(row)
            print(f"T={T:2d} {src:5s} {feat:32s} best {r['best']}/{len(ms)} loo {r['loo']} auc {r['auc']:.2f} "
                  f"p1 {p1:.3f} p_fw {row['p_fw_T']:.3f} thr1 {t1['best']}/10 {r['dir']} {r['thr']:+.4f} "
                  f"s21->{'bad' if row['border_pred_bad'] else 'good'} same-rule {row['same_rule_at']}")
    (HERE.parent / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
