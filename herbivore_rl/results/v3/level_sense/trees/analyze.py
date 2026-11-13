"""나무 쪽 측정 묶음 정리 (10-27) — sense.py run 기록(저장소 밖)을 읽어 같은 시드 짝 표·위 5 칸·나무 성질 순위를 낸다.

    cd herbivore_rl && PYTHONUTF8=1 python results/v3/level_sense/trees/analyze.py --out <sense.py run --out 폴더> [--save]

판(combo) = 두뇌(r7e·r1bf) × 바탕(I 통합 s20004·J 조연우 s20010) × 세계(N 포만 끔·G 포만 켬) × 나무를 더한 지역(Barren·Forest). 판마다 그 지역 세계만
돌린 기록(__R-<지역>)을 쓴다 (나무를 더하지 않은 지역은 같은 시드면 바탕과 같다 — 하네스 바탕 맞추기 200/200).

비교 세 가지 (모두 같은 시드 짝 = 변형 − 대조, 시드 34900~34999):
  수  : t10·t30·t60·t120 (무작위) − base (+0)
  자리: ring30·graze30·path30·edge30·clump30 − t30 (같은 30 그루 무작위) 와 − base 둘 다. I 바탕 Forest 는 graze 10 그루·path 17 그루밖에 안 들어가
        trees:10:graze − t10, trees:17:path − trees:17:rand 로 같은 수끼리 견준다.
  길  : trees:60:rand+gate+paths:<한 길> − gate (파이썬 실행기, I·Barren 만)
표의 d = 차이 ÷ 바탕 시드 sd (sense.paired). t = 짝 차이 평균 ÷ 표준오차.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
import sense  # noqa: E402

BRAINS = ("r7e", "r1bf")
BASES = ("I", "J")
WORLDS = ("N", "G")
REGIONS = ("Barren", "Forest")
COUNTS = ("t10", "t30", "t60", "t120")
PLACES = ("ring30", "graze30", "path30", "edge30", "clump30")
I_FOREST = {"graze30": ("trees:10:graze", "t10"), "path30": ("trees:17:path", "trees:17:rand")}
PATHS = {"sight": "trees:60:rand+gate+paths:sight", "move": "trees:60:rand+gate+paths:move", "obs": "trees:60:rand+gate+paths:obs"}
RING_PATHS = {"sight": "trees:30:ring+gate+paths:sight", "move": "trees:30:ring+gate+paths:move", "obs": "trees:30:ring+gate+paths:obs"}
KEY = ["ep_hide", "ep_saved", "ep_caught", "caught", "hunt_success", "fl_obstacle_of_chased", "fl_cover_of_chased", "ep_chased_n", "ep_hidden_n",
       "fl_start_1k", "flee_share", "beh_graze", "beh_hide", "in_shelter", "starved", "route_pick_shelter"]
HEAD = ["ep_hide", "ep_hidden_n", "ep_chased_n", "ep_saved", "ep_caught", "caught", "hunt_success", "fl_obstacle_of_chased", "beh_graze", "beh_hide",
        "flee_share", "starved"]
# 위 5 칸에서 뺀다: 끝 까닭 몫 end_* 는 fl_*_of_chased 와 같은 것을 다른 분모로 다시 센 칸, 숨음·도망 수는 남긴다
SKIP_TOP = {"fl_obstacle_n", "route_drop_obstacle_n", "route_hidden_chased", "end_obstacle"}
TSIG = 3.0                                             # 바뀜으로 셀 |t| (칸이 많아 2 보다 엄하게)


def combos():
    for b in BRAINS:
        for base in BASES:
            for w in WORLDS:
                for r in REGIONS:
                    yield b, base, w, r


def cname(c) -> str:
    return f"{c[0]}·{c[1]}·{c[2]}·{c[3]}"


def pair_rows(d: Path, ref: str, var: str, region: str, runner=None) -> dict | None:
    try:
        t = sense.table(d, ref, [var], {region: [region]}, runner, None)
    except SystemExit:
        return None
    rows = t["variants"][var]["regions"][region]
    if rows is None:
        return None
    out = {}
    for k, p in rows.items():
        out[k] = {kk: (None if isinstance(p.get(kk), float) and not math.isfinite(p[kk]) else p.get(kk)) for kk in ("ref", "var", "diff", "t", "d", "sd_ref", "n")}
    out["_place"] = t["variants"][var]["place"]
    return out


def collect(out_dir: Path) -> dict:
    R: dict = {}
    for c in combos():
        b, base, w, r = c
        d = sense.run_dir(out_dir, base, b, w, 1800)
        if not d.exists():
            continue
        e: dict = {"count": {}, "place_vs_t30": {}, "place_vs_base": {}, "paths": {}, "ring_paths": {}}
        for v in COUNTS:
            e["count"][v] = pair_rows(d, "base", v, r)
        for v in PLACES:
            if base == "I" and r == "Forest" and v in I_FOREST:
                vv, ref = I_FOREST[v]
            else:
                vv, ref = v, "t30"
            e["place_vs_t30"][v] = pair_rows(d, ref, vv, r)
            e["place_vs_base"][v] = pair_rows(d, "base", vv, r)
        if r == "Barren" and base == "I":
            for k, v in PATHS.items():
                e["paths"][k] = pair_rows(d, "gate", v, r, "python")
            for k, v in RING_PATHS.items():
                e["ring_paths"][k] = pair_rows(d, "gate", v, r, "python")
        R[cname(c)] = e
    return R


def pct(name: str) -> float:
    return 100.0 if name in sense.PCT else 1.0


def cell(p: dict | None, name: str) -> str:
    if not p or name not in p or p[name]["diff"] is None:
        return "—"
    q = p[name]
    star = "**" if q["t"] is not None and abs(q["t"]) >= TSIG else ""
    return f"{star}{q['diff'] * pct(name):+.2f}{star} ({q['t']:+.1f})" if q["t"] is not None else f"{q['diff'] * pct(name):+.2f}"


DEER = {"flee_share", "fl_start_1k", "ep_start_1k", "in_shelter", "route_pick_shelter", "route_onset_shelter", "route_shelter_steps", "flight_len_s",
        "ep_hidden_n", "arrive_cover_n", "shelter_d_m", "onset_d_m", "onset_d_stalker_m", "onset_d_chaser_m", "trunk_d_m", "trunk_near2m", "deer_back_1k",
        "det_deer_used_1k", "tgt_deer_first", "tgt_deer_any"}


def is_deer(k: str) -> bool:
    """사슴이 스스로 고르거나 하는 것 (실행 행동 몫·도망 시작·은신처·움직인 거리 등). 늑대 쪽·끝 까닭·관측 입력은 뺀다."""
    return k in DEER or k.startswith(("beh_", "moved_"))


def top5(p: dict | None, deer: bool = False) -> list:
    """|d| 위 5 칸. 관측 입력 obs_* 는 행동이 아니라 뺀다. deer=True 면 사슴 행동 칸만."""
    if not p:
        return []
    rows = []
    for k, q in p.items():
        if k.startswith(("_", "obs_")) or k in SKIP_TOP or q["d"] is None or q["t"] is None:
            continue
        if deer and not is_deer(k):
            continue
        if q["sd_ref"] is None or q["sd_ref"] <= 0:
            continue
        rows.append((abs(q["d"]), k, q["d"], q["t"], q["diff"]))
    rows.sort(reverse=True)
    return [dict(metric=k, d=round(dd, 3), t=round(t, 2), diff=dif) for _, k, dd, t, dif in rows[:5]]


def labels() -> dict:
    return {m[0]: m[1] for m in sense._metrics()}


def report(R: dict) -> tuple[str, dict]:
    L = labels()
    md: list = []
    summ: dict = {"top5": {}, "prop_rank": {}, "agree": {}}
    md.append("# 나무 측정 표 (analyze.py 가 만든 글 — 손대지 않는다)\n")
    md.append(f"칸 = 같은 시드 짝 차이 (변형 − 대조) 와 (t). % 칸은 %p. **굵게** = |t| ≥ {TSIG:g}. 시드 34900~34999 (100), 1800 스텝, 나무를 더한 지역 세계만.\n")
    # 1. 수
    md.append("## 1. 수 (무작위, − base)\n")
    for m in HEAD:
        md.append(f"\n### {m} — {L.get(m, m)}\n")
        md.append("| 판 (두뇌·바탕·세계·지역) | 바탕 값 | +10 | +30 | +60 | +120 |")
        md.append("|---|---|---|---|---|---|")
        for cn, e in R.items():
            p0 = e["count"].get("t10")
            refv = "—" if not p0 or m not in p0 or p0[m]["ref"] is None else f"{p0[m]['ref'] * pct(m):.2f}"
            md.append(f"| {cn} | {refv} | " + " | ".join(cell(e["count"].get(v), m) for v in COUNTS) + " |")
    # 2. 자리
    md.append("\n## 2. 자리 (30 그루, − 같은 수 무작위)\n")
    md.append("I 바탕 Forest 의 graze·path 는 10·17 그루만 들어가 같은 수 무작위와 견준다.\n")
    for m in HEAD:
        md.append(f"\n### {m} — {L.get(m, m)}\n")
        md.append("| 판 | ring (문 앞 고리) | graze (풀밭) | path (길목) | edge (먼 가장자리) | clump (한 덩어리) |")
        md.append("|---|---|---|---|---|---|")
        for cn, e in R.items():
            md.append(f"| {cn} | " + " | ".join(cell(e["place_vs_t30"].get(v), m) for v in PLACES) + " |")
    # 3. 길
    ms = HEAD + ["fl_cover_of_chased", "in_shelter", "eye_blocked", "tgt_blocked", "deer_hit_1k", "wolf_hit_1k", "det_deer_used_1k", "onset_d_m",
                 "moved_m", "shelter_d_m"]
    for grp, title in (("paths", "+60 무작위"), ("ring_paths", "문 앞 고리 30 그루")):
        md.append(f"\n## 3{'' if grp == 'paths' else '-2'}. 길 ({title}, 한 길만 켬 − gate, 파이썬 실행기, I·Barren)\n")
        md.append("| 판 | 칸 | 눈길만 (sight) | 몸만 (move) | 관측만 (obs) |")
        md.append("|---|---|---|---|---|")
        for cn, e in R.items():
            if not any(e[grp].get(k) for k in PATHS):
                continue
            for m in ms:
                md.append(f"| {cn} | {m} | " + " | ".join(cell(e[grp].get(k), m) for k in PATHS) + " |")
    # 4. 위 5 칸 (판마다 |d| 위 5 → 16 판에서 몇 번 뽑혔나)
    md.append("\n## 4. 행동이 가장 많이 바뀐 칸 위 5 (|d| 순, 판마다 뽑아 모음)\n")
    md.append("d = 차이 ÷ 바탕 시드 sd. 바탕에서 늘 0 인 칸(나무가 있어야 생기는 칸)과 같은 것을 다시 센 칸은 뺐다. 칸 이름 뒤 = 뽑힌 판 수 / 평균 d.\n")
    groups = ([("count", v, "− base") for v in COUNTS] + [("place_vs_t30", v, "− t30") for v in PLACES] + [("place_vs_base", "ring30", "− base")]
              + [("paths", k, "− gate (60)") for k in PATHS] + [("ring_paths", k, "− gate (ring30)") for k in PATHS])
    md.append("관측 입력 obs_* 는 행동이 아니라 뺐다. '사슴만' = 사슴이 스스로 하는 칸(실행 행동 몫·도망 시작·은신처 안·숨은 사건 수·움직인 거리 등)만.\n")
    for deer in (False, True):
        md.append(f"\n### {'사슴 행동 칸만' if deer else '모든 칸 (늑대·도망 끝 까닭 포함)'}\n")
        for grp, v, refname in groups:
            cnt: dict = {}
            per: dict = {}
            for cn, e in R.items():
                tp = top5(e[grp].get(v), deer)
                if tp:
                    per[cn] = tp
                for x in tp:
                    c = cnt.setdefault(x["metric"], [0, 0.0, 0])
                    c[0] += 1
                    c[1] += x["d"]
                    c[2] += 1 if abs(x["t"]) >= TSIG else 0
            if not per:
                continue
            summ["top5" if not deer else "top5_deer"] = summ.get("top5" if not deer else "top5_deer", {})
            summ["top5" if not deer else "top5_deer"][f"{v} {refname}"] = per
            best = sorted(cnt.items(), key=lambda kv: (-kv[1][0], -abs(kv[1][1])))[:5]
            md.append(f"- **{v}** ({refname}, 판 {len(per)}): " + "; ".join(f"`{k}` {c[0]}/{c[1] / c[0]:+.2f} (|t|≥{TSIG:g} 인 판 {c[2]})" for k, c in best))
    # 5. 판마다 같은 결론인가 — 바뀜 방향 셈
    md.append(f"\n## 5. 판마다 같은 결론인가 — 판 평균 차이 [|t| ≥ {TSIG:g} 오름/내림/그대로 판 수]\n")
    md.append("| 변형 | " + " | ".join(HEAD) + " |")
    md.append("|---|" + "---|" * len(HEAD))
    for grp, v, refname in groups:
        row = []
        for m in HEAD:
            up = dn = fl = 0
            for e in R.values():
                p = e[grp].get(v)
                if not p or m not in p or p[m]["t"] is None:
                    continue
                if p[m]["t"] >= TSIG:
                    up += 1
                elif p[m]["t"] <= -TSIG:
                    dn += 1
                else:
                    fl += 1
            ds = [e[grp][v][m]["diff"] for e in R.values() if e[grp].get(v) and m in e[grp][v] and e[grp][v][m]["diff"] is not None]
            mean = sum(ds) / len(ds) * pct(m) if ds else None
            row.append(f"{mean:+.2f} [{up}/{dn}/{fl}]" if up + dn + fl else "—")
            summ["agree"].setdefault(f"{v} {refname}", {})[m] = dict(mean=mean, up=up, down=dn, flat=fl)
        md.append(f"| {v} {refname} | " + " | ".join(row) + " |")
    # 5-2. 두뇌·바탕·세계·지역 갈래마다
    md.append(f"\n## 5-2. 갈래마다 (두뇌·바탕·세계·지역 하나씩 고정, 판 8 개씩) — 평균 차이 [|t| ≥ {TSIG:g} 인 판 수]\n")
    SUB = ["ep_hide", "ep_hidden_n", "ep_caught", "caught", "hunt_success", "fl_obstacle_of_chased", "beh_hide", "beh_graze"]
    for grp, v, refname in [("count", "t30", "− base"), ("count", "t120", "− base"), ("place_vs_t30", "ring30", "− t30"),
                            ("place_vs_t30", "path30", "− t30"), ("place_vs_t30", "clump30", "− t30")]:
        md.append(f"\n### {v} {refname}\n")
        md.append("| 갈래 | " + " | ".join(SUB) + " |")
        md.append("|---|" + "---|" * len(SUB))
        for pos, keys in ((0, BRAINS), (1, BASES), (2, WORLDS), (3, REGIONS)):
            for k in keys:
                es = [e for cn, e in R.items() if cn.split("·")[pos] == k]
                row = []
                for m in SUB:
                    qs = [e[grp][v][m] for e in es if e[grp].get(v) and m in e[grp][v] and e[grp][v][m]["diff"] is not None]
                    if not qs:
                        row.append("—")
                        continue
                    sig = sum(1 for q in qs if q["t"] is not None and abs(q["t"]) >= TSIG)
                    row.append(f"{sum(q['diff'] for q in qs) / len(qs) * pct(m):+.2f} [{sig}/{len(qs)}]")
                    summ.setdefault("split", {}).setdefault(f"{v} {refname}", {}).setdefault(k, {})[m] = dict(
                        mean=sum(q["diff"] for q in qs) / len(qs) * pct(m), sig=sig, n=len(qs))
                md.append(f"| {k} | " + " | ".join(row) + " |")
    # 6. 나무 성질 순위 — 칸마다 성질별 가장 큰 |d| (판 가운데값)
    md.append("\n## 6. 어떤 나무 성질이 변화를 가장 크게 만드나 — 칸마다 판들의 가운데값 d [|t| ≥ 3 인 판 / 판]\n")
    md.append("수 = +n − base. 자리 = 그 자리 30 그루 − 무작위 30 그루(같은 수). 길 = +60 무작위의 한 길만 − gate (파이썬, I·Barren). d = 차이 ÷ 바탕 시드 sd. "
              "잡음 = 판들의 d 표준오차 가운데값(|d|/|t|) — 이보다 2~3 배 작으면 잡음 안이다. 바탕 sd 가 0 인 칸(Barren 바탕에 나무가 없어 늘 0 인 칸)은 d 대신 "
              "차이 %p 가운데값을 '%p' 로 적는다. 고리 … = 문 앞 고리 30 그루의 한 길만 − gate. 가장 큰 = 판 절반 넘게 |t| ≥ 3 인 것 가운데 |d| 가 가장 큰 것 "
              "(한 칸 안에 '%p' 가 섞이면 모두 |차이| 가운데값으로 견준다).\n")
    OPTS = [("수 30", "count", "t30"), ("수 60", "count", "t60"), ("수 120", "count", "t120"), ("문 앞 고리", "place_vs_t30", "ring30"),
            ("풀밭", "place_vs_t30", "graze30"), ("길목", "place_vs_t30", "path30"), ("먼 가장자리", "place_vs_t30", "edge30"),
            ("한 덩어리", "place_vs_t30", "clump30"), ("눈길만", "paths", "sight"), ("몸만", "paths", "move"), ("관측만", "paths", "obs"),
            ("고리 눈길만", "ring_paths", "sight"), ("고리 몸만", "ring_paths", "move")]
    md.append("| 칸 | 잡음 | " + " | ".join(o[0] for o in OPTS) + " | 가장 큰 |")
    md.append("|---|---|" + "---|" * len(OPTS) + "---|")

    def med(xs):
        xs = sorted(x for x in xs if x is not None)
        return None if not xs else (xs[len(xs) // 2] if len(xs) % 2 else 0.5 * (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]))

    def dval(p, m):
        if not p or m not in p or p[m]["t"] is None:
            return None
        q = p[m]
        ok = q["d"] is not None and q["sd_ref"] not in (None, 0)
        return (q["d"] if ok else None, q["diff"] * pct(m), q["t"])

    for m in HEAD:
        cells, rank = [], []
        se = med([abs(q[0] / q[2]) for e in R.values() for g in ("count", "place_vs_t30", "paths") for p in e[g].values()
                  for q in [dval(p, m)] if q and q[0] is not None and q[2] not in (0, None) and math.isfinite(q[2])])
        rec = {}
        mixed = [False]
        for lab, g, v in OPTS:
            qs = [q for q in (dval(e[g].get(v), m) for e in R.values()) if q]
            if not qs:
                cells.append("—")
                continue
            sig = sum(1 for q in qs if abs(q[2]) >= TSIG)
            ds = [q[0] for q in qs if q[0] is not None]
            mdf = med([q[1] for q in qs])
            if len(ds) * 2 >= len(qs):
                md_ = med(ds)
                cells.append(f"{md_:+.2f} [{sig}/{len(qs)}]")
                rec[lab] = dict(d=md_, diff=mdf, sig=sig, n=len(qs))
            else:
                md_ = None
                mixed[0] = True
                cells.append(f"{mdf:+.2f}%p [{sig}/{len(qs)}]")
                rec[lab] = dict(diff=mdf, sig=sig, n=len(qs))
            if sig * 2 > len(qs):
                rank.append((abs(md_) if md_ is not None else None, abs(mdf), lab))
        # 한 칸 안에 d 와 %p 가 섞이면 모두 %p 차이로 견준다
        rank = sorted(((r[1] if mixed[0] else r[0], r[2]) for r in rank), reverse=True)
        summ["prop_rank"][m] = dict(noise_se=se, opts=rec, best=rank[0][1] if rank else None)
        md.append(f"| {m} | {'—' if se is None else f'{se:.2f}'} | " + " | ".join(cells) + f" | {rank[0][1] if rank else '없음'} |")
    # 7. 자리 요약 (놓은 그루)
    md.append("\n## 7. 놓은 나무 (기록 meta)\n")
    for cn, e in R.items():
        notes = []
        for grp in ("count", "place_vs_base"):
            for v, p in e[grp].items():
                if p and p.get("_place"):
                    notes.append(f"{v}: {p['_place']}")
        md.append(f"- {cn}: " + "; ".join(notes))
    return "\n".join(md) + "\n", summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="sense.py run --out 폴더 (저장소 밖)")
    ap.add_argument("--save", action="store_true", help="trees/TABLES.md·results.json 을 쓴다")
    a = ap.parse_args(argv)
    R = collect(Path(a.out))
    md, summ = report(R)
    if a.save:
        (HERE.parent / "TABLES.md").write_text(md, encoding="utf-8")
        slim = {cn: {g: {v: ({k: q for k, q in p.items() if k in KEY or k.startswith("_") or k in ("eye_blocked", "tgt_blocked", "deer_hit_1k",
                                                                                                         "wolf_hit_1k", "onset_d_m", "moved_m")}
                                if p else None) for v, p in e[g].items()} for g in e} for cn, e in R.items()}
        (HERE.parent / "results.json").write_text(json.dumps(dict(meta=dict(made_by="level_sense/trees/analyze.py", seeds=[34900, 34999], horizon=1800,
                                                                           tsig=TSIG), summary=summ, pairs=slim), ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
        print(f"-> {HERE.parent / 'TABLES.md'}, results.json")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
