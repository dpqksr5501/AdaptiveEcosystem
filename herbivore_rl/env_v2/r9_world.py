"""R9 world — deer, wolves and wild boar, each species one learned brain (design AdaptiveEcosystem/Docs/RL_Policy/
RL_R9_MULTISPECIES_DESIGN.md 3~6절, 3-9 step order, 12절 tests).

Owner: world agent. Tests: tests/test_r9.py (12절 1~12·19·20·22·23). Contract document: impl_contract.md (scratchpad r9/).

New independent world (3절): `r8_world.py`/`world.py` are not changed. R8's grass patch generator is COPIED (it sits inside
`R8World._init_world`, r8_world.py 303~313); `_box_mean` is imported from r8_world. One object runs K worlds as one array batch;
every world has its own RNG branches, so a world's trajectory does not depend on the other worlds in the batch (test 1).

Individuals: one table (K, S). Slots are species blocks [sp_lo[sp], sp_hi[sp]) in the order deer → wolf → boar (3-6), so the
learner's obs/actions are one slice. Slot caps per species = cfg.world.slots. Train world: slots i < counts[k, sp] of a block are
always alive at observation time (instant respawn), slots ≥ counts never live. Judge world: no respawn, births go to the lowest
empty slot of the species block (r9_life decides, the world installs); perception gathers alive slots only (K, M_alive, M_alive)
in slot order (3-9, test 22).

Hidden vs observable: `sp` (species number), `slot_sp`, `body` (species-indexed table) and `carc_sp` exist only for physics,
life and stats. Perception (`_perceive`) and the observation function (`build_obs`) read per-slot body arrays (`sb`, from
r9_body.expand_body), `kin_id` (species number mapped through a per-world permutation; only equality is used), positions, motion,
heads, grids, shelters, carcasses (with the dead's kin_id) and memory — never a species number (4-4, 4-6, test 2·3).

State table (dtype, shape, meaning). K worlds, S slots, G grid cells per side, C shelter cap, M carcass cap, Mx gathered-alive cap.
  batch constants
    mode str ('train'|'judge'), K, S, Q (quadrants 1|4), G, C, M, size f64, D (= 2 steps / decision)
    sp_lo, sp_hi           int64 (3,)      slot block bounds per species
    slot_sp                int8  (S,)      species of each slot (constant)
    body                   r9_body.Body    body table; rules: r9_life.LifeRules; life: r9_life.LifeState
    sb                     dict            expand_body(body, sp): per-slot body arrays (K, S) [food arrays (K, S, 3)]
    cell_quad              int8  (G, G)    quadrant of each grid cell
  per world (K,)
    seeds int64 · t int64 (world-local step) · next_uid int64 (IDs start at 1, only increase, 3-6)
    s_w uint64 · s_q uint64 (K, 4)          life hash seeds (r9_life.life_seeds)
    counts int64 (K, 3)                     species counts at (re)init (train: constant alive count)
    kin_perm int8 (K, 3)                    kin_id = kin_perm[k, sp]
    run_mult f64 (K, 3)                     per-world run multiplier (wolf U[0.90, 1.05], others 1)
    grass_mult · root_mult f64 (K,)         regen multipliers · juv_frac f64 (K, 3) · rule_f f64 (K,) RULE_DEER facing f
    n_cov int64 (K,)
  per slot (K, S)
    sp int8 [hidden] · kin_id int8 · alive bool · uid int64 (0 = empty)
    pos · head · vel · disp · dir_cmd · knock_dir  f64 (K, S, 2)
        vel = self-propelled velocity after wall slide (acceleration memory); disp = total last-step displacement incl. contact
        (obs own_speed, vel_x/y, approach, hearing); head = unit, follows vel when moving; dir_cmd = WALK/RUN direction fixed at
        the decision (head rotated by DIR8[j])
    E · R (fat fraction) · stam · hp · born (step) · next_birth (step) · g_speed · g_size · resp_t (last (re)birth step)  f64
    stam_lock bool · sex int8 (r9_body SEX_*) · quad int8 · mating bool · generation int32
    parent_a · parent_b · offspring · killer  int64 (uids; 0 = unknown)
    act · prev_act int64 (decision actions) · bite_cd · knock_left int32 · dead_cause int8 (CAUSE_*, this step)
    derived every step: af (age frac) · gr (growth) · size_obs (= size0 × g_size × gr) · spd_scale · maint · mature
  pairs
    mem f64 (K, S, S)       approach memory, row = observer i, column = other j (both species and kin)
  grids (K, G, G) f64
    grass · grass_cap · grass_regen · root · root_cap · root_regen ;  cover_cell bool (K, G, G)
  shelters
    cov_c f64 (K, C, 2) · cov_r f64 (K, C) · cov_ok bool (K, C)   (padding: centre −1e6, r 0, ok False)
  carcasses (K, M)
    carc_ok bool · carc_pos f64 (K, M, 2) · carc_meat · carc_meat0 · carc_t f64 · carc_kin int8 (kin_id of the dead — obs uses this)
    carc_sp int8 [hidden, stats] · carc_uid · carc_killer int64
  controllers (order 0)
    ctrl[k][sp] r9_brains.Controller | None · bstate[k][sp] int64 (slots of sp, n_state) · rng_act[k][sp] Generator
  per-world RNG Generators: rng_bite[k] · rng_resp[k]   (TAG table below)
  last decision: _obs f32 (K, S, 107) · _rew f64 (K, S) · _done bool (K, S) · _info dict ; stats: st dict ; record: events dict

Step order (3-9; one `step(actions)` = one decision = D = 2 steps; decisions happen at global t mod 2 == 0)
  0 decide      decide(): every species decides from the last observation; fixed brains run once per world on the same-shape
                block obs[k, lo:hi] (7-10) via r9_brains.decide_block; dir_cmd fixed for the decision
  1 move        action → target velocity (body table × spd_scale × wound (0.5 + 0.5 HP) × weak 0.75 × stamina lock → walk)
                → acceleration clip |Δvel| ≤ accel → self move + wall slide (clip to [0, size]) → contact displacement (counter
                knock 0.25 per step × 4) → wolf shelter push-out (radius + 0.5). All from previous positions (simultaneous)
  2 bite        wolves in a per-step random order (rng_bite permutation of the biter slots, drawn every step); a wolf with
                bite_cd == 0 bites the nearest other-species prey with: outside shelter, dist ≤ bite_r × g_size × gr, in the head
                cone (dot ≥ 0.5), own self-velocity toward it > 0.03. Deer die; boar counter (HP ≥ 0.35, wolf in its ±75.5°
                front) or HP loss; one death per individual, one bite per wolf; cooldown 8 / 30 (counter). The dead are marked
                at once (alive False, dead_cause) and skip orders 3~5
  3 eat         grids: R8 demand split (bincount of want, taken = min(demand, food), frac); meat: nearest eatable carcass within
                1.0, 3 places nearest first (ties lower slot), not own kin; boar takes the first available of root → meat → grass
  4 metabolism  e_new = min(E − drain × gait_drain × maint + gain, 1) then R8 `_reserve` (deficit from fat, refill 0.25 of gain
                when E ≥ 0.7); stamina drain (effective RUN) / recover; HP regen
  5 breed       r9_life.breed_step(self, life, rules) → BreedEvents (costs written by life; births credited to both parents);
                judge newborns installed into their slots
  6 deaths      starvation (E ≤ 0 and R ≤ 0) → carcasses for every death of this step (bites included)
  reward        r = 0.01 + 1.0 × Δ(E + R × C) + 10 × births − 10 × death (F switch: births × 2 + 8/2250 per mature E ≥ 0.7 step),
                for individuals alive at the step start; Δ uses the values at death for the dead (before respawn)
  7 regrow      grass/root food += regen × (cap − food); carcass meat −= meat0 / 1350
  8 respawn     train only: new uid; 20% newborn form, 80% far from all other-species individuals; references cleared
                (mem row/column, r9_life.on_slot_reset, brain state row)
  9 perceive    eye ∪ ear ∪ nose over gathered alive slots; approach memory update; t += 1
  Within a decision, steps after a death are not added (R8 `step` 634~638).

Numerics (3-9): geometry float64, obs float32; sums between individuals are sequential species → slot sums (`seq_sum` = np.cumsum
last element, or explicit loops / np.bincount in slot order) — no matmul, np.sum or mean over individuals; no trig inside a step
(r9_body.DIR8 / GOLDEN8 tables); stable selections (distance, ties lower slot); RNG per use (TAG table) and a fixed number of draws
per step regardless of alive/dead and brain kind; life values are hashes (r9_life).

Public API (VecEnv / eval)
  R9World(cfg, seeds, counts=None, record=False, pairs_full=False)
  decide(learner_sp, learner_actions) → (K, S) actions   [contract name `act()`: renamed — `act` is also the (K, S) action array
                                                           that r9_life reads, and an instance array would shadow the method]
  step(actions) → (obs, rew, done, info) · reset(seeds, counts) · reinit(k, seed, counts_k) · refresh() · set_controller(k, sp, ctrl)
  obs() / rewards() / info() / obs_maps() / alive_index() / learner_index(sp) / world_params(k) / stats_snapshot() / flush_hunts()
  step_hook(world, dead (K, S), extra dict) is called at the end of every step (eval tools; must not change the world).
  record=True keeps events: deaths (cause, killer uid, place, age, since spawn, wall band, shelter edge, E/R/HP, meat), bites
  (wolf/prey uid, prey species, outcome kill|wound|counter, distance, wolf E/HP, prey age, near carcass), respawns (form),
  births (judge newborns) and hunts = 8-2 approach segments (wolf uid, target uid/species, t0, t1, closing decisions, ran, end
  gap|kill|target_gone|wolf_gone|reset|open). Closing is measured between consecutive decisions (first at the 2nd decision).

Interpretations where the design is silent are marked [해석] / [어림] here and listed in the world agent's report (open_issues).
"""

from __future__ import annotations

import math
from typing import Any, NamedTuple, Sequence

import numpy as np

from . import r9_body as B
from . import r9_brains as BR
from . import r9_life as L
from .r8_world import _box_mean  # R8 helper reused as the design says (11절)

EPS = 1e-9

# RNG branch tags: default_rng([seed, TAG]). TAG_GRASS reuses R8 TAG_FOOD (8102) on purpose — test 20 compares the copied grass
# generator bit-for-bit with R8World of the same seed. Judge quadrant q grass: default_rng([seed, TAG_GRASS, q]); root likewise.
TAG_PARAM = 9101      # world values: counts (all species, fixed order), run mults, regen mults, juvenile fracs, rule f
TAG_GRASS = 8102
TAG_ROOT = 9103
TAG_SHELTER = 9104    # shelter count, radii, centres
TAG_PLACE = 9105      # start positions, heads (DIR8 index), start fat
TAG_KIN = 9106        # kin_id permutation
TAG_ACT = 9110        # + species number: per-species action sampling (opponent Gumbel u, (n_sp_slots, 19) every decision)
TAG_BITE = 9120       # per-step biter order permutation
TAG_RESP = 9121       # respawn: form, adult choice, 64 candidates, head index, fat (fixed count per respawn event)
TAG_EVAL = 9122       # evaluation-only randomness (reserved)
TAGS = dict(PARAM=TAG_PARAM, GRASS=TAG_GRASS, ROOT=TAG_ROOT, SHELTER=TAG_SHELTER, PLACE=TAG_PLACE, KIN=TAG_KIN, ACT=TAG_ACT,
            BITE=TAG_BITE, RESP=TAG_RESP, EVAL=TAG_EVAL)

# death causes
CAUSE_NONE, CAUSE_BITE, CAUSE_COUNTER, CAUSE_STARVE = 0, 1, 2, 3
CAUSE_NAMES = ("none", "bite", "counter", "starve")

# bite outcomes (stats / bite records)
BITE_KILL, BITE_WOUND, BITE_COUNTER = 0, 1, 2
BITE_NAMES = ("kill", "wound", "counter")

# respawn forms (train world)
RESP_NONE, RESP_FAR, RESP_NEWBORN = 0, 1, 2

# 3-6 '갓난 꼴: 같은 종 성체 1.1~2.5 단위 옆' = 1.1 + 0.2 j, j = 0..7 on the golden-angle table (design numbers, not in the YAML)
RESP_RING_R0 = 1.1
RESP_RING_DR = 0.2

# 8-2 '다가감 구간': closing faster than 0.1 units/step for more than 4 decisions; ends after 2 non-closing decisions or a kill
HUNT_CLOSE_SPEED = 0.1
HUNT_MIN_DECISIONS = 4
HUNT_GAP_END = 2
HUNT_END_NAMES = ("gap", "kill", "target_gone", "wolf_gone", "reset", "open")

INFO_KEYS = ("dead_cause", "dead_uid", "killer", "respawned", "newborn", "births", "alive", "uid", "t", "near_ties")


def row_seq_sums(mask: np.ndarray, values: tuple) -> tuple[np.ndarray, list[np.ndarray]]:
    """Per-row sequential sums over the last axis of a (..., n) bool mask: (count (...,) int64, [Σ_j mask·v_j for v in values]).
    Each value array has shape (..., n) or broadcasts to it along the leading axes as (A, 1, n). np.bincount adds the selected
    entries in row-major order (column ascending inside a row) starting from 0.0 — the C++ loop `acc += v[j]` (3-9 차례 합).
    Equal to seq_sum(where(mask, v, 0)) + 0.0."""
    shp = mask.shape[:-1]
    rows = int(np.prod(shp)) if shp else 1
    flat = mask.reshape(rows, mask.shape[-1])
    r, c = np.nonzero(flat)
    cnt = np.bincount(r, minlength=rows).reshape(shp)
    out = []
    for v in values:
        vv = np.broadcast_to(v, mask.shape).reshape(rows, mask.shape[-1])
        out.append(np.bincount(r, weights=vv[r, c], minlength=rows).reshape(shp))
    return cnt, out


def seq_sum(a: np.ndarray, axis: int = -1) -> np.ndarray:
    """Sequential (left-to-right) sum along `axis` via np.cumsum — the 3-9 '차례 합' (C++ loop order), never pairwise."""
    a = np.asarray(a)
    if a.shape[axis] == 0:
        ax = axis if axis >= 0 else a.ndim + axis
        return np.zeros(a.shape[:ax] + a.shape[ax + 1:], dtype=a.dtype)
    return np.take(np.cumsum(a, axis=axis), -1, axis=axis)


def _len2(v: np.ndarray) -> np.ndarray:
    return v[..., 0] * v[..., 0] + v[..., 1] * v[..., 1]


def _unit(v: np.ndarray) -> np.ndarray:
    """v / |v| (0 where |v| ≤ EPS) — same operations as r8_world._norm."""
    n = np.sqrt(_len2(v))[..., None]
    return np.divide(v, n, out=np.zeros_like(v), where=n > EPS)


class ObsInputs(NamedTuple):
    """Everything `build_obs` may read (4절). Deliberately no species number, no species-indexed table (test 2). `pc` is the
    perception of `R9World._perceive` (gathered alive slots, built from per-slot body arrays and kin_id only)."""
    t: np.ndarray            # (K,)
    pc: dict                 # gathered perception (see R9World._perceive)
    pos: np.ndarray          # (K, S, 2)
    head: np.ndarray
    disp: np.ndarray
    alive: np.ndarray        # (K, S)
    kin_id: np.ndarray
    sb: dict                 # per-slot body arrays
    E: np.ndarray
    R: np.ndarray
    stam: np.ndarray
    hp: np.ndarray
    size_obs: np.ndarray
    af: np.ndarray
    next_birth: np.ndarray
    mating: np.ndarray
    sex: np.ndarray
    mature: np.ndarray
    uid: np.ndarray
    parent_a: np.ndarray
    parent_b: np.ndarray
    check_related: bool      # judge world: mate_ok excludes kin (train world has no kinship)
    size: float
    cell: float
    grass: np.ndarray        # (K, G, G)
    root: np.ndarray
    cov_c: np.ndarray
    cov_r: np.ndarray
    cov_ok: np.ndarray
    mem: np.ndarray          # (K, S, S)


def _cells(P: np.ndarray, cell: float, G: int):
    """Grid cell of positions (r8_world._cell)."""
    kc = 1.0 / float(cell)
    ix = np.clip((P[..., 0] * kc).astype(np.int64), 0, G - 1)
    iy = np.clip((P[..., 1] * kc).astype(np.int64), 0, G - 1)
    return ix, iy


def _shelter_edge(P: np.ndarray, cov_c: np.ndarray, cov_r: np.ndarray, cov_ok: np.ndarray):
    """P (K, X, 2) → (nearest shelter index, edge distance) by edge distance; inf when the world has no shelter."""
    dx = P[:, :, None, 0] - cov_c[:, None, :, 0]
    dy = P[:, :, None, 1] - cov_c[:, None, :, 1]
    d = np.sqrt(dx * dx + dy * dy) - cov_r[:, None, :]
    d = np.where(cov_ok[:, None, :], d, np.inf)
    j = d.argmin(-1)
    return j, np.take_along_axis(d, j[..., None], -1)[..., 0]


def _topk_min(key: np.ndarray, n: int, own: bool = False) -> np.ndarray:
    """First n column indices of each row ordered by key ascending, ties lower column (= stable argsort[..., :n]); −1 when the
    row has fewer finite keys. Repeated argmin (argmin returns the first minimum). own=True: key may be overwritten."""
    if not own:
        key = key.copy()
    out = np.full(key.shape[:-1] + (n,), -1, dtype=np.int64)
    for r in range(n):
        j = key.argmin(-1)
        v = np.take_along_axis(key, j[..., None], -1)[..., 0]
        got = v < np.inf
        out[..., r] = np.where(got, j, -1)
        np.put_along_axis(key, j[..., None], np.inf, -1)
    return out


def build_obs(inp: ObsInputs) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Observation (K, S, 107) float32 (4절, column layout r9_body.OBS_NAMES) + hidden slot maps (K, S, 6) other and (K, S, 2) kin
    (slot numbers, −1 empty). Dead slots get zeros. All columns are computed on the gathered alive rows of `inp.pc` and scattered
    back to their slots (gathered order = slot order)."""
    nm = B.OBS_NORM
    K, S = inp.alive.shape
    pc = inp.pc
    ic, valid = pc["ic"], pc["valid"]
    Mx = ic.shape[1]
    kk = np.arange(K)[:, None]
    kk3 = kk[:, :, None]
    sb = inp.sb

    def g(a):
        return a[kk, ic]

    og = np.zeros((K, Mx, B.OBS_DIM))
    P, Hd, Dp = pc["P"], pc["H"], pc["Dp"]
    hx, hy = Hd[..., 0], Hd[..., 1]
    # --- self 0~22 (4-2) ---
    og[..., B.O_ENERGY] = g(inp.E)
    og[..., B.O_RESERVE] = g(inp.R)
    og[..., B.O_STAMINA] = g(inp.stam)
    og[..., B.O_HEALTH] = g(inp.hp)
    og[..., B.O_OWN_SIZE] = g(inp.size_obs) / nm["size"]
    og[..., B.O_AGE_FRAC] = g(inp.af)
    tt = np.asarray(inp.t, dtype=np.float64)[:, None]
    og[..., B.O_BIRTH_WAIT] = np.maximum(0.0, g(inp.next_birth) - tt) / nm["birth_wait"]
    G = inp.grass.shape[-1]
    ix, iy = _cells(P, inp.cell, G)
    eats = sb["eats"][kk, ic]
    epu = sb["e_per_unit"][kk, ic]
    wg = np.where(eats[..., B.GRASS], epu[..., B.GRASS], 0.0)
    wr = np.where(eats[..., B.ROOT], epu[..., B.ROOT], 0.0)
    wm = np.where(eats[..., B.MEAT], epu[..., B.MEAT], 0.0)
    br = max(1, int(round(nm["food_r"] / float(inp.cell))))      # 20 units = 10 cells (R8 density_blur)
    fbg = _box_mean(inp.grass, br)
    fbr = _box_mean(inp.root, br)
    dens_grid = wg * fbg[kk, iy, ix] + wr * fbr[kk, iy, ix]
    here_grid = wg * inp.grass[kk, iy, ix] + wr * inp.root[kk, iy, ix]
    cmeat = pc["cmeat"][:, None, :]
    dens_meat = seq_sum(np.where(pc["csens"] & (pc["cdist"] <= nm["food_r"]), cmeat, 0.0), -1) + 0.0
    here_meat = seq_sum(np.where(pc["cother"] & (pc["cdist"] <= nm["here_r"]), cmeat, 0.0), -1) + 0.0
    og[..., B.O_FOOD_DENSITY] = (dens_grid + wm * dens_meat / float(nm["food_box_cells"])) / g(sb["food_density_ref"])
    og[..., B.O_FOOD_HERE] = (here_grid + wm * here_meat) / g(sb["food_here_ref"])
    jsh, edge = _shelter_edge(P, inp.cov_c, inp.cov_r, inp.cov_ok)
    inside = edge <= 0.0
    has_sh = np.isfinite(edge)
    og[..., B.O_IN_SHELTER] = inside
    cc = np.take_along_axis(inp.cov_c, np.where(has_sh, jsh, 0)[..., None], 1)        # (K, Mx, 2)
    u = _unit(cc - P)
    off = inside | ~has_sh
    og[..., B.O_SHELTER_X] = np.where(off, 0.0, u[..., 0] * hx + u[..., 1] * hy)
    og[..., B.O_SHELTER_Y] = np.where(off, 0.0, -u[..., 0] * hy + u[..., 1] * hx)
    og[..., B.O_SHELTER_EDGE] = np.minimum(np.maximum(edge, 0.0), 1e9) / nm["edge"]
    dirs = B.rotate(np.broadcast_to(Hd[:, :, None, :], (K, Mx, 8, 2)), np.broadcast_to(B.DIR8, (K, Mx, 8, 2)))
    px, py = P[..., 0:1], P[..., 1:2]
    ux, uy = dirs[..., 0], dirs[..., 1]
    size = float(inp.size)
    with np.errstate(divide="ignore", invalid="ignore"):
        tx = np.where(ux > EPS, (size - px) / ux, np.where(ux < -EPS, px / -ux, np.inf))
        ty = np.where(uy > EPS, (size - py) / uy, np.where(uy < -EPS, py / -uy, np.inf))
    og[..., B.O_FREE0:B.O_FREE0 + 8] = np.minimum(tx, ty) / nm["free"]
    spd = np.sqrt(_len2(Dp))
    og[..., B.O_OWN_SPEED] = spd / nm["speed"]
    og[..., B.O_MATING] = g(inp.mating)
    # --- other-species slots (4-3) and kin (4-4) ---
    perc, same = pc["perc"], pc["same"]
    dx, dy, dist, invd = pc["dx"], pc["dy"], pc["dist"], pc["invd"]
    pk = perc & same
    sel_k = _topk_min(np.where(pk, dist, np.inf), B.N_KIN, own=True)
    sel_o = _topk_min(np.where(perc ^ pk, dist, np.inf), B.N_OTHER, own=True)     # (K, Mx, 6) gathered columns
    pn, vn = nm["pos"], nm["vel"]
    hx3, hy3 = hx[..., None], hy[..., None]
    sizes_g = g(inp.size_obs)
    # other block
    got = sel_o >= 0
    so = np.where(got, sel_o, 0)
    tk = lambda arr: np.take_along_axis(arr, so, -1)                  # noqa: E731  (K, Mx, Mx) → (K, Mx, 6)
    dxs, dys, dss, ivs = tk(dx), tk(dy), tk(dist), tk(invd)
    Dxj, Dyj = Dp[kk3, so, 0], Dp[kk3, so, 1]
    Hxj, Hyj = Hd[kk3, so, 0], Hd[kk3, so, 1]
    blk = np.zeros((K, Mx, B.N_OTHER, B.N_OF))
    blk[..., 0] = 1.0
    blk[..., 1] = (dxs * hx3 + dys * hy3) / pn
    blk[..., 2] = (-dxs * hy3 + dys * hx3) / pn
    blk[..., 3] = dss / pn
    blk[..., 4] = (Dxj * hx3 + Dyj * hy3) / vn
    blk[..., 5] = (-Dxj * hy3 + Dyj * hx3) / vn
    blk[..., 6] = tk(pc["appr"])
    blk[..., 7] = inp.mem[kk3, ic[:, :, None], ic[kk3, so]]
    blk[..., 8] = -(Hxj * dxs + Hyj * dys) * ivs
    blk[..., 9] = sizes_g[kk3, so] / nm["size"]
    blk[..., 10] = (tk(perc) & ~tk(pc["vis"])).astype(np.float64)
    blk = np.where(got[..., None], blk, 0.0)
    og[..., B.SL_OTHER] = blk.reshape(K, Mx, B.N_OTHER * B.N_OF)
    # kin summary: sequential sums over gathered columns (slot order); counts are exact integers
    run = (spd > nm["kin_run_speed"]).astype(np.float64)
    cnt, (nrun, fx, fy) = row_seq_sums(pk, (run[:, None, :], Dp[:, None, :, 0], Dp[:, None, :, 1]))
    cf = np.maximum(cnt, 1).astype(np.float64)
    has = cnt > 0
    og[..., B.KINSUM0] = cnt / nm["kin_count"]
    og[..., B.KINSUM0 + 1] = np.where(has, nrun / cf, 0.0)
    mfx = np.where(has, fx / cf, 0.0)
    mfy = np.where(has, fy / cf, 0.0)
    og[..., B.KINSUM0 + 2] = (mfx * hx + mfy * hy) / nm["flow"]
    og[..., B.KINSUM0 + 3] = (-mfx * hy + mfy * hx) / nm["flow"]
    # near-kin slots: [문서 빈칸 → 다른 종 칸과 같은 정규화] position / 20, velocity / 0.9, size / 2
    gk = sel_k >= 0
    sk = np.where(gk, sel_k, 0)
    tk2 = lambda arr: np.take_along_axis(arr, sk, -1)                 # noqa: E731
    dxk, dyk = tk2(dx), tk2(dy)
    Dxk, Dyk = Dp[kk3, sk, 0], Dp[kk3, sk, 1]
    kb = np.zeros((K, Mx, B.N_KIN, B.N_KF))
    kb[..., 0] = 1.0
    kb[..., 1] = (dxk * hx3 + dyk * hy3) / pn
    kb[..., 2] = (-dxk * hy3 + dyk * hx3) / pn
    kb[..., 3] = (Dxk * hx3 + Dyk * hy3) / vn
    kb[..., 4] = (-Dxk * hy3 + Dyk * hx3) / vn
    kb[..., 5] = sizes_g[kk3, sk] / nm["size"]
    sex_g, mat_g = g(inp.sex), g(inp.mature)
    ok = mat_g[kk3, sk] & L.mate_compatible(sex_g[..., None], sex_g[kk3, sk])
    if inp.check_related:
        pa, pb, ud = g(inp.parent_a), g(inp.parent_b), g(inp.uid)
        ok = ok & ~L.related(pa[..., None], pb[..., None], ud[..., None], pa[kk3, sk], pb[kk3, sk], ud[kk3, sk])
    kb[..., 6] = ok.astype(np.float64)
    kb = np.where(gk[..., None], kb, 0.0)
    og[..., B.SL_KIN] = kb.reshape(K, Mx, B.N_KIN * B.N_KF)
    # scatter gathered rows back to their slots
    obs = np.zeros((K, S, B.OBS_DIM), dtype=np.float32)
    oth = np.full((K, S, B.N_OTHER), -1, dtype=np.int64)
    kin = np.full((K, S, B.N_KIN), -1, dtype=np.int64)
    ki, ii = np.nonzero(valid)
    si = ic[ki, ii]
    obs[ki, si] = np.clip(og[ki, ii], -1.0, 1.0).astype(np.float32)
    oth[ki, si] = np.where(got, ic[kk3, so], -1)[ki, ii]
    kin[ki, si] = np.where(gk, ic[kk3, sk], -1)[ki, ii]
    return obs, oth, kin


class R9World:
    """K worlds of the R9 ecosystem. `step(actions (K, S) int)` = one decision (2 steps) → (obs (K, S, 107) f32, rew (K, S) f64,
    done (K, S) bool, info dict). See the module docstring for the state table and step order."""

    def __init__(self, cfg: dict, seeds: Sequence[int], *, counts: np.ndarray | None = None, record: bool = False,
                 pairs_full: bool = False):
        """cfg from r9_body.load_r9_config; mode = cfg.world.mode. counts: optional (K, 3) int species counts per world; an entry
        ≥ 0 overrides, −1 = drawn from the seed (the VecEnv passes the learner count by world number k, 7-3). TAG_PARAM always
        draws all three counts (fixed draw count), the override only replaces the value. Judge: start counts from cfg.judge.
        record: keep event lists (deaths, bites, respawns, births, hunt segments) for evaluation. pairs_full: perception over the
        full slot table (K, S, S) instead of gathered alive slots — reference path of test 22 (same results, slower)."""
        self.cfg = cfg
        w = cfg["world"]
        self.mode = str(w["mode"])
        self.judge = self.mode == "judge"
        self.size = float(w["size"])
        self.Q = int(w["quadrants"])
        self.D = int(w["decision_steps"])
        caps = np.array([int(w["slots"][n]) for n in B.SPECIES], dtype=np.int64)
        self.caps = caps
        self.sp_hi = np.cumsum(caps).astype(np.int64)
        self.sp_lo = (self.sp_hi - caps).astype(np.int64)
        self.S = int(self.sp_hi[-1])
        self.slot_sp = np.repeat(np.arange(B.N_SPECIES), caps).astype(np.int8)
        fd = cfg["food"]
        self.cell = float(fd["cell"])
        self.G = int(math.ceil(self.size / self.cell))
        sh = w["shelters"]
        per_q = int(sh["per_quadrant"])
        self.C = per_q * self.Q if per_q > 0 else int(sh["count"][1])
        if sh.get("fixed"):
            self.C = max(self.C, len(sh["fixed"]))
        self.C = max(self.C, 1)
        self.M = int(w["carcass_slots"])
        self.body = B.load_body(cfg)
        self.rules = L.LifeRules.from_cfg(cfg, self.body)
        cc = (np.arange(self.G) + 0.5) * self.cell
        cx, cy = np.meshgrid(cc, cc)                                   # (G, G): [iy, ix]
        self.cell_quad = B.quadrant_of(np.stack([cx, cy], -1), self.size, self.Q)
        self._ccx, self._ccy = cx, cy
        # body-common constants
        cm = self.body.common
        self._gait_drain = np.asarray(cm["gait_drain"], dtype=np.float64)
        self._lock = float(cm["stamina_lock"])
        self._unlock = float(cm["stamina_unlock"])
        self._wound = float(cm["wound_speed"])
        self._eat_min = float(cm["eat_min"])
        self._walk_eat = float(cm["walk_eat_mult"])
        gz = cm["graze"]
        self._graze = (float(gz["forage"]), float(gz["cohesion"]), float(gz["separation"]), float(gz["sep_radius"]),
                       int(gz["grad_blur"]))
        bt, ct, bd, cc_ = cm["bite"], cm["counter"], cm["bite_damage"], cm["carcass"]
        self._bite_cone, self._bite_appr, self._bite_cd = float(bt["cone_cos"]), float(bt["approach_min"]), int(bt["cooldown"])
        self._ct = dict(hp_min=float(ct["hp_min"]), cone=float(ct["cone_cos"]), damage=float(ct["damage"]),
                        lerp0=float(ct["age_lerp"][0]), lerp1=float(ct["age_lerp"][1]), knock=float(ct["knock_step"]),
                        knock_steps=int(ct["knock_steps"]), nobite=int(ct["nobite_steps"]), self_damage=float(ct["self_damage"]))
        self._bite_base = float(bd["base"])
        if [float(x) for x in bd["mass_age_lerp"]] != [0.12, 1.0]:
            # r9_life.mass_ratio (contract owner: life) fixes Lerp(0.12, 1, af); a different YAML value would be silently ignored
            raise ValueError("body_common.bite_damage.mass_age_lerp must be [0.12, 1.0] (r9_life.mass_ratio)")
        self._carc = dict(meat_frac=float(cc_["meat_frac"]), kg=float(cc_["kg_per_unit"]), places=int(cc_["places"]),
                          eat_r=float(cc_["eat_r"]), decay=float(cc_["decay_steps"]))
        self._push = float(cm["shelter_push"])
        rw = cfg["reward"]
        self._rw = dict(alive=float(rw["alive"]), energy=float(rw["energy"]), birth=float(rw["birth"]), death=float(rw["death"]))
        ff = rw["fallback_f"]
        self._ff = dict(on=bool(ff["enabled"]), birth=float(ff["birth"]), per=float(ff["condition_total"]) / float(ff["condition_period"]),
                        e_min=float(ff["e_min"]))
        # per-slot constants derived from the hidden slot species (physics only — never used by perception/observation)
        self._biters = np.nonzero(self.body.can_bite[self.slot_sp.astype(np.int64)])[0].astype(np.int64)
        self._bite_mat = self.body.bites[self.slot_sp[self._biters].astype(np.int64)][:, self.slot_sp.astype(np.int64)]
        rank = np.full((self.S, B.N_FOODS), 99, dtype=np.int64)
        first_grid = np.full(self.S, -1, dtype=np.int64)
        for s in range(self.S):
            order = self.body.diet_order[int(self.slot_sp[s])]
            for r_, f in enumerate(order):
                rank[s, f] = r_
            grids = [f for f in order if f in B.GRID_FOODS]
            first_grid[s] = grids[0] if grids else -1
        self._diet_rank = rank
        self._first_grid = first_grid
        eats_s = self.body.eats[self.slot_sp.astype(np.int64)]
        self._meat_only = eats_s[:, B.MEAT] & ~eats_s[:, B.GRASS] & ~eats_s[:, B.ROOT]
        self.record = bool(record)
        self.pairs_full = bool(pairs_full)
        self.step_hook = None
        self.K = 0
        K = len(seeds)
        self._alloc(K)
        cnt = None if counts is None else np.asarray(counts, dtype=np.int64).reshape(K, B.N_SPECIES)
        for k, sd in enumerate(seeds):
            self._init_world(k, int(sd), None if cnt is None else cnt[k])
        self.reset_stats()
        self._derive()
        self._perceive(update_mem=False)
        self._obs = self._observe()
        self._rew = np.zeros((K, self.S))
        self._done = np.zeros((K, self.S), dtype=bool)
        self._info: dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # allocation and world creation
    # ------------------------------------------------------------------ #

    def _alloc(self, K: int) -> None:
        S, G, C, M = self.S, self.G, self.C, self.M
        self.K = K
        z = lambda *sh, dt=np.float64: np.zeros(sh, dtype=dt)  # noqa: E731
        self.seeds = z(K, dt=np.int64)
        self.t = z(K, dt=np.int64)
        self.next_uid = np.ones(K, dtype=np.int64)
        self.s_w = z(K, dt=np.uint64)
        self.s_q = z(K, 4, dt=np.uint64)
        self.counts = z(K, 3, dt=np.int64)
        self.kin_perm = z(K, 3, dt=np.int8)
        self.run_mult = np.ones((K, 3))
        self.grass_mult = np.ones(K)
        self.root_mult = np.ones(K)
        self.juv_frac = z(K, 3)
        self.rule_f = np.full(K, float(self.cfg["rules"]["deer"]["facing_eval"]))
        self.n_cov = z(K, dt=np.int64)
        self._rmult = np.ones((K, S))
        # slots
        self.sp = np.broadcast_to(self.slot_sp, (K, S)).copy()
        self.kin_id = z(K, S, dt=np.int8)
        self.alive = z(K, S, dt=bool)
        self.uid = z(K, S, dt=np.int64)
        self.pos = z(K, S, 2)
        self.head = z(K, S, 2)
        self.head[..., 0] = 1.0
        self.vel = z(K, S, 2)
        self.disp = z(K, S, 2)
        self.dir_cmd = z(K, S, 2)
        self.knock_dir = z(K, S, 2)
        self.E = z(K, S)
        self.R = z(K, S)
        self.stam = np.ones((K, S))
        self.hp = np.ones((K, S))
        self.born = z(K, S)
        self.next_birth = z(K, S)
        self.g_speed = np.ones((K, S))
        self.g_size = np.ones((K, S))
        self.resp_t = z(K, S)
        self.stam_lock = z(K, S, dt=bool)
        self.sex = z(K, S, dt=np.int8)
        self.quad = z(K, S, dt=np.int8)
        self.mating = z(K, S, dt=bool)
        self.generation = z(K, S, dt=np.int32)
        self.parent_a = z(K, S, dt=np.int64)
        self.parent_b = z(K, S, dt=np.int64)
        self.offspring = z(K, S, dt=np.int64)
        self.killer = z(K, S, dt=np.int64)
        self.act = np.full((K, S), B.WATCH, dtype=np.int64)
        self.prev_act = np.full((K, S), B.WATCH, dtype=np.int64)
        self.bite_cd = z(K, S, dt=np.int32)
        self.knock_left = z(K, S, dt=np.int32)
        self.dead_cause = z(K, S, dt=np.int8)
        self.mem = z(K, S, S)
        # grids
        for n in ("grass", "grass_cap", "grass_regen", "root", "root_cap", "root_regen"):
            setattr(self, n, z(K, G, G))
        self.cover_cell = z(K, G, G, dt=bool)
        # shelters
        self.cov_c = np.full((K, C, 2), -1e6)
        self.cov_r = z(K, C)
        self.cov_ok = z(K, C, dt=bool)
        # carcasses
        self.carc_ok = z(K, M, dt=bool)
        self.carc_pos = z(K, M, 2)
        self.carc_meat = z(K, M)
        self.carc_meat0 = z(K, M)
        self.carc_t = z(K, M)
        self.carc_kin = np.full((K, M), -1, dtype=np.int8)
        self.carc_sp = np.full((K, M), -1, dtype=np.int8)
        self.carc_uid = z(K, M, dt=np.int64)
        self.carc_killer = z(K, M, dt=np.int64)
        # controllers, rng
        n_sp = [int(self.sp_hi[s] - self.sp_lo[s]) for s in range(3)]
        self.ctrl = [[None, None, None] for _ in range(K)]
        self.bstate = [[np.zeros((n_sp[s], 0), dtype=np.int64) for s in range(3)] for _ in range(K)]
        self.rng_act: list[list[np.random.Generator]] = [[None, None, None] for _ in range(K)]
        self.rng_bite: list[np.random.Generator] = [None] * K
        self.rng_resp: list[np.random.Generator] = [None] * K
        self.sb = B.expand_body(self.body, self.sp)
        self.life = L.LifeState.alloc(K, S, self.rules)
        self._near_ties = z(K, 3, dt=np.int64)
        # hunt tracker (record mode)
        nb = len(self._biters)
        self._h_prev = np.full((K, nb, S), np.inf)
        self._h_on = z(K, nb, S, dt=bool)
        self._h_close = z(K, nb, S, dt=np.int64)
        self._h_gap = z(K, nb, S, dt=np.int64)
        self._h_t0 = z(K, nb, S, dt=np.int64)
        self._h_ran = z(K, nb, S, dt=bool)
        self._h_tuid = z(K, nb, S, dt=np.int64)
        self._h_puid = z(K, nb, S, dt=np.int64)           # target uid that _h_prev was measured to
        self._h_wuid = z(K, nb, dt=np.int64)
        self._dec_kills: list[tuple] = []
        self.events = dict(deaths=[], bites=[], respawns=[], births=[], hunts=[])

    def _judge_counts(self) -> list[list[int]]:
        """Judge start per quadrant: [[deer, wolf, boar] for q] (3-6 판정 세계)."""
        jd = self.cfg["judge"]
        sq = jd["start_per_quadrant"]
        wp = jd["wolf_packs"]
        packs = {int(q) for q in wp["quadrants"]}
        out = []
        for q in range(self.Q):
            out.append([int(sq["deer"]), int(wp["per_pack"]) if q in packs else 0, int(sq["boar"])])
        return out

    def _region(self, q: int) -> tuple[float, float, float]:
        """(x0, y0, side) of quadrant q (whole stage when Q = 1)."""
        if self.Q == 1:
            return 0.0, 0.0, self.size
        h = 0.5 * self.size
        return float(q % 2) * h, float(q // 2) * h, h

    def _outside_shelters(self, k: int, c: np.ndarray, margin) -> np.ndarray:
        """c (..., 2) → bool: outside every shelter circle of world k by more than r + margin."""
        ok = self.cov_ok[k]
        if not ok.any():
            return np.ones(c.shape[:-1], dtype=bool)
        cc, rr = self.cov_c[k][ok], self.cov_r[k][ok]
        dx = c[..., None, 0] - cc[:, 0]
        dy = c[..., None, 1] - cc[:, 1]
        d = np.sqrt(dx * dx + dy * dy)
        return (d > rr + margin).all(-1)

    def _init_world(self, k: int, seed: int, counts_k: np.ndarray | None) -> None:
        """World k from seed: world values, shelters, grids, founders, RNG streams, cleared carcasses/memory/pairs."""
        cfg, body = self.cfg, self.body
        w, rz, fd = cfg["world"], cfg["randomize"], cfg["food"]
        G = self.G
        self.seeds[k] = seed
        self.t[k] = 0
        self.next_uid[k] = 1
        s_w, s_q = L.life_seeds(seed)
        self.s_w[k] = np.uint64(s_w)
        self.s_q[k] = np.array(s_q, dtype=np.uint64)
        # --- world values (3-8) — always the same number of draws in the same order ---
        gp = np.random.default_rng([seed, TAG_PARAM])
        cnt = [int(gp.integers(int(cfg["counts"][n][0]), int(cfg["counts"][n][1]) + 1)) for n in B.SPECIES]
        rm = [float(gp.uniform(body.run_mult_lo[s], body.run_mult_hi[s])) for s in range(3)]
        gm = float(gp.uniform(*rz["grass_regen_mult"]))
        rmu = float(gp.uniform(*rz["root_regen_mult"]))
        jf = [float(gp.uniform(*rz["juvenile_frac"][n])) for n in B.SPECIES]
        rf = float(gp.uniform(*rz["rule_deer_facing"]))
        per_q = None
        if self.judge:
            if counts_k is not None and (np.asarray(counts_k) >= 0).any():
                raise ValueError("judge world start counts come from cfg.judge (counts override is train-only)")
            jd = cfg["judge"]
            per_q = self._judge_counts()
            cnt = [sum(r[s] for r in per_q) for s in range(3)]
            gm, rmu = float(jd["grass_regen_mult"]), float(jd["root_regen_mult"])
            if jd["wolf_run_mult"] is not None:
                rm[B.WOLF] = float(jd["wolf_run_mult"])
            fo = jd["founders"]
            jf = [float(fo[n]["juvenile_frac"]) if isinstance(fo[n], dict) else 0.0 for n in B.SPECIES]
            rf = float(cfg["rules"]["deer"]["facing_eval"])
        elif counts_k is not None:
            for s in range(3):
                if int(counts_k[s]) >= 0:
                    cnt[s] = int(counts_k[s])
        for s in range(3):
            if cnt[s] > int(self.caps[s]):
                raise ValueError(f"world {k}: {B.SPECIES[s]} count {cnt[s]} exceeds slot cap {int(self.caps[s])}")
        self.counts[k] = cnt
        self.run_mult[k] = rm
        self._rmult[k] = np.asarray(rm)[self.slot_sp.astype(np.int64)]
        self.grass_mult[k], self.root_mult[k] = gm, rmu
        self.juv_frac[k] = jf
        self.rule_f[k] = rf
        # --- shelters (3-1) ---
        sh = w["shelters"]
        cov: list[tuple[float, float, float]] = []
        if sh.get("fixed"):
            cov = [(float(a), float(b), float(c)) for a, b, c in sh["fixed"]]
        else:
            gs = np.random.default_rng([seed, TAG_SHELTER])
            pq = int(sh["per_quadrant"])
            wg, gap = float(sh["wall_gap"]), float(sh["min_gap"])
            for q in range(self.Q):
                x0, y0, side = self._region(q)
                n = pq if pq > 0 else int(gs.integers(int(sh["count"][0]), int(sh["count"][1]) + 1))
                for _ in range(n):
                    r = float(gs.uniform(*sh["radius"]))
                    for _ in range(int(sh["tries"])):
                        c = gs.uniform([x0 + wg, y0 + wg], [x0 + side - wg, y0 + side - wg])
                        if all(math.hypot(c[0] - a, c[1] - b) >= gap for a, b, _r in cov):
                            cov.append((float(c[0]), float(c[1]), r))
                            break
                    # [어림] no spot after `tries` draws → this shelter is dropped (min_gap is a hard rule)
        nc = len(cov)
        if nc > self.C:
            raise ValueError(f"world {k}: {nc} shelters exceed the shelter cap {self.C}")
        self.n_cov[k] = nc
        self.cov_c[k] = -1e6
        self.cov_r[k] = 0.0
        self.cov_ok[k] = False
        cvr = np.zeros((G, G), dtype=bool)
        for i, (a, b, r) in enumerate(cov):
            self.cov_c[k, i] = (a, b)
            self.cov_r[k, i] = r
            self.cov_ok[k, i] = True
            cvr |= (self._ccx - a) ** 2 + (self._ccy - b) ** 2 <= r ** 2        # r8_world 207 (same expression)
        self.cover_cell[k] = cvr
        # --- grids (3-2): R8 patch generator copied (r8_world.py 304~313) ---
        g_, r_ = fd["grass"], fd["root"]
        tot = fd["quadrant_grass_total"]
        if not self.judge:
            cap = self._patch(np.random.default_rng([seed, TAG_GRASS]), G, int(g_["patch_blur"]), float(g_["patch_threshold"]))
            rcap = self._patch(np.random.default_rng([seed, TAG_ROOT]), G, int(r_["patch_blur"]), float(r_["patch_threshold"]))
        else:
            cap = np.zeros((G, G))
            rcap = np.zeros((G, G))
            Gq = G // 2 if self.Q == 4 else G
            for q in range(self.Q):
                iy0, ix0 = (q // 2) * Gq, (q % 2) * Gq
                cq = self._patch(np.random.default_rng([seed, TAG_GRASS, q]), Gq, int(g_["patch_blur"]), float(g_["patch_threshold"]))
                if tot is not None:
                    s_ = float(seq_sum(cq.reshape(-1)))
                    if s_ > 0.0:
                        cq = cq * (float(tot) / s_)          # [해석] capacity × 70 / sum (cells may exceed 1), before cover × 0.15
                cap[iy0:iy0 + Gq, ix0:ix0 + Gq] = cq
                rq = self._patch(np.random.default_rng([seed, TAG_ROOT, q]), Gq, int(r_["patch_blur"]), float(r_["patch_threshold"]))
                rcap[iy0:iy0 + Gq, ix0:ix0 + Gq] = rq       # [어림] root per quadrant, sum not matched
        cmg, cmr = float(g_["cover_mult"]), float(r_["cover_mult"])
        cap = np.where(cvr, cap * cmg, cap)
        rcap = np.where(cvr, rcap * cmr, rcap)
        self.grass_cap[k] = cap
        self.grass[k] = cap
        self.grass_regen[k] = float(g_["regen_base"]) * gm * np.where(cvr, cmg, 1.0)          # r8_world 313 (same order)
        self.root_cap[k] = rcap
        self.root[k] = rcap
        self.root_regen[k] = float(g_["regen_base"]) * float(r_["regen_q"]) * rmu * np.where(cvr, cmr, 1.0)
        # --- slots: clear, then founders ---
        self._clear_world_slots(k)
        gk = np.random.default_rng([seed, TAG_KIN])
        self.kin_perm[k] = gk.permutation(3).astype(np.int8)
        self.kin_id[k] = self.kin_perm[k][self.slot_sp.astype(np.int64)]
        self._place_founders(k, cnt, per_q)
        # --- RNG streams ---
        for s in range(3):
            self.rng_act[k][s] = np.random.default_rng([seed, TAG_ACT + s])
        self.rng_bite[k] = np.random.default_rng([seed, TAG_BITE])
        self.rng_resp[k] = np.random.default_rng([seed, TAG_RESP])
        # --- carcasses, memory, pairs, brain states, hunt tracker ---
        self.carc_ok[k] = False
        self.carc_meat[k] = 0.0
        self.carc_meat0[k] = 0.0
        self.carc_kin[k] = -1
        self.carc_sp[k] = -1
        self.carc_uid[k] = 0
        self.carc_killer[k] = 0
        self.mem[k] = 0.0
        self.life.reset_world(k)
        for s in range(3):
            self.bstate[k][s][:] = 0
        self._hunt_reset_world(k)

    @staticmethod
    def _patch(gen: np.random.Generator, G: int, blur: int, thr: float) -> np.ndarray:
        """R8 food patch capacity (copied from r8_world.py 305~308): box-blurred uniform noise, min-max normalised, threshold."""
        m = _box_mean(gen.random((1, G, G)), max(1, int(blur)))[0]
        m = (m - m.min()) / max(m.max() - m.min(), EPS)
        t = float(thr)
        return np.clip((m - t) / (1.0 - t), 0.0, 1.0)

    def _clear_world_slots(self, k: int) -> None:
        self.alive[k] = False
        self.uid[k] = 0
        for n in ("pos", "vel", "disp", "dir_cmd", "knock_dir"):
            getattr(self, n)[k] = 0.0
        self.head[k] = 0.0
        self.head[k, :, 0] = 1.0
        for n in ("E", "R", "born", "next_birth", "resp_t"):
            getattr(self, n)[k] = 0.0
        self.stam[k] = 1.0
        self.hp[k] = 1.0
        self.g_speed[k] = 1.0
        self.g_size[k] = 1.0
        for n in ("stam_lock", "mating"):
            getattr(self, n)[k] = False
        for n in ("sex", "quad", "generation", "parent_a", "parent_b", "offspring", "killer", "bite_cd", "knock_left", "dead_cause"):
            getattr(self, n)[k] = 0
        self.act[k] = B.WATCH
        self.prev_act[k] = B.WATCH

    def _set_slot(self, k: int, s: int, *, uid: int, pos, head, E: float, R: float, born: float, next_birth: float, sex: int,
                  g_speed: float, g_size: float, parent_a: int = 0, parent_b: int = 0, generation: int = 0) -> None:
        """Install one individual into slot s of world k. Clears everything that pointed at the slot (memory row/column, brain
        state row) and the per-individual motion state."""
        self.alive[k, s] = True
        self.uid[k, s] = int(uid)
        self.pos[k, s] = pos
        self.head[k, s] = head
        self.vel[k, s] = 0.0
        self.disp[k, s] = 0.0
        self.dir_cmd[k, s] = 0.0
        self.knock_dir[k, s] = 0.0
        self.E[k, s] = E
        self.R[k, s] = R
        self.stam[k, s] = 1.0
        self.hp[k, s] = 1.0
        self.stam_lock[k, s] = False
        self.born[k, s] = born
        self.next_birth[k, s] = next_birth
        self.sex[k, s] = int(sex)
        self.g_speed[k, s] = g_speed
        self.g_size[k, s] = g_size
        self.parent_a[k, s] = int(parent_a)
        self.parent_b[k, s] = int(parent_b)
        self.offspring[k, s] = 0
        self.generation[k, s] = int(generation)
        self.mating[k, s] = False
        self.quad[k, s] = B.quadrant_of(np.asarray(pos, dtype=np.float64), self.size, self.Q)
        self.act[k, s] = B.WATCH
        self.prev_act[k, s] = B.WATCH
        self.bite_cd[k, s] = 0
        self.knock_left[k, s] = 0
        self.resp_t[k, s] = float(self.t[k])
        self.mem[k, s, :] = 0.0
        self.mem[k, :, s] = 0.0
        sp = int(self.slot_sp[s])
        st = self.bstate[k][sp]
        if st.shape[1]:
            st[s - int(self.sp_lo[sp])] = 0

    def _place_try(self, gl, lo, hi, ok_fn, score_fn, tries: int, fallback):
        """R8 placement loop (r8_world 343~358): first candidate with ok_fn, else the best score among scored candidates."""
        best, best_d = None, -np.inf
        for _ in range(tries):
            c = gl.uniform(lo, hi)
            sc = score_fn(c)
            if sc is None:
                continue
            if ok_fn(c, sc):
                return c
            if sc > best_d:
                best, best_d = c, sc
        return best if best is not None else np.asarray(fallback, dtype=np.float64)

    def _place_founders(self, k: int, cnt: list[int], per_q: list[list[int]] | None) -> None:
        """Founders (3-6). UID order: train = species order; judge = quadrant order, deer → wolf → boar inside. Placement [어림]
        (R8 꼴, no rule in the design): wolves first (outside shelter r + margin, ≥ wolf_gap from other wolves; judge pack mates
        within pack_r of the first wolf), then deer/boar outside shelters and ≥ prey_from_wolf from every wolf (else the farthest
        candidate). Heads = DIR8[random index] [어림 — no trig]."""
        cfg, body = self.cfg, self.body
        pl, rz = cfg["placement"], cfg["randomize"]
        gl = np.random.default_rng([self.seeds[k], TAG_PLACE])
        tries = int(pl["tries"])
        rows = []                                            # (q, sp, index in group, group count)
        if per_q is None:
            for s in range(3):
                for i in range(cnt[s]):
                    rows.append((0, s, i, cnt[s]))
        else:
            for q in range(self.Q):
                for s in range(3):
                    for i in range(per_q[q][s]):
                        rows.append((q, s, i, per_q[q][s]))
        fill = [0, 0, 0]
        slots, uids = [], []
        for (q, s, i, n) in rows:
            slots.append(int(self.sp_lo[s]) + fill[s])
            fill[s] += 1
            uids.append(int(self.next_uid[k]))
            self.next_uid[k] += 1
        pos = {}
        wolves: list[np.ndarray] = []
        pack_first: dict[int, np.ndarray] = {}
        wmargin = float(pl["shelter_margin"])
        order = [r for r in range(len(rows)) if rows[r][1] == B.WOLF] + [r for r in range(len(rows)) if rows[r][1] != B.WOLF]
        heads, fats = {}, {}
        for r in order:
            q, s, i, n = rows[r]
            x0, y0, side = self._region(q)
            lo, hi = [x0, y0], [x0 + side, y0 + side]
            margin = wmargin if not bool(body.shelter_enter[s]) else 0.0
            if s == B.WOLF:
                if self.judge and q in pack_first:
                    f0 = pack_first[q]
                    pr = float(pl["pack_r"])

                    def ok_pack(c, sc, f0=f0, pr=pr):
                        return True

                    def sc_pack(c, f0=f0, pr=pr, margin=margin):
                        if not (0.0 <= c[0] <= self.size and 0.0 <= c[1] <= self.size):
                            return None
                        if math.hypot(c[0] - f0[0], c[1] - f0[1]) > pr or not self._outside_shelters(k, c, margin):
                            return None
                        return 0.0
                    p = self._place_try(gl, [f0[0] - pr, f0[1] - pr], [f0[0] + pr, f0[1] + pr], ok_pack, sc_pack, tries,
                                        [min(max(f0[0] + 0.5 * pr, 0.0), self.size), f0[1]])
                else:
                    gap = float(pl["wolf_gap"])

                    def sc_w(c, margin=margin):
                        if not self._outside_shelters(k, c, margin):
                            return None
                        return min((math.hypot(c[0] - a[0], c[1] - a[1]) for a in wolves), default=1e9)
                    p = self._place_try(gl, lo, hi, lambda c, sc, gap=gap: sc >= gap, sc_w, tries, [x0 + 1.0, y0 + 1.0])
                    if self.judge:
                        pack_first[q] = p
                wolves.append(p)
            else:
                gap = float(pl["prey_from_wolf"])
                wp = np.asarray(wolves).reshape(-1, 2)

                def sc_p(c, margin=margin, wp=wp):
                    if not self._outside_shelters(k, c, margin):
                        return None
                    if not len(wp):
                        return 1e9
                    d = wp - c
                    return float(np.sqrt(d[:, 0] * d[:, 0] + d[:, 1] * d[:, 1]).min())
                p = self._place_try(gl, lo, hi, lambda c, sc, gap=gap: sc >= gap, sc_p, tries, [x0 + 0.5 * side, y0 + 0.5 * side])
            pos[r] = p
            heads[r] = B.DIR8[int(gl.integers(0, 8))]
            fats[r] = float(gl.uniform(*rz["fat_init"])) if not self.judge else float(cfg["judge"]["start"]["fat"])
        # life values (hash) and installation in uid order
        sw = int(self.s_w[k])
        for r, (q, s, i, n) in enumerate(rows):
            sq = int(self.s_q[k, q])
            uid = uids[r]
            gsp, gsz = L.founder_genome(body, s, sw, sq, uid)
            sex = L.founder_sex(body, s, sw, sq, uid, i)
            mat, mx = float(body.maturity[s]), float(body.max_founder_age[s])
            if self.judge and not isinstance(cfg["judge"]["founders"][B.SPECIES[s]], dict):
                if cfg["judge"]["founders"][B.SPECIES[s]] != "just_mature":
                    raise ValueError(f"judge.founders.{B.SPECIES[s]} must be just_mature or {{juvenile_frac: x}}")
                age = mat                                    # 막 성숙한 성체 (born = t − 성숙)
            else:
                aseed = L.age_seed(sq, s)
                age = L.founder_age(mat, float(self.juv_frac[k, s]), mx, aseed, L.founder_rank(i, n, aseed), n)
            e0 = float(cfg["judge"]["start"]["energy"][B.SPECIES[s]]) if self.judge else float(rz["start_energy"])
            self._set_slot(k, slots[r], uid=uid, pos=pos[r], head=heads[r], E=e0, R=fats[r], born=-float(age),
                           next_birth=L.first_birth_time(body, s, 0.0, sq, uid), sex=sex, g_speed=gsp, g_size=gsz)

    # ------------------------------------------------------------------ #
    # life cycle of the batch
    # ------------------------------------------------------------------ #

    def reset(self, seeds: Sequence[int] | None = None, counts: np.ndarray | None = None) -> np.ndarray:
        """Re-initialise every world (same seeds if None) and return the first observation. Statistics restart."""
        sd = [int(s) for s in (self.seeds if seeds is None else seeds)]
        if len(sd) != self.K:
            self._alloc(len(sd))
        cnt = None if counts is None else np.asarray(counts, dtype=np.int64).reshape(len(sd), 3)
        for k, s in enumerate(sd):
            self._init_world(k, s, None if cnt is None else cnt[k])
        self.reset_stats()
        self.refresh()
        return self._obs

    def reinit(self, k: int, seed: int, counts_k: np.ndarray | None = None) -> None:
        """Replace world k by a new seed (VecEnv staggered renew); statistics keep counting; observation rebuilt (other worlds'
        perception and observation are recomputed from unchanged state — same values)."""
        self._hunt_flush_world(k, "reset")
        self._init_world(k, int(seed), counts_k)
        self.refresh()

    def refresh(self) -> None:
        """Recompute derived values, perception (no memory update) and the observation after outside edits (tests, eval)."""
        self._derive()
        self._perceive(update_mem=False)
        self._obs = self._observe()

    def set_controller(self, k: int, sp: int, ctrl) -> None:
        """Fixed brain (r9_brains.Controller) for species sp of world k; None = actions come from outside (learner). The brain
        state block is re-allocated (zeros) for the brain's n_state."""
        self.ctrl[k][sp] = ctrl
        n = int(self.sp_hi[sp] - self.sp_lo[sp])
        ns = int(getattr(ctrl.brain, "n_state", 0)) if ctrl is not None else 0
        self.bstate[k][sp] = np.zeros((n, ns), dtype=np.int64)

    # ------------------------------------------------------------------ #
    # decisions
    # ------------------------------------------------------------------ #

    def decide(self, learner_sp: int | None = None, learner_actions: np.ndarray | None = None,
               default_action: int = B.WATCH) -> np.ndarray:
        """Order 0 (the contract's `act()`; renamed because the contract also names the (K, S) action array `act`, which r9_life
        reads — an instance array would shadow a method of the same name): (K, S) int64 actions. Learner slots from `learner_actions` — (K, block) or flat in `learner_index(sp)` order —
        and every other species block from its controller, one same-shape call per world (7-10). Every species' action stream
        draws (block, 19) uniforms every decision, whoever decides (test 27); blocks without a controller get default_action."""
        K, S = self.K, self.S
        a = np.full((K, S), int(default_action), dtype=np.int64)
        near = np.zeros((K, 3), dtype=np.int64)
        if learner_sp is not None:
            lo, hi = int(self.sp_lo[learner_sp]), int(self.sp_hi[learner_sp])
            la = np.asarray(learner_actions, dtype=np.int64)
            if la.shape == (K, hi - lo):
                a[:, lo:hi] = la
            else:
                ek, es = self.learner_index(learner_sp)
                la = la.reshape(-1)
                if la.shape[0] != len(ek):
                    raise ValueError(f"learner actions: want (K, {hi - lo}) or ({len(ek)},), got {la.shape}")
                a[ek, es] = la
        for s in range(3):
            lo, hi = int(self.sp_lo[s]), int(self.sp_hi[s])
            n = hi - lo
            for k in range(K):
                ctrl = self.ctrl[k][s]
                if ctrl is None or s == learner_sp:
                    self.rng_act[k][s].random((n, B.N_ACTIONS))          # stream kept in step (decide_block draws the same)
                    continue
                acts, gap = BR.decide_block(ctrl, self._obs[k, lo:hi], self.rng_act[k][s], self.bstate[k][s],
                                            {"facing_f": float(self.rule_f[k])})
                a[k, lo:hi] = acts
                near[k, s] = int((np.asarray(gap)[self.alive[k, lo:hi]] < BR.NEAR_TIE).sum())
        self._near_ties = near
        return a

    def step(self, actions: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
        """One decision. actions (K, S) int in 0..18 (dead/empty slots ignored). Returns (obs, rew, done, info): done = died during
        the decision; train-world dead slots are already respawned (obs is the new individual, R8 rule); info keys INFO_KEYS."""
        K, S = self.K, self.S
        a = np.asarray(actions).reshape(K, S).astype(np.int64)
        if a.min() < 0 or a.max() >= B.N_ACTIONS:
            raise ValueError(f"actions must be 0..{B.N_ACTIONS - 1}: {a.min()}..{a.max()}")
        self.prev_act = self.act.copy()
        self.act = np.where(self.alive, a, B.WATCH)
        j = B.action_dir_index(self.act)
        rot = B.rotate(self.head, B.DIR8[np.clip(j, 0, 7)])
        self.dir_cmd = np.where((j >= 0)[..., None], rot, 0.0)
        self._decision_stats()
        self._dec_kills = []
        rew = np.zeros((K, S))
        done = np.zeros((K, S), dtype=bool)
        cause = np.zeros((K, S), dtype=np.int8)
        duid = np.zeros((K, S), dtype=np.int64)
        kill = np.zeros((K, S), dtype=np.int64)
        births = np.zeros((K, S), dtype=np.int64)
        resp = np.zeros((K, S), dtype=bool)
        newb = np.zeros((K, S), dtype=bool)
        for _ in range(self.D):
            r, dead, b, rs, nb = self._phys()
            rew += np.where(done, 0.0, r)
            first = dead & ~done
            cause = np.where(first, self.dead_cause, cause)
            duid = np.where(first, self._dead_uid, duid)
            kill = np.where(first, self.killer, kill)
            births += np.where(done, 0, b)
            done |= dead
            resp |= rs
            newb |= nb
        if self.record:
            self._track_hunts()
        self._obs = self._observe()
        self._rew, self._done = rew, done
        self._info = dict(dead_cause=cause, dead_uid=duid, killer=kill, respawned=resp, newborn=newb, births=births,
                          alive=self.alive.copy(), uid=self.uid.copy(), t=self.t.copy(), near_ties=self._near_ties_dec.copy())
        return self._obs, rew, done, self._info

    # --- read-only views ---
    def obs(self) -> np.ndarray:
        """Last observation (K, S, 107) float32."""
        return self._obs

    def observe(self) -> np.ndarray:
        return self._obs

    def rewards(self) -> np.ndarray:
        """Rewards (K, S) float64 of the last decision."""
        return self._rew

    def info(self) -> dict[str, Any]:
        """Info dict of the last decision (INFO_KEYS)."""
        return self._info

    def obs_maps(self) -> tuple[np.ndarray, np.ndarray]:
        """Hidden slot maps of the last observation: other-species columns (K, S, 6) and near-kin columns (K, S, 2), −1 empty."""
        return self._other_slots, self._kin_slots

    def alive_index(self) -> tuple[np.ndarray, np.ndarray]:
        """(idx (K, Mx) int64 alive slots in slot order with −1 padding, n (K,)). Mx = max alive over the batch (3-9 모으기)."""
        n = self.alive.sum(1).astype(np.int64)
        Mx = max(int(n.max()) if self.K else 0, 1)
        order = np.argsort(~self.alive, axis=1, kind="stable")[:, :Mx]
        valid = np.arange(Mx)[None, :] < n[:, None]
        return np.where(valid, order, -1).astype(np.int64), n

    def learner_index(self, sp: int) -> tuple[np.ndarray, np.ndarray]:
        """(env_k, env_s) int64 for the learner VecEnv: world-major, then slot, slots lo_sp .. lo_sp + counts[k, sp] − 1 (7-3)."""
        lo = int(self.sp_lo[sp])
        c = self.counts[:, sp].astype(np.int64)
        ek = np.repeat(np.arange(self.K, dtype=np.int64), c)
        es = np.concatenate([lo + np.arange(int(x), dtype=np.int64) for x in c]) if self.K else np.zeros(0, np.int64)
        return ek, es

    def world_params(self, k: int) -> dict:
        """Recorded world values: seed, counts, run mult, regen mults, juvenile fracs, shelters, rule f, controllers' labels."""
        ok = self.cov_ok[k]
        return dict(seed=int(self.seeds[k]), mode=self.mode, counts={n: int(self.counts[k, s]) for s, n in enumerate(B.SPECIES)},
                    run_mult={n: float(self.run_mult[k, s]) for s, n in enumerate(B.SPECIES)},
                    grass_regen_mult=float(self.grass_mult[k]), root_regen_mult=float(self.root_mult[k]),
                    juvenile_frac={n: float(self.juv_frac[k, s]) for s, n in enumerate(B.SPECIES)},
                    rule_f=float(self.rule_f[k]), kin_perm=self.kin_perm[k].tolist(),
                    shelters=[[float(c[0]), float(c[1]), float(r)] for c, r in zip(self.cov_c[k][ok], self.cov_r[k][ok])],
                    controllers={n: (None if self.ctrl[k][s] is None else
                                     dict(label=self.ctrl[k][s].label, brain=self.ctrl[k][s].brain.name,
                                          stochastic=bool(self.ctrl[k][s].stochastic))) for s, n in enumerate(B.SPECIES)})

    # ------------------------------------------------------------------ #
    # statistics
    # ------------------------------------------------------------------ #

    def reset_stats(self) -> None:
        K = self.K
        z = lambda *sh, dt=np.int64: np.zeros(sh, dtype=dt)  # noqa: E731
        self.st = dict(
            steps=z(K),
            alive_steps=z(K, 3),
            decisions=z(K, 3),
            actions=z(K, 3, B.N_ACTIONS),
            run_steps=z(K, 3),                       # effective RUN gait
            in_shelter_steps=z(K, 3),
            wall_steps=z(K, 3),                      # within world.wall_band of any wall (8-4)
            corner_steps=z(K, 3),                    # within the band of two walls (8-4 구석 지키기)
            deaths=z(K, 3, 4),                       # [species, cause]
            deaths_wall=z(K, 3),
            bites=z(K, 3, 3),                        # [prey species, outcome]
            wolf_hp_lost=z(K, dt=np.float64),
            eaten_units=z(K, 3, 3, dt=np.float64),   # [eater species, food]
            eaten_e=z(K, 3, 3, dt=np.float64),
            grid_regen=z(K, 2, dt=np.float64),       # food units regrown [grass, root]
            meat_created=z(K, 3, dt=np.float64),     # by dead species
            meat_decayed=z(K, dt=np.float64),
            meat_overflow=z(K),                      # carcasses dropped because the carcass table was full
            meat_overflow_lost=z(K, dt=np.float64),
            birth_credits=z(K, 3),                   # parent credits (2 per delivery)
            newborns=z(K, 3),
            respawns=z(K, 3, 3),                     # [species, form]
            near_ties=z(K, 3),
        )

    def stats_snapshot(self) -> dict:
        return {k: v.copy() for k, v in self.st.items() if isinstance(v, np.ndarray)}

    def _decision_stats(self) -> None:
        st = self.st
        ki, si = np.nonzero(self.alive)
        sp = self.slot_sp[si].astype(np.int64)
        np.add.at(st["decisions"], (ki, sp), 1)
        np.add.at(st["actions"], (ki, sp, self.act[ki, si]), 1)
        st["near_ties"] += self._near_ties
        self._near_ties_dec = self._near_ties
        self._near_ties = np.zeros_like(self._near_ties)

    # ------------------------------------------------------------------ #
    # one step (module docstring 'Step order')
    # ------------------------------------------------------------------ #

    def _derive(self) -> None:
        """Per-step derived arrays at the current t (LH 196~203)."""
        sb = self.sb
        t = self.t.astype(np.float64)[:, None]
        self.af = L.age_frac(t, self.born, sb["maturity"])
        self.gr = L.growth(self.af, sb["growth_smooth"])
        self.bscale = L.body_scale(self.g_size, self.gr)
        self.size_obs = sb["size0"] * self.bscale
        self.spd_scale = L.speed_scale(self.g_speed, self.gr)
        self.maint = L.maintenance(self.g_size, self.g_speed)
        self.mature = self.af >= 1.0

    def _phys(self):
        K, S = self.K, self.S
        self._derive()
        self.dead_cause[:] = CAUSE_NONE
        self.killer[:] = 0
        self._dead = np.zeros((K, S), dtype=bool)
        self._dead_uid = np.zeros((K, S), dtype=np.int64)
        alive0 = self.alive.copy()
        C = self.sb["reserve_cap"]
        val0 = self.E + self.R * C
        self._move()                                       # 1
        self._bite()                                       # 2
        gain_e = self._eat()                               # 3
        self._metabolism(gain_e)                           # 4
        ev = self._breed()                                 # 5
        newborn = np.zeros((K, S), dtype=bool)
        for nb in ev.newborns:
            self._install_newborn(nb)
            newborn[nb.k, nb.slot] = True
        dead = self._deaths()                              # 6
        val1 = self.E + self.R * C
        births = np.asarray(ev.births, dtype=np.int64)
        rw = self._rw
        if self._ff["on"]:
            cond = self.alive & self.mature & (self.E >= self._ff["e_min"])
            bterm = self._ff["birth"] * births + self._ff["per"] * cond
        else:
            bterm = rw["birth"] * births
        r = rw["alive"] + rw["energy"] * (val1 - val0) + bterm + rw["death"] * dead
        r = np.where(alive0, r, 0.0)
        self._regrow()                                     # 7
        resp = self._respawn(dead) if not self.judge else np.zeros((K, S), dtype=bool)   # 8
        self._perceive(update_mem=True)                    # 9
        self._step_stats(alive0, births, newborn)
        self.t += 1
        if self.step_hook is not None:                     # eval tools — must not change the world
            self.step_hook(self, dead, dict(births=births, newborn=newborn, respawned=resp))
        return r, dead, births, resp, newborn

    def _step_stats(self, alive0, births, newborn) -> None:
        st = self.st
        st["steps"] += 1
        band = float(self.cfg["world"]["wall_band"])
        P = self.pos
        nx = (P[..., 0] < band) | (P[..., 0] > self.size - band)
        ny = (P[..., 1] < band) | (P[..., 1] > self.size - band)
        edge = self._edge1                                 # after the move (a respawned slot keeps its old edge — stats only)
        for s in range(3):
            m = slice(int(self.sp_lo[s]), int(self.sp_hi[s]))
            a0 = alive0[:, m]
            st["alive_steps"][:, s] += a0.sum(1)
            al = self.alive[:, m]
            st["run_steps"][:, s] += (a0 & (self._gait[:, m] == B.G_RUN)).sum(1)
            st["in_shelter_steps"][:, s] += (al & (edge[:, m] <= 0.0)).sum(1)
            st["wall_steps"][:, s] += (al & (nx[:, m] | ny[:, m])).sum(1)
            st["corner_steps"][:, s] += (al & nx[:, m] & ny[:, m]).sum(1)
            st["birth_credits"][:, s] += births[:, m].sum(1)
            st["newborns"][:, s] += newborn[:, m].sum(1)

    # --- 1 move ---------------------------------------------------------
    def _first_food(self, P: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """(K, S) first available food in diet order at P (−1 none): grid cell ≥ eat_min, or an eatable carcass (other kin,
        meat > 0) within carcass.eat_r (3-3, 5절 EAT)."""
        K = self.K
        sb = self.sb
        kk = np.arange(K)[:, None]
        ix, iy = _cells(P, self.cell, self.G)
        eats = sb["eats"]
        av = np.zeros((K, self.S, B.N_FOODS), dtype=bool)
        av[..., B.GRASS] = mask & eats[..., B.GRASS] & (self.grass[kk, iy, ix] >= self._eat_min)
        av[..., B.ROOT] = mask & eats[..., B.ROOT] & (self.root[kk, iy, ix] >= self._eat_min)
        mm = mask & eats[..., B.MEAT]
        if mm.any() and self.carc_ok.any():
            ki, si = np.nonzero(mm)
            d = self.carc_pos[ki] - P[ki, si][:, None, :]
            dd = np.sqrt(d[..., 0] * d[..., 0] + d[..., 1] * d[..., 1])
            ok = (self.carc_ok[ki] & (self.carc_meat[ki] > 0.0) & (self.carc_kin[ki] != self.kin_id[ki, si][:, None])
                  & (dd <= self._carc["eat_r"]))
            av[ki, si, B.MEAT] = ok.any(1)
        rank = np.where(av, self._diet_rank[None], 99)
        f = rank.argmin(-1)
        best = np.take_along_axis(rank, f[..., None], -1)[..., 0]
        return np.where(best < 99, f, -1)

    def _graze_dir(self, need: np.ndarray) -> np.ndarray:
        """EAT walking direction (K, S, 2) for the slots in `need` (5절, R8 식): unit(0.83 food gradient + 0.71 kin cohesion +
        1.35 separation) from the last perception, computed on those gathered rows only. Food gradient = Σ_grid-diet e_f
        ∇boxmean_2(grid_f); meat-only bodies: toward the nearest sensed carcass (none → cohesion and separation only). Separation
        from all alive same-kin within sep_radius (R8 used all deer) [해석]."""
        pc = self._pc
        K = self.K
        out = np.zeros((K, self.S, 2))
        fw, cw, sw, sep_r, gb = self._graze
        ic, valid = pc["ic"], pc["valid"]
        kk = np.arange(K)[:, None]
        rk, ri = np.nonzero(valid & need[kk, ic])
        if not len(rk):
            return out
        si = ic[rk, ri]
        same, perc, pair = pc["same"][rk, ri], pc["perc"][rk, ri], pc["pair"][rk, ri]
        dx, dy, dist, invd = pc["dx"][rk, ri], pc["dy"][rk, ri], pc["dist"][rk, ri], pc["invd"][rk, ri]
        Pn = pc["P"][rk]
        Pi = pc["P"][rk, ri]
        pk = perc & same
        kf = pk.astype(np.float64)
        cnt = pk.sum(-1)
        cf = np.maximum(cnt, 1).astype(np.float64)
        cx = (seq_sum(kf * Pn[..., 0], -1) + 0.0) / cf
        cy = (seq_sum(kf * Pn[..., 1], -1) + 0.0) / cf
        to_c = np.where((cnt > 0)[..., None], _unit(np.stack([cx, cy], -1) - Pi), 0.0)
        wgt = np.clip(1.0 - dist / sep_r, 0.0, None)
        wgt = np.where(pair & same, wgt, 0.0)
        c = wgt * invd
        sep = -np.stack([seq_sum(c * dx, -1) + 0.0, seq_sum(c * dy, -1) + 0.0], -1)
        n = np.sqrt(_len2(sep))[..., None]
        sep = sep * np.minimum(1.0, 1.0 / np.maximum(n, EPS))
        sb = self.sb
        eats, epu = sb["eats"][rk, si], sb["e_per_unit"][rk, si]
        ix, iy = _cells(Pi, self.cell, self.G)
        fgx = np.zeros(len(rk))
        fgy = np.zeros(len(rk))
        for f, grid in ((B.GRASS, self.grass), (B.ROOT, self.root)):
            wf = np.where(eats[..., f], epu[..., f], 0.0)
            if not (wf > 0).any():
                continue
            bm = _box_mean(grid, max(1, int(gb)))
            gy, gx = np.gradient(bm, axis=(1, 2))
            fgx = fgx + wf * gx[rk, iy, ix]
            fgy = fgy + wf * gy[rk, iy, ix]
        fg = _unit(np.stack([fgx, fgy], -1))
        mo = self._meat_only[si]
        if mo.any():
            key = np.where(pc["csens"][rk, ri], pc["cdist"][rk, ri], np.inf)
            jc = key.argmin(-1)
            hasc = np.take_along_axis(key, jc[..., None], -1)[..., 0] < np.inf
            vx = np.take_along_axis(pc["cdx"][rk, ri], jc[..., None], -1)[..., 0]
            vy = np.take_along_axis(pc["cdy"][rk, ri], jc[..., None], -1)[..., 0]
            tm = np.where(hasc[..., None], _unit(np.stack([vx, vy], -1)), 0.0)
            fg = np.where(mo[..., None], tm, fg)
        raw = fw * fg + cw * to_c + sw * sep
        out[rk, si] = _unit(raw)
        return out

    def _move(self) -> None:
        """Order 1 (3-9): action → target velocity → acceleration clip → self move + wall slide → knock (contact) → shelter push
        (contact, non-entering bodies). Simultaneous from the previous positions. [해석] the multipliers (growth·gene·wound·weak·
        lock → walk) scale the target and the acceleration limit clips the change, so |Δvel| ≤ accel every step."""
        K, S = self.K, self.S
        sb = self.sb
        alive = self.alive
        act = self.act
        P0 = self.pos
        kk = np.arange(K)[:, None]
        jsh, edge0 = _shelter_edge(P0, self.cov_c, self.cov_r, self.cov_ok)
        inside0 = edge0 <= 0.0
        gait = np.zeros((K, S), dtype=np.int64)
        base = np.zeros((K, S))
        dirv = np.zeros((K, S, 2))
        ekind = np.full((K, S), -1, dtype=np.int64)
        emult = np.zeros((K, S))
        lockd = self.stam_lock
        walk_sp = sb["walk_speed"]
        run_sp = sb["run_speed"] * self._rmult
        # EAT (5절)
        is_eat = alive & (act == B.EAT)
        if is_eat.any():
            kind = self._first_food(P0, is_eat)
            ok = kind >= 0
            need = is_eat & ~ok
            if need.any():
                dg = self._graze_dir(need)
                has = _len2(dg) > EPS * EPS
            else:
                dg = np.zeros((K, S, 2))
                has = np.zeros((K, S), dtype=bool)
            walk = need & has
            stand = is_eat & ~walk
            ekind = np.where(is_eat & ok, kind, ekind)
            ekind = np.where(walk, np.where(sb["eats"][..., B.GRASS], B.GRASS, -1), ekind)
            # R8: standing EAT without food ≥ eat_min (no direction) still eats its cell at rate 1 — first grid food of the diet
            ekind = np.where(stand & ~ok, self._first_grid[None, :], ekind)
            emult = np.where(stand, 1.0, np.where(walk, self._walk_eat, 0.0))
            gait = np.where(walk, B.G_WALK, gait)
            base = np.where(walk, walk_sp, base)
            dirv = np.where(walk[..., None], dg, dirv)
        # WALK_j / RUN_j: direction fixed at the decision (dir_cmd)
        wk = alive & (act >= B.WALK_FIRST) & (act <= B.WALK_LAST)
        rn = alive & (act >= B.RUN_FIRST) & (act <= B.RUN_LAST)
        dirv = np.where((wk | rn)[..., None], self.dir_cmd, dirv)
        rok, rlk = rn & ~lockd, rn & lockd
        gait = np.where(wk | rlk, B.G_WALK, np.where(rok, B.G_RUN, gait))
        base = np.where(wk | rlk, walk_sp, np.where(rok, run_sp, base))
        # SHELTER: entering bodies outside run to the nearest (edge) shelter centre; inside or non-entering (wolf) stand (3-5)
        sh = alive & (act == B.SHELTER) & sb["shelter_enter"] & ~inside0 & np.isfinite(edge0)
        if sh.any():
            cpos = self.cov_c[kk, jsh]
            dirv = np.where(sh[..., None], _unit(cpos - P0), dirv)
            sok, slk = sh & ~lockd, sh & lockd
            gait = np.where(slk, B.G_WALK, np.where(sok, B.G_RUN, gait))
            base = np.where(slk, walk_sp, np.where(sok, run_sp, base))
        hp_f = self._wound + (1.0 - self._wound) * self.hp
        weak = np.where(self.E < sb["weak_e"], sb["weak_speed"], 1.0)
        tsp = base * self.spd_scale * hp_f * weak
        tv = dirv * tsp[..., None]
        v0 = self.vel
        dv = tv - v0
        n = np.sqrt(_len2(dv))
        acc = sb["accel"]
        big = n > acc
        sc = acc / np.maximum(n, EPS)
        v1 = np.where(big[..., None], v0 + dv * sc[..., None], tv)
        v1 = np.where(alive[..., None], v1, 0.0)
        Ps = P0 + v1
        P1 = np.clip(Ps, 0.0, self.size)
        self._vel_free = v1                                    # accel-limited self velocity before the wall (test 19)
        self._wall = P1 != Ps
        v1 = np.where(self._wall, P1 - P0, v1)                 # wall slide: the blocked component of the self velocity
        P2 = P1
        kn = alive & (self.knock_left > 0)
        if kn.any():
            P2 = np.clip(np.where(kn[..., None], P1 + self.knock_dir * self._ct["knock"], P1), 0.0, self.size)
            self.knock_left = np.where(kn, self.knock_left - 1, self.knock_left).astype(np.int32)
        pushed = np.zeros((K, S), dtype=bool)
        ne = alive & ~sb["shelter_enter"]
        if ne.any():
            for ci in range(self.C):
                okc = self.cov_ok[:, ci]
                if not okc.any():
                    continue
                c = self.cov_c[:, ci][:, None, :]
                rr = (self.cov_r[:, ci] + self._push)[:, None]
                v = P2 - c
                dd = np.sqrt(_len2(v))
                inn = ne & okc[:, None] & (dd < rr)
                if inn.any():
                    pu = np.where((dd > EPS)[..., None], v / np.maximum(dd, EPS)[..., None], np.array([1.0, 0.0]))
                    P2 = np.where(inn[..., None], c + pu * rr[..., None], P2)
                    pushed |= inn
            P2 = np.clip(P2, 0.0, self.size)
        disp = np.where(alive[..., None], P2 - P0, 0.0)
        self._jsh1, self._edge1 = _shelter_edge(P2, self.cov_c, self.cov_r, self.cov_ok)
        mv = _len2(v1) > EPS * EPS
        self.head = np.where(mv[..., None], _unit(v1), self.head)
        self.pos = P2
        self.vel = v1
        self.disp = disp
        self.quad = B.quadrant_of(P2, self.size, self.Q)
        self._gait = gait
        self._drain = sb["drain"] * self._gait_drain[gait] * self.maint
        self._ekind, self._emult = ekind, emult
        self._tspeed = tsp
        self._contact = disp - v1
        self._knocked, self._pushed = kn, pushed

    # --- 2 bite ---------------------------------------------------------
    def _kill(self, k: int, s: int, cause: int, killer_uid: int) -> None:
        self._dead[k, s] = True
        self._dead_uid[k, s] = self.uid[k, s]
        self.alive[k, s] = False
        self.dead_cause[k, s] = cause
        self.killer[k, s] = int(killer_uid)

    def _bite(self) -> None:
        """Order 2 (3-4). Biter order = rng_bite permutation of the biter slots, drawn every step for every world.
        Pairs are computed only for alive biters ready to bite (bite_cd 0) × alive slots gathered in slot order (3-9 모으기) —
        the L0 judge variant has 64 wolf slots × 1,024 slots, and the full (K, nb, S) table cost ~2 ms per world-step there
        (Fix 단계 검토 medium). Elementwise the same formulas, argmin over the gathered columns = first lowest slot, so the
        result is bit-identical to `_bite_full` (pairs_full reference path, test 22b)."""
        if self.pairs_full:
            self._bite_full()
            return
        K = self.K
        bs = self._biters
        nb = len(bs)
        perms = [self.rng_bite[k].permutation(nb) for k in range(K)]
        if nb == 0:
            return
        self.bite_cd[:, bs] = np.maximum(self.bite_cd[:, bs] - 1, 0)
        w_ok = self.alive[:, bs] & (self.bite_cd[:, bs] == 0)          # (K, nb)
        rk, rw = np.nonzero(w_ok)                                       # ready biter rows, world-major then biter
        if not len(rk):
            return
        idx, _n = self.alive_index()                                    # (K, Mx) alive slots in slot order
        valid = idx >= 0
        ic = np.where(valid, idx, 0)
        wsl = bs[rw]
        Pw, Hw, Vw = self.pos[rk, wsl], self.head[rk, wsl], self.vel[rk, wsl]     # (n, 2)
        reach = self.sb["bite_r"][rk, wsl] * self.bscale[rk, wsl]                   # (n,)
        icr = ic[rk]                                                    # (n, Mx)
        Pt = self.pos[rk[:, None], icr]                                 # (n, Mx, 2)
        dx = Pt[..., 0] - Pw[:, None, 0]
        dy = Pt[..., 1] - Pw[:, None, 1]
        dist = np.sqrt(dx * dx + dy * dy)
        invd = 1.0 / np.maximum(dist, EPS)
        cone = (dx * Hw[:, None, 0] + dy * Hw[:, None, 1]) * invd >= self._bite_cone
        appr = (dx * Vw[:, None, 0] + dy * Vw[:, None, 1]) * invd > self._bite_appr
        prey_ok = self.alive & (self._edge1 > 0.0)
        can = (self._bite_mat[rw[:, None], icr] & valid[rk] & prey_ok[rk[:, None], icr] & (dist <= reach[:, None]) & cone & appr)
        if not can.any():
            return
        row = np.full((K, nb), -1, dtype=np.int64)
        row[rk, rw] = np.arange(len(rk))
        for k in np.unique(rk[can.any(1)]):
            for wi in perms[k]:
                r = int(row[k, wi])
                if r < 0 or not can[r].any():
                    continue
                w = int(bs[wi])
                if not self.alive[k, w]:
                    continue
                cand = can[r] & self.alive[k, icr[r]]                   # kills earlier in this step
                if not cand.any():
                    continue
                g = int(np.argmin(np.where(cand, dist[r], np.inf)))
                self._resolve_bite(int(k), w, int(icr[r, g]), float(dist[r, g]))

    def _bite_full(self) -> None:
        """Reference path of `_bite` over the full (K, nb, S) table (pairs_full=True, test 22b)."""
        K = self.K
        bs = self._biters
        nb = len(bs)
        perms = [self.rng_bite[k].permutation(nb) for k in range(K)]
        if nb == 0:
            return
        self.bite_cd[:, bs] = np.maximum(self.bite_cd[:, bs] - 1, 0)
        Pw, Hw, Vw = self.pos[:, bs], self.head[:, bs], self.vel[:, bs]
        reach = self.sb["bite_r"][:, bs] * self.bscale[:, bs]
        dx = self.pos[:, None, :, 0] - Pw[:, :, None, 0]
        dy = self.pos[:, None, :, 1] - Pw[:, :, None, 1]
        dist = np.sqrt(dx * dx + dy * dy)
        invd = 1.0 / np.maximum(dist, EPS)
        cone = (dx * Hw[:, :, None, 0] + dy * Hw[:, :, None, 1]) * invd >= self._bite_cone
        appr = (dx * Vw[:, :, None, 0] + dy * Vw[:, :, None, 1]) * invd > self._bite_appr
        prey_ok = self.alive & (self._edge1 > 0.0)
        w_ok = self.alive[:, bs] & (self.bite_cd[:, bs] == 0)
        can = (self._bite_mat[None] & prey_ok[:, None, :] & (dist <= reach[..., None]) & cone & appr & w_ok[..., None])
        if not can.any():
            return
        for k in np.nonzero(can.any((1, 2)))[0]:
            for wi in perms[k]:
                if not can[k, wi].any():
                    continue
                w = int(bs[wi])
                if not self.alive[k, w]:
                    continue
                cand = can[k, wi] & self.alive[k]
                if not cand.any():
                    continue
                j = int(np.argmin(np.where(cand, dist[k, wi], np.inf)))
                self._resolve_bite(k, w, j, float(dist[k, wi, j]))

    def _resolve_bite(self, k: int, w: int, j: int, d: float) -> None:
        sb, ct = self.sb, self._ct
        spj = int(self.slot_sp[j])
        out = BITE_WOUND
        if not bool(sb["has_hp"][k, j]):
            self._kill(k, j, CAUSE_BITE, self.uid[k, w])
            self.bite_cd[k, w] = self._bite_cd
            out = BITE_KILL
        else:
            tw = self.pos[k, w] - self.pos[k, j]
            tl = math.sqrt(tw[0] * tw[0] + tw[1] * tw[1])
            tu = tw / tl if tl > EPS else np.array([1.0, 0.0])
            front = float(self.head[k, j, 0] * tu[0] + self.head[k, j, 1] * tu[1])
            if bool(sb["counter"][k, j]) and self.hp[k, j] >= ct["hp_min"] and front >= ct["cone"]:
                af = float(self.af[k, j])
                dmg = ct["damage"] * float(self.bscale[k, j]) * (ct["lerp0"] + (ct["lerp1"] - ct["lerp0"]) * af)
                self.hp[k, w] = max(0.0, float(self.hp[k, w]) - dmg)
                self.st["wolf_hp_lost"][k] += dmg
                self.knock_dir[k, w] = tu
                self.knock_left[k, w] = ct["knock_steps"]
                self.bite_cd[k, w] = ct["nobite"]
                self.hp[k, j] = max(0.0, float(self.hp[k, j]) - ct["self_damage"])
                out = BITE_COUNTER
                if self.hp[k, w] <= 0.0:
                    self._kill(k, w, CAUSE_COUNTER, self.uid[k, j])
            else:
                loss = float(np.clip(self._bite_base / float(L.mass_ratio(self.g_size[k, j], self.af[k, j])), self._bite_base, 1.0))
                self.hp[k, j] = max(0.0, float(self.hp[k, j]) - loss)
                self.bite_cd[k, w] = self._bite_cd
                if self.hp[k, j] <= 0.0:
                    self._kill(k, j, CAUSE_BITE, self.uid[k, w])
                    out = BITE_KILL
        self.st["bites"][k, spj, out] += 1
        if out == BITE_KILL:
            self._dec_kills.append((k, w, j, int(self.uid[k, w]), int(self._dead_uid[k, j])))
        if self.record:
            near_c = bool((self.carc_ok[k] & (np.sqrt(_len2(self.carc_pos[k] - self.pos[k, w])) <= 2.0)).any())
            self.events["bites"].append(dict(k=k, t=int(self.t[k]), wolf_uid=int(self.uid[k, w]),
                                             prey_uid=int(self.uid[k, j] if out != BITE_KILL else self._dead_uid[k, j]),
                                             prey_sp=spj, outcome=BITE_NAMES[out], dist=d, wolf_E=float(self.E[k, w]),
                                             wolf_hp=float(self.hp[k, w]), prey_af=float(self.af[k, j]),
                                             prey_hp=float(self.hp[k, j]), near_carcass=near_c,
                                             wolf_act=int(self.act[k, w]), quad=int(self.quad[k, j])))

    # --- 3 eat ----------------------------------------------------------
    def _eat(self) -> np.ndarray:
        """Order 3: grid foods by the R8 demand split (r8_world 745~757), meat from the nearest eatable carcass, 3 places nearest
        first. Returns gain_e (K, S); gains in food units are kept in self._gain_u (K, S, 3)."""
        K, S, G = self.K, self.S, self.G
        sb = self.sb
        alive = self.alive
        kind, mult = self._ekind, self._emult
        e_dr = self.E - self._drain
        gain_e = np.zeros((K, S))
        gain_u = np.zeros((K, S, B.N_FOODS))
        kk = np.arange(K)[:, None]
        GG = G * G
        ix, iy = _cells(self.pos, self.cell, G)
        flat = (kk * GG + iy * G + ix).reshape(-1)
        for f, name in ((B.GRASS, "grass"), (B.ROOT, "root")):
            m = alive & (kind == f)
            if not m.any():
                continue
            epu, rate = sb["e_per_unit"][..., f], sb["eat_rate"][..., f]
            want = np.zeros((K, S))
            want[m] = np.clip((1.0 - e_dr[m]) / epu[m], 0.0, rate[m]) * mult[m]
            demand = np.bincount(flat, weights=want.reshape(-1), minlength=K * GG)
            fflat = getattr(self, name).reshape(-1)
            taken = np.minimum(demand, fflat)
            frac = np.divide(taken, demand, out=np.zeros_like(taken), where=demand > 0)
            setattr(self, name, (fflat - taken).reshape(K, G, G))
            gu = want * frac[flat].reshape(K, S)
            gain_u[..., f] = gu
            gain_e = gain_e + np.where(m, gu * epu, 0.0)
        m = alive & (kind == B.MEAT)
        if m.any() and self.carc_ok.any():
            ki, si = np.nonzero(m)
            d = self.carc_pos[ki] - self.pos[ki, si][:, None, :]
            dd = np.sqrt(d[..., 0] * d[..., 0] + d[..., 1] * d[..., 1])
            ok = (self.carc_ok[ki] & (self.carc_meat[ki] > 0.0) & (self.carc_kin[ki] != self.kin_id[ki, si][:, None])
                  & (dd <= self._carc["eat_r"]))
            key = np.where(ok, dd, np.inf)
            cj = key.argmin(1)
            dc = key[np.arange(len(ki)), cj]
            has = dc < np.inf
            ki, si, cj, dc = ki[has], si[has], cj[has], dc[has]
            if len(ki):
                # places: per carcass the `places` nearest eaters (ties lower slot)
                order = np.lexsort((si, dc, cj, ki))
                grp = ki[order] * self.M + cj[order]
                start = np.r_[0, np.nonzero(np.diff(grp))[0] + 1]
                rank = np.arange(len(order)) - np.repeat(start, np.diff(np.r_[start, len(order)]))
                keep = np.zeros(len(order), dtype=bool)
                keep[order] = rank < self._carc["places"]
                ki, si, cj = ki[keep], si[keep], cj[keep]
                epu = sb["e_per_unit"][ki, si, B.MEAT]
                want = np.clip((1.0 - e_dr[ki, si]) / epu, 0.0, sb["eat_rate"][ki, si, B.MEAT]) * mult[ki, si]
                key2 = ki * self.M + cj
                demand = np.bincount(key2, weights=want, minlength=K * self.M)
                mflat = self.carc_meat.reshape(-1)
                taken = np.minimum(demand, mflat)
                frac = np.divide(taken, demand, out=np.zeros_like(taken), where=demand > 0)
                self.carc_meat = (mflat - taken).reshape(K, self.M)
                gu = want * frac[key2]
                gain_u[ki, si, B.MEAT] = gu
                gain_e[ki, si] = gain_e[ki, si] + gu * epu
                gone = self.carc_ok & (self.carc_meat <= 1e-12)
                if gone.any():
                    self.st["meat_decayed"] += np.where(gone, self.carc_meat, 0.0).sum(1)
                    self.carc_meat = np.where(gone, 0.0, self.carc_meat)
                    self.carc_ok &= ~gone
        ka, sa = np.nonzero(alive)
        if len(ka):
            sp = self.slot_sp[sa].astype(np.int64)
            for f in range(B.N_FOODS):
                np.add.at(self.st["eaten_units"], (ka, sp, f), gain_u[ka, sa, f])
                np.add.at(self.st["eaten_e"], (ka, sp, f), gain_u[ka, sa, f] * sb["e_per_unit"][ka, sa, f])
        self._gain_u = gain_u
        return gain_e

    # --- 4 metabolism ---------------------------------------------------
    def _metabolism(self, gain_e: np.ndarray) -> None:
        """Order 4: e_new = min(E − drain + gain, 1) → R8 `_reserve` (r8_world 796~816, per-slot C) → stamina → HP regen."""
        sb = self.sb
        m = self.alive
        e_dr = self.E - self._drain
        e_new = np.minimum(e_dr + gain_e, 1.0)
        C = sb["reserve_cap"]
        R = self.R
        out = e_new.copy()
        need = e_new < 0.0
        if need.any():
            want = -e_new / C
            cov = want <= R
            out = np.where(need, np.where(cov, 0.0, e_new + R * C), out)
            R = np.where(need, np.where(cov, R - want, 0.0), R)
        rf = sb["refill_frac"]
        fill = (out >= sb["refill_e"]) & (R < 1.0) & (gain_e > 0.0) & (rf > 0.0)
        if fill.any():
            mvf = np.where(fill, np.minimum(rf * gain_e, (1.0 - R) * C), 0.0)
            out = out - mvf
            R = np.where(fill, np.minimum(R + mvf / C, 1.0), R)
        self.E = np.where(m, out, self.E)
        self.R = np.where(m, R, self.R)
        run = self._gait == B.G_RUN
        st = np.where(run, np.maximum(self.stam - sb["stam_drain"], 0.0), np.minimum(self.stam + sb["stam_recover"], 1.0))
        self.stam = np.where(m, st, self.stam)
        # [어림] 1e-9 tolerance: 90 drains of 0.85/90 from 1.0 land on 0.15 up to rounding
        lk = np.where(self.stam <= self._lock + 1e-9, True, np.where(self.stam >= self._unlock - 1e-9, False, self.stam_lock))
        self.stam_lock = np.where(m, lk, self.stam_lock)
        reg = m & sb["has_hp"]
        self.hp = np.where(reg, np.minimum(self.hp + sb["hp_regen"], 1.0), self.hp)

    # --- 5 breed --------------------------------------------------------
    def _breed(self) -> L.BreedEvents:
        return L.breed_step(self, self.life, self.rules)

    def _install_newborn(self, nb: L.Newborn) -> None:
        """Judge-world child from r9_life.breed_step: lowest empty slot of its species (life chose it). Stamina 1, HP 1, velocity
        0, action WATCH; next_birth = born (Unreal child NextBirth = 0, eligibility waits for maturity) [해석]."""
        k, s = int(nb.k), int(nb.slot)
        if self.alive[k, s]:
            raise RuntimeError(f"newborn into a live slot: world {k} slot {s}")
        if int(self.slot_sp[s]) != int(nb.sp):
            raise RuntimeError(f"newborn species {nb.sp} into slot {s} of species {int(self.slot_sp[s])}")
        self._set_slot(k, s, uid=int(nb.uid), pos=np.asarray(nb.pos, dtype=np.float64), head=np.asarray(nb.head, dtype=np.float64),
                       E=float(nb.energy), R=float(nb.fat), born=float(nb.born), next_birth=float(nb.born), sex=int(nb.sex),
                       g_speed=float(nb.g_speed), g_size=float(nb.g_size), parent_a=int(nb.parent_a), parent_b=int(nb.parent_b),
                       generation=int(nb.generation))
        if self.record:
            self.events["births"].append(dict(k=k, t=int(self.t[k]), uid=int(nb.uid), sp=int(nb.sp), parent_a=int(nb.parent_a),
                                              parent_b=int(nb.parent_b), x=float(nb.pos[0]), y=float(nb.pos[1]),
                                              quad=int(self.quad[k, s])))

    # --- 6 deaths -------------------------------------------------------
    def _add_carcass(self, k: int, pos, meat: float, kin: int, sp: int, uid: int, killer: int) -> None:
        free = np.nonzero(~self.carc_ok[k])[0]
        if len(free):
            c = int(free[0])
        else:
            c = int(np.argmin(self.carc_meat[k]))            # [어림] table full: drop the carcass with the least meat
            self.st["meat_overflow"][k] += 1
            self.st["meat_overflow_lost"][k] += float(self.carc_meat[k, c])
        self.carc_ok[k, c] = True
        self.carc_pos[k, c] = pos
        self.carc_meat[k, c] = meat
        self.carc_meat0[k, c] = meat
        self.carc_t[k, c] = float(self.t[k])
        self.carc_kin[k, c] = kin
        self.carc_sp[k, c] = sp
        self.carc_uid[k, c] = uid
        self.carc_killer[k, c] = killer

    def _deaths(self) -> np.ndarray:
        """Order 6: starvation (E ≤ 0 and R ≤ 0) joins this step's bite/counter deaths; every death leaves a carcass with meat =
        mass_kg × mass_ratio × meat_frac / kg_per_unit (3-4). Judge-world slots are emptied (uid 0)."""
        starve = self.alive & (self.E <= 0.0) & (self.R <= 0.0)
        for k, s in zip(*np.nonzero(starve)):
            self._kill(int(k), int(s), CAUSE_STARVE, 0)
        dead = self._dead.copy()
        if not dead.any():
            return dead
        mr = L.mass_ratio(self.g_size, self.af)
        meat = self.sb["mass_kg"] * mr * self._carc["meat_frac"] / self._carc["kg"]
        band = float(self.cfg["world"]["wall_band"])
        for k, s in zip(*np.nonzero(dead)):
            k, s = int(k), int(s)
            sp = int(self.slot_sp[s])
            self._add_carcass(k, self.pos[k, s].copy(), float(meat[k, s]), int(self.kin_id[k, s]), sp, int(self._dead_uid[k, s]),
                              int(self.killer[k, s]))
            self.st["meat_created"][k, sp] += float(meat[k, s])
            self.st["deaths"][k, sp, int(self.dead_cause[k, s])] += 1
            p = self.pos[k, s]
            wall = bool(p[0] < band or p[0] > self.size - band or p[1] < band or p[1] > self.size - band)
            self.st["deaths_wall"][k, sp] += int(wall)
            if self.record:
                _, e = _shelter_edge(self.pos[k:k + 1, s:s + 1], self.cov_c[k:k + 1], self.cov_r[k:k + 1], self.cov_ok[k:k + 1])
                self.events["deaths"].append(dict(k=k, t=int(self.t[k]), uid=int(self._dead_uid[k, s]), sp=sp,
                                                  cause=CAUSE_NAMES[int(self.dead_cause[k, s])], killer=int(self.killer[k, s]),
                                                  x=float(p[0]), y=float(p[1]), age=float(self.t[k] - self.born[k, s]),
                                                  af=float(self.af[k, s]), since_spawn=float(self.t[k] - self.resp_t[k, s]),
                                                  quad=int(self.quad[k, s]), wall=wall, shelter_edge=float(e[0, 0]),
                                                  E=float(self.E[k, s]), R=float(self.R[k, s]), hp=float(self.hp[k, s]),
                                                  meat=float(meat[k, s])))
            if self.judge:
                self.uid[k, s] = 0
                self.mating[k, s] = False
                self.vel[k, s] = 0.0
                self.disp[k, s] = 0.0
                self.knock_left[k, s] = 0
        return dead

    # --- 7 regrow -------------------------------------------------------
    def _regrow(self) -> None:
        g0, r0 = self.grass, self.root
        self.grass = self.grass + self.grass_regen * (self.grass_cap - self.grass)      # r8_world 773
        self.root = self.root + self.root_regen * (self.root_cap - self.root)
        K = self.K
        self.st["grid_regen"][:, 0] += seq_sum((self.grass - g0).reshape(K, -1), -1)
        self.st["grid_regen"][:, 1] += seq_sum((self.root - r0).reshape(K, -1), -1)
        if self.carc_ok.any():
            dec = np.where(self.carc_ok, np.minimum(self.carc_meat0 / self._carc["decay"], self.carc_meat), 0.0)
            self.carc_meat = self.carc_meat - dec
            gone = self.carc_ok & (self.carc_meat <= 1e-12)
            self.st["meat_decayed"] += dec.sum(1) + np.where(gone, self.carc_meat, 0.0).sum(1)
            self.carc_meat = np.where(gone, 0.0, self.carc_meat)
            self.carc_ok &= ~gone

    # --- 8 respawn (train) ----------------------------------------------
    def _respawn(self, dead: np.ndarray) -> np.ndarray:
        """Order 8 (3-6 학습 세계 '죽은 뒤'). Per event the RESP stream always draws: form u, adult pick u, `candidates` × 2
        positions, head index, fat. 20% newborn form (age 0, E 0.4, fat 0) on the golden ring 1.1 + 0.2 j around a random alive
        mature same-species individual (clear of everyone by breed.clear_r, inside the stage, non-entering bodies outside
        shelters); no adult or no free ring spot → the far form [해석]. Far form: first candidate outside shelters and ≥ far_r from
        every alive other-species individual, else the farthest outside-shelter candidate (R8); start age/fat/E distribution."""
        K, S = self.K, self.S
        resp = np.zeros((K, S), dtype=bool)
        if not dead.any():
            return resp
        cfg, body = self.cfg, self.body
        rz, rs = cfg["randomize"], cfg["respawn"]
        nc, far, nbf = int(rs["candidates"]), float(rs["far_r"]), float(rs["newborn_frac"])
        br = body.common["breed"]
        clear_r = float(br["clear_r"])
        self._resp_form = np.zeros((K, S), dtype=np.int8)
        for k in np.nonzero(dead.any(1))[0]:
            k = int(k)
            g = self.rng_resp[k]
            sw, sq = int(self.s_w[k]), int(self.s_q[k, 0])
            for s in np.nonzero(dead[k])[0]:
                s = int(s)
                sp = int(self.slot_sp[s])
                u_form = float(g.random())
                u_pick = float(g.random())
                cand = g.uniform(0.0, self.size, (nc, 2))
                hidx = int(g.integers(0, 8))
                fat_u = float(g.uniform(*rz["fat_init"]))
                uid = int(self.next_uid[k])
                self.next_uid[k] += 1
                enter = bool(body.shelter_enter[sp])
                pos, form = None, RESP_FAR
                if u_form < nbf:
                    lo, hi = int(self.sp_lo[sp]), int(self.sp_hi[sp])
                    adults = np.nonzero(self.alive[k, lo:hi] & self.mature[k, lo:hi])[0] + lo
                    if len(adults):
                        a = int(adults[min(int(u_pick * len(adults)), len(adults) - 1)])
                        others = self.pos[k][self.alive[k]]
                        for jj in range(8):
                            q = self.pos[k, a] + (RESP_RING_R0 + RESP_RING_DR * jj) * B.GOLDEN8[jj]
                            if not (0.0 <= q[0] <= self.size and 0.0 <= q[1] <= self.size):
                                continue
                            if not enter and not self._outside_shelters(k, q, 0.0):
                                continue
                            dd = others - q
                            if len(others) and (np.sqrt(dd[:, 0] * dd[:, 0] + dd[:, 1] * dd[:, 1]) < clear_r).any():
                                continue
                            pos, form = q, RESP_NEWBORN
                            break
                if pos is None:
                    margin = 0.0 if enter else self._push
                    out = self._outside_shelters(k, cand, margin)
                    om = self.alive[k] & (self.slot_sp != sp)
                    op = self.pos[k][om]
                    if len(op):
                        dx = cand[:, None, 0] - op[None, :, 0]
                        dy = cand[:, None, 1] - op[None, :, 1]
                        dmin = np.sqrt(dx * dx + dy * dy).min(1)
                    else:
                        dmin = np.full(nc, 1e9)
                    okc = out & (dmin >= far)
                    pick = int(np.argmax(okc)) if okc.any() else int(np.argmax(np.where(out, dmin, dmin - 1e6)))
                    pos = cand[pick].copy()
                gsp, gsz = L.founder_genome(body, sp, sw, sq, uid)
                sex = L.respawn_sex(body, sp, sw, sq, uid)
                t = float(self.t[k])
                if form == RESP_NEWBORN:
                    born, e0, r0, nbt = t, float(br["child_e"]), float(br["child_fat"]), t
                else:
                    age = L.respawn_age(float(body.maturity[sp]), float(self.juv_frac[k, sp]), float(body.max_founder_age[sp]),
                                        L.age_seed(sq, sp), uid)
                    born, e0, r0 = t - age, float(rz["start_energy"]), fat_u
                    nbt = L.first_birth_time(body, sp, t, sq, uid)
                self._set_slot(k, s, uid=uid, pos=pos, head=B.DIR8[hidx], E=e0, R=r0, born=born, next_birth=nbt, sex=sex,
                               g_speed=gsp, g_size=gsz)
                L.on_slot_reset(self.life, k, [s], self)
                resp[k, s] = True
                self._resp_form[k, s] = form
                self.st["respawns"][k, sp, form] += 1
                if self.record:
                    self.events["respawns"].append(dict(k=k, t=int(self.t[k]), uid=uid, sp=sp, form=int(form),
                                                        x=float(pos[0]), y=float(pos[1])))
        return resp

    # --- 9 perceive -----------------------------------------------------
    def _eye(self, n: int) -> np.ndarray:
        e = getattr(self, "_eye_cache", None)
        if e is None or e.shape[0] != n:
            e = np.eye(n, dtype=bool)
            self._eye_cache = e
        return e

    def _gather_alive(self) -> tuple[np.ndarray, np.ndarray]:
        """(idx (K, Mx) slot numbers in slot order (−1 pad), valid (K, Mx)). pairs_full: idx = all slots, valid = alive."""
        if self.pairs_full:
            return np.broadcast_to(np.arange(self.S, dtype=np.int64), (self.K, self.S)).copy(), self.alive.copy()
        idx, n = self.alive_index()
        return idx, idx >= 0

    def _perceive(self, update_mem: bool) -> None:
        """Order 9 (4-1): eye (see_r × head_down when the decision action is EAT, fov) ∪ ear (hear_radius of the maker's |disp|)
        ∪ nose (smell_r) between gathered alive individuals; approach memory m ← 0.8 m + 0.2 a when perceived, else 0.9 m (alive
        pairs only). Carcasses: eye ∪ nose, other kin, meat > 0. Reads per-slot body arrays and kin_id — no species number."""
        K = self.K
        sb = self.sb
        idx, valid = self._gather_alive()
        ic = np.where(valid, idx, 0)
        Mx = ic.shape[1]
        kk = np.arange(K)[:, None]
        P, H, Dp = self.pos[kk, ic], self.head[kk, ic], self.disp[kk, ic]
        hd = np.where(self.act[kk, ic] == B.EAT, sb["head_down"][kk, ic], 1.0)
        see = sb["see_r"][kk, ic] * hd
        fov = sb["fov_cos"][kk, ic]
        smr = sb["smell_r"][kk, ic]
        kin = self.kin_id[kk, ic]
        Px, Py = P[..., 0], P[..., 1]
        dx = Px[:, None, :] - Px[:, :, None]                         # [k, i, j] = P_j − P_i
        dy = Py[:, None, :] - Py[:, :, None]
        # in-place ufuncs below compute exactly sqrt(dx·dx + dy·dy), 1 / max(dist, EPS), (dx·hx + dy·hy)·invd and
        # clip(−(Dx·dx + Dy·dy)·invd / 0.9, −1, 1) — the same operations in the same order as the plain expressions
        tmp = np.empty_like(dx)
        dist = np.multiply(dx, dx)
        np.multiply(dy, dy, out=tmp)
        np.add(dist, tmp, out=dist)
        np.sqrt(dist, out=dist)
        invd = np.maximum(dist, EPS)
        np.divide(1.0, invd, out=invd)
        cosang = np.multiply(dx, H[:, :, None, 0])
        np.multiply(dy, H[:, :, None, 1], out=tmp)
        np.add(cosang, tmp, out=cosang)
        np.multiply(cosang, invd, out=cosang)
        pair = valid[:, :, None] & valid[:, None, :]
        pair &= ~self._eye(Mx)[None]
        vis = np.less_equal(dist, see[:, :, None])
        vis &= np.greater_equal(cosang, fov[:, :, None])
        vis &= pair
        spd = np.sqrt(_len2(Dp))
        heard = np.less_equal(dist, B.hear_radius(spd)[:, None, :])
        heard &= pair
        smell = np.less_equal(dist, smr[:, :, None])
        smell &= pair
        perc = vis | heard
        perc |= smell
        appr = np.multiply(Dp[:, None, :, 0], dx)
        np.multiply(Dp[:, None, :, 1], dy, out=tmp)
        np.add(appr, tmp, out=appr)
        np.negative(appr, out=appr)
        np.multiply(appr, invd, out=appr)
        np.divide(appr, B.OBS_NORM["vel"], out=appr)
        np.clip(appr, -1.0, 1.0, out=appr)
        del tmp, cosang
        same = kin[:, :, None] == kin[:, None, :]
        if update_mem:
            keep, gain, decay = B.SENSE["mem_keep"], B.SENSE["mem_gain"], B.SENSE["mem_decay"]
            if self.pairs_full:
                m = np.where(perc, keep * self.mem + gain * appr, decay * self.mem)
                self.mem = np.where(valid[:, :, None] & valid[:, None, :], m, self.mem)
            else:
                n = valid.sum(1)
                for k in range(K):
                    nk = int(n[k])
                    if not nk:
                        continue
                    ix_ = np.ix_(idx[k, :nk], idx[k, :nk])
                    blk = self.mem[k][ix_]
                    self.mem[k][ix_] = np.where(perc[k, :nk, :nk], keep * blk + gain * appr[k, :nk, :nk], decay * blk)
        # carcasses (gathered ok slots in carcass order)
        if self.pairs_full:
            cidx = np.broadcast_to(np.arange(self.M, dtype=np.int64), (K, self.M)).copy()
            cvalid = self.carc_ok.copy()
        else:
            nc = self.carc_ok.sum(1)
            Mc = max(int(nc.max()) if K else 0, 1)
            corder = np.argsort(~self.carc_ok, axis=1, kind="stable")[:, :Mc]
            cvalid = np.arange(Mc)[None, :] < nc[:, None]
            cidx = np.where(cvalid, corder, -1)
        cic = np.where(cvalid, cidx, 0)
        CP = self.carc_pos[kk, cic]
        cmeat = np.where(cvalid, self.carc_meat[kk, cic], 0.0)
        ckin = self.carc_kin[kk, cic]
        cdx = CP[:, None, :, 0] - Px[:, :, None]
        cdy = CP[:, None, :, 1] - Py[:, :, None]
        cdist = np.sqrt(cdx * cdx + cdy * cdy)
        ccos = (cdx * H[:, :, None, 0] + cdy * H[:, :, None, 1]) / np.maximum(cdist, EPS)
        cpair = valid[:, :, None] & cvalid[:, None, :]
        cother = cpair & (ckin[:, None, :] != kin[:, :, None])
        csens = (((cdist <= see[:, :, None]) & (ccos >= fov[:, :, None])) | (cdist <= smr[:, :, None])) & cother \
            & (cmeat[:, None, :] > 0.0)
        self._pc = dict(idx=idx, ic=ic, valid=valid, P=P, H=H, Dp=Dp, dx=dx, dy=dy, dist=dist, invd=invd, pair=pair, vis=vis,
                        heard=heard, smell=smell, perc=perc, appr=appr, same=same, kin=kin,
                        cidx=cidx, cic=cic, cvalid=cvalid, cmeat=cmeat, cdx=cdx, cdy=cdy, cdist=cdist, cother=cother, csens=csens)

    def _observe(self) -> np.ndarray:
        """Observation from ObsInputs (no species number) → build_obs. Stores the hidden slot maps."""
        self._derive()
        inp = ObsInputs(t=self.t, pc=self._pc, pos=self.pos, head=self.head, disp=self.disp, alive=self.alive, kin_id=self.kin_id,
                        sb=self.sb, E=self.E, R=self.R, stam=self.stam, hp=self.hp, size_obs=self.size_obs, af=self.af,
                        next_birth=self.next_birth, mating=self.mating, sex=self.sex, mature=self.mature, uid=self.uid,
                        parent_a=self.parent_a, parent_b=self.parent_b, check_related=self.judge, size=self.size, cell=self.cell,
                        grass=self.grass, root=self.root, cov_c=self.cov_c, cov_r=self.cov_r, cov_ok=self.cov_ok, mem=self.mem)
        obs, oth, kin = build_obs(inp)
        self._other_slots, self._kin_slots = oth, kin
        return obs

    # ------------------------------------------------------------------ #
    # hidden hunt records (8-2 다가감 구간 raw data, record mode)
    # ------------------------------------------------------------------ #

    def _hunt_reset_world(self, k: int) -> None:
        self._h_prev[k] = np.inf
        self._h_on[k] = False
        self._h_close[k] = 0
        self._h_gap[k] = 0
        self._h_ran[k] = False
        self._h_tuid[k] = 0
        self._h_puid[k] = 0
        self._h_wuid[k] = self.uid[k, self._biters] if len(self._biters) else 0

    def _hunt_emit(self, k: int, wi: int, s: int, reason: str) -> None:
        n = int(self._h_close[k, wi, s])
        if n > HUNT_MIN_DECISIONS or reason == "kill":
            self.events["hunts"].append(dict(k=k, wolf_uid=int(self._h_wuid[k, wi]), target_uid=int(self._h_tuid[k, wi, s]),
                                             target_sp=int(self.slot_sp[s]), t0=int(self._h_t0[k, wi, s]), t1=int(self.t[k]),
                                             n_close=n, ran=bool(self._h_ran[k, wi, s]), end=reason))
        self._h_on[k, wi, s] = False
        self._h_close[k, wi, s] = 0
        self._h_gap[k, wi, s] = 0
        self._h_ran[k, wi, s] = False

    def _hunt_flush_world(self, k: int, reason: str) -> None:
        if not self.record or not len(self._biters):
            return
        for wi, s in zip(*np.nonzero(self._h_on[k])):
            self._hunt_emit(k, int(wi), int(s), reason)

    def flush_hunts(self) -> None:
        """Close every open hunt segment (reason 'open') — call at the end of an evaluation run."""
        for k in range(self.K):
            self._hunt_flush_world(k, "open")

    def _track_hunts(self) -> None:
        """Decision-level state machine per (wolf, target) pair: closing = perceived and distance shrank faster than
        HUNT_CLOSE_SPEED per step since the previous decision. A segment starts at the first closing decision, ends after
        HUNT_GAP_END non-closing decisions, a kill by this wolf, or either individual leaving; segments with more than
        HUNT_MIN_DECISIONS closing decisions (or ended by a kill) are recorded. Kill attribution rules live in the eval (8-2).
        The previous-decision distance is kept with the target uid it was measured to (_h_puid): a slot whose individual changed
        (train respawn inside the decision, judge newborn) has no previous distance (Fix 단계 검토 low — before, the old
        individual's distance was compared with the new one's and could start a segment without any approach).
        Sparse form: only eligible pairs (alive wolf × perceived alive other-species slot) and open segments are touched; the
        state arrays stay (K, nb, S). Bit-identical to `_track_hunts_full` (pairs_full reference path, test 22b)."""
        if self.pairs_full:
            self._track_hunts_full()
            return
        bs = self._biters
        if not len(bs):
            return
        K, S = self.K, self.S
        pc = self._pc
        ic, valid = pc["ic"], pc["valid"]
        inv = np.full((K, S), -1, dtype=np.int64)
        ki, ii = np.nonzero(valid)
        inv[ki, ic[ki, ii]] = ii
        wi_g = inv[:, bs]                                             # (K, nb) gathered row of each biter slot (−1 none)
        # wolf changed (respawn) → drop its row
        wu = self.uid[:, bs]
        for k, wi in zip(*np.nonzero(wu != self._h_wuid)):
            for s in np.nonzero(self._h_on[k, wi])[0]:
                self._hunt_emit(int(k), int(wi), int(s), "wolf_gone")
            self._h_prev[k, wi] = np.inf
            self._h_wuid[k, wi] = wu[k, wi]
        # kills this decision
        for (k, w, j, wuid, puid) in self._dec_kills:          # kill events themselves are in events['bites']
            wi = int(np.nonzero(bs == w)[0][0])
            if self._h_on[k, wi, j] and self._h_tuid[k, wi, j] == puid:
                self._hunt_emit(k, wi, j, "kill")
        ok_, ow_, os_ = np.nonzero(self._h_on)
        gone = (self.uid[ok_, os_] != self._h_tuid[ok_, ow_, os_]) | ~self.alive[ok_, os_]
        for k, wi, s in zip(ok_[gone], ow_[gone], os_[gone]):
            self._hunt_emit(int(k), int(wi), int(s), "target_gone")
        # eligible pairs: alive wolf rows × perceived gathered columns, other species it can bite, alive
        rk, rw = np.nonzero((wi_g >= 0) & self.alive[:, bs])
        rows = pc["perc"][rk, wi_g[rk, rw]] & valid[rk]                 # (n, Mx)
        r_, g_ = np.nonzero(rows)
        pk, pw = rk[r_], rw[r_]
        ps = ic[pk, g_]
        el = self._bite_mat[pw, ps] & self.alive[pk, ps]
        pk, pw, ps = pk[el], pw[el], ps[el]
        wsl = bs[pw]
        dist = np.sqrt(_len2(self.pos[pk, ps] - self.pos[pk, wsl]))
        tu = self.uid[pk, ps]
        prev = np.where(self._h_puid[pk, pw, ps] == tu, self._h_prev[pk, pw, ps], np.inf)
        closing = np.isfinite(prev) & ((prev - dist) / float(self.D) > HUNT_CLOSE_SPEED)
        a_w = self.act[pk, wsl]
        run = (a_w >= B.RUN_FIRST) & (a_w <= B.RUN_LAST)
        start = closing & ~self._h_on[pk, pw, ps]
        sk, sw, ss = pk[start], pw[start], ps[start]
        self._h_t0[sk, sw, ss] = self.t[sk] - self.D
        self._h_tuid[sk, sw, ss] = tu[start]
        self._h_on[sk, sw, ss] = True
        ck, cw, cs = pk[closing], pw[closing], ps[closing]
        self._h_close[ck, cw, cs] += 1
        # gap: open and not closing → +1, closing → 0 (pairs that are not open keep gap 0 — _hunt_emit / reset zero it)
        self._h_gap[self._h_on] += 1
        self._h_gap[ck, cw, cs] = 0
        rr = closing & run
        self._h_ran[pk[rr], pw[rr], ps[rr]] = True
        for k, wi, s in zip(*np.nonzero(self._h_on & (self._h_gap >= HUNT_GAP_END))):
            self._hunt_emit(int(k), int(wi), int(s), "gap")
        self._h_prev.fill(np.inf)
        self._h_prev[pk, pw, ps] = dist
        self._h_puid[pk, pw, ps] = tu

    def _track_hunts_full(self) -> None:
        """Reference path of `_track_hunts` over the full (K, nb, S) table (pairs_full=True, test 22b)."""
        bs = self._biters
        if not len(bs):
            return
        K, S = self.K, self.S
        pc = self._pc
        ic, valid = pc["ic"], pc["valid"]
        inv = np.full((K, S), -1, dtype=np.int64)
        ki, ii = np.nonzero(valid)
        inv[ki, ic[ki, ii]] = ii
        wi_g = inv[:, bs]                                             # (K, nb)
        perc_ws = np.zeros((K, len(bs), S), dtype=bool)
        for k in range(K):
            ok = wi_g[k] >= 0
            if not ok.any():
                continue
            rows = pc["perc"][k, wi_g[k, ok]]                         # (n_ok, Mx)
            cols = ic[k, valid[k]]
            sub = np.zeros((int(ok.sum()), S), dtype=bool)
            sub[:, cols] = rows[:, valid[k]]
            perc_ws[k, ok] = sub
        d = self.pos[:, None, :, :] - self.pos[:, bs][:, :, None, :]
        dist = np.sqrt(_len2(d))
        elig = perc_ws & self._bite_mat[None] & self.alive[:, None, :] & self.alive[:, bs][..., None]
        # wolf changed (respawn) → drop its row; target uid changed → drop the pair
        wu = self.uid[:, bs]
        for k, wi in zip(*np.nonzero(wu != self._h_wuid)):
            for s in np.nonzero(self._h_on[k, wi])[0]:
                self._hunt_emit(int(k), int(wi), int(s), "wolf_gone")
            self._h_prev[k, wi] = np.inf
            self._h_wuid[k, wi] = wu[k, wi]
        # kills this decision
        for (k, w, j, wuid, puid) in self._dec_kills:          # kill events themselves are in events['bites']
            wi = int(np.nonzero(bs == w)[0][0])
            if self._h_on[k, wi, j] and self._h_tuid[k, wi, j] == puid:
                self._hunt_emit(k, wi, j, "kill")
        tu = np.broadcast_to(self.uid[:, None, :], elig.shape)
        gone = self._h_on & ((tu != self._h_tuid) | ~self.alive[:, None, :])
        for k, wi, s in zip(*np.nonzero(gone)):
            self._hunt_emit(int(k), int(wi), int(s), "target_gone")
        prev = np.where(self._h_puid == tu, self._h_prev, np.inf)
        closing = elig & np.isfinite(prev) & ((prev - dist) / float(self.D) > HUNT_CLOSE_SPEED)
        run = ((self.act[:, bs] >= B.RUN_FIRST) & (self.act[:, bs] <= B.RUN_LAST))[..., None]
        start = closing & ~self._h_on
        self._h_t0 = np.where(start, (self.t - self.D)[:, None, None], self._h_t0)
        self._h_tuid = np.where(start, tu, self._h_tuid)
        self._h_on |= start
        self._h_close = np.where(closing, self._h_close + 1, self._h_close)
        self._h_gap = np.where(closing, 0, np.where(self._h_on, self._h_gap + 1, 0))
        self._h_ran |= closing & run
        for k, wi, s in zip(*np.nonzero(self._h_on & (self._h_gap >= HUNT_GAP_END))):
            self._hunt_emit(int(k), int(wi), int(s), "gap")
        self._h_prev = np.where(elig, dist, np.inf)
        self._h_puid = np.where(elig, tu, self._h_puid)
