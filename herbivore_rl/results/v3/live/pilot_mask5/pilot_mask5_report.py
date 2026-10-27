"""판 5 예비 측정 표 (pilot.md — pilot_mask5_analyze.py 가 summary.json 에서 자동으로 만든다. 손으로 고치지 않는다)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

import pilot_mask5_analyze as an

HS = (900, 1800, 2700, 3600)
N_CELLS = [k for k, v in an.CELLS.items() if v[0] == "N"]
G_CELLS = [k for k, v in an.CELLS.items() if v[0] == "G"]
SHORT = {"P1_N_hide": "P1 사건 숨음", "GH_flight_caught": "GH 사건 잡힘", "GN_caught": "GN 잡힘", "GN_starved": "GN 굶음", "GN_alive": "GN 산",
         "GF_flight_starts": "GF 도망 시작/1000", "GE_episode_starts": "GE 사건 시작/1000", "GV_flee_time": "GV FLEE 몫", "GC_flight_unsafe": "GC 잡힘·잘림 몫",
         "GG_caught": "GG 잡힘", "GG_starved": "GG 굶음", "GG_alive": "GG 산", "GG_chase": "GG 쫓긴 초"}
PCT = {"P1_N_hide", "GH_flight_caught", "GN_caught", "GN_starved", "GN_alive", "GV_flee_time", "GC_flight_unsafe", "GG_caught", "GG_starved", "GG_alive"}


def f(x, nd=2, sign=True):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    s = f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"
    return s.replace("-", "−")


def val(cell: str, x: float, nd: int = 2, sign: bool = True) -> str:
    return f(x * 100.0, nd, sign) if cell in PCT else f(x, nd + 1, sign)


def unit(cell: str) -> str:
    return "%p" if cell in PCT else ("초" if cell == "GG_chase" else "")


def pm_changed(name: str) -> str:
    import pilot_mask5 as pm

    v = pm.VARIANTS.get(name, {})
    return pm.TREE_REGION if v.get("trees") else (v.get("weather") or ("—",))[0]


def cand_key(tag: str):
    m = re.match(r"s(\d+)(_fc[0-9.]+)?_(\d+)M", tag)
    return (int(m.group(3)), int(m.group(1)), m.group(2) or "") if m else (99, 99, tag)


def write(S: dict, path: Path) -> None:
    V = S["variants"]
    names = list(V)
    main = [n for n in names if not n.endswith("_off")]                  # 크기 고르기 셈 (대조 _off 는 표에만 — 모아 셈에는 넣지 않는다)
    L = ["# 판 5 두뇌(R7e) 실시간 고리 예비 측정 — 표 (자동 생성: pilot_mask5_analyze.py, 손으로 고치지 않는다)", "",
         "- 보고만 — 관문 크기를 고르는 자료다. 판정이 아니다. 시드는 예비 시드 34900~34999 만(관문 시드 35000~35199 안 씀), 시험 폴더(실제 폴더 Saved/EcoAdapt 안 씀).",
         "- 셈은 live.py 함수 그대로(시드마다 지역 셋 분자·분모 합 → 짝 차이 r4_eval.paired → 문턱 live.t_crit). 관문 꼴 판정(gate_fast)은 live.gate_live 의 t 칸과 "
         "후보마다 같은 t 를 내는지 맞춰 봤다: " + ", ".join(f"{k} {v['candidates']} 후보 |t 차이| ≤ {v['worst_t_diff']:.0e}" for k, v in S["check_fast"].items()),
         "- 두뇌 이름: current = 지금 두뇌 R7e(`ckpt/v3/v3_r7_g995_s1_20m.zip`), s<모델 시드>_<학습 스텝> = 그 변형 T 세계(판 5 · 켠 세계, R7 조리법·λ 0.98)에서 "
         "R7e 를 이어 배운 후보, same = R7e 를 한 번 더(같은 두뇌 두 번).", "- 판 길이 900·1800·2700·3600 스텝 = 2·4·6·8 분 (한 판에서 그 길이로 끊은 기록).", ""]
    # 1. 변형
    L += ["## 1. 환경 변화 (변형)", "", "| 변형 | 바뀜 | 후보 | 벽시계 초 | 학습 스텝/초 | 평가기 세계-스텝/초 (프로세스당) | T 세계 f_dec (잰 값) |", "|---|---|---|---|---|---|---|"]
    for n in names:
        v = V[n]
        t = v["times"]
        L.append(f"| {n} | {v['label']} | {', '.join(sorted(v['candidates'], key=cand_key))} | {f(v.get('wall_s'), 0, False)} | "
                 f"{f(t.get('train_steps_per_sec'), 0, False)} | {f(t.get('native_steps_per_s_mean'), 0, False)} | {f(v.get('f_dec_T'), 6, False)} |")
    L.append("")
    # 2. 지금 두뇌 수준
    L += ["## 2. 지금 두뇌(R7e) — 변형마다 판 길이별 값 (시드 100 × 지역 셋, 전체 합)", "",
          "| 변형 | 세계 | 길이 | 사건 숨음 비율 | 사건 잡힘 비율 | 쫓긴 사건/시드 | 잡힌 몫 | 굶은 몫 | GE 사건 시작/1000 | GF 도망 시작/1000 | GV FLEE 몫 | 시드마다 숨음 비율 sd %p |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in names:
        for w in ("N", "G"):
            for h in HS:
                x = V[n]["current"].get(f"{w}{h}")
                if x is None:
                    continue
                L.append(f"| {n} | {w} | {h} | {f(x['ep_hide'] * 100, 2, False)}% | {f(x['ep_caught'] * 100, 2, False)}% | {f(x['ep_chased_per_seed'], 1, False)} | "
                         f"{f(x['caught'] * 100, 2, False)}% | {f(x['starved'] * 100, 2, False)}% | {f(x['ge'], 3, False)} | {f(x['gf'], 3, False)} | "
                         f"{f(x['gv'] * 100, 2, False)}% | {f(x['hide_seed_sd'] * 100, 2, False)} |")
    L.append("")
    # 2-1. 지역마다
    L += ["### 2-1. 지역마다 사건 숨음 비율 (N 1800, 전체 합) — 지금 두뇌와 후보 차이 %p", "",
          "| 변형 | 바뀐 지역 | 지역 | 지금 | " + " | ".join(["1M 평균 차이", "2M 평균 차이", "4M 평균 차이"]) + " |", "|---|---|---|---|---|---|---|"]
    for n in names:
        rg = V[n].get("region_N1800") or {}
        if "current" not in rg:
            continue
        ch = pm_changed(n)
        for r, cur in sorted(rg["current"].items()):
            cols = []
            for S_ in (1, 2, 4):
                ds = [rg[c][r]["hide"] - cur["hide"] for c in V[n]["candidates"] if cand_key(c)[0] == S_ and c in rg]
                cols.append(f(np.mean(ds) * 100) if ds else "—")
            L.append(f"| {n} | {ch} | {r} | {cur['hide'] * 100:.2f}% | " + " | ".join(cols) + " |")
    L.append("")
    # 3. P1 짝 흔들림
    L += ["## 3. 1차 P1 사건 숨음 비율 — 후보 − 지금 (N 세계, 시드 100): 차이 %p (짝 t) · 시드마다 짝 차이 sd %p · 짝 상관 r", "",
          "| 변형 | 후보 | " + " | ".join(f"N {h}" for h in HS) + " |", "|---|---|" + "---|" * len(HS)]
    sds = {h: [] for h in HS}
    eff = {h: [] for h in HS}
    for n in names:
        for c in sorted([b for b in V[n]["brains"] if b != "current"], key=cand_key):
            row = []
            for h in HS:
                q = V[n]["vs_current"].get(f"{c}@{h}", {}).get("P1_N_hide")
                if q is None:
                    row.append("—")
                    continue
                row.append(f"{f(q['diff'] * 100)} ({f(q['t'])}) · sd {f(q['sd'] * 100, 2, False)} · r {f(q['r'], 2)}")
                if c != "same" and n in main:
                    sds[h].append(q["sd"])
                    eff[h].append(q["diff"] / q["sd"] if q["sd"] > 0 else float("nan"))
            L.append(f"| {n} | {c} | " + " | ".join(row) + " |")
    L += ["", f"모아 셈 (변형 {len(main)} 개 — 대조 {', '.join(x for x in names if x not in main) or '없음'} 은 뺌):", "",
          "| 길이 | 후보 수 | sd 가운데값 %p | sd 범위 %p | 2 %p 가를 시드 수 | 3 %p | 5 %p | 10 %p | 차이 ÷ sd 가운데값 (시드 하나당 효과) |", "|---|---|---|---|---|---|---|---|---|"]
    for h in HS:
        if not sds[h]:
            continue
        md = float(np.median(sds[h]))
        L.append(f"| {h} | {len(sds[h])} | {f(md * 100, 2, False)} | {f(min(sds[h]) * 100, 2, False)}~{f(max(sds[h]) * 100, 2, False)} | "
                 + " | ".join(str(an.need(md, d)) for d in (0.02, 0.03, 0.05, 0.10)) + f" | {f(float(np.nanmedian(eff[h])), 3)} |")
    L.append("")
    L += ["### 3-1. 학습 스텝 S 별 — 1차 P1 차이 (모든 변형·모델 시드, 시드 100)", "",
          "| S | 후보 수 | N 1800 차이 평균 %p (범위) | t ≥ +1.984 (나아짐) | t ≤ −1.984 (나빠짐) | N 3600 차이 평균 %p | GV FLEE 몫 차이 평균 %p (N 1800) |", "|---|---|---|---|---|---|---|"]
    byS: dict = {}
    for n in main:
        for c in V[n]["candidates"]:
            byS.setdefault(cand_key(c)[0], []).append((n, c))
    for S_, items in sorted(byS.items()):
        d18 = [V[n]["vs_current"][f"{c}@1800"]["P1_N_hide"] for n, c in items if f"{c}@1800" in V[n]["vs_current"]]
        d36 = [V[n]["vs_current"][f"{c}@3600"]["P1_N_hide"] for n, c in items if f"{c}@3600" in V[n]["vs_current"]]
        gv = [V[n]["vs_current"][f"{c}@1800"]["GV_flee_time"]["diff"] for n, c in items if f"{c}@1800" in V[n]["vs_current"]]
        if not d18:
            continue
        L.append(f"| {S_}M | {len(d18)} | {f(np.mean([q['diff'] for q in d18]) * 100)} ({f(min(q['diff'] for q in d18) * 100)}~{f(max(q['diff'] for q in d18) * 100)}) | "
                 f"{sum(q['t'] >= 1.984 for q in d18)} | {sum(q['t'] <= -1.984 for q in d18)} | "
                 f"{f(np.mean([q['diff'] for q in d36]) * 100) if d36 else '—'} | {f(np.mean(gv) * 100)} |")
    L.append("")
    # 4. 지킴 칸 흔들림
    L += ["## 4. 관문 칸마다 시드 짝 흔들림 — 후보 − 지금 (시드 100, 모든 후보)", "",
          "| 칸 | 세계·길이 | sd 가운데값 | 차이 가운데값 | 나빠지는 쪽 |t| ≥ 문턱 인 후보 / 후보 수 (시드 100 문턱 1.984) | 짝 상관 r 가운데값 |", "|---|---|---|---|---|---|"]
    for cellname, (w, key, sign) in an.CELLS.items():
        for h in ((1800, 3600) if w == "N" else (1800, 3600)):
            sd_, df_, bad, tot, rr = [], [], 0, 0, []
            for n in main:
                for c in [b for b in V[n]["brains"] if b not in ("current", "same")]:
                    q = V[n]["vs_current"].get(f"{c}@{h}", {}).get(cellname)
                    if q is None:
                        continue
                    tot += 1
                    sd_.append(q["sd"])
                    df_.append(q["diff"])
                    rr.append(q["r"])
                    t = q["t"]
                    if (sign > 0 and t >= 1.984) or (sign < 0 and t <= -1.984) or (sign == 0 and t >= 1.984):
                        bad += 1
            if not tot:
                continue
            what = "1차 통과 쪽 (t ≥ +)" if sign == 0 else ("커짐" if sign > 0 else "작아짐")
            L.append(f"| {SHORT[cellname]} | {w} {h} | {val(cellname, float(np.median(sd_)), 2, False)} {unit(cellname)} | {val(cellname, float(np.median(df_)))} | "
                     f"{bad}/{tot} ({what}) | {f(float(np.nanmedian(rr)), 2)} |")
    L.append("")
    # 5. 후보 − 지금 큰 표
    for hN in (1800, 3600):
        L += [f"## 5. 후보 − 지금 (시드 100): N {hN} 칸 · G 3600 칸 — 차이 (짝 t)", "",
              "| 변형 | 후보 | " + " | ".join(SHORT[k] for k in N_CELLS) + " | " + " | ".join(SHORT[k] for k in G_CELLS) + " |",
              "|---|---|" + "---|" * (len(N_CELLS) + len(G_CELLS))]
        for n in names:
            for c in sorted([b for b in V[n]["brains"] if b != "current"], key=cand_key):
                cells = []
                for k in N_CELLS:
                    q = V[n]["vs_current"].get(f"{c}@{hN}", {}).get(k)
                    cells.append("—" if q is None else f"{val(k, q['diff'])} ({f(q['t'], 1)})")
                for k in G_CELLS:
                    q = V[n]["vs_current"].get(f"{c}@3600", {}).get(k)
                    cells.append("—" if q is None else f"{val(k, q['diff'])} ({f(q['t'], 1)})")
                L.append(f"| {n} | {c} | " + " | ".join(cells) + " |")
        L.append("")
    # 6. 관문 꼴 판정
    cfgs = ["N1800x80|G3600x40", "N1800x100|G3600x60", "N2700x80|G3600x40", "N3600x80|G3600x40", "N3600x100|G3600x60", "N900x100|G3600x40"]
    L += ["## 6. 관문 꼴 판정 (예비 시드 앞 n 개로 — 판정 아님. G4·G5·G6 은 빼고 t 칸만, δ_H 0)", "",
          "통과 = 1차 P1 과 지킴 t 칸 모두. '1차 (t)' = 1차를 못 넘음, 지킴 이름 = 걸린 지킴(그 t). 첫 줄 N1800x80|G3600x40 이 지금 LIVE 크기다.", "",
          "| 변형 | 후보 | " + " | ".join(cfgs) + " |", "|---|---|" + "---|" * len(cfgs)]
    tally = []
    for cf in cfgs:
        gs = [V[n]["gates"][f"{c}|{cf}"] for n in main for c in V[n]["candidates"] if f"{c}|{cf}" in V[n]["gates"]]
        if gs:
            tally.append(f"{cf}: 후보 {len(gs)} 가운데 통과 {sum(g['passed'] for g in gs)} · 1차 못 넘음 {sum(not g['p1_ok'] for g in gs)} · "
                         f"중간 판정(앞 절반 t ≤ 0)에서 끝남 {sum(bool(g.get('interim_stop')) for g in gs)}")
    L[-3:-3] = ["모아 셈 (대조 뺌): " + " / ".join(tally), ""]
    for n in names:
        for c in sorted(V[n]["candidates"], key=cand_key):
            row = []
            for cf in cfgs:
                g = V[n]["gates"].get(f"{c}|{cf}")
                if g is None:
                    row.append("—")
                elif g["passed"]:
                    row.append(f"**통과** (P1 t {f(g['p1_t'], 1)})")
                elif not g["p1_ok"]:
                    row.append(f"1차 ({f(g['p1_diff'] * 100, 1)} %p, t {f(g['p1_t'], 1)})" + (f" + {', '.join(SHORT[k] for k in g['bad'])}" if g["bad"] else ""))
                else:
                    row.append("지킴 " + ", ".join(f"{SHORT[k]} ({f(g['bad_t'][k], 1)})" for k in g["bad"]) + f" (P1 t {f(g['p1_t'], 1)})")
            L.append(f"| {n} | {c} | " + " | ".join(row) + " |")
    L.append("")
    # 7. A/A
    L += ["## 7. 같은 두뇌 두 번 (A/A)", ""]
    same = [(n, V[n]["vs_current"]) for n in names if any(k.startswith("same@") for k in V[n]["vs_current"])]
    for n, vc in same:
        mx = max(abs(q["diff"]) for k, row in vc.items() if k.startswith("same@") for q in row.values())
        ts = {q["t"] for k, row in vc.items() if k.startswith("same@") for q in row.values()}
        L.append(f"- (가) 그대로 두 번 ({n} same — R7e 를 더 견줄 두뇌로 한 번 더): 판 길이 넷 × 칸 열다섯 모든 차이의 |최댓값| = {mx:g}, 짝 t = {sorted(ts)} "
                 "— 판정이 결정적이라 같은 두뇌는 차이가 정확히 0 이다. 1차는 '차이 > 0' 이라 같은 두뇌는 늘 기각, 지킴은 t 0 이라 늘 통과.")
    L += ["- (나) 시드를 섞은 같은 두뇌 (부트스트랩 — 지금 두뇌의 시드 100 개에서 '지금'·'후보'를 따로 복원 추출, 효과가 없는 두뇌. 변형마다 4000 번. "
          "두 번 보기 = 앞 절반 짝 t ≤ 0 이면 중간 기각):", "",
          "| 크기 (N 길이 × 시드 · G 길이 × 시드) | 1차 우연 통과 몫 (변형 평균, 범위) | 1차 t sd (1 이면 t 분포대로) | 지킴 하나 이상 우연히 걸림 (평균, 범위) | 모두 통과 (한 번 보기) | "
          "중간 기각 몫 | 두 번 보기로 모두 통과 | 칸마다 걸림 (변형 평균) |", "|---|---|---|---|---|---|---|---|"]
    keys = []
    for n in names:
        for k in S["aa"].get(n, {}):
            if k not in keys:
                keys.append(k)
    for k in keys:
        rows = [S["aa"][n][k] for n in names if k in S["aa"].get(n, {})]
        p1 = [r["p1_pass"] for r in rows]
        ag = [r["any_guard_fail"] for r in rows]
        pa = [r["pass_all"] for r in rows]
        per = {g: float(np.mean([r["guard_fail"][g] for r in rows])) for g in an.GUARDS}
        top = " · ".join(f"{SHORT[g]} {per[g] * 100:.1f}%" for g in sorted(per, key=lambda g: -per[g]) if per[g] > 0)
        tsd = float(np.mean([r["p1_t_sd"] for r in rows]))
        fut = float(np.mean([r.get("interim_stop", float("nan")) for r in rows]))
        pseq = float(np.mean([r.get("pass_all_seq", float("nan")) for r in rows]))
        L.append(f"| {k} | {np.mean(p1) * 100:.2f}% ({min(p1) * 100:.2f}~{max(p1) * 100:.2f}) | {tsd:.2f} | {np.mean(ag) * 100:.1f}% ({min(ag) * 100:.1f}~{max(ag) * 100:.1f}) | "
                 f"{np.mean(pa) * 100:.2f}% | {fut * 100:.1f}% | {pseq * 100:.2f}% | {top} |")
    L.append("")
    # 8. 검정력
    L += ["## 8. 검정력 어림 (1차 P1 — 짝 t 한쪽, 비중심 t. sd = 3절 후보 sd 가운데값)", "",
          "| N 길이 | sd %p | 시드 n | +0.5 %p | +1 %p | +2 %p | +3 %p | δ_H 1 %p 일 때 +1 · +2 %p | 중간 판정(앞 절반 t ≤ 0)에서 멈출 몫: 0 · +0.5 · +1 %p |",
          "|---|---|---|---|---|---|---|---|---|"]
    for h in HS:
        if not sds[h]:
            continue
        md = float(np.median(sds[h]))
        for nn in (40, 60, 80, 100, 120):
            L.append(f"| {h} | {md * 100:.2f} | {nn} | " + " | ".join(f"{an.power(d, md, nn) * 100:.0f}%" for d in (0.005, 0.01, 0.02, 0.03)) + " | "
                     + " · ".join(f"{an.power(d, md, nn, 0.01) * 100:.0f}%" for d in (0.01, 0.02)) + " | "
                     + " · ".join(f"{an.futility_stop(d, md, nn) * 100:.0f}%" for d in (0.0, 0.005, 0.01)) + " |")
    L.append("")
    path.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
