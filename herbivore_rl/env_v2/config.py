"""V2 설정 로더 — v1 `configs/default.yaml` 위에 `configs/v2.yaml` 을 덮는다.

v1 키는 그대로 속성으로 남고(`cfg.see_r` 등), V2 전용 값은 `cfg.v2` 딕셔너리로 들어간다.
`overrides` 에 적힌 v1 키만 v1 값을 덮는다. 값이 키: 값 묶음인 v1 키(지금은 `rand` 하나)는 한 단계만 합친다:
적은 하위 키만 바꾸고 나머지 하위 키는 v1 값 그대로 둔다(예: `overrides: {rand: {pred_speed_mult: [0.6, 0.95]}}`
는 rand 의 world_size 등을 지우지 않는다). 하위 키의 값(목록 등)은 통째로 바꾼다. 묶음이 아닌 키는 전처럼 통째로
바꾼다. overrides 가 비었거나 묶음이 아닌 키만 덮는 설정은 10-02 전과 같은 결과다(tests/test_features_v2.py).
읽을 때 바로 실패하는 것: 모르는 최상위 키, v1 에 없는 overrides 키, 묶음 키의 v1 에 없는 하위 키, 묶음 키에
묶음이 아닌 값·묶음이 아닌 키에 묶음 값, `features` 블록의 형식 오류(`env_v2/features.py` — 모르는 기능 이름,
아직 구현하지 않은 기능 켜기, 구현한 기능의 모르는·빠진 계수 등).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from env.config import DEFAULT_CONFIG, ROOT, Config

from .features import FEATURE_IDS, parse_features

V2_CONFIG = ROOT / "configs" / "v2.yaml"

# v2.yaml 최상위 키. 그 밖의 키는 들여쓰기 실수(`features:` 아래 블록이 최상위로 나옴)나 오타라
# 그냥 두면 기능이 모두 꺼진 v1 세계에서 조용히 학습한다.
V2_TOP_KEYS = frozenset({"version", "overrides", "features", "train"})


def load_v2_config(path: str | Path | None = None, base: str | Path | None = None) -> Config:
    with open(Path(base) if base is not None else DEFAULT_CONFIG, encoding="utf-8") as f:
        data = dict(yaml.safe_load(f))
    with open(Path(path) if path is not None else V2_CONFIG, encoding="utf-8") as f:
        v2 = yaml.safe_load(f) or {}
    if not isinstance(v2, dict):
        raise ValueError(f"v2 설정 최상위는 키: 값 꼴이어야 한다. 받은 값: {v2!r}")
    v2 = dict(v2)
    extra = sorted(set(v2) - V2_TOP_KEYS, key=str)
    if extra:
        hint = [k for k in extra if k in FEATURE_IDS]
        raise ValueError(
            f"v2 설정에 모르는 최상위 키 {extra} 가 있다. 쓸 수 있는 키: {', '.join(sorted(V2_TOP_KEYS))}"
            + (f". {hint} 는 기능 이름이다 — `features:` 아래로 들여쓴다" if hint else "")
        )
    overrides = v2.pop("overrides", None) or {}
    if not isinstance(overrides, dict):
        raise ValueError(f"overrides 는 v1 키: 값 꼴이어야 한다. 받은 값: {overrides!r}")
    unknown = sorted(set(overrides) - set(data), key=str)
    if unknown:
        raise ValueError(f"overrides 는 v1 키(configs/default.yaml)만 덮는다. 모르는 키: {unknown}")
    data.update(_merge_overrides(data, overrides))
    parse_features(v2.get("features"))      # 형식부터 검사한다(dict() 변환 오류보다 읽기 쉬운 메시지)
    v2["features"] = dict(v2.get("features") or {})
    data["v2"] = v2
    return Config(data)


def _merge_overrides(v1: dict, overrides: dict) -> dict:
    """overrides → v1 위에 덮을 값. 묶음(dict) 값 v1 키는 한 단계 합친 사본, 그 밖은 적은 값 그대로."""
    out = {}
    for k, v in overrides.items():
        base = v1[k]
        if isinstance(base, dict):
            if not isinstance(v, dict):
                raise ValueError(f"overrides.{k} 는 v1 에서 하위 키 묶음이라 {{하위 키: 값}} 꼴로 적는다. 받은 값: {v!r}")
            bad = sorted(set(v) - set(base), key=str)
            if bad:
                raise ValueError(f"overrides.{k} 에 v1 {k} 에 없는 하위 키 {bad} 가 있다. "
                                 f"쓸 수 있는 하위 키: {', '.join(map(str, base))}")
            out[k] = {**base, **v}
        elif isinstance(v, dict):
            raise ValueError(f"overrides.{k} 는 v1 에서 묶음이 아니다(값 {base!r}). 하위 키를 적을 수 없다: {v!r}")
        else:
            out[k] = v
    return out
