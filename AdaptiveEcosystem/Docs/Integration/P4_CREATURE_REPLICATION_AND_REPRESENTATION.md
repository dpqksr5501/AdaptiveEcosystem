# P4 — 실제 동물의 복제·보간·표현 예산

작성일: 2026-10-11 / UE 5.8 / 기준: `M4`, `6235742` / 상태: 통합 계획, 대규모 전송/표현 검증 없음.

[전체 순서](README.md) · 이전: [P3](P3_SPATIAL_AND_QUERY_OPTIMIZATION.md) · 다음: [P5](P5_PARALLEL_PROCESSING_AND_TIME_SCHEDULING.md)

## 1. 목표와 선행 조건

서버 전체 논리 개체 수와 각 Client의 Proxy/Actor 수를 분리한다. 기존 Mass Bubble 기반을 유지하면서 동물에도 연결별 relevance·갱신·수신 보간·표현 상한을 적용한다. P1 사건/ID 계약과 P2 계측이 선행 조건이다.

## 2. 현재 근거와 차이

| Source/계약 | 현재 상태 |
| --- | --- |
| [Creature Network Trait](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureNetworkTrait.cpp) | 기존 Network Trait와 Bubble을 사용, Client 논리 분리 |
| [Creature Spawner의 SyncVisuals](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.cpp) | Integrated Entity를 읽어 Actor 직접 생성/제거, Client는 VInterpTo 기반 위치 완화 |
| [Mass Replication Types](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicationTypes.h) | M4 Snapshot과 Creature presentation 전송 계약 확인 지점 |
| [M4.1 계약](../Roadmap/M4/M4_1_DATA_CONTRACT.md) | sequence/time/reset와 Client 수신 버퍼. Actor/Add 예산은 설정이며 집행 완료 아님 |
| [M4.2 구현](../Roadmap/M4/M4_2_REPLICATION_INTERVAL.md) | 연결별 일반 Transform 검사 gate·중요 상태 우선 처리. 실제 packet 간격은 별도 검증 |

현재 동물 표현은 모든 대상에 Actor를 직접 바인딩한다. Dedicated는 표현을 만들지 않지만 Listen Host/Standalone의 대상 전체 표현에도 별도 가시성/예산 검토가 필요하다. 현재 VInterpTo를 표본 시각 기반 M4 보간 완료로 기록하지 않는다.

## 3. 작업 A — 전송과 수신 계약 연결

1. M4 vitals/life/reset/sequence와 Creature velocity/eating/pursuit/visual flag의 소유·변환을 표로 정리한다. HP byte 추측으로 LifeState를 확정하지 않는다.
2. 기존 Replicator callback에서 현재 연결의 relevance/LOD와 update gate를 확인한다. entity 하나의 LOD 값을 모든 Client에 공유하지 않는다.
3. Add·Region commit·Dead·reset·Off Remove 등 우선 사건을 보존한다. Energy 양자화 변경으로 표본이 자주 발생하는 경우를 순수 이동과 분리 측정한다.
4. 수신 표본의 Previous/Current·sequence·reset·재진입 초기화를 동물 표시에도 연결한다. 렌더 시계와 생태 WorldClock을 섞지 않는다.
5. 첫 Add/reset은 snap하고 정상 표본은 정의된 timeline으로 보간한다. 실제 Client Transform과 Actor 표현의 writer를 구분해 중복 보간/적분을 방지한다.

## 4. 작업 B — 연결별 예산과 전환

- 여러 종/Template/Viewer를 합친 연결 전체 관련 개체·Actor·Add 예산을 집행한다. LOD별 max count를 연결 전체 예산이라고 간주하지 않는다.
- 공격/상호작용 대상과 가까운 위험 등 필수 개체의 우선순위, 동률 기준, 초과 시 처리 정책을 정의한다.
- 동시 진입 시 Add/Actor 생성 queue로 작업을 분산하고 신규·취소·삭제·재접속의 queue 수명을 정한다.
- 히스테리시스·최소 유지 등 전환 안정화 정책을 기록해 경계에서 spawn/destroy 반복을 줄인다.
- Actor 풀은 identity/bind/애니메이션·오디오·보간 상태를 완전히 reset한다. pooled 객체와 StableAgentId를 동일시하지 않는다.

## 5. 작업 C — 동물 표현과 애니메이션

가까운 개체는 정밀 Skeletal Actor, 중간은 애니메이션/표현 갱신 절감, 먼 개체는 검증된 간소 표현 또는 표시 없음으로 구성한다. ISM에 기존 Skeletal 애니메이션을 그대로 옮길 수 있다고 가정하지 않는다. VAT/vertex animation은 에셋 제작·호환성·동작 표현을 별도 검증할 선택지다.

Epic은 Mass Representation의 High/Low Actor·ISM·표현 없음과 Actor pooling을 설명한다. [MassGameplay 공식 근거](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-gameplay-in-unreal-engine)

현재 Skeletal Actor를 유지하는 경우 [Animation Budget Allocator](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-budget-allocator-in-unreal-engine)의 중요도 기반 애니메이션 예산 적용을 검토한다. 적용과 활성화·실측을 별도 작업으로 기록한다. Notify 축소가 서버 논리 소음을 줄이면 안 된다. 가까운 발소리·사망/행동 전환·재접속 reset의 회귀를 확인한다.

## 6. 완료·검증 기준

- A/B Client가 다른 위치에서 다른 관심 개체/주기를 받고 서버 논리는 한 번만 계산한다.
- 전체 Entity N이 늘어도 각 Client의 Proxy/Actor/Add가 정의한 예산을 만족한다. Host 표현도 제한한다.
- sequence 역전/중복, 지연·손실·저 FPS, teleport/reset, relevance 재진입에서 ghost·중복 bind·stale 보간이 없다.
- relevance Remove는 Population/사망을 바꾸지 않는다. 죽음·잔류·삭제의 전달 범위와 ACK 유무를 정직하게 기록한다.
- 서버 dirty 수와 packet bytes/간격, Client CPU·애니메이션·Actor 생성 spike를 각각 측정한다.
- 실제 팀 레벨과 다중 Client/재접속에서 감각·발소리·Shelter 상태가 회귀하지 않는다.

제안 담당: wonkii는 transport/예산/보간, 조연우는 수동적 동물 Actor·애니메이션·오디오 소비, avaroki는 스트리밍/가시성 시나리오. M4.4~6과 동물 경로의 공통 적용이며 별도 소리 RPC·Client PPO는 추가하지 않는다. C++/빌드 입력 변경 시 루트 UBT 규칙을 따른다.
