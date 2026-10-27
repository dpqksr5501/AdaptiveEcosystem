"""level_sense/sense.py 빠른 시험 (10-27). herbivore_rl/ 에서:

    PYTHONUTF8=1 python -m pytest results/v3/level_sense/test_sense.py -q      # 또는
    PYTHONUTF8=1 python results/v3/level_sense/test_sense.py

보는 것:
  - 시드 지킴 (예비 범위 34900~34999 밖 거부), 변형 글 읽기·거부.
  - 바탕 스냅숏 = pilot_mask5 의 '바뀌기 전 바탕 + 10-27 고침 켬' (저장소의 I_wx·J_wx 스냅숏과 날씨 바뀐 지역만 다르다).
  - 나무 자리 함수 결정성(같은 인자 → 같은 원판)·규칙 지킴(벽 4 m·은신처 둘레 2 m·줄기 사이 3 m), rand 30 그루 = pilot_mask5 manifest 의 30 그루.
  - 일(job) 꼴 변형 t10 = pilot 스냅숏 I_t10 을 같은 변환으로 만든 일 (설정·먹이 지도 바이트 같음).
  - 이름표 변형 모두 규칙 검사 통과 (check_region).
  - 바탕 맞추기: 평가기로 I_t10·J_t30 시드 34900~34901 × 1800 스텝 → 저장소 pilot_mask5/seeds 의 시드 합 칸과 정확히 같다.
  - 두 실행기·길 떼어 보기: Barren 시드 34900 × 300 스텝에서 t30 의 파이썬 = 평가기, 길 셋 모두 켬(t30all) = t30, 길 셋 모두 끔(t30none) = gate.
  - 작은 숲(spot): 결정성·규칙 지킴·원 안, 은신처 한가운데·좁은 원은 못 놓은 그루를 세고 멈추지 않음, 글 읽기·거부, 무대 밖 중심 거부, 파이썬 = 평가기.
  - 공간 지도: 켜도 세계 기록·다른 탐침 칸이 같다, 지도 합 = 행동 칸(산 사슴-스텝·graze·flee·hide·잡힘), 지역 합치기(save_maps).
  - 지역 고름(--regions): Barren 만 돌린 기록 = 세 지역 판의 Barren.
  - 명령 연기(run --maps → maps → rank, scan 격자): 짧은 판으로 끝까지 돈다.
"""

from __future__ import annotations

import copy
import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

import pytest  # noqa: E402

import sense  # noqa: E402

_INFO: dict = {}


def info(base: str = "I", brain: str = "r7e") -> dict:
    k = (base, brain)
    if k not in _INFO:
        _INFO[k] = sense.prepare(base, brain, Path(tempfile.mkdtemp(prefix="ls_test_")))
    return _INFO[k]


def test_seed_guard():
    assert sense.parse_seeds("34900-34902") == [34900, 34901, 34902]
    assert sense.parse_seeds("34999") == [34999]
    for bad in ("35000", "34990-35001", "33100-33101", "32000", "34899"):
        with pytest.raises(SystemExit):
            sense.parse_seeds(bad)


def test_parse_variants():
    for name in sense.PRESETS:
        v = sense.parse_variant(name)
        assert v["name"] == name
    assert sense.parse_variant("t30move")["python_only"]
    assert not sense.parse_variant("t30")["python_only"]
    e = sense.parse_variant("trees:12:ring@Forest+weather:snow:0.5")["edits"]
    assert e[0] == dict(kind="trees", n=12, place="ring", seed=sense.TREE_SEED, region="Forest") and e[1]["intensity"] == 0.5
    for bad in ("trees:0:rand", "trees:5:moon", "weather:fog:1", "paths:move", "trees:5:rand+paths:move", "food:-1", "shelter:0",
                "trees:5:rand+gate+paths:move+sight:off", "gate+gate", "day:901", "what"):
        with pytest.raises(SystemExit):
            sense.parse_variant(bad)


def test_base_snapshot_is_pilot_pre_plus_calm():
    """바탕 = pilot_mask5 의 바뀌기 전 바탕 + 고침 켬: 저장소 I_wx(Barren 날씨만 바꿈)·J_wx(Highland 날씨만 바꿈)와 그 지역 날씨 칸 말고 같다."""
    pm = sense._pm()
    for key, wx_variant, wx_region in (("I", "I_wx", "Barren"), ("J", "J_wx", "Highland")):
        b = sense.base_snapshot(key)
        w = json.loads((pm.SNAP_DIR / f"{wx_variant}.json").read_text(encoding="utf-8"))
        assert b["settings"] == w["settings"]
        for rb, rw in zip(b["regions"], w["regions"]):
            assert rb["region"] == rw["region"]
            rb, rw = copy.deepcopy(rb), copy.deepcopy(rw)
            if rb["region"] == wx_region:
                assert rb["world"]["weather"] != rw["world"]["weather"]
                for r in (rb, rw):
                    r["world"].pop("weather")
                    r.pop("weather_now")
            assert rb == rw, rb["region"]
        assert all(len(r["obstacles"]["discs"]) == 0 for r in b["regions"] if r["region"] == "Barren")
        assert b["regions"][0]["world"]["wild_flight"]["rest_keep"] is True and "graze_calm" in b["regions"][0]["world"]


def test_tree_placement_deterministic_and_rules():
    pm = sense._pm()
    R = sense.tree_rules()
    I = info()
    reg = I["regions"]["Barren"]
    covers = [list(map(float, c)) for c in reg["covers"]]
    cap = reg["cap"]
    man = json.loads((pm.SNAP_DIR / "manifest.json").read_text(encoding="utf-8"))
    for place in sense.PLACES:
        a, ma = sense.place_trees(place, 30, 60.0, covers, [], cap, 2.0, sense.TREE_SEED, int(reg["region_index"]))
        b, mb = sense.place_trees(place, 30, 60.0, covers, [], cap, 2.0, sense.TREE_SEED, int(reg["region_index"]))
        assert a == b and ma == mb, place
        assert len(a) == 30
        for i, (x, y, r) in enumerate(a):
            assert R["r_lo"] - 1e-12 <= r <= R["r_hi"] + 1e-12
            assert sense._wall_ok(x, y, r, 60.0, R["wall"])
            for c in covers:
                assert math.hypot(x - c[0], y - c[1]) >= c[2] + R["clear"] + r - 1e-12
            for j, (x2, y2, r2) in enumerate(a):
                if j != i:
                    assert math.hypot(x - x2, y - y2) >= r + r2 + R["gap"] - 1e-12
        c, _ = sense.place_trees(place, 30, 60.0, covers, [], cap, 2.0, sense.TREE_SEED + 1, int(reg["region_index"]))
        assert c != a, place
    rand, _ = sense.place_trees("rand", 30, 60.0, covers, [], cap, 2.0, sense.TREE_SEED, int(reg["region_index"]))
    assert [[round(v, 6) for v in t] for t in rand] == man["trees30"]["I"]
    # 있던 원판도 피한다 (ring 을 rand 30 위에)
    d, _ = sense.place_trees("ring", 10, 60.0, covers, rand, cap, 2.0, sense.TREE_SEED, int(reg["region_index"]))
    for x, y, r in d:
        for x2, y2, r2 in rand:
            assert math.hypot(x - x2, y - y2) >= r + r2 + R["gap"] - 1e-12


def test_job_variant_equals_pilot_snapshot_path():
    """일 꼴 t10 (바탕 + Barren 원판 10) = pilot 스냅숏 I_t10 을 live.prepare 로 바꾼 일 — 설정·먹이 지도가 바이트 단위로 같다."""
    live = sense._live()
    pm = sense._pm()
    I = info()
    seeds = [34900]
    mine, _ = sense.build_items(I, I["model"], seeds, 1800, "N", sense.parse_variant("t10"))
    sp = pm.SNAP_DIR / "I_t10.json"
    pinfo = live.prepare(sp, live.read_snapshot(sp), Path(tempfile.mkdtemp(prefix="ls_test_p_")), live.brain_folders(Path(tempfile.gettempdir())))
    theirs = live.eval_items(pinfo, "cur", Path(live.ad.ROOT / pinfo["record"]["anchor"]), seeds, 1800, "N", "multi", [1800])
    assert len(mine) == len(theirs) == 3
    for (k1, t1, j1), (k2, t2, j2) in zip(mine, theirs):
        assert j1["region"] == j2["region"] and j1["seed"] == j2["seed"]
        assert json.dumps(j1["cfg"], sort_keys=True) == json.dumps(j2["cfg"], sort_keys=True), j1["region"]
        assert j1["snap_food"] == j2["snap_food"]
        assert j1["model"] == j2["model"] and j1["steps"] == j2["steps"]


def test_all_presets_keep_world_rules():
    I = info()
    for name in sense.PRESETS:
        var = sense.parse_variant(name)
        items, vrec = sense.build_items(I, I["model"], [34900], 1, "N", var)
        for r, x in vrec.items():
            assert x["checks"]["ok"], (name, r)
            if not var["python_only"]:
                assert x["checks"]["ceval"] == "받음", (name, x["checks"]["ceval"])
        # 다른 지역은 그대로
        base, _ = sense.build_items(I, I["model"], [34900], 1, "N", sense.parse_variant("base"))
        for (_, _, j1), (_, _, j0) in zip(items, base):
            if j1["region"] not in vrec:
                assert json.dumps(j1["cfg"], sort_keys=True) == json.dumps(j0["cfg"], sort_keys=True)
                assert j1["snap_food"] == j0["snap_food"]


def test_baseline_matches_pilot_seed_table():
    """평가기로 다시 잰 지금 두뇌(R7e) N 1800 시드 합 = 저장소 pilot_mask5/seeds 표 (I_t10·J_t30, 시드 34900~34901)."""
    for base, v, pv in (("I", "t10", "I_t10"), ("J", "t30", "J_t30")):
        B = info(base)
        items, _ = sense.build_items(B, B["model"], [34900, 34901], 1800, "N", sense.parse_variant(v))
        out, _ = sense.run_ceval(items, 6)
        mine = sense.my_seed_table([r for _, r in out], 1800)
        pil = sense.pilot_seed_table(pv)
        for s in (34900, 34901):
            assert mine[s] == {k: pil[s][k] for k in mine[s]}, (pv, s)


def test_runners_and_paths_agree():
    """Barren 시드 34900 × 300 스텝: t30 파이썬 = 평가기 (세계 기록 겹치는 칸 모두), t30all = t30, t30none = gate (길 떼어 보기 감싸기가 새 나무의
    모든 길을 잡고, 떨굴 것이 없으면 그대로)."""
    I = info()

    def one(name, runner):
        items, _ = sense.build_items(I, I["model"], [34900], 300, "N", sense.parse_variant(name))
        items = [it for it in items if it[2]["region"] == "Barren"]
        if runner == "ceval":
            return [r for _, r in sense.run_ceval(items, 1)[0]]
        return [sense.py_world(copy.deepcopy(it[2])) for it in items]

    t30_py = one("t30", "python")
    assert sense.compare_worlds(one("t30", "ceval"), t30_py)["exact"] == 1
    assert sense.compare_worlds(one("t30all", "python"), t30_py)["exact"] == 1
    gate_py = one("gate", "python")
    c = sense.compare_worlds(one("t30none", "python"), gate_py)
    assert c["exact"] == 1, c
    assert sense.compare_worlds(one("gate", "ceval"), gate_py)["exact"] == 1
    spot = "spot:82:114:8:10+spot:60:60:8:10"
    assert sense.compare_worlds(one(spot, "ceval"), one(spot, "python"))["exact"] == 1


def test_spot_placement_and_parse():
    R = sense.tree_rules()
    I = info()
    reg = I["regions"]["Barren"]
    covers = [list(map(float, c)) for c in reg["covers"]]
    idx = int(reg["region_index"])
    a, ma = sense.place_spot(8, 60.0, covers, [], sense.TREE_SEED, idx, (30.0, 30.0), 5.0)
    b, mb = sense.place_spot(8, 60.0, covers, [], sense.TREE_SEED, idx, (30.0, 30.0), 5.0)
    assert a == b and ma == mb
    assert ma["n_placed"] == 8 and ma["unplaced"] == 0 and ma["center_state"] == "놓을 수 있음"
    for i, (x, y, r) in enumerate(a):
        assert math.hypot(x - 30.0, y - 30.0) <= 5.0 + 1e-9
        assert R["r_lo"] - 1e-12 <= r <= R["r_hi"] + 1e-12 and sense._wall_ok(x, y, r, 60.0, R["wall"])
        for c in covers:
            assert math.hypot(x - c[0], y - c[1]) >= c[2] + R["clear"] + r - 1e-12
        for j, (x2, y2, r2) in enumerate(a):
            if j != i:
                assert math.hypot(x - x2, y - y2) >= r + r2 + R["gap"] - 1e-12
    c, _ = sense.place_spot(8, 60.0, covers, [], sense.TREE_SEED, idx, (31.0, 30.0), 5.0)
    assert c != a
    d, md = sense.place_spot(8, 60.0, covers, a, sense.TREE_SEED, idx, (30.0, 30.0), 5.0)       # 있던 원판을 피한다 → 좁아서 일부만
    assert md["n_placed"] + md["unplaced"] == 8 and md["n_placed"] < 8
    for x, y, r in d:
        for x2, y2, r2 in a:
            assert math.hypot(x - x2, y - y2) >= r + r2 + R["gap"] - 1e-12
    e, me = sense.place_spot(8, 60.0, covers, [], sense.TREE_SEED, idx, (15.0, 15.0), 4.0)      # 은신처 한가운데 — 멈추지 않고 센다
    assert e == [] and me["n_placed"] == 0 and me["unplaced"] == 8 and me["center_state"] == "은신처 안" and me["free_frac"] == 0.0
    f, mf = sense.place_spot(8, 60.0, covers, [], sense.TREE_SEED, idx, (30.0, 30.0), 1.5)     # 좁은 원
    assert 0 < mf["n_placed"] < 8 and mf["n_placed"] + mf["unplaced"] == 8
    ed = sense.parse_variant("spot:60:60:8:10@Forest")["edits"][0]
    assert ed == dict(kind="trees", place="spot", n=8, x=30.0, y=30.0, r=5.0, seed=sense.TREE_SEED, region="Forest")
    assert sense.parse_variant("spot:60:60:8")["edits"][0]["r"] is None
    for bad in ("spot:60:60:0", "spot:-1:5:3", "spot:60:60:8:0", "spot:60:60", "spot:a:60:8"):
        with pytest.raises(SystemExit):
            sense.parse_variant(bad)
    with pytest.raises(SystemExit):
        sense.build_items(I, I["model"], [34900], 1, "N", sense.parse_variant("spot:200:60:8:10"))
    items, vrec = sense.build_items(I, I["model"], [34900], 1, "N", sense.parse_variant("spot:30:30:8:10+spot:60:60:8:10"))
    pl = vrec["Barren"]["place"]
    assert [p["n_placed"] for p in pl] == [0, 8] and len(vrec["Barren"]["new_trees"]) == 8 and vrec["Barren"]["checks"]["ok"]
    assert pl[1]["center_game_cm"] == [I["origin_cm"]["Barren"][0] + 30.0 * 200.0, I["origin_cm"]["Barren"][1] + 30.0 * 200.0]


def test_maps_and_region_filter():
    I = info()
    var = sense.parse_variant("spot:60:60:8:10")
    items, vrec = sense.build_items(I, I["model"], [34900], 300, "N", var, regions_run=["Barren"])
    assert [it[2]["region"] for it in items] == ["Barren"]
    full, _ = sense.build_items(I, I["model"], [34900], 300, "N", var)
    fb = [it for it in full if it[2]["region"] == "Barren"]
    assert json.dumps(fb[0][2]["cfg"], sort_keys=True) == json.dumps(items[0][2]["cfg"], sort_keys=True)
    assert sense.compare_worlds([r for _, r in sense.run_ceval(items, 1)[0]], [r for _, r in sense.run_ceval(fb, 1)[0]])["exact"] == 1
    with pytest.raises(SystemExit):
        sense.build_items(I, I["model"], [34900], 300, "N", sense.parse_variant("trees:5:rand@Forest"), regions_run=["Barren"])
    r0 = sense.py_world(copy.deepcopy(items[0][2]))
    j = copy.deepcopy(items[0][2])
    j["maps"] = True
    r1 = sense.py_world(j)
    assert sense.compare_worlds([r0], [r1])["exact"] == 1
    p1 = dict(r1["py"]["probe"])
    mp = p1.pop("maps")
    assert p1 == r0["py"]["probe"] and r1["py"]["obstacles"] == r0["py"]["obstacles"]
    m = {k: sum(v) for k, v in mp["counts"].items()}
    assert set(m) == set(sense.MAPS) and mp["g"] == 30
    assert m["deer"] == r1["live_steps"]
    assert (m["graze"], m["flee"], m["hide"]) == tuple(r1["beh_steps"][:3])
    assert m["caught"] == r1["caught"] and m["chased_flee"] <= m["flee"] and m["enter_fled"] <= m["enter"]
    assert m["spot_deer"] == m["spot_wolf"] > 0 and m["wolf_hunt"] + m["wolf_idle"] + m["wolf_sleep"] == 300 * 4
    assert m["onset"] == sum(r1["py"]["probe"]["onset_n"]) + r1["py"]["probe"]["onset_none"]
    with tempfile.TemporaryDirectory() as td:
        d = sense.save_maps(Path(td) / "m.json.gz", [copy.deepcopy(r1), dict(copy.deepcopy(r1), seed=34901)], dict(variant="x"), I, vrec)
        reg = d["regions"]["Barren"]
        assert reg["worlds"] == 2 and reg["seeds"] == [34900, 34901, 2]
        assert sum(reg["all"]["deer"]) == 2 * m["deer"] and sum(reg["even"]["deer"]) == m["deer"]
        assert len(reg["discs"]) == 8 and reg["region_index"] == 0


def test_commands_smoke():
    """짧은 판(시드 2·60 스텝)으로 run --maps → maps → rank, scan 격자가 끝까지 돈다."""
    with tempfile.TemporaryDirectory() as td:
        common = ["--base", "I", "--out", td, "--seeds", "34900-34901", "--horizon", "60", "--workers", "2"]
        assert sense.main(["run", *common, "--variants", "base", "spot:60:60:8:10", "--runner", "python", "--maps", "--regions", "Barren"]) == 0
        d = Path(td) / "I_r7e_N_h60"
        assert (d / "base__python__R-Barren.json.gz").exists() and (d / "spot_60_60_8_10__maps__R-Barren.json.gz").exists()
        assert sense.main(["maps", "--dir", str(d), "--variant", "base", "--show", "flee", "lost/chased_flee", "--spots", "2", "--save"]) == 0
        assert (d / "maps_base_Barren.json").exists()
        assert sense.main(["rank", "--dir", str(d), "--glob", "spot*", "--metrics", "tree", "--save", "t"]) == 0
        assert sense.main(["table", "--dir", str(d), "--variants", "spot_60_60_8_10", "--only", "tree", "core"]) == 0
        assert sense.main(["scan", *common, "--grid", "40"]) == 0
        s = json.loads((d / "scan_grid40_Barren.json").read_text(encoding="utf-8"))
        assert len(s["rows"]) + len(s["skipped"]) == 9 and s["rows"] and all(r["n_placed"] == 8 for r in s["rows"])


if __name__ == "__main__":
    sys.exit(pytest.main([str(HERE), "-q"]))
