"""R8 리플레이 영상 — 위에서 본 무대 애니메이션 mp4 (발표용, 설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R8_LEARN_DANGER_DESIGN.md 8-4).

`herbivore_rl/` 에서 (PYTHONUTF8=1):
    python results/v3/r8/r8_replay_video.py --model ckpt/r8/r8_p_s0.zip --seed 41900 \
        --out C:/kwon/univ/3-1/GameContentsCapstoneDesign/week9_assets/r8/replay_s0_41900.mp4

왼쪽 칸 = --model(R8 두뇌, 또는 --policy 기준 정책), 오른쪽 칸 = --compare(기본 always_eat '늘 먹기').
두 칸은 같은 설정·같은 시드로 R8World(cfg, [seed]) 를 따로 만들어 돈다 — `r8_replay.record` 를 그대로 쓴다. 세계의 난수 갈래(배치·동물 움직임·
다시 남)는 시드로만 정해져 시작 세계가 같고, 다른 것은 정책뿐이다(동물 난수는 정책과 무관하게 늘 같은 개수를 뽑는다).

그리기 규칙·색은 r8_replay.py 와 같다: 배경 = 시작 먹이 용량(초록), 어두운 원 = 은신처, 사슴 점·꼬리 색 = 그때 고른 행동(먹기 초록·뛰기 주황·
은신처로 파랑·살피기 회색), 늑대 빨강·해 없는 짐승 갈색(곰 검정), 잡힌 자리 × (영상 구간 안에서 잡힌 것은 끝까지 남는다). 꼬리 = 지난 20 스텝.
화면 글자는 위의 두 이름표와 아래 작은 범례뿐이다(--note 를 주면 오른쪽 아래 작은 회색 글 한 줄, --counter 면 칸마다 '잡힘 n').

시간: 1 프레임 = 1 스텝(--steps-per-frame), 1 스텝 = 2/15 초 → 30 fps 에서 실제의 4 배 빠르기. 기본 25 초 = 750 스텝 = 무대 100 초.

장면 고르기 규칙 (결과를 보기 전에 정한 규칙 — 좋아 보이는 장면을 손으로 고르지 않는다):
  1. 두 정책을 같은 시드로 --record 스텝(기본 3000 = 판정 평가 길이) 기록한다.
  2. 스텝마다 '늑대 10 단위(20 m) 안 사슴 수' 를 왼쪽(R8) 칸에서 센다 — r8_replay.pick_frame 과 같은 수(--pick both 면 두 칸 합).
  3. 영상 길이 L 스텝, 정점 f = 그 수가 가장 큰 스텝(같으면 이른 것). 단 f 는 [0.6 L, T − 0.4 L] 안에서만 찾는다.
  4. 영상 구간 = [f − 0.6 L, f + 0.4 L) — 정점 앞 60% 가 늑대가 사슴 무리에 다가오는 구간이 된다. 포스터 그림 = 정점 프레임.
  --start 로 구간 시작을 손으로 주면 이 규칙 밖이다(그때는 곁 파일 .json 의 rule 에 'manual' 로 남는다).

나오는 것: <out>.mp4 (H.264·yuv420p·faststart — 파워포인트 재생), 포스터 <out>.png, 곁 파일 <out>.json (시드·모델·구간·정점·칸마다 잡힘 수).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
for _p in (ROOT, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import eval_r8 as EV  # noqa: E402  ← env.torch_init 를 먼저 싣는다
import r8_replay as RP  # noqa: E402

import numpy as np  # noqa: E402

from env_v2.r8_world import K_BEAR, K_BEAST, K_WOLF  # noqa: E402

BG = "#F5F3EC"                                      # 7·8주차 덱 바탕색
INK = "#1B2A2F"
MUTED = "#5A6468"
NAMES = {"always_eat": "늘 먹기", "rule_blind": "손규칙 (이름표 없음)", "rule_oracle": "손규칙 (이름표 있음)", "rule_aim": "손규칙 (다가옴만)",
         "random": "무작위"}


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        p = shutil.which("ffmpeg")
        if p:
            return p
    raise SystemExit("ffmpeg 를 찾지 못했다 (imageio_ffmpeg 또는 PATH)")


def near_wolf_count(tr: dict, r: float = 10.0) -> np.ndarray:
    """스텝마다 늑대 r 단위 안 사슴 수 (r8_replay.pick_frame 과 같은 셈)."""
    P, Ap = tr["pos"], tr["apos"]
    wolves = np.nonzero(tr["present"] & (tr["kind"] == K_WOLF))[0]
    if not len(wolves):
        return np.zeros(len(P), dtype=np.int64)
    d = np.sqrt(((P[:, :, None, :] - Ap[:, None, wolves, :]) ** 2).sum(-1)).min(-1)     # (T, N)
    return (d < r).sum(1)


def pick_window(cnt: np.ndarray, L: int, lead: float = 0.6) -> tuple[int, int]:
    """(구간 시작, 정점). 규칙은 모듈 머리 주석 3·4."""
    T = len(cnt)
    a, b = int(round(lead * L)), T - (L - int(round(lead * L)))
    if b < a:                                       # 기록이 영상보다 짧다 — 처음부터
        return 0, int(np.argmax(cnt))
    f = a + int(np.argmax(cnt[a:b + 1]))
    return f - int(round(lead * L)), f


def label_of(name: str) -> str:
    return NAMES.get(name, Path(name).stem if name.endswith(".zip") else name)


def main(argv=None) -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D
    from matplotlib.patches import Circle

    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/v3_r8_pilot.yaml")
    ap.add_argument("--model", default=None, help="왼쪽 칸 모델 zip (herbivore_rl/ 기준 또는 절대 경로)")
    ap.add_argument("--policy", default=None, help="--model 대신 왼쪽 칸 기준 정책 (always_eat·rule_blind·rule_oracle·random)")
    ap.add_argument("--compare", default="always_eat", help="오른쪽 칸 정책 (기본 늘 먹기)")
    ap.add_argument("--seed", type=int, default=41900)
    ap.add_argument("--bears", type=int, default=0)
    ap.add_argument("--record", type=int, default=3000, help="장면을 고를 기록 길이 (스텝)")
    ap.add_argument("--seconds", type=float, default=25.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--steps-per-frame", type=int, default=1)
    ap.add_argument("--size", default="1920x1080", help="영상 크기 폭x높이 (예 1600x900)")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--pick", choices=("left", "both"), default="left", help="장면 고르기 셈: 왼쪽 칸만(기본, r8_replay 와 같음) 또는 두 칸 합")
    ap.add_argument("--start", type=int, default=None, help="구간 시작 스텝을 손으로 (규칙 밖 — 곁 파일에 남는다)")
    ap.add_argument("--tail", type=int, default=20, help="꼬리 길이 (스텝)")
    ap.add_argument("--left-label", default="R8 두뇌")
    ap.add_argument("--right-label", default=None, help="기본: 정책 이름 (always_eat → 늘 먹기)")
    ap.add_argument("--note", default=None, help="오른쪽 아래 작은 회색 글 (초안 표시 등)")
    ap.add_argument("--counter", action="store_true", help="칸마다 '잡힘 n' 을 작게 적는다")
    ap.add_argument("--out", required=True, help="mp4 경로 (포스터 .png·곁 파일 .json 이 같은 이름으로)")
    args = ap.parse_args(argv)

    t_start = time.time()
    W, H = (int(v) for v in args.size.lower().split("x"))
    if W % 2 or H % 2:
        raise SystemExit("영상 폭·높이는 짝수 (yuv420p)")
    cfg = EV._cfg(args.config)
    if args.bears:
        cfg = EV.override(cfg, {"bears": {"count": args.bears}})
    first = args.model or args.policy
    if first is None:
        raise SystemExit("--model 또는 --policy 를 준다")
    names = [first, args.compare]
    trs = [RP.record(cfg, args.seed, args.record, EV.make_policy(n)) for n in names]
    T = min(len(tr["pos"]) for tr in trs)
    spf = max(1, int(args.steps_per_frame))
    n_frames = int(round(args.seconds * args.fps))
    L = n_frames * spf
    cnt = near_wolf_count(trs[0])[:T]
    if args.pick == "both":
        cnt = cnt + near_wolf_count(trs[1])[:T]
    if args.start is not None:
        t0 = max(0, min(int(args.start), max(0, T - L)))
        peak = t0 + int(np.argmax(cnt[t0:t0 + L]))
        rule = "manual"
    else:
        t0, peak = pick_window(cnt, L)
        rule = f"peak_near_wolf10_{args.pick}_lead0.6"
    t1 = min(T, t0 + L)
    frames = list(range(t0, t1, spf))
    print(f"기록 {T} 스텝, 구간 [{t0}, {t1}) {len(frames)} 프레임, 정점 스텝 {peak} (늑대 10 단위 안 사슴 {int(cnt[peak])})", flush=True)

    # ---------------- 그림 틀 ----------------
    fig = plt.figure(figsize=(W / 100.0, H / 100.0), dpi=100, facecolor=BG)
    top_px, bot_px, gap_px = int(0.105 * H), int(0.085 * H), int(0.03 * W)
    side = min((W - 3 * gap_px) / 2.0, H - top_px - bot_px)
    k = side / 940.0                                         # 1080p 칸(≈940 px) 기준 크기 배수
    x_left = (W - 2 * side - gap_px) / 2.0
    y0 = bot_px + (H - top_px - bot_px - side) / 2.0
    S = trs[0]["size"]
    labels = [args.left_label, args.right_label or label_of(args.compare)]
    cat_idx = {"eat": 0, "run": 1, "shelter": 2, "watch": 3}
    cat_rgb = np.array([matplotlib.colors.to_rgba(RP.ACT_COL[c]) for c in ("eat", "run", "shelter", "watch")])
    panels = []
    for j, tr in enumerate(trs):
        ax = fig.add_axes(((x_left + j * (side + gap_px)) / W, y0 / H, side / W, side / H))
        ax.set_facecolor("white")
        ax.imshow(tr["food"], origin="lower", extent=(0, S, 0, S), cmap="Greens", vmin=0, vmax=1.0, alpha=0.55, zorder=0)
        for c in tr["cov_c"]:
            ax.add_patch(Circle(c, tr["cov_r"], color="#333333", alpha=0.35, lw=0, zorder=1))
        ax.set_xlim(0, S)
        ax.set_ylim(0, S)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color("#C4C2BC")
            sp.set_linewidth(1.2)
        lc = LineCollection([], linewidths=2.0 * k, alpha=0.9, zorder=3)
        ax.add_collection(lc)
        deer = ax.scatter([], [], s=70 * k * k, edgecolors="k", linewidths=0.6 * k, zorder=5, clip_on=False)   # 벽에 붙은 점도 다 보이게
        animals = []
        for a in np.nonzero(tr["present"])[0]:
            kd = int(tr["kind"][a])
            col = RP.KIND_COL[kd]
            ln, = ax.plot([], [], color=col, lw=2.6 * k, alpha=0.85, zorder=4, solid_capstyle="round")
            dot, = ax.plot([], [], "o", color=col, ms=(17 if kd == K_BEAR else 13) * k, mec="white", mew=1.4 * k, zorder=6, clip_on=False)
            animals.append((a, ln, dot))
        xs = ax.scatter([], [], marker="x", c="k", s=170 * k * k, linewidths=3.0 * k, zorder=7, clip_on=False)
        txt = None
        if args.counter:
            txt = ax.text(0.015, 0.985, "", transform=ax.transAxes, ha="left", va="top", fontsize=17 * k, color=INK,
                          bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.8), zorder=8)
        fig.text((x_left + j * (side + gap_px) + side / 2) / W, (y0 + side + 0.022 * H) / H, labels[j], ha="center", va="bottom",
                 fontsize=34 * k, fontweight="bold", color=INK)
        cats = np.vectorize(cat_idx.get)(RP.act_cat(tr["act"]))
        panels.append(dict(tr=tr, ax=ax, lc=lc, deer=deer, animals=animals, xs=xs, txt=txt, cats=cats,
                           catch=sorted(((int(t), p, kd) for (t, p, kd) in tr["catch"]), key=lambda c: c[0])))
    ms = 11 * k
    hd = [Line2D([0], [0], marker="o", lw=0, color=RP.KIND_COL[K_WOLF], mec="white", ms=ms * 1.15, label="늑대"),
          Line2D([0], [0], marker="o", lw=0, color=RP.KIND_COL[K_BEAST], mec="white", ms=ms * 1.15, label="해 없는 짐승")]
    if args.bears:
        hd.append(Line2D([0], [0], marker="o", lw=0, color=RP.KIND_COL[K_BEAR], ms=ms * 1.3, label="곰"))
    hd += [Line2D([0], [0], marker="o", lw=2.4 * k, color=RP.ACT_COL[c], mec="k", mew=0.5, ms=ms * 0.8, label=f"사슴 {t}")
           for c, t in (("eat", "먹기"), ("run", "뛰기"), ("shelter", "은신처로"), ("watch", "살피기"))]
    hd += [Line2D([0], [0], marker="x", lw=0, color="k", ms=ms, mew=2.6 * k, label="잡힌 자리"),
           Line2D([0], [0], marker="o", lw=0, color="#333333", alpha=0.35, ms=ms * 1.6, label="은신처")]
    fig.legend(handles=hd, loc="lower center", bbox_to_anchor=(0.5, 0.012), ncol=len(hd), fontsize=17 * k, frameon=False,
               handletextpad=0.35, columnspacing=1.5)
    if args.note:
        fig.text(0.995, 0.006, args.note, ha="right", va="bottom", fontsize=13 * k, color="#8A8F91")
    if fig.canvas.get_width_height() != (W, H):
        raise SystemExit(f"그림 크기 {fig.canvas.get_width_height()} ≠ {W}x{H}")

    def update(t: int) -> None:
        for pn in panels:
            tr, cats = pn["tr"], pn["cats"]
            P, D = tr["pos"], tr["dead"]
            segs, cols = [], []
            for u in range(max(1, t - args.tail + 1), t + 1):
                ok = ~D[u] & ~D[u - 1]
                ii = np.nonzero(ok)[0]
                if len(ii):
                    segs.extend(np.stack([P[u - 1, ii], P[u, ii]], 1))
                    cols.append(cat_rgb[cats[u, ii]])
            pn["lc"].set_segments(segs)
            if cols:
                pn["lc"].set_color(np.concatenate(cols, 0))
            live = ~D[t]
            pn["deer"].set_offsets(P[t, live])
            pn["deer"].set_facecolors(cat_rgb[cats[t, live]])
            lo = max(0, t - args.tail)
            for a, ln, dot in pn["animals"]:
                q = tr["apos"][lo:t + 1, a]
                ln.set_data(q[:, 0], q[:, 1])
                dot.set_data([q[-1, 0]], [q[-1, 1]])
            cp = [p for (tc, p, kd) in pn["catch"] if t0 <= tc <= t]
            pn["xs"].set_offsets(np.asarray(cp) if cp else np.zeros((0, 2)))
            if pn["txt"] is not None:
                pn["txt"].set_text(f"잡힘 {len(cp)}")

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    poster = out.with_suffix(".png")
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(args.fps), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf), "-pix_fmt", "yuv420p", "-profile:v", "high", "-threads", "2",
           "-movflags", "+faststart", "-an", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    poster_frame = min(frames, key=lambda t: abs(t - peak))
    try:
        for i, t in enumerate(frames):
            update(t)
            fig.canvas.draw()
            buf = fig.canvas.buffer_rgba()
            proc.stdin.write(bytes(buf))
            if t == poster_frame:
                from PIL import Image

                Image.fromarray(np.asarray(buf)[..., :3].copy()).save(poster)
            if (i + 1) % 150 == 0:
                print(f"  {i + 1}/{len(frames)} 프레임 ({time.time() - t_start:.0f}s)", flush=True)
    finally:
        proc.stdin.close()
        rc = proc.wait()
    plt.close(fig)
    if rc != 0:
        raise SystemExit(f"ffmpeg 실패 (코드 {rc})")
    caught = [sum(1 for (tc, _, _) in pn["catch"] if t0 <= tc < t1) for pn in panels]
    meta = dict(out=str(out), poster=str(poster), poster_step=int(poster_frame), config=args.config, seed=args.seed, left=first, right=args.compare,
                labels=labels, world=trs[0]["params"], record_steps=int(T), window=[int(t0), int(t1)], peak_step=int(peak),
                peak_near_wolf=int(cnt[peak]), rule=rule, fps=args.fps, steps_per_frame=spf, frames=len(frames), size=[W, H],
                caught_in_window={labels[0]: caught[0], labels[1]: caught[1]},
                caught_in_record={labels[0]: trs[0]["caught_n"], labels[1]: trs[1]["caught_n"]}, note=args.note,
                made=time.strftime("%Y-%m-%d %H:%M:%S"), seconds_taken=round(time.time() - t_start, 1))
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"영상 {out} ({out.stat().st_size / 1e6:.1f} MB), 포스터 {poster}, 구간 잡힘 {labels[0]} {caught[0]} / {labels[1]} {caught[1]}, "
          f"{time.time() - t_start:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
