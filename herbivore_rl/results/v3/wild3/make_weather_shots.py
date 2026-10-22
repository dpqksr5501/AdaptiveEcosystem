"""우리 시험 레벨(통합 v3) 비·눈 연출 사진과 연출 시간표 그림 (10-18, README.md 5절). herbivore_rl/ 에서

    python results/v3/wild3/make_weather_shots.py --frames <촬영 출력 폴더>      # 판 폴더 wxA·wxB·wxC 가 든 폴더 (-EcoV3FilmOut)

판 (명령은 README.md 5절):
  wxA  통합 촬영(-EcoV3FilmShots=지역,방식,…): 숲·고지·메마른 땅 무대를 비스듬히 위에서(wide)·사슴을 따라(deer), 빗줄기 배수 1 (팀 화면과 같다)
  wxB  단독 촬영(-EcoV3FilmStandalone, 통합 v3 모드도 켬): 땅 높이 1.8 m 정지 카메라(숲·고지·메마른 땅), 경계 넘기(메마른 땅 → 숲 → 메마른 땅, 고지 → 메마른 땅, 10 m/s)
  wxC  wxB 의 숲 두 장면을 빗줄기 배수 4 로 (eco.IntegratedV3.WeatherRainDensity 4 — 발표용)
출력 shots/: 사진 1280×720 (forest_rain_*·highland_snow_*·barren_clear_*), 이웃 프레임 차이(forest_rain_motion.png — 낮에 옅은 빗줄기를 보이게),
  경계 넘기 띠(crossing_rain.png·crossing_snow.png), 연출 시간표(weather_fx_timeline.png — 촬영 감독 watch.txt 의 RainAlpha·SnowAlpha·켜짐),
  film_runs/<판>/shots.json·watch.txt (촬영 감독 기록 — 읽기만 한 연출 액터 상태), summary.json (장면마다 프레임·연출 상태).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
OUT = HERE / "shots"
SIZE = (1280, 720)
# (출력 이름, 판, 장면 이름, 장면 안 몇째 캡처) — 장면 이름은 shots.json 의 tag(단독) 또는 '지역/방식'(통합)
PICKS = (
    ("forest_rain_wide.png", "wxA", "Forest/wide", 4),
    ("forest_rain_ground.png", "wxB", "forest_ground", 6),
    ("forest_rain_ground_density4.png", "wxC", "forest_ground", 4),
    ("highland_snow_wide.png", "wxA", "Highland/wide", 4),
    ("highland_snow_deer.png", "wxA", "Highland/deer", 3),
    ("highland_snow_ground.png", "wxB", "highland_ground", 6),
    ("barren_clear_wide.png", "wxA", "Barren/wide", 3),
)
STATE = re.compile(r"t=([\d.]+) frame=(\d+) cam=\(([-\d]+),([-\d]+),([-\d]+)\).*?Rain=NiagaraComponent\[active=(\d)(?: spawn_rate=([\d.]+))?.*?"
                   r"Snow=NiagaraComponent\[active=(\d).*?RainAlpha=([\d.]+) SnowAlpha=([\d.]+) RainSpawnRate=([-\d.]+) bRainOn=(\d) bSnowOn=(\d) "
                   r"bRainSoundOn=(\d) CameraWeather=(\d) CameraIntensity=([\d.]+)")


def shots_of(run_dir: Path) -> dict:
    d = json.loads((run_dir / "shots.json").read_text(encoding="utf-8"))
    return {(s.get("tag") or f"{s['region']}/{s['mode']}"): s for s in d["shots"]}


def states_of(run_dir: Path) -> dict:
    out = {}
    for line in (run_dir / "watch.txt").read_text(encoding="utf-8").splitlines():
        m = STATE.search(line)
        if m:
            g = m.groups()
            out[int(g[1])] = dict(t=float(g[0]), cam=[int(g[2]) / 100.0, int(g[3]) / 100.0, int(g[4]) / 100.0], rain_active=int(g[5]),
                                  spawn_rate=float(g[6]) if g[6] else None, snow_active=int(g[7]), rain_alpha=float(g[8]), snow_alpha=float(g[9]),
                                  rain_on=int(g[11]), snow_on=int(g[12]), sound_on=int(g[13]), weather=int(g[14]), intensity=float(g[15]))
    return out


def frame(run_dir: Path, i: int) -> Image.Image:
    return Image.open(run_dir / f"f_{i:05d}.png").convert("RGB")


def label(im: Image.Image, text: str) -> Image.Image:
    im = im.copy()
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("malgun.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    d.rectangle((0, 0, im.width, 34), fill=(0, 0, 0))
    d.text((8, 5), text, fill=(255, 255, 255), font=font)
    return im


def strip(run_dir: Path, frames: list[int], states: dict, out: Path, title: str) -> list[dict]:
    tiles, rows = [], []
    for i in frames:
        st = states.get(i, {})
        wx = {0: "맑음", 1: "비", 2: "눈"}.get(st.get("weather"), "?")
        text = f"{title} t={st.get('t', 0):.2f}s y={st.get('cam', [0, 0])[1]:.0f}m 지역 {wx} · 비 {st.get('rain_alpha', 0):.2f} · 눈 {'켬' if st.get('snow_on') else '끔'}"
        tiles.append(label(frame(run_dir, i).resize((640, 360)), text))
        rows.append(dict(frame=i, **st))
    W = Image.new("RGB", (640 * 2, 360 * ((len(tiles) + 1) // 2)))
    for k, t in enumerate(tiles):
        W.paste(t, ((k % 2) * 640, (k // 2) * 360))
    W.save(out)
    return rows


def timeline(states: dict, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = "Malgun Gothic"
    ks = sorted(states)
    t = [states[k]["t"] for k in ks]
    fig, ax = plt.subplots(2, 1, figsize=(10, 5), sharex=True, gridspec_kw=dict(height_ratios=[2, 1]))
    ax[0].step(t, [states[k]["rain_alpha"] for k in ks], where="post", label="비 세기 × 페이드 (RainAlpha)", color="#3b6fb6")
    ax[0].step(t, [states[k]["snow_on"] for k in ks], where="post", label="눈 켬 (bSnowOn)", color="#888888", linestyle="--")
    ax[0].set_ylabel("연출")
    ax[0].set_ylim(-0.05, 1.1)
    ax[0].legend(loc="upper right", fontsize=8)
    ax[1].step(t, [states[k]["weather"] for k in ks], where="post", color="#444444")
    ax[1].set_yticks([0, 1, 2], ["맑음", "비", "눈"])
    ax[1].set_ylabel("카메라 지역")
    ax[1].set_xlabel("월드 초 (단독 촬영 wxB — 경계 넘기 10 m/s)")
    fig.suptitle("우리 시험 레벨 비·눈 연출: 카메라 지역 날씨 → 연출 (촬영 감독 watch.txt, 캡처마다)")
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--frames", type=Path, required=True, help="촬영 출력 폴더 (판 폴더 wxA·wxB·wxC 가 든 폴더)")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict = {"picks": [], "crossings": {}}
    runs = {r: a.frames / r for r in ("wxA", "wxB", "wxC")}
    shots = {r: shots_of(p) for r, p in runs.items()}
    states = {r: states_of(p) for r, p in runs.items()}
    for name, run, shot, k in PICKS:
        s = shots[run][shot]
        i = s["first_frame"] + k
        frame(runs[run], i).resize(SIZE, Image.LANCZOS).save(OUT / name)
        summary["picks"].append(dict(file=name, run=run, shot=shot, frame=i, **states[run].get(i, {})))
    # 이웃 프레임 차이 (정지 카메라 숲 땅 높이 — 바뀐 것은 빗줄기·사슴뿐)
    s = shots["wxB"]["forest_ground"]
    i = s["first_frame"] + 6
    d = ImageOps.autocontrast(ImageChops.difference(frame(runs["wxB"], i), frame(runs["wxB"], i + 1)).convert("L"))
    d.resize(SIZE, Image.LANCZOS).save(OUT / "forest_rain_motion.png")
    # 경계 넘기
    b = runs["wxB"]
    ci, co, so = shots["wxB"]["cross_in"]["first_frame"], shots["wxB"]["cross_out"]["first_frame"], shots["wxB"]["snow_out"]["first_frame"]
    summary["crossings"]["rain"] = strip(b, [ci + 14, ci + 16, ci + 18, ci + 22, co + 15, co + 16, co + 17, co + 19], states["wxB"], OUT / "crossing_rain.png",
                                         "메마른 땅↔숲")
    summary["crossings"]["snow"] = strip(b, [so + 14, so + 15, so + 16, so + 17, so + 18, so + 22], states["wxB"], OUT / "crossing_snow.png", "고지→메마른 땅")
    timeline(states["wxB"], OUT / "weather_fx_timeline.png")
    for r, p in runs.items():
        dst = OUT / "film_runs" / r
        dst.mkdir(parents=True, exist_ok=True)
        for f in ("shots.json", "watch.txt"):
            shutil.copyfile(p / f, dst / f)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"썼다: {OUT} (사진 {len(PICKS)} + 차이 1 + 띠 2 + 시간표 1)")


if __name__ == "__main__":
    main()
