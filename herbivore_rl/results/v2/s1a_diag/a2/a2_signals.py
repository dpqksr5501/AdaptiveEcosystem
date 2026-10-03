"""S1-a 진단 A2 — 학습 기록(TB 스칼라·탐침·R²)으로 좋음·나쁨을 시점별로 가르는 지표를 찾는다 → a2/signals.json.

    # herbivore_rl/ 에서 (a2_extract.py 다음)
    python results/v2/s1a_diag/a2/a2_signals.py

정의 (결과를 보기 전에 정한 것과 본 뒤 더한 것을 나눠 적는다)
- 라벨: 좋음 9 · 나쁨 4 · 경계 1(t0_s21). 가르기 점수는 경계를 뺀 13모델(9 대 4)로 센다. 경계는 위치만 적는다
- 연속 결과: g_minus_c2 = G_γ(결정 모드) − 같은 평가 시드 집합의 C2 (평가 1.482 / 탐색 1.217). 14모델 순위 상관
- 시점 T(M): 1·2·3·4·5·6·7·8·10·12·15·20. 주 시점은 1·2·3·5·10
- 지표 값(가족):
  win = (T − 0.5M, T + 32768] 의 기록 평균(롤아웃 약 15개, 1M 간격 기록(탐침·R²)은 T 직후 한 점)
  cum = (0, T + 32768] 평균
- 빼는 TB 열: time/fps(스레드 수에 따라 다르다), train/learning_rate·train/clip_range(상수), world/resets(스텝으로 정해진다)
- 점수(지표·시점마다):
  best = 문턱 하나(방향 둘)로 13모델 중 맞힌 최대 수. 나쁨 = 문턱 아래(또는 위)
  loo = 하나 빼고 남은 12개로 문턱·방향을 고르고(동률이면 간격이 가장 넓은 중점) 뺀 모델을 맞혔는지. 13개 중 맞힌 수
  auc = P(나쁨 값 < 좋음 값) (0.5 = 무관, 0 또는 1 = 완전 분리)
  rho = 14모델 Spearman(지표, g_minus_c2)
- 다중 비교 보정: 라벨 배정 C(13,4) = 715 가지를 모두 돌려 '그 시점 모든 지표 중 best 최댓값'의 분포를 만든다(가족별·합쳐서).
  관측 최댓값 이상이 나올 비율을 p_fw 로 적는다(같은 시점 안의 지표 선택 보정. 시점 선택은 보정하지 않는다)
- 스레드 1 부분(10모델, 6 대 4, 경계 제외)도 같은 점수를 낸다(v2_1 s0~2 만 --threads 3 이다)
- 탐침(probe/*)은 T0·v2_1c 11모델(경계 포함, 라벨 6 대 4)만 있다. 그 지표는 10모델로 따로 센다
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).resolve()
D = json.loads((HERE.parent / "curves.json").read_text(encoding="utf-8"))
MODELS = D["models"]
LAB = D["labels"]
OUT = D["outcome"]
THREADS = {m: D["meta"][m]["threads"] for m in MODELS}
SKIP = {"time/fps", "train/learning_rate", "train/clip_range", "world/resets"}
TS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20]
MAIN_TS = [1, 2, 3, 5, 10]
W = 0.5e6
SLACK = 32768


def series(m: str, tag: str) -> np.ndarray | None:
    v = D["tb"][m].get(tag)
    return None if v is None else np.asarray(v, dtype=np.float64)


def feat_value(m: str, tag: str, fam: str, T: float) -> float:
    a = series(m, tag)
    if a is None:
        return np.nan
    s, v = a[:, 0], a[:, 1]
    hi = T * 1e6 + SLACK
    k = (s > T * 1e6 - W) & (s <= hi) if fam == "win" else (s <= hi)
    return float(v[k].mean()) if k.any() else np.nan


def split_scores(x: np.ndarray, y: np.ndarray) -> tuple[int, str, float, float]:
    """문턱 하나로 맞힌 최대 수, 방향('low' = 나쁨이 아래), 문턱, 그 문턱 양옆 간격. y: 1 = 나쁨."""
    o = np.argsort(x, kind="mergesort")
    xs, ys = x[o], y[o]
    n = len(x)
    nb = ys.sum()
    cb = np.concatenate([[0], np.cumsum(ys)])            # 앞 k 개 중 나쁨 수
    k = np.arange(n + 1)
    low = cb + ((n - k) - (nb - cb))                     # 앞 k 개 = 나쁨 예측
    high = (k - cb) + (nb - cb)                          # 앞 k 개 = 좋음 예측
    best = int(max(low.max(), high.max()))
    cands = []
    for arr, dr in ((low, "low"), (high, "high")):
        for kk in np.flatnonzero(arr == best):
            lo = xs[kk - 1] if kk > 0 else xs[0] - 1.0
            hi = xs[kk] if kk < n else xs[-1] + 1.0
            if kk > 0 and kk < n and xs[kk - 1] == xs[kk]:
                continue
            cands.append((hi - lo, dr, 0.5 * (lo + hi)))
    if not cands:
        return best, "low", float(np.median(x)), 0.0
    gap, dr, thr = max(cands)
    return best, dr, float(thr), float(gap)


def predict(x: float, dr: str, thr: float) -> int:
    return int(x < thr) if dr == "low" else int(x > thr)


def loo(x: np.ndarray, y: np.ndarray) -> int:
    ok = 0
    for i in range(len(x)):
        m = np.ones(len(x), bool)
        m[i] = False
        _, dr, thr, _ = split_scores(x[m], y[m])
        ok += predict(x[i], dr, thr) == y[i]
    return int(ok)


def auc_low(x: np.ndarray, y: np.ndarray) -> float:
    xb, xg = x[y == 1], x[y == 0]
    c = (xb[:, None] < xg[None, :]).sum() + 0.5 * (xb[:, None] == xg[None, :]).sum()
    return float(c / (len(xb) * len(xg)))


def best_count_fast(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """X (F, n) 지표 값, Y (L, n) 라벨 배정 → (L,) 지표 최댓값 best. 값 동률은 없다고 본다(연속 값)."""
    n = X.shape[1]
    out = np.zeros(len(Y), dtype=int)
    k = np.arange(n + 1)
    for f in range(X.shape[0]):
        o = np.argsort(X[f])
        ys = Y[:, o]
        cb = np.concatenate([np.zeros((len(Y), 1), int), np.cumsum(ys, 1)], 1)
        nb = ys.sum(1, keepdims=True)
        low = cb + ((n - k) - (nb - cb))
        high = (k - cb) + (nb - cb)
        out = np.maximum(out, np.maximum(low.max(1), high.max(1)))
    return out


def all_labelings(n: int, nbad: int) -> np.ndarray:
    Y = []
    for c in itertools.combinations(range(n), nbad):
        y = np.zeros(n, int)
        y[list(c)] = 1
        Y.append(y)
    return np.array(Y)


def score_set(models: list[str], feats: dict, T: int) -> dict:
    lab = [m for m in models if LAB[m] != "border"]
    y = np.array([LAB[m] == "bad" for m in lab], int)
    res = {}
    for (tag, fam), vals in feats.items():
        x = np.array([vals[T][m] for m in lab])
        ok = ~np.isnan(x)
        if ok.sum() < len(x):
            continue
        b, dr, thr, gap = split_scores(x, y)
        res[f"{fam}:{tag}"] = {"best": b, "n": int(len(x)), "dir": dr, "thr": thr, "gap": gap, "loo": loo(x, y),
                               "auc": auc_low(x, y)}
    return res


def main() -> int:
    tags = sorted({t for m in MODELS for t in D["tb"][m]} - SKIP)
    feats = {}
    for tag in tags:
        for fam in ("win", "cum"):
            feats[(tag, fam)] = {T: {m: feat_value(m, tag, fam, T) for m in MODELS} for T in TS}
    g = np.array([OUT[m]["g_minus_c2"] for m in MODELS])
    lab13 = [m for m in MODELS if LAB[m] != "border"]
    lab_t1 = [m for m in MODELS if THREADS[m] == 1]
    full_tags = [k for k in feats if not k[0].startswith("probe/")]       # 14모델 모두 있는 지표
    Y13 = all_labelings(13, 4)
    Y10 = all_labelings(10, 4)
    out = {"def": {"W": W, "slack": SLACK, "TS": TS, "skip": sorted(SKIP), "labels": LAB,
                   "n_labeled": {"good": int(sum(LAB[m] == "good" for m in MODELS)),
                                 "bad": int(sum(LAB[m] == "bad" for m in MODELS)), "border": 1},
                   "threads": THREADS},
           "values": {f"{fam}:{tag}": {str(T): feats[(tag, fam)][T] for T in TS} for (tag, fam) in feats},
           "by_T": {}}
    for T in TS:
        all13 = score_set(MODELS, {k: feats[k] for k in full_tags}, T)
        t1 = score_set(lab_t1, feats, T)              # 탐침 포함(스레드 1 = T0·v2_1c)
        for name, r in all13.items():
            fam, tag = name.split(":", 1)
            x = np.array([feats[(tag, fam)][T][m] for m in MODELS])
            r["rho"] = float(spearmanr(x, g).statistic)
            r["border_value"] = feats[(tag, fam)][T]["v2_2r_t0_s21"]
            r["border_pred_bad"] = bool(predict(r["border_value"], r["dir"], r["thr"]))
        # 다중 비교 귀무: 라벨 배정 전부
        fw = {}
        for famset, keys in (("win", [k for k in full_tags if k[1] == "win"]),
                             ("cum", [k for k in full_tags if k[1] == "cum"]), ("all", full_tags)):
            X = np.array([[feats[k][T][m] for m in lab13] for k in keys])
            null = best_count_fast(X, Y13)
            obs = max(all13[f"{k[1]}:{k[0]}"]["best"] for k in keys)
            fw[famset] = {"obs_max": int(obs), "p_fw": float((null >= obs).mean()),
                          "null_dist": {str(v): int((null == v).sum()) for v in sorted(set(null.tolist()))},
                          "n_feats": len(keys)}
        lab10 = [m for m in lab_t1 if LAB[m] != "border"]
        keys10 = list(feats)
        X10 = np.array([[feats[k][T][m] for m in lab10] for k in keys10])
        null10 = best_count_fast(X10, Y10)
        obs10 = max(t1[f"{k[1]}:{k[0]}"]["best"] for k in keys10)
        fw["threads1_all"] = {"obs_max": int(obs10), "p_fw": float((null10 >= obs10).mean()),
                              "null_dist": {str(v): int((null10 == v).sum()) for v in sorted(set(null10.tolist()))},
                              "n_feats": len(keys10)}
        out["by_T"][str(T)] = {"all13": all13, "threads1": t1, "fw": fw}
        top = sorted(all13.items(), key=lambda kv: (-kv[1]["best"], -kv[1]["loo"], -abs(kv[1]["auc"] - 0.5)))[:6]
        print(f"\n=== T={T}M  p_fw(all) {fw['all']['p_fw']:.3f} (max {fw['all']['obs_max']}/13), "
              f"thr1 max {obs10}/10 p_fw {fw['threads1_all']['p_fw']:.3f}")
        for k, r in top:
            print(f"  {k:34s} best {r['best']:2d}/13 loo {r['loo']:2d} auc {r['auc']:.2f} rho {r['rho']:+.2f} "
                  f"{r['dir']} {r['thr']:+.4f} border->{'bad' if r['border_pred_bad'] else 'good'}")
        top1 = sorted(t1.items(), key=lambda kv: (-kv[1]["best"], -kv[1]["loo"]))[:3]
        for k, r in top1:
            print(f"  [thr1] {k:30s} best {r['best']:2d}/10 loo {r['loo']:2d} auc {r['auc']:.2f}")
    (HERE.parent / "signals.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
