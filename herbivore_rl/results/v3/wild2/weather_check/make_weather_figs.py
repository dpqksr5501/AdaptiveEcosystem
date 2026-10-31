"""팀 지역 날씨(비·눈) 확인 그림·요약 (10-18, README.md).

film_runs/<판>/watch.txt 는 촬영 감독 -EcoV3FilmWatch 가 캡처마다 남긴 팀 날씨 블루프린트 상태다(읽기만 한 값).
이 스크립트는
  1) summary.json — 지역에 들어간 때·비/눈 세기(타임라인 Alpha)가 오르기 시작한 때·다 오른 때·나간 뒤 꺼진 때,
     비·눈 이펙트 자리와 카메라·폰 거리, 소리, 프레임 시간
  2) weather_timeline.png — shc_pawn 판의 비·눈 세기와 카메라가 있던 지역
을 만든다. --frames <폴더> 를 주면 그 폴더(촬영 출력 shc_pawn/·shc_sound/·shc_sunspeed/·integration_v3/ 를 담은 곳)에서
README 의 사진(1280×720)도 다시 만든다.

    python results/v3/wild2/weather_check/make_weather_figs.py [--frames <촬영 출력 폴더>]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "film_runs"

# 지역 경계 (월드 cm, 두 맵 같은 트리거 상자 TV_Region_*: 가운데 y 0·±50000, 반폭 x 75000·y 25000·z 15000)
Y_FOREST = 25000.0
Y_HIGHLAND = -25000.0
Z_TOP = 15000.0


def region_of(x: float, y: float, z: float) -> str:
    if abs(x) > 75000 or abs(z) > Z_TOP:
        return "상자 밖"
    if y > Y_FOREST:
        return "숲"
    if y < Y_HIGHLAND:
        return "고지"
    return "메마른 땅"


def parse_watch(path: Path) -> tuple[list[dict], list[dict]]:
    rows, perf = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("perf"):
            m = re.search(r"t=(\S+) frames=(\d+) wall_ms_per_frame=(\S+) .* captures=(\d+)", line)
            perf.append({"t": float(m[1]), "ms": float(m[3]), "captures": int(m[4])})
            continue
        head, *parts = line.split(" | ")
        cam = tuple(float(v) for v in re.search(r"cam=\(([^)]*)\)", head)[1].split(","))
        pm = re.search(r"pawn=\(([^)]*)\)", head)
        row = {
            "t": float(re.search(r"t=(\S+)", head)[1]),
            "frame": int(re.search(r"frame=(\d+)", head)[1]),
            "cam": cam,
            "pawn": tuple(float(v) for v in pm[1].split(",")) if pm else None,
            "audio_device": (re.search(r"audio_device=(\d)", head) or [None, None])[1],
            "sounds": re.findall(r"playing_sound=(\S+?)@", head),
        }
        for p in parts:
            name = p.split(" ")[0]
            if "RegionalWeather" not in name:
                continue
            kind = "rain" if "Rain" in name else "snow"
            sysm = re.search(r"RainSystem=NiagaraComponent\[active=(\d) visible=\d at=\(([^)]*)\) cam_d=(\S+)m", p)
            sndm = re.search(r"RainSound=AudioComponent\[active=(\d) playing=(\d) vol=(\S+)", p)
            row[kind] = {
                "inside": int(re.search(r"CameraInsideRegion=(\d)", p)[1]),
                "alpha": float(re.search(r"RainTimeline_Alpha_\w+=(\S+)", p)[1]),
                "sys_active": int(sysm[1]) if sysm else None,
                "sys_at": tuple(float(v) for v in sysm[2].split(",")) if sysm else None,
                "sys_cam_d": float(sysm[3]) if sysm else None,
                "sound_playing": int(sndm[2]) if sndm else None,
                "sound_vol": float(sndm[3]) if sndm else None,
            }
        rows.append(row)
    return rows, perf


def transitions(rows: list[dict], kind: str) -> list[dict]:
    """지역 들어감·나감마다: 그때, 세기가 오르기 시작한 때, 다 오른 때 / 내려가기 시작한 때, 이펙트가 꺼진 때 (캡처 간격 안 어림)."""
    out = []
    prev = None
    prev_t = None
    for i, r in enumerate(rows):
        w = r.get(kind)
        if w is None:
            continue
        if prev is not None and w["inside"] != prev["inside"]:
            # continuous = 바로 앞 캡처가 0.25 초 안 (경계를 걸어서 넘은 장면). 아니면 장면 사이에 카메라가 뛰어서 넘은 때라 지연을 못 잰다
            ev = {"kind": "enter" if w["inside"] else "leave", "t": r["t"], "cam": r["cam"],
                  "continuous": r["t"] - prev_t <= 0.25}
            later = [x for x in rows[i:] if x.get(kind) and x[kind]["inside"] == w["inside"]]
            if w["inside"]:
                # 첫 0 보다 큰 세기와 그 기울기(초당 0.2)로 시작 때를 되짚는다
                up = next((x for x in later if x[kind]["alpha"] > 0.0), None)
                if up:
                    ev["fade_in_start"] = round(up["t"] - up[kind]["alpha"] / 0.2, 2)
                    ev["delay_s"] = round(ev["fade_in_start"] - r["t"], 2)
                full = next((x for x in later if x[kind]["alpha"] >= 0.999), None)
                ev["full_t"] = full["t"] if full else None
                ev["sys_active_at_enter"] = w["sys_active"]
            else:
                off = next((x for x in later if x[kind]["sys_active"] == 0), None)
                ev["alpha_at_leave"] = w["alpha"]
                ev["sys_off_t"] = off["t"] if off else None
            out.append(ev)
        prev = w
        prev_t = r["t"]
    return out


def summarize() -> dict:
    out: dict = {}
    for run in sorted(p.name for p in RUNS.iterdir() if (p / "watch.txt").exists()):
        rows, perf = parse_watch(RUNS / run / "watch.txt")
        s: dict = {"captures": len(rows)}
        for kind in ("rain", "snow"):
            ks = [r[kind] for r in rows if kind in r]
            if not ks:
                s[kind] = "블루프린트 없음"
                continue
            act = [k for k in ks if k["sys_active"] == 1]
            d = sorted(k["sys_cam_d"] for k in act if k["sys_cam_d"] is not None)
            pawn_d = []
            for r in rows:
                k = r.get(kind)
                if k and k["sys_active"] == 1 and r["pawn"] and k["sys_at"]:
                    pawn_d.append(sum((a - b) ** 2 for a, b in zip(k["sys_at"], r["pawn"])) ** 0.5 / 100.0)
            s[kind] = {
                "transitions": transitions(rows, kind),
                "fx_to_camera_m_median": d[len(d) // 2] if d else None,
                "fx_to_camera_m_max": d[-1] if d else None,
                "fx_to_pawn_m_max": round(max(pawn_d), 2) if pawn_d else None,
                "sound_component_seen": any(k["sound_playing"] is not None for k in ks),
            }
        s["audio_device"] = sorted({r["audio_device"] for r in rows if r["audio_device"] is not None})
        s["sounds_heard"] = sorted({n for r in rows for n in r["sounds"]})
        free = sorted(p["ms"] for p in perf if p["captures"] == 0 and p["t"] > 2.5)
        if free:
            s["frame_ms_no_capture_median"] = free[len(free) // 2]
            s["frame_ms_no_capture_max"] = free[-1]
        out[run] = s
    (HERE / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def plot_timeline() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    rows, _ = parse_watch(RUNS / "shc_pawn" / "watch.txt")
    ink, muted, grid, surface = "#1f1f1e", "#6b6a63", "#e4e3dc", "#fcfcfb"
    colors = {"rain": "#2a78d6", "snow": "#eb6834"}
    bands = {"숲": "#eef3ea", "고지": "#eef1f6", "메마른 땅": "#f6f1e8", "상자 밖": "#f1f1f0"}
    fig, ax = plt.subplots(figsize=(12.8, 4.6), dpi=100)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    # 카메라가 있던 지역 띠 (캡처 간격 0.2 초, 장면 사이 빈 때는 그리지 않음)
    for a, b in zip(rows, rows[1:]):
        if b["t"] - a["t"] > 0.25:
            continue
        ax.axvspan(a["t"], b["t"], color=bands[region_of(*a["cam"])], lw=0)
    seg_start = 0
    for kind, label in (("rain", "비 세기 (숲 블루프린트)"), ("snow", "눈 세기 (고지 블루프린트)")):
        segs, cur = [], []
        for a in rows:
            if cur and a["t"] - cur[-1][0] > 0.25:
                segs.append(cur)
                cur = []
            cur.append((a["t"], a[kind]["alpha"]))
        segs.append(cur)
        for i, sgm in enumerate(segs):
            ax.plot([p[0] for p in sgm], [p[1] for p in sgm], color=colors[kind], lw=2, label=label if i == 0 else None,
                    solid_capstyle="round")
    # 지역 이름 (띠 위)
    last = None
    for a in rows:
        reg = region_of(*a["cam"])
        if reg != last:
            if 53.5 <= a["t"] <= 106:
                ax.text(a["t"] + 0.3, 1.08, reg, color=muted, fontsize=9, va="bottom")
            last = reg
    for ev in [e for e in transitions(rows, "rain") + transitions(rows, "snow") if e["continuous"]]:
        ax.axvline(ev["t"], color=muted, lw=1, ls=(0, (2, 2)))
    ax.set_ylim(-0.03, 1.2)
    ax.set_yticks([0, 0.5, 1.0])
    ax.set_xlabel("월드 시간 (초, -benchmark -fps=30)", color=ink)
    ax.set_ylabel("세기 (타임라인 Alpha, 0~1)", color=ink)
    ax.tick_params(colors=muted)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.grid(axis="y", color=grid, lw=1)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, -0.18), ncol=2, frameon=False, labelcolor=ink)
    ax.set_xlim(53.5, 106.5)
    note = dict(color=ink, fontsize=9, va="center")
    arrow = dict(arrowstyle="-", color=muted, lw=1)
    ax.annotate("숲에 들어감 (59 s)\n비 이펙트는 바로 켜지지만 세기 0", (59.0, 0.02), (55.0, 0.45), arrowprops=arrow, **note)
    ax.annotate("7 s 뒤 세지기 시작,\n5 s 동안 0 → 1", (68.5, 0.5), (60.6, 0.8), arrowprops=arrow, **note)
    ax.annotate("숲을 나옴 (79 s)\n곧 5 s 동안 약해짐", (81.5, 0.5), (84.0, 0.8), arrowprops=arrow, **note)
    ax.annotate("고지에 들어감 (96 s): 눈 알갱이는 바로 보이고\n세기 값만 7.5 s 뒤에 오른다", (104.2, 0.1), (92.4, 0.45),
                arrowprops=arrow, **note)
    ax.set_title("팀 지역 날씨 블루프린트의 세기 — 카메라가 경계를 걸어서 넘은 장면 (shc_pawn 판, 점선 = 경계를 넘은 때)",
                 color=ink, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(HERE / "weather_timeline.png", facecolor=surface)
    plt.close(fig)


def stills(frames: Path) -> None:
    """README 사진 (1280×720). frames = 촬영 출력 폴더."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype("malgun.ttf", 22)

    def img(run: str, f: int) -> Image.Image:
        return Image.open(frames / run / f"f_{f:05d}.png").convert("RGB")

    def tag(im: Image.Image, text: str) -> Image.Image:
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 12 + 12 * len(text), 34), fill=(20, 20, 20))
        d.text((8, 4), text, fill=(255, 255, 255), font=font)
        return im

    def save(im: Image.Image, name: str) -> None:
        im.resize((1280, 720), Image.LANCZOS).save(HERE / name, optimize=True)

    def sheet(run: str, items: list[tuple[int, str]], name: str) -> None:
        w = Image.new("RGB", (1920, 1080))
        for i, (f, text) in enumerate(items):
            w.paste(tag(img(run, f).resize((960, 540), Image.LANCZOS), text), ((i % 2) * 960, (i // 2) * 540))
        save(w, name)

    # 숲 비 (세기 1) + 이웃 프레임과의 차이 (빗줄기·물방울 고리만 남는다)
    save(tag(img("shc_pawn", 137), "숲 t=73.4 s 비 세기 1"), "forest_rain.png")
    a = np.asarray(img("shc_pawn", 0), dtype=float)
    b = np.asarray(img("shc_pawn", 1), dtype=float)
    diff = Image.fromarray(np.clip(np.abs(a - b).sum(2) * 3, 0, 255).astype("uint8")).convert("RGB")
    save(tag(diff, "숲 t=16.0 s 와 16.2 s 차이 (서 있는 카메라: 빗줄기·고리)"), "forest_rain_motion.png")
    save(tag(img("shc_pawn", 27), "고지 t=37.4 s 눈"), "highland_snow.png")
    save(tag(img("shc_pawn", 40), "메마른 땅 t=48 s 맑음"), "barren_clear.png")
    sheet("shc_pawn", [(234, "t=95.8 경계 1 m 앞 (메마른 땅)"), (236, "t=96.2 고지 1 m 안"), (240, "t=97.0"), (244, "t=97.8")],
          "snow_crossing.png")
    sheet("shc_sound", [(72, "메마른 땅 t=49 (고지 나온 지 3 초)"), (74, "t=50"), (76, "t=51"), (78, "t=52 꺼짐")],
          "barren_snow_after_leaving.png")
    w = Image.new("RGB", (1920, 540))
    w.paste(tag(img("shc_sunspeed", 0).resize((960, 540), Image.LANCZOS), "SunSpeed 10: t=8 s"), (0, 0))
    w.paste(tag(img("shc_sunspeed", 2).resize((960, 540), Image.LANCZOS), "t=14 s"), (960, 0))
    w.resize((1280, 360), Image.LANCZOS).save(HERE / "sunspeed_8s_14s.png", optimize=True)
    sheet("integration_v3", [(0, "통합 레벨 숲 wide"), (2, "숲 사슴"), (4, "고지 wide"), (6, "고지 사슴")],
          "integration_level.png")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=Path, default=None)
    args = ap.parse_args()
    s = summarize()
    plot_timeline()
    if args.frames:
        stills(args.frames)
    for run, v in s.items():
        print(run, json.dumps({k: v[k] for k in v if k not in ("rain", "snow")}, ensure_ascii=False))
        for kind in ("rain", "snow"):
            if isinstance(v.get(kind), dict):
                print("  ", kind, json.dumps(v[kind], ensure_ascii=False))


if __name__ == "__main__":
    main()
