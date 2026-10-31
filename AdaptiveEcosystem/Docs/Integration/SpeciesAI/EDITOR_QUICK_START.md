# SpeciesAI 실제 적용과 독립 실행

UE 5.8.3 / 2026-10-14. 이 문서는 이번에 추가한 C++와 생성된 에셋을 실제 레벨에 연결하는 순서다. 기존 팀 레벨의 배치·애니메이션 자산은 유지한다. 레벨 실행·네트워크·cook·성능 통과 기록은 [구현 마일스톤](IMPLEMENTATION_MILESTONES.md)과 구분한다.

## 1. 제공된 에셋

Content Browser에서 `/Game/Experiments/SpeciesAI`를 연다.

| 에셋 | 용도 |
| --- | --- |
| `ST_Deer`, `DA_Deer`, `EC_Deer` | 사슴 전체 행동 + 새 NavMesh/지면 이동 |
| `ST_Wolf`, `DA_Wolf`, `EC_Wolf` | 늑대 전체 행동 + 새 NavMesh/지면 이동 |
| `ST_DeerV1`, `DA_DeerV1`, `EC_DeerV1` | V1 관측을 사용하는 StateTree 정책 비교; 기존 이동/섭식 경로 유지 |
| `SO_ActivitySlot` | Graze/Rest 장소에 지정하는 1개 슬롯의 기본 SmartObject 정의 |

세 StateTree의 schema는 **Mass Behavior**다. 루트 `UtilityRoot`가 Highest Utility로 자식을 선택하고, 각 float consideration에는 입력 0→0, 1→1 response curve가 연결되어 있다. 종별 점수는 C++의 `Deer/EcoDeerUtility.cpp`, `Wolf/EcoWolfUtility.cpp`가 만든다. `ST_Deer`와 `ST_Wolf`는 서로 다른 저장 에셋이므로 이후 종별 상태·consideration을 독립적으로 편집할 수 있다.

DataAsset은 공유하는 설정이고 개체별 상태는 Fragment에 있다. 실행 중 DataAsset 값을 변경하지 말고 PIE를 종료한 다음 프로필을 수정한다. 실제 영속 `SpeciesId`는 기존 계약을 따라 사슴=`Herbivore`, 늑대=`Wolf`다.

에셋이 없을 때 Editor가 종료된 상태에서 다음 도구로 생성할 수 있다. 이 명령은 자동화 테스트가 아니라 저장 에셋 작성·StateTree 컴파일 도구다. 기존 StateTree의 상태/노드와 Profile/EntityConfig 설정은 덮어쓰지 않는다. 생성 경로의 누락된 Mass authoring schema와 기본 슬롯 정의의 schema는 보수한다.

```powershell
& 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' `
  'C:/Users/wonkii/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/AdaptiveEcosystem.uproject' `
  -run=EcoSpeciesAIAssets -unattended -nop4 -nullrhi
```

## 2. 공통 레벨 준비

1. 기존 통합 레벨을 **에디터에서** 복제한다. World Partition 맵은 `.umap` 파일만 복사하지 않는다. 상세 기존 배치는 [M4 새 레벨 설정](../M4_NEW_LEVEL_MANUAL_SETUP.md)을 참고한다.
2. `EcoCreatureIntegrationSpawner`는 정확히 하나만 둔다. 같은 월드의 M3 Box Bootstrap을 제거한다. 추가 일반 MassSpawner를 붙이지 않는다.
3. World Settings의 GameMode Override를 `EcoCreatureIntegrationGameMode` 또는 그 자식으로 지정한다. 해당 GameMode가 `EcoGameState`와 WorldEpoch를 준비한다.
4. EcologyRegion의 RegionId, Bounds, Groups의 RegionId와 스폰 지점을 맞춘다. 지면/충돌/Navigation이 있는 셀을 로드한다. 초기 규모는 1~8마리, Waves=false로 시작한다.
5. NavMeshBoundsVolume이 이동 가능한 지면을 덮도록 배치하고 Navigation을 빌드한다. 에디터의 `P` 표시로 연속된 녹색 이동면을 확인한다. `DA_*`의 기본 몸체는 radius=30cm, height=130cm다. Project Settings의 Supported Agents가 이 몸체를 지원해야 한다. NavData가 없으면 새 전체 행동 Config는 시작 전에 거부한다.
6. 사슴/늑대 표현 클래스는 기존 `/Game/Creatures/Integrated/BP_EcoDeer`, `BP_EcoWolf`를 연결한다. 표현 Actor를 별도로 배치하지 않는다. FootstepAudioSet은 기존 설정을 재사용한다.
7. coordinator의 `Validate Editor Setup`을 실행하고 오류를 수정한다. 전체 행동 Config에 Movement/StateTree/SmartObject Trait를 추가로 중첩하지 않는다. `Eco Integrated Creature` Trait가 프로필에 따라 필요한 구성을 조립한다.

`Config/DefaultMass.ini`도 함께 적용해야 한다. 엔진 `MassNavigationSmoothHeightProcessor`를 끄고 동일한 높이 보정을 수행하는 프로젝트 호환 Processor로 교체했다. 호환 Processor는 새 `FEcoGroundedNavigationTag` 개체를 제외한다. 이 파일이 누락되어 stock 높이 writer가 다시 활성화되면 새 Config 등록을 거부한다.

## 3. 사슴만 실행

- Enabled Species=`DeerOnly`.
- Herbivore Config=`EC_Deer`; Wolf Config는 비워도 된다.
- Groups의 사슴 수=1~8, 늑대 수는 활성 역할 필터에서 제외된다.
- 처음에는 Enable Species AI Fixtures=false.
- 먹이 장소가 없으면 배회·휴식으로 시작한다. 섭식은 아래 Graze 슬롯과 지역 Food가 모두 필요하다.

`EcoSpeciesAIActivitySite`를 지면에 배치하고 RegionId를 현재 지역과 맞춘다. Kind=`Graze`, For Predator=false. SmartObject 컴포넌트의 Definition을 `SO_ActivitySlot`으로 지정한다. 먹이 provider의 FoodPatchPosition 근처에 놓는다. 슬롯 좌표 자체를 지면에 두고, 동물이 접근할 수 있는 NavMesh 위에 놓는다. 필요 수만큼 Actor를 복제하면 각각 독립 슬롯을 제공한다.

휴식 장소도 같은 Actor로 만든다. Kind=`Rest`, For Predator=false. 동물이 차지할 수 있는 공간·슬롯 간 간격을 확보한다. 먹이 위치는 이용 장소이며 별도 Food 잔고를 갖지 않는다. 자원 잔고는 Region Ecology 원장이 관리한다.

위협 시험은 Enable Species AI Fixtures=true로 켠 뒤 `EcoSpeciesAIFixture`를 배치한다. Prey=false, Visible=true, Makes Noise=false로 시작한다. 처음에는 Motion Radius=0으로 놓고 사슴의 앞쪽 감각 범위 안에 둔다. 뒤쪽 소음은 Visible=false, Makes Noise=true로 바꾸어 확인한다. fixture 자체에는 표시용 메시가 없으므로 Outliner/Details와 상태 기록으로 확인하거나 별도의 충돌 없는 표시 메시를 붙인다.

Social Shelter는 기존 `EcoShelterAnchor`를 사용한다. 실제 차폐가 있는 위치와 접근 가능한 슬롯을 배치한다. 새 이동 계층이 기존 Social Request를 소비하고 실제 도착/실패 feedback을 돌려준다. 일반 Graze/Rest SmartObject와 Shelter 예약의 소유자는 다르다.

## 4. 늑대만 실행

- Enabled Species=`WolfOnly`.
- Wolf Config=`EC_Wolf`; Herbivore Config는 비워도 된다.
- 늑대 초기 수=1. Enable Predator Survival=true로 켜야 기존 권위 생존 경로가 실제 포획 영양을 Energy에 적용한다.
- `EcoSpeciesAIActivitySite`: Kind=Rest, For Predator=true, RegionId 일치, Definition=`SO_ActivitySlot`.
- Enable Species AI Fixtures=true. `EcoSpeciesAIFixture`: Prey=true, Visible=true, Motion Radius=0으로 먼저 시험한다.

늑대는 기본 Energy가 높으면 휴식할 수 있다. `eco.M4.Dump details`에서 StableAgentId를 확인하고 서버 콘솔에서 `eco.M4.SetVitals <ID> 1 0.2`로 배고픔을 만든다. 범위/FOV/LOS를 통과한 cue를 따라 추적하고 실제 거리·LOS가 유효할 때 공격을 요청한다. 그 다음 Motion Radius/Period Seconds를 조절하여 움직이는 대역을 시험한다.

Visible=false와 Makes Noise=false를 같이 설정하면 마지막 cue만 기억한다. 숨은 대역의 현재 위치를 계속 추적하면 실패다. 소음만 켠 경우 조사 위치에 불확실성을 적용하고 공격에 필요한 fresh sight는 제공하지 않는다.

fixture 포획은 실제 prey Death/Population/PredationHistory를 바꾸지 않는다. 별도 FixtureCaptures와 일회 nutrition receipt를 사용한다. 같은 프레임 여러 늑대가 공격해도 대역의 capture availability를 첫 성공자가 바꾸므로 중복 성공을 방지한다.

## 5. 실제 두 종 합치기

Enabled Species=Both, Herbivore Config=EC_Deer, Wolf Config=EC_Wolf로 지정하고 **Enable Species AI Fixtures=false**로 둔다. Both에서 fixture 옵션을 켜면 설정 검증이 거부한다. 처음에는 사슴 4, 늑대 1로 시작하고 안전한 스폰 간격을 둔다.

실제 prey는 기존 Mass 감각/Grid에서 읽는다. 새 공격은 lethal HP/death candidate를 기록하고, 기존 coordinator가 유일한 사망 확정·Population/PredationHistory·포획 보상 경로를 수행한다. 기존 자동 근접 포획 Processor는 새 이동 tag의 늑대를 제외한다. 이를 다시 포함시키면 공격 중복 경로가 되므로 제외 조건을 유지한다.

## 6. PPO 비교 설정

| 실험 | 사슴 Config | 늑대/이동·섭식 조건 | 해석 |
| --- | --- | --- | --- |
| PPO 기존 기준선 | 기존 `DA_EcoDeer` EntityConfig | 기존 동일 늑대 Config, 동일 맵/초기값 | 기존 정책 기준선 |
| StateTree 정책 비교 | `EC_DeerV1` | 기준선의 늑대·이동·Social·섭식 유지 | 정책 교체 효과; 새 NavMesh/슬롯 생활 미사용 |
| 전체 시스템 비교 | `EC_Deer` + 필요 시 `EC_Wolf` | 새 이동/섭식/공격 | 전체 시스템 효과 |

V1 프로필은 7개 관측만으로 점수를 만들고 추가 fixture 입력을 쓰지 않는다. PPO와 동일한 `EcoObservation::Build`를 사용하며 `eco.Policy.PredationSource` 설정도 공유한다. 결정 주기는 기본 PolicyInterval/60초이고 V1에서는 production MinimumDwell을 적용하지 않는다. 기존 generated 상수/학습 가중치를 변경하지 않았다.

이 두 구현의 프레임 최초 결정 위상은 같다고 검증한 상태가 아니다. 엄밀한 반복 비교에서는 관측·결정 시각과 초기 상태를 함께 기록하고, 필요한 동일 cadence/initial phase 조건을 고정해야 한다. 새 몸체 속력·새 늑대·슬롯 섭식까지 같이 바꾸고 사슴 정책만의 성능으로 해석하지 않는다.

## 7. 수동 상태 확인

```text
eco.M4.Dump details
eco.SpeciesAI.Status
eco.SpeciesAI.Capture
eco.SpeciesAI.PathQueries 8
eco.SpeciesAI.PathMilliseconds 2
```

Status는 새 StateTree cohort의 역할·tier·경로·공격·예약·활동을 출력한다. Capture는 `Saved/SpeciesAI/Snapshot_*.csv`와 `.manifest.txt`를 저장한다. 이는 누적 성능 benchmark가 아닌 수동 순간 기록이다. CSV의 ObservationValid=1인 행만 V1 관측 값으로 해석한다. full 행동 또는 늑대의 미수집 observation을 V1 값으로 해석하지 않는다. 기존 PPO cohort는 기존 `eco.M4.Dump` 및 기존 정책 진단을 함께 사용한다.

프로필/실험 조건·초기 Food/Population·survival·waves·migration·replication settings·맵·실행 시간·서버 FPS·hardware도 비교 기록에 따로 남긴다. PathMilliseconds는 동기 쿼리 사이의 **soft budget**이며 하나의 경로 계산을 중단시키는 hard deadline이 아니다.
