"""야생 2단계 1 — 언리얼 통합 v3 기록과 파이썬 거울 짝 비교(같은 먹이 지도)를 나란히 본다 (10-17, README.md '언리얼').

    # herbivore_rl/ 에서
    python results/v3/wild2/compare_unreal_wild2.py --unreal-dir results/v3/wild2/unreal_logs/food1_s20000-20002 \
        --python results/v3/wild2/runs/pair_d128_wild2_u20000-20002_k10.json

언리얼: 10초 기록 첫 줄 '[EcoV3I] <지역> | <t>초 ... 사슴 산 a/n ... 포획 x (누적 c) 굶음 y (누적 s)', 셋째 줄 '<지역> 경계 거리 | ... 은신처 안 잡힘 x (누적 k)',
다섯째 줄 '<지역> 사냥·은신처 | ...'(EcoPolicyV3IntegratedSubsystem.cpp LogContext — 사냥 누적·은신처 안 사슴·스텝 누적·둘레 밖 잡힘 누적). 230초 줄(-seconds=240 의
마지막 기록 줄)을 쓴다. 기록 이름 d<사슴>_s<세션 시드>_k0.log (trim_unreal_log.py).
파이썬: run_mirror.py --unreal-maps … --diag 결과. 세계마다 meta.unreal_map(세션 시드·지역·반복)과 230초 줄(누적 hunt_*·shelter_steps·live_steps, caught·starved).
둘레 밖 잡힘·원 안 잡힘은 파이썬 진단이 240초까지 센 값이다(언리얼은 230초까지 — 10초 차이).
표: 지도 9장 합(언리얼 한 판 대 파이썬 반복 10판의 평균 [최소..최대]), 숲(Forest) 지도 3장만, 지도마다. z = (언리얼 − 파이썬 평균) ÷ 파이썬 반복 표준편차.
10-17 더함(야생 2단계 2 늑대 무리): 언리얼 여섯째 줄 '<지역> 늑대 무리 | ...'(협동 사냥을 켰을 때만)과 파이썬 10초 줄의 pack_*(run_mirror.py, wild_pack 을 켠
세계)이 모두 있으면 표에 앞장·돕기·은신처 문 늑대-스텝 몫과 늑대 포획·협동 포획 줄을 더한다.
--independent: 파이썬이 짝 비교가 아닌 독립 지도 판(run_mirror.py --diag, 메타에 unreal_map 없음)이면 세계를 앞에서부터 언리얼 지역 수(9)씩 묶어 반복으로 보고
'지도 모두' 표만 낸다(지도가 서로 다르다 — 숲 줄은 없다).
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

T_CMP = 230.0
NAME = re.compile(r'd(\d+)_s(\d+)_k(\d)(?:_e(\d+))?\.log$')
MAIN = re.compile(r'\[EcoV3I\] (\S+) \| ([\d.]+)초 (?:낮|밤)?.*?사슴 산 (\d+)/(\d+).*?포획 \d+ \(누적 (\d+)\) 굶음 \d+ \(누적 (\d+)\)')
KEEP = re.compile(r'\[EcoV3I\] (\S+) 경계 거리 \| ([\d.]+)초 \| .*?은신처 안 잡힘 \d+ \(누적 (\d+)\)')
HUNT = re.compile(r'\[EcoV3I\] (\S+) 사냥·은신처 \| ([\d.]+)초 \| 사냥 누적: 시작 (\d+) · 끝 (\d+) · 성공 (\d+) · 사냥 밖 포획 (\d+) · 성공률 [\d.]+% '
                  r'\(추격형 시작 (\d+) 끝 (\d+) 성공 (\d+) · 잠행형 시작 (\d+) 끝 (\d+) 성공 (\d+)\).*?누적 (\d+)/(\d+) .*?2 m 안 (\d+) · 4 m 안 (\d+)')
PACK = re.compile(r'\[EcoV3I\] (\S+) 늑대 무리 \| ([\d.]+)초 \| 늑대 \d+ \| 누적 늑대·스텝 (\d+): 앞장 (\d+) \([\d.]+%\) · 돕기 (\d+) \([\d.]+%\) · '
                  r'기다림 (\d+) · 은신처 문 (\d+) \| 늑대 포획 누적 (\d+) · 협동 포획 (\d+)')
KEYS = ("n", "alive", "caught", "starved", "starts", "ends", "success", "outside", "ch_e", "ch_s", "st_e", "st_s", "shelter", "live", "ring2",
        "ring4", "cover")
PACK_KEYS = ("pk_steps", "pk_lead", "pk_help", "pk_wait", "pk_door", "pk_catch", "pk_coop")


def parse_unreal(folder: Path) -> dict[tuple[int, str], dict]:
    out: dict[tuple[int, str], dict] = {}
    for p in sorted(folder.glob("*.log")):
        m = NAME.search(p.name)
        if not m:
            continue
        seed = int(m.group(2))
        for line in p.read_text(encoding="utf-8").splitlines():
            for rx, kind in ((MAIN, "main"), (KEEP, "keep"), (HUNT, "hunt"), (PACK, "pack")):
                g = rx.search(line)
                if not g or float(g.group(2)) != T_CMP:
                    continue
                d = out.setdefault((seed, g.group(1)), {})
                v = [int(x) for x in g.groups()[2:]]
                if kind == "main":
                    d.update(alive=v[0], n=v[1], caught=v[2], starved=v[3])
                elif kind == "keep":
                    d.update(cover=v[0])
                elif kind == "pack":
                    d.update(zip(PACK_KEYS, v))
                else:
                    d.update(starts=v[0], ends=v[1], success=v[2], outside=v[3], ch_e=v[5], ch_s=v[6], st_e=v[8], st_s=v[9], shelter=v[10],
                             live=v[11], ring2=v[12], ring4=v[13])
    bad = [k for k, d in out.items() if not set(KEYS) <= set(d)]
    if bad:
        raise SystemExit(f"언리얼 기록에 {T_CMP}초 줄이 모자라다: {bad}")
    return out


def parse_python(paths, block: int = 0) -> dict[tuple[int, str], list[dict]]:
    """짝 비교: 지도 (세션 시드, 지역) → 반복 목록. block > 0(독립 지도): 세계 i 를 가짜 지도 (i mod block, '') 의 반복으로 둔다."""
    out: dict[tuple[int, str], list[dict]] = {}
    i = 0
    for p in paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        for w in d["worlds"]:
            m = w["meta"]
            um = m["unreal_map"] if not block else dict(seed=i % block, region="")
            i += 1
            r = next(x for x in w["rows"] if x["t_s"] == T_CMP)
            g = m["diag"]
            # 유형별은 세계 메타의 마지막 hunt_stats(240초)만 있다 — 230초 줄의 합과 같은 비율로 본다(유형 칸은 참고)
            h = m["hunt"]
            out.setdefault((int(um["seed"]), um["region"]), []).append(dict(
                n=r["n"], alive=r["alive"], caught=r["caught"], starved=r["starved"], starts=r["hunt_starts"], ends=r["hunt_ends"],
                success=r["hunt_success"], outside=0, ch_e=h["chaser_ends"], ch_s=h["chaser_success"], st_e=h["stalker_ends"],
                st_s=h["stalker_success"], shelter=r["shelter_steps"], live=r["live_steps"], ring2=g["catch_ring"][0], ring4=g["catch_ring"][1],
                cover=g["catch_cover"], outside_end=h["outside"],
                **({k: r[c] for k, c in zip(PACK_KEYS, ("pack_wolf_steps", "pack_lead", "pack_help", "pack_wait", "pack_door", "pack_catches",
                                                        "pack_coop"))} if "pack_help" in r else {})))
    return out


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def has_pack(maps, u, py) -> bool:
    return all(set(PACK_KEYS) <= set(u[m]) and all(set(PACK_KEYS) <= set(p) for p in py[m]) for m in maps)


def summary(maps, u, py):
    """지도 묶음 → (언리얼 합, 파이썬 반복별 합 목록). 늑대 무리 칸은 양쪽 모두 있을 때만 더한다."""
    keys = KEYS + (PACK_KEYS if has_pack(maps, u, py) else ())
    U = {k: sum(u[m][k] for m in maps) for k in keys}
    reps = min(len(py[m]) for m in maps)
    P = [{k: sum(py[m][j][k] for m in maps) for k in keys} for j in range(reps)]
    for j in range(reps):
        P[j]["outside"] = sum(py[m][j]["outside_end"] for m in maps)
    return U, P


def stat(vals):
    n = len(vals)
    mu = sum(vals) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / (n - 1)) if n > 1 else float("nan")
    return mu, sd, min(vals), max(vals)


METRICS = (
    ("산 %", lambda d: pct(d["alive"], d["n"]), 1),
    ("잡힘 %", lambda d: pct(d["caught"], d["n"]), 2),
    ("굶음 %", lambda d: pct(d["starved"], d["n"]), 2),
    ("사냥 시작", lambda d: d["starts"], 1),
    ("끝난 사냥", lambda d: d["ends"], 1),
    ("성공", lambda d: d["success"], 1),
    ("사냥 성공률 %", lambda d: pct(d["success"], d["ends"]), 1),
    ("은신처 안 사슴·스텝 %", lambda d: pct(d["shelter"], d["live"]), 1),
    ("둘레 밖 2 m 안 잡힘", lambda d: d["ring2"], 1),
    ("둘레 밖 4 m 안 잡힘", lambda d: d["ring4"], 1),
    ("은신처 안 잡힘", lambda d: d["cover"], 1),
)
PACK_METRICS = (
    ("늑대·스텝 가운데 앞장 %", lambda d: pct(d["pk_lead"], d["pk_steps"]), 1),
    ("돕기 %", lambda d: pct(d["pk_help"], d["pk_steps"]), 1),
    ("은신처 문 %", lambda d: pct(d["pk_door"], d["pk_steps"]), 2),
    ("늑대 포획", lambda d: d["pk_catch"], 1),
    ("협동 포획", lambda d: d["pk_coop"], 1),
)


def table(title, maps, u, py):
    U, P = summary(maps, u, py)
    print(f"\n### {title} (지도 {len(maps)}장, 파이썬 반복 {len(P)})\n")
    print("| 칸 | 언리얼 | 파이썬 평균 [최소..최대] | z |")
    print("|---|---|---|---|")
    for name, f, nd in METRICS + (PACK_METRICS if "pk_steps" in U else ()):
        uv = f(U)
        mu, sd, lo, hi = stat([f(p) for p in P])
        z = (uv - mu) / sd if sd and sd > 0 and math.isfinite(sd) else float("nan")
        zs = f"{z:+.1f}" if math.isfinite(z) else "—"
        print(f"| {name} | {uv:.{nd}f} | {mu:.{nd}f} [{lo:.{nd}f}..{hi:.{nd}f}] | {zs} |")
    print(f"| 사냥 밖 포획 (언리얼 230초 · 파이썬 240초) | {U['outside']} | {stat([p['outside'] for p in P])[0]:.1f} | — |")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--unreal-dir", type=Path, required=True)
    ap.add_argument("--python", nargs="+", required=True)
    ap.add_argument("--independent", action="store_true", help="독립 지도 비교 (모듈 docstring)")
    a = ap.parse_args(argv)
    u = parse_unreal(a.unreal_dir)
    if a.independent:
        py = parse_python(a.python, block=len(u))
        uk = sorted(u)
        u = {(j, ""): u[k] for j, k in enumerate(uk)}
        table("독립 지도 모두", sorted(u), u, py)
        return
    py = parse_python(a.python)
    maps = sorted(set(u) & set(py))
    if not maps:
        raise SystemExit("언리얼과 파이썬에 같은 지도가 없다")
    table("지도 모두", maps, u, py)
    table("숲(Forest)만", [m for m in maps if m[1] == "Forest"], u, py)
    print("\n### 지도마다 (230초)\n")
    print("| 지도 | 언리얼 산·잡힘·굶음 | 파이썬 잡힘 평균 [범위] | 언리얼 사냥 시작·끝·성공 | 파이썬 성공/끝 평균 | 언리얼 은신처 안 % | 파이썬 은신처 안 % [범위] |")
    print("|---|---|---|---|---|---|---|")
    for m in maps:
        d, ps = u[m], py[m]
        c = [p["caught"] for p in ps]
        sh = [pct(p["shelter"], p["live"]) for p in ps]
        print(f"| {m[0]} {m[1]} | {d['alive']}·{d['caught']}·{d['starved']} | {sum(c) / len(c):.1f} [{min(c)}..{max(c)}] | "
              f"{d['starts']}·{d['ends']}·{d['success']} | {sum(p['success'] for p in ps) / len(ps):.1f}/{sum(p['ends'] for p in ps) / len(ps):.1f} | "
              f"{pct(d['shelter'], d['live']):.1f} | {sum(sh) / len(sh):.1f} [{min(sh):.1f}..{max(sh):.1f}] |")


if __name__ == "__main__":
    main()
