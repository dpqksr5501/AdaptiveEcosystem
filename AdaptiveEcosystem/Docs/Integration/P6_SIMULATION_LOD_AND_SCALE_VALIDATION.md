# P6 — Simulation LOD와 대규모 생태 폐루프 검증

작성일: 2026-10-11 / UE 5.8 / 기준: `M4`, `6235742` / 상태: 후속 설계·검증 계획, 규모 목표 미달성.

[전체 순서](README.md) · 이전: [P5](P5_PARALLEL_PROCESSING_AND_TIME_SCHEDULING.md)

## 1. 목적과 선행 조건

서버가 멀리 있는 개체의 생태 결과를 유지하면서 정밀 감각·행동·이동 비용을 관리한다. P1 공통 생명주기, P2 기준선, P4 Client 예산, P5 시간·계산 계약이 선행 조건이다. 지역 집계만 남기는 모델은 개체 상태를 유지하는 저주기 LOD와 다른 설계이므로 별도 결정 없이 도입하지 않는다.

Epic의 [MassGameplay 문서](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-gameplay-in-unreal-engine)는 Simulation LOD의 Chunk 분류·가변 계산 주기, 연결별 Replication LOD, 화면 Representation LOD를 구분한다. 엔진 기능은 생태 보존·학습 파리티를 자동 보장하지 않는다.

## 2. 세 LOD의 의미

| LOD | 소유 범위 | 비용 조절 | 유지할 상태 |
| --- | --- | --- | --- |
| Simulation | 서버 논리 | 감각·정책·이동의 정밀도/주기 | ID·생존·자원 사건·Region·Population |
| Replication | 각 Client 연결 | 관련 개체·표본 주기/우선순위 | 서버 논리의 지속과 권위 |
| Representation | Host/Client 화면 | Actor/메시·애니메이션·소리 | Proxy/논리 생존과 구분 |

화면 밖·relevance Off 개체를 죽이거나 Population에서 제외하지 않는다. 한 Client의 시야를 서버 전역 Simulation LOD로 직접 사용하지 않는다. 여러 플레이어·상호작용·경보·포식·이주 경계의 중요도를 함께 고려한다.

## 3. 현재 가드와 첫 구현 범위

[M3 Bootstrap](../../Source/AdaptiveEcosystem/Mass/EcoMassNetworkBootstrap.cpp)은 Simulation LOD 혼용을 거부한다. 이동 정지/이중 writer 위험을 방지하는 현재 계약이다. 먼저 P1 통합 경로에서 variable tick·Travel·Alive Query·writer를 확인하고 제한된 opt-in 구성으로 검증한다. 가드 제거를 시작 작업으로 삼지 않는다.

첫 단계는 개체 ID/Fragment를 유지한 채 일부 계산 빈도를 낮추는 것이다. 구체적인 거리·Hz·최대 N·예산은 P2 결과와 정책 시간 계약으로 결정한다. 본 문서는 검증되지 않은 기본 수치를 지정하지 않는다.

## 4. 설계 작업

1. 중요도 입력: 모든 권위 viewer, 실제 상호작용, 위협/포식, Shelter 예약·lease, Travel·도착 예정, 지역 자원 사건을 정리한다.
2. 계산별 주기: 정책/감각/이동/기억/대사/섭식/집계를 나눈다. 최종 LOD 등급 하나로 모든 계산을 무조건 끄지 않는다.
3. 경과 시간: 미실행 interval을 명시적으로 반영한다. 큰 dt의 충돌 통과·도착 초과·사망 이후 소비를 방지할 처리 규칙을 정한다.
4. 자원: 실제 GrantedFood·누적 소비·공급·손실과 종료 Food의 보존식을 유지한다. LOD 전환에서 요청을 중복 제출하지 않는다.
5. 생명주기: 대사/기아/사망·예약 만료·피식 cooldown·기억/Alarm 감쇠를 시간 기준으로 처리한다. 정확한 사건 시각과 허용 지연을 구분한다.
6. 승격: 오래된 행동·목적지·감각 cache와 lease를 재검증하고 상태를 최신화한다. 승격 burst는 예산/분산으로 관리한다.
7. World Partition: 화면에 로드되지 않은 지형/물/은신처의 서버 논리 입력 공급을 정의한다. 전체 habitat를 항상 로드하는 비용도 측정한다.

근사 이동·감각은 full-rate와 다른 결과를 만들 수 있다. Food/ID/단일 Death 등의 불변 조건과 행동/시간 오차 허용 기준을 분리하고 사전에 기록한다. 관측 의미·정규화·행동 역매핑·가중치를 임의 변경하지 않는다.

## 5. 대규모 검증 행렬

| 시나리오 | 확인할 정확성 | 측정할 비용 |
| --- | --- | --- |
| 원거리 부재 후 재방문 | Food/Energy/Population/Region의 연속 변화 | 원거리 서버 논리 시간 |
| 다중 Client 분산 | 서버 결정 한 번, 각 연결 relevance 독립 | Client 수별 CPU/bytes/Proxy |
| 고밀도 위협·은신처 경합 | 감각/포식/예약·정리·단일 Death | 후보/Trace·p95/p99 |
| 고갈·과밀·A→B 이주 | 동일 ID·인구 보존·도착·식사 경계 | Migration/집계/catch-up |
| 동시 진입·승격·스폰 | 중복 Actor/표본·queue 누수 없음 | 최대 frame/packet·생성량 |
| 지연·손실·저 FPS·재접속 | stale 보간/ghost 제거·상태 초기화 | 지연 회복·메모리 잔류 |
| 장시간 고갈/공급 | 자원 보존·기아·회복·예상 사망 | 누수/queue 증가·서버 안정성 |

현 유효 구성부터 N·밀도·종 비율·Client 수를 단계적으로 확대한다. 현재 512 초기화 상한을 넘는 시험은 별도 구성/코드 변경 후 검증한다. 1000/5000/10000 등은 선택할 시험 목표이며 현재 지원·성능 달성을 뜻하지 않는다.

full-rate 기준과 LOD 버전을 같은 seed/config/환경에서 비교한다. 기능별 비활성 비교와 표현 없음 비교로 비용의 원인을 분리한다. 다른 개체 수·렌더·충돌 규칙을 쓴 결과를 Mass의 배율로 제시하지 않는다.

## 6. 최종 완료 증거

- 대규모 서버 Entity 수와 각 Client Proxy/Actor 수를 동시에 보여주고 각각의 예산을 만족한다.
- 화면 밖 지역도 자원·생존·이주 결과가 다음 관측으로 돌아오는 폐루프를 확인한다.
- N·밀도·Client 수별 hardware/build/측정 구간과 p50/p95/p99·메모리·전송량 표가 있다.
- ID 중복·중복 소비/Death·Population 불일치·예약 누수·Client 권위 계산이 없다.
- 기준 시뮬레이션과의 근사 오차/사건 지연을 사전 기준으로 판정한다. 미검증/실패와 미지원 범위를 남긴다.

제안 담당: wonkii는 서버 LOD/권위/네트워크/규모 보고, sinhyeok04는 정책 시간·파리티·행동 비교, 조연우는 감각·예약·표현 회귀, avaroki는 원거리 레벨/streaming 입력. 관련 C++ 변경 후 직접 UBT와 통합 실행 검증을 수행한다.

참조: [M4 단계/완료 게이트](../Roadmap/M4/M4_IMPLEMENTATION_PLAN.md), [M5 폐루프](../Roadmap/M5/M5_PPO_CLOSED_LOOP.md), [P2 계측](P2_PROFILING_AND_BASELINE.md), [생존 검증의 한계](../Roadmap/M3/OVERCROWDING_STARVATION_VALIDATION_REPORT.md).
