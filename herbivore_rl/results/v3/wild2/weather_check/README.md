# 팀 지역 날씨(비·눈) 눈으로 확인 (10-18)

10-18 사용자 '언리얼에서 날씨도 바뀌도록 세팅되었다고 했는데 확인해봐'. 팀(avaroki 님) PR `ff8c8f4` 의 시험 레벨
`/Game/SHC/Maps/LV_SHC_RegionalWeatherTest` 를 GPU 로 그려 사진을 찍고, 팀 날씨 블루프린트의 상태를 프레임마다 읽어 적었다.
팀 파일·콘텐츠·설정·레벨은 하나도 바꾸지 않았다(실행 중 읽기만, SunSpeed 만 실행 중 콘솔 `set` 으로 메모리에서 바꿈).

## 한 줄 결론

- **화면·소리 연출로는 된다.** 카메라가 숲 상자에 들어가면 비가 오고(빗소리 포함), 고지 상자에 들어가면 눈이 오고, 메마른 땅은 맑다.
  경계를 넘으면 0.2 초 안에 알아챈다.
- 그런데 **비·눈이 카메라가 아니라 플레이어 캐릭터 자리에 생긴다**(안·밖 판정만 카메라). 보통 3인칭 놀이처럼 카메라가 캐릭터 곁이면 괜찮지만,
  카메라만 따로 옮기면(우리 촬영, 관전·위에서 보는 카메라) 비·눈이 안 보인다. 아래 사진은 촬영 감독이 캐릭터를 카메라 4 m 뒤에 옮겨 둔 판이다.
- 다른 것: 비는 들어가고 **7~9 초 뒤에야** 내리기 시작해 5 초 동안 세진다. 눈은 들어가자마자 다 내리고, **나온 뒤 약 5 초 동안 메마른 땅에도 그대로 내리다가 뚝 끊긴다.**
  지역 상자 높이(땅에서 약 150 m)보다 카메라가 높으면 비가 꺼진다. 하늘·빛은 그대로 맑아서 낮에는 비가 옅게 보인다. 빗소리는 나온 뒤에도 음량 0 으로 계속 재생된다.
  천둥은 비 14 초 동안 한 번도 안 났다. 눈 소리는 없다.
- **게임 값은 아무것도 안 바뀐다.** 지역 강수(`FRegionEnvironmentState.Rainfall`)는 0, 날씨 상태는 맑음 그대로다. 블루프린트가 지역 값을 쓰지 않는다.
- **우리 통합 레벨(`LV_Ecosystem_IntegrationTest`)에는 날씨 액터가 없어서 비·눈이 전혀 안 보인다**(통합 v3 모드로 찍음).
- **SunSpeed** 는 애셋을 안 고치고 `-ExecCmds="set BP_SkyManager_C SunSpeed 10"` 로 돌릴 수 있다. 초당 10° 로 해가 돌아 36 초에 하루가 되고, 8 초 사진은 이미 밤이다.
  팀 시계·동물 낮밤과는 따로 돈다.

## 1. 어떻게 봤나

이 레벨에는 통합 조정자가 없어 우리 통합 v3 모드와 촬영 감독이 돌지 않는다. 그래서 촬영 감독(`AI/Policy/EcoV3FilmDirector.*`)에 스위치만 더했다(없으면 예전과 같음).

| 스위치 | 하는 일 |
|---|---|
| `-EcoV3FilmStandalone` | 통합 v3 모드 없이 월드 시간으로 돈다. 장면 = `이름,x,y,h,방위°,숙임°,시작초,길이초[,x1,y1,h1]`(월드 m, h = 땅 위 m, 끝 자리가 있으면 곧게 옮김) |
| `-EcoV3FilmEvery=<n>` | n 프레임마다 한 장 (기본 1) |
| `-EcoV3FilmWatch=<글자;…>` | 클래스 이름에 그 글자가 든 액터의 블루프린트 변수·가리키는 컴포넌트(켜짐·소리 재생·음량·타임라인·자리·카메라 거리)를 캡처마다 `watch.txt` 에. 폰 자리·재생 중인 소리 모두, 1 초마다 프레임 시간도 |
| `-EcoV3FilmPawn=<m>` | 단독 촬영에서 플레이어 폰을 매 프레임 카메라 앞 m(음수 = 뒤) 땅 위에 둔다(이동 컴포넌트 끔) |

판 다섯(`film_runs/`, 기록 `unreal_logs/`):

| 판 | 무엇 |
|---|---|
| `shc_detached` | 카메라만 옮김(폰 그대로). 비·눈 이펙트가 어디 생기는지 |
| `shc_pawn` | 폰을 카메라 4 m 뒤에 둠. 사진 대부분과 경계 넘기 |
| `shc_sound` | 소리 확인. `-benchmark` 는 소리를 아예 끄므로(엔진 `FApp::CanEverRenderAudio`) `-UseFixedTimeStep -fps=30` 으로 |
| `shc_sunspeed` | `set BP_SkyManager_C SunSpeed 10` |
| `integration_v3` | 우리 통합 레벨, 통합 v3 모드(세션 20000) |

모두 1920×1080 창 GPU 렌더(`-game -windowed`), 소리 판 말고는 `-benchmark -fps=30`. 요약 숫자 `summary.json`, 그림 `make_weather_figs.py`.

## 2. 장면마다 본 것

| 장면 | 사진 | 본 것 |
|---|---|---|
| 숲 땅 높이 (비 세기 1) | `forest_rain.png`, `forest_rain_motion.png` | 가는 빗줄기와 땅의 물방울 고리. 맑은 하늘이라 옅다(서 있는 카메라의 이웃 프레임 차이로 보면 또렷하다) |
| 숲 100 m 위 | (`shc_pawn` f10) | 비 안 보임(이펙트는 캐릭터가 있는 땅 곁) |
| 숲 200 m 위 (상자 위) | (f15) | 카메라가 상자 밖이라 비가 꺼지기 시작(세기 0.41 → 0) |
| 고지 땅 높이 | `highland_snow.png` | 큰 눈송이가 가득. 하늘은 파랗다 |
| 메마른 땅 | `barren_clear.png` | 맑음, 비·눈 이펙트 꺼짐 |
| 메마른 땅 → 숲 경계 걸어 넘기 (5 m/s) | `weather_timeline.png` | 넘자 곧 비 이펙트가 켜지지만 세기 0 이라 안 보인다. 7.1 초 뒤 세지기 시작, 12 초 뒤 다 셈(카메라만 옮긴 판은 9.0 초 뒤) |
| 숲 → 메마른 땅 | 같은 그림 | 넘자 곧 약해지기 시작, 5 초 뒤 꺼짐 |
| 메마른 땅 → 고지 | `snow_crossing.png` | 넘은 지 0.2 초에 눈송이가 보인다(눈 세기 값은 7.5 초 뒤에 오르지만 눈송이 양과 상관없다) |
| 고지 → 메마른 땅 | `barren_snow_after_leaving.png` | 모래 위에 3~5 초 동안 눈이 그대로 펑펑 오다가 5.5 초에 뚝 끊긴다 |
| 우리 통합 레벨 | `integration_level.png` | 숲·고지 어디에도 비·눈 없음. 날씨 액터 0, `BP_SkyManager` 만 있음(SunSpeed 0) |
| SunSpeed 10 | `sunspeed_8s_14s.png` | 8 초에 이미 밤(달빛, 화면이 노랗고 푸르스름함), 14 초 더 어둡다. 어두우니 빗줄기가 또렷하다 |

가장 잘 보이는 사진: `highland_snow.png`, `barren_snow_after_leaving.png`, `forest_rain.png`(+ `forest_rain_motion.png`), `weather_timeline.png`.

## 3. 블루프린트가 하는 일 (변수 이름·노드 이름과 실행 중 상태로 재구성)

- `BP_SHC_RainRegionalWeather`(→ `TV_Region_Forest`)·`BP_SHC_SnowRegionalWeather`(→ `TV_Region_Highland`): 타이머로 `GetPlayerCameraManager → GetCameraLocation` 이
  `RegionBounds` 상자(`GetActorBounds`, 충돌 있는 컴포넌트만 — 트리거 상자 x ±750 m · y ±250 m · z ±150 m) 안인지 본다(`CameraInsideRegion`).
- 안이면 나이아가라(`Rain_System`·`NS_Blizzard`)를 켜고, 다른 타이머로 그 자리를 **플레이어 폰 자리**로 옮긴다. `shc_detached` 판에서 비 이펙트는 카메라에서
  120~1660 m 떨어진 폰 자리(처음엔 PlayerStart, 그 뒤 폰이 땅 밑으로 떨어지는 자리)에 있었고, `shc_pawn` 판에서는 카메라 곁 4 m 였다.
- 세기는 5 초 타임라인(`RainTimeline` Alpha 0 → 1)이 나이아가라 `RainfallIntensity` 와 빗소리 음량을 함께 올린다. 들어간 뒤 타임라인이 7~9 초 늦게 시작한다
  (판마다 7.1·9.0 초, 눈 7.5 초). 나가면 곧 거꾸로 5 초, 끝나면 이펙트를 끈다.
- 눈 이펙트(`NS_Blizzard`)는 세기 값을 따르지 않는 것으로 보인다 — 세기 0 일 때도 눈송이가 가득하고, 끌 때 줄지 않고 한 번에 사라진다.
- 빗소리(`A_Rain_Cue`)는 세기 = 음량(0.09 → 1.00). 비가 끝나도 소리 컴포넌트를 멈추지 않아 음량 0 으로 계속 재생되고, 마지막 비 자리에 남는다.
  천둥(`A_Thunder_Cue`)은 무작위 지연 뒤 나는 것 같은데 비 세기 1 인 14 초 동안 못 들었다. 눈 블루프린트에는 소리가 없다.
- 하늘·빛은 건드리지 않는다. 비 블루프린트의 `SkyManager`, 하늘 블루프린트의 `WeatherManager` 칸은 레벨에서 비어 있다.
- `BP_SkyManager`: 매 틱 `SunCurrentRotation` pitch += SunSpeed × 프레임 초, 해(`DirectionalLight`)와 달(`MoonLight`, 반대쪽)을 돌린다.
  SunSpeed 10 → 8 초에 pitch 315° → 34.7°(해가 지평선 밑), 21 초에 164.7°. 하루 = 360 / SunSpeed 초.
  팀 시계(`UEcoWorldClockSubsystem`)·우리 통합 v3 낮밤(60 + 60 초)과 이어져 있지 않다.

## 4. 문제 (팀에 알릴 것)

1. **이펙트가 카메라가 아니라 캐릭터를 따라간다.** 카메라가 캐릭터와 떨어지는 모든 경우(촬영·관전·위에서 보기)에 날씨가 안 보인다. `SetRainLocation` 이 쓰는 자리를
   카메라 자리(`GetCameraLocation`)로 바꾸면 판정과 이펙트가 같은 곳을 본다.
2. **비가 7~9 초 늦게 온다.** 경계를 넘어도 한동안 안 와서 '지역 날씨'로 안 읽힌다.
3. **눈이 끌 때 줄지 않는다.** 고지를 나온 뒤 5 초 동안 사막에 눈이 그대로 오다 뚝 끊긴다(`barren_snow_after_leaving.png`). 눈 이펙트도 세기 값을 따르게 하면 된다.
4. 빗소리 컴포넌트가 음량 0 으로 계속 돈다(멈추거나 지우기). 천둥은 못 들었다.
5. 상자 높이 ±150 m 를 넘는 카메라에서는 비가 꺼진다(높은 하늘 장면).
6. 하늘이 그대로라 낮 비는 옅다(구름·빛을 함께 바꾸면 더 비 같다).
7. 게임 값이 그대로다(5절) — 화면만 바뀐다.

(카메라만 옮긴 판에서 폰이 땅 밑으로 떨어졌다. 월드 파티션이 카메라 둘레만 불러 폰 밑 땅이 내려간 것으로 보인다 — 우리 촬영 방식 때문이지 팀 블루프린트 탓이 아니다.)

## 5. 오류·성능

- 세 SHC 판 기록에 블루프린트 오류(`Accessed None`)·애셋 없음·리디렉터 경고 없음. 엔진 시작 때 늘 나는 경고(편집기 위젯 등록, HLOD 빌더 클래스)만 있다.
- 프레임 시간(캡처 없는 1 초 창, 1920×1080): SHC 맵 가운값 6.7 ms(약 150 fps), 비·눈이 카메라 곁에 있을 때도 6.3~9.4 ms — 날씨 비용은 거의 안 보인다.
  우리 통합 레벨 v3 모드 8.6 ms.
- 우리 통합 레벨 기록: 오류·ensure 없음.

## 6. 날씨가 지금 게임 값에 하는 일 — 없음

- 블루프린트가 지역 값을 쓰지 않아 강수 0·맑음 그대로다(`AEcoRegionEnvironmentAdapter::ApplyRainfall` 은 코드에만 있고 어느 맵에도 없다). 날씨 상태에 눈 칸도 없다(`EEcoWeatherState` = 맑음·비·폭풍·가뭄).
- 강수를 읽는 곳: 팀 Social 위협 감지(`EcoThreatDetectionProcessor` 시야 × Lerp(1, `RainVisionMultiplier`, 강수))·팀 포식자 감각(`EcoPredatorPerception` 시야·청각),
  지역 먹이 재생(`bRainfallAffectsRegeneration`, 두 맵 모두 꺼짐). 비 배수 기본값이 1.0 이라 값이 들어와도 설정 전에는 그대로다.
- 우리 v3 두뇌·세계(언리얼 C++·파이썬 모두)는 날씨를 읽지 않는다. 파이썬 `weather` 기능(번호 8)은 자리만 있고 구현 안 됨, 눈 땅(`realism_terrain`)은 파이썬 R3 에만 있다.

## 7. 두 길 (만들지 않음 — 할 수 있는지와 드는 일)

**(i) 레벨 애셋을 안 고치고 우리 시험 레벨에 지역 날씨 보이기.** 된다. 우리 레벨에도 같은 트리거 상자 `TV_Region_Forest·Barren·Highland` 가 있다.
- 방법: 기본 꺼진 CVar(예 `eco.IntegratedV3.TeamWeather`)가 켜지면 통합 v3 모드가 무대를 만들 때 팀 블루프린트 두 개를 클래스 경로로 불러
  `SpawnActorDeferred` → `RegionBounds` 에 그 트리거 상자를 리플렉션으로 넣음 → `FinishSpawning`. C++ 40~60 줄 + 시험 1 + 사진 확인, 2~3 시간.
- 걸림: 이펙트가 플레이어 폰 자리에 생긴다. 우리 통합 레벨의 PlayerStart 는 숲 무대 안이라 거기만 비가 오고, 촬영 카메라 곁에는 안 온다.
  통합 v3 모드에서는 플레이어 폰이 사슴의 위협이라(`EcoPolicyV3IntegratedProcessors` 가 `UEcoPlayerEcologyComponent` 폰을 읽음) 촬영용으로 폰을 옮길 수 없다.
  그래서 촬영에 쓰려면 팀이 1번(카메라 자리)을 고치거나, 우리가 팀 나이아가라·소리 애셋만 빌려 카메라 곁에 켜는 작은 연출기(지역 값 → 화면)를 만든다(반나절~하루).
  2·3번(늦게 옴, 눈 끊김)은 블루프린트를 쓰는 한 그대로 따라온다.

**(ii) 나중에 비·눈을 행동에 넣기 (파이썬 먼저).** 된다. 계획서 `RL_V3_R4_PLAN.md` 5절과 같은 길.
- 필요한 것: 서버에 있는 지역 날씨 값(지역마다 강수 0~1 과 눈, 바뀌는 때를 표·시드로). 지금은 카메라 곁 연출뿐이라 값이 없다 → 팀이 어댑터로 `ApplyRainfall` 을 쓰고 눈 칸을 더해야 언리얼과 같은 세계가 된다.
- 파이썬: `weather` 기능(8)을 지역마다 정해진 표로 구현, 효과만(관측 칸 그대로) — 비 = 청각 × (1 − 0.5 × 강수)·시야 × (1 − 0.3 × 강수), 눈 = 사슴 × 0.6·늑대 × 0.85 (R3 눈 값).
  지금 두뇌 R1b 를 그 세계에서 재 보고(잡힘이 늘어나는지) 1 일. 효과가 크면 R4w 학습 1~2 일(계산) + 관측을 바꾸면 계약·C++·골든 1~2 일,
  언리얼 v3 세계가 지역 값을 읽게 하기 반나절~1 일.

## 8. 다시 만들기

```
# SHC 레벨 (폰을 카메라 4 m 뒤에) — shc_pawn
UnrealEditor.exe <uproject> /Game/SHC/Maps/LV_SHC_RegionalWeatherTest -game -EcoV3Film=shc_pawn -EcoV3FilmStandalone -EcoV3FilmPawn=-4 -EcoV3FilmOut=<폴더>
  "-EcoV3FilmShots=forest_west,300,420,1.8,180,2,16,1;forest_tree11,343,418,1.8,-90,4,19,1;forest_high100,342,300,100,90,-30,24,1;forest_high200,342,300,200,90,-35,29,2;highland_ground,340,-470,1.8,90,0,37,2;highland_high,340,-600,60,90,-20,42,1;barren_ground,340,10,1.8,90,0,48,1;boundary_in,340,230,1.8,90,0,55,8,340,270,1.8;forest_stay,340,270,1.8,90,0,63,12;boundary_out,340,270,1.8,-90,0,75,8,340,230,1.8;barren_stay,340,230,1.8,-90,0,83,6;highland_in,340,-230,1.8,-90,0,92,8,340,-270,1.8;highland_stay,340,-270,1.8,-90,0,100,6"
  -EcoV3FilmEvery=6 "-EcoV3FilmWatch=RegionalWeather;SkyManager" -benchmark -fps=30 -seconds=115 -windowed -ResX=1920 -ResY=1080 -nosplash -DisablePlugins=Bridge,Fab
# shc_detached = 위에서 -EcoV3FilmPawn 빼고 장면 시작초를 당긴 판 (shots.json), shc_sunspeed = + "-ExecCmds=set BP_SkyManager_C SunSpeed 10",
# shc_sound = -benchmark 대신 -UseFixedTimeStep (소리가 실제로 난다), integration_v3 = /Game/Map/LV_Ecosystem_IntegrationTest -EcoIntegratedV3 -EcoV3Seed=20000
#   "-EcoV3FilmShots=Forest,wide,0,6,1;Forest,deer,0,10,1;Highland,wide,0,14,1;Highland,deer,0,18,1;Barren,wide,0,22,1" -EcoV3FilmEvery=15
# 요약·그림 (herbivore_rl/ 에서, --frames = 촬영 출력 폴더 — 판 이름 폴더들)
python results/v3/wild2/weather_check/make_weather_figs.py --frames <폴더>
```

## 파일

- `README.md` — 이 글. `summary.json` — 판마다 지역 넘은 때·세기 지연·이펙트와 카메라·폰 거리·소리·프레임 시간(`make_weather_figs.py` 가 만듦).
- `film_runs/<판>/watch.txt`·`shots.json` — 촬영 감독 기록(캡처마다 팀 날씨·하늘 블루프린트 상태, 1 초마다 프레임 시간). `unreal_logs/<판>.log` — 언리얼 기록.
- 사진(1280×720): `forest_rain.png`, `forest_rain_motion.png`, `highland_snow.png`, `barren_clear.png`, `snow_crossing.png`, `barren_snow_after_leaving.png`,
  `sunspeed_8s_14s.png`, `integration_level.png`. 그림 `weather_timeline.png`.
