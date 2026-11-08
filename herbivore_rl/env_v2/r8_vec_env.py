"""R8 학습용 VecEnv — R8 세계 K 개(각 사슴 N)를 SB3 환경 K × N 개로 (설계 RL_R8_LEARN_DANGER_DESIGN.md 7절).

`vec_env.MultiWorldVecEnv` 의 규칙을 그대로 옮겼다.
  - 세계마다 `reset_steps`(스텝) = reset_steps / decision_steps 결정이 지나면 새 시드로 바꾼다. 세계 k 는 처음에 k·T/K 결정을 산 것으로
    두어 교체가 T/K 간격으로 엇갈린다. 새 시드는 메타 난수(meta_seed)로 풀에서 고르고, 동시에 도는 세계와 겹치지 않는다.
  - 교체로 끊긴 칸은 done=True + `terminal_observation` + `TimeLimit.truncated=True`(SB3 가 γ·V(끝 관측)을 더한다). 같은 결정에 죽은 칸은
    사망이 우선한다 — truncated 를 싣지 않는다.
  - 사망 칸의 `terminal_observation` 은 다시 난 뒤 관측이다(SB3 는 사망에 쓰지 않는다).
세계 K 개는 R8World 하나의 배열 묶음이다(세계마다 난수 갈래가 따로라 묶음과 무관하게 같은 시드 = 같은 세계).
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from gymnasium.spaces import Box, Discrete
from stable_baselines3.common.vec_env.base_vec_env import VecEnv

from .r8_world import N_ACTIONS, OBS_DIM, R8World

OBS_SPACE = Box(-1.0, 1.0, (OBS_DIM,), np.float32)
ACT_SPACE = Discrete(N_ACTIONS)


class R8VecEnv(VecEnv):
    metadata = {"render_modes": []}

    def __init__(self, cfg: dict, num_worlds: int | None = None, reset_steps: int | None = None, seeds=None, meta_seed: int = 0):
        tr = cfg["train"]
        self.cfg = cfg
        self.K = int(num_worlds if num_worlds is not None else tr["num_worlds"])
        steps = int(reset_steps if reset_steps is not None else tr["reset_steps"])
        D = int(cfg["world"]["decision_steps"])
        self.T = max(1, steps // D)                    # 교체 주기 (결정)
        if seeds is None:
            lo, hi = tr["seeds"]
            seeds = range(int(lo), int(hi))
        self.pool = np.asarray(list(seeds), dtype=np.int64)
        self._meta = np.random.default_rng(meta_seed)
        first: list[int] = []
        for _ in range(self.K):
            first.append(self._pick(first))
        self.world = R8World(cfg, first)
        self.N = self.world.N
        self.seed_history: list[list[int]] = [[s] for s in first]
        self.num_resets = 0
        self._fresh = True
        self._age = self._staggered()
        self._actions = None
        self.render_mode = None
        super().__init__(self.K * self.N, OBS_SPACE, ACT_SPACE)

    def _staggered(self) -> np.ndarray:
        return np.array([(k * self.T) // self.K for k in range(self.K)], dtype=np.int64)

    def _pick(self, exclude) -> int:
        ex = set(int(e) for e in exclude)
        if len(self.pool) <= len(ex):
            return int(self._meta.choice(self.pool))
        while True:
            s = int(self._meta.choice(self.pool))
            if s not in ex:
                return s

    def _renew(self, k: int) -> None:
        others = [int(s) for j, s in enumerate(self.world.seeds) if j != k]
        s = self._pick(others)
        self.world.reinit(k, s)
        self._age[k] = 0
        self.seed_history[k].append(s)
        self.num_resets += 1

    def current_seeds(self) -> list[int]:
        return [int(s) for s in self.world.seeds]

    def reset(self) -> np.ndarray:
        # SB3 는 learn 시작 때 reset 을 부른다. 막 만든 세계는 그대로 쓴다(MultiWorldVecEnv 와 같다)
        if not self._fresh:
            for k in range(self.K):
                self._renew(k)
        self._fresh = True
        self._age = self._staggered()
        return self.world.observe().reshape(-1, OBS_DIM).copy()

    def step_async(self, actions: np.ndarray) -> None:
        self._actions = np.asarray(actions).reshape(self.K, self.N)

    def step_wait(self):
        self._fresh = False
        obs, rew, done, _ = self.world.step(self._actions)
        obs = obs.copy()
        done = done.copy()
        infos: list[dict[str, Any]] = [{} for _ in range(self.num_envs)]
        N = self.N
        for k, i in zip(*np.nonzero(done)):              # 사망: 끝, 부트스트랩 없음
            infos[k * N + i]["terminal_observation"] = obs[k, i]
        self._age += 1
        ren = np.nonzero(self._age >= self.T)[0]
        if len(ren):
            for k in ren:
                for i in np.nonzero(~done[k])[0]:
                    infos[k * N + i]["terminal_observation"] = obs[k, i].copy()
                    infos[k * N + i]["TimeLimit.truncated"] = True
                done[k] = True
                self._renew(int(k))
            obs = self.world.observe().copy()
        return obs.reshape(-1, OBS_DIM), rew.reshape(-1).astype(np.float64), done.reshape(-1), infos

    def close(self) -> None:
        pass

    # --- SB3 가 요구하는 최소 구현 ---
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
        return [None] * self.num_envs

    def get_images(self):
        raise NotImplementedError("렌더는 results/v3/r8/r8_replay.py 를 쓴다")
