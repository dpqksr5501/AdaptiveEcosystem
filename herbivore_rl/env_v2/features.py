"""V2 기능 스위치와 기능별 난수 스트림 (계획서 4.8, 0-1b).

버전 설정(`configs/v2.yaml`, `configs/v2_0b.yaml`, `configs/v2_1.yaml`, `configs/v2_2.yaml`, `configs/v2_2r_*.yaml` ...)의
`features:` 아래에 기능마다
블록 하나를 둔다.

    features:
      food_v: {enabled: true, alpha: 0.5, floor: 0.1, recovery_half_lives: [300, 700], init_frac: [0.3, 1.0]}
      daynight: {enabled: false}

- 블록이 없거나 `enabled` 가 없는 기능은 꺼진 것이다. 모두 끄면 env_v2 World 는 v1 과 같은 세계다.
- 블록의 나머지 키는 그 기능의 계수다(`Features.params`). **켠 기능의 계수는 yaml 에 모두 적는다.**
  구현 코드는 기본값을 두지 않고 `p["alpha"]` 처럼 읽는다. 그래야 보정한 값이 설정 파일, 진단 캐시 키
  (`diagnose_v2.py` config_digest), 학습 메타 JSON 에 그대로 남는다.
- 읽을 때 바로 실패하는 것(켰다고 적었는데 아무 일도 안 일어나는 실험을 막는다):
  등록부(`FEATURE_IDS`)에 없는 이름, 블록이 아닌 값, bool 이 아닌 `enabled`, 문자열이 아닌 키,
  숫자처럼 보이는 문자열 값(PyYAML 은 `1e-3`·`1.0e3` 을 문자열로 읽는다. 소수점과 지수 부호를 넣어
  `1.0e-3`·`1.0e+3` 으로 쓴다),
  아직 구현하지 않은 기능 켜기, 구현한 기능(`PARAM_KEYS`)의 모르는 계수 키(`enable`·`alhpa` 같은 오타),
  켠 기능의 빠진 계수.

기능마다 난수 스트림이 따로다: `np.random.default_rng([seed, STREAM_DOMAIN, FEATURE_IDS[name], part])`.
기능 A 를 켜고 끄든, A 가 난수를 몇 개 뽑든 기능 B 의 스트림이 내는 난수열은 그대로이고, 기능 스트림을
써도 v1 스트림(`default_rng(seed)`)은 소비되지 않는다. (A 가 세계를 바꾸면 사망·리스폰 같은 사건이
달라져 B 와 v1 이 난수를 *언제 몇 개* 쓰는지는 달라진다. 그건 기능을 켠 결과다.) 기능을 구현할 때 지킬 것:

1. 기능은 자기 스트림(`World.feature_rng(name, part)`)에서만 뽑는다. v1 스트림 `World.rng` 와
   다른 기능의 스트림에서 뽑지 않는다. 다른 기능의 스트림을 만들지 않는지는 `tests/test_features_v2.py` 가
   구현된 기능마다 확인한다. v1 스트림을 쓰지 않는지는 테스트로 잡히지 않으므로 리뷰로 지킨다.
2. v1 난수 호출을 대신하는 기능(예: v2.5a 리스폰 위치, v2.7 b)도 v1 호출은 그대로 두고 결과만 덮어쓴다.
   그래야 같은 사건이 일어나면 v1 스트림의 위치가 기능 스위치와 상관없이 같다.
3. 이미 있는 기능에 나중에 난수를 더할 때는 새 `part` 번호에서 뽑는다. 같은 스트림 뒤에 붙이면
   앞 버전 세계의 난수열이 밀린다.
4. 번호는 한번 정하면 바꾸지 않는다. 바꾸면 같은 시드의 세계가 조용히 달라진다. 새 기능은 새 번호를 받는다.
5. 이미 있는 기능에 동작을 더할 때는 새 계수 키를 `PARAM_KEYS` 에 더하고, 그 키의 '끔' 값이 앞 버전
   동작이 되게 한다. 앞 버전 설정에는 그 값을 적는다(계수가 빠지면 읽을 때 실패한다). 3 과 5 가 함께
   있어야 "새 기능만 끈 상태 = 직전 버전" 회귀가 지켜진다.
6. 규칙 5 의 다른 꼴 — 선택 계수 키(`OPTIONAL_KEYS`, 10-14 R3): 앞 버전 설정 파일을 고치지 않고(그 파일의 config digest 와
   기록된 결과가 그대로 남게) 이미 있는 기능에 동작을 더할 때 쓴다. 등록부에 키와 '끔' 값(= 앞 버전 동작)을 한 번 적고, 켠 블록에
   그 키가 없으면 끔 값으로 읽는다(`with_optional`). 새 설정은 선택 키도 모두 적는다(R3 설정 configs/v3_r3*.yaml 이 적는다).
   모르는 키 검사는 선택 키도 안다. 끔 값으로 앞 버전과 비트 동일인지는 그 기능의 시험이 본다(tests/test_r3_world.py).

numpy `SeedSequence` 는 시드 목록 끝의 0 을 무시하고(`[s, 2, 7]` 과 `[s, 2, 7, 0]` 이 같은 스트림),
2^32 이상의 정수는 uint32 단어 여러 개로 쪼갠다. 그래서 시드와 part 는 [0, 2^32) 로 제한한다. 이 범위에서
`part=0` 은 계획서의 `[seed, 2, feature_id]` 와 같다. 기능 번호 0 은 쓰지 않는다(`[s, 2, 0]` 은 예전 공용
스트림 `[s, 2]` 와 같아진다). `env_v2/rollout.py` 의 순열 스트림은 둘째 칸이 101·202 라 겹치지 않는다.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

# 시드 목록 둘째 칸. v1 스트림은 default_rng(seed) = [seed, 0, ...] 이고 순열 대조군은 101·202 다.
STREAM_DOMAIN = 2
_U32 = 2**32

# 기능 이름 → 스트림 번호. 버전 순서로 붙였다 (계획서 4.1, 4.9). 번호를 바꾸거나 다시 쓰지 않는다.
# 기능 하나 = 버전 하나의 스위치다. 그 버전을 끄면 직전 버전 세계가 된다.
FEATURE_IDS: Mapping[str, int] = MappingProxyType({
    "food_v": 1,        # v2.0b 먹이 2층: 식생 용량 V 의 훼손과 느린 회복
    "speed": 2,         # v2.1 보행 3단(정지·걷기·뛰기), 대사·섭식 연동
    "vigilance": 3,     # v2.2 경계, threat_recency, 위협 방향
    "regions": 4,       # v2.3 A/B 지역, 소속, 지역 포식자, 지역 기억 (플레이어형 위협은 v3 threats(16)가 맡는다)
    "daynight": 5,      # v2.4 낮밤 위상, 밤 탐지·섭식·휴식 배수
    "region_env": 6,    # v2.5a 지역 환경: 리스폰 위치 규칙, 지역 재생비, 지역 사이 틈
    "migration": 7,     # v2.5b 이주 조향 항, 지역 먹이·안전 관측, 고갈 안전망
    "weather": 8,       # v2.6 맑음↔비 Markov, 탐지·재생·회복 배수
    "boldness": 9,      # v2.7 개체 대담함 b, 사망 보상 조건화
    "water": 10,        # v2.8 물웅덩이, 수분, 마시기
    "boundary": 11,     # R1 (i) 언리얼 경계 반발 파리티
    "obstacles": 12,    # R1 (ii) 원형 장애물 반발로 예약 → v3 세로 장애물(나무·바위 원판). 10-14 에는 자리만 두었고 야생 2단계 3(10-17 사용자
                        # '추천대로 끄고 2~4번 진행해')에서 넣었다: 사슴·늑대가 원판 둘레를 따라 미끄러지고, 원판이 눈길을 가리고(발소리는 못 가림),
                        # 원판 밑 먹이가 없다. 정의는 env_v2/world.py 모듈 docstring '야생 2단계' 3, 자료 World.obstacles (K, 3) [x, y, r]
    "vigil_window": 13,  # v2.2r 경계 재설계(10-03 R2): 경계 행동 열 유무, 창 안 한정 경계(W′), 반사 돌아보기(L)
    "pred_sleep": 14,    # v2.4s 포식자 밤잠(10-07 사용자 결정 A안): 대부분 밤에 자고 세계마다 일부만 야행성
    "repertoire": 15,    # v3 R0 행동 레퍼토리(10-07 사용자 결정 (4)): 행동 실행기·잠금·사건·개체 행동 상태, 장치 M1·M2·M4·M5·M6
    "threats": 16,       # v3 R0 위협 유형(10-07 사용자 결정 (4)): 잠행-돌진 포식자(M3)와 플레이어형 위협
    "stare_down": 17,    # v3 R2 M7 노려보기 대치(10-08 사용자 결정 (1)): 표적 잠금, 얼어 노려보기 → 대치·물러남·들킴. 난수 없음
    "alarm": 18,         # v3 R2 M8 동족 경보 전염(10-08 사용자 결정 (1)): 경보 방출·수신·중계, 관측 alarm_heard, 사건 E7. 난수 없음
    # v3 현실성 1단계(10-14 사용자 방향 — 통합 레벨을 본 뒤 "도망 멈춤·갑자기 잠듦이 이상하다", "은신처엔 먹이를 적게"). 규칙 다섯을
    # 따로 켜고 끈다. 난수 없음(정의·식·현실 근거는 env_v2/world.py 모듈 docstring 'realism_*')
    "realism_vision": 19,      # (a) 사슴의 위협 시야각(예: 300°, 바로 뒤 사각만 남김). 동족 시야는 따로 적은 키가 바꾸지 않으면 그대로
    "realism_hearing": 20,     # (b) 위협 발소리: 걸음새·속력에 따른 반경 안이면 방향과 무관하게 '감지됨'(관측 18칸·범위 그대로)
    "realism_shelter": 21,     # (c) 은신처 원 안의 사슴은 행동과 무관하게 잡히지 않는다(안에서 먹어도 된다)
    "realism_night": 22,       # (d) 늑대 밤잠 점진화: 사냥 중·사슴 근처면 눕지 않음, 걸음을 늦추며 눕기, 늑대마다 다른 잠·기상 시각, 기상 가속
    "realism_cover_food": 23,  # (e) 은신처 원과 겹치는 셀의 먹이 용량·재생을 밖의 일부로(빽빽한 덤불 밑은 풀이 적다)
    # v3 R3 세계(10-14 사람 결정, 명세 Docs/RL_Policy/RL_V3_R3_SPEC.md 14절). 정의·식·현실 근거는 env_v2/world.py 모듈 docstring
    # 'R3 세계'. 늑대가 은신처 원에 못 들어감(H17)과 은신처 먹이 배수 뽑기(H7)는 기존 블록의 선택 키다(OPTIONAL_KEYS). 늑대가 잡은 자리에서
    # 서서 먹는 시간(10-15 사람 결정)도 threats 블록의 선택 키 eat_in_place 와 v1 키 pred_eat_cd(overrides)다 — 새 번호가 없다
    "realism_chase": 24,       # (f) 추격 고정: 쫓기 시작한 늑대는 그 사슴이 보이는 동안 표적을 바꾸지 않는다(H6). 난수 없음
    "realism_terrain": 25,     # (h) 지형 구역: 셀마다 보통·눈·거친 땅, 이동 전 셀의 땅이 속력을 줄인다(H18, 사슴은 관측하지 않음 H19)
    # 언리얼 통합 v3 모드 거울(10-15 사용자 '언리얼에서 돌리는 게 파이썬에서 돌리는 것과 얼마나 비슷한지'): 팀 레벨의 지역 무대 하나를
    # 흉내 내는 세계 규칙 묶음 — 부활 없음(죽은 사슴은 그 자리에 남는다), 피식 EMA 분모, 시작 낮밤 위상, 무대 1/4·3/4 은신처, 늑대 구성
    # (잠행·추격 번갈아), 무대 시작 배치·방향. 정의·식·C++ 출처는 env_v2/world.py 모듈 docstring '통합 무대'
    "integrated_stage": 26,
    # 야생 규칙 1단계(10-15 사용자 '야생 생태계 규칙', 명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md). 셋 다 난수 없음. 정의·식·현실 근거는
    # env_v2/world.py 모듈 docstring '야생 1단계'
    "wild_reserve": 27,     # (w1) 지방 비축: E 가 0 밑이면 느린 비축 R 에서 꺼내 쓰고 R 이 바닥나야 굶어 죽는다, E 가 바닥이면 약해진다(느림)
    "wild_satiation": 28,   # (w2) 늑대 포만: 먹고 나면 정한 시간(게임 하루 단위) 동안 쉬며 사냥하지 않는다
    "wild_flight": 29,      # (w3) 도주 반사 거리: 사냥 중인 늑대가 경계 거리 안이면 먹으며 멀어지고, 도주 거리 안·다가오면 안전할 때까지 뛴다
    # 야생 규칙 2단계 2(10-17 사용자 '추천대로 끄고 2~4번 진행해', 명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md). 난수 없음. 정의·식·현실 근거는
    # env_v2/world.py 모듈 docstring '야생 2단계' 2
    "wild_pack": 30,        # 늑대 무리 협동 사냥: 한 늑대가 사슴을 쫓는 동안 쉬던 동료가 그 사슴이 달아날 곳(은신처 문·도주선 앞)에 가서 기다린다
    # 야생 3단계(10-18 사용자 '우리 테스트 레벨에도 날씨 적용되게 해 줘. 그 날씨와 장애물들을 바탕으로 만들어진 세계를 파이썬에 고대로 옮겨서 학습시킬 거야',
    # 명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md 11절). 난수 없음. 정의·식·현실 근거는 env_v2/world.py 모듈 docstring '야생 3단계'.
    # 번호 8 weather 는 v2.6 설계(맑음↔비 Markov, 먹이 재생·회복 배수)의 자리라 그대로 두고 새 번호를 받는다(규칙 4)
    "wild_weather": 31,     # 지역 날씨: 지역마다 맑음·비·눈과 세기(고정 표, 선택 시간표). 비는 시야·청각, 눈은 시야·이동(사슴이 늑대보다 더 느려짐)
    # R5 장애물 관측(10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 계획서 RL_V2_PLAN.md 10-19 (16)). 세계 규칙이 아니라 관측 칸 셋이다 —
    # 켜도 동역학·난수는 그대로이고 관측 맨 끝에 escape_room·obstacle_near·threat_hidden 이 붙는다. 정의·식은 env_v2/world.py 모듈 docstring 'R5 장애물 관측',
    # 계약 Docs/RL_Policy/POLICY_CONTRACT_V3.md 2-4
    "obstacle_obs": 32,
})

# 구현을 마친 기능. 기능을 구현하는 커밋에서 이름을 더한다.
IMPLEMENTED: frozenset[str] = frozenset({"food_v", "speed", "vigilance", "vigil_window", "daynight", "pred_sleep",
                                         "repertoire", "threats", "stare_down", "alarm",
                                         "realism_vision", "realism_hearing", "realism_shelter", "realism_night",
                                         "realism_cover_food", "realism_chase", "realism_terrain", "integrated_stage",
                                         "wild_reserve", "wild_satiation", "wild_flight", "wild_pack", "obstacles", "wild_weather",
                                         "obstacle_obs"})

# 구현한 기능의 계수 키. 켜면 모두 적어야 하고, 여기 없는 키는 오타로 보고 실패한다.
# 기능을 구현하는 커밋에서 IMPLEMENTED 와 함께 더한다. 값의 범위는 기능 코드가 검사한다.
PARAM_KEYS: Mapping[str, frozenset[str]] = MappingProxyType({
    # v2.0b (env_v2/world.py `_food_v_params`): 훼손 계수 α, 하한(cap0 비율), 휴식 회복 반감기 목록(스텝,
    # reset 마다 하나), V 초기값 cap0 비율 범위 [하, 상](reset 마다 좌우 절반에 하나씩)
    "food_v": frozenset({"alpha", "floor", "recovery_half_lives", "init_frac"}),
    # v2.1 (env_v2/world.py `_speed_params`): 행동 idx 4 의 보행 문턱 [걷기, 뛰기], 상태별 속력 [정지, 걷기,
    # 뛰기](× herb_speed, 정지는 0), 상태별 섭식 배수(want 에 곱한다), 대사 계수 c_rest·c_move
    # (drain = energy_drain·(c_rest + c_move·(v/herb_speed)²)), 에너지 보상을 순변화로 볼지(#4, false = v1 획득량)
    "speed": frozenset({"thresholds", "gait_speed", "gait_eat", "c_rest", "c_move", "net_energy_reward"}),
    # v2.2 (env_v2/world.py `_vigil_params`): 행동 vigilance 의 경계 문턱(a > threshold 면 경계), threat_recency 의
    # 스텝당 감쇠 계수(안 보이면 r ← decay·r), 경계 중 섭식 배수(want 에 곱한다, 4.4 표는 0), 경계 중 시야 각(도,
    # 360 = 모든 방향. 반경은 see_r 그대로, #5). 경계 중 속력 0·대사(speed 의 정지 대사)는 계수가 아니라 규칙이다.
    # threat_flee(10-03, 1-5 Gate E2b 의 10절 #18 변형용): 포식자가 안 보일 때 조향에 더하는 위협 반대 항
    # threat_flee·flee_weight·threat_recency·(−ThreatDir) 의 배수. 0 = 끔(1-4 구현 그대로, 규칙 5)
    "vigilance": frozenset({"threshold", "decay", "eat_mult", "fov_deg", "threat_flee"}),
    # v2.2r (env_v2/world.py `_window_params`, 10-03 R2·수정 제안서 3.1 (나)): vigilance 위에 얹는 스위치라 vigilance 를
    # 함께 켜야 한다. action = 경계 행동 열이 있나(false 면 관측 8·threat_recency 는 그대로 두고 행동 열만 뺀다 — T1·L),
    # window_only = 경계가 '창 안'(결정 때 포식자 안 보임 & threat_recency > theta)에서만 효력이 있나(W′),
    # look_back = 반사 돌아보기(정지 중이고 창 안이면 heading ← ThreatDir, L), theta = 창 문턱(Gate E2 의 θ 0.5).
    # 기능을 끄면(블록이 없으면) v2.2 그대로다 — vigilance 계수 키를 늘리지 않아 configs/v2_2.yaml 의 config_digest
    # (efc8f775f1e1)와 기록된 결과가 그대로 남는다(규칙 5 대신 새 기능 번호, 규칙 4)
    "vigil_window": frozenset({"action", "window_only", "look_back", "theta"}),
    # v2.4 (env_v2/world.py `_daynight_params`, 계획서 4.9.2·4.2·#21): speed 를 함께 켜야 한다. periods = 하루 길이 T
    # 목록(스텝, 짝수, reset 마다 하나), twilight = 전환 앞뒤 박명 폭(T 비율, 계획서 0.05), detect_night·eat_night·
    # rest_night = 어둠 d 에서 포식자 탐지 반경·섭식·정지 비경계 개체의 휴식 대사에 곱하는 (1 − x·d) 의 x(0 = 그 밤 효과
    # 끔, #21 이 Gate N 에서 실패한 항을 0 으로 뺀다), fixed_day_frac = 낮 고정 세계 비율(#27 기능 꺼진 세계, 1.0 이면
    # 모든 세계가 낮 = v2.1 동역학), transition_norm = 관측 to_transition 의 분모(계약 상수 900), start_induce = 시작
    # 상태 유도 비율(탐침 실패 때의 대응 1회, 0 = 끔: reset 의 해 질 녘 시작·낮은 에너지와 리스폰의 낮은 에너지).
    # rest_cover_only(10-06 v2.4b, results/v2/v2_4/MEMO.md 변경 기록): true 면 휴식 할인을 은신처 안(결정 때)에서 멈춘 개체만
    # 받는다. false = v2.4 그대로(규칙 5 의 끔 값)
    "daynight": frozenset({"periods", "twilight", "detect_night", "eat_night", "rest_night", "fixed_day_frac",
                           "transition_norm", "start_induce", "rest_cover_only"}),
    # v2.4s (env_v2/world.py `_pred_sleep_params`, 10-07 사용자 결정 A안 "밤에는 포식자도 자야 맞다"): daynight 를 함께
    # 켜야 한다. nocturnal_frac = 야행성 비율 q 의 범위 [하, 상](reset 마다 하나, 포식자마다 확률 q 로 야행성), sleep_dark =
    # 이 어둠 이상이면 주행성 포식자가 잔다(멈춤, 사냥 안 함, 초식 시야에 안 보임 — 굴에 있다), twilight_slow = 깨어 있는
    # 주행성 포식자의 속력에 (1 − d) 를 곱하나(박명에 느려진다)
    "pred_sleep": frozenset({"nocturnal_frac", "sleep_dark", "twilight_slow"}),
    # v3 R0 (env_v2/repertoire.py `parse_params`, 명세 RL_V3_R0_SPEC.md 2·3절): speed·daynight 를 함께 켜야 하고 vigilance 와는
    # 함께 켤 수 없다(행동 열이 'behavior' 하나가 된다). 잠금(스텝) lock_graze·lock_flee·lock_freeze, lock_hide = 은신처 도착 뒤
    # 최소 유지, hide_travel_max = 도착까지의 최대 잠금, sleep_enter·sleep_hold·sleep_wake = 잠 진입·최소 수면·기상(M4),
    # startle_steps = GRAZE → FLEE 놀람 정지(M2), c_still = 정지 탐지 배수(M1, FREEZE·도착 HIDE·SLEEP), cover_mult_crouch·
    # cover_mult_graze·cover_mult_sleep·cover_mult_other = 은신처 안의 웅크린 HIDE·GRAZE·SLEEP·그 밖 행동의 은신 배수(M6,
    # 표적 선택·포획 판정 모두), graze_head_down = GRAZE 의 자기 포식자 탐지 반경 배수(M5),
    # sleep_sight = SLEEP 의 자기 탐지 반경 배수, sleep_rest = SLEEP·은신처 안 휴식 할인 x(대사 × (1 − x·d)), graze_eat_min =
    # GRAZE 가 멈춰 먹는 셀 먹이 문턱, graze_forage·graze_cohesion = GRAZE·FLEE 조향 가중치, event_near·event_approach·
    # event_energy·event_dark = 사건 E2·E4·E5 문턱, decision_jitter = 사건 결정 지연 최대 J(스텝), recency_decay =
    # threat_recency 감쇠, steps_norm = 관측 '행동 경과' 분모, obs_extra = 추가 관측 9칸을 관측에 넣나(R0 는 false)
    "repertoire": frozenset({"lock_graze", "lock_flee", "lock_freeze", "lock_hide", "hide_travel_max", "sleep_enter",
                             "sleep_hold", "sleep_wake", "startle_steps", "c_still", "cover_mult_crouch",
                             "cover_mult_graze", "cover_mult_sleep", "cover_mult_other", "graze_head_down",
                             "sleep_sight", "sleep_rest", "graze_eat_min", "graze_forage", "graze_cohesion", "event_near", "event_approach", "event_energy",
                             "event_dark", "decision_jitter", "recency_decay", "steps_norm", "obs_extra"}),
    # v3 R0 (env_v2/world.py `_threats_params`, 명세 3절 M3·플레이어형 위협): daynight 를 함께 켜야 한다. stalk_frac = 잠행형
    # 비율 p_stalk 의 범위 [하, 상](reset 마다 하나), stalk_dist = 돌진을 시작하는 체감 거리, stalk_speed·pounce_speed·
    # exhaust_speed = 잠행·돌진·탈진 속력(× herb_speed), pounce_steps·exhaust_steps = 돌진 최대·탈진 스텝, player_frac = 플레이어가
    # 있는 세계 비율, player_speeds = [배회, 잠행, 돌진] 속력(× herb_speed), player_mode_steps = 배회·잠행 모드 길이 범위 [하, 상],
    # player_stalk_p = 모드를 새로 고를 때 잠행일 확률, player_charge_dist = 잠행 중 돌진을 시작하는 체감 거리,
    # player_charge_steps·player_rest_steps = 돌진 최대·휴식 스텝, player_catch_r·player_cooldown = 포획 거리·포획 뒤 쿨다운
    "threats": frozenset({"stalk_frac", "stalk_dist", "stalk_speed", "pounce_speed", "pounce_steps", "exhaust_speed",
                          "exhaust_steps", "player_frac", "player_speeds", "player_mode_steps", "player_stalk_p",
                          "player_charge_dist", "player_charge_steps", "player_rest_steps", "player_catch_r",
                          "player_cooldown"}),
    # v3 R2 M7 (env_v2/world.py `_stare_params`, 명세 RL_V3_R2_SPEC.md 2절): repertoire·threats 를 함께 켜야 한다.
    # target_lock = 잠행 위협(잠행형의 잠행 단계·플레이어 잠행 모드)이 표적을 잠그나(false = '지난 스텝 표적' 기록만, 표적
    # 선택은 그대로), spot_r = 노려보기가 통하는 실거리(0 = 노려보기 블록을 건너뛴다 — 중립), spot_cos = 눈맞춤 각의 cos,
    # spot_steps = 이어서 노려봐야 하는 스텝, balk_steps·balk_speed = 잠행형 물러남 스텝·속력(× herb_speed),
    # spotted_steps·spotted_charge_speed = 플레이어 '들킴' 스텝·들킨 돌진 속력 상한(× herb_speed)
    "stare_down": frozenset({"target_lock", "spot_r", "spot_cos", "spot_steps", "balk_steps", "balk_speed",
                             "spotted_steps", "spotted_charge_speed"}),
    # v3 R2 M8 (env_v2/world.py `_alarm_params`, 명세 3절): repertoire 를 함께 켜야 한다. alarm_r = 들리는 실거리,
    # alarm_steps = 경보가 남는 스텝(ttl), max_hop = 낼 수 있는 가장 큰 홉, hop_gain = 홉마다 곱하는 관측 세기,
    # relay_window = 원점 뒤 중계할 수 있는 스텝, event_alarm = 사건 E7 세기 문턱, on_catch = 잡힌 개체의 비명.
    # alarm_r 0 이고 on_catch false 면 블록 전체를 건너뛴다(중립)
    "alarm": frozenset({"alarm_r", "alarm_steps", "max_hop", "hop_gain", "relay_window", "event_alarm", "on_catch"}),
    # v3 현실성 1단계 (env_v2/world.py `_rz_*_params`, 정의·식·현실 근거는 world.py 모듈 docstring 'realism_*'). 다섯 다 repertoire 를
    # 함께 켜야 한다(realism_night 는 pred_sleep 도). 블록이 없으면(또는 enabled: false) 그 규칙이 없는 지금 세계와 비트 동일이다.
    # realism_vision: threat_fov_deg = 위협(포식자·플레이어)을 보는 시야각(도, [fov_deg 120, 360]), kin_fov_deg = 동족 시야각
    # (fov_deg 120 이면 지금 그대로)
    "realism_vision": frozenset({"threat_fov_deg", "kin_fov_deg"}),
    # realism_hearing: 위협의 지난 스텝 속력 s(× herb_speed)에서 소리 반경 R — s < s_silent 면 0, 아니면
    # r_quiet + (r_loud − r_quiet)·clip((s − s_quiet)/(s_loud − s_quiet), 0, 1). roam_quiet = 전력 걸음(표적 추격·돌진)이 아닌 위협의
    # s 를 s_quiet 에서 자르나, cap_to_sight = 들리는 반경을 그 사슴의 지금 탐지 반경(밤·행동 배수 포함)으로 자르나(학습 범위 보존
    # 장치 — 현실 규칙이 아니다)
    "realism_hearing": frozenset({"r_quiet", "r_loud", "s_silent", "s_quiet", "s_loud", "roam_quiet", "cap_to_sight"}),
    # realism_shelter: untargetable = 은신처 안 사슴을 표적 고르기·잠금에서도 빼나, player_too = 플레이어형 위협에도 적용하나
    "realism_shelter": frozenset({"untargetable", "player_too"}),
    # realism_night: settle_r = 눕지 못하게 하는 사슴까지의 실거리, hunt_dark = 이 어둠 이상이면 주행성 늑대가 새 사냥을 시작하지
    # 않는다(쫓던 사냥만 계속), night_floor = 해 진 뒤 깨어 있는 주행성 늑대의 속력 배수 하한(≤ 1 − pred_sleep.sleep_dark), spread =
    # 늑대마다 다른 잠·기상 지연의 최대(박명 폭 τ 비율), ramp_steps = 눕기·깨기에 걸리는 스텝(활동도 0 ↔ 1)
    "realism_night": frozenset({"settle_r", "hunt_dark", "night_floor", "spread", "ramp_steps"}),
    # realism_cover_food: cap_frac = 은신처 셀(은신처 원과 겹치는 셀, `World._cover_overlap_cells`) 먹이 용량 배수, regen_frac = 은신처
    # 셀 재생률 / 밖 재생률(v1 은 0.3). 선택 키 frac_range(아래 OPTIONAL_KEYS)를 쓰면 둘 다 null 로 둔다
    "realism_cover_food": frozenset({"cap_frac", "regen_frac"}),
    # v3 R3 (env_v2/world.py `_rz_chase_params`·`_rz_terrain_params`, 정의는 모듈 docstring 'R3 세계'). 둘 다 repertoire 를 함께 켜야 한다.
    # realism_chase: lost_steps = 고정한 표적이 늑대 시야(pred_view_r·pred_fov_deg) 밖에 있어도 놓지 않는 연속 포식자 스텝 수(그동안 마지막으로
    # 본 자리로 간다, 0 = 시야를 벗어난 스텝에 놓는다), stalk_phase = 잠행형의 잠행 접근·플레이어 잠행 모드에서도 고정하나(false = 돌진·
    # 플레이어 돌진부터만 — 명세 3-1 (f)), player_too = 플레이어형 위협에도 쓰나
    "realism_chase": frozenset({"lost_steps", "stalk_phase", "player_too"}),
    # realism_terrain: snow_frac·rough_frac = 눈·거친 땅 넓이 목표 범위 [하, 상](셀 비율, 세계마다 하나), zero_p = [눈, 거친 땅] 이 아예
    # 없는 세계의 확률, patch_r = 덩어리 원판 반지름 범위 [하, 상](단위), max_patches = 땅마다 원판 수 상한, mult_herb·mult_pred·
    # mult_player = [보통, 눈, 거친 땅] 속력 배수(사슴·늑대·플레이어형 위협, 보통은 1)
    "realism_terrain": frozenset({"snow_frac", "rough_frac", "zero_p", "patch_r", "max_patches", "mult_herb", "mult_pred",
                                  "mult_player"}),
    # 언리얼 통합 무대 거울 (env_v2/world.py `_ist_params`, 정의는 모듈 docstring '통합 무대'). repertoire·threats 를 함께 켜야 한다. 모든 키가
    # 끔 값이면(respawn true, 나머지 null) 블록을 켜도 끈 세계와 비트 동일이다(tests/test_unreal_mirror.py).
    #   respawn = 죽은 슬롯을 되살리나(false = 시체로 남고 다음 스텝부터 관측·표적·먹이·이동·번식에서 빠진다 — C++ bRespawnDead false),
    #   ema_den = 피식 EMA 분모(null = 슬롯 수 N — C++ PredEmaDenominator = 계획한 사슴 수),
    #   day_offset = 시작 낮밤 위상 o(null = daynight 스트림이 뽑은 값, 0 = 언리얼 DayOffset 0 — t = 0 이 새벽 전환 d = 0.5),
    #   cover_layout = 'quad'(무대 1/4·3/4 지점 은신처, C++ 우리 은신처) 또는 null(v1 무작위 원), cover_count·cover_r_frac = quad 의 수·반경 비율
    #   (반경 = clip(cover_r_frac × 한 변, cover_r_min, cover_r_max)),
    #   wolf_kinds = 'alternate'(늑대 슬롯 짝수 잠행형·홀수 근접 추격형, 모두 주행성 — C++ WolfSpecForOrdinal) 또는 null(threats 스트림이 뽑은 구성),
    #   start_layout = 'stage'(C++ PlanStage: 늑대는 무대 모서리 쪽, 사슴은 무대 균등·늑대에게서 멀리) 또는 null(v1 맵 균등), wolf_corner_frac·
    #   wolf_gap·deer_wolf_gap·deer_margin·deer_spacing = stage 의 계수(단위),
    #   head_layout = 'golden'(C++ 조정자의 순번 × 2.399963 rad 시작 방향) 또는 null(v1 무작위 각)
    "integrated_stage": frozenset({"respawn", "ema_den", "day_offset", "cover_layout", "cover_count", "cover_r_frac", "wolf_kinds",
                                   "start_layout", "wolf_corner_frac", "wolf_gap", "deer_wolf_gap", "deer_margin", "deer_spacing",
                                   "head_layout"}),
    # 야생 1단계 (env_v2/world.py `_wild_*_params`, 정의는 모듈 docstring '야생 1단계'). 셋 다 daynight 를 함께 켜야 한다(시간 계수를 게임 하루
    # 단위로 적고 하루 길이 dn_period 로 스텝을 낸다). 끄면 지금 세계와 비트 동일이다(tests/test_wild1.py).
    #   wild_reserve: reserve_days = 가득 찬 비축이 걷기 대사(× energy_drain)만으로 버티는 게임 하루 수(비축 용량 = reserve_days × 하루 스텝 ×
    #   energy_drain, E 단위), init = 시작·새 개체 비축 R(0~1), refill_e = 이 E 이상일 때만 먹은 몫의 일부를 R 로 옮긴다, refill_frac = 옮기는 몫,
    #   weak_e = E 가 이것보다 낮으면 약하다(비축으로 사는 몸), weak_speed = 약한 사슴의 이동 속력 배수(1 = 약해지지 않음)
    "wild_reserve": frozenset({"reserve_days", "init", "refill_e", "refill_frac", "weak_e", "weak_speed"}),
    #   wild_satiation: sat_days = 먹기(pred_eat_cd)가 끝난 뒤 사냥하지 않고 쉬는 게임 하루 수, rest_speed = 쉬는 동안 배회 속력 배수. threats 또는
    #   repertoire 를 함께 켜야 한다(v3 포식자 스텝)
    "wild_satiation": frozenset({"sat_days", "rest_speed"}),
    #   wild_flight: alert_r·flight_r·safe_r = 경계·도주·안전 거리(단위, 1 단위 = 2 m), approach = '다가옴' 접근 관측 문턱, alert_w = 경계 중 먹으며
    #   멀어지는 조향 항 무게, rest_alert = 쉬는·먹는 늑대도 경계(멀어지기)만 일으키나, shelter_cos·shelter_r = 도주 때 고르는 은신처(늑대 반대쪽
    #   ±acos(shelter_cos) 안, 가장자리까지 shelter_r 안), crouch = 은신처 안에서 사냥 중인 늑대를 알아채면 웅크리나, wall_margin = 무대 벽 미끄러짐
    #   여유(단위). repertoire 를 함께 켜야 한다
    "wild_flight": frozenset({"alert_r", "flight_r", "safe_r", "approach", "alert_w", "rest_alert", "shelter_cos", "shelter_r",
                              "crouch", "wall_margin"}),
    # 야생 2단계 2 (env_v2/world.py `_wild_pack_params`·`pack_goals`, 정의는 모듈 docstring '야생 2단계' 2). threats 를 함께 켜야 한다(늑대 유형·상태).
    #   wild_pack: join_r = 동료가 쫓는 사슴이 이 실거리(단위) 안이면 돕는다, lead = 은신처가 없을 때 사슴 도주선 앞쪽 거리(단위), door_r·door_cos =
    #   사슴이 향하는 은신처(가장자리까지 door_r 안, 도주 방향 ±acos(door_cos) 안), wait_r = 목표 자리에 이만큼(단위) 가까우면 멈춰 사슴 쪽을 보고 기다린다
    "wild_pack": frozenset({"join_r", "lead", "door_r", "door_cos", "wait_r"}),
    # 야생 2단계 3 세로 장애물 (env_v2/world.py `_obstacles_params`·`obstacle_layout`·`obstacle_slide`·`sight_blocked`, 정의는 모듈 docstring '야생 2단계' 3).
    #   obstacles: tree_per_ha·rock_per_ha = 무대 1 ha 마다 나무 줄기·바위 수, tree_r·rock_r = 반지름 [하, 상](단위, 1 단위 = 2 m — 세계마다 자기 스트림
    #   part 0 에서 U[하, 상]), body_r = 몸 반지름(단위 — 이동은 원판 반지름 + body_r 앞에서 멈춰 미끄러진다), block_sight = 원판이 눈길을 가리나(발소리는
    #   못 가린다), no_food = 원판 밑 먹이 셀 용량을 원판이 덮은 몫만큼 줄이나. 선택 키 fixed(아래 OPTIONAL_KEYS)
    "obstacles": frozenset({"tree_per_ha", "tree_r", "rock_per_ha", "rock_r", "body_r", "block_sight", "no_food"}),
    # 야생 3단계 지역 날씨 (env_v2/world.py `_wild_weather_params`·`weather_mults`, 정의는 모듈 docstring '야생 3단계'). speed·daynight·repertoire 를
    # 함께 켜야 하고(시야는 밤 탐지 반경에 곱한다, 늑대 시야는 v3 포식자 스텝), 청각 배수가 1 보다 작으면 realism_hearing 도 켜야 한다.
    #   wild_weather: region = 이 세계가 흉내 내는 지역 이름(regions 의 키 — 짝 비교 실행기가 지도마다 덮는다), regions = 지역 → [날씨, 세기]
    #   (날씨 clear·rain·snow, 세기 0~1, 맑음은 세기 0), rain_sight·rain_hear·snow_sight·snow_hear = 세기 1 일 때 시야(사슴 위협 탐지 반경과 늑대 시야
    #   반경)·사슴 청각(위협 발소리 반경) 배수, snow_deer_speed·snow_wolf_speed = 세기 1 일 때 눈의 사슴·늑대(모든 위협) 이동 속력 배수(모두 (0, 1] —
    #   세기 I 의 배수는 1 − (1 − 값)·I), obs_visibility = 관측 visibility 에 시야 배수를 곱하나(계획서 RL_V2_PLAN.md 4.2 표 9·#25 의 w).
    #   선택 키 schedule(아래 OPTIONAL_KEYS)
    "wild_weather": frozenset({"region", "regions", "rain_sight", "rain_hear", "snow_sight", "snow_hear", "snow_deer_speed",
                               "snow_wolf_speed", "obs_visibility"}),
    # R5 장애물 관측 (env_v2/world.py `_obstacle_obs_params`·`obstacle_obs_values`, 정의는 모듈 docstring 'R5 장애물 관측'). 다른 기능이 없어도 켤 수 있다
    # (원판이 없으면 칸이 벽 거리·1·0 이다). 원판·몸 반지름은 obstacles 블록이 정한다.
    #   obstacle_obs: escape_norm = 관측 escape_room(도망칠 쪽 빈 거리)의 분모(단위, 1 단위 = 2 m), near_norm = 관측 obstacle_near(몸 가장자리에서 가장 가까운
    #   원판 가장자리까지)의 분모(단위). 둘 다 0 보다 크다. 관측 = clip(거리 ÷ 분모, 0, 1)
    "obstacle_obs": frozenset({"escape_norm", "near_norm"}),
})

# 선택 계수 키(모듈 docstring 규칙 6, 10-14 R3): 기능 → {키: 끔 값}. 켠 블록에 없으면 끔 값(= 앞 버전 동작)으로 읽는다. 앞 버전 설정
# 파일(configs/v3_real1_*.yaml)을 고치지 않으려고 둔다 — 새 설정은 모두 적는다.
#   realism_shelter.block_predators: 늑대(player_too 면 플레이어형 위협도)가 은신처 원에 들어가지 못하고 원 둘레를 따라 미끄러진다
#     (H17, env_v2/world.py `_rz_wall_push`). 사슴은 그대로 드나든다. false = 1단계 그대로(늑대가 원을 지나다닌다)
#   realism_cover_food.frac_range: [하, 상] 이면 세계마다 f ~ U[하, 상] 하나를 자기 스트림 part 0 에서 뽑아 용량·재생 배수에 함께 쓴다
#     (H7, cap_frac·regen_frac 는 null). null = 1단계 그대로(cap_frac·regen_frac 고정, 난수 없음)
#   threats.eat_in_place (10-15 사람 결정 '먹는 시간 주기 (약 5초)'): 늑대(플레이어형 위협 말고 모든 포식자)가 사슴을 잡은 뒤 쿨다운
#     (v1 키 pred_eat_cd)이 남은 동안 그 자리에 서서 먹는다(env_v2/world.py `_step_predators_v3`, 모듈 docstring 'R3 세계' (j)). 먹는 시간
#     자체는 v1 키 pred_eat_cd 를 overrides 로 덮는다(R3 설정은 38스텝). false = 지금까지 그대로(쿨다운 동안 기본 속력으로 배회)
#   wild_flight.hold_awake·edge_r (10-16 사용자 '늑대가 먹기 시작하면 도망치던 사슴이 멈춘다'·'가장자리에서 늑대가 계속 잡아먹는다'): hold_awake
#     true 면 시작한 도주는 깨어 있는 늑대(사냥·먹기·배부름 — 자는 늑대 말고) 모두가 실거리 safe_r 밖이 되거나 은신처 안일 때까지 이어진다
#     (도주를 일으키는 것은 그대로 사냥 중인 늑대만). edge_r > 0 이면 도주·경계 방향이 무대 가장자리 edge_r 안에서 벽 쪽 성분을 벽을 따라가는
#     성분으로 돌리고 모서리를 벗어나는 쪽을 고른다(env_v2/world.py `wf_edge_steer`). false·0 = 10-15 그대로
#   obstacles.fixed (10-17 야생 2단계 3): [[x, y, r], …](단위) 이면 무작위 배치 대신 이 원판을 쓴다(난수를 뽑지 않는다 — 언리얼 무대에서 읽은 원판으로 거울을
#     돌리는 짝 비교용, results/v3/mirror/run_mirror.py --unreal-obstacles). null = 자기 스트림 part 0 으로 무작위 배치
#   obstacles.detour·detour_* (10-17 장애물 돌아가기, env_v2/world.py `detour_moves`, 모듈 docstring '야생 2단계' 3 의 6)): detour true 면 사슴·늑대가 원판에
#     막히면(부딪혀 가려던 쪽으로 detour_block 몫도 못 감) 가려던 방향에서 가장 적게 돈 빈 방향(한 스텝에 detour_free 몫 이상 나아감 — 22.5° 씩 16 방향)으로
#     돌아가고, 앞 보기 detour_probe(단위)가 트이거나 detour_steps 스텝이 지날 때까지 같은 쪽으로 돈다. 돕는 늑대는 detour_help_block 스텝 넘게
#     돌아가거나 막혀 돌아서면 detour_help_drop 스텝 동안 돕지 않는다(길목 자리를 버리고 다시 고른다). false = 10-17 3 그대로(미끄러짐만). 숫자 키 기본값은
#     켰을 때 쓰는 값이다(끄면 읽지 않는다)
#   realism_shelter.wolf_margin (10-17 늑대 몸 여유): 막는 위협이 은신처 원 둘레가 아니라 반지름 r + wolf_margin(단위, 1 단위 = 2 m) 둘레를
#     따라 미끄러진다(늑대 중심이 그 안에 들지 않는다). block_predators 를 켰을 때만 0 보다 클 수 있다. 사슴의 안전 판정(원 안 |q − c| ≤ r)은
#     그대로다. 0 = 10-16 그대로(원 둘레에서 미끄러짐)
#   wild_weather.schedule (10-18 야생 3단계, 시간에 따라 바뀌는 날씨의 자리): {지역: [[시작 스텝, 날씨, 세기], …]}(시작 스텝은 reset 뒤 세계 t, 0 이상이고
#     늘어나는 정수) 이면 그 지역 세계는 시작 스텝 ≤ t 인 마지막 줄의 날씨를 쓰고, 첫 줄 앞이거나 표에 없는 지역은 regions 의 고정 날씨를 쓴다. 난수 없음.
#     null = 고정 날씨(지역마다 늘 같다)
#   integrated_stage.respawn_safe_r·respawn_tries (10-18 R4 학습 보충, 사람 결정 RL_V2_PLAN.md 10-18 (15) D2 — 학습 세계 전용, 판정 세계·언리얼에는 없다):
#     respawn true 세계에서 respawn_safe_r(단위, 1 단위 = 2 m)가 숫자면 죽은 사슴이 다음 스텝에 무대 안 새 자리에 다시 나는데, 그 자리는 모든 늑대(위협)에게서
#     respawn_safe_r 이상, 원판(r + 몸) 밖, 은신처 원 밖이다(자기 스트림 part 1 에서 후보 respawn_tries 개, 다 못 맞추면 늑대에게서 가장 먼 후보 — env_v2/world.py
#     `_ist_safe_spawn`). v1 리스폰 뽑기(자리·각)는 그대로 하고 자리만 덮는다(규칙 2). null = v1 그대로(맵 균등 자리)
OPTIONAL_KEYS: Mapping[str, Mapping[str, Any]] = MappingProxyType({
    "realism_shelter": MappingProxyType({"block_predators": False, "wolf_margin": 0.0}),
    "realism_cover_food": MappingProxyType({"frac_range": None}),
    "threats": MappingProxyType({"eat_in_place": False}),
    "wild_flight": MappingProxyType({"hold_awake": False, "edge_r": 0.0}),
    "obstacles": MappingProxyType({"fixed": None, "detour": False, "detour_block": 0.5, "detour_free": 0.8, "detour_probe": 1.5,
                                   "detour_steps": 45, "detour_help_block": 15, "detour_help_drop": 38}),
    "wild_weather": MappingProxyType({"schedule": None}),
    "integrated_stage": MappingProxyType({"respawn_safe_r": None, "respawn_tries": 64}),
})


def with_optional(name: str, p: Mapping[str, Any]) -> dict[str, Any]:
    """기능 `name` 의 계수(`Features.params`)에 빠진 선택 키를 끔 값으로 채운 사본(규칙 6). 선택 키가 없는 기능은 그대로다."""
    out = {k: copy.deepcopy(v) for k, v in OPTIONAL_KEYS.get(name, {}).items()}
    out.update(p)
    return out


@dataclass(frozen=True)
class Features:
    """검증을 마친 `features:` 블록. 등록된 이름만 들어 있다."""

    blocks: Mapping[str, Mapping[str, Any]]

    def enabled(self, name: str) -> bool:
        _check_name(name)
        return bool(self.blocks.get(name, {}).get("enabled", False))

    def params(self, name: str) -> dict[str, Any]:
        """`enabled` 를 뺀 블록의 나머지 키. 깊은 사본이라 고쳐도 설정과 다른 세계에 번지지 않는다."""
        _check_name(name)
        return copy.deepcopy({k: v for k, v in self.blocks.get(name, {}).items() if k != "enabled"})

    @property
    def active(self) -> tuple[str, ...]:
        """켜진 기능 이름을 번호 순으로."""
        return tuple(n for n in FEATURE_IDS if self.enabled(n))

    def __reduce__(self):
        # MappingProxyType 은 pickle 이 안 된다. World 를 deepcopy·pickle 할 수 있게 보통 dict 로 넘겨
        # 다시 만든다. 이미 검증한 값이라 다시 검증하지 않는다(받는 쪽의 IMPLEMENTED 와 무관하게 복원).
        return (_rebuild_features, ({k: copy.deepcopy(dict(v)) for k, v in self.blocks.items()},))


def _freeze(blocks: Mapping[str, Mapping[str, Any]]) -> Features:
    return Features(MappingProxyType({k: MappingProxyType(dict(v)) for k, v in blocks.items()}))


def _rebuild_features(blocks: Mapping[str, Mapping[str, Any]]) -> Features:
    return _freeze(blocks)


def _check_name(name: str) -> None:
    if name not in FEATURE_IDS:
        raise KeyError(f"등록되지 않은 V2 기능 '{name}'. 등록된 기능: {', '.join(FEATURE_IDS)}")


def _check_part(part: Any) -> None:
    if isinstance(part, bool) or not isinstance(part, (int, np.integer)) or not 0 <= part < _U32:
        raise ValueError(f"part 는 0 이상 2^32 미만의 정수여야 한다. 받은 값: {part!r}")


def _looks_numeric(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    try:
        float(v)
    except ValueError:
        return False
    return True


def _check_values(name: str, key: str, v: Any) -> None:
    items = v if isinstance(v, (list, tuple)) else [v]
    for x in items:
        if _looks_numeric(x):
            raise ValueError(
                f"features.{name}.{key} 의 값 {x!r} 가 문자열이다. PyYAML 은 '1e-3'·'1.0e3' 같은 지수 "
                f"표기를 문자열로 읽는다. 소수점과 지수 부호를 넣어 1.0e-3, 1.0e+3 처럼 쓴다"
            )


def parse_features(raw: Mapping[str, Any] | None, implemented: frozenset[str] | None = None,
                   param_keys: Mapping[str, frozenset[str]] | None = None) -> Features:
    """`cfg.v2["features"]` 를 검증한다. 형식이 틀리면 ValueError, 모르는 이름이면 KeyError.

    `implemented`·`param_keys` 를 주지 않으면 이 모듈의 `IMPLEMENTED`·`PARAM_KEYS` 를 그때그때 읽는다
    (테스트에서 바꿀 수 있게).
    """
    if implemented is None:
        implemented = IMPLEMENTED
    if param_keys is None:
        param_keys = PARAM_KEYS
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ValueError(f"features 는 기능 이름 → 블록(dict) 이어야 한다. 받은 값: {raw!r}")
    blocks: dict[str, Mapping[str, Any]] = {}
    for name, block in raw.items():
        _check_name(name)
        if block is None:
            block = {}
        if not isinstance(block, Mapping):
            raise ValueError(
                f"features.{name} 는 {{enabled: true|false, ...}} 꼴의 블록이어야 한다. 받은 값: {block!r}"
            )
        for key, v in block.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"features.{name} 의 키는 문자열이어야 한다(YAML 1.1 에서 on/yes/off 는 bool 이다). "
                    f"받은 키: {key!r}"
                )
            if key != "enabled":
                _check_values(name, key, v)
        on = block.get("enabled", False)
        if not isinstance(on, bool):
            raise ValueError(f"features.{name}.enabled 는 true/false 여야 한다. 받은 값: {on!r}")
        if on and name not in implemented:
            raise ValueError(
                f"V2 기능 '{name}' 은 아직 구현되지 않았다. 켜도 세계가 바뀌지 않으므로 끈 채로 둔다 "
                f"(구현된 기능: {', '.join(sorted(implemented)) or '없음'})"
            )
        if name in implemented:
            known = param_keys.get(name, frozenset())
            # 선택 키(규칙 6)는 알고 있는 키이지만 빠져도 된다(끔 값으로 읽는다)
            unknown = sorted(set(block) - {"enabled"} - set(known) - set(OPTIONAL_KEYS.get(name, {})))
            if unknown:
                raise ValueError(
                    f"features.{name} 에 모르는 키 {unknown} 가 있다(오타?). 쓸 수 있는 키: "
                    f"enabled, {', '.join(sorted(known)) or '(계수 없음)'}"
                    + (f" (선택 키 {', '.join(sorted(OPTIONAL_KEYS[name]))})" if name in OPTIONAL_KEYS else "")
                )
            missing = sorted(set(known) - set(block))
            if on and missing:
                raise ValueError(
                    f"features.{name} 을 켜려면 계수 {missing} 를 적어야 한다. 계수는 yaml 이 유일한 원본이다"
                )
        blocks[name] = dict(block)
    return _freeze(blocks)


def features_of(cfg) -> Features:
    """설정 객체에서 기능 블록을 읽는다. v1 Config 처럼 `v2` 가 없으면 모두 꺼진 것으로 본다."""
    v2 = getattr(cfg, "v2", None) or {}
    return parse_features(v2.get("features"))


def feature_stream(seed: int, name: str, part: int = 0) -> np.random.Generator:
    """세계 시드 `seed` 에서 기능 `name` 의 `part` 번 난수 스트림을 만든다."""
    _check_name(name)
    _check_part(part)
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or not 0 <= seed < _U32:
        raise ValueError(f"seed 는 0 이상 2^32 미만의 정수여야 한다. 받은 값: {seed!r}")
    return np.random.default_rng([int(seed), STREAM_DOMAIN, FEATURE_IDS[name], int(part)])
