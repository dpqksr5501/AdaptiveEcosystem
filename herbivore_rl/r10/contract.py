"""R10 감각 S1·행동 A1 계약 (0 단계 사양 1·7·8 절).

- 시간: 물리 한 걸음 STEP_S = 2/15 s (R9·언리얼 Native v3 와 같음), 결정은 DECISION_STEPS = 2 걸음마다, 하루 900 걸음.
- 감각 206 칸 = 자기 16 + 몸 18 + 8 방향 × 6 + 발밑 6 + 다른 동물 8 × 12 + 같은 종 4 + 환경 6 + 예비 12. 모두 머리 기준(x 머리, y 왼쪽).
  종 수·맵 크기와 상관없이 같은 크기다. 몸 값·맵은 계약 해시에 들어가지 않는다(설계 11 절 — 몸은 '배운 범위' 표로 대조).
- 행동 24 칸 = 서서 먹기 · 천천히 8 방향 · 빠르게 8 방향 · 숨기 · 지켜보기 · 오르기 · 내리기 · 빠르게 내리기 · 덮치기 · 예비 1.
  몸이 못 하는 행동은 마스크로 막는다(`action_mask`). 덮치기는 몸에 덮치기 능력(body.burst_mps)이 있고 준비됐을 때만.
- 행동 고르기: 학습과 실행 모두 막히지 않은 칸의 softmax 에서 뽑는다(개체마다 시드). 가장 높은 칸은 진단용 —
  11-19 작은 확인에서 가장 높은 칸만 고른 사슴이 빈 칸에서 먹기만 되풀이했다.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

CONTRACT = "r10_io"
SENSE_VERSION = "S1"
ACTION_VERSION = "A1"

STEP_S = 2.0 / 15.0
DECISION_STEPS = 2
DECISION_S = STEP_S * DECISION_STEPS
DAY_STEPS = 900

N_DIR = 8                     # 머리에서 왼쪽 j × 45°
N_OTHER = 8
N_SPARE_OBS = 12              # 처음 16 — 11-19 몸 칸 b_kill, 11-19 덮치기 3 칸(b_burst·burst_ready·burst_phase)으로 씀

DIR8 = np.array([[np.cos(np.radians(45.0 * j)), np.sin(np.radians(45.0 * j))] for j in range(N_DIR)], dtype=np.float64)
DIR8[np.abs(DIR8) < 1e-12] = 0.0

SELF_NAMES = ("energy", "reserve", "stamina", "health", "age_frac", "can_mate", "birth_wait", "speed", "air_height",
              "water_height_frac", "in_water", "in_shelter", "breath", "airborne",
              "burst_ready", "burst_phase")   # 덮치기: 준비 1 · 덮치는 중 남은 몫(+) · 지친 중 남은 몫(−)
BODY_NAMES = ("b_mass", "b_radius", "b_walk", "b_run", "b_swim", "b_swim_speed", "b_fly", "b_cruise_height", "b_wade",
              "b_slope", "b_turn", "b_sight", "b_fov", "b_diet_plant", "b_diet_water", "b_diet_meat", "b_kill", "b_burst")
DIR_FIELDS = ("free", "rise", "depth", "current", "cover", "food")
DIR_NAMES = tuple(f"{f}_{j}" for j in range(N_DIR) for f in DIR_FIELDS)
HERE_NAMES = ("food_here", "carcass_here", "to_surface", "to_bottom", "slope_here", "shelter_edge")
# 다른 동물 한 칸 12: 매체는 물·하늘 두 칸(둘 다 0 = 땅)
OTHER_SLOT_FIELDS = ("present", "x", "y", "approach", "speed", "size_ratio", "mass_ratio", "in_water", "in_air", "height_diff",
                     "same_kin", "facing_me")
OTHER_NAMES = tuple(f"o{i}_{f}" for i in range(N_OTHER) for f in OTHER_SLOT_FIELDS)
KIN_NAMES = ("kin_count", "kin_cx", "kin_cy", "kin_speed")
ENV_NAMES = ("light", "rain", "snow", "temperature", "water_trend", "noise_dir")
SPARE_NAMES = tuple(f"spare_{i}" for i in range(N_SPARE_OBS))

OBS_NAMES = SELF_NAMES + BODY_NAMES + DIR_NAMES + HERE_NAMES + OTHER_NAMES + KIN_NAMES + ENV_NAMES + SPARE_NAMES
OBS_DIM = len(OBS_NAMES)


def _span(names: tuple, start: int) -> tuple[int, int]:
    return start, start + len(names)


_o = 0
SLICES = {}
for _key, _names in (("self", SELF_NAMES), ("body", BODY_NAMES), ("dir", DIR_NAMES), ("here", HERE_NAMES),
                     ("other", OTHER_NAMES), ("kin", KIN_NAMES), ("env", ENV_NAMES), ("spare", SPARE_NAMES)):
    SLICES[_key] = _span(_names, _o)
    _o += len(_names)

# 정규화 기준(사양 7 절): lg(x) = log1p(x / ref) / log1p(max / ref) 를 0~1 로 자른다.
NORM = {
    "dist_m": {"ref": 2.0, "max": 60.0},          # 거리·갈 수 있는 거리
    "speed_mps": {"ref": 1.0, "max": 25.0},       # 속력·다가옴 크기
    "height_m": {"ref": 0.5, "max": 60.0},        # 땅 위 높이·높이 차 크기
    "depth_m": {"ref": 0.25, "max": 5.0},         # 물 깊이
    "current_mps": {"ref": 0.1, "max": 2.0},
    "food": {"ref": 1.0},                          # x / (x + ref) (R9 food_dir 꼴)
    "ratio_log2_max": 10.0,                         # 크기·질량 비: clip(log2(비) / 10, −1, 1)
    "kin_count_max": 12.0,
}

ACTION_NAMES = (("EAT",) + tuple(f"SLOW_{j * 45}" for j in range(N_DIR)) + tuple(f"FAST_{j * 45}" for j in range(N_DIR))
                + ("HIDE", "WATCH", "UP", "DOWN", "DIVE", "BURST", "SPARE_23"))
N_ACTIONS = len(ACTION_NAMES)
A_EAT, A_HIDE, A_WATCH, A_UP, A_DOWN, A_DIVE = 0, 17, 18, 19, 20, 21
A_SLOW0, A_FAST0 = 1, 9
A_BURST = 22                  # 덮치기: 머리 쪽으로 body.burst_mps 로 burst_s 동안 (방향 칸으로 꺾을 수 있음), 뒤에 지침
SPARE_ACTIONS = (23,)

NET = {"obs_dim": OBS_DIM, "hidden": [128, 128], "activation": "tanh", "n_actions": N_ACTIONS, "head": "masked_logits"}


def lg(x, ref: float, mx: float) -> np.ndarray:
    """0~1 로그 눈금 (사양 7 절)."""
    x = np.maximum(np.asarray(x, dtype=np.float64), 0.0)
    return np.clip(np.log1p(x / ref) / np.log1p(mx / ref), 0.0, 1.0)


def slg(x, ref: float, mx: float) -> np.ndarray:
    """부호 있는 로그 눈금 (−1~1)."""
    x = np.asarray(x, dtype=np.float64)
    return np.sign(x) * lg(np.abs(x), ref, mx)


def ratio(a, b) -> np.ndarray:
    """크기·질량 비 log2(a/b)/10 을 −1~1 로."""
    a = np.maximum(np.asarray(a, dtype=np.float64), 1e-9)
    b = np.maximum(np.asarray(b, dtype=np.float64), 1e-9)
    return np.clip(np.log2(a / b) / NORM["ratio_log2_max"], -1.0, 1.0)


def action_mask(medium: dict, burst: bool = False) -> np.ndarray:
    """종 카드 medium (+ 덮치기 능력) → 이 몸이 할 수 있는 행동 (bool, N_ACTIONS). 사양 8 절.
    덮치기가 지금 준비됐는지는 감각(burst_ready)으로 policy.mask_from_obs 가 막는다."""
    m = np.ones(N_ACTIONS, dtype=bool)
    fly = bool(medium.get("fly"))
    swim = bool(medium.get("swim"))
    if not (fly or swim):
        m[[A_UP, A_DOWN]] = False
    if not fly:
        m[A_DIVE] = False
    if not burst:
        m[A_BURST] = False
    m[list(SPARE_ACTIONS)] = False
    return m


def obs_mask(medium: dict, burst: bool = False) -> np.ndarray:
    """종 카드 medium → 이 몸이 느낄 수 있는 감각 칸 (bool, OBS_DIM). 못 느끼는 칸은 세계가 0 으로 둔다."""
    m = np.ones(OBS_DIM, dtype=bool)
    idx = {n: i for i, n in enumerate(OBS_NAMES)}
    if not medium.get("fly"):
        m[[idx["air_height"], idx["airborne"]]] = False
    if not medium.get("swim"):                         # 헤엄 못 하는 몸: 물속 높이·숨 가쁨 없음
        m[[idx["water_height_frac"], idx["breath"]]] = False
    if not burst:                                      # 덮치기 없는 몸
        m[[idx["burst_ready"], idx["burst_phase"]]] = False
    if medium.get("needs_water"):                      # 물고기: 물 밖 소리·비는 못 느낀다
        m[[idx["noise_dir"], idx["rain"], idx["snow"]]] = False
    lo, hi = SLICES["spare"]
    m[lo:hi] = False
    return m


def _canon(v):
    if isinstance(v, dict):
        return {str(k): _canon(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_canon(x) for x in v]
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    if v is None or isinstance(v, str):
        return v
    raise TypeError(f"cannot hash {v!r}")


def io_contract_dict() -> dict:
    return {"contract": CONTRACT, "sense": SENSE_VERSION, "action": ACTION_VERSION, "obs_names": list(OBS_NAMES),
            "norm": _canon(NORM), "actions": list(ACTION_NAMES), "dirs": "head rotated ccw by j*45deg",
            "step_s": STEP_S, "decision_steps": DECISION_STEPS, "day_steps": DAY_STEPS, "net": _canon(NET),
            "select": "sample softmax over unmasked (training and runtime, per-agent seed); argmax over unmasked = diagnostics only", "obs_dtype": "float32", "obs_clip": [-1.0, 1.0]}


def io_hash() -> str:
    s = json.dumps(io_contract_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "0x" + hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


assert OBS_DIM == 206, OBS_DIM
assert len(OTHER_SLOT_FIELDS) == 12
assert N_ACTIONS == 24
