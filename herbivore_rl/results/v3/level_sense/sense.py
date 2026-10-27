"""레벨 요소별 사슴 행동 민감도 하네스 (2026-10-27).

사용자 질문(10-27, 원문): "레벨이 달라졌을 때 사슴의 행동에 가장 큰 영향을 끼치는 요소가 뭐야? 나무가 막 자라났을때".
실제 게임 스냅숏 세계(실시간 고리 예비 측정 pilot_mask5 와 같은 바탕·같은 변환 경로)에 레벨 요소를 하나씩 바꿔, 같은 두뇌·같은 시드 짝으로 사슴 행동이
'얼마나·어떻게' 바뀌는지 잰다. 판정이 아니다. 시드는 예비 범위 34900~34999 만 받는다(관문 판정 시드 35000~35199 와 다른 사전 등록 범위는 거부).

    # herbivore_rl/ 에서 (PYTHONUTF8=1). <out> 기본 = AdaptiveEcosystem/Saved/LevelSense (git 밖). <d> = <out>/<바탕>_<두뇌>_<세계>_h<길이>
    S=results/v3/level_sense/sense.py
    python $S list [--base I] [--variants t30 ring30 spot:60:60:8:10 …]                 # 변형 목록 + 규칙 검사 + 나무 자리 요약 (돌리지 않음)
    python $S run --base I|J --brain r7e|r1bf --world N|G --variants base t10 t30 'spot:82:114:8:10' …         [--seeds 34900-34999] [--horizon 1800] [--runner auto|ceval|python] [--workers 6] [--region Barren]         [--regions Barren]   # 그 지역 세계만 (시간 1/3 — 기록 이름 __R-Barren)
        [--maps]             # 공간 지도 (파이썬 실행기) -> <변형>__maps[__R-…].json.gz
        [--stuck K] [--out <out>] [--force]
    python $S table --dir <d> --ref base --variants t10 t30 [--region Barren] [--only tree core ep_hide …] [--save]   # 같은 시드 짝 표
    python $S maps --dir <d> --variant base [--region Barren] [--show flee chased_flee lost lost/chased_flee …] [--spots 3 --trees 8 --radius 10] [--save]
                                                                                         # 공간 지도 글 그림·값 큰 셀·작은 숲 자리 후보
    python $S scan --base I [--grid 20 | --from-map <d> --map chased_flee lost … --spots 3] [--trees 8 --radius 10] [--metrics tree] [--tag …]
                                                                                         # 점마다 작은 숲(평가기·지역 하나) → 줄 세우기 표
    python $S rank --dir <d> --glob 'spot*' [--variants …] [--metrics tree] [--sort fl_obstacle_of_chased --order abs|asc|desc] [--save 이름]
    python $S match --out <out> [--raw <pilot_mask5 원자료 폴더>] [--save <json>]        # 바탕 맞추기 (pilot_mask5 의 R7e N 1800 값과)
    python $S parity --dir <d> --variants base t30 [--save <json>]                       # 두 실행기 맞춰 보기 (같은 변형의 ceval·python 기록)
    python -m pytest results/v3/level_sense/test_sense.py -q                            # 빠른 시험 (약 1 분)

시간 (10-27, 워커 6, 다른 일과 CPU 를 나눈 채): 변형 하나 = 두뇌 하나·시드 100·지역 셋·N·1800 스텝 = 세계 300 개 → 평가기 53~60 초, 파이썬 600~800 초
(10~13 분). --regions Barren 이면 세계 100 개라 약 1/3. 시드 2·300 스텝 같은 연기 판은 평가기 1 초 밑.

바탕 세계 (BASES — 둘 다 게임이 R7e 를 건 Play 의 실제 스냅숏, 저장소의 pilot_mask5/snapshots/<맵>_t10.json 에서 Barren 원판만 비워 '나무 0' 으로):
  I = 통합 맵 LV_Ecosystem_IntegrationTest 세션 20004 (10-24 route5_test, pilot_mask5 가 Barren 나무 0·맑음으로 되돌린 것) + 10-27 게임 기본 GrazeCalm·RestKeep 켬.
  J = 조연우 맵 복사본 LV_EcoV3_JYUEcosystem 세션 20010 240 초 대조 모드 (Barren 나무 0) + 10-27 게임 기본.
  live.prepare(스냅숏 → 판정 세계 G·N, 판 5 거울 configs/v3_wild3_route5_mirror.yaml)를 그대로 부르고, 일(job)은 live.eval_items 그대로 만든 뒤 변형을 일의
  설정(job cfg)·스냅숏 먹이 지도(job snap_food)에만 얹는다. G = 늑대 포만 켬(게임 값), N = 포만 끔(live NOSAT). 두뇌 r7e = 판 5 R7e(관측 24), r1bf = 게임 기본
  내장 R1b-F — 스냅숏 두뇌 칸을 R1b-F 로 바꾼 'R1b-F 를 건 Play' 꼴(두 길 끔)로 관측 21 거울에서 R1b-F + 0 열(결정이 R1b-F 와 비트 단위로 같다)로 돈다.

변형 (한 지역 — 기본 Barren, 편집마다 @지역 으로 바꿀 수 있다. '+' 로 잇는다. 이름표 PRESETS):
  trees:<n>:<자리>   새 줄기 원판 n 개. 자리 = rand(게임 시험용 대역 AddTrees 규칙 무작위 — pilot_mask5.grow_trees 그대로, 씨 20261027 이면 앞 30 그루가 pilot 과 같다)
                     ring(은신처 둘레 2~6 m 고리 — 문 앞), graze(먹이 용량 위 25% 셀 — 사슴이 주로 먹는 트인 풀밭), path(그 풀밭 셀 → 가장 가까운 은신처 문 길목),
                     edge(벽 16 m 안 띠 가운데 모든 은신처에서 16 m 밖 — 은신처에서 먼 가장자리), clump(은신처에서 가장 먼 점 둘레 한 덩어리 — 그루당 약 10 단위²).
                     모든 자리는 AddTrees 와 같은 규칙을 지킨다: 줄기 반지름 40.45 cm × U[1.8, 2.2], 벽 4 m·은신처 둘레 2 m·줄기 사이 3 m 띄움(있던 원판 포함).
  gate               무대 밖 '문지기 원판' 하나((−100, −100, 0.01) — 아무것도 막지 않는다). 원판이 0 → 1 개가 되면 세계의 원판 갈래(늑대 '느려지면 돕기 그만둠' 등)가
                     켜지는 것을 따로 재고, 길 떼어 보기 세계의 대조가 된다(아래).
  weather:<kind>:<I> 지역 날씨 종류·세기 (clear·rain·snow). sight:off = 원판 눈길 가림 끔(그 지역 모든 원판 — Barren 바탕 원판은 0 이라 새 나무만).
  shelter:<k>        은신처 수 (quad 차례 — 3 이면 마지막(45, 15) 원을 빼고, 5 면 quad 규칙이 다섯째를 놓는다). 스냅숏 먹이 용량의 은신처 먹이 부족(× cap_frac)을
                     빠진 원에서는 되돌리고 새 원에는 건다(세계가 그 은신처로 처음부터 만들어졌을 때와 같은 지도).
  food:<s>           지역 먹이 용량 × s (스냅숏 지도에 곱함 — 시작 먹이 = 용량).
  wolves:<n>         지역 늑대 수 (설정 predator_count — 통합 무대가 늑대·사슴 시작 자리를 다시 뽑는다. 종류는 alternate 그대로).
  day:<T>            하루 길이 T 스텝(낮·밤 각 T/2 — 밤 길이). 늑대 포만·사슴 비축의 '일' 단위 계수는 초가 그대로이게 900/T 를 곱한다. 시작 위상은 비율 그대로.
  foliage:<r>:<b>    숲 시야(잎) 켬 (features.obstacles.foliage — 평가기 지원, 변환은 거부하는 칸이라 일 설정에만).
  paths:<길,…>       길 떼어 보기 (파이썬 실행기 전용 — 아래). 새 나무가 닿을 길 = move(몸 이동·밀어내기·돌아가기)·sight(눈길 가림 — 사슴·늑대·거리 두기·도망 기록)·
                     obs(관측 18~20 — 도망 쪽 트임·가까운 줄기·늑대 가림). 고른 길만 새 나무를 쓰고 나머지 길에서는 새 나무가 없는 것처럼 계산한다. gate 를 함께 넣는다.

길 떼어 보기 (env_v2 코드는 고치지 않는다 — 파이썬 실행기 워커 안에서 env_v2.world 의 함수를 감싼다. 감싼 세계는 게임에 없는 세계다):
  move  = obstacle_slide·detour_moves·obstacle_inside·obstacle_push_out 에 넘기는 원판에서 새 나무를 뺀다.
  sight = World._ob_seg_blocked(사슴 → 늑대·늑대 → 사슴·거리 두기·도망 끝 까닭이 모두 지난다)와 flight_route_geometry 의 원판에서 새 나무를 뺀다.
  obs   = obstacle_obs_values 의 원판에서 새 나무를 뺀다(관측 18~20 — R1b-F 세계에는 그 칸이 없다).
  '원판이 하나라도 있나'로 갈리는 세계 코드(늑대 돕기 그만둠 등)는 문지기 원판으로 모든 떼어 보기 세계에서 켜 둔다 — 그래서 대조는 base 가 아니라 gate 다.
  확인(test_sense.py): 길 셋 모두 켬 = 감싸지 않은 세계와 기록이 같다. 길 셋 모두 끔 = gate 세계와 기록이 같다(감싸기가 새 나무의 모든 길을 잡는다).
  밖에 남는 것: 처음 먹이(원판 밑 먹이 줄임 — 스냅숏 먹이 지도가 덮어 0), 통계 칸 obstacle_stats n·area_frac(새 나무를 센다).

실행기:
  ceval  = C++ 평가기(results/v3/live/ceval.py Pool — 파이썬이 만든 시작 상태를 그대로 받아 게임 세계 코드로 돈다, 파이썬 거울 세계와 비트 단위로 같다). 빠르다.
           길 떼어 보기(paths)는 받지 않는다.
  python = 파이썬 거울 세계(run_mirror.run_world 와 같은 차례 + 진단 + 탐침). 느리다. 탐침(행동이 '어떻게' 바뀌나): 움직인 거리(행동별), 가장 가까운 줄기·은신처
           가장자리 거리, 관측 칸 분포(트인 거리·가까운 줄기·가려짐·shelter_reach …, 늑대를 아는 사슴만 따로), 늑대가 새 표적을 잡을 때 그 사슴이 이미 그 늑대를
           알았나(사슴이 먼저 앎 대 늑대가 먼저), 도주 반사 시작 때 가장 가까운 깬 늑대 거리·종류, obstacle_stats(부딪힘·돌아섬·가린 쌍)·pack_stats.
  두 실행기가 같은 변형에서 같은 세계 기록(겹치는 칸 모두)을 내는지 parity 로 맞춘다.
기록: <d>/<변형>__<실행기>[__R-<지역…>].json.gz (세계마다 기록 + meta: 변형 칸·나무 원판·규칙 검사·시간·게임 원점). 끼임(--stuck K)은 G 세계 3600 스텝
파이썬(live stuck 과 같은 일)으로 <변형>__stuck.json.gz. table·rank 는 세 지역 판이 없으면 필요한 지역을 가진 __R- 판을 쓴다.

작은 숲 (10-27 사용자 추가 요청 "나무 자리도 어디에 있을 때 가장 영향을 끼치는지 잘 찾아봐"):
  spot:<x m>:<y m>:<그루>[:<반지름 m>[:<씨>]]  지역 좌표(왼쪽 아래 모서리 0, 무대 0~120 m) 한 점 둘레 원 안에 그루를 고른 분포로 차례로 놓는다. 받아들임 규칙은
      AddTrees 와 같고(위), 그루마다 SPOT_TRIES 번 안에 자리를 못 찾으면 멈추지 않고 '못 놓음'으로 센다 — meta·notes 에 놓은/바란 그루, 원 안 놓을 수 있는
      넓이 몫(벽·은신처 규칙만), 중심 상태(은신처 안·둘레 띄움 안·벽 띄움 안), 게임 좌표 중심(cm = origin_cm + 단위 × 200)이 남는다. 반지름을 빼면
      √(그루 × 10 단위² / π) (8 그루 ≈ 10 m). 줄기 사이 3 m 띄움 때문에 반지름 6 m 원에는 8 그루가 다 들어가지 않는다(5 그루쯤). '+' 로 여러 점을 잇는다.
  scan 은 격자(--grid m) 또는 공간 지도 후보 점마다 spot 변형을 만들고, 다 놓지 못하는 점은 빼고(기록), 바탕과 함께 지역 하나만 평가기로 돌려 rank 표를 낸다.

공간 지도 (run --maps, 파이썬 실행기만 — 스텝 뒤 상태만 읽어 세계를 바꾸지 않는다. 시험이 켬·끔 기록이 같음을 본다):
  셀 MAP_CELL = 2 단위(4 m, 먹이 셀과 같다), 셀마다 횟수. 지도 이름·뜻은 MAPS (deer·graze·flee·hide·chased_flee·onset·spot_deer·spot_wolf·lost·enter·
  enter_fled·caught·wolf_hunt·wolf_idle·wolf_sleep). 지역마다 시드 모두(all)·짝수 시드(even)를 따로 더해 두고, maps 명령이 짝수 ↔ 홀수 지도의 맞음 r
  (자리 고르기를 믿을 만한가)·값 큰 셀·작은 숲 자리 후보(값 큰 셀부터, 서로 --sep m 띄우고 그 점 둘레에 작은 숲을 다 놓을 수 있는 곳)를 낸다. 'a/b' 는 셀마다
  a ÷ b (b < --min-den 이면 0) — 예 lost/chased_flee = 쫓기는 도망 가운데 늑대가 놓친 비율 지도. 근사: spot_deer 는 '늑대가 새 표적을 잡은 때'(표적 고르기는
  매 스텝 보이는 사슴 가운데서 — 처음 본 순간과 같지 않을 수 있다), lost 는 표적을 놓거나 다른 사슴으로 바꾼 때(줄기 가림만이 아니다), enter 는 은신처 원에
  들어가기 바로 전 스텝 자리다.

나무 덕 칸 (METRIC_GROUPS['tree'], table --only tree · scan/rank --metrics tree): 1차 '사건 숨음 비율'(ep_hide)은 은신처로 끝난 사건만 세어 줄기로
  벗어난 도망을 숨음으로 세지 않으므로(PRIOR_EVIDENCE.md) 나무 효과를 거꾸로 보일 수 있다. 그래서 나무가 사슴을 돕는 길을 따로 본다:
  fl_obstacle_of_chased(쫓긴 도망 가운데 끝 까닭 obstacle — 줄기에 가려 늑대가 놓침)·fl_obstacle_n·route_drop_obstacle_n(원판이 늑대 눈길을 가려 놓친
  사건)·route_hidden_chased(쫓기는 FLEE 스텝 가운데 쫓는 늑대 모두에게 가려진 몫)·ep_caught(쫓긴 사건 가운데 잡힘)·ep_saved(1 − 잡힘 − 굶음)·
  fl_caught_of_chased·hunt_success(늑대 사냥 성공률)·hunt_starts_n·fl_own_of_chased·fl_cover_of_chased, 파이썬이면 tgt_blocked·eye_blocked·help_drop_n.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
LS_DIR = HERE.parent                                   # results/v3/level_sense
ROOT = HERE.parents[3]                                 # herbivore_rl/
LIVE_DIR = ROOT / "results" / "v3" / "live"
PM_DIR = LIVE_DIR / "pilot_mask5"
for _p in (ROOT, LIVE_DIR, PM_DIR, ROOT / "results" / "v3" / "adapt", ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "r4",
           ROOT / "results" / "v3" / "wild2", LS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

PROJECT = ROOT.parent / "AdaptiveEcosystem"
OUT_DEFAULT = PROJECT / "Saved" / "LevelSense"         # git 밖 (**/Saved/)
SEED_BOX = (34900, 34999)                              # 예비 시드만 (관문 판정 35000~35199·그 밖 사전 등록 범위는 받지 않는다)
STEP_S = 2.0 / 15.0
UNIT_M = 2.0                                           # 1 단위 = 2 m
TARGET = "Barren"
GATE_DISC = (-100.0, -100.0, 0.01)                     # 문지기 원판 (무대 밖 — 아무것도 막지 않는다)
TREE_SEED = 20261027                                   # pilot_mask5.TREE_SEED 와 같다
TAG_PLACE = 0x4C53454E                                 # "LSEN" — rand 밖 자리 난수
PLACES = ("rand", "ring", "graze", "path", "edge", "clump")
RING_W = 2.0                                           # ring: 줄기 가장자리가 은신처 둘레에서 2 m(띄움) ~ 2 m + 4 m (단위 2)
GRAZE_Q = 0.75                                         # graze·path: 먹이 용량 위 25% 셀
EDGE_BAND, EDGE_FAR = 8.0, 8.0                         # edge: 중심이 벽에서 16 m 안, 모든 은신처 가장자리에서 16 m 밖 (단위)
CLUMP_AREA = 10.0                                      # clump: 그루당 단위² (덩어리 반지름 = √(n·10/π), 못 놓으면 10% 씩 넓힘)
PLACE_TRIES = 4000
BRAINS = {
    "r7e": dict(zip="ckpt/v3/v3_r7_g995_s1_20m.zip", label="R7e (관측 24·판 5, 두 길 후보)"),
    "r1bf": dict(zip="ckpt/v3/v3_r1_g995_s3_20m.zip", label="R1b-F (관측 18·판 2, 게임 기본 내장) — 판정은 R1b-F + 0 열(관측 21, 결정 같음)"),
}
BASES = {
    "I": dict(src="I_t10.json", label="통합 맵 LV_Ecosystem_IntegrationTest 세션 20004 (10-24 route5_test 스냅숏, Barren 나무 0·맑음) + 10-27 게임 기본"),
    "J": dict(src="J_t10.json", label="조연우 맵 복사본 LV_EcoV3_JYUEcosystem 세션 20010 240 초 대조 모드 (Barren 나무 0) + 10-27 게임 기본"),
}
PRESETS = {
    "base": "",
    "t10": "trees:10:rand", "t20": "trees:20:rand", "t30": "trees:30:rand", "t60": "trees:60:rand", "t120": "trees:120:rand", "t240": "trees:240:rand",
    "ring30": "trees:30:ring", "graze30": "trees:30:graze", "path30": "trees:30:path", "edge30": "trees:30:edge", "clump30": "trees:30:clump",
    "gate": "gate",
    "t30nosight": "trees:30:rand+sight:off",
    "fol30": "trees:30:rand+foliage:3:2",
    "t30all": "trees:30:rand+gate+paths:move,sight,obs", "t30none": "trees:30:rand+gate+paths:",
    "t30move": "trees:30:rand+gate+paths:move", "t30sight": "trees:30:rand+gate+paths:sight", "t30obs": "trees:30:rand+gate+paths:obs",
    "t30noobs": "trees:30:rand+gate+paths:move,sight",
    "rain": "weather:rain:1", "snow": "weather:snow:1", "rain065": "weather:rain:0.65", "clear": "weather:clear:0",
    "shelter-1": "shelter:3", "shelter+1": "shelter:5",
    "food50": "food:0.5", "food25": "food:0.25",
    "wolf+1": "wolves:5", "wolf+2": "wolves:6",
    "day2x": "day:1800", "dayhalf": "day:600",
}
WX_KINDS = ("clear", "rain", "snow")
OBS_TRACK = ("pred_count", "pred_dist", "cover_dist", "escape_room", "obstacle_near", "threat_hidden", "in_panic", "shelter_reach", "shelter_edge")
TRUNK_BINS = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, math.inf)         # 단위 (1, 2, 4, 8, 16, 32 m)
SHELTER_BINS = (-math.inf, 0.0, 1.0, 2.0, 4.0, 8.0, 16.0, math.inf)  # 단위 (가장자리 거리 — 0 밑 = 은신처 안)
ONSET_BINS = (0.0, 2.0, 4.0, 7.5, 10.0, 15.0, 20.0, math.inf)       # 단위 (도주 반사 시작 때 가장 가까운 깬 늑대)
OBS_BINS = 10
SPOT_TRIES = 2000                                      # spot: 그루마다 해 볼 자리 수 (못 찾으면 그 그루는 못 놓음으로 센다 — 멈추지 않는다)
MAP_CELL = 2.0                                         # 공간 지도 셀 (단위 = 4 m, 먹이 셀과 같다 — 60 단위 무대면 30 × 30)
MAPS = {                                               # 공간 지도 (파이썬 실행기 --maps, 셀마다 횟수 — 스텝 뒤 상태)
    "deer": "산 사슴 자리 (사슴-스텝)",
    "graze": "먹는 사슴 자리 (실행 행동 graze)",
    "flee": "달리는 사슴 자리 (실행 행동 flee — 도망 길)",
    "hide": "숨는 사슴 자리 (실행 행동 hide)",
    "chased_flee": "늑대 표적인 채 달리는 사슴 자리 (쫓기는 도망 길)",
    "onset": "도주 반사가 시작된 사슴 자리 (사슴이 위협을 알아챈 곳)",
    "spot_deer": "늑대가 새 표적을 잡은 때 그 사슴 자리 (늑대가 사슴을 고른 곳)",
    "spot_wolf": "늑대가 새 표적을 잡은 때 그 늑대 자리",
    "lost": "늑대가 표적을 놓거나 바꾼 때 그 (산) 사슴 자리 (줄기 가림·시야·거리·바꿈 모두)",
    "enter": "사슴이 은신처 원에 들어가기 바로 전 자리 (은신처 문)",
    "enter_fled": "그 가운데 달리며 들어간 사슴 (도망 끝 문)",
    "caught": "잡힌 사슴 자리",
    "wolf_hunt": "표적이 있는 깬 늑대 자리 (사냥 길)",
    "wolf_idle": "표적 없는 깬 늑대 자리 (지나는·기다리는 곳)",
    "wolf_sleep": "자는 늑대 자리 (쉬는 곳)",
}


# --------------------------------------------------------------------- #
# 작은 도구
# --------------------------------------------------------------------- #


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse_seeds(text: str) -> list[int]:
    """'34900-34999' 또는 '34900,34903' → 시드 목록. 예비 범위(SEED_BOX) 밖이면 멈춘다 — 관문 판정 시드와 다른 사전 등록 범위는 쓰지 않는다."""
    out: list[int] = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-", 1))
            out += list(range(lo, hi + 1))
        else:
            out.append(int(part))
    if not out:
        raise SystemExit("시드가 없다")
    bad = [s for s in out if not SEED_BOX[0] <= s <= SEED_BOX[1]]
    if bad:
        raise SystemExit(f"시드 {bad[:5]} 는 예비 범위 {SEED_BOX[0]}~{SEED_BOX[1]} 밖이다 — 관문 판정 시드(35000~35199)와 다른 사전 등록 범위는 쓰지 않는다")
    if len(set(out)) != len(out):
        raise SystemExit("시드가 겹친다")
    return out


def json_dump_gz(path: Path, d) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"), default=_jsonable)
    os.replace(tmp, path)


def json_load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return o.as_posix()
    raise TypeError(type(o).__name__)


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_+.\-]", "_", name)


def _pm():
    import pilot_mask5 as pm  # noqa: WPS433 (sys.path 는 위에서 맞춘다)

    return pm


def _live():
    import live  # noqa: WPS433

    return live


# --------------------------------------------------------------------- #
# 바탕 스냅숏·두뇌
# --------------------------------------------------------------------- #


def base_snapshot(key: str) -> dict:
    """바탕 스냅숏 (나무 0): pilot_mask5/snapshots/<맵>_t10.json 에서 Barren 원판을 비우고(pilot_mask5.set_discs) 환경 판을 0 으로. 그 밖 칸(먹이 지도·
    은신처·사슴·늑대·날씨·10-27 고침 켬)은 pilot_mask5 가 만든 그대로다 — pilot_mask5 의 '바뀌기 전 바탕 + 고침 켬'과 같다(test_sense 가 원 바탕으로 맞춘다)."""
    pm = _pm()
    b = BASES[key]
    s = json.loads((pm.SNAP_DIR / b["src"]).read_text(encoding="utf-8"))
    reg = next(r for r in s["regions"] if r["region"] == pm.TREE_REGION)
    pm.set_discs(reg, [])
    s["env"] = dict(watch=True, revision=0, changed_step=0, first_changed_step=0, trigger="", changes=[])
    s["why"] = f"level_sense 바탕 {key} (나무 0) — {b['label']}"
    return s


def as_brain(snap: dict, brain: str) -> dict:
    """스냅숏의 지금 두뇌를 brain 으로 (r7e 는 그대로). r1bf = 게임 기본 내장 R1b-F 를 건 Play 꼴: 두뇌 칸을 R1b-F 로, 지역 world.wild_flight 의 두 길·
    반사 밖 도망 막음을 끈다(R1b-F 를 건 게임은 두 길이 꺼져 있다). 나머지 칸은 그대로다."""
    if brain == "r7e":
        return snap
    if brain != "r1bf":
        raise SystemExit(f"모르는 두뇌 {brain} ({', '.join(BRAINS)})")
    live = _live()
    s = copy.deepcopy(snap)
    z = live.ad.R1BF
    wsha = live.zip_weights_sha(z)
    s["brain"] = dict(id=f"v3_r1_g995_s3_20m@{wsha[:8]}", model="v3_r1_g995_s3_20m", model_path="ckpt/v3/v3_r1_g995_s3_20m.zip",
                      weights_sha256=wsha, builtin=True, allowed=list(snap["brain"].get("allowed", [1, 1, 1, 0, 0])), last_swap_step=-1,
                      contract_hash=live.zip_contract(z), obs_dim=18, mask_version=2, route=False, flee_gate=False, adapt={})
    for r in s["regions"]:
        wf = r["world"]["wild_flight"]
        wf["route"] = False
        wf["brain_flee_outside_reflex"] = True
    s["why"] = str(s.get("why", "")) + " — 두뇌 R1b-F 로 바꿈 (level_sense)"
    return s


def prepare(base: str, brain: str, prep_dir: Path) -> dict:
    """바탕 스냅숏 → live.prepare (판정 세계 G·N — 실시간 고리와 같은 변환). 반환 info (+ model = 판정에 쓰는 모델 zip, snapshot_sha256)."""
    live = _live()
    snap = as_brain(base_snapshot(base), brain)
    prep_dir.mkdir(parents=True, exist_ok=True)
    sp = prep_dir / f"base_{base}_{brain}.json"
    sp.write_text(json.dumps(snap, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    info = live.prepare(sp, live.read_snapshot(sp), prep_dir / f"{base}_{brain}", live.brain_folders(prep_dir))
    info["model"] = Path(live.ad.ROOT / info["record"]["anchor"])
    info["snapshot_sha256"] = sha256_file(sp)
    info["base"], info["brain"] = base, brain
    # 게임 좌표: 세계 cm = origin_cm + 단위 × 200 (C++ FRegionCtx UnitsToCm — EcoPolicyV3IntegratedSubsystem.h). 공간 지도·spot 을 레벨 자리로 옮길 때 쓴다
    info["origin_cm"] = {r["region"]: [float(v) for v in r.get("origin_cm", [0.0, 0.0, 0.0])] for r in snap["regions"]}
    return info


def game_cm(info: dict, region: str, x_units: float, y_units: float) -> list:
    """지역 좌표(단위) → 게임 세계 좌표 cm [X, Y] (스냅숏 origin_cm + 단위 × 200)."""
    o = (info.get("origin_cm") or {}).get(region, [0.0, 0.0, 0.0])
    return [round(o[0] + float(x_units) * 200.0, 1), round(o[1] + float(y_units) * 200.0, 1)]


# --------------------------------------------------------------------- #
# 변형
# --------------------------------------------------------------------- #


def parse_variant(name: str) -> dict:
    """변형 이름(PRESETS) 또는 편집 글('trees:30:ring+gate+…') → {name, spec, edits[{kind, region?, …}]}."""
    spec = PRESETS.get(name, name)
    edits = []
    for part in [p.strip() for p in spec.split("+") if p.strip()]:
        region = None
        if "@" in part:
            part, region = part.split("@", 1)
        f = part.split(":")
        k = f[0]
        try:
            if k == "trees":
                e = dict(kind="trees", n=int(f[1]), place=f[2] if len(f) > 2 else "rand", seed=int(f[3]) if len(f) > 3 else TREE_SEED)
                if e["place"] not in PLACES or e["n"] < 1:
                    raise ValueError
            elif k == "spot":
                # spot:<x m>:<y m>:<그루>[:<반지름 m>[:<씨>]] — 지역 좌표(왼쪽 아래 모서리 0, 1 단위 = 2 m) 한 점 둘레 작은 숲
                x_m, y_m, n = float(f[1]), float(f[2]), int(f[3])
                r_m = float(f[4]) if len(f) > 4 and f[4] != "" else None
                e = dict(kind="trees", place="spot", n=n, x=x_m / UNIT_M, y=y_m / UNIT_M, r=None if r_m is None else r_m / UNIT_M,
                         seed=int(f[5]) if len(f) > 5 else TREE_SEED)
                if n < 1 or not (math.isfinite(x_m) and math.isfinite(y_m)) or x_m < 0 or y_m < 0 or (r_m is not None and not r_m > 0):
                    raise ValueError
            elif k == "gate":
                e = dict(kind="gate")
            elif k == "weather":
                e = dict(kind="weather", wx=f[1], intensity=float(f[2]) if len(f) > 2 else (0.0 if f[1] == "clear" else 1.0))
                if e["wx"] not in WX_KINDS or not (0.0 <= e["intensity"] <= 1.0) or (e["wx"] != "clear" and e["intensity"] <= 0.0):
                    raise ValueError
                if e["wx"] == "clear":
                    e["intensity"] = 0.0
            elif k == "sight":
                if f[1:] != ["off"]:
                    raise ValueError
                e = dict(kind="sight", on=False)
            elif k == "shelter":
                e = dict(kind="shelter", count=int(f[1]))
                if not 1 <= e["count"] <= 8:
                    raise ValueError
            elif k == "food":
                e = dict(kind="food", scale=float(f[1]))
                if not e["scale"] >= 0.0:
                    raise ValueError
            elif k == "wolves":
                e = dict(kind="wolves", n=int(f[1]))
                if not 0 <= e["n"] <= 12:
                    raise ValueError
            elif k == "day":
                e = dict(kind="day", period=int(f[1]))
                if e["period"] <= 0 or e["period"] % 2:
                    raise ValueError
            elif k == "foliage":
                e = dict(kind="foliage", r=float(f[1]) if len(f) > 1 else 3.0, block=float(f[2]) if len(f) > 2 else 2.0)
            elif k == "paths":
                act = [x for x in (f[1].split(",") if len(f) > 1 else []) if x]
                if any(x not in ("move", "sight", "obs") for x in act):
                    raise ValueError
                e = dict(kind="paths", active=sorted(set(act)))
            else:
                raise ValueError
        except (ValueError, IndexError):
            raise SystemExit(f"변형 편집 {part!r} 을 읽지 못했다 (sense.py 머리 주석 '변형')") from None
        if region:
            e["region"] = region
        edits.append(e)
    kinds = [e["kind"] for e in edits]
    for k in set(kinds):
        if k != "trees" and kinds.count(k) > 1:
            raise SystemExit(f"변형 {name}: 편집 {k} 를 두 번 주었다")
    if "paths" in kinds:
        if "trees" not in kinds:
            raise SystemExit(f"변형 {name}: paths 는 trees 와 함께 쓴다 (새 나무의 길을 떼어 본다)")
        if "gate" not in kinds:
            raise SystemExit(f"변형 {name}: paths 는 gate 와 함께 쓴다 (원판 갈래를 모든 떼어 보기 세계에서 켜 둔다 — 대조 = gate)")
        if "foliage" in kinds or "sight" in kinds:
            raise SystemExit(f"변형 {name}: paths 는 foliage·sight:off 와 함께 쓰지 않는다")
    return dict(name=name, spec=spec, edits=edits, python_only="paths" in kinds)


def _wall_ok(x, y, r, size, wall):
    return wall + r <= x <= size - wall - r and wall + r <= y <= size - wall - r


def tree_rules():
    """AddTrees 규칙 (단위): 벽 띄움, 은신처 둘레 띄움, 줄기 사이 띄움, 반지름 범위."""
    pm = _pm()
    return dict(wall=pm.WALL_CLEAR_M * 100.0 / pm.UNIT_CM, clear=pm.COVER_CLEAR_M * 100.0 / pm.UNIT_CM, gap=pm.GAP_M * 100.0 / pm.UNIT_CM,
                r_lo=pm.TRUNK_R_MESH_CM * pm.SCALE_LO / pm.UNIT_CM, r_hi=pm.TRUNK_R_MESH_CM * pm.SCALE_HI / pm.UNIT_CM)


def _spot_ok(x, y, r, size, covers, placed, R) -> bool:
    """pilot_mask5.grow_trees 와 같은 받아들임 규칙 (벽·은신처 둘레·줄기 사이)."""
    if not _wall_ok(x, y, r, size, R["wall"]):
        return False
    for c in covers:
        if float(c[2]) > 0.0 and math.hypot(x - float(c[0]), y - float(c[1])) < float(c[2]) + R["clear"] + r:
            return False
    for d in placed:
        if math.hypot(x - d[0], y - d[1]) < d[2] + r + R["gap"]:
            return False
    return True


def _graze_cells(size: float, covers, cap, cell: float, R) -> tuple[np.ndarray, np.ndarray]:
    """먹이 용량 위 (1 − GRAZE_Q) 셀 (은신처 둘레 띄움 밖에 중심이 있는 셀만) → (셀 중심 (k, 2), 용량 (k,))."""
    g = int(round(math.sqrt(len(cap))))
    c = np.asarray(cap, dtype=np.float64).reshape(g, g)                 # [iy, ix]
    iy, ix = np.mgrid[0:g, 0:g]
    cx, cy = (ix + 0.5) * cell, (iy + 0.5) * cell
    ok = np.ones((g, g), dtype=bool)
    for cv in covers:
        ok &= np.hypot(cx - float(cv[0]), cy - float(cv[1])) >= float(cv[2]) + R["clear"]
    ok &= (cx >= R["wall"]) & (cx <= size - R["wall"]) & (cy >= R["wall"]) & (cy <= size - R["wall"])
    vals = c[ok]
    if not len(vals):
        raise SystemExit("graze: 놓을 수 있는 셀이 없다")
    q = float(np.quantile(vals, GRAZE_Q))
    sel = ok & (c >= q) & (c > 0.0)
    if not sel.any():
        raise SystemExit("graze: 먹이 있는 셀이 없다")
    return np.c_[cx[sel], cy[sel]], c[sel]


def place_spot(n: int, size: float, covers, avoid, seed: int, region_index: int, center, radius=None) -> tuple[list, dict]:
    """spot: 점 center(단위) 둘레 반지름 radius(단위, None = √(n·CLUMP_AREA/π)) 원 안 고른 분포로 n 그루를 차례로 놓는다. 받아들임 규칙은 AddTrees 와 같다(벽 4 m·
    은신처 둘레 2 m·줄기 사이 3 m, 있던 원판 포함). 그루마다 SPOT_TRIES 번 안에 자리를 못 찾으면 그 그루는 건너뛰고 '못 놓음'으로 센다(멈추지 않는다).
    반환 (놓은 원판, meta: 중심·반지름 m, 바란·놓은·못 놓은 수, 원 안에서 벽·은신처 규칙만 지키는 넓이 몫 free_frac, 중심 자리 상태)."""
    pm = _pm()
    R = tree_rules()
    cx, cy = (float(v) for v in center)
    if not (0.0 <= cx <= size and 0.0 <= cy <= size):
        raise SystemExit(f"spot 중심 ({cx * UNIT_M:g}, {cy * UNIT_M:g}) m 가 무대(0~{size * UNIT_M:g} m) 밖이다")
    rs = float(radius) if radius else math.sqrt(n * CLUMP_AREA / math.pi)
    g = np.random.default_rng([TAG_PLACE, int(seed), int(region_index) + 1, len(PLACES), int(round(cx * 1000)), int(round(cy * 1000)),
                               int(round(rs * 1000)), int(n)])
    cov = [list(map(float, c)) for c in covers if float(c[2]) > 0.0]
    placed = [list(map(float, d)) for d in avoid]
    out: list = []
    miss = 0
    for _k in range(n):
        for _try in range(SPOT_TRIES):
            r = float(pm.TRUNK_R_MESH_CM * g.uniform(pm.SCALE_LO, pm.SCALE_HI) / pm.UNIT_CM)
            rr, th = rs * math.sqrt(g.uniform(0.0, 1.0)), g.uniform(0.0, 2.0 * math.pi)
            x, y = cx + rr * math.cos(th), cy + rr * math.sin(th)
            if _spot_ok(x, y, r, size, cov, placed, R):
                out.append([float(x), float(y), r])
                placed.append([float(x), float(y), r])
                break
        else:
            miss += 1
    # 원 안 격자점(0.25 단위) 가운데 벽·은신처 둘레 규칙만(줄기 사이 빼고, 평균 반지름) 지키는 몫 — 못 놓은 까닭 읽기용
    r_mid = 0.5 * (R["r_lo"] + R["r_hi"])
    xs = np.arange(cx - rs, cx + rs + 1e-9, 0.25)
    gx, gy = np.meshgrid(xs, np.arange(cy - rs, cy + rs + 1e-9, 0.25))
    ind = np.hypot(gx - cx, gy - cy) <= rs
    ok = ind & (gx >= R["wall"] + r_mid) & (gx <= size - R["wall"] - r_mid) & (gy >= R["wall"] + r_mid) & (gy <= size - R["wall"] - r_mid)
    for c in cov:
        ok &= np.hypot(gx - c[0], gy - c[1]) >= c[2] + R["clear"] + r_mid
    d_edge = min((math.hypot(cx - c[0], cy - c[1]) - c[2] for c in cov), default=math.inf)
    state = ("은신처 안" if d_edge < 0 else "은신처 둘레 띄움 안" if d_edge < R["clear"] + r_mid else
             "벽 띄움 안" if not _wall_ok(cx, cy, r_mid, size, R["wall"]) else "놓을 수 있음")
    meta = dict(place="spot", center_m=[round(cx * UNIT_M, 3), round(cy * UNIT_M, 3)], radius_m=round(rs * UNIT_M, 3), n_req=int(n), n_placed=len(out),
                unplaced=int(miss), free_frac=round(float(ok.sum() / max(ind.sum(), 1)), 4), center_state=state,
                center_shelter_edge_m=round(d_edge * UNIT_M, 3) if math.isfinite(d_edge) else None)
    return out, meta


def place_trees(place: str, n: int, size: float, covers, avoid, cap, cell: float, seed: int, region_index: int, center=None,
                radius=None) -> tuple[list, dict]:
    """새 줄기 원판 n 개 [x, y, r] (놓은 차례) + 자리 요약. avoid = 있던 원판(문지기 빼고). rand 는 pilot_mask5.grow_trees 그대로(같은 씨·지역이면 pilot 과 같은
    자리), 나머지는 자리마다 제안 분포만 다르고 받아들임 규칙은 같다. spot 은 place_spot (center·radius — 못 놓은 그루는 세고 멈추지 않는다)."""
    pm = _pm()
    R = tree_rules()
    if place == "spot":
        return place_spot(n, size, covers, avoid, seed, region_index, center, radius)
    if place == "rand":
        return [list(map(float, t)) for t in pm.grow_trees(size, covers, avoid, n, seed, region_index)], dict(place="rand", rule="pilot_mask5.grow_trees")
    g = np.random.default_rng([TAG_PLACE, int(seed), int(region_index) + 1, PLACES.index(place)])
    placed = [list(map(float, d)) for d in avoid]
    out: list = []
    cov = [list(map(float, c)) for c in covers if float(c[2]) > 0.0]
    meta: dict = dict(place=place)
    if place in ("graze", "path"):
        pts, w = _graze_cells(size, cov, cap, cell, R)
        pr = w / w.sum()
        meta.update(cells=int(len(pts)), cap_q=float(np.quantile(np.asarray(cap, dtype=np.float64), GRAZE_Q)))
    if place == "clump":
        xs = np.arange(R["wall"] + 1.0, size - R["wall"] - 1.0 + 1e-9, 0.5)
        best, cen = -math.inf, (size / 2, size / 2)
        for x in xs:
            for y in xs:
                d = min((math.hypot(x - c[0], y - c[1]) - c[2] for c in cov), default=math.inf)
                if d > best + 1e-9:
                    best, cen = d, (float(x), float(y))
        rc = math.sqrt(n * CLUMP_AREA / math.pi)
        meta.update(center=[round(cen[0], 3), round(cen[1], 3)], r_start=round(rc, 3))
    for k in range(n):
        for _try in range(PLACE_TRIES):
            r = float(pm.TRUNK_R_MESH_CM * g.uniform(pm.SCALE_LO, pm.SCALE_HI) / pm.UNIT_CM)
            if place == "ring":
                c = cov[int(g.integers(len(cov)))]
                th = g.uniform(0.0, 2.0 * math.pi)
                e = g.uniform(R["clear"] + r, R["clear"] + r + RING_W)
                x, y = c[0] + (c[2] + e) * math.cos(th), c[1] + (c[2] + e) * math.sin(th)
            elif place == "graze":
                j = int(g.choice(len(pts), p=pr))
                x, y = pts[j, 0] + g.uniform(-0.5, 0.5) * cell, pts[j, 1] + g.uniform(-0.5, 0.5) * cell
            elif place == "path":
                j = int(g.choice(len(pts), p=pr))
                gx, gy = float(pts[j, 0]), float(pts[j, 1])
                kk = int(np.argmin([math.hypot(gx - c[0], gy - c[1]) - c[2] for c in cov]))
                c = cov[kk]
                dx, dy = gx - c[0], gy - c[1]
                L = math.hypot(dx, dy) or 1.0
                ux, uy = dx / L, dy / L
                door = (c[0] + c[2] * ux, c[1] + c[2] * uy)
                s = g.uniform(0.0, 1.0)
                lat = g.uniform(-1.0, 1.0)
                x = door[0] + s * (gx - door[0]) - lat * uy
                y = door[1] + s * (gy - door[1]) + lat * ux
            elif place == "edge":
                x = g.uniform(R["wall"] + r, size - R["wall"] - r)
                y = g.uniform(R["wall"] + r, size - R["wall"] - r)
                if min(x, y, size - x, size - y) > EDGE_BAND:
                    continue
                if min((math.hypot(x - c[0], y - c[1]) - c[2] for c in cov), default=math.inf) < EDGE_FAR:
                    continue
            elif place == "clump":
                if _try and _try % 400 == 0:
                    rc *= 1.1
                rr, th = rc * math.sqrt(g.uniform(0.0, 1.0)), g.uniform(0.0, 2.0 * math.pi)
                x, y = cen[0] + rr * math.cos(th), cen[1] + rr * math.sin(th)
            else:
                raise ValueError(place)
            if _spot_ok(x, y, r, size, cov, placed, R):
                out.append([float(x), float(y), r])
                placed.append([float(x), float(y), r])
                break
        else:
            raise SystemExit(f"{place}: 나무 {k + 1} 번째 자리를 {PLACE_TRIES} 번 안에 못 찾았다 (지금까지 {len(out)} 그루)")
    if place == "clump":
        meta["r_end"] = round(rc, 3)
    return out, meta


def _region_world(cfg: dict, seed: int, snap_food=None):
    """설정 dict 로 파이썬 세계 하나 (reset, 스냅숏 먹이 지도를 주면 덮는다)."""
    from env.config import Config
    from env_v2.world import World

    w = World(Config(copy.deepcopy(cfg)), seeds=[int(seed)])
    if snap_food is not None:
        _live().ad.apply_snapshot_food(w, snap_food)
    return w


def tree_summary(new, covers, cap, cell: float, size: float) -> dict:
    """새 나무 자리 요약: 은신처 가장자리까지 거리(단위)·벽까지·그 셀 먹이 용량·짝 거리 최소."""
    if not new:
        return dict(n=0)
    g = int(round(math.sqrt(len(cap))))
    c = np.asarray(cap, dtype=np.float64).reshape(g, g)
    a = np.asarray(new, dtype=np.float64)
    cov = np.asarray([c_ for c_ in covers if float(c_[2]) > 0.0], dtype=np.float64).reshape(-1, 3)
    de = (np.sqrt(((a[:, None, :2] - cov[None, :, :2]) ** 2).sum(-1)) - cov[None, :, 2]).min(1) if len(cov) else np.full(len(a), np.inf)
    wall = np.minimum.reduce([a[:, 0], a[:, 1], size - a[:, 0], size - a[:, 1]])
    ix = np.clip((a[:, 0] / cell).astype(int), 0, g - 1)
    iy = np.clip((a[:, 1] / cell).astype(int), 0, g - 1)
    dd = np.sqrt(((a[:, None, :2] - a[None, :, :2]) ** 2).sum(-1)) + np.eye(len(a)) * 1e9
    return dict(n=int(len(a)), shelter_edge_m=dict(mean=float(de.mean() * UNIT_M), min=float(de.min() * UNIT_M), max=float(de.max() * UNIT_M)),
                wall_m=dict(mean=float(wall.mean() * UNIT_M), min=float(wall.min() * UNIT_M)), cell_cap_mean=float(c[iy, ix].mean()),
                region_cap_mean=float(c.mean()), nn_m=dict(mean=float(dd.min(1).mean() * UNIT_M), min=float(dd.min() * UNIT_M)) if len(a) > 1 else None,
                r_m=dict(mean=float(a[:, 2].mean() * UNIT_M), min=float(a[:, 2].min() * UNIT_M), max=float(a[:, 2].max() * UNIT_M)))


def edit_region(info: dict, cfg0: dict, food0: list, region: str, edits: list, seed0: int) -> dict:
    """지역 하나의 일 설정·먹이 지도에 편집을 얹는다 (시드와 무관 — 지역마다 한 번). 반환 {cfg, snap_food, paths, new_trees, gate, notes, place_meta}."""
    cfg = copy.deepcopy(cfg0)
    food = [float(x) for x in food0]
    f = cfg["v2"]["features"]
    notes: list = []
    reg = info["regions"][region]
    ed = {e["kind"]: e for e in edits if e["kind"] != "trees"}
    trees = [e for e in edits if e["kind"] == "trees"]
    if "weather" in ed:
        e = ed["weather"]
        before = list(f["wild_weather"]["regions"][region])
        f["wild_weather"]["regions"][region] = [e["wx"], float(e["intensity"])]
        notes.append(f"날씨 {before[0]} {before[1]:g} → {e['wx']} {e['intensity']:g}")
    if "shelter" in ed:
        e = ed["shelter"]
        ist = f["integrated_stage"]
        w_old = _region_world(cfg, seed0)
        before = int(ist["cover_count"])
        ist["cover_count"] = int(e["count"])
        w_new = _region_world(cfg, seed0)
        if len(w_new.cov_r) != int(e["count"]):
            raise SystemExit(f"은신처 {e['count']} 개를 quad 규칙이 다 놓지 못했다 (놓은 수 {len(w_new.cov_r)})")
        zf = f["realism_cover_food"]
        if zf.get("enabled"):
            frac = float(zf["cap_frac"])
            old_c, new_c = w_old.cover_food_cell.ravel(), w_new.cover_food_cell.ravel()
            a = np.asarray(food, dtype=np.float64)
            a = np.where(old_c & ~new_c, a / frac, a)
            a = np.where(new_c & ~old_c, a * frac, a)
            food = a.tolist()
            notes.append(f"은신처 {before} → {e['count']} (먹이 용량: 빠진 원 셀 {int((old_c & ~new_c).sum())} 개 ÷ {frac:g}, 새 원 셀 "
                         f"{int((new_c & ~old_c).sum())} 개 × {frac:g})")
        else:
            notes.append(f"은신처 {before} → {e['count']}")
        notes.append("은신처 원 " + json.dumps(np.c_[w_new.cov_c, w_new.cov_r].round(4).tolist()))
    if "food" in ed:
        s = float(ed["food"]["scale"])
        food = (np.asarray(food, dtype=np.float64) * s).tolist()
        notes.append(f"먹이 용량 × {s:g}")
    if "wolves" in ed:
        n = int(ed["wolves"]["n"])
        before = list(cfg["rand"]["predator_count"])
        cfg["rand"]["predator_count"] = [n, n]
        notes.append(f"늑대 {before[0]} → {n} (시작 배치 다시 뽑힘)")
    if "day" in ed:
        P = int(ed["day"]["period"])
        dn = f["daynight"]
        P0 = int(dn["periods"][0])
        if len(dn["periods"]) != 1:
            raise SystemExit("하루 길이 목록이 하나가 아니다")
        k = P / P0
        dn["periods"] = [P]
        if float(dn["transition_norm"]) < P / 2:
            raise SystemExit(f"하루 길이 {P} 의 반이 관측 정규화 transition_norm {dn['transition_norm']} 보다 길다 (계약 칸 — 바꾸지 않는다)")
        ist = f["integrated_stage"]
        if ist.get("day_offset") is not None:
            ist["day_offset"] = int(round(int(ist["day_offset"]) * k)) % P
        for blk, key in (("wild_satiation", "sat_days"), ("wild_reserve", "reserve_days")):
            if blk in f and key in f[blk]:
                f[blk][key] = float(f[blk][key]) / k
        notes.append(f"하루 {P0} → {P} 스텝 (밤 {P0 // 2} → {P // 2} 스텝), 포만·비축 '일' 계수 × {1 / k:g} (초 그대로)")
    if "foliage" in ed:
        e = ed["foliage"]
        f["obstacles"]["foliage"] = dict(enabled=True, r=float(e["r"]), block=float(e["block"]), trees="all")
        notes.append(f"숲 시야(잎) 켬 r {e['r']:g}·block {e['block']:g}")
    if "sight" in ed:
        f["obstacles"]["block_sight"] = False
        notes.append("원판 눈길 가림 끔 (이 지역 모든 원판)")
    base_discs = [list(map(float, d)) for d in (f["obstacles"].get("fixed") or [])]
    new_all: list = []
    pmeta: list = []
    if trees:
        wv = _region_world(cfg, seed0)
        covers = np.c_[wv.cov_c, wv.cov_r].tolist()
        cell = float(cfg["food_cell"])
        size = float(wv.size)
        for e in trees:
            spot = e["place"] == "spot"
            new, meta = place_trees(e["place"], int(e["n"]), size, covers, base_discs + new_all, food, cell, int(e["seed"]), int(reg["region_index"]),
                                    center=(e["x"], e["y"]) if spot else None, radius=e.get("r") if spot else None)
            meta["summary"] = tree_summary(new, covers, food, cell, size)
            pmeta.append(meta)
            new_all += new
            near = (f"은신처 가장자리까지 평균 {meta['summary']['shelter_edge_m']['mean']:.1f} m" if new else "놓은 그루 없음")
            if spot:
                notes.append(f"작은 숲 {meta['n_placed']}/{meta['n_req']} 그루 (중심 {meta['center_m'][0]:g}, {meta['center_m'][1]:g} m · 반지름 "
                             f"{meta['radius_m']:g} m · 씨 {e['seed']} — 중심 {meta['center_state']}, 원 안 놓을 수 있는 넓이 {meta['free_frac'] * 100:.0f}%, "
                             f"못 놓음 {meta['unplaced']}) — {near}")
            else:
                notes.append(f"나무 +{e['n']} ({e['place']}, 씨 {e['seed']}) — {near}")
    gate = "gate" in ed
    discs = base_discs + new_all + ([list(GATE_DISC)] if gate else [])
    if trees or gate:
        f["obstacles"]["fixed"] = sorted(discs)                     # 게임과 같은 (x, y, r) 순 (pilot_mask5.set_discs 와 같다)
    if gate:
        notes.append("문지기 원판 (−100, −100, 0.01)")
    paths = None
    if "paths" in ed:
        act = set(ed["paths"]["active"])
        drop = [list(map(float, d)) for d in new_all]
        paths = dict(active=sorted(act), drop={k: ([] if k in act else drop) for k in ("move", "sight", "obs")})
        notes.append(f"길 떼어 보기: 새 나무가 닿는 길 = {', '.join(sorted(act)) or '없음'} (파이썬 실행기 감싸기 — 게임에 없는 세계)")
    return dict(cfg=cfg, snap_food=food, paths=paths, new_trees=new_all, gate=gate, base_discs=base_discs, notes=notes, place_meta=pmeta)


def build_items(info: dict, model: Path, seeds, horizon: int, world: str, var: dict, region: str = TARGET, kind: str = "multi",
                regions_run=None) -> tuple[list, dict]:
    """live.eval_items 그대로 만든 일에 변형을 얹는다 → (일 목록 (kind, 꼬리표, job), 변형 기록 {지역: edit_region 결과 요약 + 규칙 검사}).
    regions_run 을 주면 그 지역 세계만 돌린다(바꾸지 않은 지역은 바탕과 같은 세계라 지역 하나 비교에는 빼도 된다 — 시간 1/3)."""
    live = _live()
    if kind == "multi":
        items = live.eval_items(info, "cur", model, seeds, horizon, world, "multi", [horizon])
    else:
        items = live.stuck_items(info, "cur", model, seeds, horizon)
    if regions_run:
        bad = [r for r in regions_run if r not in info["regions"]]
        if bad:
            raise SystemExit(f"지역 {bad} 이 없다 ({', '.join(info['regions'])})")
        items = [it for it in items if it[2]["region"] in set(regions_run)]
    by: dict = {}
    for e in var["edits"]:
        r = e.get("region", region)
        if r not in info["regions"]:
            raise SystemExit(f"지역 {r} 이 없다 ({', '.join(info['regions'])})")
        if regions_run and r not in regions_run:
            raise SystemExit(f"변형 {var['name']} 이 바꾸는 지역 {r} 이 돌릴 지역 {list(regions_run)} 밖이다")
        by.setdefault(r, []).append(e)
    vrec: dict = {}
    for r, edits in by.items():
        j0 = next(it[2] for it in items if it[2]["region"] == r)
        res = edit_region(info, j0["cfg"], j0["snap_food"], r, edits, int(j0["seed"]))
        for it in items:
            job = it[2]
            if job["region"] != r:
                continue
            job["cfg"] = copy.deepcopy(res["cfg"])
            job["snap_food"] = list(res["snap_food"])
            if res["paths"] is not None:
                job["paths"] = copy.deepcopy(res["paths"])
        chk = check_region(info, next(it[2] for it in items if it[2]["region"] == r), res, edits)
        for pmeta in res["place_meta"]:
            if pmeta["place"] == "spot":
                pmeta["center_game_cm"] = game_cm(info, r, pmeta["center_m"][0] / UNIT_M, pmeta["center_m"][1] / UNIT_M)
        vrec[r] = dict(notes=res["notes"], new_trees=res["new_trees"], gate=res["gate"], base_discs=len(res["base_discs"]), paths=res["paths"],
                       place=res["place_meta"], checks=chk,
                       cfg_sha=hashlib.sha256(json.dumps(res["cfg"], sort_keys=True, default=_jsonable).encode()).hexdigest()[:16],
                       food_sha=hashlib.sha256(np.asarray(res["snap_food"], dtype="<f8").tobytes()).hexdigest()[:16])
    return items, vrec


def check_region(info: dict, job: dict, res: dict, edits: list) -> dict:
    """변형 세계가 세계 규칙을 지키나 (어기면 멈춘다): 새 줄기 = 무대 안 벽 4 m·은신처 둘레 2 m·줄기 사이 3 m 띄움(있던 원판 포함), 은신처 = 무대 안·서로
    겹치지 않음·바라는 수, reset 뒤 사슴·늑대가 (그 세계에서 몸을 막는) 원판 안에 없음, 먹이 용량 유한·0 이상, 늑대 수, 하루 길이. 평가기가 받는 세계인가도
    적는다(ceval world_block — 길 떼어 보기 세계는 파이썬만)."""
    import ceval
    from env_v2.world import obstacle_inside

    R = tree_rules()
    out: dict = dict(ok=True, items=[])
    with ghost_scope(job.get("paths")):
        w = ceval.make_world(job)
        size = float(w.size)
        new = [tuple(d) for d in res["new_trees"]]
        others = [tuple(d) for d in res["base_discs"]]
        cov = np.c_[w.cov_c, w.cov_r]
        # 새 줄기
        worst = dict(wall=math.inf, shelter=math.inf, gap=math.inf)
        for i, (x, y, r) in enumerate(new):
            if not (R["r_lo"] - 1e-9 <= r <= R["r_hi"] + 1e-9):
                raise SystemExit(f"새 줄기 {i} 반지름 {r} 이 AddTrees 범위 밖")
            worst["wall"] = min(worst["wall"], min(x, y, size - x, size - y) - r - R["wall"])
            for c in cov:
                worst["shelter"] = min(worst["shelter"], math.hypot(x - c[0], y - c[1]) - c[2] - R["clear"] - r)
            for j, d in enumerate(others + new):
                if j - len(others) == i:
                    continue
                worst["gap"] = min(worst["gap"], math.hypot(x - d[0], y - d[1]) - d[2] - r - R["gap"])
        if new and min(worst.values()) < -1e-9:
            raise SystemExit(f"새 줄기가 AddTrees 규칙을 어긴다 (여유 단위: {worst})")
        if new:
            out["items"].append(f"새 줄기 {len(new)}: 벽·은신처 둘레·줄기 사이 여유 최소 {worst['wall']:.3f}·{worst['shelter']:.3f}·{worst['gap']:.3f} 단위 (≥ 0)")
        disc = np.asarray(w.obstacles, dtype=np.float64).reshape(-1, 3)
        gate = [d for d in disc.tolist() if tuple(d) == GATE_DISC]
        if len(disc) != len(others) + len(new) + len(gate) or (res["gate"] and len(gate) != 1):
            raise SystemExit(f"세계 원판 수 {len(disc)} 이 바탕 {len(others)} + 새 {len(new)} + 문지기 {len(gate)} 와 다르다")
        out["items"].append(f"세계 원판 {len(disc)} = 바탕 {len(others)} + 새 {len(new)} + 문지기 {len(gate)}")
        # 은신처
        for i in range(len(cov)):
            x, y, r = cov[i]
            if r <= 0 or x - r < 0 or y - r < 0 or x + r > size or y + r > size:
                raise SystemExit(f"은신처 {i} 가 무대 밖이다 {cov[i].tolist()}")
            for j in range(i + 1, len(cov)):
                if math.hypot(x - cov[j][0], y - cov[j][1]) < r + cov[j][2]:
                    raise SystemExit(f"은신처 {i}·{j} 가 겹친다")
        want = next((e["count"] for e in edits if e["kind"] == "shelter"), None)
        if want is not None and len(cov) != want:
            raise SystemExit(f"은신처 수 {len(cov)} 이 {want} 와 다르다")
        out["items"].append(f"은신처 {len(cov)}: 무대 안·서로 안 겹침")
        # 개체가 몸을 막는 원판 안에 없나 (길 떼어 보기 세계는 move 길의 원판만 — 감싼 세계 그대로)
        mv = [d for d in disc.tolist() if not (job.get("paths") and tuple(d) in {tuple(x) for x in job["paths"]["drop"]["move"]})]
        mv = np.asarray(mv, dtype=np.float64).reshape(-1, 3)
        body = float(w._ob["body_r"]) if w._ob is not None else 0.0
        n_in_d = int(obstacle_inside(np.asarray(w.pos), mv, body).sum()) if len(mv) else 0
        n_in_w = int(obstacle_inside(np.asarray(w.pred_pos), mv, body).sum()) if len(mv) else 0
        if n_in_d or n_in_w:
            raise SystemExit(f"reset 뒤 원판 안 사슴 {n_in_d}·늑대 {n_in_w}")
        out["items"].append(f"reset 뒤 몸을 막는 원판 안 사슴 0·늑대 0 (원판 {len(mv)})")
        cap = np.asarray(w.food_cap, dtype=np.float64)
        if not np.all(np.isfinite(cap)) or cap.min() < 0:
            raise SystemExit("먹이 용량에 음수·수가 아닌 값")
        out["items"].append(f"먹이 용량 합 {cap.sum():.3f} (셀 {cap.size})")
        wn = next((e["n"] for e in edits if e["kind"] == "wolves"), None)
        if wn is not None and int(w.M) != wn:
            raise SystemExit(f"늑대 수 {w.M} 이 {wn} 와 다르다")
        out["items"].append(f"늑대 {int(w.M)} (잠행 {int((w.pred_type == 1).sum())}·추격 {int((w.pred_type == 0).sum())}), 사슴 {int(w.N)}, 하루 {int(w.dn_period)} 스텝"
                            f"·시작 위상 {int(w.dn_offset)}, 날씨 {['clear', 'rain', 'snow'][int(w.weather_kind)] if w._wx is not None else '-'} "
                            f"{float(w.weather_intensity) if w._wx is not None else 0:g}")
        out["covers"] = cov.round(4).tolist()
        out["wolves"] = int(w.M)
        try:
            ceval.world_block(w)
            out["ceval"] = "받음"
        except ValueError as ex:
            out["ceval"] = f"거부: {ex}"
    return out


# --------------------------------------------------------------------- #
# 길 떼어 보기 (파이썬 워커 안 감싸기 — env_v2 는 고치지 않는다)
# --------------------------------------------------------------------- #

_GHOST: dict = dict(move=None, sight=None, obs=None)        # 길마다 떨굴 원판 {(x, y, r)} — None/빈 = 그대로
_GHOST_ON = [False]


def _drop(discs, key):
    d = _GHOST[key]
    if not d:
        return discs
    a = np.asarray(discs, dtype=np.float64).reshape(-1, 3)
    if not len(a):
        return discs
    keep = np.fromiter((tuple(map(float, row)) not in d for row in a), dtype=bool, count=len(a))
    if keep.all():
        return discs
    return a[keep]


def ghost_install() -> None:
    """env_v2.world 의 원판 함수를 감싼다 (프로세스마다 한 번, 떨굴 원판이 없으면 그대로 부른다 — 비트 단위로 같다)."""
    if _GHOST_ON[0]:
        return
    import env_v2.world as W

    o_slide, o_detour, o_inside, o_push = W.obstacle_slide, W.detour_moves, W.obstacle_inside, W.obstacle_push_out
    o_obs, o_route, o_seg = W.obstacle_obs_values, W.flight_route_geometry, W.World._ob_seg_blocked

    def slide(p, q, discs, body_r, size=None):
        return o_slide(p, q, _drop(discs, "move"), body_r, size)

    def detour(p, v, left, side, steps, discs, body_r, size, deer, dp, walls=None, wall_sel=None):
        return o_detour(p, v, left, side, steps, _drop(discs, "move"), body_r, size, deer, dp, walls, wall_sel)

    def inside(q, discs, body_r):
        return o_inside(q, _drop(discs, "move"), body_r)

    def push(q, discs, body_r, size, walls=None):
        return o_push(q, _drop(discs, "move"), body_r, size, walls)

    def obsv(p, head, seen, away, threat, discs, *a, **k):
        return o_obs(p, head, seen, away, threat, _drop(discs, "obs"), *a, **k)

    def route(p, a0, q, S, dist, cov_c, cov_r, discs, *a, **k):
        return o_route(p, a0, q, S, dist, cov_c, cov_r, _drop(discs, "sight"), *a, **k)

    def seg(self, a, b):
        if not _GHOST["sight"]:
            return o_seg(self, a, b)
        full = self.obstacles
        self.obstacles = _drop(full, "sight")
        try:
            return o_seg(self, a, b)
        finally:
            self.obstacles = full

    W.obstacle_slide, W.detour_moves, W.obstacle_inside, W.obstacle_push_out = slide, detour, inside, push
    W.obstacle_obs_values, W.flight_route_geometry = obsv, route
    W.World._ob_seg_blocked = seg
    _GHOST_ON[0] = True


class ghost_scope:
    """with ghost_scope(job['paths']): … — 그 동안 길마다 새 나무를 떨군다 (paths 가 None 이면 아무것도 바꾸지 않는다)."""

    def __init__(self, paths):
        self.paths = paths

    def __enter__(self):
        if self.paths:
            ghost_install()
            for k in ("move", "sight", "obs"):
                _GHOST[k] = {tuple(map(float, d)) for d in self.paths["drop"][k]} or None
        return self

    def __exit__(self, *exc):
        for k in _GHOST:
            _GHOST[k] = None
        return False


# --------------------------------------------------------------------- #
# 파이썬 실행기 (run_mirror.run_world 와 같은 차례 + 진단 + 탐침)
# --------------------------------------------------------------------- #


class Probe:
    """행동이 '어떻게' 바뀌나 — 스텝 뒤 상태만 읽는다 (동역학과 무관). 산 사슴-스텝(스텝 첫머리에 산 사슴) 단위."""

    def __init__(self, w, real_discs: np.ndarray, maps: bool = False):
        from env_v2.world import WF_PANIC

        self.WF_PANIC = WF_PANIC
        self.mg = int(round(float(w.size) / MAP_CELL)) if maps else 0
        self.maps = {k: np.zeros(self.mg * self.mg, dtype=np.int64) for k in MAPS} if maps else None
        self._on = None
        self.names = list(w.obs_names)
        self.track = [n for n in OBS_TRACK if n in self.names]
        self.idx = [self.names.index(n) for n in self.track]
        self.i_pc = self.names.index("pred_count")
        self.disc = np.asarray(real_discs, dtype=np.float64).reshape(-1, 3)
        self.live_n = 0
        self.moved = np.zeros(5)
        self.moved_n = np.zeros(5, dtype=np.int64)
        self.trunk_sum, self.trunk_n, self.trunk_hist = 0.0, 0, np.zeros(len(TRUNK_BINS) - 1, dtype=np.int64)
        self.sh_sum, self.sh_out, self.sh_hist = 0.0, 0, np.zeros(len(SHELTER_BINS) - 1, dtype=np.int64)
        self.obs_sum = np.zeros(len(self.track))
        self.obs_aware_sum = np.zeros(len(self.track))
        self.aware_n = 0
        self.obs_hist = np.zeros((len(self.track), OBS_BINS), dtype=np.int64)
        self.obs_aware_hist = np.zeros((len(self.track), OBS_BINS), dtype=np.int64)
        self.new_tgt = np.zeros(2, dtype=np.int64)            # [추격형, 잠행형] 늑대가 새 표적을 잡은 수
        self.new_tgt_aware = np.zeros(2, dtype=np.int64)      # 그 가운데 그 사슴이 그 늑대를 이미 알던(지난 관측의 알아챔 — 눈 또는 귀) 수
        self.new_tgt_aware_any = np.zeros(2, dtype=np.int64)  # 그 사슴이 어떤 늑대든 알던 수
        self.onset_n = np.zeros(2, dtype=np.int64)            # 도주 반사(덮기 PANIC) 시작 — 가장 가까운 깬 늑대 [추격형, 잠행형]
        self.onset_d = np.zeros(2)
        self.onset_hist = np.zeros(len(ONSET_BINS) - 1, dtype=np.int64)
        self.onset_none = 0

    def before(self, w) -> None:
        self.p0 = np.array(w.pos, copy=True)
        g = getattr(w, "_g", None) or {}
        pv = g.get("wf_pvis")
        self.pv0 = None if pv is None else np.array(pv, copy=True)
        tg = getattr(w, "pred_target", None)
        self.tg0 = np.full(w.M, -1, dtype=np.int64) if tg is None or len(tg) != w.M else np.array(tg, copy=True)
        self.wf0 = None if getattr(w, "_wf", None) is None else np.array(w.wf_mode, copy=True)
        if self.maps is not None:
            self.cov0 = np.asarray(w._in_cover(w.pos), dtype=bool).copy()

    def _cells(self, P: np.ndarray) -> np.ndarray:
        P = np.asarray(P, dtype=np.float64).reshape(-1, 2)
        ix = np.clip(np.floor(P[:, 0] / MAP_CELL).astype(np.int64), 0, self.mg - 1)
        iy = np.clip(np.floor(P[:, 1] / MAP_CELL).astype(np.int64), 0, self.mg - 1)
        return iy * self.mg + ix

    def _add(self, name: str, P) -> None:
        P = np.asarray(P, dtype=np.float64).reshape(-1, 2)
        if len(P):
            self.maps[name] += np.bincount(self._cells(P), minlength=self.mg * self.mg)

    def _map_after(self, w, L: np.ndarray) -> None:
        """공간 지도 (MAPS) — 스텝 뒤 상태만 읽는다. L = 스텝 첫머리에 산 사슴."""
        pos = np.asarray(w.pos)
        beh = np.asarray(w._rs.behavior).astype(np.int64)
        self._add("deer", pos[L])
        for i, nm in enumerate(("graze", "flee", "hide")):
            self._add(nm, pos[L & (beh == i)])
        tgt = np.zeros(w.N, dtype=bool)
        tg = getattr(w, "pred_target", None)
        tg = np.asarray(tg) if tg is not None and len(tg) == w.M else np.full(w.M, -1, dtype=np.int64)
        tv = tg[(tg >= 0) & (tg < w.N)]
        tgt[tv] = True
        self._add("chased_flee", pos[L & (beh == 1) & tgt])
        if self._on is not None:
            self._add("onset", pos[self._on])
        if w.M and len(self.tg0) == w.M:
            ppos = np.asarray(w.pred_pos)
            wolf = ~np.asarray(getattr(w, "pred_is_player", np.zeros(w.M, dtype=bool)), dtype=bool)
            new = wolf & (tg >= 0) & (tg != self.tg0)
            if new.any():
                self._add("spot_deer", pos[tg[new]])
                self._add("spot_wolf", ppos[new])
            alive = np.asarray(w.alive, dtype=bool) if w.alive is not None else np.ones(w.N, dtype=bool)
            had = wolf & (self.tg0 >= 0) & (self.tg0 < w.N) & (tg != self.tg0)
            if had.any():
                i0 = self.tg0[had]
                self._add("lost", pos[i0[alive[i0]]])
            asleep = np.asarray(getattr(w, "pred_asleep", np.zeros(w.M, dtype=bool)), dtype=bool)
            self._add("wolf_sleep", ppos[wolf & asleep])
            self._add("wolf_hunt", ppos[wolf & ~asleep & (tg >= 0)])
            self._add("wolf_idle", ppos[wolf & ~asleep & (tg < 0)])
        inc = np.asarray(w._in_cover(pos), dtype=bool)
        ent = L & ~self.cov0 & inc
        self._add("enter", self.p0[ent])
        self._add("enter_fled", self.p0[ent & (beh == 1)])
        if w.alive is not None:
            died = L & ~np.asarray(w.alive, dtype=bool) & (np.asarray(w.death_cause) == 1)
            self._add("caught", pos[died])

    def after(self, w, live_before: np.ndarray) -> None:
        L = np.asarray(live_before, dtype=bool)
        self._on = None
        nL = int(L.sum())
        if not nL:
            if self.maps is not None:
                self._map_after(w, L)
            return
        self.live_n += nL
        P = np.asarray(w.pos)[L]
        mv = np.sqrt(((P - self.p0[L]) ** 2).sum(1))
        beh = np.asarray(w._rs.behavior)[L].astype(np.int64)
        self.moved += np.bincount(beh, weights=mv, minlength=5)[:5]
        self.moved_n += np.bincount(beh, minlength=5)[:5]
        if len(self.disc):
            dt = (np.sqrt(((P[:, None, :] - self.disc[None, :, :2]) ** 2).sum(-1)) - self.disc[None, :, 2]).min(1)
            self.trunk_sum += float(dt.sum())
            self.trunk_n += nL
            self.trunk_hist += np.histogram(dt, bins=TRUNK_BINS)[0]
        if len(w.cov_r):
            ds = (np.sqrt(((P[:, None, :] - np.asarray(w.cov_c)[None, :, :]) ** 2).sum(-1)) - np.asarray(w.cov_r)[None, :]).min(1)
            self.sh_hist += np.histogram(ds, bins=SHELTER_BINS)[0]
            out = ds > 0.0
            self.sh_sum += float(ds[out].sum())
            self.sh_out += int(out.sum())
        O = np.asarray(w._obs, dtype=np.float64)[L]
        if self.idx:
            V = O[:, self.idx]
            self.obs_sum += V.sum(0)
            B = np.clip((V * OBS_BINS).astype(np.int64), 0, OBS_BINS - 1)
            for k in range(len(self.idx)):
                self.obs_hist[k] += np.bincount(B[:, k], minlength=OBS_BINS)
            aw = O[:, self.i_pc] > 0.0
            if aw.any():
                self.aware_n += int(aw.sum())
                self.obs_aware_sum += V[aw].sum(0)
                for k in range(len(self.idx)):
                    self.obs_aware_hist[k] += np.bincount(B[aw, k], minlength=OBS_BINS)
        if w.M:
            from env_v2.world import PT_STALKER

            kind = (np.asarray(w.pred_type) == PT_STALKER).astype(np.int64)
            tg = getattr(w, "pred_target", None)
            if tg is not None and len(tg) == w.M:
                tg = np.asarray(tg)
                new = (tg >= 0) & (tg != self.tg0)
                for m in np.flatnonzero(new):
                    i, k = int(tg[m]), int(kind[m])
                    self.new_tgt[k] += 1
                    if self.pv0 is not None and self.pv0.shape == (w.N, w.M):
                        self.new_tgt_aware[k] += int(bool(self.pv0[i, m]))
                        self.new_tgt_aware_any[k] += int(bool(self.pv0[i].any()))
            if self.wf0 is not None:
                on = L & (np.asarray(w.wf_mode) == self.WF_PANIC) & (self.wf0 != self.WF_PANIC)
                self._on = on
                if on.any():
                    awake = ~np.asarray(w.pred_asleep, dtype=bool)
                    pos = np.asarray(w.pos)[on]
                    if awake.any():
                        d = np.sqrt(((pos[:, None, :] - np.asarray(w.pred_pos)[None, awake, :]) ** 2).sum(-1))
                        j = d.argmin(1)
                        dm = d[np.arange(len(pos)), j]
                        kk = kind[np.flatnonzero(awake)[j]]
                        np.add.at(self.onset_n, kk, 1)
                        np.add.at(self.onset_d, kk, dm)
                        self.onset_hist += np.histogram(dm, bins=ONSET_BINS)[0]
                    else:
                        self.onset_none += int(on.sum())
        if self.maps is not None:
            self._map_after(w, L)

    def result(self) -> dict:
        mp = {} if self.maps is None else dict(maps=dict(cell=MAP_CELL, g=self.mg, counts={k: v.tolist() for k, v in self.maps.items()}))
        return dict(**mp, live_n=self.live_n, moved=self.moved.tolist(), moved_n=self.moved_n.tolist(),
                    trunk_sum=self.trunk_sum, trunk_n=self.trunk_n, trunk_hist=self.trunk_hist.tolist(), trunk_discs=int(len(self.disc)),
                    shelter_sum=self.sh_sum, shelter_out=self.sh_out, shelter_hist=self.sh_hist.tolist(),
                    obs_names=self.track, obs_sum=self.obs_sum.tolist(), obs_aware_sum=self.obs_aware_sum.tolist(), aware_n=self.aware_n,
                    obs_hist=self.obs_hist.tolist(), obs_aware_hist=self.obs_aware_hist.tolist(),
                    new_tgt=self.new_tgt.tolist(), new_tgt_aware=self.new_tgt_aware.tolist(), new_tgt_aware_any=self.new_tgt_aware_any.tolist(),
                    onset_n=self.onset_n.tolist(), onset_d=self.onset_d.tolist(), onset_hist=self.onset_hist.tolist(), onset_none=self.onset_none,
                    bins=dict(trunk=list(TRUNK_BINS), shelter=list(SHELTER_BINS), onset=list(ONSET_BINS), obs=OBS_BINS))


def py_world(job: dict) -> dict:
    """파이썬 세계 하나: run_mirror.run_world(진단 켬)와 같은 차례로 job['steps'] 스텝 → live._world_multi 와 같은 칸 + py(탐침·obstacle·pack·weather).
    job['paths'] 가 있으면 길 떼어 보기 감싸기를 건다."""
    from env_v2 import rollout as ro

    import ceval
    import run_mirror as rm

    with ghost_scope(job.get("paths")):
        t0 = time.perf_counter()
        w = ceval.make_world(job)                                   # World + 스냅숏 먹이 지도 (평가기·거울 실행기와 같다)
        fl_on = getattr(w, "_wf", None) is not None
        if fl_on:
            w.track_flight = True
        H = int(job["steps"])
        w.keep_pair_vis = True
        w._g = w._geometry()
        w._obs = w._obs_from(w._g)
        dg = rm._Diag(w)
        real = [d for d in np.asarray(w.obstacles, dtype=np.float64).reshape(-1, 3).tolist() if tuple(d) != GATE_DISC]
        pr = Probe(w, np.asarray(real).reshape(-1, 3), maps=bool(job.get("maps")))
        pol = ro.build_policy({"kind": "rep_learned", "path": str(job["model"])}, int(job["seed"]))
        ro.forward_bind(pol, w)
        shelter = [0, 0]
        for _ in range(H):
            live_before = w.alive
            alive_before = int(live_before.sum())
            pr.before(w)
            w.step(np.asarray(pol(w.observe()), dtype=np.float64))
            shelter[0] += int(np.count_nonzero(live_before & w._in_cover(w.pos)))
            shelter[1] += alive_before
            dg.after(w, live_before)
            pr.after(w, live_before)
        d = dg.result(w)
        cause, dt = np.asarray(w.death_cause), np.asarray(w.death_t)
        hunt = {k: (None if isinstance(v, float) and v != v else v) for k, v in w.hunt_stats().items()}
        out = dict(seed=int(job["seed"]), region=job["region"], n=int(w.N), caught=int((cause == 1).sum()), starved=int((cause == 2).sum()),
                   alive=int((cause == 0).sum()), shelter_steps=int(shelter[0]), live_steps=int(shelter[1]), beh_steps=d["beh_steps"],
                   catch_cover=d["catch_cover"], hunt=hunt, wall_s=round(time.perf_counter() - t0, 3))
        if fl_on:
            out["flight"] = w.flight_stats()
        out["at"] = {str(H): dict(caught=int(((cause == 1) & (dt <= H)).sum()), starved=int(((cause == 2) & (dt <= H)).sum()),
                                  alive=int(((cause == 0) | (dt > H)).sum()))}
        if fl_on:
            out["at"][str(H)]["flight"] = out["flight"]
        py = dict(probe=pr.result(), diag={k: d[k] for k in ("catch_fled", "catch_saw", "catches", "panic_ends", "panic_end_awake", "heard_live",
                                                             "live_obs", "catch_ring", "occ_edge", "occ_n") if k in d})
        if getattr(w, "_ob", None) is not None:
            py["obstacles"] = w.obstacle_stats()
        if getattr(w, "_wp", None) is not None:
            py["pack"] = w.pack_stats()
        if getattr(w, "_wx", None) is not None:
            py["weather"] = w.weather_stats()
        out["py"] = py
        return out


def _py_item(item):
    kind, tag, job = item
    if kind == "multi":
        return tag, py_world(job)
    if kind == "stuck":
        import adapt as ad

        with ghost_scope(job.get("paths")):
            return tag, ad._stuck_one(job)
    raise ValueError(kind)


def run_python(items: list, workers: int, on_done=None) -> list:
    from env_v2 import rollout as ro

    ex = ro.make_executor(min(int(workers), len(items)))
    if ex is None:
        out = []
        for it in items:
            out.append(_py_item(copy.deepcopy(it)))
            if on_done:
                on_done()
        return out
    from concurrent.futures import as_completed

    with ex:
        futs = {ex.submit(_py_item, it): k for k, it in enumerate(items)}
        out = [None] * len(items)
        for f in as_completed(futs):
            out[futs[f]] = f.result()
            if on_done:
                on_done()
    return out


def run_ceval(items: list, workers: int, on_done=None) -> tuple[list, dict]:
    import ceval

    if any(it[2].get("paths") for it in items):
        raise SystemExit("길 떼어 보기(paths) 세계는 평가기가 받지 않는다 — --runner python")
    pool = ceval.Pool(workers)
    out = pool.run(items, on_done)
    for (kind, tag, job), (t2, r) in zip(items, out):
        if t2 != tag or int(r["seed"]) != int(job["seed"]) or r["region"] != job["region"]:
            raise SystemExit("평가기 결과가 일과 맞지 않는다")
    return out, dict(pool.timing)


# --------------------------------------------------------------------- #
# 명령: list · run
# --------------------------------------------------------------------- #


def run_dir(out: Path, base: str, brain: str, world: str, horizon: int) -> Path:
    return Path(out) / f"{base}_{brain}_{world}_h{int(horizon)}"


def _reg_suffix(regions) -> str:
    return "" if not regions else "__R-" + "-".join(sorted(regions))


def raw_path(d: Path, variant: str, runner: str, regions=None) -> Path:
    """기록 파일. regions(일부 지역만 돌린 판)를 주면 이름에 __R-<지역…> 이 붙는다."""
    return Path(d) / f"{safe_name(variant)}__{runner}{_reg_suffix(regions)}.json.gz"


def maps_path(d: Path, variant: str, regions=None) -> Path:
    return Path(d) / f"{safe_name(variant)}__maps{_reg_suffix(regions)}.json.gz"


def _partial_files(d: Path, variant: str, kind: str) -> list:
    """일부 지역 판 파일 [(경로, 지역 집합)] (kind = 실행기 이름 또는 maps)."""
    out = []
    for q in sorted(Path(d).glob(f"{safe_name(variant)}__{kind}__R-*.json.gz")):
        out.append((q, set(q.name[: -len(".json.gz")].split("__R-", 1)[1].split("-"))))
    return out


def cmd_list(a) -> int:
    print("두뇌:", "; ".join(f"{k} = {v['label']}" for k, v in BRAINS.items()))
    print("바탕:", "; ".join(f"{k} = {v['label']}" for k, v in BASES.items()))
    print("변형 이름표:")
    for k, v in PRESETS.items():
        print(f"  {k:<12} {v or '(바꿈 없음)'}{'   [파이썬 전용]' if 'paths:' in v else ''}")
    if not a.variants:
        return 0
    prep = Path(a.out) / "prep"
    info = prepare(a.base, a.brain, prep)
    seeds = parse_seeds(a.seeds)[:1]
    for v in a.variants:
        var = parse_variant(v)
        _, vrec = build_items(info, info["model"], seeds, 1, "N", var, a.region)
        print(f"\n[{v}] {var['spec'] or '(바꿈 없음)'}")
        for r, x in vrec.items():
            print(f"  {r}: " + " · ".join(x["notes"]))
            for c in x["checks"]["items"]:
                print(f"    검사 {c}")
            print(f"    평가기: {x['checks']['ceval']}")
            for pmeta in x["place"]:
                s = pmeta["summary"]
                if not s.get("n"):
                    print(f"    자리 {pmeta['place']}: 놓은 그루 없음")
                    continue
                print(f"    자리 {pmeta['place']}: 은신처 가장자리까지 {s['shelter_edge_m']['mean']:.1f} m (최소 {s['shelter_edge_m']['min']:.1f}), 벽까지 "
                      f"{s['wall_m']['mean']:.1f} m, 그 셀 먹이 용량 평균 {s['cell_cap_mean']:.4f} (지역 {s['region_cap_mean']:.4f})"
                      + (f", 가장 가까운 줄기 {s['nn_m']['mean']:.1f} m" if s.get("nn_m") else "")
                      + (f", 덩어리 중심 {pmeta.get('center')} 반지름 {pmeta.get('r_end')}" if pmeta["place"] == "clump" else "")
                      + (f", 게임 좌표 중심 {pmeta.get('center_game_cm')} cm" if pmeta["place"] == "spot" else ""))
    return 0


def choose_runner(var: dict, want: str) -> str:
    if want == "auto":
        return "python" if var["python_only"] else "ceval"
    if want == "ceval" and var["python_only"]:
        raise SystemExit(f"변형 {var['name']} 은 길 떼어 보기라 파이썬 실행기만 돈다 (--runner python)")
    return want


def _covers_discs(info: dict, vrec: dict, region: str) -> tuple[list, list]:
    """지도 파일에 적을 그 지역 은신처·원판(문지기 빼고): 바꾼 지역은 변형 세계(검사가 읽은 은신처, 바탕 원판 + 새 나무), 아니면 바탕."""
    reg = info["regions"][region]
    discs = [list(map(float, d)) for d in reg.get("discs") or []]
    covers = [list(map(float, c)) for c in reg["covers"]]
    if region in vrec:
        covers = vrec[region]["checks"].get("covers", covers)
        discs = discs + [list(map(float, d)) for d in vrec[region]["new_trees"]]
    return covers, discs


def save_maps(path: Path, recs: list, meta: dict, info: dict, vrec: dict) -> dict:
    """세계 기록의 py.probe.maps 를 지역마다 더해(all·시드 짝수 even) 따로 저장하고 기록에서는 뺀다(기록 크기). 반환 지도 파일 내용."""
    by: dict = {}
    for r in recs:
        m = (r.get("py") or {}).get("probe", {}).pop("maps", None)
        if m is None:
            continue
        reg = by.setdefault(r["region"], dict(cell=m["cell"], g=m["g"], worlds=0, seeds=[], all={}, even={}))
        reg["worlds"] += 1
        reg["seeds"].append(int(r["seed"]))
        for k, v in m["counts"].items():
            a = np.asarray(v, dtype=np.int64)
            reg["all"][k] = reg["all"].get(k, 0) + a
            if int(r["seed"]) % 2 == 0:
                reg["even"][k] = reg["even"].get(k, 0) + a
    for rn, reg in by.items():
        reg["seeds"] = [min(reg["seeds"]), max(reg["seeds"]), len(reg["seeds"])]
        for part in ("all", "even"):
            reg[part] = {k: np.asarray(v).tolist() for k, v in reg[part].items()}
        reg["covers"], reg["discs"] = _covers_discs(info, vrec, rn)
        reg["origin_cm"] = (info.get("origin_cm") or {}).get(rn)
        reg["region_index"] = int(info["regions"][rn]["region_index"])
        reg["size"] = float(reg["g"] * reg["cell"])
    d = dict(meta=dict(meta, made_by="level_sense/sense.py run --maps", labels=MAPS), regions=by)
    json_dump_gz(path, d)
    return d


def run_variants(a, variants: list) -> dict:
    """변형마다 돌려 기록을 쓴다 (cmd_run·cmd_scan). 반환 {변형: 기록 경로}. a = run 인자 (seeds·horizon·workers·out·base·brain·world·runner·region·
    regions·maps·force·stuck·stuck_horizon)."""
    seeds = parse_seeds(a.seeds)
    H = int(a.horizon)
    W = int(a.workers)
    if W > 6:
        raise SystemExit("워커는 6 이하 (다른 일과 CPU 를 나눈다)")
    d = run_dir(Path(a.out), a.base, a.brain, a.world, H)
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    info = prepare(a.base, a.brain, Path(a.out) / "prep")
    t_prep0 = time.perf_counter() - t0
    regs_all = list(info["regions"])
    regions_run = [r for r in regs_all if r in set(a.regions)] if getattr(a, "regions", None) else None
    if regions_run is not None and (not regions_run or len(regions_run) != len(set(a.regions))):
        raise SystemExit(f"--regions {a.regions} 가운데 없는 지역이 있다 ({', '.join(regs_all)})")
    if regions_run == regs_all:
        regions_run = None
    maps = bool(getattr(a, "maps", False))
    print(f"바탕 {a.base} ({BASES[a.base]['label']}), 두뇌 {a.brain} ({info['record']['anchor']}), 세계 {a.world}, 길이 {H} 스텝, 시드 {seeds[0]}~{seeds[-1]} "
          f"({len(seeds)}), 지역 {regions_run or regs_all}, 워커 {W}, 변환 {t_prep0:.1f} 초" + (", 공간 지도 켬" if maps else "") + f" -> {d}", flush=True)
    paths: dict = {}
    for v in variants:
        var = parse_variant(v)
        runner = choose_runner(var, a.runner)
        if maps and runner != "python":
            if a.runner == "auto":
                runner = "python"
            else:
                raise SystemExit("공간 지도(--maps)는 파이썬 실행기만 낸다 (--runner python 또는 auto)")
        rp = raw_path(d, v, runner, regions_run)
        full = raw_path(d, v, runner)
        have = full if full.exists() else rp if rp.exists() else None
        if have is not None and not a.force and (not maps or maps_path(d, v, None if have == full else regions_run).exists()):
            print(f"[{v}] {have.name} 이 있다 — 건너뜀 (--force 로 다시)", flush=True)
            paths[v] = have
            continue
        t1 = time.perf_counter()
        items, vrec = build_items(info, info["model"], seeds, H, a.world, var, a.region, regions_run=regions_run)
        if maps:
            for it in items:
                it[2]["maps"] = True
        t_build = time.perf_counter() - t1
        for r, x in vrec.items():
            print(f"[{v}] {r}: " + " · ".join(x["notes"]) + f" — 검사 {len(x['checks']['items'])} 통과, 평가기 {x['checks']['ceval']}", flush=True)
        done = [0]

        def tick():
            done[0] += 1
            if done[0] % 60 == 0:
                print(f"  {done[0]}/{len(items)} ({time.perf_counter() - t2:.0f} 초)", flush=True)

        t2 = time.perf_counter()
        timing: dict = {}
        if runner == "ceval":
            out, timing = run_ceval(items, W, tick)
        else:
            out = run_python(items, W, tick)
        t_run = time.perf_counter() - t2
        recs = [r for _, r in out]
        meta = dict(made_by="level_sense/sense.py run", variant=v, spec=var["spec"], edits=var["edits"], runner=runner, base=a.base, brain=a.brain,
                    brain_label=BRAINS[a.brain]["label"], model=info["record"]["anchor"], world=a.world, horizon=H, seeds=[seeds[0], seeds[-1], len(seeds)],
                    regions=regions_run or regs_all, regions_all=regs_all, target_region=a.region, workers=W, snapshot_sha256=info["snapshot_sha256"],
                    variant_regions=vrec, origin_cm=info.get("origin_cm"),
                    time=dict(build_s=round(t_build, 2), run_s=round(t_run, 2), worlds=len(items), native=timing,
                              world_steps_per_s_total=round(len(items) * H / t_run, 1) if t_run > 0 else None),
                    when=time.strftime("%Y-%m-%dT%H:%M:%S"))
        if maps:
            mp = maps_path(d, v, regions_run)
            save_maps(mp, recs, {k: meta[k] for k in ("variant", "spec", "base", "brain", "world", "horizon", "seeds", "regions")}, info, vrec)
            print(f"[{v}] 공간 지도 -> {mp.name}", flush=True)
        json_dump_gz(rp, dict(meta=meta, worlds=recs))
        paths[v] = rp
        pooled = pooled_summary(recs, H)
        tgt = [r for r in recs if r["region"] == a.region]
        pt = pooled_summary(tgt, H) if tgt else None
        print(f"[{v}] {runner}: 세계 {len(items)} × {H} 스텝 — 만들기 {t_build:.1f} 초 + 돌리기 {t_run:.1f} 초 ({t_run / 60:.2f} 분). "
              f"사건 숨음 비율 {pooled['ep_hide'] * 100:.2f}% · 사건 잡힘 {pooled['ep_caught'] * 100:.2f}% · 잡힌 몫 {pooled['caught'] * 100:.2f}% -> {rp.name}",
              flush=True)
        if pt:
            print(f"[{v}] {a.region} 나무 덕 칸: 쫓긴 도망 가운데 줄기에 가려 끝남 {pt['obstacle_of_chased'] * 100:.2f}% · 쫓긴 사건 가운데 잡힘 "
                  f"{pt['ep_caught'] * 100:.2f}% · 늑대 사냥 성공률 {pt['hunt_success'] * 100:.1f}% · 사건 숨음 비율 {pt['ep_hide'] * 100:.2f}%", flush=True)
        if a.stuck:
            sk = seeds[: int(a.stuck)]
            t3 = time.perf_counter()
            sitems, _ = build_items(info, info["model"], sk, int(a.stuck_horizon), "G", var, a.region, kind="stuck", regions_run=regions_run)
            sout = run_python(sitems, W)
            sp = Path(d) / f"{safe_name(v)}__stuck{_reg_suffix(regions_run)}.json.gz"
            json_dump_gz(sp, dict(meta=dict(variant=v, spec=var["spec"], world="G", horizon=int(a.stuck_horizon), seeds=sk, regions=regions_run or regs_all,
                                            wall_s=round(time.perf_counter() - t3, 1)), worlds=[r for _, r in sout]))
            print(f"[{v}] 끼임 (G {a.stuck_horizon} 스텝, 시드 {len(sk)}): 사슴 {sum(len(r.get('deer_events', [])) for _, r in sout)}"
                  f"·늑대 {sum(len(r.get('wolf_events', [])) for _, r in sout)} ({time.perf_counter() - t3:.0f} 초) -> {sp.name}", flush=True)
    return paths


def cmd_run(a) -> int:
    run_variants(a, a.variants)
    return 0


def pooled_summary(recs: list, H: int) -> dict:
    """세계 합 (전체 합의 비율 — 보고용): 사건 숨음·잡힘 비율, 잡힌 몫, 나무 덕 칸(쫓긴 도망 가운데 줄기에 가려 끝남·늑대 사냥 성공률)."""
    ep = dict(chased=0, hidden=0, caught=0)
    n = c = obs = chased = hs = he = 0
    for r in recs:
        at = r["at"][str(H)]
        f = at["flight"]
        e = f["episode"]
        for k in ep:
            ep[k] += int(e[k])
        n += int(r["n"])
        c += int(at["caught"])
        obs += int(f["n"].get("obstacle", 0))
        chased += int(f["hide"]["chased"])
        hs += int(r["hunt"]["success"])
        he += int(r["hunt"]["ends"])
    return dict(ep_hide=ep["hidden"] / max(ep["chased"], 1), ep_caught=ep["caught"] / max(ep["chased"], 1), caught=c / max(n, 1),
                ep_chased=ep["chased"], ep_hidden=ep["hidden"], obstacle_of_chased=obs / max(chased, 1), hunt_success=hs / max(he, 1))


# --------------------------------------------------------------------- #
# 지표·표
# --------------------------------------------------------------------- #

REASONS = ("cover", "obstacle", "fov", "range", "switch", "stop", "held", "unchased", "caught", "starved", "truncated")   # env_v2 FLIGHT_CAUSES
BEH = ("graze", "flee", "hide", "freeze", "sleep")


def _F(r, H):
    at = r.get("at", {}).get(str(H))
    return (at or {}).get("flight") or r.get("flight") or {}


def _A(r, H):
    return r.get("at", {}).get(str(H)) or r


def _route(r, H):
    return _F(r, H).get("route") or {}


def _sum(d):
    return float(sum(int(v) for v in (d or {}).values()))


def _metrics() -> list:
    """(이름, 뜻, fn(기록, H) → (분자, 분모), 필요 'any'|'python'). 시드마다 고른 지역의 분자·분모를 각각 더한 뒤 나눈다."""
    M = []

    def add(name, label, fn, need="any"):
        M.append((name, label, fn, need))

    add("ep_hide", "사건 숨음 비율 (1차 P1)", lambda r, H: (_F(r, H)["episode"]["hidden"], _F(r, H)["episode"]["chased"]))
    add("ep_caught", "사건 잡힘 비율 (GH)", lambda r, H: (_F(r, H)["episode"]["caught"], _F(r, H)["episode"]["chased"]))
    add("ep_chased_n", "쫓긴 사건 수", lambda r, H: (_F(r, H)["episode"]["chased"], 1))
    add("ep_hidden_n", "숨음 사건 수", lambda r, H: (_F(r, H)["episode"]["hidden"], 1))
    add("ep_other_chased_n", "쫓긴 사건 가운데 숨음·잡힘·굶음 밖으로 끝난 수", lambda r, H: (_F(r, H)["episode"]["other_chased"], 1))
    add("ep_start_1k", "사건 시작 /1000 산 사슴-스텝 (GE)", lambda r, H: (1000.0 * _F(r, H)["episode"]["started"], _F(r, H)["live_steps"]))
    add("fl_start_1k", "도망 시작 /1000 산 사슴-스텝 (GF)", lambda r, H: (1000.0 * _F(r, H)["started"], _F(r, H)["live_steps"]))
    add("flee_share", "달린 시간 몫 FLEE (GV)", lambda r, H: (_F(r, H)["flee_steps"], _F(r, H)["live_steps"]))
    for i, b in enumerate(BEH):
        add(f"beh_{b}", f"실행 행동 몫 {b}", (lambda i: lambda r, H: (r["beh_steps"][i], r["live_steps"]))(i))
    add("in_shelter", "은신처 원 안 몫", lambda r, H: (r["shelter_steps"], r["live_steps"]))
    for rs in REASONS:
        add(f"end_{rs}", f"도망 끝 까닭 몫 {rs}", (lambda rs: lambda r, H: (_F(r, H)["n"].get(rs, 0), _sum(_F(r, H)["n"])))(rs))
    add("flight_len_s", "도망 한 번 길이 초", lambda r, H: (_sum(_F(r, H)["steps"]) * STEP_S, _sum(_F(r, H)["n"])))
    add("chase_own_s", "스스로 벗어난 도망의 쫓긴 초", lambda r, H: (_F(r, H)["own_contact"] * STEP_S, _F(r, H)["own_n"]))
    add("chased_flight_s", "쫓긴 도망 하나의 쫓긴 초", lambda r, H: (_sum(_F(r, H)["contact"]) * STEP_S, _F(r, H)["hide"]["chased"]))
    add("contact_share", "쫓기는 산 사슴-스텝 몫", lambda r, H: (_sum(_F(r, H)["contact"]), _F(r, H)["live_steps"]))
    add("shelter_end_share", "은신처 원 안에서 끝난 도망 몫", lambda r, H: (_F(r, H)["shelter_end"], _sum(_F(r, H)["n"])))
    add("fl_hide", "도망 단위 숨음 비율", lambda r, H: (_F(r, H)["hide"]["hidden"], _F(r, H)["hide"]["chased"]))
    add("arrive_cover_n", "은신처로 끝난 도망 수 (cover)", lambda r, H: (_F(r, H)["n"].get("cover", 0), 1))
    add("cover_then_caught", "은신처로 끝난 뒤 10 초 안 잡힘 몫", lambda r, H: (_F(r, H)["hide"]["cover_then_caught"], _F(r, H)["n"].get("cover", 0)))
    add("caught", "잡힌 몫", lambda r, H: (_A(r, H)["caught"], r["n"]))
    add("starved", "굶은 몫", lambda r, H: (_A(r, H)["starved"], r["n"]))
    add("alive", "산 몫", lambda r, H: (_A(r, H)["alive"], r["n"]))
    add("catch_cover", "은신처 안 잡힘 / 잡힘", lambda r, H: (r["catch_cover"], r["caught"]))
    add("hunt_success", "늑대 사냥 성공률", lambda r, H: (r["hunt"]["success"], r["hunt"]["ends"]))
    add("hunt_starts_n", "늑대 사냥 시작 수", lambda r, H: (r["hunt"]["starts"], 1))
    add("hunt_success_stalker", "잠행형 사냥 성공률", lambda r, H: (r["hunt"].get("stalker_success", 0), r["hunt"].get("stalker_ends", 0)))
    add("hunt_success_chaser", "추격형 사냥 성공률", lambda r, H: (r["hunt"].get("chaser_success", 0), r["hunt"].get("chaser_ends", 0)))
    add("route_pick_shelter", "두 길 결정 가운데 SHELTER 고름 몫",
        lambda r, H: (_route(r, H).get("picked", {}).get("shelter", 0), _route(r, H).get("picked", {}).get("shelter", 0) + _route(r, H).get("picked", {}).get("run", 0)))
    add("route_onset_shelter", "도주 시작 때 SHELTER 가능 몫", lambda r, H: (_route(r, H).get("onset_shelter", 0), _route(r, H).get("onsets", 0)))
    add("route_invalid", "SHELTER 고른 뒤 무효 몫", lambda r, H: (_route(r, H).get("invalid", {}).get("shelter", 0), _route(r, H).get("picked", {}).get("shelter", 0)))
    add("route_shelter_steps", "도주 스텝 가운데 SHELTER 길 몫",
        lambda r, H: (_route(r, H).get("steps", {}).get("shelter", 0), _route(r, H).get("steps", {}).get("shelter", 0) + _route(r, H).get("steps", {}).get("run", 0)))
    # 나무 덕 칸 (10-27 사용자 추가 요청 — 1차 '사건 숨음 비율'은 은신처로 끝난 사건만 세어 줄기로 벗어난 도망을 숨음으로 세지 않는다. PRIOR_EVIDENCE.md)
    add("fl_obstacle_of_chased", "쫓긴 도망 가운데 줄기에 가려 늑대가 놓쳐 끝난 몫 (끝 까닭 obstacle)",
        lambda r, H: (_F(r, H)["n"].get("obstacle", 0), _F(r, H)["hide"]["chased"]))
    add("fl_obstacle_n", "줄기에 가려 끝난 도망 수 (obstacle)", lambda r, H: (_F(r, H)["n"].get("obstacle", 0), 1))
    add("fl_cover_of_chased", "쫓긴 도망 가운데 은신처로 끝난 몫 (cover)", lambda r, H: (_F(r, H)["n"].get("cover", 0), _F(r, H)["hide"]["chased"]))
    add("fl_own_of_chased", "쫓긴 도망 가운데 스스로 벗어난 몫 (cover·obstacle·fov·range)", lambda r, H: (_F(r, H)["own_n"], _F(r, H)["hide"]["chased"]))
    add("fl_caught_of_chased", "쫓긴 도망 가운데 잡혀 끝난 몫", lambda r, H: (_F(r, H)["n"].get("caught", 0), _F(r, H)["hide"]["chased"]))
    add("ep_saved", "쫓긴 사건 가운데 안 잡히고 안 굶은 몫 (1 − 잡힘 − 굶음)",
        lambda r, H: (_F(r, H)["episode"]["chased"] - _F(r, H)["episode"]["caught"] - _F(r, H)["episode"]["starved"], _F(r, H)["episode"]["chased"]))
    add("route_drop_obstacle_n", "원판이 늑대 눈길을 가려 놓친 사건 수 (도망길 기록 — 두 길 세계)",
        lambda r, H: (float(sum((_route(r, H).get("drop_obstacle") or {}).values())), 1))
    add("route_hidden_chased", "쫓기는 FLEE 스텝 가운데 쫓는 늑대 모두에게 줄기로 가려진 몫 (두 길 세계)",
        lambda r, H: (float(sum((_route(r, H).get("hidden_steps") or {}).values())), float(sum((_route(r, H).get("chased_steps") or {}).values()))))
    # 파이썬 탐침
    P = lambda r: r["py"]["probe"]  # noqa: E731
    add("moved_m", "산 사슴-스텝당 움직인 거리 m", lambda r, H: (sum(P(r)["moved"]) * UNIT_M, sum(P(r)["moved_n"])), "python")
    for i, b in enumerate(BEH[:3]):
        add(f"moved_{b}_m", f"{b} 스텝당 움직인 거리 m", (lambda i: lambda r, H: (P(r)["moved"][i] * UNIT_M, P(r)["moved_n"][i]))(i), "python")
    add("trunk_d_m", "가장 가까운 줄기 가장자리까지 m (줄기 있는 지역)", lambda r, H: (P(r)["trunk_sum"] * UNIT_M, P(r)["trunk_n"]), "python")
    add("trunk_near2m", "줄기 2 m 안 몫", lambda r, H: (sum(P(r)["trunk_hist"][:2]), P(r)["trunk_n"]), "python")
    add("shelter_d_m", "은신처 밖 사슴의 가장 가까운 은신처 가장자리까지 m", lambda r, H: (P(r)["shelter_sum"] * UNIT_M, P(r)["shelter_out"]), "python")
    for nm in OBS_TRACK:
        add(f"obs_{nm}", f"관측 {nm} 평균 (산 사슴)", (lambda nm: lambda r, H: _obs_mean(P(r), nm, False))(nm), "python")
        add(f"obs_{nm}_aware", f"관측 {nm} 평균 (늑대를 아는 사슴)", (lambda nm: lambda r, H: _obs_mean(P(r), nm, True))(nm), "python")
    add("obs_escape_lt10m_aware", "늑대를 알 때 도망 쪽 트임 10 m 밑 몫", lambda r, H: _obs_low(P(r), "escape_room", 5, True), "python")
    add("tgt_deer_first", "늑대 새 표적 때 그 사슴이 그 늑대를 이미 앎 (사슴이 먼저)", lambda r, H: (sum(P(r)["new_tgt_aware"]), sum(P(r)["new_tgt"])), "python")
    add("tgt_deer_any", "늑대 새 표적 때 그 사슴이 어떤 늑대든 앎", lambda r, H: (sum(P(r)["new_tgt_aware_any"]), sum(P(r)["new_tgt"])), "python")
    add("new_tgt_n", "늑대 새 표적 수", lambda r, H: (sum(P(r)["new_tgt"]), 1), "python")
    add("onset_d_m", "도주 반사 시작 때 가장 가까운 깬 늑대 m", lambda r, H: (sum(P(r)["onset_d"]) * UNIT_M, sum(P(r)["onset_n"])), "python")
    add("onset_d_stalker_m", "그 늑대가 잠행형일 때 m", lambda r, H: (P(r)["onset_d"][1] * UNIT_M, P(r)["onset_n"][1]), "python")
    add("onset_d_chaser_m", "그 늑대가 추격형일 때 m", lambda r, H: (P(r)["onset_d"][0] * UNIT_M, P(r)["onset_n"][0]), "python")
    add("onset_stalker_share", "도주 반사 시작 때 가장 가까운 깬 늑대가 잠행형인 몫", lambda r, H: (P(r)["onset_n"][1], sum(P(r)["onset_n"])), "python")
    O = lambda r: r["py"].get("obstacles") or {}  # noqa: E731
    add("deer_hit_1k", "사슴 줄기 부딪힘 /1000 사슴-스텝", lambda r, H: (1000.0 * O(r).get("deer_hit", 0), O(r).get("deer_steps", 0)), "python")
    add("deer_back_1k", "사슴 물러남(끼임 꼴) /1000", lambda r, H: (1000.0 * O(r).get("deer_back", 0), O(r).get("deer_steps", 0)), "python")
    add("wolf_hit_1k", "늑대 줄기 부딪힘 /1000 늑대-스텝", lambda r, H: (1000.0 * O(r).get("wolf_hit", 0), O(r).get("wolf_steps", 0)), "python")
    add("wolf_dead_1k", "늑대 돌아섬 /1000 늑대-스텝", lambda r, H: (1000.0 * O(r).get("wolf_dead", 0), O(r).get("wolf_steps", 0)), "python")
    add("eye_blocked", "사슴이 본 늑대 쌍 가운데 줄기가 가린 몫", lambda r, H: (O(r).get("eye_blocked", 0), O(r).get("eye_pairs", 0)), "python")
    add("tgt_blocked", "늑대가 본 사슴 쌍 가운데 줄기가 가린 몫", lambda r, H: (O(r).get("tgt_blocked", 0), O(r).get("tgt_pairs", 0)), "python")
    add("help_drop_n", "늑대 돕기 그만둠 수", lambda r, H: ((O(r).get("detour") or {}).get("help_drop", 0), 1), "python")
    add("det_deer_used_1k", "사슴 돌아가기 스텝 /1000", lambda r, H: (1000.0 * (O(r).get("detour") or {}).get("deer_used", 0), O(r).get("deer_steps", 0)), "python")
    add("pack_help_frac", "늑대 돕기 스텝 몫", lambda r, H: ((r["py"].get("pack") or {}).get("help_n", 0), (r["py"].get("pack") or {}).get("wolf_steps", 0)), "python")
    return M


def _obs_mean(p, nm, aware):
    if nm not in p["obs_names"]:
        return (0.0, 0)
    k = p["obs_names"].index(nm)
    return (p["obs_aware_sum"][k], p["aware_n"]) if aware else (p["obs_sum"][k], p["live_n"])


def _obs_low(p, nm, nbins, aware):
    if nm not in p["obs_names"]:
        return (0.0, 0)
    k = p["obs_names"].index(nm)
    h = p["obs_aware_hist" if aware else "obs_hist"][k]
    return (float(sum(h[:nbins])), float(sum(h)))


def load_raw(d: Path, variant: str, runner: str | None = None, need=None) -> dict:
    """<변형>__<실행기>.json.gz (runner None 이면 python 이 있으면 그것, 없으면 ceval). 세 지역 판이 없으면 need(지역 목록)를 모두 가진 일부 지역 판
    (<변형>__<실행기>__R-<지역…>.json.gz)을 쓴다."""
    cands = [runner] if runner else ["python", "ceval"]
    for rn in cands:
        p = raw_path(d, variant, rn)
        if p.exists():
            return json_load_gz(p)
        if need:
            for q, regs in _partial_files(d, variant, rn):
                if set(need) <= regs:
                    return json_load_gz(q)
    raise SystemExit(f"{d} 에 {variant} 기록이 없다 ({', '.join(str(raw_path(d, variant, rn).name) for rn in cands)}"
                     + (f" 또는 지역 {sorted(need)} 을 가진 __R- 판" if need else "") + ")")


def _regions_in(rec: dict) -> set:
    return {w["region"] for w in rec["worlds"]}


def seed_values(recs: list, H: int, regions, need_python: bool) -> dict:
    """지표마다 {시드: (분자 합, 분모 합)} — 고른 지역만."""
    rs = set(regions)
    out: dict = {}
    for name, _, fn, need in _metrics():
        if need == "python" and not need_python:
            continue
        acc: dict = {}
        ok = True
        for r in recs:
            if r["region"] not in rs:
                continue
            try:
                num, den = fn(r, H)
            except (KeyError, TypeError, IndexError):
                ok = False
                break
            a = acc.setdefault(int(r["seed"]), [0.0, 0.0])
            a[0] += float(num)
            a[1] = 1.0 if name.endswith("_n") else a[1] + float(den)      # '_n' 칸 = 수 (고른 지역의 합)
        if ok and acc:
            out[name] = acc
    return out


def paired(ref: dict, var: dict) -> dict | None:
    """같은 시드 짝 (변형 − 바탕): 두 쪽 모두 분모 > 0 인 시드만. 차이 평균·sd·t·표준화 크기(차이 ÷ 바탕 시드 sd)."""
    seeds = sorted(s for s in ref if s in var and ref[s][1] > 0 and var[s][1] > 0)
    if not seeds:
        vs = [var[s][0] / var[s][1] for s in sorted(var) if var[s][1] > 0]
        if not vs:
            return None
        nan = float("nan")                                  # 바탕에 없는 칸 (예: 줄기 0 그루 세계의 줄기 거리) — 변형 값만
        return dict(ref=nan, var=float(np.mean(vs)), diff=nan, sd=nan, t=nan, d=nan, sd_ref=nan, n=0, n_var=len(vs), dropped=len(var))
    a = np.array([ref[s][0] / ref[s][1] for s in seeds])
    b = np.array([var[s][0] / var[s][1] for s in seeds])
    dd = b - a
    n = len(dd)
    m = float(dd.mean())
    sd = float(dd.std(ddof=1)) if n > 1 else float("nan")
    t = m / (sd / math.sqrt(n)) if n > 1 and sd > 0 else (0.0 if m == 0 else math.copysign(math.inf, m))
    sdb = float(a.std(ddof=1)) if n > 1 else float("nan")
    return dict(ref=float(a.mean()), var=float(b.mean()), diff=m, sd=sd, t=t, d=(m / sdb if sdb and sdb > 0 else (0.0 if m == 0 else math.inf)),
                sd_ref=sdb, n=n, dropped=len(set(ref) | set(var)) - n)


METRIC_GROUPS = {
    # 나무 덕 칸: 줄기가 사슴을 돕는 길이 보이는 칸 (1차 숨음 비율은 줄기로 벗어난 도망을 숨음으로 세지 않아 나무 효과를 거꾸로 보일 수 있다)
    "tree": ["fl_obstacle_of_chased", "fl_obstacle_n", "route_drop_obstacle_n", "route_hidden_chased", "ep_caught", "ep_saved", "fl_caught_of_chased",
             "hunt_success", "hunt_starts_n", "fl_own_of_chased", "fl_cover_of_chased", "ep_hide", "ep_hidden_n", "ep_chased_n", "caught",
             "tgt_blocked", "eye_blocked", "help_drop_n", "wolf_dead_1k"],
    # 행동 칸: 사슴이 무엇을 하나
    "core": ["ep_hide", "ep_caught", "ep_chased_n", "ep_hidden_n", "fl_start_1k", "ep_start_1k", "flee_share", "beh_graze", "beh_flee", "beh_hide",
             "in_shelter", "caught", "starved", "alive", "hunt_success", "route_pick_shelter", "chased_flight_s", "flight_len_s"],
}
PCT = ({"ep_hide", "ep_caught", "flee_share", "in_shelter", "fl_hide", "cover_then_caught", "caught", "starved", "alive", "catch_cover", "hunt_success",
        "hunt_success_stalker", "hunt_success_chaser", "route_pick_shelter", "route_onset_shelter", "route_invalid", "route_shelter_steps",
        "shelter_end_share", "contact_share", "trunk_near2m", "tgt_deer_first", "tgt_deer_any", "onset_stalker_share", "eye_blocked", "tgt_blocked",
        "pack_help_frac", "obs_escape_lt10m_aware", "fl_obstacle_of_chased", "fl_cover_of_chased", "fl_own_of_chased", "fl_caught_of_chased", "ep_saved",
        "route_hidden_chased"} | {f"beh_{b}" for b in BEH} | {f"end_{r}" for r in REASONS})
RANK_METRICS = ["fl_obstacle_of_chased", "ep_caught", "ep_saved", "hunt_success", "ep_hide", "ep_hidden_n", "ep_chased_n", "caught", "beh_graze",
                "beh_hide", "flee_share", "fl_start_1k"]


def expand_only(only) -> list | None:
    """--only 의 묶음 이름(tree·core)을 칸 이름으로 편다."""
    if not only:
        return None
    out: list = []
    for x in only:
        for y in METRIC_GROUPS.get(x, [x]):
            if y not in out:
                out.append(y)
    return out


def table(d: Path, ref: str, variants: list, regions_sets: dict, runner: str | None = None, only: list | None = None) -> dict:
    need = sorted({r for regs in regions_sets.values() for r in regs})
    R = load_raw(d, ref, runner, need)
    H = int(R["meta"]["horizon"])
    only = expand_only(only)
    names = {m[0]: m for m in _metrics()}
    order = [n for n in only if n in names] if only else list(names)
    out: dict = dict(dir=str(d), ref=ref, horizon=H, ref_runner=R["meta"]["runner"], variants={}, order=order)
    for v in variants:
        V = load_raw(d, v, runner, need)
        need_py = R["meta"]["runner"] == "python" and V["meta"]["runner"] == "python"
        have = _regions_in(R) & _regions_in(V)
        vo: dict = dict(runner=V["meta"]["runner"], spec=V["meta"]["spec"], regions={}, place=_place_note(V))
        for rname, regs in regions_sets.items():
            if not set(regs) <= have:
                vo["regions"][rname] = None                 # 그 지역 세계가 한쪽 기록에 없다 (일부 지역 판)
                continue
            a = seed_values(R["worlds"], H, regs, need_py)
            b = seed_values(V["worlds"], H, regs, need_py)
            rows = {}
            for name in order:
                if name in a and name in b:
                    p = paired(a[name], b[name])
                    if p is not None:
                        rows[name] = dict(p, label=names[name][1])
            vo["regions"][rname] = rows
        out["variants"][v] = vo
    return out


def _place_note(V: dict) -> str:
    """기록 meta 의 나무 자리 요약 한 줄 (spot 은 놓은/바란 그루·중심)."""
    out = []
    for r, x in (V["meta"].get("variant_regions") or {}).items():
        for pm_ in x.get("place") or []:
            if pm_["place"] == "spot":
                out.append(f"{r} spot ({pm_['center_m'][0]:g}, {pm_['center_m'][1]:g}) m r {pm_['radius_m']:g} — {pm_['n_placed']}/{pm_['n_req']} 그루")
            else:
                out.append(f"{r} {pm_['place']} {pm_['summary'].get('n', 0)} 그루")
    return "; ".join(out)


def fmt_table(t: dict, scale: dict | None = None) -> str:
    tree = set(METRIC_GROUPS["tree"])
    lines = [f"바탕 {t['ref']} ({t['ref_runner']}), 길이 {t['horizon']} — 같은 시드 짝 (변형 − 바탕). % 칸은 %·%p, d = 차이 ÷ 바탕 시드 sd, "
             f"[나무 덕] = 줄기가 사슴을 돕는 길이 보이는 칸"]
    for v, vo in t["variants"].items():
        for rname, rows in vo["regions"].items():
            lines.append(f"\n### {v} ({vo['spec'] or '바꿈 없음'}, {vo['runner']}) — {rname}\n")
            if vo.get("place"):
                lines.append(f"나무 자리: {vo['place']}\n")
            if rows is None:
                lines.append("(이 지역 세계가 한쪽 기록에 없다 — 일부 지역 판)")
                continue
            lines.append("| 칸 | 바탕 | 변형 | 차이 | sd | t | d | n |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for name, p in rows.items():
                k = 100.0 if name in PCT else 1.0
                lab = ("[나무 덕] " if name in tree else "") + p["label"]
                if p["n"] == 0:
                    lines.append(f"| {lab} (`{name}`) | — | {p['var'] * k:.4g} | — | — | — | — | 변형만 {p.get('n_var', 0)} |")
                    continue
                lines.append(f"| {lab} (`{name}`) | {p['ref'] * k:.4g} | {p['var'] * k:.4g} | {p['diff'] * k:+.3g} | {p['sd'] * k:.3g} | {p['t']:+.2f} | "
                             f"{p['d']:+.2f} | {p['n']} |")
    return "\n".join(lines)


def cmd_table(a) -> int:
    d = Path(a.dir)
    R = load_raw(d, a.ref, a.runner, [a.region or TARGET])
    tgt = a.region or R["meta"].get("target_region", TARGET)
    regs_all = list(R["meta"].get("regions_all") or R["meta"]["regions"])
    have = _regions_in(R)
    sets = {f"{tgt}": [tgt]} if tgt in have else {}
    if set(regs_all) <= have:
        sets["세 지역 합"] = regs_all
    if not sets:
        raise SystemExit(f"바탕 기록에 지역 {tgt} 이 없다 (있는 지역 {sorted(have)})")
    t = table(d, a.ref, a.variants, sets, a.runner, a.only)
    md = fmt_table(t)
    print(md)
    if a.save:
        stem = f"table_{safe_name(a.ref)}_vs_{'_'.join(safe_name(v) for v in a.variants)}"[:150]
        (d / f"{stem}.md").write_text(md + "\n", encoding="utf-8", newline="\n")
        (d / f"{stem}.json").write_text(json.dumps(t, ensure_ascii=False, indent=1, default=_jsonable) + "\n", encoding="utf-8", newline="\n")
        print(f"\n-> {d / (stem + '.md')}")
    return 0


# --------------------------------------------------------------------- #
# 자리 찾기: rank · maps · scan
# --------------------------------------------------------------------- #


def variants_in(d: Path, pattern: str) -> list:
    """폴더의 기록 파일에서 변형 이름(파일 이름 꼴 — safe_name 은 다시 걸어도 같다)을 고른다. pattern = glob (예 'spot*')."""
    import fnmatch

    out = []
    for q in sorted(Path(d).glob("*__*.json.gz")):
        stem = q.name.split("__", 1)[0]
        kind = q.name.split("__", 2)[1].split(".")[0]
        if kind in ("ceval", "python") and fnmatch.fnmatch(stem, pattern) and stem not in out:
            out.append(stem)
    return out


def rank_rows(d: Path, ref: str, variants: list, region: str, metrics: list, runner: str | None = None) -> list:
    """변형마다 지역 하나의 같은 시드 짝 차이 (칸마다 diff·t·ref·var) + 나무 자리 요약. 표 함수 table 을 그대로 쓴다."""
    t = table(d, ref, variants, {region: [region]}, runner, metrics)
    rows = []
    for v, vo in t["variants"].items():
        V = load_raw(d, v, runner, [region])
        spot = [pm_ for x in (V["meta"].get("variant_regions") or {}).values() for pm_ in (x.get("place") or []) if pm_["place"] == "spot"]
        rows.append(dict(variant=v, spec=vo["spec"], runner=vo["runner"], place=vo["place"],
                         center_m=spot[0]["center_m"] if spot else None, n_placed=sum(s["n_placed"] for s in spot) if spot else None,
                         n_req=sum(s["n_req"] for s in spot) if spot else None, center_game_cm=spot[0].get("center_game_cm") if spot else None,
                         m={k: {kk: p[kk] for kk in ("ref", "var", "diff", "sd", "t", "n")} for k, p in (vo["regions"][region] or {}).items()}))
    return rows


def fmt_rank(rows: list, metrics: list, sort: str | None, order: str = "abs") -> str:
    def key(r):
        p = r["m"].get(sort) if sort else None
        if p is None or p["n"] == 0 or not math.isfinite(p["t"]):
            return math.inf
        return -abs(p["t"]) if order == "abs" else (p["t"] if order == "asc" else -p["t"])

    rs = sorted(rows, key=key) if sort else rows
    metrics = [m for m in metrics if any((r["m"].get(m) or {}).get("n", 0) > 0 for r in rows)]   # 어느 줄에도 값이 없는 칸(실행기 밖)은 뺀다
    head = "| 변형 | 나무 | " + " | ".join(f"`{m}`" for m in metrics) + " |"
    lines = ["차이 (t) — 같은 시드 짝 (변형 − 바탕), % 칸은 %p" + (f", 줄 순서 = `{sort}` 의 t ({order})" if sort else ""), "", head,
             "|---|---|" + "---|" * len(metrics)]
    for r in rs:
        cells = []
        for m in metrics:
            p = r["m"].get(m)
            if p is None or p["n"] == 0:
                cells.append("—")
                continue
            k = 100.0 if m in PCT else 1.0
            cells.append(f"{p['diff'] * k:+.3g} ({p['t']:+.1f})")
        tree = (f"{r['n_placed']}/{r['n_req']} @ ({r['center_m'][0]:g}, {r['center_m'][1]:g}) m" if r.get("center_m") else (r["place"] or "—"))
        lines.append(f"| {r['variant']} | {tree} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def cmd_rank(a) -> int:
    d = Path(a.dir)
    vs = list(a.variants or [])
    for g in a.glob or []:
        vs += [v for v in variants_in(d, g) if v not in vs and v != safe_name(a.ref)]
    if not vs:
        raise SystemExit("변형이 없다 (--variants 또는 --glob)")
    metrics = expand_only(a.metrics) or RANK_METRICS
    rows = rank_rows(d, a.ref, vs, a.region, metrics, a.runner)
    md = fmt_rank(rows, metrics, a.sort, a.order)
    print(md)
    if a.save:
        stem = f"rank_{safe_name(a.save)}"
        (d / f"{stem}.md").write_text(md + "\n", encoding="utf-8", newline="\n")
        (d / f"{stem}.json").write_text(json.dumps(dict(ref=a.ref, region=a.region, metrics=metrics, rows=rows), ensure_ascii=False, indent=1,
                                                   default=_jsonable) + "\n", encoding="utf-8", newline="\n")
        print(f"\n-> {d / (stem + '.md')}")
    return 0


def load_maps(d: Path, variant: str, region: str) -> dict:
    """<변형>__maps(.json.gz 또는 __R-…) 에서 그 지역 지도."""
    cands = [maps_path(d, variant)] + [q for q, regs in _partial_files(d, variant, "maps") if region in regs]
    for p in cands:
        if p.exists():
            m = json_load_gz(p)
            if region in m["regions"]:
                return dict(m["regions"][region], meta=m["meta"])
    raise SystemExit(f"{d} 에 {variant} 의 {region} 공간 지도가 없다 (run --maps --runner python 으로 만든다)")


def map_values(M: dict, name: str, part: str = "all", min_den: float = 20.0) -> np.ndarray:
    """지도 하나 (g, g) [iy, ix]. 'a/b' 는 셀마다 a ÷ b (b < min_den 인 셀은 0)."""
    g = int(M["g"])
    src = M[part] if part != "odd" else {k: (np.asarray(M["all"][k]) - np.asarray(M["even"][k])).tolist() for k in M["all"]}
    if "/" in name:
        a, b = name.split("/", 1)
        A, B = np.asarray(src[a], dtype=np.float64), np.asarray(src[b], dtype=np.float64)
        v = np.where(B >= min_den, A / np.maximum(B, 1e-12), 0.0)
    else:
        if name not in src:
            raise SystemExit(f"지도 {name} 이 없다 ({', '.join(src)})")
        v = np.asarray(src[name], dtype=np.float64)
    return v.reshape(g, g)


def _cell_center(M: dict, iy: int, ix: int) -> tuple[float, float]:
    c = float(M["cell"])
    return (ix + 0.5) * c, (iy + 0.5) * c


def ascii_map(M: dict, V: np.ndarray, width: int = 2) -> str:
    """지도 글 그림 (위 = y 큼). 세기 ' .:-=+*#%@' (√ 비율), 은신처 둘레 셀은 값이 작으면 'o', 줄기가 있는 셀은 'T'."""
    g = int(M["g"])
    c = float(M["cell"])
    chars = " .:-=+*#%@"
    mx = float(V.max()) if V.size else 0.0
    cov = np.asarray(M.get("covers") or [], dtype=np.float64).reshape(-1, 3)
    disc = np.asarray(M.get("discs") or [], dtype=np.float64).reshape(-1, 3)
    tcell = {(int(min(g - 1, max(0, y // c))), int(min(g - 1, max(0, x // c)))) for x, y, _ in disc}
    rows = []
    for iy in range(g - 1, -1, -1):
        s = []
        for ix in range(g):
            v = V[iy, ix]
            lvl = 0 if v <= 0 or mx <= 0 else max(1, int(math.ceil(9 * math.sqrt(v / mx))))
            ch = chars[lvl]
            x, y = _cell_center(M, iy, ix)
            if (iy, ix) in tcell:
                ch = "T"
            elif lvl <= 1 and len(cov) and (np.abs(np.hypot(x - cov[:, 0], y - cov[:, 1]) - cov[:, 2]) <= 0.6 * c).any():
                ch = "o"
            s.append(ch * width)
        rows.append(f"{(iy + 0.5) * c * UNIT_M:5.0f} |" + "".join(s))
    axis = "      " + "".join(f"{(ix + 0.5) * c * UNIT_M:<{width * 5}.0f}" for ix in range(0, g, 5))
    return "\n".join(rows + [axis + "  (m)"])


def spot_candidates(M: dict, V: np.ndarray, k: int, sep_m: float, n: int, r_m: float, info_region_index: int = 0) -> list:
    """지도 값이 큰 셀부터, 서로 sep_m 이상 떨어지고 그 점 둘레 작은 숲(n 그루, 반지름 r_m)을 AddTrees 규칙으로 다 놓을 수 있는 중심 k 개.
    반환 [{x_m, y_m, value, share, placed, spec}]."""
    g = int(M["g"])
    size = float(M["size"])
    cov = [list(map(float, c)) for c in (M.get("covers") or [])]
    disc = [list(map(float, x)) for x in (M.get("discs") or [])]
    tot = float(V.sum()) or 1.0
    order = np.argsort(-V.ravel(), kind="stable")
    out: list = []
    for idx in order:
        if len(out) >= k:
            break
        iy, ix = divmod(int(idx), g)
        v = float(V[iy, ix])
        if v <= 0:
            break
        x, y = _cell_center(M, iy, ix)
        if any(math.hypot(x - o["x"], y - o["y"]) * UNIT_M < sep_m for o in out):
            continue
        new, meta = place_spot(n, size, cov, disc, TREE_SEED, info_region_index, (x, y), r_m / UNIT_M)
        if meta["n_placed"] < n:
            continue
        out.append(dict(x=x, y=y, x_m=round(x * UNIT_M, 2), y_m=round(y * UNIT_M, 2), value=v, share=v / tot, placed=meta["n_placed"],
                        center_state=meta["center_state"], spec=f"spot:{x * UNIT_M:g}:{y * UNIT_M:g}:{n}:{r_m:g}"))
    return out


def cmd_maps(a) -> int:
    d = Path(a.dir)
    M = load_maps(d, a.variant, a.region)
    labels = M["meta"].get("labels", MAPS)
    out: dict = dict(variant=a.variant, region=a.region, seeds=M["seeds"], cell_m=float(M["cell"]) * UNIT_M, maps={})
    print(f"{a.variant} — {a.region} 공간 지도 (셀 {float(M['cell']) * UNIT_M:g} m, 세계 {M['worlds']}, 시드 {M['seeds']}). 은신처(단위) "
          f"{M.get('covers')}, 줄기 {len(M.get('discs') or [])} 개, 게임 원점 {M.get('origin_cm')} cm")
    for name in a.show:
        V = map_values(M, name, "all", a.min_den)
        Ve, Vo = map_values(M, name, "even", a.min_den), map_values(M, name, "odd", a.min_den)
        ok = (Ve.ravel().std() > 0) and (Vo.ravel().std() > 0)
        rr = float(np.corrcoef(Ve.ravel(), Vo.ravel())[0, 1]) if ok else float("nan")
        lab = labels.get(name) or " ÷ ".join(labels.get(x, x) for x in name.split("/"))
        print(f"\n## {name} — {lab}\n합 {V.sum():.6g}, 시드 반 나눠 맞음 r = {rr:.2f} (짝수 시드 지도 ↔ 홀수 시드 지도)")
        if not a.no_ascii:
            print(ascii_map(M, V))
        order = np.argsort(-V.ravel(), kind="stable")[: a.top]
        tot = float(V.sum()) or 1.0
        cov = np.asarray(M.get("covers") or [], dtype=np.float64).reshape(-1, 3)
        top = []
        for idx in order:
            iy, ix = divmod(int(idx), int(M["g"]))
            x, y = _cell_center(M, iy, ix)
            de = float((np.hypot(x - cov[:, 0], y - cov[:, 1]) - cov[:, 2]).min()) * UNIT_M if len(cov) else math.nan
            o = M.get("origin_cm") or [0.0, 0.0, 0.0]
            top.append(dict(x_m=x * UNIT_M, y_m=y * UNIT_M, value=float(V[iy, ix]), share=float(V[iy, ix]) / tot, shelter_edge_m=de,
                            game_cm=[o[0] + x * 200.0, o[1] + y * 200.0]))
        print("값 큰 셀: " + "; ".join(f"({t_['x_m']:g}, {t_['y_m']:g}) m {t_['value']:.4g} ({t_['share'] * 100:.1f}%, 은신처 가장자리 "
                                    f"{t_['shelter_edge_m']:+.0f} m)" for t_ in top))
        cand = spot_candidates(M, V, a.spots, a.sep, a.trees, a.radius, int(M.get("region_index", 0))) if a.spots else []
        if cand:
            print(f"작은 숲 자리 후보 ({a.trees} 그루·반지름 {a.radius:g} m·서로 {a.sep:g} m 이상, 다 놓을 수 있는 곳): "
                  + " ".join(c["spec"] for c in cand))
        out["maps"][name] = dict(total=float(V.sum()), half_r=rr, top=top, candidates=cand)
    if a.save:
        p = d / f"maps_{safe_name(a.variant)}_{a.region}.json"
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=_jsonable) + "\n", encoding="utf-8", newline="\n")
        print(f"\n-> {p}")
    return 0


def cmd_scan(a) -> int:
    """작은 숲 자리 훑기: 격자(--grid m) 또는 공간 지도 후보(--from-map)의 점마다 spot 변형을 지역 하나만(평가기) 돌리고 rank 로 줄 세운다."""
    info = prepare(a.base, a.brain, Path(a.out) / "prep")
    if a.region not in info["regions"]:
        raise SystemExit(f"지역 {a.region} 이 없다 ({', '.join(info['regions'])})")
    reg = info["regions"][a.region]
    j0 = next(it[2] for it in _live().eval_items(info, "cur", info["model"], [SEED_BOX[0]], 1, a.world, "multi", [1]) if it[2]["region"] == a.region)
    w0 = _region_world(j0["cfg"], SEED_BOX[0])
    size = float(w0.size)
    covers = np.c_[w0.cov_c, w0.cov_r].tolist()
    base_discs = [list(map(float, x)) for x in (j0["cfg"]["v2"]["features"]["obstacles"].get("fixed") or [])]
    cands: list = []
    if a.from_map:
        M = load_maps(Path(a.from_map), a.map_variant, a.region)
        for name in a.map:
            for c in spot_candidates(M, map_values(M, name, "all", a.min_den), a.spots, a.sep, a.trees, a.radius, int(reg["region_index"])):
                cands.append((c["x"], c["y"], f"지도 {name} ({c['share'] * 100:.1f}%)"))
    else:
        step = a.grid / UNIT_M
        xs = np.arange(step / 2, size, step)
        cands = [(float(x), float(y), "격자") for y in xs for x in xs]
    variants, skipped, why = [], [], {}
    for x, y, src in cands:
        spec = f"spot:{x * UNIT_M:g}:{y * UNIT_M:g}:{a.trees}:{a.radius:g}"
        if spec in variants:
            continue
        _, meta = place_spot(a.trees, size, covers, base_discs, TREE_SEED, int(reg["region_index"]), (x, y), a.radius / UNIT_M)
        if meta["n_placed"] < a.trees:
            skipped.append(dict(spec=spec, placed=meta["n_placed"], state=meta["center_state"], free_frac=meta["free_frac"]))
            continue
        variants.append(spec)
        why[safe_name(spec)] = src
    print(f"훑기: 후보 {len(cands)}, 돌릴 점 {len(variants)}, 다 못 놓아 뺀 점 {len(skipped)} "
          + (f"({', '.join(s['spec'] + ' ' + str(s['placed']) + '/' + str(a.trees) + ' ' + s['state'] for s in skipped[:8])}{' …' if len(skipped) > 8 else ''})"
             if skipped else ""), flush=True)
    a.regions = [a.region]
    a.maps = False
    a.stuck = 0
    a.force = False
    run_variants(a, [a.ref] + variants)
    d = run_dir(Path(a.out), a.base, a.brain, a.world, int(a.horizon))
    metrics = expand_only(a.metrics) or RANK_METRICS
    rows = rank_rows(d, a.ref, [safe_name(v) for v in variants], a.region, metrics, "ceval" if a.runner in ("auto", "ceval") else a.runner)
    for r in rows:
        r["source"] = why.get(r["variant"], "")
    md = fmt_rank(rows, metrics, a.sort, a.order)
    print(md)
    tag = safe_name(a.tag or (f"map_{'+'.join(a.map)}" if a.from_map else f"grid{a.grid:g}"))
    p = d / f"scan_{tag}_{a.region}.json"
    p.write_text(json.dumps(dict(made_by="level_sense/sense.py scan", ref=a.ref, region=a.region, trees=a.trees, radius_m=a.radius, metrics=metrics,
                                 skipped=skipped, rows=rows), ensure_ascii=False, indent=1, default=_jsonable) + "\n", encoding="utf-8", newline="\n")
    (d / f"scan_{tag}_{a.region}.md").write_text(md + "\n", encoding="utf-8", newline="\n")
    print(f"\n-> {p}")
    return 0


# --------------------------------------------------------------------- #
# 바탕 맞추기 · 두 실행기 맞추기
# --------------------------------------------------------------------- #

PILOT_OF = {("I", "t10"): "I_t10", ("I", "t20"): "I_t20", ("I", "t30"): "I_t30", ("J", "t10"): "J_t10", ("J", "t20"): "J_t20", ("J", "t30"): "J_t30"}


def pilot_seed_table(variant: str, key: str = "current:N:1800") -> dict:
    """저장소의 pilot_mask5/seeds/<변형>.json.gz → {시드: {FIELDS}} (지금 두뇌 R7e, 지역 셋 합)."""
    d = json_load_gz(PM_DIR / "seeds" / f"{variant}.json.gz")
    f = d["fields"]
    return {int(s): dict(zip(f, row)) for s, row in zip(d["seeds"], d["table"][key])}


def my_seed_table(recs: list, H: int) -> dict:
    import pilot_mask5_analyze as an

    return an.seed_table(dict(meta={}, worlds=recs), H)


def compare_worlds(a: list, b: list, keys=None, H: int | None = None) -> dict:
    """두 기록 묶음 (시드, 지역) 짝마다 칸이 정확히 같은가. keys None = 양쪽에 다 있는 칸(wall_s·native·py 빼고)."""
    ka = {(int(r["seed"]), r["region"]): r for r in a}
    kb = {(int(r["seed"]), r["region"]): r for r in b}
    both = sorted(set(ka) & set(kb))
    bad = []
    for k in both:
        x, y = ka[k], kb[k]
        ks = keys or sorted((set(x) & set(y)) - {"wall_s", "native", "py"})
        diff = [c for c in ks if x.get(c) != y.get(c)]
        if diff:
            bad.append(dict(seed=k[0], region=k[1], differ=diff[:6]))
    return dict(worlds=len(both), exact=len(both) - len(bad), only_a=len(set(ka) - set(kb)), only_b=len(set(kb) - set(ka)), bad=bad[:10])


def cmd_match(a) -> int:
    out: dict = dict(made_by="level_sense/sense.py match", rows=[])
    for base in ("I", "J"):
        d = run_dir(Path(a.out), base, "r7e", "N", 1800)
        for v in ("t10", "t20", "t30"):
            pv = PILOT_OF[(base, v)]
            try:
                R = load_raw(d, v, a.runner)
            except SystemExit as ex:
                print(f"{base} {v}: {ex}")
                continue
            mine = my_seed_table(R["worlds"], 1800)
            pil = pilot_seed_table(pv)
            same = sum(1 for s in pil if s in mine and all(mine[s][k] == pil[s][k] for k in pil[s]))
            hide_m = sum(x["ep_hidden"] for x in mine.values()) / max(sum(x["ep_chased"] for x in mine.values()), 1)
            hide_p = sum(x["ep_hidden"] for x in pil.values()) / max(sum(x["ep_chased"] for x in pil.values()), 1)
            row = dict(base=base, variant=v, pilot=pv, runner=R["meta"]["runner"], seeds_exact=same, seeds=len(pil), hide_mine=hide_m, hide_pilot=hide_p)
            if a.raw:
                rp = Path(a.raw) / f"{pv}.json.gz"
                if rp.exists():
                    raw = json_load_gz(rp)
                    res = {}
                    for c in raw["captured"]:
                        res.update(c["res"])
                    pw = [dict(w, **{k: w["at"]["1800"][k] for k in ("caught", "starved", "alive")}, flight=w["at"]["1800"]["flight"],
                               at={"1800": w["at"]["1800"]}) for w in res["current:N"]["worlds"]]
                    mw = [dict(w, flight=w["at"]["1800"]["flight"]) for w in R["worlds"]]
                    row["raw_worlds"] = compare_worlds(mw, pw, keys=["n", "caught", "starved", "alive", "flight", "at"])
            out["rows"].append(row)
            print(f"{base} {v} ({row['runner']}) ↔ pilot {pv}: 시드 합 칸이 모두 같은 시드 {same}/{len(pil)}, 사건 숨음 비율 {hide_m * 100:.2f}% (pilot "
                  f"{hide_p * 100:.2f}%)" + (f", 원자료 세계 기록 같음 {row['raw_worlds']['exact']}/{row['raw_worlds']['worlds']}" if "raw_worlds" in row else ""))
        # 바탕(나무 0): pilot 판이 없다 — 원자료가 있으면 바뀌지 않은 지역(바탕 = 변형)과 J 의 Barren(= J_wx 의 Barren)을 세계마다 맞춘다
        try:
            B = load_raw(d, "base", a.runner)
        except SystemExit:
            continue
        mine = my_seed_table(B["worlds"], 1800)
        hide_b = sum(x["ep_hidden"] for x in mine.values()) / max(sum(x["ep_chased"] for x in mine.values()), 1)
        row = dict(base=base, variant="base", runner=B["meta"]["runner"], hide_mine=hide_b)
        if a.raw:
            for pv, regs in ((f"{base}_t10", ("Forest", "Highland")),) + ((("J_wx", ("Barren", "Forest")),) if base == "J" else ()):
                rp = Path(a.raw) / f"{pv}.json.gz"
                if not rp.exists():
                    continue
                raw = json_load_gz(rp)
                res = {}
                for c in raw["captured"]:
                    res.update(c["res"])
                pw = [dict(w, flight=w["at"]["1800"]["flight"], **{k: w["at"]["1800"][k] for k in ("caught", "starved", "alive")})
                      for w in res["current:N"]["worlds"] if w["region"] in regs]
                mw = [dict(w, flight=w["at"]["1800"]["flight"]) for w in B["worlds"] if w["region"] in regs]
                row[f"raw_{pv}_{'+'.join(regs)}"] = compare_worlds(mw, pw, keys=["n", "caught", "starved", "alive", "flight"])
        out["rows"].append(row)
        print(f"{base} base ({row['runner']}): 사건 숨음 비율 {hide_b * 100:.2f}% (pilot 판 없음)"
              + "".join(f", {k} 같음 {v['exact']}/{v['worlds']}" for k, v in row.items() if k.startswith("raw_")))
    if a.save:
        p = Path(a.save)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=_jsonable) + "\n", encoding="utf-8", newline="\n")
        print(f"-> {p}")
    return 0


def cmd_parity(a) -> int:
    d = Path(a.dir)
    out: dict = dict(made_by="level_sense/sense.py parity", dir=d.name, rows=[])
    for v in a.variants:
        A = load_raw(d, v, "ceval")
        B = load_raw(d, v, "python")
        c = compare_worlds(A["worlds"], B["worlds"])
        ta, tb = A["meta"]["time"], B["meta"]["time"]
        keys = sorted({k for r in A["worlds"] for k in r} & {k for r in B["worlds"] for k in r} - {"wall_s", "native", "py"})
        out["rows"].append(dict(variant=v, spec=A["meta"]["spec"], compared_keys=keys, **c,
                                time=dict(ceval=ta, python=tb, workers=[A["meta"]["workers"], B["meta"]["workers"]])))
        print(f"{v}: 세계 기록(겹치는 칸 모두 — wall_s·native·py 빼고) 정확히 같음 {c['exact']}/{c['worlds']} (한쪽만 {c['only_a']}·{c['only_b']})"
              + (f", 다른 세계 {c['bad'][:3]}" if c["bad"] else "")
              + f". 시간: 평가기 {ta['run_s']:.0f} 초 (+ 만들기 {ta['build_s']:.0f}), 파이썬 {tb['run_s']:.0f} 초 (+ {tb['build_s']:.0f})")
    if a.save:
        p = Path(a.save)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=_jsonable) + "\n", encoding="utf-8", newline="\n")
        print(f"-> {p}")
    return 0


# --------------------------------------------------------------------- #


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(s, variants_required=False):
        s.add_argument("--base", default="I", choices=list(BASES))
        s.add_argument("--brain", default="r7e", choices=list(BRAINS))
        s.add_argument("--region", default=TARGET)
        s.add_argument("--seeds", default=f"{SEED_BOX[0]}-{SEED_BOX[1]}")
        s.add_argument("--out", default=str(OUT_DEFAULT))
        s.add_argument("--variants", nargs="+", required=variants_required, default=[])

    def runargs(s):
        s.add_argument("--world", default="N", choices=["N", "G"])
        s.add_argument("--horizon", type=int, default=1800)
        s.add_argument("--runner", default="auto", choices=["auto", "ceval", "python"])
        s.add_argument("--workers", type=int, default=6)

    def rankargs(s):
        s.add_argument("--metrics", nargs="+", default=None, help=f"칸 이름 또는 묶음 tree·core (기본 {' '.join(RANK_METRICS)})")
        s.add_argument("--sort", default="fl_obstacle_of_chased", help="줄 세울 칸 (t 로)")
        s.add_argument("--order", default="abs", choices=["abs", "asc", "desc"])

    def spotargs(s, spots_default):
        s.add_argument("--spots", type=int, default=spots_default, help="작은 숲 자리 후보 수")
        s.add_argument("--sep", type=float, default=16.0, help="후보끼리 띄움 m")
        s.add_argument("--trees", type=int, default=8, help="작은 숲 그루 수")
        s.add_argument("--radius", type=float, default=10.0, help="작은 숲 반지름 m")
        s.add_argument("--min-den", type=float, default=20.0, help="'a/b' 지도에서 b 가 이보다 작은 셀은 0")

    s = sub.add_parser("list")
    common(s)
    s = sub.add_parser("run")
    common(s, True)
    runargs(s)
    s.add_argument("--regions", nargs="+", default=None, help="이 지역 세계만 돌린다 (기록 이름에 __R-<지역>)")
    s.add_argument("--maps", action="store_true", help="공간 지도 (파이썬 실행기) -> <변형>__maps.json.gz")
    s.add_argument("--stuck", type=int, default=0, help="끼임 세기 시드 수 (G 세계·파이썬, 0 = 안 함)")
    s.add_argument("--stuck-horizon", type=int, default=3600)
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("table")
    s.add_argument("--dir", required=True)
    s.add_argument("--ref", default="base")
    s.add_argument("--variants", nargs="+", required=True)
    s.add_argument("--region", default=None)
    s.add_argument("--runner", default=None, choices=["ceval", "python"])
    s.add_argument("--only", nargs="+", default=None, help="칸 이름 또는 묶음 tree(나무 덕)·core(행동)")
    s.add_argument("--save", action="store_true")
    s = sub.add_parser("rank")
    s.add_argument("--dir", required=True)
    s.add_argument("--ref", default="base")
    s.add_argument("--variants", nargs="+", default=None)
    s.add_argument("--glob", nargs="+", default=None, help="기록 파일 이름으로 변형 고르기 (예 'spot*')")
    s.add_argument("--region", default=TARGET)
    s.add_argument("--runner", default=None, choices=["ceval", "python"])
    rankargs(s)
    s.add_argument("--save", default=None, help="이름 -> <dir>/rank_<이름>.md·json")
    s = sub.add_parser("maps")
    s.add_argument("--dir", required=True)
    s.add_argument("--variant", default="base")
    s.add_argument("--region", default=TARGET)
    s.add_argument("--show", nargs="+", default=["flee", "chased_flee", "onset", "spot_deer", "lost", "enter_fled", "graze", "wolf_idle", "wolf_sleep",
                                                 "caught"], help=f"지도 이름 ({', '.join(MAPS)}) 또는 'a/b'")
    s.add_argument("--top", type=int, default=6)
    s.add_argument("--no-ascii", action="store_true")
    spotargs(s, 0)
    s.add_argument("--save", action="store_true")
    s = sub.add_parser("scan")
    common(s)
    runargs(s)
    s.add_argument("--ref", default="base")
    s.add_argument("--grid", type=float, default=20.0, help="격자 간격 m (--from-map 이 없을 때)")
    s.add_argument("--from-map", default=None, help="공간 지도가 있는 폴더 (run --maps 결과)")
    s.add_argument("--map-variant", default="base")
    s.add_argument("--map", nargs="+", default=["chased_flee"], help="후보를 뽑을 지도 이름 (여럿이면 지도마다 --spots 개)")
    spotargs(s, 6)
    rankargs(s)
    s.add_argument("--tag", default=None)
    s = sub.add_parser("match")
    s.add_argument("--out", default=str(OUT_DEFAULT))
    s.add_argument("--raw", default=None, help="pilot_mask5 원자료 폴더 (raw/<변형>.json.gz — 저장소 밖)")
    s.add_argument("--runner", default=None, choices=["ceval", "python"])
    s.add_argument("--save", default=None, help="결과 json 경로")
    s = sub.add_parser("parity")
    s.add_argument("--dir", required=True)
    s.add_argument("--variants", nargs="+", required=True)
    s.add_argument("--save", default=None, help="결과 json 경로")
    a = ap.parse_args(argv)
    return dict(list=cmd_list, run=cmd_run, table=cmd_table, rank=cmd_rank, maps=cmd_maps, scan=cmd_scan, match=cmd_match, parity=cmd_parity)[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
