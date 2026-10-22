"""R5 장애물 관측 골든 — export_golden_v3_obstacle_obs.py → ObstacleObsGoldenVectorsV3.h (계약 POLICY_CONTRACT_V3.md 2-4, 11-4 G11).

올린 사본 results/v3/r5/golden/ObstacleObsGoldenVectorsV3.h 는 지금 코드로 다시 만든 헤더와 바이트 단위로 같다(결정성 — 같은 코드·설정이면 같은 바이트).
언리얼 모듈에 헤더가 있으면(C++ 단계 뒤) 그것도 같다. g++ 가 있으면 계약 2-4 의 C++ 꼴 스칼라 참조(tests/cpp/obstacle_obs_ref_main.cpp)를 컴파일해
골든 435 사례와 비트 단위로 같은지 본다. 시드는 이 골든 전용 탐색 시드 32093·32094 다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import shutil
import subprocess
import sys

import pytest

from env.config import ROOT

COPY = ROOT / "results" / "v3" / "r5" / "golden" / "ObstacleObsGoldenVectorsV3.h"
UE_POLICY = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
REF_MAIN = ROOT / "tests" / "cpp" / "obstacle_obs_ref_main.cpp"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built():
    if not R1_MODEL.exists():
        pytest.skip("롤아웃 사례에 게임 두뇌 모델이 필요하다")
    ex = _module("_export_golden_v3_obstacle_obs", ROOT / "export_golden_v3_obstacle_obs.py")
    return ex, ex.build_header()


def test_golden_copy_is_fresh(built):
    ex, text = built
    assert COPY.read_bytes() == text.encode("utf-8")
    assert "kContractHashObs21Mask2 = 0xbc4fc2d45c47c5fdULL" in text
    assert "kEscapeNorm = 10.0" in text and "kNearNorm = 5.0" in text and "kBodyR = 0.15" in text
    ue = UE_POLICY / ex.HEADER
    if ue.exists():
        assert ue.read_bytes() == text.encode("utf-8")


def test_golden_seeds_are_not_judge_seeds(built):
    ex, _ = built
    ex.check_seeds(ex.SEED_LAYOUT, ex.SEED_CASE)
    for s in (33100, 33000, 10005):
        with pytest.raises(SystemExit):
            ex.check_seeds(s)


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")
def test_scalar_reference_matches_golden_with_gpp(tmp_path):
    exe = tmp_path / ("obstacle_obs_ref.exe" if sys.platform == "win32" else "obstacle_obs_ref")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-I", str(COPY.parent), str(REF_MAIN), "-o", str(exe)],
                           capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
