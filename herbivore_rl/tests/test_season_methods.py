"""이어 학습 방식 M0~M3 (season/train_season.py, SEASON 5.4).

작은 혼합 세계(묶음마다 세계 1개, 슬롯 256)와 짧은 롤아웃(세계당 8스텝, 2,048 timestep)으로 갱신 규칙만 본다.
"""

import numpy as np
import pytest
import torch as th

from env_v2.rollout import model_gamma
from season.common import ANCHORS, PPO_CONFIG, load_base, load_season, SEASONS
from season.mixed_vec_env import build_mixed
from season.train_season import (LR_MULT, SMALL_CLIP, SeasonPPO, anchor_kl, make_season_model, method_config,
                                 policy_param_names, value_param_names)
from train import load_tuned, make_model

ANCHOR = ANCHORS["v1"]
SMALL = dict(batch_size=512, n_epochs=2)
N_STEPS = 8


@pytest.fixture(scope="module")
def tuned():
    return dict(load_tuned(PPO_CONFIG), gamma=model_gamma(ANCHOR))


@pytest.fixture(scope="module")
def cfgs():
    return load_season(SEASONS["a"]), load_base()


def small_model(cfgs, tuned, method, kl=None, warmup=1, seed=0, reseed=True):
    venv = build_mixed(*cfgs, seed=seed, worlds_per_part=1)
    mcfg = method_config(method, tuned, kl, warmup_rollouts=warmup)
    return make_season_model(venv, ANCHOR, mcfg, tuned, seed, N_STEPS, reseed=reseed, **SMALL)


def params(model, names):
    sd = model.policy.state_dict()
    return {n: sd[n].detach().clone() for n in names}


def same(a, b):
    return all(th.equal(a[k], b[k]) for k in a)


def test_method_config(tuned):
    lr0, clip0 = tuned["learning_rate"], tuned["clip_range"]
    m0, m1, m2 = (method_config(m, tuned) for m in ("M0", "M1", "M2"))
    m3 = method_config("M3", tuned, 0.5)
    assert (m0["warmup_rollouts"], m0["learning_rate"], m0["clip_range"], m0["kl_coef"]) == (0, lr0, clip0, 0.0)
    assert (m1["warmup_rollouts"], m1["learning_rate"], m1["clip_range"], m1["kl_coef"]) == (10, lr0, clip0, 0.0)
    assert m2["warmup_rollouts"] == 10 and m2["learning_rate"] == pytest.approx(lr0 * LR_MULT)
    assert m2["clip_range"] == SMALL_CLIP == 0.1 and m2["kl_coef"] == 0.0
    assert {k: m3[k] for k in ("warmup_rollouts", "learning_rate", "clip_range")} == \
           {k: m2[k] for k in ("warmup_rollouts", "learning_rate", "clip_range")} and m3["kl_coef"] == 0.5
    with pytest.raises(ValueError):
        method_config("M3", tuned)              # KL 계수가 없다
    with pytest.raises(ValueError):
        method_config("M2", tuned, 0.1)         # M3 이 아닌데 KL 계수
    with pytest.raises(ValueError):
        method_config("M4", tuned)


def test_param_split(cfgs, tuned):
    m = small_model(cfgs, tuned, "M0")
    pol, val = policy_param_names(m.policy), value_param_names(m.policy)
    assert "log_std" in pol and "action_net.weight" in pol and "mlp_extractor.policy_net.0.weight" in pol
    assert "value_net.weight" in val and "mlp_extractor.value_net.0.weight" in val
    assert not set(pol) & set(val) and len(pol) + len(val) == len(list(m.policy.parameters()))


def test_m2_lr_and_clip(cfgs, tuned):
    m = small_model(cfgs, tuned, "M2")
    assert m.lr_schedule(1.0) == pytest.approx(tuned["learning_rate"] * LR_MULT)
    assert m.clip_range(1.0) == pytest.approx(0.1) and m.clip_range(0.3) == pytest.approx(0.1)
    m1 = small_model(cfgs, tuned, "M1")
    assert m1.lr_schedule(1.0) == pytest.approx(tuned["learning_rate"])
    assert m1.clip_range(1.0) == pytest.approx(tuned["clip_range"])
    assert m.gamma == m.rollout_buffer.gamma == tuned["gamma"]


def test_m1_freezes_policy_during_warmup(cfgs, tuned):
    """예열 롤아웃 동안 정책 쪽 파라미터는 그대로이고 가치망만 바뀐다. 예열이 끝나면 정책도 바뀐다."""
    m = small_model(cfgs, tuned, "M1", warmup=1)
    pol0, val0 = params(m, policy_param_names(m.policy)), params(m, value_param_names(m.policy))
    m.learn(total_timesteps=N_STEPS * m.env.num_envs, reset_num_timesteps=True)
    assert m.season_log[0]["mode"] == "warmup" and m.season_log[0]["anchor_kl_before"] == 0.0
    assert same(params(m, policy_param_names(m.policy)), pol0)
    assert not same(params(m, value_param_names(m.policy)), val0)
    assert all(p.requires_grad for p in m.policy.parameters())        # 예열 뒤 다시 켠다
    m.learn(total_timesteps=N_STEPS * m.env.num_envs, reset_num_timesteps=False)
    assert m.season_log[1]["mode"] == "ppo"
    assert not same(params(m, policy_param_names(m.policy)), pol0)


def plain_ref(cfgs, tuned, seed, reseed):
    """10-02 스크래치(train_mixed.py)·train_v2 --init 과 같은 순서로 만든 보통 PPO: make_model → PPO.load → 이식."""
    from stable_baselines3 import PPO

    venv = build_mixed(*cfgs, seed=seed, worlds_per_part=1)
    ref = make_model(venv, tensorboard_log=None, n_steps=N_STEPS, seed=seed, **dict(tuned, **SMALL))
    ref.policy.load_state_dict(PPO.load(str(ANCHOR), device="cpu").policy.state_dict())
    if reseed:
        ref.set_random_seed(seed)
    return ref


@pytest.mark.parametrize("reseed", [False, True], ids=["rng_compat", "reseed"])
def test_m0_equals_plain_ppo(cfgs, tuned, reseed):
    """M0 은 PPO.train() 그대로다: 같은 이식·같은 난수 순서의 보통 PPO 와 한 롤아웃 뒤 비트 단위로 같다.

    reseed=False(--rng-compat)는 10-02 스크래치의 혼합 학습과 같은 순서다(스크래치 재현 확인의 근거).
    """
    # 전역 난수를 함께 쓰므로 모델마다 만들고 바로 학습한다
    m = small_model(cfgs, tuned, "M0", warmup=0, seed=2, reseed=reseed)
    m.learn(total_timesteps=N_STEPS * m.env.num_envs, reset_num_timesteps=True)
    ref = plain_ref(cfgs, tuned, 2, reseed)
    ref.learn(total_timesteps=N_STEPS * ref.env.num_envs, reset_num_timesteps=True)
    a, b = m.policy.state_dict(), ref.policy.state_dict()
    assert all(th.equal(a[k], b[k]) for k in a)
    assert m.season_log[0]["mode"] == "ppo"


def test_reseed_makes_seed_matter(cfgs, tuned):
    """PPO.load 는 앵커 zip 의 저장 시드로 전역 난수를 다시 잡는다. 기본(reseed)은 학습 시드가 표본 잡음을 정한다:
    세계가 같아도(같은 meta_seed) PPO 시드가 다르면 갱신이 달라진다."""
    def run(noise_seed=None):
        x = small_model(cfgs, tuned, "M0", warmup=0, seed=0)
        if noise_seed is not None:
            x.set_random_seed(noise_seed)        # 세계는 그대로, 잡음만 바꾼다
        x.learn(total_timesteps=N_STEPS * x.env.num_envs, reset_num_timesteps=True)
        return x.policy.state_dict()

    sa, sb, sc = run(), run(), run(1)
    assert all(th.equal(sa[k], sb[k]) for k in sa)
    assert not all(th.equal(sa[k], sc[k]) for k in sa)


def test_anchor_kl_zero_at_anchor_and_positive_after_change(cfgs, tuned):
    m = small_model(cfgs, tuned, "M3", kl=0.1, warmup=0)
    obs = th.as_tensor(np.random.default_rng(0).random((256, 7)), dtype=th.float32)
    assert anchor_kl(m.policy, m.season_anchor, obs).item() == pytest.approx(0.0, abs=1e-7)
    with th.no_grad():
        m.policy.action_net.bias += 0.3
        m.policy.log_std -= 0.2
    kl = anchor_kl(m.policy, m.season_anchor, obs)
    assert kl.item() > 1e-3
    # 기울기는 앵커 쪽으로 당긴다: KL 만으로 몇 걸음 내리면 줄어든다
    opt = th.optim.Adam([p for n, p in m.policy.named_parameters() if n in policy_param_names(m.policy)], lr=1e-2)
    for _ in range(50):
        opt.zero_grad()
        anchor_kl(m.policy, m.season_anchor, obs).backward()
        opt.step()
    assert anchor_kl(m.policy, m.season_anchor, obs).item() < 0.5 * kl.item()
    assert all(p.grad is None or th.all(p.grad == 0) for p in m.season_anchor.parameters())


def test_m3_adds_kl_term(cfgs, tuned):
    """M3 은 KL 항이 손실에 들어가 같은 시드의 M2 와 갱신이 달라진다. KL 은 리허설 슬롯 상태에서 잰다."""
    m3 = small_model(cfgs, tuned, "M3", kl=0.5, warmup=0)
    m3.learn(total_timesteps=N_STEPS * m3.env.num_envs, reset_num_timesteps=True)
    m2 = small_model(cfgs, tuned, "M2", warmup=0)
    m2.learn(total_timesteps=N_STEPS * m2.env.num_envs, reset_num_timesteps=True)
    row = m3.season_log[0]
    assert row["mode"] == "ppo+kl" and np.isfinite(row["anchor_kl"]) and row["anchor_kl"] >= 0.0
    assert m2.season_log[0]["mode"] == "ppo"
    a, b = m3.policy.state_dict(), m2.policy.state_dict()
    assert not all(th.equal(a[k], b[k]) for k in policy_param_names(m3.policy))
    assert m3.season_rehearsal == slice(128, 256)


def test_saved_zip_is_plain_ppo(cfgs, tuned, tmp_path):
    """시즌 속성은 zip 에 들어가지 않고 보통 PPO 로 읽힌다(평가 워커가 그대로 싣는다)."""
    from stable_baselines3 import PPO

    m = small_model(cfgs, tuned, "M3", kl=0.1, warmup=0)
    assert isinstance(m, SeasonPPO) and all(k in m._excluded_save_params() for k in m.__dict__ if k.startswith("season_"))
    m.save(tmp_path / "m.zip")
    back = PPO.load(tmp_path / "m.zip", device="cpu")
    assert not any(k.startswith("season_") for k in back.__dict__)
    a, b = m.policy.state_dict(), back.policy.state_dict()
    assert all(th.equal(a[k], b[k]) for k in a)
