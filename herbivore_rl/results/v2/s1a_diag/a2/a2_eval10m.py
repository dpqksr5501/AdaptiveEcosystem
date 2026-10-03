"""S1-a 진단 A2 — 10M 중간 저장과 20M 최종을 같은 짧은 평가로 잰다 → a2/eval10m.json.

    # herbivore_rl/ 에서
    python results/v2/s1a_diag/a2/a2_eval10m.py            # 결정 모드 → eval10m.json
    python results/v2/s1a_diag/a2/a2_eval10m.py stoch      # 확률 모드(학습 분포에 가깝다) → eval10m_stoch.json (C2 는 상수라 같다)

- 모델: v2_1_s{0,1,2} (--threads 3), v2_1c_s3{0..4} (--threads 1). 각각 `<이름>_10m.zip`(실제 10M 직후)과 `<이름>.zip`(20M)
- 비교 기준: C2 상수(E1-b, `diag_v2_1c_s30/constsearch.json` best)
- 평가: 결정 모드, 평가 시드 10000~10009 × 3000스텝, configs/v2_1.yaml, γ 0.9916661555611042(끝 600스텝 제외)
- 열: G_γ·아사율·피식률·수명·번식 + World.gait_stats 열(p_stop_hungry·p_stop_full·stall_frac·hungry_frac·starve_share 등)
- 워커 6. 코어 코드는 고치지 않는다(run_specs 를 부르기만 한다).
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저

import json  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import numpy as np  # noqa: E402

from env_v2.config import load_v2_config  # noqa: E402
from env_v2.rollout import public_row, run_specs  # noqa: E402

GAMMA = 0.9916661555611042
STEPS = 3000
SEEDS = list(range(10000, 10010))
WORKERS = 6
MODELS = ["v2_1_s0", "v2_1_s1", "v2_1_s2"] + [f"v2_1c_s{s}" for s in range(30, 35)]
C2 = [0.9709889334578663, 0.7849404966375042, 0.2182330585135458, 0.03358694847233987, 0.4913744307309694]
COLS = ["g_gamma", "starve_rate", "predation_rate", "survival", "repro", "mean_return", "starve_share",
        "p_stop_hungry", "p_stop_full", "stall_frac", "hungry_frac", "stop_frac", "walk_frac", "run_frac",
        "stop_frac_cmd", "walk_frac_cmd", "run_frac_cmd", "b1", "b2", "b8", "intake_per_step", "drain_per_step"]


def main() -> int:
    stoch = len(sys.argv) > 1 and sys.argv[1] == "stoch"
    cfg = load_v2_config(ROOT / "configs" / "v2_1.yaml")
    specs = {}
    for m in MODELS:
        specs[f"{m}@10m"] = {"kind": "learned", "model": str(ROOT / "ckpt" / "v2" / f"{m}_10m.zip")}
        specs[f"{m}@20m"] = {"kind": "learned", "model": str(ROOT / "ckpt" / "v2" / f"{m}.zip")}
        if stoch:
            specs[f"{m}@10m"]["mode"] = specs[f"{m}@20m"]["mode"] = "stochastic"
    specs["C2"] = {"kind": "fixed", "action": C2}
    t0 = time.time()
    out = run_specs(cfg, specs, SEEDS, STEPS, workers=WORKERS, gamma=GAMMA)
    rows = {k: [public_row(r) for r in v] for k, v in out.items()}
    mean = {k: {c: float(np.nanmean([r.get(c, np.nan) for r in v])) for c in COLS} for k, v in rows.items()}
    res = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "command": "python results/v2/s1a_diag/a2/a2_eval10m.py" + (" stoch" if stoch else ""), "config": "configs/v2_1.yaml",
           "seeds": SEEDS, "steps": STEPS, "gamma": GAMMA, "mode": "stochastic" if stoch else "deterministic", "specs": specs,
           "elapsed_s": time.time() - t0, "mean": mean, "rows": rows}
    (HERE.parent / ("eval10m_stoch.json" if stoch else "eval10m.json")).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in mean.items():
        print(f"{k:16s} G {v['g_gamma']:+.3f} starve {v['starve_rate']:.5f} pS|h {v['p_stop_hungry']:.3f} "
              f"pS|f {v['p_stop_full']:.3f} hungry {v['hungry_frac']:.3f} stall {v['stall_frac']:.4f}")
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
