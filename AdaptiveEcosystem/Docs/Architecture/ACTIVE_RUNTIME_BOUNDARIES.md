# Active Runtime / Legacy Boundaries

> 기준 Milestone: M0 — Architecture & Authority Alignment  
> 기준 엔진: Unreal Engine 5.8

## 1. Active Runtime 계약

신규 PPO + Mass 경로는 아래 헤더만 공통 계약으로 사용한다.

| 책임 | 계약 또는 구현 |
| :--- | :--- |
| 영속 ID와 런타임 인덱스 | `Core/EcoIds.h` |
| World 환경과 권위 생태 상태의 데이터 형식 | `Core/EcoRegionTypes.h` |
| Mass가 버퍼링하고 Ecology가 반영할 이벤트 | `Core/EcoEventTypes.h` |
| Mass에서 Actor/Client로 전달할 읽기 전용 Snapshot | `Core/EcoRepresentationTypes.h` |
| PPO 관측과 행동 | `AI/Policy/EcoPolicyContracts.h` |
| 개체별 논리 상태 | `Mass/EcoMassFragments.h` |
| 지역 자원과 집계 상태의 권위 소유자 | `Ecology/EcologySimulationSubsystem.*` |
| 활성 복제 DTO | `Network/EcologyNetworkTypes.h` |

Active Runtime 파일은 `Core/EcoDataContracts.h` 또는 `Evolution/`을 include하지 않는다.

## 2. Legacy 경계

다음 경로는 기존 에셋과 실험을 빌드 가능한 상태로 보존하기 위한 Legacy 영역이다.

- `Evolution/`
- `Ecology/EcologyServerSubsystem.*`
- `Debug/EcologyBootstrapTestActor.*`
- `Network/EcologyLegacyNetworkTypes.h`
- `Core/EcoDataContracts.h`의 Trait, Generation, Evolution Proposal 계약
- `AEcologyRegion::ApplyVegetationConsumption()`과 `ApplyVegetationRegrowth()`
- Evolution Profile을 적용하는 기존 Creature Trait 경로

Legacy Evolution Subsystem은 Project Settings의 `Adaptive Ecosystem > Legacy > Enable Legacy Evolution Subsystem`을 명시적으로 켠 경우에만 Server/Standalone 게임 월드에 생성된다. 설정 변경 후 PIE를 다시 시작해야 한다. Debug Actor의 자동 실행도 기본적으로 꺼져 있다.

## 3. 상태 소유권

| 상태 | 유일한 권위 소유자 | 다른 계층의 역할 |
| :--- | :--- | :--- |
| Bounds, 온도, 습도, 강우, 낮/밤, 날씨 | `AEcologyRegion` / World | Ecology와 Mass가 읽음 |
| FoodAmount, FoodCapacity, PredationHistory, 지역 집계 | `UEcologySimulationSubsystem` | Mass는 이벤트와 집계 Snapshot을 버퍼링하여 전달 |
| StableAgentId, HP, Energy, Region, Policy 상태 | Mass Entity Fragment | Representation과 Network는 Snapshot만 읽음 |
| 화면 표현과 보간 상태 | Actor / Client Representation | 권위 논리 상태로 역반영하지 않음 |

`FMassEntityHandle`은 저장 또는 복제하지 않는다. `StableAgentId`는 0을 Invalid로 예약하며 Server/Standalone의 `AllocateStableAgentId()`가 발급한다. Region/Species Runtime Index는 현재 World의 hot path에서만 사용한다.

## 4. 권위 변경 흐름

Mass Processor의 병렬 Entity loop는 UObject를 직접 호출하지 않는다. 소비·포식·개체군 집계 결과를 각각 `FEcoFoodConsumptionRequest`, `FEcoPredationEvent`, `FEcoRegionPopulationSnapshot`으로 버퍼링한 뒤 Game Thread reconciliation 단계에서 `UEcologySimulationSubsystem`에 적용한다.

범용 상태 덮어쓰기 API는 제공하지 않는다. 초기 등록, Food 소비, 포식 기록, Population 집계 갱신은 목적이 드러나는 API로 분리한다.

## 5. 에디터 수동 확인

자동화 테스트 대신 M0에서는 다음을 PIE로 확인한다.

1. Project Settings에서 Legacy 설정이 꺼져 있고 `AEcologyBootstrapTestActor.bAutoRunOnBeginPlay`가 false인지 확인한다.
2. Standalone 또는 Listen Server PIE에서 `UEcologySimulationSubsystem`이 존재하고 `UEcologyServerSubsystem`은 존재하지 않는지 확인한다.
3. Client PIE에서 `UEcologySimulationSubsystem`이 생성되지 않는지 확인한다.
4. `Forest_A`의 EnvironmentState를 변경해도 SimulationSubsystem의 FoodAmount가 바뀌지 않는지 확인한다.
5. Food 소비 요청 후 FoodAmount가 0 아래로 내려가지 않고, Simulation Tick 후 FoodCapacity를 넘지 않는지 확인한다.
6. Predation Event를 반복 적용해도 PredationHistory가 1을 넘지 않고 Tick에 따라 0 방향으로 감쇠하는지 확인한다.
7. Population Snapshot 적용 시 Population은 0 이상, AverageEnergy는 0~1 범위로 보정되는지 확인한다.
8. 발급된 StableAgentId가 1부터 시작하며 0이 반환되지 않는지 확인한다.
9. Legacy 검증이 필요할 때만 설정을 켜고 PIE를 재시작한 후 Debug Actor의 Call In Editor/수동 실행 기능을 사용한다.

