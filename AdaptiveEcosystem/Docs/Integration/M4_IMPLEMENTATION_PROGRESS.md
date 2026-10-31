# M4 통합 구현 진행 기록

기준: `M4`, 시작 HEAD `3062180` (Source 기준 `6235742`) / UE 5.8 / 2026-10-13.

**새 복사 레벨의 현재 설정 기준:** [수동 배치·팀 기능 연결 가이드](M4_NEW_LEVEL_MANUAL_SETUP.md). 레벨 복사와 Actor/BP 배치는 사용자가 수행한다. 이 문서의 기존 맵 실행 기록을 새 레벨의 통과 기록으로 재사용하지 않는다.

사용자 요청에 따라 자동화 테스트는 작성·실행하지 않는다. 각 마일스톤의 소스 구현, 직접 UBT, 수동 실행은 별도 상태로 기록한다. 최초 UBA 저장소 접근 오류 실행은 사용자 승인으로 종료했다. 프로젝트 내부 저장 경로로 재실행하고 타입 추론·이름 충돌을 수정한 직접 UBT가 성공했다. 실제 맵의 CLI 실행은 GUI PIE/렌더 검증과 구분한다.

| 마일스톤 | 소스 작업 | 빌드 / 수동 상태 | 확인 문서 |
| --- | --- | --- | --- |
| A 기준선 복구 | Replicator lambda/capture, Migration 중복 실행·signature 복구 | UBT 성공 / 동물 Standalone 90초, Box 300초 논리 실행 정상 종료·8개체 실제 이주 | [A](Milestone_A_EDITOR_CHECK.md) |
| B 복제 정확성 | 이동 serial/시각과 표현 revision 분리, 실제 동물 표본 보간/reset | UBT 성공 / 3지역 서버+두 차례 접속 정상 종료, 실제 presentation-only 수신 관측; 지연/teleport 등 수동 게이트 남음 | [B](Milestone_B_EDITOR_CHECK.md) |
| C 정책 필수 보정 | HP/pending/client 필터, 초 단위 정책 debt/EMA, 최종 heading, 피식 분모 snapshot | 최종 UBT 성공 / 20·30·60FPS 약 7.5회/개체·초, 관측된 fallback 0; Golden/행동 품질 미실행 | [C](Milestone_C_EDITOR_CHECK.md) |
| D 공통 생명주기 | 종별 생존 adapter, 공통 Death/feeding/migration receipts, 세계·지역×종 회계/멸종 row | 최종 UBT 성공 / 포식·섭식 회계 실행, Box 16개체 단일 기아 사망·정리, 최종 동물 이주/지역×종 보존 검사 정상 | [D](Milestone_D_EDITOR_CHECK.md) |
| E 환경 폐루프 | World 날씨/clock bridge, 지역 강수량→재생 opt-in, 완료 자원 step 환경 snapshot·Client DTO | 최종 UBT 성공 / 건조·비 설정의 실제 공급 1/3 Food/s·회계 정상, 기존 하늘 BP 노드 연결·렌더 확인 남음 | [E](Milestone_E_EDITOR_CHECK.md) |
| F 계측·예산·스케줄 | CPU trace, step ID lookup, 단일 집계, 감각 grid 후보, Actor pool/예산, 연결 Add/relevance cap, 순수 추론 worker opt-in, 원거리 정책 LOD opt-in | 최종 UBT 성공 / 기본 Actor/pool 상한 관측; worker dispatch·LOD·대규모/CPU/packet 성능 측정 미실행 | [F](Milestone_F_EDITOR_CHECK.md) |

## 파일별 책임

| 파일 | 책임 |
| --- | --- |
| `Creature/Runtime/EcoCreatureIntegrationSpawner.*` | opt-in coordinator 생명주기·월드 완료 경계, 기존 Blueprint 클래스 identity 보존 |
| `EcoCreatureSpawning.cpp` | template/맵 검사, spawn·StableAgentId·종별 생존 설정 초기화 |
| `EcoCreatureSetupValidation.cpp` | 수동 배치의 읽기 전용 검사·Editor 버튼, 시작 전 ID/수량/좌표/Config/환경 설정 검증 |
| `EcoCreatureTemplateValidation.cpp` | 서버/Client의 실제 template 구성 검증·등록, 역할/단일 movement/Client 논리 분리 |
| `EcoCreatureLifecycle.cpp` | 완료 자원 step, 먹이 요청·결과, 공통 생존/사망·이주 commit 조정 |
| `EcoCreaturePopulation.cpp` | 한 번의 지역 누산, 실제 Birth-Death 회계, 동일 완료 step의 지역×종 summary |
| `EcoCreatureWorldProviders.cpp` | 권위 자원·authored Shelter의 관측 읽기. 자원 차감하지 않음 |
| `EcoCreaturePresentation.cpp` | Client/Host 표시 선택·보간·reset·Actor budget/pool. 생태 상태 쓰기 없음 |
| `EcoCreatureScheduling.cpp` | opt-in 원거리 정책 주기. 이동·생존·예약 시간을 줄이지 않음 |
| `EcoCreatureDiagnostics.cpp` | 수동 인구/Actor/pool/step/정책 debt 진단 |
| `Mass/EcoMassSurvival.*` | Box와 Creature의 검증→생존/Death 결과 적용, 예약/Travel/feed 정리, dead 잔류/삭제 |
| `Mass/EcoMassMigration.*` | 자원/압력 snapshot→이주 계획·실제 도착 commit. 위치 적분 없음 |
| `AI/Policy/EcoNeighborhoodGatherProcessor.cpp` | 살아 있는 개체의 위치·종·ID spatial snapshot |
| `EcoPerceptionProcessor.cpp` | 기하/위협/동종 관측 입력 |
| `EcoPolicyProcessor.cpp` | 관측·시간·실행 모드와 개체별 출력 commit |
| `EcoPolicyBatch.*` | UObject/Fragment 참조 없는 수치 추론 batch. worker 완료까지 barrier |
| `EcoPredationProcessor.cpp` | 포획·원인/predator ID 요청, 정책 EMA. Ecology Death commit은 하지 않음 |
| `EcoSteeringProcessor.cpp` | 사슴의 단일 위치/속도 writer와 Social Request/Feedback |
| `AI/Social/Senses/EcoPredatorPerception.cpp` | grid 후보를 사용한 감각/기억. 위험/자원 원장 쓰기 없음 |
| `World/EcoRegionEnvironmentAdapter.*` | 기존 날씨/하늘 Blueprint와 권위 Region 환경·논리 clock 연결 |
| `Ecology/EcologyResourceSimulation.cpp` | 재생·공급·손실·배분·완료 snapshot 단일 원장 |
| `Ecology/EcologyEnvironmentSimulation.cpp` | 완료 경계에서 World 입력 검증·snapshot, opt-in 강수량→재생 반응 |
| `Debug/EcoEnvironmentDiagnostics.cpp` | 서버의 명시적 수동 강수량·재생 설정 명령. 자동화 실행 없음 |
| `Network/Mass/EcoMassReplicator.cpp` | 연결별 표본/gate, 모든 종/Template 합산 Add/relevance admission |
| `Mass/EcoMassPresentationFragments.h` | stale/중복 수신 판정과 Client 표본 timeline |

## 유지한 계약과 opt-in

- V1 관측 7/행동 4, 기존 가중치·정규화·Raw Action 보존. 기본 관측 5는 지역 Provider 의미를 유지한다.
- `eco.Policy.PredationSource 1`은 학습 전역 EMA 실험이다. 기본 0. 피식 분모는 두 경우 모두 개체별 1/max 오류를 없앴다.
- 기본 Creature 사슴은 기존 대사 1/s, Food gain 5, 기아 유예 0, 피해 5/s. 늑대 survival은 기본 꺼짐. Box baseline 값과 별개다.
- 지역 재생률 기본 0, Spawn Waves 기본 꺼짐. 공급/반복 시연은 명시적 설정이다.
- 강수량 반응은 기본 꺼짐. 켜면 `Rate × lerp(DryMultiplier, WetMultiplier, Rainfall)`을 자원 step에 한 번 적용하며 실제량은 잔여 capacity까지다. Weather/논리 clock의 Client 시각 입력은 GameState 요약을 거친다.
- 순수 추론 worker와 정책 Simulation LOD는 기본 꺼짐. 실제 개선/정확성을 측정한 것으로 기록하지 않는다.
- 기존 Box/PPO/CustomMovement Bootstrap 혼용 거부를 유지한다. Social에 위치 적분을 넣지 않는다.

## 남은 적용·검증 경계

- 연결 admission은 기존 엔진 relevance/LOD 후보와 반복 Add를 사용한다. 상한 도달 시 기존 관련 항목을 유지하고 새 후보를 보류한다. 전 연결 후보를 거리순으로 다시 선발하거나 플레이어 상호작용을 우선 evict하는 기능은 별도다.
- Actor는 거리와 기존 binding 유지 bias로 선발하며 active+hidden pool 총량을 제한한다. 먼 SkeletalMesh를 ISM/VAT로 바꾸는 신규 에셋은 만들지 않았다.
- catch-up은 논리 생존/자원 시간을 보존하며 물리 위치를 재적분하지 않는다. 과거 행동/충돌을 완전히 replay하는 sim-to-sim 구현은 아니다.
- V3의 18/19 관측·5 logits·새 마스크·M8/무정원 Shelter 전환, 새 모델 선택·가중치 로더는 기존 계약 변경과 RL Export 산출물에 의존한다. 이번 V1 기준 코드에 묵시적으로 적용하지 않는다.
- authored 식물 원장, 다종 종 정의, 두 대륙 unload/저장 복원은 전체 계획의 후속 범위다. 소규모 통합 안정화·수동 게이트를 통과한 뒤 진행한다.

직접 빌드 보조: `Tools/Integration/build_integration_milestone.ps1 -Milestone A` (B~F/Final 지원). 실행 중 엔진/빌드가 있으면 시작을 거부하고 어떤 프로세스도 종료하지 않는다. 자동화 테스트를 호출하지 않는다. 실제 UBT 로그는 `Saved/IntegrationBuilds/`에 저장한다.

## 실행 증거

- A 빌드: `Saved/IntegrationBuilds/Milestone_A_20261013_131302.log`, 성공. 이 빌드는 A~F 초기 Source 작업을 함께 컴파일했다. C~F를 각각 분리 빌드했다고 주장하지 않는다.
- B 빌드: `Saved/IntegrationBuilds/Milestone_B_20261013_131751.log`, velocity-only gate 보정 포함, 성공.
- `Integration_MilestoneA_Creature.log`: 14개체/2지역, 90초 Standalone/NullRHI, 종료 0. 고유 Death 11, Shelter Moving→Occupied 관측, 마지막 Alive 3. Fatal/assert/runtime-stop 0.
- `Integration_MilestoneA_Box.log`: `Jang_lv`, 300초 고정 시간/NullRHI, 종료 0. ID 1~8의 Forest_A→Forest_B 실제 도착, Death 0, Error/Fatal 0. 기아 사망 검증은 이 실행의 결과가 아니다.
- `Integration_B_Server.log`: 실맵 19개체/3지역, Dedicated/NullRHI 150초, 종료 0. 고유 Death 12, Error/Fatal/runtime-stop 0.
- `Integration_B_ClientA.log`: 위 서버에 실제 접속, 권위 Owned 0·표현 Actor 수신·지역 전환, 42초 정상 종료 0. NullRHI이므로 메시/애니메이션의 화면 품질 확인은 별도다.
- `Integration_B_ClientB.log`: 두 번째 접속 시 proxy/표현은 수신했으나 서버 종료가 클라이언트의 42초 종료보다 먼저 발생했다. 기본 맵으로 travel하면서 fixture 타이머가 사라졌다. 재접속 검증 통과로 기록하지 않는다. PID/실행 인자로 해당 작업이 만든 게임 프로세스임을 확인하고 정리했다. 종료 승인 질문은 ‘빌드 중단 금지’를 게임 클라이언트 종료로 확대 해석한 것이어서 철회했다. 이후 engine `-SECONDS=`를 추가했다.
- `Integration_Final_Server.log`, `Integration_Final_ClientA.log`, `Integration_Final_ClientB.log`: 최종 표본 계약/진단 코드의 Dedicated 140초 + 동일 서버의 순차 Client 42초 접속 2회, 모두 종료 0/Ready=1. 서버 19 births/13 고유 Death/6 alive, Error/Fatal/runtime-stop 0. Client authority Owned=0, presentation-only 수신 카운터 실제 증가, 초기/relevance 재진입 buffer reset, 관측 Rejected=0. 과거/중복 표본을 의도적으로 주입한 시험은 아니다. 이 실행은 종별 누적 DTO와 최종 전체-chunk batch 정리 이전이며 기본 복제 경로의 증거다.
- `Integration_E_Dry20.log`: 20FPS, 20초/Step21, Rain=0·Rate2·Dry0.5·Wet1.5 → 실제 공급 1 Food/s. 고유 Death5, Ready=1, 종료0, Error/Fatal/runtime-stop0.
- `Integration_E_Wet60.log`: 60FPS, 20초/Step21, Rain=1 → 실제 공급 3 Food/s. 고유 Death7, Ready=1, 종료0, Error/Fatal/runtime-stop0. 위 두 실행은 성장식·회계와 FPS 스케줄을 확인했다. FPS가 달라 행동 품질의 날씨 인과 비교로 사용하지 않는다.
- `Integration_D_BoxStarvation.log`: `Jang_lv` 두 지역 Food=0 수동 주입, 300초 고정 시간 실행, 종료0. 고유 Starvation Death16(Time115), Cleanup16(Time117), 피식으로 분류하지 않음, Error/Fatal0.
- 최종 직접 UBT: `Saved/IntegrationBuilds/Milestone_Final_20261013_134804.log`, 성공. 기존 StructUtils 폐기 예정 경고/XGE 라이선스의 standalone fallback 경고는 기록됐으며 빌드 실패는 아니다.
- `Integration_Final_CreatureMigration.log`: 위 최종 빌드의 40초 Standalone/NullRHI, Forest_A 고갈 주입. 실제 Forest_A→Forest_B 도착과 지역×종 보존 검사, 전체-chunk 정책 batch의 기본 serial 경로를 확인했다. 종료0/Ready=1, 마지막 alive2 = births14 - deaths12, active2+pool12≤64, Error/Fatal/runtime-stop0. 최종 Source 입력 SHA256 목록은 `Saved/IntegrationBuilds/M4_Final_SourceManifest.json`에 저장했다.

자동화 suite·Golden Vector·GUI PIE·cook·packet/성능 수치·장기 soak는 이 증거에 포함되지 않는다.

## 새 레벨 수동 통합 요청에 대한 후속 구현

2026-10-13, 같은 M4 working tree에서 A~F를 재대조하고 새 레벨 설정용 부족한 부분을 보완했다. Content/Config·레벨 복사·Actor/BP 배치·자동 배치 Python 도구·자동화 테스트는 변경/실행하지 않았다.

| 단계 | 이번 후속 코드 작업 | 확인 / 사용자 수동 게이트 |
| --- | --- | --- |
| A | Coordinator의 `ValidateEditorSetup` 버튼과 기본 설정 검사. 중복 coordinator/RegionId, Groups ID, 수량/cap, 좌표/arrival/인접 ID, 환경·GameState 검사 | 읽기 전용 버튼의 실제 Editor 클릭과 새 레벨 배치는 사용자 진행. 기존 3지역 맵 시작 검사는 통과 |
| B | Config의 predator 역할과 실제 서버/Client template 필수/금지 fragment를 생성 전에 검사. 단일 movement 가드와 Client 논리 분리 유지 | 기존 맵 Dedicated/Client 양쪽 template `Validated=1`. 새 레벨의 reset/지연/재진입은 별도 확인 |
| C | 기존 7관측/4행동·수치·초 단위 스케줄 보존. numeric batch가 실제 ParallelFor 경로를 선택한 결정 수 계측 | 이번 변경은 관측·가중치 교체가 아님. Golden/행동 품질 판정 생략 |
| D | 초기 사슴+늑대 합계와 지역 spawn cap 불일치, wave 좌표 부족, 잘못된 초기 자원/환경을 변경 전에 거부 | 기존 맵의 19개체 초기화·완료 생존/자원/종별 회계 정상. 새 레벨의 이주/과밀/늑대 생존은 단계별 확인 |
| E | 비복제 배치 Actor의 HasAuthority를 World NetMode로 교체해 Client 표시 이벤트 차단 오류 수정. ApplyRainfall API로 온도/습도 유지. BP 입력 속성 공개 | UBT 확인. 사용자가 배치할 Adapter/기존 Weather/Sky BP 연결과 Client 이벤트·렌더 확인은 미실행 |
| F | ParallelDecisions와 BudgetDeferredAdds 계측. 작은 19개체 fixture에서도 예산 초과를 확인할 설정을 가이드에 명시 | 기본 client Actor+pool 상한 관측. 실제 worker dispatch/Simulation LOD/대규모·packet/CPU 판정은 미실행 |

- 직접 UBT `Milestone_Final_20261013_162307.log`: 성공. 첫 후속 빌드의 AActor Role 이름 충돌과 Spring Movement 헤더 누락을 수정한 뒤 재빌드했다.
- `Saved/Logs/M4_ManualSetup_Standalone.log`: 기존 Integration Test, 19개체·3지역, 20초/NullRHI, 종료0, Ready=1 Step20, template 역할 검사 통과.
- `Saved/Logs/M4_ManualSetup_Server.log`: 같은 코드·기존 맵 Dedicated 65초, 종료0, Ready=1 Step65, Visuals0.
- `Saved/Logs/M4_ManualSetup_Client.log`: 위 서버에 25초 실제 접속, 종료0, Ready=1, 역할별 Client template 검사 통과, LogicalOwned0·proxy/Actor 수신. 새 레벨/Adapter BP가 배치된 실행이나 GUI/오디오 확인은 아니다.
- 마지막 Client 검사 보완은 이동·수명·감각 논리 fragment가 섞인 template도 거부한다. 최종 UBT `Milestone_Final_20261013_164338.log` 성공 후 `M4_ManualSetup_FinalServer.log`(45초) / `M4_ManualSetup_FinalClient.log`(15초)에서 양쪽 종료0/Ready1, 역할별 Validated1, Client LogicalOwned0을 재확인했다. Error/Fatal/runtime-stop0. 현재 Source 입력 hash는 `Saved/IntegrationBuilds/M4_ManualSetup_SourceManifest.json`에 갱신했다.

새 가이드는 Actor/에셋 참조, world-space 스폰·먹이 좌표와 local-space Arrival Offset, World Partition 상시 로딩, 단계별 최소 설정/기대 결과, Weather/Sky Blueprint 인계와 실패 확인 순서를 포함한다. 코드 구현과 실행 게이트를 구분하며 전체 A~F의 성능/출하 게이트까지 통과했다고 선언하지 않는다.
