"""R8 파일럿 세계 — 위험을 스스로 배우는 사슴 (설계 `AdaptiveEcosystem/Docs/RL_Policy/RL_R8_LEARN_DANGER_DESIGN.md` 3~6절).

기존 `world.py` 와 따로 선 새 세계다(설계 3절 — 기존 세계는 한 줄도 바꾸지 않는다). 값·식은 기존 세계에서 옮겼고 출처는 설계 표에 있다.

한 객체가 세계 K 개를 한 배열 묶음으로 돌린다(K = len(seeds), 사슴 (K, N), 동물 칸 (K, A)). 세계마다 난수 갈래가 따로라
세계 하나의 궤적은 함께 도는 다른 세계와 무관하다(같은 시드 = 같은 세계, 묶음 크기·순서와 무관). 학습 VecEnv(`r8_vec_env.py`)는
K = 32, 평가는 K = 100 으로 한 번에 돈다.

무엇이 R7e 와 다른가 (설계 3-7)
  - 위협 이름표가 없다. 관측 함수(`_observe`·`_perceive`)는 동물의 종류 배열(`kind`)을 읽지 않는다 — `present`(칸이 차 있음)·위치·
    지난 스텝 이동·머리 방향·크기만 읽는다. 시험 `tests/test_r8.py` 가 종류만 맞바꾼 세계의 관측이 비트 단위로 같음을 지킨다.
  - 도주 반사·경계 걷기·쉬는 늑대 피하기·FLEE 방향 규칙·마스크가 없다. 행동 11 개를 두뇌가 2 스텝마다 고른다.
  - 보상 = 0.01 + (E_new − E_prev) + 10 × 번식 − 10 × 죽음 (R7 과 같은 식, 위험 힌트 없음).

1 단위 = 2 m, 1 스텝 = 2/15 초. 난수 갈래(`default_rng([시드, 구분값])`): 세계 값·먹이 지도·배치·동물 움직임·다시 남·평가 정책·곰.
동물 움직임 갈래는 스텝마다 세계마다 (늑대 칸 + 짐승 칸, 5) 균등 수를 늘 같은 개수 뽑는다 — 사슴 행동과 무관하게 소비가 같아
짐승의 궤적은 정책과 무관하다(평가 짝 비교).

행동 (설계 5절, 결정 1 번 = 2 스텝)
  0 EAT     지금 셀 먹이 ≥ eat_min 이면 서서 먹고(섭식 1.0), 아니면 n(0.83 먹이 기울기 + 0.71 무리 + 1.35 분리) 쪽으로 걸으며 먹는다(0.5).
            탐지 반경 × head_down.
  1~8 RUN   결정 때 머리 방향에서 왼쪽(반시계)으로 (k − 1) × 45° 돌린 방향으로 뛰기. 섭식 0, 대사 2.5 배. 벽에서 미끄러진다.
  9 SHELTER 가장 가까운(가장자리 거리) 은신처 중심 쪽으로 뛰기. 안이면 서서 숨는다(섭식 0, 대사 정지).
  10 WATCH  서서 고개를 든다(섭식 0, 대사 정지, 탐지 반경 × 1).
  머리 방향 = 움직이면 실제 이동 방향, 서 있으면 그대로.

한 스텝 순서 (`_phys`)
  1) 사슴 이동(행동 → 속도, 약하면 × weak_speed, 벽 안으로 자름)  2) 동물 이동(늑대: 표적 고르기·추격/잠행/덮침/탈진/먹기/배회,
  짐승: 돌아다님/풀 뜯기/내달리기, 곰: 서 있기/덮침/먹기) — 벽에서 튕김, 은신처 원(r + margin) 밖으로 밀어냄  3) 잡기(늑대·곰, 칸 차례)
  4) 섭식·대사·지방 비축  5) 보상 에너지 항·번식  6) 죽음(잡힘·굶음)  7) 먹이 재생  8) 다시 남  9) 동물 느낌·다가옴 기억 갱신

숨은 기록(관측에 넣지 않는다): 잡은 동물 종류, 결정마다 '가장 가까운 느낀 동물'의 종류·거리 띠·도망 여부(`flee_cnt`),
`record_samples` 면 평가용 표본 줄(`samples`).
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Sequence

import numpy as np
import yaml

EPS = 1e-9

# 난수 갈래 구분값 (다른 세계의 구분값과 겹치지 않게 고른 수)
TAG_PARAM, TAG_FOOD, TAG_PLACE, TAG_ANIM, TAG_RESP, TAG_POL, TAG_BEAR = 8101, 8102, 8103, 8104, 8105, 8106, 8107

# 행동 번호
EAT, SHELTER, WATCH = 0, 9, 10
RUN_FIRST, RUN_LAST = 1, 8
N_ACTIONS = 11
ACTION_NAMES = ("EAT",) + tuple(f"RUN_{j * 45}" for j in range(8)) + ("SHELTER", "WATCH")

# 동물 종류 (숨은 값 — 관측 함수는 읽지 않는다)
K_NONE, K_WOLF, K_BEAST, K_BEAR = 0, 1, 2, 3
KIND_NAMES = {K_WOLF: "wolf", K_BEAST: "beast", K_BEAR: "bear"}
# 짐승 상태
B_ROAM, B_GRAZE, B_DASH = 0, 1, 2

# 걸음 번호 (정지·걷기·뛰기)
G_STOP, G_WALK, G_RUN = 0, 1, 2

OBS_SELF_NAMES = ("energy", "reserve", "food_density", "food_here", "in_shelter", "shelter_x", "shelter_y", "shelter_edge",
                  "free_0", "free_1", "free_2", "free_3", "free_4", "free_5", "free_6", "free_7", "own_speed")
OBS_ANIMAL_FIELDS = ("present", "rel_x", "rel_y", "dist", "vel_x", "vel_y", "approach", "approach_mem", "facing", "size", "heard_only")
OBS_KIN_NAMES = ("kin_count", "kin_run_frac", "kin_flow_x", "kin_flow_y")
N_SLOTS = 4
OBS_NAMES = (OBS_SELF_NAMES + tuple(f"a{j}_{f}" for j in range(N_SLOTS) for f in OBS_ANIMAL_FIELDS) + OBS_KIN_NAMES)
OBS_DIM = len(OBS_NAMES)            # 65
A0 = len(OBS_SELF_NAMES)            # 동물 칸 시작 열 (17)
NA = len(OBS_ANIMAL_FIELDS)         # 동물 칸 하나의 열 수 (11)
KIN0 = A0 + N_SLOTS * NA            # 동족 칸 시작 열 (61)

REQUIRED = {
    "world": ("size", "n_deer", "covers", "cover_r", "decision_steps"),
    "food": ("cell", "patch_blur", "patch_threshold", "regen_base", "regen_mult", "cover_mult", "eat_rate", "energy_per_unit",
             "grad_blur", "density_blur"),
    "deer": ("speed", "gait_speed", "gait_eat", "gait_drain", "energy_drain", "init_energy", "max_energy", "repro_threshold",
             "repro_cd", "reserve_cap", "reserve_init", "refill_e", "refill_frac", "weak_e", "weak_speed", "eat_min",
             "graze_forage", "graze_cohesion", "sep_weight", "sep_radius", "respawn_r", "respawn_candidates", "start_r"),
    "sense": ("see_r", "fov_deg", "head_down", "hear_r_quiet", "hear_r_loud", "hear_s_silent", "hear_s_quiet", "hear_s_loud",
              "pos_norm", "vel_norm", "mem_keep", "mem_gain", "mem_decay", "size_norm", "kin_norm", "run_frac_speed",
              "free_norm", "edge_norm", "speed_norm", "flow_norm"),
    "animals": ("size", "roam_speed", "turn", "shelter_margin", "min_gap"),
    "wolves": ("count", "speed_mult", "stalk_frac", "view_r", "fov_deg", "catch_r", "eat_steps", "stalk_near", "stalk_speed",
               "pounce_speed", "pounce_steps", "tired_steps", "tired_speed"),
    "beasts": ("count", "next_probs", "roam_steps", "graze_steps", "dash_speed", "dash_steps"),
    "bears": ("count", "size", "trigger_r", "pounce_speed", "pounce_steps", "catch_r", "eat_steps", "start_r"),
    "reward": ("alive", "energy", "repro", "death"),
}


# --------------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------------- #

def _deep_merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def check_r8_config(cfg: dict) -> dict:
    """필수 키 검사와 몇 가지 범위 검사. 기본값은 없다(설정 파일에 다 적는다)."""
    for sec, keys in REQUIRED.items():
        if sec not in cfg or not isinstance(cfg[sec], dict):
            raise ValueError(f"R8 설정에 '{sec}' 블록이 없다")
        miss = [k for k in keys if k not in cfg[sec]]
        if miss:
            raise ValueError(f"R8 설정 '{sec}' 에 키 {miss} 가 없다")
    w, b = cfg["wolves"]["count"], cfg["beasts"]["count"]
    if not (0 <= int(w[0]) <= int(w[1])) or not (0 <= int(b[0]) <= int(b[1])):
        raise ValueError(f"wolves.count·beasts.count 는 0 ≤ 하 ≤ 상: {w}, {b}")
    if int(cfg["bears"]["count"]) < 0:
        raise ValueError("bears.count 는 0 이상")
    if int(cfg["world"]["decision_steps"]) < 1:
        raise ValueError("world.decision_steps 는 1 이상")
    p = np.asarray(cfg["beasts"]["next_probs"], dtype=float)
    if p.shape != (3,) or (p < 0).any() or abs(p.sum() - 1.0) > 1e-9:
        raise ValueError(f"beasts.next_probs 는 [풀 뜯기, 내달리기, 돌아다님] 확률 셋(합 1): {p}")
    return cfg


def load_r8_config(path) -> dict:
    """R8 설정 YAML. 최상위 `inherit: 파일` 이 있으면 그 파일(같은 폴더 기준)을 먼저 읽고 이 파일 값으로 덮는다."""
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "inherit" in raw:
        base = load_r8_config(p.parent / raw.pop("inherit"))
        base.pop("_path", None)
        raw = _deep_merge(base, raw)
    raw["_path"] = str(p)
    return check_r8_config(raw)


def override(cfg: dict, patch: dict) -> dict:
    """설정 사본에 덮어쓰기(평가의 곰 시험 등)."""
    return check_r8_config(_deep_merge(cfg, patch))


# --------------------------------------------------------------------------- #
# 작은 도움 함수 (마지막 축이 (x, y))
# --------------------------------------------------------------------------- #

def _norm(v: np.ndarray) -> np.ndarray:
    n = np.sqrt((v * v).sum(-1, keepdims=True))
    return np.divide(v, n, out=np.zeros_like(v), where=n > EPS)


def _rot(v: np.ndarray, ang) -> np.ndarray:
    """v 를 반시계로 ang 라디안 돌린다(ang 은 스칼라 또는 v[..., 0] 과 같은 꼴)."""
    c, s = np.cos(ang), np.sin(ang)
    return np.stack([c * v[..., 0] - s * v[..., 1], s * v[..., 0] + c * v[..., 1]], -1)


def _box_mean(F: np.ndarray, br: int) -> np.ndarray:
    """(K, G, G) 격자의 반경 br 셀 정사각 평균(경계는 잘린 창의 실제 면적으로 나눈다 — world._box_mean 과 같은 식)."""
    K, G, _ = F.shape
    sat = np.zeros((K, G + 1, G + 1))
    np.cumsum(np.cumsum(F, 1), 2, out=sat[:, 1:, 1:])
    i = np.arange(G)
    r0, r1 = np.clip(i - br, 0, G), np.clip(i + br + 1, 0, G)
    box = (sat[:, r1[:, None], r1[None, :]] - sat[:, r0[:, None], r1[None, :]]
           - sat[:, r1[:, None], r0[None, :]] + sat[:, r0[:, None], r0[None, :]])
    return box / ((r1 - r0)[:, None] * (r1 - r0)[None, :])


def hear_radius(s: np.ndarray, sense: dict) -> np.ndarray:
    """지난 스텝 속력 s(× 사슴 뛰기 속력 0.6 으로 나눈 값)의 소리 반경 (설계 4-1). 종류·내부 상태와 무관하다."""
    t = np.clip((s - sense["hear_s_quiet"]) / (sense["hear_s_loud"] - sense["hear_s_quiet"]), 0.0, 1.0)
    return np.where(s < sense["hear_s_silent"], 0.0, sense["hear_r_quiet"] + (sense["hear_r_loud"] - sense["hear_r_quiet"]) * t)


# --------------------------------------------------------------------------- #
# 세계
# --------------------------------------------------------------------------- #

class R8World:
    """세계 K 개의 묶음. `step(actions (K, N) int)` = 결정 1 번(decision_steps 스텝) → (obs (K, N, 65), rew (K, N), done (K, N))."""

    def __init__(self, cfg: dict, seeds: Sequence[int], record_samples: bool = False):
        self.cfg = cfg
        w, fd, d, s = cfg["world"], cfg["food"], cfg["deer"], cfg["sense"]
        self.size = float(w["size"])
        self.N = int(w["n_deer"])
        self.D = int(w["decision_steps"])
        self.cov_c = np.asarray(w["covers"], dtype=np.float64).reshape(-1, 2)
        self.cov_r = float(w["cover_r"])
        self.unit = float(d["speed"])                              # 사슴 뛰기 속력 (단위/스텝) — 동물 속력 배수의 기준
        self.maxW = int(cfg["wolves"]["count"][1])
        self.maxB = int(cfg["beasts"]["count"][1])
        self.nBear = int(cfg["bears"]["count"])
        self.AW = self.maxW + self.maxB                            # 움직임 난수를 늘 같은 개수 뽑는 칸 (늑대 + 짐승)
        self.A = max(self.AW + self.nBear, N_SLOTS)                # 칸이 관측 칸 수보다 적으면 빈 칸(present 거짓)으로 채운다
        self.G = int(math.ceil(self.size / float(fd["cell"])))
        cc = (np.arange(self.G) + 0.5) * float(fd["cell"])
        cx, cy = np.meshgrid(cc, cc)                               # (G, G): [iy, ix]
        cov = np.zeros((self.G, self.G), dtype=bool)
        for c in self.cov_c:
            cov |= (cx - c[0]) ** 2 + (cy - c[1]) ** 2 <= self.cov_r ** 2
        self.cover_cell = cov
        self.fov_cos = math.cos(math.radians(float(s["fov_deg"]) / 2.0))
        self.wolf_fov_cos = math.cos(math.radians(float(cfg["wolves"]["fov_deg"]) / 2.0))
        self.gait_speed = np.asarray(d["gait_speed"], dtype=np.float64) * self.unit
        self.gait_eat = np.asarray(d["gait_eat"], dtype=np.float64)
        self.gait_drain = np.asarray(d["gait_drain"], dtype=np.float64)
        self.run_angles = np.arange(8) * (math.pi / 4.0)           # 행동 1~8 / free_0~7 의 방향 (머리에서 반시계)
        self.record_samples = bool(record_samples)
        self.step_hook = None
        self.K = 0
        self._alloc(len(seeds))
        for k, sd in enumerate(seeds):
            self._init_world(k, int(sd))
        self.reset_stats()
        self._perceive(update_mem=False)
        self.obs = self._observe()

    # ------------------------------------------------------------------ #
    # 만들기
    # ------------------------------------------------------------------ #

    def _alloc(self, K: int) -> None:
        N, A, G = self.N, self.A, self.G
        self.K = K
        self.seeds = np.zeros(K, dtype=np.int64)
        # 세계 값
        self.M = np.zeros(K, dtype=np.int64)
        self.H = np.zeros(K, dtype=np.int64)
        self.wolf_speed = np.zeros(K)
        self.regen_mult = np.zeros(K)
        # 먹이
        self.food_cap = np.zeros((K, G, G))
        self.food = np.zeros((K, G, G))
        self.regen = np.zeros((K, G, G))
        # 사슴
        self.pos = np.zeros((K, N, 2))
        self.head = np.zeros((K, N, 2))
        self.disp = np.zeros((K, N, 2))
        self.E = np.zeros((K, N))
        self.R = np.zeros((K, N))
        self.cd = np.zeros((K, N), dtype=np.int64)
        self.act = np.full((K, N), WATCH, dtype=np.int64)
        self.prev_act = np.full((K, N), WATCH, dtype=np.int64)
        self.run_dir = np.zeros((K, N, 2))
        self.mem = np.zeros((K, N, A))
        # 동물 (칸: 늑대 maxW · 짐승 maxB · 곰 nBear)
        self.kind = np.zeros((K, A), dtype=np.int8)                 # 숨은 값
        self.present = np.zeros((K, A), dtype=bool)                 # 관측이 읽는 '칸이 차 있음'
        self.apos = np.full((K, A, 2), -1000.0)
        self.ahead = np.zeros((K, A, 2))
        self.ahead[..., 0] = 1.0
        self.adisp = np.zeros((K, A, 2))
        self.asize = np.zeros((K, A))
        self.aroam = np.zeros((K, A))                               # 배회 속력 (단위/스텝)
        self.stalker = np.zeros((K, A), dtype=bool)
        self.eat_left = np.zeros((K, A), dtype=np.int64)
        self.pounce_left = np.zeros((K, A), dtype=np.int64)
        self.tired_left = np.zeros((K, A), dtype=np.int64)
        self.target = np.full((K, A), -1, dtype=np.int64)           # 이번 스텝 표적 (늑대·곰)
        self.lock = np.full((K, A), -1, dtype=np.int64)             # 덮침 표적 (잠행 늑대·곰)
        self.bstate = np.zeros((K, A), dtype=np.int64)
        self.bleft = np.zeros((K, A), dtype=np.int64)
        self.bdir = np.zeros((K, A, 2))
        self.bspeed = np.zeros((K, A))
        self.rng_anim: list[np.random.Generator] = [None] * K
        self.rng_resp: list[np.random.Generator] = [None] * K
        self.rng_pol: list[np.random.Generator] = [None] * K
        self.t = np.zeros(K, dtype=np.int64)                        # 세계마다 스텝 수

    def _outside_cover(self, p: np.ndarray, margin: float) -> np.ndarray:
        d = np.sqrt(((p[..., None, :] - self.cov_c) ** 2).sum(-1))
        return (d > self.cov_r + margin).all(-1)

    def _init_world(self, k: int, seed: int) -> None:
        """세계 k 를 시드 seed 로 새로 만든다(먹이 지도·세계 값·배치·상태 모두)."""
        cfg = self.cfg
        fd, d, an, wl, bs, br = cfg["food"], cfg["deer"], cfg["animals"], cfg["wolves"], cfg["beasts"], cfg["bears"]
        size, N, G = self.size, self.N, self.G
        self.seeds[k] = seed
        self.t[k] = 0
        # --- 세계 값 (설계 3-6) — 늘 같은 개수를 뽑는다 ---
        gp = np.random.default_rng([seed, TAG_PARAM])
        M = int(gp.integers(int(wl["count"][0]), int(wl["count"][1]) + 1))
        wsp = float(gp.uniform(*wl["speed_mult"]))
        H = int(gp.integers(int(bs["count"][0]), int(bs["count"][1]) + 1))
        rgm = float(gp.uniform(*fd["regen_mult"]))
        stalk = gp.random(max(self.maxW, 1))[: self.maxW] < float(wl["stalk_frac"])
        sizes = gp.uniform(an["size"][0], an["size"][1], max(self.AW, 1))[: self.AW]
        roams = gp.uniform(an["roam_speed"][0], an["roam_speed"][1], max(self.AW, 1))[: self.AW] * self.unit
        self.M[k], self.H[k], self.wolf_speed[k], self.regen_mult[k] = M, H, wsp, rgm
        # --- 먹이 (설계 3-2, world._build_world 의 v1 패치) ---
        gf = np.random.default_rng([seed, TAG_FOOD])
        m = _box_mean(gf.random((1, G, G)), max(1, int(fd["patch_blur"])))[0]
        m = (m - m.min()) / max(m.max() - m.min(), EPS)
        t = float(fd["patch_threshold"])
        cap = np.clip((m - t) / (1.0 - t), 0.0, 1.0)
        cm = float(fd["cover_mult"])
        cap = np.where(self.cover_cell, cap * cm, cap)
        self.food_cap[k] = cap
        self.food[k] = cap
        self.regen[k] = float(fd["regen_base"]) * rgm * np.where(self.cover_cell, cm, 1.0)
        # --- 동물 칸 ---
        A = self.A
        self.kind[k] = K_NONE
        self.present[k] = False
        self.apos[k] = -1000.0
        self.ahead[k] = 0.0
        self.ahead[k, :, 0] = 1.0
        self.adisp[k] = 0.0
        self.asize[k] = 0.0
        self.aroam[k] = 0.0
        self.stalker[k] = False
        for arr in (self.eat_left, self.pounce_left, self.tired_left, self.bstate, self.bleft):
            arr[k] = 0
        self.target[k] = -1
        self.lock[k] = -1
        self.bdir[k] = 0.0
        self.bspeed[k] = 0.0
        act_slots = [a for a in range(self.maxW) if a < M] + [self.maxW + h for h in range(self.maxB) if h < H]
        for a in act_slots:
            self.kind[k, a] = K_WOLF if a < self.maxW else K_BEAST
            self.present[k, a] = True
        if self.AW:
            self.asize[k, : self.AW] = np.where(self.present[k, : self.AW], sizes, 0.0)
            self.aroam[k, : self.AW] = np.where(self.present[k, : self.AW], roams, 0.0)
        self.stalker[k, : self.maxW] = stalk & self.present[k, : self.maxW]
        # --- 배치 (설계 3-6) ---
        gl = np.random.default_rng([seed, TAG_PLACE])
        mg = float(an["shelter_margin"])
        placed = []
        for a in act_slots:
            best, best_d = None, -1.0
            for _ in range(200):
                c = gl.uniform(0.0, size, 2)
                if not self._outside_cover(c, mg):
                    continue
                dmin = min((float(np.hypot(*(c - q))) for q in placed), default=1e9)
                if dmin >= float(an["min_gap"]):
                    best = c
                    break
                if dmin > best_d:
                    best, best_d = c, dmin
            if best is None:
                best = np.array([1.0, 1.0])
            placed.append(best)
            self.apos[k, a] = best
            ang = gl.uniform(0.0, 2 * math.pi)
            self.ahead[k, a] = (math.cos(ang), math.sin(ang))
        # 짐승 첫 상태: 돌아다님, 길이 U[roam_steps] (짐승 칸마다 늘 하나 뽑는다)
        rl = gl.uniform(bs["roam_steps"][0], bs["roam_steps"][1], max(self.maxB, 1))[: self.maxB]
        for h in range(self.maxB):
            a = self.maxW + h
            self.bstate[k, a] = B_ROAM
            self.bleft[k, a] = int(round(rl[h])) if self.present[k, a] else 0
        apts = np.asarray(placed).reshape(-1, 2)
        for i in range(N):
            best, best_d = None, -1.0
            for _ in range(200):
                c = gl.uniform(0.0, size, 2)
                if not self._outside_cover(c, 0.0):
                    continue
                dmin = float(np.sqrt(((apts - c) ** 2).sum(1)).min()) if len(apts) else 1e9
                if dmin >= float(d["start_r"]):
                    best = c
                    break
                if dmin > best_d:
                    best, best_d = c, dmin
            if best is None:
                best = np.array([size / 2, size / 2])
            self.pos[k, i] = best
            ang = gl.uniform(0.0, 2 * math.pi)
            self.head[k, i] = (math.cos(ang), math.sin(ang))
        # --- 곰 (설계 10절, 기본 0 마리) — 따로 갈래라 곰을 더해도 다른 배치가 그대로다 ---
        if self.nBear:
            gb = np.random.default_rng([seed, TAG_BEAR])
            for j in range(self.nBear):
                a = self.AW + j
                best, best_d = None, -1.0
                for _ in range(400):
                    c = gb.uniform(0.0, size, 2)
                    if not self._outside_cover(c, mg):
                        continue
                    dmin = float(np.sqrt(((self.pos[k] - c) ** 2).sum(1)).min())
                    if dmin >= float(br["start_r"]):
                        best = c
                        break
                    if dmin > best_d:
                        best, best_d = c, dmin
                self.kind[k, a] = K_BEAR
                self.present[k, a] = True
                self.apos[k, a] = best
                ang = gb.uniform(0.0, 2 * math.pi)
                self.ahead[k, a] = (math.cos(ang), math.sin(ang))
                self.asize[k, a] = gb.uniform(br["size"][0], br["size"][1])
        # --- 사슴 상태 ---
        self.disp[k] = 0.0
        self.E[k] = float(d["init_energy"])
        self.R[k] = float(d["reserve_init"])
        self.cd[k] = 0
        self.act[k] = WATCH
        self.prev_act[k] = WATCH
        self.run_dir[k] = 0.0
        self.mem[k] = 0.0
        self.rng_anim[k] = np.random.default_rng([seed, TAG_ANIM])
        self.rng_resp[k] = np.random.default_rng([seed, TAG_RESP])
        self.rng_pol[k] = np.random.default_rng([seed, TAG_POL])

    def reinit(self, k: int, seed: int) -> None:
        """세계 k 를 새 시드로 바꾸고(통계는 이어 센다) 관측을 다시 만든다."""
        self._init_world(k, seed)
        self._perceive(update_mem=False)
        self.obs = self._observe()

    def world_params(self, k: int) -> dict:
        return dict(seed=int(self.seeds[k]), wolves=int(self.M[k]), beasts=int(self.H[k]), wolf_speed_mult=float(self.wolf_speed[k]),
                    food_regen_mult=float(self.regen_mult[k]), stalkers=int(self.stalker[k].sum()), bears=int(self.nBear))

    # ------------------------------------------------------------------ #
    # 통계
    # ------------------------------------------------------------------ #

    def reset_stats(self) -> None:
        K = self.K
        self.st = dict(
            deer_steps=np.zeros(K, dtype=np.int64),
            caught_wolf=np.zeros(K, dtype=np.int64),
            caught_bear=np.zeros(K, dtype=np.int64),
            starved=np.zeros(K, dtype=np.int64),
            repro=np.zeros(K, dtype=np.int64),
            eaten_e=np.zeros(K),
            in_shelter=np.zeros(K, dtype=np.int64),
            decisions=np.zeros(K, dtype=np.int64),
            actions=np.zeros((K, N_ACTIONS), dtype=np.int64),
            flee_cnt=np.zeros((K, 4, 3, 2), dtype=np.int64),      # [세계, 종류(0 없음·1 늑대·2 짐승·3 곰), 거리 띠, 도망]
            flee_dir_sum=np.zeros(K),
            flee_dir_n=np.zeros(K, dtype=np.int64),
            slot_eaten_e=np.zeros((K, self.N)),                     # 칸(사슴 자리)별 — 섞인 무리 비교용
            slot_repro=np.zeros((K, self.N), dtype=np.int64),
            slot_caught=np.zeros((K, self.N), dtype=np.int64),
        )
        self.samples: list[np.ndarray] = []

    # ------------------------------------------------------------------ #
    # 기하
    # ------------------------------------------------------------------ #

    def _cover_edge(self, P: np.ndarray):
        """P (..., 2) → (가장 가까운 은신처 번호, 가장자리 거리) — 가장자리 거리 기준."""
        d = np.sqrt(((P[..., None, :] - self.cov_c) ** 2).sum(-1)) - self.cov_r
        j = d.argmin(-1)
        return j, np.take_along_axis(d, j[..., None], -1)[..., 0]

    def _cell(self, P: np.ndarray):
        kc = 1.0 / float(self.cfg["food"]["cell"])
        ix = np.clip((P[..., 0] * kc).astype(np.int64), 0, self.G - 1)
        iy = np.clip((P[..., 1] * kc).astype(np.int64), 0, self.G - 1)
        return ix, iy

    def _see_r(self) -> np.ndarray:
        s = self.cfg["sense"]
        return np.where(self.act == EAT, float(s["see_r"]) * float(s["head_down"]), float(s["see_r"]))

    def _kin(self, need_steer: bool):
        """사슴끼리: 느낀 동족 (K, N, N) 와 (필요하면) 무리 중심 쪽·분리. 느낌 = 눈(반경·시야각 300°) ∪ 귀(속력의 소리 반경) — 동물과 같은 규칙."""
        s, d = self.cfg["sense"], self.cfg["deer"]
        P, Hd = self.pos, self.head
        dx = P[:, None, :, 0] - P[:, :, None, 0]                    # [k, i, j] = P_j − P_i
        dy = P[:, None, :, 1] - P[:, :, None, 1]
        dist = np.sqrt(dx * dx + dy * dy)
        invd = 1.0 / np.maximum(dist, EPS)
        cosang = (dx * Hd[:, :, 0:1] + dy * Hd[:, :, 1:2]) * invd
        spd = np.sqrt((self.disp ** 2).sum(-1)) / self.unit          # (K, N)
        vis = (dist <= self._see_r()[:, :, None]) & (cosang >= self.fov_cos)
        heard = dist <= hear_radius(spd, s)[:, None, :]
        eye = np.eye(self.N, dtype=bool)[None]
        kin = (vis | heard) & ~eye
        if not need_steer:
            return kin, dx, dy, dist, None, None
        kf = kin.astype(np.float64)
        cnt = kf.sum(-1)
        cxm = (kf * P[:, None, :, 0]).sum(-1) / np.maximum(cnt, 1.0)
        cym = (kf * P[:, None, :, 1]).sum(-1) / np.maximum(cnt, 1.0)
        to_c = np.where(cnt[..., None] > 0, _norm(np.stack([cxm, cym], -1) - P), 0.0)
        wgt = np.clip(1.0 - dist / float(d["sep_radius"]), 0.0, None)
        wgt = np.where(eye, 0.0, wgt)
        c = wgt * invd
        sep = -np.stack([(c * dx).sum(-1), (c * dy).sum(-1)], -1)
        n = np.sqrt((sep * sep).sum(-1, keepdims=True))
        sep = sep * np.minimum(1.0, 1.0 / np.maximum(n, EPS))
        return kin, dx, dy, dist, to_c, sep

    def _food_grad(self) -> np.ndarray:
        """사슴 셀의 먹이 기울기 단위벡터 (K, N, 2) — 반경 grad_blur 셀 평균의 기울기(world._food_fields 와 같은 식)."""
        bm = _box_mean(self.food, max(1, int(self.cfg["food"]["grad_blur"])))
        gy, gx = np.gradient(bm, axis=(1, 2))
        ix, iy = self._cell(self.pos)
        kk = np.arange(self.K)[:, None]
        return _norm(np.stack([gx[kk, iy, ix], gy[kk, iy, ix]], -1))

    def _perceive(self, update_mem: bool) -> None:
        """사슴 → 동물 느낌 (K, N, A) 과 다가옴 기억 갱신. 종류 배열을 읽지 않는다(present·위치·이동·머리·크기만)."""
        s = self.cfg["sense"]
        P, Hd = self.pos, self.head
        dx = self.apos[:, None, :, 0] - P[:, :, None, 0]             # 사슴 → 동물
        dy = self.apos[:, None, :, 1] - P[:, :, None, 1]
        dist = np.sqrt(dx * dx + dy * dy)
        invd = 1.0 / np.maximum(dist, EPS)
        cosang = (dx * Hd[:, :, 0:1] + dy * Hd[:, :, 1:2]) * invd
        pres = self.present[:, None, :]
        vis = pres & (dist <= self._see_r()[:, :, None]) & (cosang >= self.fov_cos)
        aspd = np.sqrt((self.adisp ** 2).sum(-1)) / self.unit         # (K, A)
        heard = pres & (dist <= hear_radius(aspd, s)[:, None, :])
        perc = vis | heard
        vn = float(s["vel_norm"]) * self.unit
        appr = np.clip(-(self.adisp[:, None, :, 0] * dx + self.adisp[:, None, :, 1] * dy) * invd / vn, -1.0, 1.0)
        if update_mem:
            m = np.where(perc, float(s["mem_keep"]) * self.mem + float(s["mem_gain"]) * appr, float(s["mem_decay"]) * self.mem)
            self.mem = np.where(pres, m, 0.0)
        self._pc = dict(dx=dx, dy=dy, dist=dist, invd=invd, vis=vis, heard=heard, perc=perc, appr=appr)

    # ------------------------------------------------------------------ #
    # 관측
    # ------------------------------------------------------------------ #

    def _observe(self) -> np.ndarray:
        """관측 (K, N, 65) float32 (설계 4절). 동물 칸 차례 = 느낀 동물 가까운 순. 숨은 `obs_slot_anim` (K, N, 4) 에 칸마다 동물 칸 번호(없으면 −1)."""
        s = self.cfg["sense"]
        K, N, A = self.K, self.N, self.A
        P, Hd = self.pos, self.head
        hx, hy = Hd[..., 0], Hd[..., 1]
        o = np.zeros((K, N, OBS_DIM), dtype=np.float64)
        kk = np.arange(K)[:, None]
        # --- 자기 ---
        o[..., 0] = self.E / float(self.cfg["deer"]["max_energy"])
        o[..., 1] = self.R
        ix, iy = self._cell(P)
        fb = _box_mean(self.food, max(1, int(self.cfg["food"]["density_blur"])))
        o[..., 2] = fb[kk, iy, ix]
        o[..., 3] = self.food[kk, iy, ix]
        j, edge = self._cover_edge(P)
        inside = edge <= 0.0
        o[..., 4] = inside
        v = self.cov_c[j] - P
        u = _norm(v)
        o[..., 5] = np.where(inside, 0.0, u[..., 0] * hx + u[..., 1] * hy)
        o[..., 6] = np.where(inside, 0.0, -u[..., 0] * hy + u[..., 1] * hx)
        o[..., 7] = np.maximum(edge, 0.0) / float(s["edge_norm"])
        dirs = _rot(Hd[:, :, None, :], self.run_angles[None, None, :])  # (K, N, 8, 2)
        px, py = P[..., 0:1], P[..., 1:2]
        ux, uy = dirs[..., 0], dirs[..., 1]
        with np.errstate(divide="ignore", invalid="ignore"):
            tx = np.where(ux > EPS, (self.size - px) / ux, np.where(ux < -EPS, px / -ux, np.inf))
            ty = np.where(uy > EPS, (self.size - py) / uy, np.where(uy < -EPS, py / -uy, np.inf))
        o[..., 8:16] = np.minimum(tx, ty) / float(s["free_norm"])
        o[..., 16] = np.sqrt((self.disp ** 2).sum(-1)) / (float(s["speed_norm"]) * self.unit)
        # --- 동물 칸 (가까운 순 4) ---
        pc = self._pc
        key = np.where(pc["perc"], pc["dist"], np.inf)
        order = np.argsort(key, axis=-1, kind="stable")[..., :N_SLOTS]          # (K, N, 4)
        got = np.take_along_axis(key, order, -1) < np.inf
        self.obs_slot_anim = np.where(got, order, -1)
        pn, vn = float(s["pos_norm"]), float(s["vel_norm"]) * self.unit
        g = lambda arr: np.take_along_axis(arr, order, -1)               # noqa: E731
        dx, dy, dist, invd = g(pc["dx"]), g(pc["dy"]), g(pc["dist"]), g(pc["invd"])
        ax = np.take_along_axis(np.broadcast_to(self.adisp[:, None, :, 0], (K, N, A)), order, -1)
        ay = np.take_along_axis(np.broadcast_to(self.adisp[:, None, :, 1], (K, N, A)), order, -1)
        ahx = np.take_along_axis(np.broadcast_to(self.ahead[:, None, :, 0], (K, N, A)), order, -1)
        ahy = np.take_along_axis(np.broadcast_to(self.ahead[:, None, :, 1], (K, N, A)), order, -1)
        asz = np.take_along_axis(np.broadcast_to(self.asize[:, None, :], (K, N, A)), order, -1)
        hx3, hy3 = hx[..., None], hy[..., None]
        blk = np.zeros((K, N, N_SLOTS, NA))
        blk[..., 0] = 1.0
        blk[..., 1] = (dx * hx3 + dy * hy3) / pn
        blk[..., 2] = (-dx * hy3 + dy * hx3) / pn
        blk[..., 3] = dist / pn
        blk[..., 4] = (ax * hx3 + ay * hy3) / vn
        blk[..., 5] = (-ax * hy3 + ay * hx3) / vn
        blk[..., 6] = g(pc["appr"])
        blk[..., 7] = g(self.mem)
        blk[..., 8] = -(ahx * dx + ahy * dy) * invd                     # 동물 머리 · (동물 → 나)
        blk[..., 9] = asz / float(s["size_norm"])
        blk[..., 10] = (g(pc["heard"]) & ~g(pc["vis"])).astype(np.float64)
        blk = np.where(got[..., None], blk, 0.0)
        o[..., A0:KIN0] = blk.reshape(K, N, N_SLOTS * NA)
        # --- 동족 ---
        kin, kdx, kdy, kdist, _, _ = self._kin(False)
        kf = kin.astype(np.float64)
        cnt = kf.sum(-1)
        spd = np.sqrt((self.disp ** 2).sum(-1))
        run = (spd > float(s["run_frac_speed"]) * self.unit).astype(np.float64)
        o[..., KIN0] = cnt / float(s["kin_norm"])
        o[..., KIN0 + 1] = np.divide((kf * run[:, None, :]).sum(-1), cnt, out=np.zeros_like(cnt), where=cnt > 0)
        fx = np.divide((kf * self.disp[:, None, :, 0]).sum(-1), cnt, out=np.zeros_like(cnt), where=cnt > 0)
        fy = np.divide((kf * self.disp[:, None, :, 1]).sum(-1), cnt, out=np.zeros_like(cnt), where=cnt > 0)
        fn = float(s["flow_norm"]) * self.unit
        o[..., KIN0 + 2] = (fx * hx + fy * hy) / fn
        o[..., KIN0 + 3] = (-fx * hy + fy * hx) / fn
        return np.clip(o, -1.0, 1.0).astype(np.float32)

    def observe(self) -> np.ndarray:
        return self.obs

    # ------------------------------------------------------------------ #
    # 결정
    # ------------------------------------------------------------------ #

    def step(self, actions: np.ndarray):
        """결정 1 번. actions (K, N) 정수 0~10. 반환 (obs (K, N, 65) float32, rew (K, N), done (K, N) bool, info dict).
        한 결정 안에서 죽으면 그 칸은 곧바로 다시 나고 남은 스텝은 새 사슴이 서 있다(WATCH). 그 뒤 보상은 끝난 판에 넣지 않는다."""
        a = np.asarray(actions).reshape(self.K, self.N).astype(np.int64)
        if a.min() < 0 or a.max() >= N_ACTIONS:
            raise ValueError(f"행동 번호는 0~{N_ACTIONS - 1} 이다: {a.min()}..{a.max()}")
        self.prev_act = self.act.copy()
        self.act = a.copy()
        run = (a >= RUN_FIRST) & (a <= RUN_LAST)
        ang = (np.clip(a, RUN_FIRST, RUN_LAST) - RUN_FIRST) * (math.pi / 4.0)
        self.run_dir = np.where(run[..., None], _rot(self.head, ang), 0.0)
        self._decision_stats(a)
        rew = np.zeros((self.K, self.N))
        done = np.zeros((self.K, self.N), dtype=bool)
        caught_kind = np.zeros((self.K, self.N), dtype=np.int8)
        for _ in range(self.D):
            r, dead, ck = self._phys()
            rew += np.where(done, 0.0, r)
            caught_kind = np.where(done, caught_kind, ck)
            done |= dead
        self.obs = self._observe()
        return self.obs, rew, done, dict(caught_kind=caught_kind)

    def _decision_stats(self, a: np.ndarray) -> None:
        """결정 때 숨은 기록 (설계 8-3 도망 몫): 은신처 밖 사슴의 '가장 가까운 느낀 동물' c* 가 15 단위 안이면 (종류, 띠, 도망)."""
        st = self.st
        K, N = self.K, self.N
        st["decisions"] += N
        np.add.at(st["actions"], (np.repeat(np.arange(K), N), a.reshape(-1)), 1)
        c0 = self.obs_slot_anim[..., 0]
        kk = np.arange(K)[:, None]
        has = c0 >= 0
        ci = np.where(has, c0, 0)
        d0 = np.where(has, np.take_along_axis(self._pc["dist"], ci[..., None], -1)[..., 0], np.inf)
        _, edge = self._cover_edge(self.pos)
        ok = has & (d0 < 15.0) & (edge > 0.0)
        kind = np.where(has, self.kind[kk, ci], 0).astype(np.int64)
        band = np.clip((np.where(has, d0, 0.0) // 5.0), 0, 2).astype(np.int64)
        fled = ((a >= RUN_FIRST) & (a <= SHELTER)).astype(np.int64)
        if ok.any():
            kw, iw = np.nonzero(ok)
            np.add.at(st["flee_cnt"], (kw, kind[kw, iw], band[kw, iw], fled[kw, iw]), 1)
        # 도망 방향: 뛰기를 골랐고 가장 가까운 늑대(실거리)가 10 단위 안이면 cos(뛰기 방향, 그 늑대 반대)
        wolf = (self.kind == K_WOLF)[:, None, :]
        dist = np.where(wolf, self._pc["dist"], np.inf)
        wj = dist.argmin(-1)
        wd = np.take_along_axis(dist, wj[..., None], -1)[..., 0]
        runm = (a >= RUN_FIRST) & (a <= RUN_LAST) & (wd < 10.0)
        if runm.any():
            away = self.pos - self.apos[kk, wj]
            c = (_norm(away) * self.run_dir).sum(-1)
            st["flee_dir_sum"] += np.where(runm, c, 0.0).sum(1)
            st["flee_dir_n"] += runm.sum(1)
        if self.record_samples and ok.any():
            kw, iw = np.nonzero(ok)
            c = ci[kw, iw]
            o = self.obs[kw, iw]
            within = (self._pc["perc"] & (self._pc["dist"] < 15.0)).sum(-1)[kw, iw]
            st_code = self._anim_state_code()[kw, c]
            prev_fled = ((self.prev_act >= RUN_FIRST) & (self.prev_act <= SHELTER))[kw, iw]
            row = np.stack([kw, kind[kw, iw], band[kw, iw], fled[kw, iw], o[:, A0 + 6], o[:, A0 + 7], o[:, A0 + 8], within,
                            o[:, KIN0 + 1], st_code, d0[kw, iw], prev_fled, iw], 1).astype(np.float64)
            self.samples.append(row)

    SAMPLE_COLUMNS = ("world", "kind", "band", "fled", "approach", "approach_mem", "facing", "n_within15", "kin_run_frac",
                      "astate", "dist", "prev_fled", "deer")

    def _anim_state_code(self) -> np.ndarray:
        """동물 상태 번호 (숨은 기록용): 늑대 0 사냥·1 먹기·2 탈진, 짐승 10 + (0 돌아다님·1 풀 뜯기·2 내달리기), 곰 20 + (0 서 있음·1 덮침·2 먹기)."""
        wolf = np.where(self.eat_left > 0, 1, np.where(self.tired_left > 0, 2, 0))
        beast = 10 + self.bstate
        bear = 20 + np.where(self.eat_left > 0, 2, np.where(self.pounce_left > 0, 1, 0))
        return np.where(self.kind == K_WOLF, wolf, np.where(self.kind == K_BEAST, beast, np.where(self.kind == K_BEAR, bear, -1)))

    # ------------------------------------------------------------------ #
    # 한 스텝 (모듈 docstring '한 스텝 순서')
    # ------------------------------------------------------------------ #

    def _phys(self):
        cfg = self.cfg
        d, fd, rw = cfg["deer"], cfg["food"], cfg["reward"]
        K, N = self.K, self.N
        kk = np.arange(K)[:, None]
        act = self.act
        P0 = self.pos
        # 1) 사슴 이동
        weak = self.E / float(d["max_energy"]) < float(d["weak_e"])
        jc, edge = self._cover_edge(P0)
        inside0 = edge <= 0.0
        gait = np.zeros((K, N), dtype=np.int64)
        dirv = np.zeros((K, N, 2))
        eat_mult = np.zeros((K, N))
        is_eat = act == EAT
        if is_eat.any():
            _, _, _, _, to_c, sep = self._kin(True)
            fg = self._food_grad()
            ix, iy = self._cell(P0)
            food_ok = self.food[kk, iy, ix] >= float(d["eat_min"])
            raw = float(d["graze_forage"]) * fg + float(d["graze_cohesion"]) * to_c + float(d["sep_weight"]) * sep
            dg = _norm(raw)
            has = (dg * dg).sum(-1) > EPS * EPS
            g_eat = np.where(food_ok, G_STOP, np.where(has, G_WALK, G_STOP))
            gait = np.where(is_eat, g_eat, gait)
            dirv = np.where((is_eat & (g_eat == G_WALK))[..., None], dg, dirv)
            eat_mult = np.where(is_eat, self.gait_eat[g_eat], 0.0)
        run = (act >= RUN_FIRST) & (act <= RUN_LAST)
        gait = np.where(run, G_RUN, gait)
        dirv = np.where(run[..., None], self.run_dir, dirv)
        shel = act == SHELTER
        go = shel & ~inside0
        gait = np.where(go, G_RUN, gait)
        dirv = np.where(go[..., None], _norm(self.cov_c[jc] - P0), dirv)
        spd = self.gait_speed[gait] * np.where(weak, float(d["weak_speed"]), 1.0)
        P1 = np.clip(P0 + dirv * spd[..., None], 0.0, self.size)
        disp = P1 - P0
        moved = (disp * disp).sum(-1) > EPS * EPS
        self.head = np.where(moved[..., None], _norm(disp), self.head)
        self.pos = P1
        self.disp = disp
        _, edge1 = self._cover_edge(P1)
        inside = edge1 <= 0.0
        # 2)·3) 동물 이동과 잡기
        caught_kind = self._animals(inside)
        caught = caught_kind > 0
        # 4) 섭식·대사·지방 비축 (world.step 3) 과 같은 식)
        drain = float(d["energy_drain"]) * self.gait_drain[gait]
        e_dr = self.E - drain
        epu = float(fd["energy_per_unit"])
        want = np.clip((float(d["max_energy"]) - e_dr) / epu, 0.0, float(fd["eat_rate"])) * eat_mult
        ix, iy = self._cell(P1)
        GG = self.G * self.G
        flat = (kk * GG + iy * self.G + ix).reshape(-1)
        demand = np.bincount(flat, weights=want.reshape(-1), minlength=K * GG)
        fflat = self.food.reshape(-1)
        taken = np.minimum(demand, fflat)
        frac = np.divide(taken, demand, out=np.zeros_like(taken), where=demand > 0)
        self.food = (fflat - taken).reshape(K, self.G, self.G)
        gain = want * frac[flat].reshape(K, N)
        gain_e = gain * epu
        e_new = np.minimum(e_dr + gain_e, float(d["max_energy"]))
        e_new = self._reserve(e_new, gain_e)
        # 5) 보상(살아 있음 + 에너지 순변화) · 번식
        rew = float(rw["alive"]) + float(rw["energy"]) * (e_new - self.E)
        self.E = e_new
        self.cd = np.maximum(self.cd - 1, 0)
        repro = (self.E > float(d["repro_threshold"])) & (self.cd == 0)
        rew = rew + float(rw["repro"]) * repro
        self.E = np.where(repro, float(d["init_energy"]), self.E)
        self.cd = np.where(repro, int(d["repro_cd"]), self.cd)
        # 6) 죽음
        starved = (self.E <= 0.0) & (self.R <= 0.0) & ~caught
        dead = caught | starved
        rew = rew + float(rw["death"]) * dead
        # 7) 먹이 재생
        self.food = self.food + self.regen * (self.food_cap - self.food)
        # 통계
        st = self.st
        st["deer_steps"] += N
        st["caught_wolf"] += (caught_kind == K_WOLF).sum(1)
        st["caught_bear"] += (caught_kind == K_BEAR).sum(1)
        st["starved"] += starved.sum(1)
        st["repro"] += repro.sum(1)
        st["eaten_e"] += gain_e.sum(1)
        st["in_shelter"] += inside.sum(1)
        st["slot_eaten_e"] += gain_e
        st["slot_repro"] += repro
        st["slot_caught"] += caught
        # 8) 다시 남
        if dead.any():
            self._respawn(dead)
        # 9) 느낌·다가옴 기억
        self._perceive(update_mem=True)
        self.t += 1
        if self.step_hook is not None:                  # 평가 도구용(새는 길 시험·리플레이) — 세계를 바꾸지 않는다
            self.step_hook(self, dead, caught_kind)
        return rew, dead, caught_kind

    def _reserve(self, e_new: np.ndarray, gain_e: np.ndarray) -> np.ndarray:
        """지방 비축 (world._wild_reserve_step 과 같은 식): 모자람은 비축에서, 남음(refill_e 이상)은 비축으로."""
        d = self.cfg["deer"]
        C = float(d["reserve_cap"])
        R = self.R
        out = e_new.copy()
        need = e_new < 0.0
        if need.any():
            want = -e_new / C
            cov = want <= R
            out = np.where(need, np.where(cov, 0.0, e_new + R * C), out)
            R = np.where(need, np.where(cov, R - want, 0.0), R)
        rf = float(d["refill_frac"])
        if rf > 0.0:
            fill = (out >= float(d["refill_e"])) & (R < 1.0) & (gain_e > 0.0)
            if fill.any():
                mv = np.where(fill, np.minimum(rf * gain_e, (1.0 - R) * C), 0.0)
                out = out - mv
                R = np.where(fill, np.minimum(R + mv / C, 1.0), R)
        self.R = R
        return out

    def _respawn(self, dead: np.ndarray) -> None:
        """죽은 칸을 새 사슴으로 (설계 3-3): 후보 가운데 은신처 밖·모든 동물에서 respawn_r 이상인 첫 자리, 없으면 동물에서 가장 먼 후보."""
        d = self.cfg["deer"]
        nc, rr = int(d["respawn_candidates"]), float(d["respawn_r"])
        for k in np.nonzero(dead.any(1))[0]:
            g = self.rng_resp[k]
            pres = self.present[k]
            ap = self.apos[k][pres]
            for i in np.nonzero(dead[k])[0]:
                c = g.uniform(0.0, self.size, (nc, 2))
                ang = g.uniform(0.0, 2 * math.pi)
                out = self._outside_cover(c, 0.0)
                dmin = np.sqrt(((c[:, None, :] - ap[None]) ** 2).sum(-1)).min(1) if len(ap) else np.full(nc, 1e9)
                ok = out & (dmin >= rr)
                if ok.any():
                    pick = int(np.argmax(ok))
                else:
                    sc = np.where(out, dmin, dmin - 1e6)
                    pick = int(np.argmax(sc))
                self.pos[k, i] = c[pick]
                self.head[k, i] = (math.cos(ang), math.sin(ang))
                self.disp[k, i] = 0.0
                self.E[k, i] = float(d["init_energy"])
                self.R[k, i] = float(d["reserve_init"])
                self.cd[k, i] = 0
                self.act[k, i] = WATCH
                self.run_dir[k, i] = 0.0
                self.mem[k, i] = 0.0
                # 이 칸을 노리던 덮침은 끝난다 (잠행 늑대는 탈진)
                hit = self.lock[k] == i
                if hit.any():
                    wolf = hit & (self.kind[k] == K_WOLF)
                    self.tired_left[k] = np.where(wolf, int(self.cfg["wolves"]["tired_steps"]), self.tired_left[k])
                    self.pounce_left[k] = np.where(hit, 0, self.pounce_left[k])
                    self.lock[k] = np.where(hit, -1, self.lock[k])

    # ------------------------------------------------------------------ #
    # 동물
    # ------------------------------------------------------------------ #

    def _animals(self, deer_inside: np.ndarray) -> np.ndarray:
        """동물 한 스텝: 이동 → 벽 튕김 → 은신처 밖으로 → 잡기. 반환 caught_kind (K, N) int8 (0 = 안 잡힘)."""
        cfg = self.cfg
        an, wl, bs, br = cfg["animals"], cfg["wolves"], cfg["beasts"], cfg["bears"]
        K, N, A, AW = self.K, self.N, self.A, self.AW
        kk = np.arange(K)[:, None]
        u = np.zeros((K, max(AW, 1), 5))
        for k in range(K):                                      # 늘 같은 개수 (사슴 행동과 무관)
            u[k] = self.rng_anim[k].random((max(AW, 1), 5))
        u = u[:, :AW]
        U = np.zeros((K, A, 5))
        U[:, :AW] = u
        kind = self.kind
        is_w, is_b, is_r = kind == K_WOLF, kind == K_BEAST, kind == K_BEAR
        P = self.pos
        valid_deer = ~deer_inside                                # 은신처 안 사슴은 표적이 아니다
        dx = P[:, None, :, 0] - self.apos[:, :, None, 0]         # [k, a, i] 동물 → 사슴
        dy = P[:, None, :, 1] - self.apos[:, :, None, 1]
        dist = np.sqrt(dx * dx + dy * dy)
        invd = 1.0 / np.maximum(dist, EPS)
        speed = np.zeros((K, A))
        dirv = self.ahead.copy()
        turn = (U[..., 0] * 2.0 - 1.0) * float(an["turn"])
        wander = _rot(self.ahead, turn)
        # --- 늑대 ---
        self.target[:] = -1
        if is_w.any():
            eating = is_w & (self.eat_left > 0)
            tired = is_w & ~eating & (self.tired_left > 0)
            hunt = is_w & ~eating & ~tired
            cosw = (dx * self.ahead[..., 0:1] + dy * self.ahead[..., 1:2]) * invd
            seen = (dist <= float(wl["view_r"])) & (cosw >= self.wolf_fov_cos) & valid_deer[:, None, :]
            dsee = np.where(seen, dist, np.inf)
            tgt = dsee.argmin(-1)
            has = np.take_along_axis(dsee, tgt[..., None], -1)[..., 0] < np.inf
            pouncing = hunt & self.stalker & (self.pounce_left > 0)
            # 덮침 중인 잠행 늑대는 덮침 표적에 매달린다 (표적이 은신처에 들면 덮침이 끝나고 탈진)
            lk = np.where(self.lock >= 0, self.lock, 0)
            lock_ok = (self.lock >= 0) & valid_deer[kk, lk]
            end_p = pouncing & ~lock_ok
            pouncing = pouncing & lock_ok
            tgt = np.where(pouncing, lk, tgt)
            has = np.where(pouncing, True, has & hunt & ~end_p)
            tdist = np.take_along_axis(dist, tgt[..., None], -1)[..., 0]
            to_t = np.stack([np.take_along_axis(dx, tgt[..., None], -1)[..., 0],
                             np.take_along_axis(dy, tgt[..., None], -1)[..., 0]], -1) * (1.0 / np.maximum(tdist, EPS))[..., None]
            chase = hunt & ~self.stalker & has
            start_p = hunt & self.stalker & ~pouncing & has & (tdist <= float(wl["stalk_near"]))
            sneak = hunt & self.stalker & ~pouncing & has & ~start_p
            self.pounce_left = np.where(start_p, int(wl["pounce_steps"]), self.pounce_left)
            self.lock = np.where(start_p, tgt, np.where(end_p, -1, self.lock))
            pounce_now = pouncing | start_p
            self.tired_left = np.where(end_p, int(wl["tired_steps"]), self.tired_left)
            u_ = self.unit
            sp_w = np.where(eating, 0.0,
                   np.where(tired | end_p, float(wl["tired_speed"]) * u_,
                   np.where(pounce_now, float(wl["pounce_speed"]) * u_,
                   np.where(chase, self.wolf_speed[:, None] * u_,
                   np.where(sneak, float(wl["stalk_speed"]) * u_, self.aroam)))))
            aim = chase | pounce_now | sneak
            dir_w = np.where(aim[..., None], to_t, np.where(eating[..., None], self.ahead, wander))
            speed = np.where(is_w, sp_w, speed)
            dirv = np.where(is_w[..., None], dir_w, dirv)
            self.target = np.where(aim, tgt, -1)
            self.eat_left = np.where(eating, self.eat_left - 1, self.eat_left)
            self.tired_left = np.where(tired, self.tired_left - 1, self.tired_left)
            dec = pounce_now
            self.pounce_left = np.where(dec, self.pounce_left - 1, self.pounce_left)
        # --- 짐승 ---
        if is_b.any():
            fin = is_b & (self.bleft <= 0)
            if fin.any():
                pr = np.asarray(bs["next_probs"], dtype=np.float64)
                from_roam = fin & (self.bstate == B_ROAM)
                ch = np.where(U[..., 1] < pr[0], B_GRAZE, np.where(U[..., 1] < pr[0] + pr[1], B_DASH, B_ROAM))
                nxt = np.where(from_roam, ch, B_ROAM)
                lo_hi = {B_ROAM: bs["roam_steps"], B_GRAZE: bs["graze_steps"], B_DASH: bs["dash_steps"]}
                ln = np.zeros((K, A))
                for st_, (lo, hi) in lo_hi.items():
                    ln = np.where(nxt == st_, lo + (hi - lo) * U[..., 2], ln)
                self.bstate = np.where(fin, nxt, self.bstate)
                self.bleft = np.where(fin, np.round(ln).astype(np.int64), self.bleft)
                ang = U[..., 3] * 2 * math.pi
                nd = np.stack([np.cos(ang), np.sin(ang)], -1)
                newdash = fin & (nxt == B_DASH)
                self.bdir = np.where(newdash[..., None], nd, self.bdir)
                ds = bs["dash_speed"]
                self.bspeed = np.where(newdash, (ds[0] + (ds[1] - ds[0]) * U[..., 4]) * self.unit, self.bspeed)
            sp_b = np.where(self.bstate == B_ROAM, self.aroam, np.where(self.bstate == B_DASH, self.bspeed, 0.0))
            dir_b = np.where((self.bstate == B_ROAM)[..., None], wander,
                             np.where((self.bstate == B_DASH)[..., None], self.bdir, self.ahead))
            speed = np.where(is_b, sp_b, speed)
            dirv = np.where(is_b[..., None], dir_b, dirv)
            self.bleft = np.where(is_b, self.bleft - 1, self.bleft)
        # --- 곰 (설계 10절) ---
        if is_r.any():
            eat_r = is_r & (self.eat_left > 0)
            pnc = is_r & ~eat_r & (self.pounce_left > 0)
            lk = np.where(self.lock >= 0, self.lock, 0)
            lock_ok = (self.lock >= 0) & valid_deer[kk, lk]
            stop_p = pnc & ~lock_ok
            pnc = pnc & lock_ok
            near = np.where(valid_deer[:, None, :], dist, np.inf)
            nt = near.argmin(-1)
            nd_ = np.take_along_axis(near, nt[..., None], -1)[..., 0]
            trig = is_r & ~eat_r & ~pnc & ~stop_p & (nd_ <= float(br["trigger_r"]))
            self.lock = np.where(trig, nt, np.where(is_r & stop_p, -1, self.lock))
            self.pounce_left = np.where(trig, int(br["pounce_steps"]), np.where(is_r & stop_p, 0, self.pounce_left))
            go = pnc | trig
            tg = np.where(go, self.lock, 0)
            td = np.take_along_axis(dist, tg[..., None], -1)[..., 0]
            to_t = np.stack([np.take_along_axis(dx, tg[..., None], -1)[..., 0],
                             np.take_along_axis(dy, tg[..., None], -1)[..., 0]], -1) * (1.0 / np.maximum(td, EPS))[..., None]
            speed = np.where(is_r, np.where(go, float(br["pounce_speed"]) * self.unit, 0.0), speed)
            dirv = np.where((is_r & go)[..., None], to_t, np.where(is_r[..., None], self.ahead, dirv))
            self.target = np.where(is_r & go, self.lock, self.target)
            self.eat_left = np.where(eat_r, self.eat_left - 1, self.eat_left)
            self.pounce_left = np.where(go, self.pounce_left - 1, self.pounce_left)
            ended = go & (self.pounce_left <= 0)
            self.lock = np.where(is_r & ended, -1, self.lock)
        # --- 움직이기: 벽 튕김, 은신처 밖으로 ---
        pres = self.present
        speed = np.where(pres, speed, 0.0)
        old = self.apos.copy()
        newp = old + dirv * speed[..., None]
        hd = np.where((speed > 0)[..., None], dirv, self.ahead)
        outx = (newp[..., 0] < 0.0) | (newp[..., 0] > self.size)
        outy = (newp[..., 1] < 0.0) | (newp[..., 1] > self.size)
        hd = np.stack([np.where(outx, -hd[..., 0], hd[..., 0]), np.where(outy, -hd[..., 1], hd[..., 1])], -1)
        self.bdir = np.where((is_b & (self.bstate == B_DASH))[..., None], hd, self.bdir)
        newp = np.clip(newp, 0.0, self.size)
        rr = self.cov_r + float(an["shelter_margin"])
        for c in self.cov_c:
            v = newp - c
            dd = np.sqrt((v * v).sum(-1))
            inn = pres & (dd < rr)
            if inn.any():
                push = np.where((dd > EPS)[..., None], v / np.maximum(dd, EPS)[..., None], np.array([1.0, 0.0]))
                newp = np.where(inn[..., None], c + push * rr, newp)
        newp = np.where(pres[..., None], newp, old)
        self.apos = newp
        self.adisp = newp - old
        hdn = _norm(hd)
        self.ahead = np.where((pres & ((hdn * hdn).sum(-1) > 0.5))[..., None], hdn, self.ahead)
        # --- 잡기 (칸 차례, 사슴 하나는 한 번만) ---
        caught_kind = np.zeros((K, N), dtype=np.int8)
        tg = self.target
        if (tg >= 0).any():
            for a in range(A):
                ta = tg[:, a]
                ks = np.nonzero(ta >= 0)[0]
                if not len(ks):
                    continue
                ti = ta[ks]
                dv = self.apos[ks, a] - self.pos[ks, ti]
                dd = np.sqrt((dv * dv).sum(-1))
                ka = kind[ks, a]
                cr = np.where(ka == K_BEAR, float(br["catch_r"]), float(wl["catch_r"]))
                hit = (dd <= cr) & ~deer_inside[ks, ti] & (caught_kind[ks, ti] == 0)
                if hit.any():
                    kh, th = ks[hit], ti[hit]
                    caught_kind[kh, th] = ka[hit]
                    es = np.where(ka[hit] == K_BEAR, int(br["eat_steps"]), int(wl["eat_steps"]))
                    self.eat_left[kh, a] = es
                    self.pounce_left[kh, a] = 0
                    self.lock[kh, a] = -1
                    self.tired_left[kh, a] = 0
        # 잠행 늑대 덮침이 이번 스텝에 다 됐는데 못 잡았으면 탈진
        if is_w.any():
            miss = is_w & self.stalker & (self.lock >= 0) & (self.pounce_left <= 0) & (self.eat_left == 0)
            self.tired_left = np.where(miss, int(wl["tired_steps"]), self.tired_left)
            self.lock = np.where(miss, -1, self.lock)
        return caught_kind

    # ------------------------------------------------------------------ #
    # 보조
    # ------------------------------------------------------------------ #

    def stats_snapshot(self) -> dict:
        return {k: v.copy() for k, v in self.st.items() if isinstance(v, np.ndarray)}

    def samples_array(self) -> np.ndarray:
        if not self.samples:
            return np.zeros((0, len(self.SAMPLE_COLUMNS)))
        return np.concatenate(self.samples, 0)
