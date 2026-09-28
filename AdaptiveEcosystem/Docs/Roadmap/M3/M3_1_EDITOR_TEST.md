# M3.1 에디터 테스트

## 현재 상태

서버 시계, 낮밤별 스폰 예약, 지역 초기 식량 편집 및 Mass 생성 경로를 구현했다. 화면 Print 함수 오버로드 오류와 UE 5.8 템플릿 구성 조회 오류를 수정하고, 2026-09-28 `AdaptiveEcosystemEditor Win64 Development` 빌드 성공을 확인했다. 자동화 테스트는 사용자 요청에 따라 생략했다. 수정 후 실제 PIE 생성/표시는 검증 대기다. 레벨/EntityConfig 바이너리 에셋은 변경하지 않았다.

새 UCLASS/UPROPERTY가 있으므로 에디터를 종료하고 `AdaptiveEcosystemEditor Win64 Development`를 UE 5.8에서 빌드한 후 에디터를 다시 열어 아래를 확인한다.

## 설정

M3.2 구현 이후 아래 M3.1 스폰만 확인하려면 Project Settings의 Feeding Enabled와 Day/Night Food Event Enabled를 끈다. 현재 사용자 설정(낮밤 10초, 스폰 간격 5초/4초)의 일일 기대 수량은 [M3.2 에디터 테스트](M3_2_EDITOR_TEST.md)를 참고한다.

1. 기존 M2 Box 표시가 되는 맵에서 `EcologyRegion` 두 개를 배치하고 `RegionId`를 각각 `Forest_A`, `Forest_B`로 지정한다. Bounds는 겹치지 않게 배치한다. `AdjacentRegionIds`에는 상대 지역 ID를 넣는다.
2. 각 Region Details의 **Ecology → Initial Resources**에서 `InitialFoodAmount=1000`, `FoodCapacity=2000`을 설정한다. 초기 식량은 0 이상 Capacity 이하로 지정한다. 변경한 값은 다음 Play 시작에 적용된다.
3. `EcoMassNetworkBootstrap`을 지역별 하나씩 배치한다. `RegionActor`에 해당 Region을 연결하고, `EntityConfig`에 기존 M2 Box 설정을 지정한다. 두 Bootstrap 모두 `InitialAgentCount=8`, `SpawnSpacing=250`, `bAutoInitialize=true`로 설정한다. 기존 에셋에 저장된 64 등의 값은 직접 8로 변경한다.
4. 각 Bootstrap을 자기 Region 중앙에 배치한다. 기본 64개 스폰 슬롯은 XY 각각 중심 ±875 범위이므로 Bounds가 이 범위를 포함해야 한다. `ArrivalOffset`도 지역 내부에 둔다.
5. **Project Settings → Adaptive Ecosystem → M3**에서 Day/Night Duration 각각 60초, Global Population Limit 128, Required Region Count 2를 확인한다. `Print Server Time`, `Print Server Time To Screen`을 켜고 Print Interval은 1초로 둔다. Spawn Schedule 기본값은 낮 30초/4개, 밤 20초/6개, 지역 상한 64다.

## 확인

먼저 Play의 Net Mode를 **Standalone**으로 실행한다. Output Log에서 `Eco`를 검색한다. 플레이어 조작 없이 확인할 수 있다.

| 시작 후 서버 시간 | 지역별 예상 개체 수 | 기대 상태 |
| --- | --- | --- |
| 0초 | 8 | 두 지역 초기 생성, Ready 로그 |
| 30초 | 12 | 낮 웨이브 +4 |
| 60초 | 12 | Night 전환, 경계 웨이브 없음 |
| 80초 | 18 | 밤 웨이브 +6 |
| 100초 | 24 | 밤 웨이브 +6 |
| 120초 | 24 | Day 전환, 경계 웨이브 없음 |

화면과 로그의 `[Eco Server Time]`에서 Time, Cycle, Day/Night, Remaining을 확인한다. `[Eco Region]`에서 초기 Food/Capacity를, `[Eco Spawn]`에서 지역별 실제 생성 수와 웨이브를 확인한다. 기본 설정에서는 약 440초에 지역별 64/전체 128에 도달하고 추가 생성이 멈춘다. 기존 EntityConfig에 별도 사망 등 개체 수를 바꾸는 로직이 없는 경우의 예상값이다.

Play를 종료하고 A의 `InitialFoodAmount=0`으로 변경해 재실행한다. A는 초기 8개만 유지하고, B는 계속 추가 생성되어야 한다. **이 단계에서는 식량 소비·이벤트·이주가 아직 실행되지 않는다.** 식량 0은 추가 스폰 차단만 확인한다.

마지막으로 Listen Server + Client 1개로 실행해 서버 로그는 한 번만 진행되고 Client에 기존 M2 Box가 표시되는지 확인한다. Client 자체에는 권위 시계가 없으며 시계 요약 복제는 M3.3 범위다. 한 프로세스 PIE 화면 메시지는 여러 창에서 공유될 수 있으므로 권위 판정은 월드 이름이 있는 서버 로그로 확인한다.

시작 실패 시 `Population stopped` 로그를 확인한다. 중복 RegionId, 누락된 Bootstrap/EntityConfig, Bounds 밖 슬롯, InitialFoodAmount > FoodCapacity 등이면 설정을 고치고 Play를 재시작한다.

### 수정 기록: Region 등록 성공 후 템플릿 검사 실패

`Forest_A`, `Forest_B` 등록 후 `Template is missing authoritative M3 fragments/tags, or contains ClientProxy`로 중단되는 문제를 수정했다. 원인은 Bootstrap의 검증 코드가 이전 `Composition.Fragments`/`Tags` 필드를 직접 읽은 것이다. UE 5.8의 구성 추가 경로는 `ElementsBitSet`을 갱신하므로, 실제 템플릿이 올바르더라도 이전 필드 검사에서는 필수 요소가 없는 것으로 판단할 수 있었다.

검사를 `Composition.Contains<T>()`로 변경했다. 이 API는 실제 저장소를 조회한다. 필수 Fragment/Authority/Alive 검사와 ClientProxy 배제 조건은 유지하며, 실패 로그에는 Config 경로, NetMode, 누락 요소 목록, ClientProxy 포함 여부를 남긴다.

전체 초기화는 Region 및 모든 Bootstrap 검증 → Ecology 초기 상태/예약 → Mass Entity 생성/초기화 → 실제 Population 집계 → 서버 시계 시작/Ready 순서다. 검증 실패는 Entity 생성 이전에 발생하므로 시계와 복제도 시작되지 않는다. `mass.debug.DrawAllEntities 1`은 이미 생성된 Transform 보유 Entity를 그릴 뿐 생성 기능이 없어, 이 상태에서는 표시할 대상이 없다. RegionActor 참조를 다시 지정해도 구성 조회 코드의 오류를 해결할 수는 없다.

### 수정 기록: Population 집계 쿼리 초기화 assertion

템플릿 검사를 통과한 뒤 `ReconcilePopulation()`의 첫 `AddRequirement<FEcoRegionFragment>()`에서 `Modifying requirements before initialization is not supported` assertion이 발생했다. 기본 생성한 `FMassEntityQuery`를 EntityManager에 연결하지 않은 것이 원인이다. 오류의 `bInitialized`는 엔진의 쿼리 요구사항 초기화 상태이며, LifecycleSubsystem의 개체군 준비 플래그와 다르다.

로컬 쿼리를 `FMassEntityQuery Query(Manager.AsShared())`로 생성하여 같은 World의 EntityManager에 먼저 연결한 뒤 읽기 요구사항을 추가하도록 수정했다. 실행 컨텍스트도 동일 Manager에서 생성하며 Local 방식으로 실행한다. Processor 소유 쿼리의 등록/초기화 경로는 이 Subsystem의 로컬 쿼리에 자동 적용되지 않는다.

이 집계는 초기 스폰 전 기존 개체 수 확인, 각 스폰 후 실제 Population 반영, 반복 스폰 상한 판단에 공통으로 사용된다. Region/Vitals와 Authority/Alive를 읽어 Mass 루프 밖에서 Ecology에 집계를 전달하는 책임 경계는 유지한다. 확인한 다른 기본 생성 쿼리들은 요구사항 추가 전 명시적 Initialize를 호출하고 있었고, Processor 멤버 쿼리는 소유 Processor에 등록되어 있었다.

수정 후 UE 5.8 `AdaptiveEcosystemEditor Win64 Development` 빌드에 성공했다. 자동화 테스트는 기존 요청에 따라 생략했고 PIE 재검증은 남아 있다. 에디터를 다시 열어 `[Eco Spawn]`, `[Eco M3.1] Ready`, 증가하는 `[Eco Server Time]` 및 30초의 추가 웨이브를 확인한다.

## 후속 낮밤/날씨 Subsystem 연결

- `UEcoWorldClockSubsystem`은 서버/Standalone 경과 시간의 소유자다. `UEcoMassLifecycleSubsystem`이 초기 생성 성공 후 시작하고 한 경로에서만 시간을 전진시킨다.
- 이후 서버 WorldSubsystem이 `IEcoDayCycleProvider`를 구현하고, 초기화 중 같은 World의 Clock에 `SetDayCycleProvider(this)`로 등록한다. Clock 시작 이후 교체는 거절한다. 필요 시 해당 Subsystem의 초기화 의존성으로 Clock을 먼저 초기화한다.
- Provider는 입력 서버 시간에 대한 CycleId, Day/Night, Phase 시작/종료 시각을 반환한다. 예약 지연 처리 때문에 과거 시각도 일관되게 평가해야 한다. 시간 역행이나 무효 구간은 거절된다. 미등록 상태는 고정 60초 Day/60초 Night 계산을 사용한다.
- 날씨 상태는 World의 환경 책임으로 확장한다. Clock/Provider가 식량이나 Entity를 수정하지 않는다. Ecology는 스폰 조건/예약, Mass는 생성 및 실제 개체 집계를 소유한다. Subsystem에 네트워크 프로퍼티/RPC를 추가하지 않는다.
