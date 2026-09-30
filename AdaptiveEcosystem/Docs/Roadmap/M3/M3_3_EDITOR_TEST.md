# M3.3 구현 및 에디터 확인

2026-09-28 구현. UE 5.8 `AdaptiveEcosystemEditor Win64 Development` 빌드로 검증한다. 자동화 테스트는 요청대로 작성·실행하지 않는다. 아래 PIE 시나리오는 기대 결과이며 실제 실행 완료 기록이 아니다. 검증 상태는 [검증 기록](M3_VALIDATION_REPORT.md)을 참고한다.

## 수동 Starvation → 이주와 Day/Night 생성 주기 확인

1. **에디터를 완전히 종료하고 다시 연다.** Fragment와 서버 템플릿 구성이 변경되었다. 기존 M3.2 맵과 Box EntityConfig를 사용한다. 새 Creature Actor나 이동 Trait를 추가할 필요 없다. 기존 `Eco Network Agent` Trait가 서버에 필요한 이동 Fragment와 CodeDrivenMovement Tag를 제공한다.
2. `EcologyRegion` 두 개의 `RegionId`를 `Forest_A`, `Forest_B`로 지정하고, **A의 Adjacent Region Ids에 Forest_B, B에는 Forest_A**를 넣는다. 인접은 명시적인 방향 연결이다. 가까이 배치하는 것만으로 인접해지지 않는다. A/B 초기 Food는 각각 40/400, Capacity는 각각 초기 Food 이상으로 둔다.
3. 두 Bootstrap의 `RegionActor`를 각각 연결하고 기존 Box `EntityConfig`, `InitialAgentCount=8`, `SpawnSpacing=250`, `bAutoInitialize=true`를 설정한다. 기본 상한 64의 전체 스폰 슬롯이 각 Bounds 안에 있어야 한다. 기존 에셋에 저장된 개체 수가 8인지 확인한다.
4. **Project Settings → Adaptive Ecosystem**에서 `Migration.Enabled=true`, `Enable Spawn Waves=true`, `Draw Migration Debug=true`를 확인한다. 이 설정들은 각각 독립적이다. `Debug.Starvation.Forest_A` 명령은 이 값을 바꾸지 않는다. 이벤트 원인만 분리해서 보고 싶으면 Day/Night Food Event를 각각 끄고, 소비 영향을 분리하려면 Feeding을 끈다. 이 선택도 Spawn Waves 설정과 독립적이다.
5. Migration 설정은 기본값 `Decision Interval Seconds=1`, `Speed=400 cm/s`, `Arrival Radius=30 cm`, `Arrival Spread=300 cm`, `Food Epsilon=0.0001`, `Print Transitions=true`로 둔다. 각 Bootstrap의 Day/Night Spawn Interval이 실제 Phase 길이보다 짧아야 해당 Phase에 웨이브가 있다. 예를 들어 Day/Night가 각각 10초라면 Day Interval=5초, Night Interval=4초로 설정한다. Standalone PIE로 실행하고 `[Eco M3.2] ... Waves=1`과 `[Eco M3.3] Ready`를 확인한다.
6. 초기 A/B가 각각 8개인 경우를 비교하려면 첫 웨이브 전에 **게임 뷰포트 콘솔**에서 `Debug.Starvation.Forest_A`를 입력한다. 일반형 `Debug.Starvation Forest_A`도 지원한다. Client 창에서는 실행할 수 없다.

기대 흐름:

| 시점 | A 요약 | B 요약 | 관찰 |
| --- | --- | --- | --- |
| 초기 | Food=40, Pop=8 | Food=400, Pop=8 | 각 ID가 자기 지역에 정지 |
| A 명령 처리 후 | Food=0, A 신규 생성 스킵 | B는 예정된 Day/Night 웨이브 계속 실행 | 동일 A ID가 청록색 화살표를 따라 B로 이동 |
| 도착하는 동안 | 기존 A 개체의 Pop가 하나씩 감소 | 이주 도착과 B 웨이브가 각각 Pop에 반영 | Bounds 내부이며 목표 반경 안인 개체만 소속 변경 |
| 모두 도착 | 기존 A의 Pop=0, Traveling=0 | 기존 8명 + 이주 8명 + 성공한 B 웨이브 수 | 전체 Pop 증가는 성공한 신규 생성 수만큼이며, 이주 자체는 총합을 늘리지 않음 |

요약은 1초마다 갱신된다. 이동 중 Population은 마지막 도착 지역인 A 소속이며, 화면상 B Bounds에 들어간 것만으로 소속이 바뀌지 않는다. B의 정규 웨이브는 `[Eco Spawn] Region=Forest_B Initial=0`로 확인한다. A는 Food=0이므로 `[Eco Spawn Skipped] Region=Forest_A`가 나오지만 예약된 주기 자체는 유지된다. 도착 전후 `ID`를 비교하고, 신규 B 개체는 새로운 ID인지 구분한다. `mass.debug.DrawAllEntities 1`은 해당 PIE의 권위 게임 뷰포트에서 켜며 Entity를 새로 생성하는 명령은 아니다.

Output Log에서 `Eco Food Event`와 `Eco Migration`을 검색한다. 전자는 `Source=Debug.Starvation`, `ActualLoss=40`을, 후자는 `State=Traveling` 및 같은 ID의 `Arrived=1 From=Forest_A Region=Forest_B`를 기록한다. `Epoch/Step/Time`은 완료 자원 단계, `Observed`는 실제 서버 처리 시각이다. 도착 로그의 `NextFeed`는 Observed+Feeding Interval(기본 10초)이다. Feeding을 켜 둔 경우 기존 소비 예약도 계속 실행된다.

### 공간 배치 예시

장애물이 없는 평면에서 A 중심 `(0,0,100)`, B 중심 `(4000,0,100)`, 각 Box Extent `(1500,1500,1000)`, Scale `(1,1,1)`, Arrival Offset `(0,0,0)`으로 두고 Bootstrap도 각각 같은 중심에 둔다. 실제 맵의 바닥 높이에 맞춰 Z를 조절한다. 이동은 3D 직선이며 NavMesh·충돌 회피·지면 추적을 하지 않는다. **Arrival 위치의 Z도 Box 중심 높이와 맞춘다.** 이 배치에서는 대략 10초 전후 이동이 보이며, 초기 스폰 슬롯과 개체별 도착 오프셋에 따라 시간이 달라진다. Arrival Spread를 늘리면 도착점이 더 퍼지지만 Bounds 내부로 제한된다.

M3 Box 템플릿은 이동 작성자가 하나여야 한다. PPO Herbivore, Custom/Spring Movement, Simulation LOD가 있으면 초기 검증이 이유를 출력하고 중단한다. 기존 Visualization/Replication LOD는 유지한다. 엔진 이동은 Off simulation LOD를 건너뛰므로 이 관찰 경로에서는 Simulation LOD Trait를 사용하지 않는다.

## 양쪽 또는 이동 중 고갈

새 PIE에서 A 명령을 실행하고 **도착하기 전에** `Debug.Starvation.Forest_B`를 입력한다. 다음 판단(기본 최대 1초의 시뮬레이션 시간)에서 이동 개체가 현재 위치에 멈추고 `WaitingForFood`가 된다. B 거주 개체도 기다린다. Travel 목적지는 초기화하지만 마지막 Region 소속과 ID는 유지한다. 도착하지 않은 A 개체는 A Pop에 포함되고, 이미 도착한 개체는 B Pop에 포함된다. 전체 합은 `초기 16 + 양쪽 고갈 전 성공한 웨이브 수`이며, 이주·대기만으로 변하지 않는다. 양쪽 Food=0 이후 예정된 추가 웨이브는 스킵되고 재스폰·왕복이 반복되지 않아야 한다. 식량 재생은 없으므로 초기 상태로 돌아가려면 PIE를 재시작한다.

## 도착 후 소비와 자동 고갈 확인

별도 원인 분석이 필요할 때만 Migration Enabled=true, Spawn Waves=false, Day/Night Event=false, Feeding Enabled=true, First Feed Delay=20, Interval=10, Amount=1로 설정하고 PIE를 재시작한다. 위의 전체 주기 확인에서는 Spawn Waves=true를 유지한다.

- **도착 후 소비:** A Food=40/B=400에서 A 명령을 입력한다. Traveling/Waiting 개체는 소비 요청을 만들지 않는다. 도착한 ID는 도착시각+10초부터 B 소비에 참여한다. 밀린 소비를 한꺼번에 지급하지 않는다. B의 기존 주민은 자기 예약을 유지하므로 지역 전체 소비 시각이 하나로 합쳐지지는 않는다.
- **소비 고갈:** A Food=24/B=400, 각 8개, 명령 없이 시작한다. A는 20/30/40초에 8씩 소비하고 40초 완료 단계부터 이주한다.
- **낮 이벤트:** A Food=40, Feeding=false, Day Event=true/Region=Forest_A/Food Loss=40. 낮 길이 60초, Phase Fraction=0.25이면 낮 시작+15초에 A가 고갈된다.
- **밤 이벤트:** B Food=40/A=400, Feeding=false, Day Event=false, Night Event=true/Region=Forest_B/Food Loss=40. 밤 길이 60초, Phase Fraction=0.25이면 밤 시작+15초에 B→A 이주한다.

설정 변경은 PIE 재시작 후 적용된다. Food Epsilon은 후보 판단에만 사용하며 작은 양수 식량을 장부에서 삭제하지 않는다. 지역 생성 상한 64는 이주 도착을 제한하지 않는다.

## Host/Client와 표시

GameMode의 GameState는 기존 `AEcoGameState` 또는 그 Blueprint여야 한다. Listen Server + Client에서 명령은 Host 창에서만 실행한다. 양쪽 화면의 지역 Food/Population/Traveling/Waiting과 Day/Night 잔여 시간은 **동일한 완료 요약 DTO**를 읽는다. Host 개체 라벨/화살표는 서버 Mass를 읽으며 자동 복제되지 않는다. Client Box의 Transform/Region은 기존 Bubble 경로로 전달된다. Client Bubble은 부분집합이므로 보이는 Box 개수를 전체 Population과 비교하지 않는다.

추가 수동 확인: 이동 후 Late Join, Bubble 범위 이탈/재진입, PIE 종료/재시작, 30/60 FPS 및 긴 프레임, 128개체 15분. 엔진 Movement는 한 프레임의 이동 적분을 최대 0.1초로 제한하므로 심한 hitch에서는 실제 이동 완료가 늦어질 수 있다. 밀린 자원 예약은 기존 프레임당 8단계 한도로 처리하며 실제 도착의 소비 예약은 과거 시각으로 소급하지 않는다.

표시를 숨기려면 Draw Migration Debug=false로 설정한다. 같은 프로세스 PIE의 화면 Print는 창 간 공유될 수 있으므로 `[Eco Authority/Client 월드이름]`과 Epoch를 함께 확인한다. World Partition을 사용할 때 테스트 Region/Bootstrap은 모두 로드되어 있어야 한다.

## 책임 분리

| 계층 | 구현 | 책임 |
| --- | --- | --- |
| Core | `EcoMigrationTypes.h` | Residence enum, 설정, UObject 없는 공간 값 계약 |
| World | `EcologyWorldSubsystem::BuildSpatialSnapshots` | Bounds/Arrival/인접 ID를 runtime index 순서의 값으로 제공 |
| Ecology | 기존 자원 조정 경로 | Starvation/소비/낮밤 이벤트, 완료 Food snapshot, Mass가 계산한 지역 집계 수신 |
| Mass | `EcoMassMigration.*`, Travel/Lifetime Fragment | 후보 선택, 상태 전이, 이동 의도, 도착 commit, 소비 예약 |
| 엔진 MassMovement | `UMassApplyMovementProcessor` | DesiredVelocity를 실제 Transform으로 적분 |
| 조정 경계 | `EcoMassLifecycleSubsystem` | 자원 완료→이주/도착→단일 Mass 집계→1초 요약 게시 순서 |
| Network | `AEcoGameState`, `FEcoCompletedWorldSummary` | 공통 Step/Revision의 시간+지역 묶음 복제. 기존 Bubble은 개체 Transform/Region 전달 |
| Debug | `EcoMigrationDebugSubsystem` | 수신 요약 및 서버 Mass의 읽기 전용 표시 |

`FEcoTravelFragment::State`가 Resident/Traveling/WaitingForFood의 유일한 기준이다. 이전 bool은 제거하고 예약된 `FEcoMigratingTag`는 사용하지 않으므로 이동 중 Archetype 변경/Deferred Tag 경합이 없다. Identity/Entity/Network ID를 바꾸거나 목적지에서 새 개체를 생성하지 않는다. Social Herd/Alarm/Shelter에는 이동 책임을 추가하지 않았다. Energy·기아 사망·Food 재생·PPO 관측/행동 확장은 이번 범위에 포함되지 않는다.
