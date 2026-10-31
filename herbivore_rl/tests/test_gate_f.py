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


# --------------------------------------------------------------------- #
# R10 (10-02 승인 F4 정의, results/v2/gate_f_r10/PREREG.md)
# --------------------------------------------------------------------- #

OLD_DIR = ROOT / "results" / "v2" / "gate_f"
K600 = 2.0 ** (-G.QUIET / 693.0)


def _keep_out(monkeypatch):
    """G.main(--out) 가 바꾸는 모듈 전역(OUT·ROUNDS·NOTES)을 테스트 뒤 되돌린다."""
    for k in ("OUT", "ROUNDS", "NOTES"):
        monkeypatch.setattr(G, k, getattr(G, k))


def _fv_cfg(name="v2_0b.yaml", **kw):
    cfg = load_v2_config(ROOT / "configs" / name)
    blk = dict(cfg.v2["features"]["food_v"], **kw)
    return cfg.replace(v2=dict(cfg.v2, features=dict(cfg.v2["features"], food_v=blk)))


def test_trace_sets_r10_definition():
    """r10: 섭식 강도(누적 섭취/cap0) 순위. 같은 장난감에서 상위는 같고, 마지막 구간 기준 셀은 cap0 가 큰 쪽
    {31..35}(섭취 1 이 같으면 cap0 가 클수록 강도가 작다)로 1002 의 {30..34} 와 다르다."""
    cap, eaten, _ = _toy()
    bin_of, top, refs = G.trace_sets(cap, eaten, G.F4_R10)
    assert sorted(top.tolist()) == [36, 37, 38, 39]
    assert all(r.size == 5 for r in refs)
    assert not set(top.tolist()) & set(np.concatenate(refs).tolist())
    assert set(refs[3].tolist()) == {31, 32, 33, 34, 35}
    eaten2 = eaten.copy()
    eaten2[2] = 5.0                                           # cap0 0.146 → 강도 34: 섭취는 작아도 상위
    assert sorted(G.trace_sets(cap, eaten2, G.F4_R10)[1].tolist()) == [2, 37, 38, 39]
    assert sorted(G.trace_sets(cap, eaten2)[1].tolist()) == [36, 37, 38, 39]     # 1002 는 누적 섭취 순위
    np.testing.assert_array_equal(G.trace_key(cap, eaten2, G.F4_R10), eaten2 / cap)
    with pytest.raises(ValueError):
        G.trace_key(cap, eaten, "x")


def test_trace_metrics_r10_uses_r10_sets():
    cap, eaten, X = _toy()
    v_after = np.full(len(cap), 0.8)
    v_after[36:] = 0.6
    a = G.trace_metrics(X, cap, eaten, np.empty(0, int), np.empty(0, int), 120, v_after=v_after, f4_def=G.F4_R10)
    b = G.trace_metrics(X, cap, eaten, np.empty(0, int), np.empty(0, int), 120, v_after=v_after)
    assert a["n_top"] == b["n_top"] == 4
    assert a["amp"] == pytest.approx(0.4, abs=1e-5) and a["persist"] == pytest.approx(0.2)
    inten = eaten / cap
    assert a["intensity_ratio"] == pytest.approx(inten[36:].sum() / (4 * inten[31:36].mean()))


def test_paired_rest_fences_both_groups_and_persist_identity():
    """짝 휴식: 상위·기준 셀을 함께 막으면 두 무리 모두 섭취가 0 이고 V 는 휴식 회복만 해서
    1 − V/cap0 가 셀마다 2^(−600/h) 배가 된다. 그래서 600스텝 뒤 차 = 2^(−600/h)·울타리 직전 차(항등식)."""
    cfg = _fv_cfg(alpha=0.1, recovery_half_lives=[693.0])
    w, pol = G.ExclosureWorld(cfg, seeds=[636]), make_fixed()
    for _ in range(800):
        w.step(pol(w.observe()))
    cap_all = w.food_cap.reshape(-1)
    pos = np.flatnonzero(cap_all > 0.0)
    cap = cap_all[pos]
    bin_of, top, refs = G.trace_sets(cap, w._fv_eaten.reshape(-1)[pos].copy(), G.F4_R10)
    assert (w._fv_eaten.reshape(-1)[pos[top]] > 0).all()
    sel = np.concatenate([top, *refs])
    w.excl = pos[sel]
    e0, v0 = w._fv_eaten.reshape(-1).copy(), w.food_v.reshape(-1)[pos] / cap
    for _ in range(G.QUIET):
        w.step(pol(w.observe()))
    e1, v1 = w._fv_eaten.reshape(-1), w.food_v.reshape(-1)[pos] / cap
    np.testing.assert_array_equal(e1[pos[top]], e0[pos[top]])                       # 상위 셀 섭취 0
    np.testing.assert_array_equal(e1[pos[np.concatenate(refs)]], e0[pos[np.concatenate(refs)]])   # 기준 셀도
    assert (w._fv_last_eat.reshape(-1)[w.excl] <= 800).all()
    assert (e1 > e0).any()                                    # 울타리 밖에서는 계속 먹었다
    np.testing.assert_allclose(1.0 - v1[sel], K600 * (1.0 - v0[sel]), rtol=0, atol=1e-12)
    ok = np.array([r.size > 0 for r in refs])
    t = top[ok[bin_of[top]]]
    assert G.gap_after(v1, bin_of, t, refs) == pytest.approx(K600 * G.gap_after(v0, bin_of, t, refs), abs=1e-12)


def test_run_job_r10_records_prediction_and_supply():
    """run_job r10: 울타리 = 상위 + 기준 셀, 600스텝 뒤 = 예측(1e-6 안, run_job 이 단언한다), 먹이 공급 열."""
    job = dict(policy="C2", spec={"kind": "fixed", "action": G.C2_ACTION}, seed=636, steps=1300, warmup=500,
               cfg=_fv_cfg(alpha=0.1, recovery_half_lives=[693.0]).to_dict(), f4_def=G.F4_R10)
    r = G.run_job(job)
    assert r["f4_def"] == "r10" and r["n_fenced"] > r["n_top"] >= 1
    assert r["persist_k"] == pytest.approx(K600) and math.isfinite(r["persist_pred"])
    assert abs(r["persist"] - r["persist_pred"]) < G.PERSIST_TOL
    assert r["persist_pred"] == pytest.approx(K600 * r["amp_end"])
    assert r["need"] == pytest.approx(128 * 0.002 / 0.5) and r["food_scarce"] is False
    old = G.run_job(dict(job, f4_def=G.F4_OLD))                  # 1002: 상위 셀만 울타리라 항등식이 아니다
    assert old["f4_def"] == "1002" and "persist_pred" not in old and "n_fenced" not in old
    assert old["v_cell_mean"] == r["v_cell_mean"]                 # 창 안 지표는 정의와 무관하다(같은 세계·정책)


@pytest.mark.parametrize("name", ["v2_0b.yaml", "v2_1_0b.yaml"])
def test_food_scarce_flag_on_calibration_seeds(name):
    """먹이 부족 세계 = 공급 상한 Σ r·cap0 < 기초 수요 128·0.002/0.5 = 0.512. 보정 시드 중 20001 만이다
    (PREREG 값 2.739 / 0.278 / 1.996). v2.1 세계도 같은 시드의 배치·재생이 같아 값이 같다."""
    cfg = load_v2_config(ROOT / "configs" / name)
    got = {s: G.food_supply(G.ExclosureWorld(cfg, seeds=[s]), cfg) for s in G.CALIB_SEEDS}
    assert {s: g["food_scarce"] for s, g in got.items()} == {20000: False, 20001: True, 20002: False}
    for s, v in {20000: 2.739, 20001: 0.278, 20002: 1.996}.items():
        assert got[s]["supply_max"] == pytest.approx(v, abs=5e-4)
        assert got[s]["need"] == pytest.approx(0.512)
    w = G.ExclosureWorld(cfg, seeds=[20001])
    assert got[20001]["supply_max"] == pytest.approx(float((w.regen_field * w.food_cap).sum()))


def _row(policy, seed, scarce=False, amp=0.3, **fail):
    p = dict(a=True, b=True, c=True, d=True)
    p.update({k: False for k in fail})
    p["all"] = all(p.values())
    return {"policy": policy, "seed": seed, "pass": p, "amp": amp, "persist": 0.15, "food_scarce": scarce}


def test_summary_r10_judges_non_scarce_cells_only():
    rows = [_row(pn, s, scarce=s == 20001, **({"b": 1, "c": 1} if s == 20001 else {}), amp=0.0 if s == 20001 else 0.3)
            for pn in G.V1_POLICIES for s in G.CALIB_SEEDS]
    s = G.summarize_candidate(rows, G.F4_R10)
    assert s["n"] == 6 and s["n_total"] == 9 and s["passed"] and s["abd_all"] and s["d_all"]
    assert s["n_pass"]["all"] == 6 and s["n_pass_total"]["all"] == 6 and s["n_pass_total"]["b"] == 6
    assert s["amp_mean"] == pytest.approx(0.3) and s["amp_mean_total"] == pytest.approx(0.2)
    assert sorted(s["scarce"]) == sorted([pn, 20001] for pn in G.V1_POLICIES)
    old = G.summarize_candidate(rows)                                        # 1002: 9칸, 10-02 키 그대로
    assert old["n"] == 9 and not old["passed"] and not old["abd_all"]
    assert set(old) == {"n", "n_pass", "abd_all", "n_abd", "amp_mean", "amp_min", "persist_mean", "passed"}
    none = G.summarize_candidate([dict(r, food_scarce=True) for r in rows], G.F4_R10)
    assert none["n"] == 0 and not none["passed"] and not none["abd_all"] and not none["d_all"]


def test_select_r10_counts_judged_cells():
    """R2 선택: 먹이 부족 칸에서만 (b)가 깨진 후보는 r10 에서 (a)(b)(d)를 지킨 것으로 본다. 진폭 평균은 판정 칸 값."""
    base = [(pn, s) for pn in G.V1_POLICIES for s in G.CALIB_SEEDS]
    a = [_row(pn, s, scarce=s == 20001, amp=0.15) for pn, s in base]
    b = [_row(pn, s, scarce=s == 20001, amp=0.25, **({"b": 1} if s == 20001 else {})) for pn, s in base]
    c = [_row(pn, s, scarce=s == 20001, amp=0.4, **({"d": 1} if s == 20000 else {})) for pn, s in base]
    for f4, want in ((G.F4_R10, 1), (G.F4_OLD, 0)):
        cands = [{"summary": G.summarize_candidate(x, f4)} for x in (a, b, c)]
        assert G.select(cands) == want, f4


@pytest.mark.parametrize("name", ["v2_0b.yaml", "v2_1_0b.yaml"])
def test_exclosure_world_without_fence_is_world_both_configs(name):
    """울타리 없는 ExclosureWorld = World (비트 단위). v2_1_0b(speed + food_v)는 World.step 이 보행 섭식 배수를
    넘기므로(_eat(e, mult)) 그것도 그대로 넘겨야 한다. 행동은 정지·걷기·뛰기가 모두 나오게 무작위다."""
    from env_v2.world import World, action_dim
    cfg = load_v2_config(ROOT / "configs" / name)
    d = action_dim(cfg)
    a, b = G.ExclosureWorld(cfg, seeds=[20001]), World(cfg, seeds=[20001])
    rng = np.random.default_rng(3)
    for _ in range(300):
        act = rng.random((a.N, d))
        np.testing.assert_array_equal(a.observe(), b.observe())
        a.step(act)
        b.step(act)
    for k in ("food", "food_v", "pos", "energy", "_fv_eaten"):
        assert np.array_equal(getattr(a, k), getattr(b, k)), k
    assert a.stats() == b.stats()
    if d == 5:
        assert a.gait_stats() == pytest.approx(b.gait_stats(), nan_ok=True)
    grazed = np.flatnonzero(a._fv_eaten.reshape(-1) > 0)
    a.excl = grazed
    e0, v0 = a._fv_eaten.reshape(-1)[grazed].copy(), a.food_v.reshape(-1)[grazed].copy()
    for _ in range(100):
        a.step(rng.random((a.N, d)))
    assert np.array_equal(a._fv_eaten.reshape(-1)[grazed], e0)            # 울타리 안 섭취 0
    assert (a.food_v.reshape(-1)[grazed] >= v0).all()                      # 휴식 회복만 일어난다


V21_SHA256 = "effeae61b1b890af33608edd0730d6e769c05ae23d3820ec123bf3e81446237c"   # results/v2/s1a/report.md


@pytest.mark.skipif(not G.V21_MODEL.exists(), reason="v2.1 출시 모델은 커밋하지 않는다(로컬 전용)")
def test_run_job_v21_on_speed_food_v_world():
    """고정 정책 확인의 잡 하나: v2_1_0b(speed + food_v)에 v2.1 출시 모델(결정)을 넣어 r10 울타리 시험까지 돈다
    (ExclosureWorld 가 보행 섭식 배수를 넘긴다). 보정 시드가 아닌 짧은 실행이다."""
    meta = G.policy_meta(G.policy_specs(["v21"]))["v21"]
    assert meta["sha256"] == V21_SHA256 and meta["deterministic"] and meta["source"] == "ckpt/v2/s1a_g_s58.zip"
    cfg = load_v2_config(ROOT / "configs" / "v2_1_0b.yaml")
    r = G.run_job(dict(policy="v21", spec=G.policy_specs(["v21"])["v21"], seed=636, steps=1300, warmup=500,
                       cfg=cfg.to_dict(), f4_def=G.F4_R10))
    assert r["half_life"] == 693.0 and r["alpha"] == 0.03 and set(r["pass"]) == {"a", "b", "c", "d", "all"}
    assert abs(r["persist"] - r["persist_pred"]) < G.PERSIST_TOL and r["lifespan"] > 0


def test_policy_specs_v21():
    sp = G.policy_specs(["v21", "c2v21"])
    assert sp["v21"] == {"kind": "learned", "model": str(G.V21_MODEL.resolve())}
    assert sp["c2v21"]["kind"] == "fixed" and len(sp["c2v21"]["action"]) == 5
    assert all(G.POLICY_ACT_DIM[n] == 5 for n in G.V21_POLICIES)
    assert all(G.POLICY_ACT_DIM[n] == 4 for n in G.V1_POLICIES)
    assert set(G.POLICY_ORDER) == set(G.POLICY_LABEL) == set(G.POLICY_ACT_DIM)
    assert set(G.ROUND_NAMES) == set(G.ROUND_LABEL)


def test_old_dir_report_is_reproduced(tmp_path, monkeypatch):
    """meta 에 f4_def 가 없는 10-02 기록(results/v2/gate_f)은 1002 정의로 읽어 report.md·report.json 을 생성 시각
    말고는 그대로 다시 만든다(측정 정의 글도 10-02 그대로). 원본 디렉터리는 건드리지 않고 사본으로 잰다."""
    import json
    import shutil
    _keep_out(monkeypatch)
    shutil.copytree(OLD_DIR / "rounds", tmp_path / "rounds")
    assert G.main(["report", "--out", str(tmp_path)]) == 0
    old = (OLD_DIR / "report.md").read_text(encoding="utf-8").split("\n")
    new = (tmp_path / "report.md").read_text(encoding="utf-8").split("\n")
    assert len(old) == len(new)
    assert [i for i, (x, y) in enumerate(zip(old, new)) if x != y] == [2]    # 생성 시각 줄만
    assert old[2].split("(")[0] == new[2].split("(")[0] and old[2].split(")", 1)[1] == new[2].split(")", 1)[1]
    jo = json.loads((OLD_DIR / "report.json").read_text(encoding="utf-8"))
    jn = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    jo["meta"].pop("generated")
    jn["meta"].pop("generated")
    assert jo == jn and jn["meta"]["definitions"] == G.DEFINITIONS and "f4_def" not in jn["meta"]


def _r10_dir(tmp_path, final="R1", fixed=False, r2=False):
    """10-02 R1 선택값·ref 기록에 r10 표시와 먹이 공급 열을 붙인 보고서 형식 시험용 디렉터리(판정 값은 10-02 정의라
    새 F4 값이 아니다). fixed 면 같은 칸의 정책 이름을 v2.1 쪽(C2 → c2v21, learned → v21)으로 바꾼 fixed·ref21 도 둔다.
    r2 면 같은 후보를 R2 격자 6개(α 2 × h 3 이름)로 복제한 R2 도 둔다."""
    import copy
    import json
    supply = {20000: 2.739, 20001: 0.278, 20002: 1.996}
    rename = {"C2": "c2v21", "learned": "v21"}
    (tmp_path / "rounds").mkdir(parents=True)
    plan = [("R1", final), ("ref", "ref")] + ([("R1", "fixed"), ("ref", "ref21")] if fixed else []) \
        + ([("R1", "R2")] if r2 else [])
    for name, out in plan:
        d = json.loads((OLD_DIR / "rounds" / f"{name}.json").read_text(encoding="utf-8"))
        d["meta"]["f4_def"] = G.F4_R10
        d["meta"]["round"] = out
        c = copy.deepcopy(d["candidates"][d["selected"] or 0])
        if out in ("fixed", "ref21"):
            c["rows"] = [dict(r, policy=rename[r["policy"]]) for r in c["rows"] if r["policy"] in rename]
            d["meta"]["policies"] = {rename[k]: dict(v, label=G.POLICY_LABEL[rename[k]]) for k, v in
                                     d["meta"]["policies"].items() if k in rename}
        if name == "R1":
            for r in c["rows"]:
                r.update(supply_max=supply[r["seed"]], need=0.512, supply_ratio=supply[r["seed"]] / 0.512,
                         food_scarce=r["seed"] == 20001, intensity_ratio=r["intake_ratio"], persist_pred=None)
            c["summary"] = G.summarize_candidate(c["rows"], G.F4_R10)
        d["candidates"], d["selected"] = [c], 0
        if out == "R2":
            d["candidates"] = [dict(copy.deepcopy(c), label=f"α {a} · 하한 0.1 · h {h}")
                               for a in (0.03, 0.05) for h in (693, 1386, 2079)]
        (tmp_path / "rounds" / f"{out}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_r10_report_judged_cells_scarce_table_and_branch(tmp_path, monkeypatch):
    _keep_out(monkeypatch)
    G.main(["report", "--out", str(_r10_dir(tmp_path / "a"))])
    t = (tmp_path / "a" / "report.md").read_text(encoding="utf-8")
    assert "판정 칸 6칸" in t and "참고 9칸 전체" in t and "먹이 부족 세계 (판정 제외, 따로 보고):" in t
    assert "| 20001 | 10.7 (49) | 0.278 | 0.512 | 0.54 | 예 |" in t
    assert "600스텝 뒤 (짝 휴식)" in t and "R2 를 1회" in t and "사람이 정한다" not in t
    assert G.DEFINITIONS_R10[3] in t and G.DEFINITIONS[3] not in t
    assert len(t.split("\n")) <= 150
    G.main(["report", "--out", str(_r10_dir(tmp_path / "b", final="R2"))])
    t2 = (tmp_path / "b" / "report.md").read_text(encoding="utf-8")
    assert f"기존 그림(`{G.S7_FIGURE}`" in t2 and "학습 분포에 넣지 않는다" in t2


def test_r10_report_fixed_check_judges_release_model_only(tmp_path, monkeypatch):
    """고정 정책 확인: 판정은 v2.1 출시 모델(v21)의 판정 칸(먹이 부족 세계 제외) (d)만, v2.1 C2 는 보고만."""
    import json
    _keep_out(monkeypatch)
    out = _r10_dir(tmp_path / "f", fixed=True)
    rounds = {n: json.loads((out / "rounds" / f"{n}.json").read_text(encoding="utf-8"))
              for n in ("R1", "ref", "fixed", "ref21")}
    fx = G.fixed_verdict(rounds)
    assert fx["judge_policies"] == ["v21"] and fx["n"] == 2 and fx["passed"]        # v21 × {20000, 20002}
    c = rounds["fixed"]["candidates"][0]
    for r in c["rows"]:
        if r["policy"] == "c2v21":
            r["pass"] = dict(r["pass"], d=False, all=False)                         # C2 실패는 판정과 무관
    assert G.fixed_verdict(rounds)["passed"]
    for r in c["rows"]:
        if r["policy"] == "v21" and r["seed"] == 20001:
            r["pass"] = dict(r["pass"], d=False, all=False)                         # 먹이 부족 칸도 무관
    assert G.fixed_verdict(rounds)["passed"]
    for r in c["rows"]:
        if r["policy"] == "v21" and r["seed"] == 20002:
            r["pass"] = dict(r["pass"], d=False, all=False)
    assert not G.fixed_verdict(rounds)["passed"]
    G.main(["report", "--out", str(out)])
    t = (out / "report.md").read_text(encoding="utf-8")
    assert "- 고정 정책 확인 `α 0.03 · 하한 0.1 · h 693`: **통과**" in t and "## v2.1 대비 생존 경제" in t
    assert "### fixed 고정 정책 확인" in t and "F 가 실패해 이 결과는 보고만 한다." in t
    assert len(t.split("\n")) <= 150


def test_r10_report_all_rounds_fits_150_lines(tmp_path, monkeypatch):
    """회차를 모두 돌린 디렉터리(ref, R1, R2 격자 6후보, fixed, ref21)의 보고서도 150줄 안이다(R1 은 요약 한 줄)."""
    _keep_out(monkeypatch)
    out = _r10_dir(tmp_path / "all", fixed=True, r2=True)
    G.main(["report", "--out", str(out)])
    t = (out / "report.md").read_text(encoding="utf-8")
    assert "마지막 회차 R2 보정 2회차" in t and "| α 0.05 · 하한 0.1 · h 2079 |" in t
    assert "- 선택값 `α 0.03 · 하한 0.1 · h 693` — 실패." in t                    # R1 은 한 줄
    assert len(t.split("\n")) <= 150, len(t.split("\n"))


def test_cli_r10_guards(tmp_path, monkeypatch):
    """참고 회차 짝(ref·ref21 ↔ --reference), 행동 수, food_v 끈 참고 설정, 한 디렉터리 정의 섞기 금지.
    모두 잡을 돌리기 전에 멈춘다."""
    import argparse
    import shutil
    _keep_out(monkeypatch)
    run = ["run", "--out", str(tmp_path), "--steps", "1300", "--warmup", "500"]
    for extra in (["--round", "ref21"], ["--round", "fixed", "--reference"], ["--round", "R1", "--reference"],
                  ["--round", "fixed", "--policies", "C2"],                         # 행동 4 정책 × 행동 5 세계
                  ["--round", "R1", "--policies", "v21"],                           # 행동 5 정책 × 행동 4 세계
                  ["--round", "ref", "--reference", "--config", str(ROOT / "configs" / "v2_0b.yaml")]):
        with pytest.raises(SystemExit):
            G.main(run + extra)
    ref21 = G.build_candidates(argparse.Namespace(reference=True, config="v2_1.yaml"),
                               load_v2_config(ROOT / "configs" / "v2_1.yaml"))
    assert len(ref21) == 1 and ref21[0]["label"] == "food_v 끔 (v2.1)" and ref21[0]["params"] is None
    old = tmp_path / "old"
    (old / "rounds").mkdir(parents=True)
    shutil.copy(OLD_DIR / "rounds" / "ref.json", old / "rounds" / "ref.json")
    with pytest.raises(SystemExit, match="섞지"):
        G.main(["run", "--out", str(old), "--round", "R2", "--alpha", "0.03", "--steps", "1300", "--warmup", "500"])
    mix = _r10_dir(tmp_path / "mix")
    shutil.copy(OLD_DIR / "rounds" / "R0.json", mix / "rounds" / "R0.json")              # meta 에 f4_def 없음 = 1002
    with pytest.raises(SystemExit, match="섞여"):
        G.main(["report", "--out", str(mix)])


def test_cli_run_r10_smoke(tmp_path, monkeypatch):
    """run 전 과정(워커 프로세스, 회차 기록, 보고서)을 보정 시드가 아닌 시드 하나·짧은 실행으로 돈다:
    R1(v2.0b, C2), fixed(v2_1_0b, v2.1 C2 — 판정 정책 v21 이 없으니 통과가 아니다), ref21(v2.1, food_v 끔)."""
    import json
    _keep_out(monkeypatch)
    run = ["run", "--out", str(tmp_path), "--seeds", "636", "--steps", "1300", "--warmup", "500", "--workers", "1"]
    assert G.main(run + ["--round", "R1", "--alpha", "0.1", "--policies", "C2"]) == 0
    assert G.main(run + ["--round", "fixed", "--alpha", "0.1", "--policies", "c2v21"]) == 0
    assert G.main(run + ["--round", "ref21", "--reference", "--policies", "c2v21"]) == 0
    r1 = json.loads((tmp_path / "rounds" / "R1.json").read_text(encoding="utf-8"))
    assert r1["meta"]["f4_def"] == "r10" and r1["candidates"][0]["summary"]["n_total"] == 1
    row = r1["candidates"][0]["rows"][0]
    assert row["f4_def"] == "r10" and row["n_fenced"] > row["n_top"] and not row["food_scarce"]
    fx = json.loads((tmp_path / "rounds" / "fixed.json").read_text(encoding="utf-8"))
    assert fx["meta"]["config"] == "configs/v2_1_0b.yaml" and fx["candidates"][0]["rows"][0]["policy"] == "c2v21"
    ref21 = json.loads((tmp_path / "rounds" / "ref21.json").read_text(encoding="utf-8"))
    assert ref21["meta"]["config"] == "configs/v2_1.yaml" and ref21["candidates"][0]["label"] == "food_v 끔 (v2.1)"
    rep = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert rep["meta"]["f4_def"] == "r10" and rep["fixed"]["n"] == 0 and not rep["fixed"]["passed"]
    t = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## v2.1 대비 생존 경제 (고정 정책, 참고)" in t and "F4 정의 r10" in t
