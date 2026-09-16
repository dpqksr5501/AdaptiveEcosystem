# Initial Repository Bootstrap Prompt

너는 Unreal Engine 5.7 C++ 팀 프로젝트의 초기 공통 구조를 세팅하는 AI coding agent다.

작업 전에 저장소를 탐색하고 반드시 다음을 읽어라.

- `AGENTS.md`
- `docs/00_PROJECT_SCOPE.md`
- `docs/01_ARCHITECTURE.md`
- `docs/02_DATA_CONTRACTS.md`
- `docs/03_TEAM_ROLES.md`
- `docs/08_BOOTSTRAP_PLAN.md`
- `docs/09_GIT_CONTRIBUTING.md`
- `docs/10_DECISIONS_OPEN_QUESTIONS.md`

`docs/reference/` 문서는 원본 참고 자료다. 상위 통합 문서와 충돌할 경우 임의로 합치지 말고 차이를 보고하라.

## 이번 작업 목표

전체 생태계나 LLM을 구현하지 마라.
**팀원들이 병렬 개발할 수 있도록 최소 공통 C++ 계약과 첫 Vertical Slice skeleton만 만든다.**

## 먼저 확인

1. repo root의 `.uproject`
2. 실제 Project/Module 이름
3. 기존 Source/Plugin 구조
4. Build.cs
5. Git ignore/LFS
6. 기존 유사 USTRUCT/Class가 있는지

`.uproject`가 없으면 임의 생성하지 말고 사용자가 UE 5.7 C++ project를 repo root에 만들어야 한다고 보고한다.

## 공통 타입

기존 타입이 없을 때만 다음 최소 계약을 추가한다.

- `FRegionEnvironmentState`
- `FPlayerPressureState`
- `FSpeciesEvolutionProfile`
- `FCreatureSpawnData`

최초 실제 Trait은:

- BodyScale
- MoveSpeedMultiplier
- Fear
- Aggression

식별:

- `FName RegionId`
- `FName SpeciesId`
- 필요한 경우 `uint64 StableAgentId`
- revision/epoch는 docs 규칙에 맞춘다.

과도한 미래 타입을 모두 구현하지 마라.

## Runtime skeleton

가능한 최소 범위:

### World
- `AEcologyRegion` 또는 기존 equivalent
- RegionId
- 최소 Environment query 경로

### Server/Ecology
- authoritative service skeleton
- `Forest_A × Wolf` dummy profile query
- 실제 Mass/Pressure/LLM 전체 구현 금지

### Creature
- `ACreatureCharacter`
- `UCreatureTraitComponent`
- Species Profile 적용 API
- BodyScale 적용 경로
- MoveSpeedMultiplier 적용 경로
- Fear/Aggression 저장/Debug query

### Network
- full replication 구현 금지
- Subsystem을 replication transport로 만들지 말 것
- future replicated species state 위치만 명확히

### Evolution
- 실제 LLM 추가 금지
- 필요하면 interface/TODO 수준

## Dummy vertical slice

```text
RegionId = Forest_A
SpeciesId = Wolf
BodyScale = 0.90
MoveSpeedMultiplier = 1.10
Fear = 0.80
Aggression = 0.20
```

이 Profile을 Creature에 적용 가능한 코드 경로를 만든다.

Editor asset이 필요하면 C++ extension point까지만 만들고 manual step을 보고한다.

## 절대 하지 말 것

- Mass 전체 시스템 구현
- llama.cpp/ONNX 외부 dependency 추가
- UtilityAI/Nav3D/KawaiiPhysics 설치
- Simulation Policy AI 구현
- Wing/Flight
- Procedural mesh
- 수십 Trait 구현
- 임의 Plugin refactor
- unrelated code 변경

## 완료 보고

1. 저장소 분석
2. 생성/수정 파일
3. 데이터 계약
4. skeleton 구조
5. build 결과
6. editor manual step
7. 미구현 범위
8. 역할별 다음 1~3개 작업
