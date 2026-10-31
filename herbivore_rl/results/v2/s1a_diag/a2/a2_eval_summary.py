"""S1-a 진단 A2 — 10M 중간 저장 평가 요약 → a2/eval10m_summary.json.

    # herbivore_rl/ 에서 (a2_eval10m.py 와 a2_eval10m.py stoch 다음)
    python results/v2/s1a_diag/a2/a2_eval_summary.py

- 모델 8개(좋음 5: v2_1_s0·s1·s2, v2_1c_s32·s34 / 나쁨 3: v2_1c_s30·s31·s33). 라벨은 20M 최종 기준(stage1_close.md 8절)
- 시점(10M·20M) × 모드(결정·확률) × 지표(G_γ, 아사율, P(정지|배고픔), 배고픔 비율)마다:
  AUC = P(나쁨 < 좋음), 문턱 하나로 맞힌 최대 수(/8), 정확 p(라벨 배정 C(8,3) = 56가지 중 best 가 관측 이상)
- 짧은 평가판 '나쁨 정의'(stage1_close 8절을 같은 짧은 평가의 C2 에 댄 것, 결과 뒤 기술):
  G_γ < C2 − 1 이고 아사율 ≥ 2 × C2 아사율
- 짧은 평가 20M 결정 G_γ 와 원 평가(diag_<모델>/ablate.json C0, 시드 10000~10019 × 5000스텝)의 Spearman
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).resolve()
RES = HERE.parents[2]
MODELS = ["v2_1_s0", "v2_1_s1", "v2_1_s2", "v2_1c_s30", "v2_1c_s31", "v2_1c_s32", "v2_1c_s33", "v2_1c_s34"]
BAD = {"v2_1c_s30", "v2_1c_s31", "v2_1c_s33"}
COLS = ["g_gamma", "starve_rate", "p_stop_hungry", "hungry_frac", "p_stop_full", "starve_share"]


def best_of(x, Y):
    o = np.argsort(x)
    ys = Y[:, o]
    n = len(x)
    k = np.arange(n + 1)
    cb = np.concatenate([np.zeros((len(Y), 1), int), np.cumsum(ys, 1)], 1)
    nb = ys.sum(1, keepdims=True)
    return np.maximum((cb + (n - k) - (nb - cb)).max(1), ((k - cb) + (nb - cb)).max(1))


def main() -> int:
    y = np.array([m in BAD for m in MODELS], int)
    Y = []
    for c in itertools.combinations(range(len(MODELS)), int(y.sum())):
        z = np.zeros(len(MODELS), int)
        z[list(c)] = 1
        Y.append(z)
    Y = np.array(Y)
    out = {"models": MODELS, "bad": sorted(BAD), "modes": {}}
    for mode, fn in (("det", "eval10m.json"), ("stoch", "eval10m_stoch.json")):
        p = HERE.parent / fn
        if not p.exists():
            continue
        E = json.loads(p.read_text(encoding="utf-8"))["mean"]
        c2 = E["C2"]
        res = {"per_model": {m: {at: {c: E[f"{m}@{at}"][c] for c in COLS} for at in ("10m", "20m")} for m in MODELS},
               "C2": {c: c2[c] for c in COLS}, "sep": {}, "bad_def": {}}
        for at in ("10m", "20m"):
            for c in COLS:
                x = np.array([E[f"{m}@{at}"][c] for m in MODELS])
                xb, xg = x[y == 1], x[y == 0]
                auc = float((xb[:, None] < xg[None, :]).mean() + 0.5 * (xb[:, None] == xg[None, :]).mean())
                b = int(best_of(x, y[None, :])[0])
                pe = float((best_of(x, Y) >= b).mean())
                res["sep"][f"{at}:{c}"] = {"auc": auc, "best": b, "p_exact": pe}
            flag = {m: bool(E[f"{m}@{at}"]["g_gamma"] < c2["g_gamma"] - 1
                            and E[f"{m}@{at}"]["starve_rate"] >= 2 * c2["starve_rate"]) for m in MODELS}
            res["bad_def"][at] = flag
        g10 = [E[f"{m}@10m"]["g_gamma"] for m in MODELS]
        g20 = [E[f"{m}@20m"]["g_gamma"] for m in MODELS]
        res["spearman_g10_g20"] = float(spearmanr(g10, g20).statistic)
        if mode == "det":
            full = [json.loads((RES / f"diag_{m}" / "ablate.json").read_text(encoding="utf-8"))["controls"]["C0"]["mean"]
                    ["g_gamma"] for m in MODELS]
            res["spearman_short20_full20"] = float(spearmanr(g20, full).statistic)
            res["full20_g"] = dict(zip(MODELS, full))
        out["modes"][mode] = res
        print(f"== {mode}  C2 G {c2['g_gamma']:+.3f} starve {c2['starve_rate']:.5f}")
        for m in MODELS:
            a, b = res["per_model"][m]["10m"], res["per_model"][m]["20m"]
            print(f"  {m:10s} {'bad ' if m in BAD else 'good'} 10M G {a['g_gamma']:+.3f} st {a['starve_rate']:.5f} "
                  f"pSh {a['p_stop_hungry']:.3f} hun {a['hungry_frac']:.3f} def {int(res['bad_def']['10m'][m])} | "
                  f"20M G {b['g_gamma']:+.3f} st {b['starve_rate']:.5f} pSh {b['p_stop_hungry']:.3f} "
                  f"hun {b['hungry_frac']:.3f} def {int(res['bad_def']['20m'][m])}")
        for k, v in res["sep"].items():
            print(f"  sep {k:22s} auc {v['auc']:.2f} best {v['best']}/8 p {v['p_exact']:.3f}")
        print(f"  spearman g10~g20 {res['spearman_g10_g20']:+.2f}"
              + (f", short20~full20 {res['spearman_short20_full20']:+.2f}" if mode == "det" else ""))
    (HERE.parent / "eval10m_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
