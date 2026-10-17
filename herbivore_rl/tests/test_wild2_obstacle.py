"""야생 2단계 3 — 도주를 막는 세로 장애물(기능 obstacles(12), 설정 configs/v3_wild2_obstacle_mirror.yaml) (10-17 사용자 '추천대로 끄고 2~4번 진행해',
명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md 6절, 정의는 env_v2/world.py 모듈 docstring '야생 2단계' 3).

비트 동일: 끈 세계는 직전 커밋(1b11c78)의 코드와 궤적·통계·v1 난수 상태·기능 스트림이 같다(야생 1·2단계 거울·R3 설정, R1b 롤아웃 포함).
새 설정에서 obstacles 를 끄면 v3_wild2_pack_mirror.yaml 과 같다.
규칙 단위 시험: 미끄러짐 손 장면(정면 멈춤·비스듬 미끄러짐·겹친 원판·가는 원판 뚫기 막음·멀어짐·벽 구석 물러남), 시선(엄격한 <·끝점·길이 0), 먹이 몫,
밀어내기(늑대는 은신처 막기 원 밖), 발소리는 가리지 않음, 롤아웃에서 사슴·늑대가 원판(r + 몸) 안에 들지 않고 무대 밖에 나가지 않음, fixed 원판 = 같은
무작위 배치, 짝 비교 실행기 --unreal-obstacles. 시드는 탐색 32080~32083·33090~33098 만 쓴다.
현실 근거: 늑대에게 잡힌 엘크는 도망이 막히는 곳에서 더 많았다(Kauffman 외 2007), 온대 성숙림 줄기 단면적 34 m²/ha(ESA E094-195).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import json
import math
import shutil
import subprocess
import sys

import numpy as np
import pytest
import yaml

from env.config import ROOT
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.features import features_of
from env_v2.world import (OB_EPS, OB_RING, OBSTACLE_COLUMNS, World, _obstacles_params, obstacle_food_factor, obstacle_inside, obstacle_layout,
                          obstacle_push_out, obstacle_slide, sight_blocked)

CFG = ROOT / "configs"
PACK = CFG / "v3_wild2_pack_mirror.yaml"
OBST = CFG / "v3_wild2_obstacle_mirror.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "1b11c78"              # 야생 2단계 3 직전 커밋(늑대 무리 C++) — 비트 동일 기준
BODY = 0.15
OP = dict(tree_per_ha=250.0, tree_r=[0.05, 0.15], rock_per_ha=5.0, rock_r=[0.25, 0.75], body_r=BODY, block_sight=True, no_food=True)

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _tum():
    spec = importlib.util.spec_from_file_location("_tum_for_obstacle", ROOT / "tests" / "test_unreal_mirror.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _graze(w):
    return np.full((w.N, 1), float(rep.GRAZE))


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


def test_obstacle_config_is_pack_plus_obstacles():
    """v3_wild2_obstacle_mirror.yaml = v3_wild2_pack_mirror.yaml + obstacles 블록(version 만 다르다). 줄기 단면적 ≈ 34 m²/ha."""
    a = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    b = yaml.safe_load(OBST.read_text(encoding="utf-8"))
    assert a["version"] == "3.wild2pack" and b["version"] == "3.wild2obstacle"
    fa, fb = a.pop("features"), b.pop("features")
    a.pop("version"), b.pop("version")
    assert a == b
    assert set(fb) - set(fa) == {"obstacles"} and all(fa[k] == fb[k] for k in fa)
    assert fb["obstacles"] == dict(enabled=True, **OP)
    lo, hi = (v * 2.0 for v in OP["tree_r"])                      # m
    basal = math.pi * (lo * lo + lo * hi + hi * hi) / 3.0 * OP["tree_per_ha"]
    assert 33.0 < basal < 35.0                                    # ESA E094-195: 34.1 m²/ha


def test_obstacle_world_layout():
    """무대 120 m = 1.44 ha: 줄기 360 + 바위 7 = 367 원판, 은신처 원 안에 중심이 없다, 원판 안에서 시작하는 사슴·늑대가 없다."""
    w = World(load_v2_config(OBST).replace(N=64), seeds=[32080])
    assert w.obstacles.shape == (367, 3) and w.obstacles.dtype == np.float64
    r = w.obstacles[:, 2]
    assert ((r >= 0.05) & (r <= 0.75)).all() and int(np.count_nonzero(r >= 0.25)) >= 7
    for (cx, cy), cr in zip(w.cov_c, w.cov_r):
        assert (((w.obstacles[:, 0] - cx) ** 2 + (w.obstacles[:, 1] - cy) ** 2) > cr * cr).all()
    assert not obstacle_inside(w.pos, w.obstacles, BODY).any() and not obstacle_inside(w.pred_pos, w.obstacles, BODY).any()
    assert w.obstacle_stats()["n"] == 367


def test_obstacle_off_equals_pack():
    """obstacles 를 끈 새 설정 = 늑대 무리 거울(궤적·통계·사냥 셈)."""
    c1 = load_v2_config(PACK).replace(N=32)
    c2 = _with(load_v2_config(OBST).replace(N=32), obstacles=dict(enabled=False))
    w1, w2 = World(c1, seeds=[32081]), World(c2, seeds=[32081])
    assert w2.obstacles.shape == (0, 3)
    for _ in range(300):
        a = _graze(w1)
        for x, y in zip(w1.step(a), w2.step(a)):
            np.testing.assert_array_equal(x, y)
    for k in ("pos", "energy", "food", "food_cap", "pred_pos", "pred_head", "pred_cd"):
        np.testing.assert_array_equal(getattr(w1, k), getattr(w2, k))
    assert json.dumps(w1.hunt_stats()) == json.dumps(w2.hunt_stats()) and json.dumps(w1.pack_stats()) == json.dumps(w2.pack_stats())
    with pytest.raises(ValueError, match="obstacle_stats"):
        w2.obstacle_stats()


def test_obstacle_params_checked():
    base = load_v2_config(OBST).replace(N=8)
    for kw in (dict(tree_per_ha=-1.0), dict(tree_r=[0.2, 0.1]), dict(rock_r=[0.0, 0.5]), dict(rock_r=0.5), dict(body_r=-0.1),
               dict(block_sight=1), dict(fixed=[[1.0, 1.0, 0.0]])):
        with pytest.raises(ValueError, match="obstacles"):
            World(_with(base, obstacles=kw), seeds=[32080])
    f = features_of(_with(base, repertoire=dict(enabled=False), threats=dict(enabled=False), wild_pack=dict(enabled=False),
                          wild_flight=dict(enabled=False), wild_satiation=dict(enabled=False)))
    with pytest.raises(ValueError, match="repertoire 또는 threats"):
        _obstacles_params(f.params("obstacles"), f)


def test_obstacle_fixed_equals_random_layout():
    """fixed = 무작위 배치와 같은 원판이면 궤적이 같다(배치 난수는 기능 스트림 part 0 뿐이라 다른 스트림이 그대로다)."""
    c = load_v2_config(OBST).replace(N=32)
    w1 = World(c, seeds=[32082])
    w2 = World(_with(c, obstacles=dict(fixed=w1.obstacles.tolist())), seeds=[32082])
    np.testing.assert_array_equal(w1.obstacles, w2.obstacles)
    for _ in range(200):
        a = _graze(w1)
        for x, y in zip(w1.step(a), w2.step(a)):
            np.testing.assert_array_equal(x, y)
    w3 = World(_with(c, obstacles=dict(fixed=[])), seeds=[32082])
    assert w3.obstacles.shape == (0, 3)


# --------------------------------------------------------------------- #
# 규칙 단위
# --------------------------------------------------------------------- #


def _slide(p, q, discs, size=None, body=BODY):
    q2, hit, back = obstacle_slide(np.asarray([p], float), np.asarray([q], float), np.asarray(discs, float).reshape(-1, 3), body, size)
    return q2[0], bool(hit[0]), bool(back[0])


def test_slide_head_on_stops_at_contact():
    """정면으로 부딪히면 둘레(r + 몸 + OB_EPS)에서 멈춘다 — 남은 이동이 모두 안쪽이다."""
    q, hit, back = _slide([8.0, 10.0], [9.5, 10.0], [[10.0, 10.0, 0.5]])
    assert hit and not back
    np.testing.assert_allclose(q, [10.0 - (0.5 + BODY + OB_EPS), 10.0], rtol=0, atol=1e-12)


def test_slide_glancing_slides_around():
    """비스듬히 닿으면 둘레를 따라 미끄러진다 — 원판 밖이고 처음 방향으로 앞으로 간다."""
    q, hit, back = _slide([8.0, 9.8], [9.5, 9.8], [[10.0, 10.0, 0.5]])
    assert hit and not back
    assert not obstacle_inside(q[None, :], np.array([[10.0, 10.0, 0.5]]), BODY)[0]
    assert q[1] < 9.8 and q[0] > 9.0


def test_slide_thin_trunk_no_tunnel_and_away():
    """가는 줄기(반지름 10 cm)도 빠르게 뚫고 지나가지 못한다. 멀어지는 이동은 막지 않는다. 제자리는 그대로."""
    q, hit, _ = _slide([4.0, 5.01], [6.0, 5.01], [[5.0, 5.0, 0.05]])
    assert hit and q[0] < 5.0
    q, hit, _ = _slide([4.0, 5.3], [6.0, 5.3], [[5.0, 5.0, 0.05]])
    assert not hit and q.tolist() == [6.0, 5.3]
    q, hit, _ = _slide([10.0, 10.66], [10.0, 11.5], [[10.0, 10.0, 0.5]])
    assert not hit
    q, hit, _ = _slide([8.0, 10.0], [8.0, 10.0], [[10.0, 10.0, 0.5]])
    assert not hit and q.tolist() == [8.0, 10.0]


def test_slide_overlapping_and_wall_pocket():
    """겹친 두 원판 사이로 가도 어느 원판(r + 몸) 안에도 들지 않는다. 벽과 원판 사이 구석에서는 자른 자리가 원판 안이라 닿은 자리로 물러난다."""
    pair = [[10.0, 10.0, 0.4], [10.0, 10.9, 0.4]]
    for p, q in (([8.0, 10.45], [11.0, 10.45]), ([8.0, 10.2], [11.5, 10.6])):
        q2, hit, _ = _slide(p, q, pair)
        assert hit and not obstacle_inside(q2[None, :], np.asarray(pair), BODY)[0]
    q2, hit, back = _slide([0.0, 8.0], [0.0, 10.5], [[0.3, 10.0, 0.4]], size=20.0)
    assert hit and back and not obstacle_inside(q2[None, :], np.array([[0.3, 10.0, 0.4]]), BODY)[0] and q2[1] > 8.0


def test_sight_rules():
    """눈길 가림: 선분과 중심의 가장 가까운 거리 < r(꼭 r 이면 안 가림), 원판 앞에서 끝나면 안 가림, 길이 0 은 안 가림."""
    d = np.array([[10.0, 10.0, 0.5]])
    a = np.array([[8.0, 10.5], [8.0, 10.49], [8.0, 10.0], [8.0, 8.0], [8.0, 8.0]])
    b = np.array([[12.0, 10.5], [12.0, 10.49], [9.0, 10.0], [8.0, 8.0], [12.0, 12.0]])
    got = [bool(sight_blocked(a[i:i + 1], b[i:i + 1], d)[0, 0]) for i in range(len(a))]
    assert got == [False, True, False, False, True]
    assert sight_blocked(a, b, np.zeros((0, 3))).shape == (5, 5) and not sight_blocked(a, b, np.zeros((0, 3))).any()


def test_food_factor():
    """셀을 다 덮는 바위는 먹이 0, 셀 모서리에 중심이 있는 반지름 1 원판은 16 표본점 가운데 3 개, 원판이 없으면 1."""
    f = obstacle_food_factor(30, 2.0, np.array([[11.0, 11.0, 1.6], [0.0, 0.0, 1.0]]))
    assert f[5, 5] == 0.0 and f[0, 0] == 13.0 / 16.0 and f[10, 10] == 1.0
    assert (obstacle_food_factor(30, 2.0, np.zeros((0, 3))) == 1.0).all()


def test_push_out_rules():
    """원판 안 개체는 가장 가까운 둘레 밖 후보로, 늑대는 은신처 막기 원 안 후보를 쓰지 않는다, 후보가 없으면 그대로 둔다."""
    d = np.array([[10.0, 10.0, 0.5]])
    q, mv, fl = obstacle_push_out(np.array([[10.2, 10.1]]), d, BODY, 20.0)
    assert mv == 1 and fl == 0 and not obstacle_inside(q, d, BODY)[0]
    np.testing.assert_allclose(np.linalg.norm(q[0] - d[0, :2]), 0.5 + BODY + OB_EPS, rtol=0, atol=1e-12)
    walls = np.array([[12.0, 10.0, 1.5]])
    qd, *_ = obstacle_push_out(np.array([[10.6, 10.0]]), d, BODY, 20.0)
    qw, *_ = obstacle_push_out(np.array([[10.6, 10.0]]), d, BODY, 20.0, walls)
    assert np.linalg.norm(qd[0] - walls[0, :2]) < 1.5 and np.linalg.norm(qw[0] - walls[0, :2]) >= 1.5
    q, mv, fl = obstacle_push_out(np.array([[1.0, 1.0]]), np.array([[1.0, 1.0, 1.5]]), BODY, 2.0)
    assert mv == 0 and fl == 1 and q.tolist() == [[1.0, 1.0]]
    assert len(OB_RING) == 8 and all(abs(math.hypot(*u) - 1.0) < 1e-15 for u in OB_RING)


def test_hearing_not_blocked_but_sight_is():
    """줄기 뒤에 있는 늑대: 서 있으면(소리 없음) 사슴이 못 보고, 달려오면(발소리) 알아챈다."""
    w = World(_with(load_v2_config(OBST).replace(N=8), obstacles=dict(fixed=[[30.0, 30.0, 0.15]])), seeds=[32083])
    w.pos[:] = [5.0, 5.0]
    w.pos[0] = [28.0, 30.0]
    w.head[0] = [1.0, 0.0]
    w.pred_pos[:] = [55.0, 55.0]
    w.pred_pos[0] = [33.0, 30.0]
    w.pred_asleep[:] = False
    w.pred_vel[:] = 0.0
    w.pred_running[:] = False
    g = w._geometry()
    assert g["pred_count"][0] == 0                          # 눈길이 줄기에 가린다
    w.pred_vel[0] = [-0.6, 0.0]
    w.pred_running[0] = True
    g = w._geometry()
    assert g["pred_count"][0] == 1                          # 발소리는 줄기가 못 가린다
    w2 = World(_with(load_v2_config(OBST).replace(N=8), obstacles=dict(fixed=[[30.0, 30.0, 0.15]], block_sight=False)), seeds=[32083])
    w2.pos[:], w2.head[:], w2.pred_pos[:] = w.pos, w.head, w.pred_pos
    w2.pred_asleep[:] = False
    w2.pred_vel[:] = 0.0
    w2.pred_running[:] = False
    assert w2._geometry()["pred_count"][0] == 1             # 가림을 끄면 본다


# --------------------------------------------------------------------- #
# 롤아웃
# --------------------------------------------------------------------- #


def test_rollout_invariants_and_determinism():
    """무작위 행동 400 스텝: 사슴·늑대가 원판(r + 몸) 안에 들지 않고 무대 밖에 나가지 않는다. 같은 시드 = 같은 궤적. 통계가 맞는다."""
    c = load_v2_config(OBST).replace(N=48)
    ws = [World(c, seeds=[32083]) for _ in range(2)]
    rng = np.random.default_rng(32083)
    for _ in range(400):
        a = rng.integers(0, 3, (48, 1)).astype(np.float64)
        a[a == 2] = float(rep.HIDE)
        for w in ws:
            w.step(a)
        w = ws[0]
        assert not obstacle_inside(w.pos, w.obstacles, BODY).any() and not obstacle_inside(w.pred_pos, w.obstacles, BODY).any()
        assert (w.pos >= 0).all() and (w.pos <= w.size).all() and (w.pred_pos >= 0).all() and (w.pred_pos <= w.size).all()
    np.testing.assert_array_equal(ws[0].pos, ws[1].pos)
    np.testing.assert_array_equal(ws[0].pred_pos, ws[1].pred_pos)
    st = ws[0].obstacle_stats()
    assert st["deer_hit"] > 0 and st["wolf_hit"] > 0 and st["deer_back"] <= st["deer_hit"] and st["wolf_dead"] <= st["wolf_hit"] + st["wolf_back"]
    assert 0 < st["eye_blocked"] < st["eye_pairs"] and 0 < st["tgt_blocked"] < st["tgt_pairs"]
    assert 0 < st["deer_steps"] <= 400 * 48 and st["wolf_steps"] == 400 * ws[0].M


def _cover_food(w, cap):
    """은신처 먹이 부족(realism_cover_food)을 켠 세계는 원판 먹이 몫 뒤에 은신처 셀 용량 × cap_frac 을 건다(world.py `_rz_cover_food_apply`,
    C++ FFoodGrid::Build 의 ApplyObstacleFood → ApplyShelterFood 와 같은 순서). 10-17 고침으로 이 설정에 은신처 먹이 부족을 다시 넣었다."""
    return np.where(w.cover_food_cell, cap * w.cover_food_cap, cap) if getattr(w, "_zf", None) is not None else cap


def test_food_under_discs_reduced():
    """원판 밑 셀 용량 = v1 용량 × 먹이 몫(no_food), 그 뒤 은신처 셀 × cap_frac. 끄면 그대로."""
    c = load_v2_config(OBST).replace(N=8)
    w = World(c, seeds=[32080])
    w0 = World(_with(c, obstacles=dict(no_food=False), realism_cover_food=dict(enabled=False)), seeds=[32080])
    assert w._zf is not None and w.cover_food_cell.any() and w.cover_food_cap == 0.15
    np.testing.assert_array_equal(w.food_cap, _cover_food(w, w0.food_cap * obstacle_food_factor(w.gw, float(c.food_cell), w.obstacles)))
    assert (w0.ob_food_factor == 1.0).all() and (w.ob_food_factor < 1.0).any()


# --------------------------------------------------------------------- #
# 비트 동일
# --------------------------------------------------------------------- #


def test_obstacle_bit_identical_to_head(tmp_path):
    """직전 코드(1b11c78)와: 야생 1·2단계 거울·R3 설정의 궤적·통계·난수·관측 이름·기능 스트림이 같다(R1b 롤아웃 포함). obstacles 는 끈 세계에서 길이 없다."""
    tum = _tum()
    old_root = tum._archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(tum.TRACE_SRC % dict(keys=tum.KEYS, stats=tum.STATS), encoding="utf-8")
    # 늑대 무리 거울은 두 코드 모두 지금 파일을 읽는다(10-17 고침으로 이 설정에 은신처 먹이 부족을 다시 넣었다 — 설정이 아니라 코드를 견준다.
    # 1b11c78 코드도 realism_cover_food 를 안다)
    jobs = [dict(config="configs/v3_r3_on.yaml", seed=32080, steps=250, policy="rand"),
            dict(config="configs/v3_wild1_mirror.yaml", seed=32081, steps=400, policy="rand"),
            dict(config=str(PACK), seed=32082, steps=400, policy="rand")]
    if R1_MODEL.exists():
        jobs.append(dict(config=str(PACK), seed=32083, steps=400, policy="model", model=str(R1_MODEL)))
    procs = []
    for root, tag in ((old_root, "old"), (ROOT, "new")):
        jp, op = tmp_path / f"jobs_{tag}.json", tmp_path / f"out_{tag}.json"
        jp.write_text(json.dumps(jobs), encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, str(script), str(jp), str(op)], cwd=root), op))
    outs = []
    for p, op in procs:
        assert p.wait(timeout=900) == 0
        outs.append(json.loads(op.read_text(encoding="utf-8")))
    for j, a, b in zip(jobs, *outs):
        first = next((i for i, (x, y) in enumerate(zip(a["hashes"], b["hashes"])) if x != y), None)
        assert first is None and len(a["hashes"]) == len(b["hashes"]), (j, first)
        for k in ("stats", "rng", "obs_names", "streams"):
            assert a[k] == b[k], (j, k)


# --------------------------------------------------------------------- #
# 실행기 · 지도
# --------------------------------------------------------------------- #


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_obstacle_maps_and_runner(tmp_path):
    """make_obstacle_maps: 세션마다 세 지역 원판(파이썬 숲 배치, 시드 33090~), 은신처 원은 언리얼 무대와 같다(quad). 실행기 --unreal-obstacles 는
    지도 세계의 원판을 그대로 쓰고, 짝 비교 먹이 지도 덮기는 원판 밑 먹이 몫을 다시 건다."""
    mk = _module("_mk_obstacle_maps", ROOT / "results" / "v3" / "wild2" / "make_obstacle_maps.py")
    d = mk.build([20000])[20000]
    assert [r["region"] for r in d["regions"]] == ["Barren", "Forest", "Highland"]
    for r in d["regions"]:
        assert len(r["discs"]) == 367 and r["size"] == 60.0
        np.testing.assert_allclose(np.asarray(r["covers"]), [[45, 45, 6], [15, 45, 6], [15, 15, 6], [45, 15, 6]], rtol=0, atol=1e-9)
    (tmp_path / "s20000.json").write_text(json.dumps(d), encoding="utf-8")
    rm = _module("_rm_for_obstacle", ROOT / "results" / "v3" / "mirror" / "run_mirror.py")
    obs = rm.load_unreal_obstacles(tmp_path, [20000])
    assert obs[(20000, "Forest")] == d["regions"][1]["discs"]
    res = rm.run(16, 38, [32080, 32081, 32082], steps=20, workers=0, config=OBST, unreal_maps=[20000], replicates=1, unreal_obstacles=tmp_path)
    for wd, r in zip(res["worlds"], ("Barren", "Forest", "Highland")):
        assert wd["meta"]["unreal_map"]["region"] == r and wd["meta"]["obstacles"]["n"] == 367
    with pytest.raises(ValueError, match="obstacles"):
        rm.run(16, 38, [32080, 32081, 32082], steps=5, workers=0, config=PACK, unreal_maps=[20000], unreal_obstacles=tmp_path)
    # 지도 덮기: 원판 밑 먹이 몫이 새 지도에도 걸린다
    c = rm.mirror_cfg(16, 38, OBST)
    w = World(c, seeds=[32080])
    rm.apply_unreal_map(w, 20000, "Forest")
    w0 = World(_with(c, obstacles=dict(no_food=False), realism_cover_food=dict(enabled=False)), seeds=[32080])
    rm.apply_unreal_map(w0, 20000, "Forest")
    np.testing.assert_array_equal(w.food_cap, _cover_food(w, w0.food_cap * w.ob_food_factor))


# --------------------------------------------------------------------- #
# C++ 골든 (export_golden_v3_obstacle.py → AI/Policy/ObstacleGoldenVectorsV3.h, 검사 본문 Tests/ObstacleGoldenCheckV3.h)
# --------------------------------------------------------------------- #

UE_POLICY = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
OB_CPP_MAIN = ROOT / "tests" / "cpp" / "obstacle_v3_main.cpp"


def test_obstacle_golden_header_is_fresh():
    """언리얼 모듈의 ObstacleGoldenVectorsV3.h 는 지금 코드로 다시 만든 헤더와 바이트 단위로 같다."""
    path = UE_POLICY / "ObstacleGoldenVectorsV3.h"
    if not path.exists():
        pytest.skip("언리얼 모듈 장애물 골든 헤더 없음")
    ex = _module("_export_golden_v3_obstacle", ROOT / "export_golden_v3_obstacle.py")
    assert path.read_bytes() == ex.build_header().encode("utf-8")


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")
def test_cpp_obstacle_matches_golden_with_gpp(tmp_path):
    """언리얼 모듈의 EcoThreatModel.h·EcoWorldV3.h·장애물 골든 헤더를 그대로 g++ 로 컴파일해 대조한다(UE 시험 Policy.V3.Obstacle.Golden 과 같은 검사 본문)."""
    if not (UE_POLICY / "ObstacleGoldenVectorsV3.h").exists():
        pytest.skip("언리얼 모듈 장애물 골든 헤더 없음")
    exe = tmp_path / ("obstacle_v3.exe" if sys.platform == "win32" else "obstacle_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-Wno-unused-parameter", "-I", str(UE_POLICY),
                            str(OB_CPP_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"


def test_columns_and_registry():
    assert OBSTACLE_COLUMNS == ("x", "y", "r")
    g = np.random.default_rng(0)
    d = obstacle_layout(g, 60.0, np.zeros((0, 2)), np.zeros(0), dict(OP, tree_r=(0.05, 0.15), rock_r=(0.25, 0.75)))
    assert d.shape == (367, 3)
