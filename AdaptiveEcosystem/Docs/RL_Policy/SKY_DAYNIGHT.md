# 하늘 연출 — 해·달이 팀 시계를 따라 돈다 (2026-10-27)

사용자 결정(10-27 'ㄱㄱ', B '하늘 연동'): 통합 v3 모드에서 사슴·늑대는 팀 시계(낮 60 초·밤 60 초)를 따라 낮밤을 겪는데, 화면의 해는 모든 맵에서 45° 에 멈춰 있어 늘 낮으로 보인다. 우리 C++ 연출이 해·달을 팀 시계에 맞춰 돌리고, 밤에도 늑대·사슴이 보이게 달빛을 올린다.

- 코드: `Source/AdaptiveEcosystem/AI/Policy/EcoV3SkyPresenter.h/.cpp` (`UEcoV3SkyPresenterSubsystem`, 순수 함수·빛 손잡이 `EcoV3Sky`)
- 시험: `Source/AdaptiveEcosystem/AI/Policy/Tests/EcoV3SkyPresenterTest.cpp` (`AdaptiveEcosystem.Policy.V3.Sky.*` 5 개)
- 상태 (10-27 오후): UBT 두 판(적응 unity·`-DisableAdaptiveUnity`) 성공, 자동화 `AdaptiveEcosystem` 255 개 실패 0 (`Sky.*` 5 개 포함). 창 없는 게임(`-RenderOffscreen`·`-NullRHI`)으로
  두 맵의 낮·해 질 녘·밤·새벽 화면과 하늘 어둠 = v3 어둠, 팀 기본 v1 은 그대로, 같은 시드 사슴 줄 바이트 동일을 확인했다 (9절). 기본값은 오전 창 모드 확인(달 색 섞기 1)과 9절 화면으로 정했다.
  10-27 적대적 확인(코드 그대로)에서 창 없는 리슨 + 클라이언트 1·데디케이티드 + 클라이언트 2 의 클라이언트 하늘이 되감김·건너뜀 없이 서버 시계를 따라가는 것과
  원본 `LV_JYU_Ecosystem` 에서도 같은 길로 도는 것을 봤다 (9.1절). 편집기 PIE·fps 비교는 아직이다.

## 1. 그리기만 한다

이 연출은 빛만 돌린다. v3 세계 규칙(파이썬 = C++ 비트 일치)·관측·개체·난수·팀 시계·레벨·애셋에 쓰지 않는다.

- 사슴·늑대의 낮밤(v3 어둠 `d`)은 전처럼 팀 시계에 맞춘 전역 스텝이 정한다 (`UEcoPolicyV3IntegratedSubsystem::TryCreateContexts`·`CheckClockDrift`). 어느 v3 규칙도 방향광·하늘 BP 를 읽지 않는다 (소스에서 `DirectionalLight` 를 읽는 규칙 코드는 없다).
- 팀 하늘 BP·맵·라이트 액터는 고치지 않는다. 실행 중에만 회전·세기·색과 BP 인스턴스 칸 하나를 바꾸고, 끄면 처음 값으로 되돌린다. 아무것도 저장하지 않는다.
- 팀 기본 모드(`eco.IntegratedPolicyVersion 1`)는 그대로다 (기본 `eco.Sky.Link 1` 은 통합 v3 월드에서만 켠다).

## 2. 조사한 것 (10-27)

### 2.1 팀 시계와 전달

- 권위 시계 `UEcoWorldClockSubsystem` (서버·단독에만 있다): 조정자 `AEcoCreatureIntegrationSpawner::Reconcile` 이 매 프레임 월드 dt 로 앞으로 보낸다. 표본 `FEcoServerTimeSnapshot` = 판(WorldEpoch)·서버 초·위상(낮/밤·시작·끝). 통합 v3 모드는 낮밤을 60 + 60 초로 맞춘다.
- 팀 BP 쪽 입구 `AEcoRegionEnvironmentAdapter::OnClockUpdated(위상, 진행 p)` 는 0.2 초마다 불리지만, 4 맵 모두 이 이벤트로 하늘을 돌리는 BP 가 없다.
- 클라이언트는 `AEcoGameState` 요약 `FEcoCompletedWorldSummary::Time` 을 받는다. 서버가 자원 스텝(1 초 이하)마다 `PublishEcologySummary` 로 올리고 `StateRevision` 이 하나 오른다 — 약 1 초마다 온다.
- v3 동물의 낮밤은 팀 시계와 0.13 초 안으로 맞는다 (조사 측정. 4 스텝 = 0.53 초 넘게 벌어지면 다시 맞춘다).

### 2.2 팀 하늘 BP `/Game/SHC/Blueprints/Sky/BP_SkyManager`

편집기 파이썬(`UnrealEditor-Cmd -run=pythonscript`, 편집기 닫힘, 저장 안 함)으로 BP 그래프를 T3D 글로 내보내 읽었다.

- 생성 스크립트: `SunCurrentRotation = SunDefaultRotaion`.
- BeginPlay: `IsValid(Sun) && DynamicSun` 이 아니면 `SetActorTickEnabled(false)`. 맞으면 아무것도 하지 않는다.
- Tick (`DynamicSun` 일 때 매 프레임):
  1. `SunCurrentRotation = (Pitch = Clamp(SunCurrentRotation.Pitch + SunSpeed × dt, 0, 360), Yaw = 0, Roll = 0)`
  2. `Sun.SetActorRotation(SunCurrentRotation)`
  3. `Moon.SetActorRotation(MakeRotator(Roll, Pitch + 180, Yaw) of Sun.GetActorRotation())` — 달은 늘 해의 정반대
  4. `SunCurrentRotation.Pitch >= 360` 이면 0 으로
  - 연결 안 된 `Debug` 함수(개발 전용 화면 글 "Sun Current Pitch:")는 불리지 않는다. 세기·색·하늘빛·안개는 건드리지 않는다.
- 놓인 값 (4 맵 `/Game/Map/LV_Ecosystem_IntegrationTest`·`/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem`·`/Game/JYU/Maps/LV_JYU_Ecosystem`·`/Game/SHC/Maps/LV_SHC_RegionalWeatherTest` 같음): `SunSpeed 0`·`DynamicSun 켬`·`SunDefaultRotaion (p315)` → 해가 45° 높이에 멈춤.
- 조사 실행(`SunSpeed 3`)에서 매 초 `SunCurrentRotation` 의 pitch 와 해 액터 pitch 가 같이 움직였다 — BP Tick 이 그 칸을 매 프레임 해에 넣는다.
- 조사 때 콘솔 `set BP_SkyManager_C SunCurrentRotation (Pitch=180)` 이 안 먹은 까닭 (엔진 소스로 본 것, 실행 확인 전): 편집기 빌드의 `set` 은 값을 넣은 뒤 `PostEditChangeProperty` 를 부르고, PIE 가 아닌 `-game` 월드의 액터는 거기서 생성 스크립트를 다시 돌린다 (`AActor::ReregisterComponentsWhenModified`). 생성 스크립트가 `SunCurrentRotation = SunDefaultRotaion` 이라 곧바로 315° 로 덮였다. `SunSpeed` 는 생성 스크립트가 건드리지 않아 남았다. 우리 C++ 는 반사로 인스턴스 칸만 쓰므로 생성 스크립트가 다시 돌지 않는다.

### 2.3 빛·대기·안개 (`LV_Ecosystem_IntegrationTest` 기준 — 다른 3 맵도 해·달·하늘빛 세기·색인·회전은 같고, 안개·대기 세부 값은 이 맵만 읽었다)

| 액터 | 값 |
|---|---|
| `DirectionalLight` (해) | 8 lux, 흰색, Movable, 대기 빛 색인 0 |
| `MoonLight` (달) | 0.01 lux, 노랑 (255, 242, 77), Movable, 대기 빛 색인 1 |
| `SkyLight` | 1, 실시간 캡처, 아래 반구 검정 |
| `SkyAtmosphere` | 지구 기본 (반지름 6360 km, 높이 60 km) |
| `ExponentialHeightFog` | 산란 색 0, 대기 기여 ×1, 방향 산란 0 |
| 후처리 볼륨 | 없음 (프로젝트 자동 노출 — 확장 휘도 범위 켬, Lumen GI·반사) |

- 해·달은 대기 빛이라 땅에 닿는 세기에 대기 투과가 곱해진다. 지평선 아래 빛은 행성 안을 지나 투과가 0 이 된다 (`FAtmosphereSetup::GetTransmittanceAtGroundLevel`, 최소 고도 −90°). 그래서 낮의 달·밤의 해는 저절로 꺼진다.
- 안개는 자기 산란 색이 0 이고 대기 기여만 쓰므로 밤에 같이 어두워진다 — 손대지 않는다.
- 팀 달빛 0.01 lux 는 해의 1/800 이다. 조사의 `SunSpeed 3` 화면에서 밤은 거의 깜깜한 주황·갈색이었다 (노란 달빛 + 자동 노출).

## 3. 설계

### 3.1 시간 → 해 각도

팀 시계 위상(낮/밤)과 진행 `p` (0~1) 로 해 방향광 pitch 를 정한다.

| 위상 | 해 pitch | 해 높이 `e = asin(−sin pitch)` |
|---|---|---|
| 낮 `p` | `180 + 180p` | `0 → 90° (30 초) → 0` |
| 밤 `p` | `360 + 180p` (= `180p`) | `0 → −90° (90 초) → 0` |

- 지평선 = 0·60·120 초. 낮 끝(pitch 360 = 0)과 밤 시작, 밤 끝(180)과 낮 시작이 이어진다. 60 초 낮이면 3°/s.
- yaw 는 팀 BP 처럼 0 이다 — 해가 +X 쪽에서 떠서 머리 위를 지나 −X 쪽으로 진다. 팀 기본 해(315°, 45° 높이)는 이 길의 낮 45 초 자리다. 팀 BP 가 없는 맵은 해 방향광이 놓인 방위(앞 방향의 방위 — roll 180 이어도 맞다)를 yaw 로 쓴다.
- 달 = 해 + 180° pitch (팀 BP 식 그대로 — 빛 방향이 정반대, 높이 = −해 높이).
- 하늘 어둠 `d = clamp(0.5 − e / 36°, 0, 1)` 은 v3 어둠(`EcoObservationV3::DayNightPhase`, 주기 900·어스름 45 스텝)과 같다. v3 어스름은 주기의 5 % = 반주기의 10 % = 180° × 0.1 = 18° 라, 경계 ±6 초가 해 높이 ±18° 다. 시험 `Sky.DarknessParity` 가 1800 스텝 모두 1e-9 안으로 같음을 본다 (파이썬 사본 계산: 가장 큰 차이 2e-15).

### 3.2 밝기

| 빛 | 세기 |
|---|---|
| 해 | 팀 값 × `SunIntensityScale(e)`: 지평선 위 1, 아래 12°(항해 박명, 해 진 뒤 4 초)까지 smoothstep 으로 0 |
| 달 | 팀 값 → 밤 달빛 `eco.Sky.NightBrightness` (기본 1 lux), 밤 정도 `NightFactor(d)` 만큼. 팀 값보다 어둡게 하지 않는다 |
| 달 색 | 팀 색 → 차가운 달빛 (0.55, 0.65, 1.0 선형), `eco.Sky.MoonTint × NightFactor(d)` 만큼 (기본 1 — 자동 노출이 한밤을 낮 밝기로 맞춰 팀 노랑 달빛이면 노란 낮처럼 보였다. 0 = 팀 색) |
| 하늘빛 | 팀 값 × `Lerp(1, eco.Sky.NightSkyLight, NightFactor(d))` (기본 1 = 팀 값) |

- `NightFactor(d) = smoothstep((d − 0.5) / 0.5)`: 해 질 때 0, 해가 18° 내려간 어스름 끝(6 초 뒤) 1. 새벽에는 거꾸로. 화면의 밤 = 규칙의 밤이다.
- 해 세기를 줄이는 것은 대기 없는 맵의 안전장치다 (대기 있는 맵은 투과가 이미 0 이라 차이 없음). 지평선 위에서는 팀 값 그대로이고 노을은 대기가 만든다.
- 해가 지고 0~6 초 사이는 해·달 모두 지평선 가까이 있어 잠깐 가장 어둡다 (하늘빛만 남는다). 어스름으로 읽히는지 화면으로 본다.

### 3.3 팀 하늘 BP 와 다투지 않기

1. 매 프레임 팀 BP 인스턴스의 `SunCurrentRotation` 칸에 우리 pitch 를 반사로 써 둔다 (`SunSpeed` 는 바꾸지 않는다 — 0 그대로). BP Tick 이 다음 프레임에 그 값(+ 0 × dt)을 해에 넣고 달을 반대로 돌리므로 우리 값과 같다.
2. 카메라 갱신 뒤 `TG_PostUpdateWork` (BP Tick `TG_PrePhysics` 뒤) 에 해·달 방향광을 직접 돌려 이번 프레임 값을 정확히 맞춘다. BP 가 없거나 Tick 이 꺼진 맵(`DynamicSun` 끔 등)에서도 하늘이 돈다.
3. 끄면 BP 칸·해·달 회전·세기·달 색·하늘빛 세기를 처음 값으로 되돌린다. BP 는 다음 Tick 에 315° 로 돌아간다.

찾기: `SunCurrentRotation`(FRotator)·`Sun` 칸이 있는 블루프린트 액터(이름 순 첫째)의 `Sun`·`Moon` 방향광. 없거나 비면 대기 빛 색인 0(해)·1(달) 방향광 중 가장 밝은 것, 대기 빛이 없으면 가장 밝은 방향광을 해로(달 없음). Static 해는 돌릴 수 없어 아무것도 바꾸지 않는다 (기록 한 줄, 1 초마다 다시 찾는다).

### 3.4 시간 출처와 클라이언트 보간

- 서버·단독: 팀 시계를 매 프레임 읽는다.
- 클라이언트: GameState 요약이 바뀔 때(`StateRevision`)만 복사해 `Time` 을 표본으로 쓴다.
- 표시 시계(`EcoV3Sky::StepClock`): 프레임마다 dt 만큼 앞으로 가고, 새 표본이 오면 오차를 2 초 시간 상수로 나눠 메운다. 메우는 몫이 2 초 이하라 뒤로 가지 않는다. 2 초 넘게 어긋나거나 판이 바뀌면 곧바로 맞춘다. 다음 표본 전에 위상 끝을 넘으면 본 낮·밤 길이로 다음 위상을 이어 그린다.
- 시뮬레이션(파이썬 사본, 60 fps): 1 초마다 정확한 표본 → 어긋남 0, 0.1 초 늦고 ±0.15 초 흔들리는 표본 → 뒤로 가지 않고 늦은 서버 시각과 0.09 초 안.

## 4. 켜는 조건과 콘솔

| 콘솔 변수 | 기본 | 뜻 |
|---|---|---|
| `eco.Sky.Link` | 1 | 0 = 끔 (켜져 있었으면 되돌림), 1 = 통합 v3 모드 월드, 2 = 팀 시계가 도는 모든 게임 월드 (팀 v1 확인용 — 고른 사람만) |
| `eco.Sky.NightBrightness` | 1 | 한밤 달빛 lux (팀 0.01, 1000 에서 자름) |
| `eco.Sky.MoonTint` | 1 | 밤 달빛 색 섞기 0~1 (0 = 팀 노랑 그대로) |
| `eco.Sky.NightSkyLight` | 1 | 한밤 하늘빛 배수 (0~100) |
| `eco.Sky.LogSeconds` | 10 | `[EcoV3I] 하늘` 기록 간격 (팀 시계 초, 0 = 켬·낮밤 바뀜 때만) |

- 1 의 '통합 v3 모드': 서버·단독은 `UEcoPolicyV3IntegratedSubsystem::IsActive()`, 클라이언트(통합 서브시스템이 켜지지 않는다)는 `eco.IntegratedPolicyVersion 3` 이거나 맵 조정자 `bUseV3Policy`. 데디케이티드 서버가 `-EcoIntegratedV3` 로 돌고 클라이언트가 v1 이면 클라이언트 하늘은 돌지 않는다 — 클라이언트에도 같은 스위치를 주거나 `eco.Sky.Link 2`.
- 시간 출처가 없으면(시계 시작 전·요약 전) 기다리고 하늘은 팀 그대로다.
- 데디케이티드 서버에는 틱을 걸지 않는다. NullRHI 헤드리스 실행에서는 돈다 — 빛만 돌리므로 시뮬레이션과 무관하고, 헤드리스로 확인할 수 있다 (8절).
- 콘솔 값은 매 프레임 읽어 실행 중에 바꿔도 된다.

기록 (`LogEcoPolicyV3I`):

- `[EcoV3I] 하늘 연출 켬 (eco.Sky.Link 1, 권위 — 팀 시계): 해 DirectionalLight_UAID_… 세기 8.00 · 달 DirectionalLight_UAID_… 세기 0.010 색 (255,242,77) · 하늘빛 SkyLight_… 세기 1.00 | 팀 하늘 BP BP_SkyManager_C_UAID_… (SunSpeed 0.00 그대로 · SunCurrentRotation p315.0 → 실행 중 우리 pitch 를 쓴다) | 해 길 yaw 0° … | 밤 달빛 1.00 lux …`
- `[EcoV3I] 하늘 | 켬·낮 시작·밤 시작·간격 | 팀 시계 72.0초 밤 20% | 해 pitch 36.0° 높이 −36.0° → 하늘 d=1.00 (v3 Barren 세계 d=1.00) | 해 0.00 · 달 1.000 · 하늘빛 1.00` — 서버·단독 통합 v3 는 첫 지역 세계의 v3 어둠을 같이 적는다 (두 값이 0.02 안이면 맞다 — 0.13 초 차 = 0.4° = d 0.011).
- `[EcoV3I] 하늘 연출 끔 (…) — 해·달·하늘빛·팀 하늘 BP 칸을 처음 값으로 되돌렸다`

## 5. 하지 않은 것

- v3 세계 규칙·파이썬 미러·학습 가중치: 그대로.
- 팀 하늘 BP·맵·라이트·안개·후처리 애셋: 그대로 (저장 없음). `SunSpeed` 도 그대로.
- 팀 기본 v1 월드: `eco.Sky.Link 1` 에서 아무것도 바꾸지 않는다.
- 자동 노출·후처리: 건드리지 않는다. 밤 밝기는 달빛·하늘빛 세기로만 조절한다.
- 해 높이를 실제 위도처럼 기울이지 않았다 (낮 30 초에 머리 위를 지난다 — 결정된 식 `180 + 180p`).

## 6. 시험 (`AdaptiveEcosystem.Policy.V3.Sky.*`)

| 시험 | 보는 것 |
|---|---|
| `Sky.Angles` | 지평선 0·60·120 초, 30 초 머리 위·90 초 발밑, 경계에서 이어짐, 0.25 초 걸음 연속, 낮 위·밤 아래, 해 높이 = 방향광 해 자리 높이, +X 에서 떠 −X 로 짐(yaw 90 이면 +Y), 달 정반대(정규화된 해 회전에서 만들어도 같다), 팀 기본 315° = 낮 45 초, 범위 밖·NaN 진행 자름 |
| `Sky.DarknessParity` | 하늘 어둠 = v3 어둠 1800 스텝 1e-9 안, 어스름 칸 수, 지평선 0.5·±18° 0/1 |
| `Sky.Brightness` | 밤 정도·해 세기 배수 곡선, 한낮(팀 값 그대로)·한밤(해 0·달 1)·어스름 0/3/6 초 달빛, 해 진 뒤 달빛이 줄지 않음, 팀보다 어둡게 안 함, 이상한 콘솔 값 자름, 달 색 섞기·하늘빛 배수 |
| `Sky.ClientClock` | 표본 전 없음, 첫 표본 맞춤, 정확한 1 초 표본 130 초 어긋남 0, 늦고 흔들리는 표본에 뒤로 안 감·0.3 초 안, 5 초 건너뜀·판 바뀜 곧바로 맞춤, 멈춤 그대로, 위상 밖 이어 감·본 길이 사용, 깨진 표본 무시 |
| `Sky.Rig` | 시험 월드 방향광 셋: 색인 0·1 로 해·달 찾기(대기 빛 아닌 빛은 무시), 해 길 방위 = 놓인 방위 105°, 한밤·한낮·낮 15 초 방향과 세기, 달 색 섞기, 되돌리기(회전·세기·색), Static 해·방향광 없는 월드는 찾기 실패 |

팀 하늘 BP 칸 쓰기(반사)는 시험 월드에 BP 가 없어 자동화로 보지 않는다 — 8절 헤드리스 확인으로 본다.

## 7. 알려진 한계·후속

- 방향광이 매 프레임 움직이므로 가상 그림자 맵 캐시가 매 프레임 무효가 된다 (`SunSpeed` 를 켜도 같다). fps 가 떨어지면 일정 각도(예: 0.1°)마다만 돌리는 콘솔 값을 더할 수 있다.
- 클라이언트가 통합 v3 인지 알 길이 콘솔 스위치·조정자 칸뿐이다 (4절).
- 밤 밝기는 자동 노출과 함께 보인다 — 달빛을 올려도 자동 노출이 일부 되돌린다. 기본값은 화면으로 정한다.

## 8. 화면 확인 때 볼 것

빌드(UBT 적응 unity·`-DisableAdaptiveUnity`)와 자동화(`-ini:Engine:[ConsoleVariables]:eco.IntegratedPolicyVersion=1`, 실패 0 — 새 `Sky.*` 5 개 포함) 뒤:

1. **헤드리스 각도** (`-NullRHI`, 통합 v3): `/Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3Film=sky -EcoV3FilmOut=<폴더> -EcoV3FilmShots=Forest,wide,0,1,136 -EcoV3FilmEvery=30 -EcoV3FilmWatch=SkyManager -benchmark -fps=30 -seconds=150 -NullRHI -NoSound -unattended`. `watch.txt` 의 `SunCurrentRotation=(p…)` 가 `180 + 3t` (낮)·`3(t − 60)` (밤) 를 따르고 `Sun`·`Moon` 회전이 그와 같은지 (해 액터 pitch 는 정규화돼 보인다 — 예: p210 → `(p−30, y180)`), `SunSpeed=0.000` 그대로인지. 기록의 `하늘 d` 와 `v3 … 세계 d` 가 0.02 안인지.
2. **낮밤 화면** (1280×720, 통합 v3 — 이 컴퓨터는 `UserEngine.ini` 로 v3 기본. 보이는 창을 띄우지 않고 `-RenderOffscreen` 으로 찍는다 — 10-27 사용자 지시, 창이 포커스를 빼앗았다): 0 초 해가 +X 지평선, 30 초 머리 위, 60 초 −X 로 짐, 밤에 달이 +X 에서 떠 90 초 머리 위, 120 초 다시 해 뜸. 해·그림자가 떨리지 않는지 (BP 와 우리 값이 프레임마다 다투지 않는지). Niagara 엔진 assert(타입 해시 충돌)가 다시 나면 확인용 실행에만 `-EcoV3WeatherVisuals=0`.
3. **밤 밝기** (가장 중요): 한밤에 늑대·사슴이 보이는지. 자동 노출이 따라오는 몇 초 뒤에 본다. 어두우면 `eco.Sky.NightBrightness 2`~`4`, 그늘이 검으면 `eco.Sky.NightSkyLight 2`~`3`, 밤이 저녁처럼 노라면 `eco.Sky.MoonTint 0.5`~`1`. 정한 값을 기본값으로 옮긴다 (`kDefaultNightLux` 등).
4. **어스름**: 해 지고 0~6 초의 잠깐 어두운 구간·노을 하늘이 어색하지 않은지. 구름(`VolumetricCloud`)이 밤에 빛나지 않는지, 안개가 같이 어두워지는지.
5. **켬·끔**: 실행 중 `eco.Sky.Link 0` → 해가 45° 로 돌아오고 달 0.01·노랑으로, `1` → 다시 연동. `eco.IntegratedPolicyVersion 1` (팀 기본) 실행에는 `하늘 연출 켬` 기록이 없고 하늘이 그대로인지.
6. **조연우 맵** `LV_EcoV3_JYUEcosystem`·`LV_JYU_Ecosystem` 에서도 같은 길로 도는지 (같은 팀 하늘 BP·라이트 구성).
7. **Dedicated + Client 2**: 클라이언트 하늘이 서버 시계와 1 초 안으로 같이 돌고 요약 사이에 끊기지 않는지 (클라이언트에도 `-EcoIntegratedV3` 또는 `eco.Sky.Link 2`). 데디케이티드 서버 기록에는 하늘 줄이 없다.
8. **성능**: 켬·끔 fps 비교 (`stat unit` 또는 촬영 감독 `perf` 줄) — 7절 그림자 캐시.

## 9. 10-27 확인 결과 (창 없음)

조건: 사용자 지시(10-27 — 게임 창이 포커스를 빼앗았다)로 보이는 창을 띄우지 않았다. 화면은 `UnrealEditor -game -RenderOffscreen -ResX=1280 -ResY=720`(창 없이 그림),
나머지는 `UnrealEditor-Cmd -game -NullRHI` 로 돌렸다. 모두 `-benchmark -fps=30 -unattended -nosplash -NoSound` 와 끝 시간을 줬고, 실행마다 보이는 창 감시를 걸어 0 개였다.
통합 v3, 세션 20010, 사슴 128 × 지역 셋. 화면은 촬영 감독이 1 초마다 한 장(`-EcoV3FilmEvery=30`), 팀 하늘 BP 칸은 `-EcoV3FilmWatch=SkyManager`, 하늘 기록은 `eco.Sky.LogSeconds 5`.

| 확인 | 결과 |
|---|---|
| 하늘 어둠 = v3 어둠 | 4 판(통합 맵·조연우 복사 맵 × 숲 넓게·늑대 따라가기)의 5 초마다 기록에서 `하늘 d` 와 `v3 Forest 세계 d` 의 차가 최대 0.01 |
| 팀 하늘 BP 칸 | `SunCurrentRotation` pitch 가 낮 `180 + 3t`·밤 `3(t − 60)` 을 따른다 (1 초마다). 해·달 액터 회전은 정반대, `SunSpeed=0.000` 그대로 |
| 켬·끔 | 124 초 `eco.Sky.Link 0` → 125 초 화면이 315°(45° 높이) 고정 하늘, `하늘 연출 끔` 기록. 127 초 `1` → 다시 연동 |
| 팀 기본 v1 | `-ini:Engine:[ConsoleVariables]:eco.IntegratedPolicyVersion=1` 통합 맵 131 초: 하늘 기록 0 줄, pitch 315 내내, 화면 밝기 155~156 내내 |
| 같은 시드 | `-NullRHI` 121 초 사슴 줄 `[EcoV3Obs]` 343218 개가 변경 전 빌드(`28baef7`) = 하늘 켬(기본) = `eco.Sky.Link=0` 으로 바이트까지 같다 |
| 조연우 복사 맵 | 같은 팀 하늘 BP·라이트 구성으로 같은 길로 돈다 (원본 `LV_JYU_Ecosystem` 은 9.1절) |

화면 밝기 (화면 평균 휘도 0~255, Rec.709 가중, 1 초 표본):

| 판 | 낮 10~50 초 | 밤 70~110 초 (최저) | 해 질 녘 60~66 초 최저 | 새벽 114~122 초 최저 | 평균 60 밑인 초 |
|---|---|---|---|---|---|
| 통합 맵 숲 넓게 | 156 | 138 (123) | 35 | 36 | 62·63·118·119 |
| 통합 맵 숲 늑대 | 150 | 152 (143) | 28 | 43 | 63~65·119·120 |
| 조연우 복사 맵 숲 넓게 | 168 | 163 (157) | 57 | 50 | 62·119 |
| 조연우 복사 맵 숲 늑대 | 167 | 160 (152) | 41 | 46 | 63·119·120 |
| 팀 기본 v1 통합 맵 (하늘 그대로) | 155 | 156 (155) | 156 | 155 | 없음 |

밤 달빛 비교 (통합 맵 숲 늑대 따라가기, 같은 시드·같은 카메라 길, 0.5 초에 `eco.Sky.NightBrightness`):

| 밤 달빛 (lux) | 밤 70~110 초 평균 (최저) | 평균 60 밑인 초 |
|---|---|---|
| 0.1 | 121 (31) | 63~72·116~120 (15 초) |
| 0.3 | 137 (103) | 63~67·118~120 (8 초) |
| 1 (기본) | 152 (143) | 63~65·119·120 (5 초) |
| 2 | 158 (156) | 63·120 (2 초) |

- 한밤에는 자동 노출이 화면을 낮 밝기 가까이 올린다. 늑대·사슴이 달 그림자까지 보인다. 밤은 차가운 달빛 색과 해 없는 하늘로 구분되지만, 낮처럼 밝게 느껴질 수 있다.
- 달빛을 낮춰도 한밤 화면은 크게 어두워지지 않고(자동 노출) 어스름 어둠만 길어진다. 기본 1 lux 를 그대로 뒀다. 어스름 어둠을 더 줄이려면 `eco.Sky.NightBrightness 2` 를 쓴다.
- 어스름 어둠: 해 질 녘(61~65 초)·새벽(118~120 초)에는 해·달이 모두 지평선 근처라 대기를 길게 지나 약하고, 자동 노출이 따라오는 동안 2~5 초 어둡다. 늑대 따라가기 120 초 한 장은 늑대가 거의 보이지 않는다.
- 조연우 복사 맵 숲은 처음부터 맑고 74 초쯤부터 비가 온다 — 팀 날씨(비 주기)와 같은 때다 (LIVE_ADAPT_SPEC.md 5.1 '시작 날씨').
- 화면 파일 (저장소 밖 `C:/kwon/univ/3-1/GameContentsCapstoneDesign/week8_assets/sky/`): 판마다 30·60·90·120 초 한 장(`sky_<맵>_forest_<wide|wolf>_t030_day.png` 등), 사진판(`*_sheet.png`), 밝기 표(`*_brightness.tsv`),
  하늘 d·v3 d 표(`sky_vs_v3_darkness.tsv`), 밤 달빛 비교 사진판(`sky_IT_forest_wolf_nightlux*_sheet.png`).
- 아직: 편집기 PIE, 켬·끔 fps 비교 (Dedicated + Client 2·원본 `LV_JYU_Ecosystem` 은 9.1절).

### 9.1 클라이언트·원본 맵 (10-27 적대적 확인, 코드 그대로)

조건: 보이는 창 없이 모두 `UnrealEditor-Cmd`(서버 `-server`, 리슨 호스트·클라이언트·단독 `-game -NullRHI`)로, 실시간(고정 스텝 아님)·`-seconds` 끝 시간,
`-EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=20010 -NoSound -unattended -nosplash`, `eco.Sky.LogSeconds 0.25`. 실행마다 0.25 초 간격으로 언리얼 프로세스의
보이는 창을 찾았고 0 개였다. 통합 맵 `/Game/Map/LV_Ecosystem_IntegrationTest`, 같은 컴퓨터 127.0.0.1.

| 판 | 클라이언트 하늘 | 서버 시계와 차 |
|---|---|---|
| 리슨 호스트 + 클라이언트 1 (115 초) | `하늘 연출 켬 (… 클라이언트 — GameState 요약 사이를 이어 그린다)` 한 번, 끔 0. 표시 시계 8 → 122 초에서 되감김 0, 0.25 초 기록 사이 (Δ표시 시계 − Δ벽시계)가 −0.06 ~ +0.16 초 (+0.16 은 켠 직후 한 번) | 같은 벽시계의 호스트(권위 팀 시계)와 평균 −0.01 초, −0.23 ~ +0.07 초 → 하늘 d 차 최대 0.02 |
| 데디케이티드 + 클라이언트 2 (115 초) | 두 클라이언트 모두 켬 한 번·끔 0, 되감김 0, 기록 사이 차 −0.08 ~ +0.11 초 | 서버 기록(`Forest 날씨 \| N초`, 10 초마다 — 벽시계와 0.03 초 안)으로 잰 서버 시각보다 평균 0.1 초 늦다. 켠 처음 몇 초는 0.8~1.0 초 늦게 시작해 메우고, 5 초 뒤부터 0.03 ~ 0.42 초 |
| 원본 `/Game/JYU/Maps/LV_JYU_Ecosystem` 단독 (80 초) | 하늘 연출 켬 (권위), 같은 팀 하늘 BP·라이트 | 하늘 d 와 v3 세계 d 차 최대 0.02 (316 줄 — 기록이 소수 둘째 자리로 반올림하고, 실시간이라 v3 전역 스텝이 팀 시계와 조금 벌어진다. 다시 맞추는 문턱 0.53 초 = d 0.044 안) |

- 클라이언트 하늘은 요약(약 1 초마다)이 늦게 오는 만큼 0.1 초쯤 늦게 돈다 — 어스름(d 가 바뀌는 12 초)에서도 d 차 0.01 쯤이라 눈으로는 같다.
- 데디케이티드 서버 기록에는 하늘 줄이 없다 (서버에는 만들지 않는다).
- 화면을 찍지는 않았다 (클라이언트 `-NullRHI`). 클라이언트가 그리는 빛 값은 기록의 해 pitch·세기로 봤다 — 해 pitch 와 표시 시계 식의 차 최대 0.1° (기록 반올림).
