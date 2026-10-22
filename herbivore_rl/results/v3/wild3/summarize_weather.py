"""야생 3단계 지역 날씨 표 (results/v3/wild3/README.md). herbivore_rl/ 에서

    python results/v3/wild3/summarize_weather.py              # runs/ 의 판들 → summary.md·summary.json (표준 출력에도)

판(run_all.sh): trees_240·wild3_240·wild3_novis_240·wild3_snow05_240·wild3_snowspeed_240·wild3_snowsight_240(240초, 지도 9장 × 반복 10 = 90 세계),
trees_16m·wild3_16m(16분, 지도 30장 × 1 = 30 세계).
기준(trees) 과 날씨 판은 세계마다 같은 시드·같은 먹이 지도·같은 나무 원판이고 날씨만 다르다(짝). 메마른 땅은 맑음이라 두 판이 같아야 한다(어긋나면 실패).

칸 (정의는 env_v2/world.py 모듈 docstring '야생 3단계', results/v3/mirror/run_mirror.py 머리 주석):
  산·잡힘·굶음 %   마지막 줄(240초·960초) — 처음 사슴 대비, 그 지역 세계 모두 합
  사냥 · 성공률    늑대 사냥 시작 수(전력 걸음 시작)와 끝난 사냥 가운데 잡음으로 끝난 몫
  도망 · 숨기 %    산 사슴-스텝 가운데 그 스텝 행동이 FLEE·HIDE 인 몫(진단 beh_steps)
  은신처 안 %      스텝 첫머리 산 사슴 가운데 이동 뒤 위치가 은신처 원 안인 몫
  알아챔 % (거리)  산 사슴 × 깨어 있는 늑대 쌍 가운데 사슴이 그 늑대를 감지한(보임·들림 — 관측과 같은 판정) 몫, 거리 구간 m(진단 band_pairs·band_seen)
  들어서만 %       위협이 감지됐는데 눈으로는 하나도 안 보인 사슴-스텝 몫(세계 평균, realism_stats heard_only_frac)
  짝 차이          세계마다 (날씨 − 기준) 의 평균 ± 2 × 표준오차(지역 세계 수로), z = 평균 ÷ 표준오차. 잡힘·산은 %p(사슴 128 대비)
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
BANDS = ("<5", "5~10", "10~15", "15~30")
GROUPS = (("모두", None), ("숲 (비)", "Forest"), ("고지 (눈)", "Highland"), ("메마른 땅 (맑음)", "Barren"))
FLEE, HIDE = 1, 2
PAIRS_240 = (("trees_240", "wild3_240", "날씨 (기본)"), ("trees_240", "wild3_novis_240", "날씨, visibility 에 안 실음"),
             ("trees_240", "wild3_snow05_240", "날씨, 고지 눈 세기 0.5"), ("trees_240", "wild3_snowspeed_240", "날씨, 눈은 이동만(시야 1)"),
             ("trees_240", "wild3_snowsight_240", "날씨, 눈은 시야만(이동 1)"))
PAIRS_16 = (("trees_16m", "wild3_16m", "날씨 (기본)"),)


def load(name: str) -> dict:
    return json.loads((RUNS / f"{name}.json").read_text(encoding="utf-8"))


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def agg(ws: list[dict]) -> dict:
    t = dict(worlds=len(ws), n=0, alive=0, caught=0, starved=0, starts=0, ends=0, success=0, shelter=0, live=0, beh=[0] * 5,
             pairs=[0] * len(BANDS), seen=[0] * len(BANDS), heard=[])
    for w in ws:
        last, m = w["rows"][-1], w["meta"]
        g = m["diag"]
        t["n"] += last["n"]
        t["alive"] += last["alive_end"]
        t["caught"] += last["caught"]
        t["starved"] += last["starved"]
        for k in ("starts", "ends", "success"):
            t[k] += m["hunt"][k]
        t["shelter"] += m["shelter_steps"]
        t["live"] += m["live_steps"]
        t["beh"] = [a + b for a, b in zip(t["beh"], g["beh_steps"])]
        t["pairs"] = [a + b for a, b in zip(t["pairs"], g["band_pairs"])]
        t["seen"] = [a + b for a, b in zip(t["seen"], g["band_seen"])]
        if m.get("heard_only_frac") is not None:
            t["heard"].append(m["heard_only_frac"])
    nb = sum(t["beh"])
    return dict(worlds=t["worlds"], alive_pct=pct(t["alive"], t["n"]), caught_pct=pct(t["caught"], t["n"]), starved_pct=pct(t["starved"], t["n"]),
                hunts=t["starts"], hunt_rate_pct=pct(t["success"], t["ends"]), flee_pct=pct(t["beh"][FLEE], nb), hide_pct=pct(t["beh"][HIDE], nb),
                shelter_pct=pct(t["shelter"], t["live"]), seen_pct=[pct(s, p) for s, p in zip(t["seen"], t["pairs"])],
                heard_only_pct=100.0 * sum(t["heard"]) / len(t["heard"]) if t["heard"] else float("nan"))


def per_world(w: dict) -> dict:
    last, g = w["rows"][-1], w["meta"]["diag"]
    nb = sum(g["beh_steps"])
    return dict(caught=pct(last["caught"], last["n"]), alive=pct(last["alive_end"], last["n"]), flee=pct(g["beh_steps"][FLEE], nb))


def paired(base: list[dict], wx: list[dict]) -> dict:
    out = {}
    for key in ("caught", "alive", "flee"):
        d = [per_world(x)[key] - per_world(b)[key] for b, x in zip(base, wx)]      # 날씨 − 기준
        k = len(d)
        mu = sum(d) / k
        sd = math.sqrt(sum((v - mu) ** 2 for v in d) / (k - 1)) if k > 1 else float("nan")
        se = sd / math.sqrt(k) if k > 1 else float("nan")
        out[key] = dict(mean=mu, se2=2.0 * se, z=(mu / se) if se and se > 0 else (0.0 if mu == 0 else float("inf")))
    return out


def check_pair(a: dict, b: dict) -> None:
    """같은 시드·지도·지역 순서이고, 맑은 지역은 날씨 판과 기준 판이 같아야 한다(줄·죽음·사냥)."""
    if len(a["worlds"]) != len(b["worlds"]):
        raise SystemExit("두 판의 세계 수가 다르다")
    for x, y in zip(a["worlds"], b["worlds"]):
        mx, my = x["meta"], y["meta"]
        if mx["seed"] != my["seed"] or mx["unreal_map"] != my["unreal_map"]:
            raise SystemExit(f"짝이 아니다: {mx['seed']} {mx['unreal_map']} vs {my['seed']} {my['unreal_map']}")
        if mx["unreal_map"]["region"] == "Barren":
            same = (x["rows"] == [{k: r[k] for k in x["rows"][0]} for r in y["rows"]] and mx["death_t"] == my["death_t"]
                    and mx["hunt"] == my["hunt"])
            if not same:
                raise SystemExit(f"맑은 지역(메마른 땅) 세계 {mx['seed']} 가 기준과 다르다 — 날씨가 맑은 지역에 샜다")


def region_of(w):
    return w["meta"]["unreal_map"]["region"]


def f1(x, nd=1):
    return "—" if x != x else f"{x:.{nd}f}"


def table(base_name: str, runs: list[tuple[str, str]], title: str, lines: list[str], out: dict) -> None:
    b = load(base_name)
    rs = [(load(n), label, n) for n, label in runs]
    for r, _, _ in rs:
        check_pair(b, r)
    sec = b["meta"]["steps"] * 8.0 / 60.0
    span = f"{sec / 60.0:.0f}분" if sec >= 600 else f"{sec:.0f}초"
    lines += [f"\n### {title} ({span}, 사슴 128, 두뇌 R1b-F argmax)\n",
              "| 지역 | 판 | 세계 | 산 % | 잡힘 % | 굶음 % | 사냥 · 성공률 % | 도망 % | 숨기 % | 은신처 안 % | 알아챔 % <5 · 5~10 · 10~15 · 15~30 m | 들어서만 % |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for gname, reg in GROUPS:
        sel = lambda d: [w for w in d["worlds"] if reg is None or region_of(w) == reg]   # noqa: E731
        for d, label, key in [(b, "나무 거울 (날씨 없음)", base_name)] + rs:
            a = agg(sel(d))
            out.setdefault(key, {})[reg or "all"] = a
            lines.append(f"| {gname} | {label} | {a['worlds']} | {f1(a['alive_pct'])} | {f1(a['caught_pct'], 2)} | {f1(a['starved_pct'], 2)} | "
                         f"{a['hunts']} · {f1(a['hunt_rate_pct'])} | {f1(a['flee_pct'], 2)} | {f1(a['hide_pct'], 2)} | {f1(a['shelter_pct'])} | "
                         f"{' · '.join(f1(v, 0) for v in a['seen_pct'])} | {f1(a['heard_only_pct'])} |")
    lines += ["\n| 지역 | 판 | 잡힘 짝 차이 %p (± 2SE, z) | 산 짝 차이 %p (± 2SE, z) | 도망 몫 짝 차이 %p (± 2SE, z) |", "|---|---|---|---|---|"]
    for gname, reg in GROUPS:
        bw = [w for w in b["worlds"] if reg is None or region_of(w) == reg]
        for d, label, key in rs:
            xw = [w for w in d["worlds"] if reg is None or region_of(w) == reg]
            p = paired(bw, xw)
            out.setdefault(key, {}).setdefault("paired", {})[reg or "all"] = p
            cell = lambda q: f"{q['mean']:+.2f} ± {q['se2']:.2f} ({q['z']:+.1f})"   # noqa: E731
            lines.append(f"| {gname} | {label} | {cell(p['caught'])} | {cell(p['alive'])} | {cell(p['flee'])} |")


def main(argv=None) -> None:
    lines = ["# 야생 3단계 지역 날씨 — 지금 게임 두뇌(R1b-F) 측정 (자동 생성: summarize_weather.py)",
             "", "기준 = configs/v3_wild2_trees_mirror.yaml, 날씨 = configs/v3_wild3_mirror.yaml. 지도 (세션, 지역) 마다 언리얼과 같은 먹이 지도·나무 원판·지역 날씨,"
             " 기준과 날씨 판은 같은 시드 짝. 메마른 땅(맑음)은 두 판의 10초 줄·죽음·사냥 칸이 같음을 확인했다(비트 동일은 tests/test_wild3_weather.py)."]
    out: dict = {}
    table("trees_240", [(n, lab) for _, n, lab in PAIRS_240 if (RUNS / f"{n}.json").exists()], "240초 짝 비교", lines, out)
    if (RUNS / "trees_16m.json").exists() and (RUNS / "wild3_16m.json").exists():
        table("trees_16m", [(n, lab) for _, n, lab in PAIRS_16], "16분 짝 비교", lines, out)
    text = "\n".join(lines) + "\n"
    (HERE / "summary.md").write_text(text, encoding="utf-8", newline="\n")
    (HERE / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, allow_nan=True), encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
