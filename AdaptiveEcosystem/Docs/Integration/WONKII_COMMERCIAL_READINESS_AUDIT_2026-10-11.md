# wonkii 담당 영역 — 상용 적용 평가와 구현 순서

작성일: 2026-10-11 / Source 기준: 로컬 `M4`, `6235742` / 프로젝트 기준 엔진: UE 5.8.

범위는 생태계 총괄, 공통 생명주기·자원·이주·집계, 서버 권위, Mass 복제와 Client 성능이다. Social·감각·정책·레벨은 이 영역에 연결되는 계약만 평가한다. 이 문서는 Source 정적 감사와 Epic 공식 문서·Riot 개발사 자료에 기반한 **평가 및 구현 제안**이다. 이번 작업에서 C++ 수정, UBT, 자동화, PIE, 패키징, 성능 측정은 하지 않았다. 기존 작업 트리의 P1~P6와 Docs/README 변경은 그대로 보존했다.

## 1. 판정

현재 단계는 **기능을 시연하고 일부 정확성을 검증한 통합 프로토타입**이다. 상용 게임용 기반으로 삼을 수 있지만, 제품 수준의 대규모 성능·네트워크 품질·지속성·실패 복구가 입증된 런타임이라고 평가할 근거는 부족하다. 소규모 세션 게임과 장시간 지속되는 온라인 월드의 요구는 다르므로 최대 논리 개체 수, 동시 Client 수, 최소 사양, 세션 길이, 저장 요구부터 명시해야 한다.

이미 갖춘 기반은 서버/Standalone 권위 분리, StableAgentId, 지역 자원 배분과 보존 검사, Box의 시각 기반 대사·기아·단일 사망 처리, 이주 결과·요약, Mass Bubble과 연결별 이동 검사 간격이다. 문제는 기반 부재보다 **서로 다른 실행 경로의 통합과 실제 부하에서의 보장 부족**이다.

특히 현재 HEAD의 복제 Source에는 문법 오류가 있다. 과거 빌드 성공 기록을 현재 HEAD의 실행 가능성으로 해석하면 안 된다.

## 2. 문제별 근거와 상용 영향

| 우선순위 | 실제 근거 | 상용 게임에서의 영향 | 구현 방향 |
| --- | --- | --- | --- |
| 선행 차단 | [EcoMassReplicator.cpp](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp)의 71, 89, 125행에 미완성 lambda 선언이 남고 뒤에 다른 선언이 이어진다. 명시적 capture 목록도 사용하는 지역 변수와 맞지 않는다. HEAD와 작업 트리 모두 동일 | 현재 Source를 빌드 가능한 기준선으로 사용할 수 없음 | 중복 선언 제거·capture 정리 후 직접 UBT 및 복제 회귀. 실제 compiler 로그는 아직 없음 |
| 높음 | [Creature Reconcile](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.cpp)의 별도 대사·기아·죽음 처리와 [Box Lifecycle](../../Source/AdaptiveEcosystem/Mass/EcoMassLifecycleSubsystem.cpp)의 공통 Survival/RecordDeaths 경로가 공존 | 개체 생성 경로에 따라 죽음 원인·기아 유예·집계·재시도 규칙이 달라질 수 있음 | 공통 clock/생존/결과 commit에 종별 adapter 연결. 현재 동일 개체가 이중 처리된다는 뜻은 아님 |
| 높음 | Creature의 대사 pass는 살아 있는 `Herbivore`만 처리한다. [EcoSurvivalTypes.h](../../Source/AdaptiveEcosystem/Core/EcoSurvivalTypes.h)의 공통 사망 원인은 None/Starvation/ExternalDamage이며 Creature는 별도 `bPredated`로 지역 피식 기록을 갱신 | 초식동물 고갈과 포식자 생존·먹이 획득·개체군 변화가 같은 생태 계약으로 닫혀 있지 않음 | Predator/Prey 사건과 에너지 규칙을 공통 계약에 추가. 늑대 규칙을 사슴 값으로 대체하지 않음 |
| 높음 | [복제 ModifyEntity](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp)는 이동 gate 전에 `SetPresentation` 변경을 dirty 처리하지만 이 변경만으로 sequence를 올리지 않는다. [Client Receive](../../Source/AdaptiveEcosystem/Mass/EcoMassPresentationFragments.h)는 같은 sequence를 거부하고 [Bubble](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.cpp)는 Receive 실패 시 presentation 반영 전에 반환 | HP/identity/reset/Transform 변경 없이 velocity·행동 flag만 달라지면 전송된 변경이 Client에 반영되지 않는 경로가 있음 | 통일된 payload revision 또는 이동/표현별 revision과 수신 계약. 정적 경로 분석이며 네트워크 실행 재현 전 |
| 높음 | [ConnectionBudget](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassNetworkSettings.h)은 Future M4.6 설정. Source 검색상 Trait의 유효성 검사 외 실제 MaxRelevantAgents/MaxActorRepresentations/MaxAddsPerUpdate 집행 없음 | 여러 종·Template의 동시 진입 시 연결별 CPU·메모리·생성 burst를 제한하지 못함 | 연결 전체 relevance/Add 예산과 화면별 Actor 예산을 실제 적용 |
| 높음 | [SyncVisuals](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.cpp)는 대상마다 Actor를 생성/삭제하고 Client 위치에 `VInterpTo` 적용. Previous/Current 서버 표본과 reset revision을 동물 표시에서 소비하지 않음 | 지연에 따른 따라가기 오차, 작은 teleport의 잘못된 평활화, relevance 경계의 Actor 생성 spike 가능 | 서버 표본 timeline 보간·reset 전달·표현 LOD·풀링·히스테리시스 |
| 높음 | [M4 검증 기록](../Roadmap/M4/M4_VALIDATION_REPORT.md)에 M4.2 이후 다중 Client·packet 간격·CPU/Network trace가 미실행/미측정으로 남음. 동물 통합 검증은 별도 시점/조건 | 원하는 N/Client 수에서 서버 tick과 Client frame을 지킬지 판정 불가 | 현재 commit의 동물 경로로 기준선 재측정. Box/NullRHI 결과와 구분 |
| 중간~높음 | Creature feeding 결과마다 Owned 전체 재검색, Summary는 지역마다 Owned 순회. [PredatorPerception](../../Source/AdaptiveEcosystem/AI/Social/Senses/EcoPredatorPerception.cpp)은 관찰자마다 살아 있는 prey 목록 순회 | 최악 결과 매칭 O(F×N), 집계 O(R×N), 표적 후보 O(P×N). 밀집·다수 종에서 CPU 비용 증가 | step 수명의 ID lookup, 단일 집계 pass, 공간 broad phase. 병목 순위·배율은 미측정 |
| 중간~높음 | Box는 최대 8 catch-up pass를 두지만 Creature는 약 1초 이상 누적 Elapsed를 한 번에 대사·섭식 처리. Policy는 LastPolicyStep 기반 프레임 카운터 | 긴 frame·저 FPS·LOD 변경에서 의사결정 주기와 사건 순서가 달라질 수 있음 | 논리 시계·실행 주기·catch-up 부채·최대 처리량 계약. Policy 시간 변경은 RL 담당과 parity 검토 |
| 지속 월드에서 높음 | 별도 격자 predation SaveGame은 존재하지만 권위 지역 Food/Population·개체 Vitals/Travel·ID 발급·spawn cursor 전체의 저장/복원 구현은 검색에서 확인되지 않음 | 재시작 후 생태 결과 소실, ID 재사용, 중복 웨이브/사건 위험 | 버전 있는 완료 step snapshot과 복원·중복 방지 계약 |
| 지속/대규모 월드에서 높음 | [World Subsystem](../../Source/AdaptiveEcosystem/World/EcologyWorldSubsystem.cpp)은 로드된 Region Actor로 공간/환경 snapshot을 만든다. Creature에는 habitat streaming source와 로드 대기가 있고 EndPlay는 Owned를 파괴 | 현재 habitat 로딩 전략의 메모리 비용과 coordinator/지역 unload 때의 논리 지속성이 불명확 | 서버 논리 데이터 수명과 공간 Actor 수명을 분리하고 지원하는 unload 정책을 명시 |

## 3. 첫 구현 묶음 — 기준선과 복제 정확성

기존 [P1~P6](README.md) 앞에 다음 선행 작업을 둔다. 표에 없는 새 타입 이름은 제안이며 구현 완료를 뜻하지 않는다.

1. `EcoMassReplicator.cpp`의 중복/미완성 선언과 capture를 정리한다. `CacheViews`, `AddEntity`, `ModifyEntity`가 사용하는 view·handler·설정을 모두 올바른 수명 안에서 참조하도록 만든다.
2. 복제 payload의 갱신 단위를 정한다. 첫 선택지는 accepted payload 변경마다 sequence를 한 번 올리는 방식이다. 표현만 갱신할 때 기존 위치의 시각을 새 위치 표본처럼 덮어쓰지 않도록 이동 표본 시간과 표현 revision의 의미를 분리한다. 대안은 movement/presentation revision을 별도로 수신하는 계약이다.
3. `SetPresentation` 결과를 gate와 commit 판단에 포함한다. HP/Energy의 공통 byte와 Creature byte는 현재 round/truncate 경로가 다르므로 하나의 변환 규칙과 데이터 소유자를 정하고 중복 전송 필요성을 평가한다.
4. Creature 표시에서 `FEcoClientPresentationFragment`의 수신 표본/reset을 읽는다. 로컬 프레임마다 증가시키는 Binding.Sequence를 서버 sequence의 대체물로 사용하지 않는다.
5. 의미 있는 회귀는 **HP·위치 고정 + velocity만 변경**, **행동 flag만 변경**, **같은 sequence 중복**, **이전 sequence**, **작은 teleport + reset revision**, **relevance Remove→동일 ID 재진입**이다. 특히 잘못된 stale 거부와 잘못된 재적용을 함께 검사한다.

완료 기준은 직접 UBT 성공, 위 회귀의 수신 결과 일치, Dedicated/Client 실연결 확인이다. 수정 전에 실행 중 UBT/dotnet/Editor/Live Coding/MSBuild/ShaderCompileWorker를 확인하고 겹쳐 빌드하거나 기존 실행을 중단하지 않는다. Editor 빌드 성공과 실제 Server/Client 패키지 빌드·cook 성공도 구분한다.

## 4. 공통 생태계 실행 경계 — P1 구체화

기존 Box의 검증된 자원·생존 계약을 재사용하되, Creature의 설정·행동 의미를 명시적으로 adapter에 담는다. 동일 개체의 이동 writer는 하나로 유지하고 Bootstrap 혼용 가드를 먼저 제거하지 않는다.

권위 실행 순서는 다음의 의존성을 만족하도록 확정한다. 섭식과 기아 피해 중 어느 사건이 먼저인지도 계약에 넣는다. 이 순서는 새 기본 동작을 확정한 것이 아니며 기존 두 경로의 차이를 비교해 결정한다.

```text
권위 clock / 완료 step 경계
→ 유효 개체·지역·종 입력 snapshot
→ 종별 행동·섭식 요청 / 검증된 피식·외부 피해 요청
→ 자원 배분과 Vitals 결과 적용 / 단일 Death commit
→ 예약·pending feeding·Travel 종료 정리 / 이주 commit
→ 동일 완료 step의 지역·종별 집계와 요약
→ 복제 표본 / 표현 전용 소비
```

- 사망 계약에는 WorldEpoch, StepId, StableAgentId, Cause, EventTime, 필요한 경우 PredatorStableAgentId를 포함한다. 기존 `FEcoDeathOutcome`을 확장할지 별도 검증된 Predation outcome을 결합할지 결정한다. 외부 피해·기아를 포식으로 추정하지 않는다.
- feeding은 기존 `FEcoFeedRequest/Result`의 Epoch/Step·지역·실제 GrantedAmount를 보존한다. 요청을 제출했을 때의 결과를 ID lookup으로 찾아 적용하되 handle 유효성, ID, 살아 있음, 같은 step, 이전 적용 여부를 재검증한다.
- Creature 현재의 늑대 대사 제외를 지원 규칙으로 둘지 공통 생존으로 전환할지 기록한다. 포식 성공→포식자 에너지 획득→다음 행동의 연결도 별도 설정으로 정의한다.
- Population은 지역 총계와 지역×종 집계를 함께 제공한다. 전체 Population만으로 사슴 감소와 늑대 증가의 의미를 평가하지 않는다.
- 새 공통 실행기에 연결한 Entity만 기존 Creature 대사/Death pass에서 제외한다. 단계적 전환 중에도 같은 ID의 이중 소모·이중 commit을 막는다.
- 모든 runtime 오류를 `Ready=false`만으로 종료하는 현재 Creature 방식에서, 실패 종류·완료 watermark·재시도 가능 여부를 진단할 수 있도록 한다. 변경 도중 일부 자원만 commit된 상태를 자동 재시도로 더 악화시키지 않도록 결과 적용 경계를 검증한다.

완료 불변 조건:

```text
Food_end = Food_start + 실제 공급 + 실제 재생 - Σ 실제 지급량 - 명시적 손실
Alive_end = Alive_start + 성공 Births - 단일 Deaths - 명시적 논리 Despawns
지역 Population 변화에는 이주 입출을 추가하되 세계 합계에서 이주는 상쇄
같은 Epoch의 StableAgentId 중복 = 0
같은 사건의 Food/Energy/Death/Predation 중복 반영 = 0
```

Clamp 때문에 식이 깨지는 경우 overflow/spillage를 명시적 손실로 기록한다. 시각 표현 제거를 논리 Despawn/Death에 포함하지 않는다.

## 5. 성능 목표와 측정 — P2/P3/P5 구체화

먼저 제품 프로필에 TargetHardware, ServerTickHz, ClientFPS, MaxLogicalAgents, MaxClients, MaxRelevantAgentsPerClient, ActorBudget, 연결별 대역폭, 정상/최악 밀도, SessionDuration을 기록한다. 현재 Creature 초기화는 512 상한이 있다. 1000/5000/10000은 향후 시험 목표이며 지원·달성 수치가 아니다.

30 Hz 서버를 선택하면 전체 frame 시간은 약 33.3ms, 60 FPS Client는 약 16.7ms다. 이 전체 시간을 생태계가 독점할 수 없으므로 측정 후 생태계·복제·표현별 예산을 배정한다. p50/p95/p99와 최대값, hitch 횟수, 측정 구간을 함께 기록한다. 제안 수치를 현재 측정 성과로 적지 않는다.

Riot의 [VALORANT 서버 성능 글](https://www.riotgames.com/en/news/valorants-128-tick-servers)은 세부 시스템 계측·예산과 실제 호스팅 부하 측정의 필요성을 설명한다. 여기서 가져올 것은 측정 방식이며 128 tick이나 해당 게임의 최적화 수치를 생태계에 적용하는 것이 아니다. [League 실사용 성능 글](https://www.riotgames.com/en/news/profiling-real-world-performance-league)은 재현 자료와 평균 FPS만으로 원인을 판단하는 한계를 설명한다.

구현할 계측 구간은 Survival, Feeding request/resolve/apply, Migration, Aggregation, Policy, Senses, Social, Movement, Replication collect/serialize, Client sample/visual update, Actor create/recycle이다. 후보 수, trace 수, 실제 이번 pass 실행 수, dirty 사유, packet 크기, Client Actor/mesh 수, backlog와 메모리를 함께 수집한다. Debug Draw와 상세 로그는 성능 캡처에서 분리한다.

최적화 순서:

1. step 수명 ID→handle lookup으로 O(F×N) 결과 매칭 제거. RegionRuntimeIndex/SpeciesRuntimeIndex별 누산으로 집계 단일 pass.
2. 감각 담당과 기존 grid 기반 후보 선별. cell 경계·이주·음수 좌표·고밀도에서 brute-force 기준과 표적 결과 비교.
3. ReadOnly 입력 snapshot→순수 계산→GameThread commit을 나눈 뒤 확인된 고비용 계산만 worker로 이동. UObject·LOS·자원·예약 변경을 실행 flag만 바꿔 worker에서 호출하지 않는다. [Epic MassEntity](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-entity-in-unreal-engine)의 Chunk/Processor 및 command buffer 경계와 대조한다.
4. 프레임 카운터 정책과 감각 갱신을 논리 시각 스케줄로 바꾸는 것은 별도 행동 변경이다. RL 담당과 Python step/관측·행동 parity를 확인하고 전후 재평가한다.
5. 긴 frame의 누락 시간은 backlog로 관측하고 한 frame의 catch-up work에 상한을 둔다. 부채를 조용히 삭제하지 않으며 오래된 상태를 어디까지 허용할지 정한다. 모든 동물을 한꺼번에 갱신하는 동기화 spike도 분산한다.

## 6. 연결별 복제와 화면 비용 — P4 구체화

[Epic MassGameplay](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-gameplay-in-unreal-engine)는 Simulation·Replication·Representation LOD를 구분하고 연결별 relevance 및 Actor pooling을 설명한다. 프로젝트에서도 세 예산을 별도로 집행한다. 공식 문서의 Mass Replication experimental 설명에는 UE 5.1 기준 문구가 남아 있으므로 이를 UE 5.8 안정성 판정으로 단정하지 않는다.

- 연결 전체의 종/Template/Viewer 합산 relevance 예산을 적용한다. 중요한 상호작용·근거리 위협·필수 상태를 우선하고 거리/중요도/StableAgentId로 안정적인 동률 규칙을 둔다. 예산 때문에 필수 대상을 생략해야 하는 경우 지원 제한을 명시한다.
- Add queue에는 생성량/CPU 비용 상한, 취소, Remove 우선 처리, 접속 세대 reset, 대기 시간 상한을 둔다. 전환 히스테리시스와 queue 적체 경고를 추가한다.
- `SetPresentation`이 이동 gate 밖에서 dirty되는 경로와 HP/Energy 양자화 변화로 gate를 우회하는 경로를 각각 측정한다. Energy UI 갱신을 매번 중요 생명주기 사건과 같은 우선순위로 취급해야 하는지 재설계한다.
- Client 보간은 서버 표본 시각을 Client 표시 시계로 매핑하고, `RenderTime = estimated server sample time - interpolation delay`에서 두 표본을 읽는다. 표본 부족 시 제한된 extrapolation/hold를 정하고 첫 Add/reset/재진입에는 snap한다. 생태 WorldClock과 실제 전송 표본 시계를 혼동하지 않는다.
- Actor 수는 relevance 수와 별도로 제한하고 Listen Host/Standalone도 적용한다. 풀 반환 시 identity, 표본 buffer, 애니메이션, Notify gate, 오디오 상태를 초기화한다. 중·원거리 skeletal 갱신 절감이나 ISM/VAT는 에셋 비용과 표현 품질을 검증한 뒤 선택한다.
- Dead 잔류 2초의 best-effort 전송은 모든 Client가 사망 연출을 봤다는 보장이 아니다. 보상·퀘스트·플레이어가 유발한 사망 확인은 별도의 권위 결과/확인 계약으로 연결한다. 모든 야생동물 사망에 무조건 ACK를 도입하지 않는다.

[Networking Insights](https://dev.epicgames.com/documentation/en-us/unreal-engine/networking-insights-in-unreal-engine)로 연결별 packet과 property 비용을 확인한다. dirty 횟수는 실제 packet 횟수가 아니며 이 도구의 packet 크기는 압축 전 수치이므로 실제 wire bandwidth와 구분한다. 기존 Mass transport를 평가하기 전에 Replication Graph/Iris로 교체부터 하지 않는다.

## 7. 원거리·저장·복원 — P6와 추가 과제

Simulation LOD 첫 구현은 개체 ID/Fragment를 유지한 채 비싼 계산의 주기를 줄이는 범위로 제한한다. 대사·자원 지급·기아·예약 lease·이주 도착의 시간 의미는 유지한다. 상세 근사와 full-rate의 결과는 완전히 같다고 가정하지 않고 사건 지연과 행동 오차를 별도 평가한다.

원거리 지역을 aggregate로 바꾸는 것은 다음 단계다. 개체를 제거했다가 다시 만드는 방식에는 종별 개체수·에너지 분포·ID 보존/재구성, 지역 입출, 중복 spawn 방지 규칙이 필요하다. 화면 밖이라는 이유로 Population을 줄이지 않는다.

[Epic World Partition](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine)의 streaming source는 셀 로딩을 관리한다. 생태 상태 지속성을 자동 제공하는 근거로 쓰지 않는다. 현재 habitat 로딩은 충돌 공급에 필요할 수 있으므로 제거부터 하지 않고 로드 범위·메모리 비용·unload 대응을 측정한다. server의 collision/input unavailable 상태를 정상 정지/우회/지원 제한 중 무엇으로 다룰지 정의한다.

지속 월드 또는 저장 가능한 싱글플레이를 목표로 하면 새 버전 snapshot에 다음을 포함한다:

| 저장 항목 | 복원 원칙 |
| --- | --- |
| SaveSchemaVersion, ConfigVersion, PolicyVersion, 완료 Step/시각, RNG 상태 | 다른 버전은 migration 또는 명시적 거부. 미완료 transaction은 저장하지 않음 |
| 지역 Food·Predation·생태 파라미터·spawn cursor | 동일 웨이브/공급 사건 재실행 방지 |
| StableAgentId·SpeciesId·RegionId·Vitals·Travel·death 상태 | 새 runtime index/handle을 생성하고 영속 ID로 다시 연결 |
| 다음 ID/사건 watermark | 살아 있는 ID·사망 기록과 충돌 방지 |
| Herd/예약의 복원 또는 재계산 정책 | Social 담당과 lease 시간 기준 및 slot 재검증 합의 |

`FMassEntityHandle`과 UObject 주소를 저장하지 않는다. runtime epoch는 복원한 ID의 지속성과 별도로 오래된 연결/요청을 거부하도록 정의한다. 완료 step에서 snapshot을 복사하고 비동기 저장, 실패 처리, 이전 정상 저장본 복원, 버전 호환 검사를 구현한다. [Epic SaveGame](https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine)은 비동기 저장을 안내하지만 게임별 복원 정확성은 프로젝트가 정의해야 한다. 세션마다 초기화하는 게임이면 세션 간 저장을 제외할 수 있고 대신 재접속/reset 정확성을 완료 기준으로 삼는다.

## 8. 연구의 적용 가치를 입증할 비교

정확성 통과와 학습 정책의 유용성은 다른 주장이다. wonkii는 동일 환경의 자원·생존·이주 계측을 제공하고 정책/Social 담당과 비교 조건을 합의한다.

- Utility + 공통 생태계와 PPO + 공통 생태계를 같은 환경·종 비율·공급·플레이어 압력에서 비교한다.
- Social ON/OFF, full-rate/LOD, 표현 ON/OFF를 독립 비교한다. 동시에 여러 기능을 바꿔 원인을 추정하지 않는다.
- 여러 seed에서 생존 시간, 종별 개체수 추이, 실제 Food 소비/회복, 이주 성공/정체, 포식 성공, 원거리 재방문 일관성, CPU·bytes·메모리를 기록한다.
- 학습에 없던 고갈·밀집·통로 폐쇄·다중 플레이어 압력에도 평가한다. PPO가 모든 상황에서 우수하다는 가정을 두지 않는다.
- 멸종이 의도된 결과인지 콘텐츠 중단인지 제품 규칙으로 정한다. 현재 재생 없는 Box 테스트의 전멸을 버그로 단정하거나 검증 편의를 위해 자동 회복을 숨겨 넣지 않는다.
- gameplay 프로필에 공급·재생·spawn·최소/최대 개체수·회복 정책을 명시하고 연구 비교 프로필과 구분해 결과에 설정 버전을 남긴다. 현재 존재하는 수동 공급 기능은 회복 시나리오 검증에 활용한다.

## 9. 검증과 완료 게이트

아래 숫자는 제안 시험 조건이며 실행 결과가 아니다. 지원 제품 범위를 확정하면서 수정한다.

| 단계 | 시험 | 완료 증거 |
| --- | --- | --- |
| A | 현재 HEAD 복제 코드 복구, 직접 UBT, 표본/표현 revision 회귀 | 빌드 로그와 Client 수신 결과 |
| B | 동일 개체의 섭식·기아·피식·외부 피해·이주·예약 정리 | Food 보존, 단일 Death, 종별 Population, stale 결과 거부 |
| C | 현재 유효 범위 내 N=32/128/512, 분산/밀집, Client=1/2/4 | 실제 spawn 수, 서버/Client p50/p95/p99/max, packet·Actor·메모리 |
| D | 동시 relevance 진입·teleport·rejoin·Client 저 FPS | budget 준수, Add backlog 회복, ghost/중복 bind/reset 오류 없음 |
| E | 정상/중간 지연·손실 및 극단 조건 | 설정 방향과 실측 RTT를 기록. 예: 500ms RTT/10% 손실은 stress 조건 |
| F | 30~60분 고갈/공급/반복 접속, 이후 목표 세션 길이 | backlog·메모리·ID·예약 누수·장기 집계 불일치 없음 |
| G | 원거리 이탈/재방문, 필요 시 저장→프로세스 재시작→복원 | 논리 지속, 자원/ID/Travel 보존, 중복 웨이브 없음 |
| H | 실제 Server/Client package/cook와 최소 사양 | 에셋·Template·실제 배포 환경의 비용/정확성 |

[Epic Network Emulation](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-network-emulation-in-unreal-engine)은 로컬/LAN만으로 지연·손실 문제를 검증할 수 없다고 설명하고 500ms round-trip ping/10% 이상 손실의 극단 시험을 예로 든다. 이는 그 조건에서 완벽한 애니메이션을 보장하라는 요구가 아니라 stale 상태·ghost·오류 회복을 확인하는 시험이다.

우선 실행 단위는 **A → P2 현 상태 캡처 → B/P1 통합 → 복제·표현 예산 → 계측 상위 병목 제거 → 시간/병렬·LOD → 저장/장시간 제품 게이트**다. 저장이 제품 필수라면 공통 생명주기 계약 단계에서 함께 설계한다. 특정 최적화 수치를 약속하거나 모든 기능을 한 번에 바꾸지 않는다.

이번 문서의 검증: 참조 Source와 HEAD 대조, 역할·기존 계획의 범위 확인, 공식/개발사 원문 열람, 링크 대상과 변경 diff 확인. 신규 런타임 통과·성능 달성을 주장하지 않는다.
