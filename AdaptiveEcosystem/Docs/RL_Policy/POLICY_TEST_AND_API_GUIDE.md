# PPO 정책 계층 — 테스트·연동 가이드

이 PR 을 **테스트하는 사람**과 정책 계층에 **다른 시스템을 연결할 사람**을 위한 문서다.
빌드 구조, 검증 기록, 엔진 버전 이슈 같은 구현 세부는
[UNREAL_POLICY_INTEGRATION.md](UNREAL_POLICY_INTEGRATION.md), 파이썬 학습 과정과 결과는
[`herbivore_rl/docs/PROJECT_SUMMARY.md`](../../../herbivore_rl/docs/PROJECT_SUMMARY.md) 에 있다.

---

## 1. 5분 테스트

### 1.1 레벨

**`Content/EcoTest/L_EcoPolicyTest`** 를 연다. 바닥, 조명, 스포너(`EcoPolicyTestSpawner_0`)
하나뿐인 레벨이다. Play 하면 스포너가 Mass 엔티티를 만들고 정책·조향 프로세서가 바로 돈다.

> **UE 5.8.3** 에서 확인했다 (팀 에셋은 5.8.2·5.8.3 으로 저장돼 있다). 정식 5.8.0 보다 이전
> 빌드에서는 에디터가 켜지자마자 꺼지거나 에셋이 `Custom version is too new` 로 안 열린다.
> Epic Games Launcher 에서 5.8 을 최신 핫픽스로 업데이트한다.

### 1.2 순서

1. **Play** (Alt+P) — 초식 96마리, 포식자 5마리가 생긴다
2. **출력 로그** 를 연다 — 5초마다 `[Eco]` 줄이 찍힌다
3. **콘솔**(`~`)에 `eco.UseLearnedPolicy 0` → Utility AI, `eco.UseLearnedPolicy 1` → 학습 정책.
   Play 중에 바로 바뀐다

### 1.3 확인할 것

| 확인 | 정상 | 이상하면 |
|---|---|---|
| 초식 점이 움직인다 | 로그 `이동 96` 이고 화면에서도 이동 | 정지 = 조향 적분 문제 |
| 포식자가 쫓고 잡는다 | 부채꼴 안 초식에게 빨간 추격선, 잡히면 주황 구. 로그 `포획` 이 늘어남 | 포획 0 이 계속되면 포획 판정 문제 |
| 잡힌 초식이 다시 나타난다 | 로그 `개체 96` 유지 | 줄어들면 리스폰 문제 |
| 경계 밖으로 안 나간다 | 검은 사각형(±150m) 안 | — |
| 정책을 바꾸면 행동이 바뀐다 | 아래 기대값 | 값이 같으면 콘솔 변수가 안 먹는 것 |

로그 예:

```
[Eco] 정책=학습 | 개체 96, 이동 96, 포식자 본 개체 10, 도주 0 | 포획 5 (누적 5) | forage 0.41 cohesion 0.80 flee 0.38 cover 0.05
```

기대값 (60초 실행, 5초 구간 평균의 범위. 10-01 결함 4건 수정 뒤 30·60FPS 에서 잰 값):

| 정책 | cohesion | cover | flee | 특징 |
|---|---|---|---|---|
| 학습 정책 (`1`) | 0.65 ~ 0.93 | 0.05 ~ 0.06 | 0.37 ~ 0.39 | 꾸준히 뭉쳐 있고 은신처 쪽 가중치를 조금 쓴다 |
| Utility (`0`) | 0.12 ~ 0.85 | 0.00 ~ 0.02 | 0.39 ~ 0.40 | 포획이 몰리면 cohesion 이 오르고 조용하면 떨어진다 |

수정 전 값(cohesion 0.32~1.00, flee 0.42~0.71 등)은 관측 5(최근 피식)가 128배 부풀어 있을 때
잰 것이라 쓰지 않는다 (`UNREAL_POLICY_INTEGRATION.md` 4.2절).

**포획 수로 두 정책의 우열을 보면 안 된다.** 이 레벨은 학습 환경과 조건이 다르다 (6절).
우열 비교는 파이썬 평가(시드 20개 짝지은 비교)의 몫이다.

### 1.4 화면 표시

| 표시 | 뜻 |
|---|---|
| 점 (화면 12px) 파랑 → 빨강 | 초식. 색 = `cohesion` 0 → 1 |
| 점에서 뻗은 선 | 초식이 바라보는 방향. 멈춘 개체는 유지된 방향을 회색 가는 선으로 |
| 굵은 노란 선 | 도주 중 (포식자 반대 방향) |
| 빨간 X / 회색 X | 포식자 — 사냥 중 / 식사 중 |
| X 앞 부채꼴 | 포식자 시야 28m × 150°. 이 안의 초식만 쫓는다 |
| X 에서 나간 빨간 선 | 지금 쫓는 표적 |
| 주황 구 (1.5초) | 방금 잡힌 자리 |
| 파란 두 겹 원 | 은신처 4곳 (반경 25m). 안의 초식은 포식자에게 2.5배 멀어 보인다 |
| 회색 원 / 검은 사각형 | 스폰 반경 / 시뮬레이션 경계 |

### 1.5 자동 테스트

- **UE**: 세션 프런트엔드 → Automation 에서 `AdaptiveEcosystem.Policy` (30개). 명령줄:
  ```bash
  UnrealEditor-Cmd.exe <절대경로>/AdaptiveEcosystem.uproject "-ExecCmds=Automation RunTests AdaptiveEcosystem.Policy" "-testexit=Automation Test Queue Empty" -unattended -nopause -nosplash -NullRHI -log
  ```
- **Python**: `cd herbivore_rl && python -m pytest -q` (89 passed, 1 skipped)

| UE 테스트 | 확인하는 것 |
|---|---|
| `GoldenVectorParity` | C++ 신경망 추론이 파이썬 정답 100쌍과 일치 (최대 오차 1.19e-7) |
| `SteeringParity` | C++ 조향 수식이 파이썬 정답 100쌍과 일치 (1.79e-7) |
| `OutputRange` | 어떤 관측에도 행동이 [0,1] |
| `BehaviorConfigUnits` | 격자 단위 → cm·초 변환 |
| `UtilityBaseline` | Utility 수식과 튜닝 계수 |
| `PipelineSmoke` | 프로세서 4개가 실제 엔티티에서 돎. 관측·행동 범위, 정책 주기, 속력, **위치가 실제로 바뀜**, 움직이는 개체의 yaw = 속도 방향 |
| `Predation.FromBehind` | 뒤에서 온 포식자에게도 잡힘 |
| `Predation.OnePerTickAndCooldown` | 포식자당 한 틱 한 마리, 식사 쿨다운 |
| `Predation.CoverHidesDistance` | 은신처 안이면 체감 거리 2.5배 |
| `Predation.EmaPerCatchMatchesPython` / `EmaIsGlobal` / `EmaDenominatorAliveMaxOverStep` | 관측 5: 피식 1건 = 파이썬과 같은 증가량(128마리면 0.0039), 위치와 무관한 전역 값, 분모 = 스텝 내 산 개체 최대 수 |
| `Predation.EmaStepOwnedByPredationProcessor` / `ObservationReadsGlobalEma` | EMA 스텝은 포식 프로세서가 한다, 다음 결정이 같은 전역 값을 읽는다 |
| `Predation.EmaFormulaSequence` / `SaveLoadGlobalEma` | EMA 식 고정, 저장·불러오기(옛 지역별 저장은 거부) |
| `AliveFilter.CorpseLeavesNeighborhood` / `DeadAgentIsFrozen` / `RespawnRoundTrip` | 잡힌 개체는 Alive→PendingDeath, 다음 틱부터 색인·관측·정책·조향에서 빠진다, 되살리면 돌아온다 |
| `AliveFilter.PredationAfterSteering` / `NoDoubleCatchSameTick` | 포획 판정은 조향 뒤. 두 포식자가 같은 개체를 고르면 사망 1건, 둘 다 쿨다운(파이썬과 같다) |
| `Schedule.StepClockUnits` / `SixtyFpsMatchesLegacy` | 시간 시계 단위(잡음 섞인 60FPS 도 매 프레임 1틱), 60FPS 에서 예전 결정 프레임과 같다 |
| `Schedule.DecisionRateFpsIndependent` / `PredationEmaFpsIndependent` / `LargeAndZeroDelta` / `SpawnPhaseSentinel` | 10~120FPS 에서 결정 수와 EMA 감쇠가 같다, 큰 dt·0·NaN 처리, 미배정 위상(-1) 흩기 |
| `Heading.YawFollowsVelocity` / `HeldWhenStopped` / `FollowsBoundaryVelocity` | 움직이면 yaw = 속도 방향, 멈추면 유지(그 방향 기준으로 본다), 벽 반발 뒤 속도를 따른다 |

---

## 2. 열어 둔 값

### 2.1 실행 중에 바꿀 수 있는 것

| 콘솔 변수 | 기본 | 뜻 |
|---|---|---|
| `eco.UseLearnedPolicy` | `1` | `1` = 학습 정책 (`RunPolicy`), `0` = Utility AI (`RunUtilityPolicy`) |

### 2.2 테스트 스포너 — 레벨에서 바꿀 수 있는 것

`EcoPolicyTestSpawner_0` 선택 → 디테일 패널. **Play 전에** 바꾼다 (스폰 시점에 읽는다).

| 카테고리 | 속성 | 기본 | 단위 | 뜻 |
|---|---|---|---|---|
| Ecology\|Test | `HerbivoreCount` | 96 | 마리 | 초식 수 |
| | `PredatorCount` | 5 | 마리 | 포식자 수 |
| | `SpawnRadius` | 12000 | cm | 처음 뿌리는 반경 |
| | `PredatorSpeedRatio` | 1.0 | 배 | 포식자 속도 = 초식 속도 × 이 값. 파이썬은 0.8~1.2 |
| | `bDrawDebug` | 켬 | | 화면 표시 전체 |
| | `LogInterval` | 5 | 초 | `[Eco]` 로그 주기. 0 이면 끔 |
| Ecology\|Test\|Debug | `HerbivorePointSize` | 12 | px | 초식 점 크기 (줌과 무관) |
| | `HeadingLineLength` | 700 | cm | 바라보는 방향 선 길이 |
| | `PredatorMarkSize` | 450 | cm | 포식자 X 반폭 |
| | `bDrawPredatorView` | 켬 | | 포식자 시야 부채꼴과 추격선 |

스폰 배치는 고정 시드라 매번 같다. 정책만 바꿔 같은 장면을 비교할 수 있다.

### 2.3 트레잇 — Mass Entity Config 에셋으로 개체를 만들 때

| 트레잇 (표시 이름) | 속성 | 적용 여부 |
|---|---|---|
| `UEcoHerbivoreTrait` (Eco Herbivore) | `MaxEnergy` (100), `InitialEnergyRatio` (1.0) | 적용됨 — 관측 `energy` 의 분모와 시작값 |
| | `BehaviorConfig` | 보이기만 하고 프로세서가 읽지 않는다 — 프로세서는 2.5절 상수를 쓴다. 결정 위상은 트레잇이 -1(미배정)로 두고 정책 프로세서가 엔티티 인덱스로 흩는다 |
| `UEcoPredatorTrait` (Eco Predator) | 없음 | 포식자에게 행동을 주지 않는다. 이동은 다른 AI 나 플레이어 몫 |

초식 트레잇이 붙이는 것: `FEcoHerbivoreTag`, `FEcoAliveTag`(서버·스탠드얼론), `FMassCustomMovementTag`, 관측·행동·주기·기하·생체
프래그먼트, 공유 설정. 위치·속도는 요구만 한다 (엔진 이동 트레잇이 제공).

- **엔진 `UMassMovementTrait` 와 같이 써도 된다.** `FMassCustomMovementTag` 가 있어서 엔진 이동
  프로세서가 이 개체를 건너뛴다. 없으면 엔진 기본값(`bIsCodeDrivenMovement = true`) 때문에
  이동이 이중으로 적용되거나 속도가 덮어써진다.
- 트레잇 경로(MassSpawner 로 레벨 배치)는 **빌드만 확인했고 레벨에서는 아직 검증하지 않았다.**
  검증된 경로는 테스트 스포너다.

### 2.4 코드 기본값 — 에디터에서 못 바꾸는 것

월드 서브시스템은 레벨에 배치되지 않아서 디테일 패널이 없다. 바꾸려면 헤더의 기본값을 고친다.

| 클래스 | 값 | 기본 | 뜻 |
|---|---|---|---|
| `UEcoDummyWorldProviderSubsystem` | `WorldExtent` | 15000 cm | 시뮬레이션 경계 (±). 테스트 레벨 바닥과 같다. 바닥을 바꾸면 같이 바꾼다 |
| | `CoverRadius` | 2500 cm | 은신처 반경. 위치는 (±0.45 × WorldExtent, ±0.45 × WorldExtent) 4곳 |
| | `FoodWavelength` | 6000 cm | 먹이 무늬 파장 |
| | `FoodThreshold` | 0.35 | 이 값 아래 먹이는 0 |
| | `ConsumeRegenPerSecond` | 0.02 | 소비된 먹이의 초당 회복 |

### 2.5 학습 조건 상수 — 자동 생성, 손대지 않는다

`AI/Policy/EcoBehaviorConfig.h`. `herbivore_rl/configs/default.yaml` 에서 `python export_weights.py`
가 만든다. **관측 정규화나 조향 상수를 바꾸면 정책을 다시 학습해야 한다** (정책이 이 값으로 학습됐다).

| 상수 | 값 | 뜻 |
|---|---|---|
| `PolicyInterval` / `StepSeconds` | 8 논리 틱 / 0.133초 | 정책 결정 한 번, 피식 EMA 한 스텝 = 파이썬 1스텝. 프레임 수가 아니라 시간으로 센다 (1 논리 틱 = 1/60초) |
| `GridUnitCm` | 200 | 파이썬 격자 1칸 |
| `HerbSpeedCmS` | 900 | 초식 속력 (항상 이 속력) |
| `SeeRadiusCm` / `FovDeg` | 4000 / 120 | 초식 시야 |
| `ObsPredCountNorm` / `ObsKinCountNorm` / `ObsCoverNormCm` | 8 / 20 / 4000 | 관측 정규화 분모 |
| `SepWeight` / `SepRadiusCm` / `FleeWeight` | 1.35 / 1000 / 3.0 | 조향 상수 |
| `PredationEmaDecay` / `PredationEmaGain` | 0.95 / 10 | 피식 EMA(관측 5) 갱신 |
| `PredViewRadiusCm` / `PredFovDeg` | 2800 / 150 | 포식자 시야 |
| `PredCatchRadiusCm` / `PredEatCooldownS` | 200 / 0.667 | 포획 거리 / 식사 쿨다운 |
| `CoverHideMult` | 2.5 | 은신처 안 체감 거리 배수 |

---

## 3. 다른 시스템이 연결할 곳

### 3.1 먹이·은신처 정보 제공

정책 계층은 먹이와 은신처를 **인터페이스로만** 읽는다. 기본은 임시 월드(`UEcoDummyWorldProviderSubsystem`)
이고, 실제 시스템이 생기면 등록만 바꾸면 된다. 프로세서 코드는 그대로다.

```cpp
UEcoWorldProviderRegistry* Registry = World->GetSubsystem<UEcoWorldProviderRegistry>();
Registry->SetFoodProvider(MyFoodSystem);    // IEcoWorldFoodProvider
Registry->SetCoverProvider(MyShelterSystem); // IEcoWorldCoverProvider
```

| 인터페이스 | 함수 | 쓰는 곳 |
|---|---|---|
| `IEcoWorldFoodProvider` | `GetFoodDensity(Location, Radius)` → [0,1] | 관측 `food_density` |
| | `GetFoodGradient(Location, Radius)` → 방향 | 조향 먹이 방향 |
| | `ConsumeFood(Location, Amount)` → 실제 먹은 양 | 아직 호출하는 프로세서 없음 |
| `IEcoWorldCoverProvider` | `GetCoverDistance(Location)` → cm | 관측 `cover_distance` |
| | `GetCoverDirection(Location)` → 방향 | 조향 은신처 방향 |
| | `IsInCover(Location)` → bool | 포획 판정 (체감 거리 2.5배) |

### 3.2 포식 보고

`UEcoRegionPredationSubsystem` 이 최근 피식 EMA(관측 `recent_predation`)를 관리한다. 파이썬과 같은
**전역 값 하나**다: `ema = 0.95·ema + 0.05·(스텝 피식 사망 수 / 산 초식 수)·10`, 관측은 `min(ema, 1)`.
분모와 스텝은 `UEcoPredationProcessor` 가 맡는다(틱마다 포획 전 생존 수 보고, StepSeconds 마다 스텝).

| 함수 | 블루프린트 | 뜻 |
|---|---|---|
| `ReportPredation(Location)` | Callable | 피식 한 건. **플레이어가 잡을 때도 이걸 불러야 한다** (지금은 포식자 포획만 보고됨). Location 은 지금 식에 쓰지 않는다 |
| `GetRecentPredation()` | Pure | 최근 피식 [0,1] |
| `Get(Location)` | Pure (폐기 예정) | 호환용. 위치와 무관하게 위 값을 돌려준다 |
| `SaveToSlot` / `LoadFromSlot` | Callable | 세션 간 유지용. 자동 호출은 안 한다. 저장 스키마 2 — 예전 지역별 저장(값이 부풀어 있음)은 불러오지 않는다 |

### 3.3 읽어 갈 수 있는 프래그먼트

| 프래그먼트 | 쓰는 프로세서 | 내용 |
|---|---|---|
| `FEcoPolicyOutputFragment` | Policy (0.133초마다) | 가중치 4개 `forage` `cohesion` `flee_dist` `cover`, 모두 [0,1] |
| `FEcoObservationFragment` | Policy | 관측 7개 |
| `FEcoSteeringGeometryFragment` | Perception (매 틱) | 동족·포식자·먹이·은신처 방향과 거리 |
| `FEcoPredatorStateFragment` | Predation | 포식자 식사 쿨다운 (초) |
| 태그 `FEcoHerbivoreTag` / `FEcoPredatorTag` | — | 초식 / 포식자 |
| 태그 `FEcoAliveTag` / `FEcoPendingDeathTag` | Predation | 초식 쿼리는 전부 Alive 를 요구한다. 잡히면 HP=0(즉시) + Alive→PendingDeath(지연). 시체 정리(파괴·슬롯 해제)는 Lifecycle 몫 |

### 3.4 프로세서 순서

모두 PrePhysics, Server·Standalone, 게임 스레드.

```
Gather → Perception → Policy → Steering (속도 + 위치 적분 + yaw) → Predation (포획, 생존 수, EMA 스텝)
→ (페이즈 끝) 지연 명령 반영 — 잡힌 개체는 다음 틱부터 어디에도 걸리지 않는다
```

정책 결정과 피식 EMA 는 프레임 수가 아니라 시간(0.133초)으로 돈다. FPS 가 바뀌어도 같다.

**소셜 런타임과의 관계.** Alarm 프로세서는 `FEcoPolicyOutputFragment` 를 읽어 보정한 행동을
`FEcoSocialBehaviorFragment` 에 쓴다. Steering 은 `FEcoPolicyOutputFragment` 를 읽으므로
**지금은 경보 보정이 이동에 반영되지 않는다.** Shelter 프로세서는 그 보정값을 읽어 은신 의도를
정한다. 또 소셜 프로세서들은 `FEcoAliveTag` 와 소셜 전용 프래그먼트(무리·경보·신원·은신 의도)가
있는 개체만 처리하는데, 테스트 레벨 개체에는 `FEcoAliveTag` 만 있고 소셜 전용 프래그먼트가 없어서
테스트 레벨에서는 소셜 동작이 돌지 않는다.
Steering 이 보정값을 읽게 할지는 합의가 필요하다.

---

## 4. 팀 계약서(POLICY_CONTRACT_V1)와 다른 점 — 합의 필요

`AGENTS.md` 는 관측·행동 공식이 `POLICY_CONTRACT_V1.md` 와 일치해야 한다고 정한다. 이 PR 은
`herbivore_policy_spec.md` 를 따랐고, 다음이 다르다. 정책은 오른쪽 값으로 학습·검증됐다.

| 항목 | 계약서·`EcoPolicyContracts.h` | 이 PR |
|---|---|---|
| `predator_count` 정규화 | ÷ 5 (`MaxPredatorCap`) | ÷ 8 |
| `cover_distance` 정규화 | ÷ 3000cm (`CoverSearchRadius`) | ÷ 4000cm |
| Utility 수식 | 고정 계수 (`EvaluateUtilityBaseline`) | Optuna 튜닝 계수 (`RunUtilityPolicy`) |
| 조향에서 `flee_dist` | 도주 힘에 곱하는 가중치, 정렬 항 있음 | 도망을 시작하는 거리 (시야 대비 비율), 정렬 항 없음 |
| `recent_predation` 정의 | 지역 피식 기록 | 전역 EMA, 분모 = 산 초식 수 (파이썬과 같음) |

제안: 계약서를 이 PR 의 구현에 맞춰 고친다. 반대로 코드를 계약서에 맞추면 정규화가 바뀌어
처음부터 다시 학습해야 한다.

---

## 5. 새 정책을 넣는 법

```bash
cd herbivore_rl
python train.py              # 200만 스텝, 약 1분 → ckpt/final.zip
python export_weights.py     # 헤더 5개 생성 + 파이썬과 자동 비교 → 언리얼 폴더로 복사
```

그다음 `AdaptiveEcosystemEditor Win64 Development` 로 빌드하면 새 가중치가 들어간다.
`export_weights.py` 가 통과 메시지를 내지 않으면 빌드하지 않는다.

---

## 6. 테스트 레벨의 한계

행동을 **보는** 용도다. 학습 환경과 다음이 다르다.

- 밀도: 파이썬은 한 변 120~220m 에 128마리, 테스트 레벨은 300m 에 96마리 (약 1/4)
- 원거리형 포식자 없음 (파이썬은 에피소드마다 0~50%)
- 에너지가 줄지 않고 먹이가 소비되지 않는다 (대사·섭식 프로세서 없음)
- 먹이는 임시 사인 무늬이고 화면에 그려지지 않는다
- 정책 실패 시 Utility 로 자동 전환하는 기능이 아직 없다 (콘솔로 수동 전환만)
