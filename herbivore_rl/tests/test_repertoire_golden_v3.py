"""v3 R1b 세계 개체 논리 골든 (`export_golden_v3_world.py`) — 파이썬 세계 → 언리얼 C++ (EcoRepertoire.h·EcoObservationV3.h) 다리의 검증.

헤더를 임시 폴더에 다시 만들어 (1) 언리얼 모듈에 들어간 헤더와 바이트 단위로 같은지(결정성·최신), (2) 헤더의 Arbiter 열을 진짜
`repertoire.arbitrate`·`tick`·`reset_slots` 로 다시 돌려 같은 값이 나오는지(헤더 숫자 표기·열 이음이 맞다), (3) 골든이 계약의 경우
(창 범주, 사건 E1~E6, 전환, 닫힌 고리)를 덮는지, (4) 경계 열이 계약 5절의 뜻대로 움직이는지, (5) 보정 시드만 쓰는지 본다.
g++ 가 있으면 언리얼 모듈의 엔진 무관 헤더를 그대로 컴파일해 골든과 대조한다(`tests/cpp/parity_repertoire_v3_main.cpp`,
UE 자동화 시험과 같은 검사 `Tests/RepertoireGoldenCheckV3.h`).
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

import export_golden_v3_world as eg
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config

ROOT = Path(__file__).resolve().parent.parent
MODEL = eg.DEFAULT_MODEL
POLICY_DIR = eg.UE_POLICY_DIR
UE_HEADER = POLICY_DIR / eg.HEADER
CPP_MAIN = ROOT / "tests" / "cpp" / "parity_repertoire_v3_main.cpp"
REP_H = POLICY_DIR / "EcoRepertoire.h"
OBS_H = POLICY_DIR / "EcoObservationV3.h"
CHECK_H = POLICY_DIR / "Tests" / "RepertoireGoldenCheckV3.h"
UE_TEST = POLICY_DIR / "Tests" / "EcoRepertoireV3Test.cpp"

needs_model = pytest.mark.skipif(not MODEL.exists(), reason=f"{MODEL} 없음 (ckpt 는 저장소에 없다)")
needs_gpp = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")


# --------------------------------------------------------------------- #
# 헤더 읽기
# --------------------------------------------------------------------- #

_ARRAY = re.compile(r"inline constexpr (const char\*|[\w:]+) (\w+)\[(\w+)\] = \{(.*?)\};", re.S)
_SCALAR = re.compile(r"inline constexpr ([\w:]+) (\w+) = ([^;{]+);")


def parse_header(path: Path) -> dict:
    """생성 헤더 → 이름: 값. double 은 float64, float 은 float32, 정수는 int64(uint64 는 파이썬 int 목록), 문자열은 목록."""
    txt = Path(path).read_text(encoding="utf-8")
    out = {}
    for ctype, name, _n, body in _ARRAY.findall(txt):
        body = re.sub(r"//[^\n]*", "", body)
        if ctype == "const char*":
            out[name] = re.findall(r'"([^"]*)"', body)
            continue
        toks = [t.strip() for t in body.replace("\n", " ").split(",") if t.strip()]
        if ctype == "double":
            out[name] = np.array([float(t) for t in toks], dtype=np.float64)
        elif ctype == "float":
            out[name] = np.array([float(t.rstrip("f")) for t in toks], dtype=np.float32)
        elif ctype == "std::uint64_t":
            out[name] = [int(t.rstrip("ULL"), 16) for t in toks]
        else:
            out[name] = np.array([int(t) for t in toks], dtype=np.int64)
    for ctype, name, val in _SCALAR.findall(txt):
        val = val.strip()
        if ctype == "double":
            out[name] = float(val)
        elif re.fullmatch(r"-?\d+", val):
            out[name] = int(val)
    return out


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    if not MODEL.exists():
        pytest.skip(f"{MODEL} 없음")
    out = tmp_path_factory.mktemp("golden_v3_world")
    r = eg.export(MODEL, eg.DEFAULT_CONFIG, out)
    r["out"] = out
    return r


@pytest.fixture(scope="module")
def golden_h(exported):
    return parse_header(exported["out"] / eg.HEADER)


@pytest.fixture(scope="module")
def params():
    from env_v2.features import features_of

    cfg = load_v2_config(eg.DEFAULT_CONFIG)
    return rep.parse_params(features_of(cfg).params("repertoire"), features_of(cfg))


# --------------------------------------------------------------------- #
# 결정성·최신
# --------------------------------------------------------------------- #


@needs_model
def test_regenerated_header_matches_unreal_module_bytes(exported):
    """다시 만든 헤더가 언리얼 모듈의 헤더와 바이트 단위로 같다 — 다른 실행과 같은 결과이고 모듈 헤더가 최신이다.
    다르면 `python export_golden_v3_world.py` 로 모듈 헤더를 다시 낸다."""
    if not UE_HEADER.exists():
        pytest.skip(f"언리얼 모듈 헤더 없음: {UE_HEADER}")
    assert (exported["out"] / eg.HEADER).read_bytes() == UE_HEADER.read_bytes(), "골든 헤더가 다르다 — 결정적이지 않거나 낡았다"


@needs_model
def test_header_writer_is_deterministic(exported, tmp_path):
    """같은 데이터로 두 번 쓰면 바이트가 같다(시각·절대 경로를 적지 않는다)."""
    for k in (1, 2):
        d = tmp_path / str(k)
        d.mkdir()
        eg.write_header(d / eg.HEADER, exported["golden"], exported["meta"])
    a, b = (tmp_path / "1" / eg.HEADER).read_bytes(), (tmp_path / "2" / eg.HEADER).read_bytes()
    assert a == b == (exported["out"] / eg.HEADER).read_bytes()
    txt = a.decode("utf-8")
    assert "자동 생성. 수정 금지." in txt
    assert ":/" not in txt and ":\\" not in txt, "절대 경로가 헤더에 들어갔다"


def test_golden_uses_calibration_seeds_only():
    """골든 시드는 보정 시드다. 판정 시드(10000~10019, 10200~10219, 12160~12199)를 주면 멈춘다."""
    eg.check_seeds(eg.GOLDEN_SEEDS)
    eg.check_seeds([eg.EDGE_SEED])
    for s in (10000, 10019, 10205, 12160, 12199):
        with pytest.raises(SystemExit, match="판정 시드"):
            eg.check_seeds([s])
    assert set(eg.GOLDEN_SEEDS) == {20000, 20001, 20002}


# --------------------------------------------------------------------- #
# 헤더를 진짜 파이썬 Arbiter 로 다시 돌린다
# --------------------------------------------------------------------- #


def _state_from(rs, v) -> None:
    for k, f in enumerate(eg.STATE_FIELDS):
        getattr(rs, f)[0] = v[k]


@needs_model
def test_header_sequences_replay_through_python_arbiter(golden_h, params):
    """헤더의 모든 Arbiter 열(시작 상태 + 스텝마다 요청·결정 관측)을 진짜 repertoire.arbitrate·tick·reset_slots 로 다시 돌리면
    헤더의 결정 뒤 상태·결정·전환·사건·사건 비트·reads(rep_peek 과 같은 미리 보기)가 그대로 나온다."""
    h, p = golden_h, params
    nf = len(eg.STATE_FIELDS)
    init = h["kSeqInitState"].reshape(-1, nf)
    oint = h["kStepObsInt"].reshape(-1, 4)
    oreal = h["kStepObsReal"].reshape(-1, 6)
    state = h["kStepState"].reshape(-1, nf)
    bad = []
    for s in range(h["kSeqCount"]):
        seed, slot = int(h["kSeqSeed"][s]), int(h["kSeqSlot"][s])
        rs = rep.RepState(1, p, np.array([0.5]), 0.0, 0)
        _state_from(rs, init[s])
        for k in range(h["kSeqLength"][s]):
            n = h["kSeqStart"][s] + k
            d = [math.inf if x >= 1e299 else float(x) for x in oreal[n]]
            obs = dict(pred_count=np.array([oint[n, 0]]), pred_count_ev=np.array([oint[n, 1]]),
                       in_cover=np.array([bool(oint[n, 2])]), cover_k=np.array([oint[n, 3]]),
                       d_pred_min=np.array([d[0]]), pred_approach=np.array([d[1]]), d_pred_min_ev=np.array([d[2]]),
                       pred_approach_ev=np.array([d[3]]), energy=np.array([d[4]]), dark=d[5])
            if h["kSeqAlarm"][s]:
                obs["alarm_new"] = np.array([bool(h["kStepAlarmNew"][n])])
            reads, wake = eg.peek(rs, p, obs)
            pre = eg.state_matrix(rs)
            res = rep.arbitrate(rs, p, np.array([h["kStepRequest"][n]]), obs)
            flags = int(eg.result_flags(res, reads, wake)[0])
            if (not np.array_equal(eg.state_matrix(rs)[0], state[n]) or flags != h["kStepFlags"][n]
                    or int(eg.event_bits(pre, obs, p)[0]) != h["kStepEvents"][n]):
                bad.append((h["kSeqName"][s], k))
            rep.tick(rs)
            if h["kStepRespawn"][n]:
                g = int(h["kStepRespawnGeneration"][n])
                rs.reset_slots(np.array([0]), p, np.array([h["kStepRespawnEnergy"][n]]), float(h["kStepRespawnDark"][n]),
                               seed, np.array([g]))
                rs.jitter[0] = rep.decision_jitter(seed, [slot], np.array([g]), p["decision_jitter"])[0]
    assert not bad, f"헤더 열을 파이썬 Arbiter 로 다시 돌린 값이 다르다: {bad[:5]}"
    assert h["kStepCount"] == len(h["kStepRequest"]) == int(h["kSeqLength"].sum())


@needs_model
def test_hash_rows_match_python(golden_h):
    """지연 해시 행 = repertoire.mix_chain(505, 시드, 키), 지연 = decision_jitter (파리티 키) / H mod 4 (통합 모드 키)."""
    h = golden_h
    for k in range(h["kHashCount"]):
        seed, key = int(h["kHashSeed"][k]), h["kHashKey"][k]
        hv = int(rep.mix_chain(rep.JITTER_TAG, np.int64(seed), np.uint64(key)))
        assert hv == h["kHashValue"][k]
        assert hv % 4 == h["kHashJitter"][k]
        if h["kHashSlot"][k] >= 0:
            slot, gen = int(h["kHashSlot"][k]), int(h["kHashGeneration"][k])
            assert int(rep.agent_keys([slot], [gen])[0]) == key
            assert rep.decision_jitter(seed, [slot], np.array([gen]), 3)[0] == h["kHashJitter"][k]
    assert (h["kHashSlot"] < 0).any() and (h["kHashSlot"] >= 0).any()


@needs_model
def test_world_constants_come_from_config(golden_h, params):
    """상수 표는 R1b 세계 설정 값이다(경보 꺼짐, 관측 18, 은신 배수 4.0/1.5/2.5/1.0, 보행 [0, 0.4, 1.0])."""
    c = dict(zip(golden_h["kWorldConstantNames"], golden_h["kWorldConstantValues"]))
    assert len(c) == golden_h["kWorldConstantCount"]
    assert c["alarm_event"] == 0.0 and c["obs_dim"] == 18.0
    assert c["lock_graze"] == params["lock_graze"] == 12 and c["hide_travel_max"] == 40
    assert (c["cover_mult_crouch"], c["cover_mult_graze"], c["cover_mult_sleep"], c["cover_mult_other"]) == (4.0, 1.5, 2.5, 1.0)
    assert (c["gait_speed_0"], c["gait_speed_1"], c["gait_speed_2"]) == (0.0, 0.4, 1.0)
    assert c["fov_cos"] == math.cos(math.radians(120.0) * 0.5)
    assert c["step_seconds"] * 7.5 == pytest.approx(1.0)


# --------------------------------------------------------------------- #
# 덮음 (계약의 경우가 골든에 있다)
# --------------------------------------------------------------------- #


@needs_model
def test_golden_covers_contract_cases(exported, golden_h):
    """롤아웃 창 범주가 모두 나오고, 사건 E1~E6·네 행동으로의 전환·리스폰·닫힌 고리·지연 0~3 이 골든에 있다. E7 은 플래그를 켠
    경계 열 하나에만 있다."""
    s, h = exported["stats"], golden_h
    assert set(s["window_cats"]) == set(eg.WINDOW_CATEGORIES)
    assert len(set(h["kSeqName"][s["rollout_seqs"]:])) == s["edge_seqs"]
    assert not set(h["kSeqName"][s["rollout_seqs"]:]) & set(eg.WINDOW_CATEGORIES), "경계 열 이름이 창 범주와 겹친다"
    assert s["rollout_seqs"] == len(eg.GOLDEN_SEEDS) * len(eg.WINDOW_CATEGORIES)
    assert s["edge_seqs"] == len(eg.edge_specs())             # event_jitter 는 지연 0~3 넷이 따로 있다
    assert s["loop_seqs"] == len(eg.GOLDEN_SEEDS) * eg.LOOP_WINDOWS_PER_SEED
    ev = h["kStepEvents"]
    for name, bit in eg.EV_BITS.items():
        assert ((ev & bit) != 0).any(), f"사건 {name} 이 골든에 없다"
    kinds = h["kSeqKind"]
    roll_steps = int(h["kSeqLength"][kinds == eg.KIND_ROLLOUT].sum())
    sw = (h["kStepFlags"][:roll_steps] & eg.FLAG_SWITCH) != 0
    beh = h["kStepState"].reshape(-1, 19)[:roll_steps, 0]
    assert {0, 1, 2, 3} <= set(beh[sw].tolist()), "롤아웃 창에 GRAZE·FLEE·HIDE·FREEZE 전환이 다 있어야 한다"
    assert not (beh == rep.SLEEP).any(), "R1b 롤아웃에는 SLEEP 이 없다 (마스크가 막는다)"
    e7_seqs = {h["kSeqName"][q] for q in range(h["kSeqCount"]) for k in range(h["kSeqLength"][q])
               if h["kStepEvents"][h["kSeqStart"][q] + k] & eg.EV_BITS["e7"]}
    assert e7_seqs == {"kin_alarm_e7"} and h["kSeqAlarm"].sum() == 1
    assert h["kStepRespawn"][:roll_steps].sum() > 0 and h["kRespawnCount"] > 0
    assert h["kLoopRowCount"] == s["loop_seqs"] * eg.WINDOW
    jit = h["kSeqInitState"].reshape(-1, 19)[:, 18]
    assert {0, 1, 2, 3} <= set(jit.tolist())
    # 제어기: 롤아웃에 모든 행동(SLEEP 제외)·세 보행·웅크림·heading 덮기, 손 사례에 SLEEP
    ci = h["kCtlStateInt"].reshape(-1, 4)
    assert {0, 1, 2, 3, 4} <= set(ci[:, 0].tolist()) and {0, 1, 2} <= set(h["kCtlGait"].tolist())
    cb = h["kCtlBool"].reshape(-1, 3)
    assert cb[:, 1].any() and cb[:, 2].any()
    assert (h["kCtlRepro"].reshape(-1, 3)[:, 2] == 1).any(), "번식 사례가 있어야 한다"
    # 지각: 띠(사건 비교 시야 ≠ 실제 시야)와 자는 위협
    se = h["kSnapExpInt"].reshape(-1, 5)
    assert (se[:, 0] != se[:, 1]).any() and h["kSnapThreatAsleep"].any()


@needs_model
def test_threshold_exclusions_are_reported(exported, golden_h):
    """문턱 근처 제외 수가 헤더 머리에 적혀 있고, 골든 창에는 문턱 근처 결정 관측이 없다(계약 11-2)."""
    s = exported["stats"]
    txt = (exported["out"] / eg.HEADER).read_text(encoding="utf-8")
    assert f"창 후보 {s['window_candidates']} 중 {s['window_near_excluded']}" in txt
    assert f"문턱 근처로 검사를 뺀 개체 {s['snap_near_excluded']}" in txt
    assert s["window_candidates"] > s["window_near_excluded"] >= 0
    h = golden_h
    roll = int(h["kSeqLength"][h["kSeqKind"] == eg.KIND_ROLLOUT].sum())
    oi, orl = h["kStepObsInt"].reshape(-1, 4)[:roll], h["kStepObsReal"].reshape(-1, 6)[:roll]
    near = (oi[:, 0] > 0) & ((np.abs(orl[:, 0] - 8.0) < eg.NEAR_DIST) | (np.abs(orl[:, 1] - 0.9) < eg.NEAR_APPROACH))
    near |= (oi[:, 1] > 0) & ((np.abs(orl[:, 2] - 8.0) < eg.NEAR_DIST) | (np.abs(orl[:, 3] - 0.9) < eg.NEAR_APPROACH))
    near |= np.abs(orl[:, 4] - 0.25) < eg.NEAR_ENERGY
    assert not near.any()
    assert int((h["kSnapAgentCheck"] == 0).sum()) == s["snap_near_excluded"]


# --------------------------------------------------------------------- #
# 경계 열이 계약 5절의 뜻대로 움직인다 (파이썬 참조 그대로)
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def edges(params):
    return {q["name"]: q for q in eg.edge_sequences(params, eg.EDGE_SEED)}


def _col(q, field):
    return np.array([r["post"][eg.STATE_FIELDS.index(field)] for r in q["steps"]])


def _flag(q, bit):
    return np.array([(r["flags"] & bit) != 0 for r in q["steps"]])


def test_edge_lock_expiry_and_startle(edges):
    """GRAZE 잠금 12 가 끝난 스텝 12 에 FLEE, 놀람 3스텝은 위상 0, FLEE 잠금 8 뒤 스텝 20 에 GRAZE."""
    q = edges["lock_expiry"]
    sw = np.flatnonzero(_flag(q, eg.FLAG_SWITCH)).tolist()
    assert sw == [12, 20]
    assert _col(q, "phase")[12:16].tolist() == [0, 0, 0, 1]
    assert _col(q, "startle_left")[12] == 3


@pytest.mark.parametrize("j", range(4))
def test_edge_event_jitter_delays_decision(edges, j):
    """스텝 3 의 E1 결정은 3 + jitter 에 온다(잠금 중이어도 사건 결정이 연다)."""
    q = edges[f"event_jitter_{j}"]
    assert q["steps"][3]["ev"] & eg.EV_BITS["e1"]
    assert np.flatnonzero(_flag(q, eg.FLAG_SWITCH)).tolist() == [3 + j]
    assert np.flatnonzero(_flag(q, eg.FLAG_FIRE)).tolist() == [3 + j]


def test_edge_waiting_event_and_hide_arrival(edges):
    """대기 중 새 사건은 지연을 다시 걸지 않는다(스텝 2 사건 → 5 결정). 늦게 도착하면 E6, 도착 잠금 12, 위상 1."""
    q = edges["event_while_waiting"]
    assert np.flatnonzero(_flag(q, eg.FLAG_FIRE)).tolist()[0] == 5
    e6 = [k for k, r in enumerate(q["steps"]) if r["ev"] & eg.EV_BITS["e6"]]
    assert e6 == [8]
    assert _col(q, "lock_left")[8] == 12 and _col(q, "phase")[8] == 1 and _col(q, "hide_target")[5] == 2


def test_edge_view_widening_is_not_an_event(edges):
    """실제 시야에만 보인 위협은 사건이 아니고 기준값에만 들어간다(사건 비교 시야). 접근 0.9 는 빠름(같음 포함)."""
    q = edges["view_widening"]
    ev = [r["ev"] for r in q["steps"]]
    assert ev[2] == 0 and ev[3] == 0 and ev[4] == 0 and ev[5] == 0
    assert ev[8] & eg.EV_BITS["e1"] and ev[9] & eg.EV_BITS["e2"] and not ev[10] & eg.EV_BITS["e2"]
    assert ev[11] & eg.EV_BITS["e2"]                                 # 7.999 < 8 로 들어옴


def test_edge_energy_and_dark_thresholds(edges):
    """E4 는 0.25 아래로 내려갈 때만(0.25 는 낮지 않다), E5 는 d = 0.5 를 양방향으로 지날 때(0.5 는 어둠 쪽)."""
    e4 = [k for k, r in enumerate(edges["energy_low"]["steps"]) if r["ev"] & eg.EV_BITS["e4"]]
    assert e4 == [2, 5, 7, 9]
    e5 = [k for k, r in enumerate(edges["dark_cross"]["steps"]) if r["ev"] & eg.EV_BITS["e5"]]
    assert e5 == [1, 4, 5]
    keep = edges["energy_low"]
    assert _flag(keep, eg.FLAG_DECIDE)[2:].all() and not _flag(keep, eg.FLAG_SWITCH).any()   # 같은 요청은 다시 잠그지 않는다


def test_edge_hide_paths(edges):
    """은신처 안 HIDE 는 곧바로 도착(잠금 12, E6 없음). 시간 끝(40) 뒤 같은 요청은 계속 가고, 목표가 없으면 −1."""
    q = edges["hide_immediate"]
    assert _col(q, "arrived")[0] == 1 and _col(q, "lock_left")[0] == 12 and _col(q, "phase")[0] == 1
    assert not any(r["ev"] & eg.EV_BITS["e6"] for r in q["steps"])
    t = edges["hide_travel_timeout"]
    dec = _flag(t, eg.FLAG_DECIDE)
    assert dec[0] and not dec[1:40].any() and dec[40:44].all() and not _flag(t, eg.FLAG_SWITCH)[1:44].any()
    assert t["steps"][44]["ev"] & eg.EV_BITS["e6"]
    assert (_col(edges["hide_no_cover"], "hide_target") == -1).all()


def test_edge_respawn_and_seq_wrap(edges, params):
    """리스폰: seq + 1, 잠금 12, 지연은 새 세대의 해시. seq 는 255 다음 0."""
    q = edges["respawn_twice"]
    assert [k for k, r in enumerate(q["steps"]) if r["resp"]] == [3, 17]
    seq = _col(q, "seq")
    assert seq[4] == seq[3] + 1                                       # 리스폰 뒤 첫 스텝의 상태
    j1 = rep.decision_jitter(eg.EDGE_SEED, [0], np.array([1]), params["decision_jitter"])[0]
    assert _col(q, "jitter")[4] == j1
    assert _col(edges["seq_wrap"], "seq")[0] == 0


def test_edge_sleep_unit_path(edges):
    """SLEEP: 진입 3스텝 위상 0, E3, 기상 중 위상 2, 기상 중 사건이 있으면 깨는 스텝에 요청(FLEE)으로, 없으면 wake_target 으로."""
    q = edges["sleep_unit"]
    beh, ph = _col(q, "behavior"), _col(q, "phase")
    assert beh[0] == rep.SLEEP and ph[:3].tolist() == [0, 0, 0] and ph[3] == 1
    assert any(r["ev"] & eg.EV_BITS["e3"] for r in q["steps"])
    assert (ph == 2).any()
    woke = [k for k, r in enumerate(q["steps"]) if (r["flags"] & eg.FLAG_SWITCH) and beh[k - 1] == rep.SLEEP and ph[k - 1] == 2]
    assert len(woke) == 2
    assert beh[woke[0]] == rep.FLEE and _flag(q, eg.FLAG_WAKE)[woke[0]]
    assert beh[woke[1]] == rep.GRAZE and not _flag(q, eg.FLAG_WAKE)[woke[1]]


def test_edge_e7_only_in_graze_or_sleep(edges):
    """E7 (플래그를 켠 열): GRAZE 의 새 경보는 사건, FREEZE 에서는 사건이 아니다."""
    q = edges["kin_alarm_e7"]
    e7 = [k for k, r in enumerate(q["steps"]) if r["ev"] & eg.EV_BITS["e7"]]
    assert e7 == [2]
    assert _col(q, "behavior")[7] == rep.FREEZE and q["steps"][7]["alarm"] == 1


# --------------------------------------------------------------------- #
# C++ (엔진 없이)
# --------------------------------------------------------------------- #


def test_cpp_files_are_engine_independent_and_clean():
    """엔진 무관 헤더는 표준 헤더와 서로만 싣는다(UObject·CoreMinimal 없음). 새 파일에 절 기호를 쓰지 않는다."""
    inc = re.compile(r'#include\s+[<"]([^>"]+)[>"]')
    assert set(inc.findall(REP_H.read_text(encoding="utf-8"))) == {"cmath", "cstdint"}
    assert set(inc.findall(OBS_H.read_text(encoding="utf-8"))) == {"cmath", "cstdint", "EcoRepertoire.h"}
    assert set(inc.findall(CHECK_H.read_text(encoding="utf-8"))) == {
        "cmath", "cstdint", "../EcoObservationV3.h", "../EcoPolicyV3Inference.h", "../EcoRepertoire.h",
        "../RepertoireGoldenVectorsV3.h"}
    if UE_HEADER.exists():
        assert set(inc.findall(UE_HEADER.read_text(encoding="utf-8"))) == {"cstdint"}
    for p in (REP_H, OBS_H, CHECK_H, UE_TEST, CPP_MAIN, ROOT / "export_golden_v3_world.py", Path(__file__), UE_HEADER):
        if p.exists():
            assert chr(0xA7) not in p.read_text(encoding="utf-8"), p.name


@needs_model
@needs_gpp
def test_cpp_matches_golden_with_gpp(tmp_path):
    """언리얼 모듈의 EcoRepertoire.h·EcoObservationV3.h 를 그대로 g++ 로 컴파일해 골든 전부를 대조한다(UE 시험과 같은 검사)."""
    exe = tmp_path / ("parity_rep_v3.exe" if sys.platform == "win32" else "parity_rep_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-I", str(POLICY_DIR),
                            str(CPP_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
    rows = dict(re.findall(r"^(\w+)\s+cases=\d+ skipped=\d+ failures=0 max_err=([0-9.e+-]+)", run.stdout, re.M))
    assert len(rows) == 15, run.stdout
    assert max(float(v) for v in rows.values()) <= 1e-4
    assert float(rows["obs_build"]) == 0.0                            # 같은 double 입력이면 비트 단위로 같다
