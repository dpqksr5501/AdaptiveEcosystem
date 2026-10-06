"""채택 판정 A1~A5·보류 재확인·SR1 통과 규칙 (season/gate.py, SEASON 4.2·5.4). 손으로 만든 행으로 본다."""

import math

import numpy as np
import pytest

from season import gate as gt
from season.common import ANCHORS, EVAL_SEEDS

SEEDS = list(EVAL_SEEDS)
N = len(SEEDS)
WIGGLE = np.array([1.0, -1.0] * (N // 2))          # 평균 0, 표준편차 > 0 인 결정적 잡음


def rows(seeds=SEEDS, act_mean=(0.4, 0.8, 0.4, 0.1), act_std=(0.2, 0.1, 0.2, 0.05), **cols):
    """열 이름 → 시드별 값(배열 또는 상수)으로 행 목록을 만든다."""
    m, s = np.asarray(act_mean), np.asarray(act_std)
    out = []
    for i, seed in enumerate(seeds):
        r = {"seed": seed, "act_mean": m.tolist(), "act_m2": (s * s + m * m).tolist()}
        for c, v in cols.items():
            r[c] = float(np.broadcast_to(v, (len(seeds),))[i])
        out.append(r)
    return out


def base_cols(**over):
    c = dict(g_gamma=1.0 + 0.01 * WIGGLE, predation_rate=0.004 + 1e-5 * WIGGLE, starve_rate=0.0005 + 1e-5 * WIGGLE,
             survival=300.0 + WIGGLE, react_pred=0.08)
    c.update(over)
    return c


def good_rows() -> dict:
    """모든 판정을 통과하는 후보. Ge 피식률이 현재보다 7.5%, K2-B 보다 5% 낮고 나머지는 현재·앵커와 같다."""
    cur = base_cols()
    r = {
        "G/cur": rows(**cur),
        "G/cur_P": rows(**base_cols(g_gamma=0.6 - 0.01 * WIGGLE)),        # C0 − C1′ = 0.4 + 0.02·잡음
        "G/cand": rows(**base_cols(g_gamma=1.0 + 0.012 * WIGGLE)),
        "G/cand_P": rows(**base_cols(g_gamma=0.6 - 0.01 * WIGGLE)),       # C0 − C1′ = 0.4 + 0.022·잡음
        "Ge/cur": rows(predation_rate=0.0040 + 2e-5 * WIGGLE, starve_rate=0.0, repro=0.0),
        "Ge/k2b": rows(predation_rate=0.0039 + 2e-5 * WIGGLE[::-1], starve_rate=0.0, repro=0.0),
        "Ge/cand": rows(predation_rate=0.0037 + 1e-5 * WIGGLE, starve_rate=0.0, repro=0.0),
        "B/anchor": rows(**base_cols(g_gamma=3.0 + 0.02 * WIGGLE)),
        "B/cand": rows(**base_cols(g_gamma=3.0 + 0.02 * WIGGLE[::-1])),
    }
    return r


A5_OK = {"pass": True, "max_err": 0.0}


def test_ttest_degenerate():
    assert gt.ttest([1.0, 1.0], [1.0, 1.0])["t"] == 0.0
    assert gt.ttest([2.0, 2.0], [1.0, 1.0])["t"] == math.inf
    assert gt.ttest([0.0, 0.0], [1.0, 1.0])["t"] == -math.inf
    assert math.isnan(gt.ttest([2.0], [1.0])["t"])           # 시드 하나: 결론 없음
    with pytest.raises(ValueError):
        gt.ptest(rows(seeds=[1, 2], x=0.0), rows(seeds=[1, 3], x=0.0), "x")


def test_good_candidate_passes():
    res = gt.judge(good_rows(), A5_OK)
    assert res["pass"] and res["reasons"] == [] and res["n_pass"] == 5
    assert res["A1"]["a"]["t"] <= -gt.T_CRIT and res["A1"]["b"]["t"] <= -gt.T_CRIT
    assert res["A1"]["c"]["drop"] <= 0.05
    assert res["A2"]["2"]["frac"] == pytest.approx(1.0) and res["A2"]["anchor_qualified_G"]
    b = gt.brief(res)
    assert b["ge_pred_rel_vs_cur"] == pytest.approx(-0.075) and b["b_act_shift_max"] == 0.0


@pytest.mark.parametrize("case,mutate,reason", [
    ("A1(a) 현재보다 낮지 않다", lambda r: r.update({"Ge/cand": r["Ge/cur"]}), "A1 이득 없음"),
    ("A1(b) K2-B 보다 낮지 않다", lambda r: r.update({"Ge/k2b": rows(predation_rate=0.0037 + 1e-5 * WIGGLE[::-1])}),
     "A1 시즌 효과 없음"),
    ("A1(c) G_γ 6% 하락", lambda r: r.update({"G/cand": rows(**base_cols(g_gamma=0.94 + 0.01 * WIGGLE)),
                                               "G/cand_P": rows(**base_cols(g_gamma=0.53 - 0.01 * WIGGLE))}),
     "A1 이득 없음"),
    ("A2(2) C0−C1′ 이 앵커의 75% 미만", lambda r: r.update({"G/cand_P": rows(**base_cols(g_gamma=0.75 + 0.01 * WIGGLE))}),
     "A2 상수화"),
    ("A2(3) react_pred 0.5배", lambda r: r.update({"G/cand": rows(**base_cols(g_gamma=1.0 + 0.012 * WIGGLE,
                                                                               react_pred=0.04))}), "A2 상수화"),
    ("A2(4) 행동 표준편차 0.4배", lambda r: r.update({"G/cand": rows(act_std=(0.08, 0.04, 0.08, 0.02),
                                                                  **base_cols(g_gamma=1.0 + 0.012 * WIGGLE))}),
     "A2 상수화"),
    ("A3(4) B 행동 평균 0.06 이동", lambda r: r.update({"B/cand": rows(act_mean=(0.46, 0.8, 0.4, 0.1),
                                                                    **base_cols(g_gamma=3.0 + 0.02 * WIGGLE))}),
     "A3 망각"),
    ("A3(2) B 피식률 유의 상승", lambda r: r.update({"B/cand": rows(**base_cols(g_gamma=3.0 + 0.02 * WIGGLE,
                                                                             predation_rate=0.0042 + 1e-5 * WIGGLE))}),
     "A3 망각"),
    ("A4 G 아사율 유의 상승", lambda r: r.update({"G/cand": rows(**base_cols(g_gamma=1.0 + 0.012 * WIGGLE,
                                                                             starve_rate=0.0007 + 1e-5 * WIGGLE))}),
     "A4 결과 악화"),
])
def test_each_gate_fails_alone(case, mutate, reason):
    r = good_rows()
    mutate(r)
    res = gt.judge(r, A5_OK)
    assert not res["pass"] and res["reasons"] == [reason], case


def test_a5_fail_reason():
    res = gt.judge(good_rows(), {"pass": False, "max_err": 1.0})
    assert res["reasons"] == ["A5 파리티"]


def test_a5_on_anchor_and_nan_model(tmp_path):
    """A5: 앵커는 골든 100쌍 최대 오차 ≤ 1e-5 로 통과한다. 가중치에 NaN 을 넣은 사본은 실패한다."""
    import torch as th
    from stable_baselines3 import PPO

    ok = gt.gate_a5(ANCHORS["v1"])
    assert ok["pass"] and ok["max_err"] <= gt.PARITY_TOL and ok["in_range"] and ok["deterministic"]
    m = PPO.load(str(ANCHORS["v1"]), device="cpu")
    with th.no_grad():
        m.policy.action_net.bias[0] = float("nan")
    m.save(tmp_path / "nan.zip")
    bad = gt.gate_a5(tmp_path / "nan.zip")
    assert not bad["pass"] and not bad["finite_params"]


def test_holdout_uses_prefixed_rows():
    r = good_rows()
    hold = {f"hold/{k}": v for k, v in r.items() if k.startswith("Ge/")}
    h = gt.holdout(hold)
    assert h["pass"] and set(h) == {"a", "b", "pass"}
    hold["hold/Ge/cand"] = hold["hold/Ge/k2b"]
    assert not gt.holdout(hold)["pass"]


def test_rank_key_orders():
    good = gt.judge(good_rows(), A5_OK)
    good["holdout"] = {"pass": True}
    r = good_rows()
    r["Ge/cand"] = r["Ge/cur"]
    weak = gt.judge(r, A5_OK)
    assert gt.rank_key(good) > gt.rank_key(weak)
    assert gt.candidate_ok(good) and not gt.candidate_ok(weak)
    inf_drop = dict(weak, A1=dict(weak["A1"], a=dict(weak["A1"]["a"], t=-math.inf)))
    nan_t = dict(weak, A1=dict(weak["A1"], a=dict(weak["A1"]["a"], t=math.nan)))
    assert gt.rank_key(inf_drop) > gt.rank_key(weak) > gt.rank_key(nan_t)
    no_hold = dict(good)
    no_hold.pop("holdout")
    assert not gt.candidate_ok(no_hold)


def test_sr1_verdict_rule():
    """시즌 2개 이상 × 시드 0·1 모두 통과해야 (방식, 앵커)가 통과한다. 1차 선별 하나는 통과가 아니다."""
    R = []

    def add(method, anchor, season, seed, ok):
        R.append({"method": method, "anchor": anchor, "season": season, "seed": seed, "ok": ok})

    for s in ("a", "b"):                         # m2@v20: a, b 모두 두 시드 통과 → 통과
        for seed in (0, 1):
            add("m2", "v20", s, seed, True)
    add("m2", "v20", "c", 0, False)
    add("m1", "v1", "a", 0, True)                # m1@v1: 1차 선별 하나만 → 미통과
    for s in ("a", "b"):                         # m3@v1: b 의 시드 1 이 없다 → 시즌 하나만 센다
        add("m3k0p5", "v1", s, 0, True)
    add("m3k0p5", "v1", "a", 1, True)
    v = gt.sr1_verdict(R)
    c = v["combos"]
    assert c["m2@v20"]["pass"] and c["m2@v20"]["seasons_passed"] == ["a", "b"]
    assert not c["m1@v1"]["pass"] and not c["m3k0p5@v1"]["pass"] and c["m3k0p5@v1"]["seasons_passed"] == ["a"]
    assert v["pass"]


def test_clean_json():
    import json

    d = gt.clean({"a": np.float32(1.5), "b": [math.inf, np.int64(3)], "c": np.bool_(True), "d": float("nan")})
    assert json.loads(json.dumps(d)) == {"a": 1.5, "b": ["inf", 3], "c": True, "d": "nan"}
