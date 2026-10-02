"""V2 1-4 — v2.2 경계(vigilance)·threat_recency·ThreatDir (계획서 4.2·4.3·4.4·4.7, 1단계 1-4, 10절 #1·#5·#18).

문턱 경계, 경계 시 속력 0(speed 보다 우선)·섭식 eat_mult·정지 대사·360° 시야(반경 그대로)·heading(보이면 가장 가까운
포식자 쪽, 아니면 마지막 위협 방향), threat_recency 감쇠·리스폰 리셋, ThreatDir 리스폰 리셋, vigilance 끈 설정 =
v2.1 비트 동일(기록된 Gate E1-b 결과 행 재현 포함), speed·vigilance 끈 설정 = v1 비트 동일, 결정성·복제, 난수를 쓰지
않음(자기 스트림), 경계 통계(vigil_stats)·보행 통계(gait_stats)의 정의, 관측 8·행동 6 이 VecEnv·학습(train_v2,
vigilance 편향 −0.84)·진단(diagnose_v2)·영상(replay_v2)을 통과한다(짧은 smoke).

10-03 검토 회귀: 360° 경계 시야로 새로 찾은 포식자 쪽으로 스텝 끝 heading 을 맞춘다(8c, fov_deg = 360 일 때만).
경계 지속(다음 관측 360°)이 시야를 합친 B3·B4·B5′ 를 치우치게 하는 것을 고정하고, 결정 관측 기본 FOV 만 센 *_narrow 와
시야와 무관한 기준 구간 *_truth 가 포식자를 보지 않는 정책에서 0 근처인지 본다. 관측적 B5 의 역인과와 C4-energy 개입 차.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import json
import math
import pickle

import numpy as np
import pytest
import yaml

import env_v2.features as F
from env.config import ROOT, load_config
from env.world import World as WorldV1
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.steering import EPS, steer
from env_v2.vec_env import MultiWorldVecEnv
from env_v2.world import (ACT_SPEED, GAIT_RUN, GAIT_STOP, GAIT_WALK, OBS_THREAT_RECENCY, RECENT_THREAT,
                          VIGIL_STAT_COLUMNS, World, action_names, obs_dim, obs_names)
from policies.registry import make_policy

V2_1 = ROOT / "configs" / "v2_1.yaml"
V2_2 = ROOT / "configs" / "v2_2.yaml"
NAMES6 = ("forage", "cohesion", "flee_dist", "cover", "speed", "vigilance")
OBS8 = ("food_density", "pred_count", "pred_dist", "kin_count", "energy", "recent_predation", "cover_dist",
        "threat_recency")
ACT_VIG = 5
BASE4 = [0.4, 0.8, 0.4, 0.1]
C_REST = 15.0 / 21.0                      # v2_1.yaml 의 정지 대사 배수(Gate E1-b r2_5_ew0_5)

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def cfg2():
    return load_v2_config(V2_2)


def _features(cfg, **blocks):
    """v2_2.yaml 의 기능 블록에서 일부만 바꾼 설정. 블록 값은 {키: 값} (enabled 포함)."""
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _vig_off(cfg):
    return _features(cfg, vigilance={"enabled": False})


def _act(n, speed=0.5, vig=0.0, base=BASE4):
    a = np.empty((n, 6))
    a[:, :4] = base
    a[:, ACT_SPEED] = speed
    a[:, ACT_VIG] = vig
    return a


def _set_predators(w, pos, head=None):
    """포식자를 `pos` (M,2) 로 바꾼다. 움직이지 않고(속력 0) 사냥하지 않는다(쿨다운). 기하·관측·threat 를 다시 잰다."""
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
    if w._vg is not None:
        w.threat[:] = 0.0
        w.threat_dir[:] = 0.0
        w._tr_truth[:] = 0.0
        w._perceive(w._g)
    w._obs = w._obs_from(w._g)
    return w


def _v1_cfg_of(cfg):
    v1 = load_config()
    return v1.replace(**{k: getattr(cfg, k) for k in v1.to_dict()})


def _same(d1, d2):
    assert d1.keys() == d2.keys()
    for k in d1:
        a, b = d1[k], d2[k]
        assert a == b or (isinstance(a, float) and math.isnan(a) and math.isnan(b)), k


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


def test_v2_2_config_is_v2_1_plus_vigilance(cfg2):
    """v2_2.yaml = v2_1.yaml 의 모든 계수(overrides·speed·train) + vigilance (+ train.init_action_bias). 관측 8, 행동 6."""
    c1 = load_v2_config(V2_1)
    assert cfg2.v2["version"] == "2.2"
    for k, v in c1.to_dict().items():
        if k != "v2":
            assert getattr(cfg2, k) == v, k                      # v1 키(overrides 를 거친 값)가 같다
    assert cfg2.v2["features"]["speed"] == c1.v2["features"]["speed"]
    assert set(cfg2.v2["features"]) == {"speed", "vigilance"}
    assert {k: v for k, v in cfg2.v2["train"].items() if k != "init_action_bias"} == c1.v2["train"]
    assert cfg2.v2["train"]["init_action_bias"] == {"vigilance": -0.84}
    assert set(cfg2.v2["features"]["vigilance"]) == {"enabled"} | set(F.PARAM_KEYS["vigilance"])
    assert "vigilance" in F.IMPLEMENTED and F.FEATURE_IDS["vigilance"] == 3
    w = World(cfg2, seeds=[0])
    assert w.features.active == ("speed", "vigilance")
    assert w.act_names == NAMES6 == action_names(cfg2) and w.act_dim == 6
    assert w.obs_names == OBS8 == obs_names(cfg2) and w.obs_dim == 8 == obs_dim(cfg2)
    assert OBS_THREAT_RECENCY == 7 and w._act_vig == ACT_VIG
    vg = w._vg
    assert (vg["threshold"], vg["decay"], vg["eat_mult"], vg["fov_deg"]) == (0.5, 0.95, 0.0, 360.0)
    assert vg["wide_cos"] == -math.inf
    assert vg["half_life"] == pytest.approx(math.log(0.5) / math.log(0.95))
    assert obs_dim(c1) == 7 and World(c1, seeds=[0]).obs_dim == 7


@pytest.mark.parametrize("kw", [
    {"threshold": -0.1}, {"threshold": 1.5}, {"threshold": True}, {"threshold": "0.5"},
    {"decay": -0.01}, {"decay": 1.01}, {"decay": float("nan")},
    {"eat_mult": -0.5}, {"fov_deg": 90.0}, {"fov_deg": 361.0}, {"fov_deg": [360.0]},
])
def test_vigilance_params_are_checked(cfg2, kw):
    with pytest.raises((ValueError, TypeError)):
        World(_features(cfg2, vigilance=kw), seeds=[0])


def test_vigilance_needs_every_coefficient(cfg2):
    """계수는 yaml 이 유일한 원본이다. 켤 때 하나라도 빠지면 읽을 때 실패한다(코드 기본값 없음). 오타도 실패한다."""
    for key in F.PARAM_KEYS["vigilance"]:
        block = {k: v for k, v in cfg2.v2["features"]["vigilance"].items() if k != key}
        with pytest.raises(ValueError, match=key):
            F.parse_features({"vigilance": block})
    with pytest.raises(ValueError, match="모르는 키"):
        F.parse_features({"vigilance": dict(cfg2.v2["features"]["vigilance"], threshhold=0.5)})


# --------------------------------------------------------------------- #
# 문턱 · 경계 상태 (속력·섭식·대사·heading)
# --------------------------------------------------------------------- #


def test_vigilance_threshold_is_strict_and_beats_speed(cfg2):
    """a > 0.5 이면 경계(같으면 아님). 경계는 speed 명령보다 우선한다: 뛰기 명령이어도 속력 0, 실제 보행 정지."""
    w = World(cfg2, seeds=[10000])
    t = w._vg["threshold"]
    a_vig = np.array([0.0, np.nextafter(t, 0.0), t, np.nextafter(t, 1.0), 0.9, 1.0])
    v_in = np.tile([[0.6, 0.0]], (len(a_vig), 1))
    rng_state = w.rng.bit_generator.state
    w.gait = np.full(len(a_vig), GAIT_RUN, dtype=np.int8)
    v = w._vigil_step(v_in, a_vig)
    want = np.array([False, False, False, True, True, True])
    np.testing.assert_array_equal(w.vigilant, want)
    np.testing.assert_array_equal(np.linalg.norm(v, axis=1), np.where(want, 0.0, 0.6))
    np.testing.assert_array_equal(w.gait, np.where(want, GAIT_STOP, GAIT_RUN))
    np.testing.assert_array_equal(w.vel, v)
    assert w.rng.bit_generator.state == rng_state                    # v1 스트림을 쓰지 않는다

    w = World(cfg2, seeds=[10000])
    w.step(_act(w.N, speed=1.0, vig=0.9))                            # 모두 뛰기 명령 + 경계
    assert w.vigilant.all() and (w.gait == GAIT_STOP).all() and (w.gait_cmd == GAIT_RUN).all()
    assert (w.vel == 0.0).all()


@pytest.mark.parametrize("seed", [10000, 636])
def test_vigilant_agents_stand_do_not_eat_and_pay_rest_metabolism(cfg2, seed):
    """경계: 위치 그대로, 섭식 0(eat_mult), 대사 energy_drain × c_rest(정지 대사), 보상 = 순변화. 절반만 경계시켜
    비경계 절반은 v2.1 걷기 규칙(속력 0.4, 섭식 0.5, 대사 1)과 같은지도 본다."""
    w = World(cfg2, seeds=[seed])
    _set_predators(w, np.empty((0, 2)))                                # 포식자 없음
    c = w.cfg
    vig = np.arange(w.N) % 2 == 0
    a = _act(w.N, speed=0.5, vig=np.where(vig, 1.0, 0.0))
    pos0, e0 = w.pos.copy(), w.energy.copy()
    k = np.flatnonzero(w.food_cap.reshape(-1) > 0.5)[0]
    w.pos[vig] = ((k % w.gw) + 0.5) * c.food_cell, ((k // w.gw) + 0.5) * c.food_cell   # 경계 개체는 먹이 셀 위
    pos0 = w.pos.copy()
    w._g = w._geometry()
    w._perceive(w._g)
    v1 = steer(w._g, a, c)
    _, rew, done, _ = w.step(a)
    assert not done.any()
    np.testing.assert_array_equal(w.pos[vig], pos0[vig])
    rest = c.energy_drain * w._sp["drain_mult"][GAIT_STOP]
    assert rest == pytest.approx(c.energy_drain * C_REST, rel=1e-15)
    np.testing.assert_array_equal(w.energy[vig], e0[vig] - rest)                  # 먹이 셀 위에서도 먹지 않는다
    np.testing.assert_allclose(rew, c.rew_alive + (w.energy - e0), atol=1e-15)
    walk = ~vig & (np.linalg.norm(v1, axis=1) > EPS)
    np.testing.assert_allclose(np.linalg.norm(w.vel[walk], axis=1), 0.4 * c.herb_speed, rtol=1e-12)
    assert (w.gait[vig] == GAIT_STOP).all() and (w.gait[walk] == GAIT_WALK).all()


def test_vigilance_eat_mult_scales_want(cfg2):
    """eat_mult 를 바꾸면 경계 개체의 want 에 곱한다(9절 '섭식 손실' 손잡이). 1 이면 정지 섭식(1.0)과 같다."""
    w = World(_features(cfg2, vigilance={"eat_mult": 1.0}), seeds=[10000])
    w.vigilant[:] = True
    w.gait[:] = GAIT_STOP
    drain, eat = w._drain_eat()
    np.testing.assert_array_equal(eat, 1.0)
    np.testing.assert_allclose(drain, w.cfg.energy_drain * C_REST)
    w2 = World(cfg2, seeds=[10000])
    w2.vigilant[:] = True
    w2.gait[:] = GAIT_STOP
    np.testing.assert_array_equal(w2._drain_eat()[1], 0.0)


def _brute_view(w, i, wide):
    """개체 i 의 (동족 수, 포식자 수, 가장 가까운 보이는 포식자 거리). `_geometry` 와 같은 식을 개체 하나로."""
    c = w.cfg
    h = w.head[i]
    fcos = w._vg["wide_cos"] if wide else c.fov_cos

    def vis(P):
        d = P - w.pos[i]
        dist = np.sqrt(d[:, 0] * d[:, 0] + d[:, 1] * d[:, 1])
        cosang = (d[:, 0] * h[0] + d[:, 1] * h[1]) * (1.0 / np.maximum(dist, EPS))
        return (dist <= c.see_r) & (cosang >= fcos), dist

    kv, _ = vis(w.pos)
    kv[i] = False
    pv, pd = vis(w.pred_pos) if w.M else (np.zeros(0, bool), np.zeros(0))
    return int(kv.sum()), int(pv.sum()), float(pd[pv].min()) if pv.any() else math.inf


def test_wide_view_after_vigilant_step_scenario(cfg2):
    """포식자가 바로 뒤(거리 10)에 있으면 기본 시야(120°)로는 안 보인다. 경계한 스텝 뒤에는 360° 로 보인다(반경 see_r
    밖 25 의 포식자는 여전히 안 보인다). 그 스텝 끝에 heading 이 360° 로 새로 찾은 포식자 쪽(뒤)으로 돈다(8c, 10-03
    검토: 결정 관측 120° 의 ThreatDir 만 따르면 한 스텝짜리 경계가 방향을 남기지 못한다). 그래서 경계를 풀고 멈춰 서면
    120° 시야가 그 포식자 쪽이라 계속 보인다(heading 유지). 다시 경계해도 heading 은 위협 쪽 그대로다."""
    w = World(cfg2, seeds=[10000])
    i = 0
    h0 = w.head[i].copy()
    w.pos[i] = np.clip(w.pos[i], 30.0, w.size - 30.0)                 # 포식자가 맵 안에 있게
    near, far = w.pos[i] - 10.0 * h0, w.pos[i] - 25.0 * h0
    _set_predators(w, [near, far])
    o = w.observe()
    assert o[i, 1] == 0.0 and o[i, 2] == 1.0 and o[i, OBS_THREAT_RECENCY] == 0.0     # 뒤라 안 보인다
    stop_vig, stop = _act(w.N, speed=0.0, vig=1.0), _act(w.N, speed=0.0, vig=0.0)

    o, *_ = w.step(stop_vig)                                          # 1) 경계 한 스텝
    assert w._wide[i]
    assert o[i, 1] == np.float32(1 / 8) and o[i, 2] == np.float32(10.0 / 20.0)     # 360°, 반경 20 안의 하나만
    assert o[i, OBS_THREAT_RECENCY] == 1.0
    np.testing.assert_allclose(w.threat_dir[i], -h0, atol=1e-12)     # 위협 방향 = 뒤
    np.testing.assert_array_equal(w.head[i], w.threat_dir[i])         # 8c: 스텝 끝 heading = 새로 찾은 위협 쪽
    np.testing.assert_array_equal(w.gaze[i], w.head[i])
    kin, pc, d = _brute_view(w, i, wide=True)                         # 360° 관측은 heading 과 무관하다
    assert (o[i, 3], o[i, 1]) == (np.float32(min(kin / 20, 1)), np.float32(pc / 8)) and pc == 1

    o, *_ = w.step(stop)                                              # 2) 경계를 풀고 정지: 120°, heading 유지
    assert not w._wide[i]
    np.testing.assert_allclose(w.head[i], -h0, atol=1e-12)
    assert o[i, 1] == np.float32(1 / 8) and o[i, 2] == np.float32(10.0 / 20.0)     # 120° 가 포식자 쪽이라 보인다
    assert o[i, OBS_THREAT_RECENCY] == 1.0
    kin_n, pc_n, _ = _brute_view(w, i, wide=False)
    assert o[i, 3] == np.float32(min(kin_n / 20, 1)) and kin_n <= kin and pc_n == 1

    o, *_ = w.step(stop_vig)                                          # 3) 다시 경계: heading ← ThreatDir (그대로 뒤쪽)
    np.testing.assert_allclose(w.head[i], -h0, atol=1e-12)
    np.testing.assert_array_equal(w.gaze[i], w.head[i])
    o, *_ = w.step(stop)                                              # 4) 정지: 120° 가 포식자 쪽이라 보인다
    assert o[i, 1] == np.float32(1 / 8) and o[i, OBS_THREAT_RECENCY] == 1.0


def test_vigilant_heading_is_not_turned_after_perception_below_360(cfg2):
    """fov_deg < 360 이면 8c 를 하지 않는다 — heading 을 바꾸면 그 heading 으로 잰 경계 시야 관측과 어긋나기 때문이다.
    그 스텝에 처음 본 포식자(140° 뒤, 300° 시야 안·120° 밖) 쪽은 다음 경계 스텝의 1e 에서 돈다. 관측은 늘 스텝 끝
    heading 으로 잰 값과 같다."""
    w = World(_features(cfg2, vigilance={"fov_deg": 300.0}), seeds=[10000])
    i = 0
    h0 = w.head[i].copy()
    w.pos[i] = np.clip(w.pos[i], 30.0, w.size - 30.0)
    c, s = math.cos(math.radians(140.0)), math.sin(math.radians(140.0))
    u = np.array([h0[0] * c - h0[1] * s, h0[0] * s + h0[1] * c])     # heading 에서 140° 돈 방향
    _set_predators(w, [w.pos[i] + 10.0 * u])
    assert w.observe()[i, 1] == 0.0
    stop_vig, stop = _act(w.N, speed=0.0, vig=1.0), _act(w.N, speed=0.0, vig=0.0)

    o, *_ = w.step(stop_vig)                                          # 1) 경계: 300° 로 보이지만 heading 은 유지
    assert w._wide[i] and o[i, 1] == np.float32(1 / 8) and o[i, OBS_THREAT_RECENCY] == 1.0
    np.testing.assert_allclose(w.threat_dir[i], u, atol=1e-12)
    np.testing.assert_array_equal(w.head[i], h0)
    kin, pc, d = _brute_view(w, i, wide=True)                         # 스텝 끝 heading(h0)으로 잰 300° 관측과 같다
    assert (o[i, 1], o[i, 2], o[i, 3]) == (np.float32(pc / 8), np.float32(min(d / 20, 1)),
                                           np.float32(min(kin / 20, 1))) and pc == 1
    o, *_ = w.step(stop)                                              # 2) 정지: 120° 밖이라 안 보인다
    assert o[i, 1] == 0.0 and o[i, OBS_THREAT_RECENCY] == np.float32(0.95)
    w.step(stop_vig)                                                  # 3) 다시 경계: 1e 에서 위협 쪽으로 돈다
    np.testing.assert_allclose(w.head[i], u, atol=1e-12)
    o, *_ = w.step(stop)                                              # 4) 정지: 120° 가 포식자 쪽이라 보인다
    assert o[i, 1] == np.float32(1 / 8)


def test_vigilant_heading_faces_nearest_visible_predator(cfg2):
    """보이는 포식자가 둘이면 ThreatDir·heading 은 가장 가까운 쪽 단위벡터다(결정 때 관측 기준)."""
    w = World(cfg2, seeds=[636])
    i = 3
    w.pos[i] = (w.size / 2, w.size / 2)
    w._wide[i] = True                                                 # 결정 관측을 360° 로
    p_near = w.pos[i] + np.array([-6.0, 8.0])                          # 거리 10, 방향 (-0.6, 0.8)
    p_far = w.pos[i] + np.array([12.0, 5.0])                           # 거리 13
    _set_predators(w, [p_far, p_near])
    np.testing.assert_allclose(w.threat_dir[i], [-0.6, 0.8], atol=1e-12)
    a = _act(w.N, speed=0.0, vig=0.0)
    a[i, ACT_VIG] = 1.0
    w.step(a)
    np.testing.assert_allclose(w.head[i], [-0.6, 0.8], atol=1e-12)
    assert np.linalg.norm(w.head[i]) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("seed", [10000, 10003])
def test_geometry_uses_wide_view_exactly_for_last_step_vigilant(cfg2, seed):
    """여러 스텝 동안 모든 개체의 관측 1·3(포식자·동족 수)과 거리가 '직전 스텝에 경계했으면 360°, 아니면 120°'와 같다.
    리스폰 개체는 경계했어도 기본 시야다. 관측 7 은 threat_recency 그대로다."""
    w = World(cfg2, seeds=[seed])
    rng = np.random.default_rng(seed)
    checked = 0
    for _ in range(40):
        a = _act(w.N, speed=0.5, vig=0.0)
        a[:, ACT_SPEED] = rng.random(w.N)
        a[:, ACT_VIG] = rng.random(w.N)
        obs, _, done, _ = w.step(a)
        np.testing.assert_array_equal(w._wide, w.vigilant & ~done)
        np.testing.assert_array_equal(obs[:, OBS_THREAT_RECENCY], w.threat.astype(np.float32))
        if done.any():          # 산 개체의 관측은 리스폰 전 위치로 쟀다(v1 규약) — 리스폰이 있던 스텝은 건너뛴다
            continue
        checked += 1
        for i in range(0, w.N, 7):
            kin, pc, d = _brute_view(w, i, bool(w._wide[i]))
            assert obs[i, 3] == np.float32(min(kin / 20, 1)) and obs[i, 1] == np.float32(min(pc / 8, 1)), i
            assert obs[i, 2] == np.float32(min(d / 20, 1)), i
    assert checked >= 10


# --------------------------------------------------------------------- #
# threat_recency · ThreatDir · 리스폰
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("decay", [0.9, 0.95, 0.975])
def test_threat_recency_is_one_when_seen_then_decays(cfg2, decay):
    """보이는 동안 1, 안 보이면 스텝마다 × decay (놓친 뒤 k 스텝 = decay^k, 같은 곱셈 순서로 비트 동일).
    ThreatDir 는 안 보이는 동안 마지막 값 그대로다."""
    w = World(_features(cfg2, vigilance={"decay": decay}), seeds=[10000])
    i = 5
    w.pos[i] = (w.size / 2, w.size / 2)
    _set_predators(w, [w.pos[i] + 5.0 * w.head[i]])                   # 바로 앞 5: 보인다
    assert w.threat[i] == 1.0
    td = w.threat_dir[i].copy()
    stop = _act(w.N, speed=0.0, vig=0.0)
    for _ in range(3):
        w.step(stop)
        assert w.threat[i] == 1.0
    w.M = 0                                                           # 포식자가 사라진다
    r = 1.0
    for _ in range(30):
        o, *_ = w.step(stop)
        r = r * decay
        assert w.threat[i] == r and o[i, OBS_THREAT_RECENCY] == np.float32(r)
        np.testing.assert_array_equal(w.threat_dir[i], td)


def test_respawn_resets_threat_threatdir_and_view(cfg2):
    """리스폰: threat_recency 0, ThreatDir 0, 기본 시야(경계하다 죽어도). terminal_obs 는 죽기 전 값이다. 리스폰 관측에서
    포식자가 보이면 바로 1 이 된다(그 개체의 첫 관측)."""
    w = World(cfg2, seeds=[10000])
    i = 7
    w.pos[i] = (w.size / 2, w.size / 2)
    _set_predators(w, [w.pos[i] + 5.0 * w.head[i]])
    w.step(_act(w.N, speed=0.0, vig=0.0))
    w.M = 0
    w.step(_act(w.N, speed=0.0, vig=0.0))
    assert w.threat[i] == 0.95 and (w.threat_dir[i] != 0).any()
    w.energy[i] = 1e-6                                               # 이번 스텝에 굶어 죽는다
    a = _act(w.N, speed=0.0, vig=1.0)
    obs, _, done, term = w.step(a)
    assert done[i] and w.vigilant[i]                                  # 훅은 죽은 개체의 마지막 스텝 값 그대로
    assert term[i, OBS_THREAT_RECENCY] == np.float32(0.95 * 0.95)
    assert obs[i, OBS_THREAT_RECENCY] == 0.0 and w.threat[i] == 0.0
    np.testing.assert_array_equal(w.threat_dir[i], 0.0)
    assert not w._wide[i] and w._wide[~done].all()
    assert w._vig_prev[i] == -1
    assert not w._near[i] and w._tr_truth[i] == 0.0                   # 통계 전용 기준 흔적도 새 개체로 (포식자 없음)

    # 리스폰 자리에서 포식자가 보이면 1 (리셋 뒤 같은 갱신 규칙)
    w = World(cfg2, seeds=[10000])
    w.energy[i] = 1e-6
    orig = w._respawn

    def respawn_in_front(dead):
        orig(dead)
        for j in dead:
            w.pos[j] = (w.size / 2, w.size / 2)
            w.head[j] = (1.0, 0.0)
    w._respawn = respawn_in_front
    _set_predators(w, [(w.size / 2 + 4.0, w.size / 2)])
    obs, _, done, _ = w.step(_act(w.N, speed=0.0, vig=0.0))
    assert done[i] and obs[i, OBS_THREAT_RECENCY] == 1.0
    np.testing.assert_allclose(w.threat_dir[i], [1.0, 0.0], atol=1e-12)
    assert w._near[i] and w._tr_truth[i] == 1.0


def test_reset_starts_from_zero_and_first_view(cfg2):
    """reset: 모두 기본 시야, threat_recency 는 첫 관측에서 보이면 1 아니면 0, ThreatDir 는 보이면 그 방향 아니면 0."""
    for seed in (0, 636, 10000):
        w = World(cfg2, seeds=[seed])
        seen = w._g["pred_count"] > 0
        assert not w._wide.any() and not w.vigilant.any()
        np.testing.assert_array_equal(w.threat, np.where(seen, 1.0, 0.0))
        np.testing.assert_array_equal(w.threat_dir[~seen], 0.0)
        np.testing.assert_allclose(np.linalg.norm(w.threat_dir[seen], axis=1), 1.0, atol=1e-12)


# --------------------------------------------------------------------- #
# 이전 버전과의 관계 · 결정성 · 난수
# --------------------------------------------------------------------- #

SPECS = [{"kind": "fixed", "action": [0.3, 0.8, 0.4, 0.1, 0.2]}, {"kind": "random", "seed": 3, "act_dim": 5}]


def _rule5(obs):
    a = np.tile(BASE4 + [0.5], (len(obs), 1))
    a[obs[:, 4] < 0.5, ACT_SPEED] = 0.0
    a[obs[:, 2] < 0.5, ACT_SPEED] = 1.0
    return a


@pytest.mark.parametrize("seed", [0, 636, 10000])
@pytest.mark.parametrize("pol", ["fixed", "random", "rule"])
def test_vigilance_off_matches_v2_1_bitwise(cfg2, seed, pol):
    """v2_2.yaml 에서 vigilance 만 끈 설정 = v2_1.yaml (관측·보상·위치·heading·보행·통계 10열·gait_stats 비트 동일).
    관측 7·행동 5 이고 경계 훅이 없다."""
    w2 = World(_vig_off(cfg2), seeds=[seed])
    w1 = World(load_v2_config(V2_1), seeds=[seed])
    assert w2.features.active == ("speed",) and w2.act_dim == 5 and w2.obs_dim == 7
    assert getattr(w2, "vigilant", None) is None and getattr(w2, "gaze", None) is None
    p1, p2 = [ro.build_policy(SPECS[pol == "random"]) if pol != "rule" else _rule5 for _ in range(2)]
    for _ in range(300):
        o1, o2 = w1.observe(), w2.observe()
        np.testing.assert_array_equal(o1, o2)
        r1, r2 = w1.step(p1(o1)), w2.step(p2(o2))
        for x, y in zip(r1, r2):
            np.testing.assert_array_equal(x, y)
        np.testing.assert_array_equal(w1.gait, w2.gait)
    assert w1.stats() == w2.stats()
    _same(w1.gait_stats(), w2.gait_stats())
    for k in ("pos", "head", "energy", "pred_pos", "food", "vel"):
        np.testing.assert_array_equal(getattr(w1, k), getattr(w2, k), err_msg=k)


def test_vigilance_off_reproduces_recorded_v2_1_result(cfg2):
    """1-4 전 코드가 남긴 Gate E1-b 결과(results/v2/e1/B1/r2_5_ew0_5/constsearch_seg.json, C2-seg, 평가 시드 10000 ×
    5000스텝)를 vigilance 를 끈 v2_2 설정으로 다시 돌리면 행 전체(G_γ·통계·보행 지표)가 비트 단위로 같다."""
    d = json.loads((ROOT / "results/v2/e1/B1/r2_5_ew0_5/constsearch_seg.json").read_text(encoding="utf-8"))
    m = d["meta"]
    assert m["config_digest"] == "f068496361f9" and m["eval_steps"] == 5000 and int(m.get("head") or 0) == 0
    spec = {"policy": {"kind": "fixed", "action": d["base_action"]},
            "wrap": [{"kind": "seg_const", "bins": d["bins"], "dims": d["dims"],
                      "table": [x for row in d["best_table"] for x in row]}]}
    want = d["per_seed"]["C2-seg"][0]
    assert want["seed"] == 10000
    r = ro.rollout(_vig_off(cfg2), ro.build_policy(spec, 10000), 10000, m["eval_steps"], gamma=m["gamma"],
                   tail=m["tail"])
    from diagnose_v2 import clean

    assert clean(ro.public_row(r)) == want


@pytest.mark.parametrize("seed", [0, 10000])
@pytest.mark.parametrize("spec", [{"kind": "fixed", "action": [0.3, 0.8, 0.4, 0.1]}, {"kind": "utility"},
                                  {"kind": "random", "seed": 3}], ids=["fixed", "utility", "random"])
def test_speed_and_vigilance_off_matches_v1_bitwise(cfg2, seed, spec):
    """speed·vigilance 를 모두 끈 v2_2 설정 = 같은 v1 키(E1-b 포식자 속도 포함)의 v1 World. 관측 7·행동 4."""
    w2 = World(_features(cfg2, speed={"enabled": False}, vigilance={"enabled": False}), seeds=[seed])
    assert w2.features.active == () and w2.act_dim == 4 and w2.obs_dim == 7
    v1 = WorldV1(_v1_cfg_of(cfg2), seeds=[seed])
    p1, p2 = make_policy(spec), make_policy(spec)
    for _ in range(300):
        o1, o2 = v1.observe(), w2.observe()
        np.testing.assert_array_equal(o1, o2)
        v1.step(p1(o1))
        w2.step(p2(o2))
    assert v1.stats() == w2.stats()
    for k in ("pos", "head", "energy", "pred_pos", "food"):
        np.testing.assert_array_equal(getattr(v1, k), getattr(w2, k), err_msg=k)


def test_never_vigilant_matches_v2_1_world(cfg2):
    """vigilance 를 켜도 아무도 경계하지 않으면(a ≤ 0.5) 위치·에너지·보상·보행이 v2.1 과 같다. 관측은 7 열까지 같고
    threat_recency 칸만 더 있다(포식자는 경계를 모르고, 시야는 늘 120° 다)."""
    w2, w1 = World(cfg2, seeds=[636]), World(load_v2_config(V2_1), seeds=[636])
    for _ in range(300):
        o1, o2 = w1.observe(), w2.observe()
        np.testing.assert_array_equal(o1, o2[:, :7])
        a5 = _rule5(o1)
        r1, r2 = w1.step(a5), w2.step(np.c_[a5, np.full(w2.N, 0.5)])
        for x, y in zip(r1[1:3], r2[1:3]):
            np.testing.assert_array_equal(x, y)
    assert w1.stats() == w2.stats()
    _same(w1.gait_stats(), w2.gait_stats())
    assert w2.vigil_stats()["vig_frac"] == 0.0 and w2.vigil_stats()["obs_wide_frac"] == 0.0


def test_vigilance_world_is_deterministic_and_uses_no_random_stream(cfg2):
    """켠 상태: 같은 시드·정책이면 같은 궤적·통계. pickle·deepcopy 한 세계는 이어서 같게 돈다. 기능 난수 스트림 0개이고
    경계·인식 단계는 v1 스트림을 건드리지 않는다(규칙 1, 4.8)."""
    spec = ro.adapt_spec({"kind": "random", "seed": 2}, 6)
    a, b = World(cfg2, seeds=[636]), World(cfg2, seeds=[636])
    pa, pb = ro.build_policy(spec), ro.build_policy(spec)
    for _ in range(200):
        ra, rb = a.step(pa(a.observe())), b.step(pb(b.observe()))
        for x, y in zip(ra, rb):
            np.testing.assert_array_equal(x, y)
    assert a.stats() == b.stats()
    _same(a.vigil_stats(), b.vigil_stats())
    clones = [pickle.loads(pickle.dumps(a)), copy.deepcopy(a)]
    for _ in range(50):
        act = pa(a.observe())
        a.step(act)
        for c in clones:
            c.step(act)
    for c in clones:
        for k in ("pos", "head", "threat", "threat_dir", "_wide", "vigilant"):
            np.testing.assert_array_equal(getattr(c, k), getattr(a, k), err_msg=k)
        _same(c.vigil_stats(), a.vigil_stats())
    assert a._feature_rngs == {}
    state = a.rng.bit_generator.state
    a._vigil_step(np.zeros((a.N, 2)), np.full(a.N, 0.9))
    a._perceive(a._g)
    assert a.rng.bit_generator.state == state


def test_vigilance_without_speed(cfg2):
    """speed 를 끄고 vigilance 만 켜면 행동 5개(idx 4 = vigilance), 관측 8개. 경계 개체는 멈추고 먹지 않고 대사는 v1(1×)
    이다(speed 가 없어 대사가 속력과 무관하다). 비경계 개체는 v1 과 같이 herb_speed 로 움직인다. vel 훅이 있다."""
    cfg = _features(cfg2, speed={"enabled": False})
    w = World(cfg, seeds=[10000])
    _set_predators(w, np.empty((0, 2)))
    assert w.act_names == ("forage", "cohesion", "flee_dist", "cover", "vigilance") and w._act_vig == 4
    assert w.obs_dim == 8 and getattr(w, "gait", None) is None
    vig = np.arange(w.N) % 3 == 0
    a = np.c_[np.tile(BASE4, (w.N, 1)), np.where(vig, 1.0, 0.0)]
    v1 = steer(w._g, a, w.cfg)
    pos0, e0 = w.pos.copy(), w.energy.copy()
    w.step(a)
    np.testing.assert_array_equal(w.pos[vig], pos0[vig])
    np.testing.assert_array_equal(w.energy[vig], e0[vig] - w.cfg.energy_drain)
    mv = ~vig & (np.linalg.norm(v1, axis=1) > EPS)
    np.testing.assert_allclose(np.linalg.norm(w.vel[mv], axis=1), w.cfg.herb_speed, rtol=1e-12)
    np.testing.assert_array_equal(w.vel[vig], 0.0)
    with pytest.raises(ValueError):
        w.gait_stats()


def test_wrong_action_width_is_refused(cfg2):
    w = World(cfg2, seeds=[0])
    for k in (4, 5, 7):
        with pytest.raises(ValueError, match="vigilance"):
            w.step(np.full((w.N, k), 0.5))


# --------------------------------------------------------------------- #
# 통계: vigil_stats · gait_stats
# --------------------------------------------------------------------- #


def _rule6(obs):
    """상태 의존 규칙: 놓친 직후(최근 위협·안 보임) 경계, 포식자 가까우면 뛰기, 배고프면 정지, 그 밖은 걷기.
    포식자가 보이고 배부르면 가끔 경계(관측 0 으로 갈라 둔다)."""
    a = np.tile(BASE4 + [0.5, 0.0], (len(obs), 1))
    a[obs[:, 4] < 0.5, ACT_SPEED] = 0.0
    a[obs[:, 2] < 0.5, ACT_SPEED] = 1.0
    a[(obs[:, OBS_THREAT_RECENCY] > 0.5) & (obs[:, 2] >= 1.0), ACT_VIG] = 1.0
    a[(obs[:, 2] < 1.0) & (obs[:, 4] >= 0.5) & (obs[:, 0] > 0.05), ACT_VIG] = 0.8
    return a


def _near_hand(w):
    """개체마다 거리 ≤ see_r 인 포식자가 있는가(FOV 무시) — `_perceive` 의 기준 상태를 지금 위치로 손으로 잰다."""
    if not w.M:
        return np.zeros(w.N, dtype=bool)
    ex = w.pred_pos[:, 0][None, :] - w.pos[:, 0:1]
    ey = w.pred_pos[:, 1][None, :] - w.pos[:, 1:2]
    return (np.sqrt(ex * ex + ey * ey) <= w.cfg.see_r).any(1)


@pytest.mark.parametrize("seed", [10000, 10003])
def test_vigil_stats_match_hand_counts(cfg2, seed):
    """vigil_stats 를 스텝마다 손으로 센 값과 맞춘다: 구간별 P(경계)·B3(결정 관측 기본 시야만인 b3_narrow 포함)·B4(이동 도주를
    결정 관측 시야로 나눈 b4_narrow·b4_wide 와 그 합 b4, 경계한 도주 분기, 죽은 개체 제외)·B5 기울기·energy 구간·B5′(포식자
    수, 결정 관측 기본 시야만인 *_narrow, recent_predation 상·하위 20% 스텝)·b8_vig(리스폰 개체는 잇지 않는다)·360° 관측의
    동족·포식자 수·threat 평균·시야와 무관한 기준 구간(*_truth: 결정 위치의 반경 안 여부와 그 흔적, 리스폰 0)."""
    w = World(cfg2, seeds=[seed])
    c, T = w.cfg, 500
    decay = w._vg["decay"]
    rows = []
    prev = np.full(w.N, -1)
    sw = sws = 0
    b4 = np.zeros((3, 2))
    ema_t, nv_t = [], []
    near_h = _near_hand(w)
    tr_h = np.where(near_h, 1.0, 0.0)                               # reset: 0 에서 첫 관측으로
    for _ in range(T):
        g0, tr0, wide0, e0 = w._g, w.threat.copy(), w._wide.copy(), w.energy.copy()
        ema0 = min(w.pred_ema, 1.0)
        near0, trt0 = w._near.copy(), w._tr_truth.copy()
        np.testing.assert_array_equal(near0, near_h)                 # 결정 관측 위치에서 잰 반경 안 여부
        np.testing.assert_array_equal(trt0, tr_h)                    # 같은 곱셈 순서라 비트 동일
        assert not ((g0["pred_count"] > 0) & ~near0).any()           # 보임 ⇒ 반경 안
        obs = w.observe()
        np.testing.assert_array_equal(obs[:, OBS_THREAT_RECENCY], tr0.astype(np.float32))
        a = _rule6(obs)
        _, _, done, _ = w.step(a)
        vig = w.vigilant.copy()
        pc = g0["pred_count"]
        seg = np.where(pc > 0, np.where(pc >= 2, 3, 2), np.where(tr0 > RECENT_THREAT, 1, 0))
        seg_t = np.where(near0, 2, np.where(trt0 > RECENT_THREAT, 1, 0))
        rows.append(np.c_[seg, wide0, e0 >= 0.5, vig, np.clip(e0, 0, 1), g0["kin_count"], pc, tr0, seg_t])
        ema_t.append(ema0)
        nv_t.append(vig.sum())
        same = prev >= 0
        sws += same.sum()
        sw += (same & (prev != vig)).sum()
        prev = vig.astype(int)
        prev[done] = -1
        branch = g0["d_pred_min"] < a[:, 2] * c.see_r
        moving = np.linalg.norm(w.vel, axis=1) > EPS
        lost = w._g["pred_count"] == 0                              # 산 개체의 행은 리스폰이 바꾸지 않는다
        mv = branch & ~vig & moving
        for k, m in enumerate((mv & ~wide0, mv & wide0, branch & vig)):
            m = m & ~done
            b4[k] += (m.sum(), (m & lost).sum())
        near_h = _near_hand(w)                                      # 스텝 끝(죽은 개체는 리스폰) 위치
        tr_h = np.where(near_h, 1.0, np.where(done, 0.0, tr_h * decay))
    X = np.concatenate(rows)
    seg, wide, full, v = X[:, 0], X[:, 1] > 0, X[:, 2] > 0, X[:, 3] > 0
    e, kin, pcs, tr, seg_t = X[:, 4], X[:, 5], X[:, 6], X[:, 7], X[:, 8]
    s = w.vigil_stats()
    assert tuple(s) == VIGIL_STAT_COLUMNS

    def p(m):
        return v[m].mean() if m.any() else float("nan")

    assert (seg == 1).any() and (seg >= 2).any() and wide.any() and b4[0, 0] > 0 and b4[1, 0] > 0, \
        "이 시드에서 조건 표본이 있어야 한다"
    assert (seg_t == 1).any() and (seg_t == 2).any()
    assert s["vig_frac"] == pytest.approx(v.mean())
    assert [s["seg_seen_frac"], s["seg_recent_frac"], s["seg_calm_frac"]] == pytest.approx(
        [(seg >= 2).mean(), (seg == 1).mean(), (seg == 0).mean()])
    assert [s["p_vig_seen"], s["p_vig_recent"], s["p_vig_calm"]] == pytest.approx(
        [p(seg >= 2), p(seg == 1), p(seg == 0)])
    assert s["b3"] == pytest.approx(p(seg == 1) - p(seg == 0))
    assert s["b3_narrow"] == pytest.approx(p((seg == 1) & ~wide) - p((seg == 0) & ~wide))
    assert s["b4"] == pytest.approx((b4[0, 1] + b4[1, 1]) / (b4[0, 0] + b4[1, 0]))
    assert s["b4_n"] == b4[0, 0] + b4[1, 0] == s["b4_narrow_n"] + s["b4_wide_n"]
    assert s["b4_narrow"] == pytest.approx(b4[0, 1] / b4[0, 0]) and s["b4_narrow_n"] == b4[0, 0]
    assert s["b4_wide"] == pytest.approx(b4[1, 1] / b4[1, 0]) and s["b4_wide_n"] == b4[1, 0]
    assert s["b4_vig_n"] == b4[2, 0]
    assert s["b4_vig"] == pytest.approx(b4[2, 1] / b4[2, 0] if b4[2, 0] else float("nan"), nan_ok=True)
    assert [s["p_vig_seen_narrow"], s["p_vig_pc0_narrow"], s["p_vig_pc1_narrow"], s["p_vig_pc2_narrow"]] == pytest.approx(
        [p((seg >= 2) & ~wide), p((seg <= 1) & ~wide), p((seg == 2) & ~wide), p((seg == 3) & ~wide)], nan_ok=True)
    assert s["b5p_pred_narrow"] == pytest.approx(p((seg >= 2) & ~wide) - p((seg <= 1) & ~wide))
    assert [s["seg_near_truth_frac"], s["seg_recent_truth_frac"]] == pytest.approx(
        [(seg_t == 2).mean(), (seg_t == 1).mean()])
    assert [s["p_vig_near_truth"], s["p_vig_recent_truth"], s["p_vig_calm_truth"]] == pytest.approx(
        [p(seg_t == 2), p(seg_t == 1), p(seg_t == 0)])
    assert s["b3_truth"] == pytest.approx(p(seg_t == 1) - p(seg_t == 0))
    assert s["b5p_truth"] == pytest.approx(p(seg_t == 2) - p(seg_t <= 1))
    assert s["b5"] == pytest.approx(np.polyfit(e, v.astype(float), 1)[0], rel=1e-9, abs=1e-12)
    assert [s["p_vig_hungry"], s["p_vig_full"]] == pytest.approx([p(~full), p(full)])
    assert s["b5p_pred"] == pytest.approx(p(seg >= 2) - p(seg <= 1))
    assert [s["p_vig_pc0"], s["p_vig_pc1"], s["p_vig_pc2"]] == pytest.approx(
        [p(seg <= 1), p(seg == 2), p(seg == 3)], nan_ok=True)
    ema, nv = np.array(ema_t), np.array(nv_t, dtype=float)
    lo, hi = np.quantile(ema, [0.2, 0.8])
    assert s["b5p_ema"] == pytest.approx(nv[ema >= hi].sum() / (w.N * (ema >= hi).sum())
                                         - nv[ema <= lo].sum() / (w.N * (ema <= lo).sum()))
    assert s["b8_vig"] == pytest.approx(sw / sws * 60 / 8)
    assert s["obs_wide_frac"] == pytest.approx(wide.mean())
    assert [s["kin_narrow"], s["kin_wide"], s["pred_narrow"], s["pred_wide"]] == pytest.approx(
        [kin[~wide].mean(), kin[wide].mean(), pcs[~wide].mean(), pcs[wide].mean()])
    assert s["threat_mean"] == pytest.approx(tr.mean())
    assert s["b3"] > 0.5                                         # 규칙 정책이니 놓친 직후 경계가 뚜렷하다
    assert s["kin_wide"] > s["kin_narrow"]                       # 360° 관측은 동족을 더 많이 본다(4.2 주의)


def test_constant_policy_has_zero_conditional_vigilance_differences(cfg2):
    """상수 정책(C1·C2 꼴)은 B3·B5·B5′ 이 구성상 0 이고 경계 전환이 없다 — 6.3 판정 규칙의 전제."""
    for vig in (0.2, 0.9):
        w = World(cfg2, seeds=[10000])
        for _ in range(300):
            w.step(_act(w.N, speed=0.5, vig=vig))
        s = w.vigil_stats()
        assert s["vig_frac"] == (1.0 if vig > 0.5 else 0.0)
        for k in ("b3", "b5p_pred", "b5p_ema", "b8_vig", "b3_truth", "b5p_truth"):
            assert s[k] == 0.0, k
        # 늘 경계하면 기본 시야 관측은 첫 스텝·리스폰 개체뿐이라 '최근 위협' 표본이 없다(nan)
        for k in ("b3_narrow", "b5p_pred_narrow"):
            assert s[k] == 0.0 or (vig > 0.5 and math.isnan(s[k])), k
        assert s["b5"] == pytest.approx(0.0, abs=1e-12)
        assert s["obs_wide_frac"] == pytest.approx(1.0 - 1.0 / 300 if vig > 0.5 else 0.0, abs=0.01)


def _blind_markov(stay, start, seed):
    """관측을 보지 않는 지속형 경계 규칙: 직전에 경계했으면 확률 stay 로 유지, 아니면 start 로 시작(정상 비율
    start/(start + 1 − stay), 평균 지속 1/(1 − stay) 스텝). 비경계 개체는 걷기·v1 조향 그대로(조향은 기하를 본다)."""
    rng = np.random.default_rng(seed)
    prev = np.zeros(128, dtype=bool)

    def pol(obs):
        nonlocal prev
        prev = rng.random(len(obs)) < np.where(prev, stay, start)
        return _act(len(obs), speed=0.5, vig=np.where(prev, 1.0, 0.0))
    return pol


def _run_stats(cfg, seed, pol, steps, fix4=None):
    """`steps` 스텝 뒤 vigil_stats 와 관측 4 평균. fix4 를 주면 정책에 넣는 관측 4 를 그 값으로 고정한다(C4-energy 고정)."""
    w = World(cfg, seeds=[seed])
    e_sum = 0.0
    for _ in range(steps):
        o = w.observe()
        e_sum += float(o[:, 4].mean())
        if fix4 is not None:
            o = o.copy()
            o[:, 4] = fix4
        w.step(pol(o))
    return w.vigil_stats(), e_sum / steps


@pytest.mark.parametrize("stay,start,seed", [(0.9, 0.05, 10000), (0.96, 0.01, 10003)])
def test_persistent_predator_blind_vigilance_biases_pooled_indicators(cfg2, stay, start, seed):
    """10-03 검토 회귀: 포식자를 보지 않고 경계를 몇 스텝씩 잇기만 하는 정책. 경계한 개체의 다음 결정 관측이 360° 라
    시야를 합친 지표는 행동과 무관하게 치우친다 — B5′ 관측 기준(b5p_pred)은 기준 0.2 를 넘고(거짓 통과), B3(b3)는
    음수로 내려가며, B4(b4_wide)는 v1 비교 값(b4_narrow)보다 크다. 결정 관측이 기본 FOV 인 개체만 센 *_narrow 와
    시야와 무관한 기준 구간 *_truth 는 0 근처다. 이 치우침이 있다는 사실을 고정해 둔다(판정 정의는 1-6 사전 등록)."""
    s, _ = _run_stats(cfg2, seed, _blind_markov(stay, start, seed), 3000)
    assert s["vig_frac"] == pytest.approx(start / (start + 1.0 - stay), abs=0.03)
    assert s["b5p_pred"] > 0.2 and s["p_vig_seen"] > s["p_vig_pc0"]          # 360° 선택 효과 (B5′ +)
    assert s["b3"] < -0.05                                                    # 경계 지속이 평시 쪽을 채운다 (B3 −)
    for k in ("b5p_pred_narrow", "b3_narrow"):
        assert abs(s[k]) < 0.03, (k, s[k])
    for k in ("b5p_truth", "b3_truth"):
        assert abs(s[k]) < 0.05, (k, s[k])
    assert s["b4_wide"] > s["b4_narrow"] + 0.05                               # 360° 결정 뒤 도주는 구성상 자주 놓친다
    assert s["b4_narrow"] < s["b4"] < s["b4_wide"]
    assert s["b5"] < -0.03                  # 경계 섭식 0 의 역인과: energy 를 보지 않아도 B5 기대 부호(−)가 나온다


def test_b5_sign_is_reverse_causal_and_c4_energy_separates(cfg2):
    """10-03 검토 회귀: 관측적 B5(b5)는 energy 를 보지 않는 지속 경계에서도 음수다(부호 기준 자동 통과). 같은 평가 시드에서
    C4-energy(정책에 넣는 관측 4 를 평균으로 고정)와의 차는 energy 를 보지 않는 정책에서 정확히 0, 배고플 때 경계를 더 하는
    정책에서 뚜렷한 음수다 — B5 판정은 이 개입 차로 한다(1-6 사전 등록)."""
    seed, T = 10000, 1500
    blind = lambda: _blind_markov(0.96, 0.01, seed)                           # noqa: E731
    s0, e_mean = _run_stats(cfg2, seed, blind(), T)
    s4, _ = _run_stats(cfg2, seed, blind(), T, fix4=e_mean)
    assert s0["b5"] < -0.03
    _same(s0, s4)                                                             # 관측 4 를 안 보므로 같은 궤적

    def hungry():                                                             # 결정마다 독립: 배고프면 0.3, 아니면 0.02
        rng = np.random.default_rng(seed)
        return lambda obs: _act(len(obs), speed=0.5,
                                vig=(rng.random(len(obs)) < np.where(obs[:, 4] < 0.5, 0.3, 0.02)).astype(float))
    h0, e_mean = _run_stats(cfg2, seed, hungry(), T)
    h4, _ = _run_stats(cfg2, seed, hungry(), T, fix4=e_mean)
    assert h0["b5"] < -0.2 and abs(h4["b5"]) < 0.05
    assert h0["b5"] - h4["b5"] < -0.2


def test_gait_stats_exclude_vigilant_agents_from_b1_b2_and_stall(cfg2):
    """경계는 속력 0 이라 실제 보행 '정지'로 센다. 그러나 B1 의 뛰기·B2 의 '경계가 아닌 정지'·stall 에서는 뺀다(6.2).
    명령 보행 비율은 경계와 무관한 speed 명령이다."""
    w = World(cfg2, seeds=[10000])
    for _ in range(200):
        w.step(_act(w.N, speed=1.0, vig=0.9))                       # 모두 뛰기 명령 + 경계
    s = w.gait_stats()
    assert s["stop_frac"] == 1.0 and s["run_frac_cmd"] == 1.0 and s["stall_frac"] == 0.0
    assert s["p_run_unseen"] == 0.0 and s["p_stop_full"] == 0.0
    for k in ("b1", "p_run_d025", "p_run_d050", "p_run_d100", "p_stop_hungry"):
        assert s[k] == 0.0 or math.isnan(s[k]), k
    w = World(cfg2, seeds=[10000])
    for _ in range(200):
        w.step(_act(w.N, speed=0.0, vig=0.2))                       # 경계 없이 정지
    s = w.gait_stats()
    assert s["p_stop_full"] == 1.0 and w.vigil_stats()["vig_frac"] == 0.0


# --------------------------------------------------------------------- #
# 관측 8 · 행동 6 이 VecEnv · 학습 · 진단 · 영상 도구를 통과한다 (smoke)
# --------------------------------------------------------------------- #


def test_vec_env_spaces_follow_config(cfg2):
    venv = MultiWorldVecEnv(cfg2, num_worlds=2, meta_seed=0)
    assert venv.action_space.shape == (6,) and venv.observation_space.shape == (8,)
    assert venv.act_names == NAMES6 and venv.obs_names == OBS8 and venv.obs_dim == 8
    a = np.zeros((venv.num_envs, 6), dtype=np.float32)
    a[:, ACT_VIG] = 3.0                                              # sigmoid(3) > 0.5 → 경계
    obs, rew, done, _ = venv.step(a)
    assert obs.shape == (venv.num_envs, 8)
    assert all(w.vigilant.all() for w in venv.worlds)
    assert MultiWorldVecEnv(load_v2_config(V2_1), num_worlds=1).observation_space.shape == (7,)


def test_rollout_rows_carry_vigilance_columns(cfg2):
    r = ro.rollout(cfg2, ro.build_policy({"kind": "fixed", "action": BASE4 + [0.5, 0.2]}), 10000, 30, tail=0,
                   record_every=10)
    assert set(ro.VIGIL_COLUMNS) <= set(r) and set(ro.GAIT_COLUMNS) <= set(r)
    assert r["_obs"].shape == (3 * 128, 8) and r["_act"].shape == (3 * 128, 6) and r["_obs_sum"].shape == (8,)
    r1 = ro.rollout(load_v2_config(V2_1), ro.build_policy({"kind": "fixed", "action": BASE4 + [0.5]}), 10000, 5,
                    tail=0)
    assert not set(ro.VIGIL_COLUMNS) & set(r1)


def test_vig_probs_matches_sampling():
    """시작 분포 계산(가우시안 → [-3,3] 자르기 → sigmoid → 문턱 0.5)이 표본과 같다. μ −0.84·σ 1 이면 약 20%."""
    from train_v2 import vig_probs

    assert vig_probs([-0.84], [1.0], 0.5)[0] == pytest.approx(0.5 * math.erfc(0.84 / math.sqrt(2.0)), abs=1e-12)
    assert vig_probs([-0.84], [1.0], 0.5)[0] == pytest.approx(0.2005, abs=1e-4)
    rng = np.random.default_rng(0)
    for mu, sd in ((-0.84, 1.0), (0.0, 1.0), (2.0, 0.5), (-3.5, 2.0)):
        raw = np.clip(mu + sd * rng.standard_normal(200_000), -3.0, 3.0)
        emp = (1.0 / (1.0 + np.exp(-raw)) > 0.5).mean()
        assert vig_probs([mu], [sd], 0.5)[0] == pytest.approx(emp, abs=5e-3)


def test_init_action_bias_is_validated(cfg2):
    from train_v2 import init_action_bias

    assert init_action_bias(cfg2, NAMES6) == {"vigilance": -0.84}
    assert init_action_bias(load_v2_config(V2_1), NAMES6[:5]) == {}               # 없으면 기존과 같다
    for bad in ({"vigilence": -0.84}, {"vigilance": "x"}, {"vigilance": True}, [-0.84]):
        cfg = cfg2.replace(v2=dict(cfg2.v2, train=dict(cfg2.v2["train"], init_action_bias=bad)))
        with pytest.raises(SystemExit):
            init_action_bias(cfg, NAMES6)
    with pytest.raises(SystemExit):
        init_action_bias(cfg2, NAMES6[:5])                       # vigilance 가 없는 세계


TINY = {"version": "2.2", "overrides": {"rand": {"pred_speed_mult": [0.6, 0.95]}},
        "train": {"num_worlds": 1, "reset_interval": 4000, "rollout_world_steps": 8,
                  "init_action_bias": {"vigilance": -0.84}}}


@pytest.fixture(scope="module")
def tiny_vig_model(tmp_path_factory):
    """v2_2.yaml 의 기능 블록 그대로, 세계 1개 × 롤아웃 8스텝으로 1회 학습한 모델과 그 설정."""
    import train_v2

    d = tmp_path_factory.mktemp("vig_model")
    raw = yaml.safe_load(V2_2.read_text(encoding="utf-8"))
    cfg_path = d / "tiny_v2_2.yaml"
    cfg_path.write_text(yaml.safe_dump(dict(TINY, features=raw["features"]), allow_unicode=True), encoding="utf-8")
    out = d / "m.zip"
    assert train_v2.main(["--steps", "1", "--seed", "0", "--config", str(cfg_path), "--out", str(out),
                          "--tb", str(d / "tb"), "--threads", "1"]) == 0
    return cfg_path, out


def test_train_v2_learns_six_actions_from_eight_obs_with_vigilance_bias(tiny_vig_model):
    """정책 입력 8·출력 6. 학습 전 vigilance 편향 −0.84(설정), log_std 0 → 경계 약 20%. speed 편향은 0 그대로."""
    import torch
    from stable_baselines3 import PPO

    _, out = tiny_vig_model
    m = PPO.load(out, device="cpu")
    assert m.action_space.shape == (6,) and m.observation_space.shape == (8,)
    assert m.policy.action_net.out_features == 6
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["act_names"] == list(NAMES6) and meta["obs_names"] == list(OBS8) and meta["v2"]["version"] == "2.2"
    assert meta["init_action_bias"] == {"vigilance": -0.84}
    ip = meta["init_policy"]
    assert ip["action_bias"][ACT_VIG] == pytest.approx(float(torch.tensor(-0.84)), abs=0)
    assert ip["action_bias"][ACT_SPEED] == 0.0 and ip["log_std"][ACT_VIG] == 0.0
    assert ip["vigilance"]["vig_prob"] == pytest.approx(0.2005, abs=0.01)
    walk = math.erf(math.log(2.0) / math.sqrt(2.0))
    assert ip["speed"]["gait_prob"]["walk"] == pytest.approx(walk, abs=0.01)


def test_diagnose_handles_eight_obs_and_six_actions(tiny_vig_model, tmp_path, monkeypatch):
    """ablate(C3-vigilance 포함), permute(C4-threat_recency 고정·순열), constsearch C2-seg(구간 = 보임 × 최근 위협,
    vigilance 만 구간별), r2·curves 가 관측 8·행동 6 으로 돈다. 결과에 경계 지표와 관측 이름이 남는다."""
    import diagnose_v2 as dg

    monkeypatch.setattr(dg, "CACHE", tmp_path / "cache")
    _, model = tiny_vig_model
    common = ["--config", str(V2_2), "--eval-seeds", "10000", "10001", "--eval-steps", "40", "--tail", "0",
              "--calib-seeds", "0", "--calib-steps", "30", "--workers", "1"]
    out = str(tmp_path / "abl")
    assert dg.main(["ablate", "--model", str(model), "--out", out] + common) == 0
    d = json.loads((tmp_path / "abl" / "ablate.json").read_text(encoding="utf-8"))
    assert d["meta"]["act_names"] == list(NAMES6) and d["meta"]["obs_names"] == list(OBS8)
    assert "C3-vigilance" in d["per_seed"] and "Utility" not in d["per_seed"]
    assert {"vig_frac", "b3", "b4", "b5", "b5p_ema", "b3_narrow", "b3_truth", "b4_narrow", "b5p_pred_narrow",
            "b5p_truth"} <= set(d["controls"]["C0"]["mean"])
    assert "threat_recency" in d["calib"]["obs_mean"] and "vigilance" in d["calib"]["mean_action"]
    md = (tmp_path / "abl" / "ablate.md").read_text(encoding="utf-8")
    assert "경계 지표" in md and "B4 (120° 결정)" in md and "B5′ 포식자 (반경 기준)" in md

    assert dg.main(["permute", "--model", str(model), "--out", out, "--obs", "threat_recency"] + common) == 0
    pm = json.loads((tmp_path / "abl" / "permute.json").read_text(encoding="utf-8"))
    assert {"C4-threat_recency-fix", "C4-threat_recency-perm"} <= set(pm["per_seed"])
    assert pm["controls"]["C4-threat_recency-fix"]["spec"]["wrap"][0]["dims"] == [OBS_THREAT_RECENCY]

    assert dg.main(["constsearch", "--model", str(model), "--out", out, "--seg-bins", "pred_dist:1.0",
                    "threat_recency:0.5", "--seg-dims", "vigilance", "--base-action", "0.4", "0.8", "0.4", "0.1",
                    "0.5", "0.2", "--const-action", "0.2", "0.9", "0.2", "0.2"] + common) == 0
    seg = json.loads((tmp_path / "abl" / "constsearch_seg.json").read_text(encoding="utf-8"))
    assert seg["dims"] == [ACT_VIG] and seg["bins"] == [[2, [1.0]], [7, [0.5]]]
    assert seg["segments"][1].endswith("threat_recency≥0.5") and "vig_frac" in seg["eval"]["mean"]

    assert dg.main(["r2", "--model", str(model), "--out", out] + common) == 0
    r2 = json.loads((tmp_path / "abl" / "r2.json").read_text(encoding="utf-8"))
    assert len(r2["r2"]["C0"]) == 6 and "관측 8" in (tmp_path / "abl" / "r2.md").read_text(encoding="utf-8")
    assert dg.main(["curves", "--model", str(model), "--out", out] + common) == 0
    cv = json.loads((tmp_path / "abl" / "curves.json").read_text(encoding="utf-8"))
    assert list(cv["conditional"]) == list(OBS8) and "## threat_recency" in (
        tmp_path / "abl" / "curves.md").read_text(encoding="utf-8")

    P = dg.build_parser()
    with pytest.raises(SystemExit):
        dg.Ctx(P.parse_args(["ablate", "--policy", "fixed", "--action"] + ["0.5"] * 5 + ["--config", str(V2_2)]))
    with pytest.raises(SystemExit):
        dg.parse_bins(["9:0.5"], OBS8)
    assert dg.parse_bins(["threat_recency:0.5"], OBS8) == [[7, [0.5]]]


def test_wrappers_and_stochastic_mode_keep_six_actions(tiny_vig_model):
    """C3-vigilance(행동 고정)·C1′(순열)·C4-threat(관측 고정)·확률 모드가 행동 6개·관측 8개를 그대로 쓴다."""
    _, model = tiny_vig_model
    obs = np.random.default_rng(0).random((128, 8)).astype(np.float32)
    learned = {"kind": "learned", "model": str(model)}
    fix = ro.build_policy({"policy": learned, "wrap": [{"kind": "act_fix", "dims": [ACT_VIG],
                                                        "values": [0, 0, 0, 0, 0, 0.9]}]})
    a = fix(obs)
    assert a.shape == (128, 6) and (a[:, ACT_VIG] == 0.9).all()
    perm = ro.build_policy({"policy": learned, "wrap": [{"kind": "act_permute"}]}, seed=3)(obs)
    base = ro.build_policy(learned)(obs)
    np.testing.assert_allclose(np.sort(perm, 0), np.sort(base, 0))
    o_fix = ro.build_policy({"policy": learned, "wrap": [{"kind": "obs_fix", "dims": [7], "values": [0.0]}]})(obs)
    o2 = obs.copy()
    o2[:, 7] = 0.0
    np.testing.assert_array_equal(o_fix, ro.build_policy(learned)(o2))
    sto = {**learned, "mode": "stochastic"}
    s1, s2 = ro.build_policy(sto, seed=10000)(obs), ro.build_policy(sto, seed=10000)(obs)
    assert s1.shape == (128, 6) and ((0 < s1) & (s1 < 1)).all()
    np.testing.assert_array_equal(s1, s2)


def test_replay_draws_vigilance_for_six_actions(cfg2, tmp_path, capsys):
    """영상: 경계 훅(vigilant·gaze)을 읽어 흰 테두리·시선선을 그리고 vigilance 설명줄을 단다. 경계 개체의 점 색은 정지.
    fixed 6개·random 은 세계에 맞추고 5개는 멈춘다."""
    import replay_v2 as R

    rand = dict(cfg2.rand, world_size=[30.0, 30.0], predator_count=[2, 2])
    cfg = cfg2.replace(N=16, rand=rand)
    spec = R.fit_spec(R.parse_spec("fixed:0.4,0.8,0.4,0.1,0.9,0.9"), 6, NAMES6)
    run = R.run_policy(cfg, spec, 10000, steps=6, stride=2)
    assert all(f["vig"] is not None and np.asarray(f["vig"]).all() for f in run.frames)
    assert all((f["gait"] == GAIT_STOP).all() for f in run.frames)
    assert all(f["gaze"].shape == (16, 2) for f in run.frames)
    line = R.vigil_line([run])
    assert "vigilance 문턱 > 0.5" in line and "360°" in line and "감쇠 0.95" in line
    assert R.vigil_line([R.Run("v2.1", World(load_v2_config(V2_1), seeds=[0]))]) is None
    assert R.fit_spec(R.parse_spec("random:3"), 6) == {"kind": "random", "seed": 3, "act_dim": 6}
    with pytest.raises(ValueError):
        R.fit_spec(R.parse_spec("fixed:0.4,0.8,0.4,0.1,0.5"), 6, NAMES6)
    fig, update, n, panels = R.build_figure([run], fps=10, dpi=30)
    update(n - 1)
    assert len(panels[0].gaze.get_segments()) == 16                 # 모든 개체가 경계라 시선선 16개
    import matplotlib.pyplot as plt
    plt.close(fig)
    out = tmp_path / "v.gif"
    assert R.main(["--config", str(V2_2), "--policy", "fixed:0.4,0.8,0.4,0.1,0.5,0.7", "--steps", "6",
                   "--stride", "2", "--dpi", "30", "--fps", "10", "--out", str(out)]) == 0
    assert out.exists() and "경계=1.0000" in capsys.readouterr().out


# --------------------------------------------------------------------- #
# threat_flee (10-03, 1-5 Gate E2b 의 10절 #18 변형 팔. configs/v2_2.yaml 은 0 = 끔)
# --------------------------------------------------------------------- #


def test_steer_extra_none_or_zero_is_bitwise_v1_line(cfg2):
    """steer(extra=None) 와 0 행렬을 더한 값은 extra 없는 조향과 비트 단위로 같다(계약 조향 그대로)."""
    w = World(cfg2, seeds=[10000])
    a = _act(w.N, speed=0.5)
    v0 = steer(w._g, a, cfg2)
    np.testing.assert_array_equal(steer(w._g, a, cfg2, None), v0)
    np.testing.assert_array_equal(steer(w._g, a, cfg2, np.zeros((w.N, 2))), v0)


def test_threat_flee_zero_never_builds_the_term(cfg2, monkeypatch):
    """configs/v2_2.yaml 의 threat_flee 는 0 이고, 0 이면 항을 만들지 않는다(steer 에 None — 1-4 구현 그대로)."""
    assert cfg2.v2["features"]["vigilance"]["threat_flee"] == 0.0 and World(cfg2, seeds=[0])._vg["threat_flee"] == 0.0
    calls = []
    monkeypatch.setattr(World, "_threat_flee_term", lambda self: calls.append(1) or np.zeros((self.N, 2)))
    w = World(cfg2, seeds=[10000])
    for t in range(40):
        w.step(_act(w.N, speed=0.9, vig=float(t % 3 == 0)))
    assert calls == [] and w.threat_dir.any()


def test_threat_flee_is_checked(cfg2):
    with pytest.raises(ValueError, match="threat_flee"):
        World(_features(cfg2, vigilance={"threat_flee": -0.1}), seeds=[0])
    with pytest.raises(ValueError, match="threat_flee"):
        F.parse_features({"vigilance": {k: v for k, v in cfg2.v2["features"]["vigilance"].items()
                                        if k != "threat_flee"}})


def test_threat_flee_term_definition(cfg2):
    """항 = threat_flee·flee_weight·threat_recency·(−ThreatDir), 결정 관측에서 포식자가 안 보인 개체만. 보인 개체와
    위협을 본 적 없는 개체(ThreatDir 0)는 0."""
    for tf in (1.0, 0.5):
        w = World(_features(cfg2, vigilance={"threat_flee": tf}), seeds=[10000])
        w.threat[:] = 0.0
        w.threat_dir[:] = 0.0
        w.threat[0], w.threat_dir[0] = 0.6, (0.0, 1.0)          # 안 보임, 최근 위협
        w.threat[1], w.threat_dir[1] = 1.0, (1.0, 0.0)          # 보임 → 0 (v1 도주 항이 맡는다)
        w.threat[2] = 0.3                                       # 본 적 없음 → 0
        pc = np.zeros(w.N, dtype=np.int64)
        pc[1] = 2
        w._g = dict(w._g, pred_count=pc)
        t = w._threat_flee_term()
        np.testing.assert_allclose(t[0], [0.0, -tf * cfg2.flee_weight * 0.6], atol=1e-15)
        assert not t[1:].any()


@pytest.mark.parametrize("tf", [0.0, 1.0])
def test_threat_flee_moves_isolated_agent_away_from_last_threat(cfg2, tf):
    """조향 가중 0·이웃 없음·포식자 안 보임이면 v1 조향 합이 0 이라 정지한다(방향 없음). threat_flee 1 이면 −ThreatDir
    쪽으로 뛴다(뛰기 명령, 속력 herb_speed)."""
    w = World(_features(cfg2, vigilance={"threat_flee": tf}), seeds=[10000])
    _set_predators(w, [[-500.0, -500.0]])                       # 아무도 못 본다
    c = np.array([w.size / 2, w.size / 2])
    w.pos[:] = 1.0                                              # 나머지는 구석에 모은다(0 번 근처에 이웃 없음)
    w.pos[0] = c
    w.threat[0], w.threat_dir[0] = 0.6, (0.0, 1.0)
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)
    assert w._g["pred_count"][0] == 0
    w.step(_act(w.N, speed=1.0, vig=0.0, base=[0.0, 0.0, 0.0, 0.0]))
    if tf:
        np.testing.assert_allclose(w.pos[0], c + [0.0, -cfg2.herb_speed], atol=1e-12)
        assert w.gait[0] == GAIT_RUN
    else:
        np.testing.assert_array_equal(w.pos[0], c)
        assert w.gait[0] == GAIT_STOP
