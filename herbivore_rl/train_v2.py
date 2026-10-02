"""V2 PPO 학습 (계획서 4.7).

    python train_v2.py --steps 20000000 --seed 0 --run-name v2_0_s0 --save-at 10000000

v1 train.py 와 다른 점:
- 독립 세계 K 개를 묶은 MultiWorldVecEnv 로 학습한다 (env_v2/vec_env.py). 세계는 주기적으로 바뀐다
- 무작위 초기화가 기본이다. v1 은 Utility 모방에서 시작해 그 근처에 머물렀다 (계획서 T3)
- 롤아웃 배치를 v1 과 같게(32,768) 두려고 세계당 n_steps = 256 / K 로 줄인다
- 행동 차원별 평균·표준편차·log_std, 선형 R², 월드 상태를 기록하고, 실행 명령과 설정을 함께 저장한다

PPO 구조(7-64-64-4, tanh)와 기본 하이퍼파라미터는 v1 의 `train.PPO_KWARGS` / `make_model` 을 그대로 쓴다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from stable_baselines3.common.callbacks import BaseCallback

from env_v2.config import load_v2_config
from env_v2.vec_env import MultiWorldVecEnv, sigmoid
from env_v2.world import ACT_DIM, OBS_DIM
from train import load_tuned, make_model

ROOT = Path(__file__).resolve().parent
CKPT = ROOT / "ckpt" / "v2"
ACT_NAMES = ["forage", "cohesion", "flee_dist", "cover"]


def linear_r2(obs: np.ndarray, act: np.ndarray) -> np.ndarray:
    """행동 차원마다 관측의 선형 회귀로 설명되는 분산 비율. 1에 가까우면 '선형 규칙 수준'이다."""
    X = np.c_[obs, np.ones(len(obs))]
    coef, *_ = np.linalg.lstsq(X, act, rcond=None)
    res = act - X @ coef
    var = act.var(0)
    return np.where(var > 0, 1.0 - res.var(0) / np.maximum(var, 1e-12), np.nan)


class BehaviorLogCallbackV2(BaseCallback):
    """롤아웃마다 행동 분포·정책 분산·월드 상태를, `r2_every` 스텝마다 선형 R² 를 기록한다."""

    def __init__(self, r2_every: int = 1_000_000, save_at: list[int] | None = None,
                 save_prefix: Path | None = None):
        super().__init__()
        self.r2_every = r2_every
        self._next_r2 = r2_every
        self.save_at = sorted(save_at or [])
        self.save_prefix = save_prefix
        self.r2_history: list[dict] = []

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        buf = self.model.rollout_buffer
        raw = buf.actions.reshape(-1, ACT_DIM)
        a = sigmoid(np.clip(raw, -3.0, 3.0))
        for i, name in enumerate(ACT_NAMES):
            self.logger.record(f"act/{name}_mean", float(a[:, i].mean()))
            self.logger.record(f"act/{name}_std", float(a[:, i].std()))
        log_std = self.model.policy.log_std.detach().cpu().numpy()
        for i, name in enumerate(ACT_NAMES):
            self.logger.record(f"policy/{name}_log_std", float(log_std[i]))
        self.logger.record("rollout/reward_per_step", float(buf.rewards.mean()))

        env = self.training_env
        worlds = env.worlds
        self.logger.record("world/mean_energy", float(np.mean([w.energy.mean() for w in worlds])))
        self.logger.record("world/in_cover_frac", float(np.mean([w._g["in_cover"].mean() for w in worlds])))
        self.logger.record("world/kill_ema", float(np.mean([w.pred_ema for w in worlds])))
        self.logger.record("world/resets", float(env.num_resets))

        if self.num_timesteps >= self._next_r2:
            # 버퍼의 행동은 정책 분포에서 뽑은 값이라 잡음이 섞여 R² 가 낮게 나온다. 정책 평균(결정적
            # 행동)으로 잰다 — 진단 도구(diagnose_v2.py)와 같은 기준이다.
            obs = buf.observations.reshape(-1, OBS_DIM)
            det, _ = self.model.predict(obs, deterministic=True)
            r2 = linear_r2(obs.astype(np.float64), sigmoid(np.clip(det, -3.0, 3.0)))
            row = {"timesteps": int(self.num_timesteps)}
            for i, name in enumerate(ACT_NAMES):
                self.logger.record(f"r2/{name}", float(r2[i]))
                row[name] = float(r2[i])
            self.r2_history.append(row)
            self._next_r2 += self.r2_every

        while self.save_at and self.num_timesteps >= self.save_at[0]:
            at = self.save_at.pop(0)
            if self.save_prefix is not None:
                path = self.save_prefix.with_name(f"{self.save_prefix.stem}_{at / 1e6:g}m.zip")
                self.model.save(path)
                print(f"  중간 저장 {at:,} → {path.name} (실제 {self.num_timesteps:,})", flush=True)


def default_run_name(cfg, seed: int, steps: int) -> str:
    """--run-name 이 없을 때의 실행 이름. 설정 version 을 넣어 버전마다 체크포인트·TensorBoard 이름이 갈린다
    (v2.0 → v2_0_s0_20m 그대로, v2.0b → v2_0b_s0_20m). version 은 선택 키라 없으면 2.0 으로 본다."""
    ver = str(cfg.v2.get("version") or "2.0").replace(".", "_")
    return f"v{ver}_s{seed}_{steps // 1_000_000}m"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="V2 PPO 학습 (다중 세계)")
    p.add_argument("--steps", type=int, default=20_000_000)
    p.add_argument("--seed", type=int, default=0, help="PPO 시드이자 세계 선택 시드(meta_seed)")
    p.add_argument("--run-name", default=None, help="기본 v<설정 version>_s<seed>_<M>m (예: v2_0b_s0_20m)")
    p.add_argument("--out", default=None, help="기본 ckpt/v2/<run-name>.zip")
    p.add_argument("--config", default=None, help="기본 configs/v2.yaml")
    p.add_argument("--ppo-config", default=str(ROOT / "configs" / "ppo_best.yaml"))
    p.add_argument("--init", default=None, help="가중치를 옮겨 올 체크포인트. 기본은 무작위 초기화")
    p.add_argument("--num-worlds", type=int, default=None)
    p.add_argument("--reset-interval", type=int, default=None)
    p.add_argument("--save-at", type=int, nargs="*", default=[], help="중간 저장 시점(timestep)")
    p.add_argument("--threads", type=int, default=4, help="torch 스레드 수 (병렬 실행 시 줄인다)")
    p.add_argument("--tb", default=str(ROOT / "runs" / "v2"))
    args = p.parse_args(argv)

    torch.set_num_threads(args.threads)
    cfg = load_v2_config(args.config)
    venv = MultiWorldVecEnv(cfg, num_worlds=args.num_worlds, reset_interval=args.reset_interval,
                            meta_seed=args.seed)
    rollout_world_steps = int(cfg.v2["train"].get("rollout_world_steps", 256))
    n_steps = max(1, rollout_world_steps // venv.K)

    tuned = load_tuned(args.ppo_config)
    run = args.run_name or default_run_name(cfg, args.seed, args.steps)
    out = Path(args.out) if args.out else CKPT / f"{run}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    model = make_model(venv, tensorboard_log=args.tb, n_steps=n_steps, seed=args.seed, **tuned)
    if args.init:
        from stable_baselines3 import PPO
        donor = PPO.load(args.init, device="cpu")
        model.policy.load_state_dict(donor.policy.state_dict())
        print(f"가중치 이식: {args.init}")
    else:
        print("무작위 초기화로 시작 (계획서 4.7)")

    print(f"{args.steps:,} 스텝 — 세계 {venv.K}개 × {venv.N}슬롯 = num_envs {venv.num_envs}, "
          f"세계당 n_steps {n_steps} (배치 {n_steps * venv.num_envs:,}), 리셋 {venv.T}스텝마다", flush=True)
    cb = BehaviorLogCallbackV2(save_at=args.save_at, save_prefix=out)
    t0 = time.time()
    model.learn(total_timesteps=args.steps, callback=cb, tb_log_name=run,
                reset_num_timesteps=True, progress_bar=False)
    elapsed = time.time() - t0
    model.save(out)
    print(f"저장: {out}  ({elapsed / 60:.1f}분)")

    meta = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": " ".join([Path(sys.executable).name] + sys.argv),
        "python": platform.python_version(),
        "steps": args.steps,
        "actual_timesteps": int(model.num_timesteps),
        "seed": args.seed,
        "elapsed_min": round(elapsed / 60, 2),
        "ppo": {k: (float(v) if isinstance(v, (int, float)) else str(v)) for k, v in {
            "n_steps": n_steps, "batch_size": model.batch_size, "n_epochs": model.n_epochs,
            "gamma": model.gamma, "gae_lambda": model.gae_lambda, "ent_coef": model.ent_coef,
            "learning_rate": tuned.get("learning_rate", "default"), "clip_range": tuned.get("clip_range", "default"),
        }.items()},
        "v2": cfg.v2,
        "num_worlds": venv.K, "reset_interval": venv.T,
        "worlds_seen": sum(len(h) for h in venv.seed_history),
        "world_resets": venv.num_resets,
        "r2_history": cb.r2_history,
        "init": args.init,
    }
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"학습한 세계 수: {meta['worlds_seen']} (시간 초과 리셋 {venv.num_resets}회)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
