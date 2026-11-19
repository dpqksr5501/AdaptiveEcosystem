"""R10 정식 학습 이어 달리기 — 앞 단계가 끝나길 기다렸다가 다음 단계를 띄운다 (땅 → 하늘 → 물).

    python -X utf8 results/v3/r10/chain_r10.py --after ground --root ckpt/r10 --base ckpt/r10/all1

- 끝 판정: 앞 단계 폴더의 종마다 <종>.out 에 '끝:' 줄이 있거나, 모든 .out 이 --stall-min 분 동안 안 바뀜(멈춤·죽음).
- 다음 단계는 run_stage_r10.py 로 띄우고 --init-from <앞 단계 폴더> <base> (앞 단계에 없는 종은 base 에서 잇는다).
- 기록: <root>/chain.log
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

from run_stage_r10 import ORDER, STAGES  # noqa: E402

FOLDER = {"ground": "stage1", "air": "stage2", "water": "stage3"}


def stage_species(stage: str) -> list:
    return [s for st in ORDER[:ORDER.index(stage) + 1] for s in STAGES[st]]


def finished(folder: Path, species: list, stall_s: float) -> tuple:
    outs = [folder / f"{s}.out" for s in species]
    done = [s for s, f in zip(species, outs) if f.exists() and "끝:" in f.read_text(encoding="utf-8", errors="replace")]
    if len(done) == len(species):
        return True, "모두 끝"
    newest = max((f.stat().st_mtime for f in outs if f.exists()), default=0.0)
    if newest and time.time() - newest > stall_s:
        return True, f"멈춤 {int((time.time() - newest) / 60)} 분 (끝 {len(done)}/{len(species)})"
    return False, f"끝 {len(done)}/{len(species)}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--after", choices=ORDER[:-1], default="ground", help="이 단계가 끝나길 기다린 뒤 다음 단계부터")
    ap.add_argument("--root", default="ckpt/r10")
    ap.add_argument("--base", default="ckpt/r10/all1", help="앞 단계에 없는 종을 이어 받을 폴더")
    ap.add_argument("--stall-min", type=float, default=30.0)
    ap.add_argument("--poll-s", type=float, default=120.0)
    ap.add_argument("--wall-hours", type=float, default=12.0)
    a = ap.parse_args(argv)
    root = Path(a.root)
    log = (root / "chain.log").open("a", encoding="utf-8")

    def say(msg):
        log.write(f"{time.strftime('%m-%d %H:%M')} {msg}\n")
        log.flush()

    prev = a.after
    for nxt in ORDER[ORDER.index(a.after) + 1:]:
        pf = root / FOLDER[prev]
        say(f"기다림: {prev} ({pf})")
        while True:
            ok, why = finished(pf, stage_species(prev), a.stall_min * 60)
            if ok:
                break
            time.sleep(a.poll_s)
        nf = root / FOLDER[nxt]
        say(f"{prev} 끝 ({why}) → {nxt} 띄움 ({nf})")
        cmd = [sys.executable, "-X", "utf8", str(HERE / "run_stage_r10.py"), "--stage", nxt, "--out", str(nf),
               "--init-from", str(pf), a.base, "--wall-hours", str(a.wall_hours)]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        say(r.stdout.strip().replace("\n", " | ") + (f" !! {r.stderr.strip()[-300:]}" if r.returncode else ""))
        if r.returncode:
            return r.returncode
        time.sleep(300)          # 새 .out 이 생길 시간
        prev = nxt
    say("이어 달리기 끝 (물 단계까지 띄움)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
