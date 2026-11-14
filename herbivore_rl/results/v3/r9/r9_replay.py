"""R9 리플레이 그림 — 위에서 본 무대, 종별 색 궤적 (PNG 파일만 만든다, 띄우지 않음; 설계 11절·9-3 '리플레이로 장면을 본다').

`herbivore_rl/` 에서 (PYTHONUTF8=1):
    python results/v3/r9/r9_replay.py --form judge --seed 44100 --steps 1500 --out results/v3/r9/replay/judge_44100.png
    python results/v3/r9/r9_replay.py --form train --seed 44000 --steps 900 --deer A --wolf A --boar A --brain A:deer=… A:wolf=… A:boar=…

왼쪽: 궤적 전체 (배경 = 시작 풀 용량, 회색 원 = 은신처, 사슴 갈색·늑대 빨강·멧돼지 짙은 회색, 늑대 선은 굵게). × = 물려 죽은 자리
(색 = 죽은 종), ○ = 굶어 죽음, ★ = 반격으로 죽은 늑대, + = 판정 세계 출생. 오른쪽: 첫 물려 죽음 ±40 스텝 장면(없으면 마지막 80 스텝).
판정 시드(44800~44999)는 판정 결과(eval/judge.json, judged = true)가 생긴 뒤에만 받는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for _p in (ROOT, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

import eval_r9 as EV  # noqa: E402
import r9_eval_core as C  # noqa: E402
from env_v2 import r9_body as B  # noqa: E402

SP_COL = {0: "#8c6d31", 1: "#d62728", 2: "#3a3a3a"}
SP_LW = {0: 0.6, 1: 1.6, 2: 0.9}


def guard_seed(seed: int) -> None:
    if C.is_judge_seed(seed):
        js = HERE.parent / "eval" / "judge.json"
        ok = js.exists() and bool(json.loads(js.read_text(encoding="utf-8")).get("judged"))
        if not ok:
            raise C.JudgeSeedError(f"시드 {seed} 는 판정 시드다 — 판정(eval/judge.json, judged) 전에는 쓰지 않는다. 초안은 개발 44000~44199")


def record(cfg: dict, seed: int, steps: int, specs: dict, brains: dict) -> dict:
    stoch = cfg["world"]["mode"] == "judge" and not bool(cfg["judge"]["greedy"])
    rec = C.run(cfg, [seed], steps, EV.spec_fn(cfg, specs, brains, stochastic=stoch), scenes=False, traj_worlds=[0])
    caps = [int(cfg["world"]["slots"][n]) for n in B.SPECIES]
    rec["slot_sp"] = np.repeat(np.arange(3), caps)
    return rec


def _tracks(tr: dict, t0: int, t1: int):
    """Per slot list of (species-agnostic) polylines between steps t0..t1, split where the uid changes or the slot is empty."""
    pos, alive, uid, ts = tr["pos"], tr["alive"], tr["uid"], tr["t"]
    sel = (ts >= t0) & (ts <= t1)
    P, A, U = pos[sel], alive[sel], uid[sel]
    out = []
    for s in range(P.shape[1]):
        seg = []
        for i in range(P.shape[0]):
            if A[i, s] and (not seg or U[i, s] == seg[-1][1]):
                seg.append((P[i, s], U[i, s]))
            else:
                if len(seg) > 1:
                    out.append((s, np.array([p for p, _ in seg])))
                seg = [(P[i, s], U[i, s])] if A[i, s] else []
        if len(seg) > 1:
            out.append((s, np.array([p for p, _ in seg])))
    return out


def draw(rec: dict, out: Path, title: str) -> Path:
    from matplotlib.patches import Circle

    import plot_r9

    plt = plot_r9._plt()                                        # Agg + 한글 글꼴

    tr = rec["traj"][0]
    size = float(rec["size"])
    ssp = rec["slot_sp"]
    deaths = [d for d in rec["deaths"] if int(d["k"]) == 0]
    births = [b for b in rec["births"] if int(b["k"]) == 0]
    bite = [d for d in deaths if d["cause"] == "bite"]
    tmax = int(tr["t"][-1]) if len(tr["t"]) else 0
    if bite:
        tc = int(bite[0]["t"])
        win = (max(0, tc - 40), tc + 40)
    else:
        win = (max(0, tmax - 80), tmax)
    fig, axes = plt.subplots(1, 2, figsize=(15, 7.5))
    for ax, (t0, t1), sub in ((axes[0], (0, tmax), "궤적 전체"), (axes[1], win, f"장면 {win[0]}~{win[1]} 스텝")):
        ax.imshow(rec["grass_cap"][0], origin="lower", extent=(0, size, 0, size), cmap="Greens", alpha=0.45, vmin=0)
        cc, rr = rec["cov"][0]
        for c, r in zip(cc, rr):
            ax.add_patch(Circle((c[0], c[1]), r, color="#9e9e9e", alpha=0.35, lw=0))
        for s, line in _tracks(tr, t0, t1):
            sp = int(ssp[s])
            ax.plot(line[:, 0], line[:, 1], color=SP_COL[sp], lw=SP_LW[sp], alpha=0.85)
            ax.plot(line[-1, 0], line[-1, 1], "o", color=SP_COL[sp], ms=2.5 if sp != 1 else 4)
        for d in deaths:
            if not (t0 <= int(d["t"]) <= t1):
                continue
            sp = int(d["sp"])
            mk = {"bite": "x", "starve": "o", "counter": "*"}[d["cause"]]
            ax.plot(d["x"], d["y"], mk, color=SP_COL[sp] if d["cause"] != "counter" else "black", ms=8, mfc="none" if mk == "o" else None)
        for b in births:
            if t0 <= int(b["t"]) <= t1:
                ax.plot(b["x"], b["y"], "+", color=SP_COL[int(b["sp"])], ms=6)
        ax.set_xlim(0, size)
        ax.set_ylim(0, size)
        ax.set_aspect("equal")
        ax.set_title(sub)
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/v3_r9.yaml")
    ap.add_argument("--judge-config", default="configs/v3_r9_judge.yaml")
    ap.add_argument("--form", choices=("train", "judge"), default="judge")
    ap.add_argument("--seed", type=int, default=44100)
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--deer", default="RULE_DEER")
    ap.add_argument("--wolf", default="RULE_WOLF")
    ap.add_argument("--boar", default="RULE_BOAR")
    ap.add_argument("--brain", nargs="*", default=[])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    guard_seed(args.seed)
    ct = B.load_r9_config(EV._p(args.config))
    cj = B.load_r9_config(EV._p(args.judge_config))
    cfg = cj if args.form == "judge" else B.override(ct, EV.EVAL_FACING)
    brains = C.load_brains(C.parse_brain_args(args.brain), cfg)
    specs = {B.DEER: args.deer, B.WOLF: args.wolf, B.BOAR: args.boar}
    rec = record(cfg, args.seed, args.steps, specs, brains)
    out = Path(args.out) if args.out else HERE.parent / "replay" / f"{args.form}_{args.seed}.png"
    t = f"R9 {args.form} 세계 시드 {args.seed}, {args.steps} 스텝 — 사슴 {args.deer} · 늑대 {args.wolf} · 멧돼지 {args.boar}"
    print(f"그림 {draw(rec, out, t)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
