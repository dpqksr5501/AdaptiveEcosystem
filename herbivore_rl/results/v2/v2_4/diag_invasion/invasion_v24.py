"""v2.4 소수 침입 시험 (진단 칸, 판정 아님 — `../PREREG.md` 4절, 수정 제안서 3.2 표 0행).

    # herbivore_rl/ 에서
    python results/v2/v2_4/diag_invasion/invasion_v24.py --workers 14

128칸 중 16칸(슬롯 0~15)만 밤 규칙(`daynight_v2.night_rest`)을 쓰고 나머지는 바탕 정책 그대로다. 변형 A = 모든 에너지,
B = 배부를 때만. 바탕 = E1-b C2 상수, FIX(s1a_g_s58 결정, 관측 앞 7칸). 범위 양 끝 4칸 = 하루 길이 {600, 1800} ×
포식자 속도 {[0.6, 0.7], [0.85, 0.95]}. 탐색 시드 12000~12039 × 5000스텝. 통계는 침입 개체 − 거주 개체의
개체-스텝당 피식·아사·보상(시드별), 짝 t(40시드). 결과: invasion.json, invasion.md.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

SEEDS = list(range(12000, 12040))
STEPS = 5000
FOCAL = list(range(16))
C2 = [0.9709889334578663, 0.7849404966375042, 0.2182330585135458, 0.03358694847233987, 0.4913744307309694]
CELLS = {"T600_slow": ([600], [0.6, 0.7]), "T600_fast": ([600], [0.85, 0.95]),
         "T1800_slow": ([1800], [0.6, 0.7]), "T1800_fast": ([1800], [0.85, 0.95])}


def _cfg(periods, psm):
    from env_v2.config import load_v2_config

    cfg = load_v2_config(ROOT / "configs" / "v2_4_on.yaml")
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    f["daynight"]["periods"] = list(periods)
    cfg = cfg.replace(v2=dict(cfg.v2, features=f))
    return cfg.replace(rand=dict(cfg.rand, pred_speed_mult=list(psm)))


def _job(args):
    import env.torch_init  # noqa: F401
    from env_v2 import rollout as ro
    from env_v2.world import World

    import daynight_v2 as dnv

    cell, base_name, variant, seed = args
    periods, psm = CELLS[cell]
    cfg = _cfg(periods, psm)
    base = {"kind": "fixed", "action": C2} if base_name == "C2" else \
        dnv.take7({"kind": "learned", "model": str(ROOT / "ckpt" / "v2" / "s1a_g_s58.zip")})
    spec = dnv.add_wrap(base, dnv.rule_wrap(cfg, fed_only=(variant == "B"), slots=FOCAL))
    pol = ro.build_policy(spec, seed)

    class W(World):
        def _accumulate(self, a, rew, repro, caught, starved, done):
            self.last = (caught.copy(), starved.copy())
            super()._accumulate(a, rew, repro, caught, starved, done)

    w = W(cfg, seeds=[seed])
    N = w.N
    rew_s, pred_s, starve_s = np.zeros(N), np.zeros(N), np.zeros(N)
    for _ in range(STEPS):
        _, rew, done, _ = w.step(pol(w.observe()))
        if hasattr(pol, "observe_done"):
            pol.observe_done(done)
        c, s = w.last
        rew_s += rew
        pred_s += c
        starve_s += s
    foc = np.zeros(N, dtype=bool)
    foc[FOCAL] = True
    out = {}
    for k, v in (("rew", rew_s), ("pred", pred_s), ("starve", starve_s)):
        out[k] = float(v[foc].mean() / STEPS - v[~foc].mean() / STEPS)
    return cell, base_name, variant, seed, out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args(argv)
    jobs = [(c, b, v, s) for c in CELLS for b in ("C2", "FIX") for v in ("A", "B") for s in SEEDS]
    res = {}
    with ProcessPoolExecutor(a.workers) as ex:
        for cell, b, v, s, out in ex.map(_job, jobs):
            res.setdefault(f"{cell}|{b}|{v}", {})[s] = out
    summ = {}
    for key, per in res.items():
        summ[key] = {}
        for k in ("rew", "pred", "starve"):
            d = np.array([per[s][k] for s in SEEDS])
            sd = float(d.std(ddof=1))
            summ[key][k] = dict(mean=float(d.mean()), t=float(d.mean() / (sd / math.sqrt(len(d)))) if sd > 0 else None)
    here = HERE.parent
    (here / "invasion.json").write_text(json.dumps(dict(summary=summ, per_seed=res), indent=1), encoding="utf-8")
    L = ["# v2.4 소수 침입 시험 (진단, 판정 아님)", "",
         "침입 16칸이 밤 규칙(A 모든 에너지, B 배부를 때만)을 쓰고 112칸은 바탕 정책. 값 = 침입 − 거주, 개체-스텝당, 탐색 시드 40."
         " 짝 t(자유도 39) 임계 2.023.", "",
         "| 칸 | 바탕 | 변형 | 보상 (t) | 피식 (t) | 아사 (t) |", "|---|---|---|---|---|---|"]
    for key in sorted(summ):
        c, b, v = key.split("|")
        s = summ[key]
        f = lambda x: f"{x['mean']:+.5f} ({x['t']:+.2f})" if x["t"] is not None else f"{x['mean']:+.5f}"
        L.append(f"| {c} | {b} | {v} | {f(s['rew'])} | {f(s['pred'])} | {f(s['starve'])} |")
    (here / "invasion.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
