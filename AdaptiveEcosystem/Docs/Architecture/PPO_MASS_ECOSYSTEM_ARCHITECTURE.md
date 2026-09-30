# PPO + MassEntity 기반 동적 생태계 종합 아키텍처 (PPO & Mass Dynamic Ecosystem)

> 기준 엔진: **Unreal Engine 5.8**  
> 모듈: `AdaptiveEcosystem`  
> 상태: **Target Architecture + Current Implementation Gap**<br>
> Source 감사 기준: `main` / `295ac2f` / 2026-09-30 (빌드·PIE 재실행 없음)<br>
> 관련 핵심 문서: [POLICY_CONTRACT_V1.md](../RL_Policy/POLICY_CONTRACT_V1.md), [Social CURRENT_STATE](../조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md), [MASS_PROCESSOR_ORDER.md](../Mass/MASS_PROCESSOR_ORDER.md), [RL_TRAINING_PIPELINE.md](../RL_Policy/RL_TRAINING_PIPELINE.md)

---

## 1. 아키텍처 개요 및 패러다임 전환

본 프로젝트의 목표는 **대규모 개체(MassEntity)의 군집 행동, 지역 자원 및 포식 역학, 환경 변화가 상호작용하는 완전한 동적 생태계 피드백 루프(Closed-Loop Dynamic Ecosystem)**를 구축하는 것입니다.

신규 경로는 세대 교체형 LLM Trait 변이에 의존하지 않습니다. 기존 Legacy 코드는 별도로 보존합니다. **Python에서 학습한 고수준 행동 정책을 Unreal C++에서 네이티브 추론하고, Social의 행동 보정·은신처 목적지를 단일 Steering/Movement 경로로 전달**하는 구조가 목표입니다.

### 1.1 Target Architecture

아래는 목표 폐루프이며 전체 연결이 완료되었다는 뜻이 아닙니다. MassFlock은 초기 조향 참조이고 현재 PPO 경로는 자체 격자와 `EcoPolicy::Steer`를 사용합니다.

```text
┌────────────────────────────────────────────────────────┐
│ 1. WORLD / REGION LAYER                                │
│    - AEcologyRegion (Bounds, Spatial Partitioning)     │
│    - FRegionEnvironmentState (Rainfall, Temp, DayNight)│
└───────────────────────────┬────────────────────────────┘
                            │ Environment & Resources
                            ▼
┌────────────────────────────────────────────────────────┐
│ 2. ECOLOGY RUNTIME LAYER                               │
│    - UEcologySimulationSubsystem (WorldSubsystem)      │
│    - Authoritative Resource Reconciliation             │
│    - Predation History Accumulation & Decay            │
│    - Population Aggregation & Regional Metrics         │
└───────────────────────────┬────────────────────────────┘
                            │ Ecology Context
                            ▼
┌────────────────────────────────────────────────────────┐
│ 3. MASS LOGICAL CREATURE LAYER                         │
│    - Logical Source of Truth (StableAgentId, Vitals)   │
│    - FEcoObservationFragment (7 Normalized Features)   │
│    - FEcoPolicyOutputFragment (4 Behavior Weights)     │
└───────────────────────────┬────────────────────────────┘
                            │ Observations
                            ▼
┌────────────────────────────────────────────────────────┐
│ 4. BEHAVIOR POLICY INFERENCE LAYER                     │
│    - Shared Neural Network (7 -> 64 -> 64 -> 4)        │
│    - Unreal C++ Native Forward Inference (Deterministic)│
│    - Utility Baseline Toggle & Fallback                │
└───────────────────────────┬────────────────────────────┘
                            │ Raw Action: forage, cohesion, flee_dist, cover
                            ▼
┌────────────────────────────────────────────────────────┐
│ 5. SOCIAL BEHAVIOR RUNTIME                            │
│    - Persistent Herd / Membership / Aggregate         │
│    - Threat / Alarm / Social Response                 │
│    - Shelter LOS / Score / Slot Reservation / Release │
└───────────────────────────┬────────────────────────────┘
                            │ ModulatedAction / TargetPosition
                            ▼
┌────────────────────────────────────────────────────────┐
│ 6. STEERING / MOVEMENT                                │
│    - Consume behavior intent / choose movement goal   │
│    - Local flock steering / path / arrival execution  │
│    - One final velocity / Transform writer per Entity │
└───────────────────────────┬────────────────────────────┘
                            │ Movement & Consumption
                            ▼
┌────────────────────────────────────────────────────────┐
│ 7. INTERACTION, LIFECYCLE & REGIONAL FEEDBACK          │
│    - Food Consumption -> Energy Gain                   │
│    - Starvation / Predation -> Entity Death            │
│    - Resource Depletion -> Migration Decision          │
│    - Kill Events -> Region PredationHistory Increase   │
└───────────────────────────┬────────────────────────────┘
                            │ Feedback
                            └────────────────────────────↺
```

### 1.2 Current Implementation Gap

| 경로 | 현재 Source | 미통합 범위 |
| :--- | :--- | :--- |
| World / Ecology / Mass M3 | 권위 시계·스폰·Food 소비/손실·고갈 이주·집계·요약 복제 구현 | 지급량→Energy/HP, 정식 기아/사망, 전체 폐루프 |
| PPO / Utility | Native 추론·자체 이웃 격자·관측·속도 조향 구현. Dummy Food/Cover와 별도 격자 피식 EMA 사용 | 실제 Ecology/Shelter Provider, 계약 수치 정합성, 생명주기 피드백 |
| Social | Herd/Alarm/Shelter MVP 구현. 작업 브랜치에서 실제 포식자/Actor 위협 감지를 추가. Raw를 보존하여 ModulatedAction을 계산하고 예약 목적지를 기록 | production EntityConfig/JYU/Client 검증, 행동·목적지 소비자, Moving/Occupied, Death/Despawn/Migration 해제 |
| Steering / Movement | PPO Steering은 Raw Action을 사용하여 Transform을 직접 적분. M3 이주는 DesiredVelocity→엔진 ApplyMovement | 공통 Entity·우선순위·단일 writer·명시적 Processor handoff |
| Network / Representation | Bubble에 PositionYaw/StableAgentId/SpeciesId/RegionId, GameState에 완료 지역 요약 전달 | 실제 플레이어 상호작용·사망·Social 상태 표현에 대한 별도 검증 |

Source 근거: [PPO Processors](../../Source/AdaptiveEcosystem/AI/Policy/EcoBehaviorProcessors.cpp), [Providers](../../Source/AdaptiveEcosystem/AI/Policy/EcoWorldProviders.cpp), [M3 Lifecycle](../../Source/AdaptiveEcosystem/Mass/EcoMassLifecycleSubsystem.cpp), [Feeding](../../Source/AdaptiveEcosystem/Mass/EcoMassFeeding.cpp), [Migration](../../Source/AdaptiveEcosystem/Mass/EcoMassMigration.cpp), [Bootstrap 구성 가드](../../Source/AdaptiveEcosystem/Mass/EcoMassNetworkBootstrap.cpp).

M3 Bootstrap은 PPO Herbivore/Custom/Spring Movement 혼용을 거부하고, Herbivore Trait는 CustomMovement Tag로 엔진 이동을 제외합니다. 따라서 현 기본 경로의 이중 위치 적분을 단정하지 않습니다. 통합 시 이 분리를 어떻게 유지/조정할지 먼저 계약으로 정해야 합니다. 실행 순서는 [Mass 문서](../Mass/MASS_PROCESSOR_ORDER.md), Social의 검증 범위와 현재 우선순위는 [CURRENT_STATE](../조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md)를 따릅니다. M3 관찰 경로 구현을 M3 전체 또는 M4/M5 완료로 간주하지 않습니다.

---

## 2. 데이터 소유권 및 계층별 책임

| 계층 | 주요 클래스 / 구조체 | 소유 데이터 | 책임 및 권한 |
| :--- | :--- | :--- | :--- |
| **World / Region** | `AEcologyRegion` | 지리적 볼륨, 위치, `FRegionEnvironmentState` | 물리 공간 제공, 날씨/낮밤 파라미터 홀딩. 논리 생태를 결정하지 않음. |
| **Ecology Runtime** | `UEcologySimulationSubsystem` | `FRegionEcologyState`, `PredationHistory`, 자원 총량 | 지역 자원 소모/재생 총괄, 포식 사건 집계 및 지수 감쇠, 개체군 카운팅. |
| **Mass Entities** | `FEcoIdentityFragment`<br>`FEcoVitalsFragment`<br>`FEcoObservationFragment`<br>`FEcoPolicyOutputFragment` | `StableAgentId`, `HP`, `Energy`, 관측값 7개, 정책 출력값 4개 | 대규모 개체의 논리적 본체(Source of Truth). |
| **Behavior Policy** | `UEcoPolicyProcessor`, `EcoPolicy::RunPolicy/RunUtilityPolicy` | Raw Action, 학습·수치 계약 | 개체가 무엇을 하고 싶은지 결정. RL 담당 영역. |
| **Social Runtime** | `UEcoHerdSubsystem`, `UEcoShelterSubsystem`, Social Fragments/Processors | Herd identity/context, Alarm, ModulatedAction, Shelter 예약/목적지 | 사회적 문맥을 해석하고 행동 의도를 구체화. 자원/Vitals/이동 적분/복제 transport의 주인이 아님. |
| **Steering / Movement** | 현재 `UEcoSteeringProcessor`, Migration + 엔진 Movement | 최종 속도·Transform, 경로·도착 실행 | 목적지까지 어떻게 이동할지 실행. production handoff는 미통합. |
| **Shared Species Config** | `FEcoSpeciesSharedFragment` | `BaseMoveSpeed`, `EnergyDecayRate`, `ViewDistance`, `FOV` | 종(Species) 단위 불변/저주기 공유 속성. |
| **Creature / Client Representation** | 엔진 Representation / Actor / Client Bubble | Mesh/Anim, 수신 Transform 및 시각 상태 | 활성 Mass 경로의 표현자. Legacy Creature 코드 전체가 이미 이 경계로 전환되었다는 뜻은 아님. |

**Herd != Flock**: Herd는 지속적인 논리적/사회적 무리이며, Flock/Steering은 실제 이동 행동입니다. Social이 Raw Action을 덮어쓰거나 Movement 담당의 저수준 조향을 소유하지 않습니다.

---

## 3. 핵심 규칙 및 가이드라인

1. **Shared Fragment 오용 금지**:
   - PPO의 정책 출력(forage, cohesion, flee_dist, cover)은 개체마다 고유한 값입니다.
   - 이를 `FMassSharedFragment`에 넣으면 Archetype churn 및 메모리 파편화가 발생하므로, 반드시 `FEcoPolicyOutputFragment`(개체별 Fragment)에 저장합니다.
2. **비동기/스레드 안전성 (Thread Safety)**:
   - Mass Entity 루프 내부에서 `AEcologyRegion`이나 `UEcologySimulationSubsystem`의 UObject 프로퍼티를 직접 수정하지 않습니다.
   - 자원 소비 요청(Food Consumption Request)은 Mass Processor에서 버퍼링하거나 Deferred Command를 통해 프레임 종료 시점에 일괄 처리(Reconciliation)합니다.
3. **PPO와 C++ 간 Sim-to-Sim 일치**:
   - 실제 Python 학습 환경은 `herbivore_rl/`입니다. 초기 `Tools/RL`/Aquarium 계획과 구분합니다. 관측 순서·정규화·조향의 Source 및 생성 헤더를 V1 문서와 대조하고, 알려진 차이를 보고하며 Golden Vector로 검증합니다.
4. **Utility AI의 역할**:
   - Utility AI는 별도 메인 시스템이 아닌, **PPO 비교군(Baseline)**, **초기 imitation learning 데이터 생성기**, **PPO 실패 시 즉각 전환 가능한 fallback**으로 사용됩니다.
   - 현재 `eco.UseLearnedPolicy`는 PPO/Utility 선택 스위치입니다. 자동 실패 감지·fallback의 production 완료를 전제하지 않습니다.
5. **Server / Standalone 권위**:
   - Herd/Shelter Subsystem은 Client 생성을 제외하고 Social Processor는 UE 5.8 기본 `Server | Standalone`을 상속합니다. 기본 자동 실행은 서버 권위입니다. 에디터 실행 설정 override·Authority/Alive/ClientProxy query·Client Trait/EntityConfig는 통합 단계에서 확인합니다.
6. **현재 다음 작업**:
   - Production Integration: 실제 위협→Alarm, Raw→ModulatedAction→Steering, Shelter 목적지→이동, 도착·점유·예약 유지와 생명주기 해제, end-to-end 검증. Merge/Split·multi-hop gossip·ORCA·자동 Cover 생성·새 PPO 차원은 Deferred입니다.
