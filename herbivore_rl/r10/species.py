"""R10 종 카드 — 몸 숫자 한 곳 (0 단계 사양 3 절).

- 파일: herbivore_rl/species/<id>.json (SI: m·kg·s·°). 파이썬 학습 세계와 언리얼이 같은 파일을 읽는다.
- 값 기준: 언리얼이 실제로 실행하는 값. 출처는 카드의 "sources" 에 칸마다 적는다(없는 값을 정했으면 '정함: 까닭').
- 몸 벡터 18 칸(감각 S1 의 body 묶음)과 학습 흔들기·'배운 범위' 표, 이름 모를 동물 카드를 만든다.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np

from r10 import contract as C

ROOT = Path(__file__).resolve().parents[1]
SPECIES_DIR = ROOT / "species"
CARD_VERSION = 1
DIET_KEYS = ("grass", "forbs", "browse", "wet_meadow", "roots", "insects", "aquatic", "drift", "meat", "carrion")
PLANT_DIET = ("grass", "forbs", "browse", "wet_meadow", "roots")
WATER_DIET = ("insects", "aquatic", "drift")
MEAT_DIET = ("meat", "carrion")

# (그룹, 칸): (최소, 최대, 비워도 되나) — 비워도 되는 칸은 매체에 따라 필요 없을 때만 (아래 _need)
FIELDS = {
    ("medium", "ground"): (None, None, False), ("medium", "swim"): (None, None, False), ("medium", "fly"): (None, None, False),
    ("medium", "needs_water"): (None, None, False), ("medium", "wade_depth_m"): (0.0, 3.0, False),
    ("medium", "swim_depth_frac"): (0.0, 1.0, True), ("medium", "cruise_height_m"): (0.5, 200.0, True),
    ("medium", "ceiling_m"): (1.0, 500.0, True), ("medium", "takeoff_s"): (0.05, 10.0, True),
    ("body", "mass_kg"): (0.01, 2000.0, False), ("body", "radius_m"): (0.01, 3.0, False),
    ("body", "walk_mps"): (0.0, 10.0, False), ("body", "run_mps"): (0.0, 30.0, False),
    ("body", "swim_mps"): (0.0, 10.0, True), ("body", "swim_fast_mps"): (0.0, 15.0, True),
    ("body", "fly_mps"): (0.0, 40.0, True), ("body", "cruise_mps"): (0.0, 60.0, True), ("body", "dive_mps"): (0.0, 90.0, True),
    ("body", "accel_mps2"): (0.1, 50.0, False), ("body", "turn_dps"): (10.0, 2000.0, False),
    ("body", "lat_accel_mps2"): (0.1, 50.0, False), ("body", "max_slope_deg"): (5.0, 89.0, False),
    ("body", "step_m"): (0.0, 2.0, False), ("body", "stamina_s"): (1.0, 3600.0, False),
    ("body", "stamina_recover_s"): (1.0, 3600.0, False),
    # 덮치기 (잠깐 매우 빠르게, 뒤에 지침) — 없으면 넷 다 null. 언리얼 Native 늑대 pounce 값 (EcoThreatModel.h:205-208)
    ("body", "burst_mps"): (0.0, 60.0, True), ("body", "burst_s"): (0.1, 30.0, True),
    ("body", "burst_exhaust_mps"): (0.0, 30.0, True), ("body", "burst_exhaust_s"): (0.0, 120.0, True),
    ("senses", "sight_m"): (0.05, 200.0, False), ("senses", "fov_deg"): (30.0, 360.0, False),
    ("senses", "smell_m"): (0.0, 200.0, False), ("senses", "hearing_m"): (0.0, 300.0, False),
    ("senses", "night_vision"): (0.0, 1.0, False),
    ("eat", "rate_per_s"): (0.0, 10.0, False), ("eat", "energy_per_unit"): (0.0, 100.0, False),
    ("metabolism", "drain_per_day"): (0.0, 10.0, False), ("metabolism", "reserve_days"): (0.0, 60.0, False),
    ("metabolism", "run_cost"): (1.0, 20.0, False), ("metabolism", "swim_cost"): (1.0, 20.0, True),
    ("metabolism", "fly_cost"): (1.0, 20.0, True),
    ("combat", "kill_mass_ratio"): (0.0, 20.0, False), ("combat", "reach_m"): (0.0, 5.0, False),
    ("combat", "attack_cd_s"): (0.0, 60.0, False), ("combat", "defense"): (0.0, 100.0, False),
    ("combat", "counter_reach_m"): (0.0, 5.0, False),
    ("life", "maturity_days"): (0.1, 3650.0, False), ("life", "litter"): (1.0, 2000.0, False),
    ("life", "gestation_days"): (0.0, 400.0, False),
}
RANDOMIZE_DEFAULT_KEYS = ("body.mass_kg", "body.radius_m", "body.walk_mps", "body.run_mps", "body.swim_mps", "body.fly_mps",
                          "body.cruise_mps", "body.accel_mps2", "body.turn_dps", "senses.sight_m", "eat.rate_per_s",
                          "metabolism.drain_per_day", "body.burst_mps")


def _need(card: dict, group: str, key: str) -> bool:
    """매체에 따라 꼭 있어야 하는 칸."""
    m = card.get("medium", {})
    if key == "burst_mps":
        return False
    if key in ("burst_s", "burst_exhaust_mps", "burst_exhaust_s"):
        return card.get("body", {}).get("burst_mps") is not None
    if key in ("swim_mps", "swim_fast_mps", "swim_depth_frac", "swim_cost"):
        return bool(m.get("swim"))
    if key in ("fly_mps", "cruise_mps", "dive_mps", "cruise_height_m", "ceiling_m", "takeoff_s", "fly_cost"):
        return bool(m.get("fly"))
    return True


def validate(card: dict) -> list[str]:
    """문제 목록 (비어 있으면 통과)."""
    bad = []
    if card.get("card_version") != CARD_VERSION:
        bad.append(f"card_version {card.get('card_version')} != {CARD_VERSION}")
    if not isinstance(card.get("id"), str) or not card["id"]:
        bad.append("id missing")
    for (g, k), (lo, hi, nullable) in FIELDS.items():
        v = card.get(g, {}).get(k, "<missing>")
        if v == "<missing>":
            bad.append(f"{g}.{k} missing")
            continue
        if v is None:
            if _need(card, g, k):
                bad.append(f"{g}.{k} is null but this body needs it")
            continue
        if lo is None:
            if not isinstance(v, bool):
                bad.append(f"{g}.{k} must be true/false")
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or not lo <= v <= hi:
            bad.append(f"{g}.{k} = {v!r} outside [{lo}, {hi}]")
    diet = card.get("diet", {})
    for k in DIET_KEYS:
        v = diet.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
            bad.append(f"diet.{k} must be ≥ 0")
    if not any((diet.get(k) or 0) > 0 for k in DIET_KEYS):
        bad.append("diet: nothing to eat")
    m = card.get("medium", {})
    if not (m.get("ground") or m.get("swim") or m.get("fly")):
        bad.append("medium: no way to move")
    if m.get("needs_water") and not m.get("swim"):
        bad.append("medium: needs_water without swim")
    b = card.get("body", {})
    if isinstance(b.get("walk_mps"), (int, float)) and isinstance(b.get("run_mps"), (int, float)) and b["run_mps"] < b["walk_mps"]:
        bad.append("body: run_mps < walk_mps")
    if isinstance(b.get("burst_mps"), (int, float)) and isinstance(b.get("run_mps"), (int, float)) and b["burst_mps"] < b["run_mps"]:
        bad.append("body: burst_mps < run_mps")
    if (card.get("combat", {}).get("kill_mass_ratio") or 0) > 0 and (diet.get("meat") or 0) <= 0:
        bad.append("combat: can kill but does not eat meat")
    for key in card.get("randomize", {}).get("keys", []):
        g, _, k = key.partition(".")
        if (g, k) not in FIELDS:
            bad.append(f"randomize key {key} unknown")
    return bad


def load_card(path: str | Path) -> dict:
    card = json.loads(Path(path).read_text(encoding="utf-8"))
    bad = validate(card)
    if bad:
        raise ValueError(f"{path}: " + "; ".join(bad))
    return card


def load_all(folder: str | Path = SPECIES_DIR) -> dict[str, dict]:
    out = {}
    for p in sorted(Path(folder).glob("*.json")):
        c = load_card(p)
        if c["id"] != p.stem:
            raise ValueError(f"{p}: id {c['id']!r} != file name")
        out[c["id"]] = c
    return out


def _v(card, g, k, default=0.0) -> float:
    v = card.get(g, {}).get(k)
    return float(default if v is None else v)


def body_vector(card: dict) -> np.ndarray:
    """감각 S1 body 묶음 18 칸 (0~1). 이름 차례는 contract.BODY_NAMES."""
    m = card["medium"]
    d = card["diet"]
    tot = sum(float(d[k]) for k in DIET_KEYS) or 1.0
    v = [
        np.clip((math.log10(_v(card, "body", "mass_kg")) + 2.0) / 5.0, 0, 1),            # 0.01 ~ 1000 kg
        np.clip((math.log10(_v(card, "body", "radius_m")) + 2.0) / 2.5, 0, 1),           # 1 cm ~ 3 m
        C.lg(_v(card, "body", "walk_mps"), 1.0, 25.0),
        C.lg(_v(card, "body", "run_mps"), 1.0, 25.0),
        float(bool(m["swim"])),
        C.lg(_v(card, "body", "swim_fast_mps", _v(card, "body", "swim_mps")), 1.0, 25.0),
        float(bool(m["fly"])),
        C.lg(_v(card, "medium", "cruise_height_m"), 2.0, 200.0),
        C.lg(_v(card, "medium", "wade_depth_m"), 0.1, 3.0),
        _v(card, "body", "max_slope_deg") / 90.0,
        C.lg(_v(card, "body", "turn_dps"), 30.0, 2000.0),
        C.lg(_v(card, "senses", "sight_m"), 2.0, 200.0),
        _v(card, "senses", "fov_deg") / 360.0,
        sum(float(d[k]) for k in PLANT_DIET) / tot,
        sum(float(d[k]) for k in WATER_DIET) / tot,
        sum(float(d[k]) for k in MEAT_DIET) / tot,
        np.clip(_v(card, "combat", "kill_mass_ratio") / 4.0, 0, 1),                      # 물 수 있는 몸무게 비 (0 ~ 4 배)
        C.lg(_v(card, "body", "burst_mps"), 1.0, 25.0),                                  # 덮치기 속력 (0 = 없음)
    ]
    out = np.asarray([float(x) for x in v], dtype=np.float32)
    assert out.shape == (len(C.BODY_NAMES),)
    return out


def trained_range(card: dict) -> dict:
    """흔들기 범위 표 {"group.key": [하한, 상한]} — 팩 manifest 에 적고 언리얼 값과 대조한다(설계 11 절)."""
    frac = float(card.get("randomize", {}).get("frac", 0.15))
    out = {}
    for key in card.get("randomize", {}).get("keys", RANDOMIZE_DEFAULT_KEYS):
        g, _, k = key.partition(".")
        v = card.get(g, {}).get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = [v * (1 - frac), v * (1 + frac)]
    return out


def jitter(card: dict, rng: np.random.Generator) -> dict:
    """학습 세계 하나의 몸: randomize.keys 를 곱 U[1 − frac, 1 + frac] 로 흔든다 (같은 rng 차례면 같은 결과)."""
    c = copy.deepcopy(card)
    for key, (lo, hi) in trained_range(card).items():
        g, _, k = key.partition(".")
        c[g][k] = float(rng.uniform(lo, hi))
    b = c["body"]
    b["run_mps"] = max(b["run_mps"], b["walk_mps"])
    if b.get("burst_mps") is not None:
        b["burst_mps"] = max(b["burst_mps"], b["run_mps"])
    return c


def random_card(rng: np.random.Generator, idx: int = 0) -> dict:
    """'이름 모를 동물' (사양 3 절): 질량 log-균등 0.1~500 kg, 크기 법칙 어림 ±30%, 매체 땅 80%·물 10%·하늘 10%."""
    mass = float(10 ** rng.uniform(-1.0, math.log10(500.0)))
    j = lambda: float(rng.uniform(0.7, 1.3))
    medium_kind = rng.choice(["ground", "water", "air"], p=[0.8, 0.1, 0.1])
    radius = 0.12 * mass ** (1 / 3) * j()
    run = 3.0 * mass ** 0.17 * j()
    diet = {k: 0.0 for k in DIET_KEYS}
    eats = rng.choice(["plant", "omni", "meat"], p=[0.5, 0.25, 0.25])
    if eats in ("plant", "omni"):
        for k in ("grass", "forbs", "browse"):
            diet[k] = float(rng.uniform(0.5, 1.5))
    if eats in ("meat", "omni"):
        diet["meat"] = float(rng.uniform(0.5, 1.5))
        diet["carrion"] = float(rng.uniform(0.2, 1.0))
    if medium_kind == "water":
        diet.update(aquatic=1.0, insects=0.5, drift=0.5)
    burst = medium_kind == "ground" and diet["meat"] > 0 and rng.random() < 0.4     # 땅 사냥꾼 가운데 덮치는 몸
    card = {
        "id": f"unknown_{idx}", "name_ko": "이름 모를 동물", "card_version": CARD_VERSION,
        "medium": {"ground": medium_kind != "water", "swim": medium_kind == "water", "fly": medium_kind == "air",
                   "needs_water": medium_kind == "water", "wade_depth_m": 0.3 * radius, "swim_depth_frac": 0.5 if medium_kind == "water" else None,
                   "cruise_height_m": 15.0 * j() if medium_kind == "air" else None, "ceiling_m": 40.0 if medium_kind == "air" else None,
                   "takeoff_s": 0.6 if medium_kind == "air" else None},
        "body": {"mass_kg": mass, "radius_m": radius, "walk_mps": 0.35 * run, "run_mps": run,
                 "swim_mps": 0.4 * run if medium_kind == "water" else None, "swim_fast_mps": run if medium_kind == "water" else None,
                 "fly_mps": 2.0 * run if medium_kind == "air" else None, "cruise_mps": 3.5 * run if medium_kind == "air" else None,
                 "dive_mps": 6.0 * run if medium_kind == "air" else None, "accel_mps2": 4.0 * j(), "turn_dps": 200.0 * j(),
                 "lat_accel_mps2": 8.0 * j(), "max_slope_deg": 35.0 * j(), "step_m": 0.4 * radius, "stamina_s": 30.0 * j(),
                 "stamina_recover_s": 60.0 * j(),
                 "burst_mps": 1.9 * run * j() if burst else None, "burst_s": 1.6 * j() if burst else None,
                 "burst_exhaust_mps": 0.25 * run if burst else None, "burst_exhaust_s": 4.0 * j() if burst else None},
        "senses": {"sight_m": 15.0 * j(), "fov_deg": 270.0, "smell_m": 8.0 * j(), "hearing_m": 20.0 * j(), "night_vision": float(rng.uniform(0, 1))},
        "diet": diet,
        "eat": {"rate_per_s": 0.02 * j(), "energy_per_unit": 0.5 * j()},
        "metabolism": {"drain_per_day": 0.6 * mass ** -0.25 * j(), "reserve_days": (8.0 if eats == "meat" else 3.0) * j(), "run_cost": 3.0,
                       "swim_cost": 1.0 if medium_kind == "water" else None, "fly_cost": 1.5 if medium_kind == "air" else None},
        "combat": {"kill_mass_ratio": float(rng.uniform(0.3, 1.6)) if diet["meat"] > 0 else 0.0, "reach_m": 1.5 * radius,
                   "attack_cd_s": 2.0, "defense": float(rng.uniform(0, 30)), "counter_reach_m": 1.2 * radius},
        "life": {"maturity_days": 30.0, "litter": 1.0, "gestation_days": 10.0},
        "randomize": {"frac": 0.0, "keys": []},
        "sources": {"*": "r10.species.random_card (사양 3 절 크기 법칙 어림)"},
    }
    bad = validate(card)
    assert not bad, bad
    return card
