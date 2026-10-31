"""유지 표본 모드(수정 제안서 3.1 (가) R1 출시 모드, 5절 #3)의 단위 테스트.

- 해시: SplitMix64 기준값, 고정 골든값(C++ 골든 시퀀스의 시작값), u ∈ (0,1), 대략 균등
- 조향 4열은 결정 모드(policies.registry)와 비트 단위로 같다
- K=1 이면 호출마다 새 u, K=24 면 블록 안에서 같고 경계에서 바뀐다. 위상은 개체마다 다르다
- 리스폰(observe_done)은 키를 바꿔 곧바로 새 u 를 쓴다
- 칸 빈도가 해석적 Φ 칸 확률과 맞고, Φ⁻¹ 없는 경계 비교가 연속값 문턱과 같다
- 결정·확률 모드 롤아웃은 이 기능 전과 비트 단위로 같다
- 래퍼(내장·factory)가 observe_done 을 바탕 정책으로 넘긴다
- diagnose_v2 의 --act-mode hold --hold-k: 이름·캐시·meta·재사용 조건·modecmp

학습은 돌리지 않는다. 작은 모델은 무작위 초기화 PPO 에 행동 평균 편향과 log_std 를 박아 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from scipy.special import ndtri

import diagnose_v2 as dg
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.world import World
from policies.registry import make_policy

ROOT = Path(__file__).resolve().parent.parent
V2_2 = ROOT / "configs" / "v2_2.yaml"
TINY = {"version": "2.2", "overrides": {"rand": {"pred_speed_mult": [0.6, 0.95]}},
        "train": {"num_worlds": 1, "reset_interval": 4000, "rollout_world_steps": 8}}
# 행동 평균(자르기 전)과 log_std. 열 3 의 3.5 는 [-3, 3] 밖이라 결정 경로의 자르기를 함께 본다. 열 4·5 = speed·vigilance
BIAS6 = [2.0, -1.0, 0.5, 3.5, 0.3, -0.6]
LOG_STD6 = [-0.5, 0.0, 0.3, 0.0, 0.2, -0.3]
SPEED_T = (1.0 / 3.0, 2.0 / 3.0)        # configs/v2_2.yaml features.speed.thresholds (a ≥ t)
VIG_T = 0.5                              # features.vigilance.threshold (a > t)

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def key(slot, gen=0):
    return (int(slot) << 32) + int(gen)


# --------------------------------------------------------------------- #
# 공용: 행동 6개 작은 모델, 고정 분포 대역
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def tiny6(tmp_path_factory):
    """configs/v2_2.yaml 기능 블록 그대로(관측 8·행동 6)인 세계 1개 설정과, 편향·log_std 를 박은 무작위 PPO."""
    import torch as th
    from env_v2.vec_env import MultiWorldVecEnv
    from train import make_model

    d = tmp_path_factory.mktemp("hold6")
    raw = yaml.safe_load(V2_2.read_text(encoding="utf-8"))
    cfg_path = d / "tiny_v2_2.yaml"
    cfg_path.write_text(yaml.safe_dump(dict(TINY, features=raw["features"]), allow_unicode=True), encoding="utf-8")
    cfg = load_v2_config(cfg_path)
    model = make_model(MultiWorldVecEnv(cfg, num_worlds=1), tensorboard_log=None, n_steps=8, seed=0)
    assert model.action_space.shape == (6,) and model.observation_space.shape == (8,)
    with th.no_grad():
        model.policy.action_net.bias.copy_(th.tensor(BIAS6))
        model.policy.log_std.copy_(th.tensor(LOG_STD6))
    path = d / "m.zip"
    model.save(path)
    return cfg_path, path


class Stub(ro.HoldLearned):
    """모든 개체가 같은 (μ, σ) 인 대역. 관측과 무관하므로 u 의 유지가 행동에 그대로 보인다."""

    def __init__(self, mu, sd, seed=10000, k=24, salt=0):
        n = len(mu)
        space = SimpleNamespace(low=np.full(n, -3, np.float32), high=np.full(n, 3, np.float32))
        super().__init__(SimpleNamespace(policy=SimpleNamespace(action_space=space)), seed, k, salt)
        self.mu, self.sd = np.asarray(mu, np.float32), np.asarray(sd, np.float32)

    def _forward32(self, obs):
        n = len(obs)
        return np.tile(self.mu, (n, 1)), np.tile(self.sd, (n, 1))


def _obs8(n=128, seed=0):
    return np.random.default_rng(seed).random((n, 8)).astype(np.float32)


# --------------------------------------------------------------------- #
# 1) 해시
# --------------------------------------------------------------------- #


def test_hash_matches_splitmix64_reference():
    """Mix64 는 SplitMix64 마무리 함수, H(x) 하나는 SplitMix64(시드 x) 의 첫 출력이다 (Vigna splitmix64.c 기준값)."""
    assert int(ro.hold_hash(0)) == 0xE220A8397B1DCDAF
    s, out = 1234567, []
    for _ in range(5):
        s = (s + ro.HOLD_GOLDEN) % (1 << 64)
        out.append(int(ro.mix64(s)))
    assert out == [6457827717110365317, 3203168211198807973, 9817491932198370423, 4593380528125082431,
                   16408922859458223821]
    assert int(ro.hold_hash(1234567)) == out[0]
    # 사슬: H(a, b, c) = Mix64((H(a, b) ^ c) + GOLDEN)
    ab = int(ro.hold_hash(7, 8))
    assert int(ro.hold_hash(7, 8, 9)) == int(ro.mix64(((ab ^ 9) + ro.HOLD_GOLDEN) % (1 << 64)))
    assert int(ro.hold_chain(ro.hold_hash(7, 8), 9)) == int(ro.hold_hash(7, 8, 9))
    # 음수는 2의 보수 uint64
    assert int(ro.hold_hash(404, 10000, -1, 0, 4, 0)) == int(ro.hold_hash(404, 10000, 2**64 - 1, 0, 4, 0))
    with pytest.raises(TypeError):
        ro.hold_hash(1.5)


# C++ 골든 시퀀스의 시작값 (10-03 고정). 바꾸면 C++ 표본기와 파리티가 깨진다.
GOLDEN = [
    # (입력 H(404, seed, salt, key, col, block)), 해시, u
    ((404, 10000, 0, key(0, 0), 4, 0), 0x58D5EDE64E8719DD, 0.34701430199359284),
    ((404, 10000, 0, key(5, 1), 5, 7), 0x5367C73BF94A976D, 0.32580228056148497),
    ((404, 12000, 3, key(127, 2), 4, 208), 0x26A2DEC4CFA807F3, 0.15092270188293366),
]


@pytest.mark.parametrize("inputs,h,u", GOLDEN)
def test_hash_golden_values(inputs, h, u):
    assert int(ro.hold_hash(*inputs)) == h
    assert float(ro.hold_uniform(h)) == u
    assert int(ro.hold_hash(404, 10000, 0)) == 0x950BEB42433AEA8B           # seed·salt 까지의 접두 상태


def test_phase_and_noise_golden_values():
    """위상 φ = H(404, seed, salt, key, 0xFFFFFFFF) mod 24, 그리고 u 블록. 개체 0 은 φ 16 이라 tick 8 에서 블록 1 이 된다."""
    keys = [key(0), key(1), key(127), key(5, 1)]
    assert ro.hold_phase(10000, 0, keys, 24).tolist() == [16, 17, 8, 6]
    u0 = ro.hold_noise(10000, 0, [key(0)], [4, 5], 0, 24)
    np.testing.assert_array_equal(u0, [[0.34701430199359284, 0.9975173394577542]])
    np.testing.assert_array_equal(ro.hold_noise(10000, 0, [key(0)], [4, 5], 7, 24), u0)
    u8 = ro.hold_noise(10000, 0, [key(0)], [4, 5], 8, 24)
    np.testing.assert_array_equal(u8, [[0.3324325261726121, 0.9812057931325858]])
    assert float(u8[0, 0]) == float(ro.hold_uniform(ro.hold_hash(404, 10000, 0, key(0), 4, 1)))


def test_uniform_is_exact_and_open():
    """U = ((h >> 12) + 0.5)·2^-52 는 끝값도 (0,1) 안이다. (h >> 11)·2^-53 + 2^-54 는 최댓값이 1.0 으로 반올림된다."""
    top = 2**64 - 1
    assert float(ro.hold_uniform(0)) == 2.0 ** -53
    assert float(ro.hold_uniform(top)) == 1.0 - 2.0 ** -53 < 1.0
    assert ((top >> 11) * 2.0 ** -53 + 2.0 ** -54) == 1.0                     # 53비트 꼴을 쓰지 않는 이유
    assert np.isfinite(ndtri(ro.hold_uniform(np.array([0, top], dtype=np.uint64)))).all()


def test_hash_uniform_is_roughly_uniform():
    n = 100_000
    keys = np.arange(n, dtype=np.int64) * 7919 + 13
    u = ro.hold_uniform(ro.hold_hash(404, 10000, 0, keys, 4, 0))
    assert u.dtype == np.float64 and ((u > 0) & (u < 1)).all()
    assert len(np.unique(u)) == n
    ks = np.abs(np.sort(u) - (np.arange(n) + 0.5) / n).max()
    assert ks < 0.01                                                          # 1% 기각값 1.63/√n ≈ 0.0052 의 두 배
    assert abs(u.mean() - 0.5) < 0.005
    hist = np.bincount((u * 20).astype(int), minlength=20) / n
    assert np.abs(hist - 0.05).max() < 0.005
    # 열·블록·시드·salt 가 다르면 다른 수열 (상관 없음)
    for other in (ro.hold_hash(404, 10000, 0, keys, 5, 0), ro.hold_hash(404, 10000, 0, keys, 4, 1),
                  ro.hold_hash(404, 10001, 0, keys, 4, 0), ro.hold_hash(404, 10000, 1, keys, 4, 0),
                  ro.hold_hash(303, 10000, 0, keys, 4, 0)):
        assert abs(np.corrcoef(u, ro.hold_uniform(other))[0, 1]) < 0.02


def test_vectorized_noise_equals_scalar_hash():
    keys = [key(s, g) for s, g in ((0, 0), (3, 2), (127, 5))]
    for tick in (0, 5, 23, 24, 100):
        u = ro.hold_noise(9, 2, keys, [4, 5], tick, 24)
        for i, kk in enumerate(keys):
            phi = int(ro.hold_hash(404, 9, 2, kk, 0xFFFFFFFF)) % 24
            for j, col in enumerate((4, 5)):
                h = int(ro.hold_hash(404, 9, 2, kk, col, (tick + phi) // 24))
                assert u[i, j] == float(ro.hold_uniform(h))
    p = Stub([0.0] * 6, [1.0] * 6, seed=9, salt=2, k=24)
    p.tick = 37
    p.gen[:] = 0
    np.testing.assert_array_equal(p.noise(3, [4, 5]), ro.hold_noise(9, 2, [key(s) for s in range(3)], [4, 5], 37, 24))


# --------------------------------------------------------------------- #
# 2) 조향 열 = 결정 모드
# --------------------------------------------------------------------- #


def test_steering_columns_bit_identical_to_deterministic(tiny6):
    cfg_path, model = tiny6
    det = make_policy({"kind": "learned", "model": str(model)})
    hold = ro.build_policy({"kind": "learned", "model": str(model), "mode": "hold", "hold_k": 24}, 10000)
    assert isinstance(hold, ro.HoldLearned) and hold.k == 24 and hold.salt == 0
    w = World(load_v2_config(cfg_path), seeds=[10000])
    for _ in range(20):
        obs = w.observe()
        a_det = np.asarray(det(obs), dtype=np.float64)
        a = hold(obs)
        assert a.dtype == np.float64 and a.shape == (w.N, 6)
        np.testing.assert_array_equal(a[:, :4], a_det[:, :4])                 # 비트 단위
        assert not np.array_equal(a[:, 4:], a_det[:, 4:])
        w.step(a_det)
    # float64 관측도 predict 와 같은 float32 로 들어간다
    o64 = _obs8().astype(np.float64)
    np.testing.assert_array_equal(hold(o64)[:, :4], np.asarray(det(o64), dtype=np.float64)[:, :4])
    np.testing.assert_allclose(hold(o64)[:, 3], 1 / (1 + np.exp(-3.0)), atol=1e-6)    # 자르기(μ 3.5)


def test_sampled_columns_follow_formula(tiny6):
    _, model = tiny6
    hold = ro.build_policy({"kind": "learned", "model": str(model), "mode": "hold", "hold_k": 5, "salt": 3}, 7)
    obs = _obs8()
    mu, sd = hold.distribution(obs)
    np.testing.assert_allclose(sd, np.broadcast_to(np.exp(LOG_STD6), sd.shape), rtol=1e-6)
    u = ro.hold_noise(7, 3, [key(s) for s in range(len(obs))], [4, 5], 0, 5)
    a = hold(obs)
    np.testing.assert_array_equal(hold.last_u, u)
    raw = np.clip(mu[:, 4:] + sd[:, 4:] * ndtri(u), -3, 3)
    np.testing.assert_array_equal(a[:, 4:], 1 / (1 + np.exp(-raw)))


# --------------------------------------------------------------------- #
# 3) 유지·위상·리스폰
# --------------------------------------------------------------------- #


def test_k1_draws_fresh_noise_every_tick():
    p = Stub([0.0] * 6, [1.0] * 6, k=1)
    obs = np.zeros((128, 8), np.float32)
    acts = np.stack([p(obs) for _ in range(6)])
    for t in range(5):
        assert (acts[t, :, 4:] != acts[t + 1, :, 4:]).all()
    np.testing.assert_array_equal(acts[:, :, :4], np.broadcast_to(0.5, acts[:, :, :4].shape))


def test_k24_holds_within_block_and_changes_at_boundaries():
    k = 24
    p = Stub([0.0, 0.0, 0.0, 0.0, 0.4, -0.2], [1.0] * 6, k=k)
    n, T = 128, 3 * k
    obs = np.zeros((n, 8), np.float32)
    acts = np.stack([p(obs) for _ in range(T)])                    # (T, n, 6)
    phase = ro.hold_phase(10000, 0, [key(s) for s in range(n)], k)
    changed = (acts[1:, :, 4:] != acts[:-1, :, 4:]).any(-1)         # (T-1, n): tick t → t+1 에서 바뀌었나
    for i in range(n):
        want = [((t + 1 + phase[i]) % k == 0) for t in range(T - 1)]   # 블록 경계 = (tick + φ) 가 K 의 배수
        assert changed[:, i].tolist() == want, i
    assert len(np.unique(phase)) >= 18                              # 128 개체가 24 위상에 흩어진다
    # 한 tick 에 바뀌는 개체는 일부뿐이다 (모두 함께 바뀌지 않는다)
    assert changed.sum(1).max() < n // 4


def test_respawn_changes_key_and_noise_immediately():
    p = Stub([0.0] * 6, [1.0] * 6, k=24)
    obs = np.zeros((128, 8), np.float32)
    phase = ro.hold_phase(10000, 0, [key(s) for s in range(128)], 24)
    a0 = p(obs)
    # 다음 tick 에서 블록이 바뀌지 않는 개체들 가운데 셋을 죽인다
    stay = np.flatnonzero((1 + phase) % 24 != 0)
    dead = np.zeros(128, bool)
    dead[stay[:3]] = True
    p.observe_done(dead)
    assert p.gen[dead].tolist() == [1, 1, 1] and p.gen[~dead].sum() == 0
    a1 = p(obs)
    assert (a1[dead, 4:] != a0[dead, 4:]).all()
    keep = np.zeros(128, bool)
    keep[stay] = True
    keep &= ~dead
    np.testing.assert_array_equal(a1[keep, 4:], a0[keep, 4:])
    # 새 키 = 슬롯·2^32 + 1, 위상도 새 키에서 다시 정한다
    np.testing.assert_array_equal(p.keys(128)[dead], [key(s, 1) for s in np.flatnonzero(dead)])
    np.testing.assert_array_equal(p.last_u[dead], ro.hold_noise(10000, 0, [key(s, 1) for s in np.flatnonzero(dead)],
                                                                [4, 5], 1, 24))
    # 두 번 죽으면 세대 2
    p.observe_done(dead)
    assert p.gen[dead].tolist() == [2, 2, 2]


def test_noise_is_reproducible_and_seed_dependent():
    obs = np.zeros((128, 8), np.float32)
    s1 = [Stub([0.0] * 6, [1.0] * 6, seed=10000)(obs) for _ in range(2)]
    np.testing.assert_array_equal(s1[0], s1[1])
    other = Stub([0.0] * 6, [1.0] * 6, seed=10001)(obs)
    salted = Stub([0.0] * 6, [1.0] * 6, seed=10000, salt=1)(obs)
    assert not np.array_equal(s1[0][:, 4:], other[:, 4:]) and not np.array_equal(s1[0][:, 4:], salted[:, 4:])


# --------------------------------------------------------------------- #
# 4) 칸 확률
# --------------------------------------------------------------------- #


def _speed_cell(a):
    return (a >= SPEED_T[0]).astype(int) + (a >= SPEED_T[1]).astype(int)


@pytest.mark.parametrize("mu,sd", [(0.0, 1.0), (0.8, 0.5), (-1.2, 1.3), (2.5, 0.7)])
def test_cell_frequencies_match_analytic_phi(mu, sd):
    """많은 개체 × 블록에서 speed 칸 빈도 = [Φ(b0), Φ(b1) − Φ(b0), 1 − Φ(b1)], b_j = (logit(t_j) − μ)/σ."""
    n_agents, n_blocks = 2048, 20
    keys = [key(s, g) for s in range(n_agents // 2) for g in range(2)]
    u = np.concatenate([ro.hold_noise(10000, 0, keys, [4], 24 * b, 24)[:, 0] for b in range(n_blocks)])
    a = 1 / (1 + np.exp(-np.clip(mu + sd * ndtri(u), -3, 3)))
    emp = np.bincount(_speed_cell(a), minlength=3) / len(a)
    p = ro.hold_cell_bounds(mu, sd, SPEED_T)
    want = np.array([p[0], p[1] - p[0], 1 - p[1]])
    np.testing.assert_allclose(emp, want, atol=0.01)
    assert want[0] == pytest.approx(0.5 * (1 + math.erf((math.log(0.5) - mu) / sd / math.sqrt(2))), abs=1e-12)


def test_cells_by_boundary_match_thresholding_continuous_value():
    """Φ⁻¹ 없는 경계 비교(C++ 꼴) = 연속값 sigmoid(clip(μ + σΦ⁻¹(u))) 의 문턱 칸. 다른 것은 동률 근처(측도 0)뿐이다."""
    rng = np.random.default_rng(0)
    n = 200_000
    mu = rng.uniform(-4, 4, n)
    sd = np.exp(rng.uniform(-2, 1, n))
    u = ro.hold_uniform(ro.hold_hash(404, 1, 2, np.arange(n), 4, 0))
    raw = mu + sd * ndtri(u)
    a = 1 / (1 + np.exp(-np.clip(raw, -3, 3)))
    got = ro.hold_cells(mu, sd, u, SPEED_T)
    want = _speed_cell(a)
    lt = np.log(np.array(SPEED_T) / (1 - np.array(SPEED_T)))
    near = (np.abs(raw[:, None] - lt[None, :]) < 1e-9).any(1)
    assert ((got == want) | near).all() and near.sum() < 5
    vig = ro.hold_cells(mu, sd, u, [VIG_T], strict=True)
    assert ((vig == (a > VIG_T)) | (np.abs(raw) < 1e-9)).all()
    # 자르기: logit(t) ≤ −3 이면 늘 넘고(p = 0), > 3 이면 못 넘는다(p = 1). t = 0·1 도 그렇다
    np.testing.assert_array_equal(ro.hold_cell_bounds([0.0, 5.0, -5.0], [1.0, 1.0, 1.0], [0.0, 0.01, 0.99, 1.0]),
                                  [[0, 0, 1, 1]] * 3)
    a_lo = 1 / (1 + np.exp(-np.clip(-5 + 0.1 * ndtri(u[:1000]), -3, 3)))
    assert (a_lo >= 0.01).all() and (ro.hold_cells(np.full(1000, -5.0), np.full(1000, 0.1), u[:1000], [0.01]) == 1).all()


# --------------------------------------------------------------------- #
# 5) 결정·확률 모드 롤아웃은 그대로
# --------------------------------------------------------------------- #

CKPT = ROOT / "ckpt" / "v2" / "v2_2_s0.zip"
CKPT_SHA1 = "581c2b64efe0"                         # results/v2/stage1_v2_2.md 1-6 모델표
# 이 기능 전(HEAD 30504c9 의 env_v2/rollout.py)으로 잰 값: configs/v2_2.yaml, 시드 10000, 60스텝, tail 0
PRE_DIGEST = {"deterministic": ("49258e8a89930423", 1.185338092105),
              "stochastic": ("de5ad6be5b6f34d2", 1.4421349921517432)}


def _row_digest(r) -> str:
    h = hashlib.sha1()
    for k in ("_act_sum", "_act_sq", "_obs_sum"):
        h.update(np.ascontiguousarray(np.asarray(r[k], dtype=np.float64)).tobytes())
    h.update(np.array([r[c] for c in ("g_gamma", "mean_return", "survival", "b8", "vig_frac")], np.float64).tobytes())
    return h.hexdigest()[:16]


@pytest.mark.skipif(not CKPT.exists() or dg.model_fingerprint(CKPT) != CKPT_SHA1,
                    reason="ckpt/v2/v2_2_s0.zip (1-6 모델) 이 없다 — 학습 산출물은 커밋하지 않는다")
@pytest.mark.parametrize("mode", ["deterministic", "stochastic"])
def test_det_and_stochastic_rollouts_bit_identical_to_before(mode):
    spec = {"kind": "learned", "model": str(CKPT)}
    if mode == "stochastic":
        spec["mode"] = "stochastic"
    r = ro.rollout(load_v2_config(V2_2), ro.build_policy(spec, 10000), 10000, 60, tail=0)
    digest, g = PRE_DIGEST[mode]
    assert r["g_gamma"] == g and _row_digest(r) == digest


def _old_rollout_sums(cfg, policy, seed, steps):
    """이 기능 전 rollout 의 행동 루프(훅 없음)를 그대로 옮긴 재계산."""
    w = World(cfg, seeds=[seed])
    act_sum = np.zeros(w.act_dim)
    rew = np.empty((steps, w.N))
    done = np.empty((steps, w.N), dtype=bool)
    for t in range(steps):
        a = np.asarray(policy(w.observe()), dtype=np.float64)
        act_sum += a.sum(0)
        _, rew[t], done[t], _ = w.step(a)
    return act_sum, ro.g_gamma(rew, done, ro.load_gamma(), 0)


@pytest.mark.parametrize("mode", ["deterministic", "stochastic"])
def test_det_and_stochastic_rollouts_equal_recomputation(tiny6, mode):
    cfg_path, model = tiny6
    cfg = load_v2_config(cfg_path)
    spec = {"kind": "learned", "model": str(model), **({"mode": mode} if mode == "stochastic" else {})}
    pol = ro.build_policy(spec, 10000)
    assert getattr(pol, "observe_done", None) is None                 # 훅이 없으니 rollout 이 달라질 수 없다
    r = ro.rollout(cfg, pol, 10000, 30, tail=0)
    act_sum, g = _old_rollout_sums(cfg, ro.build_policy(spec, 10000), 10000, 30)
    np.testing.assert_array_equal(r["_act_sum"], act_sum)
    assert r["g_gamma"] == g


class _Recorder:
    """고정 행동을 내고 observe_done 호출을 적는 정책."""

    def __init__(self, act):
        self.act, self.calls = np.asarray(act, np.float64), []

    def __call__(self, obs):
        return np.tile(self.act, (len(obs), 1))

    def observe_done(self, done):
        self.calls.append(np.array(done, copy=True))


def test_rollout_calls_observe_done_after_every_step(tiny6):
    cfg_path, _ = tiny6
    cfg = load_v2_config(cfg_path).replace(N=16)
    rec = _Recorder([0.0, 0.5, 0.5, 0.5, 0.0, 0.0])                  # 먹지 않고 서 있기 — 굶어 죽는 개체가 생긴다
    steps = 400
    w = World(cfg, seeds=[3])
    want = []
    for _ in range(steps):
        want.append(w.step(np.tile(rec.act, (w.N, 1)))[2])
    r = ro.rollout(cfg, rec, 3, steps, tail=0)
    assert len(rec.calls) == steps
    np.testing.assert_array_equal(np.stack(rec.calls), np.stack(want))
    assert np.stack(rec.calls).any() and r["_act_n"] == steps * cfg.N


# --------------------------------------------------------------------- #
# 6) 래퍼가 리스폰 훅을 넘긴다
# --------------------------------------------------------------------- #


def _plain_factory(base, spec, seed):
    """observe_done 이 없는 외부 factory 래퍼 (행동을 그대로 넘긴다)."""
    return lambda obs: base(obs)


WRAPS = [
    {"kind": "act_fix", "dims": [1], "values": [0, 0.5, 0, 0, 0, 0]},
    {"kind": "act_permute", "salt": 0},
    {"kind": "obs_fix", "dims": [7], "values": [0.3]},
    {"kind": "obs_permute", "dims": [0], "salt": 0},
    {"kind": "seg_const", "bins": [[4, [0.5]]], "dims": [1], "table": [0.2, 0.8]},
    {"factory": "test_hold_mode_v2:_plain_factory"},
]


@pytest.mark.parametrize("w", WRAPS, ids=lambda w: w.get("kind") or "factory")
def test_wrappers_forward_observe_done(tiny6, w):
    _, model = tiny6
    hold = {"kind": "learned", "model": str(model), "mode": "hold", "hold_k": 24}
    pol = ro.build_policy({"policy": hold, "wrap": [w, {"kind": "act_fix", "dims": [], "values": [0] * 6}]}, 10000)
    base = pol
    while not isinstance(base, ro.HoldLearned):
        base = getattr(base, "base", None) or getattr(base, "policy")
    obs = _obs8()
    assert pol(obs).shape == (128, 6)
    dead = np.zeros(128, bool)
    dead[[2, 9]] = True
    pol.observe_done(dead)
    assert base.gen[[2, 9]].tolist() == [1, 1] and base.gen.sum() == 2
    # 결정 모드 바탕이면 넘길 곳이 없어 아무 일도 없다
    det = ro.build_policy({"policy": {"kind": "learned", "model": str(model)}, "wrap": [w]}, 10000)
    ro.forward_done(det, dead)


# --------------------------------------------------------------------- #
# 7) 스펙 검사
# --------------------------------------------------------------------- #


def test_hold_spec_validation(tiny6):
    _, model = tiny6
    m = str(model)
    assert "hold" in ro.ACTION_MODES
    assert ro.action_mode({"policy": {"kind": "learned", "model": m, "mode": "hold", "hold_k": 3}, "wrap": []}) == "hold"
    assert ro.hold_k_of({"kind": "learned", "model": m, "mode": "hold", "hold_k": 3}) == 3
    assert ro.hold_k_of({"kind": "learned", "model": m}) is None
    for bad in ({"mode": "hold"}, {"mode": "hold", "hold_k": 0}, {"mode": "hold", "hold_k": -2},
                {"mode": "hold", "hold_k": 2.5}, {"mode": "hold", "hold_k": True}, {"hold_k": 24},
                {"mode": "stochastic", "hold_k": 24}):
        with pytest.raises(ValueError):
            ro.build_policy({"kind": "learned", "model": m, **bad}, 0)
    with pytest.raises(ValueError, match="학습 정책"):
        ro.build_policy({"kind": "utility", "mode": "hold", "hold_k": 24}, 0)
    assert ro._SALT["act_hold"] == ro.HOLD_TAG == 404
    assert ro.HOLD_TAG not in (ro._SALT["act_permute"], ro._SALT["obs_permute"], ro._SALT["act_sample"])


def test_hold_rollout_is_reproducible_and_differs_from_deterministic(tiny6):
    cfg_path, model = tiny6
    cfg = load_v2_config(cfg_path)
    spec = {"kind": "learned", "model": str(model), "mode": "hold", "hold_k": 24}
    r1 = ro.rollout(cfg, ro.build_policy(spec, 10000), 10000, 40, tail=0)
    r2 = ro.run_specs(cfg, {"h": spec}, [10000], 40, workers=1, tail=0)["h"][0]
    rd = ro.rollout(cfg, ro.build_policy({"kind": "learned", "model": str(model)}, 10000), 10000, 40, tail=0)
    assert ro.public_row(r1) == ro.public_row(r2)
    np.testing.assert_array_equal(r1["_act_sum"], r2["_act_sum"])
    assert not np.array_equal(r1["_act_sum"][4:], rd["_act_sum"][4:])


# --------------------------------------------------------------------- #
# 8) diagnose_v2
# --------------------------------------------------------------------- #


def test_explore_seeds_are_disjoint():
    ex = set(dg.EXPLORE_SEEDS)
    assert (min(ex), max(ex), len(ex)) == (12000, 12039, 40)
    assert not ex & set(range(0, 1000)) and not ex & set(range(10000, 10020)) and not ex & set(dg.RESCORE_SEEDS)
    assert list(dg.RESCORE_SEEDS) == list(range(100, 120))


def test_diagnose_hold_names_cache_and_meta(tiny6, tmp_path):
    cfg_path, model = tiny6
    P = dg.build_parser()
    base = ["ablate", "--model", str(model), "--config", str(cfg_path), "--out", str(tmp_path)]
    det = dg.Ctx(P.parse_args(base))
    sto = dg.Ctx(P.parse_args(base + ["--act-mode", "stochastic"]))
    h24 = dg.Ctx(P.parse_args(base + ["--act-mode", "hold", "--hold-k", "24"]))
    h16 = dg.Ctx(P.parse_args(base + ["--act-mode", "hold", "--hold-k", "16"]))
    assert h24.spec == {"kind": "learned", "model": str(model.resolve()), "mode": "hold", "hold_k": 24}
    names = {c.name for c in (det, sto, h24, h16)}
    assert names == {"m_v2_2", "m_v2_2_stoch", "m_v2_2_hold24", "m_v2_2_hold16"}
    files = [dg.calib_cache_key(c)[0].name for c in (det, sto, h24, h16)]
    assert files == ["calib.npz", "calib_stochastic.npz", "calib_hold24.npz", "calib_hold16.npz"]
    k24, k16 = dg.calib_cache_key(h24)[1], dg.calib_cache_key(h16)[1]
    assert k24["act_mode"] == "hold" and k24["hold_k"] == 24 and k24 != k16
    assert set(dg.calib_cache_key(det)[1]) == {"spec", "seeds", "steps", "record_every", "config_digest", "model_sha1"}
    assert h24.meta()["hold_k"] == 24 and "hold_k" not in det.meta() and "hold_k" not in sto.meta()
    assert "K=24" in dg.md_meta(h24.meta())[2]
    # 같은 --name 이어도 K 가 다르면 이전 ablate 의 C0 를 쓰지 않는다
    rows = [{"seed": s, "g_gamma": 1.0} for s in h24.eval_seeds]
    dg.save_json(tmp_path / "ablate.json", {"meta": h24.meta(), "per_seed": {"C0": rows}})
    assert dg.reference_rows(h24, "C0") == rows
    assert dg.reference_rows(h16, "C0") is None and dg.reference_rows(det, "C0") is None
    for argv in (["--act-mode", "hold"], ["--hold-k", "24"], ["--act-mode", "stochastic", "--hold-k", "24"],
                 ["--act-mode", "hold", "--hold-k", "0"]):
        with pytest.raises(SystemExit):
            dg.Ctx(P.parse_args(base + argv))
    with pytest.raises(SystemExit):
        dg.Ctx(P.parse_args(["ablate", "--policy", "utility", "--act-mode", "hold", "--hold-k", "24"]))


def test_diagnose_ablate_runs_in_hold_mode(tiny6, tmp_path, monkeypatch):
    """ablate(C1·C3-k·C1′ 래퍼가 유지 표본 바탕 위에 씌워진다)이 짧게 돈다."""
    monkeypatch.setattr(dg, "CACHE", tmp_path / "cache")
    cfg_path, model = tiny6
    common = ["--config", str(cfg_path), "--eval-seeds", "10000", "10001", "--eval-steps", "30", "--tail", "0",
              "--calib-seeds", "0", "--calib-steps", "20", "--workers", "1", "--no-utility"]
    assert dg.main(["ablate", "--model", str(model), "--act-mode", "hold", "--hold-k", "4",
                    "--out", str(tmp_path / "h")] + common) == 0
    d = json.loads((tmp_path / "h" / "ablate.json").read_text(encoding="utf-8"))
    assert d["meta"]["act_mode"] == "hold" and d["meta"]["hold_k"] == 4
    assert "C1'" in d["per_seed"] and (tmp_path / "cache" / "m_v2_2_hold4" / "calib_hold4.npz").exists()
    assert "hold K=4" in (tmp_path / "h" / "ablate.md").read_text(encoding="utf-8")


def _fake(run, g, *, act_mode="deterministic", hold_k=None):
    meta = {"eval_seeds": list(range(10000, 10020)), "eval_steps": 5000, "gamma": 0.99, "tail": 600, "head": 0,
            "act_mode": act_mode, "config_digest": "cfg", "config_version": "2.2", "model_gamma": 0.99,
            "model_sha1": f"m{run}", "spec": {"kind": "learned", "model": f"none/{run}.zip"}}
    if hold_k is not None:
        meta["hold_k"] = hold_k
    rows = []
    for s, v in zip(meta["eval_seeds"], g):
        r = {"seed": s, "g_gamma": float(v), "survival": 400.0 + v, "starve_rate": 1e-4,
             "predation_rate": 1e-3 - 1e-5 * v, "mean_return": 30.0 + v}
        r.update({c: 0.5 for c in dg.BEHAVIOR + ["repro"]})
        rows.append(r)
    return {"meta": meta, "per_seed": {"C0": rows}, "_dir": f"fake/{act_mode}{hold_k or ''}_{run}"}


def test_mode_compare_accepts_hold_as_second_mode():
    rng = np.random.default_rng(0)
    base = [10 + rng.standard_normal(20) for _ in range(3)]
    det = [_fake(i, b) for i, b in enumerate(base)]
    hold = [_fake(i, b + 1.0 + 0.01 * rng.standard_normal(20), act_mode="hold", hold_k=24) for i, b in enumerate(base)]
    r = dg.mode_compare(det, hold, reps=200)
    assert r["mode2"] == "hold" and r["hold_k"] == 24
    assert r["groups"][0]["cols"]["g_gamma"]["diff"] == pytest.approx(1.0, abs=0.01) and r["groups"][0]["trigger"]
    md = "\n".join(dg.md_modecmp(dg.clean(r)))
    assert "유지 표본 K24" in md and "모드 차 신호" in md
    sto = [_fake(i, b, act_mode="stochastic") for i, b in enumerate(base)]
    assert "mode2" not in dg.mode_compare(det, sto, reps=50)                          # 확률 모드 결과 모양 그대로
    with pytest.raises(SystemExit):
        dg.mode_compare(det, hold[:2] + [_fake(2, base[2], act_mode="hold", hold_k=16)], reps=50)   # K 가 섞였다
    with pytest.raises(SystemExit):
        dg.mode_compare(det, hold[:2] + sto[2:], reps=50)                             # 모드가 섞였다
