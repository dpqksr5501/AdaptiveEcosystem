"""10-27 고침 C++ 골든 (사용자 '평소 사슴이 제자리에서 빙빙 돈다'·'쉬는 늑대 곁에서 멈춰 있다' — 먹기 걷기 고침·거리 두기를 파이썬·C++ 에 같이 넣는다).

- export_golden_v3_calm.py → AI/Policy/CalmGoldenVectorsV3.h 가 지금 코드로 다시 만든 헤더와 바이트 단위로 같다.
- 손 장면이 뜻대로다(거리 두기 시작·시야각 밖·이어짐·V + 여유 경계 ± ulp·들어갈 때 V 경계·가림·은신처 안·사냥 늑대 우선·도주 우선·두 늑대·자는 늑대·발소리·
  죽음·밤, 10-27 적대적 검토 — 이어지는 거리 두기의 방향 관성·벽 앞 굽히는 쪽).
- g++ 하네스 tests/cpp/calm_v3_main.cpp (검사 본문 = UE 시험 AdaptiveEcosystem.Policy.V3.Calm.* 의 Tests/CalmGoldenCheckV3.h): 방향·제어·덮기 장면·B 장면·
  기준 루프(지역 둘 × 두 고침 켬·끔·끈 칸 엉뚱한 값, 600 스텝 지문)가 파이썬과 비트 단위로 같다.
시드는 탐색 32081~32089 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import shutil
import subprocess
import sys

import numpy as np
import pytest

from env.config import ROOT
from env_v2.world import WF_ALERT, WF_NONE, WF_PANIC, WF_REST

UE_POLICY = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
CPP_MAIN = ROOT / "tests" / "cpp" / "calm_v3_main.cpp"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ex():
    return _module("_export_golden_v3_calm", ROOT / "export_golden_v3_calm.py")


def test_calm_golden_header_is_fresh(ex):
    """언리얼 모듈의 CalmGoldenVectorsV3.h 는 지금 코드로 다시 만든 헤더와 바이트 단위로 같다."""
    path = UE_POLICY / "CalmGoldenVectorsV3.h"
    if not path.exists():
        pytest.skip("언리얼 모듈 10-27 고침 골든 헤더 없음")
    assert path.read_bytes() == ex.build_header().encode("utf-8")


def test_hand_scenes_mean_what_they_say(ex):
    """덮기 장면의 손 장면(사슴 2)이 설계대로다 — 생성기가 적는 값이 뜻과 맞는지(골든이 틀린 동작을 굳히지 않게)."""
    w = ex.scene_world()
    scs, res, tags, hand = ex.scenes(w)
    want = {"rest_start_sated": WF_REST, "rest_start_eating": WF_REST, "rear_blind": WF_NONE, "keep_memory_rear": WF_REST,
            "keep_exact_out": WF_REST, "keep_out_plus_ulp": WF_NONE, "start_exact_V": WF_REST, "start_V_plus_ulp": WF_NONE,
            "occluded": WF_NONE, "occluded_keep_ends": WF_NONE, "in_cover": WF_NONE, "hunting_alert_wins": WF_ALERT, "panic_wins": WF_PANIC,
            "two_resting": WF_REST, "asleep_ignored": WF_NONE, "heard_rear": WF_REST, "dead": WF_NONE, "wall": WF_REST, "corner": WF_REST,
            "night_far": WF_NONE, "night_near": WF_REST, "facing_away_seen_by_pvis_no": WF_NONE, "from_alert": WF_REST,
            "from_panic_release": WF_PANIC, "panic_released_far": WF_NONE, "keep_inertia": WF_REST, "keep_inertia_opposite": WF_REST,
            "start_no_inertia": WF_REST, "keep_inertia_wall": WF_REST, "keep_inertia_wall_other": WF_REST}
    got = {tags[k]: int(res[k]["mode"][2]) for k in range(hand)}
    assert got == want
    k = tags.index("rest_start_sated")
    assert res[k]["dir"][2].tolist() == [-1.0, -0.0]                       # 늑대(+x) 반대로
    # 10-27 적대적 검토 — 이어지는 거리 두기의 방향 관성: 지난 방향을 이어받고(합이 0 이면 반대 방향 그대로), 시작·지난 경계는 잇지 않는다
    h = np.sqrt(0.5)
    np.testing.assert_allclose(res[tags.index("keep_inertia")]["dir"][2], [-h, h], atol=1e-15)
    for t in ("keep_inertia_opposite", "start_no_inertia", "from_alert"):
        assert res[tags.index(t)]["dir"][2].tolist() == [-1.0, -0.0], t
    # 벽 앞 정면 늑대: 굽히는 쪽(벽을 따라 어느 쪽)이 지난 쪽을 따른다 — 스텝마다 좌우로 뒤집히지 않는다
    dl, dr = res[tags.index("keep_inertia_wall")]["dir"][2], res[tags.index("keep_inertia_wall_other")]["dir"][2]
    assert dl[0] < 0.0 < dr[0] and dl[1] <= 0.0 and dr[1] <= 0.0
    k = tags.index("panic_released_far")
    assert int(res[k]["lock"][2]) == 0                                      # 도주가 풀리면 잠금 0 (그대로)


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")
def test_cpp_calm_matches_golden_with_gpp(tmp_path):
    """언리얼 모듈의 EcoRepertoire.h·EcoWorldV3.h·10-27 고침 골든 헤더를 그대로 g++ 로 컴파일해 대조한다(UE 시험 Policy.V3.Calm.* 와 같은 검사 본문)."""
    if not (UE_POLICY / "CalmGoldenVectorsV3.h").exists():
        pytest.skip("언리얼 모듈 10-27 고침 골든 헤더 없음")
    exe = tmp_path / ("calm_v3.exe" if sys.platform == "win32" else "calm_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-Wno-unused-parameter", "-I", str(UE_POLICY),
                            str(CPP_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
