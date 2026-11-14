"""R9 두뇌 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 7-4·7-5·7-10, 12절 시험 16·27).

16. numpy 고정 두뇌 = SB3 `predict(deterministic=True)`: 작은 PPO(115 → 64 → 64 → 19, tanh — 학습은 안 함)에서 세 층을 꺼내 관측 1,024 개의
    로짓 차 < 1e-5, 행동이 같다. Gumbel-max 표본의 분포 = softmax(20 만 번).
27. npz 몸 해시가 다르면 세계(load_brain)가 거부한다(입출력 해시·종·이름·모양·형식도). 상대 두뇌 종류(규칙·학습·확률·가장 높은 칸)를
    바꿔도 decide_block 의 난수 소비가 같다(세계 없이 볼 수 있는 부분 — 세계를 붙인 판은 21 과 함께 나중 단계).
규칙 두뇌 9 개(7-5, S′ S4 2026-11-12): 관측 115 칸만 읽고 정해진 대로 고르는지 손 관측으로 본다. S′ 세계는 EAT = 그 자리에서 먹기,
SHELTER = 제자리 서기라 규칙 두뇌가 먹이(food_dir)·은신처(shelter_x·y) 쪽으로 직접 걷거나 뛴다 — 예전 시험의 '도망 → SHELTER',
'배고픔 → EAT', '사체 느낌(food_density) → EAT' 기대값을 S4 뜻으로 바꿨다(목록은 s_impl/WORLD.md). 모든 규칙에 막힘 기억 2 칸이 붙는다.
시드는 시험 범위 44350~44399 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch 보다 먼저

import copy
import json

import gymnasium as gym
import numpy as np
import pytest
import torch

from env.config import ROOT
from env_v2 import r9_body as B
from env_v2 import r9_brains as R

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def cfg():
    return B.load_r9_config(CFG)


class _Env(gym.Env):
    observation_space = gym.spaces.Box(-1.0, 1.0, (B.OBS_DIM,), np.float32)
    action_space = gym.spaces.Discrete(B.N_ACTIONS)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return np.zeros(B.OBS_DIM, np.float32), {}

    def step(self, a):
        return np.zeros(B.OBS_DIM, np.float32), 0.0, False, False, {}


@pytest.fixture(scope="module")
def ppo():
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    torch.set_num_threads(1)
    m = PPO("MlpPolicy", DummyVecEnv([_Env]), n_steps=64, batch_size=64, seed=44350, device="cpu",
            policy_kwargs=dict(net_arch=dict(pi=[64, 64], vf=[64, 64]), activation_fn=torch.nn.Tanh))
    # SB3 starts action_net at gain 0.01 (logits ~1e-2). Re-draw the three layers at a trained-like scale so the 1e-5 check means
    # something (logits O(1~10), gaps ≫ float32 error).
    g = torch.Generator().manual_seed(44351)
    net = m.policy.mlp_extractor.policy_net
    with torch.no_grad():
        for lin, s in ((net[0], 0.35), (net[2], 0.4), (m.policy.action_net, 1.2)):
            lin.weight.copy_(torch.randn(lin.weight.shape, generator=g) * s)
            lin.bias.copy_(torch.randn(lin.bias.shape, generator=g) * 0.3)
    return m


def _torch_logits(m, obs):
    pol = m.policy
    with torch.no_grad():
        x = torch.as_tensor(obs)
        return pol.action_net(pol.mlp_extractor.forward_actor(pol.pi_features_extractor(x))).numpy()


# --------------------------------------------------------------------------- 16


def test_16_numpy_equals_sb3_predict(ppo):
    w = R.extract_sb3(ppo)
    assert {k: v.shape for k, v in w.items()} == R.NPZ_SHAPES and all(v.dtype == np.float32 for v in w.values())
    obs = np.random.default_rng(44352).uniform(-1, 1, (1024, B.OBS_DIM)).astype(np.float32)
    obs[:256] = np.clip(np.round(obs[:256] * 2) / 2, -1, 1)          # 관측 끝·0 값 섞기 (실제 관측처럼 0 칸이 많다)
    lg_np = R.forward_np(w, obs)
    lg_th = _torch_logits(ppo, obs)
    assert lg_np.dtype == np.float32 and lg_np.shape == (1024, B.N_ACTIONS)
    assert float(np.abs(lg_np - lg_th).max()) < 1e-5
    assert float(np.abs(lg_np).max()) > 1.0                           # 의미 있는 크기
    act_sb3, _ = ppo.predict(obs, deterministic=True)
    gap = R.top_gap(lg_np)
    assert int((gap < R.NEAR_TIE).sum()) == 0
    assert np.array_equal(np.asarray(act_sb3, np.int64), np.argmax(lg_np, 1))
    brain = R.MlpBrain(name="t", kind="mlp", species=B.DEER, weights=w)
    ctrl = R.Controller(brain, stochastic=False)
    a, g2 = R.decide_block(ctrl, obs, np.random.default_rng(44353), None, {})
    assert np.array_equal(a, np.asarray(act_sb3, np.int64)) and np.array_equal(g2, gap)


def test_16_gumbel_matches_softmax():
    lg = (np.random.default_rng(44354).normal(0, 1.5, B.N_ACTIONS)).astype(np.float32)
    N = 200_000
    u = np.random.default_rng(44355).random((N, B.N_ACTIONS))
    a = R.gumbel_argmax(np.broadcast_to(lg, (N, B.N_ACTIONS)), u)
    freq = np.bincount(a, minlength=B.N_ACTIONS) / N
    z = lg.astype(np.float64) - lg.max()
    p = np.exp(z) / np.exp(z).sum()
    tol = 5 * np.sqrt(p * (1 - p) / N) + 1e-4
    assert np.all(np.abs(freq - p) < tol), (freq, p)
    # u = 0 은 그 칸이 뽑히지 않는다(−inf), 동점은 낮은 번호
    u2 = np.full((1, B.N_ACTIONS), 0.5)
    u2[0, 0] = 0.0
    assert R.gumbel_argmax(np.zeros((1, B.N_ACTIONS), np.float32), u2)[0] == 1


def test_16_npz_roundtrip(tmp_path, cfg, ppo):
    w = R.extract_sb3(ppo)
    zipp = tmp_path / "src.zip"
    zipp.write_bytes(b"not a real zip - sha only")
    meta = R.brain_meta(cfg, "deer", "A", 3, 12_345_678, zipp)
    assert set(R.META_KEYS) <= set(meta) and meta["io_hash"] == B.hash_hex(B.io_hash())
    assert meta["body_hash"] == B.hash_hex(B.body_hash(cfg, B.DEER)) and len(meta["src_zip_sha256"]) == 64
    p = tmp_path / "deer_r3_12345678.npz"
    R.save_brain(p, w, meta)
    assert p.exists()
    br = R.load_brain(p, cfg, B.DEER)
    assert br.kind == "mlp" and br.species == B.DEER and br.meta == meta
    obs = np.random.default_rng(44356).uniform(-1, 1, (64, B.OBS_DIM)).astype(np.float32)
    assert np.array_equal(br.logits(obs), R.forward_np(w, obs))
    # 판정 설정의 몸 해시가 같으므로 판정 세계도 받는다
    assert R.load_brain(p, B.load_r9_config(JCFG), "deer").name == br.name
    # SB3 zip → npz 도움 함수
    zp = tmp_path / "m.zip"
    ppo.save(str(zp))
    meta2 = R.export_sb3_zip(zp, tmp_path / "m.npz", cfg, B.WOLF, "B", 0, 5)
    br2 = R.load_brain(tmp_path / "m.npz", cfg, B.WOLF)
    assert meta2["species"] == "wolf" and np.array_equal(br2.logits(obs), R.forward_np(w, obs))


# --------------------------------------------------------------------------- 27


def _write(tmp_path, name, w, meta):
    p = tmp_path / name
    R.save_brain(p, w, meta)
    return p


def test_27_load_rejects_mismatch(tmp_path, cfg, ppo):
    w = R.extract_sb3(ppo)
    meta = R.brain_meta(cfg, B.DEER, "A", 1, 100, None)
    p = _write(tmp_path, "ok.npz", w, meta)
    R.load_brain(p, cfg, B.DEER)
    # (가) 몸 해시: 그 종 몸 값이 바뀐 세계는 거부, 다른 종 몸만 바뀌면 받는다
    c2 = copy.deepcopy(cfg)
    c2["species"]["deer"]["drain"] = 0.0021
    with pytest.raises(R.BrainContractError, match="body_hash"):
        R.load_brain(p, c2, B.DEER)
    c3 = copy.deepcopy(cfg)
    c3["species"]["wolf"]["drain"] = 0.0004
    R.load_brain(p, c3, B.DEER)
    c4 = copy.deepcopy(cfg)
    c4["body_common"]["gait_drain"] = [0.714, 1.0, 2.4]                # 공통 몸 규칙은 세 종 모두
    with pytest.raises(R.BrainContractError, match="body_hash"):
        R.load_brain(p, c4, B.DEER)
    # (나) 종
    with pytest.raises(R.BrainContractError, match="species"):
        R.load_brain(p, cfg, B.WOLF)
    # (다) 입출력 해시·이름·형식·모양
    bad = dict(meta, io_hash="0x0000000000000001")
    with pytest.raises(R.BrainContractError, match="io_hash"):
        R.load_brain(_write(tmp_path, "io.npz", w, bad), cfg, B.DEER)
    bad = dict(meta, obs_names=list(B.OBS_NAMES[:-1]) + ["x"])
    with pytest.raises(R.BrainContractError, match="names"):
        R.load_brain(_write(tmp_path, "nm.npz", w, bad), cfg, B.DEER)
    bad = dict(meta, format="eco_brain")
    with pytest.raises(R.BrainContractError, match="format"):
        R.load_brain(_write(tmp_path, "fm.npz", w, bad), cfg, B.DEER)
    w2 = dict(w, W2=np.zeros((11, 64), np.float32))
    with pytest.raises(R.BrainContractError, match="W2"):
        R.save_brain(tmp_path / "sh.npz", w2, meta)
    arrays = {k: w[k] for k in R.NPZ_WEIGHT_KEYS}
    arrays["W0"] = np.zeros((64, 106), np.float32)
    arrays["meta_json"] = np.array(json.dumps(meta))
    with open(tmp_path / "sh2.npz", "wb") as fh:
        np.savez(fh, **arrays)
    with pytest.raises(R.BrainContractError, match="W0"):
        R.load_brain(tmp_path / "sh2.npz", cfg, B.DEER)


def _all_brains(cfg, ppo):
    w = R.extract_sb3(ppo)
    mlp = R.MlpBrain(name="m", kind="mlp", species=B.DEER, weights=w)
    out = [R.Controller(mlp, True, "current"), R.Controller(mlp, False, "current")]
    out += [R.Controller(R.make_rule(n, cfg, R.RULE_SPECIES[n] if R.RULE_SPECIES[n] is not None else B.DEER), st, "rule")
            for n in R.RULE_NAMES for st in (True, False)]
    return out


def test_27_rng_consumption_independent_of_brain(cfg, ppo):
    """decide_block 은 두뇌 종류·방식과 무관하게 rng.random((n, 19)) 하나만 뽑는다 — 다른 갈래가 밀리지 않는다."""
    n = 64
    obs = np.random.default_rng(44357).uniform(-1, 1, (n, B.OBS_DIM)).astype(np.float32)
    ref = np.random.default_rng([44358, B.DEER])
    for _ in range(3):
        ref.random((n, B.N_ACTIONS))
    want = ref.bit_generator.state
    for ctrl in _all_brains(cfg, ppo):
        rng = np.random.default_rng([44358, B.DEER])
        state = ctrl.brain.new_state(n)
        for _ in range(3):
            a, gap = R.decide_block(ctrl, obs, rng, state, {"facing_f": 0.9})
            assert a.shape == (n,) and a.dtype == np.int64 and a.min() >= 0 and a.max() < B.N_ACTIONS
            assert gap.shape == (n,)
        assert rng.bit_generator.state == want, ctrl.brain.name
        if ctrl.brain.kind == "rule":
            assert np.all(np.isinf(gap))
    # 같은 u 로 RANDOM = argmax(u)
    rng = np.random.default_rng(44359)
    u = np.random.default_rng(44359).random((n, B.N_ACTIONS))
    a, _ = R.decide_block(R.Controller(R.make_rule("RANDOM", cfg), False), obs, rng, None, {})
    assert np.array_equal(a, np.argmax(u, 1))


def test_27_stochastic_uses_u(cfg, ppo):
    """확률 행동 = Gumbel-max(로짓 + g(u)), 가장 높은 칸 = argmax(로짓). 같은 u 면 같은 행동."""
    w = R.extract_sb3(ppo)
    mlp = R.MlpBrain(name="m", kind="mlp", weights=w)
    obs = np.random.default_rng(44360).uniform(-1, 1, (32, B.OBS_DIM)).astype(np.float32)
    a1, g1 = R.decide_block(R.Controller(mlp, True), obs, np.random.default_rng(44361), None, {})
    u = np.random.default_rng(44361).random((32, B.N_ACTIONS))
    z = R.gumbel_values(R.forward_np(w, obs), u)
    assert np.array_equal(a1, np.argmax(z, 1)) and np.array_equal(g1, R.top_gap(z))
    a2, _ = R.decide_block(R.Controller(mlp, False), obs, np.random.default_rng(44361), None, {})
    assert np.array_equal(a2, np.argmax(R.forward_np(w, obs), 1))


# --------------------------------------------------------------------------- rules (7-5)


def _obs(n=1, E=0.5, stamina=1.0, health=1.0, age=1.0, edge=1.0, sx=1.0, sy=0.0, free=1.0, here=0.5, fd=None, inside=0.0):
    """here = food_here (기본 0.5: 발밑에 먹을 것 있음 — 사슴 문턱 0.06·멧돼지 0.045·늑대 1e-9 위), fd = {j: food_dir_j}."""
    o = np.zeros((n, B.OBS_DIM), np.float32)
    o[:, B.O_ENERGY], o[:, B.O_STAMINA], o[:, B.O_HEALTH], o[:, B.O_AGE_FRAC] = E, stamina, health, age
    o[:, B.O_SHELTER_EDGE], o[:, B.O_SHELTER_X], o[:, B.O_SHELTER_Y] = edge, sx, sy
    o[:, B.O_FREE0:B.O_FREE0 + 8] = free
    o[:, B.O_FOOD_HERE] = here
    o[:, B.O_IN_SHELTER] = inside
    for j, v in (fd or {}).items():
        o[:, B.O_FOOD_DIR0 + j] = v
    return o


def _other(o, j, x, y, appr=0.0, facing=0.0, size=0.5, row=0):
    """다른 종 칸 j 에 단위 (x, y) 의 개체."""
    d = np.hypot(x, y)
    vals = dict(present=1.0, rel_x=x / 20, rel_y=y / 20, dist=d / 20, approach=appr, facing=facing, size=size)
    for f, v in vals.items():
        o[row, B.other_col(j, f)] = v


def _kin(o, j, x, y, size=0.4, row=0):
    for f, v in dict(present=1.0, rel_x=x / 20, rel_y=y / 20, size=size).items():
        o[row, B.kin_col(j, f)] = v


def _one(brain, o, ctx=None, state=None):
    """state=None → 새 기억 (S4 막힘 기억이 앞 호출의 EAT 를 기억하지 않게); 이어지는 기억은 state 를 넘긴다."""
    u = np.full((o.shape[0], B.N_ACTIONS), 0.5)
    if state is None:
        state = brain.new_state(o.shape[0])
    return brain.act(o, u, False, state, ctx or {})


def test_rule_deer(cfg):
    br = R.make_rule("RULE_DEER", cfg)
    o = _obs()
    _other(o, 0, 12, 0, appr=0.2, facing=0.95)
    assert _one(br, o)[0] == B.RUN_FIRST + 4                          # 앞에서 바라보며 다가옴 → 뒤로 뛰기 (RUN_180)
    assert _one(br, o, {"facing_f": 0.97})[0] == B.EAT                 # f = 0.97 이면 바라봄 부족, 10 단위 밖
    o = _obs(edge=6 / 20)
    _other(o, 0, 0, 8, appr=0.2, facing=0.0)                          # 10 단위 안 다가옴 (바라봄 무관)
    assert _one(br, o)[0] == B.RUN_FIRST                              # 은신처 가장자리 8 단위 안 → 은신처(앞, shelter_x 1) 쪽 뛰기
    o = _obs(edge=0.0, sx=0.0, inside=1.0)
    _other(o, 0, 0, 8, appr=0.2, facing=0.0)
    assert _one(br, o)[0] == B.SHELTER                                # 은신처 안 → 제자리 서기(SHELTER)
    o = _obs()
    _other(o, 0, 0, 8, appr=0.2)
    assert _one(br, o)[0] == B.RUN_FIRST + 6                          # 왼쪽에서 → 오른쪽(270°)으로
    o = _obs()
    o[0, B.O_FREE0 + 4] = 0.1                                         # 뒤가 벽
    _other(o, 0, 8, 0, appr=0.2)
    assert _one(br, o)[0] == B.RUN_FIRST + 3                          # 다음으로 가까운 열린 쪽 135° (동점이면 낮은 번호)
    o = _obs()
    _other(o, 0, 8, 0, appr=0.1)                                      # 10 단위 안이어도 approach 0.1 ≤ 0.15, 바라봄 0
    assert _one(br, o)[0] == B.EAT
    assert _one(br, _obs(E=0.95))[0] == B.WATCH and _one(br, _obs(E=0.5))[0] == B.EAT
    # S4 먹이 찾기 (관측만): 발밑에 없으면 food_dir 가장 큰 칸 쪽 걷기, 아무것도 못 느끼면 앞으로(찾기)
    assert _one(br, _obs(here=0.0, fd={3: 0.2, 5: 0.4}))[0] == B.WALK_FIRST + 5
    assert _one(br, _obs(here=0.0))[0] == B.WALK_FIRST
    assert _one(br, _obs(here=0.05, fd={1: 0.1}))[0] == B.WALK_FIRST + 1            # 0.05 < 사슴 문턱 0.06
    assert br.params["here_min"] == R.here_min_of(cfg, B.DEER) and br.n_state == 2


def test_rule_wolf(cfg):
    br = R.make_rule("RULE_WOLF", cfg)
    assert br.n_state == 1 + 2
    assert _one(br, _obs(E=0.9, here=0.5))[0] == B.EAT                # 발밑(1.0 안) 사체 + E < 0.98 → 먹기
    assert _one(br, _obs(E=0.9, here=0.0, fd={2: 0.3}))[0] == B.WALK_FIRST + 2   # 느낀 사체 쪽 걷기 (S4)
    assert _one(br, _obs(E=0.98, here=0.5))[0] == B.WATCH
    o = _obs(E=0.5, here=0.0)
    _other(o, 0, 6, 0, size=0.5)                                      # 가까운 큰 몸
    _other(o, 1, 0, 10, size=0.4)                                     # 작은 몸 우선
    assert _one(br, o)[0] == B.WALK_FIRST + 2                         # 10 단위 > 6 → 걷기(몰래) 90°
    o = _obs(E=0.5, here=0.0)
    _other(o, 0, 0, 5.9, size=0.4)
    assert _one(br, o)[0] == B.RUN_FIRST + 2                          # 6 단위 안 → 뛰기
    # '은신처 밖': 내 은신처 중심 어림 (2 + 5.5) 단위 앞 — 그 안의 표적은 뺀다
    o = _obs(E=0.5, edge=2 / 20, sx=1.0, sy=0.0, here=0.0)
    _other(o, 0, 8, 0, size=0.3)
    _other(o, 1, -10, 0, size=0.6)
    assert _one(br, o)[0] == B.WALK_FIRST + 4
    assert _one(br, _obs(E=0.95, here=0.0))[0] == B.WATCH
    # 배고픈데 표적 없음 → 순찰 [어림]
    assert _one(br, _obs(E=0.5, here=0.0))[0] == B.WALK_FIRST
    o = _obs(E=0.5, free=0.5, here=0.0)
    o[0, B.O_FREE0] = 0.1
    o[0, B.O_FREE0 + 2] = 0.9
    assert _one(br, o)[0] == B.WALK_FIRST + 2
    # 지구력 잠김 고리(0.15 에서 잠김, 0.55 에서 풀림)를 기억으로 따라 한다
    st = br.new_state(1)
    seq = []
    for stam in (1.0, 0.1, 0.4, 0.54, 0.55, 0.4):
        o = _obs(E=0.5, stamina=stam, here=0.0)
        _other(o, 0, 0, 4, size=0.4)
        seq.append(int(_one(br, o, state=st)[0]))
    assert seq == [B.RUN_FIRST + 2, B.WALK_FIRST + 2, B.WALK_FIRST + 2, B.WALK_FIRST + 2, B.RUN_FIRST + 2, B.RUN_FIRST + 2]
    R.Brain.reset_state(st, [0])
    assert st[0, R.WS_LOCKED] == 0


def test_rule_boar(cfg):
    br = R.make_rule("RULE_BOAR", cfg)
    assert br.n_state == 3 + 2 and br.params["here_min"] == R.here_min_of(cfg, B.BOAR)
    # 뛰어서 바라보며 다가옴 + 성체·HP 충분·새끼 2 단위 안 → 그쪽으로 걷기(마주 서기)
    st = br.new_state(1)
    o = _obs()
    _other(o, 0, 2, 0, appr=0.5, facing=0.95)
    _kin(o, 0, 1, 0, size=0.3)
    assert _one(br, o, state=st)[0] == B.WALK_FIRST and st[0, R.BS_FLEE_LEFT] == 0
    # 새끼가 없으면 반대로 뛰기를 6 결정
    st = br.new_state(1)
    o = _obs()
    _other(o, 0, 2, 0, appr=0.5, facing=0.95)
    seq = [int(_one(br, o, state=st)[0])]
    for _ in range(6):
        seq.append(int(_one(br, _obs(), state=st)[0]))               # 위협이 사라져도 이어 감, 못 느끼면 곧장(RUN_0)
    assert seq == [B.RUN_FIRST + 4] + [B.RUN_FIRST] * 5 + [B.EAT]
    # 어린 멧돼지(성숙 전)는 새끼 곁이어도 도망, HP < 0.55 도 도망
    for kw in (dict(age=0.5), dict(health=0.5)):
        o = _obs(**kw)
        _other(o, 0, 2, 0, appr=0.5, facing=0.95)
        _kin(o, 0, 1, 0, size=0.3)
        assert _one(br, o, state=br.new_state(1))[0] == B.RUN_FIRST + 4, kw
    # 걸어서 다가옴 → 한 결정 그쪽으로 걷고 그 뒤 살피기, 사라지면 다시 먹기
    st = br.new_state(1)
    o = _obs()
    _other(o, 0, 0, 2, appr=0.2, facing=0.0)
    assert [int(_one(br, o, state=st)[0]) for _ in range(3)] == [B.WALK_FIRST + 2, B.WATCH, B.WATCH]
    assert _one(br, _obs(), state=st)[0] == B.EAT and st[0, R.BS_FACED] == 0
    # 3.25 단위 밖, 바라보지 않으면 도망 안 함
    o = _obs()
    _other(o, 0, 4, 0, appr=0.5, facing=0.95)
    assert _one(br, o, state=br.new_state(1))[0] == B.EAT
    o = _obs(E=0.95)
    _other(o, 0, 2, 0, appr=0.5, facing=0.5)
    assert _one(br, o, state=br.new_state(1))[0] == B.WATCH
    # 두뇌 자체 기억(state=None)과 reset
    o = _obs()
    _other(o, 0, 2, 0, appr=0.5, facing=0.95)
    br.act(o, np.full((1, 19), 0.5), False, None, {})
    assert br.state[0, R.BS_FLEE_LEFT] == 5
    br.reset([0])
    assert br.state[0, R.BS_FLEE_LEFT] == 0


def test_rule_hide_always_random(cfg):
    for name in ("HIDE_DEER", "HIDE_BOAR"):
        br = R.make_rule(name, cfg)
        o = _obs(E=0.1)
        _other(o, 3, 15, 15)
        assert _one(br, o)[0] == B.RUN_FIRST                          # 누군가 느낌 → 은신처(shelter_x 1 = 앞) 쪽 뛰기 (S4)
        o = _obs(E=0.1, edge=0.0, sx=0.0, inside=1.0)
        _other(o, 3, 15, 15)
        assert _one(br, o)[0] == B.SHELTER                            # 안이면 제자리 서기
        assert _one(br, _obs(E=0.2))[0] == B.EAT and _one(br, _obs(E=0.5))[0] == B.RUN_FIRST
        assert _one(br, _obs(E=0.2, here=0.0, fd={6: 0.3}))[0] == B.WALK_FIRST + 6
    for sp in (B.DEER, B.BOAR):
        br = R.make_rule("ALWAYS_EAT", cfg, sp)
        assert np.all(_one(br, _obs(n=5, E=1.0)) == B.EAT)
        o = _obs(n=2, E=0.5, here=0.0, fd={4: 0.2})
        _other(o, 0, 2, 0, appr=0.5, facing=0.95)
        assert np.all(_one(br, o) == B.WALK_FIRST + 4)                # 도망 없이 먹이 찾기만
    with pytest.raises(ValueError):
        R.make_rule("ALWAYS_EAT", cfg)                                # 종이 있어야 발밑 문턱을 안다
    for name, first in (("NOHUNT", B.WALK_FIRST), ("NOHUNT_RUN", B.RUN_FIRST)):
        br = R.make_rule(name, cfg)
        assert br.species == B.WOLF and br.n_state == 2
        o = _obs(E=0.5, here=0.0, fd={2: 0.3})
        _other(o, 0, 3, 0, size=0.3)                                  # 산 먹이가 앞에 있어도 사체 쪽으로만
        assert _one(br, o)[0] == first + 2
        assert _one(br, _obs(E=0.5, here=0.5))[0] == B.EAT
        o = _obs(E=0.5, here=0.0)
        _other(o, 0, 3, 0, size=0.3)
        assert _one(br, o)[0] == B.WATCH                              # 사체를 못 느끼면 산 먹이로 가지 않는다
        assert _one(br, _obs(E=0.99, here=0.5))[0] == B.WATCH
    rnd = R.make_rule("RANDOM", cfg)
    u = np.random.default_rng(44362).random((4000, B.N_ACTIONS))
    a = rnd.act(_obs(n=4000), u, False, None, {})
    assert np.array_equal(a, np.argmax(u, 1)) and np.bincount(a, minlength=19).min() > 150
    with pytest.raises(ValueError):
        R.make_rule("RULE_BEAR", cfg)


def test_rules_read_observation_only(cfg):
    """규칙 두뇌는 관측 115 칸만 받는다: 같은 관측이면 같은 행동(종 이름표가 들어올 길이 없다), 죽은 칸(관측 0)도 정해진 값."""
    o = np.random.default_rng(44363).uniform(-1, 1, (256, B.OBS_DIM)).astype(np.float32)
    u = np.random.default_rng(44364).random((256, B.N_ACTIONS))
    for name in R.RULE_NAMES:
        sp = R.RULE_SPECIES[name] if R.RULE_SPECIES[name] is not None else B.DEER
        a1 = R.make_rule(name, cfg, sp).act(o, u, False, None, {"facing_f": 0.9})
        a2 = R.make_rule(name, cfg, sp).act(o.copy(), u.copy(), True, None, {"facing_f": 0.9})
        assert np.array_equal(a1, a2), name
        z = R.make_rule(name, cfg, sp).act(np.zeros((3, B.OBS_DIM), np.float32), u[:3], False, None, {})
        assert z.shape == (3,) and z.min() >= 0 and z.max() < B.N_ACTIONS
