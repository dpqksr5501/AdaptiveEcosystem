# 팀 날씨·나무 시험 레벨 확인 (10-17, 팀 PR ff8c8f4)

팀(avaroki 님)이 `origin/feat/ecosystem-integration-map` 에 올린 '지역별 비·눈 날씨 및 나무 장애물 배치'(`ff8c8f4`, 그 위 `2d761c9` main 합침)를
`Branch_Sinhyeok` 에 합치고(`3e90177`) 새 시험 레벨 `/Game/SHC/Maps/LV_SHC_RegionalWeatherTest` 를 읽기만 해서 확인했다.
레벨·콘텐츠·설정은 하나도 바꾸지 않았다(저장 없음, 파이썬 플러그인은 명령줄로만 켬).

## 한 줄 결론

- 나무 11 그루는 모두 숲 지역에 있지만 **우리 동물 무대(120 m 상자) 셋 어디에도 들어오지 않는다**(가장 가까운 나무가 숲 무대 남쪽 끝에서 14.7 m 밖). 그래서 지금은 사슴이 지날 나무가 0 이고, 파이썬 세계도 지금 그대로(원판 0)가 언리얼과 같다.
- 이 레벨에는 통합 조정자(`AEcoCreatureIntegrationSpawner`)와 은신처 앵커가 없어서 **동물이 아예 나오지 않고 우리 통합 v3 모드도 돌지 않는다**(기록 `unreal_logs/shc_map_s20000.log`).
- 나무의 충돌이 **나무 전체(잎 포함)를 감싼 볼록 껍질 하나**라서, 줄기(밑동 반경 약 0.8 m)가 아니라 땅 위 60 cm 에서 반경 약 8~13 m 의 보이지 않는 벽이 된다. 우리 레벨 읽기 규칙으로 읽으면 나무마다 반경 13.8 m 원판이다.
- 나무 11 그루가 모두 같은 높이(z = −1310)에 놓여 9 그루는 땅에 1.8~4.6 m 묻혔고 2 그루는 0.8 m·3.2 m 떠 있다.
- 비·눈은 **보이고 들리는 것만** 바뀐다. 카메라가 지역 트리거 상자 안이면 카메라 곁에 비·눈 이펙트와 소리를 켠다. 지역 환경 값(`FRegionEnvironmentState`, 강수 0)과 게임 규칙은 그대로다.

## 1. 합치기

- `git merge origin/feat/ecosystem-integration-map` → `3e90177`(글자 충돌 없음, Content 만 바뀜, C++·Config 그대로). LFS 실제 파일 모두 받음.
- 빌드 `-DisableAdaptiveUnity`·기본 두 방식 성공(바뀐 C++ 없음), 자동 시험 163 = 성공 162 + 기존 경고 1(SaveLoadGlobalEma), 실패 0.
- 통합 레벨 `LV_Ecosystem_IntegrationTest` 에서는 `BP_WeatherManager_PlayerFollow` 액터가 지워지고, 풀 액터의 풀 유형 경로가 `/Game/SHC/Foliage` 로 바뀌었다.
  통합 v3 모드를 병합 뒤 다시 돌렸다(세션 20000, 30초): 무대 셋 원판 0·0·0, 숲 무대 메시 20(모두 충돌 없는 풀, 병합 전 38), 오류·ensure·EcoV3I 경고 0
  (`unreal_logs/integration_map_s20000.log`, `v3_export_integration_s20000.json`).
- 팀에 알릴 것(다른 맵이 깨짐): `/Game/Actors/BP_WeatherManager_PlayerFollow` 리디렉터가 없는 `/Game/SHC/Blueprints/Weather/BP_WeatherManager_PlayerFollow` 를 가리킨다
  (`BP_WeatherManager_Region` 으로 이름을 바꾸며 리디렉터를 남기지 않은 것으로 보임). `LV_JYU_V3Integration` 을 열면
  'Failed to find redirected assets … Unknown actor base class' 경고가 나고 그 날씨 액터가 빠진다(`LV_JYU_RefugeSafety`·`Integration_JwJ` 도 같은 액터를 쓴다).
  옛 `/Game/Foliage/FT_GrassC·D` 도 리디렉터 없이 옮겨져 그 세 맵의 풀 유형 연결이 끊긴다(그려진 풀 인스턴스는 남는다 — 풀 칠하기 도구에서만 문제).

## 2. 레벨 사실 (`scan_LV_SHC_RegionalWeatherTest.json`)

| 항목 | LV_SHC_RegionalWeatherTest | LV_Ecosystem_IntegrationTest |
|---|---|---|
| 지형·지역 | 같은 지형(스트리밍 조각 64), `AEcologyRegion` 셋(Barren·Forest·Highland, 같은 상자), 트리거 상자 `TV_Region_*` 셋 | 같음 |
| 먹이 자리(무대 중심) `Eco_FoodHint_*` | 같은 자리 | 같음 |
| 통합 조정자 `AEcoCreatureIntegrationSpawner` | **없음** | 있음 (`Eco_CreatureRuntime`) |
| 은신처 앵커 `AEcoShelterAnchor` | **없음** | 숲 2 (학습 범위 밖이라 우리 코드가 뺌) |
| PlayerStart | (18200, 40450) — 나무 무리 가운데 | (34200, 48500) — 숲 무대 안 |
| 충돌하는 정적 메시 | `Beech_Tree` 11 (BlockAll, 쿼리+물리, WorldStatic·Pawn 막음, 크기 2) | 0 |
| 풀(충돌 없음) | `SM_MWAM_GrassC`·`GrassD` 10+10 | 같음 |
| 날씨·하늘 | `BP_SHC_RainRegionalWeather`(→ `TV_Region_Forest`), `BP_SHC_SnowRegionalWeather`(→ `TV_Region_Highland`), `BP_SkyManager`(SunSpeed 0) | `BP_SkyManager`(SunSpeed 0) |
| 지역 환경 값 | 강수 0·맑음 (Barren 30 °C·0.2, Forest 20 °C·0.7, Highland −5 °C·0.4), 강수가 재생을 안 바꿈 | 같음 |

두 맵은 지형·지역·먹이 자리가 같아서, SHC 나무 자리를 통합 맵 무대 좌표로 그대로 옮겨 겹쳐 볼 수 있다(아래 그림).

## 3. 나무 11 그루 (`summary.json`)

| 나무 | 자리 x, y (m) | 줄기 밑 − 땅 | 땅 위 60 cm 충돌 단면(같은 넓이 원 반경) | 숲 무대까지 |
|---|---|---|---|---|
| Beech_Tree11 | 343.6, 390.3 | 3.19 m 떠 있음 | 없음 (밑으로 지나감) | 14.7 m |
| Beech_Tree2 | 244.2, 471.7 | 0.76 m 떠 있음 | 없음 (1 m 높이부터 막음) | 37.8 m |
| Beech_Tree | 220.7, 424.4 | 1.80 m 묻힘 | 9.9 m | 61.3 m |
| Beech_Tree3 | 188.6, 522.5 | 3.93 m 묻힘 | 12.2 m | 93.4 m |
| Beech_Tree5 | 186.5, 326.1 | 3.28 m 묻힘 | 11.5 m | 123.9 m |
| Beech_Tree4 | 120.5, 424.4 | 3.65 m 묻힘 | 11.9 m | 161.5 m |
| Beech_Tree9 | 120.5, 615.8 | 4.64 m 묻힘 | 12.7 m | 185.3 m |
| Beech_Tree6 | 68.9, 494.0 | 4.64 m 묻힘 | 12.7 m | 213.1 m |
| Beech_Tree8 | 76.8, 321.0 | 3.15 m 묻힘 | 11.4 m | 221.7 m |
| Beech_Tree7 | −12.0, 361.6 | 3.14 m 묻힘 | 11.4 m | 297.2 m |
| Beech_Tree10 | −78.4, 510.4 | 4.20 m 묻힘 | 12.4 m | 360.4 m |

- 무대마다 우리 레벨 읽기가 집을 원판: 숲 0 · 메마른 땅 0 · 고지 0 (원판 중심이 무대 상자 안이어야 한다 — `ScanStageObstacles`).
- 땅 높이는 줄기 자리와 둘레 5 m 네 곳에서 선 추적으로 쟀다(나무는 빼고). 11 그루 모두 z = −1310 이다.

## 4. 나무 충돌 모양 (`beech_tree_collision.png`)

- `Beech_Tree` 단순 충돌 = 볼록 껍질 1 개(꼭짓점 32, 구·상자·캡슐 0). 메시 공간 상자 x −722~688, y −642~717, z 0~1243 cm → 크기 2 배로 28 × 27 × 25 m. 잎까지 감싼다.
- 그리기 메시의 줄기 밑동은 반경 약 0.8 m(크기 2 배, 바닥 꼭짓점 6 개). 첫 가지·잎은 줄기 밑에서 2 m 위부터다.
- 껍질을 줄기 밑 높이에서 자른 단면(같은 넓이 원 반경): 0.05 m 7.3 m, 0.6 m 7.9 m, 1.5 m 8.9 m. 땅에 묻힌 나무는 더 넓은 단면이 땅에 닿아 땅 위 60 cm 에서 9.9~12.7 m 가 된다.
- 팀 이동 제약(`EcoCreatureMovement::ConstrainStep`, WorldStatic 쓸기)은 단순 충돌을 쓰므로, 동물·플레이어가 줄기에서 8~13 m 떨어진 허공에서 막힌다(추정 — 이 레벨에는 동물이 없어 직접 보지는 못했다).
- 우리 레벨 읽기(`ObstacleCollisionBox`: 단순 충돌 상자의 가로 반폭 평균)로 읽으면 나무마다 반경 13.8 m 원판(무대 넓이의 4.2%)이다. 실제 숲의 줄기(반경 0.1~0.3 m)와 거리가 멀다.

## 5. 날씨 (지금 하는 일)

- `BP_SHC_RainRegionalWeather`·`BP_SHC_SnowRegionalWeather`: `RegionBounds` 로 트리거 상자(숲·고지)를 받고, 카메라가 상자 안이면 카메라 곁에 비(`Rain_System`)·눈(`NS_Blizzard`) 나이아가라를 켜고 따라 옮긴다. 비는 빗소리·천둥도 낸다.
  `RainfallIntensity` 는 나이아가라 변수다. 메마른 땅에는 날씨가 없다.
- 두 블루프린트는 `AEcologyRegion`·`FRegionEnvironmentState`·`AEcoRegionEnvironmentAdapter` 를 부르지 않는다(애셋 안 참조 없음). 지역 강수는 적어 둔 0 그대로다.
  그래서 강수를 읽는 팀 규칙(Social 위협 감지·늑대 감각의 비 시야·청각 배수, 지역 재생 — 지금 꺼짐)도, 우리 v3 세계(날씨를 읽지 않음)도 바뀌지 않는다.
- 이어 주는 길은 코드에 이미 있다: `AEcoRegionEnvironmentAdapter::ApplyRainfall(강수, 날씨)`(서버에서 지역 환경 값 쓰기)·`OnClockUpdated`(시계 → 빛·비 연출). 어느 맵에도 놓여 있지 않다.
- `BP_SkyManager`: 매 틱 해 회전을 `SunSpeed × 시간` 만큼 바꾼다(블루프린트 노드 이름으로 본 어림). 두 맵 모두 SunSpeed 0(해 고정, pitch 315). 팀 시계(`UEcoWorldClockSubsystem`)와 이어져 있지 않아서,
  SunSpeed 를 올리면 보이는 해·달과 동물이 쓰는 낮밤(통합 v3 모드 60 + 60 초)이 따로 돈다.

## 6. 막힌 것과 가장 싼 길

1. **무대 안에 나무가 없다.** 우리 통합 v3 모드는 팀 통합 레벨의 무대(먹이 자리 둘레 120 m)에서만 돈다. 가장 싼 길은 팀이 같은 나무를 `LV_Ecosystem_IntegrationTest`(또는 정할 공식 레벨)의 무대 안에 놓는 것이다.
   그러면 우리 코드가 그대로 읽고(`eco.IntegratedV3.Obstacles` 기본 1), `-EcoV3ObstacleExport=` JSON 을 파이썬 거울(`run_mirror.py --unreal-maps … --unreal-obstacles …`)이 같은 원판으로 읽는다.
   SHC 맵에 조정자·은신처를 넣는 길도 있지만 팀 콘텐츠를 바꿔야 한다. 측정 전용 원판(`-EcoV3ObstacleImport=`)은 화면에 나무가 없어 '레벨과 같은 환경'이 아니다.
   (10-17 뒤: 이 배치를 통합 레벨 무대에 겹쳐 파이썬 거울과 언리얼 헤드리스를 같은 원판으로 견줬다 — 무대마다 원판 0 이라 지금 기본과 같은 세계, `../shc/README.md`.)
2. **충돌이 줄기가 아니다.** 나무를 무대에 놓기 전에 `Beech_Tree` 충돌을 줄기 캡슐(반경 약 0.8 m, 높이 2~3 m)로 바꾸기를 팀에 요청한다. 고치지 않으면 우리 읽기(13.8 m)와 팀 이동 제약(8~13 m)이 둘 다 줄기와 다르다.
   팀이 못 고치면 우리 읽기 규칙을 바꿀지(예: 몸 높이 단면이나 그리기 메시 밑동으로 원판) 사람이 정한다 — 지금 규칙은 바꾸지 않았다.
3. **나무를 땅에 붙이기.** 같은 z 로 복사해서 묻히거나 떠 있다(End 키로 땅에 붙이면 된다).
4. 날씨는 보이는 것만이라 학습 세계에 넣을 것이 아직 없다. 날씨 규칙(비가 시야·발소리를 줄이는 것 등)은 나중 일이다.

## 7. 다시 만들기

```
# 레벨 읽기 (각 맵, 편집기 파이썬 — 저장 없음)
set ECO_SCAN_MAP=/Game/SHC/Maps/LV_SHC_RegionalWeatherTest
set ECO_SCAN_OUT=<이 폴더>/scan_LV_SHC_RegionalWeatherTest.json
UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script=<이 폴더>/unreal_level_scan.py -EnablePlugins=PythonScriptPlugin,GeometryScripting -unattended -nopause -nosplash -NullRHI -NoSound
# 통합 v3 모드 (무대·원판·은신처 JSON)
UnrealEditor-Cmd.exe <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=20000 -EcoV3ObstacleExport=<이 폴더>/v3_export_integration_s20000.json -benchmark -fps=60 -seconds=30 -NullRHI -NoSound -unattended -nosplash -nopause -DisablePlugins=Bridge,Fab
# 그림 (herbivore_rl/ 에서)
python results/v3/wild2/level_shc/plot_level_shc.py
```

## 파일

- `unreal_level_scan.py` — 편집기 파이썬 레벨 읽기(액터·충돌·지역·날씨 변수·땅 높이·단순 충돌 꼭짓점·우리 원판 계산).
- `scan_LV_SHC_RegionalWeatherTest.json`, `scan_LV_Ecosystem_IntegrationTest.json` — 그 결과.
- `v3_export_integration_s20000.json` — 통합 v3 모드 내보내기(무대 원점·원판·은신처 원·읽기 셈).
- `plot_level_shc.py` → `stage_Forest.png`·`stage_Barren.png`·`stage_Highland.png`(무대 + 둘레 50 m: 사슴 시작 자리 = 무대 전체, 은신처 원 4, 원판, 곁의 나무),
  `map_overview.png`(맵 전체), `forest_trees.png`(숲 지역 나무 11), `beech_tree_collision.png`(나무 하나의 충돌 모양), `summary.json`.
- `unreal_logs/` — 두 맵 헤드리스 실행에서 남긴 줄.
