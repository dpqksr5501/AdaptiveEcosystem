"""야생 3단계 지역 날씨 — 언리얼 통합 v3(나무 + 날씨, 기본값) 대 파이썬 거울 configs/v3_wild3_mirror.yaml 짝 비교 (10-18, README.md 4절).
herbivore_rl/ 에서

    python results/v3/wild3/compare_weather.py                       # 기본 경로 → compare_weather.md (표준 출력에도)
    python results/v3/wild3/compare_weather.py --unreal-dir <폴더> --python <판.json> --exports <폴더> --out <md>

언리얼: 10초 기록(../wild2/compare_unreal_wild2.py 의 줄들 — 첫 줄·경계 거리·사냥·은신처·늑대 무리·장애물)과 여덟째 줄 '<지역> 날씨 | <t>초 | …'
(EcoPolicyV3IntegratedSubsystem.cpp LogContext — 날씨 스텝, 감지 띠 '<5 m a/b' …, '들어서만 안 사슴·스텝 h/n'). 230초 줄을 쓴다(-seconds=240 의 마지막 기록 줄).
파이썬: run_mirror.py --diag --unreal-maps … --unreal-obstacles results/v3/wild2/trees/tree_layout.json 판(지도마다 그 지역 먹이 지도·나무·날씨, 반복 10).
  감지 띠·들어서만은 진단(band_pairs·band_seen·heard_live·live_obs — 240초까지)이다. 언리얼은 230초까지 — 비율로만 견준다.
표: 지역마다 언리얼 한 판(지도 3장 합) 대 파이썬 반복 10 판(지도 3장 합)의 평균 [최소..최대], z = (언리얼 − 파이썬 평균) ÷ 파이썬 반복 표준편차.
확인: 언리얼 내보내기(unreal_exports/s<세션>.json)의 지역 날씨 = 거울 설정 wild_weather.regions(+ 배수 계수), 원판 = 나무 배치 표(tree_layout.json) — 다르면 실패.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1] / "wild2"))

import compare_unreal_wild2 as cu  # noqa: E402

T_CMP = cu.T_CMP
BANDS = ("<5", "5~10", "10~15", "15~30")
WX = re.compile(r'\[EcoV3I\] (\S+) 날씨 \| ([\d.]+)초 \| (.*?) \| 날씨 스텝 누적 맑음 (\d+) · 비 (\d+) · 눈 (\d+) \| 감지 누적[^:]*: '
                r'<5 m (\d+)/(\d+) \([\d.]+%\) · 5~10 m (\d+)/(\d+) \([\d.]+%\) · 10~15 m (\d+)/(\d+) \([\d.]+%\) · 15~30 m (\d+)/(\d+) \([\d.]+%\) \| '
                r'들어서만 안 사슴·스텝 (\d+)/(\d+)')
WX_KO = {"맑음": "clear", "비": "rain", "눈": "snow"}
GROUPS = (("지도 모두", None), ("숲 (비)", "Forest"), ("고지 (눈)", "Highland"), ("메마른 땅 (맑음)", "Barren"))
SENSE_KEYS = tuple(f"sp{b}" for b in range(4)) + tuple(f"ss{b}" for b in range(4)) + ("heard", "live_obs")


def parse_unreal_weather(folder: Path, base: dict) -> dict:
    """compare_unreal_wild2.parse_unreal 결과에 230초 날씨 줄(감지 띠·들어서만·날씨)을 더한다."""
    for p in sorted(folder.glob("*.log")):
        m = cu.NAME.search(p.name)
        if not m:
            continue
        seed = int(m.group(2))
        for line in p.read_text(encoding="utf-8").splitlines():
            g = WX.search(line)
            if not g or float(g.group(2)) != T_CMP:
                continue
            d = base.setdefault((seed, g.group(1)), {})
            v = [int(x) for x in g.groups()[3:]]
            desc = g.group(3).split()
            d["weather"] = ("off", 0.0) if desc[0] == "날씨" else (WX_KO.get(desc[0], desc[0]), float(desc[1]))
            d["wx_steps"] = v[0:3]
            for b in range(4):
                d[f"ss{b}"] = v[3 + 2 * b]
                d[f"sp{b}"] = v[4 + 2 * b]
            d["heard"], d["live_obs"] = v[11], v[12]
    bad = [k for k, d in base.items() if "heard" not in d]
    if bad:
        raise SystemExit(f"언리얼 기록에 {T_CMP}초 날씨 줄이 없다: {bad}")
    return base


def parse_python_weather(paths) -> tuple[dict, dict]:
    """compare_unreal_wild2.parse_python 에 감지 띠·들어서만(진단)을 더한다. 세계 날씨도 돌려준다 (지도 → (날씨, 세기))."""
    py = cu.parse_python(paths)
    wx: dict = {}
    for p in paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        idx: dict = {}
        for w in d["worlds"]:
            m = w["meta"]
            key = (int(m["unreal_map"]["seed"]), m["unreal_map"]["region"])
            j = idx.get(key, 0)
            idx[key] = j + 1
            g = m["diag"]
            rec = py[key][j]
            for b in range(4):
                rec[f"sp{b}"] = g["band_pairs"][b]
                rec[f"ss{b}"] = g["band_seen"][b]
            if "heard_live" not in g:
                raise SystemExit(f"{p}: 진단에 heard_live 가 없다 — run_mirror.py 10-18 판으로 다시 돌린다")
            rec["heard"], rec["live_obs"] = g["heard_live"], g["live_obs"]
            wx[key] = (m["weather"]["kind"], float(m["weather"]["intensity"])) if "weather" in m else ("off", 0.0)
    return py, wx


def check_exports(exports: Path, sessions, cfg_path: Path, layout_path: Path) -> list[str]:
    """언리얼 내보내기의 지역 날씨·배수 = 거울 설정, 원판 = 나무 배치 표. 문제 목록(비면 같음)."""
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    wx = cfg["features"]["wild_weather"]
    layout = {r["region"]: [list(map(float, d)) for d in r["discs"]] for r in json.loads(layout_path.read_text(encoding="utf-8"))["regions"]}
    bad = []
    for s in sessions:
        e = json.loads((exports / f"s{s}.json").read_text(encoding="utf-8"))
        for r in e["regions"]:
            name, w = r["region"], r["weather"]
            want = wx["regions"].get(name, ["clear", 0.0])
            if not w["on"] or w["kind"] != want[0] or float(w["intensity"]) != float(want[1]):
                bad.append(f"s{s} {name}: 날씨 {w} ≠ 거울 {want}")
            for k in ("rain_sight", "rain_hear", "snow_sight", "snow_hear", "snow_deer_speed", "snow_wolf_speed"):
                if float(w[k]) != float(wx[k]):
                    bad.append(f"s{s} {name}: {k} {w[k]} ≠ {wx[k]}")
            if bool(w["obs_visibility"]) != bool(wx["obs_visibility"]) or int(w["schedule_rows"]) != 0:
                bad.append(f"s{s} {name}: visibility·시간표가 거울과 다르다")
            discs = [list(map(float, d)) for d in r["discs"]]
            if discs != layout.get(name, []):
                bad.append(f"s{s} {name}: 원판 {len(discs)} ≠ 배치 표 {len(layout.get(name, []))}")
    return bad


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


METRICS = (
    ("산 %", lambda d: pct(d["alive"], d["n"]), 1),
    ("잡힘 %", lambda d: pct(d["caught"], d["n"]), 2),
    ("굶음 %", lambda d: pct(d["starved"], d["n"]), 2),
    ("사냥 시작", lambda d: d["starts"], 1),
    ("사냥 성공률 %", lambda d: pct(d["success"], d["ends"]), 1),
    ("은신처 안 사슴·스텝 %", lambda d: pct(d["shelter"], d["live"]), 1),
) + tuple((f"알아챔 % {BANDS[b]} m", (lambda b_: (lambda d: pct(d[f"ss{b_}"], d[f"sp{b_}"])))(b), 1) for b in range(4)) + (
    ("들어서만 안 산 사슴·스텝 %", lambda d: pct(d["heard"], d["live_obs"]), 2),
)
KEYS = cu.KEYS + SENSE_KEYS


def group_table(title, maps, u, py, lines, out):
    U = {k: sum(u[m][k] for m in maps) for k in KEYS}
    reps = min(len(py[m]) for m in maps)
    P = [{k: sum(py[m][j][k] for m in maps) for k in KEYS} for j in range(reps)]
    lines += [f"\n### {title} (지도 {len(maps)}장, 파이썬 반복 {reps})\n", "| 칸 | 언리얼 | 파이썬 평균 [최소..최대] | z |", "|---|---|---|---|"]
    rows = {}
    for name, f, nd in METRICS:
        uv = f(U)
        vals = [f(p) for p in P]
        mu, sd, lo, hi = cu.stat(vals)
        z = (uv - mu) / sd if sd and sd > 0 and math.isfinite(sd) else float("nan")
        zs = f"{z:+.1f}" if math.isfinite(z) else "—"
        lines.append(f"| {name} | {uv:.{nd}f} | {mu:.{nd}f} [{lo:.{nd}f}..{hi:.{nd}f}] | {zs} |")
        rows[name] = dict(unreal=uv, python=mu, lo=lo, hi=hi, z=z if math.isfinite(z) else None)
    out[title] = rows


def effect_table(title, maps, u, ub, py, pb, lines, out):
    """날씨가 바꾼 것: 언리얼 (날씨 판 − 끈 판) 대 파이썬 짝 (반복 j 의 날씨 − 나무 거울, 같은 시드·지도) 차이 평균 ± 2 × 표준오차 [최소..최대]."""
    U = {k: sum(u[m][k] for m in maps) for k in KEYS}
    UB = {k: sum(ub[m][k] for m in maps) for k in KEYS}
    reps = min(min(len(py[m]), len(pb[m])) for m in maps)
    P = [{k: sum(py[m][j][k] for m in maps) for k in KEYS} for j in range(reps)]
    PB = [{k: sum(pb[m][j][k] for m in maps) for k in KEYS} for j in range(reps)]
    lines += [f"\n### 날씨가 바꾼 것 — {title} (지도 {len(maps)}장, 파이썬 짝 반복 {reps})\n",
              "| 칸 | 언리얼 차이 (날씨 − 끔) | 파이썬 짝 차이 평균 ± 2 × 표준오차 [최소..최대] | 언리얼이 파이썬 범위 안 |", "|---|---|---|---|"]
    rows = {}
    for name, f, nd in METRICS:
        du = f(U) - f(UB)
        dv = [f(x) - f(y) for x, y in zip(P, PB)]
        mu, sd, lo, hi = cu.stat(dv)
        se = sd / math.sqrt(len(dv)) if math.isfinite(sd) else float("nan")
        inside = (lo <= du <= hi) if math.isfinite(du) else False
        lines.append(f"| {name} | {du:+.{nd}f} | {mu:+.{nd}f} ± {2 * se:.{nd}f} [{lo:+.{nd}f}..{hi:+.{nd}f}] | {'예' if inside else '아니오'} |")
        rows[name] = dict(unreal=du, python=mu, se2=2 * se, lo=lo, hi=hi, inside=inside)
    out["effect " + title] = rows


def main(argv=None):
    base = ROOT / "results" / "v3"
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--unreal-dir", type=Path, default=base / "wild3" / "unreal_logs")
    ap.add_argument("--python", nargs="+", default=[str(base / "wild3" / "runs" / "wild3_240.json")])
    ap.add_argument("--exports", type=Path, default=base / "wild3" / "unreal_exports")
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "v3_wild3_mirror.yaml")
    ap.add_argument("--layout", type=Path, default=base / "wild2" / "trees" / "tree_layout.json")
    ap.add_argument("--out", type=Path, default=base / "wild3" / "compare_weather.md")
    ap.add_argument("--baseline", action="store_true", help="날씨를 끈 판끼리 (언리얼 -EcoV3Weather=0 대 파이썬 나무 거울) — 내보내기 확인을 건너뛴다")
    ap.add_argument("--base-unreal-dir", type=Path, default=base / "wild3" / "unreal_logs_weather_off",
                    help="날씨를 끈 언리얼 판 (날씨가 바꾼 것 표 — 없으면 건너뛴다)")
    ap.add_argument("--base-python", nargs="+", default=[str(base / "wild3" / "runs" / "trees_240.json")], help="날씨 없는 파이썬 짝 판 (나무 거울)")
    a = ap.parse_args(argv)
    u = parse_unreal_weather(a.unreal_dir, cu.parse_unreal(a.unreal_dir))
    py, pwx = parse_python_weather(a.python)
    maps = sorted(set(u) & set(py))
    if not maps:
        raise SystemExit("언리얼과 파이썬에 같은 지도가 없다")
    sessions = sorted({m[0] for m in maps})
    bad = [] if a.baseline else check_exports(a.exports, sessions, a.config, a.layout)
    for m in maps:
        if u[m]["weather"] != pwx[m]:
            bad.append(f"{m}: 언리얼 날씨 {u[m]['weather']} ≠ 파이썬 {pwx[m]}")
    reps = min(len(py[m]) for m in maps)
    if a.baseline:
        head = (f"날씨를 끈 기준 판: 언리얼 통합 v3 (나무, -EcoV3Weather=0) 세션 {sessions[0]}~{sessions[-1]} 240초 · 파이썬 configs/v3_wild2_trees_mirror.yaml 같은 먹이 지도·나무, "
                f"지도마다 반복 {reps}. 230초 줄(감지 띠·들어서만은 비율 — 언리얼 230초·파이썬 240초까지).")
        check = "확인: 지도마다 양쪽 모두 날씨 끔" if not bad else "다름 " + "; ".join(bad)
        groups = (("지도 모두", None), ("숲", "Forest"), ("고지", "Highland"), ("메마른 땅", "Barren"))
    else:
        head = (f"언리얼 통합 v3 기본값(나무 + 날씨) 세션 {sessions[0]}~{sessions[-1]} 240초 · 파이썬 configs/v3_wild3_mirror.yaml 같은 먹이 지도·나무·지역 날씨, 지도마다 반복 "
                f"{reps}. 230초 줄(감지 띠·들어서만은 비율 — 언리얼 230초·파이썬 240초까지).")
        check = ("확인: 내보내기 날씨·배수 = 거울 설정, 원판 = 나무 배치 표, 지도마다 날씨 = 파이썬 — 모두 같음" if not bad else "다름 " + "; ".join(bad))
        groups = GROUPS
    lines = ["# 야생 3단계 날씨 — 언리얼 대 파이썬 짝 비교 (자동 생성: compare_weather.py)", "", head, "", check]
    out: dict = {"ok": not bad, "problems": bad}
    for title, reg in groups:
        group_table(title, [m for m in maps if reg is None or m[1] == reg], u, py, lines, out)
    if not a.baseline and a.base_unreal_dir and a.base_unreal_dir.exists():
        ub = parse_unreal_weather(a.base_unreal_dir, cu.parse_unreal(a.base_unreal_dir))
        pb, _ = parse_python_weather(a.base_python)
        em = [m for m in maps if m in ub and m in pb]
        lines += ["", "## 날씨가 바꾼 것 (같은 세션·지도에서 날씨 판 − 날씨 끈 판)", "",
                  f"언리얼: {a.base_unreal_dir.name} (-EcoV3Weather=0) 한 판씩. 파이썬: 나무 거울 짝(같은 시드·같은 지도). 메마른 땅(맑음)은 양쪽 모두 0 이어야 한다."]
        for title, reg in GROUPS:
            sel = [m for m in em if reg is None or m[1] == reg]
            if sel:
                effect_table(title, sel, u, ub, py, pb, lines, out)
    text = "\n".join(lines) + "\n"
    a.out.write_text(text, encoding="utf-8", newline="\n")
    a.out.with_suffix(".json").write_text(json.dumps(out, ensure_ascii=False, indent=1, allow_nan=True), encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
