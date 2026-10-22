"""네이티브 두뇌 평가기 (AdaptiveEcosystem/Tools/EcoV3Eval — 게임의 엔진 무관 세계 코드 EcoWorldV3.h 를 엔진 없이, results/v3/live/ceval.py).

- numpy PCG64 이어 받기가 numpy 와 같은 64 비트 수열을 낸다.
- 저장소 두뇌 파일이 평가기의 검사(계약·차원·문턱·sha256·골든)를 통과한다.
- 평가기 설정(파이썬 거울 세계 → 스냅숏 지역 world 블록 꼴)이 스냅숏 world 블록과 같다(시드·난수 갈래·팀 은신처 생명주기·포만(N)·세계 허용 칸 표기 빼고).
- 같은 시작 상태에서 C++ 세계가 파이썬 세계(world.py 그대로)와 비트 단위로 같다 — 궤적 모든 칸·기록 칸 전체. 10-22 world.py 가 동족 무리 중심·분리를
  C++ PerceiveKin 과 같은 j 차례 합으로 더한다(`_seq_sum`). 그 전에는 행렬곱이라 시작 지각의 그 두 칸만 끝 비트가 달랐고, 이 시험은 그 두 칸만 바꾼
  진단 기하(옛 ceval.seq_kin_geometry)로 같음을 보았다 — 진단은 world.py 와 같아져 지웠다.
- Pool.run 기록 칸 = 파이썬 판정 기록 칸 (+ native), 'multi' 는 판정 길이마다 at.
평가기 실행 파일이 없으면 건너뛴다 (빌드: AdaptiveEcosystem/Tools/EcoV3Eval/build.ps1).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import json
import subprocess
import sys

import numpy as np
import pytest

from env.config import ROOT

LIVE_DIR = ROOT / "results" / "v3" / "live"
SNAP = LIVE_DIR / "pilot" / "eco_v3_snapshot_s20004_t475_e1.json"
ECOBRAINS = ROOT.parent / "AdaptiveEcosystem" / "EcoBrains"
BRAIN21 = ECOBRAINS / "v3_r1_g995_s3_obs21zero.json"
EXE = ROOT.parent / "AdaptiveEcosystem" / "Tools" / "EcoV3Eval" / "bin" / "EcoV3Eval.exe"

pytestmark = [pytest.mark.skipif(not EXE.exists(), reason="평가기 실행 파일이 없다 (Tools/EcoV3Eval/build.ps1)"),
              pytest.mark.skipif(not (ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip").exists(), reason="관측 21 모델 zip 이 없다 (저장소 밖 ckpt)")]


@pytest.fixture(scope="module")
def ce():
    if str(LIVE_DIR) not in sys.path:
        sys.path.insert(0, str(LIVE_DIR))
    import ceval

    return ceval


@pytest.fixture(scope="module")
def prepared(ce, tmp_path_factory):
    import live

    snap = live.read_snapshot(SNAP)
    info = live.prepare(SNAP, snap, tmp_path_factory.mktemp("prep"), live.brain_folders(live.DEFAULT_ROOT))
    return dict(info=info, snap=snap, zip=info["start"]["zip"])


def test_pcg64_matches_numpy(ce):
    g = np.random.default_rng(32099)
    g.random(5)
    st = g.bit_generator.state["state"]
    want = [int(x) for x in g.bit_generator.random_raw(100)]
    out = subprocess.run([str(EXE), "--pcg-selftest", str(st["state"]), str(st["inc"]), "100"], capture_output=True, text=True, check=True)
    assert [int(x) for x in out.stdout.split()] == want


def test_brain_files_pass(ce):
    for f in sorted(ECOBRAINS.glob("*.json")):
        out = subprocess.run([str(EXE), "--brain-check", str(f)], capture_output=True, text=True)
        assert out.returncode == 0, (f.name, out.stderr)
        d = json.loads(out.stdout)
        assert d["weights_sha256"] == json.loads(f.read_text(encoding="utf-8"))["weights_sha256"]


def test_world_block_matches_snapshot(ce, prepared):
    for world in ("N", "G"):
        for kind, tag, job in ce.eval_items(prepared["info"], "t", prepared["zip"], [34900], 1, world):
            wb = ce.world_block(ce.make_world(job))
            sw = next(r["world"] for r in prepared["snap"]["regions"] if r["region"] == job["region"])
            for k, v in sw.items():
                if k in ("seed", "rng_stream", "protected_refuges", "world_allowed"):
                    continue
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        if kk in ("schedule_rows", "kind", "intensity") or (k == "wild_satiation" and kk == "enabled"):
                            continue
                        assert wb[k][kk] == vv, (world, job["region"], k, kk)
                else:
                    assert wb[k] == v, (world, job["region"], k)
            assert wb["wild_satiation"]["enabled"] == (world == "G")
            # 세계 허용 칸: 표기는 다르지만(파이썬 = 실제 허용 목록, 스냅숏 = 세계 칸) 두뇌 허용 칸과 곱하면 같다
            model = json.loads(BRAIN21.read_text(encoding="utf-8"))["allowed_mask"]
            assert [a & b for a, b in zip(wb["world_allowed"], model)] == [a & b for a, b in zip(sw["world_allowed"], model)]
            wx = next(r["world"]["weather"] for r in prepared["snap"]["regions"] if r["region"] == job["region"])
            assert wb["weather"]["kind"] == wx["kind"]


def test_bit_identical_to_python_world(ce, prepared):
    """궤적 150 스텝: 첫 비트 차이가 없다. 시작 지각의 동족 무리 중심·분리도 0 차이다 (10-22 전에는 이 두 칸만 1e-15 쯤 달랐다 — 행렬곱 순서)."""
    kind, tag, job = ce.eval_items(prepared["info"], "t", prepared["zip"], [34901], 150, "N")[0]
    row = ce.run_native([ce.native_job(job, 0, trace=150)], BRAIN21, 1)[0]
    real = ce.trace_diff(ce.python_trace(job, prepared["zip"], 150), row)
    assert real["first_bit_difference"] is None, real["rows"][real["first_bit_difference"]]
    r0 = real["rows"][0]
    assert (r0["pos"], r0["head"], r0["energy"], r0["obs"], r0["wolf_pos"], r0["away_from_pred"], r0["food_grad"], r0["to_centroid"],
            r0["separation"]) == (0.0,) * 9


def test_records_equal_python_judge(ce, prepared, monkeypatch):
    """Step 안 도망 기록(EcoWorldV3.h FlightBeforeThreatStep·FlightStepEnd — 스텝 끝 은신처·표적·사냥, 실행한 FLEE·반사)과 기록 칸 전체가 파이썬 판정
    (r4_eval._one·live._world_multi — world.py 그대로)과 같다: N·G 세계 지역 셋 × 300 스텝, 'multi' 판정 길이마다 at 의 도망 기록까지.
    골든(Flight.Golden)은 파이썬이 적은 재료를 순수 함수에 넣어 보므로 Step 안에서 재료를 뜨는 자리는 이 대조만 본다."""
    import copy

    import adapt as ad
    import live

    items = (ce.eval_items(prepared["info"], "t", prepared["zip"], [34903], 300, "N")
             + ce.eval_items(prepared["info"], "t", prepared["zip"], [34903], 300, "G", "multi", [150, 300]))
    nat = ce.Pool(2, brain=BRAIN21).run(copy.deepcopy(items))
    import run_mirror as rm

    monkeypatch.setattr(rm, "apply_unreal_map", rm.apply_unreal_map)          # 판정 함수가 덮는 먹이 지도 훅을 시험 뒤 되돌린다
    tot = dict(started=0, own_n=0, caught=0, shelter_end=0, flee=0)
    for (kind, tag, job), (_, r) in zip(items, nat):
        py = ad._world_one(copy.deepcopy(job)) if kind == "world" else live._world_multi(copy.deepcopy(job))
        diff = [k for k in py if k not in ("wall_s", "native") and k in r and not ce._same(py[k], r[k])]
        assert not diff, (kind, job["region"], {k: (py[k], r[k]) for k in diff})
        assert r["flight"] == {k: py["flight"][k] for k in r["flight"]}, (kind, job["region"])     # 네이티브 도망 칸은 모두 파이썬과 같다
        if kind == "multi":
            for h in ("150", "300"):
                assert r["at"][h]["flight"] == {k: py["at"][h]["flight"][k] for k in r["at"][h]["flight"]}, (job["region"], h)
        f = r["flight"]
        tot["started"] += f["started"]
        tot["own_n"] += f["own_n"]
        tot["caught"] += f["n"]["caught"]
        tot["shelter_end"] += f["shelter_end"]
        tot["flee"] += f["flee_steps"]
    # 대조가 빈 기록이 아니다: 도망·스스로 벗어남·잡힘·은신처 끝이 모두 있다
    assert min(tot.values()) > 0, tot


def test_world_block_refuses_unported_settings(ce, prepared):
    """평가기가 옮기지 않는 칸이 바탕과 다르면 거부한다 (허용 목록): 도망길 측정(route_fixed — 'run' 도 도망길 기록을 낼 수 없다·quiet_end),
    늑대·밤 계수, v1 상수. 옮기는 칸(포만 끔 N·wild_flight 계수·숲 시야 obstacles.foliage — 10-22 C++ 에 옮김)과 끔 값을 적은 선택 키는 받는다."""
    import adapt as ad

    def job_of(sets):
        return ad.make_jobs(prepared["info"], prepared["zip"], [34900], 1, True, dict(name="t", sets=sets))[0]

    def block(sets):
        return ce.world_block(ce.make_world(job_of(sets)))

    for sets in ({"wild_satiation.enabled": False}, {"wild_flight.alert_r": 16.0}, {"wild_flight.route_fixed": None, "wild_flight.quiet_end": 0},
                 {"obstacles.foliage": {"enabled": False, "r": 1.5}}):
        assert block(sets)["obstacle_rules"]["foliage"] is False
    # 숲 시야: world 블록 obstacle_rules 의 foliage·foliage_r·foliage_block, 일의 foliage_trees (원판마다 0/1 — 스냅숏 원판은 fixed 라 모두 나무)
    on = block({"obstacles.foliage": {"enabled": True, "r": 2.5, "block": 1.5}})["obstacle_rules"]
    assert (on["foliage"], on["foliage_r"], on["foliage_block"]) == (True, 2.5, 1.5)
    nj = ce.native_job(job_of({"obstacles.foliage": {"enabled": True}}), 0)
    assert len(nj["foliage_trees"]) == len(nj["discs"]) > 0 and set(nj["foliage_trees"]) == {1}
    assert ce.native_job(job_of({}), 0)["foliage_trees"] == []
    for sets in ({"wild_flight.route_fixed": "open"}, {"wild_flight.route_fixed": "run"}, {"wild_flight.quiet_end": 15},
                 {"threats.stalk_dist": 7.0}, {"realism_night.settle_r": 9.0}, {"pred_sleep.sleep_dark": 0.4}, {"obstacle_obs.escape_norm": 12.0}):
        with pytest.raises(ValueError):
            block(sets)
    job = ad.make_jobs(prepared["info"], prepared["zip"], [34900], 1, True)[0]
    job["cfg"]["pred_view_r"] = float(job["cfg"]["pred_view_r"]) + 1.0
    with pytest.raises(ValueError, match="pred_view_r"):
        ce.world_block(ce.make_world(job))


def test_live_evaluator_hook(ce):
    """live.py 판정 실행기 갈림이 이 파일을 'ceval' 로 불러 쓴다: run_items·version (판정 저장 열쇠 — 실행 파일·C++ 소스·파이썬 셈 길 지문)."""
    import live

    ev = live.evaluator("ceval")
    assert callable(ev["run"]) and callable(ev["version"])
    tag = live.eval_code_tag("ceval")
    assert isinstance(tag, str) and len(tag) == 24 and tag != live.eval_code_tag("python")
    names = {p.name for p in ce.native_sources()}
    assert {"EcoV3Eval.cpp", "EcoWorldV3.h", "EcoThreatModel.h", "EcoObservationV3.h", "EcoRepertoire.h", "EcoPolicyV3Inference.h",
            "EcoRefugeSafetyV3.h", "EcoSha256.h", "PolicyWeightsV3.h", "MiniJson.h", "Pcg64.h"} <= names


def test_pool_record_schema(ce, prepared, monkeypatch):
    items = (ce.eval_items(prepared["info"], "t", prepared["zip"], [34902], 40, "N", "world")
             + ce.eval_items(prepared["info"], "t", prepared["zip"], [34902], 40, "G", "multi", [20, 40]))
    out = ce.Pool(2, brain=BRAIN21).run(items)
    assert [t for t, _ in out] == [t for _, t, _ in items]
    for (kind, tag, job), (_, r) in zip(items, out):
        want = set(ce.WORLD_KEYS if kind == "world" else ce.MULTI_KEYS) | {"flight", "native"} | ({"at"} if kind == "multi" else set())
        assert set(r) == want
        assert r["region"] == job["region"] and r["n"] == r["caught"] + r["starved"] + r["alive"]
        assert r["flight"]["started"] == sum(r["flight"]["n"].values())
        assert r["native"]["mask_violations"] == 0 and r["native"]["obs_layout_mismatch"] == 0
        if kind == "multi":
            assert set(r["at"]) == {"20", "40"} and r["at"]["40"]["caught"] == r["caught"]
    # 파이썬 판정 기록과 같은 칸 (r4_eval._one 하나만 돌려 견준다 — 40 스텝)
    import adapt as ad
    import run_mirror as rm

    monkeypatch.setattr(rm, "apply_unreal_map", rm.apply_unreal_map)          # _world_one 이 덮는 먹이 지도 훅을 시험 뒤 되돌린다 (뒤 시험 test_adapt_v3 의 지도 재현)
    kind, tag, job = items[0]
    py = ad._world_one(dict(job))
    assert set(py) | {"native"} == set(out[0][1])
    assert py["hunt"].keys() == out[0][1]["hunt"].keys() and py["weather"].keys() == out[0][1]["weather"].keys()
    # 도망 기록: 10-21 정의 칸은 모두 같다. 파이썬에 뒤에 더한 칸(도망길 등 — C++ 에 아직 없는 기능)은 네이티브에 없을 수 있다 (compare 가 python_only 로 적는다)
    core = {"started", "live_steps", "flee_steps", "reflex_steps", "n", "steps", "contact", "own_n", "own_steps", "own_contact", "shelter_end", "hist",
            "hist_edges"}
    assert set(out[0][1]["flight"]) == core and core <= set(py["flight"])
