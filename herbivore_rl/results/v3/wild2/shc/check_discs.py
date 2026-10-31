"""SHC 거울 원판 대조 (10-17, 측정 전용): 언리얼이 쓴 원판(-EcoV3ObstacleExport JSON)·우리가 만든 지도(make_shc_obstacle_maps.py)·파이썬 거울 세계가 실제로
쓰는 원판(World.obstacles)이 지도 (세션, 지역) 마다 비트 단위로 같은지 본다. 은신처 원(언리얼 Covers 대 파이썬 cov_c·cov_r)과 무대 원점도 함께 본다.
은신처 원은 비트 단위로 같지 않다(알려진 것): 파이썬 무대 배치는 cos·sin 으로 1/4·3/4 자리를 셈해 14.999999999999996 이 나오고, 언리얼은 놓은 앵커 자리
(cm)에서 셈해 15 다 — 차이 3.6e-15 단위(1e-14 m 쯤). 그래서 은신처는 가장 큰 차이와 1e-9 안(tests/test_wild2_obstacle.py 와 같은 허용)을 적는다.
herbivore_rl/ 에서

    python results/v3/wild2/shc/check_discs.py --sessions 20000-20002

파이썬 세계는 run_mirror.py 짝 비교와 같은 길로 만든다: mirror_cfg(사슴 128, 늑대 식사 38) → obstacles.fixed ← 지도 원판 → World(시드) → apply_unreal_map.
비트 단위 = 모양이 같고 모든 칸의 float.hex 가 같다(원판이 0 개면 모양 (0, 3) 끼리). 출력 stdout 과 --out JSON.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]
for p in (ROOT, ROOT / "results" / "v3" / "mirror"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

CONFIG = ROOT / "configs" / "v3_wild2_obstacle_mirror.yaml"


def hexes(a) -> list:
    a = np.asarray(a, dtype=np.float64).reshape(-1, 3)
    return [[float(v).hex() for v in row] for row in a]


def same(a, b) -> bool:
    a = np.asarray(a, dtype=np.float64).reshape(-1, 3)
    b = np.asarray(b, dtype=np.float64).reshape(-1, 3)
    return a.shape == b.shape and hexes(a) == hexes(b)


def main(argv=None) -> None:
    import run_mirror as rm
    from env.config import Config
    from env_v2 import world as wm

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sessions", default="20000-20002")
    ap.add_argument("--exports", type=Path, default=HERE.parent / "unreal_exports", help="언리얼 내보내기 export_s<세션>.json 폴더")
    ap.add_argument("--maps", type=Path, default=HERE.parent / "obstacle_maps")
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--seed", type=int, default=32000, help="파이썬 세계 시드 (원판·은신처는 시드와 무관 — 확인용 하나)")
    ap.add_argument("--out", type=Path, default=HERE.parent / "disc_check.json")
    a = ap.parse_args(argv)
    sessions = rm.parse_unreal_maps(a.sessions)
    cfg = rm.mirror_cfg(128, rm.eat_steps_of_seconds(5.0), a.config).to_dict()
    maps = rm.load_unreal_obstacles(a.maps, sessions)
    rows, ok = [], True
    for u in sessions:
        exp = json.loads((a.exports / f"export_s{u}.json").read_text(encoding="utf-8"))
        mp = json.loads((a.maps / f"s{u}.json").read_text(encoding="utf-8"))
        mreg = {r["region"]: r for r in mp["regions"]}
        for er in sorted(exp["regions"], key=lambda r: r["region"]):
            g = er["region"]
            c = copy.deepcopy(cfg)
            c["v2"]["features"]["obstacles"]["fixed"] = maps[(u, g)]
            w = wm.World(Config(c), seeds=[int(a.seed)])
            rm.apply_unreal_map(w, u, g)
            py = np.asarray(w.obstacles, dtype=np.float64)
            py_cov = np.c_[w.cov_c, w.cov_r]
            row = dict(session=u, region=g, unreal_discs=len(er["discs"]), map_discs=len(mreg[g]["discs"]), python_discs=int(len(py)),
                       python_shape=list(py.shape), imported=bool(er.get("imported")), level_discs=int(er.get("level_discs", -1)),
                       unreal_eq_map=same(er["discs"], mreg[g]["discs"]), unreal_eq_python=same(er["discs"], py),
                       covers_bit_eq=same(er["covers"], py_cov),
                       covers_max_diff=float(np.abs(np.asarray(er["covers"], dtype=np.float64).reshape(-1, 3) - py_cov).max()) if len(py_cov) else 0.0,
                       origin_eq=[float(v) for v in er["origin_cm"][:2]] == [float(v) for v in mreg[g]["origin_cm"][:2]],
                       size_eq=float(er["size"]) == float(w.size) == float(mreg[g]["size"]))
            row["covers_close"] = len(er["covers"]) == len(py_cov) and row["covers_max_diff"] <= 1e-9
            row["all_ok"] = all(row[k] for k in ("unreal_eq_map", "unreal_eq_python", "covers_close", "origin_eq", "size_eq", "imported"))
            ok &= row["all_ok"]
            rows.append(row)
            print(f"s{u} {g:8s}: 원판 언리얼 {row['unreal_discs']} · 지도 {row['map_discs']} · 파이썬 {row['python_discs']} {tuple(py.shape)} | "
                  f"언리얼=지도 {row['unreal_eq_map']} · 언리얼=파이썬 {row['unreal_eq_python']} · 은신처 비트 {row['covers_bit_eq']} (가장 큰 차이 "
                  f"{row['covers_max_diff']:.1e}) · 원점 {row['origin_eq']} · "
                  f"한 변 {row['size_eq']} · 가져옴 {row['imported']} (레벨에서 읽은 원판 {row['level_discs']})")
    print("모두 같음" if ok else "다른 것이 있다")
    a.out.write_text(json.dumps(dict(sessions=sessions, config=str(a.config.relative_to(ROOT)) if a.config.is_relative_to(ROOT) else str(a.config),
                                     seed=a.seed, all_ok=bool(ok), rows=rows), ensure_ascii=False, indent=1), encoding="utf-8")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
