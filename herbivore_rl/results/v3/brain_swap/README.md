# 두뇌 바꾸기 시연 — Play 를 멈추지 않고 사슴 두뇌를 R4 로 (2026-10-18)

사용자 10-18: '나무나 풀 같은 식생이 점점 변해서 환경이 달라지면 그 정보가 없는 상태로 사슴은 학습이 되어 있잖아? … 우리가 계획한 가중치 로더 써서
두뇌 바꿔 주는 기술을 한번 적용해 보자'. 로더 코드는 `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoV3Brain.{h,cpp}`, 쓰는 법은
`AdaptiveEcosystem/Docs/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md` 4-5b '10-18 두뇌 바꾸기'.

## 1. 결론

- **두뇌를 빌드 없이, Play 를 멈추지 않고 바꿔 끼울 수 있다.** 120초에 내장 두뇌(R1b-F)를 R4 s0 파일 두뇌로 바꿨더니, 바꾼 결정 스텝부터 사슴이 새 두뇌로 움직였다.
  사슴은 그대로 남았고(지우거나 새로 만들지 않음), 바꾸기 앞 기록은 바꾸지 않은 판과 한 줄도 다르지 않았다.
- **바뀐 것이 눈에 보인다.** 늑대를 알 때 숨는 몫이 바꾸기 뒤 120초 동안 **내장 1.9% → R4 13.3%** 다(세션 셋 합). 같은 시간대의 바꾸지 않은 판과 견준 값이라
  낮밤·늑대 배부름 같은 시간 차이는 빠져 있다. 파이썬 R4 보고(`results/v3/r4/situ.md`)의 3.0 → 13.7% 와 같은 쪽이다.
- **잡힌 수는 그대로다**(바꾼 뒤 120초 포획 32 대 31). R4 가 사슴을 덜 잡히게 하지 못했다는 판정(`results/v3/r4/README.md`)과 맞는다. 그래서 게임 기본 두뇌는 R1b-F 그대로다.
  이 시연은 '바꿔 끼우는 기술'을 보이는 것이지 R4 를 쓰자는 것이 아니다.
- 지금 두뇌는 나무·풀을 관측으로 보지 못한다(관측 18칸). 로더는 '환경이 바뀌면 그 환경에서 다시 배운 두뇌를 빌드 없이 넣는' 길이다. 새 두뇌가 더 낫다는 판정은 파이썬
  사전 등록 판정이 한다.

## 2. 어떻게 쟀나

- 언리얼 통합 레벨 헤드리스(`/Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3`, 기본값 = 레벨 나무 + 날씨, 지역마다 사슴 128·늑대 4, 241초, `-benchmark -fps=60`).
- 세션 20000·20001·20002 마다 두 판:
  - `base` — 처음부터 끝까지 내장 두뇌 `v3_r1_g995_s3_20m@eca97f2e`(R1b, 통합 모드는 얼기를 세계가 막아 R1b-F).
  - `swap` — 같은 세션, `-EcoV3BrainSwapAt=120 -EcoV3BrainSwapTo=v3_r4_g995_s0_20m`. 120.0초(전역 스텝 900)의 결정 스텝 경계에서 `v3_r4_g995_s0_20m@f807bea5`
    (`AdaptiveEcosystem/EcoBrains/v3_r4_g995_s0_20m.json`)로 바꾼다.
- 숫자는 10초마다 지역마다 나오는 기록 줄 `[EcoV3I] <지역> 두뇌 |` 에서 읽었다. 정의는 R4 보고 도구 `results/v3/r4/situ_eval.py` 와 같다:
  - 두뇌 스텝 = 산 사슴의 결정 스텝 가운데 도주 반사(도주·웅크림 덮기)가 덮지 않은 스텝. 행동 = 그 스텝에 실제로 한 행동.
  - 늑대를 앎 = 그 스텝의 결정 관측에서 `pred_count > 0`(깨어 있는 늑대를 보거나 들음).
- 비교 도구 `compare_swap.py`(아래 3절), 표 `compare_swap.json`, 고른 기록 줄 `unreal_logs/s<세션>_{base,swap}.log`.

## 3. 표

늑대를 알 때 두뇌 스텝의 숨기 몫 (괄호 = 늑대를 안 두뇌 스텝 수, 세 지역 합):

| 세션 | 앞 0~120초 base | 앞 swap | 뒤 120~240초 base (내장) | 뒤 swap (R4) |
|---|---|---|---|---|
| 20000 | 2.8% (16,743) | 2.8% (16,743) | 3.3% (13,407) | **10.7%** (12,496) |
| 20001 | 1.0% (21,173) | 1.0% (21,173) | 1.9% (19,029) | **15.0%** (17,586) |
| 20002 | 1.9% (18,439) | 1.9% (18,439) | 0.7% (14,242) | **13.5%** (7,704) |
| 합 | 1.8% (56,355) | 1.8% (56,355) | 1.9% (46,678) | **13.3%** (37,786) |

- 앞 창은 두 판이 숫자까지 같다. 바꾸기 앞 기록 줄도 모두 같다(세션마다 377·376·376 줄, 시각·CPU 칸과 설정 줄 '사슴 두뇌:' 빼고).
- 바꾸기 줄은 swap 판마다 하나: `[EcoV3I] 두뇌 바꿈 | 120.0초 (전역 스텝 900) | v3_r1_g995_s3_20m@eca97f2e → v3_r4_g995_s0_20m@f807bea5 …`. base 판에는 없다.
- 지역마다 보아도 뒤 창의 R4 숨기 몫이 모두 내장보다 크다(9칸 가운데 9칸 — 표는 `compare_swap.py` 출력).
- 모든 두뇌 스텝의 숨기 몫(늑대를 모를 때 포함)은 뒤 창 base 0.03~0.16% 대 swap 0.41~0.94% 다. 늑대를 모를 때는 두 두뇌 모두 거의 먹기만 한다.
- 뒤 창 포획 10·11·10 대 10·11·11, 굶음 0, 창 끝 산 사슴 362·363·364 대 362·363·363. EcoV3I 경고·오류 0.

## 4. 다시 돌리기

```sh
# herbivore_rl/ 에서 (편집기를 닫고, 빌드한 뒤)
for S in 20000 20001 20002; do
  for K in base swap; do
    X=""; [ "$K" = swap ] && X="-EcoV3BrainSwapAt=120 -EcoV3BrainSwapTo=v3_r4_g995_s0_20m"
    MSYS_NO_PATHCONV=1 "<UE_5.8>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 \
      -EcoV3DeerPerRegion=128 -EcoV3Seed=$S $X -benchmark -fps=60 -seconds=241 -NullRHI -NoSound -unattended -nosplash -nopause \
      -DisablePlugins=Bridge,Fab -abslog=<폴더>/s${S}_${K}_full.log
  done
done
python results/v3/brain_swap/compare_swap.py --logs <폴더> --sessions 20000-20002
```

PIE 에서 같은 것을 보려면: 통합 v3 모드로 Play → `eco.V3Debug 1` → 콘솔 `eco.V3Brain.Load v3_r4_g995_s0_20m`. 지역 글자 끝의 '이 두뇌로 늑대를 알 때 숨기 n%' 와
사슴 글자 '숨기'(파랑)가 늘어난다. 되돌리기는 `eco.V3Brain.Load builtin`.
