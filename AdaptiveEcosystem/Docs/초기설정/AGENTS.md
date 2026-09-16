# AGENTS.md

## 0. 목적

이 문서는 이 Unreal Engine 저장소에서 작업하는 모든 AI coding agent의 최상위 지침이다.
코드를 수정하기 전에 반드시 다음 문서를 읽는다.

- `AdaptiveEcosystem/Docs/초기설정/01_ARCHITECTURE.md`
- `AdaptiveEcosystem/Docs/초기설정/02_DATA_CONTRACTS.md`
- `AdaptiveEcosystem/Docs/초기설정/03_TEAM_ROLES.md`
- `AdaptiveEcosystem/Docs/초기설정/08_BOOTSTRAP_PLAN.md`

역할별 작업이라면 해당 역할 문서와 프롬프트도 읽는다.

프로젝트는 **Unreal Engine 5.8 / C++ 중심 동적 생태계 캡스톤 프로젝트**다.
플레이어 행동과 환경 변화가 장기적으로 누적되고, `Region × Species` 단위로 개체 수·분포·Trait·행동 성향·활동 시간·이주 경향이 변화한다.

가장 중요한 책임 경계는 다음과 같다.

> **World는 공간/환경을 제공한다. Ecology/Server는 권위 상태를 유지한다. Evolution LLM은 장기 Trait 변화를 제안한다. Creature Runtime은 검증된 Trait을 실제 몬스터에 표현한다. Network는 확정된 상태만 동기화한다.**

---

## 1. 프로젝트의 두 AI 경계

### A. Creature Evolution LLM — 캡스톤 핵심

입력:
- Region Environment
- Player Pressure
- Population / Migration 상태
- 현재 Species Evolution Profile
- Generation / Revision

출력:
- 지원되는 Trait의 **delta proposal**
- 예: `BodyScaleDelta`, `LegScaleDelta`, `MoveSpeedDelta`, `FearDelta`, `AggressionDelta`, `MigrationDelta`

흐름:

```text
FEvolutionContext
    ↓
Evolution LLM
    ↓
FEvolutionProposal
    ↓
Evolution Validator
    ↓
FSpeciesEvolutionProfile
```

LLM은 Actor를 직접 수정하지 않는다.

### B. Simulation Policy AI — 성능 연구/확장

입력:
- Entity/Population 상태
- Resource/Risk/Energy
- Simulation LOD 분포
- Representation Count
- Server Runtime Metrics
- 현재 Policy

출력:
- `PolicyId` 중심의 `FSimulationPolicyProposal`

흐름:

```text
FSimulationAIObservation
    ↓
Policy AI
    ↓
FSimulationPolicyProposal
    ↓
Server Validator
    ↓
Authoritative Simulation Policy
```

이 AI는 Creature Trait을 결정하지 않는다.
두 AI를 하나의 Proposal 타입이나 모델로 합치지 않는다.

---

## 2. 역할 경계

### World / Level
소유:
- Region 공간 정의
- Environment State 제공
- Weather / Day-Night / Vegetation 연결
- Spawn 가능한 공간
- Shelter / Navigation / World Partition / PCG 연동

소유하지 않음:
- Evolution 결정
- Species Population 정책
- Creature Trait 계산

### Server / Ecology / Mass / Network
소유:
- 서버 권위 생태 상태
- `Region × Species` runtime state
- Player event/pressure 집계
- Population / Resource / Risk / Energy / Migration
- MassEntity 기반 원거리/대규모 논리 Simulation
- Simulation LOD
- MassRepresentation / MassActors 경계
- Stable identity / epoch / revision
- Species Profile 저장
- Replication / Save / Load
- Observation Builder / Dataset Logger / AI Proposal Validation

### AI / LLM
소유:
- Evolution LLM의 input preprocessing / prompt/model / structured proposal
- 필요 시 Simulation Policy AI의 Dataset/Model/Inference
- Model/Schema Revision
- Offline evaluation

소유하지 않음:
- Unreal Actor 직접 수정
- Replication/RPC
- 최종 Authority
- Mass Fragment 직접 mutation

### Creature Runtime / Gameplay / AI / Animation
소유:
- `ACreatureCharacter`
- `UCreatureTraitComponent`
- 최종 Species Profile 적용
- Scale/Bone/Morph/Material 표현
- Gameplay Stats
- Utility AI / StateTree / Perception / EQS
- Animation adaptation
- active Actor debug

Creature는 **왜** Trait이 변했는지 결정하지 않는다.

---

## 3. 권위와 상태 소유권

- 논리 생태 상태는 **Server/Standalone authoritative World**에만 존재한다.
- Client는 복제된 근거리 Actor와 필요한 Region/Species Summary/Profile만 가진다.
- `UWorldSubsystem`은 서비스/상태 소유 후보이지 Replication transport가 아니다.
- Replication은 `GameState`, replicated Actor/Component 등 명시적인 네트워크 객체를 사용한다.
- Mass Entity handle, Actor pointer, ISM instance index를 영속 외부 ID로 노출하지 않는다.
- 장기 논리 ID는 `StableAgentId`, `RegionId`, `SpeciesId`, Revision/Epoch를 사용한다.

---

## 4. 초기 공통 Trait

첫 Vertical Slice에서는 다음 4개만 실제 적용한다.

- `BodyScale`
- `MoveSpeedMultiplier`
- `Fear`
- `Aggression`

확장 예정:

### Phenotype
- BodyScale
- LegScale
- BodyBoneScale
- ColorBrightness
- ColorTintStrength
- MorphWeight (asset이 지원하는 경우)

### Gameplay
- MoveSpeedMultiplier
- HealthMultiplier
- AttackMultiplier

### Behavior
- Fear
- Aggression
- GroupAffinity
- HidePreference

### Ecology
- MigrationTendency
- RoamRadiusMultiplier
- DayActivityPreference
- NightActivityPreference

부트스트랩 단계에서 Wing/Flight, Procedural Mesh, 대규모 Morph 제작, Groom mutation, 새로운 Animation 대량 제작은 하지 않는다.

---

## 5. Mass / Representation 원칙

Server 팀이 Mass를 사용할 경우 다음 원칙을 지킨다.

- Mass는 많은 **논리 개체**를 저비용으로 유지하는 서버 Simulation 계층이다.
- 근거리 상호작용 Creature는 Actor Representation으로 활성화될 수 있다.
- 논리 상태의 기본 진실값은 Runtime/Mass에 둔다.
- Actor는 표시/상호작용 계층이며, 명시적인 ownership transfer를 만들지 않은 한 장기 상태의 단일 진실값이 아니다.
- Representation 전환 전후 `StableAgentId`, HP, Energy, 생존 여부, Species/Profile Revision이 유지되어야 한다.
- 가까운 Actor만 일반 replication 경로를 사용하고, 원거리 모든 Entity transform을 Client에 보내지 않는다.

---

## 6. LLM / AI 공통 원칙

모든 AI는 다음 경계를 따른다.

```text
Server State
  ↓
Observation / Context
  ↓
AI
  ↓
Proposal
  ↓
Server Validation
  ↓
Authoritative Commit
```

필수:
- 비동기 결과의 `ObservationId` 또는 Context Revision 추적
- `WorldEpoch` 검증
- Model/Schema Revision 관리
- timeout/error/failure fallback
- structured output
- Server-side validation

AI failure 시 Simulation이 중단되면 안 된다.

---

## 7. AI coding agent 작업 규칙

1. 저장소 전체를 먼저 확인한다.
2. 실제 `.uproject`, Module, Plugin 구조를 확인한 뒤 기존 구조를 존중한다.
3. 프로젝트명이 이미 있으면 임의 이름을 만들지 않는다.
4. 작은 compile-safe change로 작업한다.
5. 공통 USTRUCT/interface 변경은 문서도 같은 PR에서 수정한다.
6. 외부 Plugin/Library를 사용자 승인 없이 추가하지 않는다.
7. 초기 단계에서 llama.cpp/ONNX/Utility AI plugin/Nav3D를 자동 설치하지 않는다.
8. Mass를 사용하더라도 외부 API에 Mass handle을 노출하지 않는다.
9. Game Thread를 장시간 block하는 AI inference를 만들지 않는다.
10. mutable runtime state를 DataAsset에 저장하지 않는다.
11. Blueprint는 디자이너 연결점으로 사용하되 C++ architecture를 숨기는 용도로 쓰지 않는다.
12. 테스트/디버그 관찰 가능성을 같이 설계한다.
13. 기존 reference 문서의 개인 프로젝트 목표와 팀 프로젝트 핵심 목표를 혼동하지 않는다.

---

## 8. 최초 성공 조건

실제 LLM 없이 다음 데이터 파이프라인이 동작해야 한다.

```text
Forest_A
  +
Wolf
  +
Dummy Species Profile

BodyScale = 0.90
MoveSpeedMultiplier = 1.10
Fear = 0.80
Aggression = 0.20
        ↓
Server authoritative profile
        ↓
Creature Runtime
        ↓
크기/속도 적용 + Fear/Aggression 조회 가능
```

그 뒤 각 파트가 Dummy를 실제 World/Ecology/Mass/LLM/Network 기능으로 교체한다.
