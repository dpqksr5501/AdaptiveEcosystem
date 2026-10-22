"""0-5 기록용 평가: v2.0 모델 6개 + v1 기준을 평가 시드 20개 × 5000스텝으로 잰다."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
from env.config import load_config
from env.rollout import run_policy

def main():
    cfg = load_config()
    seeds = list(range(10000, 10020))
    models = {"v1_final": "ckpt/final.zip"}
    for s in (0, 1, 2):
        models[f"v2_0_s{s}_10m"] = f"ckpt/v2/v2_0_s{s}_10m.zip"
        models[f"v2_0_s{s}_20m"] = f"ckpt/v2/v2_0_s{s}.zip"
    out = {}
    for name, path in models.items():
        rows, mean = run_policy(cfg, {"kind": "learned", "model": str(ROOT / path)}, seeds, 5000, workers=12)
        out[name] = {"mean": mean, "per_seed": {c: [r[c] for r in rows] for c in mean}}
        print(f"{name:14s} ret {mean['mean_return']:7.2f} surv {mean['survival']:6.1f} repro {mean['repro']:5.2f} "
              f"pred {mean['predation_rate']:.5f} coh {mean['cohesion_mean']:.3f} flee {mean['flee_dist_mean']:.3f} "
              f"cover {mean['cover_frac']:.3f} react_pred {mean['react_pred']:.3f}", flush=True)
    Path(__file__).with_name("eval_v2_0.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

if __name__ == "__main__":
    main()
