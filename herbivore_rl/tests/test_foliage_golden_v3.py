"""숲 시야 C++ 골든 (10-22 — 12880eb 의 파이썬 숲 시야 obstacles.foliage 를 C++ 에 옮김, 기본 끔).

- export_golden_v3_foliage.py → AI/Policy/FoliageGoldenVectorsV3.h 가 지금 코드로 다시 만든 헤더와 바이트 단위로 같다.
- g++ 하네스 tests/cpp/foliage_v3_main.cpp (검사 본문 = UE 시험 AdaptiveEcosystem.Policy.V3.Foliage.* 의 Tests/FoliageGoldenCheckV3.h): 눈길 길이
  (a ↔ b 비트 동일·잎 구간 64 넘는 길)·관측 threat_hidden·쌍 장면(늑대 표적·잎만 가림)·도망 기록 lost_foliage 가 파이썬과 같고, 거울 세계 450 스텝
  숲 시야 켬·끔이 파이썬(동족 차례 합 기하)과 스텝마다 지문까지 비트 단위로 같다.
시드는 내보내기 전용 32090~32097 만 쓴다.
"""

import importlib.util
import shutil
import subprocess
import sys

import pytest

from env.config import ROOT

UE_POLICY = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
CPP_MAIN = ROOT / "tests" / "cpp" / "foliage_v3_main.cpp"


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_foliage_golden_header_is_fresh():
    """언리얼 모듈의 FoliageGoldenVectorsV3.h 는 지금 코드로 다시 만든 헤더와 바이트 단위로 같다."""
    path = UE_POLICY / "FoliageGoldenVectorsV3.h"
    if not path.exists():
        pytest.skip("언리얼 모듈 숲 시야 골든 헤더 없음")
    ex = _module("_export_golden_v3_foliage", ROOT / "export_golden_v3_foliage.py")
    assert path.read_bytes() == ex.build_header().encode("utf-8")


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")
def test_cpp_foliage_matches_golden_with_gpp(tmp_path):
    """언리얼 모듈의 엔진 무관 헤더·숲 시야 골든을 그대로 g++ 로 컴파일해 대조한다 (UE 시험 Policy.V3.Foliage.Golden·World·Off 와 같은 검사 본문)."""
    if not (UE_POLICY / "FoliageGoldenVectorsV3.h").exists():
        pytest.skip("언리얼 모듈 숲 시야 골든 헤더 없음")
    exe = tmp_path / ("foliage_v3.exe" if sys.platform == "win32" else "foliage_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-Wno-unused-parameter", "-I", str(UE_POLICY),
                            str(CPP_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
