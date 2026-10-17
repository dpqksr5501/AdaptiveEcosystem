"""v3 야생 2단계 3 골든 내보내기 — 세로 장애물(obstacles)을 언리얼 C++ `EcoThreatModel.h` (ObstacleSlide·SightBlocked·InsideAnyObstacle·
Step 의 표적 가림과 이동)·`EcoWorldV3.h` (FObstacleConfig·ObstaclePushOut·FFoodGrid::ApplyObstacleFood)와 대조할 골든 헤더를 만든다
(명세 `Docs/RL_Policy/RL_V3_WILD2_SPEC.md` 6절 '골든').

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_obstacle.py
    # 시험용 다른 폴더
    python export_golden_v3_obstacle.py --out <폴더>

세계·시드: configs/v3_wild2_obstacle_mirror.yaml. 이 내보내기 전용 탐색 시드 32095(원판 배치)·32096(장면 난수)·32097(한 스텝 장면). 판정 시드는 쓰지 않는다.

묶음:
  미끄러짐  `obstacle_slide` 의 (원판 묶음, 이동 전 p, 가려던 q, 맵 자르기 여부) → (새 q, 부딪힘, 물러남). 손 장면(정면·비스듬·겹친 두 원판·가는 원판
            뚫기·멀어짐·제자리·벽과 원판 사이 구석·원판 안에서 시작) + 거울 배치 난수 장면 + 빽빽한 원판 무리 난수 장면
  시선      `sight_blocked` 한 쌍 (원판 묶음, a, b) → 가림. 손 장면(꼭 r 만큼 떨어진 선분 — 엄격한 <, 끝점 뒤 원판, 길이 0) + 난수 장면
  먹이      `obstacle_food_factor` 로 줄인 용량 (격자 30 × 30, 셀 2): 처음 용량(난수)과 줄인 용량. 거울 배치 + 손 배치(표본점에 꼭 닿는 원판·셀을 다 덮는
            바위·맵 모서리 원판)
  밀어내기  `obstacle_push_out` 한 개체 (원판 묶음, p, 늑대 여부·은신처 막기 원) → (새 p, 결과 0 그대로·1 옮김·2 못 옮김)
  한 스텝   거울 세계(사슴 24, 늑대 4 = 잠행 2·추격 2, 원판 = 그 세계의 배치)의 상태를 장면마다 정해 `World._step_predators_v3` 를 한 번 부른다(낮 d = 0,
            사슴은 모두 먹기). 출력은 늑대 위치·heading·쿨다운·배부름·잠행 상태·남은 수·돕기·표적·잡은 사슴·원판 부딪힘·되돌림·돌아섬.
            C++ 은 PackPeek → PackGoals → Step 을 늑대 순서로 불러 같은 값을 내야 한다(EcoWorldV3 C2 와 같은 순서, 원판은 미리 보기에도 넘긴다).
"""

from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path

import numpy as np

from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import (OB_EPS, OB_PASSES, OB_SAMPLES, PT_CHASER, PT_STALKER, ST_EXHAUST, ST_POUNCE, ST_ROAM, World,
                          obstacle_food_factor, obstacle_inside, obstacle_push_out, obstacle_slide, sight_blocked)

HERE = Path(__file__).resolve().parent
OBST = HERE / "configs" / "v3_wild2_obstacle_mirror.yaml"
DEFAULT_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
SEED_LAYOUT = 32095
SEED_CASE = 32096
SEED_STEP = 32097
N_STEP = 24
STEP_SCENES = 80
SLIDE_RANDOM = 400
SLIDE_DENSE = 150
SIGHT_RANDOM = 400
PUSH_RANDOM = 160
GW, CELL = 30, 2.0


def d_lit(x) -> str:
    """double 리터럴: 파이썬 repr (다시 읽으면 같은 float64 가 되는 가장 짧은 표기)."""
    x = float(x)
    if not math.isfinite(x):
        raise SystemExit(f"헤더에 유한하지 않은 값: {x}")
    s = repr(x)
    return s if ("." in s or "e" in s or "inf" in s) else s + ".0"


def c_array(ctype: str, name: str, flat: list, per_line: int, fmt) -> str:
    if not flat:
        raise SystemExit(f"{name} 가 비었다 — C++ 배열은 크기 0 일 수 없다")
    lines = [f"\tinline constexpr {ctype} {name}[{len(flat)}] = {{"]
    for k in range(0, len(flat), per_line):
        lines.append("\t\t" + ", ".join(fmt(v) for v in flat[k:k + per_line]) + ",")
    lines.append("\t};")
    return "\n".join(lines)


def mirror_params() -> dict:
    cfg = load_v2_config(OBST)
    op = dict(cfg.v2["features"]["obstacles"])
    op.pop("enabled")
    return op


def mirror_layout(op: dict) -> tuple[np.ndarray, float, np.ndarray]:
    """거울 세계(시드 SEED_LAYOUT)의 원판 배치·무대 한 변·은신처 원 (x, y, r)."""
    w = World(load_v2_config(OBST).replace(N=8), seeds=[SEED_LAYOUT])
    if w._ob is None or not len(w.obstacles):
        raise SystemExit("v3_wild2_obstacle_mirror.yaml 은 obstacles 를 켜고 원판이 있어야 한다")
    return w.obstacles.copy(), float(w.size), np.c_[w.cov_c, w.cov_r]


# --------------------------------------------------------------------- #
# 원판 묶음 (장면이 번호로 가리킨다)
# --------------------------------------------------------------------- #


class DiscSets:
    def __init__(self):
        self.flat: list[float] = []
        self.index: list[tuple[int, int]] = []   # (시작 원판, 수)

    def add(self, d) -> int:
        d = np.asarray(d, dtype=np.float64).reshape(-1, 3)
        self.index.append((len(self.flat) // 3, len(d)))
        self.flat += [float(v) for v in d.reshape(-1)]
        return len(self.index) - 1

    def get(self, k: int) -> np.ndarray:
        s, n = self.index[k]
        return np.asarray(self.flat[3 * s:3 * (s + n)], dtype=np.float64).reshape(-1, 3)


def slide_cases(sets: DiscSets, mirror: int, size: float, body: float, rng) -> list[dict]:
    out = []

    def case(k, p, q, sz):
        out.append(dict(set=k, p=np.asarray(p, float), q=np.asarray(q, float), size=float(sz)))

    one = sets.add([[10.0, 10.0, 0.5]])
    case(one, [8.0, 10.0], [9.5, 10.0], -1.0)                 # 정면: 남은 이동이 모두 안쪽 — 닿은 자리에서 멈춘다
    case(one, [8.0, 9.8], [9.5, 9.8], -1.0)                   # 비스듬: 둘레를 따라 미끄러진다
    case(one, [8.0, 10.0], [12.0, 10.0], -1.0)                # 뚫고 지나가려는 긴 이동
    case(one, [10.0, 10.66], [10.0, 11.5], -1.0)              # 둘레 곁에서 멀어짐(b ≥ 0) — 안 닿는다
    case(one, [8.0, 10.0], [8.0, 10.0], -1.0)                 # 제자리
    case(one, [10.1, 10.0], [10.6, 10.0], -1.0)               # 원판 안에서 시작 — 그 원판은 건너뛴다 → 끝도 안이라 물러남
    case(one, [8.0, 8.0], [12.0, 12.0], 20.0)                 # 대각선 정면, 맵 자르기
    thin = sets.add([[5.0, 5.0, 0.05]])
    case(thin, [4.0, 5.01], [6.0, 5.01], -1.0)                # 가는 원판(줄기) 뚫기 막음
    case(thin, [4.0, 5.3], [6.0, 5.3], -1.0)                  # 몸 여유 밖으로 지나감
    pair = sets.add([[10.0, 10.0, 0.4], [10.0, 10.9, 0.4]])
    case(pair, [8.0, 10.45], [11.0, 10.45], -1.0)             # 겹친 두 원판 사이 V 자 — 되풀이
    case(pair, [8.0, 10.2], [11.5, 10.6], -1.0)
    wall = sets.add([[0.3, 10.0, 0.4]])
    case(wall, [0.0, 8.0], [0.0, 10.5], 20.0)                 # 벽과 원판 사이 구석: 잘라서 원판 안 → 닿은 자리로 물러남
    case(wall, [0.5, 8.0], [-0.2, 10.5], 20.0)
    corner = sets.add([[0.2, 0.2, 0.3]])
    case(corner, [1.0, 1.0], [0.0, 0.0], 20.0)                # 맵 모서리
    tri = sets.add([[5.0, 5.0, 0.3], [5.7, 5.0, 0.3], [5.35, 5.6, 0.3]])
    case(tri, [3.0, 5.2], [6.0, 5.4], -1.0)                   # 세 원판 무리
    case(tri, [5.35, 4.0], [5.35, 6.5], -1.0)
    n_hand = len(out)
    d = sets.get(mirror)
    for _ in range(SLIDE_RANDOM):
        # 거울 배치: 원판 하나 곁(둘레 밖 0~1.2 단위)에서 그 원판 쪽으로 기울인 이동 (사슴 걷기 0.24·뛰기 0.6, 늑대 0.96·돌진 1.5)
        for _t in range(100):
            k = int(rng.integers(0, len(d)))
            a = rng.uniform(0.0, 2.0 * math.pi)
            p = d[k, :2] + (d[k, 2] + body + rng.uniform(0.01, 1.2)) * np.array([math.cos(a), math.sin(a)])
            if 0.0 <= p.min() and p.max() <= size and not obstacle_inside(p[None, :], d, body)[0]:
                break
        to = d[k, :2] - p
        to = to / max(np.linalg.norm(to), 1e-12)
        ang = rng.normal(0.0, 0.6)
        c, s = math.cos(ang), math.sin(ang)
        v = np.array([to[0] * c - to[1] * s, to[0] * s + to[1] * c]) * rng.choice([0.24, 0.6, 0.96, 1.5])
        sz = size if rng.random() < 0.5 else -1.0
        q = p + v
        if sz > 0:
            q = np.clip(q, 0.0, sz)
        case(mirror, p, q, sz)
    for _ in range(SLIDE_DENSE):
        # 빽빽한 무리: 원판 8~14 개를 3 단위 상자에 몰아 둔다
        n = int(rng.integers(8, 15))
        dd = np.c_[rng.uniform(4.0, 7.0, (n, 2)), rng.uniform(0.05, 0.6, n)]
        k = sets.add(dd)
        for _t in range(200):
            p = rng.uniform(3.0, 8.0, 2)
            if not obstacle_inside(p[None, :], dd, body)[0]:
                break
        else:
            continue
        v = rng.normal(0.0, 1.0, 2)
        v = v / max(np.linalg.norm(v), 1e-12) * rng.uniform(0.2, 2.0)
        case(k, p, p + v, -1.0 if rng.random() < 0.5 else 10.0)
    return out, n_hand


def sight_cases(sets: DiscSets, mirror: int, size: float, rng) -> tuple[list[dict], int]:
    out = []

    def case(k, a, b):
        out.append(dict(set=k, a=np.asarray(a, float), b=np.asarray(b, float)))

    one = sets.add([[10.0, 10.0, 0.5]])
    case(one, [8.0, 10.5], [12.0, 10.5])           # 꼭 r 만큼 떨어진 선분 — 엄격한 < 라 안 가린다
    case(one, [8.0, 10.49], [12.0, 10.49])         # 조금 안쪽 — 가린다
    case(one, [8.0, 10.0], [9.0, 10.0])            # 원판 앞에서 끝남
    case(one, [12.0, 10.0], [11.0, 10.0])          # 반대쪽 앞에서 끝남
    case(one, [8.0, 8.0], [8.0, 8.0])              # 길이 0
    case(one, [8.0, 8.0], [12.0, 12.0])            # 대각선으로 가운데
    case(one, [10.0, 8.0], [10.0, 9.5])            # 끝점이 꼭 둘레 위 — 가린다(가장 가까운 거리 0.5 < 0.5 아님 → 안 가림)
    n_hand = len(out)
    d = sets.get(mirror)
    for _ in range(SIGHT_RANDOM):
        a = rng.uniform(0.0, size, 2)
        b = a + rng.normal(0.0, 1.0, 2) / 1.0 * rng.uniform(0.5, 25.0)
        case(mirror, a, np.clip(b, 0.0, size))
    return out, n_hand


def push_cases(sets: DiscSets, mirror: int, size: float, body: float, covers: np.ndarray, rng) -> tuple[list[dict], int]:
    out = []

    def case(k, p, wolf, sz, cov=None, margin=0.0):
        out.append(dict(set=k, p=np.asarray(p, float), wolf=bool(wolf), size=float(sz),
                        cov=np.zeros((0, 3)) if cov is None else np.asarray(cov, float).reshape(-1, 3), margin=float(margin)))

    one = sets.add([[10.0, 10.0, 0.5]])
    case(one, [10.2, 10.1], False, 20.0)            # 바깥쪽 지름 방향으로
    case(one, [10.0, 10.0], False, 20.0)            # 중심과 겹침 — (1, 0) 쪽
    case(one, [9.0, 10.0], False, 20.0)             # 밖 — 그대로
    edge = sets.add([[0.3, 10.0, 0.6]])
    case(edge, [0.2, 10.0], False, 20.0)            # 지름 방향 후보가 맵 밖 → 링 후보
    pair = sets.add([[10.0, 10.0, 0.5], [10.9, 10.0, 0.5]])
    case(pair, [10.45, 10.0], False, 20.0)          # 겹친 두 원판 사이
    box = sets.add([[1.0, 1.0, 1.5]])
    case(box, [1.0, 1.0], False, 2.0)               # 무대를 다 덮음 — 못 옮김
    wolfc = sets.add([[10.0, 10.0, 0.5]])
    case(wolfc, [10.6, 10.0], True, 20.0, cov=[[12.0, 10.0, 1.0]], margin=0.5)   # 늑대: 지름 방향 후보가 은신처 막기 원 안 → 다른 후보
    case(wolfc, [10.6, 10.0], False, 20.0, cov=[[12.0, 10.0, 1.0]], margin=0.5)  # 사슴은 은신처를 피하지 않는다
    n_hand = len(out)
    d = sets.get(mirror)
    for _ in range(PUSH_RANDOM):
        k = int(rng.integers(0, len(d)))
        p = d[k, :2] + rng.uniform(-1.0, 1.0, 2) * (d[k, 2] + body)
        p = np.clip(p, 0.0, size)
        case(mirror, p, rng.random() < 0.5, size, cov=covers, margin=0.5)
    return out, n_hand


def run_push(c, d, body):
    walls = np.c_[c["cov"][:, :2], c["cov"][:, 2] + c["margin"]] if c["wolf"] and len(c["cov"]) else None
    q, moved, failed = obstacle_push_out(c["p"][None, :], d, body, c["size"], walls)
    code = 0 if (moved + failed) == 0 else (1 if moved else 2)
    return q[0], code


# --------------------------------------------------------------------- #
# 한 스텝 장면 (export_golden_v3_pack.py 의 한 스텝 장면 + 원판)
# --------------------------------------------------------------------- #


def step_world() -> World:
    w = World(load_v2_config(OBST).replace(N=N_STEP), seeds=[SEED_STEP])
    if w._ob is None or w._wp is None or w.M != 4 or w.alive is None or not len(w.obstacles):
        raise SystemExit("v3_wild2_obstacle_mirror.yaml 은 원판·늑대 4·wild_pack 켬·부활 없음이어야 한다")
    if w._zc is not None or w._sd is not None or w._zt is not None or w._pred_ranged_v1.any():
        raise SystemExit("한 스텝 장면은 추격 고정·노려보기·지형·원거리형이 없어야 한다(C++ 위협 모델에 없다)")
    return w


def step_scenes():
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
            if u < 0.08:
                cd[m] = int(rng.integers(1, 39))
            elif u < 0.14:
                sat[m] = int(rng.integers(1, 451))
            elif u < 0.30 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_POUNCE, int(rng.integers(0, 13))
            elif u < 0.34 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_EXHAUST, int(rng.integers(1, 31))
        # 사슴: 늑대 앞에 몇 마리 몰아 표적·가림이 생기게 (원판 밖)
        p = rng.uniform(0.0, S, (N, 2))
        for i in range(min(10, N)):
            m = int(rng.integers(0, M))
            p[i] = np.clip(q[m] + head[m] * rng.uniform(1.0, 14.0) + rng.normal(0.0, 2.0, 2), 0.0, S)
        p, _, _ = obstacle_push_out(p, disc, body, S)
        mv = rng.normal(0.0, 1.0, (N, 2))
        mv = mv / np.maximum(np.linalg.norm(mv, axis=1, keepdims=True), 1e-9) * rng.choice([0.0, 0.24, 0.6], (N, 1), p=[0.2, 0.3, 0.5])
        # 늑대 몇은 원판(가장 큰 것부터 고른 바위·줄기) 둘레 바로 밖에서 원판 쪽을 보게 해 부딪힘·막다른 곳이 생기게
        big = np.argsort(-disc[:, 2])[:12]
        for m in range(M):
            if rng.random() < 0.45:
                for _t in range(50):
                    k = int(big[int(rng.integers(0, len(big)))])
                    a = rng.uniform(0.0, 2.0 * math.pi)
                    u = np.array([math.cos(a), math.sin(a)])
                    c = disc[k, :2] + (disc[k, 2] + body + rng.uniform(0.005, 0.3)) * u
                    if (0.0 <= c.min() and c.max() <= S and not w._rz_inside_disc(c[None, :])[0]
                            and not obstacle_inside(c[None, :], disc, body)[0]):
                        q[m] = c
                        b = rng.normal(0.0, 0.08)
                        head[m] = np.array([-u[0] * math.cos(b) + u[1] * math.sin(b), -u[0] * math.sin(b) - u[1] * math.cos(b)])
                        if w.pred_type[m] == PT_STALKER and rng.random() < 0.5:
                            # 막다른 곳: 돌진 중(표적 없으면 heading 으로 곧장)인 잠행형이 원판 둘레에 바짝 붙어 정면으로 — 거의 못 가 돌아선다
                            q[m] = disc[k, :2] + (disc[k, 2] + body + 0.002) * u
                            head[m] = -u
                            cd[m], sat[m], st[m], left[m] = 0, 0, ST_POUNCE, int(rng.integers(1, 13))
                        break
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
        in_cov = w._in_cover(w.pos)
        turns = copy.deepcopy(w.rng).uniform(-w.cfg.pred_wander_turn, w.cfg.pred_wander_turn, M)
        caught = w._step_predators_v3()
        k = np.full(M, -1, dtype=np.int64)
        got = w.pred_cd == int(w.cfg.pred_eat_cd)
        for m in np.flatnonzero(got):
            dd = np.sqrt(((w.pos - q[m]) ** 2).sum(1)) * np.where(in_cov, w._rep_cover, 1.0)
            dd = np.where(caught & ~in_cov, dd, np.inf)
            k[m] = int(np.argmin(dd))
        out.append(dict(q=q, head=head, cd=cd, sat=sat, st=st, left=left, p=p, mv=w.pos - w._pack_p0, in_cov=in_cov, turns=turns,
                        q1=w.pred_pos.copy(), head1=w.pred_head.copy(), cd1=w.pred_cd.copy(), sat1=w.pred_sat.copy(),
                        st1=w.stalk_state.copy(), left1=w.stalk_left.copy(), help=w.pack_help.copy(), target=w.pred_target.copy(), caught=k,
                        hit=w.pred_ob_hit.copy(), back=w.pred_ob_back.copy(), dead=w.pred_ob_dead.copy()))
    consts = dict(size=S, kinds=w.pred_type.copy(), cov=np.c_[w.cov_c, w.cov_r], margin=w._zw_m, eat_cd=int(w.cfg.pred_eat_cd),
                  sat_steps=int(w._ws_sat_steps), M=M, N=N, pred_speed_mult=float(w.pred_speed_mult), discs=disc.copy(), body=body,
                  sight=bool(w._ob["block_sight"]))
    return out, consts


# --------------------------------------------------------------------- #
# 헤더
# --------------------------------------------------------------------- #


def build_header() -> str:
    op = mirror_params()
    body = float(op["body_r"])
    layout, size, covers = mirror_layout(op)
    rng = np.random.default_rng(SEED_CASE)
    sets = DiscSets()
    mirror = sets.add(layout)
    slides, n_slide_hand = slide_cases(sets, mirror, size, body, rng)
    sights, n_sight_hand = sight_cases(sets, mirror, size, rng)
    pushes, n_push_hand = push_cases(sets, mirror, size, body, covers, rng)
    # 먹이 손 배치: 표본점에 꼭 닿는 원판·셀을 다 덮는 바위·맵 모서리·맵 가장자리 밖으로 걸친 원판·아주 가는 줄기 (묶음 목록을 쓰기 전에 더한다)
    hand = sets.add([[2.0 + 0.25, 4.0 + 0.25, 0.25], [11.0, 11.0, 1.6], [0.0, 0.0, 1.0], [59.5, 30.0, 0.9], [30.0, 30.0, 0.05]])
    food_sets = [mirror, hand]
    n_sets = len(sets.index)
    steps, sc = step_scenes()
    L = [
        "// 자동 생성 — herbivore_rl/export_golden_v3_obstacle.py (손으로 고치지 않는다). 세계 configs/v3_wild2_obstacle_mirror.yaml, 시드 32095·32096·32097.",
        "// v3 야생 2단계 3 세로 장애물 골든 (명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md 6절). 검사는 Tests/ObstacleGoldenCheckV3.h (AdaptiveEcosystem.Policy.V3.Obstacle.*).",
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace EcoWorldV3::GoldenObstacle",
        "{",
        "\t// 거울 설정 obstacles 계수 (C++ FObstacleConfig 기본값과 같아야 한다)와 상수 (world.py OB_PASSES·OB_EPS·OB_SAMPLES)",
        f"\tinline constexpr double kCfgBodyR = {d_lit(body)};",
        f"\tinline constexpr std::int32_t kCfgBlockSight = {int(op['block_sight'])};",
        f"\tinline constexpr std::int32_t kCfgNoFood = {int(op['no_food'])};",
        f"\tinline constexpr std::int32_t kPasses = {OB_PASSES};",
        f"\tinline constexpr double kEps = {d_lit(OB_EPS)};",
        f"\tinline constexpr std::int32_t kSamples = {OB_SAMPLES};",
        f"\tinline constexpr double kMirrorSize = {d_lit(size)};",
        f"\tinline constexpr std::int32_t kMirrorDiscs = {len(layout)};",
        "",
        "\t// ---- 원판 묶음: kSetIndex[2k..] = (시작 원판, 수), kSetDiscs[3·원판..] = (x, y, r). 묶음 0 = 거울 세계 배치 (시드 32095) ----",
        f"\tinline constexpr std::int32_t kSets = {len(sets.index)};",
        c_array("std::int32_t", "kSetIndex", [v for t in sets.index for v in t], 16, str),
        c_array("double", "kSetDiscs", sets.flat, 6, d_lit),
    ]
    # 미끄러짐
    si, sd, so, soi = [], [], [], []
    n_hit = n_back = 0
    for c in slides:
        d = sets.get(c["set"])
        sz = c["size"] if c["size"] >= 0 else None
        q, hit, back = obstacle_slide(c["p"][None, :], c["q"][None, :], d, body, sz)
        si += [c["set"]]
        sd += [c["p"][0], c["p"][1], c["q"][0], c["q"][1], c["size"]]
        so += [q[0, 0], q[0, 1]]
        soi += [int(hit[0]), int(back[0])]
        n_hit += int(hit[0])
        n_back += int(back[0])
    L += [
        "",
        "\t// ---- 미끄러짐 (world.py obstacle_slide, 몸 kCfgBodyR): 장면 s = 묶음 kSlideSet[s], kSlideIn[5s..] = (px, py, qx, qy, 맵 한 변 — 음수면 자르지 않음),",
        "\t//      출력 kSlideOut[2s..] = 새 q, kSlideOutI[2s..] = (부딪힘, 물러남). 앞 kSlideHand 개는 손 장면 ----",
        f"\tinline constexpr std::int32_t kSlideCases = {len(slides)};",
        f"\tinline constexpr std::int32_t kSlideHand = {n_slide_hand};",
        f"\tinline constexpr std::int32_t kSlideHits = {n_hit};",
        f"\tinline constexpr std::int32_t kSlideBacks = {n_back};",
        c_array("std::int32_t", "kSlideSet", si, 20, str),
        c_array("double", "kSlideIn", sd, 5, d_lit),
        c_array("double", "kSlideOut", so, 4, d_lit),
        c_array("std::int32_t", "kSlideOutI", soi, 20, str),
    ]
    # 시선
    vi, vd, vo = [], [], []
    for c in sights:
        d = sets.get(c["set"])
        b = bool(sight_blocked(c["a"][None, :], c["b"][None, :], d)[0, 0])
        vi += [c["set"]]
        vd += [c["a"][0], c["a"][1], c["b"][0], c["b"][1]]
        vo += [int(b)]
    L += [
        "",
        "\t// ---- 시선 (world.py sight_blocked 한 쌍): 장면 s = 묶음 kSightSet[s], kSightIn[4s..] = (ax, ay, bx, by), 출력 kSightOut[s] = 가림. 앞 kSightHand 개는 손 장면 ----",
        f"\tinline constexpr std::int32_t kSightCases = {len(sights)};",
        f"\tinline constexpr std::int32_t kSightHand = {n_sight_hand};",
        f"\tinline constexpr std::int32_t kSightBlocked = {sum(vo)};",
        c_array("std::int32_t", "kSightSet", vi, 20, str),
        c_array("double", "kSightIn", vd, 4, d_lit),
        c_array("std::int32_t", "kSightOut", vo, 40, str),
    ]
    # 먹이
    cap0, cap1 = [], []
    for k in food_sets:
        c0 = rng.uniform(0.0, 1.0, (GW, GW))
        f = obstacle_food_factor(GW, CELL, sets.get(k))
        cap0 += list(c0.reshape(-1))
        cap1 += list((c0 * f).reshape(-1))
    L += [
        "",
        f"\t// ---- 먹이 (world.py obstacle_food_factor): 격자 {GW} × {GW}, 셀 {CELL}. 배치 kFoodSet[j] 마다 처음 용량 kFoodCap0[j·Gw²..] → 줄인 용량 kFoodCap1 ----",
        f"\tinline constexpr std::int32_t kFoodGw = {GW};",
        f"\tinline constexpr double kFoodCell = {d_lit(CELL)};",
        f"\tinline constexpr std::int32_t kFoodLayouts = {len(food_sets)};",
        c_array("std::int32_t", "kFoodSet", food_sets, 8, str),
        c_array("double", "kFoodCap0", cap0, 6, d_lit),
        c_array("double", "kFoodCap1", cap1, 6, d_lit),
    ]
    # 밀어내기
    pi_, pd, pc, po, poi = [], [], [], [], []
    for c in pushes:
        d = sets.get(c["set"])
        q, code = run_push(c, d, body)
        pi_ += [c["set"], int(c["wolf"]), len(pc) // 3, len(c["cov"])]
        pd += [c["p"][0], c["p"][1], c["size"], c["margin"]]
        pc += [float(v) for v in c["cov"].reshape(-1)]
        po += [q[0], q[1]]
        poi += [code]
    if not pc:
        pc = [0.0, 0.0, 0.0]
    L += [
        "",
        "\t// ---- 밀어내기 (world.py obstacle_push_out 한 개체): 장면 s: kPushInt[4s..] = (묶음, 늑대, 은신처 시작, 은신처 수), kPushIn[4s..] = (px, py, 맵 한 변,",
        "\t//      늑대 몸 여유), 은신처 원 kPushCover (x, y, r). 출력 kPushOut[2s..] = 새 p, kPushOutI[s] = 0 그대로·1 옮김·2 못 옮김. 앞 kPushHand 개는 손 장면 ----",
        f"\tinline constexpr std::int32_t kPushCases = {len(pushes)};",
        f"\tinline constexpr std::int32_t kPushHand = {n_push_hand};",
        f"\tinline constexpr std::int32_t kPushMoved = {poi.count(1)};",
        f"\tinline constexpr std::int32_t kPushFailed = {poi.count(2)};",
        c_array("std::int32_t", "kPushInt", pi_, 16, str),
        c_array("double", "kPushIn", pd, 4, d_lit),
        c_array("double", "kPushCover", pc, 6, d_lit),
        c_array("double", "kPushOut", po, 4, d_lit),
        c_array("std::int32_t", "kPushOutI", poi, 40, str),
    ]
    # 한 스텝
    M, N = sc["M"], sc["N"]
    kinds = [int(x) for x in sc["kinds"]]
    if kinds != [PT_STALKER, PT_CHASER, PT_STALKER, PT_CHASER]:
        raise SystemExit(f"늑대 구성이 잠행·추격 번갈아가 아니다: {kinds}")
    in_d, in_i, prey_s, out_sd, out_si = [], [], [], [], []
    hits = backs = deads = catches = targets = 0
    for t in steps:
        for m in range(M):
            in_d += [t["q"][m, 0], t["q"][m, 1], t["head"][m, 0], t["head"][m, 1], t["turns"][m]]
            in_i += [int(t["cd"][m]), int(t["sat"][m]), int(t["st"][m]), int(t["left"][m])]
            out_sd += [t["q1"][m, 0], t["q1"][m, 1], t["head1"][m, 0], t["head1"][m, 1]]
            out_si += [int(t["cd1"][m]), int(t["sat1"][m]), int(t["st1"][m]), int(t["left1"][m]), int(t["help"][m]), int(t["target"][m]),
                       int(t["caught"][m]), int(t["hit"][m]), int(t["back"][m]), int(t["dead"][m])]
            hits += int(t["hit"][m])
            backs += int(t["back"][m])
            deads += int(t["dead"][m])
            catches += int(t["caught"][m] >= 0)
            targets += int(t["target"][m] >= 0)
        for i in range(N):
            prey_s += [t["p"][i, 0], t["p"][i, 1], t["mv"][i, 0], t["mv"][i, 1], float(t["in_cov"][i])]
    L += [
        "",
        "\t// ---- 한 스텝 장면 (world.py _step_predators_v3, 늑대 4 = 순번 짝수 잠행·홀수 추격, 사슴 모두 먹기, 낮 d = 0, 원판 = 그 세계 배치) ----",
        f"\tinline constexpr std::int32_t kStepScenes = {len(steps)};",
        f"\tinline constexpr std::int32_t kStepWolves = {M};",
        f"\tinline constexpr std::int32_t kStepPrey = {N};",
        f"\tinline constexpr double kStepWorldSize = {d_lit(sc['size'])};",
        f"\tinline constexpr double kStepPredSpeedMult = {d_lit(sc['pred_speed_mult'])};",
        f"\tinline constexpr double kStepWolfMargin = {d_lit(sc['margin'])};",
        f"\tinline constexpr std::int32_t kStepEatCd = {sc['eat_cd']};",
        f"\tinline constexpr std::int32_t kStepSatSteps = {sc['sat_steps']};",
        f"\tinline constexpr std::int32_t kStepSight = {int(sc['sight'])};",
        f"\tinline constexpr std::int32_t kStepHits = {hits};",
        f"\tinline constexpr std::int32_t kStepBacks = {backs};",
        f"\tinline constexpr std::int32_t kStepDeads = {deads};",
        f"\tinline constexpr std::int32_t kStepCatches = {catches};",
        f"\tinline constexpr std::int32_t kStepTargets = {targets};",
        f"\tinline constexpr std::int32_t kStepCoverCount = {len(sc['cov'])};",
        c_array("double", "kStepCover", [v for row in sc["cov"] for v in row], 6, d_lit),
        f"\tinline constexpr std::int32_t kStepDiscCount = {len(sc['discs'])};",
        c_array("double", "kStepDiscs", [v for row in sc["discs"] for v in row], 6, d_lit),
        "\t// 늑대 (장면 s·늑대 m = s·4 + m): 입력 (x, y, hx, hy, 배회 선회), (쿨다운, 배부름, 잠행 상태, 남은 수)",
        c_array("double", "kStepWolfIn", in_d, 5, d_lit),
        c_array("std::int32_t", "kStepWolfInI", in_i, 16, str),
        "\t// 사슴 (장면 s·사슴 i = s·N + i): (x, y, 이동 x, 이동 y, 은신처 안 0/1)",
        c_array("double", "kStepPreyIn", prey_s, 5, d_lit),
        "\t// 출력 늑대: (x, y, hx, hy), (쿨다운, 배부름, 잠행 상태, 남은 수, 돕기, 표적, 잡은 사슴, 원판 부딪힘, 되돌림, 돌아섬)",
        c_array("double", "kStepWolfOut", out_sd, 4, d_lit),
        c_array("std::int32_t", "kStepWolfOutI", out_si, 10, str),
        "}",
        "",
    ]
    if len(sets.index) != n_sets or any(k >= n_sets for k in si + vi + food_sets + pi_[0::4]):
        raise SystemExit("원판 묶음 목록을 쓴 뒤에 묶음을 더했다 — 장면이 없는 묶음을 가리킨다")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / "ObstacleGoldenVectorsV3.h"
    path.write_text(build_header(), encoding="utf-8", newline="\n")
    print(f"썼다: {path}")


if __name__ == "__main__":
    main()
