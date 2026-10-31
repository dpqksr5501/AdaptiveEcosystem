"""야생 2단계 3 측정용 장애물 지도 (10-17). 언리얼 팀 통합 레벨의 무대에는 충돌하는 나무·바위가 없어서(레벨 읽기: 숲 무대 메시 38 개는 모두 충돌 없는 풀),
파이썬 거울의 숲 배치(configs/v3_wild2_obstacle_mirror.yaml obstacles — 나무 줄기 1 ha 250·바위 1 ha 5)로 지역마다 원판을 만들어 언리얼과 같은 원판으로
견준다. herbivore_rl/ 에서

    python results/v3/wild2/make_obstacle_maps.py --sessions 20000-20002 --out results/v3/wild2/obstacle_maps

출력: 세션마다 <out>/s<세션 시드>.json — 언리얼 내보내기(EcoPolicyV3IntegratedSubsystem::ExportObstacles)와 같은 꼴 {session_seed, regions: [{region, size,
discs: [[x, y, r], …], covers: [[x, y, r], …]}]}. 언리얼은 -EcoV3ObstacleImport=<파일> 로 읽고(측정 전용 — 레벨에 보이는 물체가 없는 원판), 파이썬 거울은
run_mirror.py --unreal-maps … --unreal-obstacles <out> 로 읽는다.
배치 = 파이썬 세계(설정 그대로, 사슴 8)의 obstacle_layout — 기능 스트림 obstacles part 0. 세계 시드 = 33090 + 3·(세션 순번) + (지역 순번 Barren 0·Forest 1·Highland 2)
(탐색 범위 33000~33099, 세션 셋까지). 은신처 원은 파이썬 무대 배치(quad)이고 언리얼 무대와 같다(10-17 레벨 읽기 JSON 의 covers 와 같음을 시험이 본다).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

CONFIG = ROOT / "configs" / "v3_wild2_obstacle_mirror.yaml"
REGIONS = ("Barren", "Forest", "Highland")
SEED_BASE = 33090
UNREAL_SEED_RANGE = (20000, 20019)


def layout_seed(session_index: int, region: str) -> int:
    s = SEED_BASE + 3 * int(session_index) + REGIONS.index(region)
    if not 33000 <= s <= 33099:
        raise ValueError(f"배치 시드 {s} 가 탐색 범위 33000~33099 밖이다(세션은 셋까지)")
    return s


def region_map(session_index: int, region: str, config: Path = CONFIG) -> dict:
    from env_v2.config import load_v2_config
    from env_v2.world import World

    w = World(load_v2_config(config).replace(N=8), seeds=[layout_seed(session_index, region)])
    if w._ob is None:
        raise ValueError(f"{config} 는 obstacles 를 켠 설정이어야 한다")
    return dict(region=region, size=float(w.size), seed=int(w.seed), discs=[[float(v) for v in row] for row in w.obstacles],
                covers=np.c_[w.cov_c, w.cov_r].tolist())


def build(sessions, config: Path = CONFIG) -> dict:
    out = {}
    for i, u in enumerate(sessions):
        if not UNREAL_SEED_RANGE[0] <= int(u) <= UNREAL_SEED_RANGE[1]:
            raise ValueError(f"세션 시드 {u} 는 {UNREAL_SEED_RANGE} 안이어야 한다")
        out[int(u)] = dict(session_seed=int(u), units="stage units, 1 unit = 200 cm, x·y from stage origin",
                           source=f"python obstacle_layout ({Path(config).name})", regions=[region_map(i, r, config) for r in REGIONS])
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sessions", default="20000-20002")
    ap.add_argument("--out", type=Path, default=HERE.parent / "obstacle_maps")
    ap.add_argument("--config", type=Path, default=CONFIG)
    a = ap.parse_args(argv)
    lo, _, hi = a.sessions.partition("-")
    sessions = list(range(int(lo), int(hi or lo) + 1))
    a.out.mkdir(parents=True, exist_ok=True)
    for u, d in build(sessions, a.config).items():
        p = a.out / f"s{u}.json"
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        print(f"{p}: " + ", ".join(f"{r['region']} {len(r['discs'])}" for r in d["regions"]))


if __name__ == "__main__":
    main()
