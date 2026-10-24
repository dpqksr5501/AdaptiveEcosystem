# 생태계 서버·네트워킹 담당 AI 작업 가이드

작성일: **2026-10-24** / 구현 기준: **`d095948`** / UE5.8. [공통 작업 안내](../Team/ECOSYSTEM_AI_COLLABORATION_20261024.md)와 루트 AGENTS.md를 먼저 읽는다. 이 문서는 현재 Source의 소유권과 후속 작업 acceptance를 함께 설명한다. 제안한 운영 기능까지 구현됐다는 뜻은 아니다.

## 1. 이번 통합으로 서버 담당자가 받는 것

실제 통합 맵은 `/Game/JYU/Maps/LV_JYU_Ecosystem`이다. 서버/Standalone에 soil/life를 opt-in했고 Native Step→완료 GT 경계→M4 장부를 연결했다. 현재 기본 SocialControl=0, 기존 V1/v3 계약·모델과 다른 맵의 기본 옵션은 보존한다.

기존 [Mass 권위 계약](MASS_NETWORK_AUTHORITY_CONTRACT.md)은 유효하다. 그 문서의 Steam Listen Session 구조와 이번 Dedicated world 로컬 검증은 서로 다른 검증 범위다. 현재 테스트 서버는 `UnrealEditor-Cmd.exe ... -server`로 실행한 Dedicated world이며, Linux 배포·독립 Server target 패키지·상용 운영·Steam 초대/인증의 완료 증거는 아니다.

## 2. 먼저 확인할 Source 지도

아래 경로는 `AdaptiveEcosystem/Source/AdaptiveEcosystem/` 기준이다.

| 영역 | 실제 파일/타입 | 확인할 일 |
|---|---|---|
| World 역할·기동 | `Creature/Runtime/EcoCreatureIntegrationSpawner.*`, `EcoCreatureSetupValidation.cpp`, `EcoCreatureNetworkTrait.*` | Authority/Client 분기, backend/flag, template·EntityConfig 일치 |
| Native 실행 | `AI/Policy/EcoPolicyV3IntegratedProcessors.cpp`, `EcoWorldV3.h` | GT gather와 단일 Native writer, Client 실행 금지 |
| 완료·수명 | `EcoCreatureLifecycle.cpp`, `EcoCreatureNaturalBirth.cpp`, `EcoCreatureCarcass.cpp`, `EcoCreaturePlayerOutcomes.cpp` | 실제 완료 결과와 중복 방지, 생성/삭제 시점 |
| 장부 | `Ecology/EcologySimulationSubsystem.*`, `EcologySpatialFood.cpp` | Amount·소비/성장/손실·인구/사망/이주 sequence/receipt |
| Bubble payload | `Network/Mass/EcoMassReplicationTypes.h::FReplicatedEcoMassAgent` | identity·position·vitals/life·Activity·BodyScale·revision |
| 송신/수신 | `EcoMassReplicator.cpp`, `EcoMassClientBubble.cpp` | 중요 dirty 갱신·수신 초기화·순서·relevance 수명 |
| 표현 | `EcoCreaturePresentation.cpp`, `Creature/Representation/*` | 수신 상태만 소비하는 Actor·애니메이션/오디오·크기 |
| 식생 DTO | `World/EcoVegetationField.*` | replicated Cells/MovementMarks, 서버 논리와 Client ISM 분리 |
| 환경 요약 | 기존 `Network/EcoGameState.*`, `EcoV3WeatherPresenter.*` | Client 날씨 수신 표현, Subsystem 복제 금지 |
| 저장/운영 | `EcoEcosystemCheckpoint.cpp`, `EcoEcosystemArchive.h`, `EcoPopulationRecovery.cpp` | 완료 경계·same-build·재결합·거절 비변경 |
| 플레이어 요청 | `Creature/Player/EcoPlayerEcologyComponent.*` | owner RPC와 실제 서버 검증 |

`EcoCreature*` 새 cpp들은 기존 spawner의 partial 구현이다. 같은 이름의 두 번째 EcologyManager를 만들지 않는다. [Mass 순서](../Mass/MASS_PROCESSOR_ORDER.md)를 바꾸면 그 이유와 영향을 별도로 검증한다.

## 3. Client에 무엇을 보내고 무엇을 남길까

| 데이터 | 현재 소비 경로 | 지켜야 할 의미 |
|---|---|---|
| Region Summary | 기존 GameState/요약 transport | UI용 요약이며 권위 Food 잔고가 아님 |
| ID·위치/yaw·속도·시각 상태 | 기존 Mass Bubble→수신 proxy/Actor | relevance에 따른 표현이며 두 번째 생물 개체가 아님 |
| Activity·focus·BodyScale | Bubble presentation→Actor/ABP | 받은 행동/크기만 표현, Client 성장/유전 계산 금지 |
| 식생 셀 | `AEcoVegetationField::Cells`→ISM | RegionId+Cell이 논리 표본 ID. food/moisture/stress/plant는 양자화된 시각 DTO |
| 이동 마크 | Field의 `MovementMarks` | 제한된 흔적 표현. 원래 모든 논리 흔적/정확한 발 본 위치가 아님 |
| Observation·Raw Request·유전·개인 기억·부모·자원 거래 | 기본적으로 서버 내부 | Inspector/학습 진단에서 읽을 수 있다는 이유로 전체 복제하지 않음 |

현재 맵은 지역당900 논리 셀 중 시각 최대256개를 표본으로 보내고 Field는1Hz로 갱신한다. DTO에 없는 셀을 food0으로 해석하지 않는다. 같은 Field를 Client별 논리 grid로 재생성하거나 Client에서 재생률을 적분하지 않는다.

서버/Standalone의 `GetAuthorityAgentIds`는 권위 개체를 반환한다. Client는 그 목록·Native step/contexts·이주 Subsystem이0이어야 한다. **Client의 Mass proxy 총수가0이어야 한다는 뜻은 아니다.** proxy·Actor·수신 식생은 있어야 화면이 보인다.

## 4. ID·시간·순서·reset을 섞지 않기

| 값 | 실제 수명/의미 | 잘못된 사용 |
|---|---|---|
| StableAgentId | 논리 생애와 저장의 ID | Actor pointer/Entity index로 대체 |
| RegionId/SpeciesId | 영속 지리·종 식별 | runtime compact index를 저장·전송 계약으로 사용 |
| FMassNetworkID | 현재 transport proxy 식별 | 장기 혈통·저장 ID |
| World epoch | 권위 실행/거래 세대 | 같은 ID이면 다른 서버 세션의 상태도 수락 |
| SampleSequence | Bubble entry별 uint32 순서 | 전 서버 생애주기의 전역 sequence |
| VisualRevision | 시각 상태 갱신 | 자연 출생/정책 세대 번호 |
| MovementDiscontinuityRevision | teleport/reset 경계 | 일반 이동 중 임의 증가 또는 무시 |
| ServerSampleRealTimeSeconds | 서버 GetRealTimeSeconds | 생태 WorldClock·Native step·Client wall time과 혼용 |

현재 `FEcoRepresentationSnapshot`에는 world epoch 필드가 없다. “epoch가 모든 visual payload에 이미 들어 있다”고 가정하지 않는다. 새 세션/재접속/호스트 이동 프로토콜이 필요하면 기존 연결 수명·reset과 별도 handshake/version 계약부터 설계한다. 현재 혼합 빌드/구버전 payload 접속은 지원 완료가 아니다.

기존 수신 버퍼는 첫 Add/ID 변경/reset에서 Previous=Current로 초기화하고 동일/이전 Sequence를 거절한다. uint32 비교는 연속 차이가2^31 미만인 전제가 있다. **버퍼 존재와 동물 Actor의 timeline 보간·연결 전체 예산 집행 완료는 별개**다. [M4.1](../Roadmap/M4/M4_1_DATA_CONTRACT.md), [M4.2](../Roadmap/M4/M4_2_REPLICATION_INTERVAL.md), [P4 후속 계획](../Integration/P4_CREATURE_REPLICATION_AND_REPRESENTATION.md)의 Source와 현재 동물 소비자를 대조한다.

BodyScale은 `byte / 128`이다. 기본128은1.0이며 서버가 genome/growth로 결정한다. 테스트의2/128 허용은 전송 지연을 포함한 장면 대조 기준이지 양자화 자체의 최대 오차가 아니다. 죽은 어린 개체는 사망 시각의 크기로 고정한다. HP byte0만 보고 사망을 확정하지 않고 명시적 life 상태를 사용한다.

## 5. 생명주기 사건은 전송과 별개다

자연 출생은 실제 부모/영양/자리/예약을 통과한 뒤 인구에 반영된다. 새 Actor나 proxy 생성이 Birth가 아니다. relevance Remove는 Death가 아니며, 기존 개체의 다른 Client 첫 Add도 새 출생이 아니다.

현재 life 세계의 사체 보존은22초이며 사체 영양 lease는20초다. 서버의 사망 receipt는 한 번만 확정한다. 표현 제거 시점이 다르다고 Client/Actor가 HP를 다시 깎거나 사체 보상을 다시 지급하지 않는다. 관심 밖에서 죽은 개체의 완전한 사건 전달/ACK가 필요하면 별도 기능으로 정의한다.

이주는 목적지 선택, 지역 경계 인계, 경로 끝 정착을 분리한다. 지역 인계는 기존 M4 receipt와 실제 Native context 이전을 소비한다. Authoritative Transform의 순간 변화를 Client가 “튀었다”고 보정하더라도 서버의 이주를 되돌리지 않는다. 실패 시 복귀 한 번과 Abandoned/stranded 정리를 보존한다.

## 6. 플레이어 요청·운영 API의 신뢰 경계

현재 F 입력은 `TryStrike()`→`ServerTryStrike()` owner RPC→서버 큐다. Client가 target/position/damage를 넘기지 않는다. 실제 서버 몸·거리300cm·높이 차150cm·방향/LOS·1초 cooldown·3초 기한·큐32를 확인하고 완료 경계에서 HP−30을 적용한다. 여러 Client 시험에서는 소유권 없는 RPC, spam, 지연 입력, 사망한 대상, 잘못된 World/region을 negative case로 추가한다. Client의 “명중했다”는 연출은 권위 outcome과 구분한다.

`SaveEcosystem`, `LoadEcosystem`, `QueuePopulationRecovery`와 콘솔 명령은 일반 Client용 임의 RPC로 감싸지 않는다. 후속 운영 UI/서비스라면 관리자 인증·권한·감사 로그·재시도/중복 키·차단 정책이 필요하다. 이는 **후속 요구사항**이며 현재 생태계가 완전한 운영 보안 서비스를 제공한다는 의미가 아니다. 실제 피해 원인/운영 보충을 자연 포식·자연 출생·loot/퀘스트 보상으로 중복 분류하지 않는다.

## 7. 저장·서버 재시작을 다룰 때

- 현재 파일은 `Saved/Ecosystem/<slot>.eco`, schema1+길이/checksum+runtime image hash·맵·모델 검사다. same-build startup restore이며 live rollback·cross-build·Editor→package 변환은 미지원이다.
- Git SHA 일치만으로 바이너리 hash 일치를 보장하지 않는다. 팀원이 clone해서 빌드한 뒤 기존 `.eco`가 거절돼도 데이터를 지우거나 새 세계로 자동 초기화하지 않는다.
- 실제 commit 경계를 저장한다. pending spawn·미채택 개체·미확정 Native 죽음은 다음 경계를 기다린다. resource receipt를 저장 후 다시 실행하지 않는다.
- 새 Entity를 준비·검증한 뒤 기존 세계를 교체한다. 실패 시 이전 세계/allocator/counter를 보존한다. 현재 runtime index/Actor/ISM ID를 그대로 살리지 않는다.
- 저장 cover 순서는 유지하되 새 World의 실제 은신처 geometry/높이/등록에 재결합한다. 등록 순서와 영속 identity를 혼동하지 않는다.
- 플레이어 대기 입력·일시 Shelter lease·미완료 운영 요청은 취소한다. 출생 대기와 저장된 운영 cooldown 등 지속 상태의 정책은 기존 codec를 따른다.
- 살아 있는 인구 cap과 저장에 남는 사체 행 cap을 구분한다. death retention을 이유로 살아 있는 개체를 더 생성하지 않는다.

프로덕션 저장 서비스 확장은 먼저 versioned schema, 안전한 파일 교체/백업·장애 복구, 명시적 migration 도구, 빌드/모델 롤백, ID namespace/world epoch, checkpoint와 외부 DB/보상 transaction의 원자성·멱등성을 결정한다. 현재 파일 저장을 DB·자동 저장·백업·분산 승계까지 완료한 것으로 기록하지 않는다.

## 8. 우선 개선할 작업

| 우선순위 | 작은 작업 단위 | 완료 기준 |
|---|---|---|
| P0 | 기준 SHA·LFS·EntityConfig·World 역할 고정 | 동일 구성에서 기존 검증 재현, Client authority/Native0 |
| P1 | 접속/지역 전환 hitch의 원인 분리 | streaming·Actor Add·애니메이션 초기화·복제 수신·QA 기록 비용의 시간 구간 분리 |
| P1 | 연결별 예산/수신 timeline Source 감사 | 설정 존재와 실제 집행을 구분, 공유 proxy 상태로 A/B의 LOD를 섞지 않음 |
| P2 | 확인된 병목 하나 개선 | 같은 baseline/candidate로 p95와 max·Actor/Add 수·bytes 비교, 중요 사건 누락0 |
| P2 | 느린/손실 연결과 재진입 검증 | 중복 bind·ghost·stale 표본·잘못된 reset 재현/해결 |
| P3 | 저장/운영 또는 배포 확장 | 별도 계약·인증/장애/호환 negative test와 새 배포 증거 |

한 번에 엔진 replication·자체 transport·새 manager·새 보간을 모두 교체하지 않는다. Actor pooling을 추가하면 ID/binding/mesh/ABP/Activity/오디오/BodyScale/보간/죽음 상태를 reset하고, 대기 Add의 취소·죽음·relevance 이탈도 처리한다. 논리 거래를 생략하는 방식으로 CPU를 줄이지 않는다.

`mass.UseProcessingQueue=0`은 기존 UE5.8 MassReplication 복사 query 호환 가드다. 이 설정의 근거를 읽지 않고 “최적화”로 켜지 않는다. 서버 Native 병렬화도 GT UObject/trace/Mass 구조 변경을 worker로 단순 이동해서 해결하지 않는다.

## 9. 실제 검증 순서

다음 명령은 **프로젝트 폴더 `AdaptiveEcosystem/`에서**, 모든 engine/build 프로세스가 정상 종료된 뒤 실행한다. C++ 변경이 없으면 문서 작업에 새 빌드를 요구하지 않는다. 아래 실행은 새 검증 기록을 만드는 예시다.

```powershell
./Tools/Integration/build_integration_milestone.ps1 -Milestone Final
./Tools/Editor/run_ecosystem_validation.ps1 -Check automation
./Tools/Editor/run_ecosystem_validation.ps1 -Check assets
./Tools/Editor/test_vegetation_network.ps1 -Map /Game/JYU/Maps/LV_JYU_Ecosystem -AuthoredWeather -AuditFolder MyNetworkRun_20261024 -OverlapClients -ClientAAt 10 -ClientBAt 60 -Duration 110 -ExitAfter 160
./Tools/Editor/run_ecosystem_life.ps1 -Mode save -Name MySave -Slot MyRestart -Seed 23 -Duration 115 -SaveAt 95
./Tools/Editor/run_ecosystem_life.ps1 -Mode load -Name MyLoad -Slot MyRestart -Seed 23 -Duration 25
./Tools/Editor/package_ecosystem.ps1
./Tools/Editor/test_ecosystem_package.ps1
```

MyRestart는 위 새 서버에서 생성한 파일이다. 새 빌드를 사이에 끼우지 않는다. helper는 기존 프로세스를 강제 종료하지 않고 busy면 거절한다. package helper는 직접 Game UBT 후 UAT cook/stage/archive를 수행한다. 관찰 Python은 개발 QA이며 production inference가 아니다.

| 장면 | 반드시 대조할 결과 | 현재 증거 / 새 담당 작업 |
|---|---|---|
| 첫 접속·정지 중 성장·late join | 최신 ID/region/life/Activity/크기, 시각 상태 dirty 갱신 | 기존 동시2Client/자식 크기 통과, 수정 후 재검증 |
| A/B 서로 다른 지역 | 각 관심 field/개체, 서버 Native 한 번만 실행 | 현재 같은 PC에서3지역 field 수신 통과 |
| 죽음·보존·삭제 | 한 번의 서버 death, relevance Remove와 분리 | codec/실제 장면 근거, 새 transport에서 회귀 |
| 재접속·재진입·오래된 표본 | 첫 Add/reset 초기화, ghost·중복 bind 없음 | 손실/WAN/장시간 조합은 추가 검증 필요 |
| 자연 출생·이주·로드 | identity 유지와 실제 context/region 인계, reset revision | 기본 기능 검증과 수정 영향 대조 |
| 부하 증가 | 실제 cap·연결 수·Proxy/Actor/Add·GT/Render/Native·bytes·메모리 | 먼저 현 장면 baseline, 무검증500/1000 상향 금지 |
| cook·패키지 | FX/소리/식물/물·BP 의존성, editor-only template 오류0 | label 설정·ReferencedSet·실제 실행을 함께 확인 |

## 10. 성능을 보고할 때의 함정

Native batch p95는 전체 GT/frame CPU가 아니다. Dedicated FrameTime 약34ms에는30Hz pacing이 포함된다. CSV의 GameThread/RenderThread, 계측된 exclusive scope 합계, process memory, 수신 표본/실제 packet bytes를 따로 적는다. QA 마지막 JSON 기록의1초 이상 지연을 production Native 비용으로 설명하지 않는다.

2026-10-23 같은 PC의 동시2Client에서 Native batch p95 약2.244ms, Client GT p95 약2.76/2.77ms였지만 ClientA 최대 frame 약350ms hitch가 남았다. CPU/GPU·해상도·접속/이동 경로·관찰 도구·인구·캐시 조건과 함께 읽는다. 평균/p95 개선으로 max hitch나 거래 누락을 숨기지 않는다.

직접 NetDriver `*BytesPerSecond` 카운터는 해당 실행에서0이었다. 최종 대역폭은 실제 누적 total byte 차분/관찰 wall time으로 계산했다. 수신/송신 p95 약13,172/22,910B/s이며 전체 NetDriver 수치다. 순수 ecology payload만의 비용도, 순간 burst 최대도 아니다.

## 11. PR·종료 보고 acceptance

PR에는 문제의 trigger·최종 동작·수정 파일과 소유권, 이전 payload/model/save 호환성, 실제 World 역할·맵·인구/연결·기간·seed·flags, 테스트 JSON/실제 장면, p95/max·원시 counter 정의, 실패/negative case, rollback·남은 한계를 적는다. 새 RPC가 있으면 owner/권위 검증·큐 상한·TTL·중복/과부하 처리도 포함한다.

LFS 객체와 World Partition 외부 actor 누락을 확인하고 개인 발표·Saved raw·실행 파일은 push하지 않는다. 학습 담당에게 필요한 결과는 시각 Actor 위치가 아니라 권위 snapshot/실제 outcome·단위/시간·world/model 버전이다. 상대의 학습/서비스 완료를 대신 선언하지 않는다.
