"""Gate F — v2.0b 먹이 2층의 환경 게이트 (계획서 0-6, 4.9.1, 6.2 F4, 9절).

v2.0b 는 정책이 새로 쓸 입력·행동이 없어서 C2-seg 비교 대신, 정해 둔 정책으로 3만 스텝을 돌려 동역학이
설계대로인지 본다(5.0 환경 게이트). 정책 3종(v1 최적 상수 C2, v1 학습 정책, 튜닝 Utility) × 보정 시드 3개.

    python gate_f.py run --round R0 --alpha 0.5 --note "제안값 첫 실행"
    python gate_f.py run --round R1 --alpha 0.03 0.05 0.1 --note "보정 1회차 (사전 등록)"
    python gate_f.py run --round R2 --alpha ... --floor ... --half-life ... --regen-base ... --note "..."
    python gate_f.py run --round ref --reference --note "참고: food_v 끈 v2.0 세계"
    python gate_f.py report

R10 재판정(결과 디렉터리 results/v2/gate_f_r10, 사전 등록 그 디렉터리의 PREREG.md):

    python gate_f.py run --out results/v2/gate_f_r10 --round ref --reference --note "참고 v2.0"
    python gate_f.py run --out results/v2/gate_f_r10 --round R1 --alpha 0.03 --floor 0.1 --note "..."
    python gate_f.py run --out results/v2/gate_f_r10 --round R2 --alpha 0.03 0.05 --half-life 693 1386 2079 --floor 0.1
    python gate_f.py run --out results/v2/gate_f_r10 --round fixed --alpha 0.03 --half-life 693 --policies v21 c2v21
    python gate_f.py run --out results/v2/gate_f_r10 --round ref21 --reference --config configs/v2_1.yaml
    python gate_f.py report --out results/v2/gate_f_r10

- F4 정의는 `--f4-def` 로 고른다. `r10`(기본) = 10-02 승인 정의를 R10 에서 구현한 것이다: 상위·기준 셀을 섭식
  강도(창 안 누적 섭취/cap0) 순위로 고르고, 600스텝 시험은 상위 셀과 기준 셀을 함께 쉬게 한다(짝 휴식). 먹이 부족
  세계(공급 상한 Σ r·cap0 < 기초 수요)의 칸은 판정에서 빼고 따로 보고한다. `1002` = 10-02 판정 때 정의(누적 섭취
  순위, 상위 셀만 울타리, 9칸 모두 판정)다. 정의는 회차 기록 meta 의 `f4_def` 에 남고, 없으면 `1002` 로 읽는다.
  그래서 `report` 는 results/v2/gate_f(10-02 기록)를 그때 글 그대로 다시 만든다. 한 디렉터리에 정의를 섞지 않는다
  (run 이 거부한다).
- 회차 fixed(고정 정책 확인)·ref21(v2.1 참고)은 보정 횟수와 종합 판정에 들지 않는다. fixed 는 v2.1 세계에 food_v 를
  더한 configs/v2_1_0b.yaml 에 v2.1 출시 모델(s1a_g_s58, 결정)과 v2.1 C2 를 넣어 판정 칸 모두에서 (d) 아사 비중
  ≤ 0.4 인지 본다((a)(b)(c)는 보고만). ref21 은 같은 정책으로 food_v 를 끈 v2.1 세계다(생존 경제 비교).

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
from env_v2.world import FOOD_V_FLOOR_TOL, World, action_dim

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "v2" / "gate_f"
ROUNDS = OUT / "rounds"
NOTES = OUT / "notes.md"
CONFIG = ROOT / "configs" / "v2_0b.yaml"
REF_CONFIG = ROOT / "configs" / "v2.yaml"
FIXED_CONFIG = ROOT / "configs" / "v2_1_0b.yaml"     # 고정 정책 확인: v2.1 + food_v (학습 금지)
REF21_CONFIG = ROOT / "configs" / "v2_1.yaml"
V21_MODEL = ROOT / "ckpt" / "v2" / "s1a_g_s58.zip"   # v2.1 출시 모델 (results/v2/s1a/report.md, 커밋하지 않음)
S7_FIGURE = "results/v2/replay_s7_food_v.png"        # R10 실패 갈래의 S7 그림 (α 0.03, .mp4 는 로컬)

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
# v2.1 최적 상수 C2 (Gate E1-b 판정 results/v2/e1/judge_e1b.json final.c2, 행동 5 = speed 0.49 걷기)
C2V21_ACTION = [0.9709889334578663, 0.7849404966375042, 0.2182330585135458, 0.03358694847233987,
                0.4913744307309694]
POLICY_ORDER = ("C2", "learned", "utility", "v21", "c2v21")
V1_POLICIES = ("C2", "learned", "utility")          # 행동 4 (v2.0·v2.0b 세계)
V21_POLICIES = ("v21", "c2v21")                     # 행동 5 (speed 를 켠 v2.1 세계)
POLICY_ACT_DIM = {"C2": 4, "learned": 4, "utility": 4, "v21": 5, "c2v21": 5}
POLICY_LABEL = {"C2": "C2 v1 최적 상수", "learned": "v1 학습 정책", "utility": "Utility (튜닝)",
                "v21": "v2.1 출시 모델 s1a_g_s58", "c2v21": "C2 v2.1 최적 상수"}
# fixed·ref21 은 R10 회차다(보정 횟수·종합 판정 밖). 이름을 뒤에 붙여 예전 디렉터리의 보고서 순서가 그대로다
ROUND_NAMES = ("R0", "R1", "R2", "ref", "fixed", "ref21")
ROUND_LABEL = {"R0": "R0 제안값", "R1": "R1 보정 1회차", "R2": "R2 보정 2회차", "ref": "ref v2.0 참고",
               "fixed": "fixed 고정 정책 확인", "ref21": "ref21 v2.1 참고"}
REF_ROUNDS = ("ref", "ref21")                       # food_v 를 끈 참고 회차 (--reference)
FIXED_JUDGE_POLICIES = ("v21",)                     # 고정 정책 확인의 판정 정책(v2.1 출시 모델). c2v21 은 보고만

# F4 정의. 회차 meta 의 f4_def 가 없으면 F4_OLD 다(10-02 기록 results/v2/gate_f)
F4_OLD, F4_R10 = "1002", "r10"
F4_DEFS = (F4_OLD, F4_R10)
PERSIST_TOL = 1e-6        # r10: 600스텝 뒤와 예측 2^(−600/h)·진폭(끝)의 허용 차(진폭(끝)이 float32 표본이라 약 1e-7)

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

# R10 정의 (10-02 승인 F4 정의, 결정 R10, results/v2/gate_f_r10/PREREG.md). 공통·(a)·(b)·(d)는 위와 같다
DEFINITIONS_R10 = DEFINITIONS[:3] + [
    "- (c) 흔적 진폭(F4, 10-02 승인 정의). cap0 > 0 셀을 cap0 순위로 4등분해 cap0 구간을 만든다. 섭식 강도 = 창 안 "
    "누적 섭취 / cap0. 상위 셀 = 섭식 강도가 가장 큰 ceil(10%) 셀(맵 전체 순위, 같으면 셀 번호 순). 기준 셀 = 각 "
    "cap0 구간 안에서 섭식 강도가 작은 쪽 절반(구간 셀 수의 floor(50%), 최소 1, 같으면 셀 번호 순)에서 상위 셀을 뺀 "
    "것. 기준 셀이 남지 않은 구간의 상위 셀은 진폭에서 뺀다. 진폭 = 상위 셀마다 (그 셀 cap0 구간 기준 셀들의 창 평균 "
    "V/cap0 평균 − 그 셀의 창 평균 V/cap0)의 평균. 600스텝 뒤(짝 휴식) = t = 30000 에서 상위 셀과 모든 기준 셀에 "
    "함께 울타리를 쳐 섭식을 막고(그 셀들의 섭취 0, 나머지 세계·정책·다른 셀의 섭식은 그대로) 600스텝 더 돌린 뒤, "
    "상위 셀마다 (같은 구간 기준 셀 평균 V/cap0 − 그 셀 V/cap0)의 평균. 울타리 안 셀은 휴식 회복만 하므로 "
    "600스텝 뒤 = 2^(−600/h)·진폭(끝)이다(h 693 에서 0.549배). 실행마다 예측과의 차가 1e-6 미만인지 확인한다. "
    "통과: 진폭 ≥ 0.2 이고 600스텝 뒤 ≥ 0.1 (h 693 에서 진폭(끝) ≥ 0.182 와 같다). 자연 사건은 보조 열로만 낸다.",
    DEFINITIONS[4],
    "- 판정 칸: 먹이 부족 세계의 칸은 판정에서 빼고 따로 보고한다. 먹이 부족 = 공급 상한 Σ r·cap0 < 기초 수요 "
    "N·energy_drain/food_energy_per_unit (r = 세계의 셀별 재생률 regen_field, 은신처 0.3배 포함. 기초 수요는 보행과 "
    "무관한 기초 대사를 먹이 단위로 바꾼 값). 종합 판정 = 마지막 보정 회차 선택값이 판정 칸 모두에서 (a)~(d) 통과. "
    "회차 선택값 = (a)(b)(d)를 판정 칸 모두에서 지키는 후보 가운데 판정 칸 진폭 평균이 가장 큰 것이다((b)는 후보마다 "
    "자기 h 로 잰다). 9칸 전체 통과 수는 참고로 함께 낸다.",
    "- 고정 정책 확인(fixed): 같은 측정에서 판정 정책(v2.1 출시 모델 s1a_g_s58, 결정 모드)의 판정 칸 모두 (d) 아사 "
    "비중 ≤ 0.4 면 통과. v2.1 C2 와 (a)(b)(c)는 보고만 한다.",
    "- 참고 열: 수명 = 창 안에서 죽은 개체의 평균 나이(스텝), 아사율·피식률 = 창 안 사망 / (27,000 × 128). "
    "F_r·V_r = 좌우 절반의 ΣF/Σcap0·ΣV/Cap0 창 평균, F_r 표준편차 = 그 시계열의 창 안 표준편차(9절 신호). "
    "강도비 = 상위 셀 섭식 강도 합 / 그 셀 구간 기준 셀 평균 섭식 강도의 합. x = α·r_eff/ρ 의 중앙값"
    "(상위 셀 / 상위 셀이 있는 구간의 기준 셀, r_eff = 스텝당 섭취 / 창 평균 V, 4.9.1 (b) 해석). "
    "진폭(끝) = t = 30000 한 시점의 진폭(= 울타리 직전), 예측 = 2^(−600/h)·진폭(끝). 자연 사건 = 상위 셀에서 마지막 "
    "섭취(창 안) 뒤 600스텝 동안 섭취가 없었던 사건의 600스텝 시점 차와 그 사건의 멈춤 직후 차.",
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


def trace_key(cap: np.ndarray, eaten: np.ndarray, f4_def: str = F4_OLD) -> np.ndarray:
    """(c) 셀 순위 열쇠. `1002` 는 창 안 누적 섭취, `r10` 은 섭식 강도 = 누적 섭취/cap0 (cap0 > 0 셀만 온다)."""
    if f4_def == F4_OLD:
        return eaten
    if f4_def == F4_R10:
        return np.asarray(eaten, dtype=np.float64) / np.asarray(cap, dtype=np.float64)
    raise ValueError(f"F4 정의는 {F4_DEFS} 중 하나다: {f4_def!r}")


def trace_sets(cap: np.ndarray, eaten: np.ndarray, f4_def: str = F4_OLD):
    """(c) 상위 셀(맵 전체 순위 상위 ceil(10%))과 cap0 구간별 기준 셀(구간 안 순위 하위 절반에서 상위 셀을 뺀 것).

    순위 열쇠는 `trace_key`(정의 `1002` 누적 섭취, `r10` 섭식 강도). 같으면 셀 번호 순(안정 정렬)이다.
    """
    m = len(cap)
    key = trace_key(cap, eaten, f4_def)
    bin_of = cap_bins(cap)
    top = np.argsort(-key, kind="stable")[:max(1, int(math.ceil(TOP_FRAC * m)))]
    is_top = np.zeros(m, dtype=bool)
    is_top[top] = True
    refs = []
    for b in range(CAP_BINS):
        idx = np.flatnonzero(bin_of == b)
        idx = idx[np.argsort(key[idx], kind="stable")][:max(1, int(REF_FRAC * len(idx)))] if idx.size else idx
        refs.append(idx[~is_top[idx]])
    return bin_of, top, refs


def gap_after(v_after: np.ndarray, bin_of: np.ndarray, top: np.ndarray, refs: list) -> float:
    """울타리 시험 뒤 V/cap0 (cells,) → 상위 셀마다 (같은 구간 기준 셀 평균 − 그 셀)의 평균."""
    r = np.array([v_after[x].mean() if x.size else np.nan for x in refs])
    return float((r[bin_of[top]] - v_after[top]).mean())


def trace_metrics(X: np.ndarray, cap: np.ndarray, eaten: np.ndarray, ev_s: np.ndarray, ev_i: np.ndarray,
                  lag: int, v_after: np.ndarray | None = None, f4_def: str = F4_OLD) -> dict:
    """(c) 흔적 진폭과 지속. X (n, cells) 창 안 V/cap0 표본, cap cap0, eaten 창 안 누적 섭취(셀별),
    v_after 울타리 600스텝 뒤 V/cap0 (cells,) — 판정하는 지속(persist). 울타리는 정의 `1002` 면 상위 셀만,
    `r10` 이면 상위 셀과 기준 셀이다(`run_job`). 셀 고르기는 `trace_sets(cap, eaten, f4_def)`.
    (ev_s, ev_i) 자연 사건(상위 셀이 스스로 600스텝 안 뜯김)의 표본 번호·셀, lag = 600/EVERY — 보조 열."""
    nan = float("nan")
    bin_of, top, refs = trace_sets(cap, eaten, f4_def)
    ok = np.array([r.size > 0 for r in refs])
    top = top[ok[bin_of[top]]]                     # 기준 셀이 없는 구간(셀이 아주 적은 세계)의 상위 셀은 뺀다
    if not top.size:
        return dict(amp=nan, amp_end=nan, persist=nan, persist_nat=nan, persist_nat_d0=nan, n_events=0,
                    n_event_cells=0, n_top=0, intake_ratio=nan, intensity_ratio=nan, amp_bins=[nan] * CAP_BINS,
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
    inten = trace_key(cap, eaten, F4_R10)
    ref_int = np.array([inten[r].mean() if r.size else nan for r in refs])
    den_i = float(ref_int[bin_of[top]].sum())
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
        intensity_ratio=float(inten[top].sum()) / den_i if den_i > 0 else float("inf"),
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
    먹지 못한다. 환경 코드(env_v2)는 바꾸지 않는다. speed 를 켠 세계는 `World.step` 이 보행 섭식 배수 `mult` 를
    함께 넘기므로 그대로 넘긴다(None 이면 v1 섭식).
    """

    excl: np.ndarray | None = None

    def _eat(self, e_drained, mult=None):
        if self.excl is None:
            return super()._eat(e_drained, mult)
        F = self.food.reshape(-1)               # 연속 배열의 뷰
        saved = F[self.excl].copy()
        F[self.excl] = 0.0
        try:
            return super()._eat(e_drained, mult)
        finally:
            F[self.excl] = saved


def food_supply(w: World, cfg) -> dict:
    """먹이 부족 세계 판정 값(R10, PREREG). 세계를 만든 직후(reset 뒤) 값이다.

    공급 상한 = Σ r·cap0 (r = 세계의 셀별 재생률 `regen_field`, 은신처 0.3배와 재생 배수 포함, cap0 = 0 셀은 0).
    재생은 F += r·(목표 − F) 이고 목표(v1 cap0, v2.0b V)가 cap0 이하라 한 스텝 재생량은 이 값을 넘지 않는다.
    기초 수요 = N·energy_drain/food_energy_per_unit (보행과 무관한 기초 대사를 먹이 단위로 바꾼 값).
    공급 상한 < 기초 수요 면 먹이 부족 세계다.
    """
    supply = float((w.regen_field * w.food_cap).sum())
    need = float(w.N * cfg.energy_drain / cfg.food_energy_per_unit)
    return dict(supply_max=supply, need=need, supply_ratio=supply / need, food_scarce=bool(supply < need))


def run_job(job: dict) -> dict:
    """정책 하나 × 시드 하나. 프로세스 경계를 넘으므로 인자는 dict 하나다."""
    from policies.registry import make_policy

    t_start = time.time()
    cfg = Config(job["cfg"])
    policy = make_policy(job["spec"])
    seed, steps, warmup = int(job["seed"]), int(job["steps"]), int(job["warmup"])
    f4 = job.get("f4_def", F4_OLD)
    w = ExclosureWorld(cfg, seeds=[seed])
    supply = food_supply(w, cfg)
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
        f4_def=f4, **supply,
    )
    k = SERIES_EVERY // EVERY
    series = {"t": list(range(warmup, steps + 1, SERIES_EVERY)),
              "F_L": reg[::k, 4].tolist(), "F_R": reg[::k, 5].tolist()}
    if on:
        alpha, rho, h = float(w._fv["alpha"]), float(w.food_v_rho), float(w.food_v_half_life)
        eaten = w._fv_eaten.reshape(-1)[pos] - base["eaten"]
        bin_of, top, refs = trace_sets(cap, eaten, f4)
        # (c) 울타리 시험: 창이 끝난 t = steps 에서 울타리 셀의 섭식만 막고 QUIET 스텝 더 돌린다(창 지표에는 안
        # 들어감). 정의 1002 는 상위 셀만, r10 은 상위 셀과 모든 기준 셀을 함께 막는다(짝 휴식)
        fenced = top if f4 == F4_OLD else np.concatenate([top, *refs])
        w.excl = pos[fenced]
        for _ in range(QUIET):
            w.step(policy(w.observe()))
        assert (w._fv_last_eat.reshape(-1)[w.excl] <= steps).all(), "울타리 안에서 섭식이 일어났다"
        v_after = w.food_v.reshape(-1)[pos] / cap
        tm = trace_metrics(X, cap, eaten, np.asarray(ev_s, dtype=np.int64), np.asarray(ev_i, dtype=np.int64),
                           QUIET // EVERY, v_after=v_after, f4_def=f4)
        if f4 == F4_R10:
            # 짝 휴식이면 울타리 안 셀은 휴식 회복 V += ρ·(cap0 − V) 만 해서 1 − V/cap0 가 셀마다 같은 배수
            # (1 − ρ)^600 = 2^(−600/h) 로 줄고, 진폭은 그 차의 평균이라 같은 배수가 된다(수학적으로 정확한 항등식).
            # 진폭(끝)이 float32 표본이라 차는 1e-7 정도다
            kq = 2.0 ** (-QUIET / h)
            pred = kq * tm["amp_end"]
            if tm["n_top"]:
                assert abs(tm["persist"] - pred) < PERSIST_TOL, ("짝 휴식 항등식이 깨졌다", tm["persist"], pred)
            row.update(n_fenced=int(fenced.size), persist_k=kq, persist_pred=pred)
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
    """정책 이름 → `policies.registry` 스펙. learned·v21 은 결정 모드(registry 의 learned 는 늘 deterministic)."""
    specs = {"C2": {"kind": "fixed", "action": list(C2_ACTION)},
             "learned": {"kind": "learned", "model": str((ROOT / "ckpt" / "final.zip").resolve())},
             "utility": {"kind": "utility"},
             "v21": {"kind": "learned", "model": str(V21_MODEL.resolve())},
             "c2v21": {"kind": "fixed", "action": list(C2V21_ACTION)}}
    return {n: specs[n] for n in names}


def sha256_of(path) -> str | None:
    import hashlib

    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def policy_meta(specs: dict) -> dict:
    from policies.utility import BEST_PATH, load_best_params

    out = {}
    for n, sp in specs.items():
        m = {"label": POLICY_LABEL[n], "spec": sp}
        if n == "learned":
            m.update(sha1=model_fingerprint(sp["model"]), deterministic=True)
        if n == "utility":
            m.update(params=load_best_params(), source=str(BEST_PATH.relative_to(ROOT)).replace("\\", "/"))
        if n == "v21":
            m.update(sha1=model_fingerprint(sp["model"]), sha256=sha256_of(sp["model"]), deterministic=True,
                     source=rel(sp["model"]))
        if n == "c2v21":
            m.update(source="results/v2/e1/judge_e1b.json final.c2")
        out[n] = m
    return out


def policy_line(pn: str, m: dict) -> str:
    """보고서 '조건' 의 정책 한 줄(앞의 '  - ' 포함). C2·learned·utility 는 10-02 보고서 글 그대로다."""
    if pn == "C2":
        return f"  - {m['label']}: 행동 고정 {m['spec']['action']} (계획서 2.1)"
    if pn == "learned":
        return (f"  - {m['label']}: `ckpt/final.zip` (sha1 {m.get('sha1')}), deterministic, sigmoid "
                "(`policies/registry.py`)")
    if pn == "v21":
        return (f"  - {m['label']}: `{m.get('source')}` (sha256 {m.get('sha256')}), deterministic, sigmoid "
                "(`policies/registry.py`, 출시 결정 모드)")
    if pn == "c2v21":
        return f"  - {m['label']}: 행동 고정 {m['spec']['action']} ({m.get('source')})"
    p = m.get("params", {})
    return (f"  - {m['label']}: `{m.get('source')}` 의 튜닝값 (`tune_utility.py` 300 trial) — "
            + ", ".join(f"{k} {v:.4f}" for k, v in p.items()))


def candidate_label(p: dict | None, version: str = "2.0") -> str:
    if p is None:
        return f"food_v 끔 (v{version})"
    s = f"α {p['alpha']:g} · 하한 {p['floor']:g} · h {p['half_life']:g}"
    return s + (f" · r_base {p['regen_base']:g}" if p.get("regen_base") is not None else "")


def build_candidates(args, cfg) -> list[dict]:
    """명령줄 값 목록의 곱 → 후보. 생략한 계수는 설정 파일의 food_v 블록 값이다.

    --reference 는 food_v 를 끈 설정이면 된다(ref = v2.0, ref21 = v2.1 처럼 다른 기능은 켜져 있어도 된다).
    """
    if args.reference:
        if (cfg.v2["features"].get("food_v") or {}).get("enabled"):
            raise SystemExit(f"--reference 는 food_v 를 끈 설정이어야 한다: {args.config}")
        return [dict(label=candidate_label(None, str(cfg.v2.get("version") or "2.0")), params=None, cfg=cfg)]
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


def judged_rows(rows: list[dict], f4_def: str = F4_OLD) -> list[dict]:
    """판정 칸. 정의 r10 은 먹이 부족 세계(`food_supply`)의 칸을 뺀다. 1002 는 모든 칸이다."""
    if f4_def == F4_OLD:
        return list(rows)
    return [r for r in rows if not r.get("food_scarce", False)]


def n_pass_of(P: list[dict]) -> dict:
    return {k: sum(p[k] for p in P) for k in ("a", "b", "c", "d", "all")}


def summarize_candidate(rows: list[dict], f4_def: str = F4_OLD) -> dict:
    """후보 하나의 정책·시드 묶음 요약 (선택 규칙에 쓰는 값).

    정의 1002 는 10-02 기록과 같은 키·값이다. r10 은 판정 칸(`judged_rows`)으로 같은 키를 계산하고, 9칸 전체
    통과 수(n_total·n_pass_total), 먹이 부족 칸, d_all((d)가 모든 정책의 판정 칸에서 통과, 참고값. 고정 정책 확인
    판정은 `fixed_verdict` 가 판정 정책만으로 한다), 600스텝 뒤와 예측의 최대 차를 더한다. 판정 칸이 없으면 통과가
    아니다.
    """
    if not rows or "pass" not in rows[0]:
        return {}
    if f4_def == F4_OLD:
        P = [r["pass"] for r in rows]
        amps = [r["amp"] for r in rows]
        return dict(
            n=len(rows), n_pass=n_pass_of(P),
            abd_all=all(p["a"] and p["b"] and p["d"] for p in P),
            n_abd=sum(p["a"] and p["b"] and p["d"] for p in P),
            amp_mean=float(np.mean(amps)), amp_min=float(np.min(amps)),
            persist_mean=finite_mean([r["persist"] for r in rows]),
            passed=all(p["all"] for p in P),
        )
    J = judged_rows(rows, f4_def)
    P = [r["pass"] for r in J]
    amps = [r["amp"] for r in J]
    nan = float("nan")
    errs = [abs(r["persist"] - r["persist_pred"]) for r in rows
            if r.get("persist_pred") is not None and math.isfinite(r["persist_pred"]) and math.isfinite(r["persist"])]
    return dict(
        n=len(J), n_pass=n_pass_of(P),
        abd_all=bool(P) and all(p["a"] and p["b"] and p["d"] for p in P),
        n_abd=sum(p["a"] and p["b"] and p["d"] for p in P),
        amp_mean=float(np.mean(amps)) if amps else nan, amp_min=float(np.min(amps)) if amps else nan,
        persist_mean=finite_mean([r["persist"] for r in J]),
        passed=bool(P) and all(p["all"] for p in P),
        d_all=bool(P) and all(p["d"] for p in P),
        n_total=len(rows), n_pass_total=n_pass_of([r["pass"] for r in rows]),
        amp_mean_total=finite_mean([r["amp"] for r in rows]),
        scarce=[[r["policy"], r["seed"]] for r in rows if r.get("food_scarce", False)],
        persist_pred_err_max=max(errs) if errs else nan,
    )


def select(cands: list[dict]) -> int | None:
    """회차 선택값: (a)(b)(d)를 모든 정책·시드에서 지키는 후보 중 진폭 평균 최대. 없으면 (a)(b)(d) 통과 수 최대.

    요약(`summarize_candidate`)이 판정 칸으로 계산되므로 정의 r10 에서는 '모든 판정 칸'이다."""
    scored = [(i, c["summary"]) for i, c in enumerate(cands) if c.get("summary")]
    if not scored:
        return None
    good = [t for t in scored if t[1]["abd_all"]]
    if good:
        return max(good, key=lambda t: t[1]["amp_mean"])[0]
    return max(scored, key=lambda t: (t[1]["n_abd"], t[1]["amp_mean"]))[0]


def round_f4_def(d: dict) -> str:
    """회차 기록의 F4 정의. meta 에 없으면 10-02 기록이라 1002 다."""
    return d["meta"].get("f4_def", F4_OLD)


DEFAULT_CONFIG = {"ref": REF_CONFIG, "ref21": REF21_CONFIG, "fixed": FIXED_CONFIG}   # 나머지 회차는 CONFIG


def cmd_run(args) -> int:
    if args.round not in ROUND_NAMES:
        raise SystemExit(f"--round 는 {', '.join(ROUND_NAMES)} 중 하나다 (보정은 최대 2회, 계획서 5.0)")
    if (args.round in REF_ROUNDS) != bool(args.reference):
        raise SystemExit(f"--round {'·'.join(REF_ROUNDS)} 와 --reference 는 함께 쓴다")
    if args.round in ("fixed", "ref21") and args.f4_def != "r10":
        raise SystemExit("--round fixed·ref21 은 R10 회차라 --f4-def r10 으로만 돈다(10-02 기록 디렉터리를 지킨다)")
    # 한 디렉터리에 F4 정의를 섞지 않는다(예전 결과 디렉터리에 새 정의 회차가 끼는 것을 막는다)
    other = sorted({round_f4_def(d) for n, d in load_rounds().items() if n != args.round} - {args.f4_def})
    if other:
        raise SystemExit(f"{ROUNDS} 의 다른 회차는 F4 정의 {other} 다. --f4-def {args.f4_def} 회차를 섞지 않는다 "
                         "(정의마다 --out 을 따로 쓴다)")
    args.config = args.config or str(DEFAULT_CONFIG.get(args.round, CONFIG))
    args.policies = args.policies or list(V21_POLICIES if args.round in ("fixed", "ref21") else V1_POLICIES)
    cfg = load_v2_config(args.config)
    ad = action_dim(cfg)
    bad = [pn for pn in args.policies if POLICY_ACT_DIM[pn] != ad]
    if bad:
        raise SystemExit(f"정책 {bad} 의 행동 수가 {args.config} 세계의 행동 수 {ad} 와 다르다 "
                         f"(행동 4: {', '.join(V1_POLICIES)}, 행동 5: {', '.join(V21_POLICIES)})")
    seeds = parse_seeds(args.seeds) if args.seeds else list(CALIB_SEEDS)
    lo, hi = cfg.eval_seeds
    check_disjoint("보정 시드", seeds, range(lo, hi), args)
    specs = policy_specs(args.policies)
    missing = [sp["model"] for sp in specs.values() if sp["kind"] == "learned" and not Path(sp["model"]).exists()]
    if missing:
        raise SystemExit(f"학습 정책 파일이 없다: {missing}")
    cands = build_candidates(args, cfg)
    jobs = []
    for ci, c in enumerate(cands):
        for pn, sp in specs.items():
            for s in seeds:
                jobs.append(dict(cand=ci, policy=pn, spec=sp, seed=int(s), steps=args.steps, warmup=args.warmup,
                                 cfg=c["cfg"].to_dict(), f4_def=args.f4_def))
    workers = max(1, min(len(jobs), args.workers or max(1, (os.cpu_count() or 2) - 2)))
    print(f"[{args.round}] 후보 {len(cands)}개 × 정책 {len(specs)} × 시드 {len(seeds)} = {len(jobs)}잡, "
          f"{args.steps}스텝, 워커 {workers}, F4 정의 {args.f4_def}", flush=True)
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
                if "persist_pred" in r:
                    msg += f" (600뒤 예측 {r['persist_pred']:.3f})"
            if args.f4_def == F4_R10 and r["food_scarce"]:
                msg += f" [먹이 부족 {r['supply_ratio']:.2f}배, 판정 제외]"
            print(msg + f" ({r['elapsed_s']:.0f}s)", flush=True)
    order = {pn: i for i, pn in enumerate(POLICY_ORDER)}
    out_cands = []
    for c, rs in zip(cands, rows):
        rs.sort(key=lambda r: (order[r["policy"]], r["seed"]))
        out_cands.append(dict(label=c["label"], params=c["params"], food_v=c.get("block"),
                              overrides=c.get("overrides", {}), config_digest=config_digest(c["cfg"]),
                              rows=rs, summary=summarize_candidate(rs, args.f4_def)))
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
            f4_def=args.f4_def,
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


def md_rows(rows: list[dict], r10: bool = False) -> list[str]:
    fence = "짝 휴식" if r10 else "울타리"
    L = ["| 정책 | 시드 | Σcap0 (셀) | (a) V/cap0 | 하한 셀 | (b) 반감기 (배) | (c) 진폭 | "
         f"600스텝 뒤 ({fence}) | (d) 아사 비중 | a b c d |",
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


def md_aux(rows: list[dict], r10: bool = False) -> list[str]:
    """보조 지표 표. r10 은 공급/수요 열, 섭취비 대신 강도비, 진폭(끝) 옆에 600스텝 뒤 예측을 낸다."""
    if r10:
        L = ["| 정책 | 시드 | 공급/수요 | r | V_L / V_R | F_L / F_R | F_r 표준편차 L / R | 강도비 | x 상위 / 기준 "
             "| 뜯긴 셀 | 진폭(끝) / 600뒤 예측 | 자연 사건 600뒤 / 멈춤 직후 (건, 셀) | 진폭 cap0 구간 1~4 (상위 셀 수) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    else:
        L = ["| 정책 | 시드 | r | V_L / V_R | F_L / F_R | F_r 표준편차 L / R | 섭취비 | x 상위 / 기준 | 뜯긴 셀 "
             "| 진폭(끝) | 자연 사건 600뒤 / 멈춤 직후 (건, 셀) | 진폭 cap0 구간 1~4 (상위 셀 수) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        bins = " / ".join(f"{f3(a, 2)}({n})" for a, n in zip(r["amp_bins"], r["n_top_bins"]))
        head = f"| {POLICY_LABEL[r['policy']]} | {r['seed']} | "
        if r10:
            head += f"{f3(r.get('supply_ratio'), 2)} | "
        ratio = f3(r.get("intensity_ratio"), 2) if r10 else f3(r["intake_ratio"], 2)
        end = f"{f3(r['amp_end'])} / {f3(r.get('persist_pred'))}" if r10 else f3(r["amp_end"])
        L.append(f"{head}{r['r_mean']:.4f} | {f3(r['v_left'])} / "
                 f"{f3(r['v_right'])} | {f3(r['f_left'])} / {f3(r['f_right'])} | {f3(r['f_left_std'])} / "
                 f"{f3(r['f_right_std'])} | {ratio} | {f3(r['x_top'], 2)} / "
                 f"{f3(r['x_ref'], 2)} | {f3(r['grazed_frac'], 2)} | {end} | "
                 f"{f3(r['persist_nat'])} / {f3(r['persist_nat_d0'])} ({r['n_events']}, {r['n_event_cells']}) | "
                 f"{bins} |")
    return L


def md_compare(ref: dict, cand: dict, ref_label: str, cand_label: str,
               tags: tuple[str, str] = ("v2.0", "v2.0b"), with_f: bool = True,
               per_cell: bool = True) -> list[str]:
    """참고 세계(food_v 끔) 대비 생존 경제. 같은 정책·시드끼리. tags = 둘째 표(F_r) 머리의 (참고, 후보) 이름.
    r10 보고서는 정책별 평균 행만 내고(per_cell False, 칸별 값은 report.json) 둘째 표를 내지 않는다(with_f False,
    후보 쪽 F_r 는 보조 지표 표에 있다)."""
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
        if not per_cell:
            continue
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
    if not with_f:
        return L
    t0, t1 = tags
    L += ["", f"| 정책 | 시드 | F_L / F_R ({t0}) | F_L / F_R ({t1}) | F_r 표준편차 ({t0}) | F_r 표준편차 ({t1}) |",
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


def fixed_verdict(rounds: dict) -> dict | None:
    """고정 정책 확인(fixed): 판정 정책(`FIXED_JUDGE_POLICIES`, v2.1 출시 모델)의 판정 칸 모두에서 (d) 아사 비중
    ≤ 0.4 면 통과. 다른 정책(v2.1 C2)과 (a)(b)(c)는 보고만 한다. 판정 정책의 판정 칸이 없으면 통과가 아니다."""
    d = rounds.get("fixed")
    sel = d.get("selected") if d else None
    if sel is None:
        return None
    c = d["candidates"][sel]
    J = [r for r in judged_rows(c["rows"], F4_R10) if r["policy"] in FIXED_JUDGE_POLICIES]
    n_d = sum(bool(r["pass"]["d"]) for r in J)
    return dict(round="fixed", selected=sel, label=c["label"], params=c["params"], summary=c["summary"],
                judge_policies=list(FIXED_JUDGE_POLICIES), n=len(J), n_d=n_d,
                starve_share_max=max((r["starve_share"] for r in J), default=None),
                passed=bool(J) and n_d == len(J))


def dir_f4_def(rounds: dict) -> str:
    """디렉터리의 F4 정의. 회차마다 다르면 멈춘다(정의마다 디렉터리를 따로 쓴다)."""
    defs = sorted({round_f4_def(d) for d in rounds.values()})
    if len(defs) > 1:
        raise SystemExit(f"{ROUNDS} 에 F4 정의가 섞여 있다: {defs}")
    return defs[0]


def history_table(rounds: dict, abd_head: str) -> list[str]:
    L = ["## 보정 이력", "", f"| 회차 | 시험한 후보 | 이유·메모 | 선택 | {abd_head} | 선택값 판정 |",
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
    return L


def commands_list(rounds: dict) -> list[str]:
    L = ["- 실행 명령 (회차별 전문, `herbivore_rl/` 에서):"]
    for name in ROUND_NAMES:
        if name in rounds:
            m = rounds[name]["meta"]
            L.append(f"  - {ROUND_LABEL[name]} ({m['generated']}, {m['elapsed_s']:.0f}s, 워커 {m['workers']}): "
                     f"`{m['command']}`")
    return L


def report_1002(rounds: dict, fv: dict | None, now: str) -> list[str]:
    """10-02 정의(1002) 보고서. results/v2/gate_f 의 report.md 를 생성 시각 말고는 글자 그대로 다시 만든다."""
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
    L += history_table(rounds, "선택값 (a)(b)(d) 모두 지킴")

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
    L += [policy_line(pn, pm[pn]) for pn in POLICY_ORDER if pn in pm]
    L += commands_list(rounds)
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
    return L


def next_step_r10(fv: dict, fx: dict | None) -> str:
    """R10 의 사전 결정 갈래(계획서 0-6·10절 R10, PREREG). 사람 결정을 기다리지 않는다."""
    if fv["passed"]:
        if fx is None:
            return "F 통과. 고정 정책 확인(`--round fixed`)을 돌린다."
        if fx["passed"]:
            return ("F 와 고정 정책 확인을 모두 통과해 v2.0b 는 학습 분포에 넣을 수 있는 선택지가 된다. 이번 창(v2.4)에는 "
                    "넣지 않는다(한 버전에 기능 하나, R11 미결).")
        return "F 는 통과했지만 고정 정책 확인이 실패해 v2.0b 는 학습 분포에 넣지 않는다."
    if fv["round"] == "R2":
        return (f"보정 2회를 다 썼다. S7 은 기존 그림(`{S7_FIGURE}`·`.mp4`, α 0.03)으로 대신하고 v2.0b 는 학습 분포에 "
                "넣지 않는다. 회차를 더 하지 않는다.")
    return ("남은 보정 회차 R2 를 1회 한다(PREREG 의 격자·선택 규칙). R2 도 실패하면 S7 은 기존 그림으로 대신하고 "
            "v2.0b 는 학습 분포에 넣지 않는다.")


def scarce_table(rounds: dict) -> list[str]:
    """시드마다 공급 상한·기초 수요(먹이 부족 세계). 회차 순서로 처음 나온 칸의 값이다."""
    first, vals = {}, {}
    for name in ROUND_NAMES:
        for c in (rounds.get(name) or {}).get("candidates", []):
            for r in c["rows"]:
                if "supply_max" in r:
                    first.setdefault(r["seed"], r)
                    vals.setdefault(r["seed"], set()).add(round(r["supply_max"], 9))
    if not first:
        return []
    L = ["| 시드 | Σcap0 (셀) | 공급 상한 Σ r·cap0 | 기초 수요 | 공급/수요 | 먹이 부족 (판정 제외) |",
         "|---|---|---|---|---|---|"]
    for s in sorted(first):
        r = first[s]
        L.append(f"| {s} | {r['sum_cap0']:.1f} ({r['n_cells']}) | {r['supply_max']:.3f} | {r['need']:.3f} | "
                 f"{r['supply_ratio']:.2f} | {'예' if r['food_scarce'] else '아니오'} |")
    if any(len(v) > 1 for v in vals.values()):
        L.append("- 회차·후보마다 공급 상한이 다른 시드가 있다(r 을 바꾼 후보). 판정 칸은 칸마다 자기 값으로 정한다.")
    return L


def report_r10(rounds: dict, fv: dict | None, fx: dict | None, now: str) -> list[str]:
    """R10 정의 보고서. 판정을 맨 앞에 두고, 회차마다 선택값의 판정 칸·먹이 부족 칸 표를 낸다.

    후보가 여럿인 회차는 후보 요약 표 한 줄씩만 내고, 칸별 표는 선택값만 낸다(칸별 값은 report.json 에 모두 있다).
    마지막이 아닌 보정 회차는 선택값 요약 한 줄만, 보조 지표 표는 마지막 보정 회차의 선택값에만, 참고 세계 대비는
    생존 경제 표만 낸다(회차를 모두 돌려도 150줄 안팎).
    """
    L = ["# Gate F 보고서 (R10 재판정): v2.0b 먹이 2층 (환경 층)", "",
         f"> 자동 생성: `python gate_f.py report --out {rel(OUT)}` ({now}). 회차 기록: `{rel(ROUNDS)}/*.json`. "
         "사전 등록 `PREREG.md`. 계획서 0-6, 4.9.1, 6.2 F4, 10절 R10. F4 정의 r10(10-02 승인 정의).", ""]

    def counts(P: dict, n: int) -> str:
        return ", ".join(f"({k}) {P[k]}/{n}" for k in "abcd") + f", 모두 {P['all']}/{n}"

    # --- 판정 ---
    L.append("## 판정")
    if fv:
        s = fv["summary"]
        sc = ", ".join(f"{POLICY_LABEL[p]}·{sd}" for p, sd in s["scarce"]) or "없음"
        L += [f"- 종합: **{'통과' if fv['passed'] else '실패'}** — 마지막 회차 {ROUND_LABEL[fv['round']]}의 선택값 "
              f"`{fv['label']}`.",
              f"- 기준별 통과(판정 칸 {s['n']}칸 = 먹이 부족 세계를 뺀 정책·시드): {counts(s['n_pass'], s['n'])}. "
              f"(c) 진폭 평균 {f3(s['amp_mean'])}(최소 {f3(s['amp_min'])}), 600스텝 뒤 평균 {f3(s['persist_mean'])}.",
              f"- 참고 {s['n_total']}칸 전체(먹이 부족 세계 포함): {counts(s['n_pass_total'], s['n_total'])}. "
              f"판정에서 뺀 칸: {sc}."]
    if fx:
        s = fx["summary"]
        who = ", ".join(POLICY_LABEL[p] for p in fx["judge_policies"])
        L.append(f"- 고정 정책 확인 `{fx['label']}`: **{'통과' if fx['passed'] else '실패'}** — {who}의 판정 칸에서 "
                 f"(d) 아사 비중 ≤ 0.4 {fx['n_d']}/{fx['n']} (최대 {f3(fx['starve_share_max'])}). 보고만(모든 정책의 "
                 f"판정 칸 {s['n']}): (a) {s['n_pass']['a']}, (b) {s['n_pass']['b']}, (c) {s['n_pass']['c']}, "
                 f"(d) {s['n_pass']['d']}."
                 + (" F 가 실패해 이 결과는 보고만 한다." if fv and not fv["passed"] else ""))
    if fv:
        L.append(f"- 다음(R10 사전 결정, 사람 결정을 기다리지 않는다): {next_step_r10(fv, fx)}")
    L.append("")

    L += history_table(rounds, "선택값 (a)(b)(d) 판정 칸 모두 지킴")
    if NOTES.exists():
        L += ["## 해석", "", NOTES.read_text(encoding="utf-8").strip(), ""]

    # --- 조건 ---
    any_meta = next(iter(rounds.values()))["meta"]
    pm: dict = {}
    for d in rounds.values():
        for pn, m in d["meta"]["policies"].items():
            pm.setdefault(pn, m)
    L += ["## 조건", "",
          f"- 보정 시드 {', '.join(map(str, any_meta['seeds']))} × {any_meta['steps']}스텝, 창 t = "
          f"{any_meta['warmup']}~{any_meta['steps']}. 평가 시드 10000~10019·학습 시드 [0, 1000) 와 겹치지 않는다.",
          "- 회차별 설정: " + "; ".join(f"{ROUND_LABEL[n]} `{rounds[n]['meta']['config']}`" for n in ROUND_NAMES
                                    if n in rounds)
          + ". food_v 회차는 `recovery_half_lives` 를 후보 h 하나로 덮는다(4.7 판정 실행 고정). 지역 = 맵 좌우 절반.",
          "- 먹이 부족 세계(판정 칸에서 빼고 따로 보고, 학습 무작위화는 그대로):", ""]
    L += scarce_table(rounds) + ["", "- 정책:"]
    L += [policy_line(pn, pm[pn]) for pn in POLICY_ORDER if pn in pm]
    L += commands_list(rounds)
    L += ["", "## 측정 정의", ""] + DEFINITIONS_R10 + [""]

    # --- 회차별 결과 (참고 회차는 아래 비교 표로만) ---
    L += ["## 회차별 결과", ""]
    last = fv["round"] if fv else None
    for name in [n for n in ROUND_NAMES if n in rounds and n not in REF_ROUNDS]:
        d = rounds[name]
        sel, cands = d.get("selected"), d["candidates"]
        L += [f"### {ROUND_LABEL[name]}", ""]
        if name in gate_rounds(rounds) and name != last:          # 앞 보정 회차: 선택값 한 줄(메모는 보정 이력)
            if sel is not None:
                s = cands[sel]["summary"]
                L.append(f"- 선택값 `{cands[sel]['label']}` — {'통과' if s['passed'] else '실패'}. 판정 칸: "
                         f"{counts(s['n_pass'], s['n'])}. (c) 진폭 평균 {f3(s['amp_mean'])}, 600스텝 뒤 평균 "
                         f"{f3(s['persist_mean'])}. 칸별 값은 `{rel(ROUNDS)}/{name}.json`.")
            L.append("")
            continue
        L += [f"- 메모: {d['meta'].get('note') or '—'} (명령은 '조건')", ""]
        if len(cands) > 1:
            L += ["| 후보 | (a)(b)(d) 판정 칸 모두 | (a) | (b) | (c) | (d) | 진폭 평균 | 600스텝 뒤 평균 | 판정 |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for i, c in enumerate(cands):
                s = c["summary"]
                n = s["n"]
                L.append(f"| {c['label']}{' (선택)' if i == sel else ''} | {ok(s['abd_all'])} | "
                         + " | ".join(f"{s['n_pass'][k]}/{n}" for k in "abcd")
                         + f" | {f3(s['amp_mean'])} | {f3(s['persist_mean'])} | {'통과' if s['passed'] else '실패'} |")
            L.append("")
        if sel is None:
            continue
        c = cands[sel]
        s = c["summary"]
        if name == "fixed":
            head = f"고정 정책 확인 {'통과' if fx and fx['passed'] else '실패'}"
        else:
            head = "통과" if s["passed"] else "실패"
        err = s.get("persist_pred_err_max")
        err_s = "—" if err is None or not math.isfinite(err) else f"{err:.1e}"
        L += [f"#### {c['label']}{' (선택)' if len(cands) > 1 else ''} — {head}", "",
              f"- 판정 칸: {counts(s['n_pass'], s['n'])}. (c) 진폭 평균 {f3(s['amp_mean'])}, 최소 {f3(s['amp_min'])}. "
              f"600스텝 뒤와 예측 2^(−600/h)·진폭(끝)의 최대 차 {err_s}. 설정 digest {c['config_digest']}", ""]
        scarce = [r for r in c["rows"] if r.get("food_scarce", False)]
        L += md_rows(judged_rows(c["rows"], F4_R10), r10=True) + [""]
        if scarce:
            L += ["먹이 부족 세계 (판정 제외, 따로 보고):", ""] + md_rows(scarce, r10=True) + [""]
        if name == last:
            L += ["보조 지표 (해석용, 모든 칸):", ""] + md_aux(c["rows"], r10=True) + [""]

    # --- 참고 세계 대비 ---
    if "ref" in rounds and fv:
        cand = rounds[fv["round"]]["candidates"][fv["selected"]]
        L += ["## v2.0 대비 생존 경제 (참고)", ""]
        L += md_compare(rounds["ref"], cand, "v2.0(food_v 끔)", f"v2.0b `{cand['label']}`", with_f=False,
                        per_cell=False) + [""]
    if "ref21" in rounds and fx:
        cand = rounds["fixed"]["candidates"][fx["selected"]]
        L += ["## v2.1 대비 생존 경제 (고정 정책, 참고)", ""]
        L += md_compare(rounds["ref21"], cand, "v2.1(food_v 끔)", f"v2.1 + food_v `{cand['label']}`",
                        with_f=False, per_cell=False) + [""]
    return L


def cmd_report(args=None) -> int:
    rounds = load_rounds()
    if not rounds:
        raise SystemExit(f"회차 기록이 없다: {ROUNDS}")
    f4 = dir_f4_def(rounds)
    fv = final_verdict(rounds)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta = dict(generated=now, command="python gate_f.py report", criteria=CRIT,
                window=[WARMUP, STEPS], every=EVERY, quiet=QUIET, top_frac=TOP_FRAC, ref_frac=REF_FRAC,
                cap_bins=CAP_BINS, design_half_life=DESIGN_HALF_LIFE, definitions=DEFINITIONS)
    extra = {}
    if f4 == F4_OLD:
        L = report_1002(rounds, fv, now)
    else:
        fx = fixed_verdict(rounds)
        L = report_r10(rounds, fv, fx, now)
        meta.update(command=f"python gate_f.py report --out {rel(OUT)}", definitions=DEFINITIONS_R10, f4_def=f4,
                    persist_tol=PERSIST_TOL)
        extra = dict(fixed=fx)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    def strip(d):
        return {**d, "candidates": [{**c, "rows": [{k: v for k, v in r.items() if k != "series"} for r in c["rows"]]}
                                    for c in d["candidates"]]}
    save_json(OUT / "report.json", dict(meta=meta, verdict=fv, **extra,
                                        rounds={k: strip(v) for k, v in rounds.items()}))
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
    s.add_argument("--round", required=True,
                   help="R0 (제안값) | R1 | R2 (보정 1·2회차) | ref (v2.0 참고) | fixed (고정 정책 확인) | ref21 (v2.1 참고)")
    s.add_argument("--reference", action="store_true",
                   help="food_v 끈 참고 세계를 돌린다(--round ref·ref21 과 함께. 기본 ref configs/v2.yaml, "
                        "ref21 configs/v2_1.yaml)")
    s.add_argument("--config", default=None,
                   help="기본 R0·R1·R2 configs/v2_0b.yaml, fixed configs/v2_1_0b.yaml, ref configs/v2.yaml, "
                        "ref21 configs/v2_1.yaml")
    s.add_argument("--f4-def", choices=F4_DEFS, default=F4_R10,
                   help="F4·(c) 정의와 판정 칸 규칙. r10(기본) = 10-02 승인 정의(섭식 강도 순위, 짝 휴식, 먹이 부족 세계 "
                        "제외), 1002 = 10-02 판정 때 정의. 회차 meta 에 남고 한 디렉터리에 섞지 않는다")
    s.add_argument("--alpha", type=float, nargs="+", default=None, help="훼손 계수 α 후보")
    s.add_argument("--floor", type=float, nargs="+", default=None, help="V 하한(cap0 비율) 후보")
    s.add_argument("--half-life", type=float, nargs="+", default=None,
                   help=f"회복 반감기 h 후보(스텝). 기본 {DESIGN_HALF_LIFE} 하나 (4.7 판정 실행 고정)")
    s.add_argument("--regen-base", type=float, nargs="+", default=None,
                   help="재생률 r 의 v1 키 food_regen_base 후보(overrides). 기본은 v1 값")
    s.add_argument("--policies", nargs="+", choices=POLICY_ORDER, default=None,
                   help="기본 fixed·ref21 은 v21 c2v21 (행동 5), 나머지 회차는 C2 learned utility (행동 4)")
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
