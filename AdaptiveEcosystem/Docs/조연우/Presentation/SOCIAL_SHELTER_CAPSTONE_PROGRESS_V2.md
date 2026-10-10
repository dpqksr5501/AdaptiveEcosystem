# Social Runtime 캡스톤 중간 보고 V2

작성일: 2026-10-02 / 발표자: 조연우 / 표지 포함 9장

발표 범위는 `7f44d5e`의 이동 인계·예약 생명주기·진단 로그·HUD 개선이다. 기존 Social 기능은 담당 역할의 배경으로만 설명한다. 프로젝트에서 맡은 위치, 기존 공백, 기술 선택과 동작 결과를 중심으로 구성한다.

## 1. 개체의 은신 행동을 연결하는 Social Runtime

### 슬라이드 본문

AdaptiveEcosystem

Social Runtime

목적지 전달과 예약 관리의 연결 준비

조연우 / 캡스톤 디자인 중간 진행 보고

### 발표자 설명

“제 담당은 Social Runtime입니다. 개체가 위협에 반응해 은신처를 선택하고 자리를 예약하는 부분을 맡고 있습니다. 이번에는 그 다음 단계인 이동 요청 전달, 이동 결과에 따른 예약 유지·반환, 실행 상태 확인을 구현했습니다. 실제 이동 코드와의 연결은 다음 단계입니다.”

근거: [담당 경계와 이번 구현 범위][contract].

## 2. 프로젝트에서 내가 맡은 부분

### 슬라이드 본문

| 담당 계층 | 역할 |
|---|---|
| Policy | 개체별 행동 선호도 생성 |
| Social / 내 담당 | 경보에 맞춘 행동 보정, 은신처 목적지·예약 관리 |
| Movement | 실제 경로·위치·속도 갱신 |

이번 기여: Social의 목적지·예약을 이동 결과와 연결할 관리 규칙 구현

Social 요청을 기존 이동 코드가 소비하는 연결은 대기

### 발표자 설명

“전체 프로젝트에는 행동 선호도를 만드는 Policy와 실제 이동을 실행하는 Movement가 있습니다. 저는 그 사이에서 무리와 위험 상황을 반영하고, 은신처 목적지와 예약 소유권을 관리합니다. 행동 보정과 은신처 선택은 기존 기능이고, 이번에는 이동 계층에 전달할 요청과 결과 처리 규칙을 추가했습니다. Social에서 별도 이동 코드를 만들어 위치를 갱신하지 않고, 기존 이동 작성자 하나에 연결할 수 있도록 준비했습니다.”

근거: [현재 이동 작성자와 통합 대기 상태][current], [책임별 인계 데이터][contract].

## 3. 비어 있던 연결과 이번 보완

### 슬라이드 본문

| 기존 공백 | 이번 구현 | 만들어 내는 동작 |
|---|---|---|
| 목적지 기록 이후 이동 결과 미연결 | 요청·결과 계약 | 이동 채택·실패·도착 결과 처리 |
| 이동·점유에 따른 예약 유지 미연결 | 상태 전이와 예약 유효기간 갱신 | 유효한 진행·점유 때 예약 연장 |
| 죽음·삭제·이주 전용 반환 미연결 | 소유권·예약 자격 확인 | 사용할 수 없는 슬롯 반환 |

Social 처리 구현 완료 / 실제 이동 연결 후 JYU 전체 흐름 확인

### 발표자 설명

“기존에는 목적지와 슬롯을 예약하는 코드가 있었지만, 이동 담당자가 그 요청을 채택했는지 또는 도착했는지 알려주는 통로가 없었습니다. 예약 만료는 있었으나 유효한 이동과 점유에 따른 유지도 연결되지 않았습니다. 그래서 요청·결과 계약과 상태 관리, 소유권 정리를 추가했습니다. 이 기능들은 Social 코드와 자동화에서 확인했으며 실제 이동까지 이어지는 게임 동작은 연결 후 확인해야 합니다.”

근거: [main 당시 공백과 현재 구현 상태][current], [상태·유지·삭제 계약][contract].

## 4. 예약 결과를 안전하게 처리하는 기술

### 슬라이드 본문

| 기술 선택 | 막으려는 문제 | 구현 효과 |
|---|---|---|
| 예약 세대 번호 | 이전 예약의 결과가 새 예약을 변경 | 현재 예약과 일치하는 결과만 처리 |
| 결과 순번 / Sequence | 같은 보고를 여러 번 처리 | 새로운 순번의 결과만 한 번 소비 |
| Request / Feedback 분리 | 데이터 작성 책임이 섞임 | Social은 요청, 이동 계층은 결과 작성 |

보정된 행동과 실제 예약 슬롯 좌표를 전달

### 발표자 설명

“예를 들어 예약 15의 이동 실패가 늦게 도착했는데 이미 예약 16을 받았다면, 새 예약을 잘못 취소하면 안 됩니다. 예약을 새로 받을 때마다 번호를 바꾸고 현재 번호와 일치하는 결과만 처리합니다. 같은 결과의 반복 처리도 순번으로 차단합니다. 요청과 결과 데이터의 작성자를 분리하고, 이동 계층에는 Social 보정이 끝난 행동과 실제 예약 슬롯 좌표를 제공합니다. 이때 행동을 다시 보정해 중복 적용하지 않도록 계약에 명시했습니다.”

근거: [인계 Fragment와 Report 함수][fragments], [예약 번호·Sequence 규칙][contract].

## 5. 상태와 유효기간으로 예약 유지

### 슬라이드 본문

| 상태 | 인정 조건 |
|---|---|
| 예약 / Reserved | 슬롯 소유권 확보 |
| 이동 / Moving | 새 이동 보고 수신 |
| 점유 / Occupied | 도착 보고와 실제 거리 확인 |

기본 12초 예약 / 유효한 이동·점유 보고에 따라 갱신

도착 60cm·유지 120cm: 작은 위치 흔들림에 따른 반복 해제 완화

### 사진 제안

예약 슬롯과 `Slots: 2/2`가 보이는 화면. 슬롯 예약을 실제 점유로 설명하지 않는다.

### 발표자 설명

“예약만으로 이동이나 점유를 인정하면 실제 위치와 예약 상태가 달라질 수 있습니다. 새 이동 보고를 받아 이동 상태를 인정하고, 도착 보고가 들어와도 실제 거리를 확인합니다. 기본 예약 유효기간은 12초이며 유효한 이동·점유 보고가 이어질 때 연장합니다. 처음 도착할 때는 60cm, 유지할 때는 120cm를 허용해서 작은 위치 흔들림 때문에 반복 해제되는 것을 줄였습니다. 이동·점유 전이는 테스트가 위치와 결과를 모사해 검증했습니다.”

근거: [상태 전이·유효기간·거리 규칙][contract], [기본 설정][settings].

## 6. 멈추거나 사라진 개체의 슬롯 반환

### 슬라이드 본문

| 확인 근거 | 반환 규칙과 결과 |
|---|---|
| 이동·점유 보고 중단 | 2초 이상 새 보고가 없으면 반환 |
| 실제 거리 진행 정체 | 이동 중 8초간 진행이 없으면 반환 |
| 실패·은신 요구 종료·이주 | 유지 조건을 잃은 슬롯 반환 |
| 죽음·개체 삭제 | 남은 소유권을 정리해 예약 누수 방지 |

마지막 개체가 삭제돼도 남은 예약 정리 실행

### 발표자 설명

“이동 중이라는 보고만 계속 보내면서 실제로는 멈춰 있을 수도 있습니다. 그래서 새 보고가 들어오는지와 목적지까지의 거리가 실제로 줄어드는지를 함께 봅니다. 보고가 끊기거나 진행이 정체되면 슬롯을 반환합니다. 죽음·삭제·이주에도 예약이 남지 않도록 소유권을 확인하며, 마지막 개체가 사라져도 정리 처리가 계속 실행되게 했습니다.”

진행은 직선 거리 기반이라 긴 우회 경로의 타임아웃은 이동 연결 때 조정해야 한다. 현재 비교 정렬도 정확한 점수와 StableAgentId로 중재해 같은 슬롯의 승자를 결정한다. Calm 이름만으로 은신 요구 종료를 판정하지 않는다.

근거: [Lifecycle 구현][lifecycle], [소유권 및 정렬 계약][contract], [생명주기 테스트][tests].

## 7. 논리 상태와 화면 표시의 혼동 해소

### 슬라이드 본문

예약 정보가 경보 표시를 가리던 문제

경보·예약 정보를 두 줄로 표시

개체·예약 번호와 반환 이유를 로그에 기록

진단 명령: `eco.Shelter.Log 1 / 2`

HUD 구현·빌드 완료 / 실제 화면 추가 확인 필요

### 사진 제안

개체 머리 위 두 줄 HUD 화면. 실제 사진 전에는 표시를 실증했다고 설명하지 않는다.

### 발표자 설명

“예약한 개체가 빨강으로 변하지 않는다는 보고가 있었는데, 로그에서는 실제 경보 강도가 Panic 기준을 넘고 있었습니다. 기존 화면이 예약 점수를 표시할 때 경보 글자를 건너뛰는 문제여서 두 줄로 분리했습니다. 로그에는 어떤 개체의 어떤 예약이 왜 반환됐는지를 남깁니다. 그래서 판단 자체의 문제와 표시만의 문제를 구분할 수 있습니다.”

슬롯의 주황색은 예약 상태, 은신처 중심의 빨강은 슬롯 만석이다. 개체 Alert/Panic 색상과 구분한다. Safe/Danger 표시도 종합 점수 분류이며 실제 도착 위치의 안전성 확정이 아니다.

근거: [HUD 색상 및 사용자 로그 분석][contract], [HUD 코드][harness], [진단 로그][diagnostics].

## 8. 실행에서 확인한 결과

### 슬라이드 본문

- JYU: 100개체, 은신처 3곳, 동시 예약 최대 6슬롯
- 예약 만료·재예약과 개별 은신 요구 종료 반환 확인
- 예약 중인 개체의 경보 반응도 확인
- Social 자동화 9/9 통과: 기존 Threat 4 + 이번 Lifecycle 5

JYU는 예약 동작 확인 / 실제 이동·점유 연결 대기

### 사진 제안

여러 개체와 은신처가 보이는 JYU 전체 실행 화면.

### 발표자 설명

“사용자 JYU 로그에서 예약 만료와 새 예약 발급, 개별 은신 요구 종료에 따른 반환을 확인했습니다. 개체 100마리에 은신처 3곳을 놓은 시험에서 최대 6슬롯이 동시에 예약됐습니다. 예약 중인 개체도 Panic 기준 이상의 경보를 받는 기록을 확인했습니다. 자동화에서는 오래된 결과 차단, 상태 전이, 예약 유지, 개체 삭제와 경쟁 처리를 확인했습니다.”

JYU의 Moving/Occupied/FreshFeedback은 0이며 실제 이동 소비자가 아직 없다. 자동화의 이동·도착 모사는 실제 게임 이동 실증과 구분한다. 직접 UBT 빌드도 성공했다. 위협 종료 후 전체 예약 0, 사망·이주 실제 실행, Client는 추가 검증 대상이다.

근거: [사용자 JYU 로그 기록][contract], [자동화 결과][report], [이번 테스트][tests].

## 9. 이번 기여와 다음 연결

### 슬라이드 본문

| 이번에 마련한 것 | 연결 후 확인할 동작 |
|---|---|
| 유효한 행동·슬롯 목적지 Request | 기존 이동 코드가 실제 이동 실행 |
| 결과 기반 예약 유지·반환 | 도착·실패·요구 종료에 맞는 상태 변경 |
| 예약 번호·이유 로그와 HUD | 실제 이동과 예약 상태가 일치하는지 확인 |

다음 단계: 이동 담당자와 연결하고 JYU 전체 흐름 검증

### 발표자 설명

“이번 기여는 Social의 목적지와 예약을 실제 이동 결과에 맞춰 관리할 수 있는 계약과 코드를 마련한 것입니다. 다음에는 이동 담당자가 기존 이동 작성자 하나에 요청 소비와 결과 반환을 연결합니다. 그러면 제가 구현한 상태·유지·반환 처리와 함께 실제 개체가 이동하고 도착하는 전체 흐름을 검증할 수 있습니다. 실제 개체 구성과 Server/Client도 확인할 예정입니다.”

근거: [인계 및 다음 담당자 작업][contract], [전체 통합 대기 상태][current].

[contract]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Docs/조연우/SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md
[current]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Docs/조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md
[fragments]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/EcoSocialFragments.h
[settings]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/EcoSocialMovementTypes.h
[lifecycle]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/Shelter/EcoShelterLifecycleProcessor.cpp
[tests]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/Tests/EcoShelterLifecycleTests.cpp
[harness]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/Debug/EcoShelterTestHarnessActor.cpp
[diagnostics]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/Shelter/EcoShelterDiagnostics.cpp
[report]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Saved/Automation/SocialShelterDiagnostics/index.json
