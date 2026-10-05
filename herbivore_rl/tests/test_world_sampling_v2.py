"""S1-a 학습 세계 균형 추출과 세계 시드 분리 (10-04 사용자 결정, results/v2/s1a/PREREG.md).

`world_params` 가 World.reset 의 무작위화 값과 같다, world_sampling 이 없으면 세계 고르기가 예전과 같다(메타 난수 소비 포함),
균형 추출은 결정적이고 동시에 도는 시드를 겹치지 않으며 후보 1개면 균등 추출과 같다, 시간 평균 편차를 줄인다,
설정 검사, `train_v2 --world-seed` 를 주지 않으면(또는 --seed 와 같으면) 학습이 비트 단위로 같고 메타에 world_seed 가 남는다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import json

import numpy as np
import pytest
import yaml

from env.config import ROOT, load_config
from env_v2.config import load_v2_config
from env_v2.vec_env import MultiWorldVecEnv, world_sampling_params
from env_v2.world import WORLD_PARAM_KEYS, World, world_params

V2_1 = ROOT / "configs" / "v2_1.yaml"
BAL = ROOT / "configs" / "v2_1_bal.yaml"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def cfgs():
    return load_v2_config(V2_1), load_v2_config(BAL)


@pytest.mark.parametrize("seed", [0, 7, 636, 999, 12000])
def test_world_params_match_world_reset(cfgs, seed):
    for cfg in (cfgs[0], load_config()):
        w = World(cfg, seeds=[seed])
        p = world_params(cfg, seed)
        assert tuple(p) == WORLD_PARAM_KEYS
        assert p["world_size"] == w.size and p["predator_count"] == w.M
        assert p["pred_speed_mult"] == w.pred_speed_mult and p["ranged_frac"] == w.ranged_frac
        assert p["cover_frac"] == w.cover_frac_target and p["food_regen_mult"] == w.food_regen_mult


def _plain_sequence(meta_seed, k, n_more):
    """world_sampling 이 없던 때의 고르기 규칙을 그대로 다시 쓴 것 (초기 k 개 + 교체 n_more 번, 교체는 슬롯 0 자리)."""
    rng = np.random.default_rng(meta_seed)
    pool = np.arange(1000)

    def pick(exclude):
        exclude = set(exclude)
        while True:
            s = int(rng.choice(pool))
            if s not in exclude:
                return s

    cur = []
    for _ in range(k):
        cur.append(pick(cur))
    seq = list(cur)
    for _ in range(n_more):
        cur[0] = pick(cur[1:])
        seq.append(cur[0])
    return seq


def test_uniform_sampling_unchanged(cfgs):
    """world_sampling 이 없으면 세계 고르기(메타 난수 소비 포함)가 예전 규칙과 같다."""
    v = MultiWorldVecEnv(cfgs[0], num_worlds=4, meta_seed=31)
    assert v._ws is None
    got = v.current_seeds()
    for _ in range(6):
        v._renew(0)
        got.append(v.worlds[0].seed)
    assert got == _plain_sequence(31, 4, 6)


def test_balanced_with_one_candidate_is_uniform(cfgs):
    """후보 1개면 고를 것이 없으므로 균등 추출과 같은 순서다."""
    c = cfgs[1]
    t = dict(c.v2["train"])
    t["world_sampling"] = dict(t["world_sampling"], candidates=1)
    v = MultiWorldVecEnv(c.replace(v2=dict(c.v2, train=t)), num_worlds=4, meta_seed=31)
    got = v.current_seeds()
    for _ in range(6):
        v._renew(0)
        got.append(v.worlds[0].seed)
    assert got == _plain_sequence(31, 4, 6)


def test_balanced_is_deterministic_distinct_and_keeps_the_mean_near_the_pool(cfgs):
    a = MultiWorldVecEnv(cfgs[1], num_worlds=8, meta_seed=50)
    b = MultiWorldVecEnv(cfgs[1], num_worlds=8, meta_seed=50)
    assert a.current_seeds() == b.current_seeds()
    for _ in range(40):
        k = len(a.ws_picked) % 8
        a._renew(k)
        b._renew(k)
        cur = a.current_seeds()
        assert len(set(cur)) == 8                      # 동시에 도는 세계는 겹치지 않는다
    assert a.ws_picked == b.ws_picked and len(a.ws_picked) == 48
    z = np.array([a._ws_z[s] for s in a.ws_picked])
    assert np.all(np.abs(z.mean(0)) < 0.05)            # 표준화 평균이 풀 평균 근처
    fr = np.array([world_params(cfgs[1], s)["food_regen_mult"] for s in a.ws_picked])
    assert abs(fr.mean() - 1.249) < 0.03
    # 균등 추출과 비교: 같은 메타 시드에서 평균 편차가 더 작다
    u = _plain_sequence(50, 8, 40)
    zu = np.array([a._ws_z[s] for s in u])
    assert np.linalg.norm(z.mean(0)) < np.linalg.norm(zu.mean(0))


@pytest.mark.parametrize("raw, match", [
    ({"mode": "stratified", "candidates": 8, "keys": ["food_regen_mult"]}, "balanced"),
    ({"mode": "balanced", "candidates": 0, "keys": ["food_regen_mult"]}, "candidates"),
    ({"mode": "balanced", "candidates": 8, "keys": ["food"]}, "keys"),
    ({"mode": "balanced", "candidates": 8, "keys": []}, "keys"),
    ({"mode": "balanced", "candidates": 8}, "모두"),
    ({"mode": "balanced", "candidates": True, "keys": ["food_regen_mult"]}, "candidates"),
])
def test_world_sampling_params_rejected(raw, match):
    with pytest.raises(ValueError, match=match):
        world_sampling_params(raw)


def test_bal_config_world_is_v2_1(cfgs):
    """v2_1_bal.yaml 의 세계는 v2_1.yaml 과 같고 train.world_sampling 만 더했다. v2_1.yaml 의 digest 는 그대로다."""
    from diagnose_v2 import config_digest

    a, b = cfgs
    assert a.v2["features"] == b.v2["features"]
    for k, v in a.to_dict().items():
        if k != "v2":
            assert getattr(b, k) == v, k
    assert {k: v for k, v in b.v2["train"].items() if k != "world_sampling"} == a.v2["train"]
    assert config_digest(a) == "f068496361f9"


def _tiny(tmp_path, extra):
    import train_v2

    raw = yaml.safe_load(V2_1.read_text(encoding="utf-8"))
    raw["train"].update(num_worlds=2, rollout_world_steps=8)
    cfg_path = tmp_path / "tiny.yaml"
    cfg_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    out = tmp_path / f"m{len(extra)}.zip"
    assert train_v2.main(["--steps", "64", "--seed", "3", "--config", str(cfg_path), "--out", str(out),
                          "--tb", str(tmp_path / "tb"), "--threads", "1", *extra]) == 0
    return out


def test_world_seed_default_is_bit_identical(tmp_path):
    """--world-seed 를 안 주거나 --seed 와 같은 값을 주면 학습이 비트 단위로 같다. 메타에 world_seed 가 남는다."""
    import torch
    from stable_baselines3 import PPO

    a = _tiny(tmp_path, [])
    b = _tiny(tmp_path, ["--world-seed", "3"])
    c = _tiny(tmp_path, ["--world-seed", "4", "--probe-every", "0"])
    sa, sb = PPO.load(a, device="cpu").policy.state_dict(), PPO.load(b, device="cpu").policy.state_dict()
    assert all(torch.equal(sa[k], sb[k]) for k in sa)
    ma = json.loads(a.with_suffix(".json").read_text(encoding="utf-8"))
    mc = json.loads(c.with_suffix(".json").read_text(encoding="utf-8"))
    assert ma["world_seed"] == 3 and ma["seed"] == 3 and mc["world_seed"] == 4 and mc["seed"] == 3


def test_world_pool_min_filters_training_pool_only(cfgs):
    """train.world_pool_min 은 학습 풀에서 하한 아래 세계만 뺀다. 없으면 풀이 그대로다."""
    from env_v2.vec_env import world_pool_min_params

    base = cfgs[0]
    t = dict(base.v2["train"])
    t["world_pool_min"] = {"food_regen_mult": 1.0}
    v = MultiWorldVecEnv(base.replace(v2=dict(base.v2, train=t)), num_worlds=4, meta_seed=5)
    fr = np.array([world_params(base, int(s))["food_regen_mult"] for s in v.pool])
    assert fr.min() >= 1.0 and 600 < len(v.pool) < 720          # U[0.5, 2.0] 에서 1.0 이상은 약 2/3
    assert all(world_params(base, s)["food_regen_mult"] >= 1.0 for s in v.current_seeds())
    assert len(MultiWorldVecEnv(base, num_worlds=4, meta_seed=5).pool) == 1000
    for bad in ({"food": 1.0}, {"food_regen_mult": "1"}, {}):
        with pytest.raises(ValueError):
            world_pool_min_params(bad)
