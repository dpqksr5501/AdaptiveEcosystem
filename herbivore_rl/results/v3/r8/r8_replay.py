"""R8 리플레이 그림 — 위에서 본 무대 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R8_LEARN_DANGER_DESIGN.md 8-4).

    python results/v3/r8/r8_replay.py --model ckpt/r8/r8_p_s0.zip --compare always_eat --seed 41900 --steps 600 \
        --out results/v3/r8/replay/r8_s0.png

위 줄: 궤적 전체(배경 = 시작 먹이 용량, 어두운 원 = 은신처, 사슴 선 색 = 행동 — 먹기 초록·뛰기 주황·은신처 파랑·살피기 회색,
늑대 빨강·짐승 갈색, 잡힌 자리 ×). 아래 줄: 고른 장면(앞 정책에서 늑대 10 단위 안 사슴이 가장 많은 스텝) ±20 스텝 꼬리.
--model 대신 --policy 로 기준 정책(always_eat·rule_blind·rule_oracle·random)을 앞 칸에 둘 수 있다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for _p in (ROOT, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import eval_r8 as EV  # noqa: E402  ← env.torch_init 를 먼저 싣는다

import numpy as np  # noqa: E402

from env_v2.r8_world import EAT, K_BEAR, K_BEAST, K_WOLF, RUN_FIRST, RUN_LAST, SHELTER, R8World  # noqa: E402

ACT_COL = {"eat": "#2e9e44", "run": "#f08a24", "shelter": "#2a6fdb", "watch": "#8c8c8c"}
KIND_COL = {K_WOLF: "#d62728", K_BEAST: "#8c564b", K_BEAR: "#000000"}
EVAL_SEEDS = (41900, 41999)                         # 판정 평가 시드 (설계 8-1·11절)


def guard_eval_seed(seed: int, allow: bool = False) -> None:
    """판정 전에는 평가 시드를 쓰지 않는다(설계 8-1). 기본 --seed 가 41900 이라 판정 평가 결과(eval/summary.json)가 생긴 뒤에만,
    또는 --allow-eval-seed 를 줄 때만 평가 시드로 돈다. 초안은 개발 시드 41400~41449 · 점검 시드 41800~41839."""
    if EVAL_SEEDS[0] <= seed <= EVAL_SEEDS[1] and not allow and not (HERE.parent / "eval" / "summary.json").exists():
        raise SystemExit(f"시드 {seed} 는 판정 평가 시드(41900~41999)다 — 판정 평가(STATUS.md 4절 ②, eval/summary.json) 전에는 쓰지 않는다. "
                         "초안은 --seed 41400~41449(개발) 또는 41800~41839(점검). 꼭 써야 하면 --allow-eval-seed")


def record(cfg, seed: int, steps: int, policy) -> dict:
    w = R8World(cfg, [seed])
    T = int(steps)
    tr = dict(pos=[], act=[], apos=[], dead=[], catch=[], prev=None)

    def hook(wd, dead, ck):
        tr["pos"].append(wd.pos[0].copy())
        tr["act"].append(wd.act[0].copy())
        tr["apos"].append(wd.apos[0].copy())
        tr["dead"].append(dead[0].copy())
        if (ck[0] > 0).any() and tr["prev"] is not None:
            for i in np.nonzero(ck[0] > 0)[0]:
                tr["catch"].append((len(tr["pos"]) - 1, tr["prev"][i].copy(), int(ck[0, i])))
        tr["prev"] = wd.pos[0].copy()

    w.step_hook = hook
    tr["prev"] = w.pos[0].copy()
    tr["pos0"], tr["food"] = w.pos[0].copy(), w.food_cap[0].copy()
    for _ in range(T // w.D):
        a = policy(w.observe(), w)
        w.step(a)
    tr["kind"] = w.kind[0].copy()
    tr["present"] = w.present[0].copy()
    tr["cov_c"], tr["cov_r"], tr["size"] = w.cov_c, w.cov_r, w.size
    for k in ("pos", "act", "apos", "dead"):
        tr[k] = np.asarray(tr[k])
    tr["caught_n"] = int(w.st["caught_wolf"].sum() + w.st["caught_bear"].sum())
    tr["params"] = w.world_params(0)
    return tr


def act_cat(a: np.ndarray) -> np.ndarray:
    c = np.full(a.shape, "watch", dtype=object)
    c[a == EAT] = "eat"
    c[(a >= RUN_FIRST) & (a <= RUN_LAST)] = "run"
    c[a == SHELTER] = "shelter"
    return c


def draw(ax, tr: dict, t0: int, t1: int, title: str, frame: int | None = None) -> None:
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Circle

    S = tr["size"]
    ax.imshow(tr["food"], origin="lower", extent=(0, S, 0, S), cmap="Greens", vmin=0, vmax=1.0, alpha=0.55)
    for c in tr["cov_c"]:
        ax.add_patch(Circle(c, tr["cov_r"], color="#333333", alpha=0.35, lw=0))
    P, A, D = tr["pos"], tr["act"], tr["dead"]
    cats = act_cat(A)
    segs, cols = [], []
    for t in range(max(t0, 1), t1):
        ok = ~D[t] & ~D[t - 1]
        for i in np.nonzero(ok)[0]:
            segs.append([P[t - 1, i], P[t, i]])
            cols.append(ACT_COL[cats[t, i]])
    ax.add_collection(LineCollection(segs, colors=cols, linewidths=1.2, alpha=0.9))
    for a in np.nonzero(tr["present"])[0]:
        q = tr["apos"][t0:t1, a]
        ax.plot(q[:, 0], q[:, 1], color=KIND_COL[int(tr["kind"][a])], lw=1.6, alpha=0.9)
        ax.plot(q[-1, 0], q[-1, 1], "o", color=KIND_COL[int(tr["kind"][a])], ms=6 if tr["kind"][a] != K_BEAR else 9)
    if frame is not None:
        live = ~D[frame]
        ax.scatter(P[frame, live, 0], P[frame, live, 1], s=14, c=[ACT_COL[c] for c in cats[frame, live]], edgecolors="k", linewidths=0.4, zorder=5)
    for (t, p, kd) in tr["catch"]:
        if t0 <= t < t1:
            ax.plot(p[0], p[1], "x", color="k", ms=8, mew=2, zorder=6)
    ax.set_xlim(0, S)
    ax.set_ylim(0, S)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=10)


def pick_frame(tr: dict) -> int:
    P, Ap = tr["pos"], tr["apos"]
    wolves = np.nonzero(tr["present"] & (tr["kind"] == K_WOLF))[0]
    if not len(wolves):
        return len(P) // 2
    d = np.sqrt(((P[:, :, None, :] - Ap[:, None, wolves, :]) ** 2).sum(-1)).min(-1)     # (T, N)
    cnt = (d < 10.0).sum(1)
    return int(np.argmax(cnt))


def main(argv=None) -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    try:
        plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/v3_r8_pilot.yaml")
    ap.add_argument("--model", default=None)
    ap.add_argument("--policy", default=None, help="--model 대신 앞 칸 기준 정책")
    ap.add_argument("--compare", default="always_eat")
    ap.add_argument("--seed", type=int, default=41900)
    ap.add_argument("--steps", type=int, default=600)
    ap.add_argument("--bears", type=int, default=0)
    ap.add_argument("--out", default=str(HERE.parent / "replay" / "r8.png"))
    ap.add_argument("--allow-eval-seed", action="store_true", help="판정 평가 전에도 평가 시드 41900~41999 를 쓴다 (기본은 막음)")
    args = ap.parse_args(argv)
    guard_eval_seed(args.seed, args.allow_eval_seed)
    cfg = EV._cfg(args.config)
    if args.bears:
        cfg = EV.override(cfg, {"bears": {"count": args.bears}})
    first = args.model or args.policy
    if first is None:
        raise SystemExit("--model 또는 --policy 를 준다")
    names = [first, args.compare]
    trs = [record(cfg, args.seed, args.steps, EV.make_policy(n)) for n in names]
    f = pick_frame(trs[0])
    fig, axs = plt.subplots(2, 2, figsize=(12, 13.4))
    p = trs[0]["params"]
    for j, (n, tr) in enumerate(zip(names, trs)):
        lab = EV.policy_label(n)
        draw(axs[0, j], tr, 0, len(tr["pos"]), f"{lab} — 전체 {len(tr['pos'])} 스텝, 잡힘 {tr['caught_n']}")
        draw(axs[1, j], tr, max(0, f - 20), min(len(tr["pos"]), f + 1), f"{lab} — 스텝 {f} (꼬리 20 스텝)", frame=f)
    hd = [Line2D([0], [0], color=c, lw=2, label=k) for k, c in (("먹기", ACT_COL["eat"]), ("뛰기", ACT_COL["run"]),
                                                               ("은신처로", ACT_COL["shelter"]), ("살피기", ACT_COL["watch"]))]
    hd += [Line2D([0], [0], color=KIND_COL[K_WOLF], lw=2, label="늑대"), Line2D([0], [0], color=KIND_COL[K_BEAST], lw=2, label="해 없는 짐승"),
           Line2D([0], [0], marker="x", color="k", lw=0, label="잡힌 자리")]
    if args.bears:
        hd.append(Line2D([0], [0], color=KIND_COL[K_BEAR], lw=2, label="곰"))
    fig.legend(handles=hd, loc="lower center", ncol=len(hd), fontsize=10)
    fig.suptitle(f"R8 세계 {args.seed}: 늑대 {p['wolves']}(잠행 {p['stalkers']}) · 짐승 {p['beasts']} · 늑대 속도 {p['wolf_speed_mult']:.2f} · "
                 f"먹이 재생 {p['food_regen_mult']:.2f}", fontsize=12)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97), h_pad=2.5)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    print(f"그림 {out} (장면 스텝 {f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
