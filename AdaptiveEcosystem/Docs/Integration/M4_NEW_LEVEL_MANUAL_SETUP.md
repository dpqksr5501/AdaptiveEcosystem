# 새 통합 레벨 수동 설정 — 팀 기능과 M4 Mass 연결

UE 5.8 / 현재 M4 working tree / 2026-10-13. **레벨 복사·Actor 배치·Blueprint 연결은 사용자가 한다.** 이 작업은 Source와 문서만 구현한다. 자동화 테스트는 생략하며 새 레벨의 PIE 통과는 직접 확인한 뒤 기록한다.

[A~F 코드·빌드 기록](M4_IMPLEMENTATION_PROGRESS.md) · [처리 책임/시간 계약](M4_RUNTIME_INTEGRATION_CONTRACT.md)

## 1. 레벨 복사와 기존 배치 확인

1. Editor/Live Coding을 닫고 최종 빌드 후 프로젝트를 연다.
2. Content Browser의 `/Game/Map/LV_Ecosystem_IntegrationTest`를 에디터의 레벨 복제 기능으로 복사한다. 새 이름은 예를 들어 `LV_Wonkii_Integration`이다. **이 이름의 레벨을 코드가 생성한 것은 아니다.** World Partition/External Actors를 유지하려면 에디터에서 복사·저장하고 파일 탐색기로 `.umap`만 복사하지 않는다.
3. 새 레벨을 열어 이름을 확인하고 Save All 한다. World Partition에서 동물을 놓을 terrain cell을 먼저 로드한다. Outliner의 `EcologyRuntime` 폴더를 확인한다.
4. 원본 테스트 맵에는 이미 Region 3, Coordinator 1, Shelter 2, FoodHint 3이 있다. 그대로 활용하거나 **기존 논리 배치를 정리한 뒤** 아래 순서로 다시 넣는다. Coordinator/같은 RegionId를 기존 것 위에 더 넣지 않는다. Landscape·수풀·물·조명과 기존 TriggerBox는 유지할 수 있다.

새 레벨은 경로 이름을 읽는 코드에 의존하지 않는다. 아래 RegionId/Groups/Config를 실제 배치와 일치시키면 된다. 비교를 쉽게 하려면 처음에는 `Forest`, `Barren`, `Highland` ID를 유지한다.

## 2. 필요한 Actor와 에셋

| 배치/연결 순서 | 선택할 대상 | 역할 / 핵심 설정 |
| --- | --- | --- |
| 1 | World Settings → GameMode Override | `EcoCreatureIntegrationGameMode`, 또는 이를 부모로 만든 사용자 BP GameMode. 이 클래스가 `EcoGameState`와 WorldEpoch를 초기화한다. 기존 플레이어가 필요하면 자식 GameMode의 Default Pawn Class에 기존 플레이어 BP를 지정한다. |
| 2 | `EcologyRegion` × 3 | 지역 bounds, 고유 RegionId, 초기 Food, 인접 지역, 도착 위치. 기존 TriggerBox만으로는 논리 지역이 등록되지 않는다. |
| 3 | `EcoCreatureIntegrationSpawner` × **1** | 초기 Entity 생성, 공통 생존/자원/사망/이주·집계 조정. native Actor 또는 기존 `BP_EcoCreatureIntegration`을 사용하고 아래 값을 인스턴스에서 설정한다. |
| 4 | `EcoShelterAnchor` | 수풀/차폐 위치의 예약·이동·점유. 실제 슬롯 지면이 평탄한 곳에 배치한다. |
| 5 | `PlayerStart`와 플레이어 Pawn | 관찰/네트워크 viewer. 실제 동물 스폰 근처에 둔다. 플레이어를 위협으로 시험할 때 Pawn BP에 `EcoThreatSourceComponent`를 추가한다. |
| 6 | 기존 Sky/Weather Actor + 사용자 Adapter BP | E 단계에서 `EcoRegionEnvironmentAdapter`를 부모로 BP를 만들고 기존 하늘/날씨 Actor 참조를 연결한다. |

**따로 배치하지 않을 대상:** `EcoMassNetworkBootstrap`(Box), 일반 MassSpawner, 사슴/늑대 표현 BP, Policy/Social Processor. 이 레벨의 coordinator가 논리 Entity와 수동 표현을 생성하고 Processor는 엔진의 Mass 실행 경로에서 동작한다. 기존 Bootstrap 가드를 제거하지 않는다.

Coordinator Details의 참조:

| 필드 | 지정할 에셋 |
| --- | --- |
| Herbivore Config | `/Game/Creatures/Integrated/DA_EcoDeer` |
| Wolf Config | `/Game/Creatures/Integrated/DA_EcoWolf` |
| Herbivore Actor Class | `/Game/Creatures/Integrated/BP_EcoDeer` |
| Wolf Actor Class | `/Game/Creatures/Integrated/BP_EcoWolf` |
| Footstep Audio Set | `/Game/Audio/Footsteps/Settings/DA_EcoFootsteps` |

EntityConfig의 `Eco Integrated Creature` trait은 사슴에서 Predator=false, 늑대에서 true다. 내부에서 역할별 Policy/Social/Senses/CustomMovement를 조립한다. 추가 이동 Trait를 임의로 합치지 않는다. 저장된 Config를 재사용하고 서버/클라이언트 모두 같은 에셋을 사용한다. Config를 별도로 복제하면 새 GUID가 생기므로 양쪽 참조도 그 새 에셋으로 함께 맞춘다.

## 3. Region과 Groups 맞추기

기존 terrain을 복사했을 때 사용할 초기값:

| RegionId | Region 위치 XYZ / Box Extent XYZ (cm) | 초기 Food / Capacity | 인접 ID | Groups: 사슴 / 늑대 |
| --- | --- | --- | --- | --- |
| Forest | `(0,50000,0)` / `(75000,25000,15000)` | 1400 / 2000 | Barren | 8 / 1 |
| Barren | `(0,0,0)` / `(75000,25000,15000)` | 500 / 1000 | Forest, Highland | 4 / 1 |
| Highland | `(0,-50000,0)` / `(75000,25000,15000)` | 600 / 1200 | Barren | 4 / 1 |

Box Extent는 반길이다. Region의 Scale은 처음에 `(1,1,1)`로 유지한다. **Groups에 각 RegionId와 초기 개체 수를 동일하게 입력한다.** 새 지역을 쓰면 이 표의 ID 대신 실제 ID를 양쪽에 입력한다.

- Region: Food Regeneration Rate=0, Rainfall Affects Regeneration=false, Ecological Comfort Population=64로 시작한다. Temperature/Humidity는 지역별 기존 값 유지, Rainfall은 0..1이다.
- Coordinator: Global Population Limit=64 이상(표 합계 19), Day/Night Seconds=60/60, Enable Waves=false, Population Pressure=true. Groups → Schedule → Region Population Limit은 해당 초기 **사슴+늑대 합계 이상**이어야 한다.
- 실맵에서는 Groups → Herbivore Spawn Points / Wolf Spawn Points에 **world-space XYZ**를 인원 수만큼 넣는다. 기존 배열을 유지하면 기존 안전 지점으로 시작한다. 빈 배열은 Region 중심 주변 자동 링이므로 중심이 물/낭떠러지인 큰 맵에서는 쓰지 않는다.
- 위치를 바꿀 때는 TargetPoint를 임시 표식으로 놓고 지면의 XYZ를 읽어 배열에 입력한다. 스폰 힌트의 Z도 실제 지면 근처로 둔다. 시작 전에 모든 좌표가 지역 안이며 바닥 충돌·경사·장애물·금지 영역 검사를 통과해야 한다.
- Food Patch Position은 **world-space**다. Use Food Patch Position=true로 켜고 먹이 밀도 중심 좌표를 입력한다. FoodHint/TargetPoint는 표식이며 FoodAmount를 소유하거나 소비하는 식물이 아니다.
- Region → Arrival Offset은 **지역 Actor 기준 local-space**다. `도착 world 위치 - Region 위치`(회전/Scale=기본인 경우)를 입력한다. 기본 맵의 도착 XY는 Forest `(34000,30000)`, Barren `(34000,20000)`, Highland `(34000,-30000)`이다. Z는 해당 위치의 실제 지면이다. 지면·지역 내부를 확인하고 월드 좌표를 Offset에 그대로 넣지 않는다.
- 물의 `NavModifierVolume`/`NavArea_Null`과 지형 충돌을 유지한다. 현재 이동은 지면·장애물·금지 구간을 검사한다. NavMesh를 배치했다고 우회 경로 탐색이 자동 연결되는 것은 아니다. 첫 이주 확인은 물/큰 장애물이 없는 두 지역의 짧은 연결 구간으로 한다.

World Partition에서는 Coordinator, Regions, Shelter Anchors, 환경 Adapter, 물 금지 Volume, PlayerStart의 **Is Spatially Loaded를 끄고** 처음에는 항상 활성 Data Layer에 둔다. Coordinator → Use Habitat Streaming=true, Radius=10000cm로 시작한다. 이 authority source가 스폰·현재 개체·도착점 주변 collision을 유지한다. Client는 자기 viewer에 따른 일반 streaming을 사용한다.

## 4. 배치 검사 버튼

Coordinator 선택 → Details의 Creature → Setup → **Validate Editor Setup** 클릭 → Output Log에서 `[Eco Setup]` 검색한다.

- `Errors=0`: 고유 ID, Groups, Config 역할, 표현 종, 수량/상한, 인접 ID, 좌표 범위 등 기본 연결을 통과했다.
- Note의 Is Spatially Loaded/스폰 링/Audio/Shelter 경고도 확인한다. 지면과 이동 경로는 별도로 확인한다.
- 이 버튼은 Entity를 만들거나 Actor/에셋/레벨을 수정·저장하지 않는다. PIE 시작 시 동일 기본 검사와 실제 서버/클라이언트 template fragment 검사도 수행한다.

## 5. A~F 실행 순서와 통과 기준

각 단계를 마친 뒤 설정을 기록하고 다음 단계로 간다. 수량/Config/예산을 바꾸면 PIE를 종료하고 다시 시작한다.

| 단계 | 이번 단계의 최소 설정/조작 | 확인할 결과 |
| --- | --- | --- |
| A: 기본 연결 | 처음엔 Forest 사슴 2, 나머지/늑대 0으로 Standalone. 성공 후 표의 19개체로 확대. `eco.Integration.Dump details` | Ready=1, 초기 Births=설정 합계, Runtime stopped 없음. coordinator는 하나이고 지면 위에서 종별 단일 movement가 실행된다. |
| B: 복제 | Play → Players=2, Play As Client/전용 서버. 가능하면 별도 프로세스. 서버 `eco.M4.TraceSamples 1`, 양쪽 `eco.M4.Dump details` | Client LogicalOwned=0, 현재 proxy/Actor 수신. 이동 serial과 VisualRevision 분리, flag/velocity 수신, Off→재진입/재접속, 작은 `eco.M4.Teleport <ID> X Y Z` reset. 지연/손실은 별도 조건으로 시험. |
| C: PPO·Social·감각 | V1 정책/LOD 기본 유지. `t.MaxFPS 20/30/60`, `eco.Social.ActionAudit 1`, `eco.Shelter.Log 1`, `eco.Creature.DrawFacing 1` | 약 7.5 결정/개체·초, 죽은 개체 제외, 실제 속도와 heading 일치. Raw→Effective→Request→이동→Feedback. Anchor Capacity=4/Radius=150/Quality=.65에서 Moving→Occupied→해제. |
| D: 생존·자원·이주 | 서버 `Debug.Starvation Forest`, 이후 별도 실행 `Debug.FoodSupply Forest 100`; `eco.M4.SetVitals <ID> 1 0` 또는 `0 0` | 지급량만 Energy 반영, 기아/피식/외부 피해 구분, Death 한 번, 예약 해제, 같은 ID 도착. GameState Species row의 Population=Births−Deaths+MigrationIn−MigrationOut. |
| E: 환경 폐루프 | 아래 BP 연결 후 Region Rate=2, rainfall response=true, Dry=.5/Wet=1.5. 같은 FPS에서 Rainfall=0/1 비교 | 실제 공급 1/3 Food/s(잔여 capacity 제한) → ObsFood/Raw/Social/소비·인구 → 다음 관측. Client 하늘/날씨는 완료 DTO로 표시한다. |
| F: 예산·규모 | 먼저 Relevant=8/Actor=4/Adds=2로 19개체 연결 테스트. 이후 64→128→256→512 확대 시 안전 좌표/지역·세계 상한도 함께 확대 | Bubble 합산 상한, Actor+pool 상한, BudgetDeferredAdds, 재바인딩 reset. opt-in worker/LOD와 기능·CPU/packet 비용을 각각 확인한다. |

D의 늑대 생존은 처음엔 꺼둔다. 별도 조건에서 Predator Survival=true, Drain=1, Capture Gain=25로 설정해 실제 포획만 Energy 보상하고 먹잇감이 없으면 기아 사망하는지 확인한다. 과밀은 Food 충분/Region Comfort를 초기 수보다 작게 한 별도 조건에서 확인한다. 웨이브를 켤 때는 Day/Night Count만큼의 안전한 스폰 좌표와 Food·cap을 준비한다.

F의 `eco.Policy.Parallel 1`은 이번 실행의 due 개체가 64 이상일 때만 ParallelFor 경로를 쓴다. `eco.Integration.Dump`의 **ParallelDecisions**로 확인한다. 작은 fixture에서 1로 켜고 값이 0인 것은 오작동이 아니다. Simulation LOD=true/Far Distance=20000/Far Multiplier=4 비교에서는 위협·예약·이주 중 full-rate 복귀, 화면 밖 생존/lease/인구 유지가 필수다.

상한 도달 시 기존 관련 개체를 유지하고 새 후보를 보류하는 admission 정책이다. 가까운 새 공격 대상을 무조건 우선 evict하는 기능으로 읽지 않는다. 성능 측정 때 `eco.Integration.LogDetails 0`, `eco.M4.TraceSamples 0`, Print Resource Changes=false, 감각/방향 draw·상세 로그 off로 바꾸고 PIE를 재시작한다. 지원 규모는 실제 CPU/packet/메모리·장기 수명 결과를 기록한 범위만 선언한다.

## 6. 기존 날씨/하늘 Blueprint 연결

직접 만들 BP의 예시 이름: `BP_WonkiiEnvironmentBridge` / 부모: `EcoRegionEnvironmentAdapter`. 레벨에 하나 배치하고 Sky Actor/Weather Actor 참조 변수를 만든 뒤 인스턴스에서 기존 `/Game/Actors/BP_SkyManager`, `BP_WeatherManager` 또는 `BP_WeatherManager_PlayerFollow`를 지정한다. 기존 BP의 실제 함수·변수 이름을 확인해 아래 이벤트에 연결한다. 여기에 적은 이벤트는 **새 native Adapter API**이며 기존 Sky BP에 이미 같은 함수가 있다고 가정하지 않는다.

```text
서버/Standalone의 Weather Manager (정규화 강수 0..1)
  → Adapter.ApplyRainfall(Rainfall, WeatherState)
  → Region World 입력 → Ecology 완료 step → GameState summary

Adapter.OnEnvironmentUpdated(RegionId, Environment)
  → 기존 Weather BP의 비/구름/Niagara 표시 입력
Adapter.OnClockUpdated(Phase, PhaseProgress)
  → 기존 Sky BP의 해/밝기/시간 표시 입력
```

1. 기존 Sky BP의 자체 낮밤 자동 갱신을 끄거나 해당 갱신 경로를 분리하고, coordinator clock을 유일한 시간 입력으로 사용한다. PhaseProgress는 **해당 phase의 0..1**이며 하루 전체 비율이 아니다. Day/Night를 Switch해 각각 작성한 curve로 표시한다. 현재 fixed clock은 Day/Night를 제공한다.
2. 논리 날씨 입력 생산은 서버/Standalone에서만 한다. BP에서는 `Get Game Mode → Is Valid`로 authority world를 확인하고, Coordinator `Is Runtime Ready` 뒤 ApplyRainfall을 호출한다. 비복제 배치 Actor의 Switch Has Authority만으로 월드 권위를 판단하지 않는다. Native 함수도 NM_Client 쓰기를 거부한다.
3. ApplyRainfall은 지역별 Temperature/Humidity를 보존한다. 전체 환경을 의도적으로 교체할 때만 `ApplyWeather`를 쓴다. RegionIds가 비면 전체 등록 지역, 특정 지역만 적용하려면 실제 ID 배열을 지정한다.
4. 기존 BP가 강수량을 0..100으로 제공하면 100으로 나눠 0..1로 연결한다. 반환값 false면 초기화/대상 ID를 확인하고 ready 이후 다시 전달한다. 자체 Weather 입력을 연결할 때 Apply Authored Weather=false로 둬 매 tick 값이 덮어써지지 않게 한다. 간단한 고정 날씨 시험은 true+Authored Weather를 사용한다.
5. Client의 OnEnvironmentUpdated/OnClockUpdated는 **표시 전용**으로 연결한다. 그 이벤트에서 논리 ApplyWeather를 다시 호출하거나 Client가 날씨를 무작위 결정하도록 연결하지 않는다. 플레이어 따라가는 비 효과의 위치 갱신과 논리 날씨 선택은 구분한다.

Player 위협 시험은 Pawn의 EcoThreatSourceComponent에서 Threat Enabled=true, Strength=1로 시작하고 접근 후 false로 바꿔 Alarm 감쇠/해제를 확인한다. 이 입력은 Social 위협이다. V1에 새로운 플레이어/강수량 관측을 추가한 것으로 해석하지 않는다.

## 7. 막힐 때 확인 순서

| 증상 | 먼저 볼 설정 |
| --- | --- |
| 시작 실패/Errors>0 | GameMode·WorldEpoch, 중복 coordinator/RegionId, Groups ID, Schedule/Global cap, Config Predator 역할, 로드된 cells |
| 바닥 스폰 실패 | 좌표가 world-space인지, 실제 지면 Z 근처인지, WorldStatic 충돌·경사·금지 Volume·Habitat Streaming |
| 동물은 있는데 Client에 안 보임 | 저장된 동일 Config/GUID, viewer와 실제 스폰 거리, 실제 Config Replication LOD 거리, Bubble PendingAdds, Actor cap |
| Shelter 미도착/이주 정지 | 목적지 지면/경계/장애물/물 금지 구간, Shelter 슬롯의 평탄성, Native 로그의 Request/Feedback·예약 해제 |
| 먹이가 없어도 반복 생성/시연 유지 | Waves/재생/수동 공급을 기록. 재스폰·공급이 꺼진 baseline과 별도 비교 |
| Client 날씨/시간 미표시 | Adapter BP가 Client에 로드됐는지, 항상 활성 Data Layer, 실제 이벤트→시각 함수 연결, GameState 완료 summary |

자동 배치 Python 도구는 이 수동 설정 작업에서 실행하지 않는다. 새 레벨의 에셋 변경·배치·GUI/오디오/성능 통과 기록은 사용자가 수행한 결과를 기준으로 남긴다. V3·식물 자원·다종·두 대륙/저장 복원은 기존 계약과 모델 산출물이 필요한 후속 범위다.
