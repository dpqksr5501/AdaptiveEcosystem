"""V2 v2.2r CM — 범주형 보행 (env_v2/cm.py, 10-03 R2 갈림 3, 수정 제안서 3.1 (나) CM 행·3.3).

설정 검사, 범주 → 세계 행동 변환(칸 가운데 값이라 문턱의 float 차이로 칸이 바뀌지 않음), 창 밖 look 마스크(확률 0·
표본에 안 나옴), 분포의 log_prob·entropy(가우시안 + 비율 × 범주)·mode, 시작 확률(로짓 편향), VecEnv 행동 공간·변환,
CM 학습 smoke 와 저장·불러오기, 평가 정책(결정 = 최빈 범주, 유지 표본 = 누적 확률 비교, 조향 = 결정 모드 경로)을 고정한다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import json
import math

import numpy as np
import pytest
import torch as th
import yaml

from env.config import ROOT
from env_v2.cm import (CATEGORIES, N_STEER, SPEED_VALUE, CMPolicy, GaussCatDistribution, cat_from_uniform, cm_params,
                       cm_to_world, is_cm_file, look_mask, make_cm_policy)
from env_v2.config import load_v2_config
from env_v2.vec_env import MultiWorldVecEnv
from env_v2.world import World

CM = ROOT / "configs" / "v2_2r_cm.yaml"
W = ROOT / "configs" / "v2_2r_w.yaml"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def cfg():
    return load_v2_config(CM)


def _with_cm(cfg, **kw):
    t = dict(cfg.v2["train"])
    t["cm"] = dict(t["cm"], **kw)
    return cfg.replace(v2=dict(cfg.v2, train=t))


def test_cm_config_is_w_world_plus_cm(cfg):
    """v2_2r_cm.yaml 의 세계(features·overrides)는 v2_2r_w.yaml 과 같고 train.cm 만 더했다."""
    w = load_v2_config(W)
    assert cfg.v2["features"] == w.v2["features"]
    for k, v in w.to_dict().items():
        if k != "v2":
            assert getattr(cfg, k) == v, k
    p = cm_params(cfg)
    assert p["categories"] == list(CATEGORIES) and p["mask_look"] and p["theta"] == 0.5
    np.testing.assert_allclose(np.exp(p["init_logits"]), np.array([0.3, 0.5, 0.2, 0.1]) / 1.1)
    assert p["cat_ent_coef"] == 0.01
    assert cm_params(w) is None


@pytest.mark.parametrize("kw, match", [
    ({"categories": ["stop", "run"]}, "categories"),
    ({"init_probs": [0.3, 0.5, 0.2]}, "init_probs"),
    ({"init_probs": [0.3, 0.5, 0.2, 0.0]}, "init_probs"),
    ({"cat_ent_coef": -0.1}, "cat_ent_coef"),
    ({"mask_look_outside_window": "yes"}, "mask_look"),
])
def test_cm_params_rejected(cfg, kw, match):
    with pytest.raises(ValueError, match=match):
        cm_params(_with_cm(cfg, **kw))


def test_cm_needs_matching_world(cfg):
    """look 범주는 W′ 세계(경계 열·창 한정)에서만, K = 3 은 경계 열 없는 세계에서만 쓴다."""
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    f["vigil_window"]["window_only"] = False
    with pytest.raises(ValueError, match="look 범주"):
        cm_params(cfg.replace(v2=dict(cfg.v2, features=f)))
    with pytest.raises(ValueError, match="K = 3"):
        cm_params(_with_cm(cfg, categories=["stop", "walk", "run"], init_probs=[0.3, 0.5, 0.2],
                           mask_look_outside_window=False))


def test_cm_to_world_maps_categories_to_cell_centres(cfg):
    names = World(cfg, seeds=[0]).act_names
    raw = np.zeros((4, 5))
    raw[:, 4] = [0, 1, 2, 3]
    raw[:, :4] = [[-1.0, 0.0, 1.0, 2.0]] * 4
    a = cm_to_world(raw, cm_params(cfg), names)
    np.testing.assert_allclose(a[:, :4], 1.0 / (1.0 + np.exp(-raw[:, :4])))
    np.testing.assert_array_equal(a[:, 4], [SPEED_VALUE[c] for c in CATEGORIES])
    np.testing.assert_array_equal(a[:, 5], [0.0, 0.0, 0.0, 1.0])
    w = World(cfg, seeds=[0])
    t_walk, t_run = w._sp["thresholds"]
    cmd = (a[:, 4] >= t_walk).astype(int) + (a[:, 4] >= t_run)
    np.testing.assert_array_equal(cmd[:3], [0, 1, 2])
    assert (a[:, 5] > w._vg["threshold"]).tolist() == [False, False, False, True]


def _dist(k=4, ent_scale=2.0, n=6, seed=0):
    g = th.Generator().manual_seed(seed)
    mean = th.randn(n, N_STEER + k, generator=g)
    log_std = th.randn(N_STEER, generator=g) * 0.3
    return GaussCatDistribution(k, ent_scale), mean, log_std


def test_distribution_log_prob_entropy_and_mask():
    d, mean, log_std = _dist()
    allow = th.tensor([True, False, True, False, True, False])
    d.proba_distribution(mean, log_std, allow)
    probs = d.cat.probs
    assert th.all(probs[~allow, 3] == 0) and th.allclose(probs.sum(1), th.ones(6))
    # 막힌 행의 나머지 확률 = 막지 않은 softmax 를 다시 맞춘 값
    ref = th.softmax(mean[:, N_STEER:N_STEER + 3], 1)
    assert th.allclose(probs[~allow, :3], ref[~allow], atol=1e-6)
    a = d.sample()
    assert a.shape == (6, N_STEER + 1) and th.all(a[~allow, N_STEER] != 3)
    normal = th.distributions.Normal(mean[:, :N_STEER], log_std.exp())
    want = normal.log_prob(a[:, :N_STEER]).sum(1) + d.cat.log_prob(a[:, N_STEER].long())
    assert th.allclose(d.log_prob(a), want)
    assert th.allclose(d.entropy(), normal.entropy().sum(1) + 2.0 * d.cat.entropy())
    m = d.mode()
    assert th.equal(m[:, :N_STEER], mean[:, :N_STEER]) and th.equal(m[:, N_STEER], probs.argmax(1).float())
    for _ in range(50):                                 # 막힌 범주는 표본에 나오지 않는다
        assert th.all(d.sample()[~allow, N_STEER] != 3)


def test_look_mask_matches_world_window(cfg):
    """관측으로 만든 마스크 = 세계의 결정 때 창(World.window)."""
    w = World(cfg, seeds=[12000])
    rng = np.random.default_rng(1)
    for _ in range(200):
        o = w.observe()
        m = look_mask(o, 0.5)
        w.step(rng.random((w.N, w.act_dim)))
        np.testing.assert_array_equal(m, w.window)


@pytest.fixture(scope="module")
def tiny_cm(tmp_path_factory):
    import train_v2

    d = tmp_path_factory.mktemp("cm")
    raw = yaml.safe_load(CM.read_text(encoding="utf-8"))
    raw["train"].update(num_worlds=1, rollout_world_steps=8)
    cfg_path = d / "tiny_cm.yaml"
    cfg_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    out = d / "m.zip"
    assert train_v2.main(["--steps", "2000", "--seed", "0", "--config", str(cfg_path), "--out", str(out),
                          "--tb", str(d / "tb"), "--threads", "1", "--probe-every", "1000"]) == 0
    return cfg_path, out


def test_cm_training_smoke_and_reload(tiny_cm):
    """CM 학습: 정책 CMPolicy, 출력층 4 + 4, 범주 엔트로피 비율 = 0.01 / ent_coef, 시작 로짓 편향, 탐침 기록에
    범주 확률(p_cat_*·p_vig_win). 저장한 zip 을 불러와도 같은 클래스다."""
    from stable_baselines3 import PPO

    cfg_path, out = tiny_cm
    m = PPO.load(out, device="cpu")
    assert isinstance(m.policy, CMPolicy) and m.policy.action_net.out_features == N_STEER + 4
    assert m.action_space.shape == (5,) and m.action_space.high[4] == 3.0
    assert m.policy.cm_ent_scale == pytest.approx(0.01 / float(m.ent_coef))
    assert m.policy.cm_mask_theta == 0.5
    assert is_cm_file(out)
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["init_policy"]["cm"]["categories"] == list(CATEGORIES)
    rows = meta["probe_history"]
    assert rows and {"p_cat_look", "p_vig_win", "p_stop_win_full"} <= set(rows[0])
    assert rows[0]["p_vig_calm"] == 0.0


def test_cm_eval_policy_modes(tiny_cm):
    """결정 = 최빈 범주, 유지 표본 = 누적 확률 비교(K 스텝 안에서 u 고정), 조향은 세 모드 모두 결정 모드와 같다.
    창 밖 개체는 어떤 모드에서도 look(경계 1)을 고르지 않는다."""
    from stable_baselines3 import PPO

    cfg_path, out = tiny_cm
    m = PPO.load(out, device="cpu")
    w = World(load_v2_config(cfg_path), seeds=[12000])
    rng = np.random.default_rng(2)
    for _ in range(60):
        w.step(rng.random((w.N, w.act_dim)))
    obs = w.observe()
    det = make_cm_policy(m, 12000, "deterministic")
    hold = make_cm_policy(m, 12000, "hold", hold_k=24)
    sto = make_cm_policy(m, 12000, "stochastic")
    a_det, a_hold, a_sto = det(obs), hold(obs), sto(obs)
    np.testing.assert_array_equal(a_det[:, :4], a_hold[:, :4])
    np.testing.assert_array_equal(a_det[:, :4], a_sto[:, :4])
    np.testing.assert_array_equal(det.last_cat, det.last_probs.argmax(1))
    np.testing.assert_array_equal(hold.last_cat, cat_from_uniform(hold.last_probs, hold.last_u))
    outside = ~look_mask(obs, 0.5)
    for a in (a_det, a_hold, a_sto):
        assert (a[outside, 5] == 0.0).all()
    u0 = hold.last_u.copy()
    hold(obs)
    same = hold.last_u == u0
    assert same.mean() > 0.8                    # K = 24 에서 한 스텝 뒤 대부분 같은 블록이다(위상 경계만 바뀐다)


def test_cat_from_uniform_matches_cdf():
    p = np.array([[0.2, 0.3, 0.5, 0.0], [0.25, 0.25, 0.25, 0.25]])
    for u, want in ((0.1, [0, 0]), (0.2, [1, 0]), (0.49, [1, 1]), (0.5, [2, 2]), (0.999, [2, 3])):
        np.testing.assert_array_equal(cat_from_uniform(p, np.array([u, u])), want)


def test_vec_env_uses_cm_action_space(cfg):
    v = MultiWorldVecEnv(cfg, num_worlds=1)
    assert v.action_space.shape == (5,) and v.act_dim == 6
    raw = np.zeros((v.num_envs, 5), dtype=np.float32)
    raw[:, 4] = 3
    v.step_async(raw)
    assert (v._actions[:, 5] == 1.0).all() and (v._actions[:, 4] == SPEED_VALUE["look"]).all()
    assert math.isclose(v._actions[0, 0], 0.5)


def test_rollout_runs_cm_models_in_every_mode(tiny_cm):
    """rollout 은 CM 모델을 알아보고 세 모드로 돌린다. 행에는 창 지표(window_stats)가 붙고, 창 밖 경계는 0 이다."""
    from env_v2.rollout import WINDOW_COLUMNS, run_specs

    cfg_path, out = tiny_cm
    cfg = load_v2_config(cfg_path)
    specs = {m: {"kind": "learned", "model": str(out), **kw} for m, kw in
             (("det", {}), ("hold", {"mode": "hold", "hold_k": 24}), ("sto", {"mode": "stochastic"}))}
    res = run_specs(cfg, specs, [12000], 300, workers=1)
    for m, rows in res.items():
        r = rows[0]
        assert set(WINDOW_COLUMNS) <= set(r) and r["p_vig_calm_w"] == 0.0, m
    same = run_specs(cfg, {"hold": specs["hold"]}, [12000], 300, workers=1)["hold"][0]
    assert same["mean_return"] == res["hold"][0]["mean_return"]  # 유지 표본은 시드로 재현된다
