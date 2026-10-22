# SpeciesAI 코드 책임과 실행 계약

기준: 2026-10-14 working tree. 소스 기준 구현 설명이다. 레벨 실행을 통과했다는 의미는 아니다. 아래 파일은 `Source/AdaptiveEcosystem/` 기준이다. 각 header는 해당 cpp의 타입/계약을 선언한다.

## 1. 파일별 책임

| 파일 | 소유하는 책임 | 다른 계층에 맡기는 책임 |
| --- | --- | --- |
| `Core/EcoActivityTypes.h` | 안정적인 Activity 표현 코드 | Brain·이동·수명 처리 |
| `AI/Behavior/EcoSpeciesAIProfile.h/.cpp` | 종별 공유 설정·범위/StateTree schema 검증 | 개체 상태·실시간 설정 변경 |
| `AI/Behavior/EcoSpeciesAIFragments.h/.cpp` | 개체별 snapshot/decision/execution/move/attack/exposure 계약, request revision | World 서비스·Food/Vitals 거래 |
| `AI/Behavior/EcoSpeciesAITemplate.h/.cpp` | opt-in Mass 구성·엔진 shared params·brain과 movement tag | 스폰/Population·클라이언트 논리 |
| `AI/Behavior/EcoSpeciesAIInputProcessor.cpp` | GT 감각/provider/Herd 값 gather, 중요도/주기, wake signal | StateTree 선택·위치 적분 |
| `AI/Behavior/StateTree/EcoSpeciesAIStateTreeNodes.h/.cpp` | Mass dependency 선언, snapshot evaluator, raw policy/행동 선호 Task | LOS/Nav/SO query·자원/HP·Actor 접근 |
| `AI/Behavior/Deer/EcoDeerUtility.cpp` | 사슴 점수와 Raw Action 매핑 | Social modulation·섭식 원장 |
| `AI/Behavior/Deer/EcoDeerExecution.cpp` | 배회/도주/섭식·휴식/복귀의 실행 의도, 실제 점유 전 Hold 금지 | 최종 위치·Energy 쓰기 |
| `AI/Behavior/Wolf/EcoWolfUtility.cpp` | 늑대 생활/추격/수색/식사 cooldown 점수 | 실제 먹잇감 위치를 추적 입력으로 조회 |
| `AI/Behavior/Wolf/EcoWolfExecution.cpp` | 기억 위치 추적·포기/표적 cooldown·공격 요청 | 공격 성공/Death/보상 확정 |
| `AI/Behavior/EcoSpeciesAIActivityProcessor.cpp` | World 생존/Travel/Social Shelter 우선순위, 일반 슬롯 예약, 종별 의도를 공통 Move에 연결 | 지면 이동·Ecology 회계 |
| `AI/Behavior/EcoSpeciesAIActors.h/.cpp` | authored Graze/Rest 장소와 명시적인 scripted fixture | 실제 논리 동물·지역 Food 잔고 |
| `AI/Behavior/StateTree/EcoSpeciesAIAssetBuilder.h/.cpp` | 서로 다른 StateTree/Profile/EntityConfig와 기본 슬롯 에셋 작성·컴파일 | 맵 편집·게임 자동화 테스트 |
| `AI/Policy/EcoObservationBuilder.h/.cpp` | PPO/V1 StateTree가 공유하는 7개 관측 인코더 | 정책 추론·상수/가중치 수정 |
| `Mass/Navigation/EcoSpeciesAINavigationProcessor.cpp` | GT 경로 예산·aging·revision·NavData/projection/corridor/short-path | 실제 이동·도착 점유 확정 |
| `Mass/Movement/EcoSpeciesAIGroundConstraint.h/.cpp` | capsule sweep·ground probe·경사/높이·Region/금지영역 검사 | 생태 Region commit·Transform 저장 |
| `Mass/Movement/EcoSpeciesAIGroundSceneSubsystem.h/.cpp` | World별 금지 NavModifier bounds를 프레임당 한 번 수집 | Replication·개체 논리 상태 |
| `Mass/Movement/EcoSpeciesAIMovementProcessor.cpp` | 새 개체의 유일한 Transform/Velocity writer, actual arrival/progress, Shelter feedback, Graze exposure | Food 지급·Death·Region 이동 commit |
| `Mass/Movement/EcoCompatibleNavigationHeightProcessor.h/.cpp` | 새 grounded 개체를 제외한 기존 엔진 높이 보정 동작 | 새 개체의 높이 보정 |
| `Creature/Runtime/Interaction/EcoSpeciesAIInteractionSubsystem.h/.cpp` | 비Shelter SO 예약/lease/점유/해제·무효화, 장소 grid, 도달 불가 장소 cooldown, fixture receipt queue | Shelter 예약·지역 Food 원장·네트워크 |
| `Creature/Runtime/Interaction/EcoSpeciesAIAttackProcessor.cpp` | 요청 순서·fresh sight·실제 거리/LOS·resident/region·cooldown 검증, lethal candidate/fixture receipt | Brain의 숨은 위치 갱신·Population/보상 commit |
| `Debug/EcoSpeciesAIDiagnostics.cpp` | 수동 cohort 상태 출력·CSV/manifest snapshot | 자동 실행·상태 변경·성능 통과 판정 |

`AI/Behavior/EcoSpeciesAIBehavior.h`, `EcoSpeciesAIExecution.h`, `EcoSpeciesAIProcessors.h`는 각각 순수 정책 함수, 실행 의도 함수, Processor 선언을 묶는다. 종별 구현이 서로의 cpp를 호출하거나 include하지 않는다.

## 2. 기존 파일의 연결 변경

| 기존 파일 | 이번 추가 연결 |
| --- | --- |
| `Creature/Runtime/EcoCreatureNetworkTrait.h/.cpp` | bUseSpeciesAI/Profile로 기존 template 조립 후 새 helper 적용; Client에는 적용하지 않음 |
| `EcoCreatureIntegrationSpawner.h`, `EcoCreatureSetupValidation.cpp`, `EcoCreatureTemplateValidation.cpp` | DeerOnly/WolfOnly/Both·활성 역할만 검사·profile/schema/OffTag/NavData·Client 배제·stock height writer 검사 |
| `EcoCreatureSpawning.cpp`, `EcoCreatureLifecycle.cpp`, `EcoCreatureScheduling.cpp` | 역할별 spawn/wave 필터, 실제 Graze 시간으로 공통 FeedRequest 생성, fixture 보상 별도 처리, 새 scheduler와 기존 policy LOD 중복 배제 |
| `AI/Policy/EcoPolicyProcessor.cpp` | 새 Brain 제외·공통 관측 encoder 사용; 기존 PPO 계산식 유지 |
| `AI/Policy/EcoSteeringProcessor.cpp`, `Creature/Runtime/EcoCreaturePredatorProcessor.cpp` | 새 grounded tag 제외; V1 정책 비교는 기존 writer 유지 |
| `AI/Policy/EcoPredationProcessor.cpp` | 새 늑대의 자동 근접 포획 제외 |
| `AI/Social/Alarm/EcoAlarmProcessors.cpp` | Social Response가 Mass StateTree Raw Action 뒤 실행되도록 dependency 추가 |
| `Network/Mass/EcoMassReplicationTypes.h`, `EcoMassReplicator.cpp`, `EcoMassClientBubble.cpp` | 연결별 기존 Bubble에 activity byte 추가·변경 시 visual revision/우선 갱신 |
| `EcoCreaturePresentation.cpp`, `Creature/Representation/EcoCreatureVisualState.h`, `EcoCreatureAnimInstance.h/.cpp` | 받은 Activity를 표현/AnimBP 읽기 전용 값으로 전달 |
| `AdaptiveEcosystem.Build.cs`, `.uproject`, `Config/DefaultMass.ini` | 실제 UE 5.8 모듈/플러그인·높이 writer 배타 설정 |

작업 시작 시 존재했던 다른 Source/에셋 변경과 이번 변경은 같은 working tree에 있다. 기존 변경을 되돌리거나 자동 커밋하지 않았다.

## 3. 처리 순서와 권위

```text
기존 Neighborhood/Perception + engine LOD
  → SpeciesAI Input (값 gather / 최종 Simulation tier / signal)
  → Behavior: Mass StateTree Raw Action → 기존 Social Response/Shelter
  → SpeciesAI Activity (Travel/Shelter 우선, ModulatedAction·목적지 소비)
  → Tasks: SpeciesAI Nav → engine PathFollow/Boundary
  → engine Steering/Avoidance/ApplyForce
  → SpeciesAI Movement (한 번의 지면 위치 적분 / actual feedback)
  → SpeciesAI Attack (요청 검증 / lethal candidate)
  → 기존 coordinator 완료 경계 (survival/death/food/arrival/migration/summary)
```

Input이 읽는 Herd/개인 위협 snapshot 일부는 이전 완료 Behavior 패스의 값이다. Social lifecycle도 이전 완료 movement feedback을 다음 패스에 소비한다. 이 경계에서 같은 프레임의 미완료 상태를 완료 결과로 해석하지 않는다. 실제 동적 StateTree를 포함한 processor graph와 지연은 수동 gate에서 확인해야 한다.

현재 Social 패스의 Panic은 Activity가 즉시 읽어 Shelter 또는 Flee를 실행한다. 다음 입력 gather도 새 Panic으로 앞당긴다. 행동/Travel/Shelter·표적 변경은 이전 경로를 취소하므로 기존 repath 제한 때문에 반대 행동의 경로를 계속 걷지 않는다. 성공한 공격의 Eat cooldown은 정기 StateTree 재선택을 기다리지 않고 실행에 적용한다.

새 runtime Processor는 Server/Standalone execution flags와 Authority tag를 요구한다. Client에는 vitals/brain/request/StateTree instance/경로 fragment가 없다. Subsystem은 로컬 서비스이며 RPC/복제 transport가 없다.

기존 `FMassCustomMovementTag`가 엔진 ApplyMovement를 배제하고, Grounded tag가 기존 사슴/늑대 writer 및 호환 높이 writer를 배제한다. representation/root motion/animation notify가 논리 위치·HP·Energy를 갱신하지 않는다.

## 4. 시간·실패·회계

- Brain/cue/추격·공격 cooldown·slot lease는 World time이다. feeding segment/fixture reward 지급 경계는 기존 Ecology clock이다. 두 시계를 같은 숫자로 가정하지 않는다.
- Movement는 frame dt를 최대 0.1초로 제한하고 최대 16 substep을 수행한다. 제외된 시간은 ClampedSeconds에 누적한다. 긴 hitch의 전체 거리를 한 번에 이동하거나 그 전체 시간만큼 섭식하지 않는다.
- Pending path에는 요청 deadline이 있고, 이동 중에는 실제 거리 감소에 기반한 progress timeout이 있다. 정상적인 긴 이동을 최초 요청 deadline 때문에 실패시키지 않는다.
- 도착은 실제 위치와 원래 목적지 반경으로 판정한다. Nav projection이 도착 반경보다 크게 벗어나면 경로 요청을 거부한다. partial 경로는 기본 거부한다.
- 일반 슬롯은 6,000cm 범위의 2,000cm grid로 찾는다. 지점은 고정 authored Actor다. 실행 중 장소를 이동하면 unregister/register로 index를 갱신해야 한다.
- 엔진 slot invalidation callback은 토큰을 무효화한다. cleanup/lease/죽음/삭제/지역 변경/의도 변경이 해제한다. 도달 불가 장소는 해당 owner에게 10초 제외하고 reservation을 풀어 다른 장소를 고를 수 있게 한다.
- Graze는 살아 있는 resident·점유 token·무위협·실제 저속 조건에서만 노출 시간을 기록한다. coordinator가 segment를 한 번 소비해 공통 FeedRequest를 만들고 실제 granted food로 Energy를 갱신한다. 최대 32개 불연속 segment를 보관하고 초과 시간은 DroppedSeconds에 기록한다.
- 공격 요청은 시간→StableAgentId 순서로 처리한다. fresh sight·현재 range/LOS·region/resident·생존을 재검사하고 Requested sequence를 한 번 resolve한다. 실패 재시도는 최소 0.25초, 성공은 프로필 AttackCooldown이다.
- 실제 포식은 prey HP=0과 death candidate를 먼저 기록한다. death receipt·Population/History·영양의 최종 owner는 기존 coordinator다. 이것은 새 범용 transactional combat framework가 아니다.
- target domain은 Entity/Fixture로 분리한다. 요청/queue는 World 안에서만 살아 있고 비동기 완료를 보관하지 않는다. 명시적인 epoch/generation을 모든 요청에 넣는 비동기/영속 복원 확장은 아직 제공하지 않는다.

## 5. 효율과 확장 지점

공유 프로필/엔진 파라미터와 개체별 hot state를 분리한다. mutable 상태를 Shared Fragment에 넣지 않는다. 상태 변경마다 Activity tag를 바꾸지 않고 enum/revision을 갱신하므로 그 이유의 archetype churn을 피한다.

평온 Brain 주기는 High/Medium/Low에서 1/2/4배다. no-viewer는 Low, 위협·추격·공격 cooldown·slot·Travel·매우 낮은 Energy는 High로 보호한다. stock Off/variable movement tick은 새 구성에 붙이지 않는다. 실제 이동·생존·자원 clock은 멈추지 않는다. representation/replication relevance는 별도다.

경로는 기본 frame당 full query 최대 8개·soft 2ms이며 aging을 적용한다. World/UObject/LOS/Nav/SO/commit은 GT, StateTree task는 선언된 external fragment만 접근한다. 기본 engine StateTree parallel 설정을 임의로 바꾸지 않았다. 순수 점수 함수는 향후 numeric batch로 옮길 수 있다.

기존 coordinator의 논리 개체 상한은 512를 유지한다. 2,048 이상의 처리 능력을 검증하거나 그 상한을 변경한 구현이 아니다. 고밀도 이동의 capsule/LOS 비용, site contention, pathfinding 단일 호출 최대 시간은 실측이 필요하다.

현재 기본 nutrition은 Instant Capture Reward다. Carcass resource/slot, Wolf Pack, stamina/수분/체온, 새 species relation registry, ORCA, multi-hop alarm, patch별 Food ledger, asynchronous path service, aggregate distant simulation은 별도 계약을 추가하는 후속 확장이다. 기존 계획의 후속 항목을 기본 구현 완료에 포함하지 않는다.
