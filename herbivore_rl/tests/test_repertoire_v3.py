"""v3 R0 — 행동 레퍼토리(repertoire, 기능 15)와 위협 유형(threats, 기능 16) (명세 Docs/RL_Policy/RL_V3_R0_SPEC.md,
사전 등록 results/v3/r0/PREREG.md).

설정(v3_r0 = v2_4s + 두 블록, _on 은 낮 고정 비율만 0), 계수 검사, 두 기능을 끄면 v2.4s 와 비트 동일(잠행형·플레이어가 없는
threats 도 포식자 동역학이 같다), 행동 실행기(잠금·사건·결정 지연·놀람·잠 진입/기상·숨기 도착/웅크림·정지 표시), 제어기,
세계 장치(M1 정지 탐지·M5 고개 숙임·M6 상태별 은신 배수·포획은 은신 배수만·SLEEP 전용 휴식 할인), 잠행-돌진 상태 기계,
플레이어(밤에 자지 않음·초식 관측에 보임·모드 순환), 자기 스트림만 씀, 결정성·복제, 통계·롤아웃 열, 추가 관측, 손 규칙,
침입 도구 smoke, 리플레이 훅.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import importlib.util
import json
import math
import pickle

import numpy as np
import pytest
import yaml

import repertoire_rules as rr
from env.config import ROOT
from env_v2 import repertoire as rep
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.features import feature_stream
from env_v2.world import (GAIT_RUN, GAIT_STOP, GAIT_WALK, PM_CHARGE, PM_REST, PM_STALK, PM_WANDER, PT_CHASER,
                          PT_PLAYER, PT_STALKER, REP_STAT_COLUMNS, ST_EXHAUST, ST_POUNCE, ST_ROAM, THREAT_STAT_COLUMNS,
                          World, obs_names)

V2_4S = ROOT / "configs" / "v2_4s.yaml"
V2_4S_ON = ROOT / "configs" / "v2_4s_on.yaml"
V3 = ROOT / "configs" / "v3_r0.yaml"
V3_ON = ROOT / "configs" / "v3_r0_on.yaml"
C2 = [0.97099, 0.78494, 0.21823, 0.03359, 0.49137]
G, F, H, Z, S = rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def cfg3():
    return load_v2_config(V3_ON)


@pytest.fixture(scope="module")
def P(cfg3):
    return World(cfg3, seeds=[12000])._rp


def _feat(cfg, name, **kw):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    f[name] = dict(f[name], **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _rule5(obs):
    a = np.tile([0.4, 0.8, 0.4, 0.1, 0.5], (len(obs), 1))
    a[obs[:, 4] < 0.5, 4] = 0.0
    a[obs[:, 2] < 0.5, 4] = 1.0
    return a


def _same(d1, d2):
    assert d1.keys() == d2.keys()
    for k in d1:
        a, b = d1[k], d2[k]
        assert a == b or (isinstance(a, float) and math.isnan(a) and math.isnan(b)), k


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #

REP_BLOCK = dict(enabled=True, lock_graze=12, lock_flee=8, lock_freeze=12, lock_hide=12, hide_travel_max=40,
                 sleep_enter=3, sleep_hold=60, sleep_wake=3, startle_steps=3, c_still=1.8, cover_mult_crouch=2.5,
                 cover_mult_graze=1.5, cover_mult_sleep=2.5, cover_mult_other=1.0, graze_head_down=0.6, sleep_sight=0.3, sleep_rest=0.6, graze_eat_min=0.06,
                 graze_forage=0.83, graze_cohesion=0.71, event_near=8.0, event_approach=0.9, event_energy=0.25,
                 event_dark=0.5, decision_jitter=3, recency_decay=0.95, steps_norm=60, obs_extra=False)
THREAT_BLOCK = dict(enabled=True, stalk_frac=[0.3, 0.7], stalk_dist=6.0, stalk_speed=0.3, pounce_speed=1.5,
                    pounce_steps=12, exhaust_speed=0.2, exhaust_steps=30, player_frac=0.5,
                    player_speeds=[0.4, 0.3, 1.3], player_mode_steps=[200, 400], player_stalk_p=0.5,
                    player_charge_dist=6.0, player_charge_steps=20, player_rest_steps=30, player_catch_r=1.0,
                    player_cooldown=30)


@pytest.mark.parametrize("v3, v2", [(V3, V2_4S), (V3_ON, V2_4S_ON)], ids=["train", "on"])
def test_v3_configs_are_v2_4s_plus_two_blocks(v3, v2):
    """v3_r0(_on) = v2_4s(_on) + repertoire·threats 블록(명세 수치) + version 3.r0. 그 밖의 키는 그대로다."""
    r3 = yaml.safe_load(v3.read_text(encoding="utf-8"))
    r2 = yaml.safe_load(v2.read_text(encoding="utf-8"))
    assert r3["version"] == "3.r0"
    assert {k: v for k, v in r3.items() if k not in ("version", "features")} == \
        {k: v for k, v in r2.items() if k not in ("version", "features")}
    assert {k: v for k, v in r3["features"].items() if k not in ("repertoire", "threats")} == r2["features"]
    assert r3["features"]["repertoire"] == REP_BLOCK and r3["features"]["threats"] == THREAT_BLOCK
    w = World(load_v2_config(v3), seeds=[0])
    assert w.features.active == ("speed", "daynight", "pred_sleep", "repertoire", "threats")
    assert w.act_names == ("behavior",) and w.act_dim == 1
    assert w.obs_dim == 9 and w.obs_names == obs_names(load_v2_config(v2))       # R0 는 관측이 v2.4s 9칸 그대로


@pytest.mark.parametrize("name, kw, match", [
    ("repertoire", dict(lock_graze=-1), "lock_graze"),
    ("repertoire", dict(sleep_wake=1.5), "sleep_wake"),
    ("repertoire", dict(c_still=0.5), "c_still"),
    ("repertoire", dict(graze_head_down=0.0), "graze_head_down"),
    ("repertoire", dict(sleep_rest=1.5), "sleep_rest"),
    ("repertoire", dict(event_dark=1.0), "event_dark"),
    ("repertoire", dict(obs_extra=1), "obs_extra"),
    ("threats", dict(stalk_frac=[0.7, 0.3]), "stalk_frac"),
    ("threats", dict(pounce_steps=0), "pounce_steps"),
    ("threats", dict(player_speeds=[0.4, 0.3]), "player_speeds"),
    ("threats", dict(player_mode_steps=[400, 200]), "player_mode_steps"),
    ("threats", dict(player_frac=2.0), "player_frac"),
])
def test_params_are_checked(cfg3, name, kw, match):
    with pytest.raises(ValueError, match=match):
        World(_feat(cfg3, name, **kw), seeds=[0])


def test_prerequisites_and_missing_coefficients(cfg3, tmp_path):
    with pytest.raises(ValueError, match="daynight"):
        World(_feat(_feat(_feat(cfg3, "daynight", enabled=False), "pred_sleep", enabled=False), "threats",
                    enabled=False), seeds=[0])
    with pytest.raises(ValueError, match="daynight"):
        World(_feat(_feat(_feat(cfg3, "daynight", enabled=False), "pred_sleep", enabled=False), "repertoire",
                    enabled=False), seeds=[0])
    vig = yaml.safe_load((ROOT / "configs" / "v2_2.yaml").read_text(encoding="utf-8"))["features"]["vigilance"]
    f = {k: dict(v) for k, v in cfg3.v2["features"].items()}
    f["vigilance"] = dict(vig)
    with pytest.raises(ValueError, match="vigilance"):
        World(cfg3.replace(v2=dict(cfg3.v2, features=f)), seeds=[0])
    raw = yaml.safe_load(V3.read_text(encoding="utf-8"))
    del raw["features"]["repertoire"]["sleep_rest"]
    p = tmp_path / "v3_missing.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="sleep_rest"):
        load_v2_config(p)


# --------------------------------------------------------------------- #
# 끈 기능 = v2.4s (비트 동일)
# --------------------------------------------------------------------- #

SPECS5 = [{"kind": "fixed", "action": C2}, ro.adapt_spec({"kind": "random", "seed": 3}, 5)]


def _run_pair(wa, wb, pol_a, pol_b, steps=300):
    for _ in range(steps):
        oa, ob = wa.observe(), wb.observe()
        np.testing.assert_array_equal(oa, ob)
        ra, rb = wa.step(pol_a(oa)), wb.step(pol_b(ob))
        for x, y in zip(ra, rb):
            np.testing.assert_array_equal(x, y)
    for name in ("stats", "gait_stats", "daynight_stats", "pred_sleep_stats"):
        _same(getattr(wa, name)(), getattr(wb, name)())
    for k in ("pos", "head", "energy", "pred_pos", "pred_head", "food", "vel", "pred_cd"):
        np.testing.assert_array_equal(getattr(wa, k), getattr(wb, k), err_msg=k)


@pytest.mark.parametrize("seed", [0, 10000, 12000])
@pytest.mark.parametrize("pol", ["fixed", "random", "rule"])
@pytest.mark.parametrize("v3, v2", [(V3_ON, V2_4S_ON), (V3, V2_4S)], ids=["on", "train"])
def test_both_off_matches_v2_4s_bitwise(v3, v2, seed, pol):
    """repertoire·threats 를 끈 v3_r0(_on) = v2_4s(_on): 관측·보상·사망·위치·통계 비트 동일, 두 기능의 스트림 0개."""
    off = _feat(_feat(load_v2_config(v3), "repertoire", enabled=False), "threats", enabled=False)
    w3, w2 = World(off, seeds=[seed]), World(load_v2_config(v2), seeds=[seed])
    assert w3.features.active == ("speed", "daynight", "pred_sleep") and w3._rp is None and w3._th is None
    assert not w3._v3p and w3.M_base == w3.M
    pa, pb = [ro.build_policy(SPECS5[pol == "random"]) if pol != "rule" else _rule5 for _ in range(2)]
    _run_pair(w3, w2, pa, pb)
    assert not {n for n, _ in w3._feature_rngs} & {"repertoire", "threats"}


@pytest.mark.parametrize("seed", [0, 12000, 12003])
def test_neutral_threats_keep_v2_4s_predators_bitwise(cfg3, seed):
    """threats 를 켜도 잠행형 비율 0·플레이어 없음이면 v3 포식자 스텝(_step_predators_v3)이 v2.4s 와 비트 동일하다
    (v1 스트림 호출 모양·체감 거리·포획 순서가 같다). threats 스트림은 part 0·1 만 생긴다."""
    cfg = _feat(_feat(cfg3, "repertoire", enabled=False), "threats", stalk_frac=[0.0, 0.0], player_frac=0.0)
    w3, w2 = World(cfg, seeds=[seed]), World(load_v2_config(V2_4S_ON), seeds=[seed])
    assert w3._v3p and w3._th is not None and not w3.player_present and not (w3.pred_type == PT_STALKER).any()
    assert w3.rng.bit_generator.state == w2.rng.bit_generator.state
    _run_pair(w3, w2, _rule5, _rule5)
    assert {k for k in w3._feature_rngs if k[0] == "threats"} <= {("threats", 0), ("threats", 1)}
    assert w3.threats_stats()["catch_rate_player"] == 0.0


def test_obs_extra_changes_observation_only(cfg3):
    """obs_extra true: 관측이 9 + 9칸(이름 OBS_EXTRA_NAMES)이 되고 뒤 9칸 = rep_obs_extra(). 세계 동역학은 같다."""
    on = _feat(cfg3, "repertoire", obs_extra=True)
    wa, wb = World(on, seeds=[12001]), World(cfg3, seeds=[12001])
    assert wa.obs_names == wb.obs_names + rep.OBS_EXTRA_NAMES and wa.obs_dim == 18
    rng = np.random.default_rng(5)
    for _ in range(150):
        oa, ob = wa.observe(), wb.observe()
        np.testing.assert_array_equal(oa[:, :9], ob)
        np.testing.assert_array_equal(oa[:, 9:], wb.rep_obs_extra())
        a = rng.integers(0, 5, (wa.N, 1)).astype(np.float64)
        ra, rb = wa.step(a), wb.step(a)
        for x, y in zip(ra[1:3], rb[1:3]):
            np.testing.assert_array_equal(x, y)
    np.testing.assert_array_equal(wa.pos, wb.pos)
    ex = wb.rep_obs_extra()
    assert ex.shape == (wb.N, 9) and np.all(ex >= 0.0) and np.all(ex <= 1.0)
    np.testing.assert_array_equal(ex[:, 2:7].sum(1), 1.0)                        # 현재 행동 one-hot
    np.testing.assert_array_equal(ex[np.arange(wb.N), 2 + wb._rs.behavior.astype(int)], 1.0)


# --------------------------------------------------------------------- #
# 행동 실행기 (env_v2/repertoire.py, 순수 계산)
# --------------------------------------------------------------------- #


def _o(pc=0, d=np.inf, app=0.5, energy=0.8, dark=0.0, in_cover=False, cover_k=0):
    one = lambda x, dt=None: np.array([x], dtype=dt)        # noqa: E731
    return dict(pred_count=one(pc, np.int64), d_pred_min=one(float(d)), pred_approach=one(float(app)),
                energy=one(float(energy)), dark=float(dark), in_cover=one(bool(in_cover)), cover_k=one(cover_k, np.int64))


def _drive(P, reqs, obs_fn, jitter=0, rs=None):
    """요청 열을 한 개체에 넣고 스텝마다 (behavior, phase, steps_in, seq, decide, switch) 를 남긴다."""
    if rs is None:
        rs = rep.RepState(1, P, np.array([0.8]), 0.0, 0)
        rs.jitter[:] = jitter
    out = []
    for t, req in enumerate(reqs):
        res = rep.arbitrate(rs, P, np.array([req]), obs_fn(t))
        out.append((int(rs.behavior[0]), int(rs.phase[0]), int(rs.steps_in[0]), int(rs.seq[0]),
                    bool(res["decide"][0]), bool(res["switch"][0])))
        rep.tick(rs)
    return out, rs


def test_requests_wait_for_lock(P):
    """잠금 동안 요청은 무시된다: GRAZE 12스텝 뒤 FLEE 로 바뀌고(seq 1, steps_in 0), FLEE 는 놀람 3스텝이 진입 위상이다."""
    h, _ = _drive(P, [F] * 30, lambda t: _o())
    beh = [x[0] for x in h]
    assert beh[:12] == [G] * 12 and beh[12:] == [F] * 18
    assert [x[4] for x in h[:12]] == [False] * 12 and h[12][4] and h[12][5]
    assert h[12][2] == 0 and h[12][3] == 1 and h[13][2] == 1
    assert [x[1] for x in h[12:16]] == [0, 0, 0, 1]                    # 놀람 정지 3스텝 = 진입
    assert [x[2] for x in h[:12]] == list(range(12))                    # 경과 스텝


@pytest.mark.parametrize("jitter", [0, 2])
def test_event_unlocks_decision_after_jitter(P, jitter):
    """E1(보이는 위협 수 증가)은 잠금 중에도 결정 시점을 만든다. 개체 지연 J 스텝 뒤에 결정한다."""
    h, _ = _drive(P, [F] * 10, lambda t: _o(pc=int(t >= 3), d=12.0), jitter=jitter)
    first = next(t for t, x in enumerate(h) if x[0] == F)
    assert first == 3 + jitter and h[first][4]


@pytest.mark.parametrize("kind", ["near", "approach", "energy", "dark"])
def test_edge_events(P, kind):
    """E2(8 안으로 들어옴·접근 ≥ 0.9), E4(에너지 < 0.25 로 내려감), E5(어둠 0.5 통과)는 경계를 넘는 스텝에 결정 시점이다.
    같은 상태가 이어지면 다시 사건이 되지 않는다."""
    def obs(t):
        late = t >= 5
        if kind == "near":
            return _o(pc=1, d=7.0 if late else 12.0)
        if kind == "approach":
            return _o(pc=1, d=12.0, app=0.95 if late else 0.6)
        if kind == "energy":
            return _o(energy=0.2 if late else 0.3)
        return _o(dark=0.6 if late else 0.4)
    reqs = [G] + [F] * 9
    h, _ = _drive(P, reqs, obs)
    assert [x[0] for x in h].index(F) == 5
    # 사건 결정 뒤에는 잠금(FLEE 8)이 다시 걸린다 — 같은 상태가 이어져도 결정 시점이 아니다
    assert not any(x[4] for x in h[6:])


def test_sleep_enter_hold_wake(P):
    """SLEEP: 진입 3(위상 0) → 수면(위상 1), 잠금 3 + 60. 결정이 다른 행동이면 기상 3스텝(위상 2, 결정 안 받음) 뒤 바뀐다."""
    reqs = [S] * 13 + [G] * 80
    h, rs = _drive(P, reqs, lambda t: _o(dark=0.0))
    beh, ph = [x[0] for x in h], [x[1] for x in h]
    assert beh[12] == S and ph[12:15] == [0, 0, 0] and ph[15] == 1
    assert beh[12:78] == [S] * 66 and ph[75:78] == [2, 2, 2]               # 12 + 63 = 75 에 기상 시작
    assert beh[78] == G and h[78][3] == 2 and h[78][2] == 0 and h[77][2] == 65
    assert not any(x[4] for x in h[76:78])                                  # 기상 중에는 결정하지 않는다


def test_threat_while_sleeping_is_an_event(P):
    """E3: 잠 중 위협이 보이면(줄곧) 스텝마다 결정 시점이다 — 잠금 63 전에 깨어(기상 3) 다른 행동으로 바꿀 수 있다."""
    reqs = [S] * 5 + [F] * 10
    h, _ = _drive(P, reqs, lambda t: _o(pc=1, d=12.0))
    beh, ph = [x[0] for x in h], [x[1] for x in h]
    assert beh[0] == S                                                      # t=0 E1 로 바로 잠
    assert ph[5:8] == [2, 2, 2] and beh[8] == F                             # t=5 결정 → 기상 → t=8 FLEE(놀람 없음)
    assert h[8][1] == 0 and h[9][1] == 1


def test_hide_travel_arrival_and_lock(P):
    """HIDE: 은신처 밖에서 고르면 가는 중(위상 0, 잠금 최대 40). 도착하면 웅크림(위상 1), 사건 E6 으로 결정 시점, 그 뒤 12 잠금.
    은신처 안에서 고르면 곧바로 도착(E6 없음). 도착하지 못하면 40스텝 뒤 결정 시점."""
    reqs = [H] * 21 + [G] * 20
    h, rs = _drive(P, reqs, lambda t: _o(in_cover=t >= 20, cover_k=0))
    beh, ph = [x[0] for x in h], [x[1] for x in h]
    assert beh[12] == H and ph[12:20] == [0] * 8 and ph[20] == 1 and h[20][4]       # 도착 스텝에 결정(E6)
    assert beh[31] == H and beh[32] == G                                    # 도착 뒤 잠금 12
    h2, rs2 = _drive(P, [H] * 13 + [G] * 3, lambda t: _o(in_cover=True))
    assert h2[12][0] == H and h2[12][1] == 1 and rs2.arrived[0] is not None
    assert [x[0] for x in h2[13:]] == [H, H, H]                              # E6 없음 → 잠금 12 그대로
    h3, _ = _drive(P, [H] * 13 + [G] * 45, lambda t: _o(in_cover=False))
    assert [x[0] for x in h3].index(G, 13) == 12 + 40


def test_seq_wraps_like_uint8(P):
    rs = rep.RepState(1, P, np.array([0.8]), 0.0, 0)
    rs.seq[:] = 255
    rs.lock_left[:] = 0
    rep.arbitrate(rs, P, np.array([F]), _o())
    assert rs.seq[0] == 0 and rs.behavior[0] == F


def test_decision_jitter_hash():
    """사건 결정 지연 = H(505, 세계 시드, 슬롯·2^32 + 세대) mod (J + 1). rollout 의 유지 표본 해시·개체 키와 같은 꼴이다."""
    slots, gens = np.arange(128), np.zeros(128, dtype=np.int64)
    j = rep.decision_jitter(12000, slots, gens, 3)
    assert j.min() >= 0 and j.max() <= 3 and len(set(j.tolist())) == 4
    want = ro.hold_hash(505, 12000, ro.hold_agent_keys(slots, gens)) % np.uint64(4)
    np.testing.assert_array_equal(j, want.astype(np.int64))
    np.testing.assert_array_equal(rep.decision_jitter(0, np.arange(5), np.zeros(5, dtype=np.int64), 0), 0)
    # 세계 시드·세대가 다르면 지연도 다르다(고정 슬롯이 시드마다 같은 지연을 갖지 않는다)
    assert not np.array_equal(j, rep.decision_jitter(12001, slots, gens, 3))
    assert not np.array_equal(j, rep.decision_jitter(12000, slots, gens + 1, 3))


def _inp(n=1, away=(1.0, 0.0), seen=True, food_ok=False, grad=(0.0, 1.0), target=(0.0, 1.0), in_cover=False,
         dark=0.0):
    t = lambda v: np.tile(np.asarray(v, dtype=np.float64), (n, 1))        # noqa: E731
    return dict(food_grad=t(grad), to_centroid=t((0.0, 0.0)), separation=t((0.0, 0.0)), away_from_pred=t(away),
                to_target=t(target), pred_count=np.full(n, int(seen)), food_ok=np.full(n, bool(food_ok)),
                in_cover=np.full(n, bool(in_cover)), dark=float(dark))


def test_controllers(cfg3, P):
    """행동별 제어기: 속도·보행·섭식·자기 시야·정지·웅크림·시선 (명세 2절 표)."""
    sp = World(cfg3, seeds=[0])._sp
    hs = cfg3.herb_speed
    rs = rep.RepState(1, P, np.array([0.8]), 0.0, 0)

    def run(b, **kw):
        rs.behavior[:] = b
        return rep.control(rs, P, _inp(**kw), cfg3, sp)

    o = run(G, food_ok=True)
    assert o["gait"][0] == GAIT_STOP and o["eat"][0] == 1.0 and o["see"][0] == 0.6 and not o["still"][0]
    o = run(G, food_ok=False)
    assert o["gait"][0] == GAIT_WALK and o["eat"][0] == 0.5
    np.testing.assert_allclose(o["vel"][0], [0.0, 0.4 * hs])
    rs.startle_left[:] = 2
    o = run(F)
    assert o["gait"][0] == GAIT_STOP and not o["vel"].any() and o["eat"][0] == 0.0     # 놀람 정지(M2)
    rs.startle_left[:] = 0
    o = run(F)
    assert o["gait"][0] == GAIT_RUN and o["see"][0] == 1.0
    np.testing.assert_allclose(o["vel"][0], [hs, 0.0])
    rs.away[:] = [[0.0, -1.0]]
    o = run(F, seen=False)                                                  # 안 보이면 마지막 위협 반대 방향
    np.testing.assert_allclose(o["vel"][0], [0.0, -hs])
    o = run(Z, away=(1.0, 0.0))
    assert o["gait"][0] == GAIT_STOP and o["still"][0] and o["eat"][0] == 0.0 and o["see"][0] == 1.0
    np.testing.assert_allclose(o["face"][0], [-1.0, 0.0])                   # 위협 쪽으로 고개
    o = run(S)
    assert o["gait"][0] == GAIT_STOP and o["still"][0] and o["see"][0] == 0.3 and not o["vel"].any()
    assert o["drain"][0] == sp["drain_mult"][GAIT_STOP]                    # 은신처 밖 잠은 할인 없음
    o = run(S, in_cover=True, dark=0.5)
    assert o["drain"][0] == pytest.approx(sp["drain_mult"][GAIT_STOP] * (1 - 0.6 * 0.5))
    o = run(G, food_ok=True, in_cover=True, dark=1.0)
    assert o["drain"][0] == sp["drain_mult"][GAIT_STOP]                    # 휴식 할인은 SLEEP 전용
    rs.arrived[:] = False
    rs.hide_target[:] = 0
    o = run(H, seen=True)
    assert o["gait"][0] == GAIT_RUN and not o["still"][0] and o["eat"][0] == 0.0
    np.testing.assert_allclose(o["vel"][0], [0.0, hs])
    o = run(H, seen=False)
    assert o["gait"][0] == GAIT_WALK
    rs.hide_target[:] = -1                                                  # 고른 은신처가 없다(세계에 은신처 없음): 정지
    o = run(H, seen=True)
    assert o["gait"][0] == GAIT_STOP and not o["vel"].any() and not o["still"][0]
    rs.arrived[:] = True
    o = run(H)
    assert o["gait"][0] == GAIT_STOP and o["still"][0] and o["crouch"][0] and not o["vel"].any()


# --------------------------------------------------------------------- #
# 세계 장치 (M1·M5·M6·포획·휴식 할인)
# --------------------------------------------------------------------- #


def _preds(w, pos, kind=None, head=None, speed=0.5):
    """포식자를 `pos` 로 바꾼다(모두 깨어 있고 사냥한다, 쿨다운 0). 플레이어(PT_PLAYER)는 끝에 둔다."""
    pos = np.asarray(pos, dtype=np.float64).reshape(-1, 2)
    M = len(pos)
    kind = np.zeros(M, dtype=np.int8) if kind is None else np.asarray(kind, dtype=np.int8)
    w.M = M
    w.M_base = int(np.count_nonzero(kind != PT_PLAYER))
    w.pred_pos = pos.copy()
    w.pred_head = np.tile([1.0, 0.0], (M, 1)) if head is None else np.asarray(head, dtype=np.float64).reshape(-1, 2)
    w.pred_ranged = np.zeros(M, dtype=bool)
    w._pred_ranged_v1 = np.zeros(M, dtype=bool)
    w.pred_speed = np.full(M, float(speed))
    w.pred_catch_r = np.ones(M)
    w.pred_cd = np.zeros(M, dtype=np.int32)
    w.pred_vel = np.zeros((M, 2))
    if w._th is not None:
        w.pred_type = kind
        w.pred_is_player = kind == PT_PLAYER
        w.player_present = bool(w.pred_is_player.any())
        w.stalk_state = np.zeros(M, dtype=np.int8)
        w.stalk_left = np.zeros(M, dtype=np.int64)
        w.player_mode = np.zeros(M, dtype=np.int8)
        w.player_left = np.full(M, 10 ** 6, dtype=np.int64)
    if w._ps is not None:
        w.pred_nocturnal = np.ones(M, dtype=bool)
        w.pred_asleep = np.zeros(M, dtype=bool)
        w._pred_speed_mult = np.ones(M)
    return w


def _clear(w, keep=()):
    """은신처를 없애고 `keep` 밖 개체를 구석으로 보낸다."""
    w.cov_c, w.cov_r = np.zeros((0, 2)), np.zeros(0)
    far = np.ones(w.N, dtype=bool)
    far[list(keep)] = False
    w.pos[far] = [1.0, 1.0]
    w._rep_still = np.zeros(w.N, dtype=bool)
    w._rep_cover = np.ones(w.N)


def _ang(v):
    return math.atan2(v[1], v[0])


def test_still_detection_steers_target_choice(cfg3):
    """M1: 정지(FREEZE·도착 HIDE·SLEEP) 개체는 표적 선택 체감 거리 × 1.8 — 같은 실거리 9 에서 움직이는 개체를 고르고,
    둘 다 정지면 14/1.8 ≈ 7.8 밖이라 표적이 없다(배회). M6: 은신처 안 GRAZE 는 × 1.5."""
    w = World(cfg3, seeds=[12000])
    c = np.array([w.size / 2, w.size / 2])
    a = math.radians(20)
    p_lo, p_hi = c + 9 * np.array([math.cos(-a), math.sin(-a)]), c + 9 * np.array([math.cos(a), math.sin(a)])

    def target(still, cover=None):
        _clear(w, keep=(0, 1))
        w.pos[0], w.pos[1] = p_lo, p_hi
        w._rep_still[:2] = still
        if cover is not None:
            w.cov_c, w.cov_r = np.array([p_hi]), np.array([1.0])
            w._rep_cover[1] = cover
        _preds(w, [c], kind=[PT_CHASER])
        w._step_predators_v3()
        return _ang(w.pred_head[0])

    assert target([True, False]) == pytest.approx(a)
    assert target([False, True]) == pytest.approx(-a)
    assert abs(target([True, True])) <= 0.15 + 1e-9                         # 배회 선회 한도 안
    assert target([False, False], cover=1.5) == pytest.approx(-a)          # 은신처 안 GRAZE 는 9 × 1.5 = 13.5
    assert target([False, True], cover=2.5) == pytest.approx(-a)           # 웅크린 HIDE: max(2.5, 1.8)·9 > 14


@pytest.mark.parametrize("still, in_cover, cover, caught", [
    (True, False, 1.0, True),        # 정지 탐지는 포획 판정에 쓰지 않는다
    (False, True, 1.5, False),       # 은신처 안 GRAZE 0.9 × 1.5 > 1
    (True, True, 2.5, False),        # 웅크린 HIDE
    (False, True, 1.0, True),        # 은신처 안이어도 FLEE 는 배수 1
])
def test_catch_uses_cover_multiplier_only(cfg3, still, in_cover, cover, caught):
    w = World(cfg3, seeds=[12000])
    c = np.array([w.size / 2, w.size / 2])
    _clear(w, keep=(0,))
    w.pos[0] = c + [0.9, 0.0]
    if in_cover:
        w.cov_c, w.cov_r = np.array([w.pos[0]]), np.array([1.0])
    w._rep_still[0], w._rep_cover[0] = still, cover
    _preds(w, [c], kind=[PT_CHASER])
    assert bool(w._step_predators_v3()[0]) is caught


def test_v2_4s_cover_rule_without_repertoire(cfg3):
    """repertoire 를 끈 threats 세계는 v1 은신 규칙(은신처 안 × cover_hide_mult 2.5, 탐지·포획 모두)이다."""
    w = World(_feat(cfg3, "repertoire", enabled=False), seeds=[12000])
    c = np.array([w.size / 2, w.size / 2])
    w.cov_c, w.cov_r = np.array([c + [0.9, 0.0]]), np.array([1.0])
    w.pos[:] = [1.0, 1.0]
    w.pos[0] = c + [0.9, 0.0]
    _preds(w, [c], kind=[PT_CHASER])
    assert not w._step_predators_v3()[0]


def test_own_detection_radius_by_behavior(cfg3):
    """M5·잠 시야: 초식의 포식자 탐지 반경 = see_r·visibility × (GRAZE 0.6, SLEEP 0.3, 그 밖 1). 동족 시야는 그대로다."""
    w = World(cfg3, seeds=[12000])
    w.day_fixed = True
    w._daynight_update()
    c = np.array([w.size / 2, w.size / 2])
    _clear(w, keep=(0, 1))
    w.pos[0], w.head[0] = c, [1.0, 0.0]
    w.pos[1] = c + [15.0, 1.0]                                             # 동족(거리 15)은 늘 보인다
    for d, see, vis in ((13.0, 0.6, False), (11.0, 0.6, True), (13.0, 1.0, True), (7.0, 0.3, False), (5.0, 0.3, True)):
        _preds(w, [c + [d, 0.0]], kind=[PT_CHASER])
        w._rep_see[0] = see
        g = w._geometry()
        assert bool(g["pred_count"][0] > 0) is vis, (d, see)
        assert g["kin_count"][0] == 1


def test_pred_approach_and_kin_alarm(cfg3):
    """관측 pred_approach = (clip(v_pred·û/herb_speed, −1, 1) + 1)/2 (û = 위협 → 개체), 없으면 0.5.
    kin_alarm = 보이는 동족 중 FLEE 비율."""
    w = World(cfg3, seeds=[12000])
    w.day_fixed = True
    w._daynight_update()
    c = np.array([w.size / 2, w.size / 2])
    _clear(w, keep=(0, 1, 2))
    w.pos[0], w.head[0] = c, [1.0, 0.0]
    w.pos[1], w.pos[2] = c + [3.0, 1.0], c + [3.0, -1.0]
    w._rs.behavior[:] = G
    w._rs.behavior[1] = F
    _preds(w, [c + [5.0, 0.0]], kind=[PT_CHASER])
    w._rep_see[:] = 1.0
    for vel, want in (((-0.36, 0.0), 0.8), ((0.36, 0.0), 0.2), ((0.0, 0.5), 0.5), ((-2.0, 0.0), 1.0)):
        w.pred_vel[0] = vel
        g = w._geometry()
        assert g["pred_approach"][0] == pytest.approx(want)
        assert g["kin_alarm"][0] == pytest.approx(0.5)
    _preds(w, [c + [-30.0, 0.0]], kind=[PT_CHASER])
    assert w._geometry()["pred_approach"][0] == 0.5


def test_sleep_only_rest_discount_and_eat(cfg3):
    """휴식 할인은 SLEEP·은신처 안 전용: 대사 × (1 − 0.6·d). 은신처 안 GRAZE 정지·밖 SLEEP 은 할인이 없다(v2.4 rest_night
    를 쓰지 않는다). 섭식 = 제어기 배수 × (1 − 0.9·d)."""
    w = World(cfg3, seeds=[12000])
    w.dark = 1.0
    inc = np.zeros(w.N, dtype=bool)
    inc[::2] = True
    w._g = dict(w._g, in_cover=inc)
    beh = np.full(w.N, S, dtype=np.int8)
    beh[:4] = G
    w._rs.behavior[:] = beh
    w._rep_step(beh[:, None].astype(np.float64))         # 요청 = 지금 행동이라 결정 시점이어도 그대로다
    np.testing.assert_array_equal(w._rs.behavior, beh)
    drain, eat = w._drain_eat()
    dm = w.cfg.energy_drain * w._sp["drain_mult"]
    sleep = beh == S
    assert (w.gait[sleep] == GAIT_STOP).all()
    np.testing.assert_allclose(drain[sleep & inc], dm[GAIT_STOP] * (1 - 0.6))
    np.testing.assert_allclose(drain[sleep & ~inc], dm[GAIT_STOP])
    np.testing.assert_allclose(drain[~sleep], dm[w.gait[~sleep]])             # GRAZE 는 은신처 안 밤에도 할인 없음
    np.testing.assert_array_equal(w._rep_eat[sleep], 0.0)
    np.testing.assert_allclose(eat, w._rep_eat * (1 - 0.9))


# --------------------------------------------------------------------- #
# 잠행-돌진형 · 플레이어 (threats)
# --------------------------------------------------------------------- #


def test_stalker_state_machine(cfg3):
    """M3: 체감 거리 > 6 이면 × 0.3 잠행, ≤ 6 이면 × 1.5 로 돌진 12번, 마지막 판정 뒤 놓치면 30스텝 탈진(× 0.2, 사냥 안 함),
    그 뒤 배회로 돌아와 다시 잡는다."""
    w = World(cfg3, seeds=[12000])
    hs = w.cfg.herb_speed
    c = np.array([w.size / 2, w.size / 2])
    _clear(w, keep=(0,))
    _preds(w, [c], kind=[PT_STALKER])
    w.pos[0] = c + [10.0, 0.0]
    w._step_predators_v3()
    assert w.stalk_state[0] == ST_ROAM and np.linalg.norm(w.pred_vel[0]) == pytest.approx(0.3 * hs)
    w.pos[0] = w.pred_pos[0] + [5.0, 0.0]
    w._step_predators_v3()
    assert w.stalk_state[0] == ST_POUNCE and np.linalg.norm(w.pred_vel[0]) == pytest.approx(1.5 * hs)
    assert w._th_pounce[0] == 1
    w.pos[0] = w.pred_pos[0] - [30.0, 0.0]                                  # 놓친다(시야 밖)
    for _ in range(11):
        w._step_predators_v3()
        assert np.linalg.norm(w.pred_vel[0]) == pytest.approx(1.5 * hs)
    assert w.stalk_state[0] == ST_POUNCE and w.stalk_left[0] == 0
    w._step_predators_v3()                                                  # 마지막 판정 스텝(느리게 곧장)
    assert w.stalk_state[0] == ST_EXHAUST and np.linalg.norm(w.pred_vel[0]) == pytest.approx(0.2 * hs)
    for _ in range(30):
        w.pos[0] = w.pred_pos[0] + 0.5 * w.pred_head[0]                    # 바로 앞에 있어도 탈진 중에는 못 잡는다
        assert not w._step_predators_v3()[0]
    assert w.stalk_state[0] == ST_ROAM
    w.pos[0] = w.pred_pos[0] + 0.5 * w.pred_head[0]
    assert w._step_predators_v3()[0]
    assert w._th_catch.tolist() == [0, 0, 1, 0] and w._th_pounce.tolist() == [2, 1]


def test_player_never_sleeps_and_is_perceived(cfg3):
    """플레이어는 밤잠 배열에 야행성으로 들어가 잠도 박명 감속도 없다. 초식 관측의 포식자 칸에 보인다."""
    seeds = [s for s in range(12000, 12040) if World(cfg3, seeds=[s]).player_present]
    w = World(cfg3, seeds=[seeds[0]])
    i = w.M - 1
    assert w.pred_is_player[i] and w.pred_type[i] == PT_PLAYER and w.M == w.M_base + 1
    assert w.pred_nocturnal[i] and w.pred_cd.dtype == np.int32
    w.day_fixed = False
    w.dn_period, w.dn_offset = 600, 450                                     # 한밤(d = 1)
    w._daynight_update()
    assert w.dark == 1.0 and not w.pred_asleep[i] and w._pred_speed_mult[i] == 1.0
    assert w.pred_asleep[:w.M_base][~w.pred_nocturnal[:w.M_base]].all()
    c = w.pred_pos[i]
    w.pos[0], w.head[0] = c - [3.0, 0.0], [1.0, 0.0]
    g = w._geometry()
    assert g["pred_count"][0] >= 1 and g["d_pred_min"][0] <= 3.0 + 1e-9
    assert w.pred_sleep_stats()["pred_noct_n"] == float(w.pred_nocturnal[:w.M_base].sum())


def test_player_modes_cycle_and_catch():
    """플레이어가 있는 세계(player_frac 1): 모드가 배회·잠행·돌진·휴식을 돈다. 휴식은 player_rest_steps, 돌진은 최대
    player_charge_steps(+ 마지막 판정). 플레이어 포획은 catch_rate_player 로 센다. 스트림은 threats part 0~3 만."""
    cfg = _feat(load_v2_config(V3_ON), "threats", player_frac=1.0, player_mode_steps=[30, 60])
    w = World(cfg, seeds=[12000])
    i = w.M - 1
    assert w.player_present and w.pred_is_player[i]
    modes = []
    a = np.zeros((w.N, 1))
    for _ in range(1500):
        w.step(a)
        modes.append(int(w.player_mode[i]))
        assert not w.pred_asleep[i]
    m = np.array(modes)
    assert {PM_WANDER, PM_STALK, PM_CHARGE, PM_REST} <= set(modes)
    runs = np.split(m, np.flatnonzero(np.diff(m)) + 1)
    rest = [len(r) for r in runs[1:-1] if r[0] == PM_REST]
    charge = [len(r) for r in runs[1:-1] if r[0] == PM_CHARGE]
    assert rest and set(rest) == {30}
    assert charge and max(charge) <= 21
    ts = w.threats_stats()
    assert tuple(ts) == THREAT_STAT_COLUMNS and ts["player_present"] == 1.0 and ts["player_charge_n"] >= len(charge)
    # 포식자 둘이 한 스텝에 같은 개체를 잡으면 유형별 포획은 둘 다 센다(사망은 하나)
    assert sum(ts[k] for k in ("catch_rate_chaser", "catch_rate_ranged", "catch_rate_stalker",
                               "catch_rate_player")) * w.t * w.N >= w._pred_deaths - 1e-9
    assert {k[0] for k in w._feature_rngs} <= {"threats", "pred_sleep"}
    assert {k[1] for k in w._feature_rngs if k[0] == "threats"} <= {0, 1, 2, 3}


def test_threat_draws_and_fractions(cfg3):
    """p_stalk ~ U[0.3, 0.7] 와 포식자별 잠행형 판정은 threats part 0 의 1 + M 개, 플레이어 유무·배치는 part 1 의 4 개다.
    잠행형은 근접형이다. 세계의 약 절반에 플레이어가 있다. v1 스트림은 v2.4s 와 같은 위치다."""
    w2 = World(load_v2_config(V2_4S_ON), seeds=[12005])
    w = World(cfg3, seeds=[12005])
    g = feature_stream(12005, "threats", 0)
    p = g.uniform(0.3, 0.7)
    st = g.random(w.M_base) < p
    assert w.threat_p_stalk == p and np.array_equal(w.pred_type[:w.M_base] == PT_STALKER, st)
    assert not (w.pred_ranged & (w.pred_type == PT_STALKER)).any()
    assert w.rng.bit_generator.state == w2.rng.bit_generator.state
    np.testing.assert_array_equal(w.pred_pos[:w.M_base], w2.pred_pos)
    present = [World(cfg3, seeds=[s]).player_present for s in range(120)]
    assert 0.35 < np.mean(present) < 0.65
    assert present[:20] == [bool(feature_stream(s, "threats", 1).random(4)[0] < 0.5) for s in range(20)]


def test_features_draw_only_from_their_own_streams(cfg3, monkeypatch):
    """repertoire 는 난수를 쓰지 않고, threats 는 자기 스트림 part 0~3 만 쓴다(스트림 생성을 직접 기록한다)."""
    import env_v2.world as wm

    seen = []
    real = wm.feature_stream

    def spy(seed, name, part=0):
        seen.append((name, int(part)))
        return real(seed, name, part)

    monkeypatch.setattr(wm, "feature_stream", spy)
    cfg = _feat(cfg3, "threats", player_frac=1.0)
    w = World(cfg, seeds=[12002])
    rng = np.random.default_rng(1)
    for _ in range(300):
        w.step(rng.integers(0, 5, (w.N, 1)).astype(np.float64))
    names = {n for n, _ in seen}
    assert names <= {"daynight", "pred_sleep", "threats"} and "repertoire" not in names
    assert {p for n, p in seen if n == "threats"} <= {0, 1, 2, 3}


# --------------------------------------------------------------------- #
# 세계 통합: 훅·리스폰·결정성·통계
# --------------------------------------------------------------------- #


def test_world_hooks_follow_contract(cfg3):
    """스텝 뒤 훅(behavior·beh_phase·beh_steps·beh_seq): 행동이 바뀌면 seq + 1·경과 0, 그 밖에는 경과 + 1. 정지형 행동
    (FREEZE·SLEEP·도착 HIDE)은 속도 0. 리스폰 개체는 다음 스텝에 GRAZE 진입(경과 0, seq + 1)이다."""
    w = World(cfg3, seeds=[12002])
    rng = np.random.default_rng(3)
    prev = None
    n_dead = 0
    for t in range(800):
        req = rng.integers(0, 5, (w.N, 1)).astype(np.float64)
        if t % 50 < 25:
            req[:] = G                                                      # 리스폰 확인용으로 GRAZE 구간을 섞는다
        _, _, done, _ = w.step(req)
        cur = (w.behavior.copy(), w.beh_phase.copy(), w.beh_steps.copy(), w.beh_seq.copy())
        still = (w.behavior == Z) | (w.behavior == S) | ((w.behavior == H) & (w.beh_phase == 1))
        assert not w.vel[still].any()
        assert set(np.unique(w.beh_phase[w.behavior != S])) <= {0, 1}
        if prev is not None:
            pb, _, ps, pseq = prev
            alive = ~prev_done
            changed = (cur[0] != pb) & alive
            np.testing.assert_array_equal(cur[3][changed], (pseq[changed] + 1) % 256)
            np.testing.assert_array_equal(cur[2][changed], 0)
            same = (cur[0] == pb) & alive & (cur[3] == pseq)
            np.testing.assert_array_equal(cur[2][same], ps[same] + 1)
            reborn = prev_done & (req[:, 0] == G)
            if reborn.any():
                n_dead += int(reborn.sum())
                np.testing.assert_array_equal(cur[0][reborn], G)
                np.testing.assert_array_equal(cur[2][reborn], 0)
                np.testing.assert_array_equal(cur[3][reborn], (pseq[reborn] + 1) % 256)
        prev, prev_done = cur, done
    assert n_dead > 0
    assert set(np.unique(w.behavior)) <= {G, F, H, Z, S}


def test_deterministic_and_copyable(cfg3):
    rng_a, rng_b = np.random.default_rng(9), np.random.default_rng(9)
    a, b = World(cfg3, seeds=[12001]), World(cfg3, seeds=[12001])
    for _ in range(200):
        ra = a.step(rng_a.integers(0, 5, (a.N, 1)).astype(np.float64))
        rb = b.step(rng_b.integers(0, 5, (b.N, 1)).astype(np.float64))
        for x, y in zip(ra, rb):
            np.testing.assert_array_equal(x, y)
    _same(a.repertoire_stats(), b.repertoire_stats())
    clones = [pickle.loads(pickle.dumps(a)), copy.deepcopy(a)]
    for _ in range(100):
        act = rng_a.integers(0, 5, (a.N, 1)).astype(np.float64)
        a.step(act)
        for c in clones:
            c.step(act)
    for c in clones:
        for k in ("pos", "energy", "pred_pos", "behavior", "beh_seq", "stalk_state", "player_mode"):
            np.testing.assert_array_equal(getattr(c, k), getattr(a, k), err_msg=k)
        _same(c.repertoire_stats(), a.repertoire_stats())
        _same(c.threats_stats(), a.threats_stats())


def test_bad_behavior_ids_are_rejected(cfg3):
    w = World(cfg3, seeds=[0])
    for bad in (5.0, -0.5, np.nan, 0.5, 2.5, 3.0 + 1e-9):
        with pytest.raises(ValueError, match="behavior"):
            w.step(np.full((w.N, 1), bad))
    with pytest.raises(ValueError):
        w.step(np.zeros((w.N, 5)))


def test_repertoire_stats_definitions(cfg3):
    """비율 합 1, 늘 GRAZE 요청이면 GRAZE 만 쓰고 전환이 없다(리스폰은 전환이 아니다), 행동별 사망 합 = 사망 수."""
    w = World(cfg3, seeds=[12002])
    for _ in range(600):
        w.step(np.zeros((w.N, 1)))
    s = w.repertoire_stats()
    assert tuple(s) == REP_STAT_COLUMNS
    assert s["use_graze"] == 1.0 and s["switch_per_sec"] == 0.0 and math.isnan(s["flicker_rate"])
    assert int(w._rep_dead.sum()) == w._pred_deaths + w._starve_deaths
    assert s["pred_rate_graze"] == pytest.approx(w._pred_deaths / (600 * w.N))
    w = World(cfg3, seeds=[12002])
    rng = np.random.default_rng(0)
    for _ in range(400):
        w.step(rng.integers(0, 5, (w.N, 1)).astype(np.float64))
    s = w.repertoire_stats()
    for pre in ("use_", "use_seen_", "use_unseen_"):
        assert sum(s[pre + b] for b in rep.BEHAVIOR_NAMES) == pytest.approx(1.0)
    assert 0.0 < s["flicker_rate"] < 1.0 and s["switch_per_sec"] > 0.0 and 0.0 < s["decide_frac"] < 1.0
    assert int(w._rep_hist.sum()) == w._agent_steps


def test_flicker_counts_aba_within_window(cfg3):
    """깜빡임 = A → B 전환 뒤 22스텝(3초) 안에 B → A 로 되돌아온 전환."""
    w = World(cfg3, seeds=[0])
    assert w._rep_flicker_w == 22
    w._rep_before[:] = -1
    out = dict(switch=np.zeros(w.N, dtype=bool), decide=np.zeros(w.N, dtype=bool), prev=np.full(w.N, G))
    no = np.zeros(w.N, dtype=bool)
    w._rs.behavior[:] = F
    out["switch"][:2] = True
    w._rep_accumulate(out, no, no)                                          # G → F (t = 0)
    w.t = 10
    w._rs.behavior[:] = G
    out["prev"][:] = F
    w._rep_accumulate(out, no, no)                                          # F → G 10스텝 뒤: 깜빡임 2
    w.t = 100
    w._rs.behavior[:] = F
    out["prev"][:] = G
    w._rep_accumulate(out, no, no)                                          # G → F 90스텝 뒤: 깜빡임 아님
    assert w._rep_flicker == 2 and w._rep_switch == 6


def test_vec_env_refuses_repertoire_until_r1():
    """학습 VecEnv 는 연속 행동만 받는다 — repertoire 세계를 넣으면 늘 GRAZE 가 되므로 조용히 학습하지 않게 멈춘다(R1 에서
    이산 경로를 만든다). threats 만 켠 세계(행동 5)는 받는다."""
    from env_v2.vec_env import MultiWorldVecEnv

    with pytest.raises(ValueError, match="R1"):
        MultiWorldVecEnv(load_v2_config(V3), seeds=range(100, 110), meta_seed=0)
    venv = MultiWorldVecEnv(_feat(load_v2_config(V3), "repertoire", enabled=False), seeds=range(100, 110), meta_seed=0)
    assert venv.action_space.shape == (5,) and venv.observation_space.shape == (9,)
    venv.close()


def test_rollout_rows_carry_v3_columns_only_when_on(cfg3):
    r3 = ro.rollout(cfg3, ro.build_policy({"kind": "fixed", "action": [0.0]}), 12000, 200)
    r2 = ro.rollout(load_v2_config(V2_4S_ON), ro.build_policy({"kind": "fixed", "action": C2}), 12000, 200)
    for cols in (ro.REPERTOIRE_COLUMNS, ro.THREAT_COLUMNS):
        assert set(cols) <= set(r3) and not set(cols) & set(r2)
    json.dumps(ro.public_row(r3))
    assert r3["_act_sum"].shape == (1,)


# --------------------------------------------------------------------- #
# 손 규칙 (repertoire_rules.py)
# --------------------------------------------------------------------- #


def _rule_obs(cfg, rows):
    """규칙 입력 관측(설정 이름으로 칸을 채운다). rows: dict 목록 {pc, dist, app, cover, energy, vis}."""
    names = list(obs_names(cfg))
    o = np.zeros((len(rows), len(names)), dtype=np.float32)
    for i, r in enumerate(rows):
        o[i, names.index("pred_count")] = r.get("pc", 0) / 8.0
        o[i, names.index("pred_dist")] = r.get("dist", 20.0) / cfg.see_r
        o[i, names.index("pred_approach")] = r.get("app", 0.5)
        o[i, names.index("cover_dist")] = r.get("cover", 20.0) / cfg.obs_cover_norm
        o[i, names.index("energy")] = r.get("energy", 0.8)
        o[i, names.index("visibility")] = r.get("vis", 1.0)
    return o


def test_rules(cfg3):
    cfg = rr.with_obs_extra(cfg3)
    with pytest.raises(ValueError, match="obs_extra"):
        rr.rule_spec(cfg3, 8, 0.75)
    rows = [dict(), dict(pc=1, dist=5.0), dict(pc=1, dist=10.0, app=0.95), dict(pc=1, dist=10.0, app=0.6),
            dict(pc=1, dist=12.0, app=0.5, cover=3.0), dict(vis=0.5, energy=0.8, cover=0.0),
            dict(vis=0.5, energy=0.8, cover=4.0), dict(vis=1.0, cover=0.0), dict(pc=1, dist=12.0, cover=12.0)]
    o = _rule_obs(cfg, rows)
    pol = lambda spec: ro.build_policy(spec, 0)(o)[:, 0].astype(int).tolist()     # noqa: E731
    assert pol(rr.rule_spec(cfg, 8, 0.75)) == [G, F, F, G, G, G, G, G, G]
    spec = rr.rule_spec(cfg, 8, 0.75)
    spec["wrap"][0]["night_sleep"] = dict(energy=0.5)                       # 거주 규칙은 X(SLEEP)를 쓰지 않는다
    with pytest.raises(ValueError, match="밤 잠"):
        ro.build_policy(spec, 0)
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="freeze")) == [G, F, F, Z, Z, G, G, G, Z]
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="freeze", mode="out")) == [Z, F, F, G, G, Z, Z, Z, G]
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="freeze", mode="cross")) == [G, Z, Z, G, G, G, G, G, G]
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="hide")) == [G, F, F, G, H, G, G, G, G]
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="hide", mode="out")) == [H, F, F, G, G, G, G, H, G]
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="hide", mode="cross")) == [G, H, H, G, G, G, G, G, G]
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="sleep")) == [G, F, F, G, G, S, G, G, G]
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="sleep", mode="out")) == [S, F, F, S, S, G, G, S, S]
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="sleep", mode="cross")) == [G, F, F, G, G, G, S, G, G]
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="graze")) == [G] * 9
    assert pol(rr.rule_spec(cfg, 8, 0.75, x="freeze", mode="out", slots=[0, 5])) == [Z, F, F, G, G, Z, G, G, G]


# --------------------------------------------------------------------- #
# 침입 도구 smoke · 리플레이 훅
# --------------------------------------------------------------------- #


def _invasion_module():
    spec = importlib.util.spec_from_file_location("invasion_r0", ROOT / "results" / "v3" / "r0" / "invasion_r0.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_invasion_tool_smoke(tmp_path, monkeypatch):
    """시드 2개 · 40스텝 · 칸 1개 smoke: 탐색 캐시, 침입 요약·판정 파일. 판정 값은 보지 않는다."""
    inv = _invasion_module()
    cell = "ps0.7_pl_T600"
    cfg = inv.cell_cfg(cell)
    w = World(cfg, seeds=[12000])
    assert w.player_present and w.threat_p_stalk == 0.7 and w.dn_period == 600 and w.obs_dim == 18
    res = inv.search([12000, 12001], 30, 1, tmp_path, grid_theta=[6.0, 8.0], grid_approach=[0.9], cells=[cell])
    assert set(res["table"]) == {"6|0.9", "8|0.9"} and res["best"]["approach"] == 0.9
    monkeypatch.setattr(inv, "_map", lambda jobs, workers: (_ for _ in ()).throw(AssertionError("캐시를 안 썼다")))
    assert inv.search([12000, 12001], 30, 1, tmp_path, grid_theta=[6.0, 8.0], grid_approach=[0.9],
                      cells=[cell]) == json.loads((tmp_path / "search.json").read_text(encoding="utf-8"))
    monkeypatch.undo()
    out = inv.run([12000, 12001], 40, 1, tmp_path, 8.0, 0.75, cells=[cell], behaviors=("freeze", "sleep"))
    assert set(out["summary"]) == {f"{x}|{m}|{cell}" for x in ("freeze", "sleep") for m in inv.MODES} | \
        {f"graze|niche|{cell}"}
    v = out["summary"][f"freeze|out|{cell}"]
    assert v["use_focal"] > 0.3 and v["use_res"] == 0.0 and v["rew"]["n"] == 2
    assert out["gate"]["freeze"]["complete"] and not out["gate"]["hide"]["complete"]
    for name in ("invasion.json", "invasion.md", "gate.json"):
        assert (tmp_path / name).exists()
    assert "smoke" in (tmp_path / "invasion.md").read_text(encoding="utf-8")


def test_replay_hooks_only_when_repertoire_on(cfg3, tmp_path):
    import replay_v2 as R

    w2 = World(load_v2_config(V2_4S_ON), seeds=[0])
    w2.step(np.tile(C2, (w2.N, 1)))
    assert set(R._applied(w2, None)) == {"gait", "vig", "gaze", "look"}
    tracker = R.RespawnTracker(w2.N, 2)
    assert "pred_type" not in R._snapshot(w2, tracker, 0)
    run = R.run_policy(cfg3, {"kind": "fixed", "action": [3.0]}, 12001, 30, 2, label="얼기 요청")
    f = run.frames[-1]
    assert f["beh"].shape == (cfg3.N,) and "pred_type" in f and "beh" in R.series(run.frames)
    labels = [h.get_label() for h in R._legend_handles([run], 2, 2)]
    assert "얼기" in labels and "플레이어(위협)" in labels
    png, _ = R.render_png([run], tmp_path / "v3.png", 20, dpi=40)
    assert png.exists() and R.rep_line([run]) is not None
    assert R.parse_spec("behavior:freeze") == R.parse_spec("behavior:3") == {"kind": "fixed", "action": [3.0]}
    with pytest.raises(ValueError):
        R.parse_spec("behavior:run")


# --------------------------------------------------------------------- #
# 검토 수정 (10-07): 기상 중 사건, 자기 시야 변화, 정수 행동, 은신 배수 계수, 지연 해시, 지표 정의, v1 스트림, 침입 도구
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("jitter", [0, 2])
def test_wake_event_is_decided_when_wake_ends(P, jitter):
    """기상 중(이탈 위상)에 사건이 나면 결정 지연과 무관하게 깨는 스텝이 결정 시점이고 기상 뒤 행동 = 지금 요청이다(사건이
    결정 없이 사라지지 않는다). 잠금이 끝난 t=75 에 GRAZE 를 요청해 t=75~77 기상, t=77 부터 거리 5 의 위협."""
    reqs = [S] * 75 + [G] * 2 + [F] * 20
    h, _ = _drive(P, reqs, lambda t: _o(pc=1, d=5.0) if t >= 77 else _o(), jitter=jitter)
    beh, ph = [x[0] for x in h], [x[1] for x in h]
    assert ph[75:78] == [2, 2, 2] and h[75][4] and not any(x[4] for x in h[76:78])     # t=75 기상 결정, 기상 중 결정 없음
    assert beh[78] == F and h[78][4] and h[78][5]                           # 깨는 스텝에 바로 FLEE(결정 시점)
    assert h[78][1] == 0 and h[79][1] == 1                                  # SLEEP → FLEE 는 놀람이 없다(기상이 지연이다)
    # 위협이 없으면 처음 기상 요청(GRAZE)으로 깨고 GRAZE 잠금이 걸린다(결정 시점 아님)
    h2, _ = _drive(P, reqs, lambda t: _o(), jitter=jitter)
    assert h2[78][0] == G and not h2[78][4] and [x[0] for x in h2[78:90]] == [G] * 12


def test_events_compare_on_narrower_sight(P):
    """E1·E2 는 사건 비교 시야(이번·직전 관측의 행동 시야 배수 중 작은 쪽)로 센 값(*_ev)을 직전 기준값과 비교하고, 기준값은
    실제 관측 값으로 둔다 — 자기 시야가 넓어져 보인 위협은 사건이 아니고, 뒤에 진짜로 새 위협이 오면 사건이다."""
    rs = rep.RepState(1, P, np.array([0.8]), 0.0, 0)
    rs.jitter[:] = 0
    rs.lock_left[:] = 10

    def ev(pc, d):
        return dict(pred_count_ev=np.array([pc]), d_pred_min_ev=np.array([float(d)]), pred_approach_ev=np.array([0.5]))
    res = rep.arbitrate(rs, P, np.array([F]), dict(_o(pc=1, d=7.0), **ev(0, np.inf)))
    assert not res["event"][0] and not res["decide"][0] and rs.prev_pc[0] == 1 and rs.prev_near[0]
    res = rep.arbitrate(rs, P, np.array([F]), _o(pc=1, d=6.0))              # 같은 위협이 다가와도 사건이 아니다
    assert not res["event"][0] and rs.behavior[0] == G
    res = rep.arbitrate(rs, P, np.array([F]), _o(pc=2, d=5.0))              # 새 위협(E1)
    assert res["event"][0] and res["decide"][0] and rs.behavior[0] == F


def _lone(cfg, seed=12000):
    """낮 고정·은신처 없음, 개체 0 은 가운데에서 +x 를 본다(나머지는 구석). 포식자는 `_preds` 로 둔다."""
    w = World(cfg, seeds=[seed])
    w.day_fixed = True
    w._daynight_update()
    c = np.array([w.size / 2, w.size / 2])
    _clear(w, keep=(0,))
    w.pos[0], w.head[0] = c, [1.0, 0.0]
    w._rs.jitter[:] = 0
    return w, c


def _refresh(w):
    w._g = w._geometry()
    rep.perceive(w._rs, w._rp, w._g)
    w._obs = w._obs_from(w._g)


def test_own_sight_widening_is_not_an_event(cfg3):
    """GRAZE(고개 숙임 0.6·see_r = 12) → FREEZE(20)로 시야가 넓어져 거리 16 의 위협이 보여도 사건이 아니다 — FREEZE 잠금 12 가
    그대로 걸린다(검토: 진입의 18% 가 바로 다음 결정에서 E1 을 내 잠금·놀람을 우회했다). 그 뒤 새 위협이 들어오면 사건이다."""
    w, c = _lone(cfg3)
    _preds(w, [c + [16.0, 0.0], c + [-40.0, 0.0]], kind=[PT_CHASER, PT_CHASER], speed=0.0)
    w._rs.lock_left[:] = 0
    _refresh(w)
    assert w._g["pred_count"][0] == 0                                       # GRAZE 시야 12 밖
    req = np.zeros((w.N, 1))
    req[0] = Z
    w.step(req)
    assert w.behavior[0] == Z and w._g["pred_count"][0] == 1 and w._g["pred_count_ev"][0] == 0
    req[0] = F
    beh = []
    for _ in range(11):
        w.step(req)
        beh.append(int(w.behavior[0]))
    assert beh == [Z] * 11                                                  # 잠금 12 동안 FLEE 요청을 받지 않는다
    w.pred_pos[1] = c + [8.0, 2.0]                                          # 진짜로 새 위협(E1)
    _refresh(w)
    w.step(req)
    assert w.behavior[0] == F


def test_random_spec_draws_behavior_ids(cfg3):
    """repertoire 세계의 random 스펙은 정수 행동 번호 0..4 를 고르게 뽑는다(adapt_spec 에 행동 이름을 준다). 연속 [0, 1) 행동
    (행동 이름 없이 만든 random, 학습 정책의 sigmoid 출력)은 세계가 거부한다 — 조용히 늘 GRAZE 가 되지 않는다."""
    w = World(cfg3, seeds=[12000])
    spec = ro.adapt_spec({"kind": "random", "seed": 4}, w.act_dim, w.act_names)
    assert spec == {"kind": "random", "seed": 4, "act_dim": 1, "choices": rep.N_BEHAVIORS}
    pol = ro.build_policy(spec)
    for _ in range(80):
        a = pol(w.observe())
        assert set(np.unique(a)) <= {0.0, 1.0, 2.0, 3.0, 4.0}
        w.step(a)
    s = w.repertoire_stats()
    assert all(s[f"use_{b}"] > 0.0 for b in rep.BEHAVIOR_NAMES)
    cont = ro.build_policy(ro.adapt_spec({"kind": "random", "seed": 4}, w.act_dim))
    with pytest.raises(ValueError, match="정수"):
        w.step(cont(w.observe()))
    v24 = World(load_v2_config(V2_4S_ON), seeds=[0])                        # 다른 세계의 random 스펙은 그대로다
    assert ro.adapt_spec({"kind": "random", "seed": 4}, v24.act_dim, v24.act_names) == \
        {"kind": "random", "seed": 4, "act_dim": 5}


def test_cover_mult_by_behavior(cfg3):
    """M6 은신 배수(은신처 안일 때)는 행동별 yaml 계수 넷이다: 웅크린 HIDE·GRAZE·SLEEP·그 밖(FLEE·FREEZE·가는 중 HIDE)."""
    cfg = _feat(cfg3, "repertoire", cover_mult_sleep=2.0, cover_mult_other=1.2)
    w = World(cfg, seeds=[12000])
    b = np.array([G, F, H, H, Z, S])
    crouch = np.array([False, False, False, True, False, False])
    np.testing.assert_array_equal(rep.cover_mult(w._rp, b, crouch), [1.5, 1.2, 1.2, 2.5, 1.2, 2.0])
    w._rs.behavior[:] = S
    w._rep_step(np.full((w.N, 1), float(S)))
    np.testing.assert_array_equal(w._rep_cover, 2.0)
    # 판정 설정: 은신처 안 SLEEP 은 웅크림과 같은 2.5(10-07 결정 (n)), 그 밖 = 1
    p0 = World(cfg3, seeds=[0])._rp
    assert (p0["cover_mult_sleep"], p0["cover_mult_other"]) == (2.5, 1.0)
    with pytest.raises(ValueError, match="cover_mult_sleep"):
        World(_feat(cfg3, "repertoire", cover_mult_sleep=0.5), seeds=[0])


def test_jitter_is_per_world_and_per_life(cfg3):
    """사건 결정 지연은 세계 시드·슬롯·세대의 해시다: 같은 슬롯도 세계마다 다르고, 리스폰한 개체는 세대 + 1 로 새 지연을 받는다."""
    a, b = World(cfg3, seeds=[12000]), World(cfg3, seeds=[12001])
    zero = np.zeros(a.N, dtype=np.int64)
    np.testing.assert_array_equal(a._rs.jitter, rep.decision_jitter(12000, np.arange(a.N), zero, 3))
    assert not np.array_equal(a._rs.jitter, b._rs.jitter)
    for _ in range(3000):
        _, _, done, _ = a.step(np.zeros((a.N, 1)))
        if done.any():
            break
    d = np.flatnonzero(done)
    assert len(d) and (a._rep_gen[d] == 1).all() and a._rep_gen.sum() == len(d)
    np.testing.assert_array_equal(a._rs.jitter[d], rep.decision_jitter(12000, d, np.ones(len(d), dtype=np.int64), 3))


def test_daynight_rest_and_eat_columns_follow_behavior(cfg3):
    """repertoire 세계의 daynight_stats 휴식·먹기 열은 행동 기준이다: p_rest_cover = P(결정 때 은신처 안 & SLEEP),
    p_eat = P(먹이 셀 & GRAZE | 결정 때 배부름). 손으로 센 값과 같다."""
    class W(World):
        def _daynight_accumulate(self, *args):
            self.dn_pos = self.pos.copy()                                   # 섭식 위치(이동 뒤, 리스폰 전)
            super()._daynight_accumulate(*args)

    w = W(_feat(cfg3, "daynight", periods=[600]), seeds=[12000])
    rng = np.random.default_rng(7)
    n = np.zeros(3)
    rest = np.zeros(3)
    n_pf, eat = np.zeros((3, 2)), np.zeros((3, 2))
    for _ in range(700):
        d = w.dark
        ph = 0 if d <= 0.2 + 1e-9 else (2 if d >= 0.8 - 1e-9 else 1)
        inc = w._g["in_cover"].copy()
        full = (w.energy >= 0.5 * w.cfg.max_energy).astype(int)
        w.step(rng.integers(0, 5, (w.N, 1)).astype(np.float64))
        b = w.behavior
        ix, iy = w._cell_index(w.dn_pos)
        food = w.food_cap[iy, ix] > 0.0
        n[ph] += w.N
        rest[ph] += np.count_nonzero(inc & (b == S))
        np.add.at(n_pf[ph], full, 1)
        np.add.at(eat[ph], full[food & (b == G)], 1)
    s = w.daynight_stats()
    assert n[0] and n[2] and rest[2] > 0
    assert s["p_rest_cover_day"] == pytest.approx(rest[0] / n[0])
    assert s["p_rest_cover_night"] == pytest.approx(rest[2] / n[2])
    assert s["n1"] == pytest.approx(rest[2] / n[2] - rest[0] / n[0])
    for ph, name in ((0, "day"), (2, "night")):
        for k, hf in ((0, "hungry"), (1, "full")):
            if n_pf[ph, k]:
                assert s[f"p_eat_{name}_{hf}"] == pytest.approx(eat[ph, k] / n_pf[ph, k])


def test_v1_stats_action_columns_are_nan(cfg3):
    """repertoire 세계에는 v1 조향 행동 열이 없어 stats() 의 행동 열은 nan 이다(0 이 실측처럼 보이지 않게)."""
    w = World(cfg3, seeds=[12000])
    for _ in range(30):
        w.step(np.zeros((w.N, 1)))
    s = w.stats()
    for k in ("cohesion_mean", "flee_dist_mean", "flee_dist_std", "react_pred", "react_hunger"):
        assert math.isnan(s[k]), k
    assert math.isfinite(s["mean_return"]) and math.isfinite(s["cover_frac"])
    w2 = World(_feat(cfg3, "repertoire", enabled=False), seeds=[12000])
    w2.step(np.tile(C2, (w2.N, 1)))
    assert math.isfinite(w2.stats()["cohesion_mean"])


def test_v1_stream_shape_while_stepping(cfg3):
    """스텝 중간에도 _step_predators_v3 의 v1 스트림 소비는 v2.4s 모양이다: 선회 M_base 개 + (v1 원거리형 배치에 원거리형이
    있으면) 원거리 판정 (M_base, N) 개 — 잠행형이 원거리형을 덮고 플레이어가 있어도."""
    cfg = _feat(cfg3, "threats", player_frac=1.0)
    covered = False
    for seed in (12000, 12001, 12005):
        w = World(cfg, seeds=[seed])
        covered |= bool((w._pred_ranged_v1[:w.M_base] & ~w.pred_ranged[:w.M_base]).any())
        rng = np.random.default_rng(seed)
        for t in range(150):
            if t % 50 == 49:
                probe = copy.deepcopy(w.rng)
                probe.uniform(-w.cfg.pred_wander_turn, w.cfg.pred_wander_turn, w.M_base)
                if w._pred_ranged_v1[:w.M_base].any():
                    probe.random((w.M_base, w.N))
                w._step_predators_v3()
                assert w.rng.bit_generator.state == probe.bit_generator.state, (seed, t)
            w.step(rng.integers(0, 5, (w.N, 1)).astype(np.float64))
    assert covered                                                          # 원거리형을 덮은 세계가 하나는 있다


def test_repertoire_stats_match_hand_counts(cfg3):
    """repertoire_stats 의 사용 비율·전환 수와 슬롯별 전환·깜빡임 수(rep_slot_counts)가 훅으로 손으로 센 값과 같다. 리스폰은
    전환이 아니다(새 개체는 GRAZE 로 시작하므로 첫 스텝에 GRAZE 가 아니면 그 스텝에 전환했다)."""
    w = World(cfg3, seeds=[12003])
    rng = np.random.default_rng(11)
    use = np.zeros(rep.N_BEHAVIORS)
    sw = 0
    prev, prev_done = w.behavior.copy(), np.zeros(w.N, dtype=bool)
    for _ in range(400):
        _, _, done, _ = w.step(rng.integers(0, 5, (w.N, 1)).astype(np.float64))
        b = w.behavior
        use += np.bincount(b, minlength=rep.N_BEHAVIORS)
        sw += int(np.count_nonzero((b != prev) & ~prev_done) + np.count_nonzero(prev_done & (b != G)))
        prev, prev_done = b.copy(), done
    s = w.repertoire_stats()
    for k, name in enumerate(rep.BEHAVIOR_NAMES):
        assert s[f"use_{name}"] == pytest.approx(use[k] / use.sum())
    assert w._rep_switch == sw
    sc = w.rep_slot_counts()
    assert sc["switch"].sum() == w._rep_switch and sc["flicker"].sum() == w._rep_flicker
    assert s["switch_per_sec"] == pytest.approx(sw / (400 * w.N) * 60.0 / w.cfg.policy_interval)


def test_invasion_tool_guards_and_report_columns(tmp_path):
    """사전 등록 결과를 덮지 않는다: 조건이 다른 탐색 캐시는 --force 없이 멈추고, 사전 등록 폴더에는 PREREG 조건만 쓴다.
    침입 요약에는 사건 조건 지표·MDE·희석 보정·깜빡임·이중차 판정이 있다."""
    inv = _invasion_module()
    cell = "ps0.3_np_T600"
    kw = dict(grid_theta=[8.0], grid_approach=[0.9], cells=[cell])
    inv.search([12000, 12001], 30, 1, tmp_path, **kw)
    with pytest.raises(inv.StaleCache, match="force"):
        inv.search([12000, 12001], 31, 1, tmp_path, **kw)
    assert inv.search([12000, 12001], 31, 1, tmp_path, force=True, **kw)["meta"]["steps"] == 31
    for argv in (["run", "--steps", "30"], ["search", "--seeds", "12000"], ["run", "--cells", cell],
                 ["run", "--theta", "8", "--approach", "0.9", "--seeds", "12000"]):
        with pytest.raises(SystemExit):
            inv.main(argv)                                                  # --out 기본값 = 사전 등록 폴더
    with pytest.raises(SystemExit):
        inv.main(["run", "--steps", "30", "--seeds", "12000", "12001", "--cells", cell, "--grid-theta", "8",
                  "--grid-approach", "0.9", "--out", str(tmp_path), "--workers", "1"])   # 다른 조건(31스텝)의 캐시
    out = inv.run([12000, 12001], 80, 1, tmp_path, 8.0, 0.9, cells=[cell], behaviors=("freeze",), flee_check=False)
    v = out["summary"][f"freeze|out|{cell}"]
    for k in ("ev_rew", "ev_pred", "ev_starve", "rew_did"):
        assert set(v[k]) == {"mean", "t", "n", "mde80"}
    assert v["ev_n_f"] > 0 and v["ev_n_r"] > 0 and math.isfinite(v["rew_per_use"])
    assert 0.0 <= v["flicker_f"] <= 1.0 and v["switch_per_sec_f"] > 0.0
    assert set(out["gate_did"]) == set(inv.BEHAVIORS)
    md = (tmp_path / "invasion.md").read_text(encoding="utf-8")
    assert "사건 조건" in md and "이중차 판정" in md and "깜빡임" in md


def test_invasion_gate_low_power_verdict():
    """(1)·(2) 통과, (3)만 실패이고 교차 칸 침입 X 사용 비율이 LOW_USE 미만이면 '판정 불능(검정력 부족)'(통과 아님)."""
    inv = _invasion_module()
    cells = list(inv.CELLS)

    def row(mean, t, use=0.2):
        return dict(rew=dict(mean=mean, t=t, n=40, mde80=None), use_focal=use)
    s = {}
    for c in cells:
        s[f"freeze|niche|{c}"] = row(0.001, 1.0)
        s[f"freeze|out|{c}"] = row(-0.01, -5.0)
        s[f"freeze|cross|{c}"] = row(-0.0001, -0.5, use=0.03)
    g = inv.gate(s, cells)["freeze"]
    assert g["c1"] and g["c2"] and not g["c3"] and not g["pass_"] and g["verdict"] == "low_power"
    for c in cells:
        s[f"freeze|cross|{c}"]["use_focal"] = 0.2
    assert inv.gate(s, cells)["freeze"]["verdict"] == "fail"
