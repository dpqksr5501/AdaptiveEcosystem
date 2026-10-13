# Social 이동 인계와 Shelter 예약 생명주기

> **2026-10-08 통합 갱신:** `/Game/Map/LV_Ecosystem_IntegrationTest`의 opt-in Creature는 기존 단일 Movement writer가 Request를 소비하고 Feedback을 반환한다. 실제 Moving→Occupied와 사망 시 슬롯 반환, Client 표현 및 재접속을 검증했다. 아래의 “연결 대기”와 JYU 기록은 2026-10-01 당시 범위다. 현재 실행·검증은 [Creature 통합](CREATURE_PRODUCTION_INTEGRATION.md), [감각·Notify 고도화](CREATURE_SENSORY_AND_NOTIFY_REFINEMENT.md)를 따른다. 기존 JYU/M3 전체 전환 완료를 의미하지 않는다.

> 작업 브랜치: `codex/social-shelter-handoff`<br>
> 기준 커밋: `9461ae7` — 실제 위협 연동 및 문서 감사<br>
> 담당: 조연우 / Social Runtime · 최종 갱신 2026-10-01

## 1. 이번 작업의 범위

Social은 **유효한 행동·목적지 제안**을 제공하고 **이동 결과에 따른 예약 상태**를 소유한다. 실제 경로 탐색, 장애물 회피, 속도·Transform 적분은 이동 담당 계층이 맡는다.

```text
Policy Raw Action → Social Response → Shelter Query → Reservation
                                                        ↓
                                           Shelter Lifecycle Processor
                                              ↓                 ↑
                                 Movement Request           Movement Feedback
                                              ↓                 ↑
                                       단일 이동 writer (연결 대기)
```

이번에 추가한 것은 인계용 Request/Feedback Fragment, Reserved/Moving/Occupied 상태 전이, 예약 유지와 종료 규칙이다. PPO 관측 7개·행동 4개, 가중치, 자원/Vitals/Travel 작성자, Network transport 및 실제 이동 Processor는 변경하지 않는다.

Source: [인계 Fragment](../../Source/AdaptiveEcosystem/AI/Social/EcoSocialFragments.h), [설정·상태 타입](../../Source/AdaptiveEcosystem/AI/Social/EcoSocialMovementTypes.h), [Lifecycle Processor](../../Source/AdaptiveEcosystem/AI/Social/Shelter/EcoShelterLifecycleProcessor.cpp), [예약 Subsystem](../../Source/AdaptiveEcosystem/AI/Social/Shelter/EcoShelterSubsystem.cpp), [자동화 테스트](../../Source/AdaptiveEcosystem/AI/Social/Tests/EcoShelterLifecycleTests.cpp).

**JYU 개체가 실제 은신처로 걸어가는 기능은 아직 연결 대기다.** 자동화에서의 이동·도착 검증은 테스트 소비자가 위치와 결과를 제공하는 방식이다. 이 구분을 구현 완료/PIE 기록에도 유지한다.

## 2. 책임과 인계 데이터

| 데이터 | 작성자 | 읽는 쪽 |
|---|---|---|
| `FEcoPolicyOutputFragment.Action` | RL / Policy | Social Response, 현재 기존 Steering |
| `FEcoSocialBehaviorFragment.ModulatedAction` | Social Response | Shelter, Lifecycle |
| `FEcoSocialMovementRequestFragment` | Shelter Lifecycle | 이동 담당 Processor |
| `FEcoShelterMovementFeedbackFragment` | 이동 담당 Processor | Shelter Lifecycle |
| `FEcoShelterIntentFragment` / Slot lease | Social | 이동 계층은 직접 변경하지 않음 |
| Transform / Velocity / DesiredVelocity | 기존 이동 writer | Social은 도착/진행 확인을 위해 위치만 읽음 |
| HP / Travel State | 생명주기 / Migration | Social은 예약 자격 확인만 수행 |

### Movement Request

- `bValid`: 권위 World에서 살아 있는 유효한 Social 개체인지. false이면 이 Social 제안을 사용하지 않는다.
- `EffectiveAction`: Raw가 아닌 **Social 보정이 끝난 4개 행동**이다. 같은 항목에 Social 보정을 다시 곱하지 않는다.
- 인계에는 별도 Cohesion 배율을 중복 제공하지 않는다. `EffectiveAction.Cohesion`에는 이미 보정이 들어 있다.
- `Mode`: `None` / `ShelterTravel` / `ShelterHold`.
- `ReservationId`: World 내 예약 세대 번호. 0은 목적지 소유권 없음이다.
- `ShelterIndex` / `SlotIndex` / `TargetPosition`: 예약된 **슬롯**의 목적지다. Shelter 중심이나 Dummy Cover 목적지와 혼동하지 않는다.
- `ArrivalRadius`: cm, 3D 도착 허용 거리.
- `ValidUntilWorldTime`: 권위 World의 게임 시간으로 표현된 lease 만료 시각. 실제 벽시계 또는 다른 World의 시간과 비교하지 않는다.

`Mode=None`이어도 bValid=true이면 EffectiveAction을 제공한다. 별도 이동 목적지가 없는 일반 행동이다. `ShelterHold`는 도착한 슬롯 유지 제안이며 Social이 직접 속도를 0으로 쓰는 상태가 아니다.

### Movement Feedback

이동 계층은 현재 Request의 `ReservationId`를 포함하여 `Report(id, status)`로 새 결과를 기록한다. 이 함수는 Sequence를 증가시키며, Social은 동일 Sequence를 한 번만 소비한다.

| 상태 | 의미 |
|---|---|
| Moving | 요청을 채택했고 이동을 수행 중. 새 Sequence의 주기적 진행 보고 필요 |
| Arrived | 실제 슬롯 도착 또는 도착 위치 유지. Social이 실제 위치도 확인 |
| Failed | 경로 생성/이동 실패. 해당 예약 해제 및 재탐색 cooldown |
| Yielded | 이동 우선순위 판단에서 다른 의도가 선택됨. 해당 예약 해제 |
| None | 유효한 이동 결과 없음. heartbeat로 처리하지 않음 |

Report는 이동 의도를 실행한 뒤 매 프레임 또는 FeedbackTimeout보다 짧은 주기로 호출한다. 단순히 예전 Status 값을 버퍼에 남겨 놓는 것은 새 heartbeat가 아니다. 오래된 비동기 경로 결과는 **그 경로를 요청했을 당시의 예약 번호**로 보고해야 한다. 새 Request의 번호를 붙여 오래된 결과를 전달하지 않는다.

### 소비자 쿼리 예시 — 이동 담당자 구현 지점

```cpp
// 이동 담당 Processor의 ConfigureQueries에 추가할 계약 요구사항.
Query.AddRequirement<FEcoSocialMovementRequestFragment>(EMassFragmentAccess::ReadOnly);
Query.AddRequirement<FEcoShelterMovementFeedbackFragment>(EMassFragmentAccess::ReadWrite);
// 기존 Transform/Velocity/DesiredVelocity 작성 권한과 권위 태그 요구는 유지.
ExecutionOrder.ExecuteAfter.Add(UEcoShelterLifecycleProcessor::StaticClass()->GetFName());
```

기존 이동 작성자 **하나**가 Request의 유효성·모드·예약 만료를 확인해 채택하거나 Yielded를 보고한다. 경로 실패는 Failed, 진행은 Moving, 실제 도착은 Arrived를 보고한다. 일반 행동에 EffectiveAction을 소비하는 변경은 해당 이동/RL 담당자가 검토한다. 이 문서의 예시는 현재 기존 Steering에 이미 적용된 코드가 아니다.

## 3. 상태 전이와 유지 규칙

```text
None → Searching → Reserved
                      │ 새 Moving 보고
                      ▼
                    Moving
                      │ 새 Arrived 보고 + 실제 슬롯 거리 검사
                      ▼
                    Occupied

Reserved / Moving / Occupied → None
  위협/cover 요구 종료, 실패/양보, lease 소실, 소스 자격 소실,
  이동 보고 중단, 진행 정체, 슬롯 이탈, 죽음/삭제/이주
```

- 예약됐다는 이유만으로 Moving 또는 Occupied로 바꾸지 않는다. 소비자가 없으면 Reserved 상태로 대기하다 초기 TTL이 끝난다.
- 이미 슬롯에 있는 개체는 올바른 Arrived 보고로 Reserved에서 바로 Occupied가 될 수 있다.
- 최초 도착 허용 반경은 60cm, 점유 유지 반경은 120cm다. 작은 위치 흔들림 때문에 점유를 반복 획득/해제하지 않는다. 실제 위치가 유지 반경을 벗어나면 해제한다.
- Moving/Occupied는 새 이동 보고를 기본 2초 이상 받지 못하면 해제한다.
- Moving은 실제 목적지 거리가 10cm 이상 줄어든 경우 진행 시각을 갱신한다. heartbeat만 계속 보내도 8초 이상 목적지에 가까워지지 않으면 해제한다.
- 현재 진행 판정은 직선 거리 기반 휴리스틱이다. 벽을 크게 우회하는 정상 경로도 정체로 판단될 수 있어 이동 담당자가 경로 특성에 맞게 ProgressTimeout을 조정해야 한다. 경로 잔여 거리 기반 판정은 소비자 연결 시 별도 계약으로 검토한다.
- 유효한 진행/점유 상태는 기본 12초 lease를 연장한다. 초기 TTL이 만료되거나 번호가 교체된 예약은 연장으로 되살릴 수 없다.
- 실패·해제 후 재탐색 cooldown 기본 1초, 슬롯 경쟁 패배는 기존 0.5초다.
- 위협이 사라져도 Raw/Social Cover가 0.25 이상이면 은신 요구는 남을 수 있다. Alarm이 Calm이라는 사실만으로 해제를 결정하지 않는다.

시간은 pause/dilation을 따르는 World 게임 시간이다. Settings는 `FEcoSocialSpeciesSharedFragment.Shelter`로 설정한다. NaN/무한값, ExitRadius < ArrivalRadius, FeedbackTimeout > LeaseDuration 등 잘못된 설정은 해당 개체의 예약/Request를 비활성화한다.

## 4. 동시성·오래된 결과·삭제 처리

각 예약에는 단조 증가하는 `ReservationId`를 부여한다. 같은 개체가 같은 슬롯을 재예약해도 새 번호를 받는다. 유지/연장은 같은 번호를 유지한다. `ResetAllReservations`는 번호 발급기를 되감지 않는다.

- 해제/연장/반환값은 AgentId와 예약 번호를 확인한다. 늦게 온 Failed/Arrived가 새 예약을 변경하지 못한다.
- Slot 소유권에 Mass owner handle도 함께 기록한다. World 로컬 추적이며 저장/복제하지 않는다.
- Lifecycle은 유효한 예약 번호를 확인한 뒤, 확인되지 않은 Social 관리 예약을 해제한다. 마지막 개체가 삭제되거나 필수 Fragment를 잃어 쿼리에서 빠져도 고아 예약을 정리한다.
- 따라서 Lifecycle은 **QueryBasedPruning=Never**다. 살아 있는 개체가 없다는 이유로 정리 Processor가 제거되지 않게 한다.
- owner handle 없이 수동 API로 만든 기존 예약은 TTL 또는 명시적 Release를 따른다.
- State 변화와 Subsystem 갱신은 Server/Standalone GameThread에서 직렬 처리한다. 이동 결과는 Fragment로 주고받으며 worker에서 World Subsystem을 변경하지 않는다.
- 슬롯 경합은 SlotIndex → 정확한 Score 내림차순 → StableAgentId 오름차순이다. 기존 `IsNearlyEqual` 비교의 비추이성으로 정렬 순서가 불안정해질 수 있던 부분을 수정했다. 비유한 점수와 Invalid AgentId를 거부한다.

## 5. Migration과 이동 우선순위

현재는 M3 Migration의 권위를 보존한다. `FEcoTravelFragment.State == Traveling`이면 Social 예약과 이동 제안을 해제한다. HP=0, Alive 제거, PendingDeath, ClientProxy 역시 제외한다. 원래의 HP/Travel/Region 값은 변경하지 않는다.

일반 Flee/Forage/Cohesion/Cover 선호는 EffectiveAction으로 전달한다. Shelter와 긴급 Flee의 최종 경로 선택은 이동 writer가 수행하며, Shelter를 채택하지 않을 때 Yielded를 반환한다. 이 기본 계약을 실제 production 경로에 적용하기 전에 이동 담당자와 우선순위를 검토한다. 팀 합의 또는 전체 production 통합이 끝났다는 의미는 아니다.

M3 Bootstrap 가드와 Herbivore CustomMovement Tag는 유지한다. PPO 직접 적분과 M3 엔진 이동을 같은 Entity에 겹치지 않는다.

## 6. 실행 순서와 에디터 확인

`PrePhysics / Behavior`: Social Response → Query → Reservation → **Lifecycle**. Lifecycle은 Movement 그룹 이전에 실행한다. 미래 소비자는 Lifecycle 이후에 실행하고 그 결과는 다음 Lifecycle 패스에서 처리한다. 같은 프레임에 순환 의존성을 만들지 않는다.

Social Trait와 JYU Herd Harness에 Request/Feedback Fragment를 추가했다. Shelter HUD는 Reserved/Moving/Occupied를 구분해 표시하고 세 상태 모두 목적지 연결선을 그린다.

JYU에서는 기존 캐릭터 위협 감지/예약을 계속 확인할 수 있다. 기존 Harness에는 실제 이동 소비자가 없으므로 **Reserved 표시와 TTL 재탐색이 정상**이다. Moving/Occupied를 보려면 단일 이동 writer가 Request를 소비하고 결과를 보고하도록 연결해야 한다. 가까이 있다는 이유만으로 Occupied 표시를 만들지 않는다.

### 6.1 에디터 실행과 로그 전달

1. 최신 DLL을 사용하도록 에디터를 새로 열고 `Content/Map/Lvl_JYU`를 연다. 기존 Herd/Alarm/Shelter Harness와 Shelter Anchor 구성을 사용한다. 새 이동 컴포넌트를 추가하는 단계는 없다.
2. 실제 캐릭터 접근 시험에서는 Alarm Harness의 **Continuous Threat를 끄고**, 수동 위협 주입을 하지 않는다. Shelter Harness의 **Use Threat Location Override를 끈다**. 캐릭터의 Eco Threat Source 컴포넌트는 `Threat Enabled=true`, `Threat Strength=1`로 둔다.
3. Output Log 창을 열고 하단 Cmd 입력란에서 PIE 시작 전에 다음 명령을 실행한다.

   ```text
   eco.Shelter.Log 1
   ```

   기본값 0은 꺼짐, 1은 예약/상태 변경 이벤트와 5초 간격 요약, 2는 탐색·경합 상세 로그까지 기록한다. 추가 진단이 필요하면 `eco.Shelter.Log 2`, 종료 후에는 `eco.Shelter.Log 0`을 실행한다. 요약 주기는 World 게임 시간이므로 pause/dilation의 영향을 받는다. Shipping에서는 꺼진다.

4. 처음에는 플레이어를 개체의 감지 거리 밖에 둔다. PIE를 시작하고 5초 정도 초기 요약을 기록한 뒤, 개체가 바라보는 쪽에서 벽 없이 접근한다. 기존 감지에는 시야·LOS 조건이 있다.
5. Alert/Panic 반응과 은신처 예약을 확인하며 가까이에서 **20~30초** 유지한다. 현재 Harness에서는 Moving/Occupied가 나오지 않아도 정상이다. 예약이 12초 TTL로 만료되고 은신 요구가 남으면 재예약되어 새 Reservation 번호가 나온다.
6. 멀리 이동하거나, F8로 Eject한 뒤 **PIE 플레이어 인스턴스**의 Eco Threat Source에서 Threat Enabled를 끈다. 게임을 일시정지하지 않고 10~20초 더 관찰한다. 실제 위협이 활성인 채로 Clear All Alarms만 누르면 다시 감지되므로 입력부터 종료한다. 다른 실제 포식자/수동 위협도 남아 있지 않아야 한다.
7. Output Log 검색에서 `LogEcoSocialShelter`로 필터링하고 초기·접근·유지·종료 구간을 함께 복사한다. 로그가 크면 `Saved/Logs/AdaptiveEcosystem.log` 파일을 전달한다. 해당 파일은 프로젝트 폴더 아래의 가장 최근 실행 로그인지 확인한다. 테스트 날짜, 어떤 동작을 했는지와 화면 한 장도 함께 남긴다.

이번에 새로 구현한 진단은 [EcoShelterDiagnostics.cpp](../../Source/AdaptiveEcosystem/AI/Social/Shelter/EcoShelterDiagnostics.cpp)의 console variable과 `LogEcoSocialShelter` category를 사용한다. 상태/lease 이벤트에는 World·게임 시간·Agent·Reservation·Slot·Reason을 기록한다. 요약은 Processor 인스턴스별로 기록하며 여러 PIE World의 값을 전역 static 캐시에 섞지 않는다. 로그 토글은 예약/이동의 논리를 변경하지 않는다.

### 6.2 로그를 읽는 기준

| 로그/필드 | 의미·확인할 것 |
|---|---|
| `[Summary] Matched` | Lifecycle 쿼리에 잡힌 Entity 수. JYU Herd Harness가 활성인데 계속 0이면 Fragment/Shared 구성·스폰 확인 |
| `ValidRequests` / `NeedsShelter` | 유효 Social 요청 수 / Cover 또는 Panic으로 은신이 필요한 개체 수 |
| `Alert` / `Panic` | 유효 요청 개체 중 경보 상태별 수. 접근 후 증가하는지 확인 |
| `ActiveShelters` / `HeldSlots` | 등록된 유효 은신처 수 / 실제 예약 소유권이 있는 슬롯 수 |
| `[Reserve] Reason=Granted` | 예약 성공. Agent, Slot, Reservation, Target, Expires 기록 |
| `WaitingForMovementAck` / `FreshFeedback` | 현재 Reserved 개체 수 / 요약 사이에 새 예약 번호·Sequence가 일치하여 소비된 결과 수. None/Failed/Yielded도 소비 수에는 포함되므로 이동 heartbeat 수와 같지 않음 |
| `MissingFeedbackBuffer` | Feedback Fragment가 없는 Lifecycle 대상 수. 0이어도 실제 이동 소비자가 존재한다는 뜻은 아님 |
| `[Sample] ConsumedSeq=0` | 출력된 대표 예약 개체에 아직 일치하는 새 결과가 없음. FeedbackReservation/FeedbackSeq로 오래된 결과와 비교 |
| `[Transition] Reserved->Moving`, `Moving->Occupied` | 실제 소비자의 새 보고로 상태 전이. 현재 JYU에는 소비자가 없어 미출력이 예상됨 |
| `[Expire] Reason=LeaseTTL` / `[LeaseLost]` | 초기 lease 만료 또는 예약 소실. 이동 미연결 Harness에서는 TTL 만료가 예상됨 |
| `[StateRelease] Reason=NoShelterDemand` | Panic이 아니고 Social Cover < 0.25가 되어 예약 반환. Calm이라는 이름만으로 판정하지 않음 |
| `Reason=FeedbackTimeout` / `NoProgress` | 채택한 이동의 새 보고가 2초 중단 / 직선 거리 진행이 8초 정체 |
| `Reason=MovementFailed` / `MovementYielded` | 이동 실패 / 이동 담당자가 다른 의도를 선택 |
| `Reason=DeadOrInvalidHP`, `NotAlive`, `PendingDeath`, `Migrating` | 개체의 예약 자격 소실 |
| `Reason=OwnerMissingOrIneligible` | 필수 구성 소실·삭제 등으로 확인되지 않은 owner의 슬롯 반환 |
| `[Search] Result=NoAvailableCandidate` (2단계) | 해당 반경에 유효하고 비어 있는 후보가 없음. 등록 수·거리·슬롯 포화·좌표/반경 유효성 확인 |
| `[ReservationRejected]` (2단계) | 슬롯 경쟁 패배 또는 후보 무효/사용 중. 일부 개체의 패배만으로 오류라고 보지 않음 |

`NetMode`: 0=Standalone, 1=Dedicated Server, 2=Listen Server. Client는 Social 논리를 실행하지 않아 이 요약을 출력하지 않는다. `[Summary]`의 상태·개체 수는 현재 스냅샷이고 FreshFeedback/ArrivalRejected는 이전 요약 이후의 누적값이다. 동일 프레임에 Searching이 Reserved로 바뀔 수 있어 Searching=0만으로 탐색 불발을 판단하지 않는다.

벽 차폐가 다시 의심되면 PIE의 Shelter Harness에서 **Occlusion Probe Wall**에 벽을 지정하고 **Diagnose Threat Occlusion**을 실행한다. 이 기존 일회성 진단은 `LogTemp`의 `[ShelterOcclusion]`/충돌 설정 로그를 출력하므로 `LogEcoSocialShelter` 필터를 잠시 해제해 함께 전달한다. 차폐 판정은 Shelter 중심 기준이며 경로 도달 가능성을 판정하지 않는다.

## 7. 검증

2026-09-30, UE 5.8.2에서 직접 `UnrealBuildTool.exe`로 `AdaptiveEcosystemEditor Win64 Development` 빌드 **성공**. 초기 Unity 빌드에서 기존 Social 감지 함수의 `Dt`가 테스트 전역 상수를 가리는 C4459 오류가 발생해 해당 지역 변수 이름을 수정한 뒤 재빌드했다.

`UnrealEditor-Cmd /Engine/Maps/Entry -NullRHI`에서 `Automation RunTests AdaptiveEcosystem.Social` 실행: **9/9 통과, 실패 0, 미실행 0**. 기존 Threat 테스트 4개와 새 Lifecycle 테스트 5개를 함께 검증했다.

| 새 테스트 | 확인 범위 |
|---|---|
| HandoffAndArrival | Raw 보존, 이동 승인, 실제 거리 도착 판정, 점유 반경 hysteresis·이탈 |
| LeaseGenerationAndFeedback | 오래된 예약 결과 차단, 중복 Sequence 거부, heartbeat·초기 TTL 만료, 실패/양보 |
| ProgressAndRenewal | 진행 없는 heartbeat 해제, 실제 진행 중 lease 유지, 은신 요구 종료 |
| OwnerCleanup | HP=0, Alive 제거, ClientProxy 제외, 이주 및 마지막 개체 삭제 정리 |
| CompetitionAndOrder | 동일 점수 슬롯 경합의 ID 순서, 패자의 소유권 침해 방지, Query→Reservation→Lifecycle 의존성 |

로컬 결과: `Saved/Automation/SocialShelterLifecycle/index.json`, `Saved/Logs/SocialShelterLifecycleAutomation.log`. 초기 에디터 로딩의 기존 `Condition failed` 로그와 별개로 Automation Controller와 보고서의 9개 테스트 결과는 모두 Success다.

테스트 코드의 위치 변경은 이동 소비자를 모사한 검증이며 Social production Processor는 Transform/Velocity를 쓰지 않는다. 이번 작업에서는 JYU PIE, 실제 이동 소비자, production EntityConfig 및 Listen Server/Client 검증을 수행하지 않았다. 앞선 사용자 확인인 캐릭터 접근→Alert와 과거 Shelter 차폐 검증을 이번 Moving/Occupied 실증으로 확대하지 않는다.

### 진단 로그 추가 검증 — 2026-09-30

로그 추가 후 직접 UBT 빌드 **성공**, `eco.Shelter.Log 2`를 활성화한 Social 자동화 재실행 **9/9 통과**. 실제 출력에서 Search, Reserve, Summary/Sample, Reserved→Moving→Occupied, StateRelease, Expire 및 owner 삭제 정리를 확인했다. 새 단위 테스트를 추가하지 않았으며 기존 상태/예약 회귀 테스트를 사용했다. 로컬 산출물은 `Saved/Automation/SocialShelterDiagnostics/index.json`, `Saved/Logs/SocialShelterDiagnosticsAutomation.log`다. 이 결과는 자동화 테스트 World의 확인이며 사용자의 JYU PIE 로그는 전달 후 별도로 기록한다.

### 사용자 JYU PIE 로그 확인 — 2026-09-30

사용자가 은신처가 없는 위치와 있는 위치를 오가며 실행한 `Saved/Logs/AdaptiveEcosystem.log`를 읽었다. 주요 실행은 **23:43:58~23:45:00 KST**, Standalone JYU (`NetMode=0`)다. 게임 시간 9.76초에 `eco.Shelter.Log 1`을 켰으므로 그 이전 이벤트는 이 진단 범위에 포함되지 않는다. 이후 23:45:12~23:45:14에 짧게 재시작한 기록도 있다.

| 확인 항목 | 실제 로그 근거 |
|---|---|
| Harness 구성 | 100 Entity / 5 cluster, CoverSearchRadius=3000cm. 모든 요약에서 Matched=100, ValidRequests=100, MissingFeedbackBuffer=0 |
| 은신 요구/예약 | 은신처 3곳 등록. 첫 실행 요약에서 NeedsShelter=11~37, 동시 Reserved/HeldSlots 최대 6. 로깅 활성 후 `[Reserve]` 42회 기록 |
| 실제 경보 반응 | Alert/Panic 수가 실행 중 변함. 게임 시간 19.76초에 Alert=2, Panic=18 |
| 초기 lease 만료 | `[Expire] Reason=LeaseTTL` 9회, 대응 `[LeaseLost]` 9회. Reservation=12는 게임 시간 13.32초 예약 → 25.32초 만료, 이후 새 번호로 예약 |
| 은신 요구 종료 | `[StateRelease] Reason=NoShelterDemand` 34회 및 슬롯 반환 확인. 이로써 개별 개체의 요구 종료 반환은 사용자 PIE에서도 확인 |
| 이동 미연결 | 모든 요약에서 Moving=0, Occupied=0, FreshFeedback=0. Reserved 및 WaitingForMovementAck만 존재하며 현재 Harness 계약과 일치 |
| PIE 종료/재시작 | 62.76초 종료에서 남은 5개 예약이 ShelterUnregistered로 반환. 재시작 0.01초 요약은 NeedsShelter=0, Reserved=0, HeldSlots=0 |

이 결과는 **사용자 JYU의 권위 Social 요청 생성·예약·TTL·개별 요구 종료 반환 확인**이다. 최종 첫 실행 요약(59.76초)은 NeedsShelter=26, Reserved=5여서 위협 종료 후 전체 요구/예약이 0까지 내려가는 장면은 확인되지 않았다. 재시작의 0은 새 World 초기화이며 이를 위협 종료 검증으로 대체하지 않는다.

1단계 로그에는 Search 결과·개체/플레이어 이동 동선·차폐 적중 정보가 없으므로, 사용자 설명의 “은신처 없는 위치” 구간을 특정하거나 NoAvailableCandidate/슬롯 경쟁/벽 차폐를 확정하지 않는다. 은신처 탐색 반경은 **개체 위치 기준**이며 플레이어가 은신처 없는 곳에 서 있어도 개체 반경 안의 후보를 예약할 수 있다. 모든 개체가 예약되지 않는 상황은 요구 수와 동시 예약 수만으로 오류라고 판정하지 않는다. 상세 후보 확인은 `eco.Shelter.Log 2`의 Search/ReservationRejected와 함께 판단한다.

확인한 첫 JYU 스폰 이후 구간에서 Error/Fatal/Assert/Ensure는 발견되지 않았다. 에디터 시작 시점의 기존 `LogAutomationTest: Error: Condition failed`는 로그에 있으므로 전체 로그가 오류 없이 깨끗하다고 기록하지 않는다. 실제 이동·도착·점유, production EntityConfig, 사망/이주 PIE 및 Client는 기존처럼 확인 대기다. 이번에는 로그/문서만 검토했고 새 UBT나 PIE를 실행하지 않았다.

### HUD 색상 혼동 수정 — 2026-10-01

사용자가 “은신처 가까이 있는 개체는 빨강으로 안 변한다”고 보고한 뒤 최신 `AdaptiveEcosystem.log`를 확인했다. 00:03:15 KST, 게임 시간 11.23초의 Sample은 **Agent=1021, State=Reserved, Alarm=0.72**이며 기본 PanicThreshold=0.6보다 높다. 21.23초에도 Agent=1007이 Reserved, Alarm=0.74였다. 예약 개체 역시 Panic 강도에 도달하는 로그이므로 예약이 경보를 억제한다고 해석하지 않는다. 새 로그에는 2단계 Search의 NoAvailableCandidate 및 ReservationRejected도 기록돼 있으나, NoAvailableCandidate만으로 후보 거리와 슬롯 포화를 분리하지는 않는다.

기존 `DrawEntityHUD`는 Reserved/Moving/Occupied 분기에서 은신처 점수에 따른 초록/주황 글자만 출력하고 Alarm 표시 분기를 건너뛰었다. 이를 [Shelter Harness](../../Source/AdaptiveEcosystem/Debug/EcoShelterTestHarnessActor.cpp)에서 두 줄로 수정했다.

- 첫 줄 `A1021 [Panic] 0.72`: Agent ID·Alarm 상태·강도. Panic=빨강, Alert=주황, Recover=하늘색, Regroup=핑크.
- 둘째 줄 `S#0 [Reserved/Safe] 0.95`: 예약 상태·기존 점수 분류. Alarm 색상을 덮어쓰지 않는다. Safe/Danger는 기존 종합 점수 0.7 기준이며 실제 도착/벽 차폐의 독립 검증 결과가 아니다.
- 예약 없는 Calm 개체의 글자는 기존처럼 숨긴다. 슬롯/앵커/의도선의 기존 색상과 Alarm Harness의 경보 구체는 유지한다.

**개체 주변 구체**의 빨강은 Alarm Harness에서 Panic 상태로 그린다. 실제 구체가 빨강이 아니라면 새 첫 줄의 상태·강도를 확인한다. Alarm의 전이는 거리 감쇠와 0.6/0.2 기본 임계값을 사용하고, 감지는 FOV/거리/Visibility LOS를 따른다. 벽 차폐는 직접 감지를 막을 수 있고 같은 Herd의 다른 구성원이 발견한 경보는 여전히 전파될 수 있다. 현재 Shelter 위치/예약 여부로 Panic을 낮추는 로직은 없다.

수정 후 직접 UBT `AdaptiveEcosystemEditor Win64 Development` 빌드 **성공**. HUD만 수정했으므로 자동화 테스트를 추가하거나 재실행하지 않았다. 새 두 줄의 실제 PIE 시각 확인은 사용자 재생 후 기록한다. 이전 Social 자동화 9/9 결과는 앞선 상태 관리 코드의 검증 기록이다.

### 화면의 슬롯 색상 및 2단계 로그 재확인 — 2026-10-01

사용자가 새 로그와 Shelter #1 화면을 전달했다. 해당 실행의 00:13~00:14 KST 구간에서 `eco.Shelter.Log 2`가 활성화됐고, Matched/ValidRequests=100, ActiveShelters=3을 확인했다. 초기 3.48초는 NeedsShelter/Reserved/HeldSlots=0, 8.49초는 Panic=18, Reserved/HeldSlots=6이었다. 23.49초 Sample은 **Agent=1078, State=Reserved, Distance=442.5cm, Alarm=0.81**이었다. 실제 예약 개체도 Panic 기준 이상의 경보를 받는다. Moving/Occupied/FreshFeedback은 이번에도 0으로 이동 소비자 미연결 상태다.

로깅 활성 이후 Search 427회 중 Candidate=69, NoAvailableCandidate=358, ReservationRejected=47, Reserve=22를 확인했다. NoShelterDemand에 의한 반환 18회와 PIE 종료의 ShelterUnregistered 반환 4회가 기록돼 있다. 후보가 없다는 결과는 등록 후보의 거리/빈 슬롯 조건 중 무엇이 원인인지 단독으로 확정하지 못한다. 확인한 PIE 구간에는 Error/Fatal/Assert/Ensure가 없으며 초기 에디터 로딩의 기존 Condition failed는 별도로 존재한다.

첨부 화면의 Shelter #1 양옆 주황 구체 두 개는 **개체 경보가 아니라 예약 슬롯**이다. `Slots: 2/2` 표시와 일치한다. Harness는 예약 슬롯을 Orange, 빈 슬롯을 Cyan으로 그린다. 중심의 은신처 구체/원은 슬롯이 전부 예약되면 Red다. 따라서 이 표시를 개체의 Alert/Panic 색상으로 해석하지 않는다. 개체 경보 구체는 개체 위치+40cm에 Alarm 상태별로 별도 그린다. `[THREAT SOURCE]`도 별도의 위협 위치 표시다.

화면은 Shelter #0의 차폐 표시 OccScore=1.0 및 #1/#2 노출 표시 OccScore=0.1을 보여준다. 슬롯 2/2는 예약 소유권이며 실제 Occupied가 아니다. 첨부 영역에는 새 개체 두 줄 HUD가 보이지 않아 그 렌더링은 시각 검증 완료로 올리지 않는다. 이번에는 로그·화면·Source를 확인하고 문서만 갱신했으며 새 빌드나 PIE를 실행하지 않았다.

## 8. 다음 담당자 인계

1. production EntityConfig에 Social Trait와 정책/종 공유 데이터가 올바르게 구성됐는지 확인한다.
2. 이동 담당자가 기존 writer 하나에 Request/Feedback 계약을 연결한다. 경로 도달 가능성·목적지 중단·Migration/Flee 우선순위를 검토한다.
3. JYU 실제 은신 이동/도착/점유/종료와 Listen Server/Client를 검증한다.
4. 도착 위치의 실제 안전성, 실패한 후보 회피와 위협 이동에 따른 예약 재평가는 별도 개선이다. 현재 차폐 점수는 Shelter 중심 기준이며, 예약 슬롯의 경로/차폐를 보증하지 않는다.

## 9. 브랜치 포함 관계와 작업 정리 — 2026-10-01

현재 작업 브랜치는 **`codex/social-shelter-handoff`**다. 커밋 전 로컬 브랜치와 Source를 확인했다.

| 이전 브랜치 | 확인한 커밋 | 현재 브랜치에 포함된 내용 |
|---|---|---|
| `codex/social-runtime-docs-audit` | `295ac2f` | 해당 브랜치의 커밋은 현재 브랜치의 조상이다. 당시 문서 감사 변경은 다음 작업의 `9461ae7`에 함께 커밋됐다. Architecture, Policy 계약, Mass 실행 순서, Social 현재 상태·가이드 등 문서 변경을 `git show 9461ae7 --stat`에서 확인 |
| `codex/social-threat-integration` | `9461ae7` | 실제 포식자/Actor Threat Source 감지, Herd 경보 연동, 테스트와 문서, 기존 캐릭터 컴포넌트·JYU 테스트 환경 포함 |
| `codex/social-shelter-handoff` | `9461ae7`에서 이어 작업 | Social 이동 인계 계약, 예약 생명주기, 진단 로그, HUD 개선 및 이번 JYU 저장본 추가 |

두 이전 브랜치 모두 `git merge-base --is-ancestor <branch> HEAD`가 성공했다. 문서 감사는 별도 merge commit이 아니라 `9461ae7`의 변경 내역에 포함된 형태다. 이 기록은 위 로컬 커밋을 기준으로 하며 이후 다른 브랜치에 추가되는 작업까지 포함한다고 보증하지 않는다.

### 이번 커밋에 담는 기능

- **이동 담당자에게 전달할 데이터:** 보정 행동과 유효한 예약 목적지를 Request로 제공하고, 예약 번호·Sequence가 맞는 Feedback만 처리한다.
- **예약 관리:** 승인/도착 결과에 따른 Moving/Occupied 전이, lease 유지, 진행 정체·실패·은신 요구 종료·사망·삭제·이주에 따른 반환을 구현했다.
- **운영 확인:** `eco.Shelter.Log 1/2`로 예약 이벤트와 요약을 수집하고, 개체 경보와 은신처 예약 정보를 HUD에서 함께 표시한다.
- **테스트 환경·문서:** 사용자가 시험하며 저장한 `Content/Map/Lvl_JYU.umap`을 포함한다. 계약·실행 순서·구현 현황·에디터 설정 및 실제 로그 해석을 갱신했다.

### 검증 결과와 남은 연결

직접 UBT 빌드 성공, Social 자동화 **9/9 통과** 및 사용자 JYU 로그·화면 확인 기록은 7절에 보존했다. 사용자는 이번 테스트 동작을 정상으로 확인했다. 차폐/노출 점수와 예약/반환·경보 반응을 확인한 범위이며, 실제 은신 이동·도착/점유·Client 검증은 여전히 연결 대기다. 새 두 줄 HUD 전체 화면의 시각 검증도 별도로 남아 있다.

다음 작업은 이동 담당자가 **기존 단일 이동 writer에 Request 소비와 Feedback 반환을 연결**하는 것이다. Social에서 별도 위치 적분을 추가하지 않는다. 이번 마무리에서는 문서와 Git 포함 관계를 검토했으며 새 UBT/자동화/PIE 실행을 수행하지 않았다.
