"""도망길 손 규칙 측정 (10-21 사용자 '도망 방향을 두뇌가 고름' 2단계 — 설계 Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 9-1·9-2·9-4절, 학습 전, 보고만).

길을 세계 규칙으로 고정해(측정 전용 선택 키 wild_flight.route_fixed — env_v2/world.py 모듈 docstring '야생 1단계' (w3) 도망길) 길마다 도망이 얼마나
짧아지는지 시드 짝으로 잰다. 도주 밖 행동은 obs21zero argmax(= R1b-F). 두뇌·게임·관문은 바꾸지 않는다.

    # herbivore_rl/ 에서 (PYTHONUTF8=1)
    python results/v3/route/route_rules.py run --out <폴더> [--parts rules,clump,g] [--workers 14]       # 본 측정 (부분마다 raw_<부분>.json, 있으면 건너뜀)
    python results/v3/route/route_rules.py run --out <폴더> --smoke                                          # 시드 3 · 300 스텝 · 워커 ≤ 4 (도구 확인)
    python results/v3/route/route_rules.py report --out <폴더>                                               # rules.json·rules.md + 9-4 판단표(oracle.json 이 있으면 함께)
    python results/v3/route/route_rules.py run --out <폴더> --world-set features.obstacles.foliage.enabled=true --world-set features.obstacles.foliage.r=3.0
                                                                                                             # 세계 덮기 (10-21 숲 시야 다시 잼)

세계 덮기 --world-set 키=값 (여러 번): 점 경로(features.<기능>.<키>[.<아래 키>] = v2 기능 블록, v2.<…>, 그 밖은 v1 칸)에 YAML 값을 넣어 모든 팔의 세계(비교 기준
RUN 포함 — 같은 덮기)에 건다. 덮기가 있으면 부분마다 '덮기 없음' RUN 팔(plain_…, --no-plain 이면 뺌)을 더 돌려 덮기 효과 표(RUN 덮기 − RUN 덮기 없음, 끝
규칙 효과 표와 같은 꼴)를 낸다. 덮기는 raw_<부분>.json(진짜 기록)·meta.json(부분 전·부분마다 쓴다)에 남는다. run 은 이미 있는 raw 파일마다 그 덮기와
견주어 다르면 멈추고(섞지 않는다 — 같은 덮기로 이어 돌리기, 새 폴더, 또는 --force 와 그 부분을 --parts 에), report 는 부분끼리·meta 와 덮기가 다르면 멈춘다.

부분 (9-1 표):
  rules  N 세계(늑대 포만 끔), 시드 34900~34959 × 지역 셋, 1800 스텝: 길 4(run·open·cover·shelter) × 끝 규칙 2(지금·quiet_end 15) = 8 팔
  clump  같은 세계 + 지역마다 덩어리 숲 2 개(반지름 5 단위 = 10 m, 줄기 30 그루, r 0.4 단위 — 측정 전용, 레벨을 바꾸지 않음): 길 2(run·cover) × 끝 규칙 2 = 4 팔
  g      G 세계(게임 그대로), 시드 34900~34939 × 3, 3600 스텝: RUN 대 가장 좋은 규칙(rules 결과에서 고름 — --g-route·--g-quiet 로 정할 수 있다)
세계 = 스냅숏(기본 results/v3/live/pilot/eco_v3_snapshot_s20004_t475_e1.json)을 실시간 고리 변환(live.prepare)으로 만든 G·N 과 같다(먹이 지도 = 스냅숏).
워커 = 실시간 고리 판정 갈림 live.eval_runner('python' 고정 — 네이티브 판정기는 길 키를 모른다), 세계 하나 = live._world_multi(run_mirror.run_world).
P1 = 스스로 벗어난 도망(은신처·원판·시야각·반경)의 쫓긴 시간 시드 평균(live.flight_pair — 관문 1차와 같은 셈), 보조 = 그 도망의 길이(초).
숲 시야(features.obstacles.foliage — env_v2/world.py 모듈 docstring '야생 2단계' 3 의 7))를 켜면 잎이 가려 놓친 도망도 원판(obstacle)이고, 그 가운데 잎 때문인
것(lost_foliage)의 몫(÷ 원판 놓침 수 — 팔마다 합 표 '원판 놓침 가운데 잎 때문', 숲 시야를 끈 팔은 —)을 따로 적는다.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
for _p in (ROOT, ROOT / "results" / "v3" / "adapt", ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "r4",
           ROOT / "results" / "v3" / "wild2", ROOT / "results" / "v3" / "live", HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

import adapt as ad  # noqa: E402
import live as lv  # noqa: E402
import r4_eval as re_  # noqa: E402

SNAPSHOT = ROOT / "results" / "v3" / "live" / "pilot" / "eco_v3_snapshot_s20004_t475_e1.json"
ROUTES = ("run", "open", "cover", "shelter")
QUIET = (0, 15)                                     # 끝 규칙: 지금(0 = 끔)·quiet_end 15 스텝(2 초)
PARTS = ("rules", "clump", "g")
SEEDS = dict(rules=(34900, 34959), clump=(34900, 34959), g=(34900, 34939))
STEPS = dict(rules=1800, clump=1800, g=3600)
SMOKE = dict(seeds=3, steps=300, workers=4)
STEP_S = lv.STEP_S
USEFUL_S, USEFUL_T, CAUGHT_T, OBST_PP = 0.5, 2.0, 2.0, 0.05     # 9-4 '쓸모 있음': 차이 ≤ −0.5 초·짝 t ≤ −2, 잡힘 t ≥ +2 면 빼기, COVER 원판 놓침 몫 +5 %p
# 덩어리 숲 가정 (9-1 — 측정 전용): 지역마다 덩어리 CLUMPS 개, 반지름 CLUMP_R 단위 안에 줄기 CLUMP_TRUNKS 그루(r CLUMP_TRUNK_R), 줄기 중심 사이 ≥ CLUMP_GAP
CLUMP_TAG = 0x434C554D50                            # "CLUMP"
CLUMPS, CLUMP_R, CLUMP_TRUNKS, CLUMP_TRUNK_R, CLUMP_GAP = 2, 5.0, 30, 0.4, 1.2
CLUMP_WALL, CLUMP_COVER_GAP, CLUMP_APART, CLUMP_TRIES = 3.0, 2.0, 12.0, 4000
CAUSES = ("cover", "obstacle", "fov", "range", "switch", "stop", "held", "unchased", "caught", "starved", "truncated")


# --------------------------------------------------------------------- #
# 세계·일
# --------------------------------------------------------------------- #

def prepare_info(out: Path, snapshot: Path) -> dict:
    """스냅숏 → <out>/world (live.prepare — world.yaml(G)·regions.json·convert.json). 이미 있으면 다시 읽는다."""
    rd = Path(out) / "world"
    if (rd / "convert.json").exists() and (rd / "regions.json").exists():
        rec = json.loads((rd / "convert.json").read_text(encoding="utf-8"))
        return dict(record=rec, regions=json.loads((rd / "regions.json").read_text(encoding="utf-8")), dir=rd,
                    start=dict(zip=Path(ROOT / rec["anchor"])))
    snap = lv.read_snapshot(snapshot)
    return lv.prepare(Path(snapshot), snap, rd, lv.brain_folders(Path(out)))


def clump_discs(region_index: int, size: float, covers) -> list:
    """덩어리 숲 원판 (지역마다 결정적 — 난수 default_rng([CLUMP_TAG, region_index])). 덩어리 중심 = 벽에서 CLUMP_R + CLUMP_WALL 안쪽, 은신처 원에서
    r_k + CLUMP_R + CLUMP_COVER_GAP 밖, 덩어리끼리 CLUMP_APART 이상. 줄기 = 덩어리 원(반지름 CLUMP_R − CLUMP_TRUNK_R) 안 균등, 줄기 중심 사이 ≥ CLUMP_GAP
    (사슴 몸이 지날 틈). 반환 [[x, y, r], …]."""
    g = np.random.default_rng([CLUMP_TAG, int(region_index)])
    cc = np.asarray([[c[0], c[1]] for c in covers], dtype=np.float64).reshape(-1, 2)
    cr = np.asarray([c[2] for c in covers], dtype=np.float64).reshape(-1)
    lo, hi = CLUMP_R + CLUMP_WALL, float(size) - CLUMP_R - CLUMP_WALL
    centers: list = []
    for _ in range(CLUMP_TRIES):
        if len(centers) == CLUMPS:
            break
        c = g.uniform(lo, hi, 2)
        if len(cc) and (np.sqrt(((cc - c) ** 2).sum(1)) < cr + CLUMP_R + CLUMP_COVER_GAP).any():
            continue
        if any(math.hypot(c[0] - o[0], c[1] - o[1]) < CLUMP_APART for o in centers):
            continue
        centers.append((float(c[0]), float(c[1])))
    if len(centers) < CLUMPS:
        raise ValueError(f"지역 {region_index}: 덩어리 숲 자리 {CLUMPS} 개를 찾지 못했다")
    out = []
    for cx, cy in centers:
        trunks: list = []
        for _ in range(CLUMP_TRIES):
            if len(trunks) == CLUMP_TRUNKS:
                break
            r = (CLUMP_R - CLUMP_TRUNK_R) * math.sqrt(float(g.random()))
            a = 2.0 * math.pi * float(g.random())
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if any(math.hypot(x - u, y - v) < CLUMP_GAP for u, v in trunks):
                continue
            trunks.append((x, y))
        if len(trunks) < CLUMP_TRUNKS:
            raise ValueError(f"지역 {region_index}: 덩어리 줄기 {CLUMP_TRUNKS} 그루를 놓지 못했다")
        out += [[float(x), float(y), CLUMP_TRUNK_R] for x, y in trunks]
    return out


def arm_name(route: str, qe: int, clump: bool = False, world: str = "N", plain: bool = False) -> str:
    """팔 이름: [plain_][clump_]<길>_q<끝 규칙>[_<세계>] — plain = 세계 덮기(--world-set)를 걸지 않은 RUN 기준 팔."""
    return f"{'plain_' if plain else ''}{'clump_' if clump else ''}{route}_q{int(qe)}" + ("" if world == "N" else f"_{world}")


# --------------------------------------------------------------------- #
# 세계 덮기 (--world-set)
# --------------------------------------------------------------------- #

def parse_world_set(items) -> dict:
    """['키=값', …] → {점 경로: 값} (값은 YAML — true·3.0·null·[1, 2]). 같은 키를 두 번 주면 멈춘다."""
    import yaml

    out: dict = {}
    for it in items or ():
        if "=" not in it:
            raise SystemExit(f"--world-set {it!r} 는 키=값 꼴이어야 한다")
        k, v = it.split("=", 1)
        k = k.strip()
        if not k or any(not x for x in k.split(".")):
            raise SystemExit(f"--world-set {it!r}: 키가 비었다")
        if k in out:
            raise SystemExit(f"--world-set {k} 를 두 번 주었다")
        out[k] = yaml.safe_load(v)
    return out


def apply_world_set(cfg: dict, sets: dict) -> None:
    """설정 dict(Config.to_dict 꼴)에 점 경로 덮기를 건다(제자리): features.<…> = cfg['v2']['features'][…], v2.<…> = cfg['v2'][…], 그 밖은 v1 칸.
    중간 칸이 없거나 null 이면 빈 블록을 만든다(예: obstacles.foliage — 빠진 아래 키는 세계가 끔 값으로 채운다). 중간 칸이 블록이 아니면 멈춘다."""
    for path, val in sets.items():
        ks = path.split(".")
        if ks[0] == "features":
            node, ks = cfg.setdefault("v2", {}).setdefault("features", {}), ks[1:]
        elif ks[0] == "v2":
            node, ks = cfg.setdefault("v2", {}), ks[1:]
        else:
            node = cfg
        if not ks:
            raise SystemExit(f"--world-set {path}: 칸 이름이 없다")
        for k in ks[:-1]:
            if node.get(k) is None:
                node[k] = {}
            if not isinstance(node[k], dict):
                raise SystemExit(f"--world-set {path}: 칸 {k} 가 블록이 아니다 ({node[k]!r})")
            node = node[k]
        node[ks[-1]] = val


def world_set_text(sets: dict) -> str:
    return " ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in sets.items()) or "없음"


def raw_world_set(path: Path) -> dict:
    """이미 쓴 raw_<부분>.json(·oracle_raw.json)의 세계 덮기 — 그 파일이 잰 세계의 진짜 기록이다(meta.json 은 보고용). 옛 판(칸 없음) = 덮기 없음."""
    return json.loads(Path(path).read_text(encoding="utf-8")).get("world_set") or {}


def same_world_set(x: dict, y: dict) -> bool:
    """JSON 으로 적은 덮기끼리 같은가 (키 순서 무관)."""
    return json.dumps(lv.jsonable(x or {}), sort_keys=True) == json.dumps(lv.jsonable(y or {}), sort_keys=True)


def route_items(info: dict, model: Path, seeds, steps: int, route: str, qe: int, world: str = "N", clump: bool = False,
                world_set: dict | None = None, plain: bool = False) -> list:
    """팔 하나의 일 (live._world_multi — 판정 길이 steps 하나): N 은 늑대 포만 끔(live.NOSAT), 길 고정 wild_flight.route_fixed·끝 규칙 quiet_end(0 이면 적지
    않는다), clump 면 지역 원판에 덩어리 숲을 더하고 그 줄기 밑 먹이 용량을 줄인다(obstacle_food_factor — 스냅숏 용량은 지금 나무까지 건 값이다).
    world_set = 세계 덮기(--world-set — 모든 팔에 같게, 길·끝 규칙·포만 뒤에 건다), plain 이면 덮기를 걸지 않는다(덮기 효과 표의 기준 RUN)."""
    from env_v2.world import obstacle_food_factor

    sets = dict(lv.NOSAT["sets"]) if world == "N" else {}
    sets["wild_flight.route_fixed"] = route
    if int(qe) > 0:
        sets["wild_flight.quiet_end"] = int(qe)
    jobs = ad.make_jobs(info, Path(model), seeds, int(steps), True, dict(name=arm_name(route, qe, clump, world, plain), sets=sets))
    if world_set and not plain:
        for j in jobs:
            apply_world_set(j["cfg"], world_set)
    if clump:
        size = float(jobs[0]["cfg"]["rand"]["world_size"][0]) if jobs and "rand" in jobs[0]["cfg"] else 60.0
        extra = {n: clump_discs(r["region_index"], size, r["covers"]) for n, r in info["regions"].items()}
        for j in jobs:
            r = info["regions"][j["region"]]
            add = extra[j["region"]]
            j["cfg"]["v2"]["features"]["obstacles"]["fixed"] = list(j["cfg"]["v2"]["features"]["obstacles"]["fixed"] or []) + add
            gw = int(r["gw"])
            cell = float(j["cfg"].get("food_cell", 0.0)) or size / gw
            j["snap_food"] = (np.asarray(r["cap"], dtype=np.float64).reshape(gw, gw)
                              * obstacle_food_factor(gw, cell, np.asarray(add, dtype=np.float64))).ravel().tolist()
    tag = arm_name(route, qe, clump, world, plain)
    for j in jobs:
        j["horizons"] = [int(steps)]
    return [("multi", f"{tag}:{world}", j) for j in jobs]


def run_items(items: list, workers: int, label: str) -> list:
    """live.eval_runner('python' 워커 풀) — 50 판마다 진행 줄."""
    done = [0]
    t0 = time.perf_counter()

    def tick():
        done[0] += 1
        if done[0] % 50 == 0 or done[0] == len(items):
            print(f"  {label} {done[0]}/{len(items)} ({time.perf_counter() - t0:.0f} 초)", flush=True)

    return lv.eval_runner(items, int(workers), kind="python", on_done=tick)


# --------------------------------------------------------------------- #
# 통계 (시드 짝 — 지역마다, 그리고 지역 합)
# --------------------------------------------------------------------- #

def by_arm(rows: list) -> dict:
    out: dict = {}
    for tag, w in rows:
        out.setdefault(tag.rsplit(":", 1)[0], []).append(w)
    return out


def region_res(worlds: list, region: str | None) -> dict:
    return dict(worlds=[w for w in worlds if region is None or w["region"] == region])


def seed_sums(res: dict) -> dict:
    """시드 → 지역 합 (도망 기록·길 기록·죽음)."""
    out: dict = {}
    for w in res["worlds"]:
        f = w["flight"]
        a = out.setdefault(int(w["seed"]), dict(n=0, caught=0, starved=0, alive=0, shelter=0, live=0, started=0, flee=0, own_n=0, own_steps=0,
                                                own_contact=0, refled=0, onsets=0, onset_cover=0, onset_shelter=0, chased=0, hidden=0,
                                                quiet=0, lost_foliage=0, fol=False, causes={c: 0 for c in CAUSES}))
        for k in ("n", "caught", "starved", "alive"):
            a[k] += int(w[k])
        a["shelter"] += int(w["shelter_steps"])
        a["live"] += int(f["live_steps"])
        a["started"] += int(f["started"])
        a["flee"] += int(f["flee_steps"])
        a["own_n"] += int(f["own_n"])
        a["own_steps"] += int(f["own_steps"])
        a["own_contact"] += int(f["own_contact"])
        a["quiet"] += int(f.get("quiet_ends", 0))
        if "lost_foliage" in f:                                                # 숲 시야 켬 세계만 (obstacle 의 일부)
            a["fol"] = True
            a["lost_foliage"] += int(f["lost_foliage"]["n"])
        for c in CAUSES:
            a["causes"][c] += int(f["n"][c])
        r = f.get("route")
        if r is not None:
            a["refled"] += int(r["refled"])
            a["onsets"] += int(r["onsets"])
            a["onset_cover"] += int(r["onset_cover"])
            a["onset_shelter"] += int(r["onset_shelter"])
            a["chased"] += int(sum(r["chased_steps"].values()))
            a["hidden"] += int(sum(r["hidden_steps"].values()))
    return out


def _r(x, y):
    return x / y if y else float("nan")


SEED_METRICS = {
    # 이름 → (시드 합 → 값, 단위 글자)
    "p1_len_s": (lambda a: _r(a["own_steps"], a["own_n"]) * STEP_S, "초"),
    "started": (lambda a: float(a["started"]), "수"),
    "truncated": (lambda a: float(a["causes"]["truncated"]), "수"),
    "flee_s_per_deer_min": (lambda a: _r(60.0 * a["flee"], a["live"]), "초/사슴-분"),
    "own_share": (lambda a: _r(a["own_n"], a["started"]), "몫"),
    "obstacle_share": (lambda a: _r(a["causes"]["obstacle"], a["started"]), "몫"),
    # 원판(obstacle) 놓침 가운데 잎 때문인 몫 — 숲 시야를 끈 세계(덮기 없음 팔 등)는 nan
    "foliage_of_obstacle": (lambda a: _r(a["lost_foliage"], a["causes"]["obstacle"]) if a["fol"] else float("nan"), "몫"),
    "cover_end_share": (lambda a: _r(a["causes"]["cover"], a["started"]), "몫"),
    "caught_share": (lambda a: _r(a["causes"]["caught"], a["started"]), "몫"),
    "caught": (lambda a: _r(a["caught"], a["n"]), "몫"),
    "starved": (lambda a: _r(a["starved"], a["n"]), "몫"),
    "alive": (lambda a: _r(a["alive"], a["n"]), "몫"),
    "shelter": (lambda a: _r(a["shelter"], a["live"]), "몫"),
    "refled": (lambda a: float(a["refled"]), "수"),
    "onset_cover": (lambda a: _r(a["onset_cover"], a["onsets"]), "몫"),
    "onset_shelter": (lambda a: _r(a["onset_shelter"], a["onsets"]), "몫"),
    "hidden_share": (lambda a: _r(a["hidden"], a["chased"]), "몫"),
}


def pair_metric(xa: dict, xb: dict, key: str) -> dict:
    """시드 짝 a − b (둘 다 값이 nan 이 아닌 시드만). 0.5 초를 가를 시드 수(5 %·검정력 80 %)도 적는다(초 단위 칸만)."""
    fn = SEED_METRICS[key][0]
    seeds = [s for s in sorted(xa) if s in xb]
    va = {s: fn(xa[s]) for s in seeds}
    vb = {s: fn(xb[s]) for s in seeds}
    keep = [s for s in seeds if va[s] == va[s] and vb[s] == vb[s]]
    if len(keep) < 2:
        return dict(a=float("nan"), b=float("nan"), diff=float("nan"), se=float("nan"), t=float("nan"), n=len(keep), sd=float("nan"))
    p = re_.paired({s: va[s] for s in keep}, {s: vb[s] for s in keep})
    return dict(p, sd=float(p["se"] * math.sqrt(p["n"])))


def compare(xres: dict, bres: dict, region: str | None) -> dict:
    """팔 x 대 기준 b (같은 시드·같은 지역): P1 쫓긴 시간(live.flight_pair — 관문 1차 셈)과 9-2 칸들의 짝 차이."""
    A, B = region_res(xres["worlds"], region), region_res(bres["worlds"], region)
    p1 = lv.flight_pair(A, B)
    p1["sd"] = float(p1["se"] * math.sqrt(p1["n"])) if p1["n"] > 1 else float("nan")
    p1["seeds_for_0.5s"] = (int(math.ceil(((lv._Z975 + 0.8416) * p1["sd"] / 0.5) ** 2)) if p1["sd"] == p1["sd"] else None)
    xa, xb = seed_sums(A), seed_sums(B)
    out = dict(p1=p1)
    for k in SEED_METRICS:
        out[k] = pair_metric(xa, xb, k)
    return out


def pooled_arm(res: dict, region: str | None) -> dict:
    """팔 하나의 합 (보고): 시드 합 몫·평균."""
    xs = seed_sums(region_res(res["worlds"], region))
    t = {k: sum(a[k] for a in xs.values()) for k in ("n", "caught", "starved", "alive", "shelter", "live", "started", "flee", "own_n",
                                                    "own_steps", "own_contact", "refled", "onsets", "onset_cover", "onset_shelter", "chased",
                                                    "hidden", "quiet", "lost_foliage")}
    causes = {c: sum(a["causes"][c] for a in xs.values()) for c in CAUSES}
    return dict(t, causes=causes, seeds=len(xs), own_contact_s=_r(t["own_contact"], t["own_n"]) * STEP_S,
                own_len_s=_r(t["own_steps"], t["own_n"]) * STEP_S, flee_s_per_deer_min=_r(60.0 * t["flee"], t["live"]),
                cause_share={c: _r(v, t["started"]) for c, v in causes.items()}, caught_frac=_r(t["caught"], t["n"]),
                starved_frac=_r(t["starved"], t["n"]), shelter_frac=_r(t["shelter"], t["live"]), onset_cover=_r(t["onset_cover"], t["onsets"]),
                onset_shelter=_r(t["onset_shelter"], t["onsets"]), hidden_share=_r(t["hidden"], t["chased"]),
                fol=any(a["fol"] for a in xs.values()),
                foliage_of_obstacle=(_r(t["lost_foliage"], causes["obstacle"]) if any(a["fol"] for a in xs.values()) else float("nan")))


def useful(cmp: dict, route: str) -> tuple[bool, str]:
    """9-4 '쓸모 있음' (한 지역의 비교 하나): P1 차이 ≤ −0.5 초 ∧ 짝 t ≤ −2, 또는 COVER 는 원판 놓침 몫 +5 %p 이상 ∧ P1 이 줄어드는 쪽.
    잡힘이 늘면(짝 t ≥ +2) 쓸모 있음으로 치지 않는다."""
    p, ob, cg = cmp["p1"], cmp["obstacle_share"], cmp["caught"]
    why = []
    ok = p["n"] >= 2 and p["diff"] <= -USEFUL_S and p["t"] <= -USEFUL_T
    if ok:
        why.append(f"P1 {p['diff']:+.2f} 초 (t {p['t']:+.2f})")
    if route == "cover" and ob["n"] >= 2 and ob["diff"] >= OBST_PP and p["n"] >= 2 and p["diff"] < 0:
        ok = True
        why.append(f"원판 놓침 몫 {ob['diff'] * 100:+.1f} %p")
    if ok and cg["n"] >= 2 and cg["t"] >= CAUGHT_T:
        return False, f"잡힘 늘어남 (t {cg['t']:+.2f}) — " + ", ".join(why)
    return ok, ", ".join(why)


# --------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------- #

def seeds_of(lohi) -> list[int]:
    return list(range(int(lohi[0]), int(lohi[1]) + 1))


def arms_of(part: str, g_route: str | None = None, g_qe: int | None = None, plain: bool = False) -> list[tuple]:
    """부분의 팔 (길, 끝 규칙, 덩어리 숲, 세계, 덮기 없음). plain 이면 RUN 팔마다 세계 덮기를 걸지 않은 기준 팔(덮기 효과 표)을 뒤에 더한다."""
    if part == "rules":
        arms = [(r, q, False, "N", False) for r in ROUTES for q in QUIET]
    elif part == "clump":
        arms = [(r, q, True, "N", False) for r in ("run", "cover") for q in QUIET]
    elif part == "g":
        arms = [("run", int(g_qe), False, "G", False), (g_route, int(g_qe), False, "G", False)]
    else:
        raise ValueError(f"모르는 부분 {part}")
    if plain:
        arms += [(r, q, cl, wn, True) for r, q, cl, wn, _ in arms if r == "run"]
    return arms


def pick_best(rules: dict | None) -> tuple[str, int]:
    """G 세계에 견줄 가장 좋은 규칙: rules 비교(지역 합)에서 RUN 대비 P1 차이가 가장 작은(가장 음수) 두뇌 길(COVER·SHELTER — OPEN 은 측정 전용이라 두뇌가
    고를 수 없다)·끝 규칙 — 쓸모 있음인 것을 먼저."""
    if not rules:
        raise SystemExit("G 세계 부분은 rules 결과(raw_rules.json)나 --g-route·--g-quiet 가 있어야 한다")
    best = None
    for name, c in rules["compare"].items():
        route, qe = name.rsplit("_q", 1)
        if route not in ("cover", "shelter"):
            continue
        d = c["all"]["p1"]["diff"]
        u = any(c[r]["useful"][0] for r in c if r != "all")
        key = (0 if u else 1, d if d == d else math.inf)
        if best is None or key < best[0]:
            best = (key, route, int(qe))
    return best[1], best[2]


def cmd_run(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    parts = [p for p in a.parts.split(",") if p]
    for p in parts:
        if p not in PARTS:
            raise SystemExit(f"--parts {p} 는 {', '.join(PARTS)} 가운데 하나여야 한다")
    W = min(int(a.workers), SMOKE["workers"]) if a.smoke else int(a.workers)
    wset = parse_world_set(a.world_set)
    plain = bool(wset) and not a.no_plain
    info = prepare_info(out, Path(a.snapshot))
    model = Path(a.model) if a.model else Path(info["start"]["zip"])
    print(f"도망길 손 규칙 측정 → {out} (스냅숏 {Path(a.snapshot).name}, 두뇌 {lv.path_text(model)}, 워커 {W}, 세계 덮기 {world_set_text(wset)}"
          f"{' + 덮기 없음 RUN' if plain else ''}{', 연기 시험' if a.smoke else ''})", flush=True)
    meta_p = out / "meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    # 섞지 않기: 이미 있는 부분 결과마다 그 raw 파일에 적힌 덮기와 견준다(meta.json 은 끊긴 실행이면 없거나 옛 값일 수 있다). 다른 덮기의 부분은
    # --force 로 이번에 다시 잴 때만 허용한다(그 밖은 멈춘다 — 다른 부분을 그 결과로 고르거나 한 보고에 섞지 않게)
    had = {p: raw_world_set(out / f"raw_{p}.json") for p in PARTS if (out / f"raw_{p}.json").exists()}
    bad = [p for p, ws in had.items() if not same_world_set(ws, wset) and not (a.force and p in parts)]
    if bad:
        raise SystemExit(f"{out} 의 결과 " + ", ".join(f"{p}(세계 덮기 {world_set_text(had[p])})" for p in bad) + f" — 지금 덮기 {world_set_text(wset)} "
                         "와 섞지 않는다 (같은 --world-set 으로 다시 돌리거나, 새 폴더, 또는 --force 와 그 부분을 --parts 에 넣어 다시)")
    meta.update(snapshot=str(a.snapshot), model=lv.path_text(model), smoke=bool(a.smoke), workers=W, started=meta.get("started") or datetime.now().isoformat(),
                world_set=lv.jsonable(wset), world_set_args=list(a.world_set or []), plain=plain)
    lv.atomic_write_json(meta_p, meta)                   # 부분을 돌리기 전에 먼저 쓴다 (끊겨도 덮기가 남는다 — 부분이 끝날 때마다 다시 쓴다)
    for part in parts:
        raw = out / f"raw_{part}.json"
        if raw.exists() and not a.force:
            print(f"  {part}: {raw.name} 이 있다 — 건너뜀 (--force 로 다시)", flush=True)
            continue
        seeds = seeds_of(SEEDS[part])[: SMOKE["seeds"]] if a.smoke else seeds_of(SEEDS[part])
        steps = SMOKE["steps"] if a.smoke else STEPS[part]
        if part == "g":
            if a.g_route:
                gr, gq = a.g_route, int(a.g_quiet or 0)
            else:
                rr = out / "raw_rules.json"
                gr, gq = pick_best(summarize_part(json.loads(rr.read_text(encoding="utf-8"))) if rr.exists() else None)
            if gr == "run":
                print("  g: 가장 좋은 규칙이 RUN — G 세계 비교를 건너뛴다", flush=True)
                continue
            arms = arms_of(part, gr, gq, plain)
        else:
            arms = arms_of(part, plain=plain)
        items = [it for (r, q, cl, wn, pl) in arms for it in route_items(info, model, seeds, steps, r, q, wn, cl, wset, pl)]
        print(f"  {part}: 팔 {len(arms)} × 시드 {len(seeds)} × 지역 {len(info['regions'])} = 세계 {len(items)}, {steps} 스텝", flush=True)
        t0 = time.perf_counter()
        rows = run_items(items, W, part)
        wall = time.perf_counter() - t0
        world_wall = [w["wall_s"] for _, w in rows]
        d = dict(part=part, seeds=seeds, steps=steps, world_set=lv.jsonable(wset),
                 arms=[dict(route=r, quiet_end=q, clump=cl, world=wn, plain=pl, name=arm_name(r, q, cl, wn, pl)) for r, q, cl, wn, pl in arms],
                 workers=W, wall_s=round(wall, 1), world_wall_mean_s=float(np.mean(world_wall)), sec_per_world_step=float(np.mean(world_wall)) / steps,
                 worlds=[dict(tag=t, **w) for t, w in rows])
        lv.atomic_write_json(raw, lv.jsonable(d), indent=None)
        meta.setdefault("times", {})[part] = dict(wall_s=d["wall_s"], worlds=len(rows), sec_per_world_step=d["sec_per_world_step"])
        lv.atomic_write_json(meta_p, meta)
        print(f"  {part}: {wall:.0f} 초 (세계 하나 평균 {d['world_wall_mean_s']:.1f} 초) → {raw.name}", flush=True)
    lv.atomic_write_json(meta_p, meta)
    return cmd_report(a)


def summarize_part(d: dict) -> dict:
    """raw_<부분>.json → 팔마다 합(지역별·전체), 기준 팔(같은 끝 규칙·같은 배치의 RUN) 대비 비교와 쓸모 있음."""
    rows = [(w["tag"], w) for w in d["worlds"]]
    arms = by_arm(rows)
    regions = sorted({w["region"] for _, w in rows})
    res = {k: dict(worlds=v) for k, v in arms.items()}
    out = dict(part=d["part"], seeds=d["seeds"], steps=d["steps"], regions=regions, world_set=d.get("world_set") or {},
               plain=any(arm.get("plain") for arm in d["arms"]), pooled={}, compare={})
    for name, r in res.items():
        out["pooled"][name] = {reg: pooled_arm(r, reg) for reg in regions} | {"all": pooled_arm(r, None)}
    for arm in d["arms"]:
        name = arm["name"]
        if arm["route"] == "run":
            continue
        base = arm_name("run", arm["quiet_end"], arm["clump"], arm["world"])
        if base not in res:
            continue
        c = {}
        for reg in regions + [None]:
            cm = compare(res[name], res[base], reg)
            cm["useful"] = useful(cm, arm["route"])
            c[reg or "all"] = cm
        out["compare"][name.removesuffix(f"_{arm['world']}") if arm["world"] != "N" else name] = c
    # 끝 규칙 효과 (RUN quiet_end 15 − RUN 지금) — 보고
    for cl in (False, True):
        a_, b_ = arm_name("run", 15, cl), arm_name("run", 0, cl)
        if a_ in res and b_ in res:
            out.setdefault("quiet_effect", {})["clump" if cl else "now"] = {(reg or "all"): compare(res[a_], res[b_], reg) for reg in regions + [None]}
    # 세계 덮기 효과 (RUN 덮기 − 같은 끝 규칙·배치·세계의 RUN 덮기 없음, 같은 시드 — 숲 시야 효과) — 보고
    for arm in d["arms"]:
        if not arm.get("plain"):
            continue
        a_ = arm_name("run", arm["quiet_end"], arm["clump"], arm["world"])
        if a_ in res and arm["name"] in res:
            out.setdefault("set_effect", {})[a_] = {(reg or "all"): compare(res[a_], res[arm["name"]], reg) for reg in regions + [None]}
    return out


def oracle_rows(out: Path) -> dict | None:
    p = out / "oracle.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


ORACLE_MEASURE = "contact"                           # 판단표 잣대 — 오라클도 P1 과 같은 쫓긴 시간이어야 한다 (oracle.py MEASURE)


def decide(rules: dict | None, clump: dict | None, oracle: dict | None) -> dict:
    """9-4 미리 적은 판단표 — 위에서부터 읽어 처음으로 '아니오'가 아닌 줄에서 멈춘다: '예'면 그 줄이 판단, 아직 모름(None — 오라클·덩어리 숲·배울 수 있나
    결과가 없음)이면 판단하지 않는다(verdict None, pending = 그 줄, missing = 모자란 것). 모든 줄이 '아니오'면 줄 0(쓸모 있는 길 없음).
    잣대는 모든 줄이 P1 = 쫓긴 시간(관문 1차와 같은 셈) — 오라클 결과가 다른 잣대(옛 도망 길이)면 그 줄은 모름으로 둔다."""
    def any_useful(part, route, qes):
        if not part:
            return None, []
        hit = []
        for name, c in part["compare"].items():
            r, q = name.removeprefix("clump_").rsplit("_q", 1)
            if r != route or int(q) not in qes:
                continue
            for reg, cm in c.items():
                if reg != "all" and cm["useful"][0]:
                    hit.append(f"{name} {reg}: {cm['useful'][1]}")
        return bool(hit), hit

    rows = []
    o_none = o_learn = None
    o_ok = oracle is not None and oracle.get("measure") == ORACLE_MEASURE
    o_miss = ("오라클 결과 (oracle.py run 뒤 report)" if oracle is None
              else f"오라클을 쫓긴 시간으로 다시 셈 (지금 잣대 {oracle.get('measure', '도망 길이 — 옛 꼴')} — oracle.py report)")
    if o_ok:
        o_none = oracle["decision"]["no_gain"]
        o_learn = oracle["decision"]["learnable"]
    rows.append(dict(row=1, cond="오라클(잡음 뺀 값) − RUN > −0.5 초 (모든 지역, 두 끝 규칙)", hit=o_none, next="학습하지 않음. 보고",
                     evidence=oracle["decision"]["no_gain_why"] if o_ok else o_miss, missing=[] if o_none is not None else ([o_miss] if not o_ok else ["오라클 이득 (값 없음)"])))
    rows.append(dict(row=2, cond="배울 수 있나 실패", hit=None if o_learn is None else not o_learn, next="관측을 고친 뒤 다시 잼 (학습하지 않음)",
                     evidence=oracle["decision"]["learnable_why"] if o_ok else o_miss,
                     missing=[] if o_learn is not None else ([o_miss] if not o_ok else [f"배울 수 있나 판단 ({oracle['decision']['learnable_why']})"])))
    c_now, e_now = any_useful(rules, "cover", (0,))
    c_q, e_q = any_useful(rules, "cover", (15,))
    c_cl, e_cl = any_useful(clump, "cover", (0, 15))
    s_any, e_s = any_useful(rules, "shelter", (0, 15))
    m_r = [] if rules else ["규칙 측정 rules (route_rules.py run --parts rules)"]
    m_c = [] if clump else ["덩어리 숲 측정 clump (route_rules.py run --parts clump)"]
    rows.append(dict(row=3, cond="COVER 가 지금 끝 규칙·지금 배치에서 쓸모 있음", hit=c_now, next="사람 결정 없이 세 길로 10절 단계 진행", evidence=e_now, missing=m_r))
    rows.append(dict(row=4, cond="COVER 가 quiet_end 에서만 쓸모 있음", hit=None if c_now is None or c_q is None else (not c_now and c_q),
                     next="14절 (1) 을 묻는다", evidence=e_q, missing=m_r))
    rows.append(dict(row=5, cond="COVER 가 덩어리 숲에서만 쓸모 있음",
                     hit=None if c_now is None or c_q is None or c_cl is None else (not c_now and not c_q and c_cl), next="14절 (2) 를 묻는다", evidence=e_cl,
                     missing=m_r + m_c))
    rows.append(dict(row=6, cond="COVER 는 어디서도 쓸모없고 SHELTER 만 쓸모 있음",
                     hit=None if None in (c_now, c_q, c_cl, s_any) else (not c_now and not c_q and not c_cl and s_any), next="14절 (2) 를 묻는다",
                     evidence=e_s, missing=m_r + m_c))
    verdict = pending = None
    for r in rows:                                   # 위에서부터: 처음으로 '아니오'가 아닌 줄에서 멈춘다 (모르는 줄을 건너뛰고 아래 줄로 판단하지 않는다)
        if r["hit"] is None:
            pending = r
            break
        if r["hit"]:
            verdict = r
            break
    else:
        verdict = dict(row=0, cond="어느 줄에도 맞지 않음 (쓸모 있는 길 없음)", next="보고 — 학습하지 않음", hit=True, evidence=[], missing=[])
    missing = [] if pending is None else list(dict.fromkeys(m for r in rows if r["hit"] is None for m in r["missing"]))
    return dict(rows=rows, verdict=verdict, pending=None if pending is None else pending["row"], missing=missing, measure=ORACLE_MEASURE)


def fnum(x, nd=2, unit=""):
    if x is None or x != x:
        return "—"
    return f"{x:+.{nd}f}{unit}" if unit != "%" else f"{x * 100:+.{nd}f}%p"


def fmt_part(s: dict, title: str) -> list[str]:
    L = [f"## {title} (시드 {s['seeds'][0]}~{s['seeds'][-1]} × 지역 {len(s['regions'])}, {s['steps']} 스텝, 세계 덮기 {world_set_text(s.get('world_set') or {})})", "",
         "| 팔 | 지역 | P1 RUN 초 | P1 팔 초 | 차이 | sd | t | 시드 (빠짐) | 0.5 초 가를 시드 | 길이 차이 초 | 시작 수 차이 | 잘림 차이 | 도주 초/사슴-분 차이 | 원판 놓침 몫 | 잡힘 차이 (t) | 굶음 차이 | 은신처 안 | 5 초 안 다시 | 쓸모 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, c in s["compare"].items():
        for reg, cm in c.items():
            p = cm["p1"]
            u = cm.get("useful", (False, ""))
            L.append(f"| {name} | {reg} | {p['b']:.2f} | {p['a']:.2f} | {fnum(p['diff'])} | {p['sd']:.2f} | {fnum(p['t'])} | {p['n']} ({len(p['dropped'])}) | "
                     f"{p['seeds_for_0.5s'] if p['seeds_for_0.5s'] is not None else '—'} | {fnum(cm['p1_len_s']['diff'])} | {fnum(cm['started']['diff'], 1)} | "
                     f"{fnum(cm['truncated']['diff'], 1)} | {fnum(cm['flee_s_per_deer_min']['diff'])} | {fnum(cm['obstacle_share']['diff'], 1, '%')} | "
                     f"{fnum(cm['caught']['diff'], 2, '%')} ({fnum(cm['caught']['t'])}) | {fnum(cm['starved']['diff'], 2, '%')} | "
                     f"{fnum(cm['shelter']['diff'], 2, '%')} | {fnum(cm['refled']['diff'], 1)} | {'예 — ' + u[1] if u[0] else ('아니오' + (' — ' + u[1] if u[1] else ''))} |")
    L += ["", "### 팔마다 합 (전체 지역)", "",
          "| 팔 | 시작 | 쫓긴 시간 초 (스스로 벗어남) | 그 길이 초 | 도주 초/사슴-분 | 끝 까닭 몫 (은신처·원판·시야각·반경 / 바꿈·그만둠·붙잡힘·안 쫓김 / 잡힘·굶음·잘림) | 원판 놓침 가운데 잎 때문 (숲 시야 끈 팔 —) | 잡힘 | 은신처 안 | 시작 때 COVER·SHELTER 가능 | 쫓는 늑대에게 가려진 몫 | quiet 끝 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, pr in s["pooled"].items():
        a = pr["all"]
        cs = a["cause_share"]
        parts = " / ".join("·".join(f"{cs[c] * 100:.1f}" for c in grp) for grp in (CAUSES[:4], CAUSES[4:8], CAUSES[8:]))
        fs = a.get("foliage_of_obstacle", float("nan"))                  # 원판(obstacle) 놓침 가운데 잎 때문 (lost_foliage ÷ obstacle)
        L.append(f"| {name} | {a['started']} | {a['own_contact_s']:.2f} | {a['own_len_s']:.2f} | {a['flee_s_per_deer_min']:.2f} | {parts} | "
                 f"{'—' if fs != fs else f'{fs * 100:.1f}%'} | {a['caught_frac'] * 100:.2f}% | {a['shelter_frac'] * 100:.1f}% | {a['onset_cover'] * 100:.1f}% · {a['onset_shelter'] * 100:.1f}% | "
                 f"{a['hidden_share'] * 100:.1f}% | {a['quiet']} |")
    if "quiet_effect" in s:
        L += ["", "### 끝 규칙 효과 (RUN quiet_end 15 − RUN 지금)", "", "| 배치 | 지역 | P1 차이 초 (t) | 도주 초/사슴-분 차이 | 잡힘 차이 (t) | 5 초 안 다시 차이 |", "|---|---|---|---|---|---|"]
        for lay, by in s["quiet_effect"].items():
            for reg, cm in by.items():
                L.append(f"| {lay} | {reg} | {fnum(cm['p1']['diff'])} ({fnum(cm['p1']['t'])}) | {fnum(cm['flee_s_per_deer_min']['diff'])} | "
                         f"{fnum(cm['caught']['diff'], 2, '%')} ({fnum(cm['caught']['t'])}) | {fnum(cm['refled']['diff'], 1)} |")
    if "set_effect" in s:
        L += ["", f"### 숲 시야 효과 — 세계 덮기 효과 (RUN 덮기 {world_set_text(s.get('world_set') or {})} − 같은 RUN 덮기 없음, 같은 시드)", "",
              "| RUN 팔 | 지역 | P1 덮기 없음 초 | P1 덮기 초 | 차이 (t) | 시작 수 차이 | 도주 초/사슴-분 차이 | 스스로 벗어남 몫 차이 | 원판 놓침 몫 차이 | 잡힘 차이 (t) | 굶음 차이 | 은신처 안 차이 | 5 초 안 다시 차이 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for arm, by in s["set_effect"].items():
            for reg, cm in by.items():
                p = cm["p1"]
                L.append(f"| {arm} | {reg} | {p['b']:.2f} | {p['a']:.2f} | {fnum(p['diff'])} ({fnum(p['t'])}) | {fnum(cm['started']['diff'], 1)} | "
                         f"{fnum(cm['flee_s_per_deer_min']['diff'])} | {fnum(cm['own_share']['diff'], 1, '%')} | {fnum(cm['obstacle_share']['diff'], 1, '%')} | "
                         f"{fnum(cm['caught']['diff'], 2, '%')} ({fnum(cm['caught']['t'])}) | {fnum(cm['starved']['diff'], 2, '%')} | "
                         f"{fnum(cm['shelter']['diff'], 2, '%')} | {fnum(cm['refled']['diff'], 1)} |")
    return L + [""]


def cmd_report(a) -> int:
    out = Path(a.out)
    parts = {}
    for part in PARTS:
        p = out / f"raw_{part}.json"
        if p.exists():
            parts[part] = summarize_part(json.loads(p.read_text(encoding="utf-8")))
    if not parts:
        raise SystemExit(f"{out} 에 raw_*.json 이 없다 — run 부터")
    oracle = oracle_rows(out)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8")) if (out / "meta.json").exists() else {}
    # 세계 덮기 = 부분 raw 파일의 기록(진짜). 부분끼리 다르거나 meta.json(있고 그 칸이 있을 때)과 다르면 멈춘다 — 다른 세계를 한 보고에 섞지 않는다
    ws_parts = {p: s.get("world_set") or {} for p, s in parts.items()}
    wset = next(iter(ws_parts.values()))
    if any(not same_world_set(v, wset) for v in ws_parts.values()):
        raise SystemExit(f"{out} 의 부분끼리 세계 덮기가 다르다 — " + "; ".join(f"{p}: {world_set_text(v)}" for p, v in ws_parts.items())
                         + " (같은 --world-set 으로 다시 재거나 --force 로 그 부분을 다시)")
    if "world_set" in meta and not same_world_set(meta["world_set"], wset):
        raise SystemExit(f"{out}/meta.json 의 세계 덮기 {world_set_text(meta['world_set'])} 가 부분 결과의 덮기 {world_set_text(wset)} 와 다르다 "
                         "— 끊긴 실행이면 같은 명령으로 다시 돌린다")
    plain = any(s.get("plain") for s in parts.values())
    o_note = ""
    if oracle is not None and not same_world_set((oracle.get("meta") or {}).get("world_set", {}), wset):
        # 오라클과 규칙 측정의 세계 덮기가 다르면 판단표에 쓰지 않는다 (다른 세계)
        o_note = (f"오라클 세계 덮기 {world_set_text((oracle.get('meta') or {}).get('world_set', {}))} ≠ 규칙 측정 덮기 "
                  f"{world_set_text(wset)} — 오라클을 판단표에 쓰지 않는다")
        oracle = None
    dec = decide(parts.get("rules"), parts.get("clump"), oracle)
    lv.atomic_write_json(out / "rules.json", lv.jsonable(dict(meta=meta, parts=parts, decision=dec)))
    L = [f"# 도망길 손 규칙 측정 (설계 RL_V3_FLIGHT_ROUTE_DESIGN.md 9절 — 보고만){' — 연기 시험' if meta.get('smoke') else ''}", "",
         f"- 스냅숏 {Path(meta.get('snapshot', '')).name}, 도주 밖 두뇌 {meta.get('model')}, 워커 {meta.get('workers')}, 시간 {json.dumps(meta.get('times', {}), ensure_ascii=False)}",
         f"- 세계 덮기 (--world-set, 모든 팔·비교 기준 RUN 에 같게): {world_set_text(wset)}"
         + (" — 덮기 없음 RUN 팔(plain_…)로 덮기 효과 표를 함께 낸다" if plain else "") + (f". **{o_note}**" if o_note else ""),
         "- P1 = 스스로 벗어난 도망(은신처·원판·시야각·반경)의 쫓긴 시간 시드 평균 (관문 1차와 같은 셈). 차이 = 팔 − 같은 끝 규칙·같은 배치의 RUN. 몫 차이는 %p",
         f"- 쓸모 있음(9-4): 한 지역 이상에서 P1 차이 ≤ −{USEFUL_S} 초 ∧ 짝 t ≤ −{USEFUL_T}, 또는 COVER 원판 놓침 몫 ≥ +{OBST_PP * 100:.0f}%p ∧ P1 이 줄어듦. 잡힘 t ≥ +{CAUGHT_T} 면 빼기", ""]
    titles = dict(rules="규칙 (N 세계, 지금 배치)", clump="덩어리 숲 가정 (N 세계, 측정 전용)", g="게임 세계 G (RUN 대 가장 좋은 규칙)")
    for part, s in parts.items():
        L += fmt_part(s, titles[part])
    L += ["## 9-4 판단표 (위에서부터 읽어 처음으로 '아니오'가 아닌 줄에서 멈춤 — '—'(모름)이면 판단하지 않는다. 잣대: 모든 줄이 P1 = 쫓긴 시간)", "",
          "| 줄 | 결과 | 맞음 | 다음 | 근거 |", "|---|---|---|---|---|"]
    for r in dec["rows"]:
        ev = r["evidence"] if isinstance(r["evidence"], str) else ("; ".join(r["evidence"]) or "—")
        L.append(f"| {r['row']} | {r['cond']} | {'—' if r['hit'] is None else ('예' if r['hit'] else '아니오')} | {r['next']} | {ev} |")
    v = dec["verdict"]
    L += ["", f"**판단: {('줄 ' + str(v['row']) + ' — ' + v['cond'] + ' → ' + v['next']) if v else '아직 정할 수 없다 — 줄 ' + str(dec['pending']) + ' 을 모른다 (모자란 것: ' + '; '.join(dec['missing']) + ')'}**", ""]
    text = "\n".join(L)
    (out / "rules.md").write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    print(f"-> {out / 'rules.json'}, {out / 'rules.md'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="측정 (부분마다 raw_<부분>.json) 뒤 report")
    r.add_argument("--out", required=True)
    r.add_argument("--parts", default="rules,clump,g")
    r.add_argument("--snapshot", default=str(SNAPSHOT))
    r.add_argument("--model", default=None, help="도주 밖 두뇌 (기본: 스냅숏 변환의 시작 zip = obs21zero)")
    r.add_argument("--workers", type=int, default=14)
    r.add_argument("--g-route", default=None, choices=ROUTES)
    r.add_argument("--g-quiet", type=int, default=None)
    r.add_argument("--smoke", action="store_true", help=f"시드 {SMOKE['seeds']} · {SMOKE['steps']} 스텝 · 워커 ≤ {SMOKE['workers']}")
    r.add_argument("--force", action="store_true")
    r.add_argument("--world-set", action="append", default=[], metavar="키=값",
                   help="세계 덮기 (여러 번, 예: features.obstacles.foliage.enabled=true) — 모든 팔·비교 기준 RUN 에 같게 건다")
    r.add_argument("--no-plain", action="store_true", help="덮기가 있어도 '덮기 없음' RUN 팔(덮기 효과 표)을 돌리지 않는다")
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report", help="raw_*.json (+ oracle.json) → rules.json·rules.md·9-4 판단표")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
