"""R9 brains — fixed MLP brains (npz), rule brains (7-5) and the per-world same-shape block decision (7-10).

Owner: brains agent. Tests: tests/test_r9_brains.py (12절 16·27 + rule brains on hand observations). The world never needs these to
step — `R9World.step(actions)` takes actions from outside; `R9World.act()` (order 0) is the only caller.

Contract (impl_contract.md §7)
  - Every brain reads the same 115 observation columns (r9_body.OBS_NAMES, float32) and returns one of 19 actions. No species
    number, no hidden state of others. Rule thresholds compare observation values (normalised, 4절; distances in units / 20).
  - Rule brains (7-5, S′ 'S4' 2026-11-12) are yardsticks, not learners: rules are allowed, but they read the observation only (and
    their own memory). In the S′ world EAT eats only what is here and SHELTER stands, so a rule that wants food walks toward the
    largest food_dir column and a rule that wants a shelter walks / runs toward shelter_x·shelter_y — the world never walks for them.
  - `decide_block(ctrl, obs_block, rng, state, ctx)` is called by the world ONCE PER WORLD PER SPECIES with the block
    obs[k, lo_sp:hi_sp] (n = that species' slot cap, dead slots included) so the MKL result does not depend on how many worlds are
    batched (7-10, test 21). It ALWAYS draws `rng.random((n, N_ACTIONS))` first, whatever the brain kind and mode, so swapping
    brains or modes never shifts another stream (3-9, test 27).
  - Stochastic: Gumbel-max a = argmax(z), z = float64(logit) + g, g = −log(−log u) (float64). Greedy: argmax(logits) on the float32
    logits. Ties → lowest index (np.argmax). Rule brains ignore `stochastic` (RANDOM uses u: argmax(u) = uniform over 19).
  - Near ties (7-10): `gap` = difference of the two largest values the decision maximised (greedy: logits, stochastic: z). The
    world counts gap < NEAR_TIE. Rule brains return inf.
  - npz: weights W0 (64, 115), B0 (64,), W1 (64, 64), B1, W2 (19, 64), B2 (19,) float32 + `meta_json` (0-d unicode array, no
    pickle): format, species, branch, round, decisions, obs_names, action_names, io_hash, body_hash, body_table_hash,
    src_zip_sha256, config_digest. `load_brain` rejects format / shape / name / io_hash / species / body_hash (of that species in
    the world config) mismatches with BrainContractError (test 27).
  - Rule-brain memory (RULE_BOAR flee count-down and face-off flag, RULE_WOLF stamina-lock copy, and for every S4 rule two 'stuck'
    columns: last decision was EAT, food_here × 1e6 then) is int64 (n, n_state) per slot.
    The world keeps it per world·species (bstate[k][sp], zeroes a row when a slot is reset — `Brain.reset_state`). When `state` is
    None the brain uses its own array (`Brain.state`, one world; `Brain.reset(rows)` clears rows) — for tests and single-world use.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import r9_body as B
from .r9_body import (ACTION_NAMES, DIR8, EAT, N_ACTIONS, O_AGE_FRAC, O_ENERGY, O_FOOD_HERE, O_FREE0, O_HEALTH, O_IN_SHELTER,
                      O_SHELTER_EDGE, O_SHELTER_X, O_SHELTER_Y, O_STAMINA, OBS_DIM, OBS_NAMES, RUN_FIRST, RUN_LAST, SHELTER,
                      SL_FOOD_DIR, SPECIES, WALK_FIRST, WALK_LAST, WATCH, kin_col, other_col)

HIDDEN = 64
NPZ_FORMAT = "eco_r9_brain"
NPZ_FORMAT_VERSION = 1
NPZ_WEIGHT_KEYS = ("W0", "B0", "W1", "B1", "W2", "B2")
NPZ_SHAPES = {"W0": (HIDDEN, OBS_DIM), "B0": (HIDDEN,), "W1": (HIDDEN, HIDDEN), "B1": (HIDDEN,), "W2": (N_ACTIONS, HIDDEN),
              "B2": (N_ACTIONS,)}
META_KEYS = ("species", "branch", "round", "decisions", "obs_names", "action_names", "io_hash", "body_hash", "body_table_hash",
             "src_zip_sha256", "config_digest")

# 7-5 (S′ S4). NOHUNT · NOHUNT_RUN = wolf negative controls of C0-10 (never go to live prey; walk / run toward the sensed carcass).
# RULE_NAMES keeps the S′ meaning (the S′ rule set the eval tools and the old tests walk — 동물 9-1 B6, like r9_body.SPECIES).
# 동물 세계 1 단계 (RL_R9_SPECIES_TRAITS.md 6-4): RULE_BUFFALO · RULE_LEOPARD · RULE_FOX (FAUNA_RULE_NAMES) — yardsticks and round-0
# opponents only, observation columns only (no species label exists in the observation); they need rules.<species> in the config.
RULE_NAMES = ("RULE_DEER", "RULE_BOAR", "RULE_WOLF", "HIDE_DEER", "HIDE_BOAR", "ALWAYS_EAT", "RANDOM", "NOHUNT", "NOHUNT_RUN")
FAUNA_RULE_NAMES = ("RULE_BUFFALO", "RULE_LEOPARD", "RULE_FOX")
ALL_RULE_NAMES = RULE_NAMES + FAUNA_RULE_NAMES
RULE_SPECIES = {"RULE_DEER": B.DEER, "RULE_BOAR": B.BOAR, "RULE_WOLF": B.WOLF, "HIDE_DEER": B.DEER, "HIDE_BOAR": B.BOAR,
                "ALWAYS_EAT": None, "RANDOM": None, "NOHUNT": B.WOLF, "NOHUNT_RUN": B.WOLF,
                "RULE_BUFFALO": B.BUFFALO, "RULE_LEOPARD": B.LEOPARD, "RULE_FOX": B.FOX}
RULE_CFG = {"RULE_DEER": "deer", "RULE_BOAR": "boar", "RULE_WOLF": "wolf", "HIDE_DEER": "hide", "HIDE_BOAR": "hide", "NOHUNT": "wolf",
            "NOHUNT_RUN": "wolf", "RULE_BUFFALO": "buffalo", "RULE_LEOPARD": "leopard", "RULE_FOX": "fox"}
RULE_N_BASE = {"RULE_BOAR": 3, "RULE_WOLF": 1, "RULE_LEOPARD": 1}   # rule-specific memory columns; every rule adds the 2 stuck columns
N_STUCK = 2
RULE_N_STATE = {n: RULE_N_BASE.get(n, 0) + N_STUCK for n in ALL_RULE_NAMES}
NEAR_TIE = 1e-5                     # 7-10: decisions whose top-2 gap < 1e-5 are counted

# RULE_BOAR state columns · RULE_WOLF state column
BS_FLEE_LEFT, BS_FACED, BS_FLEE_DIR = 0, 1, 2
WS_LOCKED = 0
PATROL_FREE_MIN = 0.2               # [어림] RULE_WOLF hungry without a target walks straight; if free_0 ≤ this, toward the freest side
FLOW_MIN = 0.1                      # [어림] search: follow the kin flow when |kin_flow| (/0.6) > this (mean displacement 0.06 units/step)
KIN_FAR = 5.0                       # [어림] search without flow: toward the nearest kin when it is farther than this (units)
STUCK_Q = 1e6                       # food_here in the int64 memory at 1e-6 resolution (eating lowers it ≥ 0.008 per decision)

POS_N = float(B.OBS_NORM["pos"])     # 20: observation distance unit

# observation columns used by the rules
_OC = {f: np.array([other_col(j, f) for j in range(B.N_OTHER)]) for f in B.OBS_OTHER_FIELDS}       # 31 + 11 j + field
_KC = {f: np.array([kin_col(j, f) for j in range(B.N_KIN)]) for f in B.OBS_KIN_FIELDS}
_FREE = np.arange(O_FREE0, O_FREE0 + 8)


class BrainContractError(ValueError):
    """npz brain does not match the world's I/O contract or the species body hash."""


# --------------------------------------------------------------------------- #
# numerics
# --------------------------------------------------------------------------- #

def forward_np(weights: dict, obs: np.ndarray) -> np.ndarray:
    """logits = W2·tanh(W1·tanh(W0·x + B0) + B1) + B2 in float32 (export_weights_v3.forward_np form). One call per world block."""
    x = np.asarray(obs, dtype=np.float32)
    h1 = np.tanh(x @ weights["W0"].T + weights["B0"])
    h2 = np.tanh(h1 @ weights["W1"].T + weights["B1"])
    return h2 @ weights["W2"].T + weights["B2"]


def gumbel_values(logits: np.ndarray, u: np.ndarray) -> np.ndarray:
    """z = float64(logits) + (−log(−log u)) — the perturbed values Gumbel-max maximises. u = 0 gives −inf (never chosen)."""
    with np.errstate(divide="ignore"):
        g = -np.log(-np.log(np.asarray(u, dtype=np.float64)))
    return np.asarray(logits, dtype=np.float64) + g


def gumbel_argmax(logits: np.ndarray, u: np.ndarray) -> np.ndarray:
    """argmax(logits + (−log(−log u))) per row, ties lowest index (7-4 확률 행동 = softmax 표본)."""
    return np.argmax(gumbel_values(logits, u), axis=1).astype(np.int64)


def top_gap(values: np.ndarray) -> np.ndarray:
    """(n,) gap between the two largest values per row (float64; 7-10 near-tie count)."""
    s = np.sort(np.asarray(values, dtype=np.float64), axis=1)
    with np.errstate(invalid="ignore"):
        return s[:, -1] - s[:, -2]


def _dir_index(vx: np.ndarray, vy: np.ndarray, free: np.ndarray | None = None, free_min: float = 0.0) -> np.ndarray:
    """Direction index j (0..7) whose DIR8[j] is closest to (vx, vy) in the self frame (largest cosine — R8 rule_actions without
    arctan2/cos: dot of the unit vector with the literal table). With `free`, directions whose free_j ≤ free_min lose 10 (R8:
    'cosj − 10'), so the closest open direction wins; ties → lowest j."""
    vx = np.asarray(vx, dtype=np.float64)
    vy = np.asarray(vy, dtype=np.float64)
    n = np.sqrt(vx * vx + vy * vy)
    inv = np.where(n > 0, 1.0 / np.where(n > 0, n, 1.0), 0.0)
    c = (vx * inv)[:, None] * DIR8[None, :, 0] + (vy * inv)[:, None] * DIR8[None, :, 1]
    if free is not None:
        c = np.where(np.asarray(free, dtype=np.float64) > free_min, c, c - 10.0)
    return np.argmax(c, axis=1).astype(np.int64)


def _first(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(has, index) of the first True per row (other/kin slots are sorted nearest first)."""
    return mask.any(1), np.argmax(mask, axis=1)


def _take(o: np.ndarray, cols: np.ndarray, j: np.ndarray) -> np.ndarray:
    return o[np.arange(o.shape[0]), cols[j]]


# --------------------------------------------------------------------------- #
# brains
# --------------------------------------------------------------------------- #

@dataclass
class Brain:
    """Base brain. `kind` = 'mlp' | 'rule'. `n_state` = int64 columns of per-slot state the brain keeps (rule brains: flee count-
    down etc.); the world stores state[k][sp] (n_slots, n_state) and zeroes rows when a slot is reset (respawn / birth)."""
    name: str
    kind: str
    species: int | None = None      # trained species (mlp) or the intended species (rule; None = any)
    n_state: int = 0
    state: np.ndarray | None = field(default=None, repr=False)   # own memory when the caller passes state=None

    def logits(self, obs: np.ndarray) -> np.ndarray | None:
        """(n, 115) float32 → (n, 19) float32 logits; rule brains return None."""
        return None

    def new_state(self, n: int) -> np.ndarray:
        return np.zeros((int(n), self.n_state), np.int64)

    @staticmethod
    def reset_state(state: np.ndarray | None, rows) -> None:
        """Zero the memory rows of reset slots (respawn / birth into a slot)."""
        if state is not None and state.size:
            state[np.asarray(rows, dtype=np.int64)] = 0

    def reset(self, rows=None) -> None:
        """Clear the brain's own memory (all rows, or the given rows)."""
        if self.state is None:
            return
        if rows is None:
            self.state[...] = 0
        else:
            self.reset_state(self.state, rows)

    def _mem(self, n: int, state: np.ndarray | None) -> np.ndarray:
        if self.n_state == 0:
            return np.zeros((n, 0), np.int64)
        if state is None:
            if self.state is None or self.state.shape != (n, self.n_state):
                self.state = self.new_state(n)
            state = self.state
        if state.shape != (n, self.n_state) or state.dtype != np.int64:
            raise ValueError(f"{self.name}: state must be int64 ({n}, {self.n_state}), got {state.dtype} {state.shape}")
        return state

    def act(self, obs: np.ndarray, u: np.ndarray, stochastic: bool, state: np.ndarray | None, ctx: dict) -> np.ndarray:
        """(n, 115) float32 obs, (n, 19) float64 uniforms (already drawn), per-slot state (n, n_state) int64 (mutated in place),
        ctx (e.g. {'facing_f': 0.9}) → actions (n,) int64 in 0..18."""
        return self.decide(obs, u, stochastic, state, ctx)[0]

    def decide(self, obs, u, stochastic, state, ctx) -> tuple[np.ndarray, np.ndarray]:
        """(actions (n,) int64, gap (n,) float64)."""
        raise NotImplementedError


@dataclass
class MlpBrain(Brain):
    weights: dict = field(default_factory=dict)   # W0..B2 float32
    meta: dict = field(default_factory=dict)

    def logits(self, obs: np.ndarray) -> np.ndarray:
        return forward_np(self.weights, obs)

    def decide(self, obs, u, stochastic, state, ctx):
        lg = self.logits(obs)
        if stochastic:
            z = gumbel_values(lg, u)
            return np.argmax(z, axis=1).astype(np.int64), top_gap(z)
        return np.argmax(lg, axis=1).astype(np.int64), top_gap(lg)


@dataclass
class RuleBrain(Brain):
    """S4 rule brain (observation only). params = cfg['rules'][...] thresholds (distances in units; the brain divides by POS_N) +
    here_min (the species' food_here threshold, `here_min_of`). Memory = the rule's own n_base columns, then 2 stuck columns:
    [last decision was EAT, food_here × 1e6 then] — EAT that did not lower food_here (nothing eatable here: food_here also counts
    residue below eat_min and mixed foods, so the threshold alone cannot tell) is 'stuck' and the seek goes on (time difference of
    the observation only). blind = [diagnostic] decide with the food_dir columns set to 0."""
    params: dict = field(default_factory=dict)
    n_base: int = 0
    blind: bool = False

    def decide(self, obs, u, stochastic, state, ctx):
        o = np.asarray(obs, dtype=np.float64)
        if o.ndim != 2 or o.shape[1] != OBS_DIM:
            raise ValueError(f"{self.name}: rule brains need ({OBS_DIM},) observations, got {o.shape}")
        if self.blind:
            o = o.copy()
            o[:, SL_FOOD_DIR] = 0.0
        n = o.shape[0]
        mem = self._mem(n, state)
        c0 = self.n_base
        fhq = np.round(o[:, O_FOOD_HERE] * STUCK_Q).astype(np.int64)
        p = dict(self.params)
        p["_stuck"] = (mem[:, c0] == 1) & (fhq >= mem[:, c0 + 1])
        a = np.asarray(_RULES[self.name](o, np.asarray(u, dtype=np.float64), mem[:, :c0], ctx or {}, p), dtype=np.int64)
        mem[:, c0] = (a == EAT).astype(np.int64)
        mem[:, c0 + 1] = fhq
        return a, np.full(n, np.inf)


@dataclass
class Controller:
    """Who decides one species block of one world (7-4): a brain + action mode. label: 'current' | 'past:<v>' | 'rule' | ..."""
    brain: Brain
    stochastic: bool
    label: str = ""


def decide_block(ctrl: Controller, obs_block: np.ndarray, rng: np.random.Generator, state: np.ndarray | None,
                 ctx: dict) -> tuple[np.ndarray, np.ndarray]:
    """One world × one species decision: u = rng.random((n, 19)) ALWAYS first, then ctrl.brain.decide(...).
    Returns (actions (n,) int64, gap (n,) float64 — inf for rule brains)."""
    obs = np.asarray(obs_block, dtype=np.float32)
    if obs.ndim != 2 or obs.shape[1] != OBS_DIM:
        raise ValueError(f"obs block must be (n, {OBS_DIM}), got {obs.shape}")
    u = rng.random((obs.shape[0], N_ACTIONS))
    a, gap = ctrl.brain.decide(obs, u, bool(ctrl.stochastic), state, ctx or {})
    return np.asarray(a, dtype=np.int64), np.asarray(gap, dtype=np.float64)


# --------------------------------------------------------------------------- #
# rule brains (7-5, S′ S4) — observation columns only
# --------------------------------------------------------------------------- #

_FD = SL_FOOD_DIR


def _search(o, p):
    """No food sensed at all — deterministic search from the observation: follow the kin flow, else toward a far nearest kin, else
    straight on (toward the freest side when the wall is within 2 units)."""
    free = o[:, _FREE]
    ks = B.KINSUM0
    cnt = o[:, ks] > 0.0
    fx, fy = o[:, ks + 2], o[:, ks + 3]
    flow_on = cnt & (fx * fx + fy * fy > FLOW_MIN * FLOW_MIN)
    j_flow = _dir_index(fx, fy, free, PATROL_FREE_MIN)
    kx, ky = o[:, kin_col(0, "rel_x")], o[:, kin_col(0, "rel_y")]
    kfar = (o[:, kin_col(0, "present")] > 0.5) & (kx * kx + ky * ky > (KIN_FAR / POS_N) ** 2)
    j_kin = _dir_index(kx, ky, free, PATROL_FREE_MIN)
    j_str = np.where(free[:, 0] > PATROL_FREE_MIN, 0, np.argmax(free, axis=1))
    j = np.where(flow_on, j_flow, np.where(kfar, j_kin, j_str))
    return WALK_FIRST + j


def seek_obs(o, p):
    """Food seeking: food_here ≥ here_min and not stuck → EAT; else WALK toward the largest food_dir column; nothing sensed →
    `_search`."""
    fh = (o[:, O_FOOD_HERE] >= p["here_min"]) & ~p.get("_stuck", np.zeros(o.shape[0], dtype=bool))
    fd = o[:, _FD]
    has = fd.max(1) > 0.0
    best = np.argmax(fd, axis=1)
    return np.where(fh, EAT, np.where(has, WALK_FIRST + best, _search(o, p)))


def _to_shelter(o, run=True):
    """(going action, inside, shelter direction known): inside → SHELTER (stand), outside → RUN (or WALK) toward shelter_x·y."""
    inside = o[:, O_IN_SHELTER] > 0.5
    sx, sy = o[:, O_SHELTER_X], o[:, O_SHELTER_Y]
    known = (sx * sx + sy * sy) > 0.25
    j = _dir_index(sx, sy)
    go = (RUN_FIRST if run else WALK_FIRST) + j
    return np.where(inside, SHELTER, np.where(known, go, SHELTER)), inside, known


def _rule_deer(o, u, mem, ctx, p):
    """RULE_DEER: nearest other within 15 and (facing > f and approach > 0.1), or within 10 and approach > 0.15 → flee: inside a
    shelter → SHELTER; shelter edge within 8 → RUN toward shelter_x·y; else the RUN direction closest to 'away' among free_j > 0.2.
    Otherwise E < 0.9 → food seeking (`seek_obs`), else WATCH. f = ctx['facing_f'] (train world U[0.8, 0.97]) else facing_eval 0.9."""
    f = float(ctx.get("facing_f", p["facing_eval"]))
    pres = o[:, other_col(0, "present")] > 0.5
    dist, appr, fac = o[:, other_col(0, "dist")], o[:, other_col(0, "approach")], o[:, other_col(0, "facing")]
    trig = pres & (((dist < p["near"] / POS_N) & (fac > f) & (appr > p["approach_far"]))
                   | ((dist < p["close"] / POS_N) & (appr > p["approach_close"])))
    j = _dir_index(-o[:, other_col(0, "rel_x")], -o[:, other_col(0, "rel_y")], o[:, _FREE], p["free_min"])
    go_sh, inside, known = _to_shelter(o, run=True)
    near_sh = o[:, O_SHELTER_EDGE] < p["shelter_edge"] / POS_N
    flee = np.where(inside, SHELTER, np.where(near_sh & known, go_sh, RUN_FIRST + j))
    idle = np.where(o[:, O_ENERGY] < p["full_e"], seek_obs(o, p), WATCH)
    return np.where(trig, flee, idle)


def _rule_boar(o, u, mem, ctx, p):
    """RULE_BOAR (Fauna flee 650 cm·1.5 s, offspring guard — EcoFaunaMovement.cpp 128~157·383~405):
      1 another within 3.25 runs at me (approach > 0.33) facing me (facing > 0.9): adult with HP ≥ 0.55 and a young kin
        (size < 0.45) within 2 → WALK toward it (face-off); else RUN away for 6 decisions (count-down in memory).
      2 flee count-down left → RUN away from the nearest perceived other (none: straight on, RUN_0, or the freest side).
      3 another within 3.25 walks in (0.1 < approach ≤ 0.33 [어림 approach_walk]) → one decision WALK toward it, then WATCH.
      4 otherwise E < 0.9 → food seeking (`seek_obs`), else WATCH."""
    near = p["near"] / POS_N
    pres = o[:, _OC["present"]] > 0.5
    dist, appr, fac = o[:, _OC["dist"]], o[:, _OC["approach"]], o[:, _OC["facing"]]
    run_thr = pres & (dist < near) & (appr > p["approach_run"]) & (fac > p["facing"])
    walk_thr = pres & (dist < near) & (appr > p["approach_walk"]) & (appr <= p["approach_run"])
    has_run, jr = _first(run_thr)
    has_walk, jw = _first(walk_thr)
    rx, ry = _take(o, _OC["rel_x"], jr), _take(o, _OC["rel_y"], jr)
    yr = p["young_r"] / POS_N
    krx, kry = o[:, _KC["rel_x"]], o[:, _KC["rel_y"]]
    young = (o[:, _KC["present"]] > 0.5) & (o[:, _KC["size"]] < p["young_size"]) & (krx * krx + kry * kry < yr * yr)
    defend = has_run & (o[:, O_AGE_FRAC] >= 1.0) & (o[:, O_HEALTH] >= p["guard_hp"]) & young.any(1)
    free = o[:, _FREE]
    j_toward = _dir_index(rx, ry)
    j_away = _dir_index(-rx, -ry, free, PATROL_FREE_MIN)
    # count-down flight: away from the nearest perceived other, else straight on (head follows the run)
    any_o = pres[:, 0]
    j_cont = np.where(any_o, _dir_index(-o[:, other_col(0, "rel_x")], -o[:, other_col(0, "rel_y")], free, PATROL_FREE_MIN),
                      np.where(free[:, 0] > PATROL_FREE_MIN, 0, np.argmax(free, axis=1)))
    jw_t = _dir_index(_take(o, _OC["rel_x"], jw), _take(o, _OC["rel_y"], jw))
    left = mem[:, BS_FLEE_LEFT]
    faced = mem[:, BS_FACED]
    cont = ~has_run & (left > 0)
    walk = ~has_run & ~cont & has_walk
    a = np.where(o[:, O_ENERGY] < p["full_e"], seek_obs(o, p), WATCH)
    a = np.where(walk, np.where(faced == 0, WALK_FIRST + jw_t, WATCH), a)
    a = np.where(cont, RUN_FIRST + j_cont, a)
    a = np.where(has_run, np.where(defend, WALK_FIRST + j_toward, RUN_FIRST + j_away), a)
    n_flee = int(p["flee_decisions"])
    mem[:, BS_FLEE_LEFT] = np.where(has_run, np.where(defend, 0, n_flee - 1), np.where(cont, left - 1, 0))
    mem[:, BS_FACED] = np.where(walk, 1, 0)
    mem[:, BS_FLEE_DIR] = np.where(has_run & ~defend, j_away, np.where(cont, j_cont, mem[:, BS_FLEE_DIR]))
    return a


def _carcass(o, p, other):
    """Carcass seeking for a meat-only body: food_here (meat within 1.0) and not stuck → EAT; else WALK toward the largest food_dir
    column (a sensed carcass); nothing sensed → `other`."""
    fh = (o[:, O_FOOD_HERE] >= p["here_min"]) & ~p.get("_stuck", np.zeros(o.shape[0], dtype=bool))
    fd = o[:, _FD]
    return np.where(fh, EAT, np.where(fd.max(1) > 0.0, WALK_FIRST + np.argmax(fd, axis=1), other))


def _rule_wolf(o, u, mem, ctx, p):
    """RULE_WOLF: E < 0.98 and a carcass here (food_here) → EAT, a sensed carcass (food_dir) → WALK toward it. Otherwise E < 0.9 →
    hunt: target = nearest other outside shelters, preferring size < 0.47 (body < 0.94); beyond 6 → WALK toward it (stalk), within →
    RUN; stamina locked → WALK. Satiated → WATCH.
    '은신처 밖' is not observable for others — DECISION [어림, open issue]: my nearest shelter centre is estimated as
    (shelter_x, shelter_y) × (shelter_edge + r_est / 20) with r_est = 5.5 (mean radius); targets within r_est of it are skipped.
    The stamina lock is not observed either: the brain keeps a copy (lock at ≤ stamina_lock, unlock at ≥ stamina_unlock, the body
    hysteresis of 3-3). Hungry without a target (no 7-5 rule) [어림]: patrol — WALK straight on, or toward the freest side when
    free_0 ≤ 0.2."""
    E = o[:, O_ENERGY]
    st = o[:, O_STAMINA]
    lock = mem[:, WS_LOCKED]
    lock = np.where(st <= p["stamina_lock"], 1, np.where(st >= p["stamina_unlock"], 0, lock))
    mem[:, WS_LOCKED] = lock
    pres = o[:, _OC["present"]] > 0.5
    rx, ry, sz = o[:, _OC["rel_x"]], o[:, _OC["rel_y"]], o[:, _OC["size"]]
    sx, sy, se = o[:, O_SHELTER_X], o[:, O_SHELTER_Y], o[:, O_SHELTER_EDGE]
    r_est = p["shelter_r_est"] / POS_N
    known = (sx * sx + sy * sy) > 0.25                        # a shelter direction is observed (0 only inside one)
    cx, cy = sx * (se + r_est), sy * (se + r_est)
    dx, dy = rx - cx[:, None], ry - cy[:, None]
    in_sh = known[:, None] & (dx * dx + dy * dy < r_est * r_est)
    cand = pres & ~in_sh
    has_small, js = _first(cand & (sz < p["small_size"]))
    has_any, ja = _first(cand)
    jt = np.where(has_small, js, ja)
    tx, ty, td = _take(o, _OC["rel_x"], jt), _take(o, _OC["rel_y"], jt), _take(o, _OC["dist"], jt)
    j = _dir_index(tx, ty)
    hunt = np.where((td > p["stalk_r"] / POS_N) | (lock == 1), WALK_FIRST + j, RUN_FIRST + j)
    free = o[:, _FREE]
    patrol = WALK_FIRST + np.where(free[:, 0] > PATROL_FREE_MIN, 0, np.argmax(free, axis=1))
    a = np.where(E < p["hunt_e"], np.where(has_any, hunt, patrol), WATCH)
    return np.where(E < p["eat_e"], _carcass(o, p, a), a)


def _nohunt(o, u, mem, ctx, p):
    """NOHUNT (C0-10 negative control, '사체 쪽 걷기'): E < 0.98 → carcass seeking only (food_here → EAT, sensed carcass → WALK
    toward it), else WATCH. Never goes to live prey (it may still bite by contact — the body rule)."""
    E = o[:, O_ENERGY]
    return np.where(E < p["eat_e"], _carcass(o, p, np.full(o.shape[0], WATCH)), WATCH)


def _nohunt_run(o, u, mem, ctx, p):
    """NOHUNT_RUN (C0-10 negative control, '사체 쪽 뛰기'): NOHUNT with every WALK_j replaced by RUN_j."""
    x = np.asarray(_nohunt(o, u, mem, ctx, p), dtype=np.int64)
    w = (x >= WALK_FIRST) & (x <= WALK_LAST)
    return np.where(w, x + (RUN_FIRST - WALK_FIRST), x)


def _rule_hide(o, u, mem, ctx, p):
    """HIDE_DEER · HIDE_BOAR (C0-11 only): any perceived other → go to a shelter (inside → SHELTER, outside → RUN toward
    shelter_x·y); none and E < 0.3 → food seeking; otherwise go to a shelter."""
    any_o = (o[:, _OC["present"]] > 0.5).any(1)
    go, _in, _kn = _to_shelter(o, run=True)
    return np.where(any_o, go, np.where(o[:, O_ENERGY] < p["eat_e"], seek_obs(o, p), go))


def _always_eat(o, u, mem, ctx, p):
    """ALWAYS_EAT: food seeking always (no flight, no shelter, whatever E) — the S′ meaning of the old 'always EAT'."""
    return seek_obs(o, p)


def _random(o, u, mem, ctx, p):
    """RANDOM: argmax(u) — uniform over the 19 actions from the already drawn uniforms."""
    return np.argmax(u, axis=1)


# --- 동물 세계 규칙 두뇌 (6-4, 문턱 모두 [어림]; 관측만 읽는다) -------------------------------------------------------------

def _flee_or_hide(o, rx, ry):
    """Threat answer shared by RULE_LEOPARD / RULE_FOX: inside a shelter → SHELTER; a shelter direction known → RUN toward it;
    else RUN away from (rx, ry) (closest open direction)."""
    go_sh, inside, known = _to_shelter(o, run=True)
    j_away = _dir_index(-rx, -ry, o[:, _FREE], PATROL_FREE_MIN)
    return np.where(inside, SHELTER, np.where(known, go_sh, RUN_FIRST + j_away))


def _rule_buffalo(o, u, mem, ctx, p):
    """RULE_BUFFALO:
      1 the nearest other within threat_r comes in (approach > approach): it is at the head (rel_x / |rel| ≥ face_cos) → RUN toward
        it (a charge); else WALK toward it (turn to face).
      2 E < full_e → food seeking (`seek_obs`).
      3 the nearest kin farther than kin_far → WALK toward it.
      4 WATCH."""
    pres = o[:, other_col(0, "present")] > 0.5
    rx, ry = o[:, other_col(0, "rel_x")], o[:, other_col(0, "rel_y")]
    dist, appr = o[:, other_col(0, "dist")], o[:, other_col(0, "approach")]
    thr = pres & (dist < p["threat_r"] / POS_N) & (appr > p["approach"])
    rn = np.sqrt(rx * rx + ry * ry)
    head_on = rx >= p["face_cos"] * rn
    j = _dir_index(rx, ry)
    face = np.where(head_on, RUN_FIRST + j, WALK_FIRST + j)
    kx, ky = o[:, kin_col(0, "rel_x")], o[:, kin_col(0, "rel_y")]
    kfar = (o[:, kin_col(0, "present")] > 0.5) & (kx * kx + ky * ky > (p["kin_far"] / POS_N) ** 2)
    a = np.where(kfar, WALK_FIRST + _dir_index(kx, ky), WATCH)
    a = np.where(o[:, O_ENERGY] < p["full_e"], seek_obs(o, p), a)
    return np.where(thr, face, a)


def _rule_leopard(o, u, mem, ctx, p):
    """RULE_LEOPARD (stamina-lock copy in memory like RULE_WOLF):
      1 threat = the nearest other within threat_r coming in (approach > threat_approach) with size ≥ threat_size_min → shelter
        (inside SHELTER, known RUN toward it) else RUN away.
      2 E < eat_e and a carcass here / sensed → `_carcass` (EAT / WALK toward it).
      3 E < hunt_e: target = the nearest other with size < prey_size_max and approach ≤ prey_approach_max (inside a shelter too —
        P1). Beyond stalk_r: WATCH while the target faces me (facing > watch_facing) else WALK toward it; within: RUN (locked → WALK).
      4 stamina locked → WALK toward a shelter (inside: SHELTER).
      5 WATCH."""
    E = o[:, O_ENERGY]
    st = o[:, O_STAMINA]
    lock = mem[:, WS_LOCKED]
    lock = np.where(st <= p["stamina_lock"], 1, np.where(st >= p["stamina_unlock"], 0, lock))
    mem[:, WS_LOCKED] = lock
    pres = o[:, _OC["present"]] > 0.5
    sz = o[:, _OC["size"]]
    dist, appr = o[:, _OC["dist"]], o[:, _OC["approach"]]
    has_thr, jt = _first(pres & (dist < p["threat_r"] / POS_N) & (appr > p["threat_approach"]) & (sz >= p["threat_size_min"]))
    flee = _flee_or_hide(o, _take(o, _OC["rel_x"], jt), _take(o, _OC["rel_y"], jt))
    has_prey, jp = _first(pres & (sz < p["prey_size_max"]) & (appr <= p["prey_approach_max"]))
    tx, ty = _take(o, _OC["rel_x"], jp), _take(o, _OC["rel_y"], jp)
    td, tf = _take(o, _OC["dist"], jp), _take(o, _OC["facing"], jp)
    j = _dir_index(tx, ty)
    far = td > p["stalk_r"] / POS_N
    hunt = np.where(far, np.where(tf > p["watch_facing"], WATCH, WALK_FIRST + j), np.where(lock == 1, WALK_FIRST + j, RUN_FIRST + j))
    go_sh, _in, _kn = _to_shelter(o, run=False)
    a = np.where(lock == 1, go_sh, WATCH)
    a = np.where((E < p["hunt_e"]) & has_prey, hunt, a)
    a = np.where(E < p["eat_e"], _carcass(o, p, a), a)
    return np.where(has_thr, flee, a)


def _rule_fox(o, u, mem, ctx, p):
    """RULE_FOX (thresholds relative to the own size column):
      1 the nearest other within flee_r coming in (approach > flee_approach) bigger than own × flee_size_ratio → shelter (inside
        SHELTER, known RUN toward it) else RUN away.
      2 E < eat_e: a smaller other (size < own × prey_size_ratio) within pounce_r → RUN toward it (stage 1 has no such body — the
        rat of stage 3); else food seeking (`seek_obs`: carcass meat and root).
      3 WATCH."""
    own = o[:, B.O_OWN_SIZE]
    pres = o[:, _OC["present"]] > 0.5
    sz, dist, appr = o[:, _OC["size"]], o[:, _OC["dist"]], o[:, _OC["approach"]]
    has_thr, jt = _first(pres & (dist < p["flee_r"] / POS_N) & (appr > p["flee_approach"])
                         & (sz > own[:, None] * p["flee_size_ratio"]))
    flee = _flee_or_hide(o, _take(o, _OC["rel_x"], jt), _take(o, _OC["rel_y"], jt))
    has_prey, jp = _first(pres & (sz < own[:, None] * p["prey_size_ratio"]) & (dist < p["pounce_r"] / POS_N))
    pounce = RUN_FIRST + _dir_index(_take(o, _OC["rel_x"], jp), _take(o, _OC["rel_y"], jp))
    eat = np.where(has_prey, pounce, seek_obs(o, p))
    a = np.where(o[:, O_ENERGY] < p["eat_e"], eat, WATCH)
    return np.where(has_thr, flee, a)


_RULES = {"RULE_DEER": _rule_deer, "RULE_BOAR": _rule_boar, "RULE_WOLF": _rule_wolf, "HIDE_DEER": _rule_hide,
          "HIDE_BOAR": _rule_hide, "ALWAYS_EAT": _always_eat, "RANDOM": _random, "NOHUNT": _nohunt, "NOHUNT_RUN": _nohunt_run,
          "RULE_BUFFALO": _rule_buffalo, "RULE_LEOPARD": _rule_leopard, "RULE_FOX": _rule_fox}


def here_min_of(cfg: dict, sp: int) -> float:
    """Smallest food_here meaning 'something eatable here' for species sp, from its body table (computed once, not in a step):
    max over its grid foods of e_f × eat_min / food_here_ref (deer 0.06, boar 0.045); a meat-only body: > 0 (1e-9)."""
    s = cfg["species"][B.ALL_SPECIES[int(sp)]]
    em = float(cfg["body_common"]["eat_min"])
    ref = float(s["food_here_ref"])
    vals = [float(s["e_per_unit"][f]) * em / ref for f in s["diet"] if f in ("grass", "root")]
    if not vals:
        return 1e-9
    return max(vals)


def make_rule(name: str, cfg: dict, sp: int | None = None, blind: bool = False) -> RuleBrain:
    """Rule brain by name (RULE_NAMES) with thresholds from cfg['rules'] (7-5). sp = the species whose block it decides (its body
    table gives the food_here threshold `here_min_of`); default = the rule's own species. ALWAYS_EAT serves deer and boar, so it needs
    sp. RULE_WOLF / NOHUNT* also copy the body stamina hysteresis (body_common.stamina_lock / stamina_unlock)."""
    if name not in ALL_RULE_NAMES:
        raise ValueError(f"unknown rule brain {name!r} (known: {ALL_RULE_NAMES})")
    own = RULE_SPECIES[name]
    if sp is None:
        if name == "ALWAYS_EAT":
            raise ValueError("ALWAYS_EAT needs the species it decides for (make_rule(name, cfg, sp)) — food_here threshold")
        sp = own
    params = dict(cfg["rules"][RULE_CFG[name]]) if name in RULE_CFG else {}
    if name in ("RULE_WOLF", "NOHUNT", "NOHUNT_RUN", "RULE_LEOPARD"):
        params["stamina_lock"] = float(cfg["body_common"]["stamina_lock"])
        params["stamina_unlock"] = float(cfg["body_common"]["stamina_unlock"])
    params = {k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for k, v in params.items()}
    params["here_min"] = here_min_of(cfg, sp) if sp is not None else 1e-9
    nb = RULE_N_BASE.get(name, 0)
    return RuleBrain(name=name, kind="rule", species=(own if own is not None else (None if sp is None else int(sp))),
                     n_state=nb + N_STUCK, params=params, n_base=nb, blind=bool(blind))


# --------------------------------------------------------------------------- #
# SB3 → npz (7-10)
# --------------------------------------------------------------------------- #

def extract_sb3(model) -> dict:
    """SB3 PPO MlpPolicy → W0..B2 float32 from mlp_extractor.policy_net[0], [2] and action_net (7-10). Checks the net shape
    (115 → 64 → 64 → 19, tanh) and that the features extractor is a plain flatten (no observation transform outside the 3 layers).
    R9's own function — export_weights_v3.extract is RepertoirePolicy-only."""
    import torch as th
    from stable_baselines3.common.torch_layers import FlattenExtractor

    pol = model.policy
    if tuple(model.observation_space.shape) != (OBS_DIM,) or int(model.action_space.n) != N_ACTIONS:
        raise BrainContractError(f"model spaces {model.observation_space.shape}/{model.action_space} are not ({OBS_DIM},)/Discrete(19)")
    if not isinstance(pol.pi_features_extractor, FlattenExtractor):
        raise BrainContractError(f"policy features extractor is {type(pol.pi_features_extractor).__name__}, not FlattenExtractor")
    net = pol.mlp_extractor.policy_net
    if not (len(net) == 4 and isinstance(net[0], th.nn.Linear) and isinstance(net[1], th.nn.Tanh)
            and isinstance(net[2], th.nn.Linear) and isinstance(net[3], th.nn.Tanh)):
        raise BrainContractError(f"policy_net is not Linear-Tanh-Linear-Tanh: {net}")
    out = {}
    for tag, lin in (("0", net[0]), ("1", net[2]), ("2", pol.action_net)):
        w = lin.weight.detach().cpu().numpy().astype(np.float32)
        b = lin.bias.detach().cpu().numpy().astype(np.float32)
        out[f"W{tag}"], out[f"B{tag}"] = w, b
    _check_weights(out)
    return out


def _check_weights(w: dict) -> None:
    for k in NPZ_WEIGHT_KEYS:
        if k not in w:
            raise BrainContractError(f"weights miss {k}")
        a = np.asarray(w[k])
        if a.shape != NPZ_SHAPES[k]:
            raise BrainContractError(f"{k} shape {a.shape} != {NPZ_SHAPES[k]} (net contract 115 → 64 → 64 → 19)")
        if a.dtype != np.float32:
            raise BrainContractError(f"{k} dtype {a.dtype} is not float32")
        if not np.all(np.isfinite(a)):
            raise BrainContractError(f"{k} has non-finite values")


def config_digest(cfg: dict) -> str:
    """sha1 (first 12 hex) of the config dict without its file path (export_weights_v3.config_digest form)."""
    d = {k: v for k, v in cfg.items() if k != "_path"}
    return hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _species_index(species) -> int:
    if isinstance(species, (int, np.integer)):
        if not 0 <= int(species) < len(B.ALL_SPECIES):
            raise ValueError(f"unknown species {species!r}")
        return int(species)
    if species not in B.SPECIES_INDEX:
        raise ValueError(f"unknown species {species!r}")
    return B.SPECIES_INDEX[species]


def brain_meta(cfg: dict, species, branch: str, round_: int, decisions: int, src_zip: Path | None) -> dict:
    """meta_json dict (META_KEYS) incl. r9_body.io_hash(), body_hash(cfg, species), body_table_hash(cfg)."""
    sp = _species_index(species)
    src = None if src_zip is None else hashlib.sha256(Path(src_zip).read_bytes()).hexdigest()
    return {"format": NPZ_FORMAT, "format_version": NPZ_FORMAT_VERSION, "species": B.ALL_SPECIES[sp], "branch": str(branch),
            "round": int(round_), "decisions": int(decisions), "obs_names": list(OBS_NAMES), "action_names": list(ACTION_NAMES),
            "io_hash": B.hash_hex(B.io_hash()), "body_hash": B.hash_hex(B.body_hash(cfg, sp)),
            "body_table_hash": B.hash_hex(B.body_table_hash(cfg)), "src_zip_sha256": src, "config_digest": config_digest(cfg)}


def save_brain(path: Path, weights: dict, meta: dict) -> None:
    """np.savez (no pickle) at exactly `path`: NPZ_WEIGHT_KEYS float32 + meta_json (0-d unicode)."""
    _check_weights(weights)
    miss = [k for k in META_KEYS if k not in meta]
    if miss:
        raise BrainContractError(f"meta misses {miss}")
    arrays = {k: np.ascontiguousarray(weights[k], dtype=np.float32) for k in NPZ_WEIGHT_KEYS}
    arrays["meta_json"] = np.array(json.dumps(meta, sort_keys=True, ensure_ascii=True))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as fh:
        np.savez(fh, **arrays)


def _read_npz(path: Path, sp: int) -> tuple[dict, dict]:
    """npz weights + meta with every check of `load_brain` except the body hash (format, shapes, names, io_hash, species)."""
    with np.load(Path(path), allow_pickle=False) as z:
        keys = set(z.files)
        miss = [k for k in NPZ_WEIGHT_KEYS + ("meta_json",) if k not in keys]
        if miss:
            raise BrainContractError(f"{path}: npz misses {miss}")
        weights = {k: np.array(z[k]) for k in NPZ_WEIGHT_KEYS}
        meta = json.loads(str(z["meta_json"][()]))
    _check_weights(weights)
    miss = [k for k in META_KEYS if k not in meta]
    if miss:
        raise BrainContractError(f"{path}: meta misses {miss}")
    if meta.get("format") != NPZ_FORMAT or int(meta.get("format_version", -1)) != NPZ_FORMAT_VERSION:
        raise BrainContractError(f"{path}: format {meta.get('format')!r} v{meta.get('format_version')} is not {NPZ_FORMAT} v{NPZ_FORMAT_VERSION}")
    if meta["species"] != B.ALL_SPECIES[sp]:
        raise BrainContractError(f"{path}: brain species {meta['species']!r} != requested {B.ALL_SPECIES[sp]!r}")
    if list(meta["obs_names"]) != list(OBS_NAMES) or list(meta["action_names"]) != list(ACTION_NAMES):
        raise BrainContractError(f"{path}: observation / action names differ from the R9 I/O contract")
    if meta["io_hash"] != B.hash_hex(B.io_hash()):
        raise BrainContractError(f"{path}: io_hash {meta['io_hash']} != {B.hash_hex(B.io_hash())}")
    return weights, meta


def rebody_brain(src: Path, cfg: dict, species, out: Path) -> dict:
    """동물 세계 6-1 `rebody`: carry a brain of the SAME species into a world with another body (e.g. the S′ demo brain into the animal
    world). The npz is read with every `load_brain` check except the body hash (format, shapes, names, io_hash, species); the new
    meta is `brain_meta(cfg, species, ...)` of the target world (its body hash, so `load_brain` accepts it there) plus `init_from`
    = the original meta's path, sha256, species, body_hash, body_table_hash and config_digest. The only door that moves a brain
    across bodies — and it writes that fact into the file. Returns the new meta."""
    sp = _species_index(species)
    src = Path(src)
    weights, old = _read_npz(src, sp)
    meta = brain_meta(cfg, sp, old["branch"], int(old["round"]), int(old["decisions"]), None)
    meta["init_from"] = {"path": str(src), "sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "species": old["species"],
                         "body_hash": old["body_hash"], "body_table_hash": old["body_table_hash"],
                         "config_digest": old["config_digest"]}
    save_brain(Path(out), weights, meta)
    return meta


def load_brain(path: Path, cfg: dict, species) -> MlpBrain:
    """Read npz (allow_pickle=False), check shapes, names, io_hash, species and body_hash(cfg, species); BrainContractError on
    mismatch (test 27). The world calls this with ITS config, so a brain trained on another body is refused."""
    sp = _species_index(species)
    with np.load(Path(path), allow_pickle=False) as z:
        keys = set(z.files)
        miss = [k for k in NPZ_WEIGHT_KEYS + ("meta_json",) if k not in keys]
        if miss:
            raise BrainContractError(f"{path}: npz misses {miss}")
        weights = {k: np.array(z[k]) for k in NPZ_WEIGHT_KEYS}
        meta = json.loads(str(z["meta_json"][()]))
    _check_weights(weights)
    miss = [k for k in META_KEYS if k not in meta]
    if miss:
        raise BrainContractError(f"{path}: meta misses {miss}")
    if meta.get("format") != NPZ_FORMAT or int(meta.get("format_version", -1)) != NPZ_FORMAT_VERSION:
        raise BrainContractError(f"{path}: format {meta.get('format')!r} v{meta.get('format_version')} is not {NPZ_FORMAT} v{NPZ_FORMAT_VERSION}")
    if meta["species"] != B.ALL_SPECIES[sp]:
        raise BrainContractError(f"{path}: brain species {meta['species']!r} != requested {B.ALL_SPECIES[sp]!r}")
    if list(meta["obs_names"]) != list(OBS_NAMES) or list(meta["action_names"]) != list(ACTION_NAMES):
        raise BrainContractError(f"{path}: observation / action names differ from the R9 I/O contract")
    if meta["io_hash"] != B.hash_hex(B.io_hash()):
        raise BrainContractError(f"{path}: io_hash {meta['io_hash']} != {B.hash_hex(B.io_hash())}")
    want = B.hash_hex(B.body_hash(cfg, sp))
    if meta["body_hash"] != want:
        raise BrainContractError(f"{path}: body_hash {meta['body_hash']} != world {B.ALL_SPECIES[sp]} body {want} (trained on another body)")
    name = f"{meta['species']}:{meta['branch']}:r{meta['round']}:{meta['decisions']}"
    return MlpBrain(name=name, kind="mlp", species=sp, n_state=0, weights=weights, meta=meta)


def export_sb3_zip(zip_path: Path, npz_path: Path, cfg: dict, species, branch: str, round_: int, decisions: int) -> dict:
    """PPO zip → npz brain (league / snapshot helper). Returns the meta written."""
    from stable_baselines3 import PPO

    model = PPO.load(str(zip_path), device="cpu")
    w = extract_sb3(model)
    meta = brain_meta(cfg, species, branch, round_, decisions, Path(zip_path))
    save_brain(Path(npz_path), w, meta)
    return meta
