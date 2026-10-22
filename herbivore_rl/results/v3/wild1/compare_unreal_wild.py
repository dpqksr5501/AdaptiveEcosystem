"""야생 1단계 규칙 수치를 언리얼 기록과 파이썬 거울(run_mirror.py --diag)에서 나란히 본다 (10-16, 사람 결정 10-15 (7) 이식 확인).

    # herbivore_rl/ 에서
    python results/v3/wild1/compare_unreal_wild.py --unreal-dir results/v3/wild1/unreal_logs \
        --python results/v3/wild1/runs/d128_wild1.json results/v3/wild1/runs/d64_wild1.json

산·잡힘·굶음 표는 results/v3/mirror/compare_unreal.py 가 낸다. 이 스크립트는 그 옆에 규칙 자체가 같은 정도로 도는지를 본다.
언리얼: 10초 기록의 넷째 줄 '[EcoV3I] <지역> 야생 | ...'(비축·포만)과 셋째 줄 '[EcoV3I] <지역> 경계 거리 | ...'(도주 반사), 첫 줄의 '구간 사용'
(행동별 개체·스텝)을 구간마다 더한다. 기록 줄은 230초까지라 언리얼 합은 0~230초, 파이썬 진단(meta['diag'])은 0~240초 합이다.
지역(= 파이썬 세계) 하나가 표본 하나다. 칸마다 지역 평균과 [최소..최대].
  약함 %     = 약한(배 10% 밑, 비축으로 사는) 개체·스텝 ÷ 산 개체·스텝 (파이썬 wild.weak_frac)
  배부름·먹기 % = 늑대·스텝 가운데 배불러 쉰·먹는 몫 (wild.sated_frac·eating_frac). 언리얼은 구간 % × 구간 늑대·스텝을 더한다(구간 % 는 정수 반올림)
  경계·도주·웅크림 % = 산 사슴·스텝 가운데 도주 반사가 덮은 몫 (wild.mode_alert/panic/shelter_frac)
  도주 시작 = 지역 하나의 도주(뛰기) 시작 수, 은신처에서 끝 % = 끝난 도주 가운데 은신처에서 끝난 몫 (wild.panic_starts·panic_ends·panic_end_shelter)
  도망·숨기 % = 실행한 행동(덮기 뒤) 가운데 FLEE·HIDE 몫 (diag.beh_steps, 언리얼 '구간 사용')
  비축 끝 % = 마지막 시각 산 사슴 비축 평균 (wild.reserve_mean, 언리얼 '지금 비축 평균' 230초 줄)
z 줄 = (언리얼 지역 평균 − 파이썬 지역 평균) ÷ (파이썬 지역 표준편차 ÷ √언리얼 지역 수) — |z| < 2 면 언리얼 지역 수만큼 뽑을 때 흔한 차이다.
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import re
from collections import defaultdict
from pathlib import Path

NAME = re.compile(r'd(\d+)_s(\d+)_k(\d)(?:_e(\d+))?\.log$')
WILD = re.compile(r'\[EcoV3I\] (\S+) 야생 \| ([\d.]+)초 \| 지방 비축: .*?약한 개체·스텝 (\d+)/(\d+) .*?지금 비축 평균 (\d+)% .*?'
                  r'늑대 포만\(\d+ 스텝\): 구간 늑대·스텝 (\d+) 중 배불러 쉼 (\d+)% · 먹는 중 (\d+)%')
KEEP = re.compile(r'\[EcoV3I\] (\S+) 경계 거리 \| ([\d.]+)초 \| .*?도망 시작 (\d+) .*?덮기 개체·스텝 경계 (\d+) 도망 (\d+) 웅크림 (\d+) \(두뇌 (\d+)\) '
                  r'\| 끝난 도망 (\d+) \(은신처에서 (\d+)\)')
USED = re.compile(r'\[EcoV3I\] (\S+) \| ([\d.]+)초 .*?구간 사용\(개체·스텝\): 먹기 (\d+) 도망 (\d+) 숨기 (\d+) 얼기 (\d+) 잠 (\d+)')
KEYS = ("weak", "sated", "eating", "alert", "panic", "shelter", "panic_starts", "end_shelter", "flee", "hide", "reserve_end")


def parse_unreal(path) -> dict[str, dict]:
    """기록 하나 → 지역 → 규칙 수치(0~230초 합)."""
    acc: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for line in io.open(path, "rb").read().decode("utf-8", "replace").splitlines():
        if (m := WILD.search(line)):
            a = acc[m.group(1)]
            a["weak_n"] += int(m.group(3)); a["live_n"] += int(m.group(4))
            a["reserve_end"] = float(m.group(5)) / 100.0; a["wolf_n"] += int(m.group(6))
            a["sated_n"] += int(m.group(7)) / 100.0 * int(m.group(6)); a["eat_n"] += int(m.group(8)) / 100.0 * int(m.group(6))
        elif (m := KEEP.search(line)):
            a = acc[m.group(1)]
            a["panic_starts"] += int(m.group(3))
            for k, g in (("alert_n", 4), ("panic_n", 5), ("shelter_n", 6), ("brain_n", 7), ("ends", 8), ("ends_shelter", 9)):
                a[k] += int(m.group(g))
        elif (m := USED.search(line)):
            a = acc[m.group(1)]
            v = [int(m.group(g)) for g in range(3, 8)]
            a["beh_n"] += sum(v); a["flee_n"] += v[1]; a["hide_n"] += v[2]
    out = {}
    for reg, a in acc.items():
        modes = a["alert_n"] + a["panic_n"] + a["shelter_n"] + a["brain_n"]
        out[reg] = dict(weak=a["weak_n"] / max(a["live_n"], 1), sated=a["sated_n"] / max(a["wolf_n"], 1), eating=a["eat_n"] / max(a["wolf_n"], 1),
                        alert=a["alert_n"] / max(modes, 1), panic=a["panic_n"] / max(modes, 1), shelter=a["shelter_n"] / max(modes, 1),
                        panic_starts=a["panic_starts"], end_shelter=a["ends_shelter"] / max(a["ends"], 1),
                        flee=a["flee_n"] / max(a["beh_n"], 1), hide=a["hide_n"] / max(a["beh_n"], 1), reserve_end=a.get("reserve_end", float("nan")))
    return out


def load_unreal(unreal_dir) -> dict[int, list[dict]]:
    out: dict[int, list] = defaultdict(list)
    for p in sorted(glob.glob(str(Path(unreal_dir) / "**" / "*.log"), recursive=True)):
        m = NAME.search(Path(p).name)
        if m and int(m.group(3)) == 0 and not m.group(4):
            out[int(m.group(1))].extend(parse_unreal(p).values())
    return dict(out)


def load_python(paths) -> dict[int, list[dict]]:
    out: dict[int, list] = defaultdict(list)
    for p in paths:
        res = json.loads(Path(p).read_text(encoding="utf-8"))
        for wd in res["worlds"]:
            d = wd["meta"].get("diag")
            if not d or "wild" not in d:
                continue
            w, beh = d["wild"], d["beh_steps"]
            tot = max(sum(beh), 1)
            out[int(res["meta"]["deer"])].append(dict(
                weak=w["weak_frac"], sated=w["sated_frac"], eating=w["eating_frac"], alert=w["mode_alert_frac"], panic=w["mode_panic_frac"],
                shelter=w["mode_shelter_frac"], panic_starts=w["panic_starts"], end_shelter=w["panic_end_shelter"] / max(w["panic_ends"], 1),
                flee=beh[1] / tot, hide=beh[2] / tot, reserve_end=w["reserve_mean"]))
    return dict(out)


def cell(rows, key) -> str:
    v = [r[key] for r in rows]
    if not v:
        return "—"
    m = sum(v) / len(v)
    if key == "panic_starts":
        return f"{m:.0f} [{min(v):.0f}..{max(v):.0f}]"
    return f"{100 * m:.1f} [{100 * min(v):.0f}..{100 * max(v):.0f}]"


def z_cell(u, p, key) -> str:
    """z = (언리얼 지역 평균 − 파이썬 지역 평균) ÷ (파이썬 지역 표준편차 ÷ √언리얼 지역 수). |z| < 2 면 표본 흔들림 안."""
    uv, pv = [r[key] for r in u], [r[key] for r in p]
    if len(uv) < 1 or len(pv) < 2:
        return "—"
    pm = sum(pv) / len(pv)
    sd = (sum((x - pm) ** 2 for x in pv) / (len(pv) - 1)) ** 0.5
    return f"{(sum(uv) / len(uv) - pm) / (sd / len(uv) ** 0.5):+.1f}" if sd > 0 else "—"


def table(unreal, python) -> str:
    head = ("약함 %", "배부름 %", "먹기 %", "경계 %", "도주 %", "웅크림 %", "도주 시작(지역)", "은신처에서 끝 %", "도망 행동 %", "숨기 행동 %", "비축 끝 %")
    lines = ["| 사슴/지역 | 쪽 (지역 수) | " + " | ".join(head) + " |", "|---|---|" + "---|" * len(head)]
    for deer in sorted(set(unreal) | set(python), reverse=True):
        for side, rows in (("언리얼", unreal.get(deer, [])), ("파이썬", python.get(deer, []))):
            lines.append(f"| {deer} | {side} ({len(rows)}) | " + " | ".join(cell(rows, k) for k in KEYS) + " |")
        u, p = unreal.get(deer, []), python.get(deer, [])
        lines.append(f"| {deer} | z | " + " | ".join(z_cell(u, p, k) for k in KEYS) + " |")
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--unreal-dir", required=True)
    ap.add_argument("--python", nargs="+", required=True, help="run_mirror.py --diag JSON (야생 설정)")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    out = table(load_unreal(a.unreal_dir), load_python(sorted({f for p in a.python for f in glob.glob(p)})))
    print(out)
    if a.out:
        a.out.write_text(out + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
