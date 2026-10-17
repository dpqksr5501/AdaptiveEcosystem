"""10-17 늑대 몸 여유 표 (README.md '늑대 몸 여유'). herbivore_rl/ 에서
    python results/v3/wild1/summarize_margin.py d128_margin0 d128_margin1m d128_margin0_no_sat d128_margin1m_no_sat
runs/<이름>.json 은 run_mirror.py --diag 결과다(진단 칸 catch_cover·catch_ring·wolf_steps·wolf_in_r·wolf_in_1m·wolf_edge_min)."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from env_v2 import repertoire as rep  # noqa: E402


def row(name: str) -> dict:
    d = json.loads((HERE / "runs" / f"{name}.json").read_text(encoding="utf-8"))
    t = dict(n=0, alive=0, caught=0, starved=0, catches=0, cover=0, ring2=0, ring4=0, wsteps=0, w_in_r=0, w_in_1m=0, edge_min=math.inf,
             flee=0, beh=0, margin=d["meta"].get("wolf_margin"))
    for w in d["worlds"]:
        last, g = w["rows"][-1], w["meta"]["diag"]
        t["n"] += last["n"]
        t["alive"] += last["alive_end"]
        t["caught"] += last["caught"]
        t["starved"] += last["starved"]
        t["catches"] += g["catches"]
        t["cover"] += g["catch_cover"]
        t["ring2"] += g["catch_ring"][0]
        t["ring4"] += g["catch_ring"][1]
        t["wsteps"] += g["wolf_steps"]
        t["w_in_r"] += g["wolf_in_r"]
        t["w_in_1m"] += g["wolf_in_1m"]
        if g["wolf_edge_min"] is not None:
            t["edge_min"] = min(t["edge_min"], g["wolf_edge_min"])
        t["flee"] += g["beh_steps"][rep.FLEE]
        t["beh"] += sum(g["beh_steps"])
    return t


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def main(names):
    print("| 판 | 몸 여유 | 산 % | 잡힘 % (±2σ) | 굶음 % | 도망 % | 잡힘 수 | 은신처 안 잡힘 | 둘레 밖 2 m 안 잡힘 | 둘레 밖 4 m 안 잡힘 | "
          "늑대 중심 원 안 % | 늑대 중심 둘레 1 m 안 % | 늑대 중심과 둘레 가장 가까이 (m) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for nm in names:
        t = row(nm)
        p = t["caught"] / t["n"]
        se = 200.0 * math.sqrt(p * (1.0 - p) / t["n"])            # 사슴마다 따로 잡힌다고 본 어림(세계 안 상관은 무시)
        m = "설정 값 1 m" if t["margin"] is None else f"{2.0 * t['margin']:.0f} m"
        print(f"| {nm} | {m} | {pct(t['alive'], t['n']):.1f} | {100 * p:.2f} (±{se:.2f}) | {pct(t['starved'], t['n']):.1f} | "
              f"{pct(t['flee'], t['beh']):.1f} | {t['catches']} | {t['cover']} | {t['ring2']} | {t['ring4']} | {pct(t['w_in_r'], t['wsteps']):.2f} | "
              f"{pct(t['w_in_1m'], t['wsteps']):.2f} | {2.0 * t['edge_min']:.2f} |")


if __name__ == "__main__":
    main(sys.argv[1:])
