"""V2 0-6 Gate F 측정 도구 (`gate_f.py`) — 자기상관 반감기, 흔적 진폭·지속, 선택 규칙, 롤아웃 기록."""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import math

import numpy as np
import pytest

import gate_f as G
from env.config import ROOT
from env_v2.config import load_v2_config


def test_pooled_half_life_recovers_ar1():
    """반감기 40표본(= 200스텝)인 AR(1) 셀들 → 같은 값. 셀마다 분산이 달라도 분산 가중 묶음이라 맞다."""
    rng = np.random.default_rng(0)
    n, cells, hl = 4000, 120, 40
    phi = 2.0 ** (-1.0 / hl)
    X = np.zeros((n, cells))
    scale = rng.uniform(0.2, 3.0, cells)
    for t in range(1, n):
        X[t] = phi * X[t - 1] + rng.normal(0.0, 1.0, cells)
    X = X * scale + rng.uniform(0, 1, cells)          # 셀별 평균·분산이 달라도
    est = G.pooled_half_life(X.astype(np.float32), every=5)
    assert abs(est - hl * 5) <= 0.1 * hl * 5


def test_pooled_half_life_none_without_variance():
    assert G.pooled_half_life(np.ones((100, 5), dtype=np.float32)) is None
    assert G.pooled_half_life(np.ones((100, 0), dtype=np.float32)) is None


def _toy(m=40, n=300):
    cap = np.linspace(0.1, 1.0, m)
    eaten = np.zeros(m)
    eaten[-4:] = [10.0, 11.0, 12.0, 13.0]                    # 상위 10% = 마지막 4셀(가장 높은 cap0 구간)
    eaten[-10:-4] = 1.0
    X = np.full((n, m), 0.9, dtype=np.float32)          # 실제 기록처럼 float32 (허용 오차 1e-5)
    X[:, -4:] = 0.5
    return cap, eaten, X


def test_trace_sets_definition():
    cap, eaten, _ = _toy()
    bin_of, top, refs = G.trace_sets(cap, eaten)
    assert sorted(top.tolist()) == [36, 37, 38, 39]
    assert (bin_of[top] == 3).all()
    assert all(r.size == 5 for r in refs)                     # 구간 10셀의 하위 절반
    assert not set(top.tolist()) & set(np.concatenate(refs).tolist())
    assert set(refs[3].tolist()) == {30, 31, 32, 33, 34}      # 마지막 구간에서 섭취가 작은 쪽 절반


def test_trace_metrics_amplitude_and_persistence():
    cap, eaten, X = _toy()
    lag = 120
    X[200, 39] = 0.75                                         # 자연 사건: 멈춘 뒤 600스텝 시점에 일부 회복
    X[200 - lag, 39] = 0.40
    ev_s = np.array([200, 200, 250])
    ev_i = np.array([39, 5, 38])                              # 셀 5 는 상위가 아니라 빠진다
    v_after = np.full(len(cap), 0.8)                          # 울타리 600스텝 뒤: 기준 셀(30~34) 0.8
    v_after[36:] = [0.6, 0.65, 0.7, 0.75]
    tm = G.trace_metrics(X, cap, eaten, ev_s, ev_i, lag, v_after=v_after)
    assert tm["n_top"] == 4 and tm["n_events"] == 2 and tm["n_event_cells"] == 2
    mean_39 = (0.5 * (len(X) - 2) + 0.75 + 0.40) / len(X)
    assert tm["amp"] == pytest.approx(0.9 - (0.5 * 3 + mean_39) / 4, abs=1e-5)
    assert tm["amp_end"] == pytest.approx(0.4, abs=1e-5)
    assert tm["persist"] == pytest.approx(0.8 - 0.675)        # 판정하는 지속 = 울타리 시험
    assert tm["persist_nat"] == pytest.approx(((0.9 - 0.75) + (0.9 - 0.5)) / 2, abs=1e-5)
    assert tm["persist_nat_d0"] == pytest.approx(((0.9 - 0.40) + (0.9 - 0.5)) / 2, abs=1e-5)
    assert tm["intake_ratio"] == pytest.approx(11.5 / 1.0)    # 기준 셀 30~34 의 섭취는 모두 1


def test_trace_metrics_without_exclosure_is_nan():
    cap, eaten, X = _toy()
    tm = G.trace_metrics(X, cap, eaten, np.empty(0, int), np.empty(0, int), 120)
    assert tm["n_events"] == 0 and math.isnan(tm["persist"]) and math.isnan(tm["persist_nat"])
    row = dict(v_cell_mean=0.6, floor_frac=0.0, acf_half_life=693, amp=0.3, persist=tm["persist"],
               starve_share=0.1)
    p = G.verdict(row, 693.0)
    assert p["a"] and p["b"] and p["d"] and not p["c"] and not p["all"]   # 지속을 못 재면 (c) 실패


def test_verdict_bounds():
    base = dict(v_cell_mean=0.6, floor_frac=0.1, acf_half_life=693, amp=0.25, persist=0.12, starve_share=0.3)
    assert G.verdict(base, 693.0)["all"]
    for k, v, crit in [("v_cell_mean", 0.95, "a"), ("floor_frac", 0.5, "a"), ("acf_half_life", 300, "b"),
                       ("acf_half_life", None, "b"), ("amp", 0.19, "c"), ("persist", 0.09, "c"),
                       ("starve_share", 0.41, "d")]:
        assert not G.verdict(dict(base, **{k: v}), 693.0)[crit], (k, v)


def test_select_rule():
    """(a)(b)(d)를 모든 칸에서 지키는 후보 중 진폭 평균 최대. 없으면 (a)(b)(d) 통과 칸 수 최대."""
    def c(abd_all, n_abd, amp):
        return {"summary": dict(abd_all=abd_all, n_abd=n_abd, amp_mean=amp)}
    assert G.select([c(False, 8, 0.3), c(True, 9, 0.1), c(True, 9, 0.15)]) == 2
    assert G.select([c(False, 6, 0.3), c(False, 8, 0.1), c(False, 8, 0.12)]) == 2
    assert G.select([{"summary": {}}]) is None


def test_exclosure_world_without_fence_is_world():
    """울타리 없는 ExclosureWorld = World (비트 단위). 울타리를 치면 그 셀만 섭취·훼손이 0 이다."""
    from env_v2.world import World
    cfg = load_v2_config(ROOT / "configs" / "v2_0b.yaml")
    pol = make_fixed()
    a, b = G.ExclosureWorld(cfg, seeds=[20001]), World(cfg, seeds=[20001])
    for _ in range(300):
        a.step(pol(a.observe()))
        b.step(pol(b.observe()))
    for k in ("food", "food_v", "pos", "energy", "_fv_eaten"):
        assert np.array_equal(getattr(a, k), getattr(b, k)), k
    grazed = np.flatnonzero(a._fv_eaten.reshape(-1) > 0)
    a.excl = grazed
    e0, v0 = a._fv_eaten.reshape(-1)[grazed].copy(), a.food_v.reshape(-1)[grazed].copy()
    for _ in range(100):
        a.step(pol(a.observe()))
    assert np.array_equal(a._fv_eaten.reshape(-1)[grazed], e0)            # 울타리 안 섭취 0
    assert (a.food_v.reshape(-1)[grazed] >= v0).all()                      # 휴식 회복만 일어난다


def make_fixed():
    from policies.registry import make_policy
    return make_policy({"kind": "fixed", "action": G.C2_ACTION})


def test_run_job_records_gate_columns():
    cfg = load_v2_config(ROOT / "configs" / "v2_0b.yaml")
    blk = dict(cfg.v2["features"]["food_v"], alpha=0.1, recovery_half_lives=[693.0])
    on = cfg.replace(v2=dict(cfg.v2, features={"food_v": blk}))
    job = dict(policy="C2", spec={"kind": "fixed", "action": G.C2_ACTION}, seed=20001, steps=1300, warmup=500)
    r = G.run_job(dict(job, cfg=on.to_dict()))
    assert r["half_life"] == 693.0 and r["n_cells"] > 0
    assert set(r["pass"]) == {"a", "b", "c", "d", "all"}
    assert 0.0 < r["v_cell_mean"] <= 1.0 and 0.0 <= r["floor_frac"] <= 1.0
    assert len(r["series"]["t"]) == len(r["series"]["V_L"]) == (1300 - 500) // G.SERIES_EVERY + 1
    assert math.isfinite(r["persist"]) and r["n_top"] >= 1
    off = G.run_job(dict(job, cfg=load_v2_config().to_dict()))         # v2.0: 판정 열 없이 생존 경제만
    assert "pass" not in off and off["lifespan"] > 0 and "f_left" in off


def test_cli_rejects_third_calibration():
    with pytest.raises(SystemExit):
        G.main(["run", "--round", "R3", "--steps", "1300", "--warmup", "500"])
