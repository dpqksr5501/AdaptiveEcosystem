"""무대 나무 원판 대조 (10-17 확인, 측정 전용): 언리얼이 세계에 넣은 원판(-EcoV3ObstacleExport JSON)·배치 표(tree_layout.json)·파이썬 거울 세계가
실제로 쓰는 원판(World.obstacles)이 지도 (세션, 지역) 마다 비트 단위로 같은지 본다. 거울 설정 configs/v3_wild2_trees_mirror.yaml 의 obstacles.fixed 가
숲 표와 같은지, 언리얼 내보내기의 tree_discs(나무 원판) = discs(세계 원판, 레벨 원판 0 이면 같다)인지, 은신처 원·무대 원점·한 변도 함께 본다.
은신처 원은 비트 단위로 같지 않다(알려진 것, ../shc/check_discs.py 머리 주석): 파이썬은 cos·sin 으로 14.999999999999996, 언리얼은 앵커 자리에서 15 —
그래서 가장 큰 차이와 1e-9 안을 적는다. --old 를 주면 전에 올려 둔 내보내기와도 견준다(같은 시드면 같은 세계인지).
herbivore_rl/ 에서

    python results/v3/wild2/trees/check_discs.py --sessions 20000-20002 --exports <언리얼 내보내기 폴더(export_s<세션>.json)>

파이썬 세계는 run_mirror.py 짝 비교와 같은 길로 만든다: mirror_cfg(사슴 128, 늑대 식사 38, 거울 설정) → obstacles.fixed ← 표의 그 지역 원판
(run_mirror.load_unreal_obstacles) → World(시드) → apply_unreal_map. 비트 단위 = 모양이 같고 모든 칸의 float.hex 가 같다. 출력 stdout 과 --out JSON.
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
import yaml  # noqa: E402

CONFIG = ROOT / "configs" / "v3_wild2_trees_mirror.yaml"
LAYOUT = HERE.parent / "tree_layout.json"


def hexes(a) -> list:
    a = np.asarray(a, dtype=np.float64).reshape(-1, 3)
    return [[float(v).hex() for v in row] for row in a]


def same(a, b) -> bool:
    a = np.asarray(a, dtype=np.float64).reshape(-1, 3)
    b = np.asarray(b, dtype=np.float64).reshape(-1, 3)
    return a.shape == b.shape and hexes(a) == hexes(b)


def export_path(folder: Path, u: int) -> Path:
    for name in (f"export_s{u}.json", f"s{u}.json"):
        if (folder / name).exists():
            return folder / name
    raise SystemExit(f"{folder} 에 세션 {u} 내보내기가 없다")


def main(argv=None) -> None:
    import run_mirror as rm
    from env.config import Config
    from env_v2 import world as wm

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sessions", default="20000-20002")
    ap.add_argument("--exports", type=Path, default=HERE.parent / "unreal_exports", help="언리얼 내보내기 폴더 (export_s<세션>.json 또는 s<세션>.json)")
    ap.add_argument("--old", type=Path, default=None, help="견줄 전 내보내기 폴더 (같은 시드 = 같은 원판·은신처인지)")
    ap.add_argument("--layout", type=Path, default=LAYOUT)
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--seed", type=int, default=32000, help="파이썬 세계 시드 (원판·은신처는 시드와 무관 — 확인용 하나)")
    ap.add_argument("--out", type=Path, default=HERE.parent / "disc_check.json")
    a = ap.parse_args(argv)
    sessions = rm.parse_unreal_maps(a.sessions)
    cfg = rm.mirror_cfg(128, rm.eat_steps_of_seconds(5.0), a.config).to_dict()
    maps = rm.load_unreal_obstacles(a.layout, sessions)
    lay = json.loads(a.layout.read_text(encoding="utf-8"))
    lreg = {r["region"]: r for r in lay["regions"]}
    # 거울 설정 하나만 쓸 때의 원판(= 숲 표) — 파일에 적힌 그대로
    raw = yaml.safe_load(a.config.read_text(encoding="utf-8"))
    fixed_yaml = raw["features"]["obstacles"]["fixed"]
    yaml_eq_forest = same(fixed_yaml, lreg["Forest"]["discs"])
    print(f"거울 설정 obstacles.fixed {len(fixed_yaml)} 개 = 숲 표 {len(lreg['Forest']['discs'])} 개: {yaml_eq_forest}")
    rows, ok = [], bool(yaml_eq_forest)
    for u in sessions:
        exp = json.loads(export_path(a.exports, u).read_text(encoding="utf-8"))
        old = json.loads(export_path(a.old, u).read_text(encoding="utf-8")) if a.old else None
        oreg = {r["region"]: r for r in old["regions"]} if old else {}
        layout_tag = f"{lay['version']} {lay['digest']}"
        for er in sorted(exp["regions"], key=lambda r: r["region"]):
            g = er["region"]
            c = copy.deepcopy(cfg)
            c["v2"]["features"]["obstacles"]["fixed"] = maps[(u, g)]
            w = wm.World(Config(c), seeds=[int(a.seed)])
            rm.apply_unreal_map(w, u, g)
            py = np.asarray(w.obstacles, dtype=np.float64)
            py_cov = np.c_[w.cov_c, w.cov_r]
            row = dict(session=u, region=g, unreal_discs=len(er["discs"]), unreal_tree_discs=len(er.get("tree_discs", [])),
                       layout_discs=len(lreg[g]["discs"]), python_discs=int(len(py)), python_shape=list(py.shape),
                       level_discs=int(er.get("level_discs", -1)), imported=bool(er.get("imported")),
                       skipped=int(er.get("tree_skipped_cover", 0)) + int(er.get("tree_skipped_no_ground", 0)) + int(er.get("tree_skipped_no_mesh", 0)),
                       max_relief_cm=float(er.get("tree_max_relief_cm", 0.0)),
                       layout_tag_eq=exp.get("tree_layout") == layout_tag,
                       unreal_eq_layout=same(er["discs"], lreg[g]["discs"]), tree_eq_discs=same(er.get("tree_discs", []), er["discs"]),
                       unreal_eq_python=same(er["discs"], py), covers_bit_eq=same(er["covers"], py_cov),
                       covers_max_diff=float(np.abs(np.asarray(er["covers"], dtype=np.float64).reshape(-1, 3) - py_cov).max()) if len(py_cov) else 0.0,
                       size_eq=float(er["size"]) == float(w.size) == float(lay["stage_size"]))
            row["covers_close"] = len(er["covers"]) == len(py_cov) and row["covers_max_diff"] <= 1e-9
            keys = ["unreal_eq_layout", "tree_eq_discs", "unreal_eq_python", "covers_close", "size_eq", "layout_tag_eq"]
            if old:
                o = oreg[g]
                row["old_eq"] = (same(o["discs"], er["discs"]) and same(o["covers"], er["covers"])
                                 and [float(v) for v in o["origin_cm"]] == [float(v) for v in er["origin_cm"]])
                keys.append("old_eq")
            row["all_ok"] = all(row[k] for k in keys) and not row["imported"] and row["level_discs"] == 0 and row["skipped"] == 0
            ok &= row["all_ok"]
            rows.append(row)
            print(f"s{u} {g:8s}: 원판 언리얼 {row['unreal_discs']} (나무 {row['unreal_tree_discs']} + 레벨 {row['level_discs']}) · 표 {row['layout_discs']} · "
                  f"파이썬 {row['python_discs']} {tuple(py.shape)} | 언리얼=표 {row['unreal_eq_layout']} · 언리얼=파이썬 {row['unreal_eq_python']} · "
                  f"나무=세계 {row['tree_eq_discs']} · 뺀 나무 {row['skipped']} · 밑동 높낮이 {row['max_relief_cm']:.1f} cm · 은신처 비트 {row['covers_bit_eq']} "
                  f"(가장 큰 차이 {row['covers_max_diff']:.1e}) · 한 변 {row['size_eq']} · 표 지문 {row['layout_tag_eq']}"
                  + (f" · 전 내보내기와 같음 {row['old_eq']}" if old else ""))
    print("모두 같음" if ok else "다른 것이 있다")
    rel = (lambda p: str(p.resolve().relative_to(ROOT)) if p.resolve().is_relative_to(ROOT) else str(p))
    a.out.write_text(json.dumps(dict(sessions=sessions, config=rel(a.config), layout=rel(a.layout), exports=rel(a.exports),
                                     old=rel(a.old) if a.old else None, seed=a.seed, yaml_fixed_eq_forest=bool(yaml_eq_forest),
                                     all_ok=bool(ok), rows=rows), ensure_ascii=False, indent=1), encoding="utf-8")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
