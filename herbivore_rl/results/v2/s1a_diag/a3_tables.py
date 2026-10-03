"""A3 표 출력 — a3_overlay_summary.json·a3_tb.json 을 읽어 보고용 마크다운 표를 화면에 찍는다(파일은 쓰지 않는다).

실행(herbivore_rl 에서): python results/v2/s1a_diag/a3_tables.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def f(x, nd=3):
    return "-" if x is None else f"{x:+.{nd}f}" if isinstance(x, float) else str(x)


def main() -> None:
    s = json.loads((HERE / "a3_overlay_summary.json").read_text(encoding="utf-8"))
    M = s["models"]
    for mode in ("det", "k24"):
        print(f"\n### 전체 덧씌우기 ({mode}) G_γ 와 아사율(×1e-4), 차 (t)")
        print("| 모델 | 분류 | base G_γ | a ΔG (t) | b ΔG (t) | c ΔG (t) | base 아사 | a Δ아사 | b Δ아사 | c Δ아사 |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for name, mo in M.items():
            md = mo["modes"].get(mode, {})
            if "base" not in md:
                continue
            b = md["base"]
            cells = [name, mo["class"], f"{b['g_gamma']:+.3f}"]
            for c in ("a", "b", "c"):
                e = md.get(c)
                cells.append("-" if not e else f"{e['vs_base']['g_gamma']['diff']:+.3f} ({e['vs_base']['g_gamma']['t']:+.1f})")
            cells.append(f"{b['starve_rate'] * 1e4:.2f}")
            for c in ("a", "b", "c"):
                e = md.get(c)
                cells.append("-" if not e else f"{e['vs_base']['starve_rate']['diff'] * 1e4:+.2f}")
            print("| " + " | ".join(cells) + " |")
    for mode in ("det", "k24"):
        print(f"\n### 소수 침입 ({mode}, 침입자 16/128 의 G_γ − base 같은 슬롯) [γ 학습 / 획득량 보상 / γ0.998]")
        print("| 모델 | 분류 | ia ΔG_grp (t) | ib ΔG_grp (t) | ic ΔG_grp (t) | ic Δgain_grp | ic Δg998_grp | ic Δ피식_grp ×1e-4 | ic Δ아사_grp ×1e-4 | ic Δ번식_grp ×1e-4 |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for name, mo in M.items():
            md = mo["modes"].get(mode, {})
            if "base" not in md or not any(c in md for c in ("ia", "ib", "ic")):
                continue
            cells = [name, mo["class"]]
            for c in ("ia", "ib", "ic"):
                e = md.get(c)
                cells.append("-" if not e else f"{e['vs_base']['g_gamma_grp']['diff']:+.3f} ({e['vs_base']['g_gamma_grp']['t']:+.1f})")
            e = md.get("ic")
            if e:
                v = e["vs_base"]
                cells += [f"{v['g_gain_grp']['diff']:+.3f}" if "g_gain_grp" in v else "-",
                          f"{v['g998_grp']['diff']:+.3f}" if "g998_grp" in v else "-",
                          f"{v['pred_rate_grp']['diff'] * 1e4:+.2f}", f"{v['starve_rate_grp']['diff'] * 1e4:+.2f}",
                          f"{v['repro_rate_grp']['diff'] * 1e4:+.2f}" if "repro_rate_grp" in v else "-"]
            else:
                cells += ["-"] * 6
            print("| " + " | ".join(cells) + " |")
    print("\n### 상태 S(배고픔 & 발밑 먹이 < 0.05) 표본, base 결정 모드")
    print("| 모델 | 분류 | S 비율 | P(정지|S) | G 정지 | G 걷기 | P(아사로 끝|S 정지) | P(아사로 끝|S 걷기) | P(120스텝 안 먹이|정지) | P(120 안|걷기) | 정지 중 은신처 | 정지 중 용량0 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, mo in M.items():
        b = mo["modes"].get("det", {}).get("base")
        if not b:
            continue
        S = b["S_samples"]
        st, wk, rn = S["stop"], S["walk"], S["run"]
        n = st["n"] + wk["n"] + rn["n"]
        print("| " + " | ".join([
            name, mo["class"], f"{b['S_frac']:.3f}", f"{st['n'] / n:.3f}" if n else "-",
            f"{st['G_mean']:+.3f}" if st["G_mean"] is not None else "-",
            f"{wk['G_mean']:+.3f}" if wk["G_mean"] is not None else "-",
            f"{st['p_end_starve']:.3f}" if st.get("p_end_starve") is not None else "-",
            f"{wk['p_end_starve']:.3f}" if wk.get("p_end_starve") is not None else "-",
            f"{st['p_ttf_le120']:.3f}" if st.get("p_ttf_le120") is not None else "-",
            f"{wk['p_ttf_le120']:.3f}" if wk.get("p_ttf_le120") is not None else "-",
            f"{st['p_in_cover']:.3f}" if st.get("p_in_cover") is not None else "-",
            f"{st['p_capzero']:.3f}" if st.get("p_capzero") is not None else "-",
        ]) + " |")
    print("\n### 아사 지점 (base 결정)")
    print("| 모델 | 분류 | 아사 수 | 은신처 안 | 용량 0 셀 | 직전 50스텝 정지 비율 평균 | 정지 ≥ 절반 | forage 평균(배고픔) | cover 평균 | speed 평균 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name, mo in M.items():
        b = mo["modes"].get("det", {}).get("base")
        if not b:
            continue
        ss = b.get("starve_site", {})
        am = b["act_mean_hungry"]
        a_all = b["act_mean"]
        print("| " + " | ".join([name, mo["class"], str(ss.get("n", 0)),
                                 f"{ss.get('in_cover', float('nan')):.3f}", f"{ss.get('capzero', float('nan')):.3f}",
                                 f"{ss.get('last50_stop_mean', float('nan')):.3f}",
                                 f"{ss.get('last50_stop_ge_half', float('nan')):.3f}",
                                 f"{am[0]:.3f}", f"{a_all[3]:.3f}", f"{a_all[4]:.3f}"]) + " |")
    print("\n### 보상 정의 재채점 (결정): 순변화 ΔG_γ / 획득량 ΔG (같은 궤적)")
    print("| 모델 | 분류 | a | b | c | ia grp | ib grp | ic grp |")
    print("|---|---|---|---|---|---|---|---|")
    for name, mo in M.items():
        md = mo["modes"].get("det", {})
        cells = [name, mo["class"]]
        for c, key in (("a", ""), ("b", ""), ("c", ""), ("ia", "_grp"), ("ib", "_grp"), ("ic", "_grp")):
            e = md.get(c)
            v = e["vs_base"] if e else {}
            if f"g_gamma{key}" in v and f"g_gain{key}" in v:
                cells.append(f"{v['g_gamma' + key]['diff']:+.3f} / {v['g_gain' + key]['diff']:+.3f}")
            else:
                cells.append("-")
        print("| " + " | ".join(cells) + " |")
    print("\n### 침입 γ 비교 (결정): ΔG_grp γ학습 / γ0.998")
    for name, mo in M.items():
        md = mo["modes"].get("det", {})
        out = []
        for c in ("ia", "ib", "ic"):
            e = md.get(c)
            if e and "g998_grp" in e["vs_base"]:
                out.append(f"{c} {e['vs_base']['g_gamma_grp']['diff']:+.3f}/{e['vs_base']['g998_grp']['diff']:+.3f}")
        if out:
            print(name, mo["class"], " ".join(out))
    print("\n### 묶음")
    for k, v in s.get("groups", {}).items():
        print(k, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()})


if __name__ == "__main__":
    main()
