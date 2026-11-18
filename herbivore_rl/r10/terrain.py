"""R10 층 지형과 맵 카드 (0 단계 사양 4 절).

셀 하나 = cell_m(기본 1 m). 배열은 [iy, ix] (y 가 행). 세계 좌표 x ∈ [0, W·cell), y ∈ [0, H·cell).
- ground_z: 땅 높이(물이 있는 셀은 바닥 높이와 같다 — 걷는 몸은 바닥을 밟는다)
- water_bed_z · water_surf0_z: 물 바닥·기준 수면. water_sys 셀만 물이 될 수 있고, 수면 = 기준 수면 + 수위 오프셋(t).
- current: 물살 (m/s, x·y)
- block: 바위·나무 줄기 (땅 몸 못 지나감) · cover_sight: 시야를 막는 정도 0~1 · cover_body: 은신처 안(보호) · canopy: 나는 몸 이착륙 막음
- food: FOOD_KINDS 차례의 (양, 용량, 재생/s, 마름/s)
맵 카드 = 이 배열들(npz) + 머리(json). 생성기(mapgen)와 언리얼 내보내기가 같은 꼴을 쓴다.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

CARD_FORMAT = "r10-map"
CARD_VERSION = 1
FOOD_KINDS = ("grass", "forbs", "browse", "wet_meadow", "roots", "insects", "aquatic", "drift")
LAYERS = ("ground_z", "water_bed_z", "water_surf0_z", "water_sys", "current", "block", "cover_sight", "cover_body", "canopy",
          "food_amount", "food_cap", "food_regen", "food_dry")


@dataclass
class WaterCycle:
    """수위 오프셋(m) = amp × 주기 모양 + 비 오름. 언리얼 EcoVegetationField 의 오름·높음·내림·낮음 꼴."""

    amp_m: float = 0.0
    rise_s: float = 30.0
    high_s: float = 20.0
    fall_s: float = 45.0
    low_s: float = 40.0
    phase_s: float = 0.0
    rain_rise_m: float = 0.0

    def offset(self, t_s: float, rain: float = 0.0) -> float:
        period = self.rise_s + self.high_s + self.fall_s + self.low_s
        if self.amp_m <= 0.0 or period <= 0.0:
            return self.rain_rise_m * rain
        u = (t_s + self.phase_s) % period
        if u < self.rise_s:
            f = u / self.rise_s
        elif u < self.rise_s + self.high_s:
            f = 1.0
        elif u < self.rise_s + self.high_s + self.fall_s:
            f = 1.0 - (u - self.rise_s - self.high_s) / self.fall_s
        else:
            f = 0.0
        return self.amp_m * (f - 0.5) + self.rain_rise_m * rain


@dataclass
class MapCard:
    cell_m: float
    ground_z: np.ndarray
    water_bed_z: np.ndarray
    water_surf0_z: np.ndarray
    water_sys: np.ndarray
    current: np.ndarray
    block: np.ndarray
    cover_sight: np.ndarray
    cover_body: np.ndarray
    canopy: np.ndarray
    food_amount: np.ndarray
    food_cap: np.ndarray
    food_regen: np.ndarray
    food_dry: np.ndarray
    water: WaterCycle = field(default_factory=WaterCycle)
    meta: dict = field(default_factory=dict)

    @property
    def h(self) -> int:
        return int(self.ground_z.shape[0])

    @property
    def w(self) -> int:
        return int(self.ground_z.shape[1])

    @property
    def size_m(self) -> tuple[float, float]:
        return self.w * self.cell_m, self.h * self.cell_m

    def check(self) -> None:
        h, w = self.h, self.w
        nf = len(FOOD_KINDS)
        want = {"ground_z": (h, w), "water_bed_z": (h, w), "water_surf0_z": (h, w), "water_sys": (h, w), "current": (h, w, 2),
                "block": (h, w), "cover_sight": (h, w), "cover_body": (h, w), "canopy": (h, w), "food_amount": (nf, h, w),
                "food_cap": (nf, h, w), "food_regen": (nf, h, w), "food_dry": (nf, h, w)}
        for k, shp in want.items():
            a = getattr(self, k)
            if a.shape != shp:
                raise ValueError(f"map layer {k} shape {a.shape} != {shp}")
            if not np.all(np.isfinite(a)):
                raise ValueError(f"map layer {k} has non-finite values")
        if np.any(self.food_amount > self.food_cap + 1e-6) or np.any(self.food_cap < 0):
            raise ValueError("food amount must be in [0, cap]")
        if np.any(self.water_sys.astype(bool) & (self.water_bed_z > self.ground_z + 1e-4)):
            raise ValueError("water bed above ground")

    # ------------------------------------------------------------------ 질의 (벡터)

    def cell(self, x, y) -> tuple[np.ndarray, np.ndarray]:
        ix = np.clip(np.floor(np.asarray(x) / self.cell_m).astype(np.int64), 0, self.w - 1)
        iy = np.clip(np.floor(np.asarray(y) / self.cell_m).astype(np.int64), 0, self.h - 1)
        return ix, iy

    def inside(self, x, y) -> np.ndarray:
        x = np.asarray(x)
        y = np.asarray(y)
        return (x >= 0) & (y >= 0) & (x < self.w * self.cell_m) & (y < self.h * self.cell_m)

    def height(self, x, y) -> np.ndarray:
        ix, iy = self.cell(x, y)
        return self.ground_z[iy, ix]

    def surface(self, x, y, level: float) -> np.ndarray:
        """수면 높이(물이 없으면 바닥보다 낮은 값 — depth 0)."""
        ix, iy = self.cell(x, y)
        surf = self.water_surf0_z[iy, ix] + level
        return np.where(self.water_sys[iy, ix] > 0, surf, self.ground_z[iy, ix] - 1.0)

    def depth(self, x, y, level: float) -> np.ndarray:
        ix, iy = self.cell(x, y)
        d = self.water_surf0_z[iy, ix] + level - self.water_bed_z[iy, ix]
        return np.where(self.water_sys[iy, ix] > 0, np.maximum(d, 0.0), 0.0)

    def current_at(self, x, y) -> np.ndarray:
        ix, iy = self.cell(x, y)
        return self.current[iy, ix]

    # ------------------------------------------------------------------ 저장

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        arrays = {k: getattr(self, k) for k in LAYERS}
        head = {"format": CARD_FORMAT, "version": CARD_VERSION, "cell_m": self.cell_m, "w": self.w, "h": self.h,
                "food_kinds": list(FOOD_KINDS), "water": self.water.__dict__, "meta": self.meta}
        arrays["head_json"] = np.array(json.dumps(head, sort_keys=True, ensure_ascii=True))
        with open(p, "wb") as fh:
            np.savez_compressed(fh, **arrays)


def load_map(path: str | Path) -> MapCard:
    with np.load(Path(path), allow_pickle=False) as z:
        head = json.loads(str(z["head_json"][()]))
        if head.get("format") != CARD_FORMAT or int(head.get("version", -1)) != CARD_VERSION:
            raise ValueError(f"{path}: not a {CARD_FORMAT} v{CARD_VERSION} card")
        if list(head["food_kinds"]) != list(FOOD_KINDS):
            raise ValueError(f"{path}: food kinds {head['food_kinds']} != {list(FOOD_KINDS)}")
        arrays = {k: np.array(z[k]) for k in LAYERS}
    m = MapCard(cell_m=float(head["cell_m"]), water=WaterCycle(**head["water"]), meta=head.get("meta", {}), **arrays)
    m.check()
    return m


def blank_map(w: int, h: int, cell_m: float = 1.0) -> MapCard:
    """평평하고 물·막힘·먹이 없는 맵 (시험·작은 확인의 바탕)."""
    nf = len(FOOD_KINDS)
    z2 = np.zeros((h, w), np.float32)
    return MapCard(cell_m=cell_m, ground_z=z2.copy(), water_bed_z=z2.copy(), water_surf0_z=z2 - 1.0,
                   water_sys=np.zeros((h, w), np.uint8), current=np.zeros((h, w, 2), np.float32),
                   block=np.zeros((h, w), np.uint8), cover_sight=z2.copy(), cover_body=np.zeros((h, w), np.uint8),
                   canopy=np.zeros((h, w), np.uint8), food_amount=np.zeros((nf, h, w), np.float32),
                   food_cap=np.zeros((nf, h, w), np.float32), food_regen=np.zeros((nf, h, w), np.float32),
                   food_dry=np.zeros((nf, h, w), np.float32))


def rotate_xy(x, y, k: int, w_m: float, h_m: float):
    """rotate90(m, k) 를 한 맵에서 점 (x, y) 가 가는 자리. np.rot90(axes=(0, 1)) 한 번 = (x, y) → (y, W − x) — 시계 90°."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    for _ in range(k % 4):
        x, y = y, w_m - x
        w_m, h_m = h_m, w_m
    return x, y


def rotate_vec(vx, vy, k: int):
    """rotate90 한 번마다 벡터 (vx, vy) → (vy, −vx)."""
    for _ in range(k % 4):
        vx, vy = vy, -np.asarray(vx)
    return vx, vy


def rotate90(m: MapCard, k: int = 1) -> MapCard:
    """맵을 np.rot90(axes=(0, 1)) 로 k 번 돌린다 (회전 불변 시험용). 점은 rotate_xy, 물살 벡터는 rotate_vec 로 같이 돈다."""
    k %= 4
    rot = lambda a: np.ascontiguousarray(np.rot90(a, k, axes=(-2, -1)) if a.ndim == 3 and a.shape[0] == len(FOOD_KINDS)
                                         else np.rot90(a, k, axes=(0, 1)))
    cur = np.rot90(m.current, k, axes=(0, 1)).copy()
    ang = -math.pi / 2 * k
    c, s = math.cos(ang), math.sin(ang)
    cur = np.stack([c * cur[..., 0] - s * cur[..., 1], s * cur[..., 0] + c * cur[..., 1]], axis=-1).astype(np.float32)
    return MapCard(cell_m=m.cell_m, ground_z=rot(m.ground_z), water_bed_z=rot(m.water_bed_z), water_surf0_z=rot(m.water_surf0_z),
                   water_sys=rot(m.water_sys), current=cur, block=rot(m.block), cover_sight=rot(m.cover_sight),
                   cover_body=rot(m.cover_body), canopy=rot(m.canopy), food_amount=rot(m.food_amount), food_cap=rot(m.food_cap),
                   food_regen=rot(m.food_regen), food_dry=rot(m.food_dry), water=m.water, meta=dict(m.meta, rotated=k))
