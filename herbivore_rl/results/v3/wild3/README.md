# 야생 3단계 — 지역 날씨 (숲 비 · 고지 눈 · 메마른 땅 맑음) + 무대 나무 (10-18)

10-18 사용자 '일단 우리 테스트 레벨에도 날씨 적용되게 해 줘. 그리고 그 날씨와 장애물들을 바탕으로 만들어진 세계를 파이썬에 고대로 옮겨서 학습시킬 거야.'
이 폴더는 그 가운데 날씨 몫이다. 1~2절은 **파이썬 쪽 첫 단계**(팀 날씨 설계를 세계 규칙으로 옮기고 지금 게임 두뇌 R1b-F 를 그 세계에서 잼, `555b8d5`),
3~5절은 **언리얼 쪽**(같은 규칙을 C++ 로 옮기고, 우리 시험 레벨 `/Game/Map/LV_Ecosystem_IntegrationTest` 에서 비·눈이 보이게 하고, 언리얼과 파이썬을 짝 비교함)이다.
명세 `AdaptiveEcosystem/Docs/RL_Policy/RL_V3_WILD2_SPEC.md` 11절, 결정 기록 `RL_V2_PLAN.md` 10-18 (15), 언리얼 스위치는 계획서 `RL_V3_UNREAL_TRAINING_PLAN.md` 4-5b '10-18 지역 날씨'.

## 한 줄 결론

- 팀 설계(숲 상자 = 비, 고지 상자 = 눈, 메마른 땅 = 맑음)를 지역마다 고정 날씨로 옮겼다. 비는 시야(× 0.9)와 사슴 청각(× 0.5)을, 눈은 시야(× 0.7)와 이동(사슴 × 0.6, 늑대 × 0.85)을 줄인다.
- **숲 비는 잡힘을 바꾸지 않는다**(240초 5.23 → 5.21%). 사슴이 늑대를 늦게 알아채지만(15~30 m 46 → 28%) 늑대도 덜 본다.
- **고지 눈은 잡힘을 늘린다**(240초 5.23 → 6.09%, 같은 세계 짝 +0.86 %p, z +5.1 · 16분 21.1 → 23.9%, z +3.6). 거의 다 '쫓는 늑대가 뛰는 사슴보다 빨라짐'에서 온다.
- 메마른 땅은 맑음이라 날씨 없는 세계와 비트 단위로 같다. 날씨를 끈 세계는 직전 코드와 비트 단위로 같다(시험).
- 지금 두뇌는 날씨에 맞춰 행동을 바꾸지 않는다(도망·숨기 몫이 오히려 준다 — 덜 알아채니 덜 도망친다). 학습이 배울 몫이 있다(눈 오는 고지에서 더 일찍 도망치기 등, 추정).
- **언리얼도 같은 규칙으로 돈다**(3·4절). 언리얼 통합 v3 기본값(나무 + 날씨) 세션 20000~20002 대 파이썬 같은 지도 반복 10: 산 94.5 대 94.5%, 잡힘 5.47 대 5.49%, 굶음 0,
  지역마다 모든 칸 |z| ≤ 2.3. 날씨가 바꾼 것(날씨 판 − 끈 판)도 같은 쪽이다 — 고지 잡힘 +0.78 대 +0.86 %p, 15~30 m 알아챔 숲 −21 대 −19 %p·고지 −33 대 −28 %p.
- **우리 시험 레벨에서 비·눈이 보인다**(5절). 레벨·애셋은 그대로 두고 팀 나이아가라·빗소리를 카메라 곁에 켠다 — 숲 비, 고지 눈, 메마른 땅 맑음. 경계를 넘으면 곧바로 바뀐다
  (비 1.5 초에 다 셈·1 초에 꺼짐, 눈은 나오자마자 멈춰 0.7 초 안에 사라짐 — 팀 블루프린트의 7~9 초 늦음·5.5 초 남음·음량 0 소리 없음). 다만 비는 팀 화면처럼 맑은 낮에 옅다
  (빗줄기 배수 `eco.IntegratedV3.WeatherRainDensity` 4 면 또렷하다).

## 1. 규칙 (`wild_weather`, 기능 번호 31)

정의·식·C++ 꼴은 `env_v2/world.py` 모듈 docstring '야생 3단계', 값과 출처는 명세 11-3. 날씨 (k, 세기 I) 의 배수 m(I) = 1 − (1 − m₁)·I.

| | 비 (세기 1) | 눈 (세기 1) | 현실 근거 (한 줄, 출처는 명세 11-8) |
|---|---|---|---|
| 사슴이 위협을 보는 반경 (40 m) | × 0.9 → 36 m | × 0.7 → 28 m | 큰비는 40 m 앞 대비를 약 6% 줄이고 빗줄기가 움직임을 가린다(어림) · 큰 눈은 시정 400 m 밑(Rasmussen 외 1999) → 40 m 앞 대비 0.74 |
| 늑대가 사슴을 보는 반경 (28 m) | × 0.9 → 25.2 m | × 0.7 → 19.6 m | 같은 비·눈이 늑대 눈도 가린다(사슴과 같게) |
| 사슴이 발소리를 듣는 반경 (달리는 늑대 40 m) | × 0.5 → 20 m | 그대로 | 배경 소음 +6 dB 면 들리는 거리가 반(구면 퍼짐, Barber 외 2010) · 갓 내린 눈은 소리를 먹고 언 눈은 뽀득거려 방향이 엇갈린다 |
| 이동 | 그대로 | 사슴 × 0.6, 늑대 × 0.85 (R3 지형 눈 값) | 사슴은 발 하중이 커서 눈에 더 빠진다(Telfer & Kelsall 1984), 눈이 깊을수록 늑대가 사슴을 더 잡는다(Nelson & Mech 1986) |
| 관측 `visibility` | (1 − 0.5·d) × 0.9 | (1 − 0.5·d) × 0.7 | 계약 #25 '실효 탐지 반경 ÷ 40 m' 그대로 — 칸 수 18 그대로, 사슴은 이 칸으로 날씨를 안다 |

- 늑대 청각은 이 세계에 없어서(늑대는 시야 반경 하나로 사슴을 찾는다) 청각 배수는 사슴에게만 건다. 늑대 시야 반경에는 사슴과 같은 시야 배수가 걸린다.
- 바꾸지 않는 것: 늑대 무리 돕기 거리, 도주 반사 실거리 문턱, 은신처, 먹이, 대사, 동족 시야, 낮밤 구간(어둠 d 로 정한다).
- 지역은 세계마다 하나(`wild_weather.region`). 짝 비교 실행기가 지도 (세션, 지역) 마다 그 지역의 먹이 지도·나무(숲 24·고지 9·메마른 땅 0 그루)·날씨를 넣는다.
- 시간에 따라 바뀌는 날씨는 자리만 있다(`schedule`, 기본 null — 지역마다 늘 같다).

## 2. 측정 (사슴 128, 늑대 4, 두뇌 R1b-F argmax)

세계: 언리얼 세션 20000~20002 의 지역 지도 9장 × 반복 10 = 90 세계(240초, 시드 32000~32089), 세션 20000~20009 지도 30장 × 1 = 30 세계(16분, 시드 32000~32029).
기준(나무 거울, 날씨 없음)과 날씨 판은 세계마다 같은 시드·먹이 지도·나무다. 전체 표는 `summary.md`(자동 생성), 수는 `summary.json`.

240초 (지역마다 30 세계):

| 지역 | 산 % | 잡힘 % | 굶음 % | 사냥 성공률 % | 도망 몫 % | 알아챔 % 15~30 m | 잡힘 짝 차이 %p (z) |
|---|---|---|---|---|---|---|---|
| 숲: 날씨 없음 → 비 | 94.7 → 94.8 | 5.23 → 5.21 | 0.03 → 0 | 56.7 → 58.4 | 9.29 → 9.06 | 46 → 28 | −0.03 ± 0.36 (−0.1) |
| 고지: 날씨 없음 → 눈 | 94.8 → 93.9 | 5.23 → 6.09 | 0 → 0 | 56.5 → 78.7 | 8.49 → 5.80 | 46 → 19 | **+0.86 ± 0.34 (+5.1)** |
| 메마른 땅: 맑음 (같음) | 94.8 | 5.21 | 0 | 62.8 | 8.48 | 47 | 0 |
| 모두 | 94.8 → 94.5 | 5.23 → 5.50 | 0.01 → 0 | 58.5 → 66.2 | 8.76 → 7.79 | 46 → 32 | +0.28 ± 0.19 (+3.0) |

16분 (게임 8일, 지역마다 10 세계):

| 지역 | 산 % | 잡힘 % | 굶음 % | 사냥 성공률 % | 잡힘 짝 차이 %p (z) |
|---|---|---|---|---|---|
| 숲: 날씨 없음 → 비 | 51.4 → 54.5 | 20.00 → 20.31 | 28.59 → 25.16 | 58.6 → 57.3 | +0.31 ± 1.73 (+0.4) |
| 고지: 날씨 없음 → 눈 | 63.2 → 58.8 | 21.09 → 23.91 | 15.70 → 17.34 | 57.1 → 71.7 | **+2.81 ± 1.57 (+3.6)** |
| 메마른 땅 (같음) | 57.3 | 21.09 | 21.64 | 59.6 | 0 |
| 모두 | 57.3 → 56.8 | 20.73 → 21.77 | 21.98 → 21.38 | 58.4 → 62.7 | +1.04 ± 0.88 (+2.4) |

나눠 보기 (240초 고지, 잡힘 짝 차이 %p):

| 판 | 잡힘 짝 차이 (z) | 사냥 · 성공률 | 읽기 |
|---|---|---|---|
| 눈 (기본) | +0.86 ± 0.34 (+5.1) | 310 · 78.7% | |
| 눈 이동 배수만 (시야 1) | +0.81 ± 0.37 (+4.4) | 309 · 79.2% | 늘어난 잡힘은 거의 이동 배수 몫 |
| 눈 시야 배수만 (이동 1) | +0.16 ± 0.38 (+0.8) | 510 · 42.9% | 사냥은 늘지만 놓친다 — 잡힘 그대로 |
| 눈 세기 0.5 (사슴 0.8 · 늑대 0.925 · 시야 0.85) | +0.60 ± 0.37 (+3.2) | 353 · 66.4% | 그 사이 |
| 날씨를 visibility 에 안 실음 | 고지 +0.70 ± 0.40 (+3.5), 숲 −0.08 | 320 · 75.2% | 지금 두뇌는 이 칸의 낮은 값에 거의 반응하지 않는다 |

- 알아챔(산 사슴 × 깨어 있는 늑대 쌍 가운데 사슴이 감지한 몫): 숲 <5 · 5~10 · 10~15 · 15~30 m = 87 · 76 · 65 · 46 → 79 · 73 · 59 · 28%, 고지 87 · 78 · 64 · 46 → 81 · 57 · 46 · 19%.
  들어서만 안 몫은 숲 3.1 → 0.7%(빗소리), 고지 2.6 → 1.1%.
- 굶음은 240초에 0 이다. 16분 숲 굶음 28.6 → 25.2% 는 10 세계라 흔들림 안이다.
- 사냥 성공률은 고지에서 목표 띠(10~30%)에서 더 멀어진다(보고만 — 늑대 규칙이 크게 정한다, R4 계획 D6).

### 끼임 (`../wild2/stuck_check.py` — 느려진 몸이 줄기에 끼지 않나)

- 짝 지도 90 세계 × 240초(지도 지역마다 나무·날씨, `stuck_check.py` 도 10-18 부터 지도 지역의 날씨를 넣는다): 사슴 0 번, 늑대 줄기 끼임 0 번. 은신처 둘레 기어감 16 번(숲 4 · 고지 4 · 메마른 땅 8)·가장 김 5.2 초 — 날씨 없는 나무 판 21 번(7 · 6 · 8)·5.2 초(`../wild2/trees/README.md`). 기록 `runs/stuck_wild3_pair.json`.
- 고지 눈 배수 + 숲 원판 24 그루(더 빽빽한 줄기에 눈), 30 세계 × 16분:
  사슴 끼임 0 번, 늑대 줄기 끼임 0 번, 돌아가기가 빈 방향을 못 찾음 0 번.
  은신처 둘레에서 3 초 넘게 기어간 늑대 38 번(돕는 늑대 13)·가장 김 5.7 초 — 날씨 없는 숲 배치는 23 번·5.2 초(`../wild2/trees/README.md`). 느려진 늑대는
  3 초 동안 1 m 문턱을 덜 넘어서 더 세어진다. 막힌 것이 아니다. 기록 `runs/stuck_snow_long.json`(커밋하지 않음).

## 3. 언리얼 규칙 (C++, 파이썬과 비트 단위로 같음)

- 세계 층(엔진 무관): `AI/Policy/EcoWorldV3.h` `FWeatherConfig`(기본 끔, 계수 = 거울 설정)·`WeatherAt`(시간표 자리 — 파이썬 `weather_at`)·`WeatherMults`(m(I) = 1 − (1 − m₁)·I)·
  `UpdateDayNight`(어둠과 같은 때 날씨·배수)·`SeePredNow`(사슴 탐지 반경 SeeR × ((1 − 0.5·d) × 시야))·`ObsVisibilityMult`·`WolfViewNow`, 발소리 × 사슴 청각(`BuildThreatInputs`),
  사슴 속도 × 사슴 이동(B, 약함 뒤), 위협 Step 의 `WeatherViewMult`·`WeatherSpeedMult`(`EcoThreatModel.h`, 밤잠 배수 뒤·돌아가기 앞, 무리 미리 보기도 같은 입력),
  `EcoObservationV3.h` visibility × 시야. 맑음·세기 0·배수 1 은 곱해도 같은 값이라 날씨를 끈 세계와 비트 단위로 같다.
- 통합 모드: `eco.IntegratedV3.Weather`(기본 1, 지역 표 `kRegionWeatherDefaults` = 숲 비 1·고지 눈 1·메마른 땅 맑음, 덮기 `eco.IntegratedV3.Weather<지역>` = `날씨[:세기]`).
  10초 여덟째 줄 `[EcoV3I] <지역> 날씨 |`(지금 날씨·배수·늑대 시야, 날씨 스텝, 감지 누적 = 산 사슴 × 깨어 있는 늑대 쌍의 거리 띠별 감지, 들어서만 안 사슴·스텝 — 기록만).
- 골든 `AI/Policy/WeatherGoldenVectorsV3.h`(`herbivore_rl/export_golden_v3_weather.py`, 시드 32098·32099): 설정·배수 43·시간표 45·낮밤 114(`_daynight_update` 의 어둠·탐지 반경·
  visibility·늑대 시야·배수)·지각 18 장면(발소리 × 청각 → 알아챔 1152 쌍, 날씨가 바꾼 쌍 14)·한 스텝 80 장면(무리 미리 보기 → 목표 → Step, 날씨가 바꾼 늑대 144) 모두 비트 단위로 같다.
  같은 검사 본문(`Tests/WeatherGoldenCheckV3.h`)을 UE 시험 `Policy.V3.Weather.Golden` 과 g++ 하네스(`tests/cpp/weather_v3_main.cpp`, `tests/test_wild3_weather.py`)가 부른다.
  끄면 그대로(기준 루프 240 스텝: 맑음·배수 1 인 비·세기 0 눈 = 날씨 끔)와 첫 스텝 눈 이동(사슴 × 0.6·늑대 × 0.85)도 본다.
- 실제 판에서도: 언리얼 메마른 땅(맑음) 기록 줄(10초 첫 줄·경계 거리·야생·사냥·은신처·늑대 무리)이 날씨를 넣기 전 나무 판(`../wild2/trees/unreal_logs`)과 세 세션 모두 같다.

## 4. 언리얼 대 파이썬 (헤드리스, 사슴 128, 240초)

언리얼 통합 v3 기본값(나무 + 날씨) 세션 20000~20002(`unreal_logs/`, 내보내기 `unreal_exports/` — 지역 날씨·배수 = 거울 설정, 원판 = 나무 배치 표 확인) 대 파이썬
`configs/v3_wild3_mirror.yaml` 같은 먹이 지도·나무·날씨 반복 10(`runs/wild3_240`, 시드 32000~32089). 230초 줄, 감지 띠·들어서만은 비율(언리얼 230초·파이썬 240초까지).
칸마다 언리얼 한 판 · 파이썬 평균 (z), z = (언리얼 − 평균) ÷ 파이썬 반복 표준편차. 전체 표 `compare_weather.md`(+ 날씨를 끈 판끼리 `compare_weather_off.md`).

| 지역 | 산 % | 잡힘 % | 굶음 % | 사냥 성공률 % | 알아챔 15~30 m % | 들어서만 % |
|---|---|---|---|---|---|---|
| 숲 (비) | 94.8 · 94.8 (−0.1) | 5.21 · 5.18 (+0.1) | 0 · 0 | 55.6 · 59.9 (−0.5) | 28.7 · 27.7 (+0.4) | 1.02 · 0.70 (+1.7) |
| 고지 (눈) | 93.8 · 93.9 (−1.2) | 6.25 · 6.09 (+1.2) | 0 · 0 | 72.7 · 81.5 (−1.0) | 17.1 · 18.7 (−0.6) | 1.36 · 1.17 (+1.5) |
| 메마른 땅 (맑음) | 95.1 · 94.8 (+0.7) | 4.95 · 5.18 (−0.7) | 0 · 0 | 48.7 · 63.6 (−2.0) | 47.2 · 46.8 (+0.1) | 3.19 · 3.24 (−0.1) |
| 모두 | 94.5 · 94.5 (+0.1) | 5.47 · 5.49 (−0.1) | 0 · 0 | 58.3 · 67.3 (−1.8) | 33.0 · 32.0 (+0.4) | 1.86 · 1.70 (+0.7) |

- 가까운 띠: 숲 <5·5~10·10~15 m 알아챔 88.7·83.7·66.7 대 80.4·73.8·59.2%(z +1.3·+1.7·+2.2), 고지 77.0·54.2·39.8 대 82.3·57.1·45.9%(−1.2·−0.8·−1.2).
  가까운 띠는 쌍이 적어(지역마다 600~13000) 한 판 흔들림이 크다 — 날씨를 끈 판끼리도 숲 은신처 안 −2.4·고지 <5 m −1.5 가 나온다(`compare_weather_off.md`).
- 메마른 땅 사냥 시작 41 대 32.8(+2.3)·성공률(−2.0)은 날씨와 무관한 옛 차이다(명세 6-6, `../wild2/trees/README.md` 7-3 — 이 무대는 비트 단위로 날씨 전과 같다).
- **날씨가 바꾼 것**(같은 세션·지도의 날씨 판 − `-EcoV3Weather=0` 판, `unreal_logs_weather_off/` · 파이썬 나무 거울 짝 `runs/trees_240`):

| 지역 | 잡힘 %p 언리얼 · 파이썬 (± 2SE) | 사냥 성공률 %p | 알아챔 15~30 m %p | 들어서만 %p |
|---|---|---|---|---|
| 숲 (비) | −0.52 · −0.05 ± 0.28 | −6.6 · +2.0 ± 7.6 | −21.2 · −18.5 ± 2.1 | −1.65 · −2.51 ± 0.41 |
| 고지 (눈) | +0.78 · +0.86 ± 0.21 | +11.6 · +24.3 ± 5.3 | −33.0 · −27.9 ± 2.8 | −1.86 · −1.49 ± 0.38 |
| 메마른 땅 | 0 · 0 | 0 · 0 | 0 · 0 | 0 · 0 |

  방향은 모두 같다(고지 잡힘이 늘고, 비·눈 모두 멀리서 덜 알아채고, 빗소리로 들어서만 안 몫이 준다). 언리얼 차이는 한 판끼리라 파이썬 짝(같은 시드라 흔들림이 작다)보다 넓게 흔들린다.
- 기록 오류·ensure·EcoV3I 경고 0(여섯 판).

## 5. 우리 시험 레벨에서 비·눈 보이기 (`shots/`)

- 연출 `AI/Policy/EcoV3WeatherPresenter.*`(`eco.IntegratedV3.WeatherVisuals` 기본 1). 프레임마다(카메라 갱신 뒤) 첫 플레이어의 카메라 자리를 가로로 품는 지역(`AEcologyRegion` 상자 —
  이 레벨은 Barren 중심 (0, 0)·Forest (0, 500)·Highland (0, −500) m, 반폭 750 × 250 m)의 **세계 날씨**(규칙이 쓰는 그 값)를 읽어, 비면 팀 `Rain_System`(빗줄기 `User.SpawnRate`
  = 500 × 세기 × 페이드 — 팀 블루프린트가 세기 1 에 넣는 값을 실행 중에 읽어 같게 둠)·`A_Rain_Cue`(음량 = 세기 × 페이드), 눈이면 `NS_Blizzard` 를 카메라 자리에 켠다.
  레벨·애셋·팀 블루프린트는 그대로다(이 레벨에는 날씨 액터가 없다). 그리지 않는 실행(-NullRHI)·전용 서버·클라이언트에서는 아무것도 만들지 않는다 — 헤드리스 판은 그대로다.
- 사진(1280×720, GPU 1920×1080 `-benchmark -fps=30`, 세션 20000, 낮):

| 사진 | 무엇 |
|---|---|
| `forest_rain_wide.png` | 숲 무대를 비스듬히 위에서 (빗줄기 배수 1 — 팀 화면과 같다). 가는 빗줄기 몇 줄과 옅은 물안개 |
| `forest_rain_ground.png` · `forest_rain_motion.png` | 숲 땅 높이 정지 카메라. 맑은 낮이라 빗줄기가 옅다 — 이웃 프레임 차이(`motion`)에서 세로 빗줄기가 가득 보인다 |
| `forest_rain_ground_density4.png` | 같은 자리, `eco.IntegratedV3.WeatherRainDensity 4` (발표용) — 빗줄기가 또렷하다 |
| `highland_snow_wide.png` · `highland_snow_deer.png` · `highland_snow_ground.png` | 고지: 위에서·사슴 곁·땅 높이 모두 눈송이 |
| `barren_clear_wide.png` | 메마른 땅: 비·눈 없음 |
| `crossing_rain.png` | 메마른 땅 → 숲 (10 m/s): 경계에서 0.33 초 뒤 비 0.22, 1.33 초 뒤 다 셈 · 숲 → 메마른 땅: 1 초에 꺼짐 |
| `crossing_snow.png` | 고지 → 메마른 땅: 나오는 순간 새 눈송이 멈춤, 0.33 초 뒤 몇 송이, 0.67 초 뒤 없음 (팀 블루프린트는 5.5 초 동안 그대로 내림) |
| `weather_fx_timeline.png` | 카메라 지역 날씨와 연출 상태(캡처마다 `film_runs/wxB/watch.txt`) |

- 촬영 감독 기록 `shots/film_runs/<판>/watch.txt`(캡처마다 연출 액터 `EcoV3WeatherFx` 의 켜짐·자리·빗줄기 수·페이드 — 읽기만), 장면마다 수 `shots/summary.json`.
- 소리: `-benchmark`·`-NoSound` 판이라 들어 보지 못했다. 코드는 비가 0 이 되면 빗소리를 멈춘다(`bRainSoundOn` 끔 — 팀 블루프린트처럼 음량 0 으로 남지 않는다).
- 남은 것: 비는 맑은 낮 하늘에서 옅다(팀 애셋 그대로 — 하늘·빛은 바꾸지 않는다). 연출은 첫 로컬 플레이어 카메라 하나만 본다(분할 화면·클라이언트 없음).

## 6. 다음

1. R4 학습 세계 설정(`configs/v3_r4.yaml` — 이 거울 + 세계마다 지역 하나 + 학습용 부활(늑대에게서 40 m 밖)). 관측 18칸 그대로, R1b-F 에서 이어 배운다(결정 10-18 (15)).
2. (팀) 하늘·빛을 날씨에 맞추면 비가 더 비처럼 보인다. 팀 블루프린트의 카메라 자리·늦음·소리 문제는 `../wild2/weather_check/README.md` 4절.

## 다시 만들기

```
# herbivore_rl/ 에서
python results/v3/wild3/make_wild3_config.py --check      # 설정이 나무 거울 + 날씨 블록으로 최신인지
sh results/v3/wild3/run_all.sh                            # 판 열 개 + 끼임 세기 → runs/ (약 20분, 20 코어)
python results/v3/wild3/summarize_weather.py              # → summary.md · summary.json
python -m pytest tests/test_wild3_weather.py -q           # 시험 13개 (골든 헤더 최신 · g++ 골든 포함)
python export_golden_v3_weather.py                        # 날씨 골든 헤더 → AI/Policy/WeatherGoldenVectorsV3.h
# 언리얼 헤드리스 (세션 s = 20000, 20001, 20002; 날씨를 끈 판은 + -EcoV3Weather=0, 내보내기 빼고 → unreal_logs_weather_off)
UnrealEditor-Cmd.exe <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=<s>
    -EcoV3ObstacleExport=<이 폴더>/unreal_exports/s<s>.json -benchmark -fps=60 -seconds=240 -NullRHI -NoSound -unattended -nosplash -nopause
    -DisablePlugins=Bridge,Fab -abslog=<전체 기록 d128_s<s>_k0.full.log>
python results/v3/wild1/trim_unreal_log.py results/v3/wild3/unreal_logs <전체 기록>...
# 파이썬 짝 (진단 heard_live 가 든 판 — run_all.sh 의 trees_240·wild3_240 과 같은 명령) · 견줌
python results/v3/wild3/compare_weather.py                # → compare_weather.md · .json (날씨가 바꾼 것 표 포함)
python results/v3/wild3/compare_weather.py --baseline --unreal-dir results/v3/wild3/unreal_logs_weather_off --python results/v3/wild3/runs/trees_240.json --out results/v3/wild3/compare_weather_off.md
# GPU 사진 (UnrealEditor.exe, 공통: <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3Seed=20000 -EcoV3FilmOut=<폴더> -EcoV3FilmWatch=EcoV3WeatherFx
#   -benchmark -fps=30 -windowed -ResX=1920 -ResY=1080 -NoSound -nosplash -DisablePlugins=Bridge,Fab)
#   wxA: -EcoV3Film=wxA "-EcoV3FilmShots=Forest,wide,0,6,3;Forest,shelter,0,10,3;Highland,wide,0,14,3;Highland,deer,0,18,3,10,3,225,0;Barren,wide,0,22,3;Barren,deer,0,26,3,10,3,225,0" -EcoV3FilmEvery=15 -seconds=31
#   wxB: -EcoV3Film=wxB -EcoV3FilmStandalone "-EcoV3FilmShots=forest_ground,330,470,1.8,0,0,3,4;forest_low,342,440,6,90,-10,8,3;cross_in,340,200,1.8,90,0,12,10,340,300,1.8;cross_out,340,300,1.8,-90,0,23,10,340,200,1.8;highland_ground,340,-490,1.8,90,0,34,3;snow_out,340,-300,1.8,90,0,38,10,340,-200,1.8;barren_ground,340,10,1.8,90,0,49,2" -EcoV3FilmEvery=10 -seconds=53
#   wxC: -EcoV3Film=wxC -EcoV3FilmStandalone -EcoV3WeatherRainDensity=4 "-EcoV3FilmShots=forest_ground,330,470,1.8,0,0,3,3;forest_low,342,440,6,90,-10,7,3" -EcoV3FilmEvery=10 -seconds=11
python results/v3/wild3/make_weather_shots.py --frames <폴더>   # → shots/
```

## 파일

- `README.md` — 이 글. `summary.md`·`summary.json` — 표와 수(`summarize_weather.py` 가 만듦).
- `make_wild3_config.py` — `configs/v3_wild3_mirror.yaml` 생성기(나무 거울 + `wild_weather` 블록). `run_all.sh` — 측정 묶음. `summarize_weather.py` — 표(메마른 땅이 기준과 같은지도 본다).
- `runs/` — 실행 결과(커밋하지 않음): `trees_240`, `wild3_240`, `wild3_novis_240`, `wild3_snow05_240`, `wild3_snowspeed_240`, `wild3_snowsight_240`, `trees_16m`, `wild3_16m`, `stuck_wild3_pair`, `stuck_snow_long`.
  `trees_240`·`wild3_240` 은 10-18 언리얼 비교 때 진단 `heard_live`·`live_obs` 를 더해 다시 돌렸다(다른 칸은 그대로 — 90 세계 모두 10초 줄·죽음·사냥·진단이 같음).
- `unreal_logs/` — 언리얼 기본값(나무 + 날씨) 세션 20000~20002 기록(`../wild1/trim_unreal_log.py` 로 고름), `unreal_logs_weather_off/` — 같은 세션 `-EcoV3Weather=0`.
  `unreal_exports/` — 원판·은신처·지역 날씨 JSON(`-EcoV3ObstacleExport=`).
- `compare_weather.py` — 언리얼 대 파이썬 짝 비교(+ 날씨가 바꾼 것)와 내보내기 확인 → `compare_weather.md`·`.json`, 날씨를 끈 판끼리 `compare_weather_off.md`·`.json`.
- `make_weather_shots.py` — GPU 촬영 출력에서 `shots/` 사진·띠·시간표를 만든다. `shots/` — 5절.
