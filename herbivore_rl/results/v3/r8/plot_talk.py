"""R8 발표용 막대 그림 — 판정 평가 summary.json 하나를 읽어 정책마다 잡힘 비·먹음 비·늑대/짐승 앞 도망 몫을 가로 막대로 (matplotlib PNG).

`herbivore_rl/` 에서 (PYTHONUTF8=1):
    python results/v3/r8/plot_talk.py --summary results/v3/r8/eval/summary.json \
        --out C:/kwon/univ/3-1/GameContentsCapstoneDesign/week9_assets/r8/talk_bars.png --split

읽는 것: `eval_r8.py eval` 의 summary.json (`write_summary` — 학습 중 점검 `checkpoints/m<k>/summary.json` 도 같은 꼴, 판정 세계만 다르다).
그리는 것 (값은 모두 summary.json 에 있는 그대로, 새로 재지 않는다):
  잡힘   = caught_1k / ALWAYS_EAT 의 caught_1k   (늘 먹기 = 1, 낮을수록 좋다. 점선 0.5 = 판정 P1 기준)
  먹은 양 = eaten_x1000 / ALWAYS_EAT 의 eaten_x1000 (늘 먹기 = 1. 점선 0.7 = 판정 P2 기준)
  도망친 몫 = 가장 가까운 느낀 동물이 늑대일 때 / 해 없는 짐승일 때 뛰기·은신처를 고른 몫. 주 Δ 와 같은 거리 띠 맞춤 가중
             (띠 [0,5)·[5,10)·[10,15), 무게 = 띠의 두 쪽 표본 수 합 — eval_r8.delta_from 과 같은 식이라 늑대 − 짐승 = Δ).
             오른쪽 '+n%p' = Δ. 진하면 delta_ci 아래 끝 > 0 (세계를 되뽑아도 늘 0 보다 큼 = 우연이 아닌 차이), 흐리면 아니다.
정책 (있는 것만, 이 차례): 늘 먹기 · 손규칙 이름표 없음(RULE_BLIND) · 손규칙 이름표 있음(RULE_ORACLE) · R8 시드 0·1·2 · 대조 H0.
  이름 끝의 `_<k>m`(점검 체크포인트)도 같은 줄로 읽고 이름표에 (kM) 를 붙인다. 없는 정책은 건너뛰고 알린다(숫자를 지어내지 않는다).
--split 이면 칸마다 따로 <out 이름>_caught.png·_eaten.png·_flee.png 도 쓴다. --note = 오른쪽 아래 작은 글(초안 표시).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/

C = dict(bg="#F5F3EC", ink="#1B2A2F", muted="#5A6468", faint="#A7ADB0", grid="#E0DCD1", edge="#C4C2BC",
         wolf="#d62728", beast="#8c564b")           # 7·8주차 덱 색 + r8_replay 의 늑대·짐승 색
POLICIES = [  # (summary 이름 또는 앞머리, 이름표, 막대 색)
    ("ALWAYS_EAT", "늘 먹기", "#B8B4A9"),
    ("RULE_BLIND", "손규칙 · 이름표 없음", "#A9B0B3"),
    ("RULE_ORACLE", "손규칙 · 이름표 있음", "#7D858A"),
    ("RULE_AIM", "손규칙 · 다가옴만 피함", "#A9B0B3"),
    ("r8_p_s0", "R8 · 시드 0", "#1F6F6B"),
    ("r8_p_s1", "R8 · 시드 1", "#1F6F6B"),
    ("r8_p_s2", "R8 · 시드 2", "#1F6F6B"),
    ("r8_h0_s0", "대조 · 짐승 없이 배움", "#7CC5BD"),
]
DEFAULT = ["ALWAYS_EAT", "RULE_BLIND", "RULE_ORACLE", "r8_p_s0", "r8_p_s1", "r8_p_s2", "r8_h0_s0"]
PANELS = ("caught", "eaten", "flee")


def find(res: dict, key: str) -> str | None:
    """summary 의 정책 이름: 같은 이름, 또는 `<key>_<k>m` (점검 체크포인트)."""
    if key in res:
        return key
    for lab in res:
        if re.fullmatch(re.escape(key) + r"_\d+m", lab):
            return lab
    return None


def weighted_flee(m: dict) -> tuple[float, float]:
    """(늑대 앞 도망 몫, 짐승 앞 도망 몫) — eval_r8.delta_from 과 같은 띠 무게."""
    Fw, Fh, nw, nh = m["F_wolf"], m["F_beast"], m["n_wolf"], m["n_beast"]
    wts = [(nw[b] + nh[b]) if (nw[b] > 0 and nh[b] > 0) else 0 for b in range(len(Fw))]
    tot = sum(wts)
    if tot <= 0:
        return float("nan"), float("nan")
    fw = sum(w * f for w, f in zip(wts, Fw)) / tot
    fh = sum(w * f for w, f in zip(wts, Fh)) / tot
    d = m.get("delta")
    if d is not None and math.isfinite(d) and abs((fw - fh) - d) > 1e-6:
        raise SystemExit(f"도망 몫 차이 {fw - fh:.6f} 가 summary 의 Δ {d:.6f} 와 다르다 — summary 꼴을 확인한다")
    return fw, fh


def rows_from(js: dict, keys: list[str]) -> list[dict]:
    res = js["results"]
    ae_lab = find(res, "ALWAYS_EAT")
    if ae_lab is None:
        raise SystemExit("summary 에 ALWAYS_EAT 가 없다 — 비를 낼 기준이 없다")
    ae = res[ae_lab]
    meta = {k: (lab, col) for k, lab, col in POLICIES}
    rows = []
    for key in keys:
        lab = find(res, key)
        if lab is None:
            print(f"알림: summary 에 {key} 가 없어 건너뛴다", file=sys.stderr)
            continue
        m = res[lab]
        name, col = meta.get(key, (key, "#1F6F6B"))
        km = re.search(r"_(\d+)m$", lab)
        if km and lab != key:
            name = f"{name} ({int(km.group(1))}M)"
        fw, fh = weighted_flee(m)
        ci = m.get("delta_ci") or [float("nan"), float("nan")]
        rows.append(dict(key=key, label=lab, name=name, color=col, caught=m["caught_1k"] / max(ae["caught_1k"], 1e-12),
                         eaten=m["eaten_x1000"] / max(ae["eaten_x1000"], 1e-12), fw=fw, fh=fh, delta=m.get("delta"),
                         sure=bool(math.isfinite(ci[0]) and ci[0] > 0), base=(lab == ae_lab)))
    if not rows:
        raise SystemExit("그릴 정책이 없다")
    return rows


def _style(ax, n: int, show_names: bool, rows: list[dict]) -> None:
    ax.set_facecolor(C["bg"])
    ax.set_yticks(range(n))
    ax.set_yticklabels([r["name"] for r in rows] if show_names else [""] * n, fontsize=16, color=C["ink"])
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", colors=C["muted"], labelsize=13)
    ax.set_ylim(n - 0.45, -0.6)
    ax.grid(axis="x", color=C["grid"], lw=1)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(C["edge"])


def panel_ratio(ax, rows: list[dict], field: str, title: str, goal: float | None, goal_txt: str, show_names: bool) -> None:
    n = len(rows)
    vals = [r[field] for r in rows]
    ax.barh(range(n), vals, height=0.62, color=[r["color"] for r in rows], edgecolor="none")
    top = max(1.0, max(vals)) * 1.28
    for i, (r, v) in enumerate(zip(rows, vals)):
        txt = "1 (기준)" if r["base"] else f"{v:.2f}배"
        ax.text(v + top * 0.015, i, txt, va="center", ha="left", fontsize=15, color=C["ink"], fontweight="normal" if r["base"] else "bold",
                bbox=dict(boxstyle="square,pad=0.1", fc=C["bg"], ec="none"), zorder=4)
    if goal is not None:
        ax.axvline(goal, color=C["ink"], ls=(0, (3, 3)), lw=1.4)
        ax.text(goal, -0.58, goal_txt, ha="center", va="bottom", fontsize=12.5, color=C["muted"])
    ax.set_xlim(0, top)
    _style(ax, n, show_names, rows)
    ax.set_title(title, fontsize=19, fontweight="bold", color=C["ink"], loc="left", pad=22)


def panel_flee(ax, rows: list[dict], show_names: bool) -> None:
    n = len(rows)
    h = 0.36
    for i, r in enumerate(rows):
        fw, fh = r["fw"], r["fh"]
        if not (math.isfinite(fw) and math.isfinite(fh)):
            ax.text(0.01, i, "표본 없음", va="center", fontsize=13, color=C["muted"])
            continue
        ax.barh(i - h / 2, 100 * fw, height=h, color=C["wolf"], edgecolor="none")
        ax.barh(i + h / 2, 100 * fh, height=h, color=C["beast"], edgecolor="none")
        if fw == 0 and fh == 0:
            ax.text(1.0, i, "도망 안 함", va="center", fontsize=14, color=C["muted"])
            continue
        ax.text(100 * fw + 1.0, i - h / 2, f"{100 * fw:.0f}%", va="center", fontsize=13, color=C["ink"])
        ax.text(100 * fh + 1.0, i + h / 2, f"{100 * fh:.0f}%", va="center", fontsize=13, color=C["ink"])
    xmax = max([100 * max(r["fw"], r["fh"]) for r in rows if math.isfinite(r["fw"]) and math.isfinite(r["fh"])] + [10.0])
    right = xmax * 1.55
    for i, r in enumerate(rows):
        d = r["delta"]
        if d is None or not math.isfinite(d) or (r["fw"] == 0 and r["fh"] == 0):
            continue
        ax.text(right * 0.985, i, f"{100 * d:+.0f}%p", va="center", ha="right", fontsize=16,
                color=C["ink"] if r["sure"] else C["faint"], fontweight="bold" if r["sure"] else "normal")
    ax.set_xlim(0, right)
    _style(ax, n, show_names, rows)
    ax.set_title("도망친 몫 — 늑대 앞 / 짐승 앞", fontsize=19, fontweight="bold", color=C["ink"], loc="left", pad=22)
    from matplotlib.patches import Patch
    from matplotlib.transforms import offset_copy

    ax.legend(handles=[Patch(color=C["wolf"], label="늑대가 가까이"), Patch(color=C["beast"], label="해 없는 짐승이 가까이")],
              loc="upper left", bbox_to_anchor=(-0.01, 0.0), bbox_transform=offset_copy(ax.transAxes, fig=ax.figure, y=-26, units="points"),
              ncol=2, fontsize=13.5, frameon=False, handlelength=1.2, columnspacing=1.2)          # 눈금 글자 아래 (높이와 무관하게 점 단위)
    ax.annotate("진한 +%p = 우연이 아닌 차이", xy=(1.0, 0.0), xycoords="axes fraction", xytext=(0, -54), textcoords="offset points",
                ha="right", va="top", fontsize=12, color=C["muted"])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")


def render(rows: list[dict], panels: list[str], out: Path, note: str | None, goals: bool) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    n = len(rows)
    widths = {"caught": 1.0, "eaten": 1.0, "flee": 1.45}
    fig, axs = plt.subplots(1, len(panels), figsize=(4.2 + sum(4.3 * widths[p] for p in panels), 1.9 + 0.62 * n), facecolor=C["bg"],
                            gridspec_kw=dict(width_ratios=[widths[p] for p in panels]), squeeze=False)
    for j, (ax, p) in enumerate(zip(axs[0], panels)):
        first = j == 0
        if p == "caught":
            panel_ratio(ax, rows, "caught", "늑대에게 잡힘 (늘 먹기 = 1)", 0.5 if goals else None, "목표: 절반 이하", first)
        elif p == "eaten":
            panel_ratio(ax, rows, "eaten", "먹은 양 (늘 먹기 = 1)", 0.7 if goals else None, "목표: 0.7 이상", first)
        else:
            panel_flee(ax, rows, first)
    if note:
        fig.text(0.995, 0.008, note, ha="right", va="bottom", fontsize=11, color="#8A8F91")
    fig.tight_layout(rect=(0, 0.035 if note else 0, 1, 1), w_pad=3.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, facecolor=C["bg"])
    plt.close(fig)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", default=str(HERE.parent / "eval" / "summary.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--policies", nargs="*", default=DEFAULT, help="summary 이름(또는 앞머리) 차례")
    ap.add_argument("--panels", nargs="*", default=list(PANELS), choices=PANELS)
    ap.add_argument("--split", action="store_true", help="칸마다 따로 그림도 쓴다")
    ap.add_argument("--no-goals", action="store_true", help="판정 기준 점선(0.5·0.7)을 뺀다")
    ap.add_argument("--note", default=None)
    args = ap.parse_args(argv)
    sp = Path(args.summary)
    js = json.loads((sp if sp.is_absolute() else ROOT / sp).read_text(encoding="utf-8"))
    rows = rows_from(js, list(args.policies))
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    a = js.get("args", {})
    print(f"summary {sp} (세계 {a.get('seeds')}, {a.get('steps')} 스텝, 만든 때 {js.get('finished')})")
    for r in rows:
        print(f"  {r['label']}: 잡힘 {r['caught']:.3f}배 먹음 {r['eaten']:.3f}배 도망 늑대 {r['fw']:.3f} 짐승 {r['fh']:.3f} "
              f"Δ {r['delta'] if r['delta'] is None else round(r['delta'], 3)} {'(우연 아님)' if r['sure'] else ''}")
    print(render(rows, list(args.panels), out, args.note, not args.no_goals))
    if args.split:
        for p in args.panels:
            print(render(rows, [p], out.with_name(f"{out.stem}_{p}{out.suffix}"), args.note, not args.no_goals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
