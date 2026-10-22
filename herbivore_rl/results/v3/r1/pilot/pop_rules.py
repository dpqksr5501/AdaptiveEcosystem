"""R1 진단(기록용): 무리 전체가 같은 손 규칙을 쓸 때의 성과 (results/v3/r1/PREREG.md 변경 기록 10-07 '팔 비교 중 진단').

판정 세계 configs/v3_r1_on.yaml, 보정 시드 20000~20007 × 3000스텝, G_γ(γ 0.9916661555611042, tail 600).
정책: 늘 먹기(C_GRAZE), R_base(θ 4, a 0.9), R_base + 얼기(가까운 위협), R_base + 숨기, FSM(숨기 > 얼기 > R_base).

    python results/v3/r1/pilot/pop_rules.py [--theta 4 --approach 0.9] [--seeds ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

GAMMA = 0.9916661555611042


def main() -> int:
    import repertoire_rules as rr
    from env_v2.config import load_v2_config
    from env_v2.rollout import run_specs

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/v3_r1_on.yaml")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(20000, 20008)))
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--theta", type=float, default=4.0)
    ap.add_argument("--approach", type=float, default=0.9)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "pop_rules.json"))
    a = ap.parse_args()
    cfg = load_v2_config(ROOT / a.config)
    geo = rr._geom(cfg)

    def with_x(*xs):
        spec = rr.rule_spec(cfg, a.theta, a.approach)
        for x, mode in xs:
            spec["wrap"].append(dict(factory="repertoire_rules:x_rule", x=x, mode=mode, slots=None, **rr.NICHES[x], **geo))
        return spec

    specs = {
        "c_graze": {"kind": "fixed", "action": [0.0]},
        "r_base": with_x(),
        "r_base+freeze_near": with_x(("freeze", "cross")),
        "r_base+hide": with_x(("hide", "niche")),
        "fsm": with_x(("freeze", "cross"), ("hide", "niche")),
    }
    rows = run_specs(cfg, specs, a.seeds, a.steps, workers=a.workers, gamma=GAMMA, tail=600)
    out = {}
    base = np.array([r["g_gamma"] for r in rows["c_graze"]])
    for name, rs in rows.items():
        g = np.array([r["g_gamma"] for r in rs])
        d = g - base
        sd = d.std(ddof=1) if len(d) > 1 else float("nan")
        out[name] = dict(g_gamma=float(g.mean()), minus_c_graze=float(d.mean()),
                         t=float(d.mean() / (sd / np.sqrt(len(d)))) if sd > 0 else None,
                         pred=float(np.mean([r["predation_rate"] for r in rs])),
                         starve=float(np.mean([r["starve_rate"] for r in rs])))
        print(f"{name:22s} G_γ {out[name]['g_gamma']:.4f}  − 늘 먹기 {out[name]['minus_c_graze']:+.4f} (t {out[name]['t']})  "
              f"피식 {out[name]['pred']:.5f}  아사 {out[name]['starve']:.5f}")
    Path(a.out).write_text(json.dumps(dict(meta=vars(a), result=out), indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
