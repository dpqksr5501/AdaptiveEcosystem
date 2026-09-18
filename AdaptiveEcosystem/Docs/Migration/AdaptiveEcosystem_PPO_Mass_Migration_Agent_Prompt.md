# AdaptiveEcosystem — PPO + MassEntity 동적 생태계 아키텍처 전환 Agent Prompt

> 대상 저장소: `dpqksr5501/AdaptiveEcosystem`  
> 기준 브랜치: `main`  
> Unreal Engine: **5.8**  
> 목적: 기존 **Server + LLM 기반 Trait Evolution 구조**를 폐기/격리하고, **MassEntity 기반 동적 생태계 + Python PPO 학습 + Unreal C++ Policy Inference + MassFlock 조향** 구조로 단계적으로 전환한다.

---

## 0. 작업의 핵심

이 작업은 `LLM -> PPO` 이름 치환이 아니다.

현재 저장소의 중심 흐름은 다음과 같다.

```text
Environment / Player Pressure
→ Evolution Context
→ LLM / Rule Provider
→ Trait Delta Proposal
→ Validator
→ Species Evolution Profile
→ Creature Actor에 Trait 적용
```

새 구조의 중심은 다음이다.

```text
World / Weather / Day-Night / Resource
                ↓
          Region Ecology State
                ↓
       Mass Logical Creatures
                ↓
       Per-Agent Observation
                ↓
     Learned PPO Behavior Policy
                ↓
forage / cohesion / flee_dist / cover
                ↓
       Mass Steering / Movement
                ↓
Food Consumption / Survival / Predation
Death / Migration / optional Reproduction
                ↓
Resource / Population / Predation History
                ↓
          Region Ecology State
                ↺
```

**동적 생태계가 본체이고 PPO는 개체 행동 정책을 담당하는 핵심 기술이다.**

한 번에 저장소 전체를 갈아엎지 말고 **컴파일 가능한 작은 단계/PR 단위**로 전환한다.

---

## 1. 반드시 먼저 읽을 파일

코드 수정 전에 저장소를 직접 탐색하고 아래 파일을 읽어라.

### Root

```text
AGENTS.md
README.md
AdaptiveEcosystem/AdaptiveEcosystem.uproject
AdaptiveEcosystem/Source/AdaptiveEcosystem/AdaptiveEcosystem.Build.cs
```

### Docs

```text
AdaptiveEcosystem/Docs/아키텍처_설명.md

AdaptiveEcosystem/Docs/초기설정/01_ARCHITECTURE.md
AdaptiveEcosystem/Docs/초기설정/02_DATA_CONTRACTS.md
AdaptiveEcosystem/Docs/초기설정/03_TEAM_ROLES.md
AdaptiveEcosystem/Docs/초기설정/04_SERVER_MASS_NETWORK.md
AdaptiveEcosystem/Docs/초기설정/05_AI_LLM_BOUNDARY.md
AdaptiveEcosystem/Docs/초기설정/08_BOOTSTRAP_PLAN.md
AdaptiveEcosystem/Docs/초기설정/AGENTS.md
AdaptiveEcosystem/Docs/초기설정/ASSET_AUDIT.md
AdaptiveEcosystem/Docs/초기설정/INITIAL_REPO_BOOTSTRAP.md

AdaptiveEcosystem/Docs/초기설정2/REPO_STABILIZATION_PLAN.md
AdaptiveEcosystem/Docs/초기설정2/REPO_STABILIZATION_PROMPT.md

AdaptiveEcosystem/Docs/초기설정3/진화모델_확장.md
AdaptiveEcosystem/Docs/초기설정3/진화모델_확장_AGENT_PROMPT.md
```

### Runtime

```text
AdaptiveEcosystem/Source/AdaptiveEcosystem/Core/EcoDataContracts.h
AdaptiveEcosystem/Source/AdaptiveEcosystem/World/*
AdaptiveEcosystem/Source/AdaptiveEcosystem/Ecology/*
AdaptiveEcosystem/Source/AdaptiveEcosystem/Evolution/*
AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/*
AdaptiveEcosystem/Source/AdaptiveEcosystem/Network/*
AdaptiveEcosystem/Source/AdaptiveEcosystem/Debug/*
```

경로가 바뀌었거나 새 코드가 있으면 실제 현재 저장소를 기준으로 다시 판단한다.

---

## 2. 현재 저장소 분석 기준

현재 코드에서 **유지 가치가 높은 부분**:

- `AEcologyRegion`
  - `RegionId`
  - `FRegionEnvironmentState`
  - Region Bounds
  - 식생/먹이 소비·재생
  - Rainfall 기반 regrowth
- `UEcologyWorldSubsystem`
  - Region registry
  - RegionId 기반 lookup
  - environment query
- `StableAgentId`, `RegionId`, `SpeciesId`, Epoch/Revision 개념
- `ACreatureCharacter`가 Ecology subsystem을 직접 조회하지 않고 외부에서 초기화되는 representation 경계

다음 원칙은 유지한다.

```text
Logical Mass Entity
        ↓
Representation Snapshot
        ↓
Creature Actor
```

Actor는 논리 생태 상태의 source of truth가 아니다.

---

## 3. 폐기/격리할 기존 핵심

새 프로젝트 목표의 중심이 아니므로 다음은 Active Runtime 핵심에서 제거한다.

```text
Evolution LLM
FEvolutionContext
FEvolutionProposal
FSpeciesEvolutionProfile 기반 장기 Trait Evolution
FVegetationEvolutionProfile 기반 식생 Trait Evolution
IEvolutionDecisionProvider
DummyEvolutionDecisionProvider
UEvolutionValidator
Mutation Budget
Generation 기반 Trait Delta Commit
LLM Async Proposal Pipeline
Simulation Policy AI
```

또한 다음도 캡스톤 핵심 목표에서 제외한다.

```text
복잡한 Player Pressure 10여 종
BodyScale/Bone/Material 세대 진화
Fear/Aggression Trait Evolution
Dedicated Server를 필수 전제로 둔 구조
Full Multiplayer Replication
```

단, 첫 PR에서 무조건 대량 삭제하지 마라.

1. C++/Blueprint/Asset reference 조사
2. 새 Runtime 계약 추가
3. 기존 호출부를 새 계약으로 이동
4. Build/Editor 확인
5. Legacy 코드 제거 또는 격리

기존 문서는 `DEPRECATED` 표시 또는 `Docs/Legacy_ServerLLM/` 이동을 검토한다. Git history rewrite는 금지한다.

---

## 4. 프로젝트의 새 정의

> 플레이어 행동과 날씨·낮/밤·지역 자원 상태가 개체의 관측과 행동에 영향을 주고, 개체의 먹이 소비·생존·피식·사망·이주 결과가 다시 Resource와 Population을 변화시키는 **MassEntity 기반 동적 생태계**를 구현한다. 개체의 환경 적응 행동은 Python에서 PPO로 학습하고, 학습된 Policy는 Unreal C++에서 직접 추론하여 Mass 기반 이동에 적용한다.

핵심은:

```text
환경 → 행동 → 생태 변화 → 새로운 환경 → 행동 ...
```

이다.

PPO 자체가 프로젝트 목적이 아니다.

---

## 5. 목표 아키텍처

```text
┌──────────────────────────────────────────┐
│ WORLD / REGION                           │
│ Region / Weather / DayNight / Shelter    │
│ Food Capacity / Resource Regeneration    │
└──────────────────────┬───────────────────┘
                       ▼
┌──────────────────────────────────────────┐
│ ECOLOGY RUNTIME                          │
│ Region Ecology State                     │
│ Resource / Population / PredationHistory │
│ Aggregation / Lifecycle / Migration      │
└──────────────────────┬───────────────────┘
                       ▼
┌──────────────────────────────────────────┐
│ MASS LOGICAL CREATURES                   │
│ Identity / Vitals / Region / Travel       │
│ Observation / Policy Output              │
└──────────────────────┬───────────────────┘
                       ▼
┌──────────────────────────────────────────┐
│ BEHAVIOR POLICY                          │
│ PPO Policy OR Utility Baseline           │
│ shared model, per-agent observation      │
└──────────────────────┬───────────────────┘
                       ▼
┌──────────────────────────────────────────┐
│ MASS STEERING                            │
│ MassNavigation spatial lookup            │
│ Flock + Forage + Flee + Cover forces     │
└──────────────────────┬───────────────────┘
                       ▼
┌──────────────────────────────────────────┐
│ MOVEMENT / INTERACTION                   │
│ Move / Eat / Predation / Death / Travel  │
└──────────────────────┬───────────────────┘
                       ▼
             Region State Feedback
                       └──────────────↺
```

---

## 6. 데이터 소유권

### Entity Fragment — 개체마다 다른 값

```text
StableAgentId
SpeciesId
HP
Energy
Current Region
Target Region
Travel State
Alive
Current Observation
Current Policy Output
Policy Update Timing
```

### Shared / Species Config — 종 단위 공유값

```text
MaxHP
BaseMoveSpeed
EnergyDecayRate
FoodConsumptionRate
FoodEnergyGain
ViewDistance
FOV
MigrationThreshold
PolicyConfigId
```

### Region / World Runtime State — 지역 공유값

```text
RegionId
FoodAmount
FoodCapacity
FoodRegenerationRate
Population Summary
PredationHistory
Weather
DayPhase
Temperature
Humidity
Rainfall
```

### Actor / Representation

```text
Mesh
Animation
Collision
Combat Presentation
Player Interaction
```

Actor는 장기 논리 상태의 단일 진실값이 아니다.

---

## 7. Environment와 Ecology State 분리

현재 `FRegionEnvironmentState`에 환경과 자원이 섞여 있다.

새 구조는 의미를 분리한다.

```cpp
FRegionEnvironmentState
- Temperature
- Humidity
- Rainfall
- DayPhase
- WeatherState
```

```cpp
FRegionEcologyState
- RegionId
- FoodAmount
- FoodCapacity
- FoodRegenerationRate
- PredationHistory
- Population
- AverageEnergy
```

`VegetationDensity`가 시각적 식생 밀도라면 Resource의 파생값으로 취급하거나 owner를 명확히 한다.

**같은 Food 상태를 Environment와 Ecology가 따로 보유하지 마라.**

---

## 8. MassEntity 데이터 설계

실제 UE 5.8 API를 확인한 뒤 naming을 맞춘다.

권장 개념:

```text
FEcoIdentityFragment
- StableAgentId
- SpeciesId

FEcoVitalsFragment
- HP
- Energy

FEcoRegionFragment
- RegionRuntimeIndex

FEcoTravelFragment
- TargetRegion
- TravelProgress / state

FEcoObservationFragment
- policy observation v1

FEcoPolicyOutputFragment
- forage
- cohesion
- flee_dist
- cover

FEcoPolicyRuntimeFragment
- LastPolicyStep
- NextPolicyStep
- ModelRevision

FEcoSpeciesSharedFragment
- immutable/slow-changing species parameters
```

Tag는 최소화한다.

```text
FEcoAliveTag
FEcoMigratingTag
```

매 프레임 자주 변하는 행동 상태를 Tag add/remove로 표현해 archetype churn을 만들지 않는다.

---

## 9. Hot Path ID

외부 계약에서는 `FName RegionId`, `FName SpeciesId`를 유지할 수 있다.

Mass hot loop에서는 반복적인 문자열/FName lookup 대신:

```text
RegionRuntimeIndex
SpeciesRuntimeIndex
```

같은 compact index를 검토한다.

외부 ID ↔ runtime index 변환은 registry/subsystem 경계에서 수행한다.

---

## 10. Processor 실행 순서

명시적인 실행 순서를 설계한다.

```text
1. Eco.Environment / Region Update
2. Eco.Observation
3. Eco.Policy
4. Eco.Steering
5. Mass Movement
6. Eco.Interaction
7. Eco.Vitals / Lifecycle
8. Eco.Migration
9. Eco.Aggregation / Metrics
10. Representation / LOD
```

UE 5.8의 Processor Group / dependency API를 실제 엔진 기준으로 확인한다. UE 5.1 코드를 그대로 복사하지 않는다.

---

## 11. 병렬 처리 안전성

금지:

```text
Entity loop 안에서 Region UObject를 매 Entity마다 직접 수정
Entity loop 안에서 공유 TMap을 무잠금 mutate
Entity loop 안에서 Actor/World 검색 반복
```

Food 소비는 가능하면:

```text
Entity
→ Food Request
→ Region별 Request 집계
→ Reconciliation
→ FoodAmount 감소
→ Energy gain
```

처럼 처리한다.

Entity composition 변경은 Mass deferred command를 사용한다.

---

## 12. PPO Observation Contract V1

정책 V1은 **7개 입력**으로 고정한다.

```text
1. food_density
2. predator_count
3. predator_distance
4. conspecific_count
5. energy
6. recent_predation
7. cover_distance
```

각 feature마다 반드시 문서화:

```text
의미
단위
원본 범위
정규화
missing 처리
clip 범위
관측 시점
```

가능하면 dimensionless normalized value를 사용한다.

예:

```text
energy              : 0..1
food_density         : 0..1
recent_predation     : 0..1
predator_distance    : distance / view_distance
cover_distance       : distance / cover_search_radius
predator_count       : min(count, cap) / cap
conspecific_count    : min(count, cap) / cap
```

정규화 상수를 Python과 C++에 따로 하드코딩하지 않는다.

---

## 13. PPO Action Contract V1

출력은 직접 위치/속도가 아니라 다음 4개 고수준 행동 파라미터다.

```text
forage
cohesion
flee_dist
cover
```

의미:

```text
forage    = 먹이 방향 조향 강도
cohesion  = 동족 응집 강도
flee_dist = 포식자로부터 도주를 시작하는 거리/민감도
cover     = 은신처 방향 조향 강도
```

이 구조를 유지하는 이유:

- Aquarium과 Unreal의 물리 차이를 줄이기 좋음
- Policy가 Unreal Movement를 직접 대체하지 않음
- MassFlock과 자연스럽게 결합 가능
- 디버깅이 쉬움

---

## 14. Action Post-processing

Python PPO와 C++ inference가 조용히 달라지지 않도록 다음을 Contract로 고정한다.

```text
hidden activation
actor output semantics
raw output clamp
sigmoid/tanh 여부
action space range
parameter range mapping
deterministic inference semantics
```

현재 계획의:

```text
raw clamp ±3
→ sigmoid
→ behavior parameter range mapping
```

을 유지한다면 Python 학습 환경에서도 동일 wrapper/post-process를 사용한다.

SB3 내부 구현을 추측해서 C++를 쓰지 마라.

최종 기준은:

```python
model.predict(obs, deterministic=True)
```

와 C++ 결과의 일치다.

---

## 15. Policy Network

목표 모델:

```text
7 → 64 → 64 → 4
```

정책 하나를 모든 개체가 공유한다.

```text
shared policy
+
per-agent observation
=
per-agent behavior output
```

Hidden activation은 현재 계획대로 `tanh`를 사용할 수 있으나 실제 SB3 설정에 명시한다.

학습 후 `state_dict()`와 실제 actor 구조를 확인해 export한다.

---

## 16. Aquarium + SB3 연결 시 주의

Aquarium은 **PettingZoo 기반 multi-agent environment**다.

Stable-Baselines3는 기본적으로 single-agent Gymnasium interface를 전제로 하므로,
**“PettingZoo이므로 SB3에 바로 직결된다”라고 가정하지 마라.**

다음 중 하나의 명시적인 adapter를 만든다.

```text
A. parameter sharing + SuperSuit/vectorization
B. project-owned PettingZoo → Gym/VecEnv shared-policy adapter
```

Adapter 책임:

```text
agent lifecycle
observation batching
action unbatching
termination/truncation
seed
reset
reward handling
dead-agent handling
```

PettingZoo API test와 short-training smoke test를 추가한다.

---

## 17. Python 프로젝트 구조

Unreal Source와 학습 코드를 섞지 않는다.

```text
Tools/
└─ RL/
   ├─ pyproject.toml
   ├─ README.md
   ├─ adaptive_ecosystem_rl/
   │  ├─ env/
   │  │  ├─ aquarium_adapter.py
   │  │  ├─ observation.py
   │  │  ├─ action_mapping.py
   │  │  └─ reward.py
   │  ├─ training/
   │  │  ├─ train_ppo.py
   │  │  └─ optimize_optuna.py
   │  ├─ baseline/
   │  │  └─ utility_policy.py
   │  ├─ eval/
   │  │  └─ evaluate.py
   │  └─ export/
   │     ├─ export_policy.py
   │     └─ generate_golden_vectors.py
   └─ tests/
```

`checkpoints/`, `runs/`, `videos/`, 대용량 로그는 기본적으로 Git에 커밋하지 않는다.

---

## 18. Aquarium 확장 범위

Aquarium이 제공하는 다음을 최대한 재사용한다.

```text
2D continuous environment
predator/prey
FOV
view distance
physics/steering
hit/catch logic
render/debug
```

추가 핵심:

```text
Food resource + regeneration
Cover / shelter zones
Region/local predation history
Energy
필요 시 ranged predator behavior
```

가능하면 wrapper/subclass/composition을 우선하고 upstream core를 무분별하게 fork하지 않는다.

---

## 19. Sim-to-Sim Gap

Python Aquarium과 Unreal Mass는 물리/단위가 다르다.

맞춰야 할 항목:

```text
time step
movement response
max velocity
steering strength
FOV
view distance
catch distance
neighbor count semantics
cover distance semantics
food density semantics
energy drain/gain
```

pixels ↔ centimeters를 직접 대응하지 말고 관측은 정규화된 의미 공간으로 만든다.

Direct velocity 대신 behavior weight를 출력하는 현재 구조를 유지한다.

---

## 20. Reward 설계

Survival reward 하나만 쓰지 않는다.

그렇지 않으면:

```text
무조건 숨기
움직이지 않기
먹이 무시
비정상 군집
```

같은 degenerate policy가 가능하다.

최소 고려:

```text
survival
predation penalty
energy maintenance
food acquisition
movement/energy cost
cover trade-off
grouping trade-off
optional reproduction success
```

Reward coefficient는 config로 관리하고 실험마다 revision을 기록한다.

---

## 21. Utility AI 비교군

Utility AI는 메인 Runtime이 아니다.

```text
1. PPO 비교군
2. 초기 imitation/behavior cloning 실험의 teacher 후보
3. PPO 실패 시 fallback
```

예:

```text
forage    = k1 * (1 - energy)
cohesion  = k2 * recent_predation
flee_dist = k3 + k4 * recent_predation
cover     = k5 * predator_count
```

`k1~k5`는 가능하면 Optuna로 튜닝한다.

비교는:

```text
동일 Environment
동일 Observation semantics
동일 Action semantics
동일 Reward
동일 Evaluation Seed
```

를 사용한다.

학습에 쓰지 않은 최소 20개 seed로 평가한다.

---

## 22. 평가 지표

### 생태/생존

```text
average survival time
predation rate
food consumed
average energy
population change
migration count
resource depletion/recovery
optional reproduction count
```

### 행동

```text
cohesion
flee distance
cover usage ratio
forage ratio
movement distribution
```

### 상황 적응

```text
predator absent → present
low predation → high predation
not hungry → hungry
```

상황별 4개 출력 평균 변화량을 기록한다.

### 성능

```text
Entity count
Game Thread
Processor cost
Policy inference cost
Mass steering cost
Archetype count
Chunk count
Representation count
```

---

## 23. Python → Unreal Policy Export

Runtime에서 Python interpreter, ONNX, NNE를 사용하지 않는 방향을 기본으로 한다.

```text
SB3 trained policy
→ exact deterministic actor weights
→ normalization + action mapping metadata
→ generated C/C++ header/inl
→ UE policy inference
```

권장:

```text
Source/AdaptiveEcosystem/AI/Policy/
├─ EcoPolicyTypes.h
├─ EcoPolicyRuntime.h/.cpp
├─ EcoPolicyProcessor.h/.cpp
└─ Generated/
   └─ EcoPolicyWeights.generated.inl
```

생성 파일 metadata:

```text
ModelRevision
PolicySchemaVersion
NormalizationRevision
Layer dimensions
Activation
Action mapping version
Training experiment id
optional model hash
```

Generated 파일은 사람이 직접 수정하지 않는다.

---

## 24. Python ↔ C++ 정합성

Export script가 **golden vectors**를 생성한다.

```text
100개 Observation
+
Python deterministic output
```

C++ Automation Test에서 같은 입력을 넣고 비교한다.

검증 대상:

```text
observation order
normalization
weight layout
bias
activation
output layer
clamp
sigmoid/tanh/post-process
parameter mapping
```

초기 권장 tolerance:

```text
max abs error <= 1e-5
```

필요 시 float 차이를 근거로 조정한다.

---

## 25. MassFlock 활용 전략

참고 오픈소스:

```text
PiotrJezyna/MassFlock
MIT License
원본 UE 5.1
```

원본은:

```text
Cohesion
Alignment
Avoidance
MassNavigation HashGrid neighbor lookup
FMassForceFragment
Flock Movement
Flock Bounds
Simulation LOD
```

를 제공한다.

**UE 5.8에 그대로 복사해서 된다고 가정하지 마라.**

먼저 compatibility spike:

```text
UE 5.8 Mass module names
MassNavigation API
UMassNavigationSubsystem
FMassSimulationLODFragment
Variable Tick
Processor dependency
FMassForceFragment
Representation/LOD
```

를 확인한다.

---

## 26. MassFlock + PPO에서 가장 중요한 구조

원본 MassFlock의 Cohesion/Alignment/Avoidance 파라미터는 `FMassSharedFragment` 기반이다.

PPO 출력은 **개체마다 다르다.**

잘못된 구현:

```text
Entity마다 PPO cohesion 값 때문에
Shared Fragment를 별도 생성
```

이러면 shared-fragment/archetype 조합이 증가할 수 있다.

대신:

```text
Species/Base Shared Params
       ×
Per-Agent FEcoPolicyOutputFragment
       ↓
Final Steering Force
```

로 만든다.

예:

```text
Base Cohesion Radius / Force = Shared
PPO cohesion multiplier       = Per Entity Fragment
```

`flee_dist`, `forage`, `cover`도 per-agent Fragment다.

필요하면 원본 Processor를 그대로 쓰지 말고 프로젝트용 `UEcoFlockSteeringProcessor`로 적응한다.

---

## 27. MassFlock 도입 방식

둘 중 하나를 명시적으로 선택한다.

### Option A — Reference-based Adaptation 권장

MassFlock의 알고리즘/HashGrid 구조를 참고하여 UE5.8용 프로젝트 Processor 구현.

장점:

- per-agent PPO output과 자연스럽게 결합
- UE5.8 API 대응
- 불필요한 원본 프로젝트 코드 미도입

MIT attribution은 `THIRD_PARTY_NOTICES.md`에 기록한다.

### Option B — Fork/Vendor

원본을 plugin/fork로 가져와 UE5.8 + per-agent extension.

upstream과 local patch를 문서화한다.

사용자 승인 없이 거대한 third-party source를 자동 vendor하지 않는다.

---

## 28. Steering Layer

개념적으로:

```text
Final Force =
    Base Flock Cohesion
  + Base Alignment
  + Base Avoidance
  + PPO-weighted Forage
  + PPO-weighted Flee
  + PPO-weighted Cover
  + Bounds / Navigation
```

PPO 출력은 힘 자체가 아니라 정규화된 behavior weight로 유지한다.

---

## 29. Player = Predator

V1 범위:

```text
Player 존재
→ predator_count / predator_distance

사냥 성공
→ Creature death
→ Region PredationHistory 증가
→ 이후 다른 Entity observation 변화
```

미구현:

```text
플레이어별 기억
길들이기
먹이 주기
개별 평판
```

Player Actor를 MassNavigation spatial structure에 넣는 방법은 UE5.8 public API를 먼저 확인한다.

Private API를 억지로 호출하지 말고, 필요하면 별도 lightweight predator spatial registry를 만든다.

---

## 30. Predation History

기존 `FPlayerPressureState`의 다수 pressure를 유지하지 말고 V1 핵심 상태로 축소한다.

```text
RegionPredationHistory : 0..1
```

예:

```text
kill/predation event → 증가
time → decay
```

decay는 config화한다.

이 값이 observation의 `recent_predation`이다.

---

## 31. Weather / Day-Night

Policy V1은 7개 입력이다.

Weather/DayNight를 무작정 8/9번째 feature로 추가하지 마라.

V1에서는 간접 영향 우선:

```text
Rain
→ Food Regeneration
→ Food Density
→ Observation
→ Behavior
```

```text
Night
→ Resource/Predator/Cover condition
→ 기존 Observation
→ Behavior
```

직접 feature로 추가하려면 반드시:

```text
PolicySchemaVersion 증가
Python env 수정
재학습
Exporter 수정
C++ 수정
Golden test 재생성
```

을 함께 한다.

---

## 32. Food / Vegetation Feedback

현재 `ApplyVegetationConsumption()` / `ApplyVegetationRegrowth()` 개념은 재사용 가능하다.

하지만 새 구조의 핵심은 식생 Trait Evolution이 아니라 **동적 Resource feedback**이다.

```text
Rainfall
→ Food Regen
→ FoodAmount 증가

Creature Forage
→ FoodAmount 감소
→ Energy 증가

Food 부족
→ 이동/이주
→ Region Population 변화
```

복잡한 식물 유전/세대 진화를 재도입하지 않는다.

---

## 33. Population

가능하면 Population은 실제 logical entity의 집계값이다.

```text
Population(region, species)
=
Alive Mass Entity count
```

별도 Summary가 있다면 Aggregation Processor가 authoritative logical entities에서 갱신한다.

Population counter와 Entity lifecycle이 drift하지 않게 한다.

---

## 34. Lifecycle / Reproduction

첫 Mass MVP:

```text
100 wolves
Energy 감소
Food 소비
Death
Migration
```

장기적으로 Population이 감소만 하면 생태 피드백이 제한된다.

초기 MVP 후 다음 중 하나를 명시적으로 결정한다.

```text
A. simple reproduction
B. region-level recruitment / respawn
C. reproduction 미구현을 데모 범위로 명확히 제한
```

Aquarium 평가에서 reproduction을 쓰면 Unreal과의 차이를 문서화한다.

---

## 35. Migration

매 Entity가 매 프레임 expensive path search를 하지 않는다.

```text
Region resource / energy / risk
→ low-frequency migration decision
→ TargetRegion
→ coarse travel state
→ 필요한 실제 movement
```

2 Region MVP부터 시작한다.

---

## 36. Representation / Simulation LOD

```text
Far
→ logical Mass only / low-frequency simulation

Near
→ visual Mass Representation

Important interaction
→ 필요 시 ACreatureCharacter
```

전환 전후 유지:

```text
StableAgentId
HP
Energy
Region
Species
Alive
필요한 behavior state
```

Representation 전환은 새 개체 생성이 아니다.

---

## 37. Policy Update Rate / LOD

Policy inference를 매 프레임 하지 않는다.

초기 예:

```text
Policy update = 8 simulation ticks 또는 일정 Hz
Steering = simulation tick
Region ecology = 더 낮은 Hz
```

최종 rate는 profiling으로 결정한다.

LOD 품질 검증:

```text
10 Hz baseline
vs 2 Hz
vs 1 Hz
```

측정:

```text
Energy error
Death time error
Migration decision time error
Population error
```

---

## 38. Debug / Observability

### Entity

```text
StableAgentId
Species
Region
HP
Energy
LOD
```

### Observation

```text
food_density
predator_count
predator_distance
conspecific_count
energy
recent_predation
cover_distance
```

### Policy

```text
PPO / Utility
ModelRevision
forage
cohesion
flee_dist
cover
last inference step
```

### Region

```text
FoodAmount / Capacity
Food Regen
Population
PredationHistory
Weather
DayPhase
Migration In/Out
```

### Performance

```text
Mass Entity Count
Representation Count
Observation Processor ms
Policy Processor ms
Steering Processor ms
Interaction Processor ms
```

PPO ↔ Utility 런타임 전환 console variable을 고려한다.

---

## 39. Reproducibility

Python 실험 metadata:

```text
seed
training/eval seed split
Aquarium version
SB3 version
PettingZoo version
SuperSuit/custom adapter version
reward config
observation schema
action schema
normalization revision
PPO hyperparameters
model revision
git commit
```

---

## 40. Optuna

초기 탐색 후보:

```text
learning_rate
gamma
entropy coefficient
필요 시 gae_lambda / clip_range
Utility k1~k5
```

초기 MVP에서 고정 권장:

```text
7 → 64 → 64 → 4
hidden activation
observation order
action mapping
```

아키텍처를 바꾸면 PolicySchemaVersion을 올린다.

---

## 41. 오픈소스 / License

사용 후보:

```text
michaelkoelle/marl-aquarium — MIT
Stable-Baselines3
PettingZoo
Optuna
PiotrJezyna/MassFlock — MIT
```

`THIRD_PARTY_NOTICES.md`를 추가한다.

복사/수정한 MIT 코드의 저작권/라이선스를 보존한다.

Python dependency는 버전을 고정한다.

---

## 42. Build.cs / uproject

현재 Mass dependency가 충분하지 않다.

UE 5.8 실제 엔진에서 필요한 module/plugin을 확인하고 최소 추가한다.

예상 후보:

```text
MassEntity
MassCommon
MassSpawner
MassMovement
MassNavigation
MassLOD
MassRepresentation
MassActors
StructUtils
```

Plugin 후보:

```text
MassEntity
MassGameplay
MassAI
```

이름/공개 여부는 UE5.8 실제 API로 확인한다.

MassGameplay이 Experimental인 부분은 리스크로 기록한다.

---

## 43. Source 구조 권장안

기존 단일 Runtime Module은 유지해도 된다.

```text
Source/AdaptiveEcosystem/
├─ Core/
│  ├─ EcoIds.h
│  ├─ EcoRegionTypes.h
│  └─ EcoPolicyContracts.h
├─ World/
├─ Ecology/
├─ Mass/
│  ├─ EcoMassFragments.h
│  ├─ EcoMassTraits.*
│  ├─ Observation/
│  ├─ Policy/
│  ├─ Steering/
│  ├─ Interaction/
│  ├─ Lifecycle/
│  └─ Migration/
├─ AI/
│  ├─ Policy/
│  └─ Baseline/
├─ Creature/
│  └─ Representation/
└─ Debug/
```

Public/Private 전체 이동 같은 unrelated 대규모 refactor는 동시에 하지 않아도 된다.

---

## 44. `EcoDataContracts.h` 분해

현재 한 파일에:

```text
Environment
Player Pressure
Creature Traits
Evolution Profiles
Evolution Context/Proposal
Vegetation Evolution
Ecology Events
```

가 섞여 있다.

단계적으로:

```text
Core/EcoRegionTypes.h
Core/EcoEventTypes.h
Core/EcoRepresentationTypes.h
AI/Policy/EcoPolicyContracts.h
Mass/EcoMassFragments.h
```

로 분해한다.

삭제 예정 LLM/Evolution 타입이 Core 계약을 계속 오염시키지 않게 한다.

한 PR에서 모든 타입을 강제 이동해 include breakage를 만들지 않는다.

---

## 45. `UEcologyServerSubsystem`

현재 클래스는 server-only + Evolution Profile/Proposal commit 중심이다.

새 MVP는 Dedicated Server 중심이 아니다.

권장 목표:

```text
UEcologySimulationSubsystem
- World-scoped ecology runtime
- Region resource state
- Predation history
- events
- aggregation
- simulation scheduling
```

즉시 rename이 위험하면:

```text
1. 새 Subsystem 추가
2. 새 코드가 새 Subsystem 사용
3. 기존 UEcologyServerSubsystem deprecated wrapper
4. reference 확인 후 제거
```

멀티플레이를 나중에 추가하더라도 Core Simulation과 Network Authority를 분리한다.

---

## 46. Creature Runtime

현재:

```text
ACreatureCharacter
→ FSpeciesEvolutionProfile
→ UCreatureTraitComponent
```

새 구조:

```text
Mass Logical State
→ Representation Snapshot
→ ACreatureCharacter
```

Actor가 PPO를 직접 추론하지 않는다.

Actor에는 최소 정보만 전달한다.

```text
StableAgentId
SpeciesId
HP
Energy
Transform
presentation state
```

Evolution-specific Scale/Fear/Aggression 체계를 새 AI와 이중으로 남기지 않는다.

---

## 47. Network

현재 MVP에서는 Dedicated Server/Replication을 필수 성공 조건으로 두지 않는다.

`Network/`는:

```text
reference 없으면 Legacy/Future로 격리
새 핵심 경로가 의존하지 않게 함
Subsystem은 replication transport가 아니라는 원칙만 유지
```

향후 multiplayer 시 Region summary + Active Actor 상태만 별도 설계한다.

모든 Mass Entity transform을 보내지 않는다.

---

## 48. Legacy Evolution 제거 완료 조건

최종 Active Runtime 핵심 경로에서 다음 의존성이 없어져야 한다.

```text
Evolution/
FSpeciesEvolutionProfile
FVegetationEvolutionProfile
FEvolutionContext
FEvolutionProposal
UEvolutionValidator
IEvolutionDecisionProvider
```

역사 기록은 Git/Legacy docs로 남길 수 있다.

새 동적 생태계와 옛 세대별 Trait Evolution을 동시에 핵심 체계로 남기지 않는다.

---

## 49. 테스트

### C++ Automation

```text
StableAgentId uniqueness
Energy clamp
Food non-negative
Population aggregation consistency
PredationHistory decay
Migration transition
Policy normalization
Policy C++ forward
Golden-vector parity
```

### Python

```text
Aquarium adapter reset/step
observation shape = 7
action shape = 4
range validation
seed reproducibility
shared-policy adapter smoke test
PPO short training
export round trip
Utility baseline evaluation
```

### Integration

```text
100 logical creatures
2 regions
food consumption
energy drain/gain
player absent simulation
migration
player predator event
predation history
PPO vs Utility toggle
weather/day-night effect
```

---

## 50. 성능 검증

최초 목표:

```text
100 logical creatures
```

이후:

```text
500
1000
가능하면 그 이상
```

측정:

```text
Game Thread
Mass Processor cost
Policy inference cost
Neighbor search cost
Archetype count
Chunk count
Memory
Representation count
```

Mass 사용 자체를 성공으로 간주하지 말고 profiling으로 검증한다.

---

## 51. 데모 시나리오

### A. 플레이어 사냥 압력

```text
Region A
PredationHistory 낮음
Wolf 일반 행동
↓
Player 반복 사냥
↓
Creature death
PredationHistory 증가
Population 감소
↓
recent_predation observation 증가
↓
PPO output 변화
↓
cohesion / flee_dist / cover 변화
↓
재방문 시 행동 양상 변화
```

### B. 자원 부족

```text
Creature forage
→ Food 감소
→ Energy 확보

Food 부족
→ migration 조건 충족
→ Region B 이동
→ Region별 Population 변화
```

### C. Weather

```text
Rain 증가
→ Food regeneration 변화
→ Food density 변화
→ Observation 변화
→ behavior 변화
→ resource/population feedback
```

---

## 52. 단계별 Migration Plan

### PR 1 — Architecture Reset / Documentation

- LLM Evolution 구조와 새 목표 차이 명시
- Root `AGENTS.md`와 active docs 수정
- Legacy docs DEPRECATED
- Policy/Ecosystem contract 초안
- 코드 동작 최대한 유지

### PR 2 — Region Resource + Mass Skeleton

```text
2 Region
100 Entity
StableAgentId
HP
Energy
Region
Food
```

PPO 없이도 됨.

성공 조건:

```text
player 없이 simulation
Food/Energy 변화
Population 집계 일치
```

### PR 3 — Lifecycle + Migration

```text
Energy drain/gain
Death
Food consumption
Migration
PredationHistory
```

### PR 4 — Python RL Environment

```text
Aquarium extension
7 observation
4 action
Energy/Food/Cover/Predation
Utility baseline
SB3 shared-policy adapter
```

### PR 5 — PPO Training / Evaluation / Export

```text
7→64→64→4
Optuna
train/eval seed separation
Utility comparison
policy export
golden vectors
```

### PR 6 — C++ Policy Runtime

```text
generated weights
C++ deterministic inference
golden parity
PolicyProcessor
PPO / Utility toggle
```

### PR 7 — MassFlock / MassNavigation

```text
UE5.8 compatible neighbor lookup
base flock
per-agent PPO weights
forage
flee
cover
movement
```

### PR 8 — Full Ecosystem Feedback

```text
Weather / DayNight / Resource
→ Observation
→ PPO
→ Movement/Interaction
→ Food / Death / Migration / Population
→ Region State
```

### PR 9 — Representation / LOD / Profiling

```text
near representation
far logical simulation
Simulation LOD
profiling
behavior comparison
final demo
```

---

## 53. Definition of Done

```text
[ ] Active 핵심 경로에서 LLM Evolution 의존성 제거
[ ] Mass Entity가 logical creature source of truth
[ ] StableAgentId 유지
[ ] Region Resource 단일 owner
[ ] Population과 Entity lifecycle 일치
[ ] Food 소비 → Energy 반영
[ ] Player kill → PredationHistory
[ ] Observation V1 7개 Python/C++ 동일
[ ] Action V1 4개 Python/C++ 동일
[ ] shared PPO + per-agent observation
[ ] Utility baseline + runtime toggle
[ ] Python deterministic output ↔ C++ parity
[ ] PPO per-agent 값 때문에 Shared Fragment 폭발 없음
[ ] Weather/DayNight가 생태 상태에 실제 영향
[ ] Resource/Population 결과가 다음 행동에 feedback
[ ] 100 Entity가 player 없이 simulation
[ ] profiling 기록
```

---

## 54. 하지 말 것

```text
LLM backend 추가
llama.cpp 추가
Evolution LLM 복원
ONNX/NNE 추가
Python runtime game embed
한 PR에 전체 시스템 구현
Template Asset 대량 삭제
Git history rewrite
Full multiplayer replication
Save/Load 전체 구현
유전자/염색체 모델
절차적 Creature mesh
Mass Entity마다 Actor/AIController 생성
Entity마다 매 프레임 UObject/Actor search
per-agent PPO value를 Shared Fragment로 저장
```

---

## 55. 문서 갱신

최소:

```text
AGENTS.md
AdaptiveEcosystem/Docs/아키텍처_설명.md
AdaptiveEcosystem/Docs/초기설정/01_ARCHITECTURE.md
AdaptiveEcosystem/Docs/초기설정/02_DATA_CONTRACTS.md
AdaptiveEcosystem/Docs/초기설정/03_TEAM_ROLES.md
AdaptiveEcosystem/Docs/초기설정/08_BOOTSTRAP_PLAN.md
```

Legacy 처리:

```text
05_AI_LLM_BOUNDARY.md
초기설정3/진화모델_확장.md
초기설정3/진화모델_확장_AGENT_PROMPT.md
```

삭제보다 먼저 `DEPRECATED — Legacy Server/LLM Architecture` 표시 권장.

---

## 56. 새 문서 권장

```text
Docs/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md
Docs/POLICY_CONTRACT_V1.md
Docs/RL_TRAINING_PIPELINE.md
Docs/MASS_PROCESSOR_ORDER.md
Docs/THIRD_PARTY_INTEGRATION.md
THIRD_PARTY_NOTICES.md
```

`POLICY_CONTRACT_V1.md`에는 반드시:

```text
Observation order
Normalization
Action order
Action range
Network dimensions
Activation
Post-processing
Model revision
Schema revision
```

을 고정한다.

---

## 57. 판단 우선순위

충돌 시:

```text
1. 이 프롬프트의 새 프로젝트 목표
2. 실제 UE 5.8 API
3. 현재 compile-safe runtime
4. 새 Active architecture docs
5. Legacy LLM docs
```

Legacy 문서 내용을 새 요구사항으로 오해하지 마라.

---

## 58. Build / 검증

각 단계 후 가능한 범위에서:

```text
AdaptiveEcosystemEditor Win64 Development
```

빌드.

실패 시 구분:

```text
project code compile error
third-party Mass API incompatibility
UE5.8 plugin/module issue
local SDK/toolchain issue
missing asset/editor setup
```

Editor manual step이 필요하면 정확히 보고한다.

---

## 59. 완료 보고 형식

```text
1. Current Repo Analysis
2. Target Architecture Applied
3. Changed Files
4. New Files
5. Legacy Files
6. Data Contracts
7. MassEntity
8. RL Pipeline
9. Policy Export
10. Python ↔ C++ Parity Result
11. MassFlock / MassNavigation Integration
12. Ecosystem Feedback
13. Debug / Profiling
14. Build Result
15. Manual Unreal Editor Checks
16. Intentionally Not Implemented
17. Risks / Open Questions
18. Recommended Next PR
```

---

## 60. 마지막 원칙

성공 기준은:

```text
"PPO가 움직였다"
```

가 아니다.

성공 기준은:

```text
플레이어와 환경 때문에 Region 상태가 달라지고
→ 개체 관측이 달라지고
→ 학습 정책이 행동을 달리하고
→ 행동 결과가 Resource / Population / Distribution을 다시 바꾸며
→ 다음 시뮬레이션 상태에 누적되는 것
```

이다.

항상 다음 질문으로 우선순위를 판단한다.

> **이 기능이 개체 행동과 지역 생태 상태 사이의 feedback loop를 더 명확하고, 확장 가능하고, 검증 가능하게 만드는가?**

아니라면 캡스톤 핵심 경로에서 우선순위를 낮춰라.
