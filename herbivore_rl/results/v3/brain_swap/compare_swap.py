"""두뇌 바꾸기 시연 (10-18, 측정 전용 — 실행 중 가중치 로더 `AI/Policy/EcoV3Brain.h`).

언리얼 통합 레벨 헤드리스 판 두 개를 세션마다 견준다 (기본값 = 레벨 나무 + 날씨, 사슴 128/지역, 241초):
  base  처음부터 끝까지 내장 두뇌 R1b (통합 모드는 얼기를 세계가 막아 R1b-F)
  swap  같은 세션, 120초(전역 스텝 900)의 결정 스텝 경계에서 R4 s0 파일 두뇌로 바꿈
        (-EcoV3BrainSwapAt=120 -EcoV3BrainSwapTo=v3_r4_g995_s0_20m — Play 를 다시 시작하지 않는다)

본다:
  1. 바꾸기 앞(0~120초)의 기록 줄이 두 판에서 모두 같은가 (시각·CPU 칸과 설정 줄 '사슴 두뇌:'·명령줄 빼고) — 바꾸기가 그 앞을 건드리지 않는다.
  2. 바꾸기 줄 '[EcoV3I] 두뇌 바꿈 |' 하나, 시각 120.0초·전역 스텝 900, 내장 id → R4 id.
  3. 10초 아홉째 줄 '[EcoV3I] <지역> 두뇌 |' 의 두뇌 id 와 행동 몫: 구간 두뇌 스텝(도주 반사 밖)과 그중 늑대를 앎(관측 pred_count > 0)의 먹기·도망·숨기.
     창 앞 (0, 120]초·뒤 (120, 240]초, 세 지역 합과 지역마다. 같은 창의 base 와 swap 을 견주면 시간(낮밤·늑대 배부름·산 사슴 수) 차이가 빠진다.
  4. 첫 줄의 구간 포획·굶음 합, 창 끝 산 사슴.

herbivore_rl/ 에서
    python results/v3/brain_swap/compare_swap.py --logs <전체 기록 폴더> --sessions 20000-20002
    (전체 기록 이름 s<세션>_base_full.log·s<세션>_swap_full.log — 고른 줄을 results/v3/brain_swap/unreal_logs/ 에 쓴다)
출력: stdout(표), --out (기본 results/v3/brain_swap/compare_swap.json).
"""

from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SWAP_T = 120.0
END_T = 240.0
BEH = ("먹기", "도망", "숨기", "얼기", "잠")

STAMP = re.compile(r"^\[[^\]]*\]\[\s*\d+\]")
CPU = re.compile(r"결정 스텝 CPU\(모든 지역\) 평균 [\d.]+ ms/스텝, 최대 [\d.]+ ms/프레임")
MAIN = re.compile(r"\[EcoV3I\] (\S+) \| ([\d.]+)초 (?:낮|밤) .*?사슴 산 (\d+)/(\d+).*?포획 (\d+) \(누적 (\d+)\) 굶음 (\d+) \(누적 (\d+)\)")
BRAIN = re.compile(r"\[EcoV3I\] (\S+) 두뇌 \| ([\d.]+)초 \| 두뇌 (\S+)(.*?) \| 구간 두뇌 스텝\(도주 반사 밖\) (\d+): (.*?) \| 그중 늑대를 앎 (\d+): (.*?) \| "
                   r"반사 스텝 (\d+) \(늑대를 앎 (\d+)\)")
SHARE = re.compile(r"(먹기|도망|숨기|얼기|잠) (\d+) \(")
SWAP = re.compile(r"\[EcoV3I\] 두뇌 바꿈 \| ([\d.]+)초 \(전역 스텝 (\d+)\) \| (\S+) → (\S+)")
START = re.compile(r"\[EcoV3I\] 두뇌 시작 \| ([\d.]+)초 \(전역 스텝 (\d+)\) \| (\S+)")


def sessions(text: str) -> list[int]:
    lo, _, hi = text.partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


def norm(line: str) -> str:
    return CPU.sub("결정 스텝 CPU(…)", STAMP.sub("", line)).strip()


def counts(text: str) -> list[int]:
    d = dict((k, int(v)) for k, v in SHARE.findall(text))
    return [d.get(b, 0) for b in BEH]


def read(path: Path) -> dict:
    raw = io.open(path, "rb").read().decode("utf-8", "replace").splitlines()
    keep, eco = [], []
    for line in raw:
        if "LogInit: Command Line:" in line:
            keep.append(re.sub(r"\s+-abslog=\S+", "", line[line.index("LogInit:"):]))
        elif "[EcoV3I]" in line or "[EcoV3Brain]" in line:
            if MAIN.search(line) or BRAIN.search(line) or SWAP.search(line) or START.search(line) or "Warning:" in line or "Error:" in line \
                    or not re.search(r"\[EcoV3I\] \S+ \S+ \| [\d.]+초", line):
                keep.append(line)
            eco.append(norm(line))
    main, brain = [], []
    swaps, starts = [], []
    for e in eco:
        if m := MAIN.search(e):
            main.append(dict(region=m[1], t=float(m[2]), alive=int(m[3]), adopted=int(m[4]), caught=int(m[5]), caught_cum=int(m[6]),
                             starved=int(m[7]), starved_cum=int(m[8])))
        elif m := BRAIN.search(e):
            brain.append(dict(region=m[1], t=float(m[2]), id=m[3], mixed=bool(m[4].strip()), steps=counts(m[6]), n=int(m[5]),
                              know=counts(m[8]), n_know=int(m[7]), reflex=int(m[9]), reflex_know=int(m[10])))
        elif m := SWAP.search(e):
            swaps.append(dict(t=float(m[1]), step=int(m[2]), src=m[3], dst=m[4]))
        elif m := START.search(e):
            starts.append(dict(t=float(m[1]), step=int(m[2]), id=m[3]))
    warn = sum(1 for k in keep if "Warning:" in k or "Error:" in k)
    return dict(keep=keep, eco=eco, main=main, brain=brain, swaps=swaps, starts=starts, warnings=warn)


def window(rows: list, lo: float, hi: float, region: str | None = None) -> list:
    return [r for r in rows if lo < r["t"] <= hi + 1e-9 and (region is None or r["region"] == region)]


def summary(log: dict, lo: float, hi: float, region: str | None = None) -> dict:
    br = window(log["brain"], lo, hi, region)
    mn = window(log["main"], lo, hi, region)
    steps = [sum(r["steps"][b] for r in br) for b in range(5)]
    know = [sum(r["know"][b] for r in br) for b in range(5)]
    n, nk = sum(steps), sum(know)
    pct = lambda x, t: round(100.0 * x / t, 2) if t else 0.0  # noqa: E731
    last = {}
    for r in mn:
        last[r["region"]] = r["alive"]
    return dict(ids=sorted({r["id"] for r in br}), mixed=sum(r["mixed"] for r in br), intervals=len(br),
                brain_steps=n, share=[pct(x, n) for x in steps], know_steps=nk, know_share=[pct(x, nk) for x in know],
                know_counts=know, reflex=sum(r["reflex"] for r in br), reflex_know=sum(r["reflex_know"] for r in br),
                caught=sum(r["caught"] for r in mn), starved=sum(r["starved"] for r in mn), alive_end=sum(last.values()))


def prefix_check(base: dict, swap: dict) -> dict:
    """바꾸기 줄 앞의 기록 줄이 두 판에서 같은가 (설정 줄 '사슴 두뇌:' 은 예정 바꾸기 칸이 달라, 저장소 줄 '[EcoV3Brain] 대기' 는 바꾸기 사건이라 뺀다)."""
    skip = lambda e: "[EcoV3I] 사슴 두뇌:" in e or "[EcoV3Brain]" in e  # noqa: E731
    s_eco = [e for e in swap["eco"] if not skip(e)]
    b_eco = [e for e in base["eco"] if not skip(e)]
    cut = next((i for i, e in enumerate(s_eco) if SWAP.search(e)), len(s_eco))
    pre = s_eco[:cut]
    same = sum(1 for a, b in zip(pre, b_eco) if a == b)
    first_diff = next((i for i, (a, b) in enumerate(zip(pre, b_eco)) if a != b), None)
    return dict(lines=len(pre), same=same, first_diff=first_diff, first_diff_line=pre[first_diff][:200] if first_diff is not None else None)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--logs", required=True, help="전체 기록 폴더 (s<세션>_base_full.log·s<세션>_swap_full.log)")
    p.add_argument("--sessions", default="20000")
    p.add_argument("--out", default=str(HERE / "compare_swap.json"))
    p.add_argument("--trim-dir", default=str(HERE / "unreal_logs"))
    args = p.parse_args(argv)

    trim = Path(args.trim_dir)
    trim.mkdir(parents=True, exist_ok=True)
    out = dict(swap_t=SWAP_T, end_t=END_T, behaviors=list(BEH), sessions={})
    tot = {k: {w: dict(know=[0] * 5, steps=[0] * 5, caught=0, starved=0) for w in ("pre", "post")} for k in ("base", "swap")}
    for s in sessions(args.sessions):
        logs = {}
        for k in ("base", "swap"):
            logs[k] = read(Path(args.logs) / f"s{s}_{k}_full.log")
            (trim / f"s{s}_{k}.log").write_text("\n".join(logs[k]["keep"]) + "\n", encoding="utf-8", newline="\n")
        base, swap = logs["base"], logs["swap"]
        regions = sorted({r["region"] for r in base["brain"]})
        res = dict(prefix=prefix_check(base, swap), swaps=swap["swaps"], base_swaps=base["swaps"], starts=dict(base=base["starts"], swap=swap["starts"]),
                   warnings=dict(base=base["warnings"], swap=swap["warnings"]), windows={}, regions={})
        for k in ("base", "swap"):
            for w, (lo, hi) in (("pre", (0.0, SWAP_T)), ("post", (SWAP_T, END_T))):
                sm = summary(logs[k], lo, hi)
                res["windows"][f"{k}_{w}"] = sm
                for b in range(5):
                    tot[k][w]["know"][b] += sm["know_counts"][b]
                tot[k][w]["caught"] += sm["caught"]
                tot[k][w]["starved"] += sm["starved"]
                for rg in regions:
                    res["regions"].setdefault(rg, {})[f"{k}_{w}"] = summary(logs[k], lo, hi, rg)
        out["sessions"][str(s)] = res

        pf = res["prefix"]
        print(f"## 세션 {s}")
        print(f"- 바꾸기 앞 기록 줄 {pf['same']}/{pf['lines']} 같음" + (f" (처음 다른 줄 {pf['first_diff']}: {pf['first_diff_line']})" if pf["first_diff"] is not None else ""))
        for sw in swap["swaps"]:
            print(f"- 바꾸기: {sw['t']:.1f}초 전역 스텝 {sw['step']} | {sw['src']} → {sw['dst']}  (base 판 바꾸기 {len(base['swaps'])})")
        print(f"- 경고·오류 줄: base {base['warnings']} · swap {swap['warnings']}")
        print("| 판·창 | 두뇌 | 두뇌 스텝 | 먹기·도망·숨기 % | 늑대를 앎 스텝 | 늑대를 알 때 먹기·도망·숨기 % | 반사 스텝 | 포획 | 굶음 | 창 끝 산 사슴 |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for key in ("base_pre", "swap_pre", "base_post", "swap_post"):
            sm = res["windows"][key]
            print(f"| {key} | {' '.join(sm['ids'])}{' (구간 중 바꿈)' if sm['mixed'] else ''} | {sm['brain_steps']} | "
                  f"{sm['share'][0]:.1f} · {sm['share'][1]:.1f} · {sm['share'][2]:.1f} | {sm['know_steps']} | "
                  f"{sm['know_share'][0]:.1f} · {sm['know_share'][1]:.1f} · **{sm['know_share'][2]:.1f}** | {sm['reflex']} | {sm['caught']} | {sm['starved']} | {sm['alive_end']} |")
        print("지역마다 늑대를 알 때 숨기 % (base 앞 / swap 앞 / base 뒤 / swap 뒤):")
        for rg in regions:
            r = res["regions"][rg]
            print(f"  {rg}: " + " / ".join(f"{r[k]['know_share'][2]:.1f} ({r[k]['know_steps']})" for k in ("base_pre", "swap_pre", "base_post", "swap_post")))
        print()

    pct = lambda x: round(100.0 * x[2] / sum(x), 2) if sum(x) else 0.0  # noqa: E731
    out["total"] = {f"{k}_{w}": dict(know_steps=sum(tot[k][w]["know"]), know_counts=tot[k][w]["know"], hide_know_pct=pct(tot[k][w]["know"]),
                                     caught=tot[k][w]["caught"], starved=tot[k][w]["starved"])
                    for k in ("base", "swap") for w in ("pre", "post")}
    print("## 세션 합 — 늑대를 알 때 숨기 %")
    for key, v in out["total"].items():
        print(f"- {key}: {v['hide_know_pct']:.2f}% ({v['know_counts'][2]}/{v['know_steps']}) · 포획 {v['caught']} · 굶음 {v['starved']}")
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"\n쓴 파일: {args.out}, 고른 줄 {trim}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
