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
- **앞부분 제외.** `head` 를 주면 G_γ 평균에서 롤아웃 앞 `head` 스텝(리셋 과도기)도 뺀다 (6.1-4, 기본 0).

정책 스펙 예:
    {"kind": "learned", "model": "ckpt/final.zip"}                 # policies.registry 스펙 그대로
    {"kind": "learned", "model": "ckpt/final.zip", "mode": "stochastic"}   # 확률 모드
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

from .world import ACT_DIM, OBS_DIM, World

# 학습 γ 의 출처. 모델마다 γ 가 다르면 --gamma 로 덮는다.
PPO_CONFIG = ROOT / "configs" / "ppo_best.yaml"
DEFAULT_GAMMA = 0.9916661555611042

# World.stats() 10열 뒤에 붙는 열. 시드마다 하나의 값이다.
EXTRA_COLUMNS = ["g_gamma", "starve_rate", "starve_share"]
ROW_COLUMNS = STAT_COLUMNS + EXTRA_COLUMNS


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
_SALT = {"act_permute": 101, "obs_permute": 202, "act_sample": 303}


def _perm_rng(kind: str, seed: int, salt: int) -> np.random.Generator:
    return np.random.default_rng([int(seed), _SALT[kind], int(salt)])


class ActFix:
    """행동 차원 `dims` 를 상수로 고정한다. `values` 는 행동 전체 길이(ACT_DIM) 벡터다 (C3-k)."""

    def __init__(self, base, dims, values):
        self.base, self.dims = base, list(dims)
        self.values = np.asarray(values, dtype=np.float64)

    def __call__(self, obs):
        a = np.array(self.base(obs), dtype=np.float64)
        if self.dims:
            a[:, self.dims] = self.values[self.dims]
        return a


class ActPermute:
    """같은 스텝에서 개체끼리 행동 벡터를 통째로 섞는다 (C1′).

    스텝마다 행동 분포(합·빈도)는 그대로고 개체와 행동의 대응만 끊긴다. RNG 는 시드로 정해진다.
    """

    def __init__(self, base, seed, salt=0):
        self.base = base
        self.rng = _perm_rng("act_permute", seed, salt)

    def __call__(self, obs):
        a = np.asarray(self.base(obs))
        return a[self.rng.permutation(len(a))]


class ObsFix:
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


class ObsPermute:
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


class SegConst:
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


def make_wrapper(w: dict, base, seed: int):
    """래퍼 스펙 하나 → 정책. 내장 kind 가 아니면 `factory` ("모듈:함수") 를 불러 쓴다.

    외부 factory 의 모양은 `f(base, spec, seed) -> 정책` 이다. 워커가 그 모듈을 직접 import 한다.
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
        return getattr(importlib.import_module(mod), attr)(base, w, seed)
    raise ValueError(f"알 수 없는 래퍼: {w!r}")


# --------------------------------------------------------------------- #
# 행동 모드: 결정(평균 행동) / 확률(학습 분포에서 표본)
# --------------------------------------------------------------------- #

ACTION_MODES = ("deterministic", "stochastic")
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
    ε 는 평가 시드에서 유도한 전용 스트림 [seed, 303, salt] 에서 호출마다 (N, 4) 개씩 뽑는다. 그래서 같은
    시드·같은 호출 순서면 같은 행동이 나온다. 스트림은 v1 세계·기능·순열 대조군과 겹치지 않는다(_SALT).
    """

    def __init__(self, model, seed: int, salt: int = 0):
        self.model = model
        self.rng = _perm_rng("act_sample", seed, salt)

    def distribution(self, obs) -> tuple[np.ndarray, np.ndarray]:
        """관측 → (평균 μ, 표준편차 exp(log_std)), 둘 다 (N, 4). 자르기 전 값이다."""
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


# 워커 안에서 학습 정책을 잡마다 다시 싣지 않는다. 결정적 추론이라 상태가 없다.
_BASE_CACHE: dict[str, object] = {}
# 확률 모드는 RNG 상태가 있어 정책은 잡마다 새로 만들고, 실은 모델만 돌려쓴다.
_MODEL_CACHE: dict[str, object] = {}


def _load_model(spec: dict):
    import env.torch_init  # noqa: F401  ← torch보다 먼저 (워커에서도)
    from stable_baselines3 import PPO

    key = json.dumps({k: spec[k] for k in ("model", "device") if k in spec}, sort_keys=True)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = PPO.load(spec["model"], device=spec.get("device", "cpu"))
    return _MODEL_CACHE[key]


def _base_policy(spec: dict, seed: int = 0):
    from policies.registry import make_policy

    if action_mode(spec) == "stochastic":
        if spec.get("kind") != "learned":
            raise ValueError(f"확률 모드는 학습 정책에만 있다: {spec!r}")
        return StochasticLearned(_load_model(spec), seed, spec.get("salt", 0))
    if spec.get("kind") != "learned":       # random 은 RNG 상태가 있어 잡마다 새로 만든다
        return make_policy(spec)
    key = json.dumps(spec, sort_keys=True)
    if key not in _BASE_CACHE:
        _BASE_CACHE[key] = make_policy(spec)
    return _BASE_CACHE[key]


def build_policy(spec: dict, seed: int = 0):
    """정책 스펙(래퍼 포함) → 관측 (N,7) → 행동 (N,4) 함수. 래퍼는 목록 순서대로 바깥에 씌운다.

    `seed` 는 순열 래퍼와 확률 모드 잡음 스트림의 시드다(롤아웃에서는 평가 시드).
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

    `head`·`tail` 은 G_γ 평균에서만 뺀다. World.stats() 의 다른 지표는 롤아웃 전체 값이다.

    - `_act_sum`, `_act_sq`, `_act_n`: 실제로 적용된 행동의 합·제곱합·개수 (C1 평균 행동용)
    - `_obs_sum`: 관측 합 (C4 평균 관측용)
    - `_obs`, `_act`: `record_every` 스텝마다의 관측과 그 스텝 행동 (반응 곡선·R²용)
    """
    gamma = load_gamma() if gamma is None else float(gamma)
    w = World(cfg, seeds=[seed])
    N = w.N
    rew = np.empty((steps, N), dtype=np.float64)
    done = np.empty((steps, N), dtype=bool)
    act_sum, act_sq = np.zeros(ACT_DIM), np.zeros(ACT_DIM)
    obs_sum = np.zeros(OBS_DIM)
    obs_s, act_s = [], []
    for t in range(steps):
        obs = w.observe()
        a = np.asarray(policy(obs), dtype=np.float64)
        act_sum += a.sum(0)
        act_sq += (a * a).sum(0)
        obs_sum += obs.sum(0, dtype=np.float64)
        if record_every and t % record_every == 0:
            obs_s.append(np.array(obs, dtype=np.float32))
            act_s.append(a.copy())
        _, r, d, _ = w.step(a)
        rew[t], done[t] = r, d

    s = w.stats()
    s["seed"] = int(seed)
    s["g_gamma"] = g_gamma(rew, done, gamma, tail, head)
    deaths = w._pred_deaths + w._starve_deaths
    s["starve_rate"] = w._starve_deaths / max(steps * N, 1)
    s["starve_share"] = w._starve_deaths / deaths if deaths else float("nan")
    s["_act_sum"], s["_act_sq"], s["_act_n"] = act_sum, act_sq, steps * N
    s["_obs_sum"] = obs_sum
    if record_every:
        s["_obs"] = np.concatenate(obs_s) if obs_s else np.empty((0, OBS_DIM), np.float32)
        s["_act"] = np.concatenate(act_s) if act_s else np.empty((0, ACT_DIM))
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
