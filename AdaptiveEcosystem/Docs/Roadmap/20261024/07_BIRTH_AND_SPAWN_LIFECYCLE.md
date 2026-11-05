# T07. 지정 위치의 실제 출생·안전한 Mass 생성

상태: 신규 공통 API·backend adapter 명세 / 기준: `8836558` / 책임 제안: 원준 생성·ID·회계, 권신혁 번식·v3 초기화, 조연우 Herd·표현.

선행: [T01](01_RUNTIME_CONFIGURATION_AND_AUTHORITY.md). 확인: [F11·F12](99_DECISIONS_AND_CONFIRMATIONS.md). 연계: T03/T08/T11.

## 1. 목적과 현재 공백

부모 근처에서 새 생애를 가진 개체를 실제 생성하고 Births·Population·Client 표현까지 한 번만 반영한다. 사망만 누적되는 v3 실행을 재생산 가능한 생태계로 확장하는 공통 기반이다.

현재 비공개 Spawn(RegionId, Count, bPredator)는 그룹 시작 위치를 사용한다. StableAgentId 발급과 초기화·SuccessfulBirths/SpeciesTotals 반영은 있으나 지정 위치의 번식 요청 계약은 없다. Native 번식 표시/에너지 변화·ReproducedStep을 실제 새끼 Entity 생성으로 해석하지 않는다. v3 통합은 wave를 끈다.

## 2. 범위와 책임

포함: 서버 로컬 출생 요청·중복 방지·상한 예약·지면 위치 검증·Mass 생성·정책별 초기화·결과 receipt·회계·복제.

제외: 번식 확률/주기/비용 임의 변경, 성장·유전·새 juvenile rig, Client 직접 spawn RPC, 사망 개체의 ID 재활용, wave를 번식 대용으로 켜기.

권신혁은 언제·어느 부모가·어떤 비용으로 요청하는지와 Native 상태 초기화를 제공한다. 원준은 안전 생성·성공 확정·원장을 소유한다. 조연우는 부모 무리 가입 정책과 수동 표현을 연결한다.

## 3. 요청·결과의 논리 계약 제안

아래 이름은 설계용이다. 실제 타입은 Core 공통 요청과 backend adapter 책임을 분리해 구현 시 확정한다.

| 요청 필드 | 의미·검증 |
|---|---|
| WorldEpoch + BirthRequestId | world 내부 고유 요청, 중복 key |
| ParentStableAgentId + ReproductionRevision | 같은 번식 사건의 재시도 식별 |
| SpeciesId/RegionId/Backend | 허용 종·부모/지역·구성 검증 |
| DesiredWorldPosition/MaxPlacementRadius | Unreal cm, 유한값·지역·지면 검사 |
| RequestedAt/Deadline | 공통 서버 논리 시각 |
| ExpectedParentStateRevision | 대기 중 죽음·이주·상태 변경 재검증 |
| InitializationProfileId | 합의된 초기 에너지·비축·행동 프로필 |

결과는 RequestId, Pending/Committed/Rejected/Cancelled, 새 StableAgentId, 실제 위치·지역, BirthTime·CompletedStep, 실패 사유를 갖는다. 외부에는 EntityHandle을 반환하지 않는다. 같은 key·같은 payload 재요청은 기존 결과를 돌려주고 다른 payload는 충돌로 거부한다.

## 4. 처리 상태와 확정 경계

```text
Requested → Validated → CapacityReserved → CreationStaged
          → BackendInitialized → Committed
어느 미확정 단계든 → Rejected/Cancelled + 예약·임시 개체 정리
```

1. 요청을 큐에 넣고 현재 서버/Standalone·epoch·부모 생존·지원 종·backend를 검사한다.
2. alive와 생성 대기 예약을 합산해 세계·지역 상한을 예약한다. dead 표현 잔류의 메모리 상한은 별도다.
3. 원하는 위치 주변을 제한된 횟수·정해진 동점 순서로 검사한다. 부모와 너무 겹치는 위치·보호 영역 규칙·지면 미준비를 처리한다. 전체 맵을 무제한 검색하지 않는다.
4. Mass가 순회 중이 아닌 정해진 Game Thread 생성 경계에서 Entity를 만든다. 초기화 완료 전 일반 정책·포식 Query가 읽지 않게 creation context/태그 공개 시점을 관리한다.
5. ID를 서버에서 발급하고 종·지역·lifetime·vitals·정책·Social 기본값을 초기화한다. 실패해 사용한 ID는 다시 발급하지 않는다.
6. backend가 Native Body·관측·행동·region membership까지 준비됐음을 확인한다.
7. 같은 안전 경계에서 Owned/lookup·출생 회계·부모 비용 확정·결과 receipt를 공개한다. 실패 가능 검사는 먼저 끝내고 commit 구간의 부분 성공을 방지한다.
8. 완료 summary와 Mass 복제는 이후 현재 상태를 publish한다. 두 채널이 같은 packet으로 도착한다는 보장은 하지 않는다.

## 5. v3 초기화의 별도 요구

현재 v3는 지역 stage 계획과 AdoptedDeer/Native view 배열·ContextIndex에 의존한다. 기존 Spawn을 공개하는 것만으로 Native 개체가 올바르게 추가되지 않는다.

adapter는 새 개체의 Region context, Unreal cm↔Native 단위, Body·reserve, Rep/decision, mask·cooldown, observation/perception cache, 결정 phase, ID 정렬·view 재구축을 초기화한다. 진행 중 Step이 보관한 포인터·배열 view를 재할당으로 무효화하지 않는다. 최초 관측 전 임의 상수로 추론하지 않는다.

초기화 시각 이전으로 대사·섭식을 catch-up하지 않는다. 관측·위협 난수/phase 초기화는 RL 계약에 맞추고 새 개체가 죽은 개체의 슬롯·기억·도망 기록을 상속하지 않게 한다. 새 개체가 늘어난 뒤 원래 개체의 ID 순서와 Native index를 혼동하지 않는다.

## 6. 부모 비용·취소·중복

F11은 필수다. 현재 Native의 번식 시점 에너지 처리를 그대로 둔 채 별도 생성에서 비용을 또 빼지 않는다. 요청/비용 예약/실제 출생 확정으로 나누거나, 실패 시 비용 의미를 명시하는 RL 계약 변경이 필요하다.

권고는 실제 생성 성공에 비용을 한 번만 확정하는 방식이다. 비용 예약 후 부모가 죽거나 이주하면 commit 직전 재검증한다. 비용을 환불하는 정책을 선택한다면 같은 receipt를 두 번 환불하지 않는다.

중복 결과 캐시는 world 수명으로 관리한다. 무제한 메모리 대신 완료 요청 high-watermark/제한된 기록 정책을 정하고, 캐시에서 사라진 옛 key를 새 요청으로 재실행하지 않는다. EndPlay는 대기 요청·capacity 예약을 취소한다.

## 7. 생성·회계 실패 처리

초기화 실패한 임시 Entity는 공개 전 안전하게 제거하고 Owned·성공 Births에 넣지 않는다. commit 후 유효 출생은 취소로 지우지 않는다. 이후 사망은 기존 Death 경로로 별도 확정한다.

현재 누적 Births에는 초기 생성도 포함된다. 세계 alive = SuccessfulBirths - CommittedDeaths, 지역×종 Population = Births - Deaths + In - Out 계약을 유지한다. T03의 기간 비교에서는 시작 snapshot을 빼서 실제 새 출생만 센다.

구조적 불일치가 생기면 기존 FailRuntime/Ready 정책으로 중단·진단하고 Population을 임의 max/대입으로 맞추지 않는다.

## 8. 구현 단위

- BT-A: F11/F12를 결정하고 request/result·상한 예약·실패 사유를 정의한다.
- BT-B: 초기 Spawn과 공통 초기화 부분을 재사용하되 지정 위치 경로를 분리한다.
- BT-C: v3 동적 adoption과 부모 비용 hook을 권신혁과 연결한다.
- BT-D: 회계·summary·Client Add·Herd 초기화를 연결한다.
- BT-E: 실패·중복·동시 다수 요청·저 FPS·재접속을 검증한다.

## 9. 검증 시나리오

| ID | 조건 | 기대 결과 |
|---|---|---|
| BT01 | 부모 근처 정상 출생 | 새 ID 1개·실제 위치·Births+1 |
| BT02 | 같은 요청 반복/다른 payload | 중복 생성 0, payload 충돌 거부 |
| BT03 | 상한 직전 동시 요청 | pending 포함 상한 유지 |
| BT04 | 부모 죽음·이주·deadline 초과 | 합의된 취소/성공 정책, 비용 중복 없음 |
| BT05 | 지면 미준비·충돌·범위 밖 | 제한 대기/거부, 예약 누수 0 |
| BT06 | Native 초기화 중 실패 | ghost Entity·성공 Births 없음 |
| BT07 | 생성 직후 포식·기아 | 출생/사망 각 1회, 순서 있는 receipt |
| BT08 | 저 FPS의 catch-up | 출생 전 식사·대사 적용 없음 |
| BT09 | Client 동시·늦은 참가 | 같은 새 ID를 현재 상태로 표현 |
| BT10 | 다수 생성 후 Native Step | 기존/신규 개체 view 유효, 중복 adoption 없음 |

## 10. 완료 조건

공통 API가 지정 위치 생성·멱등성·실패 정리를 제공하고 실제 v3 요청이 연결된다. 성공/거부 이유와 부모 비용을 연결한 receipt가 있으며 인구·자원 보존과 Client 표시를 통과한다. 새끼 외형 없이 성체 rig로 검증하면 그 범위를 명시하고 성장 구현 완료로 기록하지 않는다.

## 11. Source·계약 근거

- [기존 Spawn](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureSpawning.cpp), [비공개 API·누적 상태](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.h)
- [인구·summary 보존 검사](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePopulation.cpp)
- [Native 개체 fragment](../../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedFragments.h), [지역·adoption](../../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp)
- [기존 출생 계획](../ProductionIntegration/02_BirthLifecycle/README.md), [RL 팀 출생 요청](../../RL_Policy/TEAM_REQUESTS_V3.md)
