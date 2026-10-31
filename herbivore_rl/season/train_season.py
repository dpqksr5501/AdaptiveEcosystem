"""앵커에서 이어 학습한다 — SR1 방식 M0~M3 (SEASON 4.1 이어 학습 표, 5.4 방식).

    python -m season.train_season --anchor v1 --season a --method M2 --seed 0
    python -m season.train_season --anchor v20 --season season/seasons/season_b.yaml --method M3 --kl-coef 0.5 --seed 1
    python -m season.train_season --anchor v1 --k2b --method M2 --seed 0          # K2-B 대조 후보 (B 만)

방식 (SEASON 5.4, 아래로 갈수록 앞 방식을 포함한다):
- M0: 정책·가치·log_std 를 통째로 옮기고 ppo_best 그대로 학습한다. `train_v2.py --init` 과 같은 이식이다.
- M1: 처음 롤아웃 10회(32,768 × 10 = 327,680 timestep) 동안 정책 쪽 파라미터(mlp_extractor.policy_net, action_net,
  log_std)를 고정하고 가치망만 학습한다. 그 뒤는 M0 과 같다. 예열 롤아웃도 학습량 2M 안에 센다.
- M2: M1 + learning_rate × 0.3, clip_range 0.1.
- M3: M2 + 앵커 KL 항. 손실에 kl_coef × KL(앵커 ‖ 현재)를 더한다. KL 은 리허설 슬롯(혼합 세계의 마지막 묶음 = B)
  롤아웃 상태에서 뽑은 미니배치(크기 batch_size)로 잰다. 대각 가우시안의 닫힌 식이고, 행동 차원으로 더하고 상태로
  평균한다. 계수는 {0.1, 0.5} 다(SEASON 5.4 제안). 예열 중에는 정책이 고정이라 KL 항을 넣지 않는다.
  SB3 의 target_kl 은 갱신 사이 조기 종료 장치라 앵커에 대한 KL 이 아니다. 그래서 `PPO.train()` 을 덮어쓴다(SeasonPPO).

공통 (SEASON 4.1 이어 학습 표):
- γ 는 앵커 zip 에 적힌 학습 γ 다(`env_v2.rollout.model_gamma`). v2 레시피의 0.995 가 아니다(SEASON:364).
  v1·v2.0 s0 앵커는 둘 다 0.9916661555611042 다.
- 나머지 하이퍼파라미터는 `configs/ppo_best.yaml`(`train.load_tuned`) 위에 방식의 값을 덮는다. 모델은 `train.make_model`
  로 만들고 클래스만 SeasonPPO 로 바꾼다. make_model 의 구조 고정 규칙(64-64 tanh, 탐색 금지 항목)을 그대로 쓰려는 것이다.
- 세계는 G 4개 + B 4개(K2-B 는 B 4개 + B 4개, `season/mixed_vec_env.py`)다. 세계당 n_steps = rollout_world_steps(256) /
  세계 수(8) = 32 이고, 롤아웃은 32,768 timestep 이다.
- Adam 상태는 새로 시작하고 reset_num_timesteps=True 다.
- 학습 세계 시드는 설정의 train_seeds [0, 1000) 에서 뽑는다. 평가·보류 시드와 겹치지 않는지 시작할 때 본다.
- 산출물은 `runs/season/sr1/train/<이름>.zip` 과 같은 이름의 `.json`(명령, 앵커 sha1, 설정 지문, 방식, 롤아웃별 기록)이다.
  `ckpt/` 아래로는 쓰지 않는다(앵커를 덮지 않게).

M0 은 SB3 `PPO.train()` 을 그대로 부른다. 앵커와의 거리 기록(`anchor_kl_before`)은 난수를 쓰지 않는 순전파라 학습에
영향이 없다. 그래서 `--rng-compat` 이면 같은 세계·시드에서 10-02 스크래치의 혼합 s0 과 같은 값이 나온다
(tests/test_season_methods.py 가 한 롤아웃으로 확인한다). 기본은 이식 뒤 학습 시드로 난수를 다시 잡는다
(`make_season_model` 의 난수 설명).
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import json
import platform
import time
from datetime import datetime, timezone

import numpy as np
import torch as th
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.utils import explained_variance
from torch.distributions import Normal, kl_divergence
from torch.nn import functional as F

from diagnose_v2 import check_disjoint, config_digest, model_fingerprint
from env_v2.rollout import model_gamma
from env_v2.vec_env import sigmoid
from season.common import (EVAL_SEEDS, HOLDOUT_SEEDS, PPO_CONFIG, SR1_STEPS, H, load_base,
                           load_season, method_tag, resolve_anchor, resolve_season, run_name, sim_digest, train_path)
from season.mixed_vec_env import B_META_OFFSET, build_k2b, build_mixed
from train import PPO_KWARGS, load_tuned, make_model

METHODS = ("M0", "M1", "M2", "M3")
KL_COEFS = (0.1, 0.5)               # SR1 1차 선별의 M3 계수 (SEASON 5.4 제안)
WARMUP_ROLLOUTS = 10                # M1 가치망 예열 롤아웃 수 (약 0.33M timestep, SEASON 5.4 제안)
LR_MULT = 0.3                       # M2 learning_rate 배수
SMALL_CLIP = 0.1                    # M2 clip_range
KL_RNG_TAG = 5501                   # KL 미니배치 난수 스트림 구분값. SB3 전역 난수열을 건드리지 않는다

# 정책 쪽 파라미터 이름 머리. 나머지(mlp_extractor.value_net.*, value_net.*)가 가치망이다.
# net_arch=[64, 64] 는 SB3 2.x 에서 정책·가치망이 층을 나누지 않는다(features extractor 는 Flatten 이라 파라미터가 없다).
POLICY_PREFIXES = ("mlp_extractor.policy_net.", "action_net.", "log_std")


# --------------------------------------------------------------------- #
# 방식 설정
# --------------------------------------------------------------------- #


def method_config(method: str, tuned: dict, kl_coef: float | None = None,
                  warmup_rollouts: int = WARMUP_ROLLOUTS) -> dict:
    """방식 → 학습 설정 {method, warmup_rollouts, learning_rate, clip_range, kl_coef}.

    learning_rate·clip_range 의 바탕은 튜닝값(없으면 `train.PPO_KWARGS`)이다. kl_coef 는 M3 에만 쓰고 양수여야 한다.
    """
    if method not in METHODS:
        raise ValueError(f"방식은 {METHODS} 중 하나다. 받은 값: {method!r}")
    lr0 = tuned.get("learning_rate", PPO_KWARGS["learning_rate"])
    clip0 = tuned.get("clip_range", PPO_KWARGS["clip_range"])
    if not isinstance(lr0, (int, float)) or not isinstance(clip0, (int, float)):
        raise ValueError("이어 학습은 상수 learning_rate·clip_range 만 받는다(스케줄 함수는 배수를 정할 수 없다)")
    if method != "M3" and kl_coef is not None:
        raise ValueError(f"kl_coef 는 M3 에만 쓴다 (받은 방식 {method})")
    if method == "M3" and (kl_coef is None or not float(kl_coef) > 0.0):
        raise ValueError(f"M3 은 양수 kl_coef 가 필요하다 (SR1 은 {KL_COEFS}). 받은 값: {kl_coef!r}")
    warm = 0 if method == "M0" else int(warmup_rollouts)
    if warm < 0:
        raise ValueError(f"warmup_rollouts {warmup_rollouts} 는 0 이상이다")
    small = method in ("M2", "M3")
    return {
        "method": method,
        "warmup_rollouts": warm,
        "learning_rate": float(lr0) * LR_MULT if small else float(lr0),
        "clip_range": SMALL_CLIP if small else float(clip0),
        "kl_coef": float(kl_coef) if method == "M3" else 0.0,
    }


def policy_param_names(policy) -> list[str]:
    return [n for n, _ in policy.named_parameters() if n.startswith(POLICY_PREFIXES)]


def value_param_names(policy) -> list[str]:
    return [n for n, _ in policy.named_parameters() if not n.startswith(POLICY_PREFIXES)]


def gaussian_params(policy, obs: th.Tensor) -> tuple[th.Tensor, th.Tensor]:
    """정책의 행동 분포(대각 가우시안) 평균과 표준편차. 자르기·sigmoid 전의 원값 공간이다."""
    d = policy.get_distribution(obs).distribution
    return d.mean, d.stddev


def anchor_kl(policy, anchor, obs: th.Tensor) -> th.Tensor:
    """KL(앵커 ‖ 정책): 행동 차원으로 더하고 상태로 평균한다. 앵커 쪽은 기울기를 끊는다. 같은 가중치면 0 이다."""
    with th.no_grad():
        a_mu, a_std = gaussian_params(anchor, obs)
    mu, std = gaussian_params(policy, obs)
    return kl_divergence(Normal(a_mu, a_std), Normal(mu, std)).sum(-1).mean()


# --------------------------------------------------------------------- #
# SeasonPPO — PPO.train() 덮어쓰기
# --------------------------------------------------------------------- #


class SeasonPPO(PPO):
    """M1 예열(가치망만)과 M3 앵커 KL 을 넣은 PPO. 둘 다 끄면 `PPO.train()` 그대로다.

    `train.make_model` 이 만든 PPO 의 클래스를 바꿔 쓰고 `season_setup` 으로 시즌 속성을 단다(`make_season_model`).
    시즌 속성(이름이 season_ 으로 시작)은 zip 에 저장하지 않는다. 저장한 zip 은 보통 PPO 로 읽힌다.
    """

    def season_setup(self, warmup_rollouts: int, kl_coef: float, anchor_policy, rehearsal: slice, seed: int) -> None:
        self.season_warmup_rollouts = int(warmup_rollouts)
        self.season_kl_coef = float(kl_coef)
        self.season_anchor = anchor_policy
        self.season_rehearsal = rehearsal
        self.season_rng = np.random.default_rng([int(seed), KL_RNG_TAG])
        self.season_rollouts = 0
        self.season_log: list[dict] = []

    def _excluded_save_params(self) -> list[str]:
        return super()._excluded_save_params() + [k for k in self.__dict__ if k.startswith("season_")]

    # --- 리허설 상태 ---------------------------------------------------- #

    def _rehearsal_obs(self) -> np.ndarray:
        """이번 롤아웃의 리허설 슬롯 관측 (상태 수, 관측 수). 버퍼가 이미 평탄화됐으면(슬롯 우선) 그 순서로 자른다."""
        buf, sl = self.rollout_buffer, self.season_rehearsal
        if not buf.generator_ready:                  # (n_steps, n_envs, obs_dim)
            obs = buf.observations[:, sl]
        else:                                       # (n_envs·n_steps, obs_dim), 슬롯 e 는 [e·n_steps, (e+1)·n_steps)
            obs = buf.observations[sl.start * buf.buffer_size: sl.stop * buf.buffer_size]
        return np.asarray(obs, dtype=np.float32).reshape(-1, buf.obs_shape[0])

    def _drift(self, obs: np.ndarray) -> float:
        """이번 롤아웃을 모은 정책과 앵커의 KL (리허설 상태 전체 평균, 기울기 없음). 난수를 쓰지 않는다."""
        with th.no_grad():
            return float(anchor_kl(self.policy, self.season_anchor, th.as_tensor(obs, device=self.device)))

    # --- 갱신 ---------------------------------------------------------- #

    def train(self) -> None:
        if not hasattr(self, "season_rollouts"):     # season_setup 없이 읽은 모델은 PPO 그대로다
            return super().train()
        k = self.season_rollouts
        obs_r = self._rehearsal_obs() if self.season_anchor is not None else None
        row = {"rollout": k, "timesteps": int(self.num_timesteps)}
        if obs_r is not None:
            row["anchor_kl_before"] = self._drift(obs_r)
        if k < self.season_warmup_rollouts:
            row["mode"] = "warmup"
            row.update(self._train_value_only())
        elif self.season_kl_coef > 0.0:
            row["mode"] = "ppo+kl"
            row.update(self._train_with_kl(obs_r))
        else:
            row["mode"] = "ppo"
            super().train()
            nv = self.logger.name_to_value
            row.update({"value_loss": float(nv.get("train/value_loss", float("nan"))),
                        "clip_fraction": float(nv.get("train/clip_fraction", float("nan"))),
                        "approx_kl": float(nv.get("train/approx_kl", float("nan")))})
        self.logger.record("season/warmup", float(row["mode"] == "warmup"))
        if "anchor_kl_before" in row:
            self.logger.record("season/anchor_kl_before", row["anchor_kl_before"])
        self.season_log.append(row)
        self.season_rollouts = k + 1

    def _train_value_only(self) -> dict:
        """M1 예열: 정책 쪽 파라미터의 requires_grad 를 끄고 가치 손실만 내린다. 미니배치 순서는 PPO.train() 과 같다."""
        self.policy.set_training_mode(True)
        self._update_learning_rate(self.policy.optimizer)
        frozen = [p for n, p in self.policy.named_parameters() if n.startswith(POLICY_PREFIXES)]
        flags = [p.requires_grad for p in frozen]
        losses = []
        try:
            for p in frozen:
                p.requires_grad_(False)
            for _ in range(self.n_epochs):
                for data in self.rollout_buffer.get(self.batch_size):
                    values = self.policy.predict_values(data.observations).flatten()
                    value_loss = F.mse_loss(data.returns, values)
                    losses.append(value_loss.item())
                    self.policy.optimizer.zero_grad()
                    (self.vf_coef * value_loss).backward()
                    th.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                    self.policy.optimizer.step()
                self._n_updates += 1
        finally:
            for p, f in zip(frozen, flags):
                p.requires_grad_(f)
        ev = explained_variance(self.rollout_buffer.values.flatten(), self.rollout_buffer.returns.flatten())
        self.logger.record("train/value_loss", float(np.mean(losses)))
        self.logger.record("train/explained_variance", ev)
        self.logger.record("train/n_updates", self._n_updates, exclude="tensorboard")
        return {"value_loss": float(np.mean(losses))}

    def _train_with_kl(self, obs_r: np.ndarray) -> dict:
        """M3: `PPO.train()` (SB3 2.9) 본문에 앵커 KL 항을 더한다. clip_range_vf·target_kl 처리도 그대로 옮겼다."""
        self.policy.set_training_mode(True)
        self._update_learning_rate(self.policy.optimizer)
        clip_range = self.clip_range(self._current_progress_remaining)
        if self.clip_range_vf is not None:
            clip_range_vf = self.clip_range_vf(self._current_progress_remaining)
        obs_t = th.as_tensor(obs_r, device=self.device)
        with th.no_grad():
            a_mu, a_std = gaussian_params(self.season_anchor, obs_t)
        entropy_losses, pg_losses, value_losses, clip_fractions, kls = [], [], [], [], []
        approx_kl_divs = []
        continue_training = True
        for epoch in range(self.n_epochs):
            approx_kl_divs = []
            for data in self.rollout_buffer.get(self.batch_size):
                values, log_prob, entropy = self.policy.evaluate_actions(data.observations, data.actions)
                values = values.flatten()
                advantages = data.advantages
                if self.normalize_advantage and len(advantages) > 1:
                    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
                ratio = th.exp(log_prob - data.old_log_prob)
                policy_loss_1 = advantages * ratio
                policy_loss_2 = advantages * th.clamp(ratio, 1 - clip_range, 1 + clip_range)
                policy_loss = -th.min(policy_loss_1, policy_loss_2).mean()
                pg_losses.append(policy_loss.item())
                clip_fractions.append(th.mean((th.abs(ratio - 1) > clip_range).float()).item())
                if self.clip_range_vf is None:
                    values_pred = values
                else:
                    values_pred = data.old_values + th.clamp(values - data.old_values, -clip_range_vf, clip_range_vf)
                value_loss = F.mse_loss(data.returns, values_pred)
                value_losses.append(value_loss.item())
                entropy_loss = -th.mean(-log_prob) if entropy is None else -th.mean(entropy)
                entropy_losses.append(entropy_loss.item())

                # 앵커 KL: 리허설 상태에서 batch_size 개를 전용 난수로 뽑는다
                idx = th.as_tensor(self.season_rng.integers(0, len(obs_r), size=self.batch_size), device=self.device)
                mu, std = gaussian_params(self.policy, obs_t[idx])
                kl = kl_divergence(Normal(a_mu[idx], a_std[idx]), Normal(mu, std)).sum(-1).mean()
                kls.append(kl.item())

                loss = (policy_loss + self.ent_coef * entropy_loss + self.vf_coef * value_loss
                        + self.season_kl_coef * kl)

                with th.no_grad():
                    log_ratio = log_prob - data.old_log_prob
                    approx_kl_div = th.mean((th.exp(log_ratio) - 1) - log_ratio).cpu().numpy()
                    approx_kl_divs.append(approx_kl_div)
                if self.target_kl is not None and approx_kl_div > 1.5 * self.target_kl:
                    continue_training = False
                    break

                self.policy.optimizer.zero_grad()
                loss.backward()
                th.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                self.policy.optimizer.step()
            self._n_updates += 1
            if not continue_training:
                break

        ev = explained_variance(self.rollout_buffer.values.flatten(), self.rollout_buffer.returns.flatten())
        self.logger.record("train/entropy_loss", np.mean(entropy_losses))
        self.logger.record("train/policy_gradient_loss", np.mean(pg_losses))
        self.logger.record("train/value_loss", np.mean(value_losses))
        self.logger.record("train/approx_kl", np.mean(approx_kl_divs))
        self.logger.record("train/clip_fraction", np.mean(clip_fractions))
        self.logger.record("train/loss", loss.item())
        self.logger.record("train/explained_variance", ev)
        self.logger.record("train/std", th.exp(self.policy.log_std).mean().item())
        self.logger.record("train/n_updates", self._n_updates, exclude="tensorboard")
        self.logger.record("train/clip_range", clip_range)
        self.logger.record("season/anchor_kl", float(np.mean(kls)))
        return {"value_loss": float(np.mean(value_losses)), "clip_fraction": float(np.mean(clip_fractions)),
                "approx_kl": float(np.mean(approx_kl_divs)), "anchor_kl": float(np.mean(kls))}


def make_season_model(venv, anchor_path: str | Path, mcfg: dict, tuned: dict, seed: int, n_steps: int,
                      tensorboard_log: str | None = None, reseed: bool = True, **overrides) -> SeasonPPO:
    """`train.make_model` 로 PPO 를 만들고 앵커 가중치(정책·가치·log_std)를 옮긴 뒤 SeasonPPO 로 바꾼다.

    `tuned` 의 learning_rate·clip_range 는 방식 설정(`method_config`) 값으로 바뀐다. `overrides` 는 테스트가 batch_size·
    n_epochs 를 줄일 때만 쓴다. 앵커 정책은 KL 기준으로 고정해 둔다(기울기 없음, 평가 모드).

    난수: `PPO.load` 는 zip 에 저장된 학습 시드(v1·v2.0 s0 모두 0)로 전역 난수(torch·numpy·random)를 다시 잡는다
    (SB3 `_setup_model` → `set_random_seed`). 그래서 `train_v2.py --init` 과 10-02 스크래치는 `--seed` 와 무관하게 같은
    PPO 표본 잡음·미니배치 순서를 썼고, 시드는 세계 고르기(meta_seed)만 바꿨다. `reseed=True`(기본)면 이식 뒤에
    `set_random_seed(seed)` 로 다시 잡아 학습 시드가 잡음까지 정하게 한다. `reseed=False` 는 10-02 순서 그대로다
    (스크래치 재현 확인용, 명령줄 `--rng-compat`).
    """
    kw = dict(tuned, learning_rate=mcfg["learning_rate"], clip_range=mcfg["clip_range"])
    kw.update(overrides)
    model = make_model(venv, tensorboard_log=tensorboard_log, n_steps=n_steps, seed=seed, **kw)
    donor = PPO.load(str(anchor_path), device="cpu")
    model.policy.load_state_dict(donor.policy.state_dict())
    if reseed:
        model.set_random_seed(seed)
    anchor = donor.policy
    anchor.set_training_mode(False)
    for p in anchor.parameters():
        p.requires_grad_(False)
    model.__class__ = SeasonPPO
    model.season_setup(mcfg["warmup_rollouts"], mcfg["kl_coef"], anchor, venv.rehearsal_slice, seed)
    return model


class SeasonLogCallback(BaseCallback):
    """롤아웃마다 묶음별 보상 평균과 행동 평균을 남긴다 (SEASON 5.4 부수 확인: G 와 B 의 리턴이 갈리나)."""

    def __init__(self):
        super().__init__()
        self.history: list[dict] = []

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        env, buf = self.training_env, self.model.rollout_buffer
        names = list(env.act_names)
        row = {"timesteps": int(self.num_timesteps)}
        for i, lab in enumerate(env.labels):
            sl = env.part_slice(i)
            key = f"{i}{lab}"
            row[f"reward_{key}"] = float(buf.rewards[:, sl].mean())
            a = sigmoid(np.clip(buf.actions[:, sl].reshape(-1, len(names)), -3.0, 3.0)).mean(0)
            row.update({f"act_{key}_{n}": float(v) for n, v in zip(names, a)})
            self.logger.record(f"season/reward_{key}", row[f"reward_{key}"])
        self.history.append(row)


# --------------------------------------------------------------------- #
# 명령줄
# --------------------------------------------------------------------- #


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="앵커에서 이어 학습 (SR1 방식 M0~M3)")
    p.add_argument("--anchor", required=True, help="앵커 이름(v1, v20) 또는 zip 경로")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--season", help="시즌 이름(a, b, c) 또는 yaml 경로. 후보 = G 4 + B 4")
    g.add_argument("--k2b", action="store_true", help="K2-B 대조 후보: 시즌 없이 B 4 + B 4")
    p.add_argument("--method", required=True, choices=METHODS)
    p.add_argument("--kl-coef", type=float, default=None, help=f"M3 앵커 KL 계수 (SR1: {KL_COEFS})")
    p.add_argument("--steps", type=int, default=SR1_STEPS)
    p.add_argument("--seed", type=int, default=0, help="PPO 시드이자 G 묶음 meta_seed (B 묶음은 +7919)")
    p.add_argument("--out", default=None, help="기본 runs/season/sr1/train/<이름>.zip")
    p.add_argument("--base", default=None, help="B 설정 (기본 configs/v2.yaml)")
    p.add_argument("--ppo-config", default=str(PPO_CONFIG))
    p.add_argument("--warmup-rollouts", type=int, default=WARMUP_ROLLOUTS, help="M1~M3 가치망 예열 롤아웃 수")
    p.add_argument("--threads", type=int, default=3, help="torch 스레드 수 (10-02 측정과 같은 3)")
    p.add_argument("--tb", default=None, help="TensorBoard 디렉터리 (기본 끔)")
    p.add_argument("--rng-compat", action="store_true",
                   help="앵커 zip 의 저장 시드로 잡힌 난수 그대로 학습한다(10-02 스크래치·train_v2 --init 과 같은 난수열, "
                        "재현 확인용). 기본은 이식 뒤 --seed 로 다시 잡는다")
    p.add_argument("--force", action="store_true", help="있는 출력 zip 을 덮어쓴다")
    args = p.parse_args(argv)

    th.set_num_threads(args.threads)
    anchor_tag, anchor_path = resolve_anchor(args.anchor)
    if not anchor_path.exists():
        raise SystemExit(f"앵커 {anchor_path} 가 없다")
    gamma = model_gamma(anchor_path)
    if gamma is None:
        raise SystemExit(f"앵커 {anchor_path} 의 γ 를 읽지 못했다 (SEASON:364 — 시즌 γ 는 앵커의 학습 γ 다)")
    tuned = dict(load_tuned(args.ppo_config), gamma=gamma)
    mcfg = method_config(args.method, tuned, args.kl_coef, args.warmup_rollouts)
    mtag = method_tag(args.method, args.kl_coef)

    b_cfg = load_base(args.base)
    if args.k2b:
        season_tag, season_path, g_cfg = None, None, None
        venv = build_k2b(b_cfg, args.seed)
    else:
        season_tag, season_path = resolve_season(args.season)
        g_cfg = load_season(season_path)
        venv = build_mixed(g_cfg, b_cfg, args.seed)
    for cfg in (c for c in (g_cfg, b_cfg) if c is not None):
        check_disjoint("학습 세계 시드", range(*cfg.train_seeds), EVAL_SEEDS + HOLDOUT_SEEDS, None)

    name = run_name(anchor_tag, season_tag, mtag, args.seed, args.steps)
    out = Path(args.out) if args.out else train_path(anchor_tag, season_tag, mtag, args.seed, args.steps)
    if out.resolve().is_relative_to((H / "ckpt").resolve()):
        raise SystemExit(f"{out} 는 ckpt/ 아래다. 시즌 후보는 runs/season/ 에 쓴다 (앵커를 덮지 않게)")
    if out.exists() and not args.force:
        raise SystemExit(f"{out} 가 이미 있다 (덮으려면 --force)")
    out.parent.mkdir(parents=True, exist_ok=True)

    rws = int(((g_cfg or b_cfg).v2.get("train") or {}).get("rollout_world_steps", 256))
    n_steps = max(1, rws // venv.K)
    model = make_season_model(venv, anchor_path, mcfg, tuned, args.seed, n_steps, tensorboard_log=args.tb,
                              reseed=not args.rng_compat)
    if float(model.gamma) != gamma or float(model.rollout_buffer.gamma) != gamma:
        raise RuntimeError(f"모델 γ {model.gamma} 가 앵커 γ {gamma} 와 다르다")

    kind = "K2-B (B 4 + B 4)" if args.k2b else f"시즌 {season_tag} (G 4 + B 4)"
    print(f"[{name}] 앵커 {anchor_tag} ({model_fingerprint(anchor_path)}), {kind}, 방식 {mtag}: "
          f"lr {mcfg['learning_rate']:.4g}, clip {mcfg['clip_range']:g}, 예열 {mcfg['warmup_rollouts']}롤아웃, "
          f"KL {mcfg['kl_coef']:g}, γ {gamma}, n_steps {n_steps} × num_envs {venv.num_envs}", flush=True)
    cb = SeasonLogCallback()
    t0 = time.time()
    model.learn(total_timesteps=args.steps, callback=cb, tb_log_name=name, reset_num_timesteps=True,
                progress_bar=False)
    elapsed = time.time() - t0
    model.save(out)

    history = [dict(a, **b) for a, b in zip(model.season_log, cb.history)]
    meta = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": " ".join(["python", "-m", "season.train_season"]
                            + (sys.argv[1:] if argv is None else [str(a) for a in argv])),
        "python": platform.python_version(),
        "sim_digest": sim_digest(),
        "run_name": name,
        "anchor": {"tag": anchor_tag, "path": str(anchor_path), "sha1": model_fingerprint(anchor_path)},
        "season": None if args.k2b else {"tag": season_tag, "path": str(season_path),
                                         "version": g_cfg.v2.get("version"), "config_digest": config_digest(g_cfg)},
        "base": {"path": str(args.base or "configs/v2.yaml"), "config_digest": config_digest(b_cfg)},
        "k2b": bool(args.k2b),
        "method": dict(mcfg, tag=mtag),
        "gamma": float(model.gamma),
        "gamma_source": "anchor",
        "ppo": {"n_steps": n_steps, "batch_size": int(model.batch_size), "n_epochs": int(model.n_epochs),
                "gae_lambda": float(model.gae_lambda), "ent_coef": float(model.ent_coef),
                "learning_rate": mcfg["learning_rate"], "clip_range": mcfg["clip_range"],
                "ppo_config": args.ppo_config},
        "steps": args.steps,
        "actual_timesteps": int(model.num_timesteps),
        "seed": args.seed,
        "rng": "anchor_zip_seed (10-02 호환)" if args.rng_compat else "reseed(seed)",
        "meta_seeds": [args.seed, args.seed + B_META_OFFSET],
        "parts": list(venv.labels),
        "worlds": venv.worlds_seen(),
        "elapsed_min": round(elapsed / 60, 3),
        "out_sha1": model_fingerprint(out),
        "history": history,
    }
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {out} ({elapsed / 60:.2f}분, {model.num_timesteps:,} timestep, 본 세계 {meta['worlds']['total']}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
