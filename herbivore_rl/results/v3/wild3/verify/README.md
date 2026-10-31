# 지역 날씨 독립 확인 — 새 언리얼 판으로 다시 견줌 (10-18)

10-18 사용자 '일단 우리 테스트 레벨에도 날씨 적용되게 해 줘. 그리고 그 날씨와 장애물들을 바탕으로 만들어진 세계를 파이썬에 고대로 옮겨서 학습시킬 거야'의
날씨 단계(`555b8d5` 파이썬 규칙, `1e53f7f` C++·연출, `8dd2f87` 첫 비교)를 앞 판과 겹치지 않는 판으로 다시 확인했다. 코드·설정·레벨·콘텐츠는 바꾸지 않았다(빌드 없음 —
`1e53f7f` 빌드 그대로, 그 빌드의 자동 시험 171 = 성공 170 + 기존 경고 1 은 빌드 직후 같은 바이너리로 돌았다).

## 한 줄 결론

- **파이썬과 언리얼은 같은 날씨 세계다.** 지역마다 배수(시야·청각·이동·visibility)가 두 쪽 모두 같은 수이고, 새 세션 20004 와 더해 돌린 20003·20005~20008 을 합친
  지도 27장에서 언리얼 대 파이썬의 모든 칸이 |z| ≤ 1.8 이다. 메마른 땅(맑음)은 날씨를 켜도 끈 판과 기록이 똑같다.
- **화면도 맞다.** 숲은 비(빗소리 실제 재생), 고지는 눈, 메마른 땅은 숲 경계 10 m 앞에서도 비·소리 없음. 숲에서 나오면 1 초에 비와 빗소리가 함께 꺼지고, 고지에서 나오면
  다음 캡처(0.33 초)에 눈이 꺼진다.
- **옛 문제는 다시 생기지 않았다.** 언리얼 아홉 판(날씨 여섯·끔 셋): 은신처 안 잡힘 0, 굶음 0, 도망 중 죽음 0, 줄기·벽 막힘 0, 돌아가기 못 찾음 0, 오류·경고 0.
  파이썬 180 세계: 은신처 안 잡힘 0, 사슴 끼임 0, 늑대 줄기 끼임 0. 다만 파이썬 한 세계(메마른 땅 — 날씨 없는 곳)에서 사슴 1 마리가 도망치다 굶었다(4절, 날씨와 무관).
- 고친 코드는 없다. 문서 한 곳(R4 계획 5절의 옛 후보 값)에 지금 값을 가리키는 줄을 더했다.

## 1. 무엇을 돌렸나

| 쪽 | 판 | 시드 | 기록 |
|---|---|---|---|
| 언리얼 헤드리스 (사슴 128, 240초, 기본값 = 나무 + 날씨) | 세션 20004 (맡은 판) + 20003·20005·20006·20007·20008 (흔들림을 보려고 더함) | 20003~20008 | `unreal_logs/`, 내보내기 `unreal_exports/` |
| 언리얼 날씨 끈 판 (`-EcoV3Weather=0`) | 세션 20003·20004·20005 | 같음 | `unreal_logs_weather_off/` |
| 파이썬 `configs/v3_wild3_mirror.yaml` 같은 먹이 지도·나무·지역 날씨 | 지도마다 반복 10 | 33000~33089 (앞 비교의 32000~32089 와 겹치지 않음) | `runs/wild3_240_s*.json` (커밋하지 않음) |
| 파이썬 나무 거울(날씨 없음) 짝 | 같은 지도·같은 시드 | 같음 | `runs/trees_240_s*.json` |
| 파이썬 끼임 세기 (`../../wild2/stuck_check.py`) | 지도 20003~20005 × 반복 10 = 90 세계 | 33000~33089 | `runs/stuck_wild3_s20003-20005.*` |
| 언리얼 GPU 촬영 `wxV` (세션 20004, 소리 장치 켬 — `-UseFixedTimeStep -fps=30`, `-benchmark` 는 소리를 아예 끈다) | 정지 넷 + 나가기 둘 | 20004 | `film_wxV/`(촬영 감독 기록), `stills.jpg`, `exits.md` |

- 파이썬 시드 33000~33089 는 R4 계획 D8 의 판정 범위다. 여기서는 지금 두뇌 R1b-F 를 거울 세계에서 재는 데만 썼다(학습·고르기·R4 결정에는 쓰지 않음). 거울 설정 머리
  주석의 허용 범위(32000~32099·33000~33099) 안이다.

## 2. 배수가 같은가 (숫자)

언리얼 시작 줄 `[EcoV3I] <지역> 날씨 | …`(여섯 판 모두 같음)·내보내기 JSON 의 지역 날씨 계수와 파이썬 `weather_mults`(거울 설정 값)를 견줬다. 모두 같다.

| 지역 | 날씨 | 사슴 위협 탐지 (낮) | 늑대 시야 | 사슴 청각 | 사슴 이동 | 늑대 이동 | 관측 visibility |
|---|---|---|---|---|---|---|---|
| 숲 | 비 1 | 40 → 36 m | 28 → 25.2 m | × 0.5 | × 1 | × 1 | × 0.9 |
| 고지 | 눈 1 | 40 → 28 m | 28 → 19.6 m | × 1 | × 0.6 | × 0.85 | × 0.7 |
| 메마른 땅 | 맑음 | 40 m | 28 m | × 1 | × 1 | × 1 | × 1 |

- 230초 줄의 날씨 스텝: 지역마다 1725 스텝 모두 그 날씨(숲 비 1725·고지 눈 1725·메마른 땅 맑음 1725).
- 골든(`tests/test_wild3_weather.py` 13개, g++ 골든 대조 포함)을 다시 돌려 모두 통과했다.
- 남은 틈: 날씨 골든 장면은 세로 장애물을 끈 세계다(날씨와 나무를 함께 둔 장면은 골든에 없다). 두 규칙은 서로 곱하기만 하고(가림은 반경과 따로 판정), 함께 둔 실제 판은 아래
  3절로만 확인했다.

## 3. 언리얼 대 파이썬

칸마다 언리얼 · 파이썬 평균 (z), z = (언리얼 − 파이썬 평균) ÷ 파이썬 반복 표준편차. 전체 표 `compare_weather_s20004.md`(맡은 판)·`compare_weather_pooled_s20000-20008.md`(지도 27장).

세션 20004 하나 (지도 3장):

| 지역 | 산 % | 잡힘 % | 굶음 % | 사냥 성공률 % | 15~30 m 늑대 알아챔 % | 들어서만 알아챔 % |
|---|---|---|---|---|---|---|
| 숲 (비) | 96.1 · 94.0 | 3.91 · 6.02 | 0 · 0 | 60.0 · 63.6 (−0.4) | 19.7 · 28.9 (−1.8) | 0.46 · 0.53 (−0.4) |
| 고지 (눈) | 93.8 · 93.8 (−0.3) | 6.25 · 6.17 (+0.3) | 0 · 0 | 80.0 · 73.4 (+0.6) | 31.5 · 20.9 (+2.9) | 1.52 · 1.49 (+0.1) |
| 메마른 땅 | 94.5 · 94.3 (+0.2) | 5.47 · 5.62 (−0.2) | 0 · 0.08 | 58.3 · 68.8 (−0.8) | 40.4 · 48.0 (−0.7) | 3.38 · 2.01 (+1.6) |
| 모두 | 94.8 · 94.0 (+2.0) | 5.21 · 5.94 (−2.0) | 0 · 0.03 | 65.6 · 67.7 (−0.3) | 30.8 · 31.6 (−0.2) | 1.78 · 1.34 (+1.9) |

- 숲 20004 는 언리얼이 5 마리, 파이썬 10 번이 7~8 마리 잡혔다. 지도 하나에서는 늑대가 240초에 잡을 수 있는 수가 거의 차서(배부름 60초) 파이썬 흔들림이 작게 나와 z 가
  부풀어 보인다(산·잡힘 z ±5.6). 파이썬 숲 지도 40 번 가운데 5 마리 이하는 2 번이다. 그래서 다섯 세션을 더 돌려 합쳐 봤다.

세션 20000~20008 지도 27장 (앞 비교 20000~20002 + 이번 여섯):

| 지역 | 산 % | 잡힘 % | 굶음 % | 사냥 성공률 % | 15~30 m 늑대 알아챔 % | 들어서만 알아챔 % |
|---|---|---|---|---|---|---|
| 숲 (비) | 95.0 · 94.7 (+1.1) | 5.03 · 5.33 (−1.1) | 0 · 0 | 56.6 · 59.2 (−0.7) | 25.2 · 27.5 (−1.5) | 0.84 · 0.69 (+1.8) |
| 고지 (눈) | 93.8 · 94.0 (−1.7) | 6.25 · 6.03 (+1.7) | 0 · 0 | 80.9 · 77.5 (+0.7) | 18.7 · 19.7 (−0.7) | 1.35 · 1.46 (−1.2) |
| 메마른 땅 | 94.7 · 94.8 (−0.5) | 5.30 · 5.16 (+0.5) | 0 · 0.01 | 59.0 · 62.7 (−0.6) | 47.5 · 45.7 (+0.6) | 2.80 · 2.94 (−0.4) |
| 모두 | 94.5 · 94.5 (−0.1) | 5.53 · 5.51 (+0.1) | 0 · 0.00 | 64.7 · 65.9 (−0.4) | 31.5 · 31.1 (+0.3) | 1.66 · 1.69 (−0.3) |

- 모든 칸(지역 넷 × 칸 열하나) |z| ≤ 1.8. 내보내기 확인(지역 날씨·계수 = 거울 설정, 원판 = 나무 배치 표, 지도마다 날씨 = 파이썬)도 모두 같다.

## 4. 날씨가 바꾼 것 (날씨 판 − 끈 판)

잡힘 수, 세션 9개(지역마다 지도 9장 × 128 마리) — `effect_catches.md`:

| 지역 | 언리얼 날씨 · 끔 → 차이 | 파이썬 날씨 · 끔 → 짝 차이 ± 표준편차 | z |
|---|---|---|---|
| 숲 (비) | 58 · 64 → −6 | 61.4 · 60.9 → +0.5 ± 3.6 | −1.8 |
| 고지 (눈) | 72 · 66 → +6 | 69.5 · 60.2 → +9.3 ± 3.2 | −1.0 |
| 메마른 땅 (맑음) | 61 · 61 → 0 | 59.5 · 59.5 → 0 | 둘 다 0 |

- 방향은 같다(고지 잡힘이 늘고 메마른 땅은 그대로). 숲은 언리얼 쪽이 조금 더 줄었지만 흔들림 안이다(세션 6개까지는 z −2.8 이었다가 9개에서 −1.8 — 더 모을수록 가까워졌다).
- 감지 칸(세션 20000~20005, `compare_weather_effect_s20000-20005.md`): 15~30 m 알아챔 숲 −21.6 대 −17.2 %p·고지 −27.3 대 −26.3 %p, 들어서만 숲 −1.68 대 −2.07 %p — 같은 쪽.

## 5. 화면 (`stills.jpg`, `exits.md`)

- 정지 넷(1920×1080 GPU, 땅 높이 1.8 m): 숲 — 비 켬·빗소리 재생(맑은 낮이라 빗줄기는 옅다, 앞 판과 같음), 메마른 땅 숲 경계 10 m 앞에서 숲 쪽을 봄 — 비·소리 없음,
  고지 — 눈송이, 메마른 땅 가운데 — 맑음.
- 숲 → 메마른 땅(10 m/s, 경계 y = 250 m): 카메라가 경계를 넘은 17.0 초 뒤 비 세기 0.67(17.33 초)·0.33(17.67 초)·0(18.00 초). 18.00 초에 비 나이아가라 꺼짐, 빗소리
  `A_Rain_Cue` 재생 1 → 0, 월드에서 재생 중인 빗소리 없음. 들어갈 때는 1.5 초에 다 셈(11.0 초에 들어가 12.67 초에 1.00).
- 고지 → 메마른 땅(경계 y = −250 m): 31.0 초에 넘고 다음 캡처 31.33 초에 눈 꺼짐.
- 소리 장치가 있는 판(캡처 84 번 모두 `audio_device=1`)에서 빗소리 컴포넌트가 실제로 재생되고 멈추는 것을 봤다(앞 판들은 `-benchmark` 라 소리 장치가 없었다).
  사람 귀로 듣지는 않았다.
- 촬영 기록의 늑대·사슴 발소리 줄(팀 표현 액터)은 `film_wxV/watch.txt` 에서 뺐다(날씨와 무관, 크기).

## 6. 옛 문제 다시 보기

- 언리얼 날씨 판 여섯·끈 판 셋의 230초 줄: 은신처 안 잡힘 0, 굶음 0, 도망 중 죽음 0, 지형 막힘 사슴·늑대 0, 원판 밖으로 못 옮김 0, 돌아가기 못 찾음 0, 마스크 위반 0,
  EcoV3I 경고·오류 0, 기록의 다른 Error/Ensure 0.
- 파이썬 날씨 세계 180 (지도 18장 × 10): 은신처 안 잡힘 0. 끼임 세기 90 세계 × 240초: 사슴 끼임 0, 늑대 줄기 끼임 0, 돌아가기 못 찾음 0, 은신처 둘레 3 초 넘게 기어감
  19 번(돕는 늑대 9)·가장 김 6.0 초(앞 판 16 번·5.2 초, 날씨 없는 판 21~22 번·5.2~6.0 초 — 같은 무리).
- **도망 중 굶음 1 (파이썬)**: 지도 20004 메마른 땅 반복 6(시드 33006)의 사슴 112 가 214 초에 굶었다. 메마른 땅은 맑음이라 날씨 없는 나무 거울 같은 시드에서도 똑같이 생긴다
  (날씨와 무관). 먹이 없는 자리에서 시작해 30 초에 배가 비고, 무대 위쪽 벽 곁에서 깨어 있는(사냥하지 않는) 늑대 한두 마리가 40 m 안에 머물러 도주가 이어져(10-16 '깨어 있는
  늑대가 안전 거리 안이면 도주를 잇는다') 약 70 초 동안 비축을 빨리 썼다(도주 중 비축이 도주 없을 때의 약 2.6 배 빠르게 줄었다). 언리얼 판에서는 0 이다. 고치지 않았다(규칙 판단 — R4 학습 세계에서 더 자주 볼 수 있다, 다음에 볼 일).

## 7. 문제와 처리

| 문제 | 처리 |
|---|---|
| 코드 버그 | 찾지 못함 — 고친 코드 없음 |
| R4 계획 5절 표가 옛 후보 값(비 시야 × (1 − 0.3 × 강수), 늑대 청각도 줄임)을 그대로 보여 줌 (머리 줄에 '바뀌었다'만 있음) | 5절 머리에 지금 값(명세 11절)을 가리키는 줄을 더함 |
| 날씨 골든이 장애물을 끈 장면만 봄 | 남김 — 실제 판 비교(3절)로만 확인. 함께 둔 골든은 다음에 더할 수 있다 |
| 파이썬 한 세계의 도망 중 굶음 1 (날씨와 무관) | 남김 — 6절 |
| 숲 비 잡힘 효과가 언리얼에서 조금 더 큼 (z −1.8) | 흔들림 안 — 세션을 더 모으면 좁혀 볼 수 있다 |
| 촬영 판 명령에 `-ini:Engine:[ConsoleVariables]:au.MuteAudio=1` 을 넣으면 엔진이 거부(ECVF_Cheat — 처리된 ensure 한 번)하고 소리가 스피커로 난다 | 이 판은 그대로 둠(촬영 몇 초 빗소리가 났을 수 있다). 다음엔 `-ExecCmds="au.MuteAudio 1"` 을 쓴다 |

## 다시 만들기

```
# herbivore_rl/ 에서. 언리얼 헤드리스 (s = 20003 … 20008; 끈 판은 + -EcoV3Weather=0, 내보내기 빼고 → unreal_logs_weather_off)
UnrealEditor-Cmd.exe <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=<s>
    -EcoV3ObstacleExport=<이 폴더>/unreal_exports/s<s>.json -benchmark -fps=60 -seconds=240 -NullRHI -NoSound -unattended -nosplash -nopause
    -DisablePlugins=Bridge,Fab -abslog=<전체 기록>
python results/v3/wild1/trim_unreal_log.py results/v3/wild3/verify/unreal_logs <전체 기록>...
# 파이썬 짝 (C = configs/v3_wild3_mirror.yaml 은 wild3_240_*, configs/v3_wild2_trees_mirror.yaml 은 trees_240_*)
R="python results/v3/mirror/run_mirror.py --diag --out-dir results/v3/wild3/verify/runs --deer 128 --unreal-obstacles results/v3/wild2/trees/tree_layout.json --replicates 10"
$R --unreal-maps 20004 --seeds 33000-33029 --config <C> --name <wild3|trees>_240_s20004
$R --unreal-maps 20003,20005 --seeds 33030-33089 --config <C> --name <wild3|trees>_240_s20003_20005
$R --unreal-maps 20006-20008 --seeds 33000-33089 --config <C> --name <wild3|trees>_240_s20006_20008
python results/v3/wild2/stuck_check.py --config configs/v3_wild3_mirror.yaml --seeds 33000-33089 --steps 1800 --unreal-maps 20003-20005 --replicates 10
    --unreal-obstacles results/v3/wild2/trees/tree_layout.json --out results/v3/wild3/verify/runs/stuck_wild3_s20003-20005.json
# 견줌: 20004 하나
V=results/v3/wild3/verify
python results/v3/wild3/compare_weather.py --unreal-dir $V/unreal_logs --python $V/runs/wild3_240_s20004.json --exports $V/unreal_exports
    --out $V/compare_weather_s20004.md --base-unreal-dir $V/unreal_logs_weather_off --base-python $V/runs/trees_240_s20004.json
#   (unreal_logs 에 다른 세션도 있지만 파이썬 판에 있는 지도만 견준다)
# 견줌: 지도 27장 = ../unreal_logs 와 unreal_logs 의 기록, ../unreal_exports 와 unreal_exports 를 한 폴더씩에 모아서
python results/v3/wild3/compare_weather.py --unreal-dir <모은 기록> --python results/v3/wild3/runs/wild3_240.json $V/runs/wild3_240_s*.json --exports <모은 내보내기>
    --out $V/compare_weather_pooled_s20000-20008.md --base-unreal-dir <없는 폴더>
# 날씨가 바꾼 것: 세션 20000~20005 (날씨 판 · 끈 판을 각각 한 폴더에 모아서), 잡힘 수 세션 9개
python results/v3/wild3/compare_weather.py --unreal-dir <날씨 판 20000~20005> --python results/v3/wild3/runs/wild3_240.json $V/runs/wild3_240_s20004.json
    $V/runs/wild3_240_s20003_20005.json --exports <모은 내보내기> --base-unreal-dir <끈 판 20000~20005>
    --base-python results/v3/wild3/runs/trees_240.json $V/runs/trees_240_s20004.json $V/runs/trees_240_s20003_20005.json --out $V/compare_weather_effect_s20000-20005.md
python results/v3/wild3/verify/effect_catches.py
# GPU 촬영 (UnrealEditor.exe, 소리 장치 켬)
UnrealEditor.exe <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3Seed=20004 -EcoV3Film=wxV -EcoV3FilmStandalone -EcoV3FilmOut=<폴더>
  "-EcoV3FilmShots=forest_ground,330,470,1.8,0,0,3,3;barren_border,340,240,1.8,90,0,8,3;cross_out,340,300,1.8,-90,0,12,8,340,220,1.8;highland_ground,340,-490,1.8,90,0,22,3;snow_out,340,-300,1.8,90,0,26,8,340,-220,1.8;barren_ground,340,10,1.8,90,0,36,3"
  -EcoV3FilmEvery=10 -EcoV3FilmWatch=EcoV3WeatherFx -UseFixedTimeStep -fps=30 -seconds=40 -windowed -ResX=1920 -ResY=1080 -nosplash -DisablePlugins=Bridge,Fab
  "-ExecCmds=au.MuteAudio 1"     (이 판은 -ini 로 넣어 거부됐다 — 7절)
python results/v3/wild3/verify/make_verify_stills.py --run <폴더>/wxV
```

## 파일

- `README.md` — 이 글. `stills.jpg` — 정지 넷. `exits.md`·`exits.json` — 나가기 두 번의 캡처마다 연출 상태·재생 중 소리(`make_verify_stills.py` 가 만듦).
- `compare_weather_s20004.md`·`.json` — 세션 20004 대 파이썬(+ 날씨가 바꾼 것). `compare_weather_pooled_s20000-20008.md`·`.json` — 지도 27장.
  `compare_weather_effect_s20000-20005.md`·`.json` — 날씨가 바꾼 것 세션 6개. `effect_catches.py`·`effect_catches.md` — 날씨가 바꾼 잡힘 수 세션 9개.
- `unreal_logs/`(날씨 판 20003~20008)·`unreal_logs_weather_off/`(끈 판 20003~20005) — `../../wild1/trim_unreal_log.py` 로 고른 기록. `unreal_exports/` — 원판·지역 날씨 JSON.
- `film_wxV/` — 촬영 감독 `shots.json`·`watch.txt`(발소리 줄 뺌). `runs/` — 파이썬 판(커밋하지 않음).
