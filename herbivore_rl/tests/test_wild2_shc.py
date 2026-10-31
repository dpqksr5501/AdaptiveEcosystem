"""팀 날씨·나무 시험 레벨 거울 (10-17, 팀 PR ff8c8f4 LV_SHC_RegionalWeatherTest, results/v3/wild2/shc/README.md).

- make_shc_obstacle_maps.py 가 우리 레벨 읽기 규칙(C++ ScanStageObstacles)을 같은 순서로 건다: 중심이 무대 밖 → 충돌 없음 → 작음 → 낮음 → 은신처 원 안,
  남은 원판은 (x, y, r) 순. 올려 둔 지도(shc/obstacle_maps)는 지금 scan·내보내기에서 다시 만든 것과 같고 무대마다 원판 0 이다.
- 원판 0 개를 fixed 로 넣은 장애물 거울(돌아가기·시선 가림 켬) = 늑대 무리 거울(원판이 없으면 장애물 규칙을 타지 않는다).
- stuck_check.py 짝 지도(--unreal-maps·--replicates·--unreal-obstacles)는 run_mirror.py 와 같은 지도·원판 짝을 쓴다.
시드는 탐색 32080~32083 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import json

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import World

CFG = ROOT / "configs"
PACK = CFG / "v3_wild2_pack_mirror.yaml"
OBST = CFG / "v3_wild2_obstacle_mirror.yaml"
WILD2 = ROOT / "results" / "v3" / "wild2"
SHC = WILD2 / "shc"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _inst(label, x, y, r, h=300.0, collides=True):
    return dict(label=label, static_meshes=[dict(mesh="/Game/T.T", collides=collides,
                                                 instances=[dict(t=[x, y, 0.0], reader_disc=dict(center_cm=[x, y, 0.0], r_cm=r, height_cm=h))])])


def test_shc_reader_rule_order():
    """무대 원점 (1000, 2000) cm·한 변 60 단위·은신처 (15, 15, 6): 남김·뺌 까닭이 C++ 순서와 같고, 남은 원판은 무대 단위 (x, y, r) 순."""
    mk = _module("_mk_shc", SHC / "make_shc_obstacle_maps.py")
    region = dict(region="Forest", size=60, origin_cm=[1000.0, 2000.0, 0.0], covers=[[15, 15, 6]])
    scan = dict(actors=[
        _inst("keep_b", 1000 + 40 * 200, 2000 + 10 * 200, 50.0),
        _inst("keep_a", 1000 + 30 * 200, 2000 + 50 * 200, 80.0),
        _inst("out", 1000 - 1.0, 2000 + 10 * 200, 50.0),            # 중심이 무대 밖 (x < 0)
        _inst("edge", 1000 + 60 * 200, 2000, 50.0),                 # 무대 끝 위 = 안 (C++ X > SizeCm 만 밖)
        _inst("nocol", 1000 + 20 * 200, 2000 + 20 * 200, 50.0, collides=False),
        _inst("tiny", 1000 + 20 * 200, 2000 + 30 * 200, 24.9),
        _inst("low", 1000 + 20 * 200, 2000 + 40 * 200, 50.0, h=49.0),
        _inst("cover", 1000 + 15 * 200, 2000 + 16 * 200, 50.0),     # 은신처 원 안
        dict(label="no_mesh"),
    ])
    discs, dropped, frame = mk.stage_discs(scan, region)
    assert discs == [[30.0, 50.0, 0.4], [40.0, 10.0, 0.25], [60.0, 0.0, 0.25]]
    assert [(d["label"], d["why"]) for d in dropped] == [("out", "중심이 무대 밖"), ("nocol", "충돌 없음"), ("tiny", "작음"), ("low", "낮음"),
                                                         ("cover", "은신처 원 안")]
    assert len(frame) == 8 and next(f for f in frame if f["label"] == "out")["gap_center_m"] == 0.01


def test_shc_maps_are_fresh_and_empty(tmp_path):
    """올려 둔 지도 = 지금 scan(level_shc)·통합 레벨 내보내기에서 다시 만든 것. 나무 11 그루는 무대 셋 모두 밖이라 원판 0."""
    mk = _module("_mk_shc2", SHC / "make_shc_obstacle_maps.py")
    mk.main(["--sessions", "20000-20002", "--out", str(tmp_path / "maps")])
    for s in (20000, 20001, 20002):
        a = json.loads((SHC / "obstacle_maps" / f"s{s}.json").read_text(encoding="utf-8"))
        b = json.loads((tmp_path / "maps" / f"s{s}.json").read_text(encoding="utf-8"))
        assert a == b
        assert [r["region"] for r in a["regions"]] == ["Barren", "Forest", "Highland"]
        assert all(r["discs"] == [] and len(r["dropped"]) == 11 for r in a["regions"])
    t = json.loads((tmp_path / "trees_in_stage_frame.json").read_text(encoding="utf-8"))
    assert t["kept"] == dict(Barren=0, Forest=0, Highland=0)
    near = min(t["trees"]["Forest"], key=lambda f: f["gap_center_m"])
    assert near["label"] == "Beech_Tree11" and 0.0 < near["gap_disc_m"] < 0.2


def test_zero_discs_equal_pack():
    """장애물 거울에 원판 0 개(fixed [])를 넣으면 늑대 무리 거울과 궤적·통계가 같다(돌아가기·시선 가림·먹이 몫을 타지 않는다)."""
    c1 = load_v2_config(PACK).replace(N=32)
    c2 = load_v2_config(OBST).replace(N=32)
    f = {k: dict(v) for k, v in c2.v2["features"].items()}
    f["obstacles"]["fixed"] = []
    c2 = c2.replace(v2=dict(c2.v2, features=f))
    w1, w2 = World(c1, seeds=[32082]), World(c2, seeds=[32082])
    assert w2.obstacles.shape == (0, 3)
    a = np.full((w1.N, 1), float(rep.GRAZE))
    for _ in range(300):
        for x, y in zip(w1.step(a), w2.step(a)):
            np.testing.assert_array_equal(x, y)
    for k in ("pos", "energy", "food", "food_cap", "pred_pos", "pred_head", "pred_cd"):
        np.testing.assert_array_equal(getattr(w1, k), getattr(w2, k))
    assert json.dumps(w1.hunt_stats()) == json.dumps(w2.hunt_stats()) and json.dumps(w1.pack_stats()) == json.dumps(w2.pack_stats())
    st = w2.obstacle_stats()
    assert st["n"] == 0 and st["detour"]["help_drop"] == 0 and st["eye_pairs"] == 0


def test_stuck_check_paired_maps(tmp_path):
    """stuck_check.py 짝 지도: 지도 (세션, 지역) 순서·원판이 run_mirror.py 짝과 같다(367 원판 지도와 SHC 0 원판 지도)."""
    sc = _module("_stuck_shc", WILD2 / "stuck_check.py")
    out = tmp_path / "s.json"
    sc.main(["--seeds", "32080-32082", "--steps", "5", "--workers", "0", "--unreal-maps", "20000", "--replicates", "1",
             "--unreal-obstacles", str(WILD2 / "obstacle_maps"), "--out", str(out)])
    d = json.loads(out.read_text(encoding="utf-8"))
    assert [(w["unreal_map"]["region"], w["discs"]) for w in d["worlds"]] == [("Barren", 367), ("Forest", 367), ("Highland", 367)]
    assert set(d["summary"]["by_region"]) == {"Barren", "Forest", "Highland"}
    sc.main(["--seeds", "32080-32082", "--steps", "5", "--workers", "0", "--unreal-maps", "20000", "--replicates", "1",
             "--unreal-obstacles", str(SHC / "obstacle_maps"), "--out", str(out)])
    d = json.loads(out.read_text(encoding="utf-8"))
    assert [w["discs"] for w in d["worlds"]] == [0, 0, 0]
    with pytest.raises(ValueError, match="replicates"):
        sc.main(["--seeds", "32080-32081", "--steps", "5", "--workers", "0", "--unreal-maps", "20000"])
    with pytest.raises(ValueError, match="unreal-maps"):
        sc.main(["--seeds", "32080", "--steps", "5", "--workers", "0", "--unreal-obstacles", str(SHC / "obstacle_maps")])
