"""v3 야생 2단계 2 골든 내보내기 — 늑대 무리 협동 사냥(wild_pack)을 언리얼 C++ `EcoThreatModel.h` (PackPeek·PackGoals·Step 6b′)와 대조할
골든 헤더를 만든다 (명세 `Docs/RL_Policy/RL_V3_WILD2_SPEC.md` '골든 시험').

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_pack.py
    # 시험용 다른 폴더
    python export_golden_v3_pack.py --out <폴더>

세계·시드: configs/v3_wild2_pack_mirror.yaml(늑대 4·wild_pack 켬). 이 내보내기 전용 탐색 시드 32093(한 스텝 장면)·32094(목표 장면). 판정 시드는 쓰지 않는다.

묶음:
  목표 장면    `pack_goals` 의 입력(늑대 위치·heading·앞장·돕기·표적, 사슴 위치·이번 이동, 은신처 원, 몸 여유, 무대, 계수)과 출력(돕기·기다림·문·
              고른 사슴·방향). 손 장면(은신처 문·도주선 앞·기다림·서 있는 사슴·사슴과 겹친 늑대·서 있는 사슴과 겹친 앞장·같은 거리·맵 가장자리·
              반경 0 원·join_r 경계) + 난수 장면. C++ PackGoals 가 비트 단위로 같아야 한다.
  한 스텝 장면 거울 세계(사슴 24, 늑대 4 = 잠행 2·추격 2)의 상태를 장면마다 정해 `World._step_predators_v3` 를 한 번 부른다(낮 d = 0, 밤잠 배수 1,
              먹기·배부름·돌진·지침 상태를 섞음, 사슴은 모두 먹기). 입력(늑대 위치·heading·쿨다운·배부름·잠행 상태·남은 수, 사슴 위치·이동·은신처 안,
              배회 선회 난수)과 출력(늑대 위치·heading·쿨다운·배부름·잠행 상태·남은 수, 돕기·기다림·문·고른 사슴, 표적, 잡은 사슴).
              C++ 은 PackPeek → PackGoals → Step 을 늑대 순서로 불러 같은 값을 내야 한다(EcoWorldV3 C2 와 같은 순서).
"""

from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path

import numpy as np

from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import PT_CHASER, PT_STALKER, ST_EXHAUST, ST_POUNCE, ST_ROAM, World, pack_goals

HERE = Path(__file__).resolve().parent
PACK = HERE / "configs" / "v3_wild2_pack_mirror.yaml"
DEFAULT_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
SEED_STEP = 32093
SEED_GOAL = 32094
N_STEP = 24
STEP_SCENES = 80
GOAL_RANDOM = 60
KEYS = ("join_r", "lead", "door_r", "door_cos", "wait_r")


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


def u8(v) -> str:
    return str(int(v))


# --------------------------------------------------------------------- #
# 목표 장면
# --------------------------------------------------------------------- #


def _scene(wq, whead, leader, helper, tgt, p, disp, cov, margin, size, wp):
    return dict(wq=np.asarray(wq, float).reshape(-1, 2), whead=np.asarray(whead, float).reshape(-1, 2), leader=np.asarray(leader, bool),
                helper=np.asarray(helper, bool), tgt=np.asarray(tgt, np.int64), p=np.asarray(p, float).reshape(-1, 2),
                disp=np.asarray(disp, float).reshape(-1, 2), cov=np.asarray(cov, float).reshape(-1, 3), margin=float(margin),
                size=float(size), wp=dict(wp))


def goal_scenes(wp0: dict):
    """손 장면 + 난수 장면 (모듈 docstring '목표 장면')."""
    h1 = [[1.0, 0.0]] * 2
    hand = [
        _scene([[20, 30], [50, 10]], h1, [1, 0], [0, 1], [0, 0], [[25, 40]], [[0.6, 0]], [[40, 40, 6]], 0.5, 60, wp0),      # 은신처 문
        _scene([[30, 30], [10, 40]], h1, [1, 0], [0, 1], [0, 0], [[25, 40]], [[-0.6, 0]], [[40, 40, 6]], 0.5, 60, wp0),     # 도주선 앞
        _scene([[30, 30], [19, 40.5]], h1, [1, 0], [0, 1], [0, 0], [[25, 40]], [[-0.6, 0]], [[40, 40, 6]], 0.5, 60, wp0),   # 기다림
        _scene([[25, 30], [10, 10]], h1, [1, 0], [0, 1], [0, 0], [[25, 36]], [[0, 0]], [], 0.5, 60, wp0),                    # 서 있는 사슴
        _scene([[30, 30], [25, 40]], [[1, 0], [0.6, 0.8]], [1, 0], [0, 1], [0, 0], [[25, 40]], [[0, 0]], [], 0.5, 60,
               dict(wp0, lead=0.0)),                                                                                          # 늑대가 사슴 위 → heading
        _scene([[25, 40], [10, 10]], h1, [1, 0], [0, 1], [0, 0], [[25, 40]], [[0, 0]], [], 0.5, 60, wp0),                    # 앞장이 서 있는 사슴 위 → U = 0
        _scene([[0, 0], [5, 5], [30, 30]], [[1, 0]] * 3, [1, 1, 0], [0, 0, 1], [0, 1, 0], [[30, 35], [30, 25]], [[0, 0.6], [0, -0.6]],
               [], 0.5, 60, wp0),                                                                                             # 같은 거리 → 앞 슬롯
        _scene([[30, 20], [50, 50]], h1, [1, 0], [0, 1], [0, 0], [[57, 30]], [[0.6, 0]], [], 0.5, 60, wp0),                  # 맵 가장자리
        _scene([[20, 30], [50, 10]], h1, [1, 0], [0, 1], [0, 0], [[25, 40]], [[0.6, 0]], [[40, 40, 0.0]], 0.5, 60, wp0),     # 반경 0 원
        _scene([[0, 0], [10, 0]], h1, [1, 0], [0, 1], [0, 0], [[15, 0]], [[0.6, 0]], [], 0.5, 60, dict(wp0, join_r=5.0)),    # join_r 경계
        _scene([[0, 0], [9.9, 0]], h1, [1, 0], [0, 1], [0, 0], [[15, 0]], [[0.6, 0]], [], 0.5, 60, dict(wp0, join_r=5.0)),   # join_r 밖
        _scene([[20, 30], [50, 10]], h1, [1, 0], [0, 1], [0, 0], [[25, 40]], [[0.6, 0]], [[40, 40, 6], [33, 41, 3]], 0.0, 60,
               wp0),                                                                                                          # 문 둘, 몸 여유 0
    ]
    rng = np.random.default_rng(SEED_GOAL)
    rand = []
    for s in range(GOAL_RANDOM):
        size = float(rng.choice([60.0, 85.0, 110.0]))
        M, N, K = int(rng.integers(2, 7)), int(rng.integers(2, 11)), int(rng.integers(0, 5))
        wq = rng.uniform(-0.0, size, (M, 2))
        ang = rng.uniform(0, 2 * np.pi, M)
        whead = np.stack([np.cos(ang), np.sin(ang)], 1)
        leader = rng.random(M) < 0.4
        leader[int(rng.integers(0, M))] = True
        helper = ~leader & (rng.random(M) < 0.8)
        tgt = rng.integers(0, N, M)
        p = rng.uniform(0.0, size, (N, 2))
        disp = rng.normal(0.0, 0.4, (N, 2)) * (rng.random((N, 1)) < 0.8)
        cov = np.c_[rng.uniform(0.0, size, (K, 2)), np.where(rng.random(K) < 0.15, 0.0, rng.uniform(3.0, 9.0, K))]
        # 문 장면을 늘린다: 은신처 하나를 쫓기는 사슴의 이동 방향 앞(가장자리까지 2~12 단위)에 둔다
        if K and rng.random() < 0.6:
            i = int(tgt[int(np.flatnonzero(leader)[0])])
            u = disp[i] / max(float(np.linalg.norm(disp[i])), 1e-9)
            r = float(rng.uniform(3.0, 9.0))
            cov[0] = [*(p[i] + u * (r + float(rng.uniform(2.0, 12.0)))), r]
        wp = dict(wp0, join_r=float(rng.choice([wp0["join_r"], 20.0, 40.0])), lead=float(rng.choice([wp0["lead"], 3.0, 10.0])),
                  wait_r=float(rng.choice([wp0["wait_r"], 3.0])))
        sc = _scene(wq, whead, leader, helper, tgt, p, disp, cov, float(rng.choice([0.0, 0.5])), size, wp)
        # 기다림 장면을 늘린다: 돕는 늑대 하나를 자기 목표 자리 곁(wait_r 안)으로 옮긴다
        if rng.random() < 0.35:
            hp, wt, dr, prey, dv = run_goal(sc)
            hs = np.flatnonzero(hp)
            if len(hs):
                m = int(hs[0])
                goal = _goal_point(sc, m, int(prey[m]))
                off = rng.uniform(-0.4, 0.4, 2) * wp["wait_r"]
                sc["wq"][m] = np.clip(goal + off, 0.0, size)
        rand.append(sc)
    return hand + rand, len(hand)


def _goal_point(sc, m, i):
    """기다림 장면 만들기용: 늑대 m 이 사슴 i 를 고를 때의 목표 자리(pack_goals 와 같은 식 — 장면 배치 전용)."""
    p, disp, cov, wp = sc["p"][i], sc["disp"][i], sc["cov"], sc["wp"]
    n = float(np.linalg.norm(disp))
    u = disp / n if n > 1e-9 else np.zeros(2)
    best = None
    for k in range(len(cov)):
        c, r = cov[k, :2], cov[k, 2]
        if r <= 0:
            continue
        e = c - p
        dk = float(np.linalg.norm(e))
        if 0 < dk - r <= wp["door_r"] and float(e @ u) / dk >= wp["door_cos"] and (best is None or dk - r < best[0]):
            best = (dk - r, c - (r + sc["margin"]) * e / dk)
    g = best[1] if best else p + wp["lead"] * u
    return np.clip(g, 0.0, sc["size"])


def run_goal(sc):
    return pack_goals(sc["wq"], sc["whead"], sc["leader"], sc["helper"], sc["tgt"], sc["p"], sc["disp"], sc["cov"][:, :2], sc["cov"][:, 2],
                      sc["margin"], sc["size"], sc["wp"])


# --------------------------------------------------------------------- #
# 한 스텝 장면
# --------------------------------------------------------------------- #


def step_world() -> World:
    w = World(load_v2_config(PACK).replace(N=N_STEP), seeds=[SEED_STEP])
    if w._wp is None or w.M != 4 or w.alive is None:
        raise SystemExit("v3_wild2_pack_mirror.yaml 은 늑대 4·wild_pack 켬·부활 없음이어야 한다")
    if w._rp is None or w._zs is None or not w._zw or w._ws is None or not w._eat_in_place:
        raise SystemExit("한 스텝 장면은 행동 레퍼토리·은신처 안전·진입 금지·포만·제자리 식사를 켠 세계여야 한다")
    if w._zc is not None or w._sd is not None or w._zt is not None or w._pred_ranged_v1.any():
        raise SystemExit("한 스텝 장면은 추격 고정·노려보기·지형·원거리형이 없어야 한다(C++ 위협 모델에 없다)")
    return w


def step_scenes():
    """모듈 docstring '한 스텝 장면'. 반환 (장면 목록, 세계 상수)."""
    w = step_world()
    rng = np.random.default_rng(SEED_STEP)
    S, M, N = w.size, w.M, w.N
    rp = w._rp
    out = []
    for s in range(STEP_SCENES):
        # 늑대: 무대 아무 데나(은신처 둘레 밖), heading 무작위, 상태 섞기
        q = np.zeros((M, 2))
        for m in range(M):
            for _ in range(200):
                c = rng.uniform(0.0, S, 2)
                if not w._rz_inside_disc(c[None, :])[0]:
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
            if u < 0.12:
                cd[m] = int(rng.integers(1, 39))                       # 먹는 중
            elif u < 0.22:
                sat[m] = int(rng.integers(1, 451))                     # 배부름
            elif u < 0.32 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_POUNCE, int(rng.integers(0, 13))   # 돌진 중(남은 0 = 마지막 판정)
            elif u < 0.36 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_EXHAUST, int(rng.integers(1, 31))  # 지침
        # 사슴: 무대 아무 데나, 늑대 곁에 몇 마리 몰아 앞장이 생기게, 이번 이동은 0~뛰기
        p = rng.uniform(0.0, S, (N, 2))
        for i in range(min(6, N)):
            m = int(rng.integers(0, M))
            p[i] = np.clip(q[m] + head[m] * rng.uniform(1.0, 12.0) + rng.normal(0.0, 2.0, 2), 0.0, S)
        mv = rng.normal(0.0, 1.0, (N, 2))
        mv = mv / np.maximum(np.linalg.norm(mv, axis=1, keepdims=True), 1e-9) * rng.choice([0.0, 0.24, 0.6], (N, 1), p=[0.2, 0.3, 0.5])
        def put(wd, q_):
            # 세계에 넣는다 (사슴은 모두 먹기, 낮 d = 0, 밤잠 배수 1, 깨어 있음)
            wd.pos = p.copy()
            wd._pack_p0 = p - mv
            wd._rs.behavior[:] = rep.GRAZE
            wd._rep_still = np.zeros(N, dtype=bool)
            wd._rep_cover = rep.cover_mult(rp, wd._rs.behavior, np.zeros(N, dtype=bool))
            wd.alive = np.ones(N, dtype=bool)
            wd.pred_pos, wd.pred_head = q_.copy(), head.copy()
            wd.pred_cd, wd.pred_sat = cd.copy(), sat.copy()
            wd.stalk_state, wd.stalk_left = st.copy(), left.copy()
            wd.pred_asleep = np.zeros(M, dtype=bool)
            wd._pred_speed_mult = np.ones(M)
            wd.dark = 0.0
            wd._zn_hunt = np.zeros(M, dtype=bool)
            wd._hunt_on = np.zeros(M, dtype=bool)

        # 기다림 장면을 늘린다: 장면의 40% 는 사본으로 한 번 돌려 본 뒤 첫 돕는 늑대를 자기 목표 자리 곁(0.3 단위 안)으로 옮긴다
        if rng.random() < 0.4:
            wa = copy.deepcopy(w)
            put(wa, q)
            wa._step_predators_v3()
            hs = np.flatnonzero(wa.pack_help)
            if len(hs):
                m = int(hs[0])
                i = int(wa.pack_prey[m])
                sc = dict(p=p, disp=mv, cov=np.c_[w.cov_c, w.cov_r], wp=w._wp, margin=w._zw_m, size=S)
                goal = _goal_point(dict(sc, p=p, disp=mv), m, i)
                q = q.copy()
                q[m] = np.clip(goal + rng.uniform(-0.3, 0.3, 2), 0.0, S)
        put(w, q)
        in_cov = w._in_cover(w.pos)
        turns = copy.deepcopy(w.rng).uniform(-w.cfg.pred_wander_turn, w.cfg.pred_wander_turn, M)
        caught = w._step_predators_v3()
        k = np.full(M, -1, dtype=np.int64)
        got = w.pred_cd == int(w.cfg.pred_eat_cd)
        for m in np.flatnonzero(got):
            d = np.sqrt(((w.pos - q[m]) ** 2).sum(1)) * np.where(in_cov, w._rep_cover, 1.0)
            d = np.where(caught & ~in_cov, d, np.inf)
            k[m] = int(np.argmin(d))
        # 사슴 이동은 세계가 읽는 값 그대로(위치 − 이동 전 위치 — 이동 벡터와 마지막 비트가 다를 수 있다. C++ 도 Pos − PrevPos 다)
        out.append(dict(q=q, head=head, cd=cd, sat=sat, st=st, left=left, p=p, mv=w.pos - w._pack_p0, in_cov=in_cov, turns=turns,
                        q1=w.pred_pos.copy(), head1=w.pred_head.copy(), cd1=w.pred_cd.copy(), sat1=w.pred_sat.copy(),
                        st1=w.stalk_state.copy(), left1=w.stalk_left.copy(), help=w.pack_help.copy(), wait=w.pack_wait.copy(),
                        door=w.pack_door.copy(), prey=w.pack_prey.copy(), target=w.pred_target.copy(), caught=k))
    consts = dict(size=S, kinds=w.pred_type.copy(), speed=w.pred_speed.copy(), cov=np.c_[w.cov_c, w.cov_r], margin=w._zw_m,
                  eat_cd=int(w.cfg.pred_eat_cd), sat_steps=int(w._ws_sat_steps), turn=float(w.cfg.pred_wander_turn), M=M, N=N,
                  pred_speed_mult=float(w.pred_speed_mult))
    return out, consts


# --------------------------------------------------------------------- #
# 헤더
# --------------------------------------------------------------------- #


def build_header() -> str:
    cfg = load_v2_config(PACK)
    wp0 = dict(cfg.v2["features"]["wild_pack"])
    wp0.pop("enabled")
    goals, n_hand = goal_scenes(wp0)
    steps, sc = step_scenes()
    L = [
        "// 자동 생성 — herbivore_rl/export_golden_v3_pack.py (손으로 고치지 않는다). 세계 configs/v3_wild2_pack_mirror.yaml, 시드 32093·32094.",
        "// v3 야생 2단계 2 늑대 무리 협동 골든 (명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md '골든 시험'). 검사는 Tests/EcoPackV3Test.cpp (AdaptiveEcosystem.Policy.V3.Pack.*).",
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace EcoThreatV3::GoldenPack",
        "{",
        "\t// 거울 설정 wild_pack 계수 (C++ FPackHuntConfig 기본값과 같아야 한다)",
    ]
    for k in KEYS:
        L.append(f"\tinline constexpr double kCfg_{k} = {d_lit(wp0[k])};")
    # 목표 장면
    ints, dbl, wolf_d, wolf_i, prey_d, cov_d, out_i, out_d = [], [], [], [], [], [], [], []
    for g in goals:
        hp, wt, dr, prey, dv = run_goal(g)
        M, N, K = len(g["wq"]), len(g["p"]), len(g["cov"])
        ints += [M, N, K, len(wolf_i) // 3, len(prey_d) // 4, len(cov_d) // 3]
        dbl += [g["size"], g["margin"]] + [g["wp"][k] for k in KEYS]
        for m in range(M):
            wolf_d += [g["wq"][m, 0], g["wq"][m, 1], g["whead"][m, 0], g["whead"][m, 1]]
            wolf_i += [int(g["leader"][m]), int(g["helper"][m]), int(g["tgt"][m])]
            out_i += [int(hp[m]), int(wt[m]), int(dr[m]), int(prey[m])]
            out_d += [dv[m, 0], dv[m, 1]]
        for i in range(N):
            prey_d += [g["p"][i, 0], g["p"][i, 1], g["disp"][i, 0], g["disp"][i, 1]]
        for k in range(K):
            cov_d += list(g["cov"][k])
    n_help = sum(v for v in out_i[0::4])
    n_wait = sum(v for v in out_i[1::4])
    n_door = sum(v for v in out_i[2::4])
    L += [
        "",
        "\t// ---- 목표 장면 (world.py pack_goals) ----",
        "\t// 장면 s: kGoalInt[6s..] = (늑대 M, 사슴 N, 은신처 K, 늑대 시작, 사슴 시작, 은신처 시작), kGoalDbl[7s..] = (무대, 몸 여유, join_r, lead, door_r, door_cos, wait_r).",
        "\t// 늑대 w: kGoalWolfD[4w..] = (x, y, hx, hy), kGoalWolfI[3w..] = (앞장, 돕기 후보, 표적). 사슴 i: kGoalPrey[4i..] = (x, y, 이동 x, 이동 y). 원 (x, y, r).",
        "\t// 출력 늑대 w: kGoalOutI[4w..] = (돕기, 기다림, 문, 고른 사슴), kGoalOutD[2w..] = 방향. 앞 kGoalHand 개는 손 장면",
        f"\tinline constexpr std::int32_t kGoalScenes = {len(goals)};",
        f"\tinline constexpr std::int32_t kGoalHand = {n_hand};",
        f"\tinline constexpr std::int32_t kGoalHelp = {n_help};",
        f"\tinline constexpr std::int32_t kGoalWait = {n_wait};",
        f"\tinline constexpr std::int32_t kGoalDoor = {n_door};",
        c_array("std::int32_t", "kGoalInt", ints, 12, str),
        c_array("double", "kGoalDbl", dbl, 7, d_lit),
        c_array("double", "kGoalWolfD", wolf_d, 4, d_lit),
        c_array("std::int32_t", "kGoalWolfI", wolf_i, 15, str),
        c_array("double", "kGoalPrey", prey_d, 4, d_lit),
        c_array("double", "kGoalCover", cov_d, 6, d_lit),
        c_array("std::int32_t", "kGoalOutI", out_i, 16, str),
        c_array("double", "kGoalOutD", out_d, 4, d_lit),
    ]
    # 한 스텝 장면
    M, N = sc["M"], sc["N"]
    kinds = [int(x) for x in sc["kinds"]]
    if kinds != [PT_STALKER, PT_CHASER, PT_STALKER, PT_CHASER]:
        raise SystemExit(f"늑대 구성이 잠행·추격 번갈아가 아니다: {kinds}")
    in_d, in_i, prey_s, out_sd, out_si = [], [], [], [], []
    helps = waits = doors = catches = 0
    for t in steps:
        for m in range(M):
            in_d += [t["q"][m, 0], t["q"][m, 1], t["head"][m, 0], t["head"][m, 1], t["turns"][m]]
            in_i += [int(t["cd"][m]), int(t["sat"][m]), int(t["st"][m]), int(t["left"][m])]
            out_sd += [t["q1"][m, 0], t["q1"][m, 1], t["head1"][m, 0], t["head1"][m, 1]]
            out_si += [int(t["cd1"][m]), int(t["sat1"][m]), int(t["st1"][m]), int(t["left1"][m]), int(t["help"][m]), int(t["wait"][m]),
                       int(t["door"][m]), int(t["prey"][m]), int(t["target"][m]), int(t["caught"][m])]
            helps += int(t["help"][m])
            waits += int(t["wait"][m])
            doors += int(t["door"][m])
            catches += int(t["caught"][m] >= 0)
        for i in range(N):
            prey_s += [t["p"][i, 0], t["p"][i, 1], t["mv"][i, 0], t["mv"][i, 1], float(t["in_cov"][i])]
    L += [
        "",
        "\t// ---- 한 스텝 장면 (world.py _step_predators_v3, 늑대 4 = 순번 짝수 잠행·홀수 추격, 사슴 모두 먹기, 낮 d = 0) ----",
        f"\tinline constexpr std::int32_t kStepScenes = {len(steps)};",
        f"\tinline constexpr std::int32_t kStepWolves = {M};",
        f"\tinline constexpr std::int32_t kStepPrey = {N};",
        f"\tinline constexpr double kStepWorldSize = {d_lit(sc['size'])};",
        f"\tinline constexpr double kStepPredSpeedMult = {d_lit(sc['pred_speed_mult'])};",
        f"\tinline constexpr double kStepWolfMargin = {d_lit(sc['margin'])};",
        f"\tinline constexpr std::int32_t kStepEatCd = {sc['eat_cd']};",
        f"\tinline constexpr std::int32_t kStepSatSteps = {sc['sat_steps']};",
        f"\tinline constexpr std::int32_t kStepHelp = {helps};",
        f"\tinline constexpr std::int32_t kStepWait = {waits};",
        f"\tinline constexpr std::int32_t kStepDoor = {doors};",
        f"\tinline constexpr std::int32_t kStepCatches = {catches};",
        f"\tinline constexpr std::int32_t kStepCoverCount = {len(sc['cov'])};",
        "\t// 은신처 원 (x, y, 사슴 반지름)",
        c_array("double", "kStepCover", [v for row in sc["cov"] for v in row], 6, d_lit),
        "\t// 늑대 (장면 s·늑대 m = s·4 + m): 입력 (x, y, hx, hy, 배회 선회), (쿨다운, 배부름, 잠행 상태, 남은 수)",
        c_array("double", "kStepWolfIn", in_d, 5, d_lit),
        c_array("std::int32_t", "kStepWolfInI", in_i, 16, str),
        "\t// 사슴 (장면 s·사슴 i = s·N + i): (x, y, 이동 x, 이동 y, 은신처 안 0/1)",
        c_array("double", "kStepPreyIn", prey_s, 5, d_lit),
        "\t// 출력 늑대: (x, y, hx, hy), (쿨다운, 배부름, 잠행 상태, 남은 수, 돕기, 기다림, 문, 고른 사슴, 표적, 잡은 사슴)",
        c_array("double", "kStepWolfOut", out_sd, 4, d_lit),
        c_array("std::int32_t", "kStepWolfOutI", out_si, 10, str),
        "}",
        "",
    ]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / "PackGoldenVectorsV3.h"
    path.write_text(build_header(), encoding="utf-8", newline="\n")
    print(f"썼다: {path}")


if __name__ == "__main__":
    main()
