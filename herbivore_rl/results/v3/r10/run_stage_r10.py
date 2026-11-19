"""R10 정식 학습 단계 띄우기 (설계 10·16 절: 땅 10 → 하늘 2 → 물 4, 종마다 따로, 리그).

    python -X utf8 results/v3/r10/run_stage_r10.py --stage ground --out ckpt/r10/stage1 --init-from ckpt/r10/all1
    python -X utf8 results/v3/r10/run_stage_r10.py --stage air --out ckpt/r10/stage2 --init-from ckpt/r10/stage1
    python -X utf8 results/v3/r10/run_stage_r10.py --stage water --out ckpt/r10/stage3 --init-from ckpt/r10/stage2

- 세계 종 = 그 단계까지의 종 모두. 학습 종 = 그 단계까지의 종 모두(앞 단계 종은 이어 배움). 같은 --out 폴더가 리그(서로 최신 두뇌를 상대로).
- --init-from 폴더에 그 종의 zip 이 있으면 가장 큰 결정 수에서 잇는다. 없으면 처음부터.
- 사냥하는 몸(고기를 먹고 kill_mass_ratio > 0)은 밀도 단계(처음 작은 맵·먹잇감 많이)를 쓴다.
- 종마다 프로세스 하나(torch 스레드 1). 출력은 <out>/<종>.out · .log.jsonl · <종>_<결정>.zip/.npz.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

STAGES = {
    "ground": ["deer", "wolf", "boar", "buffalo", "leopard", "fox", "rat", "bighorn", "jackrabbit", "horse"],
    "air": ["crow", "golden_eagle"],
    "water": ["mink", "ariake_catfish", "common_carp", "small_fish"],
}
ORDER = ["ground", "air", "water"]


def latest_zip(folder: Path, sid: str):
    best = None
    for f in folder.glob(f"{sid}_*.zip"):
        n = f.stem.rpartition("_")[2]
        if n.isdigit() and (best is None or int(n) > best[0]):
            best = (int(n), f)
    return best[1] if best else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=ORDER, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--init-from", default=None)
    ap.add_argument("--decisions", type=int, default=30_000_000)
    ap.add_argument("--wall-hours", type=float, default=12.0)
    ap.add_argument("--snapshot-every", type=int, default=1_000_000)
    ap.add_argument("--refresh-every", type=int, default=1_000_000)
    ap.add_argument("--curriculum", type=int, default=3_000_000)
    ap.add_argument("--seed0", type=int, default=1000)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    species = [s for st in ORDER[:ORDER.index(a.stage) + 1] for s in STAGES[st]]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1")
    for i, sid in enumerate(species):
        card = json.loads((ROOT / "species" / f"{sid}.json").read_text(encoding="utf-8"))
        hunter = (card.get("combat", {}).get("kill_mass_ratio") or 0) > 0 and (card["diet"].get("meat") or 0) > 0
        cmd = [sys.executable, "-X", "utf8", str(HERE / "train_r10.py"), "--species", sid, "--only", *species,
               "--decisions", str(a.decisions), "--wall-hours", str(a.wall_hours), "--snapshot-every", str(a.snapshot_every),
               "--league-dir", str(out), "--refresh-every", str(a.refresh_every), "--seed", str(a.seed0 + i), "--out", str(out)]
        if hunter:
            cmd += ["--curriculum", str(a.curriculum), "--prey0", "4", "8"]
        init = latest_zip(Path(a.init_from), sid) if a.init_from else None
        if init:
            cmd += ["--init", str(init)]
        print(sid, "사냥" if hunter else "", init.name if init else "처음부터", flush=True)
        if not a.dry:
            fh = open(out / f"{sid}.out", "a", encoding="utf-8")
            subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
