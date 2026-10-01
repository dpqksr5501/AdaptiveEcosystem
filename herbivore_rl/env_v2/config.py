"""V2 설정 로더 — v1 `configs/default.yaml` 위에 `configs/v2.yaml` 을 덮는다.

v1 키는 그대로 속성으로 남고(`cfg.see_r` 등), V2 전용 값은 `cfg.v2` 딕셔너리로 들어간다.
`overrides` 에 적힌 v1 키만 v1 값을 덮는다.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from env.config import DEFAULT_CONFIG, ROOT, Config

V2_CONFIG = ROOT / "configs" / "v2.yaml"


def load_v2_config(path: str | Path | None = None, base: str | Path | None = None) -> Config:
    with open(Path(base) if base is not None else DEFAULT_CONFIG, encoding="utf-8") as f:
        data = dict(yaml.safe_load(f))
    with open(Path(path) if path is not None else V2_CONFIG, encoding="utf-8") as f:
        v2 = dict(yaml.safe_load(f) or {})
    data.update(v2.pop("overrides", None) or {})
    v2.setdefault("features", {})
    v2["features"] = dict(v2["features"] or {})
    data["v2"] = v2
    return Config(data)
