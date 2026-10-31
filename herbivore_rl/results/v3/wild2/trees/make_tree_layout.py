"""통합 레벨 동물 무대에 놓는 나무 배치 표 (10-17 사용자 '그럼 그냥 우리 쪽 테스트 레벨에 저 사람이 만든 장애물들 적절히 배치해 봐').

팀(avaroki 님) 나무 메시 /Game/SHC/Fab/Realistic_Beech_Tree_3D_Vegetation/Beech_Tree 를 우리 시험 레벨 LV_Ecosystem_IntegrationTest 의 무대(지역마다
먹이 자리 둘레 120 m 상자)에 놓는다. 레벨·콘텐츠는 바꾸지 않는다 — 통합 v3 모드가 실행 중에 이 표대로 나무 액터를 놓고(충돌 없음), 줄기 원판을
v3 세계 장애물에 넣는다(C++ EcoPolicyV3IntegratedSubsystem 'StageTrees'). 파이썬 거울은 같은 표의 원판을 obstacles.fixed 로 쓴다. herbivore_rl/ 에서

    python results/v3/wild2/trees/make_tree_layout.py            # 표·헤더·거울 설정을 다시 쓴다 (같은 규칙·같은 시드면 바이트 단위로 같다)
    python results/v3/wild2/trees/make_tree_layout.py --check    # 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다 (쓰지 않는다)

쓰는 것 (셋 모두 같은 숫자 — 파이썬 repr 표기라 다시 읽으면 같은 float64):
  results/v3/wild2/trees/tree_layout.json                         지역마다 discs [[x, y, r], …] + trees (자리·회전·크기·액터 기준점). 언리얼 내보내기 꼴이라
                                                                  run_mirror.py·stuck_check.py --unreal-obstacles 가 그대로 읽는다(지역마다 원판)
  AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/TreeLayoutV3.h   C++ 헤더 (언리얼은 파일을 읽지 않는다)
  configs/v3_wild2_trees_mirror.yaml                              = v3_wild2_obstacle_mirror.yaml + obstacles.fixed(숲 무대 원판) — 그 파일을 고치면 다시 만든다
  results/v3/wild2/trees/tree_layout.png                          무대 셋 그림 (줄기·잎 넓이·은신처·빈터·지킬 자리)

단위: 무대 단위(1 단위 = 2 m), x·y 는 무대 (0, 0) = x·y 가 가장 작은 모서리에서. 무대 한 변 60 단위(120 m, 통합 기본 eco.IntegratedV3.StageSizeM 120).

규칙 (줄마다 현실 근거 또는 어림):
  수      숲 24 그루 — 실제 온대 성숙림 줄기 단면적 34 m²/ha(ESA Ecological Archives E094-195, 명세 RL_V3_WILD2_SPEC.md 6-3)를 이 나무 밑동(반경 0.81 m,
          단면적 2.06 m²)으로 나누면 1 ha 16.5 그루 → 무대 1.44 ha 에 23.8 → 24 (팀 피드백 FEEDBACK_AVAROKI_1017.md 의 부탁과 같은 수).
          고지 9 그루 — 고지(−5 °C·눈)는 나무 한계선 가까운 성긴 숲으로 보고 숲의 3/8(1 ha 6.3 그루, 단면적 약 13 m²/ha) — 어림.
          메마른 땅 0 그루 — 너도밤나무는 가뭄에 약해 메마른 땅(30 °C·습도 0.2)에 자라지 않고, 나무 없는 무대가 하나 있어야 나무 효과를 견준다
          (R4 계획 RL_V3_R4_PLAN.md 의 '나무 없는 무대').
  굵기    줄기 원판 반지름 r = 밑동 꼭짓점 반경(메시 40.45 cm, 바닥 육각형 꼭짓점 6 — 10-17 편집기 파이썬으로 잼) × 크기. 밑동이 가장 굵다(메시 110 cm
          높이에서 32.5 cm). 꼭짓점 반경이라 보이는 줄기가 원판 밖으로 나오지 않는다. 사슴·늑대 몸 30 cm 는 세계가 더한다(FObstacleConfig::BodyR).
  크기    U[1.8, 2.2] (팀 배치 2 배의 ±10% — 같은 숲 나무의 키 차이 어림), 방위 U[0°, 360°), 곧게 선다(땅 기울기를 따르지 않는다 — 나무는 위로 자란다).
  간격    줄기 중심끼리 d_min 밖 (포아송 원반 = 무작위로 던져 가까운 것은 버림). d_min = 빈 넓이 ÷ 그루 수의 제곱근의 절반(0.5 m 단위로 반올림) —
          성숙림 큰 나무는 서로 그늘·뿌리 다툼으로 고르게 떨어져 선다(무작위보다 고른 무늬 — 어림). 숲 줄기 사이 틈은 d_min − 2r ≥ 3 m(사슴이 빠져나감).
  은신처  우리 은신처 원 4 곳(무대 1/4·3/4 지점, 반경 12 m — C++ ExtraCoverCount 4·ExtraCoverRadiusFrac 0.1, 파이썬 cover_layout quad)에서
          줄기 가장자리가 반경 + 2 m 밖. 은신처 원 안 나무는 C++ 레벨 읽기도 은신처 장식으로 보고 빼는 자리다.
  벽      줄기 가장자리가 무대 벽에서 4 m 밖 (무대 벽은 실제 땅에 없는 울타리 — 벽과 줄기 사이에 사슴이 끼지 않게, 파이썬 무작위 배치 0.6 m 보다 넉넉히).
  빈터    무대 중심 반경 22 m 안에는 놓지 않는다. 무대 중심이 팀 먹이 자리(Eco_FoodHint_*)이고 숲 무대에서는 팀 은신처 앵커 둘·플레이어 시작이 그 안에 있다.
          숲 속 빈터(볕이 들어 풀이 자라는 곳)에서 사슴이 풀을 뜯는다 — v3 먹이 격자는 세션 시드마다 바뀌어(FFoodGrid::Build) 고정 표가 따라갈 수 없다.
  지킬 자리 늑대 시작 모서리 넷(무대 중심 ± 0.4 × 한 변 — C++ WolfStartCornerFrac 0.4, 파이썬 start_layout stage)에서 줄기 가장자리 3 m 밖
          (시작 자리 계획이 나무 때문에 바뀌지 않게). 숲은 팀 은신처 앵커 둘(반경 1.5 m + 2 m)·플레이어 시작(3 m)도 — 자리는 통합 레벨 읽기
          level_shc/scan_LV_Ecosystem_IntegrationTest.json.
  시드    숲 32095, 고지 32096 (numpy default_rng, 탐색 범위). 뽑기 순서: 한 번 던질 때마다 x, y, 크기, 방위.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
TREES = HERE.parent
ROOT = HERE.parents[4]                      # herbivore_rl
REPO = ROOT.parent
JSON_OUT = TREES / "tree_layout.json"
PNG_OUT = TREES / "tree_layout.png"
HEADER_OUT = REPO / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy" / "TreeLayoutV3.h"
OBST_YAML = ROOT / "configs" / "v3_wild2_obstacle_mirror.yaml"
YAML_OUT = ROOT / "configs" / "v3_wild2_trees_mirror.yaml"

VERSION = "trees-1017a"
MESH = "/Game/SHC/Fab/Realistic_Beech_Tree_3D_Vegetation/Beech_Tree.Beech_Tree"
UNIT_CM = 200.0                             # EcoRepertoireV3::kUnitCm
SIZE = 60.0                                 # 무대 한 변 (단위) = 120 m
TRUNK_R_MESH_CM = 40.45                     # 밑동 바닥 육각형 꼭짓점 반경 (메시 cm, 10-17 잼)
PIVOT_OFF_MESH_CM = (-3.707, 0.246)         # 메시 기준점 → 밑동 중심 (메시 cm, 바닥 꼭짓점 평균)
SINK_CM = 10.0                              # 밑동을 줄기 아래 가장 낮은 땅보다 이만큼 묻는다 (팀 피드백 '0~30 cm')
SCALE = (1.8, 2.2)
COVER_CLEAR_M = 2.0
WALL_CLEAR_M = 4.0
MEADOW_R_M = 22.0
WOLF_KEEP_M = 3.0
MIN_GAP_M = 3.0                             # 줄기 사이 틈 하한 (검사만)
TRIES = 200000
BODY_R = 0.15                               # FObstacleConfig::BodyR (기록·검사만)
# (지역, 그루 수, 시드). 지역 이름 = 팀 AEcologyRegion RegionId. 메마른 땅은 0 그루(위 규칙)
STAGES = (("Barren", 0, None), ("Forest", 24, 32095), ("Highland", 9, 32096))
# 무대 단위 지킬 자리 (x, y, 반경 m — 줄기 가장자리가 이 반경 밖). 숲 무대 원점 (28200, 40500) cm 기준 (통합 레벨 읽기)
EXTRA_KEEP = {
    "Forest": (((33300.0 - 28200.0) / UNIT_CM, (45100.0 - 40500.0) / UNIT_CM, 1.5 + COVER_CLEAR_M),    # Eco_Shelter_Forest_01
               ((34200.0 - 28200.0) / UNIT_CM, (44400.0 - 40500.0) / UNIT_CM, 1.5 + COVER_CLEAR_M),    # Eco_Shelter_Forest_02
               ((34200.0 - 28200.0) / UNIT_CM, (48500.0 - 40500.0) / UNIT_CM, 3.0)),                   # PlayerStart
}


def d_lit(x) -> str:
    """double 리터럴: 파이썬 repr (다시 읽으면 같은 float64 가 되는 가장 짧은 표기)."""
    x = float(x)
    if not math.isfinite(x):
        raise SystemExit(f"유한하지 않은 값: {x}")
    s = repr(x)
    return s if ("." in s or "e" in s) else s + ".0"


def quad_covers(size: float = SIZE) -> list[tuple[float, float, float]]:
    """우리 은신처 원 (C++ 무대 1/4·3/4 지점, 반경 clamp(0.1 × 한 변, 4, 9) — EcoWorldV3::QuadCovers 와 같은 자리)."""
    r = min(max(0.1 * size, 4.0), 9.0)
    a, b = 0.25 * size, 0.75 * size
    return [(a, a, r), (b, a, r), (a, b, r), (b, b, r)]


def wolf_corners(size: float = SIZE) -> list[tuple[float, float]]:
    """늑대 시작 모서리 힌트 (C++ PlanStage: 중심 ± WolfStartCornerFrac 0.4 × 한 변, 차례 (+,+)·(−,−)·(+,−)·(−,+))."""
    c, k = 0.5 * size, 0.4 * size
    return [(c + k, c + k), (c - k, c - k), (c + k, c - k), (c - k, c + k)]


def keep_points(region: str) -> list[tuple[float, float, float]]:
    """줄기 가장자리가 비워 둘 자리 (x, y, 반경 단위)."""
    out = [(x, y, WOLF_KEEP_M / 2.0) for x, y in wolf_corners()]
    out += [(x, y, m / 2.0) for x, y, m in EXTRA_KEEP.get(region, ())]
    return out


def site_ok(x: float, y: float, r: float, region: str) -> bool:
    """줄기 (x, y, 반지름 r) 가 무대 규칙(벽·은신처·빈터·지킬 자리)을 지키나 (간격은 따로)."""
    e = WALL_CLEAR_M / 2.0 + r
    if not (e <= x <= SIZE - e and e <= y <= SIZE - e):
        return False
    for cx, cy, cr in quad_covers():
        if math.hypot(x - cx, y - cy) < cr + COVER_CLEAR_M / 2.0 + r:
            return False
    if math.hypot(x - 0.5 * SIZE, y - 0.5 * SIZE) < MEADOW_R_M / 2.0 + r:
        return False
    for kx, ky, kr in keep_points(region):
        if math.hypot(x - kx, y - ky) < kr + r:
            return False
    return True


@functools.lru_cache(maxsize=None)
def free_area_m2(region: str) -> float:
    """규칙을 지키는 넓이 (m², 0.1 단위 격자, 반지름 = 크기 2 배 줄기 — site_ok 와 같은 식을 배열로) — 간격 d_min 을 정하는 데만 쓴다."""
    r = TRUNK_R_MESH_CM * 2.0 / UNIT_CM
    g = np.arange(0.05, SIZE, 0.1)
    X, Y = np.meshgrid(g, g)
    e = WALL_CLEAR_M / 2.0 + r
    ok = (X >= e) & (X <= SIZE - e) & (Y >= e) & (Y <= SIZE - e)
    for cx, cy, cr in quad_covers():
        ok &= np.hypot(X - cx, Y - cy) >= cr + COVER_CLEAR_M / 2.0 + r
    ok &= np.hypot(X - 0.5 * SIZE, Y - 0.5 * SIZE) >= MEADOW_R_M / 2.0 + r
    for kx, ky, kr in keep_points(region):
        ok &= np.hypot(X - kx, Y - ky) >= kr + r
    return float(ok.sum()) * (0.1 * UNIT_CM / 100.0) ** 2


def min_spacing_m(region: str, n: int) -> float:
    return 0.5 * round(2.0 * 0.5 * math.sqrt(free_area_m2(region) / n))


def pivot_of(x: float, y: float, yaw_deg: float, scale: float) -> tuple[float, float]:
    """줄기 중심 (x, y) → 액터 기준점 (단위). 메시 기준점에서 밑동 중심까지 = 크기 × PIVOT_OFF 를 방위만큼 돌린 것 (언리얼 yaw: x → y 쪽으로 돈다)."""
    a = math.radians(yaw_deg)
    ox, oy = scale * PIVOT_OFF_MESH_CM[0], scale * PIVOT_OFF_MESH_CM[1]
    rx, ry = ox * math.cos(a) - oy * math.sin(a), ox * math.sin(a) + oy * math.cos(a)
    return round(x - rx / UNIT_CM, 6), round(y - ry / UNIT_CM, 6)


def place(region: str, n: int, seed: int) -> tuple[list[dict], float, int]:
    """포아송 원반 던지기: 한 번에 x, y, 크기, 방위를 뽑고 규칙·간격을 지키면 받는다. 반환 (나무 목록 (x, y, r) 순, d_min m, 던진 수)."""
    d_min = min_spacing_m(region, n)
    g = np.random.default_rng(seed)
    trees: list[dict] = []
    tries = 0
    while len(trees) < n:
        tries += 1
        if tries > TRIES:
            raise SystemExit(f"{region}: {TRIES} 번 안에 {n} 그루를 못 놓았다 (놓은 수 {len(trees)}, d_min {d_min} m)")
        x, y = round(float(g.uniform(0.0, SIZE)), 3), round(float(g.uniform(0.0, SIZE)), 3)
        s = round(float(g.uniform(*SCALE)), 3)
        yaw = round(float(g.uniform(0.0, 360.0)), 1)
        r = TRUNK_R_MESH_CM * s / UNIT_CM
        if not site_ok(x, y, r, region):
            continue
        if any(math.hypot(x - t["x"], y - t["y"]) < d_min / 2.0 for t in trees):
            continue
        px, py = pivot_of(x, y, yaw, s)
        trees.append(dict(x=x, y=y, r=r, pivot_x=px, pivot_y=py, yaw_deg=yaw, scale=s))
    trees.sort(key=lambda t: (t["x"], t["y"], t["r"]))
    return trees, d_min, tries


def build() -> dict:
    regions = []
    for region, n, seed in STAGES:
        if n == 0:
            regions.append(dict(region=region, count=0, seed=None, min_spacing_m=None, free_area_m2=None, tries=0, discs=[], trees=[]))
            continue
        trees, d_min, tries = place(region, n, seed)
        regions.append(dict(region=region, count=n, seed=seed, min_spacing_m=d_min, free_area_m2=round(free_area_m2(region), 2), tries=tries,
                            discs=[[t["x"], t["y"], t["r"]] for t in trees], trees=trees))
    body = dict(version=VERSION, mesh=MESH, units="stage units, 1 unit = 200 cm, x·y from stage origin (min corner)", stage_size=SIZE,
                trunk_r_mesh_cm=TRUNK_R_MESH_CM, pivot_offset_mesh_cm=list(PIVOT_OFF_MESH_CM), sink_cm=SINK_CM, scale_range=list(SCALE),
                rules=dict(cover_clear_m=COVER_CLEAR_M, wall_clear_m=WALL_CLEAR_M, meadow_r_m=MEADOW_R_M, wolf_keep_m=WOLF_KEEP_M,
                           covers=[list(c) for c in quad_covers()], keep={k: [list(p) for p in keep_points(k)] for k, _, _ in STAGES}),
                regions=regions)
    body["digest"] = hashlib.sha1(json.dumps([r["discs"] for r in regions] + [[[t["pivot_x"], t["pivot_y"], t["yaw_deg"], t["scale"]]
                                                                             for t in r["trees"]] for r in regions]).encode()).hexdigest()[:12]
    return body


def check(body: dict) -> list[str]:
    """규칙을 다시 검사한다 (만든 뒤·시험). 어긋남 목록."""
    bad = []
    for reg in body["regions"]:
        tr = reg["trees"]
        for t in tr:
            if not site_ok(t["x"], t["y"], t["r"], reg["region"]):
                bad.append(f"{reg['region']} ({t['x']}, {t['y']}) 규칙 밖")
            if abs(t["r"] - TRUNK_R_MESH_CM * t["scale"] / UNIT_CM) > 0.0 or not SCALE[0] <= t["scale"] <= SCALE[1]:
                bad.append(f"{reg['region']} ({t['x']}, {t['y']}) 반지름·크기")
        for i in range(len(tr)):
            for j in range(i + 1, len(tr)):
                d = math.hypot(tr[i]["x"] - tr[j]["x"], tr[i]["y"] - tr[j]["y"])
                if d < reg["min_spacing_m"] / 2.0 or (d - tr[i]["r"] - tr[j]["r"]) * 2.0 < MIN_GAP_M:
                    bad.append(f"{reg['region']} {i}·{j} 간격 {d * 2.0:.2f} m")
        if reg["discs"] != sorted(reg["discs"]):
            bad.append(f"{reg['region']} 원판 순서")
    return bad


def render_json(body: dict) -> str:
    return json.dumps(body, ensure_ascii=False, indent=1) + "\n"


def render_header(body: dict) -> str:
    L = [f"// 자동 생성 — herbivore_rl/results/v3/wild2/trees/make_tree_layout.py (손으로 고치지 않는다). 배치 {body['version']}, 지문 {body['digest']}.",
         "// 통합 v3 모드가 팀 통합 레벨의 동물 무대마다 실행 중에 놓는 나무(팀 Beech_Tree, 충돌 없음)와 그 줄기 원판 (10-17 사용자 '우리 쪽 테스트 레벨에 저 사람이",
         "// 만든 장애물들 적절히 배치해 봐'). 규칙·근거는 생성 파일 머리 주석과 herbivore_rl/results/v3/wild2/trees/README.md. 같은 숫자가 tree_layout.json 과",
         "// configs/v3_wild2_trees_mirror.yaml(obstacles.fixed, 숲)에 있다 — 파이썬 거울이 같은 원판으로 돈다. 쓰는 곳: EcoPolicyV3IntegratedSubsystem 'StageTrees'.",
         "#pragma once", "", "#include <cstdint>", "", "namespace EcoTreeLayoutV3", "{",
         f"\tinline constexpr const char* kVersion = \"{body['version']}\";",
         f"\tinline constexpr const char* kDigest = \"{body['digest']}\";",
         f"\tinline constexpr const char* kMeshPath = \"{body['mesh']}\";",
         f"\tinline constexpr double kStageSizeUnits = {d_lit(body['stage_size'])};     // 이 표가 맞는 무대 한 변 (단위) — 다른 크기 무대에는 놓지 않는다",
         f"\tinline constexpr double kTrunkRadiusMeshCm = {d_lit(body['trunk_r_mesh_cm'])};   // 밑동 꼭짓점 반경 (메시 cm) — 원판 반지름 = 이 값 × 크기 ÷ 200",
         f"\tinline constexpr double kPivotOffsetMeshCmX = {d_lit(body['pivot_offset_mesh_cm'][0])};   // 메시 기준점 → 밑동 중심 (메시 cm)",
         f"\tinline constexpr double kPivotOffsetMeshCmY = {d_lit(body['pivot_offset_mesh_cm'][1])};",
         f"\tinline constexpr double kSinkCm = {d_lit(body['sink_cm'])};   // 밑동을 줄기 아래 가장 낮은 땅보다 묻는 깊이",
         f"\tinline constexpr double kScaleLo = {d_lit(body['scale_range'][0])};",
         f"\tinline constexpr double kScaleHi = {d_lit(body['scale_range'][1])};",
         f"\tinline constexpr double kCoverClearM = {d_lit(COVER_CLEAR_M)};   // 줄기 가장자리 ↔ 은신처 원 둘레 (m)",
         f"\tinline constexpr double kWallClearM = {d_lit(WALL_CLEAR_M)};    // 줄기 가장자리 ↔ 무대 벽 (m)",
         f"\tinline constexpr double kMeadowRadiusM = {d_lit(MEADOW_R_M)};  // 무대 중심 빈터 반경 (m)",
         f"\tinline constexpr double kWolfKeepM = {d_lit(WOLF_KEEP_M)};     // 줄기 가장자리 ↔ 늑대 시작 모서리 (m)",
         "", "\t/** 나무 하나 (무대 단위, 무대 (0, 0) = 가장 작은 모서리). 원판 = (X, Y, R). 액터 = 기준점 (PivotX, PivotY)·방위 YawDeg·크기 Scale. */",
         "\tstruct FTree", "\t{", "\t\tdouble X;", "\t\tdouble Y;", "\t\tdouble R;", "\t\tdouble PivotX;", "\t\tdouble PivotY;", "\t\tdouble YawDeg;",
         "\t\tdouble Scale;", "\t};", ""]
    names = {}
    for reg in body["regions"]:
        if not reg["trees"]:
            continue
        nm = f"k{reg['region']}Trees"
        names[reg["region"]] = nm
        L.append(f"\t// {reg['region']}: {reg['count']} 그루, 시드 {reg['seed']}, 줄기 중심 간격 {reg['min_spacing_m']} m 밖, 빈 넓이 {reg['free_area_m2']} m²")
        L.append(f"\tinline constexpr FTree {nm}[{len(reg['trees'])}] = {{")
        for t in reg["trees"]:
            L.append("\t\t{" + ", ".join(d_lit(t[k]) for k in ("x", "y", "r", "pivot_x", "pivot_y", "yaw_deg", "scale")) + "},")
        L.append("\t};")
        L.append("")
    L += ["\t/** 지역 무대 하나의 표 (Region = 팀 AEcologyRegion RegionId). Num 0 = 나무 없음. */",
          "\tstruct FStageTrees", "\t{", "\t\tconst char* Region;", "\t\tconst FTree* Trees;", "\t\tstd::int32_t Num;", "\t\tdouble MinSpacingM;", "\t};", ""]
    L.append(f"\tinline constexpr std::int32_t kNumStages = {len(body['regions'])};")
    L.append(f"\tinline constexpr FStageTrees kStages[{len(body['regions'])}] = {{")
    for reg in body["regions"]:
        nm = names.get(reg["region"])
        L.append(f"\t\t{{\"{reg['region']}\", {nm if nm else 'nullptr'}, {reg['count']}, {d_lit(reg['min_spacing_m'] or 0.0)}}},")
    L += ["\t};", "}", ""]
    return "\n".join(L)


def render_yaml(body: dict) -> str:
    """configs/v3_wild2_trees_mirror.yaml = 머리 주석 + v3_wild2_obstacle_mirror.yaml 그대로(version 만 바꿈) + obstacles.fixed(숲 무대 원판)."""
    src = OBST_YAML.read_text(encoding="utf-8")
    forest = next(r for r in body["regions"] if r["region"] == "Forest")
    head = [
        "# 야생 2단계 3 나무 거울 세계 — 통합 레벨 무대에 놓은 팀 나무 줄기 (10-17 사용자 '그럼 그냥 우리 쪽 테스트 레벨에 저 사람이 만든 장애물들 적절히 배치해 봐').",
        "# 자동 생성 — results/v3/wild2/trees/make_tree_layout.py (손으로 고치지 않는다. v3_wild2_obstacle_mirror.yaml 을 고치면 다시 만든다). 설명 results/v3/wild2/trees/README.md.",
        f"# = configs/v3_wild2_obstacle_mirror.yaml(아래 그대로) + obstacles.fixed 하나: 무작위 줄기·바위 대신 배치 표 {body['version']}(지문 {body['digest']})의",
        f"#   숲 무대 Beech_Tree {forest['count']} 그루 줄기 원판(반지름 = 밑동 꼭짓점 반경 40.45 cm × 크기 1.8~2.2 = 0.73~0.89 m). fixed 가 있으면 tree_per_ha·rock_per_ha",
        "#   무작위 배치는 쓰지 않는다(난수를 뽑지 않는다). 언리얼 통합 v3 모드(eco.IntegratedV3.StageTrees 1, 기본)가 같은 표로 나무를 놓고 같은 원판을 세계에 넣는다.",
        "# 지역마다 다른 표(숲 24·고지 9·메마른 땅 0): 짝 비교 실행기 run_mirror.py --unreal-maps … --unreal-obstacles results/v3/wild2/trees/tree_layout.json",
        "#   (그 파일은 언리얼 내보내기 꼴 — 지도 (세션, 지역) 마다 그 지역 원판을 fixed 로 덮는다). 이 파일 하나만 쓰면 모든 세계가 숲 무대다.",
        "#",
        "# ── 아래는 v3_wild2_obstacle_mirror.yaml 그대로 (version 과 obstacles.fixed 만 다르다) ──",
    ]
    if 'version: "3.wild2obstacle"' not in src or "    detour_help_drop: 38\n" not in src:
        raise SystemExit("v3_wild2_obstacle_mirror.yaml 의 version·detour_help_drop 줄을 못 찾았다 — 생성기를 고친다")
    src = src.replace('version: "3.wild2obstacle"', 'version: "3.wild2trees"', 1)
    fixed = ["    # 나무 배치 표 (자동 생성 — make_tree_layout.py): 숲 무대 줄기 원판 [x, y, r] (단위, (x, y, r) 순 = C++ 원판 순서)", "    fixed:"]
    fixed += [f"      - [{d_lit(x)}, {d_lit(y)}, {d_lit(r)}]" for x, y, r in forest["discs"]]
    src = src.replace("    detour_help_drop: 38\n", "    detour_help_drop: 38\n" + "\n".join(fixed) + "\n", 1)
    return "\n".join(head) + "\n" + src


def plot(body: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle

    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.4))
    for ax, reg in zip(axes, body["regions"]):
        m = UNIT_CM / 100.0
        ax.add_patch(Rectangle((0, 0), SIZE * m, SIZE * m, fill=False, ec="#333", lw=1.2))
        e = WALL_CLEAR_M
        ax.add_patch(Rectangle((e, e), SIZE * m - 2 * e, SIZE * m - 2 * e, fill=False, ec="#999", lw=0.6, ls=":"))
        for cx, cy, cr in quad_covers():
            ax.add_patch(Circle((cx * m, cy * m), cr * m, fc="#5566aa33", ec="#5566aa", lw=1.0))
            ax.add_patch(Circle((cx * m, cy * m), cr * m + COVER_CLEAR_M, fill=False, ec="#5566aa", lw=0.5, ls="--"))
        ax.add_patch(Circle((0.5 * SIZE * m, 0.5 * SIZE * m), MEADOW_R_M, fc="#dddd8833", ec="#aaa055", lw=0.8, ls="--"))
        for kx, ky, kr in keep_points(reg["region"]):
            ax.add_patch(Circle((kx * m, ky * m), kr * m, fill=False, ec="#cc6633", lw=0.6))
        for t in reg["trees"]:
            ax.add_patch(Circle((t["x"] * m, t["y"] * m), 6.4 * t["scale"] / 2.0, fc="#3a7a3a22", ec="none"))   # 잎 넓이 (중앙 반경 어림)
            ax.add_patch(Circle((t["x"] * m, t["y"] * m), t["r"] * m, fc="#6b4a2b", ec="#3b2a1b", lw=0.5))
        n = reg["count"]
        sub = f", 간격 {reg['min_spacing_m']} m 밖" if n else " (메마른 땅 — 나무 없음)"
        ax.set_title(f"{reg['region']} 무대: Beech_Tree {n} 그루{sub}", fontsize=10)
        ax.set_xlim(-3, SIZE * m + 3)
        ax.set_ylim(-3, SIZE * m + 3)
        ax.set_aspect("equal")
        ax.set_xlabel("x (m, 무대 원점에서)")
        ax.set_ylabel("y (m)")
    fig.suptitle(f"통합 레벨 무대 나무 배치 {body['version']} — 갈색 = 줄기 원판(세계 장애물), 초록 = 잎(그림만), 파랑 = 은신처 12 m(+2 m), 노랑 = 빈터 22 m, "
                 "주황 = 늑대 시작·팀 은신처·플레이어 시작", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="쓰지 않고 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다")
    ap.add_argument("--no-plot", action="store_true")
    a = ap.parse_args(argv)
    body = build()
    bad = check(body)
    if bad:
        raise SystemExit("규칙 어긋남: " + "; ".join(bad))
    outs = {JSON_OUT: render_json(body), HEADER_OUT: render_header(body), YAML_OUT: render_yaml(body)}
    if a.check:
        stale = [str(p) for p, text in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            raise SystemExit("지금 규칙으로 만든 것과 다르다: " + ", ".join(stale))
        print(f"최신 ({body['version']}, 지문 {body['digest']})")
        return
    for p, text in outs.items():
        p.write_text(text, encoding="utf-8", newline="\n")
    if not a.no_plot:
        plot(body, PNG_OUT)
    for reg in body["regions"]:
        rs = [t["r"] * UNIT_CM / 100.0 for t in reg["trees"]]
        print(f"{reg['region']}: {reg['count']} 그루" + (f", 간격 {reg['min_spacing_m']} m 밖, 빈 넓이 {reg['free_area_m2']} m², 던짐 {reg['tries']}, "
                                                    f"줄기 반지름 {min(rs):.3f}~{max(rs):.3f} m" if rs else ""))
    print(f"-> {JSON_OUT}\n-> {HEADER_OUT}\n-> {YAML_OUT}\n지문 {body['digest']}")


if __name__ == "__main__":
    sys.exit(main())
