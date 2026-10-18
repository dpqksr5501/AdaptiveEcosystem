"""R5 관측 21 시작 두뇌 (`results/v3/r5/zero_extend.py` — R1b-F + 새 관측 세 칸 입력 열 0) 와 그 언리얼 두뇌 파일
(`AdaptiveEcosystem/EcoBrains/v3_r1_g995_s3_obs21zero.json`)의 파이썬 쪽 검증 (10-19, 계약 POLICY_CONTRACT_V3.md 2-4).

(1) 저장소 두뇌 파일: 계약 = 관측 21·마스크 판 2(0xbc4fc2d45c47c5fd = C++ kContractHashObs21Mask2), 관측 이름 = R1b 18 + 장애물 세 칸, 허용·문턱 = R1b,
(2) 가중치: 첫 층 앞 18 열·다른 층 = R1b 두뇌 파일(비트 단위), 새 세 열 = +0.0, sha256 = 층 바이트,
(3) 골든: 관측 21 거울 세계 시드 32099, 새 칸 값이 실제로 움직이고, 로짓 = 앞 18 칸만 본 R1b 로짓, 마스크 argmax,
(4) 모델 zip·두뇌 파일이 다시 만들어도 바이트 단위로 같다(결정성 — ckpt 가 있을 때), 모델 관측 = 관측 21 설정, 새 열 0,
(5) 두뇌 골든 세계 고르기(관측 18 → v3_wild3_mirror, 관측 21 → v3_wild3_obs_mirror).
언리얼 쪽은 Tests/EcoV3BrainTest.cpp Brain.LoadObs21·EcoObstacleObsV3Test.cpp·EcoPolicyV3IntegratedTest.cpp Integrated.BrainObs21Zero.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import base64
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

import export_weights_v3 as ex

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "results" / "v3" / "r5"))
import zero_extend as zx  # noqa: E402

BRAIN_DIR = ROOT.parent / "AdaptiveEcosystem" / "EcoBrains"
ZERO = BRAIN_DIR / "v3_r1_g995_s3_obs21zero.json"
R1B = BRAIN_DIR / "v3_r1_g995_s3_20m.json"
HASH21 = "0xbc4fc2d45c47c5fd"


def _lf(b: bytes) -> bytes:
    return b.replace(bytes([13, 10]), bytes([10]))


def _layers(d: dict) -> dict:
    w = {}
    for L in d["layers"]:
        w[L["weight"]] = np.frombuffer(base64.b64decode(L["w_f32le_b64"]), dtype="<f4").reshape(L["out"], L["in"])
        w[L["bias"]] = np.frombuffer(base64.b64decode(L["b_f32le_b64"]), dtype="<f4")
    return w


@pytest.fixture(scope="module")
def files():
    return json.loads(ZERO.read_text(encoding="utf-8")), json.loads(R1B.read_text(encoding="utf-8"))


def test_contract_names_allowed(files):
    from env_v2.config import load_v2_config
    from env_v2.world import OBSTACLE_OBS_NAMES, obs_names

    z, r = files
    assert z["format"] == ex.BRAIN_FORMAT and z["format_version"] == ex.BRAIN_FORMAT_VERSION
    assert z["obs_dim"] == 21 and z["obs_names"] == r["obs_names"] + list(OBSTACLE_OBS_NAMES)
    assert z["obs_names"] == list(obs_names(load_v2_config(zx.OBS_CONFIG))), "관측 21 거울 설정과 같은 이름"
    assert z["mask_version"] == 2 == r["mask_version"]
    assert z["contract_hash"] == HASH21 == f"0x{ex.contract_hash(z['obs_names'], 2):016x}"
    hdr = (ex.UE_POLICY_DIR / "EcoPolicyV3Inference.h").read_text(encoding="utf-8")
    assert re.search(r"kContractHashObs21Mask2 = 0x([0-9a-f]+)ULL", hdr).group(1) == HASH21[2:], "C++ 가 아는 관측 21 계약 해시"
    gold = (ex.UE_POLICY_DIR / "ObstacleObsGoldenVectorsV3.h").read_text(encoding="utf-8")
    assert f"kContractHashObs21Mask2 = {HASH21}ULL" in gold
    assert z["allowed"] == r["allowed"] == ["graze", "flee", "hide", "freeze"] and z["allowed_mask"] == r["allowed_mask"]
    assert z["thresholds"] == r["thresholds"] and z["hidden"] == 64 and z["num_behaviors"] == 5 and z["behaviors"] == r["behaviors"]
    assert z["id"] == f"v3_r1_g995_s3_obs21zero@{z['weights_sha256'][:8]}"
    assert z["golden"]["world_config"] == "configs/v3_wild3_obs_mirror.yaml" and z["golden"]["seed"] == ex.BRAIN_GOLDEN_SEED
    txt = ZERO.read_text(encoding="utf-8")
    assert "C:" not in txt and "\\Users" not in txt


def test_weights_are_r1b_plus_zero_columns(files):
    z, r = files
    wz, wr = _layers(z), _layers(r)
    assert [(L["out"], L["in"]) for L in z["layers"]] == [(64, 21), (64, 64), (5, 64)]
    assert np.array_equal(wz["W0"][:, :18].view(np.uint32), wr["W0"].view(np.uint32)), "첫 층 앞 18 열 = R1b"
    assert not wz["W0"][:, 18:].view(np.uint32).any(), "새 세 열 = +0.0 (비트 0)"
    for k in ("B0", "W1", "B1", "W2", "B2"):
        assert np.array_equal(wz[k].view(np.uint32), wr[k].view(np.uint32)), k
    raw = b"".join(base64.b64decode(L[f]) for L in z["layers"] for f in ("w_f32le_b64", "b_f32le_b64"))
    assert hashlib.sha256(raw).hexdigest() == z["weights_sha256"]


def test_golden_equals_r1b_on_first_18(files):
    z, r = files
    g = z["golden"]
    assert g["count"] == len(g["cases"]) >= 8
    obs = np.array([c["obs"] for c in g["cases"]], dtype=np.float32)
    mask = np.array([c["mask"] for c in g["cases"]], dtype=bool)
    logits = np.array([c["logits"] for c in g["cases"]], dtype=np.float32)
    act = np.array([c["action"] for c in g["cases"]])
    assert obs.shape[1] == 21
    extra = obs[:, 18:]
    assert ((extra > 0.0) & (extra < 1.0)).any(), "골든의 새 칸이 실제로 움직인다 (0·1 만이 아니다)"
    l21 = ex.forward_np(obs, _layers(z), np.float32)
    l18 = ex.forward_np(obs[:, :18], _layers(r), np.float32)
    assert np.abs(l21 - l18).max() < 1e-6, "새 열 0 — 로짓은 앞 18 칸만 본 R1b 와 같다"
    assert np.abs(l21 - logits).max() < 1e-5
    assert np.array_equal(ex.masked_argmax(logits, mask), act)
    assert np.all(ex.top_gap(logits, mask) >= ex.NEAR_TIE_GAP)
    assert len(set(act.tolist())) >= 2


def test_golden_config_choice():
    from env_v2.config import load_v2_config
    from env_v2.world import obs_names

    assert ex.brain_golden_config_for(obs_names(load_v2_config(ex.BRAIN_GOLDEN_CONFIG))) == ex.BRAIN_GOLDEN_CONFIG
    assert ex.brain_golden_config_for(obs_names(load_v2_config(ex.BRAIN_GOLDEN_CONFIG_OBS21))) == ex.BRAIN_GOLDEN_CONFIG_OBS21


@pytest.mark.skipif(not zx.SRC_MODEL.exists(), reason="ckpt 는 저장소에 없다 (R1b s3 모델 필요)")
def test_zero_model_and_brain_file_are_deterministic(files, tmp_path):
    from stable_baselines3 import PPO

    z, _ = files
    a = zx.zero_extend(out_model=tmp_path / "a" / "v3_r1_g995_s3_obs21zero.zip")
    b = zx.zero_extend(out_model=tmp_path / "b" / "v3_r1_g995_s3_obs21zero.zip")
    assert a["sha256"] == b["sha256"] == z["model"]["sha256"], "같은 원 모델이면 같은 zip 바이트 (두뇌 파일에 적힌 sha256)"
    assert a["err_logit"] == 0.0 and a["err_value"] == 0.0
    m = PPO.load(str(a["out"]), device="cpu")
    assert tuple(m.policy.rep_obs_names) == tuple(z["obs_names"]) and m.observation_space.shape == (26,)
    w0 = m.policy.mlp_extractor.policy_net[0].weight.detach().numpy()
    v0 = m.policy.mlp_extractor.value_net[0].weight.detach().numpy()
    assert not w0[:, 18:].any() and not v0[:, 18:].any(), "정책·가치망 첫 층 새 열 0"
    out = tmp_path / "v3_r1_g995_s3_obs21zero.json"
    ex.export_brain_file(a["out"], out, world_label=zx.WORLD_LABEL)
    # 모델 경로 칸만 다르다 (시험 zip 은 herbivore_rl/ 밖이라 파일 이름만 적힌다 — export_weights_v3.rel)
    got = out.read_bytes().replace(b'"path": "v3_r1_g995_s3_obs21zero.zip"', b'"path": "ckpt/v3/v3_r1_g995_s3_obs21zero.zip"')
    assert got == _lf(ZERO.read_bytes()), "저장소 두뇌 파일 = 지금 코드로 다시 만든 파일 (바이트 단위)"
