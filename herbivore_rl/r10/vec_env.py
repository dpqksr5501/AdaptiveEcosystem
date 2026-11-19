"""R10 학습 칸 — 한 종(학습하는 종)의 개체들을 SB3 VecEnv 로 (R9 R9VecEnv 꼴, 0 단계 사양 2 절).

- 세계 K 개, 세계마다 무작위 맵(학습 시드 범위)과 무작위 종 목록. 학습하는 종은 늘 있고 세계마다 learner_cap 칸.
- 다른 종은 고정 두뇌(numpy 가중치)나 공통 규칙 두뇌로 움직인다. 이름 모를 동물도 가끔 넣는다(규칙 두뇌).
- renew_decisions 마다 모든 세계를 새 맵·새 종 목록으로 바꾼다(그때 학습 칸 모두 끝). 학습 칸은 죽으면 다음 결정에 되살아난다.
- curriculum(밀도 단계): 처음엔 작은 맵에 학습 종이 물 수 있는 몸(몸무게 비·같은 매체, 종 이름 아님)을 많이 두고,
  curriculum["decisions"] 결정에 걸쳐 맵 크기·먹잇감 수를 보통 범위(mapgen RANGES·1~other_cap)로 넓힌다. 세계 규칙·계약은 그대로.
"""

from __future__ import annotations

import numpy as np

from r10 import contract as C
from r10 import mapgen as G
from r10 import policy as P
from r10 import rule_brain as RB
from r10 import senses as O
from r10 import species as S
from r10 import world as W

try:
    import gymnasium as gym
    from stable_baselines3.common.vec_env import VecEnv
except ImportError:  # 시험 없이 세계만 쓸 때
    gym = None
    VecEnv = object


class R10VecEnv(VecEnv):
    def __init__(self, learner: str, cards: dict, n_worlds: int = 8, learner_cap: int = 8, other_cap: int = 6,
                 present_p: float = 0.75, unknown_max: int = 2, brains: dict | None = None, seed: int = 0,
                 renew_decisions: int = 2500, map_purpose: str = "train", map_seed0: int | None = None,
                 map_overrides: dict | None = None, rules: W.Rules | None = None, curriculum: dict | None = None):
        if learner not in cards:
            raise ValueError(f"learner {learner!r} not in cards {sorted(cards)}")
        self.learner = learner
        self.cards = cards
        self.K = int(n_worlds)
        self.learner_cap = int(learner_cap)
        self.other_cap = int(other_cap)
        self.present_p = float(present_p)
        self.unknown_max = int(unknown_max)
        self.brains = dict(brains or {})               # 종 id → numpy 가중치 (없으면 규칙 두뇌)
        self.rng = np.random.default_rng([int(seed), 0x5210_0002])
        self.seed_ = int(seed)
        self.renew_decisions = int(renew_decisions)
        self.map_purpose = map_purpose
        lo, hi = G.SEED_RANGES[map_purpose]
        self.map_seed0 = int(map_seed0 if map_seed0 is not None else lo + (int(seed) * 997) % (hi - lo))
        self.map_overrides = map_overrides
        self.rules = rules or W.Rules()
        self.curriculum = dict(curriculum) if curriculum else None
        self.prey = self._prey_ids()
        self.prey_cap = max(self.other_cap, int(self.curriculum["prey0"][1])) if self.curriculum else self.other_cap
        self.slots = (self.learner_cap + self.other_cap * (len(cards) - 1 - len(self.prey)) + self.prey_cap * len(self.prey)
                      + 2 * self.unknown_max)
        self.n_renew = 0
        self.decisions = 0
        self._build()
        n_envs = self.K * self.learner_cap
        if gym is not None:
            obs_space = gym.spaces.Box(-1.0, 1.0, (C.OBS_DIM,), np.float32)
            act_space = gym.spaces.Discrete(C.N_ACTIONS)
            super().__init__(n_envs, obs_space, act_space)
        else:
            self.num_envs = n_envs
        self._actions = np.zeros(n_envs, np.int64)
        self.ep_ret = np.zeros(n_envs)
        self.ep_len = np.zeros(n_envs, np.int64)

    # ------------------------------------------------------------------ 세계 만들기

    def _prey_ids(self) -> set:
        """학습 종이 물 수 있는 종: 고기를 먹고, 상대 몸무게 ≤ 내 몸무게 × kill_mass_ratio, 같은 매체 (세계 물기 규칙의 몸 조건)."""
        me = self.cards[self.learner]
        kr = (me.get("combat", {}).get("kill_mass_ratio") or 0.0)
        if kr <= 0 or (me.get("diet", {}).get("meat") or 0) <= 0:
            return set()
        lim = me["body"]["mass_kg"] * kr
        return {sid for sid, c in self.cards.items()
                if sid != self.learner and c["body"]["mass_kg"] <= lim
                and any(me["medium"].get(k) and c["medium"].get(k) for k in ("ground", "swim", "fly"))}

    def progress(self) -> float:
        """밀도 단계 진행 0 → 1 (학습 칸 결정 수 기준)."""
        if not self.curriculum:
            return 1.0
        return float(min(1.0, self.decisions * self.K * self.learner_cap / max(1, int(self.curriculum["decisions"]))))

    def _lerp(self, a, b):
        t = self.progress()
        return a + (b - a) * t

    def _roster(self):
        ents = [(self.cards[self.learner], self.learner_cap, self.learner_cap)]
        ids = [self.learner]
        cur = self.curriculum
        for sid, card in self.cards.items():
            if sid == self.learner:
                continue
            if sid in self.prey and cur:
                lo = int(round(self._lerp(cur["prey0"][0], 1)))
                hi = int(round(self._lerp(cur["prey0"][1], self.other_cap)))
                if self.rng.random() > self._lerp(1.0, self.present_p):
                    continue
                ents.append((card, int(self.rng.integers(lo, max(lo, hi) + 1)), self.prey_cap))
                ids.append(sid)
                continue
            if self.rng.random() > self.present_p:
                continue
            ents.append((card, int(self.rng.integers(1, self.other_cap + 1)), self.prey_cap if sid in self.prey else self.other_cap))
            ids.append(sid)
        for u in range(int(self.rng.integers(0, self.unknown_max + 1))):
            uc = S.random_card(self.rng, u)
            ents.append((uc, 1, 2))
            ids.append(uc["id"])
        return W.Roster(ents), ids

    def _build(self):
        maps, rosters, self.ids = [], [], []
        for k in range(self.K):
            seed = self.map_seed0 + self.n_renew * self.K + k
            lo, hi = G.SEED_RANGES[self.map_purpose]
            seed = lo + (seed - lo) % (hi - lo)
            ov = dict(self.map_overrides or {})
            if self.curriculum:
                lo = int(round(self._lerp(self.curriculum["size0"][0], G.RANGES["size_m"][0])))
                hi = int(round(self._lerp(self.curriculum["size0"][1], G.RANGES["size_m"][1])))
                ov.setdefault("w", int(self.rng.integers(lo, hi + 1)))
                ov.setdefault("h", int(self.rng.integers(lo, hi + 1)))
            maps.append(G.make_map(seed, self.map_purpose, ov or None))
            r, ids = self._roster()
            rosters.append(r)
            self.ids.append(ids)
        self.world = W.World(maps, rosters, slots=self.slots, seed=self.seed_ * 100003 + self.n_renew, rules=self.rules,
                             train=True, jitter=True)
        w = self.world
        self.learner_slots = np.concatenate([np.arange(k * w.S, k * w.S + self.learner_cap) for k in range(self.K)])
        w.respawn_wait[self.learner_slots] = 1
        # 학습 칸은 늘 살아 있게 시작 (자리를 못 찾으면 그 칸은 비어 있다)
        for i in self.learner_slots:
            if not w.alive[i]:
                w._spawn(i)
        self.obs_all = O.observe(w)
        self.since_renew = 0

    # ------------------------------------------------------------------ 상대 행동

    def _others_actions(self, obs_all):
        w = self.world
        a = np.full(w.N, C.A_WATCH, np.int64)
        alive = w.alive.copy()
        alive[self.learner_slots] = False
        if not alive.any():
            return a
        by_id = {}
        for i in np.nonzero(alive)[0]:
            sid = self.ids[w.wk[i]][w.sp[i]]
            by_id.setdefault(sid, []).append(i)
        for sid, idx in by_id.items():
            idx = np.array(idx)
            wts = self.brains.get(sid)
            a[idx] = P.act_np(wts, obs_all[idx]) if wts is not None else RB.decide(obs_all[idx])
        return a

    # ------------------------------------------------------------------ VecEnv

    def reset(self):
        self.ep_ret[:] = 0
        self.ep_len[:] = 0
        return self.obs_all[self.learner_slots].copy()

    def step_async(self, actions):
        self._actions = np.asarray(actions, dtype=np.int64)

    def step_wait(self):
        w = self.world
        a = self._others_actions(self.obs_all)
        a[self.learner_slots] = self._actions
        alive_before = w.alive[self.learner_slots].copy()
        w.step(a)
        self.obs_all = O.observe(w)
        rew = np.where(alive_before, w.reward[self.learner_slots], 0.0).astype(np.float32)
        done = w.done[self.learner_slots].copy()
        self.decisions += 1
        self.since_renew += 1
        infos = [{} for _ in range(self.num_envs)]
        self.ep_ret += rew
        self.ep_len += 1
        obs = self.obs_all[self.learner_slots].copy()
        if self.since_renew >= self.renew_decisions:
            for e in range(self.num_envs):
                if not done[e]:
                    infos[e]["TimeLimit.truncated"] = True
                infos[e]["terminal_observation"] = obs[e].copy()
            done[:] = True
            self.n_renew += 1
            self._build()
            obs = self.obs_all[self.learner_slots].copy()
        else:
            for e in np.nonzero(done)[0]:
                infos[e]["terminal_observation"] = obs[e].copy()
        for e in np.nonzero(done)[0]:
            infos[e]["episode"] = {"r": float(self.ep_ret[e]), "l": int(self.ep_len[e])}
            self.ep_ret[e] = 0
            self.ep_len[e] = 0
        return obs, rew, done, infos

    def close(self):
        pass

    def get_attr(self, attr_name, indices=None):
        return [getattr(self, attr_name)] * (self.num_envs if indices is None else len(list(indices)))

    def set_attr(self, attr_name, value, indices=None):
        setattr(self, attr_name, value)

    def env_method(self, method_name, *method_args, indices=None, **method_kwargs):
        return [None] * self.num_envs

    def env_is_wrapped(self, wrapper_class, indices=None):
        return [False] * self.num_envs

    def seed(self, seed=None):
        return [None] * self.num_envs
