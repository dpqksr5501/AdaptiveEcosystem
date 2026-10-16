# P2 — 실제 동물 경로의 계측과 성능 기준선

작성일: 2026-10-11 / UE 5.8 / 기준: `M4`, `6235742` / 상태: 측정 계획, 신규 캡처 없음.

[전체 순서](README.md) · 이전: [P1](P1_AUTHORITY_LIFECYCLE_INTEGRATION.md) · 다음: [P3](P3_SPATIAL_AND_QUERY_OPTIMIZATION.md)

## 1. 목적

Mass Entity 수가 늘 때 서버 논리·Client 복제·동물 표현 중 어디서 비용이 증가하는지 분리한다. 기능 통과, 평균 FPS, 대규모 성능 통과를 구분한다. P1 이전 현 상태와 P1 이후를 같은 조건에서 비교할 수 있다.

## 2. 기준 Source와 현재 한계

- [EcoBehaviorProcessors.cpp](../../Source/AdaptiveEcosystem/AI/Policy/EcoBehaviorProcessors.cpp): Gather/Perception/Policy/Predation/Steering 비용과 GameThread 실행.
- [EcoCreatureIntegrationSpawner.cpp](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.cpp): Reconcile·SyncVisuals·PublishSummary와 전체 순회.
- [EcoMassReplicator.cpp](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp), [EcoMassClientBubble.cpp](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.cpp): 연결별 표본·갱신·제거.
- [M4.2 계측](../Roadmap/M4/M4_2_REPLICATION_INTERVAL.md): `eco.M4.Dump`, `eco.M4.TraceSamples` 의미. counters/설정 존재가 실제 packet 간격/예산 통과의 증거는 아니다.

현재 Creature 초기화는 `GlobalPopulationLimit > 512`를 거부한다. 처음에는 유효한 구성 범위에서 시험하고, 1000개체 이상은 별도 규모 확장·구성 검증 후 실행한다. 상한만 제거해 성능을 증명하지 않는다.

## 3. 계측 항목

| 영역 | 필수 시간/수량 | 구분할 내용 |
| --- | --- | --- |
| 서버 프레임 | 전체·GameThread·worker 시간, p50/p95/p99, spike | CPU 논리와 렌더 비용 |
| 행동 | Gather/감각/관측/추론/Social/이동 시간, 실제 갱신 개체 수 | 대상 Entity 수와 이번 pass 실행 수 |
| 공간/충돌 | grid rebuild/query, 후보 수, LOS/지면/장애물 Trace 횟수 | 균일 배치와 고밀도 군집 |
| 생태 | Feeding/Survival/Migration/집계 시간, 결과 매칭 수 | step 주기·catch-up·보존 실패 |
| 복제 | 연결별 관련 개체·LOD·Add/Remove·dirty·표본 간격·bytes | dirty 생성과 실제 packet 전송 |
| Client | Proxy·Actor·Skeletal Mesh·풀 수, 표현/보간 시간 | relevance와 화면 가시성 |
| 애니메이션/오디오 | 갱신 수·CPU 시간·동시 재생 수 | 서버 논리 소음과 로컬 재생 |
| 메모리 | Fragment/Query buffer·Actor/자산·수신 버퍼 사용량 | 시작·안정·재진입 후 잔류 |

진단 함수와 상세 로그는 측정 모드를 분리한다. 화면 Debug Draw·Trace 로그 자체가 비용을 바꾸므로 기능 진단 캡처와 성능 캡처를 따로 기록한다.

## 4. 재현 시나리오

1. 현 기본 동물 레벨: 사슴/늑대·먹이·은신처 설정을 기록하고 warm-up 이후 고정 구간 측정.
2. 규모 단계: 유효한 설정에서 소수→중간→상한 근처로 증가. 실제 Spawn 성공 수를 기록한다. 이후 확장 목표는 P6에서 결정한다.
3. 밀도 단계: 같은 N으로 넓은 분산/한곳 군집/은신처 경합을 비교한다.
4. Client 단계: 같은 서버 N으로 Client 수와 서로 다른 위치·시야를 바꾼다. 접속 수 증가와 N 증가의 비용을 분리한다.
5. burst 단계: 관심 영역 동시 진입/이탈·재접속·사망 집단 발생의 최대 frame/packet 크기를 측정한다.
6. 논리 분리: Dedicated 서버, Listen Host, Client의 비용을 별도 기록한다. Box나 NullRHI 결과를 동물 렌더 성능으로 쓰지 않는다.

같은 commit/config/seed/실제 개체 수/시간 길이/카메라/날씨 조건으로 전후 비교한다. 무작위·경로 차이가 큰 시험은 반복 실행 분포를 보고한다. 목표 FPS·서버 tick budget·하드웨어·Client 수는 측정 전에 기록하며 현재 문서에서 달성 수치를 만들어 넣지 않는다.

## 5. 캡처와 기록 형식

Epic의 [Unreal Insights 성능 안내](https://dev.epicgames.com/documentation/en-us/unreal-engine/introduction-to-performance-profiling-and-configuration-in-unreal-engine)는 thread·메모리·대역폭 분석을 제공한다. [Networking Insights](https://dev.epicgames.com/documentation/en-us/unreal-engine/networking-insights-in-unreal-engine)는 packet·연결·속성별 전송 분석의 근거다.

네트워크 캡처의 공식 예는 `-trace=net -NetTrace=1`이며 Editor 환경에서는 tracehost 등 세션 설정도 확인한다. 설치된 UE 5.8에서 사용 가능한 Mass trace channel/Insights 기능은 실제 엔진과 캡처로 확인한다. 아직 실행하지 않은 명령이나 화면을 성공 기록으로 쓰지 않는다.

| 기록 필드 | 내용 |
| --- | --- |
| 실행 식별 | commit/branch, UE 버전, 날짜, map, config, seed |
| 장비/프로세스 | CPU/GPU/RAM, 해상도, build, server/client 모드 |
| 부하 | 실제 Alive/Dead/종별 수, Client 수, 분포·밀도 |
| 결과 | 측정 구간·반복 수, p50/p95/p99/max, ms/bytes/count 단위 |
| 정확성 | Food·Population·중복 Death·예약 누수·Client 논리 실행 여부 |
| 증거 | trace/로그 경로, 집계표, 미실행 항목과 제한 |

큰 trace/Saved 산출물을 무조건 Git에 추가하지 않는다. 체크인 보고서에 재현 설정·요약·산출물 위치를 남긴다.

## 6. 완료 기준과 인계

- 서버/복제/Client 표현 비용을 분리한 재현 가능한 기준선이 있다.
- N·밀도·Client 수를 별도 축으로 비교하고 spike를 평균에 숨기지 않는다.
- 측정된 상위 비용을 근거로 P3/P4/P5의 실제 작업 순서를 조정한다.
- 최적화 후 정확성과 비용을 동일 조건에서 비교할 수 있다.

계측 구현 제안은 wonkii 중심이며 각 담당이 자신의 구간과 의미를 검토한다. C++ 변경 시 루트 빌드 규칙을 적용한다. 기존 [M4 검증 기록](../Roadmap/M4/M4_VALIDATION_REPORT.md)의 미검증 항목을 새 캡처 없이 통과로 바꾸지 않는다.
