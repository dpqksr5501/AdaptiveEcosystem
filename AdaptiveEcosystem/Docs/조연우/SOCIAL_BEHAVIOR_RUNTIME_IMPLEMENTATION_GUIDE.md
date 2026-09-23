# Social Behavior & Shelter Runtime — AI Coding Agent Implementation Guide

> **Project:** AdaptiveEcosystem  
> **Repository:** `dpqksr5501/AdaptiveEcosystem`  
> **Engine:** Unreal Engine 5.8  
> **Suggested repo path:** `AdaptiveEcosystem/Docs/SocialBehavior/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md`  
> **Audience:** Codex, Antigravity, and other AI coding agents
>
> 이 문서는 `AGENTS.md`와 기존 Active Architecture 문서를 대체하지 않는다.
> 구현 전 반드시 `AGENTS.md` → Active Architecture → Policy Contract → Mass Processor Order를 먼저 읽고,
> 이 문서를 Social Behavior 기능 구현을 위한 추가 지침으로 사용한다.

---

# 0. 핵심 목표

이 작업의 목적은 PPO나 MassFlock을 다시 만드는 것이 아니다.

추가할 핵심 시스템:

```text
1. Dynamic Herd
   - 지속적인 논리적 무리 ID
   - Join / Leave
   - Merge / Split
   - Herd aggregate
   - Representative
   - Regroup

2. Alarm Communication
   - Threat signal
   - Radius / decay / TTL / hop
   - Herd-level aggregation
   - Alert / Panic / Recovery / Regroup

3. Cover / Shelter
   - Shelter registry
   - Nearby candidate query
   - LOS / safety scoring
   - Capacity / slot
   - Reservation / release
```

선택적 고급 기능:

```text
4. Local Avoidance
   - Preferred Velocity → Safe Velocity
   - UE 5.8 Mass built-in 기능을 먼저 평가
   - 부족할 때만 RVO2 / ORCA core 포팅 검토
```

책임 경계:

```text
RL / PPO
= 무엇을 하고 싶은지 결정
  forage / cohesion / flee_dist / cover

Social Behavior Runtime
= 무리, 경보, 은신처 등 사회적/환경적 실행 문맥 결정

MassFlock / Movement
= 실제 local flock steering 및 이동 실행
```

**MassFlock은 다른 팀원 담당이다.**
본 작업에서 MassFlock을 재구현하거나 소유권을 가져오지 않는다.

---

# 1. 현재 Repository에서 확인된 사실

## 1.1 Unreal Project

실제 Unreal 프로젝트 루트:

```text
AdaptiveEcosystem/
```

프로젝트 파일:

```text
AdaptiveEcosystem/AdaptiveEcosystem.uproject
```

현재 `EngineAssociation`:

```text
5.8
```

현재 활성 Mass 관련 Plugin:

```text
MassGameplay
MassAI
```

현재 Runtime module:

```text
AdaptiveEcosystem
```

새 Runtime module을 추가할 특별한 이유가 없다면 기존 단일 모듈을 유지한다.

---

## 1.2 현재 Mass 데이터 계약

현재 파일:

```text
AdaptiveEcosystem/Source/AdaptiveEcosystem/Mass/EcoMassFragments.h
```

이미 존재하는 주요 per-agent Fragment:

```text
FEcoIdentityFragment
- StableAgentId
- SpeciesId
- SpeciesRuntimeIndex

FEcoVitalsFragment
- HP
- MaxHP
- Energy
- MaxEnergy

FEcoRegionFragment
- CurrentRegionId
- CurrentRegionIndex

FEcoTravelFragment
- TargetRegionId
- TargetRegionIndex
- TravelProgress
- bIsTraveling

FEcoObservationFragment
- FEcoPolicyObservationV1

FEcoPolicyOutputFragment
- FEcoPolicyActionV1

FEcoPolicyRuntimeFragment
- LastPolicyStep
- NextPolicyStep
- ModelRevision
```

현재 Species Shared Fragment:

```text
FEcoSpeciesSharedFragment
- BaseMoveSpeed
- EnergyDecayRate
- FoodConsumptionRate
- FoodEnergyGain
- ViewDistance
- FOV
- CoverSearchRadius
- MigrationThreshold
```

현재 Tags:

```text
FEcoAliveTag
FEcoMigratingTag
```

### 절대 중복 생성하지 말 것

Social Behavior 구현 시 아래 값을 새로운 Fragment에 또 만들지 않는다.

```text
StableAgentId
SpeciesId
SpeciesRuntimeIndex
HP / Energy
Region
ViewDistance
FOV
CoverSearchRadius
PPO Observation
PPO Action
```

기존 Fragment를 읽어 사용한다.

---

## 1.3 현재 Policy Contract

현재 파일:

```text
AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoPolicyContracts.h
AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V1.md
```

Policy V1:

```text
Observation: 7
Action: 4
Network: 7 → 64 → 64 → 4
```

Observation:

```text
0 food_density
1 predator_count
2 predator_distance
3 conspecific_count
4 energy
5 recent_predation
6 cover_distance
```

Action:

```text
0 forage
1 cohesion
2 flee_dist
3 cover
```

### 임의 변경 금지

다음 변경은 Social Behavior 구현 범위가 아니다.

```text
Observation 7 → 8
Action 4 → 5
새로운 alarm observation 추가
새로운 herd action 추가
새 PPO output 추가
기존 feature 순서 변경
정규화 방식 변경
```

필요성이 발견되면 구현하지 말고 RL 담당자에게 Contract Change Request로 남긴다.

---

# 2. AI Agent 작업 원칙

## 2.1 먼저 읽고 수정한다

코드 작업 시작 전 최소 다음 파일을 읽는다.

```text
/AGENTS.md

AdaptiveEcosystem/Docs/Architecture/
  PPO_MASS_ECOSYSTEM_ARCHITECTURE.md

AdaptiveEcosystem/Docs/RL_Policy/
  POLICY_CONTRACT_V1.md

AdaptiveEcosystem/Docs/Mass/
  MASS_PROCESSOR_ORDER.md

AdaptiveEcosystem/Docs/Integration/
  THIRD_PARTY_INTEGRATION.md

AdaptiveEcosystem/Source/AdaptiveEcosystem/
  Core/
  Mass/
  AI/Policy/
```

그리고 현재 branch에서 다른 팀원이 이미 추가한:

```text
MassFlock integration
Steering Processor
Spatial Hash / Grid
Preferred Velocity
Movement Fragment
```

관련 코드가 있는지 반드시 다시 검색한다.

**이 문서에 적힌 클래스 후보보다 현재 Repository가 우선이다.**

---

## 2.2 작은 Compile-safe 단계로 작업한다

한 번에 Herd + Alarm + Cover 전체를 구현하지 않는다.

권장 작업 단위:

```text
Change 0 : Source audit + 문서 보정
Change 1 : Social data contracts only
Change 2 : Herd MVP
Change 3 : Herd aggregate + hysteresis
Change 4 : Alarm MVP
Change 5 : Alarm herd integration
Change 6 : Shelter registry + authored shelter
Change 7 : Shelter query
Change 8 : Reservation
Change 9 : Merge / Split / Regroup
Change 10: Optional avoidance evaluation
```

각 단계는 그 자체로 빌드되어야 한다.

---

# 3. 권장 Source Directory 구조

현재 단일 Runtime module을 유지하면서 다음 구조를 우선 검토한다.

```text
AdaptiveEcosystem/Source/AdaptiveEcosystem/
└─ AI/
   └─ Social/
      ├─ EcoSocialTypes.h
      ├─ EcoSocialFragments.h
      │
      ├─ Herd/
      │  ├─ EcoHerdTypes.h
      │  ├─ EcoHerdSubsystem.h/.cpp
      │  ├─ EcoHerdMembershipProcessor.h/.cpp
      │  └─ EcoHerdAggregateProcessor.h/.cpp
      │
      ├─ Alarm/
      │  ├─ EcoAlarmTypes.h
      │  ├─ EcoAlarmEmitProcessor.h/.cpp
      │  ├─ EcoAlarmPropagationProcessor.h/.cpp
      │  └─ EcoSocialResponseProcessor.h/.cpp
      │
      └─ Shelter/
         ├─ EcoShelterTypes.h
         ├─ EcoShelterSubsystem.h/.cpp
         ├─ EcoShelterAnchor.h/.cpp
         ├─ EcoShelterQueryProcessor.h/.cpp
         └─ EcoShelterReservationProcessor.h/.cpp
```

Optional:

```text
AI/Social/Avoidance/
```

초기 MVP에서는 파일 수를 줄이기 위해 다음 정도로 합쳐도 된다.

```text
AI/Social/
├─ EcoSocialFragments.h
├─ EcoHerdSubsystem.h/.cpp
├─ EcoHerdProcessors.h/.cpp
├─ EcoAlarmProcessors.h/.cpp
├─ EcoShelterSubsystem.h/.cpp
└─ EcoShelterProcessors.h/.cpp
```

클래스가 작고 책임이 명확할 때만 분리한다.

---

# 4. 데이터 소유권 설계

## 4.1 Per-agent 데이터

Per-agent로 달라지는 값만 Fragment에 둔다.

후보:

```cpp
USTRUCT()
struct FEcoHerdMemberFragment : public FMassFragment
{
    GENERATED_BODY()

    int32 HerdRuntimeIndex = INDEX_NONE_ECO;
    float MembershipConfidence = 0.0f;
};
```

```cpp
UENUM()
enum class EEcoSocialState : uint8
{
    Calm,
    Alert,
    Panic,
    Recovering,
    Regrouping
};
```

```cpp
USTRUCT()
struct FEcoAlarmStateFragment : public FMassFragment
{
    GENERATED_BODY()

    uint64 LastSignalId = 0;
    FVector LastThreatPosition = FVector::ZeroVector;
    float AlarmStrength = 0.0f;
    EEcoSocialState State = EEcoSocialState::Calm;
};
```

```cpp
UENUM()
enum class EEcoShelterIntentState : uint8
{
    None,
    Searching,
    Reserved,
    Moving,
    Occupied
};
```

```cpp
USTRUCT()
struct FEcoShelterIntentFragment : public FMassFragment
{
    GENERATED_BODY()

    int32 TargetShelterIndex = INDEX_NONE_ECO;
    int32 TargetSlotIndex = INDEX_NONE_ECO;
    float CurrentScore = 0.0f;
    float NextQueryTime = 0.0f;
    EEcoShelterIntentState State = EEcoShelterIntentState::None;
};
```

### 중요한 원칙

상태가 자주 변한다고 Tag를 반복 추가/제거하지 않는다.

```text
CalmTag → AlertTag → PanicTag → RecoveryTag
```

같은 구조는 Archetype churn을 만들 수 있다.

Social State처럼 자주 변하는 상태는 고정 Fragment 내부 enum/값을 우선한다.

---

## 4.2 Species 공통 설정

Species마다 동일한 Social parameter는 Shared Fragment 후보이다.

```cpp
USTRUCT()
struct FEcoSocialSpeciesSharedFragment : public FMassSharedFragment
{
    GENERATED_BODY()

    float HerdJoinRadius;
    float HerdLeaveRadius;
    float HerdMergeRadius;

    float JoinDwellTime;
    float LeaveDwellTime;

    float AlarmRadius;
    float AlarmDistanceDecay;
    float AlarmTimeDecay;
    uint8 MaxAlarmHop;

    int32 MaxHerdNeighborCandidates;
};
```

단, 기존 `FEcoSpeciesSharedFragment`에 이미 존재하는:

```text
ViewDistance
FOV
CoverSearchRadius
```

를 다시 추가하지 않는다.

---

## 4.3 Herd global runtime

Herd 전체 정보를 모든 Entity에 복제하지 않는다.

후보 POD:

```cpp
struct FEcoHerdRuntimeData
{
    int32 RuntimeIndex = INDEX_NONE_ECO;
    int64 PersistentHerdId = 0;

    FVector Center = FVector::ZeroVector;
    FVector AverageVelocity = FVector::ZeroVector;

    FMassEntityHandle Representative;
    int32 MemberCount = 0;

    float AlarmStrength = 0.0f;
    FVector LastThreatPosition = FVector::ZeroVector;

    double LastAggregateTime = 0.0;
    double LastTopologyUpdateTime = 0.0;
};
```

Hot-path에서는:

```text
HerdRuntimeIndex
```

를 사용하고,

디버깅/로그/장기 식별에는:

```text
PersistentHerdId
```

를 사용한다.

---

# 5. Subsystem과 Mass Worker Thread 경계

기존 `MASS_PROCESSOR_ORDER.md` 원칙을 반드시 따른다.

## 금지

Entity loop 안에서 다음을 직접 반복 호출/수정하지 않는다.

```text
UWorldSubsystem
AActor
global TMap write
Cover Actor
Herd UObject
```

잘못된 형태:

```cpp
EntityQuery.ForEachEntityChunk(...,
{
    for (...)
    {
        SocialSubsystem->HerdMap.Find(...);
        SocialSubsystem->ReserveCover(...);
    }
});
```

## 권장

### Pattern A — Read snapshot

Processor 시작 시 필요한 read-only snapshot을 확보하고
Entity tight loop에서는 POD/array만 읽는다.

### Pattern B — Proposal + Reconciliation

병렬 계산:

```text
Entity
→ Join Proposal
→ Alarm Proposal
→ Shelter Reservation Proposal
```

안전한 단계:

```text
Proposal
→ Conflict Resolution
→ Runtime Table Update
```

다음 단계/프레임에서 결과를 Entity Fragment로 반영한다.

이 패턴을 다음에 우선 적용한다.

```text
Herd Join / Merge
Shelter Reservation
Alarm cross-herd broadcast
```

---

# 6. Shared Spatial Query 원칙

Dynamic Herd, Alarm, Optional Avoidance가 모두 neighbor search를 필요로 한다.

각 시스템이 별도 spatial data structure를 만들지 않는다.

금지:

```text
HerdGrid
AlarmGrid
AvoidanceGrid
MassFlockGrid
```

가 각각 독립 존재.

우선순위:

```text
1. 현재 branch의 MassFlock / Movement 구현 확인
2. UE 5.8 MassNavigation / MassMovement / MassCrowd 확인
3. 기존 spatial neighbor lookup 재사용 가능성 확인
4. 불가능할 때만 Social 전용 spatial index 검토
```

새 Spatial Query를 만들 경우에도 하나의 shared index를 여러 Social Processor가 사용하게 한다.

---

# 7. Dynamic Herd 구현 사양

## 7.1 Herd와 Flock의 구분

```text
Herd
= 지속적인 논리적 사회 그룹

Flock
= local movement / steering
```

Social Runtime 소유:

```text
Herd ID
Membership
Join / Leave
Merge / Split
Aggregate
Representative
Threat State
Regroup
```

MassFlock 담당자 소유:

```text
Cohesion
Alignment
Separation
실제 local steering
```

Social code에서 동일한 Cohesion force를 다시 계산하지 않는다.

---

## 7.2 Herd MVP

첫 완료 목표:

```text
100 Mass Entity
→ 근접한 같은 Species를 여러 Herd로 분류
→ Herd ID가 일정 시간 유지
→ Join / Leave 안정 동작
→ Herd Center / Average Velocity / MemberCount 계산
```

필수:

```text
Same Species Filter
JoinRadius
LeaveRadius
Join Dwell
Leave Dwell
HerdRuntimeIndex
PersistentHerdId
```

---

## 7.3 Hysteresis

반드시:

```text
JoinRadius < LeaveRadius
```

또는 동등한 hysteresis를 사용한다.

거리뿐 아니라 dwell time도 사용한다.

---

## 7.4 Update frequency

Herd topology는 Movement보다 느리게 갱신한다.

```text
Movement / steering : high frequency
Herd aggregate      : medium frequency
Herd membership     : low frequency
Merge / Split       : lower frequency
```

hard-coded frame count보다 simulation time / configurable interval을 우선한다.

---

## 7.5 Aggregate

금지:

```text
for each entity
  for each herd member
```

권장:

```text
Pass 1
Entity → Herd accumulator

Pass 2
Accumulator → FEcoHerdRuntimeData
```

계산:

```text
Center
Average Velocity
MemberCount
Representative
```

---

## 7.6 Representative

초기에는 Behavioral Leader를 만들지 않는다.

Representative 역할:

```text
Herd-level query 대표
Debug representative
향후 Shelter group query 대표
향후 Alarm aggregate 대표
```

MVP 대표 선정:

```text
Herd center와 가까운 Alive Entity
```

정도로 충분하다.

---

## 7.7 Merge / Split

MVP 완료 후 구현한다.

Merge 판단:

```text
same species
center distance
heading compatibility
relative velocity
merge dwell time
```

Split 판단:

```text
Herd spread 초과
→ candidate herd만 connectivity 검사
→ 실제 component 분리 시 split
```

전체 World graph를 매 tick 구성하지 않는다.

---

# 8. Alarm Communication 구현 사양

## 8.1 목표

```text
Threat detected
→ Alarm Signal
→ Same Herd
→ Nearby Herd
→ Social Response
```

---

## 8.2 Policy Contract 유지

Alarm을 새 Observation으로 추가하지 않는다.

초기 구현:

```text
PPO Action
+
Social Modifier
```

우선순위:

```text
1. Existing PPO output amplification
2. Runtime target resolution
3. Extreme condition only: emergency override
```

---

## 8.3 Alarm signal

후보:

```cpp
struct FEcoAlarmSignal
{
    uint64 SignalId = 0;
    FEcoAgentId SourceAgentId = 0;

    FVector ThreatPosition = FVector::ZeroVector;
    float InitialStrength = 0.0f;

    double CreatedTime = 0.0;
    double ExpireTime = 0.0;

    uint8 HopCount = 0;
};
```

장기 identity에 `FMassEntityHandle`을 사용하지 않는다.

---

## 8.4 Decay

개념:

\[
S_{recv}
=
S_0 e^{-lpha d}
e^{-eta \Delta t}
\gamma^h
\]

- distance attenuation
- time attenuation
- hop attenuation

매 tick global strength를 계속 write하기보다 원본 strength + timestamp에서 현재 값을 계산하는 방식을 우선 검토한다.

---

## 8.5 Deduplication

초기:

```text
LastSignalId
```

또는 작은 fixed-size recent signal ring buffer.

Entity마다 무제한 `TSet<uint64>`를 만들지 않는다.

---

## 8.6 Herd-level propagation

Herd가 구현된 이후:

```text
Individual
→ Herd Threat State
→ Nearby Herd
→ Member
```

형태를 우선한다.

---

# 9. Cover / Shelter 구현 사양

## 9.1 이름

내부 Runtime 명칭은 가능하면 `Shelter`를 우선한다.

Policy Contract의 `Cover` 명칭은 기존 계약이므로 그대로 유지한다.

---

## 9.2 CoverDistance 의미를 임의 변경하지 않는다

현재 Policy Contract:

```text
nearest cover / shelter distance
normalized by CoverSearchRadius
```

Social Runtime 내부에서:

```text
nearest available reserved slot
nearest best-scored LOS-valid slot
```

로 의미를 조용히 바꾸지 않는다.

필요하다면:

```text
Policy CoverDistance
```

와

```text
Runtime SelectedShelter
```

를 별도 개념으로 유지한다.

---

## 9.3 MVP는 authored shelter

자동 NavMesh cover generation부터 만들지 않는다.

Level authoring용 lightweight actor 후보:

```cpp
AEcoShelterAnchor
```

역할:

```text
Editor에서 위치/방향/quality/capacity authoring
BeginPlay 시 Shelter Registry 등록
Runtime Creature마다 Actor reference를 보유하지 않음
```

등록 후 Runtime은 compact POD data를 사용한다.

---

## 9.4 Shelter data

```cpp
struct FEcoShelterPoint
{
    int32 RuntimeIndex = INDEX_NONE_ECO;
    FVector Position = FVector::ZeroVector;
    FVector SurfaceNormal = FVector::ZeroVector;

    float Quality = 1.0f;
    int32 Capacity = 1;
};
```

Reservation 단위:

```cpp
struct FEcoShelterSlot
{
    int32 ShelterRuntimeIndex = INDEX_NONE_ECO;
    int32 SlotIndex = INDEX_NONE_ECO;

    FVector Position = FVector::ZeroVector;

    FEcoAgentId ReservedBy = 0;
    double ReservationExpireTime = 0.0;
};
```

Runtime slot을 UObject/Actor per slot로 만들지 않는다.

---

## 9.5 Query pipeline

```text
Creature needs shelter
↓
Nearby candidate lookup
↓
Cheap filter
  distance
  capacity
  coarse availability
↓
Expensive checks
  LOS
  path/reachability if available
  threat-relative safety
↓
Score
↓
Reservation Proposal
↓
Conflict Resolution
↓
Target shelter / slot assigned
```

모든 Entity × 모든 Shelter에 line trace하지 않는다.

---

## 9.6 LOS

매 frame 재평가하지 않는다.

재평가 조건 후보:

```text
Threat position changed enough
Creature moved enough
Shelter cache expired
Reservation expired
```

---

## 9.7 Scoring

예:

\[
Score(c)
=
w_o Occlusion
-
w_d Distance
+
w_q Quality
+
w_a Availability
-
w_p CrowdingPenalty
\]

weight는 나중에 config/shared data로 이동 가능하게 설계한다.
MVP에서 과도한 generic scoring framework를 만들지 않는다.

---

## 9.8 Reservation

병렬 worker가 global reservation table을 직접 동시에 수정하지 않는다.

```text
Query Processor
→ Reservation Proposal

Reservation Reconciliation
→ deterministic winner

Apply Result
→ Target slot Fragment
```

Tie break:

```text
higher score
→ shorter distance
→ lower StableAgentId
```

---

# 10. MassFlock / Movement Integration Boundary

Social Runtime은 필요한 경우 의도 데이터만 제공한다.

후보:

```text
HerdRuntimeIndex
GroupTargetDirection
SocialCohesionModifier
ThreatPosition
SelectedShelterPosition
ShelterIntentStrength
```

실제 계약은 현재 MassFlock 담당 코드가 merge된 후 audit한다.

금지:

```text
MassFlock Processor 복제
MassFlock Cohesion force 중복 계산
MassFlock source 임의 대규모 변경
```

필요한 interface가 없으면 최소한의 adapter/interface 변경만 제안한다.

---

# 11. Local Avoidance — Optional

Herd/Alarm/Shelter가 완성된 뒤 검토한다.

```text
Preferred Velocity
→ Local Avoidance
→ Safe Velocity
```

Local Avoidance는 목표를 다시 결정하지 않는다.

구현 순서:

```text
1. UE 5.8 MassNavigation / MassMovement / MassCrowd source audit
2. 현재 팀의 MassFlock avoidance 확인
3. 기존 기능 만족 여부 평가
4. 부족할 때만 Custom algorithm 고려
```

RVO2 / ORCA를 포팅할 경우:

```text
KEEP
ORCA constraint math
linear solver
preferred velocity projection

REPLACE
RVO2 Agent
RVOSimulator
KdTree
position integration
```

외부 코드 복사 전 라이선스를 검증하고 `THIRD_PARTY_NOTICES.md`를 갱신한다.

---

# 12. Third-party / OSS 정책

현재 프로젝트 `THIRD_PARTY_NOTICES.md`에는:

```text
MassFlock
Aquarium
Stable-Baselines3
DynamicWeather
```

가 등록되어 있다.

Social Behavior 참고 후보:

```text
OpenSteer / Reynolds
ARGoS3
CoverGenerator-UE4
RVO2
DetourCrowd / Recast
HRVO
```

원칙:

```text
참고와 실제 코드 도입을 구분
외부 Source 복사/수정 전 현재 LICENSE 확인
라이선스 불명확 시 코드 복사 금지
실제 도입 시 THIRD_PARTY_NOTICES.md 갱신
Docs/Integration/THIRD_PARTY_INTEGRATION.md 갱신
```

MassFlock은 다른 팀원 담당 Movement 계층이다.

---

# 13. Processor Order 통합

현재 Active Mass 순서:

```text
Environment / Region
Observation
Policy
Steering
Movement
Interaction
Vitals / Lifecycle
Migration
Aggregation
Representation / LOD
```

Social Runtime 논리 위치:

```text
Environment / Region

Observation
Policy

Herd Membership
Herd Aggregate
Alarm Emit / Propagate
Social Response
Shelter Query / Reservation

Steering / MassFlock
Movement

Interaction
Vitals / Lifecycle
...
```

실제 Execution Group 이름과 prerequisite API는 UE 5.8 및 현재 branch 코드를 확인한 뒤 결정한다.

존재하지 않는 Processor Group 이름을 문서만 보고 임의 생성하지 않는다.

---

# 14. Update Rate / Simulation LOD

모든 Social Processor를 매 frame 실행하지 않는다.

```text
High frequency
- Movement
- Steering
- Optional local avoidance

Medium frequency
- Herd aggregate
- Alarm response

Low frequency
- Herd membership
- Merge / Split
- Shelter re-query
- Representative election
```

Far LOD:

```text
Individual alarm broadcast
→ Herd-level threat only

Individual shelter query
→ representative/group-level query 후보

Frequent membership
→ low-frequency topology update
```

정확한 주기는 Profiling으로 결정한다.

---

# 15. 성능 원칙

## 금지

```text
O(N^2) all-pairs search
per-agent UObject AI
per-agent EQS query
per-agent TMap allocation
per-tick TArray allocation in hot loop
per-entity global TMap write
every-frame LOS for every shelter
```

## 권장

```text
bounded neighbor count
shared spatial partition
compact runtime index
preallocated buffers
dense arrays
two-pass reduction
proposal/reconciliation
staggered update
Simulation LOD
```

---

# 16. Determinism / Debugging

같은 입력에서는 가능한 한 같은 결과를 만든다.

특히:

```text
Herd assignment
Reservation winner
Representative selection
```

에서 iteration order에만 의존하지 않는다.

Tie break:

```text
StableAgentId
PersistentHerdId
```

등을 사용한다.

Debug 로그에는 pointer 주소보다:

```text
StableAgentId
SpeciesId
HerdId
ShelterIndex
SignalId
```

를 사용한다.

---

# 17. 테스트 전략

## Herd

```text
JoinRadius 안에서 가입
LeaveRadius 밖에서 탈퇴
Hysteresis 영역에서 membership 유지
Representative death 시 재선정
StableAgentId tie-break deterministic
```

## Alarm

```text
거리 증가 → strength 감소
시간 증가 → strength 감소
TTL 이후 무효
MaxHop 이후 전파 중단
동일 SignalId 중복 처리 방지
```

## Shelter

```text
Nearby candidate query
LOS-safe shelter 선택
동일 slot 경쟁
deterministic reservation winner
TTL release
dead agent reservation cleanup
```

## Functional demo

```text
100 logical entities
2+ herds
1 threat source
3+ shelter clusters

normal herd
→ threat
→ alarm propagation
→ panic / shelter selection
→ threat clear
→ recovery / regroup
```

---

# 18. Definition of Done

## Phase 0 — Audit

```text
현재 Mass/Movement/Spatial 코드 경로 확인
중복 생성하면 안 되는 타입 목록 정리
MassFlock 담당자의 interface 확인
Policy V1 변경 없음 확인
```

## Phase 1 — Social Data Foundation

```text
새 Fragment / enum / runtime POD compile
기존 Fragment와 값 중복 없음
frequent state를 tag로 만들지 않음
```

## Phase 2 — Herd MVP

```text
100 Entity에서 Herd ID 생성
Join / Leave
Hysteresis
Center
Average Velocity
MemberCount
Representative
```

## Phase 3 — Alarm MVP

```text
Signal 생성
TTL
distance/time decay
dedup
same-herd propagation
PPO schema 변경 없음
```

## Phase 4 — Shelter MVP

```text
Authored Shelter Anchor
runtime registry
nearby query
basic LOS check
reservation
release
```

## Phase 5 — Recommended

```text
Herd Merge / Split
Panic / Recovery / Regroup
Herd-level alarm aggregate
Cover capacity
LOS cache
LOD update rates
```

## Phase 6 — Advanced Optional

```text
Automatic cover generation
Group shelter assignment
Custom ORCA
Advanced fission/fusion herd model
```

---

# 19. AI Agent가 하지 말아야 할 것

```text
1. PPO Observation / Action 임의 변경
2. Legacy Evolution 코드 의존
3. per-creature Actor AI 생성
4. MassFlock 재구현
5. 여러 Spatial Grid 중복 생성
6. Shared Fragment에 per-agent mutable social state 저장
7. Social state를 자주 바뀌는 MassTag로 모델링
8. Entity hot loop에서 UObject global state 직접 수정
9. 모든 기능을 한 작업에서 구현
10. 빌드 확인 없이 다음 단계 진행
11. README만 보고 OSS source 복사
12. LICENSE 미확인 외부 코드 복사
13. 자동 Cover generation을 MVP보다 먼저 구현
14. Custom ORCA를 UE 내장 avoidance 조사보다 먼저 구현
```

---

# 20. Agent 작업 결과 보고 형식

각 작업 완료 후:

```text
## Changed
- 수정/추가 파일
- 구현 기능

## Architecture Decisions
- 새로 결정한 책임 경계
- 재사용한 기존 타입/API

## Did Not Change
- PPO Contract
- MassFlock ownership
- Region contract
- Lifecycle contract

## Validation
- Build result
- Test result
- Unreal Editor runtime result

## Performance Notes
- Entity count
- Processor timing
- allocation / query concerns

## Follow-up
- 다음 단계
- 팀 합의가 필요한 부분
```

---

# 21. Compile / Validation

`AGENTS.md` 규칙에 따라 변경 후 UnrealBuildTool 빌드를 수행한다.

Target:

```text
AdaptiveEcosystemEditor
Win64
Development
```

Agent가 로컬 UE 경로를 모르면 임의 경로를 만들지 않는다.

컴파일 실패 상태에서 다음 기능 단계로 진행하지 않는다.

---

# 22. 첫 작업 — TASK 0 Source Audit

이 문서를 받은 AI Agent는 바로 Herd 코드를 만들지 않는다.

먼저:

```text
TASK 0 — Social Runtime Source Audit
```

을 수행한다.

요구사항:

1. 현재 branch `Source/AdaptiveEcosystem/` 전체 조사
2. 다음 키워드의 기존 구현 검색

```text
Mass
Movement
Navigation
Flock
Steering
Spatial
Velocity
Avoidance
Processor
Fragment
```

3. 다음 질문에 답한다.

```text
A. 현재 Creature 위치는 어떤 Fragment에서 읽는가?
B. 현재 Velocity는 어떤 Fragment에서 읽는가?
C. FEcoIdentityFragment를 모든 Social Entity가 보유하는가?
D. 같은 Species neighbor query를 재사용할 수 있는가?
E. MassFlock 담당 코드가 현재 branch에 merge되어 있는가?
F. Herd가 Movement에 전달할 최소 interface는 무엇인가?
G. Preferred Velocity가 현재 존재하는가?
H. UE5.8 built-in Mass avoidance가 현재 프로젝트에서 사용 가능한가?
```

4. Audit 결과를 이 문서의 `Implementation Audit` 섹션 또는 별도 문서에 기록
5. 후보 클래스명을 실제 Repository 구조에 맞게 보정
6. 그 이후에만 Herd MVP 구현 시작

---

# 23. TASK 1 — Herd MVP

Audit 이후:

```text
Persistent Dynamic Herd MVP
```

범위:

```text
FEcoHerdMemberFragment
Social species config
Herd runtime storage
Membership processor
Aggregate processor
Representative selection
```

하지 않을 것:

```text
Alarm
Cover
Merge / Split
Leader following
ORCA
```

테스트:

```text
100개의 같은 Species Entity가
공간적으로 2~4개 그룹으로 나뉘어 있을 때
안정적인 Herd ID를 유지한다.
```

---

# 24. TASK 2 — Alarm MVP

Herd 이후:

```text
Alarm signal
TTL
decay
dedup
same-herd propagation
SocialState
```

PPO Contract 변경 금지.

---

# 25. TASK 3 — Shelter MVP

Alarm 이후:

```text
AEcoShelterAnchor
Shelter registry
Nearby query
basic LOS
slot reservation
release
```

자동 Cover Generation은 하지 않는다.

---

# 26. TASK 4 — Integration

최종:

```text
PPO Action
↓
Social Runtime
↓
Herd / Alarm / Shelter intent
↓
MassFlock / Movement interface
```

MassFlock implementation 자체를 Social ownership으로 이동하지 않는다.

---

# 27. 추가 확장 판단 기준

새 기능 추가 전:

```text
이 기능이 Social Runtime 책임인가?
기존 Policy Contract를 변경하는가?
다른 팀원의 Source of Truth를 복제하는가?
MassEntity data-oriented 구조를 유지하는가?
100 → 500 → 1000 Entity로 확장 가능한가?
MVP보다 구현 가치가 높은가?
```

명확하지 않으면 먼저 설계 문서화 후 구현을 보류한다.

---

# 28. 현재 main 기준 특히 주의할 점

현재 확인된 사실:

```text
EcoMassFragments.h:
Identity / Vitals / Region / Travel /
Observation / Policy Output / Policy Runtime 존재

FEcoSpeciesSharedFragment:
ViewDistance / FOV / CoverSearchRadius 존재

Build.cs:
MassCore
MassEntity
MassCommon
MassMovement
MassSpawner
MassNavigation
MassSimulation
MassLOD
MassRepresentation
MassActors
이미 dependency에 포함
```

따라서 기존 Mass dependency와 타입을 먼저 재사용한다.

Active Architecture 문서에는 MassNavigation HashGrid와 MassFlock Steering 계층이 설계되어 있으나,
문서만 보고 해당 Processor가 현재 branch에 이미 구현되어 있다고 가정하지 않는다.

**Source가 사실의 최종 기준이다.**

---

# 29. 문서 우선순위

충돌 시:

```text
1. 현재 컴파일 가능한 Source
2. Root AGENTS.md의 불변 원칙
3. POLICY_CONTRACT_V1.md
4. PPO_MASS_ECOSYSTEM_ARCHITECTURE.md
5. MASS_PROCESSOR_ORDER.md
6. 이 문서
7. 기술조사 / 아이디어 문서
8. Legacy Evolution 문서
```

Source와 Active Contract가 명백히 충돌하면 조용히 한쪽을 선택하지 말고 불일치를 보고한다.

---

# 30. 최종 목표

```text
Creature Social Behavior Runtime

Dynamic Herd
- persistent membership
- join / leave
- merge / split
- representative
- regroup

Alarm Communication
- signal
- radius
- decay
- TTL
- dedup
- herd aggregation
- panic / recovery

Shelter
- authored shelter registry
- spatial query
- LOS
- scoring
- capacity
- reservation

Optional
- preferred velocity → safe velocity avoidance
```

책임은 그대로 유지한다.

```text
RL owns:
Observation / Action / Reward / PPO

Mass/Ecology owns:
Vitals / Lifecycle / Population / Region

MassFlock owner owns:
Local flock steering / movement implementation

Social Runtime owns:
Logical social grouping, danger communication,
and shelter resolution
```

---

# 31. Implementation Audit

> AI Agent가 실제 작업 branch를 검사한 후 갱신한다. 추측으로 채우지 않는다.

```text
Audit Date:
Branch / Commit:

Current Position Fragment:
Current Velocity Fragment:
Current Steering Fragment:
Current Spatial Query:
Current MassFlock Integration:
Current Preferred Velocity:
Current Avoidance:
Current Processor Groups:

Reusable Existing Types:

Required New Types:

Required Cross-team Interface:

Known Risks:
```

---

# 32. Source Basis

이 문서는 다음 현재 Repository 자료와 Social Behavior 기술조사 결과를 기준으로 작성되었다.

```text
/AGENTS.md

AdaptiveEcosystem/Source/AdaptiveEcosystem/Mass/EcoMassFragments.h
AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoPolicyContracts.h
AdaptiveEcosystem/Source/AdaptiveEcosystem/Core/EcoIds.h
AdaptiveEcosystem/Source/AdaptiveEcosystem/AdaptiveEcosystem.Build.cs

AdaptiveEcosystem/Docs/Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md
AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V1.md
AdaptiveEcosystem/Docs/Mass/MASS_PROCESSOR_ORDER.md
AdaptiveEcosystem/Docs/Integration/THIRD_PARTY_INTEGRATION.md

/THIRD_PARTY_NOTICES.md

AdaptiveEcosystem Social & Navigation Behavior Runtime 기술조사 보고서
```

이 문서의 후보 클래스명은 구현 완료 사실을 의미하지 않는다.
실제 Source Audit 이후 현재 branch에 맞춰 조정한다.
