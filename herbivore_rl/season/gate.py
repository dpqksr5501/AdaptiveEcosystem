"""채택 판정 A1~A5, 보류 시드 재확인, SR1 통과 규칙 (SEASON 4.2, 5.4). 판정은 사전 등록 값 그대로다.

검정은 평가 시드를 짝지은 t(`diagnose_v2.paired`, 자유도 19, |t| > 2.093)다. 학습 시드가 하나라 부트스트랩은 쓰지 않는다.
짝지은 차의 표준편차가 0 이면(예: 아사가 양쪽 모두 0) t 는 차가 0 이면 0, 아니면 차의 부호를 가진 무한대로 둔다. 시드가
하나뿐이면 t 는 nan 이고, nan 은 어느 조건도 만족하지 않는다(유의해야 하는 조건도, 유의하지 않아야 하는 조건도 실패).

| 판정 | 조건 | 행 |
|---|---|---|
| A1 개선 | (a) Ge 피식률이 현재보다 유의하게 낮다 t ≤ −2.093. (b) Ge 피식률이 K2-B 보다도 t ≤ −2.093. (c) G 의 G_γ 비열등: 현재 대비 t > −2.093 이고 점추정 하락 ≤ 5% | Ge/cand·cur·k2b, G/cand·cur |
| A2 상수 붕괴 방지 | (1) G 의 시드별 [G_γ(후보) − G_γ(C1′ 후보)] − [G_γ(현재) − G_γ(C1′ 현재)] 의 t > −2.093. (2) G 에서 후보의 C0 − C1′ 이 t ≥ 2.093 이고 앵커 차의 75% 이상. (3) react_pred(후보) ≥ 0.8 × 현재. (4) 행동 차원별 표준편차 ≥ 0.5 × 현재 (모두 G) | G/cand·cand_P·cur·cur_P(·anchor·anchor_P) |
| A3 망각 방지 | B 에서 앵커와 비교: (1) G_γ t > −2.093 이고 점추정 하락 ≤ 5%. (2) 피식률·아사율이 유의하게 높지 않고(t < 2.093) 수명이 유의하게 짧지 않다(t > −2.093). (3) react_pred ≥ 0.8 × 앵커. (4) 행동 차원별 평균 변화 |Δ| ≤ 0.05 | B/cand·anchor |
| A4 결과 안전 | G 에서 아사율·피식률 t < 2.093, 수명 t > −2.093 (현재 대비) | G/cand·cur |
| A5 수치·파리티 | 정책 파라미터에 NaN·Inf 가 없고, 골든 관측 100개의 출력이 [0,1] 안이며, `export_weights.forward`(C++ RunPolicy 와 같은 순서)와 SB3 결정 출력의 최대 오차 ≤ 1e-5 | 모델 zip |

- react_pred 는 시드 평균(nan 제외)으로 비교한다. 행동 표준편차·평균은 개체-스텝 전체로 묶은 값이다(`eval_worlds.slim_row`).
- A5 는 v1 내보내기(`export_weights.extract`·`forward`·`sample_observations`, 7-64-64-4)로 한다. SR1 앵커와 후보는 모두 이
  차원이다. 다른 차원(V2a 등)은 V2 내보내기 함수가 생기기 전까지 A5 를 실패로 둔다("내보내기 경로 없음"). 언리얼 헤더는
  만들지 않는다(`export_weights.main` 을 부르지 않는다).
- 보류 재확인: A1~A5 를 통과한 후보는 보류 시드 10020~10039 의 Ge 에서 A1(a)(b) 를 다시 본다(SEASON 4.2 선택 편향).
  SR1 통과 규칙이 "학습 시드 2개 모두 A1~A5 와 보류 시드 재확인 통과"라서 통과한 후보마다 재확인한다.
- SR1 통과 규칙(SEASON 5.4:648): 한 (방식, 앵커)가 시즌 3개 중 2개 이상에서, 학습 시드 2개(0, 1) 모두 A1~A5 와 보류
  재확인을 통과해야 한다. 1차 선별 하나만 통과한 것은 통과가 아니다.

    python -m season.gate --candidate runs/season/sr1/train/v1_a_m2_s0.zip --k2b runs/season/sr1/train/v1_k2b_m2_s0.zip \
        --anchor v1 --season a --workers 4 --out runs/season/sr1/gate/v1_a_m2_s0
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import json
import math
from collections import defaultdict

import numpy as np

from diagnose_v2 import nanmean, paired
from evaluate import T_CRIT
from season.common import EVAL_SEEDS, EVAL_STEPS, HOLDOUT_SEEDS, SR1_SEEDS, resolve_anchor

GG_DROP_MAX = 0.05          # A1(c)·A3(1) G_γ 점추정 하락 한도
C0C1_FRAC = 0.75            # A2(2) 앵커 C0 − C1′ 대비 비율
REACT_FRAC = 0.8            # A2(3)·A3(3) react_pred 비율
STD_FRAC = 0.5              # A2(4) 행동 차원별 표준편차 비율
MEAN_SHIFT_MAX = 0.05       # A3(4) 행동 차원별 평균 변화 한도
PARITY_TOL = 1e-5           # A5 골든 최대 오차 (export_weights 기준과 같다)
N_GOLDEN = 100
SR1_MIN_SEASONS = 2

REASON = {"A1": "이득 없음", "A1b": "시즌 효과 없음", "A2": "상수화", "A3": "망각", "A4": "결과 악화", "A5": "파리티"}


# --------------------------------------------------------------------- #
# 검정 도구
# --------------------------------------------------------------------- #


def col(rows: list[dict], c: str) -> np.ndarray:
    return np.array([float("nan") if r.get(c) is None else float(r[c]) for r in rows], dtype=np.float64)


def ttest(a, b) -> dict:
    """짝지은 t (a − b). `diagnose_v2.paired` 에 표준편차 0 처리만 더한다(모듈 docstring)."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if len(a) < 2:                           # 시드 하나: 표준편차가 없다(paired 도 nan 을 낸다)
        return {"diff": float(np.mean(a - b)) if len(a) else float("nan"), "t": float("nan"), "n": int(len(a))}
    res = paired(a, b)
    t = res["t"]
    if len(a) >= 2 and not math.isfinite(t) and math.isfinite(res["diff"]) and res["sd"] == 0.0:
        t = 0.0 if res["diff"] == 0.0 else math.copysign(math.inf, res["diff"])
    return {"diff": float(res["diff"]), "t": float(t), "n": int(len(a))}


def ptest(rows_a: list[dict], rows_b: list[dict], c: str) -> dict:
    """열 c 를 시드로 짝지어 검정한다. 평균과 상대 변화(diff / |평균 b|)도 낸다."""
    sa, sb = [int(r["seed"]) for r in rows_a], [int(r["seed"]) for r in rows_b]
    if sa != sb:
        raise ValueError(f"짝지을 시드가 다르다: {sa[:3]}… vs {sb[:3]}…")
    a, b = col(rows_a, c), col(rows_b, c)
    out = ttest(a, b)
    ma, mb = float(np.mean(a)), float(np.mean(b))
    out.update(mean_a=ma, mean_b=mb, rel=(out["diff"] / abs(mb)) if mb != 0.0 else float("nan"))
    return out


def drop_frac(test: dict) -> float:
    """기준(b) 대비 a 의 하락 비율. 오르면 음수다."""
    mb = test["mean_b"]
    if mb == 0.0:
        return 0.0 if test["mean_a"] >= 0.0 else math.inf
    return (mb - test["mean_a"]) / abs(mb)


def act_stats(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """행동 차원별 평균과 표준편차 (개체-스텝 전체로 묶음). 시드마다 개체-스텝 수가 같아 시드 평균으로 묶는다."""
    m = np.mean([r["act_mean"] for r in rows], axis=0)
    m2 = np.mean([r["act_m2"] for r in rows], axis=0)
    return m, np.sqrt(np.maximum(m2 - m * m, 0.0))


def _lt(t, lim=T_CRIT) -> bool:          # 유의하게 높지 않다
    return bool(t < lim)


def _gt(t, lim=-T_CRIT) -> bool:         # 유의하게 낮지 않다
    return bool(t > lim)


# --------------------------------------------------------------------- #
# A1~A5
# --------------------------------------------------------------------- #


def gate_a1(rows: dict, prefix: str = "") -> dict:
    a = ptest(rows[f"{prefix}Ge/cand"], rows[f"{prefix}Ge/cur"], "predation_rate")
    b = ptest(rows[f"{prefix}Ge/cand"], rows[f"{prefix}Ge/k2b"], "predation_rate")
    a["pass"] = bool(a["t"] <= -T_CRIT)
    b["pass"] = bool(b["t"] <= -T_CRIT)
    out = {"a": a, "b": b}
    if f"{prefix}G/cand" in rows:
        c = ptest(rows[f"{prefix}G/cand"], rows[f"{prefix}G/cur"], "g_gamma")
        c["drop"] = drop_frac(c)
        c["pass"] = bool(_gt(c["t"]) and c["drop"] <= GG_DROP_MAX)
        out["c"] = c
    out["pass"] = all(v["pass"] for v in out.values())
    return out


def gate_a2(rows: dict) -> dict:
    def g(role: str) -> np.ndarray:
        return col(rows[f"G/{role}"], "g_gamma")

    anc, anc_p = ("anchor", "anchor_P") if "G/anchor" in rows else ("cur", "cur_P")
    d1 = ttest(g("cand") - g("cand_P"), g("cur") - g("cur_P"))
    d1["pass"] = _gt(d1["t"])
    d2 = ttest(g("cand"), g("cand_P"))
    anchor_gap = ttest(g(anc), g(anc_p))
    d2["anchor_diff"], d2["anchor_t"] = anchor_gap["diff"], anchor_gap["t"]
    d2["frac"] = d2["diff"] / anchor_gap["diff"] if anchor_gap["diff"] != 0.0 else float("nan")
    d2["pass"] = bool(d2["t"] >= T_CRIT and d2["diff"] >= C0C1_FRAC * anchor_gap["diff"])
    rc, ru = nanmean(col(rows["G/cand"], "react_pred")), nanmean(col(rows["G/cur"], "react_pred"))
    d3 = {"cand": rc, "cur": ru, "pass": bool(rc >= REACT_FRAC * ru)}
    sc, su = act_stats(rows["G/cand"])[1], act_stats(rows["G/cur"])[1]
    d4 = {"cand": sc.tolist(), "cur": su.tolist(), "pass": bool(np.all(sc >= STD_FRAC * su))}
    out = {"1": d1, "2": d2, "3": d3, "4": d4}
    out["pass"] = all(v["pass"] for v in out.values())
    out["anchor_qualified_G"] = bool(anchor_gap["t"] >= T_CRIT)     # 앵커 자격(G 쪽, SEASON 4.2). 판정과 별개
    return out


def gate_a3(rows: dict) -> dict:
    cand, anc = rows["B/cand"], rows["B/anchor"]
    g = ptest(cand, anc, "g_gamma")
    g["drop"] = drop_frac(g)
    g["pass"] = bool(_gt(g["t"]) and g["drop"] <= GG_DROP_MAX)
    pred, starve, surv = (ptest(cand, anc, c) for c in ("predation_rate", "starve_rate", "survival"))
    out2 = {"predation_rate": pred, "starve_rate": starve, "survival": surv,
            "pass": bool(_lt(pred["t"]) and _lt(starve["t"]) and _gt(surv["t"]))}
    rc, ra = nanmean(col(cand, "react_pred")), nanmean(col(anc, "react_pred"))
    d3 = {"cand": rc, "anchor": ra, "pass": bool(rc >= REACT_FRAC * ra)}
    mc, ma = act_stats(cand)[0], act_stats(anc)[0]
    shift = mc - ma
    d4 = {"shift": shift.tolist(), "max_abs": float(np.max(np.abs(shift))),
          "pass": bool(np.all(np.abs(shift) <= MEAN_SHIFT_MAX))}
    out = {"1": g, "2": out2, "3": d3, "4": d4}
    out["pass"] = all(v["pass"] for v in out.values())
    return out


def gate_a4(rows: dict) -> dict:
    cand, cur = rows["G/cand"], rows["G/cur"]
    starve, pred, surv = (ptest(cand, cur, c) for c in ("starve_rate", "predation_rate", "survival"))
    return {"starve_rate": starve, "predation_rate": pred, "survival": surv,
            "pass": bool(_lt(starve["t"]) and _lt(pred["t"]) and _gt(surv["t"]))}


def gate_a5(model_path: str | Path, n: int = N_GOLDEN) -> dict:
    """수치·파리티. v1 내보내기 함수로 골든 n 개를 다시 계산해 SB3 결정 출력과 비교한다(헤더는 쓰지 않는다)."""
    from stable_baselines3 import PPO

    from env.vec_env import sigmoid
    from export_weights import extract, forward, sample_observations

    model = PPO.load(str(model_path), device="cpu")
    sd = model.policy.state_dict()
    finite = bool(all(np.isfinite(v.detach().cpu().numpy()).all() for v in sd.values()))
    out = {"finite_params": finite}
    if not finite:
        return dict(out, reason="NaN·Inf 파라미터", **{"pass": False})
    try:
        w = extract(model)
    except SystemExit as e:                    # 차원이 7-64-64-4 가 아니다
        return dict(out, reason=f"내보내기 경로 없음: {e}", **{"pass": False})
    obs = sample_observations(n)
    try:
        ref = sigmoid(model.predict(obs, deterministic=True)[0])
    except ValueError as e:                    # 분포 인자에 NaN 이 생기면 SB3 가 멈춘다
        return dict(out, reason=f"순전파 실패: {e}", **{"pass": False})
    mine = forward(obs, w)
    again = forward(obs, w)
    err = float(np.abs(ref - mine).max())
    in_range = bool(np.isfinite(mine).all() and (mine >= 0.0).all() and (mine <= 1.0).all())
    out.update(in_range=in_range, max_err=err, deterministic=bool(np.array_equal(mine, again)),
               weights_finite=bool(all(np.isfinite(v).all() for v in w.values())))
    out["pass"] = bool(finite and out["weights_finite"] and in_range and out["deterministic"] and err <= PARITY_TOL)
    return out


def judge(rows: dict, a5: dict) -> dict:
    """A1~A5 판정 결과. 사유는 실패한 판정의 이름표다(A1 은 (b)만 실패면 '시즌 효과 없음')."""
    res = {"A1": gate_a1(rows), "A2": gate_a2(rows), "A3": gate_a3(rows), "A4": gate_a4(rows), "A5": a5}
    reasons = []
    for k in ("A1", "A2", "A3", "A4", "A5"):
        if not res[k]["pass"]:
            if k == "A1" and res[k]["a"]["pass"] and res[k]["c"]["pass"] and not res[k]["b"]["pass"]:
                reasons.append(f"A1 {REASON['A1b']}")
            else:
                reasons.append(f"{k} {REASON[k]}")
    res["pass"] = not reasons
    res["reasons"] = reasons
    res["n_pass"] = sum(bool(res[k]["pass"]) for k in ("A1", "A2", "A3", "A4", "A5"))
    return res


def holdout(rows: dict, prefix: str = "hold/") -> dict:
    """보류 시드 재확인: Ge 에서 A1(a)(b)."""
    return gate_a1(rows, prefix=prefix)


def brief(res: dict) -> dict:
    """요약 표용 핵심 수치."""
    a1, a2, a3 = res["A1"], res["A2"], res["A3"]
    return {
        "ge_pred_rel_vs_cur": a1["a"]["rel"], "ge_pred_t_vs_cur": a1["a"]["t"],
        "ge_pred_rel_vs_k2b": a1["b"]["rel"], "ge_pred_t_vs_k2b": a1["b"]["t"],
        "g_gamma_drop": a1["c"]["drop"], "g_gamma_t": a1["c"]["t"],
        "c0c1_frac": a2["2"]["frac"], "c0c1_t": a2["2"]["t"],
        "b_react_ratio": (a3["3"]["cand"] / a3["3"]["anchor"]) if a3["3"]["anchor"] else float("nan"),
        "b_act_shift_max": a3["4"]["max_abs"],
    }


def rank_key(res: dict) -> tuple:
    """'가장 나은 후보' 순서(2차 확인 대상 고르기, 제안): 전부 통과 > 통과 판정 수 > Ge 피식률 t(현재 대비, 낮을수록)."""
    t = res["A1"]["a"]["t"]
    return (bool(res.get("pass") and res.get("holdout", {}).get("pass", False)), int(res["n_pass"]),
            -math.inf if math.isnan(t) else -t)      # t = −inf(표준편차 0 인 하락)은 가장 앞이다


# --------------------------------------------------------------------- #
# SR1 통과 규칙
# --------------------------------------------------------------------- #


def candidate_ok(res: dict) -> bool:
    """A1~A5 와 보류 재확인을 모두 통과했나."""
    return bool(res.get("pass") and res.get("holdout", {}).get("pass", False))


def sr1_verdict(results: list[dict], seeds=SR1_SEEDS, min_seasons: int = SR1_MIN_SEASONS) -> dict:
    """SR1 통과 규칙 (SEASON 5.4:648). results 의 각 항목은 {anchor, method, season, seed, ok}.

    (방식, 앵커)마다 시즌별로 `seeds` 가 모두 있고 모두 ok 인 시즌을 센다. min_seasons 이상이면 통과다.
    """
    table: dict[tuple, dict] = defaultdict(lambda: defaultdict(dict))
    for r in results:
        table[(r["method"], r["anchor"])][r["season"]][int(r["seed"])] = bool(r["ok"])
    out = {}
    for (method, anchor), seasons in sorted(table.items()):
        good = sorted(s for s, by_seed in seasons.items() if all(by_seed.get(int(x), False) for x in seeds))
        out[f"{method}@{anchor}"] = {"method": method, "anchor": anchor, "seasons_passed": good,
                                    "seasons_seen": sorted(seasons), "pass": len(good) >= min_seasons}
    return {"combos": out, "pass": any(v["pass"] for v in out.values()),
            "rule": f"시즌 {min_seasons}개 이상 × 학습 시드 {list(seeds)} 모두 A1~A5·보류 통과"}


# --------------------------------------------------------------------- #
# 명령줄: 후보 하나 판정
# --------------------------------------------------------------------- #


def clean(o):
    """JSON 저장용: numpy 값을 파이썬 값으로, 무한대·nan 을 문자열로 바꾼다."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else str(f)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def run_gate(cand, cur, k2b, anchor, season, *, executor=None, workers=None, cache=None, gamma=None,
             seeds=EVAL_SEEDS, holdout_seeds=HOLDOUT_SEEDS, steps: int = EVAL_STEPS) -> dict:
    """후보 하나를 평가하고 판정한다. A1~A5 를 통과하면 보류 재확인까지 한다."""
    from env_v2.rollout import model_gamma
    from season.eval_worlds import evaluate_bundle, gate_bundle, ge_sanity, holdout_bundle, world_configs

    gamma = model_gamma(anchor) if gamma is None else float(gamma)
    cfgs = world_configs(season)
    rows = evaluate_bundle(gate_bundle(cand, cur, k2b, anchor), cfgs, seeds, steps, gamma,
                           executor=executor, workers=workers, cache=cache)
    res = judge(rows, gate_a5(cand))
    if res["pass"]:
        rows.update(evaluate_bundle(holdout_bundle(cand, cur, k2b), cfgs, holdout_seeds, steps, gamma,
                                    executor=executor, workers=workers, cache=cache, prefix="hold/"))
        res["holdout"] = holdout(rows)
    res["ge_sanity"] = ge_sanity([v for k, v in rows.items() if "Ge/" in k])
    res["brief"] = brief(res)
    res["gamma"] = gamma
    return res


def main(argv=None) -> int:
    from env_v2.rollout import make_executor
    from season.eval_worlds import EvalCache

    p = argparse.ArgumentParser(description="시즌 후보 하나를 판정한다 (A1~A5, 보류 재확인)")
    p.add_argument("--candidate", required=True)
    p.add_argument("--k2b", required=True, help="같은 앵커·방식·시드의 K2-B zip")
    p.add_argument("--anchor", required=True, help="앵커 이름(v1, v20) 또는 zip")
    p.add_argument("--current", default=None, help="현재 두뇌 zip (기본 = 앵커, SR1 은 시즌 사슬이 없다)")
    p.add_argument("--season", required=True, help="시즌 이름(a, b, c) 또는 yaml")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--steps", type=int, default=EVAL_STEPS)
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--out", required=True, help="gate.json 을 쓸 디렉터리")
    args = p.parse_args(argv)

    _, anchor = resolve_anchor(args.anchor)
    cur = Path(args.current) if args.current else anchor
    ex = make_executor(args.workers)
    try:
        res = run_gate(args.candidate, cur, args.k2b, anchor, args.season, executor=ex,
                       cache=None if args.no_cache else EvalCache(), steps=args.steps)
    finally:
        if ex is not None:
            ex.shutdown()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "gate.json").write_text(json.dumps(clean(res), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"판정: {'채택 가능' if candidate_ok(res) else '기각'} {res['reasons']}  → {out / 'gate.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
