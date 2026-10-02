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
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from gymnasium.spaces import Box
from stable_baselines3.common.vec_env.base_vec_env import VecEnv

from .world import ACT_DIM, OBS_DIM, World

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


class MultiWorldVecEnv(VecEnv):
    metadata = {"render_modes": []}

    def __init__(self, cfg, num_worlds: int | None = None, reset_interval: int | None = None,
                 seeds=None, meta_seed: int = 0):
        train = (getattr(cfg, "v2", None) or {}).get("train", {})
        self.cfg = cfg
        self.K = int(num_worlds if num_worlds is not None else train.get("num_worlds", 8))
        self.T = int(reset_interval if reset_interval is not None else train.get("reset_interval", 4000))
        if self.K < 1 or self.T < 1:
            raise ValueError(f"num_worlds={self.K}, reset_interval={self.T} 는 1 이상이어야 한다")
        if seeds is None:
            lo, hi = cfg.train_seeds
            seeds = range(lo, hi)
        self.pool = np.asarray(list(seeds), dtype=np.int64)
        self._meta = np.random.default_rng(meta_seed)

        self.worlds: list[World] = []
        for _ in range(self.K):
            s = self._pick_seed(exclude=[w.seed for w in self.worlds])
            self.worlds.append(World(cfg, seeds=[s]))
        self.N = self.worlds[0].N
        self.act_dim = self.worlds[0].act_dim
        self.act_names = self.worlds[0].act_names
        self.obs_dim = self.worlds[0].obs_dim
        self.obs_names = self.worlds[0].obs_names
        self._age = self._staggered_ages()
        self._fresh = True          # 한 스텝도 안 돈 세계는 reset() 이 다시 뽑지 않는다
        self.num_resets = 0         # 시간 초과로 세계를 새로 뽑은 횟수
        self.seed_history: list[list[int]] = [[w.seed] for w in self.worlds]
        self._actions: np.ndarray | None = None
        self.render_mode = None
        super().__init__(self.K * self.N, obs_space(self.obs_dim), act_space(self.act_dim))

    # --- 세계 관리 ----------------------------------------------------- #

    def _staggered_ages(self) -> np.ndarray:
        return np.array([(k * self.T) // self.K for k in range(self.K)], dtype=np.int64)

    def _pick_seed(self, exclude) -> int:
        """동시에 도는 세계와 겹치지 않는 시드. 풀이 세계 수보다 작으면 겹침을 허용한다."""
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
        return np.concatenate([w.observe() for w in self.worlds])

    def step_async(self, actions: np.ndarray) -> None:
        self._actions = sigmoid(np.asarray(actions, dtype=np.float64))   # (-3,3) → [0,1]

    def step_wait(self):
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
