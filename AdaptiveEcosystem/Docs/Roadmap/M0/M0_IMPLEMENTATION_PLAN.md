# M0 Implementation Plan — Architecture & Authority Alignment

> 대상 Milestone: [M0 — Architecture & Authority Alignment](M0_ARCHITECTURE_AUTHORITY.md)  
> 목적: 기능 확장이 아니라 **활성 런타임의 의존 방향과 상태 소유권을 고정**하는 단계

---

## 1. 구현 결과

M0 완료 시 프로젝트의 활성 런타임은 다음 구조를 따른다.

```text
World / Region
  └─ 공간 경계와 FRegionEnvironmentState 제공
               ↓
UEcologySimulationSubsystem
  └─ FRegionEcologyState의 유일한 소유자
               ↓
Mass Logical State
  └─ StableAgentId, Vitals, Region, Policy 상태의 유일한 소유자
               ↓
Network / Representation
  └─ 권위 결과를 읽고 전달하거나 표현
```

기존 Evolution 시스템은 빌드 가능한 Legacy 코드로 남길 수 있지만, 신규 활성 경로가 해당 타입과 Subsystem을 참조하지 않아야 한다.

---

## 2. 현재 상태와 M0 목표

| 현재 상태 | 문제 | M0 목표 |
| :--- | :--- | :--- |
| `FRegionEnvironmentState`에 Legacy Food 필드가 남아 있음 | 지역 자원의 이중 진실값 가능성 | 신규 경로는 `FRegionEcologyState`만 사용 |
| `AEcologyRegion`이 식생과 Food를 직접 변경 | World와 Simulation 책임 혼합 | World는 환경과 공간만 제공 |
| 두 Ecology Subsystem이 Server World에 존재 | 활성 경로와 Legacy 경로 혼동 | SimulationSubsystem만 신규 본체로 사용 |
| `EcoDataContracts.h`에 Evolution 타입이 집중됨 | 신규 코드가 Legacy에 쉽게 결합 | 활성 계약을 작은 헤더로 분리 |
| Network 타입이 Evolution Profile을 포함 | 향후 Mass 복제 계약과 충돌 | 활성 Network DTO와 Legacy DTO 분리 |
| 기존 Debug Actor가 Evolution 흐름을 자동 실행 | 신규 런타임 검증과 혼동 | Legacy 테스트는 명시적 opt-in으로만 실행 |

---

## 3. 목표 의존 방향

허용되는 의존 방향은 다음과 같다.

```text
Core
 ↑
World      AI/Policy
 ↑           ↑
Ecology ← Mass
 ↑           ↑
Network   Representation
```

주요 금지 방향:

- Core가 World, Ecology, Mass 또는 Network를 참조하지 않는다.
- World가 Ecology Simulation 결과를 결정하지 않는다.
- Mass Entity loop가 Region Actor 또는 Ecology UObject를 직접 변경하지 않는다.
- Client Representation이 Server Simulation을 조회하거나 변경하지 않는다.
- 신규 Network 타입이 Evolution Profile을 포함하지 않는다.

---

## 4. 작업 패키지

### M0.1 — Active와 Legacy 경계 확정

목적은 삭제가 아니라 신규 코드가 사용할 영역을 명확히 하는 것이다.

작업 대상:

- `Core/EcoIds.h`
- `Core/EcoRegionTypes.h`
- `AI/Policy/EcoPolicyContracts.h`
- `Mass/EcoMassFragments.h`
- `Ecology/EcologySimulationSubsystem.*`
- `Network/EcologyNetworkTypes.h`

위 파일을 Active Runtime 계약으로 지정한다. 다음 영역은 Legacy로 분류한다.

- `Evolution/`
- `Ecology/EcologyServerSubsystem.*`
- Evolution 타입을 사용하는 기존 Creature Trait 경로
- `Debug/EcologyBootstrapTestActor.*`

Legacy 파일을 즉시 대량 이동하면 Blueprint와 include 경로가 깨질 수 있으므로, M0에서는 폴더 이동보다 문서·주석·기본 비활성화를 우선한다.

완료 조건:

- Active/Legacy 파일 목록이 문서로 확인 가능함
- 이후 신규 코드가 참조할 계약 헤더가 명확함

---

### M0.2 — 공통 데이터 계약 분리

`EcoDataContracts.h`에서 신규 런타임에 필요한 계약이 Evolution 타입과 함께 확장되지 않도록 한다.

권장 분리:

```text
Core/EcoIds.h
  └─ FEcoAgentId, Runtime Index

Core/EcoRegionTypes.h
  └─ Environment State, Ecology State

Core/EcoEventTypes.h
  └─ Predation, Consumption 등 신규 생태 이벤트

Core/EcoRepresentationTypes.h
  └─ Mass → Actor/Client 표현 Snapshot

AI/Policy/EcoPolicyContracts.h
  └─ Observation V1, Action V1

Core/EcoDataContracts.h
  └─ Legacy Evolution 계약 유지
```

기존 호출부를 한 번에 모두 이동하지 않는다. Active Runtime 파일부터 작은 헤더를 직접 include하도록 바꾸고, Legacy 코드는 기존 헤더를 계속 사용할 수 있게 한다.

완료 조건:

- Active Runtime 헤더가 `EcoDataContracts.h`를 필요로 하지 않음
- `EcoDataContracts.h` 변경 없이도 신규 Mass/Simulation 계약을 확장할 수 있음
- 모든 변경 단계에서 빌드 가능함

---

### M0.3 — Region Resource 단일 소유권 확정

`FRegionEcologyState`와 `UEcologySimulationSubsystem`을 Food, PredationHistory와 Population의 유일한 권위 소유자로 확정한다.

원칙:

- `AEcologyRegion`은 Bounds와 `FRegionEnvironmentState`만 제공한다.
- `VegetationDensity`, `FoodAvailability`는 Legacy 호환 필드로만 유지한다.
- 신규 코드가 Legacy Food 필드를 읽거나 쓰지 않게 한다.
- `ApplyVegetationConsumption()`과 `ApplyVegetationRegrowth()`는 Legacy 호출 전용으로 표시한다.
- 신규 Resource 변경은 `UEcologySimulationSubsystem` 경계에서만 수행한다.

`UEcologySimulationSubsystem`의 public API는 읽기와 명시적 권위 변경을 구분한다. 범용 `SetRegionState()`를 여러 계층에서 자유롭게 호출하는 구조보다, 등록·조회·이벤트 반영 목적이 드러나는 API를 유지한다.

완료 조건:

- 신규 경로에서 Food를 저장하는 장소가 하나임
- World 계층이 Food 소비와 개체 생존을 결정하지 않음
- Region 환경 변경과 Ecology 자원 변경을 독립적으로 테스트할 수 있음

---

### M0.4 — Server와 Client 실행 경계 고정

`UEcologySimulationSubsystem`은 Standalone 또는 Server World에서만 생성한다. Client World에는 권위 SimulationSubsystem을 만들지 않는다.

M0에서는 실제 Processor를 구현하지 않지만 이후 Processor의 실행 정책을 다음처럼 고정한다.

```text
Server | Standalone
- Observation
- Policy
- Steering Authority
- Interaction
- Vitals / Lifecycle
- Migration
- Aggregation

Client
- Replicated State Apply
- Interpolation
- Representation / Animation
- Debug Visualization
```

완료 조건:

- 모든 권위 변경 API가 Server/Standalone 전제임
- Client 전용 코드가 권위 Subsystem을 요구하지 않음
- Listen Server와 향후 Dedicated Server가 동일한 Simulation 경로를 사용함

---

### M0.5 — 식별자 역할 고정

현재 `FEcoAgentId`, `StableAgentId`, Region/Species Runtime Index를 신규 계약의 기준으로 사용한다.

규칙:

- Mass Fragment의 `StableAgentId` 타입은 프로젝트 별칭인 `FEcoAgentId`와 일치시킨다.
- `StableAgentId`는 0을 Invalid 값으로 취급하고 Server가 발급한다.
- Region/Species Runtime Index는 World 내부 hot path에서만 사용한다.
- `FMassEntityHandle`은 저장하거나 Network DTO에 넣지 않는다.
- `FMassNetworkID`는 M2에서 MassReplication을 도입할 때 전송용 ID로 추가하며 StableAgentId를 대체하지 않는다.

완료 조건:

- 각 ID의 생성자와 사용 범위가 문서와 코드 주석에 일치함
- Persistent ID와 Runtime Handle을 혼용하는 API가 없음

---

### M0.6 — Legacy Evolution 기본 비활성화

기존 코드를 즉시 삭제하지 않고 신규 게임 실행에서 자동으로 개입하지 않게 한다.

권장 처리:

- `UEcologyServerSubsystem`을 Legacy 용도로 명시하고 기본 실행 경로에서 제외
- 필요한 경우 명시적인 개발 설정으로만 Legacy Subsystem 활성화
- `AEcologyBootstrapTestActor`의 자동 실행 기본값 비활성화
- 기존 Evolution 검증은 수동 Legacy 테스트로만 유지
- 신규 Network DTO에서 `FSpeciesEvolutionProfile` 제거 또는 Legacy Network 타입으로 분리

완료 조건:

- 일반 게임 실행에서 Evolution Profile 생성·Commit이 자동 수행되지 않음
- Legacy를 활성화하지 않아도 신규 Subsystem과 프로젝트가 정상 시작됨
- Legacy 코드는 별도 제거 Milestone 전까지 빌드 가능한 상태를 유지함

---

### M0.7 — 경계 검증과 빌드

M0는 기능 테스트보다 아키텍처 회귀 방지 테스트가 중요하다.

필수 검증:

- Standalone/Server에는 `UEcologySimulationSubsystem`이 존재함
- Client에는 권위 SimulationSubsystem이 생성되지 않음
- Region Environment 변경이 FoodAmount를 직접 변경하지 않음
- FoodAmount가 음수가 되지 않음
- PredationHistory가 `[0, 1]` 범위를 유지함
- StableAgentId 기본·Invalid 규칙이 유지됨
- Active Runtime 파일이 Evolution 헤더를 참조하지 않음
- `AdaptiveEcosystemEditor Win64 Development` 빌드 통과

---

## 5. 권장 적용 순서

```text
1. Active/Legacy 목록 확정
2. Active 계약 헤더 분리
3. Network DTO에서 Evolution 의존 제거
4. Region과 Simulation의 Food 소유권 분리
5. Legacy Subsystem/Test 자동 실행 차단
6. Server/Client 경계 테스트 추가
7. 전체 빌드와 문서 동기화
```

각 단계는 독립적으로 컴파일 가능한 작은 변경으로 진행한다. 특히 `EcoDataContracts.h` 전체 분해와 Legacy 파일 대량 이동을 한 번에 수행하지 않는다.

---

## 6. M0에서 변경하지 않을 것

- Steam Session 생성과 Join 흐름
- `MassReplication` Client Bubble 구현
- 실제 Mass Entity Spawner와 Processor
- PPO 가중치와 C++ 추론기
- Creature Representation 완성
- Dedicated Server Target과 배포
- Legacy 코드의 물리적 완전 삭제

이 항목은 각각 M1 이후 Milestone에서 구현한다.

---

## 7. 최종 완료 체크리스트

```text
[ ] Active Runtime과 Legacy 파일 경계가 확정됨
[ ] 신규 코드가 EcoDataContracts.h의 Evolution 타입에 의존하지 않음
[ ] FRegionEcologyState가 지역 자원의 단일 진실값임
[ ] Mass Entity가 개체 논리 상태의 단일 진실값으로 정의됨
[ ] Client는 권위 생태 Simulation을 실행하지 않음
[ ] StableAgentId와 Runtime/Network ID 역할이 분리됨
[ ] Legacy Evolution이 기본 게임 실행에 자동 개입하지 않음
[ ] 경계 자동화 테스트가 통과함
[ ] UnrealBuildTool 빌드가 통과함
```
