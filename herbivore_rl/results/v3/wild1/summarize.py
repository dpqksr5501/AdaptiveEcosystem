"""야생 1단계 측정 표 (results/v3/wild1/README.md). run_all.sh 가 만든 runs/*.json(run_mirror.py --diag)을 읽어 표 하나를 쓴다.

    # herbivore_rl/ 에서
    python results/v3/wild1/summarize.py            # → results/v3/wild1/table.md

열(세계를 모두 합친 수):
  산·잡힘·굶음 %   = 처음 놓은 사슴 가운데 끝까지 산·잡힌·굶어 죽은 비율
  도망 %           = 산 사슴-스텝 가운데 행동이 FLEE 인 몫, 숨기 % = HIDE 인 몫
  알아챔 <5·5~10·10~15·15~30 m = 깨어 있는 늑대와 그 거리에 있는 (사슴, 늑대) 쌍 가운데 사슴이 알아챈(시야·청각) 몫
  잡힘 중 도망 %   = 잡힌 사슴 가운데 마지막 5초 안에 도망친 적이 있는 몫, 잡힘 중 먹던 % = 잡힌 스텝 행동이 GRAZE 인 몫,
  잡힘 중 못 봄 %  = 마지막 5초 동안 깨어 있는 늑대를 한 번도 알아채지 못한 몫
  도망 중 굶음     = 굶어 죽은 사슴 가운데 마지막 5초 안에 도망친 수
  늑대 하루 사냥   = 잡힘 ÷ (늑대 수 × 게임 하루 수)
  늑대 배부름·먹기 % = 늑대-스텝 가운데 배불러 쉰·먹은 몫(포만 규칙을 켠 판만), 약함 % = 산 사슴-스텝 가운데 배가 바닥인(E < 0.1) 몫
  첫 굶음(일)      = 세계마다 처음 굶어 죽은 때(게임 하루)의 중앙값(굶음이 없는 세계는 빼고, 그 수를 괄호에)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
ORDER = ("base", "wild1", "wild1_no_reserve", "wild1_no_satiation", "wild1_no_detect", "wild1_no_flight", "base_long", "wild1_long")
LABEL = {"base": "기준(거울)", "wild1": "야생 1단계", "wild1_no_reserve": "  - 비축 뺌", "wild1_no_satiation": "  - 포만 뺌",
         "wild1_no_detect": "  - 시야·청각 뺌", "wild1_no_flight": "  - 도주 반사 뺌", "base_long": "기준 16분", "wild1_long": "야생 1단계 16분"}


def summarize(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    W = [w["meta"] for w in d["worlds"]]
    n = sum(m["n"] for m in W)
    cause = np.concatenate([np.asarray(m["death_cause"]) for m in W])
    dg = [m["diag"] for m in W]
    beh = np.sum([x["beh_steps"] for x in dg], 0)
    bp = np.sum([x["band_pairs"] for x in dg], 0)
    bs = np.sum([x["band_seen"] for x in dg], 0)
    catches = sum(x["catches"] for x in dg)
    days = sum(x["wolves"] * x["steps"] / x["period"] for x in dg)
    out = dict(worlds=len(W), deer=d["meta"]["deer"], steps=d["meta"]["steps"],
               alive=100 * np.mean(cause == 0), caught=100 * np.mean(cause == 1), starved=100 * np.mean(cause == 2),
               flee=100 * beh[1] / beh.sum(), hide=100 * beh[2] / beh.sum(), seen=(100 * bs / np.maximum(bp, 1)).tolist(),
               catch_fled=100 * sum(x["catch_fled"] for x in dg) / max(catches, 1),
               catch_graze=100 * sum(x["catch_beh"][0] for x in dg) / max(catches, 1),
               catch_unseen=100 * (1 - sum(x["catch_saw"] for x in dg) / max(catches, 1)),
               starve_fled=sum(x["starve_fled"] for x in dg), starves=sum(x["starves"] for x in dg),
               kills_per_wolf_day=catches / max(days, 1e-9))
    first = []
    for m in W:
        t = [dt for dt, c in zip(m["death_t"], m["death_cause"]) if c == 2]
        if t:
            first.append(min(t) / m["diag"]["period"])
    out["first_starve_day"] = float(np.median(first)) if first else float("nan")
    out["first_starve_worlds"] = len(first)
    wild = [x.get("wild", {}) for x in dg]
    for k in ("sated_frac", "eating_frac", "weak_frac", "reserve_mean"):
        v = [x[k] for x in wild if k in x]
        out[k] = float(np.mean(v)) if v else float("nan")
    assert abs(out["alive"] + out["caught"] + out["starved"] - 100) < 1e-6
    return out


def fmt(x, nd=1):
    return "-" if x != x else f"{x:.{nd}f}"


def table(rows) -> str:
    head = ("| 판 | 사슴 | 세계 | 산 % | 잡힘 % | 굶음 % | 도망 % | 숨기 % | 알아챔 <5·5~10·10~15·15~30 m % | 잡힘 중 도망 % | 잡힘 중 먹던 % | "
            "잡힘 중 못 봄 % | 도망 중 굶음 / 굶음 | 늑대 하루 사냥 | 늑대 배부름 % | 늑대 먹기 % | 약함 % | 첫 굶음(일) |")
    lines = [head, "|" + "---|" * 18]
    for name, s in rows:
        lines.append(" | ".join([f"| {LABEL.get(name, name)}", str(s["deer"]), str(s["worlds"]), fmt(s["alive"]), fmt(s["caught"]),
                                 fmt(s["starved"]), fmt(s["flee"]), fmt(s["hide"]), "·".join(f"{v:.0f}" for v in s["seen"]),
                                 fmt(s["catch_fled"], 0), fmt(s["catch_graze"], 0), fmt(s["catch_unseen"], 0),
                                 f"{s['starve_fled']} / {s['starves']}", fmt(s["kills_per_wolf_day"], 2),
                                 fmt(100 * s["sated_frac"], 0), fmt(100 * s["eating_frac"], 0), fmt(100 * s["weak_frac"], 0),
                                 f"{fmt(s['first_starve_day'], 2)} ({s['first_starve_worlds']})"]) + " |")
    return "\n".join(lines)


def main(argv=None) -> None:
    out = []
    for deer in (128, 64):
        rows = []
        for key in ORDER:
            p = RUNS / f"d{deer}_{key}.json"
            if p.exists():
                rows.append((key, summarize(p)))
        if rows:
            out.append(f"## 사슴 {deer}마리\n\n" + table(rows))
    text = "# 야생 1단계 측정 표 (summarize.py 가 만든다)\n\n" + "\n\n".join(out) + "\n"
    (HERE / "table.md").write_text(text, encoding="utf-8")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
