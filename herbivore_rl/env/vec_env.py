"""§6.2 SB3 연결 — 자체 VecEnv.

`supersuit`은 쓰지 않는다. PettingZoo 환경을 SB3 VecEnv로 바꿔 주는 어댑터인데,
§11-A 판단으로 자체 World를 쓰면서 변환할 PettingZoo 환경이 없어졌다. §6.2가 열어 둔
"N 고정·리스폰 규약과 안 맞으면 자체 래퍼" 경로를 그대로 따른다 — `World`는 N=128
슬롯 고정 리스폰(§4.3)이라 PettingZoo의 에이전트 등장/퇴장 규약과 애초에 맞지 않는다.

**슬롯 하나 = SB3 환경 하나.** `num_envs = N = 128`. 즉 SB3의 1 timestep은 개체 1마리의
1스텝이고, World 1스텝은 SB3 128 timestep이다.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from gymnasium.spaces import Box
from stable_baselines3.common.vec_env.base_vec_env import VecEnv

from .config import Config
from .world import ACT_DIM, OBS_DIM, World

OBS_SPACE = Box(0.0, 1.0, (OBS_DIM,), np.float32)      # §3.1
ACT_SPACE = Box(-3.0, 3.0, (ACT_DIM,), np.float32)     # §3.2 — SB3가 보는 공간


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


class HerdVecEnv(VecEnv):
    """§1.3 — `World.step()` 은 항상 [0,1] 행동을 받는다.

    정책의 (-3,3) 출력을 [0,1]로 바꾸는 sigmoid는 **여기에만** 있다. Utility AI와 평가
    코드는 sigmoid 없이 그대로 쓴다. 이 경계가 흐려지면 §0의 동일 조건 비교가 깨진다.
    """

    metadata = {"render_modes": []}

    def __init__(self, cfg: Config, seeds=None, meta_seed: int = 0):
        self.world = World(cfg, seeds=seeds, meta_seed=meta_seed)
        self.cfg = cfg
        self._actions: np.ndarray | None = None
        self.render_mode = None          # super().__init__ 이 읽으므로 그 전에
        super().__init__(self.world.N, OBS_SPACE, ACT_SPACE)

    # --- 핵심 루프 ---------------------------------------------------- #

    def reset(self) -> np.ndarray:
        return self.world.reset()

    def step_async(self, actions: np.ndarray) -> None:
        self._actions = sigmoid(np.asarray(actions, dtype=np.float64))   # (-3,3) → [0,1]

    def step_wait(self):
        obs, rew, done, term = self.world.step(self._actions)
        infos: list[dict[str, Any]] = [{} for _ in range(self.num_envs)]
        for i in np.flatnonzero(done):
            infos[i]["terminal_observation"] = term[i]
        return obs, rew, done, infos

    def close(self) -> None:
        pass

    # --- SB3가 요구하는 최소 구현 --------------------------------------- #
    # 슬롯은 독립 환경이 아니라 한 World의 일부다. "환경 i의 속성" 이라는 개념이 없으므로
    # 이 래퍼 자신의 속성을 indices 개수만큼 복제해서 돌려준다.
    # §6.5가 쓰는 `training_env.get_attr("world")[0]` 이 World를 돌려주려면 이래야 한다.

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
        # 시드는 World가 자기 풀(§3.5)에서 고른다. SB3가 여기를 건드리면 안 된다.
        return [None] * self.num_envs

    def get_images(self):
        raise NotImplementedError("렌더는 replay.py 를 쓴다")


def make_vec_env(cfg: Config, seeds=None, meta_seed: int = 0) -> HerdVecEnv:
    return HerdVecEnv(cfg, seeds=seeds, meta_seed=meta_seed)
