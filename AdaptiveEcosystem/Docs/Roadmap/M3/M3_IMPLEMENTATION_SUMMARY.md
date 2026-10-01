# M3 구현 현황과 에디터 검증 가이드

> 기준일: 2026-09-30. 현재 작업 트리의 C++/설정과 기존 M3 문서·검증 기록을 대조한 요약이다. 코드에 구현된 기능, 이전 빌드·로그로 확인된 사실, 앞으로 실행할 PIE 기대값을 구분한다. 이 문서 작업에서는 소스·에셋을 변경하거나 PIE/빌드를 새로 실행하지 않았다.

## 1. 현재 범위와 상태

M3.1~M3.3의 **관찰용 생태 시나리오**는 코드로 연결되어 있다. Server/Standalone에서 지역별 초기 Mass Entity 생성 → 낮밤 웨이브 → 개체별 먹이 소비/환경 손실 → 식량 고갈 → 인접 지역으로 같은 Entity 이동/도착 → 지역 집계/복제 요약을 처리한다. 이 경로의 UE 5.8 `AdaptiveEcosystemEditor Win64 Development` 빌드 성공은 [검증 기록](M3_VALIDATION_REPORT.md)에 남아 있다. 기존 Standalone 로그에서는 `Forest_A`의 수동 고갈과 기존 ID 1~8의 `Forest_B` 도착, 총 개체 수 16 유지가 관찰되었다.

**M3 전체 생태 폐루프 완료를 뜻하지는 않는다.** 위 로그는 당시 추가 Spawn Waves가 꺼진 빌드에서 나온 것으로, 우회 설정 제거 후의 정기 생성·이주 동시 실행, Host/Client 표시, 긴 시간 안정성은 기존 검증 기록에서 미확인이다. 자동화 테스트는 기존 요청에 따라 작성·실행하지 않았다. 아래 표의 “구현”은 소스에 경로가 있다는 뜻이고 “PIE 확인”과 다르다.

| 단계 | 현재 개발된 기능 | 확인된 증거 | 남은 실제 확인 |
| --- | --- | --- | --- |
| M3.1 | 권위 시계, 지역/Bootstrap 초기화, Day/Night 정기 Spawn, 상한·Food 조건, Mass 집계 | Editor 빌드 성공 기록 | 수정된 구성으로 초기/반복 생성·Client Box PIE 재확인 |
| M3.2 | 개체별 소비 예약, 비례 배분, 낮/밤 Food 손실, 수동 Starvation, 자원 장부 | Editor 빌드 성공 기록; 수동 고갈의 자원 로그 | 소비·자동 이벤트 단독/통합 수치 재현 |
| M3.3 | 인접 지역 선택, Traveling/Waiting/도착, 같은 ID·Population 재집계, 완료 요약 복제, 읽기 전용 Debug | Editor 빌드 성공 기록; 과거 Standalone A→B 로그 | Spawn Waves 동시 실행, 양쪽 고갈, 도착 후 소비, Host/Client/Late Join |

세부 설계는 [M3.1](M3_1_WORLD_AND_SPAWN.md), [M3.2](M3_2_RESOURCE_AND_EVENTS.md), [M3.3](M3_3_MIGRATION_AND_VALIDATION.md)에 있다. 이 문서는 현재 구현과 검증에 필요한 공통 진입점이다.

## 2. 개발된 동작과 책임

| 계층 | 소유하는 상태/역할 | 구현 위치 |
| --- | --- | --- |
| World | `AEcologyRegion`의 RegionId·Bounds·도착점·명시적 인접 관계, 서버 낮밤 시간 및 공간 snapshot. 지역 Actor의 초기 Food는 편집 입력이며 실행 중 Food 장부가 아니다 | [EcologyRegion.h](../../../Source/AdaptiveEcosystem/World/EcologyRegion.h), [EcoWorldClockSubsystem.cpp](../../../Source/AdaptiveEcosystem/World/EcoWorldClockSubsystem.cpp), [EcologyWorldSubsystem.cpp](../../../Source/AdaptiveEcosystem/World/EcologyWorldSubsystem.cpp) |
| Ecology | 지역 Food/Capacity, Spawn 예약·상한, 이벤트 손실·소비 비례 배분·자원 보존, StableAgentId 발급, Mass가 보내온 Population 집계 수신 | [EcologySimulationSubsystem.cpp](../../../Source/AdaptiveEcosystem/Ecology/EcologySimulationSubsystem.cpp), [EcologyResourceSimulation.cpp](../../../Source/AdaptiveEcosystem/Ecology/EcologyResourceSimulation.cpp), [EcoSpawnSchedule.cpp](../../../Source/AdaptiveEcosystem/Ecology/EcoSpawnSchedule.cpp) |
| Mass | Bootstrap의 초기/웨이브 Entity 생성과 개체 Fragment 초기화, 개체별 소비 예약/지급, Travel 상태·이동 의도·도착 시 Region 변경, Alive Entity 기준 집계 | [EcoMassNetworkBootstrap.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassNetworkBootstrap.cpp), [EcoMassFeeding.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassFeeding.cpp), [EcoMassMigration.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassMigration.cpp) |
| 조정 경계 | 초기 구성 검증 후 시계 시작, 예정 시각 순서 실행, 단계 사이의 Mass/Ecology 호출, 오류 시 중단, 완료 집계와 요약 게시 | [EcoMassLifecycleSubsystem.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassLifecycleSubsystem.cpp) |
| Network/표시 | `AEcoGameState`의 시각+자원+개체군 단일 완료 요약 복제, 기존 Mass Bubble의 관련 Box Transform/Region 전달, Host Mass ID/화살표 및 양쪽 지역 라벨 표시 | [EcoGameState.cpp](../../../Source/AdaptiveEcosystem/Network/EcoGameState.cpp), [EcologyNetworkTypes.h](../../../Source/AdaptiveEcosystem/Network/EcologyNetworkTypes.h), [EcoMigrationDebugSubsystem.cpp](../../../Source/AdaptiveEcosystem/Debug/EcoMigrationDebugSubsystem.cpp) |

### M3.1: 지역·낮밤·생성

- 지정한 수의 지역과 **지역별 Bootstrap 하나**가 모두 유효해야 초기화를 진행한다. RegionId 중복/잘못된 인접 ID, Bounds 밖 도착점·스폰 슬롯, EntityConfig의 필수 Fragment 누락 또는 충돌하는 Movement Trait는 시작 실패 원인이다. 현재 구현은 한 지역에 Bootstrap을 여러 개 두는 구성도 거절한다.
- 초기 생성은 Bootstrap의 `InitialAgentCount`를 사용한다. 이후 낮/밤 웨이브는 Bootstrap `SpawnSchedule`의 간격·수량을 따른다. 각 Phase는 끝 시각을 포함하지 않으므로 전환 순간 이중 웨이브가 없다. `Food=0`이면 **추가 웨이브만** 생략하며 초기 생성은 별도로 처리한다.
- 기본 설정값은 낮 60초/밤 60초, 낮 30초마다 4개·밤 20초마다 6개, 지역 생성 상한 64·전체 상한 128이다. 다만 현재 [DefaultGame.ini](../../../Config/DefaultGame.ini)는 낮/밤 각각 **10초**로 덮어쓴다. 맵에 저장된 Bootstrap 설정도 기본 C++ 값과 다를 수 있으므로 에디터 Details의 실제 값을 확인해야 한다.
- 신규 Entity마다 새 `StableAgentId`, Species/Region ID와 runtime index, Transform, Resident Travel 상태, 생성/첫 소비 시각을 초기화한다. `mass.debug.DrawAllEntities 1`은 생성된 Transform 보유 Entity를 그리는 엔진 명령이며 생성 자체를 실행하지 않는다.

### M3.2: 정기 소비·환경 이벤트·자원

- 기본 소비 설정은 출생 후 20초 첫 요청, 이후 10초 간격, 회당 Food 1이다. 소비 자격은 Authority·Alive·`Resident` Entity이며 Traveling/Waiting은 제외한다. 개체별 요청을 Mass에 모아 Ecology가 지역별로 비례 배분한다. 예를 들어 Food 5에 10명이 2씩 요청하면 지급 합 5, 각자 0.5다. 현재 지급량은 `LastGrantedAmount`/`TotalGrantedAmount`에 기록되지만 **Energy/HP로 환산되지는 않는다**.
- 낮/밤 자동 이벤트는 해당 Phase의 설정 fraction에 지역 Food를 최대 `FoodLoss`만큼 줄이며 Phase당 한 번이다. 낮 이벤트는 기본 비활성·`Forest_A`, 밤 이벤트는 기본 활성·`Forest_B`이다. 10초 Phase라면 기본 fraction 기준 낮 시작 후 약 4.167초, 밤 시작 후 2.5초다. Food는 0 미만이 되지 않으며 이번 관찰 경로에서 재생률은 0이다.
- `Debug.Starvation.Forest_A` 또는 `Debug.Starvation Forest_A`는 권위 World의 A Food를 다음 해당 자원 처리 시각에 0으로 만들도록 예약한다. **시계, Spawn Waves, 생성 간격, Feeding 설정을 변경하지 않는다.** 실제 감소량은 `EventLoss`로 기록된다. 잘못된 지역/중복 대기 요청/Client 실행은 거부된다.
- 완료 자원 snapshot에는 Epoch/Step/시각, Food/Capacity, EventLoss/Consumed/반올림 차이가 들어간다. 보존식은 `Before - EventLoss - Consumed - Rounding = After`다. 낡거나 중복된 개체 소비 요청은 거절한다.

### M3.3: 고갈 이주·집계·표시

- `Migration.Enabled`가 켜져 있으면 기본 1초 판단 주기에 식량이 고갈된 지역의 Resident가 **명시적으로 등록된 인접 지역** 중 Food가 있는 곳을 찾는다. 현재는 고갈에 반응하는 고정 규칙이다. 설정 기본값은 속도 400 cm/s, 도착 반경 30 cm, 도착점 분산 300 cm, Food 판단 epsilon 0.0001이다.
- Mass 상태의 기준은 `FEcoTravelFragment::State` 한 값(`Resident`, `Traveling`, `WaitingForFood`)이다. 이동 중에도 이전에 commit된 지역 Population에 속한다. 엔진 Mass Movement가 Transform을 움직이고, 목표 반경과 목적지 Bounds 안에 들어왔으며 목적지 Food가 남아 있을 때 **같은 Entity/StableAgentId**의 Region을 목적지로 바꾼다. 도착지에서 새 Entity를 만들지 않는다.
- 목적지가 중간에 고갈되거나 후보가 없으면 현재 위치에서 기다린다. 도착 후 첫 소비는 실제 관측 도착 시각 + 소비 간격으로 재예약하여 이동 중 밀린 식사를 몰아서 처리하지 않는다. 지역 생성 상한 64는 새 Spawn을 제한하지만 기존 Entity의 이주 도착을 막지는 않는다.
- 매 완료 단계에 Mass의 Alive Entity를 조회해 지역 Population/Traveling/Waiting을 갱신하고, 1초 간격으로 `AEcoGameState`에 단일 완료 요약을 게시한다. Host Debug는 Mass의 ID·이동 화살표까지 읽고 Client는 복제된 지역 요약을 표시한다. Client Bubble은 관련 개체의 부분집합이므로 화면상 Box 수를 전체 Population과 같다고 판정하지 않는다.

처리 순서는 `환경 손실 → Food/상한을 반영한 Spawn → 소비 요청·배분 → 완료 자원 snapshot → 이주 판단·도착 commit → Mass Population 재집계 → 요약 게시`다. 시뮬레이션은 최대 0.25초 간격과 각 예약 경계로 나누고 프레임당 최대 8단계까지 따라잡는다. 이동 조향은 프레임마다 별도로 실행한다. 따라서 같은 시각에 기아 이벤트와 웨이브가 겹치면 손실이 먼저이고, 이주로 바뀐 Population은 이후의 웨이브에 반영된다.

## 3. 에디터 준비와 공통 관찰법

1. UE 5.8용 Editor 빌드를 사용하고 **에디터를 완전히 종료한 뒤 다시 연다.** 새 Fragment/템플릿 구성이 반영되어야 한다. 기존 M2 Box EntityConfig와 맵을 사용하며 에셋은 이 구현 과정에서 자동 수정되지 않았다.
2. 두 `EcologyRegion`의 RegionId를 `Forest_A`/`Forest_B`로 지정한다. A의 `AdjacentRegionIds`에 `Forest_B`, B에는 `Forest_A`를 넣고 두 Bounds를 겹치지 않게 둔다. 각 `ArrivalOffset`은 자기 Bounds 내부에 둔다. 두 지역은 공간상 가까워도 인접 ID가 없으면 연결되지 않는다.
3. 지역마다 `EcoMassNetworkBootstrap` 하나를 두고 각 `RegionActor`, 기존 Box `EntityConfig`, `InitialAgentCount=8`, `SpawnSpacing=250`, `bAutoInitialize=true`를 확인한다. 전체 64개 반복 생성 슬롯이 자기 Bounds 안에 들어가야 한다. `Eco Network Agent` Trait가 필수이며 PPO Herbivore/Custom·Spring Movement/Simulation LOD를 이 M3 Box 이동 템플릿에 함께 넣지 않는다.
4. **Project Settings → Adaptive Ecosystem**에서 `Required Region Count=2`, `Global Population Limit=128`, `Enable Spawn Waves`, `Feeding.Enabled`, `Migration.Enabled`, Day/Night Food Event, `Draw Migration Debug`를 시나리오별로 정한다. Bootstrap의 Day/Night Spawn Interval/Count는 별도 Details 값이다. 설정을 바꾼 뒤에는 PIE를 재시작한다.
5. 우선 **Standalone PIE**로 실행한다. 명령은 Output Log 창이 아니라 권위 **게임 뷰포트 콘솔**에 입력한다. Output Log에서 `[Eco M3.1] Ready`, `[Eco M3.2] Ready`, `[Eco M3.3] Ready`, `[Eco Spawn]`, `[Eco Food Event]`, `[Eco Food]`, `[Eco Migration]`, `[Eco Daily]`를 찾는다. 시작이 중단되면 `[Eco M3.1] Population stopped:`의 구체적 원인을 먼저 해결한다.

## 4. 단계별 수동 테스트

아래 수치는 **설정을 명시한 경우의 기대값**이다. 이전 로그에 없는 항목을 이미 검증된 결과로 읽지 않는다. 실행 후에는 월드 이름·Epoch·Step·서버 시각, 개체 ID, 지역 Food/Population을 함께 기록하면 원인과 결과를 대조할 수 있다.

### A. Spawn 주기와 상한만 확인

`Feeding.Enabled=false`, Day/Night Food Event 둘 다 false, `Migration.Enabled=false`, `Enable Spawn Waves=true`, A/B Food 충분으로 둔다. 낮/밤 각각 10초, 각 Bootstrap 낮 5초/4개·밤 4초/6개, 지역 상한 64, 초기 8개로 설정한다. 기대 결과는 지역마다 0초 8 → 20초 24 → 40초 40 → 60초 56 → 80초 64이며 전체는 16 → 48 → 80 → 112 → 128이다. 낮은 +5초, 밤은 +4/+8초 웨이브가 실행된다. 상한 이후 추가 생성은 0이다. `[Eco Spawn]`, `[Eco Spawn Skipped]`, `[Eco Daily Total]` 및 `mass.debug.DrawAllEntities 1`을 함께 본다. Food만 0인 A의 **초기 8개는 남고**, A의 추가 웨이브만 스킵되는지도 별도 PIE에서 확인할 수 있다. 상세 절차는 [M3.1 에디터 테스트](M3_1_EDITOR_TEST.md), 10초 설정 기대표는 [M3.2 에디터 테스트](M3_2_EDITOR_TEST.md)에 있다.

### B. 소비·이벤트만 확인

원인을 분리하려면 `Migration.Enabled=false`, `Enable Spawn Waves=false`로 재시작한다. 소비 시험에서는 자동 이벤트를 끄고 A Food=24, 초기 8개, 첫 소비 20초/간격 10초/양 1로 둔다. A Food는 20/30/40초 완료 단계에 16/8/0을 기대하며, 50초 요청의 지급량은 0이다. 부족 배분은 별도 PIE에서 A Food=5, 10개체, 요청량 2로 확인한다. 자동 이벤트 시험에서는 소비를 끄고 각 Food=40, 낮/밤 이벤트 활성·손실 40, 낮/밤 길이 10초로 둔다. 기본 fraction이면 A가 약 4.167초, B가 밤 시작 후 2.5초에 고갈된다. `[Eco Food Event]`의 `ActualLoss`와 `[Eco Food]`의 `After/Consumed/Rounding`을 비교한다. 자세한 설정은 [M3.2 에디터 테스트](M3_2_EDITOR_TEST.md)에 있다.

### C. Starvation과 Spawn Waves가 함께 작동하는지 확인

A Food=40, B Food=400, 각 8개체, 양방향 인접, `Migration.Enabled=true`, `Enable Spawn Waves=true`, `Draw Migration Debug=true`로 둔다. Day/Night를 각각 10초로 시험할 때 **각 Bootstrap의 웨이브 간격을 낮 5초/밤 4초**로 함께 설정한다. 원인을 단순화하려면 Feeding 및 자동 Food Event만 끄되 Spawn Waves는 켜 둔다. Standalone 첫 웨이브 전에 게임 뷰포트에서 `Debug.Starvation.Forest_A`를 실행한다.

`[Eco M3.2] ... Waves=1`을 먼저 확인한다. 이어 `[Eco Debug] Starvation queued` → `[Eco Food Event] Source=Debug.Starvation` → `[Eco Food] Region=Forest_A ... After=0 ... Depleted=1`을 확인한다. A의 후속 예정 웨이브는 `[Eco Spawn Skipped]`, B의 예정 웨이브는 `[Eco Spawn] Region=Forest_B Initial=0`이어야 한다. A의 기존 ID들은 Traveling 로그/청록색 화살표로 B로 가고 `Arrived=1 From=Forest_A Region=Forest_B`에서 **같은 ID**로 도착해야 한다. A Population은 도착마다 감소하고 B는 이주 도착과 성공한 신규 생성만큼 증가한다. 전체 Population은 이주 자체로 증가하지 않는다. B의 도착 개체와 B에서 새로 태어난 개체는 서로 다른 사건이므로 B Population이 증가했다고 전부 신규 Spawn으로 세지 않는다. 상세 표와 공간 배치는 [M3.3 에디터 테스트](M3_3_EDITOR_TEST.md)에 있다.

### D. 대기·도착 후 소비·네트워크 확인

- **양쪽 고갈:** 새 PIE에서 A 명령 뒤 개체가 도착하기 전에 `Debug.Starvation.Forest_B`를 실행한다. 목적지가 없으면 `WaitingForFood`가 되고 마지막 commit 지역 소속/ID를 유지한다. 양쪽 Food=0 뒤에는 추가 웨이브가 스킵된다. Food 재생이 없으므로 재시작 전에는 회복을 기대하지 않는다.
- **도착 후 소비:** Spawn Waves/자동 이벤트를 끈 분리 실행에서 Feeding=true, A Food=40/B=400으로 둔다. A를 수동 고갈시킨 뒤 Traveling/Waiting의 소비 요청이 없고, 도착 로그의 `NextFeed`가 관측 도착 시각 + 10초인지 확인한다. 이후 해당 ID가 B의 소비에 합류해야 한다.
- **Host/Client:** GameMode가 `AEcoGameState` 또는 해당 Blueprint를 사용하도록 확인하고 Listen Server + Client에서 명령은 Host에서만 실행한다. 양쪽의 Food/Population/Traveling/Waiting·Day/Night 요약은 동일한 완료 Step을 가리켜야 한다. Host의 ID/화살표는 Client에 자동 복제되지 않는다. Client Box는 Bubble 관련 범위에서만 Transform/Region을 비교한다. Late Join, Bubble 이탈/재진입, PIE 재시작도 별도 점검한다.
- **장시간/프레임:** 30/60 FPS와 일시적 긴 프레임에서 이벤트·소비·도착 중복이 없는지, 128개체 15분에서 집계가 보존되는지 확인한다. 긴 프레임에서는 이동 적분이 0.1초로 제한되어 도착이 늦을 수 있으므로 서버 예정 시각과 실제 관측 시각을 구분한다.

공통 불변식은 `지역 Population 합 = 전체 Alive Entity 수`, `전체 Alive = 초기 생성 + 성공한 추가 생성 - 실제 사망`, `이주만으로 전체 Alive 변화 0`, `Food ≥ 0`, `각 도착 Entity의 StableAgentId 유지`다. 현재 M3 관찰 경로에는 사망 처리가 없으므로 정상 시나리오에서는 마지막 식의 사망 항이 0이다.

## 5. 현재 구현하지 않은 것과 후속 계획

- **이주 원인/특성의 다음 생성 반영은 아직 설계안이다.** [Migration-aware Spawn 계획](MIGRATION_AWARE_SPAWN_PLAN.md)에 출발지 유출·도착지 유입 이력, `MigrationOutcome`, `BirthProfile`/`ProfileRevision`, 개체별 적응 특성을 제안했지만, 현재 `FEcoSpawnRequest`에는 프로필 필드가 없고 Migration은 원인/특성 outcome을 Ecology에 게시하지 않는다. 따라서 현재 B의 다음 웨이브는 **기존 시간·Food·Population/상한 규칙**만 반영한다. 이주 경험을 물려받은 개체 생성은 지금 시험할 수 없다. Bootstrap도 이주 이력을 저장하지 않는다.
- 소비 지급은 Energy/HP, 기아 사망, 포식 생존 결과로 이어지지 않는다. 현재 `PredationHistory` 필드는 존재하지만 플레이어 사냥 압력에 따른 권위 이주 입력·특성 상속은 연결되지 않았다. V1 Observation/Utility, PPO 정책/Native 추론과의 폐루프 결합도 이번 M3.1~M3.3 관찰 구현 범위 밖이다.
- Food 자동 재생, NavMesh/장애물 회피·지면 추적, 정교한 Flock/최종 Mesh·Anim, 종별 다중 Bootstrap 운영은 이 시나리오에서 제공하지 않는다. 두 지역이 모두 고갈되면 대기와 신규 생성 중단이 정상이다.
- 현 작업 트리에는 M3 관련 추적 파일 수정과 새 파일이 함께 있다. 이 문서의 상태 판단은 **현재 작업 트리** 기준이며 별도 커밋/배포 상태나 현재 에디터의 바이너리 로드 상태를 확인했다는 뜻이 아니다. 기존 [검증 기록](M3_VALIDATION_REPORT.md)의 미실행 항목은 위 절차를 실제 실행한 뒤에만 완료로 갱신한다.
