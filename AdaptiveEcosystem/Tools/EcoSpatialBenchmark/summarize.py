"""Summarize cumulative stages; preserve raw CSV for subsequent methods."""
import argparse
import csv
import statistics
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("csv", type=Path)
parser.add_argument("--out", type=Path)
args = parser.parse_args()
with args.csv.open(encoding="utf-8-sig", newline="") as stream:
    rows = list(csv.DictReader(stream))
names = ["전체 탐색", "동족 격자", "+ 위협 격자", "+ 표적·포획 격자"]
lines = ["100스텝, 10스텝 예열, 동일 시드, 3회 중앙값. 시간은 ms이며 계측 비용을 포함한다.", "",
         "| 배치 | 사슴/늑대 | 누적 단계 | 전체 시간 | 직전 대비 | 기준 대비 | 해당 단계 후보 감소 |",
         "|---|---:|---|---:|---:|---:|---:|"]
for layout in ("spread", "dense"):
    for count in sorted({int(r["deer"]) for r in rows}):
        base = previous = None
        for stage in range(4):
            group = [r for r in rows if r["layout"] == layout and int(r["deer"]) == count and int(r["stage"]) == stage]
            if len(group) != 3:
                raise ValueError(f"Expected 3 trials: {layout}, {count}, {stage}")
            ms = statistics.median(float(r["wall_ms"]) for r in group)
            if base is None:
                base = previous = ms
            reduction = "—"
            if stage:
                key = ("kin", "threat", "wolf")[stage - 1]
                reduction = f"{statistics.median(100 * (1 - int(r[key + '_candidates']) / max(1, int(r[key + '_full']))) for r in group):.2f}%"
            lines.append(f"| {layout} | {count}/{group[0]['wolves']} | {names[stage]} | {ms:.2f} | {ms-previous:+.2f} ({100*(ms/previous-1):+.2f}%) | {100*(ms/base-1):+.2f}% | {reduction} |")
            previous = ms
text = "\n".join(lines) + "\n"
if args.out:
    args.out.write_text(text, encoding="utf-8")
else:
    print(text)
