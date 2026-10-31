"""v3 R1b 세계 개체 논리 골든 내보내기 — Arbiter·제어기·이동·에너지·지각·관측 18 (계약 POLICY_CONTRACT_V3.md 11절).

    # herbivore_rl/ 에서. 언리얼 모듈 폴더에 바로 쓴다
    python export_golden_v3_world.py
    # 시험용 다른 폴더
    python export_golden_v3_world.py --out <폴더>

산출물: AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/RepertoireGoldenVectorsV3.h (네임스페이스 EcoRepertoireV3::Golden)
읽는 쪽: C++ EcoRepertoire.h·EcoObservationV3.h 를 대조하는 Tests/RepertoireGoldenCheckV3.h (UE 자동화 시험
        Tests/EcoRepertoireV3Test.cpp 와 g++ 하네스 tests/cpp/parity_repertoire_v3_main.cpp 가 같은 검사를 부른다),
        파이썬 tests/test_repertoire_golden_v3.py.

골든은 **진짜 세계에서** 뽑는다: configs/v3_r1_on.yaml(R1b 판정·배포 세계)을 R1b 출시 모델(ckpt/v3/v3_r1_g995_s3_20m.zip)의
argmax(env_v2/rollout.py RepLearned, 배포 모드)로 보정 시드 20000~20002 에서 돌리고, 세계가 실제로 부르는 함수
(repertoire.arbitrate·control·perceive·RepState.reset_slots, World._eat·_geometry·_step_predators_v3)를 감싸 들어간 값과 나온 값을
그대로 적는다. 감싸기는 이 프로세스 안에서만이고 env_v2 코드는 바꾸지 않는다. 다시 계산한 값(섭식·에너지·번식·사건 비트·어둠)은
세계 값과 비트 단위로 같은지 확인하고, 다르면 멈춘다. 판정 시드(10000~10019, 10200~10219, 12160~12199)는 쓰지 않는다(쓰면 멈춘다).

묶음 (계약 11-4 의 이름. 일 지시의 번호로는 G3 = Arbiter 열, G4 = 제어기, G-obs = 관측이다):
  0. 세계 상수 표           v3_r1_on.yaml·default.yaml 에서 읽은 계수 → C++ FRepertoireConfig·FObservationConfig 와 하나씩 비교
  1. 지연 해시 (계약 G9)     (시드, 개체 키) → H(505, 시드, 키), 지연. 파리티 키(슬롯·세대)와 통합 모드 키(StableAgentId) 둘 다
  2. Arbiter 열 (계약 G4)    롤아웃 창(개체 하나의 연속 WINDOW 스텝: 시작 상태 + 스텝마다 요청·결정 관측 → 결정 뒤 상태 19칸·
                            결정·전환·사건·사건 결정·사건 비트·rep_peek reads·기상 결정, 스텝 뒤 리스폰) + 손으로 만든 경계 열(잠금 끝,
                            지연 0~3, 겹친 사건, 시야 넓어짐, 도착, HIDE 시간 끝, 리스폰, seq 감김, SLEEP 단위, E7 플래그). 경계 열도
                            진짜 repertoire.arbitrate·tick·reset_slots 로 돈다. 시드마다 몇 창은 관측 18 을 함께 실어 C++ 이
                            Prepare → 마스크 → 망 → Commit 을 닫힌 고리로 돌린다
  3. 리스폰                 Tick 뒤 상태 + (에너지, 어둠, 시드, 키) → reset_slots 뒤 상태
  4. 제어기·이동·에너지 (G5) 결정 뒤 상태 + 제어 입력 → 속도·보행·섭식·대사·탐지·정지·웅크림·heading 덮기·은신 배수, 이동 전후
                            위치·heading, 섭식(셀 나누기 비율은 세계 값을 입력으로)·번식 뒤 에너지. 손으로 만든 사례도 진짜 control
  5. Perceive              recency·away 갱신
  6. 관측 만들기 (G3)        미리 계산한 기하·상태 → 관측 18 (float32, 세계가 낸 관측 그대로)
  7. 지각 스냅샷 (G3)        스텝 끝 기하 입력 전부(초식 128·위협·은신처) → 개체마다 위협·동족·은신처 지각
  8. 낮밤                   (T, 위상, 박명, t) → d, 남은 스텝
  9. 피식 EMA

문턱 근처 제외 (계약 11-2): Arbiter 롤아웃 창은 결정 관측에 |d − 8| < 1e-4, |접근 − 0.9| < 1e-5, |E − 0.25| < 1e-6 이 있으면
고르지 않고, 제어기는 |셀 먹이 − 0.06| < 1e-6 이면 먹이 판정 검사를 빼고, 지각 스냅샷은 개체마다 실거리 대 반경(탐지·사건
비교·동족 20·분리 5·은신 가장자리 0) |d − r| < 1e-4 나 시야각 |cos − 0.5| < 1e-5 이 있으면 그 개체의 검사를 뺀다(배열에는 남긴다).
뺀 수는 헤더 머리에 적는다. 닫힌 고리 창은 요청을 읽는 스텝의 허용 칸 1·2위 로짓 차가 1e-4 보다 작으면 고르지 않는다.

허용: 실수 |C++ − Python| <= 1e-4 (kFloatTolerance), 정수·열거·불은 정확히 같다. 관측 18 은 같은 double 입력이면 비트 단위로 같다.
결정성: 시각·절대 경로를 적지 않는다. 같은 모델·설정·코드면 바이트 단위로 같은 헤더가 나온다(tests/test_repertoire_golden_v3.py).
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import contextlib
import math
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import torch as th

import export_weights_v3 as ew

ROOT = ew.ROOT
UE_POLICY_DIR = ew.UE_POLICY_DIR
HEADER = "RepertoireGoldenVectorsV3.h"
DEFAULT_MODEL = ew.DEFAULT_MODEL          # R1b 출시 모델 (모델 시드 3)
DEFAULT_CONFIG = ew.DEFAULT_CONFIG        # R1 판정·배포 세계 (경보 없음, 관측 18, 마스크 판 2)

GOLDEN_SEEDS = (20000, 20001, 20002)      # 보정 시드 (export_weights_v3 와 같다)
JUDGE_SEED_RANGES = ((10000, 10020), (10200, 10220), (12160, 12200))   # [시작, 끝) — 판정 시드, 쓰지 않는다
EDGE_SEED = 20000                         # 경계 열의 지연 해시 시드
STEPS = 2000
WINDOW = 40                               # Arbiter 창 길이 (스텝)
WINDOW_STRIDE = 10                        # 창 시작 후보 간격
LOOP_WINDOWS_PER_SEED = 2                 # 관측 18 을 싣는 닫힌 고리 창
SELECT_SEED = 7                           # 표본 고르기 난수 (결정적)
CTL_CAP = 5                               # 제어기 범주마다 시드당
OBS_CAP = 2                               # 관측 만들기 범주마다 시드당
PER_CAP = 8                               # Perceive 범주마다 시드당
RESPAWN_CAP = 6                           # 리스폰 시드당
EMA_CAP = 3                               # 피식 EMA (잡힘 있음·없음) 범주마다 시드당
SNAP_EVERY = 50                           # 지각 스냅샷 후보 간격 (시드당 하나를 고른다)
SNAP_OFFSET = 25
FLOAT_TOL = 1e-4                          # 실수 허용 오차 (일 지시)
NEAR_DIST = 1e-4                          # 계약 11-2 문턱 근처
NEAR_COS = 1e-5
NEAR_APPROACH = 1e-5
NEAR_ENERGY = 1e-6
NEAR_FOOD = 1e-6
NO_DIST = 1e300                           # 파이썬 inf (안 보임·은신처 없음) — C++ kNoThreatDist

STATE_FIELDS = ("behavior", "phase", "steps_in", "seq", "lock_left", "startle_left", "waking", "wake_left", "wake_target",
                "wake_ev", "ev_wait", "hide_target", "arrived", "prev_pc", "prev_near", "prev_fast", "prev_low", "prev_dark",
                "jitter")
DOBS_INT = ("pred_count", "pred_count_ev", "in_cover", "cover_k")
DOBS_REAL = ("d_pred_min", "pred_approach", "d_pred_min_ev", "pred_approach_ev", "energy", "dark")
FLAG_DECIDE, FLAG_SWITCH, FLAG_EVENT, FLAG_FIRE, FLAG_E7, FLAG_READS, FLAG_WAKE = 1, 2, 4, 8, 16, 32, 64
EV_BITS = {"e1": 1, "e2": 2, "e3": 4, "e4": 8, "e5": 16, "e6": 32, "e7": 64}
KIND_ROLLOUT, KIND_EDGE = 0, 1
CTL_ROLLOUT, CTL_SYNTH = 0, 1
_F = {f: k for k, f in enumerate(STATE_FIELDS)}

# 창 범주 (차례대로 시드마다 하나씩 고른다)
WINDOW_CATEGORIES = ("reset", "flee", "hide_e6", "hide_in_cover", "hide_timeout", "freeze", "graze_back", "startle",
                     "respawn", "e5", "e4", "e2", "e1", "jitter_wait", "fire_locked", "decide_keep")


# --------------------------------------------------------------------- #
# 작은 도구
# --------------------------------------------------------------------- #


def check_seeds(seeds) -> None:
    for s in seeds:
        for lo, hi in JUDGE_SEED_RANGES:
            if lo <= int(s) < hi:
                raise SystemExit(f"시드 {s} 는 판정 시드 [{lo}, {hi}) 다 — 골든에 쓰지 않는다")


def state_matrix(rs) -> np.ndarray:
    """RepState → (n, 19) int64 (STATE_FIELDS 순서, 불은 0/1)."""
    return np.stack([np.asarray(getattr(rs, f)).astype(np.int64) for f in STATE_FIELDS], 1)


def copy_dict(d: dict) -> dict:
    return {k: (np.array(v, copy=True) if isinstance(v, np.ndarray) else v) for k, v in d.items()}


def sentinel(x) -> np.ndarray:
    """파이썬 inf → NO_DIST (C++ kNoThreatDist). 그 값은 늘 수 > 0 으로 가려 읽는다."""
    x = np.asarray(x, dtype=np.float64)
    return np.where(np.isfinite(x), x, NO_DIST)


def event_bits(pre: np.ndarray, obs: dict, p: dict) -> np.ndarray:
    """사건 비트 (n,) — repertoire.arbitrate a·b 와 같은 식(결정 전 상태 pre 와 결정 관측). 이 값의 OR 가 진짜 arbitrate 의
    event 와 같은지 부르는 쪽이 확인한다(다르면 멈춘다)."""
    from env_v2 import repertoire as rep

    col = {f: pre[:, k] for k, f in enumerate(STATE_FIELDS)}
    pc = np.asarray(obs["pred_count"], dtype=np.int64)
    pce = np.asarray(obs.get("pred_count_ev", pc), dtype=np.int64)
    seen, seen_e = pc > 0, pce > 0
    near_e = seen_e & (np.asarray(obs.get("d_pred_min_ev", obs["d_pred_min"])) < p["event_near"])
    fast_e = seen_e & (np.asarray(obs.get("pred_approach_ev", obs["pred_approach"])) >= p["event_approach"])
    low = np.asarray(obs["energy"]) < p["event_energy"]
    dark = bool(obs["dark"] >= p["event_dark"])
    arrive = (col["behavior"] == rep.HIDE) & (col["arrived"] == 0) & np.asarray(obs["in_cover"], dtype=bool)
    bits = np.zeros(len(pc), dtype=np.int64)
    bits |= np.where(pce > col["prev_pc"], EV_BITS["e1"], 0)
    bits |= np.where((near_e & (col["prev_near"] == 0)) | (fast_e & (col["prev_fast"] == 0)), EV_BITS["e2"], 0)
    bits |= np.where((col["behavior"] == rep.SLEEP) & seen, EV_BITS["e3"], 0)
    bits |= np.where(low & (col["prev_low"] == 0), EV_BITS["e4"], 0)
    bits |= np.where((col["prev_dark"] != 0) != dark, EV_BITS["e5"], 0)
    bits |= np.where(arrive & (col["steps_in"] > 0), EV_BITS["e6"], 0)
    if "alarm_new" in obs:
        e7 = np.asarray(obs["alarm_new"], dtype=bool) & ((col["behavior"] == rep.GRAZE) | (col["behavior"] == rep.SLEEP))
        bits |= np.where(e7, EV_BITS["e7"], 0)
    return bits


def result_flags(res: dict, reads, wake) -> np.ndarray:
    f = np.zeros(len(np.asarray(res["decide"])), dtype=np.int64)
    for key, bit in (("decide", FLAG_DECIDE), ("switch", FLAG_SWITCH), ("event", FLAG_EVENT), ("fire", FLAG_FIRE),
                     ("e7", FLAG_E7)):
        f |= np.where(np.asarray(res[key], dtype=bool), bit, 0)
    f |= np.where(np.asarray(reads, dtype=bool), FLAG_READS, 0)
    f |= np.where(np.asarray(wake, dtype=bool), FLAG_WAKE, 0)
    return f


def peek(rs, p: dict, obs: dict) -> tuple[np.ndarray, np.ndarray]:
    """World.rep_peek 과 같은 미리 보기 (경계 열용 — 세계가 없다): 사본에 지금 행동을 요청으로 arbitrate."""
    from env_v2 import repertoire as rep

    cp = object.__new__(rep.RepState)
    cp.__dict__.update({k: np.array(v, copy=True) for k, v in vars(rs).items()})
    woke = rs.waking & (rs.wake_left <= 0)
    res = rep.arbitrate(cp, p, rs.behavior.astype(np.int64), obs)
    reads = np.asarray(res["decide"], dtype=bool).copy()
    return reads, reads & woke


class Reservoir:
    """범주마다 크기 cap 의 저수지 표본 (결정적 난수). 시간 전체에 고르게 퍼진다."""

    def __init__(self, cap: int, rng: np.random.Generator):
        self.cap, self.rng = cap, rng
        self.items: dict = {}
        self.seen: dict = {}

    def offer(self, cat, make) -> None:
        n = self.seen.get(cat, 0) + 1
        self.seen[cat] = n
        bucket = self.items.setdefault(cat, [])
        if len(bucket) < self.cap:
            bucket.append(make())
        else:
            j = int(self.rng.integers(n))
            if j < self.cap:
                bucket[j] = make()

    def offer_grouped(self, cats: list, make) -> None:
        """개체마다 범주(cats[i])를 받아 범주마다 한 개체를 골라 내놓는다."""
        groups: dict = {}
        for i, c in enumerate(cats):
            groups.setdefault(c, []).append(i)
        for c in sorted(groups, key=repr):
            idx = groups[c]
            i = idx[int(self.rng.integers(len(idx)))]
            self.offer(c, lambda i=i: make(i))

    def all(self) -> list:
        out = []
        for cat in sorted(self.items, key=repr):
            out += self.items[cat]
        return out


# --------------------------------------------------------------------- #
# 롤아웃 (진짜 세계를 감싼다)
# --------------------------------------------------------------------- #


def collect(model, cfg, seed: int, steps: int) -> dict:
    """판정 세계 시드 하나를 R1b argmax 로 돌리며 세계가 실제로 부르는 함수의 입출력을 모은다."""
    from env_v2 import repertoire as rep
    from env_v2.rep_policy import action_mask
    from env_v2.rollout import RepLearned
    from env_v2.world import World, daynight_phase

    w = World(cfg, seeds=[seed])
    pol = RepLearned(model)
    pol.bind_world(w)
    p, N = w._rp, w.N
    rng = np.random.default_rng([SELECT_SEED, int(seed)])
    live = {"on": False}
    cap: dict = {}

    orig_arb, orig_ctl, orig_per = rep.arbitrate, rep.control, rep.perceive
    orig_reset = rep.RepState.reset_slots

    def arb_spy(rs, pp, request, obs):
        if not live["on"]:
            return orig_arb(rs, pp, request, obs)
        cap["pre"] = state_matrix(rs)
        cap["obs"] = copy_dict(obs)
        cap["req"] = np.asarray(request, dtype=np.int64).copy()
        res = orig_arb(rs, pp, request, obs)
        cap["post"] = state_matrix(rs)
        cap["res"] = copy_dict(res)
        return res

    def ctl_spy(rs, pp, inp, c, sp):
        out = orig_ctl(rs, pp, inp, c, sp)
        if live["on"]:
            cap["ctl"] = (rs.away.copy(), copy_dict(inp), copy_dict(out))
        return out

    def per_spy(rs, pp, g, idx=None):
        if live["on"] and idx is None:
            r0, a0 = rs.recency.copy(), rs.away.copy()
            orig_per(rs, pp, g, idx)
            cap["per"] = (r0, a0, np.asarray(g["pred_count"]).copy(), np.asarray(g["away_from_pred"]).copy(),
                          rs.recency.copy(), rs.away.copy())
            return None
        return orig_per(rs, pp, g, idx)

    def reset_spy(self, idx, pp, energy, dark, sd, generations):
        if not live["on"]:
            return orig_reset(self, idx, pp, energy, dark, sd, generations)
        pre = state_matrix(self)[idx]
        orig_reset(self, idx, pp, energy, dark, sd, generations)
        cap["resp"] = (np.asarray(idx).copy(), pre, state_matrix(self)[idx], np.asarray(energy, dtype=np.float64).copy(),
                       float(dark), int(sd), np.asarray(generations).copy())
        return None

    orig_eat = w._eat

    def eat_spy(e_drained, mult=None):
        c = w.cfg
        want = np.clip((c.max_energy - e_drained) / c.food_energy_per_unit, 0.0, c.food_eat_rate)
        if mult is not None:
            want = want * mult
        ix, iy = w._cell_index(w.pos)
        flat = iy * w.gw + ix
        cells = w.gw * w.gw
        demand = np.bincount(flat, weights=want, minlength=cells)
        taken = np.minimum(demand, w.food.reshape(-1))
        frac = np.divide(taken, demand, out=np.zeros(cells), where=demand > 0)
        gain = orig_eat(e_drained, mult)
        if not np.array_equal(gain, want * frac[flat]):
            raise SystemExit("섭식 다시 계산이 World._eat 와 다르다 — 골든 감싸기를 고친다")
        cap["eat"] = (np.asarray(e_drained).copy(), np.asarray(mult).copy(), want, frac[flat].copy(), gain.copy())
        return gain

    orig_pred = w._step_predators_v3

    def pred_spy():
        cap["moved"] = (w.pos.copy(), w.head.copy())
        caught = orig_pred()
        cap["caught"] = np.asarray(caught).copy()
        return caught

    orig_geo = w._geometry
    snaps = []

    def geo_spy(idx=None, out=None):
        if live["on"] and idx is None and cap.get("t", -1) % SNAP_EVERY == SNAP_OFFSET:
            inp = dict(pos=w.pos.copy(), head=w.head.copy(), beh=w._rs.behavior.astype(np.int64).copy(),
                       see=w._rep_see.copy(), see_last=w._rep_see_last.copy(), dark=float(w.dark),
                       see_pred=float(w._see_pred), pred_pos=w.pred_pos.copy(), pred_vel=w.pred_vel.copy(),
                       pred_asleep=w.pred_asleep.copy(), cov_c=w.cov_c.copy(), cov_r=w.cov_r.copy(), t=int(cap["t"]))
            vals = orig_geo(idx, out)
            snaps.append(dict(inp=inp, out=copy_dict(vals)))
            return vals
        return orig_geo(idx, out)

    w._eat, w._step_predators_v3, w._geometry = eat_spy, pred_spy, geo_spy

    T = steps
    rec = dict(req=np.zeros((T, N), np.int64), dint=np.zeros((T, N, 4), np.int64), dreal=np.zeros((T, N, 6)),
               pre=np.zeros((T, N, 19), np.int64), post=np.zeros((T, N, 19), np.int64), flags=np.zeros((T, N), np.int64),
               ev=np.zeros((T, N), np.int64), done=np.zeros((T, N), bool), resp_energy=np.zeros((T, N)),
               resp_dark=np.zeros(T), gen_before=np.zeros((T, N), np.int64), gen_after=np.zeros((T, N), np.int64),
               obs=np.zeros((T, N, 18), np.float32), mask=np.zeros((T, N, 5), bool))
    ctl_res, obs_res = Reservoir(CTL_CAP, rng), Reservoir(OBS_CAP, rng)
    per_res, resp_res, ema_res = Reservoir(PER_CAP, rng), Reservoir(RESPAWN_CAP, rng), Reservoir(EMA_CAP, rng)
    c = w.cfg

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(rep, "arbitrate", arb_spy))
        stack.enter_context(mock.patch.object(rep, "control", ctl_spy))
        stack.enter_context(mock.patch.object(rep, "perceive", per_spy))
        stack.enter_context(mock.patch.object(rep.RepState, "reset_slots", reset_spy))
        for t in range(T):
            obs = np.asarray(w.observe(), dtype=np.float32).copy()
            pk = w.rep_peek()
            a = pol(obs)
            m = pol.last_mask.copy()
            if not np.array_equal(m, action_mask(pk, obs, pol.params, obs_names=w.obs_names)):
                raise SystemExit(f"시드 {seed} 스텝 {t}: RepLearned 마스크가 action_mask 와 다르다")
            g0, rs = w._g, w._rs
            pre_state = state_matrix(rs)
            energy0, cd0, ema0, dark0, tw0 = w.energy.copy(), w.repro_cd.copy(), float(w.pred_ema), float(w.dark), int(w.t)
            gen0 = w._rep_gen.copy()
            d_chk, dn_r = daynight_phase(w.t, w.dn_period, w.dn_offset, w.dn_tw)
            if w.day_fixed or d_chk != w.dark:
                raise SystemExit("판정 세계는 낮 고정이 아니고, 어둠 다시 계산이 세계 값과 같아야 한다")
            ix, iy = w._cell_index(w.pos)
            cell_food0 = w.food[iy, ix].copy()
            cov_edge = w._cover_edge(w.pos)[2].min(1) if len(w.cov_r) else np.full(N, np.inf)
            pos_before, head_before = w.pos.copy(), w.head.copy()
            rs_beh, rs_steps, rs_rec = rs.behavior.copy(), rs.steps_in.copy(), rs.recency.copy()

            # ---- 6. 관측 만들기 (지금 관측 = 직전 스텝 끝 값. 리스폰 행은 다시 계산한 값) ----
            def make_obs(i):
                return dict(food=float(g0["food_density"][i]), pc=int(g0["pred_count"][i]), d=float(g0["d_pred_min"][i]),
                            kin=int(g0["kin_count"][i]), energy=float(energy0[i]), ema=ema0, has_cover=int(len(w.cov_r) > 0),
                            edge=float(cov_edge[i]), dark=dark0, r=int(dn_r), app=float(g0["pred_approach"][i]),
                            kin_alarm=float(g0["kin_alarm"][i]), beh=int(rs_beh[i]), steps_in=int(rs_steps[i]),
                            recency=float(rs_rec[i]), obs=obs[i].copy(), cover_dist=float(g0["cover_dist"][i]),
                            src=(int(seed), tw0, int(i)))

            obs_res.offer_grouped([(int(rs_beh[i]), int(g0["pred_count"][i] > 0), int(g0["kin_alarm"][i] > 0),
                                    int(rs_steps[i] == 0), int(bool(g0["in_cover"][i]))) for i in range(N)], make_obs)

            cap.clear()
            cap["t"] = t
            live["on"] = True
            _, _, done, _ = w.step(a)
            live["on"] = False

            # ---- 2. Arbiter 기록 ----
            if not np.array_equal(cap["req"], a[:, 0].astype(np.int64)) or not np.array_equal(cap["pre"], pre_state):
                raise SystemExit("arbitrate 감싸기 입력이 요청·결정 전 상태와 다르다")
            dobs = cap["obs"]
            reads = np.asarray(pk["reads"], dtype=bool)
            if not np.array_equal(reads, np.asarray(cap["res"]["decide"], dtype=bool)):
                raise SystemExit("rep_peek reads 가 arbitrate decide 와 다르다")
            bits = event_bits(cap["pre"], dobs, p)
            if not np.array_equal(bits != 0, np.asarray(cap["res"]["event"], dtype=bool)):
                raise SystemExit("사건 비트의 OR 가 arbitrate event 와 다르다")
            rec["req"][t] = cap["req"]
            rec["dint"][t] = np.stack([np.asarray(dobs[k]).astype(np.int64) for k in DOBS_INT], 1)
            rec["dreal"][t] = np.stack([sentinel(dobs[k]) if k.startswith("d_") else
                                        np.broadcast_to(np.asarray(dobs[k], dtype=np.float64), (N,)) for k in DOBS_REAL], 1)
            rec["pre"][t], rec["post"][t] = cap["pre"], cap["post"]
            rec["flags"][t] = result_flags(cap["res"], reads, pk["wake_decide"])
            rec["ev"][t] = bits
            rec["done"][t] = done
            rec["gen_before"][t], rec["gen_after"][t] = gen0, w._rep_gen
            rec["obs"][t], rec["mask"][t] = obs, m

            # ---- 3. 리스폰 ----
            if done.any():
                idx, rpre, rpost, ren, rdark, rseed, rgen = cap["resp"]
                rec["resp_energy"][t, idx] = ren
                rec["resp_dark"][t] = rdark
                if not np.array_equal(np.sort(idx), np.flatnonzero(done)):
                    raise SystemExit("리스폰 행이 사망 행과 다르다")
                for k, i in enumerate(idx):
                    resp_res.offer(0, lambda k=k, i=i: dict(pre=rpre[k].copy(), post=rpost[k].copy(), energy=float(ren[k]),
                                                            dark=rdark, seed=rseed, slot=int(i), gen=int(rgen[k])))

            # ---- 4. 제어기·이동·에너지 ----
            away, inp, out = cap["ctl"]
            pos1, head1 = cap["moved"]
            e_dr, mult, want, frac, gain = cap["eat"]
            post = cap["post"]
            e_new = np.minimum(e_dr + gain * c.food_energy_per_unit, c.max_energy)
            cd1 = np.maximum(cd0 - 1, 0)
            repro = (e_new > c.repro_threshold) & (cd1 == 0)
            e_fin = np.where(repro, c.init_energy, e_new)
            cd_fin = np.where(repro, int(c.repro_cd), cd1)
            alive = ~done
            if not np.array_equal(e_fin[alive], w.energy[alive]) or not np.array_equal(cd_fin[alive], w.repro_cd[alive]):
                raise SystemExit("에너지·번식 다시 계산이 세계 값과 다르다")
            cover = rep.cover_mult(p, post[:, _F["behavior"]], out["crouch"])
            has_face = (out["face"] != 0.0).any(1)

            def make_ctl(i):
                return dict(
                    kind=CTL_ROLLOUT,
                    sint=(int(post[i, _F["behavior"]]), int(post[i, _F["startle_left"]]), int(post[i, _F["hide_target"]]),
                          int(post[i, _F["arrived"]])),
                    away=away[i].copy(),
                    vin=np.concatenate([inp["food_grad"][i], inp["to_centroid"][i], inp["separation"][i],
                                        inp["away_from_pred"][i], inp["to_target"][i]]),
                    iin=(int(inp["pred_count"][i]), int(bool(inp["food_ok"][i])), int(bool(inp["in_cover"][i]))),
                    cell_food=float(cell_food0[i]), dark=float(inp["dark"]),
                    vel=out["vel"][i].copy(), gait=int(out["gait"][i]), eat=float(out["eat"][i]),
                    drain=float(out["drain"][i]), see=float(out["see"][i]), still=int(bool(out["still"][i])),
                    crouch=int(bool(out["crouch"][i])), face=out["face"][i].copy(), has_face=int(bool(has_face[i])),
                    cover=float(cover[i]),
                    has_move=1, size=float(w.size), pos0=pos_before[i].copy(), head0=head_before[i].copy(),
                    pos1=pos1[i].copy(), head1=head1[i].copy(),
                    has_energy=1, e0=float(energy0[i]), cd0=int(cd0[i]), e_dr=float(e_dr[i]), mult=float(mult[i]),
                    want=float(want[i]), frac=float(frac[i]), gain=float(gain[i]), e_new=float(e_new[i]),
                    e_fin=float(e_fin[i]), cd_fin=int(cd_fin[i]), repro=int(bool(repro[i])), src=(int(seed), tw0, int(i)))

            ctl_res.offer_grouped(
                [(int(post[i, 0]), int(out["gait"][i]), int(bool(out["crouch"][i])),
                  int(bool(has_face[i]) or post[i, _F["startle_left"]] > 0),
                  int(bool(inp["food_ok"][i])) if post[i, 0] == rep.GRAZE else int(inp["pred_count"][i] > 0),
                  int(bool(repro[i]))) for i in range(N)], make_ctl)

            # ---- 5. Perceive ----
            r0, a0, pcs, afp, r1, a1 = cap["per"]
            per_res.offer_grouped([0 if pcs[i] > 0 else (1 if r0[i] > 0 else 2) for i in range(N)],
                                  lambda i: dict(r0=float(r0[i]), a0=a0[i].copy(), pc=int(pcs[i]), afp=afp[i].copy(),
                                                 r1=float(r1[i]), a1=a1[i].copy()))

            # ---- 9. 피식 EMA ----
            n_caught = int(np.count_nonzero(cap["caught"]))
            ema1 = float(w.pred_ema)
            ema_res.offer(int(n_caught > 0), lambda: dict(ema0=ema0, caught=n_caught, n=N, ema1=ema1))

    return dict(seed=int(seed), N=N, size=float(w.size), rec=rec, ctl=ctl_res.all(), obs=obs_res.all(), per=per_res.all(),
                resp=resp_res.all(), ema=ema_res.all(), snaps=snaps, params=p,
                period=int(w.dn_period), offset=int(w.dn_offset), tw=int(w.dn_tw))


# --------------------------------------------------------------------- #
# Arbiter 창 고르기
# --------------------------------------------------------------------- #


def near_threshold_steps(rec: dict, p: dict) -> np.ndarray:
    """결정 관측이 사건 문턱 근처인 (스텝, 개체) (계약 11-2: 8·0.9·0.25)."""
    pc, pce = rec["dint"][..., 0], rec["dint"][..., 1]
    d, app, de, appe, en = (rec["dreal"][..., k] for k in range(5))
    near = (pc > 0) & ((np.abs(d - p["event_near"]) < NEAR_DIST) | (np.abs(app - p["event_approach"]) < NEAR_APPROACH))
    near |= (pce > 0) & ((np.abs(de - p["event_near"]) < NEAR_DIST) | (np.abs(appe - p["event_approach"]) < NEAR_APPROACH))
    near |= np.abs(en - p["event_energy"]) < NEAR_ENERGY
    return near


def window_occurrences(rec: dict) -> dict:
    """범주별 (T, N) 일어남 표."""
    from env_v2 import repertoire as rep

    pre, post, flags, ev, done = rec["pre"], rec["post"], rec["flags"], rec["ev"], rec["done"]
    beh = post[..., _F["behavior"]]
    sw = (flags & FLAG_SWITCH) != 0
    dec = (flags & FLAG_DECIDE) != 0
    fire = (flags & FLAG_FIRE) != 0
    event = (flags & FLAG_EVENT) != 0
    return {
        "flee": sw & (beh == rep.FLEE),
        "hide_e6": (ev & EV_BITS["e6"]) != 0,
        "hide_in_cover": sw & (beh == rep.HIDE) & (post[..., _F["arrived"]] == 1),
        "hide_timeout": (beh == rep.HIDE) & (post[..., _F["arrived"]] == 0) & (pre[..., _F["lock_left"]] <= 0) & dec,
        "freeze": sw & (beh == rep.FREEZE),
        "graze_back": sw & (beh == rep.GRAZE),
        "startle": sw & (post[..., _F["startle_left"]] > 0),
        "respawn": done,
        "e5": (ev & EV_BITS["e5"]) != 0,
        "e4": (ev & EV_BITS["e4"]) != 0,
        "e2": (ev & EV_BITS["e2"]) != 0,
        "e1": (ev & EV_BITS["e1"]) != 0,
        "jitter_wait": event & ~fire,
        "fire_locked": fire & (pre[..., _F["lock_left"]] > 0),
        "decide_keep": dec & ~sw & fire,
    }


def window_counts(occ: np.ndarray, t0s: np.ndarray, span: int) -> np.ndarray:
    """(len(t0s), N) — [t0, t0 + span) 안의 일어남 수."""
    cs = np.concatenate([np.zeros((1, occ.shape[1]), np.int64), np.cumsum(occ.astype(np.int64), 0)])
    return cs[t0s + span] - cs[t0s]


def select_windows(col: dict, model, rng: np.random.Generator) -> tuple[list, dict]:
    """시드 하나의 창: 범주마다 하나 (문턱 근처 창 제외, 같은 개체의 창은 겹치지 않는다). 앞 창 몇 개는 닫힌 고리."""
    from env_v2.rep_policy import policy_obs

    rec, p = col["rec"], col["params"]
    T, N = rec["req"].shape
    t0s = np.arange(0, T - WINDOW + 1, WINDOW_STRIDE)
    near = window_counts(near_threshold_steps(rec, p), t0s, WINDOW) > 0         # (C, N)
    stats = {"candidates": int(near.size), "near_excluded": int(near.sum())}
    occ = window_occurrences(rec)
    taken: dict = {}

    def free(i, t0):
        return all(t0 + WINDOW <= a or b <= t0 for a, b in taken.get(i, []))

    chosen = []
    for cat in WINDOW_CATEGORIES:
        if cat == "reset":
            ok = ~near[0]
            sw = ((rec["flags"][:WINDOW] & FLAG_SWITCH) != 0).sum(0)
            cand = [(0, i) for i in np.flatnonzero(ok)]
            if cand:
                best = max(cand, key=lambda x: (sw[x[1]], -x[1]))
                chosen.append((cat, best[1], 0))
                taken.setdefault(best[1], []).append((0, WINDOW))
            continue
        span = WINDOW - 1 if cat == "respawn" else WINDOW      # 리스폰 뒤 스텝이 창 안에 남게
        has = (window_counts(occ[cat], t0s, span) > 0) & ~near
        cand = [(int(t0s[c]), int(i)) for c, i in zip(*np.nonzero(has)) if free(int(i), int(t0s[c]))]
        if not cand:
            continue
        t0, i = cand[int(rng.integers(len(cand)))]
        chosen.append((cat, i, t0))
        taken.setdefault(i, []).append((t0, t0 + WINDOW))

    # 닫힌 고리: 요청을 읽는 다중 칸 스텝에 망 근접 동점이 없는 창
    loops, loop_rejected = set(), 0
    for k, (cat, i, t0) in enumerate(chosen):
        if len(loops) >= LOOP_WINDOWS_PER_SEED:
            break
        sl = slice(t0, t0 + WINDOW)
        obs, mask = rec["obs"][sl, i], rec["mask"][sl, i]
        logits, act = ew.torch_logits(model.policy, policy_obs(obs, mask))
        if not np.array_equal(act, rec["req"][sl, i]):
            raise SystemExit("닫힌 고리 창의 argmax 가 롤아웃 요청과 다르다")
        reads = (rec["flags"][sl, i] & FLAG_READS) != 0
        gap = ew.top_gap(logits, mask)
        if np.any(reads & (gap < ew.NEAR_TIE_GAP)):
            loop_rejected += 1
            continue
        loops.add(k)
    stats["loop_near_tie_rejected"] = loop_rejected
    out = []
    for k, (cat, i, t0) in enumerate(chosen):
        out.append(dict(cat=cat, agent=i, t0=t0, loop=k in loops))
    return out, stats


def rollout_sequence(col: dict, win: dict) -> dict:
    rec, i, t0 = col["rec"], win["agent"], win["t0"]
    sl = slice(t0, t0 + WINDOW)
    steps = []
    for t in range(t0, t0 + WINDOW):
        steps.append(dict(req=int(rec["req"][t, i]), dint=rec["dint"][t, i].copy(), dreal=rec["dreal"][t, i].copy(),
                          alarm=0, flags=int(rec["flags"][t, i]), ev=int(rec["ev"][t, i]), post=rec["post"][t, i].copy(),
                          resp=int(rec["done"][t, i]), resp_energy=float(rec["resp_energy"][t, i]) if rec["done"][t, i] else 0.0,
                          resp_dark=float(rec["resp_dark"][t]) if rec["done"][t, i] else 0.0,
                          resp_gen=int(rec["gen_after"][t, i]) if rec["done"][t, i] else 0))
    fresh = t0 == 0
    return dict(kind=KIND_ROLLOUT, name=win["cat"], alarm=0, fresh=int(fresh),
                init_energy=float(rec["dreal"][0, i, 4]) if fresh else 0.0,
                init_dark=float(rec["dreal"][0, i, 5]) if fresh else 0.0,
                seed=col["seed"], slot=int(i), gen=int(rec["gen_before"][t0, i]), src=(col["seed"], int(t0), int(i)),
                init=rec["pre"][t0, i].copy(), steps=steps,
                loop_obs=rec["obs"][sl, i].copy() if win["loop"] else None)


# --------------------------------------------------------------------- #
# 경계 열 (진짜 repertoire 함수로 돌린다)
# --------------------------------------------------------------------- #


def _o(pc=0, d=math.inf, app=0.5, pce=None, de=None, appe=None, energy=0.5, dark=0.0, in_cover=False, cover_k=-1,
       alarm=None) -> dict:
    """결정 관측 하나 (개체 1). *_ev 를 주지 않으면 실제 시야 값과 같다."""
    if pce is None:
        pce = pc
    if de is None:
        de = d if pce > 0 else math.inf
    if appe is None:
        appe = app if pce > 0 else 0.5
    o = dict(pred_count=np.array([pc], dtype=np.int64), d_pred_min=np.array([float(d)]),
             pred_approach=np.array([float(app)]), pred_count_ev=np.array([pce], dtype=np.int64),
             d_pred_min_ev=np.array([float(de)]), pred_approach_ev=np.array([float(appe)]),
             energy=np.array([float(energy)]), dark=float(dark), in_cover=np.array([bool(in_cover)]),
             cover_k=np.array([int(cover_k)], dtype=np.int64))
    if alarm is not None:
        o["alarm_new"] = np.array([bool(alarm)])
    return o


def edge_specs() -> list:
    """(이름, 시작 에너지, 시작 어둠, 상태 덮기, E7 켬, 스텝 [(요청, 결정 관측, 리스폰 (E, d) 또는 None)])."""
    G, F, H, Z, S = 0, 1, 2, 3, 4
    q = _o()
    seqs = []
    # 1. 잠금 끝: GRAZE 12 뒤 FLEE(놀람 3), FLEE 8 뒤 GRAZE
    seqs.append(("lock_expiry", 0.5, 0.0, {}, False, [(F, q, None)] * 16 + [(G, q, None)] * 10))
    # 2. 사건 지연 0~3: 스텝 3 에 E1, 잠금 중 사건 결정으로 FREEZE
    for j in range(4):
        st = [(Z, q, None)] * 3 + [(Z, _o(pc=1, d=15.0), None)] * 7
        seqs.append((f"event_jitter_{j}", 0.5, 0.0, {"jitter": j}, False, st))
    # 3. 대기 중 사건 (다시 걸지 않는다) → HIDE(목표 2), 도착 E6 → 지연 → GRAZE
    st = [(H, q, None)] * 2 + [(H, _o(pc=1, d=12.0), None), (H, _o(pc=1, d=7.0), None)]
    st += [(H, _o(pc=1, d=7.0, cover_k=2), None)] * 4
    st += [(G, _o(pc=1, d=7.0, in_cover=True, cover_k=2), None)] * 8
    seqs.append(("event_while_waiting", 0.5, 0.0, {"jitter": 3}, False, st))
    # 4. 한 스텝에 E1·E2(가까움·빠름)·E4·E5 함께, 그다음 어둠이 반대로 지남
    st = [(F, _o(energy=0.3, dark=0.45), None)] * 3
    st += [(F, _o(pc=2, d=5.0, app=0.95, energy=0.24, dark=0.5), None)]
    st += [(F, _o(pc=2, d=4.0, app=0.95, energy=0.23, dark=0.52), None)] * 6
    st += [(G, _o(pc=0, energy=0.23, dark=0.49), None)] * 4
    seqs.append(("simultaneous_events", 0.3, 0.45, {}, False, st))
    # 5. 시야 넓어짐: 실제 시야에만 보인 위협은 사건이 아니고 기준값에만 들어간다
    st = [(Z, q, None)] * 2
    st += [(Z, _o(pc=1, d=6.0, pce=0), None), (Z, _o(pc=1, d=6.0, pce=1, de=6.0), None),
           (Z, _o(pc=2, d=6.0, pce=1, de=6.0), None), (Z, _o(pc=1, d=6.0, pce=1, de=6.0), None), (Z, q, None), (Z, q, None),
           (Z, _o(pc=1, d=9.0), None), (Z, _o(pc=1, d=9.0, app=0.9), None), (Z, _o(pc=1, d=9.0, app=0.89), None),
           (Z, _o(pc=1, d=7.999), None)]
    seqs.append(("view_widening", 0.5, 0.0, {}, False, st))
    # 6. 에너지 0.25 경계 (0.25 는 낮지 않다), 잠금 끝 뒤 같은 요청은 다시 잠그지 않는다
    st = [(G, _o(energy=e), None) for e in (0.26, 0.25, 0.2499, 0.24, 0.26, 0.24, 0.25, 0.2, 0.3, 0.1)]
    seqs.append(("energy_low", 0.26, 0.0, {"lock_left": 2}, False, st))
    # 7. 어둠 0.5 경계 (0.5 는 어둠 쪽, 양방향)
    st = [(G, _o(dark=dk), None) for dk in (0.48888888888888893, 0.5, 0.5111111111111111, 0.5, 0.48888888888888893, 0.5)]
    seqs.append(("dark_cross", 0.5, 0.47, {}, False, st))
    # 8. 은신처 안에서 HIDE → 곧바로 도착(잠금 12, E6 없음), 잠금 끝에 GRAZE
    st = [(H, _o(in_cover=True, cover_k=1), None)] * 12 + [(G, _o(in_cover=True, cover_k=1), None)] * 3
    seqs.append(("hide_immediate", 0.5, 0.0, {"lock_left": 0}, False, st))
    # 9. HIDE 시간 끝(40) 뒤 같은 요청으로 계속 가고, 늦게 도착(E6) → 지연 뒤 GRAZE
    st = [(H, _o(cover_k=3), None)] * 44 + [(H, _o(in_cover=True, cover_k=3), None)]
    st += [(G, _o(in_cover=True, cover_k=3), None)] * 6
    seqs.append(("hide_travel_timeout", 0.5, 0.0, {"lock_left": 0}, False, st))
    # 10. FREEZE → FLEE 는 놀람이 없고, GRAZE → FLEE 는 놀람 3
    st = [(Z, _o(pc=1, d=10.0), None)] * 12 + [(F, _o(pc=1, d=10.0), None)] * 8 + [(G, q, None)] * 12
    st += [(F, _o(pc=1, d=10.0), None)] * 6
    seqs.append(("flee_startle", 0.5, 0.0, {"lock_left": 0}, False, st))
    # 11. 리스폰 두 번 (seq + 1, 세대 + 1 로 지연 다시)
    st = [(F, q, None)] * 3 + [(F, q, (0.5, 0.3))] + [(F, _o(dark=0.3), None)] * 13 + [(F, _o(dark=0.3), (0.5, 0.6))]
    st += [(F, _o(dark=0.6), None)] * 3
    seqs.append(("respawn_twice", 0.5, 0.0, {}, False, st))
    # 12. seq 감김 (255 → 0)
    seqs.append(("seq_wrap", 0.5, 0.0, {"seq": 255, "lock_left": 0}, False, [(F, q, None)] * 3))
    # 13. SLEEP 단위 (두 두뇌에서 쓰이지 않지만 분기는 계약이다): 진입·E3·기상 중 사건 → 기상 결정, 사건 없는 기상
    st = [(S, q, None)] * 5 + [(S, _o(pc=1, d=12.0), None)] * 6 + [(G, _o(pc=1, d=12.0), None)] * 2
    st += [(G, _o(pc=2, d=11.0), None)] + [(F, _o(pc=2, d=11.0), None)] * 4 + [(G, q, None)] * 10
    st += [(S, q, None)] * 80 + [(G, q, None)] * 2 + [(S, q, None)] * 6
    seqs.append(("sleep_unit", 0.5, 0.0, {"lock_left": 0}, False, st))
    # 14. E7 (bKinAlarmEvent 켬 — R1b 세계는 끈다): GRAZE 는 사건, FREEZE 는 사건이 아니다
    st = [(Z, _o(alarm=False), None)] * 2 + [(Z, _o(alarm=True), None)] + [(Z, _o(alarm=False), None)] * 4
    st += [(Z, _o(alarm=True), None)] + [(G, _o(alarm=True), None)] * 6
    seqs.append(("kin_alarm_e7", 0.5, 0.0, {"jitter": 1}, True, st))
    # 15. 은신처가 없는 세계의 HIDE (목표 −1, 도착 없음)
    seqs.append(("hide_no_cover", 0.5, 0.0, {"lock_left": 0}, False, [(H, _o(pc=1, d=9.0), None)] * 4))
    return seqs


def edge_sequences(p: dict, seed: int) -> list:
    from env_v2 import repertoire as rep

    out = []
    for k, (name, e0, d0, over, alarm, steps) in enumerate(edge_specs()):
        rs = rep.RepState(1, p, np.array([e0]), d0, seed)
        for key, v in over.items():
            getattr(rs, key)[0] = v
        gen = 0
        init = state_matrix(rs)[0]
        recs = []
        for req, o, resp in steps:
            if ("alarm_new" in o) != alarm:
                raise SystemExit(f"경계 열 {name}: E7 입력과 플래그가 맞지 않는다")
            reads, wake = peek(rs, p, o)
            pre = state_matrix(rs)
            res = rep.arbitrate(rs, p, np.array([req], dtype=np.int64), o)
            bits = event_bits(pre, o, p)
            if not np.array_equal(bits != 0, np.asarray(res["event"], dtype=bool)):
                raise SystemExit(f"경계 열 {name}: 사건 비트가 arbitrate 와 다르다")
            post = state_matrix(rs)[0]
            rep.tick(rs)
            r_e = r_d = 0.0
            if resp is not None:
                gen += 1
                r_e, r_d = resp
                rs.reset_slots(np.array([0]), p, np.array([r_e]), r_d, seed, np.array([gen]))
            recs.append(dict(req=int(req), dint=np.array([int(o[f][0]) for f in DOBS_INT], dtype=np.int64),
                             dreal=np.array([float(sentinel(o[f])[0]) if f.startswith("d_") else float(np.asarray(o[f]).reshape(-1)[0])
                                             for f in DOBS_REAL]),
                             alarm=int(bool(o.get("alarm_new", [False])[0])), flags=int(result_flags(res, reads, wake)[0]),
                             ev=int(bits[0]), post=post, resp=int(resp is not None), resp_energy=float(r_e),
                             resp_dark=float(r_d), resp_gen=gen if resp is not None else 0))
        out.append(dict(kind=KIND_EDGE, name=name, alarm=int(alarm), fresh=int(not over), init_energy=float(e0),
                        init_dark=float(d0), seed=int(seed), slot=0, gen=0, src=(-1, k, 0), init=init, steps=recs,
                        loop_obs=None))
    return out


# --------------------------------------------------------------------- #
# 제어기 손 사례·해시·낮밤·상수
# --------------------------------------------------------------------- #


def control_synthetic(cfg, p: dict) -> list:
    """손으로 만든 제어기 사례 — 진짜 repertoire.control 로 낸다(방향 없음, 목표 없음, A 없음, SLEEP 휴식 할인 등)."""
    from env_v2 import repertoire as rep
    from env_v2.features import features_of
    from env_v2.world import _speed_params

    sp = _speed_params(features_of(cfg).params("speed"))
    z, ex, ey, diag = [0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.6, -0.8]
    # (행동, 놀람, 목표, 도착, 상태 away, 먹이 기울기, 무리, 분리, 위협 반대, 목표 쪽, 위협 수, 먹이 충분, 은신처 안, 어둠)
    rows = [
        (0, 0, -1, 0, z, z, z, z, z, z, 0, 0, 0, 0.0),            # GRAZE 방향 없음 → 정지·섭식 1.0
        (0, 0, -1, 0, z, ex, ey, [0.2, 0.1], z, z, 0, 0, 0, 0.3),  # GRAZE 걷기
        (2, 0, -1, 0, z, ex, ey, z, z, z, 1, 0, 0, 0.0),          # HIDE 목표 없음 → 정지
        (3, 0, -1, 0, z, ex, ey, z, z, z, 0, 0, 0, 0.0),          # FREEZE A 없음 → heading 그대로
        (3, 0, -1, 0, diag, ex, ey, z, z, z, 0, 0, 0, 0.0),       # FREEZE 기억한 A → −A
        (3, 0, -1, 0, diag, ex, ey, z, ey, z, 1, 0, 1, 0.8),      # FREEZE 보이는 위협 A
        (4, 0, -1, 0, z, ex, ey, z, z, z, 0, 0, 1, 0.7),          # SLEEP 은신처 안 → 대사 × (1 − 0.6·d)
        (4, 0, -1, 0, z, ex, ey, z, z, z, 0, 0, 0, 0.7),          # SLEEP 밖
        (1, 0, -1, 0, ex, ey, z, z, z, z, 0, 0, 0, 0.0),          # FLEE 안 보임 → 기억 A 로 뛰기
        (1, 2, -1, 0, ex, ey, z, z, ey, z, 1, 0, 0, 0.0),         # FLEE 놀람 → 정지
        (1, 0, -1, 0, z, z, z, z, z, z, 0, 0, 0, 0.0),            # FLEE 방향 없음 → 정지
        (2, 0, 1, 1, z, ex, ey, ex, ey, ex, 1, 0, 1, 0.2),        # HIDE 도착 → 웅크림
        (2, 0, 1, 0, z, ex, ey, [0.1, 0.0], ey, diag, 1, 0, 0, 0.0),   # HIDE 가는 중, 보임 → 뛰기
        (2, 0, 1, 0, z, ex, ey, z, z, diag, 0, 0, 0, 0.0),        # HIDE 가는 중, 안 보임 → 걷기
        (0, 0, -1, 0, z, ex, z, z, z, z, 1, 1, 1, 0.0),           # GRAZE 먹이 충분 → 정지, 은신 1.5
    ]
    n = len(rows)
    rs = rep.RepState(n, p, np.full(n, 0.5), 0.0, EDGE_SEED)
    rs.behavior = np.array([r[0] for r in rows], dtype=np.int8)
    rs.startle_left = np.array([r[1] for r in rows], dtype=np.int64)
    rs.hide_target = np.array([r[2] for r in rows], dtype=np.int64)
    rs.arrived = np.array([bool(r[3]) for r in rows])
    rs.away = np.array([r[4] for r in rows], dtype=np.float64)
    vec = lambda k: np.array([r[k] for r in rows], dtype=np.float64)    # noqa: E731
    inp = dict(food_grad=vec(5), to_centroid=vec(6), separation=vec(7), away_from_pred=vec(8), to_target=vec(9),
               pred_count=np.array([r[10] for r in rows], dtype=np.int64), food_ok=np.array([bool(r[11]) for r in rows]),
               in_cover=np.array([bool(r[12]) for r in rows]))
    out_all = []
    for k, r in enumerate(rows):            # 어둠이 스칼라라 행마다 부른다
        one = {key: v[k:k + 1] for key, v in inp.items()}
        one["dark"] = r[13]
        rk = object.__new__(rep.RepState)
        rk.__dict__.update({key: np.array(v[k:k + 1], copy=True) for key, v in vars(rs).items()})
        out = rep.control(rk, p, one, cfg, sp)
        cover = rep.cover_mult(p, rk.behavior, out["crouch"])
        out_all.append(dict(
            kind=CTL_SYNTH, sint=(r[0], r[1], r[2], r[3]), away=np.array(r[4], dtype=np.float64),
            vin=np.concatenate([np.array(r[j], dtype=np.float64) for j in range(5, 10)]), iin=(r[10], r[11], r[12]),
            cell_food=-1.0, dark=float(r[13]), vel=out["vel"][0].copy(), gait=int(out["gait"][0]), eat=float(out["eat"][0]),
            drain=float(out["drain"][0]), see=float(out["see"][0]), still=int(bool(out["still"][0])),
            crouch=int(bool(out["crouch"][0])), face=out["face"][0].copy(), has_face=int(bool((out["face"][0] != 0).any())),
            cover=float(cover[0]), has_move=0, size=0.0, pos0=np.zeros(2), head0=np.zeros(2), pos1=np.zeros(2),
            head1=np.zeros(2), has_energy=0, e0=0.0, cd0=0, e_dr=0.0, mult=0.0, want=0.0, frac=0.0, gain=0.0, e_new=0.0,
            e_fin=0.0, cd_fin=0, repro=0, src=(-1, k, 0)))
    return out_all


def hash_rows() -> list:
    from env_v2.repertoire import agent_keys, decision_jitter, mix_chain, JITTER_TAG

    rows = []
    pairs = [(0, 0), (1, 0), (2, 0), (3, 0), (7, 0), (5, 3), (127, 0), (127, 1), (4096, 2 ** 32 - 1)]
    for seed in (20000, 20001, 20002, 0, -1, 2 ** 62 + 12345):
        for slot, gen in pairs:
            key = int(agent_keys([slot], [gen])[0])
            h = int(mix_chain(JITTER_TAG, np.int64(seed), np.uint64(key)))
            j = int(decision_jitter(seed, [slot], np.array([gen], dtype=np.int64), 3)[0])
            if j != h % 4:
                raise SystemExit("지연 해시 확인 실패")
            rows.append(dict(seed=seed, key=key, h=h, j=j, slot=slot, gen=gen))
        for stable in (1, 42, 123456789012, 2 ** 40 + 7):       # 통합 모드 키 (StableAgentId)
            h = int(mix_chain(JITTER_TAG, np.int64(seed), np.uint64(stable)))
            rows.append(dict(seed=seed, key=stable, h=h, j=h % 4, slot=-1, gen=-1))
    return rows


def daynight_rows(cols: list) -> list:
    from env_v2.world import daynight_phase

    rows = []
    for t in (0, 1, 45, 449, 450, 451, 495, 899, 900, 1349):     # 계약 7-6 확인값 (T 900, o 0)
        d, r = daynight_phase(t, 900, 0, 45)
        rows.append((t, 900, 0, 45, d, r))
    for col in cols:
        T, o, tw = col["period"], col["offset"], col["tw"]
        for t in (0, 1, T // 2 - o % (T // 2), T // 2 - 1, T // 2, T - 1, T, 2 * T + 7, 1999, 123457):
            d, r = daynight_phase(t, T, o, tw)
            rows.append((int(t), T, o, tw, d, r))
    for T, tw in ((600, 30), (1800, 90)):
        for t in (0, 15, 29, 30, 31, T // 2 - 1, T // 2, T // 2 + 30, T - 1):
            d, r = daynight_phase(t, T, 0, tw)
            rows.append((int(t), T, 0, tw, d, r))
    return rows


def world_constants(cfg, p: dict) -> list:
    """(이름, 값) — C++ 상수와 하나씩 비교한다. 이름은 파이썬 키 그대로(C++ 시험이 이름으로 짝짓는다)."""
    from env_v2 import repertoire as rep
    from env_v2.features import features_of
    from env_v2.world import _daynight_params, _speed_params

    f = features_of(cfg)
    sp = _speed_params(f.params("speed"))
    dn = _daynight_params(f.params("daynight"), f)
    out = []
    for k in ("lock_graze", "lock_flee", "lock_freeze", "lock_hide", "hide_travel_max", "sleep_enter", "sleep_hold",
              "sleep_wake", "startle_steps", "decision_jitter", "event_near", "event_approach", "event_energy", "event_dark",
              "recency_decay", "graze_head_down", "sleep_sight", "graze_forage", "graze_cohesion", "graze_eat_min",
              "sleep_rest", "cover_mult_crouch", "cover_mult_graze", "cover_mult_sleep", "cover_mult_other", "c_still",
              "steps_norm"):
        out.append((k, float(p[k])))
    for k in ("sep_weight", "flee_weight", "herb_speed", "energy_drain", "max_energy", "init_energy", "food_eat_rate",
              "food_energy_per_unit", "repro_threshold", "repro_cd", "see_r", "obs_pred_count_norm", "obs_kin_count_norm",
              "obs_cover_norm", "sep_radius", "predation_ema_decay", "predation_ema_gain", "grid_unit_cm"):
        out.append((k, float(getattr(cfg, k))))
    out.append(("fov_cos", float(cfg.fov_cos)))
    out.append(("step_seconds", float(cfg.policy_interval) / 60.0))
    for g in range(3):
        out.append((f"gait_speed_{g}", float(sp["speed"][g])))
        out.append((f"gait_eat_{g}", float(sp["eat"][g])))
        out.append((f"drain_mult_{g}", float(sp["drain_mult"][g])))
    out += [("c_rest", sp["c_rest"]), ("c_move", sp["c_move"])]
    out += [("detect_night", dn["detect_night"]), ("eat_night", dn["eat_night"]), ("transition_norm", dn["transition_norm"])]
    out += [("jitter_tag", float(rep.JITTER_TAG)), ("seq_mod", float(rep.SEQ_MOD)), ("eps", 1e-9),
            ("alarm_event", float(f.enabled("alarm"))), ("obs_dim", float(len(ew_obs_names(cfg))))]
    return out


def ew_obs_names(cfg) -> tuple:
    from env_v2.world import obs_names

    return tuple(obs_names(cfg))


# --------------------------------------------------------------------- #
# 지각 스냅샷
# --------------------------------------------------------------------- #


def asleep_hidden(inp: dict) -> int:
    """자고 있어서 안 보이는 (초식, 위협) 쌍 — 깨어 있었다면 탐지 반경·시야각 안이다."""
    if not inp["pred_asleep"].any():
        return 0
    ex = inp["pred_pos"][None, :, 0] - inp["pos"][:, None, 0]
    ey = inp["pred_pos"][None, :, 1] - inp["pos"][:, None, 1]
    pd = np.sqrt(ex * ex + ey * ey)
    cs = (ex * inp["head"][:, None, 0] + ey * inp["head"][:, None, 1]) / np.maximum(pd, 1e-9)
    vis = (pd <= inp["see_pred"] * inp["see"][:, None]) & (cs >= 0.5)
    return int((vis & inp["pred_asleep"][None, :]).sum())


def pick_snapshot(col: dict) -> dict:
    """후보 중 사건 비교 시야가 실제 시야와 다른 개체(행동 시야 배수가 바뀐 띠의 위협)와 자서 안 보이는 위협이 많고, 위협이
    보이고 동족 경보가 있는 개체가 많은 스텝 하나. 10-22: 띠와 자서 안 보이는 위협이 둘 다 있는 스텝을 먼저 고른다(동족 차례 합으로 롤아웃이
    바뀐 뒤 점수만으로는 세 시드 모두 자는 위협이 없는 스텝을 골라 골든이 그 지각 경우를 잃었다). 그런 스텝이 없으면 점수 그대로."""
    best, score = None, (False, -1)
    for s in col["snaps"]:
        o = s["out"]
        band = int((np.asarray(o["pred_count"]) != np.asarray(o["pred_count_ev"])).sum())
        hid = asleep_hidden(s["inp"])
        sc = (band > 0 and hid > 0, 100 * band + 10 * hid + int((np.asarray(o["pred_count"]) > 0).sum())
              + int((np.asarray(o["kin_alarm"]) > 0).sum()))
        if sc > score:
            best, score = s, sc
    if best is None:
        raise SystemExit(f"시드 {col['seed']}: 지각 스냅샷이 없다")
    return best


def snapshot_case(col: dict, snap: dict, cfg) -> dict:
    """스냅샷 하나 → 입력·기대값과 개체별 문턱 근처 검사 칸."""
    inp, out = snap["inp"], snap["out"]
    pos, head, see, see_last = inp["pos"], inp["head"], inp["see"], inp["see_last"]
    N = len(pos)
    fov = cfg.fov_cos
    sp = inp["see_pred"]
    check = np.ones(N, dtype=bool)
    edge = np.full(N, np.inf)
    for i in range(N):
        P, Hd = pos[i], head[i]
        ex, ey = inp["pred_pos"][:, 0] - P[0], inp["pred_pos"][:, 1] - P[1]
        pd = np.sqrt(ex * ex + ey * ey)
        cs = (ex * Hd[0] + ey * Hd[1]) * (1.0 / np.maximum(pd, 1e-9))
        awake = ~inp["pred_asleep"]
        r_see, r_ev = sp * see[i], sp * np.minimum(see[i], see_last[i])
        bad = awake & ((np.abs(pd - r_see) < NEAR_DIST) | (np.abs(pd - r_ev) < NEAR_DIST)
                       | ((np.abs(cs - fov) < NEAR_COS) & (pd <= r_see + NEAR_DIST)))
        dx, dy = pos[:, 0] - P[0], pos[:, 1] - P[1]
        dist = np.sqrt(dx * dx + dy * dy)
        kc = (dx * Hd[0] + dy * Hd[1]) * (1.0 / np.maximum(dist, 1e-9))
        other = np.arange(N) != i
        kbad = other & ((np.abs(dist - cfg.see_r) < NEAR_DIST) | (np.abs(dist - cfg.sep_radius) < NEAR_DIST)
                        | ((np.abs(kc - fov) < NEAR_COS) & (dist <= cfg.see_r + NEAR_DIST)))
        if len(inp["cov_r"]):
            cdx, cdy = inp["cov_c"][:, 0] - P[0], inp["cov_c"][:, 1] - P[1]
            e = np.sqrt(cdx * cdx + cdy * cdy) - inp["cov_r"]
            edge[i] = e.min()
            cbad = abs(edge[i]) < NEAR_DIST
        else:
            cbad = False
        check[i] = not (bad.any() or kbad.any() or cbad)
    cover_dist = np.where(np.isfinite(edge), np.clip(np.maximum(edge, 0.0) / cfg.obs_cover_norm, 0.0, 1.0), 1.0)
    if not np.array_equal(cover_dist, np.asarray(out["cover_dist"])):
        raise SystemExit("은신처 가장자리 다시 계산이 세계 cover_dist 와 다르다")
    return dict(seed=col["seed"], t=inp["t"], dark=inp["dark"], see_pred=sp, pos=pos, head=head,
                see=np.stack([see, see_last], 1), beh=inp["beh"], check=check,
                threats=np.concatenate([inp["pred_pos"], inp["pred_vel"]], 1), asleep=inp["pred_asleep"],
                covers=np.concatenate([inp["cov_c"], inp["cov_r"][:, None]], 1) if len(inp["cov_r"]) else np.zeros((0, 3)),
                exp_int=np.stack([np.asarray(out["pred_count"]), np.asarray(out["pred_count_ev"]),
                                  np.asarray(out["kin_count"]).astype(np.int64), np.asarray(out["cover_k"]),
                                  np.asarray(out["in_cover"]).astype(np.int64)], 1).astype(np.int64),
                exp_real=np.stack([sentinel(out["d_pred_min"]), out["away_from_pred"][:, 0], out["away_from_pred"][:, 1],
                                   out["pred_approach"], sentinel(out["d_pred_min_ev"]), out["pred_approach_ev"],
                                   out["to_centroid"][:, 0], out["to_centroid"][:, 1], out["separation"][:, 0],
                                   out["separation"][:, 1], out["kin_alarm"], out["cover_dist"], sentinel(edge)], 1))


# --------------------------------------------------------------------- #
# 모으기
# --------------------------------------------------------------------- #


def build_golden(model, cfg, seeds, steps: int) -> dict:
    from env_v2 import repertoire as rep

    check_seeds(seeds)
    check_seeds([EDGE_SEED])
    cols = [collect(model, cfg, s, steps) for s in seeds]
    p = cols[0]["params"]
    stats = {"seeds": [int(s) for s in seeds], "steps": int(steps), "window_candidates": 0, "window_near_excluded": 0,
             "loop_near_tie_rejected": 0}
    seqs = []
    for col in cols:
        rng = np.random.default_rng([SELECT_SEED, col["seed"], 1])
        wins, st = select_windows(col, model, rng)
        stats["window_candidates"] += st["candidates"]
        stats["window_near_excluded"] += st["near_excluded"]
        stats["loop_near_tie_rejected"] += st["loop_near_tie_rejected"]
        seqs += [rollout_sequence(col, wn) for wn in wins]
    n_roll = len(seqs)
    seqs += edge_sequences(p, EDGE_SEED)

    # 제어기 (롤아웃 + 손 사례). 먹이 판정 문턱 근처는 검사에서 뺀다
    ctl = [r for col in cols for r in col["ctl"]] + control_synthetic(cfg, p)
    for r in ctl:
        r["food_check"] = int(r["cell_food"] >= 0.0 and abs(r["cell_food"] - p["graze_eat_min"]) >= NEAR_FOOD)
        if r["kind"] == CTL_ROLLOUT and r["food_check"] and r["sint"][0] == rep.GRAZE:
            if bool(r["iin"][1]) != (r["cell_food"] >= p["graze_eat_min"]):
                raise SystemExit("제어기 food_ok 가 셀 먹이와 맞지 않는다")
    stats["ctl_food_near_excluded"] = int(sum(1 for r in ctl if r["kind"] == CTL_ROLLOUT and not r["food_check"]))

    obs_cases = [r for col in cols for r in col["obs"]]
    for r in obs_cases:
        if r["has_cover"] and float(np.clip(max(r["edge"], 0.0) / cfg.obs_cover_norm, 0.0, 1.0)) != r["cover_dist"]:
            raise SystemExit("관측 만들기 입력의 은신처 가장자리가 세계 cover_dist 와 맞지 않는다")
    per = [r for col in cols for r in col["per"]]
    resp = [r for col in cols for r in col["resp"]]
    ema = [r for col in cols for r in col["ema"]]
    snaps = [snapshot_case(col, pick_snapshot(col), cfg) for col in cols]
    stats["snap_agents"] = int(sum(len(s["pos"]) for s in snaps))
    stats["snap_near_excluded"] = int(sum(int((~s["check"]).sum()) for s in snaps))
    stats["snap_band"] = int(sum(int((s["exp_int"][:, 0] != s["exp_int"][:, 1]).sum()) for s in snaps))
    stats["snap_asleep"] = int(sum(asleep_hidden(pick_snapshot(c)["inp"]) for c in cols))
    stats["rollout_seqs"], stats["edge_seqs"] = n_roll, len(seqs) - n_roll
    stats["rollout_steps"] = int(sum(len(s["steps"]) for s in seqs[:n_roll]))
    stats["edge_steps"] = int(sum(len(s["steps"]) for s in seqs[n_roll:]))
    stats["loop_seqs"] = int(sum(1 for s in seqs if s["loop_obs"] is not None))
    stats["window_cats"] = [s["name"] for s in seqs[:n_roll]]
    return dict(params=p, consts=world_constants(cfg, p), hashes=hash_rows(), seqs=seqs, resp=resp, ctl=ctl, per=per,
                obs=obs_cases, snaps=snaps, daynight=daynight_rows(cols), ema=ema, stats=stats,
                worlds=[(c["seed"], c["size"], c["period"], c["offset"], c["tw"]) for c in cols])


# --------------------------------------------------------------------- #
# 헤더 쓰기
# --------------------------------------------------------------------- #


def f64_lit(x) -> str:
    """double 을 다시 읽으면 같은 double 이 되는 가장 짧은 십진 표기 (inf → 1e300 = kNoThreatDist)."""
    v = float(x)
    if math.isinf(v):
        return "1e300" if v > 0 else "-1e300"
    if math.isnan(v):
        raise SystemExit("골든에 NaN 이 있다")
    return repr(v)


def u64_lit(x) -> str:
    return f"0x{int(x) & 0xFFFFFFFFFFFFFFFF:016x}ULL"


def i64_lit(x) -> str:
    v = int(x)
    if not -(2 ** 63) < v < 2 ** 63:
        raise SystemExit(f"int64 범위 밖: {v}")
    return str(v)


def _names(xs) -> str:
    return ", ".join(f'"{x}"' for x in xs)


def write_header(path: Path, g: dict, meta: dict) -> None:
    from env_v2.repertoire import BEHAVIOR_NAMES

    s = g["stats"]
    seqs, ctl, snaps = g["seqs"], g["ctl"], g["snaps"]
    arr = ew.c_array
    i32, u8, f32 = ew._i32, ew._u8, ew.f32_lit

    # 2. Arbiter 열
    starts, lengths, loop_starts, loop_rows = [], [], [], []
    st_req, st_dint, st_dreal, st_alarm, st_flags, st_ev, st_post = [], [], [], [], [], [], []
    st_resp, st_re, st_rd, st_rg = [], [], [], []
    n = 0
    for q in seqs:
        starts.append(n)
        lengths.append(len(q["steps"]))
        if q["loop_obs"] is not None:
            loop_starts.append(len(loop_rows))
            loop_rows += list(q["loop_obs"])
        else:
            loop_starts.append(-1)
        for r in q["steps"]:
            st_req.append(r["req"])
            st_dint.append(r["dint"])
            st_dreal.append(r["dreal"])
            st_alarm.append(r["alarm"])
            st_flags.append(r["flags"])
            st_ev.append(r["ev"])
            st_post.append(r["post"])
            st_resp.append(r["resp"])
            st_re.append(r["resp_energy"])
            st_rd.append(r["resp_dark"])
            st_rg.append(r["resp_gen"])
            n += 1
    if not loop_rows:
        raise SystemExit("닫힌 고리 창이 없다")
    flags_all = np.array(st_flags)
    ev_all = np.array(st_ev)
    beh_post = np.array(st_post)[:, 0]
    ev_counts = {k: int(((ev_all & b) != 0).sum()) for k, b in EV_BITS.items()}
    roll_steps = s["rollout_steps"]
    sw_roll = (flags_all[:roll_steps] & FLAG_SWITCH) != 0
    into = np.bincount(beh_post[:roll_steps][sw_roll], minlength=5)

    snap_a0, snap_t0, snap_c0 = np.cumsum([0] + [len(x["pos"]) for x in snaps])[:-1], \
        np.cumsum([0] + [len(x["threats"]) for x in snaps])[:-1], np.cumsum([0] + [len(x["covers"]) for x in snaps])[:-1]
    max_agents = max(len(x["pos"]) for x in snaps)
    max_threats = max(max(len(x["threats"]) for x in snaps), 1)
    max_covers = max(max(len(x["covers"]) for x in snaps), 1)
    covers_all = np.concatenate([x["covers"] for x in snaps]) if sum(len(x["covers"]) for x in snaps) else np.zeros((1, 3))

    worlds = "\n".join(f"//            시드 {sd}: 맵 {sz:.3f}단위, 하루 {T}스텝 (위상 {o}, 박명 {tw})" for sd, sz, T, o, tw in g["worlds"])
    cat_n = {}
    for c in s["window_cats"]:
        cat_n[c] = cat_n.get(c, 0) + 1
    cats = ", ".join(f"{c} {k}" for c, k in cat_n.items())
    body = f"""// 자동 생성. 수정 금지.
// 생성: herbivore_rl/export_golden_v3_world.py — v3 R1b 세계 개체 논리 골든 (Arbiter·제어기·이동·에너지·지각·관측 18)
// model:   {meta["model"]}  (sha256 {meta["model_sha256"]})
// world:   {meta["world_config"]}  (config_digest {meta["world_digest"]}), 경보 없음, 관측 18, 마스크 판 2
//          보정 시드 {" ".join(map(str, s["seeds"]))} x {s["steps"]}스텝, 모델 자신의 argmax (env_v2/rollout.py RepLearned)
{worlds}
// 계약:    AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V3.md 5·6·2절. 대조 코드 Tests/RepertoireGoldenCheckV3.h
//
// 0. 세계 상수 kWorldConstantCount = {len(g["consts"])} (파이썬 설정에서 읽은 값 = C++ FRepertoireConfig·FObservationConfig)
// 1. 지연 해시 kHashCount = {len(g["hashes"])} (파리티 키 슬롯·2^32 + 세대, 통합 모드 키 StableAgentId)
// 2. Arbiter 열 kSeqCount = {len(seqs)}: 롤아웃 창 {s["rollout_seqs"]} (x {WINDOW}스텝 = {s["rollout_steps"]}), \
경계 열 {s["edge_seqs"]} ({s["edge_steps"]}스텝), 닫힌 고리 {s["loop_seqs"]}
//    창 범주 (범주 창 수): {cats}
//    문턱 근처 제외 (|d - 8| < 1e-4, |접근 - 0.9| < 1e-5, |E - 0.25| < 1e-6): 창 후보 {s["window_candidates"]} 중 \
{s["window_near_excluded"]}
//    닫힌 고리 망 근접 동점 (1·2위 < 1e-4) 으로 고르지 않은 창: {s["loop_near_tie_rejected"]}
//    롤아웃 창의 전환: GRAZE {into[0]}, FLEE {into[1]}, HIDE {into[2]}, FREEZE {into[3]}, SLEEP {into[4]}
//    모든 열의 사건 수: E1 {ev_counts["e1"]}, E2 {ev_counts["e2"]}, E3 {ev_counts["e3"]}, E4 {ev_counts["e4"]}, \
E5 {ev_counts["e5"]}, E6 {ev_counts["e6"]}, E7 {ev_counts["e7"]}
// 3. 리스폰 kRespawnCount = {len(g["resp"])}
// 4. 제어기 kControlCount = {len(ctl)} (롤아웃 {sum(1 for r in ctl if r["kind"] == CTL_ROLLOUT)}, 손 사례 \
{sum(1 for r in ctl if r["kind"] == CTL_SYNTH)}), 셀 먹이 |f - 0.06| < 1e-6 로 먹이 판정 검사를 뺀 것 {s["ctl_food_near_excluded"]}
// 5. Perceive kPerceiveCount = {len(g["per"])}
// 6. 관측 만들기 kObsBuildCount = {len(g["obs"])}
// 7. 지각 스냅샷 kSnapCount = {len(snaps)} (개체 {s["snap_agents"]}, 사건 비교 시야가 실제 시야와 다름 {s["snap_band"]}, 자서 안 보이는 위협 쌍 {s["snap_asleep"]}),\n//    문턱 근처로 검사를 뺀 개체 {s["snap_near_excluded"]}
//    (실거리 대 탐지·사건 비교·동족 20·분리 5·은신 가장자리 0 |d - r| < 1e-4, 시야각 |cos - 0.5| < 1e-5)
// 8. 낮밤 kDayNightCount = {len(g["daynight"])}
// 9. 피식 EMA kEmaCount = {len(g["ema"])}
//
// 허용: 실수 |C++ - Python| <= kFloatTolerance, 정수·열거·불은 정확히 같다. 거리 1e300 = 파이썬 inf (안 보임·은신처 없음)
#pragma once

#include <cstdint>

namespace EcoRepertoireV3::Golden
{{
	inline constexpr double kFloatTolerance = {f64_lit(FLOAT_TOL)};
	inline constexpr const char* kBehaviorNames[5] = {{{_names(BEHAVIOR_NAMES)}}};

	// ---- 0. 세계 상수 ----
	inline constexpr std::int32_t kWorldConstantCount = {len(g["consts"])};
{arr("const char*", "kWorldConstantNames", [k for k, _ in g["consts"]], 4, lambda x: f'"{x}"')}
{arr("double", "kWorldConstantValues", [v for _, v in g["consts"]], 6, f64_lit)}

	// ---- 1. 지연 해시 H(505, Seed, AgentKey), 지연 = H mod 4 ----
	inline constexpr std::int32_t kHashCount = {len(g["hashes"])};
{arr("std::int64_t", "kHashSeed", [r["seed"] for r in g["hashes"]], 6, i64_lit)}
{arr("std::uint64_t", "kHashKey", np.array([r["key"] for r in g["hashes"]], dtype=np.uint64), 4, u64_lit)}
{arr("std::uint64_t", "kHashValue", np.array([r["h"] for r in g["hashes"]], dtype=np.uint64), 4, u64_lit)}
{arr("std::int32_t", "kHashJitter", [r["j"] for r in g["hashes"]], 32, i32)}
{arr("std::int64_t", "kHashSlot", [r["slot"] for r in g["hashes"]], 16, i64_lit, comment="[n] -1 = 통합 모드 키")}
{arr("std::int64_t", "kHashGeneration", [r["gen"] for r in g["hashes"]], 8, i64_lit)}

	// ---- 2. Arbiter 열 ----
	inline constexpr std::int32_t kStateFieldCount = {len(STATE_FIELDS)};
	inline constexpr const char* kStateFieldNames[kStateFieldCount] = {{{_names(STATE_FIELDS)}}};
	inline constexpr std::int32_t kObsIntCount = {len(DOBS_INT)};     // {" ".join(DOBS_INT)}
	inline constexpr std::int32_t kObsRealCount = {len(DOBS_REAL)};    // {" ".join(DOBS_REAL)}
	inline constexpr std::uint8_t kFlagDecide = {FLAG_DECIDE};
	inline constexpr std::uint8_t kFlagSwitch = {FLAG_SWITCH};
	inline constexpr std::uint8_t kFlagEvent = {FLAG_EVENT};
	inline constexpr std::uint8_t kFlagFire = {FLAG_FIRE};
	inline constexpr std::uint8_t kFlagE7 = {FLAG_E7};
	inline constexpr std::uint8_t kFlagReads = {FLAG_READS};          // rep_peek reads
	inline constexpr std::uint8_t kFlagWakeDecide = {FLAG_WAKE};     // rep_peek wake_decide
	inline constexpr std::int32_t kSeqKindRollout = {KIND_ROLLOUT};
	inline constexpr std::int32_t kSeqKindEdge = {KIND_EDGE};
	inline constexpr std::int32_t kSeqCount = {len(seqs)};
{arr("const char*", "kSeqName", [q["name"] for q in seqs], 6, lambda x: f'"{x}"')}
{arr("std::int32_t", "kSeqStart", starts, 16, i32, comment="[s] 스텝 배열의 첫 칸")}
{arr("std::int32_t", "kSeqLength", lengths, 16, i32)}
{arr("std::int32_t", "kSeqKind", [q["kind"] for q in seqs], 32, i32)}
{arr("std::uint8_t", "kSeqAlarm", [q["alarm"] for q in seqs], 32, u8, comment="[s] 1 = bKinAlarmEvent 켜고 돌린다 (경계 열 하나)")}
{arr("std::uint8_t", "kSeqFresh", [q["fresh"] for q in seqs], 32, u8, comment="[s] 1 = 시작 상태가 InitAgent 그대로")}
{arr("double", "kSeqInitEnergy", [q["init_energy"] for q in seqs], 6, f64_lit)}
{arr("double", "kSeqInitDark", [q["init_dark"] for q in seqs], 6, f64_lit)}
{arr("std::int64_t", "kSeqSeed", [q["seed"] for q in seqs], 8, i64_lit)}
{arr("std::int32_t", "kSeqSlot", [q["slot"] for q in seqs], 16, i32)}
{arr("std::int32_t", "kSeqGeneration", [q["gen"] for q in seqs], 16, i32)}
{arr("std::int32_t", "kSeqSource", [x for q in seqs for x in q["src"]], 3, i32, comment="[s*3] 시드, 시작 스텝, 개체 (경계 열: -1, 번호, 0)")}
{arr("std::int32_t", "kSeqLoopStart", loop_starts, 16, i32, comment="[s] kLoopObs 의 첫 행, -1 = 닫힌 고리 아님")}
{arr("std::int32_t", "kSeqInitState", [x for q in seqs for x in q["init"]], 19, i32, comment="[s*19] kStateFieldNames 순서")}

	inline constexpr std::int32_t kStepCount = {n};
{arr("std::int32_t", "kStepRequest", st_req, 32, i32)}
{arr("std::int32_t", "kStepObsInt", np.array(st_dint).reshape(-1), 4, i32, comment="[n*4] 결정 관측 정수 칸")}
{arr("double", "kStepObsReal", np.array(st_dreal).reshape(-1), 6, f64_lit, comment="[n*6] 결정 관측 실수 칸")}
{arr("std::uint8_t", "kStepAlarmNew", st_alarm, 32, u8)}
{arr("std::uint8_t", "kStepFlags", st_flags, 32, i32, comment="[n] kFlag* 비트")}
{arr("std::uint8_t", "kStepEvents", st_ev, 32, i32, comment="[n] 사건 비트 E1 0x01 .. E7 0x40")}
{arr("std::int32_t", "kStepState", np.array(st_post).reshape(-1), 19, i32, comment="[n*19] 결정(Commit) 뒤 상태")}
{arr("std::uint8_t", "kStepRespawn", st_resp, 32, u8, comment="[n] 1 = 이 스텝 Tick 뒤 리스폰")}
{arr("double", "kStepRespawnEnergy", st_re, 8, f64_lit)}
{arr("double", "kStepRespawnDark", st_rd, 8, f64_lit)}
{arr("std::int32_t", "kStepRespawnGeneration", st_rg, 32, i32)}
	inline constexpr std::int32_t kLoopRowCount = {len(loop_rows)};
{arr("float", "kLoopObs", np.array(loop_rows).reshape(-1), 18, f32, comment="[r*18] 닫힌 고리 창의 관측 18 (그 스텝 결정 전)")}

	// ---- 3. 리스폰 (Tick 뒤 상태 -> reset_slots 뒤 상태) ----
	inline constexpr std::int32_t kRespawnCount = {len(g["resp"])};
{arr("std::int32_t", "kRespawnPre", [x for r in g["resp"] for x in r["pre"]], 19, i32)}
{arr("std::int32_t", "kRespawnPost", [x for r in g["resp"] for x in r["post"]], 19, i32)}
{arr("double", "kRespawnEnergy", [r["energy"] for r in g["resp"]], 6, f64_lit)}
{arr("double", "kRespawnDark", [r["dark"] for r in g["resp"]], 6, f64_lit)}
{arr("std::int64_t", "kRespawnSeed", [r["seed"] for r in g["resp"]], 8, i64_lit)}
{arr("std::int32_t", "kRespawnSlot", [r["slot"] for r in g["resp"]], 16, i32)}
{arr("std::int32_t", "kRespawnGeneration", [r["gen"] for r in g["resp"]], 16, i32)}

	// ---- 4. 제어기·이동·에너지 ----
	inline constexpr std::int32_t kControlCount = {len(ctl)};
{arr("std::uint8_t", "kCtlKind", [r["kind"] for r in ctl], 32, i32, comment="[n] 0 롤아웃, 1 손 사례 (이동·에너지 없음)")}
{arr("std::int32_t", "kCtlStateInt", [x for r in ctl for x in r["sint"]], 4, i32, comment="[n*4] 행동, 놀람, 은신 목표, 도착")}
{arr("double", "kCtlAway", np.array([r["away"] for r in ctl]).reshape(-1), 2, f64_lit, comment="[n*2] 상태 away")}
{arr("double", "kCtlVecIn", np.array([r["vin"] for r in ctl]).reshape(-1), 10, f64_lit, comment="[n*10] 먹이 기울기, 무리, 분리, 위협 반대, 목표 쪽")}
{arr("std::int32_t", "kCtlIntIn", [x for r in ctl for x in r["iin"]], 3, i32, comment="[n*3] 위협 수, 먹이 충분, 은신처 안")}
{arr("double", "kCtlCellFood", [r["cell_food"] for r in ctl], 6, f64_lit, comment="[n] 결정 때 셀 먹이 (-1 = 손 사례)")}
{arr("std::uint8_t", "kCtlFoodCheck", [r["food_check"] for r in ctl], 32, u8, comment="[n] 0 = 문턱 근처·손 사례로 먹이 판정 검사 안 함")}
{arr("double", "kCtlDark", [r["dark"] for r in ctl], 6, f64_lit)}
{arr("double", "kCtlVelocity", np.array([r["vel"] for r in ctl]).reshape(-1), 4, f64_lit)}
{arr("std::int32_t", "kCtlGait", [r["gait"] for r in ctl], 32, i32)}
{arr("double", "kCtlReal", [x for r in ctl for x in (r["eat"], r["drain"], r["see"], r["cover"])], 4, f64_lit, comment="[n*4] 섭식 배수, 대사 배수, 탐지 배수, 은신 배수")}
{arr("std::uint8_t", "kCtlBool", [x for r in ctl for x in (r["still"], r["crouch"], r["has_face"])], 3, u8, comment="[n*3] 정지, 웅크림, heading 덮기")}
{arr("double", "kCtlFace", np.array([r["face"] for r in ctl]).reshape(-1), 4, f64_lit)}
{arr("std::uint8_t", "kCtlHasMove", [r["has_move"] for r in ctl], 32, u8)}
{arr("double", "kCtlWorldSize", [r["size"] for r in ctl], 6, f64_lit)}
{arr("double", "kCtlMove", np.array([np.concatenate([r["pos0"], r["head0"], r["pos1"], r["head1"]]) for r in ctl]).reshape(-1), 4, f64_lit, comment="[n*8] 이동 전 위치·heading, 이동 뒤 위치·heading")}
{arr("std::uint8_t", "kCtlHasEnergy", [r["has_energy"] for r in ctl], 32, u8)}
{arr("double", "kCtlEnergy", [x for r in ctl for x in (r["e0"], r["e_dr"], r["mult"], r["want"], r["frac"], r["gain"], r["e_new"], r["e_fin"])], 4, f64_lit, comment="[n*8] E, E′, 섭식 배수(밤 포함), 수요, 셀 비율, 먹은 양, E_new, 번식 뒤 E")}
{arr("std::int32_t", "kCtlRepro", [x for r in ctl for x in (r["cd0"], r["cd_fin"], r["repro"])], 3, i32, comment="[n*3] 번식 쿨다운 전, 뒤, 번식함")}

	// ---- 5. Perceive ----
	inline constexpr std::int32_t kPerceiveCount = {len(g["per"])};
{arr("double", "kPerReal", [x for r in g["per"] for x in (r["r0"], r["a0"][0], r["a0"][1], r["afp"][0], r["afp"][1], r["r1"], r["a1"][0], r["a1"][1])], 4, f64_lit, comment="[n*8] recency 전, away 전, 위협 반대, recency 뒤, away 뒤")}
{arr("std::int32_t", "kPerPredCount", [r["pc"] for r in g["per"]], 32, i32)}

	// ---- 6. 관측 만들기 ----
	inline constexpr std::int32_t kObsBuildCount = {len(g["obs"])};
{arr("std::int32_t", "kObInt", [x for r in g["obs"] for x in (r["pc"], r["kin"], r["has_cover"], r["r"], r["beh"], r["steps_in"])], 6, i32, comment="[n*6] 위협 수, 동족 수, 은신처 있음, 전환까지 스텝, 행동, 경과")}
{arr("double", "kObReal", [x for r in g["obs"] for x in (r["food"], r["d"], r["energy"], r["ema"], r["edge"], r["dark"], r["app"], r["kin_alarm"], r["recency"])], 3, f64_lit, comment="[n*9] 먹이, 거리, E, EMA, 은신 가장자리, d, 접근, 동족 경보, recency")}
{arr("float", "kObExpected", np.array([r["obs"] for r in g["obs"]]).reshape(-1), 6, f32, comment="[n*18] 세계가 낸 관측")}
{arr("std::int32_t", "kObSource", [x for r in g["obs"] for x in r["src"]], 3, i32)}

	// ---- 7. 지각 스냅샷 ----
	inline constexpr std::int32_t kSnapCount = {len(snaps)};
	inline constexpr std::int32_t kSnapMaxAgents = {max_agents};
	inline constexpr std::int32_t kSnapMaxThreats = {max_threats};
	inline constexpr std::int32_t kSnapMaxCovers = {max_covers};
{arr("std::int32_t", "kSnapAgentStart", snap_a0, 8, i32)}
{arr("std::int32_t", "kSnapAgentCount", [len(x["pos"]) for x in snaps], 8, i32)}
{arr("std::int32_t", "kSnapThreatStart", snap_t0, 8, i32)}
{arr("std::int32_t", "kSnapThreatCount", [len(x["threats"]) for x in snaps], 8, i32)}
{arr("std::int32_t", "kSnapCoverStart", snap_c0, 8, i32)}
{arr("std::int32_t", "kSnapCoverCount", [len(x["covers"]) for x in snaps], 8, i32)}
{arr("double", "kSnapDark", [x["dark"] for x in snaps], 4, f64_lit)}
{arr("double", "kSnapSeePred", [x["see_pred"] for x in snaps], 4, f64_lit, comment="[s] see_r·(1 − 0.5·d)")}
{arr("std::int32_t", "kSnapSource", [v for x in snaps for v in (x["seed"], x["t"])], 2, i32, comment="[s*2] 시드, 스텝 (그 스텝 끝 기하)")}
{arr("double", "kSnapAgent", np.concatenate([np.concatenate([x["pos"], x["head"], x["see"]], 1) for x in snaps]).reshape(-1), 6, f64_lit, comment="[a*6] 위치, heading, 탐지 배수 지금·직전")}
{arr("std::int32_t", "kSnapAgentBehavior", np.concatenate([x["beh"] for x in snaps]), 32, i32)}
{arr("std::uint8_t", "kSnapAgentCheck", np.concatenate([x["check"] for x in snaps]).astype(np.int64), 32, u8, comment="[a] 0 = 문턱 근처로 검사 안 함")}
{arr("double", "kSnapThreat", np.concatenate([x["threats"] for x in snaps]).reshape(-1), 4, f64_lit, comment="[m*4] 위치, 지난 변위")}
{arr("std::uint8_t", "kSnapThreatAsleep", np.concatenate([x["asleep"] for x in snaps]).astype(np.int64), 32, u8)}
{arr("double", "kSnapCover", covers_all.reshape(-1), 3, f64_lit, comment="[k*3] 중심, 반지름")}
{arr("std::int32_t", "kSnapExpInt", np.concatenate([x["exp_int"] for x in snaps]).reshape(-1), 5, i32, comment="[a*5] 위협 수, 사건 비교 위협 수, 동족 수, 은신처, 은신처 안")}
{arr("double", "kSnapExpReal", np.concatenate([x["exp_real"] for x in snaps]).reshape(-1), 13, f64_lit, comment="[a*13] 거리, 위협 반대 x·y, 접근, 사건 거리, 사건 접근, 무리 x·y, 분리 x·y, 동족 경보, 은신 거리 관측, 가장자리")}

	// ---- 8. 낮밤 ----
	inline constexpr std::int32_t kDayNightCount = {len(g["daynight"])};
{arr("std::int64_t", "kDnT", [r[0] for r in g["daynight"]], 8, i64_lit)}
{arr("std::int32_t", "kDnParam", [x for r in g["daynight"] for x in r[1:4]], 3, i32, comment="[n*3] 하루 길이, 위상, 박명")}
{arr("double", "kDnDark", [r[4] for r in g["daynight"]], 6, f64_lit)}
{arr("std::int32_t", "kDnSteps", [r[5] for r in g["daynight"]], 16, i32)}

	// ---- 9. 피식 EMA ----
	inline constexpr std::int32_t kEmaCount = {len(g["ema"])};
{arr("double", "kEmaBefore", [r["ema0"] for r in g["ema"]], 4, f64_lit)}
{arr("double", "kEmaAfter", [r["ema1"] for r in g["ema"]], 4, f64_lit)}
{arr("std::int32_t", "kEmaCaught", [r["caught"] for r in g["ema"]], 16, i32)}
{arr("std::int32_t", "kEmaAgents", [r["n"] for r in g["ema"]], 16, i32)}
}}
"""
    Path(path).write_text(body, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------- #


def export(model_path: Path, config: Path, out: Path, seeds=GOLDEN_SEEDS, steps: int = STEPS) -> dict:
    """헤더를 `out` 에 쓴다. 반환: 메타·통계·골든 (시험이 읽는다)."""
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import check_mask_version

    model_path, config, out = Path(model_path), Path(config), Path(out)
    if not model_path.exists():
        raise SystemExit(f"{model_path} 없음")
    check_seeds(seeds)
    prev_threads = th.get_num_threads()
    th.set_num_threads(1)
    try:
        model = ew.load_model(model_path)
        cfg = load_v2_config(config)
        names = ew_obs_names(cfg)
        check_mask_version(int(getattr(model.policy, "rep_mask_version", 1)), names)
        if len(names) != 18 or "alarm_heard" in names:
            raise SystemExit("이 골든은 R1b 세계(관측 18, 경보 없음)만 받는다")
        from env_v2.features import features_of
        if any(n.startswith("realism_") for n in features_of(cfg).active):
            raise SystemExit("이 골든은 R1b 세계만 받는다 — realism_*(v3 현실성 1단계) 규칙은 C++ 에 아직 없다")
        if features_of(cfg).params("threats").get("eat_in_place"):
            raise SystemExit("이 골든은 R1b 세계만 받는다 — threats.eat_in_place(늑대가 잡은 자리에서 서서 먹음, 10-15)는 C++ 에 아직 없다")
        g = build_golden(model, cfg, seeds, steps)
    finally:
        th.set_num_threads(prev_threads)
    meta = dict(model=ew.rel(model_path), model_sha256=ew.file_sha256(model_path), world_config=ew.rel(config),
                world_digest=ew.config_digest(cfg))
    out.mkdir(parents=True, exist_ok=True)
    write_header(out / HEADER, g, meta)
    return dict(meta=meta, stats=g["stats"], golden=g)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="v3 R1b 세계 개체 논리 골든 내보내기")
    p.add_argument("--model", default=str(DEFAULT_MODEL))
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="R1b 세계 (관측 18, 경보 없음)")
    p.add_argument("--seeds", type=int, nargs="+", default=list(GOLDEN_SEEDS))
    p.add_argument("--steps", type=int, default=STEPS)
    p.add_argument("--out", default=str(UE_POLICY_DIR), help="헤더를 쓸 폴더 (기본: 언리얼 모듈 AI/Policy)")
    args = p.parse_args(argv)

    r = export(Path(args.model), Path(args.config), Path(args.out), args.seeds, args.steps)
    s, g = r["stats"], r["golden"]
    print(f"모델: {r['meta']['model']}  sha256 {r['meta']['model_sha256'][:16]}")
    print(f"Arbiter 열: 롤아웃 창 {s['rollout_seqs']} ({s['rollout_steps']}스텝), 경계 열 {s['edge_seqs']} "
          f"({s['edge_steps']}스텝), 닫힌 고리 {s['loop_seqs']}")
    print(f"문턱 근처 제외: 창 후보 {s['window_candidates']} 중 {s['window_near_excluded']}, 제어기 먹이 {s['ctl_food_near_excluded']}, "
          f"스냅샷 개체 {s['snap_agents']} 중 {s['snap_near_excluded']}, 닫힌 고리 망 근접 동점 {s['loop_near_tie_rejected']}")
    print(f"제어기 {len(g['ctl'])}  리스폰 {len(g['resp'])}  Perceive {len(g['per'])}  관측 만들기 {len(g['obs'])}  "
          f"스냅샷 {len(g['snaps'])}  해시 {len(g['hashes'])}  낮밤 {len(g['daynight'])}  EMA {len(g['ema'])}")
    print(f"생성: {Path(args.out) / HEADER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
