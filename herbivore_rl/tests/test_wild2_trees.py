"""무대 나무 배치 표 (10-17 사용자 '그럼 그냥 우리 쪽 테스트 레벨에 저 사람이 만든 장애물들 적절히 배치해 봐', results/v3/wild2/trees/README.md).

- make_tree_layout.py 가 올려 둔 표·C++ 헤더·거울 설정을 지금 규칙·시드로 바이트 단위 그대로 다시 만든다(--check), 규칙(벽·은신처·빈터·늑대 모서리·간격)을 지킨다.
- C++ 헤더 TreeLayoutV3.h 의 숫자 = tree_layout.json 의 숫자 (float64 비트 단위, 반지름 = 밑동 꼭짓점 반경 × 크기 ÷ 200 도 같은 식).
- 거울 설정 configs/v3_wild2_trees_mirror.yaml 의 세계 원판 = 숲 무대 표, 나머지는 v3_wild2_obstacle_mirror.yaml 과 같다. 처음 자리는 원판 밖.
- 짝 지도 --unreal-obstacles tree_layout.json 은 지역마다 그 지역 표(메마른 땅 0·숲 24·고지 9)를 쓴다 (run_mirror.py·stuck_check.py).
- 언리얼 헤드리스 내보내기(trees/unreal_exports, 있으면) = 표.
시드는 탐색 32080~32083 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import json
import re

import numpy as np
import pytest

from env.config import ROOT
from env_v2.config import load_v2_config
from env_v2.world import World, obstacle_inside

CFG = ROOT / "configs"
OBST = CFG / "v3_wild2_obstacle_mirror.yaml"
TREES_CFG = CFG / "v3_wild2_trees_mirror.yaml"
WILD2 = ROOT / "results" / "v3" / "wild2"
TREES = WILD2 / "trees"
LAYOUT = TREES / "tree_layout.json"
HEADER = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy" / "TreeLayoutV3.h"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _layout():
    return json.loads(LAYOUT.read_text(encoding="utf-8"))


def _region(d, name):
    return next(r for r in d["regions"] if r["region"] == name)


def test_layout_fresh_and_rules():
    """올려 둔 세 파일 = 지금 규칙·시드로 만든 것(쓰지 않고 견줌). 숲 24·고지 9·메마른 땅 0, 규칙 어긋남 0, 틈 3 m 넘음."""
    mk = _module("_mk_trees", TREES / "make_tree_layout.py")
    mk.main(["--check"])
    body = mk.build()
    assert body == _layout()
    assert mk.check(body) == []
    assert [(r["region"], r["count"]) for r in body["regions"]] == [("Barren", 0), ("Forest", 24), ("Highland", 9)]
    for r in body["regions"]:
        tr = r["trees"]
        assert r["discs"] == [[t["x"], t["y"], t["r"]] for t in tr] == sorted(r["discs"])
        for i, a in enumerate(tr):
            assert 0.73 < a["r"] * 2.0 < 0.90 and mk.SCALE[0] <= a["scale"] <= mk.SCALE[1]
            for b in tr[i + 1:]:
                d = np.hypot(a["x"] - b["x"], a["y"] - b["y"])
                assert d * 2.0 >= r["min_spacing_m"] and (d - a["r"] - b["r"]) * 2.0 >= 3.0
    # 은신처 원 + 2 m·빈터 22 m 안에 줄기가 없다 (은신처 자리 = C++ 무대 1/4·3/4, 반경 6 단위)
    for r in body["regions"]:
        for t in r["trees"]:
            for cx, cy, cr in ((15, 15, 6), (45, 15, 6), (15, 45, 6), (45, 45, 6)):
                assert np.hypot(t["x"] - cx, t["y"] - cy) >= cr + 1.0 + t["r"]
            assert np.hypot(t["x"] - 30.0, t["y"] - 30.0) >= 11.0 + t["r"]


def test_header_matches_json():
    """C++ 헤더의 나무 줄 (x, y, r, 기준점 x·y, 방위, 크기) = JSON (repr 표기라 float64 비트 단위). 지역·그루 수·간격 줄도 같다."""
    text = HEADER.read_text(encoding="utf-8")
    d = _layout()
    assert f'kDigest = "{d["digest"]}"' in text and f'kVersion = "{d["version"]}"' in text and f'kMeshPath = "{d["mesh"]}"' in text
    for r in d["regions"]:
        m = re.search(rf"k{r['region']}Trees\[(\d+)\] = \{{\n(.*?)\n\t\}};", text, re.S)
        if r["count"] == 0:
            assert m is None and f'{{"{r["region"]}", nullptr, 0, 0.0}}' in text
            continue
        assert m and int(m.group(1)) == r["count"]
        rows = [[float(v) for v in ln.strip().strip("{},").split(", ")] for ln in m.group(2).splitlines()]
        want = [[t[k] for k in ("x", "y", "r", "pivot_x", "pivot_y", "yaw_deg", "scale")] for t in r["trees"]]
        assert rows == want
        assert f'{{"{r["region"]}", k{r["region"]}Trees, {r["count"]}, {r["min_spacing_m"]}}}' in text
        for t in r["trees"]:
            assert t["r"] == 40.45 * t["scale"] / 200.0     # C++ 시험 StageTrees.Layout 과 같은 식 (비트 단위)


def test_mirror_config_reads_forest_discs():
    """거울 설정 = 장애물 거울 + obstacles.fixed(숲 표): 세계 원판 = 표, 무작위 배치 난수를 쓰지 않는다, 처음 사슴·늑대는 원판(r + 몸) 밖."""
    d = _layout()
    forest = np.asarray(_region(d, "Forest")["discs"])
    a, b = load_v2_config(TREES_CFG), load_v2_config(OBST)
    fa = {k: dict(v) for k, v in a.v2["features"].items()}
    fb = {k: dict(v) for k, v in b.v2["features"].items()}
    assert np.array_equal(np.asarray(fa["obstacles"].pop("fixed")), forest)
    assert fa == fb and a.v2["version"] == "3.wild2trees"
    for seed in (32080, 32081):
        w = World(a.replace(N=128), seeds=[seed])
        np.testing.assert_array_equal(w.obstacles, forest)
        body = w._ob["body_r"]
        assert not obstacle_inside(w.pos, w.obstacles, body).any() and not obstacle_inside(w.pred_pos, w.obstacles, body).any()
        st = w.obstacle_stats()
        assert st["n"] == 24 and abs(st["r_mean"] - forest[:, 2].mean()) < 1e-12


def test_pair_maps_per_region(tmp_path):
    """짝 지도: run_mirror.load_unreal_obstacles(tree_layout.json) = 지역마다 그 표, stuck_check 짝 지도(메마른 땅·숲·고지 순) 원판 수 0·24·9."""
    rm = _module("_run_mirror_trees", WILD2.parent / "mirror" / "run_mirror.py")
    d = _layout()
    obs = rm.load_unreal_obstacles(LAYOUT, [20000, 20001])
    for s in (20000, 20001):
        for r in d["regions"]:
            assert obs[(s, r["region"])] == r["discs"]
    cfg = rm.mirror_cfg(64, 38, TREES_CFG).to_dict()
    for r in ("Highland", "Barren"):
        c = json.loads(json.dumps(cfg))
        c["v2"]["features"]["obstacles"]["fixed"] = obs[(20000, r)]
        from env.config import Config
        w = World(Config(c), seeds=[32082])
        assert w.obstacles.shape == (len(obs[(20000, r)]), 3)
        if len(obs[(20000, r)]):
            np.testing.assert_array_equal(w.obstacles, np.asarray(obs[(20000, r)]))
    sc = _module("_stuck_trees", WILD2 / "stuck_check.py")
    out = tmp_path / "s.json"
    sc.main(["--seeds", "32080-32082", "--steps", "5", "--workers", "0", "--config", str(TREES_CFG), "--unreal-maps", "20000",
             "--replicates", "1", "--unreal-obstacles", str(LAYOUT), "--out", str(out)])
    j = json.loads(out.read_text(encoding="utf-8"))
    assert [(w["unreal_map"]["region"], w["discs"]) for w in j["worlds"]] == [("Barren", 0), ("Forest", 24), ("Highland", 9)]


def test_unreal_export_matches_layout():
    """언리얼 헤드리스(-EcoIntegratedV3, 무대 나무 기본 켬) 내보내기의 지역 원판 = 표 (레벨 원판 0 이라 세계 원판 = 나무 원판). 내보내기가 없으면 건너뛴다."""
    ex = sorted((TREES / "unreal_exports").glob("s*.json"))
    if not ex:
        pytest.skip("언리얼 내보내기 없음")
    d = _layout()
    for f in ex:
        u = json.loads(f.read_text(encoding="utf-8"))
        assert u["stage_trees_on"] and u["tree_layout"] == f"{d['version']} {d['digest']}"
        for r in u["regions"]:
            want = _region(d, r["region"])["discs"]
            assert r["tree_discs"] == want and r["discs"] == want and r["level_discs"] == 0, (f.name, r["region"])
            assert r["tree_layout_count"] == len(want) and r["tree_skipped_cover"] == 0 and r["tree_skipped_no_ground"] == 0
