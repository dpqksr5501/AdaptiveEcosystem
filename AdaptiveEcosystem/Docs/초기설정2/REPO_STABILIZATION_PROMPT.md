# AdaptiveEcosystem — Bootstrap Stabilization Agent Prompt

현재 저장소의 초기 Bootstrap 코드를 **안정화**해줘.

기능을 추가로 많이 만드는 작업이 아니다.  
팀원들이 이제 역할별로 병렬 개발을 시작할 예정이므로, **공통 데이터 계약 / Server Authority / Runtime 의존성 경계 / 문서 정합성**을 먼저 바로잡는 것이 목적이다.

## 작업 전에 반드시 저장소를 먼저 분석해라

현재 Repo 구조를 임의로 가정하지 말고 실제 파일을 확인한다.

현재 알려진 프로젝트 위치는:

```text
RepoRoot/
└─ AdaptiveEcosystem/
   └─ AdaptiveEcosystem.uproject
```

먼저 다음을 읽어라.

```text
RepoRoot/AGENTS.md                  // 존재하면 최우선
AdaptiveEcosystem/Docs/초기설정/AGENTS.md
AdaptiveEcosystem/Docs/초기설정/01_ARCHITECTURE.md
AdaptiveEcosystem/Docs/초기설정/02_DATA_CONTRACTS.md
AdaptiveEcosystem/Docs/초기설정/03_TEAM_ROLES.md
AdaptiveEcosystem/Docs/초기설정/04_SERVER_MASS_NETWORK.md
AdaptiveEcosystem/Docs/초기설정/05_AI_LLM_BOUNDARY.md
AdaptiveEcosystem/Docs/초기설정/08_BOOTSTRAP_PLAN.md
AdaptiveEcosystem/Docs/초기설정/INITIAL_REPO_BOOTSTRAP.md
```

그리고 현재 C++ 구현도 반드시 확인한다.

```text
Core/EcoDataContracts.h
World/
Ecology/
Evolution/
Creature/
Network/
AdaptiveEcosystem.Build.cs
AdaptiveEcosystem.uproject
```

문서보다 실제 현재 코드가 이미 발전한 부분이 있다면 무조건 덮어쓰지 말고 충돌을 분석한 뒤 최소 변경으로 정리한다.

## 별첨 안정화 계획을 기준으로 작업한다

`AdaptiveEcosystem/Docs/초기설정/REPO_STABILIZATION_PLAN.md`를 읽고 그 내용을 이번 작업의 기준으로 사용한다.

핵심 목표:

```text
A. UE 버전 / 문서 경로 정합성
B. Root AGENTS.md
C. Data Contract 타입 / Trait 범위 정합성
D. Runtime Evolution Validator
E. EcologyServerSubsystem Server-only
F. Creature → Ecology 직접 의존 제거
G. Dummy Integration을 Debug/Test Harness로 이동
H. 실제 LLM은 비동기 구조로 연결된다는 경계 명시
I. Asset Audit만 수행하고 자동 삭제 금지
J. Clean Build
```

## UE 버전

현재 `.uproject`의 `EngineAssociation`을 확인한다.

현재 프로젝트가 UE 5.8이라면 `UE 5.8`을 canonical version으로 사용하고 기존 문서의 `5.7` 표현을 5.8로 정리한다.

사용자가 명시적으로 요청하지 않는 한 `.uproject`를 5.7로 내리지 마라.

## Root AGENTS.md

Repo Root에 `AGENTS.md`가 없다면 추가한다.

반드시 포함:

```text
- 실제 UE project root = AdaptiveEcosystem/
- Engine = UE 5.8
- 설계 문서 위치
- Server Authority 원칙
- Creature / Ecology / World / AI 책임 경계
- AI는 Proposal만 생성
- Subsystem은 Replication Transport가 아님
- 실제 LLM blocking inference 금지
- Mass handle / Actor pointer를 영속 ID로 사용 금지
- 과도한 refactor 금지
```

## 공통 Data Contract 정리

기존 타입을 중복 생성하지 마라.

Bootstrap canonical 타입:

```cpp
FName RegionId;
FName SpeciesId;

int64 StableAgentId;

int32 WorldEpoch;
int32 ControlEpoch;
int32 ContextRevision;
int32 ModelRevision;
int32 SchemaRevision;

int64 ProfileRevision;

int32 Generation;
int32 RandomSeed;
```

문서의 uint 계열과 현재 C++의 signed 타입이 혼재되어 있다면 현재 Bootstrap C++ 타입을 기준으로 문서를 맞춘다.

## Trait Hard Limit 정리

문서 기준:

```text
BodyScale               0.80 ~ 1.20
LegScale                0.90 ~ 1.10
BodyBoneScale           0.90 ~ 1.10
ColorBrightness         0.70 ~ 1.20
ColorTintStrength       0.00 ~ 1.00

MoveSpeedMultiplier     0.80 ~ 1.25
HealthMultiplier        0.80 ~ 1.25
AttackMultiplier        0.80 ~ 1.25

Fear                    0.00 ~ 1.00
Aggression              0.00 ~ 1.00
GroupAffinity           0.00 ~ 1.00
HidePreference          0.00 ~ 1.00

MigrationTendency       0.00 ~ 1.00
DayActivityPreference   0.00 ~ 1.00
NightActivityPreference 0.00 ~ 1.00
```

`RoamRadiusMultiplier`은 기존 문서/코드 의미를 확인하고 합리적인 범위를 하나로 통일한 뒤 변경 이유를 보고해라.

현재 C++ Clamp meta가 다르면 문서 기준과 맞춘다.

중요: `UPROPERTY Clamp meta != Runtime Validation`.

## Evolution Validator 구현

다음 경계를 실제 코드로 만든다.

```text
Current Profile
+
FEvolutionProposal
+
Expected WorldEpoch / ContextRevision
        ↓
Evolution Validator
        ↓
Validated New Profile
```

권장 파일:

```text
Evolution/EvolutionValidator.h
Evolution/EvolutionValidator.cpp
```

최소 책임:

```text
- stale WorldEpoch reject
- stale ContextRevision reject
- non-finite value reject
- per-trait delta clamp/reject
- hard min/max
- Mutation Budget
- ProfileRevision increment
```

과도한 Species 생물학 규칙은 만들지 않는다.

## EcologyServerSubsystem을 실제 Server-only로 수정

`UEcologyServerSubsystem : UWorldSubsystem`을 확인한다.

가능하면 `ShouldCreateSubsystem(UObject* Outer) const`를 override하여:

```text
NM_Client -> false
Standalone / Listen Server / Dedicated Server -> true
```

가 되게 한다.

또한 Profile commit / authoritative state mutation API가 Client context에서 실행되지 않도록 방어한다.

## Creature가 EcologyServerSubsystem을 직접 참조하지 않게 수정

최종 Runtime 경계:

```text
Server / Spawn / Representation
          ↓
FCreatureSpawnData
FSpeciesEvolutionProfile
          ↓
ACreatureCharacter
          ↓
UCreatureTraitComponent
```

`ACreatureCharacter`에 명시적인 초기화 API를 추가한다.

권장:

```cpp
void InitializeCreature(
    const FCreatureSpawnData& InSpawnData,
    const FSpeciesEvolutionProfile& InProfile);
```

`BeginPlay()`에서 Ecology subsystem을 직접 query하지 않도록 한다.

Creature는 Profile이 어디서 만들어졌는지 몰라야 한다.

## Dummy Vertical Slice는 Debug/Test Harness로 분리

Dummy test는 유지한다.

```text
Forest_A
Wolf

BodyScale = 0.90
MoveSpeedMultiplier = 1.10
Fear = 0.80
Aggression = 0.20
```

필요하면:

```text
Source/AdaptiveEcosystem/Debug/EcologyBootstrapTestActor.*
```

같은 작은 integration harness를 만든다.

역할:

```text
ServerSubsystem에서 Dummy Profile 조회
        ↓
지정된 / 생성된 Creature에 InitializeCreature()
        ↓
Trait 적용 확인
```

Debug/Test Harness가 Production Creature Runtime 의존성을 오염시키면 안 된다.

## Dummy / Rule Provider는 유지하되 실제 LLM과 구분

현재 `IEvolutionDecisionProvider::RequestProposal(...)`가 동기 함수라면 Dummy/Rule fallback용으로 유지할 수 있다.

하지만 실제 LLM inference를 이 함수 안에서 blocking 호출로 구현하지 마라.

주석/문서를 명확히 한다.

```text
Immediate Provider
- Dummy
- Rule Based

Async Evolution Service
- LLM runtime
- snapshot
- worker/task
- proposal queue
- validator
- server commit
```

이번 작업에서는 llama.cpp, ONNX, HTTP LLM, Python bridge 등을 추가하지 마라.

## Network는 확장하지 말고 경계만 유지

`FReplicatedSpeciesState`, `FReplicatedRegionSummary` 구조를 확인한다.

Subsystem 자체에 Replication property를 추가하지 마라.

이번 PR에서 full replication을 구현하지 않는다.

## Template Asset은 자동 삭제 금지

현재 프로젝트 Content 아래의 Template/Variant asset을 조사한다.

예:

```text
Variant_Combat
Variant_Platforming
Variant_SideScrolling
```

이번 작업에서 자동 삭제하지 마라.

대신:

```text
AdaptiveEcosystem/Docs/초기설정/ASSET_AUDIT.md
```

를 생성한다.

형식:

```text
KEEP
REMOVE CANDIDATE
UNKNOWN / NEED REFERENCE CHECK
```

삭제가 안전하다는 확신이 없으면 무조건 `UNKNOWN`에 둔다.

Git history rewrite를 하지 마라.

## 기존 구조를 과도하게 리팩터링하지 마라

이번 작업에서 금지:

```text
- Public/Private 전체 이동
- 새 Plugin 추출
- EcosystemRuntime Plugin 생성
- Mass 전체 구현
- Simulation LOD 전체 구현
- LLM 연결
- Utility AI 전체 구현
- Network full replication
- Save/Load 전체 구현
- PCG 전체 구현
- Template Asset 대량 삭제
- Git history rewrite
```

## Build

변경 후 가능한 범위에서 Clean Build를 수행한다.

우선순위:

```text
AdaptiveEcosystemEditor Win64 Development
```

빌드가 환경 문제로 불가능하면 실행한 명령, 실패 위치, 프로젝트 코드 문제인지 로컬 UE/SDK 환경 문제인지 구분해서 보고한다.

가능하면 Editor launch까지 확인한다.

## 완료 보고

작업 후 반드시 다음 형식으로 답한다.

```text
1. Current Repo Analysis
2. Changed Files
3. New Files
4. Engine / Documentation Alignment
5. Data Contract Alignment
6. Evolution Validator
7. Server Authority Fix
8. Creature Dependency Fix
9. Dummy Integration Path
10. LLM Async Boundary
11. Network Boundary
12. Asset Audit
13. Build Result
14. Manual Unreal Editor Checks
15. Intentionally Not Implemented
16. Next Tasks
   - World 담당
   - Server/Mass/Network 담당
   - AI/LLM 담당
   - Creature/Integration 담당
```

작업 도중 문서와 코드가 충돌하고 어떤 쪽을 기준으로 해야 할지 불명확하면 임의로 큰 구조를 결정하지 말고, **기존 런타임 구조를 보존하면서 최소 변경 후 충돌 내용을 보고**해라.
