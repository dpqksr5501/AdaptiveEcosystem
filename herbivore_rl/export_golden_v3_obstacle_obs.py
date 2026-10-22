"""R5 장애물 관측 골든 내보내기 — 관측 맨 끝 세 칸(escape_room·obstacle_near·threat_hidden)을 언리얼 C++ 와 대조할 골든 헤더를 만든다
(10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 계획서 Docs/RL_Policy/RL_V2_PLAN.md 10-19 (16), 계약 Docs/RL_Policy/POLICY_CONTRACT_V3.md 2-4,
정의는 env_v2/world.py 모듈 docstring 'R5 장애물 관측'·`obstacle_obs_values`).

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다 (C++ 단계 — 그 단계가 빌드·자동 시험과 함께 올린다)
    python export_golden_v3_obstacle_obs.py
    # 파이썬 단계의 올린 사본(results/v3/r5/golden/) 또는 시험용 다른 폴더
    python export_golden_v3_obstacle_obs.py --out results/v3/r5/golden

세계: configs/v3_wild3_obs_mirror.yaml(언리얼과 같은 세계 + 관측 21). 이 내보내기 전용 탐색 시드 32093(무작위 줄기 배치)·32094(장면 난수·롤아웃 세계). 판정 시드는 쓰지 않는다.
C++ 은 사슴 하나마다 (자리, heading, 위협을 아나, away, 가장 가까운 위협 자리, 원판 묶음, 몸 반지름, 무대 한 변, block_sight) → (E, N, 가림) 과 관측 세 칸 float 을
같은 값으로 내야 한다(같은 식·같은 순서라 비트 단위로 같다 — 원시 거리 double 도 같다). 위협 지각(보임·away·가장 가까운 위협)은 지금 C++ PerceiveThreats 가 이미
파이썬과 같으므로 여기서는 그 결과를 입력으로 준다.

묶음:
  설정     거울 설정 obstacle_obs 계수(escape_norm·near_norm)·obstacles.body_r·무대 한 변, 관측 수 21·첫 칸 18·칸 이름, 입출력 계약 해시(관측 21·마스크 판 2).
  원판     묶음 0 = 없음, 1 = 숲 나무 24, 2 = 고지 나무 9(results/v3/wild2/trees/tree_layout.json), 3 = 숲 나무 + 덤불(results/v3/adapt/adapt.py shrub_discs, 1 ha 150 개),
           4 = 무작위 줄기 숲(obstacles 계수 그대로 1 ha 줄기 250 + 바위 5, 시드 32093 자기 스트림 part 0), 5 뒤 = 손 묶음.
  사례     kind 0 손 사례(벽 위·모서리·ux = 0·방향 고르기·원판 앞·접함·비낌·뒤·원판 안에서 시작·겹친 원판·둘레 위·가림의 엄격한 <·끝점·위협 뒤·길이 0·
           block_sight 끔·위협 모름), kind 1 장면(묶음 1~4 세계마다 사슴 64: 무작위 + 벽 위 + 원판 둘레(R + OB_EPS) + 원판 안 + 줄기를 사이에 둔 사슴·늑대 —
           뛰는 늑대라 발소리로만 앎), kind 2 롤아웃(관측 21 숲·덤불 숲 세계에서 지금 게임 두뇌 R1b-F 로 600 스텝 — 결정마다 산 사슴 몇 줄).
  내보내기 전에 세 칸을 C++ 꼴 스칼라 참조(이 파일 `_ref_one`)로 다시 계산해 비트 단위로 같은지 보고, 다르면 멈춘다.
결정성: 시각·절대 경로를 적지 않는다. 같은 코드·설정이면 바이트 단위로 같은 헤더가 나온다(tests/test_obstacle_obs_golden.py).
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

import export_weights_v3 as ew
from env_v2.config import load_v2_config
from env_v2.world import EPS, OB_EPS, OBSTACLE_OBS_NAMES, World, obstacle_layout, obstacle_obs_values

HERE = Path(__file__).resolve().parent
OBS_CFG = HERE / "configs" / "v3_wild3_obs_mirror.yaml"
LAYOUT = HERE / "results" / "v3" / "wild2" / "trees" / "tree_layout.json"
R1BF = HERE / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
DEFAULT_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
HEADER = "ObstacleObsGoldenVectorsV3.h"
SEED_LAYOUT = 32093
SEED_CASE = 32094
JUDGE_SEED_RANGES = ((10000, 10020), (10200, 10220), (12160, 12200), (14000, 14040), (15000, 15040), (10300, 10320), (33000, 33200))
SCENE_DEER = 64
ROLL_STEPS = 600
ROLL_EVERY = 50
ROLL_ROWS = 6
NO_DIST = 1e300                      # 파이썬 inf (원판 없음) — C++ kNoThreatDist 와 같은 표기
KIND_HAND, KIND_SCENE, KIND_ROLL = 0, 1, 2
SHRUB_REGION_INDEX = 1               # 숲 (적응 고리 regions.json 의 region_index — 덤불 배치 난수)


def check_seeds(*seeds) -> None:
    for s in seeds:
        for lo, hi in JUDGE_SEED_RANGES:
            if lo <= int(s) < hi:
                raise SystemExit(f"시드 {s} 는 판정 시드 [{lo}, {hi}) 다 — 골든에 쓰지 않는다")


def d_lit(x) -> str:
    """double 을 다시 읽으면 같은 double 이 되는 가장 짧은 십진 표기 (inf → 1e300)."""
    v = float(x)
    if math.isinf(v):
        return "1e300" if v > 0 else "-1e300"
    if math.isnan(v):
        raise SystemExit("골든에 NaN 이 있다")
    s = repr(v)
    return s if ("." in s or "e" in s) else s + ".0"


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def region_discs() -> dict:
    d = json.loads(LAYOUT.read_text(encoding="utf-8"))
    return {r["region"]: [[float(v) for v in row] for row in r["discs"]] for r in d["regions"]}


# --------------------------------------------------------------------- #
# C++ 꼴 스칼라 참조 (모듈 docstring 'R5 장애물 관측' — 사슴 하나, 원판 순서대로)
# --------------------------------------------------------------------- #


def _ref_one(x, y, hx, hy, seen, awx, awy, tx_, ty_, discs, body_r, size, block):
    if seen and math.sqrt(awx * awx + awy * awy) > EPS:
        wx, wy = awx, awy
    else:
        wx, wy = hx, hy
    nw = math.sqrt(wx * wx + wy * wy)
    ux, uy = (wx / nw, wy / nw) if nw > EPS else (1.0, 0.0)
    tx = (size - x) / ux if ux > 0.0 else (x / (-ux) if ux < 0.0 else math.inf)
    ty = (size - y) / uy if uy > 0.0 else (y / (-uy) if uy < 0.0 else math.inf)
    e = min(tx, ty)
    if not e > 0.0:
        e = 0.0
    near = math.inf
    for cx, cy, r in discs:
        fx, fy = x - cx, y - cy
        R = r + body_r
        cc = fx * fx + fy * fy - R * R
        b = fx * ux + fy * uy
        d = b * b - cc
        if cc >= 0.0 and b < 0.0 and d >= 0.0:
            e = min(e, -b - math.sqrt(d))
        near = min(near, math.sqrt(fx * fx + fy * fy) - R)
    hid = False
    if seen and block:
        dx, dy = x - tx_, y - ty_
        dd = dx * dx + dy * dy
        for cx, cy, r in discs:
            gx, gy = cx - tx_, cy - ty_
            t = (gx * dx + gy * dy) / dd if dd > 0.0 else 0.0
            t = min(max(t, 0.0), 1.0)
            qx = tx_ + t * dx - cx
            qy = ty_ + t * dy - cy
            if qx * qx + qy * qy < r * r:
                hid = True
                break
    return e, near, hid


def _obs3(e, near, hid, en, nn):
    o1 = min(max(e / en, 0.0), 1.0)
    o2 = min(max((near if near > 0.0 else 0.0) / nn, 0.0), 1.0)
    return [np.float32(o1), np.float32(o2), np.float32(1.0 if hid else 0.0)]


# --------------------------------------------------------------------- #
# 원판 묶음
# --------------------------------------------------------------------- #


class DiscSets:
    def __init__(self):
        self.index: list[tuple[int, int]] = []
        self.flat: list[float] = []
        self.arrays: list[np.ndarray] = []

    def add(self, discs) -> int:
        a = np.asarray(discs, dtype=np.float64).reshape(-1, 3)
        self.index.append((len(self.flat) // 3, len(a)))
        self.flat += [float(v) for v in a.reshape(-1)]
        self.arrays.append(a)
        return len(self.index) - 1

    def get(self, k: int) -> np.ndarray:
        return self.arrays[k]


def world_for(discs, n: int, seed: int, region: str = "Forest") -> World:
    c = _with(load_v2_config(OBS_CFG).replace(N=int(n)), obstacles=dict(fixed=[list(map(float, d)) for d in discs]),
              wild_weather=dict(region=region))
    w = World(c, seeds=[int(seed)])
    w.keep_pair_vis = True
    return w


# --------------------------------------------------------------------- #
# 사례
# --------------------------------------------------------------------- #


def hand_cases(sets: DiscSets, size: float) -> list[dict]:
    """손 사례 (묶음은 사례마다 새로 더한다 — 0 은 원판 없음)."""
    s = math.sqrt(0.5)
    out = []

    def case(p, h, seen, away, threat, set_k, body, block=True, sz=size):
        out.append(dict(kind=KIND_HAND, set=set_k, p=[float(p[0]), float(p[1])], h=[float(h[0]), float(h[1])], seen=bool(seen),
                        away=[float(away[0]), float(away[1])], threat=[float(threat[0]), float(threat[1])], body=float(body), size=float(sz),
                        block=bool(block)))

    z = [0.0, 0.0]
    # 벽·방향 (원판 없음)
    case([10, 20], [1, 0], False, z, z, 0, 0.15)
    case([10, 20], [-1, 0], False, z, z, 0, 0.15)
    case([10, 20], [0, 1], False, z, z, 0, 0.15)            # ux = 0
    case([10, 20], [0, -1], False, z, z, 0, 0.15)
    case([0, 20], [-1, 0], False, z, z, 0, 0.15)            # 벽 위에서 벽 쪽 → 0
    case([60, 60], [1, 1], False, z, z, 0, 0.15)            # 모서리
    case([10, 20], [s, s], False, z, z, 0, 0.15)            # 대각선
    case([10, 20], [0.6, -0.8], False, z, z, 0, 0.15)
    case([10, 20], [1, 0], True, [-1, 0], [12, 20], 0, 0.15)            # 위협을 알면 away
    case([10, 20], [1, 0], True, [0, 0], [10, 20], 0, 0.15)             # away 0 → heading
    case([10, 20], [0, 0], False, z, z, 0, 0.15)                        # heading 0 → (1, 0)
    case([10, 20], [0, 1], False, [-1, 0], [12, 20], 0, 0.15)           # 모르면 away 를 읽지 않음
    case([10, 20], [1e-10, 0], False, z, z, 0, 0.15)                    # heading 길이 1e-9 밑 → (1, 0)
    case([30, 30], [1, 0], True, [3e-10, 4e-10], [30, 30], 0, 0.15)     # away 길이 5e-10 → heading
    # 원판 (몸 0.5)
    one = sets.add([[20, 10, 1.0]])
    case([10, 10], [1, 0], False, z, z, one, 0.5)                       # 앞: 8.5
    case([10, 10], [1, 0], False, z, z, sets.add([[20, 11.5, 1.0]]), 0.5)   # 접함 Δ = 0
    case([10, 10], [1, 0], False, z, z, sets.add([[20, 11.6, 1.0]]), 0.5)   # 비낌
    case([10, 10], [1, 0], False, z, z, sets.add([[0, 10, 1.0]]), 0.5)      # 뒤
    case([20.5, 10], [1, 0], False, z, z, one, 0.5)                     # 원판 안에서 시작 — 건너뜀, N < 0
    case([10, 10], [1, 0], False, z, z, sets.add([[30, 10, 1.0], [20, 10, 1.0], [25, 10, 3.0]]), 0.5)   # 겹친 원판
    rim = 20 - 1.5 - OB_EPS
    case([rim, 10], [1, 0], False, z, z, one, 0.5)                      # 둘레 위(미끄러지는 사슴) 원판 쪽
    case([rim, 10], [-1, 0], False, z, z, one, 0.5)                     # 둘레 위 멀어지는 쪽
    case([10, 10], [s, s], False, z, z, sets.add([[14, 14, 0.4], [14, 13, 0.4], [40, 40, 2.0]]), 0.15)
    # 가림 (늑대 (0, 10) → 사슴 (10, 10), 몸 0.15)
    wolf, me, away = [0, 10], [10, 10], [1, 0]
    for discs in ([[5, 10, 0.5]], [[5, 10.5, 0.5]], [[5, 10.49, 0.5]], [[12, 10, 0.5]], [[-2, 10, 0.5]], [[11.9, 10.2, 0.5]], [[10.3, 10, 0.5]]):
        case(me, [1, 0], True, away, wolf, sets.add(discs), 0.15)
    k = sets.add([[5, 10, 0.5]])
    case(me, [1, 0], False, away, wolf, k, 0.15)                        # 위협 모름
    case(me, [1, 0], True, away, wolf, k, 0.15, block=False)            # block_sight 끔
    case(me, [1, 0], True, z, me, sets.add([[10.1, 10, 0.5]]), 0.15)    # 길이 0, 위협 자리가 원판 안
    case(me, [1, 0], True, z, me, sets.add([[11, 10, 0.5]]), 0.15)      # 길이 0, 밖
    case(me, [1, 0], True, away, wolf, 0, 0.15)                         # 원판 없음
    return out


def _scene_state(w, rng) -> None:
    """사슴·늑대 자리: 무작위 + 벽 위 + 원판 둘레(R + OB_EPS) + 원판 안 + 줄기를 사이에 둔 사슴·늑대(뛰는 늑대 — 발소리). 늑대는 깨어 있다."""
    N, S = w.N, w.size
    D = w.obstacles
    b = float(w._ob["body_r"])
    pos = rng.uniform(0.0, S, (N, 2))
    ang = rng.uniform(0.0, 2 * np.pi, N)
    head = np.stack([np.cos(ang), np.sin(ang)], 1)
    for i in range(6):
        pos[i, i % 2] = 0.0 if i % 4 < 2 else S
        head[i] = -head[i] if rng.random() < 0.5 else head[i]
    if len(D):
        for i in range(6, 14):
            k = int(rng.integers(len(D)))
            a = rng.uniform(0, 2 * np.pi)
            pos[i] = D[k, :2] + (D[k, 2] + b + OB_EPS) * np.array([np.cos(a), np.sin(a)])
            head[i] = -np.array([np.cos(a), np.sin(a)]) if i % 2 == 0 else head[i]
        for i in range(14, 17):
            k = int(rng.integers(len(D)))
            pos[i] = D[k, :2] + 0.3 * D[k, 2]
    w.pos = np.clip(pos, 0.0, S)
    w.head = head
    w.pred_pos = np.clip(w.pos[rng.integers(0, N, w.M)] + rng.normal(0.0, 4.0, (w.M, 2)), 0.0, S)
    if len(D):
        for m in range(min(w.M, 3)):
            k = int(rng.integers(len(D)))
            a = rng.uniform(0, 2 * np.pi)
            u = np.array([np.cos(a), np.sin(a)])
            w.pos[N - 1 - m] = np.clip(D[k, :2] + (D[k, 2] + b + 3.0) * u, 0.0, S)
            w.pred_pos[m] = np.clip(D[k, :2] - (D[k, 2] + 3.0) * u, 0.0, S)
    w.pred_vel = np.tile([w.cfg.herb_speed, 0.0], (w.M, 1))
    if hasattr(w, "pred_running"):
        w.pred_running[:] = True
    w.pred_asleep[:] = False


def _rows_from(w, g, set_k: int, kind: int, rows) -> list[dict]:
    """세계 기하 g 의 행 rows → 사례 (지각 결과를 입력으로, 세계가 낸 원시 거리·관측을 출력으로)."""
    P = w.pos
    ex = w.pred_pos[:, 0][None, :] - P[:, 0:1]
    ey = w.pred_pos[:, 1][None, :] - P[:, 1:2]
    pd = np.sqrt(ex * ex + ey * ey)
    j = np.where(g["wf_pvis"], pd, np.inf).argmin(1)
    seen = np.isfinite(g["d_pred_min"])
    o = w._obs_from(g)
    k0 = w._obs_oo
    out = []
    for i in rows:
        i = int(i)
        out.append(dict(kind=kind, set=set_k, p=[float(P[i, 0]), float(P[i, 1])], h=[float(w.head[i, 0]), float(w.head[i, 1])], seen=bool(seen[i]),
                        away=[float(g["away_from_pred"][i, 0]), float(g["away_from_pred"][i, 1])],
                        threat=[float(w.pred_pos[j[i], 0]), float(w.pred_pos[j[i], 1])] if seen[i] else [0.0, 0.0],
                        body=float(w._ob["body_r"]), size=float(w.size), block=bool(w._ob["block_sight"]),
                        world=dict(e=float(g["ob_escape"][i]), n=float(g["ob_near"][i]), hid=bool(g["ob_hidden"][i]),
                                   obs=[np.float32(v) for v in o[i, k0:k0 + 3]])))
    return out


def scene_cases(sets: DiscSets, set_ids: list[int], rng) -> list[dict]:
    out = []
    for k in set_ids:
        w = world_for(sets.get(k), SCENE_DEER, SEED_CASE)
        _scene_state(w, rng)
        g = w._geometry()
        out += _rows_from(w, g, k, KIND_SCENE, range(w.N))
    return out


class _Head18:
    """두뇌(관측 18 모델)에게 세계 관측 앞 18 칸만 보이는 창(results/v3/r5/obs_check.py 와 같다)."""

    def __init__(self, w, k: int):
        self._w = w
        self._k = k
        self.obs_names = tuple(w.obs_names[:k])

    def observe(self):
        return self._w.observe()[:, :self._k]

    def __getattr__(self, name):
        return getattr(self._w, name)


def rollout_cases(sets: DiscSets, set_ids: list[int], rng) -> list[dict]:
    from env_v2 import rollout as ro

    out = []
    if not R1BF.exists():
        raise SystemExit(f"롤아웃 사례에 게임 두뇌 모델이 필요하다: {R1BF}")
    for k in set_ids:
        w = world_for(sets.get(k), 128, SEED_CASE)
        pol = ro.build_policy({"kind": "rep_learned", "path": str(R1BF)}, SEED_CASE)
        ro.forward_bind(pol, _Head18(w, w._obs_oo))
        for t in range(1, ROLL_STEPS + 1):
            w.step(np.asarray(pol(w.observe()[:, :w._obs_oo]), dtype=np.float64))
            if t % ROLL_EVERY:
                continue
            live = np.flatnonzero(w.alive)
            seen = np.isfinite(w._g["d_pred_min"])[live]
            # 위협을 아는 행을 먼저(가림·도주 방향을 시험), 나머지는 무작위
            pick = list(live[seen][:ROLL_ROWS // 2]) + list(rng.choice(live, ROLL_ROWS - min(ROLL_ROWS // 2, int(seen.sum())), replace=False))
            out += _rows_from(w, w._g, k, KIND_ROLL, pick)
    return out


def finish(cases: list[dict], sets: DiscSets, en: float, nn: float) -> dict:
    """사례마다 `obstacle_obs_values`(세계와 같은 함수)·스칼라 참조로 계산해 비트 단위로 같은지 본다. 세계 사례는 세계 값과도."""
    n_hid = n_seen = n_zero = n_one = 0
    for c in cases:
        d = sets.get(c["set"])
        e, n, h = obstacle_obs_values(np.array([c["p"]]), np.array([c["h"]]), np.array([c["seen"]]), np.array([c["away"]]),
                                      np.array([c["threat"]]), d, c["body"], c["size"], c["block"])
        r = _ref_one(*c["p"], *c["h"], c["seen"], *c["away"], *c["threat"], [tuple(map(float, x)) for x in d], c["body"], c["size"], c["block"])
        if not (float(e[0]) == r[0] and float(n[0]) == r[1] and bool(h[0]) == r[2]):
            raise SystemExit(f"세계 함수와 스칼라 참조가 다르다: {c} → {(e[0], n[0], h[0])} 대 {r}")
        obs = _obs3(r[0], r[1], r[2], en, nn)
        if "world" in c:
            wv = c["world"]
            if not (wv["e"] == r[0] and wv["n"] == r[1] and wv["hid"] == r[2] and all(a == b for a, b in zip(wv["obs"], obs))):
                raise SystemExit(f"세계 관측이 스칼라 참조와 다르다: {c}")
        c["out"] = dict(e=r[0], n=r[1], hid=r[2], obs=obs)
        n_hid += int(r[2])
        n_seen += int(c["seen"])
        n_zero += int(obs[0] == 0.0)
        n_one += int(obs[0] == 1.0)
    return dict(hidden=n_hid, seen=n_seen, escape_zero=n_zero, escape_one=n_one)


# --------------------------------------------------------------------- #
# 헤더
# --------------------------------------------------------------------- #


def build_header() -> str:
    check_seeds(SEED_LAYOUT, SEED_CASE)
    cfg = load_v2_config(OBS_CFG)
    f = cfg.v2["features"]
    oo, ob = f["obstacle_obs"], f["obstacles"]
    en, nn, body = float(oo["escape_norm"]), float(oo["near_norm"]), float(ob["body_r"])
    from env_v2.world import obs_names

    names = obs_names(cfg)
    k0 = list(names).index(OBSTACLE_OBS_NAMES[0])
    if len(names) != 21 or k0 != 18 or tuple(names[18:]) != OBSTACLE_OBS_NAMES:
        raise SystemExit(f"관측 21 계약이 아니다: {names}")
    chash = ew.contract_hash(names, 2)
    probe = World(cfg.replace(N=8), seeds=[SEED_CASE])
    size = float(probe.size)
    covers = np.c_[probe.cov_c, probe.cov_r]
    regions = region_discs()
    sys.path.insert(0, str(HERE / "results" / "v3" / "adapt"))
    import adapt

    sets = DiscSets()
    sets.add([])                                                     # 0 없음
    forest = sets.add(regions["Forest"])                             # 1
    highland = sets.add(regions["Highland"])                         # 2
    brush = sets.add(regions["Forest"] + adapt.shrub_discs(SHRUB_REGION_INDEX, size, covers.tolist()))   # 3
    lay = dict(tree_per_ha=float(ob["tree_per_ha"]), tree_r=list(ob["tree_r"]), rock_per_ha=float(ob["rock_per_ha"]), rock_r=list(ob["rock_r"]),
               body_r=body)
    from env_v2.features import feature_stream

    trunk = sets.add(obstacle_layout(feature_stream(SEED_LAYOUT, "obstacles", 0), size, probe.cov_c, probe.cov_r, lay))   # 4
    rng = np.random.default_rng(SEED_CASE)
    cases = hand_cases(sets, size)
    n_hand = len(cases)
    cases += scene_cases(sets, [forest, highland, brush, trunk], rng)
    n_scene = len(cases) - n_hand
    cases += rollout_cases(sets, [forest, brush], rng)
    n_roll = len(cases) - n_hand - n_scene
    st = finish(cases, sets, en, nn)
    if st["hidden"] == 0 or st["seen"] == 0 or st["escape_zero"] == 0:
        raise SystemExit(f"사례가 가림·위협·벽 0 을 시험하지 않는다: {st}")

    ci, cd, co, coi, cf = [], [], [], [], []
    for c in cases:
        ci += [c["kind"], c["set"], int(c["seen"]), int(c["block"])]
        cd += c["p"] + c["h"] + c["away"] + c["threat"] + [c["body"], c["size"]]
        co += [c["out"]["e"], c["out"]["n"]]
        coi += [int(c["out"]["hid"])]
        cf += c["out"]["obs"]
    arr = ew.c_array
    L = [
        "// 자동 생성 — herbivore_rl/export_golden_v3_obstacle_obs.py (손으로 고치지 않는다). 세계 configs/v3_wild3_obs_mirror.yaml, 시드 32093·32094.",
        "// R5 장애물 관측 골든 (계약 Docs/RL_Policy/POLICY_CONTRACT_V3.md 2-4, 정의 herbivore_rl/env_v2/world.py 'R5 장애물 관측'·obstacle_obs_values).",
        f"// 사례 {len(cases)} = 손 {n_hand} · 장면 {n_scene} · 롤아웃 {n_roll}. 가림 {st['hidden']} · 위협을 앎 {st['seen']} · escape_room 0 {st['escape_zero']} · 1 {st['escape_one']}.",
        "// 허용: 원시 거리 double 과 관측 float 모두 비트 단위로 같다(같은 식·같은 순서).",
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace EcoObservationV3::GoldenObstacleObs",
        "{",
        "\t// ---- 설정 (거울 설정 obstacle_obs·obstacles 계수 — C++ 관측 설정 기본값과 같아야 한다) ----",
        f"\tinline constexpr std::int32_t kObsDim = {len(names)};",
        f"\tinline constexpr std::int32_t kFirstSlot = {k0};",
        f"\tinline constexpr const char* kSlotNames[3] = {{{', '.join(chr(34) + n + chr(34) for n in OBSTACLE_OBS_NAMES)}}};",
        f"\tinline constexpr std::uint64_t kContractHashObs21Mask2 = 0x{chash:016x}ULL;   // export_weights_v3.contract_hash(관측 21, 마스크 판 2)",
        f"\tinline constexpr double kEscapeNorm = {d_lit(en)};",
        f"\tinline constexpr double kNearNorm = {d_lit(nn)};",
        f"\tinline constexpr double kBodyR = {d_lit(body)};",
        f"\tinline constexpr double kStageSize = {d_lit(size)};",
        f"\tinline constexpr double kEps = {d_lit(EPS)};",
        f"\tinline constexpr double kNoDist = {d_lit(NO_DIST)};   // N 이 ∞(원판 없음)",
        "",
        "\t// ---- 원판 묶음: kSetIndex[2k..] = (시작 원판, 수), kSetDiscs[3·원판..] = (x, y, r). 0 없음·1 숲 24·2 고지 9·3 숲 + 덤불·4 무작위 줄기 숲, 5 뒤 손 ----",
        f"\tinline constexpr std::int32_t kSets = {len(sets.index)};",
        arr("std::int32_t", "kSetIndex", [v for t in sets.index for v in t], 16, ew._i32),
        arr("double", "kSetDiscs", sets.flat if sets.flat else [0.0], 6, d_lit),
        "",
        "\t// ---- 사례 c: kCaseInt[4c..] = (종류 0 손·1 장면·2 롤아웃, 원판 묶음, 위협을 앎, block_sight),",
        "\t//      kCaseIn[10c..] = (x, y, hx, hy, away x, away y, 위협 x, 위협 y — 위협을 모르면 0, 몸 반지름, 무대 한 변),",
        "\t//      출력 kCaseOut[2c..] = (E, N — ∞ 는 kNoDist), kCaseHidden[c], kCaseObs[3c..] = 관측 세 칸 float ----",
        f"\tinline constexpr std::int32_t kCases = {len(cases)};",
        f"\tinline constexpr std::int32_t kHandCases = {n_hand};",
        f"\tinline constexpr std::int32_t kSceneCases = {n_scene};",
        f"\tinline constexpr std::int32_t kRolloutCases = {n_roll};",
        f"\tinline constexpr std::int32_t kHiddenCases = {st['hidden']};",
        arr("std::int32_t", "kCaseInt", ci, 16, ew._i32),
        arr("double", "kCaseIn", cd, 5, d_lit),
        arr("double", "kCaseOut", co, 6, d_lit),
        arr("std::int32_t", "kCaseHidden", coi, 40, ew._i32),
        arr("float", "kCaseObs", cf, 6, ew.f32_lit),
        "}",
        "",
    ]
    return "\n".join(L)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    out = a.out if a.out.is_absolute() else Path.cwd() / a.out
    out.mkdir(parents=True, exist_ok=True)
    path = out / HEADER
    path.write_text(build_header(), encoding="utf-8", newline="\n")
    print(f"썼다: {path}")


if __name__ == "__main__":
    main()
