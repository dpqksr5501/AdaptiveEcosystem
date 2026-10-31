"""팀 날씨·나무 시험 레벨(LV_SHC_RegionalWeatherTest, 팀 PR ff8c8f4)의 나무를 우리 동물 무대 원판으로 옮긴 장애물 지도 (10-17, 측정 전용).

그 레벨에는 통합 조정자·은신처가 없어서 우리 통합 v3 모드가 돌지 않는다(results/v3/wild2/level_shc/README.md). 그 레벨은 팀 통합 레벨
LV_Ecosystem_IntegrationTest 의 사본(같은 지형·지역 상자·먹이 자리 = 같은 무대 자리)이므로, 레벨 읽기 결과(편집기 파이썬 scan JSON 의 나무 자리·
충돌 상자)를 통합 레벨 무대 좌표에 겹쳐 우리 레벨 읽기 규칙(C++ EcoPolicyV3IntegratedSubsystem::ScanStageObstacles)을 그대로 건다. herbivore_rl/ 에서

    python results/v3/wild2/shc/make_shc_obstacle_maps.py --sessions 20000-20002

규칙(C++ 와 같은 순서): 정적 메시 인스턴스마다 충돌 상자 중심(ObstacleCollisionBox — scan 의 reader_disc.center_cm)이 무대 상자 [0, 한 변]² 밖이면 뺀다
(중심이 무대 밖) → 충돌 안 함(쿼리 충돌 ∧ WorldStatic 막음이 아님) → 가로 반지름(reader_disc.r_cm) < 25 cm → 높이 < 50 cm → 중심이 은신처 원 안 →
남김. 512 개를 넘으면 큰 것부터, 끝에 (x, y, r) 순으로 늘어놓는다. 무대 원점·한 변·은신처 원은 통합 레벨 내보내기 JSON(-EcoV3ObstacleExport)을 읽는다.

출력: 세션마다 <out>/s<세션 시드>.json — make_obstacle_maps.py·언리얼 내보내기와 같은 꼴 {session_seed, units, source, regions: [{region, size, origin_cm,
discs: [[x, y, r], …], covers, dropped: [...]}]}. 언리얼은 -EcoV3ObstacleImport=<파일>, 파이썬 거울은 run_mirror.py --unreal-obstacles <out> 로 읽는다
(둘 다 region·discs 만 읽는다 — dropped 는 사람이 보는 기록). 세션 시드는 무대 자리를 바꾸지 않는다(같은 원판이 세션마다 들어간다).
요약 <out>/../trees_in_stage_frame.json: 나무마다 무대마다 무대 단위 자리와 무대 상자까지 거리(중심·원판 가장자리·몸 반지름 0.15 단위를 더한 가장자리).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve()
WILD2 = HERE.parents[1]
SCAN = WILD2 / "level_shc" / "scan_LV_SHC_RegionalWeatherTest.json"
EXPORT = WILD2 / "level_shc" / "v3_export_integration_s20000.json"
OUT = HERE.parent / "obstacle_maps"
UNIT_CM = 200.0                 # EcoRepertoireV3::kUnitCm
MIN_R_CM = 25.0                 # FEcoV3ObstacleScan::kMinRadiusCm
MIN_H_CM = 50.0                 # FEcoV3ObstacleScan::kMinHeightCm
MAX_DISCS = 512                 # FEcoV3ObstacleScan::kMaxDiscs
BODY_R = 0.15                   # FObstacleConfig::BodyR (단위)
UNREAL_SEED_RANGE = (20000, 20019)


def parse_sessions(s: str) -> list[int]:
    out = []
    for part in s.split(","):
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    for u in out:
        if not UNREAL_SEED_RANGE[0] <= u <= UNREAL_SEED_RANGE[1]:
            raise ValueError(f"언리얼 세션 시드 {u} 가 {UNREAL_SEED_RANGE} 밖이다")
    return out


def instances(scan: dict):
    """scan JSON 의 정적 메시 인스턴스 (이름표, 메시, 충돌함, reader_disc, 자리)."""
    for a in scan["actors"]:
        for c in a.get("static_meshes", []) or []:
            for inst in c.get("instances", []) or []:
                rd = inst.get("reader_disc")
                if rd is None:
                    continue
                yield dict(label=a["label"], mesh=c["mesh"].rsplit(".", 1)[-1], collides=bool(c["collides"]), disc=rd, t=inst["t"])


def box_gap(x: float, y: float, size: float) -> float:
    """무대 상자 [0, size]² 까지의 거리 (안이면 0)."""
    dx = max(0.0 - x, 0.0, x - size)
    dy = max(0.0 - y, 0.0, y - size)
    return math.hypot(dx, dy)


def stage_discs(scan: dict, region: dict) -> tuple[list, list, list]:
    """한 무대: (남긴 원판 [[x, y, r]], 뺀 것 기록, 나무마다 무대 좌표 기록). C++ ScanStageObstacles 와 같은 순서."""
    ox, oy = float(region["origin_cm"][0]), float(region["origin_cm"][1])
    size_u = float(region["size"])
    size_cm = size_u * UNIT_CM
    covers = [tuple(map(float, c)) for c in region["covers"]]
    kept, dropped, frame = [], [], []
    for it in instances(scan):
        cx, cy = float(it["disc"]["center_cm"][0]), float(it["disc"]["center_cm"][1])
        r_cm, h_cm = float(it["disc"]["r_cm"]), float(it["disc"]["height_cm"])
        X, Y = cx - ox, cy - oy
        xu, yu, ru = X / UNIT_CM, Y / UNIT_CM, r_cm / UNIT_CM
        gap_c = box_gap(xu, yu, size_u)
        frame.append(dict(label=it["label"], mesh=it["mesh"], x=round(xu, 4), y=round(yu, 4), r=round(ru, 4),
                          gap_center_m=round(gap_c * 2.0, 2), gap_disc_m=round((gap_c - ru) * 2.0, 2),
                          gap_body_m=round((gap_c - ru - BODY_R) * 2.0, 2)))
        if X < 0.0 or Y < 0.0 or X > size_cm or Y > size_cm:
            dropped.append(dict(label=it["label"], why="중심이 무대 밖", x=round(xu, 4), y=round(yu, 4), r=round(ru, 4)))
            continue
        if not it["collides"]:
            dropped.append(dict(label=it["label"], why="충돌 없음"))
            continue
        if r_cm < MIN_R_CM:
            dropped.append(dict(label=it["label"], why="작음"))
            continue
        if h_cm < MIN_H_CM:
            dropped.append(dict(label=it["label"], why="낮음"))
            continue
        if any(cr > 0.0 and (xu - cxv) ** 2 + (yu - cyv) ** 2 <= cr * cr for cxv, cyv, cr in covers):
            dropped.append(dict(label=it["label"], why="은신처 원 안"))
            continue
        kept.append((xu, yu, ru))
    if len(kept) > MAX_DISCS:
        kept.sort(key=lambda d: (-d[2], d[0], d[1]))
        kept = kept[:MAX_DISCS]
    kept.sort(key=lambda d: (d[0], d[1], d[2]))
    return [list(d) for d in kept], dropped, frame


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sessions", default="20000-20002")
    ap.add_argument("--scan", type=Path, default=SCAN)
    ap.add_argument("--export", type=Path, default=EXPORT, help="통합 레벨 내보내기 JSON (무대 원점·한 변·은신처 원)")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    scan = json.loads(a.scan.read_text(encoding="utf-8"))
    exp = json.loads(a.export.read_text(encoding="utf-8"))
    regions = sorted(exp["regions"], key=lambda r: r["region"])
    per_region, frames = [], {}
    for r in regions:
        discs, dropped, frame = stage_discs(scan, r)
        per_region.append(dict(region=r["region"], size=r["size"], origin_cm=r["origin_cm"], discs=discs, covers=r["covers"], dropped=dropped))
        frames[r["region"]] = frame
    a.out.mkdir(parents=True, exist_ok=True)
    for u in parse_sessions(a.sessions):
        doc = dict(session_seed=u, units="stage units, 1 unit = 200 cm, x·y from stage origin",
                   source=f"{scan['map']} 나무를 {a.export.name} 무대에 겹침 (ScanStageObstacles 규칙, make_shc_obstacle_maps.py)",
                   regions=per_region)
        (a.out / f"s{u}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    summ = dict(scan=a.scan.name, export=a.export.name, body_r_units=BODY_R,
                kept={r["region"]: len(r["discs"]) for r in per_region}, trees=frames)
    (a.out.parent / "trees_in_stage_frame.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in per_region:
        near = min(frames[r["region"]], key=lambda f: f["gap_center_m"])
        print(f"{r['region']}: 원판 {len(r['discs'])} · 뺌 {len(r['dropped'])} | 가장 가까운 {near['label']} 중심 {near['gap_center_m']} m · "
              f"원판 가장자리 {near['gap_disc_m']} m · 몸 더한 가장자리 {near['gap_body_m']} m 밖")


if __name__ == "__main__":
    main()
