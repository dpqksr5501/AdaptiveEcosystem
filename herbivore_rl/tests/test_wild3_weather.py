"""야생 3단계 지역 날씨 — 기능 wild_weather(31), 설정 configs/v3_wild3_mirror.yaml (10-18 사용자 '일단 우리 테스트 레벨에도 날씨 적용되게 해 줘. 그리고 그 날씨와
장애물들을 바탕으로 만들어진 세계를 파이썬에 고대로 옮겨서 학습시킬 거야', 명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md 11절, 정의는 env_v2/world.py 모듈 docstring '야생 3단계').

비트 동일: 날씨를 끈 세계는 직전 커밋(65cadc2)의 코드와 궤적·통계·v1 난수 상태·기능 스트림이 같다(나무 거울·야생 1단계·R3 설정, R1b 롤아웃 포함). 맑은 지역(메마른 땅)의
날씨 세계 = 나무 거울 세계(같은 프로세스·직전 코드 모두). 날씨를 끈 새 설정 = 나무 거울.
규칙 시험: 배수 식(세기 0·0.5·1, 맑음), 시간표, 계수 검사, 탐지 반경·관측 visibility(obs_visibility 켬·끔), 빗소리(사슴 등 뒤 달리는 늑대가 맑으면 들리고 비면 안 들림),
늑대 시야(아주 작은 시야 배수면 사냥이 거의 없음), 눈 이동(사슴·늑대 첫 스텝 이동 = 맑음 × 배수), 짝 비교 실행기의 지역 날씨, 설정 생성기 최신.
시드는 탐색 32084~32089 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import json
import shutil
import subprocess
import sys

import numpy as np
import pytest
import yaml

from env.config import ROOT
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.features import features_of
from env_v2.world import WX_CLEAR, WX_RAIN, WX_SNOW, World, _wild_weather_params, weather_at, weather_mults

CFG = ROOT / "configs"
TREES = CFG / "v3_wild2_trees_mirror.yaml"
WILD3 = CFG / "v3_wild3_mirror.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "65cadc2"              # 야생 3단계 직전 커밋(팀 날씨 눈으로 확인) — 비트 동일 기준
NOON = 225                           # integrated_stage.day_offset 225 → t = 0 이 한낮(d = 0, 늑대가 깨어 있다)

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _wild3(n=32, **wx):
    return _with(load_v2_config(WILD3).replace(N=n), wild_weather=wx)


def _graze(w):
    return np.full((w.N, 1), float(rep.GRAZE))


def _same_run(w1, w2, steps, pol1=None, pol2=None):
    for _ in range(steps):
        a1 = _graze(w1) if pol1 is None else np.asarray(pol1(w1.observe()), dtype=np.float64)
        a2 = _graze(w2) if pol2 is None else np.asarray(pol2(w2.observe()), dtype=np.float64)
        np.testing.assert_array_equal(a1, a2)
        for x, y in zip(w1.step(a1), w2.step(a2)):
            np.testing.assert_array_equal(x, y)
    for k in ("pos", "energy", "food", "food_cap", "pred_pos", "pred_head", "pred_cd", "alive"):
        np.testing.assert_array_equal(getattr(w1, k), getattr(w2, k))
    assert json.dumps(w1.hunt_stats()) == json.dumps(w2.hunt_stats()) and json.dumps(w1.pack_stats()) == json.dumps(w2.pack_stats())


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


def test_wild3_config_is_trees_plus_weather():
    """v3_wild3_mirror.yaml = v3_wild2_trees_mirror.yaml + wild_weather(version 만 다르다). 숲 비·고지 눈·메마른 땅 맑음, 생성기가 최신."""
    a = yaml.safe_load(TREES.read_text(encoding="utf-8"))
    b = yaml.safe_load(WILD3.read_text(encoding="utf-8"))
    assert a["version"] == "3.wild2trees" and b["version"] == "3.wild3"
    fa, fb = a.pop("features"), b.pop("features")
    a.pop("version"), b.pop("version")
    assert a == b
    assert set(fb) - set(fa) == {"wild_weather"} and all(fa[k] == fb[k] for k in fa)
    wx = fb["wild_weather"]
    assert wx["regions"] == {"Barren": ["clear", 0.0], "Forest": ["rain", 1.0], "Highland": ["snow", 1.0]} and wx["region"] == "Forest"
    assert (wx["rain_sight"], wx["rain_hear"], wx["snow_sight"], wx["snow_hear"]) == (0.9, 0.5, 0.7, 1.0)
    r3 = yaml.safe_load((CFG / "v3_r3.yaml").read_text(encoding="utf-8"))["features"]["realism_terrain"]
    assert (wx["snow_deer_speed"], wx["snow_wolf_speed"]) == (r3["mult_herb"][1], r3["mult_pred"][1])     # R3 지형 눈 값 그대로
    assert wx["obs_visibility"] is True and wx["schedule"] is None
    gen = _module("_make_wild3_config", ROOT / "results" / "v3" / "wild3" / "make_wild3_config.py")
    assert gen.render() == WILD3.read_text(encoding="utf-8")


def test_weather_params_checked():
    base = load_v2_config(WILD3).replace(N=8)
    bad = [dict(region="Desert"), dict(regions={"Forest": ["fog", 1.0]}), dict(regions={"Forest": ["rain", 1.5]}),
           dict(regions={"Forest": ["clear", 0.5]}), dict(regions=[["Forest", "rain", 1.0]]), dict(rain_sight=0.0), dict(snow_deer_speed=1.2),
           dict(obs_visibility=1), dict(schedule={"Forest": [[10, "rain", 1.0], [5, "clear", 0.0]]}),
           dict(schedule={"Forest": [[-1, "rain", 1.0]]}), dict(schedule={"Desert": [[0, "rain", 1.0]]}),
           dict(schedule={"Barren": [[0, "storm", 1.0]]}), dict(schedule={"Forest": []})]
    for kw in bad:
        with pytest.raises(ValueError, match="wild_weather"):
            World(_with(base, wild_weather=kw), seeds=[32084])
    # 선행 기능: repertoire·daynight. 청각 배수 < 1 이면 realism_hearing
    f = features_of(_with(base, realism_hearing=dict(enabled=False)))
    with pytest.raises(ValueError, match="realism_hearing"):
        _wild_weather_params(f.params("wild_weather"), f)
    _wild_weather_params(dict(f.params("wild_weather"), rain_hear=1.0), f)       # 청각 배수 1 이면 청각 없는 세계에도 된다
    f = features_of(_with(base, repertoire=dict(enabled=False)))
    with pytest.raises(ValueError, match="repertoire"):
        _wild_weather_params(f.params("wild_weather"), f)


def test_weather_mults_and_schedule():
    """배수 m(I) = 1 − (1 − m₁)·I. 맑음·세기 0 은 정확히 1.0. 시간표는 시작 스텝 ≤ t 인 마지막 줄, 첫 줄 앞·표 없는 지역은 고정 날씨."""
    f = features_of(load_v2_config(WILD3))
    wx = _wild_weather_params(f.params("wild_weather"), f)
    assert weather_mults(wx, WX_CLEAR, 0.0) == (1.0, 1.0, 1.0, 1.0)
    assert weather_mults(wx, WX_RAIN, 0.0) == (1.0, 1.0, 1.0, 1.0) and weather_mults(wx, WX_SNOW, 0.0) == (1.0, 1.0, 1.0, 1.0)
    assert weather_mults(wx, WX_RAIN, 1.0) == pytest.approx((0.9, 0.5, 1.0, 1.0), abs=1e-15)
    assert weather_mults(wx, WX_SNOW, 1.0) == pytest.approx((0.7, 1.0, 0.6, 0.85), abs=1e-15)
    assert weather_mults(wx, WX_SNOW, 0.5) == pytest.approx((0.85, 1.0, 0.8, 0.925), abs=1e-15)
    assert weather_mults(wx, WX_RAIN, 0.5)[2:] == (1.0, 1.0)                 # 비는 이동을 바꾸지 않는다
    assert weather_at(wx, 0) == (WX_RAIN, 1.0) and weather_at(wx, 10 ** 6) == (WX_RAIN, 1.0)
    p = dict(f.params("wild_weather"), schedule={"Forest": [[100, "clear", 0.0], [300, "rain", 0.5]], "Highland": [[0, "clear", 0.0]]})
    ws = _wild_weather_params(p, f)
    assert [weather_at(ws, t) for t in (0, 99, 100, 299, 300, 5000)] == [(WX_RAIN, 1.0)] * 2 + [(WX_CLEAR, 0.0)] * 2 + [(WX_RAIN, 0.5)] * 2
    hs = _wild_weather_params(dict(p, region="Highland"), f)
    assert weather_at(hs, 0) == (WX_CLEAR, 0.0)
    bs = _wild_weather_params(dict(p, region="Barren"), f)
    assert bs["schedule"] is None and weather_at(bs, 200) == (WX_CLEAR, 0.0)


def test_schedule_runs_in_world():
    """시간표 세계: 스텝마다 그때 날씨를 쓴다(날씨별 스텝 수, 지금 배수·탐지 반경)."""
    w = World(_wild3(16, schedule={"Forest": [[0, "clear", 0.0], [50, "rain", 1.0], [120, "snow", 0.5]]}), seeds=[32084])
    for _ in range(200):
        w.step(_graze(w))
    st = w.weather_stats()
    assert (st["steps_clear"], st["steps_rain"], st["steps_snow"]) == (50, 70, 80) and st["kind"] == "snow" and st["schedule"]
    assert st["sight"] == pytest.approx(0.85) and st["deer_speed"] == pytest.approx(0.8)
    assert w._see_pred == pytest.approx(w.cfg.see_r * (1.0 - 0.5 * w.dark) * 0.85)


# --------------------------------------------------------------------- #
# 비트 동일
# --------------------------------------------------------------------- #


def test_weather_off_and_clear_equal_trees():
    """날씨를 끈 새 설정 = 나무 거울, 맑은 지역(메마른 땅)·모든 배수 1 인 비 = 나무 거울(궤적·통계·사냥 셈). R1b 두뇌가 있으면 그 롤아웃으로도."""
    from env_v2 import rollout as ro

    base = load_v2_config(TREES).replace(N=32)
    cases = [_with(load_v2_config(WILD3).replace(N=32), wild_weather=dict(enabled=False)), _wild3(32, region="Barren"),
             _wild3(32, rain_sight=1.0, rain_hear=1.0)]
    for c in cases:
        w1, w2 = World(base, seeds=[32085]), World(c, seeds=[32085])
        _same_run(w1, w2, 300)
    if R1_MODEL.exists():
        w1, w2 = World(base.replace(N=64), seeds=[32086]), World(_wild3(64, region="Barren"), seeds=[32086])
        p1 = ro.build_policy({"kind": "rep_learned", "path": str(R1_MODEL)}, 32086)
        p2 = ro.build_policy({"kind": "rep_learned", "path": str(R1_MODEL)}, 32086)
        ro.forward_bind(p1, w1)
        ro.forward_bind(p2, w2)
        _same_run(w1, w2, 300, p1, p2)
    w = World(_with(load_v2_config(WILD3).replace(N=8), wild_weather=dict(enabled=False)), seeds=[32085])
    with pytest.raises(ValueError, match="weather_stats"):
        w.weather_stats()


def test_weather_bit_identical_to_head(tmp_path):
    """직전 코드(65cadc2)와: 나무 거울·야생 1단계·R3 설정의 궤적·통계·난수·관측 이름·기능 스트림이 같다(R1b 롤아웃 포함). 새 코드의 날씨 설정에서 맑은 지역
    (메마른 땅)은 직전 코드의 나무 거울과 같다."""
    tum = _module("_tum_for_weather", ROOT / "tests" / "test_unreal_mirror.py")
    old_root = tum._archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(tum.TRACE_SRC % dict(keys=tum.KEYS, stats=tum.STATS), encoding="utf-8")
    old = [dict(config="configs/v3_r3_on.yaml", seed=32087, steps=250, policy="rand"),
           dict(config="configs/v3_wild1_mirror.yaml", seed=32088, steps=300, policy="rand"),
           dict(config=str(TREES), seed=32089, steps=400, policy="rand")]
    if R1_MODEL.exists():
        old.append(dict(config=str(TREES), seed=32084, steps=400, policy="model", model=str(R1_MODEL)))
    new = [dict(j) for j in old]
    # 맑은 지역의 날씨 세계(새 코드만 안다) = 직전 코드의 나무 거울
    old.append(dict(config=str(TREES), seed=32085, steps=400, policy="rand"))
    new.append(dict(config=str(WILD3), seed=32085, steps=400, policy="rand", set={"wild_weather": {"region": "Barren"}}))
    if R1_MODEL.exists():
        old.append(dict(config=str(TREES), seed=32086, steps=400, policy="model", model=str(R1_MODEL)))
        new.append(dict(config=str(WILD3), seed=32086, steps=400, policy="model", model=str(R1_MODEL), set={"wild_weather": {"region": "Barren"}}))
    procs = []
    for root, js, tag in ((old_root, old, "old"), (ROOT, new, "new")):
        jp, op = tmp_path / f"jobs_{tag}.json", tmp_path / f"out_{tag}.json"
        jp.write_text(json.dumps(js), encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, str(script), str(jp), str(op)], cwd=root), op))
    outs = []
    for p, op in procs:
        assert p.wait(timeout=900) == 0
        outs.append(json.loads(op.read_text(encoding="utf-8")))
    for j, a, b in zip(new, *outs):
        first = next((i for i, (x, y) in enumerate(zip(a["hashes"], b["hashes"])) if x != y), None)
        assert first is None and len(a["hashes"]) == len(b["hashes"]), (j, first)
        for k in ("stats", "rng", "obs_names", "streams"):
            assert a[k] == b[k], (j, k)


# --------------------------------------------------------------------- #
# 규칙
# --------------------------------------------------------------------- #


def test_detect_radius_and_visibility_observation():
    """사슴 탐지 반경 = see_r × ((1 − 0.5·d) × w_s). 관측 visibility 는 obs_visibility 면 (1 − 0.5·d) × w_s, 끄면 1 − 0.5·d. 늑대 시야 반경 = 14 × w_s."""
    vi = World(load_v2_config(TREES).replace(N=16), seeds=[32084]).obs_names.index("visibility")
    for region, ws in (("Barren", 1.0), ("Forest", 0.9), ("Highland", 0.7)):
        for obs_vis in (True, False):
            w = World(_wild3(16, region=region, obs_visibility=obs_vis), seeds=[32084])
            for _ in range(500):                  # 낮(0)·박명·밤을 지난다(하루 900 스텝, t = 0 은 새벽 전환)
                d = w.dark
                raw = 1.0 - 0.5 * d
                assert w._see_pred == w.cfg.see_r * (raw * ws)
                assert w._wx_view == w.cfg.pred_view_r * ws
                o = w.observe()
                assert np.all(o[:, vi] == np.float32(raw * ws if obs_vis else raw))
                w.step(_graze(w))


def _hear_scene(region, dist):
    """사슴 0 의 바로 뒤(사각) dist 단위에 달리는 늑대 0 하나를 둔 한낮 세계의 기하. 다른 늑대·사슴은 멀리, 원판·은신처 없음."""
    w = World(_with(_wild3(4, region=region), integrated_stage=dict(day_offset=NOON), obstacles=dict(fixed=[])), seeds=[32087])
    assert w.dark == 0.0 and not w.pred_asleep.any()
    w.pos[:] = [[30.0, 30.0], [2.0, 58.0], [3.0, 58.0], [4.0, 58.0]]
    w.head[:] = [[1.0, 0.0]] * 4
    w.pred_pos[:] = [[30.0 - dist, 30.0], [58.0, 2.0], [58.0, 3.0], [58.0, 4.0]]
    w.pred_vel[:] = [[0.6, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]     # 늑대 0 은 지난 스텝 사슴 걸음(× 1.0)으로 달렸다
    w.pred_running[:] = [True, False, False, False]
    w.cov_c, w.cov_r = np.zeros((0, 2)), np.zeros(0)
    return w._geometry()


def test_rain_masks_footsteps():
    """사슴 등 뒤(시야 300° 의 사각) 15 단위에서 달리는 늑대: 맑으면 들리고(발소리 반경 20), 비면 안 들린다(20 × 0.5 = 10). 9 단위면 비에도 들린다.
    눈은 청각 배수 1 이라 맑음과 같다."""
    seen = {r: _hear_scene(r, 15.0)["pred_count"][0] for r in ("Barren", "Forest", "Highland")}
    assert seen == {"Barren": 1, "Forest": 0, "Highland": 1}
    assert _hear_scene("Forest", 9.0)["pred_count"][0] == 1


def test_snow_slows_deer_and_wolves():
    """눈 배수만 둔 고지(시야·청각 1): 첫 스텝의 사슴 적용 속도 = 맑음 × 0.6(비트 단위), 늑대 이동 = 맑음 × 0.85(막힘 없는 늑대). 한낮 시작."""
    common = dict(integrated_stage=dict(day_offset=NOON), obstacles=dict(fixed=[]))
    clear = World(_with(_wild3(32, region="Barren"), **common), seeds=[32088])
    snow = World(_with(_wild3(32, region="Highland", snow_sight=1.0), **common), seeds=[32088])
    np.testing.assert_array_equal(clear.observe(), snow.observe())
    p0 = clear.pred_pos.copy()
    clear.step(_graze(clear))
    snow.step(_graze(snow))
    np.testing.assert_array_equal(snow.vel, clear.vel * 0.6)
    assert np.abs(clear.vel).max() > 0.0
    dc, ds = clear.pred_pos - p0, snow.pred_pos - p0
    moved = np.sqrt((dc * dc).sum(1)) > 1e-9
    assert moved.any()
    np.testing.assert_allclose(ds[moved], dc[moved] * 0.85, rtol=1e-9, atol=1e-12)


def _wolf_scene(region, dist, **wx):
    """한낮, 추격형 늑대 1 이 앞(+x)을 보고 dist 단위 앞에 사슴 0. 다른 늑대는 벽을 보고, 다른 사슴은 반대쪽 구석. 원판·은신처 없음. 한 스텝 뒤 늑대 1 이 쫓나."""
    w = World(_with(_wild3(4, region=region, **wx), integrated_stage=dict(day_offset=NOON), obstacles=dict(fixed=[])), seeds=[32088])
    assert w.dark == 0.0 and not w.pred_asleep.any() and w.pred_type[1] == 0      # 슬롯 1 = 근접 추격형(통합 무대 alternate)
    w.pos[:] = [[30.0 + dist, 30.0], [2.0, 58.0], [3.0, 58.0], [4.0, 58.0]]
    w.pred_pos[:] = [[58.0, 2.0], [30.0, 30.0], [58.0, 4.0], [58.0, 6.0]]
    w.pred_head[:] = [[0.0, -1.0], [1.0, 0.0], [0.0, -1.0], [0.0, -1.0]]
    w.cov_c, w.cov_r = np.zeros((0, 2)), np.zeros(0)
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)
    w.step(_graze(w))
    return bool(w.pred_running[1])


def test_weather_shortens_wolf_sight():
    """늑대 시야 = 14 × w_s: 앞 13.3 단위의 사슴을 맑으면 보고 쫓고, 비(14 × 0.9 = 12.6)·눈(9.8)이면 못 본다. 10 단위면 비에도 쫓는다.
    비 시야 배수 1(청각만 0.5)이면 맑음처럼 쫓는다."""
    assert _wolf_scene("Barren", 13.3) and not _wolf_scene("Forest", 13.3) and not _wolf_scene("Highland", 13.3, snow_deer_speed=1.0)
    assert _wolf_scene("Forest", 10.0) and _wolf_scene("Forest", 13.3, rain_sight=1.0)


def test_runner_sets_region_weather(tmp_path):
    """짝 비교 실행기: 지도 (세션, 지역) 마다 그 지역 날씨와 나무 원판을 쓴다. 메타 weather·heard_only_frac."""
    rm = _module("_run_mirror_for_weather", ROOT / "results" / "v3" / "mirror" / "run_mirror.py")
    res = rm.run(16, 38, [32084, 32085, 32086], steps=30, workers=0, config=WILD3, unreal_maps=[20000], replicates=1,
                 unreal_obstacles=ROOT / "results" / "v3" / "wild2" / "trees" / "tree_layout.json")
    got = {wd["meta"]["unreal_map"]["region"]: (wd["meta"]["weather"]["kind"], wd["meta"]["obstacles"]["n"], wd["meta"]["weather"]["steps_" +
           wd["meta"]["weather"]["kind"]]) for wd in res["worlds"]}
    assert got == {"Barren": ("clear", 0, 30), "Forest": ("rain", 24, 30), "Highland": ("snow", 9, 30)}
    assert all(0.0 <= wd["meta"]["heard_only_frac"] <= 1.0 for wd in res["worlds"])


# --------------------------------------------------------------------- #
# C++ 골든 (export_golden_v3_weather.py → AI/Policy/WeatherGoldenVectorsV3.h, 검사 본문 Tests/WeatherGoldenCheckV3.h)
# --------------------------------------------------------------------- #

UE_POLICY = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
WEATHER_CPP_MAIN = ROOT / "tests" / "cpp" / "weather_v3_main.cpp"


def test_weather_golden_header_is_fresh():
    """언리얼 모듈의 WeatherGoldenVectorsV3.h 는 지금 코드로 다시 만든 헤더와 바이트 단위로 같다."""
    path = UE_POLICY / "WeatherGoldenVectorsV3.h"
    if not path.exists():
        pytest.skip("언리얼 모듈 날씨 골든 헤더 없음")
    ex = _module("_export_golden_v3_weather", ROOT / "export_golden_v3_weather.py")
    assert path.read_bytes() == ex.build_header().encode("utf-8")


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음")
def test_cpp_weather_matches_golden_with_gpp(tmp_path):
    """언리얼 모듈의 EcoWorldV3.h·EcoThreatModel.h·날씨 골든 헤더를 그대로 g++ 로 컴파일해 대조한다(UE 시험 Policy.V3.Weather.Golden 과 같은 검사 본문)."""
    if not (UE_POLICY / "WeatherGoldenVectorsV3.h").exists():
        pytest.skip("언리얼 모듈 날씨 골든 헤더 없음")
    exe = tmp_path / ("weather_v3.exe" if sys.platform == "win32" else "weather_v3")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-Wno-unused-parameter", "-I", str(UE_POLICY),
                            str(WEATHER_CPP_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and "PASS" in run.stdout, f"파리티 실패:\n{run.stdout}\n{run.stderr}"
