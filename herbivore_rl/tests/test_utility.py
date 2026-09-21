"""§5.1 Utility AI 와 §5.2 튜닝 산출물 검증."""

import numpy as np
import pytest

from env.config import load_config
from env.rollout import STAT_COLUMNS, rollout, run_policy, std_of
from policies.registry import make_policy
from policies.utility import SEARCH_SPACE, UTILITY_PARAMS, utility_policy


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def obs():
    """관측 공간 전체를 덮는 표본. 전부 [0,1] (§3.1)."""
    return np.random.default_rng(0).random((256, 7)).astype(np.float32)


# --------------------------------------------------------------------- #
# §5.1 수식
# --------------------------------------------------------------------- #


def test_output_shape_and_range(obs):
    a = utility_policy(obs)
    assert a.shape == (len(obs), 4)
    assert (a >= 0.0).all() and (a <= 1.0).all()
    assert np.isfinite(a).all()


def test_no_sigmoid_is_applied(obs):
    """§1.3 — sigmoid는 학습 정책의 (-3,3) 출력에만 붙는다. 여기 있으면 안 된다."""
    p = dict(UTILITY_PARAMS, k_forage=1.0)
    a = utility_policy(obs, p)
    energy = obs[:, 4]
    assert np.allclose(a[:, 0], np.clip(1.0 - energy, 0, 1), atol=1e-6)
    # sigmoid를 거쳤다면 0.5 근처로 눌렸을 것이다
    assert a[:, 0].min() < 0.1 and a[:, 0].max() > 0.9


def test_matches_literal_spec_formula(obs):
    """§5.1을 그대로 다시 써서 대조."""
    p = dict(k_forage=1.3, k_coh=17.0, flee_base=0.3, flee_k=0.6, k_cover=2.2)
    food, pc, pd, kin, energy, rp, cd = obs.T
    ref = np.stack(
        [
            np.clip(p["k_forage"] * (1.0 - energy), 0, 1),
            np.clip(p["k_coh"] * rp, 0, 1),
            np.clip(p["flee_base"] + p["flee_k"] * rp, 0, 1),
            np.clip(p["k_cover"] * pc, 0, 1),
        ],
        1,
    )
    assert np.allclose(utility_policy(obs, p), ref, atol=1e-12)


def test_each_action_depends_only_on_its_own_observation(obs):
    """§5.1은 forage←energy, cohesion←rp, flee←rp, cover←predator_count 만 쓴다.
    항이 늘면 §0의 '같은 조건' 비교가 깨진다."""
    deps = {0: [4], 1: [5], 2: [5], 3: [1]}
    base = utility_policy(obs)
    for col in range(7):
        bumped = obs.copy()
        bumped[:, col] = np.clip(bumped[:, col] + 0.3, 0, 1)
        out = utility_policy(bumped)
        for act in range(4):
            changed = not np.allclose(out[:, act], base[:, act])
            should = col in deps[act]
            if changed and not should:
                pytest.fail(f"행동 {act} 가 관측 {col} 에 반응한다 (§5.1에 없는 의존)")


def test_hungrier_forages_more():
    p = dict(UTILITY_PARAMS)
    o = np.zeros((2, 7), dtype=np.float32)
    o[:, 4] = [0.1, 0.9]                       # energy
    a = utility_policy(o, p)
    assert a[0, 0] > a[1, 0]


def test_more_predators_seeks_cover_more():
    p = dict(UTILITY_PARAMS)
    o = np.zeros((2, 7), dtype=np.float32)
    o[:, 1] = [0.0, 0.5]                       # predator_count
    a = utility_policy(o, p)
    assert a[1, 3] > a[0, 3]


def test_higher_predation_raises_cohesion_and_flee():
    p = dict(UTILITY_PARAMS)
    o = np.zeros((2, 7), dtype=np.float32)
    o[:, 5] = [0.0, 0.08]                      # recent_predation 실측 상한 근처
    a = utility_policy(o, p)
    assert a[1, 1] > a[0, 1]
    assert a[1, 2] > a[0, 2]


def test_search_space_covers_the_useful_cohesion_range():
    """§3.1 EMA 실측 범위가 0~0.078이라 k_coh 상한이 4면 cohesion이 0.31을 못 넘는다.
    그래서 §5.2 범위를 0~40으로 정정했다. 되돌아가면 여기서 걸린다."""
    rp_max = 0.078
    assert SEARCH_SPACE["k_coh"][1] * rp_max >= 1.0, (
        "k_coh 상한이 너무 낮다. cohesion이 1.0에 도달할 수 없다."
    )


# --------------------------------------------------------------------- #
# 레지스트리 (§7.1 평가와 §5.2 튜닝이 공유한다)
# --------------------------------------------------------------------- #


def test_registry_policies_return_unit_range_actions(cfg, obs):
    for spec in (
        {"kind": "random", "seed": 0},
        {"kind": "fixed", "action": [0.1, 0.2, 0.3, 0.4]},
        {"kind": "utility", "params": "default"},
        {"kind": "utility", "params": dict(UTILITY_PARAMS)},
    ):
        a = make_policy(spec)(obs)
        assert a.shape == (len(obs), 4), spec
        assert (a >= 0.0).all() and (a <= 1.0).all(), spec


def test_registry_rejects_unknown_kind():
    with pytest.raises(ValueError):
        make_policy({"kind": "nope"})


def test_fixed_policy_gives_every_agent_the_same_action(obs):
    a = make_policy({"kind": "fixed", "action": [0.1, 0.2, 0.3, 0.4]})(obs)
    assert np.allclose(a, [0.1, 0.2, 0.3, 0.4])


# --------------------------------------------------------------------- #
# 롤아웃 하네스
# --------------------------------------------------------------------- #


def test_rollout_returns_every_stat_column(cfg):
    s = rollout(cfg, make_policy({"kind": "utility", "params": "default"}), 0, 200)
    assert set(s) == set(STAT_COLUMNS) | {"seed"}
    assert s["seed"] == 0


def test_rollout_is_deterministic_for_a_seed(cfg):
    spec = {"kind": "utility", "params": "default"}
    a = rollout(cfg, make_policy(spec), 3, 200)
    b = rollout(cfg, make_policy(spec), 3, 200)
    assert a == b


def test_run_policy_serial_and_parallel_agree(cfg):
    """워커 프로세스를 거쳐도 결과가 같아야 한다. §0의 동일 조건 비교가 여기 달려 있다."""
    spec = {"kind": "utility", "params": "default"}
    seeds = [0, 1, 2, 3]
    rows_s, mean_s = run_policy(cfg, spec, seeds, 150, workers=1)
    rows_p, mean_p = run_policy(cfg, spec, seeds, 150, workers=4)
    assert rows_s == rows_p
    assert mean_s == mean_p


def test_run_policy_aggregates_over_the_given_seeds(cfg):
    rows, mean = run_policy(cfg, {"kind": "random", "seed": 0}, [5, 6, 7], 150, workers=1)
    assert [r["seed"] for r in rows] == [5, 6, 7]
    assert mean["mean_return"] == pytest.approx(
        np.mean([r["mean_return"] for r in rows])
    )
    assert std_of(rows)["mean_return"] >= 0.0


# --------------------------------------------------------------------- #
# §5.3 완료 기준 — 튜닝 산출물이 있어야 돈다
# --------------------------------------------------------------------- #

import yaml  # noqa: E402
from policies.utility import BEST_PATH, load_best_params  # noqa: E402

needs_tuning = pytest.mark.skipif(
    not BEST_PATH.exists(), reason="configs/utility_best.yaml 없음. tune_utility.py 먼저."
)


@needs_tuning
def test_best_yaml_records_its_own_conditions():
    """§12 '헤더를 손으로 적지 말 것' — 재현 조건이 산출물 안에 있어야 한다."""
    doc = yaml.safe_load(BEST_PATH.read_text(encoding="utf-8"))
    assert set(doc["params"]) == set(SEARCH_SPACE)
    c = doc["conditions"]
    assert len(c["seeds"]) == 20
    assert c["steps"] == 3000
    assert c["trials"] >= 300
    lo, hi = c["seed_pool"]
    assert all(lo <= s < hi for s in c["seeds"]), "§3.5 — 평가 시드로 튜닝하면 안 된다"


@needs_tuning
def test_tuned_params_are_inside_the_search_space():
    p = load_best_params()
    for k, (lo, hi) in SEARCH_SPACE.items():
        assert lo <= p[k] <= hi, k


@needs_tuning
def test_tuned_beats_random_by_2x(cfg):
    """§5.3 — 튜닝된 Utility AI가 랜덤 대비 mean_return 2배 이상."""
    doc = yaml.safe_load(BEST_PATH.read_text(encoding="utf-8"))
    o = doc["objective"]
    assert o["random_baseline"] > 0, "기준선이 음수면 '2배'가 정의되지 않는다"
    assert o["ratio_vs_random"] >= 2.0, (
        f"{o['value']:.2f} / {o['random_baseline']:.2f} = {o['ratio_vs_random']:.2f}배"
    )


@needs_tuning
def test_tuned_policy_actually_flees_from_predators(cfg):
    """§5.3 — '포식자 접근 시 도주가 보임' 을 눈이 아니라 수치로 확인한다.

    도주 분기가 켜진 개체의 속도가 포식자 반대쪽을 향하는지 본다.
    """
    from env.steering import steer
    from env.world import World

    policy = make_policy({"kind": "utility"})
    w = World(cfg, seeds=[10000])
    align_fleeing, align_calm, n_flee, n_calm = 0.0, 0.0, 0, 0

    for _ in range(1500):
        g, a = w._g, policy(w.observe())
        v = steer(g, a, cfg)
        speed = np.linalg.norm(v, axis=1)
        moving = speed > 1e-9
        # away_from_pred 와 실제 속도의 정렬도. +1이면 정확히 도망치는 방향.
        align = (v * g["away_from_pred"]).sum(1) / np.maximum(speed, 1e-9)
        fleeing = (g["d_pred_min"] < a[:, 2] * cfg.see_r) & moving
        near = np.isfinite(g["d_pred_min"]) & ~fleeing & moving
        align_fleeing += align[fleeing].sum(); n_flee += int(fleeing.sum())
        align_calm += align[near].sum(); n_calm += int(near.sum())
        w.step(a)

    assert n_flee > 500, f"도주 분기가 거의 안 켜졌다 ({n_flee}회)"
    mean_flee = align_fleeing / n_flee
    assert mean_flee > 0.5, f"도주 중인데 포식자 반대 방향 정렬이 {mean_flee:.3f}뿐"
    if n_calm > 100:
        assert mean_flee > align_calm / n_calm, "도주 분기가 방향을 바꾸지 못한다"
