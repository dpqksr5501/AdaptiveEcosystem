"""나무 자리 정밀 탐색 (level_sense/placement, 2026-10-27).

사용자 요청(10-27, 원문): "나무 자리도 어디에 있을때 가장 영향을 끼치는지 잘 찾아봐".
level_sense/sense.py (바탕 스냅숏·변형·실행기·같은 시드 짝 표) 위에서 돈다. sense.py·env_v2·live·adapt·ceval·C++ 는 고치지 않는다. 이 파일은
'자리 띠(zone)' 나무 놓기 하나만 sense.parse_variant·sense.place_trees 를 이 프로세스 안에서 감싸 더한다 (받아들임 규칙은 sense._spot_ok =
AddTrees 규칙 그대로 — 벽 4 m·은신처 둘레 2 m·줄기 사이 3 m, 반지름 40.45 cm × U[1.8, 2.2]). 세계 규칙 검사(sense.check_region)도 그대로 지난다.

    # herbivore_rl/ 에서 (PYTHONUTF8=1). <out> = sense run 의 --out (원자료 — 저장소 밖)
    P=results/v3/level_sense/placement/place.py
    python $P zones --out <out> --base I --region Barren --n 20 --seed 1           # 자리 띠마다 놓일 나무 자리 요약 (돌리지 않음)
    python $P run --out <out> --base I --region Barren [--brain r7e|r1bf] [--world N|G] --variants base zone_d0-5_n20_s1 spot:50:70:8:10 trees:20:rand:1 …
    python $P analyze --out <out> [--final-metric ep_caught]                         # 표·json·그림 -> placement/

자리 띠 변형 이름 zone_<띠>_n<그루>_s<씨> (띠 = ZONES). 같은 띠·씨면 그루 수가 달라도 앞 그루가 같다(n8 ⊂ n20 ⊂ n40 — 난수 흐름이 그루 수와 무관).
띠는 바탕(R7e·N) 공간 지도(sense run --maps, base__maps__R-<지역>)로 정한다 — G 세계·R1b-F 다시 재기에도 같은 자리를 쓴다.
돌리기는 평가기(ceval)·지역 하나(__R-<지역>)·시드 34900~34999 만. 변형 하나가 세계 규칙 검사에 걸리면 그 변형만 건너뛰고 적는다(멈추지 않는다).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
PL = HERE.parent
if str(PL.parent) not in sys.path:
    sys.path.insert(0, str(PL.parent))
import sense  # noqa: E402

UNIT_M = sense.UNIT_M
H = 1800
COMBOS = [("I", "Barren"), ("I", "Forest"), ("J", "Barren"), ("J", "Forest")]
BASE_LABEL = {"I": "통합 맵 s20004", "J": "조연우 맵 s20010"}
REG_LABEL = {"Barren": "메마른 땅", "Forest": "숲"}
GRID_XS = (10, 30, 50, 70, 90, 110)                    # 20 m 격자 중심 (sense scan --grid 20)
GRID_RE = re.compile(r"^spot_(\d+)_(\d+)_8_10$")
TAG_ZONE = 0x5A4F4E45                                  # "ZONE"
HI_Q, LO_Q = 0.8, 0.4
ZONE_TRIES = 20000
ZONES = {
    "d0-5": dict(kind="band", lo=0.0, hi=5.0, label="은신처 가장자리 0~5 m (문 앞)"),
    "d5-10": dict(kind="band", lo=5.0, hi=10.0, label="은신처 가장자리 5~10 m"),
    "d10-20": dict(kind="band", lo=10.0, hi=20.0, label="은신처 가장자리 10~20 m"),
    "d20-40": dict(kind="band", lo=20.0, hi=40.0, label="은신처 가장자리 20~40 m (은신처에서 먼 곳)"),
    "flee_hi": dict(kind="hi", map="flee", label="도망 길이 많이 지나는 곳 (위 20% 셀)"),
    "flee_lo": dict(kind="lo", map="flee", label="도망 길이 적게 지나는 곳 (아래 40% 셀)"),
    "spotd_hi": dict(kind="hi", map="spot_deer", label="늑대가 사슴을 고른 때 사슴 자리 (위 20%)"),
    "spotw_hi": dict(kind="hi", map="spot_wolf", label="늑대가 사슴을 고른 때 늑대 자리 (위 20%)"),
    "rest_hi": dict(kind="hi", map="wolf_sleep", label="늑대 쉬는 곳 (위 20%)"),
    "graze_hi": dict(kind="hi", map="graze", label="사슴 먹는 곳 한가운데 (위 20%)"),
    "edge": dict(kind="edge", label="가장자리 (벽 16 m 안 · 은신처에서 16 m 밖)"),
}
ZRE = re.compile(r"^zone_(.+)_n(\d+)_s(\d+)$")
CTX: dict = {"maps": {}}                               # region_index -> 바탕 공간 지도 (자리 띠 고르기)

# (칸, 쉬운 이름, 사슴에게 좋은 쪽: +1 = 늘면 좋음, -1 = 줄면 좋음, 0 = 좋고 나쁨이 없음)
METRICS = [
    ("ep_caught", "쫓긴 사건 가운데 잡힘", -1),
    ("fl_obstacle_of_chased", "줄기에 가려 늑대가 놓친 도망 몫", +1),
    ("ep_hide", "사건 숨음 비율 (은신처로 끝남)", 0),
    ("hunt_success", "늑대 사냥 성공률", -1),
    ("ep_chased_n", "쫓긴 사건 수 (시드당)", -1),
    ("beh_graze", "먹기 몫", +1),
    ("fl_start_1k", "도망 시작 /1000 사슴-스텝", 0),
]
EXTRA = ["caught", "ep_saved", "fl_cover_of_chased", "fl_own_of_chased", "flee_share", "in_shelter", "hunt_starts_n", "ep_hidden_n"]
ALL_M = [m for m, _, _ in METRICS] + EXTRA
MLAB = {m: l for m, l, _ in METRICS}
GOOD = {m: g for m, _, g in METRICS}
FEATURE_MAPS = ["flee", "chased_flee", "spot_deer", "spot_wolf", "onset", "lost", "caught", "graze", "wolf_sleep", "wolf_idle", "wolf_hunt",
                "enter_fled", "deer"]
NEAR_M = 6.0                                           # 나무 둘레 6 m 안 셀의 지도 몫 = '그 활동이 새 나무 곁을 지나는 몫'
T_STRONG = 3.2                                         # 셀 36 개 × 칸 7 개를 보면 |t| 2 쯤은 우연히 몇 개 나온다 — 우연으로 보기 어려운 선 (Bonferroni 어림)


def scale(m: str) -> float:
    return 100.0 if m in sense.PCT else 1.0


def unit(m: str) -> str:
    return "%p" if m in sense.PCT else ""


# --------------------------------------------------------------------- #
# 자리 띠 (sense 감싸기 — 이 프로세스 안에서만)
# --------------------------------------------------------------------- #

_orig_parse = sense.parse_variant
_orig_place = sense.place_trees


def parse_variant(name: str) -> dict:
    m = ZRE.match(name)
    if not m:
        return _orig_parse(name)
    z, n, s = m.group(1), int(m.group(2)), int(m.group(3))
    if z not in ZONES or n < 1:
        raise SystemExit(f"자리 띠 {z!r} 를 모른다 ({', '.join(ZONES)})")
    return dict(name=name, spec=f"zone:{z}:{n}:{s}", edits=[dict(kind="trees", place=f"zone:{z}", n=n, seed=s)], python_only=False)


def _geom(M: dict, covers, size: float):
    g, c = int(M["g"]), float(M["cell"])
    iy, ix = np.mgrid[0:g, 0:g]
    cx, cy = (ix + 0.5) * c, (iy + 0.5) * c
    cov = np.asarray([list(map(float, v)) for v in covers if float(v[2]) > 0.0], dtype=np.float64).reshape(-1, 3)
    de = (np.hypot(cx[..., None] - cov[:, 0], cy[..., None] - cov[:, 1]) - cov[:, 2]).min(-1)
    wall = np.minimum.reduce([cx, cy, size - cx, size - cy])
    return g, c, cx, cy, cov, de, wall


def zone_weights(zone: str, M: dict, covers, size: float):
    """띠 셀 무게 (g, g) [iy, ix] + 점 검사 함수 + 요약. 띠(band·edge)는 셀 중심을 반 셀 넓혀 고르고 점마다 정확히 검사한다."""
    R = sense.tree_rules()
    g, c, cx, cy, cov, de, wall = _geom(M, covers, size)
    ok = (de >= R["clear"]) & (wall >= R["wall"])
    Z = ZONES[zone]
    half = c * math.sqrt(0.5)
    info: dict = dict(zone=zone, label=Z["label"])

    def edge_d(x, y):
        return float((np.hypot(x - cov[:, 0], y - cov[:, 1]) - cov[:, 2]).min())

    if Z["kind"] == "band":
        lo, hi = Z["lo"] / UNIT_M, Z["hi"] / UNIT_M
        w = ((de >= lo - half) & (de < hi + half) & (de >= R["clear"] - half) & (wall >= R["wall"] - half)).astype(float)

        def check(x, y):
            return lo <= edge_d(x, y) < hi
    elif Z["kind"] == "edge":
        w = ((wall <= sense.EDGE_BAND + half) & (de >= sense.EDGE_FAR - half) & (wall >= R["wall"] - half)).astype(float)

        def check(x, y):
            return min(x, y, size - x, size - y) <= sense.EDGE_BAND and edge_d(x, y) >= sense.EDGE_FAR
    else:
        V = sense.map_values(M, Z["map"], "all")
        vals = V[ok]
        if Z["kind"] == "hi":
            pos = vals[vals > 0]
            q = float(np.quantile(pos, HI_Q)) if len(pos) else math.inf
            w = np.where(ok & (V >= q) & (V > 0), V, 0.0)
        else:
            q = float(np.quantile(vals, LO_Q))
            w = (ok & (V <= q)).astype(float)
        info.update(map=Z["map"], q=q, map_share=float(V[w > 0].sum() / max(V.sum(), 1e-12)))

        def check(x, y):
            return True
    if not w.sum() > 0:
        raise SystemExit(f"자리 띠 {zone}: 고를 셀이 없다")
    info.update(cells=int((w > 0).sum()), area_m2=float((w > 0).sum() * (c * UNIT_M) ** 2))
    return w, check, info


def place_zone(zone: str, n: int, size: float, covers, avoid, seed: int, region_index: int) -> tuple[list, dict]:
    M = CTX["maps"].get(int(region_index))
    if M is None:
        raise SystemExit(f"자리 띠 {zone}: 지역 {region_index} 의 바탕 공간 지도가 없다 (run --maps 먼저)")
    pm = sense._pm()
    R = sense.tree_rules()
    w, check, info = zone_weights(zone, M, covers, size)
    g, c = int(M["g"]), float(M["cell"])
    p = (w / w.sum()).ravel()
    rng = np.random.default_rng([TAG_ZONE, int(seed), int(region_index) + 1, zlib.crc32(zone.encode())])
    cov = [list(map(float, v)) for v in covers if float(v[2]) > 0.0]
    placed = [list(map(float, d)) for d in avoid]
    out: list = []
    miss = 0
    for _k in range(int(n)):
        for _t in range(ZONE_TRIES):
            j = int(rng.choice(g * g, p=p))
            iy, ix = divmod(j, g)
            x, y = (ix + rng.uniform()) * c, (iy + rng.uniform()) * c
            r = float(pm.TRUNK_R_MESH_CM * rng.uniform(pm.SCALE_LO, pm.SCALE_HI) / pm.UNIT_CM)
            if check(x, y) and sense._spot_ok(x, y, r, size, cov, placed, R):
                out.append([float(x), float(y), r])
                placed.append([float(x), float(y), r])
                break
        else:
            miss += 1
    meta = dict(place=f"zone:{zone}", n_req=int(n), n_placed=len(out), unplaced=int(miss), **info)
    return out, meta


def place_trees(place, n, size, covers, avoid, cap, cell, seed, region_index, center=None, radius=None):
    if str(place).startswith("zone:"):
        return place_zone(str(place)[5:], int(n), float(size), covers, avoid, int(seed), int(region_index))
    return _orig_place(place, n, size, covers, avoid, cap, cell, seed, region_index, center=center, radius=radius)


sense.parse_variant = parse_variant
sense.place_trees = place_trees


def combo_dir(out, base: str, brain: str = "r7e", world: str = "N") -> Path:
    return sense.run_dir(Path(out), base, brain, world, H)


def load_ctx(out, base: str, region: str) -> dict:
    M = sense.load_maps(combo_dir(out, base), "base", region)
    CTX["maps"][int(M["region_index"])] = M
    return M


# --------------------------------------------------------------------- #
# 명령: zones · run
# --------------------------------------------------------------------- #


def _stage(a):
    info = sense.prepare(a.base, "r7e", Path(a.out) / "prep")
    j0 = next(it[2] for it in sense._live().eval_items(info, "cur", info["model"], [sense.SEED_BOX[0]], 1, "N", "multi", [1])
              if it[2]["region"] == a.region)
    w0 = sense._region_world(j0["cfg"], sense.SEED_BOX[0])
    covers = np.c_[w0.cov_c, w0.cov_r].tolist()
    discs = [list(map(float, x)) for x in (j0["cfg"]["v2"]["features"]["obstacles"].get("fixed") or [])]
    return info, float(w0.size), covers, discs


def cmd_zones(a) -> int:
    M = load_ctx(a.out, a.base, a.region)
    info, size, covers, discs = _stage(a)
    ri = int(info["regions"][a.region]["region_index"])
    for z in ZONES:
        new, meta = place_zone(z, a.n, size, covers, discs, a.seed, ri)
        sm = sense.tree_summary(new, covers, [0.0] * int(M["g"]) ** 2, float(M["cell"]), size)
        print(f"{z:9s} {meta['n_placed']}/{meta['n_req']} 그루 · 셀 {meta['cells']} ({meta['area_m2']:.0f} m²)"
              + (f" · 지도 몫 {meta['map_share'] * 100:.0f}%" if "map_share" in meta else "")
              + (f" · 은신처 가장자리 평균 {sm['shelter_edge_m']['mean']:.1f} m · 벽 평균 {sm['wall_m']['mean']:.1f} m" if new else "") + f" — {meta['label']}")
    return 0


def cmd_run(a) -> int:
    if any(ZRE.match(v) for v in a.variants):
        load_ctx(a.out, a.base, a.region)
    ns = argparse.Namespace(seeds=a.seeds, horizon=H, workers=a.workers, out=a.out, base=a.base, brain=a.brain, world=a.world, runner="ceval",
                            region=a.region, regions=[a.region], maps=False, force=False, stuck=0, stuck_horizon=3600)
    if ns.workers > 6:
        raise SystemExit("워커는 6 이하")
    bad = []
    t0 = time.perf_counter()
    for v in a.variants:
        try:
            sense.run_variants(ns, [v])
        except SystemExit as e:                                    # 세계 규칙 검사 등 — 그 변형만 건너뛴다
            print(f"[{v}] 건너뜀: {e}", flush=True)
            bad.append(dict(variant=v, why=str(e)))
    d = combo_dir(a.out, a.base, a.brain, a.world)
    if bad:
        p = d / "place_skipped.json"
        old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        p.write_text(json.dumps(old + [dict(b, region=a.region) for b in bad], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"끝: 변형 {len(a.variants)} (건너뜀 {len(bad)}) {time.perf_counter() - t0:.0f} 초", flush=True)
    return 0


# --------------------------------------------------------------------- #
# 분석
# --------------------------------------------------------------------- #

_SV: dict = {}


def load_sv(d: Path, variant: str, region: str):
    k = (str(d), sense.safe_name(variant), region)
    if k not in _SV:
        V = sense.load_raw(d, sense.safe_name(variant), "ceval", [region])
        sv = sense.seed_values(V["worlds"], int(V["meta"]["horizon"]), [region], False)
        vr = (V["meta"].get("variant_regions") or {}).get(region) or {}
        _SV[k] = (sv, dict(new_trees=vr.get("new_trees", []), place=vr.get("place", []), spec=V["meta"]["spec"]))
    return _SV[k]


def has_raw(d: Path, variant: str, region: str) -> bool:
    try:
        load_sv(d, variant, region)
        return True
    except SystemExit:
        return False


def _ratio(sv: dict, seeds) -> np.ndarray:
    return np.array([sv[s][0] / sv[s][1] for s in seeds])


def pooled(ref: dict, vars_: list, seeds=None) -> dict | None:
    """같은 시드 짝: 시드마다 (변형들 평균 − 바탕). vars_ = 같은 자리 종류의 여러 놓기(씨). 반환 diff·sd·t·n·짝/홀 시드 diff·놓기마다 diff."""
    ss = sorted(s for s in ref if ref[s][1] > 0 and all(s in v and v[s][1] > 0 for v in vars_))
    if seeds is not None:
        ss = [s for s in ss if s in seeds]
    if len(ss) < 4:
        return None
    a = _ratio(ref, ss)
    each = np.array([_ratio(v, ss) for v in vars_])
    dd = each.mean(0) - a
    n = len(dd)
    sd = float(dd.std(ddof=1))
    m = float(dd.mean())
    ev = np.array([s % 2 == 0 for s in ss])
    return dict(ref=float(a.mean()), var=float(each.mean()), diff=m, sd=sd, se=sd / math.sqrt(n), t=(m / (sd / math.sqrt(n)) if sd > 0 else 0.0), n=n,
                diff_even=float(dd[ev].mean()) if ev.any() else math.nan, diff_odd=float(dd[~ev].mean()) if (~ev).any() else math.nan,
                each=[float((e - a).mean()) for e in each])


def _rank(x):
    x = np.asarray(x, dtype=float)
    o = np.argsort(x, kind="mergesort")
    r = np.empty(len(x))
    r[o] = np.arange(len(x))
    for v in np.unique(x):                      # 같은 값은 평균 순위
        k = x == v
        if k.sum() > 1:
            r[k] = r[k].mean()
    return r


def spearman(x, y) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5 or np.std(x[ok]) == 0 or np.std(y[ok]) == 0:
        return math.nan
    return float(np.corrcoef(_rank(x[ok]), _rank(y[ok]))[0, 1])


def tree_features(M: dict, trees: list, covers=None) -> dict:
    """새 나무 자리 특징: 은신처 가장자리·벽까지 평균 m, 그리고 지도마다 '나무 둘레 6 m 안 셀의 몫'(그 활동이 새 나무 곁을 지나는 몫)."""
    size = float(M["size"])
    cov = covers if covers is not None else M.get("covers") or []
    g, c, cx, cy, cova, de, wall = _geom(M, cov, size)
    a = np.asarray(trees, dtype=float).reshape(-1, 3)
    if not len(a):
        return {}
    dts = (np.hypot(a[:, None, 0] - cova[None, :, 0], a[:, None, 1] - cova[None, :, 1]) - cova[None, :, 2]).min(1)
    out = dict(door_m=float(dts.mean() * UNIT_M), wall_m=float(np.minimum.reduce([a[:, 0], a[:, 1], size - a[:, 0], size - a[:, 1]]).mean() * UNIT_M))
    near = np.zeros((g, g), dtype=bool)
    for t in a:
        near |= np.hypot(cx - t[0], cy - t[1]) <= NEAR_M / UNIT_M
    for nm in FEATURE_MAPS:
        V = sense.map_values(M, nm, "all")
        out[f"near_{nm}"] = float(V[near].sum() / max(V.sum(), 1e-12))
    return out


FEAT_LAB = dict(door_m="은신처 가장자리까지 거리", wall_m="벽까지 거리", near_flee="곁을 지나는 도망 길 몫", near_chased_flee="곁을 지나는 쫓기는 도망 길 몫",
                near_spot_deer="곁의 '늑대가 사슴을 고른' 사슴 자리 몫", near_spot_wolf="곁의 '사슴을 고른' 늑대 자리 몫",
                near_onset="곁의 '사슴이 알아챈' 자리 몫", near_lost="곁의 '늑대가 표적을 놓친' 자리 몫", near_caught="곁의 잡힌 자리 몫",
                near_graze="곁의 먹는 자리 몫", near_wolf_sleep="곁의 늑대 쉬는 자리 몫", near_wolf_idle="곁의 늑대 기다리는 자리 몫",
                near_wolf_hunt="곁의 늑대 사냥 길 몫", near_enter_fled="곁의 도망 끝 은신처 문 몫", near_deer="곁의 사슴 머문 자리 몫")


def grid_cells(out, base: str, region: str, brain: str = "r7e", world: str = "N", M: dict | None = None) -> list:
    d = combo_dir(out, base, brain, world)
    if not d.exists() or not has_raw(d, "base", region):
        return []
    ref, _ = load_sv(d, "base", region)
    cells = []
    for v in sense.variants_in(d, "spot_*"):
        m = GRID_RE.match(v)
        if not m or int(m.group(1)) not in GRID_XS or int(m.group(2)) not in GRID_XS or not has_raw(d, v, region):
            continue
        sv, meta = load_sv(d, v, region)
        row = dict(variant=v, x=int(m.group(1)), y=int(m.group(2)), n_placed=len(meta["new_trees"]), m={})
        for k in ALL_M:
            if k in ref and k in sv:
                p = pooled(ref[k], [sv[k]])
                if p:
                    row["m"][k] = p
        if M is not None:
            row["feat"] = tree_features(M, meta["new_trees"])
        cells.append(row)
    return cells


def grid_summary(cells: list) -> dict:
    out = {}
    K = len(cells)
    for k in ALL_M:
        xs = [c["m"][k] for c in cells if k in c["m"]]
        if not xs:
            continue
        ev = np.array([x["diff_even"] for x in xs])
        od = np.array([x["diff_odd"] for x in xs])
        t = np.array([x["t"] for x in xs])
        r = float(np.corrcoef(ev, od)[0, 1]) if ev.std() > 0 and od.std() > 0 else math.nan
        out[k] = dict(cells=len(xs), half_r=r, n_t2=int((np.abs(t) >= 2).sum()), n_t32=int((np.abs(t) >= T_STRONG).sum()),
                      expect_t2=round(0.048 * len(xs), 1), max_abs_t=float(np.abs(t).max()), mean_diff=float(np.mean([x["diff"] for x in xs])),
                      sd_cells=float(np.std([x["diff"] for x in xs], ddof=1)) if len(xs) > 1 else math.nan,
                      se_cell=float(np.median([x["se"] for x in xs])))
    out["_K"] = K
    return out


def feature_corr(cells: list) -> dict:
    """셀 차이 ↔ 나무 자리 특징 순위 맞음 (Spearman ρ, 셀마다 한 점)."""
    if not cells or "feat" not in cells[0]:
        return {}
    feats = list(cells[0]["feat"])
    out = {}
    for k in [m for m, _, _ in METRICS] + ["caught"]:
        y = [c["m"][k]["diff"] if k in c["m"] else math.nan for c in cells]
        out[k] = {f: spearman([c["feat"].get(f, math.nan) for c in cells], y) for f in feats}
    return out


def zone_table(out, base: str, region: str, n: int = 20, seeds=(1, 2), brain: str = "r7e", world: str = "N", zones=None) -> dict:
    d = combo_dir(out, base, brain, world)
    if not d.exists() or not has_raw(d, "base", region):
        return {}
    ref, _ = load_sv(d, "base", region)
    res = {}
    for z in (zones or ZONES):
        vs = [f"zone_{z}_n{n}_s{s}" for s in seeds]
        vs = [v for v in vs if has_raw(d, v, region)]
        if not vs:
            continue
        svs = [load_sv(d, v, region) for v in vs]
        row = dict(zone=z, label=ZONES[z]["label"], variants=vs, n_placed=[len(m["new_trees"]) for _, m in svs], m={})
        for k in ALL_M:
            if k in ref and all(k in s for s, _ in svs):
                p = pooled(ref[k], [s[k] for s, _ in svs])
                if p:
                    row["m"][k] = p
        res[z] = row
    return res


def rand_table(out, base: str, region: str, ns=(8, 20, 40), seeds=(1, 2), brain: str = "r7e", world: str = "N", kind: str = "rand") -> dict:
    """같은 수 비교: kind = rand (trees:<n>:rand:<씨>) 또는 자리 띠 이름."""
    d = combo_dir(out, base, brain, world)
    if not d.exists() or not has_raw(d, "base", region):
        return {}
    ref, _ = load_sv(d, "base", region)
    res = {}
    for n in ns:
        vs = [f"trees:{n}:rand:{s}" if kind == "rand" else f"zone_{kind}_n{n}_s{s}" for s in seeds]
        vs = [v for v in vs if has_raw(d, v, region)]
        if not vs:
            continue
        svs = [load_sv(d, v, region) for v in vs]
        row = dict(kind=kind, n=n, variants=[sense.safe_name(v) for v in vs], n_placed=[len(m["new_trees"]) for _, m in svs], m={})
        for k in ALL_M:
            if k in ref and all(k in s for s, _ in svs):
                p = pooled(ref[k], [s[k] for s, _ in svs])
                if p:
                    row["m"][k] = p
        res[n] = row
    return res


def variant_rows(out, base: str, region: str, variants: list, brain: str, world: str) -> dict:
    d = combo_dir(out, base, brain, world)
    if not d.exists() or not has_raw(d, "base", region):
        return {}
    ref, _ = load_sv(d, "base", region)
    res = {}
    for v in variants:
        if not has_raw(d, v, region):
            continue
        sv, meta = load_sv(d, v, region)
        res[sense.safe_name(v)] = dict(spec=meta["spec"], n_placed=len(meta["new_trees"]),
                                       m={k: p for k in ALL_M if k in ref and k in sv for p in [pooled(ref[k], [sv[k]])] if p})
    return res


# --------------------------------------------------------------------- #
# 그림
# --------------------------------------------------------------------- #

BLUE, RED, MID = "#2a78d6", "#c63b32", "#f0efec"
COMBO_COL = {("I", "Barren"): "#2a78d6", ("I", "Forest"): "#eb6834", ("J", "Barren"): "#1baf7a", ("J", "Forest"): "#eda100"}


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": ["Malgun Gothic", "DejaVu Sans"], "axes.unicode_minus": False, "font.size": 9,
                         "axes.edgecolor": "#888888", "axes.linewidth": 0.6})
    return plt


def _div_cmap():
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list("good_bad", [RED, MID, BLUE])


def _seq_cmap():
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list("seq_blue", ["#ffffff", "#cfe0f6", "#7fb0ea", BLUE, "#0d3a78"])


def _draw_stage(ax, M: dict, discs: bool = True, color: str = "#222222"):
    from matplotlib.patches import Circle

    S = float(M["size"]) * UNIT_M
    for cv in M.get("covers") or []:
        ax.add_patch(Circle((cv[0] * UNIT_M, cv[1] * UNIT_M), cv[2] * UNIT_M, fill=False, ec=color, lw=1.0, ls="--"))
    if discs and M.get("discs"):
        a = np.asarray(M["discs"], dtype=float)
        a = a[(a[:, 0] >= 0) & (a[:, 1] >= 0)]
        ax.scatter(a[:, 0] * UNIT_M, a[:, 1] * UNIT_M, s=6, c="#2b7a2b", marker="o", lw=0)
    ax.set_xlim(0, S)
    ax.set_ylim(0, S)
    ax.set_aspect("equal")
    ax.set_xticks([0, 30, 60, 90, 120])
    ax.set_yticks([0, 30, 60, 90, 120])
    ax.tick_params(labelsize=7, length=2)


MAP_SHOW = [("flee", "사슴 도망 길 (달리는 사슴)"), ("chased_flee", "쫓기는 도망 길"), ("spot_deer", "늑대가 사슴을 고른 곳 (처음 본 곳 어림)"),
            ("onset", "사슴이 위협을 알아채 달리기 시작한 곳"), ("caught", "잡힌 곳"), ("graze", "사슴이 먹는 곳"), ("wolf_sleep", "늑대 쉬는 곳"),
            ("enter_fled", "달려 들어간 은신처 문")]


def fig_maps(M: dict, title: str, path: Path) -> dict:
    plt = _plt()
    from matplotlib.colors import PowerNorm

    fig, axs = plt.subplots(2, 4, figsize=(14, 7.6))
    S = float(M["size"]) * UNIT_M
    half = {}
    for ax, (nm, lab) in zip(axs.ravel(), MAP_SHOW):
        V = sense.map_values(M, nm, "all")
        tot = max(V.sum(), 1e-12)
        e, o = sense.map_values(M, nm, "even").ravel(), sense.map_values(M, nm, "odd").ravel()
        rr = float(np.corrcoef(e, o)[0, 1]) if e.std() > 0 and o.std() > 0 else math.nan
        half[nm] = rr
        im = ax.imshow(V / tot * 100, origin="lower", extent=[0, S, 0, S], cmap=_seq_cmap(), norm=PowerNorm(0.5, vmin=0), interpolation="nearest")
        _draw_stage(ax, M)
        ax.set_title(f"{lab}\n합 {V.sum():.0f} · 짝/홀 시드 지도 맞음 r {rr:.2f}", fontsize=8.5)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cb.ax.tick_params(labelsize=6)
        cb.set_label("셀 몫 %", fontsize=6)
    fig.suptitle(title, fontsize=11)
    fig.text(0.5, 0.01, "점선 원 = 은신처(반지름 12 m), 초록 점 = 있던 줄기. 셀 4 m. 색 = 그 지도 전체에서 그 셀이 차지하는 몫(제곱근 눈금).", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(path, dpi=72)
    plt.close(fig)
    return half


def fig_grid(cells: list, summ: dict, M: dict, title: str, path: Path, metrics=None) -> None:
    plt = _plt()
    metrics = metrics or [m for m, _, _ in METRICS]
    fig, axs = plt.subplots(2, 4, figsize=(15, 8))
    S = float(M["size"]) * UNIT_M
    for ax, k in zip(axs.ravel(), metrics):
        G = np.full((6, 6), np.nan)
        T = np.full((6, 6), np.nan)
        for c in cells:
            if k in c["m"]:
                ix, iy = GRID_XS.index(c["x"]), GRID_XS.index(c["y"])
                G[iy, ix] = c["m"][k]["diff"] * scale(k)
                T[iy, ix] = c["m"][k]["t"]
        good = GOOD.get(k, 0)
        lim = np.nanmax(np.abs(G)) if np.isfinite(G).any() else 1.0
        lim = lim if lim > 0 else 1.0
        if good == 0:
            im = ax.imshow(G, origin="lower", extent=[0, S, 0, S], cmap="PuOr_r", vmin=-lim, vmax=lim, interpolation="nearest")
        else:
            im = ax.imshow(G * good, origin="lower", extent=[0, S, 0, S], cmap=_div_cmap(), vmin=-lim, vmax=lim, interpolation="nearest")
        for iy in range(6):
            for ix in range(6):
                if np.isfinite(G[iy, ix]):
                    t = abs(T[iy, ix])
                    ax.text(GRID_XS[ix], GRID_XS[iy], f"{G[iy, ix]:+.{1 if lim >= 2 else 2}f}" + ("*" if t >= T_STRONG else ""), ha="center", va="center",
                            fontsize=7.5 if t >= 2 else 6.5, fontweight="bold" if t >= 2 else "normal", color="#111111" if t >= 2 else "#777777")
        _draw_stage(ax, M, discs=True)
        s = summ.get(k, {})
        ax.set_title(f"{MLAB.get(k, k)} ({unit(k) or '수'})\n짝/홀 시드 지도 맞음 r {s.get('half_r', math.nan):.2f} · |t|≥2 셀 {s.get('n_t2', 0)} "
                     f"(우연 기대 {s.get('expect_t2', 0)})", fontsize=8)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cb.ax.tick_params(labelsize=6)
        cb.set_label("파랑 = 사슴에 좋음 · 빨강 = 나쁨" if good else "보라 = 줄어듦 · 주황 = 늘어남", fontsize=6)
    ax = axs.ravel()[-1]
    V = sense.map_values(M, "chased_flee", "all")
    from matplotlib.colors import PowerNorm

    ax.imshow(V / max(V.sum(), 1) * 100, origin="lower", extent=[0, S, 0, S], cmap=_seq_cmap(), norm=PowerNorm(0.5, vmin=0), interpolation="nearest")
    _draw_stage(ax, M)
    for c in cells:
        ax.plot(c["x"], c["y"], "+", color="#c63b32", ms=5)
    ax.set_title("참고: 바탕의 쫓기는 도망 길 + 격자 점(+)", fontsize=8)
    fig.suptitle(title, fontsize=11)
    fig.text(0.5, 0.01, f"칸 값 = 그 자리에 작은 숲(8 그루·반지름 10 m)을 놓았을 때 바탕 대비 차이 (같은 시드 100 짝). 굵은 글씨 = |t|≥2, * = |t|≥{T_STRONG} "
             "(셀이 많아 |t|≥2 몇 개는 우연히 나온다). 빈 칸 = 은신처 안이라 못 놓음.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(path, dpi=72)
    plt.close(fig)


def fig_bars(groups: dict, order: list, labels: dict, title: str, path: Path, metrics=None) -> None:
    """groups = {(바탕, 지역): {열쇠: row(m)}} → 칸마다 묶음 막대 (± 1.96 se)."""
    plt = _plt()
    metrics = metrics or ["ep_caught", "fl_obstacle_of_chased", "hunt_success", "ep_hide", "ep_chased_n", "beh_graze"]
    fig, axs = plt.subplots(len(metrics), 1, figsize=(12, 2.3 * len(metrics)), sharex=True)
    combos = [c for c in COMBOS if c in groups and groups[c]]
    wbar = 0.8 / max(len(combos), 1)
    x = np.arange(len(order))
    for ax, k in zip(np.atleast_1d(axs), metrics):
        for j, cb in enumerate(combos):
            vals = [groups[cb].get(o, {}).get("m", {}).get(k) for o in order]
            y = np.array([v["diff"] * scale(k) if v else np.nan for v in vals])
            e = np.array([1.96 * v["se"] * scale(k) if v else np.nan for v in vals])
            ax.bar(x + (j - (len(combos) - 1) / 2) * wbar, y, wbar * 0.92, yerr=e, color=COMBO_COL[cb], ecolor="#555555", capsize=1.5,
                   error_kw=dict(lw=0.6), label=f"{BASE_LABEL[cb[0]]} · {REG_LABEL[cb[1]]}")
        ax.axhline(0, color="#444444", lw=0.6)
        g = GOOD.get(k, 0)
        ax.set_ylabel(f"{MLAB.get(k, k)}\n차이 {unit(k) or '수'}" + ("\n(아래가 사슴에 좋음)" if g < 0 else "\n(위가 사슴에 좋음)" if g > 0 else ""), fontsize=7.5)
        ax.grid(axis="y", color="#e5e5e5", lw=0.5)
        ax.set_axisbelow(True)
    np.atleast_1d(axs)[0].legend(fontsize=7, ncol=4, loc="upper left", frameon=False)
    np.atleast_1d(axs)[-1].set_xticks(x)
    np.atleast_1d(axs)[-1].set_xticklabels([labels.get(o, str(o)) for o in order], fontsize=7.5, rotation=0)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=72)
    plt.close(fig)


def _grid_arr(cells: list, k: str):
    G = np.full((6, 6), np.nan)
    T = np.full((6, 6), np.nan)
    for c in cells:
        if k in c["m"]:
            ix, iy = GRID_XS.index(c["x"]), GRID_XS.index(c["y"])
            G[iy, ix] = c["m"][k]["diff"] * scale(k)
            T[iy, ix] = c["m"][k]["t"]
    return G, T


def fig_summary(grid_by: dict, zone_groups: dict, maps_by: dict, path: Path, zone_order: list) -> None:
    """한 장: 위 두 줄 = 네 바탕·지역의 작은 숲 격자 지도 (늑대가 놓친 도망 몫 · 쫓긴 사건 가운데 잡힘), 아래 = 자리 띠 20 그루 막대 두 칸."""
    plt = _plt()
    from matplotlib.gridspec import GridSpec

    fig = plt.figure(figsize=(16, 13.6))
    gs = GridSpec(3, 4, figure=fig, height_ratios=[1, 1, 1.15], hspace=0.42, wspace=0.18)
    for row, k in enumerate(["fl_obstacle_of_chased", "ep_caught"]):
        lim = max([np.nanmax(np.abs(_grid_arr(c, k)[0])) for c in grid_by.values() if c] + [0.1])
        im = None
        for j, cb in enumerate(COMBOS):
            ax = fig.add_subplot(gs[row, j])
            cells, M = grid_by.get(cb), maps_by.get(cb)
            if not cells or M is None:
                ax.axis("off")
                continue
            G, T = _grid_arr(cells, k)
            S = float(M["size"]) * UNIT_M
            im = ax.imshow(G * GOOD[k], origin="lower", extent=[0, S, 0, S], cmap=_div_cmap(), vmin=-lim, vmax=lim, interpolation="nearest")
            for iy in range(6):
                for ix in range(6):
                    if np.isfinite(G[iy, ix]):
                        t = abs(T[iy, ix])
                        ax.text(GRID_XS[ix], GRID_XS[iy], f"{G[iy, ix]:+.1f}", ha="center", va="center", fontsize=7.5 if t >= 2 else 6.5,
                                fontweight="bold" if t >= 2 else "normal", color="#111111" if t >= 2 else "#808080")
            _draw_stage(ax, M)
            hr = grid_summary(cells).get(k, {}).get("half_r", math.nan)
            ax.set_title(f"{BASE_LABEL[cb[0]]} · {REG_LABEL[cb[1]]}\n{SHORT_M[k]} %p · 짝/홀 맞음 r {hr:.2f}", fontsize=8.5)
        if im is not None:
            cb_ = fig.colorbar(im, ax=[fig.axes[-1]], fraction=0.046, pad=0.02)
            cb_.ax.tick_params(labelsize=6)
            cb_.set_label("파랑 = 사슴에 좋음", fontsize=7)
    combos = [c for c in COMBOS if c in zone_groups]
    wbar = 0.8 / max(len(combos), 1)
    for col, k in enumerate(["fl_obstacle_of_chased", "ep_hide"]):
        ax = fig.add_subplot(gs[2, 2 * col: 2 * col + 2])
        x = np.arange(len(zone_order))
        for j, cb in enumerate(combos):
            vals = [zone_groups[cb].get(o, {}).get("m", {}).get(k) for o in zone_order]
            y = np.array([v["diff"] * scale(k) if v else np.nan for v in vals])
            e = np.array([1.96 * v["se"] * scale(k) if v else np.nan for v in vals])
            ax.bar(x + (j - (len(combos) - 1) / 2) * wbar, y, wbar * 0.92, yerr=e, color=COMBO_COL[cb], ecolor="#555555", capsize=1.2,
                   error_kw=dict(lw=0.5), label=f"{BASE_LABEL[cb[0]]} · {REG_LABEL[cb[1]]}")
        ax.axhline(0, color="#444444", lw=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels([ZLAB_SHORT.get(o, o) for o in zone_order], fontsize=6.8, rotation=0)
        ax.grid(axis="y", color="#e5e5e5", lw=0.5)
        ax.set_axisbelow(True)
        ax.set_title(f"띠마다 20 그루 — {SHORT_M.get(k, MLAB[k])} 차이 %p " + ("(위 = 늑대가 더 놓침)" if k == "fl_obstacle_of_chased" else "(아래 = 은신처로 끝난 쫓김이 줄어듦)"),
                     fontsize=9)
        if col == 0:
            ax.legend(fontsize=7, ncol=2, loc="upper right", frameon=False)
    fig.suptitle("나무가 어디에 있을 때 사슴 행동이 바뀌나 — R7e · N 세계 · 같은 시드 100 짝 (위 두 줄: 그 칸에 작은 숲 8 그루, 아래: 띠 안 20 그루)", fontsize=11.5)
    fig.text(0.5, 0.005, "점선 원 = 은신처. 굵은 글씨 = |t|≥2 (칸이 많아 몇 개는 우연). '짝/홀 시드 지도 맞음 r' 이 0 가까우면 그 지도의 무늬는 우연(흔들림)이다.",
             ha="center", fontsize=8.5)
    fig.savefig(path, dpi=72, bbox_inches="tight")
    plt.close(fig)


ZLAB_SHORT = {"d0-5": "문 앞\n0~5m", "d5-10": "은신처\n5~10m", "d10-20": "은신처\n10~20m", "d20-40": "먼 곳\n20~40m",
              "flee_hi": "도망 길\n많음", "flee_lo": "도망 길\n적음", "spotd_hi": "표적 된\n사슴 자리", "spotw_hi": "표적 고른\n늑대 자리",
              "rest_hi": "늑대\n쉼터", "graze_hi": "먹는 곳", "edge": "가장\n자리", "rand20": "무작위"}
SHORT_M = {"fl_obstacle_of_chased": "늑대가 놓친 도망 몫", "ep_caught": "쫓긴 사건 가운데 잡힘", "ep_hide": "숨음 비율"}


def zone_rank(out) -> list:
    """자리 띠를 '늑대가 놓친 도망 몫' 차이의 네 바탕·지역 평균으로 줄 세운다 (큰 것부터)."""
    zs: dict = {}
    for cb in COMBOS:
        for z, r in zone_table(out, *cb).items():
            if "fl_obstacle_of_chased" in r["m"]:
                zs.setdefault(z, []).append(r["m"]["fl_obstacle_of_chased"]["diff"])
    full = [z for z in zs if len(zs[z]) == max(len(v) for v in zs.values())]
    return sorted(full, key=lambda z: -float(np.mean(zs[z])))


def cmd_select(a) -> int:
    """단계 C 고르기: 그루 수 (가장 큰 띠·문 앞·가장 작은 띠 × 8·40 그루 × 씨 2) + 다시 재기 (G 세계·R1b-F: 격자 1 위 칸·가장 큰 띠·문 앞·무작위 20, 원판 0 인 지역은 문지기)."""
    out = Path(a.out)
    zr = zone_rank(out)
    best, worst = zr[0], zr[-1]
    qz = list(dict.fromkeys([best, "d0-5", worst]))
    lines = [f"# place.py select {time.strftime('%Y-%m-%dT%H:%M:%S')} — 띠 순서 (늑대가 놓친 도망 몫 평균, 큰 것부터): {' '.join(zr)}"]
    rc = {}
    for b, reg in COMBOS:
        cells = grid_cells(out, b, reg)
        if not cells:
            continue
        top = sorted(cells, key=lambda c: -c["m"]["fl_obstacle_of_chased"]["diff"])[:1]
        no_disc = not (sense.load_maps(combo_dir(out, b), "base", reg).get("discs") or [])
        gate = [] if not no_disc else (["gate"] if reg == "Barren" else [f"gate@{reg}"])
        q = [f"zone_{z}_n{n}_s{s}" for z in qz for n in (8, 40) for s in (1, 2)]
        lines.append(f"{b} {reg} r7e N " + " ".join(q + [g for g in gate if g != "gate"]))
        rv = [f"spot:{c['x']}:{c['y']}:8:10" for c in top] + [f"zone_{z}_n20_s{s}" for z in dict.fromkeys([best, "d0-5"]) for s in (1, 2)] \
            + ["trees:20:rand:1", "trees:20:rand:2"] + gate
        for brain, world in (("r7e", "G"), ("r1bf", "N"), ("r1bf", "G")):
            lines.append(f"{b} {reg} {brain} {world} " + " ".join(rv))
        rc[f"{b}_{reg}"] = [sense.safe_name(v) for v in rv]
    (PL / "stage_c.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (PL / "recheck_variants.json").write_text(json.dumps(dict(rc, _zones=dict(order=zr, best=best, worst=worst, quantity=qz)), ensure_ascii=False, indent=1)
                                               + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


# --------------------------------------------------------------------- #
# analyze
# --------------------------------------------------------------------- #


def _slim(p: dict | None, k: str) -> dict | None:
    if not p:
        return None
    s = scale(k)
    return dict(diff=round(p["diff"] * s, 3), se=round(p["se"] * s, 3), t=round(p["t"], 2), ref=round(p["ref"] * s, 3), n=p["n"],
                each=[round(x * s, 3) for x in p.get("each", [])])


def cmd_analyze(a) -> int:
    out = Path(a.out)
    res: dict = dict(made_by="level_sense/placement/place.py analyze", when=time.strftime("%Y-%m-%dT%H:%M:%S"), out=str(out), seeds="34900-34999",
                     horizon=H, units="비율 칸은 %p, '_n' 칸은 시드당 수", combos={})
    zone_groups, qty, grid_by, maps_by = {}, {}, {}, {}
    for base, reg in COMBOS:
        key = f"{base}_{reg}"
        try:
            M = sense.load_maps(combo_dir(out, base), "base", reg)
        except SystemExit:
            M = None
        R: dict = {}
        if M is not None:
            ttl = f"바탕 공간 지도 — {BASE_LABEL[base]} · {REG_LABEL[reg]} (R7e · N 세계 · 시드 34900~34999 · 1800 스텝)"
            R["map_half_r"] = fig_maps(M, ttl, PL / f"maps_{key}.png")
        cells = grid_cells(out, base, reg, M=M)
        grid_by[(base, reg)], maps_by[(base, reg)] = cells, M
        if cells and M is not None:
            summ = grid_summary(cells)
            fig_grid(cells, summ, M, f"작은 숲 자리 훑기 (격자 20 m) — {BASE_LABEL[base]} · {REG_LABEL[reg]} · R7e · N", PL / f"grid_{key}.png")
            R["grid"] = dict(summary=summ, cells=[dict(x=c["x"], y=c["y"], n_placed=c["n_placed"], feat={f: round(v, 4) for f, v in c.get("feat", {}).items()},
                                                       m={k: _slim(c["m"].get(k), k) for k in ALL_M if k in c["m"]}) for c in cells],
                             feature_rho=feature_corr(cells))
        zt = zone_table(out, base, reg)
        if zt:
            r20 = rand_table(out, base, reg, ns=(20,)).get(20)
            if r20:
                zt["rand20"] = dict(r20, zone="rand20", label="무작위 20 그루 (AddTrees 규칙 무작위)")
            zone_groups[(base, reg)] = zt
            R["zones_n20"] = {z: dict(label=r["label"], n_placed=r["n_placed"], m={k: _slim(r["m"].get(k), k) for k in ALL_M if k in r["m"]})
                              for z, r in zt.items()}
        qz = {}
        for kind in ["rand"] + list(ZONES):
            rt = rand_table(out, base, reg, kind=kind)
            if len(rt) >= 2:
                qz[kind] = rt
        if qz:
            qty[(base, reg)] = qz
            R["quantity"] = {kind: {str(n): dict(n_placed=r["n_placed"], m={k: _slim(r["m"].get(k), k) for k in ALL_M if k in r["m"]})
                                    for n, r in rt.items()} for kind, rt in qz.items()}
        res["combos"][key] = R
    if zone_groups:
        order = zone_rank(out) + ["rand20"]
        res["zone_order"] = order
        fig_bars(zone_groups, order, ZLAB_SHORT, "자리 띠마다 나무 20 그루 (띠 안 고르게·놓기 씨 2 개 평균) — 바탕 대비 차이 (R7e · N · 시드 100 짝, 막대 끝 ± 1.96 se)",
                 PL / "zones_n20.png")
        fig_summary(grid_by, zone_groups, maps_by, PL / "summary.png", order)
    if qty:
        rows = {}
        for cb, qz in qty.items():
            rows[cb] = {f"{kind}:{n}": r for kind, rt in qz.items() for n, r in rt.items()}
        order = sorted({k for r in rows.values() for k in r}, key=lambda s: (s.split(":")[0] != "rand", s.split(":")[0], int(s.split(":")[1])))
        fig_bars(rows, order, {o: o.replace(":", "\n") for o in order}, "그루 수 대 자리 — 같은 수를 무작위(rand)와 자리 띠에 (놓기 씨 2 개 평균)", PL / "quantity.png")
    # 다시 재기 (G 세계·R1b-F): 변형 이름 목록은 recheck.json (사슬이 만든다)
    rp = PL / "recheck_variants.json"
    if rp.exists():
        rc = json.loads(rp.read_text(encoding="utf-8"))
        res["recheck"] = {}
        for key, vs in rc.items():
            base, reg = key.split("_")
            for brain, world in (("r7e", "N"), ("r7e", "G"), ("r1bf", "N"), ("r1bf", "G")):
                rows = variant_rows(out, base, reg, vs, brain, world)
                if rows:
                    res["recheck"].setdefault(key, {})[f"{brain}_{world}"] = {v: dict(spec=r["spec"], n_placed=r["n_placed"],
                                                                                        m={k: _slim(r["m"].get(k), k) for k in ALL_M if k in r["m"]})
                                                                                for v, r in rows.items()}
    p = PL / "results.json"
    p.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":"), default=sense._jsonable) + "\n", encoding="utf-8", newline="\n")
    print(f"-> {p} ({p.stat().st_size // 1024} KB), 그림 {', '.join(sorted(q.name for q in PL.glob('*.png')))}")
    return 0


TAB_M = ["fl_obstacle_of_chased", "ep_caught", "caught", "hunt_success", "ep_hide", "ep_chased_n", "beh_graze", "fl_start_1k"]
TAB_LAB = dict(fl_obstacle_of_chased="놓친 도망", ep_caught="쫓긴 사건 잡힘", caught="잡힌 몫", hunt_success="사냥 성공률", ep_hide="숨음 비율",
               ep_chased_n="쫓긴 사건 수", beh_graze="먹기 몫", fl_start_1k="도망 시작/1k")


def _cell(x, k=None) -> str:
    if not x:
        return "·"
    d, t = x["diff"], x["t"]
    f = "{:+.2f}" if abs(d) < 10 else "{:+.1f}"
    s = f.format(d) + f" ({t:+.1f})"
    return f"**{s}**" if abs(t) >= 2 else s


def cmd_tables(a) -> int:
    """results.json → TABLES.md (README 가 인용하는 표)."""
    R = json.loads((PL / "results.json").read_text(encoding="utf-8"))
    L = ["# 나무 자리 탐색 표 (place.py tables — results.json 에서 만듦)", "",
         f"R7e · N 세계(포만 끔) · 시드 34900~34999 (100) · 1800 스텝 · 평가기. 값 = 바탕 대비 차이 (비율 칸 %p, 수 칸은 시드당 수), 괄호 = t (같은 시드 100 짝). "
         "굵게 = |t| ≥ 2. 놓친 도망 = 쫓긴 도망 가운데 줄기에 가려 늑대가 놓쳐 끝난 몫, 쫓긴 사건 잡힘 = 쫓긴 사건 가운데 잡힘, 잡힌 몫 = 사슴 가운데 잡힌 몫.", ""]
    hdr = "| " + " | ".join(TAB_LAB[k] for k in TAB_M) + " |"
    sep = "|" + "---|" * (len(TAB_M) + 1)
    for key, C in R["combos"].items():
        b, reg = key.split("_")
        L += [f"## {BASE_LABEL[b]} · {REG_LABEL[reg]}", ""]
        g = C.get("grid")
        if g:
            s = g["summary"]
            L += [f"### 격자 훑기 (20 m 격자 {s['_K']} 칸, 칸마다 작은 숲 8 그루·반지름 10 m)", "",
                  "| 칸 | 셀 평균 차이 | 셀 사이 흩어짐 sd | 셀 하나 흔들림 se (가운데값) | 짝/홀 시드 지도 맞음 r | |t|≥2 셀 (우연 기대) | |t|≥3.2 셀 |", "|---|---|---|---|---|---|---|"]
            for k in TAB_M:
                if k in s:
                    x = s[k]
                    sc = scale(k)
                    L.append(f"| {TAB_LAB[k]} | {x['mean_diff'] * sc:+.2f} | {x['sd_cells'] * sc:.2f} | {x['se_cell'] * sc:.2f} | {x['half_r']:+.2f} | "
                             f"{x['n_t2']} ({x['expect_t2']}) | {x['n_t32']} |")
            cells = g["cells"]
            top = sorted([c for c in cells if c["m"].get("fl_obstacle_of_chased")], key=lambda c: -c["m"]["fl_obstacle_of_chased"]["diff"])
            L += ["", "놓친 도망이 가장 많이 늘어난 칸 셋 · 가장 적게 늘어난 칸 셋 (중심 m):", "", "| 칸 | 은신처 가장자리 m | " + " | ".join(TAB_LAB[k] for k in TAB_M) + " |",
                  "|---|---|" + "---|" * len(TAB_M)]
            for c in top[:3] + top[-3:]:
                L.append(f"| ({c['x']}, {c['y']}) | {c['feat'].get('door_m', math.nan):.1f} | " + " | ".join(_cell(c["m"].get(k)) for k in TAB_M) + " |")
            fr = g.get("feature_rho") or {}
            if fr:
                L += ["", "셀 차이와 나무 자리 특징의 순위 맞음 ρ (특징 = 새 나무 6 m 안을 지나는 바탕 활동 몫, 거리):", "",
                      "| 칸 | 가장 맞는 특징 셋 (ρ) |", "|---|---|"]
                for k in ["fl_obstacle_of_chased", "hunt_success", "ep_caught", "caught", "ep_hide", "ep_chased_n", "beh_graze"]:
                    if k in fr:
                        tops = sorted([(f, v) for f, v in fr[k].items() if v == v], key=lambda t: -abs(t[1]))[:3]
                        L.append(f"| {TAB_LAB[k]} | " + ", ".join(f"{FEAT_LAB.get(f, f)} {v:+.2f}" for f, v in tops) + " |")
        z = C.get("zones_n20")
        if z:
            order = [o for o in R.get("zone_order", list(z)) if o in z]
            L += ["", "### 자리 띠 20 그루 (놓기 씨 1·2 평균)", "", "| 띠 | 놓은 그루 " + hdr, "|---|---|" + "---|" * len(TAB_M)]
            for o in order:
                L.append(f"| {ZONES[o]['label'] if o in ZONES else '무작위 20 그루 (AddTrees 규칙)'} | {'/'.join(map(str, z[o]['n_placed']))} | " + " | ".join(_cell(z[o]["m"].get(k)) for k in TAB_M) + " |")
        q = C.get("quantity")
        if q:
            L += ["", "### 그루 수 (8·20·40, 놓기 씨 1·2 평균)", "", "| 자리 | 그루 " + hdr, "|---|---|" + "---|" * len(TAB_M)]
            for kind, rows in q.items():
                for n, r in sorted(rows.items(), key=lambda t: int(t[0])):
                    lab = "무작위 (AddTrees 규칙)" if kind == "rand" else ZONES[kind]["label"]
                    L.append(f"| {lab} | {n} | " + " | ".join(_cell(r["m"].get(k)) for k in TAB_M) + " |")
        rc = (R.get("recheck") or {}).get(key)
        if rc:
            L += ["", "### 다시 재기 (G 세계 = 포만 켬, R1b-F = 게임 기본 내장 두뇌)", "", "| 두뇌·세계 | 변형 " + hdr, "|---|---|" + "---|" * len(TAB_M)]
            for cfg, rows in rc.items():
                for v, r in rows.items():
                    L.append(f"| {cfg} | {v} | " + " | ".join(_cell(r["m"].get(k)) for k in TAB_M) + " |")
        L.append("")
    frs = [C["grid"]["feature_rho"] for C in R["combos"].values() if C.get("grid", {}).get("feature_rho")]
    if frs:
        L += ["## 네 바탕·지역을 모은 특징 순위 맞음 (격자 칸 ρ 의 평균, 괄호 = 네 곳 가운데 같은 부호 수)", "", "| 칸 | 특징 (평균 ρ) |", "|---|---|"]
        for k in ["fl_obstacle_of_chased", "hunt_success", "ep_caught", "caught", "ep_hide", "ep_chased_n", "beh_graze"]:
            feats = sorted({f for fr in frs if k in fr for f in fr[k]})
            rows = []
            for f in feats:
                v = [fr[k][f] for fr in frs if k in fr and fr[k].get(f) == fr[k].get(f)]
                if v:
                    m = float(np.mean(v))
                    rows.append((f, m, sum(1 for x in v if np.sign(x) == np.sign(m)), len(v)))
            rows.sort(key=lambda t: -abs(t[1]))
            L.append(f"| {TAB_LAB[k]} | " + ", ".join(f"{FEAT_LAB.get(f, f)} {m:+.2f} ({s}/{n})" for f, m, s, n in rows[:4]) + " |")
        L.append("")
    p = PL / "TABLES.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"-> {p}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("zones")
    s.add_argument("--out", required=True)
    s.add_argument("--base", default="I", choices=list(sense.BASES))
    s.add_argument("--region", default="Barren")
    s.add_argument("--n", type=int, default=20)
    s.add_argument("--seed", type=int, default=1)
    s = sub.add_parser("run")
    s.add_argument("--out", required=True)
    s.add_argument("--base", default="I", choices=list(sense.BASES))
    s.add_argument("--region", default="Barren")
    s.add_argument("--brain", default="r7e", choices=list(sense.BRAINS))
    s.add_argument("--world", default="N", choices=["N", "G"])
    s.add_argument("--seeds", default=f"{sense.SEED_BOX[0]}-{sense.SEED_BOX[1]}")
    s.add_argument("--workers", type=int, default=6)
    s.add_argument("--variants", nargs="+", required=True)
    s = sub.add_parser("analyze")
    s.add_argument("--out", required=True)
    s = sub.add_parser("select")
    s.add_argument("--out", required=True)
    sub.add_parser("tables")
    a = ap.parse_args(argv)
    return dict(zones=cmd_zones, run=cmd_run, analyze=cmd_analyze, select=cmd_select, tables=cmd_tables)[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
