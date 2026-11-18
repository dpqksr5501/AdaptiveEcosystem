"""R10 두뇌 — 마스크를 감각에서 읽는 정책 (0 단계 사양 8 절).

몸이 못 하는 행동(땅 몸의 오르기·내리기, 날지 않는 몸의 급강하, 예비 칸)은 감각의 몸 벡터(b_swim·b_fly)로 정해진다.
그래서 마스크를 따로 넘기지 않고 감각에서 계산해 로짓에 −1e9 를 더한다. 학습(SB3 PPO)·고정 두뇌(numpy)·언리얼(C++)이 같은 규칙을 쓴다.
"""

from __future__ import annotations

import json

import numpy as np

from r10 import contract as C

_B0 = C.SLICES["body"][0]
I_SWIM = _B0 + C.BODY_NAMES.index("b_swim")
I_FLY = _B0 + C.BODY_NAMES.index("b_fly")
NEG = -1e9


def mask_from_obs(obs: np.ndarray) -> np.ndarray:
    """(n, 206) → (n, 24) bool. contract.action_mask(medium) 와 같은 규칙."""
    obs = np.asarray(obs)
    n = obs.shape[0]
    m = np.ones((n, C.N_ACTIONS), bool)
    fly = obs[:, I_FLY] > 0.5
    swim = obs[:, I_SWIM] > 0.5
    m[:, C.A_UP] = fly | swim
    m[:, C.A_DOWN] = fly | swim
    m[:, C.A_DIVE] = fly
    m[:, list(C.SPARE_ACTIONS)] = False
    return m


def forward_np(weights: dict, obs: np.ndarray) -> np.ndarray:
    """numpy 정책 로짓 (마스크 적용 전). weights: W0 (h, 206), B0, W1, B1, W2 (24, h), B2 — tanh."""
    h = np.tanh(obs @ weights["W0"].T + weights["B0"])
    h = np.tanh(h @ weights["W1"].T + weights["B1"])
    return h @ weights["W2"].T + weights["B2"]


def act_np(weights: dict, obs: np.ndarray) -> np.ndarray:
    """결정적 행동: 막히지 않은 칸 가운데 가장 큰 로짓, 같으면 낮은 번호 (계약 select)."""
    lg = forward_np(weights, obs.astype(np.float32))
    lg = np.where(mask_from_obs(obs), lg, NEG)
    return np.argmax(lg, axis=1)


def sample_np(weights: dict, obs: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """확률 행동: 막히지 않은 칸의 softmax 에서 뽑기 (학습 때와 같은 방식, 평가 비교용)."""
    lg = forward_np(weights, obs.astype(np.float32)).astype(np.float64)
    lg = np.where(mask_from_obs(obs), lg, NEG)
    lg -= lg.max(axis=1, keepdims=True)
    pr = np.exp(lg)
    pr /= pr.sum(axis=1, keepdims=True)
    u = rng.random((pr.shape[0], 1))
    return np.minimum((np.cumsum(pr, axis=1) < u).sum(axis=1), pr.shape[1] - 1)


def load_brain(path) -> dict:
    """npz 두뇌 → numpy 가중치. 계약 해시(io_hash)가 다르면 거부. torch 를 부르지 않는다 (평가·언리얼 내보내기용)."""
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z["meta_json"][()]))
        if meta.get("io_hash") != C.io_hash():
            raise ValueError(f"{path}: io_hash {meta.get('io_hash')} != contract {C.io_hash()}")
        return {k: np.array(z[k]) for k in ("W0", "B0", "W1", "B1", "W2", "B2")}


def make_sb3_policy():
    """SB3 ActorCriticPolicy 를 감싸 로짓에 감각 마스크를 더한다 (torch 는 쓸 때만 불러온다)."""
    import torch
    from stable_baselines3.common.policies import ActorCriticPolicy

    class MaskedMlpPolicy(ActorCriticPolicy):
        def _mask(self, obs):
            fly = obs[:, I_FLY] > 0.5
            swim = obs[:, I_SWIM] > 0.5
            m = torch.ones((obs.shape[0], C.N_ACTIONS), dtype=torch.bool, device=obs.device)
            m[:, C.A_UP] = fly | swim
            m[:, C.A_DOWN] = fly | swim
            m[:, C.A_DIVE] = fly
            m[:, list(C.SPARE_ACTIONS)] = False
            return m

        def _get_action_dist_from_latent(self, latent_pi):
            logits = self.action_net(latent_pi)
            if getattr(self, "_cur_mask", None) is not None and self._cur_mask.shape[0] == logits.shape[0]:
                logits = torch.where(self._cur_mask, logits, torch.full_like(logits, NEG))
            return self.action_dist.proba_distribution(action_logits=logits)

        def forward(self, obs, deterministic=False):
            self._cur_mask = self._mask(obs)
            try:
                return super().forward(obs, deterministic)
            finally:
                self._cur_mask = None

        def evaluate_actions(self, obs, actions):
            self._cur_mask = self._mask(obs)
            try:
                return super().evaluate_actions(obs, actions)
            finally:
                self._cur_mask = None

        def get_distribution(self, obs):
            self._cur_mask = self._mask(obs)
            try:
                return super().get_distribution(obs)
            finally:
                self._cur_mask = None

    return MaskedMlpPolicy


def extract_sb3(model) -> dict:
    """SB3 PPO (pi 망 128-128 tanh) → numpy 가중치."""
    pol = model.policy
    net = pol.mlp_extractor.policy_net
    lin = [m for m in net if hasattr(m, "weight")]
    w = {"W0": lin[0].weight, "B0": lin[0].bias, "W1": lin[1].weight, "B1": lin[1].bias,
         "W2": pol.action_net.weight, "B2": pol.action_net.bias}
    return {k: v.detach().cpu().numpy().astype(np.float32) for k, v in w.items()}
