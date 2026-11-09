"""R8 그림 — 학습 곡선과 거리 띠별 도망 몫 (발표용 PNG, matplotlib).

`herbivore_rl/` 에서 (PYTHONUTF8=1):
    python results/v3/r8/plot_curve.py curve        # logs/<실행>.log.jsonl + checkpoints/<점검>/summary.json → checkpoints/curve.png
    python results/v3/r8/plot_curve.py bands --summary results/v3/r8/eval/summary.json --out results/v3/r8/eval/bands.png
    python results/v3/r8/plot_curve.py curve --talk --out <발표 자료 폴더>/curve_talk.png    # 발표용 (아래 talk)

curve (2 × 2):
  (가) 잡힘 /1000 사슴-스텝 — 학습 세계 기록, 점선 = 보정 때 늘 먹기(개발 시드).
  (나) 번식 /1000 사슴-스텝 — 먹기를 배우는가.
  (다) 도망 몫, 가장 가까운 동물이 늑대(실선)·짐승(점선)이고 15 단위 안일 때 — 학습 세계 기록(숨은 종류는 기록에만 쓴다).
  (라) 점검 세계(41800~41839) 의 Δ = 늑대 도망 몫 − 짐승 도망 몫과 95% 구간 — `watch_train.py` 가 남긴 체크포인트 점검.
talk (curve --talk, 11-05 덧붙임 — 기본 curve 출력은 그대로): 같은 학습 기록으로 큰 글자 칸 셋 — 늑대에게 잡힘 · 먹은 양 · 도망친 몫
  (가까이 온 동물이 늑대 빨강 / 짐승 갈색 점선, R8 실행만). R8 시드는 한 색, 대조 H0 는 회색 점선, 가로 점선 = 보정 때 늘 먹기(개발 시드).
  --out 을 주지 않으면 checkpoints/curve_talk.png (지켜보기가 쓰는 checkpoints/curve.png 는 건드리지 않는다). --note = 오른쪽 아래 작은 글(초안 표시).
bands: 판정 평가 summary.json 의 정책마다 거리 띠 [0,5)·[5,10)·[10,15) 의 늑대·짐승 도망 몫 막대.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
LOGS = HERE.parent / "logs"
CKPT = ROOT / "ckpt" / "r8"

DEFAULT_RUNS = ["r8_p_s0", "r8_p_s1", "r8_p_s2", "r8_h0_s0"]
AE_CALIB = dict(caught_1k=1.019, repro_1k=14.905)  # calib/calibrate_review.json ALWAYS_EAT (개발 시드 41400~41449)
COLORS = {"s0": "#1f77b4", "s1": "#ff7f0e", "s2": "#2ca02c", "h0": "#7f7f7f"}


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def _color(run: str) -> str:
    if "h0" in run:                                  # r8_h0_s0 도 s0 로 끝나므로 대조를 먼저 본다
        return COLORS["h0"]
    for k, c in COLORS.items():
        if run.endswith(k) or f"_{k}_" in run:
            return c
    return "#9467bd"


def _label(run: str) -> str:
    return f"{run} (대조: 짐승 없이 배움)" if "h0" in run else run


def _rows(run: str) -> list[dict]:
    p = LOGS / f"{run}.log.jsonl"
    out = []
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    # 학습 끝에 덧붙는 마지막 줄(final)은 남은 몇만 걸음만 모아 점 하나가 크게 튄다(11-06: 4천~6만 걸음 대 다른 줄 1천만) — 앞 줄의 10% 보다 작으면 뺀다.
    if len(out) > 1 and out[-1].get("final") and out[-1].get("deer_steps", 0) < 0.1 * out[-2].get("deer_steps", 0):
        out.pop()
    return out


def _checks(check_dir: Path, runs: list[str]) -> dict:
    """{실행: [(결정 M, Δ, 아래, 위)]} — m<k>/ 와 final/ 의 summary.json 에서."""
    out = {r: [] for r in runs}
    if not check_dir.exists():
        return out
    for d in sorted(check_dir.iterdir()):
        p = d / "summary.json"
        if not d.is_dir() or not p.exists():
            continue
        try:
            js = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for lab, m in js.get("results", {}).items():
            for run in runs:
                if d.name == "final" and lab == run:
                    meta = CKPT / f"{run}.json"
                    x = json.loads(meta.read_text(encoding="utf-8"))["timesteps"] / 1e6 if meta.exists() else None
                elif d.name.startswith("m") and lab == f"{run}_{int(d.name[1:])}m":
                    x = float(int(d.name[1:]))
                else:
                    continue
                if x is None:
                    continue
                ci = m.get("delta_ci") or [float("nan"), float("nan")]
                out[run].append((x, float(m["delta"]), float(ci[0]), float(ci[1])))
    for r in out:
        out[r].sort()
    return out


def draw_curve(runs: list[str], check_dir: Path, out_png: Path, target: int | None = None) -> Path:
    plt = _plt()
    fig, ax = plt.subplots(2, 2, figsize=(13, 8.5))
    (a, b), (c, d) = ax
    for run in runs:
        rows = _rows(run)
        if not rows:
            continue
        x = [r["timesteps"] / 1e6 for r in rows]
        col = _color(run)
        a.plot(x, [r["caught_per_1k"] for r in rows], color=col, label=_label(run), lw=1.6, ls="--" if "h0" in run else "-")
        b.plot(x, [r["repro_per_1k"] for r in rows], color=col, label=_label(run), lw=1.6, ls="--" if "h0" in run else "-")
        fw = [(xi, r["flee_wolf"]) for xi, r in zip(x, rows) if r.get("flee_wolf") is not None]
        fb = [(xi, r["flee_beast"]) for xi, r in zip(x, rows) if r.get("flee_beast") is not None]
        if fw:
            c.plot(*zip(*fw), color=col, lw=1.6, label=f"{run} 늑대")
        if fb:
            c.plot(*zip(*fb), color=col, lw=1.2, ls=":", label=f"{run} 짐승")
    a.axhline(AE_CALIB["caught_1k"], color="k", ls=":", lw=1)
    a.text(0.99, AE_CALIB["caught_1k"], " 늘 먹기(보정)", transform=a.get_yaxis_transform(), ha="right", va="bottom", fontsize=8)
    b.axhline(AE_CALIB["repro_1k"], color="k", ls=":", lw=1)
    b.text(0.99, AE_CALIB["repro_1k"], " 늘 먹기(보정)", transform=b.get_yaxis_transform(), ha="right", va="bottom", fontsize=8)
    a.set_title("(가) 늑대에게 잡힘 / 1000 사슴-스텝 (낮을수록 좋다)")
    b.set_title("(나) 번식 / 1000 사슴-스텝 (먹기를 배우는가)")
    c.set_title("(다) 도망 몫: 가장 가까운 동물이 늑대(실선) / 짐승(점선)")
    for axx in (a, b, c):
        axx.set_xlabel("학습한 결정 (백만)")
        axx.grid(alpha=0.3)
    a.legend(fontsize=8)
    c.legend(fontsize=7, ncol=2)
    ch = _checks(check_dir, runs)
    any_pt = False
    for run, pts in ch.items():
        if not pts:
            continue
        any_pt = True
        xs, ds, lo, hi = zip(*pts)
        col = _color(run)
        d.errorbar(xs, ds, yerr=[[di - li for di, li in zip(ds, lo)], [hi_ - di for di, hi_ in zip(ds, hi)]], color=col, marker="o", ms=4,
                   capsize=3, lw=1.4, ls="--" if "h0" in run else "-", label=_label(run))
    d.axhline(0.0, color="k", lw=1)
    d.set_title("(라) 점검 세계 Δ = 늑대 도망 몫 − 짐승 도망 몫 (95% 구간)")
    d.set_xlabel("체크포인트 (백만 결정)")
    d.grid(alpha=0.3)
    if any_pt:
        d.legend(fontsize=8)
    else:
        d.text(0.5, 0.5, "아직 점검 없음", transform=d.transAxes, ha="center", va="center", color="gray")
    if target:
        for axx in (a, b, c, d):
            axx.set_xlim(0, target / 1e6 * 1.02)
    fig.suptitle("R8 — 이름표 없이 위험을 스스로 배우는 사슴: 학습 곡선", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=130)
    plt.close(fig)
    return out_png


TALK = dict(bg="#F5F3EC", ink="#1B2A2F", muted="#5A6468", grid="#E0DCD1", r8="#1F6F6B", h0="#7D858A",
            wolf="#d62728", beast="#8c564b")      # 7·8주차 덱 색 + r8_replay 의 늑대·짐승 색


def draw_curve_talk(runs: list[str], out_png: Path, note: str | None = None) -> Path:
    """발표용 학습 곡선 (curve --talk): 큰 글자, 칸 셋 — 잡힘 · 먹음 · 늑대/짐승 앞 도망 몫. 값은 `draw_curve` 와 같은 학습 기록(logs/<실행>.log.jsonl).
    R8 시드들은 한 색(같은 두뇌 설계의 되풀이), 대조 H0 는 회색 점선. 도망 칸은 R8 만 — 색이 '가까이 온 동물' (늑대 빨강·짐승 갈색)."""
    plt = _plt()
    T = TALK
    rc = {"font.size": 15, "axes.edgecolor": "#C4C2BC", "axes.labelcolor": T["ink"], "xtick.color": T["muted"],
          "ytick.color": T["muted"], "text.color": T["ink"]}
    with plt.rc_context(rc):
        return _draw_curve_talk(plt, T, runs, out_png, note)


def _draw_curve_talk(plt, T: dict, runs: list[str], out_png: Path, note: str | None) -> Path:
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(16, 5.6), facecolor=T["bg"])
    data = {run: _rows(run) for run in runs}
    xmax = max([r["timesteps"] / 1e6 for rows in data.values() for r in rows] or [1.0])
    seen_r8 = seen_h0 = False
    fmax = 0.0
    for run, rows in data.items():
        if not rows:
            continue
        x = [r["timesteps"] / 1e6 for r in rows]
        h0 = "h0" in run
        kw = dict(color=T["h0"], ls="--", lw=2.4) if h0 else dict(color=T["r8"], lw=2.6, alpha=0.85)
        lab = None
        if h0 and not seen_h0:
            lab, seen_h0 = "대조: 짐승 없는 세계에서 배움", True
        elif not h0 and not seen_r8:
            lab, seen_r8 = "R8 (두뇌마다 한 줄)", True
        a.plot(x, [r["caught_per_1k"] for r in rows], label=lab, **kw)
        b.plot(x, [r["eaten_e_x1000"] for r in rows], label=lab, **kw)
        if not h0:
            fw = [(xi, 100 * r["flee_wolf"]) for xi, r in zip(x, rows) if r.get("flee_wolf") is not None]
            fb = [(xi, 100 * r["flee_beast"]) for xi, r in zip(x, rows) if r.get("flee_beast") is not None]
            fmax = max([fmax] + [v for _, v in fw + fb])
            if fw:
                c.plot(*zip(*fw), color=T["wolf"], lw=2.6, alpha=0.85)
            if fb:
                c.plot(*zip(*fb), color=T["beast"], lw=2.6, alpha=0.85, ls=(0, (4, 2)))
    for ax_, ref in ((a, AE_CALIB["caught_1k"]), (b, 7.909)):              # 7.909 = calib/calibrate_review.json ALWAYS_EAT 먹음 (개발 시드)
        ax_.axhline(ref, color=T["ink"], ls=":", lw=1.8)
        ax_.text(0.98, ref, "늘 먹기", transform=ax_.get_yaxis_transform(), ha="right", va="bottom", fontsize=14, color=T["ink"])
    a.set_ylim(0, max(a.get_ylim()[1], AE_CALIB["caught_1k"] * 1.15))
    b.set_ylim(bottom=0)
    c.set_ylim(0, 50)                                   # 처음 1M(무작위에 가까운 두뇌)의 80% 대는 칸 위로 잘린다 — 잘리면 작게 적는다
    if fmax > 50:
        c.text(0.07, 0.985, f"↑ 처음 {fmax:.0f}% (거의 무작위)", transform=c.transAxes, ha="left", va="top", fontsize=12, color=T["muted"])
    a.set_title("늑대에게 잡힘 ↓", fontsize=19, fontweight="bold", loc="left")
    b.set_title("먹은 양 ↑", fontsize=19, fontweight="bold", loc="left")
    c.set_title("도망친 몫 — 가까이 온 동물이", fontsize=19, fontweight="bold", loc="left")
    a.set_ylabel("사슴 1000 걸음마다 잡힌 수")
    b.set_ylabel("사슴 한 걸음마다 먹은 양 (×1000)")
    c.set_ylabel("도망친 몫 (%)")
    from matplotlib.lines import Line2D

    c.legend(handles=[Line2D([0], [0], color=T["wolf"], lw=3, label="늑대일 때"),
                      Line2D([0], [0], color=T["beast"], lw=3, ls=(0, (4, 2)), label="짐승일 때")], fontsize=14, frameon=False, loc="lower right")
    if seen_r8 or seen_h0:
        a.legend(fontsize=13, frameon=False, loc="center right")
    for ax_ in (a, b, c):
        ax_.set_facecolor(T["bg"])
        ax_.set_xlabel("학습량 (백만 번 결정)")
        ax_.set_xlim(0, xmax * 1.02)
        ax_.grid(color=T["grid"], lw=1)
        for sp in ("top", "right"):
            ax_.spines[sp].set_visible(False)
    if note:
        fig.text(0.995, 0.01, note, ha="right", va="bottom", fontsize=11, color="#8A8F91")
    fig.tight_layout(rect=(0, 0.03 if note else 0, 1, 1), w_pad=2.5)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150, facecolor=T["bg"])
    plt.close(fig)
    return out_png


def draw_bands(summary: Path, out_png: Path, policies: list[str] | None = None) -> Path:
    plt = _plt()
    js = json.loads(summary.read_text(encoding="utf-8"))
    res = js["results"]
    names = policies or [k for k in res if k not in ("RANDOM", "ALWAYS_EAT")]
    names = [n for n in names if n in res]
    fig, axs = plt.subplots(1, len(names), figsize=(3.2 * len(names), 3.8), sharey=True, squeeze=False)
    bands = ["0~10 m", "10~20 m", "20~30 m"]                 # 5 단위 = 10 m
    for ax, n in zip(axs[0], names):
        m = res[n]
        xs = range(3)
        ax.bar([x - 0.2 for x in xs], m["F_wolf"], width=0.4, color="#d62728", label="늑대")
        ax.bar([x + 0.2 for x in xs], m["F_beast"], width=0.4, color="#8c564b", label="해 없는 짐승")
        ax.set_xticks(list(xs), bands, fontsize=8)
        ci = m.get("delta_ci") or [float("nan"), float("nan")]
        ax.set_title(f"{n}\nΔ {m['delta']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] ρ {m['rho']:.2f}", fontsize=9)
        ax.grid(axis="y", alpha=0.3)
    axs[0][0].set_ylabel("도망 몫 (뛰기·은신처)")
    axs[0][0].legend(fontsize=8)
    a = js.get("args", {})
    fig.suptitle(f"가장 가까운 동물까지 거리별 도망 몫 — 세계 {a.get('seeds', ['?', '?'])[0]}~{a.get('seeds', ['?', '?'])[1]}", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=130)
    plt.close(fig)
    return out_png


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("curve")
    p.add_argument("--runs", nargs="*", default=DEFAULT_RUNS)
    p.add_argument("--checks", default=str(HERE.parent / "checkpoints"))
    p.add_argument("--out", default=None, help="기본 checkpoints/curve.png (--talk 면 checkpoints/curve_talk.png)")
    p.add_argument("--target", type=int, default=250_000_000)
    p.add_argument("--talk", action="store_true", help="발표용: 큰 글자, 칸 셋 (잡힘·먹음·늑대/짐승 앞 도망 몫)")
    p.add_argument("--note", default=None, help="--talk 그림 오른쪽 아래 작은 글 (초안 표시 등)")
    q = sub.add_parser("bands")
    q.add_argument("--summary", default=str(HERE.parent / "eval" / "summary.json"))
    q.add_argument("--out", default=str(HERE.parent / "eval" / "bands.png"))
    q.add_argument("--policies", nargs="*", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "curve" and args.talk:
        out = draw_curve_talk(args.runs, Path(args.out or HERE.parent / "checkpoints" / "curve_talk.png"), note=args.note)
    elif args.cmd == "curve":
        out = draw_curve(args.runs, Path(args.checks), Path(args.out or HERE.parent / "checkpoints" / "curve.png"), target=args.target)
    else:
        out = draw_bands(Path(args.summary), Path(args.out), args.policies)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
