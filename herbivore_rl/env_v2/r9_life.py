"""R9 life history — Unreal life rules ported to Python (design RL_R9_MULTISPECIES_DESIGN.md 3-6, 3-7, 10절; Unreal sources are
read only: AI/Policy/EcoLifeHistoryV3.h (LH), Creature/Runtime/EcoCreatureNaturalBirth.cpp (NB), EcoCreatureSpawning.cpp (SP),
EcoFauna.cpp (FAc), Ecology/EcologySimulationSubsystem.cpp (ESS)).

Owner: life agent. Tests: tests/test_r9_life.py (12절 13·14·15) + tests/cpp/life_golden_r9_main.cpp (engine-free golden, test 14:
Mix/Unit, FounderAge, Rank, Sex, Founder/NaturalFounder, Inherit, growth and CanParent are bit-equal to the compiled LH header).

Pure-function style: functions take the world object `w` (attributes in LIFE_READS, names from the r9_world state table) plus a
`LifeState` (life-owned pending pairs and counters) and a `LifeRules` (config). They never read RNG streams — life randomness is
the uint64 hash `Mix`/`Unit` (3-9). The only world arrays they write are LIFE_WRITES. Newborn bodies are *returned* (`Newborn`)
and installed by the world (`R9World._install_newborn`), because slot body arrays, kin_id, memory rows and perception are world-owned.

Time is in steps (float64 where Unreal uses seconds: 15 s = 112.5 steps). Hash inputs are uint64 (Python int masked to 64 bits).

Breeding per step (order 5 of 3-9, `breed_step`)
  1 pending pairs  vectorised over (K, P): slot/uid guard, both alive (no death this step), both still in the pair quadrant,
                   deer·wolf also E·HP eligibility (pending_needs_parent; the action is NOT checked — 3-7 '언리얼과 다르게'),
                   boar only alive·quadrant. Due (t ≥ due): deer·wolf deliver at once if both within birth_r (15), else no birth
                   and retry after 225 steps (NB 54~58). Boar waits up to birth_grace (150) steps for 'eligible incl. not running and
                   within 7.5', then cancels (FAc 501~514). Every delivery attempt first sets next_birth = t + retry (NB 54, FAc 518).
  2 delivery       train: cost −0.2 E both, next_birth t + 2250, offspring + 1, reward credit (no body). Judge, in Unreal order:
                   [boar cap] → child spot (8 golden-ring spots) → budget (wolf budget | plant budget) → slot cap → Newborn.
  3 scan           when ⌊2t/75⌋ changes: candidates = eligible, not pairing-blocked by the decision action (deer RUN·SHELTER, boar
                   RUN, wolf none), not already pending, in quadrant q; uid order; compatible = sex rule, not related, within mate_r.
                   Judge (limits on): one pending per quadrant × species, the first compatible pair (NB 112~133). Train and judge L0
                   (one pending off): every compatible pair, greedy in uid order (3-6 '모두').
Counters (judge 8-2 출생 막힘; also kept in the train world): an opportunity = a scan of one quadrant × species with at least one
compatible pair (one per pair made in 'all pairs' mode) or one delivery deferred by a budget/cap. opportunities = paired + Σ blocked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .r9_body import (BOAR, CHILD_AT_MIDPOINT, DEER, FOUNDER_NATURAL, GOLDEN8, GRASS, N_ACTIONS, N_SPECIES, SEX_FEMALE, SEX_MALE,
                      SEX_NONE, SEXMODE_ALTERNATE, SEXMODE_NATURAL, WOLF, Body, quadrant_of)

M64 = 0xFFFF_FFFF_FFFF_FFFF
_INV53 = 1.0 / 9007199254740992.0            # LH Unit: double(Mix(V) >> 11) * (1 / 2^53)

# World attributes the life functions read / write (names = R9World state table, impl_contract.md §2). `dead_cause` is read with
# a default (CAUSE_NONE everywhere) so a minimal fake world works.
LIFE_READS = ("K", "S", "Q", "mode", "t", "size", "alive", "dead_cause", "uid", "sp_lo", "sp_hi", "pos", "quad", "E", "hp", "born",
              "next_birth", "sex", "g_speed", "g_size", "parent_a", "parent_b", "offspring", "generation", "act", "mating",
              "cov_c", "cov_r", "cov_ok", "grass", "cell_quad", "s_w", "s_q", "next_uid")
LIFE_WRITES = ("E", "next_birth", "offspring", "mating", "next_uid")
CAUSE_NONE = 0                                # = r9_world.CAUSE_NONE (no import: r9_world imports this module)

# Reasons a mating opportunity / due birth was blocked (judge world, 8-2 출생 막힘). FOOD is ecology, the rest are content caps.
BLOCK_WOLF_BUDGET, BLOCK_BOAR_CAP, BLOCK_ONE_PENDING, BLOCK_SLOT_CAP, BLOCK_FOOD = range(5)
BLOCK_NAMES = ("wolf_budget", "boar_cap", "one_pending", "slot_cap", "food_budget")
N_BLOCK = len(BLOCK_NAMES)
CONTENT_BLOCKS = (BLOCK_WOLF_BUDGET, BLOCK_BOAR_CAP, BLOCK_ONE_PENDING, BLOCK_SLOT_CAP)


# --------------------------------------------------------------------------- #
# hash (LH 16~17) — golden-checked (test 14)
# --------------------------------------------------------------------------- #

def mix(v: int) -> int:
    """EcoLifeV3::Mix (SplitMix64 finaliser) on a uint64 (Python int, wrapped to 64 bits)."""
    v = ((int(v) & M64) + 0x9E3779B97F4A7C15) & M64
    v = ((v ^ (v >> 30)) * 0xBF58476D1CE4E5B9) & M64
    v = ((v ^ (v >> 27)) * 0x94D049BB133111EB) & M64
    return v ^ (v >> 31)


def unit(v: int) -> float:
    """EcoLifeV3::Unit: top 53 bits of Mix(v) in [0, 1)."""
    return (mix(v) >> 11) * _INV53


def mix_np(v) -> np.ndarray:
    """Vectorised Mix on uint64 arrays (numpy uint64 arithmetic wraps mod 2^64)."""
    x = np.asarray(v).astype(np.uint64, copy=True)
    with np.errstate(over="ignore"):
        x = x + np.uint64(0x9E3779B97F4A7C15)
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return x ^ (x >> np.uint64(31))


def unit_np(v) -> np.ndarray:
    return (mix_np(v) >> np.uint64(11)).astype(np.float64) * _INV53


def life_seeds(world_seed: int) -> tuple[int, tuple[int, int, int, int]]:
    """(S_w, S_q[0..3]) for a world seed (10절: 'seed from world seed and quadrant number, Unreal Mix').
    DECISION (open issue, impl_contract.md 11절 #23): S_w = Mix(seed) plays Unreal's Native Settings.Seed (wolf/boar founders,
    deer child sex); S_q = Mix(S_w + q + 1) plays the region seed LayoutSeed ^ Crc(Region) (deer founders, first-birth time,
    ages). The training world is one region (q = 0)."""
    s_w = mix(int(world_seed) & M64)
    return s_w, tuple(mix((s_w + q + 1) & M64) for q in range(4))


# --------------------------------------------------------------------------- #
# genome, age, sex, growth (LH 25~62, 187~206; SP 169~182) — golden-checked (test 14)
# --------------------------------------------------------------------------- #

def founder(seed: int, uid: int) -> tuple[float, float]:
    """EcoLifeV3::Founder → (speed, size) in 0.95..1.05 (LH 49~50)."""
    s = int(seed) & M64
    u = int(uid) & M64
    return 0.95 + 0.1 * unit(s ^ u), 0.95 + 0.1 * unit((s + u + 17) & M64)


def natural_founder(seed: int, uid: int, variation: float) -> tuple[float, float]:
    """EcoLifeV3::NaturalFounder → (speed, size) = 1 ± variation (LH 51~56; Caution·Sociability·Coat are not used by R9)."""
    v = min(max(float(variation), 0.0), 0.1)
    s = int(seed) & M64
    u = int(uid) & M64
    return 1 + 2 * v * (unit(s ^ u) - 0.5), 1 + 2 * v * (unit((s + u + 17) & M64) - 0.5)


def inherit(a_speed: float, a_size: float, b_speed: float, b_size: float, seed: int) -> tuple[float, float]:
    """EcoLifeV3::Inherit (speed, size) (LH 57~62): parents' mean ± 0.02, clamped to 0.9..1.1."""
    s = int(seed) & M64
    sp = min(max((a_speed + b_speed) * 0.5 + (unit(s) - 0.5) * 0.04, 0.9), 1.1)
    sz = min(max((a_size + b_size) * 0.5 + (unit((s + 31) & M64) - 0.5) * 0.04, 0.9), 1.1)
    return sp, sz


def inherit_seed(body: Body, sp: int, uid_a: int, uid_b: int, offspring_a: int) -> int:
    """Child genome seed. Native deer·wolf NB 73: uid_A ^ Mix(uid_B) ^ offspring_A; Fauna boar FAc 557: uid_A ^ Mix(uid_B) ^
    Mix(offspring_A). offspring_A is the count before this birth. The Fauna form is chosen by the Fauna sex rule (sex_mode
    alternate) — the body table has no separate 'Unreal backend' field."""
    a, b, o = int(uid_a) & M64, int(uid_b) & M64, int(offspring_a) & M64
    if int(body.sex_mode[sp]) == SEXMODE_ALTERNATE:
        return a ^ mix(b) ^ mix(o)
    return a ^ mix(b) ^ o


def founder_genome(body: Body, sp: int, s_w: int, s_q: int, uid: int) -> tuple[float, float]:
    """Founder / respawn genome: deer NaturalFounder(S_q, uid, 0.08), wolf·boar Founder(S_w, uid) (3-3, SP 165·174, FAc 327).
    [R9 결정 — 언리얼과 다름] The Founder FUNCTION is Unreal's, the boar SEED is not: Unreal Fauna seeds boar founders with
    101 ^ console Seed ^ default Seed (EcoFauna.cpp 294~295, usually a fixed 101-derived value), wolves with the Native
    Settings.Seed (EcoCreatureSpawning.cpp 167). R9 uses S_w for both so the genome follows the world seed. Python results are
    unaffected; a later C++ parity check (14절 #12) must seed R9 boar with S_w, not the Fauna FounderSeed (Fix 단계 검토 low)."""
    if int(body.founder_kind[sp]) == FOUNDER_NATURAL:
        return natural_founder(s_q, uid, float(body.founder_variation[sp]))
    return founder(s_w, uid)


def founder_rank(index: int, count: int, seed: int) -> int:
    """Unreal age ordinal (SP 177~178): stride = first integer ≥ 31 coprime with count, rank = (i × stride + Mix(seed) % count) % count."""
    n = int(count)
    if n <= 0:
        raise ValueError("count must be ≥ 1")
    stride = 31
    while math.gcd(stride, n) != 1:
        stride += 1
    return (int(index) * stride + int(mix(seed) % n)) % n


def founder_age(maturity: float, juvenile_frac: float, max_age: float, seed: int, ordinal: int, count: int) -> float:
    """FPopulationProfile::FounderAge (LH 27~34): stratified juvenile cohort then adults up to max_age. Units of the arguments
    (Unreal seconds, R9 steps)."""
    young = int(math.floor(max(0, int(count)) * float(juvenile_frac)))
    u = unit((int(seed) + int(ordinal) * 31) & M64)
    if ordinal < young:
        return maturity * (0.18 + 0.72 * (ordinal + u) / max(1, young))
    return maturity + (max_age - maturity) * u


def natural_sex(seed: int, uid: int, female_frac: float) -> int:
    """FPopulationProfile::Sex (LH 35~36): Unit(seed ^ Mix(uid + 911)) < female_frac → female."""
    return SEX_FEMALE if unit((int(seed) & M64) ^ mix((int(uid) + 911) & M64)) < float(female_frac) else SEX_MALE


def founder_sex(body: Body, sp: int, s_w: int, s_q: int, uid: int, index: int) -> int:
    """Founder sex: deer natural(S_q), boar alternate by spawn index within the species (FAc 333: even → female), wolf none."""
    mode = int(body.sex_mode[sp])
    if mode == SEXMODE_NATURAL:
        return natural_sex(s_q, uid, float(body.female_frac[sp]))
    if mode == SEXMODE_ALTERNATE:
        return SEX_MALE if int(index) % 2 else SEX_FEMALE
    # [언리얼 값 그대로 — 근거 약함 (3-7 표 #3: 늑대 성별 없음, 아무 둘이나 번식)]
    return SEX_NONE


def respawn_sex(body: Body, sp: int, s_w: int, s_q: int, uid: int) -> int:
    """Training-world respawn sex. DECISION: deer natural(S_q, uid); boar Unit(S_w ^ Mix(uid)) < 0.5 (child rule without parents);
    wolf none."""
    mode = int(body.sex_mode[sp])
    if mode == SEXMODE_NATURAL:
        return natural_sex(s_q, uid, float(body.female_frac[sp]))
    if mode == SEXMODE_ALTERNATE:
        return SEX_FEMALE if unit((int(s_w) & M64) ^ mix(uid)) < float(body.child_female_frac[sp]) else SEX_MALE
    return SEX_NONE


def child_sex(body: Body, sp: int, s_w: int, child_uid: int, seed: int) -> int:
    """Judge-world newborn sex. Deer NB 98: Unit(uid_child ^ Settings.Seed) < 0.6 (S_w plays Settings.Seed);
    boar FAc 571: Unit(inherit seed) < 0.5; wolf none.
    [언리얼 값 그대로 — 근거 약함 (3-7 표 #13: 사슴 새끼 암컷 0.6 — 태어날 때는 대략 반반)]"""
    mode = int(body.sex_mode[sp])
    f = float(body.child_female_frac[sp])
    if mode == SEXMODE_NATURAL:
        return SEX_FEMALE if unit((int(child_uid) & M64) ^ (int(s_w) & M64)) < f else SEX_MALE
    if mode == SEXMODE_ALTERNATE:
        return SEX_FEMALE if unit(int(seed) & M64) < f else SEX_MALE
    return SEX_NONE


def first_birth_time(body: Body, sp: int, t: float, s_q: int, uid: int) -> float:
    """Next breeding time of a founder / adult respawn: t + base + spread × Unit(S_q ^ uid) (deer SP 182; boar FAc 334; wolf t)."""
    spread = float(body.first_birth_spread[sp])
    u = unit((int(s_q) & M64) ^ (int(uid) & M64)) if spread > 0 else 0.0
    return float(t) + float(body.first_birth_base[sp]) + spread * u


def age_seed(s_q: int, sp: int) -> int:
    """DECISION: FounderAge seed. Deer uses S_q (Unreal); wolf/boar ages (train world only, new rule) use S_q ^ Mix(1000 + sp) so
    species with the same ordinals do not share ages."""
    return int(s_q) if int(sp) == DEER else (int(s_q) ^ mix(1000 + int(sp))) & M64


def respawn_age(maturity: float, juvenile_frac: float, max_age: float, seed: int, uid: int) -> float:
    """DECISION (FounderAge needs a cohort count; a single respawn has count 1 → always adult): juvenile with probability
    juvenile_frac by hash, then the FounderAge formulas with U = Unit(seed + uid × 31)."""
    young = unit((int(seed) & M64) ^ mix((int(uid) + 1301) & M64)) < float(juvenile_frac)
    u = unit((int(seed) + int(uid) * 31) & M64)
    return maturity * (0.18 + 0.72 * u) if young else maturity + (max_age - maturity) * u


def age_frac(t, born, maturity):
    """FIndividual::AgeFraction = clamp((now − born) / maturity, 0, 1) (LH 196), arrays in steps."""
    return np.clip((np.asarray(t, dtype=np.float64) - born) / maturity, 0.0, 1.0)


def growth(af, smooth):
    """FIndividual::Growth = 0.75 + 0.25 × (smooth ? T·T·(3 − 2T) : T) (LH 197~200).
    [언리얼 값 그대로 — 근거 약함 (3-7 표 #6: 갓난 새끼 크기 0.75·속도 0.95 — 실제 갓난 사슴은 어미를 못 따라가 숨는다)]"""
    af = np.asarray(af, dtype=np.float64)
    return 0.75 + 0.25 * np.where(smooth, af * af * (3 - 2 * af), af)


def body_scale(g_size, gr):
    return g_size * gr                       # LH 201


def speed_scale(g_speed, gr):
    return g_speed * (0.8 + 0.2 * gr)        # LH 202


def maintenance(g_size, g_speed):
    """LH 203: size³ × (1 + 2 × max(0, speed − 1)). Independent of age.
    [언리얼 값 그대로 — 근거 약함 (3-7 표 #7: 젖·먹여 주기 없음, 새끼 유지비가 성체와 같음)]"""
    return g_size * g_size * g_size * (1 + np.maximum(0.0, g_speed - 1) * 2)


def mass_ratio(g_size, af):
    """Fauna mass ratio size³ × Lerp(0.12, 1, age) — bite damage and carcass meat (3-4). Fauna writes FMath::Pow(Size, 3); R9 uses
    size·size·size (portable bit-exact product, ≤ 1 ulp from pow)."""
    return g_size * g_size * g_size * (0.12 + (1.0 - 0.12) * np.asarray(af, dtype=np.float64))


def genome_valid(g_speed, g_size) -> np.ndarray:
    """FGenome::IsValid speed/size part (LH 45): 0.9 ≤ speed, size ≤ 1.1 (Caution·Sociability·Coat are not modelled)."""
    sp, sz = np.asarray(g_speed, dtype=np.float64), np.asarray(g_size, dtype=np.float64)
    return np.isfinite(sp) & (sp >= 0.9) & (sp <= 1.1) & np.isfinite(sz) & (sz >= 0.9) & (sz <= 1.1)


def can_parent_core(t, born, maturity, next_birth, energy, health, g_speed, g_size, e_min: float = 0.7,
                    hp_min: float = 0.7) -> np.ndarray:
    """FIndividual::CanParent (LH 204~206) for initialized residents: health ≥ 0.7, now − born ≥ maturity, now ≥ next_birth,
    energy ≥ 0.7, genome valid. Unreal also requires health ≤ 1 (HP / MaxHP) — the world caps HP at 1, so it is not re-checked
    here (a missing cap must not silently stop breeding). No age limit (LH has no ageing).
    [언리얼 값 그대로 — 근거 약함 (3-7 표 #5: 노화·수명 없음·상처 안 나음; #4: 늑대 성숙 1,350 < 사슴 2,700 스텝)]"""
    t = np.asarray(t, dtype=np.float64)
    h = np.asarray(health, dtype=np.float64)
    return (np.isfinite(h) & (h >= hp_min) & (t - born >= maturity) & (t >= next_birth) & (np.asarray(energy) >= e_min)
            & genome_valid(g_speed, g_size))


# --------------------------------------------------------------------------- #
# breeding (3-7)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class LifeRules:
    """Config-derived life rules. Built once per world batch: `LifeRules.from_cfg(cfg, body)`.
    [언리얼 값 그대로 — 근거 약함 (3-7 표 #2: 임신 30 초 = 225 스텝 — '짝짓기 대기'로 읽는다)]"""
    mode: str                     # "train" | "judge"
    quadrants: int
    body: Body
    e_min: float
    hp_min: float
    gestation: float
    recover: float
    retry: float
    cost: float
    child_e: float
    child_fat: float
    scan_num: int
    scan_den: int
    generation_cap: int
    clear_r: float
    shelter_push: float           # child spots of bodies that cannot enter shelters keep out of r + this (the push-out circle)
    limits_on: bool               # judge: content caps (wolf budget, boar cap, one pending); L0 turns them off
    one_pending: bool
    wolf_max: int
    wolf_prey_per: int
    boar_max: int
    plant_budget: tuple           # (3,) per species: grass ≥ max(1, plant eaters + 1) × coef (0 = no plant budget)

    @classmethod
    def from_cfg(cls, cfg: dict, body: Body | None = None) -> "LifeRules":
        from .r9_body import load_body

        b = body if body is not None else load_body(cfg)
        br = cfg["body_common"]["breed"]
        judge = cfg["world"]["mode"] == "judge"
        jd = cfg.get("judge", {}) if judge else {}
        lim = jd.get("limits", {}) if judge else {}
        pb = jd.get("plant_budget", {}) if judge else {}
        on = bool(lim.get("enabled", False))
        return cls(mode=cfg["world"]["mode"], quadrants=int(cfg["world"]["quadrants"]), body=b,
                   e_min=float(br["e_min"]), hp_min=float(br["hp_min"]), gestation=float(br["gestation"]),
                   recover=float(br["recover"]), retry=float(br["retry"]), cost=float(br["cost"]), child_e=float(br["child_e"]),
                   child_fat=float(br["child_fat"]), scan_num=int(br["scan_num"]), scan_den=int(br["scan_den"]),
                   generation_cap=int(br["generation_cap"]), clear_r=float(br["clear_r"]),
                   shelter_push=float(cfg["body_common"]["shelter_push"]),
                   limits_on=on, one_pending=bool(lim.get("one_pending", False)) and on,
                   wolf_max=int(lim.get("wolf_max", 0)), wolf_prey_per=int(lim.get("wolf_prey_per", 0)), boar_max=int(lim.get("boar_max", 0)),
                   plant_budget=tuple(float(pb.get(n, 0.0)) for n in ("deer", "wolf", "boar")))


@dataclass
class LifeState:
    """Life-owned arrays: pending pairs and counters. P = pair capacity per world: judge with one pending → Q × 3 (pair index
    q × 3 + species); otherwise (train world, judge L0) S // 2 + 1 (each slot is in at most one pair)."""
    K: int
    S: int
    Q: int
    P: int
    pair_on: np.ndarray           # (K, P) bool
    pair_a: np.ndarray            # (K, P) int64 slot of parent A (lower uid of the candidate order)
    pair_b: np.ndarray            # (K, P) int64 slot of parent B
    pair_ua: np.ndarray           # (K, P) int64 uid of A (slot reuse guard)
    pair_ub: np.ndarray           # (K, P) int64 uid of B
    pair_due: np.ndarray          # (K, P) float64 step of delivery
    pair_quad: np.ndarray         # (K, P) int8 quadrant of parent A at pairing (3-1)
    pair_sp: np.ndarray           # (K, P) int8 species
    opportunities: np.ndarray     # (K, Q, 3) int64 (8-2: scans with a compatible pair, deliveries deferred by a budget/cap)
    paired: np.ndarray            # (K, Q, 3) int64
    births: np.ndarray            # (K, Q, 3) int64
    blocked: np.ndarray           # (K, Q, 3, N_BLOCK) int64
    failed: np.ndarray            # (K, Q, 3) int64 due births without delivery for distance / no free spot (retry, not a block)
    cancelled: np.ndarray         # (K, Q, 3) int64 pending pairs dropped (death, quadrant, eligibility, boar grace)
    one_pending: bool = False
    log: list = field(default_factory=list)   # judge: (k, t, sp, quad, child_uid, uid_a, uid_b) per delivered birth
    # Report-only second count of the same blocks (Fix 단계 검토 medium, 사용자 확인 필요): `blocked` follows 8-2 literally — a
    # scan-time block is counted at every 5 s scan, so one pending pair (225 steps) blocks ~6 scans while it is counted once in
    # `paired`. `blocked_once` counts a scan-time ONE_PENDING block once per pending pair and a scan-time BOAR_CAP block once per
    # run of capped scans of that quadrant; delivery-time blocks (one per deferred pair) are counted as in `blocked`.
    blocked_once: np.ndarray | None = None    # (K, Q, 3, N_BLOCK) int64
    pend_counted: np.ndarray | None = None    # (K, P) bool — this pending pair already produced a ONE_PENDING block
    cap_streak: np.ndarray | None = None      # (K, Q) bool — the last boar scan of this quadrant was blocked by the boar cap

    @classmethod
    def alloc(cls, K: int, S: int, rules: LifeRules) -> "LifeState":
        Q = int(rules.quadrants)
        P = (Q * N_SPECIES) if rules.one_pending else (S // 2 + 1)
        z = lambda dt: np.zeros((K, P), dtype=dt)  # noqa: E731
        c = lambda: np.zeros((K, Q, N_SPECIES), np.int64)  # noqa: E731
        return cls(K=K, S=S, Q=Q, P=P, pair_on=z(bool), pair_a=np.full((K, P), -1, np.int64), pair_b=np.full((K, P), -1, np.int64),
                   pair_ua=z(np.int64), pair_ub=z(np.int64), pair_due=z(np.float64), pair_quad=z(np.int8), pair_sp=z(np.int8),
                   opportunities=c(), paired=c(), births=c(), blocked=np.zeros((K, Q, N_SPECIES, N_BLOCK), np.int64), failed=c(),
                   cancelled=c(), one_pending=bool(rules.one_pending),
                   blocked_once=np.zeros((K, Q, N_SPECIES, N_BLOCK), np.int64), pend_counted=z(bool),
                   cap_streak=np.zeros((K, Q), bool))

    def reset_world(self, k: int) -> None:
        """World k was re-initialised (VecEnv renew): drop its pairs; counters keep counting (R8 stats rule)."""
        self.pair_on[k] = False
        self.pair_a[k] = -1
        self.pair_b[k] = -1
        if self.pend_counted is not None:
            self.pend_counted[k] = False
            self.cap_streak[k] = False


@dataclass
class Newborn:
    """A judge-world child decided by `breed_step`; the world installs it into `slot` (lowest empty slot of its species)."""
    k: int
    slot: int
    sp: int
    uid: int
    pos: np.ndarray               # (2,) float64
    head: np.ndarray              # (2,) unit vector = GOLDEN8[j] of the chosen ring spot (outward from the ring centre) [어림]
    born: float
    sex: int
    g_speed: float
    g_size: float
    parent_a: int                 # uid
    parent_b: int                 # uid
    generation: int
    energy: float
    fat: float
    next_birth: float = 0.0       # FIndividual default (NB 94 `ChildLife = {}`): may breed as soon as mature
    offspring: int = 0


@dataclass
class BreedEvents:
    births: np.ndarray            # (K, S) int64 deliveries credited to each parent this step (reward birth term, both worlds)
    paired: np.ndarray            # (K, S) bool newly paired this step (stats / 8-3 '대기 중 도망')
    newborns: list                # list[Newborn] (judge only), in delivery order (world, then pair index)

    @classmethod
    def empty(cls, K: int, S: int) -> "BreedEvents":
        return cls(births=np.zeros((K, S), np.int64), paired=np.zeros((K, S), bool), newborns=[])


def mate_scan_now(t) -> np.ndarray:
    """Mate scan steps: ⌊2t/75⌋ changes (3-7, every 5 s, mean 37.5 steps). t = 0 scans (Unreal NextBirthScan starts at 0)."""
    t = np.asarray(t, dtype=np.int64)
    return (2 * t) // 75 != (2 * t - 2) // 75


def slot_species(w) -> np.ndarray:
    """(S,) species of each slot from the block bounds sp_lo/sp_hi."""
    out = np.full(int(w.S), -1, np.int64)
    for s in range(N_SPECIES):
        out[int(w.sp_lo[s]):int(w.sp_hi[s])] = s
    return out


def live_mask(w) -> np.ndarray:
    """(K, S) alive, not died earlier this step (bite / counter set dead_cause before order 5), HP > 0."""
    dc = getattr(w, "dead_cause", None)
    ok = np.asarray(w.alive, dtype=bool) & (np.asarray(w.hp) > 0)
    if dc is not None:
        ok &= np.asarray(dc) == CAUSE_NONE
    return ok


def can_parent(w, rules: LifeRules) -> np.ndarray:
    """(K, S) parent eligibility without the flee/action check (LH 204~206, NB 41~42): alive (no death this step), mature,
    t ≥ next_birth, E ≥ 0.7, HP ≥ 0.7 (bodies without HP count 1 — Native deer), generation < 64, genome valid."""
    body = rules.body
    ssp = slot_species(w)
    hp = np.where(body.has_hp[ssp][None, :], np.asarray(w.hp, dtype=np.float64), 1.0)
    core = can_parent_core(np.asarray(w.t, dtype=np.float64)[:, None], w.born, body.maturity[ssp][None, :], w.next_birth, w.E,
                           hp, w.g_speed, w.g_size, rules.e_min, rules.hp_min)
    return core & live_mask(w) & (np.asarray(w.generation) < rules.generation_cap)


def mate_compatible(sex_i: np.ndarray, sex_j: np.ndarray) -> np.ndarray:
    """Species-agnostic sex rule (NB 122, FAc 614): both unspecified (wolf) or both specified and different. Used by breeding and by
    the world's `mate_ok` observation column (no species number needed)."""
    si, sj = np.asarray(sex_i), np.asarray(sex_j)
    return ((si == SEX_NONE) & (sj == SEX_NONE)) | ((si != SEX_NONE) & (sj != SEX_NONE) & (si != sj))


def related(pa_i, pb_i, uid_i, pa_j, pb_j, uid_j) -> np.ndarray:
    """Incest rule (NB 123~127, FAc 615~619): parent-child or sharing at least one known parent (0 = unknown founder parent)."""
    pc = (pa_i == uid_j) | (pb_i == uid_j) | (pa_j == uid_i) | (pb_j == uid_i)
    sib = ((pa_i != 0) & ((pa_i == pa_j) | (pa_i == pb_j))) | ((pb_i != 0) & ((pb_i == pa_j) | (pb_i == pb_j)))
    return pc | sib


def _pair_matrix(w, k: int, idx: np.ndarray, mate_r: float) -> np.ndarray:
    """(n, n) bool compatible pairs among candidate slots idx (uid order): j > i, sex rule, not related, distance ≤ mate_r
    (squared, NB 128 / FAc 622 compare squared distances)."""
    P = w.pos[k, idx]
    dx = P[:, None, 0] - P[None, :, 0]
    dy = P[:, None, 1] - P[None, :, 1]
    near = dx * dx + dy * dy <= mate_r * mate_r
    sx = w.sex[k, idx]
    pa, pb, u = w.parent_a[k, idx], w.parent_b[k, idx], w.uid[k, idx]
    rel = related(pa[:, None], pb[:, None], u[:, None], pa[None, :], pb[None, :], u[None, :])
    m = mate_compatible(sx[:, None], sx[None, :]) & ~rel & near
    return np.triu(m, 1)


class _JudgeCtx:
    """Per-world bookkeeping for judge deliveries within one breed_step: live positions (+ newborns), quadrant counts per species
    (+ newborns), taken slots, quadrant grass sums (sequential sums, cells in C order)."""

    def __init__(self, w, k: int, live: np.ndarray, ssp: np.ndarray, Q: int):
        self.k = k
        m = live[k]
        self.pos = w.pos[k, m].copy()
        qd = np.asarray(w.quad[k], dtype=np.int64)
        self.cnt = np.zeros((Q, N_SPECIES), np.int64)
        for s in range(N_SPECIES):
            for q in range(Q):
                self.cnt[q, s] = int(np.count_nonzero(m & (ssp == s) & (qd == q)))
        self.taken: set[int] = set()
        self._grass = None
        self._w = w
        self.Q = Q

    def grass_q(self, q: int) -> float:
        if self._grass is None:
            cq = np.asarray(self._w.cell_quad)
            g = np.asarray(self._w.grass[self.k], dtype=np.float64)
            self._grass = np.zeros(self.Q)
            for qq in range(self.Q):
                v = g[cq == qq]
                self._grass[qq] = float(np.cumsum(v)[-1]) if v.size else 0.0
        return float(self._grass[q])


def _child_spot(w, rules: LifeRules, k: int, sp: int, a: int, b: int, ctx: _JudgeCtx) -> tuple[np.ndarray, int] | None:
    """First free spot on the golden ring (NB 59~70, FAc 529~546; 3-7 새끼 자리): centre = parent A (deer, wolf) or the parents'
    midpoint (boar); radius r0 + dr × j along GOLDEN8[j], j = 0..7. Free = inside [0, size]², ≥ clear_r from every live individual
    (newborns of this step included, NB 67~68 '< 100 cm' → blocked), and for bodies that cannot enter shelters outside every
    shelter circle r + shelter_push. DECISION (open issue): Unreal adds a per-birth hash rotation Unit(A ^ B) × 2π (boar Unit(A))
    — dropped (GOLDEN8 literal table only, 3-9); Unreal's wolf test is r (Contains), R9 uses the push-out circle r + 0.5 so a
    newborn wolf never starts inside it (test 11)."""
    body = rules.body
    pa = w.pos[k, a]
    c = (pa + w.pos[k, b]) * 0.5 if int(body.child_center[sp]) == CHILD_AT_MIDPOINT else pa
    size = float(w.size)
    cr2 = rules.clear_r * rules.clear_r
    avoid = bool(body.child_avoid_shelter[sp])
    if avoid:
        ok = np.asarray(w.cov_ok[k], dtype=bool)
        cc = np.asarray(w.cov_c[k], dtype=np.float64)[ok]
        rr = np.asarray(w.cov_r[k], dtype=np.float64)[ok] + rules.shelter_push
    r0, dr = float(body.child_r0[sp]), float(body.child_dr[sp])
    for j in range(8):
        s = c + (r0 + dr * j) * GOLDEN8[j]
        if s[0] < 0 or s[1] < 0 or s[0] > size or s[1] > size:
            continue
        if avoid and len(rr):
            dx, dy = s[0] - cc[:, 0], s[1] - cc[:, 1]
            if np.any(dx * dx + dy * dy <= rr * rr):
                continue
        if len(ctx.pos):
            dx, dy = ctx.pos[:, 0] - s[0], ctx.pos[:, 1] - s[1]
            if np.any(dx * dx + dy * dy < cr2):
                continue
        return s, j
    return None


def _block(L: LifeState, k: int, q: int, sp: int, reason: int, once: bool = True) -> None:
    """One blocked opportunity (8-2, counted literally). `once` = also count it in the report-only `blocked_once`."""
    L.opportunities[k, q, sp] += 1
    L.blocked[k, q, sp, reason] += 1
    if once and L.blocked_once is not None:
        L.blocked_once[k, q, sp, reason] += 1


def _judge_deliver(w, L: LifeState, rules: LifeRules, ev: BreedEvents, ctx: _JudgeCtx, ssp: np.ndarray, p: int,
                   tf: float) -> None:
    """Judge-world delivery of pair p of world ctx.k in Unreal order (NB 56~108, FAc 517~588): [boar cap] → spot → budget →
    slot cap → newborn + costs. A blocked delivery counts one opportunity + one block (8-2); the parents already have
    next_birth = t + retry (bounded retry, NB 54 / FAc 518)."""
    body = rules.body
    k = ctx.k
    a, b = int(L.pair_a[k, p]), int(L.pair_b[k, p])
    sp, q = int(L.pair_sp[k, p]), int(L.pair_quad[k, p])
    # [언리얼 값 그대로 — 근거 약함 (3-7 표 #11: 멧돼지 사분면 상한 14 — 상한은 먹이와 텃세가 정한다)]
    if rules.limits_on and sp == BOAR and ctx.cnt[q, BOAR] >= rules.boar_max:
        _block(L, k, q, sp, BLOCK_BOAR_CAP)
        return
    spot = _child_spot(w, rules, k, sp, a, b, ctx)
    if spot is None:
        L.failed[k, q, sp] += 1           # NB 71 / FAc 547 `continue` — not a block reason [어림, 계약 11절 #34]
        return
    if sp == WOLF and rules.limits_on:
        # ESS 401~405: region wolves + 1 ≤ 6 and region deer ≥ 8 × (wolves + 1); boar (Fauna) is not counted as prey.
        # [언리얼 값 그대로 — 근거 약함 (3-7 표 #10: 늑대 예산이 사슴만 셈, 지역 사슴 수를 전지적으로 셈)]
        nw = int(ctx.cnt[q, WOLF])
        if not (nw + 1 <= rules.wolf_max and int(ctx.cnt[q, DEER]) >= rules.wolf_prey_per * (nw + 1)):
            _block(L, k, q, sp, BLOCK_WOLF_BUDGET)
            return
    coef = float(rules.plant_budget[sp])
    if coef > 0:
        # ESS 406 (deer, MinimumMeal × 6 = 0.42) / FAc 552~556 (boar, × 5 = 0.35): quadrant grass (root excluded) ≥
        # coef × max(1, plant eaters + 1). Plant eaters = live grass-eating species in the quadrant (+ newborns this step).
        eaters = int(sum(int(ctx.cnt[q, s]) for s in range(N_SPECIES) if bool(body.eats[s, GRASS])))
        if not (ctx.grass_q(q) >= coef * max(1, eaters + 1)):
            _block(L, k, q, sp, BLOCK_FOOD)
            return
    lo, hi = int(w.sp_lo[sp]), int(w.sp_hi[sp])
    dc = getattr(w, "dead_cause", None)
    empty = ~np.asarray(w.alive[k, lo:hi], dtype=bool)
    if dc is not None:
        empty &= np.asarray(dc[k, lo:hi]) == CAUSE_NONE     # a slot that died this step keeps its body until order 6
    slot = -1
    for i in np.flatnonzero(empty):
        if lo + int(i) not in ctx.taken:
            slot = lo + int(i)
            break
    if slot < 0:
        _block(L, k, q, sp, BLOCK_SLOT_CAP)
        return
    pos, j = spot
    ua, ub = int(w.uid[k, a]), int(w.uid[k, b])
    seed = inherit_seed(body, sp, ua, ub, int(w.offspring[k, a]))
    g_speed, g_size = inherit(float(w.g_speed[k, a]), float(w.g_size[k, a]), float(w.g_speed[k, b]), float(w.g_size[k, b]), seed)
    uid = int(w.next_uid[k])
    w.next_uid[k] = uid + 1
    sex = child_sex(body, sp, int(w.s_w[k]), uid, seed)
    gen = max(int(w.generation[k, a]), int(w.generation[k, b])) + 1
    # [언리얼 값 그대로 — 근거 약함 (3-7 표 #1: 한배 1 마리; #8: 멧돼지 새끼가 어미를 따라가지 않음 — 따라가기는 두뇌가 배울 일)]
    nb = Newborn(k=k, slot=slot, sp=sp, uid=uid, pos=np.array(pos, dtype=np.float64), head=GOLDEN8[j].copy(), born=tf, sex=sex,
                 g_speed=g_speed, g_size=g_size, parent_a=ua, parent_b=ub, generation=gen, energy=rules.child_e, fat=rules.child_fat)
    ev.newborns.append(nb)
    ctx.taken.add(slot)
    ctx.pos = np.concatenate([ctx.pos, nb.pos[None, :]], 0)
    nq = int(quadrant_of(nb.pos, float(w.size), int(L.Q)))
    ctx.cnt[nq, sp] += 1
    _pay(w, ev, rules, k, a, b, tf)
    L.births[k, q, sp] += 1
    L.log.append((k, int(tf), sp, q, uid, ua, ub))


def _pay(w, ev: BreedEvents, rules: LifeRules, k, a, b, tf) -> None:
    """Delivery costs (NB 101~107, FAc 576~587): both parents E − 0.2, next_birth = t + 2250, offspring + 1, reward credit.
    [언리얼 값 그대로 — 근거 약함 (3-7 표 #9: 수컷도 암컷과 같은 비용)]"""
    for s in (a, b):
        w.E[k, s] = w.E[k, s] - rules.cost
        w.next_birth[k, s] = tf + rules.recover
        w.offspring[k, s] = w.offspring[k, s] + 1
        ev.births[k, s] += 1


def _new_pair(w, L: LifeState, ev: BreedEvents, mating: np.ndarray, rules: LifeRules, k: int, p: int, a: int, b: int, sp: int,
              q: int, tf: float) -> None:
    L.pair_on[k, p] = True
    L.pair_a[k, p], L.pair_b[k, p] = a, b
    L.pair_ua[k, p], L.pair_ub[k, p] = int(w.uid[k, a]), int(w.uid[k, b])
    L.pair_due[k, p] = tf + rules.gestation
    L.pair_quad[k, p], L.pair_sp[k, p] = q, sp
    mating[k, a] = mating[k, b] = True
    ev.paired[k, a] = ev.paired[k, b] = True
    L.opportunities[k, q, sp] += 1
    L.paired[k, q, sp] += 1
    if L.pend_counted is not None:
        L.pend_counted[k, p] = False


def _scan(w, L: LifeState, rules: LifeRules, ev: BreedEvents, k: int, elig: np.ndarray, mating: np.ndarray, act: np.ndarray,
          ctx_cnt: np.ndarray | None, tf: float) -> None:
    """Mate scan of world k (NB 112~133, FAc 593~624). See the module docstring."""
    body = rules.body
    Q = int(L.Q)
    qd = np.asarray(w.quad[k], dtype=np.int64)
    for sp in range(N_SPECIES):
        lo, hi = int(w.sp_lo[sp]), int(w.sp_hi[sp])
        if hi <= lo:
            continue
        # 짝 맺을 때만 도망 확인 (3-7): deer RUN·SHELTER, boar RUN, wolf none (pair_block of the decision action).
        base = elig[k, lo:hi] & ~mating[k, lo:hi] & ~body.pair_block[sp, act[k, lo:hi]]
        for q in range(Q):
            m = base & (qd[lo:hi] == q)
            idx = lo + np.flatnonzero(m)
            if len(idx) < 2:
                continue
            idx = idx[np.argsort(w.uid[k, idx], kind="stable")]
            M = _pair_matrix(w, k, idx, float(body.mate_r[sp]))
            if not M.any():
                continue
            if rules.limits_on and sp == BOAR and ctx_cnt is not None and ctx_cnt[q, BOAR] >= rules.boar_max:
                _block(L, k, q, sp, BLOCK_BOAR_CAP, once=not bool(L.cap_streak[k, q]))   # FAc 600 (scan skipped at the cap)
                L.cap_streak[k, q] = True
                continue
            if sp == BOAR:
                L.cap_streak[k, q] = False
            if L.one_pending:
                # [언리얼 값 그대로 — 근거 약함 (3-7 표 #12: 사분면·종마다 대기 1 건 — 큰 무리 증가가 직선으로 묶인다)]
                p = q * N_SPECIES + sp
                if L.pair_on[k, p]:
                    _block(L, k, q, sp, BLOCK_ONE_PENDING, once=not bool(L.pend_counted[k, p]))
                    L.pend_counted[k, p] = True
                    continue
                f = int(np.flatnonzero(M.ravel())[0])
                i, j = divmod(f, len(idx))
                _new_pair(w, L, ev, mating, rules, k, p, int(idx[i]), int(idx[j]), sp, q, tf)
                continue
            used = np.zeros(len(idx), bool)
            free = np.flatnonzero(~L.pair_on[k])
            nf = 0
            for i in range(len(idx)):
                if used[i]:
                    continue
                row = M[i] & ~used
                if not row.any():
                    continue
                j = int(np.argmax(row))
                used[i] = used[j] = True
                _new_pair(w, L, ev, mating, rules, k, int(free[nf]), int(idx[i]), int(idx[j]), sp, q, tf)
                nf += 1


def breed_step(w, L: LifeState, rules: LifeRules) -> BreedEvents:
    """Step order 5 (3-9): pending checks → deliveries (cost −0.2 E both, next_birth t + 2250, offspring += 1, reward credit) →
    scan (when `mate_scan_now`). Train: all compatible pairs in uid order, no newborn bodies. Judge: one pending per quadrant ×
    species (off in L0), birth budget and content caps (blocked counters), Newborn records for the world to install.
    Writes only LIFE_WRITES; `w.mating` is rewritten from the pending pairs at the end."""
    K, S = int(w.K), int(w.S)
    ev = BreedEvents.empty(K, S)
    body = rules.body
    judge = rules.mode == "judge"
    t = np.asarray(w.t, dtype=np.int64)
    tf = t.astype(np.float64)
    ssp = slot_species(w)
    live = live_mask(w)
    act = np.clip(np.asarray(w.act, dtype=np.int64), 0, N_ACTIONS - 1)
    kk = np.arange(K)[:, None]
    elig = can_parent(w, rules)
    ctxs: dict[int, _JudgeCtx] = {}

    # ---- 1. pending pairs -------------------------------------------------------------------------------------------------
    if L.pair_on.any():
        on = L.pair_on.copy()
        a = np.where(on, L.pair_a, 0)
        b = np.where(on, L.pair_b, 0)
        psp = L.pair_sp.astype(np.int64)
        uid_ok = (w.uid[kk, a] == L.pair_ua) & (w.uid[kk, b] == L.pair_ub)
        quad_ok = (w.quad[kk, a] == L.pair_quad) & (w.quad[kk, b] == L.pair_quad)
        both_elig = elig[kk, a] & elig[kk, b]
        # 대기 중 확인: deer·wolf alive·quadrant·E·HP eligibility, boar alive·quadrant only (NB 47~51, FAc 503~508). The deer's
        # Retreat/Panic/Shelter cancel of Unreal is NOT ported — 3-7 '언리얼과 다르게 옮긴 것' (RL-6).
        keep = on & uid_ok & live[kk, a] & live[kk, b] & quad_ok & (~body.pending_needs_parent[psp] | both_elig)
        due = keep & (tf[:, None] >= L.pair_due)
        grace = body.birth_grace[psp]
        waits = grace > 0
        bb = body.birth_block[psp, act[kk, a]] | body.birth_block[psp, act[kk, b]]
        ok_par = both_elig & ~bb
        d = w.pos[kk, a] - w.pos[kk, b]
        near = d[..., 0] * d[..., 0] + d[..., 1] * d[..., 1] <= body.birth_r[psp] * body.birth_r[psp]
        over = due & waits & (tf[:, None] > L.pair_due + grace)            # FAc 504: Now > Due + 20 s → cancel
        go = (due & waits & ~over & ok_par & near) | (due & ~waits & ok_par)
        cancel = (on & ~keep) | over | (due & ~waits & ~ok_par)
        end = cancel | go
        if end.any():
            ke, pe = np.nonzero(cancel)
            np.add.at(L.cancelled, (ke, L.pair_quad[ke, pe].astype(np.int64), psp[ke, pe]), 1)
            L.pair_on &= ~end
            kg, pg = np.nonzero(go)                                         # row-major = world, then pair index
            ag, bg = a[kg, pg], b[kg, pg]
            # bounded retry on every delivery attempt (NB 54, FAc 518) — overwritten by t + 2250 on a delivery
            w.next_birth[kg, ag] = tf[kg] + rules.retry
            w.next_birth[kg, bg] = tf[kg] + rules.retry
            far = ~near[kg, pg]                                             # deer·wolf at due but > birth_r (NB 58)
            if far.any():
                np.add.at(L.failed, (kg[far], L.pair_quad[kg[far], pg[far]].astype(np.int64), psp[kg[far], pg[far]]), 1)
            kd, pd = kg[~far], pg[~far]
            if not judge:
                for k, p in zip(kd.tolist(), pd.tolist()):                  # train: reward and costs only, no body (3-6)
                    _pay(w, ev, rules, k, int(L.pair_a[k, p]), int(L.pair_b[k, p]), float(tf[k]))
                    L.births[k, int(L.pair_quad[k, p]), int(L.pair_sp[k, p])] += 1
            else:
                for k, p in zip(kd.tolist(), pd.tolist()):
                    if k not in ctxs:
                        ctxs[k] = _JudgeCtx(w, k, live, ssp, int(L.Q))
                    _judge_deliver(w, L, rules, ev, ctxs[k], ssp, p, float(tf[k]))

    # ---- 2. mating flags after pending -----------------------------------------------------------------------------------
    mating = _mating_from_pairs(L, K, S)

    # ---- 3. scan ------------------------------------------------------------------------------------------------------------
    scan = mate_scan_now(t)
    if scan.any():
        elig2 = can_parent(w, rules)          # next_birth / E changed for parents handled above
        for k in np.flatnonzero(scan).tolist():
            cnt = None
            if judge:
                if k not in ctxs:
                    ctxs[k] = _JudgeCtx(w, k, live, ssp, int(L.Q))
                cnt = ctxs[k].cnt
            _scan(w, L, rules, ev, k, elig2, mating, act, cnt, float(tf[k]))
    w.mating[...] = mating
    return ev


def _mating_from_pairs(L: LifeState, K: int, S: int) -> np.ndarray:
    m = np.zeros((K, S), bool)
    ko, po = np.nonzero(L.pair_on)
    m[ko, L.pair_a[ko, po]] = True
    m[ko, L.pair_b[ko, po]] = True
    return m


def on_slot_reset(L: LifeState, k: int, slots, w=None) -> None:
    """A slot of world k was reset (train respawn) or emptied: cancel pending pairs that reference it (3-6 '그 칸을 가리키던 값').
    With `w` the partners' `w.mating` flags are cleared at once; without it they are rewritten at the next breed_step (the
    uid guard cancels the pair there too)."""
    s = np.asarray(slots, dtype=np.int64).reshape(-1)
    if not len(s):
        return
    hit = L.pair_on[k] & (np.isin(L.pair_a[k], s) | np.isin(L.pair_b[k], s))
    if hit.any():
        p = np.flatnonzero(hit)
        np.add.at(L.cancelled, (np.full(len(p), k), L.pair_quad[k, p].astype(np.int64), L.pair_sp[k, p].astype(np.int64)), 1)
    L.pair_on[k] = L.pair_on[k] & ~hit
    if w is not None:
        w.mating[k] = _mating_from_pairs(L, L.K, L.S)[k]


def life_stats(L: LifeState) -> dict:
    """Counters for reports (8-2 출생 막힘): opportunities, paired, births, blocked by reason, failed, cancelled and the content-block
    share per species = content-blocked / (content-blocked + paired) summed over worlds and quadrants (food budget apart)."""
    content = L.blocked[..., list(CONTENT_BLOCKS)].sum(-1).sum((0, 1))
    paired = L.paired.sum((0, 1))
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(content + paired > 0, content / np.maximum(content + paired, 1), 0.0)
    bo = L.blocked_once if L.blocked_once is not None else L.blocked
    return dict(opportunities=L.opportunities.copy(), paired=L.paired.copy(), births=L.births.copy(), blocked=L.blocked.copy(),
                blocked_once=bo.copy(),
                failed=L.failed.copy(), cancelled=L.cancelled.copy(), block_names=BLOCK_NAMES, content_block_share=share,
                food_blocked=L.blocked[..., BLOCK_FOOD].sum((0, 1)))
