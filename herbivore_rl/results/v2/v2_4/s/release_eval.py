"""v2.4s 출시 후보의 평가 시드 값(보고용, 출시 규칙은 탐색 시드로 이미 골랐다 — `confirm/judge.json` release).

    # herbivore_rl/ 에서
    python results/v2/v2_4/s/release_eval.py

판정 세계 configs/v2_4s_on.yaml, 평가 시드 10000~10019 × 5000스텝, 결정 모드, G_γ γ 0.9916661555611042. 비교로 v2.1 출시
모델 s1a_g_s58(관측 앞 7칸)도 같은 조건으로 잰다. 결과: confirm/release_eval_seeds.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

NAMES = ("v2_4sp_g995_s20", "v2_4sp_g995_s22")
KEYS = ("g_gamma", "n1", "starve_rate", "predation_rate", "survival", "repro", "b1_day", "p_rest_cover_night",
        "p_rest_cover_day", "p_stop_night", "p_stop_day")


def main() -> int:
    import env.torch_init  # noqa: F401
    from diagnose_v2 import clean
    from env_v2 import rollout as ro
    from env_v2.config import load_v2_config

    import daynight_v2 as dnv

    cfg = load_v2_config(ROOT / "configs" / "v2_4s_on.yaml")
    specs = {n: {"kind": "learned", "model": str(ROOT / "ckpt" / "v2" / f"{n}.zip")} for n in NAMES}
    specs["s1a_g_s58"] = dnv.take7({"kind": "learned", "model": str(ROOT / "ckpt" / "v2" / "s1a_g_s58.zip")})
    res = ro.run_specs(cfg, specs, list(range(10000, 10020)), 5000, gamma=0.9916661555611042, workers=16)
    out = {}
    for n, rows in res.items():
        rows = [clean(ro.public_row(r)) for r in rows]
        out[n] = {k: float(np.nanmean([r[k] for r in rows])) for k in KEYS}
        print(n, {k: round(v, 5) for k, v in out[n].items()}, flush=True)
    (HERE.parent / "confirm" / "release_eval_seeds.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
