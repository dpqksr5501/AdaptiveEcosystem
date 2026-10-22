# 사슴 독립 개발 상세 계획

작성일: 2026-10-14 / UE 5.8 / 상태: Planned. [마스터 계획](README.md), [공통 런타임](COMMON_RUNTIME_IMPLEMENTATION_PLAN.md)을 전제로 한다. 아래 새 타입/asset/수치는 구현 제안이며 현재 완료 상태가 아니다.

현재 기본 구현은 [마일스톤 기록](IMPLEMENTATION_MILESTONES.md), 사용은 [Editor 빠른 시작](EDITOR_QUICK_START.md), 파일 책임은 [Source 책임](SOURCE_RESPONSIBILITIES.md)을 읽는다. D8 release gate는 실제 단독 시나리오 확인 후 완료로 기록한다.

## 1. 독립 완료의 목표

늑대 Brain 없이 사슴이 먹이 위치를 찾아 이동·섭식·휴식하고, 동족이 있으면 무리를 유지·복귀하며, 시험 위협을 시각/청각으로 감지해 도주·은신·회복해야 한다. 먹이는 실제 Ecology Food에서 차감하고 Energy·기아·사망·이주·Population으로 연결한다. 서버 권위와 Client 표현까지 단독 검증한다.

단독 개체와 사슴 무리 시험을 구분한다. 최소 사슴 한 마리는 무리 중심이나 Shelter가 없어도 invalid target으로 이동하지 않고 정상 생활을 이어간다. 몸체·방향·애니메이션 없이도 논리 검증이 가능하고, 최종 단계에서는 실제 동물 표현을 연결한다.

범위:

- 필수: StateTree Utility, common NavMesh/Avoidance/grounded movement, Graze/Rest/Shelter slot, 실제 식사·생존·이주, Simulation/Replication LOD.
- 후속: 다중 patch 수량 원장, stamina·물·체온·부상, 번식·나이/성별, 풍부한 계절 행동.
- 제외: 별도 Herd 소유자, 자동 Cover 생성, 동물 Actor가 위치/HP를 결정하는 구현, 임의 PPO 수치 수정.

## 2. Config·Trait·파일·에셋

| 항목 | 신규 계획 |
| --- | --- |
| Authority Config | `EC_Deer_StateTree`: 공통 GroundedNavigation/Mass Trait + Deer Trait + 기존 Social + replication |
| Client Config | authority Config의 Client 분기 또는 별도 `EC_Deer_Client` 생성 결과. StateTree/감각/이동/자원 논리 제외 |
| strict 비교 Config | `EC_Deer_StateTreeV1`: `ST_Deer_V1Compare`, 기존 V1 입력·4출력·공통 baseline 실행. production 추가 관측 제외 |
| 종별 Trait | `UEcoDeerBehaviorTrait`: Deer profile·deer decision/candidate/execution 데이터만 추가 |
| 종별 StateTree | `ST_Deer_Utility`, 공통 Mass schema/Task + deer 입력/Condition |
| profile asset | `DA_DeerBehavior_Default`, `DA_DeerLocomotion`, interaction/LOD profile. profile version 기록 |
| 장소 정의 | `SO_DeerGraze`, `SO_DeerRest`, Social adapter를 거친 Shelter definition |
| 레벨 | `L_DeerOnly_Flat`, `L_DeerOnly_Terrain`, `L_DeerOnly_Network` |
| 시험 source | `DA_DeerThreatScenario_*`: 위협 경로·소음/차폐·등장/소멸 시간 |

권장 구현 파일은 `AI/Behavior/Deer/EcoDeerBehaviorTypes.h`, `EcoDeerInputProcessor.*`, `EcoDeerActivityProcessor.*`, `StateTree/EcoDeerTasks.*`다. 공통 이동/service/예약은 종별 폴더에 복사하지 않는다.

SpeciesId는 현재 production의 `Herbivore`를 초기 호환 식별자로 유지한다. 외형 이름 Deer와 SpeciesId 변경을 함께 수행하지 않는다. 실제 `Deer` species registry로 바꾸려면 feeding·wave·predicate·복제/metric의 hardcoded `Herbivore` 사용을 별도 migration contract로 정리한다.

## 3. 입력·개체별 데이터·단일 writer

| 데이터 | 필수 필드 | writer |
| --- | --- | --- |
| `FEcoDeerInputFragment` | EnergyRatio, completed FoodDensity/후보 availability, 개인 위협 source/age/position/confidence, Herd shared 위협 별도, current Travel/slot/move result, 동족 summary | input gather Processor |
| `FEcoDeerDecisionFragment` | preferred activity, selected candidate/ref, request sequence·유효시간, 판단 사유·urgent 여부 | StateTree output Task |
| 기존 `FEcoPolicyOutputFragment` | Forage/Cohesion/FleeDist/Cover Raw Action | 선택된 deer backend 하나 |
| `FEcoDeerExecutionFragment` | 공통 실행 Activity, entered/deadline, calmSince, retained escape direction·candidate failure cooldown | PostSocial Deer Activity Processor |
| 공통 ActivityIntent | 실제 실행 목적지/방향·speed style·이용 intent | 위 Activity Processor만 작성 |
| common MoveResult/Exposure | 실제 이동·이용 구간·revision | common Movement/Interaction |

StateTree의 내부 상태는 engine instance가 소유하고 ExecutionFragment는 **Social/Travel까지 반영한 실행 상태**다. 내부 상태를 별도 enum으로 다시 전이시키지 않는다. 예를 들어 tree가 Forage를 선호해도 유효 Social Shelter가 생기면 실제 실행은 ShelterTravel이며 두 값은 서로 다른 의미로 진단한다.

StateTree Task는 Raw Action + 선호 decision을 발행한다. Social Response는 Raw를 읽어 EffectiveAction과 예약 Request를 제공한다. `UEcoDeerActivityProcessor`는 그 결과를 읽어 실제 생활 의도를 작성한다. final Arbiter는 Travel/예약 우선순위까지 반영한다. StateTree가 직접 final MoveTarget/Transform을 쓰거나 Slot을 Claim하지 않는다.

profile은 입력/생활/locomotion/interaction/LOD로 분리하며 실제 공유 설정 객체는 동일 프로필끼리 공유한다. 개인별 양/시간/기억/이동은 Entity 데이터다.

## 4. StateTree 계층

```text
Root
  AwaitInput
  InactiveOrDead                         [권위 상태 관찰, Hold]
  AuthorityTravelOrWaiting               [Travel을 변경하지 않음]
  UrgentThreat                          [ordered safety branch]
    Flee                                [허용 감각 방향 + 공통 후보]
    ShelterPreference                   [예약은 Social/facade가 수행]
    Recover                             [calm dwell, 유효 위협이면 즉시 중단]
  NormalLife                            [Highest Utility]
    Forage
      SelectFoodLocation
      RequestGrazeSlot
      ApproachGraze
      Graze
    Regroup
      SelectConspecificGoal
      ApproachGroup
    Rest
      SelectRestLocation
      RequestRestSlot
      ApproachRest
      Rest
    Wander
      SelectWanderGoal
      ApproachWanderGoal
```

이 트리의 UrgentThreat는 production 안전 입력을 이용한다. strict V1 asset에는 V1 seven input으로 평가 가능한 선호 선택만 남기고 직접 감각 기억/Alarm/slot availability가 정책 입력으로 들어가지 않게 한다.

유효 Social Shelter Request가 있을 때 NormalLife의 pending 이용 요청은 취소되고 실제 execution은 common Activity에서 Shelter로 override한다. 별도 tree branch를 mirror하려면 읽기 전용 Transition만 사용한다. Social reservation state가 tree에 의해 다시 변경되지 않는다.

## 5. Utility 입력·곡선·전이 규칙

점수와 condition을 분리한다. 죽음/Travel/무효 snapshot/통행 불가능은 Enter Condition이다. 배고픔·위험·생활 선호는 Consideration이다. 다음은 response curve 방향의 시작 설계다.

| 선택 | Consideration 입력·방향 | condition/중단 |
| --- | --- | --- |
| Forage | Energy 낮을수록 높음, 유효 FoodDensity/후보 높을수록 높음 | 실재 후보·재시도 cooldown, 위협/Travel/죽음 중단 |
| Regroup | 허용 동족 중심에서 떨어질수록 높음, 개인 위험/최근 피식에 따라 weight | center 유효·다른 Region 금지, 외로운 한 마리는 skip |
| Rest | Energy 높음·낮은 위험·휴식 필요가 높을수록 높음 | 안전 장소 또는 허용 in-place rest, 배고픔/위협 중단 |
| Wander | Constant curiosity + 탐색 필요 | 다른 욕구가 낮을 때 fallback, 목적지 없음은 Hold/재검색 |
| Flee | 위협 근접·strength/fresh direct evidence | production hard danger는 점수 경쟁보다 먼저 선택 |
| ShelterPreference | 위험 + 허용 Shelter 후보/차폐 quality | 권위 Claim 전에는 occupied라고 가정하지 않음 |

Float 입력은 정규화된 값과 curve로 bind하고 AND=min/OR=max·weight 의미는 엔진 방식을 따른다. mode마다 점수 범위/weight와 경계 입력 출력 표를 asset 검증 기록으로 고정한다. Rest가 고정 점수 때문에 영원히 선택되지 않거나, 모든 점수가 0이라 invalid target으로 진행하는 경우를 시험한다.

초기 튜닝 후보: HungryEnter 0.45 / SatiatedExit 0.80, calm dwell 3s, 평온 재선택 0.25s. 이는 현실 생태 수치·기존 PPO 생성 상수가 아니다. `Enter < Exit`, finite/range·positive deadline을 profile validation에서 검사한다. curve/전이 튜닝은 평가 seed와 분리하고 version/hash를 기록한다.

Minimum dwell은 Rest/Wander/일반 Forage의 불필요한 진동을 줄이는 조건이다. dead/Travel/유효 긴급 위협/slot invalid는 즉시 중단한다. 유효 감각이 사라졌다는 이유만으로 다음 frame 평온으로 돌아가지 않고 calmSince로 안정 구간을 확인한다. 오래된 개인 기억과 전달받은 Herd Alarm은 서로 다른 freshness/confidence 규칙으로 처리한다.

## 6. 단계별 생활 실행

| 단계 | Enter | Tick/완료 | Exit/실패 |
| --- | --- | --- | --- |
| SelectFoodLocation | 공통 후보 cache 조회 요청 | valid 후보/ref를 decision에 기록 | 후보 없음은 Waiting/재검색 deadline. 지역 Food 0은 실패 이유 |
| RequestGrazeSlot | facade에 kind=Graze 예약 요청 | current revision Claimed 대기 | pending cancel/실패 cooldown, 직접 Claim 금지 |
| ApproachGraze | 예약 entry 목적지 선호 발행 | 실제 MoveResult Arrived + lease 유효 | path 실패/위협 시 CancelRequested, exposure 없음 |
| Graze | 실제 도착·속도/slot·위협 조건 검증 | request-use→occupied 이후 실제 이용 구간 제출 | 위협/포만/고갈/Travel/slot invalid에 종료·Release |
| ApproachGroup | 허용 동족 center 목표 후보 | 실제 도착 반경/center revision | center 급변 시 예산형 retarget, Herd 가입 직접 수행 안 함 |
| Rest | 실제 안전 위치·slot/in-place 정책 확인 | profile dwell 후 재선택. 초기 Energy 자동 회복 없음 | 배고픔/위협/slot invalid 즉시 종료 |
| Wander | deterministic candidate 요청 | 도달/timeout 뒤 다음 후보 | 실패 후보를 cooldown하고 재검색 |

Candidate는 지역 내부·walkable/Nav projection·허용 거리·slot 상태·cache age를 포함한다. 가까운 food actor 하나만 전역 순회해 선택하지 않는다. occupied slot 경쟁에서 요청을 정렬하고 loser가 같은 slot에 계속 달려가지 않게 한다.

Rest는 에너지 소비율 변화가 필요하면 공통 survival adapter로 등록한다. 처음부터 HP/Energy를 Task에서 회복시키지 않는다. 실제 metabolic model 확장이 들어가는 조건은 기존 strict 정책 비교와 분리한다.

## 7. 위협·무리·Shelter 연결

### 7.1 감각

기존 `FEcoSensoryStateFragment.MakeReadSnapshot`과 개인/공유 정보 분리를 재사용한다. 시각=직접 확인 위치, 청각=소음 위치/불확실도, 기억=마지막 관찰 위치와 감쇠다. 재수신된 Herd 정보가 원 증거 시각을 새 시각으로 갱신해 영구 기억이 되지 않게 한다.

Flee 방향은 허용된 위협 위치에서 멀어지는 방향과 retained escape direction을 이용한다. 0 길이 방향이나 정확히 같은 위치는 StableAgentId 기반 안전 fallback 방향을 사용한다. 이것은 실제 늑대의 숨겨진 다음 위치를 알아낸 방향이 아니다.

### 7.2 도주 목적지

common candidate service에서 `escape direction cone + 거리·통행 가능성·지역 bounds`로 소수 후보를 만든다. LOS/차폐/route 비용은 budget 안에서 계산하고 valid winner를 Navigation에 요청한다. 막힌 직선으로 계속 벽에 밀어붙이지 않는다. 후보 없음은 안전한 현재 위치 Hold + Failed reason + 빠른 재시도이며 무조건 teleport하지 않는다.

Flee 반경·speed는 profile이다. engine avoidance는 다른 동물·장애물 충돌을 줄이지만 predator로부터의 거리 확보 목적을 대신하지 않는다. dodge/turn rate/급정지 한계도 actual movement 결과로 평가한다.

### 7.3 Herd와 Shelter

Herd 가입/이탈·aggregate·Alarm은 기존 Social이 처리한다. Regroup은 그 snapshot이나 허용 동족 요약을 읽는다. 동족 시각 Actor가 없다는 이유로 logical Herd를 삭제하지 않는다.

Shelter는 기존 Request의 ReservationId/slot/target/validUntil을 참조한다. Path request가 Social 목표를 NavMesh로 project한 결과가 실제 shelter arrival 반경/높이에서 벗어나면 Failed를 반환하며 projection 지점을 Occupied로 확정하지 않는다.

공통 final MoveResult → 검증된 기존 ShelterFeedback(ReservationId/Sequence/Status) adapter → 다음 Social Lifecycle 소비의 흐름을 유지한다. StateTree의 ShelterHold는 예약 상태를 읽는 실행 표시이며 Lease를 직접 늘리지 않는다. 사망·삭제·이주·path 실패·Shelter 소멸은 owner cleanup으로 연결한다.

Travel가 우선인 초기 계약을 유지한다. Travel 중 즉시 도주가 필요해지면 Migration coordinator에 suspend/yield 의도 계약을 별도 추가한다. deer Task가 Region/Travel.State를 직접 바꾸지 않는다.

## 8. NavMesh·몸체·Mass Movement/Avoidance 설정

Deer locomotion profile은 radius/height·walk/run/flee speed·turn limit·acceleration/damping·slope/step-height·corridor/border clearance를 포함한다. 시각 mesh의 pivot/forward axis/발바닥 offset과 논리 위치 기준을 명시한다.

공통 grounded path를 사용하고 terrain 검사는 [공통 6절](COMMON_RUNTIME_IMPLEMENTATION_PLAN.md#6-steeringavoidance단일-최종-이동)을 따른다. actor collision/root motion이 logical 이동을 또 수행하지 않는다. Skeletal mesh animation은 실제 velocity와 ActivityCode를 읽고 속력 변화에 맞춰 blend한다.

Standing avoidance가 Graze/Rest animal을 움직이게 할 수 있으므로 occupied 이용 단계의 허용 drift·최대 실제 속도를 정한다. slot 반경을 벗어나면 exposure를 종료하고 다시 approach/use를 검증한다. Rest/Graze의 wish speed가 0이라고 실제 speed도 0으로 간주하지 않는다.

무리 separation/cohesion은 공통 보조 힘에서 적용한다. alignment/cohesion을 새로 넣으면 기존 PPO 조향과 다른 locomotion profile version으로 기록하고 전체 스택 비교에 포함한다. 사슴마다 별도 AIController/CharacterMovementComponent를 생성하지 않는다.

## 9. Graze 자원·생존·이주

| 처리 | 담당 | 계약 |
| --- | --- | --- |
| 먹이 후보 위치 | World/interaction location provider | 지역 Food 원장과 별도 위치, 아직 없는 food를 생성하지 않음 |
| 이용 자리 | Activity reservation owner + SmartObject adapter | Graze 예약/occupied·release |
| 실제 섭식 자격 | Deer execution + 공통 exposure | actual slot/위치/속도/시간·Alive/Resident·위협 조건 |
| 요청/배분 | 기존 coordinator → Ecology | epoch/step·지역·StableAgentId·Requested/Granted |
| Energy/사망 | 기존 survival/lifecycle | 실제 Granted만 적용·metabolism 한 번·death receipt |
| 자원 고갈/과밀 이주 | 기존 Migration coordinator | decision input에서 요청, Region 실제 도착 commit |

첫 모드는 현재 지역 Food를 이용 장소에서 소비하는 `RegionFoodAtAuthoredLocations`다. 다음 `PatchFoodLedger` 모드는 resource ID·양·재생·지역 합계 계약을 가진 Ecology 확장이다. Smart Object 슬롯에 지역 FoodAmount 복사본을 만들지 않는다.

섭식은 실제 Graze 구간의 exposure에서 RequestedAmount를 계산한다. 최대 intake/time, Energy deficit cap, resource capacity와 grant rule은 공통 프로필·원장 규칙이다. stock baseline의 Forage×Density 지급과 새 구간 섭식은 다른 execution version이므로 비교 조건을 표시한다.

Food 0이면 다음 decision에서 Forage 실패/이주 압력이 드러나야 하며, energy 0에서 task가 잠들어도 기존 survival clock이 사망을 확정한다. Population은 Birth/Death/Migration 합계로 검증한다. Rest나 representation Off가 이 회계를 멈추지 않는다.

## 10. Simulation LOD·Replication LOD

평온한 원거리 사슴은 Brain/후보 검색 간격을 낮추되 이동·Food/Energy·lease는 계속 처리한다. 개인 위협·Herd Alarm·Flee/실제 ShelterTravel·유효 예약·Travel·최근 path 실패는 effective High 보호 대상이다. LOD는 [공통 10절](COMMON_RUNTIME_IMPLEMENTATION_PLAN.md#10-mass-simulation-lod와-처리-예산)을 따른다.

Replication은 기존 per-connection LOD다. compact deer ActivityCode, 실제 speed, 식사/Alive 표현을 최소 DTO로 전달하고 Raw Action·감각 위치·Herd 내부·예약 handle을 Client Brain으로 보내지 않는다. 상태 변경 visual revision과 movement serial은 각각 기존 의미로 유지한다.

DeerOnly 네트워크 맵에서 두 플레이어를 서로 다른 위치에 놓고 같은 사슴의 연결별 관련성·Actor pool·activity 보간을 확인한다. 서버에서 client relevance Remove 때문에 Population이 감소하지 않아야 한다.

## 11. 단독 시험 시나리오

| 시험 | 환경/조작 | 관찰·gate |
| --- | --- | --- |
| D-S01 단일 사슴 | 무위협, 먹이·Rest 위치, 동족 없음 | 생활 순환, invalid group target 0건 |
| D-S02 사슴 무리 | 소수→다수, 분산 스폰 | membership/aggregate 별도, regroup·겹침·candidate 비용 |
| D-S03 고갈 | 실제 Food 공급 중단/감소 | grant·Energy·기아/이주·Population 연결 |
| D-S04 위협 접근 | fixture가 허용 FOV/거리에서 접근 | 실제 감각 이후만 Flee, 응답 지연·위협 age 기록 |
| D-S05 소리/차폐 | 뒤쪽 소음·벽 뒤 위협 | Hearing/Memory uncertainty, 숨겨진 위치 갱신 없음 |
| D-S06 Shelter 경쟁 | slot 수 < 사슴 수 | 중복 점유 0, loser 재검색/회피·대기·lease |
| D-S07 slot/path 실패 | 접근 중 slot 제거·통로 차단 | Failed→release→재선택, occupied 허위 확정 0 |
| D-S08 취소/생명주기 | Graze/Rest/Flee/Travel 중 사망·삭제 | exposure·pending path/Claim 정리·인구 보존 |
| D-S09 원거리/no-player | 모든 화면 밖·Dedicated Server | Food/Energy/이주/예약 유지, brain 최대 지연 |
| D-S10 네트워크 | Listen/전용 서버 + 여러 Client | Client 판단·논리 writer 0건, per-connection relevance |
| D-S11 시간/soak | 낮은 FPS·긴 frame·30분 시작안 | clamp/decision age·exposure·resource drift·memory 누수 |

fixture는 test provider domain으로 유지한다. 시각화 Actor를 비활성화해도 위협/소음 시험은 동작해야 한다. fixture source trace는 Brain이 아니라 감각 service가 읽는다.

규모는 총 사슴 1/32/128/512/2,048을 시작안으로 두고 target hardware/tick에서 가능한 budget을 C0에서 확정한다. 평균 FPS만 보고하지 않고 Brain/감각/Nav/충돌/거래·network p95/p99와 지연·실패율·bytes/entity를 함께 기록한다.

## 12. 개발 단계·산출물·선행 조건

| 단계 | 작업·주요 파일/asset | 선행 | 완료 조건 |
| --- | --- | --- | --- |
| D0 독립 구성 | RoleMask/Config·1마리 spawn·fixture off | C0 | 늑대 Config 없이 authority/client 시작, 기존 경로 보존 |
| D1 입력·Utility | DeerInput, Mass Evaluator·curve·deer tree AwaitInput/Normal | C1 | boundary input/score·deadline·state 진동 확인 |
| D2 배회·이동 | Wander Task·common path/grounded feedback, flat/terrain 맵 | C2 | 도달/취소/경사/금지영역·actual speed, writer 하나 |
| D3 섭식·휴식 | Graze/Rest 장소·facade Task·exposure·coordinator adapter | C3 | 위치·occupied·시간·grant·Energy가 일치, 중복 지급 0 |
| D4 무리 연결 | existing Social snapshot·Regroup | D2 | 단독 fallback와 무리 aggregate·regroup, Herd 중복 상태 없음 |
| D5 위협·도주 | scripted source + 개인/공유 감각·Escape 후보/회복 | D2, D4 | 시각/청각/기억·calm dwell, hidden target 누출 없음 |
| D6 Shelter·이주 | Social Request/Feedback adapter·중단 정리 | D3, D5 | lease/도착/실패/Travel 우선·Region 회계 |
| D7 LOD·네트워크 | Activity DTO·importance protection·계측 | C4, D6 | 원거리/no-player·다중 Client/soak와 예산 |
| D8 단독 release | Config/asset manifest·수동 검증·strict V1 asset | D7 | 모든 필수 scenario 결과, 제한·재현·PPO 비교 연결 인계 |

D1의 의도 출력은 mock feedback으로 확인할 수 있지만 D2/D3의 실제 실행 검증을 대신하지 않는다. D8의 strict asset에는 production 추가 감각·속도·식사 규칙을 섞지 않는다. 기존 비교 A는 같은 입력·생활 실행·늑대 W0 또는 동일 위협 fixture로 모든 backend를 독립 실행한다.

## 13. 합칠 때의 연결과 확장

통합에서 threat fixture provider를 실제 Wolf candidate provider로 교체한다. deer Brain/Activity/Nav/예약 contract는 바뀌지 않는다. predator relation·감각/소음 mapping을 registry로 정의하고 actor tag 문자열만으로 종 관계를 고정하지 않는다. 실제 사슴 death는 Wolf AttackResolver→기존 lifecycle receipt로 연결한다.

확장 capability는 Energy 외의 Stamina/Water/Thermal, juvenile/나이·계절/번식, 새로운 herbivore species다. 추가 관측은 production profile/schema version으로 제공하고 strict V1 동결을 유지한다. stamina recovery를 Rest Task가 쓰지 않고 공통 physiology processor/adapter가 쓴다. 새 종의 데이터 때문에 기존 Entity의 hot Fragment가 계속 커지지 않도록 분리한다.

최종 deer 인계에는 body/navigation profile, StateTree·curve/interaction asset, required Fragment·dependencies, 모든 읽기/쓰기·Signal/취소·exposure 계약, fixture/production manifest, UBT·서버/Client/cook 실제 기록을 포함한다. 이번 문서는 그 구현이나 실행 통과 보고가 아니다.

Source 근거: [기존 정책](../../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyProcessor.cpp), [기존 Steering](../../../Source/AdaptiveEcosystem/AI/Policy/EcoSteeringProcessor.cpp), [Social 타입](../../../Source/AdaptiveEcosystem/AI/Social/EcoSocialFragments.h), [감각 타입](../../../Source/AdaptiveEcosystem/AI/Social/Senses/EcoSensoryTypes.h), [생존 타입](../../../Source/AdaptiveEcosystem/Core/EcoSurvivalTypes.h), [섭식/생명주기](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp).
