"""v3 10-27 고침 골든 내보내기 — 먹기 걷기 고침(repertoire.graze_* — env_v2/repertoire.py `graze_calm_dir`)·거리 두기(쉬는 늑대, wild_flight.rest_keep* —
env_v2/world.py 모듈 docstring '거리 두기')를 언리얼 C++ (EcoRepertoire.h GrazeCalmDir·Control, EcoWorldV3.h UpdateWildFlight 의 kKeepRest·FlightRestControl·
FlightRestBand·FlightAlertControl·Step)과 비트 단위로 맞출 골든 헤더를 만든다 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_WILD1_SPEC.md 13절).

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_calm.py
    # 시험용 다른 폴더
    python export_golden_v3_calm.py --out <폴더>

세계·시드: configs/v3_wild3_calm_mirror.yaml (= v3_wild3_mirror.yaml + 두 고침 — 언리얼 게임 기본의 거울). 시드는 탐색 32081~32089 만(판정 시드 밖).
묶음 (검사는 Tests/CalmGoldenCheckV3.h — UE 시험 AdaptiveEcosystem.Policy.V3.Calm.*, g++ tests/cpp/calm_v3_main.cpp):
  1 정의       설정 값(graze_*·rest_keep*) — C++ FRepertoireConfig·FWildFlightConfig 기본(끔)과 통합 기본(eco.IntegratedV3.GrazeCalm·RestKeep 1)이 맞춘다
  2 방향       `graze_calm_dir` 사례 (계수 넷·raw·heading·자리·무대 → 방향): 가운데·벽·모서리·가장자리 경계 e = R 과 바로 밑·자리 0·한 변 정확히·
               관성만·가장자리만·벽 여유만·합이 0(raw = −관성·heading — 원래 방향으로)·벽 여유가 다 지움(원래 방향으로)·난수 사례
  3 제어       `repertoire.control` GRAZE 사례 (먹이 모자람·충분, 방향 없음, 계수 켬) → 속도·보행 — C++ R3::Control
  4 덮기 장면  `World._wf_update` (스텝 끝 H) — 손 장면(쉬는 늑대 시작·시야각 밖·이어짐·V + 여유 경계 ± ulp·들어갈 때 V 경계·가림·은신처 안·사냥 늑대
               우선·도주 우선·두 늑대·자는 늑대·발소리·죽음·벽, 10-27 적대적 검토 — 이어지는 거리 두기의 방향 관성·합 0·시작과 지난 경계는 잇지 않음·벽 앞
               굽히는 쪽)과 난수 장면(지난 덮기 방향은 따로 뽑는다). 사슴마다 지난 덮기 방향을 넣고 다음 덮기·방향·잠금 — C++ UpdateWildFlight
  5 B 장면     `World._wf_rest_control`·`_wf_rest_band` (덮기 REST 의 걸어서 물러남 — 분리의 늑대 쪽 성분 지움·벽 여유, 다가가지 않기 띠 — 늑대 번호 차례·
               다 지워져 멈춤) → 속도·보행·섭식·대사·시야 배수 — C++ FlightRestControl·FlightRestBand
  6 기준 루프  거울 세계(사슴 48·늑대 4, 부활 없음) 600 스텝을 내장 R1b(ckpt/v3/v3_r1_g995_s3_20m.zip = PolicyWeightsV3.h)로: 두 고침 켬·끔(같은 시작 상태·
               같은 세계 난수) × 지역 둘(숲 — 비·나무 24, 메마른 땅 — 맑음·나무 0). 스텝마다 지문(아래), 100 스텝마다 기록 열 칸(잡힘·굶음·산·덮기별 실행
               사슴-스텝 다섯·띠가 방향을 바꾼·멈춘 사슴-스텝). C++ 은 같은 시작 상태(ceval.native_job)·같은 세계 난수(numpy PCG64 날 64 비트 — FRng::External)·
               통합 모드처럼 산 사슴만 Step 에 넘긴다. 끔 판은 켬 판 설정에서 두 고침만 끈다(끈 칸의 여유·띠는 엉뚱한 값이어도 읽지 않아야 한다 — Junk).
지문 = sha256 앞 8 바이트(리틀 엔디언) — 어둠·피식 EMA, 사슴 x·y·hx·hy·에너지·비축(칸마다 슬롯 순서), 죽음 까닭, 덮기, 스텝 첫머리 산 사슴의 행동·관측 18(float32),
  산 ∧ 덮기가 도주·웅크림이 아닌 사슴의 다음 요청, 산 ∧ 덮기가 경계·도주·거리 두기인 사슴의 덮기 방향(x, y), 늑대 x·y·hx·hy·쿨다운·남은 배부름.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import copy
import hashlib
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for _p in (HERE / "results" / "v3" / "live", HERE / "results" / "v3" / "adapt", HERE / "results" / "v3" / "mirror", HERE / "results" / "v3" / "r4",
           HERE / "results" / "v3" / "wild2"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import export_golden_v3_foliage as fg  # noqa: E402
from env.config import Config  # noqa: E402
from env_v2 import repertoire as rep  # noqa: E402
from env_v2.config import load_v2_config  # noqa: E402
from env_v2.features import OPTIONAL_KEYS  # noqa: E402
from env_v2.steering import normalize  # noqa: E402
from env_v2.world import (GAIT_RUN, GAIT_STOP, GAIT_WALK, WF_ALERT, WF_NONE, WF_PANIC, WF_REST, WF_SHELTER, World)  # noqa: E402

CALM = HERE / "configs" / "v3_wild3_calm_mirror.yaml"
MODEL = HERE / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
DEFAULT_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
HEADER = "CalmGoldenVectorsV3.h"
SEED_DIR = 32081
SEED_CTL = 32082
SEED_SCENE = 32083
SEED_B = 32084
LOOP_SEEDS = (32085, 32086, 32087, 32088, 32089)
LOOP_REGIONS = ("Forest", "Barren")
N_SCENE = 16
N_LOOP = 48
LOOP_STEPS = 600
LOOP_EVERY = 100
CHECK_LEN = 10                      # 잡힘·굶음·산 + 덮기별 실행 사슴-스텝 다섯 + 띠 방향 바꿈·멈춤
NEAR_TIE = 1e-4
D_SIZE = 60.0                       # 방향 사례 무대 한 변

d_lit, i_lit, i64_lit, u64_lit, c_array = fg.d_lit, fg.i_lit, fg.i64_lit, fg.u64_lit, fg.c_array


def f32_lit(x) -> str:
    return fg.f_lit(x)


def calm_cfg(n: int, region: str | None = None, on: bool = True):
    """거울 설정 (사슴 n, 지역 region — 날씨·원판 덮기: run_mirror 와 같은 두 칸). on 거짓이면 두 고침만 끈다(graze_* 0·rest_keep false)."""
    import run_mirror as rm

    cfg = load_v2_config(CALM).replace(N=n)
    d = copy.deepcopy(cfg.to_dict())
    f = d["v2"]["features"]
    if region is not None:
        f["wild_weather"]["region"] = region
        lay = rm.load_unreal_obstacles(HERE / "results" / "v3" / "wild2" / "trees" / "tree_layout.json", rm.parse_unreal_maps("20010"))
        f["obstacles"]["fixed"] = lay[(20010, region)]
    if not on:
        for k in rep.GRAZE_CALM_KEYS:
            f["repertoire"][k] = 0.0
        f["wild_flight"]["rest_keep"] = False
    return Config(d)


def p_of(R, W, I, M) -> dict:
    p = dict(graze_edge_r=float(R), graze_edge_w=float(W), graze_inertia=float(I), graze_wall_margin=float(M))
    p["calm"] = (p["graze_edge_r"] > 0.0 and p["graze_edge_w"] > 0.0) or p["graze_inertia"] > 0.0 or p["graze_wall_margin"] > 0.0
    return p


# --------------------------------------------------------------------- #
# 2 방향 사례
# --------------------------------------------------------------------- #


def dir_cases(calm: dict) -> list[dict]:
    rng = np.random.default_rng(SEED_DIR)
    S = D_SIZE
    cp = (calm["graze_edge_r"], calm["graze_edge_w"], calm["graze_inertia"], calm["graze_wall_margin"])
    R = cp[0]
    rows = []

    def add(par, raw, head, pos, tag):
        rows.append(dict(par=tuple(float(x) for x in par), raw=np.array(raw, dtype=np.float64), head=np.array(head, dtype=np.float64),
                         pos=np.array(pos, dtype=np.float64), tag=tag))

    h = np.sqrt(0.5)
    add(cp, [0.3, 0.4], [1.0, 0.0], [30.0, 30.0], "center")
    add(cp, [-0.8, 0.1], [-1.0, 0.0], [0.2, 30.0], "wall_out")
    add(cp, [-0.8, -0.5], [-h, -h], [0.1, 0.3], "corner_out")
    add(cp, [0.8, 0.5], [h, h], [S - 0.1, S - 0.3], "corner_out_hi")
    add(cp, [-1.0, 0.0], [0.0, 1.0], [R, 30.0], "edge_exact_R")                       # e = R (가장자리 밖)
    add(cp, [-1.0, 0.0], [0.0, 1.0], [float(np.nextafter(R, 0.0)), 30.0], "edge_R_minus_ulp")
    add(cp, [-1.0, 0.0], [0.0, 1.0], [0.0, 30.0], "pos_zero")
    add(cp, [1.0, 0.0], [0.0, 1.0], [S, 30.0], "pos_size")
    add(cp, [0.0, -1.0], [0.0, -1.0], [30.0, S / 2.0], "mid_axis")                       # p = S/2 (n = +1)
    add((0.0, 0.0, cp[2], 0.0), [0.2, -0.1], [-h, h], [30.0, 20.0], "inertia_only")
    add((cp[0], cp[1], 0.0, 0.0), [-0.5, 0.2], [1.0, 0.0], [0.7, 15.0], "edge_only")
    add((0.0, 0.0, 0.0, cp[3]), [-0.5, 0.2], [1.0, 0.0], [0.7, 15.0], "margin_only")
    add((0.0, 0.0, 0.5, 0.0), [-0.25, 0.0], [0.5 / 0.5 * 1.0, 0.0], [30.0, 30.0], "zero_sum")    # raw + 0.5·head = 0 → 원래 방향
    add((0.0, 0.0, 0.0, cp[3]), [-0.6, -0.8], [-0.6, -0.8], [0.5, 0.5], "margin_all")   # 벽 여유가 둘 다 지움 → 원래 방향
    add((cp[0], 0.0, cp[2], cp[3]), [-0.6, 0.2], [0.0, 1.0], [0.5, 30.0], "edge_w_zero")  # 가장자리 무게 0 = 가장자리 항 끔
    add((0.0, cp[1], cp[2], cp[3]), [-0.6, 0.2], [0.0, 1.0], [0.5, 30.0], "edge_r_zero")
    add(cp, [1e-6, 0.0], [-1.0, 0.0], [30.0, 30.0], "tiny_raw")
    add(cp, [-0.7, 0.7], [h, -h], [1.5, S - 1.5], "corner_mixed")
    hand = len(rows)
    sets = [cp, (cp[0], cp[1], 0.0, 0.0), (0.0, 0.0, cp[2], 0.0), (0.0, 0.0, 0.0, cp[3])]
    for k in range(180):
        par = sets[k % len(sets)] if k < 140 else (float(rng.uniform(0.5, 8.0)), float(rng.uniform(0.0, 5.0)), float(rng.uniform(0.0, 2.0)),
                                                    float(rng.uniform(0.0, 3.0)))
        near = rng.random(2) < 0.7
        pos = np.where(near, np.where(rng.random(2) < 0.5, rng.uniform(0.0, 6.0, 2), S - rng.uniform(0.0, 6.0, 2)), rng.uniform(0.0, S, 2))
        a, b = rng.uniform(0.0, 2.0 * np.pi, 2)
        mag = float(rng.uniform(0.01, 2.5))
        add(par, [mag * math.cos(a), mag * math.sin(a)], [math.cos(b), math.sin(b)], pos, "rand")
    for r in rows:
        p = p_of(*r["par"])
        base = normalize(r["raw"][None, :])
        r["out"] = rep.graze_calm_dir(r["raw"][None, :], base, r["pos"][None, :], r["head"][None, :], S, p)[0]
        r["base"] = base[0]
    return rows, hand


# --------------------------------------------------------------------- #
# 3 제어 사례 (repertoire.control GRAZE — 계수 켬)
# --------------------------------------------------------------------- #


def control_cases(w: World) -> list[dict]:
    rng = np.random.default_rng(SEED_CTL)
    p, cfg, sp = w._rp, w.cfg, w._sp
    S = float(w.size)
    rows = []
    for k in range(40):
        u = lambda: (lambda a: np.array([math.cos(a), math.sin(a)]))(rng.uniform(0.0, 2.0 * np.pi))   # noqa: E731
        g, c = u(), u()
        sep = u() * rng.uniform(0.0, 1.0)
        if k % 10 == 3:
            g, c, sep = np.zeros(2), np.zeros(2), np.zeros(2)                     # 방향 없음 → 정지
        if k % 10 == 5:
            c = -0.83 / 0.71 * g                                                  # 먹이·무리가 지움 (분리만)
        pos = np.where(rng.random(2) < 0.6, rng.uniform(0.0, 4.0, 2), rng.uniform(0.0, S, 2))
        head = u()
        food_ok = bool(k % 7 == 0)
        rs = rep.RepState(1, p, np.full(1, 0.5), 0.0, SEED_CTL)
        inp = dict(food_grad=g[None, :], to_centroid=c[None, :], separation=sep[None, :], away_from_pred=np.zeros((1, 2)), to_target=np.zeros((1, 2)),
                   pred_count=np.zeros(1, dtype=np.int64), food_ok=np.array([food_ok]), in_cover=np.array([False]), dark=0.0,
                   pos=pos[None, :], head=head[None, :], size=S)
        out = rep.control(rs, p, inp, cfg, sp)
        rows.append(dict(g=g, c=c, sep=sep, pos=pos, head=head, food_ok=food_ok, vel=out["vel"][0].copy(), gait=int(out["gait"][0])))
    return rows


# --------------------------------------------------------------------- #
# 4 덮기 장면 (H — `_wf_update`)
# --------------------------------------------------------------------- #


def scene_world() -> World:
    w = World(calm_cfg(N_SCENE), seeds=[SEED_SCENE])
    if w._wf is None or not w._wf["rest_keep"] or w.M != 4 or w._ws is None or w._ps is None or w._zv is None or w._zh is None:
        raise SystemExit("장면 세계는 거리 두기·늑대 넷·포만·밤잠·위협 시야·발소리를 켠 세계여야 한다")
    return w


def set_dark(w: World, d: float) -> None:
    """어둠 d 와 그 어둠의 탐지 반경 (world.py `_daynight_update` 의 식 — 날씨 배수는 지금 값). 늑대 잠은 장면이 따로 정한다."""
    w.dark = float(d)
    w._vis = 1.0 - w._dn["detect_night"] * w.dark
    if w._wx is None:
        w._see_pred = w.cfg.see_r * w._vis
    else:
        vis_w = w._vis * w._wx_sight
        w._see_pred = w.cfg.see_r * vis_w
        if w._wx["obs_visibility"]:
            w._vis = vis_w


SC_COVERS = 2
SC_DISCS = 3


def scene_run(w: World, sc: dict) -> dict:
    N, M = w.N, w.M
    w.alive = np.ones(N, dtype=bool)
    w.death_cause[:] = 0
    w.pos[:] = sc["pos"]
    w.head[:] = sc["head"]
    w._rep_see[:] = sc["see"]
    w._rep_see_last[:] = sc["see"]
    w.pred_pos[:] = sc["ppos"]
    w.pred_vel[:] = sc["pvel"]
    w.pred_running[:] = sc["run"]
    w.pred_cd[:] = sc["cd"]
    w.pred_sat[:] = sc["sat"]
    w.pred_asleep[:] = sc["asleep"]
    w.pred_target = np.asarray(sc["target"], dtype=np.int64).copy()
    w.cov_c = np.asarray([c[:2] for c in sc["covers"]], dtype=np.float64).reshape(-1, 2)
    w.cov_r = np.asarray([c[2] for c in sc["covers"]], dtype=np.float64)
    w.obstacles = np.asarray(sc["discs"], dtype=np.float64).reshape(-1, 3)
    set_dark(w, sc["dark"])
    w._rs.lock_left[:] = sc["lock"]
    w._g = w._geometry()
    dead = np.asarray(sc["dead"], dtype=bool)
    w.alive = ~dead
    w.wf_mode[:] = sc["prev"]
    w.wf_dir = np.asarray(sc["pdir"], dtype=np.float64).copy()     # 지난 덮기 방향 (이어지는 거리 두기의 관성 — 10-27 적대적 검토)
    w._wf_rest_exec = None
    w._wf_update(dead.copy())
    return dict(mode=w.wf_mode.copy(), dir=w.wf_dir.copy(), lock=w._rs.lock_left.copy())


def scenes(w: World):
    N, M = w.N, w.M
    V, M_ = w._wf_view(), w._wf["rest_keep_margin"]
    out = []

    def base():
        pos = np.tile([50.0, 50.0], (N, 1)) + np.arange(N)[:, None] * np.array([0.0, -0.3])
        pos[:4] = [[30.0, 10.0], [30.0, 22.0], [30.0, 30.0], [30.0, 40.0]]
        return dict(pos=pos, head=np.tile([1.0, 0.0], (N, 1)), see=np.full(N, 0.6), ppos=np.tile([-500.0, -500.0], (M, 1)), pvel=np.zeros((M, 2)),
                    run=np.zeros(M, dtype=bool), cd=np.zeros(M, dtype=np.int64), sat=np.zeros(M, dtype=np.int64), asleep=np.zeros(M, dtype=bool),
                    target=np.full(M, -1), covers=[(0.0, 0.0, 0.5)], discs=[], prev=np.zeros(N, dtype=np.int8), lock=np.full(N, 5),
                    dead=np.zeros(N, dtype=bool), dark=0.0, pdir=np.zeros((N, 2)))

    def wolf(sc, m, dx, dy=0.0, cd=0, sat=0, asleep=False, vel=(0.0, 0.0), run=False, deer=2, target=-1):
        sc["ppos"][m] = sc["pos"][deer] + np.array([dx, dy])
        sc["cd"][m], sc["sat"][m], sc["asleep"][m] = cd, sat, asleep
        sc["pvel"][m] = vel
        sc["run"][m] = run
        sc["target"][m] = target
        return sc

    tags = []

    def put(sc, tag):
        out.append(sc)
        tags.append(tag)

    put(wolf(base(), 0, 10.0, sat=100), "rest_start_sated")                              # 앞 10, 배부름 → 거리 두기
    put(wolf(base(), 0, 8.0, cd=10), "rest_start_eating")                                # 먹는 늑대(가까움, 경계 거리 안) → 거리 두기 (rest_alert 대신)
    put(wolf(base(), 0, -10.0, sat=100), "rear_blind")                                  # 바로 뒤 10 (사각, 서 있어 소리 없음) → 없음
    sc = wolf(base(), 0, -(V + M_ - 0.5), sat=100)
    sc["prev"][2] = WF_REST
    put(sc, "keep_memory_rear")                                                          # 지난 거리 두기, 뒤 V + 여유 안 → 이어짐
    def edge0(dx, prev):
        # 경계 장면: 사슴 2 를 x = 0 에 두어 늑대 자리 0 + dx 와 거리 sqrt(dx²) 가 dx 와 비트 단위로 같게 한다
        sc = base()
        sc["pos"][2] = [0.0, 30.0]
        sc["ppos"][0] = [dx, 30.0]
        sc["sat"][0] = 100
        sc["prev"][2] = prev
        return sc

    put(edge0(V + M_, WF_REST), "keep_exact_out")                                       # V + 여유 정확히 → 이어짐
    put(edge0(float(np.nextafter(V + M_, np.inf)), WF_REST), "keep_out_plus_ulp")       # 1 ulp 밖 → 끝
    put(edge0(V, WF_NONE), "start_exact_V")                                              # 들어갈 때 V 정확히 → 시작
    put(edge0(float(np.nextafter(V, np.inf)), WF_NONE), "start_V_plus_ulp")             # V 1 ulp 밖 → 시작 아님
    sc = wolf(base(), 0, 10.0, sat=100)
    sc["discs"] = [(35.0, 30.0, 0.8)]
    put(sc, "occluded")                                                                  # 줄기가 눈길을 가림 → 없음
    sc = wolf(base(), 0, 10.0, sat=100)
    sc["discs"] = [(35.0, 30.0, 0.8)]
    sc["prev"][2] = WF_REST
    put(sc, "occluded_keep_ends")                                                        # 이어짐도 가림이면 끝
    sc = wolf(base(), 0, 10.0, sat=100)
    sc["covers"] = [(30.0, 30.0, 3.0)]
    put(sc, "in_cover")                                                                  # 은신처 안 → 없음
    sc = wolf(base(), 0, 10.0, sat=100)
    wolf(sc, 1, 7.0, 3.0)
    put(sc, "hunting_alert_wins")                                                        # 알아챈 사냥 늑대 경계 거리 안·도주 거리 밖 → 경계 (거리 두기보다 앞)
    sc = wolf(base(), 0, 10.0, sat=100)
    wolf(sc, 1, 5.0, 2.0)
    put(sc, "panic_wins")                                                                # 사냥 늑대 도주 거리 안 → 도주
    sc = wolf(base(), 0, 9.0, 3.0, sat=100)
    wolf(sc, 1, 6.0, -8.0, cd=10)
    put(sc, "two_resting")                                                               # 쉬는 늑대 둘 — 거리 역수 가중 반대
    put(wolf(base(), 0, 10.0, asleep=True), "asleep_ignored")                           # 자는 늑대 → 없음
    put(wolf(base(), 0, -0.8, sat=100, vel=(0.12, 0.0)), "heard_rear")                  # 뒤 0.8 의 어슬렁 발소리(비 속 1 단위) → 알아챔 → 거리 두기
    sc = wolf(base(), 0, 10.0, sat=100)
    sc["dead"][2] = True
    sc["prev"][2] = WF_REST
    put(sc, "dead")                                                                      # 죽음 → 없음
    sc = wolf(base(), 0, 8.0, 2.0, sat=100)
    sc["pos"][2] = [0.5, 30.0]
    sc["ppos"][0] = [8.5, 32.0]
    put(sc, "wall")                                                                      # 벽 앞 — 가장자리 굽히기·벽 여유
    sc = wolf(base(), 0, 6.0, 6.0, sat=100)
    sc["pos"][2] = [1.0, 1.0]
    sc["ppos"][0] = [7.0, 7.0]
    put(sc, "corner")
    sc = wolf(base(), 0, 12.0, sat=100)
    sc["dark"] = 1.0
    put(sc, "night_far")                                                                 # 밤: 고개 든 시야가 줄어 12 를 못 봄 → 없음
    sc = wolf(base(), 0, 8.0, sat=100)
    sc["dark"] = 1.0
    put(sc, "night_near")
    sc = wolf(base(), 0, 10.0, sat=100)
    sc["head"][2] = [-1.0, 0.0]
    sc["see"][2] = 1.0
    put(sc, "facing_away_seen_by_pvis_no")                                               # 늑대가 등 뒤 (사각) → 없음
    sc = wolf(base(), 0, 10.0, sat=100)
    sc["prev"][2] = WF_ALERT
    sc["pdir"][2] = [0.0, 1.0]
    put(sc, "from_alert")                                                                # 지난 경계 → 거리 두기 (경계 방향은 관성으로 잇지 않는다)
    sc = wolf(base(), 0, 10.0, sat=100)
    sc["prev"][2] = WF_PANIC
    sc["lock"][2] = 4
    put(sc, "from_panic_release")                                                        # 지난 도주(깨어 있는 늑대가 안전 거리 안 — 붙잡힘) → 도주
    sc = wolf(base(), 0, 21.0, sat=100)
    sc["prev"][2] = WF_PANIC
    sc["lock"][2] = 4
    put(sc, "panic_released_far")                                                        # 지난 도주, 21 → 풀림 (잠금 0)
    # 10-27 적대적 검토 — 이어지는 거리 두기의 방향 관성 (WF_REST_INERTIA)
    sc = wolf(base(), 0, 10.0, sat=100)
    sc["prev"][2] = WF_REST
    sc["pdir"][2] = [0.0, 1.0]
    put(sc, "keep_inertia")                                                              # 반대 (−1, 0) + 지난 (0, 1) → n(−1, 1)
    sc = wolf(base(), 0, 10.0, sat=100)
    sc["prev"][2] = WF_REST
    sc["pdir"][2] = [1.0, 0.0]
    put(sc, "keep_inertia_opposite")                                                     # 지난 방향이 정반대 → 합 0 → 반대 방향 그대로
    sc = wolf(base(), 0, 10.0, sat=100)
    sc["pdir"][2] = [0.0, 1.0]
    put(sc, "start_no_inertia")                                                          # 시작(지난 덮기 없음)은 관성 없음
    sc = base()
    sc["pos"][2] = [30.0, 1.5]
    sc["ppos"][0] = [30.0, 11.5]
    sc["sat"][0] = 100
    sc["head"][2] = [0.0, 1.0]
    sc["prev"][2] = WF_REST
    sc["pdir"][2] = [-1.0, 0.0]
    put(sc, "keep_inertia_wall")                                                         # 벽 앞 정면 늑대 — 굽히는 쪽이 지난 쪽(−x)을 따른다
    sc = base()
    sc["pos"][2] = [30.0, 1.5]
    sc["ppos"][0] = [30.0, 11.5]
    sc["sat"][0] = 100
    sc["head"][2] = [0.0, 1.0]
    sc["prev"][2] = WF_REST
    sc["pdir"][2] = [1.0, 0.0]
    put(sc, "keep_inertia_wall_other")                                                   # 같은 자리, 지난 쪽 +x → +x 로
    hand = len(out)
    rng = np.random.default_rng(SEED_SCENE)
    for _ in range(40):
        ppos = rng.uniform(3.0, 57.0, (M, 2))
        pos = np.clip(ppos[0] + rng.uniform(-20.0, 20.0, (N, 2)), 0.0, 60.0)
        a = rng.uniform(0.0, 2.0 * np.pi, N)
        sp = rng.uniform(0.0, 0.5, M)
        b = rng.uniform(0.0, 2.0 * np.pi, M)
        cov = [(float(x), float(y), float(r)) for x, y, r in zip(rng.uniform(5, 55, 2), rng.uniform(5, 55, 2), rng.uniform(2, 6, 2))]
        nd = int(rng.integers(0, SC_DISCS + 1))
        discs = [(float(x), float(y), float(r)) for x, y, r in zip(rng.uniform(5, 55, nd), rng.uniform(5, 55, nd), rng.uniform(0.3, 1.5, nd))]
        out.append(dict(pos=pos, head=np.stack([np.cos(a), np.sin(a)], 1), see=rng.choice([1.0, 0.6, 0.3], N), ppos=ppos,
                        pvel=np.stack([sp * np.cos(b), sp * np.sin(b)], 1), run=rng.random(M) < 0.3,
                        cd=rng.choice([0, 0, 10], M), sat=rng.choice([0, 100, 100], M), asleep=rng.random(M) < 0.15,
                        target=np.where(rng.random(M) < 0.2, rng.integers(0, N, M), -1), covers=cov, discs=discs,
                        prev=rng.choice([0, 1, 2, 4, 4, 0], N).astype(np.int8), lock=rng.choice([-1, 0, 5], N),
                        dead=rng.random(N) < 0.05, dark=float(rng.choice([0.0, 0.0, 0.5, 1.0]))))
        tags.append("rand")
    rng_p = np.random.default_rng((SEED_SCENE, 7))                                       # 지난 덮기 방향 (따로 — 위 장면 뽑기를 바꾸지 않는다)
    for sc in out[hand:]:
        b = rng_p.uniform(0.0, 2.0 * np.pi, N)
        on = np.isin(sc["prev"], (WF_ALERT, WF_PANIC, WF_REST)) & (rng_p.random(N) > 0.15)
        sc["pdir"] = np.where(on[:, None], np.stack([np.cos(b), np.sin(b)], 1), 0.0)
    res = [scene_run(w, sc) for sc in out]
    return out, res, tags, hand


# --------------------------------------------------------------------- #
# 5 B 장면 (`_wf_rest_control`·`_wf_rest_band`)
# --------------------------------------------------------------------- #


def b_scenes(w: World):
    N, M = w.N, w.M
    rng = np.random.default_rng(SEED_B)
    sp, cfg = w._sp, w.cfg
    rows = []
    for k in range(48):
        ppos = rng.uniform(5.0, 55.0, (M, 2))
        pos = np.clip(ppos[k % M] + rng.uniform(-24.0, 24.0, (N, 2)), 0.0, 60.0)
        a = rng.uniform(0.0, 2.0 * np.pi, N)
        b = rng.uniform(0.0, 2.0 * np.pi, N)
        c = rng.uniform(0.0, 2.0 * np.pi, N)
        mode = rng.choice([WF_NONE, WF_NONE, WF_ALERT, WF_REST, WF_REST], N).astype(np.int8)
        wdir = np.where((mode == WF_REST)[:, None] | (mode == WF_ALERT)[:, None], np.stack([np.cos(b), np.sin(b)], 1), 0.0)
        wdir[rng.random(N) < 0.08] = 0.0                                                  # 방향 0 인 덮기 (거리 두기 제어를 타지 않음)
        beh = rng.choice([rep.GRAZE, rep.GRAZE, rep.GRAZE, rep.FLEE, rep.SLEEP], N).astype(np.int8)
        gait = rng.choice([GAIT_WALK, GAIT_WALK, GAIT_STOP, GAIT_RUN], N).astype(np.int8)
        vel = np.stack([np.cos(c), np.sin(c)], 1) * (cfg.herb_speed * sp["speed"][gait])[:, None]
        if k % 6 == 1:
            # 늑대 쪽으로 곧장 걷는 사슴 (다 지워져 멈춤)
            u = normalize(ppos[0][None, :] - pos)
            vel = u * (cfg.herb_speed * sp["speed"][GAIT_WALK])
            gait[:] = GAIT_WALK
        sep = np.stack([np.cos(a), np.sin(a)], 1) * rng.uniform(0.0, 1.0, N)[:, None]
        rk = np.flatnonzero((mode == WF_REST) & (wdir != 0.0).any(1))
        if k % 6 == 2 and len(rk):
            # 10-27 적대적 검토: 분리가 덮기 방향 반대(앞을 막은 동료) — 늑대 쪽 성분을 지워 D 그대로 가야 한다
            sep[rk] = -(0.5 + 0.5 * np.abs(np.sin(a[rk])))[:, None] * wdir[rk]
        if k % 6 == 4 and len(rk):
            # 벽 앞(x 0.3)에서 벽을 따라 물러나는데 분리가 벽 쪽 — 벽 여유가 벽 쪽 성분을 지운다
            j = rk[:3]
            pos[j] = np.stack([np.full(len(j), 0.3), 10.0 + 15.0 * np.arange(len(j))], 1)
            wdir[j] = np.stack([np.zeros(len(j)), np.where(np.arange(len(j)) % 2 == 0, 1.0, -1.0)], 1)
            sep[j] = [-0.8, 0.1]
        nd = int(rng.integers(0, SC_DISCS + 1))
        discs = [(float(x), float(y), float(r)) for x, y, r in zip(rng.uniform(5, 55, nd), rng.uniform(5, 55, nd), rng.uniform(0.3, 1.5, nd))]
        sc = dict(pos=pos, head=np.stack([np.cos(a), np.sin(a)], 1), ppos=ppos, cd=rng.choice([0, 10], M), sat=rng.choice([0, 100, 100], M),
                  asleep=rng.random(M) < 0.15, discs=discs, dark=float(rng.choice([0.0, 0.5, 1.0])), mode=mode, wdir=wdir, beh=beh,
                  vel=vel, gait=gait, eat=np.where(beh == rep.GRAZE, sp["eat"][gait], 0.0), drain=sp["drain_mult"][gait].copy(),
                  see=np.where(beh == rep.GRAZE, 0.6, 1.0), sep=sep, alive=rng.random(N) > 0.05)
        w.pos[:] = sc["pos"]
        w.head[:] = sc["head"]
        w.pred_pos[:] = sc["ppos"]
        w.pred_cd[:] = sc["cd"]
        w.pred_sat[:] = sc["sat"]
        w.pred_asleep[:] = sc["asleep"]
        w.obstacles = np.asarray(sc["discs"], dtype=np.float64).reshape(-1, 3)
        set_dark(w, sc["dark"])
        w.wf_mode[:] = sc["mode"]
        w.wf_dir = sc["wdir"].copy()
        w._rs.behavior = sc["beh"].copy()
        w.alive = sc["alive"].copy()
        o = dict(vel=sc["vel"].copy(), gait=sc["gait"].copy(), eat=sc["eat"].astype(np.float64).copy(), drain=sc["drain"].astype(np.float64).copy(),
                 see=sc["see"].astype(np.float64).copy())
        w._wf_rest_control(o, dict(separation=sc["sep"]))
        w._wf_rest_band(o)
        sc["out"] = o
        rows.append(sc)
    w.alive = np.ones(N, dtype=bool)
    return rows


# --------------------------------------------------------------------- #
# 6 기준 루프
# --------------------------------------------------------------------- #


def step_hash(w: World, alive0: np.ndarray, req: np.ndarray) -> int:
    N = w.N
    cause = np.asarray(w.death_cause).astype(np.int64)
    keep = np.asarray(w.wf_mode).astype(np.int64)
    reserve = w.reserve if w._wr is not None else np.zeros(N)
    obs = np.asarray(w._obs, dtype=np.float32)
    if obs.shape != (N, 18):
        raise SystemExit(f"관측 칸 수 {obs.shape} — 관측 18 세계여야 한다")
    live = cause == 0
    req_ok = live & (keep != WF_PANIC) & (keep != WF_SHELTER)
    dir_ok = live & ((keep == WF_ALERT) | (keep == WF_PANIC) | (keep == WF_REST))
    b = bytearray()
    b += np.asarray([w.dark, w.pred_ema], dtype="<f8").tobytes()
    for a in (w.pos[:, 0], w.pos[:, 1], w.head[:, 0], w.head[:, 1], w.energy, reserve):
        b += np.ascontiguousarray(a, dtype="<f8").tobytes()
    b += cause.astype("<i4").tobytes() + keep.astype("<i4").tobytes()
    b += np.asarray(w._rs.behavior)[alive0].astype("<i4").tobytes()
    b += np.ascontiguousarray(obs[alive0], dtype="<f4").tobytes()
    b += np.asarray(req).reshape(-1)[req_ok].astype("<i4").tobytes()
    b += np.ascontiguousarray(np.asarray(w.wf_dir, dtype=np.float64)[dir_ok], dtype="<f8").tobytes()
    for a in (w.pred_pos[:, 0], w.pred_pos[:, 1], w.pred_head[:, 0], w.pred_head[:, 1]):
        b += np.ascontiguousarray(a, dtype="<f8").tobytes()
    for a in (w.pred_cd, getattr(w, "pred_sat", np.zeros(w.M))):
        b += np.asarray(a).astype("<i4").tobytes()
    return int.from_bytes(hashlib.sha256(bytes(b)).digest()[:8], "little")


def check_row(w: World) -> list[int]:
    cause = np.asarray(w.death_cause)
    rest_on = w._wf["rest_keep"]
    return ([int(np.count_nonzero(cause == 1)), int(np.count_nonzero(cause == 2)), int(np.count_nonzero(cause == 0))]
            + [int(v) for v in w._wf_mode_n[:5]]
            + ([int(w._wf_band_n), int(w._wf_band_stop_n)] if rest_on else [0, 0]))


_MODEL: dict = {}


def _model():
    """내장 R1b 모델 (한 번만 읽는다)."""
    if "m" not in _MODEL:
        import export_weights_v3 as ew

        _MODEL["m"] = ew.load_model(MODEL)
    return _MODEL["m"]


def loop_world(seed: int, region: str, on: bool) -> dict:
    import ceval
    import export_weights_v3 as ew
    from env_v2.rollout import RepLearned

    w = World(calm_cfg(N_LOOP, region, on), seeds=[seed])
    if w.alive is None or w._wf is None or w._zs is None or w._rp["calm"] != on or w._wf["rest_keep"] != on:
        raise SystemExit("기준 루프 세계는 부활 없음·도주 반사·은신처 안전이고 두 고침이 on 이어야 한다")
    w.track_flight = True
    job = ceval.native_job(dict(seed=seed, region="golden", steps=LOOP_STEPS), 0, world=w)
    g = np.random.Generator(np.random.PCG64())
    g.bit_generator.state = w.rng.bit_generator.state
    raw = [int(x) for x in g.bit_generator.random_raw(LOOP_STEPS * w.M)]
    model = _model()
    pol = RepLearned(model)
    pol.bind_world(w)
    Wt = ew.extract(model)
    gaps = dict(all=math.inf, mismatch=0)

    def decide():
        obs = w.observe()
        a = pol(obs)[:, 0]
        m = pol.last_mask
        live = np.asarray(w.death_cause) == 0
        lg = ew.forward_np(obs, Wt, np.float32)
        gaps["mismatch"] += int(np.count_nonzero((ew.masked_argmax(lg, m) != a.astype(np.int64)) & live))
        gp = ew.top_gap(lg, m)
        multi = live & (m.sum(1) >= 2)
        if multi.any():
            gaps["all"] = min(gaps["all"], float(gp[multi].min()))
        return a

    a = decide()
    hashes = [step_hash(w, np.ones(w.N, dtype=bool), a)]
    checks = []
    for t in range(1, LOOP_STEPS + 1):
        alive0 = np.asarray(w.death_cause) == 0
        w.step(a[:, None])
        a = decide()
        hashes.append(step_hash(w, alive0, a))
        if t % LOOP_EVERY == 0:
            checks.append(check_row(w))
    if w.rng.bit_generator.state["state"] != g.bit_generator.state["state"]:
        raise SystemExit("기준 루프: 세계 난수가 스텝마다 늑대 M 개 말고도 뽑혔다 — 날 수열로 옮길 수 없다")
    ws = w.wild_stats()
    return dict(w=w, job=job, raw=raw, hashes=hashes, checks=checks, gaps=gaps, ws=ws,
                caught=int(np.count_nonzero(np.asarray(w.death_cause) == 1)))


def pick_loop(region: str) -> tuple[int, dict, dict, int]:
    """두 고침 켬 판에 거리 두기·띠·잡힘이 있고, 켬·끔 모두 근접 동점(< 1e-4)·두뇌 argmax 차가 없고, 켬·끔 궤적이 갈리는 첫 시드."""
    for seed in LOOP_SEEDS:
        try:
            on = loop_world(seed, region, True)
        except ValueError as e:
            print(f"  {region} 시드 {seed}: {e}")
            continue
        ws = on["ws"]
        print(f"  {region} 시드 {seed}: 거리 두기 시작 {ws['rest_starts']} · 띠 {ws['band_turn_steps']} · 잡힘 {on['caught']} · 최소 로짓 차 "
              f"{on['gaps']['all']:.5f} · argmax 차 {on['gaps']['mismatch']}")
        if on["gaps"]["all"] < NEAR_TIE or on["gaps"]["mismatch"] or ws["rest_starts"] == 0 or ws["band_turn_steps"] == 0 or on["caught"] == 0:
            continue
        off = loop_world(seed, region, False)
        if off["gaps"]["all"] < NEAR_TIE or off["gaps"]["mismatch"]:
            print(f"  {region} 시드 {seed}: 끔 판 근접 동점")
            continue
        jo, jf = copy.deepcopy(on["job"]), copy.deepcopy(off["job"])
        for j in (jo, jf):
            j["world"].pop("graze_calm", None)
            for k in ("rest_keep", "rest_keep_margin", "rest_keep_band", "rest_keep_asleep"):
                j["world"]["wild_flight"].pop(k, None)
        if jo != jf or on["raw"] != off["raw"]:
            raise SystemExit("두 고침 켬·끔의 시작 상태가 다르다 (두 고침만 달라야 한다)")
        div = next((k for k, (x, y) in enumerate(zip(on["hashes"], off["hashes"])) if x != y), None)
        if div is None:
            raise SystemExit(f"{region} 시드 {seed}: 켬·끔 궤적이 같다 — 고침이 걸리지 않았다")
        return seed, on, off, div
    raise SystemExit(f"{region}: 시드 {LOOP_SEEDS} 가운데 기준 루프 조건을 만족하는 시드가 없다")


# --------------------------------------------------------------------- #
# 헤더
# --------------------------------------------------------------------- #


def build_header() -> str:
    fg.check_seeds(SEED_DIR, SEED_CTL, SEED_SCENE, SEED_B, *LOOP_SEEDS)
    if (WF_NONE, WF_ALERT, WF_PANIC, WF_SHELTER, WF_REST) != (0, 1, 2, 3, 4):
        raise SystemExit("덮기 번호가 바뀌었다 — C++ kKeep* 와 맞춘다")
    if (GAIT_STOP, GAIT_WALK, GAIT_RUN) != (0, 1, 2):
        raise SystemExit("보행 번호가 바뀌었다")
    opt_r, opt_w = dict(OPTIONAL_KEYS["repertoire"]), dict(OPTIONAL_KEYS["wild_flight"])
    if any(opt_r[k] != 0.0 for k in rep.GRAZE_CALM_KEYS) or (opt_w["rest_keep"], opt_w["rest_keep_margin"], opt_w["rest_keep_band"],
                                                              opt_w["rest_keep_asleep"]) != (False, 2.0, 0.0, False):
        raise SystemExit("features.OPTIONAL_KEYS 의 끔 값이 바뀌었다 — C++ 기본값과 맞춘다")
    sw = scene_world()
    calm = {k: float(sw._rp[k]) for k in rep.GRAZE_CALM_KEYS}
    wf = sw._wf
    drows, dhand = dir_cases(calm)
    crows = control_cases(sw)
    scs, sres, stags, shand = scenes(sw)
    brows = b_scenes(sw)
    loops = []
    print("기준 루프 시드 고르기:")
    for region in LOOP_REGIONS:
        loops.append((region,) + pick_loop(region))

    N, M = sw.N, sw.M
    L = []
    L.append("// 자동 생성 — herbivore_rl/export_golden_v3_calm.py (손으로 고치지 않는다). 세계 configs/v3_wild3_calm_mirror.yaml, 시드 "
             f"{SEED_DIR}~{max(LOOP_SEEDS)}.")
    L.append("// v3 10-27 고침 골든 — 먹기 걷기 고침(repertoire.py `graze_calm_dir`)·거리 두기(쉬는 늑대, world.py `_wf_update`·`_wf_rest_control`·`_wf_rest_band`).")
    L.append("// 검사는 Tests/CalmGoldenCheckV3.h (AdaptiveEcosystem.Policy.V3.Calm.*, g++ herbivore_rl/tests/cpp/calm_v3_main.cpp). 묶음 설명은 생성기 머리 주석.")
    L.append("#pragma once")
    L.append("")
    L.append("#include <cstdint>")
    L.append("")
    L.append('#include "EcoWorldV3.h"')
    L.append("")
    L.append("namespace EcoWorldV3::GoldenCalm")
    L.append("{")
    L.append("\t// ---- 1 정의: 설정 값 (configs/v3_wild3_calm_mirror.yaml — 통합 기본 eco.IntegratedV3.GrazeCalm·RestKeep 1 이 쓰는 값) ----")
    for k, nm in (("graze_edge_r", "kGrazeEdgeR"), ("graze_edge_w", "kGrazeEdgeW"), ("graze_inertia", "kGrazeInertia"), ("graze_wall_margin", "kGrazeWallMargin")):
        L.append(f"\tinline constexpr double {nm} = {d_lit(calm[k])};")
    L.append(f"\tinline constexpr bool kRestKeep = {'true' if wf['rest_keep'] else 'false'};")
    L.append(f"\tinline constexpr double kRestKeepMargin = {d_lit(wf['rest_keep_margin'])};")
    L.append(f"\tinline constexpr double kRestKeepBand = {d_lit(wf['rest_keep_band'])};")
    L.append(f"\tinline constexpr bool kRestKeepAsleep = {'true' if wf['rest_keep_asleep'] else 'false'};")
    L.append(f"\tinline constexpr std::int32_t kKeepRestCode = {WF_REST};   // world.py WF_REST = C++ kKeepRest")
    L.append("")
    L.append(f"\t// ---- 2 방향 사례 (무대 {D_SIZE:g}): 계수 (edge_r, edge_w, inertia, wall_margin)·raw (x, y)·heading (x, y)·자리 (x, y) → 원래 방향 (x, y)·나온 방향 (x, y). "
             f"앞 kDirHand 개는 손 사례 ----")
    L.append(f"\tinline constexpr double kDirSize = {d_lit(D_SIZE)};")
    L.append(f"\tinline constexpr std::int32_t kDirCases = {len(drows)};")
    L.append(f"\tinline constexpr std::int32_t kDirHand = {dhand};")
    L.append(c_array("double", "kDirIn", [v for r in drows for v in (*r["par"], *r["raw"], *r["head"], *r["pos"])], 10, d_lit))
    L.append(c_array("double", "kDirOut", [v for r in drows for v in (*r["base"], *r["out"])], 4, d_lit))
    L.append("")
    L.append(f"\t// ---- 3 제어 사례 (R3::Control GRAZE — 계수 위 정의, 무대 kCtlSize): 먹이 기울기·무리·분리·자리·heading (x, y 다섯)·먹이 충분 → 속도 (x, y)·보행 ----")
    L.append(f"\tinline constexpr double kCtlSize = {d_lit(sw.size)};")
    L.append(f"\tinline constexpr std::int32_t kCtlCases = {len(crows)};")
    L.append(c_array("double", "kCtlIn", [v for r in crows for v in (*r["g"], *r["c"], *r["sep"], *r["pos"], *r["head"])], 10, d_lit))
    L.append(c_array("std::uint8_t", "kCtlFoodOk", [int(r["food_ok"]) for r in crows], 40, i_lit))
    L.append(c_array("double", "kCtlVel", [v for r in crows for v in r["vel"]], 4, d_lit))
    L.append(c_array("std::int32_t", "kCtlGait", [r["gait"] for r in crows], 40, i_lit))
    L.append("")
    L.append(f"\t// ---- 4 덮기 장면 (UpdateWildFlight — 장면 세계 = 기준 루프 숲 설정 + 사슴 {N}, 늑대 {M}): 장면마다 어둠·은신처 {SC_COVERS} (x, y, r — 없으면 r < 0)·")
    L.append(f"\t//      원판 {SC_DISCS} (x, y, r — 없으면 r < 0), 사슴 (x, y, hx, hy, 시야 배수, 지난 덮기, 잠금, 죽음, 지난 덮기 방향 x, y)·늑대 (x, y, vx, vy, 전력 걸음,")
    L.append("\t//      쿨다운, 배부름, 잠, 표적)")
    L.append("\t//      → 사슴 (다음 덮기, 방향 x, y, 잠금). 앞 kSceneHand 개는 손 장면 (kSceneTags)")
    L.append(f"\tinline constexpr std::int32_t kScenes = {len(scs)};")
    L.append(f"\tinline constexpr std::int32_t kSceneHand = {shand};")
    L.append(f"\tinline constexpr std::int32_t kSceneN = {N};")
    L.append(f"\tinline constexpr std::int32_t kSceneM = {M};")
    L.append(f"\tinline constexpr double kSceneWolfView = {d_lit(sw._wf_view())};   // V = pred_view_r × 날씨 시야 (숲 비)")
    L.append("\tinline constexpr const char* kSceneTags[" + str(shand) + "] = {" + ", ".join(f'"{t}"' for t in stags[:shand]) + "};")
    L.append(c_array("double", "kSceneDark", [sc["dark"] for sc in scs], 8, d_lit))
    L.append(c_array("double", "kSceneCover", [v for sc in scs for k in range(SC_COVERS) for v in
                                                (sc["covers"][k] if k < len(sc["covers"]) else (0.0, 0.0, -1.0))], 6, d_lit))
    if any(len(sc["covers"]) > SC_COVERS or len(sc["discs"]) > SC_DISCS for sc in scs):
        raise SystemExit("장면 은신처·원판 수가 칸보다 많다")
    L.append(c_array("double", "kSceneDisc", [v for sc in scs for k in range(SC_DISCS) for v in
                                               (sc["discs"][k] if k < len(sc["discs"]) else (0.0, 0.0, -1.0))], 6, d_lit))
    L.append(c_array("double", "kSceneDeerIn", [v for sc in scs for i in range(N) for v in
                                                 (sc["pos"][i, 0], sc["pos"][i, 1], sc["head"][i, 0], sc["head"][i, 1], sc["see"][i], float(sc["prev"][i]),
                                                  float(sc["lock"][i]), float(bool(sc["dead"][i])), sc["pdir"][i, 0], sc["pdir"][i, 1])], 10, d_lit))
    L.append(c_array("double", "kSceneWolf", [v for sc in scs for m in range(M) for v in
                                               (sc["ppos"][m, 0], sc["ppos"][m, 1], sc["pvel"][m, 0], sc["pvel"][m, 1], float(bool(sc["run"][m])),
                                                float(sc["cd"][m]), float(sc["sat"][m]), float(bool(sc["asleep"][m])), float(sc["target"][m]))], 9, d_lit))
    L.append(c_array("double", "kSceneDeerOut", [v for r in sres for i in range(N) for v in
                                                  (float(r["mode"][i]), r["dir"][i, 0], r["dir"][i, 1], float(r["lock"][i]))], 4, d_lit))
    modes = np.concatenate([r["mode"] for r in sres])
    L.append("")
    L.append(f"\t// ---- 5 B 장면 (FlightRestControl → FlightRestBand): 장면마다 어둠·원판 {SC_DISCS}·늑대 (x, y, 쿨다운, 배부름, 잠), 사슴 (x, y, hx, hy, 덮기, 덮기 방향 x, y,")
    L.append("\t//      행동, 속도 x, y, 보행, 섭식, 대사, 시야 배수, 분리 x, y, 산) → 사슴 (속도 x, y, 보행, 섭식, 대사, 시야 배수) ----")
    L.append(f"\tinline constexpr std::int32_t kBScenes = {len(brows)};")
    L.append(c_array("double", "kBDark", [sc["dark"] for sc in brows], 8, d_lit))
    L.append(c_array("double", "kBDisc", [v for sc in brows for k in range(SC_DISCS) for v in
                                           (sc["discs"][k] if k < len(sc["discs"]) else (0.0, 0.0, -1.0))], 6, d_lit))
    L.append(c_array("double", "kBWolf", [v for sc in brows for m in range(M) for v in
                                           (sc["ppos"][m, 0], sc["ppos"][m, 1], float(sc["cd"][m]), float(sc["sat"][m]), float(bool(sc["asleep"][m])))], 5, d_lit))
    L.append(c_array("double", "kBDeerIn", [v for sc in brows for i in range(N) for v in
                                             (sc["pos"][i, 0], sc["pos"][i, 1], sc["head"][i, 0], sc["head"][i, 1], float(sc["mode"][i]), sc["wdir"][i, 0],
                                              sc["wdir"][i, 1], float(sc["beh"][i]), sc["vel"][i, 0], sc["vel"][i, 1], float(sc["gait"][i]), float(sc["eat"][i]),
                                              float(sc["drain"][i]), float(sc["see"][i]), sc["sep"][i, 0], sc["sep"][i, 1], float(bool(sc["alive"][i])))], 17, d_lit))
    L.append(c_array("double", "kBDeerOut", [v for sc in brows for i in range(N) for v in
                                              (sc["out"]["vel"][i, 0], sc["out"]["vel"][i, 1], float(sc["out"]["gait"][i]), float(sc["out"]["eat"][i]),
                                               float(sc["out"]["drain"][i]), float(sc["out"]["see"][i]))], 6, d_lit))
    L.append("")
    L.append(f"\t// ---- 6 기준 루프 (사슴 {N_LOOP}·늑대 4, {LOOP_STEPS} 스텝, 내장 R1b — 두 고침 켬·끔, 지역 {len(loops)}) ----")
    L.append(f"\tinline constexpr std::int32_t kLoops = {len(loops)};")
    L.append(f"\tinline constexpr std::int32_t kLoopSteps = {LOOP_STEPS};")
    L.append(f"\tinline constexpr std::int32_t kLoopEvery = {LOOP_EVERY};")
    L.append(f"\tinline constexpr std::int32_t kLoopChecks = {LOOP_STEPS // LOOP_EVERY};")
    L.append(f"\tinline constexpr std::int32_t kLoopCheckLen = {CHECK_LEN};   // 잡힘·굶음·산 + 덮기별 실행 사슴-스텝 다섯 + 띠 방향 바꿈·멈춤")
    L.append("")
    for li, (region, seed, on, off, div) in enumerate(loops):
        job = on["job"]
        ns = f"Loop{li}"
        ws, wo = on["ws"], off["ws"]
        L.append(f"\t// 루프 {li}: 지역 {region}, 시드 {seed}. 켬: 잡힘 {on['caught']} · 거리 두기 시작 {ws['rest_starts']} · 띠 {ws['band_turn_steps']} "
                 f"(멈춤 {ws['band_stop_steps']}) · 끝 {ws['rest_ends']} · 최소 로짓 차 {min(on['gaps']['all'], off['gaps']['all']):.5f}. "
                 f"끔: 잡힘 {off['caught']}. 켬·끔 첫 갈림 지문 {div}")
        L.append(f"\tnamespace {ns}")
        L.append("\t{")
        Lw = []
        Lw.append(f"\tinline constexpr std::int32_t kSeed = {seed};")
        Lw.append(f"\tinline constexpr std::int32_t kN = {len(job['deer']['x'])};")
        Lw.append(f"\tinline constexpr std::int32_t kM = {len(job['wolves'])};")
        Lw.append(f"\tinline constexpr std::int32_t kFirstSplit = {div};")
        Lw.append("\t/** 세계 설정 (평가기 일의 world 블록 — EcoV3Eval.cpp ConfigOf 와 같은 대응). 두 고침 켬 판이다 (끔 판은 GrazeCalm·bRestKeep 만 끈다). */")
        Lw.append("\tinline void FillWorldConfig(FWorldConfig& C)")
        Lw.append("\t{")
        Lw += fg.config_code(job["world"])
        Lw.append("\t}")
        cov = np.asarray(job["covers"], dtype=np.float64).reshape(-1)
        dsc = np.asarray(job["discs"], dtype=np.float64).reshape(-1)
        Lw.append(f"\tinline constexpr std::int32_t kCoverCount = {len(job['covers'])};")
        Lw.append(c_array("double", "kCovers", cov, 6, d_lit))
        Lw.append(f"\tinline constexpr std::int32_t kDiscCount = {len(job['discs'])};")
        Lw.append(c_array("double", "kDiscs", dsc if len(dsc) else [0.0], 6, d_lit))
        fd = job["food"]
        Lw.append(f"\tinline constexpr std::int32_t kGw = {int(fd['gw'])};")
        Lw.append(f"\tinline constexpr double kCell = {d_lit(fd['cell'])};")
        Lw.append(c_array("double", "kCap", fd["cap"], 6, d_lit))
        Lw.append(c_array("double", "kFood", fd["food"], 6, d_lit))
        Lw.append(c_array("double", "kRegen", fd["regen"], 6, d_lit))
        dj = job["deer"]
        n = len(dj["x"])
        if dj["slot"] != list(range(n)):
            raise SystemExit("기준 루프 사슴 슬롯이 0..N−1 이 아니다")
        Lw.append("\t// 사슴 (슬롯 순서) x, y, hx, hy, energy, reserve · 번식 쿨다운")
        Lw.append(c_array("double", "kDeer", [v for i in range(n) for v in (dj["x"][i], dj["y"][i], dj["hx"][i], dj["hy"][i], dj["energy"][i],
                                                                             dj["reserve"][i])], 6, d_lit))
        Lw.append(c_array("std::int32_t", "kDeerRepro", dj["repro_cd"], 24, i_lit))
        wv = job["wolves"]
        if [a["slot"] for a in wv] != list(range(len(wv))):
            raise SystemExit("기준 루프 늑대 슬롯이 0..M−1 이 아니다")
        Lw.append("\t// 늑대 (위협 슬롯 순서) x, y, hx, hy, 기본 속력 · 잠행형인가")
        Lw.append(c_array("double", "kWolves", [v for a in wv for v in (a["x"], a["y"], a["hx"], a["hy"], a["speed"])], 5, d_lit))
        Lw.append(c_array("std::uint8_t", "kWolfStalker", [int(a["kind"] == "stalker") for a in wv], 8, i_lit))
        Lw.append(f"\t// 세계 난수: numpy PCG64 날 64 비트 {len(on['raw'])} 개 (스텝마다 늑대 슬롯 순서 배회 선회 — FRng::External)")
        Lw.append(c_array("std::uint64_t", "kRaw", on["raw"], 4, u64_lit))
        Lw.append("\t// 지문 (생성기 머리 주석 '지문', 0 번 = 시작) — 두 고침 켬·끔")
        Lw.append(c_array("std::uint64_t", "kHashOn", on["hashes"], 4, u64_lit))
        Lw.append(c_array("std::uint64_t", "kHashOff", off["hashes"], 4, u64_lit))
        Lw.append(f"\t// {LOOP_EVERY} 스텝마다 기록 (kLoopCheckLen 칸)")
        Lw.append(c_array("std::int64_t", "kCheckOn", [v for r in on["checks"] for v in r], 10, i64_lit))
        Lw.append(c_array("std::int64_t", "kCheckOff", [v for r in off["checks"] for v in r], 10, i64_lit))
        L += ["\t" + x for x in Lw]
        L.append("\t}")
        L.append("")
    L.append("\t/** 루프 표 (검사가 루프 번호로 읽는다 — 배열 길이는 칸 수로 함께 둔다). */")
    L.append("\tstruct FLoopTable")
    L.append("\t{")
    L.append("\t\tconst char* Region;")
    L.append("\t\tstd::int32_t Seed, N, M;")
    L.append("\t\tvoid (*Fill)(FWorldConfig&);")
    L.append("\t\tconst double* Covers;")
    L.append("\t\tstd::int32_t CoverCount;")
    L.append("\t\tconst double* Discs;")
    L.append("\t\tstd::int32_t DiscCount;")
    L.append("\t\tstd::int32_t Gw;")
    L.append("\t\tdouble Cell;")
    L.append("\t\tconst double* Cap;")
    L.append("\t\tconst double* Food;")
    L.append("\t\tconst double* Regen;")
    L.append("\t\tstd::int64_t Cells;")
    L.append("\t\tconst double* Deer;")
    L.append("\t\tconst std::int32_t* DeerRepro;")
    L.append("\t\tconst double* Wolves;")
    L.append("\t\tconst std::uint8_t* WolfStalker;")
    L.append("\t\tconst std::uint64_t* Raw;")
    L.append("\t\tstd::int64_t RawCount;")
    L.append("\t\tconst std::uint64_t* HashOn;")
    L.append("\t\tconst std::uint64_t* HashOff;")
    L.append("\t\tconst std::int64_t* CheckOn;")
    L.append("\t\tconst std::int64_t* CheckOff;")
    L.append("\t\tstd::int32_t FirstSplit;")
    L.append("\t};")
    rows_t = []
    for li, (region, *_r) in enumerate(loops):
        ns = f"Loop{li}"
        rows_t.append(f"\t\t{{\"{region}\", {ns}::kSeed, {ns}::kN, {ns}::kM, &{ns}::FillWorldConfig, {ns}::kCovers, {ns}::kCoverCount, {ns}::kDiscs, "
                      f"{ns}::kDiscCount, {ns}::kGw, {ns}::kCell, {ns}::kCap, {ns}::kFood, {ns}::kRegen, "
                      f"static_cast<std::int64_t>(sizeof({ns}::kCap) / sizeof(double)), {ns}::kDeer, {ns}::kDeerRepro, {ns}::kWolves, {ns}::kWolfStalker, "
                      f"{ns}::kRaw, static_cast<std::int64_t>(sizeof({ns}::kRaw) / sizeof({ns}::kRaw[0])), {ns}::kHashOn, {ns}::kHashOff, {ns}::kCheckOn, "
                      f"{ns}::kCheckOff, {ns}::kFirstSplit}},")
    L.append(f"\tinline constexpr FLoopTable kLoopTable[{len(loops)}] = {{")
    L += rows_t
    L.append("\t};")
    L.append("}")
    L.append("")
    nrest = int(np.count_nonzero(modes == WF_REST))
    print(f"방향 {len(drows)} (손 {dhand}) · 제어 {len(crows)} · 덮기 장면 {len(scs)} (손 {shand}, 거리 두기 {nrest}) · B 장면 {len(brows)} · 루프 "
          + ", ".join(f"{r} 시드 {s} (첫 갈림 {d})" for r, s, _, _, d in loops))
    if nrest == 0:
        raise SystemExit("덮기 장면에 거리 두기가 없다")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    text = build_header()
    out = args.out / HEADER
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"썼다: {out} ({len(text.encode('utf-8'))} 바이트)")


if __name__ == "__main__":
    main()
