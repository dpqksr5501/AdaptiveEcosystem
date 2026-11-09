# T02. 행동·감각 표현 데이터 복제

상태: 개발 명세 초안 / 기준: `8836558` / 책임 제안: 원준 transport, 조연우 표현, 권신혁 v3 상태 의미.

선행: [T01](01_RUNTIME_CONFIGURATION_AND_AUTHORITY.md). 확인 항목: [F06·F15·F17](99_DECISIONS_AND_CONFIRMATIONS.md). 공통 규칙은 [전체 안내](README.md).

## 1. 목적과 필요성

위치가 같아도 행동·생사·감각 방향이 달라질 수 있다. 정지한 사슴의 경계·숨기·사망을 전달하면서 이동 보간의 시간축을 보존해야 한다. 새 상태를 Client가 추론해 만들지 않고 서버의 확정 표현을 소비하게 한다.

## 2. 현재 구현과 재사용

FReplicatedEcoMassAgent는 기존 PositionYaw/ID/vitals/life/revision에 Velocity·VisualFlags·Activity·FocusYaw를 전달한다. Client Add/Modify가 이를 FEcoCreaturePresentationFragment에 복사하고 SyncVisuals가 수동 Actor에 넘긴다.

Activity enum은 기존 값 뒤에 Freeze/Sleep/Stalk/Pounce/Exhaust가 추가됐다. 늑대 9개 표현 상태의 변환표와 범위 검사도 있다. 새 transport를 만드는 업무가 아니라 전 구간의 의미와 회귀를 고정하는 업무다.

현재 LifeState는 FEcoAliveTag 유무로, Creature alive flag는 HP>0으로 생성된다. 두 값의 원천과 갱신 경계가 다르므로 사망 후보→공통 확정→태그 정리 사이에 불일치가 전달되는지 확인한다. Client가 한 값을 추측해서 맞추는 방식으로 감추지 않는다.

## 3. 필드 계약

| 필드 | 서버 입력·의미 | Client 처리 |
|---|---|---|
| StableAgentId/SpeciesId/RegionId | 장기 ID·현재 소속 | binding·표현 선택, 논리 역기입 금지 |
| PositionYaw/Velocity | 단일 writer의 실제 위치·속도 | 기존 표본 보간·방향 표현 |
| LifeState·alive flag | 공통 생명주기의 확정 상태 | HP byte만으로 사망 추정 금지 |
| Health/Energy 계열 | 정규화 후 QuantizeUnit | 기존 중복 필드는 호환성 유지·의미 일치 검사 |
| Activity | 실행된 행동의 표현 코드 | enum 재정렬 금지, 미지원 값은 안전한 Hold |
| 감각 출처 | 현재 flags bit 4~5의 Source | Sight/Hearing/Memory 표현, 새 관측 발행 금지 |
| FocusYaw | int16 각도, 현행 약 182.0389배 | 역변환·회전 경계 검사, 논리 표적 좌표 아님 |

PPO request와 실행 Activity를 동일시하지 않는다. Flee는 세계 override의 결과일 수 있다. 약함·경계 섭식·포만 휴식처럼 현재 DTO로 명시되지 않은 상태는 F06 결정 전 기존 상태에 임의로 끼워 넣지 않는다.

## 4. revision·수신 계약

1. 실제 Transform/reset/identity 변경일 때 이동 SampleSequence와 sample real time을 전진한다.
2. 행동·vitals·감각 payload 변경은 VisualRevision으로 나타낸다. 이동이 없으면 이동 표본 시간을 새로 찍지 않는다.
3. 동일 identity의 과거 이동 serial은 거부한다. 이동 serial이 같아도 새 VisualRevision은 수용한다.
4. 첫 Add·reset·새 binding은 snap한다. presentation-only 변경은 두 이동 표본의 위치·시각을 유지한다.
5. Actor의 로컬 Sequence는 렌더 호출 순서이며 네트워크 stale 판정에 쓰지 않는다.
6. serial wrap 비교는 기존 uint32 차이 계약을 유지하고, 한 비교 창에서 2^31 이상 순서를 뛰지 않는 전제를 기록한다.
7. epoch·맵 이동은 T01/T04에서 버퍼를 재생성한다. 현행 agent payload에 없는 epoch 필드를 있다고 가정하지 않는다.

## 5. 전송 우선순위

| 변화 | 현행 처리·명세 |
|---|---|
| life/vitals/flags/Activity/reset/region | 일반 movement gate보다 먼저 중요 변화로 검사 |
| Velocity 단독 | 연결 interval 적용 |
| FocusYaw 단독 | 현재 중요 변화 목록에 없고 interval 적용 |
| 무변화 | timestamp만 바꾸어 dirty하지 않음 |
| 새 Add | 최신 전체 표현과 binding 초기화 |

FocusYaw를 즉시 보낼지는 F06에서 허용 지연·packet 비용을 보고 정한다. 프레임마다 각도 변화가 priority를 우회하도록 만들지 않는다. 기존 중복 vitals 제거도 별도 wire 변경으로 측정 후 진행한다.

## 6. 개발 작업과 실패 처리

- 서버 Native/V1/StateTree 상태 → presentation → replicator → Client fragment → Actor → AnimBP 변환표를 작성한다.
- enum 끝값과 변환표 개수를 함께 검증한다. 추가 상태는 append하고, 서버/Client 빌드가 다르면 T11 호환성 정책으로 접속을 처리한다.
- 시선만 변경·행동만 변경·사망만 변경되는 정지 fixture를 개발 검증용으로 준비한다.
- 잘못된 enum·NaN은 경계에서 진단하고 안전 표현을 선택한다. 자원·생사를 Client fallback으로 변경하지 않는다.
- 중요한 전환이 현재 상태 복제로 충분한지 F15에서 정한다. 현재 FastArray는 모든 중간 행동 사건의 재생을 보장하지 않는다.
- 경보 오디오 dedup·pool reset은 T04와 함께 확인한다. 프레임마다 multicast나 별도 동물 movement replication을 추가하지 않는다.

## 7. 검증 시나리오

| ID | 자극 | 기대 결과 |
|---|---|---|
| PR01 | 정지 상태에서 Graze→Flee→Hide | 새 Activity 수신, 이동 timeline 유지 |
| PR02 | 위치 고정·FocusYaw만 회전 | interval 내 전달, ±180도 부근 정상 |
| PR03 | HP/Energy가 양자화 경계를 오감 | 양쪽 vitals 필드 일치, 불필요 dirty 계측 |
| PR04 | 정지한 개체 사망 | Alive/life/애니메이션 일치 |
| PR05 | 늑대 Settle/Waking 포함 전체 상태 | 표 범위 초과 없음, 의도한 표현 |
| PR06 | 같은 SampleSequence의 새/과거 VisualRevision | 새 것 수용·과거 것 거부 |
| PR07 | relevance 재진입 | 과거 cue·행동·경보를 새 이벤트로 재생하지 않음 |
| PR08 | 권한 없는 Client | 정책·감각 논리 실행 및 역기입 0 |

## 8. 완료 조건·관측값

필드 의미·유효범위·갱신 우선순위 표가 코드와 일치한다. MovementUpdates/PresentationUpdates/RejectedUpdates 및 서버 dirty 원인을 기록하고, 중요한 전환별 전달 지연을 T11의 확정 목표와 비교한다. T03에 실제 상태 시나리오, T04에 버퍼·binding 계약을 넘긴다.

## 9. Source·계약 근거

- [표현 enum](../../../Source/AdaptiveEcosystem/Core/EcoActivityTypes.h), [공통 snapshot](../../../Source/AdaptiveEcosystem/Core/EcoRepresentationTypes.h)
- [wire payload](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicationTypes.h), [전송 gate](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp)
- [Client Add/Modify](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.cpp), [수신 버퍼](../../../Source/AdaptiveEcosystem/Mass/EcoMassPresentationFragments.h)
- [서버 표현 변환](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp), [Actor 소비](../../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureRepresentationActor.cpp)
