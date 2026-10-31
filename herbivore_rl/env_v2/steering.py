"""V2 조향 — v1 `env/steering.py` 에서 출발한 사본. v1 은 바꾸지 않는다 (계획서 결정 3).

§3.3 조향 수식 — 파이썬 참조 구현.

§1.5: 이 파일의 수식은 언리얼 `SteeringProcessor` (§9.5)와 **한 줄씩 대응**해야 한다.
계수 하나도 임의로 바꾸지 않는다. 바꾸면 양쪽을 함께 바꾸고 스펙 §3.3을 갱신한다.

C++ 대응 (§9.5):
    FVector V = P.Forage*FoodGrad + P.Cohesion*ToCentroid + P.Cover*ToCover + 1.35f*Separation;
    if (DistPredMin < P.FleeDist * Cfg.SeeRadius) V += AwayFromPred * 3.0f;
    V += BoundaryRepulsion(Pos) + ObstacleRepulsion(Pos);   // 언리얼에만 있는 항
    Velocity = V.GetSafeNormal() * Cfg.HerbSpeed;

기하 입력 `g` 의 각 항 정의 — C++가 같은 값을 만들어야 한다:

| 키 | shape | 정의 |
|---|---|---|
| `food_grad`       | (N,2) | 블러된 먹이 필드의 기울기, **단위벡터**. 평평하면 0 |
| `to_centroid`     | (N,2) | 시야 내 동족 중심으로 향하는 **단위벡터**. 동족 없으면 0 |
| `to_cover`        | (N,2) | 가장 가까운 은신처 가장자리로 향하는 **단위벡터**. 이미 안이면 0 |
| `separation`      | (N,2) | 반경 `sep_radius` 내 동족마다 `(1 - d/R) * 멀어지는 단위벡터` 를 **합**한 뒤 크기 1로 clamp |
| `d_pred_min`      | (N,)  | 가장 가까운 포식자까지의 거리. 시야에 없으면 `+inf` |
| `away_from_pred`  | (N,2) | 가장 가까운 포식자 반대 방향 **단위벡터**. 없으면 0 |
"""

from __future__ import annotations

import numpy as np

EPS = 1e-9


def _mag(v: np.ndarray) -> np.ndarray:
    """행별 크기 (n,1). np.linalg.norm보다 디스패치 비용이 없어 hot path에서 싸다."""
    return np.sqrt((v * v).sum(1, keepdims=True))


def normalize(v: np.ndarray) -> np.ndarray:
    """행마다 단위벡터로. 영벡터는 영벡터로 남긴다 (C++ `GetSafeNormal()`과 동일)."""
    n = _mag(v)
    return np.divide(v, n, out=np.zeros_like(v), where=n > EPS)


def clamp_magnitude(v: np.ndarray, max_len: float) -> np.ndarray:
    """크기를 max_len 이하로 (C++ `GetClampedToMaxSize`)."""
    n = _mag(v)
    return v * np.minimum(1.0, max_len / np.maximum(n, EPS))


def steer(g: dict, a: np.ndarray, cfg, extra: np.ndarray | None = None) -> np.ndarray:
    """조향 가중치 `a` (N,4) in [0,1] → 속도 (N,2).

    §3.3 그대로. 도주 항은 다른 항을 **대체하지 않고 더한다** — 대체하면 도망칠 때
    무리가 흩어진다.

    `extra` (N,2) 는 V2 시험 항이다(정규화 전 합에 더한다. v2.2 threat_flee, env_v2/world.py `_threat_flee_term`).
    None 이면 v1 과 같은 줄이다(계약 조향).
    """
    v = a[:, 0:1] * g["food_grad"]
    v = v + a[:, 1:2] * g["to_centroid"]
    v = v + a[:, 3:4] * g["to_cover"]
    v = v + cfg.sep_weight * g["separation"]
    fleeing = g["d_pred_min"] < a[:, 2] * cfg.see_r
    v[fleeing] += g["away_from_pred"][fleeing] * cfg.flee_weight
    if extra is not None:
        v = v + extra
    return normalize(v) * cfg.herb_speed
