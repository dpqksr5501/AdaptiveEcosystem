"""v3 R7 본 학습 2M·5M 점검을 학습 결과가 생기는 대로 돌린다 (사전 등록 PREREG.md 5절 — 판정 아님. 학습 프로세스를 건드리지 않는다).

    # herbivore_rl/ 에서 (launch_train.ps1 -Checks 가 함께 띄운다 — STATUS.md)
    python results/v3/r7/early_checks.py --seeds 0 1 2 --control --at 2 5          # → logs/check_<s시드|off>_<k>m.txt · logs/early_main.json
    # 도구 확인(판정 아님 — 스모크 시드·짧은 길이, 체크포인트·기록은 임시 폴더)
    python results/v3/r7/early_checks.py --seeds 0 --control --at 2 5 --ckpt-dir <임시>/ck --smoke 32080-32082 --smoke-steps 300 --out-dir <임시>/ec

R6(results/v3/r6/early_checks.py)와 달리 조기 점검 6 조합(combos)은 없다 — λ 0.98 · 도주 비용 0 은 R6 조기 점검이 고른 값으로 고정했다(PREREG 3절).
체크포인트 ckpt/v3/v3_r7_g995_s<시드>_20m_<k>m.zip(대조 --control 이면 v3_r7off_g995_s0_20m_<k>m.zip 도)마다
  r7_eval run --use check --probe (점검 시드 38120~38139 × 지역 셋 × N 1800 스텝) → r7_eval.early_check(기준 판 = route0 같은 시드 runs/early_base.json,
  (b) 의 수익 목표 = λ 0.98 λ-수익, (c) 에 GF·GR) → logs/check_<이름>_<k>m.txt, 모음 logs/early_main.json(r7_eval.main_check_rules — 제외 시드·전체 멈춤).
  대조 줄은 보고만이다(제외·멈춤에 쓰지 않는다).
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

import r7_eval as E  # noqa: E402

LOGS = HERE.parent / "logs"


def wait_done(model: Path, timeout_s: float) -> bool:
    """체크포인트 파일 크기가 두 번(10 초 사이) 같을 때까지 기다린다(r6 early_checks.wait_done 의 체크포인트 갈래와 같다)."""
    t0, last = time.time(), -1
    while time.time() - t0 < timeout_s:
        if model.exists():
            n = model.stat().st_size
            if n > 0 and n == last:
                return True
            last = n
        time.sleep(10)
    return False


def _write(logs: Path, name: str, d) -> None:
    logs.mkdir(parents=True, exist_ok=True)
    (logs / name).write_text(json.dumps(E.lv.jsonable(d), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def run_name(nm: str) -> str:
    """점검 이름('s0'·'s1'·'s2'·'off') → 학습 실행 이름 (launch_train.ps1 과 같다)."""
    return "v3_r7off_g995_s0_20m" if nm == "off" else f"v3_r7_g995_{nm}_20m"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--control", action="store_true", help="대조 '길 끔' 체크포인트도 본다 (보고만)")
    ap.add_argument("--at", type=int, nargs="+", default=[2, 5], help="체크포인트(백만 스텝)")
    ap.add_argument("--workers", type=int, default=E.lv.default_workers())
    ap.add_argument("--timeout-min", type=float, default=180.0)
    ap.add_argument("--ckpt-dir", type=Path, default=E.CK)
    ap.add_argument("--smoke", default=None, help="도구 확인: 스모크 시드(32080~32099 안) — 판정 아님. --out-dir 을 함께 준다")
    ap.add_argument("--smoke-steps", type=int, default=300)
    ap.add_argument("--out-dir", type=Path, default=None, help="기록 폴더 (기본 results/v3/r7/logs, 판 파일은 results/v3/r7/runs)")
    a = ap.parse_args(argv)
    if a.smoke and a.out_dir is None:
        raise SystemExit("--smoke 는 --out-dir 을 함께 준다 (스모크 기록을 logs/ 에 쓰지 않는다)")
    plan = E.smoke_plan("check", E.R6.parse_seeds(a.smoke), a.smoke_steps) if a.smoke else None
    logs = Path(a.out_dir) if a.out_dir else LOGS
    runs_dir = (Path(a.out_dir) / "runs") if a.out_dir else E.OUT
    info = E.prepare_info(runs_dir)
    base = E.ensure_run(info, "route0", "check", a.workers, "early_base", runs_dir, probe=True, plan=plan)
    names = [f"s{s}" for s in a.seeds] + (["off"] if a.control else [])
    checks, rows = {}, {}

    def summary(at):
        return E.main_check_rules({kk: v for kk, v in checks.items() if kk[0] != "off"}, at)

    for k in a.at:
        for nm in names:
            ck = Path(a.ckpt_dir) / f"{run_name(nm)}_{k}m.zip"
            tag = f"{nm}_{k}m"
            if not wait_done(ck, a.timeout_min * 60):
                print(f"{tag}: 체크포인트 {ck.name} 가 {a.timeout_min:g}분 안에 없다 — 건너뜀", flush=True)
                rows[tag] = dict(missing=True)
                continue
            t0 = time.time()
            res = E.ensure_run(info, str(ck), "check", a.workers, f"early_{tag}", runs_dir, probe=True, plan=plan)
            r = E.early_check(res, base, E.LAM)
            text = E.fmt_check(f"{tag} ({ck.name}, {time.time() - t0:.0f}초)", r)
            logs.mkdir(parents=True, exist_ok=True)
            (logs / f"check_{tag}.txt").write_text(text + "\n", encoding="utf-8")
            print(text, flush=True)
            checks[(nm, k)] = r
            cp = r["c"]["parts"]
            rows[tag] = dict(passed=r["passed"], a=r["a"].get("ok"), b=r["b"]["ok"], c=r["c"]["ok"], defect=r["defect"]["hit"],
                             pe_shelter=r["a"].get("pe"), ev=r["b"]["ev"], hide_diff=cp["hide"]["diff"], hide_t=cp["hide"]["t"],
                             caught_ratio_t=cp["caught_ratio"]["t"], caught_t=cp["caught"]["t"], gf_diff=cp["gf"]["diff"], gf_t=cp["gf"]["t"],
                             gr_diff=cp["gr"].get("diff"), gr_t=cp["gr"].get("t"), gate_flee=r["defect"]["gate_flee"], none=r["none"])
            _write(logs, "early_main.json", dict(rows=rows, rules=summary(sorted({kk[1] for kk in checks})), lam=E.LAM, flight_cost=E.FLIGHT_COST,
                                                 smoke=a.smoke, control_note="대조 '길 끔' 줄은 보고만 (제외·멈춤에 쓰지 않는다)"))
    summ = summary(list(a.at))
    _write(logs, "early_main.json", dict(rows=rows, rules=summ, lam=E.LAM, flight_cost=E.FLIGHT_COST, smoke=a.smoke,
                                         control_note="대조 '길 끔' 줄은 보고만 (제외·멈춤에 쓰지 않는다)"))
    print(f"제외 시드: {summ['excluded'] or '없음'} · 멈춤: {'예 — ' + ' / '.join(summ['why']) if summ['stop'] else '아니오'}", flush=True)
    return 1 if summ["stop"] else 0


if __name__ == "__main__":
    sys.exit(main())
