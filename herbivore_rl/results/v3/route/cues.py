"""도망길 단서 측정 (10-22 사용자 결정 '고를 단서부터 더 잼 (추천)' — 설계 Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 9절 뒤, 학습 전, 보고만).

물음: 사슴이 그 순간 알 수 있는 단서로 '숲 그늘(COVER) / 은신처(SHELTER) / 그냥 달리기(RUN)' 가운데 어느 길이 나은지 가를 수 있나.
앞선 측정(runs/m1·m2_f30·m2_f15): 모든 도주 평균으로는 COVER 가 해롭고 SHELTER 가 낫다. 쫓기고 길마다 결과가 다른 도주(약 25 %)만 보면 가장 좋은 길이
RUN 54 % · COVER 28 % · SHELTER 18 %(숲 시야 r 3·block 2), 오라클은 쫓긴 시간 약 5.7 → 2.1 초(늘 SHELTER 3.8 초). 기존 8 특징 깊이 3 나무는 실패(확인 n ≈ 60).

측정 (run): 오라클(oracle.py)과 같은 RUN 판(N 세계, wild_flight.route_fixed 'run', 끝 규칙 quiet_end 0, 판 1800 스텝 끝까지)을 돌리며 **모든 도주 시작**
  (route_onset)을 베르누이로 솎는다(`sample_onsets` — 시작마다 균등 난수 하나, 사슴 번호 차례): 쫓기며 시작(`chased_mask` = 도망 기록 `_fl_tgt`:
  스텝 끝 사냥 중(`_wf_hunting`) 늑대의 pred_target — 도망 기록 '쫓김 창' 첫 스텝과 같은 셈)이면 확률 p_chased, 아니면 p_unchased. 뽑힐 확률이 알려져
  있어 무게 = 1/p (쫓김 층 안은 같은 무게 — 시작마다 평균, 모든 시작 = 두 층을 무게로 합친 값). 쫓김은 사슴이 모르는 값이라 고르는 모델에 넣지 않고
  층 표시로만 쓴다(배포한 고르기는 모든 시작에서 돈다). 시작마다 세계를 복제해 길 RUN·COVER(가능하면)·SHELTER(가능하면)·OPEN(측정 전용) × 흐름 3
  (oracle.rollout_one 그대로), 가짜 오라클(두뇌 길 COVER·SHELTER 팔마다 같은 흐름 열쇠의 RUN — 가능한 팔만, OPEN 가짜는 쓰지 않아 돌지 않음)도 돈다. 값 = 쫓긴 시간(관문 1차 P1 잣대, oracle.value — 잡힘·
  굶음·안 끝남 = 300 스텝 = 40 초). 시작 순간의 단서(아래 표)를 함께 적는다. 도주 밖 행동 = obs21zero argmax (route_rules·oracle 과 같다).
조건(세계 덮기, route_rules.apply_world_set): on = 숲 시야 켬(r 3.0·block 2.0 — 판단 조건, --world-set 으로 바꾸면 판단하지 않음), off = 덮기 없음
  (숲 시야 끔 — 견줌, --compare-set, 고르기 확률 × COMPARE_SCALE 0.5). 판단 시드 36000~36099 × 지역 3 — 앞선 도망길 측정(34900~34999)·관문(35000~35199)·R6(33200~33299)이 쓰지 않은
  범위. 연기 시험은 탐색 시드 34900~34902(판단 시드를 미리 보지 않는다).

단서 표 (시작 스텝 끝 — 'P' = 알 수 있음, 'X' = 알 수 없음(특권): 진단 전용, 판단 모델에 넣지 않는다. 길이 m(1 단위 = 2 m), 속력 m/s(단위/스텝 × 15)).
  P 의 약속: 늑대 단서는 **알아챈(wf_pvis — 눈(줄기·잎 가림 포함)·발소리) 사냥 중 늑대만**(설계 7절·부록 '알아챔만'). 길 기하(cover_*·shelter_*·
  관측 22·23 의 재료)만 반사와 같은 S = near_h(안전 거리 safe_r 40 m 안 사냥 중 늑대의 실거리, hold_awake 면 깨어 있는 늑대 — 설계 6절)를 쓴다.
  알아채지 못한 늑대의 위치·속도·종류·표적, safe_r 밖 늑대는 P 에 들어가지 않는다(시험 `test_perceivable_cues_ignore_unnoticed_wolves`).
  | 단서 | 종류 | 뜻 |
  |---|---|---|
  | obs_<이름> × 21 | P | 두뇌 관측 21 칸(계약 순서 OBS21 — food_density … threat_hidden), 시작 스텝 관측 |
  | cover_reach | P | 단계 4 관측 22: COVER 가능이면 H*(가림 몫), 아니면 0 |
  | shelter_reach | P | 단계 4 관측 23: SHELTER 가능이면 clip(μ*/10, 0, 1), 아니면 0 |
  | cover_h_best | P | 남은 COVER 후보의 가장 큰 H (가능 문턱 1/3 밑이어도) |
  | cover_dirs | P | 남은 COVER 후보 방향 수 (벽·경주로 빼고 남은 것, 0~7) |
  | cover_turn_deg | P | 가장 좋은 COVER 방향 j* 가 a₀(늑대 반대)에서 꺾는 각 |θ| (상수 표 ROUTE_COVER_DEG), 후보 없으면 90 |
  | cover_margin_m | P | j* 길 위 경주 여유 min_n[min_{m∈S} |q_m − x_n| − |x_n − p|], 후보 없으면 −1 |
  | shelter_ok | P | SHELTER 가능 (0/1) |
  | shelter_edge_m | P | 은신처 가장자리까지 (가능하면 k*, 아니면 가장 가까운 은신처) |
  | shelter_margin_m | P | 그 은신처 입구 경주 여유 μ = min_{m∈S} |q_m − 입구| − e |
  | shelter_cos | P | 그 은신처 쪽과 a₀ 의 cos |
  | trunks_5m · trunks_10m | P | 원판(줄기·바위) 가장자리가 5·10 m 안인 수 |
  | foliage_5m · foliage_10m | P | 잎 원 가장자리가 5·10 m 안인 수 (숲 시야 끔 = 0) |
  | in_foliage | P | 잎 원 안 (0/1) |
  | trunk_near_m | P | 가장 가까운 원판 가장자리 (없으면 120) |
  | wall_away_m | P | a₀ 방향으로 무대 벽까지 |
  | wall_min_m | P | 가장 가까운 무대 벽 |
  | n_noticed | P | 알아챈 사냥 중 늑대 수 |
  | wolf_dist_m · wolf2_dist_m | P | 알아챈 사냥 중 늑대 가운데 가장 가까운·둘째 거리 (없으면 120) |
  | wolf_closing_ms | P | 가장 가까운 알아챈 늑대가 다가오는 속력 (+ = 다가옴, 반사의 다가옴 판정과 같은 꼴) — 늑대 종류의 관측 대리 |
  | wolf_speed_ms | P | 그 늑대 속력 (걸음새로 보이는 값) |
  | wolf_bearing_cos | P | 사슴 머리 방향과 그 늑대 쪽의 cos (1 = 앞, −1 = 뒤 — 세계의 위협 시야각 식 (ex·hx + ey·hy)/d 그대로, 삼각함수 없음) |
  | wolf_heard | P | 그 늑대 발소리 반경 안 (hearing_radius × 비 배수, cap_to_sight) |
  | wolf_eye_blocked | P | 사슴 → 그 늑대 눈길이 줄기·잎에 가림 (들어서만 앎) |
  | wolf_running | P | 그 늑대가 전력 걸음 (pred_running) |
  | sight_mult | P | 날씨 시야 배수 |
  | region | X | 지역 (원-핫, 진단 전용) |
  | wolf_stalker | X | 가장 가까운 알아챈 늑대가 잠행형 (종류 — 관측 대리는 wolf_closing_ms·wolf_speed_ms) |
  | n_hunt_safe | X | 안전 거리 안 사냥 중 늑대의 실제 수 (알아챔과 무관) |
  | n_unnoticed_safe | X | 그 가운데 못 알아챈 수 |
  | n_hunt_all | X | 무대 전체 사냥 중 늑대 수 |
  | wolf_any_dist_m · wolf2_any_dist_m | X | 알아챔과 무관하게 가장 가까운·둘째 사냥 중 늑대 거리 (무대 전체, 없으면 120) |
  | wolf_any_closing_ms | X | 그 (알아챔과 무관하게 가장 가까운) 늑대가 다가오는 속력 |
  | wolf_any_noticed | X | 그 늑대를 알아챔 (0/1) |
  | n_targeting | X | 이 사슴을 표적으로 둔 사냥 중 늑대 수 (≥ 1 ⇔ 쫓김 층) |
  | tgt_dist_m · tgt_closing_ms | X | 표적으로 둔 가장 가까운 늑대의 거리·다가오는 속력 |
  | tgt_stalker · tgt_pounce | X | 표적 둔 늑대 가운데 잠행형·덮침 중이 있음 |
  날씨는 지역마다 늘 같고(맑음·비·눈) sight_mult·obs_visibility 로 알 수 있다 — 날씨 이동 배수(사슴·늑대)는 그 정해진 함수라 따로 적지 않는다
  (10-22 연기 시험: X 로 두면 P 의 정확한 일차식으로 잡혔다). 지역 원-핫도 날씨로 가려지므로 '+ 특권' 묶음에서만 쓴다.
  기호: p 사슴, q_m 늑대, a₀ = 반사와 같은 늑대 집합 S 의 거리 역수 가중 반대(은신처 굽히기 전), x_n = p + 2n·e_{j*}(n = 1..6), 입구 = 은신처 쪽
  가장자리 점. 기하는 world.flight_route_geometry 를 시작 상태로 다시 불러 얻고(세계가 남긴 route_cover_h·route_cand_ok·route_shelter_mu 와 같은지
  check 에 적는다), 경주 여유·은신처 값만 같은 식으로 더 잰다. 보고에 'X 칸 가운데 P 칸의 정확한 일차식인 것'(x_from_p)을 적는다(있으면 P 가 X 를 샌다).

분석 (report): 시드로 묶은 GroupKFold 5 겹(한 시드의 지역 셋은 같은 겹)으로 모든 뽑은 시작에 한 번 맞춘다 — 분류기(깊이 3·6 나무, HistGradientBoosting
  분류, 다항 로지스틱)는 맞춤 몫의 **비기지 않은 시작만**(두 층 모두, 무게 1/p — 비긴 시작의 정답은 정의상 아무 길이라 넣지 않는다), regret 직접(길마다
  쫓긴 시간 HistGradientBoosting 회귀 → 가능한 길 가운데 가장 짧은 것)은 모든 시작(무게 1/p). 분류기는 가능한 길만 고른다(predict_proba 를 가림).
  기준 = 늘 RUN, 늘 SHELTER(가능할 때, 아니면 RUN), 늘 COVER(같은 꼴, 보고만). 같은 확인 몫 고르기를 네 부분 집합에서 잰다: 쫓긴·비기지 않은 시작
  (판단 1~3), 모든 시작(무게 — 판단 4, 배포 모집단), 모든 쫓긴 시작·쫓기지 않은 시작(보고만). 잰 값: (무게) 평균 쫓긴 시간(초), 늘 RUN·늘 SHELTER 대비
  이득과 시드 묶음 짝 95 % 신뢰구간(같은 시작끼리 차이, 시드별 무게 합으로 묶은 표준오차, t(시드 수 − 1)), 오라클 간격 가운데 잡은 몫(늘 SHELTER →
  오라클 잡음 뺀 값), 정확도(가장 짧은 길을 고른 몫), 가장 좋은 모델의 순열 중요도(쫓긴·비기지 않은 시작 안에서 단서 하나를 겹마다 섞었을 때 평균
  쫓긴 시간이 늘어난 초, 5 번 평균). 단서 묶음 둘: 알 수 있음(P)만 · P + 특권(X).

미리 적은 판단 규칙 (CUES_RULE.md 와 같다 — 본 측정 전에 적음, 10-22 고침):
  판단 조건 = on · 판단 시드(아래 연장 하나만 허용) · 미리 정한 측정 조건(prereg_head — 덮기·quiet_end 0·흐름 3·롤아웃 300·판 1800·고르기 확률·기본
  두뇌·스냅숏·연기 시험 아님). 어긋나면 판단하지 않는다. 가장 좋은 모델 = P 만 쓴 모델 가운데 쫓긴·비기지 않은 시작의 확인 몫 평균 쫓긴 시간이 가장
  짧은 것(기준 셋 뺌). 진행(길 고르기 계약) = 넷 모두: 쫓긴·비기지 않은 시작에서 (1) 늘 SHELTER − 모델 ≥ 0.3 초, (2) 그 차이 ÷ (늘 SHELTER − 오라클
  잡음 뺀 값) ≥ 30 %(간격 ≤ 0 이면 아님), (3) 모델 − 늘 SHELTER 의 시드 묶음 짝 95 % 신뢰구간 위 끝 < 0, 그리고 (4) 같은 모델을 모든 시작(무게)에
  쓴 모델 − 늘 SHELTER 의 95 % 신뢰구간 위 끝 < 0. 진행이면 순열 중요도 위 단서를 새 관측 칸 후보로 적는다(이미 관측 21 칸이면 표시). 하나라도
  아니면 두 길(RUN + SHELTER) 안을 권한다. 표본 조건: 쫓긴·비기지 않은 시작 ≥ 1,000·시드 ≥ 30 — 모자라면 판단하지 않는다.
  연장(미리 정함, 한 번): 판단 시드 36000~36099 를 다 잰 뒤 쫓긴·비기지 않은 시작이 1,000 밑일 때만(개수만 본다) 36100~36199 를 같은 명령에 --seeds
  36000-36199 로 이어 돌리고, 판단은 그 끝에 한 번 한다. 그 밖의 시드 범위는 판단하지 않는다. 중간 보고는 개수만 낸다(결과 표 눈가림).
  숲 시야 끔(off)·쫓긴 시작 전체·쫓기지 않은 시작·P + 특권은 함께 보고만 한다.

    # herbivore_rl/ 에서 (PYTHONUTF8=1)
    python results/v3/route/cues.py run --out <폴더> [--workers 14]          # worlds_<조건>.jsonl(세계마다 이어 씀) → raw_<조건>.json → report
    python results/v3/route/cues.py run --out <폴더> --smoke                 # 탐색 시드 3 · 600 스텝 · 확률 0.25·0.03 · 워커 ≤ 8 (도구 확인 + 본 측정 어림)
    python results/v3/route/cues.py report --out <폴더>                      # cues.json·cues.md (끝나지 않은 조건은 jsonl 로 개수만 — 판단 없음)
이어 돌리기: worlds_<조건>.jsonl 첫 줄 = 머리(조건·덮기·시드·고르기 확률·흐름·최대 스텝·판 길이·두뇌·스냅숏·셈 길 지문). 같은 명령으로 다시 돌리면
  끝난 세계를 건너뛴다. 머리가 다르면(덮기·확률·지문 — 코드가 바뀜 포함, 시드 범위는 빼고 견줌) 멈춘다(--force 면 그 조건을 지우고 처음부터). 시드를
  늘려 이어 돌릴 수 있지만(세계는 (시드, 지역)으로 적으니 섞이지 않는다) 판단은 위 연장 규칙 하나만 받는다. 조건이 끝나면 raw_<조건>.json, 측정 중
  지문이 바뀌면 지문 없이 적고 멈춘다(route_rules·oracle 과 같은 꼴 — rr.code_tag).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

import oracle as orc  # noqa: E402  (route_rules 가 sys.path·torch 순서를 맞춘다)

import numpy as np  # noqa: E402

rr = orc.rr
ad, lv = rr.ad, rr.lv

CUES_TAG = 0x435545                 # "CUE"
SEEDS = (36000, 36099)              # 판단 시드 (쓴 적 없는 범위 — 34900~34999 도망길 탐색, 35000~35199 관문, 33200~33299 R6 가 아님)
EXT_SEEDS = (36100, 36199)          # 미리 정한 연장 한 번 (판단 시드의 쫓긴·비기지 않은 시작 < MIN_N 일 때만)
SMOKE_SEEDS = (34900, 34902)        # 연기 시험 = 탐색 시드 (판단 시드를 미리 보지 않는다)
REGIONS = 3
P_CHASED, P_UNCHASED = 0.30, 0.015  # 미리 정한 고르기 확률 (10-22 연기 시험 runs/cues_smoke 어림 — plan, CUES_RULE.md)
MAIN_STEPS = 1800                   # RUN 판 길이 (끝까지 — 고르기 확률이 판 길이에 고르다)
STREAMS, MAX_STEPS = orc.STREAMS, orc.MAX_STEPS
QUIET_END = 0                       # 끝 규칙: 지금
SMOKE = dict(seeds=SMOKE_SEEDS, steps=600, workers=8, p_chased=0.25, p_unchased=0.03, max_steps=MAX_STEPS)
FOLIAGE_ON = ("features.obstacles.foliage.enabled=true", "features.obstacles.foliage.r=3.0", "features.obstacles.foliage.block=2.0")
CONDS = ("on", "off")               # on = 판단 조건(숲 시야 켬), off = 견줌(덮기 없음)
M_PER_U = 2.0                       # 1 단위 = 2 m
STEP_S = orc.STEP_S
MS_PER_UPS = M_PER_U / STEP_S       # 단위/스텝 → m/s (× 15)
FAR_M = 120.0                       # '없음' 거리 (무대 한 변)
FOLDS = 5
TIE_EPS = 1e-9
BRAIN = (0, 1, 2)                   # RUN·COVER·SHELTER (두뇌 길) — OPEN(3)은 측정 전용
ROUTES = ("run", "cover", "shelter", "open")
# 판단 규칙 (CUES_RULE.md)
PROCEED_S, PROCEED_GAP = 0.3, 0.30
MIN_N, MIN_SEEDS = 1000, 30
TARGET_NONTIED = 3000               # 어림 목표: 쫓긴·비기지 않은 시작 (on — 점 추정으로)
PLAN_FLOOR = 1.5                    # 어림 바닥: 비기지 않은 몫의 아래 끝에서도 MIN_N × 1.5
TARGET_UNCHASED = 2000              # 어림 목표: 쫓기지 않은 시작 (on — 판단 4 의 모든 시작 평균)
COMPARE_SCALE = 0.5                 # off(보고만)의 두 확률 배수 — 시간을 줄인다
PERM_REPEATS = 5
REF_SEC_14W = 0.0118                # 워커 14 의 세계-스텝당 초 (runs/m2_f30 오라클, 숲 시야 켬 — 어림의 바닥값)
PLAN_Z = 1.2816                     # 어림의 비기지 않은 몫 = 한쪽 90 % Wilson 아래 끝 (연기 시험 표본이 작다)

OBS21 = ("food_density", "pred_count", "pred_dist", "kin_count", "energy", "recent_predation", "cover_dist", "visibility", "to_transition",
         "pred_approach", "kin_alarm", "beh_graze", "beh_flee", "beh_hide", "beh_freeze", "beh_sleep", "beh_steps", "threat_recency",
         "escape_room", "obstacle_near", "threat_hidden")
GEO_P = ("cover_reach", "shelter_reach", "cover_h_best", "cover_dirs", "cover_turn_deg", "cover_margin_m", "shelter_ok", "shelter_edge_m",
         "shelter_margin_m", "shelter_cos", "trunks_5m", "trunks_10m", "foliage_5m", "foliage_10m", "in_foliage", "trunk_near_m",
         "wall_away_m", "wall_min_m", "n_noticed", "wolf_dist_m", "wolf2_dist_m", "wolf_closing_ms", "wolf_speed_ms",
         "wolf_bearing_cos", "wolf_heard", "wolf_eye_blocked", "wolf_running", "sight_mult")
PRIV = ("wolf_stalker", "n_hunt_safe", "n_unnoticed_safe", "n_hunt_all", "wolf_any_dist_m", "wolf2_any_dist_m", "wolf_any_closing_ms",
        "wolf_any_noticed", "n_targeting", "tgt_dist_m", "tgt_closing_ms", "tgt_stalker", "tgt_pounce")
PERCEIVABLE = tuple(f"obs_{k}" for k in OBS21) + GEO_P
CUE_KIND = {**{k: "perceivable" for k in PERCEIVABLE}, **{k: "privileged" for k in PRIV}, "region": "privileged"}
MODELS = ("tree3", "tree6", "hgb", "logreg", "regret")
CLASSIFIERS = ("tree3", "tree6", "hgb", "logreg")
BASES = ("run", "shelter", "cover")
FEATSETS = ("perc", "all")          # 알 수 있음만 · + 특권(지역 원-핫 포함)
SUBSETS = ("nontied", "all", "chased", "unchased")


def code_tag() -> dict:
    """셈 길 지문 (rr.code_tag — 세계 = 실시간 판정 지문, 측정 = 이 파일의 측정 함수·oracle 롤아웃 원문·상수)."""
    return rr.code_tag((_cues_world, onset_cues, chased_mask, sample_onsets, orc.rollout_one, orc.reseed, rr.apply_world_set),
                       dict(tag=CUES_TAG, nosat=lv.NOSAT, obs=OBS21, p=GEO_P, x=PRIV, m=M_PER_U))


def prereg_head() -> dict:
    """미리 정한 측정 조건 (CUES_RULE.md) — 판단은 on 머리가 이것과 같을 때만 한다(시드는 decide 가 따로 본다)."""
    return dict(world_set=lv.jsonable(rr.parse_world_set(FOLIAGE_ON)), quiet_end=QUIET_END, streams=3, max_steps=300, main_steps=MAIN_STEPS,
                p_chased=P_CHASED, p_unchased=P_UNCHASED, smoke=False, model_default=True, snapshot=rr.SNAPSHOT.name)


# --------------------------------------------------------------------- #
# 고르기·단서 (워커 안)
# --------------------------------------------------------------------- #

def chased_mask(w) -> np.ndarray:
    """(N,) bool: 스텝 끝에 사냥 중인 늑대가 표적으로 둔 사슴 — 도망 기록 `_fl_tgt`(스텝 끝 `_wf_hunting` 늑대의 pred_target, 죽은 사슴 칸 −1)와 같다.
    도주 시작 스텝에 참이면 그 도망의 '쫓김 창' 첫 스텝에 쫓긴 것이다(world._fl_update 의 _fl_chased[new] = targeted(tp)). 층 표시 전용(사슴은 모른다)."""
    out = np.zeros(w.N, dtype=bool)
    t = np.asarray(w._fl_tgt, dtype=np.int64)
    out[t[(t >= 0) & (t < w.N)]] = True
    return out


def sample_onsets(rng, idx: np.ndarray, chased: np.ndarray, p_ch: float, p_un: float) -> np.ndarray:
    """이번 스텝 도주 시작 idx(사슴 번호 오름차순)마다 균등 난수 하나(같은 차례)를 뽑아 쫓긴 시작은 p_ch, 아닌 시작은 p_un 확률로 고른다(베르누이 솎기 —
    시작마다 뽑힐 확률이 알려져 있다: 무게 1/p). 시작이 없으면 난수를 쓰지 않는다."""
    idx = np.asarray(idx, dtype=np.int64)
    if not len(idx):
        return idx
    u = rng.random(len(idx))
    return idx[u < np.where(np.asarray(chased, dtype=bool), float(p_ch), float(p_un))]


def onset_cues(w, i: int) -> tuple[dict, dict]:
    """도주 시작 스텝 끝 세계 w 의 사슴 i 단서(모듈 docstring 표 — PERCEIVABLE·PRIV 칸) → (단서 dict, check dict). check = 다시 부른 기하가 세계가 남긴
    route_* 훅과 같은가(cover_h·cover_ok·shelter_ok·shelter_mu·cover_raw). P 늑대 단서는 알아챈(wf_pvis) 사냥 중 늑대만 쓴다."""
    from env_v2.world import (EPS, PT_STALKER, ROUTE_COVER, ROUTE_COVER_COS, ROUTE_COVER_DEG, ROUTE_COVER_POINTS, ROUTE_COVER_SIN,
                              ROUTE_COVER_STEP_U, ROUTE_SHELTER, ROUTE_SHELTER_REACH_U, ST_POUNCE, flight_route_geometry, hearing_radius,
                              normalize, sight_blocked)

    i = int(i)
    wf, g, cfg = w._wf, w._g, w.cfg
    if tuple(w.obs_names) != OBS21:
        raise ValueError(f"관측 칸이 OBS21 과 다르다: {w.obs_names}")
    obs = np.asarray(w._obs[i], dtype=np.float64)
    c: dict = {f"obs_{k}": float(obs[j]) for j, k in enumerate(OBS21)}
    P = w.pos[i:i + 1]
    p = P[0]
    q = w.pred_pos
    M = w.M
    # 반사와 같은 꼴 ((1, M) — `_wf_update` 와 같은 셈 순서)
    ex = q[:, 0][None, :] - P[:, 0:1]
    ey = q[:, 1][None, :] - P[:, 1:2]
    pd = np.sqrt(ex * ex + ey * ey)
    pinv = 1.0 / np.maximum(pd, EPS)
    hunt = w._wf_hunting()
    near_h = hunt[None, :] & (pd <= wf["safe_r"])
    if wf["hold_awake"]:
        awake = ~w.pred_asleep if w._ps is not None else np.ones(M, dtype=bool)
        near_h = awake[None, :] & (pd <= wf["safe_r"])
    wt = near_h / np.maximum(pd, 0.5)
    a0 = normalize(np.stack([-(ex * pinv * wt).sum(1), -(ey * pinv * wt).sum(1)], 1))
    if not (a0 * a0).sum() > EPS * EPS and near_h.any():
        j = int(np.where(near_h, pd, np.inf).argmin(1)[0])
        a0 = -np.stack([ex[:, j], ey[:, j]], 1) * pinv[:, j][:, None]
    discs = (w.obstacles if w._ob is not None and w._ob["block_sight"] and len(w.obstacles) else np.zeros((0, 3)))
    fol = w._fol_args()
    geo = flight_route_geometry(P, a0, q, near_h, pd, w.cov_c, w.cov_r, discs, w.size, wf["wall_margin"], wf["edge_r"], None, None, fol)
    ok_c, ok_s = bool(geo["cover_ok"][0]), bool(geo["shelter_ok"][0])
    chk = dict(cover_h=bool(geo["cover_best_h"][0] == w.route_cover_h[i]), cover_ok=ok_c == bool(w.route_cand_ok[i, ROUTE_COVER]),
               shelter_ok=ok_s == bool(w.route_cand_ok[i, ROUTE_SHELTER]),
               shelter_mu=bool((geo["shelter_mu"][0] if ok_s else 0.0) == w.route_shelter_mu[i]),
               cover_raw=bool(np.array_equal(geo["cover_raw"][0], w.route_cover_raw[i])))
    chk["all"] = all(chk.values())
    # --- 길 (관측 22·23 과 그 재료 — S = near_h, 설계 6절) ---
    c["cover_reach"] = float(w.route_cover_h[i]) if w.route_cand_ok[i, ROUTE_COVER] else 0.0
    c["shelter_reach"] = float(np.clip(w.route_shelter_mu[i] / ROUTE_SHELTER_REACH_U, 0.0, 1.0)) if w.route_cand_ok[i, ROUTE_SHELTER] else 0.0
    c["cover_h_best"] = float(geo["cover_best_h"][0])
    valid = geo["cover_valid"][0]
    c["cover_dirs"] = float(np.count_nonzero(valid[:len(ROUTE_COVER_DEG)]))
    jj = int(geo["cover_j"][0])
    S = near_h[0]
    if 0 <= jj < len(ROUTE_COVER_DEG):
        e = np.array([ROUTE_COVER_COS[jj] * a0[0, 0] - ROUTE_COVER_SIN[jj] * a0[0, 1], ROUTE_COVER_SIN[jj] * a0[0, 0] + ROUTE_COVER_COS[jj] * a0[0, 1]])
        sn = ROUTE_COVER_STEP_U * np.arange(1, ROUTE_COVER_POINTS + 1, dtype=np.float64)
        xs = p[None, :] + sn[:, None] * e[None, :]
        dq = np.sqrt(((q[None, :, :] - xs[:, None, :]) ** 2).sum(-1))                     # (6, M)
        race = (np.where(S[None, :], dq, np.inf).min(1) - sn).min() if S.any() else FAR_M / M_PER_U
        c["cover_turn_deg"] = abs(float(ROUTE_COVER_DEG[jj]))
        c["cover_margin_m"] = float(race) * M_PER_U
    else:
        c["cover_turn_deg"], c["cover_margin_m"] = 90.0, -1.0
    c["shelter_ok"] = float(ok_s)
    if len(w.cov_r):
        v = w.cov_c - p[None, :]
        dc = np.sqrt((v * v).sum(1))
        ed = dc - w.cov_r
        k = int(geo["shelter_k"][0]) if ok_s else int(ed.argmin())
        ent = p + ed[k] * v[k] / max(dc[k], EPS)
        dqe = np.sqrt(((q - ent[None, :]) ** 2).sum(1))
        c["shelter_edge_m"] = float(ed[k]) * M_PER_U
        c["shelter_margin_m"] = (float(dqe[S].min() - ed[k]) if S.any() else FAR_M / M_PER_U) * M_PER_U
        c["shelter_cos"] = float((v[k] @ a0[0]) / max(dc[k], EPS))
    else:
        c["shelter_edge_m"], c["shelter_margin_m"], c["shelter_cos"] = FAR_M, FAR_M, 0.0
    # --- 숲·벽 ---
    ob = np.asarray(w.obstacles, dtype=np.float64).reshape(-1, 3)
    oe = np.sqrt(((ob[:, :2] - p[None, :]) ** 2).sum(1)) - ob[:, 2] if len(ob) else np.zeros(0)
    c["trunks_5m"] = float(np.count_nonzero(oe <= 5.0 / M_PER_U))
    c["trunks_10m"] = float(np.count_nonzero(oe <= 10.0 / M_PER_U))
    c["trunk_near_m"] = float(oe.min()) * M_PER_U if len(oe) else FAR_M
    if fol is not None and len(fol[0]):
        fd = np.sqrt(((np.asarray(fol[0]) - p[None, :]) ** 2).sum(1))
        fe = fd - float(fol[1])
        c["foliage_5m"] = float(np.count_nonzero(fe <= 5.0 / M_PER_U))
        c["foliage_10m"] = float(np.count_nonzero(fe <= 10.0 / M_PER_U))
        c["in_foliage"] = float((fd < float(fol[1])).any())
    else:
        c["foliage_5m"] = c["foliage_10m"] = c["in_foliage"] = 0.0
    tw = [((w.size - p[a]) / a0[0, a]) if a0[0, a] > EPS else ((0.0 - p[a]) / a0[0, a]) if a0[0, a] < -EPS else np.inf for a in (0, 1)]
    c["wall_away_m"] = float(min(tw)) * M_PER_U if np.isfinite(min(tw)) else FAR_M
    c["wall_min_m"] = float(min(p[0], p[1], w.size - p[0], w.size - p[1])) * M_PER_U
    # --- 늑대: P = 알아챈 사냥 중 늑대만 (설계 7절·부록 '알아챔만'), X = 알아챔과 무관한 실제 값 ---
    pv = np.asarray(g["wf_pvis"][i], dtype=bool) if M else np.zeros(0, dtype=bool)
    d0 = pd[0]
    spd = np.sqrt((w.pred_vel * w.pred_vel).sum(1))
    hd = w.head[i]

    def closing(m):
        return float(-(w.pred_vel[m, 0] * ex[0, m] + w.pred_vel[m, 1] * ey[0, m]) * pinv[0, m]) * MS_PER_UPS

    seen = np.flatnonzero(hunt & pv)
    order = seen[np.argsort(d0[seen], kind="stable")]
    c["n_noticed"] = float(len(seen))
    if len(order):
        m = int(order[0])
        c["wolf_dist_m"] = float(d0[m]) * M_PER_U
        c["wolf2_dist_m"] = float(d0[order[1]]) * M_PER_U if len(order) > 1 else FAR_M
        c["wolf_closing_ms"] = closing(m)
        c["wolf_speed_ms"] = float(spd[m]) * MS_PER_UPS
        c["wolf_bearing_cos"] = float((hd[0] * ex[0, m] + hd[1] * ey[0, m]) * pinv[0, m])
        heard = 0.0
        if w._zh is not None:
            r = float(hearing_radius(w._zh, np.array([spd[m] / cfg.herb_speed]), np.array([bool(w.pred_running[m])]))[0])
            if w._wx is not None:
                r *= float(w._wx_hear)
            see_p = cfg.see_r if w._dn is None else float(w._see_pred)
            if w._rp is not None:
                see_p *= float(w._rep_see[i])
            lim = min(r, see_p) if w._zh["cap_to_sight"] else r
            heard = float(d0[m] <= lim and r > 0.0)
        c["wolf_heard"] = heard
        c["wolf_eye_blocked"] = float(sight_blocked(P, q[m:m + 1], discs, fol)[0, 0]) if (len(discs) or fol is not None) else 0.0
        c["wolf_running"] = float(bool(w.pred_running[m]))
        c["wolf_stalker"] = float(w.pred_type[m] == PT_STALKER)
    else:
        c.update(wolf_dist_m=FAR_M, wolf2_dist_m=FAR_M, wolf_closing_ms=0.0, wolf_speed_ms=0.0, wolf_bearing_cos=0.0, wolf_heard=0.0,
                 wolf_eye_blocked=0.0, wolf_running=0.0, wolf_stalker=0.0)
    c["sight_mult"] = float(w._wx_sight) if w._wx is not None else 1.0
    # --- 특권 ---
    allh = np.flatnonzero(hunt)
    oa = allh[np.argsort(d0[allh], kind="stable")]
    if len(oa):
        c["wolf_any_dist_m"] = float(d0[oa[0]]) * M_PER_U
        c["wolf2_any_dist_m"] = float(d0[oa[1]]) * M_PER_U if len(oa) > 1 else FAR_M
        c["wolf_any_closing_ms"] = closing(int(oa[0]))
        c["wolf_any_noticed"] = float(pv[oa[0]])
    else:
        c.update(wolf_any_dist_m=FAR_M, wolf2_any_dist_m=FAR_M, wolf_any_closing_ms=0.0, wolf_any_noticed=0.0)
    c["n_hunt_safe"] = float(np.count_nonzero(hunt & (d0 <= wf["safe_r"])))
    c["n_unnoticed_safe"] = float(np.count_nonzero(hunt & (d0 <= wf["safe_r"]) & ~pv))
    c["n_hunt_all"] = float(len(allh))
    tgt = np.asarray(w._fl_tgt, dtype=np.int64)
    targeting = np.flatnonzero(tgt == i)
    c["n_targeting"] = float(len(targeting))
    if len(targeting):
        mt = int(targeting[np.argmin(d0[targeting])])
        c["tgt_dist_m"] = float(d0[mt]) * M_PER_U
        c["tgt_closing_ms"] = closing(mt)
        c["tgt_stalker"] = float((w.pred_type[targeting] == PT_STALKER).any())
        st = getattr(w, "stalk_state", None)
        c["tgt_pounce"] = float(st is not None and (np.asarray(st)[targeting] == ST_POUNCE).any())
    else:
        c.update(tgt_dist_m=FAR_M, tgt_closing_ms=0.0, tgt_stalker=0.0, tgt_pounce=0.0)
    missing = [k for k in PERCEIVABLE + PRIV if k not in c]
    if missing:
        raise KeyError(f"단서가 빠졌다: {missing}")
    return {k: c[k] for k in PERCEIVABLE + PRIV}, chk


def _cues_world(job: dict) -> dict:
    """세계 하나: RUN 판을 끝까지 돌리며 도주 시작을 베르누이로 솎아(sample_onsets — 쫓김 p_chased, 아니면 p_unchased) 단서를 적고, 길(가능한 것) × 흐름
    + 가짜 RUN(가능한 팔) × 흐름을 돈다."""
    from env.config import Config
    from env_v2 import rollout as ro
    from env_v2.world import ROUTE_NAMES, ROUTE_RUN, World

    t0 = time.perf_counter()
    seed, reg_i, qe = int(job["seed"]), int(job["region_index"]), int(job["quiet_end"])
    w = World(Config(job["cfg"]), seeds=[seed])
    ad.apply_snapshot_food(w, job["snap_food"])
    w.track_flight = True
    pol = ro.build_policy({"kind": "rep_learned", "path": str(job["model"])}, seed)
    ro.forward_bind(pol, w)
    S, ms = int(job["streams"]), int(job["max_steps"])
    p_ch, p_un = float(job["p_chased"]), float(job["p_unchased"])
    pick = np.random.default_rng([CUES_TAG, 2, seed, reg_i, qe])
    recs, main_n, roll_n, seen_on, seen_ch = [], 0, 0, 0, 0
    for _ in range(int(job["steps"])):
        w.step(np.asarray(pol(w.observe()), dtype=np.float64))
        main_n += 1
        cm = chased_mask(w)
        idx = np.flatnonzero(w.route_onset & w.alive)
        seen_on += len(idx)
        seen_ch += int(np.count_nonzero(cm[idx]))
        took = sample_onsets(pick, idx, cm[idx], p_ch, p_un)
        for i in took:
            i = int(i)
            uid = len(recs)
            ok = [bool(x) for x in w.route_cand_ok[i]]
            cues, chk = onset_cues(w, i)
            L0 = int(w._fl_len[i])
            arms = {}
            for r in range(len(ROUTE_NAMES)):
                if ok[r]:
                    arms[f"real{r}"] = [orc.rollout_one(w, pol, i, r, [CUES_TAG, seed, reg_i, qe, uid, 3 * r + s], ms, L0) for s in range(S)]
            for a in BRAIN[1:]:                                   # 가짜 오라클은 두뇌 길만 쓴다(base_values)
                if ok[a]:
                    arms[f"fake{a}"] = [orc.rollout_one(w, pol, i, ROUTE_RUN, [CUES_TAG, seed, reg_i, qe, uid, 3 * a + s], ms, L0) for s in range(S)]
            n = sum(x["n"] for v in arms.values() for x in v)
            roll_n += n
            recs.append(dict(t=int(w.t), deer=i, chased=bool(cm[i]), ok=ok, cues=cues, check=chk, L0=L0, roll=n, arms=arms))
        if len(took):
            ro.forward_bind(pol, w)
    return dict(seed=seed, region=job["region"], region_index=reg_i, p_chased=p_ch, p_unchased=p_un, onsets=recs, main_steps=main_n,
                roll_steps=roll_n, onsets_seen=seen_on, chased_seen=seen_ch, wall_s=round(time.perf_counter() - t0, 2))


# --------------------------------------------------------------------- #
# 표 (분석 입력)
# --------------------------------------------------------------------- #

def onset_rows(worlds: list) -> list:
    """세계 목록 → 시작 목록 (시드·지역·뽑힐 확률 p 를 붙인다)."""
    out = []
    for w in worlds:
        for o in w["onsets"]:
            ch = bool(o.get("chased", True))
            out.append(dict(o, seed=int(w["seed"]), region=w["region"], chased=ch, p=float(w.get("p_chased" if ch else "p_unchased", 1.0))))
    return out


def table(rows: list, cap: int, regions: list | None = None) -> dict:
    """시작 목록 → 배열: real (K, 4)·fake (K, 4) 흐름 평균 쫓긴 시간(초, 돌지 않은 팔 nan — fake 0 = real 0), ok (K, 4), seed·region·chased (K,),
    wt (K,) = 1/p (뽑힐 확률의 역수), nt (K,) 비기지 않음, X (K, F) 단서(PERCEIVABLE + PRIV + 지역 원-핫), names (F,)."""
    K = len(rows)
    real, fake = np.full((K, 4), np.nan), np.full((K, 4), np.nan)
    for k, r in enumerate(rows):
        for a in range(4):
            if f"real{a}" in r["arms"]:
                real[k, a] = np.mean([orc.value(x, cap) for x in r["arms"][f"real{a}"]]) * STEP_S
            if a and f"fake{a}" in r["arms"]:
                fake[k, a] = np.mean([orc.value(x, cap) for x in r["arms"][f"fake{a}"]]) * STEP_S
        fake[k, 0] = real[k, 0]
    ok = np.array([r["ok"] for r in rows], dtype=bool).reshape(K, 4)
    regions = sorted({r["region"] for r in rows}) if regions is None else list(regions)
    names = list(PERCEIVABLE + PRIV) + [f"region_{g}" for g in regions]
    X = np.array([[r["cues"][n] for n in PERCEIVABLE + PRIV] + [float(r["region"] == g) for g in regions] for r in rows],
                 dtype=np.float64).reshape(K, len(names))
    p = np.array([float(r.get("p", 1.0)) for r in rows], dtype=np.float64)
    return dict(real=real, fake=fake, ok=ok, X=X, names=names, seed=np.array([r["seed"] for r in rows], dtype=np.int64),
                region=np.array([r["region"] for r in rows], dtype=object), chased=np.array([bool(r.get("chased", True)) for r in rows], dtype=bool),
                wt=1.0 / np.maximum(p, 1e-12), nt=nontied(real, ok), roll=np.array([float(r.get("roll", 0)) for r in rows]),
                check=np.array([bool(r.get("check", {}).get("all", True)) for r in rows], dtype=bool))


def brain_vals(real: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """(K, 3) 두뇌 길 값 — 가능하지 않은 길은 inf."""
    return np.where(ok[:, list(BRAIN)], real[:, list(BRAIN)], np.inf)


def nontied(real: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """가능한 두뇌 길의 흐름 평균이 서로 다른 시작 (하나만 가능하면 비김)."""
    v = np.where(ok[:, list(BRAIN)], real[:, list(BRAIN)], np.nan)
    if not len(v):
        return np.zeros(0, dtype=bool)
    return (np.nanmax(v, 1) - np.nanmin(v, 1)) > TIE_EPS


def labels(real: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """정답 = 가능한 두뇌 길 가운데 가장 짧은 것(같으면 RUN·COVER·SHELTER 순 — 비긴 시작의 정답은 뜻이 없다: 분류기는 비기지 않은 시작만 맞춘다)."""
    return brain_vals(real, ok).argmin(1) if len(real) else np.zeros(0, dtype=np.int64)


def subset(tb: dict, m: np.ndarray) -> dict:
    return {k: (v[m] if isinstance(v, np.ndarray) and len(v) == len(m) else v) for k, v in tb.items()}


def wmean(x, w) -> float:
    x = np.asarray(x, dtype=np.float64)
    w = np.asarray(w, dtype=np.float64)
    return float((w * x).sum() / w.sum()) if len(x) and w.sum() > 0 else float("nan")


def x_linear_in_p(X: np.ndarray, names: list, tol: float = 1e-7) -> dict:
    """X 칸(PRIV) 가운데 P 칸(PERCEIVABLE) + 상수의 정확한 일차식인 것(최소제곱 남은 값 ≤ tol·크기) — 있으면 P 가 그 특권 정보를 샌다. 변하지 않는 칸은
    뺀다(정보 없음). 행이 P 계수(rank + 1)보다 많지 않으면 가를 수 없어 exact None."""
    X = np.asarray(X, dtype=np.float64)
    pc = [j for j, n in enumerate(names) if n in PERCEIVABLE and np.ptp(X[:, j]) > 0] if len(X) else []
    xc = [j for j, n in enumerate(names) if n in PRIV and np.ptp(X[:, j]) > 0] if len(X) else []
    A = np.column_stack([X[:, pc], np.ones(len(X))]) if len(X) else np.zeros((0, 1))
    rank = int(np.linalg.matrix_rank(A)) if len(X) else 0
    out = dict(rows=int(len(X)), rank=rank, checked=[names[j] for j in xc], exact=None)
    if len(X) <= rank + 1:
        return out
    exact = []
    for j in xc:
        y = X[:, j]
        beta = np.linalg.lstsq(A, y, rcond=None)[0]
        if float(np.abs(A @ beta - y).max()) <= tol * max(1.0, float(np.abs(y).max())):
            exact.append(names[j])
    out["exact"] = exact
    return out


# --------------------------------------------------------------------- #
# 모델 (가능한 길만 고른다)
# --------------------------------------------------------------------- #

def folds(seeds: np.ndarray, n_splits: int = FOLDS) -> list:
    """시드로 묶은 GroupKFold (한 시드의 모든 시작 — 지역 셋 — 은 같은 겹). 시드가 둘 밑이면 []."""
    from sklearn.model_selection import GroupKFold

    k = min(int(n_splits), len(np.unique(seeds)))
    if k < 2:
        return []
    return list(GroupKFold(n_splits=k).split(np.zeros((len(seeds), 1)), groups=seeds))


def _masked_pick(score: np.ndarray, ok: np.ndarray, high: bool) -> np.ndarray:
    """(n, 3) 점수에서 가능한 두뇌 길 가운데 가장 높은(high)·낮은 것 — 같으면 앞 번호, 모두 막히면 RUN."""
    okb = ok[:, list(BRAIN)]
    s = np.where(okb, score, -np.inf if high else np.inf)
    out = s.argmax(1) if high else s.argmin(1)
    bad = ~np.isfinite(s[np.arange(len(s)), out]) if len(s) else np.zeros(0, dtype=bool)
    return np.where(bad, 0, out).astype(np.int64)


def make_clf(name: str):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeClassifier

    if name in ("tree3", "tree6"):
        return DecisionTreeClassifier(max_depth=int(name[-1]), min_samples_leaf=10, random_state=0)
    if name == "hgb":
        return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1.0,
                                              early_stopping=False, random_state=0)
    if name == "logreg":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
    raise ValueError(name)


def _reg():
    from sklearn.ensemble import HistGradientBoostingRegressor

    return HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1.0,
                                         early_stopping=False, random_state=0)


def _norm_w(w: np.ndarray) -> np.ndarray:
    w = np.asarray(w, dtype=np.float64)
    return w / w.mean() if len(w) and w.mean() > 0 else np.ones(len(w))


def base_choice(name: str, ok: np.ndarray) -> np.ndarray:
    """기준 고르기: run = 늘 RUN, shelter·cover = 가능하면 그 길(아니면 RUN)."""
    if name == "run":
        return np.zeros(len(ok), dtype=np.int64)
    r = 2 if name == "shelter" else 1
    return np.where(ok[:, r], r, 0).astype(np.int64)


def fit_model(name: str, X: np.ndarray, real: np.ndarray, ok: np.ndarray, wt: np.ndarray | None = None, nt: np.ndarray | None = None):
    """맞춘 고르기 함수 f(X, ok) → 길 번호 (n,). 기준(run·shelter·cover)은 맞추지 않는다. 분류기: 비기지 않은 시작(nt)만 정답(labels)에 무게(wt — 1/p,
    평균 1 로 맞춤)로 맞추고 predict_proba 를 가린다(비기지 않은 시작이 없거나 정답이 한 길뿐이면 그 길 — 가능하지 않으면 RUN). regret: 길마다 쫓긴 시간
    회귀(그 길이 가능한 모든 맞춤 시작, 무게 wt — 20 개 밑이면 그 길 무게 평균) → 가장 짧은 길."""
    K = len(X)
    wt = np.ones(K) if wt is None else np.asarray(wt, dtype=np.float64)
    nt = nontied(real, ok) if nt is None else np.asarray(nt, dtype=bool)
    if name in BASES:
        return lambda Z, o: base_choice(name, o)
    if name == "regret":
        regs = []
        for r in BRAIN:
            m = ok[:, r]
            if m.sum() >= 20:
                regs.append(_reg().fit(X[m], real[m, r], sample_weight=_norm_w(wt[m])))
            else:
                regs.append(wmean(real[m, r], wt[m]) if m.any() else np.inf)

        def f(Z, o):
            pr = np.column_stack([np.full(len(Z), g) if isinstance(g, float) else g.predict(Z) for g in regs]) if len(Z) else np.zeros((0, 3))
            return _masked_pick(pr, o, high=False)
        return f
    if name not in CLASSIFIERS:
        raise ValueError(name)
    if not nt.any():
        return lambda Z, o: np.zeros(len(Z), dtype=np.int64)
    y = labels(real[nt], ok[nt])
    cls = np.unique(y)
    if len(cls) == 1:
        c0 = int(cls[0])
        return lambda Z, o: np.where(o[:, c0], c0, 0).astype(np.int64)
    sw = _norm_w(wt[nt])
    est = make_clf(name)
    clf = est.fit(X[nt], y, logisticregression__sample_weight=sw) if name == "logreg" else est.fit(X[nt], y, sample_weight=sw)
    classes = np.asarray(clf.classes_, dtype=np.int64)

    def f(Z, o):
        sc = np.full((len(Z), 3), -np.inf)
        if len(Z):
            sc[:, classes] = clf.predict_proba(Z)
        return _masked_pick(sc, o, high=True)
    return f


def cv_choices(tb: dict, cols: np.ndarray, model: str, fl: list) -> tuple[np.ndarray, list]:
    """교차 검증 확인 몫의 고른 길 (K,)과 겹마다 (확인 행, 고르기 함수). 겹이 없으면 (None, [])."""
    if not fl:
        return None, []
    X = tb["X"][:, cols]
    out = np.zeros(len(X), dtype=np.int64)
    fns = []
    for tr, te in fl:
        f = fit_model(model, X[tr], tb["real"][tr], tb["ok"][tr], tb["wt"][tr], tb["nt"][tr])
        out[te] = f(X[te], tb["ok"][te])
        fns.append((te, f))
    return out, fns


def fit_all(tb: dict) -> tuple[list, dict]:
    """모든 뽑은 시작에 시드 묶음 교차 검증을 한 번 → (겹, {(단서 묶음, 모델): (고른 길 (K,), 겹 함수, 칸)})."""
    fl = folds(tb["seed"])
    choices = {}
    for fs in FEATSETS:
        cols = feature_cols(tb["names"], fs)
        for mname in MODELS:
            ch, fns = cv_choices(tb, cols, mname, fl)
            if ch is not None:
                choices[(fs, mname)] = (ch, fns, cols)
    return fl, choices


# --------------------------------------------------------------------- #
# 잣대
# --------------------------------------------------------------------- #

def cluster_ci(d: np.ndarray, groups: np.ndarray, w: np.ndarray | None = None) -> dict:
    """같은 시작끼리의 차이 d 의 (무게 w) 평균과 시드로 묶은 95 % 신뢰구간 (표준오차 = 시드별 w·(d − 평균) 합으로 묶은 값 ÷ 무게 합, t(시드 수 − 1)).
    무게가 같으면 시드별 (d − 평균) 합으로 묶은 보통 꼴과 같다."""
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    if not n:
        return dict(mean=float("nan"), se=float("nan"), lo=float("nan"), hi=float("nan"), n=0, groups=0)
    w = np.ones(n) if w is None else np.asarray(w, dtype=np.float64)
    W = float(w.sum())
    m = float((w * d).sum() / W)
    u = np.unique(groups)
    G = len(u)
    if G < 2:
        return dict(mean=m, se=float("nan"), lo=float("nan"), hi=float("nan"), n=n, groups=G)
    r = w * (d - m)
    s = np.array([r[groups == x].sum() for x in u])
    se = float(math.sqrt(G / (G - 1) * float((s * s).sum())) / W)
    tc = lv.t_crit(G - 1)
    return dict(mean=m, se=se, lo=m - tc * se, hi=m + tc * se, n=n, groups=G)


def base_values(tb: dict) -> dict:
    """기준 값 (K,): run·shelter(가능할 때)·cover(가능할 때)·open, oracle(두뇌 길 셋), oracle4(OPEN 포함), 가짜 오라클 이득(무게 평균)."""
    real, fake, ok = tb["real"], tb["fake"], tb["ok"]
    K = len(real)
    ar = np.arange(K)
    v = dict(run=real[:, 0], shelter=real[ar, np.where(ok[:, 2], 2, 0)], cover=real[ar, np.where(ok[:, 1], 1, 0)], open=real[:, 3])
    v["oracle"] = brain_vals(real, ok).min(1) if K else np.zeros(0)
    v["oracle4"] = np.minimum(v["oracle"], real[:, 3]) if K else np.zeros(0)
    fb = np.where(ok[:, list(BRAIN)], fake[:, list(BRAIN)], np.inf).min(1) - real[:, 0] if K else np.zeros(0)
    return dict(v=v, fake_gain=wmean(fb, tb["wt"]) if K else float("nan"))


def score(choice: np.ndarray, tb: dict, bv: dict) -> dict:
    """고른 길 (K,) → (무게) 평균 쫓긴 시간(초), 늘 RUN·늘 SHELTER 대비 차이(시드 묶음 CI), 오라클 간격 몫(늘 SHELTER → 잡음 뺀 오라클), 정확도, 고른 길 몫."""
    real, w = tb["real"], tb["wt"]
    K = len(real)
    v = real[np.arange(K), choice]
    vs = bv["v"]
    sh_m, or_m = wmean(vs["shelter"], w), wmean(vs["oracle"], w)
    orc_c = or_m - bv["fake_gain"]
    gap = sh_m - orc_c
    m = wmean(v, w)
    return dict(mean=m, vs_run=cluster_ci(v - vs["run"], tb["seed"], w), vs_shelter=cluster_ci(v - vs["shelter"], tb["seed"], w),
                gap=gap, gap_frac=(sh_m - m) / gap if gap > 0 else float("nan"),
                gap_frac_raw=(sh_m - m) / (sh_m - or_m) if sh_m > or_m else float("nan"),
                acc=wmean(v <= vs["oracle"] + TIE_EPS, w), share=[wmean(choice == r, w) for r in BRAIN])


def perm_importance(tb: dict, S: np.ndarray, entry: tuple, names: list, repeats: int | None = None) -> list:
    """순열 중요도 (값 잣대, 부분 집합 S 안): 단서 하나를 겹마다 S 의 확인 행 안에서 섞어 다시 고른 길의 (무게) 평균 쫓긴 시간 − 원래 평균
    (초, + = 그 단서가 쓸모 있음). 반복 평균·sd."""
    choice, fns, cols = entry
    X = tb["X"][:, cols]
    real, ok, w = tb["real"], tb["ok"], tb["wt"]
    idx = np.flatnonzero(S)
    base = wmean(real[idx, choice[idx]], w[idx])
    repeats = PERM_REPEATS if repeats is None else int(repeats)
    out = []
    for jc in range(X.shape[1]):
        d = []
        for rp in range(repeats):
            g = np.random.default_rng([CUES_TAG, 7, jc, rp])
            ch = choice.copy()
            for te, f in fns:
                ts = te[S[te]]
                if not len(ts):
                    continue
                Z = X[ts].copy()
                Z[:, jc] = g.permutation(Z[:, jc])
                ch[ts] = f(Z, ok[ts])
            d.append(wmean(real[idx, ch[idx]], w[idx]) - base)
        out.append(dict(cue=names[jc], kind=CUE_KIND.get(names[jc], CUE_KIND["region"] if names[jc].startswith("region_") else "?"),
                        in_obs=names[jc].startswith("obs_"), imp=float(np.mean(d)), sd=float(np.std(d))))
    return sorted(out, key=lambda r: -r["imp"])


def feature_cols(names: list, fs: str) -> np.ndarray:
    if fs == "perc":
        return np.array([j for j, n in enumerate(names) if n in PERCEIVABLE], dtype=np.int64)
    return np.arange(len(names), dtype=np.int64)


def eval_subset(tb: dict, S: np.ndarray, choices: dict, best: dict | None = None, importance: bool = False) -> dict:
    """한 부분 집합 S 에서 같은 확인 몫 고르기를 잰다: 기준 값, 모델마다(단서 묶음 둘) 점수, 가장 좋은 모델(best 를 주지 않으면 이 집합의 평균으로 고름),
    순열 중요도(importance), 지역별 평균. 값은 모두 무게(1/p) 평균."""
    S = np.asarray(S, dtype=bool)
    K = int(S.sum())
    out = dict(n=K, seeds=int(len(np.unique(tb["seed"][S]))) if K else 0)
    if not K:
        return dict(out, base=None, bases={}, models={}, best=dict(best or {}), importance={}, region={})
    sub = subset(tb, S)
    w = sub["wt"]
    bv = base_values(sub)
    vs = bv["v"]
    y = labels(sub["real"], sub["ok"])
    out["label_share"] = [wmean(y == r, w) for r in BRAIN]
    out["feasible"] = dict(cover=wmean(sub["ok"][:, 1], w), shelter=wmean(sub["ok"][:, 2], w))
    out["base"] = dict({k: wmean(x, w) for k, x in vs.items()}, fake_gain=bv["fake_gain"], oracle_corr=wmean(vs["oracle"], w) - bv["fake_gain"])
    out["bases"] = {b: score(base_choice(b, sub["ok"]), sub, bv) for b in BASES}
    out["bases"]["oracle"] = score(y, sub, bv)
    out["models"] = {}
    for (fs, mname), (ch, _, _) in choices.items():
        out["models"].setdefault(fs, {})[mname] = score(ch[S], sub, bv)
    if best is None:
        best = {fs: min(ms, key=lambda k: (ms[k]["mean"], MODELS.index(k))) for fs, ms in out["models"].items() if ms}
    out["best"] = dict(best)
    out["importance"] = {}
    if importance:
        for fs, bm in best.items():
            ent = choices[(fs, bm)]
            out["importance"][fs] = perm_importance(tb, S, ent, [tb["names"][j] for j in ent[2]])
    bp = best.get("perc")
    out["region"] = {}
    for g in sorted(set(sub["region"].tolist())):
        m = sub["region"] == g
        row = dict(n=int(m.sum()), run=wmean(vs["run"][m], w[m]), shelter=wmean(vs["shelter"][m], w[m]), oracle=wmean(vs["oracle"][m], w[m]))
        if bp is not None and ("perc", bp) in choices:
            ch = choices[("perc", bp)][0][S]
            row["best"] = wmean(sub["real"][np.flatnonzero(m), ch[m]], w[m])
        out["region"][g] = row
    return out


HEAD_KEYS = ("cond", "world_set", "quiet_end", "streams", "max_steps", "main_steps", "p_chased", "p_unchased", "smoke", "model_default", "snapshot")


def analyze_cond(raw: dict) -> dict:
    """조건 하나(raw 또는 중간 jsonl): 개수·층·점검·머리(판단 조건 대조용), 끝난 조건만 모델 점수(부분 집합 넷 — SUBSETS). 중간은 개수만(눈가림)."""
    cap = int(raw["max_steps"])
    ws = raw["worlds"]
    rows = onset_rows(ws)
    regions = sorted({w["region"] for w in ws})
    tb = table(rows, cap, regions)
    ch, nt = tb["chased"], tb["nt"]
    base = (tb["seed"] >= SEEDS[0]) & (tb["seed"] <= SEEDS[1])
    head = raw.get("head") or {}
    out = dict(world_set=raw.get("world_set", head.get("world_set", {})), head={k: head.get(k) for k in HEAD_KEYS},
               seed_list=sorted({int(w["seed"]) for w in ws}), worlds=len(ws), regions=len(regions), sampled=len(rows),
               chased=int(ch.sum()), unchased=int((~ch).sum()), nontied=int((ch & nt).sum()),
               nontied_frac=float((ch & nt).sum() / ch.sum()) if ch.any() else float("nan"), nontied_unchased=int((~ch & nt).sum()),
               base_nontied=int((ch & nt & base).sum()), check_bad=int((~tb["check"]).sum()),
               onsets_seen=int(sum(w.get("onsets_seen", 0) for w in ws)), chased_seen=int(sum(w.get("chased_seen", 0) for w in ws)),
               main_steps=int(sum(w["main_steps"] for w in ws)), roll_steps=int(sum(w["roll_steps"] for w in ws)),
               roll_chased=float(tb["roll"][ch].sum()), roll_unchased=float(tb["roll"][~ch].sum()),
               world_wall_s=float(sum(w["wall_s"] for w in ws)), partial=bool(raw.get("partial")), code=raw.get("code"),
               code_changed=raw.get("code_changed"))
    if out["partial"] or not len(rows):
        out["subsets"] = None
        return out
    out["x_from_p"] = x_linear_in_p(tb["X"], tb["names"])
    fl, choices = fit_all(tb)
    out["folds"] = len(fl)
    masks = dict(nontied=ch & nt, all=np.ones(len(rows), dtype=bool), chased=ch, unchased=~ch)
    subs = {"nontied": eval_subset(tb, masks["nontied"], choices, importance=True)}
    best = subs["nontied"]["best"]
    for nm in SUBSETS[1:]:
        subs[nm] = eval_subset(tb, masks[nm], choices, best=best)
    out["subsets"] = subs
    return out


def run_mismatch(c: dict) -> list:
    """on 조건이 미리 정한 측정 조건(prereg_head·시드·연장 규칙·세계 수)과 어긋난 것 (빈 목록 = 맞음)."""
    h = c.get("head") or {}
    bad = []
    for k, v in prereg_head().items():
        a, b = json.dumps(lv.jsonable(h.get(k)), sort_keys=True), json.dumps(lv.jsonable(v), sort_keys=True)
        if a != b:
            bad.append(f"{k} {a} ≠ {b}")
    got = set(int(s) for s in c.get("seed_list") or [])
    base = set(range(SEEDS[0], SEEDS[1] + 1))
    ext = base | set(range(EXT_SEEDS[0], EXT_SEEDS[1] + 1))
    if got == ext:
        if c.get("base_nontied", 0) >= MIN_N:
            bad.append(f"연장은 판단 시드의 쫓긴·비기지 않은 시작 < {MIN_N} 일 때만 (판단 시드만으로 {c.get('base_nontied')})")
    elif got != base:
        bad.append(f"시드 {min(got) if got else '—'}~{max(got) if got else '—'} ({len(got)} 개) ≠ 판단 시드 {SEEDS[0]}~{SEEDS[1]}"
                   f" (또는 연장 {SEEDS[0]}~{EXT_SEEDS[1]})")
    if c.get("regions") != REGIONS or c.get("worlds") != len(got) * REGIONS:
        bad.append(f"세계 {c.get('worlds')} ≠ 시드 {len(got)} × 지역 {REGIONS}")
    return bad


def decide(conds: dict) -> dict:
    """미리 적은 판단 규칙 (모듈 docstring·CUES_RULE.md): on · 미리 정한 측정 조건 · 쫓긴·비기지 않은 시작(1~3) + 모든 시작(4) · 알 수 있는 단서만."""
    c = conds.get("on")
    if c is None:
        return dict(verdict=None, why="숲 시야 켬(on) 조건 결과가 없다")
    if c["partial"]:
        return dict(verdict=None, why="on 측정이 끝나지 않았다 (중간 보고 — 개수만)")
    if c.get("code") is None:
        return dict(verdict=None, why="on 측정의 셈 길 지문이 없다 (측정 중 코드가 바뀜 — 새 폴더에서 다시)")
    if (c.get("head") or {}).get("smoke"):
        return dict(verdict=None, why="연기 시험 — 판단하지 않는다 (탐색 시드·작은 표본)")
    bad = run_mismatch(c)
    if bad:
        return dict(verdict=None, why="미리 정한 측정 조건과 다르다 — " + "; ".join(bad))
    s = c["subsets"]["nontied"]
    if s["n"] < MIN_N or s["seeds"] < MIN_SEEDS:
        return dict(verdict=None, why=f"표본 부족 — 쫓긴·비기지 않은 시작 {s['n']} (≥ {MIN_N})·시드 {s['seeds']} (≥ {MIN_SEEDS})")
    bp = s["best"].get("perc")
    if bp is None:
        return dict(verdict=None, why="모델 점수가 없다")
    m = s["models"]["perc"][bp]
    ma = c["subsets"]["all"]["models"]["perc"][bp]
    gain = -m["vs_shelter"]["mean"]
    c1, c2, c3 = gain >= PROCEED_S, (m["gap_frac"] == m["gap_frac"] and m["gap_frac"] >= PROCEED_GAP), m["vs_shelter"]["hi"] < 0.0
    c4 = ma["vs_shelter"]["hi"] < 0.0
    yn = {True: "예", False: "아니오"}
    why = (f"가장 좋은 모델 {bp}: 쫓긴·비기지 않은 시작에서 늘 SHELTER 대비 {gain:+.2f} 초 (≥ {PROCEED_S} — {yn[bool(c1)]}), 오라클 간격 "
           f"{m['gap']:.2f} 초 가운데 {m['gap_frac'] * 100:.0f}% (≥ {PROCEED_GAP * 100:.0f}% — {yn[bool(c2)]}), 95% CI [{m['vs_shelter']['lo']:+.2f}, "
           f"{m['vs_shelter']['hi']:+.2f}] (위 끝 < 0 — {yn[bool(c3)]}); 모든 시작(무게) 모델 − 늘 SHELTER {ma['vs_shelter']['mean']:+.3f} 초 95% CI "
           f"[{ma['vs_shelter']['lo']:+.3f}, {ma['vs_shelter']['hi']:+.3f}] (위 끝 < 0 — {yn[bool(c4)]})")
    top = [r for r in s["importance"].get("perc", []) if r["imp"] > 0][:8]
    return dict(verdict="proceed" if (c1 and c2 and c3 and c4) else "two_route", why=why, model=bp, checks=[bool(c1), bool(c2), bool(c3), bool(c4)],
                top_cues=[dict(cue=r["cue"], imp=r["imp"], in_obs=r["in_obs"]) for r in top])


# --------------------------------------------------------------------- #
# 시간 어림
# --------------------------------------------------------------------- #

def wilson_lo(k: int, n: int, z: float = PLAN_Z) -> float:
    """몫 k/n 의 Wilson 아래 끝 (한쪽, z)."""
    if n <= 0:
        return float("nan")
    p, z2 = k / n, z * z
    return (p + z2 / (2 * n) - z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / (1 + z2 / n)


def plan(conds: dict, sec_ws: dict, workers: int = 14, n_seeds: int = SEEDS[1] - SEEDS[0] + 1, regions: int = REGIONS,
         steps: int = MAIN_STEPS) -> dict | None:
    """본 측정 어림 (끝난 on 의 개수로): 쫓긴 시작·쫓기지 않은 시작이 세계-스텝마다 나오는 비율, 쫓긴 시작의 비기지 않은 몫(점 f = k/n, 아래 끝 lo =
    Wilson 한쪽 PLAN_Z) → 권하는 확률 p_chased = max(TARGET_NONTIED / (f · 기대 쫓긴 시작), MIN_N · PLAN_FLOOR / (lo · 기대 쫓긴 시작))(0.01 올림 — 점
    추정으로 목표, 아래 끝에서도 표본 조건의 1.5 배), p_unchased = TARGET_UNCHASED / 기대 쫓기지 않은 시작(0.001 올림). 시간은 미리 정한 확률
    (P_CHASED·P_UNCHASED, off 는 × COMPARE_SCALE)로 조건마다: 세계 × (판 길이 + 판 길이 × Σ층 확률·비율·시작당 롤아웃 스텝) × 세계-스텝당 초
    (max(잰 값, REF_SEC_14W)) ÷ 워커."""
    on = conds.get("on")
    if on is None or on.get("partial") or not on["chased"] or not on["nontied"] or not on["main_steps"]:
        return None
    nw = n_seeds * regions
    f = on["nontied"] / on["chased"]
    lo = wilson_lo(on["nontied"], on["chased"])
    rate_ch = on["chased_seen"] / on["main_steps"]
    rate_un = (on["onsets_seen"] - on["chased_seen"]) / on["main_steps"]
    exp_ch, exp_un = rate_ch * steps * nw, rate_un * steps * nw
    p_ch_point = min(1.0, TARGET_NONTIED / (f * exp_ch))
    p_ch_floor = min(1.0, MIN_N * PLAN_FLOOR / (lo * exp_ch))
    p_ch = min(1.0, math.ceil(max(p_ch_point, p_ch_floor) * 100 - 1e-9) / 100)
    p_un = min(1.0, math.ceil(TARGET_UNCHASED / exp_un * 1000 - 1e-9) / 1000) if exp_un > 0 else 0.0
    out = dict(target=TARGET_NONTIED, target_unchased=TARGET_UNCHASED, workers=workers, worlds=nw, nontied_frac=f, nontied_lo=lo, n_frac=int(on["chased"]),
               chased_per_world=rate_ch * steps, unchased_per_world=rate_un * steps, p_chased=p_ch, p_chased_point=p_ch_point, p_chased_floor=p_ch_floor, p_unchased=p_un,
               p_prereg=[P_CHASED, P_UNCHASED], same_as_prereg=bool(p_ch == P_CHASED and p_un == P_UNCHASED),
               expected_nontied=int(round(P_CHASED * exp_ch * f)), expected_nontied_lo=int(round(P_CHASED * exp_ch * lo)),
               expected_unchased=int(round(P_UNCHASED * exp_un)), conds={})
    total = 0.0
    for name, c in conds.items():
        if c.get("partial") or not c["main_steps"] or not c["sampled"]:
            continue
        rc = c["chased_seen"] / c["main_steps"]
        ru = (c["onsets_seen"] - c["chased_seen"]) / c["main_steps"]
        r_ch = c["roll_chased"] / c["chased"] if c["chased"] else c["roll_unchased"] / max(c["unchased"], 1)
        r_un = c["roll_unchased"] / c["unchased"] if c["unchased"] else r_ch
        spws = max(float(sec_ws.get(name) or 0.0), REF_SEC_14W)
        sc = 1.0 if name == "on" else COMPARE_SCALE
        pc, pu = min(1.0, P_CHASED * sc), min(1.0, P_UNCHASED * sc)
        ws = nw * steps * (1.0 + pc * rc * r_ch + pu * ru * r_un)
        t = ws * spws / workers
        total += t
        out["conds"][name] = dict(roll_per_chased=r_ch, roll_per_unchased=r_un, chased_per_world=rc * steps, unchased_per_world=ru * steps, p=[pc, pu],
                                  sec_per_world_step=spws, world_steps=ws, wall_s=t, wall_chased_s=nw * steps * pc * rc * r_ch * spws / workers,
                                  wall_unchased_s=nw * steps * pu * ru * r_un * spws / workers)
    out["wall_s"] = total
    return out


# --------------------------------------------------------------------- #
# 보고
# --------------------------------------------------------------------- #

def _ci(x: dict, nd: int = 2) -> str:
    if x["n"] == 0 or x["mean"] != x["mean"]:
        return "—"
    if x["se"] != x["se"]:
        return f"{x['mean']:+.{nd}f}"
    return f"{x['mean']:+.{nd}f} [{x['lo']:+.{nd}f}, {x['hi']:+.{nd}f}]"


def _pct(x) -> str:
    return "—" if x is None or x != x else f"{x * 100:.0f}%"


MODEL_KO = dict(run="늘 RUN", shelter="늘 SHELTER", cover="늘 COVER", oracle="오라클(잡음 그대로)", tree3="나무 깊이 3", tree6="나무 깊이 6",
                hgb="부스팅 분류", logreg="다항 로지스틱", regret="regret 직접(길마다 시간 예측)")
SUB_KO = dict(nontied="쫓기며 시작·비기지 않음 (판단 1~3 표본)", all="모든 도주 시작 — 쫓김·안 쫓김을 무게 1/p 로 (판단 4, 배포 모집단)",
              chased="모든 쫓긴 시작 (보고만)", unchased="쫓기지 않은 시작 (보고만)")
COND_KO = dict(on="숲 시야 켬 (판단 조건)", off="숲 시야 끔 (견줌)")


def fmt_subset(s: dict, title: str, nd: int = 2) -> list:
    L = [f"### {title}", ""]
    if not s["n"] or s.get("base") is None:
        return L + ["- 표본 없음", ""]
    b = s["base"]
    ls = s["label_share"]
    L += [f"- 시작 {s['n']} (시드 {s['seeds']}), 정답 몫 RUN·COVER·SHELTER {ls[0] * 100:.0f}·{ls[1] * 100:.0f}·{ls[2] * 100:.0f}% (비긴 시작은 RUN), "
          f"가능 몫 COVER {s['feasible']['cover'] * 100:.0f}%·SHELTER {s['feasible']['shelter'] * 100:.0f}%",
          f"- 평균 쫓긴 시간(초): 늘 RUN {b['run']:.{nd}f} · 늘 SHELTER {b['shelter']:.{nd}f} · 늘 COVER {b['cover']:.{nd}f} · 늘 OPEN {b['open']:.{nd}f} · "
          f"오라클 {b['oracle']:.{nd}f} (잡음 뺀 값 **{b['oracle_corr']:.{nd}f}**, 가짜 이득 {b['fake_gain']:+.{nd}f}) · OPEN 까지 넣은 오라클 {b['oracle4']:.{nd}f}",
          "", "| 단서 | 모델 | 평균 쫓긴 시간 초 | − 늘 RUN [95% CI] | − 늘 SHELTER [95% CI] | 오라클 간격 잡은 몫 (잡음 그대로 간격) | 정확도 | 고른 몫 RUN·COVER·SHELTER |",
          "|---|---|---|---|---|---|---|---|"]

    def row(fs, name, m, star=False):
        sh = m["share"]
        return (f"| {fs} | {'**' if star else ''}{MODEL_KO.get(name, name)}{'**' if star else ''} | {m['mean']:.{nd}f} | {_ci(m['vs_run'], nd)} | "
                f"{_ci(m['vs_shelter'], nd)} | {_pct(m['gap_frac'])} ({_pct(m['gap_frac_raw'])}) | {m['acc'] * 100:.0f}% | "
                f"{sh[0] * 100:.0f}·{sh[1] * 100:.0f}·{sh[2] * 100:.0f}% |")

    for name, m in s["bases"].items():
        L.append(row("기준", name, m))
    for fs, ms in s["models"].items():
        for name, m in ms.items():
            L.append(row({"perc": "알 수 있음", "all": "+ 특권"}[fs], name, m, name == s["best"].get(fs)))
    if s.get("region"):
        L += ["", "| 지역 | 시작 | 늘 RUN | 늘 SHELTER | 오라클 | 가장 좋은 모델 (알 수 있음) |", "|---|---|---|---|---|---|"]
        for g, r in s["region"].items():
            L.append(f"| {g} | {r['n']} | {r['run']:.{nd}f} | {r['shelter']:.{nd}f} | {r['oracle']:.{nd}f} | {r.get('best', float('nan')):.{nd}f} |")
    for fs, imp in s.get("importance", {}).items():
        L += ["", f"순열 중요도 — {'알 수 있는 단서' if fs == 'perc' else '모든 단서'}, 가장 좋은 모델 {MODEL_KO.get(s['best'][fs], s['best'][fs])} "
              f"(이 집합 안에서 섞으면 늘어나는 평균 쫓긴 시간 초, 위 10):", "", "| 단서 | 종류 | 관측 21 에 있음 | 중요도 초 (sd) |", "|---|---|---|---|"]
        for r in imp[:10]:
            L.append(f"| {r['cue']} | {'알 수 있음' if r['kind'] == 'perceivable' else '특권'} | {'예' if r['in_obs'] else ''} | {r['imp']:+.3f} ({r['sd']:.3f}) |")
    return L + [""]


def fmt(an: dict, meta: dict) -> str:
    L = [f"# 도망길 단서 측정 — 사슴이 알 수 있는 단서로 길을 가를 수 있나{' (연기 시험)' if meta.get('smoke') else ''}", "",
         "- 판단 규칙: results/v3/route/CUES_RULE.md (본 측정 전에 적음). 값 = 고른 길의 쫓긴 시간(초, 흐름 평균, 잡힘·굶음·안 끝남 = 40 초), "
         "시드로 묶은 교차 검증 확인 몫. 시작은 베르누이로 솎았다(쫓김 p_chased·아니면 p_unchased — 무게 1/p). CI = 같은 시작끼리 차이를 시드로 묶은 "
         "95% 신뢰구간 (음수 = 짧아짐). 모델은 모든 뽑은 시작에 한 번 맞춘다(분류기는 비기지 않은 시작만) — 부분 집합마다 같은 고르기",
         f"- 측정: {json.dumps(meta.get('runs', {}), ensure_ascii=False)}", ""]
    for name, c in an["conds"].items():
        L += [f"## {COND_KO.get(name, name)} — 세계 덮기 {rr.world_set_text(c['world_set'])}{' — **중간 (측정 중)**' if c['partial'] else ''}", "",
              f"- 세계 {c['worlds']} (시드 {len(c['seed_list'])}), 고르기 확률 쫓김 {c['head'].get('p_chased')} · 안 쫓김 {c['head'].get('p_unchased')}, "
              f"본 도주 시작 {c['onsets_seen']} 가운데 쫓기며 시작 {c['chased_seen']} "
              f"({_pct(c['chased_seen'] / c['onsets_seen'] if c['onsets_seen'] else float('nan'))})",
              f"- 뽑은 시작 {c['sampled']}: 쫓김 {c['chased']} (비기지 않음 {c['nontied']} = {_pct(c['nontied_frac'])}; 판단 시드만 {c['base_nontied']}) · "
              f"안 쫓김 {c['unchased']} (비기지 않음 {c['nontied_unchased']}), 기하 점검 어긋남 {c['check_bad']}, 셈 길 지문 {rr.code_text(c['code'])}"
              + (" (측정 중 바뀜)" if c.get("code_changed") else ""), ""]
        if c.get("subsets") is None:
            L += ["- 결과 표는 측정이 끝난 뒤에 낸다 (눈가림 — 판단 시드의 결과를 도중에 보지 않는다). 연장 여부는 위 '판단 시드만' 개수로만 정한다.", ""]
            continue
        xp = c.get("x_from_p") or {}
        L += ["- P 가 X 를 새나 (X 칸이 P 칸의 정확한 일차식): "
              + ("가를 수 없음 (행 ≤ 계수)" if xp.get("exact") is None else ("없음" if not xp["exact"] else "**" + ", ".join(xp["exact"]) + "**"))
              + f" (행 {xp.get('rows')}, P 계수 {xp.get('rank')})", ""]
        for sub in SUBSETS:
            L += fmt_subset(c["subsets"][sub], SUB_KO[sub], 3 if sub in ("all", "unchased") else 2)
    d = an["decision"]
    v = {"proceed": "진행 — 길 고르기 계약 (세 길 + 새 관측)", "two_route": "두 길(RUN + SHELTER) 안을 권함", None: "판단 없음"}[d["verdict"]]
    L += ["## 판단 (on · 미리 정한 조건 · 알 수 있는 단서만 — 쫓긴·비기지 않은 시작 1~3, 모든 시작 4)", "", f"**{v}** — {d['why']}", ""]
    if d.get("top_cues"):
        L += ["새 관측 칸 후보 (순열 중요도 위, + 인 것):", ""] + [f"- {r['cue']} ({r['imp']:+.3f} 초){' — 이미 관측 21 에 있음' if r['in_obs'] else ''}"
                                                              for r in d["top_cues"]] + [""]
    p = an.get("plan")
    if p:
        L += ["## 본 측정 어림 (이 결과로 잼)", "",
              f"- 세계 {p['worlds']} (시드 {SEEDS[0]}~{SEEDS[1]} × 지역 {REGIONS}), 세계마다 쫓긴 시작 약 {p['chased_per_world']:.0f}·쫓기지 않은 시작 약 "
              f"{p['unchased_per_world']:.0f} ({MAIN_STEPS} 스텝)",
              f"- 쫓긴 시작의 비기지 않은 몫 {p['nontied_frac'] * 100:.0f}% (쫓긴 시작 {p['n_frac']} 개로 잼 — 한쪽 90 % 아래 끝 {p['nontied_lo'] * 100:.0f}%) → "
              f"목표 {p['target']}(점 추정) 에 {p['p_chased_point']:.3f}, 아래 끝에서도 {MIN_N} × {PLAN_FLOOR} 에 {p['p_chased_floor']:.3f} → 권하는 확률 쫓김 "
              f"**{p['p_chased']}** · 안 쫓김 목표 {p['target_unchased']} 에 **{p['p_unchased']}**",
              f"- 미리 정한 확률(CUES_RULE.md) {p['p_prereg'][0]} · {p['p_prereg'][1]}"
              + ("" if p["same_as_prereg"] else " — **권하는 값과 다르다 (본 측정 전이면 CUES_RULE.md·P_CHASED·P_UNCHASED 를 함께 고친다)**")
              + f": 기대 쫓긴·비기지 않은 시작 {p['expected_nontied']} (아래 끝이면 {p['expected_nontied_lo']}), 쫓기지 않은 시작 {p['expected_unchased']}, 워커 {p['workers']}"]
        for name, c in p["conds"].items():
            L.append(f"- {name} (확률 {c['p'][0]:g}·{c['p'][1]:g}): 시작당 롤아웃 쫓김 {c['roll_per_chased']:.0f}·안 쫓김 {c['roll_per_unchased']:.0f} 세계-스텝, 세계-스텝당 "
                     f"{c['sec_per_world_step'] * 1000:.1f} ms → 약 {c['wall_s'] / 3600:.1f} 시간 (판 {MAIN_STEPS} 스텝 + 쫓김 {c['wall_chased_s'] / 3600:.1f} + "
                     f"안 쫓김 {c['wall_unchased_s'] / 3600:.1f})")
        L += [f"- 합계 약 **{p['wall_s'] / 3600:.1f} 시간** (연기 시험 표본이 작아 ±50 % — 도중에 report 로 개수를 본다)", "",
              f"    python results/v3/route/cues.py run --out results/v3/route/runs/cues1 --workers {p['workers']}", ""]
    return "\n".join(L)


# --------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------- #

def _jsonl(path: Path) -> tuple[dict | None, list]:
    """worlds_<조건>.jsonl → (머리, 세계 목록). 덜 쓰인 끝 줄은 버린다."""
    if not path.exists():
        return None, []
    head, worlds = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if "head" in d:
            head = d["head"]
        else:
            worlds.append(d)
    return head, worlds


def _same_head(a: dict, b: dict) -> bool:
    """머리끼리 같은 측정인가 — 시드 범위는 빼고 견준다(세계는 (시드, 지역)으로 따로 적으니 시드를 늘려 이어 돌려도 섞이지 않는다)."""
    def key(h):
        return json.dumps(lv.jsonable({k: v for k, v in (h or {}).items() if k != "seeds"}), sort_keys=True)
    return a is not None and b is not None and key(a) == key(b)


def cond_sets(a) -> dict:
    on = rr.parse_world_set(a.world_set or list(FOLIAGE_ON))
    off = rr.parse_world_set(a.compare_set)
    return dict(on=on, off=off)


def cmd_run(a) -> int:
    from env_v2 import rollout as ro

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    info = rr.prepare_info(out, Path(a.snapshot))
    model = Path(a.model) if a.model else Path(info["start"]["zip"])
    steps, W, ms, streams = int(a.steps), int(a.workers), int(a.max_steps), int(a.streams)
    p_ch, p_un, scale = float(a.p_chased), float(a.p_unchased), float(a.compare_scale)
    if a.smoke:
        seeds = rr.seeds_of(lv.seed_range(a.seeds) if a.seeds else SMOKE["seeds"])[: SMOKE["seeds"][1] - SMOKE["seeds"][0] + 1]
        steps, W, ms, p_ch, p_un, scale = SMOKE["steps"], min(W, SMOKE["workers"]), SMOKE["max_steps"], SMOKE["p_chased"], SMOKE["p_unchased"], 1.0
    else:
        seeds = rr.seeds_of(lv.seed_range(a.seeds) if a.seeds else SEEDS)
    for x in (p_ch, p_un):
        if not 0.0 < x <= 1.0:
            raise SystemExit(f"고르기 확률은 (0, 1] 이어야 한다: {x}")
    conds = [c for c in a.conds.split(",") if c]
    for c in conds:
        if c not in CONDS:
            raise SystemExit(f"--conds {c} 는 {', '.join(CONDS)} 가운데 하나여야 한다")
    sets = cond_sets(a)
    now = code_tag()
    for cond in [c for c in CONDS if c in conds]:                 # 늘 on → off
        pc, pu = (p_ch, p_un) if cond == "on" else (min(1.0, p_ch * scale), min(1.0, p_un * scale))
        head = dict(cond=cond, world_set=lv.jsonable(sets[cond]), quiet_end=int(a.quiet_end), seeds=[seeds[0], seeds[-1]], p_chased=pc, p_unchased=pu,
                    streams=streams, max_steps=ms, main_steps=steps, model=lv.path_text(model), model_default=a.model is None,
                    snapshot=Path(a.snapshot).name, smoke=bool(a.smoke), code=now)
        jp, rp = out / f"worlds_{cond}.jsonl", out / f"raw_{cond}.json"
        if a.force:
            jp.unlink(missing_ok=True)
            rp.unlink(missing_ok=True)
        need = {(int(sd), name) for sd in seeds for name in info["regions"]}
        if rp.exists():
            old = json.loads(rp.read_text(encoding="utf-8"))
            if not _same_head(old.get("head"), head):
                raise SystemExit(f"{rp} 의 머리가 지금과 다르다 (덮기·확률·지문 등) — 같은 명령으로, 새 폴더, 또는 --force")
            if need <= {(int(w["seed"]), w["region"]) for w in old["worlds"]}:
                print(f"  {cond}: {rp.name} 에 고른 세계가 다 있다 — 건너뜀", flush=True)
                continue
            if not jp.exists():                                  # 시드를 늘려 이어 돌림: jsonl 을 raw 로 되살린다
                lines = [json.dumps(lv.jsonable(x), ensure_ascii=False) for x in [{"head": old["head"]}] + old["worlds"]]
                jp.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        h0, done = _jsonl(jp)
        if h0 is not None and not _same_head(h0, head):
            raise SystemExit(f"{jp} 의 머리가 지금과 다르다 — 섞지 않는다 (지금 {rr.code_text(now)}, 덮기 {rr.world_set_text(sets[cond])}; "
                             f"있는 것 {rr.code_text(h0.get('code'))}, 덮기 {rr.world_set_text(h0.get('world_set') or {})}) — 같은 명령으로, 새 폴더, 또는 --force")
        # 머리 + 다 쓴 세계만 다시 적는다 (끊긴 실행의 덜 쓰인 끝 줄을 버린다 — 그 뒤에 이어 쓴 줄이 붙지 않게)
        done = list({(int(w["seed"]), w["region"]): w for w in reversed(done)}.values())
        lines = [json.dumps(lv.jsonable(x), ensure_ascii=False) for x in [{"head": h0 if h0 is not None else head}] + done]
        lv.atomic_write_text(jp, "\n".join(lines) + "\n")
        have = {(int(w["seed"]), w["region"]) for w in done}
        sw = dict(lv.NOSAT["sets"], **{"wild_flight.route_fixed": "run"})
        if int(a.quiet_end) > 0:
            sw["wild_flight.quiet_end"] = int(a.quiet_end)
        jobs = []
        for j in ad.make_jobs(info, model, seeds, steps, False, dict(name=f"cues_{cond}", sets=sw)):
            rr.apply_world_set(j["cfg"], sets[cond])
            j.update(quiet_end=int(a.quiet_end), region_index=int(info["regions"][j["region"]]["region_index"]), p_chased=pc, p_unchased=pu,
                     streams=streams, max_steps=ms)
            if (int(j["seed"]), j["region"]) not in have:
                jobs.append(j)
        print(f"도망길 단서 {cond} → {out}: 세계 {len(jobs)} 남음 / {len(seeds) * len(info['regions'])} (시드 {seeds[0]}~{seeds[-1]}), 고르기 확률 쫓김 {pc}·"
              f"안 쫓김 {pu}, 흐름 {streams}, 롤아웃 최대 {ms}, 판 {steps}, 워커 {W}, 덮기 {rr.world_set_text(sets[cond])}{', 연기 시험' if a.smoke else ''}",
              flush=True)
        t0 = time.perf_counter()
        with jp.open("a", encoding="utf-8", newline="\n") as fh:
            def put(res):
                fh.write(json.dumps(lv.jsonable(res), ensure_ascii=False) + "\n")
                fh.flush()
            ex = ro.make_executor(min(W, len(jobs))) if jobs else None
            if ex is None:
                for k, j in enumerate(jobs, 1):
                    put(_cues_world(j))
            else:
                from concurrent.futures import as_completed

                with ex:
                    futs = [ex.submit(_cues_world, j) for j in jobs]
                    for k, f in enumerate(as_completed(futs), 1):
                        put(f.result())
                        if k % 10 == 0 or k == len(futs):
                            print(f"  {cond} 세계 {k}/{len(futs)} ({time.perf_counter() - t0:.0f} 초)", flush=True)
        wall = time.perf_counter() - t0
        _, got = _jsonl(jp)
        worlds = list({(int(w["seed"]), w["region"]): w for w in reversed(got)}.values())     # 같은 세계가 두 번이면 먼저 쓴 것
        worlds.sort(key=lambda w: (w["seed"], w["region"]))
        ws = sum(w["main_steps"] + w["roll_steps"] for w in worlds)
        raw = dict(head=head, made=datetime.now().isoformat(), cond=cond, world_set=head["world_set"],
                   seeds=[min(w["seed"] for w in worlds), max(w["seed"] for w in worlds)] if worlds else head["seeds"], p_chased=pc, p_unchased=pu,
                   streams=streams, max_steps=ms, main_steps=steps, workers=W, smoke=bool(a.smoke), wall_s=round(wall, 1), world_steps=ws,
                   sec_per_world_step=float(sum(w["wall_s"] for w in worlds)) / max(ws, 1), code=now, worlds=worlds)
        end = code_tag()
        if not rr.same_code(end, now):
            raw.update(code=None, code_changed=dict(start=now, end=end))
        lv.atomic_write_json(rp, lv.jsonable(raw), indent=None)
        print(f"  {cond}: {wall:.0f} 초, 세계-스텝 {ws} → {rp.name}", flush=True)
        if raw["code"] is None:
            raise SystemExit(f"{cond} 측정 중 셈 길이 바뀌었다 ({rr.code_text(now)} → {rr.code_text(end)}) — 지문 없이 적고 멈춘다 (새 폴더에서 다시)")
    return cmd_report(a)


def load_conds(out: Path) -> tuple[dict, dict]:
    """조건마다 raw_<조건>.json(끝남) 또는 worlds_<조건>.jsonl(중간 — partial) → (raw 꼴 dict, 실행 메타)."""
    res, meta = {}, {}
    for cond in CONDS:
        rp, jp = out / f"raw_{cond}.json", out / f"worlds_{cond}.jsonl"
        raw = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else None
        head, worlds = _jsonl(jp)
        worlds = list({(int(w["seed"]), w["region"]): w for w in reversed(worlds)}.values())
        if raw is not None and len(worlds) <= len(raw["worlds"]):
            pass                                                 # 끝난 조건 (시드를 늘려 이어 돌리는 중이면 jsonl 이 더 많다 — 중간)
        elif head is not None and worlds:
            worlds.sort(key=lambda w: (w["seed"], w["region"]))
            raw = dict(head=head, world_set=head["world_set"], max_steps=head["max_steps"], smoke=head.get("smoke"), code=head.get("code"),
                       worlds=worlds, partial=True, sec_per_world_step=None)
        else:
            continue
        res[cond] = raw
        h = raw.get("head") or {}
        meta[cond] = dict(seeds=raw.get("seeds") or h.get("seeds"), p=[h.get("p_chased"), h.get("p_unchased")], worlds=len(raw["worlds"]),
                          wall_s=raw.get("wall_s"), workers=raw.get("workers"), partial=bool(raw.get("partial")),
                          sec_per_world_step=raw.get("sec_per_world_step"))
    return res, meta


def cmd_report(a) -> int:
    out = Path(a.out)
    raws, runs = load_conds(out)
    if not raws:
        raise SystemExit(f"{out} 에 raw_<조건>.json·worlds_<조건>.jsonl 이 없다 — run 부터")
    conds = {c: analyze_cond(r) for c, r in raws.items()}
    an = dict(conds=conds, decision=decide(conds))
    an["plan"] = plan(conds, {c: r.get("sec_per_world_step") for c, r in raws.items()})
    w = {c: (r.get("code") or {}).get("world") for c, r in raws.items()}
    meta = dict(runs=runs, smoke=any(bool(r.get("smoke") or (r.get("head") or {}).get("smoke")) for r in raws.values()),
                same_world_code=len(set(w.values())) <= 1)
    lv.atomic_write_json(out / "cues.json", lv.jsonable(dict(meta=meta, **an)))
    text = fmt(an, meta)
    if not meta["same_world_code"]:
        text += "\n**주의: 조건끼리 세계 셈 길 지문이 다르다 — 두 조건을 견주지 않는다.**\n"
    (out / "cues.md").write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    print(f"-> {out / 'cues.json'}, {out / 'cues.md'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="측정 (조건마다 worlds_<조건>.jsonl → raw_<조건>.json) 뒤 report")
    r.add_argument("--out", required=True)
    r.add_argument("--snapshot", default=str(rr.SNAPSHOT))
    r.add_argument("--model", default=None)
    r.add_argument("--seeds", default=None, help=f"기본 {SEEDS[0]}-{SEEDS[1]} (연장은 {SEEDS[0]}-{EXT_SEEDS[1]} 만 판단 — CUES_RULE.md)")
    r.add_argument("--p-chased", type=float, default=P_CHASED, help="쫓긴 시작을 고를 확률 (on — 미리 정한 값이 아니면 판단하지 않음)")
    r.add_argument("--p-unchased", type=float, default=P_UNCHASED, help="쫓기지 않은 시작을 고를 확률 (on)")
    r.add_argument("--compare-scale", type=float, default=COMPARE_SCALE, help=f"off 의 두 확률 배수 (보고만, 기본 {COMPARE_SCALE})")
    r.add_argument("--streams", type=int, default=STREAMS)
    r.add_argument("--max-steps", type=int, default=MAX_STEPS)
    r.add_argument("--steps", type=int, default=MAIN_STEPS, help="RUN 판 길이")
    r.add_argument("--quiet-end", type=int, default=QUIET_END)
    r.add_argument("--conds", default=",".join(CONDS))
    r.add_argument("--workers", type=int, default=14)
    r.add_argument("--smoke", action="store_true", help=f"탐색 시드 {SMOKE['seeds'][0]}~{SMOKE['seeds'][1]} · {SMOKE['steps']} 스텝 · 확률 "
                                                        f"{SMOKE['p_chased']}·{SMOKE['p_unchased']} · 워커 ≤ {SMOKE['workers']}")
    r.add_argument("--force", action="store_true", help="고른 조건의 결과를 지우고 처음부터")
    r.add_argument("--world-set", action="append", default=[], metavar="키=값",
                   help="on(판단) 조건의 세계 덮기 (여러 번 — 주면 기본 숲 시야 켬 r 3·block 2 대신, 판단하지 않음)")
    r.add_argument("--compare-set", action="append", default=[], metavar="키=값", help="off(견줌) 조건의 세계 덮기 (기본 없음 = 숲 시야 끔)")
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report", help="raw·jsonl → cues.json·cues.md (판단·본 측정 어림)")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
