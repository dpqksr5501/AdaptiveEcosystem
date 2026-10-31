# 늑대 독립 개발 상세 계획

작성일: 2026-10-14 / UE 5.8 / 상태: Planned. [마스터 계획](README.md), [공통 런타임](COMMON_RUNTIME_IMPLEMENTATION_PLAN.md)을 전제로 한다. 새 타입/asset/수치는 제안이며 현재 구현 완료를 의미하지 않는다.

현재 기본 구현은 [마일스톤 기록](IMPLEMENTATION_MILESTONES.md), 사용은 [Editor 빠른 시작](EDITOR_QUICK_START.md), 파일 책임은 [Source 책임](SOURCE_RESPONSIBILITIES.md)을 읽는다. W8 release와 후속 Carcass gate는 기본 코드 작성·빌드와 별도다.

## 1. 독립 개발의 목표

사슴 Brain 없이 늑대가 휴식·순찰·수색하고, 허용 감각으로 먹잇감 대역을 발견·추적하며, 차폐/표적 상실 시 마지막 위치를 조사하고, 도달 불가·timeout·포만/피로 조건에서 사냥을 포기해야 한다. 공격은 공통 권위 요청/결과를 통해 수행하고 섭식·cooldown·생존·예약·복제를 각각 분리한다.

늑대 단독 release는 실제 사슴 포식 검증이 아니다. moving fixture와 test receipt로 사냥 실행의 단계·실패·취소를 검증한다. 이후 실제 Entity target adapter로 바꿔 death receipt/보상/Population·PredationHistory를 통합한다.

현재 늑대는 PPO가 아니라 감각 기억 기반 PredatorMovement와 proximity capture 경로다. 새 StateTree는 별도 W1이다. 사슴 V1 네 행동을 늑대의 Hunt/Attack 출력으로 해석하지 않는다.

## 2. Config·Trait·파일·에셋

| 항목 | 신규 계획 |
| --- | --- |
| Authority Config | `EC_Wolf_StateTree`: common grounded/Nav/StateTree/Avoidance·wolf 감각/decision/attack state·network |
| Client Config | `EC_Wolf_Client` 또는 common trait Client 분기. 감각/target/path/attack/lifecycle 논리 제외 |
| 종별 Trait | `UEcoWolfBehaviorTrait`: Wolf input/decision/hunt execution·필요 capture cooldown 상태 |
| StateTree | `ST_Wolf_Utility`: Mass schema·common Task + wolf selection/attack Task |
| 프로필 | `DA_WolfBehavior_Default`, `DA_WolfLocomotion`, `DA_WolfAttack`, `DA_WolfNutrition`, patrol/LOD/interaction profile |
| Smart Objects | `SO_WolfRest`, `SO_WolfFeedSite`; 후속 `SO_Carcass` |
| 레벨 | `L_WolfOnly_Flat`, `L_WolfOnly_Terrain`, `L_WolfOnly_Network` |
| 대역 | `DA_WolfPreyScenario_*`: moving cue·소음·LOS·target generation·공격 결과 시나리오 |

SpeciesId는 현재 `Wolf`를 유지하고 registry의 Predator role과 함께 사용한다. 새 PreyRelation profile을 두어 앞으로 다른 herbivore 또는 player와의 관계를 확장한다. Brain이 모든 `!bPredator`를 무조건 먹잇감으로 가정하지 않는다.

파일 제안: `AI/Behavior/Wolf/EcoWolfBehaviorTypes.h`, `EcoWolfInputProcessor.*`, `EcoWolfActivityProcessor.*`, `StateTree/EcoWolfTasks.*`; 공격·nutrition 공통 거래는 `Creature/Runtime/Interaction/`에 둔다. Path/Movement/Replication service를 늑대용으로 복제하지 않는다.

현재 기존 Predator Trait의 `FEcoPredatorStateFragment.EatCooldown`이 capture gate다. 새 AttackRuntime이 같은 cooldown을 독립으로 갱신하지 않게 공통 attack contract의 single writer로 정리한다. Config의 combat execution mode는 LegacyProximity 또는 RequestDriven 중 하나다.

현재 Integrated Creature의 포획은 단순 거리만 보는 규칙이 아니다. Source는 최근 직접 시각 증거(0.25초 이내), 선택한 target 일치, 현재 LOS를 요구하고 CoverHideMult에 따른 체감 거리를 사용한다. 첫 `AP_Wolf_ContactV1` profile은 이 조건을 명시적으로 보존한다. 다른 windup/range/차폐 조건은 새 attack profile version이며 baseline에 조용히 적용하지 않는다.

## 3. 표적·감각·개체별 데이터

| 데이터 | 필수 내용 | writer |
| --- | --- | --- |
| 기존/adapter PreyCue | source·last observed position/time, confidence·uncertainty, target ref domain/ID | 감각 Processor |
| `FEcoWolfInputFragment` | EnergyRatio, valid prey cue·관찰 거리, 주변 허용 후보 summary·patrol/rest·attack/move feedback | input gather |
| `FEcoWolfDecisionFragment` | Patrol/Search/Pursue/Attack/Rest 선호, selected target ref·허용 관찰 위치, intent revision·사유 | StateTree |
| `FEcoWolfHuntExecutionFragment` | 실행 hunt stage, pursuit start/deadline, target revision·retry·blacklist/cooldown, last allowed cue/time | PostPolicy Activity |
| 공통 ActivityIntent/MoveRequest | 허용 목적지·style·speed·유효시간 | Activity/Arbiter 각각 한 번 |
| `FEcoAttackRequestFragment`/result | request ID·target ref·evidence·range/cooldown profile version·결과 사유 | Attack Task가 요청, common resolver가 결과 |
| nutrition/이용 exposure | mode·resource/receipt ID·실제 이용 구간 | common coordinator/interaction |

대역 표적은 FixtureId이고 실제 prey는 StableAgentId다. 기존 `FEcoPreySenseFragment`의 ageing·`MakeReadSnapshot` 수학은 재사용하되 legacy TargetAgentId에 fixture ID를 주입하지 않는다. 새 target adapter가 domain을 보존한다. 임시 EntityHandle은 lookup 최적화용 캐시이며 매 접근 시 epoch/유효성을 검증한다.

표적의 실제 current pose는 감각 service의 검사나 AttackResolver의 권위 거리 검사에서만 사용한다. Brain/Navigation은 허용 cue의 위치를 사용한다. 권위 공격 실패의 `OutOfRange`를 Brain에게 정확한 숨겨진 좌표와 함께 반환하지 않는다.

초기 입력에 Stamina/pack role/territory 지식을 만들지 않는다. extension mode에서는 capability Fragment와 명시적 version을 추가한다. 공격/자원 결과와 별개인 HuntExecution 상태는 진단용 논리 단계이며 prey HP/Dead의 사본이 아니다.

## 4. StateTree 계층

```text
Root
  AwaitInput
  InactiveOrDead                         [기존 Alive/Death 관찰]
  AuthorityTravelOrWaiting               [Travel 목표 추종 또는 대기]
  CaptureCooldown                       [권위 cooldown 읽기]
  UrgentRecovery                        [확장 physiology 조건]
  NormalLife                            [Highest Utility]
    Hunt
      SelectPrey
      ApproachOrPursue
      InvestigateLastKnownLocation
      RequestAttack
      AwaitAttackResult
      CaptureResultHandling
    Search
      SelectSearchArea
      SearchMove
    Patrol
      SelectPatrolPoint
      PatrolMove
    Rest
      RequestRestSlot
      ApproachRest
      Rest
```

Nutrition mode가 InstantCaptureReward이면 CaptureResultHandling은 완료 receipt/cooldown을 관찰하는 단계다. CarcassConsumption 모드에서만 `SelectCarcass → ClaimFeedSlot → Approach → Consume` 하위 실행을 추가한다. Eat animation 완료가 실제 capture receipt를 만들지 않는다.

하위 상태 실패는 immediate retry loop가 아니라 실패 사유·target cooldown·대체 행동 선택으로 연결한다. `AwaitAttackResult`는 current request result/deadline에 wake하며 busy polling하지 않는다. 표적을 바꾸면 기존 path/attack pending 요청을 먼저 revision 취소한다.

## 5. Utility·표적 선택·사냥 포기

| 선택 | 입력/curve 방향 | Enter/interrupt |
| --- | --- | --- |
| Hunt | 낮은 Energy·유효 prey cue·신뢰도·가까운 관찰 위치·예상 비용 | cooldown 0, valid target, blacklist 아님 |
| Search | 배고픔·허용 cue/최근 관찰 후 target loss·새 탐색 필요 | 수색 영역/시간 유효, 무한 추적 금지 |
| Patrol | authored territory/순찰 경로·constant 탐색 선호 | 다른 욕구 낮음, 순찰 목적지 도달 가능 |
| Rest | 포만/회복 필요·안전한 거점 | target 유무와 무관하게 선택 가능, 새 긴급 조건 중단 |
| Eat/Consume | 실제 receipt 또는 유효 Carcass resource·이용 자리 | 가상 성공 flag만으로 production nutrition 시작 금지 |

utility gate와 target candidate ranking을 구분한다. Hunt 선택은 행동 종류이고 어떤 prey를 고를지는 공통 허용 candidate의 `confidence·observed distance·age·도달 가능 상태·기존 target 유지 bias`로 결정한다. candidate가 수백 개인 상황에서 모든 후보 full path를 계산하지 않고 거리/감각으로 제한한 top-K에만 path 예산을 쓴다.

기존 표적 유지 margin, 새 표적 score 개선 threshold, 최대 pursuit duration·새 감각 없이 chase 가능한 memory age, 반복 path 실패 횟수·target cooldown을 profile로 둔다. 특정 target을 계속 선택하는 반례와 모든 score 0일 때 Patrol/Search fallback을 시험한다. profile에 포함한 prey health는 직접 관찰/명시적 허용 정보가 없으면 입력으로 사용하지 않는다.

사냥 포기 사유는 `CueExpired`, `ReachedLastKnownWithoutEvidence`, `PathUnreachable`, `RepeatedBlocked`, `PursuitTimeout`, `TargetInvalid/Dead`, `AuthorityTravel`, `NutritionSatisfied`, 확장 mode의 `StaminaLow`다. 마지막 사유는 기본 mode에 아직 없는 stamina를 가정한 값이 아니다.

## 6. 순찰·수색·추적 구현

### 6.1 authored 생활 영역

World location provider는 Home/Rest location·Patrol route/area를 제공한다. 이 위치는 학습/감각 바깥의 predator 정답 지도나 전체 prey 위치 지도가 아니다. local navigation filter로 통행 가능성을 확인한다. territory boundary의 권위 소유자는 World/행동 profile이며 RegionId는 Migration만 commit한다.

Patrol point는 StableAgentId·seed별 stream으로 고르고 한 waypoint 실패가 전체 runtime을 중단하지 않도록 local cooldown/대체 후보를 둔다. route/area revision이 바뀌면 active request를 취소/재평가한다. no route는 제한된 walkable wander로 fallback한다.

### 6.2 감각과 기억

시각 candidate 검사와 noise event를 기존 perception 의미로 연결한다. behind-FOV/no-LOS target은 시각 관찰로 인정하지 않는다. Hearing cue의 uncertainty를 완벽한 위치처럼 사용하지 않는다. Memory read 시 age/confidence를 계산하고 수색으로 전환한다.

보이는 표적은 최신 허용 위치가 retarget distance threshold를 넘어가고 minimum repath interval이 경과했을 때만 경로 갱신한다. 거리 비교·speed prediction은 관찰 snapshot에서만 계산한다. hidden target을 그리드에서 다시 조회해 last known position을 갱신하지 않는다.

target loss 후 마지막 위치/불확실도 반경의 소수 검색 지점을 후보로 만들고 bounded SearchTime동안 이동한다. 도달 시 새 evidence가 없으면 포기/cooldown하고 Patrol/Search로 돌아간다. 세계에서 target이 삭제됐다는 사실은 수명/ID 검증으로 invalid를 알릴 수 있으나 hidden current location은 제공하지 않는다.

### 6.3 이동/도달

common NavMesh 서비스는 pursuit 목표가 움직이는 조건을 처리한다. StateTree Tick마다 full path를 요청하지 않는다. approach와 sprint의 style·speed cap·turn/accel·body clearance는 Wolf profile이다.

Engage range는 body clearance/공격 프로필과 호환해야 한다. Avoidance가 거리를 유지해 접촉이 불가능하면 합리적인 공격 range/접근 goal을 조정하고 실제 sweep·LOS로 검증한다. prey obstacle을 무조건 제거하거나 위치를 snap하지 않는다.

request Arrived는 그 request의 관찰 목적지 도달이다. 살아 움직이는 prey의 실제 공격 도달과 같지 않다. 도착 후 target validity/최근 cue를 확인해 AttackRequest 또는 Investigate로 전환한다.

## 7. 공격 요청·권위 판정·사망

### 7.1 request-driven 모드

```text
Wolf StateTree: 공격 의도
  → FEcoAttackRequest(owner/target/epoch/request/profile)
  → common AttackResolver: 실제 범위·LOS·Alive·cooldown·관계 검사
  → damage/kill candidate
  → 기존 Lifecycle death commit + unique receipt
  → Ecology predation/population + 선택 nutrition mode
  → Wolf input/result: confirmed success/cooldown 또는 실패 사유
```

Wolf Brain이 피해 적용·prey HP=0·destroy·Food/Population 감소를 직접 수행하지 않는다. common resolver는 실제 pose를 검증해 공격 가능 여부를 결정하고, existing survival/lifecycle가 Death를 확정한다.

현재 opt-in 통합 Entity는 기존 Predator proximity 포획 Processor에서 제외하는 combat mode/tag/query 조건을 먼저 추가한다. `FEcoPredatorStateFragment`는 cooldown compatibility로 재사용할 수 있으나 legacy processor와 new resolver가 동시에 감소/판정하지 않는다.

### 7.2 판정 순서와 충돌

- 신규 execution은 completed movement 뒤 request를 수집·검증하고 기존 PostActorTick의 첫 survival/death 단계에서 확정한다. 같은 frame baseline의 predation-before-steering 의미와 구분한다.
- target ref→StableAgentId lookup→Entity validity·Alive·species relation·같은 WorldEpoch·요청 age→실제 range/LOS→cooldown 검사를 수행한다.
- ContactV1의 fresh direct sight·target 일치·cover distance multiplier를 함께 검증한다. legacy geometry의 cover 의미와 실제 Social Occupied의 차이는 별도 contract로 기록하고 새 Shelter 차폐를 곧바로 기존 cover 수치라고 간주하지 않는다.
- 동일 prey의 여러 attack은 common deterministic time/request/StableAgentId 순서로 처리해 하나의 death outcome만 확정한다. 승인된 request에만 cooldown/reward 결과를 발행한다.
- 성공 판정 뒤 prey가 다른 원인으로 이미 lethal이면 기존 death cause 우선순위를 따른다. conflicting cause를 새로운 합산 death로 만들지 않는다.
- owner가 동시에 사망/이주/취소됐으면 Pending request를 처리하지 않는다. 이미 commit한 죽음을 사후 취소하면서 Population을 다시 늘리지 않는다.
- 최초 mode는 기존 즉시 포획 조건에 맞춘 좁은 scope다. Windup/AttackWindow/Damage/Stagger는 새 combat contract와 충돌/회피 의미를 검증한 후 추가한다.

## 8. 영양·식사·Rest Smart Objects

### 8.1 초기 nutrition mode

`InstantCaptureReward`에서는 실제 unique death receipt가 확인된 뒤 기존 coordinator가 EnergyPerPredation을 한 번 지급한다. EatCooldown은 공격 금지·정지/표현 단계다. Task가 cooldown을 0으로 강제하거나 먹기 animation 끝에 Energy를 추가 지급하지 않는다.

포만 기반 Hunt 종료는 EnergyRatio 입력으로 선택한다. 늑대의 생존 설정이 현재 기본 opt-in false인 사실을 manifest에 남기고 WolfOnly production 시험은 bEnablePredatorSurvival을 명시적으로 켠 profile로 수행한다. 기존 baseline 비교에서 설정을 몰래 바꾸지 않는다.

### 8.2 Rest/FeedSite

Rest slot은 Activity reservation owner가 SmartObject Claim을 관리한다. request→approach→실제 도착→occupied→deadline rest→release의 공통 흐름이다. 초기 Rest의 에너지 이득은 없고 회복할 stamina도 없는 기본 mode에서는 pose/행동 대기다. physiology 확장이 들어가면 별도 adapter가 소비/회복을 계산한다.

FeedSite slot은 먹이 자원 그 자체가 아니다. 잡은 직후 제자리 cooldown이 기본이며 거점으로 사체를 운반하는 행동은 후속 물리/자원 ownership 설계가 필요하다.

### 8.3 사체 자원 확장

Carcass mode의 계약:

| 항목 | 소유자·처리 |
| --- | --- |
| carcass 생성 | death receipt를 원인/종 정책에 따라 한 번 처리하는 Ecology resource owner |
| 식별 | Carcass ResourceId/WorldEpoch·source death receipt, EntityHandle과 별개 |
| 양/감쇠 | resource owner가 remaining quantity·expiry·수명 기록 |
| 접근 자리 | Smart Object activity slot, resource ID를 참조 |
| 경쟁/예약 | Activity reservation owner, slot generation·lease·release |
| 실제 먹기 | actual position/speed·occupied·이용 구간 기반 consumption request |
| 배분/보상 | carcass ledger의 GrantedAmount를 coordinator가 Energy로 변환 |
| 소멸/streaming | resource quantity/수명과 시각 Actor 수명을 분리하고 slot invalid 정리 |

사체 먹기에서는 InstantCaptureReward를 끄거나 명시적 분할 모형을 새 nutrition version으로 정의한다. 처음에는 둘을 배타 설정해 이중 보상을 막는다. 같은 carcass의 다수 늑대 요청·마지막 잔여량·expiry와 consume 동시 사건을 transaction으로 검증한다.

독립 WolfOnly의 fixture carcass/영양은 test domain 원장으로 처리하고 실제 Ecology predation history에는 올리지 않는다. 실제 death source가 없는 carcass spawn은 별도의 명시적 resource injection event다.

## 9. 몸체·Movement/Avoidance·애니메이션

Wolf body/nav profile은 radius/height·capsule/pill 형상, walk/pursue speed·turn/accel, ground slope/step-height·corridor margin을 제공한다. 현재 사슴과 같은 speed constant를 쓰는 baseline과 새 종별 속력은 구분한다. 새 속력으로 사냥 성공률이 높아진 것을 StateTree 판단 개선으로만 해석하지 않는다.

common grounded movement만 final Transform/Velocity/heading을 쓴다. wolf Activity는 Pursuing/Holding/Resting 등의 speed/goal 의도를 작성한다. 기존 PredatorMovement를 opt-in query에서 제외하지 않은 구성은 검증에서 거부한다.

attack pose의 forward arc가 필요하면 completed logical heading을 resolver가 읽는다. animation montage의 root motion이나 Notify가 직접 prey를 죽이지 않는다. 서버의 attack window가 확정된 contract라면 Notify는 표현용이며 authority의 다른 writer를 만들지 않는다.

발소리는 실제 이동/바닥 조건을 기존 logical noise 서비스로 전달한다. audio 재생 수와 논리 Hearing event 수를 동일하게 묶지 않는다. Dedicated Server에 mesh/audio가 없어도 perception input이 발생해야 한다.

## 10. LOD·Replication·후속 Pack

Pursue/RequestAttack/AwaitResult/CaptureCooldown·유효 carcass claim·Travel는 importance 보호 대상이다. 평온 Patrol/Rest는 brain/candidate 주기를 늘릴 수 있다. 미래 stamina·Energy가 낮은 긴급 상태는 profile에 따라 High로 승격한다. corpse resource/slot expiry·공격 cooldown·생존은 LOD와 독립적으로 진행한다.

LOD를 낮출 때 target cue의 age는 실제 World-time에서 감쇠한다. 평온 interval이 늘어났다고 memory lifetime도 늘리지 않는다. 최대 repath/decision delay·표적 상실 후 추가 chase 시간을 계측한다.

per-connection ReplicationLOD는 기존 Bubble로 처리하고 compact wolf ActivityCode·actual speed·Eating/Pursuing/Alive flags만 Client에 전달한다. hidden target의 cue/ID·hunting utility·route/claim/attack 내부는 기본 DTO에 넣지 않는다. Activity visual revision과 movement sample revision은 따로 유지한다.

Wolf Pack은 초기 완료의 필수 요구가 아니다. 확장할 때 PersistentPackId/멤버십·shared evidence 출처/시간·role/target reservation은 Social owner가 관리한다. 개별 Wolf tree는 Pack intent를 입력으로 읽고 자신의 실행 의도를 제출한다. pack coordination으로 같은 prey 독점 권리를 주더라도 actual capture receipt는 공통 resolver만 확정한다. 물리 Flock/ORCA와 logical Pack을 구분한다.

## 11. WolfOnly 대역 설계와 시나리오

시험 provider는 moving fixture의 scripted motion·source generation·noise·perception visibility를 제공한다. 모든 Brain 입력은 공통 감각 gate를 통과하며 표적의 다음 waypoint/진짜 이동 속도/숨겨진 위치를 brain에 bind하지 않는다.

fixture target→AttackResolver test adapter→FixtureReceipt ledger→명시적인 FixtureNutrition event의 흐름을 사용한다. 이것은 실제 prey HP·Death·Population을 변경하지 않는다. 늑대 자신의 HP/Energy·생존은 기존 coordinator가 계속 관리한다. test ledger의 성공 수와 production PredationHistory는 따로 출력한다.

| 시험 | 조작 | gate |
| --- | --- | --- |
| W-S01 먹잇감 없음 | 단일 늑대·거점/순찰 위치 | 무한 Hunt/invalid target 없이 Patrol/Rest/Search |
| W-S02 visible moving prey | 거리/FOV 안의 fixture | 실제 감각 이후 추격·예산형 retarget·range 검증 |
| W-S03 뒤쪽 소음 | fixture sight 없음·noise만 | uncertainty/last known 조사, 정확한 hidden follow 금지 |
| W-S04 target loss | 차폐/소멸·memory expiry | 조사/timeout→포기·cooldown·대체 행동 |
| W-S05 unreachable/blocked | 끊긴 NavMesh/동적 벽 | bounded retry·blacklist·막힘 feedback·영구 path 대기 없음 |
| W-S06 공격 실패 | range/LOS/cooldown/late result 오류 | 실패 이유, hidden 위치 feedback 없음, 보상 0 |
| W-S07 동시 요청 | 여러 늑대·같은 Fixture target | fixture ledger 하나의 receipt, loser 결과·중복 nutrition 0 |
| W-S08 식사/Rest 정리 | Claim 중 사망·삭제·expiry·Travel | 예약/queue/exposure release·cooldown 단일 writer |
| W-S09 no-player/원거리 | Dedicated Server·평온→위협 전환 | 생존/기억/이주/lease 유지, urgent 승격 |
| W-S10 네트워크 | 여러 Client·거리 변화 | Client Brain/attack 0건, relevance Remove≠Death |
| W-S11 낮은 FPS/soak | hitch·30분 시작안 | clamp·decision/repath delay·누수·회계 |
| W-S12 Carcass 확장 | 적은 양/동시 consume/expiry | 보존식·보상 배타·slot/resource 수명 분리 |

W-S12는 Carcass mode를 실제 개발한 이후의 gate다. 미구현 상태에서는 해당 mode를 Config validation에서 거부하고 필수 기본 mode 완료에 섞지 않는다.

규모 시작안은 늑대 1/8/32/128/512와 fixture 수의 별도 축이다. 실제 통합의 사슴:늑대 비율과 다른 synthetic stress를 비교 보고에서 구분한다. pursuit-heavy 조건에서 synchronous path max·queue wait·LOS/sweep·state instance 비용을 집중 측정한다.

## 12. 단계별 개발

| 단계 | 작업·산출물 | 선행 | 완료 조건 |
| --- | --- | --- | --- |
| W0 독립 구성 | WolfOnly role/config·1마리·fixture provider off | C0 | 사슴 Config 없이 실행·기존 W0 보존 |
| W1 기본 생활 | WolfInput·Utility·AwaitInput/Patrol/Rest tree·profile | C1 | score/전이/deadline, prey 없음 fallback |
| W2 이동 | common path/grounded·patrol terrain scenario | C2 | 경로/충돌/actual speed·하나의 final writer |
| W3 감각·대역 | target domain adapter·fixture·legacy ageing 재사용 | W1 | FOV/LOS/hearing/memory, hidden data 누출 0 |
| W4 추적·포기 | select/prefer/repath·investigate·bounded pursuit | W2, W3 | target switch/invalid/unreachable/timeout·budget |
| W5 공격 계약 | RequestDriven mode·test resolver·result/death adapter | W4, 공통 attack | legacy proximity 중복 제외, current revision·단일 receipt |
| W6 nutrition·예약 | Instant reward adapter·EatCooldown/Rest slots·fixture event ledger | C3, W5 | grant·Energy·cooldown single writer·lease/정리 |
| W7 LOD·네트워크 | importance/Activity DTO·diagnostics | C4, W6 | no-player/multi-client/soak·예산 |
| W8 단독 release | fixture/production 경계·asset/Config manifest·검증 기록 | W7 | 필수 scenario 실제 결과·제한·통합 인계 |
| W9 후속 nutrition | Carcass ledger·slots·실제 consume | W8, resource contract | 기본 reward와 배타·잔량/expiry·동시 consume 검증 |

W5의 실제 prey death 검증은 I2 통합 gate에서 완료한다. 단독 test receipt와 수명 계약은 W5에서 확인하되 production 포식 완료로 표시하지 않는다. W9가 없어도 InstantCaptureReward mode의 단독 release는 가능하며 Carcass 기능은 미지원으로 명시한다.

## 13. 실제 사슴과 합치는 계약

fixture candidate provider를 actual Mass Entity provider로 교체한다. TargetRef domain은 Entity이며 StableAgentId·SpeciesRelation·WorldEpoch를 검증한다. 감각 memory/Navigation/StateTree는 같은 snapshot 인터페이스를 유지한다.

AttackResolver test adapter를 actual resolver에 연결하고 existing lifecycle에 prey lethal 후보를 전달한다. 실제 death receipt 후 Population 감소·PredationHistory·wolf nutrition을 한 번 반영한다. 손실된 target은 다음 input에서 invalid/expired가 되어 chase/attack을 중단한다. deer의 도주/은신처가 감각·LOS·추격/공격 조건에 미치는 효과를 I1~I4에서 검증한다.

통합 초기에는 소수 개체·공격 off로 탐지/이동부터 확인하고 실제 capture를 단계적으로 켠다. fixture source·fixture nutrition·test receipt는 통합 Config에서 금지한다. no fixture 실제 feed/capture ledger가 manifest에 출력돼야 한다.

## 14. 확장성과 PPO 연결

Wolf 입력/출력 schema는 종별 version을 가진다. 미래 늑대 PPO가 들어오면 WolfDecision/TargetIntent interface에 연결하는 backend adapter를 제공한다. 기존 사슴 V1 모델을 포식자용으로 재명명하지 않는다. 감각 후보·execution·attack/nutrition·movement 조건을 공통으로 묶어 모델만 비교할 수 있게 한다.

Stamina/피로·수분·부상·계절·territory·Pack은 capability/profile과 owner를 가진다. physiology는 coordinator/survival, 지속 Pack은 Social, 통행/거점은 World, 개체별 행동 선택은 Wolf backend다. 추가 알고리즘이 Fragment에 큰 동적 배열·per-agent UObject를 만들지 않도록 후보/경로 메모리는 common pool/cache와 budget을 사용한다.

인계는 StateTree/curve·body/nav·attack/nutrition profile, target domain/감각 허용 범위, 읽기/쓰기·phase·취소/deadline·receipt 정리, fixture 시나리오/ledger·실제 UBT/서버/Client/cook 기록을 포함한다. source 조회만으로 실행 통과를 선언하지 않는다.

Source 근거: [기존 늑대 이동](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePredatorProcessor.cpp), [늑대 감각/기억](../../../Source/AdaptiveEcosystem/AI/Social/Senses/EcoPredatorPerception.h), [실제 감각 Processor](../../../Source/AdaptiveEcosystem/AI/Social/Senses/EcoPredatorPerception.cpp), [기존 포획](../../../Source/AdaptiveEcosystem/AI/Policy/EcoPredationProcessor.cpp), [capture cooldown 타입](../../../Source/AdaptiveEcosystem/AI/Policy/EcoBehaviorFragments.h), [생명주기/보상](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp).
