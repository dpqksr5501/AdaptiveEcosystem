"""V2 2-4 — v2.4 낮밤(daynight): 위상·어둠·밤 탐지·섭식·휴식 배수, 관측 visibility·to_transition (계획서 4.9.2·4.2·4.7,
2단계 2-4 행, 10절 #21·#25·#27).

설정(v2_4 = v2_1 + daynight + reset 5000, v2_4_on 은 낮 고정 비율만 0), 계수 검사, 자기 스트림에서만 정해진 수를 뽑음,
위상식(전환 순간 0.5, 박명 폭 0.1·T, 남은 스텝), 관측 visibility 로 나눈 구간 = d 로 나눈 구간(float32 문턱), 탐지 배수가
포식자 탐지에만 걸리고 동족 시야는 그대로, 섭식·휴식 배수, daynight 끈 설정 = v2.1 비트 동일(기록된 결과 행 재현 포함),
낮 고정 세계 = v2.1 동역학, 결정성·복제, 위상 지표(daynight_stats)의 정의, 시작 상태 유도(start_induce), 관측 9·행동 5 가
VecEnv·rollout·학습(train_v2)을 통과한다(짧은 smoke).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import json
import math
import pickle

import numpy as np
import pytest
import yaml

from env.config import ROOT
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.features import feature_stream
from env_v2.vec_env import MultiWorldVecEnv
from env_v2.world import (DAYNIGHT_STAT_COLUMNS, DN_EDGES, GAIT_RUN, GAIT_STOP, GAIT_WALK, World, daynight_draws,
                          daynight_phase, daynight_seg_edges, obs_names)

V2_1 = ROOT / "configs" / "v2_1.yaml"
V2_4 = ROOT / "configs" / "v2_4.yaml"
V2_4_ON = ROOT / "configs" / "v2_4_on.yaml"
OBS9 = ("food_density", "pred_count", "pred_dist", "kin_count", "energy", "recent_predation", "cover_dist",
        "visibility", "to_transition")
C2 = [0.97099, 0.78494, 0.21823, 0.03359, 0.49137]     # E1-b C2 (results/v2/e1/judge_e1b.json)
C_REST = 15.0 / 21.0

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def cfg4():
    return load_v2_config(V2_4_ON)


def _dn(cfg, **kw):
    """daynight 블록 일부만 바꾼 설정."""
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    f["daynight"] = dict(f["daynight"], **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _same(d1, d2):
    assert d1.keys() == d2.keys()
    for k in d1:
        a, b = d1[k], d2[k]
        assert a == b or (isinstance(a, float) and math.isnan(a) and math.isnan(b)), k


def _rule5(obs):
    a = np.tile([0.4, 0.8, 0.4, 0.1, 0.5], (len(obs), 1))
    a[obs[:, 4] < 0.5, 4] = 0.0
    a[obs[:, 2] < 0.5, 4] = 1.0
    return a


def _set_predators(w, pos, head=None):
    """포식자를 `pos` 로 바꾼다. 움직이지 않고 사냥하지 않는다. 기하·관측을 다시 잰다."""
    pos = np.asarray(pos, dtype=np.float64).reshape(-1, 2)
    M = len(pos)
    w.M = M
    w.pred_pos = pos.copy()
    w.pred_head = np.tile([1.0, 0.0], (M, 1)) if head is None else np.asarray(head, dtype=np.float64)
    w.pred_ranged = np.zeros(M, dtype=bool)
    w.pred_speed = np.zeros(M)
    w.pred_catch_r = np.ones(M)
    w.pred_cd = np.full(M, 10**9, dtype=np.int32)
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)
    return w


def _set_dark(w, d):
    """세계의 지금 어둠을 d 로 둔다(낮 고정 해제). 관측·기하는 부르는 쪽이 다시 잰다."""
    w.day_fixed = False
    w.dark = d
    w._vis = 1.0 - w._dn["detect_night"] * d
    w._see_pred = w.cfg.see_r * w._vis


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


def test_v2_4_config_is_v2_1_plus_daynight():
    """v2_4.yaml = v2_1.yaml 의 v1 덮기·speed 블록 그대로 + daynight + reset 5000. v2_4_on 은 fixed_day_frac 만 0."""
    r1 = yaml.safe_load(V2_1.read_text(encoding="utf-8"))
    r4 = yaml.safe_load(V2_4.read_text(encoding="utf-8"))
    ron = yaml.safe_load(V2_4_ON.read_text(encoding="utf-8"))
    assert r4["overrides"] == r1["overrides"]
    assert r4["features"]["speed"] == r1["features"]["speed"]
    assert set(r4["features"]) == {"speed", "daynight"}
    assert r4["version"] == "2.4"
    assert {k: v for k, v in r4["train"].items() if k != "reset_interval"} == \
        {k: v for k, v in r1["train"].items() if k != "reset_interval"}
    assert r1["train"]["reset_interval"] == 4000 and r4["train"]["reset_interval"] == 5000
    dn = r4["features"]["daynight"]
    # eat_night 은 10-06 환경 확인 N (a2) 실패로 0(#21 가지치기, results/v2/v2_4/gate_n)
    assert dn == dict(enabled=True, periods=[600, 900, 1800], twilight=0.05, detect_night=0.5, eat_night=0.0,
                      rest_night=0.35, fixed_day_frac=0.2, transition_norm=900, start_induce=0.0, rest_cover_only=False)
    on = dict(r4)
    on["features"] = dict(r4["features"], daynight=dict(dn, fixed_day_frac=0.0))
    assert ron == on
    for p in (V2_4, V2_4_ON):
        cfg = load_v2_config(p)
        assert obs_names(cfg) == OBS9
        w = World(cfg, seeds=[0])
        assert w.obs_dim == 9 and w.act_names == ("forage", "cohesion", "flee_dist", "cover", "speed")
        assert w.features.active == ("speed", "daynight")


@pytest.mark.parametrize("kw, match", [
    (dict(periods=[600, 901]), "짝수"),
    (dict(periods=[]), "목록"),
    (dict(periods=[600.0]), "짝수"),
    (dict(twilight=0.0), "twilight"),
    (dict(twilight=0.3), "twilight"),
    (dict(twilight=0.051), "정수 스텝"),
    (dict(detect_night=1.5), "detect_night"),
    (dict(eat_night=-0.1), "eat_night"),
    (dict(rest_night=True), "rest_night"),
    (dict(fixed_day_frac=2.0), "fixed_day_frac"),
    (dict(start_induce=-1.0), "start_induce"),
    (dict(transition_norm=800), "transition_norm"),
])
def test_daynight_params_are_checked(cfg4, kw, match):
    with pytest.raises(ValueError, match=match):
        World(_dn(cfg4, **kw), seeds=[0])


def test_daynight_requires_speed_and_all_coefficients(cfg4, tmp_path):
    f = {k: dict(v) for k, v in cfg4.v2["features"].items()}
    f["speed"]["enabled"] = False
    with pytest.raises(ValueError, match="speed"):
        World(cfg4.replace(v2=dict(cfg4.v2, features=f)), seeds=[0])
    raw = yaml.safe_load(V2_4.read_text(encoding="utf-8"))
    del raw["features"]["daynight"]["start_induce"]
    p = tmp_path / "v2_4_missing.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="start_induce"):
        load_v2_config(p)


# --------------------------------------------------------------------- #
# 위상식
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("T, tw", [(600, 30), (900, 45), (1800, 90)])
def test_phase_formula_closed_form(T, tw):
    """전환 순간 d = 0.5, 박명 폭 앞뒤 τ(= 0.05·T) 스텝, 한낮 0·한밤 1, r 은 1..T/2 로 줄었다가 전환에서 T/2 로 뛴다."""
    H = T // 2
    ds, rs = zip(*(daynight_phase(t, T, 0, tw) for t in range(2 * T)))
    ds, rs = np.array(ds), np.array(rs)
    assert ds[0] == 0.5 and ds[H] == 0.5 and ds[T] == 0.5             # 전환 순간 (s = 0 새벽, s = H 해 질 녘)
    assert ds[tw] == 0.0 and ds[H - tw] == 0.0 and ds[H + tw] == 1.0 and ds[T - tw] == 1.0
    assert np.all(ds[tw:H - tw + 1] == 0.0) and np.all(ds[H + tw:T - tw + 1] == 1.0)
    assert ds[H - 1] == 0.5 - 1 / (2 * tw) and ds[H + 1] == 0.5 + 1 / (2 * tw)
    twi = (ds > 0.0) & (ds < 1.0)
    assert int(twi[:T].sum()) == 4 * tw - 2                             # 전환마다 2τ − 1 스텝(양끝 0·1 제외)
    assert rs[0] == H and rs[H - 1] == 1 and rs[H] == H and np.all(np.diff(rs[:H]) == -1)
    for t in range(T):                                                  # 시작 위상 o 는 t 를 미는 것과 같다
        assert daynight_phase(t, T, 77, tw) == daynight_phase(t + 77, T, 0, tw)


@pytest.mark.parametrize("detect", [0.5, 0.75])
def test_visibility_buckets_match_dark_buckets_in_float32(detect):
    """판정 도구가 관측 visibility(float32)로 나눈 구간 = 세계 통계가 d 로 나눈 구간(낮 d ≤ 0.2, 밤 d ≥ 0.8)이
    모든 스텝에서 같다. d = 0.2·0.8 이 정확히 나오는 스텝(k = 0.6τ)을 포함한다."""
    edges = daynight_seg_edges(detect)
    for T, tw in ((600, 30), (900, 45), (1800, 90)):
        for t in range(T):
            d, _ = daynight_phase(t, T, 0, tw)
            want = 2 if d >= DN_EDGES[1] - 1e-9 else (0 if d <= DN_EDGES[0] + 1e-9 else 1)
            vis = np.float32(1.0 - detect * d)
            got = int(np.digitize(vis, edges))           # 0 밤, 1 박명, 2 낮
            assert {0: 2, 1: 1, 2: 0}[got] == want, (T, t, d)
    assert any(daynight_phase(t, 600, 0, 30)[0] == 0.8 for t in range(600))
    with pytest.raises(ValueError):
        daynight_seg_edges(0.0)


def test_reset_draws_exactly_three_from_own_stream(cfg4):
    """reset 은 daynight 스트림 part 0 에서 정확히 3개(낮 고정, T, o)를 뽑고 v1 스트림을 건드리지 않는다. 목록 길이와
    무관하게 소비가 같다. daynight_draws 가 세계 값과 같다."""
    for seed in (0, 7, 10000, 12345):
        w4, w1 = World(cfg4, seeds=[seed]), World(load_v2_config(V2_1), seeds=[seed])
        assert w4.rng.bit_generator.state == w1.rng.bit_generator.state
        g = feature_stream(seed, "daynight", 0)
        u = g.random(3)
        T = [600, 900, 1800][min(int(u[1] * 3), 2)]
        assert (w4.day_fixed, w4.dn_period, w4.dn_offset) == (False, T, min(int(u[2] * T), T - 1))
        dr = daynight_draws(w4._dn, seed, w4.N)
        assert (dr["period"], dr["offset"], dr["day_fixed"]) == (w4.dn_period, w4.dn_offset, w4.day_fixed)
        one = World(_dn(cfg4, periods=[600]), seeds=[seed])
        assert one.dn_period == 600 and one.dn_offset == min(int(u[2] * 600), 599)
        assert w4._feature_rngs == {}
    tr = load_v2_config(V2_4)
    fixed = [World(tr, seeds=[s]).day_fixed for s in range(400)]
    assert 0.12 < np.mean(fixed) < 0.28                                 # 낮 고정 20% (#27)
    periods = [World(tr, seeds=[s]).dn_period for s in range(300)]
    assert set(periods) == {600, 900, 1800}


# --------------------------------------------------------------------- #
# 밤 효과
# --------------------------------------------------------------------- #


def test_night_shrinks_predator_detection_only(cfg4):
    """밤(d = 1)에 탐지 반경 10: 반경 10~20 의 포식자는 안 보이고(관측 1 = 0, 관측 2 = 1), 같은 거리의 동족은 그대로
    보인다(관측 3). 관측 2 의 분모는 see_r 그대로다(10 안의 포식자는 d/see_r 로 나온다)."""
    w = World(cfg4, seeds=[10000])
    p0 = np.array([w.size / 2, w.size / 2])
    w.pos[:] = p0 + np.array([-40.0, -40.0])           # 나머지 개체는 멀리
    w.head[:] = [1.0, 0.0]
    w.pos[0] = p0
    w.pos[1] = p0 + [15.0, 0.0]                         # 동족, 거리 15
    for d, want_pc in ((0.0, 1), (1.0, 0)):
        _set_dark(w, d)
        _set_predators(w, [p0 + [15.0, 1.0]])
        o = w.observe()
        assert (o[0, 1] > 0) == bool(want_pc)
        assert o[0, 2] == (1.0 if not want_pc else np.float32(np.hypot(15, 1) / 20))
        assert o[0, 3] == np.float32(1 / w.cfg.obs_kin_count_norm)
        assert o[0, 7] == np.float32(1.0 - 0.5 * d)
    _set_dark(w, 1.0)
    _set_predators(w, [p0 + [8.0, 0.0]])
    o = w.observe()
    assert o[0, 1] > 0 and o[0, 2] == np.float32(8.0 / 20.0)


def test_night_eat_and_rest_multipliers(cfg4):
    """섭식 × (1 − 0.5·d) 는 모든 보행에, 휴식 대사 × (1 − 0.35·d) 는 정지 개체에만. d = 0 이면 v2.1 값 그대로.
    (판정 설정은 eat_night 0 이라 제안값 0.5 로 켜서 본다)"""
    w = World(_dn(cfg4, eat_night=0.5), seeds=[10000])
    w.gait = np.array([GAIT_STOP, GAIT_WALK, GAIT_RUN] * 42 + [GAIT_STOP, GAIT_STOP], dtype=np.int8)
    _set_dark(w, 0.0)
    drain0, eat0 = w._drain_eat()
    sp = w._sp
    np.testing.assert_array_equal(drain0, w.cfg.energy_drain * sp["drain_mult"][w.gait])
    np.testing.assert_array_equal(eat0, sp["eat"][w.gait])
    for d in (0.4, 1.0):
        _set_dark(w, d)
        drain, eat = w._drain_eat()
        np.testing.assert_array_equal(eat, eat0 * (1.0 - 0.5 * d))
        stop = w.gait == GAIT_STOP
        np.testing.assert_array_equal(drain[stop], drain0[stop] * (1.0 - 0.35 * d))
        np.testing.assert_array_equal(drain[~stop], drain0[~stop])
    assert drain[0] == pytest.approx(w.cfg.energy_drain * C_REST * 0.65)


# --------------------------------------------------------------------- #
# 끈 설정·낮 고정 = v2.1
# --------------------------------------------------------------------- #

SPECS = [{"kind": "fixed", "action": C2}, ro.adapt_spec({"kind": "random", "seed": 3}, 5)]


@pytest.mark.parametrize("seed", [0, 636, 10000])
@pytest.mark.parametrize("pol", ["fixed", "random", "rule"])
def test_daynight_off_matches_v2_1_bitwise(cfg4, seed, pol):
    """v2_4 에서 daynight 만 끈 설정 = v2_1 (관측·보상·위치·보행·통계 비트 동일). 기능 스트림 0개."""
    w4 = World(_dn(cfg4, enabled=False), seeds=[seed])
    w1 = World(load_v2_config(V2_1), seeds=[seed])
    assert w4.features.active == ("speed",) and w4.obs_dim == 7 and w4._dn is None
    p1, p2 = [ro.build_policy(SPECS[pol == "random"]) if pol != "rule" else _rule5 for _ in range(2)]
    for _ in range(300):
        o1, o2 = w1.observe(), w4.observe()
        np.testing.assert_array_equal(o1, o2)
        r1, r2 = w1.step(p1(o1)), w4.step(p2(o2))
        for x, y in zip(r1, r2):
            np.testing.assert_array_equal(x, y)
    assert w1.stats() == w4.stats()
    _same(w1.gait_stats(), w4.gait_stats())
    for k in ("pos", "head", "energy", "pred_pos", "food", "vel"):
        np.testing.assert_array_equal(getattr(w1, k), getattr(w4, k), err_msg=k)
    assert w4._feature_rngs == {}


def test_daynight_off_reproduces_recorded_v2_1_result(cfg4):
    """1-4 전 코드가 남긴 Gate E1-b 결과 행(results/v2/e1/B1/r2_5_ew0_5/constsearch_seg.json)을 daynight 를 끈 v2_4 설정이
    비트 단위로 다시 낸다."""
    d = json.loads((ROOT / "results/v2/e1/B1/r2_5_ew0_5/constsearch_seg.json").read_text(encoding="utf-8"))
    m = d["meta"]
    assert m["config_digest"] == "f068496361f9"
    spec = {"policy": {"kind": "fixed", "action": d["base_action"]},
            "wrap": [{"kind": "seg_const", "bins": d["bins"], "dims": d["dims"],
                      "table": [x for row in d["best_table"] for x in row]}]}
    want = d["per_seed"]["C2-seg"][0]
    r = ro.rollout(_dn(cfg4, enabled=False), ro.build_policy(spec, 10000), 10000, m["eval_steps"], gamma=m["gamma"],
                   tail=m["tail"])
    from diagnose_v2 import clean

    assert clean(ro.public_row(r)) == want


@pytest.mark.parametrize("kw", [dict(fixed_day_frac=1.0),
                                dict(detect_night=0.0, eat_night=0.0, rest_night=0.0)],
                         ids=["day_fixed", "zero_mult"])
@pytest.mark.parametrize("seed", [0, 10000])
def test_neutral_daynight_world_has_v2_1_dynamics(cfg4, kw, seed):
    """낮 고정 세계(계획서 2-4 '낮 고정 세계 = 앞 버전 세계'), 또는 밤 배수를 모두 0 으로 둔 세계는 v2.1 과 동역학이 비트
    단위로 같다. 관측 앞 7칸이 같고, 낮 고정이면 뒤 두 칸이 중립값 1·1 이다."""
    w4 = World(_dn(cfg4, **kw), seeds=[seed])
    w1 = World(load_v2_config(V2_1), seeds=[seed])
    for _ in range(300):
        o1, o4 = w1.observe(), w4.observe()
        np.testing.assert_array_equal(o1, o4[:, :7])
        if "fixed_day_frac" in kw:
            assert np.all(o4[:, 7:] == 1.0)
        else:
            assert np.all(o4[:, 7] == 1.0)
        a = _rule5(o1)
        r1, r4 = w1.step(a), w4.step(a)
        for x, y in zip(r1[1:3], r4[1:3]):
            np.testing.assert_array_equal(x, y)
    assert w1.stats() == w4.stats()
    _same(w1.gait_stats(), w4.gait_stats())


def test_daynight_world_is_deterministic_and_copyable(cfg4):
    spec = ro.adapt_spec({"kind": "random", "seed": 2}, 5)
    a, b = World(cfg4, seeds=[636]), World(cfg4, seeds=[636])
    pa, pb = ro.build_policy(spec), ro.build_policy(spec)
    for _ in range(200):
        ra, rb = a.step(pa(a.observe())), b.step(pb(b.observe()))
        for x, y in zip(ra, rb):
            np.testing.assert_array_equal(x, y)
    _same(a.daynight_stats(), b.daynight_stats())
    clones = [pickle.loads(pickle.dumps(a)), copy.deepcopy(a)]
    for _ in range(50):
        act = pa(a.observe())
        a.step(act)
        for c in clones:
            c.step(act)
    for c in clones:
        for k in ("pos", "energy", "dark", "_vis", "_to_tr"):
            np.testing.assert_array_equal(getattr(c, k), getattr(a, k), err_msg=k)
        _same(c.daynight_stats(), a.daynight_stats())
    assert a._feature_rngs == {}


def test_observation_follows_phase_each_step(cfg4):
    """관측 두 칸은 스텝 뒤 t 의 값(visibility = 1 − 0.5·d, to_transition = r/900)이고 리스폰 개체도 같은 값을 본다."""
    w = World(cfg4, seeds=[10000])
    T, o, tw = w.dn_period, w.dn_offset, w.dn_tw
    a = np.tile(C2, (w.N, 1))
    for _ in range(T + 5):
        d, r = daynight_phase(w.t, T, o, tw)
        obs = w.observe()
        assert np.all(obs[:, 7] == np.float32(1.0 - 0.5 * d))
        assert np.all(obs[:, 8] == np.float32(min(r / 900, 1.0)))
        assert w.dark == d
        w.step(a)


# --------------------------------------------------------------------- #
# 통계
# --------------------------------------------------------------------- #


def test_daynight_stats_definitions(cfg4):
    """구간 비율 합 1, n1·n5p 가 정의대로, 항상 정지·항상 걷기 상수에서 B1·B2·보행 비율이 구성상 0/1, 사망 수 합 =
    v1 통계의 사망 수, 섭취·대사 합 = gait_stats 의 합."""
    for speed, gait in ((0.0, GAIT_STOP), (0.5, GAIT_WALK)):
        w = World(cfg4, seeds=[10000])
        a = np.tile(C2[:4] + [speed], (w.N, 1))
        for _ in range(1200):
            w.step(a)
        s, gs = w.daynight_stats(), w.gait_stats()
        assert tuple(s) == DAYNIGHT_STAT_COLUMNS
        assert s["frac_day"] + s["frac_twi"] + s["frac_night"] == pytest.approx(1.0)
        assert s["n1"] == pytest.approx(s["p_rest_cover_night"] - s["p_rest_cover_day"])
        assert s["n5p"] == pytest.approx(s["p_eat_night_hungry"] - s["p_eat_night_full"])
        assert s["b1_day"] == 0.0 and s["b1_night"] == 0.0 and s["b2_day"] == 0.0 and s["b2_night"] == 0.0
        assert math.isnan(s["n2"])
        if gait == GAIT_STOP:
            assert s["p_stop_day"] == 1.0 and s["p_stop_night"] == 1.0
            assert s["n1"] == pytest.approx(s["p_cover_night"] - s["p_cover_day"])
        H = w._dn_hist
        assert int(H.sum()) == w._agent_steps
        assert int(w._dn_dead.sum()) == w._pred_deaths + w._starve_deaths
        assert w._dn_energy[0].sum() == pytest.approx(w._intake_sum)
        assert w._dn_energy[1].sum() == pytest.approx(w._drain_sum)
        assert s["dark_mean"] == pytest.approx(np.mean([daynight_phase(t, w.dn_period, w.dn_offset, w.dn_tw)[0]
                                                         for t in range(1200)]))


def test_rollout_rows_carry_daynight_columns_only_when_on(cfg4):
    pol = ro.build_policy({"kind": "fixed", "action": C2})
    r4 = ro.rollout(cfg4, pol, 10000, 200)
    r1 = ro.rollout(load_v2_config(V2_1), ro.build_policy({"kind": "fixed", "action": C2}), 10000, 200)
    assert set(ro.DAYNIGHT_COLUMNS) <= set(r4) and not set(ro.DAYNIGHT_COLUMNS) & set(r1)


# --------------------------------------------------------------------- #
# 시작 상태 유도 (탐침 대응용, 기본 0)
# --------------------------------------------------------------------- #


def test_start_induce(cfg4):
    """start_induce = 1: 낮 고정이 아닌 세계는 해 지기 ⌈0.1·T⌉ 스텝 전에 시작하고 에너지가 U[0.2, 0.5], 리스폰 개체도
    U[0.2, 0.5]. 자기 스트림 part 2·3 만 쓰고 v1 스트림은 그대로다. 0 이면 part 2·3 이 생기지 않는다."""
    cfg = _dn(cfg4, start_induce=1.0)
    w, w0 = World(cfg, seeds=[10000]), World(cfg4, seeds=[10000])
    assert w.dn_induced and not w0.dn_induced
    T = w.dn_period
    assert w.dn_offset == T // 2 - math.ceil(0.1 * T)
    assert np.all((w.energy >= 0.2) & (w.energy <= 0.5))
    assert w.rng.bit_generator.state == w0.rng.bit_generator.state
    _, r = daynight_phase(0, T, w.dn_offset, w.dn_tw)
    assert r == math.ceil(0.1 * T)
    w._respawn(np.array([3, 5]))
    assert 0.2 <= w.energy[3] <= 0.5 and 0.2 <= w.energy[5] <= 0.5
    assert {k for k, _ in w._feature_rngs} == {"daynight"} and {p for _, p in w._feature_rngs} == {3}
    w0._respawn(np.array([3]))
    assert w0.energy[3] == w0.cfg.init_energy and w0._feature_rngs == {}
    fixed = World(_dn(cfg4, start_induce=1.0, fixed_day_frac=1.0), seeds=[10000])
    assert not fixed.dn_induced and fixed.energy[0] == fixed.cfg.init_energy


# --------------------------------------------------------------------- #
# VecEnv·학습 smoke
# --------------------------------------------------------------------- #


def test_vec_env_obs_space_and_reset_interval():
    venv = MultiWorldVecEnv(load_v2_config(V2_4), seeds=range(100, 110), meta_seed=0)
    assert venv.observation_space.shape == (9,) and venv.action_space.shape == (5,)
    assert venv.T == 5000
    venv.close()


TINY = {"version": "2.4", "overrides": {"rand": {"pred_speed_mult": [0.6, 0.95]}},
        "train": {"num_worlds": 1, "reset_interval": 5000, "rollout_world_steps": 8}}


def test_train_v2_smoke_with_nine_obs(tmp_path):
    import train_v2
    from stable_baselines3 import PPO

    raw = yaml.safe_load(V2_4.read_text(encoding="utf-8"))
    p = tmp_path / "tiny_v2_4.yaml"
    p.write_text(yaml.safe_dump(dict(TINY, features=raw["features"]), allow_unicode=True), encoding="utf-8")
    out = tmp_path / "m.zip"
    assert train_v2.main(["--steps", "1", "--seed", "0", "--config", str(p), "--out", str(out),
                          "--tb", str(tmp_path / "tb"), "--threads", "1", "--gamma", "0.995",
                          "--probe-every", "1"]) == 0
    m = PPO.load(out, device="cpu")
    assert m.observation_space.shape == (9,) and m.action_space.shape == (5,)
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["obs_names"] == list(OBS9) and meta["v2"]["version"] == "2.4"
    rows = [json.loads(x) for x in out.with_suffix(".probe.jsonl").read_text(encoding="utf-8").splitlines() if x]
    assert rows and {"p_stop_day", "p_stop_night", "phase_use", "frac_night"} <= set(rows[-1])


def test_daynight_draws_only_from_its_own_streams(cfg4, monkeypatch):
    """reset 의 뽑기(daynight_draws)는 World.feature_rng 캐시를 거치지 않으므로, 스트림 생성을 직접 기록해 daynight 의
    part 0·2·3 만 쓰는지 본다(10-06 검토: test_features_v2 의 캐시 검사로는 잡히지 않는다)."""
    import env_v2.world as wm

    seen = []
    real = wm.feature_stream

    def spy(seed, name, part=0):
        seen.append((name, int(part)))
        return real(seed, name, part)

    monkeypatch.setattr(wm, "feature_stream", spy)
    cfg = _dn(cfg4, start_induce=0.5)
    w = World(cfg, seeds=[636])
    pol = ro.build_policy(ro.adapt_spec({"kind": "random", "seed": 1}, 5))
    for _ in range(300):
        w.step(pol(w.observe()))
    assert {n for n, _ in seen} == {"daynight"} and {p for _, p in seen} <= {0, 2, 3}
    assert ("daynight", 0) in seen and ("daynight", 2) in seen


def test_respawn_induction_skips_day_fixed_worlds(cfg4):
    """start_induce > 0 이어도 낮 고정 세계는 리스폰 에너지를 바꾸지 않는다(난수는 같은 수를 뽑는다) — v2.1 동역학 그대로."""
    w4 = World(_dn(cfg4, fixed_day_frac=1.0, start_induce=1.0), seeds=[10000])
    w1 = World(load_v2_config(V2_1), seeds=[10000])
    for _ in range(300):
        o1, o4 = w1.observe(), w4.observe()
        np.testing.assert_array_equal(o1, o4[:, :7])
        a = _rule5(o1)
        w1.step(a)
        w4.step(a)
    assert w1.stats() == w4.stats()


def test_react_conditions_use_names_not_index():
    """diagnose_v2 의 react 표는 threat_recency 를 이름으로 찾는다. v2.4 관측(idx 7 = visibility)에는 그 구간이 없다."""
    from diagnose_v2 import react_conditions

    obs = np.random.default_rng(0).random((400, 9)).astype(np.float32)
    assert not any("threat" in k for k in react_conditions(obs, OBS9))
    obs8 = obs[:, :8]
    names8 = OBS9[:7] + ("threat_recency",)
    assert any("threat" in k for k in react_conditions(obs8, names8))
    assert any("threat" in k for k in react_conditions(obs8))           # 이름 없이 부르면 예전과 같다


def test_rest_cover_only_discounts_only_stoppers_in_cover(cfg4):
    """v2.4b rest_cover_only: 휴식 할인은 결정 때 은신처 안에서 멈춘 개체만 받는다. 끄면(v2.4) 모든 정지 개체가 받는다.
    v2_4b.yaml 은 v2_4.yaml 에서 이 키와 version 만 다르다."""
    w = World(_dn(cfg4, rest_cover_only=True), seeds=[10000])
    w.gait = np.full(w.N, GAIT_STOP, dtype=np.int8)
    _set_dark(w, 1.0)
    w._g = w._geometry()
    drain, _ = w._drain_eat()
    inc = w._g["in_cover"]
    assert inc.any() and (~inc).any()
    base = w.cfg.energy_drain * w._sp["drain_mult"][GAIT_STOP]
    np.testing.assert_array_equal(drain[inc], base * (1.0 - 0.35))
    np.testing.assert_array_equal(drain[~inc], np.full((~inc).sum(), base))
    w0 = World(cfg4, seeds=[10000])
    w0.gait = np.full(w0.N, GAIT_STOP, dtype=np.int8)
    _set_dark(w0, 1.0)
    d0, _ = w0._drain_eat()
    np.testing.assert_array_equal(d0, np.full(w0.N, base * (1.0 - 0.35)))
    r4 = yaml.safe_load(V2_4.read_text(encoding="utf-8"))
    r4b = yaml.safe_load((ROOT / "configs" / "v2_4b.yaml").read_text(encoding="utf-8"))
    assert r4b["features"]["daynight"] == dict(r4["features"]["daynight"], rest_cover_only=True)
    assert {k: v for k, v in r4b.items() if k not in ("features", "version")} ==         {k: v for k, v in r4.items() if k not in ("features", "version")}
    with pytest.raises(ValueError, match="rest_cover_only"):
        World(_dn(cfg4, rest_cover_only=1), seeds=[0])
