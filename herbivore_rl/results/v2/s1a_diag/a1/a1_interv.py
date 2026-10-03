"""A1 개입 대조 (학습 없음, 결과 뒤 확인) — raw/<모델>__det+<개입>__<시드>.npz 와 같은 시드의 결정 모드를 짝지어 비교한다.

    # herbivore_rl/ 에서
    python results/v2/s1a_diag/a1/a1_interv.py      # → a1_interv_eval.json, 표 출력

- 개입: F8 = forage 0.8 고정, F1 = forage 0.1 고정, NS = 명령 정지(speed < 1/3)를 0.5(걷기)로, CV = cover 0.2 고정.
  다른 열은 학습 정책 그대로다.
- 짝 t 는 평가 시드 20개(자유도 19)의 (개입 − 결정) 차다. 기준선 C2 는 평가 시드 G_γ 1.482, 아사율 0.00043 (stage1_close.md 4절).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import a1_behavior as A  # noqa: E402
import numpy as np  # noqa: E402

COLS = ("g_gamma", "starve_rate", "predation_rate", "survival", "hungry_frac", "stop_frac_cmd", "intake_per_step")
ARMS = ("det+F8", "det+NS", "det+F8+NS", "det+F1", "det+CV", "det+F8+CV", "det+F8+NS+CV")


def paired(a, b):
    d = np.asarray(b, float) - np.asarray(a, float)
    sd = d.std(ddof=1)
    return float(d.mean()), float(d.mean() / (sd / math.sqrt(len(d)))) if sd > 0 else float("nan")


def main() -> int:
    seeds = A.SEED_SETS["eval"]
    out = {}
    for m in A.MODELS:
        base = [A.load_job(m, "det", s) for s in seeds]
        if any(j is None for j in base):
            continue
        for arm in ARMS:
            jobs = [A.load_job(m, arm, s) for s in seeds]
            if any(j is None for j in jobs):
                continue
            r = {"group": A.MODELS[m]}
            for c in COLS:
                x0 = [j["row"][c] for j in base]
                x1 = [j["row"][c] for j in jobs]
                dm, t = paired(x0, x1)
                r[c] = dict(base=float(np.mean(x0)), arm=float(np.mean(x1)), diff=dm, t=t)
            ep0 = {k: sum(j["ep"][k] for j in base) for k in base[0]["ep"]}
            ep1 = {k: sum(j["ep"][k] for j in jobs) for k in jobs[0]["ep"]}
            r["hit02_per_life"] = dict(base=ep0["hit02"] / ep0["lives"], arm=ep1["hit02"] / ep1["lives"])
            b0 = sum(j["bins"] for j in base).sum(0)
            b1 = sum(j["bins"] for j in jobs).sum(0)
            ci, ni = A.BIN_COLS.index("cos_sum"), A.BIN_COLS.index("cos_n")
            r["cos_grad"] = dict(base=b0[ci] / b0[ni], arm=b1[ci] / b1[ni])
            out[f"{m}|{arm}"] = r
    path = A.OUT / "a1_interv_eval.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"써짐: {path}")
    for k, r in out.items():
        print(f"{k:28s} {r['group'][:4]} " + " ".join(
            f"{c[:7]} {r[c]['base']:.4g}->{r[c]['arm']:.4g} (t {r[c]['t']:+.1f})" for c in ("g_gamma", "starve_rate",
                                                                                          "predation_rate"))
              + f" hit02 {r['hit02_per_life']['base']:.3f}->{r['hit02_per_life']['arm']:.3f}"
              + f" cos {r['cos_grad']['base']:.3f}->{r['cos_grad']['arm']:.3f}"
              + f" stop {r['stop_frac_cmd']['base']:.3f}->{r['stop_frac_cmd']['arm']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
