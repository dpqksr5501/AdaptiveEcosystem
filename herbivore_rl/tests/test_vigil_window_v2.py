"""V2 v2.2r — 경계 재설계 스위치 vigil_window (수정 제안서 3.1 (나)·3.8, 10-03 R2).

탐색 팔 설정(configs/v2_2r_t1.yaml·v2_2r_l.yaml·v2_2r_w.yaml)이 v2.2 세계에서 정한 곳만 바꾸는지, 계수 검사,
경계 행동 열을 뺀 T1 = v2.2 에서 경계를 한 번도 하지 않은 세계(비트 동일), 정지하지 않는 L = T1, 경계를 쓰지 않는 W′ = T1,
W′ 의 창 밖 경계는 효력이 없음(비트 동일), L 반사 돌아보기의 조건(창 안 & 실제 정지 & ThreatDir ≠ 0)과 섭식·시야,
W′ 창 경계의 계수, window_stats 의 정의(직접 다시 센 값과 같음)를 고정한다. 기능을 끈 v2.2 의 config_digest 가 그대로인지도 본다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import math

import numpy as np
import pytest

import env_v2.features as F
from env.config import ROOT
from env_v2.config import load_v2_config
from env_v2.steering import normalize
from env_v2.world import (ACT_SPEED, GAIT_STOP, HUNGRY, WINDOW_STAT_COLUMNS, World, action_names, obs_names)

V2_2 = ROOT / "configs" / "v2_2.yaml"
T1 = ROOT / "configs" / "v2_2r_t1.yaml"
L = ROOT / "configs" / "v2_2r_l.yaml"
W = ROOT / "configs" / "v2_2r_w.yaml"
NAMES5 = ("forage", "cohesion", "flee_dist", "cover", "speed")
NAMES6 = NAMES5 + ("vigilance",)
STEPS = 300


@pytest.fixture(scope="module")
def cfgs():
    return {k: load_v2_config(p) for k, p in (("v22", V2_2), ("t1", T1), ("l", L), ("w", W))}


def _features(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _actions(seed=7, steps=STEPS, n=128):
    """스텝마다 (n, 6) 무작위 행동. 5열 세계는 앞 5열만 쓴다."""
    return np.random.default_rng(seed).random((steps, n, 6))


def _run(cfg, act, seed=12000, cols=None, fix=None):
    """`act[t]` 를 넣어 돌린다. `fix(t, a, w)` 가 있으면 넣기 전에 행동을 바꾼다. 관측·보상·사망·통계를 돌려준다."""
    w = World(cfg, seeds=[seed])
    cols = w.act_dim if cols is None else cols
    O, R, D = [], [], []
    for t in range(len(act)):
        a = act[t][:, :cols].copy()
        if fix is not None:
            a = fix(t, a, w)
        o, r, d, _ = w.step(a)
        O.append(o.copy())
        R.append(r.copy())
        D.append(d.copy())
    return w, np.array(O), np.array(R), np.array(D)


def _same_run(x, y):
    for a, b in zip(x[1:], y[1:]):
        np.testing.assert_array_equal(a, b)
    s1, s2 = x[0].stats(), y[0].stats()
    assert s1.keys() == s2.keys()
    for k in s1:
        assert s1[k] == s2[k] or (math.isnan(s1[k]) and math.isnan(s2[k])), k


# --------------------------------------------------------------------- #
# 설정·계수
# --------------------------------------------------------------------- #


def test_arm_configs_change_only_the_planned_keys(cfgs):
    """세 팔은 v2_2.yaml 의 v1 키·speed 블록·decay·threat_flee 그대로다. T1·L 은 경계 행동 열이 없고(행동 5),
    W′ 는 경계 계수만 L 형(섭식 1.0, 120°)이다. 관측은 모두 8 이다. 기능 번호 13 은 고정이다."""
    c22 = cfgs["v22"]
    assert F.FEATURE_IDS["vigil_window"] == 13 and "vigil_window" in F.IMPLEMENTED
    for key in ("t1", "l", "w"):
        c = cfgs[key]
        for k, v in c22.to_dict().items():
            if k != "v2":
                assert getattr(c, k) == v, (key, k)
        f = c.v2["features"]
        assert f["speed"] == c22.v2["features"]["speed"]
        for k in ("enabled", "threshold", "decay", "threat_flee"):
            assert f["vigilance"][k] == c22.v2["features"]["vigilance"][k], (key, k)
        assert set(f["vigil_window"]) == {"enabled"} | set(F.PARAM_KEYS["vigil_window"])
        assert f["vigil_window"]["theta"] == 0.5
        w = World(c, seeds=[0])
        assert w.features.active == ("speed", "vigilance", "vigil_window")
        assert w.obs_names == obs_names(c22) and w.obs_dim == 8
    assert action_names(cfgs["t1"]) == action_names(cfgs["l"]) == NAMES5
    assert action_names(cfgs["w"]) == NAMES6
    assert cfgs["t1"].v2["features"]["vigil_window"] == {"enabled": True, "action": False, "window_only": False,
                                                        "look_back": False, "theta": 0.5}
    assert cfgs["l"].v2["features"]["vigil_window"]["look_back"] is True
    vw = cfgs["w"].v2["features"]["vigil_window"]
    assert vw["action"] is True and vw["window_only"] is True and vw["look_back"] is False
    vg = cfgs["w"].v2["features"]["vigilance"]
    assert vg["eat_mult"] == 1.0 and vg["fov_deg"] == 120.0 == cfgs["w"].fov_deg
    assert cfgs["w"].v2["train"]["init_action_bias"] == {"vigilance": 0.0}
    assert "init_action_bias" not in cfgs["t1"].v2["train"] and "init_action_bias" not in cfgs["l"].v2["train"]


def test_v2_2_digest_is_unchanged():
    """vigil_window 는 새 기능 번호라 vigilance 계수 키를 늘리지 않는다 — v2_2.yaml 과 기록된 결과의 digest 그대로."""
    from diagnose_v2 import config_digest

    assert config_digest(load_v2_config(V2_2)) == "efc8f775f1e1"


@pytest.mark.parametrize("blocks, match", [
    ({"vigilance": {"enabled": False}}, "vigilance 를 함께"),
    ({"vigil_window": {"action": False, "window_only": True}}, "window_only"),
    ({"speed": {"enabled": False}, "vigil_window": {"look_back": True}}, "speed 를 함께"),
    ({"vigil_window": {"theta": 1.0}}, "theta"),
    ({"vigil_window": {"theta": -0.1}}, "theta"),
    ({"vigil_window": {"action": 1}}, "true/false"),
    ({"vigil_window": {"look_back": "yes"}}, "true/false"),
])
def test_window_params_rejected(cfgs, blocks, match):
    with pytest.raises(ValueError, match=match):
        World(_features(cfgs["l"], **blocks), seeds=[0])


# --------------------------------------------------------------------- #
# 끈 것과 같음 (비트 동일)
# --------------------------------------------------------------------- #


def test_t1_is_v2_2_that_never_turns_vigilant(cfgs):
    """T1(경계 행동 열 없음) = v2.2 에 경계 0 을 넣은 세계. 관측 8(threat_recency)·보상·사망·통계가 같다."""
    act = _actions()

    def no_vig(t, a, w):
        a[:, 5] = 0.0
        return a

    x = _run(cfgs["t1"], act)
    y = _run(cfgs["v22"], act, fix=no_vig)
    _same_run(x, y)
    assert x[0].vigil_stats().keys() == y[0].vigil_stats().keys()
    assert x[0].vigil_stats()["vig_frac"] == 0.0


def test_l_without_stopping_is_t1(cfgs):
    """L 에서 정지하지 않으면(speed ≥ 1/3) 반사가 돌지 않아 T1 과 같다."""
    act = _actions()

    def walk(t, a, w):
        a[:, ACT_SPEED] = 0.5
        return a

    x = _run(cfgs["l"], act, fix=walk)
    y = _run(cfgs["t1"], act, fix=walk)
    _same_run(x, y)
    assert x[0].window_stats()["look_frac"] == 0.0


def test_w_without_vigilance_is_t1(cfgs):
    """W′ 에서 경계를 쓰지 않으면(a_vig 0) 경계 계수(섭식 1.0·120°)가 쓰이지 않아 T1 과 같다."""
    act = _actions()

    def no_vig(t, a, w):
        a[:, 5] = 0.0
        return a

    _same_run(_run(cfgs["w"], act, fix=no_vig), _run(cfgs["t1"], act))


def test_w_vigilance_outside_window_has_no_effect(cfgs):
    """W′: 어디서나 a_vig = 1 인 정책 = 결정 때 창 안에서만 a_vig = 1 인 정책 (비트 동일). 창 밖 경계 비율은 0 이다."""
    act = _actions()

    def always(t, a, w):
        a[:, 5] = 1.0
        return a

    def window_only(t, a, w):
        win = (w._g["pred_count"] == 0) & (w.threat > w._vw["theta"])
        a[:, 5] = win.astype(np.float64)
        return a

    x = _run(cfgs["w"], act, fix=always)
    _same_run(x, _run(cfgs["w"], act, fix=window_only))
    ws = x[0].window_stats()
    assert ws["p_vig_calm"] == 0.0 and ws["p_vig_win"] == 1.0 and ws["win_frac"] > 0.0


# --------------------------------------------------------------------- #
# 반사 돌아보기 (L)·창 경계 (W′)
# --------------------------------------------------------------------- #


def _crafted(cfg, seed=12000):
    """포식자 없는 세계(모두 안 보임). 개체 0~63 은 창 안(threat 0.8), 64~127 은 평시(threat 0.3), 모두 ThreatDir 를
    개체마다 다른 단위벡터로 둔다. 개체 0~31·64~95 는 정지, 나머지는 걷기 명령."""
    w = World(cfg, seeds=[seed])
    w.M = 0
    for k in ("pred_pos", "pred_head"):
        setattr(w, k, np.zeros((0, 2)))
    for k in ("pred_speed", "pred_catch_r"):
        setattr(w, k, np.zeros(0))
    w.pred_ranged = np.zeros(0, dtype=bool)
    w.pred_cd = np.zeros(0, dtype=np.int32)
    w._g = w._geometry()
    N = w.N
    ang = np.linspace(0.0, 2.0 * np.pi, N, endpoint=False) + 0.3
    w.threat[:] = np.where(np.arange(N) < N // 2, 0.8, 0.3)
    w.threat_dir[:] = np.stack([np.cos(ang), np.sin(ang)], 1)
    w._obs = w._obs_from(w._g)
    a = np.empty((N, w.act_dim))
    a[:, :4] = [0.4, 0.8, 0.4, 0.1]
    a[:, ACT_SPEED] = np.where((np.arange(N) % 64) < 32, 0.1, 0.5)
    stop_cmd = a[:, ACT_SPEED] < 1.0 / 3.0
    return w, a, stop_cmd


def test_look_back_turns_stopped_agents_in_window_only(cfgs):
    """L 반사: 결정 때 창 안 & 실제 정지 & ThreatDir ≠ 0 → 스텝 끝 heading = ThreatDir. 창 밖 정지·창 안 이동은 그대로다.
    섭식은 정지 섭식(gait_eat[정지] = 1), 다음 관측 시야는 기본 FOV 다(경계가 아니다)."""
    w, a, stop_cmd = _crafted(cfgs["l"])
    head0 = w.head.copy()
    win0 = (w._g["pred_count"] == 0) & (w.threat > 0.5)
    w.step(a)
    stopped = w.gait == GAIT_STOP
    assert (stopped == stop_cmd).all()
    face = win0 & stopped
    np.testing.assert_array_equal(w.looked, face)
    np.testing.assert_array_equal(w.head[face], w.threat_dir[face])
    np.testing.assert_array_equal(w.head[~win0 & stopped], head0[~win0 & stopped])
    moving = ~stopped
    np.testing.assert_allclose(w.head[moving], normalize(w.vel[moving]))
    assert not w.vigilant.any() and not w._wide.any()
    eat = w._drain_eat()[1]
    np.testing.assert_array_equal(eat[stopped], 1.0)


def test_look_back_needs_a_threat_direction(cfgs):
    """ThreatDir = 0(위협을 본 적 없음)이면 창 안 정지여도 heading 을 바꾸지 않는다."""
    w, a, _ = _crafted(cfgs["l"])
    w.threat_dir[:] = 0.0
    head0 = w.head.copy()
    a[:, ACT_SPEED] = 0.0
    w.step(a)
    assert not w.looked.any()
    np.testing.assert_array_equal(w.head, head0)


def test_t1_has_no_reflex(cfgs):
    w, a, _ = _crafted(cfgs["t1"])
    head0 = w.head.copy()
    a[:, ACT_SPEED] = 0.0
    w.step(a)
    assert not w.looked.any()
    np.testing.assert_array_equal(w.head, head0)


def test_w_window_vigilance_uses_l_type_coefficients(cfgs):
    """W′ 창 경계: 창 안 & a_vig > 0.5 → 정지·섭식 eat_mult(1.0)·heading = ThreatDir. 창 밖은 speed 그대로·경계 아님.
    시야 120° 라 다음 관측 기하는 기본 시야와 같다."""
    w, a, _ = _crafted(cfgs["w"])
    a[:, ACT_SPEED] = 0.9                                   # 모두 뛰기 명령
    a[:, 5] = 1.0                                           # 모두 경계 명령
    win0 = (w._g["pred_count"] == 0) & (w.threat > 0.5)
    w.step(a)
    np.testing.assert_array_equal(w.vigilant, win0)
    assert (w.gait[win0] == GAIT_STOP).all() and (w.gait[~win0] != GAIT_STOP).all()
    np.testing.assert_array_equal(w.head[win0], w.threat_dir[win0])
    np.testing.assert_array_equal(w._drain_eat()[1][win0], 1.0)
    assert w._vg["wide_cos"] == pytest.approx(w.cfg.fov_cos)


# --------------------------------------------------------------------- #
# 창 지표
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("key", ["l", "w", "t1"])
def test_window_stats_match_a_direct_recount(cfgs, key):
    """window_stats = 결정 때 구간(보임·창·평시)·배부름과 이번 스텝의 실제 정지·경계를 직접 센 값."""
    act = _actions(seed=11)
    w = World(cfgs[key], seeds=[12001])
    H = np.zeros((3, 2, 2, 2), dtype=np.int64)
    look = 0
    for t in range(STEPS):
        seen = w._g["pred_count"] > 0
        win = ~seen & (w.threat > 0.5)
        full = w.energy >= HUNGRY * w.cfg.max_energy
        w.step(act[t][:, :w.act_dim])
        seg = np.where(seen, 2, win.astype(int))
        np.add.at(H, (seg, full.astype(int), (w.gait == GAIT_STOP).astype(int), w.vigilant.astype(int)), 1)
        look += int(w.looked.sum())
    s = w.window_stats()
    assert tuple(s) == WINDOW_STAT_COLUMNS
    n_win_full = H[1, 1].sum()
    assert s["p_stop_win_full"] == H[1, 1, 1].sum() / n_win_full
    assert s["p_stop_calm_full"] == H[0, 1, 1].sum() / H[0, 1].sum()
    assert s["b3_l"] == s["p_stop_win_full"] - s["p_stop_calm_full"]
    assert s["win_frac"] == H[1].sum() / H.sum()
    assert s["p_vig_win"] == H[1, :, :, 1].sum() / H[1].sum()
    assert s["look_frac"] == look / H.sum()
    assert s["look_win_frac"] <= s["p_stop_win"]
    if key == "t1":
        assert s["look_frac"] == 0.0 and s["p_vig_win"] == 0.0
    if key == "l":
        assert s["look_frac"] > 0.0
    if key == "w":
        assert s["p_vig_calm"] == 0.0 and s["p_vig_win"] > 0.0


def test_window_world_is_deterministic_and_uses_no_rng(cfgs):
    """같은 시드·같은 행동이면 같은 결과이고, 기능 스트림을 만들지 않는다(반사·창은 난수를 쓰지 않는다)."""
    act = _actions(seed=3, steps=120)
    x = _run(cfgs["l"], act)
    y = _run(cfgs["l"], act)
    _same_run(x, y)
    assert x[0]._feature_rngs == {}
