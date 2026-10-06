"""v2.4 환경 확인 N (계획서 2-5 행 Gate N (a1)~(a3), 10-03 R6 게이트 역할, 사전 등록 results/v2/v2_4/PREREG.md).

    python gate_n.py run --round N0 --out results/v2/v2_4/gate_n --workers 16
    python gate_n.py run --round N1c --set daynight.detect_night=0.75 --out results/v2/v2_4/gate_n --workers 16
    python gate_n.py report --out results/v2/v2_4/gate_n

한 회차 = 정책 3개 × 세계 3개 × 보정 시드(기본 20000~20019) × 30000스텝.
- 세계: on = configs/v2_4_on.yaml(+ --set 덮기, 판정 세계), rest0 = on 에서 rest_night 0((a3) 비교), ref = configs/v2_1.yaml
  (낮밤 없음, 안전 항목의 기준)
- 정책: C2 = E1-b 최적 상수, CSEG = E1-b C2-seg(results/v2/e1/B1/r2_5_ew0_5, E1 (a) 를 잰 정책), FIX = 고정된 최신 정책
  s1a_g_s58 결정 모드(관측 앞 7칸만 넣는다), C2F = C2 에서 flee_dist 만 1.0(도주 반경 see_r — 탐지 축소를 느끼는 상수,
  (a1) 판정), CSTOP = C2 에서 speed 만 0(늘 정지 — 휴식 할인을 받는 상수, (a3) 판정)
- 먹이 부족 세계(공급 상한 < 기초 수요, `daynight_v2.is_food_scarce`)는 판정 칸에서 빼고 따로 적는다(R10 과 같은 규칙).
판정 규칙은 `judge` 와 PREREG 2절이다. 결과: <out>/rounds/<회차>.json, <out>/report.json·report.md.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import env.torch_init  # noqa: F401
from env.config import ROOT
from env_v2 import rollout as ro
from env_v2.config import load_v2_config

import daynight_v2 as dnv
from diagnose_v2 import clean, config_digest, model_fingerprint

ON = ROOT / "configs" / "v2_4_on.yaml"
REF = ROOT / "configs" / "v2_1.yaml"
E1B = ROOT / "results" / "v2" / "e1" / "B1" / "r2_5_ew0_5" / "constsearch_seg.json"
FIX_MODEL = ROOT / "ckpt" / "v2" / "s1a_g_s58.zip"
GAMMA = 0.9916661555611042
SEEDS = list(range(20000, 20020))
STEPS = 30000
POLICIES = ("C2", "CSEG", "FIX", "C2F", "CSTOP")
WORLDS = ("on", "rest0", "ref")
COLS = ("starve_share", "starve_rate", "pred_rate_day", "pred_rate_night", "pred_rate_twi", "intake_day",
        "intake_night", "frac_day", "frac_night", "starve_rate_day", "starve_rate_night", "n1", "n5p",
        "p_stop_day", "p_stop_night", "p_cover_day", "p_cover_night", "hungry_frac", "survival", "g_gamma",
        "dn_period", "mean_return")
SAFETY = {"CSEG": 0.30, "FIX": 0.40}     # 안전 항목 상한 (E1 (a) 상한, Gate F (d))
SAFETY_REL = 0.05                       # 기준 세계가 이미 상한을 넘으면: on − ref ≤ 0.05


def policy_specs() -> dict:
    d = json.loads(E1B.read_text(encoding="utf-8"))
    c2 = [float(x) for x in d["base_action"]]
    seg = {"policy": {"kind": "fixed", "action": c2},
           "wrap": [{"kind": "seg_const", "bins": d["bins"], "dims": d["dims"],
                     "table": [x for row in d["best_table"] for x in row]}]}
    fix = dnv.take7({"kind": "learned", "model": str(FIX_MODEL)})
    c2f = list(c2)
    c2f[2] = 1.0
    cstop = list(c2)
    cstop[4] = 0.0
    return {"C2": {"kind": "fixed", "action": c2}, "CSEG": seg, "FIX": fix,
            "C2F": {"kind": "fixed", "action": c2f}, "CSTOP": {"kind": "fixed", "action": cstop}}


def apply_sets(cfg, sets):
    """'daynight.key=value' 덮기. 값은 yaml 숫자로 읽는다."""
    import yaml

    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for s in sets or []:
        key, _, val = s.partition("=")
        feat, _, k = key.partition(".")
        if feat not in f or k not in f[feat]:
            raise SystemExit(f"--set {s!r}: features.{feat}.{k} 가 없다")
        f[feat][k] = yaml.safe_load(val)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def worlds(sets) -> dict:
    on = apply_sets(load_v2_config(ON), sets)
    f = {k: dict(v) for k, v in on.v2["features"].items()}
    f["daynight"]["rest_night"] = 0.0
    rest0 = on.replace(v2=dict(on.v2, features=f))
    return {"on": on, "rest0": rest0, "ref": load_v2_config(REF)}


def cmd_run(a) -> int:
    out = Path(a.out)
    (out / "rounds").mkdir(parents=True, exist_ok=True)
    W = worlds(a.set)
    specs = policy_specs()
    if a.policies:
        specs = {k: v for k, v in specs.items() if k in a.policies}
    seeds = [int(s) for s in a.seeds] if a.seeds else SEEDS
    scarce = {}
    for s in seeds:
        sc, sup, need = dnv.is_food_scarce(W["on"], s)
        scarce[s] = dict(scarce=bool(sc), supply=sup, need=need)
    t0 = time.time()
    ex = ro.make_executor(a.workers)
    rows = {}
    try:
        for wn in WORLDS:
            if wn == "rest0" and a.skip_rest0:
                continue
            got = ro.run_specs(W[wn], specs, seeds, a.steps, gamma=GAMMA, executor=ex)
            rows[wn] = {pn: [clean(ro.public_row(r)) for r in rr] for pn, rr in got.items()}
            print(f"[{time.time() - t0:7.1f}s] {wn} 끝", flush=True)
    finally:
        if ex is not None:
            ex.shutdown()
    meta = dict(round=a.round, created=datetime.now(timezone.utc).isoformat(timespec="seconds"), sets=a.set or [],
                seeds=seeds, steps=a.steps, gamma=GAMMA, elapsed_s=round(time.time() - t0, 1),
                digests={k: config_digest(v) for k, v in W.items()},
                daynight={k: v for k, v in W["on"].v2["features"]["daynight"].items()},
                fix_model=str(FIX_MODEL.relative_to(ROOT)), fix_sha1=model_fingerprint(FIX_MODEL),
                note=a.note or "")
    res = dict(meta=meta, scarce={str(k): v for k, v in scarce.items()}, rows=rows)
    (out / "rounds" / f"{a.round}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    j = judge(res)
    print(json.dumps(j["verdict"], ensure_ascii=False, indent=1))
    return 0


def _t_crit(df: int) -> float:
    from scipy.stats import t

    return float(t.ppf(0.975, df))


def _paired(x) -> dict:
    x = np.asarray([v for v in x if v == v], dtype=np.float64)
    n = len(x)
    if n < 2:
        return dict(n=n, mean=float("nan"), t=float("nan"), crit=float("nan"))
    sd = float(x.std(ddof=1))
    t = float(x.mean() / (sd / math.sqrt(n))) if sd > 0 else (math.inf if x.mean() > 0 else -math.inf)
    return dict(n=n, mean=float(x.mean()), sd=sd, t=t, crit=_t_crit(n - 1))


def _col(res, wn, pn, c, seeds):
    by = {r["seed"]: r for r in res["rows"][wn][pn]}
    return np.array([by[s].get(c, float("nan")) for s in seeds], dtype=np.float64)


def judge(res) -> dict:
    """PREREG 2절 판정. 판정 칸은 먹이 부족이 아닌 시드다. 안전 항목만 막고 (a1) 은 보정 대상, (a2)·(a3) 실패 항은 #21 로 뺀다."""
    seeds = [int(s) for s in res["meta"]["seeds"]]
    judged = [s for s in seeds if not res["scarce"][str(s)]["scarce"]]
    scarce = [s for s in seeds if res["scarce"][str(s)]["scarce"]]
    out = dict(judged_seeds=judged, scarce_seeds=scarce, items={})
    it = out["items"]
    for pn, cap in SAFETY.items():
        on = _col(res, "on", pn, "starve_share", judged)
        ref = _col(res, "ref", pn, "starve_share", judged)
        m_on, m_ref = float(np.nanmean(on)), float(np.nanmean(ref))
        ok = m_on <= cap or (m_ref > cap and m_on - m_ref <= SAFETY_REL)
        it[f"safety_{pn}"] = dict(on=m_on, ref=m_ref, cap=cap, pass_=bool(ok),
                                  rule=f"아사 비중 평균 ≤ {cap} (기준 세계가 이미 넘으면 on − ref ≤ {SAFETY_REL})")
    if res["meta"]["round"] == "final":
        out["verdict"] = dict(safety=bool(it["safety_CSEG"]["pass_"] and it["safety_FIX"]["pass_"]), a1=None, a2=None,
                              a3=None, prune=[], note="final 회차는 가지치기한 설정의 안전 항목만 본다(PREREG 2절)")
        return out
    for pn in [p for p in POLICIES if p in res["rows"]["on"]]:
        d = _col(res, "on", pn, "pred_rate_night", judged) - _col(res, "on", pn, "pred_rate_day", judged)
        it[f"a1_{pn}"] = dict(**_paired(d), rule="밤 − 낮 피식률 > 0, 짝 t > 임계(양측 0.05)")
        it[f"a1_{pn}"]["pass_"] = bool(it[f"a1_{pn}"]["mean"] > 0 and it[f"a1_{pn}"]["t"] > it[f"a1_{pn}"]["crit"])
        fn, fd = _col(res, "on", pn, "frac_night", judged), _col(res, "on", pn, "frac_day", judged)
        inn, ind = _col(res, "on", pn, "intake_night", judged), _col(res, "on", pn, "intake_day", judged)
        ratio = float((np.nansum(inn * fn) / np.nansum(fn)) / (np.nansum(ind * fd) / np.nansum(fd)))
        it[f"a2_{pn}"] = dict(ratio=ratio, pass_=bool(ratio <= 0.8), rule="밤/낮 개체-스텝당 섭취(합친 값) ≤ 0.8")
        if "rest0" in res["rows"]:
            d3 = _col(res, "on", pn, "starve_rate", judged) - _col(res, "rest0", pn, "starve_rate", judged)
            p = _paired(d3)
            it[f"a3_{pn}"] = dict(**p, rule="아사율(on) − 아사율(휴식 할인 끔) < 0, 짝 t < −임계",
                                  pass_=bool(p["mean"] < 0 and p["t"] < -p["crit"]))
    def _ok(k):
        return bool(it[k]["pass_"]) if k in it else None       # 그 회차에서 돌리지 않은 정책의 항목은 None

    v = dict(safety=bool(it["safety_CSEG"]["pass_"] and it["safety_FIX"]["pass_"]),
             a1=_ok("a1_C2F"), a2=_ok("a2_C2"), a3=_ok("a3_CSTOP"))
    v["prune"] = [k for k, ok in (("eat_night", v["a2"]), ("rest_night", v["a3"])) if ok is False]
    out["verdict"] = v
    return out


def _fmt(x, nd=4):
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "통과" if x else "실패"
    if isinstance(x, float):
        return "nan" if x != x else f"{x:.{nd}g}" if abs(x) < 1e-3 else f"{x:.{nd}f}"
    return str(x)


def cmd_report(a) -> int:
    out = Path(a.out)
    rounds = sorted((out / "rounds").glob("*.json"), key=lambda p: json.loads(p.read_text(encoding="utf-8"))
                    ["meta"]["created"])
    allj, L = {}, ["# v2.4 환경 확인 N (자동 생성)", ""]
    L.append("사전 등록 `PREREG.md` 2절. 판정 칸 = 먹이 부족이 아닌 보정 시드. 정책: C2(E1-b 최적 상수), CSEG(E1-b C2-seg),"
             " FIX(s1a_g_s58 결정, 관측 앞 7칸), C2F(C2·flee_dist 1), CSTOP(C2·늘 정지). 세계: on(판정), rest0(휴식 할인 끔),"
             " ref(v2.1).")
    L.append("")
    L.append("| 회차 | 덮기 | 안전(CSEG·FIX) | (a1) C2F | (a2) C2 | (a3) CSTOP | 뺄 항(#21) |")
    L.append("|---|---|---|---|---|---|---|")
    for p in rounds:
        res = json.loads(p.read_text(encoding="utf-8"))
        j = judge(res)
        allj[res["meta"]["round"]] = dict(meta=res["meta"], scarce=res["scarce"], judge=j)
        v, it = j["verdict"], j["items"]
        if "note" in v:                       # final 회차(안전 항목만)
            L.append(f"| {res['meta']['round']} | {', '.join(res['meta']['sets']) or '—'} | {_fmt(v['safety'])} | — | — | — "
                     f"| (안전 항목만) |")
            continue
        L.append(f"| {res['meta']['round']} | {', '.join(res['meta']['sets']) or '—'} | {_fmt(v['safety'])} | "
                 f"{_fmt(v['a1'])} (t {_fmt(it.get('a1_C2F', {}).get('t'), 3)}) | {_fmt(v['a2'])} "
                 f"({_fmt(it.get('a2_C2', {}).get('ratio'), 3)}) | "
                 f"{_fmt(v['a3'])} (t {_fmt(it.get('a3_CSTOP', {}).get('t'), 3)}) | {', '.join(v['prune']) or '없음'} |")
    for name, rec in allj.items():
        j, m = rec["judge"], rec["meta"]
        L += ["", f"## {name}", "",
              f"- 만든 때 {m['created']}, {len(m['seeds'])}시드 × {m['steps']}스텝, {m['elapsed_s']}초. 설정 digest {m['digests']}.",
              f"- 판정 시드 {len(j['judged_seeds'])}개, 먹이 부족 시드(판정 제외) {j['scarce_seeds']}.", "",
              "| 항목 | 값 | 규칙 | 결과 |", "|---|---|---|---|"]
        for k, it in j["items"].items():
            val = ", ".join(f"{kk} {_fmt(vv, 4)}" for kk, vv in it.items() if kk not in ("rule", "pass_"))
            L.append(f"| {k} | {val} | {it['rule']} | {_fmt(it['pass_'])} |")
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(allj, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(L[:12]))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--round", required=True)
    r.add_argument("--out", default="results/v2/v2_4/gate_n")
    r.add_argument("--set", nargs="*", default=None, help="daynight.key=value 덮기")
    r.add_argument("--seeds", nargs="*", default=None)
    r.add_argument("--steps", type=int, default=STEPS)
    r.add_argument("--workers", type=int, default=16)
    r.add_argument("--skip-rest0", action="store_true")
    r.add_argument("--policies", nargs="*", default=None, help="정책 일부만 (final 회차는 안전 항목 CSEG·FIX)")
    r.add_argument("--note", default=None)
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.add_argument("--out", default="results/v2/v2_4/gate_n")
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
