"""야생 2단계 1 (은신처 먹이 부족) 파이썬 거울 표 (README.md). herbivore_rl/ 에서
    python results/v3/wild2/summarize.py d128_wild1 d128_wild2 d128_wild1_long d128_wild2_long
runs/<이름>.json 은 run_mirror.py --diag 결과다(세계 메타 hunt·shelter_steps·live_steps, 진단 catch_cover·catch_ring).

칸 (정의는 env_v2/world.py 모듈 docstring '야생 2단계', run_mirror.py 머리 주석):
  산·잡힘·굶음 %   마지막 줄(240초 판은 240초, 16분 판은 960초) — 처음 사슴 대비, 세계 모두 합
  사냥 성공률      끝난 사냥 가운데 잡음으로 끝난 몫(세계 모두 합). ±2σ 는 세계를 묶음으로 본 비율 추정의 어림(세계 안 상관은 그대로 둔다)
  추격형·잠행형    유형별 성공률(성공/끝)
  사냥/늑대·일     사냥 시작 수 ÷ (늑대 수 × 게임 하루 수, 하루 = 900 스텝)
  잡음/늑대·일     늑대 포획(성공 + 사냥 밖) ÷ (늑대 수 × 게임 하루 수)
  은신처 안 %      스텝 첫머리 산 사슴 가운데 이동 뒤 위치가 은신처 원 안인 사슴·스텝 몫
  둘레 밖 2·4 m    은신처 원 밖이고 가장 가까운 둘레까지 2 m·4 m 안에서 잡힌 수, 원 안 = 은신처 안에서 잡힌 수(0 이어야 한다)
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY = 900


def load(name: str) -> dict:
    return json.loads((HERE / "runs" / f"{name}.json").read_text(encoding="utf-8"))


def ratio_se(num: list[float], den: list[float]) -> float:
    """묶음 비율 Σnum/Σden 의 표준오차 어림(묶음 = 세계)."""
    n, D = len(num), sum(den)
    if n < 2 or D <= 0:
        return float("nan")
    r = sum(num) / D
    return math.sqrt(sum((a - r * b) ** 2 for a, b in zip(num, den)) * n / (n - 1)) / D


def row(name: str) -> dict:
    d = load(name)
    t = dict(name=name, worlds=len(d["worlds"]), steps=d["meta"]["steps"], n=0, alive=0, caught=0, starved=0, starts=0, ends=0, success=0, outside=0,
             ch_e=0, ch_s=0, st_e=0, st_s=0, wolves=0, shelter=0, live=0, cover=0, ring2=0, ring4=0, e_pct=0.0, food=0.0, succ_w=[], end_w=[])
    for w in d["worlds"]:
        last, m = w["rows"][-1], w["meta"]
        h, g = m["hunt"], m["diag"]
        t["n"] += last["n"]
        t["alive"] += last["alive_end"]
        t["caught"] += last["caught"]
        t["starved"] += last["starved"]
        for k in ("starts", "ends", "success", "outside"):
            t[k] += h[k]
        t["ch_e"] += h["chaser_ends"]
        t["ch_s"] += h["chaser_success"]
        t["st_e"] += h["stalker_ends"]
        t["st_s"] += h["stalker_success"]
        t["succ_w"].append(h["success"])
        t["end_w"].append(h["ends"])
        t["wolves"] += m["wolves"]
        t["shelter"] += m["shelter_steps"]
        t["live"] += m["live_steps"]
        t["cover"] += g["catch_cover"]
        t["ring2"] += g["catch_ring"][0]
        t["ring4"] += g["catch_ring"][1]
        t["e_pct"] += last["energy_pct"]
        t["food"] += last["food_pct"]
    return t


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def main(names):
    print("| 판 | 세계 × 시간 | 산 % | 잡힘 % | 굶음 % | 사냥 성공률 % (±2σ) | 추격형 · 잠행형 성공률 % | 사냥/늑대·일 | 잡음/늑대·일 | 사냥 밖 포획 | "
          "은신처 안 % | 원 안 잡힘 | 둘레 밖 2 m · 4 m 안 잡힘 | 끝 에너지 % · 먹이 % |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for nm in names:
        t = row(nm)
        days = t["steps"] / DAY
        wd = t["wolves"] * days
        se = ratio_se(t["succ_w"], t["end_w"])
        sec = t["steps"] * 8.0 / 60.0
        span = f"{t['worlds']} × {sec / 60.0:.0f}분" if sec >= 600 else f"{t['worlds']} × {sec:.0f}초"
        print(f"| {nm} | {span} | {pct(t['alive'], t['n']):.1f} | {pct(t['caught'], t['n']):.2f} | {pct(t['starved'], t['n']):.2f} | "
              f"{pct(t['success'], t['ends']):.1f} (±{200.0 * se:.1f}) | {pct(t['ch_s'], t['ch_e']):.0f} · {pct(t['st_s'], t['st_e']):.0f} | "
              f"{t['starts'] / wd:.2f} | {(t['success'] + t['outside']) / wd:.2f} | {t['outside']} | {pct(t['shelter'], t['live']):.1f} | {t['cover']} | "
              f"{t['ring2']} · {t['ring4']} | {t['e_pct'] / t['worlds']:.0f} · {t['food'] / t['worlds']:.0f} |")


if __name__ == "__main__":
    main(sys.argv[1:])
