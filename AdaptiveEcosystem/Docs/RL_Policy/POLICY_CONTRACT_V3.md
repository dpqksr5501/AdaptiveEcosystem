# POLICY CONTRACT V3 — 행동 레퍼토리 두뇌(RL R1b · 규칙 FSM_R2) 계약

> 판: **3.0.0 초안** (2026-10-13). 사람 확인 전이다.
> 스키마: `EcoPolicyV3::kSchemaVersion = 3` (제안. v1은 `PolicySchemaVersion = 1`, `S/AI/Policy/EcoPolicyContracts.h:15`)
> 적용: Unreal Engine 5.8 C++ (엔진 무관 헤더 + Mass 연결) · Python 3.10+ (`herbivore_rl/`, Stable-Baselines3)
> 원칙: **이 문서의 모든 수치·순서·자르기·동점 규칙은 파이썬 코드에서 가져왔다. 코드와 명세가 다르면 코드가 이긴다.** 다른 곳은 13절에 모았다.

- 경로 표기: `H/` = `herbivore_rl/`, `D/` = `AdaptiveEcosystem/Docs/`, `S/` = `AdaptiveEcosystem/Source/AdaptiveEcosystem/`.
- 근거 표기: `H/env_v2/repertoire.py:399-455`처럼 파일과 줄을 적는다. 기준은 Branch_Sinhyeok `cd19a43` 작업 트리다.
- 이 문서의 목표: C++ 기술자가 이 문서만 보고 파이썬 v3 경로가 결정 스텝마다 하는 일을 **논리 상태 수준에서 비트 단위로** 다시 만들 수 있게 한다. 논리 상태 = 행동·위상·경과·seq·잠금·사건 대기·경보 칸·위협 상태·정수 카운터, 그리고 그것을 정하는 비교 결과다. 위치·속도 같은 실수는 11절의 허용 오차로 맞춘다.
- v1 계약(`D/RL_Policy/POLICY_CONTRACT_V1.md`)과 v1 C++ 경로는 바꾸지 않는다. v3는 새 경로다.

---

## 1. 개요

### 1-1. 두 두뇌

두 두뇌는 **같은 세계 규칙**(행동 실행기 Arbiter, 행동별 제어기, 위협 모델)을 쓴다. 다른 것은 요청을 만드는 방법과 관측·마스크 판, 경보 기능 하나다.

| | (A) RL 두뇌 R1b | (B) 규칙 두뇌 FSM_R2 |
|---|---|---|
| 쓰는 세계 | 경보 **없는** 세계. 학습 `H/configs/v3_r1.yaml`, 판정·배포 기준 `H/configs/v3_r1_on.yaml` | 경보(M8) **있는** 세계 `H/configs/v3_r2_on.yaml` |
| 요청을 만드는 것 | 망 18 → 64 → 64 → 로짓 5, 마스크 로짓의 argmax | 관측만 보는 손 규칙 (9절) |
| 모델·규칙 | `H/ckpt/v3/v3_r1_g995_s3_20m.zip` (R1b 출시, `H/results/v3/r1b/report.md` 1절) | `H/repertoire_rules.py:272-296` `fsm_r2_spec(stare=False, look=True)`, 판정 도구 경로 `H/eval_v3.py:277-285` |
| 관측 | 18칸 (2절) | 19칸 = 18 + `alarm_heard` (2절) |
| 마스크 | 판 2 (3절) | 규칙은 마스크를 쓰지 않는다. 세계 판은 3이다 (3절) |
| 사건 | E1~E6 | E1~E7 (E7은 경보) |
| 허용 행동 | GRAZE·FLEE·HIDE·FREEZE (SLEEP 막음) | 규칙이 GRAZE·HIDE·FREEZE만 낸다 (9절) |
| 배포 분포 | argmax, ε 없음 | 결정적 규칙 |

- 왜 경보 세계의 두뇌가 규칙인가: R2 RL이 사전 등록 조기 중단에 두 번 걸려 실패로 닫혔다(5M U_FREEZE′ < 0.1, 첫 학습 4시드·대응 학습 3시드). 그래서 경보 세계의 두뇌는 FSM_R2다(`H/results/v3/r2/judge/PREREG.md:373-389`).
- R1b 모델은 판 2라 경보 세계에서는 판정 도구가 거부한다(`H/env_v2/rep_policy.py:151-161`, `H/env_v2/rollout.py:726-736`). 언리얼도 **R1b 두뇌를 쓰는 개체에는 M8을 켜지 않는다**.
- 노려보기 M7(대치·물러남·플레이어 들킴)은 10-13 사람 결정으로 R2에서 빠졌으므로 이 계약에 넣지 않는다(`D/RL_Policy/RL_V3_R2_SPEC.md:3-9`).
- **사람 결정 10-13 (3): 게임에는 (A) RL 두뇌 R1b를 모든 사슴에 쓴다.** 동족 경보는 연출(소리·고개 들기 등)로만 내고, 사슴의 관측·마스크·사건에는 넣지 않는다. 그래서 게임 세계의 행동 논리는 R1b가 배운 경보 없는 세계(`H/configs/v3_r1_on.yaml`)와 같다. (B) FSM_R2는 이 문서에 기록과 대조용으로 남긴다. 까닭: FSM_R2는 도망을 쓰지 않는다(13-1 D5).

### 1-2. 판과 설정

| 항목 | R1b | FSM_R2 | 근거 |
|---|---|---|---|
| 설정 version | `3.r1` | `3.r2` | `H/configs/v3_r1_on.yaml:6`, `H/configs/v3_r2_on.yaml:10` |
| 관측 수 `kObsDim` | 18 | 19 | `H/env_v2/world.py:284-304` |
| 마스크 판 `kMaskVersion` | 2 | 3 | `H/env_v2/rep_policy.py:73-74,146-148` |
| 행동 수 `kNumBehaviors` | 5 | 5 | `H/env_v2/repertoire.py:156-157` |
| 허용 | graze, flee, hide, freeze | (같은 목록, 규칙은 flee를 내지 않는다) | `H/configs/v3_r1_on.yaml:180`, `H/configs/v3_r2_on.yaml:207` |
| 두 설정의 동역학 차이 | — | `alarm` 블록 하나 | `H/configs/v3_r2_on.yaml:5-6,174-189` |

두 설정의 다른 세계 계수는 글자 그대로 같다(`H/configs/v3_r1_on.yaml:24-163`과 `H/configs/v3_r2_on.yaml`의 같은 블록). 바탕 상수는 `H/configs/default.yaml`이고, 덮는 것은 `rand.pred_speed_mult: [0.6, 0.95]` 하나다(`H/configs/v3_r1_on.yaml:20-22`).

### 1-3. 행동 번호 (계약, 뜻을 바꾸지 않는다)

| 번호 | 이름 | C++ `EEcoBehavior` |
|---|---|---|
| 0 | GRAZE 먹기 | Graze |
| 1 | FLEE 도망 | Flee |
| 2 | HIDE 숨기 | Hide |
| 3 | FREEZE 얼기 | Freeze |
| 4 | SLEEP 잠 | Sleep |

- 근거 `H/env_v2/repertoire.py:8-9,156`.
- 위상 `phase`: 0 진입, 1 지속, 2 이탈(`:159`).
- 보행 번호: 0 정지, 1 걷기, 2 뛰기(`:162`, `H/env_v2/world.py:95`).

**SLEEP은 두 두뇌 모두에서 일어나지 않는다.** R1b는 허용 마스크가 막고(4절), FSM_R2는 SLEEP 줄이 없다(9절). 시작·리스폰은 GRAZE다(`H/env_v2/repertoire.py:302,335`). 그래서 SLEEP 진입·기상·E3·휴식 할인·SLEEP 시야·SLEEP 은신 배수는 계약에 적지만 **두 두뇌의 궤적에 나타나지 않는다**. C++은 상태 칸과 분기를 그대로 두되, 골든은 SLEEP 경로를 시험하는 단위 골든 하나만 둔다(11절).

### 1-4. 계약 해시 안

**v1은 어떻게 하나 (읽기만 했다)**
- 해시가 없다. 정수 판 `PolicySchemaVersion = 1` 하나다(`S/AI/Policy/EcoPolicyContracts.h:15`, `S/AI/Policy/EcoPolicyInference.cpp:53-58`).
- 가중치 헤더 `PolicyWeights.h`에는 층·활성 함수·정규화·생성 시각·출처 경로 주석만 있다(`H/export_weights.py:104-131`).
- 단위 상수 헤더 `EcoBehaviorConfig.h`도 값만 있고 해시가 없다(`H/export_weights.py:220-284`, `S/AI/Policy/EcoBehaviorConfig.h:15-39`).
- 시즌 계획은 실행 중 로더용으로 '계약 상수를 4바이트 워드로 싣고 비트 비교, 체크섬 FNV-1a 64'를 제안했다(`D/RL_Policy/RL_SEASON_RETRAIN_PLAN.md:495-503,844`).

**v3에 이미 있는 것** (다른 작업이 만드는 중이고 아직 커밋 전이다. 읽기만 했다)
- `H/export_weights_v3.py:170-191`의 `contract_dict`·`contract_hash`가 **입출력 계약 해시**를 낸다.
  - 담는 것: 관측 이름 열, 행동 이름 열, 망(은닉 [64, 64], tanh, 로짓 머리, 망이 마스크를 보지 않음), 마스크(판, `THREAT_RECENCY_OBS`, `HIDE_COVER_OBS`, 판 3이면 `ALARM_MASK_OBS`, `MASK_LOGIT`, 마스크 칸 판정 '> 0.5'), 선택 규칙(마스크 argmax, 동점이면 낮은 번호).
  - 식: 정규 JSON(키 정렬, 공백 없음)의 sha256 앞 16자리 → uint64.
  - 가중치는 넣지 않는다. 모델 지문(zip sha256)은 헤더 주석에 따로 적는다.
- 알려진 값과 C++ 확인(`S/AI/Policy/EcoPolicyV3Inference.h`, 같은 작업):
  - 관측 18·판 2 = `0x7eea0107339be4ce`
  - 관측 19·판 3 = `0xf8c26c7d02542fae`
  - 생성 헤더의 `kContractHash`가 둘 중 하나가 아니면 `static_assert`로 빌드가 멈춘다.

**제안: 세계 계약 해시를 하나 더 둔다**
- 입출력 해시는 망 앞뒤만 지킨다. Arbiter·제어기·위협·경보·규칙 상수가 조용히 어긋나는 것은 막지 못한다. 그래서 같은 방식(정규 JSON sha256 앞 16자리)으로 `kWorldContractHash`를 더한다.
- 헤더:
  - RL 두뇌는 `PolicyWeightsV3.h`가 `kContractHash`와 `kWorldContractHash`를 함께 담는다.
  - 규칙 두뇌는 가중치가 없으므로 `PolicyRuleV3.h`(새 파일, 이름은 제안)가 같은 두 해시와 규칙 상수를 담는다.
- **세계 해시에 넣는 키** (값은 이 문서의 표와 같다)
  1. 관측 정규화·기하: `see_r`, `fov_deg`, `obs_pred_count_norm`, `obs_kin_count_norm`, `obs_cover_norm`, `max_energy`, `food_cell`, `food_grad_blur`, `detect_night`, `transition_norm`, `twilight`, `steps_norm`, `recency_decay`, `herb_speed`, `predation_ema_decay`, `predation_ema_gain`
  2. Arbiter: `lock_graze`, `lock_flee`, `lock_freeze`, `lock_hide`, `hide_travel_max`, `sleep_enter`, `sleep_hold`, `sleep_wake`, `startle_steps`, `decision_jitter`, `JITTER_TAG`, `event_near`, `event_approach`, `event_energy`, `event_dark`
  3. 제어기: `gait_speed[3]`, `gait_eat[3]`, `c_rest`, `c_move`, `energy_drain`, `graze_forage`, `graze_cohesion`, `sep_weight`, `sep_radius`, `flee_weight`, `graze_eat_min`, `graze_head_down`, `sleep_sight`, `sleep_rest`, `eat_night`, `food_eat_rate`, `food_energy_per_unit`, `repro_threshold`, `repro_cd`, `init_energy`
  4. 위협: `c_still`, `cover_mult_crouch/graze/sleep/other`, `pred_view_r`, `pred_fov_deg`, `pred_melee_catch_r`, `pred_ranged_catch_r`, `pred_ranged_catch_p`, `pred_ranged_speed_mult`, `pred_wander_turn`, `pred_eat_cd`, `sleep_dark`, `twilight_slow`, threats 블록 전부
  5. 경보(판 3 세계만): alarm 블록 전부(`alarm_r`, `alarm_steps`, `max_hop`, `hop_gain`, `relay_window`, `event_alarm`, `on_catch`), `OWN_RECENCY`, 그리고 11-3의 `kAlarmHeard` 표
  6. 규칙(규칙 두뇌만): θ 4, a 0.9, `near` 6, `fast` 0.9, `cover_near` 5, look `alarm` 0.4, look `cover_far` 5, 래퍼 순서
- **넣지 않는 것**: 세계 무작위화 범위(`rand.*`), 보상 계수, 학습 계수(ε, init_probs, f_dec, ent_coef), 생성 시각, 경로. 배포 동작을 바꾸지 않는 값이다.
- **C++ 쪽 확인**
  - `static_assert(kNumBehaviors == (int)EEcoBehavior::Count)`와 지금 있는 입출력 해시 `static_assert`를 그대로 쓴다.
  - 세계 해시는 C++에서 sha256을 다시 계산하기보다 생성 헤더의 상수 표(`kWorldConstants[]`)를 엔진 무관 헤더가 실제로 쓰는 `constexpr`와 하나씩 비교하는 자동화 시험으로 지킨다.
  - 실행 중 가중치 로더(e3)는 파일의 두 해시가 컴파일 값과 다르면 거부한다.
- 판을 올리는 때:
  - 관측·마스크·선택 규칙이 바뀌면 입출력 해시가 바뀐다.
  - 세계 규칙 상수가 바뀌면 세계 해시가 바뀐다.
  - 가중치만 바뀌면 모델 지문만 바뀐다.
- 시즌 계획의 FNV-1a 64(`D/RL_Policy/RL_SEASON_RETRAIN_PLAN.md:502`)는 `.ecopol` 파일 체크섬이다. 계약 해시와 목적이 다르므로 둘 다 둔다.

---

## 2. 관측 18 / 19

### 2-1. 언제 계산하나

- 관측은 **스텝 끝**에 한 번 만든다. 다음 스텝의 결정 입력이 된다(`H/env_v2/world.py:1530-1542`).
- 순서는 다음과 같다.
  1. `t ← t + 1`(`:1511`)
  2. 행동 상태 tick(`:1516`)
  3. 새 t의 어둠 갱신(`:1528`)
  4. 기하 `_geometry`(`:1531`)
  5. `rep.perceive`(away·recency, `:1538`)
  6. 경보 E′(19칸 세계만, `:1539-1540`)
  7. `_obs_from`(`:1541`)
  8. 리스폰
  9. 리스폰한 행만 4~7을 다시 한다(`:1544-1547`, `_observe_subset` `:1354-1361`)
- reset 관측도 같은 함수로 만든다. 이때 포식자의 지난 스텝 이동 `pred_vel`은 0이다(`:827,835-841`).
- 모든 칸은 float64로 계산한 뒤 **float32 배열에 넣는다**(`:1335`). 정책 망·마스크·규칙은 이 float32 값을 읽는다.
- **Arbiter는 float32 관측을 읽지 않는다.** 같은 시각의 기하 값(float64)을 읽는다(5-2). C++은 스텝 끝 지각 결과(관측 float + 기하 double)를 함께 들고 있어야 한다.

### 2-2. 칸 표

단위: 파이썬 길이 1단위 = 200 cm, 1스텝 = 8/60 s = 0.1333 s(`H/configs/default.yaml:86-87`, `S/AI/Policy/EcoBehaviorConfig.h:17-20,31`). 아래 '언리얼 꼴'은 cm로 계산할 때의 같은 식이다.

| 칸 | 이름 | 식 (파이썬 단위) | 정규화 · 자르기 | 언리얼 꼴 | 읽는 상태 | 근거 |
|---|---|---|---|---|---|---|
| 0 | `food_density` | 개체 위치 셀의 `food_blur` 값. `food_blur` = 먹이 격자의 정사각 평균, 반경 `max(1, round(see_r / food_cell))` = 10셀(21 × 21). 격자 밖은 잘라 낸 실제 셀 수로 나눈다 | clip[0, 1] | 셀 한 변 400 cm | 먹이 격자(그 스텝 재생 뒤), 위치 | `H/env_v2/world.py:1127-1136,1155-1159,1267-1268,1336` |
| 1 | `pred_count` | 보이는 위협 수 ÷ 8 | clip[0, 1] | 같다 | 위협 위치, 자기 heading, 어둠, 자기 행동 시야 배수, 포식자 잠 | `:1225-1238,1337`, `H/configs/default.yaml:27` |
| 2 | `pred_dist` | 가장 가까운 보이는 위협의 실거리 ÷ `see_r`(20). 안 보이면 inf → 1 | clip[0, 1] | d_cm ÷ 4000 | 같다 | `:1239-1241,1338` |
| 3 | `kin_count` | 보이는 동족 수 ÷ 20. 반경은 `see_r` 20 고정(밤·행동 배수 없음), 시야각 120° | clip[0, 1] | 반경 4000 cm | 동족 위치(이번 스텝 사망 개체 포함, 2-3), heading | `:1206-1213,1339` |
| 4 | `energy` | E ÷ `max_energy`(1) | clip[0, 1] | 비율 | 섭식·대사·번식 리셋 뒤 에너지 | `:1340,1474-1489` |
| 5 | `recent_predation` | min(`pred_ema`, 1). 전역 하나 | 상한 1 | 같다 | 전역 피식 EMA | `:1341,1497-1501` |
| 6 | `cover_dist` | max(e, 0) ÷ `obs_cover_norm`(20). e = 가장 가까운 은신처 원 가장자리까지의 거리(중심 거리 − 반지름) | clip[0, 1]. 은신처가 없으면 1 | e_cm ÷ 4000 | 은신처 원 목록 | `:1163-1167,1252-1264,1342` |
| 7 | `visibility` | (1 − `detect_night`(0.5) · d) · w. w = 지역 날씨 시야 배수(10-18 야생 3단계 `wild_weather` — 날씨 없는 세계·맑음 w = 1, 비 0.9·눈 0.7, 아래 줄) | 날씨 없으면 [0.5, 1], 날씨 있으면 [0.35, 1] | 같다 (`EcoObservationV3::FObservationInput::VisMult` = w) | 새 t의 어둠 d·날씨 | `:1092-1108,1346` |
| 8 | `to_transition` | min(r ÷ `transition_norm`(900), 1). r = 다음 낮밤 전환까지 남은 스텝 ∈ [1, T/2] | 상한 1 | 남은 초 × 7.5 ÷ 900 | 새 t | `:661-676,1103-1104,1347` |
| 9 | `pred_approach` | 가장 가까운 보이는 위협 j에 대해 c = −(v_j · e_j) ÷ \|e_j\| ÷ `herb_speed`(0.6). e_j = 위협 위치 − 내 위치, v_j = 그 위협의 **지난 스텝 실제 변위**(벽 자르기 포함). 관측 = (clip(c, −1, 1) + 1) ÷ 2. 안 보이면 0.5 | [0, 1] | 변위 cm ÷ 120 cm(= 900 cm/s × 0.1333 s) | `pred_vel`, 위치 | `:1291-1294,2113` |
| 10 | `kin_alarm` | 보이는 동족(칸 3과 같은 집합) 중 지금 행동이 FLEE인 비율. 동족이 없으면 0 | [0, 1] | 같다 | 동족의 지금 행동 | `:1311-1312` |
| 11~15 | `beh_graze`, `beh_flee`, `beh_hide`, `beh_freeze`, `beh_sleep` | 지금 행동(이번 스텝에 실행한 행동)의 원핫 | 0 / 1 | 같다 | `behavior` | `H/env_v2/repertoire.py:535` |
| 16 | `beh_steps` | min(steps_in ÷ `steps_norm`(60), 1). tick 뒤 값이라 같은 스텝 훅 `beh_steps`보다 1 크다 | 상한 1 | 같다 | `steps_in` | `H/env_v2/repertoire.py:96-97,536` |
| 17 | `threat_recency` | 이번 관측에서 위협이 보이면 1, 아니면 0.95 × 직전 값 | [0, 1] | 같다 | `recency` | `H/env_v2/repertoire.py:513-522,537` |
| 18 | `alarm_heard` (19칸만) | ttl > 0이면 `gain[hop]` × ttl ÷ `alarm_steps`(15), 아니면 0. 곱한 뒤 나눈다(이 순서) | [0, 1] | 11-3의 표를 쓴다 | 경보 칸(E′ 뒤) | `H/env_v2/repertoire.py:640-645`, `H/env_v2/world.py:1350-1351` |

- 관측 순서: `H/env_v2/world.py:86`(v1 7칸) + `:298-299`(낮밤 2칸) + `H/env_v2/repertoire.py:166-167`(9칸) + `:169`(경보 1칸).
- 칸 7 의 날씨 w (10-18, 명세 `RL_V3_WILD2_SPEC.md` 11절): 계획서 `RL_V2_PLAN.md` 4.2 표 9·#25 가 처음부터 '실효 탐지 반경 ÷ see_r = (1 − 0.5·d)·w' 로 둔 자리를 켠 것이다.
  칸 수·순서·뜻(실효 탐지 반경의 몫)은 그대로다. 파이썬 `wild_weather.obs_visibility`(거울 설정 켬), C++ `FWeatherConfig::bObsVisibility`. 곱 순서는 (1 − 0.5·d) 다음 w (골든
  `WeatherGoldenVectorsV3.h` 낮밤 묶음). R1b 는 [0.5, 1] 에서 배웠으므로 비·눈의 밤(0.45·0.35)은 처음 보는 값이다 — R4 가 배운다.
- 리스폰한 행:
  - behavior = GRAZE, steps_in = 0이라 beh_steps = 0이다.
  - recency는 0에서 시작한다. 그래서 리스폰 자리에서 위협이 보이면 1, 아니면 0이다.
  - 경보 칸은 0이다(`H/env_v2/repertoire.py:331-363`).
  - 에너지는 0.5다(`H/env_v2/world.py:2481`).

### 2-3. 기하 정의 (관측·제어기·Arbiter가 함께 쓴다)

개체 i의 위치 P, heading H(단위벡터). 모두 float64다(`H/env_v2/world.py:1182-1321`).

- **위협이 보인다**: 아래가 모두 참인 위협 m이다.
  - 실거리 pd ≤ `see_r` × (1 − 0.5·d) × `see_mult[i]`
  - (e_m · H) × (1 / max(pd, 1e−9)) ≥ cos 60°
  - m이 자지 않는다(`:1232-1237`, 밤 반경 `:1108`)
  - 파이썬의 cos 60°는 float64로 0.5000000000000001이다(`H/env/config.py:27-32`).
  - `see_mult` = 이번 스텝 제어기가 정한 자기 탐지 배수다. GRAZE 0.6, SLEEP 0.3, 그 밖 1.0(`H/env_v2/repertoire.py:499`, `H/env_v2/world.py:1777`). 리스폰·reset 개체는 0.6이다(`:1066,2505`).
  - 플레이어형 위협도 보통 위협과 같은 규칙으로 보인다.
- **가장 가까운 보이는 위협 j**: 보이는 위협 중 실거리 argmin. 동점이면 낮은 위협 색인이다(`:1239-1241`). 그 위협 쪽 반대 단위벡터가 `away_from_pred`, 안 보이면 0이다(`:1243-1245`).
- **사건 비교 시야(`*_ev`)**: 위 보임 집합에서 pd ≤ `see_r`(1 − 0.5·d) × min(`see_mult` 지금, `see_mult` 직전 관측)인 것만 센다. `pred_count_ev`, `d_pred_min_ev`, `pred_approach_ev`(가장 가까운 사건 시야 위협의 접근 관측)다. 직전 배수는 결정 관측을 만든 배수다(`:1295-1305,1776`). 관측 칸이 아니라 E1·E2만 쓴다(5-3).
- **동족이 보인다**: j ≠ i, 실거리 ≤ 20, 같은 시야각 판정(`:1206-1211`). 같은 좌표(거리 0)인 동족은 내적이 0이라 보이지 않는다.
- **무리 중심 쪽** `to_centroid` = normalize(보이는 동족 위치 평균 − P), 동족이 없으면 0(`:1214-1215`).
- **분리** `separation` = −Σ_j w_ij (pos_j − P) / max(d_ij, 1e−9)를 크기 1로 자른 값이다. w_ij = max(1 − d_ij ÷ `sep_radius`(5), 0), 시야각 없음, 자기 제외(`:1217-1222`, `H/env_v2/steering.py:44-47`).
- **은신처**: 가장자리 거리 e_k의 argmin k(동점 낮은 색인)가 `cover_k`다. `in_cover` = e_k ≤ 0(경계 포함). 은신처가 없으면 `cover_k` = −1, `in_cover` = 거짓이다(`:1252-1264,1313`, `:1169-1173`).
- **먹이 기울기** `food_grad` = normalize(gx, gy). (gy, gx) = `np.gradient`(반경 `food_grad_blur` 2셀 정사각 평균). 안쪽은 중앙 차분, 가장자리는 한쪽 차분, 간격 1이다(`:1160-1161,1269`).
- **셀 색인**: ix = clip(int(x ÷ 2), 0, gw − 1), iy도 같다. 격자 한 변 gw = ceil(size ÷ 2)(`:865,1175-1180`).
- **정규화** `normalize(v)`: |v| > 1e−9면 v/|v|, 아니면 0(`H/env_v2/steering.py:30,38-41`). C++ `GetSafeNormal()`과 같은 뜻이다. 문턱은 1e−9다.
- **사망 개체**: 관측을 만드는 시점(리스폰 전)에 이번 스텝에 죽은 개체가 제자리에 남아 있다. 그래서 다른 개체의 동족 수·중심·분리·`kin_alarm`에 한 스텝 동안 들어간다. v1 C++은 바로 뺀다(`D/RL_Policy/UNREAL_POLICY_INTEGRATION.md:184-185`). 13절 열린 질문 5에 둔다.

---

## 3. 마스크 판 2 / 판 3

m(5칸, bool) = **허용 ∧ 가능 ∧ 결정**(`H/env_v2/rep_policy.py:182-205`). 세계 상태를 바꾸지 않는다. 학습 VecEnv와 판정 롤아웃이 같은 함수를 쓴다(`H/env_v2/vec_env.py:251-255`, `H/env_v2/rollout.py:738-744`).

| 단계 | 판 2 (R1b) | 판 3 (경보 세계) | 근거 |
|---|---|---|---|
| 허용 | 모델의 `rep_allowed` = [T, T, T, T, F] (SLEEP 막음) | 같은 목록 | `H/env_v2/rep_policy.py:131-133`, 모델 policy_kwargs |
| '위협을 안다' K | obs[1] > 0 ∨ obs[17] ≥ 0.2 | K₂ ∨ obs[18] ≥ 0.4 | `:172-174`, 상수 `:67,76` |
| 가능 | GRAZE·SLEEP 늘 참, FLEE = K, FREEZE = K, HIDE = K ∧ obs[6] < 0.75 | 같다 | `:175-178`, 상수 `:64` |
| 결정 | `rep_peek().reads`가 참인 개체만 위 값. 아니면 **지금 행동 한 칸만** 참 | 같다 | `:197-202` |
| 기상 결정 | `wake_decide`면 SLEEP 칸을 끈다 | 같다 | `:198` |
| 빈 행 | 없다(GRAZE는 늘 허용·가능). 생기면 오류 | 같다 | `:203-204` |

- 비교는 **float32 관측 값**과 상수 사이에서 한다(`:171-178`). NumPy 2(설치판 2.1.3)는 파이썬 실수 상수를 float32로 내려 float32끼리 비교한다. C++도 `float` 비교(0.2f, 0.75f, 0.4f)면 같다.
  - obs[17]은 0.95^k이라 0.2와 같아지지 않는다(k = 31에서 0.204, 32에서 0.194).
  - obs[18] ≥ 0.4에는 **정확히 같은 값**이 나온다. 홉 0의 ttl 6, 홉 1의 ttl 10에서 값이 0.4f이고, 마스크가 열린다. 그래서 홉 0은 받은 뒤 10스텝(ttl 15~6), 홉 1은 6스텝(ttl 15~10) 열리고, 홉 2(최대 0.36)는 열지 않는다(`H/tests/test_r2_mechanics.py:927-948`). C++은 11-3의 표를 써서 같은 결정을 낸다.
- 판 번호는 관측 이름으로 정한다. `alarm_heard`가 있으면 3, 없으면 2다(`H/env_v2/rep_policy.py:146-148`). 경보를 끈 세계에서 판 3 코드는 판 2와 같아야 한다(시험 B4, `D/RL_Policy/RL_V3_R2_SPEC.md:639`).
- 규칙 두뇌 FSM_R2는 마스크를 읽지 않는다. 다만 규칙이 내는 요청은 늘 가능 조건 안에 있다(9절 끝).

---

## 4. 망 순전파 (RL 두뇌 R1b)

```
x = obs[0..17] (float32, 정규화 없음)
h1 = tanh(W0 · x + B0)        W0 (64, 18)
h2 = tanh(W1 · h1 + B1)       W1 (64, 64)
z  = W2 · h2 + B2             W2 (5, 64)   ← 로짓. 자르기·시그모이드 없음
zm = m ? z : −1e9
a  = argmax(zm), 동점이면 가장 낮은 번호
```

- **층**:
  - 정책 경로는 `mlp_extractor.policy_net.0`(Linear 18→64), Tanh, `policy_net.2`(Linear 64→64), Tanh, `action_net`(Linear 64→5)다.
  - 가치망(`value_net.*`, `mlp_extractor.value_net.*`)은 버린다.
  - 모델을 읽어 확인했다(구조 출력과 state_dict 모양). 구조 고정은 `H/train.py:34-37`이다.
- **입력 자르기**: 특징 추출기 `RepObsSlice`가 정책 입력 [관측 18 | 마스크 5]의 앞 18칸만 망에 넣는다(`H/env_v2/rep_policy.py:303-311`). 관측 정규화 층은 없다. SB3는 Box 관측을 float로 바꾸기만 한다.
- **가중치 배치**: torch `Linear.weight`는 (out, in)이다. v1과 같이 `W0[j*18 + i]`로 낸다(`H/export_weights.py:58-72` 형식).
- **로짓 편향**:
  - 학습 시작 때 `action_net.bias`를 log(init_probs ÷ Σ) = [−0.9163, −1.8971, −1.8971, −1.8971, −1.8971]로 두었다(`H/env_v2/rep_policy.py:353-357`).
  - `PPO.load`가 그 뒤 state_dict로 덮으므로 **배포 편향 = 학습된 B2**다. 따로 더하지 않는다.
  - s3의 B2는 [−0.91699, −1.81080, −1.76610, −1.98346, −1.89712]다. SLEEP 칸은 늘 막혀 기울기가 없어서 시작값 그대로다.
- **마스크**:
  - 막힌 칸의 로짓은 `MASK_LOGIT` = −1e9다(`H/env_v2/rep_policy.py:78,249`).
  - 배포는 softmax를 하지 않는다. argmax만 한다.
  - `torch.argmax`는 최댓값이 여럿이면 첫 번째 색인을 낸다(`:285-287`).
  - SB3 `predict(deterministic=True)`와 `rep_argmax`가 같은 값이다(`:392-397`). 확인: 무작위 관측·마스크 2000개에서 numpy 순전파 argmax, `rep_argmax`, `predict`가 모두 같았다. 로짓 최대 차는 1.9e−6이다.
- **ε 없음**: 학습 분포의 ε 혼합(`:245-257`)은 배포에 쓰지 않는다(`H/env_v2/rollout.py:755-762`).
- **언제 돌리나**:
  - 요청을 읽는 개체(`reads`)만 돌리면 된다. 읽지 않는 개체의 요청은 Arbiter가 쓰지 않는다(5-2 e).
  - 파이썬은 모든 개체에 돌린다. 결정 아닌 개체의 마스크는 지금 행동 한 칸이라 argmax = 지금 행동이다.
- **C++ 꼴**: 다른 작업이 만드는 `S/AI/Policy/EcoPolicyV3Inference.h`(커밋 전)에 `RunPolicyV3`, `SelectAction`, `ComputeFeasibleMask`, `ComposeActionMask`가 있다. 마스크는 uint8 5칸, 막힌 칸은 `kMaskLogit`, 같은 값이면 낮은 번호다. 이 절의 뜻과 같다. 함수 모양은 그 헤더가 기준이다.

---

## 5. Arbiter (행동 실행기)

`H/env_v2/repertoire.py`는 세계와 무관한 순수 계산이다. 난수를 쓰지 않는다(`:1-6`). C++ `EcoRepertoire.h`가 이 파일의 거울이다.

### 5-1. 개체 상태 (`RepState`, `:297-324`)

| 칸 | 형 | 시작값 | 뜻 |
|---|---|---|---|
| `behavior` | int8 | GRAZE | 지금 행동 |
| `phase` | int8 | 0 | 5-4 |
| `steps_in` | int | 0 | 행동 경과(진입 스텝 0) |
| `seq` | int, mod 256 | 0 | 행동이 바뀔 때마다 +1 |
| `lock_left` | int(음수 가능) | `lock_graze` 12 | ≤ 0이면 결정 시점 |
| `startle_left` | int ≥ 0 | 0 | 놀람 정지 남은 스텝 |
| `waking`, `wake_left`, `wake_target`, `wake_ev` | | 거짓, 0, GRAZE, 거짓 | SLEEP 기상(두 두뇌에서 쓰이지 않는다) |
| `ev_wait` | int | −1 | 대기 중인 사건 결정까지 남은 스텝, −1 = 없음 |
| `hide_target` | int | −1 | HIDE가 고른 은신처 색인 |
| `arrived` | bool | 거짓 | HIDE 도착(웅크림) |
| `prev_pc` | int | 0 | 직전 결정 관측의 보이는 위협 수(실제 시야) |
| `prev_near`, `prev_fast` | bool | 거짓 | 직전 근접·빠름(실제 시야) |
| `prev_low` | bool | E < 0.25 | 직전 저에너지 |
| `prev_dark` | bool | d ≥ 0.5 | 직전 어둠 쪽 |
| `away` | 2D | 0 | 마지막 위협 반대 방향(단위) 또는 경보 방향 |
| `recency` | float | 0 | threat_recency |
| `jitter` | int ∈ [0, 3] | 해시 | 사건 결정 지연(5-5) |
| 경보 칸 (판 3 세계만) | | | 8절 |

### 5-2. 한 스텝 `Arbitrate(State, Request, DecisionObs)` (`:399-455`)

결정 관측 `DecisionObs`는 **직전 스텝 끝 기하**다(리스폰 행 포함). 그리고 지금 에너지와 지금 어둠이다(`H/env_v2/world.py:1709-1721`):
- `pred_count`(int), `d_pred_min`(float64 실거리, 없으면 inf), `pred_approach`(float64)
- `pred_count_ev`, `d_pred_min_ev`, `pred_approach_ev`
- `energy` = clip(E ÷ 1, 0, 1)(float64), `dark` = d(t)
- `in_cover`, `cover_k`
- (판 3 세계만) `alarm_new`

차례(순서가 계약이다):

- **a. HIDE 도착**
  - arrive = (behavior == HIDE) ∧ ¬arrived ∧ in_cover
  - arrive면 arrived ← 참, lock_left ← `lock_hide` 12
  - E6 = arrive ∧ steps_in > 0(`:409-413`)
- **b. 사건** (5-3).
  - 그다음 기준값을 **실제 시야 값**으로 바꾼다: prev_pc ← pred_count, prev_near ← near, prev_fast ← fast, prev_low ← low, prev_dark ← dark(`:431-432`).
  - 결정 여부와 상관없이 스텝마다 바꾼다.
- **c. 지연**
  - event ∧ ev_wait < 0면 ev_wait ← jitter.
  - fire = (ev_wait == 0).
  - 그다음 ev_wait > 0이면 1 줄인다(`:434-436`).
  - 그래서 사건 t의 결정은 t + jitter 스텝에 온다.
- **d. 기상 끝** (`:438-441`, SLEEP 전용)
  - wake_ev ← wake_ev ∨ (event ∧ waking). woke = waking ∧ wake_left ≤ 0. wake_dec = woke ∧ wake_ev.
  - woke 개체는 진입한다. 대상은 (wake_dec ∧ Request ≠ SLEEP) ? Request : wake_target이다.
- **e. 결정** (`:443-452`)
  - decide = (lock_left ≤ 0 ∨ fire) ∧ ¬waking ∧ ¬woke.
  - fire ∨ decide ∨ woke면 ev_wait ← −1.
  - change = decide ∧ Request ≠ behavior.
  - change ∧ behavior == SLEEP이면 기상 시작이다(waking, wake_left ← 3, wake_target ← Request).
  - 나머지 change는 곧바로 `Enter(Request)`.
  - **Request == behavior면 아무것도 하지 않는다.** 잠금을 새로 걸지 않는다. 그래서 잠금이 끝난 뒤에는 스텝마다 결정 시점이다.
- **f. Enter(new)** (`:377-396`)
  - behavior ← new, seq ← (seq + 1) mod 256, steps_in ← 0, lock_left ← locks[new]
  - startle_left ← (new == FLEE ∧ 이전 == GRAZE) ? 3 : 0
  - waking·wake_ev 끔, wake_left ← 0
  - hide_target ← (new == HIDE) ? cover_k : −1
  - arrived ← (new == HIDE) ∧ in_cover. 이미 은신처 안이면 lock_left ← 12이고 E6은 없다.
- **g. 위상** ← `phase_of`(5-4).
- 반환:
  - `decide` = decide ∨ wake_dec. 이것이 '요청을 읽었다'다.
  - `switch` = (change ∧ ¬기상 시작) ∨ woke
  - `event`, `fire`, `e7`

스텝 끝 **Tick**(`:505-510`, 세계 스텝의 `H/env_v2/world.py:1516`)은 다음과 같다. phase는 tick에서 바꾸지 않는다.
- steps_in += 1, lock_left −= 1
- startle_left = max(startle_left − 1, 0), wake_left = max(wake_left − 1, 0)

### 5-3. 사건 E1~E7 (`H/env_v2/repertoire.py:414-430`)

준비: seen = pc > 0, near = seen ∧ d_pred_min < 8, fast = seen ∧ pred_approach ≥ 0.9. `_e` 붙은 값은 사건 비교 시야로 같은 식을 쓴다.

| 사건 | 조건 | 비고 |
|---|---|---|
| E1 | pred_count_ev > prev_pc | 수가 늘었을 때만. 같은 스텝에 하나 나가고 하나 들어오면 사건이 아니다 |
| E2 | (near_e ∧ ¬prev_near) ∨ (fast_e ∧ ¬prev_fast) | 8단위(16 m) 안으로 들어옴, 또는 접근 0.9 이상이 됨. 밖 → 안 경계 넘기 |
| E3 | behavior == SLEEP ∧ seen | 쓰이지 않음(1-3) |
| E4 | low ∧ ¬prev_low, low = energy < 0.25 | 내려갈 때만 |
| E5 | prev_dark ≠ (dark ≥ 0.5) | 양방향. 모든 개체가 같은 스텝에 받는다 |
| E6 | a의 도착 ∧ steps_in > 0 | |
| E7 (판 3 세계만) | alarm_new ∧ behavior ∈ {GRAZE, SLEEP} | behavior는 이 스텝 전환 전 값이다. FLEE·FREEZE·HIDE의 잠금은 열지 않는다(8-5) |

- event = 위 OR. 사건은 **결정 시점만** 만든다. 행동을 강제하지 않는다.
- 사건 비교 시야를 쓰는 이유: 자기 행동이 바뀌어 시야가 넓어진 것만으로 생긴 위협은 사건이 아니다. 예를 들어 GRAZE 0.6에서 FREEZE 1.0으로 바뀐 경우다(`:33-36`).
- E5 문턱: d = 0.5는 전환 스텝에 **정확히** 나온다(7-6). 낮 첫 스텝(s = 0)은 d = 0.5라 '어둠 쪽'이다. 그래서 E5는 낮 둘째 스텝(s = 1)과 밤 첫 스텝(s = T/2)에 생긴다.

### 5-4. 잠금·위상 표

| 행동 | 진입 잠금 `locks[b]` | 그 뒤 | 위상 0 | 위상 1 | 근거 |
|---|---|---|---|---|---|
| GRAZE | 12 (1.6 s) | 스텝마다 결정 | 진입 스텝 | 그 뒤 | `H/env_v2/repertoire.py:283-284,458-466` |
| FLEE | 8 (1.07 s) | 스텝마다 결정 | 진입 스텝, 또는 startle_left > 0인 동안 | 그 뒤 | 같다 |
| HIDE | 40 (5.33 s, `hide_travel_max`). 도착하면 12 | 40을 넘겨도 못 닿으면 스텝마다 결정(같은 요청이면 계속 간다) | 도착 전 | 도착(웅크림) | 같다, `:410-413` |
| FREEZE | 12 | 스텝마다 결정 | 진입 스텝 | 그 뒤 | 같다 |
| SLEEP | 3 + 60 | (쓰이지 않음) | steps_in < 3 | 수면 | 기상 중이면 위상 2 |

- 시간 읽는 법: 스텝 t에 진입해 잠금 L이면 결정 시점은 t + L이다(사건이 없을 때).
  - 확인: GRAZE → FLEE를 t = 5에 진입하면 위상 0이 t = 5~7(놀람 3스텝), 다음 결정이 t = 13이다.
- **놀람(M2)**: GRAZE → FLEE만 3스텝(0.4 s) 정지한다. FREEZE·HIDE → FLEE는 0이다. 놀람은 FLEE 잠금 8 안에 든다(뛰기 5스텝).
- 시작·리스폰 개체: GRAZE, 잠금 12, 위상 0이다. 사건이 없으면 첫 결정은 스텝 12다.

### 5-5. 결정 지연 해시와 개체 키

- `jitter = H(505, Seed, AgentKey) mod (J + 1)`, J = `decision_jitter` 3이다(`H/env_v2/repertoire.py:164,212-220`).
- `H(x1..xn)`: h = 0, 그리고 x마다 h = Mix64((h XOR x) + 0x9E3779B97F4A7C15)다. 모두 uint64이고 넘침을 허용한다(`:197-203`).
- Mix64는 SplitMix64 마무리 함수다(`:188-194`):
  - z ^= z >> 30
  - z *= 0xBF58476D1CE4E5B9
  - z ^= z >> 27
  - z *= 0x94D049BB133111EB
  - z ^= z >> 31
- 같은 함수가 `H/env_v2/rollout.py:438-495`에도 있다.
- `AgentKey = (slot << 32) + generation`(uint64)이다(`H/env_v2/repertoire.py:206-209`). generation은 그 슬롯의 리스폰 횟수(0부터)이고, 리스폰마다 +1이다(`H/env_v2/world.py:2502-2504`). `Seed`는 세계 시드(int64 → uint64)다.
- 지연은 개체가 날 때 한 번 정한다(reset `H/env_v2/repertoire.py:322`, 리스폰 `:355`).
- 확인한 값 (seed 10200):

  | (slot, gen) | (0,0) | (1,0) | (2,0) | (3,0) | (4,0) | (5,0) | (6,0) | (7,0) | (5,3) | (127,1) |
  |---|---|---|---|---|---|---|---|---|---|---|
  | jitter | 1 | 1 | 0 | 1 | 0 | 0 | 2 | 1 | 0 | 1 |

  - H(505, 10200, key)는 slot 0 = 1110555831934012869, slot 1 = 1460025693453276225, slot 2 = 18022844948526388744다(gen 0). 순수 정수 구현으로 다시 계산해 같았다.
- 언리얼 대응은 12-3을 본다.

### 5-6. 요청을 읽는지 미리 보기 (`rep_peek`)와 C++ 꼴

- 파이썬은 매 스텝 `rep_peek()`이 RepState 사본에 같은 결정 관측으로 `arbitrate`를 돌려 `reads`(= decide ∨ wake_dec)와 `wake_decide`를 얻는다. 요청 값은 결과에 영향이 없어서 지금 행동을 넣는다(`H/env_v2/world.py:1723-1743`). 세계와 난수를 건드리지 않는다. 부르든 부르지 않든 궤적이 같다(시험 B6).
- C++은 사본을 만들 필요가 없다. Arbiter를 둘로 나눈다. 결과는 같다.
  - `Prepare`: a~d와 e의 decide까지 계산한다. 아직 Enter하지 않는다.
  - `reads`면 그때 마스크와 망(또는 규칙)으로 Request를 만든다.
  - `Commit`: e의 change·Enter, f, g를 한다.
- 이렇게 하려면 a~d가 Request를 읽지 않아야 한다. 실제로 읽지 않는다.
  - 기상 끝(d)은 Request를 읽지만 그 개체는 `wake_dec`라 reads에 들어 있다.
  - 마스크의 '지금 행동 한 칸'은 Prepare 전의 behavior다(`H/env_v2/world.py:1743`).

### 5-7. 리스폰 (`H/env_v2/repertoire.py:331-363`, `H/env_v2/world.py:2475-2522`)

- 리스폰은 새 개체다. behavior GRAZE, phase 0, steps_in 0, **seq + 1**, lock 12, startle·wake 0, ev_wait −1, hide_target −1, arrived 거짓, prev_pc 0, prev_near·prev_fast 거짓, prev_low = E < 0.25, prev_dark = d ≥ 0.5다.
- away 0, recency 0이다. generation + 1로 jitter를 다시 정한다. 경보 칸은 모두 0이다(ttl 0, hop 없음, pt 0, t0 0, alarm_new 거짓, alarm_seq 0, entry_cause 0).
- 시야 배수(지금·직전) = 0.6이다.
- 위치·heading은 v1 난수로 맵 전체 균등이다(`H/env_v2/world.py:2477-2480`). 언리얼은 다르게 둔다(12-4).
- 스텝 뒤 훅(`behavior`, `beh_phase`, `beh_steps`, `beh_seq`)은 tick 전 값이고, 리스폰이 바꾸지 않는다(`H/env_v2/world.py:1076-1083`).

---

## 6. 제어기 (`Control`, `H/env_v2/repertoire.py:469-502`, 세계 쪽 `H/env_v2/world.py:1745-1783`)

### 6-1. 입력

모두 결정 관측(직전 스텝 끝 기하)과 결정 때 상태다.
- G = `food_grad`, C = `to_centroid`, Sep = `separation`
- A = seen ? `away_from_pred` : State.away
- T = normalize(cov_c[hide_target] − P). 고른 은신처의 **중심** 쪽이다. P는 결정 때 위치다(`H/env_v2/world.py:1766-1769`).
- food_ok = 결정 때 위치 셀의 먹이(섭식 전) ≥ `graze_eat_min` 0.06(`:1765,1772`)
- in_cover, d(t)

### 6-2. 행동별 규칙

| 행동 | 방향 raw | 보행 | 섭식 배수 eat | 자기 탐지 배수 see | still | crouch | heading |
|---|---|---|---|---|---|---|---|
| GRAZE | 0.83·G + 0.71·C + 1.35·Sep | food_ok ? 정지 : 걷기 | gait_eat[보행] (정지 1.0, 걷기 0.5) | 0.6 (M5) | 거짓 | 거짓 | 움직이면 속도 방향 |
| FLEE | 3.0·A + 0.71·C + 1.35·Sep | startle_left > 0 ? 정지 : 뛰기 | 0 | 1.0 | 거짓 | 거짓 | 움직이면 속도 방향 |
| HIDE 도착 전 | hide_target ≥ 0 ? T + 1.35·Sep : 0 | seen ? 뛰기 : 걷기 | 0 | 1.0 | 거짓 | 거짓 | 움직이면 속도 방향 |
| HIDE 도착 | 0 | 정지 | 0 | 1.0 | 참 | 참 | 그대로 |
| FREEZE | 0 | 정지 | 0 | 1.0 | 참 | 거짓 | A ≠ 0이면 **−A**(위협 쪽), 아니면 그대로 |
| SLEEP | 0 | 정지 | 0 | 0.3 | 참 | 거짓 | 그대로 |

- 계수: `graze_forage` 0.83, `graze_cohesion` 0.71(`H/configs/v3_r1_on.yaml:126-127`), `sep_weight` 1.35, `flee_weight` 3.0(`H/configs/default.yaml:21-23`). FLEE에도 cohesion 0.71이 붙는다(`H/env_v2/repertoire.py:479-482`).
- **방향이 없으면 정지**: |raw|² ≤ (1e−9)²이면 보행 = 정지다(`:488,493`). GRAZE가 걷기여야 하는데 방향이 없으면 정지가 되고, 섭식 배수도 정지 값 1.0이 된다.
- **속도** = normalize(raw) × `herb_speed` 0.6 × gait_speed[보행]. gait_speed = [0, 0.4, 1.0](`:494-495`, `H/configs/v3_r1_on.yaml:34`).

  | 보행 | 파이썬 | 언리얼 |
  |---|---|---|
  | 정지 | 0 | 0 |
  | 걷기 | 0.24단위/스텝 | 360 cm/s |
  | 뛰기 | 0.6단위/스텝 | 900 cm/s |

- **대사 배수** drain = drain_mult[보행] × (SLEEP ∧ in_cover ? 1 − 0.6·d : 1)(`H/env_v2/repertoire.py:497-498`).
  - drain_mult = c_rest + c_move · s² = [0.7142857, 1.0, 2.5](`H/env_v2/world.py:419-421`, `H/configs/v3_r1_on.yaml:48-49`).
  - FLEE의 놀람 정지 중에는 정지 대사다(`H/env_v2/repertoire.py:101`).
- **은신 배수** cover_mult = crouch ? 4.0 : GRAZE ? 1.5 : SLEEP ? 2.5 : 1.0(`:288-294`, `H/configs/v3_r1_on.yaml:114-117`). 은신처 **안**일 때만 쓴다(7-2).

### 6-3. 이동과 에너지 (세계, `H/env_v2/world.py:1450-1489`)

- 위치 ← clip(P + v, 0, size). 정사각 맵 벽에서 멈춘다.
- |v| > 1e−9면 heading ← normalize(v). 그 뒤 FREEZE는 heading ← −A로 덮는다(`:1450-1455`). heading은 벽 자르기 전 v로 정한다.
- 섭식·대사 (`:1564-1569,1471-1474`, `_eat` `:2396-2421`). 섭식 셀은 **이동 뒤 위치**의 셀이다. food_ok는 이동 전 셀이다.
  1. drain = 0.002 × drain 배수
  2. E′ = E − drain
  3. want = clip((1 − E′) ÷ 0.5, 0, 0.06) × eat × (1 − 0.9·d)
  4. 셀마다 수요 합을 낸다. 먹은 양은 min(수요, 셀 먹이)이고, 개체마다 수요 비율로 나눈다.
  5. E_new = min(E′ + 먹은 양 × 0.5, 1)
- 번식 (`:1484-1489`): repro_cd ← max(repro_cd − 1, 0). 그다음 E > 0.9 ∧ repro_cd == 0이면 E ← 0.5, repro_cd ← 200. 관측 energy가 바뀌므로 계약이다.
- 아사: E ≤ 0이면 사망이다(`:1492`).
- 먹이 재생 (`:1505-1507`): food ← clip(food + regen·(cap − food), 0, cap). regen = 0.026 × U[0.5, 2](세계마다) × (은신처 셀이면 0.3)(`:891-893`). v3 판정 설정에는 food_v가 없다.

---

## 7. 위협 모델 (학습 세계, `H/env_v2/world.py:1987-2145`)

### 7-1. 공통 스텝 (한 스텝, 위협 m마다. 순서가 계약이다)

1. 초식 위치는 **이동 뒤**, 위협 위치는 이동 전이다. 실거리 dist(m, i), inv = 1 ÷ max(dist, 1e−9)(`:2021-2025`).
2. 체감 거리(7-2): perceived = dist × det, catch_d = dist × cov(`:2026-2033`).
3. 쿨다운: cd ← max(cd − 1, 0). hunting = (cd == 0) ∧ ¬asleep(`:2034-2037`).
4. 자는 잠행형은 ROAM·남은 0으로 돌린다(`:2041-2044`). exh0 = 잠행형 ∧ EXHAUST, rest0 = 플레이어 ∧ REST. hunting ∧= ¬exh0 ∧ ¬rest0(`:2048-2054`).
5. 시야 vis = perceived ≤ `pred_view_r` 14 ∧ (dir(m → i) · head_m) ≥ cos 75°(0.258819). 플레이어 행은 모두 참이다. 그다음 vis ∧= hunting(`:2055-2059`).
6. 표적 j = vis 위 perceived argmin(동점 낮은 초식 색인), d_t = 그 체감 거리, has_target(`:2060-2063`).
7. 배회 선회: turn ~ U[−0.15, 0.15] rad. 보통 위협은 v1 스트림, 플레이어는 threats 스트림 3이다. wander = head를 turn만큼 돌린 것(`:2066-2072`).
8. 기본 이동 move = has_target ? unit(초식 − 위협) : wander, speed = 기본 속력(`:2073-2075`).
9. 유형별 상태 기계(7-4, 7-5)가 move·speed를 덮는다(`:2076-2077`).
10. 밤잠·박명(7-6): 자면 move = head, speed × 0. 깨어 있는 주행성은 speed × (1 − d)(`:2078-2080`).
11. pos += move × speed. 벽 밖으로 나간 축은 move 그 성분의 부호를 뒤집고(반사), pos를 [0, size]로 자른다. head ← normalize(move), `pred_vel` ← pos − 이동 전 pos(`:2083-2113`).
12. 포획: hit = catch_d ≤ catch_r ∧ hunting. 원거리형은 그 위에 난수 < 0.02여야 한다(v1 스트림 (M_base, N)개). **위협마다 한 스텝에 많아야 한 마리**, hit 중 catch_d argmin(동점 낮은 초식 색인)이다(`:2115-2125`). 거리는 1의 값(위협 이동 전)이다.
13. 같은 초식을 여러 위협이 잡으면 사망은 1건이다. 비명 점의 주인은 가장 낮은 위협 색인이다(`:2129-2132`).
14. 잡은 위협의 cd ← (플레이어 ? 30 : 5)(`:2138-2141`), 그리고 상태 갱신(`_threat_after`, `:2350-2394`).

- **쿨다운의 뜻**: 스텝 t에 잡으면 cd = 5다. 스텝 t+1~t+4는 사냥하지 않고 배회하며 기본 속력으로 움직인다. 스텝 t+5에 다시 사냥한다. 언리얼 초 단위로는 '스텝 시작에 0.1333 s를 빼고, 0이면 사냥'이다. 그러면 0.667 s 뒤 다시 잡을 수 있다(`S/AI/Policy/EcoBehaviorConfig.h:35`).
- 위협 배열 순서: 보통 위협 0..M_base−1, 그 뒤 플레이어 하나(있으면)(`:984,999-1011`). 동점은 이 색인으로 깬다.

### 7-2. 체감 거리 (M1·M6)

| 초식 상태 (이번 스텝 행동) | 은신처 안 cov | 밖 cov | det = max(cov, still ? 1.8 : 1) | 표적 체감 | 포획 체감 |
|---|---|---|---|---|---|
| GRAZE | 1.5 | 1 | 1.5 / 1 | ×1.5 / ×1 | ×1.5 / ×1 |
| FLEE, HIDE 가는 중 | 1.0 | 1 | 1 | ×1 | ×1 |
| FREEZE | 1.0 | 1 | 1.8 | ×1.8 | ×1 |
| HIDE 도착(웅크림) | 4.0 | (밖이면 1) | 4.0 (밖이면 1.8) | ×4.0 / ×1.8 | ×4.0 / ×1 |
| SLEEP (쓰이지 않음) | 2.5 | 1 | 2.5 / 1.8 | | |

- 근거: `H/env_v2/world.py:2027-2033`, `H/env_v2/repertoire.py:130-131,288-294,500`.
- '은신처 안'은 **이동 뒤** 위치로 다시 판정한다(`H/env_v2/world.py:2026`). still·crouch·cov는 이번 스텝 제어기 값이다(`:1777-1780`).
- 표적 고르기·시야 반경·돌진 거리는 perceived를 쓴다. 포획은 catch_d를 쓴다.
  - 그래서 FREEZE는 포획 거리를 늘리지 않는다.
  - 웅크림은 실거리 0.25단위(50 cm) 안에서만 잡힌다.

### 7-3. 추격형·원거리형 (`H/env_v2/world.py:907-912,991-994`)

- 세계마다 `pred_speed_mult` ~ U[0.6, 0.95]다. 모든 근접형이 같은 배수다.
- 근접 추격형: 속력 0.6 × mult = 0.36~0.57단위/스텝(540~855 cm/s), 포획 1.0(200 cm).
- 원거리형(추격형 중 비율 U[0, 0.5]): 속력 × 0.6(324~513 cm/s), 포획 3.0(600 cm), 스텝 확률 0.02.
- 상태 기계 없음. 7-1 그대로 사냥(시야 표적 쪽)하거나 배회(선회)한다. 같은 속력이다.

### 7-4. 잠행-돌진형 (threats, `H/env_v2/world.py:2291-2313,2350-2368`)

- 세계마다 p_stalk ~ U[0.3, 0.7]이다. 보통 위협마다 확률 p_stalk로 잠행형이 되고, 잠행형은 근접형이다(`:976-994`). 상태는 ROAM 0, POUNCE 1, EXHAUST 2다(`:199`).

| 상태 | 조건 | 속력 (× 0.6단위/스텝) | 방향 | 사냥 |
|---|---|---|---|---|
| ROAM, 표적 없음(또는 cd > 0) | | **기본 속력**(추격형과 같은 mult) | 배회 | cd에 따름 |
| ROAM, 표적 있음, d_t > 6 (잠행) | | 0.3 (0.18단위, 270 cm/s) | 표적 쪽 | 예 |
| ROAM → POUNCE 시작 | 표적 있음 ∧ d_t ≤ `stalk_dist` 6 (체감 거리) | 그 스텝부터 돌진 | | |
| POUNCE, 남은 > 0 (돌진) | | 1.5 (0.9단위, 1350 cm/s) | 표적 있으면 표적 쪽, 없으면 head 그대로 | 예 |
| POUNCE, 남은 ≤ 0 (마지막 판정) | | 0.2 (0.12단위, 180 cm/s) | head 그대로 | 예 |
| EXHAUST | 30스텝 | 0.2 | 배회 | 아니오 |

- 전이(`_threat_after`, 포획 판정 뒤):
  - 돌진 중 잡으면 ROAM, 남은 0이다.
  - 마지막 판정에서 놓치면 EXHAUST, 남은 30이다.
  - 놓친 돌진은 남은 − 1이다.
  - EXHAUST는 남은 − 1이고, 0 이하면 ROAM이다.
- 시작하면 남은 = `pounce_steps` 12다. 그래서 **돌진 이동 12번 + 마지막 판정 1스텝(13스텝 POUNCE)**, 놓치면 탈진 30스텝이다.
- 돌진 시작 거리는 **체감** 6이다. 실거리로는 먹는 개체 6, 은신처 안 먹기 4, 얼기 3.33, 웅크림(은신처 안) 1.5다.
- 밤잠·박명 감속은 잠행형에도 같다. 자면 상태가 ROAM으로 돌아간다(`:2041-2044`).

### 7-5. 플레이어형 대역 (threats, `H/env_v2/world.py:995-1027,2314-2336,2379-2394`)

- 세계의 절반(`player_frac` 0.5)에 하나 있다. 밤에 자지 않고(야행성으로 넣음), 박명 감속도 없다.
- **맵 전체를 본다**. 시야 반경·각이 없고 체감 거리는 같다(`:2057-2058`).
- 포획 1.0, 쿨다운 30스텝(4 s).
- 모드:

  | 모드 | 속력 (× 0.6) | 방향 | 사냥 | 끝 |
  |---|---|---|---|---|
  | WANDER | 0.4 (360 cm/s) | 배회(threats 스트림 3) | 예(가까우면 잡는다) | 남은 길이 0 → 새 모드 |
  | STALK | 0.3 (270 cm/s) | 가장 가까운 체감 거리 개체 쪽 | 예 | 남은 길이 0 → 새 모드. d_t ≤ 6이면 CHARGE |
  | CHARGE, 남은 > 0 | 1.3 (1170 cm/s) | 표적 쪽 | 예 | 20번 이동 |
  | CHARGE, 남은 ≤ 0 | 0 | head | 예 | 판정 뒤 REST |
  | REST | 0 | head | 아니오 | 30스텝 → 새 모드 |

- 새 모드는 확률 0.5로 STALK, 아니면 WANDER다. 길이는 200 + ⌊u·201⌋(200~400)스텝이다(`:1020-1027`).
- CHARGE 중 잡거나 남은 ≤ 0이면 REST다. REST는 30스텝 뒤 새 모드다(`player_rest_steps`가 0인 설정이면 곧바로 새 모드, `:2382-2388`).

### 7-6. 낮밤, 밤잠, 박명 감속

- **어둠 d** (`H/env_v2/world.py:661-676`):
  - h = T/2, s = (t + o) mod T, e = s mod h, r = h − e, k = min(e, r), τ = 0.05·T(정수 스텝)
  - 낮(s < h): d = max(0.5 − k/(2τ), 0)
  - 밤: d = min(0.5 + k/(2τ), 1)
  - C++ 꼴: e = Now − PhaseStart, r = PhaseEnd − Now(스텝), bNight = 위상이 밤.
  - 학습 T ∈ {600, 900, 1800}(80/120/240 s), τ = {30, 45, 90}(`H/configs/v3_r1_on.yaml:57-59`, `H/env_v2/world.py:480-485`).
  - 확인값 (T 900, o 0):

    | t | 0 | 1 | 45 | 449 | 450 | 451 | 495 | 899 |
    |---|---|---|---|---|---|---|---|---|
    | d | 0.5 | 0.48889 | 0 | 0.48889 | 0.5 | 0.51111 | 1.0 | 0.51111 |
    | r | 450 | 449 | 405 | 1 | 450 | 449 | 405 | 1 |

- 갱신 시점: 스텝 끝 t + 1 뒤(`H/env_v2/world.py:1524-1528`). 다음 스텝의 섭식·대사·Arbiter(E5)·포식자 이동과, 그 스텝 끝 관측이 같은 d를 쓴다.
- **밤잠**: 주행성 위협은 d ≥ 0.5면 잔다(`:1109-1114`).
  - 자는 위협은 움직이지 않고 사냥하지 않고, 초식 시야에서 빠진다.
  - d = 0.5인 낮 첫 스텝에도 잔다.
  - 야행성 비율 q ~ U[0, 0.25], 위협마다 확률 q다(`:963-974`). 플레이어는 늘 깨어 있다.
- **박명 감속**: 깨어 있는 주행성 위협의 속력은 × (1 − d)다. 야행성은 × 1이다(`:1113-1114`).

### 7-7. 언리얼 = 학습 세계의 부분집합

원칙: 학습에 있던 조건의 **일부만** 쓰는 것은 된다. 학습에 **없던** 조건은 쓰지 않는다(`D/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md:47-51`).

| 요소 | 학습 세계 | 언리얼 요구 |
|---|---|---|
| 위협 시야 14단위(28 m)·150°, 체감 거리 표적, 선회 ±0.15 rad/스텝, 벽 반사 | 늘 | **필수** (같은 식) |
| 포획 판정: 스텝마다, 이동 뒤 초식 대 이동 전 위협, 위협당 1마리, 쿨다운 5 / 플레이어 30 | 늘 | **필수** |
| 행동별 은신 배수와 c_still (7-2) | 늘 | **필수** |
| 근접 추격형 속력 | 세계마다 0.6~0.95배 하나 | **범위 안 한 값** (예: 0.8배 = 720 cm/s). 1.0배는 학습 밖이다 |
| 원거리형 | 추격형의 0~50% | 선택 (빼도 된다) |
| 잠행-돌진형 상태 기계 (7-4) | 세계마다 30~70% | 쓰면 **식 그대로**. 비율은 범위 안. 0%는 학습 밖이다(최소 30%) |
| 주행성 밤잠·박명 감속 | 늘 켬, 야행성 0~25% | **필수**. 야행성은 0~25% 안 |
| 플레이어형 대역 (7-5) | 세계 절반 | 선택. 사람 플레이어는 모드 기계가 아니다. 서버 대리로 위협 목록에 넣을 때 속력은 0~1170 cm/s 안으로 묶는다(13절 열린 질문 8) |
| 위협 수·맵 크기 | 2~12마리, 한 변 60~110단위(120~220 m), 초식 128 | 범위 안이 바람직하다. 레벨 밀도 차이는 `D/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md` 3-1에 기록돼 있다 |
| 은신처 | 반경 4~9단위(8~18 m) 원, 넓이 5~30% | 범위 안 (레벨 몫) |
| 낮밤 주기 | 600/900/1800스텝, 박명 0.05·T | 900스텝(60 + 60 s)은 범위 안이다. 박명 τ = 45스텝 |
| 위협 감각(시선 가림·발소리·기억), '직접 봐야 잡힘' | 없음 | **쓰지 않는다** (학습 밖) |
| 난수 스트림 | numpy | 맞추지 않는다. 골든은 난수를 입력으로 넣는다(11절) |

---

## 8. M8 동족 경보 (FSM_R2 세계만, `H/env_v2/repertoire.py:541-645`, `H/env_v2/world.py:1785-1846`)

계수 (`H/configs/v3_r2_on.yaml:174-189`, 검사 `H/env_v2/world.py:624-658`):

| 키 | 값 | 단위 |
|---|---|---|
| `alarm_r` | 8 | 1600 cm |
| `alarm_steps` | 15 | 2 s |
| `max_hop` | 2 | |
| `hop_gain` | 0.6 | gain = [1.0, 0.6, 0.36]. 곱을 차례로 쌓는다 |
| `relay_window` | 30 | 4 s |
| `event_alarm` | 0.4 | |
| `on_catch` | 참 | |
| `OWN_RECENCY` | 0.2 | 계약 상수 |

- gain 근거: `H/env_v2/repertoire.py:546-553`. `OWN_RECENCY` 근거: `:173`.
- `active` = alarm_r > 0 ∨ on_catch다. 거짓이면 블록 전체를 건너뛴다(`H/env_v2/world.py:657,1437,1539`). 비교가 아니라 건너뛰기다.

### 8-1. 경보 칸 (`H/env_v2/repertoire.py:366-374`)

| 칸 | 형 | 뜻 |
|---|---|---|
| `al_ttl` | int | 남은 스텝 |
| `al_hop` | uint8 | 쥔 홉. 255 = 없음. ttl이 0이 돼도 지우지 않는다. ttl > 0일 때만 읽는다 |
| `al_pt` | 2D | 경보 점 |
| `al_t0` | int | 원점(홉 0) 스텝 |
| `alarm_new` | bool | E7용 |
| `alarm_seq` | int, mod 256 | 낸 횟수 |
| `entry_cause` | bit0 봄, bit1 들음, bit2 그 밖 | 애니메이션 전용, 동역학과 무관하다 |

### 8-2. 내기 A′ (Arbiter·제어기 뒤, 이동 전, `H/env_v2/repertoire.py:556-579`, `H/env_v2/world.py:1436-1438`)

- 대상: 이번 스텝 `switch`(기상 포함) ∧ 새 행동 ∈ {FLEE, FREEZE, HIDE}인 개체(`into`)다.
- **홉 0**: into ∧ 결정 관측 pred_count > 0.
  - pt = 결정 때 위치 − away_from_pred × d_pred_min이다. 곧 가장 가까운 보이는 위협의 위치다.
  - t0 = t(이번 스텝 번호, 증가 전).
- **중계**: into ∧ 안 보임 ∧ al_ttl > 0 ∧ al_hop < 2 ∧ t − al_t0 ≤ 30.
  - hop = al_hop + 1, pt·t0는 쥔 값이다.
  - 여기의 al_ttl은 지난 E′ 뒤 값이다.
- 그 밖(기억 threat_recency만 있는 전환 등)은 내지 않는다.
- entry_cause: switch 개체는 into ? ((seen ? 1 : 0) | (ttl > 0 ? 2 : 0) | (둘 다 아니면 4)) : 0이다.
- 마지막에 **모든 개체의 alarm_new ← 거짓**이다.

### 8-3. 비명 (포획 뒤, `H/env_v2/world.py:1824-1837`)

- 이번 스텝에 잡힌 개체는 홉 0으로 낸다.
  - pt = 잡은 위협의 **이동 뒤** 위치다. 여러 위협이 잡았으면 가장 낮은 위협 색인이다(7-1 13).
  - t0 = t다.
- 같은 개체의 전환 방출을 **덮는다**(`EmitOrReplace`). 방출 버퍼는 개체 키 하나에 항목 하나다.
- alarm_seq는 E′에서 한 번만 +1이다.

### 8-4. 듣기 E′ (perceive 뒤, 관측 전, 리스폰 전, `H/env_v2/repertoire.py:582-637`)

개체 i마다, 아래 위치는 모두 스텝 끝(이동 뒤, 리스폰 전)이다. 이번 스텝에 죽은 개체도 내고 듣는다.

1. ttl0 = max(al_ttl − 1, 0). hop_prev = al_hop(지금 값).
2. 스스로 냈으면(emitted): 자기 방출 값으로 쓴다. ttl = 15, hop = 낸 홉, pt·t0 = 낸 값.
3. 후보: 이번 스텝 방출원 e ≠ i 중 sqrt(d²) ≤ 8인 것이다. d²는 dx² + dy²다. 소리라서 시야각·어둠·은신처와 무관하다.
4. 가장 좋은 후보 = (hop_e, d², AgentKey_e) 사전식 최소다.
5. 받아들임 accept:
   - emitted면 best_hop < hop(자기 홉)일 때다.
   - 아니면 ttl0 == 0 ∨ best_hop ≤ hop일 때다.
   - 받아들이면 hop ← best_hop, ttl ← 15, pt·t0 ← 그 경보 값이다. 약한 경보(홉이 큼)는 무시한다.
6. alarm_new = accept ∧ ¬emitted ∧ (ttl0 == 0 ∨ best_hop < hop_prev) ∧ gain[best_hop] ≥ 0.4.
   - 그래서 E7은 홉 0·1에서만 난다(0.36 < 0.4).
   - 같은 세기의 메아리는 E7이 아니다.
7. 방향: accept ∧ ¬emitted ∧ (이번 관측 pred_count == 0 ∧ recency < 0.2)면 away ← normalize(P_i − pt)다. P_i == pt면 0이다. recency는 바꾸지 않는다.
8. 저장한다. ttl, hop, pt, t0, alarm_new를 쓰고, emitted면 alarm_seq ← (alarm_seq + 1) mod 256이다.
9. 관측 18 = alarm_heard(2-2).

- 주의: 6의 'ttl0 == 0'은 1을 뺀 뒤 값이다. 명세 문구와 다른 점은 13절 D6에 있다.
- C++ 꼴은 명세가 정한 것과 같다(`H/env_v2/repertoire.py:132-145`, `D/RL_Policy/RL_V3_R2_SPEC.md:526-539`).

### 8-5. E7과 타이밍

- E′(스텝 t 끝)에서 정한 alarm_new가 스텝 t+1의 결정 관측에 들어간다(`H/env_v2/world.py:1719-1720`). Arbiter b에서 E7이 되고, A′에서 지운다.
- 홉 하나에 1 + jitter 스텝(0.13~0.53 s)이 걸린다(`D/RL_Policy/RL_V3_R2_SPEC.md:340`).
- 위협 없이 도는 소문은 relay_window 30 + alarm_steps 15 = 45스텝 안에 꺼진다(`:344`).

### 8-6. 동점 규칙 모음

| 판정 | 규칙 |
|---|---|
| 경보원 | (홉, d², AgentKey) 사전식 최소. AgentKey는 uint64 비교 |
| 비명 점 | 그 개체를 잡은 위협 중 가장 낮은 위협 색인 |
| 방출 버퍼 | 키 하나에 항목 하나, 비명이 전환 방출을 덮는다 |

---

## 9. FSM_R2 규칙 두뇌 (`H/repertoire_rules.py:272-296`)

관측 float32를 float64로 바꿔 읽는다(`:142-158`).

- seen = obs[1] > 0
- dist = seen ? obs[2] × 20 : ∞
- app = obs[9]
- cover_d = obs[6] × 20
- alarm = obs[18]

래퍼 순서(뒤가 앞을 덮는다, `H/env_v2/rollout.py:788-798`, 시험 `H/tests/test_r2_mechanics.py:1101-1126`):

| 차례 | 줄 | 조건 | 요청 | 근거 |
|---|---|---|---|---|
| 0 | 바탕 | 늘 | GRAZE | `H/repertoire_rules.py:123` |
| 1 | R_base(θ 4, a 0.9) | seen ∧ (dist ≤ 4 ∨ app ≥ 0.9) | FLEE | `:177-180`, `H/eval_v3.py:127` |
| 2 | look (니치) | ¬seen ∧ alarm ≥ 0.4 ∧ cover_d > 5 | FREEZE | `H/repertoire_rules.py:66,228-229` |
| 3 | 가까운 얼기 (freeze cross) | seen ∧ (dist < 6 ∨ app ≥ 0.9) ∧ **지금까지의 요청 == FLEE** | FREEZE | `:53,204-205` |
| 4 | HIDE (니치) | seen ∧ cover_d ≤ 5 | HIDE | `:55,207-208` |

결과를 우선순위로 쓰면 다음과 같다.

```
if (seen && cover_d <= 5)                          → HIDE
else if (seen && (dist <= 4 || app >= 0.9))        → FREEZE   // R_base 의 FLEE 가 3번 줄에서 모두 FREEZE 로 바뀐다
else if (!seen && alarm >= 0.4 && cover_d > 5)     → FREEZE   // look
else                                               → GRAZE
```

- **FSM_R2는 FLEE를 내지 않는다.** R_base가 FLEE를 내는 영역(dist ≤ 4 ∨ app ≥ 0.9)은 3번 줄 조건(dist < 6 ∨ app ≥ 0.9)에 늘 들어간다.
  - 판정 도구 주석도 'FSM은 도망을 쓰지 않는다'다(`H/eval_v3.py:375`).
  - 확인: `v3_r2_on`, 시드 20000 × 1500스텝에서 요청 192,000개 중 FLEE 0이었다(GRAZE 154,622 / HIDE 29,983 / FREEZE 7,395).
- 3번 줄의 'dist < 6'은 효과가 없다. 4 < dist < 6이고 느리면 GRAZE다(13절 D5).
- 규칙은 스텝마다 요청을 내고, Arbiter가 `reads`일 때만 읽는다. C++은 reads일 때만 계산해도 같다.
- 마스크와의 관계: HIDE는 seen ∧ cover_d ≤ 5라 '위협을 안다'와 cover_dist < 0.75를 만족한다. FREEZE는 seen이거나 alarm ≥ 0.4다. 그래서 규칙 요청은 늘 판 3 가능 조건 안이다.
- 문턱 비교는 float64로 (double)ObsF × 20 ≤ 4.0 꼴로 한다. obs ≤ 0.2f 같은 꼴로 바꾸지 않는다(11-2).

---

## 10. 스텝 순서와 결정 시계

### 10-1. 결정 시계

- 1 결정 스텝 = `StepSeconds` = 8/60 s = 0.1333 s, 7.5 Hz다(`S/AI/Policy/EcoBehaviorConfig.h:18,31`).
- 언리얼은 `FStepClock`(논리 틱 1/60 s, 반올림 누적)으로 스텝 수를 센다(`S/AI/Policy/EcoPolicyClock.h:23-54`).
- v3 논리 상태 전이는 모두 이 스텝에서만 일어난다. 연속 이동은 스텝 사이를 보간할 뿐이다(`D/RL_Policy/RL_V3_R2_SPEC.md:501-503`).
- **v3는 전역 스텝 번호 t 하나로 모든 개체를 같은 스텝에 처리한다.** 경보 t0·relay_window, 어둠, 포식자·초식 상호작용이 같은 스텝을 전제한다. v1의 개체별 위상 분산(`AdvanceDecisionPhase`, `S/AI/Policy/EcoPolicyClock.h:56-80`)을 v3에 쓰면 파리티가 깨진다.

### 10-2. `World.step` 순서 (v3 경로, `H/env_v2/world.py:1416-1553`)

| # | 단계 | 읽는 것 | 쓰는 것 | 근거 |
|---|---|---|---|---|
| 0 | (요청 준비) 관측 → `rep_peek` → 마스크 → 망/규칙 | 직전 끝 관측·기하, RepState | Request | `H/eval_v3.py:575-578`, `H/env_v2/rollout.py:746-752` |
| A | Arbiter | 결정 관측(직전 끝 기하), E, d(t), alarm_new | RepState (행동·잠금·사건 등) | `H/env_v2/world.py:1763-1764` |
| B | Controllers | 같은 기하, 결정 때 위치·먹이 셀 | vel, gait, eat, drain, see(다음 관측), still, crouch, cover_mult | `:1765-1780` |
| A′ | AlarmEmit (판 3) | switch, 결정 관측, 결정 때 위치, t | 방출 버퍼, entry_cause, alarm_new ← 0 | `:1437-1438,1785-1792` |
| C1 | 초식 이동 | vel, face | pos, head | `:1450-1455` |
| C2 | ThreatStep | 이동 뒤 초식 pos, still·cover_mult, 위협 상태, d(t), 잠 | 위협 pos·head·vel·상태, caught | `:1462`, 7절 |
| C3 | 비명 (판 3) | caught, 잡은 위협 pos | 방출 버퍼 덮기 | `:1463-1464` |
| C4 | 섭식·대사 | eat·drain 배수, d(t), 이동 뒤 셀 | E, 먹이 | `:1471-1481` |
| C5 | 번식 | E, repro_cd | E, repro_cd | `:1484-1489` |
| C6 | 사망 | caught, E ≤ 0 | done | `:1492-1494` |
| C7 | 피식 EMA | 잡힌 수 ÷ N(128) | pred_ema = 0.95·ema + 0.05·(n/N)·10 | `:1497-1501`, `H/configs/default.yaml:32-33` |
| C8 | 먹이 재생 | 먹이 격자 | 먹이 격자 | `:1505-1507` |
| D | t ← t + 1, 훅 내보내기, Tick | | steps_in, lock, startle, wake | `:1511-1516` |
| D′ | 어둠 갱신 (새 t) | t | d, visibility, to_transition, 위협 잠·속력 배수 | `:1524-1528` |
| E | Perception | pos, head, 위협, d, see·see_last, 먹이 | 기하(다음 결정 관측) | `:1531` |
| E1 | perceive | 기하 | away, recency | `:1538` |
| E′ | AlarmReceive (판 3) | 방출 버퍼, 스텝 끝 pos, AgentKey, 이번 pred_count, recency | 경보 칸, away(방향) | `:1539-1540,1839-1846` |
| F | Observation | 위 모두 | 관측 18/19 | `:1541` |
| G | Respawn | done | 새 개체 상태, 그 행만 E~F 다시 | `:1544-1547` |

- `D/RL_Policy/RL_V3_R2_SPEC.md:591-602`의 프로세서 순서는 C4~C8과 D′를 적지 않았다. 코드에는 있다(13절 D8).
- 계획서 e3의 '추론(다음 결정 틱의 요청)'을 G 뒤에 두어도 된다(`D/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md:383`). 다음 스텝 A가 보는 상태와 같기 때문이다. 다만 마스크에 reads가 필요하므로 5-6의 `Prepare`를 먼저 돌린다.
- 보상(생존 +0.01, 에너지 순변화, 번식 +10, 사망 −10)은 추론에 쓰지 않는다. 계약 밖이다.

---

## 11. 결정성, float32, 골든

### 11-1. 결정성

- v3 경로는 Arbiter·제어기·경보·FSM에서 난수를 쓰지 않는다. 지연은 해시다.
- 난수를 쓰는 곳은 셋이다.
  - 세계 생성·리스폰 위치(v1 스트림)
  - 포식자 배회 선회(v1 스트림 M_base개, 플레이어는 threats 스트림 3)
  - 원거리형 포획 판정
- 골든은 이 값을 **입력으로 넣는다**.
- 파이썬은 기하·Arbiter 입력을 float64로, 관측·망을 float32로 계산한다.
- UE5 `FVector`는 double이다. C++도 기하는 double, 관측은 float로 바꿔 넣는 것을 권한다. 이렇게 하면 문턱 비교가 파이썬과 같은 정밀도에서 이뤄진다.

### 11-2. 문턱 근처 제외 규칙 (`D/RL_Policy/RL_V3_R2_SPEC.md:489-492`를 넓힘)

골든 표본에서 아래 경우를 빼고, **뺀 개수를 골든 헤더 주석에 적는다**. 문턱 바로 위·아래 사례는 따로 골든 하나로 묶어 허용 오차를 적는다.

| 비교 | 빼는 범위 |
|---|---|
| 실거리 대 반경 (초식 탐지 반경, 동족 20, 위협 시야 14, 포획 1·3, 경보 8, event_near 8, stalk 6, 플레이어 돌진 6, 은신 가장자리 0, 분리 5) | \|d − r\| < 1e−4 |
| 시야각 cos (초식 0.5, 위협 cos 75°) | \|cos − c\| < 1e−5 |
| 경보원 d² 동점 | 차 < 1e−4 |
| 접근 관측 대 0.9 (E2, FSM) | \|x − 0.9\| < 1e−5 |
| 에너지 대 0.25 (E4), 먹이 대 0.06 (food_ok) | \|x − c\| < 1e−6 |
| FSM의 dist 4·6, cover_d 5 (obs × 20 값) | \|x − c\| < 1e−4 |
| 망 argmax | 허용된 칸 중 1·2위 로짓 차 < 1e−4 |

**빼지 않는 정확한 같음** (구조상 나온다. C++이 비트 단위로 맞춰야 한다):
- d = 0.5: 전환 스텝. E5와 밤잠 문턱 d ≥ 0.5가 참이다.
- alarm_heard = 0.4: (홉 0, ttl 6), (홉 1, ttl 10). 마스크와 look 줄이 열린다.
- 정수 비교: 잠금, 지연, ttl, 홉, relay_window, 남은 스텝.

### 11-3. 경보 세기 표 `kAlarmHeard[hop][ttl]` (float32, ttl 0은 0)

| ttl | 15 | 14 | 13 | 12 | 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 홉 0 | 1.0 | 0.93333 | 0.86667 | 0.8 | 0.73333 | 0.66667 | 0.6 | 0.53333 | 0.46667 | **0.4** | 0.33333 | 0.26667 | 0.2 | 0.13333 | 0.06667 |
| 홉 1 | 0.6 | 0.56 | 0.52 | 0.48 | 0.44 | **0.4** | 0.36 | 0.32 | 0.28 | 0.24 | 0.2 | 0.16 | 0.12 | 0.08 | 0.04 |
| 홉 2 | 0.36 | 0.336 | 0.312 | 0.288 | 0.264 | 0.24 | 0.216 | 0.192 | 0.168 | 0.144 | 0.12 | 0.096 | 0.072 | 0.048 | 0.024 |

- 파이썬 값은 float32(float64(gain[h] × ttl) ÷ 15)다. 굵은 칸은 float32 0.4f와 정확히 같다.
- C++ float 경로(0.6f × 10 ÷ 15)로 계산해도 열림·닫힘이 같다. 확인했다.
- 그래도 헤더에 이 표를 그대로 실어 C++이 표를 읽게 한다. 계산 순서 차이로 생길 수 있는 1 ulp 차이를 없애기 위해서다.

### 11-4. 골든 종류 (G1·G2는 `H/export_weights_v3.py`가 이미 낸다. G3~G10은 더할 것)

| # | 골든 | 입력 | 기대 출력 | 허용 | 규모 (제안) |
|---|---|---|---|---|---|
| G1 | 순전파·마스크·argmax (R1b) — **이미 만드는 중** | 관측 18 float32, 마스크 5 | 로짓 5, 마스크 argmax | `H/export_weights_v3.py`의 값: 로짓 \|Δ\| ≤ 1e−4(`LOGIT_TOL`), argmax 일치. 1·2위 차 < 1e−4는 근접 동점 묶음으로 따로 둔다 | 보정 시드 20000~20002 × 3000 결정 표본 + 합성 마스크 + 근접 동점 + 동점 규칙 묶음 |
| G2 | 마스크 판 2/3 — **이미 만드는 중** | 관측 18/19 | 가능 5칸, 허용 ∧ 가능 | 정확 | 문턱 바로 위·아래 격자(판 2·판 3) |
| G3 | 관측 만들기 | 세계 스냅샷(초식·위협 pos·head·vel, 은신처 원, 작은 먹이 격자, E, RepState, d, pred_ema, 경보 칸) | 관측 18/19, 결정 관측 기하(double) | 관측 \|Δ\| ≤ 1e−5, 정수 칸 정확 | 스냅샷 20 × 128 |
| G4 | Arbiter 여러 스텝 열 | 결정 관측 열(스텝마다 pred_count·*_ev·d·E·in_cover·cover_k·alarm_new)과 요청 열 | 스텝마다 behavior, phase, steps_in, seq, lock_left, startle_left, ev_wait, decide, switch, event, fire, e7 | 정확 | 20열 × 50스텝 (판 2용, 판 3용) |
| G5 | 제어기 | 6-1 입력, RepState | vel, gait, eat, drain, see, still, crouch, face, cover_mult | 실수 \|Δ\| ≤ 1e−6, 정수 정확 | 100 |
| G6 | 경보 내기·듣기 | 고정 위치, switch·행동, 결정 관측, 비명, 경보 칸, AgentKey | 방출(hop, pt, t0), 수신 뒤 경보 칸·away·alarm_seq, alarm_heard | 정확(pt·away는 1e−9) | 20 사례 + T8 줄 배치 |
| G7 | 위협 스텝 | 위협 상태 전부, 초식 pos·still·cover_mult·in_cover, 선회 난수, 원거리 난수 | 위협 pos·head·vel·상태·남은·cd, caught, caught_by | 위치 1e−9, 정수 정확 | 유형별 30 + 상태 전이 열 |
| G8 | FSM_R2 | 관측 19 | 요청 | 정확 | 200 (문턱 위·아래 묶음 따로) |
| G9 | 해시·낮밤 | (seed, slot, gen), (T, o, t) | jitter·H 값, d·r·visibility·to_transition | 정확 / 1e−9 | 각 50 |
| G10 | 끝에서 끝 논리 열 | 작은 복제 세계(초식 16, 위협 2~3, 은신처 2) 시작 상태와 스텝마다 난수 | 300스텝 동안 개체별 behavior·phase·seq와 경보 칸·위협 상태 | 논리 칸 정확 | 판 2·3 각 1 |

- G1·G2는 다른 작업의 `H/export_weights_v3.py`(커밋 전)가 이미 낸다(보정 시드 20000~20002, 로짓 허용 1e−4). 이 계약은 그 값을 따른다.
- G3~G10의 세계 시드도 **보정 시드 20000~20007**을 제안한다. 판정 시드(10000~10219)와 탐색·관문 시드와 겹치지 않고, f_dec·기준값 측정이 이미 쓰는 범위라 새 오염이 없다. 쓰기 전에 사전 등록 문서의 시드 목록과 한 번 더 맞춘다.
- SLEEP 경로는 G4에 '단위 사례' 열 하나로만 넣는다(1-3).
- 골든 헤더 주석에 적을 것: 모델 경로와 모델 지문(zip sha256), `kContractHash`·`kWorldContractHash`, 문턱 근처로 뺀 개수(종류별), 생성 시드. 시각·절대 경로는 적지 않는다(같은 입력이면 같은 바이트, 만드는 중인 `H/export_weights_v3.py` 머리말과 같은 규칙).
- 생성 규칙과 허용 오차는 C++을 쓰기 전에 확정한다(`D/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md:398`). 이 표가 제안이다.

---

## 12. 언리얼 대응

### 12-1. 단위

- 엔진 무관 헤더(`EcoPolicyV3Inference.h`, `EcoRepertoire.h`, `EcoKinAlarm.h`, `EcoThreatModel.h`)는 **파이썬 단위**(1단위 = 200 cm, 스텝)로 계산한다. v1 조향 골든도 파이썬 격자 단위를 썼다(`H/export_weights.py:158-163`). Mass 층이 cm ÷ 200, cm/s ÷ 1500으로 바꿔 넘긴다.
- 자주 쓰는 환산:

  | 값 | 파이썬 | 언리얼 |
  |---|---|---|
  | 초식 시야 | 20 | 4000 cm |
  | 위협 시야 | 14 | 2800 cm |
  | 포획 | 1 | 200 cm |
  | event_near·경보 | 8 | 1600 cm |
  | stalk_dist | 6 | 1200 cm |
  | θ 4 / FSM 은신처 5 | 4 / 5 | 800 / 1000 cm |
  | 은신처 거리 정규화 | 20 | 4000 cm |
  | 분리 반경 | 5 | 1000 cm |
  | 먹이 셀 | 2 | 400 cm |
  | 속력 0.6 | 0.6/스텝 | 900 cm/s |
  | 잠금 12 / 8 / 40 | 스텝 | 1.6 / 1.07 / 5.33 s |
  | 놀람 3 | 스텝 | 0.4 s |
  | 경보 ttl 15 / 중계 창 30 | 스텝 | 2 / 4 s |
  | 돌진 12 / 탈진 30 | 스텝 | 1.6 / 4 s |
  | 쿨다운 5 / 30 | 스텝 | 0.67 / 4 s |

- 접근 관측의 v_j는 위협의 '지난 결정 스텝 동안의 변위'다. 순간 속도가 아니다.

### 12-2. Mass 조각 (제안, 계획서 e3)

| 조각 | 담는 것 |
|---|---|
| `FEcoBehaviorStateFragment` | 5-1의 칸 전부(behavior, phase, steps_in, seq, lock_left, startle_left, ev_wait, jitter, hide_target, arrived, prev_*, away, recency, 기상 칸), 그리고 AgentKey |
| `FEcoKinAlarmFragment` (판 3) | 8-1의 칸 |
| `FEcoPerceptionCacheFragment` | 결정 관측 기하(double): pred_count, d_pred_min, pred_approach, *_ev, in_cover, cover_k, away_from_pred, to_centroid, separation, food_grad, see_mult·see_mult_last, 관측 float 18/19 |
| `FEcoControlOutFragment` | gait, eat·drain 배수, still, crouch, cover_mult |
| `FEcoThreatStateFragment` | 유형, 원거리, 야행성, 잠, 상태·남은, 플레이어 모드·남은, cd, head, 지난 변위, 기본 속력, 포획 반경 |

- 계획서 3-2의 복제 필드: 사슴은 BehaviorId 3비트, Phase 2비트, Gait 2비트, Seq 1바이트, LookYaw 1바이트, AlarmSeq 1바이트, AlarmHop·EntryCause 4비트다. 늑대는 ThreatState 1바이트다(`D/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md:187-191`). 값이 바뀔 때만 보낸다.
- 논리는 모두 서버·단독에서만 돈다(`AGENTS.md` 2절 2항).

### 12-3. 개체 키와 시드

- **파리티 시험 모드**(정책 테스트 스포너, 골든 G10): `AgentKey = (SlotIndex << 32) | Generation`, `Seed` = 파이썬 세계 시드다. 파이썬과 비트 단위로 같은 지연과 동점이 나온다.
- **통합 모드**(조정자 스포너): `AgentKey = (uint64)StableAgentId`, `Seed` = 세션 시드다. 해시와 분포는 같지만 값은 다르다. 리스폰 대신 새 개체가 나므로 새 StableAgentId가 곧 새 세대다. 행동 seq는 새 개체에서 0으로 시작해도 된다(애니메이션 전용).
- 이 대응은 사람 확인이 필요하다(13절 열린 질문 3).

### 12-4. v1 C++에 지금 없는 것

v1 경로에 있는 것:
- 관측 7
- 시그모이드 조향 무게 4와 `normalize(v) × 900 cm/s` 조향
- 전역 피식 EMA, 시간 기준 시계, 회전 쓰기
- 포획 프로세서(쿨다운 5스텝, 은신 2.5배 하나)

근거: `S/AI/Policy/EcoBehaviorConfig.h`, `D/RL_Policy/UNREAL_POLICY_INTEGRATION.md:143-187`.

v3에 필요하지만 커밋된 소스(`cd19a43`)에 없는 것(`S/`에서 `EEcoBehavior`·`Repertoire`·`KinAlarm`·`ThreatModel`·`EcoPolicyV3`를 찾았다). 2번(망·마스크)은 다른 작업이 `S/AI/Policy/EcoPolicyV3Inference.h`·`PolicyWeightsV3.h`·`PolicyGoldenVectorsV3.h`·`Tests/EcoPolicyV3InferenceTest.cpp`로 만드는 중이다(커밋 전):

1. 관측 칸 7~18: 낮밤 2칸, 접근 관측(위협 변위 필요), kin_alarm, 행동 원핫, 경과, threat_recency, alarm_heard. 그리고 행동별 탐지 배수와 사건 비교 시야.
2. 마스크 판 2/3, 범주 머리(로짓 5, argmax), `PolicyWeightsV3.h`
3. Arbiter(잠금·사건 E1~E7·지연 해시·놀람·HIDE 목표·도착), `EEcoBehavior`, 행동 상태 조각
4. 행동별 제어기: 보행 0/360/900, 섭식·대사 배수, 웅크림, FREEZE heading
5. 행동별 은신 배수(4.0/1.5/2.5/1.0)와 정지 탐지 1.8. 지금은 2.5 하나다(`S/AI/Policy/EcoBehaviorConfig.h:37`).
6. 위협 모델: 잠행-돌진-탈진 상태 기계, 플레이어 대역 모드, 주행성 밤잠, 박명 감속, 원거리형 확률 포획, 위협 변위 기록
7. 어둠 값 d(위상 시각 식)와 visibility·to_transition
8. M8 경보(내기·비명·듣기·E7)
9. FSM_R2 규칙 두뇌
10. AgentKey·세대 규칙, 전역 동기 스텝

- 그대로 다시 쓰는 것: `EcoBehaviorConfig.h`의 단위 상수, `FStepClock`, `EcoHeading.h`의 회전 쓰기, 이웃 격자(생존 필터 포함)
- v3 사슴에서 끄는 것: Social 출력 보정, 공황 강제 은신, Social 경보 상태 쓰기(`D/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md:385`)

---

## 13. 명세와 코드의 차이, 열린 질문

### 13-1. 차이 (코드가 이긴다. 이 문서는 코드를 따랐다)

| # | 명세·문서의 말 | 코드 | 근거 |
|---|---|---|---|
| D1 | R1 명세 2절 '가능': FLEE·FREEZE는 threat_recency > 0, HIDE는 은신처 관측 < 0.75면 된다 | 마스크 판 2: threat_recency ≥ 0.2, HIDE도 위협을 알아야 한다(판 1 → 2, 10-07 수정) | `D/RL_Policy/RL_V3_R1_SPEC.md:27-29` 대 `H/env_v2/rep_policy.py:8-13,67,172-178` |
| D2 | R0 명세 2·3절 M6: 웅크림 은신 ×2.5, 은신처 안 GRAZE ×1.5 | 웅크림 4.0, GRAZE 1.5, SLEEP 2.5, 그 밖 1.0 (계수 넷) | `D/RL_Policy/RL_V3_R0_SPEC.md:15,28` 대 `H/configs/v3_r1_on.yaml:114-117` |
| D3 | R0 명세 M3: 체감 ≤ 6이면 최대 12스텝 돌진. 계획서 3-1: '잠행형 270, 6단위 안이면 1350으로 1.6초 돌진' | 돌진 이동 12번 + 마지막 판정 1스텝(탈진 속력). 6은 **체감** 거리라 실거리 6/4/3.33/1.5. 표적이 없는 잠행형은 270이 아니라 **기본 추격 속력**으로 배회한다 | `D/RL_Policy/RL_V3_R0_SPEC.md:25`, `D/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md:133` 대 `H/env_v2/world.py:2075,2300-2313,2359-2363` |
| D4 | R0 명세 플레이어: '가장 가까운 무리 쪽', '돌진 최대 20스텝, 그 뒤 휴식' | 체감 거리가 가장 가까운 개체 쪽, 맵 전체를 본다. 돌진 이동 20번 + 멈춘 판정 1스텝 뒤 휴식 30. 배회 모드에서도 닿으면 잡는다 | `D/RL_Policy/RL_V3_R0_SPEC.md:29` 대 `H/env_v2/world.py:1999-2002,2057-2058,2314-2336,2379-2394` |
| D5 | R2 명세 4절·`fsm_r2_spec` docstring: FSM_R2 = HIDE > FREEZE 가까운 판(보임 & (거리 < 6 또는 접근 ≥ 0.9)) > look > R_base | 가까운 얼기는 바탕 요청이 FLEE일 때만 걸린다. 그래서 실제 FREEZE 영역은 R_base의 FLEE 영역(거리 ≤ 4 ∨ 접근 ≥ 0.9)과 같고, **FLEE는 나오지 않는다**. 4 < 거리 < 6 & 느림은 GRAZE다 | `D/RL_Policy/RL_V3_R2_SPEC.md:461-463` 대 `H/repertoire_rules.py:204-205`, `H/eval_v3.py:375`, 실측(9절) |
| D6 | R2 명세 3-2 5번: E7 표시는 '원래 ttl == 0이었거나 hop_best < 원래 hop' | ttl0(1을 뺀 뒤) == 0 ∨ hop_best < hop_prev. 명세 6절 C++ 꼴(`Ttl0==0`)은 코드와 같다 | `D/RL_Policy/RL_V3_R2_SPEC.md:330-334` 대 `H/env_v2/repertoire.py:589,621-622` |
| D7 | R2 명세 6절: 실수 비교는 거리 ≤ 반경, cos ≥ 문턱, 미리 계산한 hop_gain^h ≥ event_alarm뿐이다 | 관측 alarm_heard ≥ 0.4(마스크 판 3, look 줄)에서 정확한 같음이 구조상 나온다. 어둠 d = 0.5도 E5·밤잠 문턱과 정확히 같다. 둘 다 빼면 안 되고 비트 단위로 맞춰야 한다(11-2, 11-3) | `D/RL_Policy/RL_V3_R2_SPEC.md:488` 대 `H/env_v2/rep_policy.py:174`, `H/env_v2/world.py:675,1112` |
| D8 | R2 명세 7절 프로세서 순서 10단계(Arbiter … Respawn) | 포식자와 Tick 사이에 섭식·대사·번식·사망·피식 EMA·먹이 재생이 있고, Tick과 Perception 사이에 어둠 갱신이 있다. A′는 제어기 뒤(같은 입력이라 결과는 같다) | `D/RL_Policy/RL_V3_R2_SPEC.md:591-602` 대 `H/env_v2/world.py:1434-1541` |
| D9 | R0 명세 사건 '위협 8 안·돌진' | E2는 사건 비교 시야 값으로 '8 안으로 들어옴' 또는 '접근 관측 ≥ 0.9가 됨'이다. 돌진 상태를 직접 보지 않는다. E1도 사건 비교 시야 수다 | `D/RL_Policy/RL_V3_R0_SPEC.md:20` 대 `H/env_v2/repertoire.py:414-425` |
| D10 | R1·R2 명세 1절 '포식 뒤 식사 쿨다운 5스텝' | 스텝 시작에 1을 빼고 0이면 사냥한다. 잡은 뒤 4스텝 동안 사냥하지 않고, 5번째 스텝에 다시 잡을 수 있다 | `D/RL_Policy/RL_V3_R2_SPEC.md:93` 대 `H/env_v2/world.py:2034-2035,2141` |
| D11 | v1 계약 표: predator_count MaxCap 5 | 코드는 8이다(v1 문서 머리말이 이미 적었다). v3도 8이다 | `D/RL_Policy/POLICY_CONTRACT_V1.md:12,47` 대 `H/configs/default.yaml:27` |

### 13-2. 열린 질문 (사람·팀 확인)

1. **FSM_R2가 도망을 쓰지 않는 것이 의도인가?** 경보 세계에 출시하는 규칙 두뇌가 FLEE를 전혀 내지 않는다(D5). 손 규칙 판정·모방 교사 값(U_ESC 0.813 등, `H/results/v3/r2/judge/PREREG.md:196`)은 이 규칙으로 쟀으므로, 고치면 기준값이 바뀐다. 계약은 지금 코드대로 적었다.
2. **SLEEP을 C++에 실제로 구현하나?** 두 두뇌에서 일어나지 않는다. 칸과 분기는 두고 단위 골든 하나만 둘지, 아예 막고 `static_assert`로 표시할지 정한다.
3. **AgentKey 대응**(12-3): 파리티 모드(슬롯·세대)와 통합 모드(StableAgentId)를 나누는 안으로 되는가? 통합 모드의 Seed는 무엇으로 하나?
4. **전역 동기 스텝**: v3 프로세서를 개체별 위상 분산 없이 같은 스텝에 모두 돌리는 것(10-1)을 Mass 담당(wonkii)과 합의해야 한다.
5. **죽은 개체의 한 스텝**: 파이썬은 죽은 스텝의 관측에 시체를 동족으로 센다(2-3). 언리얼이 바로 빼면 그 스텝의 kin·분리·kin_alarm이 다르다. [기록만]으로 둘지, 파이썬을 바꿔 재학습 범위로 넣을지 정한다.
6. **먹이 모델**: 관측 0·먹이 기울기·food_ok·섭식은 셀 격자 기준이다. 언리얼 지역 먹이와 어떻게 잇나? 계획서는 [기록만]과 지역 재생 켜기를 제안했다(`D/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md:137`).
7. **피식 EMA 분모**: 파이썬은 N = 128 고정으로 나눈다(리스폰으로 늘 128). 언리얼 v1은 '스텝 안 포획 전 생존 수 최대'다(`D/RL_Policy/UNREAL_POLICY_INTEGRATION.md:175`). 개체 수가 변하는 레벨에서 어느 쪽이 계약인가?
8. **사람 플레이어**: 학습의 플레이어형은 맵 전체를 보는 모드 기계다. 사람 폰을 서버 대리로 위협 목록에 넣으면 움직임은 학습 밖이다. 속력 상한(1170 cm/s)만 묶는 것으로 충분한가?
9. **두뇌 선택 단위**: R1b는 M8이 켜진 세계에 둘 수 없다. 두뇌(그리고 M8 켜기)를 세계 단위 콘솔 변수로 고르는 안(`D/RL_Policy/RL_V3_REPERTOIRE_DRAFT.md:196-200` '선택 모드')으로 되는가? 한 레벨에 두 두뇌를 섞지 않는다는 규칙을 둘지 정한다.
10. **세계 계약 해시**(1-4): 입출력 해시(이미 있음)에 세계 해시를 더하는 안과 그 키 목록을 승인받아야 한다.
11. **맵 경계**: 파이썬은 정사각 맵 벽에서 초식은 멈추고(자르기) 위협은 반사한다. 계획서 결정 13(벽 따라 미끄러짐)은 학습 밖이다. 이동 막힘 처리를 어떻게 기록할지 정한다.
12. **골든 생성 시드와 허용 오차**(11-4): G3~G10의 시드(20000~20007 제안)와 표의 허용값을 확정한다. G1 로짓 허용은 1e−4(만드는 중인 값)로 둘지, v1처럼 1e−5로 좁힐지도 정한다(v1 `D/RL_Policy/POLICY_CONTRACT_V1.md:98`).
