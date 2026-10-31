# 사슴·늑대 공통 Mass 런타임 구현 상세 계획

작성일: 2026-10-14 / UE 5.8 / 상태: Planned / 상위 문서: [마스터 계획](README.md).

구현 후 안내: 이 문서는 상세 목표 설계다. 현재 작성한 기본 M1~M5 코드·에셋, 실제 검사 결과와 축소/후속 범위는 [구현 마일스톤](IMPLEMENTATION_MILESTONES.md)과 [Source 책임](SOURCE_RESPONSIBILITIES.md)을 따른다.

현재 프로젝트 Source와 `C:/Program Files/Epic Games/UE_5.8/Engine`의 설치된 Source를 대조했다. Source를 확인한 사실과 아래 새 타입·프로필·순서 제안을 구분한다. 엔진 수정은 기본 범위가 아니며 프로젝트 단일 런타임 모듈 안에서 연결한다.

로컬 `Engine/Build/Build.version`은 **5.8.3 / Changelist 58210709 / ++UE5+Release-5.8**이다. 공식 문서는 5.8 버전이며 다른 patch/build에서는 아래 구현 사실을 다시 대조한다.

## 1. 엔진에서 확인한 사실과 설계 영향

| Source 확인 | 영향 |
| --- | --- |
| `UMassStateTreeSchema`는 Mass Task/Evaluator/Condition과 common Consideration을 허용 | common Float/Enum/Constant Consideration에 값 입력을 bind. 특별한 노드가 필요하면 schema 허용·dependency를 명시 |
| schema의 external data는 WorldSubsystem·Entity/Shared/ConstShared Fragment | 임의 Actor/AIController를 external data로 직접 주입하지 않고 snapshot/서비스로 연결 |
| StateTree Trait는 asset을 ConstShared, instance handle을 Entity Fragment에 구성 | asset/설정 공유, 개체별 실행 상태 분리. 개체별 UStateTree UObject 생성 금지 |
| StateTree activation/destructor는 GT에서 instance를 생성/해제, tick에는 병렬 chunk 분기 존재 | 엔진 지원 병렬 경로와 프로젝트 Task thread safety를 별도로 확인. 값 전용 Task부터 병렬화 |
| StateTree Processor는 Behavior 그룹, SyncWorldToMass 뒤·Tasks 앞 | 종별 Brain의 dependency는 이 그룹과 공통 snapshot 준비 순서에 맞춤 |
| 기본 NavMesh Path Follow Task는 `NavData->FindPath` 동기 호출, corridor/short path 생성 | production은 공통 경로 서비스의 예산을 거침. Task 수만큼 무제한 동기 path 금지 |
| NavMesh PathFollow Processor는 Tasks 그룹, 실제 위치를 읽어 MoveTarget 진행; LOD variable tick TODO가 남음 | 초기 엔진 variable movement tick은 끄고 실제 위치·도착 검증 별도. stock Off 경로 진행을 믿지 않음 |
| Steering → Avoidance → ApplyForce → Movement 흐름 | 힘을 Force에 쓰고 ApplyForce가 DesiredVelocity 갱신 후 Force를 0으로 초기화 |
| 기본 ApplyMovement는 DesiredVelocity를 Velocity에 복사하고 위치를 더함. sweep/지면 검사는 없음 | production 최종 writer에 충돌·지면·지역 검사를 포함 |
| ApplyForce/ApplyMovement의 delta는 최대 0.1초, Custom/Off Tag는 기본 적분 제외 | production Custom writer를 배타 설정하고 시간 clamp 의미를 문서화 |
| Simulation Trait의 tag/variable tick 옵션은 초기 Off tag를 만들 수 있음 | 초기 `bSetLODTags=false`, variable tick=false. Off를 Low로 보정하고 상세 이동 정지 금지 |
| SmartObject User Trait는 user Fragment를 추가 | Trait 추가만으로 공통 예약·Food 거래·해제가 완성되지 않음 |

엔진 근거 파일은 15절에 기록한다. 공식 API 명칭과 프로젝트 신규 이름은 아래 표에서 구분한다.

## 2. 모듈·파일·Config 구성

### 2.1 빌드 입력

기존 StateTreeModule/MassCore/MassEntity/MassCommon/MassMovement/MassNavigation/MassLOD/MassReplication/NavigationSystem 의존성을 재사용한다. 새 header/API 사용 범위에 따라 `MassAIBehavior`, `MassNavMeshNavigation`, `MassSmartObjects`, `SmartObjectsModule`, `NavCorridor`를 추가한다. 공개 header에 노출되는 타입은 Public, 구현 내부 타입은 Private 의존성으로 정하며 실제 module Build.cs 이름을 구현 시 검증한다. AIController 기반 GameplayStateTree와 Mass StateTree를 혼동하지 않는다.

StateTree/MassGameplay/MassAI 플러그인 활성화를 유지하고 의존 플러그인의 availability/cook을 확인한다. experimental 표시는 서버/cook·스케일 검증을 생략할 근거가 아니다.

### 2.2 프로젝트 파일 제안

| 파일군 | 책임 |
| --- | --- |
| `Core/EcoBehaviorRuntimeContracts.h` | target/request/result ID·version·이유 enum. 모델 가중치나 species decision 포함 안 함 |
| `AI/Behavior/EcoBehaviorTraits.*`, `EcoBehaviorFragments.h` | 공통 authority 구성과 backend·snapshot·실행 metadata |
| `AI/Behavior/StateTree/` | 공통 Task/Evaluator/Condition, species profile, scheduler/signal adapter |
| `Mass/Navigation/EcoNavigationService.*` | 예산형 path 처리·corridor·cancel·short path refill |
| `Mass/Navigation/EcoMoveIntentProcessor.*` | 최종 요청 선택·revision 관리 |
| `Mass/Movement/EcoGroundedMovementProcessor.*` | 단일 실제 위치/속도/방향 갱신과 feedback |
| `Creature/Runtime/Interaction/` | slot reservation facade, 이용 exposure·섭식/공격 요청 변환 |
| `Mass/LOD/EcoSimulationImportanceProcessor.*` | 거리 LOD 보정·긴급 중요도·안전 기본값 |
| `Debug/SpeciesAI/` | test-provider·fixture·writer/계약 진단·측정 |

파일명과 새 타입명은 제안이다. 기존 타입의 확장으로 해결되면 새 복사본을 만들지 않는다. `Evolution/` 또는 legacy contract에 의존하지 않는다.

### 2.3 EntityConfig 조합

공통 base Config는 종별 필수 데이터와 표현 profile을 자식으로 분리한다. Authority와 Client에서 template 생성 결과를 각각 검사한다.

| Trait/구성 | 실제 엔진 타입 또는 신규 제안 | 구성 내용 |
| --- | --- | --- |
| 권위 공통 | 기존 Network Trait 기반 새 opt-in `UEcoSpeciesRuntimeTrait` | Identity/Region/Vitals/Travel/feeding/death/lifetime·기존 복제. 기존 CustomMovement와 PPO 구성의 무조건 주입은 분기 |
| 종·몸체 | 신규 species role/profile Trait | Deer/Wolf 고정 구분, radius/height·profile validation |
| Mass Movement | 엔진 `UMassMovementTrait` | Velocity/Force/DesiredMovement·ConstShared MovementParams |
| Mass Steering | 엔진 `UMassSteeringTrait` | MoveTarget/Steering/Standing/Ghost·steering parameters |
| Mass NavMesh | 엔진 `UMassNavMeshNavigationTrait` | radius/height·CachedPath/ShortPath/Boundary |
| Mass Avoidance | 엔진 `UMassObstacleAvoidanceTrait` | NavigationEdges·Moving/Standing AvoidanceParameters |
| obstacle 등록 | 엔진 `UMassNavigationObstacleTrait` | grid cell location. collider shape는 필요한 engine/provider 타입을 함께 확인 |
| Mass StateTree | 엔진 `UMassStateTreeTrait` | 선택된 species tree + instance. PPO strict Config에서는 이 Trait가 정책을 동시 작성하지 않음 |
| Smart Object 이용 | 엔진 `UMassSmartObjectUserTrait` + 신규 adapter Trait | UserTags + project 예약/이용 결과. 태그만으로 논리 claim 권한 주지 않음 |
| Simulation LOD | 엔진 거리 collector + `UMassSimulationLODTrait` | 거리 기반 입력·LOD. 초기 variable ticking/tag 설정은 10절 |
| 복제 | 기존 `UEcoMassNetworkTrait`/Replicator | Client Bubble·per-connection LOD·완료 snapshot |

Deer StateTree Config에서 기존 `UEcoHerbivoreTrait` 전체를 호출하면 PPO runtime/직접 writer 조건까지 들어온다. 공통 identity/species/observation 데이터를 분리해 필요한 조각만 재사용하고 backend/movement 분기를 명시한다. Wolf도 기존 Predator Trait의 capture state를 재사용하되 기존 PredatorMovement query와 신규 writer가 동시에 match하지 않게 한다.

Authority 신규 Entity에는 생성 시 고정 `FEcoGroundedNavigationTag`(제안)와 `FMassCustomMovementTag`를 붙인다. `UMassApplyMovementProcessor`가 제외하며 기존 사슴/늑대 직접 writer에는 신규 tag의 None requirement를 추가한다. 공통 Custom final writer는 신규 tag·Authority/Alive와 필요한 Fragment를 요구하고 ClientProxy/PendingDeath를 제외한다. CodeDriven flag는 engine steering 입력 의미에 맞게 검증하되 default ApplyMovement는 Custom tag로 항상 제외한다.

행동 backend도 고정 `FEcoStateTreeBehaviorTag`(제안)로 구분한다. 기존 `UEcoPolicyProcessor`의 query는 이 tag를 제외하고 새 StateTree만 해당 개체의 Raw/Decision을 쓴다. strict V1 asset이 기존 이동을 사용할 때도 backend tag는 필요하다. 이동 tag와 Brain tag를 하나로 묶어 PPO+새 이동 또는 StateTree+기존 이동 비교를 불가능하게 만들지 않는다.

Client는 logical StateTree/force/path/desired movement/Vitals/Travel/예약/감각 Fragment를 갖지 않는다. 수신 Identity/Region/Transform·ClientPresentation·필요 DTO만 가진다. 최종 engine template를 검사하며 editor InspectingData 결과와 runtime netmode 분기를 구분한다.

`EnabledRoles`에 따른 Config 등록 검증, StateTree ReadyToRun, external required Fragment, 몸체/nav agent support, backend output writer·최종 이동 writer, Box 혼용을 스폰 전에 검사한다. 오류 구성은 log만 남기고 계속 실행하지 않는다.

## 3. 데이터 소유권·요청 계약

| 값 | 소유자 | downstream |
| --- | --- | --- |
| 환경·지형·통행 정보 | World service | 감각/Nav/생태 |
| 지역 Food·피식·인구 회계 | Ecology service | 관측·거래·요약 |
| HP/Energy/Alive/Death·Region/Travel | 기존 Mass Lifecycle/Migration 계약 | Brain은 읽음 |
| 감각 기억 | 감각 Processor | Brain/Social 입력 snapshot |
| StateTree active state | 엔진 instance runtime | 진단/Activity 출력은 파생값 |
| Raw Action | 선택된 Behavior backend | Social |
| Herd/Alarm/Shelter 예약·Request | 기존 Social | Arbiter·예약 adapter |
| 행동 선호·목표 후보 | 종별 StateTree output Task | PostSocial Activity |
| 생활 목적지·이용 자격 | 종별 PostSocial Activity Processor | Arbiter/Interaction |
| final 이동 요청 | 공통 Arbiter | Navigation |
| CachedPath/ShortPath·MoveTarget | Navigation/path-follow | Steering |
| Force·DesiredMovement | Steering/Avoidance/ApplyForce 정해진 순서 | final writer |
| 실제 Transform/Velocity·heading·완료 이동 결과 | 공통 final writer | 도착/감각/거래/복제 |
| 비Shelter slot 예약 | Activity reservation owner | SmartObject adapter/이용 Task |
| 복제 DTO/Client 보간 | 기존 Network/Representation | Client 화면 |

### 3.1 제안 Fragment

| 타입 | 필드/의미 |
| --- | --- |
| `FEcoBehaviorInputFragment` | snapshot sequence/time, EnergyRatio, 감각 출처/age/confidence·허용 위치, 후보 summary, validity. strict V1은 기존 관측을 별도로 bind |
| `FEcoBehaviorRuntimeFragment` | tree/profile/backend version, last decision reason/time, next deadline. active state의 독립 사본을 authority로 쓰지 않음 |
| 종별 Decision Fragment | StateTree가 발행한 선호·허용 목표 후보·판단 사유/revision. deer/wolf 각각 구체 타입을 사용 |
| `FEcoActivityIntentFragment` | mode·target ref·위치/방향·speed style·speed limit·validUntil·request sequence·이용 kind |
| `FEcoMoveRequestFragment` | WorldEpoch/StableAgentId/RequestId/revision, source, target/nav revision, radius/deadline·priority·예약 참조 |
| `FEcoNavigationRuntimeFragment` | Pending/Ready/Following/Blocked/Failed/Cancelled, active revision·retryTime·last progress·partial path flag |
| `FEcoMoveResultFragment` | revision·sample time, 실제 pose/velocity, Arrived/Moving/Blocked/Failed/Yielded, reason |
| `FEcoActivitySlotFragment` | 논리 ReservationId·kind·owner·pending/claimed/occupied·lease·slot stable key. ClaimHandle은 별도 service runtime mapping |
| `FEcoInteractionExposureFragment` | 실제 이용 가능 구간·position/slot revision·누적 미처리 시간·마지막 소비 token |
| `FEcoBehaviorScheduleFragment` | due time·last input/decision revision, effective tier·urgent flag·dedupe reason·phase |

고정 종별 profile/curve/한계값은 ConstShared 또는 공유 Data Asset이다. 경로/감각/상태/출력/예약은 개체별 데이터다. 필요 없는 species capability Fragment는 붙이지 않는다. 자주 바뀌는 Activity를 Tag로 표현하지 않는다.

### 3.2 참조·취소·만료

`FEcoTargetRef`(제안)는 `Domain=Entity/Fixture/InteractionLocation/Carcass`와 stable key + WorldEpoch를 가진다. Entity domain의 key는 StableAgentId, Fixture는 FixtureId, 사체/장소는 별도 resource/location ID다. 서로 다른 ID를 같은 int64 값으로 추정해 조회하지 않는다.

모든 결과는 WorldEpoch·owner 생존·현재 request/profile revision·target existence를 검증한다. invalid이면 버리고 reason/counter를 남긴다. path·slot·attack·영양 요청은 idempotent ID로 처리하며 취소돼도 이미 완료한 resource 거래를 두 번 되돌리지 않는다.

cancel 사유는 새 의도, 위협 override, Travel, target lost, path invalid, timeout, owner death/delete, world shutdown이다. 모든 Task ExitState는 자신의 활성 revision에 대해서만 CancelRequested를 제출한다. 하위 service가 cleanup을 수행하고 Task가 lease/경로/Region을 직접 삭제하지 않는다. ExitState가 호출되지 않는 삭제/월드 종료에서도 owner service가 정리한다.

## 4. StateTree·Utility 구현

### 4.1 Asset 구조와 입력

`ST_Deer_Utility`와 `ST_Wolf_Utility`를 별도 asset으로 만든다. Mass Behavior schema를 사용하며 공통 Task/Evaluator를 재사용한다. `ST_Deer_V1Compare`는 strict 7→4 정책용 별도 asset이다. production tree에서 추가 입력을 켠 상태를 strict PPO 비교라고 부르지 않는다.

입력 준비 Processor는 감각·자원·개체 상태를 값 snapshot으로 만든다. `FEcoReadBehaviorInputEvaluator`는 자기 Entity의 snapshot을 instance data의 bind 가능한 숫자/enum으로 옮긴다. 후보 검색·LOS·NavSystem/SmartObject query를 Evaluator에서 수행하지 않는다. stale input은 valid=false와 reason을 출력하고 안전한 Hold/재검색 의도로 처리한다.

Task는 `FMassStateTreeTaskBase`, Evaluator/Condition은 해당 Mass base를 사용한다. 각 노드는 LinkExternalData뿐 아니라 `GetDependencies`에 ReadOnly/ReadWrite·subsystem 사용을 선언한다. stock schema가 common Consideration을 허용하므로 float response curve binding을 기본으로 한다. 공통이 아닌 새 Consideration이 필요한 경우 schema 확장·dependency 검토를 먼저 하고 무작정 노드를 추가하지 않는다.

### 4.2 선택과 전이

안전·권위 중단 가지는 ordered selection, 평온한 생활 가지는 Highest Utility를 기본으로 한다. Utility 값은 0~1 Consideration의 곡선, AND=min/OR=max, Weight 조합이며 최종 Weight 적용 점수는 1을 넘을 수 있다. 점수를 V1 action 값과 혼동하지 않는다. [공식 Utility 선택](https://dev.epicgames.com/documentation/en-us/unreal-engine/state-tree-selectors-overview)

Utility는 **selection 시점**에 평가된다. 곡선이 변한다고 지속 상태가 자동으로 재선택되는 것으로 가정하지 않는다. scheduler가 periodic/important Signal을 보내고 Task/transition이 재평가 여부를 결정한다. switching margin·minimum dwell·cooldown은 값 전용 helper가 계산해 `CanReselect` 입력으로 bind한다. hard interrupt는 그 제한을 우회하는 이유를 명시한다.

각 Task는 Enter=요청 발행, Tick=현재 revision의 결과만 확인, Exit=취소 요청으로 구성한다. 대기 Task는 다음 deadline에 wake를 예약하며 매 frame polling을 기본으로 사용하지 않는다. 하나의 상태에 여러 Task를 붙이면 첫 완료의 transition 영향이 있으므로 이동과 이용을 별도 하위 상태로 나누고 장기 관찰 Task가 의도치 않게 완료를 일으키지 않게 한다.

여기서 Task의 요청/취소 발행은 자기 Entity의 command Fragment에 값을 기록하는 의미다. Claim/Release·공격/영양·실제 Nav query 같은 UObject service 호출은 GT의 request consumer가 수행한다. 종별 문서의 "facade에 요청"도 이 mailbox 경로를 뜻한다. Task가 external Subsystem을 bind했더라도 thread-safe가 확인되지 않은 API를 worker에서 직접 호출하지 않는다.

### 4.3 Signal·scheduler

임의 FName Signal을 보내면 기본 StateTree가 자동으로 구독한다고 가정하지 않는다. 초기 adapter는 값/revision을 Fragment에 쓰고 엔진에서 구독하는 `NewStateTreeTaskRequired`를 wake로 사용한다. custom signal 이름이 필요하면 실제 StateTree processor 등록·구독 경로를 검증해 추가한다. 여러 동적 ST Processor가 같은 Entity를 tick하지 않게 한다.

`StateTreeActivate`, path done, interaction done, delayed transition 등 엔진 Signal과 project due wake를 구분한다. activation budget 탓에 tree가 늦게 시작하는 동안 의도는 Hold이며 초기 activation 지연을 계측한다. 대규모 spawn 뒤 무조건 전 Entity에 같은 frame wake를 보내지 않는다.

deadline 등록은 handle/revision 기반으로 취소하며 signal payload는 없으므로 stale wake가 오더라도 current revision을 확인한다. 각 Entity에 원인별 bit를 모아 한 번 깨우고 중요한 위협/사망/예약 실패는 일반 budget보다 우선한다. strict 비교에서는 모든 정책 backend에 동일한 decision 기회를 준다.

## 5. NavMesh 요청·경로·실패 처리

### 5.1 production 연결 방식

StateTree의 `FEcoRequestMoveTask`는 종별 Decision의 목표 선호/revision만 쓴다. PostSocial 종별 Activity Processor가 보정·생활 조건을 반영해 ActivityIntent를 쓰고, `UEcoMoveIntentProcessor`가 Travel/예약 우선순위와 유효시간을 검사해 final request를 만든다. `UEcoNavigationRequestProcessor`가 GT에서 budget 내 요청만 처리하고 engine CachedPath/ShortPath를 채운다.

엔진 `FMassNavMeshPathFollowTask`는 작은 smoke test의 기능 기준으로 사용한다. production은 그 요청/corridor/short-path 기능을 프로젝트 service로 연결해 재사용한다. 기본 Task와 service를 동시에 실행하지 않는다. 기존 B2 PPO에도 StateTree 없이 동일 service를 제공할 수 있다.

### 5.2 처리 순서

1. 현재 owner·epoch·revision·deadline, 몸체 radius/height와 지원 NavData를 검증한다.
2. 목적지 ProjectPointToNavigation은 검색 extent를 제한한다. 다른 층/물/금지영역으로 큰 거리 snap하면 거부한다. projection 위치와 원 목적지의 차이를 기록한다.
3. `FPathFindingQuery`를 구성하고 지원 agent/filter로 path를 계산한다. 초기에는 budget형 동기 처리다. 이것은 비동기 pathfinding 완료 구현이 아니다.
4. 실패/partial/single-point/no-corridor를 구분한다. 이미 실제 목적지 반경에 있는 경우 도착 검사를 하고, 멀리 있는 단일 point 결과를 도착으로 간주하지 않는다.
5. path points → corridor → short path 요청. profile의 corridor width/border offset과 몸체 clearance를 적용한다. Shared path/corridor를 여러 개체가 동시에 수정하지 않는다.
6. MoveTarget speed/style은 종별 의도와 공통 movement max를 clamp하고 Move action을 시작한다. 속도 variation은 Entity.Index 대신 StableAgentId 기반 값을 쓰는 project adapter로 재현한다.
7. stock `UMassNavMeshPathFollowProcessor`가 위치를 읽어 short path progress/MoveTarget을 갱신하고 `UMassNavMeshNavigationBoundaryProcessor`가 avoidance edges를 생성한다.
8. partial short path의 refill은 cached corridor 안의 local 작업이다. 필요 시 path done signal을 받아 다음 Behavior/서비스 패스에서 보충한다. 장거리 full path 재탐색과 다른 budget/counter로 기록한다.
9. 최종 Arrived는 실제 완료 위치·최종 목적지 반경·요청 validity를 확인한 project feedback이다. 엔진 end-of-short-path signal만으로 Shelter Occupied/Region 이동/공격 도달을 확정하지 않는다.

### 5.3 목표가 움직일 때

늑대 추적 목표는 최신 **허용 감각 위치**가 재탐색 거리/시간 threshold를 넘을 때만 새 request를 만든다. 매 perception scan이나 매 frame 새 path를 만들지 않는다. 보이는 표적의 heading 예측은 허용 snapshot으로 제한하며 감각 밖 live 위치를 읽지 않는다.

경로 invalid/streaming/nav tile 변화·막힘·취소 시 이전 path의 active revision을 무효화한다. 새 경로 Pending 동안 이전 경로를 계속 쓸 수 있는 경우는 같은 target과 안전한 유효구간일 때뿐이다. 다른 target/deadline 만료 경로는 Hold/Failed를 반환한다.

### 5.4 예산과 실패

GT queue는 priority+waiting age로 정렬하고 max queries/frame + soft time budget을 쓴다. 한 동기 path query를 중간에 중단할 수는 없으므로 개별 max/p99도 측정한다. 같은 요청은 dedupe, 삭제/취소 queue entry는 폐기, 무한 retry는 금지한다. 허용 실패 횟수 뒤 해당 후보를 cooldown하고 다른 후보/행동으로 돌아간다.

향후 engine async API로 바꾸면 callback에서 Fragment view를 보관하지 않는다. 값 결과를 staging buffer에 두고 GT safe commit에서 owner/epoch/revision/nav version을 검사한다. 비동기 도입은 동일 service interface 뒤에서 수행해 종별 tree를 수정하지 않는다.

## 6. Steering·Avoidance·단일 최종 이동

### 6.1 힘 구성

엔진 steering이 MoveTarget 추종·정지 힘을 만들고, 프로젝트의 동족 separation/alignment/cohesion 같은 추가 의도는 지정된 보조 힘 Processor에서 합성한다. Herd membership을 변경하지 않는다. 같은 separation을 project steering과 engine avoidance에서 중복으로 강하게 적용하지 않게 profile에서 분담한다.

Avoidance는 엔진 grid에 등록된 주변 collider와 NavigationEdges를 사용한다. 실제 animal body radius/height·capsule/pill 선택·body forward axis를 profile에 명시하고 큰 늑대 mesh와 작은 사슴 몸체의 clearance를 시각 크기만으로 추정하지 않는다. stationary grazer/resting animal도 obstacle로 등록해 통과를 줄인다.

Mass Avoidance는 prey 안전거리나 공격 사거리 규칙이 아니다. 같은 회피 radius 설정으로 predator가 prey에 영원히 접근하지 못하면 공격 허용 거리와 실제 body clearance를 함께 조정한다. arbitrary collider 해제·teleport로 포획을 강제하지 않는다.

엔진 steering의 일부 standing variation은 Entity.Index 또는 전역 난수를 사용한다. 재현 비교 profile에서는 speed/standing threshold/cooldown variance를 0으로 두는 시작안을 사용하거나 project deterministic adapter로 치환한다. engine 난수 variation을 남긴 실행은 설정과 한계를 manifest에 남기고 bit-exact 재현을 주장하지 않는다. Brain의 난수 stream은 이 엔진 전역 stream과 분리한다.

### 6.2 final writer 결정

production `UEcoGroundedMovementProcessor`는 `FMassCustomMovementTag`를 가진 opt-in Entity에 대해 유일한 final writer다. `UMassApplyForceProcessor`가 만든 DesiredVelocity를 읽고 최종 Velocity/Transform/heading을 쓴다. engine 기본 ApplyMovement와 기존 EcoSteering/PredatorMovement는 해당 Entity에 실행되지 않는다.

1. Authority/Alive·current intent/nav revision을 검사하고 무효/Dead는 정지한다.
2. 사용할 delta는 초기 `min(frame dt, 0.1s)`로 ApplyForce와 일치시킨다. 긴 frame의 남은 이동 시간을 역사 지형에 재적분하지 않으며 clamp 손실 시간을 계측한다. Ecology의 생존 시간은 별도 completed clock대로 진행한다.
3. 최종 speed/turn limit과 intent override를 적용한다. 급한 도주와 공격 정지도 이 입력 단계에서 결정한다.
4. 속도 × delta의 proposed step을 계산하고, 빠른 이동은 몸체 반경/최대 이동길이 기준 제한된 collision subsegment로 나눈다. 한 총 step의 시간을 두 번 적분하지 않는다.
5. World collision sweep, 필요시 bounded slide, ground probe/slope·step-height·walkable normal, Region/물/금지영역을 검사한다. 검증된 최종 위치 하나를 선택한다.
6. 실제 delta 위치에서 최종 Velocity를 산출한다. 차단 시 허용된 정지/slide 결과를 기록하고 path progress·noise·animation이 희망 속도를 실제 속도로 오인하지 않게 한다.
7. heading/rotation은 이 final writer가 갱신한다. 별도 orientation Trait를 추가하려면 rotation writer를 그쪽으로 이전하는 명시적 계약이 필요하다.
8. 위치·속도와 MoveResult를 commit한다. 다른 계층은 결과를 읽고 도착·이용·자원 거래를 판단한다.

ground probe가 실패하면 원 위치/안전 정지를 유지하고 재경로·실패 feedback을 반환한다. NavMesh에 있다는 이유로 절벽을 건너뛰지 않는다. dynamic obstacle을 NavMesh가 아직 반영하지 않아도 sweep으로 차단한다. 지역 밖 이동은 유효 Travel 요청에만 허용하고 Region commit은 Migration 소유다.

engine 기본 movement의 0.1초 clamp와 새 production 실제 제약은 Python 일정속력 경로와 다르다. 전체 sim-to-sim 파리티로 주장하지 않는다. fixed-step 이동 확장은 Force 갱신과 integration 시간을 함께 바꾸는 별도 movement version으로 다룬다.

## 7. Activity·Smart Object·자원 거래

### 7.1 장소와 양을 분리

FoodPatchLocation/RestSite/Shelter/Carcass는 후보 위치·이용 slot을 제공한다. 지역 FoodAmount는 Ecology 원장만 소유한다. initial graze slot은 지역 Food를 소비하는 **위치**이며 독립 food 잔고를 가지지 않는다. 다중 patch별 잔고는 Ecology의 child ledger로 확장한 뒤 지역 합계와 보존식으로 연결한다.

`UEcoInteractionFacade`(제안)는 kind별 요청을 권위 owner에게 전달하는 서비스다. Shelter 예약은 `UEcoShelterSubsystem`, Graze/Rest/Carcass slot은 신규 Activity reservation owner가 소유한다. 동일 slot을 둘이 관리하지 않는다. Brain/Task/Navigation은 facade에 request/cancel만 제출한다.

### 7.2 예약 연결

| 단계 | 처리 |
| --- | --- |
| Search | area/species/activity tags로 검색, 값 candidate·free slot·entry 위치 반환 |
| Request | owner가 ReservationId와 pending 요청을 발급. WorldEpoch·owner·slot generation 검증 |
| Claim | 직렬 GT에서 engine Claim. 성공 후 논리 Claimed commit, 실패/중간 오류는 mapping rollback |
| Move | 유효 예약이 제공한 접근 위치로 common Navigation request 생성 |
| Use | 실제 도착·slot 유효·활동 조건을 owner가 확인해 Occupied 및 engine Use 연결 |
| 이용 | completed movement/Activity의 실제 이용 가능 시간만 exposure에 기록 |
| Release | 완료/중단/사망/삭제/이주/timeout/slot invalid/월드 종료에서 멱등 해제 |

ClaimHandle은 runtime service mapping에만 보관하고 영속 ID/복제값으로 쓰지 않는다. slot key는 authored location ID+slot index+generation이며 streaming 재등록을 과거 slot과 혼동하지 않는다. 소멸 callback은 정리 요청을 큐에 넣고 owner가 transaction 순서대로 처리한다.

기본 Mass Claim/Use Task가 Social/Activity owner를 우회할 수 있으므로 production에서는 project facade Task를 사용한다. engine UserFragment를 추가했어도 별도의 기본 Task가 자동 Claim을 수행하도록 설정하지 않는다. 기존 Shelter Request/Feedback은 adapter로 재사용하고 일반 Rest slot에 Shelter의 State enum을 억지로 넣지 않는다.

### 7.3 섭식 시간과 결과 적용

이용 exposure는 [구간 시작/끝, region/slot/resource revision, 실제 위치·속도 조건, request token]으로 수집한다. 생태 catch-up에서 현재 Grazing 상태를 과거 전체 시간의 Grazing으로 소급 적용하지 않는다. 이미 사용한 구간은 token으로 다시 지급하지 않는다. input history가 부족한 구간은 grant하지 않고 skipped/unknown exposure를 기록한다.

Coordinator가 completed boundary에서 섭식 요청을 만들고 Ecology가 부족한 Food를 결정된 순서/공통 배분 규칙으로 분배한다. 전체 result set을 검증한 뒤 실제 GrantedAmount로 Energy를 갱신한다. 실패한 이동·위협 전환·이주·사망 시 이용 exposure 종료/정리 경계를 남긴다. StateTree/SmartObject animation 완료가 Energy 지급 권한을 갖지 않는다.

## 8. Attack·nutrition·lifecycle 공통 경계

종별 Wolf Attack Task는 target ref·감각 근거·request ID·공격 의도를 제출한다. 공통 resolver가 권위 actual target·현재 거리/LOS·Alive·cooldown·종 관계·region/시간 조건을 검사한다. 공격 검증에는 서버 실제 pose를 사용할 수 있지만 그 정보가 Brain의 추적 위치를 갱신하는 채널이 되지 않는다.

새 공격 요청 경로는 opt-in Entity에서 기존 자동 Predator proximity 포획 경로를 제외한 후 활성화한다. 동일 prey에 여러 요청이 오면 결정된 시각/ID tie-break와 death receipt를 사용해 한 번만 확정한다. 현재 사망 coordinator는 재사용하고 damage/kill candidate만 전달한다.

초기 nutrition mode는 `InstantCaptureReward`다. death receipt 뒤 한 번 지급하는 현재 모형을 사용하며 EatCooldown은 회복/표현 상태다. `CarcassConsumption`은 나중에 잔여량·ResourceId·유효기간 원장을 추가해 실제 섭식 구간당 지급한다. 두 방식을 동시에 켜 일회 보상과 사체 보상을 중복 지급하지 않는다.

WorldEpoch/Step·birth·죽음·grant·Region·request 중복을 기존 coordinator에서 검증한다. coordinator는 월드 하나, Clock도 하나다. Migration/Population 규칙을 새 Brain Task로 복제하지 않는다. fixture target의 결과는 13절의 별도 시험 domain으로 처리한다.

### 8.1 기존 coordinator에 필요한 연결 변경

| 현재 연결점 | opt-in 확장 계획 |
| --- | --- |
| `RegisterTemplates`/설정 검사 | EnabledRoles별 Config만 요구. 기존 Custom/PPO 필수 조합 검사는 legacy/new runtime mode로 분기 |
| `Spawn`·role별 provider 등록 | 활성 종만 생성·stable lookup에 등록. 종별 몸체/profile·backend/grounded tag를 검증 |
| `ProcessResourceStep` feeding | 기존 Herbivore/Forage×Density 모드는 유지. 새 GrazeExposure 모드는 diet capability·actual exposure로 요청 생성. pending/result 검증은 공통 재사용 |
| `EcoMassSurvival::Advance` | 현재 HP/Energy writer를 유지. 종별 선택 nutrition/activity adapter를 반영하되 두 번 metabolism 적용하지 않음 |
| 포획 결과 인계 | 신규 RequestDriven candidate/receipt를 기존 death 원인·ID·step 검사로 연결. legacy proximity mode와 배타 |
| `UpdateSimulationLOD` | 새 grounded/StateTree scheduling Entity는 제외해 interval multiplier 이중 적용 금지 |
| `UpdatePresentationAndNoise` | actual move result·ActivityCode를 기존 snapshot으로 변환. 기존 flag 의미/version 유지 |
| wave·Population·Migration | 활성 종 role/diet capability 기준으로 분기하고 Population 보존·Region commit 경계는 그대로 유지 |

이 변경은 coordinator를 종별로 복사하는 작업이 아니다. 대역→실제 제공자와 legacy→new execution은 시작 시 설정으로 선택하고 run 도중 몰래 전환하지 않는다.

## 9. 실행 phase·그룹·순서

목표 신규 opt-in pipeline은 다음 DAG다. 실제 engine/project processor graph를 capture해 이름·순환·query match를 검증한다.

신규 frame Processor는 PrePhysics를 기본으로 구성한다. 엔진의 실제 등록 phase와 group은 C2에서 graph로 확인하고 엔진 전역 설정을 변경해 legacy/Box 경로까지 재배치하지 않는다. coordinator는 기존 OnWorldPostActorTick 안전 경계를 유지한다.

| 순서 | phase/group와 실행 | 주요 쓰기 |
| --- | --- | --- |
| 1 | LOD collector → engine SimulationLOD → project importance 보정, Behavior 전 | effective simulation tier |
| 2 | 감각 후보/World/Ecology snapshot 준비, Behavior 전 | 감각/input values·due reasons |
| 3 | scheduler wake → 엔진 StateTree Behavior | Raw Action 또는 Activity intent |
| 4 | 기존 Social Response/Shelter Lifecycle + project final Arbiter, Tasks 전 | Social Request·final MoveRequest |
| 5 | budget NavRequest 처리 → 엔진 PathFollow/Boundary, Tasks | Cached/ShortPath·MoveTarget·Edges |
| 6 | 엔진 Steering + project 보조 조향, Avoidance 전 | Force |
| 7 | 엔진 Avoidance → ApplyForce | Force 보정→DesiredVelocity·Force reset |
| 8 | project grounded final writer, Movement | Transform/Velocity/heading·MoveResult |
| 9 | 결과·interaction/attack 수집, Movement 뒤 | exposure·권위 요청 후보 |
| 10 | 기존 OnWorldPostActorTick 안전 경계 | 생존/자원/Death/Region/Population·요약·정리 |

기존 Social processor가 Behavior 그룹에 있다는 이유로 StateTree와 같은 frame의 모든 입력을 서로 요구하지 않는다. StateTree는 준비된 감각/관측을 읽고 Social은 Raw output 이후 실행한다. Herd shared/Alarm을 production 정책 입력으로 사용할 때는 previous completed social snapshot을 bind하거나 별도 explicit dependency를 만든다. 양방향 dependency는 금지한다.

Shelter lifecycle은 이전 완료 feedback을 읽고 이번 요청을 발행한다. 이번 MoveResult는 다음 패스에 소비한다. attack after-movement는 신규 opt-in execution version이며 기존 baseline ordering은 보존한다. strict 비교의 전투 순서를 바꾸면 모든 비교군에 동일하게 적용하고 기준선을 다시 기록한다.

StateTree 기본 activation이 첫 input 준비 전에 Start될 수 있으므로 초기 root는 `AwaitInput`이다. 유효 snapshot/dependency가 준비될 때 wake한 뒤 정상 tree를 시작한다. activation 시에 실제 movement/Claim을 바로 수행하지 않는다.

## 10. Mass Simulation LOD와 처리 예산

### 10.1 엔진 연결과 안전한 초기 설정

Simulation용 `UMassDistanceLODCollectorTrait`와 `UMassSimulationLODTrait`를 사용한다. 같은 Entity에 full `UMassLODCollectorTrait`가 필요하면 full collector 한 개로 통합하고 distance collector tag를 함께 붙이지 않는다. 기존 ReplicationTrait는 별도 `FMassReplicationViewerInfoFragment`를 쓰므로 simulation viewer Fragment와 동일 데이터로 취급하지 않는다. 초기 Params.bSetLODTags=false, bEnableVariableTicking=false다. 상세 이동은 every-frame 동일 dt로 유지하고 **Brain/감각 후보/검색/경로 요청 빈도**부터 낮춘다.

engine LOD 뒤 `UEcoSimulationImportanceProcessor`가 no-viewer/Off를 Low로 보정하고 긴급·추격·공격·lease/이주를 High로 승격한다. 엔진값/보정 사유를 trace하고 최종 `FMassSimulationLODFragment.LOD`를 activation/Tasks가 읽기 전에 확정한다. Low/Off 반영을 Tag로 매 frame 옮기지 않는다. 초기 Off tag가 남아 있으면 template validation에서 거부한다.

stock PathFollow는 Simulation LOD Off에서 실제 steering과 다른 progress 처리를 할 수 있으므로 opt-in에서 Off를 허용하지 않는다. stock variable tick fragment를 붙이고 custom grounded 이동을 드문 큰 dt로 돌리는 것은 초기 범위 밖이다. 그 확장은 path-follow/steering/force/충돌/lease 시간을 함께 검증해야 한다.

Dedicated Server에서는 연결된 모든 플레이어·권위 interest source의 위치를 거리 입력에 제공한다. no-player는 Low 기본값으로 계속 진행한다. 급박한 동물은 플레이어 거리와 무관하게 High다. representation Off 또는 replication irrelevant가 Simulation Off/Death를 만들지 않는다.

### 10.2 주기 시작안

아래 값은 실험 시작안이며 UE 기본값·최종 성능 보장이 아니다. strict V1 비교는 기존 주기 그대로다.

| tier | Brain normal | 감각 후보 검색 | 일반 후보/경로 갱신 | 이동·생존·lease |
| --- | --- | --- | --- | --- |
| High | 0.1~0.25s | 0.1~0.2s | 변경/invalid 시, 최소 재요청 간격 | 상세 이동 유지, 거래/lease 독립 |
| Medium | 0.25~0.5s | 0.25~0.5s | 후보 cache·budget | 동일 |
| Low | 0.75~1s | 0.5~1s | 평온 시 재사용, maximum decision age | 동일 |

위협이 생겼을 때 저빈도 후보 검색 때문에 감지를 못 하는 지연도 측정한다. 근접 interaction broadphase·known predator/prey proximity·noise event 같은 저비용 긴급 trigger를 별도로 제공해 다음 scan을 앞당긴다. 실제 LOS/감각 검사를 생략해 완전한 감지로 처리하지 않는다.

각 due query는 chunk batch로 처리하되 개체 nextDue와 중요도를 존중한다. StableAgentId phase, 입력/목적지 revision dedupe, queue aging·maximum wait를 사용한다. existing `UpdateSimulationLOD`는 새 tag에 interval 배수를 다시 쓰지 않게 제외해 두 scheduler가 같은 deadline을 경쟁하지 않게 한다.

### 10.3 비용과 메모리

query access·chunk fragmentation·bytes/entity·path corridor heap·StateTree instance allocation·Nav projection/FindPath max·collision/LOS trace/sweep·Smart Object 검색·Signal 수를 각각 계측한다. profile은 동일 종끼리 공유하며 개체별 curve UObject를 생성하지 않는다.

frame/chunk scratch는 reserve/reuse, AgentLookup은 안전한 생성/삭제 revision 기반 갱신, World 금지영역은 spatial index·revision cache를 사용한다. worker는 immutable 값 snapshot만 계산하고 resource/Claim/World UObject 접근은 engine API 실행 계약에 맞춘다. 이 계획은 모든 StateTree/Navigation이 worker에서 실행된다고 가정하지 않는다.

## 11. Replication LOD·표현

기존 `UEcoMassReplicator`/`AEcoMassClientBubbleInfo`와 per-connection LOD를 유지한다. AI의 effective tier를 연결별 ReplicationLOD에 복사하지 않는다. 한 늑대가 두 Client 사이에 있으면 각 연결의 relevance/interval이 따로 결정된다.

DTO 추가 후보는 compact ActivityCode·ActivityRevision·actual speed·표현용 interaction flag다. 이전 Flags는 alive/eating/pursuing/vitals-known 비트로 이미 의미가 있으므로 버전 검토 없이 다른 용도로 덮어쓰지 않는다. Health/Energy·species/region·sample/visual/reset revision 계약을 재사용한다. StateTree instance·경로·ClaimHandle·target의 숨겨진 위치는 전송하지 않는다.

서버 completed movement로 heading/pose를 게시하고 Client는 수신 sample과 visual revision에 따라 보간·애니메이션만 수행한다. relevance Remove는 logical death가 아니다. Client Actor pool 반환 때 종/활동/interaction/identity 상태를 초기화한다. root motion이나 Actor tick이 Mass 위치를 역으로 갱신하지 않는다.

Standalone/Listen/Dedicated+Client에서 실제 template·execution flags를 확인한다. engine movement/nav 일부가 AllNetModes인 사실만으로 Client 실행이 안전한 것으로 간주하지 않고 Client template에서 필요한 논리 Fragment를 제외한다.

## 12. 스레드·구조 변경·수명

입력 gather/World/LOS/Nav/SmartObject 초기 service는 GT다. pure value score/기하/보조 조향은 독립 출력 batch로 분리해 병렬화한다. engine StateTree parallel mode를 켤 때 schema dependencies·common nodes·asset/instance 수명·Task side effects를 검증하고 nested ParallelFor를 중복 켜지 않는다.

값 snapshot은 epoch/frame/완료 시각을 갖고 다음 frame의 fragment view를 보관하지 않는다. reservation/resource commit과 Life/Region 변경은 기존 안전 경계다. processor loop의 구조 변경은 deferred buffer, 프레임 종료 destroy는 기존 replication observer+StateTree instance destructor가 실행되는 방식으로 처리한다. bulk 삭제에서 StateTree instance memory·path sharedptr·slot claim·queued deadline 정리가 모두 수행되는지 확인한다.

동일 HP/Energy에 두 survival processor가 쓰지 않게 새 tag를 기존 PPO vitals/Predation write query에서 어떻게 제외할지 명시한다. 신규 activity/stamina 소모는 공통 coordinator의 species survival adapter로 넘기며 별도 tick에서 Energy를 추가 차감하지 않는다.

## 13. 독립 시험 provider

공통 candidate provider interface는 production Entity/World source와 explicit test fixture source를 선택한다. fixture는 path를 따라 움직이는 value target, noise schedule·visibility 상태를 제공한다. 실제 화면 Actor는 선택적 시각화이며 target state 권위가 아니다.

감각 service는 fixture도 거리/FOV/LOS/환경·age 검사를 거쳐 입력에 넣는다. fixture target의 Domain을 보존하고 기존 `FEcoPreySenseFragment.TargetAgentId`에 가짜 실제 ID를 넣지 않는다. 새 target adapter가 legacy cue의 ageing math를 재사용한다.

Fixture attack resolver는 가상 receipt를 test ledger에 기록하고 production Ecology death/predation 기록을 호출하지 않는다. wolf 생존 시험에 필요한 에너지는 명시적인 FixtureNutrition event로 coordinator를 통해 지급하며 fixture ledger와 production nutrition counter를 분리한다. fixture 세션을 실제 prey 포식 성능으로 보고하지 않는다.

Deer/Wolf 통합 시 fixture는 config 검사에서 금지한다. source kind·fixture count·nutrition mode·실제 species count를 run manifest에 출력해 대역이 남아 있는 통합을 드러낸다.

## 14. 공통 검증과 개발 gate

| gate | 수동 재현/증거 |
| --- | --- |
| Config | DeerOnly/WolfOnly에서 다른 종 Config null 허용, Both는 두 구성 요구. invalid asset/Fragment/writer/Client 논리 구성 거부 |
| StateTree | AwaitInput→활성, 점수 변화 재선택, minimum dwell/urgent interrupt, stale wake·instance 삭제 정리 |
| Path | 원거리 corridor·partial refill·single-point·unreachable·target change·streaming invalid·budget 대기·삭제 callback |
| Movement | 경사/물/절벽/금지영역/dynamic collision, actual speed·stop·회피·하나의 적분, 긴 frame clamp counter |
| Slot | 중복 claim·접근 실패·유효 도착·occupied·owner death·월드 종료·slot invalid·idempotent release |
| 거래 | 실제 exposure만 지급, 자원 부족 배분, 중복/과거 결과 거부, birth/death/Region 시간 조건 |
| LOD | no-player Low, 원거리 Energy/Food 계속 변화, emergency 승격, state/lease 유지, 초기 OffTag 없음 |
| Network | 2개 이상 Client 연결별 relevance, Remove≠Death, Activity revision·보간·pool reset, Client Brain 0건 |
| 성능 | baseline와 기능별 Insights 캡처, p95/p99·request max·memory·decision/path delay·network budget |

Root AGENTS.md의 직접 UBT/실행 중 프로세스 확인 규칙을 구현마다 적용한다. 문서만 작성한 이번 변경에는 UBT/PIE를 새로 수행하지 않았다. 목표 hardware/tick/규모별 budget은 C0에서 기록한다. 기존 자동화 테스트 생략 방침에 맞춰 수동 scenario+반복 capture를 기본으로 하고 실제 미수행 항목을 분리한다.

## 15. 공식 문서와 로컬 엔진 근거

- [Mass StateTree Trait](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassAIBehavior/UMassStateTreeTrait), [Mass schema](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassAIBehavior/UMassStateTreeSchema), [Utility Selectors](https://dev.epicgames.com/documentation/en-us/unreal-engine/state-tree-selectors-overview)
- [Mass NavMesh Trait](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassNavMeshNavigation/UMassNavMeshNavigationTrait), [Path Follow Task](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassAIBehavior/FMassNavMeshPathFollowTask)
- [Mass Steering](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassNavigation/UMassSteeringTrait), [Avoidance Trait](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassNavigation/UMassObstacleAvoidanceTrait), [Mass Avoidance 설명](https://dev.epicgames.com/documentation/en-us/unreal-engine/mass-avoidance-overview-in-unreal-engine)
- [Simulation LOD Trait](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassLOD/UMassSimulationLODTrait), [MassGameplay LOD/Replication](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-gameplay-in-unreal-engine)
- [SmartObject User Trait](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassSmartObjects/UMassSmartObjectUserTrait), [Smart Objects 개요](https://dev.epicgames.com/documentation/en-us/unreal-engine/smart-objects-in-unreal-engine---overview)

2026-10-14에 확인한 엔진 파일(아래는 `Engine/` 기준 경로; 다른 설치 머신에서도 해당 엔진 Source로 대조):

```text
Plugins/AI/MassAI/Source/MassAIBehavior/Private/MassStateTreeSchema.cpp
Plugins/AI/MassAI/Source/MassAIBehavior/Private/MassStateTreeTrait.cpp
Plugins/AI/MassAI/Source/MassAIBehavior/Private/MassStateTreeProcessors.cpp
Plugins/AI/MassAI/Source/MassAIBehavior/Public/MassStateTreeTypes.h
Plugins/AI/MassAI/Source/MassAIBehavior/Private/Tasks/MassNavMeshPathFollowTask.cpp
Plugins/AI/MassAI/Source/MassNavMeshNavigation/Private/MassNavMeshNavigationTrait.cpp
Plugins/AI/MassAI/Source/MassNavMeshNavigation/Private/MassNavMeshNavigationProcessors.cpp
Plugins/AI/MassAI/Source/MassNavMeshNavigation/Private/MassNavMeshNavigationBoundaryProcessor.cpp
Plugins/AI/MassAI/Source/MassNavigation/Private/MassSteeringTrait.cpp
Plugins/AI/MassAI/Source/MassNavigation/Private/MassSteeringProcessors.cpp
Plugins/AI/MassAI/Source/MassNavigation/Private/MassAvoidanceTrait.cpp
Plugins/AI/MassAI/Source/MassNavigation/Private/MassNavigationObstacleTrait.cpp
Plugins/Runtime/MassGameplay/Source/MassMovement/Private/MassMovementTrait.cpp
Plugins/Runtime/MassGameplay/Source/MassMovement/Private/MassMovementProcessors.cpp
Plugins/Runtime/MassGameplay/Source/MassLOD/Public/MassSimulationLOD.h
Plugins/Runtime/MassGameplay/Source/MassLOD/Private/MassLODTrait.cpp
Plugins/Runtime/MassGameplay/Source/MassSmartObjects/Private/MassSmartObjectUserTrait.cpp
```

주요 확인 파일 SHA-256(조사 시점 재현용; 구현 gate를 통과했다는 의미가 아님):

| 파일 | SHA-256 |
| --- | --- |
| MassStateTreeSchema.cpp | `AEBD75E095B236A92B2FD86CFE08183359F3998B2A6430D8E196AF119FFD5BFC` |
| MassNavMeshPathFollowTask.cpp | `71C15E7DF86DBAA022413E230F64FA8A22EF14E831A0B3354381A5891EF8E3CE` |
| MassMovementProcessors.cpp | `E09730FDA29C7AA946CF4EACD1F7B0E8212F96B588C48CDBB4E1916217A2155E` |
| MassLODTrait.cpp | `A719C866BFCF6C69CF9BF08541A1AB8CFFDBCAE64C34DC2781E0525F79A5C02F` |

프로젝트 근거: [현재 Trait](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureNetworkTrait.cpp), [template 검사](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureTemplateValidation.cpp), [생태 거래](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp), [Replicator](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp), [Social Request/Feedback](../../../Source/AdaptiveEcosystem/AI/Social/EcoSocialFragments.h), [기존 이동/충돌](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureMovement.cpp).
