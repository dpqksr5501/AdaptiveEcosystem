"""R9 그림 — 종별 학습 곡선과 판정 세계 개체 수 곡선 (PNG 만 만든다, 띄우지 않음; 설계 11절).

`herbivore_rl/` 에서 (PYTHONUTF8=1):
    python results/v3/r9/plot_r9.py curves                         # results/v3/r9/logs/*.log.jsonl → results/v3/r9/plots/curves.png
    python results/v3/r9/plot_r9.py curves --logs <폴더> --out <png>
    python results/v3/r9/plot_r9.py pop --npz results/v3/r9/eval/judge_pop.npz --out results/v3/r9/plots/pop.png [--batches L_A L_B RULE]

curves: train_r9.py 의 기록 줄(<run>.log.jsonl, 줄마다 species·branch·round·timesteps + 종별 지표)을 갈래·종마다 이어 붙인다.
  x = 그 종·갈래가 배운 결정 수 누계(묶음 차례 = round, 같은 바퀴 안에서는 timesteps). 칸: 물림·굶음·출산 /1k 스텝, 먹은 E ×1000,
  뛰기·은신처 안 몫, 늑대 하루 잡이, E 중앙값. 바퀴 경계는 점선.
pop: eval_r9.py judge 가 남긴 개체 수 배열(배치마다 (T, K, 3))로 종마다 세계 평균 선 + 10~90% 띠.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
LOGS = HERE.parent / "logs"
PLOTS = HERE.parent / "plots"
SPECIES = ("deer", "wolf", "boar")
SP_COL = {"deer": "#8c6d31", "wolf": "#d62728", "boar": "#4b4b4b"}
BR_STYLE = {"A": "-", "B": "--"}
PANELS = (("bite_per_1k", "물림 /1k 스텝"), ("starve_per_1k", "굶음 /1k 스텝"), ("births_per_1k", "출산 /1k 스텝"),
          ("eaten_e_x1000", "먹은 E ×1000 /스텝"), ("act_run", "뛰기 몫"), ("in_shelter", "은신처 안 몫"),
          ("kills_per_wolf_day", "늑대 하루 잡이"), ("E_median", "E 중앙값"))


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for f in ("Malgun Gothic", "NanumGothic", "AppleGothic"):
        try:
            from matplotlib import font_manager

            if any(f in x.name for x in font_manager.fontManager.ttflist):
                plt.rcParams["font.family"] = f
                break
        except Exception:  # noqa: BLE001
            pass
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def read_logs(log_dir: Path) -> dict[tuple[str, str], list[dict]]:
    """{(branch, species): rows sorted by (round, timesteps)} from every *.log.jsonl (bad lines skipped)."""
    out: dict[tuple[str, str], list[dict]] = {}
    for f in sorted(Path(log_dir).glob("*.log.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            sp, br = r.get("species"), str(r.get("branch", "?"))
            if sp not in SPECIES or "timesteps" not in r:
                continue
            out.setdefault((br, sp), []).append(r)
    for k in out:
        out[k].sort(key=lambda r: (int(r.get("round", 0)), int(r.get("timesteps", 0))))
    return out


def cumulative_x(rows: list[dict]) -> tuple[np.ndarray, list[float]]:
    """x = decisions learned so far by that species·branch: bundle offsets = sum of the earlier bundles' last timesteps."""
    xs, bounds = [], []
    off, cur_round, cur_max = 0.0, None, 0.0
    for r in rows:
        rd = int(r.get("round", 0))
        if cur_round is not None and rd != cur_round:
            off += cur_max
            bounds.append(off)
            cur_max = 0.0
        cur_round = rd
        cur_max = max(cur_max, float(r["timesteps"]))
        xs.append(off + float(r["timesteps"]))
    return np.asarray(xs), bounds


def cmd_curves(args) -> int:
    data = read_logs(Path(args.logs))
    plt = _plt()
    fig, axes = plt.subplots(2, 4, figsize=(18, 8))
    for (br, sp), rows in sorted(data.items()):
        x, bounds = cumulative_x(rows)
        for ax, (key, title) in zip(axes.flat, PANELS):
            y = np.array([np.nan if r.get(key) is None else float(r[key]) for r in rows])
            if np.isfinite(y).any():
                ax.plot(x / 1e6, y, BR_STYLE.get(br, ":"), color=SP_COL[sp], label=f"{sp} {br}", lw=1.4)
            for bnd in bounds:
                ax.axvline(bnd / 1e6, color=SP_COL[sp], alpha=0.15, ls=":")
            ax.set_title(title)
    for ax in axes.flat:
        ax.set_xlabel("배운 결정 수 (M)")
        ax.grid(alpha=0.3)
    h, lab = axes.flat[0].get_legend_handles_labels()
    if h:
        fig.legend(h, lab, loc="upper right", ncol=6)
    fig.suptitle(f"R9 학습 곡선 ({len(data)} 개 갈래·종, {Path(args.logs)})")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(f"그림 {out} ({sum(len(v) for v in data.values())} 줄)")
    return 0


def cmd_pop(args) -> int:
    z = np.load(Path(args.npz), allow_pickle=False)
    names = [n for n in z.files if not n.endswith("__t")]
    if args.batches:
        names = [n for n in names if n in args.batches]
    plt = _plt()
    fig, axes = plt.subplots(len(names), 3, figsize=(15, 3.2 * max(len(names), 1)), squeeze=False)
    for i, n in enumerate(names):
        pop = np.asarray(z[n], dtype=np.float64)                    # (T, K, 3)
        t = np.asarray(z[n + "__t"], dtype=np.float64) if n + "__t" in z.files else np.arange(pop.shape[0]) * 2.0
        for s, sp in enumerate(SPECIES):
            ax = axes[i, s]
            y = pop[:, :, s]
            ax.fill_between(t / 900.0, np.percentile(y, 10, axis=1), np.percentile(y, 90, axis=1), color=SP_COL[sp], alpha=0.2, lw=0)
            ax.plot(t / 900.0, y.mean(1), color=SP_COL[sp], lw=1.5)
            ax.set_title(f"{n} — {sp} (세계 {y.shape[1]})")
            ax.set_xlabel("게임 일 (900 스텝)")
            ax.grid(alpha=0.3)
    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100)
    plt.close(fig)
    print(f"그림 {out} ({names})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("curves")
    p.add_argument("--logs", default=str(LOGS))
    p.add_argument("--out", default=str(PLOTS / "curves.png"))
    p = sub.add_parser("pop")
    p.add_argument("--npz", default=str(HERE.parent / "eval" / "judge_pop.npz"))
    p.add_argument("--batches", nargs="*", default=None)
    p.add_argument("--out", default=str(PLOTS / "pop.png"))
    args = ap.parse_args(argv)
    return cmd_curves(args) if args.cmd == "curves" else cmd_pop(args)


if __name__ == "__main__":
    sys.exit(main())
