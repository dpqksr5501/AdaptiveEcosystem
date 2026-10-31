"""v3 행동 고르기 정책 내보내기 (`export_weights_v3.py`) — 파이썬 배포 경로 → 언리얼 C++ 다리의 검증.

헤더를 임시 폴더에 다시 만들어 (1) 언리얼 모듈에 들어간 헤더와 바이트 단위로 같은지(결정성·최신), (2) 가중치가 모델과 비트 단위로
같은지, (3) NumPy 재구현 순전파가 골든 로짓·torch 정책 argmax(`rep_argmax`)와 맞는지, (4) 마스크(가능·정책 입력·문턱·판 3)와
동점 규칙이 파이썬과 같은지, (5) 계약 해시가 C++ 의 알려진 값과 같은지 본다. g++ 가 있으면 언리얼 모듈의
`EcoPolicyV3Inference.h` 를 그대로 컴파일해 골든과 대조한다(`tests/cpp/parity_v3_main.cpp`).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import export_weights_v3 as ex
from env_v2 import rep_policy as rp
from env_v2.config import load_v2_config
from env_v2.world import obs_names

ROOT = Path(__file__).resolve().parent.parent
MODEL = ex.DEFAULT_MODEL
CPP_MAIN = ROOT / "tests" / "cpp" / "parity_v3_main.cpp"
INFER_H = ex.UE_POLICY_DIR / "EcoPolicyV3Inference.h"
UE_TEST = ex.UE_POLICY_DIR / "Tests" / "EcoPolicyV3InferenceTest.cpp"

needs_model = pytest.mark.skipif(not MODEL.exists(), reason=f"{MODEL} 없음 (ckpt 는 저장소에 없다)")
needs_gpp = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")

pytestmark = needs_model


# --------------------------------------------------------------------- #
# 헤더 읽기
# --------------------------------------------------------------------- #

_ARRAY = re.compile(r"inline constexpr (?:const )?([\w:]+)\*? (\w+)\[(\w+)\] = \{(.*?)\};", re.S)
_SCALAR = re.compile(r"inline constexpr ([\w:]+) (\w+) = ([^;{]+);")


def _num(tok: str, ctype: str):
    tok = tok.strip()
    if ctype == "float":
        return np.float32(float(tok.rstrip("f")))
    return int(tok)


def parse_header(path: Path) -> dict:
    """생성 헤더의 배열·스칼라 상수 → 이름: 값. float 배열은 float32, 정수 배열은 int64. 문자열 배열은 건너뛴다."""
    txt = Path(path).read_text(encoding="utf-8")
    out = {}
    for ctype, name, _n, body in _ARRAY.findall(txt):
        if ctype == "char":
            continue
        toks = [t for t in re.sub(r"//[^\n]*", "", body).replace("\n", " ").split(",") if t.strip()]
        dtype = np.float32 if ctype == "float" else np.int64
        out[name] = np.array([_num(t, ctype) for t in toks], dtype=dtype)
    for ctype, name, val in _SCALAR.findall(txt):
        val = val.strip()
        if ctype == "float":
            out[name] = np.float32(float(val.rstrip("f")))
        elif val.endswith("ULL"):
            out[name] = int(val[:-3], 16)
        elif re.fullmatch(r"-?\d+", val):
            out[name] = int(val)
    return out


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out = tmp_path_factory.mktemp("export_v3")
    r = ex.export(MODEL, ex.DEFAULT_CONFIG, ex.ALARM_CONFIG, out)
    r["out"] = out
    return r


@pytest.fixture(scope="module")
def weights_h(exported):
    return parse_header(exported["out"] / ex.HEADERS[0])


@pytest.fixture(scope="module")
def golden_h(exported):
    return parse_header(exported["out"] / ex.HEADERS[1])


@pytest.fixture(scope="module")
def model():
    return ex.load_model(MODEL)


def _rows(a, width):
    return np.asarray(a).reshape(-1, width)


# --------------------------------------------------------------------- #
# 결정성·최신
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("name", ex.HEADERS)
def test_regenerated_headers_match_unreal_module_bytes(exported, name):
    """다시 만든 헤더가 언리얼 모듈의 헤더와 바이트 단위로 같다 — 다른 실행(다른 프로세스)과 같은 결과이고, 모듈 헤더가 최신이다.
    다르면 `python export_weights_v3.py` 로 모듈 헤더를 다시 낸다."""
    ue = ex.UE_POLICY_DIR / name
    if not ue.exists():
        pytest.skip(f"언리얼 모듈 헤더 없음: {ue}")
    assert (exported["out"] / name).read_bytes() == ue.read_bytes(), f"{name} 이 다르다 — 내보내기가 결정적이지 않거나 낡았다"


def test_header_writers_are_deterministic(exported, tmp_path):
    """같은 데이터로 두 번 쓰면 바이트가 같다(시각·절대 경로를 적지 않는다)."""
    for k in (1, 2):
        d = tmp_path / str(k)
        d.mkdir()
        ex.write_weights_header(d / ex.HEADERS[0], exported["weights"], exported["meta"])
        ex.write_golden_header(d / ex.HEADERS[1], exported["golden"], exported["meta"])
    for name in ex.HEADERS:
        a, b = (tmp_path / "1" / name).read_bytes(), (tmp_path / "2" / name).read_bytes()
        assert a == b
        assert a == (exported["out"] / name).read_bytes()
        txt = a.decode("utf-8")
        assert "자동 생성. 수정 금지." in txt
        assert ":/" not in txt and ":\\" not in txt, "절대 경로가 헤더에 들어갔다"


# --------------------------------------------------------------------- #
# 가중치·계약
# --------------------------------------------------------------------- #


def test_weights_header_is_bit_exact_and_architecture_is_confirmed(weights_h, model):
    """세 층만, float32 값이 다시 읽어도 비트 단위로 같다. 망 구조: obs[:18] → Linear·tanh → Linear·tanh → Linear(5)."""
    import torch as th

    pol = model.policy
    assert pol.share_features_extractor and isinstance(pol.features_extractor, rp.RepObsSlice)
    assert pol.rep_obs_dim == 18 and pol.observation_space.shape == (23,)
    net = pol.mlp_extractor.policy_net
    assert [type(m) for m in net] == [th.nn.Linear, th.nn.Tanh, th.nn.Linear, th.nn.Tanh]
    w = ex.extract(model)
    for k in ("W0", "B0", "W1", "B1", "W2", "B2"):
        np.testing.assert_array_equal(weights_h["k" + k], w[k].reshape(-1), err_msg=k)
    assert weights_h["kObsDim"] == 18 and weights_h["kHiddenDim"] == 64 and weights_h["kNumBehaviors"] == 5
    assert weights_h["kMaskVersion"] == rp.MASK_VERSION == pol.rep_mask_version
    np.testing.assert_array_equal(weights_h["kAllowedMask"], pol.rep_allowed_mask.astype(np.int64))
    assert weights_h["kObsPredCount"] == 1 and weights_h["kObsThreatRecency"] == 17 and weights_h["kObsCoverDist"] == 6
    assert weights_h["kObsAlarmHeard"] == -1
    assert weights_h["kThreatRecencyObs"] == np.float32(rp.THREAT_RECENCY_OBS)
    assert weights_h["kHideCoverObs"] == np.float32(rp.HIDE_COVER_OBS)
    assert weights_h["kAlarmMaskObs"] == np.float32(rp.ALARM_MASK_OBS)
    assert weights_h["kMaskLogit"] == np.float32(rp.MASK_LOGIT)


def test_contract_hash_matches_cpp_known_values(weights_h, golden_h, model):
    """생성 헤더의 계약 해시 = 파이썬 contract_hash, 그리고 C++ 의 알려진 값(R1b 관측 18·판 2, R2 관측 19·판 3)과 같다."""
    r1b = tuple(model.policy.rep_obs_names)
    r2 = tuple(obs_names(load_v2_config(ex.ALARM_CONFIG)))
    assert r2 == r1b + (rp.REP_ALARM_COL,) and rp.mask_version_of(r2) == 3 and rp.mask_version_of(r1b) == 2
    h18, h19 = ex.contract_hash(r1b, 2), ex.contract_hash(r2, 3)
    assert weights_h["kContractHash"] == h18
    assert golden_h["kAlarmContractHash"] == h19
    txt = INFER_H.read_text(encoding="utf-8")
    known = dict(re.findall(r"inline constexpr std::uint64_t (kContractHashObs\w+) = 0x([0-9a-f]+)ULL;", txt))
    assert int(known["kContractHashObs18Mask2"], 16) == h18
    assert int(known["kContractHashObs19Mask3"], 16) == h19


def test_contract_hash_tracks_layout_and_mask():
    names = tuple(obs_names(load_v2_config(ex.DEFAULT_CONFIG)))
    h = ex.contract_hash(names, 2)
    assert ex.contract_hash(names, 2) == h
    assert ex.contract_hash(names[::-1], 2) != h                    # 관측 순서
    assert ex.contract_hash(names, 3) != h                          # 마스크 판
    assert 0 <= h < 2 ** 64


def test_exporter_rejects_v1_model():
    v1 = ROOT / "ckpt" / "final.zip"
    if not v1.exists():
        pytest.skip("v1 모델 없음")
    with pytest.raises(SystemExit, match="RepertoirePolicy"):
        ex.load_model(v1)


# --------------------------------------------------------------------- #
# 순전파·argmax
# --------------------------------------------------------------------- #


def test_numpy_forward_matches_torch_policy_argmax_on_golden(weights_h, golden_h, model):
    """NumPy 재구현(헤더 가중치)이 골든 로짓과 맞고, 마스크 argmax 가 torch 정책 배포 argmax(`rep_argmax`)·골든과 같다."""
    w = {k: weights_h["k" + k].reshape(s) for k, s in
         [("W0", (64, 18)), ("B0", (64,)), ("W1", (64, 64)), ("B1", (64,)), ("W2", (5, 64)), ("B2", (5,))]}
    obs, mask = _rows(golden_h["kObs"], 18), _rows(golden_h["kMask"], 5).astype(bool)
    logits, act = _rows(golden_h["kLogits"], 5), golden_h["kAction"]
    assert len(obs) == golden_h["kCount"] == len(act)
    for dt in (np.float32, np.float64):
        assert np.abs(ex.forward_np(obs, w, dt) - logits).max() <= 1e-5
    np.testing.assert_array_equal(ex.masked_argmax(ex.forward_np(obs, w, np.float32), mask), act)
    np.testing.assert_array_equal(ex.masked_argmax(ex.forward_np(obs, w, np.float64), mask), act)
    np.testing.assert_array_equal(rp.rep_argmax(model.policy, rp.policy_obs(obs, mask)), act)
    assert mask[np.arange(len(act)), act].all()                       # 고른 칸은 허용 칸
    raw, act_t = ex.torch_logits(model.policy, rp.policy_obs(obs, mask))
    assert np.abs(raw - logits).max() <= 1e-6
    np.testing.assert_array_equal(act_t, act)


def test_near_tie_split_and_tolerance_rule(golden_h, weights_h, model):
    """본 묶음은 1·2위 차 ≥ 1e-4, 근접 동점 묶음은 < 1e-4. 근접 동점에서는 NumPy 행동이 '최대에서 1e-4 안' 칸이면 된다."""
    gap = ex.top_gap(_rows(golden_h["kLogits"], 5), _rows(golden_h["kMask"], 5))
    assert (gap >= ex.NEAR_TIE_GAP).all()
    n_obs, n_mask = _rows(golden_h["kNearTieObs"], 18), _rows(golden_h["kNearTieMask"], 5).astype(bool)
    n_logits = _rows(golden_h["kNearTieLogits"], 5)
    assert len(n_obs) == golden_h["kNearTieCount"] >= 4
    assert (ex.top_gap(n_logits, n_mask) < ex.NEAR_TIE_GAP).all()
    np.testing.assert_array_equal(rp.rep_argmax(model.policy, rp.policy_obs(n_obs, n_mask)), golden_h["kNearTieAction"])
    w = {k: weights_h["k" + k].reshape(s) for k, s in
         [("W0", (64, 18)), ("B0", (64,)), ("W1", (64, 64)), ("B1", (64,)), ("W2", (5, 64)), ("B2", (5,))]}
    for dt in (np.float32, np.float64):
        a = ex.masked_argmax(ex.forward_np(n_obs, w, dt), n_mask)
        pick = n_logits[np.arange(len(a)), a]
        top = np.where(n_mask, n_logits, -np.inf).max(1)
        assert n_mask[np.arange(len(a)), a].all() and (pick >= top - ex.NEAR_TIE_GAP).all()
    assert golden_h["kLogitTolerance"] == np.float32(ex.LOGIT_TOL) and golden_h["kNearTieGap"] == np.float32(ex.NEAR_TIE_GAP)


def test_mask_bits_are_not_net_input(golden_h, model):
    """정책 입력의 마스크 칸을 바꿔도 원 로짓은 같다 — 망은 앞 18칸만 본다."""
    obs = _rows(golden_h["kObs"], 18)[:32]
    a, _ = ex.torch_logits(model.policy, rp.policy_obs(obs, np.ones((len(obs), 5), bool)))
    b, _ = ex.torch_logits(model.policy, rp.policy_obs(obs, np.eye(5, dtype=bool)[np.arange(len(obs)) % 5]))
    np.testing.assert_array_equal(a, b)


def test_tie_rule_is_lowest_index(golden_h):
    """동점 규칙 묶음: torch MaskedEpsCategorical.mode 의 값 = 막은 로짓의 첫 최댓값(np.argmax)."""
    lg, mk = _rows(golden_h["kTieLogits"], 5), _rows(golden_h["kTieMask"], 5).astype(bool)
    want = golden_h["kTieAction"]
    np.testing.assert_array_equal(ex.tie_expected(lg, mk), want)
    np.testing.assert_array_equal(ex.masked_argmax(lg, mk), want)
    assert want.tolist() == [0, 1, 2, 3, 0, 1, 1, 1, 0, 4, 0]


# --------------------------------------------------------------------- #
# 마스크
# --------------------------------------------------------------------- #


def test_golden_masks_match_python_mask_functions(golden_h, model):
    """가능 칸 = feasible_mask(관측), 정책 입력 마스크 = action_mask(미리 보기 dict) (롤아웃 사례), 문턱·판 3 격자."""
    names = tuple(model.policy.rep_obs_names)
    obs, mask = _rows(golden_h["kObs"], 18), _rows(golden_h["kMask"], 5).astype(bool)
    np.testing.assert_array_equal(rp.feasible_mask(obs, names), _rows(golden_h["kFeasible"], 5).astype(bool))
    roll = golden_h["kKind"] != ex.KIND_SYNTH
    pk = dict(reads=golden_h["kReads"][roll].astype(bool), wake_decide=golden_h["kWakeDecide"][roll].astype(bool),
              behavior=golden_h["kBehavior"][roll])
    params = {"allowed_mask": model.policy.rep_allowed_mask}
    np.testing.assert_array_equal(rp.action_mask(pk, obs[roll], params, obs_names=names), mask[roll])
    kinds = np.bincount(golden_h["kKind"], minlength=3)
    assert kinds[ex.KIND_DECIDE] > 0 and kinds[ex.KIND_NONDEC] > 0 and kinds[ex.KIND_SYNTH] > 0
    # 문턱 바로 위·아래 (이 모델 관측)
    e_obs = _rows(golden_h["kMaskEdgeObs"], 18)
    e_feas = _rows(golden_h["kMaskEdgeFeasible"], 5).astype(bool)
    np.testing.assert_array_equal(rp.feasible_mask(e_obs, names), e_feas)
    tr = e_obs[:, names.index("threat_recency")]
    assert np.float32(rp.THREAT_RECENCY_OBS) in tr and np.nextafter(np.float32(rp.THREAT_RECENCY_OBS), np.float32(0)) in tr
    assert e_feas[:, rp.FLEE].any() and not e_feas[:, rp.FLEE].all() and e_feas[:, rp.HIDE].any()
    # 판 3 (경보 세계 관측 19)
    r2 = tuple(obs_names(load_v2_config(ex.ALARM_CONFIG)))
    a_obs = _rows(golden_h["kAlarmObs"], 19)
    a_feas = _rows(golden_h["kAlarmFeasible"], 5).astype(bool)
    np.testing.assert_array_equal(rp.feasible_mask(a_obs, r2), a_feas)
    al = a_obs[:, r2.index(rp.REP_ALARM_COL)]
    only_alarm = (a_obs[:, r2.index("pred_count")] == 0) & (a_obs[:, r2.index("threat_recency")] < rp.THREAT_RECENCY_OBS)
    np.testing.assert_array_equal(a_feas[only_alarm, rp.FLEE], al[only_alarm] >= np.float32(rp.ALARM_MASK_OBS))
    np.testing.assert_array_equal(golden_h["kAlarmFromBuiltin"], list(range(18)) + [-1])


def test_golden_covers_every_listed_behavior(golden_h, model):
    """본 묶음 롤아웃 사례의 argmax 에 목록 행동(GRAZE·FLEE·HIDE·FREEZE)이 모두 있다."""
    roll = golden_h["kKind"] != ex.KIND_SYNTH
    got = set(golden_h["kAction"][roll].tolist())
    want = {i for i, b in enumerate(model.policy.rep_allowed_mask) if b}
    assert want <= got


# --------------------------------------------------------------------- #
# C++ (엔진 없이)
# --------------------------------------------------------------------- #


def test_cpp_files_are_engine_independent_and_clean():
    """추론 헤더·생성 헤더는 표준 헤더만 싣는다(UObject·CoreMinimal 없음). 새 파일에 절 기호를 쓰지 않는다."""
    inc = re.compile(r'#include\s+[<"]([^>"]+)[>"]')
    assert set(inc.findall(INFER_H.read_text(encoding="utf-8"))) == {"cmath", "cstdint", "PolicyWeightsV3.h"}
    for name in ex.HEADERS:
        txt = (ex.UE_POLICY_DIR / name).read_text(encoding="utf-8")
        assert set(inc.findall(txt)) <= {"cstdint", "PolicyWeightsV3.h"}
        assert "namespace EcoPolicyV3" in txt
    for p in (INFER_H, UE_TEST, CPP_MAIN, ROOT / "export_weights_v3.py", Path(__file__),
              *(ex.UE_POLICY_DIR / n for n in ex.HEADERS)):
        assert chr(0xA7) not in p.read_text(encoding="utf-8"), p.name


@needs_gpp
def test_cpp_inference_matches_golden_with_gpp(tmp_path):
    """언리얼 모듈의 `EcoPolicyV3Inference.h` 를 그대로 g++ 로 컴파일해 골든 다섯 묶음을 대조한다."""
    exe = tmp_path / ("parity_v3.exe" if sys.platform == "win32" else "parity_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(ex.UE_POLICY_DIR),
                            str(CPP_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
    err = float(re.search(r"main\s+n=\d+ max_logit_err=([0-9.e+-]+)", run.stdout).group(1))
    assert err <= ex.LOGIT_TOL
