# 캡스톤 중간 진행 보고: Social Runtime 발표 초안

- 작성일: 2026-10-02
- 발표자: 조연우
- 대상: 게임 캡스톤 디자인 수업 교수님 및 조원
- 분량: 표지 포함 9장. 발표 시간은 미정이며 조별 모임 30분과 구분한다.
- 범위: 커밋 `7f44d5e`의 Social 이동 인계, 은신처 예약 생명주기, 진단 로그, HUD 개선.
- 기존 무리·경보·차폐 시스템은 이번 작업을 이해하기 위한 배경으로만 다룬다.

---

## 1. 은신처 예약 관리와 이동 연결 준비

### 슬라이드 본문

**AdaptiveEcosystem / Social Runtime**

은신처 예약의 유지·반환과 이동 결과 처리

조연우 / 캡스톤 디자인 중간 진행 보고

### 그림·실행 화면 제안

JYU 은신처 주변을 보여주는 실행 화면 한 장을 크게 배치한다. 제목 주변에는 여러 기능이나 기술 이름을 추가하지 않는다.

### 발표자 설명

“이번에는 개체가 은신처를 예약한 다음의 처리를 구현했습니다. 예약을 언제 유지하고 반환할지 정하고, 실제 이동 코드와 목적지·결과를 주고받을 수 있도록 준비했습니다. 실행 상태를 확인할 로그와 화면 표시도 개선했습니다.”

발표 근거: [이번 작업 범위 및 커밋 정리][contract].

---

## 2. 예약 이후에 필요한 처리

### 슬라이드 본문

- 은신처 선택 이후에는 이동·도착 결과를 확인해야 함
- 이동하지 않는 개체가 자리를 계속 예약하는 문제 방지
- 죽음·삭제·이주 이후에는 다른 개체가 슬롯을 사용하도록 반환
- 경보와 예약 상태를 함께 확인할 수 있는 표시 필요

### 그림·실행 화면 제안

은신처의 예약 슬롯을 보여주는 JYU 화면을 사용한다. 슬롯은 “개체 한 마리가 예약하는 자리”라는 짧은 설명을 붙인다.

### 발표자 설명

“기존에는 은신처를 선택하고 슬롯을 예약하는 기능이 있었습니다. 여기에 실제 이동 결과와 연결되는 관리가 필요했습니다. 움직이지 않거나 사라진 개체가 예약을 유지하면 다른 개체가 그 자리를 사용하지 못하므로, 반환 조건까지 함께 설계했습니다.”

발표 근거: [예약 상태 및 삭제 처리][contract].

---

## 3. 사용 기술과 담당 구조

### 슬라이드 본문

| 기술·구조 | 이번 작업에서의 역할 |
|---|---|
| Unreal Engine 5.8 / C++ | Social 예약·인계 로직 구현 |
| MassEntity Fragment | 개체별 이동 요청·결과·예약 상태 저장 |
| Mass Processor | 예약 이후 상태 확인과 정리 실행 |
| World Subsystem | 은신처 슬롯과 예약 소유권 관리 |

**Social은 목적지와 예약을 관리하고, 이동 계층은 실제 위치·속도를 갱신**

### 그림·실행 화면 제안

Social과 Movement의 책임을 나란히 보여주는 간단한 구성도. Movement 영역에는 “연결 대기”를 명시한다. 전체 PPO·생태계 구조도는 생략한다.

### 발표자 설명

“MassEntity에서는 개체별 데이터를 Fragment에 저장하고 Processor가 처리합니다. 이번에는 요청·결과 데이터와 예약 관리 Processor를 추가해 기존 Mass 구조 안에서 전달하도록 했습니다. 실제 이동은 기존 이동 담당 코드 하나가 실행하도록 책임을 구분했습니다.”

발표 근거: [Fragment 정의][fragments], [Lifecycle Processor][lifecycle], [예약 Subsystem][subsystem].

---

## 4. 이동 요청과 결과 전달

### 슬라이드 본문

| 전달 방향 | 전달하는 내용 |
|---|---|
| Social에서 이동 계층으로 | 보정된 행동, 예약 슬롯의 목적지, 예약 번호·만료 시각 |
| 이동 계층에서 Social로 | 이동 중, 도착, 실패, 다른 행동 선택 |

- 현재 예약 번호와 일치하는 새로운 결과만 처리
- 이전 예약의 늦은 결과나 같은 결과의 중복 처리 방지

**요청·결과 계약 구현 완료 / 실제 이동 코드 연결 대기**

### 그림·실행 화면 제안

Request와 Feedback을 주고받는 두 영역을 보여준다. 코드 전체 대신 “예약 번호 15의 결과는 예약 번호 16을 바꾸지 못함”이라는 설명 예시를 사용한다.

### 발표자 설명

“이동 요청에는 어디로 갈지와 어떤 예약인지가 들어 있습니다. 이동 코드는 진행 상황을 결과로 돌려줍니다. 예약이 바뀐 뒤 오래된 도착 결과가 들어오면 새 예약에 잘못 적용될 수 있어서, 예약 번호와 결과 순서를 확인하도록 했습니다. 이 데이터를 처리하는 Social 코드는 구현했고, 실제 이동 담당 코드가 읽고 결과를 쓰는 부분은 아직 연결해야 합니다.”

발표 근거: [Request·Feedback 계약][contract], [인계 Fragment][fragments].

---

## 5. 예약·이동·점유 상태 관리

### 슬라이드 본문

| 상태 | 상태를 인정하는 조건 |
|---|---|
| 예약 / Reserved | 슬롯 소유권 확보 |
| 이동 / Moving | 현재 예약에 대한 새 이동 보고 수신 |
| 점유 / Occupied | 도착 보고 수신 및 실제 슬롯 거리 확인 |

- 최초 예약은 기본 12초 동안 유효
- 유효한 이동·점유 보고가 이어지면 예약 기간 연장
- 도착 허용 거리 60cm, 점유 유지 거리 120cm

### 그림·실행 화면 제안

예약·이동·점유 세 상태를 순서대로 보여준다. 초기 예약 대기와 이동 결과를 받은 상태의 차이를 짧게 표시한다.

### 발표자 설명

“예약했다고 바로 도착한 것으로 처리하지 않습니다. 이동 중이라는 보고를 받아야 이동 상태가 되고, 도착 보고와 실제 위치를 함께 확인해 점유를 인정합니다. 도착 허용 거리와 유지 거리를 다르게 설정해서 작은 위치 흔들림으로 점유가 반복 해제되는 것도 줄였습니다. 이동·도착 전이는 자동화 테스트에서 검증했으며 JYU 실제 이동 검증은 연결 이후에 진행합니다.”

발표 근거: [상태 전이·유지 규칙][contract], [기본 설정][settings].

---

## 6. 사용할 수 없는 예약 반환

### 슬라이드 본문

- 이동 실패·다른 행동 선택·은신 요구 종료 시 반환
- 이동 보고가 2초 끊기거나 진행이 8초 정체하면 반환
- 죽음·삭제·이주 시 슬롯 소유권 정리
- 개체가 모두 삭제돼도 남은 예약 정리 계속 실행

### 그림·실행 화면 제안

정상 예약과 반환 대상 예약을 비교하는 설명 그림. “죽은 개체의 예약도 반환”을 한 가지 대표 사례로 보여준다.

### 발표자 설명

“이동 결과가 실패했거나 다른 행동을 선택하면 슬롯을 반환합니다. 이동 중이라는 보고만 계속 보내면서 실제로 움직이지 않는 상황도 확인합니다. 죽음과 이주는 다른 시스템의 상태를 읽어 예약을 정리하고, 그 상태 자체를 Social에서 변경하지 않습니다. 마지막 개체가 삭제됐을 때에도 정리 코드가 실행되도록 했습니다.”

“은신 요구 종료”는 Panic 여부와 은신 행동 값을 함께 판단한다. Calm 복귀만으로 모든 예약을 반환한다고 설명하지 않는다. 진행 정체 기준은 슬롯까지의 직선 거리이므로 긴 우회 경로에 대한 조정은 이동 연결 시 검토한다.

발표 근거: [Lifecycle Processor][lifecycle], [예약 자격 검사][eligibility], [삭제·이주·정체 테스트][tests].

---

## 7. 진단 로그와 HUD 개선

### 슬라이드 본문

- `eco.Shelter.Log 1`: 예약·반환 이벤트와 5초 간격 요약
- `eco.Shelter.Log 2`: 탐색 결과·슬롯 경쟁 상세 기록
- HUD에 경보 상태와 예약 정보를 두 줄로 표시

**표시 형식 예시**

```text
A1021 [Panic] 0.72
S#0 [Reserved/Safe] 0.95
```

**두 줄 HUD: 구현·빌드 완료 / 실행 화면 추가 확인 필요**

### 그림·실행 화면 제안

실제 로그의 Reserve 또는 StateRelease 한 줄과 Summary 한 줄을 필요한 필드만 남겨 보여준다. HUD 예시는 실제 캡처가 생기기 전까지 텍스트로 제시하고 “표시 형식 예시”를 유지한다.

### 발표자 설명

“화면 색상만 보면 예약 여부와 경보 상태를 혼동할 수 있었습니다. 예약된 개체는 기존 표시에서 경보 글자가 가려질 수 있어 두 정보를 나눠 표시하도록 수정했습니다. 또 개체 번호, 예약 번호, 상태와 반환 이유를 로그로 남겨 어떤 단계에서 문제가 발생했는지 확인할 수 있게 했습니다.”

“개체의 Panic은 빨강으로 표시하지만, 은신처 중심의 빨강은 슬롯 만석을 뜻합니다. 슬롯의 주황색도 예약 상태입니다. 같은 색이 다른 대상을 가리키므로 라벨과 로그를 함께 봅니다.”

Safe/Danger는 기존 종합 점수 기준 표시다. Safe만으로 실제 도착 위치의 안전성을 확정하지 않는다.

발표 근거: [로그 구현][diagnostics], [HUD·슬롯 표시][harness], [색상 혼동 수정 기록][contract].

---

## 8. JYU 실행 결과와 검증 범위

### 슬라이드 본문

| 확인 방법 | 확인한 내용 |
|---|---|
| JYU 화면·사용자 로그 | 100개체, 은신처 3곳, 동시 예약 최대 6슬롯 |
| JYU 사용자 로그 | 예약 만료·재예약, 개별 은신 요구 종료 반환, 경보 반응 |
| 직접 UBT 빌드 | 컴파일·링크 성공 |
| Social 자동화 | 9/9 통과: 기존 Threat 4개 + 이번 Lifecycle 5개 |

**JYU 실제 이동·도착·점유는 미검증이며 이동 연결 대기**

### 그림·실행 화면 제안

최신 JYU의 `Slots: 2/2` 화면 한 장을 사용한다. 예약 슬롯 두 곳에 “예약 자리”라는 설명을 붙이고, 점유나 이동 완료라는 표현은 사용하지 않는다.

### 발표자 설명

“JYU에서 여러 개체가 은신처 슬롯을 예약하고, 예약이 만료되거나 은신 요구가 끝나면 반환하는 동작을 확인했습니다. 예약 중인 개체에도 높은 경보 강도가 기록돼 경보와 예약이 함께 동작하는 점을 확인했습니다. 자동화 테스트는 기존 위협 테스트 네 개와 이번 생명주기 테스트 다섯 개가 모두 통과했습니다.”

“JYU에는 실제 이동 결과를 보고하는 소비자가 아직 없어서 Moving, Occupied, FreshFeedback 값이 모두 0입니다. 자동화에서는 위치와 결과를 모사해 상태 전이 코드를 확인했습니다. 실제 게임에서 걸어가서 도착한 결과와는 구분하고 있습니다.”

기존 차폐 시스템의 1.0/노출 0.1 표시도 사용자 화면에서 확인했다. 이번 변경의 신규 차폐 기능이나 실제 슬롯 안전성 검증으로 소개하지 않는다. 위협 종료 후 전체 예약이 0이 되는 장면과 사망·이주·Client의 실제 실행은 추가 확인 대상이다.

발표 근거: [사용자 JYU 실행 기록][contract], [자동화 보고서][report], [Lifecycle 테스트 코드][tests].

---

## 9. 남은 연결과 다음 검증

### 슬라이드 본문

- **구현 완료:** 이동 요청·결과 계약, 예약 상태·유지·반환, 로그, HUD 개선
- **다음 연결:** 기존 이동 코드가 Request를 읽고 Feedback을 반환
- **다음 검증:** JYU 실제 이동·도착·점유와 실패·종료 시 반환
- **통합 확인:** 실제 개체 구성 및 Server/Client 실행

### 그림·실행 화면 제안

“완료한 Social 기능”과 “연결할 이동 계층”의 두 열 비교표. 전체 프로젝트 완료율이나 근거 없는 진행 퍼센트는 넣지 않는다.

### 발표자 설명

“이번 작업으로 Social이 이동 계층에 제공할 데이터와 예약 관리 규칙을 마련했습니다. 다음에는 이동 담당자가 기존 이동 경로 하나에 요청 소비와 결과 반환을 연결해야 합니다. 이후 JYU에서 개체가 실제로 이동하고 도착해 자리를 유지하는지, 실패하거나 요구가 끝나면 반환하는지 확인하겠습니다. 실제 개체 구성과 네트워크 실행도 검증할 예정입니다.”

발표 근거: [다음 담당자 인계][contract], [현재 구현·통합 대기 상태][current].

---

## 참고 자료

아래 자료는 각 슬라이드 발표자 설명의 근거이며 별도 슬라이드에 해당하지 않는다.

- 기준 브랜치: `codex/social-shelter-handoff`
- 기준 커밋: `7f44d5e` — `feat(social): 은신처 이동 인계와 예약 생명주기 구현`
- 상태·기본 설정 수치는 현재 구현의 기본값이며 프로젝트 전체의 최종 튜닝 결과가 아니다.
- 실행 기록은 2026-09-30~2026-10-01의 기존 기록을 사용한다.

[contract]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Docs/조연우/SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md
[current]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Docs/조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md
[fragments]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/EcoSocialFragments.h
[settings]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/EcoSocialMovementTypes.h
[lifecycle]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/Shelter/EcoShelterLifecycleProcessor.cpp
[subsystem]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/Shelter/EcoShelterSubsystem.cpp
[eligibility]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/Shelter/EcoShelterEligibility.h
[diagnostics]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/Shelter/EcoShelterDiagnostics.cpp
[harness]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/Debug/EcoShelterTestHarnessActor.cpp
[tests]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/Tests/EcoShelterLifecycleTests.cpp
[report]: C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Saved/Automation/SocialShelterDiagnostics/index.json
