# 03. Team Roles — 실제로 누가 무엇을 시작하는가

이 문서는 역할 설명이 아니라 **개발 시작 작업 목록**이다.

## 0. 조장 / Creature / Integration 담당

### 첫날 해야 할 일

1. Git repo / UE 5.7 C++ 프로젝트 기준점 확정
2. `.gitignore`, Git LFS 확인
3. 공통 계약 PR 생성
   - `FRegionEnvironmentState`
   - `FPlayerPressureState`
   - `FSpeciesEvolutionProfile`
   - `FCreatureSpawnData`
   - ID/Revision 최소 규칙
4. `ACreatureCharacter` / `UCreatureTraitComponent` skeleton
5. Dummy Profile 적용
   - BodyScale
   - MoveSpeedMultiplier
   - Fear/Aggression 저장/Debug
6. 통합 TestMap에서 각 파트 연결 확인

### 이후

- Utility AI / StateTree
- AI Perception / EQS
- Morphology
- Animation adaptation
- Mass Actor Representation과 Creature Actor 연결
- 통합 Debug

### 완료 기준

> Server가 `FSpeciesEvolutionProfile`과 `FCreatureSpawnData`만 주면 Creature가 원인을 몰라도 정상적으로 표현된다.

---

## 1. 서버 / Ecology / Mass / Network 담당 — 장원준

이 역할은 `[0914]동적생태계_장원준.md`의 기술 방향을 팀 서버 계층으로 가져온다.

### 바로 시작할 일

1. authoritative World-scoped runtime service 골격
2. `Region × Species` runtime state
3. `StableAgentId`, `WorldEpoch`, `EventId`, Revision 정책
4. 100개 수준 MassEntity 최소 실험
5. Resource / Risk / Energy 기본 loop
6. Simulation LOD skeleton
7. MassRepresentation/MassActors 연결 가능성 검증
8. Region/Species Summary 생성
9. Replication transport skeleton
10. Dataset/Observation을 만들 수 있는 metrics hook

### Network에서 먼저 할 것

- 서버만 Simulation state를 변경
- Client request validation 경계
- active Actor 일반 replication
- Region/Species 저주기 summary/profile replication
- late join/reset에서 epoch/revision 관리

### 나중에 할 것

- 500 통합
- 2K/10K/25K scale test
- memory footprint
- parallel resource aggregation
- Unreal Insights
- Save/Load

### 금지

- 모든 Mass entity transform replication
- Mass handle을 외부 API ID로 사용
- Actor와 Mass가 동시에 같은 논리 상태를 임의로 write

---

## 2. AI / LLM 담당 — 인수인계 대상 팀원

이 역할은 서버와 직접 코드를 강결합하지 않고 **Schema 기반 AI 계층**을 담당한다.

### A. 캡스톤 필수: Creature Evolution LLM

먼저 Server 담당과 확정:

1. `FEvolutionContext` schema
2. `FEvolutionProposal` schema
3. Trait constraints
4. Prompt/Model revision
5. 평가 시나리오
6. fallback 규칙

그 다음:

- Dataset/Prompt sample 작성
- structured output parser contract
- model/prompt 실험
- trait delta 평가
- runtime model/interface 제공

초기 목표:

```text
Context
→ JSON Proposal
→ Validator 통과 가능한 delta
```

### B. 성능 연구: Simulation Policy AI

`[0915]NetworkToAI_인수인계.md`의 범위.

모델부터 만들지 말고 다음 순서:

1. AI가 풀 문제 정의
2. Feature Schema
3. Policy Schema
4. Dataset Schema
5. Evaluation Metric
6. Dataset Loader / Training Pipeline
7. Model Training
8. Runtime Artifact
9. Rule vs AI benchmark

초기 output은 `PolicyId` 추천 방식 권장.

### 중요한 구분

```text
Evolution LLM
→ Creature Trait 변화

Policy AI
→ Server Simulation update policy 변화
```

둘은 같은 output type이 아니다.

---

## 3. World / Level 담당

### 바로 시작할 일

1. TestMap 생성
2. `Forest_A` Region 정의
3. Spawnable area / NavMesh
4. 환경 데이터 provider
   - Rainfall
   - Humidity
   - Vegetation
   - Food
5. Day/Night 기본 연결
6. Shelter/query 위치가 필요하면 최소 interface 제공

### 서버와 맞출 것

- RegionId 규칙
- Environment State 단위/범위
- Neighbor Region 정보
- Spawn position query contract

### 완료 기준

> Server가 `RegionId`로 현재 Environment State와 Spawn 가능한 공간을 안정적으로 조회할 수 있다.

World가 Evolution Rule을 소유하지 않는다.

---

## 4. 첫 통합 목표 — 전원 공통

```text
World
Forest_A 제공
    ↓
Server
Wolf Profile 보유
    ↓
Network/Local query
Profile 전달
    ↓
Creature
BodyScale 0.90
MoveSpeed 1.10
Fear 0.80
Aggression 0.20
```

여기까지는 실제 LLM과 복잡한 Mass Simulation 없이도 성공해야 한다.

---

## 5. 이후 병렬 개발

### World
Dummy environment → 실제 weather/vegetation

### Server
Dummy state → Mass population/resource/risk/migration

### AI
Dummy proposal → Evolution LLM

### Creature
Debug trait → Utility AI / Morphology / Animation

### Network
Local profile → replicated species state + actor state

---

## 6. Branch 예시

```text
feature/core-contracts
feature/creature-runtime
feature/world-region
feature/server-ecology-runtime
feature/mass-simulation
feature/network-species-state
feature/evolution-llm
feature/simulation-policy-ai
```
