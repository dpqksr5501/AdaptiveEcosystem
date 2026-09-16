# 08. Bootstrap Plan

목표는 **팀 전체 기능을 완성하는 것이 아니라 병렬 개발 가능한 경계를 먼저 만드는 것**이다.

## Phase 0 — Repo

조장:

1. UE 5.7 C++ project가 repo root에 존재하는지 확인
2. 한번 build/editor launch
3. `.gitignore`
4. Git LFS `.uasset/.umap`
5. Initial commit
6. 문서 pack 추가

---

## Phase 1 — Shared Contracts PR

먼저 merge:

```text
FRegionEnvironmentState
FPlayerPressureState
FSpeciesEvolutionProfile
FCreatureSpawnData
RegionId / SpeciesId / Revision convention
```

MVP Trait:

```text
BodyScale
MoveSpeedMultiplier
Fear
Aggression
```

아직 Mass/LLM/Utility AI를 구현하지 않는다.

---

## Phase 2 — 3-way parallel start

### 조장 / Creature

```text
ACreatureCharacter
UCreatureTraitComponent
Dummy profile apply
Debug
```

### World

```text
TestMap
Forest_A
Environment provider
Spawn/NavMesh
```

### Server

```text
authoritative service
Forest_A × Wolf state
Dummy profile query
ID/Epoch/Revision
Mass experiment branch
```

### AI 담당

실제 dataset 전에도:

```text
Evolution schema validator
JSON/sample prompt pipeline
Policy AI feature/policy schema draft
Dataset loader skeleton
```

---

## Phase 3 — First Integration

목표:

```text
World: Forest_A
Server: Wolf Profile
Creature: apply profile
```

Dummy:

```text
BodyScale 0.90
MoveSpeed 1.10
Fear 0.80
Aggression 0.20
```

통과 조건:
- compile
- scale visible
- speed changed
- fear/aggression debug visible

---

## Phase 4 — Server Runtime

장원준 담당 병렬:

1. 100 Mass Entity
2. StableAgentId
3. resource/energy
4. habitat/risk
5. summary
6. LOD
7. representation
8. network

팀 통합 계약은 plain USTRUCT/API로 유지한다.

---

## Phase 5 — Ecology/Pressure

```text
FEcologyEvent
→ aggregation
→ FPlayerPressureState
→ FRegionSpeciesState
```

먼저 Hunting/Pursuit/Threat/DayNight 일부만 실제 구현해도 된다.

---

## Phase 6 — Evolution LLM

조건:
- Context schema stable
- Proposal schema stable
- Validator exists
- Dummy provider works
- fallback exists

구현:

```text
Context snapshot
→ async LLM
→ structured proposal
→ validation
→ profile revision commit
```

---

## Phase 7 — Creature AI/Morphology

```text
Fear/Aggression
→ Utility AI
→ StateTree

BodyScale/LegScale/Material
→ morphology

Speed
→ locomotion/animation adaptation
```

---

## Phase 8 — Replication/Persistence

- species profile replication
- active actor replication
- region summary
- late join
- save/load

raw AI internals는 replication하지 않는다.

---

## Phase 9 — Server Optimization Research

장원준 + AI 담당 선택/확장:

- 500 / 2K / 10K / 25K
- fixed vs LOD
- sequential vs parallel
- memory footprint
- simulation policy dataset
- rule vs AI policy

캡스톤 핵심 demo가 먼저 안정되어야 한다.

---

## Bootstrap Definition of Done

- `main`이 clean build
- 공통 계약 merged
- 각 역할 branch가 같은 타입 사용
- Forest_A + Wolf dummy profile end-to-end
- 실제 LLM 없이 실행 가능
- Server/Mass branch가 Creature 구현에 Mass handle을 강요하지 않음
- AI failure가 gameplay pipeline을 막지 않음
