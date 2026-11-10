"""R9 league watcher — writes the progress page every 5 minutes while nobody is awake (design AdaptiveEcosystem/Docs/RL_Policy/
RL_R9_MULTISPECIES_DESIGN.md 7-9, 9-5). Read-only: it never stops or starts a process.

    python results/v3/r9/watch_r9.py                  # every --interval s until the league halts (or --max-hours)
    python results/v3/r9/watch_r9.py --once           # one look (morning check)

Page `results/v3/r9/logs/progress.md`:
  - league: round · stage · halted, league process alive (pids.txt `league` line, command-line check), Unreal/UBT running, free
    commit memory, last league events.
  - runs of the current round (and the last finished ones): status, process alive, bundle decisions / target, %, speed, ETA, wall
    cap, latest learner numbers (bite / counter / starve / births per 1,000 agent-steps, eaten energy, run / shelter shares, wolf
    kills per wolf-day, E median, toward-wolf share for boar, entropy, explained variance).
  - 9-5 signals (morning reading, nothing is stopped):
      deer·boar  run share > 0.6 (늘 뜀); in-shelter share > 0.6 and eaten energy < ½ of the rule-brain value (늘 숨음 — needs
                 --baseline; without it the shelter part alone is shown as '기준 없음')
      wolf       ≥ 10M decisions and kills/wolf-day < 20% of RULE_WOLF (needs --baseline); E median < 0.2 (굶는 중)
      boar       walking toward a non-approaching wolf > 0.3 (n ≥ 100 decisions)
      any        wall-clock cap reached before the target (stop = wall_clock); NaN; no new log row for 45 min while alive;
                 process gone without its end record (the league re-runs it from the start copy)
  Rows with agent_steps = 0 (the end row that only carries the last PPO numbers) are not used for rates.
--baseline: JSON {"deer": {"eaten_e_x1000": …}, "boar": {"eaten_e_x1000": …}, "wolf": {"kills_per_wolf_day": …}} measured with rule
brains (C0 gates, eval_r9.py — not made here).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CKPT = ROOT / "ckpt" / "r9"
LOGS = HERE.parent / "logs"
STALE_MIN = 45.0
PREY = ("deer", "boar")


def now_s() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def absp(p) -> Path:
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def fmt(x, nd=2) -> str:
    if x is None:
        return "—"
    if isinstance(x, float) and not math.isfinite(x):
        return str(x)
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_rows(p: Path) -> list[dict]:
    rows = []
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass                                # line being written
    return rows


def read_pids(log_dir: Path) -> dict:
    """pids.txt → {what: (python_pid, started)} (last line per name). Lines from league_r9.py and spawn_detached.py."""
    out = {}
    p = log_dir / "pids.txt"
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        m = re.match(r"^(.+?) cmd_pid \d+ python_pid (\d*) log \S+ started (\S+)", line.strip())
        if m:
            out[m.group(1)] = (int(m.group(2)) if m.group(2) else None, m.group(3))
    return out


def alive(pid, marker: str):
    """True/False, None if unknown. Command line must carry the marker (PID reuse)."""
    if pid is None:
        return None
    try:
        import psutil
    except ImportError:
        return None
    try:
        pr = psutil.Process(int(pid))
        return marker in " ".join(pr.cmdline())
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    except psutil.AccessDenied:
        return None


def signals(row: dict | None, meta: dict | None, last_t: float | None, is_alive, base: dict, species: str) -> list[str]:
    out = []
    if meta is not None:
        if meta.get("stop") == "wall_clock":
            out.append("벽시계 상한에 닿음(목표 전)")
        if meta.get("stop") == "nan" or meta.get("error"):
            out.append(f"멈춤: {meta.get('stop')} {meta.get('error') or ''}".strip())
    if row is None:
        return out
    if row.get("nan"):
        out.append("NaN")
    if row.get("agent_steps", 0) > 0:
        if species in PREY:
            if (row.get("act_run") or 0.0) > 0.6:
                out.append(f"늘 뜀 (뛰기 몫 {row['act_run']:.2f})")
            if (row.get("in_shelter") or 0.0) > 0.6:
                b = base.get(species, {}).get("eaten_e_x1000")
                if b is None:
                    out.append(f"은신처 안 {row['in_shelter']:.2f} > 0.6 (먹음 기준 없음)")
                elif row.get("eaten_e_x1000", 0.0) < 0.5 * b:
                    out.append(f"늘 숨음 (은신처 {row['in_shelter']:.2f}, 먹음 {row['eaten_e_x1000']:.2f} < ½ × 규칙 {b:.2f})")
        if species == "wolf":
            b = base.get("wolf", {}).get("kills_per_wolf_day")
            if row.get("timesteps", 0) >= 10_000_000 and b is not None and row.get("kills_per_wolf_day", 0.0) < 0.2 * b:
                out.append(f"사냥 못 배움 (하루 잡이 {row['kills_per_wolf_day']:.3f} < 0.2 × 규칙 {b:.3f})")
            if row.get("E_median") is not None and row["E_median"] < 0.2:
                out.append(f"굶는 중 (E 중앙값 {row['E_median']:.2f})")
        if species == "boar" and (row.get("n_wolf_idle") or 0) >= 100 and (row.get("toward_wolf") or 0.0) > 0.3:
            out.append(f"늘 싸움 쪽 (안 오는 늑대 쪽으로 걷기 {row['toward_wolf']:.2f})")
    if is_alive and meta is None and last_t is not None and (time.time() - last_t) / 60.0 > STALE_MIN:
        out.append(f"멈춤? ({(time.time() - last_t) / 60.0:.0f} 분 동안 새 기록 없음)")
    return out


def last_rate_row(rows: list[dict]) -> dict | None:
    for r in reversed(rows):
        if r.get("agent_steps", 0) > 0:
            return r
    return rows[-1] if rows else None


def machine() -> str:
    parts = []
    try:
        sys.path.insert(0, str(HERE.parent))
        from league_r9 import GB, commit_free_bytes, unreal_running  # noqa: PLC0415
        ue = unreal_running()
        free = commit_free_bytes()
        parts.append(f"언리얼/UBT {', '.join(ue) if ue else '없음'}")
        parts.append(f"남은 커밋 메모리 {'모름' if free is None else f'{free / GB:.1f} GB'}")
    except Exception as e:  # noqa: BLE001
        parts.append(f"기계 상태 모름 ({e})")
    return " · ".join(parts)


def page(args, base: dict, seen: dict) -> tuple[str, bool]:
    st_path = absp(args.state)
    out_dir = absp(args.out)
    log_dir = absp(args.log_dir)
    st = read_json(st_path)
    pids = read_pids(log_dir)
    L = [f"# R9 진행 ({now_s()})", ""]
    if st is None:
        L.append(f"상태 파일 없음: {st_path} — 리그가 아직 안 떴다")
        return "\n".join(L) + "\n", False
    lg = pids.get(args.league_what)
    lg_alive = alive(lg[0], "league_r9.py") if lg else None
    L.append(f"- 리그: {st['round']} 바퀴 · {st['stage']} 묶음 · 멈춤 {st.get('halted') or '아님'} · 프로세스 "
             f"{'살아 있음' if lg_alive else ('모름' if lg_alive is None else '없음')}")
    L.append(f"- 기계: {machine()}")
    L.append("")
    L.append("| 실행 | 상태 | 프로세스 | 결정 / 목표 | % | 결정/초 | 예상 끝 | 물림 | 반격 | 굶음 | 출산 | 먹음×1e3 | 뛰기 | 은신 | 하루잡이 | E 중앙 | 늑대 쪽 | 엔트로피 | 설명 분산 |")
    L.append("|" + "---|" * 19)
    sig_lines = []
    any_alive = False
    runs = st.get("runs", {})
    cur = int(st["round"])
    names = [n for n in runs if re.search(rf"_r({cur}|{cur - 1})$", n)] or list(runs)[-6:]
    for name in names:
        rs = runs[name]
        m = re.match(r"^r9_(\w+?)_(deer|wolf|boar)_r(\d+)$", name)
        if not m:
            continue
        br, sp = m.group(1), m.group(2)
        meta = read_json(out_dir / br / f"{name}.json")
        rows = read_rows(log_dir / f"{name}.log.jsonl")
        row = last_rate_row(rows)
        last = rows[-1] if rows else None
        pid = (pids.get(f"train {name}") or (rs.get("pid"), None))[0]
        al = alive(pid, name) if rs.get("status") == "running" else False
        any_alive |= bool(al)
        last_t = None
        lp = log_dir / f"{name}.log.jsonl"
        if lp.exists():
            last_t = lp.stat().st_mtime
        target = None
        cmd_m = None
        tl = log_dir / f"train_{name}.log"
        if tl.exists():
            with tl.open(encoding="utf-8", errors="replace") as f:
                cmd_m = re.search(r"목표 ([\d.]+)M", f.readline())
        if cmd_m:
            target = float(cmd_m.group(1)) * 1e6
        dec = (meta or {}).get("timesteps") or (last or {}).get("timesteps") or 0
        tgt = (meta or {}).get("target") or target
        pct = 100.0 * dec / tgt if tgt else None
        spd = (meta or {}).get("dec_per_s") or (row or {}).get("dec_per_s")
        eta = None
        if al and spd and tgt:
            eta = datetime.fromtimestamp(time.time() + max(tgt - dec, 0) / max(spd, 1e-9)).strftime("%H:%M")
        status = rs.get("status")
        if status == "running" and al is False and meta is None:
            status = "끊김?"
        r = row or {}
        L.append(f"| {name} | {status} | {'살아 있음' if al else ('—' if al is None else '없음')} | {dec / 1e6:.2f}M / "
                 f"{fmt(tgt / 1e6 if tgt else None)}M | {fmt(pct, 0)} | {fmt(spd, 0)} | {eta or '—'} | {fmt(r.get('bite_per_1k'))} | "
                 f"{fmt(r.get('counter_per_1k'))} | {fmt(r.get('starve_per_1k'))} | {fmt(r.get('births_per_1k'))} | "
                 f"{fmt(r.get('eaten_e_x1000'))} | {fmt(r.get('act_run'))} | {fmt(r.get('in_shelter'))} | "
                 f"{fmt(r.get('kills_per_wolf_day'), 3)} | {fmt(r.get('E_median'))} | {fmt(r.get('toward_wolf'))} | "
                 f"{fmt((last or {}).get('entropy_loss'))} | {fmt((last or {}).get('explained_variance'))} |")
        sg = signals(row, meta, last_t, al, base, sp)
        if status == "끊김?":
            sg.append("프로세스가 끝 기록 없이 사라짐 (리그가 시작 사본에서 다시 돌린다)")
        for s_ in sg:
            sig_lines.append(f"- {name}: {s_}")
        key = (name, status, meta.get("stop") if meta else None)
        if seen.get(name) != key:
            seen[name] = key
            if seen.get("_started"):
                ev = log_dir / "watch_events.log"
                with ev.open("a", encoding="utf-8") as f:
                    f.write(f"{now_s()} {name}: {status} {meta.get('stop') if meta else ''}\n")
    seen["_started"] = True
    L += ["", "## 이상 신호 (9-5 — 멈추지 않고 아침에 읽는다)", ""]
    L += sig_lines or ["- 없음"]
    L += ["", "## 리그 사건 (마지막 10 줄)", ""]
    L += [f"- {e}" for e in st.get("events", [])[-10:]] or ["- 없음"]
    L += ["", f"규칙 두뇌 기준값: {args.baseline or '없음 (보정 관문 뒤 --baseline)'}", ""]
    halted = st.get("halted") is not None and not any_alive and not lg_alive
    return "\n".join(L) + "\n", halted


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default=str(CKPT / "league_state.json"))
    ap.add_argument("--out", default=str(CKPT))
    ap.add_argument("--log-dir", default=str(LOGS))
    ap.add_argument("--progress", default=None, help="기본 <log-dir>/progress.md")
    ap.add_argument("--interval", type=float, default=300.0)
    ap.add_argument("--max-hours", type=float, default=72.0)
    ap.add_argument("--baseline", default=None, help="규칙 두뇌 기준값 JSON (9-5)")
    ap.add_argument("--league-what", default="league r9", help="pids.txt 의 리그 줄 머리")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args(argv)
    base = read_json(absp(args.baseline)) if args.baseline else {}
    prog = absp(args.progress) if args.progress else absp(args.log_dir) / "progress.md"
    prog.parent.mkdir(parents=True, exist_ok=True)
    seen: dict = {}
    t0 = time.time()
    while True:
        text, halted = page(args, base or {}, seen)
        tmp = prog.with_suffix(".md.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(prog)
        if args.once or halted or time.time() - t0 > args.max_hours * 3600.0:
            if not args.once:
                print(f"{now_s()} 지켜보기 끝 ({'리그 멈춤' if halted else '시간 상한'})", flush=True)
            return 0
        time.sleep(float(args.interval))


if __name__ == "__main__":
    sys.exit(main())
