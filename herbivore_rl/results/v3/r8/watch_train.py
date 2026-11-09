"""R8 본 학습 지켜보기 — 밤새 사람 없이 돌며 진행·이상 신호·체크포인트 점검을 스스로 남긴다 (설계 9-3·11절, STATUS.md).

`herbivore_rl/` 에서 (PYTHONUTF8=1):
    python results/v3/r8/watch_train.py                 # 기본: r8_p_s0·s1·s2·r8_h0_s0, 목표 250M, 5 분마다
    python results/v3/r8/watch_train.py --once          # 한 번만 보고 끝 (아침 확인용 — 점검 평가는 돌리지 않는다)
띄우기는 `launch_watch.ps1`(셸과 떨어진 프로세스).

하는 일 (--interval 마다):
1. `logs/progress.md` 를 새로 쓴다: 실행마다 최근 기록(결정·진행 %·속도·예상 끝·잡힘·굶음·번식·먹음·뛰기·은신처 안·도망 늑대/짐승),
   살아 있는지, 9-3·16-3 이상 신호, 25%·50%·75%·100% 지점의 기록(학습 기록 jsonl 에서 그 지점을 처음 넘은 줄).
2. 체크포인트 점검: 모든 실행이 `ckpt/r8/<이름>_<k>m.zip` 을 가졌거나(끝났거나 죽어서 못 닿으면 뺀다) 끝 모델이 다 나오면, 점검 시드
   41800~41839(설계 11절 — 학습 중 곡선 점검에만 쓰는 범위) 에서 `eval_r8.py eval --baselines always_eat` 를 낮은 우선순위로 돌려
   `checkpoints/m<k>/summary.md`·`summary.json`(끝 모델은 `checkpoints/final/`) 에 남긴다. 판정이 아니다(판정은 평가 시드 41900~41999, 아침).
   기본 k = 10·30(9-3 의 10M·30M)·60·120·190(목표 250M 의 약 25%·50%·75%).
3. 점검이 끝날 때마다 `plot_curve.py curve` 로 `checkpoints/curve.png` 를 다시 그린다.
4. 사건(점검 시작·끝·실패, 실행 끝·죽음)은 `logs/watch_events.log` 에 덧붙인다.

모든 실행이 끝나고(또는 죽고) 점검을 다 마치면, 또는 --max-hours 가 지나면 멈춘다. 학습 프로세스는 읽기만 한다(멈추거나 죽이지 않는다).
평가 시드 41900~41999 는 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
CKPT = ROOT / "ckpt" / "r8"
LOGS = HERE.parent / "logs"
PY = sys.executable

DEFAULT_RUNS = ["r8_p_s0", "r8_p_s1", "r8_p_s2", "r8_h0_s0"]
# 보정 관문 때(개발 시드 41400~41449, 고친 세계 `calib/calibrate_review.json`) ALWAYS_EAT 값 — 16-3 의 읽는 법(첫 1M 대신 이 값을 기준으로)
AE_CALIB = dict(caught_1k=1.019, eaten_x1000=7.909, repro_1k=14.905)
STALE_MIN = 45.0                                    # 이만큼 기록이 없고 끝 기록도 없으면 '멈춤?' 신호
EVENTS = LOGS / "watch_events.log"                  # main 이 --progress 옆으로 옮긴다


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def now_s() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_rows(run: str) -> list[dict]:
    p = LOGS / f"{run}.log.jsonl"
    rows = []
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass                                    # 쓰는 중인 마지막 줄
    return rows


def read_pids() -> dict:
    """logs/pids.txt → {실행: (python_pid, 시작 시각)} (같은 이름이 여럿이면 마지막)."""
    out = {}
    p = LOGS / "pids.txt"
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        m = re.match(r"^train (\S+) cmd_pid \d+ python_pid (\d*) log \S+ started (\S+)", line.strip())
        if m:
            out[m.group(1)] = (int(m.group(2)) if m.group(2) else None, m.group(3))
    return out


def started_at(run: str, pids: dict) -> datetime | None:
    log = LOGS / f"train_{run}.log"
    if log.exists():
        with log.open(encoding="utf-8", errors="replace") as f:
            m = re.search(r"시작 (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", f.readline())
        if m:
            return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    if run in pids:
        try:
            return datetime.fromisoformat(pids[run][1])
        except ValueError:
            return None
    return None


def alive(run: str, pids: dict):
    """True/False, 모르면 None. PID 재사용을 막으려고 명령줄에 실행 이름이 있는지 본다."""
    if run not in pids or pids[run][0] is None:
        return None
    try:
        import psutil
    except ImportError:
        return None
    pid = pids[run][0]
    if not psutil.pid_exists(pid):
        return False
    try:
        pr = psutil.Process(pid)
        return run in " ".join(pr.cmdline())
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    except psutil.AccessDenied:
        return None


def final_meta(run: str) -> dict | None:
    p = CKPT / f"{run}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def fmt(x, nd=2) -> str:
    if x is None:
        return "—"
    if isinstance(x, float) and not math.isfinite(x):
        return str(x)
    return f"{x:.{nd}f}"


def flags_for(rows: list[dict], fin: dict | None, alv, log_age_min: float | None) -> list[str]:
    fl = []
    if any(r.get("nan") for r in rows) or (fin and fin.get("stop") == "nan"):
        fl.append("NaN 멈춤")
    if rows:
        r = rows[-1]
        n = r.get("timesteps", 0)
        if n >= 5_000_000 and r.get("act_run", 0) > 0.6:
            fl.append("늘 뜀(뛰기 > 0.6)")
        if n >= 5_000_000 and r.get("in_shelter", 0) > 0.6 and r.get("eaten_e_x1000", 0) < 0.5 * AE_CALIB["eaten_x1000"]:
            fl.append("늘 숨음(은신처 안 > 0.6·먹음 < 늘 먹기 절반)")
        if n >= 10_000_000 and r.get("caught_per_1k", 0) > 0.8 * AE_CALIB["caught_1k"]:
            fl.append("잡힘 안 줄어듦(> 늘 먹기 × 0.8)")
    if fin is None:
        if alv is False:
            fl.append("프로세스 없음·끝 기록 없음(죽었을 수 있다)")
        elif log_age_min is not None and log_age_min > STALE_MIN:
            fl.append(f"기록 {log_age_min:.0f}분째 없음")
    elif fin.get("stop") == "wall_clock":
        fl.append("벽시계 상한에서 멈춤(목표 못 닿음)")
    return fl


def run_status(run: str, target: int, wall_h: float, pids: dict) -> dict:
    rows = read_rows(run)
    fin = final_meta(run)
    alv = alive(run, pids)
    st = started_at(run, pids)
    lp = LOGS / f"{run}.log.jsonl"
    log_age = (time.time() - lp.stat().st_mtime) / 60.0 if lp.exists() else None
    if log_age is None and st is not None:
        log_age = (datetime.now() - st).total_seconds() / 60.0
    n = int(fin["timesteps"]) if fin else (int(rows[-1]["timesteps"]) if rows else 0)
    rate = float(rows[-1]["dec_per_s"]) if rows else None
    if fin:
        rate = float(fin.get("dec_per_s", rate or 0))
    eta = None
    if fin:
        try:
            eta = datetime.strptime(fin["finished"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, ValueError):
            eta = None
    elif rate and st is not None:
        eta = datetime.now() + timedelta(seconds=max(target - n, 0) / rate)
        eta = min(eta, st + timedelta(hours=wall_h))
    return dict(run=run, rows=rows, fin=fin, alive=alv, started=st, n=n, rate=rate, eta=eta, log_age=log_age,
                flags=flags_for(rows, fin, alv, log_age))


# --------------------------------------------------------------------------- #
# 체크포인트 점검
# --------------------------------------------------------------------------- #
def ckpt_ready(p: Path) -> bool:
    return p.exists() and (time.time() - p.stat().st_mtime) > 30.0   # 쓰는 중인 zip 을 읽지 않는다


def milestone_state(key: str, runs: list[str], status: dict) -> tuple[str, list[str]]:
    """('wait'|'ready'|'skip', 모델 경로들). key = 'm010' 꼴 또는 'final'."""
    models, waiting = [], False
    for run in runs:
        s = status[run]
        gone = s["fin"] is not None or s["alive"] is False
        if key == "final":
            p = CKPT / f"{run}.zip"
            if s["fin"] is not None and ckpt_ready(p):
                models.append(f"ckpt/r8/{run}.zip")
            elif not gone:
                waiting = True
        else:
            k = int(key[1:])
            p = CKPT / f"{run}_{k}m.zip"
            if ckpt_ready(p):
                models.append(f"ckpt/r8/{run}_{k}m.zip")
            elif not gone:
                waiting = True
    if waiting:
        return "wait", models
    return ("ready" if models else "skip"), models


def event(msg: str) -> None:
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(f"{now_s()} {msg}\n")
    print(f"{now_s()} {msg}", flush=True)


def run_check(key: str, models: list[str], args) -> str:
    out = Path(args.out) / key
    out.mkdir(parents=True, exist_ok=True)
    cmd = [PY, str(HERE.parent / "eval_r8.py"), "eval", "--config", args.config, "--models", *models, "--baselines", "always_eat",
           "--seeds", str(args.seeds[0]), str(args.seeds[1]), "--steps", str(args.steps), "--out", str(out)]
    env = dict(os.environ, PYTHONUTF8="1")
    flags = 0
    if os.name == "nt":
        flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW
    t0 = time.time()
    event(f"점검 시작 {key}: {' '.join(Path(m).stem for m in models)}")
    with (out / "eval.log").open("w", encoding="utf-8") as lf:
        try:
            r = subprocess.run(cmd, cwd=ROOT, env=env, stdout=lf, stderr=subprocess.STDOUT, creationflags=flags, timeout=args.check_timeout_h * 3600)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    mins = (time.time() - t0) / 60.0
    sm = out / "summary.md"
    if rc == 0 and sm.exists():
        txt = sm.read_text(encoding="utf-8")
        note = (f"> 학습 중 체크포인트 점검 `{key}` — 점검 시드 {args.seeds[0]}~{args.seeds[1]}(설계 11절), 판정 아님. "
                f"판정은 아침 평가 시드 41900~41999 의 마지막 모델로 한다. `watch_train.py` 가 {now_s()} 에 남김.\n\n")
        sm.write_text(note + txt, encoding="utf-8")
        event(f"점검 끝 {key} ({mins:.1f}분) → {rel(sm)}")
        return "done"
    (out / "failed.txt").write_text(f"{now_s()} 반환 {rc}\n", encoding="utf-8")
    event(f"점검 실패 {key} (반환 {rc}, {mins:.1f}분) — {rel(out)}/eval.log")
    return "failed"


def check_rows(out_dir: Path, keys: list[str]) -> list[str]:
    L = []
    for key in keys:
        p = out_dir / key / "summary.json"
        if not p.exists():
            continue
        try:
            js = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for lab, m in js.get("results", {}).items():
            if lab == "ALWAYS_EAT":
                continue
            v = js.get("verdict", {}).get(lab, {})
            hw = m.get("extra", {}).get("hunting_wolf_vs_beast", {})
            ci = m.get("delta_ci") or [float("nan"), float("nan")]
            pp = "/".join(("O" if v.get(x) else "X") for x in ("P1", "P2", "P3")) if v else "—"
            L.append(f"| {key} | {lab} | {fmt(v.get('caught_ratio'))} | {fmt(v.get('eaten_ratio'))} | {fmt(m.get('starved_1k'), 3)} | "
                     f"{fmt(m.get('delta'), 3)} [{fmt(ci[0], 3)}, {fmt(ci[1], 3)}] | {fmt(m.get('rho'))} | {fmt(hw.get('delta'), 3)} | "
                     f"{fmt(m.get('act_run'))} | {pp} |")
    return L


def pct_rows(s: dict, target: int) -> list[str]:
    L = []
    for pct in (25, 50, 75, 100):
        hit = next((r for r in s["rows"] if r.get("timesteps", 0) >= pct / 100.0 * target), None)
        if hit is None:
            continue
        when = (s["started"] + timedelta(minutes=float(hit.get("wall_min", 0)))).strftime("%H:%M") if s["started"] else "?"
        L.append(f"| {s['run']} | {pct}% | {hit['timesteps'] / 1e6:.0f}M | {when} | {fmt(hit.get('caught_per_1k'))} | {fmt(hit.get('repro_per_1k'))} | "
                 f"{fmt(hit.get('eaten_e_x1000'))} | {fmt(hit.get('act_run'))} | {fmt(hit.get('flee_wolf'))} / {fmt(hit.get('flee_beast'))} |")
    return L


def write_progress(args, status: dict, keys: list[str], states: dict, t_start: datetime) -> None:
    L = [f"# R8 본 학습 진행 (`watch_train.py` 가 {args.interval / 60:.0f} 분마다 고쳐 쓴다)", "",
         f"- 고친 때 **{now_s()}** (지켜보기 시작 {t_start:%Y-%m-%d %H:%M:%S}). 목표 {args.target / 1e6:.0f}M 결정/두뇌, 벽시계 상한 {args.wall_hours} 시간.",
         "- 값은 학습 세계(시드 41100~41399) 의 최근 기록 구간(5M) 값이다. 잡힘·굶음·번식 1000 사슴-스텝당, 먹음 사슴-스텝당 × 1000,",
         "  도망 몫 = 가장 가까운 느낀 동물이 늑대/짐승이고 15 단위 안일 때 뛰기·은신처를 고른 몫(숨은 종류는 기록에만 쓴다).",
         f"- 신호 기준(설계 9-3·16-3): 보정 때 늘 먹기 잡힘 {AE_CALIB['caught_1k']}·먹음 {AE_CALIB['eaten_x1000']}·번식 {AE_CALIB['repro_1k']} (개발 시드).", "",
         "| 실행 | 결정 | 진행 | 결정/초 | 예상 끝 | 잡힘/1k | 굶음/1k | 번식/1k | 먹음×1000 | 뛰기 | 은신처 안 | 도망 늑대 / 짐승 | 살아 있음 | 신호 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for run, s in status.items():
        r = s["rows"][-1] if s["rows"] else {}
        alive_s = "끝" if s["fin"] else {True: "예", False: "아니오", None: "?"}[s["alive"]]
        eta = s["eta"].strftime("%m-%d %H:%M") if s["eta"] else "—"
        L.append(f"| {run} | {s['n'] / 1e6:.1f}M | {100.0 * s['n'] / args.target:.0f}% | {fmt(s['rate'], 0)} | {eta}{' (끝남)' if s['fin'] else ''} | "
                 f"{fmt(r.get('caught_per_1k'))} | {fmt(r.get('starved_per_1k'))} | {fmt(r.get('repro_per_1k'))} | {fmt(r.get('eaten_e_x1000'))} | "
                 f"{fmt(r.get('act_run'))} | {fmt(r.get('in_shelter'))} | {fmt(r.get('flee_wolf'))} / {fmt(r.get('flee_beast'))} | {alive_s} | "
                 f"{'; '.join(s['flags']) if s['flags'] else '없음'} |")
    L += ["", "## 25%·50%·75%·100% 지점 (그 지점을 처음 넘은 학습 기록 줄)", "",
          "| 실행 | 지점 | 결정 | 시각 | 잡힘/1k | 번식/1k | 먹음×1000 | 뛰기 | 도망 늑대 / 짐승 |", "|---|---|---|---|---|---|---|---|---|"]
    for s in status.values():
        L += pct_rows(s, args.target)
    L += ["", f"## 체크포인트 점검 (점검 시드 {args.seeds[0]}~{args.seeds[1]}, {args.seeds[1] - args.seeds[0] + 1} 세계 × {args.steps} 스텝, 결정적 행동 — 판정 아님)", "",
          "- 잡힘 비·먹음 비 = 같은 점검 세계의 늘 먹기 대비. Δ = 늑대일 때 도망 몫 − 짐승일 때(거리 띠 맞춤), [95% 구간]. ρ = 비.",
          "  P1 잡힘 비 ≤ 0.5, P2 먹음 비 ≥ 0.7·굶음 ≤ 0.1, P3 Δ 아래 끝 > 0·ρ ≥ 1.5 (O 통과 / X 못 넘음 — 기준만 같고 세계는 점검 세계).", "",
          "| 체크포인트 | 두뇌 | 잡힘 비 | 먹음 비 | 굶음/1k | Δ [95%] | ρ | 사냥 중 늑대 대 짐승 Δ | 뛰기 | P1/P2/P3 |", "|---|---|---|---|---|---|---|---|---|---|"]
    L += check_rows(Path(args.out), keys)
    L += ["", "점검 상태: " + ", ".join(f"{k} {states.get(k, 'wait')}" for k in keys), ""]
    ev = EVENTS
    if ev.exists():
        L += ["## 사건 (최근 20 줄, 전체는 `logs/watch_events.log`)", "", "```"]
        L += ev.read_text(encoding="utf-8").splitlines()[-20:]
        L += ["```", ""]
    p = Path(args.progress)
    tmp = p.with_suffix(".md.tmp")
    tmp.write_text("\n".join(L) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def redraw(args) -> None:
    try:
        sys.path.insert(0, str(HERE.parent))
        import plot_curve
        plot_curve.draw_curve(args.runs, Path(args.out), Path(args.out) / "curve.png", target=args.target)
    except Exception as e:  # noqa: BLE001 — 그림이 안 돼도 지켜보기는 이어 간다
        event(f"곡선 그림 실패: {type(e).__name__}: {e}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="*", default=DEFAULT_RUNS)
    ap.add_argument("--target", type=int, default=250_000_000)
    ap.add_argument("--wall-hours", type=float, default=10.0)
    ap.add_argument("--milestones", nargs="*", type=int, default=[10, 30, 60, 120, 190], help="점검할 체크포인트 (M 결정)")
    ap.add_argument("--no-final", action="store_true", help="끝 모델 점검을 하지 않는다")
    ap.add_argument("--config", default="configs/v3_r8_pilot.yaml")
    ap.add_argument("--seeds", nargs=2, type=int, default=[41800, 41839])
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--interval", type=float, default=300.0, help="초")
    ap.add_argument("--max-hours", type=float, default=12.0)
    ap.add_argument("--check-timeout-h", type=float, default=2.0)
    ap.add_argument("--out", default=str(HERE.parent / "checkpoints"))
    ap.add_argument("--progress", default=str(LOGS / "progress.md"))
    ap.add_argument("--once", action="store_true", help="진행표만 한 번 쓰고 끝 (점검 평가는 돌리지 않는다)")
    args = ap.parse_args(argv)
    if 41900 <= args.seeds[1] and args.seeds[0] <= 41999:
        print("평가 시드 41900~41999 는 판정 전에 쓰지 않는다 (설계 8-1)", flush=True)
        return 2

    global EVENTS
    EVENTS = Path(args.progress).parent / "watch_events.log"
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    keys = [f"m{k:03d}" for k in args.milestones] + ([] if args.no_final else ["final"])
    t_start = datetime.now()
    if not args.once:
        event(f"지켜보기 시작 (pid {os.getpid()}): 실행 {' '.join(args.runs)}, 점검 {' '.join(keys)}, 시드 {args.seeds[0]}~{args.seeds[1]}")
    states = {k: ("done" if (Path(args.out) / k / "summary.json").exists() else "wait") for k in keys}
    reported = set()
    while True:
        pids = read_pids()
        status = {run: run_status(run, args.target, args.wall_hours, pids) for run in args.runs}
        if not args.once:
            for run, s in status.items():
                if s["fin"] is not None and ("fin", run) not in reported:
                    reported.add(("fin", run))
                    event(f"실행 끝 {run}: {s['n'] / 1e6:.2f}M 결정, 멈춤 {s['fin'].get('stop')}, {s['fin'].get('finished')}")
                elif s["fin"] is None and s["alive"] is False and ("dead", run) not in reported:
                    reported.add(("dead", run))
                    event(f"실행 {run}: 프로세스가 없고 끝 기록도 없다 (마지막 {s['n'] / 1e6:.1f}M)")
        write_progress(args, status, keys, states, t_start)
        if args.once:
            print((Path(args.progress)).read_text(encoding="utf-8"))
            return 0
        for key in keys:
            if states[key] != "wait":
                continue
            st, models = milestone_state(key, args.runs, status)
            if st == "skip":
                states[key] = "skip"
                event(f"점검 건너뜀 {key}: 닿은 실행이 없다")
            elif st == "ready":
                states[key] = run_check(key, models, args)
                redraw(args)
                write_progress(args, status, keys, states, t_start)
        all_gone = all(s["fin"] is not None or s["alive"] is False for s in status.values())
        if all_gone and all(v != "wait" for v in states.values()):
            redraw(args)
            write_progress(args, {run: run_status(run, args.target, args.wall_hours, read_pids()) for run in args.runs}, keys, states, t_start)
            event("지켜보기 끝: 모든 실행이 끝났고 점검을 마쳤다")
            return 0
        if (datetime.now() - t_start).total_seconds() > args.max_hours * 3600:
            event(f"지켜보기 끝: --max-hours {args.max_hours} 지남")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
