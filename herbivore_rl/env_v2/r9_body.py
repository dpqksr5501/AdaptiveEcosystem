"""R9 body table and I/O contract (design AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 3-3, 4, 5, 3-9, 7-10, 11, 14).

This module is the single source of the species-independent contract shared by the world (`r9_world.py`), life (`r9_life.py`)
and brains (`r9_brains.py`). Nothing here runs a world step.

  - species numbers (deer → wolf → boar, the slot block order of 3절), food kinds, sex codes (EcoLifeV3::ESex order), gaits
  - 19 actions (5절) and the literal 8-direction / golden-angle tables (3-9: no trig inside a step)
  - 115 observation columns (4절, S′ 2026-11-12: 107 + food_dir_0..7 at 23~30): names, slices, column helpers and the normalisation
    constants
  - config loading (`inherit:` merge like R8) and the body table (3-3) expanded to (n_species,) arrays and to (K, S) slot arrays
  - two contract hashes (7-10, 14-2): I/O (all species the same) and body (per species; reject a brain trained on another body)

Units are R8/Unreal v3: 1 unit = 2 m, 1 step = 2/15 s, decision = 2 steps, day = 900 steps. Speeds in the R9 config are
absolute units/step (R8 wrote multiples of the deer run speed).

Body hash = canonical JSON of `species.<name>` + `body_common` only. Train-only randomisation and judge-only birth limits live in
other blocks, so `v3_r9.yaml` and `v3_r9_judge.yaml` give the same body hash (a trained brain is accepted by the judge world).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# --------------------------------------------------------------------------- #
# species / food / sex / gait
# --------------------------------------------------------------------------- #

DEER, WOLF, BOAR = 0, 1, 2
SPECIES = ("deer", "wolf", "boar")           # slot block order inside one world (3-6: 사슴 → 늑대 → 멧돼지)
N_SPECIES = 3                                # 'S′ 세 종' (eval / league / run_night and the old tests keep this meaning — 동물 9-1 B6)
# 동물 세계 (RL_R9_SPECIES_TRAITS.md 3·9-2): species numbers continue after the S′ three. A config names a prefix of ALL_SPECIES
# (`species_of`); world / body / life / brains / VecEnv / training read the config's list, never N_SPECIES.
BUFFALO, LEOPARD, FOX, RAT, CROW = 3, 4, 5, 6, 7
ALL_SPECIES = ("deer", "wolf", "boar", "buffalo", "leopard", "fox", "rat", "crow")
STAGE1_MAX_SPECIES = 6                       # 쥐·까마귀는 3 단계 (굴·날기 몸 규칙이 생긴 뒤)
SPECIES_INDEX = {n: i for i, n in enumerate(ALL_SPECIES)}

GRASS, ROOT, MEAT = 0, 1, 2
FOODS = ("grass", "root", "meat")
N_FOODS = 3
GRID_FOODS = (GRASS, ROOT)

SEX_NONE, SEX_FEMALE, SEX_MALE = 0, 1, 2      # EcoLifeV3::ESex {Unspecified, Female, Male}

G_STAND, G_WALK, G_RUN = 0, 1, 2              # gait index into body_common.gait_drain

# founder genome kinds (LH 49~56)
FOUNDER_PLAIN, FOUNDER_NATURAL = 0, 1
# sex modes (3-3 성별, 3-7)
SEXMODE_NONE, SEXMODE_NATURAL, SEXMODE_ALTERNATE = 0, 1, 2
# child ring centre (3-7 새끼 자리)
CHILD_AT_PARENT_A, CHILD_AT_MIDPOINT = 0, 1

# --------------------------------------------------------------------------- #
# units
# --------------------------------------------------------------------------- #

UNIT_M = 2.0
STEP_S = 2.0 / 15.0
STEPS_PER_S = 7.5
DAY_STEPS = 900
DECISION_STEPS = 2

# --------------------------------------------------------------------------- #
# actions (5절)
# --------------------------------------------------------------------------- #

EAT = 0
WALK_FIRST, WALK_LAST = 1, 8                  # WALK_k: head rotated ccw (left) by (k − 1) × 45°
RUN_FIRST, RUN_LAST = 9, 16                   # RUN_k : head rotated ccw by (k − 9) × 45°
SHELTER = 17
WATCH = 18
N_ACTIONS = 19
ACTION_NAMES = (("EAT",) + tuple(f"WALK_{j * 45}" for j in range(8)) + tuple(f"RUN_{j * 45}" for j in range(8))
                + ("SHELTER", "WATCH"))
ACTION_GROUPS = {"eat": (EAT,), "walk": tuple(range(WALK_FIRST, WALK_LAST + 1)), "run": tuple(range(RUN_FIRST, RUN_LAST + 1)),
                 "shelter": (SHELTER,), "watch": (WATCH,)}


def action_dir_index(a) -> np.ndarray:
    """Direction index j (0..7) of WALK/RUN actions, −1 for the others. Works on scalars and arrays."""
    a = np.asarray(a)
    return np.where((a >= WALK_FIRST) & (a <= WALK_LAST), a - WALK_FIRST,
                    np.where((a >= RUN_FIRST) & (a <= RUN_LAST), a - RUN_FIRST, -1))


def action_mask(groups) -> np.ndarray:
    """(19,) bool from group names ('eat', 'walk', 'run', 'shelter', 'watch')."""
    m = np.zeros(N_ACTIONS, dtype=bool)
    for g in groups:
        if g not in ACTION_GROUPS:
            raise ValueError(f"unknown action group {g!r} (known: {sorted(ACTION_GROUPS)})")
        m[list(ACTION_GROUPS[g])] = True
    return m


# --------------------------------------------------------------------------- #
# literal rotation tables (3-9: 스텝 안 삼각함수 금지)
# --------------------------------------------------------------------------- #

SQRT_HALF = 0.7071067811865476                # float64 nearest to 1/√2 (= math.sqrt(0.5))

# DIR8[j] = (cos j·45°, sin j·45°). Rotating head h by j: (h_x c − h_y s, h_x s + h_y c). free_j (obs 13+j), food_dir_j (obs 23+j,
# sector centre) and WALK_{j+1} / RUN_{j+9} (the decision direction) all use the same j — the largest food_dir column names the
# WALK that moves toward that food (S′ 3-9 / 4-2).
DIR8 = np.array([
    [1.0, 0.0],
    [SQRT_HALF, SQRT_HALF],
    [0.0, 1.0],
    [-SQRT_HALF, SQRT_HALF],
    [-1.0, 0.0],
    [-SQRT_HALF, -SQRT_HALF],
    [0.0, -1.0],
    [SQRT_HALF, -SQRT_HALF],
], dtype=np.float64)
DIR8.setflags(write=False)

# Golden-angle ring for child / newborn-respawn spots (3-7, NB 59~70: Angle = K × 2.399963). Values = math.cos/sin(k × 2.399963)
# written out as float64 literals. Unreal also adds a per-birth hash rotation Unit(A ^ B) × 2π — R9 drops it (open issue in the
# contract: the design asks for a literal table; a hash rotation needs a trig call or a second table).
GOLDEN_ANGLE_RAD = 2.399963
GOLDEN8 = np.array([
    [1.0, 0.0],
    [-0.7373687228988248, 0.6754904636562651],
    [0.08742526701888792, -0.9961710810331106],
    [0.6084394079172122, 0.7936003319639882],
    [-0.9847136453733523, -0.17418104551162786],
    [0.8437546783027774, -0.5367290217998061],
    [-0.25960297378670444, 0.9657154322061441],
    [-0.4609084518190998, -0.8874476880592571],
], dtype=np.float64)
GOLDEN8.setflags(write=False)


def rotate(h: np.ndarray, cs: np.ndarray) -> np.ndarray:
    """Rotate vectors h (..., 2) ccw by table rows cs (..., 2) = (cos, sin). Products and sums only — no trig."""
    hx, hy = h[..., 0], h[..., 1]
    c, s = cs[..., 0], cs[..., 1]
    return np.stack([hx * c - hy * s, hx * s + hy * c], -1)


# --------------------------------------------------------------------------- #
# observation layout (4절, 115 columns — S′: the 8 food_dir columns close the self block, the blocks behind move by 8)
# --------------------------------------------------------------------------- #

N_FOOD_DIR = 8
FOOD_DIR_NAMES = tuple(f"food_dir_{j}" for j in range(N_FOOD_DIR))
OBS_SELF_NAMES = (("energy", "reserve", "stamina", "health", "own_size", "age_frac", "birth_wait", "food_density", "food_here",
                   "in_shelter", "shelter_x", "shelter_y", "shelter_edge",
                   "free_0", "free_1", "free_2", "free_3", "free_4", "free_5", "free_6", "free_7",
                   "own_speed", "mating")
                  + FOOD_DIR_NAMES)
OBS_OTHER_FIELDS = ("present", "rel_x", "rel_y", "dist", "vel_x", "vel_y", "approach", "approach_mem", "facing", "size",
                    "not_seen")
N_OTHER = 6
OBS_KINSUM_NAMES = ("kin_count", "kin_run_frac", "kin_flow_x", "kin_flow_y")
OBS_KIN_FIELDS = ("present", "rel_x", "rel_y", "vel_x", "vel_y", "size", "mate_ok")
N_KIN = 2

N_SELF = len(OBS_SELF_NAMES)                  # 31 (23 + food_dir 8)
N_OF = len(OBS_OTHER_FIELDS)                  # 11
N_KF = len(OBS_KIN_FIELDS)                    # 7
SELF0 = 0
OTHER0 = SELF0 + N_SELF                       # 31
KINSUM0 = OTHER0 + N_OTHER * N_OF             # 97
KIN0 = KINSUM0 + len(OBS_KINSUM_NAMES)        # 101
OBS_NAMES = (OBS_SELF_NAMES
             + tuple(f"o{j}_{f}" for j in range(N_OTHER) for f in OBS_OTHER_FIELDS)
             + OBS_KINSUM_NAMES
             + tuple(f"k{j}_{f}" for j in range(N_KIN) for f in OBS_KIN_FIELDS))
OBS_DIM = len(OBS_NAMES)                      # 115
OBS_INDEX = {n: i for i, n in enumerate(OBS_NAMES)}

SL_SELF = slice(SELF0, OTHER0)
SL_OTHER = slice(OTHER0, KINSUM0)
SL_KINSUM = slice(KINSUM0, KIN0)
SL_KIN = slice(KIN0, OBS_DIM)

# named self columns
(O_ENERGY, O_RESERVE, O_STAMINA, O_HEALTH, O_OWN_SIZE, O_AGE_FRAC, O_BIRTH_WAIT, O_FOOD_DENSITY, O_FOOD_HERE, O_IN_SHELTER,
 O_SHELTER_X, O_SHELTER_Y, O_SHELTER_EDGE) = range(13)
O_FREE0 = 13                                  # free_j = O_FREE0 + j
O_OWN_SPEED = 21
O_MATING = 22
O_FOOD_DIR0 = 23                              # food_dir_j = O_FOOD_DIR0 + j (j = 0..7)
SL_FOOD_DIR = slice(O_FOOD_DIR0, O_FOOD_DIR0 + N_FOOD_DIR)


def other_col(j: int, f: str) -> int:
    """Column of field f of other-species slot j (0..5) — 31 + 11 j + field."""
    return OTHER0 + j * N_OF + OBS_OTHER_FIELDS.index(f)


def kin_col(j: int, f: str) -> int:
    """Column of field f of near-kin slot j (0..1)."""
    return KIN0 + j * N_KF + OBS_KIN_FIELDS.index(f)


# Normalisation and sensing constants — species independent, part of the I/O hash. Body-specific scales (food refs) are in the
# body table. All observation values are clipped to [−1, 1] after normalisation (4절).
OBS_NORM = {
    "pos": 20.0,            # rel_x·rel_y·dist (other and kin slots) / 20
    "vel": 0.9,             # vel_x·vel_y·approach (other and kin slots) / 0.9 (R8 1.5 × 0.6)
    "size": 2.0,            # own_size·size / 2
    "kin_count": 20.0,
    "kin_run_speed": 0.39,  # kin_run_frac: |disp| > 0.39 units/step (R8 0.65 × 0.6)
    "flow": 0.6,            # kin_flow mean displacement / 0.6
    "free": 10.0,
    "edge": 20.0,
    "speed": 0.6,           # own_speed = |disp| / 0.6
    "birth_wait": 2250.0,   # max(0, next_birth − t) / 2250
    "food_r": 20.0,         # food_density window: grid box mean radius 10 cells (20 units) + sensed carcasses within 20 units
    "food_box_cells": 441,  # (2 × 10 + 1)² — carcass meat is divided by this to give a per-cell density
    "here_r": 1.0,          # food_here: meat of carcasses within 1.0 unit; grids use the current cell (food_dir leaves both out)
}
SENSE = {
    "hear_silent": 0.03,    # 4-1: R(s) = 0 if s < 0.03
    "hear_quiet": 0.18,     #      else 2 + 18 × clip((s − 0.18) / 0.42, 0, 1)
    "hear_span": 0.42,
    "hear_r_quiet": 2.0,
    "hear_r_loud": 20.0,
    "mem_keep": 0.8,        # approach_mem: perceived m ← 0.8 m + 0.2 a, else m ← 0.9 m
    "mem_gain": 0.2,
    "mem_decay": 0.9,
}

# Human-readable formula per column family (enters the I/O hash so a silent meaning change is caught).
OBS_SPEC = {
    "energy": "E (stomach 0..1)",
    "reserve": "fat fraction R (0..1)",
    "stamina": "stamina (0..1)",
    "health": "HP (deer always 1)",
    "own_size": "size0 × g_size × growth / 2",
    "age_frac": "clip((t − born) / maturity, 0, 1)",
    "birth_wait": "max(0, next_birth − t) / 2250",
    "food_density": "(Σ_grid-diet e_f × boxmean_r10(grid_f) + e_meat × Σ sensed carcass meat within 20 / 441) / food_density_ref",
    "food_here": "(Σ_grid-diet e_f × cell(grid_f) + e_meat × Σ carcass meat within 1.0 (other species)) / food_here_ref",
    "in_shelter": "edge distance to nearest shelter ≤ 0",
    "shelter_xy": "unit vector to nearest (edge distance) shelter centre in self frame, 0 inside",
    "shelter_edge": "max(edge, 0) / 20",
    "free_j": "ray length to wall along DIR8[j] applied to head / 10",
    "own_speed": "|disp| / 0.6 (disp = total last-step displacement incl. contact)",
    "mating": "paired and waiting for birth (0/1)",
    "food_dir": ("food_dir_j: sensed (eye see_r x head_down-if-EAT & fov, or nose smell_r) own-diet food, own cell / carcasses within "
                 "here_r excluded, cell -> argmax_j v.rotate(head, DIR8[j]) (ties lower j), x_j = sum food x energy x max(1-d/R_eye, "
                 "1-d/R_nose); value x_j / (x_j + food_here_ref)"),
    "other": "perceived (eye ∪ ear ∪ nose) other-kin individuals, distance asc, ties lower slot, 6 slots",
    "kin": "perceived same-kin individuals; summary of all + 2 nearest slots",
    "approach": "−(disp_j · (p_j − p_i)) / |p_j − p_i| / 0.9",
    "facing": "head_j · (p_i − p_j) / |p_i − p_j|",
    "not_seen": "perceived and not in eye",
    "mate_ok": "alive, same kin, mature_j, sex compatible (both none, or both set and different), judge: not related",
    "frame": "x = head, y = left (ccw)",
}


def hear_radius(s: np.ndarray) -> np.ndarray:
    """Sound radius (units) of a maker whose last-step speed is s (units/step), 4-1. Depends on actual speed only."""
    s = np.asarray(s, dtype=np.float64)
    t = np.clip((s - SENSE["hear_quiet"]) / SENSE["hear_span"], 0.0, 1.0)
    return np.where(s < SENSE["hear_silent"], 0.0, SENSE["hear_r_quiet"] + (SENSE["hear_r_loud"] - SENSE["hear_r_quiet"]) * t)


def quadrant_of(P: np.ndarray, size: float, quadrants: int) -> np.ndarray:
    """Quadrant index of positions P (..., 2): 1 region → 0; 4 → (x ≥ size/2) + 2 (y ≥ size/2) (3-1)."""
    if int(quadrants) == 1:
        return np.zeros(np.asarray(P).shape[:-1], dtype=np.int8)
    if int(quadrants) != 4:
        raise ValueError(f"quadrants must be 1 or 4: {quadrants}")
    h = 0.5 * float(size)
    return ((P[..., 0] >= h).astype(np.int8) + 2 * (P[..., 1] >= h).astype(np.int8)).astype(np.int8)


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #

SPECIES_KEYS = ("mass_kg", "founder", "founder_variation", "growth", "walk_speed", "run_speed", "run_mult", "accel",
                "stamina_run_steps", "stamina_recover_steps", "see_r", "fov_deg", "head_down", "smell_r", "drain",
                "reserve_days", "refill_e", "refill_frac", "weak_e", "weak_speed", "diet", "eat_rate", "e_per_unit",
                "has_hp", "hp_regen_per_day", "shelter_enter", "bites", "bite_r", "counter", "maturity_steps", "sex",
                "female_frac", "child_female_frac", "max_founder_age_steps", "first_birth", "mate_r", "birth_r",
                "birth_grace_steps", "pair_block", "birth_block", "pending_needs_parent", "child_ring", "food_density_ref",
                "food_here_ref")
COMMON_KEYS = ("gait_drain", "stamina_lock", "stamina_unlock", "wound_speed", "eat_min", "bite", "counter", "bite_damage", "carcass",
               "shelter_push", "breed")
# S′ (2026-11-12): EAT = stand and eat what is here, SHELTER = stand — the R8 EAT walk values (walk_eat_mult, graze) are gone.
REMOVED_COMMON_KEYS = ("walk_eat_mult", "graze")
REQUIRED = {
    "world": ("mode", "size", "decision_steps", "quadrants", "slots", "carcass_slots", "shelters", "wall_band"),
    "placement": ("wolf_gap", "prey_from_wolf", "shelter_margin", "tries", "pack_r"),
    "counts": ("deer", "wolf", "boar"),
    "learner_counts": ("deer", "wolf", "boar"),
    "randomize": ("grass_regen_mult", "root_regen_mult", "juvenile_frac", "fat_init", "start_energy", "rule_deer_facing"),
    "respawn": ("newborn_frac", "far_r", "candidates"),
    "food": ("cell", "grass", "root", "quadrant_grass_total", "train_grass_total"),
    "body_common": COMMON_KEYS,
    "species": SPECIES,
    "reward": ("alive", "energy", "birth", "death", "fallback_f"),
    "rules": ("deer", "boar", "wolf", "hide"),
    "train": ("seeds", "reset_steps", "worlds", "n_steps", "opponents", "opponent_stochastic", "ppo"),
}
# 동물 세계 몸 칸 (9-2): body_common.fauna 가 있을 때만, 그때는 모든 종 블록에 필수. 없으면 어느 종 블록에도 있으면 안 된다.
FAUNA_SPECIES_KEYS = ("bite_k", "hide", "strike_k", "gore", "gore_r", "camo", "recover")
FAUNA_COMMON_KEYS = ("damage", "age_steps", "shelter_guard", "gore", "camo_curve", "carcass_places")
FAUNA_AGE_STEPS = 64                         # = r9_life.AGE_STEPS (AGE23 literal table; checked like eat_r)
# 몸 움직임 (RL_R9_TURN_EFFORT_DESIGN.md 6-1): body_common.motion 이 있을 때만 새 줄. 깃발 둘은 필수 bool, 켜진 규칙의 종 칸은 모든 종에
# 필수, 꺼진 규칙의 칸(공통·종)은 두면 안 된다 — 쓰지 않는 값이 몸 해시에 들어가지 않는다. M2(effort)는 사용자 결정 전이라 아직 없다
# (2026-11-13 결정: 첫 바퀴 M1 만 — effort: true 는 거부).
MOTION_FLAG_KEYS = ("turn", "effort")
MOTION_EFFORT_KEYS = ("eta_up", "eta_down", "fit", "kappa")
MOTION_TURN_SPECIES_KEYS = ("turn_dps", "lat_accel_mps2")
MOTION_EFFORT_SPECIES_KEYS = ("walk_w_kg",)
MPS2_PER_UNIT = 112.5                         # 1 단위/스텝² = UNIT_M / STEP_S² = 2 m / (2/15 s)² (옆 가속 m/s² → 단위/스텝²)
NEW_SPECIES_SECTIONS = ("world.slots", "counts", "learner_counts", "randomize.juvenile_frac", "rules")
JUDGE_KEYS = ("steps", "steps_long", "worlds", "worlds_long", "start_per_quadrant", "wolf_packs", "grass_regen_mult",
              "root_regen_mult", "wolf_run_mult", "greedy", "founders", "start", "limits", "plant_budget")


def _deep_merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def species_of(cfg: dict) -> tuple:
    """Species of a config = the names of its `species` block, which must be a prefix of ALL_SPECIES (deer, wolf, boar first, then
    buffalo, leopard, fox — slot block order). S′ configs give the three; rat and crow are refused (3 단계)."""
    names = list(cfg["species"].keys())
    n = len(names)
    if n > STAGE1_MAX_SPECIES:
        raise ValueError("쥐·까마귀는 3 단계 — 굴·날기 몸 규칙 없이 넣지 않는다 (species: " + ", ".join(names) + ")")
    if n < len(SPECIES) or set(names) != set(ALL_SPECIES[:n]):
        raise ValueError(f"species must be the first n of {ALL_SPECIES} (n ≥ 3, any order in the YAML): {names}")
    return ALL_SPECIES[:n]


def _check_fauna(cfg: dict, names: tuple) -> None:
    """body_common.fauna block (R1·P1·R2·R3·R6) and the per-species body cells (9-2)."""
    fa = cfg["body_common"].get("fauna")
    if fa is None:
        for n in names:
            bad = [k for k in FAUNA_SPECIES_KEYS if k in cfg["species"][n]]
            if bad:
                raise ValueError(f"species.{n} has animal-world keys {bad} but body_common.fauna is missing")
        return
    if not isinstance(fa, dict):
        raise ValueError("body_common.fauna must be a mapping")
    miss = [k for k in FAUNA_COMMON_KEYS if k not in fa]
    if miss:
        raise ValueError(f"body_common.fauna misses keys {miss}")
    if fa["damage"] != "mass":
        raise ValueError(f"body_common.fauna.damage must be 'mass': {fa['damage']!r}")
    if fa["shelter_guard"] != "enter":
        raise ValueError(f"body_common.fauna.shelter_guard must be 'enter': {fa['shelter_guard']!r}")
    if float(fa["age_steps"]) != float(FAUNA_AGE_STEPS):
        raise ValueError(f"body_common.fauna.age_steps {fa['age_steps']} must equal the code literal {FAUNA_AGE_STEPS} (AGE23 table)")
    g = fa["gore"]
    for k in ("cone_cos", "approach_min", "cooldown", "run_only"):
        if k not in g:
            raise ValueError(f"body_common.fauna.gore misses {k!r}")
    if g["run_only"] is not True:
        raise ValueError("body_common.fauna.gore.run_only must be true (P6: 들이받기는 뛰기 걸음일 때만)")
    if int(g["cooldown"]) < 0:
        raise ValueError("body_common.fauna.gore.cooldown must be ≥ 0")
    if not float(fa["camo_curve"]["span"]) > 0.0:
        raise ValueError("body_common.fauna.camo_curve.span must be > 0")
    cp = fa["carcass_places"]
    if not (float(cp["per_size"]) > 0.0 and 1 <= int(cp["min"]) <= int(cp["max"])):
        raise ValueError(f"body_common.fauna.carcass_places must have per_size > 0 and 1 ≤ min ≤ max: {cp}")
    for n in names:
        s = cfg["species"][n]
        miss = [k for k in FAUNA_SPECIES_KEYS if k not in s]
        if miss:
            raise ValueError(f"species.{n} misses animal-world keys {miss} (body_common.fauna is set — 모든 종에 필수)")
        if not float(s["hide"]) > 0.0:
            raise ValueError(f"species.{n}.hide must be > 0")
        if not (0.0 < float(s["camo"]) <= 1.0):
            raise ValueError(f"species.{n}.camo must be in (0, 1]")
        if float(s["bite_k"]) < 0.0 or float(s["strike_k"]) < 0.0:
            raise ValueError(f"species.{n}: bite_k and strike_k must be ≥ 0")
        if not float(s["recover"]) > 0.0:
            raise ValueError(f"species.{n}.recover must be > 0")
        if not isinstance(s["gore"], bool):
            raise ValueError(f"species.{n}.gore must be true|false")
        if s["gore"] and not float(s["gore_r"]) > 0.0:
            raise ValueError(f"species.{n}: gore needs gore_r > 0")


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _check_motion(cfg: dict, names: tuple) -> None:
    """body_common.motion block (RL_R9_TURN_EFFORT_DESIGN.md 6-1): flags bool, the keys of a rule that is on are required (every
    species), the keys of a rule that is off must be absent (common and species), ranges of 6-1. No block → no motion key anywhere."""
    mo = cfg["body_common"].get("motion")
    sp_keys = MOTION_TURN_SPECIES_KEYS + MOTION_EFFORT_SPECIES_KEYS
    if mo is None:
        for n in names:
            bad = [k for k in sp_keys if k in cfg["species"][n]]
            if bad:
                raise ValueError(f"species.{n} has motion keys {bad} but body_common.motion is missing")
        return
    if not isinstance(mo, dict):
        raise ValueError("body_common.motion must be a mapping")
    unknown = [k for k in mo if k not in MOTION_FLAG_KEYS + MOTION_EFFORT_KEYS]
    if unknown:
        raise ValueError(f"body_common.motion has unknown keys {unknown} (known: {MOTION_FLAG_KEYS + MOTION_EFFORT_KEYS})")
    for k in MOTION_FLAG_KEYS:
        if k not in mo:
            raise ValueError(f"body_common.motion misses {k!r} (turn and effort are both required)")
        if not isinstance(mo[k], bool):
            raise ValueError(f"body_common.motion.{k} must be true|false (a YAML bool, not {mo[k]!r})")
    if mo["effort"]:
        raise ValueError("body_common.motion.effort: true — M2 (속도를 바꾸는 힘) 는 아직 구현하지 않았다. 사용자 결정(설계 11-5) 전이라 "
                         "첫 바퀴는 M1 회전 한계만 (effort: false)")
    bad = [k for k in MOTION_EFFORT_KEYS if k in mo]
    if bad:
        raise ValueError(f"body_common.motion {bad}: M2 keys must be absent when effort is false")
    for n in names:
        s = cfg["species"][n]
        bad = [k for k in MOTION_EFFORT_SPECIES_KEYS if k in s]
        if bad:
            raise ValueError(f"species.{n} {bad}: M2 keys must be absent when body_common.motion.effort is false")
        if mo["turn"]:
            miss = [k for k in MOTION_TURN_SPECIES_KEYS if k not in s]
            if miss:
                raise ValueError(f"species.{n} misses motion keys {miss} (body_common.motion.turn is true — 모든 종에 필수)")
            if not (_num(s["turn_dps"]) and _num(s["lat_accel_mps2"])):
                raise ValueError(f"species.{n}: turn_dps and lat_accel_mps2 must be numbers")
            step_deg = float(s["turn_dps"]) * STEP_S
            if not (0.0 < step_deg < 45.0):
                raise ValueError(f"species.{n}.turn_dps {s['turn_dps']}: per-step turn {step_deg} deg must be in (0, 45) "
                                 "(below the DIR8 angle)")
            if not float(s["lat_accel_mps2"]) > 0.0:
                raise ValueError(f"species.{n}.lat_accel_mps2 must be > 0")
        else:
            bad = [k for k in MOTION_TURN_SPECIES_KEYS if k in s]
            if bad:
                raise ValueError(f"species.{n} {bad}: turn keys must be absent when body_common.motion.turn is false")


def _check_variants(cfg: dict, names: tuple) -> None:
    """train.variants (9-5): world-number variants of the learning world (counts only — no behaviour, no RNG)."""
    vs = cfg["train"].get("variants")
    if vs is None:
        return
    if not isinstance(vs, list):
        raise ValueError("train.variants must be a list")
    caps = cfg["world"]["slots"]
    seen = set()
    for v in vs:
        for k in ("name", "learners", "every"):
            if k not in v:
                raise ValueError(f"train.variants item misses {k!r}: {v}")
        if v["name"] in seen:
            raise ValueError(f"train.variants: duplicate name {v['name']!r}")
        seen.add(v["name"])
        if float(v["every"]) != int(v["every"]) or int(v["every"]) < 2:
            raise ValueError(f"train.variants.{v['name']}.every must be an integer ≥ 2")
        bad = [n for n in v["learners"] if n not in names]
        if bad or not v["learners"]:
            raise ValueError(f"train.variants.{v['name']}.learners must name config species: {v['learners']}")
        for blk in ("counts", "learner_counts"):
            for n, lst in (v.get(blk) or {}).items():
                if n not in names:
                    raise ValueError(f"train.variants.{v['name']}.{blk}: unknown species {n!r}")
                if blk == "learner_counts" and n not in v["learners"]:
                    raise ValueError(f"train.variants.{v['name']}.learner_counts.{n}: not a learner of this variant")
                if not lst or any(float(x) != int(x) or int(x) < 0 or int(x) > int(caps[n]) for x in lst):
                    raise ValueError(f"train.variants.{v['name']}.{blk}.{n} must be integers 0..world.slots.{n}: {lst}")


def check_r9_config(cfg: dict) -> dict:
    """Required keys and a few range checks. No defaults — every value is written in the YAML (R8 rule)."""
    for sec, keys in REQUIRED.items():
        if sec not in cfg or not isinstance(cfg[sec], dict):
            raise ValueError(f"R9 config has no '{sec}' block")
        miss = [k for k in keys if k not in cfg[sec]]
        if miss:
            raise ValueError(f"R9 config '{sec}' misses keys {miss}")
    names = species_of(cfg)
    for sp in names[len(SPECIES):]:
        for path in NEW_SPECIES_SECTIONS:
            d = cfg
            for part in path.split("."):
                d = d.get(part, {}) if isinstance(d, dict) else {}
            if not isinstance(d, dict) or sp not in d:
                raise ValueError(f"R9 config: new species {sp!r} needs {path}.{sp}")
    for sp in names:
        miss = [k for k in SPECIES_KEYS if k not in cfg["species"][sp]]
        if miss:
            raise ValueError(f"R9 config species.{sp} misses keys {miss}")
    old = [k for k in REMOVED_COMMON_KEYS if k in cfg["body_common"]]
    if old:
        raise ValueError(f"body_common {old}: the S′ world has no EAT walk (EAT = stand and eat here) — remove these keys")
    eat_r = float(cfg["body_common"]["carcass"]["eat_r"])
    if eat_r != float(OBS_NORM["here_r"]):
        # S′ 검토 low: '발밑 사체' has one meaning — the observation's food_here / food_dir boundary (here_r, a code literal in the I/O
        # contract) must be the distance EAT actually eats a carcass from, or the sense would disagree with the body.
        raise ValueError(f"body_common.carcass.eat_r {eat_r} must equal the observation here_r {OBS_NORM['here_r']} (food_here · food_dir)")
    w = cfg["world"]
    if w["mode"] not in ("train", "judge"):
        raise ValueError(f"world.mode must be train|judge: {w['mode']!r}")
    if int(w["decision_steps"]) != DECISION_STEPS:
        raise ValueError(f"world.decision_steps is part of the I/O contract and must be {DECISION_STEPS}")
    if int(w["quadrants"]) not in (1, 4):
        raise ValueError(f"world.quadrants must be 1 or 4: {w['quadrants']}")
    for sp in names:
        cap = int(w["slots"][sp])
        lo, hi = (int(x) for x in cfg["counts"][sp])
        if not (0 <= lo <= hi <= cap):
            raise ValueError(f"counts.{sp} {cfg['counts'][sp]} must satisfy 0 ≤ lo ≤ hi ≤ world.slots.{sp} = {cap}")
        if max(int(x) for x in cfg["learner_counts"][sp]) > cap:
            raise ValueError(f"learner_counts.{sp} exceeds world.slots.{sp} = {cap}")
        s = cfg["species"][sp]
        for d in s["diet"]:
            if d not in FOODS:
                raise ValueError(f"species.{sp}.diet has unknown food {d!r}")
            if d not in s["eat_rate"] or d not in s["e_per_unit"]:
                raise ValueError(f"species.{sp}: diet {d!r} needs eat_rate and e_per_unit")
        for p in s["bites"]:
            if p not in names or p == sp:
                raise ValueError(f"species.{sp}.bites must name other species: {s['bites']}")
        if s["founder"] not in ("plain", "natural") or s["growth"] not in ("smooth", "linear"):
            raise ValueError(f"species.{sp}: founder plain|natural, growth smooth|linear")
        if s["sex"] not in ("none", "natural", "alternate"):
            raise ValueError(f"species.{sp}.sex must be none|natural|alternate")
        if s["child_ring"]["center"] not in ("parent_a", "midpoint"):
            raise ValueError(f"species.{sp}.child_ring.center must be parent_a|midpoint")
        action_mask(s["pair_block"])
        action_mask(s["birth_block"])
    lo, hi = (int(x) for x in cfg["train"]["seeds"])
    if not (lo < hi):
        raise ValueError(f"train.seeds [lo, hi) is empty: {cfg['train']['seeds']}")
    tg = cfg["food"]["train_grass_total"]
    if tg is not None and not float(tg) > 0.0:
        raise ValueError(f"food.train_grass_total must be null or > 0: {tg}")
    _check_fauna(cfg, names)
    _check_motion(cfg, names)
    _check_variants(cfg, names)
    if w["mode"] == "judge":
        if "judge" not in cfg or not isinstance(cfg["judge"], dict):
            raise ValueError("judge mode needs a 'judge' block")
        miss = [k for k in JUDGE_KEYS if k not in cfg["judge"]]
        if miss:
            raise ValueError(f"R9 config 'judge' misses keys {miss}")
        if cfg["food"]["quadrant_grass_total"] is None:
            raise ValueError("judge mode needs food.quadrant_grass_total")
    return cfg


def load_r9_config(path) -> dict:
    """R9 YAML. A top-level `inherit: file` (same folder) is read first and overridden by this file (R8 `load_r8_config`)."""
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "inherit" in raw:
        base = load_r9_config(p.parent / raw.pop("inherit"))
        base.pop("_path", None)
        raw = _deep_merge(base, raw)
    raw["_path"] = str(p)
    return check_r9_config(raw)


def override(cfg: dict, patch: dict) -> dict:
    """Checked copy of cfg with patch merged in (variants such as judge L0/L1, calibration candidates)."""
    out = _deep_merge(cfg, patch)
    return check_r9_config(out)


# --------------------------------------------------------------------------- #
# body table (3-3)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Body:
    """Body table expanded to (n_species,) arrays (index = species number). (n_species, n_foods) / (n_species, n_actions) where noted.

    Derived values: size0 = (mass/60)^(1/3); reserve_cap = reserve_days × 900 × drain; stam_drain = (1 − lock)/run_steps per
    effective RUN step; stam_recover = (unlock − lock)/recover_steps per non-RUN step; fov_cos = cos(fov/2) (computed once here,
    never inside a step); hp_regen = hp_regen_per_day / 900 per step.
    """
    mass_kg: np.ndarray
    size0: np.ndarray
    founder_kind: np.ndarray          # FOUNDER_PLAIN | FOUNDER_NATURAL
    founder_variation: np.ndarray     # natural only (0 for plain)
    growth_smooth: np.ndarray         # bool
    walk_speed: np.ndarray
    run_speed: np.ndarray
    run_mult_lo: np.ndarray           # per-world run multiplier range (wolf U[0.90, 1.05], others 1)
    run_mult_hi: np.ndarray
    accel: np.ndarray                 # max |Δ self velocity| per step
    stam_run_steps: np.ndarray
    stam_recover_steps: np.ndarray
    stam_drain: np.ndarray
    stam_recover: np.ndarray
    see_r: np.ndarray
    fov_deg: np.ndarray
    fov_cos: np.ndarray
    head_down: np.ndarray
    smell_r: np.ndarray
    drain: np.ndarray                 # walking metabolism E/step (× gait_drain × maintenance)
    reserve_days: np.ndarray
    reserve_cap: np.ndarray           # C in reward Δ(E + R × C)
    refill_e: np.ndarray
    refill_frac: np.ndarray
    weak_e: np.ndarray
    weak_speed: np.ndarray
    eats: np.ndarray                  # (S, F) bool
    diet_order: tuple                 # per species tuple of food numbers in priority order
    eat_rate: np.ndarray              # (S, F) food units per standing step (0 if not eaten)
    e_per_unit: np.ndarray            # (S, F) E per food unit (0 if not eaten)
    has_hp: np.ndarray                # bool
    hp_regen: np.ndarray              # per step
    shelter_enter: np.ndarray         # bool
    bites: np.ndarray                 # (S, S) bool [biter, bitten]
    can_bite: np.ndarray              # bool
    bite_r: np.ndarray                # × g_size × growth
    counter: np.ndarray               # bool (frontal counter when bitten)
    maturity: np.ndarray              # steps
    sex_mode: np.ndarray              # SEXMODE_*
    female_frac: np.ndarray
    child_female_frac: np.ndarray
    max_founder_age: np.ndarray       # steps
    first_birth_base: np.ndarray      # steps after founding / respawn
    first_birth_spread: np.ndarray    # × Unit(S_q ^ uid)
    mate_r: np.ndarray
    birth_r: np.ndarray
    birth_grace: np.ndarray           # steps a due birth may wait for eligibility (boar 150)
    pair_block: np.ndarray            # (S, A) bool: decision actions that block pairing
    birth_block: np.ndarray           # (S, A) bool: decision actions that block delivery
    pending_needs_parent: np.ndarray  # bool: pending checks E·HP eligibility (deer, wolf) or alive·quadrant only (boar)
    child_center: np.ndarray          # CHILD_AT_*
    child_r0: np.ndarray
    child_dr: np.ndarray
    child_avoid_shelter: np.ndarray   # bool
    food_density_ref: np.ndarray
    food_here_ref: np.ndarray
    # 동물 세계 (9-2). Without body_common.fauna: names = the three, fauna False and the neutral values below (unused by the old
    # code paths — the world keeps its S′ lines literally, B4).
    names: tuple = SPECIES            # species of the config (ALL_SPECIES prefix), index = species number
    n: int = N_SPECIES
    fauna: bool = False
    bite_k: np.ndarray | None = None  # R1 teeth strength (0 = no teeth)
    hide: np.ndarray | None = None    # R1 hide (divides the wound)
    strike_k: np.ndarray | None = None   # R1 horns / tusks (counter and gore)
    gore: np.ndarray | None = None    # R2 bool
    gore_r: np.ndarray | None = None  # R2 reach × g_size × growth
    camo: np.ndarray | None = None    # R3 (1 = plain)
    recover: np.ndarray | None = None  # R7 steps from a delivery to the next breeding (= body_common.breed.recover without fauna)
    c23: np.ndarray | None = None     # R1 (n, n) (kg_s / kg_t)^(2/3), computed once here (no transcendental inside a step)
    # 몸 움직임 (RL_R9_TURN_EFFORT_DESIGN.md 3-1·6-1). Without body_common.motion: motion False and None (the old lines stay literal).
    motion: bool = False              # body_common.motion block present (v0 with |v0| ≤ EPS → 0 in `_move`)
    motion_turn: bool = False         # M1 turn limit on
    motion_effort: bool = False       # M2 — not implemented (the config check refuses effort: true)
    turn_c: np.ndarray | None = None  # M1 cos Δb, Δb = turn_dps × STEP_S in radians (computed once here — no trig inside a step)
    turn_s: np.ndarray | None = None  # M1 sin Δb
    lat_u: np.ndarray | None = None   # M1 sideways acceleration lat_accel_mps2 / 112.5 (units/step²)
    common: dict = field(default_factory=dict)   # body_common block as read (floats/ints/lists/dicts)

    @property
    def plant_eater(self) -> np.ndarray:
        """Species counted as plant eaters in the judge birth budget (3-7 출생 예산): eats grass."""
        return self.eats[:, GRASS].copy()


def _f(x) -> float:
    return float(x)


# S′ 검토 low (C++ 옮김): eye field-of-view cos = cos(fov/2) as float64 literals, so the Unreal port uses the same bits instead of its
# own trig (math.radians(125) vs 125·π/180 already differ by 3 ulp; UE's float PI more). Values = math.cos(math.radians(fov / 2)) —
# the form used for any fov not listed (calibration never changes fov). Test: tests/test_r9_body.py pins the bits.
FOV_COS_LITERAL = {
    300.0: -0.8660254037844387,     # deer, boar (-0x1.bb67ae8584cabp-1)
    250.0: -0.5735764363510462,     # wolf       (-0x1.25abcf87c4979p-1)
    200.0: -0.1736481776669303,     # leopard (동물 1 단계) = math.cos(math.radians(100.0))
    260.0: -0.6427876096865394,     # fox     (동물 1 단계) = math.cos(math.radians(130.0))
}


def fov_cos_of(fov_deg: float) -> float:
    """cos(fov/2): the literal table above, else math.cos(math.radians(fov/2)) (the same form the literals were taken from)."""
    f = float(fov_deg)
    return FOV_COS_LITERAL[f] if f in FOV_COS_LITERAL else math.cos(math.radians(f / 2.0))


def load_body(cfg: dict) -> Body:
    """Body table from cfg['species'] and cfg['body_common'] (3-3). Species = `species_of(cfg)` (S′: the three)."""
    names = species_of(cfg)
    nsp = len(names)
    sp_cfg = [cfg["species"][n] for n in names]
    cm = cfg["body_common"]
    fauna = cm.get("fauna") is not None
    lock, unlock = _f(cm["stamina_lock"]), _f(cm["stamina_unlock"])
    arr = lambda key, conv=_f: np.array([conv(s[key]) for s in sp_cfg], dtype=np.float64)  # noqa: E731
    barr = lambda key: np.array([bool(s[key]) for s in sp_cfg], dtype=bool)  # noqa: E731
    mass = arr("mass_kg")
    drain = arr("drain")
    run_steps, rec_steps = arr("stamina_run_steps"), arr("stamina_recover_steps")
    eats = np.zeros((nsp, N_FOODS), dtype=bool)
    rate = np.zeros((nsp, N_FOODS))
    epu = np.zeros((nsp, N_FOODS))
    order = []
    for i, s in enumerate(sp_cfg):
        o = []
        for d in s["diet"]:
            fi = FOODS.index(d)
            eats[i, fi] = True
            rate[i, fi] = _f(s["eat_rate"][d])
            epu[i, fi] = _f(s["e_per_unit"][d])
            o.append(fi)
        order.append(tuple(o))
    bites = np.zeros((nsp, nsp), dtype=bool)
    for i, s in enumerate(sp_cfg):
        for p in s["bites"]:
            bites[i, SPECIES_INDEX[p]] = True
    if fauna:
        fz = dict(bite_k=arr("bite_k"), hide=arr("hide"), strike_k=arr("strike_k"), gore=barr("gore"), gore_r=arr("gore_r"),
                  camo=arr("camo"), recover=arr("recover"),
                  c23=np.array([[(float(a) / float(b)) ** (2.0 / 3.0) for b in mass] for a in mass], dtype=np.float64))
    else:
        fz = dict(bite_k=np.zeros(nsp), hide=np.ones(nsp), strike_k=np.zeros(nsp), gore=np.zeros(nsp, dtype=bool),
                  gore_r=np.zeros(nsp), camo=np.ones(nsp), recover=np.full(nsp, _f(cm["breed"]["recover"])), c23=None)
    mo = cm.get("motion")
    mz = dict(motion=mo is not None, motion_turn=bool(mo is not None and mo["turn"]),
              motion_effort=bool(mo is not None and mo["effort"]))
    if mz["motion_turn"]:
        # 회전 한계 (설계 3-1): 삼각함수는 불러올 때 이곳에서 한 번만 — 장면 덤프가 %.17g 로 실어 C++ 도 같은 비트를 쓴다
        ang = [math.radians(_f(s["turn_dps"]) * STEP_S) for s in sp_cfg]
        mz.update(turn_c=np.array([math.cos(a) for a in ang], dtype=np.float64),
                  turn_s=np.array([math.sin(a) for a in ang], dtype=np.float64),
                  lat_u=arr("lat_accel_mps2") / MPS2_PER_UNIT)
    fov = arr("fov_deg")
    ring = [s["child_ring"] for s in sp_cfg]
    fvar = np.array([0.0 if s["founder"] == "plain" else _f(s["founder_variation"]) for s in sp_cfg])
    return Body(
        mass_kg=mass,
        size0=(mass / 60.0) ** (1.0 / 3.0),
        founder_kind=np.array([FOUNDER_NATURAL if s["founder"] == "natural" else FOUNDER_PLAIN for s in sp_cfg], dtype=np.int64),
        founder_variation=fvar,
        growth_smooth=np.array([s["growth"] == "smooth" for s in sp_cfg], dtype=bool),
        walk_speed=arr("walk_speed"),
        run_speed=arr("run_speed"),
        run_mult_lo=np.array([_f(s["run_mult"][0]) for s in sp_cfg]),
        run_mult_hi=np.array([_f(s["run_mult"][1]) for s in sp_cfg]),
        accel=arr("accel"),
        stam_run_steps=run_steps,
        stam_recover_steps=rec_steps,
        stam_drain=(1.0 - lock) / run_steps,
        stam_recover=(unlock - lock) / rec_steps,
        see_r=arr("see_r"),
        fov_deg=fov,
        fov_cos=np.array([fov_cos_of(x) for x in fov]),
        head_down=arr("head_down"),
        smell_r=arr("smell_r"),
        drain=drain,
        reserve_days=arr("reserve_days"),
        reserve_cap=arr("reserve_days") * DAY_STEPS * drain,
        refill_e=arr("refill_e"),
        refill_frac=arr("refill_frac"),
        weak_e=arr("weak_e"),
        weak_speed=arr("weak_speed"),
        eats=eats,
        diet_order=tuple(order),
        eat_rate=rate,
        e_per_unit=epu,
        has_hp=barr("has_hp"),
        hp_regen=arr("hp_regen_per_day") / DAY_STEPS,
        shelter_enter=barr("shelter_enter"),
        bites=bites,
        can_bite=bites.any(1),
        bite_r=arr("bite_r"),
        counter=barr("counter"),
        maturity=arr("maturity_steps"),
        sex_mode=np.array([{"none": SEXMODE_NONE, "natural": SEXMODE_NATURAL, "alternate": SEXMODE_ALTERNATE}[s["sex"]]
                           for s in sp_cfg], dtype=np.int64),
        female_frac=arr("female_frac"),
        child_female_frac=arr("child_female_frac"),
        max_founder_age=arr("max_founder_age_steps"),
        first_birth_base=np.array([_f(s["first_birth"][0]) for s in sp_cfg]),
        first_birth_spread=np.array([_f(s["first_birth"][1]) for s in sp_cfg]),
        mate_r=arr("mate_r"),
        birth_r=arr("birth_r"),
        birth_grace=arr("birth_grace_steps"),
        pair_block=np.stack([action_mask(s["pair_block"]) for s in sp_cfg]),
        birth_block=np.stack([action_mask(s["birth_block"]) for s in sp_cfg]),
        pending_needs_parent=barr("pending_needs_parent"),
        child_center=np.array([CHILD_AT_PARENT_A if r["center"] == "parent_a" else CHILD_AT_MIDPOINT for r in ring], dtype=np.int64),
        child_r0=np.array([_f(r["r0"]) for r in ring]),
        child_dr=np.array([_f(r["dr"]) for r in ring]),
        child_avoid_shelter=np.array([bool(r["avoid_shelter"]) for r in ring], dtype=bool),
        food_density_ref=arr("food_density_ref"),
        food_here_ref=arr("food_here_ref"),
        names=tuple(names),
        n=nsp,
        fauna=fauna,
        **fz,
        **mz,
        common=copy.deepcopy(cm),
    )


# Per-slot fields `expand_body` gathers (K, S) [or (K, S, F) for the food arrays]. The observation function reads these and
# kin_id — never the species number (4-4, 4-6, test 2·3).
SLOT_FIELDS = ("size0", "growth_smooth", "walk_speed", "run_speed", "accel", "stam_drain", "stam_recover", "see_r", "fov_cos",
               "head_down", "smell_r", "drain", "reserve_cap", "refill_e", "refill_frac", "weak_e", "weak_speed", "has_hp",
               "hp_regen", "shelter_enter", "can_bite", "bite_r", "counter", "maturity", "mass_kg", "food_density_ref",
               "food_here_ref", "mate_r", "birth_r")
SLOT_FOOD_FIELDS = ("eats", "eat_rate", "e_per_unit")
# 동물 세계 칸 (9-2) — expand_body adds them only when body.fauna (the S′ `sb` dict keeps its keys).
SLOT_FAUNA_FIELDS = ("bite_k", "hide", "strike_k", "gore", "gore_r", "camo")
# 몸 움직임 칸 (TURN_EFFORT 7-1) — expand_body adds the turn fields only when body.motion_turn (M2 칸은 M2 를 정한 뒤).
SLOT_MOTION_FIELDS = ("turn_c", "turn_s", "lat_u")


def expand_body(body: Body, sp: np.ndarray) -> dict[str, np.ndarray]:
    """Gather body values for a species-number array sp (any shape, e.g. (K, S)) → {field: array of sp.shape} and
    {food field: array of sp.shape + (F,)}. Empty slots still carry their block's species (slots never change species)."""
    sp = np.asarray(sp, dtype=np.int64)
    out = {f: getattr(body, f)[sp] for f in SLOT_FIELDS}
    for f in SLOT_FOOD_FIELDS:
        out[f] = getattr(body, f)[sp]
    if body.fauna:
        for f in SLOT_FAUNA_FIELDS:
            out[f] = getattr(body, f)[sp]
    if body.motion_turn:
        for f in SLOT_MOTION_FIELDS:
            out[f] = getattr(body, f)[sp]
    return out


# --------------------------------------------------------------------------- #
# contract hashes (7-10, 14-2)
# --------------------------------------------------------------------------- #

BODY_CONTRACT = "eco_r9_body"
IO_CONTRACT = "eco_r9_io"
CONTRACT_VERSION = 1


def _canon(v: Any) -> Any:
    """Canonical JSON value: numbers → float (YAML 60 and 60.0 hash the same), dicts sorted by json.dumps, tuples → lists."""
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    if isinstance(v, dict):
        return {str(k): _canon(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_canon(x) for x in v]
    raise TypeError(f"cannot hash value {v!r} of type {type(v)}")


def _h64(d: dict) -> int:
    s = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], 16)


def hash_hex(h: int) -> str:
    return f"0x{int(h):016x}"


def body_contract_dict(cfg: dict, sp: int | str) -> dict:
    """Body contract of one species = its species block + body_common (both worlds read the same values)."""
    name = ALL_SPECIES[int(sp)] if isinstance(sp, (int, np.integer)) else str(sp)
    if name not in ALL_SPECIES or name not in cfg["species"]:
        raise ValueError(f"unknown species {sp!r} (config species {list(cfg['species'])})")
    return {"contract": BODY_CONTRACT, "version": CONTRACT_VERSION, "species": name,
            "body": _canon(cfg["species"][name]), "common": _canon(cfg["body_common"])}


def body_hash(cfg: dict, sp: int | str) -> int:
    """uint64 body hash of one species (npz brains carry it; the world rejects a brain whose species hash differs — test 27)."""
    return _h64(body_contract_dict(cfg, sp))


def body_table_hash(cfg: dict) -> int:
    """uint64 hash of all species blocks of the config + common (recorded in brain meta: the bodies the brain was trained against).
    S′ configs: the same dict as before (the three species)."""
    return _h64({"contract": BODY_CONTRACT + "_table", "version": CONTRACT_VERSION,
                 "species": {n: _canon(cfg["species"][n]) for n in species_of(cfg)}, "common": _canon(cfg["body_common"])})


def io_contract_dict() -> dict:
    """I/O contract shared by all three species (4·5절, 7-10): observation names/normalisation, action names, decision phase,
    net shape and selection rule. No species, no weights."""
    return {
        "contract": IO_CONTRACT,
        "version": CONTRACT_VERSION,
        "obs_names": list(OBS_NAMES),
        "obs_norm": _canon(OBS_NORM),
        "sense": _canon(SENSE),
        "obs_spec": dict(OBS_SPEC),
        "obs_clip": [-1.0, 1.0],
        "obs_dtype": "float32",
        "n_other": N_OTHER,
        "n_kin": N_KIN,
        "slot_order": "perceived, distance ascending, ties lower slot (stable sort over gathered alive slots in slot order)",
        "actions": list(ACTION_NAMES),
        "directions": {"rule": "head rotated ccw by j*45deg", "table": _canon(DIR8.tolist())},
        "decision_steps": DECISION_STEPS,
        "decision_phase": "global t mod 2 == 0",
        "net": {"obs_dim": OBS_DIM, "hidden": [64, 64], "activation": "tanh", "n_actions": N_ACTIONS, "head": "logits"},
        "select": "argmax_lowest_index",
        "mask": None,
    }


def io_hash() -> int:
    return _h64(io_contract_dict())
