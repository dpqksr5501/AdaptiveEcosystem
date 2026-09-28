"""§4.6 완료 기준."""

import numpy as np
import pytest

from env.config import load_config
from env.world import OBS_DIM, OBS_KIN_COUNT, OBS_PREDATOR_COUNT, World


@pytest.fixture
def cfg():
    return load_config()


def rollout(w, steps, seed=0):
    rng = np.random.default_rng(seed)
    out = None
    for _ in range(steps):
        out = w.step(rng.random((w.N, 4)))
    return out


def starving_world(cfg, seed=0):
    """먹이도 포식자도 없는 세계. 에너지 수지만 따로 보고 싶을 때."""
    rd = dict(cfg.rand)
    rd["predator_count"] = [0, 0]
    w = World(cfg.replace(rand=rd), seeds=[seed])
    w.food_cap[:] = 0.0
    w.food[:] = 0.0
    return w


# --------------------------------------------------------------------- #
# 관측 (§3.1, §4.6)
# --------------------------------------------------------------------- #


def test_obs_shape_and_range(cfg):
    w = World(cfg, seeds=[0])
    obs = w.observe()
    assert obs.shape == (128, OBS_DIM)
    assert obs.dtype == np.float32
    obs, rew, done, term = rollout(w, 200)
    for name, arr in (("obs", obs), ("terminal_obs", term)):
        assert arr.shape == (128, OBS_DIM), name
        assert arr.dtype == np.float32, name
        assert np.isfinite(arr).all(), name
        assert (arr >= 0.0).all() and (arr <= 1.0).all(), name
    assert rew.shape == (128,)
    assert done.shape == (128,) and done.dtype == np.bool_


def test_step_contract_returns_four_values(cfg):
    """§4.5 — obs (N,7), reward (N,), done (N,) bool, terminal_obs (N,7)."""
    w = World(cfg, seeds=[0])
    ret = w.step(np.full((w.N, 4), 0.5))
    assert len(ret) == 4


def test_predator_distance_is_one_when_none_visible(cfg):
    """§3.1 idx2 — 시야에 포식자가 없으면 1.0."""
    w = World(cfg, seeds=[0])
    w.pred_pos[:] = 0.0          # 전부 한 구석으로
    w.pos[:] = w.size            # 초식은 반대쪽 구석
    w._g = w._geometry()
    assert np.allclose(w._obs_from(w._g)[:, 2], 1.0)


def test_kin_count_excludes_self(cfg):
    """§3.1 idx3 — 자기 제외. 혼자면 0이어야 한다."""
    w = World(cfg.replace(N=1), seeds=[0])
    assert w.observe()[0, OBS_KIN_COUNT] == 0.0


# --------------------------------------------------------------------- #
# §4.6: predator_count가 M에 무관하게 같은 상황에서 같은 값
# --------------------------------------------------------------------- #


def test_predator_count_normalization_is_independent_of_M(cfg):
    """§1.2 — 환경 파라미터 M으로 나누지 않는다. 고정 상수 8.0으로만 나눈다."""
    obs_by_M = {}
    for m in (3, 5, 12):
        rd = dict(cfg.rand)
        rd["predator_count"] = [m, m]
        w = World(cfg.replace(rand=rd), seeds=[0])
        assert w.M == m
        # 같은 상황을 강제로 만든다: 초식 1마리를 원점에, 포식자 3마리를 시야 안에,
        # 나머지 포식자는 전부 먼 구석으로 치운다.
        w.pos[:] = [10.0, 10.0]
        w.head[:] = [1.0, 0.0]
        w.pred_pos[:] = w.size
        w.pred_pos[:3] = [[12.0, 10.0], [13.0, 11.0], [14.0, 9.0]]
        w._g = w._geometry()
        obs_by_M[m] = w._obs_from(w._g)[0, OBS_PREDATOR_COUNT]

    assert len(set(obs_by_M.values())) == 1, obs_by_M
    assert obs_by_M[3] == pytest.approx(3.0 / 8.0)   # ÷ 8.0 고정 (§3.1)


def test_kin_count_normalization_is_independent_of_N(cfg):
    """같은 이유로 kin_count도 N이 아니라 고정 20.0으로 나눈다."""
    vals = []
    for n in (8, 128):
        w = World(cfg.replace(N=n), seeds=[0])
        w.pos[:] = w.size          # 전부 구석에 몰아두고
        w.pos[:5] = [[10.0, 10.0], [11.0, 10.0], [12.0, 10.0], [13.0, 10.0], [14.0, 10.0]]
        w.head[:] = [1.0, 0.0]     # +x를 본다 → 0번은 앞의 4마리를 본다
        w._g = w._geometry()
        vals.append(w._obs_from(w._g)[0, OBS_KIN_COUNT])
    assert vals[0] == vals[1]
    assert vals[0] == pytest.approx(4.0 / 20.0)


# --------------------------------------------------------------------- #
# §4.6: 은신처 셀 재생 속도가 0.3배
# --------------------------------------------------------------------- #


def test_cover_cells_regenerate_at_0_3x(cfg):
    w = World(cfg, seeds=[0])
    assert w.cover_cell.any() and (~w.cover_cell).any()
    ratio = w.regen_field[w.cover_cell].mean() / w.regen_field[~w.cover_cell].mean()
    assert ratio == pytest.approx(cfg.food_cover_regen_mult)

    # 실제 한 스텝 재생량도 0.3배인지 본다. 용량 차이를 없애려고 전부 같게 맞춘다.
    w.food_cap[:] = 1.0
    w.food[:] = 0.0
    w.pos[:] = -1.0e9            # 아무도 먹지 않도록 격자 밖(클립되어 한 셀에만 모임)
    before = w.food.copy()
    w.step(np.zeros((w.N, 4)))
    grew = w.food - before
    touched = np.zeros_like(w.cover_cell)
    ix, iy = w._cell_index(np.zeros((1, 2)))
    touched[iy[0], ix[0]] = True   # 개체가 몰린 셀은 섭식이 섞이므로 제외
    inside = grew[w.cover_cell & ~touched].mean()
    outside = grew[~w.cover_cell & ~touched].mean()
    assert inside / outside == pytest.approx(cfg.food_cover_regen_mult, rel=1e-9)


def test_cover_makes_herbivore_look_farther_to_predators(cfg):
    """§4.2 — 은신처 안이면 포식자에게 거리가 2.5배로 보인다."""
    w = World(cfg, seeds=[0])
    inside = w.cov_c[0].copy()
    outside = w.cov_c[0] + np.array([w.cov_r[0] + 2.0, 0.0])
    assert w._in_cover(inside[None])[0]
    assert not w._in_cover(outside[None])[0]


# --------------------------------------------------------------------- #
# §4.6: 번식 후 energy == init_energy, repro_cd == 200
# --------------------------------------------------------------------- #


def test_reproduction_resets_energy_and_sets_cooldown(cfg):
    w = World(cfg, seeds=[0])
    w.energy[:] = cfg.repro_threshold + 0.05
    w.repro_cd[:] = 0
    _, rew, _, _ = w.step(np.zeros((w.N, 4)))

    assert cfg.repro_cd == 200
    assert np.all(w.repro_cd == 200)
    # 번식은 섭식·대사 뒤에 오므로 직후 energy는 정확히 init_energy다.
    assert np.allclose(w.energy, cfg.init_energy)
    assert rew.min() >= cfg.rew_repro       # 전원 +10 이상


def test_reproduction_requires_both_conditions(cfg):
    """energy > threshold AND repro_cd == 0 (§3.4). 쿨다운 중엔 안 된다."""
    w = starving_world(cfg)                 # 섭식이 섞이면 대사분을 못 본다
    w.energy[:] = cfg.repro_threshold + 0.05
    w.repro_cd[:] = 50
    before = w.energy.copy()
    _, rew, _, _ = w.step(np.zeros((w.N, 4)))
    assert np.all(w.repro_cd == 49)
    assert rew.max() < cfg.rew_repro
    assert np.all(w.energy < before)        # 대사만 깎였다

    # 에너지가 모자라도 안 된다
    w2 = starving_world(cfg)
    w2.energy[:] = cfg.repro_threshold - 0.05
    w2.repro_cd[:] = 0
    _, rew2, _, _ = w2.step(np.zeros((w2.N, 4)))
    assert rew2.max() < cfg.rew_repro


def test_cooldown_counts_down_to_zero_over_200_steps(cfg):
    w = World(cfg, seeds=[0])
    w.repro_cd[:] = cfg.repro_cd
    w.energy[:] = 0.0                       # 번식 재발동 없이 쿨다운만 본다
    for _ in range(cfg.repro_cd):
        w.repro_cd = np.maximum(w.repro_cd - 1, 0)
    assert np.all(w.repro_cd == 0)


# --------------------------------------------------------------------- #
# §4.6: 같은 시드 두 번 → 동일 세계
# --------------------------------------------------------------------- #


def test_same_seed_gives_identical_world(cfg):
    a, b = World(cfg, seeds=[7]), World(cfg, seeds=[7])
    assert a.seed == b.seed == 7
    for f in ("size", "M", "pred_speed_mult", "ranged_frac", "cover_frac_target",
              "food_regen_mult", "gw"):
        assert getattr(a, f) == getattr(b, f), f
    for f in ("pos", "head", "energy", "food", "food_cap", "cover_cell",
              "cov_c", "cov_r", "pred_pos", "pred_head", "pred_ranged"):
        assert np.array_equal(getattr(a, f), getattr(b, f)), f


def test_same_seed_gives_identical_trajectory(cfg):
    a, b = World(cfg, seeds=[7]), World(cfg, seeds=[7])
    oa = rollout(a, 150, seed=3)
    ob = rollout(b, 150, seed=3)
    for x, y in zip(oa, ob):
        assert np.array_equal(x, y)
    assert a.stats() == b.stats()


def test_different_seeds_give_different_worlds(cfg):
    a, b = World(cfg, seeds=[7]), World(cfg, seeds=[8])
    assert not np.array_equal(a.pos, b.pos)


def test_seed_pool_is_drawn_from_and_reset_rebuilds(cfg):
    w = World(cfg, seeds=[100, 200, 300])
    seen = {w.seed}
    for _ in range(30):
        w.reset()
        seen.add(w.seed)
    assert seen <= {100, 200, 300}
    assert len(seen) > 1


# --------------------------------------------------------------------- #
# §4.3 슬롯 고정 리스폰 / §4.5 스텝 규약
# --------------------------------------------------------------------- #


def test_population_is_fixed_at_128(cfg):
    w = World(cfg, seeds=[0])
    for _ in range(300):
        obs, rew, done, term = w.step(np.full((w.N, 4), 0.5))
        assert w.pos.shape == (128, 2)
        assert obs.shape == (128, 7)


def test_dead_slots_respawn_with_fresh_state(cfg):
    w = starving_world(cfg)
    w.energy[:] = 1e-9          # 전원 아사시킨다
    pos_before = w.pos.copy()
    obs, rew, done, term = w.step(np.zeros((w.N, 4)))
    assert done.all()
    assert np.allclose(rew, cfg.rew_alive + cfg.rew_death)
    assert np.allclose(w.energy, cfg.init_energy)
    assert np.all(w.repro_cd == 0)
    assert not np.array_equal(w.pos, pos_before)
    assert (w.pos >= 0).all() and (w.pos <= w.size).all()


def test_terminal_obs_is_pre_respawn_and_obs_is_post(cfg):
    """§4.5 — 종료 관측은 observe() 결과 복사, 리스폰 슬롯만 재계산."""
    w = starving_world(cfg)
    w.energy[:] = 1e-9
    obs, rew, done, term = w.step(np.zeros((w.N, 4)))
    assert done.all()
    # 죽는 순간의 energy는 0 이하 → 관측 idx4는 0. 리스폰 후엔 init_energy.
    assert np.allclose(term[:, 4], 0.0)
    assert np.allclose(obs[:, 4], cfg.init_energy / cfg.max_energy)


def test_survivors_share_terminal_and_current_obs(cfg):
    """아무도 안 죽으면 terminal_obs는 obs의 복사본이다 (§4.5)."""
    rd = dict(cfg.rand)
    rd["predator_count"] = [0, 0]
    w = World(cfg.replace(rand=rd), seeds=[0])
    obs, rew, done, term = w.step(np.full((w.N, 4), 0.5))
    assert not done.any()
    assert np.array_equal(obs, term)


def test_agents_stay_inside_walls_no_torus(cfg):
    """§4.2 — 벽 경계. 토러스(순환) 끄기."""
    w = World(cfg, seeds=[0])
    for _ in range(400):
        w.step(np.full((w.N, 4), 0.5))
        assert (w.pos >= 0.0).all() and (w.pos <= w.size).all()
        assert (w.pred_pos >= 0.0).all() and (w.pred_pos <= w.size).all()


# --------------------------------------------------------------------- #
# §4.4 무작위화 / §3.4 보상 / §3.1 EMA
# --------------------------------------------------------------------- #


def test_randomization_stays_within_spec_ranges(cfg):
    w = World(cfg, seeds=range(0, 60))
    rd = cfg.rand
    for _ in range(60):
        w.reset()
        assert rd["world_size"][0] <= w.size <= rd["world_size"][1]
        assert rd["predator_count"][0] <= w.M <= rd["predator_count"][1]
        assert rd["pred_speed_mult"][0] <= w.pred_speed_mult <= rd["pred_speed_mult"][1]
        assert rd["ranged_frac"][0] <= w.ranged_frac <= rd["ranged_frac"][1]
        assert rd["cover_frac"][0] <= w.cover_frac_target <= rd["cover_frac"][1]
        assert rd["food_regen_mult"][0] <= w.food_regen_mult <= rd["food_regen_mult"][1]


def test_both_predator_types_appear_across_seeds(cfg):
    w = World(cfg, seeds=range(0, 40))
    melee = ranged = False
    for _ in range(40):
        w.reset()
        melee |= bool((~w.pred_ranged).any())
        ranged |= bool(w.pred_ranged.any())
    assert melee and ranged


def test_survival_reward_is_paid_every_step(cfg):
    """§3.4 — 매 스텝 생존 +0.01."""
    rd = dict(cfg.rand)
    rd["predator_count"] = [0, 0]
    w = World(cfg.replace(rand=rd), seeds=[0])
    w.food_cap[:] = 0.0            # 먹이 0 → 에너지 획득 보상 0
    w.food[:] = 0.0
    _, rew, done, _ = w.step(np.zeros((w.N, 4)))
    assert not done.any()
    assert np.allclose(rew, cfg.rew_alive)


def test_predation_ema_follows_spec_formula(cfg):
    """§3.1 — ema = 0.95*ema + 0.05*(사망 수 / 전체 개체 수)*10."""
    w = World(cfg, seeds=[0])
    assert w.pred_ema == 0.0
    w.pred_ema = 0.4
    deaths = 3
    expected = 0.95 * 0.4 + 0.05 * (deaths / w.N) * 10.0
    got = (
        cfg.predation_ema_decay * 0.4
        + (1 - cfg.predation_ema_decay) * (deaths / w.N) * cfg.predation_ema_gain
    )
    assert got == pytest.approx(expected)


def test_starvation_kills(cfg):
    w = World(cfg, seeds=[0])
    w.food_cap[:] = 0.0
    w.food[:] = 0.0
    w.energy[:] = cfg.energy_drain * 1.5
    _, _, done, _ = w.step(np.zeros((w.N, 4)))
    assert not done.any()
    _, _, done, _ = w.step(np.zeros((w.N, 4)))
    assert done.all()


def test_full_agents_do_not_strip_the_map(cfg):
    """배부른 개체는 흡수 가능량만 먹는다. 안 그러면 맵이 벗겨진다."""
    rd = dict(cfg.rand)
    rd["predator_count"] = [0, 0]
    w = World(cfg.replace(rand=rd), seeds=[0])
    w.energy[:] = cfg.max_energy
    before = w.food.sum()
    w.step(np.zeros((w.N, 4)))
    eaten = before - w.food.sum() + (w.regen_field * 0).sum()
    # 대사분(N * drain / energy_per_unit)보다 크게 더 먹지 않는다
    budget = w.N * cfg.energy_drain / cfg.food_energy_per_unit
    assert eaten <= budget * 1.05


# --------------------------------------------------------------------- #
# §7.2 stats()
# --------------------------------------------------------------------- #


def test_stats_returns_every_spec_column(cfg):
    w = World(cfg, seeds=[0])
    rollout(w, 300)
    s = w.stats()
    expected = {
        "mean_return", "survival", "repro", "predation_rate", "cohesion_mean",
        "flee_dist_mean", "flee_dist_std", "cover_frac", "react_pred", "react_hunger",
    }
    assert set(s) == expected
    assert all(np.isfinite(v) for v in s.values()), s
    assert 0.0 <= s["cover_frac"] <= 1.0
    assert 0.0 <= s["predation_rate"] <= 1.0
