"""1-6 영상 보조 — 장면 정지 화면과 1배속 클립 (결과 뒤 추가, 그림용, 판정 아님).

PREREG 8절의 본 영상(`results/v2/replay_v2_2_compare.mp4`·`.png`)은 `replay_v2.py` 명령 그대로다(그 파일 머리 주석).
이 파일은 그 명령과 같은 수집(`replay_v2.run_policy`: 같은 설정·시드 10000·정책 스펙·라벨·자막)으로 장면 정지 화면
여러 장과 1배속 짧은 클립을 만든다. `replay_v2.py` 는 바꾸지 않고 그 함수만 쓴다. 작업 디렉터리 herbivore_rl/:

    python results/v2/s1_6/video_extra.py stills --train-seed 0 --png-steps 902:s1 918:s2 1070:s3
        → results/v2/s1_6/replay_v2_2_<태그>.png  (1800스텝·stride 2 수집 = 본 영상과 같은 프레임)
    python results/v2/s1_6/video_extra.py realtime --train-seed 0 --start 850 --end 1000
        → results/v2/replay_v2_2_realtime.mp4  (stride 1, 7.5fps. 1스텝 = 8/60초라 1배속. 스텝 850~999, 20초)

장면 스텝은 결과를 본 뒤 C0 칸에서 골랐다(`results/v2/stage1_v2_2.md` 영상 절): S1 = 포식자가 0.5·see_r 안에 보이는
개체 가운데 뛰는 개체가 가장 많은 스텝, S2 = 최근 위협·안 보임 개체가 많은 스텝(경계 0 — 실패 장면 기록), S3 = 반경
안 포식자 근처 개체가 많고 동족 중심 거리 차가 큰 스텝. 출력 파일이 이미 있으면 덮지 않는다.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # herbivore_rl/
sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저

import argparse  # noqa: E402

import replay_v2 as R  # noqa: E402
from env_v2.config import load_v2_config  # noqa: E402

SEED = 10000
CAPTION = "1-6 v2.2 · 평가 시드 10000 · 같은 세계·카메라. 점 색: 정지 회색, 걷기 초록, 뛰기 주황 · 흰 테두리 = 경계"


def runs_for(v: int, steps: int, stride: int) -> list:
    """PREREG 8절 영상 명령과 같은 두 칸(C0, C1′)."""
    cfg = load_v2_config(ROOT / "configs" / "v2_2.yaml")
    z = f"ckpt/v2/v2_2_s{v}.zip"
    specs = [R.parse_spec(f"learned:{z}"), R.parse_spec(f"perm:learned:{z}")]
    labels = [f"C0 학습 정책 (v2_2_s{v})", "C1′ 행동 순열 (보행·경계 빈도 같음, 상태와의 짝만 끊김)"]
    probe = R.World(cfg, seeds=[SEED])
    specs = [R.fit_spec(sp, probe.act_dim, probe.act_names) for sp in specs]
    return [R.run_policy(cfg, sp, SEED, steps, stride, lab) for sp, lab in zip(specs, labels)]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="1-6 영상 보조 (정지 화면·1배속 클립)")
    p.add_argument("cmd", choices=["stills", "realtime"])
    p.add_argument("--train-seed", type=int, required=True)
    p.add_argument("--steps", type=int, default=1800, help="stills 수집 스텝 (본 영상과 같게 1800)")
    p.add_argument("--stride", type=int, default=2, help="stills 수집 stride (본 영상과 같게 2)")
    p.add_argument("--png-steps", nargs="+", default=[], help="스텝:태그 ...")
    p.add_argument("--start", type=int, default=0, help="realtime 구간 첫 스텝")
    p.add_argument("--end", type=int, default=150, help="realtime 구간 끝 스텝(포함 안 함)")
    p.add_argument("--out-dir", default=None, help="출력 디렉터리 (기본: stills 는 이 파일 폴더, realtime 은 results/v2)")
    a = p.parse_args(argv)
    if a.cmd == "stills":
        out_dir = Path(a.out_dir) if a.out_dir else Path(__file__).resolve().parent
        runs = runs_for(a.train_seed, a.steps, a.stride)
        for tok in a.png_steps:
            step, _, tag = tok.partition(":")
            out = out_dir / f"replay_v2_2_{tag}.png"
            if out.exists():
                raise SystemExit(f"{out} 가 이미 있다 — 덮지 않는다")
            png, t = R.render_png(runs, out, int(step), 30, 150, 2, 120, 2, CAPTION)
            print(f"PNG {png} (step {t})")
    else:
        out_dir = Path(a.out_dir) if a.out_dir else ROOT / "results" / "v2"
        out = out_dir / "replay_v2_2_realtime.mp4"
        if out.exists():
            raise SystemExit(f"{out} 가 이미 있다 — 덮지 않는다")
        runs = runs_for(a.train_seed, a.end, 1)
        for r in runs:
            r.frames = r.frames[a.start:a.end]
        out = R.render(runs, out, 7.5, 100, None, 2, 120, 2, CAPTION + f" · 1배속(스텝 {a.start}~{a.end - 1})")
        print(f"완료 {out} {R.video_info(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
