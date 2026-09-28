"""configs/*.yaml → 속성 접근 객체.

§9.7: 상수는 한 곳(`configs/default.yaml`)에만 적는다. 파이썬도 언리얼도 여기서 읽는다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "configs" / "default.yaml"


class Config:
    """yaml 최상위 키를 속성으로 노출한다. `rand` 는 dict 그대로 둔다."""

    def __init__(self, data: dict[str, Any]):
        self._data = dict(data)
        for k, v in self._data.items():
            setattr(self, k, v)

    # --- 파생값: 스펙이 값을 정의하지 않고 계산으로 못박은 것들 ---

    @property
    def fov_cos(self) -> float:
        """시야 각도 제한 판정용 cos(fov/2). 관측 hot path에서 매번 쓰므로 미리 둔다."""
        import math

        return math.cos(math.radians(self.fov_deg) * 0.5)

    @property
    def pred_fov_cos(self) -> float:
        import math

        return math.cos(math.radians(self.pred_fov_deg) * 0.5)

    @property
    def herb_speed_cm_s(self) -> float:
        """§9.7: HerbSpeed = herb_speed × GridUnitCm ÷ (PolicyInterval/60) cm/s"""
        return self.herb_speed * self.grid_unit_cm / (self.policy_interval / 60.0)

    @property
    def see_radius_cm(self) -> float:
        """§9.7: SeeRadius = see_r × GridUnitCm"""
        return self.see_r * self.grid_unit_cm

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def replace(self, **kw: Any) -> "Config":
        """일부 값만 바꾼 사본. 테스트·튜닝용."""
        d = dict(self._data)
        d.update(kw)
        return Config(d)

    def __repr__(self) -> str:
        return f"Config({len(self._data)} keys)"


def load_config(path: str | Path | None = None) -> Config:
    p = Path(path) if path is not None else DEFAULT_CONFIG
    with open(p, encoding="utf-8") as f:
        return Config(yaml.safe_load(f))
