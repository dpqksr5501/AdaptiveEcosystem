"""S1-a 진단 A2 — 학습 경과 그림 → a2/timecourse.png.

    # herbivore_rl/ 에서 (a2_timecourse.py, a2_eval10m.py 다음)
    python results/v2/s1a_diag/a2/a2_plot.py

- 왼쪽 세 칸: 학습 롤아웃 기록(1M 창 평균) reward_per_step · mean_energy · forage_mean. 모델 14개, 나쁨 4 / 좋음 9 / 경계 1
- 오른쪽 칸: 10M 중간 저장과 20M 최종의 짧은 평가 G_γ(결정 모드, 평가 시드 10000~10009 × 3000스텝). 점선 = C2
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve()
T = json.loads((HERE.parent / "timecourse.json").read_text(encoding="utf-8"))
C = json.loads((HERE.parent / "curves.json").read_text(encoding="utf-8"))
E = json.loads((HERE.parent / "eval10m.json").read_text(encoding="utf-8"))
LAB = C["labels"]
COL = {"good": "#2a78d6", "bad": "#eb6834", "border": "#8a8984"}
NAME = {"good": "좋음 (9)", "bad": "나쁨 (4)", "border": "경계 s21"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({"font.family": ["Malgun Gothic", "DejaVu Sans"], "axes.unicode_minus": False,
                     "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "text.color": INK})


def main() -> int:
    fig, axes = plt.subplots(1, 4, figsize=(15, 3.8), facecolor="#fcfcfb")
    grid = T["grid"]
    panels = [("rollout/reward_per_step", "학습 보상/스텝"), ("world/mean_energy", "학습 세계 평균 에너지"),
              ("act/forage_mean", "forage 행동 평균(표본)")]
    for ax, (tag, title) in zip(axes, panels):
        V = T["tags"][tag]["values"]
        for kind in ("good", "border", "bad"):
            first = True
            for m, v in V.items():
                if LAB[m] != kind:
                    continue
                ax.plot(grid, v, color=COL[kind], lw=2 if kind == "bad" else 1.2,
                        ls="--" if kind == "border" else "-", alpha=1 if kind == "bad" else 0.7,
                        label=NAME[kind] if first else None)
                first = False
        ax.set_title(title, fontsize=10, loc="left")
        ax.set_xlabel("학습 스텝 (M)")
        ax.grid(color=GRID, lw=0.6)
        ax.set_facecolor("#fcfcfb")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].legend(frameon=False, fontsize=8, loc="lower left")
    ax = axes[3]
    mean = E["mean"]
    for k in mean:
        if "@10m" not in k:
            continue
        m = k.split("@")[0]
        g10, g20 = mean[k]["g_gamma"], mean[f"{m}@20m"]["g_gamma"]
        ax.plot([10, 20], [g10, g20], color=COL[LAB[m]], lw=2, marker="o", ms=5)
        ax.annotate(m.replace("v2_1c_", "").replace("v2_1_", ""), (20, g20), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=7.5, color=INK2)
    ax.axhline(mean["C2"]["g_gamma"], color=INK2, ls=":", lw=1)
    ax.text(10.2, mean["C2"]["g_gamma"] + 0.08, "C2", fontsize=8, color=INK2)
    ax.set_xticks([10, 20], ["10M 저장", "20M 최종"])
    ax.set_xlim(9, 22)
    ax.set_title("짧은 평가 G_γ (결정 모드)", fontsize=10, loc="left")
    ax.grid(color=GRID, lw=0.6, axis="y")
    ax.set_facecolor("#fcfcfb")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE.parent / "timecourse.png", dpi=130, facecolor=fig.get_facecolor())
    print("저장", HERE.parent / "timecourse.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
