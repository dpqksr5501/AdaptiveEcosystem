"""두 길 두뇌 C++ 이식 검증 자료 (이식 계획서 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_ROUTE_CPP_PORT_PLAN.md 10-1·10-2) —
export_golden_v3_route.py → AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/RouteGoldenVectorsV3.h (10-24 C++ 이식 때 Source 골든 자리로 옮김) +
results/v3/route/port/RouteGoldenVectorsV3.json (같은 내용 — 장면 단위 골든),
results/v3/route/port/make_traces.py → results/v3/route/port/{brains,traj,stats}/·MANIFEST.json (판 단위 궤적 지문·세계 기록).

- 골든: 지금 코드로 다시 만든 헤더·JSON 이 올린 것과 바이트까지 같다(결정성), 헤더와 JSON 이 같은 내용이다, 계획 장면(과제 목록 — 도주 시작 두 칸·한 칸,
  SHELTER 문턱 근처, 무효, 2 초 잠금 뒤 RUN 다시 고르기·SHELTER 유지, 관측 21~23, 마스크 판 4 줄, 실행 덮기 방향, 길 통계, 다시 난 개체 + 계획서 10-1 의
  묶음 1~6 — 6 은 도망 길 기록 짜 맞춘 장면 포함, 13-3 판 5 마스크 줄)을 다 덮는다, 시드가 판정·학습 시드가 아니다. g++ 가 있으면 C++ 꼴 스칼라 참조
  (tests/cpp/route_ref_main.cpp)와 엔진 함수 하네스(tests/cpp/route_v3_main.cpp — 검사 본문 AI/Policy/Tests/RouteGoldenCheckV3.h: 기하·길 셈 줄·적용·
  장면 통계·마스크 판 4·5·관측·도망 길 기록 장면·기준 루프 지문 두뇌 둘)가 골든을 비트 단위로 다시 낸다.
- 판 단위: MANIFEST 의 파일 sha256·신선도 입력(world.py 등)이 지금 파일과 맞고, 판 24 (두뇌 2 × N·G × 지역 셋 × 시드 34900·34901), 결정 사건이 세계 길 통계와
  맞고, route0 은 늘 RUN·길 끈 obs21zero 기록과 같고, 늘 SHELTER 시험 두뇌는 열리면 늘 SHELTER, 두뇌 파일 순전파와 torch argmax 가 같고 근접 동점이 없다.
  늘 SHELTER 두뇌 파일·zip 을 다시 만들면 바이트가 같고, 지금 코드로 만든 일(스냅숏 → live.prepare → ceval.eval_items) 12 개의 지문이 MANIFEST 와 같고
  (ceval.py·live.py 는 신선도 입력 밖이라 일 지문으로 본다), 짧은 앞부분(두 판 × 150 스텝)을 다시 돌리면 스텝마다 지문 아홉 칸·결정·죽음 사건이 같다.
- 느린 시험 (표시: 환경 변수 ECO_ROUTE_PORT_SLOW=1 일 때만 돈다 — 프로세스 4 개로 약 6 분): make_traces.py --check (판 24 전부·두뇌·MANIFEST 를 다시 만들어
  바이트까지 같은지 — MANIFEST 의 commit 칸만 뺀다).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np
import pytest

from env.config import ROOT

PORT = ROOT / "results" / "v3" / "route" / "port"
UE_POLICY = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
HEADER = UE_POLICY / "RouteGoldenVectorsV3.h"                  # 10-24 Source 골든 자리 (다른 *GoldenVectorsV3.h 와 같다)
GOLDEN_JSON = PORT / "RouteGoldenVectorsV3.json"
MANIFEST = PORT / "MANIFEST.json"
REF_MAIN = ROOT / "tests" / "cpp" / "route_ref_main.cpp"
ENGINE_MAIN = ROOT / "tests" / "cpp" / "route_v3_main.cpp"
ROUTE0_ZIP = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs24route0.zip"
SLOW = os.environ.get("ECO_ROUTE_PORT_SLOW") == "1"
PREFIX_STEPS = 150
PREFIX_RUNS = ("v3_obs24route_shelter2__N__Forest__34900", "v3_r1_g995_s3_obs24route0__G__Highland__34901")

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ex():
    return _module("_export_golden_v3_route", ROOT / "export_golden_v3_route.py")


@pytest.fixture(scope="module")
def mt():
    return _module("_make_traces_route", PORT / "make_traces.py")


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- #
# 장면 단위 골든
# --------------------------------------------------------------------- #


def test_golden_regenerates_byte_identical(ex, tmp_path):
    """지금 코드로 다시 만든 헤더·JSON = 올린 것 (바이트). 계약 해시·칸 번호 상수가 헤더에 있다."""
    if not ROUTE0_ZIP.exists():
        pytest.skip("ckpt 는 저장소에 없다 (results/v3/route/route_extend.py 로 만든다) — 기준 루프 두뇌")
    r = ex.write(tmp_path)
    assert (tmp_path / ex.HEADER).read_bytes() == HEADER.read_bytes()
    assert (tmp_path / ex.JSON_NAME).read_bytes() == GOLDEN_JSON.read_bytes()
    h = r["header"]
    assert "kContractHashObs24Mask4 = 0xe302dee198197444ULL" in h
    assert "kSlotRun = 1;" in h and "kSlotShelter = 4;" in h and "kSlotReserved = 3;" in h and "kLockSteps = 15;" in h
    assert "kEnterU = 2.0;" in h and "kExitU = 0.0;" in h and "kMaxEdgeU = 20.0;" in h
    assert "template <class TConfig>" in h and "C.WildFlight.bRoute = true;" in h


def test_golden_seeds_are_not_judge_seeds(ex):
    """골든 시드는 탐색 시드 32080~32099 안이고 판정·학습·측정 시드가 아니다 (계획서 10-1 의 5)."""
    seeds = (ex.SEED_RESPAWN, ex.SEED_LOOP, ex.SEED_BENCH, ex.SEED_GEO, ex.SEED_OBS, *ex.WORLD_SEEDS)
    ex.check_seeds(*seeds)
    assert all(32080 <= s <= 32099 for s in seeds)
    for s in (37000, 37150, 34950, 32010):
        with pytest.raises(SystemExit):
            ex.check_seeds(s)


def _header_arrays(text: str) -> tuple[dict, dict]:
    """헤더의 숫자 배열·스칼라 상수 → {이름: (C 꼴, 값 목록)}, {이름: (C 꼴, 리터럴)} (const char* 배열은 한 줄이라 빠진다)."""
    arrays = {}
    for m in re.finditer(r"inline constexpr ([\w:]+) (k\w+)\[(\d+)\] = \{[^\n]*\n(.*?)\n\t\};", text, re.S):
        ctype, name, n, body = m.group(1), m.group(2), int(m.group(3)), m.group(4)
        vals = [v.strip() for v in body.replace("\n", " ").split(",") if v.strip()]
        assert len(vals) == n, name
        arrays[name] = (ctype, vals)
    scal = {m.group(2): (m.group(1), m.group(3)) for m in re.finditer(r"inline constexpr ([\w:]+) (k\w+) = ([^;{]+);", text)}
    return arrays, scal


def _int_lit(s: str) -> int:
    return int(s.rstrip("UL"), 0)


def test_golden_header_and_json_same_content(golden):
    """헤더 배열·상수와 JSON 의 같은 이름 칸이 같은 값이다 (double 은 비트 단위, float 는 float32 로)."""
    arrays, scal = _header_arrays(HEADER.read_text(encoding="utf-8"))
    names = [k for k in golden if k.startswith("k")]
    assert set(arrays) == set(names), set(arrays) ^ set(names)
    for name in names:
        ctype, vals = arrays[name]
        js = golden[name]
        assert len(vals) == len(js), name
        if ctype == "double":
            assert all(float(a) == float(b) for a, b in zip(vals, js)), name
        elif ctype == "float":
            assert all(np.float32(a.rstrip("f")) == np.float32(b) for a, b in zip(vals, js)), name
        else:
            assert all(_int_lit(a) == int(b) for a, b in zip(vals, js)), name
    for name, v in golden["consts"].items():
        ctype, lit = scal[name]
        if ctype == "double":
            assert float(lit) == float(v), name
        elif ctype == "float":
            assert np.float32(lit.rstrip("f")) == np.float32(v), name
        else:
            assert _int_lit(lit) == int(v), name


def test_golden_covers_plan(ex, golden):
    """계획 장면 꼬리표가 모두 한 줄 이상이고(꼬리표 목록 = PLAN), 손 장면·기하 경계·마스크 갈래·다시 난 길·관측 사례·기준 루프 두뇌 둘이 모두 있다.
    줄 수·꼴이 머리 상수와 맞다."""
    cov = ex.coverage(golden)
    assert list(cov) == [k for k, _ in ex.PLAN]
    assert golden["coverage"] == cov
    assert all(v > 0 for v in cov.values()), {k: v for k, v in cov.items() if v <= 0}
    c = golden["consts"]
    assert len(golden["kRowInt"]) == c["kRows"] * len(ex.ROW_INT) and len(golden["kRowObs"]) == 3 * c["kRows"]
    assert len(golden["kApplyInt"]) == c["kApplies"] * len(ex.APPLY_INT) and len(golden["kGeoInt"]) == 3 * c["kGeoCases"]
    assert len(golden["kTickThreat"]) == 2 * c["kThreats"] * c["kTicks"]
    kinds = set(golden["meta"]["geo_kinds"])
    for k in ("mu_eq_enter", "mu_below_enter", "cos_eq_zero", "cos_below_zero", "edge_eq_max", "edge_over_max", "keep_mu_zero", "keep_mu_below",
              "tie_low_index", "not_in_S_ignored", "wall_strip_x", "wall_strip_all", "mu_ulp_above_enter", "mu_ulp_below_enter", "edge_ulp_below_max",
              "edge_ulp_above_max", "keep_mu_ulp_above", "keep_mu_ulp_below", "cos_neg_zero", "s_empty_inf", "keep_behind_far", "keep_at_center",
              "keep_center_below_eps", "wall_strip_y_low", "random"):
        assert k in kinds, k
    assert c["kGeoCases"] >= 80                                                       # 계획서 10-1 의 1 '약 80 사례'
    sc = golden["meta"]["scenes"]
    assert len(sc) == c["kScenes"] >= 15
    for word in ("두 칸", "한 칸", "문턱", "무효", "잠금", "유지", "지움", "cur < 0"):
        assert any(word in s for s in sc), word
    # 손 장면 경계 값: μ = 2 문턱 줄의 관측 22 = float32(0.2), 관측 23 = 0.15
    obs = np.asarray(golden["kRowObs"], dtype=np.float32).reshape(-1, 3)
    assert ((obs[:, 1] == np.float32(0.2)) & (obs[:, 2] == np.float32(0.15))).any()
    # 판 4 마스크 줄에서 칸 3 은 늘 막힘, 허용은 먹기·도망·숨기
    mi = np.asarray(golden["kMaskInt"]).reshape(-1, len(ex.MASK_INT))
    assert not mi[:, 12 + 3].any() and (mi[:, 7:12] == [1, 1, 1, 0, 0]).all()
    # 다시 난 개체: 죽은 사슴의 terminal_obs 길 칸은 0
    ro = np.asarray(golden["kRespawnObs"], dtype=np.float32).reshape(-1, 6)
    assert len(ro) == c["kRespawnRows"] and not ro[:, 3:].any()
    # 관측 사례: μ = +∞ 는 관측 22 = 1, 도주 아님은 0 0 0 — 식을 다시 걸면 같은 float
    oi = np.asarray(golden["kObsCaseInt"]).reshape(-1, 2)
    od = np.asarray(golden["kObsCaseIn"]).reshape(-1, 2)
    oo = np.asarray(golden["kObsCaseOut"], dtype=np.float32).reshape(-1, 3)
    assert len(oi) == c["kObsCases"]
    for (p, o), (mu, e), want in zip(oi, od, oo):
        mu = float("inf") if mu >= c["kInf"] else float(mu)
        assert ex.route_obs_ref(bool(p), bool(o), mu, float(e)) == [float(v) for v in want]
    assert any(m >= c["kInf"] and w[1] == 1.0 for m, w in zip(od[:, 0], oo))
    # 기준 루프: 두뇌 둘의 지문·기록 길이, route0 은 SHELTER 를 고르지 않고 늘 SHELTER 두뇌는 고른다, 근접 동점 없음, route0 가중치 = 두뇌 파일
    nb, T = c["kWorldBrains"], c["kWorldSteps"]
    assert nb == 2 and len(golden["kWorldHash"]) == nb * (T + 1) and len(golden["kWorldRaw"]) == T * c["kWorldM"]
    wc = np.asarray(golden["kWorldCheck"]).reshape(nb, c["kWorldChecks"], c["kWorldCheckLen"])
    assert wc[0, -1, ex.WC_PICKED_SHELTER] == 0 and wc[0, -1, ex.WC_PICKED_RUN] > 0 and wc[1, -1, ex.WC_PICKED_SHELTER] > 0
    assert c["kWorldMinTopGap"] > ex.NEAR_TIE and 0 < c["kWorldFirstSplit"] <= T
    wb = golden["meta"]["world"]["brains"]
    r0 = json.loads(ex.ROUTE0_BRAIN.read_text(encoding="utf-8"))
    assert [b["name"] for b in wb] == ["route0", "shelter2"] and wb[0]["weights_sha256"] == r0["weights_sha256"]
    assert all(b["argmax_mismatch"] == 0 for b in wb)
    assert golden["kWorldBrainDelta"] == [-2.0, 2.0]
    # 도망 길 기록 짜 맞춘 장면 (계획서 10-1 의 6): 틱마다 재료·길 덩어리·사슴 칸, 끝 refled 1 (38 스텝 째만)
    fs = golden["meta"]["flight_scene"]
    assert all(fs["checks"].values()) and fs["ticks"] == c["kFsTicks"] == len(golden["kFsTickT"])
    assert len(golden["kFsBlock"]) == c["kFsTicks"] * c["kFlightRouteLen"] and len(golden["kFsTrack"]) == c["kFsTicks"] * c["kFsN"] * c["kFsTrackLen"]
    assert golden["kFsBlock"][-2] == 1 and golden["kFsBlock"][-1] == c["kFsRefleeSteps"] == 38


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")
def test_cpp_scalar_reference_matches_golden(tmp_path):
    """C++ 꼴 스칼라 참조(double, 사슴 하나)가 기하·길 셈 줄·적용·손 장면 통계·마스크·다시 난 개체·관측 사례를 비트 단위로 다시 낸다
    (FMA 축약 끔 — 계획서 9절 R16)."""
    exe = tmp_path / ("route_ref.exe" if sys.platform == "win32" else "route_ref")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-I", str(UE_POLICY), str(REF_MAIN),
                            "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and "PASS" in run.stdout, f"참조 실패:\n{run.stdout}\n{run.stderr}"


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")
def test_cpp_engine_matches_golden(tmp_path):
    """10-24 C++ 이식: 엔진 함수(EcoWorldV3.h Detail::RouteShelterGeometry·RouteStep·RouteApply·ClearRoute·FlightUpdate 의 도망 길 기록·Step 전체,
    EcoObservationV3.h WriteRouteObs, EcoPolicyV3Inference.h ApplyRouteMaskRows)가 골든을 비트 단위로 다시 낸다 — 기준 루프 지문(두뇌 둘 × 450 스텝)까지
    (검사 본문 AI/Policy/Tests/RouteGoldenCheckV3.h, FMA 축약 끔 — 계획서 9절 R16)."""
    exe = tmp_path / ("route_v3.exe" if sys.platform == "win32" else "route_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-Wno-unused-parameter", "-I",
                            str(UE_POLICY), str(ENGINE_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and run.stdout.strip().endswith("PASS"), f"엔진 하네스 실패:\n{run.stdout}\n{run.stderr}"


def test_golden_world_brain_is_port_brain(golden, manifest):
    """골든 기준 루프의 늘 SHELTER 두뇌 = 판 단위 대조의 늘 SHELTER 두뇌 파일 (가중치 sha256 같음)."""
    sh = manifest["brains"]["v3_obs24route_shelter2"]
    r0 = manifest["brains"]["v3_r1_g995_s3_obs24route0"]
    wb = golden["meta"]["world"]["brains"]
    assert wb[1]["weights_sha256"] == sh["weights_sha256"] and wb[0]["weights_sha256"] == r0["weights_sha256"]


# --------------------------------------------------------------------- #
# 판 단위 대조 자료 (brains·traj·stats·MANIFEST)
# --------------------------------------------------------------------- #


def test_manifest_files_and_freshness(mt, manifest):
    """MANIFEST: 판 24 (두뇌 2 × N·G × 지역 셋 × 시드 34900·34901 × 1800 스텝), 파일 sha256 = 실제 파일 (git 밖 zip 은 있으면), 신선도 입력 sha256 =
    지금 파일 (다르면 make_traces.py 로 다시 만든다), 일 지문 = 지금 스냅숏 세계."""
    names = [mt.run_name(*r) for r in mt.all_runs()]
    assert len(names) == 24 and [r["run"] for r in manifest["runs"]] == names
    w = manifest["world"]
    assert w["steps"] == mt.STEPS == 1800 and w["seeds"] == [34900, 34901] and w["regions"] == ["Barren", "Forest", "Highland"]
    assert w["world_set"] == {"features.wild_flight.route": True} and w["snapshot_sha256"] == mt.file_sha256(mt.SNAPSHOT)
    stale = {p: s for p, s in manifest["inputs"].items() if mt.file_sha256(ROOT / p) != s}
    assert not stale, f"입력이 바뀌었다 — python results/v3/route/port/make_traces.py 로 다시 만든다: {sorted(stale)}"
    for k, s in manifest["files"].items():
        p = PORT / k
        if k.endswith(".zip") and not p.exists():
            continue                                    # *.zip 은 git 밖 — make_traces.py 가 같은 바이트로 다시 만든다
        assert hashlib.sha256(p.read_bytes()).hexdigest() == s, k
    for r in manifest["runs"]:
        assert r["traj"] in manifest["files"] and r["stats"] in manifest["files"]
    for sub in ("brains", "traj", "stats"):
        assert (PORT / sub).is_dir()


def test_port_brains(mt, manifest):
    """brains/: route0 = results/v3/route/brains 두뇌 파일 그대로, 늘 SHELTER 시험 두뇌 = 같은 계약(관측 24·판 4·0xe302…)·모델 경로 = port/brains zip,
    출력층은 route0 과 칸 4 편향만 다르다 (칸 1 + 2 대 칸 1 − 2). 두뇌 파일 자체 골든 사례를 numpy 순전파가 다시 낸다."""
    import export_weights_v3 as ew

    r0 = PORT / "brains" / "v3_r1_g995_s3_obs24route0.json"
    sh = PORT / "brains" / "v3_obs24route_shelter2.json"
    assert r0.read_bytes() == mt.ROUTE0_SRC.read_bytes()
    a, b = json.loads(r0.read_text(encoding="utf-8")), json.loads(sh.read_text(encoding="utf-8"))
    assert b["contract_hash"] == a["contract_hash"] == "0xe302dee198197444" and b["mask_version"] == 4 and b["obs_dim"] == 24
    assert b["model"]["path"] == "results/v3/route/port/brains/v3_obs24route_shelter2.zip" and b["allowed"] == a["allowed"]
    wa, wb = mt.brain_weights(r0), mt.brain_weights(sh)
    for k in ("W0", "B0", "W1", "B1", "W2"):
        assert np.array_equal(wa[k], wb[k]), k
    assert np.array_equal(np.delete(wa["B2"], 4), np.delete(wb["B2"], 4))
    assert wb["B2"][4] == np.float32(wb["B2"][1] + np.float32(2.0)) and wa["B2"][4] == np.float32(wa["B2"][1] - np.float32(2.0))
    for d, W in ((a, wa), (b, wb)):
        cases = d["golden"]["cases"]
        obs = np.asarray([c["obs"] for c in cases], dtype=np.float32)
        mask = np.asarray([c["mask"] for c in cases], dtype=bool)
        assert (ew.masked_argmax(ew.forward_np(obs, W, np.float32), mask) == [c["action"] for c in cases]).all()


def _stats(name: str) -> dict:
    return json.loads((PORT / "stats" / f"{name}.json").read_text(encoding="utf-8"))


def test_stats_events_match_world(mt, manifest):
    """판마다: 궤적 줄 = T + 1, 결정 사건 수 = 세계 길 결정 수, 적용된 결정(마지막 상태 앞) = picked 합, 죽음 사건 = 잡힘 + 굶음. route0 은 늘 RUN 이고
    길 끈 obs21zero 기록과 같다(계획서 10-2 조건 1). 늘 SHELTER 시험 두뇌는 SHELTER 가 열리면 늘 SHELTER (choice = picked_shelter > 0). 두뇌 파일
    순전파와 torch argmax 가 같고 근접 동점(< 1e-4)이 없다. 늘 SHELTER 판들은 실제로 은신처에 숨는다."""
    hidden = 0
    for b, wd, r, s in mt.all_runs():
        nm = mt.run_name(b, wd, r, s)
        d = _stats(nm)
        T = d["steps"]
        head, rows = mt.read_traj(PORT / "traj" / f"{nm}.jsonl.gz")
        assert head["groups"] == list(mt.GROUPS) and len(rows) == T + 1 and [x[0] for x in rows] == list(range(T + 1))
        assert all(len(x) == 1 + len(mt.GROUPS) and all(len(h) == mt.HEX for h in x[1:]) for x in rows)
        ev = np.asarray(d["events"]["decide"], dtype=np.int64).reshape(-1, 7)
        rt = d["record"]["flight"]["route"]
        assert len(ev) == rt["decisions"] == d["summary"]["decisions"] > 0, nm
        applied = ev[ev[:, 0] < T]
        assert rt["picked"]["run"] + rt["picked"]["shelter"] == len(applied), nm
        assert rt["picked"]["shelter"] == int((applied[:, 6] == 2).sum()) and rt["choice"] == int(applied[:, 3].sum()), nm
        if b == mt.ROUTE0:
            assert rt["picked"]["shelter"] == 0 and rt["steps"]["shelter"] == 0 and d["route_off"]["same"] is True, nm
        else:
            assert rt["picked"]["shelter"] == rt["choice"] > 0 and rt["steps"]["shelter"] > 0, nm
            hidden += d["summary"]["hidden"]
        assert rt["bad_shelter"] == 0 and d["check"]["argmax_mismatch"] == 0 and d["check"]["near_ties"] == 0, nm
        assert d["summary"]["caught"] + d["summary"]["starved"] + d["summary"]["alive"] == d["n"] == 128
        assert len(d["events"]["death"]) == d["summary"]["caught"] + d["summary"]["starved"]
        assert d["trace"]["record_same"] is True and d["job"]["digest"] == manifest["world"]["job_digests"][f"{wd}__{r}__{s}"]
    assert hidden > 0


def test_shelter_brain_regenerates(mt, tmp_path):
    """늘 SHELTER 시험 두뇌 zip·두뇌 파일을 지금 코드로 다시 만들면 올린 것과 바이트가 같다 (zip 은 git 밖이면 MANIFEST sha256 과)."""
    if not ROUTE0_ZIP.exists():
        pytest.skip("ckpt 는 저장소에 없다 (results/v3/route/route_extend.py 로 만든다)")
    mt.make_brains(tmp_path, log=lambda *_: None)
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for f in ("v3_obs24route_shelter2.json", "v3_r1_g995_s3_obs24route0.json", "v3_obs24route_shelter2.zip"):
        want = man["files"][f"brains/{f}"]
        assert hashlib.sha256((tmp_path / f).read_bytes()).hexdigest() == want, f


def test_traces_prefix_regenerates(mt, tmp_path):
    """짧은 앞부분: 두 판(늘 SHELTER N 숲·route0 G 고지)을 지금 코드로 150 스텝 다시 돌리면 스텝마다 지문 아홉 칸과 결정·죽음 사건이 올린 판의 앞부분과 같다."""
    if not ROUTE0_ZIP.exists():
        pytest.skip("ckpt 는 저장소에 없다 (results/v3/route/route_extend.py 로 만든다)")
    folder = mt.BRAIN_DIR
    if not mt.brain_zip(mt.SHELTER2).exists():                 # git 밖 zip 이 없으면 임시 폴더에 다시 만든다 (두뇌 파일은 올린 것과 같아야 한다)
        mt.make_brains(tmp_path, log=lambda *_: None)
        assert (tmp_path / f"{mt.SHELTER2}.json").read_bytes() == mt.brain_json(mt.SHELTER2).read_bytes()
        folder = tmp_path
    import torch

    prev = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        jobs = mt.make_jobs(PREFIX_STEPS)
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        assert {f"{wd}__{r}__{s}": mt.job_digest(j) for (wd, r, s), j in sorted(jobs.items())} == man["world"]["job_digests"],             "일 지문이 MANIFEST 와 다르다 (ceval.py·live.py·스냅숏 바탕이 바뀌었다) — python results/v3/route/port/make_traces.py 로 다시 만든다"
        for name in PREFIX_RUNS:
            b, wd, r, s = name.split("__")
            new = mt.trace_run(jobs[(wd, r, int(s))], b, PREFIX_STEPS, folder)
            _, rows = mt.read_traj(PORT / "traj" / f"{name}.jsonl.gz")
            got = [json.loads(x) for x in new["lines"]]
            assert got == rows[:PREFIX_STEPS + 1], name
            old = _stats(name)["events"]
            assert new["events"]["decide"] == [e for e in old["decide"] if e[0] <= PREFIX_STEPS], name
            assert new["events"]["death"] == [e for e in old["death"] if e[0] <= PREFIX_STEPS], name
    finally:
        torch.set_num_threads(prev)


def test_digest_state_accepts_lists(mt):
    """지문은 numpy 배열과 같은 값의 목록(평가기 trace 를 json 으로 읽은 꼴)에 같다 — C++ trace 를 같은 함수로 견줄 수 있다."""
    rng = np.random.default_rng(0)
    N, M = 5, 4
    st = dict(t=3, dark=0.25, pred_ema=0.5, **{k: rng.random(N) for k in ("x", "y", "hx", "hy", "energy", "reserve")},
              behavior=np.array([0, 1, 2, 0, 1]), request=np.array([0, 1, 1, 2, 0]), keep=np.array([0, 2, 0, 3, 0]), cause=np.array([0, 0, 1, 0, 0]),
              obs=rng.random((N, 24)).astype(np.float32), **{k: rng.random((N, 2)) for k in mt.VEC_KEYS},
              wolves=dict(x=rng.random(M), y=rng.random(M), hx=rng.random(M), hy=rng.random(M), cd=np.arange(M), sat=np.zeros(M),
                          asleep=np.array([False, True, False, False]), target=np.array([-1, 2, 0, -1])),
              route=np.array([-1, 0, -1, -1, 2]), route_k=np.array([-1, -1, -1, -1, 1]), route_age=np.array([0, 3, 0, 0, 7]),
              route_feas=np.array([0, 2, 0, 0, 2]), route_decide=np.array([False, True, False, False, False]), route_req=np.array([-1, 4, -1, -1, -1]))

    def as_lists(x):
        if isinstance(x, dict):
            return {k: as_lists(v) for k, v in x.items()}
        return x.tolist() if isinstance(x, np.ndarray) else x

    alive0 = np.array([True, True, True, False, True])
    assert mt.digest_state(st, alive0) == mt.digest_state(json.loads(json.dumps(as_lists(st))), alive0.tolist())


@pytest.mark.skipif(not SLOW, reason="느림 (프로세스 4 개로 약 6 분) — ECO_ROUTE_PORT_SLOW=1 이면 돈다")
@pytest.mark.skipif(not ROUTE0_ZIP.exists(), reason="ckpt 는 저장소에 없다")
def test_traces_full_regenerates_byte_identical():
    """[느림] 판 24 개 전부(1800 스텝)·두뇌·MANIFEST 를 다시 만들면 올린 파일과 바이트까지 같다 (make_traces.py --check)."""
    run = subprocess.run([sys.executable, str(PORT / "make_traces.py"), "--check", "--workers", "4"], cwd=str(ROOT), capture_output=True, text=True,
                         encoding="utf-8", env=dict(os.environ, PYTHONUTF8="1"))
    assert run.returncode == 0 and "최신이다" in run.stdout, f"{run.stdout[-3000:]}\n{run.stderr[-3000:]}"
