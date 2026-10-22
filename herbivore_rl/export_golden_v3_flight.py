"""v3 야생 (w3) 도망 기록 골든 내보내기 — 파이썬 도망 기록(env_v2/world.py 모듈 docstring '야생 1단계' (w3) 도망 기록, `World._fl_update`·
`_fl_close`·`flight_stats`)을 언리얼 C++ `EcoWorldV3.h` (FlightUpdate·FlightClose·FlightReportOf·FlightPairOf)와 대조할 골든 헤더를 만든다
(10-21 사용자 '언리얼에서 도는 두뇌를 굳이 파이썬으로 다시 시험하지 말고 언리얼 자체에서 평가' — C++ 평가기가 같은 정의로 센다).

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_flight.py
    # 시험용 다른 폴더
    python export_golden_v3_flight.py --out <폴더>

세계·시드: configs/v3_wild3_obs_mirror.yaml (언리얼 통합 기본의 거울 — 부활 없음, 숲 나무 원판 24·늑대 4·도주 반사·은신처 안전). 이 내보내기 전용 탐색 시드
32098(기준 루프)·32099(짜 맞춘 장면의 그릇·쌍 장면 난수). 판정 시드는 쓰지 않는다. C++ 와 파이썬은 난수열이 달라 세계 궤적은 대조하지 않는다 — 도망 기록은
스텝마다 받는 재료(FLEE·덮기·죽음·은신처·늑대 표적·사냥·놓침 까닭 쌍)의 순수 함수라 그 재료를 적어 C++ 에 그대로 먹인다.

묶음:
  짜 맞춘 장면  tests/test_flight_v3.py 의 `_tick` 장면 셋(끝 까닭·은신처/붙잡힘/바꿈/그만둠/시야각·놓침 우선순위/마지막 놓침/다시 남) + 난수 장면 하나(사슴 6 ×
                300 틱 — FLEE·표적·놓침 쌍·쉬는 늑대·죽음을 난수로). 틱마다 재료와 그 뒤 flight_stats·사슴 칸·늑대 지난 표적.
  기준 루프     거울 세계(사슴 32)를 무작위 요청(먹기·도망·숨기 — test_flight_v3 `_run` 과 같은 꼴)으로 600 스텝 돌리며 track_flight 를 켜고, `_fl_update`
                를 부를 때마다 재료를 적는다(사슴: FLEE·반사·죽음·잡힘·은신처·첫머리 산, 늑대: 표적·스텝 끝 사냥·표적 고르기 때 사냥, 지난 표적(_fl_tgt)과의 쌍).
                100 스텝마다 flight_stats·사슴 칸·늑대 지난 표적.
  쌍 장면       놓침 까닭 재료 자체: 거울 세계(사슴 16·늑대 4)의 상태를 장면마다 정해 `World._step_predators_v3` 를 한 번 부르고 `_fl_pred`(사냥 가능, 시야 반경
                안·반경과 시야각 안·원판이 가림·은신처 표적 제외)를 적는다. C++ 은 같은 상태로 FlightPairOf 를 모든 쌍에, 위협 Step 사본으로 사냥 가능을 낸다.

칸 묶음 (C++ 꼴):
  사슴 재료 비트   1 FLEE 실행 · 2 실행한 덮기 도주 · 4 죽음 · 8 잡힘 · 16 스텝 끝 은신처 원 안 · 32 스텝 첫머리에 산
  늑대 재료 비트   1 스텝 끝 사냥 중 · 2 표적 고르기 때 사냥 가능 · 4 쌍 칸 있음(_fl_pred) · 8 시야 반경 안 · 16 반경과 시야각 안 · 32 원판이 가림 ·
                   64 은신처 표적 제외 — 쌍은 (늑대, 지난 표적 _fl_tgt) 칸 (지난 표적이 없으면 쌍 비트는 1·1·0·0)
  보고 49 칸       started, live_steps, flee_steps, reflex_steps, n × 11, steps × 11, contact × 11, own_n, own_steps, own_contact, shelter_end, hist × 8
  사슴 칸 7 개     _fl_len, _fl_contact, _fl_reflex, _fl_chased, _fl_why, _fl_end_now, _fl_end_cov
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import (FL_DROP_CAUSE, FL_DROP_COVER, FL_DROP_FOV, FL_DROP_NONE, FL_DROP_OBSTACLE, FL_DROP_RANGE, FL_DROP_STOP, FL_DROP_SWITCH,
                          FLIGHT_CAUSES, FLIGHT_HIST_STEPS, FLIGHT_OWN, PT_STALKER, ST_EXHAUST, ST_POUNCE, ST_ROAM, World, obstacle_inside)

HERE = Path(__file__).resolve().parent
OBS = HERE / "configs" / "v3_wild3_obs_mirror.yaml"
DEFAULT_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
SEED_LOOP = 32098
SEED_SCENE = 32099
N_LOOP = 32
LOOP_STEPS = 600
LOOP_EVERY = 100
LOOP_ACTS_SEED = 11
RANDOM_TICKS = 300
N_PAIR = 16
PAIR_SCENES = 48
STATS_LEN = 4 + 3 * len(FLIGHT_CAUSES) + 4 + len(FLIGHT_HIST_STEPS) + 1
TRACK_LEN = 7


def c_array(ctype: str, name: str, flat: list, per_line: int, fmt) -> str:
    if not flat:
        raise SystemExit(f"{name} 가 비었다 — C++ 배열은 크기 0 일 수 없다")
    lines = [f"\tinline constexpr {ctype} {name}[{len(flat)}] = {{"]
    for k in range(0, len(flat), per_line):
        lines.append("\t\t" + ", ".join(fmt(v) for v in flat[k:k + per_line]) + ",")
    lines.append("\t};")
    return "\n".join(lines)


def d_lit(x) -> str:
    """double 리터럴: 파이썬 repr (다시 읽으면 같은 float64 가 되는 가장 짧은 표기)."""
    x = float(x)
    if not math.isfinite(x):
        raise SystemExit(f"헤더에 유한하지 않은 값: {x}")
    s = repr(x)
    return s if ("." in s or "e" in s) else s + ".0"


def i_lit(x) -> str:
    return str(int(x))


def i64_lit(x) -> str:
    return f"{int(x)}LL"


# --------------------------------------------------------------------- #
# 재료·결과 적기 (`_fl_update` 를 감싼다 — 감싼 함수는 원래 함수를 그대로 부른다)
# --------------------------------------------------------------------- #


def stats_row(f: dict) -> list[int]:
    out = [f["started"], f["live_steps"], f["flee_steps"], f["reflex_steps"]]
    for key in ("n", "steps", "contact"):
        out += [f[key][c] for c in FLIGHT_CAUSES]
    out += [f["own_n"], f["own_steps"], f["own_contact"], f["shelter_end"]]
    out += list(f["hist"])
    if len(out) != STATS_LEN:
        raise SystemExit(f"보고 칸 수 {len(out)} != {STATS_LEN}")
    return [int(v) for v in out]


def track_rows(w: World) -> list[int]:
    out = []
    for i in range(w.N):
        out += [int(w._fl_len[i]), int(w._fl_contact[i]), int(w._fl_reflex[i]), int(bool(w._fl_chased[i])), int(w._fl_why[i]),
                int(bool(w._fl_end_now[i])), int(bool(w._fl_end_cov[i]))]
    return out


class Recorder:
    """`w._fl_update` 를 감싸 부를 때마다 재료(사슴·늑대 비트, 늑대 표적·지난 표적)를 적는다. 원래 함수는 그대로 부른다."""

    def __init__(self, w: World):
        if w._wf is None or w._wf.get("route_fixed") is not None:
            # C++ 포팅(EcoWorldV3.h FlightUpdate)에는 도망길 기록이 없다 — 길 끈 wild_flight 세계만 골든으로 쓴다
            raise ValueError("골든 세계는 wild_flight 를 켜고 route_fixed 를 끈 세계여야 한다")
        self.w = w
        self.orig = w._fl_update
        self.deer: list[list[int]] = []
        self.wolf_bits: list[list[int]] = []
        self.wolf_tgt: list[list[int]] = []
        self.wolf_prev: list[list[int]] = []
        w._fl_update = self

    def __call__(self, flee, reflex, done, caught, live, in_cov, *rest, **kw):
        # rest·kw = world.py 가 뒤에 더한 인자(예: 도망길 route_exec) — 적지 않고 원래 함수에 그대로 넘긴다
        w = self.w
        N, M = w.N, w.M
        flee = np.asarray(flee, dtype=bool)
        reflex = np.asarray(reflex, dtype=bool)
        done = np.asarray(done, dtype=bool)
        cg = np.zeros(N, dtype=bool) if caught is None else np.asarray(caught, dtype=bool)
        live = np.asarray(live, dtype=bool)
        in_cov = np.asarray(in_cov, dtype=bool)
        alive0 = live | done
        self.deer.append([int(flee[i]) | 2 * int(reflex[i]) | 4 * int(done[i]) | 8 * int(cg[i]) | 16 * int(in_cov[i]) | 32 * int(alive0[i])
                          for i in range(N)])
        tgt = getattr(w, "pred_target", None)
        tgt = np.asarray(tgt, dtype=np.int64) if tgt is not None and np.shape(tgt) == (M,) else np.full(M, -1, dtype=np.int64)
        hunt_end = w._wf_hunting() if M > 0 else np.zeros(0, dtype=bool)
        tp = w._fl_tgt.copy() if w._fl_tgt.shape == (M,) else np.full(M, -1, dtype=np.int64)
        fp = w._fl_pred
        has_fp = fp is not None and fp[1].shape == (M, N)
        bits = []
        for m in range(M):
            b = int(bool(hunt_end[m]))
            b |= 2 * int(bool(fp[0][m])) if has_fp else 2
            if has_fp:
                b |= 4
            i = int(tp[m])
            rng_, vis0, blk, cov = True, True, False, False
            if has_fp and 0 <= i < N:
                rng_, vis0, blk, cov = bool(fp[1][m, i]), bool(fp[2][m, i]), bool(fp[3][m, i]), bool(fp[4][m, i])
            b |= 8 * int(rng_) | 16 * int(vis0) | 32 * int(blk) | 64 * int(cov)
            bits.append(b)
        self.wolf_bits.append(bits)
        self.wolf_tgt.append([int(v) for v in tgt])
        self.wolf_prev.append([int(v) if 0 <= v < N else -1 for v in tp])
        self.orig(flee, reflex, done, caught, live, in_cov, *rest, **kw)


# --------------------------------------------------------------------- #
# 짜 맞춘 장면 (tests/test_flight_v3.py `_tick` 과 같은 꼴)
# --------------------------------------------------------------------- #


class Scene:
    def __init__(self, name: str, n: int):
        self.name = name
        self.w = World(load_v2_config(OBS).replace(N=n), seeds=[SEED_SCENE])
        self.w.track_flight = True
        self.w._fl_reset()
        self.rec = Recorder(self.w)
        self.stats: list[list[int]] = []
        self.tracks: list[list[int]] = []
        self.prev_after: list[list[int]] = []

    @property
    def N(self):
        return self.w.N

    @property
    def M(self):
        return self.w.M

    def tick(self, flee, tgt=None, done=(), caught=(), in_cov=(), pred=None, reflex=None, idle=()):
        """test_flight_v3 `_tick` 그대로 (한 스텝 — 재료를 짜 맞춰 `_fl_update` 를 부른다)."""
        w = self.w
        N, M = w.N, w.M

        def mask(ix):
            m = np.zeros(N, dtype=bool)
            m[list(ix)] = True
            return m

        d = mask(done)
        w.pred_target = np.full(M, -1, dtype=np.int64) if tgt is None else np.asarray(tgt, dtype=np.int64)
        w.pred_cd = np.zeros(M, dtype=np.int64)
        w.pred_cd[list(idle)] = 30
        if getattr(w, "pred_asleep", None) is not None:
            w.pred_asleep = np.zeros(M, dtype=bool)
        if getattr(w, "pred_sat", None) is not None:
            w.pred_sat = np.zeros(M, dtype=np.int64)
        no = np.zeros((M, N), dtype=bool)
        w._fl_pred = pred if pred is not None else (np.ones(M, dtype=bool), np.ones((M, N), dtype=bool), np.ones((M, N), dtype=bool), no, no.copy())
        w._fl_update(mask(flee), mask(flee if reflex is None else reflex), d, mask(caught), np.ones(N, dtype=bool) & ~d, mask(in_cov))
        self.after()

    def raw(self, flee, reflex, done, caught, in_cov, tgt, idle, pred):
        """난수 장면용: 마스크·행렬을 그대로 넣는다."""
        w = self.w
        N, M = w.N, w.M
        w.pred_target = np.asarray(tgt, dtype=np.int64)
        w.pred_cd = np.where(idle, 30, 0).astype(np.int64)
        if getattr(w, "pred_asleep", None) is not None:
            w.pred_asleep = np.zeros(M, dtype=bool)
        if getattr(w, "pred_sat", None) is not None:
            w.pred_sat = np.zeros(M, dtype=np.int64)
        w._fl_pred = pred
        w._fl_update(flee, reflex, done, caught, np.ones(N, dtype=bool) & ~done, in_cov)
        self.after()

    def after(self):
        w = self.w
        self.stats.append(stats_row(w.flight_stats()))
        self.tracks.append(track_rows(w))
        self.prev_after.append([int(v) if 0 <= v < w.N else -1 for v in w._fl_tgt])


def _t(M, **pairs):
    return [pairs.get(f"w{m}", -1) for m in range(M)]


def scene_end_causes() -> Scene:
    """test_end_causes_scripted 그대로."""
    sc = Scene("끝 까닭 (원판·반경·안 쫓김·잡힘·잘림)", 6)
    M, N = sc.M, sc.N
    no = np.zeros((M, N), dtype=bool)
    yes = np.ones((M, N), dtype=bool)
    sc.tick([0, 1, 2, 4], tgt=_t(M, w0=0, w1=2))
    blk = no.copy()
    blk[0, 0] = True
    rng_ = yes.copy()
    rng_[1, 2] = False
    sc.tick([0, 1, 2, 4], tgt=_t(M, w0=0), pred=(np.ones(M, dtype=bool), rng_, rng_.copy(), no.copy(), no.copy()), in_cov=[1])
    sc.tick([0, 4, 5], pred=(np.ones(M, dtype=bool), yes, yes, blk, no.copy()), done=[4], caught=[4])
    sc.tick([5])
    return sc


def scene_cover_held() -> Scene:
    """test_cover_held_switch_stop_and_own_flee 그대로."""
    sc = Scene("은신처·붙잡힘·바꿈·그만둠·시야각", 4)
    M, N = sc.M, sc.N
    no = np.zeros((M, N), dtype=bool)
    yes = np.ones((M, N), dtype=bool)
    sc.tick([0, 1], tgt=_t(M, w0=0, w1=1), reflex=[0], in_cov=[0])
    sc.tick([])
    sc.tick([2, 3], tgt=_t(M, w0=2, w1=3))
    cov = no.copy()
    cov[0, 2] = True
    sc.tick([2, 3], tgt=_t(M, w1=0), pred=(np.ones(M, dtype=bool), yes, yes, no.copy(), cov))
    sc.tick([])
    sc.tick([0], tgt=_t(M, w0=0))
    sc.tick([0], tgt=_t(M, w0=0), idle=[0], done=[1], caught=[1])
    sc.tick([])
    sc.tick([2], tgt=_t(M, w0=2))
    hunt = np.ones(M, dtype=bool)
    hunt[0] = False
    sc.tick([2], pred=(hunt, no.copy(), no.copy(), no.copy(), no.copy()))
    sc.tick([3], tgt=_t(M, w0=3))
    sc.tick([2, 3], pred=(np.ones(M, dtype=bool), yes, no.copy(), no.copy(), no.copy()))
    sc.tick([])
    return sc


def scene_priority() -> Scene:
    """test_drop_priority_last_drop_and_respawn 그대로."""
    sc = Scene("놓침 우선순위·마지막 놓침·다시 남", 4)
    M, N = sc.M, sc.N
    no = np.zeros((M, N), dtype=bool)
    yes = np.ones((M, N), dtype=bool)
    sc.tick([0], tgt=_t(M, w0=0, w1=0))
    rng_ = yes.copy()
    rng_[1, 0] = False
    blk = no.copy()
    blk[0, 0] = True
    sc.tick([0], pred=(np.ones(M, dtype=bool), rng_, rng_.copy(), blk, no.copy()))
    sc.tick([0], tgt=_t(M, w0=0))
    rng_ = yes.copy()
    rng_[0, 0] = False
    sc.tick([0], pred=(np.ones(M, dtype=bool), rng_, rng_.copy(), no.copy(), no.copy()))
    sc.tick([])
    sc.tick([], tgt=_t(M, w0=3))
    sc.tick([3], pred=(np.ones(M, dtype=bool), yes, yes, blk[:, [3, 1, 2, 0]], no.copy()))
    sc.tick([])
    sc.tick([1], tgt=_t(M, w0=1))
    sc.tick([1], tgt=_t(M, w0=1), done=[1], caught=[1])
    sc.tick([1])
    sc.tick([])
    return sc


def scene_random(ticks: int = RANDOM_TICKS) -> Scene:
    """난수 장면: 사슴 6 의 FLEE 는 이어지기 쉽게(바뀔 확률 0.25), 늑대 4 의 표적은 사슴·없음 가운데, 쌍 칸·쉬는 늑대·표적 고르기 때 사냥 못 함·은신처·
    죽음(잡힘·굶음)은 난수로. 여러 늑대가 한 사슴을 같은 스텝에 놓치는 경우·FLEE 첫 스텝 놓침·쫓긴 뒤 놓치고 다시 쫓김이 모두 나온다."""
    sc = Scene("난수 장면", 6)
    M, N = sc.M, sc.N
    rng = np.random.default_rng(SEED_SCENE + 1)
    flee = np.zeros(N, dtype=bool)
    for _ in range(ticks):
        flip = rng.random(N) < 0.25
        flee = np.where(flip, ~flee, flee)
        reflex = flee & (rng.random(N) < 0.6)
        done = rng.random(N) < 0.03
        caught = done & (rng.random(N) < 0.7)
        in_cov = rng.random(N) < 0.2
        focus = int(rng.integers(0, N))
        tgt = np.where(rng.random(M) < 0.5, focus, rng.integers(-1, N, M))
        idle = rng.random(M) < 0.15
        hunt = rng.random(M) < 0.9
        rng_ = rng.random((M, N)) < 0.8
        vis0 = rng_ & (rng.random((M, N)) < 0.8)
        blk = vis0 & (rng.random((M, N)) < 0.25)
        cov = rng.random((M, N)) < 0.15
        sc.raw(flee.copy(), reflex, done, caught, in_cov, tgt, idle, (hunt, rng_, vis0, blk, cov))
        flee = flee & ~done
    return sc


# --------------------------------------------------------------------- #
# 기준 루프 (거울 세계 600 스텝)
# --------------------------------------------------------------------- #


def loop_world():
    w = World(load_v2_config(OBS).replace(N=N_LOOP), seeds=[SEED_LOOP])
    if w._wf is None or w.alive is None or not len(w.obstacles) or w._zs is None:
        raise SystemExit("v3_wild3_obs_mirror.yaml 은 도주 반사·부활 없음·원판·은신처 안전을 켠 세계여야 한다")
    w.track_flight = True
    rec = Recorder(w)
    rng = np.random.default_rng(LOOP_ACTS_SEED)
    stats, tracks, prev_after, at = [], [], [], []
    for t in range(1, LOOP_STEPS + 1):
        w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        if t % LOOP_EVERY == 0:
            at.append(t)
            stats.append(stats_row(w.flight_stats()))
            tracks.append(track_rows(w))
            prev_after.append([int(v) if 0 <= v < w.N else -1 for v in w._fl_tgt])
    if len(rec.deer) != LOOP_STEPS:
        raise SystemExit(f"기준 루프 재료 {len(rec.deer)} 스텝 != {LOOP_STEPS}")
    f = w.flight_stats()
    return dict(w=w, rec=rec, stats=stats, tracks=tracks, prev_after=prev_after, at=at, final=f)


# --------------------------------------------------------------------- #
# 쌍 장면 (`_step_predators_v3` 의 _fl_pred)
# --------------------------------------------------------------------- #


def pair_scenes():
    w = World(load_v2_config(OBS).replace(N=N_PAIR), seeds=[SEED_SCENE])
    if w._zc is not None or w._sd is not None or w._zt is not None or w._pred_ranged_v1.any() or w.M != w.M_base:
        raise SystemExit("쌍 장면은 추격 고정·노려보기·지형·원거리형·플레이어가 없어야 한다(C++ 위협 모델에 없다)")
    if not (w._zs and w._zs["untargetable"] and w._zs["player_too"]) or w._ob is None or not w._ob["block_sight"]:
        raise SystemExit("쌍 장면은 은신처 표적 제외(플레이어 포함)·원판 눈길 가림을 켠 세계여야 한다")
    w.track_flight = True
    w._fl_reset()
    rng = np.random.default_rng(SEED_SCENE + 2)
    S, M, N = w.size, w.M, w.N
    rp, disc, body = w._rp, w.obstacles, w._ob["body_r"]
    sights = (1.0, w._wx_sight if w._wx is not None else 1.0, 0.7)
    out = []
    for s in range(PAIR_SCENES):
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
        asleep = np.zeros(M, dtype=bool)
        for m in range(M):
            u = rng.random()
            if u < 0.08:
                cd[m] = int(rng.integers(1, 39))
            elif u < 0.14:
                sat[m] = int(rng.integers(1, 451))
            elif u < 0.20:
                asleep[m] = True
            elif u < 0.30 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_POUNCE, int(rng.integers(0, 13))
            elif u < 0.36 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_EXHAUST, int(rng.integers(1, 31))
        # 사슴: 늑대 앞·뒤·옆, 은신처 둘레·안, 원판 뒤에 몰아 반경·시야각·가림·은신처가 모두 나오게
        p = rng.uniform(0.0, S, (N, 2))
        for i in range(N):
            m = int(rng.integers(0, M))
            u = rng.random()
            if u < 0.45:
                a = math.atan2(head[m, 1], head[m, 0]) + rng.normal(0.0, 1.4)
                p[i] = q[m] + rng.uniform(1.0, 22.0) * np.array([math.cos(a), math.sin(a)])
            elif u < 0.65:
                k = int(rng.integers(0, len(w.cov_r)))
                a = rng.uniform(0.0, 2.0 * math.pi)
                p[i] = w.cov_c[k] + rng.uniform(0.0, w.cov_r[k] + 1.5) * np.array([math.cos(a), math.sin(a)])
            elif u < 0.85 and len(disc):
                k = int(rng.integers(0, len(disc)))
                v = disc[k, :2] - q[m]
                n = max(float(np.linalg.norm(v)), 1e-9)
                p[i] = disc[k, :2] + v / n * (disc[k, 2] + body + rng.uniform(0.05, 3.0)) + rng.normal(0.0, 0.3, 2)
        p = np.clip(p, 0.0, S)
        beh = rng.choice([rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP], N, p=[0.4, 0.2, 0.2, 0.1, 0.1]).astype(np.int8)
        arrived = (beh == rep.HIDE) & (rng.random(N) < 0.6)
        crouch = (beh == rep.HIDE) & arrived
        sight = float(sights[s % len(sights)])
        w.pos = p.copy()
        w._pack_p0 = p.copy()
        w._rs.behavior[:] = beh
        w._rs.arrived[:] = arrived
        w._rep_still = (beh == rep.FREEZE) | (beh == rep.SLEEP) | crouch
        w._rep_cover = rep.cover_mult(rp, beh, crouch)
        w.alive = np.ones(N, dtype=bool)
        w.pred_pos, w.pred_head = q.copy(), head.copy()
        w.pred_cd, w.pred_sat = cd.copy(), sat.copy()
        w.stalk_state, w.stalk_left = st.copy(), left.copy()
        w.pred_asleep = asleep.copy()
        w._pred_speed_mult = np.where(asleep, 0.0, 1.0)
        w.dark = 0.0
        w._zn_hunt = np.zeros(M, dtype=bool)
        w._hunt_on = np.zeros(M, dtype=bool)
        if w._wx is not None:
            w._wx_sight = sight
            w._wx_view = w.cfg.pred_view_r * sight
        elif sight != 1.0:
            raise SystemExit("날씨를 끈 세계는 시야 배수 1 만")
        in_cov = w._in_cover(w.pos)
        w._fl_pred = None
        w._step_predators_v3()
        fp = w._fl_pred
        if fp is None or fp[1].shape != (M, N):
            raise SystemExit("쌍 장면: _fl_pred 가 없다")
        out.append(dict(q=q, head=head, cd=cd, sat=sat, st=st, left=left, asleep=asleep, p=p, beh=beh, arrived=arrived, in_cov=in_cov,
                        sight=sight, hunt=fp[0].copy(), rng=fp[1].copy(), vis0=fp[2].copy(), blk=fp[3].copy(), cov=fp[4].copy()))
    consts = dict(size=S, M=M, N=N, discs=disc.copy(), kinds=w.pred_type.copy(), eat_cd=int(w.cfg.pred_eat_cd), sat_steps=int(w._ws_sat_steps),
                  pred_speed_mult=float(w.pred_speed_mult), view_r=float(w.cfg.pred_view_r), fov_cos=float(w.cfg.pred_fov_cos),
                  c_still=float(rp["c_still"]), cover_mult=(float(rp["cover_mult_crouch"]), float(rp["cover_mult_graze"]), float(rp["cover_mult_sleep"]),
                                                             float(rp["cover_mult_other"])))
    return out, consts


# --------------------------------------------------------------------- #
# 헤더
# --------------------------------------------------------------------- #


def build_header() -> str:
    if (FL_DROP_NONE, FL_DROP_RANGE, FL_DROP_SWITCH, FL_DROP_FOV, FL_DROP_STOP, FL_DROP_OBSTACLE, FL_DROP_COVER) != (0, 1, 2, 3, 4, 5, 6):
        raise SystemExit("놓침 까닭 번호가 바뀌었다 — C++ kFlDrop* 와 맞춘다")
    if (rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP) != (0, 1, 2, 3, 4):
        raise SystemExit("행동 번호가 바뀌었다 — C++ kPrey* 와 맞춘다")
    scenes = [scene_end_causes(), scene_cover_held(), scene_priority(), scene_random()]
    loop = loop_world()
    pairs, pc = pair_scenes()

    L = []
    L.append("// 자동 생성 — herbivore_rl/export_golden_v3_flight.py (손으로 고치지 않는다). 세계 configs/v3_wild3_obs_mirror.yaml, "
             f"시드 {SEED_LOOP}·{SEED_SCENE}.")
    L.append("// v3 야생 (w3) 도망 기록 골든 (world.py 모듈 docstring '야생 1단계' (w3) 도망 기록 — `_fl_update`·`flight_stats`). "
             "검사는 Tests/EcoFlightV3Test.cpp (AdaptiveEcosystem.Policy.V3.Flight.*).")
    L.append("#pragma once")
    L.append("")
    L.append("#include <cstdint>")
    L.append("")
    L.append("namespace EcoWorldV3::GoldenFlight")
    L.append("{")
    L.append("\t// ---- 정의 (FLIGHT_CAUSES 순서 이름은 C++ FlightCauseName 과 같다. FLIGHT_OWN = 앞 넷, FL_DROP_CAUSE = 놓침 까닭 → 끝 까닭) ----")
    L.append(f"\tinline constexpr std::int32_t kNumCauses = {len(FLIGHT_CAUSES)};")
    L.append("\tinline constexpr const char* kCauseNames[kNumCauses] = {" + ", ".join(f'"{c}"' for c in FLIGHT_CAUSES) + "};")
    own_ix = [FLIGHT_CAUSES.index(c) for c in FLIGHT_OWN]
    L.append(f"\tinline constexpr std::int32_t kNumOwn = {len(FLIGHT_OWN)};")
    L.append(c_array("std::int32_t", "kOwn", own_ix, 8, i_lit))
    L.append(c_array("std::int32_t", "kHistSteps", list(FLIGHT_HIST_STEPS), 8, i_lit))
    L.append(c_array("std::int32_t", "kDropCause", [FLIGHT_CAUSES.index(FL_DROP_CAUSE[k]) for k in range(FL_DROP_COVER + 1)], 8, i_lit))
    L.append(f"\tinline constexpr std::int32_t kStatsLen = {STATS_LEN};   // started, live_steps, flee_steps, reflex_steps, n·steps·contact × 11, own_n, own_steps, "
             "own_contact, shelter_end, hist × 8")
    L.append(f"\tinline constexpr std::int32_t kTrackLen = {TRACK_LEN};   // _fl_len, _fl_contact, _fl_reflex, _fl_chased, _fl_why, _fl_end_now, _fl_end_cov")
    L.append("")

    # 짜 맞춘 장면
    L.append("\t// ---- 짜 맞춘 장면 (tests/test_flight_v3.py `_tick` 장면 셋 + 난수 장면). 틱마다 사슴 재료 비트 N 개, 늑대 재료 비트·표적·지난 표적 M 개씩,")
    L.append("\t//      그 뒤 보고 kStatsLen·사슴 칸 kTrackLen × N·늑대 지난 표적(_fl_tgt) M. 장면마다 처음 상태(빈 도망)에서 시작한다 ----")
    L.append(f"\tinline constexpr std::int32_t kSceneCount = {len(scenes)};")
    L.append(c_array("std::int32_t", "kSceneN", [sc.N for sc in scenes], 8, i_lit))
    L.append(c_array("std::int32_t", "kSceneM", [sc.M for sc in scenes], 8, i_lit))
    L.append(c_array("std::int32_t", "kSceneTicks", [len(sc.stats) for sc in scenes], 8, i_lit))
    deer, wb, wt, wp, st, tr, pa = [], [], [], [], [], [], []
    for sc in scenes:
        r = sc.rec
        for k in range(len(sc.stats)):
            deer += r.deer[k]
            wb += r.wolf_bits[k]
            wt += r.wolf_tgt[k]
            wp += r.wolf_prev[k]
            st += sc.stats[k]
            tr += sc.tracks[k]
            pa += sc.prev_after[k]
    L.append(c_array("std::uint8_t", "kSceneDeer", deer, 24, i_lit))
    L.append(c_array("std::uint8_t", "kSceneWolfBits", wb, 24, i_lit))
    L.append(c_array("std::int32_t", "kSceneWolfTarget", wt, 24, i_lit))
    L.append(c_array("std::int32_t", "kSceneWolfPrev", wp, 24, i_lit))
    L.append(c_array("std::int64_t", "kSceneStats", st, 12, i64_lit))
    L.append(c_array("std::int32_t", "kSceneTracks", tr, 21, i_lit))
    L.append(c_array("std::int32_t", "kScenePrevAfter", pa, 24, i_lit))
    L.append("")

    # 기준 루프
    w = loop["w"]
    rec = loop["rec"]
    f = loop["final"]
    L.append(f"\t// ---- 기준 루프: 거울 세계 사슴 {w.N}·늑대 {w.M}, 무작위 요청(먹기·도망·숨기, 난수 시드 {LOOP_ACTS_SEED}) {LOOP_STEPS} 스텝. 스텝마다 재료,")
    L.append(f"\t//      {LOOP_EVERY} 스텝마다 보고·사슴 칸·늑대 지난 표적. 끝 보고: 시작 {f['started']} · 끝 까닭 "
             + " ".join(f"{c} {f['n'][c]}" for c in FLIGHT_CAUSES if f['n'][c]) + f" · 스스로 {f['own_n']} ----")
    L.append(f"\tinline constexpr std::int32_t kLoopN = {w.N};")
    L.append(f"\tinline constexpr std::int32_t kLoopM = {w.M};")
    L.append(f"\tinline constexpr std::int32_t kLoopSteps = {LOOP_STEPS};")
    L.append(f"\tinline constexpr std::int32_t kLoopEvery = {LOOP_EVERY};")
    L.append(f"\tinline constexpr std::int32_t kLoopChecks = {len(loop['at'])};")
    L.append(c_array("std::uint8_t", "kLoopDeer", [v for row in rec.deer for v in row], 32, i_lit))
    L.append(c_array("std::uint8_t", "kLoopWolfBits", [v for row in rec.wolf_bits for v in row], 32, i_lit))
    L.append(c_array("std::int32_t", "kLoopWolfTarget", [v for row in rec.wolf_tgt for v in row], 32, i_lit))
    L.append(c_array("std::int32_t", "kLoopWolfPrev", [v for row in rec.wolf_prev for v in row], 32, i_lit))
    L.append(c_array("std::int64_t", "kLoopStats", [v for row in loop["stats"] for v in row], 12, i64_lit))
    L.append(c_array("std::int32_t", "kLoopTracks", [v for row in loop["tracks"] for v in row], 21, i_lit))
    L.append(c_array("std::int32_t", "kLoopPrevAfter", [v for row in loop["prev_after"] for v in row], 32, i_lit))
    L.append("")

    # 쌍 장면
    P, M, N = len(pairs), pc["M"], pc["N"]
    K = len(pc["discs"])
    L.append("\t// ---- 쌍 장면 (`_step_predators_v3` 의 _fl_pred — 낮 d = 0, 늑대 순번 짝수 잠행·홀수 추격, 은신처 표적 제외·원판 눈길 가림 켬). 늑대 입력 (x, y, hx, hy)·")
    L.append("\t//      (쿨다운, 배부름, 잠행 상태, 남은 수, 잠), 사슴 입력 (x, y)·(행동, HIDE 도착, 은신처 원 안), 장면 시야 배수, 결과 늑대 사냥 가능·쌍 비트 (1 반경 안 ·")
    L.append("\t//      2 반경과 시야각 안 · 4 원판이 가림 · 8 은신처 표적 제외) ----")
    L.append(f"\tinline constexpr std::int32_t kPairScenes = {P};")
    L.append(f"\tinline constexpr std::int32_t kPairWolves = {M};")
    L.append(f"\tinline constexpr std::int32_t kPairPrey = {N};")
    L.append(f"\tinline constexpr double kPairWorldSize = {d_lit(pc['size'])};")
    L.append(f"\tinline constexpr double kPairPredSpeedMult = {d_lit(pc['pred_speed_mult'])};")
    L.append(f"\tinline constexpr std::int32_t kPairEatCd = {pc['eat_cd']};")
    L.append(f"\tinline constexpr std::int32_t kPairSatSteps = {pc['sat_steps']};")
    L.append(f"\tinline constexpr double kPairViewR = {d_lit(pc['view_r'])};")
    L.append(f"\tinline constexpr double kPairFovCos = {d_lit(pc['fov_cos'])};")
    L.append(f"\tinline constexpr double kPairCStill = {d_lit(pc['c_still'])};")
    L.append(c_array("double", "kPairCoverMult", list(pc["cover_mult"]), 4, d_lit))
    L.append(c_array("std::int32_t", "kPairStalker", [int(k == PT_STALKER) for k in pc["kinds"]], 8, i_lit))
    L.append(f"\tinline constexpr std::int32_t kPairDiscCount = {K};")
    L.append(c_array("double", "kPairDiscs", [float(v) for v in pc["discs"].reshape(-1)], 6, d_lit))
    wf, wi, pf, pi, sg, hu, fl = [], [], [], [], [], [], []
    for sc in pairs:
        for m in range(M):
            wf += [sc["q"][m, 0], sc["q"][m, 1], sc["head"][m, 0], sc["head"][m, 1]]
            wi += [int(sc["cd"][m]), int(sc["sat"][m]), int(sc["st"][m]), int(sc["left"][m]), int(sc["asleep"][m])]
            hu.append(int(bool(sc["hunt"][m])))
            for i in range(N):
                fl.append(int(sc["rng"][m, i]) | 2 * int(sc["vis0"][m, i]) | 4 * int(sc["blk"][m, i]) | 8 * int(sc["cov"][m, i]))
        for i in range(N):
            pf += [sc["p"][i, 0], sc["p"][i, 1]]
            pi += [int(sc["beh"][i]), int(sc["arrived"][i]), int(sc["in_cov"][i])]
        sg.append(sc["sight"])
    L.append(c_array("double", "kPairWolfIn", wf, 4, d_lit))
    L.append(c_array("std::int32_t", "kPairWolfInI", wi, 20, i_lit))
    L.append(c_array("double", "kPairPreyIn", pf, 4, d_lit))
    L.append(c_array("std::int32_t", "kPairPreyInI", pi, 24, i_lit))
    L.append(c_array("double", "kPairSight", sg, 6, d_lit))
    L.append(c_array("std::uint8_t", "kPairHunt", hu, 32, i_lit))
    L.append(c_array("std::uint8_t", "kPairFlags", fl, 32, i_lit))
    L.append("}")
    L.append("")
    counts = np.zeros(4, dtype=np.int64)
    for v in fl:
        counts += [(v >> b) & 1 for b in range(4)]
    print(f"짜 맞춘 장면 {len(scenes)} (틱 {sum(len(sc.stats) for sc in scenes)}) · 기준 루프 {LOOP_STEPS} 스텝 (시작 {f['started']}, 스스로 {f['own_n']}, "
          f"끝 까닭 { {c: f['n'][c] for c in FLIGHT_CAUSES if f['n'][c]} }) · 쌍 장면 {P} (반경 안 {counts[0]} · 반경과 시야각 {counts[1]} · "
          f"가림 {counts[2]} · 은신처 {counts[3]} / {len(fl)}, 사냥 못 함 {len(hu) - sum(hu)})")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    text = build_header()
    out = args.out / "FlightGoldenVectorsV3.h"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"썼다: {out} ({len(text.encode('utf-8'))} 바이트)")


if __name__ == "__main__":
    main()
