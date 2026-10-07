"""R1b 출시 선별 (results/v3/r1b/PREREG.md 4절): 통과한 모델 중 보정 시드 20000~20019 × 10000 의 G_γ 평균이 가장 높은 것.

판정 세계 configs/v3_r1_on.yaml, argmax(rep_learned), γ 0.9916661555611042, tail 600. 평가 시드로는 고르지 않는다.

    python results/v3/r1b/select.py            # judge/s<시드>.json 의 통과 모델만 잰다
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

CONFIG = "configs/v3_r1_on.yaml"
SEEDS = list(range(20000, 20020))
STEPS = 10000
GAMMA = 0.9916661555611042
TAIL = 600


def main() -> int:
    from env_v2.config import load_v2_config
    from env_v2.rollout import run_specs

    passed = []
    for s in range(6):
        g = json.loads((HERE / "judge" / f"s{s}.json").read_text(encoding="utf-8"))["gate"]
        if g["pass_"]:
            passed.append(s)
    out = dict(rule="R1b 통과 모델 중 보정 시드 20000~20019 × 10000 G_γ 평균 최대", passed=passed, seeds=SEEDS, steps=STEPS)
    if not passed:
        out["release"] = None
    else:
        cfg = load_v2_config(ROOT / CONFIG)
        specs = {f"s{s}": {"kind": "rep_learned", "path": f"ckpt/v3/v3_r1_g995_s{s}_20m.zip"} for s in passed}
        rows = run_specs(cfg, specs, SEEDS, STEPS, workers=18, gamma=GAMMA, tail=TAIL)
        out["g_gamma"] = {k: float(np.mean([r["g_gamma"] for r in v])) for k, v in rows.items()}
        out["starve_rate"] = {k: float(np.mean([r["starve_rate"] for r in v])) for k, v in rows.items()}
        best = max(out["g_gamma"], key=out["g_gamma"].get)
        out["release"] = dict(name=best, path=specs[best]["path"])
    (HERE / "select.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
