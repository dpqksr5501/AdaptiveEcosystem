"""R10 공통 규칙 두뇌 (0 단계 사양 9 절) — 종 이름을 모르고 감각만 읽는다. 0 바퀴 상대·잣대·이름 모를 동물에 쓴다.

1. 나보다 1.5 배 넘게 크고 다가오는 몸이 보이면 반대쪽으로 빠르게 (나는 몸은 오르기)
2. 배고프고 고기를 먹는 몸이면 나보다 작은 가장 가까운 몸 쪽으로 빠르게
3. 발밑에 먹이가 있고 배가 덜 찼으면 먹기 (공중이면 내리기)
4. 먹이 냄새가 가장 큰 쪽으로 천천히
5. 아니면 지켜보기
"""

from __future__ import annotations

import numpy as np

from r10 import contract as C
from r10 import policy as P

_IDX = {n: i for i, n in enumerate(C.OBS_NAMES)}
_DIR0 = C.SLICES["dir"][0]
_OTH0 = C.SLICES["other"][0]
_F = {f: k for k, f in enumerate(C.OTHER_SLOT_FIELDS)}
NF = len(C.DIR_FIELDS)
BIG = np.log2(1.5) / C.NORM["ratio_log2_max"]


def _dir_of_vector(lx, ly) -> np.ndarray:
    """머리 기준 벡터 → 가장 가까운 8 방향 번호."""
    ang = np.arctan2(ly, lx)
    return (np.round(ang / (np.pi / 4)).astype(np.int64)) % 8


def decide(obs: np.ndarray, rng: np.random.Generator | None = None) -> np.ndarray:
    obs = np.asarray(obs, dtype=np.float64)
    n = obs.shape[0]
    act = np.full(n, C.A_WATCH, dtype=np.int64)
    mask = P.mask_from_obs(obs)
    free = obs[:, [_DIR0 + j * NF + 0 for j in range(C.N_DIR)]]
    food = obs[:, [_DIR0 + j * NF + 5 for j in range(C.N_DIR)]]
    energy = obs[:, _IDX["energy"]]
    airborne = obs[:, _IDX["airborne"]] > 0.5
    can_fly = obs[:, P.I_FLY] > 0.5
    meat = obs[:, _IDX["b_diet_meat"]]
    kill = obs[:, _IDX["b_kill"]] * 4.0                      # 물 수 있는 몸무게 비 (몸 벡터)
    food_here = obs[:, _IDX["food_here"]] + obs[:, _IDX["carcass_here"]] * (meat > 0.2)

    o = obs[:, _OTH0:_OTH0 + C.N_OTHER * 12].reshape(n, C.N_OTHER, 12)
    present = o[:, :, _F["present"]] > 0.5
    other = present & (o[:, :, _F["same_kin"]] < 0.5)
    big = other & (o[:, :, _F["size_ratio"]] > BIG) & (o[:, :, _F["approach"]] > 0.05)
    # 물 수 있는 상대: 질량 비 log2(상대/나)/10 ≤ log2(kill)/10
    lim = np.where(kill > 0, np.log2(np.maximum(kill, 1e-6)) / C.NORM["ratio_log2_max"], -np.inf)
    small = other & (o[:, :, _F["mass_ratio"]] <= lim[:, None])

    done = np.zeros(n, bool)
    # 1 도망
    fl = big.any(axis=1)
    if fl.any():
        k = np.argmax(big, axis=1)
        lx = o[np.arange(n), k, _F["x"]]
        ly = o[np.arange(n), k, _F["y"]]
        j = _dir_of_vector(-lx, -ly)
        # 막힌 방향이면 열린 쪽 가운데 반대에 가까운 것
        score = free - 0.3 * np.abs(((np.arange(8)[None, :] - j[:, None] + 4) % 8) - 4)
        j2 = np.argmax(score, axis=1)
        a = C.A_FAST0 + j2
        a = np.where(can_fly & ~airborne, C.A_UP, a)
        act = np.where(fl, a, act)
        done |= fl
    # 2 사냥
    hunt = ~done & (kill > 0) & (energy < 0.7) & small.any(axis=1)
    if hunt.any():
        d = np.where(small, np.hypot(o[:, :, _F["x"]], o[:, :, _F["y"]]), np.inf)
        k = np.argmin(d, axis=1)
        j = _dir_of_vector(o[np.arange(n), k, _F["x"]], o[np.arange(n), k, _F["y"]])
        a = np.where(airborne, np.where(o[np.arange(n), k, _F["height_diff"]] < -0.05, C.A_DIVE, C.A_FAST0 + j), C.A_FAST0 + j)
        act = np.where(hunt, a, act)
        done |= hunt
    # 3 먹기
    eat = ~done & (food_here > 0.05) & (energy < 0.95)
    act = np.where(eat, np.where(airborne, C.A_DOWN, C.A_EAT), act)
    done |= eat
    # 4 먹이 쪽
    smell = ~done & (food.max(axis=1) > 0.02)
    j = np.argmax(food * (free > 0.05), axis=1)
    act = np.where(smell, C.A_SLOW0 + j, act)
    act = np.where(mask[np.arange(n), act], act, C.A_WATCH)
    return act
