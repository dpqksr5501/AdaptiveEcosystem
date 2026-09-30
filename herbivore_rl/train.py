"""§6.3 PPO 학습.

    python train.py --steps 1000000       # 파이프라인 확인
    python train.py --steps 10000000      # 본 학습

§6.1 모방 초기화를 먼저 돌려 두면 (`ckpt/warmstart.zip`) 자동으로 그 가중치에서 시작한다.

`PPO_KWARGS` 와 `make_model()` 이 이 프로젝트의 **유일한** PPO 설정이다. warmstart.py와
tune_ppo.py가 여기서 가져다 쓴다. 두 곳에 따로 적으면 모방 초기화 가중치가 학습 모델에
안 맞는다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저. 이유는 그 파일 참조

import argparse
import sys
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from torch import nn

from env.config import load_config
from env.vec_env import make_vec_env, sigmoid
from env.world import ACT_DIM

ROOT = Path(__file__).resolve().parent
CKPT = ROOT / "ckpt"
ACT_NAMES = ["forage", "cohesion", "flee_dist", "cover"]   # §3.2 순서

# §6.3 — net_arch 와 activation_fn 은 고정이다. §6.4 탐색 대상에 넣지 않는다.
# C++ 추론 함수(§9.3)와 §8.1 export가 7-64-64-4 / tanh 에 의존한다.
PPO_KWARGS = dict(
    policy_kwargs=dict(net_arch=[64, 64], activation_fn=nn.Tanh),
    n_steps=256,
    batch_size=4096,
    n_epochs=10,
    learning_rate=3e-4,
    gamma=0.995,
    gae_lambda=0.95,
    clip_range=0.2,
    ent_coef=0.01,
    seed=0,
)


def make_model(venv, tensorboard_log: str | None = "runs/", **overrides) -> PPO:
    """§6.3 설정 그대로. overrides 는 §6.4 탐색 대상만 넘어온다."""
    forbidden = {"policy_kwargs", "net_arch", "activation_fn"}
    bad = forbidden & set(overrides)
    if bad:
        raise ValueError(f"§6.4 탐색 금지 항목이다: {sorted(bad)}")
    kw = dict(PPO_KWARGS)
    kw.update(overrides)
    return PPO("MlpPolicy", venv, tensorboard_log=tensorboard_log, device="cpu", **kw)


def load_tuned(path: str | Path | None) -> dict:
    """§6.4 산출물(`configs/ppo_best.yaml`)에서 탐색된 5개만 읽는다.

    파일에 무엇이 적혀 있든 구조(net_arch / activation_fn)는 절대 반영하지 않는다 —
    `make_model()` 이 거부한다.
    """
    if path is None:
        return {}
    p = Path(path)
    if not p.exists():
        print(f"{p} 없음 — §6.3 기본값으로 진행")
        return {}
    import yaml

    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    params = {k: v for k, v in doc["params"].items()}
    params["n_epochs"] = int(params["n_epochs"])
    print(f"§6.4 튜닝값 적용: " + "  ".join(f"{k}={v}" for k, v in params.items()))
    return params


class BehaviorLogCallback(BaseCallback):
    """§6.5 — 매 롤아웃 끝에 행동 분포와 월드 상태를 기록한다."""

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        # 버퍼에는 정책이 뽑은 **원시** 행동이 들어 있다. 환경이 실제로 본 값은
        # SB3가 action_space로 clip한 뒤 HerdVecEnv가 sigmoid를 씌운 값이다 (§1.3).
        # §9.3의 C++ `clamp(-3,3) -> sigmoid` 와 같은 순서로 맞춘다.
        raw = self.model.rollout_buffer.actions.reshape(-1, ACT_DIM)
        a = sigmoid(np.clip(raw, -3.0, 3.0))
        for i, name in enumerate(ACT_NAMES):
            self.logger.record(f"act/{name}_mean", float(a[:, i].mean()))
            self.logger.record(f"act/{name}_std", float(a[:, i].std()))

        # 우리 환경은 에피소드가 끝나지 않아(슬롯 리스폰, §4.3) SB3의 rollout/ep_rew_mean이
        # 안 찍힌다. 학습 곡선을 보려면 롤아웃 보상을 직접 남겨야 한다.
        self.logger.record(
            "rollout/reward_per_step", float(self.model.rollout_buffer.rewards.mean())
        )
        self.logger.record(
            "train/policy_std", self.model.policy.log_std.detach().exp().mean().item()
        )

        w = self.training_env.get_attr("world")[0]
        self.logger.record("world/mean_energy", float(w.energy.mean()))
        self.logger.record("world/in_cover_frac", float(w._g["in_cover"].mean()))
        self.logger.record("world/kill_ema", float(w.pred_ema))
        self.logger.record("world/predation_rate", float(w.stats()["predation_rate"]))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="§6.3 PPO 학습")
    # §6.3 정정: 본 학습은 2M 이다 (기존 10M). 이 환경에서 PPO 는 2M 근처가 정점이고
    # 그 이상은 과학습이다 — 10M 모델은 도주를 거의 포기한다 (flee_dist 0.379 → 0.201).
    # 측정: docs/phase3_ppo_findings.md §6.3
    p.add_argument("--steps", type=int, default=2_000_000)
    p.add_argument("--init", default=str(CKPT / "warmstart.zip"),
                   help="§6.1 모방 초기화 가중치. 없으면 무작위 초기화로 시작")
    p.add_argument("--no-init", action="store_true", help="모방 초기화 없이 시작")
    p.add_argument("--out", default=str(CKPT / "final.zip"))
    p.add_argument("--tb", default="runs/")
    p.add_argument("--run-name", default=None)
    p.add_argument("--config", default=None)
    p.add_argument("--ppo-config", default=None,
                   help="§6.4 산출물 경로 (configs/ppo_best.yaml). 없으면 §6.3 기본값")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    venv = make_vec_env(cfg)
    tuned = load_tuned(args.ppo_config)

    # §6.3 하이퍼파라미터가 항상 권위를 갖도록 모델은 늘 make_model()로 만들고,
    # §6.1이 남긴 체크포인트에서는 **가중치만** 옮긴다. PPO.load()를 쓰면 저장된
    # 하이퍼파라미터까지 딸려 오고, clip_range·learning_rate는 SB3가 스케줄 함수로
    # 감싸는 값이라 나중에 raw float로 덮으면 train() 안에서 터진다.
    model = make_model(venv, tensorboard_log=args.tb, **tuned)
    init = Path(args.init)
    if args.no_init:
        print("모방 초기화 없이 시작")
    elif init.exists():
        donor = PPO.load(init, device="cpu")
        model.policy.load_state_dict(donor.policy.state_dict())
        print(f"모방 초기화 가중치 이식: {init}")
    else:
        print(f"{init} 없음 — 무작위 초기화로 시작 (§6.1을 먼저 돌리는 편이 낫다)")

    print(f"{args.steps:,} 스텝 학습 시작 (num_envs={venv.num_envs})")
    model.learn(
        total_timesteps=args.steps,
        callback=BehaviorLogCallback(),
        tb_log_name=args.run_name or f"ppo_{args.steps//1000}k",
        reset_num_timesteps=True,
        progress_bar=False,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save(out)
    print(f"저장: {out}")

    w = venv.world
    s = w.stats()
    print(f"학습 중 월드 상태: mean_energy={w.energy.mean():.3f} "
          f"in_cover_frac={w._g['in_cover'].mean():.3f} kill_ema={w.pred_ema:.4f} "
          f"predation_rate={s['predation_rate']:.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
