"""R9 evaluation core — run R9 worlds with fixed brains, record hidden statistics, compute the 8절 metrics
(design AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 8~10절). Used by eval_r9.py (subcommands), plot_r9.py,
r9_replay.py and tests/test_r9_eval.py.

Rules
  - The world is never written: the recorder reads hidden state (species, uid, E, HP, ...) for statistics only, through the
    world's step hook (called after every step) and two per-decision calls (`before(w, a)` with the decision-time state and the
    chosen actions, `after(...)` with the step results). Per-world statistics only depend on that world (eval RNG per world,
    default_rng([seed, TAG_EVAL])), so worlds may be run in chunks (`run(..., chunk=n)`) with the same result.
  - Seeds (10절): judge seeds 44800~44999 are only for `eval_r9.py judge`/`mixed` behind the lock file (9-2, test 25); every other
    tool calls `assert_not_judge_seeds`. 95% intervals = world bootstrap 2,000 draws, seed 44799 (a fresh generator per statistic).
  - Interpretations where the design is silent are marked [해석] / [어림] in comments (also in the eval agent's report).
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                               # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env_v2 import r9_body as B  # noqa: E402
from env_v2 import r9_brains as BR  # noqa: E402
from env_v2 import r9_life as L  # noqa: E402
from env_v2 import r9_world as W  # noqa: E402

DEER, WOLF, BOAR = B.DEER, B.WOLF, B.BOAR
SPECIES = B.SPECIES

# --------------------------------------------------------------------------- #
# seeds (10절) and bootstrap
# --------------------------------------------------------------------------- #

SEED_RANGES = {
    "train_pool": (43000, 43999), "pick_train": (44000, 44049), "confirm_train": (44050, 44099),
    "pick_judge": (44100, 44139), "confirm_judge": (44140, 44179), "smoke": (44180, 44199), "check": (44200, 44299),
    "weak_eval": (44300, 44349), "test": (44350, 44399), "weak_train": (44400, 44499),
    "judge_j1": (44800, 44899), "judge_j2": (44900, 44999),
}
JUDGE_LO, JUDGE_HI = 44800, 44999
BOOT = 2000
BOOT_SEED = 44799

# 8-2·9-2 numbers
J2_SHORT_MIN, J2_LONG_MIN = 0.6, 0.4
J3_BANDS = dict(success=(0.10, 0.50), daily_kill=(0.05, 0.30), juv_index_min=1.5)
J3_MIN_N = dict(segments=100, kills=30, boar_kills=20)
BLOCK_SHARE_FLAG = 0.2
# Metric definitions used by the gates (C0-2·C0-7) and the verdicts (J2 읽기·J3). Defaults = the design text (8-2): a hunt
# attempt per (wolf, target) approach segment, a block per 5 s scan. Fix 단계 검토(medium 둘)는 둘 다 실제 뜻보다 부풀려진다고
# 보았다 — 고르는 것은 사용자 몫이라 기본은 문서대로 두고, 다른 정의(같은 늑대의 겹친 구간을 묶은 시도 · 대기 한 번에 한 번
# 센 막힘)는 늘 함께 계산해 보고한다. eval_r9.py --hunt-def episode / --block-def once 로 바꾼다 (결과 파일에 defs 로 남김).
DEFS = dict(hunt="pair", block="scan")
HUNT_DEFS = ("pair", "episode")
BLOCK_DEFS = ("scan", "once")
OUT_OF_RANGE = (64, 6, 14)            # 3-6 학습 범위 밖: 사분면 사슴 > 64·늑대 > 6·멧돼지 > 14
NEWBORN_WINDOW = 300                  # 새끼 첫 300 스텝
RESPAWN_EXCLUDE = 300                 # 8-4 구석 지키기: 다시 난 뒤 300 스텝 뺌
ARENA_WINDOW = 200                    # 8-4 무대 악용: 다시 난 뒤 200 스텝
WALL_BAND = 4.0
FLEE_ACTIONS = tuple(range(B.RUN_FIRST, B.RUN_LAST + 1)) + (B.SHELTER,)
SPLIT_SALT = 0x5239_4A31_0000_0001    # J1 해시 배정 (8-1) — 값 자체는 [어림](고정 상수면 됨)
SPLIT_SALT2 = 0x5239_4A31_0000_0002

ANOMALY_THRESHOLDS = dict(corner=0.2, wall_drive=2.0, edge_stand=0.3, edge_kill=2.0, shield=2.0, always_hide=0.6,
                          always_run=0.6, always_fight=0.3, surplus=0.2, arena=2.0)


class JudgeSeedError(ValueError):
    """A non-judge tool received a judge seed (44800~44999), or a judge tool got a mixed / wrong range (9-2, test 25)."""


class JudgeLockError(RuntimeError):
    """Judge seeds were requested with brains or configs other than the locked ones (9-2 판정 시드 잠금)."""


def seed_list(lo: int, hi: int) -> list[int]:
    """Inclusive seed range [lo, hi]."""
    return list(range(int(lo), int(hi) + 1))


def is_judge_seed(s) -> np.ndarray:
    s = np.asarray(s, dtype=np.int64)
    return (s >= JUDGE_LO) & (s <= JUDGE_HI)


def assert_not_judge_seeds(seeds, who: str) -> None:
    """Training / check / calibration / scene tools must never touch judge seeds (9-2, test 25)."""
    bad = [int(s) for s in np.asarray(list(seeds), dtype=np.int64).reshape(-1) if is_judge_seed(s)]
    if bad:
        raise JudgeSeedError(f"{who}: 판정 시드 {bad[:5]}{'…' if len(bad) > 5 else ''} (44800~44999) 는 판정(eval_r9.py judge·mixed, "
                             f"잠금 파일)만 쓴다 — 개발 44000~44199·점검 44200~44299·시험 44350~44399 를 쓴다")


def judge_seed_mode(seeds, allowed: tuple[int, int], who: str) -> bool:
    """True when every seed is a judge seed inside `allowed` (then the lock applies), False when none is (dry run). A mix, or judge
    seeds outside the command's range (J1 44800~44899 / J2·J3 44900~44999), is an error."""
    s = np.asarray(list(seeds), dtype=np.int64)
    jm = is_judge_seed(s)
    if not jm.any():
        return False
    if not jm.all():
        raise JudgeSeedError(f"{who}: 판정 시드와 다른 시드를 섞지 않는다")
    if (s < allowed[0]).any() or (s > allowed[1]).any():
        raise JudgeSeedError(f"{who}: 판정 시드는 {allowed[0]}~{allowed[1]} 만 (10절)")
    return True


def boot_ci(stat: Callable[[np.ndarray], float], K: int, B_: int = BOOT, seed: int = BOOT_SEED) -> list[float]:
    """World bootstrap 95% interval of stat(idx) (idx = K world indices drawn with replacement). Fresh generator per statistic so
    every interval is reproducible on its own (R8 boot_delta)."""
    if K <= 0:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    vals = np.empty(B_)
    for b in range(B_):
        vals[b] = stat(rng.integers(0, K, K))
    vals = vals[np.isfinite(vals)]
    if not len(vals):
        return [float("nan"), float("nan")]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def ratio(num, den) -> float:
    num, den = float(np.sum(num)), float(np.sum(den))
    return num / den if den > 0 else float("nan")


def boot_ratio(num: np.ndarray, den: np.ndarray, scale: float = 1.0) -> tuple[float, list[float]]:
    """Point Σnum/Σden × scale and its world-bootstrap interval (num, den per world)."""
    num, den = np.asarray(num, dtype=np.float64), np.asarray(den, dtype=np.float64)
    pt = ratio(num, den) * scale
    ci = boot_ci(lambda i: ratio(num[i], den[i]) * scale, len(num))
    return pt, ci


def boot_mean(x: np.ndarray) -> tuple[float, list[float]]:
    x = np.asarray(x, dtype=np.float64)
    pt = float(x.mean()) if len(x) else float("nan")
    return pt, boot_ci(lambda i: float(x[i].mean()), len(x))


def boot_rate_diff(nA, dA, nB, dB, scale: float = 1000.0) -> tuple[float, list[float]]:
    """(ΣnA/ΣdA − ΣnB/ΣdB) × scale with a paired world bootstrap (same worlds drawn for both)."""
    nA, dA, nB, dB = (np.asarray(x, dtype=np.float64) for x in (nA, dA, nB, dB))
    pt = (ratio(nA, dA) - ratio(nB, dB)) * scale
    ci = boot_ci(lambda i: (ratio(nA[i], dA[i]) - ratio(nB[i], dB[i])) * scale, len(nA))
    return pt, ci


# --------------------------------------------------------------------------- #
# judge seed lock (9-2, test 25)
# --------------------------------------------------------------------------- #

LOCK_NAME = "JUDGE_LOCK.json"
BRANCHES = ("A", "B")
BRAIN_KEYS = tuple(f"{b}:{s}" for b in BRANCHES for s in SPECIES)


def file_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# World code that decides a judge trajectory (Fix 단계 검토 low: '세계 코드를 고친 뒤 같은 시드로 다시 판정'도 잠금이 막게).
CODE_FILES = ("env_v2/r9_body.py", "env_v2/r9_world.py", "env_v2/r9_life.py", "env_v2/r9_brains.py")


def code_digest() -> str:
    """sha256 over the world code files with line endings normalised (a CRLF checkout must not change the digest)."""
    h = hashlib.sha256()
    for rel_ in CODE_FILES:
        h.update(rel_.encode("utf-8") + b"\0")
        h.update((ROOT / rel_).read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def judge_gate(lock_path: Path, brain_paths: dict[str, str], cfg_train: dict, cfg_judge: dict, who: str, seeds,
               note: str = "") -> dict:
    """First judge-seed run writes the lock (brain sha256 × 6, config digests, contract hashes, time); later runs must match it
    exactly or JudgeLockError is raised (다음 판은 새 시드 범위로만). All six final brains (A·B × 3 species) must be named even when
    a batch uses fewer (RULE) — the lock always covers the whole final set. Returns the lock dict."""
    miss = [k for k in BRAIN_KEYS if k not in brain_paths]
    if miss:
        raise JudgeLockError(f"{who}: 판정 시드에는 최종 두뇌 6 개(--brain A:deer=… 등)를 모두 적는다 — 빠짐 {miss}")
    want = dict(
        brains={k: file_sha256(brain_paths[k]) for k in BRAIN_KEYS},
        config_digest=dict(train=BR.config_digest(cfg_train), judge=BR.config_digest(cfg_judge)),
        io_hash=B.hash_hex(B.io_hash()),
        body_table_hash=dict(train=B.hash_hex(B.body_table_hash(cfg_train)), judge=B.hash_hex(B.body_table_hash(cfg_judge))),
        code_digest=code_digest(),
    )
    lock_path = Path(lock_path)
    s = [int(x) for x in seeds]
    run = dict(who=who, seeds=[min(s), max(s)], n=len(s), note=note, time=time.strftime("%Y-%m-%d %H:%M:%S"))
    with _file_mutex(lock_path.with_suffix(".lck")):          # judge parts may start together (STATUS 판정 계획)
        return _judge_gate_locked(lock_path, brain_paths, want, run, who)


class _file_mutex:
    """Exclusive-create mutex file (Windows and POSIX), waits up to 120 s, then raises."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def __enter__(self):
        import os

        self.path.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                if time.time() - t0 > 120.0:
                    raise JudgeLockError(f"잠금 뮤텍스 {self.path} 를 120 초 안에 얻지 못했다 (남은 파일이면 지운다)")
                time.sleep(0.2)

    def __exit__(self, *exc):
        import os

        os.close(self.fd)
        try:
            os.remove(str(self.path))
        except OSError:
            pass
        return False


def _judge_gate_locked(lock_path: Path, brain_paths: dict, want: dict, run: dict, who: str) -> dict:
    if not lock_path.exists():
        lock = dict(version=1, created=run["time"], **want, brain_paths={k: str(brain_paths[k]) for k in BRAIN_KEYS}, runs=[run])
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=1), encoding="utf-8")
        return lock
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    diff = []
    for k in BRAIN_KEYS:
        if lock["brains"].get(k) != want["brains"][k]:
            diff.append(f"brain {k}")
    for k in ("train", "judge"):
        if lock["config_digest"].get(k) != want["config_digest"][k]:
            diff.append(f"config {k}")
    if lock.get("io_hash") != want["io_hash"]:
        diff.append("io_hash")
    if lock.get("code_digest") != want["code_digest"]:
        diff.append("world code (r9_body·world·life·brains)")
    if diff:
        raise JudgeLockError(f"{who}: 판정 시드 잠금({lock_path})과 다름: {diff} — 잠근 판 {lock['created']}. "
                             "다른 두뇌·설정은 판정 시드를 다시 쓰지 않는다(다음 판은 새 시드 범위로만)")
    lock["runs"].append(run)
    lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=1), encoding="utf-8")
    return lock


# --------------------------------------------------------------------------- #
# brains and controllers
# --------------------------------------------------------------------------- #

RULE_OF = {DEER: "RULE_DEER", WOLF: "RULE_WOLF", BOAR: "RULE_BOAR"}


def parse_brain_args(items) -> dict[str, str]:
    """['A:deer=path', 'deer=path', ...] → {'A:deer': path, '-:deer': path}."""
    out = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError(f"--brain 꼴은 갈래:종=경로 (예 A:deer=ckpt/r9/A/deer_r10.npz): {it!r}")
        key, path = it.split("=", 1)
        if ":" not in key:
            key = f"-:{key}"
        br, sp = key.split(":", 1)
        if sp not in SPECIES:
            raise ValueError(f"모르는 종 {sp!r}")
        out[f"{br}:{sp}"] = path
    return out


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_brains(paths: dict[str, str], cfg: dict) -> dict[str, BR.Brain]:
    """npz brains, checked against the world config (r9_brains.load_brain — io/body hashes, test 27)."""
    out = {}
    for key, p in paths.items():
        sp = key.split(":", 1)[1]
        out[key] = BR.load_brain(_resolve(p), cfg, sp)
    return out


_RULE_CACHE: dict = {}


def rule_brain(name: str, cfg: dict) -> BR.RuleBrain:
    key = (name, id(cfg))
    if key not in _RULE_CACHE:
        _RULE_CACHE[key] = BR.make_rule(name, cfg)
    return _RULE_CACHE[key]


def brain_for(spec: str, sp: int, cfg: dict, brains: dict[str, BR.Brain]) -> BR.Brain:
    """spec = rule name (RULE_NAMES) | 'rule' (the species' RULE_*) | branch 'A'/'B'/'-' (from --brain) | path.npz."""
    if spec == "rule":
        spec = RULE_OF[sp]
    if spec in BR.RULE_NAMES:
        return rule_brain(spec, cfg)
    key = f"{spec}:{SPECIES[sp]}"
    if key in brains:
        return brains[key]
    if str(spec).endswith(".npz"):
        return BR.load_brain(_resolve(spec), cfg, sp)
    raise ValueError(f"{SPECIES[sp]} 두뇌 {spec!r} 를 모른다 (규칙 이름, 'rule', --brain 으로 준 갈래, 또는 .npz)")


def ctrl(brain: BR.Brain, stochastic: bool = False, label: str = "") -> BR.Controller:
    return BR.Controller(brain=brain, stochastic=bool(stochastic), label=label or brain.name)


@dataclass
class SplitBrain(BR.Brain):
    """J1 / C0-11 mixed herd (8-1): one species block, two brains, per-slot choice `mask` (True = `first`, the learned / tested
    brain). Both brains run on the whole same-shape block (7-10) and the rows are picked; state columns are concatenated
    [first | second]. `mask` is a view into the recorder's group array, updated when a slot gets a new individual."""
    first: BR.Brain | None = None
    second: BR.Brain | None = None
    mask: np.ndarray | None = field(default=None, repr=False)

    def logits(self, obs):
        return None

    def decide(self, obs, u, stochastic, state, ctx):
        n1 = int(self.first.n_state)
        s1 = state[:, :n1] if state is not None else None
        s2 = state[:, n1:] if state is not None else None
        a1, g1 = self.first.decide(obs, u, stochastic, s1, ctx)
        a2, g2 = self.second.decide(obs, u, stochastic, s2, ctx)
        m = np.asarray(self.mask, dtype=bool)
        return np.where(m, a1, a2).astype(np.int64), np.where(m, g1, g2)


def split_hash(seed: int, uid: int) -> float:
    """[0, 1) hash of (world seed, uid) for the J1 assignment (r9_life Mix/Unit)."""
    return L.unit(L.mix(int(seed) & L.M64) ^ L.mix((int(uid) ^ SPLIT_SALT) & L.M64))


def founder_split(uids, strata, seed: int) -> np.ndarray:
    """8-1 배정: individuals ordered by (stratum, hash(seed, uid)) get first/second alternately, the starting side drawn from the
    world seed — so every stratum (sex × young/adult) is split half-half (odd → hash side) and the whole species too (|n1 − n2| ≤ 1,
    which gives J1 wolf worlds ≥ 1 learned and ≥ 1 rule wolf). Returns bool (True = first)."""
    uids = [int(u) for u in uids]
    n = len(uids)
    order = sorted(range(n), key=lambda i: (int(strata[i]), split_hash(seed, uids[i]), uids[i]))
    start = L.unit(L.mix((int(seed) ^ SPLIT_SALT2) & L.M64)) < 0.5
    out = np.zeros(n, dtype=bool)
    for r, i in enumerate(order):
        out[i] = ((r % 2) == 0) == start
    return out


def respawn_side(stratum_counts: tuple[int, int], all_counts: tuple[int, int], h: float) -> bool:
    """New individual (train respawn) [해석]: the side with fewer alive members of its stratum, then of the species, then hash."""
    a, b = stratum_counts
    if a != b:
        return a < b
    a, b = all_counts
    if a != b:
        return a < b
    return h < 0.5


# --------------------------------------------------------------------------- #
# recorder
# --------------------------------------------------------------------------- #

def _compact(alive_blk: np.ndarray, lo: int) -> tuple[np.ndarray, np.ndarray]:
    """(slots (K, m), valid (K, m)) of the alive slots of one block in slot order (m = batch max, ≥ 1)."""
    n = alive_blk.sum(1)
    m = max(int(n.max()) if len(n) else 0, 1)
    order = np.argsort(~alive_blk, axis=1, kind="stable")[:, :m]
    valid = np.arange(m)[None, :] < n[:, None]
    return order + lo, valid


def _pair_dist(PA, vA, PB, vB, same: bool = False):
    """Distances (K, nA, nB) between two compact sets (inf where invalid; diagonal inf when `same`), and A − B vectors."""
    d = PA[:, :, None, :] - PB[:, None, :, :]
    dist = np.sqrt(d[..., 0] * d[..., 0] + d[..., 1] * d[..., 1])
    ok = vA[:, :, None] & vB[:, None, :]
    if same:
        ok &= ~np.eye(PA.shape[1], dtype=bool)[None]
    return np.where(ok, dist, np.inf), d


def breedable_pair(mature: np.ndarray, sex: np.ndarray, uid: np.ndarray, pa: np.ndarray, pb: np.ndarray) -> bool:
    """8-2 공존 판정의 '번식할 수 있는 쌍' over one species' alive individuals: two mature, sex-compatible (wolves: any two —
    r9_life.mate_compatible), not related (r9_life.related). No distance / quadrant condition [해석 — 문서가 적지 않음]."""
    m = np.asarray(mature, dtype=bool)
    if m.sum() < 2:
        return False
    sx, u, a, b = (np.asarray(x)[m] for x in (sex, uid, pa, pb))
    comp = L.mate_compatible(sx[:, None], sx[None, :])
    rel = L.related(a[:, None], b[:, None], u[:, None], a[None, :], b[None, :], u[None, :])
    return bool(np.triu(comp & ~rel, 1).any())


class Recorder:
    """Per-run observer (see module docstring). `split` = dict(sp=X, group array is created here) for J1/C0-11 accounting.
    scenes=True turns on the 8-3 / 8-4 decision statistics (judge, mixed, scenes, anomaly). traj_worlds: world indices whose
    positions are kept every decision (r9_replay)."""

    ACC_FIELDS = ("r_nb", "r_off", "r_on", "steps", "eaten", "d_bite", "d_counter", "d_starve", "births", "elig", "pairs")

    def __init__(self, w: W.R9World, *, split_sp: int | None = None, scenes: bool = True, pair_every: int = 60,
                 kin_every: int = 10, traj_worlds=(), keep_rewards: bool = False):
        K, S = w.K, w.S
        self.K, self.S, self.Q, self.D = K, S, w.Q, w.D
        self.size = float(w.size)
        self.judge = bool(w.judge)
        self.ssp = w.slot_sp.astype(np.int64)
        self.lo = [int(x) for x in w.sp_lo]
        self.hi = [int(x) for x in w.sp_hi]
        self.scenes = bool(scenes)
        self.pair_every = max(int(pair_every), 1)
        self.kin_every = max(int(kin_every), 1)
        self.t0 = w.t.copy()
        self.start_counts = np.stack([w.alive[:, self.lo[s]:self.hi[s]].sum(1) for s in range(3)], 1).astype(np.int64)
        ff = w.cfg["reward"]["fallback_f"]
        self._f = dict(on=bool(ff["enabled"]), birth=float(ff["birth"]), per=float(ff["condition_total"]) / float(ff["condition_period"]),
                       emin=float(ff["e_min"]), base_birth=float(w.cfg["reward"]["birth"]))
        self._gest = float(w.cfg["body_common"]["breed"]["gestation"])
        self.rng_eval = [np.random.default_rng([int(sd), W.TAG_EVAL]) for sd in w.seeds]
        z = lambda *sh, dt=np.int64: np.zeros(sh, dtype=dt)  # noqa: E731
        # per-decision scratch
        self._dec_alive = w.alive.copy()
        self._dec_uid = w.uid.copy()
        self._done_dec = z(K, S, dt=bool)
        self._dec_gain = z(K, S, dt=np.float64)
        self._dec_cond = z(K, S)
        self._dec_steps = z(K, S)
        self._dec_mating = w.mating.copy()
        self._prev_pc = getattr(w, "_pc", None)
        # population
        self.pop: list[np.ndarray] = []
        self.pop_t: list[int] = []
        self.pair_hist: list[np.ndarray] = []
        self.pair_t: list[int] = []
        self.ehist = z(K, 3, 101)
        self.elig = z(K, 3)
        self.rew_sp = z(K, 3, dt=np.float64)                # Σ reward of decision-start individuals (J1 무리 전체 비교)
        self.steps_sp = z(K, 3)
        self.keep_rewards = bool(keep_rewards)
        self.kept: dict[str, list] = dict(r_off=[], r_on=[], done=[], group=[], alive=[])
        # kills (8-2) and hunts
        self.kills: list[dict] = []
        self._bite_ptr = 0
        self.att = z(K, 2)                                  # old definition (10 units, RUN > 2 decisions): attempts, successes
        nW = self.hi[WOLF] - self.lo[WOLF]
        self.att_n = z(K, nW)
        self.att_kill = z(K, nW, dt=bool)
        self.att_uid = w.uid[:, self.lo[WOLF]:self.hi[WOLF]].copy()
        self.pack_times: dict[tuple[int, int], list[int]] = {}
        # anomaly (8-4) per world
        self.an_corner = z(K, 2)                            # wolf steps (≥ 300 after spawn), in two-wall band
        self.an_edge_stand = z(K, 2)                        # wolf steps, standing within 2 of a shelter edge
        self.an_arena = z(K, 2, 4)                          # [deer, boar] × (steps new, steps other, bites new, bites other)
        self._rflag = z(K, S, dt=bool)
        self._rt = w.resp_t.copy()
        self.an_shield = z(K, 4)                            # deer n, deer within 3 of adult boar, random n, random within
        self.an_fight = z(K, 2)                             # adult boar decisions near a non-approaching wolf, walking toward it
        self.resp_far: list[tuple[int, int, float]] = []    # (k, sp, min distance to other species) far-form respawns (4-6)
        # scenes (8-3) per world
        self.sc_sated = z(K, 6, 2, 2)                       # stratum (dist band × wolf speed band) × (hungry, sated) × fled
        self.sc_pend = z(K, 2, 2, 2)                        # [deer, boar] × mating × fled (wolf within 10)
        self.sc_face = z(K, 2, 3)                           # (young, adult) × (face, flee, other) — wolf within 3 approaching
        self.sc_disp = z(K, 2, 2)                           # (boar arrival, deer arrival) × (stayed, left)
        self.sc_kin = z(K, 3, 2, dt=np.float64)             # nearest kin distance sum, count (sampled)
        G = int(w.G)
        self.G = G
        self.sc_cells = np.zeros((K, 3, G, G)) if self.scenes else None
        self.carc_first: dict[tuple[int, int], float] = {}
        self.carc_bouts: dict[tuple[int, int, int], int] = {}
        self._carc_last: dict[tuple[int, int, int], int] = {}
        self._dp_on = z(K, S, 2, dt=bool)
        self._dp_left = z(K, S, 2)
        self._dp_pos = np.zeros((K, S, 2, 2))
        self._dp_euid = z(K, S, 2)
        self._dp_uid = w.uid.copy()
        self._dp_nb = np.full((K, S), np.inf)
        self._dp_nd = np.full((K, S), np.inf)
        # split (J1 / C0-11)
        self.split_sp = split_sp
        self.group = np.full((K, S), -1, dtype=np.int8)
        self._dec_group = self.group.copy()
        self.acc = np.zeros((K, 3, 2, len(self.ACC_FIELDS)))
        self.pair_combo = z(K, 3, 3)                        # pairs formed: (first×first, first×second, second×second)
        self.birth_combo = z(K, 3, 3)
        self.partner: dict[tuple[int, int], int] = {}
        self.uid_group: list[dict[int, int]] = [dict() for _ in range(K)]
        self.seeds = [int(s) for s in w.seeds]
        if split_sp is not None:
            self._assign_founders(w)
        # trajectories
        self.traj_worlds = [int(k) for k in traj_worlds]
        self.traj = {k: dict(pos=[], alive=[], act=[], uid=[], t=[]) for k in self.traj_worlds}
        self.n_dec = 0
        w.step_hook = self._hook

    # --- split assignment ---------------------------------------------------
    def _stratum(self, w, k: int, s: int) -> int:
        return int(w.sex[k, s]) * 2 + int(bool(w.af[k, s] >= 1.0))

    def _assign_founders(self, w) -> None:
        sp = self.split_sp
        lo, hi = self.lo[sp], self.hi[sp]
        for k in range(self.K):
            sl = np.nonzero(w.alive[k, lo:hi])[0] + lo
            if not len(sl):
                continue
            side = founder_split(w.uid[k, sl], [self._stratum(w, k, int(s)) for s in sl], self.seeds[k])
            for s, f in zip(sl, side):
                g = 0 if f else 1
                self.group[k, s] = g
                self.uid_group[k][int(w.uid[k, s])] = g

    def _assign_new(self, w, k: int, s: int) -> None:
        sp = self.split_sp
        lo, hi = self.lo[sp], self.hi[sp]
        st = self._stratum(w, k, s)
        others = [int(j) for j in np.nonzero(w.alive[k, lo:hi])[0] + lo if int(j) != s]
        cs, ca = [0, 0], [0, 0]
        for j in others:
            g = int(self.group[k, j])
            if g < 0:
                continue
            ca[g] += 1
            if self._stratum(w, k, j) == st:
                cs[g] += 1
        first = respawn_side((cs[0], cs[1]), (ca[0], ca[1]), split_hash(self.seeds[k], int(w.uid[k, s])))
        g = 0 if first else 1
        self.group[k, s] = g
        self.uid_group[k][int(w.uid[k, s])] = g

    def make_split_views(self) -> list[np.ndarray]:
        """Per-world bool arrays shared with the SplitBrain instances (updated in place)."""
        sp = self.split_sp
        lo, hi = self.lo[sp], self.hi[sp]
        self._mask_views = [np.zeros(hi - lo, dtype=bool) for _ in range(self.K)]
        self._sync_masks()
        return self._mask_views

    def _sync_masks(self) -> None:
        if not hasattr(self, "_mask_views"):
            return
        sp = self.split_sp
        lo, hi = self.lo[sp], self.hi[sp]
        for k in range(self.K):
            self._mask_views[k][:] = self.group[k, lo:hi] == 0

    # --- per decision ---------------------------------------------------------
    def before(self, w: W.R9World, a: np.ndarray) -> None:
        self._dec_alive = w.alive.copy()
        self._dec_uid = w.uid.copy()
        self._done_dec[:] = False
        self._dec_gain[:] = 0.0
        self._dec_cond[:] = 0
        self._dec_steps[:] = 0
        self._dec_mating = w.mating.copy()
        self._dec_group = self.group.copy()
        ki, si = np.nonzero(w.alive)
        if len(ki):
            bins = np.clip((w.E[ki, si] * 100.0).astype(np.int64), 0, 100)
            np.add.at(self.ehist, (ki, self.ssp[si], bins), 1)
        for k in self.traj_worlds:
            tr = self.traj[k]
            tr["pos"].append(w.pos[k].astype(np.float32).copy())
            tr["alive"].append(w.alive[k].copy())
            tr["act"].append(a[k].astype(np.int8).copy())
            tr["uid"].append(w.uid[k].copy())
            tr["t"].append(int(w.t[k]))
        self._wolf_decision(w, a)
        if self.scenes:
            self._scene_decision(w, a)

    def _wolf_decision(self, w, a) -> None:
        """Old attempt definition (8-2 '처음 정의', report only) and pack proximity of every alive wolf (8-3 무리 사냥)."""
        lo, hi = self.lo[WOLF], self.hi[WOLF]
        if hi <= lo:
            return
        o = w.obs()
        pres = o[:, lo:hi, B.other_col(0, "present")] > 0.5
        dd = o[:, lo:hi, B.other_col(0, "dist")].astype(np.float64) * float(B.OBS_NORM["pos"])
        aw = a[:, lo:hi]
        run = (aw >= B.RUN_FIRST) & (aw <= B.RUN_LAST)
        alive = w.alive[:, lo:hi]
        cond = alive & pres & (dd <= 10.0) & run
        uid = w.uid[:, lo:hi]
        changed = uid != self.att_uid
        close = (self.att_n > 0) & (~cond | changed)
        if close.any():
            q = close & (self.att_n > 2)
            self.att[:, 0] += q.sum(1)
            self.att[:, 1] += (q & self.att_kill).sum(1)
        self.att_n = np.where(cond & ~changed, self.att_n + 1, np.where(cond, 1, 0))
        self.att_kill = np.where(cond & ~changed, self.att_kill, False)
        self.att_uid = uid.copy()
        # pack: another wolf within 5 units at this decision
        iw, vw = _compact(alive, lo)
        if iw.shape[1] >= 2:
            kk = np.arange(self.K)[:, None]
            dist, _ = _pair_dist(w.pos[kk, iw], vw, w.pos[kk, iw], vw, same=True)
            near = (dist <= 5.0).any(-1) & vw
            for k, i in zip(*np.nonzero(near)):
                self.pack_times.setdefault((int(k), int(w.uid[k, iw[k, i]])), []).append(int(w.t[k]))

    def _scene_decision(self, w, a) -> None:
        K = self.K
        kk = np.arange(K)[:, None]
        P, Hd, Dp, af, E = w.pos, w.head, w.disp, w.af, w.E
        iD, vD = _compact(w.alive[:, self.lo[DEER]:self.hi[DEER]], self.lo[DEER])
        iW, vW = _compact(w.alive[:, self.lo[WOLF]:self.hi[WOLF]], self.lo[WOLF])
        iB, vB = _compact(w.alive[:, self.lo[BOAR]:self.hi[BOAR]], self.lo[BOAR])
        flee_all = np.isin(a, FLEE_ACTIONS)
        run_all = (a >= B.RUN_FIRST) & (a <= B.RUN_LAST)
        if vD.any() and vW.any():
            dist, _ = _pair_dist(P[kk, iD], vD, P[kk, iW], vW)
            j = dist.argmin(-1)
            dmin = np.take_along_axis(dist, j[..., None], -1)[..., 0]
            ws = np.take_along_axis(iW, j, 1)
            wE = E[kk, ws]
            wsp = np.sqrt(Dp[kk, ws, 0] ** 2 + Dp[kk, ws, 1] ** 2)
            fled = flee_all[kk, iD]
            near = vD & (dmin <= 10.0)
            stratum = (dmin >= 5.0).astype(np.int64) * 3 + np.digitize(wsp, [0.03, 0.3])      # [어림] 속력 띠: 서기·걷기·뛰기
            grp = np.where(wE >= 0.8, 1, np.where(wE <= 0.5, 0, -1))
            m = near & (grp >= 0)
            kx = np.broadcast_to(kk, m.shape)
            np.add.at(self.sc_sated, (kx[m], stratum[m], grp[m], fled[m].astype(np.int64)), 1)
            mat = self._dec_mating[kk, iD]
            np.add.at(self.sc_pend, (kx[near], 0, mat[near].astype(np.int64), fled[near].astype(np.int64)), 1)
        if vB.any() and vW.any():
            dist, d = _pair_dist(P[kk, iB], vB, P[kk, iW], vW)            # d = boar − wolf
            j = dist.argmin(-1)
            dmin = np.take_along_axis(dist, j[..., None], -1)[..., 0]
            ws = np.take_along_axis(iW, j, 1)
            dv = np.take_along_axis(d, j[..., None, None].repeat(2, -1), 2)[:, :, 0, :]   # (K, nB, 2) boar − nearest wolf
            u = dv / np.maximum(dmin, W.EPS)[..., None]
            wappr = (Dp[kk, ws, 0] * u[..., 0] + Dp[kk, ws, 1] * u[..., 1]) > float(w.cfg["body_common"]["bite"]["approach_min"])
            hb = Hd[kk, iB]
            front = (-(hb[..., 0] * u[..., 0] + hb[..., 1] * u[..., 1])) >= float(w.cfg["body_common"]["counter"]["cone_cos"])
            run = run_all[kk, iB]
            adult = af[kk, iB] >= 1.0
            cat = np.where(run, 1, np.where(front, 0, 2))
            m = vB & (dmin <= 3.0) & wappr
            kx = np.broadcast_to(kk, m.shape)
            np.add.at(self.sc_face, (kx[m], adult[m].astype(np.int64), cat[m]), 1)
            fled = flee_all[kk, iB]
            near = vB & (dmin <= 10.0)
            mat = self._dec_mating[kk, iB]
            np.add.at(self.sc_pend, (kx[near], 1, mat[near].astype(np.int64), fled[near].astype(np.int64)), 1)
            # 8-4 늘 싸움: adult boar, wolf within 10 [어림] not approaching, WALK toward it (cos ≥ 0.92 ≈ ±23°) [어림]
            ab = a[kk, iB]
            jw = B.action_dir_index(ab)
            walk = (ab >= B.WALK_FIRST) & (ab <= B.WALK_LAST)
            dirv = B.rotate(hb, B.DIR8[np.clip(jw, 0, 7)])
            toward = walk & ((-(dirv[..., 0] * u[..., 0] + dirv[..., 1] * u[..., 1])) >= 0.92)
            mf = vB & adult & (dmin <= 10.0) & ~wappr
            self.an_fight[:, 0] += mf.sum(1)
            self.an_fight[:, 1] += (mf & toward).sum(1)
        # 8-4 방패: deer within 3 of an adult boar vs the same number of random points (eval RNG per world)
        ad = w.alive[:, self.lo[BOAR]:self.hi[BOAR]] & (af[:, self.lo[BOAR]:self.hi[BOAR]] >= 1.0)
        iA, vA = _compact(ad, self.lo[BOAR])
        nd = vD.sum(1)
        if vD.any():
            if vA.any():
                dist, _ = _pair_dist(P[kk, iD], vD, P[kk, iA], vA)
                within = ((dist <= 3.0).any(-1) & vD).sum(1)
            else:
                within = np.zeros(K, dtype=np.int64)
            self.an_shield[:, 0] += nd
            self.an_shield[:, 1] += within
            for k in range(K):
                n = int(nd[k])
                pts = self.rng_eval[k].uniform(0.0, self.size, (n, 2))
                self.an_shield[k, 2] += n
                if n and vA[k].any():
                    bp = P[k, iA[k, vA[k]]]
                    dx = pts[:, None, 0] - bp[None, :, 0]
                    dy = pts[:, None, 1] - bp[None, :, 1]
                    self.an_shield[k, 3] += int(((dx * dx + dy * dy) <= 9.0).any(1).sum())
        self._displacement(w)

    def _displacement(self, w) -> None:
        """8-3 자리 나눔 [해석]: a deer whose last decision was EAT gets a newcomer — nearest boar (or, baseline, nearest other
        deer) crosses from > 2 to ≤ 2 units between decisions; it 'left' if it moved ≥ 1 unit [어림] within the next 4 steps."""
        pc = w._pc
        K, S = self.K, self.S
        ic, valid, dist, pair = pc["ic"], pc["valid"], pc["dist"], pc["pair"]
        spg = self.ssp[ic]
        deer_r = valid & (spg == DEER)
        db = np.where(pair & (valid & (spg == BOAR))[:, None, :], dist, np.inf).min(-1)
        ddd = np.where(pair & (valid & (spg == DEER))[:, None, :], dist, np.inf).min(-1)
        nb = np.full((K, S), np.inf)
        nd = np.full((K, S), np.inf)
        ki, ii = np.nonzero(deer_r)
        nb[ki, ic[ki, ii]] = db[ki, ii]
        nd[ki, ic[ki, ii]] = ddd[ki, ii]
        # resolve pending
        on = self._dp_on
        if on.any():
            self._dp_left = np.where(on, self._dp_left - 1, self._dp_left)
            due = on & (self._dp_left <= 0)
            for k, s, typ in zip(*np.nonzero(due)):
                if w.alive[k, s] and w.uid[k, s] == self._dp_euid[k, s, typ]:
                    mv = w.pos[k, s] - self._dp_pos[k, s, typ]
                    left = int(math.sqrt(mv[0] * mv[0] + mv[1] * mv[1]) >= 1.0)
                    self.sc_disp[k, typ, left] += 1
            self._dp_on &= ~due
        same_ind = (w.uid == self._dp_uid) & w.alive
        eat_prev = w.act == B.EAT
        for typ, cur, prev in ((0, nb, self._dp_nb), (1, nd, self._dp_nd)):
            ev = same_ind & (prev > 2.0) & (cur <= 2.0) & eat_prev & ~self._dp_on[..., typ]
            if ev.any():
                self._dp_on[..., typ] |= ev
                self._dp_left[..., typ] = np.where(ev, 2, self._dp_left[..., typ])
                self._dp_pos[:, :, typ, :] = np.where(ev[..., None], w.pos, self._dp_pos[:, :, typ, :])
                self._dp_euid[..., typ] = np.where(ev, w.uid, self._dp_euid[..., typ])
        self._dp_nb, self._dp_nd, self._dp_uid = nb, nd, w.uid.copy()
        if self.n_dec % self.kin_every == 0:
            kd = np.where(pair & pc["same"], dist, np.inf).min(-1)
            for sp in (DEER, BOAR):
                m = valid & (spg == sp) & np.isfinite(kd)
                self.sc_kin[:, sp, 0] += np.where(m, kd, 0.0).sum(1)
                self.sc_kin[:, sp, 1] += m.sum(1)

    def after(self, w: W.R9World, a, rew, done, info) -> None:
        K, Q = self.K, self.Q
        ka, sa = np.nonzero(self._dec_alive)
        if len(ka):
            np.add.at(self.rew_sp, (ka, self.ssp[sa]), np.asarray(rew)[ka, sa])
            np.add.at(self.steps_sp, (ka, self.ssp[sa]), self._dec_steps[ka, sa])
        ki, si = np.nonzero(w.alive)
        cnt = np.bincount((ki * Q + w.quad[ki, si].astype(np.int64)) * 3 + self.ssp[si], minlength=K * Q * 3)
        self.pop.append(cnt.reshape(K, Q, 3).astype(np.int16))
        self.pop_t.append(int(self.n_dec + 1) * self.D)
        if ((self.n_dec + 1) * self.D) % self.pair_every < self.D:
            self.pair_hist.append(self.breedable_now(w))
            self.pair_t.append(int(self.n_dec + 1) * self.D)
        if self.split_sp is not None:
            self._split_after(w, rew, done, info)
        self.n_dec += 1

    def _split_after(self, w, rew, done, info) -> None:
        g = self._dec_group
        births = np.asarray(info["births"], dtype=np.float64)
        f = self._f
        cur_birth = f["birth"] if f["on"] else f["base_birth"]
        cur_cond = f["per"] * self._dec_cond if f["on"] else 0.0
        base = rew - cur_birth * births - cur_cond
        r_off = base + f["base_birth"] * births
        r_on = base + f["birth"] * births + f["per"] * self._dec_cond
        cause = np.asarray(info["dead_cause"])
        m = self._dec_alive & (g >= 0)
        ki, si = np.nonzero(m)
        if len(ki):
            sp = self.ssp[si]
            gg = g[ki, si].astype(np.int64)
            vals = dict(r_nb=base, r_off=r_off, r_on=r_on, steps=self._dec_steps, eaten=self._dec_gain,
                        d_bite=done & (cause == W.CAUSE_BITE), d_counter=done & (cause == W.CAUSE_COUNTER),
                        d_starve=done & (cause == W.CAUSE_STARVE), births=births)
            for fi, nm in enumerate(self.ACC_FIELDS):
                if nm in vals:
                    np.add.at(self.acc[:, :, :, fi], (ki, sp, gg), np.asarray(vals[nm], dtype=np.float64)[ki, si])
        resp = np.asarray(info["respawned"], dtype=bool)
        sp = self.split_sp
        lo, hi = self.lo[sp], self.hi[sp]
        if self.keep_rewards:
            self.kept["r_off"].append(r_off[:, lo:hi].astype(np.float32))
            self.kept["r_on"].append(r_on[:, lo:hi].astype(np.float32))
            self.kept["done"].append(np.asarray(done)[:, lo:hi].copy())
            self.kept["group"].append(g[:, lo:hi].copy())
            self.kept["alive"].append(self._dec_alive[:, lo:hi].copy())
        for k, s in zip(*np.nonzero(resp[:, lo:hi])):
            s = int(s) + lo
            self.group[k, s] = -1
            self._assign_new(w, int(k), s)
        self._sync_masks()

    def breedable_now(self, w) -> np.ndarray:
        """(K, 3) bool: species has a breedable pair now (8-2 공존)."""
        out = np.zeros((self.K, 3), dtype=bool)
        cap = int(w.rules.generation_cap)
        for k in range(self.K):
            for sp in range(3):
                lo, hi = self.lo[sp], self.hi[sp]
                m = w.alive[k, lo:hi] & (w.af[k, lo:hi] >= 1.0) & (w.generation[k, lo:hi] < cap)
                if m.sum() < 2:
                    continue
                out[k, sp] = breedable_pair(m, w.sex[k, lo:hi], w.uid[k, lo:hi], w.parent_a[k, lo:hi], w.parent_b[k, lo:hi])
        return out

    # --- per step (world step_hook) ------------------------------------------
    def _hook(self, w: W.R9World, dead: np.ndarray, extra: dict) -> None:
        t_step = w.t - 1
        newborn = np.asarray(extra["newborn"], dtype=bool)
        resp = np.asarray(extra["respawned"], dtype=bool)
        births = np.asarray(extra["births"])
        surv = w.alive & ~dead & ~newborn
        alive0 = surv | dead
        orig = self._dec_alive & ~self._done_dec
        gu = w._gain_u
        epu = w.sb["e_per_unit"]
        gain_e = gu[..., 0] * epu[..., 0] + gu[..., 1] * epu[..., 1] + gu[..., 2] * epu[..., 2]
        self._dec_gain += np.where(orig, gain_e, 0.0)
        self._dec_cond += orig & ~dead & w.mature & (w.E >= self._f["emin"])
        self._dec_steps += orig
        elig = L.can_parent(w, w.rules) & surv
        for s in range(3):
            self.elig[:, s] += elig[:, self.lo[s]:self.hi[s]].sum(1)
        if self.split_sp is not None:
            m = elig & orig & (self._dec_group >= 0)
            ki, si = np.nonzero(m)
            if len(ki):
                np.add.at(self.acc[:, :, :, self.ACC_FIELDS.index("elig")], (ki, self.ssp[si], self._dec_group[ki, si].astype(np.int64)), 1.0)
            self._split_pairs(w, dead, births, t_step)
        self._done_dec |= dead
        ev = w.events["bites"]
        while self._bite_ptr < len(ev):
            e = ev[self._bite_ptr]
            self._bite_ptr += 1
            if e["outcome"] == "kill":
                self._kill_row(w, e, dead)
        # 8-4 wolves: corner band (≥ 300 steps after (re)spawn), standing within 2 of a shelter edge
        lo, hi = self.lo[WOLF], self.hi[WOLF]
        if hi > lo:
            aw = surv[:, lo:hi]
            Pw = w.pos[:, lo:hi]
            sz = self.size
            nx = (Pw[..., 0] < WALL_BAND) | (Pw[..., 0] > sz - WALL_BAND)
            ny = (Pw[..., 1] < WALL_BAND) | (Pw[..., 1] > sz - WALL_BAND)
            m = aw & ((t_step[:, None] - w.resp_t[:, lo:hi]) >= RESPAWN_EXCLUDE)
            self.an_corner[:, 0] += m.sum(1)
            self.an_corner[:, 1] += (m & nx & ny).sum(1)
            spd = np.sqrt(w.disp[:, lo:hi, 0] ** 2 + w.disp[:, lo:hi, 1] ** 2)
            self.an_edge_stand[:, 0] += aw.sum(1)
            self.an_edge_stand[:, 1] += (aw & (w._edge1[:, lo:hi] <= 2.0) & (spd < 0.03)).sum(1)
        # 8-4 무대 악용 (train world)
        if not self.judge:
            for i, sp in enumerate((DEER, BOAR)):
                sl = slice(self.lo[sp], self.hi[sp])
                a0 = alive0[:, sl]
                new = a0 & self._rflag[:, sl] & ((t_step[:, None] - self._rt[:, sl]) < ARENA_WINDOW)
                bit = dead[:, sl] & (w.dead_cause[:, sl] == W.CAUSE_BITE)
                self.an_arena[:, i, 0] += new.sum(1)
                self.an_arena[:, i, 1] += (a0 & ~new).sum(1)
                self.an_arena[:, i, 2] += (bit & new).sum(1)
                self.an_arena[:, i, 3] += (bit & ~new).sum(1)
            if resp.any():
                self._rflag = np.where(resp, True, self._rflag)
                self._rt = np.where(resp, w.resp_t, self._rt)
                form = getattr(w, "_resp_form", None)
                for k, s in zip(*np.nonzero(resp)):
                    if form is not None and int(form[k, s]) != W.RESP_FAR:
                        continue
                    sp = int(self.ssp[s])
                    om = w.alive[k] & (self.ssp != sp)
                    if om.any():
                        d = w.pos[k][om] - w.pos[k, s]
                        self.resp_far.append((int(k), sp, float(np.sqrt(d[:, 0] ** 2 + d[:, 1] ** 2).min())))
        if self.scenes:
            self._scene_step(w, surv, t_step)
        self._prev_pc = w._pc

    def _split_pairs(self, w, dead, births, t_step) -> None:
        Lf = w.life
        new = Lf.pair_on & (Lf.pair_due == (t_step.astype(np.float64) + self._gest)[:, None])
        for k, p in zip(*np.nonzero(new)):
            sp = int(Lf.pair_sp[k, p])
            if sp != self.split_sp:
                continue
            ua, ub = int(Lf.pair_ua[k, p]), int(Lf.pair_ub[k, p])
            self.partner[(int(k), ua)] = ub
            self.partner[(int(k), ub)] = ua
            ga, gb = self.uid_group[k].get(ua, -1), self.uid_group[k].get(ub, -1)
            if ga >= 0 and gb >= 0:
                self.pair_combo[k, sp, ga + gb] += 1
                fi = self.ACC_FIELDS.index("pairs")
                self.acc[k, sp, ga, fi] += 1
                self.acc[k, sp, gb, fi] += 1
        for k, s in zip(*np.nonzero(births > 0)):
            sp = int(self.ssp[s])
            if sp != self.split_sp:
                continue
            uid = int(self._dec_uid[k, s]) if dead[k, s] else int(w.uid[k, s])
            pu = self.partner.get((int(k), uid))
            if pu is None or uid > pu:
                continue
            ga, gb = self.uid_group[k].get(uid, -1), self.uid_group[k].get(pu, -1)
            if ga >= 0 and gb >= 0:
                self.birth_combo[k, sp, ga + gb] += int(births[k, s])

    def _kill_row(self, w, e: dict, dead: np.ndarray) -> None:
        k = int(e["k"])
        wu = int(e["wolf_uid"])
        lo, hi = self.lo[WOLF], self.hi[WOLF]
        wsl = np.nonzero(w.uid[k, lo:hi] == wu)[0]
        seen = [0, 0, 0]
        if len(wsl):
            ws = int(wsl[0]) + lo
            if self.att_n[k, ws - lo] > 0:
                self.att_kill[k, ws - lo] = True
            pc = self._prev_pc
            if pc is not None:
                gi = np.nonzero(pc["valid"][k] & (pc["ic"][k] == ws))[0]
                if len(gi):
                    row = pc["perc"][k, gi[0]] & pc["valid"][k]
                    seen = np.bincount(self.ssp[pc["ic"][k][row]], minlength=3).tolist()
        share = float("nan")
        if int(e["prey_sp"]) == BOAR:
            blo, bhi = self.lo[BOAR], self.hi[BOAR]
            m = w.alive[k, blo:bhi] & ~dead[k, blo:bhi] & (w.quad[k, blo:bhi] == int(e["quad"]))
            juv = int((m & (w.af[k, blo:bhi] < 1.0)).sum()) + int(float(e["prey_af"]) < 1.0)
            share = juv / float(int(m.sum()) + 1)
        self.kills.append(dict(k=k, t=int(e["t"]), wolf_uid=wu, prey_uid=int(e["prey_uid"]), prey_sp=int(e["prey_sp"]),
                               prey_af=float(e["prey_af"]), quad=int(e["quad"]), wolf_E=float(e["wolf_E"]),
                               wolf_act=int(e["wolf_act"]), seen=seen, juv_share=share))

    def _scene_step(self, w, surv, t_step) -> None:
        gu = w._gain_u
        G = self.G
        K = self.K
        g = gu[..., B.GRASS]
        m = surv & (g > 0.0)
        if m.any():
            ki, si = np.nonzero(m)
            ix, iy = W._cells(w.pos[ki, si], w.cell, G)
            idx = ((ki * 3 + self.ssp[si]) * G + iy) * G + ix
            self.sc_cells += np.bincount(idx, weights=g[ki, si], minlength=K * 3 * G * G).reshape(K, 3, G, G)
        mm = surv & (gu[..., B.MEAT] > 0.0)
        if mm.any():
            er = float(w.cfg["body_common"]["carcass"]["eat_r"]) + 1e-9
            for k, s in zip(*np.nonzero(mm)):
                ok = w.carc_uid[k] != 0
                if not ok.any():
                    continue
                d = w.carc_pos[k] - w.pos[k, s]
                dd = np.where(ok & (w.carc_kin[k] != w.kin_id[k, s]), np.sqrt(d[:, 0] ** 2 + d[:, 1] ** 2), np.inf)
                c = int(dd.argmin())
                if dd[c] > er:
                    continue
                cu = int(w.carc_uid[k, c])
                if int(self.ssp[s]) == WOLF:
                    self.carc_first.setdefault((int(k), cu), float(t_step[k] - w.carc_t[k, c]))
                    key = (int(k), int(w.uid[k, s]), cu)
                    last = self._carc_last.get(key)
                    if last is None or int(t_step[k]) - last > 30:            # [어림] 30 스텝 넘게 끊기면 새 먹기
                        self.carc_bouts[key] = self.carc_bouts.get(key, 0) + 1
                    self._carc_last[key] = int(t_step[k])

    # --- end of run ------------------------------------------------------------
    def finish(self, w: W.R9World) -> dict:
        w.flush_hunts()
        close = self.att_n > 2
        self.att[:, 0] += close.sum(1)
        self.att[:, 1] += (close & self.att_kill).sum(1)
        hunts = []
        for h in w.events["hunts"]:
            tt = self.pack_times.get((int(h["k"]), int(h["wolf_uid"])), [])
            i = bisect.bisect_left(tt, int(h["t0"]))
            hh = dict(h)
            hh["pack"] = bool(i < len(tt) and tt[i] <= int(h["t1"]))
            hunts.append(hh)
        G = self.G
        em = float(w.cfg["body_common"]["eat_min"])
        food = np.zeros((self.K, 4))
        for k in range(self.K):
            for j, (f, cap) in enumerate(((w.grass[k], w.grass_cap[k]), (w.root[k], w.root_cap[k]))):
                food[k, j] = float(f.mean())
                cm = cap > em
                food[k, 2 + j] = float((f[cm] < em).mean()) if cm.any() else float("nan")    # [해석] 바닥 난 셀 = 용량 > 0.06 인 셀 중 < 0.06
        lf = L.life_stats(w.life)
        rec = dict(
            mode=w.mode, K=self.K, Q=self.Q, D=self.D, size=self.size, G=G, steps=int(self.n_dec * self.D),
            seeds=list(self.seeds), start_counts=self.start_counts, world_params=[w.world_params(k) for k in range(self.K)],
            st=w.stats_snapshot(), life={k: np.asarray(lf[k]) for k in ("opportunities", "paired", "births", "blocked", "blocked_once", "failed", "cancelled")},
            pop=np.stack(self.pop, 0) if self.pop else np.zeros((0, self.K, self.Q, 3), np.int16),
            pop_t=np.asarray(self.pop_t, dtype=np.int64),
            pair_hist=np.stack(self.pair_hist, 0) if self.pair_hist else np.zeros((0, self.K, 3), bool),
            pair_t=np.asarray(self.pair_t, dtype=np.int64), final_pair=self.breedable_now(w), food_end=food,
            ehist=self.ehist, elig=self.elig, kills=self.kills, hunts=hunts,
            deaths=[dict(d) for d in w.events["deaths"]], births=[dict(b) for b in w.events["births"]],
            respawns=len(w.events["respawns"]), att=self.att,
            boar_bites=self._boar_bites(w), rew_sp=self.rew_sp, steps_sp=self.steps_sp,
            kept={n: (np.stack(v, 0) if v else None) for n, v in self.kept.items()},
            counters=dict(near_carcass=int(sum(1 for b in w.events["bites"] if b["outcome"] == "counter" and b["near_carcass"])),
                          hunting=int(sum(1 for b in w.events["bites"] if b["outcome"] == "counter" and not b["near_carcass"]))),
            an_corner=self.an_corner, an_edge_stand=self.an_edge_stand, an_arena=self.an_arena, an_shield=self.an_shield,
            an_fight=self.an_fight, resp_far=list(self.resp_far),
            sc_sated=self.sc_sated, sc_pend=self.sc_pend, sc_face=self.sc_face, sc_disp=self.sc_disp, sc_kin=self.sc_kin,
            sc_cells_pianka=self._cell_pianka(),
            carc_first=list(self.carc_first.values()), carc_returns=int(sum(max(0, v - 1) for v in self.carc_bouts.values())),
            carc_wolf_eats=len(self.carc_bouts),
            split_sp=self.split_sp, acc=self.acc, pair_combo=self.pair_combo, birth_combo=self.birth_combo,
            uid_group=[dict(d) for d in self.uid_group],
            band_share=band_shares(w),
            traj={k: {n: np.asarray(v) for n, v in tr.items()} for k, tr in self.traj.items()},
            cov=[(w.cov_c[k][w.cov_ok[k]].copy(), w.cov_r[k][w.cov_ok[k]].copy()) for k in self.traj_worlds],
            grass_cap=[w.grass_cap[k].copy() for k in self.traj_worlds],
        )
        return rec

    def _boar_bites(self, w) -> np.ndarray:
        """(K, 2 young/adult, 3 outcome kill/wound/counter) bites on boar (C0-3)."""
        out = np.zeros((self.K, 2, 3), dtype=np.int64)
        code = {n: i for i, n in enumerate(W.BITE_NAMES)}
        for b in w.events["bites"]:
            if int(b["prey_sp"]) == BOAR:
                out[int(b["k"]), int(float(b["prey_af"]) >= 1.0), code[b["outcome"]]] += 1
        return out

    def _cell_pianka(self) -> np.ndarray:
        """Per-world Pianka overlap of deer and boar grass-cell use (8-3, report only)."""
        out = np.full(self.K, np.nan)
        if self.sc_cells is None:
            return out
        for k in range(self.K):
            p = self.sc_cells[k, DEER].reshape(-1)
            q = self.sc_cells[k, BOAR].reshape(-1)
            if p.sum() > 0 and q.sum() > 0:
                out[k] = pianka(p / p.sum(), q / q.sum())
        return out


def band_shares(w) -> dict:
    """Area shares (stage fraction) of the 8-4 bands: wall band (4 units) and the 3-unit shelter-edge band (grid 0.5 units [어림])."""
    s = float(w.size)
    wall = 1.0 - ((s - 2 * WALL_BAND) / s) ** 2
    g = np.arange(0.25, s, 0.5)
    X, Y = np.meshgrid(g, g)
    pts = np.stack([X.reshape(-1), Y.reshape(-1)], 1)
    edge = np.zeros(w.K)
    for k in range(w.K):
        ok = w.cov_ok[k]
        if not ok.any():
            continue
        c, r = w.cov_c[k][ok], w.cov_r[k][ok]
        d = np.sqrt(((pts[:, None, :] - c[None]) ** 2).sum(-1)) - r[None]
        e = d.min(1)
        edge[k] = float(((e > 0.0) & (e <= 3.0)).mean())
    return dict(wall=wall, edge=edge)


def pianka(p: np.ndarray, q: np.ndarray) -> float:
    """Pianka (1973) overlap Σ p q / sqrt(Σ p² Σ q²)."""
    p, q = np.asarray(p, dtype=np.float64), np.asarray(q, dtype=np.float64)
    den = math.sqrt(float((p * p).sum()) * float((q * q).sum()))
    return float((p * q).sum()) / den if den > 0 else float("nan")


# --------------------------------------------------------------------------- #
# running
# --------------------------------------------------------------------------- #

def run(cfg: dict, seeds, steps: int, ctrl_fn: Callable[[int, int, int], BR.Controller | None], *, counts=None,
        split: dict | None = None, scenes: bool = True, chunk: int | None = None, pair_every: int = 60, traj_worlds=(),
        progress: str | None = None, keep_rewards: bool = False, on_decision: Callable | None = None) -> dict:
    """Run worlds `seeds` for `steps` steps (decisions = steps // 2) with controllers ctrl_fn(k, sp, seed) and return the merged
    record. split = dict(sp, first, second, stochastic) → species sp is a SplitBrain herd (J1 / C0-11). chunk = worlds per batch
    (per-world results do not depend on it — world RNG per world, eval RNG per world, same-shape brain blocks)."""
    seeds = [int(s) for s in seeds]
    cnt = None if counts is None else np.asarray(counts, dtype=np.int64).reshape(len(seeds), 3)
    chunk = len(seeds) if not chunk else int(chunk)
    recs = []
    t0 = time.time()
    for c0 in range(0, len(seeds), chunk):
        sd = seeds[c0:c0 + chunk]
        w = W.R9World(cfg, sd, counts=None if cnt is None else cnt[c0:c0 + chunk], record=True)
        rec = Recorder(w, split_sp=None if split is None else int(split["sp"]), scenes=scenes, pair_every=pair_every,
                       traj_worlds=[k - c0 for k in traj_worlds if c0 <= k < c0 + len(sd)], keep_rewards=keep_rewards)
        views = rec.make_split_views() if split is not None else None
        for k in range(w.K):
            for sp in range(3):
                if split is not None and sp == int(split["sp"]):
                    sb = SplitBrain(name=f"split:{split['first'].name}|{split['second'].name}", kind="split", species=sp,
                                    n_state=int(split["first"].n_state) + int(split["second"].n_state),
                                    first=split["first"], second=split["second"], mask=views[k])
                    w.set_controller(k, sp, ctrl(sb, bool(split.get("stochastic", False)), label="split"))
                    continue
                w.set_controller(k, sp, ctrl_fn(c0 + k, sp, sd[k]))
        n_dec = int(steps) // w.D
        for d in range(n_dec):
            a = w.decide()
            rec.before(w, a)
            if on_decision is not None:
                on_decision(w, rec, a, c0)
            obs, rew, done, info = w.step(a)
            rec.after(w, a, rew, done, info)
            if progress and (d + 1) % max(1, n_dec // 10) == 0:
                print(f"  [{progress}] 세계 {c0}~{c0 + len(sd) - 1} 결정 {d + 1}/{n_dec} ({time.time() - t0:.0f}s)", flush=True)
        recs.append(rec.finish(w))
    return merge_records(recs)


def merge_records(recs: list[dict]) -> dict:
    """Concatenate chunk records along the world axis (events get their world index shifted)."""
    if len(recs) == 1:
        return recs[0]
    out = dict(recs[0])
    off = np.cumsum([0] + [r["K"] for r in recs[:-1]])
    out["K"] = int(sum(r["K"] for r in recs))
    cat0 = ("start_counts", "final_pair", "food_end", "ehist", "elig", "att", "boar_bites", "rew_sp", "steps_sp", "an_corner", "an_edge_stand", "an_arena", "an_shield",
            "an_fight", "sc_sated", "sc_pend", "sc_face", "sc_disp", "sc_kin", "sc_cells_pianka", "acc", "pair_combo", "birth_combo")
    for n in cat0:
        out[n] = np.concatenate([r[n] for r in recs], 0)
    for n in ("pop", "pair_hist"):
        out[n] = np.concatenate([r[n] for r in recs], 1)
    out["st"] = {n: np.concatenate([r["st"][n] for r in recs], 0) for n in recs[0]["st"]}
    out["life"] = {n: np.concatenate([r["life"][n] for r in recs], 0) for n in recs[0]["life"]}
    out["band_share"] = dict(wall=recs[0]["band_share"]["wall"], edge=np.concatenate([r["band_share"]["edge"] for r in recs]))
    for n in ("kills", "hunts", "deaths", "births"):
        out[n] = [dict(e, k=int(e["k"]) + int(o)) for r, o in zip(recs, off) for e in r[n]]
    out["resp_far"] = [(int(k) + int(o), sp, d) for r, o in zip(recs, off) for (k, sp, d) in r["resp_far"]]
    for n in ("seeds", "world_params", "carc_first", "uid_group"):
        out[n] = [x for r in recs for x in r[n]]
    for n in ("respawns", "carc_returns", "carc_wolf_eats"):
        out[n] = int(sum(r[n] for r in recs))
    out["counters"] = {n: int(sum(r["counters"][n] for r in recs)) for n in recs[0]["counters"]}
    out["kept"] = {n: (np.concatenate([r["kept"][n] for r in recs], 1) if recs[0]["kept"][n] is not None else None)
                   for n in recs[0]["kept"]}
    tr, cov, gc = {}, [], []
    for r, o in zip(recs, off):
        for k, v in r["traj"].items():
            tr[int(k) + int(o)] = v
        cov += r["cov"]
        gc += r["grass_cap"]
    out["traj"], out["cov"], out["grass_cap"] = tr, cov, gc
    return out


# --------------------------------------------------------------------------- #
# metrics (pure functions of the record)
# --------------------------------------------------------------------------- #

def hunt_stats(hunts: list[dict], kills: list[dict], K: int, min_close: int = W.HUNT_MIN_DECISIONS) -> dict:
    """8-2 사냥 시도·성공률. Segments = recorded approach segments with more than `min_close` closing decisions. Every kill is
    credited to its wolf's segment OPEN at the bite step (t0 ≤ t ≤ t1; same target first, else the latest started) [해석]. A kill
    with no open qualifying segment (short or no approach) is counted as one extra segment that succeeded, so every kill is a
    success and success ≤ segments [해석]. Per-world arrays (K,) for the bootstrap."""
    seg = [h for h in hunts if int(h["n_close"]) > min_close]
    by_wolf: dict[tuple[int, int], list[int]] = {}
    for i, h in enumerate(seg):
        by_wolf.setdefault((int(h["k"]), int(h["wolf_uid"])), []).append(i)
    succ = np.zeros(len(seg), dtype=bool)
    z = lambda: np.zeros(K)  # noqa: E731
    n_seg, n_succ, n_short, n_kill, n_walk, n_ran, n_pack, n_walk_seg = z(), z(), z(), z(), z(), z(), z(), z()
    for h in seg:
        n_seg[int(h["k"])] += 1
        n_ran[int(h["k"])] += bool(h.get("ran", False))
        n_pack[int(h["k"])] += bool(h.get("pack", False))
    for e in kills:
        k = int(e["k"])
        n_kill[k] += 1
        ran = B.RUN_FIRST <= int(e.get("wolf_act", -1)) <= B.RUN_LAST
        n_walk[k] += not ran
        cand = [i for i in by_wolf.get((k, int(e["wolf_uid"])), []) if int(seg[i]["t0"]) <= int(e["t"]) <= int(seg[i]["t1"])]
        if cand:
            # order-independent choice (event lists are interleaved differently when worlds run in chunks)
            same = [i for i in cand if int(seg[i]["target_uid"]) == int(e["prey_uid"])]
            key = lambda j: (int(seg[j]["t0"]), int(seg[j]["target_uid"]), int(seg[j]["t1"]))  # noqa: E731
            i = max(same, key=key) if same else max(cand, key=key)
            succ[i] = True
        else:
            n_short[k] += 1
    for i, h in enumerate(seg):
        if succ[i]:
            n_succ[int(h["k"])] += 1
            n_walk_seg[int(h["k"])] += not bool(h.get("ran", False))
    return dict(segments=n_seg + n_short, successes=n_succ + n_short, qualifying=n_seg, short_kills=n_short, kills=n_kill,
                walk_kills=n_walk, ran_segments=n_ran, pack_segments=n_pack, walk_success_segments=n_walk_seg)


def hunt_episodes(hunts: list[dict], kills: list[dict], K: int, min_close: int = W.HUNT_MIN_DECISIONS) -> dict:
    """Report-only variant [해석 — 확인 필요]: one wolf charging a herd closes on many individuals at once and the per-target
    definition (8-2) counts each as an attempt. Here qualifying per-target segments of the same wolf whose intervals overlap are
    merged into one episode; an episode succeeds if that wolf killed inside it; kills outside every episode add one successful
    episode (same rule as hunt_stats). Per-world arrays."""
    seg = [h for h in hunts if int(h["n_close"]) > min_close]
    by_wolf: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for h in seg:
        by_wolf.setdefault((int(h["k"]), int(h["wolf_uid"])), []).append((int(h["t0"]), int(h["t1"])))
    eps: dict[tuple[int, int], list[list]] = {}
    for key, iv in by_wolf.items():
        iv.sort()
        out = []
        for a, b in iv:
            if out and a <= out[-1][1]:
                out[-1][1] = max(out[-1][1], b)
            else:
                out.append([a, b, False])
        eps[key] = out
    n_ep, n_succ, n_extra = np.zeros(K), np.zeros(K), np.zeros(K)
    for (k, _u), out in eps.items():
        n_ep[k] += len(out)
    for e in kills:
        k = int(e["k"])
        hit = False
        for ep in eps.get((k, int(e["wolf_uid"])), []):
            if ep[0] <= int(e["t"]) <= ep[1]:
                ep[2] = True
                hit = True
                break
        if not hit:
            n_extra[k] += 1
    for (k, _u), out in eps.items():
        n_succ[k] += sum(1 for ep in out if ep[2])
    return dict(episodes=n_ep + n_extra, successes=n_succ + n_extra)


def juvenile_index(kills: list[dict], K: int) -> dict:
    """8-2 멧돼지 새끼 고르기 지수 = (잡힌 멧돼지 중 새끼 몫) ÷ (잡힐 때마다 그 사분면 멧돼지 중 새끼 몫의 평균) = Σ is_young / Σ share
    (pooled over kills). Per-world sums for the bootstrap."""
    n, juv, share = np.zeros(K), np.zeros(K), np.zeros(K)
    for e in kills:
        if int(e["prey_sp"]) != BOAR:
            continue
        k = int(e["k"])
        n[k] += 1
        juv[k] += float(e["prey_af"]) < 1.0
        share[k] += float(e["juv_share"])
    return dict(n=n, young=juv, share=share)


def km_median(times: np.ndarray, event: np.ndarray) -> float:
    """Kaplan–Meier median of event times with right censoring (8-2 첫 멸종 시각). inf when the curve stays above 0.5."""
    t = np.asarray(times, dtype=np.float64)
    e = np.asarray(event, dtype=bool)
    if not len(t):
        return float("nan")
    s = 1.0
    for u in np.unique(t[e]):
        at_risk = float((t >= u).sum())
        d = float(((t == u) & e).sum())
        s *= 1.0 - d / at_risk
        if s <= 0.5:
            return float(u)
    return float("inf")


def block_share(life: dict, block_def: str | None = None) -> dict:
    """8-2 막힘 몫 per world and species: content-cap blocks / (content blocks + pairs made); food budget apart.
    block_def 'scan' (8-2 문장 그대로, 기본) counts every blocked 5 s scan; 'once' uses r9_life `blocked_once` (a scan-time block
    once per pending pair / per run of capped scans — report-only alternative, DEFS)."""
    bd = DEFS["block"] if block_def is None else block_def
    key = "blocked_once" if bd == "once" and "blocked_once" in life else "blocked"
    bl = np.asarray(life[key])                                         # (K, Q, 3, 5)
    content = bl[..., list(L.CONTENT_BLOCKS)].sum(-1).sum(1)           # (K, 3)
    paired = np.asarray(life["paired"]).sum(1)                         # (K, 3)
    food = bl[..., L.BLOCK_FOOD].sum(1)
    by_reason = bl.sum((0, 1))                                         # (3, 5)
    return dict(content=content, paired=paired, food=food, by_reason=by_reason)


def lag_corr(x: np.ndarray, y: np.ndarray, max_lag: int) -> int | None:
    """Lag (in samples) maximising corr(x[t], y[t + lag]) — 'wolves follow prey' is a positive lag of wolves behind prey."""
    x = np.asarray(x, dtype=np.float64) - np.mean(x)
    y = np.asarray(y, dtype=np.float64) - np.mean(y)
    if x.std() <= 0 or y.std() <= 0:
        return None
    best, bl = -np.inf, 0
    n = len(x)
    for lag in range(-max_lag, max_lag + 1):
        a, b = (x[:n - lag], y[lag:]) if lag >= 0 else (x[-lag:], y[:n + lag])
        if len(a) < 3 or a.std() <= 0 or b.std() <= 0:
            continue
        c = float(np.corrcoef(a, b)[0, 1])
        if c > best:
            best, bl = c, lag
    return int(bl)


def logistic_slope(x: np.ndarray, y: np.ndarray, iters: int = 50) -> float:
    """Newton logistic regression y ~ b0 + b1 x; returns b1 (nan when degenerate)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if len(x) < 3 or y.min() == y.max() or x.std() <= 0:
        return float("nan")
    X = np.stack([np.ones_like(x), x], 1)
    b = np.zeros(2)
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ b, -30, 30)))
        g = X.T @ (y - p)
        H = (X * (p * (1 - p))[:, None]).T @ X + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, g)
        b = b + step
        if np.abs(step).max() < 1e-10:
            break
    return float(b[1]) if np.all(np.isfinite(b)) else float("nan")


def delta_strata(C: np.ndarray) -> tuple[float, float]:
    """C (strata, 2 groups, 2 fled) → Δ = Σ_b w_b (F_0(b) − F_1(b)) over strata with both groups (R8 delta_from), ρ = ΣwF0/ΣwF1."""
    n = C.sum(-1).astype(np.float64)
    ok = (n[:, 0] > 0) & (n[:, 1] > 0)
    F = np.divide(C[..., 1], n, out=np.zeros_like(n), where=n > 0)
    wgt = np.where(ok, n.sum(-1), 0.0)
    if wgt.sum() <= 0:
        return float("nan"), float("nan")
    wgt = wgt / wgt.sum()
    d = float((wgt * (F[:, 0] - F[:, 1])).sum())
    den = float((wgt * F[:, 1]).sum())
    return d, (float((wgt * F[:, 0]).sum() / den) if den > 0 else float("inf"))


def species_metrics(rec: dict) -> dict:
    """Per species: steps, action shares, in-shelter, eaten E, deaths, births per 1,000 steps and per 1,000 eligible steps."""
    st = rec["st"]
    out = {}
    for sp, nm in enumerate(SPECIES):
        al = st["alive_steps"][:, sp].astype(np.float64)
        dec = st["decisions"][:, sp].astype(np.float64)
        act = st["actions"][:, sp].sum(0).astype(np.float64)
        D = max(float(dec.sum()), 1.0)
        A = max(float(al.sum()), 1.0)
        deaths = st["deaths"][:, sp].sum(0)
        eh = rec["ehist"][:, sp].sum(0)
        cum = np.cumsum(eh)
        med = float(np.searchsorted(cum, 0.5 * cum[-1]) / 100.0) if cum[-1] > 0 else float("nan")
        out[nm] = dict(
            alive_steps=int(al.sum()), decisions=int(dec.sum()),
            act_eat=float(act[B.EAT]) / D, act_walk=float(act[B.WALK_FIRST:B.WALK_LAST + 1].sum()) / D,
            act_run=float(act[B.RUN_FIRST:B.RUN_LAST + 1].sum()) / D, act_shelter=float(act[B.SHELTER]) / D,
            act_watch=float(act[B.WATCH]) / D, in_shelter=float(st["in_shelter_steps"][:, sp].sum()) / A,
            run_gait=float(st["run_steps"][:, sp].sum()) / A,
            eaten_x1000=1000.0 * float(st["eaten_e"][:, sp].sum()) / A,
            eaten_by_food={f: float(st["eaten_e"][:, sp, i].sum()) for i, f in enumerate(B.FOODS)},
            caught_1k=1000.0 * float(deaths[W.CAUSE_BITE]) / A, counter_deaths_1k=1000.0 * float(deaths[W.CAUSE_COUNTER]) / A,
            starved_1k=1000.0 * float(deaths[W.CAUSE_STARVE]) / A,
            births_1k=1000.0 * float(st["birth_credits"][:, sp].sum()) / A,
            births_per_1k_eligible=1000.0 * float(st["birth_credits"][:, sp].sum()) / max(float(rec["elig"][:, sp].sum()), 1.0),
            E_median=med, near_ties=int(st["near_ties"][:, sp].sum()),
        )
    return out


def j3_metrics(rec: dict) -> dict:
    """8-2 현실 띠 지표 + 최소 표본 + 9-2 J3 판정 (셋 가운데 둘)."""
    K = int(rec["K"])
    h = hunt_stats(rec["hunts"], rec["kills"], K)
    wolf_steps = rec["st"]["alive_steps"][:, WOLF].astype(np.float64)
    sr_pair, sr_pair_ci = boot_ratio(h["successes"], h["segments"])
    he = hunt_episodes(rec["hunts"], rec["kills"], K)
    sre, sre_ci = boot_ratio(he["successes"], he["episodes"])
    hunt_def = DEFS["hunt"]
    if hunt_def == "episode":
        sr, sr_ci, n_att = sre, sre_ci, float(he["episodes"].sum())
    else:
        sr, sr_ci, n_att = sr_pair, sr_pair_ci, float(h["segments"].sum())
    dk, dk_ci = boot_ratio(h["kills"], wolf_steps / float(B.DAY_STEPS))
    jv = juvenile_index(rec["kills"], K)
    ji, ji_ci = boot_ratio(jv["young"], jv["share"])
    n_seg, n_kill, n_boar = float(h["segments"].sum()), float(h["kills"].sum()), float(jv["n"].sum())
    lo_s, hi_s = J3_BANDS["success"]
    lo_d, hi_d = J3_BANDS["daily_kill"]
    ok = dict(success=bool(n_att >= J3_MIN_N["segments"] and math.isfinite(sr) and lo_s <= sr <= hi_s),
              daily_kill=bool(n_kill >= J3_MIN_N["kills"] and math.isfinite(dk) and lo_d <= dk <= hi_d),
              juv_index=bool(n_boar >= J3_MIN_N["boar_kills"] and math.isfinite(ji) and ji >= J3_BANDS["juv_index_min"]))
    comp = np.zeros(3)
    for e in rec["kills"]:
        comp[int(e["prey_sp"])] += 1
    return dict(
        success_rate=sr, success_ci=sr_ci, hunt_def=hunt_def, attempts=int(n_att),
        success_rate_pair=sr_pair, success_pair_ci=sr_pair_ci, segments=int(n_seg), successes=int(h["successes"].sum()),
        short_kills=int(h["short_kills"].sum()), success_rate_episode=sre, success_episode_ci=sre_ci,
        episodes=int(he["episodes"].sum()), daily_kill=dk, daily_kill_ci=dk_ci, kills=int(n_kill),
        walk_kill_share=float(h["walk_kills"].sum()) / n_kill if n_kill else float("nan"),
        pack_segment_share=float(h["pack_segments"].sum()) / float(h["qualifying"].sum()) if h["qualifying"].sum() else float("nan"),
        ran_segment_share=float(h["ran_segments"].sum()) / float(h["qualifying"].sum()) if h["qualifying"].sum() else float("nan"),
        juv_index=ji, juv_index_ci=ji_ci, boar_kills=int(n_boar),
        juv_raw_share=float(jv["young"].sum()) / n_boar if n_boar else float("nan"),
        prey_share={SPECIES[s]: (float(comp[s]) / n_kill if n_kill else float("nan")) for s in (DEER, BOAR)},
        old_attempts=int(rec["att"][:, 0].sum()), old_success=ratio(rec["att"][:, 1], rec["att"][:, 0]),
        ok=ok, insufficient={k: v for k, v in dict(success=n_att < J3_MIN_N["segments"], daily_kill=n_kill < J3_MIN_N["kills"],
                                                       juv_index=n_boar < J3_MIN_N["boar_kills"]).items() if v},
        passed=int(sum(ok.values())), J3=bool(sum(ok.values()) >= 2),
        per_world=dict(segments=h["segments"].tolist(), successes=h["successes"].tolist(), kills=h["kills"].tolist(),
                       wolf_steps=wolf_steps.tolist()),
    )


def population_metrics(rec: dict) -> dict:
    """8-2 개체군 지표 (판정 세계): 공존 세계·첫 멸종·준멸종·흔들림·죽음 원인·출생 막힘·먹이 잔량·학습 범위 밖·새끼 첫 300 스텝."""
    K = int(rec["K"])
    pop = np.asarray(rec["pop"], dtype=np.int64)                      # (T, K, Q, 3)
    T = pop.shape[0]
    tot = pop.sum(2) if T else np.zeros((0, K, 3), np.int64)          # (T, K, 3)
    t = np.asarray(rec["pop_t"], dtype=np.float64)
    end_t = float(rec["steps"])
    coexist = rec["final_pair"].all(1)
    cx, cx_ci = boot_mean(coexist.astype(np.float64))
    ext_t = np.full((K, 3), end_t)
    ext_e = np.zeros((K, 3), dtype=bool)
    for k in range(K):
        for s in range(3):
            z = np.nonzero(tot[:, k, s] == 0)[0] if T else []
            if len(z):
                ext_t[k, s], ext_e[k, s] = t[z[0]], True
    start = np.asarray(rec["start_counts"], dtype=np.float64)
    low = (tot < 0.1 * start[None]).any(0) & (start > 0) if T else np.zeros((K, 3), bool)
    nopair = ~np.asarray(rec["pair_hist"]).all(0) if len(rec["pair_hist"]) else np.zeros((K, 3), bool)
    nopair |= ~rec["final_pair"]
    quasi = (low | nopair).any(1)
    half = tot[T // 2:] if T else tot
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_h = half.mean(0)
        cv = np.where(mean_h > 0, half.std(0) / mean_h, np.nan)
        mm = np.where(half.max(0) > 0, half.min(0) / half.max(0), np.nan)
    lags = []
    if T >= 8:
        stride = max(1, T // 1000)                                     # [어림] 긴 판은 1,000 점 안팎으로 솎아 교차상관 (보고만)
        step = (float(t[1] - t[0]) if T > 1 else 2.0) * stride
        sub = tot[::stride]
        for k in range(K):
            lg = lag_corr(sub[:, k, DEER] + sub[:, k, BOAR], sub[:, k, WOLF], max(1, len(sub) // 4))
            if lg is not None:
                lags.append(lg * step)
    st = rec["st"]
    deaths = st["deaths"].sum(0)                                       # (3, 4)
    life = rec["life"]
    bs = block_share(life)
    content = bs["content"].sum(1)
    paired = bs["paired"].sum(1)
    share_w = np.divide(content, content + paired, out=np.zeros(K), where=(content + paired) > 0)
    sh_all = ratio(content, content + paired)
    alt = {}
    for bd in BLOCK_DEFS:
        b2 = block_share(life, bd)
        c2 = b2["content"].sum(1)
        alt[bd] = ratio(c2, c2 + b2["paired"].sum(1))
    # out-of-training-range time share (3-6)
    oor = {SPECIES[s]: (float((pop[..., s] > OUT_OF_RANGE[s]).mean()) if T else float("nan")) for s in range(3)}
    # newborn first 300 steps
    born = {(int(b["k"]), int(b["uid"])): (int(b["t"]), int(b["sp"])) for b in rec["births"]}
    nb_n = np.zeros(3)
    nb_st = np.zeros(3)
    nb_bt = np.zeros(3)
    for (k, u), (tb, sp) in born.items():
        if tb + NEWBORN_WINDOW <= end_t:
            nb_n[sp] += 1
    for d in rec["deaths"]:
        key = (int(d["k"]), int(d["uid"]))
        if key in born:
            tb, sp = born[key]
            if tb + NEWBORN_WINDOW <= end_t and int(d["t"]) - tb < NEWBORN_WINDOW:
                nb_st[sp] += d["cause"] == "starve"
                nb_bt[sp] += d["cause"] == "bite"
    return dict(
        coexist_share=cx, coexist_ci=cx_ci, coexist_worlds=coexist.astype(int).tolist(),
        final_pair_share={SPECIES[s]: float(rec["final_pair"][:, s].mean()) for s in range(3)},
        first_extinction_median={SPECIES[s]: km_median(ext_t[:, s], ext_e[:, s]) for s in range(3)},
        extinct_share={SPECIES[s]: float(ext_e[:, s].mean()) for s in range(3)},
        quasi_extinct_share=float(quasi.mean()),
        start={SPECIES[s]: float(start[:, s].mean()) for s in range(3)},
        end_mean={SPECIES[s]: (float(tot[-1, :, s].mean()) if T else float("nan")) for s in range(3)},
        end_ratio={SPECIES[s]: (float(tot[-1, :, s].sum() / max(start[:, s].sum(), 1.0)) if T else float("nan")) for s in range(3)},
        cv_second_half={SPECIES[s]: float(np.nanmedian(cv[:, s])) if np.isfinite(cv[:, s]).any() else float("nan") for s in range(3)},
        minmax_second_half={SPECIES[s]: float(np.nanmedian(mm[:, s])) if np.isfinite(mm[:, s]).any() else float("nan") for s in range(3)},
        wolf_lag_steps_median=float(np.median(lags)) if lags else float("nan"),
        deaths={SPECIES[s]: {W.CAUSE_NAMES[c]: int(deaths[s, c]) for c in range(1, 4)} for s in range(3)},
        newborns={SPECIES[s]: int(st["newborns"][:, s].sum()) for s in range(3)},
        newborn_300={SPECIES[s]: dict(n=int(nb_n[s]), starve=float(nb_st[s] / nb_n[s]) if nb_n[s] else float("nan"),
                                       bite=float(nb_bt[s] / nb_n[s]) if nb_n[s] else float("nan")) for s in range(3)},
        block_share=sh_all, block_def=DEFS["block"], block_share_scan=alt["scan"], block_share_once=alt["once"],
        block_share_worlds=share_w.tolist(),
        block_share_species={SPECIES[s]: ratio(bs["content"][:, s], bs["content"][:, s] + bs["paired"][:, s]) for s in range(3)},
        blocked_by_reason={SPECIES[s]: {L.BLOCK_NAMES[i]: int(bs["by_reason"][s, i]) for i in range(L.N_BLOCK)} for s in range(3)},
        opportunities={SPECIES[s]: int(np.asarray(life["opportunities"])[:, :, s].sum()) for s in range(3)},
        paired={SPECIES[s]: int(paired_s) for s, paired_s in enumerate(bs["paired"].sum(0))},
        failed={SPECIES[s]: int(np.asarray(life["failed"])[:, :, s].sum()) for s in range(3)},
        cancelled={SPECIES[s]: int(np.asarray(life["cancelled"])[:, :, s].sum()) for s in range(3)},
        rule_backed=bool(math.isfinite(sh_all) and sh_all >= BLOCK_SHARE_FLAG),
        food_end=dict(grass_mean=float(np.mean(rec["food_end"][:, 0])), root_mean=float(np.mean(rec["food_end"][:, 1])),
                      grass_empty=float(np.nanmean(rec["food_end"][:, 2])), root_empty=float(np.nanmean(rec["food_end"][:, 3]))),
        out_of_train_range=oor, near_ties=int(st["near_ties"].sum()),
        slot_cap_blocks=int(bs["by_reason"][:, L.BLOCK_SLOT_CAP].sum()),
    )


def scene_metrics(rec: dict) -> dict:
    """8-3 상호작용 장면 지표 (보고만)."""
    K = int(rec["K"])
    kills = rec["kills"]
    # 늑대 먹이 바꾸기: logit P(deer) on log((seen deer + 0.5) / (seen boar + 0.5)) [어림: 0.5 보정 — 0 이 있는 죽임도 쓰려고]
    xs, ys, ks = [], [], []
    for e in kills:
        sd, sbr = float(e["seen"][DEER]), float(e["seen"][BOAR])
        xs.append(math.log((sd + 0.5) / (sbr + 0.5)))
        ys.append(1.0 if int(e["prey_sp"]) == DEER else 0.0)
        ks.append(int(e["k"]))
    xs, ys, ks = np.asarray(xs), np.asarray(ys), np.asarray(ks, dtype=np.int64)
    slope = logistic_slope(xs, ys)
    rows_by_k = [np.nonzero(ks == k)[0] for k in range(K)]

    def _sl(idx):
        r = np.concatenate([rows_by_k[i] for i in idx]) if len(idx) else np.zeros(0, np.int64)
        return logistic_slope(xs[r], ys[r])
    slope_ci = boot_ci(_sl, K, B_=500) if len(xs) >= 10 else [float("nan"), float("nan")]
    ee = rec["st"]["eaten_e"].sum(0)                                   # (3, 3)
    pk = pianka(ee[DEER] / max(ee[DEER].sum(), 1e-12), ee[BOAR] / max(ee[BOAR].sum(), 1e-12)) if ee[DEER].sum() > 0 and ee[BOAR].sum() > 0 else float("nan")
    disp = rec["sc_disp"].sum(0)                                       # (2 types, 2)
    sated = rec["sc_sated"].sum(0)
    d_sated, rho_sated = delta_strata(sated)
    pend = rec["sc_pend"].sum(0)                                       # (2 sp, 2 mating, 2 fled)
    face = rec["sc_face"].sum(0)                                       # (2 age, 3 cat)
    bites = rec["st"]["bites"].sum(0)                                  # (3 prey, 3 outcome)
    boar_bites = float(bites[BOAR].sum())
    meat_created = float(rec["st"]["meat_created"].sum())
    meat_eaten = rec["st"]["eaten_units"][:, :, B.MEAT].sum(0)
    kin = rec["sc_kin"].sum(0)

    def frac(c):
        n = float(c.sum())
        return [float(x) / n for x in c] if n else [float("nan")] * len(c)
    return dict(
        prey_switch_slope=slope, prey_switch_ci=slope_ci, prey_switch_n=int(len(xs)),
        diet_pianka=pk, cell_pianka=float(np.nanmean(rec["sc_cells_pianka"])) if np.isfinite(rec["sc_cells_pianka"]).any() else float("nan"),
        leave_after_boar=float(disp[0, 1] / disp[0].sum()) if disp[0].sum() else float("nan"),
        leave_after_deer=float(disp[1, 1] / disp[1].sum()) if disp[1].sum() else float("nan"),
        leave_n=[int(disp[0].sum()), int(disp[1].sum())],
        sated_wolf_delta=d_sated, sated_wolf_rho=rho_sated,
        sated_wolf_ci=boot_ci(lambda i: delta_strata(rec["sc_sated"][i].sum(0))[0], K, B_=500),
        flee_near_hungry=frac(sated[:, 0].sum(0))[1] if sated[:, 0].sum() else float("nan"),
        flee_near_sated=frac(sated[:, 1].sum(0))[1] if sated[:, 1].sum() else float("nan"),
        boar_face={("adult" if a else "young"): dict(zip(("face", "flee", "other"), frac(face[a]))) for a in (0, 1)},
        boar_face_n=[int(face[0].sum()), int(face[1].sum())],
        counters_per_1k_boar_bites=1000.0 * float(bites[BOAR, W.BITE_COUNTER]) / boar_bites if boar_bites else float("nan"),
        wolf_hp_lost=float(rec["st"]["wolf_hp_lost"].sum()), counters_near_carcass=int(rec["counters"]["near_carcass"]),
        counters_hunting=int(rec["counters"]["hunting"]),
        pending_flee={SPECIES[s]: dict(mating=frac(pend[i, 1])[1] if pend[i, 1].sum() else float("nan"),
                                       not_mating=frac(pend[i, 0])[1] if pend[i, 0].sum() else float("nan"),
                                       n=[int(pend[i, 1].sum()), int(pend[i, 0].sum())]) for i, s in enumerate((DEER, BOAR))},
        carcass=dict(meat_created=meat_created, wolf_share=float(meat_eaten[WOLF]) / meat_created if meat_created else float("nan"),
                     boar_share=float(meat_eaten[BOAR]) / meat_created if meat_created else float("nan"),
                     decayed_share=float(rec["st"]["meat_decayed"].sum()) / meat_created if meat_created else float("nan"),
                     first_wolf_eat_median=float(np.median(rec["carc_first"])) if rec["carc_first"] else float("nan"),
                     wolf_returns=int(rec["carc_returns"]), wolf_eating_pairs=int(rec["carc_wolf_eats"]),
                     overflow=int(rec["st"]["meat_overflow"].sum())),
        nearest_kin={SPECIES[s]: (float(kin[s, 0] / kin[s, 1]) if kin[s, 1] else float("nan")) for s in (DEER, BOAR)},
        pack_segment_share=j3_metrics(rec)["pack_segment_share"],
    )


def anomaly_metrics(rec: dict) -> dict:
    """8-4 이상 행동 점검 + 문턱 (J4)."""
    K = int(rec["K"])
    st = rec["st"]
    thr = ANOMALY_THRESHOLDS
    corner = ratio(rec["an_corner"][:, 1], rec["an_corner"][:, 0])
    prey_bite = [d for d in rec["deaths"] if d["cause"] == "bite" and int(d["sp"]) in (DEER, BOAR)]
    wall_kill = (sum(1 for d in prey_bite if d["wall"]) / len(prey_bite)) if prey_bite else float("nan")
    wall_ratio = wall_kill / rec["band_share"]["wall"] if math.isfinite(wall_kill) else float("nan")
    edge_kill = (sum(1 for d in prey_bite if 0.0 < float(d["shelter_edge"]) <= 3.0) / len(prey_bite)) if prey_bite else float("nan")
    eb = float(np.mean(rec["band_share"]["edge"])) if len(rec["band_share"]["edge"]) else float("nan")
    edge_ratio = edge_kill / eb if (math.isfinite(edge_kill) and eb > 0) else float("nan")
    edge_stand = ratio(rec["an_edge_stand"][:, 1], rec["an_edge_stand"][:, 0])
    sh = rec["an_shield"].sum(0)
    shield = (sh[1] / sh[0]) / (sh[3] / sh[2]) if sh[0] > 0 and sh[2] > 0 and sh[3] > 0 else float("nan")
    al = st["alive_steps"].sum(0).astype(np.float64)
    hide = {SPECIES[s]: float(st["in_shelter_steps"][:, s].sum()) / max(al[s], 1.0) for s in (DEER, BOAR)}
    dec = st["decisions"].sum(0).astype(np.float64)
    runs = {SPECIES[s]: float(st["actions"][:, s, B.RUN_FIRST:B.RUN_LAST + 1].sum()) / max(dec[s], 1.0) for s in range(3)}
    fight = ratio(rec["an_fight"][:, 1], rec["an_fight"][:, 0])
    kills = rec["kills"]
    surplus = (sum(1 for e in kills if e["wolf_E"] > 0.9) / len(kills)) if kills else float("nan")
    h = hunt_stats(rec["hunts"], kills, K)
    wolf_days = float(st["alive_steps"][:, WOLF].sum()) / B.DAY_STEPS
    seg_per_day = float(h["qualifying"].sum()) / wolf_days if wolf_days > 0 else float("nan")
    wd = st["deaths"][:, WOLF].sum(0)
    wolf_starve_share = float(wd[W.CAUSE_STARVE]) / float(wd[1:].sum()) if wd[1:].sum() else float("nan")
    no_hunt = bool(math.isfinite(seg_per_day) and seg_per_day < 1.0 and math.isfinite(wolf_starve_share) and wolf_starve_share > 0.5)
    ar = rec["an_arena"].sum(0)                                        # (2, 4)
    arena = {}
    for i, s in enumerate((DEER, BOAR)):
        hn = ar[i, 2] / ar[i, 0] if ar[i, 0] else float("nan")
        ho = ar[i, 3] / ar[i, 1] if ar[i, 1] else float("nan")
        arena[SPECIES[s]] = float(hn / ho) if (math.isfinite(hn) and math.isfinite(ho) and ho > 0) else float("nan")
    counter_src = dict(rec["counters"], wolf_hp_lost=float(st["wolf_hp_lost"].sum()))       # 늑대 HP 손실의 출처 (8-4 늘 싸움)
    far = [d for (_k, _s, d) in rec["resp_far"]]
    flags = dict(corner=corner > thr["corner"], wall_drive=wall_ratio > thr["wall_drive"], edge_stand=edge_stand > thr["edge_stand"],
                 edge_kill=edge_ratio > thr["edge_kill"], shield=shield > thr["shield"],
                 always_hide=any(v > thr["always_hide"] for v in hide.values()),
                 always_run=any(v > thr["always_run"] for v in runs.values()), always_fight=fight > thr["always_fight"],
                 no_hunt=no_hunt, surplus=surplus > thr["surplus"],
                 arena=any(math.isfinite(v) and v > thr["arena"] for v in arena.values()))
    flags = {k: bool(v) for k, v in flags.items()}
    return dict(corner=corner, wall_kill_share=wall_kill, wall_band_share=rec["band_share"]["wall"], wall_ratio=wall_ratio,
                edge_stand=edge_stand, edge_kill_share=edge_kill, edge_band_share=eb, edge_ratio=edge_ratio, shield=shield,
                always_hide=hide, always_run=runs, always_fight=fight, segments_per_wolf_day=seg_per_day,
                wolf_starve_share=wolf_starve_share, no_hunt=no_hunt, surplus=surplus, arena=arena, counter_source=counter_src,
                respawn_far_share=(float(np.mean(np.asarray(far) >= 20.0)) if far else float("nan")), respawn_far_n=len(far),
                flags=flags, J4=[k for k, v in flags.items() if v])


def split_metrics(rec: dict) -> dict:
    """J1 / C0-11 accounting of a SplitBrain run: per-1,000-step rates of each side and paired world-bootstrap differences."""
    sp = rec["split_sp"]
    if sp is None:
        return {}
    F = {n: i for i, n in enumerate(Recorder.ACC_FIELDS)}
    A = rec["acc"][:, sp]                                              # (K, 2, NF)
    st0, st1 = A[:, 0, F["steps"]], A[:, 1, F["steps"]]
    out = dict(species=SPECIES[sp], steps=[float(st0.sum()), float(st1.sum())])
    for nm in ("r_nb", "r_off", "r_on", "eaten", "d_bite", "d_counter", "d_starve", "births"):
        r0, r1 = 1000.0 * ratio(A[:, 0, F[nm]], st0), 1000.0 * ratio(A[:, 1, F[nm]], st1)
        d, ci = boot_rate_diff(A[:, 0, F[nm]], st0, A[:, 1, F[nm]], st1)
        out[nm] = dict(first=r0, second=r1, diff=d, ci=ci)
    e0, e1 = A[:, 0, F["elig"]], A[:, 1, F["elig"]]
    out["births_per_1k_eligible"] = dict(first=1000.0 * ratio(A[:, 0, F["births"]], e0), second=1000.0 * ratio(A[:, 1, F["births"]], e1))
    out["pairs"] = dict(first=float(A[:, 0, F["pairs"]].sum()), second=float(A[:, 1, F["pairs"]].sum()))
    pc = rec["pair_combo"][:, sp].sum(0)
    bc = rec["birth_combo"][:, sp].sum(0)
    out["pair_combo"] = dict(first_first=int(pc[0]), first_second=int(pc[1]), second_second=int(pc[2]))
    out["birth_combo"] = dict(first_first=int(bc[0]), first_second=int(bc[1]), second_second=int(bc[2]))
    out["per_world"] = dict(r_nb0=A[:, 0, F["r_nb"]].tolist(), r_nb1=A[:, 1, F["r_nb"]].tolist(), steps0=st0.tolist(), steps1=st1.tolist())
    if sp == WOLF:                                                     # 8-1 늑대 구성 값: 두뇌별 하루 잡이
        K = int(rec["K"])
        kg = np.zeros((K, 2))
        for e in rec["kills"]:
            g = rec["uid_group"][int(e["k"])].get(int(e["wolf_uid"]), -1)
            if g >= 0:
                kg[int(e["k"]), g] += 1
        out["daily_kill"] = dict(first=ratio(kg[:, 0], st0 / B.DAY_STEPS), second=ratio(kg[:, 1], st1 / B.DAY_STEPS),
                                 kills=[float(kg[:, 0].sum()), float(kg[:, 1].sum())])
        d, ci = boot_rate_diff(kg[:, 0], st0 / B.DAY_STEPS, kg[:, 1], st1 / B.DAY_STEPS, scale=1.0)
        out["daily_kill"].update(diff=d, ci=ci)
    return out


def discounted_means(rews: np.ndarray, dones: np.ndarray, mask: np.ndarray, gammas=(0.997, 0.99)) -> dict:
    """C0-11 '두 γ 후보로 할인한 결정당 반환값의 평균' [해석]: G_d = r_d + γ G_{d+1} within one individual's life (a death ends it,
    the run end truncates). rews/dones/mask (T, K, S). Returns {γ: mean over masked decisions}."""
    T = rews.shape[0]
    out = {}
    for g in gammas:
        G = np.zeros(rews.shape[1:])
        tot, n = 0.0, 0
        for d in range(T - 1, -1, -1):
            G = rews[d] + g * np.where(dones[d], 0.0, G)
            m = mask[d]
            tot += float(G[m].sum())
            n += int(m.sum())
        out[str(g)] = tot / n if n else float("nan")
    return out


def to_jsonable(x):
    """numpy → plain JSON values (nan/inf kept as floats)."""
    if isinstance(x, dict):
        return {str(k): to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [to_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return to_jsonable(x.tolist())
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x
