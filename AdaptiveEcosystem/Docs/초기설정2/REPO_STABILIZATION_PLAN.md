# AdaptiveEcosystem — Bootstrap 안정화 작업안

## 0. 목적

현재 `main`에 생성된 Bootstrap 구조는 유지한다.  
이번 작업의 목적은 기능을 확장하는 것이 아니라, **팀원들이 병렬 개발을 시작하기 전에 공통 경계와 권한 구조를 안정화하는 것**이다.

현재 프로젝트의 핵심 방향은 다음과 같다.

```text
WORLD / LEVEL
    │
    │ FRegionEnvironmentState
    ▼
SERVER ECOLOGY / MASS
    │
    ├─ Player Pressure
    ├─ Region × Species State
    ├─ Population / Resource / Risk / Energy
    ├─ Evolution Context
    └─ Authoritative Species Profile
    │
    ├───────────────┐
    ▼               ▼
Evolution LLM   Simulation Policy AI
Trait Proposal  Optional / Research
    │               │
    └───────┬───────┘
            ▼
SERVER VALIDATION / COMMIT
            │
            ▼
FSpeciesEvolutionProfile
            │
     ┌──────┴──────┐
     ▼             ▼
Mass Logical    Active Actor
Population      Representation
                      │
                      ▼
               CREATURE RUNTIME
               Morphology / Stats
               Utility AI / Animation
                      │
                      ▼
                   Network
```

핵심 원칙:

- Server가 최종 Authority다.
- LLM/AI는 Proposal만 만든다.
- AI가 Unreal Actor / Mass Entity를 직접 수정하지 않는다.
- Creature는 진화 이유를 판단하지 않고, 확정된 Profile을 표현한다.
- World는 Environment를 제공하고 Evolution을 결정하지 않는다.
- Subsystem은 Replication Transport가 아니다.
- Mass 내부 표현과 외부 공통 데이터 계약을 분리한다.
- 실제 LLM이 없어도 Rule/Dummy fallback으로 실행 가능해야 한다.

---

# 1. 현재 저장소 기준

현재 프로젝트 경로:

```text
RepoRoot/
├─ .gitattributes
├─ .gitignore
├─ README.md
└─ AdaptiveEcosystem/
   ├─ AdaptiveEcosystem.uproject
   ├─ Config/
   ├─ Content/
   ├─ Docs/
   │  └─ 초기설정/
   └─ Source/
      └─ AdaptiveEcosystem/
```

이 구조를 이번 작업에서 임의로 대규모 이동하지 않는다.

현재 `.uproject`의 EngineAssociation은 **5.8**이다.

따라서 이번 안정화 작업에서는 **UE 5.8을 현재 프로젝트 기준 버전으로 사용**한다.  
기존 문서에 남아 있는 `5.7` 표현은 `5.8`로 정리한다.

---

# 2. 이번 작업에서 반드시 수정할 항목

## 2.1 Root AGENTS.md 추가

현재 설계 문서는 다음 위치에 있다.

```text
AdaptiveEcosystem/Docs/초기설정/
```

하지만 AI coding agent가 저장소 전체를 탐색할 때 기준 문서를 바로 찾을 수 있도록:

```text
RepoRoot/AGENTS.md
```

를 추가한다.

Root `AGENTS.md`는 문서 전체를 중복 복사하지 않고 다음을 명시한다.

- 실제 UE 프로젝트 루트는 `AdaptiveEcosystem/`
- 현재 Engine 기준은 UE 5.8
- 반드시 읽어야 할 문서 경로
- Source 책임 경계
- 금지되는 과도한 구현
- 변경 전 build / 기존 타입 확인 원칙

---

## 2.2 문서 경로 및 Engine Version 정리

기존 문서/Prompt 중 다음 가정은 현재 Repo와 다르다.

```text
repo root에 .uproject가 존재한다
docs/... 경로에 문서가 있다
UE 5.7 프로젝트다
```

실제 구조는:

```text
AdaptiveEcosystem/AdaptiveEcosystem.uproject
AdaptiveEcosystem/Docs/초기설정/...
UE 5.8
```

이다.

관련 문서를 현재 구조와 일치하도록 수정한다.

특히:

```text
INITIAL_REPO_BOOTSTRAP.md
08_BOOTSTRAP_PLAN.md
AGENTS.md
01_ARCHITECTURE.md
```

의 경로/버전 표현을 확인한다.

---

# 3. 공통 데이터 계약 정합성

현재 핵심 파일:

```text
AdaptiveEcosystem/Source/AdaptiveEcosystem/Core/EcoDataContracts.h
```

구조 자체는 유지한다.

공통 계약의 역할:

```text
FRegionEnvironmentState
FPlayerPressureState

FPhenotypeTraits
FGameplayTraits
FBehaviorTraits
FEcologyTraits

FSpeciesEvolutionProfile
FCreatureSpawnData

FEvolutionContext
FEvolutionProposal
```

이번 단계에서 타입을 추가로 대량 확장하지 않는다.

## 3.1 Canonical ID / Revision 타입

Bootstrap 단계에서는 현재 C++ 구현과 맞춰 아래 타입을 기준으로 한다.

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

문서의 `uint64 / uint32`와 실제 C++의 `int64 / int32`가 혼재하지 않도록 정리한다.

향후 Strong ID Wrapper가 필요하면 별도 PR에서 검토한다.

## 3.2 Trait Hard Limit 통일

문서에 정의된 Hard Limit을 현재 기준으로 사용한다.

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
RoamRadiusMultiplier    범위 별도 명시
DayActivityPreference   0.00 ~ 1.00
NightActivityPreference 0.00 ~ 1.00
```

현재 코드의 `0.5 ~ 2.0` 같은 넓은 Clamp Meta는 문서의 기준과 일치하도록 조정한다.

단, `UPROPERTY(meta = ClampMin/ClampMax)`는 Editor 편의 기능일 뿐 **Runtime Validator를 대체하지 않는다.**

---

# 4. Evolution Validator 추가

실제 LLM 결과는 직접 `FSpeciesEvolutionProfile`에 적용하지 않는다.

```text
FEvolutionContext
      ↓
Decision Provider
      ↓
FEvolutionProposal
      ↓
Evolution Validator
      ↓
Committed FSpeciesEvolutionProfile
```

최소 Validator 책임:

```text
WorldEpoch / ContextRevision 확인
NaN / Inf 거부
Trait Hard Min / Max
세대당 Max Delta
Mutation Budget
ProfileRevision 증가
```

이번 단계에서 Species별 복잡한 생물학 규칙은 만들지 않는다.

권장 파일:

```text
Source/AdaptiveEcosystem/Evolution/EvolutionValidator.h
Source/AdaptiveEcosystem/Evolution/EvolutionValidator.cpp
```

Validator는 Server Authority 쪽에서 호출되며 Creature가 호출하지 않는다.

---

# 5. EcologyServerSubsystem을 Server-only로 보장

현재:

```text
UEcologyServerSubsystem : UWorldSubsystem
```

은 이름은 Server지만 Client World에서도 생성될 수 있다.

반드시 다음 원칙을 적용한다.

```text
Standalone / Listen Server / Dedicated Server
→ 생성 가능

NM_Client
→ 생성하지 않음
```

권장 방식:

```cpp
virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
```

에서 `UWorld::GetNetMode()`를 확인한다.

추가로 authoritative state 변경 API는 Client context에서 실행되지 않도록 방어한다.

목표:

```text
Client에 로컬 Dummy Species Profile이 생겨
Replication이 정상인 것처럼 보이는 상황 방지
```

---

# 6. Creature → Ecology 직접 의존 제거

현재 `ACreatureCharacter`가 `UEcologyServerSubsystem`을 직접 조회한다.

최종 경계는 다음이어야 한다.

```text
Server Ecology / Spawn / Representation
        │
        │ FCreatureSpawnData
        │ FSpeciesEvolutionProfile
        ▼
ACreatureCharacter
        │
        ▼
UCreatureTraitComponent
```

Creature Runtime은 다음만 알아야 한다.

```text
나는 어떤 Agent인가?
어떤 Species Profile을 적용해야 하는가?
받은 Trait을 어떻게 표현하는가?
```

Creature가 알아서는 안 되는 것:

```text
Profile이 LLM에서 왔는가?
Pressure가 왜 높아졌는가?
EcologyServerSubsystem 내부 Map이 무엇인가?
```

권장 변경:

```cpp
void InitializeCreature(
    const FCreatureSpawnData& InSpawnData,
    const FSpeciesEvolutionProfile& InProfile);
```

`CreatureCharacter.cpp`에서 `EcologyServerSubsystem` 직접 include/조회 의존성을 제거하는 방향으로 수정한다.

## 6.1 Dummy Vertical Slice는 Debug / Integration Layer로 이동

Dummy 테스트 자체는 유지한다.

```text
Forest_A
Wolf
BodyScale = 0.90
MoveSpeedMultiplier = 1.10
Fear = 0.80
Aggression = 0.20
```

하지만 Creature가 ServerSubsystem을 직접 조회해서 테스트하지 않는다.

권장:

```text
Debug / Bootstrap Test Actor
        ↓
UEcologyServerSubsystem에서 Profile 조회
        ↓
ACreatureCharacter.InitializeCreature(...)
```

예:

```text
Source/AdaptiveEcosystem/Debug/EcologyBootstrapTestActor.*
```

또는 기존 GameMode의 명시적 Test Harness.

목표는 integration test dependency를 Runtime Creature dependency와 분리하는 것이다.

---

# 7. LLM Interface는 동기 fallback과 비동기 LLM을 구분

현재:

```cpp
bool RequestProposal(
    const FEvolutionContext& Context,
    FEvolutionProposal& OutProposal);
```

형식은 Dummy / Rule-Based Provider에는 적절하다.

하지만 실제 LLM을 이 함수 안에서 blocking inference로 구현하지 않는다.

정책:

```text
Immediate Provider
- Dummy
- Rule-Based

Async Evolution Service
- llama.cpp / external model
- Snapshot
- Worker / Task
- Result Queue
- Server Commit Boundary
```

실제 LLM 구조:

```text
Server
  ↓
FEvolutionContext Snapshot
  ↓
Async Request
  ↓
LLM
  ↓
FEvolutionProposal
  ↓
Result Queue
  ↓
Validator
  ↓
Server Commit
```

이번 안정화 PR에서 실제 LLM Service를 구현하지 않는다.

대신 기존 Interface 주석과 문서에 다음을 명확히 남긴다.

> `IEvolutionDecisionProvider::RequestProposal`은 immediate/fallback provider용이다. 실제 Runtime LLM inference는 별도의 async service를 통해 통합한다.

---

# 8. Network 경계

현재 `FReplicatedSpeciesState`, `FReplicatedRegionSummary` 방향은 유지한다.

원칙:

```text
Subsystem != Replication Transport
```

추후 Replication은:

```text
GameState
또는
Dedicated Replicated Actor / Component
```

가 담당한다.

이번 안정화 단계에서는 full replication을 구현하지 않는다.

개별 Creature마다 Species Profile 전체를 반복 복제하지 않는다.

---

# 9. Git / LFS 및 Asset Audit

현재 LFS 설정은 유지한다.

이번 작업에서 Git history rewrite를 임의로 수행하지 않는다.

프로젝트에 다음 Template Content가 존재한다.

```text
Variant_Combat
Variant_Platforming
Variant_SideScrolling
```

이번 안정화 Agent는 **자동 삭제하지 않는다.**

대신:

```text
AdaptiveEcosystem/Docs/초기설정/ASSET_AUDIT.md
```

를 생성하고 다음을 분류한다.

```text
KEEP
REMOVE CANDIDATE
UNKNOWN / REFERENCE CHECK NEEDED
```

삭제는 사용자가 확인한 뒤 별도 commit에서 진행한다.

---

# 10. Build.cs / Source 구조

현재 단일 Runtime Module 구조를 유지한다.

이번 PR에서 다음을 하지 않는다.

```text
Public / Private 대규모 이동
Plugin 추출
Mass Runtime Plugin 생성
```

기존 Source 경계를 유지한다.

```text
Core/
World/
Ecology/
Evolution/
Creature/
Network/
Debug/   ← 필요 시 추가
```

---

# 11. 이번 작업의 완료 조건

```text
[ ] 문서 Engine Version이 UE 5.8로 일치
[ ] Repo Root AGENTS.md 존재
[ ] 문서 경로가 실제 Repo 구조와 일치

[ ] 공통 ID / Revision 타입 일치
[ ] Trait Hard Limit 문서/코드 일치
[ ] Runtime Evolution Validator 존재

[ ] UEcologyServerSubsystem이 Client에서 생성되지 않음
[ ] authoritative state 변경 경계가 Server로 제한됨

[ ] ACreatureCharacter가 UEcologyServerSubsystem을 직접 참조하지 않음
[ ] InitializeCreature(SpawnData, Profile) 또는 동등한 명시적 초기화 경로 존재
[ ] Dummy integration은 Debug/Integration layer를 통해 동작

[ ] Dummy/Rule provider는 유지
[ ] 실제 LLM blocking inference는 구현하지 않음
[ ] async LLM 경계가 문서에 명시

[ ] Network DTO 구조 유지
[ ] full replication 구현하지 않음

[ ] Template Asset 자동 삭제하지 않음
[ ] ASSET_AUDIT.md 생성

[ ] Clean build 성공 또는 빌드 불가 원인 정확히 보고
```

---

# 12. 이번 작업에서 하지 않을 것

```text
MassEntity 전체 구현
Simulation LOD 전체 구현
llama.cpp 연결
ONNX Runtime 연결
Utility AI 전체 구현
StateTree Creature 행동 전체 구현
Morph Target 제작
Procedural Mesh
Wing / Flight
PCG 전체 구현
Save/Load 전체 구현
Network Replication 전체 구현
대규모 Source 이동
Plugin 추출
Git history rewrite
Template Asset 자동 삭제
```

---

# 13. 작업 완료 보고 형식

```text
1. 발견한 기존 구조
2. 수정한 파일
3. 새로 만든 파일
4. Architecture Boundary 수정 내용
5. Data Contract 변경 내용
6. Server Authority 수정 내용
7. Creature Dependency 수정 내용
8. Validator 구현 내용
9. Build 결과
10. Unreal Editor에서 수동 확인할 단계
11. Asset Audit 결과
12. 아직 구현하지 않은 것
13. 역할별 다음 작업
```

이번 단계의 목적은 기능 확장이 아니라:

> **팀원들이 World / Server-Mass-Network / AI-LLM / Creature를 서로 기다리지 않고 병렬 개발할 수 있는 안정적인 공통 기준점을 만드는 것**

이다.
