"""R9 S′ 세계 시험 (사용자 결정 2026-11-12 '실전 세계랑 맞추고·그렇게 해·다 해', 설계 RL_R9_MULTISPECIES_DESIGN.md 3-3·3-9·4-2·7-3·12절).

S′ = 몸은 할 수 있는 것만(EAT = 그 자리에서 서서 먹기, SHELTER = 제자리 서기, 행동 실행 안에 자동 길찾기 없음), 감각은 정보만(새 food_dir 8 칸,
관측 115), 결정은 전부 두뇌(규칙 두뇌 S4 는 관측만 읽음). 탐색 단계 스크래치 시험(senses_explore/tests/test_s.py 31 개·test_review.py 8 개,
arm_food 4 개)을 본 코드로 옮겼다. 바꿔치기 설치 부분은 본 코드에 맞게 고쳤고, 탐색 전용 진단(오라클 두뇌·S_keepShelter·S_residue 대조·
measure_s 기록기)은 옮기지 않았다(목록은 s_impl/WORLD.md).

final.md 7-3 항목: 1 EAT 서기·뛰던 몸 = WATCH · 2 먹이 없는 EAT 는 안 먹음 · 3 SHELTER 제자리 · 4 food_dir 합성 격자·방향 규약 ·
5 관측 115 = 107 의 자리 이동(b3b8e668 기준값)·이름표 없음 · 6 결정성(같은 시드·부분 묶음·빠른 = 느린·C.run 묶음 4 = 1·판정 세계 빠른/느린) ·
7 규칙 두뇌가 관측만 · 8 서 있는 늑대는 못 문다(물기 규칙 그대로) · 9 망 64 × 115·VecEnv 115·일꾼 환경 · 11 학습 세계 풀 70.
시드: 스모크·개발 44180~44199 만 쓴다.
"""

import copy
import dataclasses
import hashlib
import inspect
import json
import math
import sys

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import r9_body as B
from env_v2 import r9_brains as BR
from env_v2 import r9_world as W
from env_v2.r9_world import R9World

EVAL_DIR = ROOT / "results" / "v3" / "r9"
CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"
SEEDS = [44180, 44181, 44182, 44183]
D_, W_, R_ = B.DEER, B.WOLF, B.BOAR
FD = B.SL_FOOD_DIR

# b3b8e668 저장소 세계(관측 107, 사슴 [16, 64], 풀 맞춤 없음)에서 WALK·RUN·WATCH 만 고른 120 결정 궤적의 sha256
# (s_impl/gen_golden.py base — 같은 값이 S′ 세계에서 food_dir 8 칸을 뺀 관측으로 나와야 한다: 자리 이동만, 다른 몸 규칙은 그대로)
GOLDEN_107 = "f149735431b0e178088115e39b1db682fad2271b9ee75b4d83fbd7d9de92f2dd"


@pytest.fixture(scope="module")
def cfg():
    return B.load_r9_config(CFG)


@pytest.fixture(scope="module")
def jcfg():
    return B.load_r9_config(JCFG)


def same_bits(a, b) -> bool:
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def rand_act(rng, w, choices=None):
    if choices is None:
        return rng.integers(0, B.N_ACTIONS, (w.K, w.S))
    c = np.asarray(choices)
    return c[rng.integers(0, len(c), (w.K, w.S))]


def scene(cfg, counts, shelters=((55.0, 55.0, 4.0),), K=1, seed=44190, patch=None):
    """tests/test_r9.scene 과 같은 꼴(모두 멈춤·성체·표준 유전·먹이 없음·번식 없음), 시드만 스모크 범위."""
    p = {"world": {"shelters": {"fixed": [list(s) for s in shelters]}}}
    if patch:
        p = B._deep_merge(p, patch)
    c = B.override(cfg, p)
    w = R9World(c, [seed + i for i in range(K)], counts=np.tile(np.asarray(counts, dtype=np.int64), (K, 1)))
    a = w.alive
    w.vel[:] = 0.0
    w.disp[:] = 0.0
    w.g_size[a] = 1.0
    w.g_speed[a] = 1.0
    w.hp[:] = 1.0
    w.stam[:] = 1.0
    w.stam_lock[:] = False
    w.E[a] = 0.6
    w.R[a] = 0.5
    w.born[:] = -3.0 * w.sb["maturity"]
    w.next_birth[:] = 1e9
    w.grass[:] = 0.0
    w.root[:] = 0.0
    w.grass_cap[:] = 0.0
    w.root_cap[:] = 0.0
    w.mem[:] = 0.0
    w.refresh()
    return w


def put(w, s, xy, head=(1.0, 0.0), vel=(0.0, 0.0), k=0):
    h = np.asarray(head, dtype=np.float64)
    w.pos[k, s] = xy
    w.head[k, s] = h / np.sqrt((h * h).sum())
    w.vel[k, s] = vel


def lo(w, sp):
    return int(w.sp_lo[sp])


def cell_of(w, xy):
    return int(xy[1] // w.cell), int(xy[0] // w.cell)        # (iy, ix)


def fd_now(w, sb=None, fast=True):
    """food_dir (K, S, 8) float64 at the current perception (slot order)."""
    f = W.food_dir_rows(w._pc, w.act, w.sb if sb is None else sb, w.grass, w.root, w._eat_min, w.cell, w.G, fast=fast)
    out = np.zeros((w.K, w.S, 8))
    ki, ii = np.nonzero(w._pc["valid"])
    out[ki, w._pc["ic"][ki, ii]] = f[ki, ii]
    return out


def three(cfg, **kw):
    """사슴·늑대·멧돼지 한 마리씩, 서로 멀리."""
    w = scene(cfg, [1, 1, 1], **kw)
    d, wf, bo = lo(w, D_), lo(w, W_), lo(w, R_)
    put(w, d, (10.0, 10.0))
    put(w, wf, (40.0, 40.0))
    put(w, bo, (10.0, 40.0))
    w.refresh()
    return w, d, wf, bo


def ref_food_dir(w, k, s, fov_cos=None):
    """food_dir 사양 문장 그대로 (한 개체, 파이썬 고리·math) — 스크래치 review/probe1.ref_food_dir."""
    sb = w.sb
    P = w.pos[k, s]
    H = w.head[k, s]
    hd = float(sb["head_down"][k, s]) if int(w.act[k, s]) == B.EAT else 1.0
    Re = float(sb["see_r"][k, s]) * hd
    Rs = float(sb["smell_r"][k, s])
    fc = float(sb["fov_cos"][k, s]) if fov_cos is None else float(fov_cos)
    eats = sb["eats"][k, s]
    epu = sb["e_per_unit"][k, s]
    ref = float(sb["food_here_ref"][k, s])
    Dd = [B.rotate(H, B.DIR8[j]) for j in range(8)]
    x = np.zeros(8)

    def w_of(vx, vy):
        d = math.hypot(vx, vy)
        ws = 0.0
        if d <= Re and (vx * H[0] + vy * H[1]) / max(d, 1e-9) >= fc:
            ws = 1.0 - d / Re
        wn = 1.0 - d / Rs if d <= Rs else 0.0
        return max(ws, wn), d

    def sector(vx, vy):
        best, bj = -9.0, 0
        for j in range(8):
            v = vx * Dd[j][0] + vy * Dd[j][1]
            if v > best:
                best, bj = v, j
        return bj

    ix0, iy0 = min(int(P[0] / w.cell), w.G - 1), min(int(P[1] / w.cell), w.G - 1)
    for f, grid in ((B.GRASS, w.grass[k]), (B.ROOT, w.root[k])):
        if not eats[f]:
            continue
        for iy in range(w.G):
            for ix in range(w.G):
                if ix == ix0 and iy == iy0:
                    continue
                g = float(grid[iy, ix])
                if g < w._eat_min:
                    continue
                vx, vy = (ix + 0.5) * w.cell - P[0], (iy + 0.5) * w.cell - P[1]
                wt, _ = w_of(vx, vy)
                if wt > 0:
                    x[sector(vx, vy)] += g * wt * float(epu[f])
    if eats[B.MEAT]:
        for c in range(w.M):
            if not w.carc_ok[k, c] or w.carc_meat[k, c] <= 0 or w.carc_kin[k, c] == w.kin_id[k, s]:
                continue
            vx, vy = w.carc_pos[k, c, 0] - P[0], w.carc_pos[k, c, 1] - P[1]
            wt, d = w_of(vx, vy)
            if d <= 1.0 or wt <= 0:
                continue
            x[sector(vx, vy)] += float(w.carc_meat[k, c]) * wt * float(epu[B.MEAT])
    return x / (x + ref)


# --------------------------------------------------------------------------- 1·2 EAT = 서서 먹기만


def _run(w, a, n):
    for _ in range(n):
        w.step(a)


@pytest.mark.parametrize("case", ["nofood", "food_near", "food_here", "carcass", "in_shelter"])
def test_s1_eat_never_moves_from_rest(cfg, case):
    w, d, wf, bo = three(cfg)
    if case == "food_near":                                   # 먹이가 옆 셀·몇 셀 앞에 있어도 걷지 않는다
        for s in (d, bo):
            iy, ix = cell_of(w, w.pos[0, s])
            w.grass[0, iy, ix + 1] = w.grass[0, iy + 2, ix] = 0.9
            w.root[0, iy, ix + 2] = 0.9
    if case == "food_here":
        for s in (d, bo):
            iy, ix = cell_of(w, w.pos[0, s])
            w.grass[0, iy, ix] = w.root[0, iy, ix] = 0.9
    if case == "carcass":                                     # 고기만 먹는 몸: 느낀 사체(3 단위 앞)·발밑 사체
        w._add_carcass(0, (43.0, 40.0), 4.0, int(w.kin_id[0, d]), D_, 999, 0)
        w._add_carcass(0, (10.5, 40.0), 4.0, int(w.kin_id[0, d]), D_, 998, 0)   # 멧돼지 발밑(고기도 먹음)
    if case == "in_shelter":
        put(w, d, (55.0, 55.0))
        put(w, bo, (56.0, 54.0))
    w.refresh()
    p0 = w.pos.copy()
    a = np.full((1, w.S), B.EAT)
    _run(w, a, 6)
    al = w.alive
    assert al[0, [d, wf, bo]].all()
    assert same_bits(w.pos[al], p0[al]), case
    assert np.abs(w.vel[al]).max() == 0.0
    assert (w._gait[al] == B.G_STAND).all()                   # 서기 대사


def test_s1_eat_from_moving_equals_watch_inertia(cfg):
    """목표 속도 0 — 뛰던 몸은 가속 한계만큼 줄며 선다(WATCH 와 비트 같음). 먹이 쪽으로 가는 성분은 없다."""
    w, d, wf, bo = three(cfg)
    iy, ix = cell_of(w, w.pos[0, d])
    w.grass[0, iy, ix] = 0.9
    w.grass[0, iy + 3, ix] = 0.9
    put(w, d, (10.0, 10.0), head=(1, 0), vel=(0.24, 0.0))
    put(w, bo, (10.0, 40.0), head=(0, 1), vel=(0.0, 0.08))
    w.refresh()
    w2 = copy.deepcopy(w)
    a1 = np.full((1, w.S), B.EAT)
    a2 = np.full((1, w.S), B.WATCH)
    for _ in range(4):
        w.step(a1)
        w2.step(a2)
        assert same_bits(w.pos, w2.pos) and same_bits(w.vel, w2.vel)


def test_s1_eat_eats_only_what_is_here(cfg):
    w, d, wf, bo = three(cfg)
    iy, ix = cell_of(w, w.pos[0, d])
    w.grass[0, iy, ix] = w.grass_cap[0, iy, ix] = 0.5
    w.refresh()
    E0 = w.E[0, d]
    w.step(np.full((1, w.S), B.EAT))
    assert w.grass[0, iy, ix] < 0.5 and w._gait[0, d] == B.G_STAND
    assert E0 > 0
    # 헛 EAT: 발밑이 eat_min 아래면 먹지 않는다 (예전 세계의 '먹이 없는 서기 EAT 도 찌꺼기를 먹음'은 없다), 옆 셀도 그대로
    w, d, wf, bo = three(cfg)
    iy, ix = cell_of(w, w.pos[0, d])
    w.grass[0, iy, ix] = w.grass_cap[0, iy, ix] = 0.03            # 용량 = 지금 양 (재생이 양을 바꾸지 않게)
    w.grass[0, iy, ix + 1] = w.grass_cap[0, iy, ix + 1] = 0.9
    w.refresh()
    e0 = w.E[0, d]
    w.step(np.full((1, w.S), B.EAT))
    assert w.grass[0, iy, ix] == 0.03 and w.grass[0, iy, ix + 1] == 0.9
    assert w._ekind[0, d] == -1 and w._emult[0, d] == 0.0 and w._gain_u[0, d].sum() == 0.0
    assert w.E[0, d] < e0                                          # 대사만


# --------------------------------------------------------------------------- 3 SHELTER = 제자리 서기


@pytest.mark.parametrize("where", ["outside", "inside"])
def test_s2_shelter_stands(cfg, where):
    w, d, wf, bo = three(cfg)
    put(w, d, (49.0, 55.0) if where == "outside" else (55.0, 55.0))       # 은신처 (55, 55) r 4
    put(w, bo, (55.0, 49.5) if where == "outside" else (56.0, 56.0))
    put(w, wf, (45.0, 55.0))
    w.refresh()
    p0 = w.pos.copy()
    a = np.full((1, w.S), B.SHELTER)
    _run(w, a, 6)
    assert same_bits(w.pos, p0)
    assert (w.act[0, [d, wf, bo]] == B.SHELTER).all()                     # 행동 기록은 SHELTER 그대로
    assert (w._gait[0, [d, wf, bo]] == B.G_STAND).all()


# --------------------------------------------------------------------------- 5 관측 115 = 107 의 자리 이동 (b3b8e668 기준값)


def test_obs_115_is_107_shifted_and_walk_run_unchanged(cfg):
    """WALK·RUN·WATCH 만 고르면 S′ 세계 = b3b8e668 세계(몸 규칙 그대로): food_dir 8 칸을 뺀 관측·보상·죽음·자리·E·지방이 기준값과 비트 같다."""
    c = B.override(cfg, {"counts": {"deer": [16, 64]}, "learner_counts": {"deer": [16, 32, 48, 64]},
                         "food": {"train_grass_total": None}})
    w = R9World(c, [44184, 44185])
    rng = np.random.default_rng(44186)
    choices = np.array(list(range(B.WALK_FIRST, B.RUN_LAST + 1)) + [B.WATCH])
    h = hashlib.sha256()

    def obs107(o):
        return np.concatenate([o[..., :23], o[..., 31:]], -1)
    h.update(np.ascontiguousarray(obs107(w.obs())).tobytes())
    for _ in range(120):
        a = choices[rng.integers(0, len(choices), (w.K, w.S))]
        o, r, d, _ = w.step(a)
        for x in (obs107(o), r, d, w.pos, w.E, w.R, w.alive, w.uid):
            h.update(np.ascontiguousarray(x).tobytes())
    assert h.hexdigest() == GOLDEN_107
    # 기존 자기 칸 번호는 그대로, 뒤 블록은 8 칸 밀림
    assert B.OBS_DIM == 115 and B.N_SELF == 31 and B.OBS_NAMES[23:31] == B.FOOD_DIR_NAMES
    assert B.OBS_NAMES[:23] == ("energy", "reserve", "stamina", "health", "own_size", "age_frac", "birth_wait", "food_density",
                                "food_here", "in_shelter", "shelter_x", "shelter_y", "shelter_edge", "free_0", "free_1", "free_2",
                                "free_3", "free_4", "free_5", "free_6", "free_7", "own_speed", "mating")
    assert B.other_col(0, "present") == 31 and B.KINSUM0 == 97 and B.kin_col(0, "present") == 101
    assert BR.NPZ_SHAPES["W0"] == (64, 115) and BR._OC["dist"][0] == B.other_col(0, "dist")
    assert B.io_contract_dict()["net"]["obs_dim"] == 115 and "food_dir" in B.io_contract_dict()["obs_spec"]


# --------------------------------------------------------------------------- 4 food_dir 합성 격자


def _deer_scene(cfg, head=(1.0, 0.0)):
    w = scene(cfg, [1, 0, 0])
    d = lo(w, D_)
    put(w, d, (31.0, 31.0), head=head)                        # 셀 (15, 15) 중심
    w.refresh()
    return w, d


def _x(e, g, d, R):
    return e * g * (1.0 - d / R)


def test_fd_sector_fov_nose_weight_own_cell(cfg):
    w, d = _deer_scene(cfg)
    ref = float(w.sb["food_here_ref"][0, d])
    e = 0.5
    cases = [((3, 0), 0, 6.0, 20.0), ((0, 3), 2, 6.0, 20.0), ((0, -3), 6, 6.0, 20.0), ((-3, 3), 3, np.hypot(6, 6), 20.0),
             ((2, 2), 1, np.hypot(4, 4), 20.0), ((-1, 0), 4, 2.0, 3.0)]          # 마지막 = 뒤(눈 밖) 2 단위 → 코
    for (ox, oy), j, dist, R in cases:
        w.grass[:] = 0.0
        w.grass[0, 15 + oy, 15 + ox] = 0.8
        w.refresh()
        f = fd_now(w)[0, d]
        x = _x(e, 0.8, dist, R)
        assert np.argmax(f) == j and np.isclose(f[j], x / (x + ref), rtol=0, atol=1e-12), ((ox, oy), f)
        assert (np.delete(f, j) == 0).all()
        assert np.isclose(w.obs()[0, d, 23 + j], np.float32(x / (x + ref)))
    # 뒤 6 단위: 눈 시야각 밖, 코 3 단위 밖 → 0
    w.grass[:] = 0.0
    w.grass[0, 15, 12] = 0.8
    w.refresh()
    assert (fd_now(w)[0, d] == 0).all()
    # 자기 셀은 빼고(food_here 가 맡음), eat_min 아래는 안 셈
    w.grass[:] = 0.0
    w.grass[0, 15, 15] = 0.8
    w.grass[0, 15, 17] = 0.05
    w.refresh()
    assert (fd_now(w)[0, d] == 0).all() and w.obs()[0, d, B.O_FOOD_HERE] > 0
    # 거리 무게 단조: 가까운 셀이 더 크다
    vals = []
    for ox in (2, 4, 6, 8):
        w.grass[:] = 0.0
        w.grass[0, 15, 15 + ox] = 0.8
        w.refresh()
        vals.append(fd_now(w)[0, d, 0])
    assert vals[0] > vals[1] > vals[2] > vals[3] > 0
    # 여러 셀은 더해진다 (같은 부채꼴)
    w.grass[:] = 0.0
    w.grass[0, 15, 18] = 0.8
    w.grass[0, 15, 20] = 0.4
    w.refresh()
    x = _x(e, 0.8, 6.0, 20.0) + _x(e, 0.4, 10.0, 20.0)
    assert np.isclose(fd_now(w)[0, d, 0], x / (x + ref), rtol=0, atol=1e-12)


def test_fd_head_down_when_eating(cfg):
    w, d = _deer_scene(cfg)
    w.grass[0, 15, 22] = 0.8                                   # 14 단위 앞
    w.refresh()
    assert fd_now(w)[0, d, 0] > 0                              # 서 있을 때 눈 20
    w.act[0, d] = B.EAT
    w.refresh()
    assert (fd_now(w)[0, d] == 0).all()                        # 먹는 중 눈 12
    w.grass[0, 15, 20] = 0.8                                   # 10 단위 → 12 안
    w.refresh()
    ref = float(w.sb["food_here_ref"][0, d])
    x = _x(0.5, 0.8, 10.0, 12.0)
    assert np.isclose(fd_now(w)[0, d, 0], x / (x + ref), rtol=0, atol=1e-12)


def test_fd_meat_only_body_and_boar(cfg):
    w = scene(cfg, [1, 1, 1])
    d, wf, bo = lo(w, D_), lo(w, W_), lo(w, R_)
    put(w, d, (5.0, 5.0))
    put(w, wf, (31.0, 31.0))
    put(w, bo, (11.0, 51.0))
    w.grass[:] = 0.9                                           # 늑대는 풀을 느끼지 않는다
    w.refresh()
    assert (fd_now(w)[0, wf] == 0).all()
    deer_kin, wolf_kin = int(w.kin_id[0, d]), int(w.kin_id[0, wf])
    w._add_carcass(0, (34.0, 31.0), 4.0, deer_kin, D_, 900, 0)        # 3 단위 앞
    w._add_carcass(0, (31.5, 31.0), 4.0, deer_kin, D_, 901, 0)        # 0.5 단위 = food_here 몫 → 뺌
    w._add_carcass(0, (31.0, 35.0), 4.0, wolf_kin, W_, 902, 0)        # 같은 종 사체 → 안 먹음
    w.refresh()
    f = fd_now(w)[0, wf]
    x = 4.0 * max(1.0 - 3.0 / 20.0, 1.0 - 3.0 / 5.0) * 1.0
    assert np.argmax(f) == 0 and np.isclose(f[0], x / (x + 4.0), rtol=0, atol=1e-12) and (f[1:] == 0).all()
    assert w.obs()[0, wf, B.O_FOOD_HERE] > 0
    # 멧돼지: 풀·땅속 같은 셀 → (0 + 풀 g w e) + 땅속 r w e ; 사체 고기도 셈
    w.grass[:] = 0.0
    w.carc_ok[:] = False
    iy, ix = 25, 5                                             # 멧돼지 셀 (25, 5) 에서 3 셀 앞 = 6 단위 (눈 8 × 1)
    w.grass[0, iy, ix + 3] = 0.6
    w.root[0, iy, ix + 3] = 0.4
    w.refresh()
    fb = fd_now(w)[0, bo]
    wgt = 1.0 - 6.0 / 8.0
    x = 0.6 * wgt * 0.05 + 0.4 * wgt * 0.15
    assert np.argmax(fb) == 0 and np.isclose(fb[0], x / (x + 0.2), rtol=0, atol=1e-12)


@pytest.mark.parametrize("head", [(1.0, 0.0), (0.6, 0.8), (-0.28, 0.96), (-1.0, -1.0)])
def test_fd_direction_convention_walk_gets_closer(cfg, head):
    """food_dir 가장 큰 칸 j → WALK_{j+1} (= WALK_FIRST + j) 을 고르면 그 먹이에 가까워진다 (왼쪽 = 반시계 부호 포함)."""
    for j in range(8):
        w, d = _deer_scene(cfg, head=head)
        h = w.head[0, d]
        u = B.rotate(h[None], B.DIR8[j][None])[0]
        tgt = w.pos[0, d] + (8.0 if j != 4 else 2.0) * u          # 바로 뒤는 눈 시야각 밖 → 코(3 단위) 안에 둔다
        iy, ix = cell_of(w, tgt)
        w.grass[0, iy, ix] = 0.8
        w.refresh()
        f = w.obs()[0, d, FD]
        assert int(np.argmax(f)) == j, (head, j, f)
        c = np.array([(ix + 0.5) * w.cell, (iy + 0.5) * w.cell])
        d0 = np.hypot(*(c - w.pos[0, d]))
        a = np.full((1, w.S), B.WATCH)
        a[0, d] = B.WALK_FIRST + j
        w.step(a)
        w.step(a)
        assert np.hypot(*(c - w.pos[0, d])) < d0 - 0.3, (head, j)
    # 왼쪽 부호: 머리 +x, 먹이 +y → 칸 2 = WALK_90, 걸으면 y 가 는다
    w, d = _deer_scene(cfg)
    w.grass[0, 19, 15] = 0.8
    w.refresh()
    assert int(np.argmax(w.obs()[0, d, FD])) == 2 and B.ACTION_NAMES[B.WALK_FIRST + 2] == "WALK_90"


def test_fd_direction_convention_random_heads(cfg):
    """(검토 P3) 아무 머리(축 아닌 것 포함)·아무 셀: food_dir 가장 큰 칸 = 그 셀 쪽 가장 가까운 걷기 방향, 한 결정 실제 변위 방향 = rotate(head, DIR8[j])."""
    rng = np.random.default_rng(44198)
    ok = 0
    c = B.override(cfg, {"world": {"shelters": {"fixed": [[55.0, 55.0, 4.0]]}}})
    for _trial in range(60):
        w = R9World(c, [44199], counts=np.array([[1, 0, 0]]))
        s = lo(w, D_)
        w.vel[:] = 0.0
        w.disp[:] = 0.0
        w.grass[:] = 0.0
        w.root[:] = 0.0
        w.grass_cap[:] = 0.0
        w.root_cap[:] = 0.0
        w.g_speed[:] = 1.0
        w.hp[:] = 1.0
        w.E[:] = 0.6
        w.stam_lock[:] = False
        ang = rng.uniform(0, 2 * np.pi)
        h = np.array([math.cos(ang), math.sin(ang)])
        P = np.array([20.0 + rng.uniform(-0.9, 0.9), 20.0 + rng.uniform(-0.9, 0.9)])
        w.pos[0, s] = P
        w.head[0, s] = h
        while True:
            off = rng.integers(-6, 7, 2)
            if (off != 0).any():
                break
        ix, iy = int(P[0] // w.cell) + off[0], int(P[1] // w.cell) + off[1]
        w.grass[0, iy, ix] = 0.8
        w.refresh()
        fd = w.obs()[0, s, FD].astype(np.float64)
        if fd.max() <= 0:
            continue
        j = int(np.argmax(fd))
        tgt = np.array([(ix + 0.5) * w.cell, (iy + 0.5) * w.cell]) - P
        dirs = B.rotate(np.broadcast_to(h, (8, 2)), B.DIR8)
        best = int(np.argmax(dirs @ tgt))
        a = np.full((1, w.S), B.WATCH)
        a[0, s] = B.WALK_FIRST + j
        w.step(a)
        dv = w.pos[0, s] - P
        u = dv / np.linalg.norm(dv)
        assert j == best and float(u @ dirs[j]) >= 1 - 1e-9
        ok += 1
    assert ok > 40


def test_fd_matches_spec_reference(cfg, jcfg):
    """(검토 P1) food_dir = 사양 문장 그대로 쓴 느린 참조(셀·사체 하나씩, math) — 학습 세계(늑대 포함)·판정 세계, 무작위 행동(EAT 자주)."""
    for c, seeds, steps in ((cfg, [44190], 30), (jcfg, [44192], 10)):
        w = R9World(c, seeds)
        rng = np.random.default_rng(44193)
        for _ in range(steps):
            a = rng.integers(0, B.N_ACTIONS, (w.K, w.S))
            a = np.where(rng.random((w.K, w.S)) < 0.35, B.EAT, a)
            o, _, _, _ = w.step(a)
        al = np.nonzero(w.alive[0])[0]
        n = 0
        for s in al[:: max(1, len(al) // 30)]:
            ref = ref_food_dir(w, 0, s).astype(np.float32)
            assert o[0, s, FD].tobytes() == ref.tobytes() or np.max(np.abs(o[0, s, FD] - ref)) < 1e-6
            n += 1
        assert n > 10


def test_fd_carcasses_reference_and_fast_slow(cfg, jcfg):
    """(검토 P1b) 사체가 많은 판(늑대·멧돼지 둘레 0.3~15 단위, 제 종·남의 종 섞어): 참조와 같고 빠른 판 = 느른 판(비트)."""
    nzm = 0
    for c, seeds in ((cfg, [44190, 44191]), (jcfg, [44192])):
        w = R9World(c, seeds)
        ws = R9World(c, seeds)
        ws.food_dir_fast = False
        rng = np.random.default_rng(44195)
        for _rnd in range(4):
            for _ in range(5):
                a = rng.integers(0, B.N_ACTIONS, (w.K, w.S))
                a = np.where(rng.random((w.K, w.S)) < 0.4, B.EAT, a)
                w.step(a)
                ws.step(a)
            for k in range(w.K):
                eaters = [s for s in np.nonzero(w.alive[k])[0] if w.sb["eats"][k, s, B.MEAT]]
                kins = np.unique(w.kin_id[k][w.alive[k]])
                for s in eaters[:6]:
                    for _ in range(2):
                        r = rng.uniform(0.3, 15.0)
                        ang = rng.uniform(0, 2 * np.pi)
                        pos = np.clip(w.pos[k, s] + r * np.array([math.cos(ang), math.sin(ang)]), 0, w.size)
                        kin = int(rng.choice(kins))
                        m = float(rng.uniform(0.5, 4.0))
                        w._add_carcass(k, pos, m, kin, 0, 0, 0)
                        ws._add_carcass(k, pos, m, kin, 0, 0, 0)
            w.refresh()
            ws.refresh()
            assert same_bits(w.obs(), ws.obs()), "fast != slow with carcasses"
            o = w.obs()
            for k in range(w.K):
                al = np.nonzero(w.alive[k])[0]
                al = [s for s in al if w.sb["eats"][k, s, B.MEAT]] + list(al[:: max(1, len(al) // 10)])
                for s in al:
                    r = ref_food_dir(w, k, s).astype(np.float32).astype(np.float64)
                    got = o[k, s, FD].astype(np.float64)
                    assert float(np.max(np.abs(r - got))) <= 1e-6, (k, s)
                    if not w.sb["eats"][k, s, B.GRASS] and not w.sb["eats"][k, s, B.ROOT]:
                        nzm += int((got > 0).any())
    assert nzm > 0


def test_fd_full_circle_view_matches_reference(cfg):
    """(arm_food omni 점검의 본 코드 몫) 시야각을 360° 로 바꾼 몸 줄(fov_cos = −1)도 food_dir 식 = 참조 — 함수가 몸 줄의 fov_cos 만 읽는다."""
    w = R9World(cfg, [44198, 44199])
    rng = np.random.default_rng(44198)
    for _ in range(5):
        w.step(rng.integers(0, B.N_ACTIONS, (w.K, w.S)))
    sb2 = dict(w.sb)
    sb2["fov_cos"] = np.full_like(w.sb["fov_cos"], -1.0)
    a = fd_now(w, sb2)
    b = fd_now(w)
    assert (a >= b - 1e-12).all() and (a > b).any()           # 더 넓게 보면 칸 값이 줄지 않음
    for s in np.nonzero(w.alive[0, :lo(w, W_)])[0][:8]:
        assert np.allclose(a[0, s], ref_food_dir(w, 0, s, fov_cos=-1.0), rtol=0, atol=1e-12)


# --------------------------------------------------------------------------- EAT·SHELTER 숨은 이동 없음 (검토 P2)


class Probe(R9World):
    """EAT·SHELTER 스텝마다 목표 속도 0·걸음 서기·속도는 같은 방향으로 줄기만(가속 없음)."""

    def __init__(self, *a, **k):
        self.bad, self.nchk = [], 0
        super().__init__(*a, **k)

    def _move(self):
        v0 = self.vel.copy()
        act = self.act.copy()
        super()._move()
        m = self.alive & ((act == B.EAT) | (act == B.SHELTER))
        if not m.any():
            return
        self.nchk += int(m.sum())
        tsp = self._tspeed
        n0 = np.sqrt((v0 * v0).sum(-1))
        vf = self._vel_free
        n1 = np.sqrt((vf * vf).sum(-1))
        cos = np.where((n0 > 1e-12) & (n1 > 1e-12), (v0 * vf).sum(-1) / np.maximum(n0 * n1, 1e-300), 1.0)
        bad = m & ((tsp != 0.0) | (self._gait != B.G_STAND) | (n1 > n0 + 1e-15) | (cos < 1 - 1e-9))
        if bad.any():
            self.bad.append((int(self.t[0]), np.argwhere(bad)[:5].tolist()))


def test_eat_shelter_no_hidden_movement(cfg, jcfg):
    for c, seeds, steps in ((cfg, [44194], 120), (jcfg, [44196], 30)):
        w = Probe(c, seeds)
        rng = np.random.default_rng(44197)
        for _ in range(steps):
            a = rng.integers(0, B.N_ACTIONS, (w.K, w.S))
            a = np.where(rng.random((w.K, w.S)) < 0.5, np.where(rng.random((w.K, w.S)) < 0.5, B.EAT, B.SHELTER), a)
            w.step(a)
        assert w.nchk > 2000 and not w.bad
        # S4 규칙 두뇌로도
        w2 = Probe(c, seeds)
        for k in range(w2.K):
            for sp, nm in ((D_, "RULE_DEER"), (W_, "RULE_WOLF"), (R_, "RULE_BOAR")):
                w2.set_controller(k, sp, BR.Controller(BR.make_rule(nm, c, sp), stochastic=False, label=nm))
        for _ in range(steps):
            w2.step(w2.decide())
        assert w2.nchk > 0 and not w2.bad


# --------------------------------------------------------------------------- 이름표 없음 (저장소 시험 2·3·02b 꼴)


FORBID = {"sp", "slot_sp", "carc_sp", "body", "rules", "life", "sp_lo", "sp_hi", "caps", "counts", "_biters", "_bite_mat",
          "_diet_rank", "carc_uid", "carc_killer"}


class Guarded(R9World):
    _guard = False

    def __getattribute__(self, name):
        if name in FORBID and object.__getattribute__(self, "_guard"):
            raise AssertionError(f"perception/observation read hidden '{name}'")
        return object.__getattribute__(self, name)

    def _perceive(self, update_mem):
        object.__setattr__(self, "_guard", True)
        try:
            return super()._perceive(update_mem)
        finally:
            object.__setattr__(self, "_guard", False)

    def _observe(self):
        object.__setattr__(self, "_guard", True)
        try:
            return super()._observe()
        finally:
            object.__setattr__(self, "_guard", False)


def _with_carcasses(w, rng):
    for _ in range(40):
        w.step(rand_act(rng, w))
    for k in range(w.K):                                        # 늑대 곁에 사체를 둬서 고기 길도 지나가게
        for s in range(lo(w, W_), int(w.sp_hi[W_])):
            if w.alive[k, s]:
                dk = int(w.kin_id[k, lo(w, D_)])
                w._add_carcass(k, np.clip(w.pos[k, s] + np.array([3.0, 1.0]), 0, 60), 3.0, dk, D_, 7000 + s, 0)
                break
    w.refresh()


def test_label_guard_obs_never_reads_species(cfg):
    g = Guarded(cfg, SEEDS[:2])
    p = R9World(cfg, SEEDS[:2])
    rng = np.random.default_rng(44187)
    for _ in range(40):
        a = rand_act(rng, g)
        og, rg, _, _ = g.step(a)
        op, rp, _, _ = p.step(a)
        assert same_bits(og, op) and same_bits(rg, rp)
    assert (og[..., FD] > 0).any()


def _perm_body(body, pinv):
    ch = {}
    for f in dataclasses.fields(body):
        v = getattr(body, f.name)
        if isinstance(v, np.ndarray) and v.shape[:1] == (3,):
            v = v[pinv]
            if f.name == "bites":
                v = v[:, pinv]
            ch[f.name] = v
        elif f.name == "diet_order":
            ch[f.name] = tuple(v[i] for i in pinv)
    return dataclasses.replace(body, **ch)


def _obs_now(w):
    w._perceive(update_mem=False)
    return w._observe()


def test_label_relabel_and_kin_perm(cfg):
    w = R9World(cfg, [44188, 44189, 44190])
    _with_carcasses(w, np.random.default_rng(44188))
    o1 = _obs_now(w)
    lw, hw = lo(w, W_), int(w.sp_hi[W_])
    assert (o1[:, lw:hw, FD] > 0).any()                          # 늑대가 사체를 느낀다 (고기 길 확인)
    for pi in ([2, 0, 1], [1, 2, 0], [0, 2, 1]):
        pi = np.asarray(pi)
        pinv = np.argsort(pi)
        w2 = copy.deepcopy(w)
        w2.sp = pi[w.sp].astype(np.int8)
        w2.slot_sp = pi[w.slot_sp].astype(np.int8)
        w2.carc_sp = np.where(w.carc_sp >= 0, pi[np.maximum(w.carc_sp, 0)], -1).astype(np.int8)
        w2.body = _perm_body(w.body, pinv)
        w2.sb = B.expand_body(w2.body, w2.sp)
        w2.kin_perm = w.kin_perm[:, pinv]
        assert same_bits(_obs_now(w2), o1)
    for sig in ([1, 2, 0], [2, 1, 0]):
        sig = np.asarray(sig, dtype=np.int8)
        w2 = copy.deepcopy(w)
        w2.kin_perm = sig[w.kin_perm]
        w2.kin_id = sig[w.kin_id]
        w2.carc_kin = np.where(w.carc_kin >= 0, sig[np.maximum(w.carc_kin, 0)], -1).astype(np.int8)
        assert same_bits(_obs_now(w2), o1)


def test_label_fd_reads_only_observers_body_row(cfg):
    w = R9World(cfg, [44191])
    _with_carcasses(w, np.random.default_rng(44191))
    base = dict(w.sb)
    f0 = fd_now(w)
    donors = [lo(w, sp) for sp in range(3)]
    hit = 0
    for sp in range(3):
        i = lo(w, sp)
        if not w.alive[0, i]:
            continue
        for dn in donors:
            if int(w.slot_sp[dn]) == sp:
                continue
            sb2 = {}
            for key, a in base.items():
                if isinstance(a, np.ndarray) and a.shape[:2] == (w.K, w.S):
                    b = a.copy()
                    b[0, np.arange(w.S) != i] = a[0, dn]
                    sb2[key] = b
                else:
                    sb2[key] = a
            assert same_bits(fd_now(w, sb2)[0, i], f0[0, i])
            hit += 1
    assert hit >= 3


# --------------------------------------------------------------------------- 6 결정성


def test_determinism_batch_and_fast_slow(cfg, jcfg):
    a = R9World(cfg, SEEDS)
    b = R9World(cfg, SEEDS)
    c = R9World(cfg, [SEEDS[2]])
    d = R9World(cfg, SEEDS[::-1])
    slow = R9World(cfg, SEEDS)
    slow.food_dir_fast = False
    slow.refresh()
    full = R9World(cfg, SEEDS, pairs_full=True)
    assert same_bits(a.obs(), b.obs()) and same_bits(a.obs()[2:3], c.obs()) and same_bits(a.obs()[::-1], d.obs())
    assert same_bits(a.obs(), slow.obs())
    rng = np.random.default_rng(44192)
    for _ in range(100):
        act = rand_act(rng, a)
        oa, ra, _, _ = a.step(act)
        ob, rb, _, _ = b.step(act)
        oc, rc, _, _ = c.step(act[2:3])
        od, rd, _, _ = d.step(act[::-1])
        os_, rs, _, _ = slow.step(act)
        of, rf, _, _ = full.step(act)
        assert same_bits(oa, ob) and same_bits(ra, rb)
        assert same_bits(oa[2:3], oc) and same_bits(ra[2:3], rc)
        assert same_bits(oa[::-1], od) and same_bits(ra[::-1], rd)
        assert same_bits(oa, os_) and same_bits(oa, of) and same_bits(ra, rf)
    assert (oa[..., FD] > 0).any()
    for n in ("pos", "vel", "E", "R", "grass", "root", "carc_meat", "uid"):
        assert same_bits(getattr(a, n), getattr(b, n)) and same_bits(getattr(a, n)[2:3], getattr(c, n)), n
    ja = R9World(jcfg, [44193, 44194])
    jb = R9World(jcfg, [44194])
    rng = np.random.default_rng(44193)
    for _ in range(20):
        act = rand_act(rng, ja)
        oa, ra, _, _ = ja.step(act)
        ob, rb, _, _ = jb.step(act[1:2])
        assert same_bits(oa[1:2], ob) and same_bits(ra[1:2], rb)


def test_determinism_judge_fast_slow(jcfg):
    """판정 세계(120 × 120, 사분면 넷)에서도 빠른 판 = 느린 판(비트) — S4 규칙 두뇌가 결정하는 닫힌 고리."""
    w = R9World(jcfg, [44186, 44187])
    s = R9World(jcfg, [44186, 44187])
    s.food_dir_fast = False
    s.refresh()
    for x in (w, s):
        for k in range(x.K):
            for sp, nm in ((D_, "RULE_DEER"), (W_, "RULE_WOLF"), (R_, "RULE_BOAR")):
                x.set_controller(k, sp, BR.Controller(BR.make_rule(nm, jcfg, sp), stochastic=False, label=nm))
    assert same_bits(w.obs(), s.obs())
    for _ in range(60):
        aw, as_ = w.decide(), s.decide()
        assert same_bits(aw, as_)
        ow, rw, _, _ = w.step(aw)
        os_, rs, _, _ = s.step(as_)
        assert same_bits(ow, os_) and same_bits(rw, rs)
    assert (ow[..., FD] > 0).any()


def test_fd_fast_prefilter_and_half_sector_bit_identical(cfg, monkeypatch):
    """속도 줄이기(11-12) 빠른 길: (1) 오프셋 거리 아래 경계는 자기 셀 안 어느 자리에서도 실제 셀 중심 거리 이하(자기 셀 = inf),
    (2) DIR8 뒤 네 줄 = 앞 네 줄의 정확한 부호 반대 → 반쪽 칸 셈 = 여덟 칸 셈(같은 값·경계 동점 포함),
    (3) 반지름 묶음 길·마스크 길(묶음 수 넘음)·개체마다 다른 눈 거리 모두 기준 길(seq_sum 전체 표)과 비트 같다."""
    # (1) lower bound
    for n in (4, 11):
        lb = W.offset_lower_bound(n, 2.0)
        ox, oy = W.offset_table(n)
        own = (ox == 0) & (oy == 0)
        assert np.isinf(lb[own]).all() and np.isfinite(lb[~own]).all()
        rng = np.random.default_rng(44195)
        fr = np.concatenate([rng.random((400, 2)), [[0.0, 0.0], [0.999999, 0.999999], [0.0, 0.999999], [0.5, 0.5]]])
        for fx, fy in fr:
            vx = (ox + 0.5 - fx) * 2.0
            vy = (oy + 0.5 - fy) * 2.0
            d = np.sqrt(vx * vx + vy * vy)
            assert (lb[~own] <= d[~own] + 1e-12).all()
    # (2) half sector
    assert np.array_equal(B.DIR8[4:], -B.DIR8[:4])                             # 값 비교 (0 의 부호만 다름)
    rng = np.random.default_rng(44196)
    h = rng.normal(size=(500, 2))
    h /= np.sqrt((h * h).sum(1))[:, None]
    h[:8] = B.DIR8
    Dd = B.rotate(h[:, None, :], B.DIR8[None, :, :])
    v = np.concatenate([rng.normal(size=(200, 2)) * 10.0, Dd[:100, 3], Dd[100:200, 0] + Dd[100:200, 1],
                        np.round(rng.normal(size=(100, 2)) * 5.0) + 0.5])            # 방향 그대로·두 칸 사이·셀 꼴
    for vv in (v, -v):
        assert np.array_equal(W._fd_sector(vv[:, 0], vv[:, 1], Dd[..., 0], Dd[..., 1]),
                              W._fd_sector_half(vv[:, 0], vv[:, 1], Dd[:, :4, 0], Dd[:, :4, 1]))
    # (3) paths vs reference
    w = R9World(cfg, [44197, 44198])
    rng = np.random.default_rng(44197)
    for _ in range(15):
        a = rand_act(rng, w)
        w.step(np.where(rng.random(a.shape) < 0.4, B.EAT, a))
    ref = fd_now(w, fast=False)
    assert (ref > 0).any()
    assert same_bits(fd_now(w), ref)
    monkeypatch.setattr(W, "FD_RADIUS_GROUPS", 0)
    assert same_bits(fd_now(w), ref)
    monkeypatch.undo()
    sb = dict(w.sb)
    sb["see_r"] = w.sb["see_r"] * (0.5 + rng.random(w.sb["see_r"].shape))      # 개체마다 다른 눈 거리 → 묶음 수 넘음
    ref2 = fd_now(w, sb=sb, fast=False)
    assert not same_bits(ref2, ref)
    assert same_bits(fd_now(w, sb=sb), ref2)


def test_eval_run_batch_4_equals_1(cfg):
    """S 규칙 Controller 로 r9_eval_core.run 을 묶음 4 와 묶음 1 로 — 기록이 비트 같다 (세계 묶음 수와 무관)."""
    if str(EVAL_DIR) not in sys.path:
        sys.path.insert(0, str(EVAL_DIR))
    import eval_r9 as EV
    import r9_eval_core as C
    c = B.override(cfg, EV.EVAL_FACING)
    specs = {D_: (lambda k: "RULE_DEER" if k % 2 == 0 else "ALWAYS_EAT"), W_: (lambda k: "RULE_WOLF" if k < 3 else "NOHUNT"),
             B.BOAR: (lambda k: "RULE_BOAR" if k % 2 == 0 else "ALWAYS_EAT")}
    r4 = C.run(c, SEEDS, 400, EV.spec_fn(c, specs, {}), scenes=False)
    r1 = C.run(c, SEEDS, 400, EV.spec_fn(c, specs, {}), scenes=False, chunk=1)
    assert r4.keys() == r1.keys()

    def js(x):
        return json.dumps(C.to_jsonable(x), sort_keys=True, default=str)
    for key in r4:
        if isinstance(r4[key], list):
            # 사건 목록(죽음·사냥 구간 …)은 묶음을 이어 붙인 차례만 다르다(묶음 4 = 시간 → 세계, 묶음 1 = 세계 → 시간) — 내용은 같은 모음
            assert sorted(js(e) for e in r4[key]) == sorted(js(e) for e in r1[key]), key
        else:
            assert js(r4[key]) == js(r1[key]), key
    br = EV.spec_fn(c, specs, {})(1, D_, SEEDS[1]).brain
    assert isinstance(br, BR.RuleBrain) and br.name == "ALWAYS_EAT" and br.params["here_min"] == BR.here_min_of(c, D_)
    assert EV.spec_fn(c, specs, {})(1, B.BOAR, SEEDS[1]).brain.params["here_min"] == BR.here_min_of(c, B.BOAR)
    sm = C.species_metrics(r4)
    assert sm["deer"]["act_walk"] > 0                    # S4 규칙은 먹이를 찾아 걷는다 (세계가 걸어 주지 않음)


# --------------------------------------------------------------------------- 7 규칙 두뇌는 관측만


def _world_with_rules(cfg, seeds):
    w = R9World(cfg, seeds)
    for k in range(w.K):
        for sp, nm in ((D_, "RULE_DEER"), (W_, "RULE_WOLF"), (R_, "RULE_BOAR")):
            w.set_controller(k, sp, BR.Controller(BR.make_rule(nm, cfg, sp), stochastic=False, label=nm))
    return w


def test_rule_brains_read_only_obs(cfg):
    w = _world_with_rules(cfg, [44195, 44196])
    for _ in range(30):
        w.step(w.decide())
    # 숨은 세계 상태를 바꿔도(관측은 그대로) 결정이 같다 → 두뇌는 관측(+ 자기 기억·facing_f)만 읽는다
    w2 = copy.deepcopy(w)
    w2.grass[:] = 0.0
    w2.root[:] = 0.0
    w2.pos[:] += 1.0
    w2.sp[:] = 0
    w2.carc_ok[:] = False
    assert same_bits(w.decide(), w2.decide())
    # 같은 관측 블록·같은 u·같은 기억이면 세계 없이 같은 행동
    for nm, sp in (("RULE_DEER", D_), ("RULE_BOAR", R_), ("RULE_WOLF", W_), ("ALWAYS_EAT", D_), ("ALWAYS_EAT", R_),
                   ("HIDE_DEER", D_), ("HIDE_BOAR", R_), ("NOHUNT", W_), ("NOHUNT_RUN", W_), ("RANDOM", D_)):
        br = BR.make_rule(nm, cfg, sp)
        assert list(inspect.signature(br.decide).parameters) == ["obs", "u", "stochastic", "state", "ctx"]
        blk = w.obs()[0, lo(w, sp):int(w.sp_hi[sp])]
        u = np.random.default_rng(44197).random((blk.shape[0], B.N_ACTIONS))
        a1, _ = br.decide(blk, u, False, br.new_state(blk.shape[0]), {"facing_f": 0.9})
        a2, _ = br.decide(blk.copy(), u.copy(), False, br.new_state(blk.shape[0]), {"facing_f": 0.9})
        assert same_bits(a1, a2) and ((a1 >= 0) & (a1 < B.N_ACTIONS)).all()
    # 관측 115 칸이 아니면 거부 (예전 107 칸 두뇌 입력이 섞이지 않게)
    with pytest.raises(ValueError):
        BR.make_rule("RULE_DEER", cfg).decide(np.zeros((2, 107), np.float32), np.zeros((2, 19)), False, None, {})


def test_rule_deer_seek_logic_on_hand_obs(cfg):
    br = BR.make_rule("RULE_DEER", cfg)
    o = np.zeros((4, B.OBS_DIM), np.float32)
    o[:, B.O_ENERGY] = 0.5
    o[:, B.O_FREE0:B.O_FREE0 + 8] = 1.0
    o[:, B.O_SHELTER_EDGE] = 1.0
    o[0, B.O_FOOD_HERE] = 0.5                                   # 발밑 → EAT
    o[1, 23 + 3] = 0.4                                           # 칸 3 → WALK_135
    o[2, 23 + 5] = 0.2
    o[2, 23 + 6] = 0.3                                           # 가장 큰 칸 6
    o[3, B.O_FOOD_HERE] = 0.03                                   # eat_min 아래 → 찾기(앞으로)
    a, _ = br.decide(o, np.zeros((4, 19)), False, None, {"facing_f": 0.9})
    assert list(a) == [B.EAT, B.WALK_FIRST + 3, B.WALK_FIRST + 6, B.WALK_FIRST + 0]
    blind = BR.make_rule("RULE_DEER", cfg, blind=True)
    a, _ = blind.decide(o, np.zeros((4, 19)), False, None, {"facing_f": 0.9})
    assert list(a) == [B.EAT, B.WALK_FIRST, B.WALK_FIRST, B.WALK_FIRST]
    # 위협 + 은신처 가장자리 8 안 → 은신처 쪽 RUN, 안이면 SHELTER
    o = np.zeros((2, B.OBS_DIM), np.float32)
    o[:, B.O_ENERGY] = 0.5
    o[:, B.O_FREE0:B.O_FREE0 + 8] = 1.0
    o[:, B.other_col(0, "present")] = 1.0
    o[:, B.other_col(0, "dist")] = 5.0 / 20
    o[:, B.other_col(0, "approach")] = 0.5
    o[:, B.other_col(0, "rel_x")] = 5.0 / 20
    o[0, B.O_SHELTER_EDGE] = 3.0 / 20
    o[0, B.O_SHELTER_Y] = 1.0                                    # 은신처는 왼쪽
    o[1, B.O_IN_SHELTER] = 1.0
    a, _ = br.decide(o, np.zeros((2, 19)), False, None, {"facing_f": 0.9})
    assert list(a) == [B.RUN_FIRST + 2, B.SHELTER]


def test_rule_stuck_memory_leaves_unchanging_food_here(cfg):
    """EAT 를 골랐는데 다음 관측의 food_here 가 줄지 않았으면(먹지 못함 — eat_min 아래 찌꺼기) 먹이 찾기로 넘어간다 (자기 기억만)."""
    for nm, sp in (("RULE_DEER", D_), ("RULE_BOAR", R_), ("ALWAYS_EAT", D_), ("ALWAYS_EAT", R_)):
        br = BR.make_rule(nm, cfg, sp)
        st = br.new_state(2)
        o = np.zeros((2, B.OBS_DIM), np.float32)
        o[:, B.O_ENERGY] = 0.5
        o[:, B.O_FREE0:B.O_FREE0 + 8] = 1.0
        o[:, B.O_FOOD_HERE] = 0.5
        o[1, 23 + 2] = 0.3
        u = np.zeros((2, B.N_ACTIONS))
        a1, _ = br.decide(o, u, False, st, {"facing_f": 0.9})
        assert list(a1) == [B.EAT, B.EAT], nm
        a2, _ = br.decide(o, u, False, st, {"facing_f": 0.9})          # 줄지 않음 → 막힘
        assert list(a2) == [B.WALK_FIRST, B.WALK_FIRST + 2], nm
        o2 = o.copy()
        o2[:, B.O_FOOD_HERE] = 0.45                                        # 걷고 나서 새 셀 (지난 행동 WALK) → 다시 EAT
        a3, _ = br.decide(o2, u, False, st, {"facing_f": 0.9})
        assert list(a3) == [B.EAT, B.EAT], nm
        o3 = o2.copy()
        o3[:, B.O_FOOD_HERE] = 0.40                                        # 먹어서 줄었음 → 계속 EAT
        a4, _ = br.decide(o3, u, False, st, {"facing_f": 0.9})
        assert list(a4) == [B.EAT, B.EAT], nm


def test_rule_thresholds_from_body_table(cfg):
    """발밑 문턱 = max_f(e_f × eat_min) / food_here_ref: 사슴 0.06, 멧돼지 0.045 (땅속 0.15 × 0.06 / 0.2), 고기만 먹는 늑대 1e-9."""
    assert np.isclose(BR.here_min_of(cfg, D_), 0.06) and np.isclose(BR.here_min_of(cfg, R_), 0.045)
    assert BR.here_min_of(cfg, W_) == 1e-9
    assert BR.make_rule("RULE_BOAR", cfg).params["here_min"] == BR.here_min_of(cfg, R_)
    assert all(BR.make_rule(n, cfg, BR.RULE_SPECIES[n] if BR.RULE_SPECIES[n] is not None else D_).n_state
               == BR.RULE_N_BASE.get(n, 0) + 2 for n in BR.RULE_NAMES)
    with pytest.raises(ValueError):
        BR.make_rule("ALWAYS_EAT", cfg)                          # 사슴·멧돼지 모두 쓰는 두뇌 — 종이 있어야 문턱을 안다


# --------------------------------------------------------------------------- 8 서 있는 늑대는 물지 못한다 (물기 규칙 그대로)


@pytest.mark.parametrize("wolf_act", [B.EAT, B.SHELTER, B.WATCH])
def test_standing_wolf_cannot_bite(cfg, wolf_act):
    w = scene(cfg, [1, 1, 0])
    d, wf = lo(w, D_), lo(w, W_)
    put(w, wf, (30.0, 30.0), head=(1, 0))
    put(w, d, (30.6, 30.0), head=(1, 0))
    w.E[0, wf] = 0.3
    w._add_carcass(0, (34.0, 30.0), 3.0, int(w.kin_id[0, d]), D_, 905, 0)   # 사체가 사슴 너머에 있어도 (예전 세계는 EAT 로 걸어가 물었다)
    w.refresh()
    a = np.full((1, w.S), B.WATCH)
    a[0, wf] = wolf_act
    for _ in range(6):
        w.step(a)
    assert w.st["bites"].sum() == 0 and w.st["deaths"].sum() == 0
    # 대조: 다가가면(WALK_0) 문다 — 물기는 행동과 무관한 몸 규칙(앞쪽 원뿔·닿는 거리·다가가는 속도 > 0.03)
    w2 = scene(cfg, [1, 1, 0])
    put(w2, lo(w2, W_), (30.0, 30.0), head=(1, 0))
    put(w2, lo(w2, D_), (30.6, 30.0), head=(1, 0))
    w2.refresh()
    a2 = np.full((1, w2.S), B.WATCH)
    a2[0, lo(w2, W_)] = B.WALK_FIRST
    for _ in range(3):
        w2.step(a2)
    assert w2.st["deaths"][0, D_, W.CAUSE_BITE] == 1               # 학습 세계는 곧바로 다시 나므로 죽음 장부로 본다


def test_moving_wolf_inertia_can_still_bite_documented(cfg):
    """[알려진 몸 물리] 뛰던 늑대가 WATCH/EAT 를 골라도 가속 한계로 몇 스텝 미끄러지며(속도 > 0.03) 물 수 있다 — 서기 늑대만 못 문다.
    '뛸 때만 묾'은 버렸다(사용자 결정 2026-11-12 4 항 — C0-3 반격 몫이 두 묶음 모두 떨어지고 뛰는 청소부를 막지 못함)."""
    w = scene(cfg, [1, 1, 0])
    d, wf = lo(w, D_), lo(w, W_)
    put(w, wf, (30.0, 30.0), head=(1, 0), vel=(0.6, 0.0))
    put(w, d, (31.2, 30.0), head=(1, 0))
    w.refresh()
    a = np.full((1, w.S), B.WATCH)
    for _ in range(3):
        w.step(a)
    assert w.st["deaths"][0, D_, W.CAUSE_BITE] == 1


# --------------------------------------------------------------------------- 9 학습 쪽 (VecEnv 115·일꾼)


def test_vec_env_obs_space_and_rule_opponents(cfg):
    from env_v2 import r9_vec_env as VE
    assert VE.OBS_SPACE.shape == (115,)
    core = type("X", (), {"_brains": {}, "cfg": cfg})()
    for name, sp, fn in (("RULE_DEER", D_, BR._rule_deer), ("RULE_WOLF", W_, BR._rule_wolf), ("ALWAYS_EAT", R_, BR._always_eat)):
        b = VE._ShardCore._brain(core, "rule", name, sp)
        assert isinstance(b, BR.RuleBrain) and BR._RULES[b.name] is fn and b.params["here_min"] == BR.here_min_of(cfg, sp)
    v = VE.R9VecEnv(cfg, "deer", seeds=[44180, 44181, 44182, 44183, 44184], num_worlds=4)
    try:
        assert v.num_envs == 16 + 24 + 32 + 40 and v.observation_space.shape == (115,)
        o = v.reset()
        assert o.shape == (112, 115) and (o[:, FD] > 0).any()
    finally:
        v.close()


def test_shard_worker_env_and_command(monkeypatch):
    """일꾼 프로세스는 저장소 폴더(ROOT)에서 같은 모듈(-m env_v2.r9_vec_env)로 돌고, 바이트코드를 저장소에 쓰지 않는다(PYTHONDONTWRITEBYTECODE)."""
    from env_v2 import r9_vec_env as VE
    seen = {}

    class FakePopen:
        def __init__(self, args, **kw):
            seen.update(kw)
            seen["args"] = list(args)
            raise OSError("stop before start")
    monkeypatch.setattr(VE.subprocess, "Popen", FakePopen)
    with pytest.raises(OSError):
        VE._RemoteShard(())
    assert seen["env"]["PYTHONDONTWRITEBYTECODE"] == "1" and seen["env"]["OMP_NUM_THREADS"] == "1"
    assert seen["cwd"] == str(VE.ROOT) and seen["args"][-4:-2] == ["env_v2.r9_vec_env", "--shard-worker"]


def test_learner_rollout_and_counts(cfg):
    """(N) 사슴 학습 칸 합 896, 롤아웃 = 896 × n_steps 32 = 28,672 = 7 × 4,096. 상대 사슴 16~40."""
    tot = {n: sum(cfg["learner_counts"][n][k % len(cfg["learner_counts"][n])] for k in range(cfg["train"]["worlds"][n]))
           for n in B.SPECIES}
    assert tot["deer"] == 896 and tot["deer"] * cfg["train"]["n_steps"]["deer"] == 28672 and 28672 % 4096 == 0
    assert cfg["counts"]["deer"] == [16, 40] and cfg["learner_counts"]["deer"] == [16, 24, 32, 40]
    assert "walk_eat_mult" not in cfg["body_common"] and "graze" not in cfg["body_common"]
    with pytest.raises(ValueError):
        B.override(cfg, {"body_common": {"walk_eat_mult": 0.5}})        # 예전 EAT 걷기 값은 받지 않는다


# --------------------------------------------------------------------------- 11 (N) 학습 세계 풀 70


def test_train_grass_total_70(cfg, jcfg):
    w = R9World(cfg, [44180, 44181, 44182])
    cmg = float(cfg["food"]["grass"]["cover_mult"])
    for k in range(w.K):
        pre = np.where(w.cover_cell[k], w.grass_cap[k] / cmg, w.grass_cap[k])
        assert abs(float(W.seq_sum(pre.reshape(-1))) - 70.0) < 1e-9
        assert same_bits(w.grass[k], w.grass_cap[k])
    # 맞춤을 끄면(null) 예전 생성기 그대로 — 모양은 같고 크기만 다르다 (재생 속도는 맞추지 않음)
    c0 = B.override(cfg, {"food": {"train_grass_total": None}})
    w0 = R9World(c0, [44180, 44181, 44182])
    for k in range(w.K):
        pre0 = np.where(w0.cover_cell[k], w0.grass_cap[k] / cmg, w0.grass_cap[k])
        f = 70.0 / float(W.seq_sum(pre0.reshape(-1)))
        assert np.allclose(w.grass_cap[k], w0.grass_cap[k] * f, rtol=1e-12, atol=0)
        assert same_bits(w.grass_regen[k], w0.grass_regen[k]) and same_bits(w.root_cap[k], w0.root_cap[k])
    # 판정 세계는 이 값을 읽지 않는다 (사분면 70 이 맡음)
    j1 = R9World(jcfg, [44186])
    j2 = R9World(B.override(jcfg, {"food": {"train_grass_total": 35.0}}), [44186])
    assert same_bits(j1.grass_cap, j2.grass_cap)
    with pytest.raises(ValueError):
        B.override(cfg, {"food": {"train_grass_total": 0.0}})
