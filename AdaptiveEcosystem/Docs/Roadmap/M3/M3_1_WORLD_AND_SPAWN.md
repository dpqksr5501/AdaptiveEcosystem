# M3.1 — 지역·낮밤·권위 스폰 기반

> 상위 계획: [M3 개발 계획](M3_IMPLEMENTATION_PLAN.md)  
> 다음 단계: [M3.2 — 소비·이벤트·자원 조정](M3_2_RESOURCE_AND_EVENTS.md)  
> 상태: 개발 계획 / 미구현·미검증  
> 예상 개발량: **2~3.5인일** (UE 5.8 Mass 경험자 1명, 1인일=8시간)

## 1. 목표와 완료 화면

플레이어 없이 A/B 두 지역에 초기 Box 개체가 생성되고, Server의 Day/Night에 따라 추가 개체가 생성되는 기반을 완성한다. Food는 이 단계에서 소비하지 않으며 재생률도 0이다. Food 값은 후속 스폰 허용 여부를 확인하는 읽기 전용 입력으로 사용한다.

완료 화면에서는 초기 A/B 각각 8개 Box, 60초 단위 Day/Night 전환, 낮 30초/4마리·밤 20초/6마리의 추가 생성과 개체 수 상한을 확인한다. 최초 표시에는 기존 M2 Box와 서버 로그만 사용해도 된다. Client 지역/시계 요약은 M3.3에서 연결한다.

## 2. 선행 조건과 범위

- M2의 EntityConfig·Box·Client Bubble을 재사용할 수 있어야 한다. 시작 시 Host/Client의 TemplateID와 기본 생성·수신을 smoke test로 확인한다.
- 장애물 없는 A/B Bounds, Spawn 위치, 도착 위치, 상호 인접 관계를 지정한다. 초기 로딩 구역을 사용하고 동적 Region 스트리밍은 제외한다.
- 1개 Species, 고정 특성을 사용한다. 실제 태양·날씨·Dusk/Dawn·AIController·Actor 전투는 제외한다.
- 초기화 실패를 무시하고 소비나 시계를 먼저 실행하지 않는다. 기존 M2 문제가 있으면 원인을 기록하고 기반을 복구한 뒤 진행한다.

## 3. 책임 분리

| 계층 | 이 단계의 책임 | 금지할 책임 |
| :--- | :--- | :--- |
| Core | 시간 snapshot, 스폰 요청/결과 등 작은 값 계약 | UObject·Mass 핸들·Network Actor 의존 |
| World | Region의 공간/연결 설정, Server 논리 시계와 Phase | Food 차감·Population 수기 증가·Entity 생성 |
| Ecology Simulation | 권위 지역 초기 상태, 스폰 일정/조건/상한 결정, StableAgentId 발급 | Transform 이동·Entity Fragment 소유·복제 프로퍼티 |
| Mass | 템플릿 구성, 승인 요청의 안전한 batch 생성, Fragment 초기화, 실제 개체 집계 | 자체 스폰 난이도/주기 결정·Food 직접 변경 |
| GameMode/조정 경계 | 양쪽 초기화 완료 확인, World→Ecology→Mass 호출 순서 연결 | 별도 시계·Food 저장소·살아있는 개체 목록 생성 |
| Network/Representation | 기존 M2 수신과 Box 표시 | Client에서 예약·ID 발급·권위 Entity 생성 |

World 시계는 시간의 단일 진실값이다. Ecology의 다음 스폰 시각은 이 시계에 대한 예약값이며 별도 시간이 아니다. GameThread 조정 코드는 계층 간 요청을 전달할 뿐 상태의 두 번째 소유자가 되지 않는다.

기존 Bootstrap은 World별 Template 등록과 최초 진입을 담당한다. 반복 생성을 위해 `InitializeMassNetwork()`의 초기화 guard를 해제하지 않는다. 별도의 batch 생성 경로를 Mass 안에 두고 초기/웨이브 요청을 명시적으로 구분한다.

## 4. 입력·출력 계약

구체적인 C++ 타입명은 구현 시 정하되 아래 의미를 고정한다. World 내부 EntityHandle은 Mass 서비스 내부에서만 사용하고 계층 간 DTO에 노출하지 않는다.

| 계약 | 생산자 → 소비자 | 필수 의미 |
| :--- | :--- | :--- |
| 시간 snapshot | World → Ecology/조정 경계 | WorldEpoch, SimTime, CycleId, Phase, PhaseStartTime |
| Region 공간 snapshot | World → Mass/조정 경계 | RegionId, Bounds, Spawn/도착 위치, 인접 RegionId. UObject 참조 없는 복사본 |
| 스폰 요청 | Ecology → Mass | 초기/웨이브 구분, 요청 key, RegionId, SpeciesId, 수량, 생성 기준 시각 |
| 스폰 결과 | Mass → Ecology/조정 경계 | 요청 key, 실제 성공 수, 실패 사유. 요청 수를 성공 수로 간주하지 않음 |
| Population snapshot | Mass → Ecology | 동일 완료 StepId의 Region별 Alive 수 및 평균 Energy |

웨이브 key는 WorldEpoch와 `(CycleId, Phase, RegionId, WaveIndex)`를 포함한다. 초기 생성 key는 별도 종류로 구분한다. 순차 스폰 승인 시 실제 성공 수와 아직 처리 중인 승인 수를 함께 고려해 128 상한을 넘지 않는다. 처리 중 예약은 완료 후 반드시 해제한다.

## 5. 구현 작업 순서

1. **설정과 초기화 정리:** `Forest_A`/`Region.Default` 불일치를 제거하고 명시적 A/B 설정을 사용한다. RegionId 중복·미등록·Bounds 밖 초기 위치·무효 Species를 초기화 오류로 처리한다. Food/Capacity는 유한하고 재생률은 0으로 검증한다.
2. **준비 상태 통일:** 두 Region과 양쪽 Template 준비 후 초기 요청을 한 번 처리한다. Actor BeginPlay 순서와 `bAutoInitialize`/GameMode 중복 진입에도 같은 초기 요청은 재실행하지 않는다. 현재 GameMode의 OR 준비 판정을 전체 필수 Region 성공 판정으로 바꾼다.
3. **서버 시계 연결:** 초기 생성 완료 후 Day에서 시계를 시작한다. 60초 Day→60초 Night를 반복한다. 실제 초기 생성 시각을 소비 유예 시간의 기준으로 저장한다.
4. **스폰 일정 생성:** Phase 진입 즉시 추가 웨이브를 만들지 않고 해당 간격 후부터 예약한다. 이전 Phase 마지막 예약과 전환이 같은 시각이면 새 Phase가 우선한다.
5. **스폰 허용 판단:** Region Food가 0, 지역 소속 개체 64 이상, 전체 Alive/예약 수 128 이상이면 추가 생성하지 않는다. 초과분과 건너뛴 웨이브는 다음에 보상하지 않는다. 지역 64 제한은 신규 생성에만 적용하며 후속 이주를 막지 않는다.
6. **안전한 Mass 생성:** Entity loop 밖의 승인된 GameThread 경계에서 batch 생성한다. StableAgentId, Region/Species ID와 Runtime Index, Vitals, Travel 초기 상태, SpawnTime과 NextFeedTime을 설정한 뒤 네트워크 Add 관측에 넘긴다.
7. **기본 집계/회귀:** Mass에서 직접 Alive를 집계하고 Ecology에 전달한다. Client는 기존 M2처럼 관련 개체만 수신한다. 로그에 key·성공 수·TemplateID를 남긴다.

생성 실패나 부분 성공은 해당 요청의 terminal 결과로 기록하고 같은 key 전체를 재실행하지 않는다. 초기 요청이 요구 수를 채우지 못하면 준비 실패로 남기고 시계를 시작하지 않는다. 재시도 정책을 숨겨 중복 생성하지 않는다.

## 6. 주 수정 영역과 다음 단계 인계

| 영역 | 작업 |
| :--- | :--- |
| `Core/`, `World/` | 작은 시간/공간 값 계약 및 논리 시계, Region 설정 검증 |
| `Ecology/EcologySimulationSubsystem.*` | 명시적 초기 상태 등록, 스폰 예약과 조건 결정 |
| `Mass/EcoMassNetworkBootstrap.*`, `EcoMassNetworkTrait.*`, `EcoMassFragments.h` | 재사용 가능한 생성 경로, Authority 초기화 및 생애/섭취 시각 Fragment |
| `AdaptiveEcosystemGameMode.*` | 전체 필수 초기화 완료 확인 및 실행 진입 |
| 테스트 맵/EntityConfig | 평면 A/B 배치, 기존 Box 유지, Client 등록 유지 |

다음 단계에 인계할 것은 실행 중인 시간 snapshot, 등록된 Region/Runtime Index, Food 읽기 snapshot, 개체별 SpawnTime/NextFeedTime, 승인 스폰 경로와 기본 집계다. `NextFeedTime = SpawnTime + 20초`만 초기화하고 실제 소비는 M3.2가 담당한다. M3.3이 Region/Travel을 바꿀 수 있도록 Alive/Authority 및 Travel 기본 구성을 마련한다.

## 7. 검증 및 종료 기준

- [ ] A/B 모두 준비되고 초기 8마리씩 생성된다. GameMode/Bootstrap 재호출로 추가 초기 생성이 없다.
- [ ] Pawn/입력 및 Client 수에 관계없이 시계·반복 생성이 진행된다.
- [ ] 3회 이상 낮밤 전환에서 예약 중복이 없고 정확한 key를 기록한다.
- [ ] 60초/120초 경계에서 이전 Phase 웨이브와 새 Phase 전환이 이중 생성하지 않는다.
- [ ] 초기 개체 및 새 웨이브마다 ID/index/시간/Travel 초기값이 유효하다.
- [ ] 설정상 Food=0인 지역의 추가 웨이브가 생략된다. Food 값은 이 단계에서 증가/감소하지 않는다.
- [ ] 부분 생성·여러 Region 같은 시각 생성에도 전체 128 상한을 넘지 않는다.
- [ ] 같은 완료 snapshot의 Alive 수 = Region Population 합 = 실제 성공한 생성 수다.
- [ ] Client는 시계/스폰 권위를 갖지 않고 M2 Template/Bubble 동작을 유지한다.
- [ ] UE 5.8 `AdaptiveEcosystemEditor Win64 Development` 빌드 및 핵심 시계/중복/상한 검증이 통과한다.

종료 시 실행 설정·key 예시·초기화 오류 재현과 검증 결과를 M3 검증 기록에 남긴다. 이 조건을 만족한 뒤 M3.2로 진행한다.
