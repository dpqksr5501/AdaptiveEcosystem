"""§5.1 Utility AI — 학습 정책의 비교군.

§0: 두 방식이 **같은 관측·행동·조향·환경·시드·목표 함수**를 써야 한다. 그래서 이
함수는 §3.1 관측 7개를 그대로 받고 §3.2 행동 4개를 [0,1]로 그대로 돌려준다.
sigmoid는 여기 없다 — 그건 학습 정책의 (-3,3) 출력에만 붙는다 (§1.3).

§12: 비교군을 수동 상수로 두지 말 것. 기본값 `UTILITY_PARAMS`는 튜닝 시작점일 뿐이고,
실제 비교에는 `configs/utility_best.yaml`(§5.2 산출)을 쓴다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
BEST_PATH = ROOT / "configs" / "utility_best.yaml"

# §5.1 시작점. 튜닝 전 값이다.
UTILITY_PARAMS = dict(k_forage=1.0, k_coh=2.0, flee_base=0.4, flee_k=0.5, k_cover=2.0)

# §5.2 탐색 범위.
# k_coh 상한만 0~4 → 0~40 으로 정정했다 (스펙 §5.2에 사유 기록).
# §3.1 `recent_predation` EMA의 실측 범위가 0~0.078(평균 0.027)이라 k_coh=4에서는
# cohesion이 평균 0.109에 그친다. 최적은 ~0.9이고 k_coh≈33에서 나온다.
# 기존 범위로는 §5.3의 "랜덤 대비 2배"가 원리적으로 불가능했다 (상한이 1.57배).
SEARCH_SPACE = dict(
    k_forage=(0.5, 2.0),
    k_coh=(0.0, 40.0),
    flee_base=(0.1, 0.8),
    flee_k=(0.0, 1.0),
    k_cover=(0.0, 4.0),
)


def utility_policy(obs: np.ndarray, p: dict = UTILITY_PARAMS) -> np.ndarray:
    """관측 (N,7) → 행동 (N,4) in [0,1]. §5.1 그대로.

    `food`, `pd`, `cd` 는 쓰지 않는다. 스펙이 그렇게 정의했고, 항을 더하면 비교군이
    달라져 §0의 동일 조건이 깨진다.
    """
    food, pc, pd, kin, energy, rp, cd = obs.T
    forage = np.clip(p["k_forage"] * (1.0 - energy), 0, 1)
    cohesion = np.clip(p["k_coh"] * rp, 0, 1)
    flee_dist = np.clip(p["flee_base"] + p["flee_k"] * rp, 0, 1)
    cover = np.clip(p["k_cover"] * pc, 0, 1)
    return np.stack([forage, cohesion, flee_dist, cover], 1)  # [0,1]


def load_best_params(path: str | Path | None = None) -> dict:
    """§5.2 산출물. 없으면 튜닝을 먼저 돌리라고 알려준다."""
    p = Path(path) if path is not None else BEST_PATH
    if not p.exists():
        raise SystemExit(
            f"{p} 가 없다. 먼저 `python tune_utility.py` 를 돌려라 (§5.2)."
        )
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {k: float(data["params"][k]) for k in UTILITY_PARAMS}
