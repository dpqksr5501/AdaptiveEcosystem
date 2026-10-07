"""v3 R1 행동 고르기 정책 — 마스크·ε 혼합 범주 분포·정책 (명세 `Docs/RL_Policy/RL_V3_R1_SPEC.md` 2·3절).

행동 공간은 늘 Discrete(5)이고 계약 순서를 따른다(env_v2/repertoire.py: 0 GRAZE, 1 FLEE, 2 HIDE, 3 FREEZE, 4 SLEEP). 목록에 없는
행동은 번호를 바꾸지 않고 마스크로 막는다.

마스크 m (5칸, 0/1) = 허용 ∧ 가능 ∧ 결정 (`action_mask`). 셋 다 결정 때 계산하고 세계 상태를 바꾸지 않는다.
  - 허용: 설정 `train.repertoire.allowed` 의 행동만
  - 가능 (`feasible_mask`, 관측으로만 계산하므로 C++ 과 파리티): '위협을 안다' = 관측 pred_count > 0 이거나 threat_recency ≥
    THREAT_RECENCY_OBS(0.2 — 감쇠 0.95 에서 마지막으로 본 뒤 약 31스텝 ≈ 4초 안). FLEE·FREEZE 는 위협을 알 때, HIDE 는 위협을 알고
    관측 cover_dist < HIDE_COVER_OBS(0.75)일 때, GRAZE·SLEEP 은 늘. 관측 칸은 이름(`World.obs_names`)으로 찾는다.
    (10-07 첫 학습 조기 중단 뒤 수정, results/v3/r1/PREREG.md 변경 기록: 처음 정의 'threat_recency > 0' 은 곱 감쇠라 본 뒤
    약 2000스텝 동안 0 이 되지 않아 결정 시점의 53% 에서 위협이 안 보이는데도 FLEE·FREEZE 가, 79% 에서 HIDE 가 열려 있었고,
    평시의 기울기가 도망 확률을 끌어내려 2M 에 붕괴했다 — 초안이 마스크로 막으려던 v2.2식 붕괴 그대로)
  - 결정 (`World.rep_peek`): 다음 스텝의 `arbitrate` 가 요청을 읽는 개체만 고를 수 있다. 읽지 않는 개체는 지금 행동 한 칸만
    1 이다(log π = 0 이라 actor 기울기가 없고 critic 만 배운다). 기상 결정에서는 SLEEP 을 막는다(기상 결정의 SLEEP 요청은
    wake_target 으로 바뀌어 다른 칸과 같은 뜻이 된다)
  - 비지 않음: GRAZE 는 늘 허용 ∧ 가능이라(`rep_params` 가 graze 를 요구한다) 결정 시점의 m 은 비지 않는다

정책 입력 (`policy_obs`): [세계 관측 obs_dim | m 5칸]. 정책(`RepertoirePolicy`)은 앞 obs_dim 칸만 망에 넣고(`RepObsSlice`) 뒤
5칸은 마스크로만 쓴다. 망은 obs_dim → 64 → 64 → 로짓 5, 가치망 따로 64·64, tanh (v2 와 같은 PPO_KWARGS 구조·초기화).

학습 분포 (`MaskedEpsCategorical`):
  π  = softmax(마스크 로짓)                   — 막힌 칸의 로짓은 MASK_LOGIT(−1e9)이라 확률이 정확히 0 이다
  π′ = (1 − ε)·π + ε·U(m)                     — ε = train.repertoire.epsilon, U(m) = m 위의 균등
  표본·log prob(PPO 비율)는 π′ 로 낸다. 엔트로피는 π(ε 제외)의 엔트로피 × ent_scale 이다. SB3 PPO 는 ent_coef × entropy() 를
  쓰므로 ent_scale = cat_ent_coef / ent_coef 로 두면 손실의 엔트로피 계수가 cat_ent_coef = ent_coef_base ÷ f_dec 가 된다
  (env_v2/cm.py 와 같은 방식). 잠긴 스텝은 엔트로피가 0 이라 평균이 결정 비율 f_dec 만큼 묽어지기 때문이다.
  m 이 한 칸뿐이면 log π′ = 0, 엔트로피 0 이다(정확히 0 으로 둔다).
배포·판정 분포: 마스크 로짓의 argmax, 동점이면 낮은 번호(`mode`). SB3 `predict(deterministic=True)` 가 이 값을 낸다.
시작 확률: 로짓 편향 = log(init_probs / Σ init_probs), 가중치는 SB3 직교 초기화 gain 0.01 그대로라 거의 상수다. 마스크가 막은
칸은 나머지로 다시 맞춰진다.

설정 블록 (`rep_params`, 기본값 없음, 키를 모두 적는다):
    train:
      repertoire:
        allowed: [graze, flee, hide]       # 행동 이름(repertoire.BEHAVIOR_NAMES). graze·flee 는 꼭 있어야 한다
        epsilon: 0.05                      # [0, 1)
        init_probs: [0.4, 0.15, 0.15, 0.15, 0.15]   # 행동마다 양수 하나(계약 순서)
        ent_coef_base: <v2.4s ent_coef>    # 0 이상
        f_dec: <학습 전 측정값>            # (0, 1], `train_v3.py measure-fdec` 로 잰다
이 블록이 있는 repertoire 세계에서만 `env_v2/vec_env.py` 가 이산 학습 경로를 쓴다(없으면 지금처럼 거부한다).
"""

from __future__ import annotations

import math

import numpy as np
import torch as th
from gymnasium import spaces
from stable_baselines3.common.distributions import CategoricalDistribution
from stable_baselines3.common.policies import ActorCriticPolicy
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from torch.distributions import Categorical

from .repertoire import BEHAVIOR_NAMES, FLEE, FREEZE, HIDE, N_BEHAVIORS, SLEEP

# 가능 조건의 문턱 (명세 2절 '가능' — 관측 계약 값이고 학습 계수가 아니다. C++ 마스크도 같은 값을 쓴다):
# HIDE 는 은신처 거리 관측(가장자리까지 / obs_cover_norm, [0, 1])이 이 값보다 작을 때만 고를 수 있다
HIDE_COVER_OBS = 0.75
# '위협을 안다'의 기억 문턱: threat_recency(본 순간 1, 스텝마다 × recency_decay) 가 이 값 이상이면 방금 본 위협을 아직 안다.
# 감쇠 0.95 에서 0.95^31 ≈ 0.204 — 마지막으로 본 뒤 약 31스텝(4초). 관측 계약 값이다(C++ 마스크도 같은 값)
THREAT_RECENCY_OBS = 0.2
# 마스크 계약 판. 가능 조건(위 두 문턱과 '숨기도 위협을 알 때만')을 바꾸면 올린다. 정책이 판을 저장하고(`rep_mask_version`),
# 판정 롤아웃(`env_v2/rollout.py` RepLearned.bind_world)이 지금 코드의 판과 다르면 멈춘다 — 다른 마스크로 조용히 판정하지 않게.
# 1 = 첫 학습(threat_recency > 0, 숨기는 은신처만), 2 = 10-07 수정(threat_recency ≥ 0.2, 숨기도 위협을 알 때만)
MASK_VERSION = 2
# 막힌 칸의 로짓. softmax 의 exp(−1e9 − ·) 는 float32 에서 정확히 0 이고, 유한한 값이라 0·log 0 이 nan 이 되지 않는다
MASK_LOGIT = -1e9
REP_KEYS = frozenset({"allowed", "epsilon", "init_probs", "ent_coef_base", "f_dec"})
# 가능 조건이 읽는 관측 칸 이름
_FEAS_COLS = ("pred_count", "threat_recency", "cover_dist")


def _number(key: str, x) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) or not math.isfinite(x):
        raise ValueError(f"train.repertoire.{key} 는 유한한 숫자여야 한다. 받은 값: {x!r}")
    return float(x)


def rep_params(cfg) -> dict | None:
    """설정의 `train.repertoire` 블록(모듈 docstring)을 검사한다. 없으면 None (연속 행동 세계, 지금과 같다). 기본값은 없다.

    반환: allowed(계약 순서의 이름 튜플), allowed_mask((5,) bool), epsilon, init_probs(list), init_logits(log(p/Σp) list),
    ent_coef_base, f_dec, cat_ent_coef(= ent_coef_base / f_dec).
    repertoire 를 켜고 obs_extra 가 true 인 세계에서만 쓴다(가능 조건이 threat_recency 관측을 읽는다, 명세 1절).
    """
    raw = ((getattr(cfg, "v2", None) or {}).get("train") or {}).get("repertoire")
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != REP_KEYS:
        raise ValueError(f"train.repertoire 는 키 {sorted(REP_KEYS)} 를 모두, 그것만 적는다. 받은 값: {raw!r}")
    allowed = raw["allowed"]
    if (not isinstance(allowed, (list, tuple)) or not allowed or any(not isinstance(a, str) for a in allowed)
            or len(set(allowed)) != len(allowed) or any(a not in BEHAVIOR_NAMES for a in allowed)):
        raise ValueError(f"train.repertoire.allowed 는 {list(BEHAVIOR_NAMES)} 중 겹치지 않는 이름 목록이다. 받은 값: {allowed!r}")
    if "graze" not in allowed or "flee" not in allowed:
        raise ValueError(f"train.repertoire.allowed 에는 graze 와 flee 가 늘 있어야 한다(명세 머리말). 받은 값: {allowed!r}")
    eps = _number("epsilon", raw["epsilon"])
    if not 0.0 <= eps < 1.0:
        raise ValueError(f"train.repertoire.epsilon 은 [0, 1) 이어야 한다. 받은 값: {eps}")
    ip = raw["init_probs"]
    if not isinstance(ip, (list, tuple)) or len(ip) != N_BEHAVIORS:
        raise ValueError(f"train.repertoire.init_probs 는 행동 {N_BEHAVIORS}개(계약 순서)마다 양수 하나다. 받은 값: {ip!r}")
    p = np.array([_number("init_probs", x) for x in ip], dtype=np.float64)
    if np.any(p <= 0.0):
        raise ValueError(f"train.repertoire.init_probs 는 모두 양수여야 한다. 받은 값: {ip!r}")
    base = _number("ent_coef_base", raw["ent_coef_base"])
    if base < 0.0:
        raise ValueError(f"train.repertoire.ent_coef_base 는 0 이상이어야 한다. 받은 값: {base}")
    f_dec = _number("f_dec", raw["f_dec"])
    if not 0.0 < f_dec <= 1.0:
        raise ValueError(f"train.repertoire.f_dec 는 (0, 1] 이어야 한다. 받은 값: {f_dec}")
    feats = (cfg.v2.get("features") or {})
    rp = feats.get("repertoire") or {}
    if not rp.get("enabled"):
        raise ValueError("train.repertoire 는 repertoire 세계(v3, features.repertoire.enabled)에서만 쓴다")
    if rp.get("obs_extra") is not True:
        raise ValueError("train.repertoire 는 features.repertoire.obs_extra: true 세계에서만 쓴다(가능 조건이 threat_recency "
                         "관측을 읽고, 정책이 지금 행동 관측을 본다 — 명세 1절)")
    names = tuple(b for b in BEHAVIOR_NAMES if b in allowed)
    return {"allowed": names, "allowed_mask": np.array([b in names for b in BEHAVIOR_NAMES], dtype=bool),
            "epsilon": eps, "init_probs": p.tolist(), "init_logits": np.log(p / p.sum()).tolist(),
            "ent_coef_base": base, "f_dec": f_dec, "cat_ent_coef": base / f_dec}


def allowed_mask_of(names) -> np.ndarray:
    """행동 이름 목록 → (5,) bool 허용 칸."""
    names = list(names)
    bad = [b for b in names if b not in BEHAVIOR_NAMES]
    if bad:
        raise ValueError(f"모르는 행동 이름 {bad}. 쓸 수 있는 이름: {list(BEHAVIOR_NAMES)}")
    return np.array([b in names for b in BEHAVIOR_NAMES], dtype=bool)


def feasible_mask(obs, obs_names) -> np.ndarray:
    """관측 (n, obs_dim) → 가능 칸 (n, 5) bool (모듈 docstring '가능'). 관측 칸은 이름으로 찾는다."""
    names = list(obs_names)
    missing = [c for c in _FEAS_COLS if c not in names]
    if missing:
        raise ValueError(f"가능 조건은 관측 {missing} 가 필요하다(features.repertoire.obs_extra: true 세계)")
    o = np.asarray(obs)
    threat = (o[:, names.index("pred_count")] > 0.0) | (o[:, names.index("threat_recency")] >= THREAT_RECENCY_OBS)
    f = np.ones((len(o), N_BEHAVIORS), dtype=bool)
    f[:, FLEE] = threat
    f[:, FREEZE] = threat
    f[:, HIDE] = threat & (o[:, names.index("cover_dist")] < HIDE_COVER_OBS)
    return f


def action_mask(src, obs, params, obs_names=None) -> np.ndarray:
    """마스크 m (n, 5) bool = 허용 ∧ 가능 ∧ 결정 (모듈 docstring). 세계 상태를 바꾸지 않는다.

    `src` 는 World(`rep_peek()` 을 부르고 관측 이름은 `World.obs_names`) 또는 `rep_peek()` 이 낸 dict(그때는 `obs_names` 를
    준다). `obs` 는 지금 세계 관측(가능 조건용 — 결정 때 관측). `params` 는 `rep_params` 반환(또는 allowed_mask 가 있는 dict).
    결정 시점이 아닌 개체는 지금 행동 한 칸, 기상 결정은 SLEEP 을 막는다. 빈 행이 있으면 멈춘다(설계상 없다).
    """
    if isinstance(src, dict):
        if obs_names is None:
            raise ValueError("action_mask 에 미리 보기 dict 를 줄 때는 obs_names 도 준다")
        pk = src
    else:
        pk = src.rep_peek()
        obs_names = src.obs_names if obs_names is None else obs_names
    m = params["allowed_mask"][None, :] & feasible_mask(obs, obs_names)
    reads = np.asarray(pk["reads"], dtype=bool)
    m[:, SLEEP] &= ~np.asarray(pk["wake_decide"], dtype=bool)
    beh = np.asarray(pk["behavior"], dtype=np.int64)
    one = np.zeros_like(m)
    one[np.arange(len(beh)), beh] = True
    m = np.where(reads[:, None], m, one)
    if not m.any(1).all():
        raise ValueError(f"빈 마스크 행이 있다(개체 {np.flatnonzero(~m.any(1))[:5].tolist()}). GRAZE 가 허용·가능이어야 한다")
    return m


def sample_masked(probs, mask, u) -> np.ndarray:
    """누적 확률 비교로 마스크 안의 행동을 고른다 (C++ 로 옮기기 쉬운 꼴, f_dec 측정·C1′ 대조군이 쓴다).

    p = probs·m 을 행마다 다시 맞춘 누적 P_j 에서 c = 'u < P_j 이고 m_j 인 첫 j'. 막힌 칸은 폭이 0 이라 뽑히지 않고,
    float 반올림으로 u 가 마지막 누적값을 넘으면 마지막 허용 칸을 고른다(막힌 칸이 나오지 않는다). `u` ∈ (0, 1) (n,).
    """
    m = np.asarray(mask, dtype=bool)
    p = np.where(m, np.asarray(probs, dtype=np.float64), 0.0)
    s = p.sum(1, keepdims=True)
    p = np.where(s > 0.0, p / np.where(s > 0.0, s, 1.0), m / np.maximum(m.sum(1, keepdims=True), 1))
    hit = (np.asarray(u, dtype=np.float64)[:, None] < np.cumsum(p, axis=1)) & m
    last = N_BEHAVIORS - 1 - np.argmax(m[:, ::-1], axis=1)
    return np.where(hit.any(1), np.argmax(hit, axis=1), last).astype(np.int64)


def policy_obs(obs, mask) -> np.ndarray:
    """정책 입력 [세계 관측 | 마스크 5칸] (n, obs_dim + 5) float32."""
    return np.concatenate([np.asarray(obs, dtype=np.float32), np.asarray(mask, dtype=np.float32)], axis=1)


# --------------------------------------------------------------------- #
# 분포
# --------------------------------------------------------------------- #


class MaskedEpsCategorical(CategoricalDistribution):
    """마스크·ε 혼합 범주 분포 (모듈 docstring '학습 분포'). `proba_distribution(로짓, 마스크)` 뒤에 쓴다."""

    def __init__(self, action_dim: int, epsilon: float, ent_scale: float):
        super().__init__(action_dim)
        self.epsilon, self.ent_scale = float(epsilon), float(ent_scale)
        self.mask: th.Tensor | None = None
        self.logits_m: th.Tensor | None = None
        self.log_pi: th.Tensor | None = None
        self.probs_eps: th.Tensor | None = None
        self.n_allowed: th.Tensor | None = None

    def proba_distribution(self, action_logits: th.Tensor, mask: th.Tensor | None = None):
        if mask is None:
            mask = th.ones_like(action_logits, dtype=th.bool)
        mask = mask.to(th.bool)
        lm = th.where(mask, action_logits, th.full_like(action_logits, MASK_LOGIT))
        self.mask, self.logits_m = mask, lm
        self.log_pi = th.log_softmax(lm, dim=1)
        pi = th.exp(self.log_pi)
        self.n_allowed = mask.sum(1)
        u = mask.to(pi.dtype) / self.n_allowed.clamp(min=1).to(pi.dtype)[:, None]
        self.probs_eps = (1.0 - self.epsilon) * pi + self.epsilon * u if self.epsilon > 0.0 else pi
        self.distribution = Categorical(probs=self.probs_eps, validate_args=False)
        return self

    def probs_masked(self) -> th.Tensor:
        """π (ε 제외, 막힌 칸 0)."""
        return th.exp(self.log_pi)

    def log_prob(self, actions: th.Tensor) -> th.Tensor:
        a = actions.long().reshape(-1, 1)
        lp = self.log_pi.gather(1, a).squeeze(1)
        in_m = self.mask.gather(1, a).squeeze(1)
        if self.epsilon > 0.0:
            n = self.n_allowed.clamp(min=1).to(lp.dtype)
            lu = th.where(in_m, math.log(self.epsilon) - th.log(n), th.full_like(lp, -math.inf))
            lp = th.logaddexp(lp + math.log1p(-self.epsilon), lu)
        return th.where(in_m & (self.n_allowed == 1), th.zeros_like(lp), lp)

    def raw_entropy(self) -> th.Tensor:
        """π(ε 제외)의 엔트로피 (배율 없음). 막힌 칸은 π = 0 이라 0 이고, 한 칸 마스크는 정확히 0 이다."""
        pi = th.exp(self.log_pi)
        h = -(pi * self.log_pi).sum(1)
        return th.where(self.n_allowed <= 1, th.zeros_like(h), h)

    def entropy(self) -> th.Tensor:
        return self.ent_scale * self.raw_entropy()

    def sample(self) -> th.Tensor:
        return self.distribution.sample()

    def mode(self) -> th.Tensor:
        # torch.argmax 는 최댓값이 여럿이면 첫 번째(낮은 번호)를 낸다 — 모드 0 관례(v1 결정적)
        return th.argmax(self.logits_m, dim=1)

    def actions_from_params(self, action_logits: th.Tensor, deterministic: bool = False, mask=None) -> th.Tensor:
        self.proba_distribution(action_logits, mask)
        return self.get_actions(deterministic=deterministic)

    def log_prob_from_params(self, action_logits: th.Tensor, mask=None):
        actions = self.actions_from_params(action_logits, mask=mask)
        return actions, self.log_prob(actions)


# --------------------------------------------------------------------- #
# 정책
# --------------------------------------------------------------------- #


class RepObsSlice(BaseFeaturesExtractor):
    """정책 입력의 앞 `obs_dim` 칸(세계 관측)만 망에 넘긴다. 뒤 5칸(마스크)은 망에 들어가지 않는다."""

    def __init__(self, observation_space: spaces.Box, obs_dim: int):
        super().__init__(observation_space, features_dim=int(obs_dim))
        self.obs_dim = int(obs_dim)

    def forward(self, observations: th.Tensor) -> th.Tensor:
        return observations[:, :self.obs_dim]


class RepertoirePolicy(ActorCriticPolicy):
    """행동 고르기 정책 (모듈 docstring). 관측 [세계 관측 obs_dim | 마스크 5], 행동 Discrete(5).

    policy_kwargs 로 `rep_allowed`(허용 행동 이름 — 판정 롤아웃의 `rep_learned` 가 마스크를 다시 만들 때 쓴다), `rep_epsilon`,
    `rep_ent_scale`(= cat_ent_coef / ent_coef), `rep_init_logits`(시작 로짓 편향 5), `rep_obs_names`(학습 세계 관측 이름 —
    판정 세계와 맞는지 본다)를 받는다. 구조(net_arch·activation_fn)는 train.PPO_KWARGS 그대로다. 마스크는 관측 뒤 5칸에서
    만들므로 관측을 받는 공개 메서드마다 먼저 계산해 둔다(env_v2/cm.py 와 같은 방식).
    """

    def __init__(self, observation_space, action_space, lr_schedule, *args, rep_allowed, rep_epsilon: float,
                 rep_ent_scale: float, rep_init_logits, rep_obs_names, rep_mask_version: int = 1, **kw):
        if not isinstance(action_space, spaces.Discrete) or int(action_space.n) != N_BEHAVIORS:
            raise ValueError(f"RepertoirePolicy 의 행동 공간은 Discrete({N_BEHAVIORS}) 다. 받은 값: {action_space}")
        obs_dim = int(observation_space.shape[0]) - N_BEHAVIORS
        if len(observation_space.shape) != 1 or obs_dim != len(rep_obs_names):
            raise ValueError(f"관측 공간 {observation_space.shape} 이 [세계 관측 {len(rep_obs_names)} | 마스크 "
                             f"{N_BEHAVIORS}] 와 다르다")
        self.rep_allowed = tuple(rep_allowed)
        self.rep_allowed_mask = allowed_mask_of(self.rep_allowed)
        self.rep_epsilon, self.rep_ent_scale = float(rep_epsilon), float(rep_ent_scale)
        self.rep_init_logits = [float(x) for x in rep_init_logits]
        self.rep_obs_names = tuple(rep_obs_names)
        # 판이 없는 저장 파일(첫 학습)은 1 이다
        self.rep_mask_version = int(rep_mask_version)
        self.rep_obs_dim = obs_dim
        if len(self.rep_init_logits) != N_BEHAVIORS:
            raise ValueError(f"rep_init_logits 는 {N_BEHAVIORS}개다. 받은 값: {rep_init_logits!r}")
        self._mask: th.Tensor | None = None
        kw["features_extractor_class"] = RepObsSlice
        kw["features_extractor_kwargs"] = dict(obs_dim=obs_dim)
        super().__init__(observation_space, action_space, lr_schedule, *args, **kw)

    def _get_constructor_parameters(self) -> dict:
        d = super()._get_constructor_parameters()
        d.update(rep_allowed=list(self.rep_allowed), rep_epsilon=self.rep_epsilon, rep_ent_scale=self.rep_ent_scale,
                 rep_init_logits=self.rep_init_logits, rep_obs_names=list(self.rep_obs_names),
                 rep_mask_version=self.rep_mask_version)
        return d

    def _build(self, lr_schedule) -> None:
        self.action_dist = MaskedEpsCategorical(N_BEHAVIORS, self.rep_epsilon, self.rep_ent_scale)
        super()._build(lr_schedule)
        with th.no_grad():
            self.action_net.bias[:] = th.as_tensor(self.rep_init_logits, dtype=self.action_net.bias.dtype)

    def _set_mask(self, obs) -> None:
        o = obs if isinstance(obs, th.Tensor) else th.as_tensor(np.asarray(obs))
        self._mask = o[:, self.rep_obs_dim:] > 0.5

    def _get_action_dist_from_latent(self, latent_pi: th.Tensor):
        return self.action_dist.proba_distribution(self.action_net(latent_pi), self._mask)

    def forward(self, obs, deterministic: bool = False):
        self._set_mask(obs)
        return super().forward(obs, deterministic)

    def evaluate_actions(self, obs, actions):
        self._set_mask(obs)
        return super().evaluate_actions(obs, actions)

    def get_distribution(self, obs):
        self._set_mask(obs)
        return super().get_distribution(obs)


def is_rep_model(model) -> bool:
    return isinstance(getattr(model, "policy", None), RepertoirePolicy)


def rep_distribution(policy: RepertoirePolicy, pobs: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """정책 입력 (n, obs_dim + 5) → (π (n,5) ε 제외·막힌 칸 0, π′ (n,5) ε 혼합, π 엔트로피 (n,) 배율 없음). float64."""
    obs_t, _ = policy.obs_to_tensor(np.asarray(pobs, dtype=np.float32))
    with th.no_grad():
        d = policy.get_distribution(obs_t)
        return (d.probs_masked().cpu().numpy().astype(np.float64), d.probs_eps.cpu().numpy().astype(np.float64),
                d.raw_entropy().cpu().numpy().astype(np.float64))


def rep_argmax(policy: RepertoirePolicy, pobs: np.ndarray) -> np.ndarray:
    """정책 입력 → 마스크 로짓 argmax (동점이면 낮은 번호) (n,) int64. `predict(deterministic=True)` 와 같은 값이다."""
    policy.set_training_mode(False)
    obs_t, _ = policy.obs_to_tensor(np.asarray(pobs, dtype=np.float32))
    with th.no_grad():
        return policy.get_distribution(obs_t).mode().cpu().numpy().astype(np.int64)


def is_rep_file(path) -> bool:
    """SB3 zip 의 정책 클래스가 RepertoirePolicy 인가. torch 를 싣지 않고 data 만 읽는다."""
    import json
    import zipfile

    try:
        with zipfile.ZipFile(path) as z:
            return "env_v2.rep_policy" in json.dumps(json.loads(z.read("data")).get("policy_class"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return False
