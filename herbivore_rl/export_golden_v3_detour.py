"""v3 야생 2단계 3 의 6) 장애물 돌아가기 골든 내보내기 — world.py `detour_moves`·`_step_predators_v3` 의 돌아가기·돕기 그만둠을 언리얼 C++
`EcoThreatModel.h` (DetourStep·DetourCandidate·Step 7′·8″·PackPeek)·`EcoWorldV3.h` (FObstacleConfig::Detour, C1 사슴 돌아가기)와 대조할 골든 헤더를 만든다
(명세 `Docs/RL_Policy/RL_V3_WILD2_SPEC.md` 7절 '골든').

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_detour.py
    # 시험용 다른 폴더
    python export_golden_v3_detour.py --out <폴더>

세계·시드: configs/v3_wild2_obstacle_mirror.yaml (돌아가기 켬). 이 내보내기 전용 탐색 시드 32090(장면 난수)·32091(한 스텝 장면 세계)·32092(궤적)과
장애물 골든과 같은 거울 배치 32095. 판정 시드는 쓰지 않는다.

묶음:
  한 번      `detour_moves` 한 개체: (원판 묶음, p, v, 상태 (left, side, steps), 사슴 여부, 은신처 막기 원 묶음) → (새 v, 고른 방향, 상태, 썼나·시작·못 찾음).
             손 장면(정면 줄기·비스듬·이어 돌기·앞 보기 트임·두 줄기 V 자·벽과 줄기 사이·둘러싸임·멈춤·은신처 막기 원·무대 밖 후보·마지막 스텝) + 거울 배치
             난수 장면 + 빽빽한 무리 난수 장면
  궤적       한 개체가 목표 자리 쪽으로(속력 그대로) T 스텝: 스텝마다 detour_moves → 이동(사슴 clip + 미끄러짐 size, 늑대 미끄러짐). 스텝마다 위치·상태
  한 스텝    거울 세계(사슴 24, 늑대 4 = 잠행 2·추격 2)의 상태를 장면마다 정해(돌아가기 상태·돕지 않는 남은 스텝 포함) `World._step_predators_v3` 를 한 번 부른다.
             출력은 늑대 위치·heading·돕기·원판 돌아섬·돌아가기 상태·돕지 않는 남은 스텝과 썼나·시작·못 찾음·그만둠.
             C++ 은 PackPeek → PackGoals → Step(In.Detour) 을 늑대 순서로 불러 같은 값을 내야 한다(EcoWorldV3 C2 와 같은 순서).
"""

from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path

import numpy as np

from env_v2 import repertoire as rep
from env_v2.world import (DETOUR_CAND_K, DETOUR_CAND_SG, DETOUR_HALF, DETOUR_ORDER_FRESH, DETOUR_ORDER_NEG, DETOUR_ORDER_POS, DETOUR_ROT,
                          PT_CHASER, PT_STALKER, ST_EXHAUST, ST_POUNCE, ST_ROAM, World, detour_moves, obstacle_inside, obstacle_push_out,
                          obstacle_slide)
import export_golden_v3_obstacle as eo

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = eo.DEFAULT_OUT
SEED_CASE = 32090
SEED_STEP = 32091
SEED_PATH = 32092
N_STEP = 24
STEP_SCENES = 80
CASE_RANDOM = 600
CASE_DENSE = 200
CASE_WALL = 240
PATH_RANDOM = 24
PATH_STEPS = 60
MARGIN = 0.5            # 은신처 막기 원 = 은신처 반지름 + 늑대 몸 여유 (거울 설정 realism_shelter.wolf_margin)

d_lit, c_array, DiscSets = eo.d_lit, eo.c_array, eo.DiscSets


def detour_params() -> dict:
    """거울 설정의 돌아가기 계수 (world.py `_obstacles_params` 의 detour)."""
    w = World(eo.obst_config(detour=True).replace(N=8), seeds=[eo.SEED_LAYOUT])
    dp = w._ob["detour"]
    if dp is None:
        raise SystemExit("v3_wild2_obstacle_mirror.yaml 은 obstacles.detour 를 켜야 한다")
    if abs(w._zw_m - MARGIN) > 0.0:
        raise SystemExit(f"거울 설정 늑대 몸 여유가 {MARGIN} 이 아니다: {w._zw_m}")
    return dict(dp)


def run_one(c: dict, d: np.ndarray, walls, body: float, dp: dict) -> dict:
    """한 번: detour_moves 한 개체."""
    left = np.array([c["st"][0]], dtype=np.int64)
    side = np.array([c["st"][1]], dtype=np.int64)
    steps = np.array([c["st"][2]], dtype=np.int64)
    v, dirs, used, start, fail = detour_moves(c["p"][None, :], c["v"][None, :], left, side, steps, d, body, c["size"], c["deer"], dp,
                                              walls, None if walls is None else np.ones(1, dtype=bool))
    return dict(v=v[0], dir=dirs[0], st=(int(left[0]), int(side[0]), int(steps[0])), used=bool(used[0]), start=bool(start[0]), fail=bool(fail[0]))


def one_cases(sets: DiscSets, mirror: int, size: float, body: float, covers: np.ndarray, rng) -> tuple[list[dict], int, list]:
    """한 번 장면들. 은신처 막기 원 묶음은 walls 목록(번호 = 묶음 번호, −1 없음)."""
    out = []
    wall_sets: list[np.ndarray] = []

    def wall(w):
        wall_sets.append(np.asarray(w, dtype=np.float64).reshape(-1, 3))
        return len(wall_sets) - 1

    def case(k, p, v, st=(0, 0, 0), deer=True, sz=20.0, wl=-1):
        out.append(dict(set=k, p=np.asarray(p, float), v=np.asarray(v, float), st=tuple(int(x) for x in st), deer=bool(deer), size=float(sz), wall=wl))

    one = sets.add([[10.0, 10.0, 0.1]])
    R = 0.1 + body
    case(one, [10.0 - R - 0.1, 10.0], [0.24, 0.0])                       # 정면 줄기(걷기): 0.1 가서 닿음 → 막힘 → +1 단계부터
    case(one, [10.0 - R - 0.1, 10.0], [0.6, 0.0])                        # 정면(뛰기)
    case(one, [10.0 - R - 0.05, 10.0], [0.6, 0.0], deer=False)           # 늑대 정면
    case(one, [10.0 - R - 0.1, 10.0 + 0.2], [0.24, 0.0])                 # 비스듬 — 많이 가서 막힘 아님(그대로)
    case(one, [10.0 - R - 0.1, 10.0 - 0.05], [0.24, 0.0])                # 조금 비켜 정면 — 막힘, 가까운 쪽(−)
    case(one, [10.0 + R + 0.01, 10.0], [0.24, 0.0], st=(10, 1, 3))       # 돌아가는 중, 멀어짐 → 앞 보기 트임 → 끝, 보통(그대로)
    case(one, [10.0 - R - 0.01, 10.0], [0.24, 0.0], st=(10, -1, 5))      # 돌아가는 중, 앞 보기 닿음 → 붙은 쪽(−) 먼저
    case(one, [10.0 - R - 0.01, 10.0], [0.24, 0.0], st=(10, 1, 5))       # 같은 자리, 붙은 쪽 +
    case(one, [10.0 - R - 0.01, 10.0], [0.24, 0.0], st=(1, 1, 44))       # 마지막 돌아가기 스텝 (left 1 → 0)
    case(one, [10.0 - R - 0.1, 10.0], [0.0, 0.0], st=(7, 1, 2))          # 멈춤 → 상태 0
    case(one, [10.0 - R - 0.1, 10.0], [1e-12, 0.0], st=(7, -1, 2))       # 거의 멈춤 (≤ EPS)
    pair = sets.add([[10.0, 10.0, 0.1], [10.0, 10.45, 0.1]])
    case(pair, [9.6, 10.225], [0.24, 0.0])                               # 두 줄기 V 자 (겹친 몸 여유) — 정면
    case(pair, [9.6, 10.225], [0.6, 0.0])
    case(pair, [9.74, 10.225], [0.24, 0.0], st=(20, 1, 8))               # V 자 안쪽 깊이, 돌아가는 중
    case(pair, [9.6, 10.225], [0.24, 0.0], deer=False)
    edge = sets.add([[0.3, 10.0, 0.1]])
    case(edge, [0.02, 9.6], [0.0, 0.24], sz=20.0)                        # 벽과 줄기 사이 (사슴 — 무대 자르기)
    case(edge, [0.02, 9.6], [-0.1, 0.4], deer=False, sz=20.0)            # 늑대 — 무대 밖 후보는 빈 방향이 아니다
    ring = sets.add([[10.0 + 0.62 * math.cos(a), 10.0 + 0.62 * math.sin(a), 0.2] for a in np.linspace(0.0, 2.0 * math.pi, 12, endpoint=False)])
    case(ring, [10.0, 10.0], [0.6, 0.0])                                 # 둘러싸임 — 빈 방향 없음(못 찾음, v 그대로)
    case(ring, [10.0, 10.0], [0.24, 0.1], st=(5, 1, 2))
    rock = sets.add([[20.0, 20.0, 0.6]])
    wl = wall([[20.0, 21.6, 0.5 + MARGIN]])
    case(rock, [20.0 - 0.75 - 0.1, 20.0], [0.48, 0.0], deer=False, sz=40.0, wl=wl)   # 늑대: + 쪽 빈 방향이 은신처 막기 원 안 → 다른 쪽
    case(rock, [20.0 - 0.75 - 0.1, 20.0], [0.48, 0.0], deer=True, sz=40.0)           # 사슴은 은신처를 피하지 않는다
    case(rock, [20.0 - 0.75 - 0.01, 20.0 + 0.05], [0.72, 0.0], deer=False, sz=40.0, wl=wl)
    tri = sets.add([[5.0, 5.0, 0.15], [5.5, 5.0, 0.15], [5.25, 5.45, 0.15]])
    case(tri, [3.0 + 1.85, 5.22], [0.6, 0.0])                            # 세 줄기 무리
    case(tri, [5.25, 4.5], [0.0, 0.24], st=(3, -1, 9))
    n_hand = len(out)
    d = sets.get(mirror)
    cw = wall(np.c_[covers[:, :2], covers[:, 2] + MARGIN])
    for _ in range(CASE_RANDOM):
        for _t in range(100):
            k = int(rng.integers(0, len(d)))
            a = rng.uniform(0.0, 2.0 * math.pi)
            p = d[k, :2] + (d[k, 2] + body + rng.uniform(0.002, 0.45)) * np.array([math.cos(a), math.sin(a)])
            if 0.0 <= p.min() and p.max() <= size and not obstacle_inside(p[None, :], d, body)[0]:
                break
        to = d[k, :2] - p
        to = to / max(np.linalg.norm(to), 1e-12)
        ang = rng.normal(0.0, 0.5)
        c, s = math.cos(ang), math.sin(ang)
        deer = bool(rng.random() < 0.5)
        sp = rng.choice([0.24, 0.6, 0.096, 0.15]) if deer else rng.choice([0.48, 0.72, 0.144, 0.0384])
        v = np.array([to[0] * c - to[1] * s, to[0] * s + to[1] * c]) * sp
        u = rng.random()
        st = (0, 0, 0) if u < 0.5 else (int(rng.integers(1, 45)), int(rng.choice([-1, 1])), int(rng.integers(1, 30)))
        case(mirror, p, v, st=st, deer=deer, sz=size, wl=cw if (not deer and rng.random() < 0.6) else -1)
    # 은신처 둘레 곁 줄기: 늑대가 줄기에 미끄러져 은신처 막기 원으로 밀려 들어가는 막힘(나아감은 block 이상)이 생기게
    cov_w = np.c_[covers[:, :2], covers[:, 2] + MARGIN]
    near = [k for k in range(len(d)) if (np.abs(np.sqrt(((cov_w[:, :2] - d[k, :2]) ** 2).sum(1)) - cov_w[:, 2]) < d[k, 2] + body + 0.6).any()]
    for _ in range(CASE_WALL if near else 0):
        k = near[int(rng.integers(0, len(near)))]
        j = int(np.argmin(np.abs(np.sqrt(((cov_w[:, :2] - d[k, :2]) ** 2).sum(1)) - cov_w[:, 2])))
        out_n = (d[k, :2] - cov_w[j, :2]) / max(np.linalg.norm(d[k, :2] - cov_w[j, :2]), 1e-12)   # 은신처 중심 → 줄기
        tang = np.array([-out_n[1], out_n[0]]) * (1.0 if rng.random() < 0.5 else -1.0)
        for _t in range(50):
            p = d[k, :2] - tang * (d[k, 2] + body + rng.uniform(0.02, 0.3)) + out_n * rng.uniform(-0.25, 0.1)
            if (0.0 <= p.min() and p.max() <= size and not obstacle_inside(p[None, :], d, body)[0]
                    and not (np.sqrt(((cov_w[:, :2] - p) ** 2).sum(1)) < cov_w[:, 2]).any()):
                break
        else:
            continue
        ang = rng.normal(0.0, 0.35)
        c, s = math.cos(ang), math.sin(ang)
        v = np.array([tang[0] * c - tang[1] * s, tang[0] * s + tang[1] * c]) * rng.choice([0.48, 0.72, 0.144])
        st = (0, 0, 0) if rng.random() < 0.7 else (int(rng.integers(1, 45)), int(rng.choice([-1, 1])), int(rng.integers(1, 30)))
        case(mirror, p, v, st=st, deer=False, sz=size, wl=cw)
    for _ in range(CASE_DENSE):
        n = int(rng.integers(8, 15))
        dd = np.c_[rng.uniform(4.0, 7.0, (n, 2)), rng.uniform(0.05, 0.4, n)]
        k = sets.add(dd)
        for _t in range(200):
            p = rng.uniform(3.5, 7.5, 2)
            if not obstacle_inside(p[None, :], dd, body)[0]:
                break
        else:
            continue
        v = rng.normal(0.0, 1.0, 2)
        v = v / max(np.linalg.norm(v), 1e-12) * rng.uniform(0.1, 0.8)
        st = (0, 0, 0) if rng.random() < 0.5 else (int(rng.integers(1, 45)), int(rng.choice([-1, 1])), int(rng.integers(1, 30)))
        case(k, p, v, st=st, deer=bool(rng.random() < 0.5), sz=10.0)
    return out, n_hand, wall_sets


def path_cases(sets: DiscSets, mirror: int, size: float, body: float, rng) -> list[dict]:
    """궤적: (원판 묶음, 시작 p, 목표 g, 속력, 사슴 여부, 무대 한 변, 스텝 수)."""
    out = []

    def case(k, p, g, sp, deer=True, sz=20.0, n=PATH_STEPS):
        out.append(dict(set=k, p=np.asarray(p, float), g=np.asarray(g, float), sp=float(sp), deer=bool(deer), size=float(sz), n=int(n)))

    pair = sets.add([[10.0, 10.0, 0.1], [10.0, 10.45, 0.1]])
    case(pair, [8.0, 10.225], [13.0, 10.225], 0.24)                     # V 자 너머 목표 (걷는 사슴)
    case(pair, [8.0, 10.225], [13.0, 10.225], 0.6)
    case(pair, [8.0, 10.225], [13.0, 10.225], 0.48, deer=False)
    rock = sets.add([[10.0, 10.0, 0.7], [10.9, 10.9, 0.12], [9.2, 10.95, 0.1]])
    case(rock, [7.0, 10.0], [13.0, 10.2], 0.24)                         # 바위 너머 (줄기 둘 곁)
    case(rock, [7.0, 10.0], [13.0, 10.0], 0.48, deer=False)
    edge = sets.add([[0.3, 10.0, 0.1], [0.75, 10.3, 0.1]])
    case(edge, [0.05, 8.0], [0.05, 13.0], 0.24)                         # 벽을 따라 줄기 두 개 사이로
    d = sets.get(mirror)
    for _ in range(PATH_RANDOM):
        for _t in range(100):
            k = int(rng.integers(0, len(d)))
            a = rng.uniform(0.0, 2.0 * math.pi)
            p = d[k, :2] + (d[k, 2] + body + rng.uniform(0.3, 1.5)) * np.array([math.cos(a), math.sin(a)])
            if 1.0 <= p.min() and p.max() <= size - 1.0 and not obstacle_inside(p[None, :], d, body)[0]:
                break
        g = np.clip(2.0 * d[k, :2] - p + rng.normal(0.0, 0.3, 2), 0.0, size)   # 원판 너머 맞은편
        deer = bool(rng.random() < 0.6)
        case(mirror, p, g, rng.choice([0.24, 0.6]) if deer else rng.choice([0.48, 0.72]), deer=deer, sz=size, n=40)
    return out


def run_path(c: dict, d: np.ndarray, body: float, dp: dict) -> list[dict]:
    p = c["p"].copy()
    left = np.zeros(1, dtype=np.int64)
    side = np.zeros(1, dtype=np.int64)
    steps = np.zeros(1, dtype=np.int64)
    rows = []
    for _ in range(c["n"]):
        to = c["g"] - p
        n = math.sqrt(to[0] * to[0] + to[1] * to[1])
        v = (to / n * c["sp"]) if n > c["sp"] else np.zeros(2)
        v2, _, used, _, _ = detour_moves(p[None, :], v[None, :], left, side, steps, d, body, c["size"], c["deer"], dp)
        if c["deer"]:
            q, _, _ = obstacle_slide(p[None, :], np.clip(p[None, :] + v2, 0.0, c["size"]), d, body, c["size"])
        else:
            q, _, _ = obstacle_slide(p[None, :], p[None, :] + v2, d, body)
        p = q[0].copy()
        rows.append(dict(p=p.copy(), st=(int(left[0]), int(side[0]), int(steps[0])), used=bool(used[0])))
    return rows


def step_world() -> World:
    w = World(eo.obst_config(detour=True).replace(N=N_STEP), seeds=[SEED_STEP])
    if w._ob is None or w._ob["detour"] is None or w._wp is None or w.M != 4 or w.alive is None or not len(w.obstacles):
        raise SystemExit("v3_wild2_obstacle_mirror.yaml 은 원판·돌아가기·늑대 4·wild_pack 켬·부활 없음이어야 한다")
    if w._zc is not None or w._sd is not None or w._zt is not None or w._pred_ranged_v1.any():
        raise SystemExit("한 스텝 장면은 추격 고정·노려보기·지형·원거리형이 없어야 한다(C++ 위협 모델에 없다)")
    return w


def step_scenes():
    """export_golden_v3_obstacle.py 의 한 스텝 장면 + 돌아가기 상태·돕지 않는 남은 스텝. 늑대를 원판 둘레 바로 밖에서 원판 쪽으로 더 자주 둔다."""
    w = step_world()
    rng = np.random.default_rng(SEED_STEP)
    S, M, N = w.size, w.M, w.N
    rp, disc, body = w._rp, w.obstacles, w._ob["body_r"]
    out = []
    for s in range(STEP_SCENES):
        q = np.zeros((M, 2))
        for m in range(M):
            for _ in range(400):
                c = rng.uniform(0.0, S, 2)
                if not w._rz_inside_disc(c[None, :])[0] and not obstacle_inside(c[None, :], disc, body)[0]:
                    break
            q[m] = c
        ang = rng.uniform(0, 2 * np.pi, M)
        head = np.stack([np.cos(ang), np.sin(ang)], 1)
        cd = np.zeros(M, dtype=np.int64)
        sat = np.zeros(M, dtype=np.int64)
        st = np.full(M, ST_ROAM, dtype=np.int8)
        left = np.zeros(M, dtype=np.int64)
        for m in range(M):
            u = rng.random()
            if u < 0.06:
                cd[m] = int(rng.integers(1, 39))
            elif u < 0.10:
                sat[m] = int(rng.integers(1, 451))
            elif u < 0.26 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_POUNCE, int(rng.integers(0, 13))
            elif u < 0.30 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_EXHAUST, int(rng.integers(1, 31))
        p = rng.uniform(0.0, S, (N, 2))
        for i in range(min(10, N)):
            m = int(rng.integers(0, M))
            p[i] = np.clip(q[m] + head[m] * rng.uniform(1.0, 14.0) + rng.normal(0.0, 2.0, 2), 0.0, S)
        p, _, _ = obstacle_push_out(p, disc, body, S)
        mv = rng.normal(0.0, 1.0, (N, 2))
        mv = mv / np.maximum(np.linalg.norm(mv, axis=1, keepdims=True), 1e-9) * rng.choice([0.0, 0.24, 0.6], (N, 1), p=[0.2, 0.3, 0.5])
        for m in range(M):
            if rng.random() < 0.6:
                for _t in range(50):
                    k = int(rng.integers(0, len(disc)))
                    a = rng.uniform(0.0, 2.0 * math.pi)
                    u = np.array([math.cos(a), math.sin(a)])
                    c = disc[k, :2] + (disc[k, 2] + body + rng.uniform(0.002, 0.3)) * u
                    if (0.0 <= c.min() and c.max() <= S and not w._rz_inside_disc(c[None, :])[0]
                            and not obstacle_inside(c[None, :], disc, body)[0]):
                        q[m] = c
                        b = rng.normal(0.0, 0.1)
                        head[m] = np.array([-u[0] * math.cos(b) + u[1] * math.sin(b), -u[0] * math.sin(b) - u[1] * math.cos(b)])
                        break
        dl = np.where(rng.random(M) < 0.4, rng.integers(1, 45, M), 0).astype(np.int64)
        ds = np.where(dl > 0, rng.choice([-1, 1], M), 0).astype(np.int64)
        dst = np.where(dl > 0, rng.integers(1, 30, M), 0).astype(np.int64)
        pdrop = np.where(rng.random(M) < 0.2, rng.integers(1, 39, M), 0).astype(np.int64)
        dslow = np.where(rng.random(M) < 0.3, rng.integers(1, 20, M), 0).astype(np.int64)
        w.pos = p.copy()
        w._pack_p0 = p - mv
        w._rs.behavior[:] = rep.GRAZE
        w._rep_still = np.zeros(N, dtype=bool)
        w._rep_cover = rep.cover_mult(rp, w._rs.behavior, np.zeros(N, dtype=bool))
        w.alive = np.ones(N, dtype=bool)
        w.pred_pos, w.pred_head = q.copy(), head.copy()
        w.pred_cd, w.pred_sat = cd.copy(), sat.copy()
        w.stalk_state, w.stalk_left = st.copy(), left.copy()
        w.pred_asleep = np.zeros(M, dtype=bool)
        w._pred_speed_mult = np.ones(M)
        w.dark = 0.0
        w._zn_hunt = np.zeros(M, dtype=bool)
        w._hunt_on = np.zeros(M, dtype=bool)
        w.pred_det_left, w.pred_det_side, w.pred_det_steps = dl.copy(), ds.copy(), dst.copy()
        w.pack_drop = pdrop.copy()
        w.pred_det_slow = dslow.copy()
        in_cov = w._in_cover(w.pos)
        turns = copy.deepcopy(w.rng).uniform(-w.cfg.pred_wander_turn, w.cfg.pred_wander_turn, M)
        drop0 = w._det_help_drop
        w._step_predators_v3()
        # 그만둠: 남은 스텝이 detour_help_drop 로 막 찼다(입력 남은 스텝은 그보다 작고 −1 된다) ∧ 이번 스텝에 도왔다. 셈과 같아야 한다
        dropped = (w.pack_drop == w._ob["detour"]["help_drop"]) & w.pack_help
        if (w.pred_det_slow[dropped] != 0).any() or (pdrop > w._ob["detour"]["help_drop"]).any():
            raise SystemExit("돕기 그만둠 장면 입력이 맞지 않다")
        if int(np.count_nonzero(dropped)) != w._det_help_drop - drop0:
            raise SystemExit("돕기 그만둠 셈이 훅과 다르다")
        out.append(dict(q=q, head=head, cd=cd, sat=sat, st=st, left=left, p=p, mv=w.pos - w._pack_p0, in_cov=in_cov, turns=turns,
                        dl=dl, ds=ds, dst=dst, pdrop=pdrop, dslow=dslow,
                        q1=w.pred_pos.copy(), head1=w.pred_head.copy(), help=w.pack_help.copy(), dead=w.pred_ob_dead.copy(),
                        dl1=w.pred_det_left.copy(), ds1=w.pred_det_side.copy(), dst1=w.pred_det_steps.copy(), pdrop1=w.pack_drop.copy(),
                        dslow1=w.pred_det_slow.copy(),
                        used=w.pred_det_used.copy(), drop=dropped))
    consts = dict(size=S, kinds=w.pred_type.copy(), cov=np.c_[w.cov_c, w.cov_r], margin=w._zw_m, eat_cd=int(w.cfg.pred_eat_cd),
                  sat_steps=int(w._ws_sat_steps), M=M, N=N, pred_speed_mult=float(w.pred_speed_mult), discs=disc.copy(), body=body,
                  sight=bool(w._ob["block_sight"]))
    return out, consts


def build_header() -> str:
    dp = detour_params()
    op = eo.mirror_params()
    body = float(op["body_r"])
    layout, size, covers = eo.mirror_layout(op)
    rng = np.random.default_rng(SEED_CASE)
    sets = DiscSets()
    mirror = sets.add(layout)
    ones, n_hand, wall_sets = one_cases(sets, mirror, size, body, covers, rng)
    paths = path_cases(sets, mirror, size, body, np.random.default_rng(SEED_PATH))
    steps, sc = step_scenes()
    n_sets = len(sets.index)
    L = [
        "// 자동 생성 — herbivore_rl/export_golden_v3_detour.py (손으로 고치지 않는다). 세계 configs/v3_wild2_obstacle_mirror.yaml (돌아가기 켬), 시드 32090·32091·32092·32095.",
        "// v3 야생 2단계 3 의 6) 장애물 돌아가기 골든 (명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md 7절). 검사는 Tests/DetourGoldenCheckV3.h (AdaptiveEcosystem.Policy.V3.Obstacle.Detour*).",
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace EcoWorldV3::GoldenDetour",
        "{",
        "\t// 거울 설정 obstacles.detour_* (C++ FDetourConfig 기본값과 같아야 한다 — 켬 칸만 기본 끔)와 몸 반지름",
        f"\tinline constexpr double kCfgBlock = {d_lit(dp['block'])};",
        f"\tinline constexpr double kCfgFree = {d_lit(dp['free'])};",
        f"\tinline constexpr double kCfgProbe = {d_lit(dp['probe'])};",
        f"\tinline constexpr std::int32_t kCfgSteps = {dp['steps']};",
        f"\tinline constexpr std::int32_t kCfgHelpBlock = {dp['help_block']};",
        f"\tinline constexpr std::int32_t kCfgHelpDrop = {dp['help_drop']};",
        f"\tinline constexpr double kCfgBodyR = {d_lit(body)};",
        "\t// 돌리기 (cos, sin) k = 0..8 (world.py DETOUR_ROT), 후보 단계·쪽, 차례 (처음·붙은 쪽 +·−)",
        c_array("double", "kRot", [x for row in DETOUR_ROT for x in row], 6, d_lit),
        f"\tinline constexpr std::int32_t kHalf = {DETOUR_HALF};",
        c_array("std::int32_t", "kCandK", list(DETOUR_CAND_K), 15, str),
        c_array("std::int32_t", "kCandSg", list(DETOUR_CAND_SG), 15, str),
        c_array("std::int32_t", "kOrderFresh", list(DETOUR_ORDER_FRESH), 15, str),
        c_array("std::int32_t", "kOrderPos", list(DETOUR_ORDER_POS), 15, str),
        c_array("std::int32_t", "kOrderNeg", list(DETOUR_ORDER_NEG), 15, str),
        "",
        "\t// ---- 원판 묶음: kSetIndex[2k..] = (시작 원판, 수), kSetDiscs[3·원판..] = (x, y, r). 묶음 0 = 거울 세계 배치 (시드 32095) ----",
        f"\tinline constexpr std::int32_t kSets = {n_sets};",
        c_array("std::int32_t", "kSetIndex", [v for t in sets.index for v in t], 16, str),
        c_array("double", "kSetDiscs", sets.flat, 6, d_lit),
        "\t// 은신처 막기 원 묶음 (x, y, r + 늑대 몸 여유): kWallIndex[2k..] = (시작 원, 수)",
    ]
    wi, wd = [], []
    for wsx in wall_sets:
        wi += [len(wd) // 3, len(wsx)]
        wd += [float(x) for x in wsx.reshape(-1)]
    L += [f"\tinline constexpr std::int32_t kWalls = {len(wall_sets)};", c_array("std::int32_t", "kWallIndex", wi, 16, str),
          c_array("double", "kWallDiscs", wd, 6, d_lit)]
    # 한 번
    oi, od, oo, ooi = [], [], [], []
    nu = ns = nf = nwall = 0
    for c in ones:
        d = sets.get(c["set"])
        walls = wall_sets[c["wall"]] if c["wall"] >= 0 else None
        r = run_one(c, d, walls, body, dp)
        if walls is not None and not c["deer"]:
            # 은신처 둘레 막힘만으로 막힌 사례(나아감은 block 이상인데 미끄러진 끝이 은신처 막기 원 안)
            q, hit, _ = obstacle_slide(c["p"][None, :], c["p"][None, :] + c["v"][None, :], d, body)
            sp = math.sqrt(c["v"][0] * c["v"][0] + c["v"][1] * c["v"][1])
            if sp > 1e-9 and hit[0]:
                g = ((q[0, 0] - c["p"][0]) * (c["v"][0] / sp) + (q[0, 1] - c["p"][1]) * (c["v"][1] / sp)) / sp
                inw = bool((np.sqrt(((walls[:, :2] - q[0]) ** 2).sum(1)) < walls[:, 2]).any())
                nwall += int(g >= dp["block"] and inw and c["st"][0] == 0)
        oi += [c["set"], c["wall"], int(c["deer"]), c["st"][0], c["st"][1], c["st"][2]]
        od += [c["p"][0], c["p"][1], c["v"][0], c["v"][1], c["size"]]
        oo += [r["v"][0], r["v"][1], r["dir"][0], r["dir"][1]]
        ooi += [r["st"][0], r["st"][1], r["st"][2], int(r["used"]), int(r["start"]), int(r["fail"])]
        nu += int(r["used"])
        ns += int(r["start"])
        nf += int(r["fail"])
    if nwall == 0:
        raise SystemExit("은신처 둘레 막힘 사례가 없다 — CASE_WALL 장면을 늘린다")
    L += [
        "",
        "\t// ---- 한 번 (world.py detour_moves 한 개체): kOneInt[6s..] = (원판 묶음, 은신처 막기 원 묶음 −1 없음, 사슴, left, side, steps),",
        "\t//      kOneIn[5s..] = (px, py, vx, vy, 무대 한 변). 출력 kOneOut[4s..] = (새 vx, vy, 고른 방향 x, y), kOneOutI[6s..] = (left, side, steps, 썼나, 시작, 못 찾음).",
        "\t//      앞 kOneHand 개는 손 장면 ----",
        f"\tinline constexpr std::int32_t kOneCases = {len(ones)};",
        f"\tinline constexpr std::int32_t kOneHand = {n_hand};",
        f"\tinline constexpr std::int32_t kOneUsed = {nu};",
        f"\tinline constexpr std::int32_t kOneStarts = {ns};",
        f"\tinline constexpr std::int32_t kOneFails = {nf};",
        f"\tinline constexpr std::int32_t kOneWallBlocks = {nwall};   // 은신처 둘레 막힘만으로 막힌 늑대 사례 (참고)",
        c_array("std::int32_t", "kOneInt", oi, 18, str),
        c_array("double", "kOneIn", od, 5, d_lit),
        c_array("double", "kOneOut", oo, 4, d_lit),
        c_array("std::int32_t", "kOneOutI", ooi, 18, str),
    ]
    # 궤적
    pi_, pd, po, poi = [], [], [], []
    pu = 0
    for c in paths:
        d = sets.get(c["set"])
        rows = run_path(c, d, body, dp)
        pi_ += [c["set"], int(c["deer"]), c["n"], len(po) // 2]
        pd += [c["p"][0], c["p"][1], c["g"][0], c["g"][1], c["sp"], c["size"]]
        for r in rows:
            po += [r["p"][0], r["p"][1]]
            poi += [r["st"][0], r["st"][1], r["st"][2], int(r["used"])]
            pu += int(r["used"])
    L += [
        "",
        "\t// ---- 궤적 (목표 쪽으로 속력 그대로, 목표 속력 거리 안이면 멈춤): kPathInt[4s..] = (원판 묶음, 사슴, 스텝 수, 출력 시작 줄),",
        "\t//      kPathIn[6s..] = (px, py, gx, gy, 속력, 무대 한 변). 출력 줄마다 kPathOut[2r..] = 위치, kPathOutI[4r..] = (left, side, steps, 썼나) ----",
        f"\tinline constexpr std::int32_t kPathCases = {len(paths)};",
        f"\tinline constexpr std::int32_t kPathRows = {len(po) // 2};",
        f"\tinline constexpr std::int32_t kPathUsed = {pu};",
        c_array("std::int32_t", "kPathInt", pi_, 16, str),
        c_array("double", "kPathIn", pd, 6, d_lit),
        c_array("double", "kPathOut", po, 4, d_lit),
        c_array("std::int32_t", "kPathOutI", poi, 16, str),
    ]
    # 한 스텝
    M, N = sc["M"], sc["N"]
    kinds = [int(x) for x in sc["kinds"]]
    if kinds != [PT_STALKER, PT_CHASER, PT_STALKER, PT_CHASER]:
        raise SystemExit(f"늑대 구성이 잠행·추격 번갈아가 아니다: {kinds}")
    in_d, in_i, prey_s, out_sd, out_si = [], [], [], [], []
    used = drops = deads = helps = 0
    for t in steps:
        for m in range(M):
            in_d += [t["q"][m, 0], t["q"][m, 1], t["head"][m, 0], t["head"][m, 1], t["turns"][m]]
            in_i += [int(t["cd"][m]), int(t["sat"][m]), int(t["st"][m]), int(t["left"][m]), int(t["dl"][m]), int(t["ds"][m]), int(t["dst"][m]),
                     int(t["pdrop"][m]), int(t["dslow"][m])]
            out_sd += [t["q1"][m, 0], t["q1"][m, 1], t["head1"][m, 0], t["head1"][m, 1]]
            out_si += [int(t["help"][m]), int(t["dead"][m]), int(t["dl1"][m]), int(t["ds1"][m]), int(t["dst1"][m]), int(t["pdrop1"][m]),
                       int(t["used"][m]), int(t["drop"][m]), int(t["dslow1"][m])]
            used += int(t["used"][m])
            drops += int(t["drop"][m])
            deads += int(t["dead"][m])
            helps += int(t["help"][m])
        for i in range(N):
            prey_s += [t["p"][i, 0], t["p"][i, 1], t["mv"][i, 0], t["mv"][i, 1], float(t["in_cov"][i])]
    L += [
        "",
        "\t// ---- 한 스텝 장면 (world.py _step_predators_v3 돌아가기 켬, 늑대 4 = 순번 짝수 잠행·홀수 추격, 사슴 모두 먹기, 낮 d = 0) ----",
        f"\tinline constexpr std::int32_t kStepScenes = {len(steps)};",
        f"\tinline constexpr std::int32_t kStepWolves = {M};",
        f"\tinline constexpr std::int32_t kStepPrey = {N};",
        f"\tinline constexpr double kStepWorldSize = {d_lit(sc['size'])};",
        f"\tinline constexpr double kStepPredSpeedMult = {d_lit(sc['pred_speed_mult'])};",
        f"\tinline constexpr double kStepWolfMargin = {d_lit(sc['margin'])};",
        f"\tinline constexpr std::int32_t kStepEatCd = {sc['eat_cd']};",
        f"\tinline constexpr std::int32_t kStepSatSteps = {sc['sat_steps']};",
        f"\tinline constexpr std::int32_t kStepSight = {int(sc['sight'])};",
        f"\tinline constexpr std::int32_t kStepUsed = {used};",
        f"\tinline constexpr std::int32_t kStepDrops = {drops};",
        f"\tinline constexpr std::int32_t kStepDeads = {deads};",
        f"\tinline constexpr std::int32_t kStepHelps = {helps};",
        f"\tinline constexpr std::int32_t kStepCoverCount = {len(sc['cov'])};",
        c_array("double", "kStepCover", [v for row in sc["cov"] for v in row], 6, d_lit),
        f"\tinline constexpr std::int32_t kStepDiscCount = {len(sc['discs'])};",
        c_array("double", "kStepDiscs", [v for row in sc["discs"] for v in row], 6, d_lit),
        "\t// 늑대 (장면 s·늑대 m = s·4 + m): 입력 (x, y, hx, hy, 배회 선회), (쿨다운, 배부름, 잠행 상태, 남은 수, 돌아가기 left, side, steps, 돕지 않는 남은 스텝,",
        "\t// 느린 스텝)",
        c_array("double", "kStepWolfIn", in_d, 5, d_lit),
        c_array("std::int32_t", "kStepWolfInI", in_i, 18, str),
        "\t// 사슴 (장면 s·사슴 i = s·N + i): (x, y, 이동 x, 이동 y, 은신처 안 0/1)",
        c_array("double", "kStepPreyIn", prey_s, 5, d_lit),
        "\t// 출력 늑대: (x, y, hx, hy), (돕기, 돌아섬, 돌아가기 left, side, steps, 돕지 않는 남은 스텝, 돌아가기 썼나, 돕기 그만둠, 느린 스텝)",
        c_array("double", "kStepWolfOut", out_sd, 4, d_lit),
        c_array("std::int32_t", "kStepWolfOutI", out_si, 18, str),
        "}",
        "",
    ]
    if len(sets.index) != n_sets:
        raise SystemExit("원판 묶음 목록을 쓴 뒤에 묶음을 더했다")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / "DetourGoldenVectorsV3.h"
    path.write_text(build_header(), encoding="utf-8", newline="\n")
    print(f"썼다: {path}")


if __name__ == "__main__":
    main()
