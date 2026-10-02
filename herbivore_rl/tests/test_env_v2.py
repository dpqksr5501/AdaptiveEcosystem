"""V2 0단계 — env_v2 골격(0-1)과 다중 세계 VecEnv(0-2). 계획서 5절 0단계 완료 기준."""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import numpy as np
import pytest

from env.config import load_config
from env.world import World as WorldV1
from env_v2.config import load_v2_config
from env_v2.features import features_of
from env_v2.vec_env import MultiWorldVecEnv
from env_v2.world import World as WorldV2
from policies.registry import make_policy


@pytest.fixture
def cfg2():
    return load_v2_config()


# --------------------------------------------------------------------- #
# 0-1 — 기능을 모두 끈 env_v2 는 v1 과 같다
# --------------------------------------------------------------------- #


def test_v2_config_keeps_v1_values(cfg2):
    v1 = load_config()
    for k, v in v1.to_dict().items():
        assert getattr(cfg2, k) == v, k                # overrides 가 비어 있으면 v1 과 같다
    assert features_of(cfg2).active == ()             # 기본 설정은 모든 기능이 꺼져 있다
    assert cfg2.v2["train"]["num_worlds"] == 8


@pytest.mark.parametrize("seed", [0, 636, 10000])
@pytest.mark.parametrize("spec", [
    {"kind": "fixed", "action": [0.3, 0.8, 0.4, 0.1]},
    {"kind": "utility"},
    {"kind": "random", "seed": 3},
])
def test_v2_world_matches_v1_when_features_off(cfg2, seed, spec):
    """같은 시드·같은 정책이면 통계 10열과 관측·위치가 v1 과 비트 단위로 같아야 한다."""
    off = cfg2.replace(v2=dict(cfg2.v2, features={}))   # 기본 설정이 나중에 기능을 켜도 이 비교는 모두 끈 상태로
    v1, v2 = WorldV1(load_config(), seeds=[seed]), WorldV2(off, seeds=[seed])
    p1, p2 = make_policy(spec), make_policy(spec)
    for _ in range(300):
        o1, o2 = v1.observe(), v2.observe()
        np.testing.assert_array_equal(o1, o2)
        v1.step(p1(o1))
        v2.step(p2(o2))
    assert v1.stats() == v2.stats()
    np.testing.assert_array_equal(v1.pos, v2.pos)
    np.testing.assert_array_equal(v1.pred_pos, v2.pred_pos)


def test_v2_feature_rng_is_a_separate_stream(cfg2):
    """V2 기능 난수는 기능별 스트림에서만 뽑는다. 그걸 써도 v1 스트림은 그대로여야 한다."""
    a, b = WorldV2(cfg2, seeds=[5]), WorldV2(cfg2, seeds=[5])
    b.feature_rng("food_v").random(1000)                 # V2 기능이 난수를 쓴 것처럼
    b.feature_rng("daynight", part=1).random(1000)
    act = np.full((a.N, 4), 0.5)
    for _ in range(50):
        a.step(act)
        b.step(act)
    np.testing.assert_array_equal(a.pos, b.pos)


# --------------------------------------------------------------------- #
# 0-2 — 다중 세계, 엇갈린 리셋, truncation
# --------------------------------------------------------------------- #


def test_multiworld_shapes_and_distinct_worlds(cfg2):
    """(a) 한 롤아웃 배치에 서로 다른 세계 K 개가 들어간다."""
    venv = MultiWorldVecEnv(cfg2, meta_seed=0)
    assert venv.num_envs == 8 * 128
    obs = venv.reset()
    assert obs.shape == (1024, 7) and obs.dtype == np.float32
    assert len(set(venv.current_seeds())) == 8
    obs, rew, done, infos = venv.step(np.zeros((1024, 4), dtype=np.float32))
    assert obs.shape == (1024, 7) and rew.shape == (1024,) and done.shape == (1024,)
    assert len(infos) == 1024
    # 세계마다 슬롯 구간의 관측이 실제로 다르다 (같은 세계를 K 번 돌리는 게 아니다)
    blocks = [obs[k * 128:(k + 1) * 128] for k in range(8)]
    assert len({b.tobytes() for b in blocks}) == 8


def test_resets_are_staggered_and_worlds_renew(cfg2):
    venv = MultiWorldVecEnv(cfg2, num_worlds=4, reset_interval=8, meta_seed=1)
    venv.reset()
    first = venv.current_seeds()
    reset_steps = {k: [] for k in range(4)}
    for t in range(1, 17):
        _, _, done, infos = venv.step(np.zeros((venv.num_envs, 4), dtype=np.float32))
        for k in range(4):
            if infos[k * 128].get("TimeLimit.truncated") or (done[k * 128:(k + 1) * 128].all()):
                reset_steps[k].append(t)
    # 세계 k 는 처음에 k·T/K 스텝을 산 것으로 둔다 → 8 - 2k 스텝째에 첫 리셋
    assert [reset_steps[k][0] for k in range(4)] == [8, 6, 4, 2]
    assert all(len(set(h)) >= 2 for h in venv.seed_history)       # 세계가 새로 뽑혔다
    assert len(set(venv.current_seeds())) == 4                      # 동시에 도는 세계는 겹치지 않는다
    assert venv.current_seeds() != first


def test_truncation_bootstraps_value_but_death_does_not(cfg2):
    """(b) 리셋으로 끊긴 슬롯은 SB3 가 보상에 γ·V(terminal_obs) 를 더한다.
    (c) 같은 스텝에 죽은 슬롯은 더하지 않는다 (사망 우선)."""
    from stable_baselines3 import PPO

    venv = MultiWorldVecEnv(cfg2, num_worlds=2, reset_interval=6, meta_seed=0)
    # 세계 1 은 나이 3 으로 시작 → 3번째 스텝에 리셋. 그 스텝에 슬롯 0 이 죽은 것으로 만든다.
    w1 = venv.worlds[1]
    orig_step = w1.step
    calls = {"n": 0}

    def step_with_forced_death(a):
        obs, rew, done, term = orig_step(a)
        calls["n"] += 1
        if calls["n"] == 3:
            done = done.copy()
            done[0] = True
        return obs, rew, done, term

    w1.step = step_with_forced_death

    raw, infos_log = [], []
    orig_wait = venv.step_wait

    def recording_wait():
        obs, rew, done, infos = orig_wait()
        raw.append(rew.copy())
        infos_log.append(infos)
        return obs, rew, done, infos

    venv.step_wait = recording_wait

    n_steps = 8
    model = PPO("MlpPolicy", venv, n_steps=n_steps, batch_size=n_steps * venv.num_envs,
                n_epochs=1, learning_rate=0.0, gamma=0.99, seed=0, device="cpu")
    model.learn(total_timesteps=n_steps * venv.num_envs)   # 롤아웃 1번, lr=0 이라 가중치 그대로
    buf = model.rollout_buffer.rewards                      # (n_steps, num_envs)

    j = 2                                                   # 세계 1 이 리셋한 스텝 (0부터)
    N = venv.N
    dead_slot = N + 0
    trunc_slots = [i for i in range(N, 2 * N) if infos_log[j][i].get("TimeLimit.truncated")]
    assert dead_slot not in trunc_slots and len(trunc_slots) == N - 1
    assert "terminal_observation" in infos_log[j][dead_slot]

    terms = np.stack([infos_log[j][i]["terminal_observation"] for i in trunc_slots])
    with __import__("torch").no_grad():
        v = model.policy.predict_values(model.policy.obs_to_tensor(terms)[0]).numpy().ravel()
    np.testing.assert_allclose(buf[j, trunc_slots] - raw[j][trunc_slots], 0.99 * v, atol=1e-4)
    assert buf[j, dead_slot] == pytest.approx(raw[j][dead_slot], abs=1e-5)       # 사망: 더하지 않는다
    untouched = [i for i in range(N) if not infos_log[j][i].get("TimeLimit.truncated")]
    np.testing.assert_allclose(buf[j, untouched], raw[j][untouched], atol=1e-5)  # 세계 0 은 그대로


def test_reset_keeps_fresh_worlds_and_renews_used_ones(cfg2):
    """SB3 가 learn 시작 때 부르는 reset 은 막 만든 세계를 버리지 않는다. 돈 뒤의 reset 은 새로 뽑는다."""
    venv = MultiWorldVecEnv(cfg2, num_worlds=3, meta_seed=4)
    built = venv.current_seeds()
    venv.reset()
    assert venv.current_seeds() == built and venv.num_resets == 0
    venv.step(np.zeros((venv.num_envs, 4), dtype=np.float32))
    venv.reset()
    assert venv.current_seeds() != built
