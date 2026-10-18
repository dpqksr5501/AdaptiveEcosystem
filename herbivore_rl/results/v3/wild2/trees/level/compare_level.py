"""레벨 나무 확인 (10-18, 측정 전용): 통합 레벨에 진짜 액터로 놓은 나무(-run=EcoV3PlaceTrees)로 돈 언리얼 헤드리스 판이 실행 중 나무(10-17
eco.IntegratedV3.StageTrees 1)로 돈 판과 같은 세계인지 본다. 두 판 모두 기본값(나무 + 날씨, 사슴 128, 240초)이고 세션 시드가 같다.

본다:
  1. 원판 내보내기(-EcoV3ObstacleExport JSON): 지역마다 세계 원판(discs) = 배치 표(tree_layout.json) = 앞 판 세계 원판 (모양 + 모든 칸 float.hex),
     레벨 나무 줄기 원판(level_tree_discs) = 표, 시작 자리 계획이 피한 원판(plan_trunk_discs) = 표, 표와 맞춘 수·다른 수, 이동 검사(trunk_probe),
     무대 원점·은신처 원이 앞 판과 같은지.
  2. 기록 줄(trim_unreal_log.py 로 고른 줄): 시각 칸과 결정 스텝 CPU 칸을 빼고 줄마다 같은지. 나무를 놓는 길이 달라 바뀌는 줄
     (설정 '무대 나무:', 시작 '<지역> 장애물 |'·'<지역> 나무 |', 10초 '<지역> 장애물 |' 의 원판 출처 칸, 명령줄·내보내기 경로)은 따로 센다.

herbivore_rl/ 에서
    python results/v3/wild2/trees/level/compare_level.py --sessions 20000-20002
출력: stdout 과 --out (기본 results/v3/wild2/trees/level/compare_level.json).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
LAYOUT = HERE.parent / "tree_layout.json"
OLD = ROOT / "results" / "v3" / "wild3"

STAMP = re.compile(r"^\[[^\]]*\]\[\s*\d+\]")
CPU = re.compile(r"결정 스텝 CPU\(모든 지역\) 평균 [\d.]+ ms/스텝, 최대 [\d.]+ ms/프레임")
TREE_SRC = re.compile(r"\((무대 나무 \d+ \+ 레벨에서 읽음 \d+|레벨 나무 \d+ \+ 그 밖 레벨에서 읽음 \d+|레벨에서 읽음),")


def hexes(a) -> list:
    return [[float(v).hex() for v in row] for row in a]


def same(a, b) -> bool:
    return len(a) == len(b) and hexes(a) == hexes(b)


def sessions(text: str) -> list[int]:
    lo, _, hi = text.partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


def norm(line: str) -> str:
    return CPU.sub("결정 스텝 CPU(…)", STAMP.sub("", line)).strip()


def kind(line: str) -> str:
    """나무를 놓는 길 때문에 달라도 되는 줄의 종류 (아니면 빈 문자열)."""
    if "Command Line:" in line or "장애물 원판 목록을 썼다" in line:
        return "명령줄·내보내기 경로"
    if "[EcoV3I] 무대 나무:" in line:
        return "설정 '무대 나무:'"
    if re.search(r"\[EcoV3I\] \S+ 나무 \|", line):
        return "시작 '<지역> 나무 |'"
    if re.search(r"\[EcoV3I\] \S+ 장애물 \| 원판 \d+ \(반지름", line):
        return "시작 '<지역> 장애물 |'"
    return ""


def compare_logs(old: Path, new: Path) -> dict:
    a = [norm(x) for x in old.read_text(encoding="utf-8").splitlines() if x.strip()]
    b = [norm(x) for x in new.read_text(encoding="utf-8").splitlines() if x.strip()]
    # 바뀌어도 되는 줄은 뺀 뒤 견주고, 10초 장애물 줄은 원판 출처 칸만 같은 꼴로 바꿔 견준다
    keep_a = [TREE_SRC.sub("(원판 출처),", x) for x in a if not kind(x)]
    keep_b = [TREE_SRC.sub("(원판 출처),", x) for x in b if not kind(x)]
    diffs = []
    for i, (x, y) in enumerate(zip(keep_a, keep_b)):
        if x != y:
            diffs.append({"line": i, "old": x[:300], "new": y[:300]})
    skipped = {}
    for x in b:
        k = kind(x)
        if k:
            skipped[k] = skipped.get(k, 0) + 1
    return {
        "old_lines": len(a), "new_lines": len(b), "compared": min(len(keep_a), len(keep_b)),
        "same_count": len(keep_a) == len(keep_b), "different": len(diffs), "first_diffs": diffs[:5], "skipped_new": skipped,
        "warnings_new": sum(1 for x in b if "Warning:" in x or "Error:" in x),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", default="20000-20002")
    ap.add_argument("--new", default=str(HERE), help="unreal_exports/·unreal_logs/ 가 든 폴더 (레벨 나무 판)")
    ap.add_argument("--old", default=str(OLD), help="같은 꼴 폴더 (실행 중 나무 판, 기본 results/v3/wild3)")
    ap.add_argument("--out", default=str(HERE / "compare_level.json"))
    args = ap.parse_args()
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    table = {r["region"]: r["discs"] for r in layout["regions"]}
    new, old = Path(args.new), Path(args.old)
    out = {"layout": f"{layout['version']} {layout['digest']}", "sessions": {}}
    ok_all = True
    for s in sessions(args.sessions):
        eu = json.loads((new / "unreal_exports" / f"s{s}.json").read_text(encoding="utf-8"))
        eo = json.loads((old / "unreal_exports" / f"s{s}.json").read_text(encoding="utf-8"))
        regions = {}
        olds = {r["region"]: r for r in eo["regions"]}
        for r in eu["regions"]:
            name = r["region"]
            o = olds[name]
            t = table.get(name, [])
            row = {
                "discs": len(r["discs"]),
                "discs_eq_table": same(r["discs"], t),
                "discs_eq_old": same(r["discs"], o["discs"]),
                "level_tree_discs_eq_table": same(r.get("level_tree_discs", []), t),
                "plan_trunk_discs_eq_table": same(r.get("plan_trunk_discs", []), t),
                "level_trees_on": r.get("level_trees_on"),
                "runtime_tree_discs": len(r.get("tree_discs", [])),
                "snapped": r.get("level_trees_snapped"), "unmatched": r.get("level_trees_unmatched"),
                "max_snap_cm": r.get("level_tree_max_snap_cm"),
                "origin_eq_old": r["origin_cm"] == o["origin_cm"],
                "covers_eq_old": same(r["covers"], o["covers"]),
                "weather_eq_old": r.get("weather") == o.get("weather"),
                "trunk_probe": r.get("trunk_probe"),
                "counts": r["counts"],
            }
            probe = row["trunk_probe"] or {}
            good = (row["discs_eq_table"] and row["discs_eq_old"] and row["origin_eq_old"] and row["covers_eq_old"] and row["weather_eq_old"]
                    and row["runtime_tree_discs"] == 0)
            if t:
                good = good and row["level_tree_discs_eq_table"] and row["plan_trunk_discs_eq_table"] and row["unmatched"] == 0 \
                    and row["snapped"] == len(t) and probe.get("cross_by_trunk") == len(t) and probe.get("ring_blocked_by_tree") == 0
            row["ok"] = good
            ok_all = ok_all and good
            regions[name] = row
        logs = compare_logs(old / "unreal_logs" / f"d128_s{s}_k0.log", new / "unreal_logs" / f"d128_s{s}_k0.log")
        ok_all = ok_all and logs["different"] == 0 and logs["same_count"] and logs["warnings_new"] == 0
        out["sessions"][str(s)] = {"regions": regions, "logs": logs}
        for name, row in regions.items():
            p = row["trunk_probe"] or {}
            print(f"s{s} {name:9s} 원판 {row['discs']:2d} · 표 {'=' if row['discs_eq_table'] else '≠'} · 앞 판 {'=' if row['discs_eq_old'] else '≠'} · "
                  f"레벨 줄기 {'=' if row['level_tree_discs_eq_table'] else '≠'} 표 · 계획 {'=' if row['plan_trunk_discs_eq_table'] else '≠'} 표 · "
                  f"맞춤 {row['snapped']} 다름 {row['unmatched']} (최대 {row['max_snap_cm']:.2g} cm) · 실행 중 나무 {row['runtime_tree_discs']} · "
                  f"이동 검사 줄기 {p.get('cross_by_trunk')}/{p.get('trees')} 막힘 · 둘레 {p.get('ring_steps')} 걸음 막힘 {p.get('ring_blocked')} (우리 나무 {p.get('ring_blocked_by_tree')}) "
                  f"→ {'OK' if row['ok'] else '확인 필요'}")
        print(f"s{s} 기록 줄: 앞 판 {logs['old_lines']} · 새 판 {logs['new_lines']} · 견준 줄 {logs['compared']} · 다른 줄 {logs['different']} · "
              f"따로 센 줄 {logs['skipped_new']} · 새 판 EcoV3I 경고·오류 {logs['warnings_new']}")
        for d in logs["first_diffs"]:
            print("   앞:", d["old"][:200])
            print("   새:", d["new"][:200])
    out["ok"] = ok_all
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("모두 같음" if ok_all else "다른 것이 있다 — 위 줄을 본다")


if __name__ == "__main__":
    main()
