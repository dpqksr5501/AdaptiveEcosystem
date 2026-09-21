"""리플레이 영상 생성 (§4.6).

    python replay.py --policy random

개체 색 = cohesion, 포식자 = 빨간 X, 은신처 = 어두운 영역.
mp4를 먼저 시도하고 ffmpeg이 없으면 gif로 떨어진다 (§2는 mp4/gif 둘 다 허용).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.animation as animation  # noqa: E402
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402


def _use_korean_font() -> None:
    """라벨에 한글이 있다. 없으면 두부가 찍히므로 있는 폰트를 찾아 쓴다."""
    have = {f.name for f in fm.fontManager.ttflist}
    for name in ("Malgun Gothic", "NanumGothic", "Gulim", "Batang", "MS Gothic"):
        if name in have:
            matplotlib.rcParams["font.family"] = name
            matplotlib.rcParams["axes.unicode_minus"] = False
            return


_use_korean_font()

from env.config import load_config  # noqa: E402
from env.world import World  # noqa: E402
from policies.registry import make_policy  # noqa: E402

ROOT = Path(__file__).resolve().parent

# 먹이: 맨땅(갈색) → 무성함(초록)
FOOD_CMAP = LinearSegmentedColormap.from_list(
    "food", ["#2a2118", "#4a3b23", "#5d7a35", "#8fc44a"]
)


def spec_for(args) -> dict:
    """CLI 인자 → `policies.registry` 스펙."""
    if args.policy == "random":
        return {"kind": "random", "seed": args.seed}
    if args.policy == "utility":
        return {"kind": "utility", "params": "default" if args.default_params else None}
    return {"kind": "learned", "model": args.model}


# --------------------------------------------------------------------- #
# 수집
# --------------------------------------------------------------------- #


def collect(world: World, policy, steps: int, stride: int):
    """프레임마다 그릴 것만 복사해 둔다."""
    frames = []
    for t in range(steps):
        obs = world.observe()
        a = policy(obs)
        if t % stride == 0:
            frames.append(
                dict(
                    t=t,
                    pos=world.pos.copy(),
                    cohesion=a[:, 1].copy(),
                    pred=world.pred_pos.copy(),
                    ranged=world.pred_ranged.copy(),
                    food=world.food.copy(),
                    energy=float(world.energy.mean()),
                    ema=float(world.pred_ema),
                    deaths=world._pred_deaths + world._starve_deaths,
                )
            )
        world.step(a)
    return frames


# --------------------------------------------------------------------- #
# 렌더
# --------------------------------------------------------------------- #


def render(world: World, frames, out: Path, fps: int, label: str):
    size = world.size
    fig, ax = plt.subplots(figsize=(7.6, 7.6), dpi=110)
    fig.patch.set_facecolor("#111111")
    ax.set_facecolor("#111111")
    ax.set_xlim(0, size)
    ax.set_ylim(0, size)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])

    extent = (0, world.gw * world.cfg.food_cell) * 2   # (x0,x1,y0,y1)
    food_im = ax.imshow(
        frames[0]["food"], origin="lower", extent=extent, cmap=FOOD_CMAP,
        vmin=0.0, vmax=1.0, interpolation="bilinear", zorder=0,
    )
    # 은신처 = 어두운 영역 (§4.6). 재생 감속은 셀 단위지만 은신 판정(_in_cover)은
    # 정확한 원이므로, 보이는 것과 판정이 어긋나지 않도록 원을 그린다.
    for (cx, cy), cr in zip(world.cov_c, world.cov_r):
        ax.add_patch(
            plt.Circle((cx, cy), cr, facecolor="black", alpha=0.55,
                       edgecolor="#5566aa", linewidth=0.8, zorder=1)
        )

    herb = ax.scatter(
        frames[0]["pos"][:, 0], frames[0]["pos"][:, 1], c=frames[0]["cohesion"],
        cmap="coolwarm", vmin=0.0, vmax=1.0, s=26, edgecolors="black",
        linewidths=0.35, zorder=3,
    )
    melee = ax.scatter([], [], marker="X", c="#ff2d2d", s=170,
                       edgecolors="white", linewidths=0.8, zorder=4)
    ranged = ax.scatter([], [], marker="x", c="#ff7a7a", s=110, linewidths=2.2, zorder=4)

    cb = fig.colorbar(herb, ax=ax, fraction=0.043, pad=0.02)
    cb.set_label("cohesion (행동 idx1)", color="white")
    cb.ax.yaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cb.ax.axes, "yticklabels"), color="white")

    title = ax.set_title("", color="white", fontsize=10, family="monospace")
    sub = (
        f"{label} | seed={world.seed} | world={size:.0f} | "
        f"M={world.M} (원거리 {int(world.pred_ranged.sum())}) | "
        f"은신처 {world.cover_frac_actual*100:.0f}%"
    )
    fig.text(0.5, 0.025, sub, ha="center", color="#aaaaaa", fontsize=9)

    def update(i):
        f = frames[i]
        food_im.set_data(f["food"])
        herb.set_offsets(f["pos"])
        herb.set_array(f["cohesion"])
        m = ~f["ranged"]
        melee.set_offsets(f["pred"][m] if m.any() else np.empty((0, 2)))
        ranged.set_offsets(f["pred"][~m] if (~m).any() else np.empty((0, 2)))
        # 이 줄만 monospace라 숫자 자리가 안 흔들린다. 한글은 아래 sub 로 뺐다.
        title.set_text(
            f"step {f['t']:5d}   energy {f['energy']:.2f}   "
            f"predation_ema {f['ema']:.3f}   deaths {f['deaths']:4d}"
        )
        return food_im, herb, melee, ranged, title

    anim = animation.FuncAnimation(fig, update, frames=len(frames), interval=1000 // fps)
    writer, out = pick_writer(out, fps)
    anim.save(str(out), writer=writer)
    plt.close(fig)
    return out


def pick_writer(out: Path, fps: int):
    """mp4를 우선하고, ffmpeg이 없으면 gif로 떨어진다."""
    exe = shutil.which("ffmpeg")
    if exe is None:
        try:
            import imageio_ffmpeg

            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            exe = None
    if exe and out.suffix == ".mp4":
        matplotlib.rcParams["animation.ffmpeg_path"] = exe
        return animation.FFMpegWriter(fps=fps, bitrate=2600), out
    if out.suffix == ".mp4":
        print("ffmpeg을 찾지 못했다. gif로 저장한다. (pip install imageio-ffmpeg)", file=sys.stderr)
        out = out.with_suffix(".gif")
    return animation.PillowWriter(fps=fps), out


# --------------------------------------------------------------------- #


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="리플레이 영상 생성")
    p.add_argument("--policy", default="random", choices=["random", "utility", "learned"])
    p.add_argument("--seed", type=int, default=10000, help="§3.5 평가 시드 기본값")
    p.add_argument("--steps", type=int, default=1800)
    p.add_argument("--stride", type=int, default=2, help="몇 스텝마다 한 프레임")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--out", default=None)
    p.add_argument("--config", default=None)
    p.add_argument("--model", default="ckpt/final.zip", help="--policy learned 용")
    p.add_argument("--default-params", action="store_true",
                   help="utility를 §5.1 기본값으로. 기본은 configs/utility_best.yaml")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    world = World(cfg, seeds=[args.seed])
    policy = make_policy(spec_for(args))

    print(f"수집 중: {args.steps} 스텝 (매 {args.stride}스텝 1프레임)")
    frames = collect(world, policy, args.steps, args.stride)

    out = Path(args.out) if args.out else ROOT / "results" / f"replay_{args.policy}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"렌더 중: {len(frames)} 프레임 -> {out}")
    out = render(world, frames, out, args.fps, args.policy)

    s = world.stats()
    print(f"완료: {out}  ({out.stat().st_size/1e6:.1f} MB)")
    print(
        "  mean_return={mean_return:.2f}  survival={survival:.0f}  repro={repro:.2f}  "
        "predation_rate={predation_rate:.4f}  cover_frac={cover_frac:.3f}".format(**s)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
