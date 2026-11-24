"""R10 이어 학습 시점 고르기 — 같은 시각에 저장된 16 종 두뇌 묶음(시점)마다 점검 맵에서 재고, 가장 나은 시점을 고른다.

    python -X utf8 results/v3/r10/pick_r10.py --run ckpt/r10/cont1 --base ckpt/r10/stage3 [--wait] [--export]

- 시점 = 이어 학습의 첫 저장부터 --every-hours 시간마다 + 끝. 종마다 그 시각까지 저장된 가장 새 npz(파일 시각).
  'base' 시점 = --base 폴더의 두뇌(이어 학습 전). 리그로 함께 배운 두뇌라 종마다 따로 섞지 않고 같은 시각끼리 묶는다.
- 1 차: 모든 시점을 점검 맵 60000~60007(8 개)에서. 2 차: 1 차 상위 --top 개 시점을 맵 60008~60031(24 개)에서 더 재고,
  1·2 차를 합친 32 개 맵으로 고른다. base 는 늘 2 차에 넣어 이어 학습으로 얼마나 나아졌는지 같은 맵에서 견준다. 규칙 두뇌도 같은 맵에서 잰다(잣대). 판정 시드(44800~44999)는 쓰지 않는다.
- 점수 = 16 종 평균 생존율(종마다 '끝 / 시작', 100 % 에서 자름). 포식자만 세져 먹잇감이 많이 죽은 시점은 높지 않다.
  같으면 규칙 두뇌보다 더 산 종 수.
- 결과: <run>/pick/ 아래 점검 json, <run>/pick.json(시점마다 표 · 고른 시점), <run>/pick.log.
  --export 면 고른 시점을 export_r10.py 로 언리얼 폴더(Saved/R10Demo)에 내보내고 <root>/chain.log 에 적는다.
- --wait: 이어 학습이 끝날 때까지(종마다 '끝:' 줄 또는 .out 이 --stall-min 분 동안 안 바뀜) 기다렸다가 시작.
- 이미 있는 점검 json 은 다시 돌리지 않는다(끊겨도 다시 부르면 이어 감).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]          # herbivore_rl
sys.path.insert(0, str(HERE))

from chain_r10 import finished  # noqa: E402
from run_stage_r10 import ORDER, STAGES, latest_npz  # noqa: E402

SPECIES = [s for st in ORDER for s in STAGES[st]]
R1 = (60000, 60008)
R2 = (60008, 60032)


def snaps(folder: Path, sid: str) -> list:
    out = []
    for f in folder.glob(f"{sid}_*.npz"):
        n = f.stem.rpartition("_")[2]
        if n.isdigit():
            out.append((f.stat().st_mtime, int(n), f))
    return sorted(out)


def build_slices(run: Path, base: Path, every_h: float) -> list:
    sn = {s: snaps(run, s) for s in SPECIES}
    slices = []
    bp = {s: latest_npz(base, s) for s in SPECIES}
    if all(bp.values()):
        slices.append({"label": "base", "picks": {s: str(p) for s, p in bp.items()}})
    if not all(sn.values()):
        return slices
    t0 = min(v[0][0] for v in sn.values())
    t_end = max(v[-1][0] for v in sn.values())
    times = []
    t = t0
    while t < t_end:
        times.append((f"{(t - t0) / 3600:.0f}h", t))
        t += every_h * 3600
    times.append(("끝", t_end + 1))
    seen = set()
    for label, T in times:
        picks = {}
        for s in SPECIES:
            got = [x for x in sn[s] if x[0] <= T + 600]
            if not got:
                break
            picks[s] = str(got[-1][2])
        if len(picks) == len(SPECIES):
            key = tuple(picks[s] for s in SPECIES)
            if key not in seen:
                seen.add(key)
                slices.append({"label": label, "picks": picks})
    return slices


def run_jobs(jobs: list, n_par: int, say) -> None:
    """jobs = [(out_path, cmd)] — 이미 있는 out 은 건너뜀."""
    todo = [(o, c) for o, c in jobs if not Path(o).exists()]
    running = []
    while todo or running:
        while todo and len(running) < n_par:
            o, c = todo.pop(0)
            lf = open(Path(o).with_suffix(".log"), "w", encoding="utf-8")
            running.append((o, subprocess.Popen(c, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT), lf))
        time.sleep(5)
        for item in list(running):
            o, p, lf = item
            if p.poll() is not None:
                lf.close()
                running.remove(item)
                if p.returncode or not Path(o).exists():
                    say(f"!! 점검 실패 {Path(o).name} (코드 {p.returncode}) — {Path(o).with_suffix('.log')}")


def tag(x: dict) -> str:
    """점검 json 이름 — 시점 이름 + 두뇌 묶음 지문('끝' 시점은 학습이 이어지면 두뇌가 바뀌므로 지문으로 가름)."""
    h = hashlib.sha1("|".join(x["picks"][s] for s in SPECIES).encode()).hexdigest()[:8]
    return f"{x['label']}_{h}"


def eval_cmd(seeds, picks, out) -> list:
    cmd = [sys.executable, "-X", "utf8", str(HERE / "eval_r10.py"), "--seeds", str(seeds[0]), str(seeds[1]), "--out", str(out)]
    if picks:
        cmd += ["--sample", "--brain", *[f"{s}={p}" for s, p in picks.items()]]
    return cmd


def load(paths) -> dict:
    """여러 점검 json 의 종마다 시작 · 끝 수를 합친다."""
    tot = {}
    for p in paths:
        for s, r in json.loads(Path(p).read_text(encoding="utf-8"))["result"].items():
            a = tot.setdefault(s, {"start": 0, "end": 0})
            a["start"] += r["start"]
            a["end"] += r["end"]
    return tot


def score(res: dict, rule: dict) -> dict:
    surv = {s: (res[s]["end"] / res[s]["start"] if res[s]["start"] else 0.0) for s in SPECIES}
    rsurv = {s: (rule[s]["end"] / rule[s]["start"] if rule[s]["start"] else 0.0) for s in SPECIES}
    return {"score": round(100 * sum(min(v, 1.0) for v in surv.values()) / len(surv), 2),
            "beat": sum(surv[s] > rsurv[s] for s in SPECIES),
            "surv": {s: round(100 * v, 1) for s, v in surv.items()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="ckpt/r10/cont1")
    ap.add_argument("--base", default="ckpt/r10/stage3")
    ap.add_argument("--root", default="ckpt/r10", help="chain.log 이 있는 폴더")
    ap.add_argument("--every-hours", type=float, default=3.0)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--jobs", type=int, default=6, help="동시에 돌릴 점검 수")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--stall-min", type=float, default=30.0)
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--dry", action="store_true", help="시점 목록만 보여 줌")
    a = ap.parse_args(argv)
    run, base, root = Path(a.run), Path(a.base), Path(a.root)
    pdir = run / "pick"
    pdir.mkdir(parents=True, exist_ok=True)
    logf = (run / "pick.log").open("a", encoding="utf-8")

    def say(msg):
        line = f"{time.strftime('%m-%d %H:%M')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    if a.wait:
        say(f"기다림: {run} 이어 학습이 끝나길")
        while True:
            ok, why = finished(run, SPECIES, a.stall_min * 60)
            if ok:
                say(f"이어 학습 끝 ({why})")
                break
            time.sleep(300)

    slices = build_slices(run, base, a.every_hours)
    say(f"시점 {len(slices)} 개: " + " ".join(x["label"] for x in slices))
    if a.dry:
        for x in slices:
            print(x["label"], " ".join(Path(p).stem.rpartition("_")[2] for p in x["picks"].values()))
        return 0

    # 1 차: 모든 시점 + 규칙 두뇌, 8 개 맵
    rule1 = pdir / "rule_r1.json"
    jobs = [(str(rule1), eval_cmd(R1, None, rule1))]
    for x in slices:
        x["r1_json"] = str(pdir / f"r1_{tag(x)}.json")
        jobs.append((x["r1_json"], eval_cmd(R1, x["picks"], x["r1_json"])))
    say(f"1 차 점검 {len(jobs)} 개 (맵 {R1[0]}~{R1[1] - 1})")
    run_jobs(jobs, a.jobs, say)
    rule_r1 = load([rule1])
    ok = [x for x in slices if Path(x["r1_json"]).exists()]
    for x in ok:
        x["r1"] = score(load([x["r1_json"]]), rule_r1)
    ok.sort(key=lambda x: (x["r1"]["score"], x["r1"]["beat"]), reverse=True)
    say("1 차: " + " · ".join(f"{x['label']} {x['r1']['score']:.1f}({x['r1']['beat']})" for x in ok))

    # 2 차: 상위 시점 + 이어 학습 전(base, 얼마나 나아졌나 잣대)을 24 개 맵 더
    top = ok[:a.top] + [x for x in ok[a.top:] if x["label"] == "base"]
    rule2 = pdir / "rule_r2.json"
    jobs = [(str(rule2), eval_cmd(R2, None, rule2))]
    for x in top:
        x["r2_json"] = str(pdir / f"r2_{tag(x)}.json")
        jobs.append((x["r2_json"], eval_cmd(R2, x["picks"], x["r2_json"])))
    say(f"2 차 점검 {len(jobs)} 개 (맵 {R2[0]}~{R2[1] - 1}): " + " ".join(x["label"] for x in top))
    run_jobs(jobs, a.jobs, say)
    rule_all = load([rule1, rule2])
    fin = [x for x in top if Path(x.get("r2_json", "")).exists()]
    for x in fin:
        x["all"] = score(load([x["r1_json"], x["r2_json"]]), rule_all)
    fin.sort(key=lambda x: (x["all"]["score"], x["all"]["beat"]), reverse=True)
    chosen = fin[0] if fin else (ok[0] if ok else None)
    rule_sc = score(rule_all, rule_all)
    say("2 차(32 개 맵 합): " + " · ".join(f"{x['label']} {x['all']['score']:.1f}({x['all']['beat']})" for x in fin)
        + f" | 규칙 두뇌 {rule_sc['score']:.1f}")
    out = {"made": time.strftime("%m-%d %H:%M"), "score": "16 종 평균 생존율(100 % 에서 자름), 괄호 = 규칙보다 더 산 종 수",
           "rule_all": rule_sc, "slices": slices, "chosen": chosen["label"] if chosen else None}
    (run / "pick.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if not chosen:
        say("!! 고를 시점이 없음")
        return 1
    say(f"고름: {chosen['label']} — " + " ".join(f"{s}={Path(p).stem.rpartition('_')[2]}" for s, p in chosen["picks"].items()))

    if a.export:
        cmd = [sys.executable, "-X", "utf8", str(HERE / "export_r10.py"), "--brain", *[f"{s}={p}" for s, p in chosen["picks"].items()]]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        msg = (r.stdout.strip().splitlines() or ["?"])[-1] + (f" !! {r.stderr.strip()[-300:]}" if r.returncode else "")
        say("언리얼 내보냄: " + msg)
        with (root / "chain.log").open("a", encoding="utf-8") as cl:
            sc = chosen.get("all") or chosen["r1"]
            cl.write(f"{time.strftime('%m-%d %H:%M')} {run.name} 시점 고름: {chosen['label']} (평균 생존 {sc['score']:.1f} %, "
                     f"규칙보다 더 산 종 {sc['beat']}/16, 규칙 두뇌 {rule_sc['score']:.1f} %) → 언리얼 내보냄: {msg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
