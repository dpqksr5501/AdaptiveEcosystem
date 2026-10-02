"""Gate F — v2.0b 먹이 2층의 환경 게이트 (계획서 0-6, 4.9.1, 6.2 F4, 9절).

v2.0b 는 정책이 새로 쓸 입력·행동이 없어서 C2-seg 비교 대신, 정해 둔 정책으로 3만 스텝을 돌려 동역학이
설계대로인지 본다(5.0 환경 게이트). 정책 3종(v1 최적 상수 C2, v1 학습 정책, 튜닝 Utility) × 보정 시드 3개.

    python gate_f.py run --round R0 --alpha 0.5 --note "제안값 첫 실행"
    python gate_f.py run --round R1 --alpha 0.03 0.05 0.1 --note "보정 1회차 (사전 등록)"
    python gate_f.py run --round R2 --alpha ... --floor ... --half-life ... --regen-base ... --note "..."
    python gate_f.py run --round ref --reference --note "참고: food_v 끈 v2.0 세계"
    python gate_f.py report

- 회차(R0 = 제안값, R1·R2 = 보정 1·2회차, ref = v2.0 참고)마다 `results/v2/gate_f/rounds/<회차>.json` 을 남기고,
  run 이 끝날 때마다 모든 회차로 `results/v2/gate_f/report.md`·`report.json` 을 다시 만든다. 보정은 계획서 5.0
  에 따라 최대 2회라 R3 은 받지 않는다. 손으로 쓴 해석은 `results/v2/gate_f/notes.md` 에 두면 보고서에 붙는다.
- 회차 하나는 후보 여러 개를 함께 잴 수 있다(값 목록의 곱). 회차의 선택값은 (a)(b)(d)를 모든 정책·시드에서
  지키는 후보 가운데 (c) 진폭 평균이 가장 큰 것이다(0-6 보정 1회차 사전 등록 규칙). 그런 후보가 없으면
  (a)(b)(d) 통과 수가 가장 많은 후보, 같으면 진폭 평균이 큰 후보다. 종합 판정은 마지막 회차 선택값이
  정책·시드 9개 모두에서 (a)~(d)를 통과하는가다.
- 계수는 명령줄에 모두 적는다. 생략한 계수만 `--config`(기본 configs/v2_0b.yaml)의 food_v 블록 값을 쓴다.
  보정 값을 yaml 에 반영한 뒤에도 앞 회차 명령을 그대로 다시 돌릴 수 있게 하기 위해서다.
- 판정 실행은 회복 반감기를 설계값 693 하나로 고정한다(4.7 "판정 실행에서는 범위를 고정"). yaml 의 학습 목록
  [300, 700, 2000, 7000] 을 `--half-life` 값 하나로 덮는다. 목록이 하나여도 food_v 스트림 소비는 같아서
  V 초기 비율은 학습 목록일 때와 같다(`World._food_v_reset`).

측정 정의는 `DEFINITIONS`(보고서에 그대로 실린다). 창은 t = 3000~30000 이다(초기 V 전이 제외, 0-6 (b)).
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저 (학습 정책을 워커에서 싣는다)

import argparse
import itertools
import json
import math
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from diagnose_v2 import check_disjoint, clean, config_digest, model_fingerprint, parse_seeds, save_json
from env.config import Config
from env.rollout import _init_worker
from env_v2.config import load_v2_config
from env_v2.world import FOOD_V_FLOOR_TOL, World

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "v2" / "gate_f"
ROUNDS = OUT / "rounds"
NOTES = OUT / "notes.md"
CONFIG = ROOT / "configs" / "v2_0b.yaml"
REF_CONFIG = ROOT / "configs" / "v2.yaml"

# 보정 시드. 계획서 4.9.1·4.7 예비 측정과 0-6 보정 1회차 사전 등록이 이 세 시드를 쓴다(Σcap0 161.8 / 10.7 / 63.2).
# 평가 시드 10000~10019 와도, 학습 시드 범위 [0, 1000) 와도 겹치지 않는다.
CALIB_SEEDS = (20000, 20001, 20002)
STEPS = 30000
WARMUP = 3000             # 창 시작. 그 전은 초기 V(cap0 × U[0.3, 1]) 전이라 지표에서 뺀다
EVERY = 5                 # 셀별 V 표본 간격(스텝)
DESIGN_HALF_LIFE = 693    # 판정 실행의 회복 반감기(스텝), ρ ≈ 1.0e-3 (4.4 표)
QUIET = 600               # (c) 섭식이 멈춘 뒤 경과(스텝)
TOP_FRAC = 0.10           # (c) 누적 섭취 상위 비율
REF_FRAC = 0.50           # (c) 같은 cap0 구간의 누적 섭취 하위 비율(기준 셀)
CAP_BINS = 4              # (c) cap0 구간 수(cap0 > 0 셀의 cap0 순위 4등분)
SERIES_EVERY = 100        # 회차 기록에 남기는 지역 시계열 간격(스텝)

# 기준 (0-6 표, #28 사전 등록)
CRIT = dict(v_lo=0.3, v_hi=0.9, floor_max=0.5, hl_lo=0.5, hl_hi=2.0, amp_min=0.2, persist_min=0.1,
            starve_max=0.4)

# v1 최적 상수 C2 (계획서 2.1, Optuna 112회)
C2_ACTION = [0.4207, 0.8656, 0.1054, 0.0044]
POLICY_ORDER = ("C2", "learned", "utility")
POLICY_LABEL = {"C2": "C2 v1 최적 상수", "learned": "v1 학습 정책", "utility": "Utility (튜닝)"}
ROUND_NAMES = ("R0", "R1", "R2", "ref")
ROUND_LABEL = {"R0": "R0 제안값", "R1": "R1 보정 1회차", "R2": "R2 보정 2회차", "ref": "ref v2.0 참고"}

DEFINITIONS = [
    "- 공통: 보정 시드마다 `World(cfg, seeds=[s])` 하나를 3만 스텝 돌린다. 창은 스텝 끝 시각 t = 3000~30000 "
    "(t = 3000 상태부터, 사건은 t = 3001~30000 스텝). 셀은 cap0 > 0 셀만 센다. V/cap0 표본은 창 안 5스텝마다"
    "(5,401개).",
    "- (a) 평균 V/cap0 = 표본 시각마다 셀별 V/cap0 의 평균(`food_stats` 의 v_cell_mean)을 창 안에서 다시 "
    "평균한 값. 하한 셀 비율 = V/cap0 ≤ floor + 0.01 인 셀의 비율(`FOOD_V_FLOOR_TOL`)의 창 평균. "
    "통과: 0.3 ≤ 평균 V/cap0 ≤ 0.9 이고 하한 셀 비율 < 0.5.",
    "- (b) V 자기상관 반감기 = 셀별 V/cap0 표본에서 셀마다 창 평균을 빼고, 셀별 자기공분산을 모두 더해(분산 가중 "
    "묶음) 지연 0 값으로 나누고 n/(n − k) 로 편향을 보정한 자기상관이 처음 0.5 이하가 되는 지연(스텝, 5스텝 "
    "해상도). 지연 n/2(13,500스텝) 안에 내려가지 않으면 '없음'(실패). 통과: 반감기/설계값(그 후보의 h) 이 "
    "0.5~2.",
    "- (c) 흔적 진폭(F4). cap0 > 0 셀을 cap0 순위로 4등분해 cap0 구간을 만든다. 상위 셀 = 창 안 누적 섭취가 "
    "가장 큰 ceil(10%) 셀(맵 전체 순위, 같으면 셀 번호 순). 기준 셀 = 각 cap0 구간 안에서 누적 섭취가 작은 "
    "쪽 절반(구간 셀 수의 floor(50%), 최소 1). 진폭 = 상위 셀마다 (그 셀 cap0 구간 기준 셀들의 창 평균 V/cap0 "
    "평균 − 그 셀의 창 평균 V/cap0)의 평균. 600스텝 뒤(울타리 시험) = t = 30000 에서 상위 셀에만 울타리를 쳐 "
    "섭식을 막고(그 셀의 섭취 0, 나머지 세계·정책·다른 셀의 섭식은 그대로) 600스텝 더 돌린 뒤, 상위 셀마다 "
    "(같은 구간 기준 셀 평균 V/cap0 − 그 셀 V/cap0)의 평균. 울타리 직전 값은 진폭(끝)이다. 통과: 진폭 ≥ 0.2 "
    "이고 600스텝 뒤 ≥ 0.1. 자연 사건(상위 셀이 창 안에서 스스로 600스텝 동안 안 뜯긴 경우)은 3만 스텝에 "
    "0~5건이라(R0) 판정에 쓰지 않고 보조 열로만 낸다.",
    "- (d) 아사 비중 = 창 안 아사 사망 / (아사 + 피식 사망). 통과: ≤ 0.4.",
    "- 참고 열: 수명 = 창 안에서 죽은 개체의 평균 나이(스텝), 아사율·피식률 = 창 안 사망 / (27,000 × 128). "
    "F_r·V_r = 좌우 절반의 ΣF/Σcap0·ΣV/Cap0 창 평균, F_r 표준편차 = 그 시계열의 창 안 표준편차(9절 신호). "
    "섭취비 = 상위 셀 평균 누적 섭취 / 그 셀 구간 기준 셀의 평균 누적 섭취. x = α·r_eff/ρ 의 중앙값"
    "(상위 셀 / 상위 셀이 있는 구간의 기준 셀, r_eff = 스텝당 섭취 / 창 평균 V, 4.9.1 (b) 해석). "
    "진폭(끝) = t = 30000 한 시점의 진폭(= 울타리 직전). 자연 사건 = 상위 셀에서 마지막 섭취(창 안) 뒤 600스텝 "
    "동안 섭취가 없었던 사건의 600스텝 시점 차(사건 가중, 5스텝 표본이라 600~604스텝)와 그 사건의 멈춤 직후 차.",
]


# --------------------------------------------------------------------- #
# 측정 (순수 함수 — tests/test_gate_f.py)
# --------------------------------------------------------------------- #


def pooled_half_life(X: np.ndarray, every: int = EVERY, chunk: int = 256) -> int | None:
    """(b) 셀별 표본 X (n, cells) → 분산 가중 묶음 자기상관이 처음 0.5 이하가 되는 지연(스텝).

    셀마다 평균을 빼고 자기공분산을 FFT 로 구해 셀끼리 더한다(분산 가중). 지연 k 의 곱 개수가 n − k 라
    n/(n − k) 를 곱한다. 지연 n/2 안에 0.5 이하로 내려가지 않거나 분산이 없으면 None.
    """
    n = int(X.shape[0])
    if n < 4 or X.shape[1] == 0:
        return None
    nfft = 1 << (2 * n - 1).bit_length()
    power = np.zeros(nfft // 2 + 1)
    for j in range(0, X.shape[1], chunk):
        x = np.asarray(X[:, j:j + chunk], dtype=np.float64)
        x = x - x.mean(0)
        f = np.fft.rfft(x, nfft, axis=0)
        power += (f.real ** 2 + f.imag ** 2).sum(1)
    acov = np.fft.irfft(power, nfft)[:n]
    if not acov[0] > 0.0:
        return None
    ac = acov / acov[0] * n / (n - np.arange(n))
    k = np.flatnonzero(ac[1:n // 2] <= 0.5)
    return int((k[0] + 1) * every) if k.size else None


def cap_bins(cap: np.ndarray, n_bins: int = CAP_BINS) -> np.ndarray:
    """cap0 순위 n_bins 등분의 구간 번호 (cells,). 같은 cap0 는 셀 번호 순."""
    bin_of = np.zeros(len(cap), dtype=np.int64)
    for b, idx in enumerate(np.array_split(np.argsort(cap, kind="stable"), n_bins)):
        bin_of[idx] = b
    return bin_of


def trace_sets(cap: np.ndarray, eaten: np.ndarray):
    """(c) 상위 셀(맵 전체 누적 섭취 상위 ceil(10%))과 cap0 구간별 기준 셀(구간 안 누적 섭취 하위 절반)."""
    m = len(cap)
    bin_of = cap_bins(cap)
    top = np.argsort(-eaten, kind="stable")[:max(1, int(math.ceil(TOP_FRAC * m)))]
    is_top = np.zeros(m, dtype=bool)
    is_top[top] = True
    refs = []
    for b in range(CAP_BINS):
        idx = np.flatnonzero(bin_of == b)
        idx = idx[np.argsort(eaten[idx], kind="stable")][:max(1, int(REF_FRAC * len(idx)))] if idx.size else idx
        refs.append(idx[~is_top[idx]])
    return bin_of, top, refs


def gap_after(v_after: np.ndarray, bin_of: np.ndarray, top: np.ndarray, refs: list) -> float:
    """울타리 시험 뒤 V/cap0 (cells,) → 상위 셀마다 (같은 구간 기준 셀 평균 − 그 셀)의 평균."""
    r = np.array([v_after[x].mean() if x.size else np.nan for x in refs])
    return float((r[bin_of[top]] - v_after[top]).mean())


def trace_metrics(X: np.ndarray, cap: np.ndarray, eaten: np.ndarray, ev_s: np.ndarray, ev_i: np.ndarray,
                  lag: int, v_after: np.ndarray | None = None) -> dict:
    """(c) 흔적 진폭과 지속. X (n, cells) 창 안 V/cap0 표본, cap cap0, eaten 창 안 누적 섭취(셀별),
    v_after 상위 셀 울타리 600스텝 뒤 V/cap0 (cells,) — 판정하는 지속(persist).
    (ev_s, ev_i) 자연 사건(상위 셀이 스스로 600스텝 안 뜯김)의 표본 번호·셀, lag = 600/EVERY — 보조 열."""
    nan = float("nan")
    bin_of, top, refs = trace_sets(cap, eaten)
    ok = np.array([r.size > 0 for r in refs])
    top = top[ok[bin_of[top]]]                     # 기준 셀이 없는 구간(셀이 아주 적은 세계)의 상위 셀은 뺀다
    if not top.size:
        return dict(amp=nan, amp_end=nan, persist=nan, persist_nat=nan, persist_nat_d0=nan, n_events=0,
                    n_event_cells=0, n_top=0, intake_ratio=nan, amp_bins=[nan] * CAP_BINS,
                    n_top_bins=[0] * CAP_BINS)
    R = np.stack([X[:, r].mean(1) if r.size else np.full(len(X), nan) for r in refs], 1)   # (n, bins)
    vbar, rbar = X.mean(0), R.mean(0)
    gap = rbar[bin_of[top]] - vbar[top]
    is_top = np.zeros(len(cap), dtype=bool)
    is_top[top] = True
    sel = is_top[ev_i]
    s, i = ev_s[sel], ev_i[sel]
    d600 = R[s, bin_of[i]] - X[s, i]
    d0 = R[s - lag, bin_of[i]] - X[s - lag, i]
    ref_eat = np.array([eaten[r].mean() if r.size else nan for r in refs])
    den = float(ref_eat[bin_of[top]].sum())
    amp_bins, n_bins = [], []
    for b in range(CAP_BINS):
        g = gap[bin_of[top] == b]
        amp_bins.append(float(g.mean()) if g.size else nan)
        n_bins.append(int(g.size))
    return dict(
        amp=float(gap.mean()),
        amp_end=float((R[-1, bin_of[top]] - X[-1, top]).mean()),
        persist=gap_after(np.asarray(v_after, dtype=np.float64), bin_of, top, refs) if v_after is not None
        else nan,
        persist_nat=float(d600.mean()) if d600.size else nan,
        persist_nat_d0=float(d0.mean()) if d0.size else nan,
        n_events=int(d600.size), n_event_cells=int(np.unique(i).size), n_top=int(top.size),
        intake_ratio=float(eaten[top].sum()) / den if den > 0 else float("inf"),
        amp_bins=amp_bins, n_top_bins=n_bins,
    )


def verdict(row: dict, h: float | None) -> dict:
    """정책·시드 한 칸의 (a)~(d) 통과 여부. food_v 를 끈 참고 행은 판정하지 않는다."""
    c = CRIT
    a = bool(c["v_lo"] <= row["v_cell_mean"] <= c["v_hi"] and row["floor_frac"] < c["floor_max"])
    hl = row.get("acf_half_life")
    b = bool(hl is not None and h and c["hl_lo"] <= hl / h <= c["hl_hi"])
    p = row.get("persist")
    cc = bool(row["amp"] >= c["amp_min"] and p is not None and math.isfinite(p) and p >= c["persist_min"])
    d = bool(row["starve_share"] <= c["starve_max"])
    return dict(a=a, b=b, c=cc, d=d, all=a and b and cc and d)


# --------------------------------------------------------------------- #
# 롤아웃 (워커)
# --------------------------------------------------------------------- #


class ExclosureWorld(World):
    """측정 전용 World: `excl`(평탄 셀 번호) 셀에 울타리를 쳐 섭식만 막는다. None 이면 World 와 같다.

    섭식 직전에 그 셀의 F 를 0 으로 보였다가 섭식 뒤 되돌린다. 그래서 그 셀의 섭취·훼손이 0 이고(_fv_taken 0,
    last_eat 그대로) 재생·휴식 회복과 관측(food_blur, food_grad)은 울타리가 없을 때와 같다. 그 셀에 선 개체는
    먹지 못한다. 환경 코드(env_v2)는 바꾸지 않는다.
    """

    excl: np.ndarray | None = None

    def _eat(self, e_drained):
        if self.excl is None:
            return super()._eat(e_drained)
        F = self.food.reshape(-1)               # 연속 배열의 뷰
        saved = F[self.excl].copy()
        F[self.excl] = 0.0
        try:
            return super()._eat(e_drained)
        finally:
            F[self.excl] = saved


def run_job(job: dict) -> dict:
    """정책 하나 × 시드 하나. 프로세스 경계를 넘으므로 인자는 dict 하나다."""
    from policies.registry import make_policy

    t_start = time.time()
    cfg = Config(job["cfg"])
    policy = make_policy(job["spec"])
    seed, steps, warmup = int(job["seed"]), int(job["steps"]), int(job["warmup"])
    w = ExclosureWorld(cfg, seeds=[seed])
    N, on = w.N, w._fv is not None
    cap_all = w.food_cap.reshape(-1)
    pos = np.flatnonzero(cap_all > 0.0)
    cap = cap_all[pos]
    left = w._left_half().reshape(-1)[pos]
    s_left, s_right = float(cap[left].sum()), float(cap[~left].sum())
    n_samp = (steps - warmup) // EVERY + 1
    X = np.empty((n_samp, pos.size), dtype=np.float32) if on else None
    reg = np.full((n_samp, 6), np.nan)     # v_cell_mean, floor_frac, V_L, V_R, F_L, F_R
    tol = w._fv["floor"] + FOOD_V_FLOOR_TOL if on else None
    ev_s, ev_i = [], []
    life_sum = life_n = 0
    base = None
    s = 0
    for _ in range(steps):
        a = policy(w.observe())
        in_win = w.t >= warmup
        life_prev = w._life_cur.copy() if in_win else None
        _, _, done, _ = w.step(a)
        if in_win and done.any():
            life_sum += int(life_prev[done].sum()) + int(done.sum())
            life_n += int(done.sum())
        if w.t < warmup or (w.t - warmup) % EVERY:
            continue
        if w.t == warmup:
            base = dict(starve=w._starve_deaths, pred=w._pred_deaths, repro=w._repro_total,
                        eaten=w._fv_eaten.reshape(-1)[pos].copy() if on else None)
        F = w.food.reshape(-1)[pos]
        if on:
            Vc = w.food_v.reshape(-1)[pos]
            vr = Vc / cap
            X[s] = vr
            reg[s, 0], reg[s, 1] = vr.mean(), (vr <= tol).mean()
            reg[s, 2] = Vc[left].sum() / s_left if s_left > 0 else np.nan
            reg[s, 3] = Vc[~left].sum() / s_right if s_right > 0 else np.nan
            if w.t - warmup >= QUIET:
                le = w._fv_last_eat.reshape(-1)[pos]
                q = w.t - le
                hit = np.flatnonzero((le >= warmup) & (q >= QUIET) & (q < QUIET + EVERY))
                ev_s.extend([s] * hit.size)
                ev_i.extend(hit.tolist())
        reg[s, 4] = F[left].sum() / s_left if s_left > 0 else np.nan
        reg[s, 5] = F[~left].sum() / s_right if s_right > 0 else np.nan
        s += 1
    assert s == n_samp, (s, n_samp)

    t_win = steps - warmup
    sd, pdth = w._starve_deaths - base["starve"], w._pred_deaths - base["pred"]
    nan = float("nan")
    row = dict(
        policy=job["policy"], seed=seed, elapsed_s=round(time.time() - t_start, 1),
        size=float(w.size), M=int(w.M), regen_mult=float(w.food_regen_mult),
        r_mean=float(w.regen_field.reshape(-1)[pos].mean()), cover_frac=float(w.cover_frac_actual),
        n_cells=int(pos.size), sum_cap0=float(cap.sum()), sum_cap0_left=s_left, sum_cap0_right=s_right,
        lifespan=life_sum / life_n if life_n else nan,
        starve_share=sd / (sd + pdth) if sd + pdth else 0.0,
        starve_rate=sd / (t_win * N), pred_rate=pdth / (t_win * N),
        repro_rate=(w._repro_total - base["repro"]) / (t_win * N),
        deaths=int(sd + pdth), starve_deaths=int(sd), pred_deaths=int(pdth),
        f_left=float(np.nanmean(reg[:, 4])), f_right=float(np.nanmean(reg[:, 5])),
        f_left_std=float(np.nanstd(reg[:, 4])), f_right_std=float(np.nanstd(reg[:, 5])),
    )
    k = SERIES_EVERY // EVERY
    series = {"t": list(range(warmup, steps + 1, SERIES_EVERY)),
              "F_L": reg[::k, 4].tolist(), "F_R": reg[::k, 5].tolist()}
    if on:
        alpha, rho, h = float(w._fv["alpha"]), float(w.food_v_rho), float(w.food_v_half_life)
        eaten = w._fv_eaten.reshape(-1)[pos] - base["eaten"]
        bin_of, top, refs = trace_sets(cap, eaten)
        # (c) 울타리 시험: 창이 끝난 t = steps 에서 상위 셀의 섭식만 막고 QUIET 스텝 더 돌린다(창 지표에는 안 들어감)
        w.excl = pos[top]
        for _ in range(QUIET):
            w.step(policy(w.observe()))
        assert (w._fv_last_eat.reshape(-1)[w.excl] <= steps).all(), "울타리 안에서 섭식이 일어났다"
        v_after = w.food_v.reshape(-1)[pos] / cap
        tm = trace_metrics(X, cap, eaten, np.asarray(ev_s, dtype=np.int64), np.asarray(ev_i, dtype=np.int64),
                           QUIET // EVERY, v_after=v_after)
        hl = pooled_half_life(X)
        vbar = X.mean(0).astype(np.float64)
        r_eff = eaten / t_win / np.maximum(vbar * cap, 1e-12)
        used = [refs[b] for b in np.unique(bin_of[top]) if refs[b].size]       # 상위 셀이 있는 구간의 기준 셀
        ref_all = np.concatenate(used) if used else np.empty(0, dtype=np.int64)
        row.update(
            half_life=h, rho=rho, alpha=alpha, floor=float(w._fv["floor"]),
            init_left=w.food_v_init[0], init_right=w.food_v_init[1],
            v_cell_mean=float(reg[:, 0].mean()), floor_frac=float(reg[:, 1].mean()),
            floor_frac_max=float(reg[:, 1].max()),
            v_left=float(np.nanmean(reg[:, 2])), v_right=float(np.nanmean(reg[:, 3])),
            acf_half_life=hl, acf_ratio=hl / h if hl is not None else None,
            taken_per_step=float(eaten.sum()) / t_win, grazed_frac=float((eaten > 0).mean()),
            x_top=float(np.median(alpha * r_eff[top] / rho)),
            x_ref=float(np.median(alpha * r_eff[ref_all] / rho)) if ref_all.size else nan,
            **tm,
        )
        row["pass"] = verdict(row, h)
        series.update(V_L=reg[::k, 2].tolist(), V_R=reg[::k, 3].tolist(), v_mean=reg[::k, 0].tolist(),
                      floor_frac=reg[::k, 1].tolist())
    row["series"] = series
    return row


# --------------------------------------------------------------------- #
# 회차 실행
# --------------------------------------------------------------------- #


def rel(path) -> str:
    """herbivore_rl/ 기준 상대 경로(밖이면 절대 경로)."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def policy_specs(names) -> dict[str, dict]:
    specs = {"C2": {"kind": "fixed", "action": list(C2_ACTION)},
             "learned": {"kind": "learned", "model": str((ROOT / "ckpt" / "final.zip").resolve())},
             "utility": {"kind": "utility"}}
    return {n: specs[n] for n in names}


def policy_meta(specs: dict) -> dict:
    from policies.utility import BEST_PATH, load_best_params

    out = {}
    for n, sp in specs.items():
        m = {"label": POLICY_LABEL[n], "spec": sp}
        if n == "learned":
            m.update(sha1=model_fingerprint(sp["model"]), deterministic=True)
        if n == "utility":
            m.update(params=load_best_params(), source=str(BEST_PATH.relative_to(ROOT)).replace("\\", "/"))
        out[n] = m
    return out


def candidate_label(p: dict) -> str:
    if p is None:
        return "food_v 끔 (v2.0)"
    s = f"α {p['alpha']:g} · 하한 {p['floor']:g} · h {p['half_life']:g}"
    return s + (f" · r_base {p['regen_base']:g}" if p.get("regen_base") is not None else "")


def build_candidates(args, cfg) -> list[dict]:
    """명령줄 값 목록의 곱 → 후보. 생략한 계수는 설정 파일의 food_v 블록 값이다."""
    if args.reference:
        if any(cfg.v2["features"].get(k, {}).get("enabled") for k in cfg.v2["features"]):
            raise SystemExit(f"--reference 는 기능을 모두 끈 설정이어야 한다: {args.config}")
        return [dict(label=candidate_label(None), params=None, cfg=cfg)]
    blk = cfg.v2["features"].get("food_v")
    if not blk or not blk.get("enabled"):
        raise SystemExit(f"{args.config} 에 켜진 food_v 블록이 없다")
    alphas = args.alpha or [blk["alpha"]]
    floors = args.floor or [blk["floor"]]
    hls = args.half_life or [DESIGN_HALF_LIFE]
    regens = args.regen_base or [None]
    out = []
    for a, f, h, r in itertools.product(alphas, floors, hls, regens):
        block = dict(blk, enabled=True, alpha=float(a), floor=float(f), recovery_half_lives=[float(h)])
        c = cfg.replace(v2=dict(cfg.v2, features=dict(cfg.v2["features"], food_v=block)))
        if r is not None:
            c = c.replace(food_regen_base=float(r))
        p = dict(alpha=float(a), floor=float(f), half_life=float(h), regen_base=None if r is None else float(r))
        out.append(dict(label=candidate_label(p), params=p, cfg=c, block=block,
                        overrides={"food_regen_base": float(r)} if r is not None else {}))
    return out


def finite_mean(xs) -> float:
    """None·nan 을 뺀 평균. 남는 값이 없으면 nan."""
    v = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return float(np.mean(v)) if v else float("nan")


def summarize_candidate(rows: list[dict]) -> dict:
    """후보 하나의 정책·시드 묶음 요약 (선택 규칙에 쓰는 값)."""
    if not rows or "pass" not in rows[0]:
        return {}
    P = [r["pass"] for r in rows]
    amps = [r["amp"] for r in rows]
    return dict(
        n=len(rows), n_pass={k: sum(p[k] for p in P) for k in ("a", "b", "c", "d", "all")},
        abd_all=all(p["a"] and p["b"] and p["d"] for p in P),
        n_abd=sum(p["a"] and p["b"] and p["d"] for p in P),
        amp_mean=float(np.mean(amps)), amp_min=float(np.min(amps)),
        persist_mean=finite_mean([r["persist"] for r in rows]),
        passed=all(p["all"] for p in P),
    )


def select(cands: list[dict]) -> int | None:
    """회차 선택값: (a)(b)(d)를 모든 정책·시드에서 지키는 후보 중 진폭 평균 최대. 없으면 (a)(b)(d) 통과 수 최대."""
    scored = [(i, c["summary"]) for i, c in enumerate(cands) if c.get("summary")]
    if not scored:
        return None
    good = [t for t in scored if t[1]["abd_all"]]
    if good:
        return max(good, key=lambda t: t[1]["amp_mean"])[0]
    return max(scored, key=lambda t: (t[1]["n_abd"], t[1]["amp_mean"]))[0]


def cmd_run(args) -> int:
    if args.round not in ROUND_NAMES:
        raise SystemExit(f"--round 는 {', '.join(ROUND_NAMES)} 중 하나다 (보정은 최대 2회, 계획서 5.0)")
    if (args.round == "ref") != bool(args.reference):
        raise SystemExit("--round ref 와 --reference 는 함께 쓴다")
    args.config = args.config or str(REF_CONFIG if args.reference else CONFIG)
    cfg = load_v2_config(args.config)
    seeds = parse_seeds(args.seeds) if args.seeds else list(CALIB_SEEDS)
    lo, hi = cfg.eval_seeds
    check_disjoint("보정 시드", seeds, range(lo, hi), args)
    specs = policy_specs(args.policies)
    cands = build_candidates(args, cfg)
    jobs = []
    for ci, c in enumerate(cands):
        for pn, sp in specs.items():
            for s in seeds:
                jobs.append(dict(cand=ci, policy=pn, spec=sp, seed=int(s), steps=args.steps, warmup=args.warmup,
                                 cfg=c["cfg"].to_dict()))
    workers = max(1, min(len(jobs), args.workers or max(1, (os.cpu_count() or 2) - 2)))
    print(f"[{args.round}] 후보 {len(cands)}개 × 정책 {len(specs)} × 시드 {len(seeds)} = {len(jobs)}잡, "
          f"{args.steps}스텝, 워커 {workers}", flush=True)
    t0 = time.time()
    rows: list[list[dict]] = [[] for _ in cands]
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as ex:
        for job, r in zip(jobs, ex.map(run_job, jobs)):
            rows[job["cand"]].append(r)
            msg = (f"  {cands[job['cand']]['label']} | {r['policy']:7s} s{r['seed']} "
                   f"수명 {r['lifespan']:.0f} 아사비중 {r['starve_share']:.3f}")
            if "pass" in r:
                hl = r["acf_half_life"]
                msg += (f" | V {r['v_cell_mean']:.3f} 하한 {r['floor_frac']:.3f} 반감기 "
                        f"{'없음' if hl is None else f'{hl}({r['acf_ratio']:.2f}배)'} 진폭 {r['amp']:.3f} "
                        f"600뒤 {r['persist']:.3f} (자연 {r['n_events']}건) {'통과' if r['pass']['all'] else '실패'}")
            print(msg + f" ({r['elapsed_s']:.0f}s)", flush=True)
    order = {pn: i for i, pn in enumerate(POLICY_ORDER)}
    out_cands = []
    for c, rs in zip(cands, rows):
        rs.sort(key=lambda r: (order[r["policy"]], r["seed"]))
        out_cands.append(dict(label=c["label"], params=c["params"], food_v=c.get("block"),
                              overrides=c.get("overrides", {}), config_digest=config_digest(c["cfg"]),
                              rows=rs, summary=summarize_candidate(rs)))
    sel = select(out_cands)
    blk0 = cfg.v2["features"].get("food_v") or {}
    data = dict(
        meta=dict(
            round=args.round, label=ROUND_LABEL[args.round], note=args.note,
            command="python gate_f.py " + " ".join(sys.argv[1:]),
            generated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            python=platform.python_version(), config=rel(args.config),
            config_version=cfg.v2.get("version"), config_food_v=blk0,
            seeds=seeds, steps=args.steps, warmup=args.warmup, every=EVERY, quiet=QUIET,
            policies=policy_meta(specs), elapsed_s=round(time.time() - t0, 1), workers=workers,
        ),
        candidates=out_cands, selected=sel,
    )
    path = ROUNDS / f"{args.round}.json"
    save_json(path, data)
    print(f"저장: {path}  ({time.time() - t0:.0f}s)")
    return cmd_report(args)


# --------------------------------------------------------------------- #
# 보고서
# --------------------------------------------------------------------- #


def load_rounds() -> dict[str, dict]:
    out = {}
    for name in ROUND_NAMES:
        p = ROUNDS / f"{name}.json"
        if p.exists():
            out[name] = json.loads(p.read_text(encoding="utf-8"))
    return out


def f3(x, nd=3) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def ok(b: bool) -> str:
    return "✓" if b else "✗"


def md_rows(rows: list[dict]) -> list[str]:
    L = ["| 정책 | 시드 | Σcap0 (셀) | (a) V/cap0 | 하한 셀 | (b) 반감기 (배) | (c) 진폭 | 600스텝 뒤 (울타리) "
         "| (d) 아사 비중 | a b c d |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        p = r["pass"]
        hl = r["acf_half_life"]
        hl_s = "없음" if hl is None else f"{hl} ({r['acf_ratio']:.2f})"
        L.append(f"| {POLICY_LABEL[r['policy']]} | {r['seed']} | {r['sum_cap0']:.1f} ({r['n_cells']}) | "
                 f"{f3(r['v_cell_mean'])} | {f3(r['floor_frac'])} | {hl_s} | {f3(r['amp'])} | "
                 f"{f3(r['persist'])} | {f3(r['starve_share'])} | "
                 f"{ok(p['a'])} {ok(p['b'])} {ok(p['c'])} {ok(p['d'])} |")
    return L


def md_aux(rows: list[dict]) -> list[str]:
    L = ["| 정책 | 시드 | r | V_L / V_R | F_L / F_R | F_r 표준편차 L / R | 섭취비 | x 상위 / 기준 | 뜯긴 셀 "
         "| 진폭(끝) | 자연 사건 600뒤 / 멈춤 직후 (건, 셀) | 진폭 cap0 구간 1~4 (상위 셀 수) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        bins = " / ".join(f"{f3(a, 2)}({n})" for a, n in zip(r["amp_bins"], r["n_top_bins"]))
        L.append(f"| {POLICY_LABEL[r['policy']]} | {r['seed']} | {r['r_mean']:.4f} | {f3(r['v_left'])} / "
                 f"{f3(r['v_right'])} | {f3(r['f_left'])} / {f3(r['f_right'])} | {f3(r['f_left_std'])} / "
                 f"{f3(r['f_right_std'])} | {f3(r['intake_ratio'], 2)} | {f3(r['x_top'], 2)} / "
                 f"{f3(r['x_ref'], 2)} | {f3(r['grazed_frac'], 2)} | {f3(r['amp_end'])} | "
                 f"{f3(r['persist_nat'])} / {f3(r['persist_nat_d0'])} ({r['n_events']}, {r['n_event_cells']}) | "
                 f"{bins} |")
    return L


def md_compare(ref: dict, cand: dict, ref_label: str, cand_label: str) -> list[str]:
    """v2.0(food_v 끔) 대비 생존 경제. 같은 정책·시드끼리."""
    by = {(r["policy"], r["seed"]): r for r in ref["candidates"][0]["rows"]}
    L = [f"- 왼쪽 {ref_label}, 오른쪽 {cand_label}. 창 t = 3000~30000.",
         "",
         "| 정책 | 시드 | 수명 | 아사 비중 | 아사율 (×1e-4) | 피식률 (×1e-4) | 번식률 (×1e-4) |",
         "|---|---|---|---|---|---|---|"]
    agg: dict[str, list] = {}
    for r in cand["rows"]:
        q = by.get((r["policy"], r["seed"]))
        if q is None:
            continue
        agg.setdefault(r["policy"], []).append((q, r))
        L.append(f"| {POLICY_LABEL[r['policy']]} | {r['seed']} | {q['lifespan']:.0f} → {r['lifespan']:.0f} | "
                 f"{q['starve_share']:.3f} → {r['starve_share']:.3f} | {q['starve_rate'] * 1e4:.2f} → "
                 f"{r['starve_rate'] * 1e4:.2f} | {q['pred_rate'] * 1e4:.2f} → {r['pred_rate'] * 1e4:.2f} | "
                 f"{q['repro_rate'] * 1e4:.2f} → {r['repro_rate'] * 1e4:.2f} |")
    for pn in POLICY_ORDER:
        if pn not in agg:
            continue
        qs, rs = zip(*agg[pn])

        def m(rows, k, s=1.0):
            return float(np.mean([x[k] for x in rows])) * s
        L.append(f"| **{POLICY_LABEL[pn]} 평균** | — | {m(qs, 'lifespan'):.0f} → {m(rs, 'lifespan'):.0f} | "
                 f"{m(qs, 'starve_share'):.3f} → {m(rs, 'starve_share'):.3f} | {m(qs, 'starve_rate', 1e4):.2f} → "
                 f"{m(rs, 'starve_rate', 1e4):.2f} | {m(qs, 'pred_rate', 1e4):.2f} → {m(rs, 'pred_rate', 1e4):.2f} | "
                 f"{m(qs, 'repro_rate', 1e4):.2f} → {m(rs, 'repro_rate', 1e4):.2f} |")
    L += ["", "| 정책 | 시드 | F_L / F_R (v2.0) | F_L / F_R (v2.0b) | F_r 표준편차 (v2.0) | F_r 표준편차 (v2.0b) |",
          "|---|---|---|---|---|---|"]
    for r in cand["rows"]:
        q = by.get((r["policy"], r["seed"]))
        if q is None:
            continue
        L.append(f"| {POLICY_LABEL[r['policy']]} | {r['seed']} | {f3(q['f_left'])} / {f3(q['f_right'])} | "
                 f"{f3(r['f_left'])} / {f3(r['f_right'])} | {f3(q['f_left_std'])} / {f3(q['f_right_std'])} | "
                 f"{f3(r['f_left_std'])} / {f3(r['f_right_std'])} |")
    return L


def gate_rounds(rounds: dict) -> list[str]:
    return [n for n in ("R0", "R1", "R2") if n in rounds]


def final_verdict(rounds: dict) -> dict | None:
    g = gate_rounds(rounds)
    if not g:
        return None
    last = rounds[g[-1]]
    sel = last.get("selected")
    if sel is None:
        return None
    c = last["candidates"][sel]
    return dict(round=g[-1], selected=sel, label=c["label"], params=c["params"], summary=c["summary"],
                passed=bool(c["summary"].get("passed")))


def cmd_report(args=None) -> int:
    rounds = load_rounds()
    if not rounds:
        raise SystemExit(f"회차 기록이 없다: {ROUNDS}")
    fv = final_verdict(rounds)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    L = ["# Gate F 보고서: v2.0b 먹이 2층 (환경 게이트)", "",
         f"> 자동 생성: `python gate_f.py report` ({now}). 회차 기록: `results/v2/gate_f/rounds/*.json`. "
         "계획서 0-6, 4.9.1, 6.2 F4, 9절.", ""]

    # --- 판정 ---
    L.append("## 판정")
    if fv:
        s = fv["summary"]
        n = s["n"]
        L += [f"- 종합: **{'통과' if fv['passed'] else '실패'}** — 마지막 회차 {ROUND_LABEL[fv['round']]}의 선택값 "
              f"`{fv['label']}`.",
              f"- 기준별 통과(정책·시드 {n}칸): (a) {s['n_pass']['a']}/{n}, (b) {s['n_pass']['b']}/{n}, "
              f"(c) {s['n_pass']['c']}/{n}, (d) {s['n_pass']['d']}/{n}, 모두 {s['n_pass']['all']}/{n}. "
              f"(c) 진폭 평균 {f3(s['amp_mean'])}(최소 {f3(s['amp_min'])}), 600스텝 뒤 평균 {f3(s['persist_mean'])}."]
        if not fv["passed"] and fv["round"] == "R2":
            L.append("- 보정 2회를 다 썼다(5.0). 계획서 0-6 의 다음 순서(로지스틱 조절값, v2.0b 범위 축소와 S7 미루기)는 "
                     "사람이 정한다.")
    L.append("")

    # --- 보정 이력 ---
    L += ["## 보정 이력", "", "| 회차 | 시험한 후보 | 이유·메모 | 선택 | 선택값 (a)(b)(d) 모두 지킴 | 선택값 판정 |",
          "|---|---|---|---|---|---|"]
    for name in gate_rounds(rounds):
        d = rounds[name]
        sel = d.get("selected")
        c = d["candidates"][sel] if sel is not None else None
        tried = "<br>".join(x["label"] for x in d["candidates"])
        L.append(f"| {ROUND_LABEL[name]} | {tried} | {d['meta'].get('note') or ''} | "
                 f"{c['label'] if c else '—'} | {ok(c['summary']['abd_all']) if c else '—'} | "
                 f"{('통과' if c['summary']['passed'] else '실패') if c else '—'} |")
    L.append("")

    # --- 해석(손으로 쓴 것) ---
    if NOTES.exists():
        L += ["## 해석", "", NOTES.read_text(encoding="utf-8").strip(), ""]

    # --- 조건 ---
    any_meta = next(iter(rounds.values()))["meta"]
    pm = any_meta["policies"]
    L += ["## 조건", "",
          f"- 보정 시드 {', '.join(map(str, any_meta['seeds']))} × {any_meta['steps']}스텝. 평가 시드 10000~10019·학습 "
          f"시드 [0, 1000) 와 겹치지 않는다(계획서 4.9.1 예비 측정과 0-6 사전 등록의 시드).",
          f"- 설정: v2.0b = `configs/v2_0b.yaml` 의 food_v 블록. 덮은 값: `recovery_half_lives` 학습 목록 → "
          f"[{DESIGN_HALF_LIFE}] (4.7 판정 실행 고정). α·하한·r 은 회차별 후보 값(아래). 지역 = 맵 좌우 절반.",
          "- 참고 세계 v2.0 = `configs/v2.yaml`(기능 모두 끔 = v1 세계).",
          "- 정책:"]
    for pn in POLICY_ORDER:
        if pn not in pm:
            continue
        m = pm[pn]
        if pn == "C2":
            L.append(f"  - {m['label']}: 행동 고정 {m['spec']['action']} (계획서 2.1)")
        elif pn == "learned":
            L.append(f"  - {m['label']}: `ckpt/final.zip` (sha1 {m.get('sha1')}), deterministic, sigmoid "
                     "(`policies/registry.py`)")
        else:
            p = m.get("params", {})
            L.append(f"  - {m['label']}: `{m.get('source')}` 의 튜닝값 (`tune_utility.py` 300 trial) — "
                     + ", ".join(f"{k} {v:.4f}" for k, v in p.items()))
    L += ["- 실행 명령 (회차별 전문, `herbivore_rl/` 에서):"]
    for name in ROUND_NAMES:
        if name in rounds:
            m = rounds[name]["meta"]
            L.append(f"  - {ROUND_LABEL[name]} ({m['generated']}, {m['elapsed_s']:.0f}s, 워커 {m['workers']}): "
                     f"`{m['command']}`")
    L += ["", "## 측정 정의", ""] + DEFINITIONS + [""]

    # --- 회차별 결과 ---
    L += ["## 회차별 결과", ""]
    for name in gate_rounds(rounds):
        d = rounds[name]
        L += [f"### {ROUND_LABEL[name]}", "", f"- 메모: {d['meta'].get('note') or '—'}",
              f"- 명령: `{d['meta']['command']}`", ""]
        for i, c in enumerate(d["candidates"]):
            s = c["summary"]
            tag = " (선택)" if i == d.get("selected") else ""
            L += [f"#### {c['label']}{tag} — {'통과' if s['passed'] else '실패'}", "",
                  f"- 통과 칸: (a) {s['n_pass']['a']}, (b) {s['n_pass']['b']}, (c) {s['n_pass']['c']}, "
                  f"(d) {s['n_pass']['d']} / {s['n']}. (c) 진폭 평균 {f3(s['amp_mean'])}, 최소 {f3(s['amp_min'])}. "
                  f"설정 digest {c['config_digest']}", ""]
            L += md_rows(c["rows"]) + [""]
            L += ["보조 지표 (해석용):", ""] + md_aux(c["rows"]) + [""]

    # --- v2.0 대비 ---
    if "ref" in rounds and fv:
        cand = rounds[fv["round"]]["candidates"][fv["selected"]]
        L += ["## v2.0 대비 생존 경제 (참고)", ""]
        L += md_compare(rounds["ref"], cand, "v2.0(food_v 끔)", f"v2.0b `{cand['label']}`") + [""]
        r0 = rounds.get("R0")
        if r0 and fv["round"] != "R0":
            L += [f"제안값 R0 `{r0['candidates'][r0['selected']]['label']}` 와의 비교:", ""]
            L += md_compare(rounds["ref"], r0["candidates"][r0["selected"]], "v2.0",
                            f"R0 `{r0['candidates'][r0['selected']]['label']}`") + [""]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    def strip(d):
        return {**d, "candidates": [{**c, "rows": [{k: v for k, v in r.items() if k != "series"} for r in c["rows"]]}
                                    for c in d["candidates"]]}
    save_json(OUT / "report.json", dict(
        meta=dict(generated=now, command="python gate_f.py report", criteria=CRIT,
                  window=[WARMUP, STEPS], every=EVERY, quiet=QUIET, top_frac=TOP_FRAC, ref_frac=REF_FRAC,
                  cap_bins=CAP_BINS, design_half_life=DESIGN_HALF_LIFE, definitions=DEFINITIONS),
        verdict=fv, rounds={k: strip(v) for k, v in rounds.items()},
    ))
    print(f"보고서: {OUT / 'report.md'}\n        {OUT / 'report.json'}")
    return 0


# --------------------------------------------------------------------- #
# 명령줄
# --------------------------------------------------------------------- #


def set_out(path: Path) -> None:
    global OUT, ROUNDS, NOTES
    OUT = path.resolve()
    ROUNDS, NOTES = OUT / "rounds", OUT / "notes.md"


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", default=None, help="출력 디렉터리. 기본 results/v2/gate_f (시험 실행은 다른 곳에)")
    p = argparse.ArgumentParser(description="Gate F — v2.0b 먹이 2층 환경 게이트 (계획서 0-6)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("run", parents=[common], help="회차 하나를 돌리고 보고서를 다시 만든다")
    s.add_argument("--round", required=True, help="R0 (제안값) | R1 | R2 (보정 1·2회차) | ref (v2.0 참고)")
    s.add_argument("--reference", action="store_true", help="food_v 끈 v2.0 세계(configs/v2.yaml)를 돌린다")
    s.add_argument("--config", default=None, help="기본 configs/v2_0b.yaml (--reference 면 configs/v2.yaml)")
    s.add_argument("--alpha", type=float, nargs="+", default=None, help="훼손 계수 α 후보")
    s.add_argument("--floor", type=float, nargs="+", default=None, help="V 하한(cap0 비율) 후보")
    s.add_argument("--half-life", type=float, nargs="+", default=None,
                   help=f"회복 반감기 h 후보(스텝). 기본 {DESIGN_HALF_LIFE} 하나 (4.7 판정 실행 고정)")
    s.add_argument("--regen-base", type=float, nargs="+", default=None,
                   help="재생률 r 의 v1 키 food_regen_base 후보(overrides). 기본은 v1 값")
    s.add_argument("--policies", nargs="+", choices=POLICY_ORDER, default=list(POLICY_ORDER))
    s.add_argument("--seeds", nargs="+", default=None, help="기본 20000 20001 20002")
    s.add_argument("--steps", type=int, default=STEPS)
    s.add_argument("--warmup", type=int, default=WARMUP)
    s.add_argument("--workers", type=int, default=None, help="기본 CPU 수 − 2")
    s.add_argument("--note", default="", help="보정 이력에 남길 이유·메모")
    s.add_argument("--allow-seed-overlap", action="store_true", help="평가 시드와 겹쳐도 진행 (진단용)")
    sub.add_parser("report", parents=[common], help="저장한 회차로 report.md·report.json 을 다시 만든다")
    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:  # pragma: no cover
        pass
    args = build_parser().parse_args(argv)
    if args.out:
        set_out(Path(args.out))
    if args.cmd == "run":
        if args.steps <= args.warmup + QUIET:
            raise SystemExit(f"--steps 는 --warmup + {QUIET} 보다 커야 한다")
        if (args.steps - args.warmup) % EVERY:
            raise SystemExit(f"--steps − --warmup 은 {EVERY} 의 배수여야 한다")
        return cmd_run(args)
    return cmd_report(args)


if __name__ == "__main__":
    sys.exit(main())
