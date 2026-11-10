"""R9 brains — fixed MLP brains (npz), rule brains (7-5) and the per-world same-shape block decision (7-10).

Owner: brains agent. Tests: tests/test_r9_brains.py (12절 16·27 + rule brains on hand observations). The world never needs these to
step — `R9World.step(actions)` takes actions from outside; `R9World.act()` (order 0) is the only caller.

Contract (impl_contract.md §7)
  - Every brain reads the same 107 observation columns (r9_body.OBS_NAMES, float32) and returns one of 19 actions. No species
    number, no hidden state of others. Rule thresholds compare observation values (normalised, 4절; distances in units / 20).
  - `decide_block(ctrl, obs_block, rng, state, ctx)` is called by the world ONCE PER WORLD PER SPECIES with the block
    obs[k, lo_sp:hi_sp] (n = that species' slot cap, dead slots included) so the MKL result does not depend on how many worlds are
    batched (7-10, test 21). It ALWAYS draws `rng.random((n, N_ACTIONS))` first, whatever the brain kind and mode, so swapping
    brains or modes never shifts another stream (3-9, test 27).
  - Stochastic: Gumbel-max a = argmax(z), z = float64(logit) + g, g = −log(−log u) (float64). Greedy: argmax(logits) on the float32
    logits. Ties → lowest index (np.argmax). Rule brains ignore `stochastic` (RANDOM uses u: argmax(u) = uniform over 19).
  - Near ties (7-10): `gap` = difference of the two largest values the decision maximised (greedy: logits, stochastic: z). The
    world counts gap < NEAR_TIE. Rule brains return inf.
  - npz: weights W0 (64, 107), B0 (64,), W1 (64, 64), B1, W2 (19, 64), B2 (19,) float32 + `meta_json` (0-d unicode array, no
    pickle): format, species, branch, round, decisions, obs_names, action_names, io_hash, body_hash, body_table_hash,
    src_zip_sha256, config_digest. `load_brain` rejects format / shape / name / io_hash / species / body_hash (of that species in
    the world config) mismatches with BrainContractError (test 27).
  - Rule-brain memory (RULE_BOAR flee count-down and face-off flag, RULE_WOLF stamina-lock copy) is int64 (n, n_state) per slot.
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
from .r9_body import (ACTION_NAMES, DIR8, EAT, N_ACTIONS, O_AGE_FRAC, O_ENERGY, O_FOOD_DENSITY, O_FREE0, O_HEALTH, O_SHELTER_EDGE,
                      O_SHELTER_X, O_SHELTER_Y, O_STAMINA, OBS_DIM, OBS_NAMES, RUN_FIRST, SHELTER, SPECIES, WALK_FIRST, WATCH,
                      kin_col, other_col)

HIDDEN = 64
NPZ_FORMAT = "eco_r9_brain"
NPZ_FORMAT_VERSION = 1
NPZ_WEIGHT_KEYS = ("W0", "B0", "W1", "B1", "W2", "B2")
NPZ_SHAPES = {"W0": (HIDDEN, OBS_DIM), "B0": (HIDDEN,), "W1": (HIDDEN, HIDDEN), "B1": (HIDDEN,), "W2": (N_ACTIONS, HIDDEN),
              "B2": (N_ACTIONS,)}
META_KEYS = ("species", "branch", "round", "decisions", "obs_names", "action_names", "io_hash", "body_hash", "body_table_hash",
             "src_zip_sha256", "config_digest")

RULE_NAMES = ("RULE_DEER", "RULE_BOAR", "RULE_WOLF", "HIDE_DEER", "HIDE_BOAR", "ALWAYS_EAT", "RANDOM")   # 7-5
RULE_SPECIES = {"RULE_DEER": B.DEER, "RULE_BOAR": B.BOAR, "RULE_WOLF": B.WOLF, "HIDE_DEER": B.DEER, "HIDE_BOAR": B.BOAR,
                "ALWAYS_EAT": None, "RANDOM": None}
RULE_CFG = {"RULE_DEER": "deer", "RULE_BOAR": "boar", "RULE_WOLF": "wolf", "HIDE_DEER": "hide", "HIDE_BOAR": "hide"}
RULE_N_STATE = {"RULE_BOAR": 3, "RULE_WOLF": 1}
NEAR_TIE = 1e-5                     # 7-10: decisions whose top-2 gap < 1e-5 are counted

# RULE_BOAR state columns · RULE_WOLF state column
BS_FLEE_LEFT, BS_FACED, BS_FLEE_DIR = 0, 1, 2
WS_LOCKED = 0
PATROL_FREE_MIN = 0.2               # [어림] RULE_WOLF hungry without a target walks straight; if free_0 ≤ this, toward the freest side

POS_N = float(B.OBS_NORM["pos"])     # 20: observation distance unit

# observation columns used by the rules
_OC = {f: np.array([other_col(j, f) for j in range(B.N_OTHER)]) for f in B.OBS_OTHER_FIELDS}
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
        """(n, 107) float32 → (n, 19) float32 logits; rule brains return None."""
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
        """(n, 107) float32 obs, (n, 19) float64 uniforms (already drawn), per-slot state (n, n_state) int64 (mutated in place),
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
    params: dict = field(default_factory=dict)    # cfg['rules'][...] thresholds (distances in units; brain divides by POS_N)

    def decide(self, obs, u, stochastic, state, ctx):
        o = np.asarray(obs, dtype=np.float64)
        n = o.shape[0]
        mem = self._mem(n, state)
        fn = _RULES[self.name]
        a = fn(o, np.asarray(u, dtype=np.float64), mem, ctx or {}, self.params)
        return np.asarray(a, dtype=np.int64), np.full(n, np.inf)


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
# rule brains (7-5) — observation columns only
# --------------------------------------------------------------------------- #

def _rule_deer(o, u, mem, ctx, p):
    """RULE_DEER: nearest other within 15 and (facing > f and approach > 0.1), or within 10 and approach > 0.15 → flee: SHELTER if
    the shelter edge is within 8, else the RUN direction closest to 'away' among free_j > 0.2. Otherwise E < 0.9 → EAT, else WATCH.
    f = ctx['facing_f'] (train world U[0.8, 0.97]) else facing_eval 0.9."""
    f = float(ctx.get("facing_f", p["facing_eval"]))
    pres = o[:, other_col(0, "present")] > 0.5
    dist, appr, fac = o[:, other_col(0, "dist")], o[:, other_col(0, "approach")], o[:, other_col(0, "facing")]
    trig = pres & (((dist < p["near"] / POS_N) & (fac > f) & (appr > p["approach_far"]))
                   | ((dist < p["close"] / POS_N) & (appr > p["approach_close"])))
    j = _dir_index(-o[:, other_col(0, "rel_x")], -o[:, other_col(0, "rel_y")], o[:, _FREE], p["free_min"])
    flee = np.where(o[:, O_SHELTER_EDGE] < p["shelter_edge"] / POS_N, SHELTER, RUN_FIRST + j)
    idle = np.where(o[:, O_ENERGY] < p["full_e"], EAT, WATCH)
    return np.where(trig, flee, idle)


def _rule_boar(o, u, mem, ctx, p):
    """RULE_BOAR (Fauna flee 650 cm·1.5 s, offspring guard — EcoFaunaMovement.cpp 128~157·383~405):
      1 another within 3.25 runs at me (approach > 0.33) facing me (facing > 0.9): adult with HP ≥ 0.55 and a young kin
        (size < 0.45) within 2 → WALK toward it (face-off); else RUN away for 6 decisions (count-down in memory).
      2 flee count-down left → RUN away from the nearest perceived other (none: straight on, RUN_0, or the freest side).
      3 another within 3.25 walks in (0.1 < approach ≤ 0.33 [어림 approach_walk]) → one decision WALK toward it, then WATCH.
      4 otherwise E < 0.9 → EAT, else WATCH."""
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
    a = np.where(o[:, O_ENERGY] < p["full_e"], EAT, WATCH)
    a = np.where(walk, np.where(faced == 0, WALK_FIRST + jw_t, WATCH), a)
    a = np.where(cont, RUN_FIRST + j_cont, a)
    a = np.where(has_run, np.where(defend, WALK_FIRST + j_toward, RUN_FIRST + j_away), a)
    n_flee = int(p["flee_decisions"])
    new_left = np.where(has_run, np.where(defend, 0, n_flee - 1), np.where(cont, left - 1, 0))
    new_faced = np.where(walk, 1, 0)
    new_dir = np.where(has_run & ~defend, j_away, np.where(cont, j_cont, mem[:, BS_FLEE_DIR]))
    mem[:, BS_FLEE_LEFT] = new_left
    mem[:, BS_FACED] = new_faced
    mem[:, BS_FLEE_DIR] = new_dir
    return a


def _rule_wolf(o, u, mem, ctx, p):
    """RULE_WOLF: a sensed carcass (food_density > 0 — a wolf's diet is meat only and only sensed carcasses count) and E < 0.98 →
    EAT. E < 0.9 → hunt: target = nearest other outside shelters, preferring size < 0.47 (body < 0.94); beyond 6 → WALK toward it
    (stalk), within → RUN; stamina locked → WALK. Satiated → WATCH.
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
    return np.where((o[:, O_FOOD_DENSITY] > 0) & (E < p["eat_e"]), EAT, a)


def _rule_hide(o, u, mem, ctx, p):
    """HIDE_DEER · HIDE_BOAR (C0-11 only): any perceived other → SHELTER; none and E < 0.3 → EAT; otherwise SHELTER."""
    any_o = (o[:, _OC["present"]] > 0.5).any(1)
    return np.where(any_o, SHELTER, np.where(o[:, O_ENERGY] < p["eat_e"], EAT, SHELTER))


def _always_eat(o, u, mem, ctx, p):
    return np.full(o.shape[0], EAT, np.int64)


def _random(o, u, mem, ctx, p):
    """RANDOM: argmax(u) — uniform over the 19 actions from the already drawn uniforms."""
    return np.argmax(u, axis=1)


_RULES = {"RULE_DEER": _rule_deer, "RULE_BOAR": _rule_boar, "RULE_WOLF": _rule_wolf, "HIDE_DEER": _rule_hide,
          "HIDE_BOAR": _rule_hide, "ALWAYS_EAT": _always_eat, "RANDOM": _random}


def make_rule(name: str, cfg: dict) -> RuleBrain:
    """Rule brain by name (RULE_NAMES) with thresholds from cfg['rules'] (7-5). RULE_WOLF also copies the body stamina hysteresis
    (body_common.stamina_lock / stamina_unlock) — the lock it mirrors."""
    if name not in RULE_NAMES:
        raise ValueError(f"unknown rule brain {name!r} (known: {RULE_NAMES})")
    params = dict(cfg["rules"][RULE_CFG[name]]) if name in RULE_CFG else {}
    if name == "RULE_WOLF":
        params["stamina_lock"] = float(cfg["body_common"]["stamina_lock"])
        params["stamina_unlock"] = float(cfg["body_common"]["stamina_unlock"])
    params = {k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for k, v in params.items()}
    return RuleBrain(name=name, kind="rule", species=RULE_SPECIES[name], n_state=RULE_N_STATE.get(name, 0), params=params)


# --------------------------------------------------------------------------- #
# SB3 → npz (7-10)
# --------------------------------------------------------------------------- #

def extract_sb3(model) -> dict:
    """SB3 PPO MlpPolicy → W0..B2 float32 from mlp_extractor.policy_net[0], [2] and action_net (7-10). Checks the net shape
    (107 → 64 → 64 → 19, tanh) and that the features extractor is a plain flatten (no observation transform outside the 3 layers).
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
            raise BrainContractError(f"{k} shape {a.shape} != {NPZ_SHAPES[k]} (net contract 107 → 64 → 64 → 19)")
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
        if not 0 <= int(species) < B.N_SPECIES:
            raise ValueError(f"unknown species {species!r}")
        return int(species)
    if species not in B.SPECIES_INDEX:
        raise ValueError(f"unknown species {species!r}")
    return B.SPECIES_INDEX[species]


def brain_meta(cfg: dict, species, branch: str, round_: int, decisions: int, src_zip: Path | None) -> dict:
    """meta_json dict (META_KEYS) incl. r9_body.io_hash(), body_hash(cfg, species), body_table_hash(cfg)."""
    sp = _species_index(species)
    src = None if src_zip is None else hashlib.sha256(Path(src_zip).read_bytes()).hexdigest()
    return {"format": NPZ_FORMAT, "format_version": NPZ_FORMAT_VERSION, "species": SPECIES[sp], "branch": str(branch),
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
    if meta["species"] != SPECIES[sp]:
        raise BrainContractError(f"{path}: brain species {meta['species']!r} != requested {SPECIES[sp]!r}")
    if list(meta["obs_names"]) != list(OBS_NAMES) or list(meta["action_names"]) != list(ACTION_NAMES):
        raise BrainContractError(f"{path}: observation / action names differ from the R9 I/O contract")
    if meta["io_hash"] != B.hash_hex(B.io_hash()):
        raise BrainContractError(f"{path}: io_hash {meta['io_hash']} != {B.hash_hex(B.io_hash())}")
    want = B.hash_hex(B.body_hash(cfg, sp))
    if meta["body_hash"] != want:
        raise BrainContractError(f"{path}: body_hash {meta['body_hash']} != world {SPECIES[sp]} body {want} (trained on another body)")
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
