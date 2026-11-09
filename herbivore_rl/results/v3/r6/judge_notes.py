"""R6 판정 뒤 보고만 — 지킴 GF·GR 이 왜 걸렸는지 가르는 사후 셈 (사전 등록 PREREG.md 8절 '어느 기준이 왜 깨졌는지 보고').

판정(judge.md)을 바꾸지 않는다. 판정·고르기·점검 때 이미 쓴 판 파일(results/v3/r6/runs/, git 밖)만 다시 읽고 새 세계를 돌리지 않는다.
사전 등록에 없던 셈이라 다음 갈래를 사람이 정할 때의 재료로만 쓴다(같은 판정 시드로 두뇌·문턱을 다시 고르지 않는다).

    # herbivore_rl/ 에서
    PYTHONUTF8=1 python results/v3/r6/judge_notes.py            # → results/v3/r6/logs/judge_notes.txt

1. 판정 N 판(시드 37000~37099 × 지역 셋): 시작한 도망을 길(run·shelter·none — none = 도주 반사 밖에서 두뇌가 스스로 고른 FLEE 로 시작해 길 결정이
   없는 도망)으로 나눈 시드당 수, 끝 까닭, GF(1000 산 사슴-스텝당 시작한 도망)·GR(살아 끝난 도망 뒤 5 초 안 다시 도망) — R6·route0·'늘 SHELTER'·대조 '길 끔'.
   '늘 SHELTER'·대조의 GF(·GR) 짝 t 도 route0 대비로 적는다(live.flight_rate_pair·r6_eval.route_guards 와 같은 셈 — 보고만).
2. 점검(37120~37139)·고르기(37100~37119) 판의 같은 칸 — 조기 점검·고르기 잣대에는 GF·GR 이 없었다(PREREG 5·6절).
   판마다 같은 시드의 route0 판(점검 = early_base, 고르기 = select_route0)과의 GF·GR 짝 차이·t 도 적는다(시드 20 — 문턱이었다면 t_crit(19) 2.093).
10-23 판정 뒤 검토 덧붙임(셈 길은 그대로, 칸만 더함): 길마다 도망 하나의 평균 길이(초), 반사 도망(run·shelter) 하나당 길 결정·다시 고름(judge.md 의
'도망 하나당'은 none 도망까지 분모에 넣는다), none 도망 판 전체 수, 위 2 의 짝 t.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

import r6_eval as R  # noqa: E402

lv, re_ = R.lv, R.re_
RUNS = HERE.parent / "runs"
OUT = HERE.parent / "logs" / "judge_notes.txt"
ROUTES = ("run", "shelter", "none")


def load(name: str) -> dict:
    return json.loads((RUNS / f"{name}.json").read_text(encoding="utf-8"))


def flights(res: dict) -> dict:
    """판 하나의 시드당 도망 수: 시작·쫓긴·숨음, 길마다 시작 수와 끝 까닭, GF, GR(길 기록이 있는 판만), 실행 FLEE 가운데 반사 밖 몫."""
    W = res["worlds"]
    S = len({int(w["seed"]) for w in W})
    t = Counter()
    ends = Counter()
    by = {r: Counter() for r in ROUTES}
    by_steps = Counter()
    has_route = all((w.get("flight") or {}).get("route") for w in W)
    for w in W:
        f = lv.flight_of(w)
        t.update(started=f["started"], live=f["live_steps"], flee=f["flee_steps"], reflex=f["reflex_steps"],
                 chased=f["hide"]["chased"], hidden=f["hide"]["hidden"])
        ends.update(f["n"])
        r = f.get("route")
        if r is not None:
            t["refled"] += int(r["refled"])
            t["decisions"] += int(r["decisions"])
            t["redecide"] += int(r["redecide_feas"])
            for k in ROUTES:
                by[k].update((r["by_route"].get(k) or {}).get("n", {}))
                by_steps[k] += sum(((r["by_route"].get(k) or {}).get("steps") or {}).values())
    out = dict(seeds=S, started=t["started"] / S, gf=1000.0 * t["started"] / t["live"], chased=t["chased"] / S, hidden=t["hidden"] / S,
               hide_share=t["hidden"] / t["chased"] if t["chased"] else float("nan"), nonreflex_flee=(t["flee"] - t["reflex"]) / S,
               ends={k: v / S for k, v in ends.items() if v})
    if has_route:
        reflex_n = sum(by["run"].values()) + sum(by["shelter"].values())
        out.update(refled=t["refled"] / S,
                   by_route={k: dict(n=sum(c.values()) / S, unchased=c["unchased"] / S, cover=c["cover"] / S, caught=c["caught"] / S,
                                     mean_s=lv.ratio(by_steps[k] * lv.STEP_S, sum(c.values()))) for k, c in by.items()},
                   none_total=int(sum(by["none"].values())), dec_per_reflex=lv.ratio(t["decisions"], reflex_n),
                   redecide_per_reflex=lv.ratio(t["redecide"], reflex_n))
    return out


def line(name: str, x: dict) -> str:
    s = (f"{name:30s} 시드 {x['seeds']:3d} · 시작한 도망 {x['started']:7.1f}/시드 · GF(전체 합) {x['gf']:.4f} · GR {x.get('refled', float('nan')):6.1f}/시드 · "
         f"쫓긴 도망 {x['chased']:6.1f} · 숨음 {x['hidden']:6.1f} ({x['hide_share'] * 100:.2f}%) · 반사 밖 실행 FLEE {x['nonreflex_flee']:7.1f} 스텝/시드")
    if "by_route" in x:
        s += "\n" + " " * 32 + " · ".join(f"길 {k} {v['n']:.1f} (안 쫓김 끝 {v['unchased']:.1f} · 은신처 끝 {v['cover']:.1f} · 잡힘 {v['caught']:.1f} · "
                                          f"평균 {v['mean_s']:.2f} 초)" for k, v in x["by_route"].items() if v["n"] > 0.05)
        s += ("\n" + " " * 32 + f"none 도망 판 전체 {x['none_total']} 개 · 반사 도망(run·shelter) 하나당 길 결정 {x['dec_per_reflex']:.3f} · "
              f"다시 고름 {x['redecide_per_reflex']:.3f}")
    return s


def pair_rows(cand: dict, cur: dict, label: str) -> list[str]:
    """보고만: GF(·GR) 짝 차이·t (route0 대비). GR 은 두 판 모두 길 기록이 있을 때만."""
    L = []
    q = lv.flight_rate_pair(cand, cur, "starts")
    L.append(f"  {label} GF 짝 차이 {q['diff']:+.4f} (t {lv.tfmt(q['t'])}, 시드 {q['n']})")
    if all(w["flight"].get("route") for w in cand["worlds"]) and all(w["flight"].get("route") for w in cur["worlds"]):
        g = R.route_guards(cand, cur)["GR_reflee"]
        L.append(f"  {label} GR 짝 차이 {g['diff']:+.2f}/시드 (t {lv.tfmt(g['t'])}, 시드 {g['n']})")
    return L


def main() -> int:
    L = ["# R6 판정 뒤 보고만 — GF·GR 이 걸린 까닭 (사후 셈, 판정을 바꾸지 않는다)", "",
         "## 1. 판정 N 판 (시드 37000~37099 × 지역 셋, 1800 스텝 — judge.md 와 같은 판 파일)", ""]
    N = {k: load(f"judge_{k}_N") for k in ("r6", "route0", "rule", "off")}
    for k, label in (("r6", "R6 v3_r6_g995_s1_20m"), ("route0", "route0"), ("rule", "'늘 SHELTER' (옛 규칙)"), ("off", "대조 '길 끔'")):
        L.append(line(label, flights(N[k])))
    L += ["", "route0 대비 짝 (보고만 — R6 의 칸은 judge.md 와 같다):"]
    for k, label in (("r6", "R6"), ("rule", "'늘 SHELTER'"), ("off", "대조 '길 끔'")):
        L += pair_rows(N[k], N["route0"], label)
    L += ["", "## 2. 점검·고르기 판 (조기 점검·고르기 잣대에 GF·GR 이 없었다 — 사후 셈)", "",
          "판마다 아래 줄: 같은 시드 route0 판(점검 early_base · 고르기 select_route0) 대비 GF·GR 짝 (시드 20 — 문턱이었다면 t_crit(19) 2.093, 보고만)", ""]
    bases = {"early": "early_base", "select": "select_route0"}
    for name in ("early_base", "early_l95_c0", "early_l95_c0027", "early_l95_c005", "early_l98_c0", "early_l98_c0027", "early_l98_c005",
                 "early_s0_2m", "early_s1_2m", "early_s2_2m", "early_s0_5m", "early_s1_5m", "early_s2_5m", "early_off_5m",
                 "select_route0", "select_v3_r6_g995_s0_20m", "select_v3_r6_g995_s1_20m", "select_v3_r6_g995_s2_20m"):
        p = RUNS / f"{name}.json"
        if p.exists():
            res = load(name)
            L.append(line(name, flights(res)))
            base = bases[name.split("_")[0]]
            if name != base and (RUNS / f"{base}.json").exists():
                L += [" " * 30 + x.strip() for x in pair_rows(res, load(base), f"{base} 대비")]
    text = "\n".join(L) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
