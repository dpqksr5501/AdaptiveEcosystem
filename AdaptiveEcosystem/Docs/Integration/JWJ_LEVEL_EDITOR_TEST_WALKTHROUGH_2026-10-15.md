# Integration_JwJ 실제 구성과 에디터 선택 순서

확인일: 2026-10-15 KST / M4 HEAD `67c860c` / UE 5.8.

현재 열린 `/Game/JWJ/Integration_JwJ`의 Actor·Config·지역·은신처·Navigation을 읽기 전용으로 조사했다. Outliner는 **162 actors / 162 loaded**였다. `ValidateEditorSetup`은 **Errors=0, Notes=2**였다. 배치 검사 결과이며 지면·경로·게임 실행 통과를 뜻하지 않는다. 이번 작업에서 레벨 복제·설정 변경·저장·PIE·빌드는 하지 않았다.

## 1. 사용할 두 레벨

| 레벨 | 목적 | Config |
| --- | --- | --- |
| `/Game/JWJ/Integration_JwJ` | 기존 PPO/M4 기준선과 생태·Social·복제 회귀 | 기존 DA_EcoDeer / DA_EcoWolf |
| `/Game/JWJ/Integration_JwJ_SpeciesAI` | 사용자가 만들 복사본. 정책 비교·종별 독립 개발·새 이동/예약/공격 | 단계별 EC_DeerV1 / EC_Deer / EC_Wolf |

두 번째 레벨 이름은 제안이며 **아직 생성하지 않았다**. 먼저 현재 레벨을 복사한 뒤 원본을 다시 열어 PPO 검증을 시작하면 초기 배치를 보존할 수 있다.

레벨만 복사하면 Config/Profile/Blueprint/오디오와 Project Settings는 공유된다. 복사본에서는 Actor 인스턴스의 값과 참조를 바꾼다. 기존 DA_EcoDeer/DA_EcoWolf를 SpeciesAI용으로 수정하지 않는다. 기존 Sky/Weather BP 그래프 자체를 바꿀 경우 해당 BP도 별도로 복제한다.

## 2. 실제 구성요소 조사 결과

### 2.1 Outliner에서 선택할 이름

| 실제 이름 | 현재 상태 | 역할 |
| --- | --- | --- |
| `Eco_CreatureRuntime` | 정확히 1개, EcologyRuntime/Coordinator | Entity 생성·공통 생존/자원/사망/이주·집계 |
| `Eco_Region_Forest`, `Eco_Region_Barren`, `Eco_Region_Highland` | 3개 | 실제 논리 지역, 초기 Food·인접 지역·도착 위치 |
| `Eco_Shelter_Forest_01`, `Eco_Shelter_Forest_02` | Forest에 2개 | Social Shelter 예약·이동·점유 |
| `Eco_FoodHint_Forest/Barren/Highland` | TargetPoint 3개 | 먹이 위치 표식. 자원 잔고·섭식 슬롯의 소유자가 아님 |
| `TV_Region_Forest/Barren/Highland` | TriggerBox 3개 | 지형 구역 표시. EcologyRegion을 대신하지 않음 |
| `TP_Shelter_Forest_01` | TargetPoint | 은신처 배치 표식. 실제 예약 Actor는 Eco_Shelter |
| `NavMeshBoundsVolume` | 1개 | Navigation 범위 |
| `RecastNavMesh-Default` | Static, radius35cm / height144cm / slope44도 | 기존 NavMesh 데이터 |
| `NavModifierVolume`, `NavModifierVolume2` | NavArea_Null 2개 | 이동 금지 구간 |
| `PlayerStart` | `(34200,48500,-600)`cm | Forest 관찰 시작점 |
| `BP_SkyManager` | 1개 | 기존 하늘 표시 |
| `BP_WeatherManager_PlayerFollow` | 1개 | 기존 플레이어 주변 날씨 효과 |
| Landscape·StreamingProxy·Foliage·Lighting 등 | 나머지 환경 | 지형·충돌·식생·표현 |

조사된 Actor 중 **Box Bootstrap, 환경 Adapter, SpeciesAI ActivitySite, SpeciesAI Fixture는 없다**. 하늘·날씨 Actor가 있다는 사실만으로 Ecology clock/강수량 인계가 연결됐다고 판단하지 않는다. 이번에는 기존 BP 내부 그래프를 조사하지 않았다.

coordinator·3개 Region·2개 Shelter·FoodHint·PlayerStart·Sky/Weather·주요 Nav Actor의 Is Spatially Loaded는 모두 false였다.

### 2.2 Eco_CreatureRuntime 현재 값

| Details 필드 | 실제 값 |
| --- | --- |
| Enabled Species / Enable Species AI Fixtures | Both / false |
| Herbivore Config / Wolf Config | 기존 DA_EcoDeer / DA_EcoWolf |
| Herbivore Actor Class / Wolf Actor Class | 기존 BP_EcoDeer / BP_EcoWolf |
| Footstep Audio Set | `/Game/Audio/Footsteps/Settings/DA_EcoFootsteps` |
| Global Population Limit | 64 |
| Day Seconds / Night Seconds | 60 / 60 |
| Enable Waves | false |
| Use Habitat Streaming / Radius | true / 10000cm |
| Energy Drain Per Second / Energy Per Food | 1 / 5 |
| Starvation Grace / Damage Per Second | 0 / 5 |
| Enable Predator Survival | false |
| Predator Drain / Energy Per Capture | 1 / 25, 생존을 켠 시험에서 사용 |
| Enable Population Pressure / Migration Enabled | true / true |
| Migration Speed / Arrival Radius / Spread | 400cm/s / 30cm / 300cm |
| Interpolation Delay / Host Visual Distance | 0.1초 / 20000cm |
| Enable Simulation LOD | false |
| Far Simulation Distance / Far Policy Interval Multiplier | 20000cm / 4 |

실제 두 EntityConfig에는 Eco Integrated Creature Trait가 각각 1개 있다. 사슴 Predator=false, 늑대=true다. **두 Config 모두 Use Species AI=false, Species AI Profile=None**이므로 현재는 기존 PPO/M4 경로다.

### 2.3 Groups·지역·좌표

아래 표는 현재 값이며 시험 후 복원 기준이다. 좌표는 cm, 표시 Z는 반올림했으므로 기존 배열의 원래 정밀도는 유지한다.

| Groups | Region Id | Herbivores / Wolves | Spawn Points 수 | Food Patch Position: world |
| --- | --- | --- | --- | --- |
| Index0 | Forest | 8 / 1 | 8 / 1 | `(34200,46500,-1631.26)` |
| Index1 | Barren | 4 / 1 | 4 / 1 | `(34000,1000,1663.26)` |
| Index2 | Highland | 4 / 1 | 4 / 1 | `(34000,-49000,2639.84)` |

모든 Group의 Use Food Patch Position=true, Schedule Region Population Limit=64다. Day/Night wave count는4/6이지만 Enable Waves=false이므로 반복 생성하지 않는다. 초기 합계는 **사슴16+늑대3=19**다.

| 선택할 Region | Initial Food / Capacity | 재생률 / Rainfall Response | Adjacent | Arrival Offset: local |
| --- | --- | --- | --- | --- |
| Eco_Region_Forest | 1400 / 2000 | 0 / false | Barren | `(34000,-20000,-1140.63)` |
| Eco_Region_Barren | 500 / 1000 | 0 / false | Forest, Highland | `(34000,20000,72.65)` |
| Eco_Region_Highland | 600 / 1200 | 0 / false | Barren | `(34000,20000,2553.12)` |

Region Actor 위치는 Forest `(0,50000,0)`, Barren `(0,0,0)`, Highland `(0,-50000,0)`, Scale은 모두1이다. RegionBounds Box Extent는 모두 `(75000,25000,15000)`이다. 실제 도착점 world XY는 Forest `(34000,30000)`, Barren `(34000,20000)`, Highland `(34000,-30000)`이다. **Arrival Offset에 world 좌표를 그대로 넣지 않는다.**

Forest/Barren/Highland 온도는20/30/-5, 습도0.7/0.2/0.4, Rainfall은 모두0이다. 이 값은 World 환경 입력이며 FoodAmount를 대신하지 않는다.

Shelter 둘 다 Capacity4 / Quality0.65 / Radius150cm다. 위치는01 `(33300,45100,-1603.13)`, 02 `(34200,44400,-1606.26)`이다.

## 3. 레벨 복사: 선택 순서

1. 현재 레벨 탭이 **Integration_JwJ**인지 확인한다.
2. **File → Save Current Level As…**를 선택한다. 현재 Editor에 이 메뉴가 있음을 확인했다. 단축키는 Ctrl+Alt+S다.
3. 저장 창에서 **Content → JWJ**를 선택한다.
4. 이름을 **Integration_JwJ_SpeciesAI**로 입력하고 저장한다. 기존 레벨을 덮어쓰지 않는다.
5. 새 탭 이름과 경로를 확인한다. World Partition 관련 Actor는 Editor가 처리하게 하고 Explorer에서 .umap만 복사하지 않는다.
6. Outliner 검색을 비워 Region3/coordinator1/Shelter2가 유지되는지 확인한다. World Settings의 GameMode도 확인한다.
7. **File → Save All**로 복사본을 저장한다.
8. **Content Drawer → Content/JWJ → Integration_JwJ 더블클릭**으로 원본을 다시 연다.

아래 원본 검증이 끝나면 복사본으로 이동한다. 이번 작업은 이 복제를 대신 실행하지 않았다.

## 4. 원본 PPO/M4: 기본 설정 선택 순서

### P0. World Settings 선택

1. 오른쪽 아래 **World Settings 탭**을 선택한다. 없으면 Window 메뉴에서 연다.
2. 검색에 GameMode를 입력한다.
3. **GameMode Override=EcoCreatureIntegrationGameMode**를 확인한다. 현재 이미 맞게 설정되어 있다.
4. 프로젝트 기본 ThirdPerson GameMode로 바꾸지 않는다. 기존 플레이어 BP가 필요하면 통합 GameMode의 자식에서 Default Pawn Class를 설정한다.

Validate의 GameMode Note는 Editor World에서 출력되는 일반 안내다. 현재 Override가 잘못됐다는 뜻은 아니다. 게임 시작 시 WorldEpoch는 별도로 검사한다.

### P1. Runtime Actor 선택

1. **Outliner 검색 → Eco_CreatureRuntime → 동일 이름 Actor 선택**.
2. Details 상단에서 **Actor 인스턴스 본체**를 선택한다. HabitatStreamingSource 컴포넌트가 아니다.
3. Details의 **All**을 선택한다. 검색에 Herbivore Config를 입력해 기존 DA_EcoDeer를 확인한다. Wolf Config도 DA_EcoWolf인지 확인한다.
4. Enabled Species=Both, Enable Species AI Fixtures=false를 유지한다.
5. Enable Waves=false, Enable Predator Survival=false, Enable Simulation LOD=false를 유지한다.
6. Groups를 펼쳐 Region Id를 읽고 현재 수량 표와 대조한다. 기존 스폰 배열·Food Patch는 유지한다.
7. Details 검색을 비우고 **Creature|Setup → ValidateEditorSetup** 버튼을 누른다.
8. 하단 **Output Log**에서 `[Eco Setup]`을 검색하고 Errors=0을 확인한다.

필드가 보이지 않으면 Actor 본체/All/검색 필터를 먼저 확인한다. 필드명을 하나씩 검색하면 긴 Details에서 카테고리를 찾기 쉽다.

### P2. 실제 Region 선택

1. Outliner 검색을 **Eco_Region_**으로 바꾼다.
2. Forest 선택 → Initial Food Amount1400, Food Capacity2000 확인.
3. Food Regeneration Rate0, Rainfall Affects Regeneration=false 확인.
4. Barren/Highland도 위 현재 값 표와 대조한다.
5. Environment State의 Food Availability를 실제 초기 Food 잔량 설정으로 사용하지 않는다.
6. TV_Region이나 FoodHint에서 이 값을 찾지 않는다. 실제 자원 초기값은 Eco_Region에 있다.

### P3. Play 메뉴 선택

1. 상단 Play 오른쪽 **세로 점 세 개 메뉴**를 연다.
2. **Number of Players=1**.
3. **Net Mode → Play Standalone**.
4. **Spawn Player At → Default Player Start**.
5. 첫 별도 창 확인은 **Standalone Game**을 선택한다. 실행 중 Actor 값을 볼 다음 시험은 **New Editor Window (PIE)**를 사용한다.
6. 저장 요구 시 대상 레벨 이름을 확인하고 저장한다. 조건 변경은 실행을 종료한 뒤 수행한다.

조사 시 현재 UI는 Selected Viewport / Players1 / Play Standalone / Default Player Start였다. 저장 ini의 과거 Simulate 이력과 구분했다.

### P4. 시작 후 확인

게임 콘솔 또는 해당 게임 World의 Output Log에서 실행한다.

```text
eco.UseLearnedPolicy 1
eco.Policy.PredationSource 0
eco.Policy.Parallel 0
eco.Integration.Dump details
eco.M4.Dump details
```

1. Ready=1, 초기 Births19, Fatal/Assertion/Runtime stopped 없음 확인.
2. 현재 Alive는 사망 후19보다 작아질 수 있다. Births와 Alive를 구분한다.
3. 이동·방향·발소리·Shelter를 관찰한다. 현 초기 종간 거리가 짧아 과거에는 Forest에서 연속 Predation이 빨랐다. 오래 생존하는 것을 최초 연결의 유일한 성공 조건으로 삼지 않는다.
4. 종료 후 실제 결과를 기록한다. 이 안내서는 새 게임 테스트 성공 기록이 아니다.

## 5. 원본 PPO/M4: 기능을 하나씩 검증

### P5. 정책 주기·방향·죽은 개체 제외

**선택:** Eco_CreatureRuntime → Details → Enabled Species/Groups.

1. Enabled Species=DeerOnly, Forest Herbivores2, Barren/Highland Herbivores0, Wolves 모두0.
2. 기존 스폰 배열은 지우지 않는다. 원인 분리 중에만 Migration→Enabled=false, Enable Population Pressure=false.
3. Waves/재생/predator survival/LOD/worker는 off. New Editor Window PIE, Net Mode=Play Standalone으로 시작한다.
4. `t.MaxFPS 20`, `t.MaxFPS 30`, `t.MaxFPS 60`을 별도 실행하고 동일 생존 ID의 Decisions/AliveSeconds 약7.5/초를 확인한다.
5. `eco.Creature.DrawFacing 1`로 실제 속도와 모델 방향을 비교한다.
6. 서버에서 `eco.M4.SetVitals <ID> 0 0`을 실행한다. 다음 생존 step 이후 dead 이동·관측 제외와 단일 Death를 확인한다.

### P6. 기아와 실제 먹이 지급

**선택:** Runtime은 P5 소수 구성, Region은 Eco_Region_Forest.

1. Migration/Pressure off, 늑대 없음, 재생0, wave off를 확인한다.
2. 실행 후 `Debug.Starvation Forest`, `eco.M4.SetVitals <ID> 1 0`.
3. HP감소→Starvation→예약 해제→cleanup 확인. 기아가 PredationHistory를 올리면 실패다.
4. 별도 실행에서 살아 있는 개체에 `Debug.FoodSupply Forest 100`을 주고 Granted/TotalFood와 Energy 변화를 확인한다.
5. Alive=Births−Deaths 확인. 공급은 사망한 개체를 되살리지 않는다.

### P7. 실제 이주·지역 회계

**선택:** Runtime→Migration/Groups, Region→Adjacent Region Ids/Arrival Offset.

1. 늑대0, Forest2/Barren2 등 소규모로 설정하고 Migration Enabled=true로 복원한다.
2. Forest↔Barren 인접 ID·안전한 도착점·지형 cell을 확인한다.
3. `Debug.Starvation Forest` 후 동일 StableAgentId의 실제 Barren 도착을 추적한다. 이동 의도만으로 성공 처리하지 않는다.
4. GameState Ecology Summary에서 지역×종 Population=Births−Deaths+MigrationIn−MigrationOut을 확인한다.
5. 과밀은 별도 실행에서 Food 충분/Pressure=true/Comfort Population을 초기 수보다 작게 설정해 확인한다. 기아와 원인을 섞지 않는다.

### P8. Social Shelter

**선택:** Eco_Shelter_Forest_01/02, Runtime, 필요하면 실제 플레이어 Pawn BP.

1. Capacity4/Quality0.65/Radius150 유지. 실제 차폐와 도착 지면 확인.
2. `eco.Shelter.Log 1`, `eco.Social.ActionAudit 1` 활성화.
3. 늑대를 복원하거나 EcoThreatSourceComponent를 명시적으로 붙인 Pawn을 사용한다. PlayerStart 자체는 위협 소스가 아니다.
4. Reserved→Moving→Occupied, 위협 해제·사망·이주 시 release와 슬롯 재사용 확인.
5. 기존 PPO는 NavMesh가 있다는 이유만으로 새 SpeciesAI 우회 경로를 사용하는 것이 아니다.

### P9. Client·보간·reset

**선택:** Play 세로 점 메뉴 → Number of Players/Net Mode.

1. PIE 종료 → New Editor Window PIE / Number of Players2 / Net Mode→Play As Client.
2. 실제 Client 창2개 확인. Play As Listen Server와 구분한다.
3. Client에서 `eco.Integration.Dump details`, `eco.M4.Dump details`. LogicalOwned0·proxy/Actor 수신 확인.
4. 서버 로그/서버 World에서 `eco.M4.TraceSamples 1`. 같은 이동 serial에서도 새 VisualRevision이 수신되는지 본다.
5. teleport는 서버에서 `eco.M4.Teleport <ID> X Y Z`. 숨겨진 Dedicated에 명령을 넣을 수 없는 실행 구성이라면 server console/별도 서버를 준비한다. Client에 입력한 것으로 성공 처리하지 않는다.
6. 거리 이탈·재진입·늦은 접속·동일 서버 재접속을 각각 기록한다.
7. Advanced Settings의 Network Emulation100ms/1%는 별도 조건으로 시험한다.

### P10. 원본 값 복원

Runtime Both, Groups8/1·4/1·4/1, Migration/Pressure=true로 복원한다. 현재 값 표의 나머지도 대조해 기준 설정으로 저장하고 Validate한다. 변경한 공유 Project Settings가 있으면 기록한 원래 값으로 복구한다.

## 6. 복사본에서 정책만 비교

1. Content/JWJ에서 **Integration_JwJ_SpeciesAI**를 열고 탭 이름 확인.
2. **Runtime → Herbivore Config만 EC_DeerV1으로 변경**.
3. Wolf Config는 기존 DA_EcoWolf, 표시BP/Audio/Groups/지역/생존/이동은 원본과 동일하게 유지.
4. Both, Fixtures=false, LOD/worker off, PredationSource0 유지.
5. Validate→PIE, `eco.SpeciesAI.Status`로 V1 cohort 확인. 기존 PPO는 기존 Dump 사용.
6. 같은 시점의 관측·결정·섭식·생존·비용 기록. PPO와 V1 StateTree의 최초 결정 위상 일치는 아직 검증되지 않았다.

이 단계에서 full EC_Deer·새 늑대·NavMesh·슬롯 생활을 동시에 바꾸면 전체 시스템 비교가 된다.

## 7. 복사본에서 full SpeciesAI: 선택 순서

### S0. 공통 Navigation·사슴1마리

1. **Runtime → Enabled Species=DeerOnly / Herbivore Config=EC_Deer**. Wolf Config는 비워도 된다.
2. Forest Herbivores1, 다른 지역0, Wolves0, Fixtures=false. 단독 시험 중 Migration/Pressure만 off.
3. Waves=false, Predator Survival=false. 기존 표시BP/Footstep Audio Set 유지.
4. **Outliner → NavMeshBoundsVolume** 선택. Forest 스폰·FoodHint·Shelter를 덮는 범위 확인.
5. 지형 cell을 로드하고 **Build → Build Paths**로 Navigation 구축. Viewport의 `P`로 연속된 녹색 이동면 확인.
6. **RecastNavMesh-Default** 선택. 현재 몸체35/144와 기본 SpeciesAI Profile30/130의 차이를 기록한다. 현 NavData에서 runtime 등록이 수락되는지 확인한다.
7. `Missing supported NavMesh`로 거부되면 **Edit → Project Settings → Navigation System → Supported Agents**에서 기존 agent를 보존하고 SpeciesAI용30/130을 구성한 뒤 해당 레벨 Navigation을 다시 빌드한다. 공유 Project Settings 변경임을 기록한다.
8. DefaultMass.ini의 stock height writer 제외를 유지한다. Movement/StateTree/SmartObject Trait를 Config에 중복 추가하거나 가드를 제거하지 않는다.
9. Validate→PIE, `eco.SpeciesAI.Status`, `eco.SpeciesAI.Capture`에서 Deer1/Wolf0·경로 상태 확인.

full SpeciesAI의 tier scheduler와 기존 Runtime Enable Simulation LOD를 같은 기능으로 취급하지 않는다.

### S1. Graze 장소 추가

1. **Eco_FoodHint_Forest** 선택 → Location 확인. 현재 `(34200,46500,-1631.26)` 부근.
2. **상단 +Add/Place Actors 클래스 검색 → EcoSpeciesAIActivitySite** 배치. 표시명에는 단어 사이 공백이 들어갈 수 있다.
3. Actor 이름 예: JWJ_Graze_Forest_01.
4. Actor 본체 Details → **Region Id=Forest / Kind=Graze / For Predator=false**.
5. Components → **SmartObject 선택** → Definition/Definition Asset=`/Game/Experiments/SpeciesAI/SO_ActivitySlot`.
6. Actor 본체로 돌아가 Transform을 FoodHint 근처 실제 지면에 맞춘다. 슬롯이 NavMesh 위에 있어야 한다.
7. World Partition의 **Is Spatially Loaded=false**로 단독 시험 중 상시 활성화한다.
8. PIE에서 ID 확인 후 `eco.M4.SetVitals <ID> 1 0.2`.
9. 접근→실제 도착→Graze, Food감소·Granted·Energy증가를 함께 확인한다.

FoodHint 이동만으로 Runtime Food Patch Position은 바뀌지 않는다. 장소를 옮길 때 Runtime→Groups→Forest→Food Patch Position도 같은 world 좌표로 맞춘다. site 자체에는 Food잔고가 없다.

### S2. 예약 경쟁·휴식·중단

1. Runtime Forest Herbivores2 / Graze site1로 재실행한다.
2. Status의 Slots/Claims/Releases 확인. 이동 중 허위 Graze 지급·중복 점유가 없어야 한다.
3. ActivitySite를 하나 더 배치 → **Kind=Rest / For Predator=false / Region Id=Forest / SO_ActivitySlot**.
4. 시험용 PIE에서 site 무효화·삭제/위협으로 중단시켜 예약 해제를 확인한다. Editor 원본의 영구 삭제와 구분한다.
5. 별도 실행에서 기존 Shelter의 실제 도착feedback 후 Occupied, 사망/Travel 시 release를 확인한다.

### S3. 사슴 위협 대역

1. Runtime **Fixtures=true / DeerOnly 유지**.
2. +Add 클래스 검색 → **EcoSpeciesAIFixture** 배치. 이름 예 JWJ_DeerThreat_01.
3. 본체 Details → **Prey=false / Visible=true / Makes Noise=false / Motion Radius0**.
4. 사슴의 실제 정면·감각 범위·LOS를 만족하는 위치에 둔다. 기본 표시mesh는 없다.
5. Flee/Shelter/Recover 확인. Visible=false/Makes Noise=true의 청각만 조건도 별도로 시험한다.
6. 시험 후 Runtime Fixtures=false로 되돌린다. Both에서 true로 두면 설정 검사가 거부한다.

### S4. 늑대만 추적·공격

1. PIE 종료 → Runtime **WolfOnly / Wolf Config=EC_Wolf**. Herbivore Config는 비워도 된다.
2. Forest Wolves1, 다른 지역Wolves0, Herbivores0.
3. **Predator Survival=true / Drain1 / Capture Gain25 / Fixtures=true**.
4. Fixture **Prey=true / Visible=true / Makes Noise=false / Motion Radius0**. 사슴 위협 대역과 구분한다.
5. Rest site는 Kind=Rest / For Predator=true / Forest로 준비한다.
6. 시작 후 늑대 Energy를0.2로 낮춰 추적→AttackSuccess/FixtureCaptures→한 번의 영양 지급 확인.
7. Visible=false/Makes Noise=false로 바꿔 숨은 현재 위치를 계속 쫓지 않고 마지막 cue 조사 후 포기하는지 확인.
8. noise-only/벽 뒤/도달 불가/늑대2 경쟁을 각각 시험한다.

fixture 성공은 실제 prey Death/Population/PredationHistory를 바꾸지 않는다.

### S5. 실제 두 종 통합

1. Runtime **Both / EC_Deer / EC_Wolf / Fixtures=false**.
2. Forest 사슴4/늑대1, 다른 지역0부터 시작. 기존 안전 스폰 좌표 유지.
3. Graze/Rest/Shelter를 준비하고 Predator Survival=true로 보상을 확인한다.
4. 탐지→도주/추적→공격→단일Death→Population/History/영양을 대조한다.
5. 통과한 뒤 Migration/Pressure를 복원하고3지역·19개체로 확장한다.

## 8. 복사본에서 환경·예산 별도 시험

### E. 환경 Adapter

기존 Sky/Weather는 있지만 Adapter는 없으므로 콘솔 논리 시험부터 분리한다.

1. FoodCapacity에 여유가 있는 상태에서 서버 `eco.Environment.Regeneration Forest 2 1 0.5 1.5`, `eco.Environment.Rain Forest 0`.
2. 같은 조건·FPS의 별도 실행에서 Rain1. 공급1/3 Food/s·소비 원장 확인.
3. 표시 인계는 Content Browser **우클릭→Blueprint Class→All Classes→EcoRegionEnvironmentAdapter**를 부모로 새 BP 작성. 예 BP_JWJ_EnvironmentBridge.
4. 복사본에1개 배치, Region Ids=Forest 등 대상, 상시 로드 설정.
5. 고정 날씨는 Apply Authored Weather=true+Authored Weather. 외부 Weather/콘솔 입력이면 false.
6. 서버 Weather입력→ApplyRainfall, OnEnvironmentUpdated→날씨 표시, OnClockUpdated→하늘 표시. PhaseProgress는 해당 Day/Night phase의0..1.
7. 실제 기존 BP 함수를 확인해서 연결한다. 이번 조사는 내부 노드를 확인하지 않았다. 원본 BP그래프를 바꿔야 한다면 복사본용 BP로 분리한다.
8. Client 이벤트는 표시 전용. Client에서 논리 날씨를 다시 결정하지 않는다.

### F. Connection Budget·병렬·LOD

1. **Edit→Project Settings→Adaptive Ecosystem→M4/Connection Budget**. 변경 전3값 기록.
2. 19개체의 작은 예산 시험: Max Relevant Agents8 / Max Actor Representations4 / Max Adds Per Update2.
3. PIE재시작→Client수신·Bubble Entries·BudgetDeferredAdds·Actor+pool상한 확인.
4. 설정은 **두 레벨 공통**이므로 종료 후 원값 복원. 규모 시험에서 작은 상한을 잊고 유지하지 않는다.
5. 기존 PPO worker는 `eco.Policy.Parallel 1`과 실제 due입력64이상·ParallelDecisions 증가로 확인. full StateTree를 기존 PPO worker 시험에 사용하지 않는다.
6. full SpeciesAI는 no-player/원거리 tier, 위협·예약·Travel의 High복귀와 화면 밖 생태 진행 확인.
7. 성능capture는 상세log/draw를 끈 별도 실행. 설정을 켠 사실을 성능 향상 측정으로 기록하지 않는다.

## 9. 문제별 다음 선택 대상

| 증상 | 확인할 선택 대상 |
| --- | --- |
| Config필드가 안 보임 | Runtime Actor본체 / Details All / 검색필터 |
| 다른 Actor가 안 보임 | Outliner의 Runtime검색 제거 후 새 이름 검색 |
| Ready0 | 첫 Eco Setup/Template rejected/ground오류, GameMode |
| 배치검사 통과 후 spawn실패 | world좌표·지형cell·collision·NavArea_Null |
| 사슴이 못 먹음 | EC_Deer·Region Food·Graze site·SO정의·FoodPatch·실제 점유 |
| 늑대가 계속 쉼 | Predator Survival·Energy·fixture Prey/Visible/FOV/LOS |
| 초기에 대부분 사망 | 초기 종간 거리·생존설정. 단일종·소수로 원인 분리 |
| Client에 안 보임 | viewer거리·동일Config·Bubble·Actor/관련성예산 |
| 높이writer/Nav거부 | DefaultMass.ini·Supported Agents·Nav빌드, 가드 유지 |
| 날씨콘솔값이 돌아감 | Adapter Authored Weather상시 덮어쓰기·기존BP 자체 갱신 |

## 10. 실행 순서와 기록

**복사본 생성 → 원본19개체 smoke → 원본 소수PPO/기아/이주/Shelter → Client → 원본 복원 → 복사본 EC_DeerV1 → EC_Deer단독/경로/Graze → WolfOnly → Both → 환경/예산/규모**.

매 실행마다 레벨명·commit/build·Config·Groups·Food·생존/이주/압력·FPS·Client수·조작·기대/실제·로그를 기록한다. 기존 PPO, V1 StateTree, full SpeciesAI를 같은 조건으로 섞지 않는다.

참고: [주간 분석](WEEKLY_DEVELOPMENT_ANALYSIS_2026-10-15.md), [M4 수동 설정](M4_NEW_LEVEL_MANUAL_SETUP.md), [SpeciesAI 적용](SpeciesAI/EDITOR_QUICK_START.md), [SpeciesAI 검증 상태](SpeciesAI/IMPLEMENTATION_MILESTONES.md). 실제 조사 원본은 로컬 Saved/Integration_JwJ_ReadOnlyAudit.json에 있다.

## 11. 2026-10-16 사용자 시험 피드백과 로그 대조

아래는 사용자 관찰과 기존 `Saved/Logs/AdaptiveEcosystem.log` 대조 결과다. 이번 확인에서 새 PIE/빌드·Source 수정·레벨 수정은 하지 않았다. 실제 복사본 실행 이름은 `Integration_Mass_JwJ`로 기록되어 있다.

### P6/P7 판정

- P6: Migration/재생/공급을 끈 조건에서 Food 고갈→Energy 소진→HP 소진→Starvation은 예상한 생존 흐름이다. 로그에도 Forest ID1/2의 Cause=Starvation이 있다. 은신처 부근 왕복 이동의 품질까지 정상이라는 판정은 아니다.
- P7: 로그에 Reason=FoodDepletion, Target=Barren, State=Traveling이 있어 사용자 관찰과 일치한다. **출발은 확인**, 도착·MigrationIn/Out·인구 보존은 별도 확인한다.

### S1: 먼저 실제 Config 경로를 확인

최근 사슴1/2/8개체 실행의 template 로그는 모두 `/Game/Creatures/Integrated/DA_EcoDeer`다. 조사한 로그에는 `/Game/Experiments/SpeciesAI/EC_Deer` 실행과 SpeciesAI Status/Capture 출력이 없다. 따라서 이번 떨림을 새 StateTree/Graze 경로의 결함으로 확정할 수 없다. BP ActivitySite를 배치한 것만으로 기존 PPO Entity가 새 Brain을 사용하지 않는다.

1. PIE 종료 → 실제 복사본 열기 → Eco_CreatureRuntime 본체 선택.
2. Herbivore Config=`/Game/Experiments/SpeciesAI/EC_Deer`, Enabled Species=DeerOnly.
3. EC_Deer의 Trait는 Use Species AI=true, Profile=DA_Deer인지 확인한다. 기존 DA_EcoDeer를 수정하지 않는다.
4. Forest 사슴1/늑대0, 다른 지역0, Migration/Pressure off로 재시작.
5. `eco.SpeciesAI.Status`에서 Deer=1을 확인한다. `Entities=0`이면 full SpeciesAI의 사슴 실행을 검증한 것이 아니다.
6. `eco.M4.SetVitals <실제 사슴 ID> 1 0.2`로 배고픔을 만들고 접근→점유→Graze/실제 지급을 확인한다.
7. 정상 Graze에서는 저속/정지가 가능하다. 도착 후 계속 다른 곳을 걷는 것이 성공 기준은 아니다. 떨림이 남으면 `eco.SpeciesAI.Capture`를 2~3초 간격으로 여러 번 실행해 Decision/Activity/NavStatus/MoveRevision/Failures/SlotReservation/Energy를 대조한다.

기존 PPO는 먹이 방향·응집·분리 벡터를 합성하므로 한 마리와 여러 마리의 움직임이 달라질 수 있다. 이 사실은 단독 떨림의 원인 확정이나 2개체 최소 실행 조건을 뜻하지 않는다.

### S2: Graze site 1개의 정확한 뜻

`Graze Site Count=1` 같은 Runtime 설정은 없다. **EcoSpeciesAIActivitySite를 상속한 Graze Actor를 레벨에 한 개 배치**한다는 의미다.

1. 레벨의 사용자 ActivitySite BP 인스턴스 선택 → 본체 Details: Region Id=Forest, Kind=Graze, For Predator=false.
2. Components→상속된 SmartObject 선택 → Definition/Definition Asset=SO_ActivitySlot.
3. SO_ActivitySlot을 열어 슬롯이1개인지 확인한다. 제공된 기본 정의는1개 슬롯이다. 경쟁 시험에서 공유 정의의 슬롯 수를2로 늘리지 않는다.
4. Outliner에서 Graze 장소 Actor를 한 개만 활성화하고 Runtime Forest Herbivores=2로 설정한다.
5. 두 번째 시험은 장소 Actor 수나 슬롯 수 중 하나만 늘려 변경 효과를 구분한다. Eco_FoodHint는 Graze Actor 수에 포함하지 않는다.

### S4: 늑대2개체 실패 원인과 명령

로그에 반복 기록된 직접 오류:

```text
[Eco Setup] Group Forest: Wolf Spawn Points needs at least 2 world-space entries.
```

늑대 최대 수가1이라는 제한이 아니다. 기존 Forest의 Wolf Spawn Points가1개뿐인 상태에서 Wolves를2로 늘려 초기화가 거부된 것이다.

1. PIE 종료 → Runtime→Groups→Region Id=Forest→Wolves=2.
2. 같은 Group의 Wolf Spawn Points를2개 이상으로 늘린다. 각 항목에 서로 겹치지 않는 실제 지면의 world XYZ를 입력한다.
3. 기존1번 좌표를 그대로 중복하지 않는다. Region 내부·collision·NavMesh·이동 금지 구역을 확인한다.
4. Schedule Region Population Limit/Global Population Limit이 초기 합계 이상인지 확인한 뒤 Validate한다.

EC_Wolf에는 별도로 `Missing supported NavMesh for the SpeciesAI body radius/height`도 기록돼 있다. 좌표 수 문제와 독립적으로 Supported Agents·profile 몸체·지형 cell·Navigation 빌드를 확인한다. 뒤의 Validated=1/Spawn 로그만으로 앞선 오류를 무시하지 않는다.

최근 단독 늑대 spawn 로그의 ID는1이었다. 현재 실행에서도 ID를 확인한 뒤 서버/Standalone에서 다음을 사용한다.

```text
eco.M4.Dump details
eco.M4.SetVitals 1 1 0.2
eco.SpeciesAI.Status
```

인자는 **StableAgentId / HP비율 / Energy비율**이다. 위 예시는 ID1을 HP100%·Energy20%로 설정한다. ID가 다르면 첫 숫자를 바꾼다. 낮은 Energy가 타깃을 생성하거나 강제로 추적 상태를 고정하지는 않는다. EC_Wolf·유효한 감각 cue가 필요하며, 대역 시험은 WolfOnly/Fixtures=true/Prey=true/Visible=true/LOS·범위가 유효해야 한다. Predator Survival=true로 대사와 포획 영양을 확인한다.
