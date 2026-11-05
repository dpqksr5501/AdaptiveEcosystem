"""R8 학습 — SB3 PPO, 처음부터 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R8_LEARN_DANGER_DESIGN.md 7절).

    python results/v3/r8/train_r8.py --config configs/v3_r8_pilot.yaml --seed 0 --run-name r8_p_s0
    python results/v3/r8/train_r8.py --config configs/v3_r8_pilot.yaml --seed 0 --steps 1000000 --run-name r8_smoke --wall-hours 0.5

- 망: 정책·가치 따로 64-64 tanh(MlpPolicy), Discrete(11), 마스크 없음. 관측 65 (env_v2/r8_world.py OBS_NAMES).
- 양: --steps(결정 = SB3 timesteps, 없으면 설정 train.total_decisions) 와 벽시계 상한 --wall-hours(없으면 train.wall_hours) 가운데 먼저 닿는 쪽.
  멈추면 그 자리 모델을 끝 모델로 저장한다.
- 체크포인트 train.ckpt_every 마다 ckpt/r8/<이름>_<k>m.zip, 끝 ckpt/r8/<이름>.zip · 메타 .json.
- 기록 train.log_first(1M) 한 번, 그 뒤 train.log_every(5M) 마다 results/v3/r8/logs/<이름>.log.jsonl: 그 사이 잡힘·굶음·번식(1000 사슴-스텝당),
  먹은 에너지(사슴-스텝당 × 1000), 행동 몫, 은신처 안 몫, 온라인 도망 몫(가장 가까운 느낀 동물이 늑대/짐승일 때, 15 단위 안 — 숨은 종류는
  기록에만 쓴다), 결정당 속도.
- 정책 가중치에 NaN 이 생기면 멈추고 기록에 남긴다(끝 모델은 NaN 전 마지막 체크포인트를 쓴다).
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저 (OpenMP 두 벌)

import numpy as np  # noqa: E402
import torch  # noqa: E402
from stable_baselines3 import PPO  # noqa: E402
from stable_baselines3.common.callbacks import BaseCallback  # noqa: E402

from env_v2.r8_vec_env import R8VecEnv  # noqa: E402
from env_v2.r8_world import ACTION_NAMES, K_BEAST, K_WOLF, OBS_DIM, load_r8_config  # noqa: E402

CKPT = ROOT / "ckpt" / "r8"
LOGS = HERE.parent / "logs"


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "?"


def make_model(venv: R8VecEnv, cfg: dict, seed: int, tb: str | None = None) -> PPO:
    p = cfg["train"]["ppo"]
    net = [int(x) for x in p["net"]]
    return PPO("MlpPolicy", venv, n_steps=int(p["n_steps"]), batch_size=int(p["batch_size"]), n_epochs=int(p["n_epochs"]),
               learning_rate=float(p["learning_rate"]), gamma=float(p["gamma"]), gae_lambda=float(p["gae_lambda"]),
               clip_range=float(p["clip_range"]), ent_coef=float(p["ent_coef"]), vf_coef=float(p["vf_coef"]),
               max_grad_norm=float(p["max_grad_norm"]),
               policy_kwargs=dict(net_arch=dict(pi=net, vf=net), activation_fn=torch.nn.Tanh),
               seed=seed, device="cpu", verbose=0, tensorboard_log=tb)


def stats_row(a: dict, b: dict) -> dict:
    """두 통계 사진(R8World.stats_snapshot) 사이의 값."""
    d = {k: (b[k] - a[k]).sum(0) for k in b}
    ds = max(int(d["deer_steps"]), 1)
    dec = max(int(d["decisions"]), 1)
    act = d["actions"]
    fc = d["flee_cnt"]                                      # [종류, 띠, 도망]

    def frac(kind):
        n = fc[kind].sum()
        return float(fc[kind, :, 1].sum() / n) if n else None

    return dict(
        deer_steps=int(d["deer_steps"]),
        caught_per_1k=1000.0 * float(d["caught_wolf"] + d["caught_bear"]) / ds,
        starved_per_1k=1000.0 * float(d["starved"]) / ds,
        repro_per_1k=1000.0 * float(d["repro"]) / ds,
        eaten_e_x1000=1000.0 * float(d["eaten_e"]) / ds,
        in_shelter=float(d["in_shelter"]) / ds,
        act_eat=float(act[0]) / dec, act_run=float(act[1:9].sum()) / dec, act_shelter=float(act[9]) / dec, act_watch=float(act[10]) / dec,
        flee_wolf=frac(K_WOLF), flee_beast=frac(K_BEAST),
        n_wolf=int(fc[K_WOLF].sum()), n_beast=int(fc[K_BEAST].sum()),
        flee_wolf_bands=[float(fc[K_WOLF, b_, 1] / max(fc[K_WOLF, b_].sum(), 1)) for b_ in range(3)],
        flee_beast_bands=[float(fc[K_BEAST, b_, 1] / max(fc[K_BEAST, b_].sum(), 1)) for b_ in range(3)],
        act_hist=[float(x) / dec for x in act],
    )


class R8Callback(BaseCallback):
    def __init__(self, venv: R8VecEnv, run: str, total: int, wall_s: float, ckpt_every: int, log_first: int, log_every: int,
                 log_path: Path):
        super().__init__()
        self.venv, self.run, self.total, self.wall_s = venv, run, total, wall_s
        self.ckpt_every, self.log_first, self.log_every = ckpt_every, log_first, log_every
        self.log_path = log_path
        self.t0 = time.time()
        self.next_ckpt = ckpt_every
        self.next_log = log_first if log_first > 0 else log_every
        self.snap = venv.world.stats_snapshot()
        self.snap_t, self.snap_n = time.time(), 0
        self.stop_reason = None
        self.last_ckpt: Path | None = None

    def _log(self, extra: dict | None = None) -> None:
        now = self.venv.world.stats_snapshot()
        row = stats_row(self.snap, now)
        dt = time.time() - self.snap_t
        row.update(run=self.run, timesteps=int(self.num_timesteps), wall_min=(time.time() - self.t0) / 60.0,
                   dec_per_s=(self.num_timesteps - self.snap_n) / max(dt, 1e-9))
        lg = self.model.logger.name_to_value if self.model is not None else {}
        for k in ("train/entropy_loss", "train/value_loss", "train/approx_kl", "train/clip_fraction", "train/explained_variance"):
            if k in lg:
                row[k.split("/")[1]] = float(lg[k])
        if extra:
            row.update(extra)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[{self.run}] {row['timesteps'] / 1e6:.1f}M {row['wall_min']:.1f}분 {row['dec_per_s']:.0f}/s "
              f"잡힘 {row['caught_per_1k']:.2f} 굶음 {row['starved_per_1k']:.2f} 번식 {row['repro_per_1k']:.2f} 먹음 {row['eaten_e_x1000']:.2f} "
              f"뛰기 {row['act_run']:.2f} 은신 {row['act_shelter']:.2f} 살핌 {row['act_watch']:.2f} 도망(늑대 {row['flee_wolf']} 짐승 {row['flee_beast']})",
              flush=True)
        self.snap, self.snap_t, self.snap_n = now, time.time(), self.num_timesteps

    def _nan(self) -> bool:
        for p in self.model.policy.parameters():
            if not torch.isfinite(p).all():
                return True
        return False

    def _on_step(self) -> bool:
        n = self.num_timesteps
        if n >= self.next_log:
            self._log()
            self.next_log = (n // self.log_every + 1) * self.log_every
        if n >= self.next_ckpt:
            path = CKPT / f"{self.run}_{n // 1_000_000}m.zip"
            self.model.save(path)
            self.last_ckpt = path
            self.next_ckpt = (n // self.ckpt_every + 1) * self.ckpt_every
        if time.time() - self.t0 > self.wall_s:
            self.stop_reason = "wall_clock"
            return False
        return True

    def _on_rollout_end(self) -> None:
        if self._nan():
            self.stop_reason = "nan"
            self._log(dict(nan=True))
            raise FloatingPointError("정책 가중치에 NaN — 학습을 멈춘다")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int, default=0, help="모델 시드 = 세계 고르기 메타 난수 시드")
    ap.add_argument("--steps", type=int, default=None, help="결정 수 (없으면 train.total_decisions)")
    ap.add_argument("--wall-hours", type=float, default=None)
    ap.add_argument("--run-name", required=True)
    ap.add_argument("--tb", default=None, help="텐서보드 폴더 (선택)")
    ap.add_argument("--overwrite", action="store_true", help="같은 이름의 끝 모델이 있어도 덮어쓴다")
    ap.add_argument("--log-every", type=int, default=None, help="기록 간격 (없으면 train.log_every)")
    ap.add_argument("--log-first", type=int, default=None, help="첫 기록 (없으면 train.log_first)")
    args = ap.parse_args(argv)

    torch.set_num_threads(1)
    cfg = load_r8_config(ROOT / args.config if not Path(args.config).is_absolute() else args.config)
    tr = cfg["train"]
    total = int(args.steps if args.steps is not None else tr["total_decisions"])
    wall_h = float(args.wall_hours if args.wall_hours is not None else tr["wall_hours"])
    CKPT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    final = CKPT / f"{args.run_name}.zip"
    if final.exists() and not args.overwrite:
        print(f"이미 있는 실행: {final} — 덮어쓰지 않는다 (--overwrite)", flush=True)
        return 2
    log_path = LOGS / f"{args.run_name}.log.jsonl"
    if log_path.exists():
        log_path.unlink()

    venv = R8VecEnv(cfg, meta_seed=args.seed)
    model = make_model(venv, cfg, args.seed, args.tb)
    log_first = int(args.log_first if args.log_first is not None else tr["log_first"])
    log_every = int(args.log_every if args.log_every is not None else tr["log_every"])
    cb = R8Callback(venv, args.run_name, total, wall_h * 3600.0, int(tr["ckpt_every"]), log_first, log_every, log_path)
    t0 = time.time()
    print(f"[{args.run_name}] 시작 {time.strftime('%Y-%m-%d %H:%M:%S')} 설정 {args.config} 시드 {args.seed} 목표 {total / 1e6:.0f}M 상한 {wall_h}h "
          f"개체 {venv.num_envs} 관측 {OBS_DIM} git {git_sha()}", flush=True)
    err = None
    try:
        model.learn(total_timesteps=total, callback=cb, progress_bar=False)
    except FloatingPointError as e:
        err = str(e)
    wall = time.time() - t0
    done_n = int(model.num_timesteps)
    if cb.stop_reason != "nan":
        model.save(final)
        if cb.snap_n < done_n:
            cb._log(dict(final=True))
    elif cb.last_ckpt is not None:
        import shutil

        shutil.copyfile(cb.last_ckpt, final)
    meta = dict(run=args.run_name, config=args.config, seed=args.seed, target=total, timesteps=done_n, wall_s=wall,
                dec_per_s=done_n / max(wall, 1e-9), stop=cb.stop_reason or "target", error=err, num_envs=venv.num_envs,
                num_worlds=venv.K, reset_decisions=venv.T, num_resets=venv.num_resets, obs_dim=OBS_DIM, actions=list(ACTION_NAMES),
                ppo=tr["ppo"], git=git_sha(), finished=time.strftime("%Y-%m-%d %H:%M:%S"),
                seeds_seen=sorted({s for h in venv.seed_history for s in h}))
    final.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{args.run_name}] 끝 {meta['finished']} {done_n / 1e6:.2f}M 결정 {wall / 60:.1f}분 {meta['dec_per_s']:.0f}/s 멈춤 {meta['stop']}", flush=True)
    return 0 if err is None else 1


if __name__ == "__main__":
    sys.exit(main())
