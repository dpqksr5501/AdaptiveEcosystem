# AdaptiveEcosystem — Monster + Vegetation Evolution Extension Agent Prompt

현재 저장소의 몬스터 진화 구조를 유지하면서, 식생도 세대 단위 적응 대상으로 확장할 수 있는 최소 구조를 추가해줘.

## 먼저 읽기
```text
AGENTS.md
AdaptiveEcosystem/Docs/아키텍처_설명.md
AdaptiveEcosystem/Docs/초기설정/01_ARCHITECTURE.md
AdaptiveEcosystem/Docs/초기설정/02_DATA_CONTRACTS.md
AdaptiveEcosystem/Docs/초기설정/05_AI_LLM_BOUNDARY.md
AdaptiveEcosystem/Source/AdaptiveEcosystem/Core/EcoDataContracts.h
AdaptiveEcosystem/Source/AdaptiveEcosystem/Evolution/
AdaptiveEcosystem/Source/AdaptiveEcosystem/Ecology/
AdaptiveEcosystem/Docs/진화모델_확장.md
```

실제 경로가 다르면 저장소를 먼저 탐색하고 현재 구조를 우선한다.

## 목표
```text
환경 / 플레이어 / 생태 압력
→ Selection Pressure
→ LLM 또는 Rule Provider가 Trait Delta 제안
→ Validator
→ 다음 세대 Profile
→ 다음 생태 사이클
```

실제 생물학 전체 시뮬레이션이 아니라 자연선택 원리를 차용한 게임용 적응 시스템이다.

## 기존 Monster 구조 유지
다음을 대규모 리팩터링하지 마라.
```text
FEvolutionContext
FEvolutionProposal
FSpeciesEvolutionProfile
UEvolutionValidator
IEvolutionDecisionProvider
```

## 식생은 Environment 값과 분리
현재 `VegetationDensity`, `FoodAvailability`는 환경 상태다.
식생 Species의 장기 Trait으로 취급하지 마라.

추가할 MVP Trait:
```text
GrowthRate
RegenerationRate
GrazingResistance
```

## 추가 권장 타입
기존 naming/style을 확인해 다음과 동등한 구조를 추가한다.
```text
FVegetationTraits
FVegetationEvolutionProfile
FVegetationEvolutionContext
FVegetationEvolutionProposal
```

최소 필드:

Profile:
```text
RegionId
VegetationSpeciesId
Generation
ProfileRevision
Traits
```

Context:
```text
WorldEpoch
ContextRevision
RegionId
VegetationSpeciesId
Environment
HarvestPressure
GrazingPressure
Generation
CurrentProfile
```

Proposal:
```text
WorldEpoch
ContextRevision
ModelRevision
SchemaRevision
GrowthRateDelta
RegenerationRateDelta
GrazingResistanceDelta
```

현재 ID/revision 타입 convention을 그대로 사용한다.

## 식생 Validator
몬스터와 같은 원칙:
```text
stale WorldEpoch reject
stale ContextRevision reject
NaN/Inf reject
Max Delta Per Generation
Mutation Budget
Hard Limit
Generation increment
ProfileRevision increment
```

초기 권장 튜닝:
```text
GrowthRate          0.70 ~ 1.30
RegenerationRate    0.70 ~ 1.30
GrazingResistance   0.00 ~ 1.00
MaxDeltaPerGen      0.10
MutationBudget      0.20
```

## 세대 적용 규칙
반드시 문서/주석으로 명시:
```text
현재 살아 있는 개체는 Spawn 당시 Profile 유지.
Profile 갱신으로 기존 Living Entity 즉시 변화 금지.
갱신 Profile은 다음 세대/새 Logical Agent/새 Spawn에 적용.
Mass Representation 전환은 새 세대가 아님.
같은 StableAgent는 기존 ProfileRevision 유지.
```

## LLM 경계
LLM은 Context를 보고 Trait Delta만 제안한다.

금지:
```text
Actor 직접 수정
Vegetation Actor 직접 수정
Population 직접 변경
Environment 직접 덮어쓰기
Validator 우회
새 Trait 이름 임의 생성
```

실제 LLM 연결은 이번 작업에서 하지 마라. Dummy/Rule Provider 또는 interface 수준으로 유지한다.

## Monster ↔ Vegetation 피드백
복잡한 먹이사슬을 구현하지 말고 계약만 준비한다.

향후 흐름:
```text
Monster Population / Grazing
→ Vegetation Pressure
→ Vegetation Profile / Density
→ Food Availability
→ Monster Evolution Context
```

직접 상호 참조 대신 Ecology State를 중간 경계로 사용한다.

## MVP
```text
Region = Forest_A

Monster = Wolf
BodyScale / MoveSpeed / Fear / Aggression

Vegetation = Grass_A
GrowthRate / RegenerationRate / GrazingResistance
```

Dummy 입력 예:
```text
Wolf HuntingPressure = 0.8
Grass GrazingPressure = 0.7
Rainfall = 0.2
```

Rule/Dummy Proposal → Validator → Generation/ProfileRevision 증가까지 확인한다.

## 이번에 하지 말 것
```text
실제 LLM runtime 연결
llama.cpp / ONNX / HTTP dependency
유전자/염색체 모델
복잡한 식물 번식
실제 biological fitness simulation
PCG 전체 재생성
Mass 전체 구현
먹이사슬 전체 구현
Network full replication
Save/Load 전체 구현
```

## 문서 갱신
최소:
```text
02_DATA_CONTRACTS.md
아키텍처_설명.md
진화모델_확장.md
```

## 완료 보고
```text
1. Current Monster Evolution Structure
2. Added Vegetation Contracts
3. Vegetation Trait Definitions
4. Vegetation Context / Proposal
5. Validator
6. Generation / Inheritance Rule
7. Monster ↔ Vegetation Feedback Boundary
8. Changed Files
9. Build Result
10. Manual Test Steps
11. Intentionally Not Implemented
12. Recommended Next Step
```

기존 Monster 구조를 깨는 대규모 변경이 필요하다고 판단되면 최소 변경안을 우선하고 큰 Refactor는 제안만 해라.
