# Active Runtime / Legacy Boundaries

> 계약 수립: M0 — Architecture & Authority Alignment<br>
> 현재 대조 기준: main `295ac2f` / 2026-09-30. M3 관찰 경로 구현 및 Social Production Integration 진행 중<br>
> 기준 엔진: Unreal Engine 5.8

## 1. Active Runtime 계약

신규 PPO + Mass 경로의 공통 계약과 계층별 상태는 아래 위치를 사용한다. 구현 사실과 목표 경계를 구분한다.

| 책임 | 계약 또는 구현 |
| :--- | :--- |
| 영속 ID와 런타임 인덱스 | `Core/EcoIds.h` |
| World 환경과 권위 생태 상태의 데이터 형식 | `Core/EcoRegionTypes.h` |
| Mass가 버퍼링하고 Ecology가 반영할 이벤트 | `Core/EcoEventTypes.h` |
| Mass에서 Actor/Client로 전달할 읽기 전용 Snapshot | `Core/EcoRepresentationTypes.h` |
| PPO 관측과 행동 | `AI/Policy/EcoPolicyContracts.h` |
| 개체별 논리 상태 | `Mass/EcoMassFragments.h` |
| Social의 Herd / Alarm / Shelter 상태·행동 의도 | `AI/Social/EcoSocialTypes.h`, `EcoSocialFragments.h` |
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
| Persistent Herd / Membership / Alarm / Shelter registry·예약 | Social Fragment + `UEcoHerdSubsystem` / `UEcoShelterSubsystem` | Raw Action을 읽어 ModulatedAction·TargetPosition을 제공. Vitals/자원/이동 적분/복제의 주인이 아님 |
| 최종 속도와 위치 적분 | Steering / Movement 담당 경로 | Social 의도를 소비하는 목표. 현재 PPO 직접 적분과 M3 엔진 이동은 분리됨 |
| 화면 표현과 보간 상태 | Actor / Client Representation | 권위 논리 상태로 역반영하지 않음 |

`FMassEntityHandle`은 저장 또는 복제하지 않는다. `StableAgentId`는 0을 Invalid로 예약하며 Server/Standalone의 `AllocateStableAgentId()`가 발급한다. Region/Species Runtime Index는 현재 World의 hot path에서만 사용한다.

**Herd != Flock**: 논리적 무리와 실제 조향을 구분한다. 목표 연결은 `Policy Raw Action → Social ModulatedAction / TargetPosition → Steering / Movement`다. 현재 Steering은 Raw를 읽는다. 작업 브랜치 `codex/social-threat-integration`에 실제 위협 감지→Alarm을 추가했으며, 목적지 소비·도착·정리는 pending이다. JYU Harness의 고정 ID·Raw Action·직접 Archetype은 production 생명주기 구성의 증거가 아니다.

Herd/Shelter Subsystem은 Client 생성을 제외한다. Detection은 `Server | Standalone`을 명시하며 다른 Social Processor는 같은 엔진 기본값을 상속한다. 작업 브랜치의 Detection/Alarm/Response는 ClientProxy/PendingDeath를 제외하고 Social Trait는 Client 논리 구성을 제외한다. 실제 EntityConfig·에디터 실행 설정·멀티플레이는 별도 검증이 필요하다. 자세한 변경 계약은 [실제 위협 연동](../조연우/SOCIAL_THREAT_ALARM_INTEGRATION.md), main 감사 근거는 [Social CURRENT_STATE](../조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md)를 따른다.

## 4. 권위 변경 흐름

Mass Processor의 병렬 Entity loop는 UObject를 직접 호출하지 않는다. 소비·포식·개체군 집계 결과를 각각 `FEcoFoodConsumptionRequest`, `FEcoPredationEvent`, `FEcoRegionPopulationSnapshot`으로 버퍼링한 뒤 Game Thread reconciliation 단계에서 `UEcologySimulationSubsystem`에 적용하는 것이 목표 계약이다. 현재 M3 Feeding/집계는 GameThread에서 처리하지만 Policy 포획은 별도 격자 EMA에 보고하므로 모든 포식 사건이 Ecology에 통합되었다는 의미는 아니다.

Social MVP의 Subsystem 접근은 GameThread 실행을 전제로 직렬화한다. 예약 제안을 수집·정렬한 뒤 조정 단계에서 commit한다. 이를 worker 병렬 구현 완료로 기록하거나 실행 플래그만 바꾸어 병렬화하지 않는다.

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

