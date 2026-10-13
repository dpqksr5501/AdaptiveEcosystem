# Mass 생태계 통합·성능 작업 안내

작성일: 2026-10-11 / 엔진: UE 5.8 / Source 기준: 로컬 `M4`, `6235742`.

이 문서는 서버의 대규모 논리 생태계와 Client의 제한된 복제·표현을 연결하기 위한 작업 순서다. 각 문서는 **구현 계획**이며 완료 보고나 새 성능 측정 결과가 아니다. 이번 변경은 문서만 작성했고 UBT·자동화·PIE·성능 캡처를 실행하지 않았다.

## 1. 기준과 현재 상태

- 팀 main의 PR #11 병합 기준은 `f54e112`이다. 현재 M4는 그 동물 통합과 wonkii의 후속 생존·복제 변경을 포함한다. M4의 모든 기능이 main에 들어갔다고 읽지 않는다.
- Creature 통합은 기존 Network Trait를 상속하고 Ecology·StableAgentId·지역·Mass Bubble을 사용한다. 완전히 독립된 생태계를 새로 만든 구조는 아니다.
- 그러나 M3/M4 Box의 `UEcoMassLifecycleSubsystem`과 동물의 `AEcoCreatureIntegrationSpawner::Reconcile`은 생존·섭식·사망 실행 경로가 다르다. 같은 개체가 현재 두 경로에서 동시에 처리된다고 단정하지 않는다. Bootstrap 혼용 가드를 유지한다.
- 사슴은 V1 PPO/Utility와 Social을 소비한다. 통합 늑대 이동은 별도 감각 기반 추적·배회 규칙이다. 모든 종을 같은 정책 알고리즘으로 바꾸는 계획이 아니다.
- Client는 생태·PPO·Social 결정을 다시 수행하지 않는다. 서버 권위 결과 중 필요한 개체만 수신하고 보간·표현한다.
- `Branch_Sinhyeok`의 V2/V3 실험은 현재 V1 production과 별도다. 이 계획에서 관측·행동·가중치를 묵시적으로 교체하지 않는다.

과거 문서의 `295ac2f` 상태와 최신 opt-in Creature 통합을 구분한다. 현재 Source, 루트 불변 원칙, Active Contract 순서로 확인하고 충돌을 기록한다.

## 2. 우선순위별 작업

| 순서 | 개별 작업 문서 | 결과물 | 기존 단계 |
| --- | --- | --- | --- |
| P1 | [공통 생명주기·권위 실행 통합](P1_AUTHORITY_LIFECYCLE_INTEGRATION.md) | 종별 행동과 공통 생존·자원·사망·집계의 책임/실행 경계 | M3 생존 + Creature + M5 |
| P2 | [계측·성능 기준선](P2_PROFILING_AND_BASELINE.md) | 동물 경로의 서버·복제·표현별 실제 비용 | M4.0 |
| P3 | [검색·감각·반복 순회 개선](P3_SPATIAL_AND_QUERY_OPTIMIZATION.md) | 중첩 검색 제거와 의미를 보존한 후보 선별 | M4.3 + 행동 처리 |
| P4 | [동물 복제·보간·표현 예산](P4_CREATURE_REPLICATION_AND_REPRESENTATION.md) | 연결별 수신·Actor·애니메이션 비용 제한 | M4.2/4.4/4.5/4.6 |
| P5 | [순수 계산 병렬화·시간 스케줄](P5_PARALLEL_PROCESSING_AND_TIME_SCHEDULING.md) | 안전한 Chunk 계산과 FPS 독립 실행 주기 | Policy/Social + M5 |
| P6 | [Simulation LOD·대규모 폐루프 검증](P6_SIMULATION_LOD_AND_SCALE_VALIDATION.md) | 원거리 생태 유지와 규모별 비용/정확성 증거 | M5 + M4.9 |

P2는 P1 이전의 현 상태도 캡처할 수 있다. P1 통합 후 동일 시나리오로 다시 비교한다. P3/P4는 P2 계측과 책임 경계가 확보되면 진행할 수 있으나, P5/P6는 갱신 순서와 결과 적용 계약이 먼저 필요하다. 숫자 순서는 우선순위이며 강제적인 전 작업 직렬 실행을 뜻하지 않는다.

## 3. 공통 불변 조건

1. World는 환경, Ecology는 지역 Food·피식 기록·집계, Mass는 개체 상태의 권위 소유자다. Subsystem에 복제 RPC/프로퍼티를 추가하지 않는다.
2. 개체별 Raw Action을 보존하고 `Policy → Social Request → Movement → Feedback`을 유지한다. 동일 Entity의 최종 위치 writer는 하나다.
3. 복제 relevance Remove·표현 Off는 사망이 아니다. 화면 밖 개체의 Population·생존·지역 결과를 지우지 않는다.
4. Shared Model과 개체별 관측·출력을 유지한다. Policy Output은 Shared Fragment로 옮기지 않는다.
5. EntityHandle은 World 내부 임시 식별이다. 저장·복제는 StableAgentId/RegionId/SpeciesId 계약을 따른다.
6. worker에서 UObject·자원·예약을 직접 변경하지 않는다. 구조 변경은 안전한 Mass 경계에서 수행하고 현재 observer/command-buffer 계약을 따른다.
7. Food 재생 보류 등 경로별 자원 규칙을 통합 중 임의 변경하지 않는다. 정책 수치·주기 변경은 Python/C++ 계약과 평가를 함께 검토한다.

## 4. 담당 연결 제안

아래는 책임 경계에 따른 제안이며 작업 배정이나 담당자의 완료 선언이 아니다.

| 담당 | 연결 책임 |
| --- | --- |
| wonkii | 공통 생명주기·자원·이주·집계, 네트워크/Client 예산·계측 |
| sinhyeok04 | 관측·추론·조향·시간 계약, Python/C++ 파리티와 정책 재평가 |
| 조연우 | 감각·Herd/Alarm·Shelter Request/Feedback·정리, 동물 표현·소음 회귀 |
| avaroki | 실제 레벨·물/지형·충돌·스트리밍 입력, 재현 가능한 공간 시나리오 |

## 5. 시작 문서와 공식 근거

- [루트 AGENTS.md](../../../AGENTS.md), [Active Runtime 경계](../Architecture/ACTIVE_RUNTIME_BOUNDARIES.md), [Mass 실행 순서](../Mass/MASS_PROCESSOR_ORDER.md)
- [V1 정책 계약](../RL_Policy/POLICY_CONTRACT_V1.md), [조연우 최신 시작 문서](../조연우/README.md), [M4 상세 계획](../Roadmap/M4/M4_IMPLEMENTATION_PLAN.md)
- [Epic MassEntity](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-entity-in-unreal-engine): 데이터·Archetype·Chunk·Processor 구성의 근거.
- [Epic MassGameplay](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-gameplay-in-unreal-engine): Simulation/Replication/Representation LOD, 표현 전환·풀링의 근거.

공식 기능을 사용할 수 있다는 사실과 프로젝트에 적용·성능 검증됐다는 사실을 구분한다. 기존 [통합 맵 안내](ECOSYSTEM_INTEGRATION_MAP_SETUP.md)와 [외부 프레임워크 통합 문서](THIRD_PARTY_INTEGRATION.md)는 별도 범위를 유지한다.
