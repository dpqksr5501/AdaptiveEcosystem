"""§8.3 완료 기준 — 내보낸 가중치가 파이썬과 같은 값을 내는가.

여기가 파이썬 → 언리얼 다리의 유일한 검증 지점이다. 이게 통과하면 언리얼에서
`RunPolicy` 가 파이썬 정책과 같은 행동을 낸다는 뜻이다 (§9.8-1).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from env.config import load_config
from env.vec_env import sigmoid
from export_weights import EXPORT, GENERATED, UE_POLICY_DIR, extract, forward

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "ckpt" / "final.zip"
CPP_MAIN = ROOT / "tests" / "cpp" / "parity_main.cpp"

needs_export = pytest.mark.skipif(
    not (EXPORT / "PolicyWeights.h").exists(),
    reason="export/ 없음. `python export_weights.py` 를 먼저 돌려라 (§8.1).",
)
needs_gcc = pytest.mark.skipif(
    shutil.which("g++") is None, reason="g++ 없음 (§8.3 문법 검사에 필요)"
)


@pytest.fixture(scope="module")
def weights():
    from stable_baselines3 import PPO

    if not MODEL.exists():
        pytest.skip(f"{MODEL} 없음")
    return extract(PPO.load(MODEL, device="cpu"))


@pytest.fixture(scope="module")
def golden():
    p = EXPORT / "verify.npz"
    if not p.exists():
        pytest.skip("export/verify.npz 없음")
    d = np.load(p)
    return d["obs"], d["out"]


# --------------------------------------------------------------------- #
# §8.1 형식
# --------------------------------------------------------------------- #


def test_only_the_three_inference_layers_are_extracted(weights):
    """§8.1 — value_net, log_std, optimizer 상태는 버린다."""
    assert set(weights) == {"W0", "B0", "W1", "B1", "W2", "B2"}
    assert weights["W0"].shape == (64, 7)
    assert weights["W1"].shape == (64, 64)
    assert weights["W2"].shape == (4, 64)
    assert weights["B0"].shape == (64,)
    assert weights["B1"].shape == (64,)
    assert weights["B2"].shape == (4,)
    assert all(v.dtype == np.float32 for v in weights.values())


@needs_export
def test_header_comment_is_generated_not_handwritten():
    """§12 — 헤더 주석을 손으로 적지 말 것. 학습 설정에서 자동으로 채워야 한다."""
    cfg = load_config()
    txt = (EXPORT / "PolicyWeights.h").read_text(encoding="utf-8")
    assert "자동 생성. 수정 금지." in txt
    assert "layers:     7-64-64-4" in txt
    assert "activation: tanh" in txt
    assert "output:     clamp(-3,3) -> sigmoid" in txt
    assert f"pred_count/{cfg.obs_pred_count_norm:g}" in txt
    assert f"kin_count/{cfg.obs_kin_count_norm:g}" in txt
    assert f"see_r={cfg.see_r:g}" in txt
    assert "generated:  20" in txt              # ISO timestamp
    assert "final.zip" in txt                   # 어느 체크포인트에서 왔는지


@needs_export
def test_header_declares_every_array_with_the_right_size():
    txt = (EXPORT / "PolicyWeights.h").read_text(encoding="utf-8")
    for name, n in [("W0", 448), ("B0", 64), ("W1", 4096),
                    ("B1", 64), ("W2", 256), ("B2", 4)]:
        assert f"static const float {name}[{n}]" in txt, name


@needs_export
def test_values_are_written_with_8_decimals():
    """§8.1 — 값은 %.8f. 자릿수가 모자라면 1e-5 파리티가 깨진다."""
    import re

    txt = (EXPORT / "PolicyWeights.h").read_text(encoding="utf-8")
    nums = re.findall(r"-?\d+\.(\d+)f", txt)
    assert nums, "부동소수 리터럴이 없다"
    assert all(len(d) == 8 for d in nums[:200])


# --------------------------------------------------------------------- #
# §8.2 / §8.3 수치 일치
# --------------------------------------------------------------------- #


def test_numpy_forward_matches_sb3_predict(weights, golden):
    """§8.3 — numpy 순전파 vs SB3 predict 차이 1e-5 이내."""
    from stable_baselines3 import PPO

    obs, expected = golden
    model = PPO.load(MODEL, device="cpu")
    ref = sigmoid(model.predict(obs, deterministic=True)[0])
    assert np.abs(ref - expected).max() <= 1e-5      # 저장된 값이 곧 predict 결과
    assert np.abs(forward(obs, weights) - ref).max() <= 1e-5


def test_forward_applies_clamp_before_sigmoid(weights):
    """§9.3 C++와 같은 순서여야 한다. clamp를 빼면 경계에서 값이 갈린다."""
    obs = np.random.default_rng(0).random((64, 7)).astype(np.float32)
    out = forward(obs, weights)
    lo, hi = sigmoid(np.array([-3.0])), sigmoid(np.array([3.0]))
    assert (out >= lo - 1e-6).all() and (out <= hi + 1e-6).all()


@needs_export
def test_verify_npz_holds_post_sigmoid_outputs(golden):
    """§8.1 — 관측 100개, **sigmoid 후** 출력 100개."""
    obs, out = golden
    assert obs.shape == (100, 7) and out.shape == (100, 4)
    assert (obs >= 0).all() and (obs <= 1).all()
    assert (out > 0).all() and (out < 1).all()       # sigmoid 후라 열린 구간
    assert np.abs(out - 0.5).max() > 0.05, "전부 0.5 근처면 sigmoid를 두 번 먹인 것이다"


# --------------------------------------------------------------------- #
# §8.3 C 문법 / §9.8-1 C++ 파리티
# --------------------------------------------------------------------- #


# §8.3은 `PolicyWeights.h` 가 "컴파일 가능한 C 문법"이기를 요구한다. 골든 벡터도 순수
# 배열이라 C로 통과한다. `UtilityParams.h` 는 namespace를 쓰므로 C++ 로만 검사한다.
HEADER_LANG = {
    "PolicyWeights.h": "c",
    "PolicyGoldenVectors.h": "c",
    "UtilityParams.h": "c++",
}


@needs_export
@needs_gcc
@pytest.mark.parametrize("name", GENERATED)
def test_generated_header_compiles(name):
    """§8.3 — gcc -fsyntax-only 통과."""
    lang = HEADER_LANG[name]
    r = subprocess.run(
        ["gcc", "-fsyntax-only", "-Wno-pragma-once-outside-header", "-x", lang,
         str(EXPORT / name)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"[{lang}] {r.stderr}"


@needs_export
@needs_gcc
def test_utility_params_header_is_generated_from_tuning():
    """§9.7 — 비교군 계수를 C++에 손으로 옮기면 §0의 동일 조건이 깨진다."""
    from policies.utility import load_best_params

    txt = (EXPORT / "UtilityParams.h").read_text(encoding="utf-8")
    assert "자동 생성. 수정 금지." in txt
    assert "utility_best.yaml" in txt
    for k, v in load_best_params().items():
        cname = k[0].upper() + k[1:]
        assert f"{cname} = {v:.8f}f" in txt, k


@needs_export
@needs_gcc
def test_cpp_inference_matches_python_within_1e_5(tmp_path):
    """§9.8-1 — 언리얼 모듈의 `EcoPolicyInference.h` 를 그대로 컴파일해 대조한다.

    이 테스트가 파이썬 → 언리얼 다리의 본체다. 엔진 없이 gcc만으로 돌기 때문에
    UE 빌드가 깨져 있어도 수치 계약은 여기서 지켜진다.
    """
    if not UE_POLICY_DIR.is_dir():
        pytest.skip(f"언리얼 모듈 경로 없음: {UE_POLICY_DIR}")
    exe = tmp_path / ("parity.exe" if sys.platform == "win32" else "parity")
    build = subprocess.run(
        ["g++", "-std=c++17", "-O2", "-Wall", "-Werror",
         "-I", str(UE_POLICY_DIR), str(CPP_MAIN), "-o", str(exe)],
        capture_output=True, text=True,
    )
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"

    run = subprocess.run([str(exe)], capture_output=True, text=True)
    assert run.returncode == 0, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
    assert "PASS" in run.stdout, run.stdout


@needs_export
def test_unreal_module_has_the_generated_headers():
    """export_weights.py 가 언리얼 모듈에도 복사했는가. 손으로 옮기면 언젠가 어긋난다."""
    if not UE_POLICY_DIR.is_dir():
        pytest.skip(f"언리얼 모듈 경로 없음: {UE_POLICY_DIR}")
    for name in GENERATED:
        ue = UE_POLICY_DIR / name
        assert ue.exists(), f"{name} 이 언리얼 모듈에 없다"
        assert ue.read_bytes() == (EXPORT / name).read_bytes(), f"{name} 내용이 다르다"
