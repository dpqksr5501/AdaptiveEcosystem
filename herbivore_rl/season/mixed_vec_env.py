"""혼합 학습 세계 — G 세계 묶음과 B 세계 묶음을 이어 붙인다 (SEASON 4.1 분포, 5.2 리허설).

기존 `env_v2.vec_env.MultiWorldVecEnv` 는 설정 하나로 모든 세계를 만든다. 그래서 설정마다 K=4 묶음을 하나씩 만들고
슬롯을 차례로 이어 붙인다(10-02 스크래치 `season_probe/train_mixed.py` 의 Mixed 를 옮겼다).

- 슬롯 순서: 묶음 0 의 세계 0..3 (각 N 슬롯), 그다음 묶음 1 의 세계 0..3. num_envs = 8 × N.
- 세계 고르기: 묶음 0 은 meta_seed = seed, 묶음 1 은 meta_seed = seed + B_META_OFFSET(7919, 스크래치와 같다).
  묶음마다 엇갈림은 reset_interval / 4 = 1000 스텝이다. 묶음끼리는 시드 겹침을 검사하지 않는다(설정이 다르다).
- 후보(`build_mixed`)는 묶음 0 = G, 묶음 1 = B 다. K2-B(`build_k2b`)는 두 묶음이 모두 B 다. K2-B 의 묶음 1 은 같은 시드
  후보의 B 묶음과 세계 순서까지 같다. 구조(세계 수, 엇갈림, 리허설 슬롯)가 후보와 같아서 방식 M3 의 KL 항도 같은 자리에
  걸린다.
- 리허설 슬롯(`rehearsal_slice`)은 마지막 묶음의 슬롯이다. M3 의 앵커 KL 은 이 슬롯의 상태에서만 잰다(SEASON 5.4
  "리허설 절반의 상태").

SB3 와 `train_v2.BehaviorLogCallbackV2` 가 읽는 속성(act_names, obs_names, obs_dim, act_dim, cm, worlds, num_resets,
seed_history)을 같은 이름으로 둔다. 범주형 보행 CM 설정은 받지 않는다(SR1 앵커는 행동 4개 가우시안이다).
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from stable_baselines3.common.vec_env.base_vec_env import VecEnv

from env_v2.vec_env import MultiWorldVecEnv, act_space, obs_space

B_META_OFFSET = 7919
WORLDS_PER_PART = 4


class MixedVecEnv(VecEnv):
    metadata = {"render_modes": []}

    def __init__(self, parts: Sequence[MultiWorldVecEnv], labels: Sequence[str]):
        parts, labels = list(parts), [str(x) for x in labels]
        if not parts or len(parts) != len(labels):
            raise ValueError(f"묶음 {len(parts)}개, 이름 {len(labels)}개 — 하나 이상이고 수가 같아야 한다")
        p0 = parts[0]
        for p in parts:
            if p.cm is not None:
                raise ValueError("혼합 세계는 범주형 보행 CM 설정을 받지 않는다")
            same = (p.N, p.obs_dim, p.act_dim, tuple(p.act_names), tuple(p.obs_names)) == \
                   (p0.N, p0.obs_dim, p0.act_dim, tuple(p0.act_names), tuple(p0.obs_names))
            if not same:
                raise ValueError("묶음끼리 슬롯 수·관측·행동이 같아야 한다 "
                                 f"({p.N}, {list(p.obs_names)}, {list(p.act_names)}) vs "
                                 f"({p0.N}, {list(p0.obs_names)}, {list(p0.act_names)})")
        self.parts = parts
        self.labels = labels
        self.N = p0.N
        self.obs_dim, self.act_dim = p0.obs_dim, p0.act_dim
        self.obs_names, self.act_names = p0.obs_names, p0.act_names
        self.cm = None
        starts = np.cumsum([0] + [p.num_envs for p in parts])
        self._slices = [slice(int(a), int(b)) for a, b in zip(starts[:-1], starts[1:])]
        self.render_mode = None
        super().__init__(int(starts[-1]), obs_space(self.obs_dim), act_space(self.act_dim))

    # --- 묶음 정보 --------------------------------------------------------- #

    def part_slice(self, i: int) -> slice:
        """묶음 i 의 슬롯 범위."""
        return self._slices[i]

    @property
    def rehearsal_slice(self) -> slice:
        """리허설(B) 슬롯 = 마지막 묶음의 슬롯."""
        return self._slices[-1]

    @property
    def worlds(self) -> list:
        return [w for p in self.parts for w in p.worlds]

    @property
    def K(self) -> int:
        return sum(p.K for p in self.parts)

    @property
    def T(self) -> int:
        return self.parts[0].T

    @property
    def world_labels(self) -> list[str]:
        """세계마다 묶음 이름 (슬롯 순서와 같은 순서)."""
        return [lab for p, lab in zip(self.parts, self.labels) for _ in range(p.K)]

    @property
    def num_resets(self) -> int:
        return sum(p.num_resets for p in self.parts)

    @property
    def seed_history(self) -> list[list[int]]:
        return [h for p in self.parts for h in p.seed_history]

    def worlds_seen(self) -> dict:
        """본 세계 수 (SEASON 5.4 부수 확인). 묶음별·전체. 처음 세계도 센다."""
        per = {f"{i}{lab}": sum(len(h) for h in p.seed_history)
               for i, (p, lab) in enumerate(zip(self.parts, self.labels))}
        return {"per_part": per, "total": sum(per.values()), "resets": self.num_resets}

    def current_seeds(self) -> list[int]:
        return [s for p in self.parts for s in p.current_seeds()]

    @property
    def world(self):
        """v1 콜백 호환용 — 첫 세계."""
        return self.parts[0].worlds[0]

    # --- 핵심 루프 ------------------------------------------------------ #

    def reset(self) -> np.ndarray:
        return np.concatenate([p.reset() for p in self.parts])

    def step_async(self, actions: np.ndarray) -> None:
        actions = np.asarray(actions)
        for p, sl in zip(self.parts, self._slices):
            p.step_async(actions[sl])

    def step_wait(self):
        obs, rew, done, infos = [], [], [], []
        for p in self.parts:
            o, r, d, i = p.step_wait()
            obs.append(o)
            rew.append(r)
            done.append(d)
            infos.extend(i)
        return np.concatenate(obs), np.concatenate(rew), np.concatenate(done), infos

    def close(self) -> None:
        for p in self.parts:
            p.close()

    # --- SB3 가 요구하는 최소 구현 (MultiWorldVecEnv 와 같은 규칙) ------------- #

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
        # 세계 시드는 묶음의 meta_seed 로 정한다. SB3 가 여기를 건드리면 안 된다.
        return [None] * self.num_envs

    def get_images(self):
        raise NotImplementedError("렌더는 replay_v2.py 를 쓴다")


def build_mixed(g_cfg, b_cfg, seed: int, worlds_per_part: int = WORLDS_PER_PART,
                reset_interval: int | None = None) -> MixedVecEnv:
    """후보 학습 세계: 묶음 0 = G (meta_seed = seed), 묶음 1 = B (meta_seed = seed + 7919)."""
    g = MultiWorldVecEnv(g_cfg, num_worlds=worlds_per_part, reset_interval=reset_interval, meta_seed=seed)
    b = MultiWorldVecEnv(b_cfg, num_worlds=worlds_per_part, reset_interval=reset_interval,
                         meta_seed=seed + B_META_OFFSET)
    return MixedVecEnv([g, b], ["G", "B"])


def build_k2b(b_cfg, seed: int, worlds_per_part: int = WORLDS_PER_PART,
              reset_interval: int | None = None) -> MixedVecEnv:
    """K2-B 학습 세계: 두 묶음 모두 B. 묶음 1 은 같은 시드 후보의 B 묶음과 같다."""
    b0 = MultiWorldVecEnv(b_cfg, num_worlds=worlds_per_part, reset_interval=reset_interval, meta_seed=seed)
    b1 = MultiWorldVecEnv(b_cfg, num_worlds=worlds_per_part, reset_interval=reset_interval,
                          meta_seed=seed + B_META_OFFSET)
    return MixedVecEnv([b0, b1], ["B", "B"])
