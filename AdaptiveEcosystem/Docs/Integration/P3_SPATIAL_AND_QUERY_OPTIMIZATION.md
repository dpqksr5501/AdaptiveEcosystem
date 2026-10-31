# P3 — 공간 검색·감각 후보·반복 순회 개선

작성일: 2026-10-11 / UE 5.8 / 기준: `M4`, `6235742` / 상태: 최적화 계획, 비용 실측 없음.

[전체 순서](README.md) · 이전: [P2](P2_PROFILING_AND_BASELINE.md) · 다음: [P4](P4_CREATURE_REPLICATION_AND_REPRESENTATION.md)

## 1. 목적과 선행 조건

P1의 권위/요청 계약과 P2의 기준선을 사용해 중첩 조회·불필요한 후보 검사·반복 World 탐색을 줄인다. 기존 감각 지식·먹이 배분·예약 결과의 의미를 보존한다. 공간 트리나 SIMD를 도입하는 것 자체를 완료 목표로 삼지 않는다.

## 2. 확인한 개선 후보

| 근거 Source | 현재 패턴 | 개선 후보 |
| --- | --- | --- |
| [Creature Spawner](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.cpp) | Feeding Result마다 Owned 개체를 재검색 | step 수명의 ID→handle/index lookup 또는 요청-result 연결 |
| [Predator Perception](../../Source/AdaptiveEcosystem/AI/Social/Senses/EcoPredatorPerception.cpp) | alive prey 목록을 만들고 각 관찰자가 순회 | 공간 broad phase로 근처 후보만 선별 |
| [Neighborhood Subsystem](../../Source/AdaptiveEcosystem/AI/Policy/EcoNeighborhoodSubsystem.cpp) | 매 frame Entries/Cells 재구축, radius query | 구축/할당/query 비용 비교 후 재사용·갱신 방식 결정 |
| [Creature Movement](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureMovement.cpp) | 이동 guard의 충돌/지면 검사와 NavModifierVolume 조회 | 공간/레벨 입력 snapshot·cache 및 검사 예산 검토 |
| [Threat Detection](../../Source/AdaptiveEcosystem/AI/Social/Alarm/EcoThreatDetectionProcessor.cpp) | grid 후보와 World LOS·청각 차폐 검사 | 후보·Trace 수 계측, 중복 검사의 안전한 제거 |

결과 수가 N과 함께 늘면 현재 Feeding 매칭은 최악 O(N²), predator 후보는 O(P×N)에 가까워질 수 있다. 이는 코드 구조 분석이며 실제 병목 순위나 개선 배율 측정값이 아니다.

## 3. 작업 A — 요청/결과 매칭

1. P1 공통 Feeding 경계에서 요청과 결과의 연결 정보를 만든다. Spawner의 중첩 검색을 별도로 영구 유지하지 않는다.
2. EntityHandle은 World/step 내부에서만 사용하고 적용 시 유효성·StableAgentId·Epoch/Step·Alive/pending 상태를 재확인한다.
3. 삭제·Archetype 변경·ID 재등록 후 stale handle/index를 사용하지 않는다. 기존 Fragment 참조를 구조 변경 뒤 보관하지 않는다.
4. 지역별 공정 배분·정렬·실제 GrantedAmount를 유지하며 중복 적용을 거부한다.

완료: 결과 처리량이 선형에 가까운지 계측하고 기존 배분 합계·에너지 회복·사망 직전 요청 취소가 일치한다.

## 4. 작업 B — 감각 broad phase

1. species/region/위치 등 읽기 snapshot과 공통 grid를 이용해 거리상 가능한 후보만 수집한다.
2. 후보에 기존 거리·시야각·LOS·Alive·종 조건을 적용한다. Region 경계/이주 중 후보를 누락하지 않는다.
3. stable ID 등 일관된 tie-break를 유지해 grid bucket 순서가 표적·예약 결과를 바꾸지 않게 한다.
4. 기억·청각 좌표를 시야 밖 실제 위치로 교체하지 않는다. 포식의 최근 직접 Sight/LOS 요구를 보존한다.
5. LOS/청각 검사 주기 변경은 별도 행동 변경으로 기록하고 P5 시간 계약과 검증한다.

완료: 경계/원점/밀집/이동·삭제 직후의 후보 정확성을 brute-force 기준과 대조하고 후보 수·Trace 수·총 CPU 시간을 비교한다.

## 5. 작업 C — 공간/World 입력과 할당

- 매 pass 임시 배열·map 생성과 용량 증가를 계측해 안정적인 버퍼 재사용을 검토한다. 캐시를 늘려 메모리 비용을 숨기지 않는다.
- 지역 bounds·물 금지 구간·NavModifierVolume은 레벨 작성자가 제공하는 공간 데이터로 정리한다. World Partition 로드/언로드, 에셋 변경, 동적 장애물에 대한 invalidation을 정의한다.
- 지면 높이·장애물 캐시는 연산을 줄일 수 있지만 경사·물·충돌 의미가 달라지면 별도 근사 처리로 검증한다.
- 행동 이웃 grid와 복제 relevance 공간 인덱스는 목적/주기가 다르다. 같다는 이유로 무조건 하나로 합치지 않는다.
- dense grid·spatial hash·quadtree/octree는 동일 분포의 query+갱신+메모리 총비용으로 선택한다. 기존 grid는 비교 baseline으로 유지한다.

## 6. 완료 기준·연결 담당

정확성은 Food/관측/표적/예약 결과와 생명주기 이벤트를 확인하고, 성능은 동일 N·밀도·Client 조건의 P2 기준선과 비교한다. 한산한 맵뿐 아니라 높은 밀도·큰 반경·음수 좌표·cell 경계·이주·streaming 변화를 포함한다.

wonkii는 요청/결과와 복제 공간 검색, sinhyeok04는 관측 이웃/조향, 조연우는 감각/기억/포식 조건, avaroki는 World 공간 입력을 검토하는 제안이다. C++ 변경 후 직접 UBT와 변경에 필요한 정확성 회귀를 수행한다.

참조: [M4 공간 검색 단계](../Roadmap/M4/M4_IMPLEMENTATION_PLAN.md), [감각 계약](../조연우/SOCIAL_SENSORY_RUNTIME.md), [최신 감각 검증 범위](../조연우/CREATURE_SENSORY_AND_NOTIFY_REFINEMENT.md), [Epic MassEntity Chunk 처리](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-entity-in-unreal-engine).
