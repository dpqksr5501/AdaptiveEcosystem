"""V2 진단 도구(0-3)의 단위 테스트. 계획서 6.1·6.3.

전체 롤아웃은 넣지 않는다. 숫자를 손으로 셀 수 있는 작은 예와 짧은 World 몇 스텝만 쓴다.
"""

import math

import numpy as np
import pytest

import diagnose_v2 as dg
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.world import World
from policies.registry import make_policy


# --------------------------------------------------------------------- #
# G_γ
# --------------------------------------------------------------------- #


def test_return_to_go_by_hand():
    """γ=0.5. 개체 0 은 t=1 에 죽고 t=2 에 리스폰한 새 개체의 보상 3 을 받는다."""
    rew = np.array([[1.0, 0.0],
                    [2.0, 0.0],
                    [3.0, 4.0]])
    done = np.array([[0, 0],
                     [1, 0],
                     [0, 0]], dtype=bool)
    G = ro.discounted_return_to_go(rew, done, 0.5)
    # 개체 0: G2=3 (새 개체), G1=2 (사망 스텝 — 뒤를 안 본다), G0=1+0.5·2=2
    # 개체 1: G2=4, G1=0+0.5·4=2, G0=0+0.5·2=1
    np.testing.assert_allclose(G, [[2.0, 1.0], [2.0, 2.0], [3.0, 4.0]])
    assert ro.g_gamma(rew, done, 0.5, tail=0) == pytest.approx(G.mean())
    assert ro.g_gamma(rew, done, 0.5, tail=1) == pytest.approx(G[:2].mean())
    assert math.isnan(ro.g_gamma(rew, done, 0.5, tail=3))      # 뺄 꼬리가 롤아웃보다 길다


def test_death_penalty_counts_but_respawn_does_not():
    rew = np.array([[0.0], [-10.0], [5.0], [5.0]])
    done = np.array([[0], [1], [0], [0]], dtype=bool)
    G = ro.discounted_return_to_go(rew, done, 0.9)
    assert G[1, 0] == pytest.approx(-10.0)
    assert G[0, 0] == pytest.approx(0.9 * -10.0)
    assert G[2, 0] == pytest.approx(5.0 + 0.9 * 5.0)


def test_tail_is_ceil_five_horizons():
    assert ro.tail_steps(0.9916661555611042) == 600
    assert ro.tail_steps(0.99) == 500
    assert ro.load_gamma() == pytest.approx(0.9916661555611042)


# --------------------------------------------------------------------- #
# 정책 래퍼
# --------------------------------------------------------------------- #


def _ident_policy(obs):
    """행동 = 관측 앞 4열. 관측이 어떻게 바뀌었는지 행동으로 볼 수 있다."""
    return np.asarray(obs[:, :4], dtype=np.float64)


def test_act_permute_keeps_distribution_and_breaks_mapping():
    rng = np.random.default_rng(0)
    obs = rng.random((128, 7)).astype(np.float32)
    a0 = _ident_policy(obs)
    w = ro.ActPermute(_ident_policy, seed=10000)
    a1 = w(obs)
    np.testing.assert_allclose(a1.sum(0), a0.sum(0))                     # 스텝 합(분포) 보존
    assert sorted(map(tuple, a1)) == sorted(map(tuple, a0))               # 행동 벡터 집합 보존
    assert (a1 != a0).any(axis=1).mean() > 0.9                            # 개체 대응은 바뀐다
    # 결정적: 같은 시드면 같은 순열, 다른 시드면 다른 순열
    np.testing.assert_array_equal(ro.ActPermute(_ident_policy, seed=10000)(obs), a1)
    assert not np.array_equal(ro.ActPermute(_ident_policy, seed=10001)(obs), a1)


def test_obs_fix_changes_only_that_column():
    obs = np.random.default_rng(1).random((64, 7)).astype(np.float32)
    orig = obs.copy()
    seen = {}

    def spy(o):
        seen["o"] = o.copy()
        return _ident_policy(o)

    ro.ObsFix(spy, dims=[2], values=[0.25])(obs)
    np.testing.assert_array_equal(obs, orig)                              # 원본은 그대로
    assert np.all(seen["o"][:, 2] == np.float32(0.25))
    np.testing.assert_array_equal(np.delete(seen["o"], 2, 1), np.delete(orig, 2, 1))


def test_obs_permute_shuffles_one_column_among_agents():
    obs = np.random.default_rng(2).random((128, 7)).astype(np.float32)
    seen = {}

    def spy(o):
        seen["o"] = o.copy()
        return _ident_policy(o)

    ro.ObsPermute(spy, dims=[4], seed=3)(obs)
    o = seen["o"]
    np.testing.assert_array_equal(np.sort(o[:, 4]), np.sort(obs[:, 4]))   # 값 집합 보존
    assert (o[:, 4] != obs[:, 4]).mean() > 0.9
    np.testing.assert_array_equal(np.delete(o, 4, 1), np.delete(obs, 4, 1))


def test_act_fix_sets_only_given_dims():
    obs = np.random.default_rng(3).random((10, 7)).astype(np.float32)
    a = ro.ActFix(_ident_policy, dims=[1], values=[0.1, 0.2, 0.3, 0.4])(obs)
    assert np.all(a[:, 1] == 0.2)
    np.testing.assert_allclose(a[:, [0, 2, 3]], _ident_policy(obs)[:, [0, 2, 3]])


def test_segment_ids_mixed_radix_and_seg_const():
    obs = np.zeros((4, 7), dtype=np.float32)
    obs[:, 2] = [0.1, 0.1, 0.9, 0.9]          # pred_dist
    obs[:, 4] = [0.2, 0.8, 0.2, 0.8]          # energy
    bins = [[2, [0.5]], [4, [0.5]]]
    assert ro.n_segments(bins) == 4 and ro.n_segments([]) == 1
    np.testing.assert_array_equal(ro.segment_ids(obs, bins), [0, 1, 2, 3])
    base = make_policy({"kind": "fixed", "action": [0.5, 0.6, 0.7, 0.8]})
    table = [[0.0], [0.1], [0.2], [0.3]]       # 구간마다 forage 만 다르다
    a = ro.SegConst(base, bins, dims=[0], table=table)(obs)
    np.testing.assert_allclose(a[:, 0], [0.0, 0.1, 0.2, 0.3])
    np.testing.assert_allclose(a[:, 1:], np.tile([0.6, 0.7, 0.8], (4, 1)))
    assert dg.seg_labels(bins) == ["pred_dist<0.5 & energy<0.5", "pred_dist<0.5 & energy≥0.5",
                                   "pred_dist≥0.5 & energy<0.5", "pred_dist≥0.5 & energy≥0.5"]


def test_build_policy_composes_wrappers_from_spec():
    spec = dg.wrap({"kind": "fixed", "action": [0.1, 0.2, 0.3, 0.4]},
                   {"kind": "act_fix", "dims": [3], "values": [0, 0, 0, 0.9]})
    a = ro.build_policy(spec, seed=0)(np.zeros((5, 7), np.float32))
    np.testing.assert_allclose(a, np.tile([0.1, 0.2, 0.3, 0.9], (5, 1)))
    specs = dg.control_specs({"kind": "utility"}, [0.3, 0.8, 0.4, 0.1])
    assert list(specs) == ["C0", "C1", "C3-forage", "C3-cohesion", "C3-flee_dist", "C3-cover", "C1'"]
    assert specs["C1"] == {"kind": "fixed", "action": [0.3, 0.8, 0.4, 0.1]}
    c4, notes = dg.obs_control_specs({"kind": "utility"}, np.arange(7) / 10, [2, 5], ["fix", "perm"])
    assert set(c4) == {"C4-pred_dist-fix", "C4-pred_dist-perm", "C4-recent_predation-fix"}
    assert notes                                                           # 전역 관측 5 순열은 뺀다


def test_short_rollout_matches_plain_world_loop():
    """래퍼 없이 돌린 v2 롤아웃은 World 를 직접 돌린 것과 같은 통계를 낸다. 보상 기록이 G_γ 로 이어진다."""
    cfg = load_v2_config()
    spec = {"kind": "fixed", "action": [0.3, 0.8, 0.4, 0.1]}
    r = ro.rollout(cfg, ro.build_policy(spec, 0), seed=10000, steps=30, tail=0, record_every=10)
    w = World(cfg, seeds=[10000])
    pol = make_policy(spec)
    rew, done = [], []
    for _ in range(30):
        _, rr, dd, _ = w.step(pol(w.observe()))
        rew.append(rr)
        done.append(dd)
    s = w.stats()
    for c in ro.STAT_COLUMNS:
        assert r[c] == s[c] or (math.isnan(r[c]) and math.isnan(s[c])), c
    assert r["g_gamma"] == pytest.approx(ro.g_gamma(np.array(rew), np.array(done), ro.load_gamma(), 0))
    assert r["_obs"].shape == (3 * 128, 7) and r["_act"].shape == (3 * 128, 4)
    assert r["_act_n"] == 30 * 128


# --------------------------------------------------------------------- #
# 통계
# --------------------------------------------------------------------- #


def test_iqm_by_hand_and_matches_trim_mean():
    assert dg.iqm(np.arange(1, 9)) == pytest.approx(4.5)                # 3,4,5,6 의 평균
    assert dg.iqm([5.0]) == 5.0
    x = np.random.default_rng(0).normal(size=37)
    scipy_stats = pytest.importorskip("scipy.stats")
    assert dg.iqm(x) == pytest.approx(scipy_stats.trim_mean(x, 0.25))


def test_stratified_bootstrap_resamples_within_strata():
    # 층(열)마다 값이 상수면, 층 안 복원추출로는 IQM 이 절대 바뀌지 않는다. 층을 섞으면 바뀐다.
    S = np.tile(np.array([0.0, 10.0, 20.0, 30.0]), (5, 1))               # (학습 시드 5, 층 4)
    ci = dg.stratified_bootstrap_ci(S, reps=200, seed=1)
    assert ci["lo"] == ci["hi"] == ci["point"] == pytest.approx(dg.iqm(S))
    # 무작위 자료: CI 가 점추정을 감싸고, 시드가 같으면 같은 CI
    R = np.random.default_rng(4).normal(size=(6, 20))
    c1 = dg.stratified_bootstrap_ci(R, reps=300, seed=2)
    c2 = dg.stratified_bootstrap_ci(R, reps=300, seed=2)
    assert c1 == c2 and c1["lo"] <= c1["point"] <= c1["hi"] and c1["lo"] < c1["hi"]
    # 학습 시드 하나면 폭 0
    one = dg.stratified_bootstrap_ci(R[:1], reps=50)
    assert one["lo"] == one["hi"]


def test_aggregate_over_training_seeds():
    """학습 시드 3개(디렉터리) × 평가 시드 4개. C1′ 는 어디서나 C0 보다 정확히 1 낮다."""
    def ablate(offset):
        rows = lambda shift: [{"seed": s, **{c: float(s + offset + shift) for c in dg.OUTCOME}}
                              for s in range(4)]
        return {"per_seed": {"C0": rows(0.0), "C1'": rows(-1.0)}}

    agg = dg.aggregate([ablate(0.0), ablate(10.0), ablate(20.0)], reps=200)
    d = agg["C1'"]["g_gamma"]["diff_vs_C0"]
    assert d["point"] == d["lo"] == d["hi"] == pytest.approx(-1.0)
    assert agg["C0"]["g_gamma"]["iqm"]["runs"] == 3 and agg["C0"]["g_gamma"]["iqm"]["strata"] == 4
    with pytest.raises(SystemExit):                                      # 평가 시드가 다르면 묶지 않는다
        bad = ablate(0.0)
        bad["per_seed"]["C0"][0]["seed"] = 99
        dg.aggregate([ablate(0.0), bad], reps=10)


def test_paired_uses_evaluate_t():
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([0.5, 1.0, 2.5, 3.0])
    p = dg.paired(a, b)
    d = a - b
    assert p["diff"] == pytest.approx(d.mean())
    assert p["t"] == pytest.approx(d.mean() / (d.std(ddof=1) / 2))
    assert p["sig"] == (abs(p["t"]) > 2.093)


def test_linear_r2_exact_linear_is_one():
    rng = np.random.default_rng(5)
    obs = rng.random((500, 7))
    act = np.c_[obs @ rng.normal(size=7) + 0.3, 2 * obs[:, 0] - obs[:, 6],
                rng.random(500), np.full(500, 0.4)]
    r2 = dg.linear_r2(obs, act)
    assert r2[0] == pytest.approx(1.0) and r2[1] == pytest.approx(1.0)
    assert r2[2] < 0.1                                                    # 잡음은 설명 못 한다
    assert math.isnan(r2[3])                                              # 상수 행동은 정의 안 됨


def test_calib_mean_matches_running_sum():
    # 시드마다 행동 차원 k 의 값이 (k+1)·{0, 0, 1, 1} → 평균 (k+1)/2, 표준편차 (k+1)/2
    row = {"_act_sum": np.array([2.0, 4, 6, 8]), "_act_sq": np.array([2.0, 8, 18, 32]),
           "_act_n": 4, "_obs_sum": np.arange(7.0) * 4}
    cal = dg.calib_from_rows([{"seed": 1, **row}, {"seed": 0, **row}])
    np.testing.assert_allclose(cal["mean_action"], [0.5, 1.0, 1.5, 2.0])
    np.testing.assert_allclose(cal["std_action"], [0.5, 1.0, 1.5, 2.0])
    np.testing.assert_allclose(cal["obs_mean"], np.arange(7.0))


def test_response_curves():
    rng = np.random.default_rng(6)
    obs = rng.random((4000, 7)).astype(np.float32)
    obs[:1500, 2] = 1.0                                                   # 포식자 안 보임 몰림
    act = np.c_[obs[:, 2], 1 - obs[:, 2], np.zeros(4000), np.zeros(4000)]
    cur = dg.conditional_curve(obs[:, 2], act)
    assert cur[-1]["lo"] == cur[-1]["hi"] == 1.0 and cur[-1]["n"] == 1500  # 몰린 점은 따로 둔다
    means = [b["act"][0] for b in cur]
    assert means == sorted(means)                                         # 행동 = 관측이면 증가
    assert sum(b["n"] for b in cur) == 4000
    pd = dg.intervention_curve(_ident_policy, obs, 2, [0.0, 0.5, 1.0])
    assert [p["act"][2] for p in pd] == pytest.approx([0.0, 0.5, 1.0])
    assert pd[0]["act"][0] == pytest.approx(obs[:, 0].mean())             # 다른 열은 그대로


def test_clean_writes_nan_as_null():
    out = dg.clean({"a": np.float64("nan"), "b": np.arange(2), "c": (np.bool_(True), 1.5)})
    assert out == {"a": None, "b": [0, 1], "c": [True, 1.5]}


def test_seed_overlap_is_refused():
    import argparse
    from diagnose_v2 import check_disjoint
    ok = argparse.Namespace(allow_seed_overlap=False)
    check_disjoint("보정 시드", range(0, 20), range(10000, 10020), ok)          # 겹치지 않으면 통과
    with pytest.raises(SystemExit):
        check_disjoint("탐색 시드", [3, 10005], range(10000, 10020), ok)
    check_disjoint("탐색 시드", [10005], range(10000, 10020), argparse.Namespace(allow_seed_overlap=True))


def test_model_fingerprint_changes_with_content(tmp_path):
    from diagnose_v2 import model_fingerprint
    p = tmp_path / "m.zip"
    p.write_bytes(b"a")
    first = model_fingerprint(p)
    p.write_bytes(b"b")
    assert model_fingerprint(p) != first
    assert model_fingerprint(tmp_path / "none.zip") is None
