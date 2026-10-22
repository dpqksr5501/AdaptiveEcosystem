"""독립 확인(10-18): 날씨가 바꾼 잡힘 수 — 언리얼 (날씨 판 − 끈 판) 대 파이썬 짝 (wild3 거울 − 나무 거울, 같은 시드·같은 지도), 세션 9개 (verify/README.md 4절).
herbivore_rl/ 에서

    python results/v3/wild3/verify/effect_catches.py          # → effect_catches.md (표준 출력에도)

언리얼 날씨 판: ../unreal_logs (20000~20002) + unreal_logs (20003~20008). 끈 판: ../unreal_logs_weather_off (20000~20002) + unreal_logs_weather_off
(20003~20005) + ../../wild2/trees/unreal_logs_s20006-20008 (날씨 코드 전 나무 판 — 지금 코드의 끈 판과 기록 줄이 같다: 20000 에서 322 줄 모두 같음).
파이썬: runs/ 의 짝 판(이 폴더 README '다시 만들기'). z = (언리얼 차이 − 파이썬 짝 차이 평균 합) ÷ √(지도마다 파이썬 짝 차이 분산의 합).
잡힘 수는 230초 기록 줄(compare_unreal_wild2.parse_unreal)이다.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
W3 = HERE.parent
sys.path.insert(0, str(W3.parent / "wild2"))

import compare_unreal_wild2 as cu  # noqa: E402

SESSIONS = range(20000, 20009)
REGIONS = (("숲 (비)", "Forest"), ("고지 (눈)", "Highland"), ("메마른 땅 (맑음)", "Barren"))


def unreal(folders) -> dict:
    out: dict = {}
    for f in folders:
        out.update(cu.parse_unreal(Path(f)))
    return out


def python(files) -> dict:
    out: dict = {}
    for f in files:
        for k, v in cu.parse_python([str(f)]).items():
            out.setdefault(k, []).extend(v)
    return out


def main() -> None:
    on = unreal([W3 / "unreal_logs", HERE / "unreal_logs"])
    off = unreal([W3 / "unreal_logs_weather_off", HERE / "unreal_logs_weather_off", W3.parent / "wild2" / "trees" / "unreal_logs_s20006-20008"])
    pw = python([W3 / "runs" / "wild3_240.json"] + sorted((HERE / "runs").glob("wild3_240_s*.json")))
    pt = python([W3 / "runs" / "trees_240.json"] + sorted((HERE / "runs").glob("trees_240_s*.json")))
    lines = ["# 날씨가 바꾼 잡힘 수 — 언리얼 대 파이썬 짝 (자동 생성: effect_catches.py)", "",
             "언리얼 한 판씩(날씨 판 − 끈 판), 파이썬 지도마다 짝 반복 10 의 차이 평균. 사슴 128 마리 무대, 240초(230초 줄).", "",
             "| 지역 | 세션 | 언리얼 날씨 · 끔 → 차이 | 파이썬 날씨 · 끔 평균 → 짝 차이 평균 (지도마다 짝 차이 표준편차) |", "|---|---|---|---|"]
    summary = []
    for title, reg in REGIONS:
        du = mu = var = 0.0
        uon = uoff = pon = poff = 0.0
        for s in SESSIONS:
            k = (s, reg)
            a = np.array([r["caught"] for r in pw[k]], dtype=float)
            b = np.array([r["caught"] for r in pt[k]], dtype=float)
            d = a - b
            sd = float(d.std(ddof=1))
            lines.append(f"| {title} | {s} | {on[k]['caught']} · {off[k]['caught']} → {on[k]['caught'] - off[k]['caught']:+d} | "
                         f"{a.mean():.1f} · {b.mean():.1f} → {d.mean():+.1f} ({sd:.2f}) |")
            du += on[k]["caught"] - off[k]["caught"]
            mu += float(d.mean())
            var += sd * sd
            uon += on[k]["caught"]
            uoff += off[k]["caught"]
            pon += float(a.mean())
            poff += float(b.mean())
        sd = math.sqrt(var)
        z = (du - mu) / sd if sd > 0 else float("nan")
        summary.append(f"| {title} | {uon:.0f} · {uoff:.0f} → {du:+.0f} | {pon:.1f} · {poff:.1f} → {mu:+.1f} ± {sd:.1f} | "
                       + (f"{z:+.1f}" if math.isfinite(z) else "— (둘 다 0)") + " |")
    lines += ["", "## 세션 9개 합", "", "| 지역 | 언리얼 날씨 · 끔 → 차이 | 파이썬 날씨 · 끔 → 짝 차이 ± 표준편차 | z |", "|---|---|---|---|"] + summary
    text = "\n".join(lines) + "\n"
    (HERE / "effect_catches.md").write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
