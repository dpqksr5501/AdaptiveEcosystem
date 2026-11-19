"""R10 맵 무작위 생성기 (0 단계 사양 6 절). numpy 만 쓴다(클라우드 설치 목록에 scipy 없음).

make_map(seed, purpose) — 같은 시드면 바이트까지 같은 맵. 시드 범위(사양 6 절):
  학습 50000~59999 · 점검 60000~60999 · 시험(처음 보는 맵) 61000~61999 — purpose 와 다른 범위는 거부한다.
층 차례: 크기 → 높이(모양 + 노이즈) → 물(없음·개울·강·호수·습지) → 막힘·가림·은신처·나무 → 먹이 군락 → 수위 주기.
"""

from __future__ import annotations

import math

import numpy as np

from r10 import terrain as T

SEED_RANGES = {"train": (50000, 60000), "check": (60000, 61000), "test": (61000, 62000), "unit": (0, 50000)}

# 범위 (사양 6 절). 값을 바꾸면 '학습 때 섞은 범위'가 바뀐다 — 팩 manifest 에 이 표를 적는다.
RANGES = {
    "size_m": (60, 200),
    "shape": {"flat": 0.30, "hills": 0.30, "plateau": 0.20, "valley": 0.20},
    "relief_m": {"flat": (0.0, 1.0), "hills": (2.0, 10.0), "plateau": (1.0, 4.0), "valley": (3.0, 12.0)},
    "cliff_m": (1.5, 8.0),
    "water": {"none": 0.20, "stream": 0.25, "river": 0.25, "lake": 0.15, "wetland": 0.15},
    "stream_width_m": (1.0, 4.0), "river_width_m": (4.0, 15.0), "river_depth_m": (0.5, 3.0), "current_mps": (0.0, 0.6),
    "lake_depth_m": (0.8, 4.0), "wetland_depth_m": (0.1, 0.4),
    "water_amp_m": (0.0, 0.8), "rain_rise_m": (0.0, 0.4),
    "tree_density": (0.0, 0.04), "rock_density": (0.0, 0.01), "bush_cover": (0.0, 0.40), "shelters": (0, 8),
    "food_abundance": (0.5, 2.0),
}
AQUATIC_FLOOR = 0.3   # 11-19: 물 바닥 조류·작은 동물은 물 전체에 얇게 깔린다 (군락만 두면 큰 물의 82~84 % 가 먹이 없음 → 물고기가 갇혀 굶음)
FOOD_BASE = {   # 셀당 용량(단위)·재생/s 의 바탕 (먹이 양 단위는 종 카드 energy_per_unit 와 짝)
    "grass": (1.0, 0.0020), "forbs": (0.8, 0.0015), "browse": (1.2, 0.0010), "wet_meadow": (1.2, 0.0025),
    "roots": (0.6, 0.0008), "insects": (0.3, 0.0030), "aquatic": (0.8, 0.0020), "drift": (0.4, 0.0040),
}


def check_seed(seed: int, purpose: str) -> None:
    lo, hi = SEED_RANGES[purpose]
    if not lo <= int(seed) < hi:
        raise ValueError(f"seed {seed} is outside the {purpose} range [{lo}, {hi}) — test seeds are locked (사양 6 절)")
    if purpose != "test" and SEED_RANGES["test"][0] <= int(seed) < SEED_RANGES["test"][1]:
        raise ValueError("test map seeds are only for evaluation")


def _pick(rng: np.random.Generator, table: dict) -> str:
    keys = list(table)
    p = np.array([table[k] for k in keys], dtype=np.float64)
    return keys[int(rng.choice(len(keys), p=p / p.sum()))]


def _u(rng, lo_hi) -> float:
    return float(rng.uniform(lo_hi[0], lo_hi[1]))


def _upsample(g: np.ndarray, h: int, w: int) -> np.ndarray:
    """거친 격자 g 를 (h, w) 로 쌍선형 보간."""
    gh, gw = g.shape
    ys = np.linspace(0, gh - 1, h)
    xs = np.linspace(0, gw - 1, w)
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    y1 = np.minimum(y0 + 1, gh - 1)
    x1 = np.minimum(x0 + 1, gw - 1)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    a = g[y0][:, x0] * (1 - fx) + g[y0][:, x1] * fx
    b = g[y1][:, x0] * (1 - fx) + g[y1][:, x1] * fx
    return a * (1 - fy) + b * fy


def noise(rng, h: int, w: int, octaves: int = 4, base_cells: float = 40.0) -> np.ndarray:
    """값 노이즈 여러 겹 → 대략 [-1, 1]."""
    out = np.zeros((h, w))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        cells = base_cells / (2 ** o)
        gh = max(2, int(math.ceil(h / cells)) + 1)
        gw = max(2, int(math.ceil(w / cells)) + 1)
        out += amp * _upsample(rng.uniform(-1, 1, (gh, gw)), h, w)
        tot += amp
        amp *= 0.5
    return out / tot


def blur(a: np.ndarray, r: int) -> np.ndarray:
    """상자 흐림 (반지름 r 셀, 가장자리는 늘림)."""
    if r <= 0:
        return a.copy()
    p = np.pad(a, r, mode="edge")
    c = np.cumsum(np.cumsum(p, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    k = 2 * r + 1
    h, w = a.shape
    s = c[k:k + h, k:k + w] - c[0:h, k:k + w] - c[k:k + h, 0:w] + c[0:h, 0:w]
    return s / (k * k)


def _dist_to_polyline(px: np.ndarray, py: np.ndarray, h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
    """각 셀 중심에서 꺾은선까지 거리와 가장 가까운 점의 접선 각."""
    yy, xx = np.mgrid[0:h, 0:w]
    cx = xx.ravel() + 0.5
    cy = yy.ravel() + 0.5
    best = np.full(cx.shape, np.inf)
    ang = np.zeros(cx.shape)
    tang = np.arctan2(np.gradient(py), np.gradient(px))
    for i in range(0, len(px), 64):
        sx = px[i:i + 64][None, :]
        sy = py[i:i + 64][None, :]
        d = np.hypot(cx[:, None] - sx, cy[:, None] - sy)
        j = np.argmin(d, axis=1)
        dm = d[np.arange(len(cx)), j]
        better = dm < best
        best = np.where(better, dm, best)
        ang = np.where(better, tang[i:i + 64][j], ang)
    return best.reshape(h, w), ang.reshape(h, w)


def _channel(rng, h, w, width_m, depth_m, cur_mps):
    """한쪽 가장자리에서 다른 쪽으로 굽이치는 물길: (물 깊이 모양 0~1, 물살 x·y)."""
    horizontal = rng.random() < 0.5
    n = 400
    t = np.linspace(0, 1, n)
    wig = sum(rng.uniform(0.03, 0.12) * np.sin(2 * math.pi * (f * t + rng.random())) for f in (1, 2, 3))
    if horizontal:
        px, py = t * w, (rng.uniform(0.25, 0.75) + wig) * h
    else:
        px, py = (rng.uniform(0.25, 0.75) + wig) * w, t * h
    if rng.random() < 0.5:
        px, py = px[::-1], py[::-1]
    d, ang = _dist_to_polyline(px, py, h, w)
    half = width_m / 2.0
    prof = np.clip(1.0 - (d / half) ** 2, 0.0, 1.0)
    cur = np.zeros((h, w, 2))
    cur[..., 0] = np.cos(ang) * cur_mps * prof
    cur[..., 1] = np.sin(ang) * cur_mps * prof
    return prof * depth_m, cur, d


def make_map(seed: int, purpose: str = "train", overrides: dict | None = None) -> T.MapCard:
    check_seed(seed, purpose)
    rng = np.random.default_rng([int(seed), 0x5210])
    o = overrides or {}
    w = int(o.get("w", rng.integers(RANGES["size_m"][0], RANGES["size_m"][1] + 1)))
    h = int(o.get("h", rng.integers(RANGES["size_m"][0], RANGES["size_m"][1] + 1)))
    shape = o.get("shape", _pick(rng, RANGES["shape"]))
    water_kind = o.get("water", _pick(rng, RANGES["water"]))

    # 높이
    relief = _u(rng, RANGES["relief_m"][shape])
    z = noise(rng, h, w, 4, 50.0) * relief
    if shape == "plateau":
        edge = noise(rng, h, w, 2, 80.0)
        cliff = _u(rng, RANGES["cliff_m"])
        z += cliff * np.clip((edge - rng.uniform(-0.2, 0.2)) * 6.0, 0.0, 1.0)
    elif shape == "valley":
        yy, xx = np.mgrid[0:h, 0:w]
        axis = (xx / w - 0.5) if rng.random() < 0.5 else (yy / h - 0.5)
        z += relief * 4.0 * axis ** 2
    z = blur(z, 1)

    # 물
    bed = z.copy()
    surf0 = z - 1.0
    sys_ = np.zeros((h, w), np.uint8)
    cur = np.zeros((h, w, 2))
    if water_kind in ("stream", "river"):
        width = _u(rng, RANGES["stream_width_m" if water_kind == "stream" else "river_width_m"])
        depth = 0.3 if water_kind == "stream" else _u(rng, RANGES["river_depth_m"])
        prof_d, cur, dist = _channel(rng, h, w, width, depth, _u(rng, RANGES["current_mps"]))
        bank = blur(z, 4)
        wet = prof_d > 0
        z = np.where(dist < width, np.minimum(z, bank + 0.2 * (dist / width)), z)     # 둑을 물 높이 쪽으로 낮춤
        surf0 = np.where(wet, bank - 0.05, surf0)
        bed = np.where(wet, bank - 0.05 - prof_d, z)
        sys_ = wet.astype(np.uint8)
    elif water_kind == "lake":
        blob = noise(rng, h, w, 3, 60.0)
        yy, xx = np.mgrid[0:h, 0:w]
        c = (rng.uniform(0.3, 0.7) * w, rng.uniform(0.3, 0.7) * h)
        r = rng.uniform(0.12, 0.3) * min(w, h)
        inside = (np.hypot(xx - c[0], yy - c[1]) / r + 0.8 * blob) < 1.0
        if inside.any():
            level = float(np.percentile(z[inside], 30))
            depth = _u(rng, RANGES["lake_depth_m"])
            shape_d = np.clip(1.0 - np.hypot(xx - c[0], yy - c[1]) / r, 0.0, 1.0)
            bed = np.where(inside, np.minimum(z, level - depth * shape_d), z)
            surf0 = np.where(inside, level, surf0)
            sys_ = inside.astype(np.uint8)
            z = np.where(inside, bed, z)
    elif water_kind == "wetland":
        patch = noise(rng, h, w, 3, 30.0) > rng.uniform(0.15, 0.4)
        depth = _u(rng, RANGES["wetland_depth_m"])
        flat = blur(z, 3)
        bed = np.where(patch, flat - depth, z)
        surf0 = np.where(patch, flat, surf0)
        sys_ = patch.astype(np.uint8)
        z = np.where(patch, bed, z)
    z = np.where(sys_ > 0, bed, z)
    water_any = sys_ > 0

    # 막힘·가림·은신처·나무
    block = np.zeros((h, w), np.uint8)
    canopy = np.zeros((h, w), np.uint8)
    land = ~water_any
    n_cells = h * w
    trees = rng.random((h, w)) < _u(rng, RANGES["tree_density"]) * blur((noise(rng, h, w, 2, 40) > 0).astype(float), 3) * 2
    trees &= land
    block |= trees.astype(np.uint8)
    canopy |= (blur(trees.astype(float), 2) > 0.02).astype(np.uint8)
    rocks = (rng.random((h, w)) < _u(rng, RANGES["rock_density"])) & land
    rocks = blur(rocks.astype(float), 1) > 0.05
    block |= (rocks & land).astype(np.uint8)
    bush = np.clip((noise(rng, h, w, 3, 25.0) + 1) / 2 - (1 - _u(rng, RANGES["bush_cover"])), 0, 1) * 2.5
    cover_sight = np.clip(bush + 0.8 * canopy + 1.0 * rocks, 0, 1) * land
    cover_body = np.zeros((h, w), np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(int(rng.integers(RANGES["shelters"][0], RANGES["shelters"][1] + 1))):
        cx, cy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(3.0, 7.0)
        cover_body |= ((np.hypot(xx + 0.5 - cx, yy + 0.5 - cy) < r) & land).astype(np.uint8)
    cover_sight = np.maximum(cover_sight, 0.7 * cover_body)

    # 먹이 군락
    nf = len(T.FOOD_KINDS)
    cap = np.zeros((nf, h, w))
    regen = np.zeros((nf, h, w))
    abund = _u(rng, RANGES["food_abundance"])
    near_water = blur(water_any.astype(float), 3) > 0.05
    shade = blur(canopy.astype(float), 3)
    for i, kind in enumerate(T.FOOD_KINDS):
        base_cap, base_regen = FOOD_BASE[kind]
        patch = np.clip(noise(rng, h, w, 3, rng.uniform(15, 40)) - rng.uniform(-0.1, 0.3), 0, 1) * 2
        where = {"grass": land & (shade < 0.3), "forbs": land, "browse": land & (shade > 0.05),
                 "wet_meadow": land & near_water, "roots": land, "insects": np.ones_like(land),
                 "aquatic": water_any, "drift": water_any & (np.hypot(cur[..., 0], cur[..., 1]) > 0.05)}[kind]
        dens = np.clip(patch, 0, 1)
        if kind == "aquatic":
            dens = np.maximum(dens, AQUATIC_FLOOR)
        cap[i] = dens * base_cap * abund * where * (1 - block)
        regen[i] = (cap[i] > 0) * base_regen * abund * rng.uniform(0.6, 1.4)
    amount = cap * rng.uniform(0.3, 1.0)
    dry = regen * rng.uniform(0.0, 0.3)

    water = T.WaterCycle(amp_m=_u(rng, RANGES["water_amp_m"]) if water_any.any() else 0.0,
                         rise_s=rng.uniform(20, 60), high_s=rng.uniform(10, 40), fall_s=rng.uniform(30, 80),
                         low_s=rng.uniform(20, 60), phase_s=rng.uniform(0, 200), rain_rise_m=_u(rng, RANGES["rain_rise_m"]))
    m = T.MapCard(cell_m=1.0, ground_z=z.astype(np.float32), water_bed_z=bed.astype(np.float32),
                  water_surf0_z=surf0.astype(np.float32), water_sys=sys_, current=cur.astype(np.float32), block=block,
                  cover_sight=cover_sight.astype(np.float32), cover_body=cover_body, canopy=canopy,
                  food_amount=amount.astype(np.float32), food_cap=cap.astype(np.float32), food_regen=regen.astype(np.float32),
                  food_dry=dry.astype(np.float32), water=water,
                  meta={"generator": "r10.mapgen", "seed": int(seed), "purpose": purpose, "shape": shape, "water": water_kind,
                        "relief_m": relief, "food_abundance": abund, "cells": n_cells})
    m.check()
    return m
