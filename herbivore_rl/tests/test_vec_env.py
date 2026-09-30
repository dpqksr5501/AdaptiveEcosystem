"""§6.2 HerdVecEnv, §6.1 모방 초기화, §6.3/§6.4 PPO 설정 계약."""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import numpy as np
import pytest
from torch import nn

from env.config import load_config
from env.vec_env import ACT_SPACE, OBS_SPACE, HerdVecEnv, make_vec_env, sigmoid
from env.world import World


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def venv(cfg):
    v = make_vec_env(cfg, seeds=[0])
    yield v
    v.close()


# --------------------------------------------------------------------- #
# §6.2 공간과 규약
# --------------------------------------------------------------------- #


def test_spaces_match_the_contract(venv):
    assert venv.num_envs == 128                      # §4.3 슬롯 하나 = 환경 하나
    assert OBS_SPACE.shape == (7,) and OBS_SPACE.dtype == np.float32   # §3.1
    assert ACT_SPACE.shape == (4,)                                     # §3.2
    assert (ACT_SPACE.low == -3.0).all() and (ACT_SPACE.high == 3.0).all()
    assert (OBS_SPACE.low == 0.0).all() and (OBS_SPACE.high == 1.0).all()


def test_reset_and_step_shapes(venv):
    obs = venv.reset()
    assert obs.shape == (128, 7) and obs.dtype == np.float32
    a = np.zeros((128, 4), dtype=np.float32)
    obs, rew, done, infos = venv.step(a)
    assert obs.shape == (128, 7)
    assert rew.shape == (128,)
    assert done.shape == (128,) and done.dtype == np.bool_
    assert len(infos) == 128 and all(isinstance(i, dict) for i in infos)


def test_sigmoid_is_applied_exactly_once(venv, cfg):
    """§1.3 — World.step()은 [0,1]만 받는다. 변환은 이 래퍼에만 있어야 한다."""
    raw = np.array([[-3.0, 0.0, 3.0, 1.0]] * 128, dtype=np.float32)
    venv.step_async(raw)
    got = venv._actions
    assert np.allclose(got, 1.0 / (1.0 + np.exp(-raw)))
    assert (got >= 0.0).all() and (got <= 1.0).all()
    assert np.isclose(got[0, 1], 0.5)                # sigmoid(0)


def test_zero_action_is_not_zero_weight(venv):
    """행동 0은 [0,1]로 가면 0.5다. 여기를 헷갈리면 조향이 통째로 어긋난다."""
    venv.step_async(np.zeros((128, 4), dtype=np.float32))
    assert np.allclose(venv._actions, 0.5)


def test_terminal_observation_is_reported_for_dead_slots(cfg):
    v = make_vec_env(cfg, seeds=[0])
    v.world.food_cap[:] = 0.0
    v.world.food[:] = 0.0
    v.world.energy[:] = 1e-9                        # 전원 아사
    _, _, done, infos = v.step(np.zeros((128, 4), dtype=np.float32))
    assert done.all()
    for i in np.flatnonzero(done):
        assert "terminal_observation" in infos[i]
        t = infos[i]["terminal_observation"]
        assert t.shape == (7,) and 0.0 <= t.min() and t.max() <= 1.0
    v.close()


def test_no_terminal_observation_when_nobody_dies(cfg):
    rd = dict(cfg.rand)
    rd["predator_count"] = [0, 0]
    v = make_vec_env(cfg.replace(rand=rd), seeds=[0])
    _, _, done, infos = v.step(np.full((128, 4), 0.5, dtype=np.float32))
    assert not done.any()
    assert all("terminal_observation" not in i for i in infos)
    v.close()


def test_get_attr_world_is_the_world(venv):
    """§6.5가 `self.training_env.get_attr("world")[0]` 로 접근한다."""
    got = venv.get_attr("world")
    assert len(got) == 128
    assert all(w is venv.world for w in got)
    assert isinstance(got[0], World)


def test_get_attr_respects_indices(venv):
    assert len(venv.get_attr("world", indices=[0, 3])) == 2
    assert len(venv.get_attr("world", indices=0)) == 1


def test_minimum_vecenv_surface_exists(venv):
    """§6.2 — get_attr / set_attr / env_is_wrapped / env_method / close 최소 구현 필수."""
    venv.set_attr("_probe", 7)
    assert venv.get_attr("_probe")[0] == 7
    assert venv.env_is_wrapped(object) == [False] * 128
    assert len(venv.env_method("_n", None)) == 128
    venv.close()


def test_vec_env_is_deterministic_for_a_seed(cfg):
    def run():
        v = make_vec_env(cfg, seeds=[11])
        rng = np.random.default_rng(0)
        out = None
        for _ in range(50):
            out = v.step(rng.uniform(-3, 3, (128, 4)).astype(np.float32))
        v.close()
        return out
    a, b = run(), run()
    for x, y in zip(a[:3], b[:3]):
        assert np.array_equal(x, y)


# --------------------------------------------------------------------- #
# §6.3 / §6.4 — 구조는 탐색 대상이 아니다
# --------------------------------------------------------------------- #


def test_ppo_config_is_fixed_where_the_spec_says(venv):
    from train import PPO_KWARGS

    pk = PPO_KWARGS["policy_kwargs"]
    assert pk["net_arch"] == [64, 64]            # §8.1 7-64-64-4
    assert pk["activation_fn"] is nn.Tanh        # §1.4 활성함수는 tanh 고정
    assert PPO_KWARGS["n_steps"] == 256
    assert PPO_KWARGS["batch_size"] == 4096
    assert PPO_KWARGS["gae_lambda"] == 0.95


def test_make_model_refuses_to_search_architecture(venv):
    """§6.4·§12 — net_arch / activation_fn 탐색 금지. 실수로 넘기면 터져야 한다."""
    from train import make_model

    for bad in ({"net_arch": [32]}, {"activation_fn": nn.ReLU},
                {"policy_kwargs": {"net_arch": [8]}}):
        with pytest.raises(ValueError, match="§6.4"):
            make_model(venv, tensorboard_log=None, **bad)


def test_tune_ppo_searches_only_the_allowed_five():
    from tune_ppo import FORBIDDEN, SEARCH

    assert set(SEARCH) == {"learning_rate", "gamma", "ent_coef", "clip_range", "n_epochs"}
    assert not (FORBIDDEN & set(SEARCH))


def test_built_model_has_the_layers_export_expects(venv):
    """§8.1이 가져갈 세 층이 그 이름 그대로 있어야 한다."""
    from train import make_model

    m = make_model(venv, tensorboard_log=None)
    net = m.policy.mlp_extractor.policy_net
    assert (net[0].in_features, net[0].out_features) == (7, 64)
    assert isinstance(net[1], nn.Tanh)
    assert (net[2].in_features, net[2].out_features) == (64, 64)
    assert isinstance(net[3], nn.Tanh)
    assert (m.policy.action_net.in_features, m.policy.action_net.out_features) == (64, 4)


# --------------------------------------------------------------------- #
# §6.1 모방 초기화
# --------------------------------------------------------------------- #


def test_logit_transform_matches_spec():
    """§6.1-2 — acts = clip(acts, 0.05, 0.95), logits = log(acts / (1-acts))."""
    from warmstart import to_logits

    a = np.array([[0.0, 0.01, 0.5, 1.0]])
    got = to_logits(a)
    ref = np.log(np.clip(a, 0.05, 0.95) / (1 - np.clip(a, 0.05, 0.95)))
    assert np.allclose(got, ref)
    assert np.isfinite(got).all(), "clip이 없으면 0과 1에서 무한대가 된다"
    assert np.isclose(got[0, 2], 0.0)
    assert abs(got[0, 0]) == pytest.approx(abs(got[0, 3]))   # 대칭


def test_sigmoid_of_logit_round_trips_inside_the_clip():
    from warmstart import to_logits

    a = np.array([[0.1, 0.3, 0.7, 0.9]])
    assert np.allclose(sigmoid(to_logits(a)), a, atol=1e-6)


def test_collected_pairs_are_in_contract_range(cfg):
    from policies.registry import make_policy
    from warmstart import collect

    obs, act = collect(cfg, make_policy({"kind": "utility", "params": "default"}),
                       [0, 1], n_pairs=1024, warmup=10, stride=5, per_seed=60)
    assert len(obs) == len(act) == 1024
    assert obs.shape[1] == 7 and act.shape[1] == 4
    assert (obs >= 0).all() and (obs <= 1).all()
    assert (act >= 0).all() and (act <= 1).all()


# --------------------------------------------------------------------- #
# §7.1 / §9.3 파리티 — predict가 clamp까지 해 주는가
# --------------------------------------------------------------------- #


def test_predict_clips_to_action_space_before_sigmoid(venv):
    """§9.3 C++는 `clamp(-3,3) -> sigmoid` 다. 파이썬 쪽도 같아야 한다.

    SB3의 `predict()` 가 action_space 경계로 clip해 주므로 §7.1의
    `sigmoid(model.predict(...))` 가 곧 C++ 계약과 일치한다. 이게 깨지면 §8.2 검증이
    통과해도 언리얼에서 값이 달라진다.
    """
    from train import make_model

    m = make_model(venv, tensorboard_log=None)
    # log_std를 키워 (-3,3) 밖 표본이 나오게 한 뒤에도 경계를 넘지 않는지 본다
    obs = np.random.default_rng(0).random((256, 7)).astype(np.float32)
    raw, _ = m.predict(obs, deterministic=True)
    assert raw.shape == (256, 4)
    assert (raw >= -3.0).all() and (raw <= 3.0).all()
    out = sigmoid(raw)
    assert (out > 0.0).all() and (out < 1.0).all()
    assert np.allclose(out, sigmoid(np.clip(raw, -3, 3)))
