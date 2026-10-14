"""V2 학습용 VecEnv — 독립 세계 K 개를 하나로 묶는다 (계획서 4.7).

v1 `env/vec_env.py` 의 HerdVecEnv 는 World 하나를 감쌌다. 학습 중 reset 은 생성 때와 learn
시작 때 두 번뿐이라 정책은 사실상 세계 하나(시드 636)에서만 배웠다. 여기서는

- 세계 K 개(각 N 슬롯)를 동시에 돌린다. num_envs = K × N. 롤아웃 한 배치에 늘 K 개 세계가 섞인다
- 세계마다 `reset_interval`(T) 스텝이 지나면 새 시드로 다시 뽑는다. 세계 k 는 처음에 k·T/K 스텝을
  이미 산 것으로 두어 리셋이 T/K 간격으로 엇갈린다
- 리셋으로 끊긴 슬롯은 done=True + `terminal_observation` + `TimeLimit.truncated=True` 로 보낸다.
  SB3 는 이때 보상에 γ·V(terminal_obs) 를 더한다 (on_policy_algorithm.collect_rollouts).
  같은 스텝에 죽은 슬롯은 사망이 우선한다 — truncated 를 싣지 않는다. 실으면 사망 비용이 줄어든다
- 동시에 도는 세계끼리는 시드가 겹치지 않는다

슬롯 하나 = SB3 환경 하나라는 v1 규약은 그대로다. 정책의 (-3,3) 출력을 [0,1] 로 바꾸는
sigmoid 도 여기에만 있다 (§1.3). 행동·관측 공간의 차원은 설정에서 읽는다(`World.act_dim`: v1 4, speed 를 켜면 5,
vigilance 까지 켜면 6. `World.obs_dim`: v1 7, vigilance 를 켜면 8).
설정에 `train.cm`(v2.2r 범주형 보행, `env_v2/cm.py`)이 있으면 정책 출력은 [조향 원값 4, 범주 번호] 이고 행동 공간은
`cm_action_space(K)` 다. 세계 행동으로 바꾸는 `cm_to_world` 도 step_async 에서만 부른다.

학습 세계 균형 추출(S1-a, 10-04 사용자 결정, `results/v2/s1a/PREREG.md`): 설정에 `train.world_sampling` 이 있으면 새 세계를
고를 때 후보 `candidates` 개를 메타 난수로 뽑고, '지금까지 고른 세계들(초기 세계 포함, 세계마다 같은 무게)의 표준화 평균'이
풀 평균(0)에 가장 가까워지는 후보를 고른다. 표준화는 풀 전체의 평균·표준편차로 하고 `keys`(`env_v2.world.world_params` 의
키)만 본다. 동시에 도는 세계와 겹치지 않는 규칙·세계 수·교체 주기는 그대로다. 블록이 없으면 지금과 같다(메타 난수 소비도 같다).
    train:
      world_sampling: {mode: balanced, candidates: 8, keys: [food_regen_mult, predator_count]}
학습 세계 하한(S1-a 사전 등록 4절 2차 대응 1, 쓸 때만): `train.world_pool_min: {food_regen_mult: 1.0}` 이면 학습 풀에서
그 값보다 작은 세계를 뺀다(`world_params` 기준). 평가 세계 분포는 그대로다. 블록이 없으면 지금과 같다.

v3 R1 이산 행동 경로 (명세 `Docs/RL_Policy/RL_V3_R1_SPEC.md` 2·4절, `env_v2/rep_policy.py`): repertoire 세계이고 설정에
`train.repertoire` 블록이 있을 때만 쓴다(블록이 없는 repertoire 세계는 지금처럼 거부한다).
  - 행동 공간 Discrete(5)(계약 순서의 행동 번호), 관측 공간 Box(0, 1, (obs_dim + 5,)) = [세계 관측 | 마스크 m]
  - reset·step 뒤마다 세계별로 `World.rep_peek()`(순수)과 지금 관측으로 m = 허용 ∧ 가능 ∧ 결정을 만들어 붙인다
  - step_async 는 행동 번호를 세계의 'behavior' 열(float)로 바꾸고, 마스크 밖 행동이면 멈춘다(학습 분포 π′ 는 막힌 칸이
    정확히 0 이라 생기지 않는다 — 생기면 버그다)
  - 끊긴 슬롯의 terminal_observation 에도 그 세계 마지막 상태(교체 전)의 마스크를 붙인다. 사망 슬롯은 리스폰 뒤 상태의
    마스크라 그 개체의 것이 아니지만 SB3 는 사망의 terminal_observation 을 쓰지 않는다(부트스트랩은 끊긴 슬롯만)
  - 학습 기록용 누적 수(`rep_counts`): 개체-스텝, 결정(요청을 읽은) 수, 피식·아사 수, 실행 행동별 수. `last_reads` = 방금
    스텝에서 요청을 읽은 개체(SB3 롤아웃 버퍼 순서와 같은 (num_envs,) bool)
세계 뽑기·엇갈린 교체·사망 우선 규칙은 연속 경로와 같다.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np
from gymnasium.spaces import Box, Discrete
from stable_baselines3.common.vec_env.base_vec_env import VecEnv

from .cm import cm_action_space, cm_params, cm_to_world
from .features import features_of
from .repertoire import N_BEHAVIORS
from .world import ACT_DIM, OBS_DIM, WORLD_PARAM_KEYS, World, world_params

OBS_SPACE = Box(0.0, 1.0, (OBS_DIM,), np.float32)   # v1 관측 7개. 세계의 관측 공간은 obs_space(obs_dim)
ACT_SPACE = Box(-3.0, 3.0, (ACT_DIM,), np.float32)    # v1 행동 4개. 세계의 행동 공간은 act_space(act_dim)


def obs_space(obs_dim: int) -> Box:
    """관측 `obs_dim` 개의 공간 [0, 1] (§3.1). 7 이면 OBS_SPACE 와 같다."""
    return Box(0.0, 1.0, (int(obs_dim),), np.float32)


def act_space(act_dim: int) -> Box:
    """행동 `act_dim` 개의 정책 출력 공간 (-3, 3). SB3 는 표본을 이 범위로 자른 뒤 env 에 넘긴다."""
    return Box(-3.0, 3.0, (int(act_dim),), np.float32)


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def world_pool_min_params(raw) -> dict | None:
    """`train.world_pool_min` 블록({world_params 키: 하한})을 검사한다. 없으면 None."""
    if raw is None:
        return None
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"train.world_pool_min 은 {{키: 하한}} 이다. 받은 값: {raw!r}")
    out = {}
    for k, v in raw.items():
        if k not in WORLD_PARAM_KEYS:
            raise ValueError(f"train.world_pool_min 의 키는 {list(WORLD_PARAM_KEYS)} 중 하나다. 받은 값: {k!r}")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"train.world_pool_min.{k} 는 유한한 숫자다. 받은 값: {v!r}")
        out[k] = float(v)
    return out


def world_sampling_params(raw) -> dict | None:
    """`train.world_sampling` 블록을 검사한다. 없으면 None (지금과 같은 균등 추출). 기본값은 없다."""
    if raw is None:
        return None
    need = {"mode", "candidates", "keys"}
    if not isinstance(raw, dict) or set(raw) != need:
        raise ValueError(f"train.world_sampling 은 키 {sorted(need)} 를 모두, 그것만 적는다. 받은 값: {raw!r}")
    if raw["mode"] != "balanced":
        raise ValueError(f"train.world_sampling.mode 는 balanced 만 있다. 받은 값: {raw['mode']!r}")
    c = raw["candidates"]
    if isinstance(c, bool) or not isinstance(c, int) or c < 1:
        raise ValueError(f"train.world_sampling.candidates 는 1 이상의 정수다. 받은 값: {c!r}")
    keys = list(raw["keys"])
    if not keys or any(k not in WORLD_PARAM_KEYS for k in keys) or len(set(keys)) != len(keys):
        raise ValueError(f"train.world_sampling.keys 는 {list(WORLD_PARAM_KEYS)} 중 겹치지 않는 하나 이상이다. 받은 값: {keys}")
    return {"mode": "balanced", "candidates": int(c), "keys": keys}


class MultiWorldVecEnv(VecEnv):
    metadata = {"render_modes": []}

    def __init__(self, cfg, num_worlds: int | None = None, reset_interval: int | None = None,
                 seeds=None, meta_seed: int = 0):
        train = (getattr(cfg, "v2", None) or {}).get("train", {})
        self.cfg = cfg
        # v3 R1 이산 행동 경로(모듈 docstring): repertoire 세계 + train.repertoire 블록일 때만. 없으면 None (지금과 같다)
        self.rep = None
        if features_of(cfg).enabled("repertoire"):
            from .rep_policy import rep_params

            self.rep = rep_params(cfg)
            if self.rep is None:
                # 행동이 이산 행동 번호 한 열이다. 연속 (-3, 3) → sigmoid 경로의 (0, 1) 값은 정수가 아니라 세계가 거부한다
                # (내림하면 늘 GRAZE 라 아무것도 배우지 않는다). 이산 행동 학습 경로(R1)는 train.repertoire 블록이 켠다
                raise ValueError("repertoire 세계(v3)는 train.repertoire 블록(R1 이산 행동 경로, env_v2/rep_policy.py)이 "
                                 "있어야 학습한다. 블록이 없으면 이 VecEnv 는 연속 행동 세계만 받는다")
        self.K = int(num_worlds if num_worlds is not None else train.get("num_worlds", 8))
        self.T = int(reset_interval if reset_interval is not None else train.get("reset_interval", 4000))
        if self.K < 1 or self.T < 1:
            raise ValueError(f"num_worlds={self.K}, reset_interval={self.T} 는 1 이상이어야 한다")
        if seeds is None:
            lo, hi = cfg.train_seeds
            seeds = range(lo, hi)
        self.pool = np.asarray(list(seeds), dtype=np.int64)
        pmin = world_pool_min_params(train.get("world_pool_min"))
        if pmin:
            keep = [s for s in self.pool.tolist()
                    if all(world_params(cfg, int(s))[k] >= v for k, v in pmin.items())]
            if len(keep) < 2 * (int(num_worlds if num_worlds is not None else train.get("num_worlds", 8))):
                raise ValueError(f"train.world_pool_min {pmin} 로 남는 학습 세계가 {len(keep)}개뿐이다")
            self.pool = np.asarray(keep, dtype=np.int64)
        self._meta = np.random.default_rng(meta_seed)
        self._ws = world_sampling_params(train.get("world_sampling"))
        if self._ws is not None:
            keys = self._ws["keys"]
            feats = np.array([[world_params(cfg, int(s))[k] for k in keys] for s in self.pool], dtype=np.float64)
            mu, sd = feats.mean(0), feats.std(0)
            sd = np.where(sd > 0, sd, 1.0)
            self._ws_z = dict(zip(self.pool.tolist(), (feats - mu) / sd))
            self._ws_sum = np.zeros(len(keys))
            self._ws_n = 0
            self.ws_picked: list[int] = []      # 고른 순서 (진단·테스트용)

        self.worlds: list[World] = []
        for _ in range(self.K):
            s = self._pick_seed(exclude=[w.seed for w in self.worlds])
            self.worlds.append(World(cfg, seeds=[s]))
        self.N = self.worlds[0].N
        self.act_dim = self.worlds[0].act_dim
        self.act_names = self.worlds[0].act_names
        self.obs_dim = self.worlds[0].obs_dim
        self.obs_names = self.worlds[0].obs_names
        # v2.2r CM (env_v2/cm.py): 설정 train.cm 이 있으면 정책 출력은 [조향 4, 범주 번호] 이고 step_async 가 세계 행동
        # (act_dim 열)으로 바꾼다. 없으면 None 이고 지금과 같다(정책 출력 = act_dim 개 원값, sigmoid).
        self.cm = cm_params(cfg)
        self._age = self._staggered_ages()
        self._fresh = True          # 한 스텝도 안 돈 세계는 reset() 이 다시 뽑지 않는다
        self.num_resets = 0         # 시간 초과로 세계를 새로 뽑은 횟수
        self.seed_history: list[list[int]] = [[w.seed] for w in self.worlds]
        self._actions: np.ndarray | None = None
        self.render_mode = None
        if self.rep is not None:
            # v3 R1 이산 경로: 정책 입력 = [세계 관측 | 마스크 5], 행동 = 행동 번호 Discrete(5)
            self.policy_obs_dim = self.obs_dim + N_BEHAVIORS
            self._mask = np.zeros((self.K * self.N, N_BEHAVIORS), dtype=bool)   # 지금 관측의 마스크 (다음 스텝용)
            self._reads = np.zeros(self.K * self.N, dtype=bool)                 # 지금 관측에서 요청을 읽는 개체
            self.last_reads = np.zeros(self.K * self.N, dtype=bool)             # 방금 스텝에서 요청을 읽은 개체
            self.rep_counts = dict(agent_steps=0, decide=0, caught=0, starved=0,
                                   beh=np.zeros(N_BEHAVIORS, dtype=np.int64))
            for k in range(self.K):
                self._set_mask(k, self.worlds[k].observe())
            super().__init__(self.K * self.N, obs_space(self.policy_obs_dim), Discrete(N_BEHAVIORS))
            return
        self.policy_obs_dim = self.obs_dim
        super().__init__(self.K * self.N, obs_space(self.obs_dim),
                         act_space(self.act_dim) if self.cm is None else cm_action_space(len(self.cm["categories"])))

    # --- 세계 관리 ----------------------------------------------------- #

    def _staggered_ages(self) -> np.ndarray:
        return np.array([(k * self.T) // self.K for k in range(self.K)], dtype=np.int64)

    def _pick_seed(self, exclude) -> int:
        """동시에 도는 세계와 겹치지 않는 시드. 풀이 세계 수보다 작으면 겹침을 허용한다.
        `train.world_sampling` 이 있으면 균형 추출(모듈 docstring): 후보를 이 규칙으로 여러 개 뽑아 하나를 고른다."""
        if self._ws is None:
            return self._pick_plain(exclude)
        cands = [self._pick_plain(exclude) for _ in range(self._ws["candidates"])]
        n = self._ws_n + 1
        cost = [float(np.sum(((self._ws_sum + self._ws_z[c]) / n) ** 2)) for c in cands]
        best = cands[int(np.argmin(cost))]         # 같으면 먼저 뽑은 후보
        self._ws_sum = self._ws_sum + self._ws_z[best]
        self._ws_n = n
        self.ws_picked.append(best)
        return best

    def _pick_plain(self, exclude) -> int:
        exclude = set(int(e) for e in exclude)
        if len(self.pool) <= len(exclude):
            return int(self._meta.choice(self.pool))
        while True:
            s = int(self._meta.choice(self.pool))
            if s not in exclude:
                return s

    def _renew(self, k: int) -> np.ndarray:
        others = [w.seed for j, w in enumerate(self.worlds) if j != k]
        s = self._pick_seed(exclude=others)
        w = self.worlds[k]
        w.seeds = np.asarray([s], dtype=np.int64)   # World.reset 은 이 풀에서 고른다
        obs = w.reset()
        self._age[k] = 0
        self.seed_history[k].append(int(w.seed))
        return obs

    def current_seeds(self) -> list[int]:
        return [int(w.seed) for w in self.worlds]

    @property
    def world(self) -> World:
        """v1 콜백 호환용 — 첫 세계."""
        return self.worlds[0]

    # --- 핵심 루프 ------------------------------------------------------ #

    def reset(self) -> np.ndarray:
        # SB3 는 learn 시작 때 reset 을 부른다. 막 만든 세계는 그대로 쓴다 — 버리면 기록이 부풀고
        # 학습에 쓰지 않은 세계가 '본 세계'로 잡힌다.
        if not self._fresh:
            for k in range(self.K):
                self._renew(k)
        self._fresh = True
        self._age = self._staggered_ages()
        if self.rep is not None:
            return np.concatenate([self._with_mask(k, w.observe()) for k, w in enumerate(self.worlds)])
        return np.concatenate([w.observe() for w in self.worlds])

    # --- v3 R1 이산 경로 (모듈 docstring) ------------------------------- #

    def _set_mask(self, k: int, obs: np.ndarray) -> None:
        """세계 k 의 지금 관측·미리 보기로 마스크(다음 스텝용)와 '요청을 읽는' 개체를 정한다. 세계를 바꾸지 않는다."""
        from .rep_policy import action_mask

        w, sl = self.worlds[k], slice(k * self.N, (k + 1) * self.N)
        pk = w.rep_peek()
        self._mask[sl] = action_mask(pk, obs, self.rep, obs_names=w.obs_names)
        self._reads[sl] = pk["reads"]

    def _with_mask(self, k: int, obs: np.ndarray) -> np.ndarray:
        """세계 k 의 마스크를 새로 정하고 정책 입력 [관측 | 마스크] 을 낸다."""
        self._set_mask(k, obs)
        return np.concatenate([obs, self._mask[k * self.N:(k + 1) * self.N].astype(np.float32)], axis=1)

    def current_masks(self) -> np.ndarray:
        """지금 관측의 마스크 (num_envs, 5) bool 사본 (다음 스텝에 쓴다)."""
        if self.rep is None:
            raise ValueError("current_masks 는 이산 경로(train.repertoire)에만 있다")
        return self._mask.copy()

    def _rep_actions(self, actions) -> np.ndarray:
        """행동 번호 (num_envs,) → 세계 행동 (num_envs, 1) float. 정수 0..4 이고 지금 마스크 안이어야 한다."""
        a = np.asarray(actions).reshape(-1)
        if a.shape != (self.num_envs,):
            raise ValueError(f"행동은 ({self.num_envs},) 행동 번호다. 받은 모양: {np.asarray(actions).shape}")
        af = a.astype(np.float64)
        if not np.all(np.isfinite(af)) or not np.all(af == np.floor(af)) or af.min() < 0 or af.max() >= N_BEHAVIORS:
            raise ValueError(f"행동은 0..{N_BEHAVIORS - 1} 의 정수 행동 번호다. 받은 범위: [{af.min()}, {af.max()}]")
        ai = af.astype(np.int64)
        bad = ~self._mask[np.arange(self.num_envs), ai]
        if bad.any():
            i = np.flatnonzero(bad)[:5]
            raise ValueError(f"마스크 밖 행동이다(슬롯 {i.tolist()}, 행동 {ai[i].tolist()}). 학습 분포는 막힌 칸이 0 이다")
        return af[:, None]

    def step_async(self, actions: np.ndarray) -> None:
        if self.rep is not None:                    # v3 R1: 행동 번호 → 'behavior' 열 (마스크 검사)
            self._actions = self._rep_actions(actions)
            return
        if self.cm is not None:                     # [조향 4, 범주] → 세계 행동 (env_v2/cm.py cm_to_world)
            self._actions = cm_to_world(actions, self.cm, self.act_names)
            return
        self._actions = sigmoid(np.asarray(actions, dtype=np.float64))   # (-3,3) → [0,1]

    def _step_wait_rep(self):
        """이산 경로의 step_wait (모듈 docstring). 세계·교체 규칙은 연속 경로와 같고 관측 뒤에 마스크를 붙인다."""
        N, D = self.N, self.policy_obs_dim
        obs_all = np.empty((self.num_envs, D), dtype=np.float32)
        rew_all = np.empty(self.num_envs, dtype=np.float64)
        done_all = np.zeros(self.num_envs, dtype=bool)
        infos: list[dict[str, Any]] = [{} for _ in range(self.num_envs)]
        self._fresh = False
        self.last_reads = self._reads.copy()
        cnt = self.rep_counts
        cnt["agent_steps"] += self.num_envs
        cnt["decide"] += int(np.count_nonzero(self.last_reads))

        for k, w in enumerate(self.worlds):
            sl = slice(k * N, (k + 1) * N)
            c0, s0 = w._pred_deaths, w._starve_deaths
            obs, rew, done, term = w.step(self._actions[sl])
            cnt["caught"] += int(w._pred_deaths - c0)
            cnt["starved"] += int(w._starve_deaths - s0)
            cnt["beh"] += np.bincount(w.behavior.astype(np.int64), minlength=N_BEHAVIORS)
            self._age[k] += 1
            base = k * N
            pobs = self._with_mask(k, obs)               # 이 세계 마지막 상태의 마스크(교체 전)
            m_final = self._mask[sl].astype(np.float32)
            for i in np.flatnonzero(done):           # 사망: 끝, 부트스트랩 없음
                infos[base + i]["terminal_observation"] = np.concatenate([term[i], m_final[i]])
            if self._age[k] >= self.T:
                # 시간 초과: 산 슬롯은 truncated 로 끊고 세계를 새로 뽑는다. 사망이 우선한다.
                for i in np.flatnonzero(~done):
                    infos[base + i]["terminal_observation"] = np.concatenate([term[i], m_final[i]])
                    infos[base + i]["TimeLimit.truncated"] = True
                done = np.ones(N, dtype=bool)
                pobs = self._with_mask(k, self._renew(k))
                self.num_resets += 1
            obs_all[sl] = pobs
            rew_all[sl] = rew
            done_all[sl] = done
        return obs_all, rew_all, done_all, infos

    def step_wait(self):
        if self.rep is not None:
            return self._step_wait_rep()
        N = self.N
        obs_all = np.empty((self.num_envs, self.obs_dim), dtype=np.float32)
        rew_all = np.empty(self.num_envs, dtype=np.float64)
        done_all = np.zeros(self.num_envs, dtype=bool)
        infos: list[dict[str, Any]] = [{} for _ in range(self.num_envs)]
        self._fresh = False

        for k, w in enumerate(self.worlds):
            sl = slice(k * N, (k + 1) * N)
            obs, rew, done, term = w.step(self._actions[sl])
            self._age[k] += 1
            base = k * N
            for i in np.flatnonzero(done):           # 사망: 끝, 부트스트랩 없음
                infos[base + i]["terminal_observation"] = term[i]
            if self._age[k] >= self.T:
                # 시간 초과: 산 슬롯은 truncated 로 끊고 세계를 새로 뽑는다. 사망이 우선한다.
                for i in np.flatnonzero(~done):
                    infos[base + i]["terminal_observation"] = term[i]
                    infos[base + i]["TimeLimit.truncated"] = True
                done = np.ones(N, dtype=bool)
                obs = self._renew(k)
                self.num_resets += 1
            obs_all[sl] = obs
            rew_all[sl] = rew
            done_all[sl] = done
        return obs_all, rew_all, done_all, infos

    def close(self) -> None:
        pass

    # --- SB3 가 요구하는 최소 구현 ---------------------------------------- #

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
        # 세계 시드는 meta_seed 로 정한다. SB3 가 여기를 건드리면 안 된다.
        return [None] * self.num_envs

    def get_images(self):
        raise NotImplementedError("렌더는 replay_v2.py 를 쓴다")
