"""10-16 가장자리·은신처 고침 표 (README.md '가장자리·은신처 고침'). herbivore_rl/ 에서
    python results/v3/wild1/summarize_fix.py d128_fix_before d128_fix_after d128_fix_before_no_sat d128_fix_after_no_sat
runs/<이름>.json 은 run_mirror.py --diag 결과다(진단 칸 catch_edge·catch_corner·catch_cover·catch_repeat·occ_*·panic_end_awake)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from env_v2 import repertoire as rep  # noqa: E402

EDGE_AREA = 1.0 - ((60.0 - 2 * 2.5) / 60.0) ** 2      # 가장자리 5 m 띠의 넓이 몫(60 단위 무대)
CORNER_AREA = 4 * 5.0 * 5.0 / 3600.0                  # 모서리(두 벽 모두 10 m 안) 넓이 몫


def row(name: str) -> dict:
    d = json.loads((HERE / "runs" / f"{name}.json").read_text(encoding="utf-8"))
    t = {k: 0 for k in ("n", "alive", "caught", "starved", "catches", "edge", "corner", "cover", "repeat", "occ", "occ_e", "occ_c",
                        "ends", "ends_awake", "flee", "beh")}
    for w in d["worlds"]:
        last, g = w["rows"][-1], w["meta"]["diag"]
        t["n"] += last["n"]
        t["alive"] += last["alive_end"]
        t["caught"] += last["caught"]
        t["starved"] += last["starved"]
        t["catches"] += g["catches"]
        t["edge"] += g["catch_edge"]
        t["corner"] += g["catch_corner"]
        t["cover"] += g["catch_cover"]
        t["repeat"] += g["catch_repeat"]
        t["occ"] += g["occ_n"]
        t["occ_e"] += g["occ_edge"]
        t["occ_c"] += g["occ_corner"]
        t["ends"] += g["panic_ends"]
        t["ends_awake"] += g["panic_end_awake"]
        t["flee"] += g["beh_steps"][rep.FLEE]
        t["beh"] += sum(g["beh_steps"])
    return t


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def main(names):
    print("| 판 | 산 % | 잡힘 % | 굶음 % | 도망 % | 도주 풀림 (그중 깨어 있는 늑대 40 m 안) | 잡힘 수 | 가장자리 5 m 잡힘 % (자리 몫 %) | "
          "모서리 잡힘 % (자리 몫 %) | 같은 늑대 20 m 안 거듭 잡힘 % | 은신처 안 잡힘 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for nm in names:
        t = row(nm)
        print(f"| {nm} | {pct(t['alive'], t['n']):.1f} | {pct(t['caught'], t['n']):.1f} | {pct(t['starved'], t['n']):.1f} | "
              f"{pct(t['flee'], t['beh']):.1f} | {t['ends']} ({t['ends_awake']}) | {t['catches']} | "
              f"{pct(t['edge'], t['catches']):.0f} ({pct(t['occ_e'], t['occ']):.0f}) | {pct(t['corner'], t['catches']):.0f} "
              f"({pct(t['occ_c'], t['occ']):.1f}) | {pct(t['repeat'], t['catches']):.0f} | {t['cover']} |")
    print(f"\n넓이 몫: 가장자리 5 m 띠 {100 * EDGE_AREA:.1f}%, 모서리 {100 * CORNER_AREA:.1f}%")


if __name__ == "__main__":
    main(sys.argv[1:])
