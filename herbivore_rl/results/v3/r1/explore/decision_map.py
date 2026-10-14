"""R1 탐색(판정 아님): 학습 정책이 '언제' 도망·숨기·얼기를 고르는가 — 결정 지도 (results/v3/r1/PREREG.md 변경 기록 10-07
'R1 판정 결과').

판정 세계 configs/v3_r1_on.yaml, **탐색 시드 12000~12007** × 3000스텝(평가 시드 10000~10019·보정 시드 20000~ 와 겹치지 않는다).
정책은 argmax(rep_learned), FSM, R_base. 결정 시점이고 마스크가 두 칸 이상인 개체-스텝만 센다(요청이 뜻이 있는 순간).
칸: 위협 거리(보이는 가장 가까운 위협, 세계 길이) × 접근 관측 × 은신처 거리 × 에너지. 칸마다 행동 비율을 낸다.

    python results/v3/r1/explore/decision_map.py [--models ckpt/v3/v3_r1_g995_s0_20m.zip ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

CONFIG = "configs/v3_r1_on.yaml"
SEEDS = list(range(12000, 12008))
STEPS = 3000
DIST_BINS = (0.0, 4.0, 6.0, 8.0, 12.0, np.inf)
APP_BINS = (0.0, 0.7, 0.9, 1.01)
COVER_BINS = (-0.1, 0.0, 5.0, 10.0, np.inf)        # 첫 칸 = 은신처 안(0)
ENERGY_BINS = (0.0, 0.35, 0.7, 1.01)


def _spec(name: str, cfg):
    import repertoire_rules as rr  # noqa: F401
    from eval_v3 import fsm_spec

    if name == "fsm":
        return fsm_spec(cfg, ("graze", "flee", "hide", "freeze"), "near")
    if name == "rbase":
        return fsm_spec(cfg, ("graze", "flee"), "near")
    return {"kind": "rep_learned", "path": name}


def _job(args):
    name, seed = args
    import env.torch_init  # noqa: F401
    import env_v2.rollout as ro
    import repertoire_rules as rr
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import action_mask, rep_params
    from env_v2.world import World

    cfg = load_v2_config(ROOT / CONFIG)
    rep = rep_params(cfg)
    geo = rr._geom(cfg)
    w = World(cfg, seeds=[seed])
    pol = ro.build_policy(_spec(name, cfg), seed)
    ro_bind = getattr(ro, "forward_bind", None)
    if ro_bind is not None:
        ro_bind(pol, w)
    elif hasattr(pol, "bind_world"):
        pol.bind_world(w)
    rows = []
    for _ in range(STEPS):
        obs = w.observe()
        m = action_mask(w, obs, rep)
        reads = np.asarray(w.rep_peek()["reads"], dtype=bool)
        a = np.asarray(pol(obs), dtype=np.float64)
        req = a[:, 0].astype(np.int64)
        keep = reads & (m.sum(1) >= 2)
        if keep.any():
            f = rr.features_of_obs(obs[keep], geo)
            rows.append(np.stack([np.where(np.isfinite(f["dist"]), f["dist"], 99.0), f["approach"], f["cover_d"],
                                  f["energy"], f["seen"].astype(float), req[keep].astype(float)], 1))
        _, _, d, _ = w.step(a)
        hook = getattr(pol, "observe_done", None)
        if hook is not None:
            hook(d)
    return name, seed, (np.concatenate(rows) if rows else np.empty((0, 6)))


def table(x: np.ndarray) -> dict:
    """결정 표본 → 칸별 행동 비율. 보이는 위협이 있는 표본만 거리·접근 칸으로 나눈다."""
    out = {}
    seen = x[:, 4] > 0
    out["n"] = int(len(x))
    out["no_threat"] = {"n": int((~seen).sum()),
                        "p": [float((x[~seen, 5] == b).mean()) if (~seen).any() else None for b in range(4)]}
    cells = []
    s = x[seen]
    for i in range(len(DIST_BINS) - 1):
        for j in range(len(APP_BINS) - 1):
            for k in range(len(COVER_BINS) - 1):
                sel = ((s[:, 0] >= DIST_BINS[i]) & (s[:, 0] < DIST_BINS[i + 1]) & (s[:, 1] >= APP_BINS[j])
                       & (s[:, 1] < APP_BINS[j + 1]) & (s[:, 2] > COVER_BINS[k]) & (s[:, 2] <= COVER_BINS[k + 1]))
                n = int(sel.sum())
                if n:
                    cells.append(dict(dist=[DIST_BINS[i], DIST_BINS[i + 1]], app=[APP_BINS[j], APP_BINS[j + 1]],
                                      cover=[COVER_BINS[k], COVER_BINS[k + 1]], n=n,
                                      p=[float((s[sel, 5] == b).mean()) for b in range(4)]))
    out["cells"] = cells
    # 에너지별 (보이는 위협, 거리 < 6)
    en = []
    for i in range(len(ENERGY_BINS) - 1):
        sel = (s[:, 0] < 6.0) & (s[:, 3] >= ENERGY_BINS[i]) & (s[:, 3] < ENERGY_BINS[i + 1])
        en.append(dict(energy=[ENERGY_BINS[i], ENERGY_BINS[i + 1]], n=int(sel.sum()),
                       p=[float((s[sel, 5] == b).mean()) if sel.any() else None for b in range(4)]))
    out["near_by_energy"] = en
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+",
                    default=[f"ckpt/v3/v3_r1_g995_s{s}_20m.zip" for s in range(6)])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", default=str(HERE / "decision_map.json"))
    a = ap.parse_args()
    names = list(a.models) + ["fsm", "rbase"]
    jobs = [(n, s) for n in names for s in SEEDS]
    acc = {n: [] for n in names}
    with ProcessPoolExecutor(a.workers) as ex:
        for n, s, x in ex.map(_job, jobs):
            acc[n].append(x)
    res = {n: table(np.concatenate(v)) for n, v in acc.items()}
    Path(a.out).write_text(json.dumps(dict(meta=dict(config=CONFIG, seeds=SEEDS, steps=STEPS), maps=res), indent=1),
                           encoding="utf-8")
    print("저장", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
