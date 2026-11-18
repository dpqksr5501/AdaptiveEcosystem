"""R10 세계 — K 개 세계를 묶어 한 걸음씩 (0 단계 사양 5 절).

종 이름은 코드에 없다. 종마다 다른 것은 모두 종 카드 숫자(슬롯마다 배열)로만 나타난다.
슬롯 N = K × S (세계마다 S 칸). 지형은 세계마다 크기가 달라 셀을 한 줄로 이어 붙이고(cell_off) 세계별 폭·높이로 찾는다.

한 결정 = 2 걸음. 걸음 차례(모두 이전 위치에서 동시에): 이동 → 접촉(물기·반격) → 먹기 → 대사 → 번식 → 죽음·사체 → 먹이 재생·수위.
결정 걸음 끝에 감각(r10.senses)을 만든다. 행동은 결정 때 정하고 두 걸음 동안 그대로다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from r10 import contract as C
from r10 import species as S
from r10 import terrain as T

FOOD_INDEX = {k: i for i, k in enumerate(T.FOOD_KINDS)}
MEAT_KINDS = ("meat", "carrion")


@dataclass
class Rules:
    """세계 규칙 상수 (종과 상관없음). 바꾸면 세계가 바뀐다 — 팩 manifest 에 적는다."""

    bite_cone_cos: float = 0.5           # 머리 앞 ±60°
    approach_min_mps: float = 0.4        # 다가가는 속도 (R9 0.03 단위/걸음 ≈ 0.45 m/s)
    counter_cone_cos: float = 0.25       # 반격: 상대 앞 ±75.5° (R9)
    counter_hp_min: float = 0.35
    bite_damage_k: float = 0.5           # 피해 = clip(k × (공격 질량 × ratio) / 먹잇감 질량, 0.2, 1)
    counter_cd_s: float = 4.0
    wade_slow: float = 0.5               # 걷기 깊이만큼 잠기면 속도 × (1 − 0.5)
    swim_clear_k: float = 0.65           # 헤엄 여유 = 반지름 × 0.65 (언리얼)
    hover_m: float = 0.5                 # 못 내려앉으면 이 높이에서 맴돈다
    land_slope_deg: float = 49.5         # 언리얼 착지 바닥 normal ≥ 0.65
    air_clear_m: float = 2.0             # 이 높이 위의 나는 몸은 막힘·나무를 넘는다
    dive_contact_k: float = 2.0          # 급강하 접촉: 높이 ≤ 반지름 × 2
    breath_s: float = 20.0               # 물고기가 물 밖(깊이 부족)에서 버티는 시간
    shelter_bite_radius_m: float = 0.25  # 은신처 안 몸은 이보다 작은 몸만 물 수 있다 (덤불 속으로 들어갈 수 있는 몸)
    reserve_refill: float = 0.25         # E ≥ 0.7 일 때 얻은 것 가운데 비축으로
    reserve_draw_below: float = 0.25     # E 가 이 아래면 비축에서 꺼냄
    carcass_meat_per_kg: float = 0.6
    carcass_life_s: float = 300.0
    mate_e_min: float = 0.6
    birth_e_min: float = 0.4
    birth_cost: float = 0.3
    rain_sight: float = 0.9
    snow_speed: float = 0.85
    respawn_decisions: int = 50          # 학습 세계: 죽은 칸은 이만큼 뒤 새 개체로 (R9 학습 세계와 같은 꼴)
    reward_alive: float = 0.01
    reward_birth: float = 10.0
    reward_death: float = -10.0
    carcass_slots: int = 32


@dataclass
class Roster:
    """세계 하나의 종 목록: (카드, 시작 마릿수, 상한)."""

    entries: list = field(default_factory=list)          # [(card, n0, cap), ...]


class World:
    """K 개 세계. maps[k] 와 rosters[k] 로 만든다. 학습 칸 고르기·두뇌는 바깥(vec_env)에서 한다."""

    def __init__(self, maps: list, rosters: list, slots: int, seed: int, rules: Rules | None = None, train: bool = True,
                 jitter: bool = True):
        self.K = len(maps)
        assert len(rosters) == self.K
        self.S = int(slots)
        self.N = self.K * self.S
        self.rules = rules or Rules()
        self.train = train
        self.rng = np.random.default_rng([int(seed), 0x5210_0001])
        self.t = 0
        self._build_maps(maps)
        self._build_slots(rosters, jitter)
        self.weather = np.zeros((self.K, 3))                 # 비·눈·기온(0~1)
        for k in range(self.K):
            self.weather[k] = (self.rng.uniform(0, 1) * (self.rng.random() < 0.4), self.rng.uniform(0, 1) * (self.rng.random() < 0.15),
                               self.rng.uniform(0.2, 0.8))
        self.carcass = {"wk": np.full(self.K * self.rules.carcass_slots, -1), "x": np.zeros(self.K * self.rules.carcass_slots),
                        "y": np.zeros(self.K * self.rules.carcass_slots), "z": np.zeros(self.K * self.rules.carcass_slots),
                        "meat": np.zeros(self.K * self.rules.carcass_slots), "age": np.zeros(self.K * self.rules.carcass_slots),
                        "kin": np.full(self.K * self.rules.carcass_slots, -1)}
        self.actions = np.full(self.N, C.A_WATCH, dtype=np.int64)
        self.events = {"deaths": [], "births": [], "bites": []}
        self._gain = np.zeros(self.N)
        self._father = {}
        self._update_water()

    # ------------------------------------------------------------------ 지형

    def _build_maps(self, maps):
        self.maps = maps
        self.mw = np.array([m.w for m in maps], np.int64)
        self.mh = np.array([m.h for m in maps], np.int64)
        self.cell_m = np.array([m.cell_m for m in maps])
        self.cell_off = np.concatenate([[0], np.cumsum(self.mw * self.mh)[:-1]]).astype(np.int64)
        cat = lambda k: np.concatenate([getattr(m, k).reshape(-1) for m in maps])
        self.g_z = cat("ground_z").astype(np.float64)
        self.g_bed = cat("water_bed_z").astype(np.float64)
        self.g_surf0 = cat("water_surf0_z").astype(np.float64)
        self.g_wsys = cat("water_sys").astype(bool)
        self.g_cur = np.concatenate([m.current.reshape(-1, 2) for m in maps]).astype(np.float64)
        self.g_block = cat("block").astype(bool)
        self.g_cover = cat("cover_sight").astype(np.float64)
        self.g_shelter = cat("cover_body").astype(bool)
        self.g_canopy = cat("canopy").astype(bool)
        self.g_food = np.concatenate([m.food_amount.reshape(len(T.FOOD_KINDS), -1) for m in maps], axis=1).astype(np.float64)
        self.g_cap = np.concatenate([m.food_cap.reshape(len(T.FOOD_KINDS), -1) for m in maps], axis=1).astype(np.float64)
        self.g_regen = np.concatenate([m.food_regen.reshape(len(T.FOOD_KINDS), -1) for m in maps], axis=1).astype(np.float64)
        self.g_dry = np.concatenate([m.food_dry.reshape(len(T.FOOD_KINDS), -1) for m in maps], axis=1).astype(np.float64)
        self.cell_wk = np.repeat(np.arange(self.K), self.mw * self.mh)
        self.level = np.zeros(self.K)
        self.level_prev = np.zeros(self.K)

    def cidx(self, wk, x, y) -> np.ndarray:
        """세계 wk 의 (x, y) → 이어 붙인 셀 번호 (가장자리로 자름)."""
        cm = self.cell_m[wk]
        ix = np.clip(np.floor(x / cm).astype(np.int64), 0, self.mw[wk] - 1)
        iy = np.clip(np.floor(y / cm).astype(np.int64), 0, self.mh[wk] - 1)
        return self.cell_off[wk] + iy * self.mw[wk] + ix

    def inside(self, wk, x, y) -> np.ndarray:
        cm = self.cell_m[wk]
        return (x >= 0) & (y >= 0) & (x < self.mw[wk] * cm) & (y < self.mh[wk] * cm)

    def depth_at(self, c) -> np.ndarray:
        d = self.g_surf0[c] + self.level[self.cell_wk[c]] - self.g_bed[c]
        return np.where(self.g_wsys[c], np.maximum(d, 0.0), 0.0)

    def surface_at(self, c) -> np.ndarray:
        return np.where(self.g_wsys[c], self.g_surf0[c] + self.level[self.cell_wk[c]], self.g_z[c])

    def _update_water(self):
        tsec = self.t * C.STEP_S
        self.level_prev = self.level.copy()
        self.level = np.array([m.water.offset(tsec, float(self.weather[k, 0])) for k, m in enumerate(self.maps)])

    # ------------------------------------------------------------------ 슬롯

    _BODY = ("mass_kg", "radius_m", "walk_mps", "run_mps", "swim_mps", "swim_fast_mps", "fly_mps", "cruise_mps", "dive_mps",
             "accel_mps2", "turn_dps", "lat_accel_mps2", "max_slope_deg", "step_m", "stamina_s", "stamina_recover_s")

    def _build_slots(self, rosters, jitter):
        N = self.N
        self.cards = [[] for _ in range(self.K)]              # 세계별 (흔든) 카드 목록
        self.base_cards = [[] for _ in range(self.K)]
        self.sp = np.full(N, -1, np.int64)                    # 세계 안 종 번호 (-1 빈 칸)
        self.cap = []                                         # 세계별 종별 상한
        self.wk = np.repeat(np.arange(self.K), self.S)
        f = lambda: np.zeros(N)
        b = lambda: np.zeros(N, bool)
        self.p = {k: f() for k in self._BODY}
        for k in ("ground", "swim", "fly", "needs_water"):
            self.p[k] = b()
        for k in ("wade_depth_m", "swim_depth_frac", "cruise_height_m", "ceiling_m", "takeoff_s", "sight_m", "fov_cos", "smell_m",
                  "night_vision", "rate_per_s", "energy_per_unit", "drain_per_step", "reserve_days", "run_cost", "swim_cost",
                  "fly_cost", "kill_mass_ratio", "reach_m", "attack_cd_s", "defense", "counter_reach_m", "maturity_days",
                  "litter", "gestation_days"):
            self.p[k] = f()
        self.p["diet"] = np.zeros((N, len(S.DIET_KEYS)))
        self.body_vec = np.zeros((N, len(C.BODY_NAMES)), np.float32)
        self.amask = np.zeros((N, C.N_ACTIONS), bool)
        self.omask = np.zeros((N, C.OBS_DIM), bool)
        self.alive = b()
        self.x, self.y, self.z = f(), f(), f()               # z: 나는 몸 = 땅 위 높이, 헤엄 몸 = 절대 높이
        self.hx, self.hy = np.ones(N), f()
        self.speed = f()
        self.vx, self.vy = f(), f()
        self.airborne, self.swimming, self.takeoff_left = b(), b(), f()
        self.E, self.R, self.stam, self.hp = f(), f(), f(), f()
        self.age_days, self.sex, self.preg_left, self.birth_wait = f(), b(), f(), f()
        self.pregnant = b()
        self.breath, self.attack_cd = f(), f()
        self.dead_wait = np.zeros(N, np.int64)
        self.respawn_wait = np.full(N, self.rules.respawn_decisions, np.int64)   # 학습 칸은 vec_env 가 1 로
        self.uid = np.zeros(N, np.int64)
        self._next_uid = 1
        self.reward = f()
        self.done = b()
        self.births_step = f()
        for k, ros in enumerate(rosters):
            caps = []
            base = k * self.S
            used = 0
            for si, (card, n0, cap) in enumerate(ros.entries):
                c = S.jitter(card, self.rng) if jitter else card
                self.cards[k].append(c)
                self.base_cards[k].append(card)
                caps.append(int(cap))
                n_slots = int(cap)
                if used + n_slots > self.S:
                    raise ValueError(f"world {k}: roster caps {used + n_slots} > slots {self.S}")
                idx = np.arange(base + used, base + used + n_slots)
                self.sp[idx] = si
                self._set_body(idx, c)
                for j in idx[:int(n0)]:
                    self._spawn(j, adult_frac=0.7)
                used += n_slots
            self.cap.append(caps)

    def _set_body(self, idx, c):
        p = self.p
        for k in self._BODY:
            v = c["body"].get(k)
            p[k][idx] = 0.0 if v is None else float(v)
        for k in ("ground", "swim", "fly", "needs_water"):
            p[k][idx] = bool(c["medium"][k])
        for k in ("wade_depth_m", "swim_depth_frac", "cruise_height_m", "ceiling_m", "takeoff_s"):
            v = c["medium"].get(k)
            p[k][idx] = 0.0 if v is None else float(v)
        p["sight_m"][idx] = c["senses"]["sight_m"]
        p["fov_cos"][idx] = math.cos(math.radians(min(c["senses"]["fov_deg"], 360.0) / 2.0))
        p["smell_m"][idx] = c["senses"]["smell_m"]
        p["night_vision"][idx] = c["senses"]["night_vision"]
        p["rate_per_s"][idx] = c["eat"]["rate_per_s"]
        p["energy_per_unit"][idx] = c["eat"]["energy_per_unit"]
        p["drain_per_step"][idx] = c["metabolism"]["drain_per_day"] / C.DAY_STEPS
        p["reserve_days"][idx] = c["metabolism"]["reserve_days"]
        p["run_cost"][idx] = c["metabolism"]["run_cost"]
        p["swim_cost"][idx] = c["metabolism"].get("swim_cost") or 1.0
        p["fly_cost"][idx] = c["metabolism"].get("fly_cost") or 1.0
        for k in ("kill_mass_ratio", "reach_m", "attack_cd_s", "defense", "counter_reach_m"):
            p[k][idx] = c["combat"][k]
        for k in ("maturity_days", "litter", "gestation_days"):
            p[k][idx] = c["life"][k]
        p["diet"][idx] = [float(c["diet"][k]) for k in S.DIET_KEYS]
        self.body_vec[idx] = S.body_vector(c)
        self.amask[idx] = C.action_mask(c["medium"])
        self.omask[idx] = C.obs_mask(c["medium"])

    # ------------------------------------------------------------------ 자리

    def clearance(self, i) -> np.ndarray:
        return self.p["radius_m"][i] * self.rules.swim_clear_k

    def _place_ok(self, i, x, y) -> np.ndarray:
        """슬롯 i 의 몸이 (x, y) 에 설 수 있나 (벡터, i 와 x 같은 길이)."""
        wk = self.wk[i]
        c = self.cidx(wk, x, y)
        d = self.depth_at(c)
        clr = self.clearance(i)
        ok = self.inside(wk, x, y) & ~self.g_block[c]
        water_ok = d >= 2.0 * clr
        land_ok = d <= np.maximum(self.p["wade_depth_m"][i], 0.0)
        return ok & np.where(self.p["needs_water"][i], water_ok, land_ok | (self.p["swim"][i] & water_ok))

    def _spawn(self, i, adult_frac=0.7, near=None):
        """빈 칸 i 에 새 개체 (near = (x, y) 면 그 둘레, 아니면 맵 어디든 몸에 맞는 자리)."""
        wk = int(self.wk[i])
        W, H = self.mw[wk] * self.cell_m[wk], self.mh[wk] * self.cell_m[wk]
        ii = np.array([i])
        for _ in range(60):
            if near is None:
                x, y = self.rng.uniform(0.5, W - 0.5), self.rng.uniform(0.5, H - 0.5)
            else:
                a = self.rng.uniform(0, 2 * math.pi)
                r = self.rng.uniform(0.5, 3.0)
                x, y = near[0] + r * math.cos(a), near[1] + r * math.sin(a)
            if self._place_ok(ii, np.array([x]), np.array([y]))[0]:
                break
        else:
            self.alive[i] = False
            return False
        a = self.rng.uniform(0, 2 * math.pi)
        self.x[i], self.y[i] = x, y
        self.hx[i], self.hy[i] = math.cos(a), math.sin(a)
        self.speed[i] = 0.0
        self.vx[i] = self.vy[i] = 0.0
        c = self.cidx(np.array([wk]), np.array([x]), np.array([y]))
        self.airborne[i] = False
        self.takeoff_left[i] = 0.0
        if self.p["needs_water"][i] or (self.p["swim"][i] and self.depth_at(c)[0] > self.p["wade_depth_m"][i]):
            bed, surf = self.g_bed[c][0], self.surface_at(c)[0]
            clr = self.clearance(ii)[0]
            frac = self.p["swim_depth_frac"][i] or 0.5
            self.z[i] = bed + clr + (surf - bed - 2 * clr) * frac
            self.swimming[i] = True
        else:
            self.z[i] = 0.0
            self.swimming[i] = False
        self.E[i] = self.rng.uniform(0.6, 0.9)
        self.R[i] = self.rng.uniform(0.2, 0.6)
        self.stam[i] = 1.0
        self.hp[i] = 1.0
        mat = max(self.p["maturity_days"][i], 1e-3)
        self.age_days[i] = mat * (self.rng.uniform(1.0, 3.0) if self.rng.random() < adult_frac else self.rng.uniform(0.05, 0.9))
        self.sex[i] = self.rng.random() < 0.5
        self.preg_left[i] = 0.0
        self.pregnant[i] = False
        self.birth_wait[i] = 0.0
        self.breath[i] = 1.0
        self.attack_cd[i] = 0.0
        self.alive[i] = True
        self.dead_wait[i] = 0
        self.uid[i] = self._next_uid
        self._next_uid += 1
        return True

    # ------------------------------------------------------------------ 한 결정

    def step(self, actions: np.ndarray) -> None:
        """한 결정(2 걸음). actions: (N,) 정수. 막힌 행동은 지켜보기로 바꾼다(학습 쪽은 마스크로 막지만 지킨다)."""
        a = np.asarray(actions, dtype=np.int64)
        bad = ~self.amask[np.arange(self.N), np.clip(a, 0, C.N_ACTIONS - 1)] | (a < 0) | (a >= C.N_ACTIONS)
        self.actions = np.where(bad, C.A_WATCH, a)
        self.reward[:] = 0.0
        self.done[:] = False
        self.births_step[:] = 0.0
        e0 = self._energy_value()
        was_alive = self.alive.copy()
        for _ in range(C.DECISION_STEPS):
            self._move()
            self._contact()
            self._eat()
            self._metabolism()
            self._life()
            self._deaths()
            self._regrow()
            self.t += 1
            self._update_water()
        e1 = self._energy_value()
        died = was_alive & ~self.alive
        r = self.rules
        self.reward = np.where(was_alive, r.reward_alive + (e1 - e0) * self.alive + r.reward_birth * self.births_step, 0.0)
        self.reward = np.where(died, r.reward_death, self.reward)
        self.done = died.copy()
        if self.train:
            self._respawn()

    def _energy_value(self) -> np.ndarray:
        return self.E + self.R * self.p["reserve_days"] * C.DAY_STEPS * self.p["drain_per_step"]

    # ------------------------------------------------------------------ 이동

    def _dir_of_action(self, a):
        """행동 → (머리 기준 방향 번호 j 또는 −1, 빠르기 0 서기·1 천천히·2 빠르게)."""
        j = np.full(a.shape, -1)
        gait = np.zeros(a.shape, np.int64)
        slow = (a >= C.A_SLOW0) & (a < C.A_SLOW0 + 8)
        fast = (a >= C.A_FAST0) & (a < C.A_FAST0 + 8)
        j[slow] = a[slow] - C.A_SLOW0
        j[fast] = a[fast] - C.A_FAST0
        gait[slow] = 1
        gait[fast] = 2
        return j, gait

    def _move(self):
        r = self.rules
        al = self.alive
        a = self.actions
        j, gait = self._dir_of_action(a)
        p = self.p
        wk = self.wk
        c0 = self.cidx(wk, self.x, self.y)
        depth0 = self.depth_at(c0)
        # 매체 상태
        in_deep = depth0 > np.maximum(p["wade_depth_m"], 0.0)
        swim_now = al & p["swim"] & (in_deep | p["needs_water"])
        flying = al & self.airborne
        # 목표 속력
        walk, run = p["walk_mps"], p["run_mps"]
        wade_f = 1.0 - r.wade_slow * np.clip(depth0 / np.maximum(p["wade_depth_m"], 1e-6), 0, 1) * (depth0 > 0)
        ground_v = np.where(gait == 2, run, np.where(gait == 1, walk, 0.0)) * np.where(swim_now, 1.0, wade_f)
        swim_v = np.where(gait == 2, p["swim_fast_mps"], np.where(gait == 1, p["swim_mps"], 0.0))
        high = self.z >= 0.6 * p["cruise_height_m"]
        fly_v = np.where(gait == 2, np.where(high, p["cruise_mps"], 1.3 * p["fly_mps"]), np.where(gait == 1, p["fly_mps"], 0.0))
        fly_v = np.where(a == C.A_DIVE, p["fly_mps"], fly_v)
        stam_lock = self.stam <= 0.0
        v_t = np.where(flying, fly_v, np.where(swim_now, swim_v, ground_v))
        v_t = np.where(stam_lock & (gait == 2), np.where(flying, p["fly_mps"], np.where(swim_now, p["swim_mps"], walk)), v_t)
        v_t = v_t * (0.5 + 0.5 * self.hp) * np.where(self.weather[wk, 1] > 0.5, r.snow_speed, 1.0) * al
        # 원하는 방향 (머리 기준 j → 세계)
        moving = j >= 0
        ca, sa = C.DIR8[np.maximum(j, 0), 0], C.DIR8[np.maximum(j, 0), 1]
        dx = np.where(moving, self.hx * ca - self.hy * sa, self.hx)
        dy = np.where(moving, self.hx * sa + self.hy * ca, self.hy)
        # 회전 한계 (M1): min(몸 한계, 옆 가속 / 속력)
        cur_ang = np.arctan2(self.hy, self.hx)
        want = np.arctan2(dy, dx)
        dang = (want - cur_ang + np.pi) % (2 * np.pi) - np.pi
        spd = np.maximum(self.speed, 0.1)
        max_turn = np.minimum(np.radians(p["turn_dps"]), p["lat_accel_mps2"] / spd) * C.STEP_S
        turn = np.clip(dang, -max_turn, max_turn) * moving
        ang = cur_ang + turn
        self.hx, self.hy = np.cos(ang), np.sin(ang)
        # 가속 한계
        dv = np.clip(v_t - self.speed, -p["accel_mps2"] * C.STEP_S * 2, p["accel_mps2"] * C.STEP_S)
        self.speed = np.maximum(self.speed + dv, 0.0) * al
        step = self.speed * C.STEP_S
        nx = self.x + self.hx * step
        ny = self.y + self.hy * step
        # 물살 (헤엄 몸)
        cur = self.g_cur[c0]
        nx = np.where(swim_now, nx + cur[:, 0] * C.STEP_S, nx)
        ny = np.where(swim_now, ny + cur[:, 1] * C.STEP_S, ny)
        # 지나갈 수 있나: 나는 몸은 air_clear_m 위면 막힘 없음, 아래면 막힘(바위·줄기)만 — 물·경사는 상관없음
        free_air = flying & (self.z >= r.air_clear_m)
        low_air = flying & ~free_air
        allidx = np.arange(self.N)

        def can_go(tx, ty):
            c1 = self.cidx(wk, tx, ty)
            fly_ok = self.inside(wk, tx, ty) & ~self.g_block[c1]
            return free_air | np.where(low_air, fly_ok, self._pass_ok(allidx, self.x, self.y, tx, ty))

        ok = can_go(nx, ny)
        # 막히면 축 하나씩 미끄러짐
        okx = can_go(nx, self.y)
        oky = can_go(self.x, ny)
        fx = np.where(ok, nx, np.where(okx, nx, self.x))
        fy = np.where(ok, ny, np.where(~okx & oky, ny, self.y))
        blocked = ~ok & ~okx & ~oky
        self.speed = np.where(blocked, 0.0, self.speed)
        W = self.mw[wk] * self.cell_m[wk]
        H = self.mh[wk] * self.cell_m[wk]
        fx = np.clip(fx, 0.01, W - 0.01)
        fy = np.clip(fy, 0.01, H - 0.01)
        self.vx = (fx - self.x) / C.STEP_S * al
        self.vy = (fy - self.y) / C.STEP_S * al
        self.x = np.where(al, fx, self.x)
        self.y = np.where(al, fy, self.y)
        self._vertical()

    def _pass_ok(self, i, x0, y0, x1, y1) -> np.ndarray:
        """땅·헤엄 몸이 (x0,y0)→(x1,y1) 로 갈 수 있나: 막힘·단차/경사·깊이(사양 5 절). 끝점만 본다(한 걸음 < 1 셀 어림)."""
        p = self.p
        wk = self.wk[i]
        c0 = self.cidx(wk, x0, y0)
        c1 = self.cidx(wk, x1, y1)
        same = c0 == c1
        inside = self.inside(wk, x1, y1)
        d1 = self.depth_at(c1)
        clr = self.clearance(i)
        rise = self.g_z[c1] - self.g_z[c0]
        dist = np.maximum(np.hypot(x1 - x0, y1 - y0), 1e-6)
        run_len = np.maximum(dist, self.cell_m[wk])
        slope_ok = (rise <= p["step_m"]) | (np.degrees(np.arctan2(rise, run_len)) <= p["max_slope_deg"])
        land_ok = ~self.g_block[c1] & slope_ok & ((d1 <= p["wade_depth_m"]) | (p["swim"] & (d1 >= 2 * clr)))
        water_ok = d1 >= 2 * clr
        ok = np.where(p["needs_water"], water_ok, land_ok)
        return inside & (same | ok)

    def _vertical(self):
        r = self.rules
        p = self.p
        a = self.actions
        al = self.alive
        dt = C.STEP_S
        c = self.cidx(self.wk, self.x, self.y)
        # 나는 몸
        fly = al & p["fly"]
        landed = fly & ~self.airborne
        can_takeoff = landed & (a == C.A_UP) & ~self.g_canopy[c] & (self.stam > 0.05)
        self.airborne = self.airborne | can_takeoff
        self.takeoff_left = np.where(can_takeoff, p["takeoff_s"], np.maximum(self.takeoff_left - dt, 0.0))
        air = fly & self.airborne
        climb = np.where(self.takeoff_left > 0, np.maximum(p["cruise_height_m"], 1.0) / np.maximum(p["takeoff_s"], 0.1) * 0.3,
                         0.65 * p["fly_mps"])
        dz = np.where(a == C.A_UP, climb, np.where(a == C.A_DOWN, -0.65 * p["fly_mps"], np.where(a == C.A_DIVE, -p["dive_mps"], 0.0)))
        dz = np.where(self.takeoff_left > 0, np.maximum(dz, climb), dz)
        z_new = np.clip(self.z + dz * dt, 0.0, np.maximum(p["ceiling_m"], 1.0))
        slope_here = self._slope_deg(c)
        can_land = ~self.g_wsys[c] | (self.depth_at(c) <= 0)
        can_land &= (slope_here <= r.land_slope_deg) & ~self.g_canopy[c]
        # 내려앉을 수 없는 칸(물·가파름·나무 아래) 위에서는 hover_m 아래로 못 내려간다 — 세계가 다른 자리를 찾아 주지 않는다
        z_new = np.where(can_land, z_new, np.maximum(z_new, r.hover_m))
        touch = air & (z_new <= 0.0) & (self.takeoff_left <= 0)
        land_now = touch & can_land
        self.z = np.where(air, z_new, self.z)
        self.airborne = np.where(land_now, False, self.airborne)
        self.z = np.where(land_now, 0.0, self.z)
        # 헤엄 몸: 새 자리의 깊이로 헤엄인지 다시 정한다. 막 물에 든 몸은 물기둥 가운데에서 시작
        depth = self.depth_at(c)
        sw = al & p["swim"] & ((depth > np.maximum(p["wade_depth_m"], 0.0)) | p["needs_water"])
        newly = sw & ~self.swimming
        self.swimming = sw
        bed = self.g_bed[c]
        surf = self.surface_at(c)
        clr = self.clearance(np.arange(self.N))
        lo, hi = bed + clr, np.maximum(surf - clr, bed + clr)
        dzs = np.where(a == C.A_UP, 0.5 * p["swim_mps"], np.where(a == C.A_DOWN, -0.5 * p["swim_mps"], 0.0))
        zs = np.where(newly, (lo + hi) / 2, self.z)
        self.z = np.where(sw, np.clip(zs + dzs * dt, lo, hi), self.z)
        self.z = np.where(al & ~sw & ~(fly & self.airborne), 0.0, self.z)

    def _slope_deg(self, c) -> np.ndarray:
        wk = self.cell_wk[c]
        w = self.mw[wk]
        off = self.cell_off[wk]
        loc = c - off
        ix, iy = loc % w, loc // w
        # 양쪽 차이 (돌려도 같은 값 — 감각 회전 불변 시험)
        xr = off + iy * w + np.minimum(ix + 1, w - 1)
        xl = off + iy * w + np.maximum(ix - 1, 0)
        yu = off + np.minimum(iy + 1, self.mh[wk] - 1) * w + ix
        yd = off + np.maximum(iy - 1, 0) * w + ix
        gx = (self.g_z[xr] - self.g_z[xl]) / 2.0
        gy = (self.g_z[yu] - self.g_z[yd]) / 2.0
        return np.degrees(np.arctan(np.hypot(gx, gy) / self.cell_m[wk]))

    # ------------------------------------------------------------------ 접촉

    def medium_code(self) -> np.ndarray:
        """0 땅 · 1 물속 · 2 하늘."""
        return np.where(self.airborne, 2, np.where(self.swimming, 1, 0))

    def _contact(self):
        r = self.rules
        p = self.p
        K, Sl = self.K, self.S
        al = self.alive.reshape(K, Sl)
        x = self.x.reshape(K, Sl)
        y = self.y.reshape(K, Sl)
        dx = x[:, None, :] - x[:, :, None]           # [k, i(공격), j(대상)] = j − i
        dy = y[:, None, :] - y[:, :, None]
        dist = np.hypot(dx, dy)
        hx = self.hx.reshape(K, Sl)[:, :, None]
        hy = self.hy.reshape(K, Sl)[:, :, None]
        cosf = (hx * dx + hy * dy) / np.maximum(dist, 1e-6)
        vx = self.vx.reshape(K, Sl)[:, :, None]
        vy = self.vy.reshape(K, Sl)[:, :, None]
        appr = (vx * dx + vy * dy) / np.maximum(dist, 1e-6)
        mass = p["mass_kg"].reshape(K, Sl)
        kr = p["kill_mass_ratio"].reshape(K, Sl)
        sp = self.sp.reshape(K, Sl)
        med = self.medium_code().reshape(K, Sl)
        zz = self.z.reshape(K, Sl)
        rad = p["radius_m"].reshape(K, Sl)
        # 같은 매체에서만. 하늘 공격자는 급강하로 대상 가까이 내려왔을 때 땅·수면 대상에 닿는다.
        dive_touch = (med[:, :, None] == 2) & (zz[:, :, None] <= rad[:, :, None] * r.dive_contact_k) & (med[:, None, :] != 2)
        same_med = (med[:, :, None] == med[:, None, :]) | dive_touch
        c = self.cidx(self.wk, self.x, self.y)
        # 은신처 안 몸은 덤불 속으로 들어갈 만큼 작은 몸만 물 수 있다 (안에 있음의 효과 — 행동과 상관없음, R9 S′ 와 같음)
        sheltered = (self.g_shelter[c] & ~self.airborne).reshape(K, Sl)
        small = rad <= r.shelter_bite_radius_m
        can = (al[:, :, None] & al[:, None, :] & (sp[:, :, None] != sp[:, None, :])
               & (kr[:, :, None] > 0) & (mass[:, None, :] <= mass[:, :, None] * kr[:, :, None])
               & (dist <= p["reach_m"].reshape(K, Sl)[:, :, None] + rad[:, None, :]) & (cosf >= r.bite_cone_cos)
               & (appr > r.approach_min_mps) & same_med & (~sheltered[:, None, :] | small[:, :, None])
               & (self.attack_cd.reshape(K, Sl)[:, :, None] <= 0))
        if not can.any():
            self.attack_cd = np.maximum(self.attack_cd - C.STEP_S, 0.0)
            return
        dist_m = np.where(can, dist, np.inf)
        target = np.argmin(dist_m, axis=2)
        has = np.isfinite(dist_m.min(axis=2))
        order = self.rng.permutation(Sl)
        for k in range(K):
            taken = set()
            for i in order:
                if not has[k, i]:
                    continue
                tj = int(target[k, i])
                if tj in taken or not self.alive[k * Sl + tj]:
                    continue
                gi, gj = k * Sl + i, k * Sl + tj
                taken.add(tj)
                self.attack_cd[gi] = p["attack_cd_s"][gi]
                dmg = float(np.clip(r.bite_damage_k * p["mass_kg"][gi] * p["kill_mass_ratio"][gi] / p["mass_kg"][gj], 0.2, 1.0))
                # 반격: 대상 앞쪽에 공격자가 있고 대상이 아직 버틸 때
                bx, by = self.x[gi] - self.x[gj], self.y[gi] - self.y[gj]
                bd = max(math.hypot(bx, by), 1e-6)
                front = (self.hx[gj] * bx + self.hy[gj] * by) / bd >= r.counter_cone_cos
                countered = (p["defense"][gj] > 0 and front and self.hp[gj] >= r.counter_hp_min
                             and bd <= p["counter_reach_m"][gj] + p["radius_m"][gi])
                if countered:
                    self.hp[gi] -= p["defense"][gj] / 100.0
                    self.attack_cd[gi] = max(self.attack_cd[gi], r.counter_cd_s)
                    dmg *= 0.5
                self.hp[gj] -= dmg
                self.events["bites"].append((self.t, int(k), int(self.uid[gi]), int(self.uid[gj]), dmg, bool(countered)))
                if self.hp[gj] <= 0:
                    self._kill(gj, "bitten", killer=gi)
                if self.hp[gi] <= 0:
                    self._kill(gi, "counter", killer=gj)
        self.attack_cd = np.maximum(self.attack_cd - C.STEP_S, 0.0)

    # ------------------------------------------------------------------ 먹기·대사

    def _eat(self):
        p = self.p
        eating = self.alive & (self.actions == C.A_EAT)
        if not eating.any():
            return
        idx = np.nonzero(eating)[0]
        c = self.cidx(self.wk[idx], self.x[idx], self.y[idx])
        want = p["rate_per_s"][idx] * C.STEP_S
        diet = p["diet"][idx]
        in_water = self.swimming[idx]
        near_surface = self.z[idx] >= self.surface_at(c) - 2 * self.clearance(idx)
        # 먹을 수 있는 칸 (매체): 물먹이는 헤엄 몸, 떠내려온 것은 수면 가까이, 땅 먹이는 물 밖(걷기 깊이 안)·나는 몸은 땅에 있을 때
        on_land = ~in_water & ~self.airborne[idx]
        reach = np.zeros((len(idx), len(T.FOOD_KINDS)), bool)
        for kname, fi in FOOD_INDEX.items():
            if kname in ("aquatic",):
                reach[:, fi] = in_water
            elif kname == "drift":
                reach[:, fi] = in_water & near_surface
            elif kname == "insects":
                reach[:, fi] = on_land | in_water
            else:
                reach[:, fi] = on_land
        avail = self.g_food[:, c].T * reach                       # (n, 8)
        dk = np.array([diet[:, S.DIET_KEYS.index(k)] for k in T.FOOD_KINDS]).T
        score = avail * dk
        best = np.argmax(score, axis=1)
        has = score[np.arange(len(idx)), best] > 1e-6
        # 칸마다 몫 나누기 (R8 꼴)
        demand = np.where(has, want, 0.0)
        key = best * self.g_z.size + c
        uniq, inv = np.unique(key, return_inverse=True)
        tot = np.bincount(inv, weights=demand)
        fi_u, c_u = uniq // self.g_z.size, uniq % self.g_z.size
        food_u = self.g_food[fi_u, c_u]
        taken_u = np.minimum(tot, food_u)
        frac = np.where(tot > 0, taken_u / np.maximum(tot, 1e-12), 0.0)
        got = demand * frac[inv]
        np.subtract.at(self.g_food, (fi_u, c_u), taken_u)
        gain = got * p["energy_per_unit"][idx] * dk[np.arange(len(idx)), best]
        # 고기: 가까운 사체 (1 m), 고기·사체를 먹는 몸
        meat_w = diet[:, S.DIET_KEYS.index("carrion")] + diet[:, S.DIET_KEYS.index("meat")]
        cw = self.carcass["wk"]
        if (cw >= 0).any() and (meat_w > 0).any():
            for n, i in enumerate(idx):
                if meat_w[n] <= 0 or has[n] and score[n, best[n]] > 0:
                    continue
                cand = np.nonzero((cw == self.wk[i]) & (self.carcass["meat"] > 0) & (self.carcass["kin"] != self.sp[i]))[0]
                if len(cand) == 0:
                    continue
                dd = np.hypot(self.carcass["x"][cand] - self.x[i], self.carcass["y"][cand] - self.y[i])
                m = int(np.argmin(dd))
                if dd[m] > 1.0 + self.p["radius_m"][i]:
                    continue
                ci = cand[m]
                eat = min(want[n] * 4.0, self.carcass["meat"][ci])
                self.carcass["meat"][ci] -= eat
                gain[n] += eat * p["energy_per_unit"][i] * max(diet[n, S.DIET_KEYS.index("carrion")], diet[n, S.DIET_KEYS.index("meat")])
        self._gain = np.zeros(self.N)
        self._gain[idx] = gain

    def _metabolism(self):
        r = self.rules
        p = self.p
        al = self.alive
        gain = self._gain
        self._gain = np.zeros(self.N)
        _, gait = self._dir_of_action(self.actions)
        fast = (gait == 2) | (self.actions == C.A_DIVE)
        mult = np.where(fast, p["run_cost"], 1.0)
        mult = np.where(self.swimming, mult * p["swim_cost"], mult)
        mult = np.where(self.airborne, mult * p["fly_cost"], mult)
        e = self.E - p["drain_per_step"] * mult + gain
        refill = np.where(self.E >= 0.7, r.reserve_refill * gain, 0.0)
        cap_e = np.maximum(p["reserve_days"] * C.DAY_STEPS * p["drain_per_step"], 1e-9)
        e = e - refill
        self.R = np.clip(self.R + refill / cap_e, 0.0, 1.0)
        need = np.clip(r.reserve_draw_below - e, 0.0, None)
        draw = np.minimum(need, self.R * cap_e)
        e = e + draw
        self.R = np.clip(self.R - draw / cap_e, 0.0, 1.0)
        self.E = np.where(al, np.minimum(e, 1.0), self.E)
        # 지구력
        use = fast | self.airborne & (self.actions == C.A_UP)
        self.stam = np.where(use, self.stam - C.STEP_S / np.maximum(p["stamina_s"], 1e-3),
                             self.stam + C.STEP_S / np.maximum(p["stamina_recover_s"], 1e-3))
        self.stam = np.clip(self.stam, 0.0, 1.0)
        # 체력 회복
        self.hp = np.where(al, np.minimum(self.hp + 0.02 * C.STEP_S / 10.0, 1.0), self.hp)
        # 숨 (물고기: 헤엄 깊이가 모자라면 줄어듦)
        c = self.cidx(self.wk, self.x, self.y)
        short = p["needs_water"] & (self.depth_at(c) < 2 * self.clearance(np.arange(self.N)))
        self.breath = np.where(short, self.breath - C.STEP_S / r.breath_s, np.minimum(self.breath + C.STEP_S / r.breath_s, 1.0))
        self.age_days = np.where(al, self.age_days + 1.0 / C.DAY_STEPS, self.age_days)

    # ------------------------------------------------------------------ 생애

    def _life(self):
        r = self.rules
        p = self.p
        al = self.alive
        adult = al & (self.age_days >= p["maturity_days"])
        self.birth_wait = np.maximum(self.birth_wait - 1.0 / C.DAY_STEPS, 0.0)
        # 짝: 어른 암컷이 같은 종 어른 수컷 가까이(반지름 합 + 1 m)이고 둘 다 힘이 있으면 새끼를 밴다
        fem = adult & ~self.sex & (self.preg_left <= 0) & (self.birth_wait <= 0) & (self.E >= r.mate_e_min)
        if fem.any():
            male = adult & self.sex & (self.E >= r.mate_e_min)
            for i in np.nonzero(fem)[0]:
                k = self.wk[i]
                lo, hi = k * self.S, (k + 1) * self.S
                cand = np.nonzero(male[lo:hi] & (self.sp[lo:hi] == self.sp[i]))[0] + lo
                if len(cand) == 0:
                    continue
                d = np.hypot(self.x[cand] - self.x[i], self.y[cand] - self.y[i])
                m = int(np.argmin(d))
                if d[m] <= p["radius_m"][i] + p["radius_m"][cand[m]] + 1.0:
                    self.pregnant[i] = True
                    self.preg_left[i] = max(p["gestation_days"][i], 1.0 / C.DAY_STEPS)
                    self._father[int(i)] = int(cand[m])
        # 낳기: 밴 기간이 끝나면 한 번. 힘이 모자라면 새끼 없이 끝난다
        self.preg_left = np.where(self.pregnant, self.preg_left - 1.0 / C.DAY_STEPS, 0.0)
        ready = al & self.pregnant & (self.preg_left <= 0)
        self.pregnant &= ~ready
        for i in np.nonzero(ready)[0]:
            if self.E[i] < r.birth_e_min:
                self._father.pop(int(i), None)
                continue
            k = int(self.wk[i])
            si = int(self.sp[i])
            lo, hi = k * self.S, (k + 1) * self.S
            same = np.nonzero(self.sp[lo:hi] == si)[0] + lo
            free = same[~self.alive[same] & (self.dead_wait[same] == 0)]
            n_alive = int(self.alive[same].sum())
            litter = int(max(1, round(p["litter"][i])))
            room = max(0, self.cap[k][si] - n_alive)
            born = 0
            for f_ in free[:min(litter, room)]:
                if self._spawn(f_, adult_frac=0.0, near=(self.x[i], self.y[i])):
                    self.age_days[f_] = 0.0
                    self.E[f_] = 0.6
                    born += 1
            if born:
                self.E[i] -= r.birth_cost
                self.births_step[i] += born
                fa = self._father.pop(int(i), None)
                if fa is not None and self.alive[fa]:
                    self.births_step[fa] += born
                self.birth_wait[i] = max(p["gestation_days"][i], 0.1)
                self.events["births"].append((self.t, k, int(self.uid[i]), born))

    # ------------------------------------------------------------------ 죽음·사체·먹이·되살리기

    def _kill(self, i, cause, killer=None):
        if not self.alive[i]:
            return
        self.alive[i] = False
        self.pregnant[i] = False
        self._father.pop(int(i), None)
        self.events["deaths"].append((self.t, int(self.wk[i]), int(self.uid[i]), int(self.sp[i]), cause,
                                      None if killer is None else int(self.uid[killer])))
        k = int(self.wk[i])
        base = k * self.rules.carcass_slots
        slots = np.arange(base, base + self.rules.carcass_slots)
        free = slots[self.carcass["meat"][slots] <= 0]
        ci = int(free[0]) if len(free) else int(slots[np.argmax(self.carcass["age"][slots])])
        self.carcass["wk"][ci] = k
        self.carcass["x"][ci], self.carcass["y"][ci], self.carcass["z"][ci] = self.x[i], self.y[i], 0.0
        self.carcass["meat"][ci] = self.p["mass_kg"][i] * self.rules.carcass_meat_per_kg
        self.carcass["age"][ci] = 0.0
        self.carcass["kin"][ci] = self.sp[i]
        self.dead_wait[i] = self.respawn_wait[i]

    def _deaths(self):
        starve = self.alive & (self.E <= 0.0) & (self.R <= 0.0)
        for i in np.nonzero(starve)[0]:
            self._kill(i, "starved")
        choke = self.alive & (self.breath <= 0.0)
        for i in np.nonzero(choke)[0]:
            self._kill(i, "out_of_water")
        hurt = self.alive & (self.hp <= 0.0)
        for i in np.nonzero(hurt)[0]:
            self._kill(i, "wounds")

    def _regrow(self):
        dt = C.STEP_S
        self.g_food = np.clip(self.g_food + (self.g_regen - self.g_dry) * dt, 0.0, self.g_cap)
        self.carcass["age"] += dt
        old = self.carcass["age"] > self.rules.carcass_life_s
        self.carcass["meat"][old] = 0.0

    def _respawn(self):
        wait = ~self.alive & (self.sp >= 0) & (self.dead_wait > 0)
        self.dead_wait = np.where(wait, self.dead_wait - 1, self.dead_wait)
        ready = ~self.alive & (self.sp >= 0) & (self.dead_wait == 0) & (self.uid > 0)
        for i in np.nonzero(ready)[0]:
            k, si = int(self.wk[i]), int(self.sp[i])
            lo, hi = k * self.S, (k + 1) * self.S
            n_alive = int((self.alive[lo:hi] & (self.sp[lo:hi] == si)).sum())
            if n_alive < self.cap[k][si]:
                self._spawn(i)
