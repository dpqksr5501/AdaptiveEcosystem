"""두뇌 파일 (`export_weights_v3.py --brain-file`) — 실행 중 가중치 로더(언리얼 `AI/Policy/EcoV3Brain.h`, 10-18 두뇌 바꾸기)의 파이썬 쪽 검증.

(1) 저장소에 올린 두뇌 파일(`AdaptiveEcosystem/EcoBrains/`)이 지금 코드·모델로 다시 만든 것과 바이트 단위로 같다(결정성·최신),
(2) 가중치 = 모델(비트 단위), R1b 파일 가중치 = 언리얼 생성 헤더 `PolicyWeightsV3.h`(같은 모델 — 내장 두뇌와 같은 지문),
(3) sha256 = 가중치 바이트(로더와 같은 순서), 계약 해시 = C++ 의 알려진 값, 허용 칸·문턱,
(4) 골든: 기대 로짓 = torch 정책(배포 경로), NumPy 재구현과 1e-5 안, 마스크 argmax, 근접 동점 없음, 행동 둘 이상,
(5) `--brain-file` 은 헤더를 쓰지 않는다. 언리얼 로더 쪽 검사는 `Tests/EcoV3BrainTest.cpp`·`EcoPolicyV3IntegratedTest.cpp Integrated.BrainSwap`.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import base64
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pytest

import export_weights_v3 as ex

ROOT = Path(__file__).resolve().parent.parent
BRAIN_DIR = ROOT.parent / "AdaptiveEcosystem" / "EcoBrains"
R1B = ex.DEFAULT_MODEL
R4 = ROOT / "ckpt" / "v3" / "v3_r4_g995_s0_20m.zip"
R4_LABEL = "R4: 통합 레벨 거울 세계 (나무 + 지역 날씨, 지역 섞기) 이어 학습 — R4 판정 실패, 늑대를 알면 더 숨음"
R1B_LABEL = "R1b: 기본 v3 세계 (configs/v3_r1.yaml) — 게임 내장 두뇌와 같은 가중치, 얼기는 통합 모드 세계가 막는다(R1b-F)"
CASES = {"r1b": (R1B, R1B_LABEL), "r4": (R4, R4_LABEL)}

pytestmark = pytest.mark.skipif(not (R1B.exists() and R4.exists()), reason="ckpt 는 저장소에 없다 (R1b s3·R4 s0 모델 필요)")


@pytest.fixture(scope="module", params=sorted(CASES))
def brain(request, tmp_path_factory):
    model, label = CASES[request.param]
    out = tmp_path_factory.mktemp("brain") / f"{model.stem}.json"
    d = ex.export_brain_file(model, out, world_label=label)
    return dict(key=request.param, model=model, path=out, d=d)


def _lf(b: bytes) -> bytes:
    """줄 끝을 LF 로 (이 PC 의 git core.autocrlf 가 꺼낼 때 CRLF 로 바꿀 수 있다 — 내용 비교는 줄 끝과 무관하게)."""
    return b.replace(bytes([13, 10]), bytes([10]))


def _floats(b64: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(b64), dtype="<f4")


def _layers(d: dict) -> dict:
    w = {}
    for L in d["layers"]:
        w[L["weight"]] = _floats(L["w_f32le_b64"]).reshape(L["out"], L["in"])
        w[L["bias"]] = _floats(L["b_f32le_b64"])
    return w


def test_committed_brain_file_is_current_and_deterministic(brain, tmp_path):
    committed = BRAIN_DIR / brain["path"].name
    assert committed.exists(), f"{committed} 없음 — export_weights_v3.py --brain-file 로 만든다"
    assert brain["path"].read_bytes() == _lf(committed.read_bytes()), "저장소 두뇌 파일이 지금 코드·모델과 다르다 — 다시 만든다"
    again = tmp_path / "again.json"
    ex.export_brain_file(brain["model"], again, world_label=CASES[brain["key"]][1])
    assert again.read_bytes() == brain["path"].read_bytes(), "같은 모델이면 바이트 단위로 같아야 한다"
    txt = brain["path"].read_text(encoding="utf-8")
    assert "C:" not in txt and "\\Users" not in txt, "절대 경로를 적지 않는다"


def test_weights_bit_exact_with_model_and_sha256(brain):
    d = brain["d"]
    model = ex.load_model(brain["model"])
    want = ex.extract(model)
    got = _layers(d)
    for k in ("W0", "B0", "W1", "B1", "W2", "B2"):
        assert got[k].shape == want[k].shape
        assert np.array_equal(got[k].view(np.uint32), want[k].astype(np.float32).view(np.uint32)), k
    assert d["weights_sha256"] == hashlib.sha256(ex.weights_bytes(want)).hexdigest()
    raw = b"".join(base64.b64decode(L[f]) for L in d["layers"] for f in ("w_f32le_b64", "b_f32le_b64"))
    assert hashlib.sha256(raw).hexdigest() == d["weights_sha256"], "sha256 은 층 순서(W0 B0 W1 B1 W2 B2) 바이트에 건다 (언리얼 로더와 같다)"
    assert d["id"] == f"{brain['model'].stem}@{d['weights_sha256'][:8]}"
    assert d["model"]["sha256"] == ex.file_sha256(brain["model"])
    assert [(L["out"], L["in"]) for L in d["layers"]] == [(64, 18), (64, 64), (5, 64)]


def test_r1b_brain_file_equals_compiled_header():
    """R1b 두뇌 파일 가중치 = 언리얼 PolicyWeightsV3.h (내장 두뇌) — 같은 지문이라 언리얼 로더가 같은 id 를 낸다."""
    d = json.loads((BRAIN_DIR / f"{R1B.stem}.json").read_text(encoding="utf-8"))
    txt = (ex.UE_POLICY_DIR / "PolicyWeightsV3.h").read_text(encoding="utf-8")
    got = _layers(d)
    for k in ("W0", "B0", "W1", "B1", "W2", "B2"):
        m = re.search(rf"inline constexpr float k{k}\[\d+\] = \{{(.*?)\}};", txt, re.S)
        vals = np.array([np.float32(float(t.strip().rstrip("f"))) for t in re.sub(r"//[^\n]*", "", m.group(1)).split(",") if t.strip()],
                        dtype=np.float32)
        assert np.array_equal(vals.view(np.uint32), got[k].reshape(-1).view(np.uint32)), k
    digest = re.search(r"kModelDigest = 0x([0-9a-f]+)ULL", txt).group(1)
    assert d["model"]["sha256"].startswith(digest)


def test_contract_mask_and_allowed(brain):
    from env_v2.rep_policy import ALARM_MASK_OBS, HIDE_COVER_OBS, MASK_LOGIT, THREAT_RECENCY_OBS
    from env_v2.repertoire import BEHAVIOR_NAMES

    d = brain["d"]
    assert d["format"] == ex.BRAIN_FORMAT and d["format_version"] == ex.BRAIN_FORMAT_VERSION
    assert d["contract_hash"] == "0x7eea0107339be4ce", "관측 18·마스크 판 2 (C++ kContractHashObs18Mask2) — 이 빌드의 관측 코드와 같은 계약만 바꿔 끼운다"
    assert d["contract_hash"] == f"0x{ex.contract_hash(d['obs_names'], d['mask_version']):016x}"
    assert d["obs_dim"] == len(d["obs_names"]) == 18 and d["hidden"] == 64 and d["num_behaviors"] == 5
    assert d["behaviors"] == list(BEHAVIOR_NAMES)
    assert d["mask_version"] == 2
    th = d["thresholds"]
    assert np.float32(th["threat_recency_obs"]) == np.float32(THREAT_RECENCY_OBS)
    assert np.float32(th["hide_cover_obs"]) == np.float32(HIDE_COVER_OBS)
    assert np.float32(th["alarm_mask_obs"]) == np.float32(ALARM_MASK_OBS)
    assert np.float32(th["mask_logit"]) == np.float32(MASK_LOGIT)
    assert d["allowed_mask"] == [int(b in d["allowed"]) for b in BEHAVIOR_NAMES]
    want = ["graze", "flee", "hide", "freeze"] if brain["key"] == "r1b" else ["graze", "flee", "hide"]
    assert d["allowed"] == want
    if brain["key"] == "r4":
        assert d["train"]["config"] == "configs/v3_r4_train.yaml"
    assert d["train"]["world"] == CASES[brain["key"]][1]


def test_golden_matches_torch_and_numpy(brain):
    from env_v2.rep_policy import policy_obs

    d = brain["d"]
    g = d["golden"]
    assert g["count"] == len(g["cases"]) >= 8
    assert g["seed"] == ex.BRAIN_GOLDEN_SEED and 32000 <= g["seed"] <= 32099
    obs = np.array([c["obs"] for c in g["cases"]], dtype=np.float32)
    mask = np.array([c["mask"] for c in g["cases"]], dtype=bool)
    logits = np.array([c["logits"] for c in g["cases"]], dtype=np.float32)
    act = np.array([c["action"] for c in g["cases"]])
    model = ex.load_model(brain["model"])
    t_logits, t_act = ex.torch_logits(model.policy, policy_obs(obs, mask))
    assert np.array_equal(t_logits.view(np.uint32), logits.view(np.uint32)), "골든 기대 로짓 = torch 정책 원 로짓 (float32 그대로)"
    assert np.array_equal(t_act, act)
    w = _layers(d)
    assert np.abs(ex.forward_np(obs, w, np.float32) - logits).max() < 1e-5
    assert np.array_equal(ex.masked_argmax(logits, mask), act)
    assert np.all(ex.top_gap(logits, mask) >= ex.NEAR_TIE_GAP), "근접 동점은 넣지 않는다"
    assert len(set(act.tolist())) >= 2
    kinds = {c["kind"] for c in g["cases"]}
    assert {"rollout", "random"} <= kinds


def test_brain_file_cli_writes_no_headers(tmp_path):
    out_dir = tmp_path / "hdr"
    out_dir.mkdir()
    f = tmp_path / "b.json"
    assert ex.main(["--model", str(R4), "--brain-file", str(f), "--out", str(out_dir), "--world-label", R4_LABEL]) == 0
    assert f.exists() and not any(out_dir.iterdir()), "--brain-file 은 헤더를 쓰지 않는다"
    assert f.read_bytes() == _lf((BRAIN_DIR / f"{R4.stem}.json").read_bytes())
