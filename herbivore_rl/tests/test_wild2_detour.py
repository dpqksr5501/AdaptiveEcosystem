"""야생 2단계 3 의 6) 장애물 돌아가기 (선택 키 obstacles.detour·detour_*, 설정 configs/v3_wild2_obstacle_mirror.yaml) (10-17 장애물 끼임 고침,
명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md 7절, 정의는 env_v2/world.py 모듈 docstring '야생 2단계' 3 의 6)).

비트 동일: 돌아가기를 끄면 직전 커밋(0a46029)의 코드·설정과 궤적·통계·v1 난수 상태·기능 스트림이 같다(장애물 거울 R1b 롤아웃 포함). 늑대 무리 거울
(원판 없음)은 그대로다.
규칙 단위 시험: 정면 줄기 → 가장 적게 돈 빈 방향(속력 그대로), 비스듬 → 그대로, 앞 보기 트임 → 끝, 이어 돌기 → 붙은 쪽, 마지막 스텝, 멈춤 → 상태 0,
둘러싸임 → 못 찾음, 늑대 은신처 막기 원(빈 방향에서 빼고, 미끄러져 원으로 밀려 들어가면 막힘), V 자 너머 목표에 닿음(끄면 못 닿음), 돕다 막힌 늑대는
잠시 돕지 않는다. 롤아웃: 원판 안·무대 밖 0, 끼임 도구(results/v3/wild2/stuck_check.py)로 짧은 판의 끼임 0. 골든: export_golden_v3_detour.py →
AI/Policy/DetourGoldenVectorsV3.h, g++ 하네스 tests/cpp/detour_v3_main.cpp. 시드는 탐색 32084~32089 만 쓴다.
현실 근거: 사슴·늑대는 나무 줄기와 바위에 몸을 밀어붙이지 않고 돌아 지나간다.
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
from env_v2.world import (DETOUR_CAND_K, DETOUR_CAND_SG, DETOUR_ORDER_FRESH, DETOUR_ROT, World, _obstacles_params, detour_candidates, detour_moves,
                          obstacle_inside, obstacle_slide)
from env_v2.features import features_of

CFG = ROOT / "configs"
PACK = CFG / "v3_wild2_pack_mirror.yaml"
OBST = CFG / "v3_wild2_obstacle_mirror.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "0a46029"              # 돌아가기 직전 커밋 — 비트 동일 기준
BODY = 0.15
DP = dict(block=0.5, free=0.8, probe=1.5, steps=45, help_block=15, help_drop=38)
UE_POLICY = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
CPP_MAIN = ROOT / "tests" / "cpp" / "detour_v3_main.cpp"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _one(p, v, discs, st=(0, 0, 0), deer=True, size=20.0, walls=None):
    left, side, steps = (np.array([x], dtype=np.int64) for x in st)
    d = np.asarray(discs, float).reshape(-1, 3)
    nv, dirs, used, start, fail = detour_moves(np.asarray([p], float), np.asarray([v], float), left, side, steps, d, BODY, size, deer, DP,
                                               None if walls is None else np.asarray(walls, float).reshape(-1, 3),
                                               None if walls is None else np.ones(1, dtype=bool))
    return nv[0], dirs[0], (int(left[0]), int(side[0]), int(steps[0])), bool(used[0]), bool(start[0]), bool(fail[0])


def _gain(p, u, discs, deer=True, size=20.0):
    """이동 시험 나아감 ((q − p)·c) / |u| 와 끝 자리 (detour_moves 의 move_test 와 같은 식)."""
    p, u = np.asarray([p], float), np.asarray([u], float)
    d = np.asarray(discs, float).reshape(-1, 3)
    if deer:
        q, hit, _ = obstacle_slide(p, np.clip(p + u, 0.0, size), d, BODY, size)
    else:
        q, hit, _ = obstacle_slide(p, p + u, d, BODY)
    s = float(np.sqrt((u * u).sum()))
    c = u[0] / s
    return float(((q[0] - p[0]) * c).sum() / s), q[0], bool(hit[0])


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


def test_detour_config_and_defaults():
    """거울 설정은 돌아가기를 켜고 계수를 모두 적는다. 키가 없으면 끔(None)이고 숫자 기본값은 켰을 때 쓰는 값이다."""
    b = yaml.safe_load(OBST.read_text(encoding="utf-8"))["features"]["obstacles"]
    assert b["detour"] is True
    assert {k[len("detour_"):]: b[k] for k in b if k.startswith("detour_")} == DP
    f = features_of(load_v2_config(OBST))
    assert _obstacles_params(f.params("obstacles"), f)["detour"] == DP
    off = _with(load_v2_config(OBST), obstacles={k: v for k, v in b.items() if not k.startswith("detour")} | dict(detour=False))
    fo = features_of(off)
    assert _obstacles_params(fo.params("obstacles"), fo)["detour"] is None
    from env_v2.features import OPTIONAL_KEYS
    assert OPTIONAL_KEYS["obstacles"]["detour"] is False
    assert {k[len("detour_"):]: v for k, v in OPTIONAL_KEYS["obstacles"].items() if k.startswith("detour_")} == DP
    # 돌리기 표: 삼각함수 값과 1 ulp 안 (리터럴이라 C++ 와 비트 동일)
    for k, (c, s) in enumerate(DETOUR_ROT):
        assert abs(c - math.cos(k * math.pi / 8)) < 1e-15 and abs(s - math.sin(k * math.pi / 8)) < 1e-15
    assert sorted(zip(DETOUR_CAND_K, DETOUR_CAND_SG)) == sorted([(k, 1) for k in range(1, 9)] + [(k, -1) for k in range(1, 8)])


def test_detour_params_checked():
    base = load_v2_config(OBST).replace(N=8)
    for kw in (dict(detour=1), dict(detour_block=0.0), dict(detour_block=1.5), dict(detour_free=0.0), dict(detour_probe=-1.0),
               dict(detour_steps=0), dict(detour_steps=2.5), dict(detour_help_block=0), dict(detour_help_drop=-1)):
        with pytest.raises(ValueError, match="obstacles"):
            World(_with(base, obstacles=kw), seeds=[32084])


# --------------------------------------------------------------------- #
# 비트 동일
# --------------------------------------------------------------------- #


def test_detour_off_bit_identical_to_head(tmp_path):
    """돌아가기를 끈 장애물 거울 = 직전 코드(0a46029)의 장애물 거울(돌아가기 키 없음). 늑대 무리 거울도 그대로. R1b 롤아웃 포함."""
    tum = _module("_tum_for_detour", ROOT / "tests" / "test_unreal_mirror.py")
    old_root = tum._archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    stats = tum.STATS + ("obstacle_stats", "pack_stats", "hunt_stats", "wild_stats")
    script = tmp_path / "trace.py"
    script.write_text(tum.TRACE_SRC % dict(keys=tum.KEYS + ("pack_help",), stats=stats), encoding="utf-8")
    base = [dict(config=str(OBST.relative_to(ROOT)), seed=32084, steps=400, policy="rand"),
            dict(config=str(PACK.relative_to(ROOT)), seed=32085, steps=300, policy="rand")]
    if R1_MODEL.exists():
        base.append(dict(config=str(OBST.relative_to(ROOT)), seed=32086, steps=400, policy="model", model=str(R1_MODEL)))
    new_jobs = [dict(j, set={"obstacles": {"detour": False}}) if "obstacle" in j["config"] else j for j in base]
    procs = []
    for root, tag, jobs in ((old_root, "old", base), (ROOT, "new", new_jobs)):
        jp, op = tmp_path / f"jobs_{tag}.json", tmp_path / f"out_{tag}.json"
        jp.write_text(json.dumps(jobs), encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, str(script), str(jp), str(op)], cwd=root), op))
    outs = []
    for p, op in procs:
        assert p.wait(timeout=900) == 0
        outs.append(json.loads(op.read_text(encoding="utf-8")))
    for j, a, b in zip(base, *outs):
        first = next((i for i, (x, y) in enumerate(zip(a["hashes"], b["hashes"])) if x != y), None)
        assert first is None and len(a["hashes"]) == len(b["hashes"]), (j, first)
        for k in ("stats", "rng", "obs_names", "streams"):
            assert a[k] == b[k], (j, k)


# --------------------------------------------------------------------- #
# 규칙 단위
# --------------------------------------------------------------------- #

ONE = [[10.0, 10.0, 0.1]]
R1 = 0.1 + BODY


def test_head_on_trunk_turns_least():
    """정면 줄기(걷는 사슴 0.24): 막힘 → 작은 각부터 +·− 번갈아 본 첫 빈 방향, 속력 그대로, 상태 (steps_max − 1, 쪽, 1)."""
    p, v = [10.0 - R1 - 0.1, 10.0], [0.24, 0.0]
    g, _, hit = _gain(p, v, ONE)
    assert hit and g < DP["block"]
    nv, c, st, used, start, fail = _one(p, v, ONE)
    assert used and start and not fail
    assert abs(math.hypot(*nv) - 0.24) < 1e-12 and np.allclose(nv, 0.24 * c, rtol=0, atol=1e-15)
    cand = detour_candidates(np.array([[1.0, 0.0]]))[0]
    j = next(j for j in DETOUR_ORDER_FRESH if np.array_equal(cand[j], c))
    for jj in DETOUR_ORDER_FRESH[:DETOUR_ORDER_FRESH.index(j)]:
        assert _gain(p, 0.24 * cand[jj], ONE)[0] < DP["free"]          # 앞 차례는 빈 방향이 아니다
    assert _gain(p, nv, ONE)[0] >= DP["free"]
    assert st == (DP["steps"] - 1, DETOUR_CAND_SG[j], 1) and DETOUR_CAND_K[j] < 8
    # 정면이라 +·− 가 같다 → 시계 반대(+) 먼저
    assert DETOUR_CAND_SG[j] == 1


def test_glancing_and_probe_and_sticky():
    # 비스듬: 많이 가서 막힘 아님 → 그대로
    p, v = [10.0 - R1 - 0.1, 10.2], [0.24, 0.0]
    nv, _, st, used, start, fail = _one(p, v, ONE)
    assert not used and not start and not fail and np.array_equal(nv, v) and st == (0, 0, 0)
    # 돌아가는 중, 앞 보기 트임 → 끝, 보통(그대로)
    nv, _, st, used, _, _ = _one([10.0 + R1 + 0.01, 10.0], [0.24, 0.0], ONE, st=(10, 1, 3))
    assert not used and st == (0, 0, 0) and np.array_equal(nv, [0.24, 0.0])
    # 돌아가는 중, 앞 보기 닿음 → 붙은 쪽 먼저 (− 쪽이 붙은 쪽이면 − 후보)
    for side in (1, -1):
        nv, c, st, used, start, _ = _one([10.0 - R1 - 0.01, 10.0], [0.24, 0.0], ONE, st=(10, side, 5))
        assert used and not start and st[0] == 9 and st[2] == 6 and st[1] == side
        assert np.sign(c[1]) == side                                     # 시계 반대 = 위(+y)
    # 마지막 스텝: left 1 → 0
    _, _, st, used, _, _ = _one([10.0 - R1 - 0.01, 10.0], [0.24, 0.0], ONE, st=(1, 1, 44))
    assert used and st == (0, 1, 45)
    # 멈춤·거의 멈춤 → 상태 0
    for v0 in ([0.0, 0.0], [1e-12, 0.0]):
        nv, _, st, used, _, _ = _one([10.0 - R1 - 0.1, 10.0], v0, ONE, st=(7, -1, 2))
        assert st == (0, 0, 0) and not used and np.array_equal(nv, v0)


def test_enclosed_fails_and_keeps_velocity():
    ring = [[10.0 + 0.62 * math.cos(a), 10.0 + 0.62 * math.sin(a), 0.2] for a in np.linspace(0.0, 2.0 * math.pi, 12, endpoint=False)]
    nv, _, st, used, start, fail = _one([10.0, 10.0], [0.6, 0.0], ring)
    assert fail and not used and not start and np.array_equal(nv, [0.6, 0.0]) and st == (0, 0, 0)


def test_wolf_walls():
    """늑대: 은신처 막기 원 안 자리는 빈 방향이 아니다(사슴은 상관없다). 줄기에 미끄러져 원으로 밀려 들어가면 나아감이 커도 막힘이다."""
    rock = [[20.0, 20.0, 0.6]]
    wall = [[19.7, 21.0, 0.8]]
    p, v = [20.0 - 0.75 - 0.1, 20.0], [0.48, 0.0]
    _, cw, _, uw, _, _ = _one(p, v, rock, deer=False, size=40.0, walls=wall)
    _, cn, _, un, _, _ = _one(p, v, rock, deer=False, size=40.0)
    assert uw and un and not np.array_equal(cw, cn)
    _, q, _ = _gain(p, 0.48 * cw, rock, deer=False, size=40.0)
    assert math.hypot(q[0] - 19.7, q[1] - 21.0) >= 0.8
    # 미끄러져 원으로 밀려 들어감: 원 둘레 곁 줄기를 비켜 지나가는 이동 가운데 나아감 ≥ block 이고 끝이 원 안인 것을 찾는다
    wl = [[20.0, 20.0, 5.0]]
    trunk = [[25.3, 20.0, 0.1]]
    found = 0
    for dx in np.linspace(-0.3, 0.0, 31):
        for y0 in (-0.4, -0.3):
            p = [25.3 + dx, 20.0 + y0]
            if math.hypot(p[0] - 20.0, p[1] - 20.0) < 5.0 or obstacle_inside(np.asarray([p]), np.asarray(trunk), BODY)[0]:
                continue
            g, q, hit = _gain(p, [0.0, 0.48], trunk, deer=False, size=40.0)
            if hit and g >= DP["block"] and math.hypot(q[0] - 20.0, q[1] - 20.0) < 5.0:
                nv, c, st, used, start, _ = _one(p, [0.0, 0.48], trunk, deer=False, size=40.0, walls=wl)
                assert used and start
                _, q2, _ = _gain(p, nv, trunk, deer=False, size=40.0)
                assert math.hypot(q2[0] - 20.0, q2[1] - 20.0) >= 5.0
                assert not _one(p, [0.0, 0.48], trunk, deer=False, size=40.0)[3]     # 원이 없으면 막힘이 아니다
                found += 1
    assert found > 0


def _path(p, goal, sp, discs, detour, n=80, deer=True, size=20.0):
    p = np.asarray(p, float)
    d = np.asarray(discs, float).reshape(-1, 3)
    st = [np.zeros(1, dtype=np.int64) for _ in range(3)]
    for _ in range(n):
        to = np.asarray(goal) - p
        nn = math.hypot(*to)
        if nn <= sp:
            return True
        v = to / nn * sp
        if detour:
            v = detour_moves(p[None, :], v[None, :], *st, d, BODY, size, deer, DP)[0][0]
        q0 = np.clip(p + v, 0.0, size) if deer else p + v
        p = obstacle_slide(p[None, :], q0[None, :], d, BODY, size if deer else None)[0][0]
    return False


def test_goes_around_v_wedge_and_rock():
    """V 자(두 줄기 몸 여유가 겹침)·바위 너머 목표: 돌아가면 닿고, 미끄러짐만이면 못 닿는다."""
    pair = [[10.0, 10.0, 0.1], [10.0, 10.45, 0.1]]
    for sp, deer, stuck in ((0.24, True, True), (0.6, True, False), (0.48, False, True)):
        assert _path([8.0, 10.225], [13.0, 10.225], sp, pair, True, deer=deer)
        # 뛰는 사슴(한 스텝 1.2 m)은 미끄러짐만으로도 겹친 몸 여유를 비껴 지나간다 — 걷는 사슴·늑대는 V 자에 낀다
        assert _path([8.0, 10.225], [13.0, 10.225], sp, pair, False, deer=deer) != stuck
    rock = [[10.0, 10.0, 0.7]]
    assert _path([7.0, 10.0], [13.0, 10.0], 0.24, rock, True)
    assert not _path([7.0, 10.0], [13.0, 10.0], 0.24, rock, False)


# --------------------------------------------------------------------- #
# 세계
# --------------------------------------------------------------------- #


def test_rollout_invariants_and_no_stuck():
    """장애물 거울(돌아가기 켬) R1b 900 스텝 두 세계: 원판 안·무대 밖 0, 돌아가기를 쓴다, 끼임 도구로 원판 곁 끼임 0(사슴·늑대)."""
    if not R1_MODEL.exists():
        pytest.skip("R1b 모델 없음")
    sc = _module("_stuck_check_for_detour", ROOT / "results" / "v3" / "wild2" / "stuck_check.py")
    cfg = sc.build_cfg(OBST, [])
    for seed in (32087, 32088):
        r = sc.one(dict(cfg=cfg, seed=seed, steps=900))
        assert r["deer_events"] == [] and [e for e in r["wolf_events"] if not e["wall"]] == [], (seed, r["deer_events"], r["wolf_events"])
        assert r["detour"]["deer_used"] > 0 and r["detour"]["wolf_used"] > 0 and r["detour"]["deer_fail"] <= r["detour"]["deer_start"]
    w = World(load_v2_config(OBST).replace(N=48), seeds=[32089])
    rng = np.random.default_rng(32089)
    for _ in range(300):
        a = rng.integers(0, 3, (48, 1)).astype(np.float64)
        a[a == 2] = float(rep.HIDE)
        drop0 = w.pack_drop.copy()
        w.step(a)
        assert not w.pack_help[drop0 > 0].any()                          # 그만둔 늑대는 남은 스텝 동안 돕지 않는다
        assert not obstacle_inside(w.pos, w.obstacles, BODY).any() and not obstacle_inside(w.pred_pos, w.obstacles, BODY).any()
        assert (w.pos >= 0).all() and (w.pos <= w.size).all() and (w.pred_pos >= 0).all() and (w.pred_pos <= w.size).all()
        assert (w.det_left >= 0).all() and (w.det_left < DP["steps"]).all() and set(np.unique(w.det_side)) <= {-1, 0, 1}


def test_help_drop_scenes():
    """골든 한 스텝 장면: 돕다 막힌 늑대가 생기고(그만둠 > 0), 그만둔 늑대는 그 스텝에 돕지 않았다."""
    ex = _module("_export_golden_v3_detour", ROOT / "export_golden_v3_detour.py")
    steps, _ = ex.step_scenes()
    assert sum(int(t["drop"].sum()) for t in steps) > 0
    for t in steps:
        assert not t["help"][t["pdrop"] > 0].any()
        assert (t["pdrop1"][t["drop"]] == DP["help_drop"]).all()
    assert sum(int(t["used"].sum()) for t in steps) > 0


# --------------------------------------------------------------------- #
# C++ 골든 (export_golden_v3_detour.py → AI/Policy/DetourGoldenVectorsV3.h, 검사 본문 Tests/DetourGoldenCheckV3.h)
# --------------------------------------------------------------------- #


def test_detour_golden_header_is_fresh():
    """언리얼 모듈의 DetourGoldenVectorsV3.h 는 지금 코드로 다시 만든 헤더와 바이트 단위로 같다."""
    path = UE_POLICY / "DetourGoldenVectorsV3.h"
    if not path.exists():
        pytest.skip("언리얼 모듈 돌아가기 골든 헤더 없음")
    ex = _module("_export_golden_v3_detour2", ROOT / "export_golden_v3_detour.py")
    assert path.read_bytes() == ex.build_header().encode("utf-8")


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")
def test_cpp_detour_matches_golden_with_gpp(tmp_path):
    """언리얼 모듈의 EcoThreatModel.h·EcoWorldV3.h·돌아가기 골든 헤더를 그대로 g++ 로 컴파일해 대조한다(UE 시험 Policy.V3.Obstacle.DetourGolden 과 같은 검사 본문)."""
    if not (UE_POLICY / "DetourGoldenVectorsV3.h").exists():
        pytest.skip("언리얼 모듈 돌아가기 골든 헤더 없음")
    exe = tmp_path / ("detour_v3.exe" if sys.platform == "win32" else "detour_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-Wno-unused-parameter", "-I", str(UE_POLICY),
                            str(CPP_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
