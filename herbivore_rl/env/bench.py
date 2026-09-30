"""환경 속도 측정 (§4.6).

    python -m env.bench

목표: 초당 500스텝 이상 (§1.1). 미달이면 종료 코드 1.
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

from .config import load_config
from .world import World

TARGET_SPS = 500.0


def bench(steps: int = 4000, warmup: int = 200, seeds=(0, 1, 2, 3, 4), config=None):
    cfg = load_config(config)
    w = World(cfg, seeds=list(seeds))
    rng = np.random.default_rng(0)
    acts = rng.random((64, w.N, 4))          # 미리 뽑아서 행동 생성 비용을 뺀다

    for i in range(warmup):
        w.step(acts[i % 64])

    t0 = time.perf_counter()
    for i in range(steps):
        w.step(acts[i % 64])
    dt = time.perf_counter() - t0

    sps = steps / dt
    return sps, dt, w


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="World 속도 측정")
    p.add_argument("--steps", type=int, default=4000)
    p.add_argument("--warmup", type=int, default=200)
    p.add_argument("--config", default=None)
    args = p.parse_args(argv)

    sps, dt, w = bench(args.steps, args.warmup, config=args.config)
    ok = sps >= TARGET_SPS

    print(f"N={w.N}  world={w.size:.1f}  M={w.M}  grid={w.gw}x{w.gw}")
    print(f"{args.steps} steps in {dt:.3f}s")
    print(f"{sps:.1f} steps/sec   (agent-steps/sec = {sps * w.N:,.0f})")
    print(f"목표 {TARGET_SPS:.0f} steps/sec — {'통과' if ok else '미달'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
