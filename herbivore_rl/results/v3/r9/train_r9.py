"""R9 one bundle — one species of one branch learns with SB3 PPO against fixed brains in the world (design
AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 7-1~7-9, 11절, 12절 test 26).

    python results/v3/r9/train_r9.py --species deer --branch A --round 0 --decisions 30000000 --wall-hours 7 --run-name r9_A_deer_r0
    python results/v3/r9/train_r9.py --species wolf --branch B --round 3 --init ckpt/r9/B/start/r9_B_wolf_r3.zip \
        --pool ckpt/r9/B/pools/r9_B_wolf_r3.json --decisions 12000000 --wall-hours 1.5 --shards 3 --run-name r9_B_wolf_r3

Usually started by `league_r9.py` (one process per bundle; wolf bundles add shard worker processes).

- New model (round 0, no --init): PPO MlpPolicy, pi/vf 64-64 tanh, Discrete(19), lr = train.ppo.learning_rate_round0 (3e-4).
  Continue (--init zip): `PPO.load(zip, env=new R9VecEnv, learning_rate=lr)` — the keyword is needed: `load` rebuilds the
  schedule in `_setup_model()` after `__dict__.update(kwargs)` (SB3 base_class.py, 7-7). lr = train.ppo.learning_rate (1e-4)
  from round 1. The actual lr (model.learning_rate, optimizer param groups after the first update) goes to the run meta (test 26).
- Value-only first rollout (round ≥ 1 with --init, train.ppo.value_only_first_rollout): the policy side (mlp_extractor.policy_net +
  action_net) has requires_grad off for the first rollout's update — Adam skips parameters without gradients, so only the value
  net learns from it (7-7). On by default for continued bundles; `--value-only-first {auto,on,off}`.
- Determinism: torch 1 thread, MKL/OMP 1 thread, `set_random_seed(bundle_seed)` after build/load with
  bundle_seed = model_seed × 1,000,000 + round × 1,000 + species [해석 — the design fixes model seeds A 0 / B 1 only]. The world
  pool and opponents come from the VecEnv meta RNG (model seed, round, segment, species). A bundle re-run from its start copy
  gives the same weights (test 26) — interrupted bundles are re-run from the start (7-9).
- Length: --decisions (bundle-local SB3 timesteps, registered in STATUS.md after C0-9) with the wall-clock safety cap --wall-hours
  (2 × the planned time, 7-3). A cap stop is recorded (stop = wall_clock, 9-5) and the bundle still ends normally.
- Snapshots (7-3·7-4): every train.snapshot_every[species] bundle decisions (deer 10M, wolf/boar 5M), taken at the start of the
  first rollout after the threshold (= the model after that update), and at the end. Each snapshot = `<out>/<branch>/<sp>_r<round>_
  <decisions>.zip` (SB3, with optimizer) + `.npz` (r9_brains: W0..B2 + meta, the world's fixed-brain file) + `.json`. After
  snapshot i the VecEnv meta stream moves to segment i (10절 '묶음 안 판 번호' 해석). The league adds the snapshots to the pool
  only when the bundle has ended.
- Log (7-7 '5M 마다 기록 줄'): first at --log-first (default 1M), then every --log-every (5M) → <log-dir>/<run>.log.jsonl, one row of
  learner-species numbers between two world-stat snapshots (`stats_row`), PPO losses and the speed. 9-5 signals are read by
  watch_r9.py from these rows.
- NaN in the policy weights stops the bundle (R8): stop = nan, the last good snapshot is the result, exit code 1.
- Run meta `<out>/<branch>/<run>.json` (written last — its presence with stop ∈ {target, wall_clock} = bundle finished) and the
  world/opponent history `<run>.history.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"                            # 7-10: same thread count in every process (shard workers too)

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저 (OpenMP 두 벌)

import numpy as np  # noqa: E402
import torch  # noqa: E402
from stable_baselines3 import PPO  # noqa: E402
from stable_baselines3.common.callbacks import BaseCallback  # noqa: E402

from env_v2 import r9_body as B  # noqa: E402
from env_v2 import r9_brains as BR  # noqa: E402
from env_v2.r9_vec_env import R9VecEnv, species_index  # noqa: E402

CKPT = ROOT / "ckpt" / "r9"
LOGS = HERE.parent / "logs"
CFG_DEFAULT = "configs/v3_r9.yaml"
DAY = float(B.DAY_STEPS)


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
    except Exception:  # noqa: BLE001
        return "?"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def bundle_seed(model_seed: int, round_: int, sp: int) -> int:
    return int(model_seed) * 1_000_000 + int(round_) * 1_000 + int(sp)


def ppo_kwargs(cfg: dict, sp: int, lr: float, n_steps: int | None = None, batch_size: int | None = None) -> dict:
    p = cfg["train"]["ppo"]
    name = B.ALL_SPECIES[sp]
    net = [int(x) for x in p["net"]]
    return dict(n_steps=int(n_steps if n_steps is not None else cfg["train"]["n_steps"][name]),
                batch_size=int(batch_size if batch_size is not None else p["batch_size"]), n_epochs=int(p["n_epochs"]),
                learning_rate=float(lr), gamma=float(p["gamma"]), gae_lambda=float(p["gae_lambda"]),
                clip_range=float(p["clip_range"]), ent_coef=float(p["ent_coef"]), vf_coef=float(p["vf_coef"]),
                max_grad_norm=float(p["max_grad_norm"]),
                policy_kwargs=dict(net_arch=dict(pi=net, vf=net), activation_fn=torch.nn.Tanh))


def policy_params(model) -> list:
    """Policy-side parameters (frozen for the value-only first rollout): mlp_extractor.policy_net + action_net."""
    pol = model.policy
    return list(pol.mlp_extractor.policy_net.parameters()) + list(pol.action_net.parameters())


def value_params(model) -> list:
    pol = model.policy
    return list(pol.mlp_extractor.value_net.parameters()) + list(pol.value_net.parameters())


# --------------------------------------------------------------------------- #
# log rows (learner species, between two VecEnv stat snapshots)
# --------------------------------------------------------------------------- #

def _sum0(d: dict, k: str):
    return np.asarray(d[k]).sum(0)


def stats_row(a: dict, b: dict, sp: int) -> dict:
    """Learner-species numbers between two `R9VecEnv.stats_snapshot()` (world totals over all worlds). Species = the first NS of
    r9_body.ALL_SPECIES (NS from the stat shapes — S′ three, 동물 세계 six). The S′ columns keep their meaning (kills = bite deaths of
    deer and boar); the animal world adds `fauna` (kills by biter → bitten species, gores, HP lost to counters and gores)."""
    d = {k: _sum0(b, k) - _sum0(a, k) for k in b if k != "online"}
    names = B.ALL_SPECIES[:int(np.asarray(d["alive_steps"]).shape[0])]
    on = {k: b["online"][k] - a["online"][k] for k in b["online"]}
    steps = max(int(d["alive_steps"][sp]), 1)
    dec = max(int(d["decisions"][sp]), 1)
    act = d["actions"][sp]
    deaths = d["deaths"][sp]                                     # [none, bite, counter, starve]
    eaten = d["eaten_e"][sp]                                      # [grass, root, meat]
    wolf_steps = max(int(d["alive_steps"][B.WOLF]), 1)
    kills = int(d["deaths"][B.DEER][1] + d["deaths"][B.BOAR][1])  # bite deaths of prey (= wolf kills)

    def frac(n, m):
        return float(n) / float(m) if m else None

    row = dict(
        species=names[sp], agent_steps=int(d["alive_steps"][sp]), decisions=int(d["decisions"][sp]),
        bite_per_1k=1000.0 * float(deaths[1]) / steps, counter_per_1k=1000.0 * float(deaths[2]) / steps,
        starve_per_1k=1000.0 * float(deaths[3]) / steps, births_per_1k=1000.0 * float(d["birth_credits"][sp]) / steps,
        eaten_e_x1000=1000.0 * float(eaten.sum()) / steps,
        eaten_grass_x1000=1000.0 * float(eaten[B.GRASS]) / steps, eaten_root_x1000=1000.0 * float(eaten[B.ROOT]) / steps,
        eaten_meat_x1000=1000.0 * float(eaten[B.MEAT]) / steps,
        act_eat=float(act[B.EAT]) / dec, act_walk=float(act[B.WALK_FIRST:B.WALK_LAST + 1].sum()) / dec,
        act_run=float(act[B.RUN_FIRST:B.RUN_LAST + 1].sum()) / dec, act_shelter=float(act[B.SHELTER]) / dec,
        act_watch=float(act[B.WATCH]) / dec, act_hist=[float(x) / dec for x in act],
        run_gait=float(d["run_steps"][sp]) / steps, in_shelter=float(d["in_shelter_steps"][sp]) / steps,
        wall=float(d["wall_steps"][sp]) / steps, corner=float(d["corner_steps"][sp]) / steps,
        kills_per_wolf_day=float(kills) / (wolf_steps / DAY), wolf_hp_lost_per_day=float(d["wolf_hp_lost"]) / (wolf_steps / DAY),
        counters_per_1k_bites=frac(1000.0 * float(d["bites"][B.BOAR][2]), int(d["bites"].sum())),
        flee_near_wolf=frac(on.get("near_wolf_flee", 0.0), on.get("near_wolf", 0.0)), n_near_wolf=int(on.get("near_wolf", 0.0)),
        toward_wolf=frac(on.get("toward_wolf", 0.0), on.get("wolf_idle", 0.0)), n_wolf_idle=int(on.get("wolf_idle", 0.0)),
        rew_per_dec=frac(on.get("rew_sum", 0.0), on.get("rew_n", 0.0)),
        respawns=int(d["respawns"][sp].sum()), opp_near_ties=int(d["near_ties"].sum()),
        pop_deaths={n: int(d["deaths"][s][1:].sum()) for s, n in enumerate(names)},
    )
    if "bite_pairs" in d:                                         # 동물 세계 (B1: the key exists only with body_common.fauna)
        bp, gr = d["bite_pairs"], d["gore"]
        row["fauna"] = dict(
            kills_by={names[i]: {names[j]: int(bp[i, j, 0]) for j in range(len(names)) if bp[i, j, 0]}
                      for i in range(len(names)) if bp[i, :, 0].any()},
            bites_by={names[i]: {names[j]: int(bp[i, j].sum()) for j in range(len(names)) if bp[i, j].sum()}
                      for i in range(len(names)) if bp[i].sum()},
            gore={names[i]: {names[j]: [int(gr[i, j, 0]), int(gr[i, j, 1])] for j in range(len(names)) if gr[i, j].sum()}
                  for i in range(len(names)) if gr[i].sum()},
            bite_in_shelter=int(d["bite_in_shelter"].sum()),
            strike_hp_by={names[i]: float(d["strike_hp_by"][i]) for i in range(len(names)) if d["strike_hp_by"][i]},
        )
    return row


# --------------------------------------------------------------------------- #
# callback
# --------------------------------------------------------------------------- #

class R9Callback(BaseCallback):
    def __init__(self, tr: "Trainer"):
        super().__init__()
        self.tr = tr
        self.t0 = time.time()
        self.n0 = tr.n0
        self.next_log = tr.log_first if tr.log_first > 0 else tr.log_every
        self.next_snap = tr.snap_every
        self.snap = tr.venv.stats_snapshot()
        self.snap_t, self.snap_n = time.time(), 0
        self.stop_reason = None
        self.rollouts = 0
        self.frozen = False
        self.lr_seen: list[float] = []
        self.last_train: dict = {}                   # train/* of the latest PPO update (the logger dumps them every iteration)
        self.train_logged = True

    @property
    def local(self) -> int:
        return int(self.num_timesteps) - self.n0

    def _on_training_start(self) -> None:
        if self.tr.value_only_first:
            for p in policy_params(self.model):
                p.requires_grad_(False)
            self.frozen = True

    def capture_train(self) -> None:
        lg = self.model.logger.name_to_value
        got = {k: float(v) for k, v in lg.items() if k.startswith("train/")}
        if got:
            self.last_train = got
            self.train_logged = False

    def _on_rollout_start(self) -> None:
        if self.rollouts >= 1:
            if self._nan():                              # right after an update: never snapshot / roll out NaN weights
                self.stop_reason = "nan"
                self.log_row(dict(nan=True))
                raise FloatingPointError("정책 가중치에 NaN — 묶음을 멈춘다")
            self.capture_train()
            if self.frozen:
                for p in policy_params(self.model):
                    p.requires_grad_(True)
                self.frozen = False
            g = self.model.policy.optimizer.param_groups
            self.lr_seen.append(float(g[0]["lr"]))
            if self.local >= self.next_snap:
                self.tr.snapshot(self.local)
                self.next_snap = (self.local // self.tr.snap_every + 1) * self.tr.snap_every
        self.rollouts += 1

    def log_row(self, extra: dict | None = None) -> dict:
        now = self.tr.venv.stats_snapshot()
        row = stats_row(self.snap, now, self.tr.sp)
        dt = time.time() - self.snap_t
        e = self.tr.venv.learner_values("E")
        row.update(run=self.tr.run, round=self.tr.round, branch=self.tr.branch, timesteps=self.local,
                   cum_timesteps=int(self.num_timesteps), wall_min=(time.time() - self.t0) / 60.0,
                   dec_per_s=(self.local - self.snap_n) / max(dt, 1e-9), E_median=float(np.median(e)) if len(e) else None,
                   R_median=float(np.median(self.tr.venv.learner_values("R"))) if len(e) else None,
                   value_only=self.frozen)
        lg = self.last_train
        for k in ("train/entropy_loss", "train/value_loss", "train/policy_gradient_loss", "train/approx_kl", "train/clip_fraction",
                  "train/explained_variance", "train/learning_rate"):
            if k in lg:
                row[k.split("/")[1]] = float(lg[k])
        if lg:
            self.train_logged = True
        if extra:
            row.update(extra)
        with self.tr.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[{self.tr.run}] {row['timesteps'] / 1e6:.2f}M {row['wall_min']:.1f}분 {row['dec_per_s']:.0f}/s "
              f"물림 {row['bite_per_1k']:.2f} 반격 {row['counter_per_1k']:.2f} 굶음 {row['starve_per_1k']:.2f} 출산 {row['births_per_1k']:.2f} "
              f"먹음 {row['eaten_e_x1000']:.2f} 뛰기 {row['act_run']:.2f} 은신 {row['in_shelter']:.2f} 하루잡이 {row['kills_per_wolf_day']:.3f} "
              f"E중앙 {row['E_median']}", flush=True)
        self.snap, self.snap_t, self.snap_n = now, time.time(), self.local
        return row

    def _nan(self) -> bool:
        return any(not torch.isfinite(p).all() for p in self.model.policy.parameters())

    def _on_step(self) -> bool:
        if self.local >= self.next_log:
            self.log_row()
            self.next_log = (self.local // self.tr.log_every + 1) * self.tr.log_every
        if time.time() - self.t0 > self.tr.wall_s:
            self.stop_reason = "wall_clock"
            return False
        return True

    def _on_rollout_end(self) -> None:
        if self._nan():
            self.stop_reason = "nan"
            self.log_row(dict(nan=True))
            raise FloatingPointError("정책 가중치에 NaN — 묶음을 멈춘다")


# --------------------------------------------------------------------------- #
# trainer
# --------------------------------------------------------------------------- #

class Trainer:
    def __init__(self, args):
        self.args = args
        torch.set_num_threads(1)
        cfg_path = Path(args.config)
        self.cfg_path = cfg_path if cfg_path.is_absolute() else ROOT / cfg_path
        cfg = B.load_r9_config(self.cfg_path)
        if args.gamma is not None:
            cfg = B.override(cfg, {"train": {"ppo": {"gamma": float(args.gamma)}}})
        if args.fallback_f:
            cfg = B.override(cfg, {"reward": {"fallback_f": {"enabled": True}}})
        self.cfg = cfg
        tr = cfg["train"]
        self.sp = species_index(args.species)
        self.name = B.ALL_SPECIES[self.sp]
        if self.name not in B.species_of(cfg):
            raise ValueError(f"--species {self.name} is not in the config species {B.species_of(cfg)} ({self.cfg_path})")
        self.branch = str(args.branch)
        self.round = int(args.round)
        if args.model_seed is None and self.branch not in tr["model_seeds"]:
            raise ValueError(f"branch {self.branch!r} is not in train.model_seeds {tr['model_seeds']} — pass --model-seed (C0-10 etc.)")
        self.model_seed = int(args.model_seed if args.model_seed is not None else tr["model_seeds"][self.branch])
        self.run = args.run_name
        self.out = (Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out) / self.branch
        self.log_dir = Path(args.log_dir) if Path(args.log_dir).is_absolute() else ROOT / args.log_dir
        self.out.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.out / f"{self.run}.json"
        self.log_path = self.log_dir / f"{self.run}.log.jsonl"
        self.skip = self.meta_path.exists() and not args.overwrite
        if self.skip:                                # finished bundle: do not build worlds / workers
            return
        self.total = int(args.decisions)
        self.wall_s = float(args.wall_hours) * 3600.0
        self.snap_every = int(args.snapshot_every if args.snapshot_every is not None else tr["snapshot_every"][self.name])
        self.log_first = int(args.log_first)
        self.log_every = int(args.log_every)
        self.pool = {}
        self.pool_file = None
        if args.pool:
            pf = Path(args.pool) if Path(args.pool).is_absolute() else ROOT / args.pool
            self.pool_file = pf
            raw = json.loads(pf.read_text(encoding="utf-8"))
            for k, lst in raw.get("pool", raw).items():
                self.pool[k] = [str(p if Path(p).is_absolute() else ROOT / p) for p in lst]
        self.shares = json.loads(args.shares) if args.shares else None
        seeds = None
        if args.seeds:
            seeds = range(int(args.seeds[0]), int(args.seeds[1]))
        self.venv = R9VecEnv(cfg, self.sp, model_seed=self.model_seed, round_=self.round, segment=0, pool=self.pool,
                             shares=self.shares, seeds=seeds, num_worlds=args.num_worlds, shards=int(args.shards),
                             worker_log_dir=self.log_dir)
        p = tr["ppo"]
        self.lr = float(p["learning_rate_round0"] if self.round == 0 else p["learning_rate"])
        if args.learning_rate is not None:
            self.lr = float(args.learning_rate)
        self.bseed = bundle_seed(self.model_seed, self.round, self.sp)
        self.init = None
        self.init_species = None
        if args.init:
            ip = Path(args.init) if Path(args.init).is_absolute() else ROOT / args.init
            self.init = ip
            # learning_rate and gamma as keywords: load rebuilds the schedule / rollout buffer from them (7-7; γ = the config
            # value chosen by C0-10 — a zip saved with another γ follows the config, not the zip)
            kw = dict(learning_rate=self.lr, gamma=float(p["gamma"]))
            if args.init_species:
                # 동물 6-1: a start copy of another (or the same) species' zip — the I/O is the same (115 → 19); the rollout length
                # follows this learner's train.n_steps (the zip's own n_steps belongs to its old world size)
                if args.init_species not in B.ALL_SPECIES:
                    raise ValueError(f"--init-species {args.init_species!r} is not a species name {B.ALL_SPECIES}")
                self.init_species = str(args.init_species)
                kw["n_steps"] = int(args.n_steps if args.n_steps is not None else tr["n_steps"][self.name])
            self.model = PPO.load(ip, env=self.venv, device="cpu", **kw)
            self.model.set_random_seed(self.bseed)
        else:
            self.model = PPO("MlpPolicy", self.venv, seed=self.bseed, device="cpu", verbose=0,
                             **ppo_kwargs(cfg, self.sp, self.lr, args.n_steps, args.batch_size))
        vo = args.value_only_first
        self.value_only_first = (self.init is not None and bool(p.get("value_only_first_rollout", True))) if vo == "auto" else vo == "on"
        self.n0 = int(self.model.num_timesteps)
        self.snapshots: list[dict] = []

    def snapshot(self, local: int) -> dict:
        stem = f"{self.name}_r{self.round}_{local}"
        z = self.out / f"{stem}.zip"
        n = self.out / f"{stem}.npz"
        self.model.save(z)
        meta = BR.brain_meta(self.cfg, self.sp, self.branch, self.round, local, z)
        BR.save_brain(n, BR.extract_sb3(self.model), meta)
        info = dict(decisions=local, cum_timesteps=int(self.model.num_timesteps), zip=rel(z), npz=rel(n),
                    sha256_zip=sha256(z), sha256_npz=sha256(n), segment=len(self.snapshots), run=self.run,
                    io_hash=meta["io_hash"], body_hash=meta["body_hash"])
        (self.out / f"{stem}.json").write_text(json.dumps(dict(info, brain=meta, species=self.name, branch=self.branch,
                                                               round=self.round), ensure_ascii=False, indent=1), encoding="utf-8")
        self.snapshots.append(info)
        self.venv.set_segment(len(self.snapshots))
        print(f"[{self.run}] 판 {stem} ({local / 1e6:.2f}M)", flush=True)
        return info

    def run_bundle(self) -> int:
        a = self.args
        if self.skip:
            print(f"이미 끝난 묶음: {self.meta_path} — 덮어쓰지 않는다 (--overwrite)", flush=True)
            return 2
        if self.log_path.exists():
            self.log_path.unlink()
        cb = R9Callback(self)
        t0 = time.time()
        print(f"[{self.run}] 시작 {time.strftime('%Y-%m-%d %H:%M:%S')} {self.name} 갈래 {self.branch} 바퀴 {self.round} "
              f"목표 {self.total / 1e6:.2f}M 상한 {a.wall_hours}h 환경 {self.venv.num_envs} 세계 {self.venv.K} 조각 {len(self.venv.shards)} "
              f"lr {self.lr} γ {self.model.gamma} 가치망만 첫 롤아웃 {self.value_only_first} 시작 {rel(self.init) if self.init else '새로'} "
              f"git {git_sha()}", flush=True)
        err = None
        try:
            self.model.learn(total_timesteps=self.total, callback=cb, progress_bar=False, reset_num_timesteps=self.init is None)
        except FloatingPointError as e:
            err = str(e)
        wall = time.time() - t0
        local = int(self.model.num_timesteps) - self.n0
        if cb.stop_reason != "nan":
            cb.capture_train()                       # the last update is not followed by a rollout start
            if cb.snap_n < local or not cb.train_logged:
                cb.log_row(dict(final=True))         # (agent_steps 0 = no new steps, only the last PPO numbers)
            if not self.snapshots or self.snapshots[-1]["decisions"] != local:
                self.snapshot(local)
        g = self.model.policy.optimizer.param_groups
        mem = self.venv.memory()                       # [this process, shard workers…] peak / private MB (C0-9)
        hist_path = self.out / f"{self.run}.history.json"
        hist_path.write_text(json.dumps(dict(seed_history=self.venv.seed_history, history=self.venv.history), ensure_ascii=False),
                             encoding="utf-8")
        labels: dict = {}
        for h in self.venv.history:
            for s, o in h["opponents"].items():
                key = f"{s}:{o['label']}:{'stoch' if o['stochastic'] else 'greedy'}"
                labels[key] = labels.get(key, 0) + 1
        meta = dict(run=self.run, species=self.name, branch=self.branch, round=self.round, model_seed=self.model_seed,
                    bundle_seed=self.bseed, config=rel(self.cfg_path), config_digest=BR.config_digest(self.cfg),
                    target=self.total, timesteps=local, cum_timesteps=int(self.model.num_timesteps), wall_s=wall,
                    dec_per_s=local / max(wall, 1e-9), stop=cb.stop_reason or "target", error=err,
                    num_envs=self.venv.num_envs, num_worlds=self.venv.K, shards=len(self.venv.shards), reset_decisions=self.venv.T,
                    num_resets=self.venv.num_resets, n_steps=int(self.model.n_steps), batch_size=int(self.model.batch_size),
                    gamma=float(self.model.gamma), learning_rate=float(self.model.learning_rate),
                    optimizer_lr=sorted({float(x["lr"]) for x in g}), lr_seen=sorted(set(cb.lr_seen)),
                    value_only_first=self.value_only_first, init=rel(self.init) if self.init else None,
                    init_sha256=sha256(self.init) if self.init else None, init_species=self.init_species,
                    config_species=list(B.species_of(self.cfg)),
                    variants=([dict(k=k, variant=v) for k, v in enumerate(self.venv.variant) if v]
                              if self.cfg["train"].get("variants") else None),
                    pool_file=rel(self.pool_file) if self.pool_file else None,
                    pool={k: [dict(path=rel(Path(p)), sha256=sha256(Path(p))) for p in v] for k, v in self.pool.items()},
                    shares=self.shares, opponent_labels=labels, snapshots=self.snapshots,
                    seeds_seen=len({s for h in self.venv.seed_history for s in h}), history=rel(hist_path),
                    fallback_f=bool(self.cfg["reward"]["fallback_f"]["enabled"]), ppo=self.cfg["train"]["ppo"],
                    io_hash=B.hash_hex(B.io_hash()), body_hash=B.hash_hex(B.body_hash(self.cfg, self.sp)),
                    memory=mem, git=git_sha(), finished=time.strftime("%Y-%m-%d %H:%M:%S"))
        self.venv.close()
        self.meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{self.run}] 끝 {meta['finished']} {local / 1e6:.2f}M 결정 {wall / 60:.1f}분 {meta['dec_per_s']:.0f}/s 멈춤 {meta['stop']}",
              flush=True)
        return 0 if err is None else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=CFG_DEFAULT)
    ap.add_argument("--species", required=True, choices=list(B.ALL_SPECIES[:B.STAGE1_MAX_SPECIES]),
                    help="배우는 종 (설정 species 에 있어야 함 — 물소·표범·여우는 configs/v3_r9_fauna.yaml)")
    ap.add_argument("--branch", required=True, help="갈래 A | B (모델 시드 = train.model_seeds)")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--decisions", type=int, required=True, help="묶음 결정 수 (SB3 timesteps, 이 묶음 안)")
    ap.add_argument("--wall-hours", type=float, required=True, help="벽시계 안전 상한")
    ap.add_argument("--run-name", required=True)
    ap.add_argument("--init", default=None, help="이어 배울 시작 사본 zip (없으면 새 모델)")
    ap.add_argument("--init-species", default=None,
                    help="동물 6-1: --init zip 이 배운 종 이름 (다른 종 zip 에서 출발 — 롤아웃 길이는 배우는 종 train.n_steps)")
    ap.add_argument("--pool", default=None, help="상대 풀 JSON {'pool': {종: [npz …]}} (묶음 시작 때 고정)")
    ap.add_argument("--shares", default=None, help="상대 몫 덮어쓰기 JSON {종: {current, past, rule, always_eat}} (9-4 처방, C0-10)")
    ap.add_argument("--shards", type=int, default=1, help="세계 조각 수 (늑대 묶음 2~3, 7-3)")
    ap.add_argument("--model-seed", type=int, default=None)
    ap.add_argument("--seeds", type=int, nargs=2, default=None, help="세계 시드 풀 [하, 상) (기본 train.seeds — 학습 풀)")
    ap.add_argument("--out", default=str(CKPT))
    ap.add_argument("--log-dir", default=str(LOGS))
    ap.add_argument("--snapshot-every", type=int, default=None)
    ap.add_argument("--log-first", type=int, default=1_000_000)
    ap.add_argument("--log-every", type=int, default=5_000_000)
    ap.add_argument("--gamma", type=float, default=None, help="C0-10 후보 (없으면 설정)")
    ap.add_argument("--fallback-f", action="store_true", help="대비책 F 켜기 (6-1, 관문에서 막힌 때만)")
    ap.add_argument("--learning-rate", type=float, default=None, help="시험용 덮어쓰기")
    ap.add_argument("--value-only-first", choices=("auto", "on", "off"), default="auto")
    ap.add_argument("--num-worlds", type=int, default=None, help="시험·스모크용 (기본 train.worlds)")
    ap.add_argument("--n-steps", type=int, default=None, help="시험용 (새 모델만)")
    ap.add_argument("--batch-size", type=int, default=None, help="시험용 (새 모델만)")
    ap.add_argument("--overwrite", action="store_true")
    return ap


def is_transient(exc: BaseException) -> bool:
    """Failures that are not a property of the seed (Fix 단계 검토 low): commit-limit MemoryError (11-05 사고 꼴), a lost shard
    worker (start failure, pipe timeout, EOF / broken pipe, worker MemoryError). Same-seed re-runs of these are not the same
    failure, so the league re-runs the bundle (bounded); NaN and other errors stay 'error' (리그가 멈추고 사람이 본다)."""
    from env_v2.r9_vec_env import ShardWorkerLost

    e: BaseException | None = exc
    while e is not None:
        if isinstance(e, (MemoryError, ShardWorkerLost, EOFError, BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return True
        e = e.__cause__ or e.__context__
    return False


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    tr = None
    try:
        tr = Trainer(args)
        return tr.run_bundle()
    except Exception as exc:  # noqa: BLE001 — a crash leaves an end record so the league knows what happened
        import traceback

        out = (Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out) / str(args.branch)
        mp = out / f"{args.run_name}.json"
        tb = traceback.format_exc()
        print(tb, flush=True)
        stop = "cut" if is_transient(exc) else "error"     # cut → the league re-runs from the start copy; error → it stops
        if not mp.exists():
            out.mkdir(parents=True, exist_ok=True)
            mp.write_text(json.dumps(dict(run=args.run_name, species=args.species, branch=args.branch, round=args.round,
                                          stop=stop, error=tb, snapshots=[], finished=time.strftime("%Y-%m-%d %H:%M:%S")),
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        return 1
    finally:
        if tr is not None and getattr(tr, "venv", None) is not None:
            tr.venv.close()                          # shard workers end with the bundle (also on errors)


if __name__ == "__main__":
    sys.exit(main())
