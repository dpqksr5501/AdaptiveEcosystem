# 01. Architecture

## 1. 최상위 구조

```text
┌───────────────────────────────┐
│         WORLD / LEVEL         │
│ Region / Weather / DayNight   │
│ Vegetation / Spawn / Shelter  │
└───────────────┬───────────────┘
                │ FRegionEnvironmentState
                ▼
┌───────────────────────────────┐
│  SERVER ECOLOGY / MASS RUNTIME│
│ Authority                     │
│ Event / Pressure              │
│ Population / Resource / Risk  │
│ Energy / Migration            │
│ MassEntity / Simulation LOD   │
│ Representation State          │
└───────┬─────────────────┬─────┘
        │                 │
        │ Evolution       │ Runtime Metrics
        ▼                 ▼
┌───────────────┐   ┌────────────────────┐
│ Evolution LLM │   │ Simulation Policy AI│
│ Trait Delta   │   │ Optional/Research   │
└───────┬───────┘   └──────────┬─────────┘
        │ Proposal             │ Policy Proposal
        ▼                      ▼
┌─────────────────────────────────────┐
│       SERVER VALIDATION / COMMIT    │
│ Trait constraints / epoch / version │
│ policy safety / fallback            │
└───────────────┬─────────────────────┘
                │
                ▼
       FSpeciesEvolutionProfile
                │
        ┌───────┴────────┐
        ▼                ▼
  Mass logical       Active Actor
  population         representation
                         │
                         ▼
                CREATURE RUNTIME
                - Morphology
                - Stats
                - Utility AI
                - Animation
                         │
                         ▼
                     Network
                         │
                         ▼
                       Client
```

---

## 2. Source/Module 전략

부트스트랩 시점에는 기존 프로젝트 구조를 우선한다.

### 기본 권장안

```text
Source/<PrimaryModule>/
├─ Public/
│  ├─ Core/
│  ├─ World/
│  ├─ Ecology/
│  ├─ Evolution/
│  ├─ Creature/
│  ├─ Spawn/
│  ├─ Network/
│  └─ Debug/
└─ Private/
   ├─ World/
   ├─ Ecology/
   ├─ Evolution/
   ├─ Creature/
   ├─ Spawn/
   ├─ Network/
   └─ Debug/
```

### Server 팀의 Runtime Plugin

장원준 담당 영역이 이미 독립 `EcosystemRuntime` Plugin으로 개발되고 있다면 다음 경계를 유지한다.

```text
Plugins/EcosystemRuntime/
  Public/
    EcoTypes
    EcoCommands
    EcoSnapshots
    EcoService
    EcoRepresentationAdapter
  Private/
    Mass/
    Representation/
    Network/
    Profiling/
```

단, 아직 Plugin이 없다면 AI agent가 임의로 Plugin refactor를 먼저 하지 않는다.
**공개 계약을 Mass/게임 코드와 분리하는 것이 우선이며, Plugin 추출은 팀 결정 후 진행한다.**

---

## 3. World 경계

World의 질문:

> 어디에 어떤 환경이 존재하며 Creature가 어디에서 활동할 수 있는가?

권장 구성:

```text
AEcologyRegion
- RegionId
- Bounds / membership
- environment source reference

UWorldEnvironmentSubsystem
- day/night
- weather-facing state
- query environment by RegionId
```

World는 `FRegionEnvironmentState`를 제공하고 Evolution이나 Population을 결정하지 않는다.

---

## 4. Server Ecology / Mass Runtime

Server의 질문:

> 현재 월드의 논리 생태 상태는 무엇이며, 다음 상태를 어떻게 계산할 것인가?

권장 책임:

- World-scoped authoritative service
- Event ingestion
- Pressure accumulation / decay
- `Region × Species` state
- Population
- Resource / Risk / Energy
- Migration
- Mass entity state
- Simulation LOD
- Representation activation state
- Evolution Profile storage
- Summary generation
- Save/Load
- Metrics

### Mass 논리 처리 순서

```text
1. 권위 Input/Event 수신·검증
2. 피해/사망/환경 사건 확정
3. Environment/Position Snapshot
4. Resource Request 생성
5. Chunk/병렬 집계 + 최종 배분
6. Energy 적용
7. LOD 대상 이동/목표 재평가
8. Representation 후보/상태 반영
9. Region/Species Summary + Metrics
10. 필요 시 Evolution trigger / AI observation
```

구조 변경은 Processor 내부에서 무분별하게 즉시 처리하지 않고 deferred command 경계를 따른다.

---

## 5. Mass ↔ Creature Actor Representation

권장 상태:

```text
Logical Agent (Server Runtime / Mass)
- StableAgentId
- SpeciesId
- Region/Habitat
- HP / Energy
- Alive
- Position / travel state
- ProfileRevision
        │
        │ near/important
        ▼
Actor Representation
- ACreatureCharacter
- Collision / interaction
- replication
- Utility AI / animation
```

원칙:

- 동일 Agent를 Mass Entity handle로 식별하지 않는다.
- `StableAgentId`가 전환 전후 유지된다.
- Actor 비활성화 후 HP/Energy/ID가 유실되면 안 된다.
- 같은 Agent의 중복 Actor가 존재하면 안 된다.
- 사망과 activation이 경합하면 Server logical death가 우선한다.
- 필요 시 `ControlEpoch`로 stale update를 거부한다.

초기에는 논리 상태를 Runtime 단일 진실값으로 유지한다.
Actor가 완전한 이동 Authority가 되는 양방향 ownership transfer는 필요한 경우에만 별도 설계한다.

---

## 6. Creature Evolution 경계

Evolution Manager가 만드는 입력:

```text
FEvolutionContext
- RegionId / SpeciesId
- WorldEpoch / ContextRevision
- FRegionEnvironmentState
- FPlayerPressureState
- Population/Summary
- CurrentProfile
- Generation
```

Provider 구조:

```text
IEvolutionDecisionProvider
├─ Dummy / RuleBased
└─ LLM
```

LLM output:

```text
FEvolutionProposal
- Trait deltas
- context identity/revision
- model/prompt revision
- optional confidence/debug code
```

Validator:

- Hard Min/Max
- Max delta per generation
- Mutation Budget
- Species constraint
- Trade-off
- malformed/NaN reject
- stale WorldEpoch/Context reject

Commit 결과:

```text
FSpeciesEvolutionProfile
```

---

## 7. Simulation Policy AI 경계

이 AI는 Evolution LLM과 별개다.

```text
Server Simulation State
+ Runtime Metrics
+ Current Policy
      ↓
FSimulationAIObservation
      ↓
AI Model
      ↓
FSimulationPolicyProposal
      ↓
Server Policy Validator
      ↓
SimulationPolicyId / Config
```

초기에는 AI가 `NearHz`, `FarHz`를 자유롭게 쓰기보다 Server가 정의한 Policy 집합 중 `PolicyId`를 선택하는 방식이 안전하다.

비교 대상:

```text
Fixed
vs Rule-Based LOD
vs AI-Based LOD
```

AI를 쓰는 것 자체가 성공 기준이 아니다.
같은 quality에서 cost 감소 또는 같은 cost에서 quality 향상을 실측해야 한다.

---

## 8. Network

Server only:

- Mass Simulation
- Pressure
- Evolution LLM invocation
- Validation
- Profile Commit
- Simulation Policy commit
- Utility AI authority where gameplay requires

Client에 전달:

### Region/Species 수준 — 저주기

```text
RegionId
SpeciesId
Generation
ProfileRevision
FSpeciesEvolutionProfile
Population/Summary 필요값
```

### Active Actor 수준

```text
StableAgentId
Transform / CharacterMovement
HP / Combat State
Current Action (필요 시)
SpeciesId / ProfileRevision
```

전송하지 않음:

- LLM prompt/raw text
- evolution context internals
- full Utility Score
- all Mass Entity transforms
- AI reasoning/debug payload
- pressure intermediate calculations

늦은 접속/Reset에는 `WorldEpoch`, Revision으로 상태를 구분한다.

---

## 9. Save / Persistence

저장 후보:

- WorldEpoch/Save Revision
- Region long-lived environment state
- Region × Species population
- Pressure accumulated state
- Species Evolution Profile
- Generation / ProfileRevision
- 필요 시 stable logical agent state

저장하지 않아도 되는 순간 상태:

- Utility Scores
- EQS result
- current animation state
- temporary LLM context
- inference queue internals

---

## 10. Debug / Observability

필수적으로 보이게 할 것:

### Creature

```text
StableAgentId
Region / Species
Generation / ProfileRevision
BodyScale / Speed / Fear / Aggression
Current Utility Intent
StateTree State
Representation Mode
```

### Server

```text
Region Population
Resource / Risk / Energy
Pressure
LOD distribution
Active Actor count
Processor cost
WorldEpoch / SummaryRevision
```

### AI

```text
Evolution ContextRevision
Evolution ModelRevision
Proposal Accepted/Rejected + reason
Policy AI ObservationId / ModelRevision / PolicyId
Fallback reason
```
