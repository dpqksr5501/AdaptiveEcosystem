"""야생 2단계 2 — 늑대 무리·협동 사냥(기능 wild_pack(30), 설정 configs/v3_wild2_pack_mirror.yaml) (10-17 사용자 '추천대로 끄고 2~4번 진행해',
명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md, 정의는 env_v2/world.py 모듈 docstring '야생 2단계' 2).

비트 동일: 끈 세계는 직전 커밋(1675861)의 코드와 궤적·통계·v1 난수 상태·기능 스트림이 같다(야생 1·2단계 거울·R3 설정, R1b 롤아웃 포함).
새 설정에서 wild_pack 을 끄고 늑대를 2 로 두면 v3_wild2_mirror.yaml(1 은신처 먹이 부족 켬)과 같다(10-17 고침 — 처음에는 먹이 부족을 빼고
v3_wild1_mirror.yaml 과 견줬다).
규칙 단위 시험: pack_goals 손 장면(은신처 문·도주선 앞·기다림·서 있는 사슴·join_r 밖·같은 거리·맵 가장자리·반경 0 원), 롤아웃에서 돕는 늑대는 사냥 중이고
전력으로 달리지 않으며(먹기·배부름·잠·돌진 아님) 목표 쪽으로 기본 속력으로 가거나 멈춰 사슴 쪽을 본다, 늑대는 은신처 원(반지름 + 몸 여유)에 들지 않는다,
통계의 맞춤. 시드는 탐색 32084~32089 만 쓴다.
현실 근거: 늑대 무리 사냥 성공은 4 마리까지 는다(MacNulty 외 2012), 늑대는 길목에 떨어져 기다린다(Gable 외 2024).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import json
import shutil
import subprocess
import sys

import numpy as np
import pytest
import yaml

from env.config import ROOT
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.steering import EPS
from env_v2.features import features_of
from env_v2.world import PT_CHASER, PT_STALKER, ST_POUNCE, World, _wild_pack_params, pack_goals

CFG = ROOT / "configs"
WILD1 = CFG / "v3_wild1_mirror.yaml"
WILD2 = CFG / "v3_wild2_mirror.yaml"
PACK = CFG / "v3_wild2_pack_mirror.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "1675861"              # 야생 2단계 2 직전 커밋(은신처 먹이 부족 C++) — 비트 동일 기준
WP = dict(join_r=60.0, lead=6.0, door_r=15.0, door_cos=0.5, wait_r=1.0)

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _tum():
    spec = importlib.util.spec_from_file_location("_tum_for_pack", ROOT / "tests" / "test_unreal_mirror.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _wolves(cfg, n):
    return cfg.replace(rand=dict(cfg.rand, predator_count=[n, n]))


def _graze(w):
    return np.full((w.N, 1), float(rep.GRAZE))


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


def test_pack_config_is_wild2_plus_pack():
    """v3_wild2_pack_mirror.yaml = v3_wild2_mirror.yaml(= v3_wild1_mirror.yaml + 은신처 먹이 부족) + 늑대 4 + wild_pack 블록(version 만 다르다).
    은신처 먹이 부족은 켠다 — 사용자 결정 '은신처는 안전하지만 먹이가 적다'(10-14·10-15). 10-17 고침: 처음에는 사용자 말 '추천대로 끄고'를 잘못 읽어 뺐다."""
    w1 = yaml.safe_load(WILD1.read_text(encoding="utf-8"))
    a = yaml.safe_load(WILD2.read_text(encoding="utf-8"))
    b = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    assert set(a["features"]) - set(w1["features"]) == {"realism_cover_food"}
    assert a["version"] == "3.wild2" and b["version"] == "3.wild2pack"
    fa, fb = a.pop("features"), b.pop("features")
    a.pop("version"), b.pop("version")
    assert a["overrides"]["rand"]["predator_count"] == [2, 2] and b["overrides"]["rand"]["predator_count"] == [4, 4]
    b["overrides"]["rand"]["predator_count"] = [2, 2]
    assert a == b
    assert set(fb) - set(fa) == {"wild_pack"}
    assert fb["realism_cover_food"] == dict(enabled=True, cap_frac=0.15, regen_frac=0.15)
    assert all(fa[k] == fb[k] for k in fa)
    assert fb["wild_pack"] == dict(enabled=True, **WP)


def test_pack_world_has_four_wolves_in_training_range():
    """늑대 4 = 잠행 2·추격 2(슬롯 번갈아), 네 모서리 시작, 모두 주행성·근접. 학습 범위(보통 위협 2~12, 잠행 30~70%) 안이다."""
    w = World(load_v2_config(PACK).replace(N=32), seeds=[32084])
    assert w.M == 4 and w.M_base == 4
    assert w.pred_type.tolist() == [PT_STALKER, PT_CHASER, PT_STALKER, PT_CHASER]
    assert w.threat_p_stalk == 0.5 and w.stage_complete
    assert not w.pred_ranged.any() and not w.pred_nocturnal.any()
    s = w.size
    np.testing.assert_allclose(w.pred_pos, [[0.9 * s, 0.9 * s], [0.1 * s, 0.1 * s], [0.9 * s, 0.1 * s], [0.1 * s, 0.9 * s]])


def test_pack_off_two_wolves_equals_wild2():
    """wild_pack 을 끄고 늑대를 2 로 둔 새 설정 = 야생 2단계 1 거울(은신처 먹이 부족 켬 — 궤적·통계·사냥 셈)."""
    c1 = load_v2_config(WILD2).replace(N=32)
    c2 = _wolves(_with(load_v2_config(PACK).replace(N=32), wild_pack=dict(enabled=False)), 2)
    w1, w2 = World(c1, seeds=[32085]), World(c2, seeds=[32085])
    for _ in range(300):
        a = _graze(w1)
        for x, y in zip(w1.step(a), w2.step(a)):
            np.testing.assert_array_equal(x, y)
    for k in ("pos", "energy", "food", "food_cap", "pred_pos", "pred_head", "pred_cd"):
        np.testing.assert_array_equal(getattr(w1, k), getattr(w2, k))
    assert json.dumps(w1.hunt_stats()) == json.dumps(w2.hunt_stats())
    with pytest.raises(ValueError, match="pack_stats"):
        w2.pack_stats()


def test_pack_params_checked():
    base = load_v2_config(PACK).replace(N=8)
    for kw in (dict(join_r=0.0), dict(lead=-1.0), dict(door_r=-0.5), dict(door_cos=1.5), dict(wait_r=-1.0)):
        with pytest.raises(ValueError, match="wild_pack"):
            World(_with(base, wild_pack=kw), seeds=[32084])
    f = features_of(_with(base, threats=dict(enabled=False)))
    with pytest.raises(ValueError, match="wild_pack 은 threats"):
        _wild_pack_params(f.params("wild_pack"), f)


# --------------------------------------------------------------------- #
# pack_goals 손 장면
# --------------------------------------------------------------------- #


def _goal(wq, leader, helper, tgt, p, disp, cov=((40.0, 40.0, 6.0),), margin=0.5, size=60.0, wp=None, whead=None):
    wq = np.asarray(wq, dtype=np.float64)
    M = len(wq)
    cov = np.asarray(cov, dtype=np.float64).reshape(-1, 3)
    return pack_goals(wq, np.tile([1.0, 0.0], (M, 1)) if whead is None else np.asarray(whead, dtype=np.float64),
                      np.asarray(leader, dtype=bool), np.asarray(helper, dtype=bool), np.asarray(tgt), np.asarray(p, dtype=np.float64),
                      np.asarray(disp, dtype=np.float64), cov[:, :2], cov[:, 2], margin, size, WP if wp is None else wp)


def test_pack_goal_door():
    """사슴이 은신처 쪽으로 달리면 돕는 늑대는 그 은신처의 문(반지름 + 몸 여유, 사슴 쪽 둘레)으로 간다."""
    hp, wt, dr, prey, dv = _goal([[20.0, 30.0], [50.0, 10.0]], [True, False], [False, True], [0, 0], [[25.0, 40.0]], [[0.6, 0.0]])
    assert hp.tolist() == [False, True] and dr[1] and not wt[1] and prey[1] == 0
    gx, gy = 40.0 - 6.5, 40.0                           # 문 = c − (r + m)·(c − p)/|c − p|, 사슴이 정확히 서쪽
    v = np.array([gx - 50.0, gy - 10.0])
    np.testing.assert_allclose(dv[1], v / np.linalg.norm(v), rtol=0, atol=1e-15)


def test_pack_goal_ahead_and_wait():
    """은신처가 없거나 각이 밖이면 도주선 앞 lead. 목표가 wait_r 안이면 멈춰 사슴 쪽을 본다."""
    # 사슴이 은신처 반대쪽(서쪽)으로 달린다 → 앞 6 단위 (19, 40)
    hp, wt, dr, prey, dv = _goal([[30.0, 30.0], [10.0, 40.0]], [True, False], [False, True], [0, 0], [[25.0, 40.0]], [[-0.6, 0.0]])
    assert hp[1] and not dr[1] and not wt[1]
    np.testing.assert_allclose(dv[1], [1.0, 0.0], atol=1e-15)          # (19, 40) − (10, 40) 방향
    # 목표 바로 곁(0.5 단위)이면 기다림: 방향 = 사슴 쪽(동쪽), 목표 쪽이 아니다
    hp, wt, dr, prey, dv = _goal([[30.0, 30.0], [19.0, 40.5]], [True, False], [False, True], [0, 0], [[25.0, 40.0]], [[-0.6, 0.0]])
    assert hp[1] and wt[1]
    v = np.array([25.0 - 19.0, 40.0 - 40.5])
    np.testing.assert_allclose(dv[1], v / np.linalg.norm(v), atol=1e-15)


def test_pack_goal_still_deer_uses_leader_side():
    """서 있는 사슴(이동 0)의 도주 방향 = 앞장 늑대에서 사슴 쪽."""
    hp, wt, dr, prey, dv = _goal([[25.0, 30.0], [10.0, 10.0]], [True, False], [False, True], [0, 0], [[25.0, 36.0]], [[0.0, 0.0]], cov=())
    assert hp[1] and not dr[1]
    g = np.array([25.0, 42.0])                         # p + 6·(0, 1)
    v = g - [10.0, 10.0]
    np.testing.assert_allclose(dv[1], v / np.linalg.norm(v), atol=1e-15)


def test_pack_goal_choice_and_limits():
    """join_r 밖이면 돕지 않는다. 가장 가까운 쫓기는 사슴, 같은 거리면 앞 슬롯 앞장. 목표는 무대 안으로 자른다. 반경 0 원은 건너뛴다.
    앞장·돕는 늑대가 아닌 늑대·앞장 자신은 그대로다."""
    wp = dict(WP, join_r=5.0)
    hp, *_ = _goal([[0.0, 0.0], [30.0, 30.0]], [True, False], [False, True], [0, 0], [[10.0, 0.0]], [[0.6, 0.0]], wp=wp)
    assert not hp.any()
    # 두 앞장이 서로 다른 사슴을 쫓고 돕는 늑대에서 같은 거리 → 앞 슬롯(0)의 사슴
    hp, wt, dr, prey, dv = _goal([[0.0, 0.0], [5.0, 5.0], [30.0, 30.0]], [True, True, False], [False, False, True], [0, 1, 0],
                                 [[30.0, 35.0], [30.0, 25.0]], [[0.0, 0.6], [0.0, -0.6]], cov=())
    assert prey.tolist() == [-1, -1, 0] and hp.tolist() == [False, False, True]
    # 맵 가장자리: 앞 6 단위가 맵 밖이면 자른다 → (60, 30)
    hp, wt, dr, prey, dv = _goal([[30.0, 20.0], [50.0, 50.0]], [True, False], [False, True], [0, 0], [[57.0, 30.0]], [[0.6, 0.0]], cov=())
    v = np.array([60.0 - 50.0, 30.0 - 50.0])
    np.testing.assert_allclose(dv[1], v / np.linalg.norm(v), atol=1e-15)
    # 반경 0 원(언리얼의 지워진 은신처)은 문이 아니다
    hp, wt, dr, prey, dv = _goal([[20.0, 30.0], [50.0, 10.0]], [True, False], [False, True], [0, 0], [[25.0, 40.0]], [[0.6, 0.0]],
                                 cov=((40.0, 40.0, 0.0),))
    assert hp[1] and not dr[1]
    # 돕는 늑대가 없으면 아무도 바뀌지 않는다
    hp, *_ = _goal([[20.0, 30.0], [50.0, 10.0]], [True, False], [False, False], [0, 0], [[25.0, 40.0]], [[0.6, 0.0]])
    assert not hp.any()


# --------------------------------------------------------------------- #
# 롤아웃
# --------------------------------------------------------------------- #


def test_pack_rollout_roles_and_shelter():
    """늑대 무리 거울 세계 1800 스텝(R1b 두뇌가 없으면 먹기만): 돕는 늑대는 늑대이고 사냥 중이며 전력으로 달리지 않는다(먹기·배부름·잠·돌진 아님).
    기다리는 늑대는 제자리에서 사슴 쪽을 보고, 움직이는 돕는 늑대는 벽·은신처에 닿지 않으면 목표 방향 그대로 간다. 늑대 중심은 은신처 원(반지름 +
    몸 여유) 안에 들지 않는다. 통계 맞춤: 협동 포획 ≤ 늑대 포획 = 사냥 성공 + 사냥 밖."""
    cfg = load_v2_config(PACK).replace(N=128)
    w = World(cfg, seeds=[32086])
    pol = None
    if R1_MODEL.exists():
        from env_v2 import rollout as ro
        pol = ro.build_policy({"kind": "rep_learned", "path": str(R1_MODEL)}, 32086)
        ro.forward_bind(pol, w)
    rr = w.cov_r + w._zw_m
    helped = waited = moved_ok = 0
    for _ in range(1800):
        q0, h0 = w.pred_pos.copy(), w.pred_head.copy()
        sat0 = w.pred_sat.copy()
        a = _graze(w) if pol is None else np.asarray(pol(w.observe()), dtype=np.float64)
        w.step(a)
        hp = w.pack_help
        if hp.any():
            helped += int(hp.sum())
            assert not (w.pred_running & hp).any()
            assert not (w.pred_asleep & hp).any()
            assert not (w.pred_sated & hp).any()
            st = w.stalk_state
            assert not (hp & (w.pred_type == PT_STALKER) & (st == ST_POUNCE)).any()
            for m in np.flatnonzero(hp):
                i = int(w.pack_prey[m])
                assert i >= 0
                if w.pack_wait[m]:
                    waited += 1
                    np.testing.assert_array_equal(w.pred_pos[m], q0[m])
                    v = w.pos[i] - q0[m]
                    n = float(np.sqrt(v @ v))
                    if n > EPS:
                        np.testing.assert_allclose(w.pred_head[m], v / n, atol=1e-12)
                else:
                    d = w.pred_pos[m] - q0[m]
                    dn = float(np.sqrt(d @ d))
                    away = (np.sqrt(((w.pred_pos[m] - w.cov_c) ** 2).sum(1)) - rr).min() > 1.0
                    inside = (w.pred_pos[m] > 0.0).all() and (w.pred_pos[m] < w.size).all()
                    if dn > 1e-9 and away and inside:
                        # 기본 속력 × 박명 배수(0 이 아니면): 방향은 목표 쪽 = 스텝 뒤 heading
                        np.testing.assert_allclose(d / dn, w.pred_head[m], atol=1e-9)
                        assert dn <= float(w.pred_speed[m]) + 1e-12
                        moved_ok += 1
        assert sat0.shape == w.pred_sat.shape
        de = np.sqrt(((w.pred_pos[:, None, :] - w.cov_c[None, :, :]) ** 2).sum(-1)) - rr[None, :]
        assert (de >= -1e-9).all()
    ps, hs = w.pack_stats(), w.hunt_stats()
    assert ps["wolf_steps"] == 1800 * 4 and helped == ps["help_n"] and ps["wait_n"] <= ps["help_n"] and ps["door_n"] <= ps["help_n"]
    assert ps["catches"] == hs["success"] + hs["outside"] and ps["pack_catches"] <= ps["catches"]
    assert ps["lead_n"] > 0 and helped > 0 and moved_ok > 0


def test_pack_moves_wolves_differently_than_off():
    """켜면 늑대 궤적이 끈 판과 갈린다(규칙이 실제로 돈다) — 같은 시드·같은 사슴 행동(먹기)으로."""
    c_on = load_v2_config(PACK).replace(N=64)
    c_off = _with(c_on, wild_pack=dict(enabled=False))
    w1, w0 = World(c_on, seeds=[32087]), World(c_off, seeds=[32087])
    diverged = False
    for _ in range(1800):
        w1.step(_graze(w1))
        w0.step(_graze(w0))
        if w1.pack_help.any():
            diverged = diverged or not np.array_equal(w1.pred_pos, w0.pred_pos)
    assert diverged


# --------------------------------------------------------------------- #
# 비트 동일
# --------------------------------------------------------------------- #


def test_pack_bit_identical_to_head(tmp_path):
    """직전 코드(1675861)와: 야생 1·2단계 거울·R3 설정의 궤적·통계·난수·관측 이름·기능 스트림이 같다(R1b 롤아웃 포함). wild_pack 은 끈 세계에서 길이 없다."""
    tum = _tum()
    old_root = tum._archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(tum.TRACE_SRC % dict(keys=tum.KEYS, stats=tum.STATS), encoding="utf-8")
    jobs = [dict(config="configs/v3_r3_on.yaml", seed=32088, steps=250, policy="rand"),
            dict(config="configs/v3_wild1_mirror.yaml", seed=32089, steps=400, policy="rand"),
            dict(config="configs/v3_wild2_mirror.yaml", seed=32084, steps=400, policy="rand")]
    if R1_MODEL.exists():
        jobs.append(dict(config="configs/v3_wild1_mirror.yaml", seed=32085, steps=400, policy="model", model=str(R1_MODEL)))
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


def test_join_radius_is_math_distance():
    """join_r 경계: 실거리가 꼭 join_r 이면 돕는다(≤)."""
    wp = dict(WP, join_r=5.0)
    hp, *_ = _goal([[0.0, 0.0], [10.0, 0.0]], [True, False], [False, True], [0, 0], [[15.0, 0.0]], [[0.6, 0.0]], cov=(), wp=wp)
    assert hp[1]


# --------------------------------------------------------------------- #
# C++ 골든 (export_golden_v3_pack.py → AI/Policy/PackGoldenVectorsV3.h, 검사 본문 Tests/PackGoldenCheckV3.h)
# --------------------------------------------------------------------- #

UE_POLICY = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
PACK_CPP_MAIN = ROOT / "tests" / "cpp" / "pack_v3_main.cpp"


def _exporter():
    spec = importlib.util.spec_from_file_location("_export_golden_v3_pack", ROOT / "export_golden_v3_pack.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pack_golden_header_is_fresh():
    """언리얼 모듈의 PackGoldenVectorsV3.h 는 지금 코드로 다시 만든 헤더와 바이트 단위로 같다."""
    path = UE_POLICY / "PackGoldenVectorsV3.h"
    if not path.exists():
        pytest.skip("언리얼 모듈 무리 골든 헤더 없음")
    assert path.read_bytes() == _exporter().build_header().encode("utf-8")


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")
def test_cpp_pack_matches_golden_with_gpp(tmp_path):
    """언리얼 모듈의 EcoThreatModel.h·무리 골든 헤더를 그대로 g++ 로 컴파일해 대조한다(UE 시험 Policy.V3.Pack.Golden 과 같은 검사 본문)."""
    if not (UE_POLICY / "PackGoldenVectorsV3.h").exists():
        pytest.skip("언리얼 모듈 무리 골든 헤더 없음")
    exe = tmp_path / ("pack_v3.exe" if sys.platform == "win32" else "pack_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-I", str(UE_POLICY), str(PACK_CPP_MAIN),
                            "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
