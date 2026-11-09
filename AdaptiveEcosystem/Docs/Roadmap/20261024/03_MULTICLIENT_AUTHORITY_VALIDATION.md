# T03. 동시 Client·늦은 참가·재접속·무관찰 상태 정합성

상태: 검증·필요 보완 개발 명세 / 기준: `8836558` / 책임 제안: 원준, 조연우 표현 회귀·World 공간 구성 협업.

선행: [T01](01_RUNTIME_CONFIGURATION_AND_AUTHORITY.md), [T02](02_AGENT_PRESENTATION_REPLICATION.md). 확인: [F01·F04·F05·F15·F18](99_DECISIONS_AND_CONFIRMATIONS.md).

## 1. 목적과 현재 근거

Client 수와 관찰 위치가 달라도 서버 생태는 한 번만 실행돼야 한다. 각 연결은 자신의 관련 개체를 받으며 지역 요약은 같은 완료 결과를 나타내야 한다.

기존 M4/JYU 기록은 Dedicated 서버와 순차 Client 두 번 접속·논리 0·표현 재생성 증거를 제공한다. 이를 동시 Client 2개, 불량망, 공식 맵, 현재 commit의 통과로 확대하지 않는다. 이번 업무는 실제 동시 실행 증거를 확보하고 실패 원인만 보완한다.

## 2. 검증 구성

| 구성 | 목적 | 최소 실행안 |
|---|---|---|
| Standalone | 기능·원장 기준 | 고정 seed·소수 개체 |
| Dedicated + 동시 Client A/B | 연결별 분리 | A/B 다른 지역, 이후 같은 개체 관찰 |
| Listen Host + 원격 Client A/B | Host 표현 비용·권위 | 로컬 Host와 원격 2개를 구분 |
| Dedicated + 접속자 0 | no-player 논리 진행 | 시작·진행·재접속 세 구간 기록 |
| packaged/Steam | 최종 접속 경로 | T11에서 별도 실행 |

서버가 계속 실행 중인 Dedicated의 no-player를 Host 종료 뒤 서버 승계와 혼동하지 않는다. Listen Host가 종료하면 MVP 세션도 종료한다.

## 3. 비교할 데이터

서버: 전체 alive ID·지역/종, 누적 Birth/Death/In/Out, Food 원장, 완료 step, 정책/Native step, 예약 수·만료, 연결별 relevance/Add/Remove/LOD.

Client: epoch·summary step/revision, 수신된 StableAgentId·생사·Activity, Proxy/Actor 수, sample/visual/reset revision, pending template, rejected/reset/pool 카운터.

Client의 보이는 개체 수를 Population과 직접 비교하지 않는다. 관심 영역·Actor 예산 때문에 부분집합일 수 있다. 서로 다른 수신 시점의 평균 에너지나 위치가 즉시 같은 것도 요구하지 않는다. 동일 완료 요약은 동일 값, 상태 전달은 확정 지연 기준 안의 수렴으로 판정한다.

## 4. 실행 절차

1. T01 manifest와 변경 없는 seed·설정으로 서버를 시작한다.
2. Client A/B를 동시에 접속시키고 각 연결의 ID를 진단 로그에 부여한다.
3. A는 지역 A, B는 지역 B에서 관찰한다. 한 연결 이동이 다른 연결의 interval/LOD를 덮지 않는지 본다.
4. 같은 개체를 가까이/멀리 본 뒤 연결별 관련 상태와 서버 공통 ID를 비교한다.
5. 정지 중 행동 변경·사망, 포식과 resource receipt를 발생시키고 로그를 연결한다.
6. A 이탈·재접속, B는 유지한 상태로 수행한다. 서버 spawn·인구가 접속 때문에 재시작되지 않아야 한다.
7. Dedicated에서 전원 이탈 후 논리 진행을 기록하고 다시 접속해 현재 snapshot을 받는다.
8. T07/T08 개발 후 같은 틀로 출생·이주 결과를 추가 검증한다.

## 5. 필수 시나리오

| ID | 상황 | 판정 |
|---|---|---|
| MC01 | 동시 A/B가 다른 지역 | 서로 다른 관련 집합, 공통 서버 논리는 1회 |
| MC02 | 같은 개체의 연결별 거리 차이 | 같은 StableAgentId, 서로 독립된 LOD·주기 |
| MC03 | A 접속 종료·재진입, B 유지 | 중복 spawn/Population 변동 0, A 최신 상태 |
| MC04 | 개체가 죽은 뒤 늦은 접속 | 현재 생사/제거 정책을 수신, 부활 ghost 없음 |
| MC05 | 카메라가 지역 경계·Off를 왕복 | Proxy Add/Remove와 server Death 분리 |
| MC06 | Dedicated no-player | Food·생존·lease 진행, 새 관찰자에게 현재 상태 |
| MC07 | template 등록 지연 중 Remove | 대기 취소, 이후 늦은 생성 없음 |
| MC08 | 맵 이동·새 epoch | 이전 summary·binding·pending add 잔류 없음 |
| MC09 | T07 출생·T08 도착 | 현재 원장과 ID 결과가 두 Client에 수렴 |
| MC10 | Listen 로컬 Host의 표현 | Host도 Actor/풀 예산 준수, 이중 논리 없음 |

## 6. 불변식과 실패 분류

- 공통 누적/기간 기준을 명시한 Population 보존식을 매 완료 step 검사한다.
- 관심 영역 Remove, Actor 반환, 연결 종료로 Birth/Death/In/Out을 만들지 않는다.
- Client authoritative Owned·policy/native step은 0이다. 읽기 전용 debug·animation tick은 이 수에 포함하지 않는다.
- summary는 같은 epoch·step·revision에서 비교한다. agent 이동 표본과 resource summary의 갱신 주기는 다름을 허용한다.
- 재접속 후 현재 상태를 보는 것과 이탈 중 모든 중간 사건을 재생하는 것은 별도 요구다. 후자는 F15 결정 전 보장하지 않는다.

실패는 Config/Template, Authority, Identity, Summary, Relevance, Presentation, Timing으로 분류한다. 증상을 감추려고 관련 개체 상한을 무제한으로 올리거나 Client 시뮬레이션을 켜지 않는다.

## 7. 산출물과 완료 조건

시나리오마다 서버/A/B 로그·맵·RunId·실제 동시 접속 구간·접속 타임라인·판정표를 남긴다. 순차와 동시 접속, headless와 렌더 확인을 분리 기록한다.

선택한 최종 backend에서 MC01~MC08·MC10을 통과해야 기본 복제 완료다. MC09는 T07/T08 완료 뒤 추가 게이트다. 지연·loss 기준을 적용한 결과는 T04, package·Steam 결과는 T11로 인계한다.

## 8. Source·기존 증거

- [GameState snapshot publish](../../../Source/AdaptiveEcosystem/Network/EcoGameState.cpp), [완료 요약 형식](../../../Source/AdaptiveEcosystem/Network/EcologyNetworkTypes.h)
- [인구 보존·summary](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePopulation.cpp)
- [연결별 Replicator](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp), [pending Add](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.cpp)
- [기존 M4 실행 기록](../../Integration/M4_IMPLEMENTATION_PROGRESS.md), [JYU 순차 접속 기록](../../조연우/JYU_V3_SOCIAL_HANDOFF.md)
