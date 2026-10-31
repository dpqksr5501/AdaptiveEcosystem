"""v2.2r CM — 범주형 보행 (10-03 R2·R8, 수정 제안서 3.1 (나) CM 행·3.3 범주형 초기값).

조향 4개는 지금처럼 가우시안이고, 보행(과 경계)을 범주 하나 Categorical(K) 로 고른다. 범주는 설정
`train.cm.categories` 순서다:
- K = 3 `[stop, walk, run]` — L 반사 세계(`configs/v2_2r_l.yaml` 꼴)에 쓴다
- K = 4 `[stop, walk, run, look]` — W′ 세계(`configs/v2_2r_w.yaml` 꼴). look = 경계 행동(창 안에서만 효력, 정지·위협 쪽
  돌아보기). `mask_look_outside_window` 면 창 밖에서 look 의 확률을 0 으로 막는다(로짓 −inf). 창은 관측으로 정한다:
  관측 1(포식자 수) = 0 & 관측 threat_recency > theta (`features.vigil_window.theta`). 세계의 창(`World.window`)과 같은
  결정 관측이다

정책 출력(SB3 행동 벡터)은 [조향 원값 4개, 범주 번호] 5칸이다. 행동 공간은 Box([-3]*4 + [0], [3]*4 + [K-1]). 세계에 넣을
때 `cm_to_world` 가 조향은 sigmoid, 범주는 speed 값(정지 1/6·걷기 1/2·뛰기 5/6, 문턱 1/3·2/3 의 칸 가운데)과
vigilance 값(look 이면 1, 아니면 0)으로 바꾼다. 세계(World)는 바꾸지 않는다 — 같은 세계의 같은 행동 열을 쓴다.

엔트로피: 조향 가우시안 엔트로피에는 PPO ent_coef 가, 범주 엔트로피에는 `cat_ent_coef` 가 걸린다. SB3 PPO 는
ent_coef × entropy() 를 쓰므로 분포의 entropy() 가 가우시안 + (cat_ent_coef / ent_coef) × 범주 엔트로피를 낸다.
시작 확률: 로짓 편향 = log(init_probs / Σ init_probs) (가중치는 SB3 직교 초기화 gain 0.01 그대로라 거의 상수다).
마스크가 look 을 막은 상태에서는 나머지 범주로 다시 맞춰진다.
"""

from __future__ import annotations

import math

import numpy as np
import torch as th
from gymnasium import spaces
from stable_baselines3.common.distributions import DiagGaussianDistribution
from stable_baselines3.common.policies import ActorCriticPolicy
from torch import nn

N_STEER = 4
CATEGORIES = ("stop", "walk", "run", "look")
# 범주 → speed 행동 값. 문턱 1/3·2/3 의 칸 가운데라 문턱의 float 차이로 칸이 바뀌지 않는다. look 은 경계가 속력보다
# 우선하므로(World._vigil_step) speed 값은 정지로 둔다(창 밖이면 마스크가 막고, 막지 않아도 정지다).
SPEED_VALUE = {"stop": 1.0 / 6.0, "walk": 0.5, "run": 5.0 / 6.0, "look": 1.0 / 6.0}
OBS_PRED_COUNT, OBS_THREAT = 1, 7


def cm_params(cfg) -> dict | None:
    """설정의 `train.cm` 블록을 검사한다. 없으면 None (가우시안 보행, 지금과 같다). 기본값은 없다."""
    raw = ((getattr(cfg, "v2", None) or {}).get("train") or {}).get("cm")
    if raw is None:
        return None
    need = {"categories", "init_probs", "cat_ent_coef", "mask_look_outside_window"}
    if not isinstance(raw, dict) or set(raw) != need:
        raise ValueError(f"train.cm 은 키 {sorted(need)} 를 모두, 그것만 적는다. 받은 값: {raw!r}")
    cats = list(raw["categories"])
    if cats not in (list(CATEGORIES[:3]), list(CATEGORIES)):
        raise ValueError(f"train.cm.categories 는 {list(CATEGORIES[:3])} 또는 {list(CATEGORIES)} 다. 받은 값: {cats}")
    p = np.asarray(raw["init_probs"], dtype=np.float64)
    if p.shape != (len(cats),) or not np.all(np.isfinite(p)) or np.any(p <= 0):
        raise ValueError(f"train.cm.init_probs 는 범주마다 양수 하나다. 받은 값: {raw['init_probs']!r}")
    ce = raw["cat_ent_coef"]
    if isinstance(ce, bool) or not isinstance(ce, (int, float)) or not math.isfinite(ce) or ce < 0:
        raise ValueError(f"train.cm.cat_ent_coef 는 0 이상의 숫자다. 받은 값: {ce!r}")
    mask = raw["mask_look_outside_window"]
    if not isinstance(mask, bool) or (mask and "look" not in cats):
        raise ValueError("train.cm.mask_look_outside_window 는 true/false 이고, true 면 categories 에 look 이 있어야 한다")
    feats = (cfg.v2.get("features") or {})
    vw = feats.get("vigil_window") or {}
    if not vw.get("enabled"):
        raise ValueError("train.cm 은 vigil_window 세계(v2.2r)에서만 쓴다")
    if "look" in cats and not (vw.get("action") and vw.get("window_only")):
        raise ValueError("look 범주는 경계 행동 열이 있고 창 안에서만 효력이 있는 세계(W′: action·window_only)에서 쓴다")
    if "look" not in cats and vw.get("action"):
        raise ValueError("look 이 없는 범주(K = 3)는 경계 행동 열이 없는 세계(action: false)에서 쓴다")
    return {"categories": cats, "init_logits": np.log(p / p.sum()).tolist(), "cat_ent_coef": float(ce),
            "mask_look": mask, "theta": float(vw["theta"])}


def cm_action_space(k: int) -> spaces.Box:
    low = np.array([-3.0] * N_STEER + [0.0], dtype=np.float32)
    high = np.array([3.0] * N_STEER + [float(k - 1)], dtype=np.float32)
    return spaces.Box(low, high, dtype=np.float32)


def cat_index(raw: np.ndarray, k: int) -> np.ndarray:
    """행동 벡터의 범주 칸 → 범주 번호 (반올림, [0, K-1] 로 자름)."""
    return np.clip(np.rint(np.asarray(raw, dtype=np.float64)), 0, k - 1).astype(np.int64)


def cm_to_world(raw: np.ndarray, cm: dict, act_names) -> np.ndarray:
    """정책 출력 (n, 5) → 세계 행동 (n, act_dim). 조향 = sigmoid(원값), speed·vigilance = 범주에서 (모듈 docstring)."""
    raw = np.asarray(raw, dtype=np.float64)
    names = list(act_names)
    cats = cm["categories"]
    c = cat_index(raw[:, N_STEER], len(cats))
    a = np.zeros((len(raw), len(names)))
    a[:, :N_STEER] = 1.0 / (1.0 + np.exp(-raw[:, :N_STEER]))
    a[:, names.index("speed")] = np.array([SPEED_VALUE[x] for x in cats])[c]
    if "vigilance" in names:
        a[:, names.index("vigilance")] = (np.array([x == "look" for x in cats])[c]).astype(np.float64)
    return a


def look_mask(obs, theta: float):
    """look 을 고를 수 있는 개체 (창 안). numpy·torch 관측 모두 받는다."""
    return (obs[:, OBS_PRED_COUNT] <= 0) & (obs[:, OBS_THREAT] > theta)


class GaussCatDistribution(DiagGaussianDistribution):
    """[조향 가우시안 N_STEER 개, 범주 하나]. 행동 벡터의 마지막 칸이 범주 번호(실수로 저장)다."""

    def __init__(self, k: int, ent_scale: float):
        super().__init__(N_STEER)
        self.k, self.ent_scale = int(k), float(ent_scale)
        self.cat: th.distributions.Categorical | None = None

    def proba_distribution_net(self, latent_dim: int, log_std_init: float = 0.0):
        net = nn.Linear(latent_dim, N_STEER + self.k)
        log_std = nn.Parameter(th.ones(N_STEER) * log_std_init, requires_grad=True)
        return net, log_std

    def proba_distribution(self, mean_actions: th.Tensor, log_std: th.Tensor, allow: th.Tensor | None = None):
        super().proba_distribution(mean_actions[:, :N_STEER], log_std)
        logits = mean_actions[:, N_STEER:]
        if allow is not None:                       # look(마지막 범주)을 창 밖에서 막는다
            neg = th.finfo(logits.dtype).min
            logits = th.cat([logits[:, :-1], th.where(allow[:, None], logits[:, -1:], th.full_like(logits[:, -1:], neg))], 1)
        self.cat = th.distributions.Categorical(logits=logits)
        return self

    def log_prob(self, actions: th.Tensor) -> th.Tensor:
        lp = super().log_prob(actions[:, :N_STEER])
        idx = th.clamp(th.round(actions[:, N_STEER]), 0, self.k - 1).long()
        return lp + self.cat.log_prob(idx)

    def entropy(self) -> th.Tensor:
        return super().entropy() + self.ent_scale * self.cat.entropy()

    def sample(self) -> th.Tensor:
        return th.cat([super().sample(), self.cat.sample().float()[:, None]], 1)

    def mode(self) -> th.Tensor:
        return th.cat([super().mode(), th.argmax(self.cat.probs, 1).float()[:, None]], 1)

    def actions_from_params(self, mean_actions, log_std, deterministic: bool = False):
        self.proba_distribution(mean_actions, log_std)
        return self.get_actions(deterministic=deterministic)

    def log_prob_from_params(self, mean_actions, log_std):
        actions = self.actions_from_params(mean_actions, log_std)
        return actions, self.log_prob(actions)


class CMPolicy(ActorCriticPolicy):
    """가우시안 조향 + 범주 보행 정책. 구조(64-64 tanh, 값 함수)는 MlpPolicy 그대로이고 출력층만 N_STEER + K 다.

    `cm_k`, `cm_init_logits`, `cm_ent_scale`(= cat_ent_coef / ent_coef), `cm_mask_theta`(None 이면 마스크 없음)를
    policy_kwargs 로 받는다. 마스크는 관측에서 만들므로 관측을 받는 공개 메서드마다 먼저 계산해 둔다.
    """

    def __init__(self, *args, cm_k: int, cm_init_logits, cm_ent_scale: float, cm_mask_theta: float | None, **kw):
        self.cm_k, self.cm_init_logits = int(cm_k), list(cm_init_logits)
        self.cm_ent_scale, self.cm_mask_theta = float(cm_ent_scale), cm_mask_theta
        self._allow: th.Tensor | None = None
        super().__init__(*args, **kw)

    def _get_constructor_parameters(self) -> dict:
        d = super()._get_constructor_parameters()
        d.update(cm_k=self.cm_k, cm_init_logits=self.cm_init_logits, cm_ent_scale=self.cm_ent_scale,
                 cm_mask_theta=self.cm_mask_theta)
        return d

    def _build(self, lr_schedule) -> None:
        self.action_dist = GaussCatDistribution(self.cm_k, self.cm_ent_scale)
        super()._build(lr_schedule)
        with th.no_grad():
            self.action_net.bias[N_STEER:] = th.as_tensor(self.cm_init_logits, dtype=self.action_net.bias.dtype)

    def _set_mask(self, obs) -> None:
        if self.cm_mask_theta is None:
            self._allow = None
        else:
            o = obs if isinstance(obs, th.Tensor) else th.as_tensor(obs)
            self._allow = look_mask(o, self.cm_mask_theta)

    def _get_action_dist_from_latent(self, latent_pi: th.Tensor):
        return self.action_dist.proba_distribution(self.action_net(latent_pi), self.log_std, self._allow)

    def forward(self, obs, deterministic: bool = False):
        self._set_mask(obs)
        return super().forward(obs, deterministic)

    def evaluate_actions(self, obs, actions):
        self._set_mask(obs)
        return super().evaluate_actions(obs, actions)

    def get_distribution(self, obs):
        self._set_mask(obs)
        return super().get_distribution(obs)


def is_cm_model(model) -> bool:
    return isinstance(getattr(model, "policy", None), CMPolicy)


def cm_distribution(model, obs: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """관측 → (조향 평균 (n,4), 조향 표준편차 (n,4), 범주 확률 (n,K)). 마스크를 적용한 확률이다."""
    pol = model.policy
    obs_t, _ = pol.obs_to_tensor(np.asarray(obs, dtype=np.float32))
    with th.no_grad():
        d = pol.get_distribution(obs_t)
        return (d.distribution.mean.cpu().numpy().astype(np.float64),
                d.distribution.stddev.cpu().numpy().astype(np.float64),
                d.cat.probs.cpu().numpy().astype(np.float64))


# --------------------------------------------------------------------- #
# 평가·배포 정책 (env_v2/rollout.py 가 CM 모델이면 이것을 쓴다)
# --------------------------------------------------------------------- #


def is_cm_file(path) -> bool:
    """SB3 zip 의 정책 클래스가 CMPolicy 인가. torch 를 싣지 않고 data 만 읽는다."""
    import json
    import zipfile

    try:
        with zipfile.ZipFile(path) as z:
            return "env_v2.cm" in json.dumps(json.loads(z.read("data")).get("policy_class"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return False


def cm_world_names(k: int) -> tuple[str, ...]:
    """범주 수 → 세계 행동 이름. K = 3 은 경계 열 없는 세계(L), K = 4 는 W′ 세계."""
    from .world import ACT_NAMES_V1

    return ACT_NAMES_V1 + ("speed",) + (("vigilance",) if k == 4 else ())


def cat_from_uniform(probs: np.ndarray, u: np.ndarray) -> np.ndarray:
    """누적 확률과 비교해 범주를 고른다: c = Σ_{j<K−1} [u ≥ P_j], P_j = p_0 + … + p_j (C++ 꼴, 누적은 double).
    마스크로 0 인 범주는 폭이 0 이라 뽑히지 않는다(u ∈ (0,1))."""
    cdf = np.cumsum(np.asarray(probs, dtype=np.float64), axis=1)[:, :-1]
    return (np.asarray(u, dtype=np.float64)[:, None] >= cdf).sum(1).astype(np.int64)


def make_cm_policy(model, seed: int, mode: str, hold_k: int | None = None, salt: int = 0):
    """CM 학습 정책 → 관측 (N, 8) → 세계 행동 (N, act_dim) 함수. mode: deterministic(최빈 범주) / hold(K 스텝 유지
    잡음의 범주, rollout.HoldLearned 와 같은 키·위상·블록, 해시 열 = 범주 칸 4) / stochastic(범주 표본, 잡음 스트림은
    rollout StochasticLearned 와 같은 [seed, 303, salt]). 조향 4열은 모든 모드에서 평균(registry 결정 모드와 같은
    float32 경로)이다."""
    from .rollout import HoldLearned, _perm_rng

    k_cat = int(model.policy.cm_k)
    names = cm_world_names(k_cat)
    cm = {"categories": list(CATEGORIES[:k_cat])}

    class _CM(HoldLearned):
        def __init__(self):
            super().__init__(model, seed, hold_k if mode == "hold" else 1, salt)
            self.rng = _perm_rng("act_sample", seed, salt) if mode == "stochastic" else None

        def __call__(self, obs):
            import torch as th

            pol = model.policy
            pol.set_training_mode(False)
            obs_t, _ = pol.obs_to_tensor(np.asarray(obs, dtype=np.float32))
            with th.no_grad():
                d = pol.get_distribution(obs_t)
                mu32 = d.distribution.mean.cpu().numpy()
                probs = d.cat.probs.cpu().numpy().astype(np.float64)
            raw = np.empty((len(mu32), N_STEER + 1))
            raw[:, :N_STEER] = np.clip(mu32, -3.0, 3.0).astype(np.float32)   # registry 와 같은 float32 clip
            if mode == "deterministic":
                c = probs.argmax(1)
            elif mode == "hold":
                u = self.noise(len(obs), [N_STEER])[:, 0]
                self.last_u = u
                c = cat_from_uniform(probs, u)
            else:
                c = cat_from_uniform(probs, self.rng.random(len(obs)))
            raw[:, N_STEER] = c
            self.last_cat, self.last_probs = c, probs
            self.tick += 1
            a = cm_to_world(raw, cm, names)
            a[:, :N_STEER] = (1.0 / (1.0 + np.exp(-raw[:, :N_STEER].astype(np.float32)))).astype(np.float64)
            return a

    return _CM()
