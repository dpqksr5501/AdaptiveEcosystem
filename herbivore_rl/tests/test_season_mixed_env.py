"""혼합 학습 세계(season/mixed_vec_env.py)의 구성과 결정성 (SEASON 4.1 분포, 5.4 부수 확인)."""

import numpy as np
import pytest

from env_v2.vec_env import MultiWorldVecEnv
from env_v2.world import world_params
from season.common import load_base, load_season, SEASONS
from season.mixed_vec_env import B_META_OFFSET, build_k2b, build_mixed


@pytest.fixture(scope="module")
def cfgs():
    return load_season(SEASONS["a"]), load_base()


def test_composition(cfgs):
    """G 4 + B 4, 슬롯 순서, 묶음 시드, 세계 매개변수가 각 설정의 범위 안."""
    g, b = cfgs
    v = build_mixed(g, b, seed=0)
    assert v.K == 8 and v.N == 128 and v.num_envs == 1024
    assert v.labels == ["G", "B"] and v.world_labels == ["G"] * 4 + ["B"] * 4
    assert v.part_slice(0) == slice(0, 512) and v.rehearsal_slice == slice(512, 1024)
    assert v.T == 4000 and [p.K for p in v.parts] == [4, 4]
    for s in v.parts[0].current_seeds():        # 시즌 (a): 포식자 10~12, 속도 1.15~1.2
        wp = world_params(g, s)
        assert 10 <= wp["predator_count"] <= 12 and 1.15 <= wp["pred_speed_mult"] <= 1.2
    for s in v.parts[1].current_seeds():        # B: 기본 범위
        wp = world_params(b, s)
        assert 2 <= wp["predator_count"] <= 12 and 0.8 <= wp["pred_speed_mult"] <= 1.2
    # 묶음은 같은 meta_seed 로 따로 만든 MultiWorldVecEnv 와 같다 (스크래치와 같은 B 시드 +7919)
    ref_g = MultiWorldVecEnv(g, num_worlds=4, meta_seed=0)
    ref_b = MultiWorldVecEnv(b, num_worlds=4, meta_seed=B_META_OFFSET)
    assert v.current_seeds() == ref_g.current_seeds() + ref_b.current_seeds()
    np.testing.assert_array_equal(v.reset(), np.concatenate([ref_g.reset(), ref_b.reset()]))
    assert v.worlds_seen() == {"per_part": {"0G": 4, "1B": 4}, "total": 8, "resets": 0}


def test_k2b_shares_b_part(cfgs):
    """K2-B 는 B + B 이고 묶음 1 이 같은 시드 후보의 B 묶음과 같다."""
    g, b = cfgs
    cand, k2b = build_mixed(g, b, seed=3), build_k2b(b, seed=3)
    assert k2b.labels == ["B", "B"] and k2b.rehearsal_slice == cand.rehearsal_slice
    assert k2b.parts[1].current_seeds() == cand.parts[1].current_seeds()
    assert k2b.parts[0].current_seeds() == MultiWorldVecEnv(b, num_worlds=4, meta_seed=3).current_seeds()


def _roll(v, steps, seed=7):
    rng = np.random.default_rng(seed)
    v.reset()
    out = []
    for _ in range(steps):
        a = rng.uniform(-3, 3, (v.num_envs, 4)).astype(np.float32)
        o, r, d, info = v.step(a)
        out.append((o.copy(), r.copy(), d.copy(), [sorted(i) for i in info]))
    return out


def test_determinism_and_reset_offsets(cfgs):
    """같은 시드·행동이면 같은 궤적이다. 짧은 reset_interval 로 묶음 1 의 truncation 이 제 슬롯에 실린다."""
    g, b = cfgs
    r1 = _roll(build_mixed(g, b, seed=1, reset_interval=8), 12)
    r2 = _roll(build_mixed(g, b, seed=1, reset_interval=8), 12)
    for (o1, w1, d1, i1), (o2, w2, d2, i2) in zip(r1, r2):
        np.testing.assert_array_equal(o1, o2)
        np.testing.assert_array_equal(w1, w2)
        np.testing.assert_array_equal(d1, d2)
        assert i1 == i2
    # 엇갈림 8/4 = 2스텝. 묶음마다 세계 3(나이 6)이 2스텝 뒤 먼저 끊긴다: 슬롯 384~511, 896~1023
    o, r, d, info = r1[1]
    assert d[384:512].all() and d[896:1024].all() and not d[:384].all()
    trunc = [k for k, i in enumerate(info) if "TimeLimit.truncated" in i]
    assert trunc and set(trunc) <= set(range(384, 512)) | set(range(896, 1024))
    assert any(k >= 512 for k in trunc)


def test_rejects_mismatched_parts(cfgs):
    from env.config import ROOT
    from env_v2.config import load_v2_config
    from season.mixed_vec_env import MixedVecEnv

    g, b = cfgs
    v21 = load_v2_config(ROOT / "configs" / "v2_1.yaml")      # speed 를 켠 세계: 행동 5개
    with pytest.raises(ValueError):
        MixedVecEnv([MultiWorldVecEnv(g, num_worlds=1), MultiWorldVecEnv(v21, num_worlds=1)], ["G", "B"])
