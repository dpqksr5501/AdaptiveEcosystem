"""V2 학습 환경 World — v1 `env/world.py` 에서 출발한 사본.

v1 파일은 언리얼에 연결된 계약(관측 7·행동 4)의 원본이라 한 줄도 바꾸지 않는다
(`Docs/RL_Policy/RL_V2_PLAN.md` 결정 3). V2 기능(속도·경계·기억·대담함·환경 상호작용)은
이 사본에 **스위치로** 붙인다. 스위치를 모두 끈 이 World 는 같은 시드에서 v1 World 와
결과가 완전히 같아야 한다 — `tests/test_env_v2.py` 가 고정한다.

기능 스위치는 버전 설정(`configs/v2*.yaml`)의 `features:` 블록이다(`env_v2/features.py`). 새 기능이 뽑는
난수는 기능마다 따로 둔 스트림 `self.feature_rng(name)` 에서만 뽑는다. v1 난수 호출 순서가 바뀌면
같은 시드의 세계가 조용히 달라지고, 기능끼리 스트림을 나눠 쓰면 기능 하나를 켜고 끌 때 다른 기능의
세계가 바뀌기 때문이다 (계획서 4.4, 4.8).

구현한 기능 (꺼진 기능의 코드 경로는 v1 과 같다):
- food_v (v2.0b, 계획서 4.9.1): 셀마다 식생 용량 V. 섭식이 V 를 깎고 재생은 cap0 대신 V 를 향한다.
  V 는 반감기 h 로 cap0 에 천천히 돌아온다. 스텝 순서는 `_food_v_step`, 통계는 `food_stats`·`food_cells`.
- speed (v2.1, 계획서 4.3·4.4·4.5): 행동이 5개가 된다(idx 4 = speed). 문턱으로 정지·걷기·뛰기를 정하고,
  상태가 v1 조향 속도의 크기, 섭식 배수, 대사를 정한다. 에너지 보상은 계수 하나로 순변화(#4)로 바꾼다.
  난수를 쓰지 않는다. 스텝 순서는 `_gait_step`, 통계는 `gait_stats`(v1 `stats()` 10열 밖).

행동 수는 설정에서 읽는다: `action_names(cfg)`·`action_dim(cfg)`, 세계마다 `World.act_names`·`World.act_dim`.
모듈 상수 `ACT_DIM`(4)은 v1 행동 수다(기능을 모두 끈 세계와 food_v 세계의 행동 수).
"""

from __future__ import annotations

import math

import numpy as np

from .features import Features, _check_name, _check_part, feature_stream, features_of
from .steering import EPS, clamp_magnitude, normalize, steer

# 관측 열 인덱스 (§3.1). 이 순서가 언리얼 FEcoObservationFragment와 일치해야 한다.
OBS_FOOD_DENSITY = 0
OBS_PREDATOR_COUNT = 1
OBS_PREDATOR_DISTANCE = 2
OBS_KIN_COUNT = 3
OBS_ENERGY = 4
OBS_RECENT_PREDATION = 5
OBS_COVER_DISTANCE = 6
OBS_DIM = 7

ACT_DIM = 4  # forage, cohesion, flee_dist, cover (§3.2). v1 행동 수 — 세계의 실제 행동 수는 World.act_dim
ACT_NAMES_V1 = ("forage", "cohesion", "flee_dist", "cover")
ACT_SPEED = 4  # speed 를 켠 세계의 보행 행동 열 (계획서 4.3 idx 4)

# 보행 상태 번호 (계획서 4.4). replay_v2.GAIT_* 와 같다.
GAIT_STOP, GAIT_WALK, GAIT_RUN = 0, 1, 2

# food_stats 의 "하한에 붙은 셀": V/cap0 ≤ floor + 이 값. 휴식 회복이 훼손 뒤에 오므로 하한까지 깎인 셀도
# 스텝 끝에는 ρ·(1 − floor)만큼 위에 있다(반감기 300 에서 0.0021). 통계 정의이고 동역학 계수가 아니다.
FOOD_V_FLOOR_TOL = 0.01

# gait_stats 의 지표 정의 (계획서 6.2, 통계 정의이고 동역학 계수가 아니다).
# B1 거리 구간 [0, 0.25), [0.25, 0.5), [0.5, 1] (× see_r). "포식자 가까움" = 보임 & d_pred < B1_EDGES[1]·see_r
# (앞 두 구간, 계획서 6.2 의 d_pred < 0.5·see_r 이고 Gate E1 구간과 같다).
B1_EDGES = (0.25, 0.5)
# B2·hungry_frac 의 "배고픔" = 결정 때(스텝 전) energy < HUNGRY·max_energy (v1 react_hunger 와 같은 문턱).
HUNGRY = 0.5
# gait_stats 누적 히스토그램 모양: [실제 보행, 명령 보행, 포식자 거리 구간(안 보임 + B1 3구간), 배부름]
GAIT_HIST_SHAPE = (3, 3, 1 + len(B1_EDGES) + 1, 2)
# gait_stats() 열 순서. env_v2/rollout.py 가 speed 를 켠 세계의 행에 붙인다.
GAIT_STAT_COLUMNS = (
    "stop_frac", "walk_frac", "run_frac", "stall_frac",
    "stop_frac_cmd", "walk_frac_cmd", "run_frac_cmd",
    "hungry_frac", "starve_rate", "starve_share",
    "b1", "p_run_unseen", "p_run_d025", "p_run_d050", "p_run_d100",
    "b2", "p_stop_hungry", "p_stop_full",
    "b8", "b8_cmd", "intake_per_step", "drain_per_step",
)


def action_names(cfg) -> tuple[str, ...]:
    """설정(또는 `Features`)의 세계가 받는 행동 이름. 순서 = 행동 열 번호 (계획서 4.3).

    v1 4개 뒤에 켠 기능의 행동이 붙는다. 지금은 speed(v2.1) 하나다. 한번 정한 열 번호는 바꾸지 않는다.
    """
    f = cfg if isinstance(cfg, Features) else features_of(cfg)
    names = ACT_NAMES_V1
    if f.enabled("speed"):
        names = names + ("speed",)
    return names


def action_dim(cfg) -> int:
    """설정의 세계가 받는 행동 수. v1·v2.0·v2.0b 4, speed 를 켜면 5."""
    return len(action_names(cfg))


def _speed_params(p: dict) -> dict:
    """speed 계수(yaml 블록, 키는 `features.PARAM_KEYS`)의 값 범위를 검사하고 상태별 표를 만든다. 기본값은 없다.

    - thresholds [t_walk, t_run]: 0 ≤ t_walk ≤ t_run ≤ 1. a < t_walk 정지, a < t_run 걷기, 그 밖은 뛰기
    - gait_speed [0, s_walk, s_run] (× herb_speed): 정지는 0, 0 < s_walk ≤ s_run
    - gait_eat [e_stop, e_walk, e_run] ≥ 0: `_eat` 의 want 에 곱하는 섭식 배수
    - c_rest, c_move ≥ 0: drain_mult[g] = c_rest + c_move·gait_speed[g]² (스텝 대사 = energy_drain × drain_mult)
    - net_energy_reward: true 면 에너지 보상이 순변화 e_new − e_prev, false 면 v1 획득량 (#4)
    """
    def num(key, x):
        if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) \
                or not math.isfinite(x):
            raise ValueError(f"features.speed.{key} 는 유한한 숫자여야 한다. 받은 값: {x!r}")
        return float(x)

    def vec(key, n):
        x = p[key]
        if not isinstance(x, (list, tuple)) or len(x) != n:
            raise ValueError(f"features.speed.{key} 는 값 {n}개 목록이어야 한다. 받은 값: {x!r}")
        return tuple(num(key, v) for v in x)

    t_walk, t_run = vec("thresholds", 2)
    speed = vec("gait_speed", 3)
    eat = vec("gait_eat", 3)
    c_rest, c_move = num("c_rest", p["c_rest"]), num("c_move", p["c_move"])
    net = p["net_energy_reward"]
    if not 0.0 <= t_walk <= t_run <= 1.0:
        raise ValueError(f"features.speed.thresholds 는 0 ≤ 걷기 ≤ 뛰기 ≤ 1 이어야 한다. 받은 값: {[t_walk, t_run]}")
    if speed[0] != 0.0 or not 0.0 < speed[1] <= speed[2]:
        raise ValueError(f"features.speed.gait_speed 는 [0, 걷기, 뛰기], 0 < 걷기 ≤ 뛰기 여야 한다(정지는 속력 0). "
                         f"받은 값: {list(speed)}")
    if min(eat) < 0.0:
        raise ValueError(f"features.speed.gait_eat 는 0 이상이어야 한다. 받은 값: {list(eat)}")
    if c_rest < 0.0 or c_move < 0.0:
        raise ValueError(f"features.speed.c_rest·c_move 는 0 이상이어야 한다. 받은 값: {c_rest}, {c_move}")
    if not isinstance(net, bool):
        raise ValueError(f"features.speed.net_energy_reward 는 true/false 여야 한다. 받은 값: {net!r}")
    sp = np.asarray(speed, dtype=np.float64)
    return dict(thresholds=(t_walk, t_run), speed=sp, eat=np.asarray(eat, dtype=np.float64),
                c_rest=c_rest, c_move=c_move, drain_mult=c_rest + c_move * sp * sp, net_energy_reward=net)


def _food_v_params(p: dict) -> dict:
    """food_v 계수(yaml 블록, 키는 `features.PARAM_KEYS`)의 값 범위를 검사한다. 기본값은 없다.

    alpha ≥ 0, 0 ≤ floor ≤ 1, 반감기는 하나 이상의 양수(스텝), floor ≤ init_frac[0] ≤ init_frac[1] ≤ 1.
    alpha = 0 이면 훼손이 없어 V 가 cap0 로 돌아가기만 한다.
    """
    def num(key, x):
        if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) \
                or not math.isfinite(x):
            raise ValueError(f"features.food_v.{key} 는 유한한 숫자여야 한다. 받은 값: {x!r}")
        return float(x)

    alpha, floor = num("alpha", p["alpha"]), num("floor", p["floor"])
    hl, fr = p["recovery_half_lives"], p["init_frac"]
    if not isinstance(hl, (list, tuple)) or not hl:
        raise ValueError(f"features.food_v.recovery_half_lives 는 반감기(스텝) 목록이어야 한다. 받은 값: {hl!r}")
    if not isinstance(fr, (list, tuple)) or len(fr) != 2:
        raise ValueError(f"features.food_v.init_frac 는 [하, 상] 두 값이어야 한다. 받은 값: {fr!r}")
    half_lives = tuple(num("recovery_half_lives", h) for h in hl)
    lo, hi = (num("init_frac", x) for x in fr)
    if alpha < 0.0:
        raise ValueError(f"features.food_v.alpha 는 0 이상이어야 한다. 받은 값: {alpha}")
    if not 0.0 <= floor <= 1.0:
        raise ValueError(f"features.food_v.floor 는 [0, 1] 의 cap0 비율이어야 한다. 받은 값: {floor}")
    if min(half_lives) <= 0.0:
        raise ValueError(f"features.food_v.recovery_half_lives 는 양수여야 한다. 받은 값: {list(half_lives)}")
    if not floor <= lo <= hi <= 1.0:
        raise ValueError(f"features.food_v.init_frac 는 floor({floor}) ≤ 하 ≤ 상 ≤ 1 이어야 한다. 받은 값: {[lo, hi]}")
    return dict(alpha=alpha, floor=floor, half_lives=half_lives, init_frac=(lo, hi))


class World:
    """N=128 슬롯 고정, 죽으면 그 슬롯에 리스폰 (§4.3).

    `step()` 은 항상 [0,1] 행동을 받는다 (§1.3). (-3,3) 출력의 sigmoid 변환은
    VecEnv 래퍼(§6.2)의 책임이지 이 클래스의 책임이 아니다.
    """

    def __init__(self, cfg, seeds=None, meta_seed: int = 0):
        self.cfg = cfg
        if seeds is None:
            lo, hi = cfg.train_seeds
            seeds = range(lo, hi)
        self.seeds = np.asarray(list(seeds), dtype=np.int64)
        self.meta = np.random.default_rng(meta_seed)
        self.N = int(cfg.N)
        self.features: Features = features_of(cfg)
        # 켠 기능의 계수(yaml 원본). 꺼진 기능은 None 이고 그 기능의 코드 경로를 타지 않는다.
        self._fv = _food_v_params(self.features.params("food_v")) if self.features.enabled("food_v") else None
        self._sp = _speed_params(self.features.params("speed")) if self.features.enabled("speed") else None
        self.act_names: tuple[str, ...] = action_names(self.features)
        self.act_dim = len(self.act_names)
        self.reset()

    # ------------------------------------------------------------------ #
    # reset / 세계 생성
    # ------------------------------------------------------------------ #

    def reset(self) -> np.ndarray:
        """§4.4 — 시드 하나가 무작위화 파라미터와 세계 배치를 모두 결정한다 (§3.5)."""
        cfg = self.cfg
        seed = int(self.meta.choice(self.seeds))
        r = self.rng = np.random.default_rng(seed)
        self.seed = seed
        # 기능별 난수 스트림은 처음 쓸 때 만든다(feature_rng). 세계를 새로 뽑으면 처음부터 다시 시작한다.
        self._feature_rngs: dict[tuple[str, int], np.random.Generator] = {}

        rd = cfg.rand
        self.size = float(r.uniform(*rd["world_size"]))
        self.M = int(r.integers(rd["predator_count"][0], rd["predator_count"][1] + 1))
        self.pred_speed_mult = float(r.uniform(*rd["pred_speed_mult"]))
        self.ranged_frac = float(r.uniform(*rd["ranged_frac"]))
        self.cover_frac_target = float(r.uniform(*rd["cover_frac"]))
        self.food_regen_mult = float(r.uniform(*rd["food_regen_mult"]))

        self._build_world()
        if self._fv is not None:
            self._food_v_reset()
        if self._sp is not None:
            # v2.1 스텝 뒤 훅 (replay_v2): 실제 보행, 명령 보행, 적용 속도. 첫 스텝 전에는 정지·0 으로 둔다.
            self.gait = np.zeros(self.N, dtype=np.int8)
            self.gait_cmd = np.zeros(self.N, dtype=np.int8)
            self.vel = np.zeros((self.N, 2))
        self._reset_stats()
        self._g = self._geometry()
        self._obs = self._obs_from(self._g)
        return self._obs

    def feature_rng(self, name: str, part: int = 0) -> np.random.Generator:
        """기능 `name` 의 난수 스트림. 이 세계의 시드에서 나오고 다른 기능·v1 스트림과 독립이다.

        같은 기능에 나중에 난수를 더할 때는 새 `part` 를 쓴다 (`env_v2/features.py` 규칙 3).
        """
        _check_name(name)
        _check_part(part)                   # 캐시를 찾기 전에 검사한다(True·1.0 은 키 1 과 같게 해시된다)
        key = (name, int(part))
        g = self._feature_rngs.get(key)
        if g is None:
            g = self._feature_rngs[key] = feature_stream(self.seed, name, part)
        return g

    def _build_world(self) -> None:
        cfg, r = self.cfg, self.rng
        N, size = self.N, self.size

        # --- 먹이 격자 (§4.2) ---
        # 셀마다 독립 균등난수를 깔면 먹이가 온 맵에 고르게 깔려서 따라갈 기울기가
        # 백색잡음이 된다 (측정: forage가 아무 이득이 없었다). 저주파 노이즈를
        # 문턱값으로 잘라 **패치**를 만들고, 재생은 그 용량(capacity)을 향해 간다.
        # 그래야 고갈된 패치가 비어 있는 채로 남고 먹이 탐색이 실제 문제가 된다.
        self.gw = int(np.ceil(size / cfg.food_cell))
        m = self._smooth(r.random((self.gw, self.gw)), int(cfg.food_patch_blur))
        m = (m - m.min()) / max(m.max() - m.min(), EPS)
        t = float(cfg.food_patch_threshold)
        self.food_cap = np.clip((m - t) / (1.0 - t), 0.0, 1.0)
        self.food = self.food_cap.copy()
        cc = (np.arange(self.gw) + 0.5) * cfg.food_cell      # 셀 중심 좌표
        self._cell_x, self._cell_y = np.meshgrid(cc, cc)     # 둘 다 (gw,gw)

        # --- 은신처 (§4.2): 셀 마스크 면적이 목표 비율에 닿을 때까지 원을 놓는다 ---
        centers, radii = [], []
        mask = np.zeros((self.gw, self.gw), dtype=bool)
        for _ in range(int(cfg.cover_max_count)):
            if mask.mean() >= self.cover_frac_target:
                break
            c = r.uniform(0.0, size, 2)
            rad = float(r.uniform(cfg.cover_r_min, cfg.cover_r_max))
            centers.append(c)
            radii.append(rad)
            mask |= (self._cell_x - c[0]) ** 2 + (self._cell_y - c[1]) ** 2 <= rad * rad
        self.cov_c = np.asarray(centers, dtype=np.float64).reshape(-1, 2)
        self.cov_r = np.asarray(radii, dtype=np.float64).reshape(-1)
        self.cover_cell = mask
        self.cover_frac_actual = float(mask.mean())

        # 은신처 셀은 재생 속도 0.3배 (§4.2)
        self.regen_field = cfg.food_regen_base * self.food_regen_mult * np.where(
            self.cover_cell, cfg.food_cover_regen_mult, 1.0
        )

        # --- 초식 (§4.3) ---
        self.pos = r.uniform(0.0, size, (N, 2))
        ang = r.uniform(0.0, 2 * np.pi, N)
        self.head = np.stack([np.cos(ang), np.sin(ang)], 1)
        self.energy = np.full(N, float(cfg.init_energy))
        self.repro_cd = np.zeros(N, dtype=np.int32)

        # --- 포식자 (§4.2) ---
        M = self.M
        self.pred_pos = r.uniform(0.0, size, (M, 2))
        pang = r.uniform(0.0, 2 * np.pi, M)
        self.pred_head = np.stack([np.cos(pang), np.sin(pang)], 1)
        self.pred_ranged = r.random(M) < self.ranged_frac
        base = cfg.herb_speed * self.pred_speed_mult
        self.pred_speed = np.where(self.pred_ranged, base * cfg.pred_ranged_speed_mult, base)
        self.pred_catch_r = np.where(
            self.pred_ranged, cfg.pred_ranged_catch_r, cfg.pred_melee_catch_r
        )
        # 포식 후 식사 쿨다운. §4.4가 포식자 속도를 herb_speed의 1.0~1.4배로 고정하므로
        # 한번 붙잡히면 도주로는 벗어날 수 없다. 쿨다운이 포식 압력의 상한을 정한다.
        self.pred_cd = np.zeros(M, dtype=np.int32)

        # --- 지역 피식 EMA (§3.1) ---
        self.pred_ema = 0.0
        self.t = 0

    def _left_half(self) -> np.ndarray:
        """셀 중심이 맵 왼쪽 절반(x < size/2)인 셀 (gw,gw). v2.3 지역 전까지 지역 대용이다 (계획서 0-6)."""
        return self._cell_x < 0.5 * self.size

    def _food_v_reset(self) -> None:
        """v2.0b 세계 생성 (계획서 4.9.1). v1 세계(`_build_world`)를 다 만든 뒤 부른다.

        food_v 스트림 part 0 에서 난수 정확히 3개를 이 순서로 뽑는다. 목록 길이와 상관없이 소비가 같다
        (`integers(1)` 은 난수를 소비하지 않으므로 고르기에 쓰지 않는다).
          1) u ~ U[0,1) → 회복 반감기 h = recovery_half_lives[floor(u·n)], ρ = 1 − 2^(−1/h)
          2) 왼쪽 절반 V 초기 비율 ~ U[init_frac]   3) 오른쪽 절반 ~ U[init_frac]
        V = cap0 × (그 셀이 속한 절반의 비율), F = min(v1 초기값 cap0, V). cap0 = 0 셀은 F = V = 0 이다.
        """
        fv, g = self._fv, self.feature_rng("food_v", 0)
        hl = fv["half_lives"]
        h = hl[min(int(g.random() * len(hl)), len(hl) - 1)]
        frac = g.uniform(fv["init_frac"][0], fv["init_frac"][1], 2)       # [왼쪽, 오른쪽]
        self.food_v_half_life = h
        self.food_v_rho = 1.0 - 2.0 ** (-1.0 / h)
        self.food_v_init = (float(frac[0]), float(frac[1]))
        self.food_v = self.food_cap * np.where(self._left_half(), frac[0], frac[1])
        self._fv_floor = fv["floor"] * self.food_cap
        np.minimum(self.food, self.food_v, out=self.food)
        # 기록 (food_stats·food_cells): reset 뒤 셀별 누적 섭취, 마지막으로 뜯긴 스텝(self.t, 없으면 −1)
        self._fv_eaten = np.zeros_like(self.food_cap)
        self._fv_last_eat = np.full(self.food_cap.shape, -1, dtype=np.int64)

    # ------------------------------------------------------------------ #
    # 기하 (관측과 조향이 공유한다)
    # ------------------------------------------------------------------ #

    def _smooth(self, arr: np.ndarray, br: int) -> np.ndarray:
        """반경 br 셀 박스 평균. SAT를 새로 만든다 (reset 시 1회용)."""
        g = self.gw
        sat = np.zeros((g + 1, g + 1))
        np.cumsum(np.cumsum(arr, 0), 1, out=sat[1:, 1:])
        return self._box_mean(sat, max(1, br))

    def _box_mean(self, sat: np.ndarray, br: int) -> np.ndarray:
        """SAT에서 반경 br 셀 정사각 평균. 경계는 잘린 창의 실제 면적으로 나눈다."""
        g = self.gw
        i = np.arange(g)
        r0, r1 = np.clip(i - br, 0, g), np.clip(i + br + 1, 0, g)
        c0, c1 = r0, r1  # 정방 격자라 행/열 인덱스가 같다
        box = (
            sat[np.ix_(r1, c1)] - sat[np.ix_(r0, c1)] - sat[np.ix_(r1, c0)] + sat[np.ix_(r0, c0)]
        )
        return box / ((r1 - r0)[:, None] * (c1 - c0)[None, :])

    def _food_fields(self) -> None:
        """먹이 밀도(관측용)와 기울기(조향용)를 격자 전체에 대해 한 번 계산한다.

        두 필드의 블러 반경이 **다르다**. 일부러 그렇게 뒀다:

        - `food_blur` (관측 idx0): 반경 `see_r`. §9.4의
          `IWorldFoodProvider::GetFoodDensity(Location, Radius)` 와 맞추기 위한 반경 평균이다
          (각도 제한 없음 — 언리얼 인터페이스가 반경만 받는다).
        - `_food_g*` (조향 `food_grad`): 반경 `food_grad_blur` 셀. see_r 블러(11×11셀)에서
          기울기를 뽑으면 한 셀을 먹어치워도 값이 0.8%밖에 안 변해서, 개체 전원이 초기
          고밀도 지점으로 몰린 뒤 같은 셀을 두고 경쟁한다. 측정 결과 `forage=1`이
          `forage=0`보다 **덜 먹었다**. 좁은 반경을 쓰면 국소 고갈이 기울기에 바로 잡혀
          비어버린 주변을 벗어나는 방향을 가리킨다.

        `food_grad` 는 관측이 아니라 §3.3의 기하 입력이므로 이 분리가 §3 계약을 건드리지
        않는다. 언리얼도 `GetFoodDensity` 와 `FoodGrad` 를 별도로 제공한다 (§9.4/§9.5).
        """
        cfg = self.cfg
        g = self.gw
        sat = np.zeros((g + 1, g + 1))
        np.cumsum(np.cumsum(self.food, 0), 1, out=sat[1:, 1:])
        self.food_blur = self._box_mean(sat, max(1, int(round(cfg.see_r / cfg.food_cell))))
        gy, gx = np.gradient(self._box_mean(sat, max(1, int(cfg.food_grad_blur))))
        self._food_gx, self._food_gy = gx, gy

    def _cover_edge(self, p: np.ndarray):
        """은신처 원까지의 (dx, dy, 가장자리까지 거리) — 전부 (n,K)."""
        dx = self.cov_c[:, 0][None, :] - p[:, 0:1]
        dy = self.cov_c[:, 1][None, :] - p[:, 1:2]
        return dx, dy, np.sqrt(dx * dx + dy * dy) - self.cov_r[None, :]

    def _in_cover(self, p: np.ndarray) -> np.ndarray:
        """위치 `p` (n,2)가 은신처 원 안인가. 관측과 포식자 판정이 같은 정의를 쓴다."""
        if not len(self.cov_r):
            return np.zeros(len(p), dtype=bool)
        return self._cover_edge(p)[2].min(1) <= 0.0

    def _cell_index(self, p: np.ndarray):
        """월드 좌표 → 격자 인덱스 (ix=열, iy=행)."""
        k = 1.0 / self.cfg.food_cell
        ix = np.clip((p[:, 0] * k).astype(np.int32), 0, self.gw - 1)
        iy = np.clip((p[:, 1] * k).astype(np.int32), 0, self.gw - 1)
        return ix, iy

    def _geometry(self, idx: np.ndarray | None = None, out: dict | None = None) -> dict:
        """행 `idx` (None이면 전체)의 기하 정보를 계산한다.

        `out` 을 주면 그 딕셔너리의 해당 행만 덮어쓴다 (§4.5 `_observe_subset` 경로).
        """
        cfg = self.cfg
        if idx is None:
            idx = np.arange(self.N)
            self._food_fields()
        P = self.pos[idx]
        Hd = self.head[idx]
        n = len(idx)
        ar = np.arange(n)
        hx, hy = Hd[:, 0:1], Hd[:, 1:2]

        # 쌍별 계산은 전부 (n, ·) 2D로 둔다. (n,N,2) 3D 임시배열을 만들면 스텝의 75%를
        # 여기서 쓴다 (측정). 합산은 행렬곱으로 내려보낸다.

        # --- 동족: 시야(거리 + 각도) 내, 자기 제외 (§3.1 idx3) ---
        dx = self.pos[:, 0][None, :] - P[:, 0:1]
        dy = self.pos[:, 1][None, :] - P[:, 1:2]
        dist = np.sqrt(dx * dx + dy * dy)
        invd = 1.0 / np.maximum(dist, EPS)
        kin_vis = (dist <= cfg.see_r) & ((dx * hx + dy * hy) * invd >= cfg.fov_cos)
        kin_vis[ar, idx] = False
        kin_f = kin_vis.astype(np.float64)
        kin_count = kin_f.sum(1)
        centroid = (kin_f @ self.pos) / np.maximum(kin_count, 1.0)[:, None]
        to_centroid = np.where(kin_count[:, None] > 0, normalize(centroid - P), 0.0)

        # --- separation: 반경 내 이웃마다 (1 - d/R) * 멀어지는 단위벡터, 합 후 크기 1로 clamp ---
        # sum_j w_ij * (pos_j - P_i)/d_ij  =  (c @ pos) - rowsum(c) * P,  c = w/d
        wgt = np.clip(1.0 - dist / cfg.sep_radius, 0.0, None)
        wgt[ar, idx] = 0.0
        c = wgt * invd
        separation = clamp_magnitude(-((c @ self.pos) - c.sum(1)[:, None] * P), 1.0)

        # --- 포식자 (§3.1 idx1, idx2) ---
        if self.M > 0:
            ex = self.pred_pos[:, 0][None, :] - P[:, 0:1]
            ey = self.pred_pos[:, 1][None, :] - P[:, 1:2]
            pd = np.sqrt(ex * ex + ey * ey)
            pinv = 1.0 / np.maximum(pd, EPS)
            pvis = (pd <= cfg.see_r) & ((ex * hx + ey * hy) * pinv >= cfg.fov_cos)
            pred_count = pvis.sum(1)
            masked = np.where(pvis, pd, np.inf)
            j = masked.argmin(1)
            d_pred_min = masked[ar, j]
            seen = np.isfinite(d_pred_min)[:, None]
            away = np.where(
                seen, -np.stack([ex[ar, j], ey[ar, j]], 1) * pinv[ar, j][:, None], 0.0
            )
        else:
            pred_count = np.zeros(n, dtype=np.int64)
            d_pred_min = np.full(n, np.inf)
            away = np.zeros((n, 2))

        # --- 은신처 (§3.1 idx6) ---
        if len(self.cov_r):
            cx, cy, edge = self._cover_edge(P)
            k = edge.argmin(1)
            e = edge[ar, k]
            in_cover = e <= 0.0
            cover_dist = np.clip(np.maximum(e, 0.0) / cfg.obs_cover_norm, 0.0, 1.0)
            to_cover = np.where(
                in_cover[:, None], 0.0, normalize(np.stack([cx[ar, k], cy[ar, k]], 1))
            )
        else:
            in_cover = np.zeros(n, dtype=bool)
            cover_dist = np.ones(n)
            to_cover = np.zeros((n, 2))

        # --- 먹이 (§3.1 idx0) ---
        ix, iy = self._cell_index(P)
        food_density = self.food_blur[iy, ix]
        food_grad = normalize(np.stack([self._food_gx[iy, ix], self._food_gy[iy, ix]], 1))

        vals = dict(
            food_grad=food_grad,
            food_density=food_density,
            to_centroid=to_centroid,
            kin_count=kin_count,
            separation=separation,
            d_pred_min=d_pred_min,
            pred_count=pred_count,
            away_from_pred=away,
            to_cover=to_cover,
            cover_dist=cover_dist,
            in_cover=in_cover,
        )
        if out is None:
            return vals
        for key, v in vals.items():
            out[key][idx] = v
        return out

    # ------------------------------------------------------------------ #
    # 관측 (§3.1)
    # ------------------------------------------------------------------ #

    def _obs_from(self, g: dict, idx: np.ndarray | None = None) -> np.ndarray:
        """§3.1 — 7개, float32, [0,1]. 정규화 상수는 전부 고정값이다 (§1.2)."""
        cfg = self.cfg
        sl = slice(None) if idx is None else idx
        n = self.N if idx is None else len(idx)
        o = np.empty((n, OBS_DIM), dtype=np.float32)
        o[:, OBS_FOOD_DENSITY] = np.clip(g["food_density"][sl], 0.0, 1.0)
        o[:, OBS_PREDATOR_COUNT] = np.clip(g["pred_count"][sl] / cfg.obs_pred_count_norm, 0.0, 1.0)
        o[:, OBS_PREDATOR_DISTANCE] = np.clip(g["d_pred_min"][sl] / cfg.see_r, 0.0, 1.0)
        o[:, OBS_KIN_COUNT] = np.clip(g["kin_count"][sl] / cfg.obs_kin_count_norm, 0.0, 1.0)
        o[:, OBS_ENERGY] = np.clip(self.energy[sl] / cfg.max_energy, 0.0, 1.0)
        o[:, OBS_RECENT_PREDATION] = min(self.pred_ema, 1.0)
        o[:, OBS_COVER_DISTANCE] = g["cover_dist"][sl]
        return o

    def _observe_subset(self, idx: np.ndarray) -> np.ndarray:
        """§4.5 — 리스폰된 슬롯만 재계산한다."""
        self._geometry(idx, out=self._g)
        return self._obs_from(self._g, idx)

    def observe(self) -> np.ndarray:
        return self._obs

    # ------------------------------------------------------------------ #
    # step (§4.5)
    # ------------------------------------------------------------------ #

    def _check_action(self, a: np.ndarray) -> None:
        """행동 배열 모양 (N, act_dim). 행동 4개(v1)를 speed 를 켠 세계에 넣으면 보행 열이 없어 여기서 멈춘다."""
        if a.ndim != 2 or a.shape != (self.N, self.act_dim):
            raise ValueError(
                f"행동은 ({self.N}, {self.act_dim}) [{', '.join(self.act_names)}] 이어야 한다. 받은 모양: {a.shape}"
                + (". v1 정책(Utility·random 4개)은 speed 를 켠 세계에 그대로 쓸 수 없다" if self.act_dim != ACT_DIM
                   and a.ndim == 2 and a.shape[1] == ACT_DIM else ""))

    def step(self, a: np.ndarray):
        """`a`: (N, act_dim) in [0,1] (§1.3). act_dim 은 v1 4, speed 를 켜면 5. 반환: obs, reward, done, terminal_obs.

        speed(v2.1)를 켠 세계의 스텝 순서는 `_gait_step` docstring 에 적었다. 끈 세계는 v1 과 같은 줄을 탄다.
        """
        cfg = self.cfg
        a = np.asarray(a, dtype=np.float64)
        self._check_action(a)
        rew = np.full(self.N, cfg.rew_alive)

        # 1) 초식 이동 — §3.3 조향 수식. 벽 경계(§4.2), 토러스 없음.
        v = steer(self._g, a, cfg)
        if self._sp is not None:
            v = self._gait_step(v, a[:, ACT_SPEED])     # v2.1: 보행 상태가 크기만 바꾼다. 방향은 v1 조향 그대로
        self.pos = np.clip(self.pos + v, 0.0, self.size)
        moving = np.linalg.norm(v, axis=1) > EPS
        self.head = np.where(moving[:, None], normalize(v), self.head)

        # 2) 포식자 이동 + 포획 판정
        caught = self._step_predators()

        # 3) 섭식 · 대사 (§3.4 "에너지 획득 +1.0 × 획득량")
        if self._sp is None:
            e_drained = self.energy - cfg.energy_drain
            gain = self._eat(e_drained)
        else:                       # v2.1: 대사와 섭식 배수가 이번 스텝의 실제 보행을 따른다
            drain = cfg.energy_drain * self._sp["drain_mult"][self.gait]
            e_drained = self.energy - drain
            gain = self._eat(e_drained, self._sp["eat"][self.gait])
        e_new = np.minimum(e_drained + gain * cfg.food_energy_per_unit, cfg.max_energy)
        if self._sp is not None and self._sp["net_energy_reward"]:
            # #4 순변화 e_new − e_prev. 번식 리셋(아래 4)과 리스폰(8)은 이 뒤라 들어가지 않는다
            rew += cfg.rew_energy * (e_new - self.energy)
        else:
            rew += cfg.rew_energy * (e_new - e_drained)
        e_prev = self.energy
        self.energy = e_new

        # 4) 번식 — energy > threshold AND repro_cd == 0 (§3.4)
        self.repro_cd = np.maximum(self.repro_cd - 1, 0)
        repro = (self.energy > cfg.repro_threshold) & (self.repro_cd == 0)
        if repro.any():
            rew += cfg.rew_repro * repro
            self.energy = np.where(repro, cfg.init_energy, self.energy)
            self.repro_cd = np.where(repro, int(cfg.repro_cd), self.repro_cd)

        # 5) 사망: 피식 또는 아사
        starved = self.energy <= 0.0
        done = caught | starved
        rew += cfg.rew_death * done

        # 6) 지역 피식 EMA (§3.1). §9.6과 맞춰 피식 사망만 센다.
        n_pred_deaths = int(caught.sum())
        self.pred_ema = (
            cfg.predation_ema_decay * self.pred_ema
            + (1.0 - cfg.predation_ema_decay) * (n_pred_deaths / self.N) * cfg.predation_ema_gain
        )

        # 7) 먹이 재생 (§4.2). 셀 용량(패치 구조)을 향해 자란다.
        #    은신처 셀은 이미 0.3배가 반영된 regen_field.
        if self._fv is None:
            self.food += self.regen_field * (self.food_cap - self.food)
            np.clip(self.food, 0.0, self.food_cap, out=self.food)
        else:
            self._food_v_step()        # v2.0b: 훼손 → 재생(목표·상한 V) → 휴식 회복

        self.t += 1
        self._accumulate(a, rew, repro, caught, starved, done)
        if self._sp is not None:      # 스텝 전 기하(self._g)·결정 때 에너지로 보행 지표를 센다
            self._gait_accumulate(e_prev, e_new - e_drained, drain)

        # 8) 관측 — 스텝당 observe() 한 번 (§4.5)
        g = self._geometry()
        obs = self._obs_from(g)
        self._g, self._obs = g, obs
        terminal_obs = obs.copy()
        if done.any():
            dead = np.flatnonzero(done)
            self._respawn(dead)
            obs[dead] = self._observe_subset(dead)
            if self._sp is not None:
                self._gait_prev[:, dead] = -1     # 새 개체: 보행 전환(B8)을 이전 개체와 잇지 않는다

        return obs, rew, done, terminal_obs

    def _gait_step(self, v: np.ndarray, a_speed: np.ndarray) -> np.ndarray:
        """v2.1 보행 (계획서 4.3·4.4). `step` 1) 에서 v1 조향 속도 `v`(크기 herb_speed 또는 0)의 크기만 바꾼다.

        한 스텝 순서 — C++ 로 옮길 때 이 순서를 지킨다. 상태가 없다(이전 스텝의 보행을 읽지 않는다):
          1a) 명령 보행 cmd = [a ≥ t_walk] + [a ≥ t_run] (0 정지, 1 걷기, 2 뛰기). a 는 sigmoid 뒤 [0,1] 값이고
              문턱은 고정값이다(최소 유지 시간 K 없음, #3)
          1b) 실제 보행 g = cmd. 단 조향 합의 방향이 없으면(|v| ≤ EPS, v1 의 '안 움직임' 판정과 같다) g = 정지.
              갈 방향이 없는 '걷기'는 제자리에 서 있는 것이므로 섭식·대사도 정지로 친다
          1c) v ← v × gait_speed[g]. 조향 방향 계산(steering.py)은 그대로다. 뛰기 1.0 이면 v1 속도와 비트 단위로 같다
          1d) (step) pos ← clip(pos + v, 0, size), |v| > EPS 면 heading ← v 방향, 아니면 유지 — v1 과 같은 줄이다.
              정지는 v = 0 이라 heading 을 유지한다. 벽에 막혀 실제 이동이 짧아도 대사는 보행 상태의 속력으로 낸다
              (clamp 전 v 로 heading 을 정하는 v1 과 같은 기준)
          2)  (step) 포식자 — v1 그대로
          3a) (step) 대사 drain = energy_drain × drain_mult[g], drain_mult = c_rest + c_move·gait_speed²
              (계획서 drain = energy_drain·(c_rest + c_move·(v/herb_speed)²) 에서 v/herb_speed = gait_speed[g])
          3b) (step) 섭식 want ← clip((max − e_drained)/fepu, 0, food_eat_rate) × gait_eat[g] (`_eat`), 나머지 v1
          3c) (step) 에너지 보상: net_energy_reward 면 e_new − e_prev, 아니면 v1 획득량 e_new − e_drained.
              번식 리셋(4)·리스폰(8)은 그 뒤라 순변화에 들어가지 않는다
        C++ 꼴 (V = v1 조향 합을 정규화해 HerbSpeed 를 곱한 값, 지금 SteeringProcessor 의 Velocity):
                Cmd = (A >= TWalk) + (A >= TRun); G = (V.SizeSquared() > EPS * EPS) ? Cmd : Stop;
                Velocity = V * GaitSpeed[G]; Drain = EnergyDrain * DrainMult[G]; Want *= GaitEat[G].
        스텝 뒤 훅(replay_v2): `self.gait` 실제 보행, `self.gait_cmd` 명령 보행, `self.vel` 적용 속도(벽 clamp 전).
        """
        sp = self._sp
        t_walk, t_run = sp["thresholds"]
        cmd = (a_speed >= t_walk).view(np.int8) + (a_speed >= t_run).view(np.int8)
        # |v| > EPS ⇔ v·v > EPS². steer 의 v 는 0 이거나 크기 herb_speed 라 경계 근처 값이 없다. 정지 = 0 이라 곱으로 고른다
        g = cmd * ((v * v).sum(1) > EPS * EPS)
        v = v * sp["speed"][g][:, None]
        self.gait, self.gait_cmd, self.vel = g, cmd, v
        return v

    def _step_predators(self) -> np.ndarray:
        """포식자 2종 (§4.2). 은신처 안 초식은 거리가 `cover_hide_mult` 배로 보인다."""
        cfg = self.cfg
        if self.M == 0:
            return np.zeros(self.N, dtype=bool)

        ar = np.arange(self.M)
        dx = self.pos[:, 0][None, :] - self.pred_pos[:, 0:1]      # (M,N)
        dy = self.pos[:, 1][None, :] - self.pred_pos[:, 1:2]
        dist = np.sqrt(dx * dx + dy * dy)
        inv = 1.0 / np.maximum(dist, EPS)
        # 이번 스텝 이동 후 위치 기준. self._g는 이동 전 기하라 여기서 다시 판정한다.
        hide = np.where(self._in_cover(self.pos), cfg.cover_hide_mult, 1.0)[None, :]
        perceived = dist * hide
        self.pred_cd = np.maximum(self.pred_cd - 1, 0)
        hunting = self.pred_cd == 0
        vis = (
            (perceived <= cfg.pred_view_r)
            & (
                (dx * self.pred_head[:, 0:1] + dy * self.pred_head[:, 1:2]) * inv
                >= cfg.pred_fov_cos
            )
            & hunting[:, None]
        )

        # 추적: 시야 내 최근접(체감 거리 기준)
        masked = np.where(vis, perceived, np.inf)
        j = masked.argmin(1)
        has_target = np.isfinite(masked[ar, j])
        turn = self.rng.uniform(-cfg.pred_wander_turn, cfg.pred_wander_turn, self.M)
        c, s = np.cos(turn), np.sin(turn)
        wander = np.stack(
            [
                self.pred_head[:, 0] * c - self.pred_head[:, 1] * s,
                self.pred_head[:, 0] * s + self.pred_head[:, 1] * c,
            ],
            1,
        )
        chase = np.stack([dx[ar, j], dy[ar, j]], 1) * inv[ar, j][:, None]
        move = np.where(has_target[:, None], chase, wander)
        self.pred_pos = self.pred_pos + move * self.pred_speed[:, None]
        # 벽에서 반사 (§4.2 토러스 끄기)
        for axis in (0, 1):
            out_of = (self.pred_pos[:, axis] < 0.0) | (self.pred_pos[:, axis] > self.size)
            move[out_of, axis] *= -1.0
        self.pred_pos = np.clip(self.pred_pos, 0.0, self.size)
        self.pred_head = normalize(move)

        # 포획: 근접형은 결정적, 원거리형은 확률적 (§4.2). 포식자당 한 스텝 한 마리.
        hit = (perceived <= self.pred_catch_r[:, None]) & hunting[:, None]
        if self.pred_ranged.any():
            roll = self.rng.random((self.M, self.N)) < cfg.pred_ranged_catch_p
            hit &= np.where(self.pred_ranged[:, None], roll, True)
        hit_d = np.where(hit, perceived, np.inf)
        k = hit_d.argmin(1)
        got = np.isfinite(hit_d[ar, k])
        caught = np.zeros(self.N, dtype=bool)
        caught[k[got]] = True
        self.pred_cd[got] = int(cfg.pred_eat_cd)
        return caught

    def _eat(self, e_drained: np.ndarray, mult: np.ndarray | None = None) -> np.ndarray:
        """셀당 총 수요를 잔량에 비례 배분한다. 개체별 루프 없음 (§1.1).

        수요는 **흡수 가능량**으로 제한한다: 배부른 개체가 먹이를 계속 퍼가면 맵 전체가
        벗겨져서(측정: food가 0.02로 수렴) 먹이 탐색이 무의미해진다. 이렇게 두면 총
        소비량이 총 대사 수요를 따라가고 패치가 유지된다.

        `mult` (N,) 는 v2.1 보행 섭식 배수다(speed). 흡수 가능량 상한까지 자른 want 에 곱한 뒤 셀 수요를 합친다.
        뛰는 개체(0)는 수요가 없어 같은 셀 개체의 몫을 줄이지 않는다. None 이면 v1 과 같다.
        """
        cfg = self.cfg
        want = np.clip(
            (cfg.max_energy - e_drained) / cfg.food_energy_per_unit, 0.0, cfg.food_eat_rate
        )
        if mult is not None:
            want = want * mult
        ix, iy = self._cell_index(self.pos)
        flat = iy * self.gw + ix
        cells = self.gw * self.gw
        demand = np.bincount(flat, weights=want, minlength=cells)
        taken = np.minimum(demand, self.food.reshape(-1))
        frac = np.divide(taken, demand, out=np.zeros(cells), where=demand > 0)
        self.food -= taken.reshape(self.gw, self.gw)
        if self._fv is not None:
            self._fv_taken = taken          # v2.0b 훼손이 셀별 섭취량을 쓴다 (_food_v_step)
        return want * frac[flat]

    def _food_v_step(self) -> None:
        """v2.0b 먹이 2층의 한 스텝 (계획서 4.9.1). `step` 7) 에서 v1 재생 대신 부른다.

        셀마다 F = self.food, V = self.food_v(식생 용량), cap0 = self.food_cap, r = self.regen_field
        (은신처 0.3배 포함, v1 그대로). 한 스텝의 순서 — C++ 로 옮길 때 이 순서를 지킨다:

          3)  섭식 (`_eat`): F ← F − taken. taken ≤ F 라 F ≥ 0.
              4)~6) 번식·사망·피식 EMA 는 F·V 를 읽지 않으므로 훼손을 3) 직후에 해도 결과가 같다.
          7a) 훼손 (taken > 0 인 셀만): V ← V − α·taken·(1 − F/V). F 는 섭취 직후 값, V 는 훼손 전 값.
              taken > 0 이면 섭취 전 F ≥ taken > 0 이고 V ≥ 섭취 전 F 라 V > 0 이다 — 0 나눗셈이 없다.
          7b) 하한: V ← max(V, floor·cap0).
          7c) F ← min(F, V). α ≤ 1 이면 수학적으로는 바뀌지 않지만 반올림·α > 1 대비로 둔다.
          7d) 재생 (모든 셀): F ← F + r·(V − F), F ← min(F, V). v1 식(목표·상한 cap0)의 cap0 를 V 로
              바꾼 것이다. v1 은 clip(F, 0, cap0) 이지만 여기서는 F ≥ 0, V ≥ F 라 r·(V − F) ≥ 0 이고
              하한 0 이 저절로 지켜져 상한만 자른다(결과가 같다).
          7e) 휴식 회복 (모든 셀): V ← V + ρ·(cap0 − V), ρ = 1 − 2^(−1/h). 섭식이 없으면 cap0 − V 가
              h 스텝마다 절반이 된다. V 가 cap0 쪽으로만 움직이므로 F ≤ V ≤ cap0, V ≥ floor·cap0 가 유지된다.

        taken 은 고정 스텝 하나(1스텝 = 0.133s) 동안 그 셀에 들어간 모든 개체 섭취의 합이고(`_eat` 의 셀별 합),
        7a~7e 는 모든 섭식이 끝난 뒤 셀마다 한 번 계산한다. (1 − F/V) 가 비선형이라 개체마다·프레임마다 V 를
        바로 깎으면 같은 섭취량에서도 훼손이 작아진다(막 자란 셀을 8번에 나눠 먹으면 약 −45%). C++ 는
        ConsumeFood 를 셀별 버퍼에 누적했다가 같은 고정 간격으로 한 번 갱신한다. r·ρ 는 스텝당 값이라 간격 dt 를
        바꾸면 r' = 1 − (1 − r)^(dt/0.133s), ρ' = 1 − 2^(−dt/(h·0.133s)) 로 다시 환산하고, α 는 분할에 불변이
        아니므로 다시 보정한다.

        스텝 끝 불변식: 0 ≤ F ≤ V ≤ cap0, floor·cap0 ≤ V. cap0 = 0 셀은 F = V = 0 이다.
        taken > 0 가드는 최적화이면서 필수다. taken = 0 이고 V > 0 인 셀에서 7a~7c 는 항등이지만, cap0 = 0 셀
        (V = F = 0)을 조밀하게 계산하면 0·(1 − 0/0) = NaN 이 되어 F 와 관측 0 의 food_blur 누적합으로 퍼진다.
        그래서 먹힌 셀(많아야 N 개)만 계산한다(C++ 도 `if (Taken > 0)`). 가드를 단 조밀 계산과 비트 단위로 같다.
        α = 0 이고 V = cap0 로 시작하면 V 가 비트 단위로 cap0 에 머물러 v2.0(= v1) 세계와 같다
        (둘 다 tests/test_food_v2.py).
        """
        fv = self._fv
        F, V = self.food.reshape(-1), self.food_v.reshape(-1)     # 연속 배열의 뷰 — 제자리 갱신
        taken = self._fv_taken
        k = (taken > 0.0).nonzero()[0]      # taken ≥ 0. float 배열의 flatnonzero 보다 몇 배 빠르다
        if k.size:
            tk, f, v = taken[k], F[k], V[k]
            v = np.maximum(v - fv["alpha"] * tk * (1.0 - f / v), self._fv_floor.reshape(-1)[k])
            V[k] = v
            F[k] = np.minimum(f, v)
            self._fv_eaten.reshape(-1)[k] += tk
            self._fv_last_eat.reshape(-1)[k] = self.t + 1     # 이 스텝이 끝난 뒤의 self.t
        # 7d·7e 는 임시 배열 하나를 같이 쓴다 (r·(V − F) 와 (V − F)·r 은 같은 값이다)
        d = np.subtract(self.food_v, self.food)
        d *= self.regen_field
        self.food += d
        np.minimum(self.food, self.food_v, out=self.food)
        np.subtract(self.food_cap, self.food_v, out=d)
        d *= self.food_v_rho
        self.food_v += d

    def _respawn(self, dead: np.ndarray) -> None:
        """§4.3 — 죽은 슬롯에 랜덤 위치로 리스폰. 개체군 동역학은 넣지 않는다."""
        r, k = self.rng, len(dead)
        self.pos[dead] = r.uniform(0.0, self.size, (k, 2))
        ang = r.uniform(0.0, 2 * np.pi, k)
        self.head[dead] = np.stack([np.cos(ang), np.sin(ang)], 1)
        self.energy[dead] = self.cfg.init_energy
        self.repro_cd[dead] = 0

    # ------------------------------------------------------------------ #
    # 통계 (§7.2)
    # ------------------------------------------------------------------ #

    def _reset_stats(self) -> None:
        self._rew_total = 0.0
        self._repro_total = 0
        self._pred_deaths = 0
        self._starve_deaths = 0   # §7.2 열은 아니고 경제 보정용 진단 카운터
        self._life_sum = 0
        self._life_count = 0
        self._life_cur = np.zeros(self.N, dtype=np.int64)
        self._act_sum = np.zeros(self.act_dim)
        self._flee_sq = 0.0
        self._cover_steps = 0
        self._agent_steps = 0
        self._a_pred = np.zeros(3)   # cohesion, flee_dist, cover — 포식자 보일 때
        self._n_pred = 0
        self._a_nopred = np.zeros(3)
        self._n_nopred = 0
        self._f_hungry, self._n_hungry = 0.0, 0
        self._f_full, self._n_full = 0.0, 0
        if self._sp is not None:     # v2.1 보행 지표 (gait_stats). 모두 개체-스텝 수다
            # 개체-스텝 히스토그램 [실제 보행 3, 명령 보행 3, 포식자 거리 구간 4, 배부름 2]. 거리 구간은
            # [안 보임, d<0.25, 0.25≤d<0.5, d≥0.5] (d = d_pred/see_r), 배부름은 [energy<0.5, ≥0.5] (결정 때)
            self._gait_hist = np.zeros(GAIT_HIST_SHAPE, dtype=np.int64)
            self._sw = np.zeros(2, dtype=np.int64)            # 보행 전환 수 [실제, 명령] (B8)
            self._sw_steps = 0                                # 직전 스텝이 같은 개체인 개체-스텝
            self._gait_prev = np.full((2, self.N), -1, dtype=np.int8)   # 직전 [실제, 명령] 보행, −1 = 없음
            self._intake_sum = 0.0                            # 먹이로 얻은 에너지(상한에서 잘린 몫 제외)
            self._drain_sum = 0.0                             # 대사로 쓴 에너지

    def _accumulate(self, a, rew, repro, caught, starved, done) -> None:
        self._rew_total += float(rew.sum())
        self._repro_total += int(repro.sum())
        self._pred_deaths += int(caught.sum())
        self._starve_deaths += int(starved.sum())
        self._life_cur += 1
        if done.any():
            self._life_sum += int(self._life_cur[done].sum())
            self._life_count += int(done.sum())
            self._life_cur[done] = 0
        self._agent_steps += self.N
        self._act_sum += a.sum(0)
        self._flee_sq += float((a[:, 2] ** 2).sum())
        self._cover_steps += int(self._g["in_cover"].sum())

        seen = self._g["pred_count"] > 0
        cols = a[:, [1, 2, 3]]
        self._a_pred += cols[seen].sum(0)
        self._n_pred += int(seen.sum())
        self._a_nopred += cols[~seen].sum(0)
        self._n_nopred += int((~seen).sum())

        hungry = self.energy < 0.5 * self.cfg.max_energy
        self._f_hungry += float(a[hungry, 0].sum())
        self._n_hungry += int(hungry.sum())
        self._f_full += float(a[~hungry, 0].sum())
        self._n_full += int((~hungry).sum())

    def _gait_accumulate(self, e_prev: np.ndarray, intake: np.ndarray, drain: np.ndarray) -> None:
        """v2.1 보행 지표를 센다. `step` 이 `_accumulate` 바로 뒤, 관측을 새로 계산하기 전에 부른다.

        조건(포식자 거리, 배고픔)은 정책이 이번 행동을 고를 때 본 상태다: 스텝 전 기하 `self._g`, 스텝 전 에너지
        `e_prev`(리스폰 직후 개체는 init_energy, 관측 4 와 같다). B1·B2 는 명령 보행으로 잰다 — 상태를 안 보는
        상수·순열 대조군에서 조건부 차이가 구성상 0 이 되게 한다(계획서 6.3 판정 규칙). 방향이 없어 실제로는
        멈춘 몫은 stall_frac 로 따로 낸다.
        """
        cfg = self.cfg
        g, cmd = self.gait, self.gait_cmd
        d = self._g["d_pred_min"] / cfg.see_r                  # 안 보이면 inf
        # 거리 구간: 안 보임 0, [0, 0.25) 1, [0.25, 0.5) 2, [0.5, 1] 3 (inf 는 두 문턱을 넘지만 seen 이 0 으로 만든다)
        b = (d < np.inf) * (1 + (d >= B1_EDGES[0]) + (d >= B1_EDGES[1]))
        full = e_prev >= HUNGRY * cfg.max_energy               # False 배고픔, True 배부름
        code = ((g * 3 + cmd) * 4 + b) * 2 + full               # GAIT_HIST_SHAPE 의 C 순서 평탄 인덱스
        self._gait_hist += np.bincount(code, minlength=self._gait_hist.size).reshape(GAIT_HIST_SHAPE)

        prev = self._gait_prev
        same = prev[0] >= 0
        self._sw_steps += int(np.count_nonzero(same))
        self._sw[0] += np.count_nonzero(same & (prev[0] != g))
        self._sw[1] += np.count_nonzero(same & (prev[1] != cmd))
        prev[0] = g
        prev[1] = cmd

        self._intake_sum += float(intake.sum())
        self._drain_sum += float(drain.sum())

    def gait_stats(self) -> dict:
        """v2.1 보행 통계 — reset 뒤 누적 (v1 `stats()` 10열 밖, 계획서 4.8). Gate E1 과 B1·B2·B8 이 쓴다.

        열 순서는 `GAIT_STAT_COLUMNS`. 비율은 모두 개체-스텝 기준이다. 분모가 0 인 열은 nan 이다.
        - stop_frac·walk_frac·run_frac: 실제 보행 비율. stall_frac: 명령은 이동인데 방향이 없어 정지한 비율
        - stop_frac_cmd·walk_frac_cmd·run_frac_cmd: 명령 보행(행동 idx 4 의 문턱) 비율
        - hungry_frac: 결정 때 energy < 0.5 인 비율 (Gate E1 (a) "energy<0.5 스텝")
        - starve_rate: 아사 / 개체-스텝, starve_share: 아사 / 사망 (env_v2/rollout.py 와 같은 정의)
        - b1 = P(뛰기 | 보임 & d < 0.5·see_r) − P(뛰기 | 안 보임). p_run_unseen, p_run_d025 [0, 0.25),
          p_run_d050 [0.25, 0.5), p_run_d100 [0.5, 1] (× see_r) 은 거리 구간별 P(뛰기) (6.2 B1)
        - b2 = P(정지 | 배고픔) − P(정지 | 배부름), p_stop_hungry·p_stop_full (6.2 B2. v2.1 은 경계가 없어 모든 정지가
          '경계가 아닌 정지'다)
        - b8·b8_cmd: 개체당 초당 보행 전환 수(실제·명령). 직전 스텝이 같은 개체인 스텝만 센다. 1스텝 =
          policy_interval/60 초 (replay_v2.step_seconds 와 같은 정의, §9.7)
        - intake_per_step·drain_per_step: 개체-스텝당 먹이 에너지·대사
        """
        if self._sp is None:
            raise ValueError("gait_stats 는 speed 를 켠 세계에만 있다 (끈 세계는 v1 과 같이 늘 herb_speed 로 움직인다)")
        nan = float("nan")
        n = self._agent_steps
        H = self._gait_hist                                    # [실제, 명령, 거리 구간, 배부름]

        def ratio(x, y):
            return float(x) / float(y) if y else nan

        gait_n, cmd_n = H.sum((1, 2, 3)), H.sum((0, 2, 3))
        b1_n, b1_run = H.sum((0, 1, 3)), H[:, GAIT_RUN].sum((0, 2))
        b2_n, b2_stop = H.sum((0, 1, 2)), H[:, GAIT_STOP].sum((0, 1))
        stall = H[GAIT_STOP, GAIT_WALK:].sum()
        p_run = [ratio(b1_run[k], b1_n[k]) for k in range(4)]
        near = ratio(b1_run[1] + b1_run[2], b1_n[1] + b1_n[2])
        p_stop = [ratio(b2_stop[k], b2_n[k]) for k in range(2)]
        deaths = self._pred_deaths + self._starve_deaths
        per_sec = 60.0 / float(self.cfg.policy_interval)
        out = dict(
            stop_frac=ratio(gait_n[0], n), walk_frac=ratio(gait_n[1], n),
            run_frac=ratio(gait_n[2], n), stall_frac=ratio(stall, n),
            stop_frac_cmd=ratio(cmd_n[0], n), walk_frac_cmd=ratio(cmd_n[1], n),
            run_frac_cmd=ratio(cmd_n[2], n),
            hungry_frac=ratio(b2_n[0], n),
            starve_rate=self._starve_deaths / max(self.t * self.N, 1),
            starve_share=ratio(self._starve_deaths, deaths),
            b1=near - p_run[0], p_run_unseen=p_run[0], p_run_d025=p_run[1], p_run_d050=p_run[2],
            p_run_d100=p_run[3],
            b2=p_stop[0] - p_stop[1], p_stop_hungry=p_stop[0], p_stop_full=p_stop[1],
            b8=ratio(self._sw[0], self._sw_steps) * per_sec, b8_cmd=ratio(self._sw[1], self._sw_steps) * per_sec,
            intake_per_step=ratio(self._intake_sum, n), drain_per_step=ratio(self._drain_sum, n),
        )
        assert tuple(out) == GAIT_STAT_COLUMNS
        return out

    def stats(self) -> dict:
        """§7.2 반환 열."""
        n, steps = self.N, max(self.t, 1)
        agent_steps = max(self._agent_steps, 1)
        lives = self._life_sum + int(self._life_cur.sum())
        n_lives = self._life_count + n
        flee_mean = self._act_sum[2] / agent_steps
        flee_var = max(self._flee_sq / agent_steps - flee_mean**2, 0.0)

        def _d(sum_a, n_a, sum_b, n_b):
            if n_a == 0 or n_b == 0:
                return float("nan")
            return float(np.abs(sum_a / n_a - sum_b / n_b).mean())

        return dict(
            mean_return=self._rew_total / n,
            survival=lives / max(n_lives, 1),
            repro=self._repro_total / n,
            predation_rate=self._pred_deaths / (steps * n),
            cohesion_mean=self._act_sum[1] / agent_steps,
            flee_dist_mean=flee_mean,
            flee_dist_std=float(np.sqrt(flee_var)),
            cover_frac=self._cover_steps / agent_steps,
            react_pred=_d(self._a_pred, self._n_pred, self._a_nopred, self._n_nopred),
            react_hunger=_d(
                np.array([self._f_hungry]),
                self._n_hungry,
                np.array([self._f_full]),
                self._n_full,
            ),
        )

    def food_stats(self) -> dict:
        """v2.0b 먹이 통계 — 지금 시점의 값 (v1 `stats()` 10열 밖, 계획서 4.8). Gate F·영상·기록 학습이 쓴다.

        지역은 v2.3 전까지 맵 좌우 절반(`_left_half`)으로 대신한다. 모두 cap0 > 0 셀만 센다.
        접미사 없음 = 맵 전체, `_left`·`_right` = 절반.
        - v_ratio, f_ratio: 지역 비율 ΣV/Σcap0, ΣF/Σcap0 (v2.3 지역 장부의 V_r·F_r 정의, 4.4)
        - v_cell_mean: 셀별 V/cap0 의 평균 (Gate F (a) "평균 V/cap0")
        - floor_frac: V/cap0 ≤ floor + FOOD_V_FLOOR_TOL 인 셀 비율 (Gate F (a) "하한에 붙은 셀")
        - eaten: reset 뒤 누적 섭취량의 합
        - half_life, rho, init_left, init_right: 이 세계에서 뽑은 회복 반감기와 V 초기 비율
        food_v 를 끈 세계는 V = cap0 로 본다(v_ratio 1). 하한·기록·뽑은 값이 없는 열은 nan 이다.
        절반에 cap0 > 0 셀이 없으면 그 절반의 열은 nan 이다.
        """
        on = self._fv is not None
        nan = float("nan")
        cap0, F = self.food_cap, self.food
        V = self.food_v if on else cap0
        pos = cap0 > 0.0
        left = self._left_half()
        out = dict(
            half_life=float(self.food_v_half_life) if on else nan,
            rho=float(self.food_v_rho) if on else nan,
            init_left=self.food_v_init[0] if on else nan,
            init_right=self.food_v_init[1] if on else nan,
        )
        tol = self._fv["floor"] + FOOD_V_FLOOR_TOL if on else nan
        for sfx, m in (("", pos), ("_left", pos & left), ("_right", pos & ~left)):
            c = cap0[m]
            s = float(c.sum())
            if s <= 0.0:
                for key in ("v_ratio", "f_ratio", "v_cell_mean", "floor_frac", "eaten"):
                    out[key + sfx] = nan
                continue
            vr = V[m] / c
            out["v_ratio" + sfx] = float(V[m].sum()) / s
            out["f_ratio" + sfx] = float(F[m].sum()) / s
            out["v_cell_mean" + sfx] = float(vr.mean())
            out["floor_frac" + sfx] = float((vr <= tol).mean()) if on else nan
            out["eaten" + sfx] = float(self._fv_eaten[m].sum()) if on else nan
        return out

    def food_cells(self) -> dict:
        """셀별 먹이 상태의 사본, 모두 (gw, gw) 이고 [iy, ix] 순서. Gate F (b) V 자기상관, (c) 흔적 진폭
        (누적 섭취 상위 10% 셀 vs 같은 cap0 구간 하위 50%, 섭식이 멈춘 뒤 경과), 영상의 짓밟힌 땅이 쓴다.

        - food_cap(cap0), food(F), food_v(V), left(왼쪽 절반), cover(은신처 셀)
        - eaten: reset 뒤 누적 섭취량, last_eat: 마지막으로 뜯긴 스텝의 self.t (뜯긴 적 없으면 −1)
        food_v 를 끈 세계는 food_v = cap0 사본이고 eaten·last_eat 는 None 이다.
        """
        on = self._fv is not None
        return dict(
            food_cap=self.food_cap.copy(),
            food=self.food.copy(),
            food_v=(self.food_v if on else self.food_cap).copy(),
            left=self._left_half(),
            cover=self.cover_cell.copy(),
            eaten=self._fv_eaten.copy() if on else None,
            last_eat=self._fv_last_eat.copy() if on else None,
        )
