# 02. Data Contracts

이 문서는 팀 간 결합 지점을 정의한다. 내부 구현은 바뀔 수 있지만 공통 계약은 PR 단위로 관리한다.

## 1. 식별자 / Revision

초기 권장 타입:

```cpp
using FRegionId = FName;      // 또는 wrapper를 나중에 도입
using FSpeciesId = FName;

uint64 StableAgentId;
uint64 EventId;
uint64 ObservationId;

uint32 WorldEpoch;
uint32 ControlEpoch;
uint32 WorldRevision;
uint32 SummaryRevision;
uint32 ConfigRevision;
uint32 ProfileRevision;
uint32 ModelRevision;
uint32 SchemaRevision;
```

초기 구현에서 Unreal reflection 때문에 alias가 불편하면 USTRUCT 내부에 `FName RegionId`, `FName SpeciesId`를 직접 사용한다.

규칙:
- `RegionId`: 예 `Forest_A`
- `SpeciesId`: 예 `Wolf`
- MassEntity handle/Actor pointer는 외부 영속 ID가 아니다.

---

## 2. Environment

```cpp
USTRUCT(BlueprintType)
struct FRegionEnvironmentState
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Temperature = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Humidity = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Rainfall = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float VegetationDensity = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float FoodAvailability = 0.0f;
};
```

단위/정규화는 World와 Server가 합의해 문서화한다.

---

## 3. Player Pressure

기본적으로 `0..1` 정규화된 장기 압력으로 관리한다.

```cpp
USTRUCT(BlueprintType)
struct FPlayerPressureState
{
    GENERATED_BODY()

    float HuntingPressure = 0.0f;
    float EncounterPressure = 0.0f;
    float PursuitPressure = 0.0f;
    float ThreatPressure = 0.0f;
    float IntrusionPressure = 0.0f;
    float RoutePressure = 0.0f;
    float SuppressionPressure = 0.0f;
    float DayPressure = 0.0f;
    float NightPressure = 0.0f;
    float DayHuntingPressure = 0.0f;
    float NightHuntingPressure = 0.0f;
};
```

시간 감쇠 개념:

```text
P_next = alpha * P_prev + (1-alpha) * P_new
```

Raw event를 그대로 LLM에 전달하지 않는다.

---

## 4. Species Trait 그룹

### Phenotype

```cpp
struct FPhenotypeTraits
{
    float BodyScale = 1.0f;
    float LegScale = 1.0f;
    float BodyBoneScale = 1.0f;
    float ColorBrightness = 1.0f;
    float ColorTintStrength = 0.0f;
    float MorphWeight = 0.0f;
};
```

### Gameplay

```cpp
struct FGameplayTraits
{
    float MoveSpeedMultiplier = 1.0f;
    float HealthMultiplier = 1.0f;
    float AttackMultiplier = 1.0f;
};
```

### Behavior

```cpp
struct FBehaviorTraits
{
    float Fear = 0.5f;
    float Aggression = 0.5f;
    float GroupAffinity = 0.5f;
    float HidePreference = 0.5f;
};
```

### Ecology

```cpp
struct FEcologyTraits
{
    float MigrationTendency = 0.0f;
    float RoamRadiusMultiplier = 1.0f;
    float DayActivityPreference = 0.5f;
    float NightActivityPreference = 0.5f;
};
```

MVP에서는 `BodyScale`, `MoveSpeedMultiplier`, `Fear`, `Aggression`만 먼저 사용한다.

---

## 5. Species Evolution Profile

`Region × Species` 단위로 다르게 존재할 수 있다.

```cpp
USTRUCT(BlueprintType)
struct FSpeciesEvolutionProfile
{
    GENERATED_BODY()

    FName RegionId;
    FName SpeciesId;

    int32 Generation = 0;
    uint32 ProfileRevision = 0;

    FPhenotypeTraits Phenotype;
    FGameplayTraits Gameplay;
    FBehaviorTraits Behavior;
    FEcologyTraits Ecology;
};
```

---

## 6. Trait 범위 / Validator 기본안

| Trait | Hard Limit | 초기 MVP 권장 |
|---|---:|---:|
| BodyScale | 0.80 ~ 1.20 | 0.90 ~ 1.10 |
| LegScale | 0.90 ~ 1.10 | 0.95 ~ 1.05 |
| BodyBoneScale | 0.90 ~ 1.10 | 0.95 ~ 1.05 |
| ColorBrightness | 0.70 ~ 1.20 | 0.85 ~ 1.10 |
| ColorTintStrength | 0 ~ 1 | 0 ~ 0.5 |
| MoveSpeedMultiplier | 0.80 ~ 1.25 | 0.90 ~ 1.15 |
| HealthMultiplier | 0.80 ~ 1.25 | 0.90 ~ 1.15 |
| AttackMultiplier | 0.80 ~ 1.25 | 0.90 ~ 1.15 |
| Fear | 0 ~ 1 | 0 ~ 1 |
| Aggression | 0 ~ 1 | 0 ~ 1 |
| GroupAffinity | 0 ~ 1 | 0 ~ 1 |
| HidePreference | 0 ~ 1 | 0 ~ 1 |
| MigrationTendency | 0 ~ 1 | 0 ~ 1 |

세대당 delta limit과 Mutation Budget을 둔다.

```text
sum(abs(delta_i)) <= MutationBudget
```

수치는 DataAsset/Config로 이동 가능하게 설계한다.

---

## 7. Evolution Context

```cpp
struct FEvolutionContext
{
    uint32 WorldEpoch;
    uint32 ContextRevision;

    FName RegionId;
    FName SpeciesId;

    FRegionEnvironmentState Environment;
    FPlayerPressureState Pressure;

    int32 Population;
    int32 Generation;

    FSpeciesEvolutionProfile CurrentProfile;
};
```

추후 필요 시 Population trend, Resource/Risk summary를 추가하되 Mass internals를 직접 포함하지 않는다.

---

## 8. Evolution Proposal

Proposal은 target value보다 delta 중심을 권장한다.

```cpp
struct FEvolutionProposal
{
    uint32 WorldEpoch;
    uint32 ContextRevision;
    uint32 ModelRevision;
    uint32 SchemaRevision;

    // phenotype deltas
    float BodyScaleDelta;
    float LegScaleDelta;
    float BodyBoneScaleDelta;
    float ColorBrightnessDelta;
    float ColorTintStrengthDelta;
    float MorphWeightDelta;

    // gameplay deltas
    float MoveSpeedDelta;
    float HealthDelta;
    float AttackDelta;

    // behavior deltas
    float FearDelta;
    float AggressionDelta;
    float GroupAffinityDelta;
    float HidePreferenceDelta;

    // ecology deltas
    float MigrationDelta;
    float RoamRadiusDelta;
    float DayActivityDelta;
    float NightActivityDelta;
};
```

예 JSON:

```json
{
  "world_epoch": 7,
  "context_revision": 42,
  "model_revision": 3,
  "body_scale_delta": -0.03,
  "leg_scale_delta": 0.02,
  "move_speed_delta": 0.04,
  "fear_delta": 0.07,
  "aggression_delta": -0.05,
  "migration_delta": 0.03,
  "night_activity_delta": 0.05
}
```

---

## 9. Region × Species Runtime State

```cpp
struct FRegionSpeciesState
{
    FName RegionId;
    FName SpeciesId;

    int32 Population;
    FPlayerPressureState Pressure;
    FSpeciesEvolutionProfile EvolutionProfile;

    uint32 SummaryRevision;
};
```

Mass를 사용할 경우 Mass Fragment는 내부 표현이고 이 구조가 외부 서비스/요약 경계가 될 수 있다.

---

## 10. Ecology Event

Player/Creature/World에서 Server Ecology로 전달하는 명시적 사건.

```cpp
enum class EEcologyEventType : uint8
{
    CreatureKilled,
    CreatureDamaged,
    Encounter,
    Pursuit,
    RegionEntered,
    RegionPresence,
    ResourceChanged,
    EnvironmentChanged
};

struct FEcologyEvent
{
    uint64 EventId;
    uint32 WorldEpoch;
    EEcologyEventType Type;
    FName RegionId;
    FName SpeciesId;
    uint64 StableAgentId;
    float Magnitude;
    double SimTimeSeconds;
};
```

EventId는 중복 적용 방지에 사용한다.

---

## 11. Logical Agent Snapshot / Representation Contract

```cpp
struct FLogicalAgentSnapshot
{
    uint64 StableAgentId;
    uint32 WorldEpoch;
    uint32 ControlEpoch;

    FName RegionId;
    FName SpeciesId;
    uint32 ProfileRevision;

    float HP;
    float Energy;
    bool bAlive;

    FVector Position;
};
```

Active Actor 생성/회수 시 필요한 최소 상태를 전달한다.

```cpp
struct FCreatureSpawnData
{
    uint64 StableAgentId;
    uint32 WorldEpoch;
    uint32 ControlEpoch;

    FName RegionId;
    FName SpeciesId;
    int32 Generation;
    uint32 ProfileRevision;

    int32 RandomSeed;
};
```

Creature는 `ProfileRevision`으로 해당 Species Profile을 조회/적용한다.

---

## 12. Network DTO

### Species state

```cpp
struct FReplicatedSpeciesState
{
    FName RegionId;
    FName SpeciesId;
    int32 Generation;
    uint32 ProfileRevision;
    FSpeciesEvolutionProfile Profile;
};
```

### Region summary

```cpp
struct FReplicatedRegionSummary
{
    FName RegionId;
    uint32 WorldEpoch;
    uint32 SummaryRevision;

    int32 Population;
    float Resource;
    float Risk;
    float AverageEnergy;
};
```

개체별로 전체 Species Profile을 반복 복제하지 않는다.

---

## 13. Mass 내부 Fragment 후보

외부 API가 아닌 Server Runtime 내부 타입.

```text
FEcoIdentityFragment
FEcoVitalsFragment
FEcoHabitatFragment
FEcoTravelFragment
FEcoSimulationLODFragment
FEcoRepresentationStateFragment
FEcoLastUpdateFragment
```

종별 immutable/slow-changing 설정은 Shared Fragment 또는 Runtime config table을 검토한다.

Hot data:
- travel/position state
- energy
- current action
- LOD timing

Cold/shared data:
- species fixed config
- habitat preference
- debug metadata

---

## 14. Simulation Policy AI Observation

Creature Evolution Context와 별개 타입이다.

```cpp
struct FSimulationAIObservation
{
    uint64 ObservationId;
    uint32 WorldEpoch;
    uint32 SchemaRevision;

    int32 EntityCount;
    float AverageEnergy;
    float ResourceLevel;
    float RiskLevel;

    int32 ActiveActorCount;
    float ProcessorCostMs;
    float ServerCpuMetric;

    int32 NearLODCount;
    int32 MidLODCount;
    int32 FarLODCount;

    int32 CurrentPolicyId;
};
```

실제 Feature 목록은 Server/AI 담당자가 dataset 생성 전에 확정한다.

Feature마다 반드시 기록:
- 이름
- 의미
- 단위
- valid range
- missing handling
- normalization
- schema version

---

## 15. Simulation Policy Proposal

```cpp
struct FSimulationPolicyProposal
{
    uint64 ObservationId;
    uint32 WorldEpoch;
    uint32 ModelRevision;
    uint32 FeatureSchemaRevision;
    uint32 PolicySchemaRevision;

    int32 SuggestedPolicyId;
    float Confidence;
};
```

Server가 `SuggestedPolicyId`를 실제 LOD/Update config로 매핑한다.

---

## 16. Versioning

Evolution LLM:

```text
EvolutionSchemaRevision
PromptRevision
ModelRevision
ProfileRevision
```

Simulation Policy AI:

```text
FeatureSchemaRevision
PolicySchemaRevision
TrainingDatasetRevision
ModelRevision
```

Server가 기대하는 Schema와 불일치하면 Proposal을 reject/fallback한다.
