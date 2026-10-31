"""언리얼 통합 v3 기록과 파이썬 거울(run_mirror.py) 결과를 나란히 본다 (10-15 사용자 '언리얼에서 돌리는 게 파이썬과 얼마나 비슷한지').

    # herbivore_rl/ 에서
    python results/v3/mirror/compare_unreal.py --unreal-dir <언리얼 기록 폴더>                    # 파이썬은 runs/*.json 전부
    python results/v3/mirror/compare_unreal.py --unreal-dir <폴더> --python results/v3/mirror/runs/d128_*.json --out cmp.md

언리얼 기록: --unreal-dir 아래(하위 폴더 포함)의 d<사슴>_s<세션 시드>_k<경계 거리>[_e<식사 초>].log — 팀 레벨 헤드리스 240초, 한 파일 = 세션
하나 = 지역 3개. 10초 줄 '[EcoV3I] <지역> | <t>초 ...'의 사슴 산·포획 누적·굶음 누적·무대 먹이 %·사슴 에너지 평균·굶주림을 읽는다(정의는
run_mirror.py docstring — 같은 정의로 적었다). _e 가 없으면 식사 5초(38스텝), e30·e60 은 225·450스텝. 기본은 경계 거리 끔(k0)만 읽는다.
파이썬: run_mirror.py 의 JSON. 시드를 적은 순서대로 3개씩 묶어 한 세션(지역 3개)으로 본다(남는 세계는 버린다). 짝 비교 JSON(--unreal-maps,
언리얼 지역 무대와 같은 먹이 지도)은 따로 본다 — 세션 = (언리얼 세션 시드, 반복 번호)의 지역 3개이고, 지도마다 언리얼 값 하나와 파이썬 반복
여럿(평균 [최소..최대])을 나란히 둔 표를 더 낸다.

집계(언리얼 쪽은 예전 scratchpad parse_density.py 와 같다): 시각 t(60·120·180·230초)마다 세션의 지역 3개를 더해 산·포획·굶음 비율을 내고
세션 평균을 낸다. 세션 범위 [최소..최대], 지역 굶음 30% 넘은 지역 비율(지도가 무너진 지역 — 굶음은 먹이 지도 운이 크게 정한다),
z = (언리얼 세션 평균 − 파이썬 세션 평균) ÷ (파이썬 세션 표준편차 ÷ √언리얼 세션 수) 를 함께 적는다 — |z| < 2 면 파이썬에서 세션을 언리얼만큼
뽑았을 때 흔히 나오는 차이다(언리얼 표본이 세션 3개라 평균 자체가 흔들린다).
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve()
RUNS = HERE.parent / "runs"
TIMES = (60.0, 120.0, 180.0, 230.0)
COLLAPSE = 0.30                      # 지역 굶음이 처음 사슴의 이 비율 이상이면 '무너진 지역'
STEP_SECONDS = 8.0 / 60.0
DEFAULT_EAT_SECONDS = 5.0            # 파일 이름에 _e 가 없는 기록(eco.IntegratedV3.WolfEatSeconds 기본 5)
MAIN = re.compile(r'\[EcoV3I\] (\S+) \| ([\d.]+)초 (낮|밤)?.*?사슴 산 (\d+)/(\d+).*?포획 (\d+) \(누적 (\d+)\) 굶음 (\d+) \(누적 (\d+)\)'
                  r'.*?무대 먹이 처음의 ([\d.]+)% · 사슴 에너지 평균 ([\d.]+)% · 굶주림\(15% 아래\) (\d+)')
NAME = re.compile(r'd(\d+)_s(\d+)_k(\d)(?:_e(\d+))?\.log$')


def eat_steps_of_seconds(sec: float) -> int:
    """식사 초 → 스텝 = 반올림(초 ÷ 8/60), 0.5 는 올림(C++ WolfEatSteps)."""
    return int(math.floor(sec / STEP_SECONDS + 0.5))


def parse_unreal_log(path) -> dict[str, dict[float, dict]]:
    """기록 하나 → 지역 → t(초) → {alive, n, caught, starved, food, energy, hungry}."""
    txt = io.open(path, "rb").read().decode("utf-8", "replace")
    rows: dict[str, dict[float, dict]] = defaultdict(dict)
    for line in txt.splitlines():
        if "[EcoV3I]" not in line:
            continue
        m = MAIN.search(line)
        if m:
            rows[m.group(1)][float(m.group(2))] = dict(
                alive=int(m.group(4)), n=int(m.group(5)), caught=int(m.group(7)), starved=int(m.group(9)),
                food=float(m.group(10)), energy=float(m.group(11)), hungry=int(m.group(12)))
    return dict(rows)


def load_unreal(unreal_dir, keepaway: int = 0) -> dict[tuple[int, int], list[list[dict[float, dict]]]]:
    """(사슴, 식사 스텝) → 세션 목록(세션 = 지역별 t → 줄 사전의 목록, 지역 이름 순). 경계 거리 keepaway 인 기록만."""
    out: dict[tuple[int, int], list] = defaultdict(list)
    for p in sorted(glob.glob(str(Path(unreal_dir) / "**" / "*.log"), recursive=True)):
        m = NAME.search(Path(p).name)
        if not m or int(m.group(3)) != keepaway:
            continue
        deer = int(m.group(1))
        eat = eat_steps_of_seconds(float(m.group(4)) if m.group(4) else DEFAULT_EAT_SECONDS)
        rows = parse_unreal_log(p)
        if rows:
            out[(deer, eat)].append([rows[r] for r in sorted(rows)])
    return dict(out)


def _region_rows(wd) -> dict[float, dict]:
    return {float(r["t_s"]): dict(alive=r["alive"], n=r["n"], caught=r["caught"], starved=r["starved"], food=r["food_pct"],
                                  energy=r["energy_pct"], hungry=r["hungry"]) for r in wd["rows"]}


def load_python(paths, paired: bool = False) -> dict[tuple[int, int], list[list[dict[float, dict]]]]:
    """run_mirror.py JSON 들 → (사슴, 식사 스텝) → 세션 목록. paired 가 거짓이면 짝 비교가 아닌 JSON 만 읽고 시드 순서대로 3개씩, 참이면 짝 비교
    JSON 만 읽고 (언리얼 세션 시드, 반복 번호)마다 지역 3개(지역 이름 순)를 한 세션으로 묶는다."""
    out: dict[tuple[int, int], list] = defaultdict(list)
    for p in paths:
        res = json.loads(Path(p).read_text(encoding="utf-8"))
        meta = res["meta"]
        if bool(meta.get("unreal_maps")) != paired:
            continue
        key = (int(meta["deer"]), int(meta["eat_steps"]))
        if paired:
            groups: dict[tuple[int, int], dict[str, dict]] = defaultdict(dict)
            for wd in res["worlds"]:
                um = wd["meta"]["unreal_map"]
                groups[(int(um["seed"]), int(um["replicate"]))][um["region"]] = _region_rows(wd)
            for g in sorted(groups):
                out[key].append([groups[g][r] for r in sorted(groups[g])])
            continue
        k = int(meta.get("session_size", 3))
        regions = [_region_rows(wd) for wd in res["worlds"]]
        for i in range(0, len(regions) - k + 1, k):
            out[key].append(regions[i:i + k])
    return dict(out)


def load_python_maps(paths) -> dict[tuple[int, int], dict[tuple[int, str], list[dict[float, dict]]]]:
    """짝 비교 JSON → (사슴, 식사 스텝) → (언리얼 세션 시드, 지역) → 파이썬 반복의 줄 목록."""
    out: dict = defaultdict(lambda: defaultdict(list))
    for p in paths:
        res = json.loads(Path(p).read_text(encoding="utf-8"))
        meta = res["meta"]
        if not meta.get("unreal_maps"):
            continue
        for wd in res["worlds"]:
            um = wd["meta"]["unreal_map"]
            out[(int(meta["deer"]), int(meta["eat_steps"]))][(int(um["seed"]), um["region"])].append(_region_rows(wd))
    return {k: dict(v) for k, v in out.items()}


def load_unreal_maps(unreal_dir, keepaway: int = 0) -> dict[tuple[int, int], dict[tuple[int, str], dict[float, dict]]]:
    """언리얼 기록 → (사슴, 식사 스텝) → (세션 시드, 지역) → 줄."""
    out: dict = defaultdict(dict)
    for p in sorted(glob.glob(str(Path(unreal_dir) / "**" / "*.log"), recursive=True)):
        m = NAME.search(Path(p).name)
        if not m or int(m.group(3)) != keepaway:
            continue
        eat = eat_steps_of_seconds(float(m.group(4)) if m.group(4) else DEFAULT_EAT_SECONDS)
        for reg, rows in parse_unreal_log(p).items():
            out[(int(m.group(1)), eat)][(int(m.group(2)), reg)] = rows
    return dict(out)


def map_table(unreal_maps, python_maps, times=(60.0, 230.0)) -> str:
    """짝 비교: 지도(언리얼 세션 시드·지역)마다 언리얼 산·포획·굶음 마리 수와 같은 지도 파이썬 반복의 평균 [최소..최대]."""
    lines = ["| 사슴/지역 | 식사 | 지도 | t(초) | 언리얼 산·포획·굶음 | 파이썬 같은 지도 산 | 포획 | 굶음 | 반복 |", "|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(set(unreal_maps) & set(python_maps), key=lambda k: (k[1], -k[0])):
        deer, eat = key
        for mp in sorted(set(unreal_maps[key]) & set(python_maps[key])):
            u, ps = unreal_maps[key][mp], python_maps[key][mp]
            for t in times:
                if t not in u or not all(t in p for p in ps):
                    continue
                cells = []
                for k in ("alive", "caught", "starved"):
                    v = [p[t][k] for p in ps]
                    cells.append(f"{sum(v) / len(v):.1f} [{min(v)}..{max(v)}]")
                lines.append(f"| {deer} | {eat * STEP_SECONDS:.0f}초 | {mp[0]} {mp[1]} | {t:.0f} | {u[t]['alive']}·{u[t]['caught']}·{u[t]['starved']} | "
                             + " | ".join(cells) + f" | {len(ps)} |")
    return "\n".join(lines)


def summarize(sessions, t: float) -> dict | None:
    """세션 목록의 시각 t 요약. 지역 하나라도 그 줄이 없으면 그 세션을 뺀다. 세션이 없으면 None."""
    per = []
    regions = []
    for sess in sessions:
        if not all(t in reg for reg in sess):
            continue
        tot = {key: sum(reg[t][key] for reg in sess) for key in ("alive", "n", "caught", "starved", "hungry")}
        per.append(dict(alive=tot["alive"] / tot["n"], caught=tot["caught"] / tot["n"], starved=tot["starved"] / tot["n"],
                        energy=sum(reg[t]["energy"] for reg in sess) / len(sess),
                        food=sum(reg[t]["food"] for reg in sess) / len(sess)))
        regions.extend(dict(dead=1 - reg[t]["alive"] / reg[t]["n"], starved=reg[t]["starved"] / reg[t]["n"]) for reg in sess)
    if not per:
        return None

    def stat(key):
        v = [x[key] for x in per]
        m = sum(v) / len(v)
        sd = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1)) if len(v) > 1 else float("nan")
        return dict(mean=m, sd=sd, lo=min(v), hi=max(v))

    return dict(n_sessions=len(per), n_regions=len(regions), **{k: stat(k) for k in ("alive", "caught", "starved", "energy", "food")},
                collapse=sum(r["starved"] >= COLLAPSE for r in regions) / len(regions),
                region_dead=(min(r["dead"] for r in regions), max(r["dead"] for r in regions)),
                region_starved=(min(r["starved"] for r in regions), max(r["starved"] for r in regions)))


def z_of(u: dict, p: dict, key: str) -> float:
    """언리얼 세션 평균이 파이썬 세션 평균에서 '세션 수가 언리얼만큼일 때의 표준오차' 몇 개 떨어졌나."""
    se = p[key]["sd"] / math.sqrt(u["n_sessions"])
    return (u[key]["mean"] - p[key]["mean"]) / se if se > 0 else float("nan")


def table(unreal, python) -> str:
    """조건(사슴·식사)마다 시각별 한 줄. 비율은 처음 사슴 대비 %."""
    pct = lambda x: f"{100 * x:5.1f}"
    lines = ["| 사슴/지역 | 식사 | t(초) | 언리얼 산·포획·굶음 % (세션) | 파이썬 산·포획·굶음 % (세션) | 차이 파이썬−언리얼 %p | z 산·포획·굶음 | "
             "무너진 지역(굶음 ≥ 30%) 언리얼·파이썬 | 지역 굶음 % 범위 언리얼·파이썬 | 에너지·먹이 % 언리얼·파이썬 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    keys = sorted(set(unreal) | set(python), key=lambda k: (k[1], -k[0]))
    for key in keys:
        deer, eat = key
        for t in TIMES:
            u = summarize(unreal.get(key, []), t)
            p = summarize(python.get(key, []), t)
            if u is None and p is None:
                continue
            cell_u = (f"{pct(u['alive']['mean'])}·{pct(u['caught']['mean'])}·{pct(u['starved']['mean'])} ({u['n_sessions']})"
                      if u else "—")
            cell_p = (f"{pct(p['alive']['mean'])}·{pct(p['caught']['mean'])}·{pct(p['starved']['mean'])} ({p['n_sessions']})"
                      if p else "—")
            if u and p:
                diff = "·".join(f"{100 * (p[k]['mean'] - u[k]['mean']):+5.1f}" for k in ("alive", "caught", "starved"))
                zs = "·".join(f"{z:+4.1f}" if math.isfinite(z) else "  —"            # 파이썬 세션 편차가 0 이면 z 가 없다
                              for z in (z_of(u, p, k) for k in ("alive", "caught", "starved")))
            else:
                diff = zs = "—"
            col = f"{u['collapse'] * 100:.0f}%·{p['collapse'] * 100:.0f}%" if u and p else "—"
            rng = (f"{100 * u['region_starved'][0]:.0f}..{100 * u['region_starved'][1]:.0f}·"
                   f"{100 * p['region_starved'][0]:.0f}..{100 * p['region_starved'][1]:.0f}") if u and p else "—"
            ef = (f"{u['energy']['mean']:.0f}/{u['food']['mean']:.0f}·{p['energy']['mean']:.0f}/{p['food']['mean']:.0f}"
                  if u and p else "—")
            lines.append(f"| {deer} | {eat * STEP_SECONDS:.0f}초({eat}) | {t:.0f} | {cell_u} | {cell_p} | {diff} | {zs} | {col} | {rng} | {ef} |")
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--unreal-dir", required=True, help="언리얼 기록 폴더 (d<사슴>_s<시드>_k<경계>[_e<초>].log, 하위 폴더 포함)")
    ap.add_argument("--python", nargs="*", default=None, help="run_mirror.py JSON (기본 runs/*.json, 이름이 _ 로 시작하면 뺀다)")
    ap.add_argument("--keepaway", type=int, default=0, help="언리얼 경계 거리 기록 (0 = 끔, 비교 기준)")
    ap.add_argument("--out", type=Path, default=None, help="표를 Markdown 으로도 쓴다")
    a = ap.parse_args(argv)
    paths = a.python if a.python else [p for p in sorted(glob.glob(str(RUNS / "*.json"))) if not Path(p).name.startswith("_")]
    files = sorted({f for p in paths for f in glob.glob(p)})
    unreal = load_unreal(a.unreal_dir, a.keepaway)
    python = load_python(files)
    paired = load_python(files, paired=True)
    if not unreal:
        print(f"언리얼 기록이 없다: {a.unreal_dir}", file=sys.stderr)
    if not python and not paired:
        print("파이썬 결과가 없다(run_mirror.py 를 먼저 돌린다)", file=sys.stderr)
    parts = [f"## 독립 지도 (파이썬 세계마다 다른 먹이 지도)\n\n{table(unreal, python)}"]
    if paired:
        parts.append(f"## 같은 지도 짝 비교 (언리얼 지역 무대의 먹이 지도, 다른 난수는 파이썬)\n\n{table(unreal, paired)}")
        parts.append(f"### 지도마다\n\n{map_table(load_unreal_maps(a.unreal_dir, a.keepaway), load_python_maps(files))}")
    out = "\n\n".join(parts)
    print(out)
    if a.out:
        a.out.write_text(out + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
