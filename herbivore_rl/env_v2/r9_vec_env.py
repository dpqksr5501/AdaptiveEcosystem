"""R9 learner VecEnv — one learning species, K train worlds, opponents are fixed brains inside the world (design
AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 7-3·7-4·7-7·7-10, 11절, 12절 tests 17·18·21).

    venv = R9VecEnv(cfg, learner="deer", model_seed=0, round_=1, pool={"wolf": [npz…], "boar": [npz…]})

- Learner slots (7-3): world k holds `learner_counts[sp][k mod len]` learners — every individual of the learning species is a
  learner slot. SB3 envs = Σ_k counts (deer 896 (S′ N: 32 worlds × 16·24·32·40) · boar 768 · wolf 384), world-major then slot
  order (`R9World.learner_index`). Observation = 115 columns (S′ 4절).
  Train worlds respawn at once, so the learner slots are always alive and the env count never changes.
- Staggered renew (R8 `r8_vec_env.py` `_staggered`·`_pick`·`_renew`): world k starts aged k·T/K decisions, T = reset_steps / 2
  = 2,500 decisions; a renewed world gets a new seed (meta RNG, from the train pool, not one of the other running seeds) AND a
  new opponent brain per non-learner species (7-4, test 18). Truncated slots: done + terminal_observation (pre-renew obs) +
  TimeLimit.truncated. A slot that died in the same decision keeps the death (no truncated flag) — R8 `r8_vec_env.py` 96~107.
  Dead slots' terminal_observation = the observation after the step (already the respawned individual; SB3 ignores it).
- Opponent pick (7-4) — every renew draws exactly 3 meta uniforms per opponent species, in species order:
      u1 → kind by the shares (order current, past, rule, always_eat); u2 → past version; u3 → stochastic (< 0.75) or greedy.
  'current' = latest version V of that species' pool (fixed for the bundle), 'past' = Uniform{⌊V/2⌋ … V − 1}; V = 0 (one version)
  sends the past share to the rule brain (RL-17). [해석] an empty pool sends 'current' and 'past' to the rule brain too.
  Round 0: rule 100% (wolf bundle prey: rule 70% + always-eat 30%); round ≥ 1: 50/30/20 (cfg.train.opponents; `shares` overrides
  per opponent species for the 9-4 prescriptions and the C0-10 always-eat start).
- Meta RNG (10절): `default_rng([model_seed, round, segment, learner_species])`. [해석] '묶음 안 판 번호' = segment = the number of
  in-bundle snapshots already written; the trainer calls `set_segment(i)` at each snapshot, so the picks after snapshot i come from
  the stream (model, round, i, species). The first segment is 0 (bundle start). Same arguments → same seeds and opponents.
- Wolf world shards (7-3, test 21): `shards = n` splits the K worlds into n contiguous blocks; block 0 runs in this process,
  blocks 1.. in worker processes (`python -m env_v2.r9_vec_env --shard-worker`, no window, MKL/OMP 1 thread, named pipe, no
  bytecode written into the repository). Workers import the same repository modules (r9_world · r9_brains · r9_body), so every
  shard runs the same S′ world as block 0 (test: tests/test_r9_s_world.py worker check). All meta
  decisions (seeds, opponents, renew times) are made here in world order, and a world's trajectory depends only on its seed,
  counts and controllers (worlds own their RNG streams; fixed brains run one same-shape block per world, 7-10), so the result
  does not depend on the shard count. Concatenation order is fixed (block 0, 1, …).
- Hidden-label stats for the training log only (never part of the observation): learner prey decisions whose nearest sensed
  other is a wolf within 10 units (flee share = RUN — S′: SHELTER is standing, not fleeing), boar decisions walking toward a non-approaching wolf (9-5).
- Judge seeds 44800~44999 are refused (9-2 판정 시드 잠금, test 25).
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from gymnasium.spaces import Box, Discrete
from stable_baselines3.common.vec_env.base_vec_env import VecEnv

from . import r9_body as B
from . import r9_brains as BR
from .r9_world import R9World

ROOT = Path(__file__).resolve().parents[1]              # herbivore_rl/
OBS_SPACE = Box(-1.0, 1.0, (B.OBS_DIM,), np.float32)
ACT_SPACE = Discrete(B.N_ACTIONS)

JUDGE_SEEDS = (44800, 45000)                            # 10절 판정 범위 [lo, hi) — training code refuses it (test 25)
FAUNA_JUDGE_SEEDS = (46900, 47000)                      # 동물 세계 판정 J2F·J3F (RL_R9_SPECIES_TRAITS.md 7-3) — also refused
OPP_KINDS = ("current", "past", "rule", "always_eat")
RULE_OF = {B.DEER: "RULE_DEER", B.WOLF: "RULE_WOLF", B.BOAR: "RULE_BOAR", B.BUFFALO: "RULE_BUFFALO", B.LEOPARD: "RULE_LEOPARD",
           B.FOX: "RULE_FOX"}
NEAR_WOLF_R = 10.0                                      # [어림] online flee / toward-wolf stats: nearest sensed wolf within 10 units
WOLF_IDLE_APPROACH = 0.1                                # [어림] 'wolf not approaching' = approach obs ≤ 0.1 (RULE_BOAR walk threshold)
TOWARD_COS = 0.9238795325112867                         # cos 22.5°: WALK_j direction within half a sector of the wolf direction
ONLINE_KEYS = ("dec", "rew_n", "rew_sum", "near_wolf", "near_wolf_flee", "wolf_idle", "toward_wolf")
FAMILY = "AF_PIPE" if os.name == "nt" else "AF_UNIX"


def species_index(sp) -> int:
    if isinstance(sp, (int, np.integer)):
        return int(sp)
    return B.SPECIES_INDEX[str(sp)]


def check_train_seeds(seeds) -> None:
    """Training / check code must never touch the judge seeds (9-2, test 25)."""
    s = np.asarray(list(seeds), dtype=np.int64)
    bad = s[(s >= JUDGE_SEEDS[0]) & (s < JUDGE_SEEDS[1])]
    if len(bad):
        raise ValueError(f"judge seeds {JUDGE_SEEDS[0]}~{JUDGE_SEEDS[1] - 1} are locked for the final judgement (got {bad[:5].tolist()})")
    bad = s[(s >= FAUNA_JUDGE_SEEDS[0]) & (s < FAUNA_JUDGE_SEEDS[1])]
    if len(bad):
        raise ValueError(f"animal-world judge seeds {FAUNA_JUDGE_SEEDS[0]}~{FAUNA_JUDGE_SEEDS[1] - 1} are locked (got {bad[:5].tolist()})")


def can_bite_of(cfg: dict, sp: int) -> bool:
    """A body with teeth (non-empty `bites`) — the same as r9_body.Body.can_bite, read from the config."""
    return bool(cfg["species"][B.ALL_SPECIES[int(sp)]]["bites"])


# --------------------------------------------------------------------------- #
# opponent choice (7-4, test 18)
# --------------------------------------------------------------------------- #

def opponent_shares(cfg: dict, round_: int, learner: int, opp: int, override: dict | None = None) -> dict:
    """Shares {kind: p} for opponent species `opp` when `learner` learns in round `round_` (cfg.train.opponents, 7-4)."""
    if override:
        o = override.get(B.ALL_SPECIES[opp], override.get(opp, override.get("*")))
        if o is not None:
            return dict(o)
    op = cfg["train"]["opponents"]
    if int(round_) == 0:
        # 'wolf bundle prey' = a body with teeth learning against a body without (S′: wolf vs deer / boar — the same pairs; 동물 9-5)
        if can_bite_of(cfg, learner) and not can_bite_of(cfg, opp):
            return dict(op["round0_wolf_prey"])
        return dict(op["round0"])
    return dict(op["later"])


def pick_opponent(meta: np.random.Generator, shares: dict, n_versions: int, past_from: float, stoch_frac: float) -> dict:
    """One opponent pick. Always draws 3 uniforms (kind, past version, mode) so the meta stream never depends on the outcome.
    n_versions = pool size of that species (versions v = 0 … V, V = n − 1). Returns {kind, v, stochastic, u}."""
    u = meta.random(3)
    tot = 0.0
    for kd in shares:
        if kd not in OPP_KINDS:
            raise ValueError(f"unknown opponent kind {kd!r} (known {OPP_KINDS})")
        tot += float(shares[kd])
    if abs(tot - 1.0) > 1e-9:
        raise ValueError(f"opponent shares must sum to 1: {shares}")
    acc, kind = 0.0, OPP_KINDS[-1]
    for kd in OPP_KINDS:
        p = float(shares.get(kd, 0.0))
        if p <= 0.0:
            continue
        acc += p
        if u[0] < acc:
            kind = kd
            break
    else:                                           # u[0] ≥ last cumulative (float rounding) → last kind with a share
        kind = [kd for kd in OPP_KINDS if float(shares.get(kd, 0.0)) > 0.0][-1]
    V = int(n_versions) - 1
    v = None
    if kind == "current":
        if V < 0:
            kind = "rule"                           # [해석] empty pool
        else:
            v = V
    elif kind == "past":
        if V <= 0:
            kind = "rule"                           # 7-4: V = 0 → the past share goes to the rule brain
        else:
            lo = int(np.floor(V * float(past_from)))
            lo = min(lo, V - 1)
            v = lo + min(int(u[1] * (V - lo)), V - lo - 1)
    return dict(kind=kind, v=v, stochastic=bool(u[2] < float(stoch_frac)), u=[float(x) for x in u])


def controller_spec(pick: dict, opp: int, pool_paths: Sequence[str], can_bite: bool | None = None) -> tuple:
    """Picklable controller spec (kind, name_or_path, stochastic, label) for shards. can_bite: the opponent has teeth (None = S′
    meaning: the wolf) — always_eat is a prey baseline."""
    kd = pick["kind"]
    if kd in ("current", "past"):
        path = str(pool_paths[pick["v"]])
        return ("mlp", path, pick["stochastic"], f"{kd}:v{pick['v']}")
    if kd == "rule":
        return ("rule", RULE_OF[opp], pick["stochastic"], f"rule:{RULE_OF[opp]}")
    if kd == "always_eat":
        if (opp == B.WOLF) if can_bite is None else bool(can_bite):
            raise ValueError("always_eat is a prey baseline (7-5), not a wolf brain")
        return ("rule", "ALWAYS_EAT", pick["stochastic"], "always_eat:ALWAYS_EAT")
    raise ValueError(kd)


# --------------------------------------------------------------------------- #
# shard core (runs in this process or in a worker process)
# --------------------------------------------------------------------------- #

class _ShardCore:
    """K_local train worlds of one shard: decide (learner actions + fixed brains) → step → renew. Same code in-process and in
    worker processes, so shard count cannot change a world's numbers."""

    def __init__(self, cfg: dict, learner: int, seeds: Sequence[int], counts: np.ndarray, specs: list, online: bool = True):
        self.cfg = cfg
        self.sp = int(learner)
        self.world = R9World(cfg, [int(s) for s in seeds], counts=np.asarray(counts, dtype=np.int64))
        self._brains: dict = {}
        for k, sp_specs in enumerate(specs):
            self._set_ctrls(k, sp_specs)
        self.ek, self.es = self.world.learner_index(self.sp)
        self.n = len(self.ek)
        self.online = bool(online)
        self.ost = {k: 0.0 for k in ONLINE_KEYS}

    def _brain(self, kind: str, name: str, sp: int):
        key = (kind, name, sp)
        b = self._brains.get(key)
        if b is None:
            if kind == "rule":
                b = BR.make_rule(name, self.cfg, sp)                # sp: food_here threshold (ALWAYS_EAT serves deer and boar)
            elif kind == "mlp":
                b = BR.load_brain(Path(name), self.cfg, sp)      # body-hash check (test 27)
            else:
                raise ValueError(kind)
            self._brains[key] = b
        return b

    def _set_ctrls(self, k: int, sp_specs: dict) -> None:
        for s in range(self.world.NS):
            if s == self.sp or sp_specs.get(s) is None:          # learner, or a species with 0 slots in this config (동물 B3)
                self.world.set_controller(k, s, None)
                continue
            kind, name, stoch, label = sp_specs[s]
            self.world.set_controller(k, s, BR.Controller(self._brain(kind, name, s), bool(stoch), label))

    def obs_flat(self) -> np.ndarray:
        return self.world.obs()[self.ek, self.es].copy()

    def _online(self, a: np.ndarray) -> None:
        """Hidden-label decision stats of the learner slots (training log only, 9-5)."""
        w, o = self.world, self.world.obs()
        ek, es = self.ek, self.es
        st = self.ost
        st["dec"] += float(self.n)
        if bool(w.body.can_bite[self.sp]) or not self.n:      # S′: the wolf (동물: every body with teeth)
            return
        oth, _ = w.obs_maps()
        j = oth[ek, es, 0]
        ok = j >= 0
        jw = np.where(ok, j, 0)
        is_wolf = ok & (w.slot_sp[jw] == B.WOLF)
        ob = o[ek, es]
        dist = ob[:, B.other_col(0, "dist")].astype(np.float64) * float(B.OBS_NORM["pos"])
        near = is_wolf & (dist <= NEAR_WOLF_R)
        act = a[ek, es]
        flee = np.isin(act, B.ACTION_GROUPS["run"])            # S′ 검토 low: SHELTER = 제자리 서기라 도망이 아니다
        st["near_wolf"] += float(near.sum())
        st["near_wolf_flee"] += float((near & flee).sum())
        if self.sp == B.BOAR:
            idle = near & (ob[:, B.other_col(0, "approach")] <= WOLF_IDLE_APPROACH)
            rx = ob[:, B.other_col(0, "rel_x")].astype(np.float64)
            ry = ob[:, B.other_col(0, "rel_y")].astype(np.float64)
            rn = np.sqrt(rx * rx + ry * ry)
            rn = np.where(rn > 0.0, rn, 1.0)
            jd = B.action_dir_index(act)
            walk = (jd >= 0) & (act < B.RUN_FIRST)
            d8 = B.DIR8[np.clip(jd, 0, 7)]
            toward = walk & ((d8[:, 0] * rx + d8[:, 1] * ry) / rn >= TOWARD_COS)
            st["wolf_idle"] += float(idle.sum())
            st["toward_wolf"] += float((idle & toward).sum())

    def step(self, la: np.ndarray, renews: list) -> tuple:
        """la (n,) learner actions in learner_index order; renews [(k_local, seed, counts_row, specs)] applied after the step.
        Returns (obs_post (n, 115), rew (n,), done (n,), term {k_local: obs_pre block})."""
        w = self.world
        a = w.decide(learner_sp=self.sp, learner_actions=np.asarray(la, dtype=np.int64))
        if self.online:
            self._online(a)
        obs, rew, done, _ = w.step(a)
        ek, es = self.ek, self.es
        o = obs[ek, es].copy()
        r = rew[ek, es].copy()
        d = done[ek, es].copy()
        self.ost["rew_n"] += float(self.n)
        self.ost["rew_sum"] += float(r.sum())
        term = {}
        if renews:
            for kl, *_ in renews:
                term[int(kl)] = o[ek == int(kl)].copy()
            self.renew(renews)
            o = w.obs()[ek, es].copy()
        return o, r, d, term

    def renew(self, renews: list) -> None:
        """New seed + controllers for the listed local worlds (counts row keeps the learner count of the world number)."""
        for kl, seed, cnt, specs in renews:
            self.world.reinit(int(kl), int(seed), np.asarray(cnt, dtype=np.int64))
            self._set_ctrls(int(kl), specs)

    def stats(self) -> tuple[dict, dict]:
        return self.world.stats_snapshot(), dict(self.ost)

    def values(self, name: str) -> np.ndarray:
        """Learner-slot values of a world array (E, R, hp, stam, …) for the training log."""
        return np.asarray(getattr(self.world, name))[self.ek, self.es].copy()

    def world_params(self, kl: int) -> dict:
        return self.world.world_params(int(kl))

    def mem(self) -> dict:
        return process_memory()


def process_memory() -> dict:
    """This process: peak working set / private bytes in MB (C0-9 memory registry, 7-9)."""
    try:
        import psutil
        mi = psutil.Process().memory_info()
        return dict(pid=os.getpid(), peak_mb=float(getattr(mi, "peak_wset", mi.rss)) / 2 ** 20,
                    private_mb=float(getattr(mi, "private", getattr(mi, "vms", 0))) / 2 ** 20)
    except Exception:  # noqa: BLE001
        return dict(pid=os.getpid(), peak_mb=None, private_mb=None)


class _LocalShard:
    def __init__(self, *args):
        self.core = _ShardCore(*args)

    def step_send(self, la, renews):
        self._res = self.core.step(la, renews)

    def step_recv(self):
        r, self._res = self._res, None
        return r

    def call(self, name, *args):
        return getattr(self.core, name)(*args)

    def obs_flat(self):
        return self.core.obs_flat()

    @property
    def n(self):
        return self.core.n

    def close(self):
        pass


class ShardWorkerLost(RuntimeError):
    """A shard worker could not start, did not open its pipe, died (EOF / broken pipe) or ran out of memory — not a property of
    the seed, so train_r9 ends the bundle with stop='cut' and the league re-runs it from the start copy (Fix 단계 검토 low)."""


class _RemoteShard:
    """Worker process holding one shard (no window, named pipe, 1 MKL/OMP thread)."""

    def __init__(self, init_args: tuple, log_path: Path | None = None):
        from multiprocessing.connection import Client

        key = secrets.token_bytes(16)
        tag = f"r9shard-{os.getpid()}-{secrets.token_hex(6)}"
        address = rf"\\.\pipe\{tag}" if os.name == "nt" else str(Path("/tmp") / tag)
        env = dict(os.environ, PYTHONUTF8="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                   PYTHONDONTWRITEBYTECODE="1")
        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NO_WINDOW
        self._log = open(log_path, "a", encoding="utf-8") if log_path is not None else subprocess.DEVNULL
        self.proc = subprocess.Popen([sys.executable, "-X", "utf8", "-m", "env_v2.r9_vec_env", "--shard-worker", address, key.hex()],
                                     cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL, stdout=self._log, stderr=self._log,
                                     creationflags=flags)
        t0 = time.time()
        self.conn = None
        while self.conn is None:
            if self.proc.poll() is not None:
                raise ShardWorkerLost(f"shard worker exited at start (rc {self.proc.returncode}, log {log_path})")
            try:
                self.conn = Client(address, family=FAMILY, authkey=key)
            except (FileNotFoundError, ConnectionRefusedError, OSError):
                if time.time() - t0 > 120.0:
                    self.proc.kill()
                    raise ShardWorkerLost("shard worker did not open its pipe in 120 s")
                time.sleep(0.05)
        self.conn.send(("init", init_args))
        self._n = int(self._recv())

    def _recv(self):
        try:
            tag, val = self.conn.recv()
        except (EOFError, BrokenPipeError, ConnectionError) as e:
            raise ShardWorkerLost(f"shard worker lost ({type(e).__name__}) — see the worker log") from e
        if tag != "ok":
            if "MemoryError" in str(val):
                raise ShardWorkerLost(f"shard worker out of memory:\n{val}")
            raise RuntimeError(f"shard worker error:\n{val}")
        return val

    @property
    def n(self):
        return self._n

    def step_send(self, la, renews):
        self.conn.send(("step", (np.asarray(la, dtype=np.int64), renews)))

    def step_recv(self):
        return self._recv()

    def call(self, name, *args):
        self.conn.send(("call", (name, args)))
        return self._recv()

    def obs_flat(self):
        return self.call("obs_flat")

    def close(self):
        try:
            if self.conn is not None:
                self.conn.send(("close", None))
                self.conn.recv()
        except (EOFError, OSError, BrokenPipeError):
            pass
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        if self._log is not subprocess.DEVNULL:
            self._log.close()


def _worker_main(address: str, key_hex: str) -> int:
    from multiprocessing.connection import Listener

    with Listener(address, family=FAMILY, authkey=bytes.fromhex(key_hex)) as lst:
        conn = lst.accept()
    core = None
    while True:
        try:
            cmd, payload = conn.recv()
        except (EOFError, OSError):
            return 0
        try:
            if cmd == "init":
                core = _ShardCore(*payload)
                conn.send(("ok", core.n))
            elif cmd == "step":
                conn.send(("ok", core.step(*payload)))
            elif cmd == "call":
                name, args = payload
                conn.send(("ok", getattr(core, name)(*args)))
            elif cmd == "close":
                conn.send(("ok", None))
                return 0
            else:
                conn.send(("err", f"unknown command {cmd!r}"))
        except Exception:  # noqa: BLE001 — sent back to the parent, which raises
            conn.send(("err", traceback.format_exc()))


# --------------------------------------------------------------------------- #
# VecEnv
# --------------------------------------------------------------------------- #

class R9VecEnv(VecEnv):
    metadata = {"render_modes": []}

    def __init__(self, cfg: dict, learner, *, model_seed: int = 0, round_: int = 0, segment: int = 0,
                 pool: dict | None = None, shares: dict | None = None, seeds=None, num_worlds: int | None = None,
                 reset_steps: int | None = None, shards: int = 1, online_stats: bool = True, worker_log_dir: Path | None = None):
        """cfg: train-mode R9 config. learner: species (name or index). pool: {species: [npz paths in version order]} for the
        opponents (the learner's own pool is not used). shares: per opponent species override {name: {kind: p}} (9-4 처방, C0-10).
        seeds: world seed pool (default cfg.train.seeds [lo, hi)). num_worlds: default cfg.train.worlds[learner]."""
        tr = cfg["train"]
        if str(cfg["world"]["mode"]) != "train":
            raise ValueError("R9VecEnv runs train worlds only (judge worlds are driven by the evaluation tools)")
        self.cfg = cfg
        self.names = B.species_of(cfg)
        self.NS = len(self.names)
        self.sp = species_index(learner)
        if not 0 <= self.sp < self.NS:
            raise ValueError(f"learner {learner!r} is not a species of this config {self.names}")
        self.name = B.ALL_SPECIES[self.sp]
        self.model_seed, self.round, self.segment = int(model_seed), int(round_), int(segment)
        self.K = int(num_worlds if num_worlds is not None else tr["worlds"][self.name])
        steps = int(reset_steps if reset_steps is not None else tr["reset_steps"])
        D = int(cfg["world"]["decision_steps"])
        self.T = max(1, steps // D)                                    # renew period (decisions)
        if seeds is None:
            lo, hi = tr["seeds"]
            seeds = range(int(lo), int(hi))
        self.pool = np.asarray(list(seeds), dtype=np.int64)
        check_train_seeds(self.pool)
        self.brain_pool = {s: [] for s in range(self.NS)}
        for key, paths in (pool or {}).items():
            si = species_index(key)
            if si >= self.NS:
                raise ValueError(f"pool species {key!r} is not in this config {self.names}")
            self.brain_pool[si] = [str(p) for p in paths]
        self.share_override = shares
        self.past_from = float(tr["opponents"]["past_from"])
        self.stoch_frac = float(tr["opponent_stochastic"])
        self._caps = np.array([int(cfg["world"]["slots"][n]) for n in self.names], dtype=np.int64)
        self._bite = [can_bite_of(cfg, s) for s in range(self.NS)]
        lc = [int(x) for x in cfg["learner_counts"][self.name]]
        self.counts = np.full((self.K, self.NS), -1, dtype=np.int64)
        self.counts[:, self.sp] = [lc[k % len(lc)] for k in range(self.K)]
        self.variant = self._apply_variants()                         # 동물 9-5 (None everywhere without train.variants)
        self._meta = np.random.default_rng([self.model_seed, self.round, self.segment, self.sp])
        # first worlds: seed, then opponents, world by world (renew uses the same order)
        self.seeds_now: list[int] = []
        specs, picks = [], []
        for k in range(self.K):
            self.seeds_now.append(self._pick(self.seeds_now))
            sp_specs, pk = self._pick_opponents()
            specs.append(sp_specs)
            picks.append(pk)
        self.seed_history: list[list[int]] = [[s] for s in self.seeds_now]
        self.history: list[dict] = [self._hist(k, 0, self.seeds_now[k], picks[k]) for k in range(self.K)]
        self.num_resets = 0
        self.decisions = 0
        n_sh = max(1, min(int(shards), self.K))
        self.bounds = [self.K * i // n_sh for i in range(n_sh + 1)]
        self.shards: list = []
        try:
            for i in range(n_sh):
                a, b = self.bounds[i], self.bounds[i + 1]
                args = (cfg, self.sp, self.seeds_now[a:b], self.counts[a:b], specs[a:b], bool(online_stats))
                if i == 0:
                    self.shards.append(_LocalShard(*args))
                else:
                    lp = None if worker_log_dir is None else Path(worker_log_dir) / f"shard_{os.getpid()}_{i}.log"
                    self.shards.append(_RemoteShard(args, lp))
        except Exception:
            self.close()
            raise
        self._n_sh = [sh.n for sh in self.shards]
        self._off = np.concatenate([[0], np.cumsum(self._n_sh)]).astype(np.int64)
        self._env_world = np.repeat(np.arange(self.K, dtype=np.int64), self.counts[:, self.sp])
        self._world_envs = [np.nonzero(self._env_world == k)[0] for k in range(self.K)]
        self._fresh = True
        self._age = self._staggered()
        self._actions = None
        self.render_mode = None
        n_env = int(self._off[-1])
        if n_env != int(self.counts[:, self.sp].sum()):
            raise RuntimeError(f"learner env count {n_env} != Σ counts {int(self.counts[:, self.sp].sum())}")
        super().__init__(n_env, OBS_SPACE, ACT_SPACE)

    # --- meta choices (this process only) ---
    def _apply_variants(self) -> list:
        """동물 9-5 `train.variants`: world k takes the first variant whose learners include this learner and k % every == every − 1;
        j = k // every picks counts[species][j % len] for opponent species and learner_counts[learner][j % len] for the learner (if
        given). World composition only — no RNG, no behaviour. Returns the variant name per world (None = base)."""
        out: list = [None] * self.K
        vs = self.cfg["train"].get("variants") or []
        for k in range(self.K):
            for v in vs:
                ev = int(v["every"])
                if self.name not in v["learners"] or k % ev != ev - 1:
                    continue
                j = k // ev
                for n, lst in (v.get("counts") or {}).items():
                    s = self.names.index(n)
                    if s != self.sp:
                        self.counts[k, s] = int(lst[j % len(lst)])
                lcs = (v.get("learner_counts") or {}).get(self.name)
                if lcs:
                    self.counts[k, self.sp] = int(lcs[j % len(lcs)])
                out[k] = str(v["name"])
                break
        for k in range(self.K):
            for s in range(self.NS):
                if self.counts[k, s] > self._caps[s]:
                    raise ValueError(f"world {k}: {self.names[s]} count {self.counts[k, s]} exceeds world.slots {self._caps[s]}")
        return out

    def _hist(self, k: int, at: int, seed: int, picks: dict) -> dict:
        """One world history row; the variant name is written only when the config has variants (S′ rows keep their keys)."""
        h = dict(k=int(k), at=int(at), seed=int(seed), opponents=picks)
        if self.cfg["train"].get("variants"):
            h["variant"] = self.variant[int(k)]
        return h

    def _staggered(self) -> np.ndarray:
        return np.array([(k * self.T) // self.K for k in range(self.K)], dtype=np.int64)

    def _pick(self, exclude) -> int:
        ex = set(int(e) for e in exclude)
        if len(self.pool) <= len(ex):
            return int(self._meta.choice(self.pool))
        while True:
            s = int(self._meta.choice(self.pool))
            if s not in ex:
                return s

    def _pick_opponents(self) -> tuple[dict, dict]:
        specs, picks = {}, {}
        for s in range(self.NS):
            if s == self.sp or self._caps[s] == 0:                  # 동물 B3: a species without slots draws no meta uniforms
                specs[s] = None
                continue
            sh = opponent_shares(self.cfg, self.round, self.sp, s, self.share_override)
            pk = pick_opponent(self._meta, sh, len(self.brain_pool[s]), self.past_from, self.stoch_frac)
            specs[s] = controller_spec(pk, s, self.brain_pool[s], self._bite[s])
            picks[self.names[s]] = dict(kind=pk["kind"], v=pk["v"], stochastic=pk["stochastic"], label=specs[s][3],
                                        path=specs[s][1] if specs[s][0] == "mlp" else None)
        return specs, picks

    def set_segment(self, segment: int) -> None:
        """Re-seed the meta stream at an in-bundle snapshot (10절 '묶음 안 판 번호')."""
        self.segment = int(segment)
        self._meta = np.random.default_rng([self.model_seed, self.round, self.segment, self.sp])

    def _shard_of(self, k: int) -> tuple[int, int]:
        for i in range(len(self.shards)):
            if self.bounds[i] <= k < self.bounds[i + 1]:
                return i, k - self.bounds[i]
        raise IndexError(k)

    def current_seeds(self) -> list[int]:
        return [int(s) for s in self.seeds_now]

    # --- SB3 ---
    def reset(self) -> np.ndarray:
        # SB3 calls reset at learn start; freshly built worlds are used as they are (R8 / MultiWorldVecEnv)
        if not self._fresh:                                            # every world renewed (R8 reset), world order
            per = [[] for _ in self.shards]
            for k in range(self.K):
                k, item = self._renew_plan(k)
                i, kl = self._shard_of(k)
                per[i].append((kl,) + item)
            for i, sh in enumerate(self.shards):
                sh.call("renew", per[i])
        self._fresh = True
        self._age = self._staggered()
        return np.concatenate([sh.obs_flat() for sh in self.shards], 0)

    def _renew_plan(self, k: int) -> tuple[int, tuple]:
        others = [int(s) for j, s in enumerate(self.seeds_now) if j != k]
        s = self._pick(others)
        specs, picks = self._pick_opponents()
        self.seeds_now[k] = s
        self.seed_history[k].append(s)
        self.history.append(self._hist(k, self.decisions, s, picks))
        self.num_resets += 1
        return k, (s, self.counts[k].copy(), specs)

    def step_async(self, actions: np.ndarray) -> None:
        self._actions = np.asarray(actions, dtype=np.int64).reshape(self.num_envs)

    def step_wait(self):
        self._fresh = False
        self.decisions += 1
        self._age += 1
        ren = np.nonzero(self._age >= self.T)[0]
        per = [[] for _ in self.shards]
        for k in ren:
            k, item = self._renew_plan(int(k))
            i, kl = self._shard_of(k)
            per[i].append((kl,) + item)
            self._age[k] = 0
        a = self._actions
        for i in range(1, len(self.shards)):                           # remote shards first, then the local one
            self.shards[i].step_send(a[self._off[i]:self._off[i + 1]], per[i])
        self.shards[0].step_send(a[self._off[0]:self._off[1]], per[0])
        res = [self.shards[0].step_recv()] + [self.shards[i].step_recv() for i in range(1, len(self.shards))]
        obs = np.concatenate([r_[0] for r_ in res], 0)
        rew = np.concatenate([r_[1] for r_ in res], 0).astype(np.float64)
        done = np.concatenate([r_[2] for r_ in res], 0)
        pre = obs.copy()
        for i, r_ in enumerate(res):
            for kl, blk in r_[3].items():
                pre[self._world_envs[self.bounds[i] + int(kl)]] = blk
        infos: list[dict[str, Any]] = [{} for _ in range(self.num_envs)]
        for e in np.nonzero(done)[0]:                                   # death: end, no bootstrap (terminal = post-step obs)
            infos[e]["terminal_observation"] = pre[e]
        for k in ren:
            for e in self._world_envs[int(k)]:
                if not done[e]:
                    infos[e]["terminal_observation"] = pre[e]
                    infos[e]["TimeLimit.truncated"] = True
                    done[e] = True
        return obs, rew, done, infos

    # --- logging helpers ---
    def stats_snapshot(self) -> dict:
        """World statistics (R9World.st) of all shards concatenated in world order + online counters summed."""
        st, on = [], {k: 0.0 for k in ONLINE_KEYS}
        for sh in self.shards:
            a, b = sh.call("stats")
            st.append(a)
            for k in ONLINE_KEYS:
                on[k] += float(b.get(k, 0.0))
        out = {k: np.concatenate([s[k] for s in st], 0) for k in st[0]}
        out["online"] = on
        return out

    def memory(self) -> list[dict]:
        """Peak / private memory of this process (shard 0) and every shard worker."""
        return [sh.call("mem") for sh in self.shards]

    def learner_values(self, name: str) -> np.ndarray:
        return np.concatenate([sh.call("values", name) for sh in self.shards], 0)

    def world_params(self, k: int) -> dict:
        i, kl = self._shard_of(int(k))
        return self.shards[i].call("world_params", kl)

    def close(self) -> None:
        for sh in getattr(self, "shards", []):
            sh.close()
        self.shards = []

    # --- SB3 minimum (R8 r8_vec_env.py) ---
    def _n(self, indices) -> int:
        if indices is None:
            return self.num_envs
        if isinstance(indices, int):
            return 1
        return len(list(indices))

    def get_attr(self, attr_name: str, indices=None) -> list[Any]:
        return [getattr(self, attr_name)] * self._n(indices)

    def set_attr(self, attr_name: str, value: Any, indices=None) -> None:
        setattr(self, attr_name, value)

    def env_method(self, method_name: str, *args, indices=None, **kwargs) -> list[Any]:
        return [getattr(self, method_name)(*args, **kwargs)] * self._n(indices)

    def env_is_wrapped(self, wrapper_class, indices=None) -> list[bool]:
        return [False] * self._n(indices)

    def seed(self, seed: int | None = None) -> Sequence[None]:
        return [None] * self.num_envs

    def get_images(self):
        raise NotImplementedError("R9 replays are separate tools (results/v3/r9)")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--shard-worker":
        sys.exit(_worker_main(sys.argv[2], sys.argv[3]))
    print("usage: python -m env_v2.r9_vec_env --shard-worker <address> <key hex>  (started by R9VecEnv)", file=sys.stderr)
    sys.exit(2)
