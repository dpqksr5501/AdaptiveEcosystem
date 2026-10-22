"""독립 확인(10-18) 비·눈 연출 사진 한 장씩 + 경계 나가기 시간표 (verify/README.md). herbivore_rl/ 에서

    python results/v3/wild3/verify/make_verify_stills.py --run <촬영 출력 폴더>/wxV

촬영 판 wxV(명령은 README.md): 통합 v3 세션 20004 + 단독 카메라, 소리 장치 켬(-UseFixedTimeStep, au.MuteAudio=1 — 스피커는 조용).
출력(이 폴더): stills.jpg(숲 비·숲 곁 메마른 땅·고지 눈·메마른 땅 맑음 넷을 2×2로, 칸마다 800×450), exits.json(나가기 두 번의 캡처마다 카메라 y·연출 상태·재생 중 소리),
  exits.md(같은 내용 표).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SIZE = (800, 450)
# (제목, 장면 tag, 장면 안 몇째 캡처)
PICKS = (
    ("숲 (비) 땅 높이", "forest_ground", 6),
    ("메마른 땅, 숲 경계 10 m 앞에서 숲 쪽을 봄 (비 없어야)", "barren_border", 6),
    ("고지 (눈) 땅 높이", "highland_ground", 6),
    ("메마른 땅 가운데 (맑음)", "barren_ground", 6),
)
LINE = re.compile(r"^t=([\d.]+) frame=(\d+) cam=\(([-\d]+),([-\d]+),([-\d]+)\)")
FIELD = {k: re.compile(p) for k, p in dict(
    rain_active=r"Rain=NiagaraComponent\[active=(\d)", spawn=r"Rain=NiagaraComponent\[active=\d spawn_rate=([\d.]+)",
    snow_active=r"Snow=NiagaraComponent\[active=(\d)", sound=r"RainSound=AudioComponent\[active=(\d) playing=(\d) vol=([\d.]+)",
    alpha=r"RainAlpha=([\d.]+) SnowAlpha=([\d.]+)", flags=r"bRainOn=(\d) bSnowOn=(\d) bRainSoundOn=(\d) CameraWeather=(\d)",
    audio=r"audio_device=(\d)").items()}
PLAYING = re.compile(r"playing_sound=(\S+?)@(\S+?)\(")


def font(size):
    for f in ("malgun.ttf", "C:/Windows/Fonts/malgun.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def parse_watch(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = LINE.match(line)
        if not m:
            continue
        r = dict(t=float(m.group(1)), frame=int(m.group(2)), cam_y_m=int(m.group(4)) / 100.0)
        for k, rx in FIELD.items():
            g = rx.search(line)
            r[k] = [float(x) for x in g.groups()] if g else None
        r["playing"] = [f"{a}@{b}" for a, b in PLAYING.findall(line)]
        rows.append(r)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", type=Path, required=True)
    a = ap.parse_args(argv)
    shots = {s["tag"]: s for s in json.loads((a.run / "shots.json").read_text(encoding="utf-8"))["shots"]}
    watch = {r["frame"]: r for r in parse_watch(a.run / "watch.txt")}
    sheet = Image.new("RGB", (SIZE[0] * 2, SIZE[1] * 2), "black")
    f = font(26)
    picks = []
    for i, (title, tag, k) in enumerate(PICKS):
        s = shots[tag]
        fr = s["first_frame"] + min(k, s["frames"] - 1)
        im = Image.open(a.run / f"f_{fr:05d}.png").convert("RGB").resize(SIZE, Image.LANCZOS)
        w = watch.get(fr, {})
        sub = (f"t={w.get('t', 0):.2f}s 비 {w.get('alpha', [0, 0])[0]:.2f} 눈켬 {int(w.get('flags', [0, 0, 0, 0])[1])} "
               f"빗소리 {int(w.get('flags', [0, 0, 0, 0])[2])}") if w else ""
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, SIZE[0], 70), fill=(0, 0, 0))
        d.text((12, 4), title, fill="white", font=f)
        d.text((12, 36), sub, fill=(200, 200, 200), font=font(22))
        sheet.paste(im, ((i % 2) * SIZE[0], (i // 2) * SIZE[1]))
        picks.append(dict(title=title, tag=tag, frame=fr, state=w))
    sheet.save(HERE / "stills.jpg", quality=88)
    exits = {}
    lines = ["# 나가기 두 번 — 캡처마다 연출 상태 (make_verify_stills.py 가 만듦)", ""]
    for tag, edge in (("cross_out", 250.0), ("snow_out", -250.0)):
        s = shots[tag]
        rows = [watch[fr] for fr in range(s["first_frame"], s["first_frame"] + s["frames"]) if fr in watch]
        exits[tag] = rows
        lines += [f"## {tag} (경계 y = {edge:.0f} m)", "", "| t 초 | 카메라 y m | 비 세기×페이드 | 비 켬 | 눈 켬 | 빗소리 켬·재생 | 재생 중 소리 |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            al, fl, so = r["alpha"] or [0, 0], r["flags"] or [0, 0, 0, 0], r["sound"] or [0, 0, 0]
            lines.append(f"| {r['t']:.2f} | {r['cam_y_m']:.1f} | {al[0]:.2f} | {int(fl[0])} | {int(fl[1])} | {int(fl[2])}·{int(so[1])} | {', '.join(r['playing']) or '없음'} |")
        lines.append("")
    (HERE / "exits.json").write_text(json.dumps(dict(picks=picks, exits=exits), ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (HERE / "exits.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
