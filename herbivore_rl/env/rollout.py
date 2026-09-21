"""정책을 여러 시드에 돌려 §7.2 통계를 모은다.

§5.2 튜닝과 §7.1 비교 평가가 **같은 목표 함수**를 쓰도록 여기 한 곳에만 둔다.
§0: 두 방식이 같은 조건에서 비교되어야 한다. 롤아웃 코드가 갈라지면 그게 깨진다.

§7.1 규약: 시드마다 `World(cfg, seeds=[s])` 를 새로 만든다. 한 World를 reset()으로
돌려쓰지 않는다 — 시드 하나가 세계 하나다 (§3.5).
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from .config import Config
from .world import World

# §7.2 열 순서. compare.csv (§7.3) 의 열 순서이기도 하다.
STAT_COLUMNS = [
    "mean_return",
    "survival",
    "repro",
    "predation_rate",
    "cohesion_mean",
    "flee_dist_mean",
    "flee_dist_std",
    "cover_frac",
    "react_pred",
    "react_hunger",
]


def rollout(cfg: Config, policy, seed: int, steps: int) -> dict:
    """시드 하나. 정책은 [0,1] 행동을 돌려줘야 한다 (§1.3)."""
    w = World(cfg, seeds=[seed])
    for _ in range(steps):
        w.step(policy(w.observe()))
    s = w.stats()
    s["seed"] = seed
    return s


# --------------------------------------------------------------------- #
# 병렬 실행
# --------------------------------------------------------------------- #


def _init_worker() -> None:
    """배열이 작아서 BLAS 스레딩은 순손해다. 워커끼리 코어를 뺏지 않게 막는다."""
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[var] = "1"


def _run_one(args):
    """프로세스 경계를 넘어야 하므로 인자는 전부 picklable한 것만 받는다."""
    cfg_dict, spec, seed, steps = args
    from policies.registry import make_policy   # 워커 안에서 import

    return rollout(Config(cfg_dict), make_policy(spec), seed, steps)


def run_policy(
    cfg: Config,
    spec: dict,
    seeds,
    steps: int,
    workers: int | None = None,
) -> tuple[list[dict], dict]:
    """정책 스펙을 시드마다 돌리고 (시드별 행, 시드 평균) 을 돌려준다.

    `spec` 은 `policies.registry.make_policy` 가 읽는 dict다. 콜러블이 아닌 이유는
    Windows spawn이 클로저를 피클하지 못하기 때문이다.
    """
    seeds = list(seeds)
    if workers is None:
        workers = min(len(seeds), max(1, (os.cpu_count() or 2) - 4))

    payload = [(cfg.to_dict(), spec, int(s), steps) for s in seeds]
    if workers <= 1:
        rows = [_run_one(p) for p in payload]
    else:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as ex:
            rows = list(ex.map(_run_one, payload))

    rows.sort(key=lambda r: r["seed"])
    mean = {c: float(np.mean([r[c] for r in rows])) for c in STAT_COLUMNS}
    return rows, mean


def std_of(rows: list[dict]) -> dict:
    """§7.3 compare.md 의 ± 표준편차."""
    return {c: float(np.std([r[c] for r in rows], ddof=1)) for c in STAT_COLUMNS}
