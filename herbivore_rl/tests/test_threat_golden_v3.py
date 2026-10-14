"""v3 위협 모델 골든 (`export_golden_v3_threat.py`) — 파이썬 학습 세계의 위협 스텝 → 언리얼 C++ `EcoThreatModel.h` 다리의 검증.

헤더를 임시 폴더에 다시 만들어 (1) 언리얼 모듈에 들어간 헤더와 바이트 단위로 같은지(결정성·최신), (2) 기록 장치가 세계 궤적을 바꾸지
않는지, (3) 헤더의 모든 사례가 참조 스텝(C++ Step 의 파이썬 거울)과 맞는지, (4) 끝 사례·무대 열이 계약의 뜻(돌진 문턱 6 정확히 같음,
쿨다운 5 = 4스텝 쉼, 해 질 녘 잠 등)대로 world.py 에서 나왔는지, (5) 위협 종류·상태 전이를 모두 덮는지, (6) 판정 시드를 쓰지 않는지
본다. g++ 가 있으면 언리얼 모듈의 `EcoThreatModel.h` 를 그대로 컴파일해 골든과 대조한다(`tests/cpp/threat_v3_main.cpp`).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import export_golden_v3_threat as ex
from env_v2 import repertoire as rep
from env_v2 import world as W
from env_v2.config import load_v2_config

ROOT = Path(__file__).resolve().parent.parent
CPP_MAIN = ROOT / "tests" / "cpp" / "threat_v3_main.cpp"
MODEL_H = ex.UE_POLICY_DIR / "EcoThreatModel.h"
UE_TEST = ex.UE_POLICY_DIR / "Tests" / "EcoThreatModelV3Test.cpp"

needs_model = pytest.mark.skipif(not ex.DEFAULT_MODEL.exists(), reason=f"{ex.DEFAULT_MODEL} 없음 (ckpt 는 저장소에 없다)")
needs_gpp = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")


# --------------------------------------------------------------------- #
# 헤더 읽기
# --------------------------------------------------------------------- #

_ARRAY = re.compile(r"inline constexpr (?:const )?([\w:]+)\*? (\w+)\[(\w+)\] = \{(.*?)\};", re.S)
_SCALAR = re.compile(r"inline constexpr ([\w:]+) (\w+) = ([^;{]+);")


def parse_header(path: Path) -> dict:
    """생성 헤더 → 이름: 값. double 은 float64, 정수는 int64, 문자열 배열은 str 목록."""
    txt = Path(path).read_text(encoding="utf-8")
    out = {}
    for ctype, name, _n, body in _ARRAY.findall(txt):
        body = re.sub(r"//[^\n]*", "", body)
        if ctype == "char":
            out[name] = re.findall(r'"([^"]*)"', body)
            continue
        toks = [t.strip() for t in body.replace("\n", " ").split(",") if t.strip()]
        if ctype == "double":
            out[name] = np.array([float(t) for t in toks], dtype=np.float64)
        else:
            out[name] = np.array([int(t) for t in toks], dtype=np.int64)
    for ctype, name, val in _SCALAR.findall(txt):
        val = val.strip()
        if ctype == "double":
            out[name] = float(val)
        elif ctype == "bool":
            out[name] = val == "true"
        elif re.fullmatch(r"-?\d+", val):
            out[name] = int(val)
    return out


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    if not ex.DEFAULT_MODEL.exists():
        pytest.skip(f"{ex.DEFAULT_MODEL} 없음")
    out = tmp_path_factory.mktemp("threat_v3")
    r = ex.export(ex.DEFAULT_MODEL, ex.DEFAULT_CONFIG, out)
    r["out"] = out
    return r


@pytest.fixture(scope="module")
def golden(exported):
    return parse_header(exported["out"] / ex.HEADER)


@pytest.fixture(scope="module")
def consts():
    return ex.cfg_constants(load_v2_config(ex.DEFAULT_CONFIG))


def _case_inputs(g: dict, n: int) -> dict:
    """헤더 사례 n → 참조 스텝 입력 (C++ 하네스 Build 와 같은 읽기)."""
    b, k = int(g["kPreyBegin"][n]), int(g["kPreyCount"][n])
    sl = slice(b, b + k)
    ranged = bool(g["kSpecRanged"][n])
    return dict(
        spec=dict(type=int(g["kSpecType"][n]), ranged=ranged, noct=bool(g["kSpecNocturnal"][n]),
                  base_speed=float(g["kSpecBaseSpeed"][n]), catch_r=float(g["kSpecCatchR"][n])),
        st=dict(pos=tuple(g["kPrePos"][2 * n:2 * n + 2]), head=tuple(g["kPreHead"][2 * n:2 * n + 2]),
                **{c: int(g["kPreInt"][5 * n + i]) for i, c in enumerate(ex.INT_COLS)}),
        prey=dict(x=g["kPreyPos"][2 * b:2 * (b + k):2], y=g["kPreyPos"][2 * b + 1:2 * (b + k):2],
                  beh=g["kPreyBehavior"][sl], arrived=g["kPreyHideArrived"][sl].astype(bool),
                  in_cover=g["kPreyInCover"][sl].astype(bool), alive=np.ones(k, dtype=bool)),
        roll=g["kPreyRoll"][sl] if ranged else None, dark=float(g["kDark"][n]), size=float(g["kWorldSize"][n]),
        turn=float(g["kTurn"][n]), mode_u=(float(g["kModeU"][2 * n]), float(g["kModeU"][2 * n + 1])))


def _run(c, inp):
    return ex.ref_step(c, inp["spec"], inp["st"], inp["prey"], inp["dark"], inp["size"], inp["turn"], inp["mode_u"],
                       inp["roll"])


def _bits(out) -> int:
    return sum(1 << i for i, b in enumerate(ex.OUT_BITS) if out[b])


def _mismatch(g, n, post, out, tol) -> list:
    bad = []
    for i, c in enumerate(ex.INT_COLS):
        if post[c] != g["kPostInt"][5 * n + i]:
            bad.append(c)
    for key, arr in (("pos", "kPostPos"), ("head", "kPostHead"), ("vel", "kPostVel")):
        if np.abs(np.array(post[key]) - g[arr][2 * n:2 * n + 2]).max() > tol:
            bad.append(key)
    if _bits(out) != g["kOutBits"][n]:
        bad.append("bits")
    if out["target"] != g["kOutTarget"][n] or out["caught"] != g["kOutCaught"][n]:
        bad.append("target/caught")
    if abs(out["d_t"] - g["kOutTargetPerceived"][n]) > tol or abs(out["speed"] - g["kOutSpeed"][n]) > tol:
        bad.append("d_t/speed")
    return bad


# --------------------------------------------------------------------- #
# 결정성·최신
# --------------------------------------------------------------------- #


@needs_model
def test_regenerated_header_matches_unreal_module_bytes(exported):
    """다시 만든 헤더가 언리얼 모듈의 헤더와 바이트 단위로 같다 — 다른 실행(다른 프로세스)과 같은 결과이고, 모듈 헤더가 최신이다.
    다르면 `python export_golden_v3_threat.py` 로 모듈 헤더를 다시 낸다."""
    ue = ex.UE_POLICY_DIR / ex.HEADER
    if not ue.exists():
        pytest.skip(f"언리얼 모듈 헤더 없음: {ue}")
    assert (exported["out"] / ex.HEADER).read_bytes() == ue.read_bytes(), "골든 헤더가 다르다 — 결정적이지 않거나 낡았다"


@needs_model
def test_header_writer_is_deterministic(exported, tmp_path):
    """같은 골든으로 두 번 쓰면 바이트가 같다(시각·절대 경로를 적지 않는다)."""
    for k in (1, 2):
        d = tmp_path / str(k)
        d.mkdir()
        ex.write_header(d / ex.HEADER, exported["golden"], exported["meta"])
    a, b = (tmp_path / "1" / ex.HEADER).read_bytes(), (tmp_path / "2" / ex.HEADER).read_bytes()
    assert a == b == (exported["out"] / ex.HEADER).read_bytes()
    txt = a.decode("utf-8")
    assert "자동 생성. 수정 금지." in txt
    assert ":/" not in txt and ":\\" not in txt, "절대 경로가 헤더에 들어갔다"
    assert not re.search(r"\b(inf|nan)\b", re.sub(r"//[^\n]*", "", txt)), "유한하지 않은 값이 헤더에 들어갔다"


# --------------------------------------------------------------------- #
# 기록 장치·참조 스텝
# --------------------------------------------------------------------- #


def _hand_rule(w) -> np.ndarray:
    """기록 장치 시험용 사슴: 위협이 보이면 FREEZE, 가까우면(관측 거리 < 0.25) HIDE, 아니면 GRAZE (정수 요청)."""
    o = w.observe()
    seen = o[:, 1] > 0
    req = np.where(seen & (o[:, 2] < 0.25), rep.HIDE, np.where(seen, rep.FREEZE, rep.GRAZE))
    return req.astype(np.float64)[:, None]


@pytest.mark.parametrize("seed", [20000, 20001])
def test_recorder_does_not_change_trajectory(seed):
    """`Recorder` 로 감싼 세계와 감싸지 않은 세계가 비트 단위로 같은 궤적을 낸다(난수 소비·순서가 그대로다). 플레이어(20000)와
    원거리형(20001)이 있는 보정 시드."""
    cfg = load_v2_config(ex.DEFAULT_CONFIG)
    a, b = W.World(cfg, seeds=[seed]), W.World(cfg, seeds=[seed])
    rec = ex.Recorder(b)
    for _ in range(400):
        a.step(_hand_rule(a))
        b.step(_hand_rule(b))
    rec.detach()
    assert len(rec.records) == 400
    for name in ("pos", "head", "energy", "pred_pos", "pred_head", "pred_vel", "pred_cd", "stalk_state", "stalk_left",
                 "player_mode", "player_left", "food"):
        np.testing.assert_array_equal(getattr(a, name), getattr(b, name), err_msg=name)
    np.testing.assert_array_equal(a._rs.behavior, b._rs.behavior)
    assert a.rng.random() == b.rng.random()
    assert a.feature_rng("threats", 3).random() == b.feature_rng("threats", 3).random()


def test_reference_step_matches_world_on_hand_rule_rollout(consts):
    """참조 스텝이 world.py 위협 스텝과 같다 — 모델 없이 손 규칙 사슴으로 돈 기록의 모든 위협 스텝(전체 초식)에서."""
    cfg = load_v2_config(ex.DEFAULT_CONFIG)
    w = W.World(cfg, seeds=[20000])
    rec = ex.Recorder(w)
    for _ in range(300):
        w.step(_hand_rule(w))
    rec.detach()
    pool = ex.validate_records(consts, rec.records)      # 다르면 SystemExit
    assert len(pool) == 300 * w.M


def test_config_constants_match_cpp_defaults(consts):
    """참조 스텝 상수가 C++ FThreatConfig 기본값 줄과 같다 (헤더 없이, 소스 글자로)."""
    txt = MODEL_H.read_text(encoding="utf-8")
    body = re.search(r"struct FThreatConfig\n\t\{(.*?)\n\t\};", txt, re.S).group(1)
    for key, v in consts.items():
        m = re.search(rf"\b{key}(\[\d+\])? = ([^;]+);", body)
        assert m, f"FThreatConfig 에 {key} 가 없다"
        lit = m.group(2).strip()
        if isinstance(v, bool):
            assert lit == ("true" if v else "false"), key
        elif isinstance(v, tuple):
            got = [float(x) for x in lit.strip("{}").split(",")]
            assert got == [float(x) for x in v], key
        else:
            assert float(lit) == float(v), f"{key}: C++ {lit} != 파이썬 {v!r}"


@needs_model
def test_header_config_matches_python(golden, consts):
    for key, v in consts.items():
        name = "kCfg" + (key[1:] if isinstance(v, bool) else key)
        if isinstance(v, tuple):
            np.testing.assert_array_equal(golden[name], np.array(v, dtype=golden[name].dtype), err_msg=name)
        else:
            assert golden[name] == v, name


@needs_model
def test_header_cases_match_reference_step(golden, consts):
    """헤더의 모든 사례: 참조 스텝(C++ Step 의 파이썬 거울)이 헤더 기대(world.py 값)와 같다. 정수·판정 정확, 실수 1e-12.
    열은 참조 스텝 자기 출력을 이어 써도 같다."""
    g = golden
    n_case = g["kCaseCount"]
    bad = []
    for n in range(n_case):
        post, out, _ = _run(consts, _case_inputs(g, n))
        out = dict(out)
        why = _mismatch(g, n, post, out, ex.REF_TOL)
        if why:
            bad.append((n, why))
    assert not bad, f"참조 스텝이 헤더와 다르다: {bad[:5]}"
    for s in range(g["kSeqCount"]):
        carry = None
        for k in range(g["kSeqLength"][s]):
            n = int(g["kSeqBegin"][s]) + k
            inp = _case_inputs(g, n)
            if carry is not None:
                inp["st"] = carry
            post, out, _ = _run(consts, inp)
            assert not _mismatch(g, n, post, out, 1e-9), (g["kSeqNames"][s], k)
            carry = dict(pos=post["pos"], head=post["head"], **{c: post[c] for c in ex.INT_COLS})


# --------------------------------------------------------------------- #
# 끝 사례·무대 열의 뜻 (world.py 가 낸 값이 계약 문장과 맞는가)
# --------------------------------------------------------------------- #


def _edge(g, name) -> int:
    i = g["kEdgeNames"].index(name)
    return int(np.flatnonzero(g["kCaseEdge"] == i)[0])


def _o(g, n) -> dict:
    bits = int(g["kOutBits"][n])
    d = {b: bool(bits >> i & 1) for i, b in enumerate(ex.OUT_BITS)}
    d.update(target=int(g["kOutTarget"][n]), caught=int(g["kOutCaught"][n]), d_t=float(g["kOutTargetPerceived"][n]),
             speed=float(g["kOutSpeed"][n]), pos=tuple(g["kPostPos"][2 * n:2 * n + 2]),
             head=tuple(g["kPostHead"][2 * n:2 * n + 2]), pre_pos=tuple(g["kPrePos"][2 * n:2 * n + 2]),
             **{c: int(g["kPostInt"][5 * n + i]) for i, c in enumerate(ex.INT_COLS)})
    return d


@needs_model
def test_edge_cases_follow_contract(golden):
    """무대 끝 사례 (world.py 가 계산) — 문턱과 정확히 같은 거리, 행동별 은신 배수, 상태 기계 끝, 낮밤, 벽, 플레이어 모드."""
    g = golden
    E = lambda name: _o(g, _edge(g, name))       # noqa: E731
    hs, base = 0.6, 0.6 * ex.STAGE_MULT
    # 돌진·플레이어 돌진 시작은 체감 거리 ≤ 6 (정확히 같으면 시작)
    e = E("stalk_start_exact")
    assert e["pounce_start"] and e["ss"] == W.ST_POUNCE and e["sl"] == 11 and e["d_t"] == 6.0
    assert e["speed"] == pytest.approx(1.5 * hs)
    e = E("stalk_above")
    assert not e["pounce_start"] and e["ss"] == W.ST_ROAM and e["has_target"] and e["speed"] == pytest.approx(0.3 * hs)
    assert E("stalk_start_cover_graze")["pounce_start"] and E("stalk_start_cover_graze")["d_t"] == 6.0
    assert not E("stalk_freeze_far")["pounce_start"] and E("stalk_freeze_far")["d_t"] == pytest.approx(7.2)
    e = E("charge_start_exact")
    assert e["charge_start"] and e["pm"] == W.PM_CHARGE and e["pl"] == 19
    assert not E("charge_above")["charge_start"] and E("charge_above")["pm"] == W.PM_STALK
    # 포획: catch_d ≤ 반경 (정확히 같으면 잡는다), 원거리형은 roll < 0.02
    assert E("catch_exact")["caught"] == 0 and E("catch_exact")["cd"] == 5
    assert E("catch_above")["caught"] == -1 and E("catch_above")["has_target"]
    assert E("ranged_exact_pass")["caught"] == 0
    assert E("ranged_roll_equal_p")["caught"] == -1 and E("ranged_above_roll0")["caught"] == -1
    # 시야 14 (정확히 같으면 보인다), 시야각 150°
    assert E("view_exact")["has_target"] and not E("view_above")["has_target"] and E("view_above")["hunting"]
    assert E("fov_behind")["target"] == 1 and not E("fov_side_out")["has_target"]
    # 행동별 은신 배수 (포획은 cov 만, 표적 고르기는 det = max(cov, still 1.8))
    assert E("crouch_cover_catch_exact")["caught"] == 0 and E("crouch_cover_safe")["caught"] == -1
    assert E("crouch_outside")["caught"] == 0 and E("crouch_outside")["d_t"] == pytest.approx(0.9)
    assert E("hide_travel_cover")["caught"] == 0
    assert E("freeze_catch")["caught"] == 0 and E("freeze_catch")["d_t"] == pytest.approx(1.35)
    assert E("sleep_cover_catch")["caught"] == 0 and E("sleep_cover_safe")["caught"] == -1
    assert E("sleep_outside")["caught"] == 0 and E("sleep_outside")["d_t"] == pytest.approx(0.875 * 1.8)
    assert E("flee_cover_catch")["caught"] == 0 and E("graze_cover_safe")["caught"] == -1
    assert E("graze_cover_safe")["d_t"] == pytest.approx(1.125)
    assert E("freeze_vs_graze_target")["target"] == 1
    # 동점 = 낮은 색인
    for name in ("tie_target", "tie_target_swapped", "player_tie_target"):
        assert E(name)["target"] == 0, name
    for name in ("tie_catch", "player_tie_catch"):
        assert E(name)["caught"] == 0, name
    # 잠행형 상태 기계
    e = E("exhaust_end")
    assert e["ss"] == W.ST_ROAM and e["sl"] == 0 and not e["hunting"] and e["caught"] == -1
    assert e["speed"] == pytest.approx(0.2 * hs)
    assert E("exhaust_mid")["ss"] == W.ST_EXHAUST and E("exhaust_mid")["sl"] == 29
    e = E("pounce_final_miss")
    assert e["ss"] == W.ST_EXHAUST and e["sl"] == 30 and e["head"] == (1.0, 0.0) and e["speed"] == pytest.approx(0.2 * hs)
    e = E("pounce_final_catch")
    assert e["caught"] == 0 and e["ss"] == W.ST_ROAM and e["sl"] == 0 and e["cd"] == 5
    e = E("pounce_dash_blind")
    assert not e["has_target"] and e["ss"] == W.ST_POUNCE and e["sl"] == 4 and e["head"] == (1.0, 0.0)
    assert E("pounce_dash_catch")["caught"] == 0 and E("pounce_dash_catch")["ss"] == W.ST_ROAM
    e = E("stalker_roam_cooldown")
    assert not e["hunting"] and e["cd"] == 2 and e["speed"] == pytest.approx(base)     # 표적 없는 ROAM 은 기본 속력
    # 낮밤: d = 0.5 (해 질 녘·해 뜰 녘 전환 스텝)에 주행성은 잔다 — 움직이지 않고 잡지 않는다. 쿨다운은 줄어든다
    for name in ("dusk_asleep_chaser", "dawn_asleep_chaser", "ranged_asleep_dusk"):
        e = E(name)
        assert e["asleep"] and e["caught"] == -1 and e["speed"] == 0.0 and e["pos"] == e["pre_pos"], name
    assert E("dusk_asleep_chaser")["cd"] == 2
    d449 = W.daynight_phase(ex.CLOCK["dusk_before"], ex.STAGE_PERIOD, ex.STAGE_OFFSET, ex.STAGE_TW)[0]
    d20 = W.daynight_phase(ex.CLOCK["twilight"], ex.STAGE_PERIOD, ex.STAGE_OFFSET, ex.STAGE_TW)[0]
    assert 0.0 < d20 < d449 < 0.5
    assert E("dusk_before_twilight")["speed"] == pytest.approx(base * (1.0 - d449))
    assert E("twilight_wander")["speed"] == pytest.approx(base * (1.0 - d20))
    for name in ("nocturnal_night", "nocturnal_dusk"):
        assert not E(name)["asleep"] and E(name)["speed"] == pytest.approx(base), name
    assert E("ranged_nocturnal_night")["caught"] == 0
    for name in ("stalker_sleep_reset_pounce", "stalker_sleep_reset_exhaust"):
        e = E(name)
        assert e["asleep"] and e["ss"] == W.ST_ROAM and e["sl"] == 0, name
    assert not E("player_night")["asleep"] and E("player_night")["speed"] == pytest.approx(0.3 * hs)
    # 벽 반사
    e = E("wall_x")
    assert e["wall"] and e["pos"][0] == ex.STAGE_SIZE and e["head"][0] < 0
    e = E("wall_corner")
    assert e["wall"] and e["pos"] == (0.0, 0.0) and e["head"] == pytest.approx((0.6, 0.8))
    assert E("wall_chase")["wall"] and E("wall_chase")["caught"] == 0
    # 플레이어
    assert E("player_far")["target"] == 0 and E("player_far")["speed"] == pytest.approx(0.3 * hs)
    e = E("player_rest_end_stalk")
    assert e["new_mode"] and e["pm"] == W.PM_STALK and e["pl"] == 400 and e["caught"] == -1
    e = E("player_rest_end_wander")
    assert e["new_mode"] and e["pm"] == W.PM_WANDER and e["pl"] == 200
    e = E("player_mode_end")
    assert e["new_mode"] and e["pm"] == W.PM_STALK and e["pl"] == 300
    e = E("player_wander_end")
    assert e["new_mode"] and e["pm"] == W.PM_WANDER and e["pl"] == 250
    e = E("player_charge_final")
    assert e["pm"] == W.PM_REST and e["pl"] == 30 and e["speed"] == 0.0
    e = E("player_charge_catch")
    assert e["caught"] == 0 and e["pm"] == W.PM_REST and e["pl"] == 30 and e["cd"] == 30
    e = E("player_charge_cooldown")
    assert not e["hunting"] and e["cd"] == 2 and e["pl"] == 6 and e["head"] == (1.0, 0.0)
    e = E("player_wander_catch")
    assert e["caught"] == 0 and e["cd"] == 30 and e["pm"] == W.PM_WANDER and e["pl"] == 49
    assert E("player_rest_no_catch")["caught"] == -1 and E("player_rest_no_catch")["pl"] == 9
    # 쿨다운 1 은 이번 스텝 0 이라 잡고, 2 는 1 이라 못 잡는다
    assert E("chaser_cd1")["caught"] == 0 and E("chaser_cd2")["caught"] == -1 and E("chaser_cd2")["cd"] == 1
    assert E("player_cd1")["caught"] == 0 and E("player_cd1")["cd"] == 30 and E("player_cd2")["caught"] == -1
    # 같은 자리: 추격형은 못 보지만 잡는다, 플레이어는 표적·돌진 시작·heading 0·잡음
    e = E("zero_dist_chaser")
    assert not e["has_target"] and e["caught"] == 0
    e = E("zero_dist_player")
    assert e["charge_start"] and e["caught"] == 0 and e["head"] == (0.0, 0.0) and e["pm"] == W.PM_REST
    for name, t in (("wander_turn_max", 0.15), ("wander_turn_min", -0.15)):
        assert E(name)["head"] == pytest.approx((math.cos(t), math.sin(t)), abs=1e-12), name


@needs_model
def test_stage_sequences_follow_contract(golden):
    """무대 열: 쿨다운 5 의 뜻(잡음 → 4스텝 쉼 → 5번째 다시 잡음), 잠행형 한 주기(돌진 12 + 마지막 판정 1 → 탈진 30),
    플레이어 돌진 한 주기(돌진 20 + 멈춘 판정 1 → 휴식 30 → 새 모드), 해 질 녘·해 뜰 녘 잠."""
    g = golden

    def seq(name):
        s = g["kSeqNames"].index(name)
        return [_o(g, int(g["kSeqBegin"][s]) + k) for k in range(int(g["kSeqLength"][s]))]

    s = seq("chaser_cooldown5")
    assert [x["caught"] for x in s] == [0, -1, -1, -1, -1, 0, -1]
    assert [x["cd"] for x in s] == [5, 4, 3, 2, 1, 5, 4]
    assert [x["hunting"] for x in s] == [True, False, False, False, False, True, False]
    s = seq("stalker_cycle")
    assert [k for k, x in enumerate(s) if x["pounce_start"]] == [1, 44]
    assert [x["ss"] for x in s[1:13]] == [W.ST_POUNCE] * 12 and [x["sl"] for x in s[1:14]] == list(range(11, -1, -1)) + [30]
    assert s[13]["ss"] == W.ST_EXHAUST and all(x["ss"] == W.ST_EXHAUST for x in s[14:43])
    assert s[43]["ss"] == W.ST_ROAM and s[43]["sl"] == 0
    s = seq("player_cycle")
    assert [k for k, x in enumerate(s) if x["charge_start"]] == [1, 52]     # 새 잠행 모드에서 곧바로 다시 돌진
    assert s[20]["pm"] == W.PM_CHARGE and s[20]["pl"] == 0 and s[21]["pm"] == W.PM_REST and s[21]["speed"] == 0.0
    assert [k for k, x in enumerate(s) if x["new_mode"]] == [51]
    assert s[51]["pm"] == W.PM_STALK and s[51]["pl"] == 320
    assert all(not x["hunting"] for x in s[22:52])
    s = seq("dusk_chaser")
    assert [x["asleep"] for x in s] == [False, False, False, True, True, True]
    s = seq("dawn_stalker")
    assert [x["asleep"] for x in s] == [True, True, True, True, False, False]
    assert s[0]["ss"] == W.ST_ROAM and s[0]["sl"] == 0                     # 잠든 탈진 잠행형은 ROAM 으로


# --------------------------------------------------------------------- #
# 덮는 범위·시드
# --------------------------------------------------------------------- #


@needs_model
def test_golden_covers_every_threat_type_and_transition(golden, exported):
    """위협 종류 넷 모두 본 사례가 있고, 종류마다 상태·전이 표시가 모두 어딘가(본·열·끝)에 있다. 풀에 문턱 근처가 아닌 표시가 있으면
    본 묶음에도 있다."""
    g = golden
    kinds = g["kCaseKind"]
    flags = g["kCaseFlags"]
    keys = np.array(["player" if t == W.PT_PLAYER else "stalker" if t == W.PT_STALKER else ("ranged" if r else "chaser")
                     for t, r in zip(g["kSpecType"], g["kSpecRanged"])])
    pool = exported["stats"]["pool_flags"]
    for k in ex.TYPE_KEYS:
        assert ((keys == k) & (kinds == ex.KIND_MAIN)).sum() >= 20, k
        for f in ex.TYPE_FLAGS[k]:
            has = (keys == k) & ((flags & ex.FLAG[f]) != 0) & (kinds != ex.KIND_NEAR)
            assert has.any(), f"{k} 의 '{f}' 사례가 없다"
            if pool[k][f] > 0:
                assert (has & (kinds == ex.KIND_MAIN)).sum() >= min(3, pool[k][f]), f"{k} 의 '{f}' 본 사례가 적다"
    assert len(g["kEdgeNames"]) == g["kEdgeCount"] and set(g["kCaseEdge"][kinds == ex.KIND_EDGE]) == set(
        range(g["kEdgeCount"]))
    assert g["kSeqCount"] >= 10 and (kinds == ex.KIND_SEQ).sum() > 0 and (kinds == ex.KIND_STAGE_SEQ).sum() > 0
    # 본·롤아웃 열에는 문턱 근처가 없다. 끝 사례는 일부러 문턱과 정확히 같은 거리를 써서 표시가 붙을 수 있다
    assert (g["kCaseNear"][np.isin(kinds, (ex.KIND_MAIN, ex.KIND_SEQ))] == 0).all()
    assert (g["kCaseNear"][kinds == ex.KIND_NEAR] != 0).all()
    assert (g["kCaseNear"][kinds == ex.KIND_EDGE] != 0).any()


@needs_model
def test_golden_uses_calibration_seeds_only(golden):
    roll = np.isin(golden["kCaseKind"], (ex.KIND_MAIN, ex.KIND_SEQ, ex.KIND_NEAR))
    assert set(golden["kCaseSource"][0::3][roll].tolist()) <= set(ex.GOLDEN_SEEDS)


@pytest.mark.parametrize("seed", [10000, 10019, 10200, 10219, 12160, 12199])
def test_exporter_refuses_judge_seeds(seed):
    with pytest.raises(SystemExit, match="판정 시드"):
        ex.check_seeds([20000, seed])
    ex.check_seeds([20000, 20001, 20002])


# --------------------------------------------------------------------- #
# C++ (엔진 없이)
# --------------------------------------------------------------------- #


def test_cpp_files_are_engine_independent_and_clean():
    """위협 모델 헤더는 표준 헤더만 싣는다(UObject·CoreMinimal 없음). UE 자동화 시험이 모듈에 있다. 새 파일에 절 기호를 쓰지 않는다."""
    inc = re.compile(r'#include\s+[<"]([^>"]+)[>"]')
    assert set(inc.findall(MODEL_H.read_text(encoding="utf-8"))) == {"cmath", "cstdint"}
    ue_golden = ex.UE_POLICY_DIR / ex.HEADER
    if ue_golden.exists():
        txt = ue_golden.read_text(encoding="utf-8")
        assert set(inc.findall(txt)) == {"cstdint"} and "namespace EcoThreatV3::Golden" in txt
    assert UE_TEST.exists(), "UE 자동화 시험이 없다"
    assert not (ex.UE_POLICY_DIR / "Tests" / "EcoThreatModelV3Test.cpp.pending").exists(), "남은 .pending 파일이 있다"
    assert "AdaptiveEcosystem.Policy.V3.Threat." in UE_TEST.read_text(encoding="utf-8")
    for p in (MODEL_H, UE_TEST, CPP_MAIN, ROOT / "export_golden_v3_threat.py", Path(__file__), ue_golden):
        if p.exists():
            assert chr(0xA7) not in p.read_text(encoding="utf-8"), p.name


@needs_model
@needs_gpp
def test_cpp_threat_model_matches_golden_with_gpp(exported, tmp_path):
    """언리얼 모듈의 `EcoThreatModel.h` 를 그대로 g++ 로 컴파일해 다시 만든 골든과 대조한다(본·끝·열·이어 붙인 열·죽은 초식·결정성)."""
    exe = tmp_path / ("threat_v3.exe" if sys.platform == "win32" else "threat_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(exported["out"]), "-I",
                            str(ex.UE_POLICY_DIR), str(CPP_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
    for group in ("main", "edge", "seq_step", "stage_step", "chain"):
        m = re.search(rf"^{group}\s+.*max_float_err=([0-9.e+-]+) mismatch=(\d+)", run.stdout, re.M)
        assert m and float(m.group(1)) <= ex.FLOAT_TOL and int(m.group(2)) == 0, group
