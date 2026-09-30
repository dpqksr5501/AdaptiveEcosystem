# M3 개발 계획 — 낮밤 스폰·먹이 고갈·지역 이주 검증

> 대상: [M3 — Authoritative Ecology Simulation Core](M3_ECOLOGY_SIMULATION_CORE.md)  
> 기준: Unreal Engine 5.8 / 단일 런타임 모듈 `AdaptiveEcosystem`  
> 갱신일: 2026-09-28  
> 상태: 기획 및 개발량 추정. 구현·실행 검증을 완료했다는 의미가 아니다.  
> 이번 우선순위: 플레이어 없이 2개 지역에서 스폰·정기 소비·낮밤 이벤트·고갈·실제 이주를 Box로 관찰한다.

## 세부 마일스톤과 진행 순서

합의한 관찰 범위를 **정확히 3개의 세부 마일스톤**으로 나눈다. 각 문서의 종료 기준을 만족한 뒤 다음 문서로 진행한다. M3.1~M3.3 코드/Editor 빌드는 완료했고, 기능별 PIE 확인 상태는 각 문서와 [M3.3 에디터 테스트](M3_3_EDITOR_TEST.md), [검증 기록](M3_VALIDATION_REPORT.md)에 구분하여 기록한다. 이번 M3.3 요청에서는 자동화 테스트를 생략했다. 체크되지 않은 항목은 검증 완료를 뜻하지 않는다.

| 순서 | 세부 계획 | 주요 소유권 / 결과 | 예상 인일 |
| :--- | :--- | :--- | :--- |
| M3.1 | [지역·낮밤·권위 스폰 기반](M3_1_WORLD_AND_SPAWN.md) | World 시간/공간, Ecology 스폰 결정, Mass 생성/초기 집계 | 2~3.5 |
| M3.2 | [정기 소비·이벤트·자원 조정](M3_2_RESOURCE_AND_EVENTS.md) | Mass 소비 요청, Ecology 이벤트/공정 배분/Food | 1.5~2 |
| M3.3 | [실제 이주·표시·통합 검증](M3_3_MIGRATION_AND_VALIDATION.md) | Mass 이동/도착/집계, Network 전달, Debug 읽기 전용 표시 | 4.5~7 |
| 합계 | M3.1 → M3.2 → M3.3 | 합의한 관찰 범위 완료 | 8~12.5 (계획상 8~13) |

각 단계는 시간/공간 snapshot → 스폰 요청/결과 → 소비 요청/결과 및 완료 Food snapshot → Migration/완료 집계 → 복제 요약으로 인계한다. World 시계가 시간의 단일 진실값이고 Ecology의 실행 StepId와 예약은 이를 참조한다. 계층 간 GameThread 조정 코드는 호출 순서만 연결하며 별도 Food·개체·시간의 소유자가 되지 않는다.

Energy·기아·사망·V1 Observation/Utility는 관찰 완료 뒤의 잔여 M3 작업이다. 이번 세 마일스톤에 포함하지 않으며 세 단계 완료를 M3 전체 완료와 구분한다.

## 1. 검토 결론과 M3 완료 범위

요청한 사이클은 **M3에서 지금 개발할 만한 최소 생태 검증 시나리오**다. 자원 변화가 개체의 지역 이동과 Population 변화로 돌아오므로 M3의 목적에 부합한다. 낮밤 스폰과 자원 감소 이벤트는 원래 M3 문서에 개별 기능으로 명시되지는 않았으나, 이번 폐루프를 재현하는 최소 환경 입력으로 포함한다.

이 계획에서는 작업을 다음 두 부분으로 나눈다. 새로운 공식 Milestone을 추가하는 것은 아니다.

- **우선 관찰 단계:** 사용자가 요청한 시간 기반 소비와 고갈 이주 데모를 먼저 완성한다.
- **M3 잔여 생태 단계:** Energy/HP, 기아·사망, V1 Observation/Utility, 장시간 생태 안정성을 연결해 기존 M3 전체 완료 조건을 충족한다.

먹이 자생 회복은 사용자 요청에 따라 보류한다. 이전 계획의 먹이 접근 지점, 배고픔에 따른 섭취량, 256마리·30분 검증을 우선 관찰 단계의 선행 조건으로 삼지 않는다. **관찰 데모 완료를 M3 전체 완료로 기록하지 않는다.**

| 고려 항목 | 판정 | 근거와 최소 범위 |
| :--- | :--- | :--- |
| 낮밤에 따른 Spawn 주기 | 지금 | 주야 상태가 생태 개체 수에 영향을 주는 입력. 논리적 Day/Night와 주기/수량만 구현 |
| 시작 시 2개 Region에 개체 생성 | 지금 | 자원 차이와 이주 전후를 비교할 필수 조건 |
| 플레이어 없이 독립 실행 | 지금 | Server/Standalone 생태계의 기본 조건. 플레이어 수·거리·행동에 스폰/Tick을 종속하지 않음 |
| 일정 시간 존재 후 주기적 소비 | 지금 | 개체 존재가 지역 자원에 영향을 주는 최소 피드백. 섭취 위치·식성·Energy는 다음 연결 |
| 고갈된 지역에서 다른 지역으로 이동 | 지금 | M3의 핵심 결과. 동일 Entity가 실제 이동하고 Region 소속을 변경 |
| 낮/밤의 갑작스러운 Food 감소 이벤트 | 지금 | 소비와 구분되는 외부 자원 압력. 고정 시점·고정 차감량 이벤트 각 1종 |
| Box 표현 | 지금 유지 | 기존 M2 표현 재사용. Box는 논리 개체의 표현이며 Actor AI가 상태를 소유하지 않음 |
| Food 재생 | 보류 | 기존 M3 범위였지만 이번 요구는 고갈 검증 우선. 테스트 재생률을 0으로 고정 |
| Energy/HP·기아·사망 | 데모 다음, M3 안 | 이주 관찰의 필수 선행은 아니지만 기존 M3 생태 완료에는 필요 |
| V1 Observation/Utility | 데모 다음, M3 안 | 이번 데모는 고정 규칙으로 인과관계를 먼저 확인. M3 전체 완료 전 기존 V1을 연결 |
| 실제 태양·조명·날씨 연출 | 후속 확장 | 시간/Phase 표시만으로 현재 검증 가능 |
| 최종 Mesh/Anim/Representation LOD | M4 | 이번 목적은 Box 이동 관찰로 충족 |
| 플레이어 공격·포식 압력 수집 | M4, 행동 반영은 M5 | Server 검증과 정책 입력 연결이 필요 |
| 학습된 PPO / Native 추론 / Python parity | M5 | 이번 자원·이주 규칙에 학습 모델이 필요하지 않음 |
| 플레이어 행동으로 태어날 특성 결정 | 별도 후속 기획 | 현재 로드맵에 확정된 기능이 아님. M4/M5의 포식·행동 변화와 출생 특성 결정은 별개. Legacy LLM Evolution을 신규 경로에 연결하지 않음 |
| 몬스터 간 전투·포식·상세 사회 행동 | 후속 기획 | 플레이어 없이 움직인다는 요구는 자율 생태 실행으로 충족하며 전투 구현까지 확대하지 않음 |

**재생 없는 상태에서는 무한히 먹이가 유지되는 순환을 만들 수 없다.** 두 지역 모두 고갈되면 이주 가능한 곳이 없어 대기하며 신규 스폰도 중단한다. 관찰 반복은 테스트 세션 재시작으로 수행하고, 낮밤 전환 시 Food를 몰래 초기화하지 않는다.

## 2. 소스 기준 재사용 가능성과 실제 개발 간극

자료 검토는 C++ 소스와 문서에 근거한다. 사용자가 확인한 M2 Box 표현은 재사용 대상으로 받아들이되, `.uasset` 내부 설정이나 현재 PIE 동작을 이번 문서 작업에서 검증했다고 주장하지 않는다.

| 근거 | 확인한 기반 | 필요한 연결 |
| :--- | :--- | :--- |
| [Core/EcoRegionTypes.h](../../../Source/AdaptiveEcosystem/Core/EcoRegionTypes.h) | Day/Dusk/Night/Dawn enum, Region Food/Capacity/재생률/Population | 시간 진행과 Phase 전환기는 없음. MVP는 Day/Night만 사용 |
| [Mass/EcoMassNetworkBootstrap.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassNetworkBootstrap.cpp) | 초기 SpawnEntities, StableAgentId 할당, RegionId 설정 | Tick 비활성·초기화 1회 구조. 반복 스폰용 batch 생성 경로를 별도로 연결 |
| [Ecology/EcologySimulationSubsystem.cpp](../../../Source/AdaptiveEcosystem/Ecology/EcologySimulationSubsystem.cpp) | Server/Standalone 권위, Food 조회/차감, 재생 함수, ID 할당 | batch 조정, 환경 자원 감소 이벤트, 명시적 실행 주기 |
| [Mass/EcoMassFragments.h](../../../Source/AdaptiveEcosystem/Mass/EcoMassFragments.h) | Identity/Region/Travel/Vitals 계약 | 나이·섭취 시각, Travel 초기화·목적지·진행·도착 실행 |
| [Network/Mass/EcoMassReplicator.cpp](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp) | Transform 전달, 변경된 RegionId의 dirty 처리 | 반복 생성과 이주 결과의 Client 회귀 검증 |
| [Network/EcologyNetworkTypes.h](../../../Source/AdaptiveEcosystem/Network/EcologyNetworkTypes.h) | Region Summary DTO | GameState의 Food/Population 게시 및 Client 표시 연결 |
| [AdaptiveEcosystemGameMode.cpp](../../../Source/AdaptiveEcosystem/AdaptiveEcosystemGameMode.cpp) | 시작 시 Bootstrap 호출과 Running 전환 | 두 지역 모두 초기화되었는지 검증. 현재 OR 방식 준비 판정으로 한 지역 성공만 전체 준비로 처리하지 않게 함 |

추가로 확인할 초기화 문제:

- 기본 Region이 Subsystem의 `Forest_A`와 Bootstrap의 `Region.Default`로 다르다. Region 설정과 Spawn RegionId를 일치시키고 compact index를 채운다.
- 현재 기본 Food 재생률은 0이 아니다. 관찰 설정에서 모든 Region의 재생률을 0으로 명시하고 기본 상태가 이를 덮어쓰지 않도록 한다. 기존 재생 코드를 삭제하지 않는다.
- World Region 등록은 BeginPlay에서 수행된다. Actor BeginPlay 순서에 기대지 않고 두 Region/Template 준비 완료 뒤 생태 시계를 시작한다.
- `TickSimulation()`은 일반 `UWorldSubsystem`의 명시적 메서드다. 이번 실행기는 단일 호출 지점을 갖고 Blueprint/Processor 중복 Tick을 막는다.
- Variant Combat의 Actor Spawner와 Legacy Trait Evolution은 신규 Mass 스폰의 기반으로 사용하지 않는다.

이전에 수행한 UE 5.8 `AdaptiveEcosystemEditor Win64 Development` 빌드는 성공했다. 이번 계획 갱신에서는 소스·Config·에셋을 수정하지 않고 런타임 시나리오도 실행하지 않았다.

## 3. 관찰 단계의 최소 기획 규칙

### 3.1 공간과 논리 개체

- 평평하고 장애물 없는 테스트 맵에 서로 이동 가능한 Region A/B를 둔다. 각 지역에는 Bounds, Spawn 위치, 도착 위치, 인접 RegionId만 설정한다.
- 종은 1개, 특성은 고정값이다. Region마다 초기 8마리를 생성하고, 스폰 웨이브를 추가해 최대 128마리를 관찰하는 설정으로 시작한다.
- 개체는 Mass Entity다. 기존 Box 표시를 유지하고 개체별 Pawn/Character/AIController를 새로 만들지 않는다. Region/Bootstrap/시계용 관리 Actor는 사용 가능하다.
- 지역 내부의 먹이는 균일한 논리 저장소로 취급한다. 해당 지역에 소속되고 이주 중이 아닌 개체는 어디에 서 있어도 소비할 수 있다. 먹이 지점 탐색·도달 판정은 이번에 구현하지 않는다.
- 관찰을 위한 카메라가 있어도 생태 실행은 플레이어 Pawn의 존재나 입력을 요구하지 않는다. Client가 0명이어도 Server/Standalone 논리 결과는 진행한다.

### 3.2 낮밤 시계와 반복 스폰

시간은 Server가 소유하는 시뮬레이션 경과 시간 하나로 판단한다. 초기화가 완료되면 Day에서 시작하고 Day 60초 → Night 60초를 반복한다. Dusk/Dawn 및 실제 조명 변화는 사용하지 않는다.

| 설정 | 제안 기본값 |
| :--- | :--- |
| Day / Night 지속 시간 | 각각 60초 |
| 시작 개체 | A/B 각각 8마리 |
| Day 스폰 | 지역마다 30초 간격으로 4마리 |
| Night 스폰 | 지역마다 20초 간격으로 6마리 |
| 전체 살아있는 개체 상한 | 128마리, 이주 중 개체 포함 |
| 지역 신규 생성 상한 | 현재 소속 개체 64마리. 이주 도착에는 이 제한을 적용하지 않음 |

위 수치는 튜닝값이다. 별도 종·주야 몬스터 목록·스폰 난이도 곡선은 추가하지 않는다.

- 게임 시작 초기 생성과 주기적 웨이브를 구분한다. Phase 진입 때 추가 웨이브를 자동 실행하지 않고 첫 웨이브는 해당 간격이 지난 후 생성한다.
- Phase가 바뀌면 이전 Phase의 다음 스폰 예약을 교체한다. 전환 경계와 이전 예약이 겹치면 새 Phase 규칙을 우선하여 이중 생성하지 않는다.
- 현재 Region Food가 0이면 해당 지역 신규 스폰을 건너뛴다. 지역/전체 상한 초과분은 생성하지 않으며, 건너뛴 웨이브를 나중에 한꺼번에 보상하지 않는다.
- 예약은 `(CycleId, Phase, RegionId, WaveIndex)`로 식별해 같은 웨이브를 두 번 실행하지 않는다. 반복 스폰 호출로 초기 개체를 다시 생성하지 않는다.
- 후속 스폰에서도 StableAgentId, Region/Species ID 및 Runtime Index, 나이/섭취/Travel 초기값을 설정한 뒤 네트워크 생성 알림을 처리한다.

### 3.3 일정 시간 존재 후 먹이 소비

최소 규칙은 **생성 후 20초부터, 이후 10초마다 개체당 Food 1을 요청**하는 것이다. 요청 시점과 적용 결과를 구분하여 나중에 Energy 연결을 붙일 수 있게 한다.

- 생성 시 `NextFeedTime = SpawnTime + 20초`로 설정한다. 첫 소비 후 10초 간격을 따른다.
- 해당 시점에 살아있고 이주 중이 아니면 현재 소속 Region에 요청한다. 전체 Population을 단순 곱하는 방식 대신 개체별 소비 대상 여부를 확인한다.
- 이주 중에는 소비하지 않으며 밀린 섭취를 누적하지 않는다. 도착 시 다음 섭취는 도착 10초 후로 예약한다. 나이와 StableAgentId는 초기화하지 않는다.
- Food가 요청 합보다 작으면 Region별 비례 배분한다. 동일 요청에는 동일량을 지급하고 실제 지급 합만 차감한다.
- 관찰 단계의 소비량은 Energy/Utility와 무관한 테스트 규칙이다. Food를 줄이기 위해 Energy를 임의로 소모하거나 기존 V1의 차원·정규화를 바꾸지 않는다.

최소 조정식:

```text
EventLoss = min(FoodBefore, EventRequestedLoss)
FoodAvailable = FoodBefore - EventLoss
scale = RequestTotal > 0 ? min(1, FoodAvailable / RequestTotal) : 0
Granted_i = Requested_i * scale
FoodAfter = FoodAvailable - sum(Granted_i)
```

NaN/Inf·잘못된 Region·중복 소비를 거부하고 Food는 `[0, FoodCapacity]`를 유지한다. `(StepId, StableAgentId)`로 중복 지급을 방지한다. 환경 이벤트에 의한 손실은 먹이 섭취나 Predation으로 기록하지 않는다.

### 3.4 낮/밤 자원 감소 이벤트

일반 이벤트 프레임워크 대신 설정 가능한 Food 감소 이벤트 2종으로 시작한다.

- **Day 이벤트:** Day 시작 25초 후 Region A의 Food를 고정량 감소.
- **Night 이벤트:** Night 시작 15초 후 Region B의 Food를 고정량 감소.
- 각 이벤트는 Phase별 1회이며 `(CycleId, Phase, EventId, RegionId)`로 중복을 막는다.
- 감소량은 설정값이고 현재 Food보다 크면 실제 Food 잔량만 감소한다. Phase 전환이나 이벤트 실행은 Food를 회복시키지 않는다.
- World 시계가 이벤트 발생 시각을 제공하고 Simulation 조정 단계가 Food를 변경한다. Region Actor의 Legacy FoodAvailability를 수정하지 않는다.
- 이벤트와 소비가 같은 시각이면 **이벤트 손실 → 소비 배분 → 고갈 판정** 순서를 적용한다. 로그에는 두 손실 원인을 따로 남긴다.

### 3.5 고갈과 실제 Migration

개체 상태는 `Resident → Traveling → Resident`를 기본으로 하고, 목적지가 없는 경우 `WaitingForFood`로 둔다. Region Food가 부동소수점 오차 범위 내 0이면 다음 Migration 판단 주기에 고갈을 인지한다. MVP 판단 주기는 1초로 제안한다.

1. 현재 지역이 고갈되면 인접 지역 중 Food가 남은 곳을 찾는다. 2개 지역이므로 처음에는 다른 한 곳만 확인한다.
2. 목적지가 있으면 Region/Travel 상태를 기록하고 Box가 목표 지역 내부 도착 위치를 향해 실제 이동한다.
3. 도착 전에는 출발 Region에 논리적으로 소속된다. 도착 위치와 Bounds 조건을 만족하면 RegionId/Runtime Index를 함께 변경한다.
4. 도착 후 그 지역 소비 규칙을 적용하고, 새 지역도 고갈되면 다시 후보를 평가한다.
5. 둘 다 고갈되면 이동을 시작하지 않는다. 진행 중 목적지가 고갈되고 다른 후보도 없으면 현재 위치에서 대기하고 Traveling을 해제한다. 이때 Region 소속은 마지막 commit을 유지한다.

Food가 0이 된 Region은 재생이 없으므로 다시 풍부해지지 않는다. 목적지 재평가를 반복하더라도 A↔B 무한 왕복을 만들지 않는다. 세션 내 스폰은 전체 상한 안에서만 진행하며 빈 지역에서는 중단한다.

이동 중 재스폰·순간이동·새 ID 발급으로 이주를 흉내 내지 않는다. 최소 목표 이동만 기존 엔진 Mass Movement에 연결하며 고품질 Flock/NavMesh를 추가하지 않는다. 여러 Box의 도착 위치는 작은 고정 오프셋으로 나눠 겹침을 줄인다. 복잡한 충돌·군집 분리는 제외한다.

## 4. 책임 경계와 실행 구성

| 부분 | 소유/처리할 데이터 | 구현 방향 |
| :--- | :--- | :--- |
| World 시계/Region | 서버 시간, Phase, Bounds, 연결 관계 | World 계층의 작은 논리 시계. 날씨·태양 시스템 없음 |
| Simulation 조정기 | Food, 이벤트 손실, 스폰 예약, 소비 배분, 집계 | Server/Standalone 전용. 한 실행 주체가 시각과 StepId 제공 |
| Mass | 나이·섭취 예정 시각·Region·Travel·Transform | 개체별 Fragment. 요청만 기록하고 공유 Food는 직접 변경하지 않음 |
| Network | 시계 요약, Region Summary, 관련 Box 프록시 | 기존 GameState 및 MassReplication 재사용. Subsystem 자체 복제 금지 |
| Debug 표시 | Phase/남은 시간, Food/Population, 이주 표시 | 상태 읽기만 수행. Client는 복제 결과를 사용 |

서버 실행 순서:

```text
시간/Phase 갱신 및 예정 이벤트 수집
→ 환경 Food 손실 조정
→ 허용된 웨이브 생성 및 개체 초기화
→ 소비 대상 Entity 평가·요청 버퍼 기록
→ Region별 소비 배분·고갈 상태 확정
→ Migration 목적지/도착 평가 → 최소 이동
→ 동일 완료 상태에서 Population 집계
→ 저주기 요약 게시 / Mass 프록시 갱신 / Box 표시
```

각 단계의 구체적 Mass Phase와 Deferred 반영 순서는 구현 시 엔진 실행 순서에 맞춰 명시한다. Entity 생성/태그 변경은 안전한 조정 경계와 Deferred Command를 사용하며, chunk loop에서 SpawnEntities나 UObject setter를 호출하지 않는다. 이동으로 실제 도착한 상태는 다음 완료 step에서 commit해도 되지만 요약과 로그는 같은 완료 상태를 기준으로 한다.

생태 처리는 0.25초 단위로 due 시각을 확인하고 매 프레임 이동은 분리한다. 저프레임에서 소비/이벤트가 누락되지 않도록 경과 시각 순서로 처리하고 catch-up 양을 제한한다. catch-up 때도 상한·고갈 규칙을 다시 확인하고 같은 이벤트를 재실행하지 않는다.

Population은 Alive Entity를 읽어 계산한다. 이벤트/이주만으로 개체는 제거되지 않으며 `Alive(t) = 초기 생성 수 + 성공한 추가 Spawn 수`다. 동일 snapshot에서 모든 Region Population 합과 Alive 수가 일치해야 한다. 이주 중 개체는 출발 Region에 1회 포함한다.

기존 `mass.UseProcessingQueue=0` 및 World별 Template/Bubble 초기화 순서를 유지한다. Client Proxy에는 서버 이동·소비 query의 필수 구성요소를 넣지 않아 Client가 Food·이주를 독립적으로 결정하지 못하게 한다.

## 5. 화면에서 확인할 결과

- 기존 Box 형태를 유지한다. 원한다면 출발 Region별 색상과 이동 중 화살표만 추가하며 Mesh/Anim 작업은 하지 않는다.
- A/B Bounds와 RegionId를 표시하고 각 지역에 `Food`, `Population`, `Traveling` 수를 표시한다.
- 화면 한쪽에 `Day/Night`, Phase 잔여 시간, CycleId를 표시한다. 시계 자체는 Server에서만 진행한다.
- 이벤트 시각에 `DayEvent: A Food -X`와 같이 실제 감소량을 보여 주어 정기 소비와 구분한다.
- Client는 GameState의 저주기 요약 및 M2 관련 프록시에서 표시한다. 서버 debug draw가 자동으로 Client에도 나타난다고 가정하지 않는다.
- 관심 영역 밖의 개체는 Client에서 보이지 않을 수 있으므로, 우선 전체 관찰은 Standalone/Host 카메라로 수행하고 Client에서는 관련 Box 결과를 확인한다.

Food/Population 및 시계 요약은 1초 간격으로 게시하는 것으로 시작한다. 서버 상태와 동일 revision의 요약을 비교하며 화면의 지연된 값으로 실시간 보존 오류를 판정하지 않는다. 상세 UI와 개체별 Energy 복제는 필요 없다.

## 6. 구현 순서와 완료 조건

| 순서 | 작업 | 해당 작업의 완료 조건 |
| :--- | :--- | :--- |
| 1 | 기존 M2 맵/EntityConfig 확인, 2개 Region 초기화, 재생 0, 기본값 정리 | A/B 모두 준비 후 시작. 각 8개 Box, 고유 ID, 유효 Runtime Index |
| 2 | 서버 낮밤 시계와 상한이 있는 반복 Spawn | Day/Night 주기가 다르게 동작. 전환·재시작·늦은 접속으로 중복 생성 없음 |
| 3 | 개체별 존재 시간·소비 일정과 Region batch 차감 | 생성 20초 전 소비 없음, 이후 10초 주기 소비. 순서와 dt에 무관하게 보존 |
| 4 | Day/Night Food 손실 이벤트 | Phase당 1회. Food 즉시 감소, 0 미만 없음, 소비 로그와 구분 |
| 5 | 고갈→이주→도착 commit, 양쪽 고갈 대기 | 동일 ID Box 실제 이동, 출발/도착 Population 일치, 왕복 진동 없음 |
| 6 | Box 디버그 표시, Region/시계 Summary 복제 | 화면에서 원인·결과 확인. Client에 같은 권위 결과 및 Late Join 상태 전달 |
| 7 | 자동화·PIE 회귀·UBT·재현 문서 | 아래 시나리오별 성공 기록. Source 변경마다 Editor 빌드 성공 |

위 작업 항목을 세부 문서의 M3.1(1~2) → M3.2(3~4) → M3.3(5~7)으로 진행한다. 각 인과관계를 단독 fixture로 먼저 검증하고 다음 단계에 전달한다. 초기 프로토타입을 교차 작성할 수는 있지만 공식 완료 판단은 각 세부 문서의 순서와 종료 기준을 따른다.

## 7. 검증용 설정과 합격 기준

복잡한 수식 없이 원인을 확인할 수 있도록 다음 preset을 둔다. 수치는 개발 편의를 위한 제안이며, 웨이브/이벤트 on/off는 테스트 설정이다.

| 시나리오 | 설정 | 기대 결과 |
| :--- | :--- | :--- |
| 소비만으로 고갈 | A Food 24, B 400, 각 8마리. 추가 Spawn/이벤트 off | A는 20/30/40초에 각 8 소비하여 40초에 0. 다음 이주 판단에서 8마리 B로 이동 |
| 이벤트만으로 고갈 | A Food 40, B 400. Day 이벤트 15초에 A -40. 추가 Spawn off | 첫 섭취 20초 전 A 고갈, A 개체 이동. 환경 이벤트가 원인임을 확인 |
| 낮밤 반복 스폰 | 두 지역 Food 충분, 손실 이벤트 off | 낮 30초/4마리, 밤 20초/6마리. 경계 중복 없음, 128 상한 유지 |
| 밤 이벤트 | B Food 40, A 400. Night 진입 15초 후 B -40. 소비/추가 Spawn off | 밤 이벤트로 B 고갈, B→A 이동. Day 이벤트는 해당 fixture에서 off |
| 실제 소비+이벤트 통합 | A 60, B 400. Day 25초 A -50, Night 15초 B -50. 주야 Spawn on | 소비/이벤트를 구분해 기록. A 고갈 후 동일 ID 이동, B 잔량에 따라 추가 소비·고갈 |
| 양쪽 고갈 | A/B 잔량 모두 0, 살아있는 개체 유지 | 신규 Spawn 없음, 먹이/이주 중복 없음, 목적지 없는 개체 대기 |
| 프레임/시간 경계 | 30/60 FPS 및 일시적 긴 frame | 경과 시각별 이벤트/소비가 한 번만 적용. 스폰 상한/보존 유지 |
| 플레이어 없음 | Pawn 생성과 플레이어 입력에 의존하지 않는 실행 | Region Food/Population/이주 결과가 독립적으로 진행 |
| M2 회귀 / Late Join | Host+Client, Bubble 진입·이탈, 이주 후 접속 | 현재 Transform/RegionId/Box/지역 요약 수신. Late Join이 스폰 시계를 재시작하지 않음 |

검증 우선순위는 다음과 같다.

1. 1~2분 안에 소비 또는 이벤트에 의한 고갈과 이주를 각각 관찰한다.
2. 3~5회 낮밤 전환에서 이벤트/스폰 중복과 Population 오류를 검사한다.
3. 최대 128개체로 15분 실행하여 둘 다 고갈된 뒤에도 Timer/이동/스폰이 폭주하지 않는지 확인한다.
4. M3 잔여 생태 단계에서 생존 개체가 유지되는 조건의 256마리·30분 검증을 다시 설계한다. 재생 없는 terminal 상태의 안정성 검증과 지속 생태 안정성 검증을 구분한다.

로그에는 SimTime/Cycle/Phase, 성공 Spawn 수, Region별 Food·Population, 이벤트 실제 손실, 요청/지급 합, Migration 시작/도착, StableAgentId를 남긴다. Food 보존은 `FoodBefore - EventLoss - GrantedTotal = FoodAfter`로 확인하고 부동소수점 허용 오차를 명시한다.

## 8. 개발량 추정

UE 5.8 Mass C++ 경험이 있는 개발자 1명, M2 복제와 기존 Box가 정상 동작하고 평면 테스트 맵을 사용할 수 있다는 전제다. 1인일은 집중 개발 8시간이며 신규 학습·세션 장애 조사·외부 대기는 포함하지 않는다. 소스 기반 추정으로 런타임 및 에셋 검증 전 오차가 있다.

| 작업 | 예상 인일 |
| :--- | :--- |
| 기존 설정 확인, 다중 Region 초기화, 관찰 fixture | 0.5~1 |
| 논리 낮밤 시계 + 반복 Spawn/상한/중복 방지 | 1.5~2.5 |
| 개체별 소비 일정 + batch 차감 + 주야 이벤트 | 1.5~2 |
| 실제 Migration 이동/도착/대기 + Population | 2~3 |
| Box 디버그 표시 + Region/시계 Summary 연결 | 1~1.5 |
| 핵심 자동화, PIE/Late Join 회귀, UBT, 기록 | 1.5~2.5 |
| **관찰 단계 합계** | **8~12.5인일, 일정 계획은 8~13인일(64~104시간)** |

세 마일스톤을 순서대로 완료하는 경우 **소비 고갈→Box 이주가 보이는 최초 Standalone 데모는 누적 5.5~8.5인일(계획상 6~9인일)**로 예상한다. 이전 4~6인일 추정은 초기화·소비·이동만 먼저 교차 구현하는 프로토타입 기준이었다. 현재는 주야 스폰과 이벤트의 선행 검증을 포함하므로 중간 데모 시점만 조정하며, 전체 관찰 범위의 8~13인일 추정은 유지한다. 데모 시점은 전체 완료 일정에 추가 합산하지 않는다.

현재 구조에서 예상되는 작업은 신규 런타임 타입/Processor/fixture 약 8~12개 C++ 파일, 기존 약 6~10개 C++ 파일의 연결 수정, 기존 EntityConfig·테스트 맵 설정, 핵심 테스트와 검증 문서다. 파일 수는 구현 분할에 따라 바뀌며 비용 산정의 확정 수치는 아니다. 최소 이동을 기존 Movement에 연결하는 부분이 가장 큰 불확실성이다.

- M2 Box/Client 템플릿/Movement 연결 또는 World Partition 로딩 문제가 발견되면 **추가 1~3인일**을 별도 반영한다.
- 낮밤 태양 연출, NavMesh, 복잡한 Flock, Actor 전투, 출생 특성 결정은 추정에 포함하지 않는다.
- **M3 전체 종료를 위한 Energy/기아·사망/V1 Observation·Utility/추가 안정성 검증은 이후 3~5인일**을 별도 예상한다. 합산 계획은 11~18인일이며 새 범위가 추가되면 다시 추정한다.
- Food 재생은 기존 함수가 있으므로 후속 작업은 새 재생 알고리즘 전체 개발보다 호출·설정·생태 밸런스·검증에 가깝다. 이번 관찰 단계 일정에는 포함하지 않는다.

## 9. 이후 연결과 최종 범위 관리

관찰 단계에서는 Vitals 값을 유지하되 고정 소비를 배고픔 계산으로 위장하지 않는다. 다음 M3 작업에서 실제 섭취량을 Energy에 연결하고 기본 소모·기아 피해·사망·프록시 제거를 구현한다. V1 7차원 관측과 Utility를 연결할 때 Food 관련 입력은 현재 균일 지역 자원 모델에 맞춰 문서화하고 관측 차원·순서·정규화는 보존한다.

시간 기반 소비는 디버그 설정으로 남길 수 있으나 일반 생태 경로와 동시에 켜 두지 않는다. 새 정책을 붙여도 이미 만든 Food 조정·Migration·집계의 상태 소유권은 유지한다. 전체 M3의 재생 포함 여부는 이번 보류를 반영해 종료 시 범위표에 명시한다.

플레이어 행동으로 출생 특성을 정하는 기능은 영향 누적 기간, 특성 적용 대상, 기존 개체 변경 여부, 종별 기본값, 스폰 시점의 고정 및 정책 호환성을 별도로 정의한 후 구현한다. 이를 낮밤 Spawn Scheduler나 Legacy Evolution에 임시로 끼워 넣지 않는다.

관찰 단계 완료 체크리스트:

- [ ] A/B 두 지역과 초기 개체가 모두 생성되며 플레이어 없이 진행된다.
- [ ] Day/Night 주기에 따라 추가 Spawn이 일어나고 상한과 고갈 제한을 지킨다.
- [ ] 생성 후 유예 시간과 소비 주기가 개체별로 적용된다.
- [ ] Food 재생은 0이며 자동 회복/Phase 초기화가 없다.
- [ ] 낮·밤 Food 감소 이벤트가 각각 한 번씩 발생한다.
- [ ] 소비와 이벤트에 의한 고갈을 각각 재현한다.
- [ ] 동일 ID의 Box가 실제로 다른 Region으로 이동하며 도착 후 소속/소비가 바뀐다.
- [ ] 양쪽 고갈 시 대기하며 이주·스폰이 폭주하지 않는다.
- [ ] Alive 수, 생성 수, Region Population 및 Food 보존이 일치한다.
- [ ] Client 요약·관련 프록시·Late Join이 정상이며 Client가 생태를 계산하지 않는다.
- [ ] 변경 후 UBT 빌드 및 핵심 테스트·PIE 기록을 확보한다.

## 10. 관련 문서

- [MVP 로드맵](../README.md)
- [M3 원래 범위와 현재 우선순위](M3_ECOLOGY_SIMULATION_CORE.md)
- [M2 네트워크 수직 슬라이스](../M2/M2_MASS_NETWORK_VERTICAL_SLICE.md)
- [Network Authority Contract](../../Network/MASS_NETWORK_AUTHORITY_CONTRACT.md)
- [Mass Processor 실행 순서](../../Mass/MASS_PROCESSOR_ORDER.md)
- [Policy Contract V1](../../RL_Policy/POLICY_CONTRACT_V1.md)
