"""v3 R6 조기 점검을 학습 결과가 생기는 대로 돌린다 (사전 등록 PREREG.md 5절 — 판정 아님. 학습 프로세스를 건드리지 않는다).

    # herbivore_rl/ 에서 (launch_train.ps1 -Checks 가 함께 띄운다 — STATUS.md)
    python results/v3/r6/early_checks.py combos                          # 조기 점검 6 조합(5M) → 고르기 → logs/early_pick.json
    python results/v3/r6/early_checks.py main --seeds 0 1 2 --control --at 2 5     # 본 학습 2M·5M 점검 → logs/early_main.json

combos: λ {95, 98} × c {0, 0027, 005} 의 끝 모델 ckpt/v3/v3_r6e_l<λ>_c<c>_s0_5m.zip(곁 메타 .json 이 생기면 학습이 끝난 것)마다
  r6_eval run --use check --probe --flight-cost <c> (점검 시드 37120~37139 × 지역 셋 × N 1800 스텝) → r6_eval.early_check(기준 판 = route0, 같은 시드,
  (b) 의 수익 목표 = 그 조합의 학습 λ)
  → logs/check_l<λ>_c<c>.txt. 여섯이 모이면 r6_eval.pick_combo(사전 등록 5-2 — 통과 조합 가운데 숨음 비율 짝 차이가 가장 큰 것, 1 %p 안이면 작은 c →
  λ 0.95)로 고르고 logs/early_pick.json·early_combos.json 을 쓴다. 멈춤이면 그 까닭을 적는다(본 학습을 띄우지 않는다 — 사람에게 보고).
main: 체크포인트 ckpt/v3/v3_r6_g995_s<시드>_20m_<k>m.zip(대조 --control 이면 v3_r6off_g995_s0_20m_<k>m.zip 도)마다 같은 점검 → logs/check_<시드>_<k>m.txt,
  모음 logs/early_main.json(r6_eval.main_check_rules — 제외 시드·전체 멈춤). 도주 비용(설명 분산의 보상)·학습 λ((b) 의 수익 목표)는
  logs/early_pick.json 의 c·λ(또는 --cost·--lam).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for p in (HERE.parent, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import r6_eval as E  # noqa: E402
from make_r6_configs import COSTS, LAMBDAS  # noqa: E402

LOGS = HERE.parent / "logs"
CK = E.CK


def wait_done(model: Path, timeout_s: float, need_meta: bool) -> bool:
    """need_meta: 학습 끝 곁 메타 <모델>.json 이 생길 때까지(끝 모델), 아니면 파일 크기가 두 번 같을 때까지(체크포인트) 기다린다."""
    t0, last = time.time(), -1
    while time.time() - t0 < timeout_s:
        if model.exists():
            if need_meta and model.with_suffix(".json").exists():
                return True
            n = model.stat().st_size
            if not need_meta and n > 0 and n == last:
                return True
            last = n
        time.sleep(10)
    return False


def _write(name: str, d) -> None:
    LOGS.mkdir(exist_ok=True)
    (LOGS / name).write_text(json.dumps(E.lv.jsonable(d), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _base(info, workers: int) -> dict:
    return E.ensure_run(info, "route0", "check", workers, "early_base", probe=True, flight_cost=0.0)


def cmd_combos(a) -> int:
    info = E.prepare_info()
    base = _base(info, a.workers)
    checks, rows = {}, {}
    for lam in LAMBDAS:
        for cost in COSTS:
            tag = f"l{lam}_c{cost}"
            ck = CK / f"v3_r6e_{tag}_s0_5m.zip"
            if not wait_done(ck, a.timeout_min * 60, True):
                print(f"{tag}: {ck.name} 학습이 {a.timeout_min:g}분 안에 끝나지 않았다 — 건너뜀", flush=True)
                rows[tag] = dict(missing=True)
                continue
            t0 = time.time()
            res = E.ensure_run(info, str(ck), "check", a.workers, f"early_{tag}", probe=True, flight_cost=COSTS[cost])
            r = E.early_check(res, base, LAMBDAS[lam])
            text = E.fmt_check(f"{tag} ({ck.name}, {time.time() - t0:.0f}초)", r)
            (LOGS / f"check_{tag}.txt").write_text(text + "\n", encoding="utf-8")
            print(text, flush=True)
            checks[(lam, cost)] = r
            rows[tag] = dict(passed=r["passed"], a=r["a"].get("ok"), b=r["b"]["ok"], c=r["c"]["ok"], defect=r["defect"]["hit"],
                             pe_shelter=r["a"].get("pe"), moved=r["a"].get("moved"), ev=r["b"]["ev"],
                             hide_diff=r["c"]["parts"]["hide"]["diff"], hide_t=r["c"]["parts"]["hide"]["t"],
                             caught_ratio_t=r["c"]["parts"]["caught_ratio"]["t"], caught_t=r["c"]["parts"]["caught"]["t"])
            _write("early_combos.json", rows)
    if len(checks) < len(LAMBDAS) * len(COSTS):
        pick = dict(stop=True, why=f"조합 {len(checks)}/{len(LAMBDAS) * len(COSTS)} 개만 점검했다 — 빠진 조합을 마저 본 뒤 고른다", pick=None)
    else:
        pick = E.pick_combo(checks)
    out = dict(pick, pick=None if pick["pick"] is None else dict(lam=pick["pick"][0], cost=pick["pick"][1],
                                                              gae_lambda=LAMBDAS[pick["pick"][0]], flight_cost=COSTS[pick["pick"][1]]),
               near=[f"l{k[0]}_c{k[1]}" for k in pick.get("near", [])], ranking=[(f"l{k[0]}_c{k[1]}", d) for k, d in pick.get("ranking", [])],
               rules=E.EARLY)
    _write("early_pick.json", out)
    if out["stop"]:
        print(f"멈춤: {out['why']}", flush=True)
        return 1
    p = out["pick"]
    print(f"고른 조합: λ {p['gae_lambda']} · c {p['flight_cost']} (l{p['lam']}_c{p['cost']}) — 가까운 조합 {out['near']}", flush=True)
    print(f"본 학습: powershell -ExecutionPolicy Bypass -File results/v3/r6/launch_train.ps1 -Phase main -Lam {p['lam']} -Cost {p['cost']} -Checks", flush=True)
    return 0


def cmd_main(a) -> int:
    cost, lam = a.cost, a.lam
    if cost is None or lam is None:
        pk = json.loads((LOGS / "early_pick.json").read_text(encoding="utf-8"))
        if pk.get("pick") is None:
            raise SystemExit("logs/early_pick.json 에 고른 조합이 없다 — --cost·--lam 을 준다")
        cost = pk["pick"]["cost"] if cost is None else cost
        lam = pk["pick"]["lam"] if lam is None else lam
    if cost not in COSTS:
        raise SystemExit(f"--cost {cost} 는 {sorted(COSTS)} 가운데 하나다")
    if lam not in LAMBDAS:
        raise SystemExit(f"--lam {lam} 는 {sorted(LAMBDAS)} 가운데 하나다")
    info = E.prepare_info()
    base = _base(info, a.workers)
    names = [f"s{s}" for s in a.seeds] + (["off"] if a.control else [])
    checks, rows = {}, {}
    for k in a.at:
        for nm in names:
            run = "v3_r6off_g995_s0_20m" if nm == "off" else f"v3_r6_g995_{nm}_20m"
            ck = CK / f"{run}_{k}m.zip"
            tag = f"{nm}_{k}m"
            if not wait_done(ck, a.timeout_min * 60, False):
                print(f"{tag}: 체크포인트 {ck.name} 가 {a.timeout_min:g}분 안에 없다 — 건너뜀", flush=True)
                rows[tag] = dict(missing=True)
                continue
            t0 = time.time()
            res = E.ensure_run(info, str(ck), "check", a.workers, f"early_{tag}", probe=True, flight_cost=COSTS[cost])
            r = E.early_check(res, base, LAMBDAS[lam])
            text = E.fmt_check(f"{tag} ({ck.name}, {time.time() - t0:.0f}초)", r)
            (LOGS / f"check_{tag}.txt").write_text(text + "\n", encoding="utf-8")
            print(text, flush=True)
            checks[(nm, k)] = r
            rows[tag] = dict(passed=r["passed"], a=r["a"].get("ok"), b=r["b"]["ok"], c=r["c"]["ok"], defect=r["defect"]["hit"],
                             pe_shelter=r["a"].get("pe"), ev=r["b"]["ev"], hide_diff=r["c"]["parts"]["hide"]["diff"],
                             hide_t=r["c"]["parts"]["hide"]["t"], caught_ratio_t=r["c"]["parts"]["caught_ratio"]["t"],
                             caught_t=r["c"]["parts"]["caught"]["t"])
            summ = E.main_check_rules({kk: v for kk, v in checks.items() if kk[0] != "off"}, sorted({kk[1] for kk in checks}))
            _write("early_main.json", dict(rows=rows, rules=summ, cost=cost, lam=lam, control_note="대조 '길 끔' 줄은 보고만 (고르기·멈춤에 쓰지 않는다)"))
    summ = E.main_check_rules({kk: v for kk, v in checks.items() if kk[0] != "off"}, list(a.at))
    _write("early_main.json", dict(rows=rows, rules=summ, cost=cost, lam=lam, control_note="대조 '길 끔' 줄은 보고만 (고르기·멈춤에 쓰지 않는다)"))
    print(f"제외 시드: {summ['excluded'] or '없음'} · 멈춤: {'예 — ' + ' / '.join(summ['why']) if summ['stop'] else '아니오'}", flush=True)
    return 1 if summ["stop"] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("combos")
    m = sub.add_parser("main")
    m.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    m.add_argument("--control", action="store_true", help="대조 '길 끔' 체크포인트도 본다 (보고만)")
    m.add_argument("--at", type=int, nargs="+", default=[2, 5], help="체크포인트(백만 스텝)")
    m.add_argument("--cost", default=None, help="도주 비용 이름 (0 · 0027 · 005) — 없으면 logs/early_pick.json")
    m.add_argument("--lam", default=None, help="학습 λ 이름 (95 · 98) — 없으면 logs/early_pick.json")
    for p in (c, m):
        p.add_argument("--workers", type=int, default=E.lv.default_workers())
        p.add_argument("--timeout-min", type=float, default=180.0)
    a = ap.parse_args(argv)
    return cmd_combos(a) if a.cmd == "combos" else cmd_main(a)


if __name__ == "__main__":
    sys.exit(main())
