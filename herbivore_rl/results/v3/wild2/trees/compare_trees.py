"""무대 나무 확인 (10-17): (1) 언리얼 대 파이썬 짝 비교를 지역마다, (2) 나무가 바꾼 것 — 나무 판 대 나무 없는 기본 판을 파이썬(같은 지도·같은 시드 짝)과
언리얼(세션 3)에서 본다. 칸·식은 ../compare_unreal_wild2.py 그대로(230초 줄).
herbivore_rl/ 에서

    python results/v3/wild2/trees/compare_trees.py \
        --unreal-trees results/v3/wild2/trees/unreal_logs --unreal-base results/v3/wild2/shc/unreal_logs \
        --python-trees results/v3/wild2/runs/pair_d128_trees_u20000-20002_k10.json --python-base results/v3/wild2/runs/pair_d128_shc_u20000-20002_k10.json
    # 두 묶음 합(20000~20002 + 20006~20008): 각 인자에 둘씩 같은 순서로

나무 없는 기본 판 = ../shc(원판 0 장애물 거울 = 10-17 고침 기본값 짝 pair_d128_packfood 와 90 세계 비트 동일, 언리얼도 기본 판 packfood 와 같은 기록 줄).
파이썬 효과: 지도 (세션, 지역) 의 반복 j 는 두 판이 같은 시드·같은 먹이 지도이고 원판만 다르다. 지역 묶음마다 반복 j 의 합으로 칸을 셈하고 차이 d_j = 나무 − 없음,
반복 10 의 평균과 '2 × 표준오차'(= 2 × 표준편차 ÷ √10, 대략 95% 범위)를 적는다. 메마른 땅은 원판 0 이라 두 판이 비트 단위로 같아야 한다(--check-barren).
언리얼 효과: 지도마다 한 판의 합 차이(참고 — 한 지도는 한 판이라 흔들림이 크다). 메마른 땅은 언리얼도 차이 0 이어야 한다.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))

import compare_unreal_wild2 as cu  # noqa: E402

GROUPS = (("지도 모두", None), ("숲(Forest)", "Forest"), ("고지(Highland)", "Highland"), ("메마른 땅(Barren)", "Barren"))


def maps_of(maps, region):
    return [m for m in maps if region is None or m[1] == region]


def sums(d_by_map, maps, keys):
    return {k: sum(d_by_map[m][k] for m in maps) for k in keys}


def effect_metrics(keys):
    out = list(cu.METRICS)
    if set(cu.PACK_KEYS) <= keys:
        out += list(cu.PACK_METRICS)
    return out


def python_effect(title, maps, pt, pb):
    keys = set(cu.KEYS) | (set(cu.PACK_KEYS) if cu.has_pack(maps, {m: pt[m][0] for m in maps}, pt) and
                           cu.has_pack(maps, {m: pb[m][0] for m in maps}, pb) else set())
    reps = min(min(len(pt[m]), len(pb[m])) for m in maps)
    T = [sums({m: pt[m][j] for m in maps}, maps, keys) for j in range(reps)]
    B = [sums({m: pb[m][j] for m in maps}, maps, keys) for j in range(reps)]
    print(f"\n### 파이썬: 나무가 바꾼 것 — {title} (지도 {len(maps)}장, 짝 반복 {reps})\n")
    print("| 칸 | 나무 없음 평균 | 나무 평균 | 차이 평균 ± 2 × 표준오차 | 차이 ÷ 표준오차 |")
    print("|---|---|---|---|---|")
    for name, f, nd in effect_metrics(keys):
        tv = [f(t) for t in T]
        bv = [f(b) for b in B]
        dv = [x - y for x, y in zip(tv, bv)]
        mu, sd, _, _ = cu.stat(dv)
        se = sd / math.sqrt(len(dv)) if math.isfinite(sd) else float("nan")
        tz = mu / se if se and se > 0 else float("nan")
        tzs = f"{tz:+.1f}" if math.isfinite(tz) else "—"
        print(f"| {name} | {cu.stat(bv)[0]:.{nd}f} | {cu.stat(tv)[0]:.{nd}f} | {mu:+.{nd}f} ± {2 * se:.{nd}f} | {tzs} |")


def unreal_effect(title, maps, ut, ub, pt, pb):
    keys = set(cu.KEYS) | (set(cu.PACK_KEYS) if all(set(cu.PACK_KEYS) <= set(ut[m]) and set(cu.PACK_KEYS) <= set(ub[m]) for m in maps) else set())
    T, B = sums(ut, maps, keys), sums(ub, maps, keys)
    reps = min(min(len(pt[m]), len(pb[m])) for m in maps)
    PT = [sums({m: pt[m][j] for m in maps}, maps, keys) for j in range(reps)]
    PB = [sums({m: pb[m][j] for m in maps}, maps, keys) for j in range(reps)]
    print(f"\n### 언리얼: 나무가 바꾼 것 — {title} (지도 {len(maps)}장)\n")
    print("| 칸 | 언리얼 나무 없음 | 언리얼 나무 | 언리얼 차이 | 파이썬 차이 평균 (반복 하나 = 지도 묶음 한 벌) | 파이썬 반복 차이 [최소..최대] |")
    print("|---|---|---|---|---|---|")
    for name, f, nd in effect_metrics(keys):
        dv = [f(a) - f(b) for a, b in zip(PT, PB)]
        mu, _, lo, hi = cu.stat(dv)
        print(f"| {name} | {f(B):.{nd}f} | {f(T):.{nd}f} | {f(T) - f(B):+.{nd}f} | {mu:+.{nd}f} | [{lo:+.{nd}f}..{hi:+.{nd}f}] |")


def common_eq(x, y) -> bool:
    """두 dict 의 같은 칸만 견준다(한쪽 설정에만 있는 칸 — 장애물 ob_*·det_* 등 — 은 뺀다). 같은 칸이 하나도 없으면 다르다고 본다."""
    if isinstance(x, dict) and isinstance(y, dict):
        ks = set(x) & set(y)
        return bool(ks) and all(json.dumps(x[k], sort_keys=True) == json.dumps(y[k], sort_keys=True) for k in ks)
    return json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True)


def barren_bit_equal(py_trees: Path, py_base: Path) -> tuple[int, int]:
    """메마른 땅(원판 0) 세계가 두 판에서 같은지 — 10초 줄 전부(같은 칸)·진단·사냥 메타. (같은 세계 수, 메마른 땅 세계 수).
    나무 없는 판이 장애물 블록 없는 설정(v3_wild2_pack_mirror.yaml)이면 장애물 칸은 한쪽에만 있어 같은 칸만 본다."""
    a = json.loads(py_trees.read_text(encoding="utf-8"))["worlds"]
    b = json.loads(py_base.read_text(encoding="utf-8"))["worlds"]
    key = (lambda w: (w["meta"]["unreal_map"]["seed"], w["meta"]["unreal_map"]["region"], w["meta"]["unreal_map"].get("replicate", 0), w["meta"].get("seed")))
    bb = {key(w): w for w in b}
    same = n = 0
    for w in a:
        if w["meta"]["unreal_map"]["region"] != "Barren":
            continue
        n += 1
        o = bb.get(key(w))
        if o is not None and len(w["rows"]) == len(o["rows"]) and all(common_eq(x, y) for x, y in zip(w["rows"], o["rows"]))                 and common_eq(w["meta"].get("diag"), o["meta"].get("diag")) and common_eq(w["meta"].get("hunt"), o["meta"].get("hunt")):
            same += 1
    return same, n


def unreal_many(folders) -> dict:
    out: dict = {}
    for f in folders:
        d = cu.parse_unreal(f)
        if set(d) & set(out):
            raise SystemExit(f"언리얼 기록 폴더의 지도가 겹친다: {f}")
        out.update(d)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--unreal-trees", type=Path, nargs="+", required=True, help="폴더 여럿이면 합친다(세션 시드가 겹치지 않아야 한다)")
    ap.add_argument("--unreal-base", type=Path, nargs="+", required=True)
    ap.add_argument("--python-trees", type=Path, nargs="+", required=True, help="짝 비교 결과 여럿이면 합친다 (--unreal-trees 와 같은 순서·같은 세션)")
    ap.add_argument("--python-base", type=Path, nargs="+", required=True)
    a = ap.parse_args(argv)
    ut, ub = unreal_many(a.unreal_trees), unreal_many(a.unreal_base)
    pt, pb = cu.parse_python(a.python_trees), cu.parse_python(a.python_base)
    maps = sorted(set(ut) & set(ub) & set(pt) & set(pb))
    if not maps:
        raise SystemExit("네 판에 같은 지도가 없다")
    print("## 1. 언리얼 대 파이썬 (나무 판, 230초 줄)")
    for title, g in GROUPS:
        cu.table(f"나무 — {title}", maps_of(maps, g), ut, pt)
    print("\n## 2. 나무가 바꾼 것")
    same = n = 0
    for x, y in zip(a.python_trees, a.python_base):
        s1, n1 = barren_bit_equal(x, y)
        same, n = same + s1, n + n1
    print(f"\n메마른 땅(원판 0) 파이썬 세계가 나무 없는 판과 같음: {same}/{n} (10초 줄 같은 칸·진단·사냥 메타)")
    for title, g in GROUPS:
        python_effect(title, maps_of(maps, g), pt, pb)
    for title, g in GROUPS:
        unreal_effect(title, maps_of(maps, g), ut, ub, pt, pb)


if __name__ == "__main__":
    main()
