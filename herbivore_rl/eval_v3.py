"""v3 R1 판정 도구 — 행동 고르기 RL 정책을 손 규칙(FSM)·대조군과 비교한다 (명세 `Docs/RL_Policy/RL_V3_R1_SPEC.md` 5절,
사전 등록 `results/v3/r1/PREREG.md` 3·4절).

    # herbivore_rl/ 에서. 학습 모델 하나(모델 시드 하나)의 판정 — 사전 등록 조건(평가 시드 10000~10019 × 10000스텝)
    python eval_v3.py run --model ckpt/v3/v3_r1_g995_s0_20m.zip --name s0 --workers 14
    # FREEZE 판은 기본이 '가까운 위협 앞 얼기'(near, R0 에서 통과한 판)다. 원래 판으로 재려면(보고·비교용)
    python eval_v3.py run --model ... --name s0_orig --freeze-variant orig --out <다른 폴더>
    # 6시드 모아 보기(judge.md, R1 성공 = 6시드 중 4시드 이상 통과)
    python eval_v3.py summarize --names s0 s1 s2 s3 s4 s5
    # 출시 선별(보정 시드 20000~20019)·조기 중단 점검(20000~20002 × 3000스텝, 체크포인트)은 다른 폴더에 쓴다
    python eval_v3.py run --model ckpt/v3/v3_r1_g995_s0_20m_2m.zip --name s0_2m --seeds 20000 20001 20002 --steps 3000 \
        --policies rl fsm --out results/v3/r1/early
    # smoke: 시드 2개 · 300스텝 · tail 100. 사전 등록 폴더가 아닌 --out 이 꼭 필요하다
    python eval_v3.py run --model <zip> --name smoke --seeds 10000 10001 --steps 300 --tail 100 --out <임시 폴더>

- 세계: 판정 설정 `configs/v3_r1_on.yaml`(train.repertoire 블록의 허용 행동이 목록이다 — R0 결과로 graze·flee·hide·freeze,
  SLEEP 은 빠졌다). 정책은 모두 argmax·결정적이다.
- 정책 (명세 5절):
  · rl: 학습 정책(`{"kind": "rep_learned"}`, 마스크 로짓 argmax)
  · fsm: 거주 규칙 R_base(θ 4, a 0.9)에 목록 행동의 니치 규칙(`repertoire_rules.NICHES`)을 얹는다. 우선순위 HIDE > FREEZE >
    SLEEP > R_base (규칙 래퍼를 SLEEP → FREEZE → HIDE 순서로 씌워 뒤 규칙이 앞 규칙을 덮는다. 목록에 없는 행동의 규칙은 빠진다 —
    지금 목록이면 HIDE > FREEZE > R_base). FREEZE 는 --freeze-variant near(기본, R0 에서 통과한 판)면 '가까운 위협 앞' 판(R0 의
    cross 조건: 바탕 규칙이 FLEE 를 고르고 위협이 6 안이거나 접근 ≥ 0.9 면 얼기), orig 면 원래 니치 조건이다
  · c_<행동>: 늘 그 행동을 요청한다. 가능하지 않으면(`rep_policy.feasible_mask`) GRAZE
  · c1p (C1′): 결정 때 RL 의 판정 세계 결정 선택 빈도(모든 평가 시드를 합친 값)를 마스크(허용 ∧ 가능 ∧ 결정)로 다시 맞춰 해시로
    뽑는다. u = U(H(606, 평가 시드, 0, 개체 키, tick)) (`env_v2.rollout` 의 hold_hash·hold_uniform, 개체 키는 리스폰마다 세대가
    오른다). RL 을 먼저 돌린 뒤 돌린다
  · c4_app: RL 에 관측 pred_approach = 0.5 를 넣는다. c4_phase: 위상 관측 visibility·to_transition 을 중립 1·1 로 넣는다.
    망 입력만 바뀌고 마스크는 참 상태로 만든다(`obs_fix` 래퍼)
- 지표 (PREREG 3절):
  · G_γ (γ 0.9916661555611042, tail 600, `env_v2.rollout.g_gamma`), 피식률·아사율(개체-스텝당), 행동별 사용 비중(실행한 행동의
    개체-스텝 비율), 깜빡임(전환 중 3초 안 A-B-A, `World.repertoire_stats` 와 같은 정의 — 시드를 합친 수로 낸다), 결정 비율
  · U_X: 결정 시점(요청을 읽는 개체·스텝, `World.rep_peek`) 표본만으로 센 조건부 선택 확률의 차. 선택 = 그 스텝의 요청(기상 결정의
    SLEEP 요청은 arbitrate 처럼 wake_target). 보임 = 관측 pred_count > 0, 거리 = 관측 pred_dist × see_r(가장 가까운 보이는
    위협), 접근 = 관측 pred_approach, 은신처 = 관측 cover_dist × obs_cover_norm, 밤 d ≥ 0.8·낮 d ≤ 0.2(관측 visibility,
    `repertoire_rules.features_of_obs`). 평가 시드를 합친 수(분자·분모)로 낸다
      U_ESC  = P(FLEE ∪ HIDE ∪ FREEZE | 보임 & 접근 ≥ 0.75 & 거리 < 10) − P(같은 셋 | 위협 없음 = 안 보임)
      U_HIDE = P(HIDE | 보임 & 은신처 ≤ 5) − P(HIDE | 안 보임 & 낮)
      U_FREEZE near = P(FREEZE | 보임 & (거리 < 6 또는 접근 ≥ 0.9)) − P(FREEZE | 보임 & 거리 ≥ 8 & 접근 < 0.7), orig = 두 항을 바꾼 것
      U_SLEEP = P(SLEEP | 밤 & E ≥ 0.5) − P(SLEEP | 낮)
  · 위험 할당(보고만): FLEE 진입(결정 시점에 FLEE 를 고르고 지금 행동이 FLEE 가 아닌, 위협이 보이는 표본) 때 거리의 중앙값을 배부름
    (E > 0.7)·배고픔(E < 0.35)으로 나눈 차(배부름 − 배고픔)
  · C4 하락률 = (U − U_C4) / U
- 판정 (PREREG 4절, 모델 시드마다 모두 만족): (1) RL − FSM G_γ 짝 t ≥ −t_crit(평가 시드 20 이면 자유도 19, 2.093. t > t_crit 면 'FSM
  을 이김'), (2) 목록 행동의 U 문턱(U_ESC ≥ 0.5 늘, U_HIDE ≥ 0.3, U_FREEZE ≥ 0.3, U_SLEEP ≥ 0.5), (3) 목록의 모든 행동 사용 비중
  ≥ 2%·깜빡임 ≤ 10%, (4) SLEEP 이 목록에 있으면 위상 중립 고정에서 U_SLEEP 50% 이상 하락, FREEZE near 판이 목록에 있으면 접근 0.5
  고정에서 U_FREEZE 50% 이상 하락(그 밖의 C4 는 보고만), (5) 아사율 ≤ 1.5 × FSM 아사율(평가 시드 평균)
- 결과: `<out>/<name>.json`(요약·시드별 값), `<out>/<name>.md`(판정표 먼저). `summarize` 는 `<out>/judge.md`.
- 사전 등록 폴더(`results/v3/r1/judge`, --out 기본값)에는 PREREG 조건(시드 10000~10019, 10000스텝, 판정 설정, tail 600, 정책
  모두, FREEZE 판 near)만 쓴다 — 다른 조건이면 시작 전에 멈춘다.

v3 R2 판정 (`--u-def r2`, 명세 `Docs/RL_Policy/RL_V3_R2_SPEC.md` 10절 7단계, 사전 등록 `results/v3/r2/judge/PREREG.md`):

    # 판정 — 사전 등록 조건(새 평가 시드 10200~10219 × 10000스텝, configs/v3_r2_on.yaml). --u-def r2 면 --config·--seeds·--out 의
    # 기본값이 R2 판정 값이다. 문턱(U_MIN_BY['r2'])을 정하고 judge/PREREG.md 를 둔 뒤에만 이 폴더에 쓴다
    python eval_v3.py run --u-def r2 --model ckpt/v3/v3_r2_g995_s0_20m.zip --name s0 --workers 14
    # 모방 초기화 직후·손 규칙 기준값(보정 시드, 판정 시드가 아니다). ws_s0 은 기본 정책 모두, ws_s1~s5 는 rl fsm_r2 c1p
    python eval_v3.py run --u-def r2 --model ckpt/v3/ws_r2/v3_r2_ws_s0.zip --name ws_s0 --seeds 20000 ... 20007 --steps 3000 \
        --out results/v3/r2/ws_baseline

- 세계: `configs/v3_r2_on.yaml` = v3_r1_on + 동족 경보 M8(관측 19·마스크 판 3). 노려보기 M7(stare_down)은 R2 세계에서 뺐다(사람
  결정 10-13, 사전 등록 results/v3/r2/PREREG.md 변경 기록 10-13 (8) — '피식자가 노려본다고 포식자가 물러나는 것은 말이 안 된다').
  경보가 없는 설정은 r2 를 받지 않는다. 노려보기를 함께 켠 설정(앞선 두 장치 실행의 재현)은 받되, 노려보기 지표는 보고만 한다(아래).
- 정책: 기본 rl·fsm_r2·rbase·c_graze·c_flee·c_hide·c_freeze·c1p (명세 대조 FSM_R2·R_base·늘 먹기·C1′ 에 R1 처럼 늘 도망·숨기·얼기를
  더한다 — 마스크만으로 생기는 U 의 크기를 보이려고. 판정 사전 등록 results/v3/r2/judge/PREREG.md).
  · fsm_r2: FSM_R2(`repertoire_rules.fsm_r2_spec`, 언리얼 규칙 두뇌) = R1 FSM(near) + 켠 장치의 줄(alarm → look, 재현용으로
    stare_down 을 켠 설정이면 stare 도). R2 세계에서는 우선순위 HIDE > FREEZE 가까운 판 > look > R_base(θ 4, a 0.9). 성과(1)·굶음(4)의
    기준 손 규칙이 FSM_R2 다. FSM_R2·R_base 대조와 모방 초기화 교사의 (θ, a)는 (4, 0.9)로 고정한다(사람 결정 10-12 밤 — R1 과 같다)
  · rbase_wr2 (기록 재현용, 기본 정책에서 뺐다): 두 장치를 함께 켰던 합친 세계의 거주 탐색(results/v3/r2/wr2_both/search.json)이
    고른 R_base(θ 4, a 0.6). R2 세계는 그 세계가 아니므로 이 대조를 기본으로 재지 않는다(--policies 로 줄 수는 있다)
- U (결정 시점 표본, 평가 시드 합침): 판정에 쓰는 것은 R1b 의 셋(U_ESC·U_HIDE′·U_FREEZE′, `u_terms` r1b 와 같다)뿐이다
  (`active_u`). 보고만(`R2_REPORT_U`, 판정에 쓰지 않는다 — 사람 결정 10-12 밤: 경보는 세계에 두고 점수 기준에서는 뺀다):
      U_LOOK = P(FREEZE | look 니치) − P(FREEZE | look 교차)
      U_LOOK_OPEN = P(FREEZE | look 니치 & FREEZE 열림) − P(FREEZE | look 교차 & FREEZE 열림)
      (노려보기를 켠 재현 설정에서만) U_STARE = P(FREEZE | stare 니치) − P(FREEZE | stare 교차), U_STARE_BAND(유지 줄을 뺀 띠만의 니치)
  니치·교차는 `repertoire_rules.NICHES` 의 look·stare 를 `x_wrap` 스펙의 `XRule.mask`(niche·cross 모드)로 그대로 쓴다(`XTerms`,
  사전 등록 results/v3/r2/PREREG.md 3절). 'FREEZE 열림' = 그 결정 시점의 마스크(`rep_policy.action_mask`, 허용 ∧ 가능 ∧ 결정)에서
  FREEZE 칸이 참. look 니치는 경보 ≥ 0.4 라 마스크 판 3 에서 늘 열리지만 look 교차(경보 < 0.4, 안 보임)는 threat_recency ≥ 0.2 일
  때만 열려서, 글자 그대로의 U_LOOK 은 경보를 읽지 않고 '열리면 언제나 얼기'만 해도 크게 나온다. 열린 결정만 센 U_LOOK_OPEN 은 그
  몫이 0 이고, 늘 U_LOOK_OPEN ≤ U_LOOK 이다(닫힌 칸은 고를 수 없다).
  판정 문턱 U_MIN_BY['r2'] = U_ESC 0.18·U_HIDE′ 0.20·U_FREEZE′ 0.10 (판정 사전 등록 3절)
- 보고만 하는 R2 지표 (`R2Acc`, 정책마다):
  · 보이는 지표: 세계의 `alarm_stats`·`threats_stats` 열(재현 설정이면 `stare_stats` 도). 수(…_n, emit_*, cry_n)는 시드를 합쳐
    1000 개체-스텝당, 비율은 시드 평균(값이 있는 시드만). 경보 포화는 alarm_frac·alarm_gap_mean·false_alarm_frac 으로 본다.
    먹기가 아닌 시간 = 1 − 먹기 사용 비중
  · 같은 순간 불일치: 결정 시점·마스크 두 칸 이상인 개체-스텝마다 같은 관측으로 FSM_R2·R_base 의 요청을 묻고(상태 없는 손 규칙 —
    세계를 바꾸지 않는다) 이 정책의 선택과 다른 비율 (`results/v3/r1b/visual/divergence.py` 의 반사실 불일치와 같은 뜻)
  · 구별 지표(결정 시점 표본): 위협 종류별(가장 가까운 보이는 위협 = 근접 추격·원거리·잠행·플레이어) FREEZE·FLEE·HIDE 비율,
    홉별(쥔 경보 홉 없음·0·1·2, 위협이 안 보일 때. 홉은 세계 훅 alarm_hop 인데 리스폰 전 값이라, 관측 alarm_heard 가 0 이면 '없음'
    으로 고쳐 센다. 관측에 경보가 있는데 훅이 없음인 표본은 빼고 hop_miss 로 센다) 반응, 밤 경보 의존(안 보임 & alarm_heard ≥ 0.4
    에서 반응 비율의 밤·낮, 반응 중 '안 보임 & 경보 > 0' 몫의 밤·낮), 에너지별 위험 감수(보임 & 거리 < 10 에서 먹기 비율의
    배부름·배고픔, 그리고 R1 의 FLEE 진입 거리 중앙값). 은신처 안 '웅크림 대 노려보기'(보임 & stare 띠에서 HIDE·FREEZE·FLEE)는
    노려보기를 켠 재현 설정에서만 낸다
- 사전 등록 폴더 `results/v3/r2/judge`(--u-def r2 의 --out 기본값)에는 PREREG 조건(시드 10200~10219, 10000스텝,
  configs/v3_r2_on.yaml, tail 600, 정책 모두, FREEZE 판 near, u-def r2, 문턱 확정, judge/PREREG.md 있음 — 제목에 '초안'이 없다)만
  쓴다.
- `summarize --u-def r2` 는 --out 기본값이 R2 판정 폴더다(기본 r1 은 R1 폴더). 결과 JSON 의 지표 정의가 --u-def 와 다르면 멈추고,
  닫힌 폴더(done.flag 가 있는 폴더)의 judge.md 는 내용이 바뀌면 덮지 않는다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from env_v2.repertoire import BEHAVIOR_NAMES, FLEE, FREEZE, GRAZE, HIDE, N_BEHAVIORS, SLEEP  # noqa: E402

CONFIG = "configs/v3_r1_on.yaml"
EVAL_SEEDS = list(range(10000, 10020))
STEPS = 10000
GAMMA = 0.9916661555611042
TAIL = 600
THETA, APPROACH = 4.0, 0.9                  # 거주 규칙 R_base(θ, a) (명세 5절)
# v3 R2: 판정 대조 FSM_R2·R_base 와 모방 초기화 교사는 위 (4, 0.9) 그대로다(사람 결정 10-12 밤, 판정 사전 등록
# results/v3/r2/judge/PREREG.md — FSM_R2 = R1 FSM + look 줄인 언리얼 규칙 두뇌 계약). 두 장치를 함께 켰던 합친 세계의 거주 탐색
# (results/v3/r2/wr2_both/search.json, W7 과 같다)은 a 0.6 을 골랐다 — 그 R_base 는 기록 재현용 대조 rbase_wr2 로 남긴다(기본 정책
# 아님, 노려보기를 뺀 R2 세계는 그 세계가 아니다)
THETA_WR2, APPROACH_WR2 = 4.0, 0.6
FREEZE_VARIANTS = ("near", "orig")
# PREREG 3절 지표 조건(지표 정의이고 세계 계수가 아니다). 거리·은신처 단위는 세계 길이
U_COND = dict(esc_approach=0.75, esc_dist=10.0, hide_cover=5.0, fz_near=6.0, fz_fast=0.9, fz_far=8.0, fz_slow=0.7,
              sleep_energy=0.5)
U_NAMES = ("esc", "hide", "freeze", "sleep")
U_TARGET = {"esc": (FLEE, HIDE, FREEZE), "hide": (HIDE,), "freeze": (FREEZE,), "sleep": (SLEEP,)}
# PREREG 4절 문턱 — 10-07 개정(PREREG 변경 기록 '판정 문턱을 손 규칙 값에 맞춤', 본 학습 1M 기록을 보기 전): 처음 값(U_ESC 0.5,
# U_HIDE 0.3, U_FREEZE 0.3, 사용 2%, 깜빡임 10%)은 가장 좋은 손 규칙도 넘지 못했다(보정 시드 20000~20007 × 3000: R_base U_ESC
# 0.364·깜빡임 0.647, FSM U_FREEZE 0.203·깜빡임 0.537, FSM 얼기 사용 2.0%). U 문턱 = 그 니치를 정한 손 규칙 값의 절반(ESC 는
# R_base, HIDE·FREEZE 는 FSM), 깜빡임 = 손 규칙의 큰 값보다 크지 않게, 사용 = 0.5%. 입력 의존(C4)은 보고만
U_MIN = {"esc": 0.18, "hide": 0.5, "freeze": 0.10, "sleep": 0.5}
# 지표 정의 묶음. r1 = R1 사전 등록(위), r1b = R1b 새 시드 확인 시험(results/v3/r1b/PREREG.md 2·3절): U_HIDE′ 제자리 웅크림
# (은신처 안 & 거리 < 6 대 은신처 안 & 거리 ≥ 8 & 접근 < 0.7), U_FREEZE′ 빠른 위협 앞 얼기(접근 ≥ 0.9 & 은신처 > 5 대 접근 < 0.7 &
# 거리 ≥ 8). U_ESC·U_SLEEP 은 같다
U_DEFS = ("r1", "r1b", "r2")
# r2 = R2 판정(모듈 docstring 'v3 R2 판정'): 판정 U 는 r1b 와 같은 셋(esc·hide·freeze)이다. look·look_open(경보 반응 — 사람 결정
# 10-12 밤: 경보는 세계에 두고 점수 기준에서는 뺀다)과, 노려보기(stare_down)를 켠 재현 설정에서만 세는 stare·stare_band(노려보기 —
# 사람 결정 10-13: R2 세계에서 뺀다)는 보고만 한다(R2_REPORT_U). 앞선 초안(10-12)은 stare·look_open 을 판정에 넣었다
R2_REPORT_U = ("look", "look_open", "stare", "stare_band")
R2_STARE_U = ("stare", "stare_band")          # 노려보기를 켠 설정에서만 세는 U
U_NAMES_R2 = U_NAMES + ("look", "look_open")
U_TARGET.update(stare=(FREEZE,), look=(FREEZE,), look_open=(FREEZE,), stare_band=(FREEZE,))
# r2 문턱(판정 사전 등록 results/v3/r2/judge/PREREG.md 3절, 학습 기록을 보기 전에 정한다 — 명세 10절 7단계, R1 선례):
# U_ESC 0.18(R2 세계 ws_baseline 10-13 의 R_base 0.357 의 절반 0.1785 를 둘째 자리 반올림 — R1 의 0.364 → 0.18 과 같은 규칙,
# 판정 사전 등록 8절 1), U_HIDE′ 0.20·U_FREEZE′ 0.10(R1b 문턱 그대로).
# SLEEP 은 목록에 없다(None = 미정 — 목록에 들어오면 판정 폴더 실행을 거부한다). 보고만 하는 U(R2_REPORT_U)는 문턱이 없다
U_MIN_BY = {"r1": U_MIN, "r1b": {"esc": 0.18, "hide": 0.2, "freeze": 0.10, "sleep": 0.5},
            "r2": {"esc": 0.18, "hide": 0.20, "freeze": 0.10, "sleep": None}}
R1B_COND = dict(hide_near=6.0, hide_far=8.0, hide_slow=0.7, fz_fast=0.9, fz_cover=5.0, fz_slow=0.7, fz_far=8.0)
USE_MIN, FLICKER_MAX, C4_DROP_MIN, STARVE_RATIO_MAX = 0.005, 0.65, 0.5, 1.5
FULL_E, HUNGRY_E = 0.7, 0.35                # 위험 할당 에너지 구간 (명세 5절)
C1P_TAG = 606                               # C1′ 해시 스트림 구분값(rollout._SALT 101~404·지연 505 와 겹치지 않는다)
PREREG_OUT = HERE / "results" / "v3" / "r1" / "judge"
PREREG_OUT_R1B = HERE / "results" / "v3" / "r1b" / "judge"     # R1b 확인 시험(summarize --u-def r1b 의 기본 폴더)
POLICY_ORDER = ("rl", "fsm", "fsm_r2", "rbase", "rbase_wr2", "c_graze", "c_flee", "c_hide", "c_freeze", "c_sleep", "c1p",
                "c4_app", "c4_phase")
# v3 R2 판정 (명세 RL_V3_R2_SPEC.md 10절 7단계): 새 평가 시드 10200~10219(지금까지 아무 시험에도 쓰지 않았다) × 10000스텝
CONFIG_R2 = "configs/v3_r2_on.yaml"
EVAL_SEEDS_R2 = list(range(10200, 10220))
PREREG_OUT_R2 = HERE / "results" / "v3" / "r2" / "judge"
# 명세 대조 FSM_R2·R_base·늘 먹기·C1′ + 보고만: 늘 도망·숨기·얼기(R1 기본 대조 — 마스크만으로 생기는 U 의 크기, 판정 사전 등록 3절).
# rbase_wr2(두 장치 합친 세계의 탐색값 R_base(4, 0.6))는 노려보기를 뺀 10-13 부터 기본에서 뺐다(THETA_WR2 주석)
R2_POLICIES = ("rl", "fsm_r2", "rbase", "c_graze", "c_flee", "c_hide", "c_freeze", "c1p")
REF_FSM = {"r1": "fsm", "r1b": "fsm", "r2": "fsm_r2"}          # 성과(1)·굶음(5)의 기준 손 규칙
R2_KINDS = ("chaser", "ranged", "stalker", "player")           # 위협 종류 번호(세계 threats 통계의 kind 와 같다)
R2_HOPS = (-1, 0, 1, 2)                                        # 쥔 경보의 홉(−1 = 없음)
R2_RISK_DIST = 10.0                                            # 에너지별 위험 감수: 보이는 위협이 이 거리 안
R2_ALARM = 0.4                                                 # 밤 경보 의존의 '강한 경보'(마스크 판 3·look 니치와 같은 값)
# 보이는 지표에서 1000 개체-스텝당으로 바꾸지 않는 수(세계당 하나 — 잠행형 포식자 수)
_NOT_PER_STEP = ("stalker_n",)


# --------------------------------------------------------------------- #
# 지표 조건 (train_v3.py 의 학습 기록도 쓴다)
# --------------------------------------------------------------------- #


def active_u(allowed, udef: str = "r1") -> tuple[str, ...]:
    """목록(허용 행동 이름)에서 판정에 쓰는 U. U_ESC 는 늘(FLEE 가 늘 있다), 나머지는 그 행동이 목록에 있을 때만. r1·r1b·r2 모두
    같은 규칙이다 — r2 의 U_LOOK·U_LOOK_OPEN·U_STARE·U_STARE_BAND 는 보고만이라 넣지 않는다(R2_REPORT_U, 사람 결정 10-12 밤·10-13)."""
    allowed = set(allowed)
    return tuple(u for u in U_NAMES if u == "esc" or u in allowed)


def u_names(udef: str = "r1", stare: bool = False) -> tuple[str, ...]:
    """지표 정의 묶음이 세는 U 이름(판정에 쓰지 않는 것 포함). r1·r1b 는 U_NAMES 그대로다. r2 는 look·look_open 을 더하고,
    `stare`(노려보기 stare_down 을 켠 재현 설정 — `XTerms` 가 stare 를 낼 때)면 stare·stare_band 도 더한다(보고만)."""
    if udef != "r2":
        return U_NAMES
    return U_NAMES_R2 + (R2_STARE_U if stare else ())


def u_terms(f: dict, variant: str = "near", udef: str = "r1") -> dict:
    """규칙 입력(`repertoire_rules.features_of_obs`) → {U 이름: (첫 항 조건, 둘째 항 조건)} (모듈 docstring '지표').
    `udef` = r1(R1 사전 등록) 또는 r1b(R1b 확인 시험의 U_HIDE′·U_FREEZE′, U_DEFS 주석). r2 는 여기서 r1b 와 같은 넷을 내고,
    보고만 하는 U_LOOK(재현 설정이면 U_STARE·U_STARE_BAND 도)의 조건은 관측으로 `XTerms` 가 낸다(손 규칙 XRule.mask 를 그대로
    쓰므로 관측이 필요하다). U_LOOK_OPEN 은 그 look 조건에 결정 시점 마스크의 FREEZE 칸을 곱한 것이다(`look_open_terms`)."""
    if variant not in FREEZE_VARIANTS:
        raise ValueError(f"freeze 판은 {FREEZE_VARIANTS} 중 하나다. 받은 값: {variant!r}")
    if udef not in U_DEFS:
        raise ValueError(f"지표 정의는 {U_DEFS} 중 하나다. 받은 값: {udef!r}")
    c = U_COND
    seen, dist, app = f["seen"], f["dist"], f["approach"]
    none = ~seen
    near = seen & ((dist < c["fz_near"]) | (app >= c["fz_fast"]))
    far = seen & (dist >= c["fz_far"]) & (app < c["fz_slow"])
    out = {"esc": (seen & (app >= c["esc_approach"]) & (dist < c["esc_dist"]), none),
           "hide": (seen & (f["cover_d"] <= c["hide_cover"]), none & f["day"]),
           "freeze": (near, far) if variant == "near" else (far, near),
           "sleep": (f["night"] & (f["energy"] >= c["sleep_energy"]), f["day"])}
    if udef in ("r1b", "r2"):
        b = R1B_COND
        inc = seen & f["in_cover"]
        out["hide"] = (inc & (dist < b["hide_near"]), inc & (dist >= b["hide_far"]) & (app < b["hide_slow"]))
        out["freeze"] = (seen & (app >= b["fz_fast"]) & (f["cover_d"] > b["fz_cover"]),
                         seen & (app < b["fz_slow"]) & (dist >= b["fz_far"]))
    return out


class XTerms:
    """U_LOOK·U_STARE·U_STARE_BAND 의 (니치, 교차) 조건 — 손 규칙 `repertoire_rules.XRule.mask` 의 niche·cross 모드 그대로다
    (스펙은 `repertoire_rules.x_wrap`, 값은 NICHES — 사전 등록 results/v3/r2/PREREG.md 3절). 모두 보고만 하는 U 의 조건이다.
    look 은 관측 alarm_heard 가 있는 세계(기능 alarm)에서만 낸다. stare·stare_band 는 노려보기(stare_down)를 켠 세계에서만 낸다
    (`stare` 인자, 기본 None = 설정을 본다 — 노려보기를 뺀 R2 세계(사람 결정 10-13)에는 없고, 두 장치를 함께 켰던 앞선 실행을 재현할
    때만 생긴다). stare 니치는 유지 줄(지금 FREEZE 면 0.45 ≤ 접근 < 0.67 도)을 포함하고, stare_band 는 같은 스펙에서 beh_freeze 칸만
    뺀 판(유지 줄 없음, 교차는 stare 와 같다)이다. 규칙 모두 바탕 요청을 보지 않으므로 base_req 는 쓰이지 않는다. 상태가 없고 세계를
    바꾸지 않는다."""

    def __init__(self, cfg, stare: bool | None = None):
        import repertoire_rules as rr

        geo = rr._geom(cfg)
        if stare is None:
            stare = has_r2_world(cfg)[0]
        self.rules = {}
        if stare:
            st = [rr.x_wrap(cfg, "stare", m, geo=geo) for m in ("niche", "cross")]
            self.rules["stare"] = tuple(rr.XRule(None, s) for s in st)
            self.rules["stare_band"] = tuple(rr.XRule(None, dict(s, cols=dict(geo["cols"]))) for s in st)
        if "alarm_heard" in geo["cols"]:
            self.rules["look"] = tuple(rr.XRule(None, rr.x_wrap(cfg, "look", m, geo=geo)) for m in ("niche", "cross"))

    def __call__(self, obs) -> dict:
        obs = np.asarray(obs)
        g = np.full(len(obs), GRAZE, dtype=np.int64)
        return {name: (a.mask(obs, g), b.mask(obs, g)) for name, (a, b) in self.rules.items()}


def look_open_terms(look: tuple, mask) -> tuple:
    """U_LOOK_OPEN 의 (니치, 교차) = look 의 (니치, 교차) & 그 표본 마스크의 FREEZE 칸(모듈 docstring 'v3 R2 판정'). `mask` 는
    결정 시점 표본의 (n, 5) bool 마스크(`rep_policy.action_mask` 의 그 행)다."""
    fz = np.asarray(mask, dtype=bool)[:, FREEZE]
    return look[0] & fz, look[1] & fz


def has_r2_world(cfg) -> tuple[bool, bool]:
    """(노려보기 M7 을 켰나, 경보 M8 을 켰나 — 관측 alarm_heard 가 있나). FSM_R2 의 줄과 r2 지표가 쓴다. R2 세계(v3_r2·v3_r2_on,
    사람 결정 10-13)는 (False, True)이고, (True, True)는 두 장치를 함께 켰던 앞선 실행의 재현 설정뿐이다."""
    from env_v2.world import obs_names

    feats = cfg.v2.get("features") or {}
    return bool((feats.get("stare_down") or {}).get("enabled")), "alarm_heard" in obs_names(cfg)


def fsm_r2_policy_spec(cfg, allowed) -> dict:
    """FSM_R2 (모듈 docstring 'v3 R2 판정'): `repertoire_rules.fsm_r2_spec` 에 켠 장치의 줄만(alarm → look, stare_down → stare)
    넣는다. R2 세계에는 노려보기가 없으므로 R_base(4, 0.9) + look + R0 HIDE + R0 가까운 위협 얼기(우선순위 HIDE > 가까운 얼기 >
    look > R_base)다. stare 줄은 노려보기를 켠 재현 설정에서만 들어간다(앞선 두 장치 실행과 같은 FSM_R2). θ 4·a 0.9 는 R1 FSM 과
    같다(THETA, APPROACH). 모방 초기화(warmstart_v3.py --teacher2 fsm_r2)도 이것을 쓴다."""
    import repertoire_rules as rr

    stare, look = has_r2_world(cfg)
    return rr.fsm_r2_spec(cfg, tuple(allowed), stare=stare, look=look, theta=THETA, approach=APPROACH)


def u_value(cnt) -> float | None:
    """[첫 항 표본 수, 첫 항 적중, 둘째 항 표본 수, 둘째 항 적중] → U (분모가 0 이면 None)."""
    na, ha, nb, hb = (float(x) for x in cnt)
    if na <= 0 or nb <= 0:
        return None
    return ha / na - hb / nb


# --------------------------------------------------------------------- #
# 정책
# --------------------------------------------------------------------- #


class ConstRequest:
    """C_k: 늘 행동 k 를 요청한다. 가능하지 않으면(관측 가능 조건) GRAZE."""

    def __init__(self, k: int, obs_names):
        self.k, self.obs_names = int(k), tuple(obs_names)

    def __call__(self, obs):
        from env_v2.rep_policy import feasible_mask

        ok = feasible_mask(obs, self.obs_names)[:, self.k]
        return np.where(ok, self.k, GRAZE).astype(np.float64)[:, None]


class C1Prime:
    """C1′ (빈도를 맞춘 무작위, 모듈 docstring). 결정 때 빈도 q 를 마스크로 다시 맞춰 해시 u 로 뽑는다. 결정이 아니면 마스크가 지금
    행동 한 칸이라 그 행동이 나온다(세계가 읽지 않는다)."""

    def __init__(self, freq, allowed_mask, seed: int, salt: int = 0):
        from env_v2.rollout import hold_hash

        self.q = np.asarray(freq, dtype=np.float64)
        self.params = {"allowed_mask": np.asarray(allowed_mask, dtype=bool)}
        self.seed, self.salt = int(seed), int(salt)
        self._h0 = hold_hash(C1P_TAG, self.seed, self.salt)
        self.gen = None
        self.tick = 0
        self.world = None

    def bind_world(self, world) -> None:
        self.world = world
        self.gen = np.zeros(world.N, dtype=np.uint64)

    def observe_done(self, done) -> None:
        self.gen[np.asarray(done, dtype=bool)] += np.uint64(1)

    def __call__(self, obs):
        from env_v2.rep_policy import action_mask, sample_masked
        from env_v2.rollout import hold_agent_keys, hold_chain, hold_uniform

        if self.world is None:
            raise ValueError("C1′ 정책은 bind_world(w) 뒤에 쓴다")
        m = action_mask(self.world, self.world.observe(), self.params)
        keys = hold_agent_keys(np.arange(len(m)), self.gen)
        u = hold_uniform(hold_chain(self._h0, keys, self.tick))
        self.tick += 1
        return sample_masked(np.broadcast_to(self.q, m.shape), m, u).astype(np.float64)[:, None]


def fsm_spec(cfg, allowed, variant: str) -> dict:
    """FSM 스펙: R_base(θ 4, a 0.9) + 목록 행동의 니치 규칙, 우선순위 HIDE > FREEZE > SLEEP > R_base (모듈 docstring)."""
    import repertoire_rules as rr

    geo = rr._geom(cfg)
    spec = rr.rule_spec(cfg, THETA, APPROACH)
    for x in ("sleep", "freeze", "hide"):           # 뒤에 씌운 규칙이 앞 규칙을 덮는다 → 우선순위는 이 순서의 반대
        if x in allowed:
            mode = "cross" if (x == "freeze" and variant == "near") else "niche"
            spec["wrap"].append(dict(factory="repertoire_rules:x_rule", x=x, mode=mode, slots=None, **rr.NICHES[x], **geo))
    return spec


def policy_spec(name: str, model: str, cfg, allowed, variant: str, freq=None) -> dict:
    """정책 이름 → 워커에 넘기는 스펙(dict, 피클 가능)."""
    from env_v2.world import obs_names

    names = list(obs_names(cfg))
    rl = {"kind": "rep_learned", "path": str(model)}
    if name == "rl":
        return {"build": rl}
    if name == "fsm":
        return {"build": fsm_spec(cfg, allowed, variant)}
    if name == "fsm_r2":
        return {"build": fsm_r2_policy_spec(cfg, allowed)}
    if name == "rbase":
        # 보고만(PREREG 변경 기록 10-07 '대응: 모방 초기화'): R_base(θ 4, a 0.9) = 먹다가 가까우면 도망. FSM 은 도망을 쓰지 않는다
        return {"build": fsm_spec(cfg, ("graze", "flee"), variant)}
    if name == "rbase_wr2":
        # v3 R2 기록 재현용(기본 정책 아님): 두 장치 합친 세계의 거주 탐색값 R_base(θ 4, a 0.6) (THETA_WR2 주석)
        import repertoire_rules as rr

        return {"build": rr.rule_spec(cfg, THETA_WR2, APPROACH_WR2)}
    if name.startswith("c_"):
        b = name[2:]
        if b not in allowed:
            raise ValueError(f"{name}: {b} 는 목록 {list(allowed)} 에 없다")
        return {"const": BEHAVIOR_NAMES.index(b)}
    if name == "c1p":
        if freq is None:
            raise ValueError("c1p 는 RL 의 결정 선택 빈도가 필요하다(RL 을 먼저 돌린다)")
        return {"c1p": [float(x) for x in freq]}
    if name == "c4_app":
        return {"build": {"policy": rl, "wrap": [{"kind": "obs_fix", "dims": [names.index("pred_approach")],
                                                  "values": [0.5]}]}}
    if name == "c4_phase":
        return {"build": {"policy": rl, "wrap": [{"kind": "obs_fix", "dims": [names.index("visibility"),
                                                                              names.index("to_transition")],
                                                  "values": [1.0, 1.0]}]}}
    raise ValueError(f"모르는 정책 {name!r}. 쓸 수 있는 이름: {POLICY_ORDER}")


def _make_policy(pspec: dict, cfg, rep, seed: int):
    from env_v2 import rollout as ro
    from env_v2.world import obs_names

    if "build" in pspec:
        return ro.build_policy(pspec["build"], seed)
    if "const" in pspec:
        return ConstRequest(pspec["const"], obs_names(cfg))
    if "c1p" in pspec:
        return C1Prime(pspec["c1p"], rep["allowed_mask"], seed)
    raise ValueError(f"모르는 정책 스펙: {pspec!r}")


# --------------------------------------------------------------------- #
# v3 R2 보고 지표 (모듈 docstring 'v3 R2 판정')
# --------------------------------------------------------------------- #


def nearest_threat_kind(w, idx) -> tuple[np.ndarray, np.ndarray]:
    """개체 `idx` 의 가장 가까운 보이는 위협의 (종류 번호 R2_KINDS — 없으면 −1, 거리 — 없으면 inf). 세계 관측(`World._geometry`)과
    같은 보임 조건(행동별 자기 탐지 반경·밤 반경·시야각·자는 포식자 제외)을 공개 상태 배열로 다시 계산한다. 세계를 바꾸지 않는다."""
    from env_v2.steering import EPS
    from env_v2.world import PT_STALKER

    cfg = w.cfg
    idx = np.asarray(idx, dtype=np.int64)
    n = len(idx)
    if w.M == 0 or n == 0:
        return np.full(n, -1, dtype=np.int64), np.full(n, np.inf)
    if w._vg is not None:
        raise ValueError("위협 종류 지표는 경계 시야(vigilance)가 없는 세계에서만 쓴다")
    P, Hd = w.pos[idx], w.head[idx]
    ex = w.pred_pos[:, 0][None, :] - P[:, 0:1]
    ey = w.pred_pos[:, 1][None, :] - P[:, 1:2]
    pd = np.sqrt(ex * ex + ey * ey)
    pinv = 1.0 / np.maximum(pd, EPS)
    see_p = (cfg.see_r if w._dn is None else w._see_pred) * w._rep_see[idx][:, None]
    pvis = (pd <= see_p) & ((ex * Hd[:, 0:1] + ey * Hd[:, 1:2]) * pinv >= cfg.fov_cos)
    if w._ps is not None:
        pvis &= ~w.pred_asleep[None, :]
    masked = np.where(pvis, pd, np.inf)
    j = masked.argmin(1)
    d = masked[np.arange(n), j]
    kind = np.where(w.pred_is_player, 3, np.where(w.pred_type == PT_STALKER, 2, np.where(w.pred_ranged, 1, 0)))
    return np.where(np.isfinite(d), kind[j], -1).astype(np.int64), d


class R2Acc:
    """한 롤아웃의 R2 보고 지표(결정 시점 표본, 모듈 docstring 'v3 R2 판정'). 같은 순간 불일치용 FSM_R2·R_base 는 상태 없는 손 규칙
    이라 묻기만 해도 세계·궤적이 바뀌지 않는다. 행렬의 열은 [표본 수, FREEZE, FLEE, HIDE] 순서다(따로 적은 것 빼고).
    은신처 안 '웅크림 대 노려보기'(`cover`)는 stare 조건(`XTerms` 의 stare_band)이 있을 때 — 노려보기를 켠 재현 설정 — 만 센다."""

    def __init__(self, cfg, rep, seed: int, variant: str, stare: bool = False):
        from env_v2 import rollout as ro

        self.rep = rep
        self.shadow = {"fsm_r2": ro.build_policy(fsm_r2_policy_spec(cfg, rep["allowed"]), seed),
                       "rbase": ro.build_policy(fsm_spec(cfg, ("graze", "flee"), variant), seed)}
        self.by_kind = np.zeros((len(R2_KINDS), 4), dtype=np.int64)       # 보임, 가장 가까운 위협의 종류별
        self.kind_miss = 0                                                 # 다시 계산한 보임·거리가 관측과 다른 표본(빠진다)
        self.by_hop = np.zeros((len(R2_HOPS), 4), dtype=np.int64)          # 안 보임, 쥔 경보 홉별
        # 훅 alarm_hop(리스폰 전)과 관측 alarm_heard 가 '경보를 쥐었나'에서 다른 결정 표본: [모두, 그중 관측에 경보가 있는데 훅이
        # 없음(by_hop 에서 빠진다)]. 나머지(훅은 있는데 관측이 0 — 이번 스텝에 리스폰한 슬롯)는 '없음'으로 고쳐 센다
        self.hop_miss = np.zeros(2, dtype=np.int64)
        # [밤, 낮] × [안 보임 & 경보 ≥ 0.4 표본, 그중 반응, 반응(FLEE·HIDE·FREEZE) 전체, 반응 중 안 보임 & 경보 > 0]
        self.night = np.zeros((2, 4), dtype=np.int64)
        self.cover = np.zeros((2, 4), dtype=np.int64)                      # [은신처 안, 밖] × 보임 & stare 띠
        self.has_cover = bool(stare)                                       # stare 조건이 있나(재현 설정만)
        self.energy = np.zeros((2, 2), dtype=np.int64)                     # [배부름, 배고픔] × [보임 & 거리 < 10 표본, GRAZE]
        self.disagree = np.zeros(3, dtype=np.int64)                        # [마스크 두 칸 이상 표본, ≠ FSM_R2, ≠ R_base]

    @staticmethod
    def _cnt(sel, chosen) -> np.ndarray:
        c = chosen[sel]
        return np.array([len(c), np.count_nonzero(c == FREEZE), np.count_nonzero(c == FLEE), np.count_nonzero(c == HIDE)])

    def add(self, w, obs, pk, dec, chosen, f, terms, m=None) -> None:
        """결정 시점 표본 하나 묶음을 더한다. `m` 은 그 표본의 마스크(`action_mask(...)[dec]`, 없으면 여기서 만든다)."""
        from env_v2.rep_policy import action_mask

        idx = np.flatnonzero(dec)
        od = obs[dec]
        seen, resp = f["seen"], np.isin(chosen, (FLEE, HIDE, FREEZE))
        kind, d = nearest_threat_kind(w, idx)
        ok = (kind >= 0) == seen
        ok &= ~seen | np.isclose(np.where(seen, d, 0.0), np.where(seen, f["dist"], 0.0), rtol=1e-5, atol=1e-4)
        self.kind_miss += int(np.count_nonzero(~ok))
        for k in range(len(R2_KINDS)):
            self.by_kind[k] += self._cnt(ok & seen & (kind == k), chosen)
        alarm = f["alarm"]
        hop_raw = np.asarray(w.alarm_hop)[idx]
        held = alarm > 0.0
        lost = held & (hop_raw < 0)                     # 관측에는 경보가 있는데 훅은 없음 → 뺀다
        self.hop_miss += (int(np.count_nonzero((hop_raw >= 0) != held)), int(np.count_nonzero(lost)))
        hop = np.where(held, hop_raw, -1)               # 리스폰한 슬롯(훅 ≥ 0, 관측 0)은 '없음'
        for i, h in enumerate(R2_HOPS):
            self.by_hop[i] += self._cnt(~seen & ~lost & (hop == h), chosen)
        for i, seg in enumerate((f["night"], f["day"])):
            strong = seg & ~seen & (alarm >= R2_ALARM)
            self.night[i] += (np.count_nonzero(strong), np.count_nonzero(strong & resp), np.count_nonzero(seg & resp),
                              np.count_nonzero(seg & resp & ~seen & (alarm > 0.0)))
        if self.has_cover:                              # 노려보기를 켠 재현 설정에서만(R2 세계에는 stare 조건이 없다)
            band = terms["stare_band"][0]
            for i, inc in enumerate((f["in_cover"], ~f["in_cover"])):
                c = chosen[seen & band & inc]
                self.cover[i] += (len(c), np.count_nonzero(c == HIDE), np.count_nonzero(c == FREEZE),
                                  np.count_nonzero(c == FLEE))
        near = seen & (f["dist"] < R2_RISK_DIST)
        for i, e in enumerate((f["energy"] > FULL_E, f["energy"] < HUNGRY_E)):
            self.energy[i] += (np.count_nonzero(near & e), np.count_nonzero(near & e & (chosen == GRAZE)))
        if m is None:
            m = action_mask(pk, obs, self.rep, obs_names=w.obs_names)[dec]
        multi = np.asarray(m, dtype=bool).sum(1) >= 2
        self.disagree[0] += int(multi.sum())
        for i, name in enumerate(("fsm_r2", "rbase"), start=1):
            other = np.asarray(self.shadow[name](od), dtype=np.float64)[:, 0].astype(np.int64)
            self.disagree[i] += int(np.count_nonzero(multi & (other != chosen)))

    def to_dict(self) -> dict:
        out = dict(by_kind=self.by_kind.tolist(), kind_miss=int(self.kind_miss), by_hop=self.by_hop.tolist(),
                   hop_miss=self.hop_miss.tolist(), night=self.night.tolist(), energy=self.energy.tolist(),
                   disagree=self.disagree.tolist())
        if self.has_cover:
            out["cover"] = self.cover.tolist()
        return out


def _clean(d: dict) -> dict:
    return {k: (None if isinstance(v, float) and not math.isfinite(v) else float(v)) for k, v in d.items()}


def visible_stats(w) -> dict:
    """세계 통계 열(모듈 docstring '보이는 지표'): stare(M7)·alarm(M8)·threats. 켜진 기능만. nan 은 None."""
    out = {}
    if w._sd is not None:
        out["stare"] = _clean(w.stare_stats())
    if w._al is not None:
        out["alarm"] = _clean(w.alarm_stats())
    if w._th is not None:
        out["threats"] = _clean(w.threats_stats())
    return out


# --------------------------------------------------------------------- #
# 롤아웃 하나 (워커)
# --------------------------------------------------------------------- #


def _job(args):
    """(정책 이름, 정책 스펙, 평가 시드) 하나. 결정 시점 표본으로 U 의 수를 센다. 인자는 피클 가능한 것만 받는다."""
    from env_v2 import rollout as ro
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import action_mask, rep_params
    from env_v2.world import World

    import repertoire_rules as rr

    name, pspec, seed, steps, config, gamma, tail, variant, udef = args
    cfg = load_v2_config(HERE / config)
    rep = rep_params(cfg)
    geo = rr._geom(cfg)
    pol = _make_policy(pspec, cfg, rep, seed)
    w = World(cfg, seeds=[seed])
    ro.forward_bind(pol, w)
    xt = XTerms(cfg) if udef == "r2" else None             # v3 R2: U_LOOK(재현 설정이면 U_STARE) 조건(손 규칙 마스크)
    stare = xt is not None and "stare" in xt.rules
    acc = R2Acc(cfg, rep, seed, variant, stare) if udef == "r2" else None
    N = w.N
    rew = np.empty((steps, N))
    done = np.empty((steps, N), dtype=bool)
    u_cnt = {u: np.zeros(4, dtype=np.int64) for u in u_names(udef, stare)}
    choice = np.zeros(N_BEHAVIORS, dtype=np.int64)
    n_dec = 0
    entries = {"full": [], "hungry": []}
    for t in range(steps):
        obs = w.observe()
        pk = w.rep_peek()
        a = np.asarray(pol(obs), dtype=np.float64)
        dec = pk["reads"]
        if dec.any():
            req = a[dec, 0].astype(np.int64)
            wake = pk["wake_decide"][dec]
            chosen = np.where(wake & (req == SLEEP), w._rs.wake_target[dec].astype(np.int64), req)
            f = rr.features_of_obs(obs[dec], geo)
            terms = u_terms(f, variant, udef)
            m_dec = None
            if xt is not None:
                terms.update(xt(obs[dec]))
                # 결정 시점 마스크(허용 ∧ 가능 ∧ 결정 — RL 이 쓰는 마스크와 같다). U_LOOK_OPEN·같은 순간 불일치가 쓴다
                m_dec = action_mask(pk, obs, rep, obs_names=w.obs_names)[dec]
                if "look" in terms:
                    terms["look_open"] = look_open_terms(terms["look"], m_dec)
            for u, (ca, cb) in terms.items():
                hit = np.isin(chosen, U_TARGET[u])
                u_cnt[u] += (np.count_nonzero(ca), np.count_nonzero(ca & hit), np.count_nonzero(cb),
                             np.count_nonzero(cb & hit))
            choice += np.bincount(chosen, minlength=N_BEHAVIORS)
            n_dec += int(dec.sum())
            ent = (chosen == FLEE) & (pk["behavior"][dec] != FLEE) & f["seen"]
            if ent.any():
                e, d = f["energy"][ent], f["dist"][ent]
                entries["full"] += d[e > FULL_E].tolist()
                entries["hungry"] += d[e < HUNGRY_E].tolist()
            if acc is not None:
                acc.add(w, obs, pk, dec, chosen, f, terms, m_dec)
        _, r, d_, _ = w.step(a)
        rew[t], done[t] = r, d_
        ro.forward_done(pol, d_)
    beh = w._rep_hist.sum((0, 1)).astype(np.int64)
    out = dict(name=name, seed=int(seed), g_gamma=ro.g_gamma(rew, done, gamma, tail),
               pred_rate=w._pred_deaths / (steps * N), starve_rate=w._starve_deaths / (steps * N),
               mean_return=float(w.stats()["mean_return"]), beh=beh.tolist(), switch=int(w._rep_switch),
               flicker=int(w._rep_flicker), decide=int(w._rep_decide), n=int(steps * N), n_dec=n_dec,
               u_cnt={u: v.tolist() for u, v in u_cnt.items()}, choice=choice.tolist(), entries=entries)
    if acc is not None:
        out.update(r2=acc.to_dict(), visible=visible_stats(w))
    return out


def _map(jobs, workers):
    if workers <= 1:
        return [_job(j) for j in jobs]
    from env.rollout import _init_worker             # 워커의 BLAS 스레드를 1 로(배열이 작아 스레딩은 손해다)

    with ProcessPoolExecutor(min(workers, len(jobs)), initializer=_init_worker) as ex:
        return list(ex.map(_job, jobs, chunksize=1))


# --------------------------------------------------------------------- #
# 모으기·판정
# --------------------------------------------------------------------- #


def pooled(rows: list[dict], allowed) -> dict:
    """한 정책의 시드별 행 → 시드를 합친 지표(사용 비중·깜빡임·결정 비율·U·위험 할당)와 시드 평균(G_γ·피식·아사)."""
    beh = np.sum([r["beh"] for r in rows], axis=0).astype(np.float64)
    sw, fl = sum(r["switch"] for r in rows), sum(r["flicker"] for r in rows)
    n, dec = sum(r["n"] for r in rows), sum(r["decide"] for r in rows)
    names = tuple(rows[0]["u_cnt"])                     # 지표 정의 묶음이 센 U (r1·r1b 는 U_NAMES)
    u_cnt = {u: np.sum([r["u_cnt"][u] for r in rows], axis=0) for u in names}
    choice = np.sum([r["choice"] for r in rows], axis=0).astype(np.float64)
    full = [x for r in rows for x in r["entries"]["full"]]
    hungry = [x for r in rows for x in r["entries"]["hungry"]]
    med = lambda xs: float(np.median(xs)) if xs else None          # noqa: E731
    mf, mh = med(full), med(hungry)
    out = dict(
        g_gamma=float(np.mean([r["g_gamma"] for r in rows])),
        pred_rate=float(np.mean([r["pred_rate"] for r in rows])),
        starve_rate=float(np.mean([r["starve_rate"] for r in rows])),
        mean_return=float(np.mean([r["mean_return"] for r in rows])),
        use={b: float(beh[k] / beh.sum()) if beh.sum() else None for k, b in enumerate(BEHAVIOR_NAMES)},
        flicker=fl / sw if sw else None, switch_n=int(sw), decide_frac=dec / n if n else None,
        choice_freq=(choice / choice.sum()).tolist() if choice.sum() else [0.0] * N_BEHAVIORS,
        u={u: u_value(u_cnt[u]) for u in names}, u_cnt={u: u_cnt[u].tolist() for u in names},
        risk=dict(median_full=mf, median_hungry=mh, n_full=len(full), n_hungry=len(hungry),
                  diff=None if mf is None or mh is None else mf - mh))
    if "r2" in rows[0]:
        out["r2"] = pooled_r2(rows)
        out["visible"] = pooled_visible(rows, n)
        out["visible"]["non_graze"] = None if out["use"]["graze"] is None else 1.0 - out["use"]["graze"]
    return out


def _rate(x, n):
    return float(x) / float(n) if n else None


def pooled_r2(rows: list[dict]) -> dict:
    """R2Acc 의 시드별 수 → 시드를 합친 비율 (모듈 docstring '구별 지표'·'같은 순간 불일치')."""
    s = {k: np.sum([r["r2"][k] for r in rows], axis=0) for k in ("by_kind", "by_hop", "night", "energy", "disagree")}
    has_cover = all("cover" in r["r2"] for r in rows)           # 노려보기를 켠 재현 설정에서만(R2Acc)
    if has_cover:
        s["cover"] = np.sum([r["r2"]["cover"] for r in rows], axis=0)

    def fr(row):        # [n, FREEZE, FLEE, HIDE] → 비율
        return dict(n=int(row[0]), freeze=_rate(row[1], row[0]), flee=_rate(row[2], row[0]), hide=_rate(row[3], row[0]),
                    respond=_rate(row[1] + row[2] + row[3], row[0]))
    nt, en, dg = s["night"], s["energy"], s["disagree"]
    night = {seg: dict(n_alarm=int(nt[i][0]), respond_alarm=_rate(nt[i][1], nt[i][0]), n_respond=int(nt[i][2]),
                       alarm_share=_rate(nt[i][3], nt[i][2])) for i, seg in enumerate(("night", "day"))}
    ra, rd = night["night"]["respond_alarm"], night["day"]["respond_alarm"]
    sa, sd = night["night"]["alarm_share"], night["day"]["alarm_share"]
    night.update(respond_alarm_diff=None if ra is None or rd is None else ra - rd,
                 alarm_share_diff=None if sa is None or sd is None else sa - sd)
    cv = s.get("cover")
    cover = None if cv is None else {seg: dict(n=int(cv[i][0]), hide=_rate(cv[i][1], cv[i][0]),
                                               freeze=_rate(cv[i][2], cv[i][0]), flee=_rate(cv[i][3], cv[i][0]))
                                     for i, seg in enumerate(("in_cover", "open"))}
    energy = {seg: dict(n=int(en[i][0]), graze=_rate(en[i][1], en[i][0])) for i, seg in enumerate(("full", "hungry"))}
    gf, gh = energy["full"]["graze"], energy["hungry"]["graze"]
    energy["graze_diff"] = None if gf is None or gh is None else gh - gf        # 양수면 배고플 때 더 버티고 먹는다
    hm = np.sum([r["r2"].get("hop_miss", [0, 0]) for r in rows], axis=0)
    out = dict(by_kind={k: fr(s["by_kind"][i]) for i, k in enumerate(R2_KINDS)},
               kind_miss=int(sum(r["r2"]["kind_miss"] for r in rows)),
               by_hop={str(h): fr(s["by_hop"][i]) for i, h in enumerate(R2_HOPS)},
               hop_miss=dict(n=int(hm[0]), dropped=int(hm[1])),
               night=night, energy=energy,
               disagree=dict(n=int(dg[0]), fsm_r2=_rate(dg[1], dg[0]), rbase=_rate(dg[2], dg[0])))
    if cover is not None:
        out["cover"] = cover
    return out


def pooled_visible(rows: list[dict], n_agent_steps: int) -> dict:
    """세계 통계 열의 시드 합침(모듈 docstring '보이는 지표'): 수(…_n·emit_*·cry_n)는 합과 1000 개체-스텝당(`<열>_per1000`),
    그 밖(비율·평균)은 값이 있는 시드의 평균."""
    out = {}
    for grp in ("stare", "alarm", "threats"):
        vals = [r["visible"][grp] for r in rows if grp in r.get("visible", {})]
        if not vals:
            continue
        agg = {}
        for k in vals[0]:
            xs = [v[k] for v in vals if v[k] is not None]
            count = (k.endswith("_n") or k.startswith("emit_")) and k not in _NOT_PER_STEP
            if count:
                agg[k] = float(np.sum(xs)) if xs else None
                agg[k + "_per1000"] = float(np.sum(xs)) / n_agent_steps * 1000.0 if xs and n_agent_steps else None
            else:
                agg[k] = float(np.mean(xs)) if xs else None
        out[grp] = agg
    return out


def paired_t(a, b) -> dict:
    """시드별 짝 차 a − b → 평균·t·임계(양측 5%, 자유도 n − 1). 표본이 2개 미만이거나 표준편차 0 이면 t None."""
    from scipy.stats import t as tdist

    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    d = d[np.isfinite(d)]
    n = len(d)
    crit = float(tdist.ppf(0.975, n - 1)) if n > 1 else None
    if n < 2:
        return dict(mean=float(d.mean()) if n else float("nan"), t=None, n=n, crit=crit)
    se = float(d.std(ddof=1)) / math.sqrt(n)
    return dict(mean=float(d.mean()), t=float(d.mean() / se) if se > 0 else None, n=n, crit=crit)


def drop(u, u_c4):
    """C4 하락률 (U − U_C4) / U. U ≤ 0 이거나 없으면 None."""
    if u is None or u_c4 is None or u <= 0:
        return None
    return (u - u_c4) / u


def gate(res: dict, allowed, variant: str, udef: str = "r1") -> dict:
    """PREREG 4절 판정 (모듈 docstring). 조건마다 값·문턱·통과, 그리고 pass(모두 통과).
    r2 는 기준 손 규칙이 FSM_R2 이고(성과·굶음), 판정 U 는 r1b 와 같은 셋이며(U_LOOK·U_LOOK_OPEN·재현 설정의 U_STARE 는 `u.report`
    에 보고만), 입력 의존(C4) 항목이 없다. 문턱이 미정(None)인 U 는 통과가 아니고 `pending` 이 참이다."""
    P = res["pooled"]
    rl, fsm = P["rl"], P[REF_FSM[udef]]
    if udef == "r2":
        return _gate_r2(res, allowed, rl, fsm)
    out = {}
    pt = res["perf"]
    if pt["t"] is not None:
        ok = pt["t"] >= -pt["crit"]
        beat = pt["t"] > pt["crit"]
    else:                                   # smoke(시드 1개·차이 없음): 평균 차의 부호로만 본다
        ok, beat = (pt["mean"] >= 0.0), False
    out["perf"] = dict(t=pt["t"], crit=pt["crit"], mean=pt["mean"], pass_=bool(ok), beats_fsm=bool(beat))
    us = {}
    for u in active_u(allowed):
        v = rl["u"][u]
        lo = U_MIN_BY[udef][u]
        us[u] = dict(value=v, min=lo, pass_=bool(v is not None and v >= lo))
    out["u"] = dict(items=us, pass_=all(x["pass_"] for x in us.values()))
    use = {b: dict(value=rl["use"][b], pass_=bool(rl["use"][b] is not None and rl["use"][b] >= USE_MIN))
           for b in allowed}
    fl = rl["flicker"]
    out["use"] = dict(items=use, flicker=fl, flicker_pass=bool(fl is None or fl <= FLICKER_MAX),
                      pass_=all(x["pass_"] for x in use.values()) and bool(fl is None or fl <= FLICKER_MAX))
    dep = {}
    if "sleep" in allowed:
        dv = res["c4_drop"].get("c4_phase", {}).get("sleep")
        dep["sleep_phase"] = dict(value=dv, min=C4_DROP_MIN, pass_=bool(dv is not None and dv >= C4_DROP_MIN))
    if "freeze" in allowed and variant == "near":
        dv = res["c4_drop"].get("c4_app", {}).get("freeze")
        dep["freeze_app"] = dict(value=dv, min=C4_DROP_MIN, pass_=bool(dv is not None and dv >= C4_DROP_MIN))
    # 보고만(10-07 개정): 입력 의존은 통과 조건에 넣지 않는다
    out["dep"] = dict(items=dep, pass_=all(x["pass_"] for x in dep.values()), report_only=True)
    lim = STARVE_RATIO_MAX * fsm["starve_rate"]
    out["starve"] = dict(rl=rl["starve_rate"], fsm=fsm["starve_rate"], limit=lim,
                         ratio=rl["starve_rate"] / fsm["starve_rate"] if fsm["starve_rate"] > 0 else None,
                         pass_=bool(rl["starve_rate"] <= lim))
    out["pass_"] = all(out[k]["pass_"] for k in ("perf", "u", "use", "starve"))
    return out


def _gate_r2(res: dict, allowed, rl: dict, fsm: dict) -> dict:
    """R2 판정(명세 10절 7단계, 판정 사전 등록 3절): 성과(RL − FSM_R2 G_γ 짝 t ≥ −t_crit), U(R1b 셋 U_ESC·U_HIDE′·U_FREEZE′, 문턱
    U_MIN_BY['r2']), 목록 행동 모두 사용 ≥ 0.5%·깜빡임 ≤ 0.65, 아사 ≤ 1.5 × FSM_R2. 입력 의존은 없다(dep 은 비어 있고 통과로 친다).
    경보 반응 U_LOOK·U_LOOK_OPEN(사람 결정 10-12 밤)과 재현 설정의 U_STARE·U_STARE_BAND(10-13)는 `u.report` 에 값만 적고 통과에
    넣지 않는다(R2_REPORT_U)."""
    out = {}
    pt = res["perf"]
    if pt["t"] is not None:
        ok, beat = pt["t"] >= -pt["crit"], pt["t"] > pt["crit"]
    else:
        ok, beat = (pt["mean"] >= 0.0), False
    out["perf"] = dict(t=pt["t"], crit=pt["crit"], mean=pt["mean"], pass_=bool(ok), beats_fsm=bool(beat), ref="fsm_r2")
    us = {}
    for u in active_u(allowed, "r2"):
        v, lo = rl["u"][u], U_MIN_BY["r2"][u]
        us[u] = dict(value=v, min=lo, pending=lo is None, pass_=bool(lo is not None and v is not None and v >= lo))
    pending = any(x["pending"] for x in us.values())
    report = {u: rl["u"][u] for u in R2_REPORT_U if u in rl["u"]}
    out["u"] = dict(items=us, pass_=all(x["pass_"] for x in us.values()), pending=pending, report=report)
    use = {b: dict(value=rl["use"][b], pass_=bool(rl["use"][b] is not None and rl["use"][b] >= USE_MIN))
           for b in allowed}
    fl = rl["flicker"]
    out["use"] = dict(items=use, flicker=fl, flicker_pass=bool(fl is None or fl <= FLICKER_MAX),
                      pass_=all(x["pass_"] for x in use.values()) and bool(fl is None or fl <= FLICKER_MAX))
    out["dep"] = dict(items={}, pass_=True, report_only=True)
    lim = STARVE_RATIO_MAX * fsm["starve_rate"]
    out["starve"] = dict(rl=rl["starve_rate"], fsm=fsm["starve_rate"], limit=lim,
                         ratio=rl["starve_rate"] / fsm["starve_rate"] if fsm["starve_rate"] > 0 else None,
                         pass_=bool(rl["starve_rate"] <= lim), ref="fsm_r2")
    out["pending"] = pending
    out["pass_"] = all(out[k]["pass_"] for k in ("perf", "u", "use", "starve"))
    return out


def config_digest(cfg) -> str:
    """diagnose_v2.config_digest 와 같은 식(설정 dict 의 sha1 앞 12자리)."""
    return hashlib.sha1(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]


def judge(model: str, name: str, seeds, steps: int, out: Path, config: str = CONFIG, variant: str = "near",
          workers: int = 1, policies=None, tail: int = TAIL, gamma: float = GAMMA, udef: str = "r1") -> dict:
    """모델 하나를 판정해 `<out>/<name>.json`·`<name>.md` 를 쓴다. 반환은 JSON 과 같은 dict."""
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import rep_params

    cfg = load_v2_config(HERE / config)
    rep = rep_params(cfg)
    if rep is None:
        raise ValueError(f"{config} 에 train.repertoire 블록(목록)이 없다")
    allowed = rep["allowed"]
    if variant not in FREEZE_VARIANTS:
        raise ValueError(f"--freeze-variant 는 {FREEZE_VARIANTS} 중 하나다")
    if udef not in U_DEFS:
        raise ValueError(f"--u-def 는 {U_DEFS} 중 하나다")
    if udef == "r2" and not has_r2_world(cfg)[1]:
        # R2 세계 = v3_r1_on + 경보(사람 결정 10-13 — 노려보기는 뺐다). 노려보기를 함께 켠 설정은 앞선 실행의 재현으로만 받는다
        raise ValueError(f"--u-def r2 는 경보(alarm)를 켠 R2 세계에서만 쓴다({CONFIG_R2}). "
                         f"{config}: {dict(zip(('stare_down', 'alarm'), has_r2_world(cfg)))}")
    if policies:
        names = list(policies)
    elif udef == "r2":
        names = list(R2_POLICIES)
    else:
        names = ["rl", "fsm", "rbase"] + [f"c_{b}" for b in allowed] + ["c1p", "c4_app", "c4_phase"]
    for must in ("rl", REF_FSM[udef]):
        if must not in names:
            raise ValueError(f"판정에는 정책 {must} 가 꼭 있어야 한다")
    seeds = [int(s) for s in seeds]
    t0 = time.time()
    phase1 = [p for p in names if p != "c1p"]
    jobs = [(p, policy_spec(p, model, cfg, allowed, variant), s, steps, config, gamma, tail, variant, udef)
            for p in phase1 for s in seeds]
    rows: dict[str, list[dict]] = {}
    for r in _map(jobs, workers):
        rows.setdefault(r["name"], []).append(r)
    pooled_ = {p: pooled(rows[p], allowed) for p in rows}
    if "c1p" in names:
        freq = pooled_["rl"]["choice_freq"]
        jobs = [("c1p", policy_spec("c1p", model, cfg, allowed, variant, freq), s, steps, config, gamma, tail, variant,
                 udef) for s in seeds]
        rows["c1p"] = _map(jobs, workers)
        pooled_["c1p"] = pooled(rows["c1p"], allowed)
    for p in rows:
        rows[p].sort(key=lambda r: r["seed"])
    g = lambda p: [r["g_gamma"] for r in rows[p]]          # noqa: E731
    res = dict(pooled=pooled_, perf=paired_t(g("rl"), g(REF_FSM[udef])))
    if udef == "r2":                                        # 보고만: RL − R_base (R1 판정의 R_base 보고와 같은 뜻)
        res["perf_rbase"] = paired_t(g("rl"), g("rbase")) if "rbase" in rows else None
        res["perf_rbase_wr2"] = paired_t(g("rl"), g("rbase_wr2")) if "rbase_wr2" in rows else None
    res["c4_drop"] = {c: {u: drop(pooled_["rl"]["u"][u], pooled_[c]["u"][u]) for u in U_NAMES}
                      for c in ("c4_app", "c4_phase") if c in pooled_}
    res["gate"] = gate(res, allowed, variant, udef)
    res["meta"] = dict(name=name, model=str(model), config=config, digest=config_digest(cfg), seeds=seeds,
                       steps=int(steps), gamma=gamma, tail=int(tail), freeze_variant=variant, u_def=udef, allowed=list(allowed),
                       policies=[p for p in POLICY_ORDER if p in rows], theta=THETA, approach=APPROACH,
                       elapsed_s=round(time.time() - t0, 1))
    if udef == "r2":
        stare_on, alarm_on = has_r2_world(cfg)
        res["meta"].update(u_min=dict(U_MIN_BY["r2"]), u_report=[u for u in R2_REPORT_U if u in pooled_["rl"]["u"]],
                           ref_fsm=REF_FSM[udef], theta_wr2=THETA_WR2, approach_wr2=APPROACH_WR2,
                           stare_down=stare_on, alarm=alarm_on, prereg=bool(out.resolve() == PREREG_OUT_R2.resolve()))
    res["per_seed"] = {p: [{k: v for k, v in r.items() if k not in ("entries",)} for r in rows[p]] for p in rows}
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / f"{name}.md").write_text(report_md(res), encoding="utf-8")
    return res


# --------------------------------------------------------------------- #
# 보고서
# --------------------------------------------------------------------- #


def _f(x, fmt=".3f"):
    return format(x, fmt) if isinstance(x, (int, float)) and x is not None and math.isfinite(x) else "—"


def _ok(b) -> str:
    return "통과" if b else "실패"


def report_md(res: dict) -> str:
    m, G, P = res["meta"], res["gate"], res["pooled"]
    if m.get("u_def") == "r2":
        return report_md_r2(res)
    small = len(m["seeds"]) < len(EVAL_SEEDS) or m["steps"] < STEPS
    L = [f"# v3 R1 판정 — {m['name']}" + (" (smoke·부분 실행, 판정 아님)" if small else ""), "",
         f"**결론: {'통과' if G['pass_'] else '실패'}** (PREREG 4절 다섯 조건 모두 만족해야 통과)", "",
         f"- 모델 `{m['model']}`, 판정 세계 `{m['config']}`(digest {m['digest']}), 목록 {', '.join(m['allowed'])}, "
         f"FREEZE 판 {m['freeze_variant']}, 지표 정의 {m.get('u_def', 'r1')}", f"- 평가 시드 {m['seeds'][0]}~{m['seeds'][-1]} ({len(m['seeds'])}개) × "
         f"{m['steps']}스텝, 정책은 모두 argmax·결정적, G_γ γ {m['gamma']} tail {m['tail']}", "",
         "## 판정 (PREREG 4절)", "", "| 조건 | 값 | 문턱 | 결과 |", "|---|---|---|---|"]
    p = G["perf"]
    beat = " — FSM 을 이김" if p["beats_fsm"] else ""
    L.append(f"| 1. 성과: RL − FSM G_γ 짝 t | 평균 차 {_f(p['mean'], '+.4f')}, t {_f(p['t'], '+.2f')} | t ≥ "
             f"−{_f(p['crit'], '.3f')} | {_ok(p['pass_'])}{beat} |")
    for u, v in G["u"]["items"].items():
        L.append(f"| 2. 맞는 때: U_{u.upper()} | {_f(v['value'])} | ≥ {v['min']} | {_ok(v['pass_'])} |")
    for b, v in G["use"]["items"].items():
        L.append(f"| 3. 쓰임: {b} 사용 비중 | {_f(v['value'], '.2%') if v['value'] is not None else '—'} | ≥ {USE_MIN:.1%} | "
                 f"{_ok(v['pass_'])} |")
    L.append(f"| 3. 쓰임: 깜빡임(3초 안 A-B-A) | {_f(G['use']['flicker'], '.2%') if G['use']['flicker'] is not None else '—'}"
             f" | ≤ {FLICKER_MAX:.0%} | {_ok(G['use']['flicker_pass'])} |")
    if G["dep"]["items"]:
        for k, v in G["dep"]["items"].items():
            label = "위상 중립 고정 → U_SLEEP 하락률" if k == "sleep_phase" else "접근 0.5 고정 → U_FREEZE 하락률"
            L.append(f"| 4. 입력 의존(보고만): {label} | {_f(v['value'])} | ≥ {v['min']} | {_ok(v['pass_'])} |")
    else:
        L.append("| 4. 입력 의존 | (해당 행동 없음) | — | 통과 |")
    s = G["starve"]
    L.append(f"| 5. 굶음: 아사율 RL / FSM | {_f(s['rl'], '.5f')} / {_f(s['fsm'], '.5f')} (비 {_f(s['ratio'], '.2f')}) | "
             f"≤ 1.5 × FSM | {_ok(s['pass_'])} |")
    L += ["", "## 정책별 지표", "",
          "사용 비중 = 실행한 행동의 개체-스텝 비율(G 먹기·F 도망·H 숨기·Z 얼기·S 잠). U 는 결정 시점 표본, 평가 시드를 합친 값.", "",
          "| 정책 | G_γ | 피식률 | 아사율 | 사용 G/F/H/Z/S | 깜빡임 | 결정 비율 | U_ESC | U_HIDE | U_FREEZE | U_SLEEP |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name in POLICY_ORDER:
        if name not in P:
            continue
        v = P[name]
        use = "/".join(_f(v["use"][b], ".3f") for b in BEHAVIOR_NAMES)
        L.append(f"| {name} | {_f(v['g_gamma'], '.4f')} | {_f(v['pred_rate'], '.5f')} | {_f(v['starve_rate'], '.5f')} | "
                 f"{use} | {_f(v['flicker'])} | {_f(v['decide_frac'])} | " + " | ".join(_f(v['u'][u]) for u in U_NAMES) + " |")
    if res["c4_drop"]:
        L += ["", "## C4 하락률 (U − U_C4) / U", "", "| 변형 | " + " | ".join(f"U_{u.upper()}" for u in U_NAMES) + " |",
              "|---|---|---|---|---|"]
        for c, d in res["c4_drop"].items():
            L.append(f"| {c} | " + " | ".join(_f(d[u]) for u in U_NAMES) + " |")
        L.append("")
        L.append("판정에 쓰는 것은 SLEEP(위상 중립)과 FREEZE near 판(접근 0.5)뿐이고 나머지는 보고만 한다.")
    r = P["rl"]["risk"]
    L += ["", "## 위험 할당 (보고만)", "",
          f"RL 의 FLEE 진입 때 가장 가까운 보이는 위협 거리 중앙값: 배부름(E > {FULL_E}) {_f(r['median_full'], '.2f')} "
          f"(n {r['n_full']}), 배고픔(E < {HUNGRY_E}) {_f(r['median_hungry'], '.2f')} (n {r['n_hungry']}), "
          f"차(배부름 − 배고픔) {_f(r['diff'], '+.2f')}. 양수면 배고플 때 위협을 더 가까이까지 참는다."]
    return "\n".join(L) + "\n"


# 보이는 지표 열(보고만). 경보(M8): 물결 크기·1초 안 고개 든 비율 두 판·홉 0 방출, 경보 포화(경보를 쥔 개체-스텝 비율·새 경보 사이
# 간격·헛경보 비율). 노려보기(M7) 열은 그 기능을 켠 재현 설정의 결과에만 있다(R2 세계에는 없다 — 사람 결정 10-13)
_VIS_COLS = (("alarm", "wave_size_mean", "물결 크기"), ("alarm", "heads_up_1s", "1초 고개 듦(r8)"),
             ("alarm", "heads_up_1s_r16", "1초 고개 듦(r16)"), ("alarm", "emit_h0_per1000", "홉0 방출/1000"),
             ("alarm", "alarm_frac", "경보 개체-스텝"), ("alarm", "alarm_gap_mean", "경보 간격"),
             ("alarm", "false_alarm_frac", "헛경보"))
# 경보 보이는 지표 둘째 표(보고만, 판정 사전 등록 5절): 홉 1·2 방출, 비명, 경보 방향이 맞은 비율(점 방식·away 복사 비교 방식 —
# 가장 가까운 깨어 있는 위협이 ±30° 안), E7 이 결정으로 이어진 비율 두 판(결정 시점이 온 비율·행동이 바뀐 비율, env_v2/world.py
# ALARM_STAT_COLUMNS 주석)
_VIS_COLS_ALARM2 = (("alarm", "emit_h1_per1000", "홉1 방출/1000"), ("alarm", "emit_h2_per1000", "홉2 방출/1000"),
                    ("alarm", "cry_n_per1000", "비명/1000"), ("alarm", "dir_ok_pt", "방향 맞음(점)"),
                    ("alarm", "dir_ok_copy", "방향 맞음(복사)"), ("alarm", "e7_decide_frac", "E7 결정"),
                    ("alarm", "e7_switch_frac", "E7 바뀜"))
_VIS_COLS_STARE = (("stare", "standoff_n_per1000", "대치/1000"), ("stare", "standoff_break_n_per1000", "깨진 대치/1000"),
                   ("stare", "balk_n_per1000", "물러남/1000"), ("stare", "spotted_n_per1000", "들킴/1000"),
                   ("stare", "spotted_charge_catch_frac", "들킨 돌진 포획률"))


def report_md_r2(res: dict) -> str:
    """R2 판정 보고(판정표 먼저, 그다음 정책별 지표·보이는 지표·구별 지표·같은 순간 불일치)."""
    m, G, P = res["meta"], res["gate"], res["pooled"]
    small = list(m["seeds"]) != EVAL_SEEDS_R2 or m["steps"] < STEPS
    pend = G.get("pending")
    head = "통과" if G["pass_"] else ("미정(문턱 미정 — 판정 사전 등록 전)" if pend else "실패")
    L = [f"# v3 R2 판정 — {m['name']}" + (" (보정 시드·부분 실행, 판정 아님)" if small else ""), "",
         f"**결론: {head}** (판정 사전 등록 results/v3/r2/judge/PREREG.md 의 조건 모두 — 기준 손 규칙 FSM_R2)", "",
         f"- 모델 `{m['model']}`, 판정 세계 `{m['config']}`(digest {m['digest']}), 목록 {', '.join(m['allowed'])}, 지표 정의 r2",
         f"- 평가 시드 {m['seeds'][0]}~{m['seeds'][-1]} ({len(m['seeds'])}개) × {m['steps']}스텝, 정책은 모두 argmax·결정적, "
         f"G_γ γ {m['gamma']} tail {m['tail']}", "",
         "## 판정", "", "| 조건 | 값 | 문턱 | 결과 |", "|---|---|---|---|"]
    p = G["perf"]
    beat = " — FSM_R2 를 이김" if p["beats_fsm"] else ""
    L.append(f"| 1. 성과: RL − FSM_R2 G_γ 짝 t | 평균 차 {_f(p['mean'], '+.4f')}, t {_f(p['t'], '+.2f')} | t ≥ "
             f"−{_f(p['crit'], '.3f')} | {_ok(p['pass_'])}{beat} |")
    for u, v in G["u"]["items"].items():
        lo = "미정" if v["pending"] else f"≥ {v['min']}"
        L.append(f"| 2. 맞는 때: U_{u.upper()} | {_f(v['value'])} | {lo} | {'미정' if v['pending'] else _ok(v['pass_'])} |")
    for b, v in G["use"]["items"].items():
        L.append(f"| 3. 쓰임: {b} 사용 비중 | {_f(v['value'], '.2%') if v['value'] is not None else '—'} | ≥ {USE_MIN:.1%} | "
                 f"{_ok(v['pass_'])} |")
    L.append(f"| 3. 쓰임: 깜빡임(3초 안 A-B-A) | {_f(G['use']['flicker'], '.2%') if G['use']['flicker'] is not None else '—'}"
             f" | ≤ {FLICKER_MAX:.0%} | {_ok(G['use']['flicker_pass'])} |")
    s = G["starve"]
    L.append(f"| 4. 굶음: 아사율 RL / FSM_R2 | {_f(s['rl'], '.5f')} / {_f(s['fsm'], '.5f')} (비 {_f(s['ratio'], '.2f')}) | "
             f"≤ 1.5 × FSM_R2 | {_ok(s['pass_'])} |")
    for u, v in G["u"].get("report", {}).items():          # 판정에 넣지 않는 U(R2_REPORT_U — 경보 반응, 재현 설정의 노려보기)
        L.append(f"| 보고만: U_{u.upper()} | {_f(v)} | — | 보고만 |")
    pr = res.get("perf_rbase")
    if pr:
        L += ["", f"보고만: RL − R_base G_γ 평균 차 {_f(pr['mean'], '+.4f')}, t {_f(pr['t'], '+.2f')}."]
    pw = res.get("perf_rbase_wr2")
    if pw:
        L += [f"보고만: RL − R_base(θ {m.get('theta_wr2', THETA_WR2):g}, a {m.get('approach_wr2', APPROACH_WR2):g} — 두 장치 합친 "
              f"세계의 거주 탐색값, 기록 재현용) G_γ 평균 차 {_f(pw['mean'], '+.4f')}, t {_f(pw['t'], '+.2f')}."]
    names = [n for n in POLICY_ORDER if n in P]
    us = tuple(u for u in U_NAMES_R2 + R2_STARE_U if any(u in P[n]["u"] for n in names))
    L += ["", "## 정책별 지표", "",
          "사용 비중 = 실행한 행동의 개체-스텝 비율(G 먹기·F 도망·H 숨기·Z 얼기·S 잠). U 는 결정 시점 표본, 평가 시드를 합친 값. "
          "U_HIDE·U_FREEZE 는 R1b 정의(U_HIDE′·U_FREEZE′). U_LOOK(글자 그대로)·U_LOOK_OPEN(FREEZE 가 열린 결정만)은 보고만이다"
          "(노려보기를 켠 재현 설정이면 U_STARE·U_STARE_BAND 도 보고만).", "",
          "| 정책 | G_γ | 피식률 | 아사율 | 사용 G/F/H/Z/S | 깜빡임 | 결정 비율 | " + " | ".join(f"U_{u.upper()}" for u in us) + " |",
          "|---|---|---|---|---|---|---|" + "---|" * len(us)]
    for name in names:
        v = P[name]
        use = "/".join(_f(v["use"][b], ".3f") for b in BEHAVIOR_NAMES)
        L.append(f"| {name} | {_f(v['g_gamma'], '.4f')} | {_f(v['pred_rate'], '.5f')} | {_f(v['starve_rate'], '.5f')} | "
                 f"{use} | {_f(v['flicker'])} | {_f(v['decide_frac'])} | " + " | ".join(_f(v['u'].get(u)) for u in us) + " |")
    L += ["", "U 표본 수(니치 / 교차, 결정 시점):", "",
          "| 정책 | " + " | ".join(f"U_{u.upper()}" for u in us) + " |", "|---|" + "---|" * len(us)]
    for name in names:
        c = P[name]["u_cnt"]
        L.append(f"| {name} | " + " | ".join(f"{c[u][0]} / {c[u][2]}" if u in c else "—" for u in us) + " |")
    L += ["", "look 교차(안 보임 & 0 < 경보 < 0.4)에서 FREEZE 가 열린 결정의 비율(이 비율이 1 보다 작은 만큼 글자 그대로의 U_LOOK 이 "
          "마스크만으로 커진다):", "", "| 정책 | look 니치 열림 | look 교차 열림 |", "|---|---|---|"]
    for name in names:
        c = P[name]["u_cnt"]
        if "look" in c and "look_open" in c:
            L.append(f"| {name} | {_f(_rate(c['look_open'][0], c['look'][0]))} | {_f(_rate(c['look_open'][2], c['look'][2]))} |")
    vcols = _VIS_COLS + (_VIS_COLS_STARE if any("stare" in P[n].get("visible", {}) for n in names) else ())
    L += ["", "## 보이는 지표 (보고만)", "",
          "수는 시드를 합쳐 1000 개체-스텝당, 비율은 시드 평균. 경보 포화 = 경보 개체-스텝·경보 간격(개체가 새 경보를 쥔 순간 사이 "
          "스텝)·헛경보(사냥 중이 아닌 위협으로 낸 홉 0 비율). 먹기가 아닌 시간 = 1 − 먹기 사용 비중.", "",
          "| 정책 | " + " | ".join(lbl for _, _, lbl in vcols) + " | 먹기가 아닌 시간 |",
          "|---|" + "---|" * (len(vcols) + 1)]
    for name in names:
        vis = P[name].get("visible", {})
        cells = [_f(vis.get(g, {}).get(k), ".3f") for g, k, _ in vcols]
        L.append(f"| {name} | " + " | ".join(cells) + f" | {_f(vis.get('non_graze'), '.3f')} |")
    L += ["", "경보 방출·방향·E7(수는 1000 개체-스텝당, 비율은 시드 평균. 방향 맞음 = 경보 방향을 받은 개체 중 가장 가까운 깨어 있는 "
          "위협이 ±30° 안인 비율 — 점 방식 / 보낸 개체의 away 복사. E7 결정 = E7 뒤 결정 지연 창 안에 결정 시점이 온 비율, E7 바뀜 = "
          "그 창 안에 행동이 바뀐 비율):", "",
          "| 정책 | " + " | ".join(lbl for _, _, lbl in _VIS_COLS_ALARM2) + " |", "|---|" + "---|" * len(_VIS_COLS_ALARM2)]
    for name in names:
        vis = P[name].get("visible", {})
        L.append(f"| {name} | " + " | ".join(_f(vis.get(g, {}).get(k), ".3f") for g, k, _ in _VIS_COLS_ALARM2) + " |")
    L += ["", "위협 유형별 포획률(개체-스텝당, 시드 평균):", "", "| 정책 | 근접 추격 | 원거리 | 잠행 | 플레이어 |", "|---|---|---|---|---|"]
    for name in names:
        th_ = P[name].get("visible", {}).get("threats", {})
        L.append(f"| {name} | " + " | ".join(_f(th_.get(f"catch_rate_{k}"), ".5f")
                                            for k in ("chaser", "ranged", "stalker", "player")) + " |")
    L += ["", "## 구별 지표 (보고만, 결정 시점 표본)", "",
          "위협 종류별(가장 가까운 보이는 위협) 선택 비율 — FREEZE / FLEE / HIDE (표본 수):", "",
          "| 정책 | " + " | ".join(R2_KINDS) + " |", "|---|" + "---|" * len(R2_KINDS)]
    for name in names:
        bk = P[name]["r2"]["by_kind"]
        L.append(f"| {name} | " + " | ".join(f"{_f(bk[k]['freeze'])} / {_f(bk[k]['flee'])} / {_f(bk[k]['hide'])} "
                                            f"({bk[k]['n']})" for k in R2_KINDS) + " |")
    L += ["", "홉별 반응(위협이 안 보일 때, 쥔 경보의 홉) — FREEZE / FLEE / HIDE (표본 수):", "",
          "| 정책 | 경보 없음 | 홉 0 | 홉 1 | 홉 2 |", "|---|---|---|---|---|"]
    for name in names:
        bh = P[name]["r2"]["by_hop"]
        L.append(f"| {name} | " + " | ".join(f"{_f(bh[str(h)]['freeze'])} / {_f(bh[str(h)]['flee'])} / "
                                            f"{_f(bh[str(h)]['hide'])} ({bh[str(h)]['n']})" for h in R2_HOPS) + " |")
    L += ["", f"밤 경보 의존 — 안 보임 & alarm_heard ≥ {R2_ALARM} 에서 반응(FLEE·HIDE·FREEZE) 비율, 반응 중 '안 보임 & 경보 > 0' 몫:",
          "", "| 정책 | 반응 밤 | 반응 낮 | 밤 − 낮 | 경보 몫 밤 | 경보 몫 낮 | 밤 − 낮 |", "|---|---|---|---|---|---|---|"]
    for name in names:
        nt = P[name]["r2"]["night"]
        L.append(f"| {name} | {_f(nt['night']['respond_alarm'])} ({nt['night']['n_alarm']}) | "
                 f"{_f(nt['day']['respond_alarm'])} ({nt['day']['n_alarm']}) | {_f(nt['respond_alarm_diff'], '+.3f')} | "
                 f"{_f(nt['night']['alarm_share'])} | {_f(nt['day']['alarm_share'])} | {_f(nt['alarm_share_diff'], '+.3f')} |")
    if all("cover" in P[n]["r2"] for n in names):           # 노려보기를 켠 재현 설정에서만
        L += ["", "은신처 안 '웅크림 대 노려보기' — 보임 & stare 띠(4 < 거리 ≤ 10 & 0.63 ≤ 접근 < 0.67)에서 HIDE / FREEZE / FLEE:",
              "", "| 정책 | 은신처 안 | 은신처 밖 |", "|---|---|---|"]
        for name in names:
            cv = P[name]["r2"]["cover"]
            L.append(f"| {name} | " + " | ".join(f"{_f(cv[k]['hide'])} / {_f(cv[k]['freeze'])} / {_f(cv[k]['flee'])} "
                                                f"({cv[k]['n']})" for k in ("in_cover", "open")) + " |")
    L += ["", f"에너지별 위험 감수 — 보임 & 거리 < {R2_RISK_DIST:g} 에서 먹기 비율(배부름 E > {FULL_E}, 배고픔 E < {HUNGRY_E}), "
          "FLEE 진입 거리 중앙값(R1 위험 할당):", "",
          "| 정책 | 먹기 배부름 | 먹기 배고픔 | 배고픔 − 배부름 | 진입 거리 배부름 | 배고픔 | 배부름 − 배고픔 |",
          "|---|---|---|---|---|---|---|"]
    for name in names:
        en, rk = P[name]["r2"]["energy"], P[name]["risk"]
        L.append(f"| {name} | {_f(en['full']['graze'])} ({en['full']['n']}) | {_f(en['hungry']['graze'])} ({en['hungry']['n']}) | "
                 f"{_f(en['graze_diff'], '+.3f')} | {_f(rk['median_full'], '.2f')} | {_f(rk['median_hungry'], '.2f')} | "
                 f"{_f(rk['diff'], '+.2f')} |")
    L += ["", "## 같은 순간 불일치 (보고만)", "",
          "결정 시점·마스크 두 칸 이상인 개체-스텝에서 같은 관측으로 물은 손 규칙의 요청과 이 정책의 선택이 다른 비율:", "",
          "| 정책 | 표본 | ≠ FSM_R2 | ≠ R_base |", "|---|---|---|---|"]
    for name in names:
        dg = P[name]["r2"]["disagree"]
        L.append(f"| {name} | {dg['n']} | {_f(dg['fsm_r2'])} | {_f(dg['rbase'])} |")
    miss = sum(P[n]["r2"]["kind_miss"] for n in names)
    L += ["", f"(위협 종류를 다시 계산한 보임·거리가 관측과 달라 뺀 표본: {miss})"]
    hm = [P[n]["r2"].get("hop_miss") for n in names]
    if all(h is not None for h in hm):
        L += [f"(홉 훅과 관측 경보가 다른 결정 표본: {sum(h['n'] for h in hm)} — 리스폰 슬롯은 '경보 없음'으로 고쳐 셌고, 관측에 경보가 "
              f"있는데 훅이 없어 뺀 표본 {sum(h['dropped'] for h in hm)})"]
    return "\n".join(L) + "\n"


def _write_judge_md(out: Path, text: str) -> None:
    """`<out>/judge.md` 를 쓴다. 닫힌 폴더(done.flag 가 있는 판정 폴더 — R1·R1b)의 judge.md 는 내용이 바뀌면 덮지 않고 멈춘다
    (다른 시험의 결과를 실수로 다시 모아 덮지 않게, 모듈 docstring)."""
    p = out / "judge.md"
    if (out / "done.flag").exists() and p.exists() and p.read_text(encoding="utf-8") != text:
        raise ValueError(f"{out} 는 닫힌 판정 폴더(done.flag)라 judge.md 를 바꾸지 않는다 — 다른 폴더면 --out(또는 --u-def)을 준다")
    p.write_text(text, encoding="utf-8")


def summarize(names, out: Path, udef: str | None = None) -> str:
    """`<out>/<name>.json` 여러 개 → `<out>/judge.md` (모델 시드별 통과표, R1 성공 = 6시드 중 4시드 이상, PREREG 5절).
    `udef` 를 주면 결과 JSON 의 지표 정의(meta.u_def, 없으면 r1)가 모두 그것이어야 한다(CLI 는 --u-def 를 준다)."""
    rows = []
    for n in names:
        res = json.loads((out / f"{n}.json").read_text(encoding="utf-8"))
        rows.append((n, res))
    if udef is not None:
        bad = [f"{n}({r['meta'].get('u_def', 'r1')})" for n, r in rows if r["meta"].get("u_def", "r1") != udef]
        if bad:
            raise ValueError(f"{out} 의 결과 {bad} 는 지표 정의가 --u-def {udef} 와 다르다 — 폴더(--out)나 --u-def 를 확인한다")
    n_pass = sum(r["gate"]["pass_"] for _, r in rows)
    if rows and all(r["meta"].get("u_def") == "r2" for _, r in rows):
        return _summarize_r2(rows, n_pass, out)
    L = ["# v3 R1 판정 모음", "",
         f"**통과 {n_pass} / {len(rows)}** — R1 성공 규칙은 6시드 중 4시드 이상 통과(PREREG 5절)"
         + (f": {'성공' if n_pass >= 4 else '실패'}" if len(rows) == 6 else " (6시드가 모두 모이면 판정)"), "",
         "| 모델 | 1 성과 (t) | 2 맞는 때 | 3 쓰임 | 4 입력 의존 | 5 굶음 | 통과 | FSM 을 이김 |", "|---|---|---|---|---|---|---|---|"]
    for n, r in rows:
        G = r["gate"]
        L.append(f"| {n} | {_ok(G['perf']['pass_'])} ({_f(G['perf']['t'], '+.2f')}) | {_ok(G['u']['pass_'])} | "
                 f"{_ok(G['use']['pass_'])} | {_ok(G['dep']['pass_'])} | {_ok(G['starve']['pass_'])} | "
                 f"**{_ok(G['pass_'])}** | {'예' if G['perf']['beats_fsm'] else '아니오'} |")
    L += ["", "출시 모델은 통과한 시드 가운데 보정 시드 20000~20019 의 G_γ 평균이 가장 높은 것을 고른다(평가 시드로는 고르지 않는다)."]
    text = "\n".join(L) + "\n"
    _write_judge_md(out, text)
    return text


def _summarize_r2(rows, n_pass: int, out: Path) -> str:
    """R2 판정 모음(성공 규칙은 판정 사전 등록 results/v3/r2/judge/PREREG.md 가 정한다 — 여기서는 통과 수만 센다)."""
    L = ["# v3 R2 판정 모음", "",
         f"**통과 {n_pass} / {len(rows)}** — 성공 규칙은 판정 사전 등록(results/v3/r2/judge/PREREG.md)을 따른다", "",
         "| 모델 | 1 성과 (t, FSM_R2) | 2 맞는 때 | 3 쓰임 | 4 굶음 | 통과 | FSM_R2 를 이김 |", "|---|---|---|---|---|---|---|"]
    for n, r in rows:
        G = r["gate"]
        u = "미정" if G.get("pending") else _ok(G["u"]["pass_"])
        L.append(f"| {n} | {_ok(G['perf']['pass_'])} ({_f(G['perf']['t'], '+.2f')}) | {u} | {_ok(G['use']['pass_'])} | "
                 f"{_ok(G['starve']['pass_'])} | **{_ok(G['pass_'])}** | {'예' if G['perf']['beats_fsm'] else '아니오'} |")
    text = "\n".join(L) + "\n"
    _write_judge_md(out, text)
    return text


def prereg_draft(path: Path) -> bool:
    """판정 사전 등록 파일의 제목 줄(첫 '# ' 줄)에 '초안'이 있으면 참(리드가 확정하기 전 — 판정 폴더 실행을 받지 않는다)."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return "초안" in line
    return True


def prereg_problems_r2(a, seeds) -> list[str]:
    """R2 판정 사전 등록 폴더(PREREG_OUT_R2)에 쓰는 실행의 조건 검사(모듈 docstring 'v3 R2 판정'). 비면 문제 없음."""
    bad = []
    if list(seeds) != EVAL_SEEDS_R2:
        bad.append("--seeds (R2 판정 10200~10219)")
    if a.steps != STEPS:
        bad.append(f"--steps (R2 판정 {STEPS})")
    if a.config != CONFIG_R2:
        bad.append(f"--config (R2 판정 {CONFIG_R2})")
    if a.tail != TAIL:
        bad.append(f"--tail (R2 판정 {TAIL})")
    if a.policies is not None:
        bad.append("--policies (R2 판정은 기본 정책 모두: " + " ".join(R2_POLICIES) + ")")
    if a.freeze_variant != "near":
        bad.append("--freeze-variant (near)")
    if getattr(a, "u_def", "r1") != "r2":
        bad.append("--u-def (R2 판정 폴더는 r2)")
    pend = [u for u, v in U_MIN_BY["r2"].items() if v is None and u in active_u(("graze", "flee", "hide", "freeze"), "r2")]
    if pend:
        bad.append(f"U 문턱 미정 {pend} (eval_v3.U_MIN_BY['r2'] — 판정 사전 등록에서 학습 기록을 보기 전에 정한다)")
    if not (PREREG_OUT_R2 / "PREREG.md").exists():
        bad.append(f"판정 사전 등록 {PREREG_OUT_R2 / 'PREREG.md'} 이 없다(명세 10절 7단계 — 학습 기록을 보기 전에 고정한다)")
    elif prereg_draft(PREREG_OUT_R2 / "PREREG.md"):
        bad.append(f"판정 사전 등록 {PREREG_OUT_R2 / 'PREREG.md'} 이 아직 초안이다(제목의 '초안' — 리드가 학습 기록을 보기 전에 "
                   "확정하고 지운다)")
    return bad


def prereg_problems(a, seeds) -> list[str]:
    """사전 등록 폴더에 쓰는 실행의 조건 검사. PREREG 조건과 다른 인자 목록(비면 문제 없음)."""
    bad = []
    if list(seeds) != EVAL_SEEDS:
        bad.append("--seeds (PREREG 10000~10019)")
    if a.steps != STEPS:
        bad.append(f"--steps (PREREG {STEPS})")
    if a.config != CONFIG:
        bad.append(f"--config (PREREG {CONFIG})")
    if a.tail != TAIL:
        bad.append(f"--tail (PREREG {TAIL})")
    if a.policies is not None:
        bad.append("--policies (PREREG 는 정책 모두)")
    if a.freeze_variant != "near":
        bad.append("--freeze-variant (R0 에서 통과한 판은 near)")
    if getattr(a, "u_def", "r1") != "r1":
        bad.append("--u-def (R1 사전 등록 폴더는 r1)")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="v3 R1 판정 (RL·FSM·대조군, PREREG 4절)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="모델 하나 판정")
    r.add_argument("--model", required=True)
    r.add_argument("--name", required=True, help="결과 파일 이름(보통 모델 시드, 예: s0)")
    r.add_argument("--config", default=None, help=f"기본 {CONFIG} (--u-def r2 면 {CONFIG_R2})")
    r.add_argument("--seeds", type=int, nargs="+", default=None,
                   help="기본 R1 평가 시드 10000~10019 (--u-def r2 면 R2 판정 시드 10200~10219)")
    r.add_argument("--steps", type=int, default=STEPS)
    r.add_argument("--tail", type=int, default=TAIL)
    r.add_argument("--freeze-variant", choices=FREEZE_VARIANTS, default="near",
                   help="FREEZE 가 목록에 있을 때 쓸 판(U_FREEZE 정의·FSM 얼기 규칙·입력 의존 조건). 기본 near")
    r.add_argument("--policies", nargs="+", default=None, choices=POLICY_ORDER)
    r.add_argument("--u-def", choices=U_DEFS, default="r1",
                   help="지표 정의 묶음: r1(R1 사전 등록, 기본), r1b(R1b 확인 시험, results/v3/r1b/PREREG.md), "
                        "r2(R2 판정, 명세 RL_V3_R2_SPEC.md 10절 7단계)")
    r.add_argument("--workers", type=int, default=14)
    r.add_argument("--out", default=None, help=f"기본 {PREREG_OUT} (--u-def r2 면 {PREREG_OUT_R2})")
    s = sub.add_parser("summarize", help="판정 결과 여러 개를 judge.md 로 모은다")
    s.add_argument("--names", nargs="+", required=True)
    s.add_argument("--u-def", choices=U_DEFS, default="r1",
                   help="결과의 지표 정의(모든 JSON 이 같아야 한다). --out 기본값도 정한다: r1 → R1 판정 폴더, r1b → R1b, r2 → R2")
    s.add_argument("--out", default=None, help=f"기본 --u-def 의 판정 폴더 ({PREREG_OUT} · {PREREG_OUT_R1B} · {PREREG_OUT_R2})")
    a = ap.parse_args(argv)
    if a.cmd == "summarize":
        out = Path(a.out) if a.out is not None else {"r1": PREREG_OUT, "r1b": PREREG_OUT_R1B, "r2": PREREG_OUT_R2}[a.u_def]
        print(summarize(a.names, out, a.u_def))
        return 0
    r2 = a.u_def == "r2"
    if a.config is None:
        a.config = CONFIG_R2 if r2 else CONFIG
    out = Path(a.out if a.out is not None else (PREREG_OUT_R2 if r2 else PREREG_OUT))
    seeds = a.seeds or (EVAL_SEEDS_R2 if r2 else EVAL_SEEDS)
    for folder, check in ((PREREG_OUT, prereg_problems), (PREREG_OUT_R2, prereg_problems_r2)):
        if out.resolve() == folder.resolve():
            bad = check(a, seeds)
            if bad:
                ap.error(f"사전 등록 폴더 {folder} 에는 PREREG 조건만 쓴다(결과를 덮지 않게). 다른 조건: " + ", ".join(bad)
                         + ". smoke·부분 실행·보정 시드는 --out 에 다른 폴더를 준다")
    judge(a.model, a.name, seeds, a.steps, out, a.config, a.freeze_variant, a.workers, a.policies, a.tail, udef=a.u_def)
    print((out / f"{a.name}.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
