"""야생 (w3) 도망 기록 C++ 골든 (10-21 사용자 '언리얼에서 도는 두뇌를 굳이 파이썬으로 다시 시험하지 말고 언리얼 자체에서 평가' — C++ 평가기·게임 화면이
파이썬 `World.flight_stats` 와 같은 정의로 센다).

- export_golden_v3_flight.py → AI/Policy/FlightGoldenVectorsV3.h 가 지금 코드로 다시 만든 헤더와 바이트 단위로 같다.
- g++ 하네스 tests/cpp/flight_v3_main.cpp (검사 본문 = UE 시험 AdaptiveEcosystem.Policy.V3.Flight.* 의 Tests/FlightGoldenCheckV3.h): 짜 맞춘 장면·
  거울 세계 600 스텝 재료 되풀이·쌍 장면이 파이썬과 같고, C++ 기준 루프는 기록 켬·끔 궤적이 비트 단위로 같다.
- 내보내기의 재료 감싸기(`Recorder`)는 세계를 바꾸지 않는다: 감싼 세계와 감싸지 않은 세계의 도망 기록·궤적이 같다.
시드는 내보내기 전용 32098·32099 만 쓴다.
"""

import importlib.util
import shutil
import subprocess
import sys

import numpy as np
import pytest

from env.config import ROOT
from env_v2.config import load_v2_config
from env_v2.world import World

UE_POLICY = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
FL_CPP_MAIN = ROOT / "tests" / "cpp" / "flight_v3_main.cpp"
OBS = ROOT / "configs" / "v3_wild3_obs_mirror.yaml"


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_flight_golden_header_is_fresh():
    """언리얼 모듈의 FlightGoldenVectorsV3.h 는 지금 코드로 다시 만든 헤더와 바이트 단위로 같다."""
    path = UE_POLICY / "FlightGoldenVectorsV3.h"
    if not path.exists():
        pytest.skip("언리얼 모듈 도망 기록 골든 헤더 없음")
    ex = _module("_export_golden_v3_flight", ROOT / "export_golden_v3_flight.py")
    assert path.read_bytes() == ex.build_header().encode("utf-8")


def test_recorder_does_not_change_world():
    """재료 감싸기는 원래 `_fl_update` 를 그대로 부른다 — 감싼 세계의 도망 기록·위치가 감싸지 않은 세계와 같다."""
    ex = _module("_export_golden_v3_flight_rec", ROOT / "export_golden_v3_flight.py")
    out = []
    for wrap in (False, True):
        w = World(load_v2_config(OBS).replace(N=16), seeds=[32098])
        w.track_flight = True
        rec = ex.Recorder(w) if wrap else None
        rng = np.random.default_rng(3)
        for _ in range(200):
            w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        out.append((w.flight_stats(), w.pos.copy(), w.pred_pos.copy()))
        if wrap:
            assert len(rec.deer) == 200 and all(len(r) == w.N for r in rec.deer) and all(len(r) == w.M for r in rec.wolf_bits)
    assert out[0][0] == out[1][0]
    np.testing.assert_array_equal(out[0][1], out[1][1])
    np.testing.assert_array_equal(out[0][2], out[1][2])


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")
def test_cpp_flight_matches_golden_with_gpp(tmp_path):
    """언리얼 모듈의 EcoWorldV3.h·도망 기록 골든 헤더를 그대로 g++ 로 컴파일해 대조한다(UE 시험 Policy.V3.Flight.Golden·Pairs·Identity 와 같은 검사 본문)."""
    if not (UE_POLICY / "FlightGoldenVectorsV3.h").exists():
        pytest.skip("언리얼 모듈 도망 기록 골든 헤더 없음")
    exe = tmp_path / ("flight_v3.exe" if sys.platform == "win32" else "flight_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-Wno-unused-parameter", "-I", str(UE_POLICY),
                            str(FL_CPP_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
