# PPO + MassEntity 기반 동적 생태계 종합 아키텍처 (PPO & Mass Dynamic Ecosystem)

> 기준 엔진: **Unreal Engine 5.8**  
> 모듈: `AdaptiveEcosystem`  
> 상태: **Active Architecture Specification**  
> 관련 핵심 문서: [POLICY_CONTRACT_V1.md](POLICY_CONTRACT_V1.md), [MASS_PROCESSOR_ORDER.md](MASS_PROCESSOR_ORDER.md), [RL_TRAINING_PIPELINE.md](RL_TRAINING_PIPELINE.md)

---

## 1. 아키텍처 개요 및 패러다임 전환

본 프로젝트의 목표는 **대규모 개체(MassEntity)의 군집 행동, 지역 자원 및 포식 역학, 환경 변화가 상호작용하는 완전한 동적 생태계 피드백 루프(Closed-Loop Dynamic Ecosystem)**를 구축하는 것입니다.

기존의 세대 교체형 LLM Trait 변이(BodyScale, Generation 기반 Profile Commit) 구조를 완전히 배제하고, **Python에서 PPO(Proximal Policy Optimization)로 사전 강화학습된 고수준 행동 정책을 Unreal C++에서 네이티브 추론하여 MassFlock 조향과 연결**합니다.

```text
┌────────────────────────────────────────────────────────┐
│ 1. WORLD / REGION LAYER                                │
│    - AEcologyRegion (Bounds, Spatial Partitioning)     │
│    - FRegionEnvironmentState (Rainfall, Temp, DayNight)│
│    - FRegionEcologyState (FoodAmount, Capacity, Regen) │
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
                            │ Weights: forage, cohesion, flee, cover
                            ▼
┌────────────────────────────────────────────────────────┐
│ 5. MASS FLOCK & STEERING LAYER                         │
│    - MassNavigation HashGrid Spatial Neighbor Lookup   │
│    - Force Blending: Separation + Alignment + Cohesion │
│    - PPO-Driven Forces: Forage, Flee, Cover            │
└───────────────────────────┬────────────────────────────┘
                            │ Movement & Consumption
                            ▼
┌────────────────────────────────────────────────────────┐
│ 6. INTERACTION, LIFECYCLE & REGIONAL FEEDBACK          │
│    - Food Consumption -> Energy Gain                   │
│    - Starvation / Predation -> Entity Death            │
│    - Resource Depletion -> Migration Decision          │
│    - Kill Events -> Region PredationHistory Increase   │
└───────────────────────────┬────────────────────────────┘
                            │ Feedback
                            └────────────────────────────↺
```

---

## 2. 데이터 소유권 및 계층별 책임

| 계층 | 주요 클래스 / 구조체 | 소유 데이터 | 책임 및 권한 |
| :--- | :--- | :--- | :--- |
| **World / Region** | `AEcologyRegion` | 지리적 볼륨, 위치, `FRegionEnvironmentState` | 물리 공간 제공, 날씨/낮밤 파라미터 홀딩. 논리 생태를 결정하지 않음. |
| **Ecology Runtime** | `UEcologySimulationSubsystem` | `FRegionEcologyState`, `PredationHistory`, 자원 총량 | 지역 자원 소모/재생 총괄, 포식 사건 집계 및 지수 감쇠, 개체군 카운팅. |
| **Mass Entities** | `FEcoIdentityFragment`<br>`FEcoVitalsFragment`<br>`FEcoObservationFragment`<br>`FEcoPolicyOutputFragment` | `StableAgentId`, `HP`, `Energy`, 관측값 7개, 정책 출력값 4개 | 대규모 개체의 논리적 본체(Source of Truth). |
| **Shared Species Config** | `FEcoSpeciesSharedFragment` | `BaseMoveSpeed`, `EnergyDecayRate`, `ViewDistance`, `FOV` | 종(Species) 단위 불변/저주기 공유 속성. |
| **Creature Actor** | `ACreatureCharacter` | Mesh, Anim, Particle, 충돌체 | Mass 논리 개체의 시각적 표현(Representation). 런타임 권위 없음. |

---

## 3. 핵심 규칙 및 가이드라인

1. **Shared Fragment 오용 금지**:
   - PPO의 정책 출력(forage, cohesion, flee_dist, cover)은 개체마다 고유한 값입니다.
   - 이를 `FMassSharedFragment`에 넣으면 Archetype churn 및 메모리 파편화가 발생하므로, 반드시 `FEcoPolicyOutputFragment`(개체별 Fragment)에 저장합니다.
2. **비동기/스레드 안전성 (Thread Safety)**:
   - Mass Entity 루프 내부에서 `AEcologyRegion`이나 `UEcologySimulationSubsystem`의 UObject 프로퍼티를 직접 수정하지 않습니다.
   - 자원 소비 요청(Food Consumption Request)은 Mass Processor에서 버퍼링하거나 Deferred Command를 통해 프레임 종료 시점에 일괄 처리(Reconciliation)합니다.
3. **PPO와 C++ 간 Sim-to-Sim 일치**:
   - Python Gym 환경(`Tools/RL`)에서 관측하는 순서/정규화 공식과 C++ Native Inference에서 계산하는 순서/공식이 100% 동일해야 합니다.
4. **Utility AI의 역할**:
   - Utility AI는 별도 메인 시스템이 아닌, **PPO 비교군(Baseline)**, **초기 imitation learning 데이터 생성기**, **PPO 실패 시 즉각 전환 가능한 fallback**으로 사용됩니다.
