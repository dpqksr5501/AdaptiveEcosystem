# M4.2 — 연결별 Replication LOD 갱신 간격

구현일: 2026-10-06 / UE 5.8. 일반 이동 표본의 간격 제한, 우선 상태 변경, High 승격 검사와 수동 계측을 구현했다. 실제 PIE의 간격·여러 Client·Remove 관찰 결과는 아직 기록하지 않았다. 자동화 테스트는 작성·실행하지 않았다.

## 관련 파일

| 파일 | 역할 |
| --- | --- |
| [EcoMassReplicator.cpp](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp) | 현재 연결의 LastUpdateTime 비교·갱신, 중요 상태 우회, High 승격, 표본 로그 |
| [EcoMassReplicationTypes.h](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicationTypes.h) | 전송 payload 및 Bubble entry의 서버 전용 이전 LOD/마지막 검사 시각 |
| [EcoMassClientBubble.h](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.h), [cpp](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.cpp) | 연결별 표본/검사/제거 계측과 reset |
| [EcoMassNetworkDiagnostics.cpp](../../../Source/AdaptiveEcosystem/Debug/EcoMassNetworkDiagnostics.cpp) | 수동 dump, SetVitals, Teleport |
| [EcoMassNetworkTrait.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassNetworkTrait.cpp), [설정](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassNetworkSettings.h) | 기존 Params 검증·실험 프리셋·역할별 템플릿 |
| [M4.1 계약](M4_1_DATA_CONTRACT.md) | 시간·ID·양자화·수신 버퍼 계약 |
| [수동 테스트](M4_EDITOR_TEST.md), [검증 기록](M4_VALIDATION_REPORT.md) | 에디터 실행 절차와 실제 확인 범위 |

## 갱신 규칙

서버가 현재 Client의 LOD를 계산한 다음 `RealTime - AgentData.LastUpdateTime >= Params.UpdateInterval[LOD]`일 때 일반 위치/yaw를 검사한다. 시간은 서버 World의 `GetRealTimeSeconds()`이며 생태 WorldClock, time dilation, 처리 Step 수로 간격을 계산하지 않는다. 간격에 도달한 첫 replication pass에서 처리하므로 목표 간격에 서버 프레임 단위의 오차가 생길 수 있다.

검사 시점에는 위치가 정지했더라도 LastUpdateTime을 전진시킨다. 이 값을 엔진 `SyncFromMass`가 현재 Client의 `AgentsData`에 저장하고 다음 pass의 `SyncToMass`가 복원한다. A 연결의 마지막 검사 시각이 B 연결에 적용되지 않는다. LastUpdateTime의 의미는 **마지막 Transform 검사 시각**이고 마지막 실제 dirty 표본 시각은 payload의 ServerSampleRealTimeSeconds다.

위치/yaw tolerance는 엔진 기준을 유지한다. 값이 그대로면 Sequence·SampleTime·FastArray dirty를 변경하지 않는다. 우선 상태 변경 시에는 현재 위치도 함께 검사하고 LastUpdateTime을 전진시키므로 다음 일반 위치 검사는 그 시점부터 간격을 기다린다.

| 사건 | 처리 |
| --- | --- |
| 신규 Add / Off 이후 재진입 | 전체 현재 snapshot 즉시 Add, Sequence=1; 이전 entry의 시계/LOD를 재사용하지 않음 |
| 일반 이동 | 현재 LOD 간격 이후 tolerance 검사; 변한 경우만 Sequence와 표본 시각 갱신 |
| Region/identity, 양자화 HP/Energy, Alive→Dead | 매 callback 검사, 변경 시 일반 간격 우회 |
| reset revision 변경 | 간격과 tolerance 모두 우회하여 현재 Transform 전체 전송 |
| Medium/Low→High | 첫 승격 callback에서 즉시 검사; 값이 같으면 dirty 표본을 만들지 않음 |
| High 이외의 LOD 전환 | 새 LOD 간격을 마지막 검사 시각에 적용 |
| Off / pending destruction | 기존 엔진 helper의 Remove 경로, 간격 gate 밖에서 처리 |
| 서버 real time 역행 | 즉시 한 번 검사하고 현재 시각으로 시계 복구 |

엔진 helper는 Modify 이전에 AgentData.LOD를 새 등급으로 덮어쓴다. 승격 검사용 이전 등급은 해당 연결의 FastArray item의 비반영(non-UPROPERTY) 필드에 보관한다. 별도 전역 ID map이나 per-entity 단일 LOD로 Client 상태를 혼합하지 않는다. 제거·재진입·연결 해제 때 item 수명과 함께 정리된다. 이 필드와 counters는 Client로 전송하지 않는다.

## 수동 계측

`eco.M4.Dump`는 Bubble별 누적 Adds/Removes와 LOD별 현재 Entries, Gated, Checks, Dirty, Priority, HighPromotions를 출력한다. LOD 숫자는 High=0, Medium=1, Low=2, Off=3이다. Checks는 Modify의 Transform 검사 수, Dirty는 Modify에서 생성한 표본 수이며 Add는 별도 집계한다. HighPromotions는 중요한 상태 변경과 동시에 발생해도 집계한다. 수치는 Bubble 생성/reset 이후 누적이므로 측정 시작·종료 dump 차이를 사용한다.

`eco.M4.TraceSamples 1`은 서버 Add/dirty/Remove를, `2`는 값이 같은 검사까지 로그로 출력한다. 로그의 World/Bubble/ID를 함께 묶어 Sequence, CheckTime, CheckDelta, SampleTime, Reason을 읽는다. Remove 로그는 제거 사건이며 새 Sequence를 생성하지 않는다. 검사 간격은 CheckDelta로, 실제 표본 간격은 같은 entry의 SampleTime 차이로 확인한다. 로그는 같은 프로세스의 모든 PIE World에 적용되며 성능 측정 전에는 `0`으로 끈다.

**중요:** Energy 대사·식사·HP 변화가 양자화 경계를 넘으면 Visual 우선 표본이 Low 간격보다 자주 생성될 수 있다. 이것은 이번 계약의 우선 전달 동작이다. 순수 이동 간격을 측정할 때는 대사/식사를 잠시 멈추고 Reason=Interval 구간을 사용한다. Packet 전송 빈도는 Bubble Actor의 NetUpdateFrequency, 대역폭과 FastArray batching의 영향도 받으므로 서버 dirty 표본 간격과 같다고 가정하지 않는다.

M4.4 보간, M4.5 표현 전환, M4.6 연결 전체 예산/승격 폭주 제어와 M4.8 플레이어 상호작용·사망 전달 보장은 후속 단계다. 기존 기아/외부 HP=0 사망 경로의 지속 Dead 상태를 우선 전달하지만, Dead 잔류와 실제 packet 전달을 ACK로 보장하는 정책은 추가하지 않았다.
