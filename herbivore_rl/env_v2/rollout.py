"""V2 롤아웃 — 정책을 env_v2 World 에 돌리고 진단용 기록을 모은다 (계획서 0-3, 6.1).

v1 `env/rollout.py` 와 같은 규약이다: 시드 하나 = 세계 하나. 시드마다 `World(cfg, seeds=[s])` 를
새로 만들고 reset() 으로 돌려쓰지 않는다. 그래서 같은 정책·같은 시드면 v1 평가와 숫자가 같다.

v1 에 없는 것:
- **정책 래퍼 훅.** 스펙에 `wrap` 목록을 주면 행동이나 관측을 바꿔 끼운다(고정·순열·구간별 상수).
  대조군 C1′·C3·C4·C2-seg 가 이것으로 만들어진다. 밖에서 만든 래퍼는 `{"factory": "모듈:함수"}`
  로 끼운다. Windows spawn 은 클로저를 피클하지 못하므로 래퍼도 dict 로만 넘긴다.
- **G_γ.** 스텝별 보상과 사망을 기록해 할인 리턴-투-고 평균을 낸다 (`g_gamma`).
- **관측·행동 표본.** `record_every` 스텝마다 실제 관측과 실제로 적용된 행동을 남긴다.
- **확률 모드** (계획서 6.1-7, #29). 학습 정책 스펙에 `"mode": "stochastic"` 을 넣으면 평균 행동 대신
  학습 때의 가우시안 분포에서 뽑은 행동을 쓴다 (`StochasticLearned`). 잡음은 평가 시드에서 유도한 전용
  스트림에서 뽑아 재현된다. `mode` 가 없거나 "deterministic" 이면 지금까지와 같은 결정 모드다.
- **유지 표본 모드** (수정 제안서 3.1 (가) R1 출시 모드, 5절 #3). `"mode": "hold", "hold_k": K` 면 조향 4열은 결정 모드
  평균 그대로, 보행·경계 열(4~)만 개체별 잡음 u 를 K 스텝 유지해 뽑는다 (`HoldLearned`). u 는 해시·위상 표본기라
  상태를 저장하지 않고 C++ 로 그대로 옮길 수 있다. 리스폰은 `observe_done` 훅으로 정책에 알린다(아래 롤아웃).
- **리스폰 훅.** 정책(래퍼 포함)에 `observe_done(done)` 이 있으면 `rollout` 이 `w.step` 뒤마다 그 스텝의 사망(=리스폰)
  배열로 부른다. 결정·확률 모드 정책에는 없어 지금까지와 같은 값이 나온다.
- **세계 연결 훅.** 정책(래퍼 포함)에 `bind_world(w)` 가 있으면 `rollout` 이 World 를 만든 직후 한 번 부른다(`forward_bind`).
  래퍼는 `observe_done` 처럼 바탕 정책으로 넘긴다. v3 R1 학습 정책(`rep_learned`)이 이 훅으로 세계를 받아 마스크(결정 미리
  보기 `World.rep_peek` + 지금 관측의 가능 조건)를 만든다. 훅이 없는 정책은 지금까지와 같다.
- **v3 R1 학습 정책** (`{"kind": "rep_learned", "path": "ckpt/v3/....zip"}`, 명세 RL_V3_R1_SPEC.md 2·3절): RepertoirePolicy
  모델(env_v2/rep_policy.py)을 싣고 매 스텝 마스크 로짓의 argmax(동점이면 낮은 번호)로 행동 번호를 낸다. 마스크는 연결한
  세계의 참 상태(지금 관측·미리 보기)로 만들고, 망에는 받은 관측을 넣는다 — C4 의 `obs_fix` 래퍼는 망 입력만 바꾼다.
  모델의 허용 행동(`rep_allowed`)·관측 이름(`rep_obs_names`)이 세계와 맞는지 연결 때 본다.
- **앞부분 제외.** `head` 를 주면 G_γ 평균에서 롤아웃 앞 `head` 스텝(리셋 과도기)도 뺀다 (6.1-4, 기본 0).
- **행동·관측 수는 세계를 따른다** (`World.act_dim`: v1 4, speed 를 켜면 5, vigilance 까지 켜면 6.
  `World.obs_dim`: v1 7, vigilance 를 켜면 8, v2.1 + daynight 9). 래퍼·확률 모드는 차원과 무관하다.
  v1 의 4개짜리 정책(Utility)은 speed·vigilance 세계에 쓸 수 없다(World.step 이 모양을 검사한다). random 은 스펙의
  `act_dim` 으로 차원을 정한다(`adapt_spec`). speed 를 켠 세계의 행에는 `World.gait_stats()` 열이,
  vigilance 를 켠 세계의 행에는 `World.vigil_stats()` 열이 붙는다.
  vigil_window(v2.2r)를 켠 세계의 행에는 `World.window_stats()` 열(WINDOW_COLUMNS)도, daynight(v2.4)를 켠 세계의 행에는
  `World.daynight_stats()` 열(DAYNIGHT_COLUMNS)도 붙는다. repertoire(v3)·threats(v3)를 켠 세계의 행에는 `World.repertoire_stats()`
  열(REPERTOIRE_COLUMNS)·`World.threats_stats()` 열(THREAT_COLUMNS)이 붙는다(repertoire 세계는 행동이 'behavior' 한 열이다).
  범주형 보행 CM 모델 (`env_v2/cm.py`)은 `_base_policy` 가 알아보고 CM 평가 정책(결정·유지 표본·확률)으로 돌린다.

정책 스펙 예:
    {"kind": "learned", "model": "ckpt/final.zip"}                 # policies.registry 스펙 그대로
    {"kind": "learned", "model": "ckpt/final.zip", "mode": "stochastic"}   # 확률 모드
    {"kind": "learned", "model": "ckpt/final.zip", "mode": "hold", "hold_k": 24}   # 유지 표본 모드 (R1)
    {"policy": {"kind": "learned", "model": "..."},
     "wrap": [{"kind": "act_fix", "dims": [1], "values": [.3, .8, .4, .1]}]}
"""

from __future__ import annotations

import importlib
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from env.config import ROOT, Config
from env.rollout import STAT_COLUMNS, _init_worker

from .world import (ACT_DIM, DAYNIGHT_STAT_COLUMNS, GAIT_STAT_COLUMNS, PSLEEP_STAT_COLUMNS, REP_STAT_COLUMNS,
                    THREAT_STAT_COLUMNS, VIGIL_STAT_COLUMNS, WINDOW_STAT_COLUMNS, World)

# 학습 γ 의 출처. 모델마다 γ 가 다르면 --gamma 로 덮는다.
PPO_CONFIG = ROOT / "configs" / "ppo_best.yaml"
DEFAULT_GAMMA = 0.9916661555611042

# World.stats() 10열 뒤에 붙는 열. 시드마다 하나의 값이다.
EXTRA_COLUMNS = ["g_gamma", "starve_rate", "starve_share"]
ROW_COLUMNS = STAT_COLUMNS + EXTRA_COLUMNS
# speed(v2.1)를 켠 세계의 행에만 더 붙는 열 (World.gait_stats, starve_* 는 위와 같은 값이라 빼고 붙인다)
GAIT_COLUMNS = [c for c in GAIT_STAT_COLUMNS if c not in EXTRA_COLUMNS]
# vigilance(v2.2)를 켠 세계의 행에만 더 붙는 열 (World.vigil_stats)
VIGIL_COLUMNS = list(VIGIL_STAT_COLUMNS)
# vigil_window(v2.2r)를 켠 세계의 행에만 더 붙는 열 (World.window_stats)
WINDOW_COLUMNS = list(WINDOW_STAT_COLUMNS)
# daynight(v2.4)를 켠 세계의 행에만 더 붙는 열 (World.daynight_stats)
DAYNIGHT_COLUMNS = list(DAYNIGHT_STAT_COLUMNS)
# pred_sleep(v2.4s)를 켠 세계의 행에만 더 붙는 열 (World.pred_sleep_stats)
PSLEEP_COLUMNS = list(PSLEEP_STAT_COLUMNS)
# repertoire(v3 R0)를 켠 세계의 행에만 더 붙는 열 (World.repertoire_stats)
REPERTOIRE_COLUMNS = list(REP_STAT_COLUMNS)
# threats(v3 R0)를 켠 세계의 행에만 더 붙는 열 (World.threats_stats)
THREAT_COLUMNS = list(THREAT_STAT_COLUMNS)


# --------------------------------------------------------------------- #
# G_γ — 할인 리턴-투-고
# --------------------------------------------------------------------- #


def load_gamma(path: str | Path | None = None) -> float:
    """configs/ppo_best.yaml 의 params.gamma. 파일이 없으면 기본값."""
    p = Path(path) if path is not None else PPO_CONFIG
    try:
        import yaml

        with open(p, encoding="utf-8") as f:
            return float(yaml.safe_load(f)["params"]["gamma"])
    except (OSError, KeyError, TypeError, ValueError):
        return DEFAULT_GAMMA


def model_gamma(path: str | Path) -> float | None:
    """SB3 zip 의 data 에 적힌 γ. torch 를 싣지 않고 읽는다. 못 읽으면 None."""
    import zipfile

    try:
        with zipfile.ZipFile(path) as z:
            return float(json.loads(z.read("data"))["gamma"])
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None


def tail_steps(gamma: float) -> int:
    """평균에서 뺄 롤아웃 끝 스텝 수 ceil(5/(1-γ)).

    롤아웃이 T 에서 끊기므로 끝 근처 스텝의 리턴-투-고는 미래 보상이 잘려 작게 나온다.
    끝에서 H 스텝 떨어진 지점의 잘린 몫은 γ^H 배다. H = 5/(1-γ) 면 γ^H ≈ e^-5 ≈ 0.7% 다.
    γ=0.99167 이면 H=600 이다.
    """
    return int(math.ceil(5.0 / (1.0 - gamma)))


def discounted_return_to_go(rew: np.ndarray, done: np.ndarray, gamma: float) -> np.ndarray:
    """(T,N) 보상과 사망 → (T,N) 리턴-투-고. 역방향 한 번: G_t = r_t + γ·G_{t+1}·(1-done_t).

    사망 스텝의 보상(사망 페널티 포함)은 넣는다. 그 뒤 같은 슬롯의 보상은 리스폰한 새 개체의
    것이라 넣지 않는다 — done_t 가 그 연결을 끊는다. 롤아웃 끝 다음은 0 으로 둔다.
    """
    rew = np.asarray(rew, dtype=np.float64)
    keep = 1.0 - np.asarray(done, dtype=np.float64)
    G = np.empty_like(rew)
    nxt = np.zeros(rew.shape[1:], dtype=np.float64)
    for t in range(len(rew) - 1, -1, -1):
        nxt = rew[t] + gamma * nxt * keep[t]
        G[t] = nxt
    return G


def g_gamma(rew: np.ndarray, done: np.ndarray, gamma: float, tail: int | None = None,
            head: int = 0) -> float:
    """모든 개체-스텝의 리턴-투-고 평균. 끝 `tail` 스텝(기본 ceil(5/(1-γ)))과 앞 `head` 스텝(기본 0)은
    평균에서 뺀다. 리턴-투-고 자체는 롤아웃 전체로 계산한다 — 앞부분은 평균에서만 빠진다.

    `head` 는 리셋 과도기를 빼려는 것이다 (계획서 6.1-4: γ=0.998 보고 평가는 10000스텝, 앞 500스텝 제외).
    남는 스텝이 없으면(T ≤ head + tail) nan 을 돌려준다.
    """
    if tail is None:
        tail = tail_steps(gamma)
    head = int(head)
    if head < 0 or tail < 0:
        raise ValueError(f"head={head}, tail={tail} 는 0 이상이어야 한다")
    T = len(rew)
    if T <= head + tail:
        return float("nan")
    G = discounted_return_to_go(rew, done, gamma)
    return float(G[head: T - tail].mean())


# --------------------------------------------------------------------- #
# 정책 래퍼 (행동·관측을 바꿔 끼우는 훅)
# --------------------------------------------------------------------- #

# 대조군·평가 모드의 RNG 스트림 구분값(시드 목록 둘째 칸). 시드가 같아도 쓰임마다 다른 수열을 쓴다.
# v1 세계는 default_rng(seed) = [seed, 0, ...], 기능은 [seed, 2, id, part] (env_v2/features.py) 라 겹치지 않는다.
# act_sample 은 확률 모드의 행동 잡음이다 (StochasticLearned). 번호는 바꾸지 않는다.
# act_hold 는 유지 표본 모드 해시의 첫 입력이다 (HoldLearned). default_rng 스트림이 아니라 SplitMix64 해시라 위 스트림과
# 생성기부터 다르지만, 번호를 여기에 같이 두어 겹치지 않게 한다.
_SALT = {"act_permute": 101, "obs_permute": 202, "act_sample": 303, "act_hold": 404}


def _perm_rng(kind: str, seed: int, salt: int) -> np.random.Generator:
    return np.random.default_rng([int(seed), _SALT[kind], int(salt)])


def forward_done(policy, done) -> None:
    """`policy` 에 리스폰 훅(`observe_done`)이 있으면 부른다. 없으면 아무것도 하지 않는다."""
    hook = getattr(policy, "observe_done", None)
    if hook is not None:
        hook(done)


def forward_bind(policy, world) -> None:
    """`policy` 에 세계 연결 훅(`bind_world`)이 있으면 부른다. 없으면 아무것도 하지 않는다."""
    hook = getattr(policy, "bind_world", None)
    if hook is not None:
        hook(world)


class _Hooks:
    """내장 래퍼의 훅 넘기기: 리스폰 훅·세계 연결 훅을 바탕 정책(`self.base`)으로 넘긴다."""

    def observe_done(self, done):
        forward_done(self.base, done)

    def bind_world(self, world):
        forward_bind(self.base, world)


class ActFix(_Hooks):
    """행동 차원 `dims` 를 상수로 고정한다. `values` 는 행동 전체 길이(세계의 act_dim) 벡터다 (C3-k)."""

    def __init__(self, base, dims, values):
        self.base, self.dims = base, list(dims)
        self.values = np.asarray(values, dtype=np.float64)

    def __call__(self, obs):
        a = np.array(self.base(obs), dtype=np.float64)
        if self.dims:
            a[:, self.dims] = self.values[self.dims]
        return a


class ActPermute(_Hooks):
    """같은 스텝에서 개체끼리 행동 벡터를 통째로 섞는다 (C1′).

    스텝마다 행동 분포(합·빈도)는 그대로고 개체와 행동의 대응만 끊긴다. RNG 는 시드로 정해진다.
    """

    def __init__(self, base, seed, salt=0):
        self.base = base
        self.rng = _perm_rng("act_permute", seed, salt)

    def __call__(self, obs):
        a = np.asarray(self.base(obs))
        return a[self.rng.permutation(len(a))]


class ObsFix(_Hooks):
    """관측 열 `dims` 를 `values` 로 고정한 뒤 정책에 넣는다 (C4-j 고정). 원본 관측은 건드리지 않는다."""

    def __init__(self, base, dims, values):
        self.base, self.dims = base, list(dims)
        self.values = np.asarray(values, dtype=np.float32).reshape(-1)
        if len(self.values) != len(self.dims):
            raise ValueError(f"dims {self.dims} 와 values 길이 {len(self.values)} 가 다르다")

    def __call__(self, obs):
        o = np.array(obs, dtype=np.float32)
        o[:, self.dims] = self.values
        return self.base(o)


class ObsPermute(_Hooks):
    """관측 열 `dims` 를 개체끼리 섞은 뒤 정책에 넣는다 (C4-j 순열). 여러 열이면 같은 순열로 함께 섞는다.

    모든 개체가 같은 값을 갖는 열(관측 5, 전역 피식 EMA)은 섞어도 바뀌지 않는다.
    """

    def __init__(self, base, dims, seed, salt=0):
        self.base, self.dims = base, list(dims)
        self.rng = _perm_rng("obs_permute", seed, salt)

    def __call__(self, obs):
        o = np.array(obs, dtype=np.float32)
        p = self.rng.permutation(len(o))
        o[:, self.dims] = o[p][:, self.dims]
        return self.base(o)


def n_segments(bins) -> int:
    """구간 수 = 열마다 (문턱 수 + 1) 의 곱."""
    return int(np.prod([len(t) + 1 for _, t in bins])) if bins else 1


def segment_ids(obs: np.ndarray, bins) -> np.ndarray:
    """관측 → 구간 id (C2-seg). `bins` = [[열 j, [문턱 t_0 < t_1 < ...]], ...].

    열 j 의 자리값은 x < t_0 이면 0, t_0 ≤ x < t_1 이면 1, ... 이다. 여러 열은 혼합 기수로 합친다
    (앞 열이 큰 자리). 예: [[2, [0.5]], [4, [0.5]]] 이면 id = 2·[d_pred≥0.5] + [energy≥0.5].
    """
    obs = np.asarray(obs)
    ids = np.zeros(len(obs), dtype=np.int64)
    for j, thr in bins:
        ids = ids * (len(thr) + 1) + np.digitize(obs[:, int(j)], np.asarray(thr, dtype=np.float64))
    return ids


class SegConst(_Hooks):
    """구간별 상수 (C2-seg). 구간마다 `dims` 행동만 `table[구간]` 값을 쓰고 나머지는 바탕 정책 값을 쓴다.

    바탕 정책을 C2 상수(`{"kind": "fixed"}`)로 두면 계획서 5.0 의 C2-seg 가 된다.
    `table` 은 (구간 수, len(dims)) 다.
    """

    def __init__(self, base, bins, dims, table):
        self.base, self.bins, self.dims = base, [[int(j), list(t)] for j, t in bins], list(dims)
        self.table = np.asarray(table, dtype=np.float64).reshape(n_segments(self.bins), len(self.dims))

    def __call__(self, obs):
        a = np.array(self.base(obs), dtype=np.float64)
        a[:, self.dims] = self.table[segment_ids(obs, self.bins)]
        return a


class _DoneForward(_Hooks):
    """리스폰 훅이 없는 외부 factory 래퍼를 감싸 훅(리스폰·세계 연결)을 바탕 정책으로 넘긴다. 행동은 래퍼 그대로다."""

    def __init__(self, policy, base):
        self.policy, self.base = policy, base

    def __call__(self, obs):
        return self.policy(obs)


class _BindForward:
    """세계 연결 훅이 없는 외부 factory 래퍼를 감싸 `bind_world` 만 바탕 정책으로 넘긴다. 행동·리스폰 훅은 래퍼 그대로다
    (래퍼에 리스폰 훅이 없으면 바탕으로 넘긴다)."""

    def __init__(self, policy, base):
        self.policy, self.base = policy, base

    def __call__(self, obs):
        return self.policy(obs)

    def observe_done(self, done):
        hook = getattr(self.policy, "observe_done", None)
        if hook is not None:
            hook(done)
        else:
            forward_done(self.base, done)

    def bind_world(self, world):
        forward_bind(self.base, world)


def _binds(policy) -> bool:
    """정책 사슬에 세계를 실제로 받는 정책(훅을 넘기기만 하는 내장 래퍼·껍질이 아닌 것, 예: rep_learned)이 있는가. 없으면
    factory 래퍼에 세계 연결 껍질을 씌우지 않는다 — 기존 스펙의 정책 객체 구조가 그대로다."""
    p = policy
    for _ in range(256):
        if isinstance(p, (_Hooks, _BindForward)):
            p = p.base
            continue
        return getattr(p, "bind_world", None) is not None
    return False


def make_wrapper(w: dict, base, seed: int):
    """래퍼 스펙 하나 → 정책. 내장 kind 가 아니면 `factory` ("모듈:함수") 를 불러 쓴다.

    외부 factory 의 모양은 `f(base, spec, seed) -> 정책` 이다. 워커가 그 모듈을 직접 import 한다.
    factory 정책에 리스폰 훅(`observe_done`)이 없고 바탕 정책에 있으면(유지 표본 모드) 훅을 넘기는 껍질을 씌운다.
    세계 연결 훅(`bind_world`)도 같다(바탕이 v3 R1 학습 정책일 때). 훅이 있는 factory 정책은 바탕으로 넘기는 일을 스스로 한다.
    """
    kind = w.get("kind")
    if kind == "act_fix":
        return ActFix(base, w["dims"], w["values"])
    if kind == "act_permute":
        return ActPermute(base, seed, w.get("salt", 0))
    if kind == "obs_fix":
        return ObsFix(base, w["dims"], w["values"])
    if kind == "obs_permute":
        return ObsPermute(base, w["dims"], seed, w.get("salt", 0))
    if kind == "seg_const":
        return SegConst(base, w["bins"], w["dims"], w["table"])
    if "factory" in w:
        mod, _, attr = w["factory"].partition(":")
        pol = getattr(importlib.import_module(mod), attr)(base, w, seed)
        if getattr(pol, "observe_done", None) is None and getattr(base, "observe_done", None) is not None:
            pol = _DoneForward(pol, base)
        if getattr(pol, "bind_world", None) is None and _binds(base):
            pol = _BindForward(pol, base)
        return pol
    raise ValueError(f"알 수 없는 래퍼: {w!r}")


# --------------------------------------------------------------------- #
# 행동 모드: 결정(평균 행동) / 확률(학습 분포에서 표본) / 유지 표본(보행·경계 열만 K 스텝 유지 표본)
# --------------------------------------------------------------------- #

ACTION_MODES = ("deterministic", "stochastic", "hold")
# 학습 때 SB3 가 환경에 넘기기 전에 자르는 범위 = env_v2.vec_env.ACT_SPACE (C++ 도 clamp(-3,3) → sigmoid)
ACT_LOW, ACT_HIGH = -3.0, 3.0


def action_mode(spec: dict) -> str:
    """정책 스펙의 행동 모드. 래퍼 스펙이면 바탕 정책의 모드다. 없으면 결정 모드."""
    base = spec.get("policy", spec)
    mode = base.get("mode", "deterministic")
    if mode not in ACTION_MODES:
        raise ValueError(f"알 수 없는 행동 모드 {mode!r} (쓸 수 있는 값: {ACTION_MODES})")
    return mode


class StochasticLearned:
    """학습 정책의 가우시안 분포에서 행동을 뽑는다 (확률 모드, 계획서 6.1-7).

    a = sigmoid(clip(μ(obs) + exp(log_std)·ε, -3, 3)), ε ~ N(0, I).
    학습 롤아웃(SB3 collect_rollouts: 분포에서 표본 → action_space 로 clip → vec_env 의 sigmoid)과 같은
    분포다. μ 는 자르기 전 평균이다 — 결정 모드는 sigmoid(clip(μ)) 이고, 잡음을 0 으로 두면 둘이 같다.
    ε 는 평가 시드에서 유도한 전용 스트림 [seed, 303, salt] 에서 호출마다 (N, 행동 수) 개씩 뽑는다. 그래서 같은
    시드·같은 호출 순서면 같은 행동이 나온다. 스트림은 v1 세계·기능·순열 대조군과 겹치지 않는다(_SALT).
    """

    def __init__(self, model, seed: int, salt: int = 0):
        self.model = model
        self.rng = _perm_rng("act_sample", seed, salt)

    def distribution(self, obs) -> tuple[np.ndarray, np.ndarray]:
        """관측 → (평균 μ, 표준편차 exp(log_std)), 둘 다 (N, 행동 수). 자르기 전 값이다."""
        import torch as th

        policy = self.model.policy
        obs_t, _ = policy.obs_to_tensor(np.asarray(obs, dtype=np.float32))
        with th.no_grad():
            d = policy.get_distribution(obs_t).distribution
            return (d.mean.cpu().numpy().astype(np.float64),
                    d.stddev.cpu().numpy().astype(np.float64))

    def __call__(self, obs):
        mu, std = self.distribution(obs)
        eps = self.rng.standard_normal(mu.shape)
        raw = np.clip(mu + std * eps, ACT_LOW, ACT_HIGH)
        return 1.0 / (1.0 + np.exp(-raw))


# ---- 유지 표본 모드 (수정 제안서 3.1 (가) R1): 해시·위상 표본기 ----
#
# 64비트 해시 (C++ 로 그대로 옮긴다. 모든 연산은 uint64, mod 2^64):
#   Mix64(z) = SplitMix64 마무리: z ^= z >> 30; z *= 0xBF58476D1CE4E5B9; z ^= z >> 27; z *= 0x94D049BB133111EB;
#              z ^= z >> 31
#   H(x_1, ..., x_n): h = 0; k = 1..n 마다 h = Mix64((h ^ x_k) + 0x9E3779B97F4A7C15). 정수 입력은 uint64 로 바꾼다
#              (음수는 2의 보수). H(x) 하나는 SplitMix64(시드 x) 의 첫 출력과 같다(H(0) = 0xE220A8397B1DCDAF).
#   U(h) = ((h >> 12) + 0.5) · 2^-52 — 위 52비트. 모든 값이 double 로 정확하고 [2^-53, 1 − 2^-53] ⊂ (0, 1) 이다.
#              (h >> 11)·2^-53 + 2^-54 는 h >> 11 ≥ 2^52 에서 54비트가 필요해 반올림되고, 최댓값은 정확히 1.0 이 된다.
# C++ 꼴:  uint64 Mix64(uint64 Z) { Z ^= Z >> 30; Z *= 0xBF58476D1CE4E5B9ull; Z ^= Z >> 27; Z *= 0x94D049BB133111EBull;
#                                   return Z ^ (Z >> 31); }
#          uint64 H = 0; for (uint64 X : Inputs) H = Mix64((H ^ X) + 0x9E3779B97F4A7C15ull);
#          double U = ((double)(H >> 12) + 0.5) * 0x1p-52;
HOLD_GOLDEN = 0x9E3779B97F4A7C15
_MIX_M1, _MIX_M2 = 0xBF58476D1CE4E5B9, 0x94D049BB133111EB
# 유지 표본 해시의 첫 입력(스트림 구분값 404, _SALT 참고). 확률 모드 잡음([seed, 303, salt] default_rng)과 섞이지 않는다.
HOLD_TAG = _SALT["act_hold"]
# 위상 해시의 '열' 자리 값. 행동 열 번호(4, 5, ...)로 쓰일 수 없는 값이고, 위상 해시는 입력이 하나 적다(블록 없음).
HOLD_PHASE_TAG = 0xFFFFFFFF
# 표본 대상 열의 시작. 앞 4열(v1 조향)은 결정 모드 평균 그대로다.
HOLD_FIRST_COL = ACT_DIM


def _u64(x) -> np.ndarray:
    """정수(배열) → uint64 배열. 음수는 2의 보수(C++ static_cast<uint64>)다."""
    a = np.asarray(x)
    if a.dtype.kind not in "iu":
        raise TypeError(f"해시 입력은 정수여야 한다: {a.dtype}")
    return a.astype(np.uint64)


def mix64(z) -> np.ndarray:
    """SplitMix64 마무리 함수 (전단사). 곱셈은 mod 2^64 로 넘친다."""
    z = _u64(z)
    with np.errstate(over="ignore"):
        z = z ^ (z >> np.uint64(30))
        z = z * np.uint64(_MIX_M1)
        z = z ^ (z >> np.uint64(27))
        z = z * np.uint64(_MIX_M2)
        return np.asarray(z ^ (z >> np.uint64(31)), dtype=np.uint64)


def hold_chain(h, *xs) -> np.ndarray:
    """해시 상태 `h` 에 입력 `xs` 를 차례로 더 섞는다. hold_hash(a, b, c) == hold_chain(hold_hash(a, b), c). 배열은 브로드캐스트."""
    h = _u64(h)
    with np.errstate(over="ignore"):
        for x in xs:
            h = mix64((h ^ _u64(x)) + np.uint64(HOLD_GOLDEN))
    return h


def hold_hash(*xs) -> np.ndarray:
    """H(x_1, ..., x_n) (위 정의). 입력이 배열이면 브로드캐스트한 uint64 배열이다."""
    return hold_chain(0, *xs)


def hold_uniform(h) -> np.ndarray:
    """U(h) = ((h >> 12) + 0.5)·2^-52 ∈ [2^-53, 1 − 2^-53] (위 정의). float64."""
    return ((_u64(h) >> np.uint64(12)).astype(np.float64) + 0.5) * 2.0 ** -52


def check_hold_k(k) -> int:
    """유지 길이 K 는 양의 정수다(bool 은 받지 않는다)."""
    if isinstance(k, bool) or not isinstance(k, (int, np.integer)) or int(k) < 1:
        raise ValueError(f"hold_k 는 양의 정수여야 한다. 받은 값: {k!r}")
    return int(k)


def hold_agent_keys(slots, generations) -> np.ndarray:
    """개체 키 = 슬롯·2^32 + 세대 (uint64). 세대 = 그 슬롯의 리스폰 횟수(0 부터)."""
    return (_u64(slots) << np.uint64(32)) + _u64(generations)


def hold_phase(seed: int, salt: int, keys, k: int) -> np.ndarray:
    """개체별 위상 φ = H(404, seed, salt, key, 0xFFFFFFFF) mod K (int64)."""
    return (hold_hash(HOLD_TAG, int(seed), int(salt), keys, HOLD_PHASE_TAG) % np.uint64(check_hold_k(k))).astype(np.int64)


def hold_noise(seed: int, salt: int, keys, cols, tick: int, k: int) -> np.ndarray:
    """(개체, 열) 유지 잡음 u = U(H(404, seed, salt, key, col, block)), block = ⌊(tick + φ)/K⌋. (len(keys), len(cols))."""
    keys = _u64(keys).reshape(-1)
    h_key = hold_chain(hold_hash(HOLD_TAG, int(seed), int(salt)), keys)
    k = check_hold_k(k)
    phase = (hold_chain(h_key, HOLD_PHASE_TAG) % np.uint64(k)).astype(np.int64)
    block = (int(tick) + phase) // k
    cols = np.asarray(cols, dtype=np.int64).reshape(-1)
    return hold_uniform(hold_chain(h_key[:, None], cols[None, :], block[:, None]))


def _phi(z) -> np.ndarray:
    """표준 정규 누적 Φ(z) = 0.5·erfc(−z/√2) (C++ 0.5 * std::erfc(-Z * M_SQRT1_2) 와 같은 꼴)."""
    from scipy.special import erfc

    return 0.5 * erfc(-np.asarray(z, dtype=np.float64) * math.sqrt(0.5))


def hold_cell_bounds(mu, sigma, thresholds) -> np.ndarray:
    """칸 경계의 누적 확률 p_j = P(a < t_j) = Φ((logit(t_j) − μ)/σ). (..., len(thresholds)).

    a = sigmoid(clip(μ + σ·Φ⁻¹(u), −3, 3)) 이므로 a ≥ t_j ⇔ u ≥ p_j 다. logit(t_j) ≤ −3 이면 늘 넘으므로 p_j = 0,
    logit(t_j) > 3 이면 넘지 못하므로 p_j = 1 이다(자르기). t_j 는 sigmoid 뒤 [0,1] 의 문턱(보행 1/3·2/3, 경계 0.5).
    """
    mu = np.asarray(mu, dtype=np.float64)[..., None]
    sigma = np.asarray(sigma, dtype=np.float64)[..., None]
    t = np.asarray(thresholds, dtype=np.float64)
    with np.errstate(divide="ignore"):
        lt = np.log(t) - np.log1p(-t)                      # logit(t), t = 0 → −inf, t = 1 → +inf
    p = _phi((lt - mu) / sigma)
    return np.where(lt <= ACT_LOW, 0.0, np.where(lt > ACT_HIGH, 1.0, p))


def hold_cells(mu, sigma, u, thresholds, strict: bool = False) -> np.ndarray:
    """Φ⁻¹ 없이 칸을 고른다: 칸 = Σ_j [u ≥ p_j] (`strict` 면 [u > p_j]). 보행은 [a ≥ t] 라 기본값, 경계는 a > 0.5 라 strict.

    연속값 a 를 문턱으로 나눈 칸과 같다(u = p_j 인 동률은 측도 0). C++ 는 이 꼴로 칸을 정한다 — 누적 확률은 double,
    `std::erfc` 로 계산한다(`_phi`). 연속값이 필요 없으므로 Φ⁻¹ 를 옮기지 않아도 된다.
    """
    p = hold_cell_bounds(mu, sigma, thresholds)
    u = np.asarray(u, dtype=np.float64)[..., None]
    return ((u > p) if strict else (u >= p)).sum(-1).astype(np.int64)


class HoldLearned:
    """유지 표본 모드 (수정 제안서 3.1 (가) R1 출시 모드). 조향은 평균, 보행·경계 열만 K 스텝 유지한 잡음으로 뽑는다.

    - 열 0~3 (v1 조향): sigmoid(clip(μ, −3, 3)) — `policies.registry` 결정 모드(model.predict(deterministic=True) →
      action_space 로 clip → sigmoid, 모두 float32)와 같은 float32 경로라 비트 단위로 같은 값이다.
    - 열 4~ (speed, vigilance — 이산 결정 열): a = sigmoid(clip(μ + σ·Φ⁻¹(u), −3, 3)), σ = exp(log_std) (float64).
      학습 분포(StochasticLearned)와 칸 확률이 같고, 다른 것은 잡음 u 를 K 스텝 유지한다는 것뿐이다.
    - u = U(H(404, seed, salt, key, col, block)), block = ⌊(tick + φ)/K⌋, φ = H(404, seed, salt, key, 0xFFFFFFFF) mod K
      (H·U 정의는 위 주석). tick = 이 정책을 만든 뒤 부른 횟수(첫 호출 0). φ 는 개체마다 달라 모든 개체가 한꺼번에
      바뀌지 않는다. 유지하는 것은 칸이 아니라 u 다 — μ 가 바뀌면(위협이 새로 보이면) 칸은 곧바로 바뀔 수 있다.
      상태를 저장하지 않으므로 C++ 에 새 Fragment 가 필요 없다.
    - 개체 키·리스폰 규칙: 파이썬은 key = 슬롯·2^32 + 세대(그 슬롯의 리스폰 횟수, 0 부터). `observe_done(done)` 이
      죽은 슬롯의 세대를 올리므로 리스폰한 개체는 다음 호출부터 새 키(새 φ, 새 u)를 쓴다. C++ 는 key = StableAgentId 다
      (리스폰하면 새 id). 키 값은 다르지만 해시와 분포는 같다.
    - seed 는 평가 시드(롤아웃), salt 는 스펙의 "salt"(기본 0). C++ 는 seed 에 세계 시드, tick 에 세계 시작부터 센
      정책 스텝 번호(첫 정책 스텝 0)를 쓴다. 해시 입력 순서는 (404, seed, salt, key, col, block) 그대로다.
    - 칸만 필요하면 Φ⁻¹ 없이 `hold_cells` 로 u 와 경계 누적 확률을 비교한다(C++ 꼴).
    """

    def __init__(self, model, seed: int, hold_k: int, salt: int = 0):
        self.model = model
        self.seed, self.salt, self.k = int(seed), int(salt), check_hold_k(hold_k)
        self.tick = 0
        self.gen = np.zeros(0, dtype=np.uint64)             # 슬롯별 세대 (호출·훅의 개체 수에 맞춰 늘린다)
        self._h0 = hold_hash(HOLD_TAG, self.seed, self.salt)
        self.last_u = None                                   # 마지막 호출의 u (개체, 표본 열). 진단·테스트용

    def _grow(self, n: int) -> None:
        if n > len(self.gen):
            self.gen = np.concatenate([self.gen, np.zeros(n - len(self.gen), dtype=np.uint64)])

    def keys(self, n: int) -> np.ndarray:
        """슬롯 0..n−1 의 지금 키."""
        self._grow(n)
        return hold_agent_keys(np.arange(n), self.gen[:n])

    def noise(self, n: int, cols) -> np.ndarray:
        """지금 tick 의 u (n, len(cols)). `hold_noise` 와 같은 값이다(키까지의 해시 상태를 한 번만 만든다)."""
        h_key = hold_chain(self._h0, self.keys(n))
        phase = (hold_chain(h_key, HOLD_PHASE_TAG) % np.uint64(self.k)).astype(np.int64)
        block = (self.tick + phase) // self.k
        cols = np.asarray(cols, dtype=np.int64)
        return hold_uniform(hold_chain(h_key[:, None], cols[None, :], block[:, None]))

    def observe_done(self, done) -> None:
        """리스폰 훅: 이번 스텝에 죽은(그 자리에 리스폰한) 슬롯의 세대를 올린다."""
        d = np.asarray(done, dtype=bool).reshape(-1)
        self._grow(len(d))
        self.gen[:len(d)][d] += np.uint64(1)

    def _forward32(self, obs) -> tuple[np.ndarray, np.ndarray]:
        """관측 → (μ, σ) float32 (N, 행동 수). model.predict 와 같은 전방 계산이다(자르기 전 평균)."""
        import torch as th

        policy = self.model.policy
        policy.set_training_mode(False)
        obs_t, _ = policy.obs_to_tensor(np.asarray(obs, dtype=np.float32))
        with th.no_grad():
            d = policy.get_distribution(obs_t).distribution
            return d.mean.cpu().numpy(), d.stddev.cpu().numpy()

    def distribution(self, obs) -> tuple[np.ndarray, np.ndarray]:
        """관측 → (평균 μ, 표준편차), 둘 다 float64 (N, 행동 수). StochasticLearned.distribution 과 같은 값이다."""
        mu32, sd32 = self._forward32(obs)
        return mu32.astype(np.float64), sd32.astype(np.float64)

    def __call__(self, obs):
        from scipy.special import ndtri

        mu32, sd32 = self._forward32(obs)
        space = self.model.policy.action_space
        raw32 = np.clip(mu32, space.low, space.high)                    # predict 의 clip (float32)
        a = (1.0 / (1.0 + np.exp(-raw32))).astype(np.float64)          # registry 의 sigmoid (float32) → float64
        n, n_act = a.shape
        cols = np.arange(HOLD_FIRST_COL, n_act)
        if len(cols):
            u = self.noise(n, cols)
            mu, sd = mu32[:, cols].astype(np.float64), sd32[:, cols].astype(np.float64)
            raw = np.clip(mu + sd * ndtri(u), ACT_LOW, ACT_HIGH)
            a[:, cols] = 1.0 / (1.0 + np.exp(-raw))
            self.last_u = u
        self.tick += 1
        return a


# 워커 안에서 학습 정책을 잡마다 다시 싣지 않는다. 결정적 추론이라 상태가 없다.
_BASE_CACHE: dict[str, object] = {}
# 확률·유지 표본 모드는 상태(RNG·tick·세대)가 있어 정책은 잡마다 새로 만들고, 실은 모델만 돌려쓴다.
_MODEL_CACHE: dict[str, object] = {}


def _load_model(spec: dict):
    import env.torch_init  # noqa: F401  ← torch보다 먼저 (워커에서도)
    from stable_baselines3 import PPO

    key = json.dumps({k: spec[k] for k in ("model", "device") if k in spec}, sort_keys=True)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = PPO.load(spec["model"], device=spec.get("device", "cpu"))
    return _MODEL_CACHE[key]


def adapt_spec(spec: dict, act_dim: int, act_names=()) -> dict:
    """정책 스펙을 행동 `act_dim` 개 세계에 맞춘다. random 바탕 정책에만 `act_dim` 을 적는다(래퍼 안쪽 포함).

    v1 행동 수(4)면 스펙을 그대로 돌려준다 — 예전 스펙·캐시 키가 바뀌지 않는다. fixed 는 action 길이가,
    learned 는 모델 출력이 차원을 정하므로 건드리지 않는다. Utility(4개)는 speed 세계에서 World.step 이 거부한다.
    `act_names` 가 repertoire(v3) 세계의 ('behavior',) 면 random 에 "choices"(행동 수 5)를 적어 정수 행동 번호를 고르게
    뽑는다 — 세계가 정수가 아닌 행동을 거부하기 때문이다(연속 [0, 1) 을 내림하면 늘 GRAZE 가 된다).
    """
    if "policy" in spec:
        return {**spec, "policy": adapt_spec(spec["policy"], act_dim, act_names)}
    if spec.get("kind") == "random" and tuple(act_names) == ("behavior",):
        from .repertoire import N_BEHAVIORS

        return {**spec, "act_dim": int(act_dim), "choices": N_BEHAVIORS}
    if spec.get("kind") == "random" and int(act_dim) != ACT_DIM:
        return {**spec, "act_dim": int(act_dim)}
    return spec


def _random_policy(spec: dict):
    """균등 랜덤 [0,1]^act_dim (C6). act_dim 4 는 policies.registry 의 random 과 같은 수열이다.
    "choices" k 가 있으면 정수 0..k−1 을 고르게 뽑아 float 로 낸다(repertoire 세계의 행동 번호, `adapt_spec`)."""
    rng = np.random.default_rng(spec.get("seed", 0))
    d = int(spec["act_dim"])
    if "choices" in spec:
        k = int(spec["choices"])
        return lambda obs: rng.integers(0, k, (len(obs), d)).astype(np.float64)
    return lambda obs: rng.random((len(obs), d))


def hold_k_of(spec: dict) -> int | None:
    """정책 스펙의 유지 길이 K. 래퍼 스펙이면 바탕 정책의 값이다. 유지 표본 모드가 아니면 None.

    유지 표본 모드는 "hold_k"(양의 정수)가 꼭 있어야 하고, 다른 모드에 "hold_k" 가 있으면 잘못 쓴 것으로 보고 멈춘다.
    """
    base = spec.get("policy", spec)
    k = base.get("hold_k")
    if action_mode(spec) != "hold":
        if k is not None:
            raise ValueError(f"hold_k 는 hold 모드에만 쓴다: {base!r}")
        return None
    if k is None:
        raise ValueError(f"hold 모드는 hold_k(양의 정수, 예: 24)가 필요하다: {base!r}")
    return check_hold_k(k)


_CM_FILES: dict[str, bool] = {}


def _is_cm(spec: dict) -> bool:
    """학습 정책 파일이 CM(env_v2/cm.py CMPolicy)인가. zip 의 data 만 읽고 워커 안에서 캐시한다."""
    from .cm import is_cm_file

    path = str(spec["model"])
    if path not in _CM_FILES:
        _CM_FILES[path] = is_cm_file(path)
    return _CM_FILES[path]


class RepLearned:
    """v3 R1 학습 정책(RepertoirePolicy 모델, `env_v2/rep_policy.py`)의 배포·판정 모드: 마스크 로짓의 argmax(동점이면 낮은
    번호, 모드 0). 출력은 (N, 1) 행동 번호(float)다.

    `bind_world(w)` 로 받은 세계의 참 상태로 매 호출 마스크를 만든다: m = 허용(모델의 rep_allowed) ∧ 가능(지금 세계 관측
    `w.observe()`) ∧ 결정(`w.rep_peek()`). 망에는 호출에 받은 관측을 넣는다 — C4 `obs_fix` 같은 바깥 래퍼가 고친 관측은 망
    입력만 바꾸고 마스크는 바꾸지 않는다. 연결 전에 부르면 멈춘다.
    """

    def __init__(self, model):
        from .rep_policy import is_rep_model

        if not is_rep_model(model):
            raise ValueError("rep_learned 는 RepertoirePolicy(env_v2/rep_policy.py) 모델만 받는다")
        self.model = model
        pol = model.policy
        self.params = {"allowed_mask": pol.rep_allowed_mask}
        self.world = None

    def bind_world(self, world) -> None:
        pol = self.model.policy
        if getattr(world, "_rp", None) is None:
            raise ValueError("rep_learned 는 repertoire 세계(v3)에서만 쓴다")
        if tuple(world.obs_names) != tuple(pol.rep_obs_names):
            raise ValueError(f"모델의 관측 {list(pol.rep_obs_names)} 이 세계의 관측 {list(world.obs_names)} 과 다르다")
        self.world = world

    def mask(self) -> np.ndarray:
        """연결한 세계의 지금 마스크 (N, 5) bool."""
        from .rep_policy import action_mask

        if self.world is None:
            raise ValueError("rep_learned 정책은 bind_world(w) 로 세계를 받은 뒤에 쓴다(rollout 이 부른다)")
        return action_mask(self.world, self.world.observe(), self.params)

    def __call__(self, obs):
        from .rep_policy import policy_obs, rep_argmax

        m = self.mask()
        a = rep_argmax(self.model.policy, policy_obs(obs, m))
        self.last_mask = m
        return a.astype(np.float64)[:, None]


def _base_policy(spec: dict, seed: int = 0):
    from policies.registry import make_policy

    if spec.get("kind") == "rep_learned":
        # v3 R1 학습 정책: argmax 만 있다(모드·유지 길이를 받지 않는다). 세계 연결 상태가 있어 잡마다 새로 만들고 모델만 돌려쓴다
        if spec.get("mode", "deterministic") != "deterministic" or "hold_k" in spec:
            raise ValueError(f"rep_learned 는 argmax(결정 모드)만 쓴다: {spec!r}")
        return RepLearned(_load_model({"model": spec["path"], **({"device": spec["device"]} if "device" in spec else {})}))
    k = hold_k_of(spec)                     # 모드 검사 + 유지 표본 모드의 K (다른 모드에 hold_k 가 있으면 멈춘다)
    if spec.get("kind") == "learned" and _is_cm(spec):
        # v2.2r 범주형 보행 CM 모델(env_v2/cm.py): 결정 = 최빈 범주, hold = 유지 잡음의 누적 확률 비교, 확률 = 범주 표본.
        # 결정 모드도 registry(가우시안 sigmoid)로는 못 돌린다. 상태(tick·세대·RNG)가 있어 잡마다 새로 만든다
        from .cm import make_cm_policy

        return make_cm_policy(_load_model(spec), seed, action_mode(spec), k, spec.get("salt", 0))
    if action_mode(spec) == "stochastic":
        if spec.get("kind") != "learned":
            raise ValueError(f"확률 모드는 학습 정책에만 있다: {spec!r}")
        return StochasticLearned(_load_model(spec), seed, spec.get("salt", 0))
    if k is not None:                       # 유지 표본 모드: 상태(tick·세대)가 있어 잡마다 새로 만든다
        if spec.get("kind") != "learned":
            raise ValueError(f"유지 표본 모드는 학습 정책에만 있다: {spec!r}")
        return HoldLearned(_load_model(spec), seed, k, spec.get("salt", 0))
    if spec.get("kind") == "random" and "act_dim" in spec:      # 행동 4개가 아닌 세계의 random (adapt_spec)
        return _random_policy(spec)
    if spec.get("kind") != "learned":       # random 은 RNG 상태가 있어 잡마다 새로 만든다
        return make_policy(spec)
    key = json.dumps(spec, sort_keys=True)
    if key not in _BASE_CACHE:
        _BASE_CACHE[key] = make_policy(spec)
    return _BASE_CACHE[key]


def build_policy(spec: dict, seed: int = 0):
    """정책 스펙(래퍼 포함) → 관측 (N, 관측 수) → 행동 (N, 행동 수) 함수. 래퍼는 목록 순서대로 바깥에 씌운다.

    `seed` 는 순열 래퍼와 확률·유지 표본 모드 잡음의 시드다(롤아웃에서는 평가 시드).
    """
    if "policy" not in spec:
        return _base_policy(spec, seed)
    pol = _base_policy(spec["policy"], seed)
    for w in spec.get("wrap", []):
        pol = make_wrapper(w, pol, seed)
    return pol


# --------------------------------------------------------------------- #
# 롤아웃
# --------------------------------------------------------------------- #


def rollout(cfg: Config, policy, seed: int, steps: int, *, gamma: float | None = None,
            tail: int | None = None, record_every: int = 0, head: int = 0) -> dict:
    """시드 하나. World.stats() 10열 + G_γ + 아사율, 그리고 `_` 로 시작하는 원시 합계·표본을 돌려준다.
    speed 를 켠 세계는 `World.gait_stats()` 열(GAIT_COLUMNS), vigilance 를 켠 세계는 `World.vigil_stats()`
    열(VIGIL_COLUMNS)도 붙는다.

    `head`·`tail` 은 G_γ 평균에서만 뺀다. World.stats() 의 다른 지표는 롤아웃 전체 값이다.

    - `_act_sum`, `_act_sq`, `_act_n`: 실제로 적용된 행동의 합·제곱합·개수 (C1 평균 행동용)
    - `_obs_sum`: 관측 합 (C4 평균 관측용)
    - `_obs`, `_act`: `record_every` 스텝마다의 관측과 그 스텝 행동 (반응 곡선·R²용)

    정책(래퍼 포함)에 `observe_done` 이 있으면 `w.step` 뒤마다 그 스텝의 사망 배열로 부른다(유지 표본 모드의 리스폰 키).
    `bind_world` 가 있으면 World 를 만든 직후 한 번 부른다(v3 R1 `rep_learned` 의 마스크).
    """
    gamma = load_gamma() if gamma is None else float(gamma)
    w = World(cfg, seeds=[seed])
    forward_bind(policy, w)                 # 세계 연결 훅(v3 R1 rep_learned). 훅이 없는 정책은 아무 일도 없다
    N, A = w.N, w.act_dim
    rew = np.empty((steps, N), dtype=np.float64)
    done = np.empty((steps, N), dtype=bool)
    act_sum, act_sq = np.zeros(A), np.zeros(A)
    obs_sum = np.zeros(w.obs_dim)
    obs_s, act_s = [], []
    done_hook = getattr(policy, "observe_done", None)
    for t in range(steps):
        obs = w.observe()
        a = np.asarray(policy(obs), dtype=np.float64)
        w._check_action(a)                  # 행동 수가 세계와 다르면 합산 전에 읽기 쉬운 오류로 멈춘다
        act_sum += a.sum(0)
        act_sq += (a * a).sum(0)
        obs_sum += obs.sum(0, dtype=np.float64)
        if record_every and t % record_every == 0:
            obs_s.append(np.array(obs, dtype=np.float32))
            act_s.append(a.copy())
        _, r, d, _ = w.step(a)
        rew[t], done[t] = r, d
        if done_hook is not None:
            done_hook(d)

    s = w.stats()
    s["seed"] = int(seed)
    s["g_gamma"] = g_gamma(rew, done, gamma, tail, head)
    deaths = w._pred_deaths + w._starve_deaths
    s["starve_rate"] = w._starve_deaths / max(steps * N, 1)
    s["starve_share"] = w._starve_deaths / deaths if deaths else float("nan")
    if w._sp is not None:
        gs = w.gait_stats()
        s.update((c, gs[c]) for c in GAIT_COLUMNS)
    if w._vg is not None:
        vs = w.vigil_stats()
        s.update((c, vs[c]) for c in VIGIL_COLUMNS)
    if w._vw is not None:
        ws = w.window_stats()
        s.update((c, ws[c]) for c in WINDOW_COLUMNS)
    if w._dn is not None:
        ds = w.daynight_stats()
        s.update((c, ds[c]) for c in DAYNIGHT_COLUMNS)
    if w._ps is not None:
        ps = w.pred_sleep_stats()
        s.update((c, ps[c]) for c in PSLEEP_COLUMNS)
    if w._rp is not None:
        rs = w.repertoire_stats()
        s.update((c, rs[c]) for c in REPERTOIRE_COLUMNS)
    if w._th is not None:
        ts = w.threats_stats()
        s.update((c, ts[c]) for c in THREAT_COLUMNS)
    s["_act_sum"], s["_act_sq"], s["_act_n"] = act_sum, act_sq, steps * N
    s["_obs_sum"] = obs_sum
    if record_every:
        s["_obs"] = np.concatenate(obs_s) if obs_s else np.empty((0, w.obs_dim), np.float32)
        s["_act"] = np.concatenate(act_s) if act_s else np.empty((0, A))
    return s


def _run_one(args):
    """프로세스 경계를 넘으므로 인자는 picklable 한 것만 받는다."""
    cfg_dict, spec, seed, steps, gamma, tail, record_every, head = args
    return rollout(Config(cfg_dict), build_policy(spec, seed), seed, steps,
                   gamma=gamma, tail=tail, record_every=record_every, head=head)


def default_workers(n_jobs: int, cap: int = 6) -> int:
    """다른 학습이 돌고 있어도 넘치지 않게 기본 상한을 둔다."""
    return max(1, min(n_jobs, cap, (os.cpu_count() or 2)))


def make_executor(workers: int) -> ProcessPoolExecutor | None:
    """명령 하나 동안 돌려쓸 워커 풀. 1 이하면 None (같은 프로세스에서 순서대로 돈다)."""
    if workers <= 1:
        return None
    return ProcessPoolExecutor(max_workers=workers, initializer=_init_worker)


def run_specs(cfg: Config, specs: dict[str, dict], seeds, steps: int, *, workers: int | None = None,
              gamma: float | None = None, tail: int | None = None, record_every: int = 0,
              executor: ProcessPoolExecutor | None = None, head: int = 0) -> dict[str, list[dict]]:
    """이름 → 스펙 여러 개를 시드마다 돌린다. 이름 → 시드순 행 목록.

    모든 (스펙, 시드) 잡을 한 풀에 넣어 코어를 고르게 쓴다. `executor` 를 주면 그 풀을 쓰고,
    없으면 `workers` 개짜리 풀을 이번 호출 동안만 만든다.
    """
    seeds = [int(s) for s in seeds]
    gamma = load_gamma() if gamma is None else float(gamma)
    payload, keys = [], []
    for name, spec in specs.items():
        for s in seeds:
            payload.append((cfg.to_dict(), spec, s, steps, gamma, tail, record_every, int(head)))
            keys.append(name)
    if executor is not None:
        results = list(executor.map(_run_one, payload))
    else:
        if workers is None:
            workers = default_workers(len(payload))
        ex = make_executor(min(workers, len(payload)))
        if ex is None:
            results = [_run_one(p) for p in payload]
        else:
            with ex:
                results = list(ex.map(_run_one, payload))
    out: dict[str, list[dict]] = {name: [] for name in specs}
    for name, r in zip(keys, results):
        out[name].append(r)
    for rows in out.values():
        rows.sort(key=lambda r: r["seed"])
    return out


def public_row(r: dict) -> dict:
    """JSON 에 남길 열만 (원시 배열 `_*` 제외)."""
    return {k: (float(v) if k != "seed" else int(v)) for k, v in r.items() if not k.startswith("_")}
