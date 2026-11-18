"""R10 종 카드 만들기 — 출처 초안(card_sources/*.json)을 종 카드(herbivore_rl/species/<id>.json)로 (0 단계 사양 3 절).

    python -X utf8 results/v3/r10/make_cards.py [--src results/v3/r10/card_sources] [--out species]

- 값 기준: 언리얼이 실제로 실행하는 값(초안의 v). 초안은 칸마다 출처 파일:줄과 다른 출처(R9 YAML 등)를 함께 적은 것이다.
- 언리얼에 없는 값은 아래 CHOSEN 표와 크기 법칙으로 정하고, 카드 sources 에 '정함: 까닭' 을 남긴다. 먹는 양·기운 소모는
  1 단계 앞 관문(먹이·굶음 띠)에서 다시 맞출 값이다.
- 언리얼 값이 바뀌면 초안을 다시 뽑고 이 스크립트를 다시 돌린다. 두뇌는 몸 벡터 + 흔들기 범위 안이면 다시 배우지 않는다(설계 11 절).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from r10 import species as S  # noqa: E402

NAME_KO = {"deer": "사슴", "wolf": "늑대", "boar": "멧돼지", "buffalo": "물소", "leopard": "표범", "fox": "여우", "rat": "쥐",
           "crow": "까마귀", "bighorn": "큰뿔양", "jackrabbit": "산토끼 계열", "horse": "말", "golden_eagle": "검독수리",
           "mink": "밍크", "ariake_catfish": "아리아케 메기류", "common_carp": "잉어", "small_fish": "이름 없는 작은 민물고기"}
# M1 회전 한계 (사용자 결정 2026-11-13, RL_R9_TURN_EFFORT_DESIGN.md 3-2) — 언리얼 6 종은 회전 제한이 없어서 이 값을 쓴다
M1 = {"deer": (130, 9), "wolf": (140, 7), "boar": (125, 7), "buffalo": (90, 5), "leopard": (135, 11), "fox": (185, 10)}
# 언리얼에 회전·옆 가속이 없는 나머지 종 (정함: 몸 크기·생활에서 어림)
TURN_EST = {"rat": (400, 10), "crow": (300, 10), "golden_eagle": (150, 8), "ariake_catfish": (300, 6), "common_carp": (250, 6),
            "small_fish": (400, 6)}
CHOSEN = {
    "deer": {"accel_mps2": 20.0, "stamina_s": 12.0, "stamina_recover_s": 10.0, "night_vision": 0.5,
             "diet": {"grass": 1.0, "forbs": 0.8, "browse": 0.5, "wet_meadow": 0.8}},
    "wolf": {"accel_mps2": 20.0, "stamina_s": 8.0, "stamina_recover_s": 10.0, "night_vision": 0.3, "kill_mass_ratio": 1.6},
    "mink": {"diet": {"roots": 0.3}},
    "ariake_catfish": {"diet": {"insects": 1.0, "aquatic": 0.5}},
}
RESERVE_DAYS = 3.0
RUN_COST, SWIM_COST, FLY_COST = 3.0, 2.0, 3.0
DAY_S = 120.0                     # 하루 = 900 걸음 × 2/15 s


def v(c, g, k):
    f = c.get(g, {}).get(k)
    return f.get("v") if isinstance(f, dict) else None


def src(c, g, k):
    f = c.get(g, {}).get(k)
    if isinstance(f, dict) and f.get("src"):
        return f"{f['src']} ({f.get('kind', '?')})"
    return None


def num(x, default=None):
    if isinstance(x, bool) or x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, dict):
        for key in ("max_m", "v"):
            if isinstance(x.get(key), (int, float)):
                return float(x[key])
    return default


def diet_of(c, sid):
    d = {k: 0.0 for k in S.DIET_KEYS}

    def pref(key):
        x = v(c, "diet", key)
        if x is True or isinstance(x, dict) or isinstance(x, list):
            return 1.0
        return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else 0.0

    for k in ("grass", "forbs", "browse", "wet_meadow", "roots", "insects"):
        d[k] = pref(k)
    aq = v(c, "diet", "aquatic_plants_drift")
    if isinstance(aq, list):
        names = " ".join(aq).lower()
        if any(s in names for s in ("plant", "margin", "shelf")):
            d["aquatic"] = 1.0
        if "drift" in names:
            d["drift"] = 1.0
        if "insect" in names:
            d["insects"] = max(d["insects"], 1.0)
    d["meat"] = 1.0 if v(c, "diet", "meat_live_prey") is True else 0.0
    car = v(c, "diet", "carrion")
    d["carrion"] = 1.0 if isinstance(car, dict) and car.get("eats", True) and car.get("eats") is not False else 0.0
    if isinstance(car, dict) and "meal_max_nutrition" in car:          # Native 늑대 사체
        d["carrion"] = 1.0
    d.update(CHOSEN.get(sid, {}).get("diet", {}))
    return d


def build(c: dict) -> dict:
    sid = c["id"]
    ch = CHOSEN.get(sid, {})
    srcs = {}
    medium = {k: v(c, "medium", k) for k in ("ground", "swim", "fly", "wade_depth_m", "swim_depth_frac", "cruise_height_m",
                                             "ceiling_m", "takeoff_s")}
    medium["ground"] = bool(medium["ground"])
    medium["swim"] = bool(medium["swim"])
    medium["fly"] = bool(medium["fly"])
    medium["needs_water"] = medium["swim"] and not medium["ground"]
    medium["wade_depth_m"] = num(medium["wade_depth_m"], 0.0)
    for k in ("ground", "swim", "fly", "wade_depth_m", "swim_depth_frac", "cruise_height_m", "ceiling_m", "takeoff_s"):
        srcs[f"medium.{k}"] = src(c, "medium", k)

    b = {k: num(v(c, "body", k)) for k in ("mass_kg", "radius_m", "walk_mps", "run_mps", "swim_mps", "fly_mps", "cruise_mps",
                                         "dive_mps", "accel_mps2", "max_slope_deg", "step_m")}
    for k in b:
        srcs[f"body.{k}"] = src(c, "body", k)
    if medium["swim"]:
        b["swim_mps"] = b["swim_mps"] or b["walk_mps"]
        b["swim_fast_mps"] = b["swim_mps"]
        srcs["body.swim_fast_mps"] = "정함: 언리얼 헤엄은 걷기 속도 하나뿐 (빠른 헤엄 = 헤엄 속도)"
    else:
        b["swim_mps"] = b["swim_fast_mps"] = None
    if medium["fly"]:
        b["dive_mps"] = b["dive_mps"] or b["cruise_mps"] or b["fly_mps"]
        srcs.setdefault("body.dive_mps", None)
        if v(c, "body", "dive_mps") is None:
            srcs["body.dive_mps"] = "정함: 언리얼에 급강하 속도 없음 → 순항 속도"
    else:
        b["fly_mps"] = b["cruise_mps"] = b["dive_mps"] = None
    if b["accel_mps2"] is None or "accel_mps2" in ch:
        b["accel_mps2"] = ch.get("accel_mps2", 10.0)
        srcs["body.accel_mps2"] = "정함: 언리얼 Native 는 가속 제한 없음 → 큰 값"
    turn = num(v(c, "body", "turn_dps"), 0.0)
    lat = num(v(c, "body", "lat_accel_mps2"))
    if sid in M1:
        turn, lat = M1[sid]
        srcs["body.turn_dps"] = srcs["body.lat_accel_mps2"] = "정함: M1 회전 한계 (사용자 결정 11-13, RL_R9_TURN_EFFORT_DESIGN.md 3-2)"
    else:
        if not turn:
            turn = TURN_EST[sid][0]
            srcs["body.turn_dps"] = "정함: 언리얼 회전 제한 없음 → 몸·생활 어림"
        else:
            srcs["body.turn_dps"] = src(c, "body", "turn_dps")
        if lat is None:
            lat = TURN_EST.get(sid, (0, 8))[1]
            srcs["body.lat_accel_mps2"] = "정함: 옆 가속 자료 없음 → 어림"
    b["turn_dps"], b["lat_accel_mps2"] = float(turn), float(lat)
    if b["max_slope_deg"] is None:
        b["max_slope_deg"] = 89.0
        srcs["body.max_slope_deg"] = "정함: 물속 몸 — 경사 제한 해당 없음"
    if b["step_m"] is None:
        b["step_m"] = 0.0
        srcs["body.step_m"] = "정함: 물속 몸 — 단차 해당 없음"
    st = v(c, "body", "stamina")
    if isinstance(st, dict) and "sprint_drain_per_s" in st:
        b["stamina_s"] = round(1.0 / st["sprint_drain_per_s"], 2)
        b["stamina_recover_s"] = round(1.0 / st["recovery_per_s"], 2)
        srcs["body.stamina_s"] = srcs["body.stamina_recover_s"] = (src(c, "body", "stamina") or "") + " — 1/SprintDrain, 1/Recovery"
    else:
        b["stamina_s"] = ch.get("stamina_s", 10.0)
        b["stamina_recover_s"] = ch.get("stamina_recover_s", 10.0)
        srcs["body.stamina_s"] = srcs["body.stamina_recover_s"] = "정함: Native 는 지구력 없음 → R9 어림"
    order = ("mass_kg", "radius_m", "walk_mps", "run_mps", "swim_mps", "swim_fast_mps", "fly_mps", "cruise_mps", "dive_mps",
             "accel_mps2", "turn_dps", "lat_accel_mps2", "max_slope_deg", "step_m", "stamina_s", "stamina_recover_s")
    body = {k: b.get(k) for k in order}

    nv = v(c, "senses", "night_vision")
    senses = {"sight_m": num(v(c, "senses", "sight_m"), 10.0), "fov_deg": num(v(c, "senses", "fov_deg"), 198.0),
              "smell_m": num(v(c, "senses", "smell_m"), 0.0), "hearing_m": num(v(c, "senses", "hearing_m"), 0.0),
              "night_vision": ch.get("night_vision", num(nv, 0.5))}
    for k in senses:
        srcs[f"senses.{k}"] = src(c, "senses", k)
    if "night_vision" in ch:
        srcs["senses.night_vision"] = "정함: Native 는 낮밤 규칙만 있고 밤눈 값 없음"

    diet = diet_of(c, sid)
    srcs["diet"] = "초안 diet (선호 수치·True=1·목록=1) + 정함: " + json.dumps(CHOSEN.get(sid, {}).get("diet", {}), ensure_ascii=False)

    m = body["mass_kg"]
    rate = min(max(0.05 * (m / 60.0) ** 0.75, 0.002), 0.5)
    drain = min(max(0.5 * (m / 60.0) ** -0.25, 0.1), 3.0)
    epu = 4.0 * drain / (DAY_S * rate)
    eat = {"rate_per_s": round(rate, 5), "energy_per_unit": round(epu, 4)}
    metab = {"drain_per_day": round(drain, 4), "reserve_days": RESERVE_DAYS, "run_cost": RUN_COST,
             "swim_cost": SWIM_COST if medium["swim"] else None, "fly_cost": FLY_COST if medium["fly"] else None}
    srcs["eat"] = srcs["metabolism"] = ("정함: 크기 법칙 — 먹는 속도 ∝ 질량^0.75, 기운 소모/일 ∝ 질량^−0.25, 먹을 때 얻는 기운 = 소모의 4 배. "
                                        "언리얼 식사·에너지 모형과 단위가 달라 1 단계 앞 관문에서 다시 맞춘다")

    hunts = v(c, "combat", "hunts") or []
    ratios = [h.get("max_prey_mass_ratio") for h in hunts if isinstance(h, dict) and isinstance(h.get("max_prey_mass_ratio"), (int, float))]
    kill = ch.get("kill_mass_ratio", max(ratios) if ratios else 0.0)
    if diet["meat"] <= 0:
        kill = 0.0
    combat = {"kill_mass_ratio": float(kill), "reach_m": num(v(c, "combat", "attack_reach_m"), round(body["radius_m"] * 1.5 + 0.2, 3)),
              "attack_cd_s": 1.0, "defense": num(v(c, "combat", "counterattack_damage_hp"), 0.0),
              "counter_reach_m": round(body["radius_m"] * 2 + 0.3, 3)}
    srcs["combat.kill_mass_ratio"] = ("정함: 언리얼 사냥 표의 max_prey_mass_ratio 가운데 가장 큰 값 — 종 이름 목록 대신 몸무게 비율 하나 "
                                      "(사양 3 절)" if "kill_mass_ratio" not in ch else "정함: Native 늑대는 사슴만 — 사슴 60 kg 이 드는 비율")
    srcs["combat.reach_m"] = src(c, "combat", "attack_reach_m") or "정함: 반지름 × 1.5 + 0.2"
    srcs["combat.defense"] = src(c, "combat", "counterattack_damage_hp")
    srcs["combat.attack_cd_s"] = "정함: R9 물기 쿨다운 8 걸음 ≈ 1 s"

    life = {"maturity_days": round(num(v(c, "life", "maturity_s"), 180.0) / DAY_S, 4),
            "litter": num(v(c, "life", "litter"), 1.0),
            "gestation_days": round(num(v(c, "life", "gestation_s"), 30.0) / DAY_S, 4)}
    srcs["life"] = f"{src(c, 'life', 'maturity_s')} · 초를 하루 {DAY_S:.0f} s 로 나눔"

    card = {"id": sid, "name_ko": NAME_KO[sid], "card_version": S.CARD_VERSION, "medium": medium, "body": body, "senses": senses,
            "diet": diet, "eat": eat, "metabolism": metab, "combat": combat, "life": life,
            "randomize": {"frac": 0.15, "keys": list(S.RANDOMIZE_DEFAULT_KEYS)},
            "sources": {k: s for k, s in srcs.items() if s}}
    bad = S.validate(card)
    if bad:
        raise ValueError(f"{sid}: {bad}")
    return card


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(HERE / "card_sources"))
    ap.add_argument("--out", default=str(S.SPECIES_DIR))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for p in sorted(Path(a.src).glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        if c.get("id") not in NAME_KO:
            continue
        card = build(c)
        (out / f"{card['id']}.json").write_text(json.dumps(card, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        b = card["body"]
        print(f"{card['id']:15s} {b['mass_kg']:7.2f} kg  걷기 {b['walk_mps']:.2f} 뛰기 {b['run_mps']:.2f} m/s  "
              f"물기 비 {card['combat']['kill_mass_ratio']:.2f}  먹이 {[k for k, x in card['diet'].items() if x > 0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
