"""정책 스펙 → 호출 가능한 정책.

정책을 **picklable한 dict**로 기술한다. 튜닝(§5.2)과 평가(§7.1)가 시드별 롤아웃을
별도 프로세스로 돌리는데, Windows의 spawn 방식은 클로저를 피클할 수 없기 때문이다.
워커는 스펙만 받아서 자기 쪽에서 정책을 만든다.

스펙 예:
    {"kind": "random", "seed": 0}
    {"kind": "utility", "params": {...}}      # 생략하면 configs/utility_best.yaml
    {"kind": "learned", "model": "ckpt/final.zip"}   # Phase 3 이후
"""

from __future__ import annotations

import numpy as np

from .utility import UTILITY_PARAMS, load_best_params, utility_policy


def make_policy(spec: dict):
    """관측 (N,7) → 행동 (N,4) in [0,1] 를 돌려주는 함수를 만든다.

    반환 행동은 **항상 [0,1]** 이다 (§1.3). 학습 정책의 (-3,3) 출력은 여기서
    sigmoid를 거쳐 나간다.
    """
    kind = spec["kind"]

    if kind == "random":
        rng = np.random.default_rng(spec.get("seed", 0))
        return lambda obs: rng.random((len(obs), 4))

    if kind == "fixed":                       # 진단용: 모든 개체에 같은 행동
        a = np.asarray(spec["action"], dtype=np.float64)
        return lambda obs: np.tile(a, (len(obs), 1))

    if kind == "utility":
        p = spec.get("params")
        if p is None:
            p = load_best_params(spec.get("path"))
        elif p == "default":
            p = UTILITY_PARAMS
        return lambda obs: utility_policy(obs, p)

    if kind == "learned":
        return _make_learned(spec)

    raise ValueError(f"알 수 없는 정책 kind: {kind!r}")


def _make_learned(spec: dict):
    """§7.1 — sigmoid(model.predict(obs, deterministic=True)[0]). Phase 3 이후."""
    # 워커 프로세스에서도 torch가 실리므로 여기서도 먼저 잡아 준다. 안 하면
    # OMP Error #15 로 워커가 통째로 죽고 BrokenProcessPool 이 된다.
    import env.torch_init  # noqa: F401

    try:
        from stable_baselines3 import PPO
    except ImportError as e:  # pragma: no cover - Phase 3 전
        raise SystemExit(
            "learned 정책은 stable-baselines3가 필요하다 (Phase 3). "
            "pip install stable-baselines3"
        ) from e
    model = PPO.load(spec["model"], device=spec.get("device", "cpu"))

    def policy(obs):
        raw = model.predict(obs, deterministic=True)[0]   # §7.1 deterministic 필수
        return 1.0 / (1.0 + np.exp(-raw))                 # §1.3 sigmoid는 여기서
    return policy
