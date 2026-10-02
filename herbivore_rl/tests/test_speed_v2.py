"""V2 1-1 — v2.1 보행 3단(speed) (계획서 4.3·4.4·4.5, 1단계 1-1, 10절 #3·#4).

문턱 경계, 상태별 속력·섭식·대사 값, heading 규칙(정지 시 유지), 에너지 순변화 보상(번식·리스폰 리셋 제외),
speed 끈 설정 = v1 비트 동일(여러 시드·정책), v1 계수로 켠 speed = v1 비트 동일(크기만 바꾸는 경로가 v1 조향·
clamp·heading 을 그대로 쓴다), 켠 상태 결정성·복제, 난수를 쓰지 않음, 보행 통계(gait_stats)의 정의,
행동 5개가 학습(train_v2)·진단(diagnose_v2)·영상(replay_v2)·VecEnv 를 통과한다(짧은 smoke).
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
from env_v2.steering import EPS, normalize, steer
from env_v2.vec_env import MultiWorldVecEnv
from env_v2.world import (ACT_DIM, ACT_SPEED, GAIT_RUN, GAIT_STAT_COLUMNS, GAIT_STOP, GAIT_WALK, World,
                          action_dim, action_names)
from policies.registry import make_policy

V2_1 = ROOT / "configs" / "v2_1.yaml"
NAMES5 = ("forage", "cohesion", "flee_dist", "cover", "speed")
# v2_1.yaml 의 대사 배수 [정지, 걷기, 뛰기]. 10-02 Gate E1-b 통과 계수(B1 r2_5_ew0_5: 뛰기 배수 R 2.5, 걷기 1 고정 →
# c_rest 15/21, c_move 37.5/21). 그 전 제안값은 [0.5, 1, 3.625] 였다.
DRAIN_MULT = (15.0 / 21.0, 1.0, 2.5)
BASE4 = [0.4, 0.8, 0.4, 0.1]

# 작은 롤아웃(1,024)에 v1 batch_size 4096 을 그대로 써서 SB3 가 내는 경고. 테스트 크기 탓이라 끈다.
pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def cfg1():
    return load_v2_config(V2_1)


def _speed(cfg, enabled=True, **kw):
    """v2_1.yaml 의 speed 블록에서 계수 일부만 바꾼 설정."""
    block = dict(cfg.v2["features"]["speed"], enabled=enabled, **kw)
    return cfg.replace(v2=dict(cfg.v2, features={"speed": block}))


def _act(n, speed, base=BASE4):
    a = np.empty((n, 5))
    a[:, :4] = base
    a[:, ACT_SPEED] = speed
    return a


def _no_predators(w):
    """포식자를 없앤다(포획·도주 없음). 기하·관측을 다시 계산한다."""
    w.M = 0
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)
    return w


def _same(d1, d2):
    assert d1.keys() == d2.keys()
    for k in d1:
        a, b = d1[k], d2[k]
        assert a == b or (isinstance(a, float) and math.isnan(a) and math.isnan(b)), k


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


def test_v2_1_config_is_v2_plus_speed(cfg1):
    """v2_1.yaml = v2.yaml + speed (계수 전부) + 포식자 속도 범위(E1-b, 10-02). 학습 설정은 같고, v1 키는
    rand.pred_speed_mult 하나만 [0.8, 1.2] → [0.6, 0.95] 로 다르다(rand 의 다른 하위 키는 v1 그대로). 행동은 5개가 된다."""
    v20 = load_v2_config()
    assert cfg1.v2["version"] == "2.1"
    assert cfg1.v2["train"] == v20.v2["train"]
    v1 = load_config().to_dict()
    for k, v in v1.items():
        if k != "rand":
            assert getattr(cfg1, k) == v, k
    assert cfg1.rand == dict(v1["rand"], pred_speed_mult=[0.6, 0.95])
    assert [k for k in v1["rand"] if cfg1.rand[k] != v1["rand"][k]] == ["pred_speed_mult"]
    assert v1["rand"]["pred_speed_mult"] == [0.8, 1.2]           # v1 configs/default.yaml 은 그대로
    assert set(cfg1.v2["features"]["speed"]) == {"enabled"} | set(F.PARAM_KEYS["speed"])
    assert "speed" in F.IMPLEMENTED                     # test_features_v2 의 자기 스트림 검사가 speed 도 돈다
    w = World(cfg1, seeds=[0])
    assert w.features.active == ("speed",)
    assert w.act_names == NAMES5 == action_names(cfg1) and w.act_dim == 5 == action_dim(cfg1)
    assert World(v20, seeds=[0]).act_dim == ACT_DIM == action_dim(v20) == 4
    sp = w._sp
    assert sp["thresholds"] == (1.0 / 3.0, 2.0 / 3.0)   # yaml 의 0.333…·0.666… 는 float64 1/3·2/3 그대로
    np.testing.assert_array_equal(sp["speed"], [0.0, 0.4, 1.0])
    np.testing.assert_array_equal(sp["eat"], [1.0, 0.5, 0.0])
    np.testing.assert_allclose(sp["drain_mult"], DRAIN_MULT, rtol=0, atol=1e-15)
    assert sp["net_energy_reward"] is True


def test_v2_1_predator_speeds_sit_between_walk_and_run(cfg1):
    """E1-b(10-02): 근접형 속력 ×0.6~0.95 → 걷기(0.4) < 근접형 < 뛰기(1.0). 원거리형은 pred_ranged_speed_mult(0.6,
    v1 그대로)를 더 곱해 ×0.36~0.57 이고 뛰기보다 느리다. 같은 시드의 세계 배치는 v1 과 같고 배수만
    0.6 + 0.875·(v1 배수 − 0.8)로 옮겨진다(같은 uniform 한 번이라 v1 난수열을 더 쓰지 않는다)."""
    gait = cfg1.v2["features"]["speed"]["gait_speed"]
    assert cfg1.pred_ranged_speed_mult == load_config().pred_ranged_speed_mult == 0.6
    slow_ranged = 0
    for seed in range(40):
        w, w1 = World(cfg1, seeds=[seed]), WorldV1(load_config(), seeds=[seed])
        assert 0.6 <= w.pred_speed_mult <= 0.95
        assert w.pred_speed_mult == pytest.approx(0.6 + 0.875 * (w1.pred_speed_mult - 0.8), abs=1e-12)
        for k in ("size", "M", "ranged_frac", "cover_frac_target", "food_regen_mult"):
            assert getattr(w, k) == getattr(w1, k), k
        for k in ("pos", "head", "energy", "pred_pos", "pred_ranged", "food"):
            np.testing.assert_array_equal(getattr(w, k), getattr(w1, k), err_msg=k)
        rel = w.pred_speed / cfg1.herb_speed
        melee, ranged = rel[~w.pred_ranged], rel[w.pred_ranged]
        assert ((gait[1] < melee) & (melee < gait[2])).all()
        np.testing.assert_allclose(ranged, w.pred_speed_mult * 0.6, rtol=1e-12)
        assert ((0.36 - 1e-12 <= ranged) & (ranged < gait[2])).all()
        slow_ranged += int(w.pred_speed_mult < 2.0 / 3.0)       # 원거리형이 걷기보다 느린 세계
    assert 0 < slow_ranged < 40


def _v1_cfg_of(cfg):
    """cfg 의 v1 키(overrides 를 거친 값)로 만든 v1 설정. v2_1.yaml 은 E1-b 로 rand.pred_speed_mult 가 v1 과 다르다."""
    v1 = load_config()
    return v1.replace(**{k: getattr(cfg, k) for k in v1.to_dict()})


@pytest.mark.parametrize("kw", [
    {"thresholds": [0.7, 0.3]}, {"thresholds": [-0.1, 0.5]}, {"thresholds": [0.3, 1.2]}, {"thresholds": [0.5]},
    {"thresholds": 0.5},
    {"gait_speed": [0.1, 0.4, 1.0]},                     # 정지는 0
    {"gait_speed": [0.0, 0.0, 1.0]}, {"gait_speed": [0.0, 0.6, 0.4]}, {"gait_speed": [0.0, 0.4]},
    {"gait_eat": [1.0, -0.5, 0.0]}, {"gait_eat": [1.0, 0.5]},
    {"c_rest": -0.1}, {"c_move": float("nan")}, {"c_rest": True},
    {"net_energy_reward": 1}, {"net_energy_reward": "true"},
])
def test_speed_params_are_checked(cfg1, kw):
    with pytest.raises(ValueError):
        World(_speed(cfg1, **kw), seeds=[0])


def test_speed_needs_every_coefficient(cfg1):
    """계수는 yaml 이 유일한 원본이다. 켤 때 하나라도 빠지면 읽을 때 실패한다(코드 기본값 없음)."""
    for key in F.PARAM_KEYS["speed"]:
        block = {k: v for k, v in cfg1.v2["features"]["speed"].items() if k != key}
        with pytest.raises(ValueError, match=key):
            F.parse_features({"speed": block})


# --------------------------------------------------------------------- #
# 문턱 · 속력 · 섭식 · 대사 · heading
# --------------------------------------------------------------------- #


def test_gait_thresholds_boundaries(cfg1):
    """a < 1/3 정지, a < 2/3 걷기, 그 이상 뛰기. 문턱 값 자체는 위 상태다. 방향이 없으면 명령과 무관하게 정지."""
    from train_v2 import gait_of

    w = World(cfg1, seeds=[10000])
    t0, t1 = w._sp["thresholds"]
    a = np.array([0.0, np.nextafter(t0, 0.0), t0, 0.5, np.nextafter(t1, 0.0), t1, 1.0])
    want = [0, 0, 1, 1, 1, 2, 2]
    rng_state = w.rng.bit_generator.state
    v = w._gait_step(np.tile([[0.6, 0.0]], (len(a), 1)), a)
    np.testing.assert_array_equal(w.gait_cmd, want)
    np.testing.assert_array_equal(w.gait, want)
    np.testing.assert_allclose(np.linalg.norm(v, axis=1), 0.6 * np.array([0, 0, 0.4, 0.4, 0.4, 1, 1]))
    np.testing.assert_array_equal(gait_of(a, (t0, t1)), want)          # 학습 기록도 같은 식
    assert w.rng.bit_generator.state == rng_state                     # 보행은 v1 스트림을 쓰지 않는다

    v = w._gait_step(np.zeros((3, 2)), np.array([0.0, 0.5, 1.0]))      # 조향 합이 0 → 갈 방향이 없다
    np.testing.assert_array_equal(w.gait_cmd, [GAIT_STOP, GAIT_WALK, GAIT_RUN])
    np.testing.assert_array_equal(w.gait, [GAIT_STOP] * 3)
    assert (v == 0.0).all()


def _expected_intake(w, pos, e_drained, mult):
    """`_eat` 를 손으로 다시 계산: 흡수 가능량 want × 섭식 배수 → 셀 수요 → 잔량 비례 배분."""
    c = w.cfg
    want = np.clip((c.max_energy - e_drained) / c.food_energy_per_unit, 0.0, c.food_eat_rate) * mult
    ix, iy = w._cell_index(pos)
    flat = iy * w.gw + ix
    demand = np.bincount(flat, weights=want, minlength=w.gw * w.gw)
    taken = np.minimum(demand, w.food.reshape(-1))
    frac = np.divide(taken, demand, out=np.zeros_like(demand), where=demand > 0)
    gain = want * frac[flat]
    return np.minimum(e_drained + gain * c.food_energy_per_unit, c.max_energy) - e_drained


@pytest.mark.parametrize("seed", [10000, 636])
@pytest.mark.parametrize("a_speed, gait", [(0.0, GAIT_STOP), (0.5, GAIT_WALK), (1.0, GAIT_RUN)])
def test_gait_speed_eat_metabolism_and_heading(cfg1, seed, a_speed, gait):
    """4.4 표: 속력 0/0.4/1.0 × herb_speed, 섭식 배수 1/0.5/0, 대사 energy_drain × (c_rest + c_move·(v/hs)²),
    heading 은 정지면 유지, 이동이면 이동 방향(= v1 조향 방향). 위치는 v1 과 같이 벽에서 자른다."""
    w = _no_predators(World(cfg1, seeds=[seed]))
    c, sp = w.cfg, w._sp
    a = _act(w.N, a_speed)
    v1 = steer(w._g, a, c)                                   # v1 조향 속도 (크기 herb_speed 또는 0)
    has_dir = np.linalg.norm(v1, axis=1) > EPS
    g = np.where(has_dir, gait, GAIT_STOP)
    pos0, head0, e0 = w.pos.copy(), w.head.copy(), w.energy.copy()
    pos = np.clip(pos0 + v1 * sp["speed"][g][:, None], 0.0, w.size)     # 이동 뒤 위치(섭식 셀)
    e_drained = e0 - c.energy_drain * sp["drain_mult"][g]
    intake = _expected_intake(w, pos, e_drained, sp["eat"][g])        # 섭식은 이동 뒤·재생 전 먹이로 한다

    _, rew, done, _ = w.step(a)
    assert not done.any()                                    # 포식자 없음, 에너지 0.5 → 사망·번식 없음
    np.testing.assert_array_equal(w.gait, g)
    np.testing.assert_array_equal(w.gait_cmd, np.full(w.N, gait))
    speed = np.linalg.norm(w.vel, axis=1)
    np.testing.assert_allclose(speed, sp["speed"][g] * c.herb_speed, rtol=1e-12, atol=0)
    np.testing.assert_array_equal(w.pos, pos)
    moving = g != GAIT_STOP
    np.testing.assert_array_equal(w.head[~moving], head0[~moving])              # 정지: heading 유지
    np.testing.assert_allclose(w.head[moving], normalize(v1)[moving], atol=1e-12)  # 이동: 이동 방향

    drain = c.energy_drain * (sp["c_rest"] + sp["c_move"] * (speed / c.herb_speed) ** 2)
    np.testing.assert_allclose(drain, c.energy_drain * sp["drain_mult"][g], rtol=1e-12)
    np.testing.assert_allclose(w.energy, e_drained + intake, rtol=0, atol=1e-15)
    if gait == GAIT_RUN:                                     # 뛰기는 먹지 않는다: 에너지 = 대사만
        np.testing.assert_array_equal(w.energy[has_dir], (e0 - c.energy_drain * DRAIN_MULT[GAIT_RUN])[has_dir])
    if gait == GAIT_STOP:
        np.testing.assert_array_equal(w.pos, pos0)
    np.testing.assert_allclose(rew, c.rew_alive + (w.energy - e0), atol=1e-15)   # 순변화 보상 (#4)


def test_eat_multiplier_scales_the_absorbable_want(cfg1):
    """섭식 배수는 흡수 가능량으로 자른 want 에 곱한다. 0 인 개체는 셀 수요가 없어 같은 셀 개체 몫을 줄이지 않는다."""
    w = World(cfg1, seeds=[10000])
    k = np.flatnonzero(w.food_cap.reshape(-1) > 0.5)[0]
    w.pos[:] = ((k % w.gw) + 0.5) * w.cfg.food_cell, ((k // w.gw) + 0.5) * w.cfg.food_cell   # 모두 셀 k
    e = np.full(w.N, 0.2)
    mult = np.where(np.arange(w.N) % 2 == 0, 1.0, 0.0)
    w.food.reshape(-1)[k] = 1.0
    gain = w._eat(e, mult)
    want = min((1.0 - 0.2) / 0.5, w.cfg.food_eat_rate)
    n_eat = int(mult.sum())
    np.testing.assert_allclose(gain[mult == 0.0], 0.0)
    np.testing.assert_allclose(gain[mult == 1.0], min(want, 1.0 / n_eat))   # 잔량 1 을 먹는 개체끼리만 나눈다


# --------------------------------------------------------------------- #
# 에너지 보상 (#4)
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("net", [True, False])
def test_energy_reward_net_change_excludes_repro_and_respawn(cfg1, net):
    """순변화 = e_new − e_prev (대사 포함). 번식 리셋(→ init_energy)과 리스폰(→ init_energy)은 보상에 들어가지 않는다.
    끄면 v1 획득량(먹이로 얻은 에너지, 뛰기는 0). 뛰는 개체로 섭취를 0 에 고정해 손으로 센다."""
    c = cfg1
    w = _no_predators(World(_speed(c, net_energy_reward=net), seeds=[10000]))
    e0 = np.full(w.N, 0.6)
    e0[:10] = 0.95                     # 뛰어도 0.9 위 → 번식 → 0.5 로 리셋
    e0[10:20] = 0.001                  # 뛰면 0 아래 → 아사 → 리스폰 0.5
    w.energy = e0.copy()
    a = _act(w.N, 1.0)
    has_dir = np.linalg.norm(steer(w._g, a, c), axis=1) > EPS
    _, rew, done, _ = w.step(a)
    e_new = e0 - c.energy_drain * DRAIN_MULT[GAIT_RUN]
    term = (e_new - e0) if net else np.zeros(w.N)
    want = c.rew_alive + term + c.rew_repro * (e_new > c.repro_threshold) + c.rew_death * (e_new <= 0.0)
    m = has_dir
    np.testing.assert_allclose(rew[m], want[m], atol=1e-12)
    assert done[10:20][m[10:20]].all() and not done[:10].any()
    np.testing.assert_array_equal(w.energy[:20][m[:20]], c.init_energy)        # 리셋된 값은 보상과 무관


def test_net_reward_matches_energy_change_and_v1_reward_is_intake(cfg1):
    """걷는 세계(먹으면서 대사): 순변화 보상 − 생존 = 에너지 변화, 획득량 보상 − 생존 = 에너지 변화 + 대사."""
    c = cfg1
    for net in (True, False):
        w = _no_predators(World(_speed(c, net_energy_reward=net), seeds=[636]))
        for _ in range(5):
            e0 = w.energy.copy()
            _, rew, done, _ = w.step(_act(w.N, 0.5))
            ok = ~done & (w.repro_cd != c.repro_cd)                # 이번 스텝에 죽거나 번식하지 않은 개체
            drain = c.energy_drain * w._sp["drain_mult"][w.gait]
            got = rew[ok] - c.rew_alive
            want = (w.energy - e0)[ok] + (0.0 if net else drain[ok])
            np.testing.assert_allclose(got, want, atol=1e-15)


# --------------------------------------------------------------------- #
# v1 과의 관계 · 결정성 · 난수
# --------------------------------------------------------------------- #

SPECS4 = [{"kind": "fixed", "action": [0.3, 0.8, 0.4, 0.1]}, {"kind": "utility"}, {"kind": "random", "seed": 3}]


@pytest.mark.parametrize("seed", [0, 636, 10000])
@pytest.mark.parametrize("spec", SPECS4, ids=["fixed", "utility", "random"])
def test_speed_off_matches_v1_bitwise(cfg1, seed, spec):
    """v2_1.yaml 에서 speed 만 끈 설정 = 같은 v1 키(overrides 를 거친 값, E1-b 포식자 속도 포함)의 v1 World
    (관측·통계 10열·위치·heading·에너지 비트 동일). 훅도 없다."""
    w2 = World(_speed(cfg1, enabled=False), seeds=[seed])
    assert w2.features.active == () and w2.act_dim == 4
    assert getattr(w2, "gait", None) is None                 # replay_v2 가 v2.0 과 같이 그린다
    v1 = WorldV1(_v1_cfg_of(cfg1), seeds=[seed])
    p1, p2 = make_policy(spec), make_policy(spec)
    for _ in range(300):
        o1, o2 = v1.observe(), w2.observe()
        np.testing.assert_array_equal(o1, o2)
        v1.step(p1(o1))
        w2.step(p2(o2))
    assert v1.stats() == w2.stats()
    for k in ("pos", "head", "energy", "pred_pos", "food"):
        np.testing.assert_array_equal(getattr(v1, k), getattr(w2, k), err_msg=k)


V1_LIKE = dict(gait_speed=[0.0, 1.0, 1.0], gait_eat=[1.0, 1.0, 1.0], c_rest=1.0, c_move=0.0,
               net_energy_reward=False)


@pytest.mark.parametrize("seed", [0, 636, 10000])
@pytest.mark.parametrize("spec", SPECS4, ids=["fixed", "utility", "random"])
def test_speed_on_with_v1_coefficients_matches_v1_bitwise(cfg1, seed, spec):
    """speed 를 켜도 '늘 v1 속력(걷기·뛰기 1.0), 섭식 1, 대사 c_rest 1·c_move 0, v1 획득량 보상'이면 v1 과 비트 동일.
    보행이 v1 조향 속도의 크기만 바꾸고 clamp·heading·섭식·보상 줄을 v1 그대로 쓴다는 확인이다. 방향이 없는 개체의
    '정지'도 v1 과 같다(v = 0, 섭식 1, 대사 1). speed 행동은 [1/3, 1) 에서 뽑는다(정지 명령은 v1 에 없다).
    v1 쪽은 같은 v1 키(overrides 를 거친 값, E1-b 포식자 속도 포함)로 만든다."""
    w2 = World(_speed(cfg1, **V1_LIKE), seeds=[seed])
    v1 = WorldV1(_v1_cfg_of(cfg1), seeds=[seed])
    p1, p2 = make_policy(spec), make_policy(spec)
    rng = np.random.default_rng(seed)
    for _ in range(300):
        o1, o2 = v1.observe(), w2.observe()
        np.testing.assert_array_equal(o1, o2)
        v1.step(p1(o1))
        w2.step(np.c_[p2(o2), rng.uniform(1.0 / 3.0, 1.0, w2.N)])
    assert v1.stats() == w2.stats()
    for k in ("pos", "head", "energy", "pred_pos", "food"):
        np.testing.assert_array_equal(getattr(v1, k), getattr(w2, k), err_msg=k)


def test_speed_world_is_deterministic_and_clones_continue(cfg1):
    """켠 상태: 같은 시드·같은 정책이면 같은 궤적·통계. pickle·deepcopy 한 세계는 이어서 같게 돈다. 난수 스트림 0개."""
    spec = ro.adapt_spec({"kind": "random", "seed": 2}, 5)
    a, b = World(cfg1, seeds=[636]), World(cfg1, seeds=[636])
    pa, pb = ro.build_policy(spec), ro.build_policy(spec)
    for _ in range(200):
        oa, ra, da, _ = a.step(pa(a.observe()))
        ob, rb, db, _ = b.step(pb(b.observe()))
        np.testing.assert_array_equal(oa, ob)
        np.testing.assert_array_equal(ra, rb)
        np.testing.assert_array_equal(da, db)
    assert a.stats() == b.stats()
    _same(a.gait_stats(), b.gait_stats())
    clones = [pickle.loads(pickle.dumps(a)), copy.deepcopy(a)]
    act = _act(a.N, 0.5)
    for _ in range(50):
        a.step(act)
        for c in clones:
            c.step(act)
    for c in clones:
        np.testing.assert_array_equal(c.pos, a.pos)
        np.testing.assert_array_equal(c.gait, a.gait)
        _same(c.gait_stats(), a.gait_stats())
    assert a._feature_rngs == {}                             # speed 는 난수를 쓰지 않는다 (규칙 1)


def test_wrong_action_width_is_refused(cfg1):
    """행동 4개(v1 정책)를 speed 세계에, 5개를 v2.0 세계에 넣으면 멈춘다(보행 열을 조용히 무시하지 않는다)."""
    w = World(cfg1, seeds=[0])
    with pytest.raises(ValueError, match="speed"):
        w.step(np.full((w.N, 4), 0.5))
    with pytest.raises(ValueError, match="Utility"):
        ro.rollout(cfg1, make_policy({"kind": "utility"}), 10000, 3)
    w0 = World(load_v2_config(), seeds=[0])
    with pytest.raises(ValueError):
        w0.step(np.full((w0.N, 5), 0.5))


# --------------------------------------------------------------------- #
# 보행 통계 (gait_stats)
# --------------------------------------------------------------------- #


def _rule(obs):
    """상태 의존 규칙: 포식자 가까우면 뛰고, 배고프면 멈추고, 아니면 걷는다."""
    a = np.tile(BASE4 + [0.5], (len(obs), 1))
    a[obs[:, 4] < 0.5, ACT_SPEED] = 0.0
    a[obs[:, 2] < 0.5, ACT_SPEED] = 1.0
    return a


@pytest.mark.parametrize("seed", [10000, 10003])
def test_gait_stats_match_hand_counts(cfg1, seed):
    """gait_stats 를 스텝마다 손으로 센 값과 맞춘다: 보행 비율(실제·명령), 방향 없음 정지, energy<0.5, B1(거리 구간),
    B2, B8(리스폰 개체는 잇지 않는다, 1스텝 = 8/60초), 섭취·대사, 아사 비중."""
    w = World(cfg1, seeds=[seed])
    c, T = w.cfg, 400
    gn, cn = np.zeros(3), np.zeros(3)
    stall = hungry = 0
    b1n, b1r, b2n, b2s = np.zeros(4), np.zeros(4), np.zeros(2), np.zeros(2)
    sw, swc, sws = 0, 0, 0
    prev = np.full((2, w.N), -1)
    drain = 0.0
    for _ in range(T):
        d = w._g["d_pred_min"] / c.see_r
        e0 = w.energy.copy()
        _, _, done, _ = w.step(_rule(w.observe()))
        g, cmd = w.gait.astype(int), w.gait_cmd.astype(int)
        gn += np.bincount(g, minlength=3)
        cn += np.bincount(cmd, minlength=3)
        stall += int(((cmd != 0) & (g == 0)).sum())
        h = e0 < 0.5
        hungry += int(h.sum())
        bins = np.where(np.isfinite(d), np.where(d < 0.25, 1, np.where(d < 0.5, 2, 3)), 0)
        for k in range(4):
            b1n[k] += (bins == k).sum()
            b1r[k] += ((bins == k) & (cmd == 2)).sum()
        for k, m in enumerate((h, ~h)):
            b2n[k] += m.sum()
            b2s[k] += (m & (cmd == 0)).sum()
        same = prev[0] >= 0
        sws += same.sum()
        sw += (same & (prev[0] != g)).sum()
        swc += (same & (prev[1] != cmd)).sum()
        prev = np.stack([g, cmd])
        prev[:, done] = -1
        dr = c.energy_drain * w._sp["drain_mult"][w.gait]
        drain += dr.sum()
    n = T * w.N
    s = w.gait_stats()
    assert tuple(s) == GAIT_STAT_COLUMNS
    np.testing.assert_allclose([s["stop_frac"], s["walk_frac"], s["run_frac"]], gn / n)
    np.testing.assert_allclose([s["stop_frac_cmd"], s["walk_frac_cmd"], s["run_frac_cmd"]], cn / n)
    assert s["stall_frac"] == pytest.approx(stall / n) and s["hungry_frac"] == pytest.approx(hungry / n)
    assert b1n[1] + b1n[2] > 0 and b2n.min() > 0, "이 시드에서 조건 표본이 있어야 한다"
    p = b1r / np.maximum(b1n, 1)
    assert s["b1"] == pytest.approx((b1r[1] + b1r[2]) / (b1n[1] + b1n[2]) - p[0])
    assert [s["p_run_unseen"], s["p_run_d025"], s["p_run_d050"], s["p_run_d100"]] == pytest.approx(
        [p[k] if b1n[k] else float("nan") for k in range(4)], nan_ok=True)
    assert s["b2"] == pytest.approx(b2s[0] / b2n[0] - b2s[1] / b2n[1])
    assert s["b8"] == pytest.approx(sw / sws * 60 / 8) and s["b8_cmd"] == pytest.approx(swc / sws * 60 / 8)
    assert s["drain_per_step"] == pytest.approx(drain / n)
    assert s["intake_per_step"] > 0.0
    deaths = w._pred_deaths + w._starve_deaths
    assert s["starve_share"] == pytest.approx(w._starve_deaths / deaths if deaths else float("nan"), nan_ok=True)
    assert s["b1"] > 0.5 and s["b2"] > 0.0                     # 규칙 정책이니 조건부 차이가 크다


def test_constant_policy_has_zero_conditional_gait_differences(cfg1):
    """상수 정책(C1·C2 꼴)은 B1·B2 가 구성상 0 이고 명령 보행이 바뀌지 않는다(B8_cmd 0) — 6.3 판정 규칙의 전제."""
    w = World(cfg1, seeds=[10000])
    for _ in range(300):
        w.step(_act(w.N, 0.9))
    s = w.gait_stats()
    assert s["b1"] == 0.0 and s["b2"] == 0.0 and s["b8_cmd"] == 0.0
    assert s["run_frac_cmd"] == 1.0 and s["run_frac"] + s["stall_frac"] == pytest.approx(1.0)


def test_gait_stats_only_in_speed_worlds_and_rollout_rows(cfg1):
    """gait_stats 는 speed 세계에만 있다. 롤아웃 행에는 speed 세계만 보행 열이 붙는다(v2.0 행은 예전 열 그대로)."""
    with pytest.raises(ValueError):
        World(load_v2_config(), seeds=[0]).gait_stats()
    r1 = ro.rollout(cfg1, ro.build_policy({"kind": "fixed", "action": BASE4 + [0.5]}), 10000, 30, tail=0)
    r0 = ro.rollout(load_v2_config(), ro.build_policy({"kind": "fixed", "action": BASE4}), 10000, 30, tail=0)
    assert set(ro.GAIT_COLUMNS) <= set(r1) and not set(ro.GAIT_COLUMNS) & set(r0)
    assert r1["_act_sum"].shape == (5,) and r1["walk_frac_cmd"] == 1.0


# --------------------------------------------------------------------- #
# 5차원 행동이 VecEnv · 학습 · 진단 · 영상 도구를 통과한다 (smoke)
# --------------------------------------------------------------------- #


def test_vec_env_action_space_follows_config(cfg1):
    venv = MultiWorldVecEnv(cfg1, num_worlds=2, meta_seed=0)
    assert venv.action_space.shape == (5,) and venv.act_names == NAMES5
    obs, rew, done, _ = venv.step(np.zeros((venv.num_envs, 5), dtype=np.float32))   # sigmoid(0) = 0.5 → 걷기
    assert obs.shape == (venv.num_envs, 7)
    assert (np.concatenate([w.gait_cmd for w in venv.worlds]) == GAIT_WALK).all()
    with pytest.raises(ValueError):
        venv.step(np.zeros((venv.num_envs, 4), dtype=np.float32))
    assert MultiWorldVecEnv(load_v2_config(), num_worlds=1).action_space.shape == (4,)


def test_gait_probs_matches_sampling():
    """학습 시작 분포 계산(가우시안 → [-3,3] 자르기 → sigmoid → 문턱)이 표본과 같다. μ 0·σ 1 이면 걷기 2Φ(ln 2) − 1."""
    from train_v2 import gait_of, gait_probs

    th = (1.0 / 3.0, 2.0 / 3.0)
    walk = math.erf(math.log(2.0) / math.sqrt(2.0))           # 2Φ(ln 2) − 1 ≈ 0.5117
    np.testing.assert_allclose(gait_probs([0.0], [1.0], th)[0], [(1 - walk) / 2, walk, (1 - walk) / 2], atol=1e-12)
    assert walk == pytest.approx(0.5117, abs=1e-4)                   # 계획서 4.7 "걷기 확률 약 51%"
    rng = np.random.default_rng(0)
    for mu, sd in ((0.0, 1.0), (2.5, 1.0), (-1.0, 0.3), (3.5, 2.0)):
        raw = np.clip(mu + sd * rng.standard_normal(200_000), -3.0, 3.0)
        emp = np.bincount(gait_of(1.0 / (1.0 + np.exp(-raw)), th), minlength=3) / len(raw)
        np.testing.assert_allclose(gait_probs([mu], [sd], th)[0], emp, atol=5e-3)


TINY = {"version": "2.1", "overrides": {}, "train": {"num_worlds": 1, "reset_interval": 4000, "rollout_world_steps": 8}}


@pytest.fixture(scope="module")
def tiny_speed_model(tmp_path_factory):
    """v2_1.yaml 의 speed 블록 그대로, 세계 1개 × 롤아웃 8스텝으로 1회 학습한 모델과 그 설정."""
    import train_v2

    d = tmp_path_factory.mktemp("speed_model")
    raw = yaml.safe_load(V2_1.read_text(encoding="utf-8"))
    cfg_path = d / "tiny_v2_1.yaml"
    cfg_path.write_text(yaml.safe_dump(dict(TINY, features=raw["features"]), allow_unicode=True), encoding="utf-8")
    out = d / "m.zip"
    assert train_v2.main(["--steps", "1", "--seed", "0", "--config", str(cfg_path), "--out", str(out),
                          "--tb", str(d / "tb"), "--threads", "1"]) == 0
    return cfg_path, out


def test_train_v2_learns_five_actions_from_plan_init(tiny_speed_model):
    """정책 출력 5개. 학습 전 마지막 층 speed 편향 0, log_std 0 → 걷기 약 51% (계획서 4.7 초기화)."""
    from stable_baselines3 import PPO

    _, out = tiny_speed_model
    m = PPO.load(out, device="cpu")
    assert m.action_space.shape == (5,) and m.policy.action_net.out_features == 5
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["act_names"] == list(NAMES5) and meta["v2"]["version"] == "2.1"
    ip = meta["init_policy"]
    assert ip["action_bias"][ACT_SPEED] == 0.0 and ip["log_std"][ACT_SPEED] == 0.0
    assert abs(ip["speed"]["mu_mean"]) < 0.05                       # action_net 가중치 gain 0.01 → μ ≈ 편향
    walk = math.erf(math.log(2.0) / math.sqrt(2.0))
    assert ip["speed"]["gait_prob"]["walk"] == pytest.approx(walk, abs=0.01)


def test_diagnose_handles_five_actions(tiny_speed_model, tmp_path, monkeypatch):
    """ablate(C1·C3-speed·C1′, 결정·확률 모드), constsearch(C2 짧은 탐색, C2-seg speed 구간별)이 행동 5개로 돈다.
    Utility 참고 행은 빠지고, 결과에 보행 지표와 행동 이름이 남는다. 길이가 틀린 상수·Utility 는 멈춘다."""
    import diagnose_v2 as dg

    monkeypatch.setattr(dg, "CACHE", tmp_path / "cache")
    _, model = tiny_speed_model
    common = ["--config", str(V2_1), "--eval-seeds", "10000", "10001", "--eval-steps", "40", "--tail", "0",
              "--calib-seeds", "0", "--calib-steps", "30", "--workers", "1"]

    assert dg.main(["ablate", "--model", str(model), "--out", str(tmp_path / "abl")] + common) == 0
    d = json.loads((tmp_path / "abl" / "ablate.json").read_text(encoding="utf-8"))
    assert d["meta"]["act_names"] == list(NAMES5)
    assert list(d["per_seed"]) == ["C0", "C1", "C3-forage", "C3-cohesion", "C3-flee_dist", "C3-cover",
                                   "C3-speed", "C1'"]                  # Utility(4개) 참고 행 없음
    assert len(d["controls"]["C1"]["spec"]["action"]) == 5 and "speed" in d["calib"]["mean_action"]
    assert {"walk_frac", "b1", "b2", "b8", "hungry_frac"} <= set(d["controls"]["C0"]["mean"])
    assert "보행 지표" in (tmp_path / "abl" / "ablate.md").read_text(encoding="utf-8")

    assert dg.main(["ablate", "--model", str(model), "--act-mode", "stochastic", "--no-utility",
                    "--out", str(tmp_path / "sto")] + common) == 0
    s = json.loads((tmp_path / "sto" / "ablate.json").read_text(encoding="utf-8"))
    assert s["meta"]["act_mode"] == "stochastic" and s["per_seed"]["C0"] != d["per_seed"]["C0"]

    # C2: 짧은 탐색 (기본 시작점 = C1 평균 행동 5개, v1 학습 전 최고 상수 + speed 0.5)
    assert dg.main(["constsearch", "--model", str(model), "--out", str(tmp_path / "abl"), "--trials", "2",
                    "--top-k", "1", "--search-seeds", "0", "--search-steps", "20", "--rescore-seeds", "100",
                    "--rescore-steps", "20", "--objective", "mean_return"] + common) == 0
    c2 = json.loads((tmp_path / "abl" / "constsearch.json").read_text(encoding="utf-8"))
    assert len(c2["best"]) == 5 and c2["names"] == list(NAMES5)
    assert c2["search"]["enqueued"][1] == dg.V1_PRETRAIN_BEST + [0.5]

    # C2-seg (Gate E1 꼴): (d_pred < 0.5) × (energy < 0.5), speed 만 구간별. 바탕은 같은 디렉터리의 C2
    assert dg.main(["constsearch", "--model", str(model), "--out", str(tmp_path / "abl"), "--seg-bins", "2:0.5",
                    "4:0.5", "--seg-dims", "speed", "--const-action", "0.9", "0.9", "0.1", "0.5"] + common) == 0
    seg = json.loads((tmp_path / "abl" / "constsearch_seg.json").read_text(encoding="utf-8"))
    assert seg["dims"] == [ACT_SPEED] and np.shape(seg["best_table"]) == (4, 1)
    assert seg["base_action"] == c2["best"] and "vs_C2" in seg["eval"]
    assert "speed" in (tmp_path / "abl" / "constsearch_seg.md").read_text(encoding="utf-8")

    P = dg.build_parser()
    for argv in (["ablate", "--policy", "fixed", "--action", "0.1", "0.2", "0.3", "0.4"],     # 4개
                 ["ablate", "--policy", "utility"]):
        with pytest.raises(SystemExit):
            dg.Ctx(P.parse_args(argv + ["--config", str(V2_1)]))
    with pytest.raises(SystemExit):
        dg.main(["constsearch", "--policy", "fixed", "--action"] + ["0.5"] * 5
                + ["--const-action", "0.1", "0.2", "0.3", "0.4", "--out", str(tmp_path / "x")] + common)
    ctx = dg.Ctx(P.parse_args(["ablate", "--policy", "random", "--config", str(V2_1)]))
    assert ctx.spec == {"kind": "random", "seed": 0, "act_dim": 5}
    assert dg.Ctx(P.parse_args(["ablate", "--policy", "random"])).spec == {"kind": "random", "seed": 0}


def test_wrappers_and_stochastic_mode_keep_five_actions(tiny_speed_model):
    """C3-speed(행동 고정)·C1′(순열)·C2-seg(speed 구간별)·확률 모드가 행동 5개를 그대로 낸다. 확률 모드는 시드로 재현."""
    _, model = tiny_speed_model
    obs = np.random.default_rng(0).random((128, 7)).astype(np.float32)
    learned = {"kind": "learned", "model": str(model)}
    fix = ro.build_policy({"policy": learned, "wrap": [{"kind": "act_fix", "dims": [4], "values": [0, 0, 0, 0, 0.9]}]})
    a = fix(obs)
    assert a.shape == (128, 5) and (a[:, 4] == 0.9).all()
    perm = ro.build_policy({"policy": learned, "wrap": [{"kind": "act_permute"}]}, seed=3)(obs)
    base = ro.build_policy(learned)(obs)
    np.testing.assert_allclose(np.sort(perm, 0), np.sort(base, 0))
    seg = ro.build_policy({"policy": {"kind": "fixed", "action": BASE4 + [0.5]},
                           "wrap": [{"kind": "seg_const", "bins": [[2, [0.5]], [4, [0.5]]], "dims": [4],
                                     "table": [1.0, 1.0, 0.5, 0.0]}]})
    o = np.zeros((4, 7), np.float32)
    o[:, 2] = [0.2, 0.2, 0.9, 0.9]
    o[:, 4] = [0.3, 0.8, 0.3, 0.8]                        # 구간 id 0, 1, 2, 3
    np.testing.assert_allclose(seg(o)[:, 4], [1.0, 1.0, 0.5, 0.0])
    sto = {**learned, "mode": "stochastic"}
    s1, s2 = ro.build_policy(sto, seed=10000)(obs), ro.build_policy(sto, seed=10000)(obs)
    assert s1.shape == (128, 5) and ((0 < s1) & (s1 < 1)).all()
    np.testing.assert_array_equal(s1, s2)


def test_replay_draws_world_gait_for_five_actions(cfg1, tmp_path, capsys):
    """영상: World.gait 를 그대로 칠하고 speed 설명줄을 단다. fixed 5개·random 은 세계에 맞추고 4개·Utility 는 멈춘다."""
    import replay_v2 as R

    rand = dict(cfg1.rand, world_size=[30.0, 30.0], predator_count=[2, 2])
    cfg = cfg1.replace(N=16, rand=rand)
    spec = R.fit_spec(R.parse_spec("fixed:0.4,0.8,0.4,0.1,0.5"), 5, NAMES5)
    run = R.run_policy(cfg, spec, 10000, steps=6, stride=2)
    assert R.gait_source(run.world).startswith("보행 = World.gait")
    gait = np.concatenate([f["gait"] for f in run.frames])
    assert set(np.unique(gait)) <= {GAIT_STOP, GAIT_WALK}               # 걷기 명령: 걷기 또는 방향 없음 정지
    assert "순변화" in R.speed_line([run]) and R.speed_line([R.Run("v2.0", World(load_v2_config(), seeds=[0]))]) is None
    assert R.fit_spec(R.parse_spec("random:3"), 5) == {"kind": "random", "seed": 3, "act_dim": 5}
    assert R.fit_spec(R.parse_spec("perm:random:3"), 5)["policy"]["act_dim"] == 5
    assert R.fit_spec(R.parse_spec("random:3"), 4) == {"kind": "random", "seed": 3}
    for bad in ("fixed:0.1,0.2,0.3,0.4", "utility"):
        with pytest.raises(ValueError):
            R.fit_spec(R.parse_spec(bad), 5, NAMES5)
    with pytest.raises(SystemExit) as e:
        R.main(["--config", str(V2_1), "--policy", "fixed:0.4,0.8,0.4,0.1", "--steps", "4"])
    assert e.value.code == 2
    out = tmp_path / "g.gif"
    assert R.main(["--config", str(V2_1), "--policy", "fixed:0.4,0.8,0.4,0.1,0.9", "--steps", "6", "--stride", "2",
                   "--dpi", "30", "--fps", "10", "--out", str(out)]) == 0
    assert out.exists()
    assert "보행 정지/걷기/뛰기" in capsys.readouterr().out
