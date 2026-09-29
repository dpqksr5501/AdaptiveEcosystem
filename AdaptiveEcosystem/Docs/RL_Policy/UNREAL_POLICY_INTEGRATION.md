# 언리얼 정책 통합 — 빌드·검증·확장 절차

`herbivore_policy_spec.md` §9 의 산출물 문서다. §은 전부 그 사양서의 절 번호.

> **테스트 방법, 열어 둔 값, 다른 시스템이 연결할 API 는
> [POLICY_TEST_AND_API_GUIDE.md](POLICY_TEST_AND_API_GUIDE.md) 에 있다.** 이 문서는 구현 세부다.

> **위치 이탈 기록 (§1.8).** §10 은 이 코드를 `herbivore_rl/unreal/Source/` 에 두라고
> 하지만 실제 UE 모듈은 `AdaptiveEcosystem/Source/AdaptiveEcosystem/` 다. 격리 폴더에
> 두면 빌드에 안 들어가서 복사 단계가 하나 늘고, 목표가 "언리얼에서 도는 것"이므로
> 실제 모듈에 직접 넣었다. §9.9 의 `unreal/README.md` 가 이 문서다.

---

## 1. 지금 되는 것

| 검증 | 방법 | 결과 |
|---|---|---|
| §8.3 numpy vs SB3 | `pytest tests/test_export.py` | 1.192e-07 |
| §9.8-1 정책 파리티 | gcc 단독 + UE 자동화 테스트 | 1.192e-07 |
| §9.8-2 조향 파리티 | 〃 | 1.788e-07 |
| §9.8-3 전체 파이프라인 | UE 자동화 테스트 + 테스트 레벨 | 통과 |
| §9.8-4 학습 정책 교체 | 콘솔 변수만 | 통과 |
| §9.8-5 지역 연동 | 테스트 레벨 로그 | 통과 |
| §4.2 포획 규칙 파리티 | UE 자동화 테스트 3개 (`Policy.Predation.*`) | 통과 — 수정 전 코드에서 3개 모두 실패하는 것을 먼저 확인 (4.1절) |

## 2. 파일 지도

모두 `Source/AdaptiveEcosystem/AI/Policy/` 아래.

| 파일 | 역할 | 자동 생성 |
|---|---|---|
| `EcoPolicyInference.h` | §9.3 `RunPolicy`. **엔진 비의존** (`<cmath>` 만) | |
| `EcoPolicyInference.cpp` | §5.1 `RunUtilityPolicy` | |
| `EcoSteering.h` | §3.3 `Steer()`. 역시 엔진 비의존 | |
| `EcoBehaviorFragments.h` | §9.2 태그·공유 설정·기하 캐시·포식자 상태(식사 쿨다운) | |
| `EcoBehaviorTraits.h/.cpp` | 레벨 배치용 Mass 트레잇 | |
| `EcoBehaviorProcessors.h/.cpp` | §9.4 Policy + §9.5 Steering (+ 게더·지각) | |
| `EcoWorldProviders.h/.cpp` | §9.4 월드팀 인터페이스 + 더미 | |
| `EcoNeighborhoodSubsystem.h/.cpp` | 이웃 조회 (균일 격자) | |
| `EcoRegionPredationSubsystem.h/.cpp` | §9.6 지역 EMA + SaveGame | |
| `PolicyWeights.h` | 7-64-64-4 가중치 | ✅ |
| `UtilityParams.h` | §5.2 튜닝 계수 | ✅ |
| `EcoBehaviorConfig.h` | §9.7 단위 대응 | ✅ |
| `PolicyGoldenVectors.h` | §9.8-1 검증용 100쌍 | ✅ |
| `SteeringGoldenVectors.h` | §9.8-2 검증용 100쌍 | ✅ |
| `Tests/EcoPolicyInferenceTest.cpp` | 파리티·범위·단위 테스트 5개 | |
| `Tests/EcoPipelineTest.cpp` | §9.8-3 파이프라인 테스트 (위치 변화 검사 포함) | |
| `Tests/EcoPredationTest.cpp` | §4.2 포획 규칙 테스트 3개 — 뒤에서 포획, 한 틱 한 마리·쿨다운, 은신처 | |
| `Tests/EcoTestWorld.h` | 두 테스트가 같이 쓰는 월드·프로세서 헬퍼 | |

그리고 `Source/AdaptiveEcosystem/Debug/EcoPolicyTestSpawner.h/.cpp` — 시각 확인용.

**✅ 표시된 다섯 개는 손으로 고치지 말 것** (§12). `herbivore_rl/export_weights.py` 가
생성하고 이 폴더로 복사한다.

## 3. 가중치 갱신 절차

```bash
cd herbivore_rl
python export_weights.py
```

한 번이면 `export/` 와 이 모듈 양쪽이 갱신된다. 그 뒤 재빌드하면 새 정책이 게임에 들어간다.
`export_weights.py` 가 §8.2 파리티를 스스로 검사하므로, 통과 메시지가 안 나오면 빌드하지 말 것.

## 4. 빌드와 검증

```bash
"C:/Program Files/Epic Games/UE_5.8/Engine/Build/BatchFiles/Build.bat" AdaptiveEcosystemEditor Win64 Development -Project=<절대경로>/AdaptiveEcosystem.uproject
```

```bash
"C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" <절대경로>/AdaptiveEcosystem.uproject "-ExecCmds=Automation RunTests AdaptiveEcosystem.Policy" "-testexit=Automation Test Queue Empty" -DisablePlugins=Bridge,Fab -unattended -nopause -nosplash -NullRHI -log
```

테스트 레벨을 헤드리스로 25초 돌려 보기:

```bash
"C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" <절대경로>/AdaptiveEcosystem.uproject /Game/EcoTest/L_EcoPolicyTest -game "-ExecCmds=eco.UseLearnedPolicy 1" -DisablePlugins=Bridge,Fab -unattended -nopause -nosplash -NullRHI -NoSound -benchmark -benchmarkseconds=25 -fps=30
```

Git Bash 에서 돌릴 때는 `export MSYS_NO_PATHCONV=1` 을 먼저 해야 한다. 안 하면
`/Game/EcoTest/...` 가 `C:/Program Files/Git/Game/...` 로 바뀌어 맵을 못 찾고 바로 종료된다.

로그에 5초마다 이런 줄이 찍힌다:

```
[Eco] 정책=학습 | 개체 96, 이동 96, 포식자 본 개체 18, 도주 0 | 포획 5 (누적 5) | forage 0.34 cohesion 0.88 flee 0.42 cover 0.10
```

실측 (96마리, 포식자 5, 60초, 같은 스폰 배치):

| 정책 | forage | cohesion | flee | cover | 포획 (60초) |
|---|---|---|---|---|---|
| Utility (§5.1) | 0.34 ~ 0.37 | 0.32 ~ 1.00 (포획 따라 출렁) | 0.42 ~ 0.71 | 0.00 ~ 0.02 | 41 |
| 학습 (PPO) | 0.30 ~ 0.39 | 0.83 ~ 0.95 | 0.39 ~ 0.43 | 0.06 ~ 0.14 | 49 |

**포획 수로 두 정책의 우열을 말하면 안 된다.** 한 번 돌린 값이고 5초 구간마다 0~9 로
요동한다. 게다가 이 레벨은 평가 환경이 아니라 시연용이다 — 밀도가 학습 때의 1/4 쯤이고,
원거리형 포식자가 없고, 에너지가 줄지 않는다 (6절). 우열 비교는 파이썬 `evaluate.py`
(20시드 짝지은 비교)의 몫이다.

이 레벨이 보여 주는 건 **반응하는 대상의 차이**다. Utility 는 §5.1 수식상
`recent_predation` 하나에만 반응해 포획이 몰리면 `cohesion` 과 `flee` 가 같이 치솟고
(9회 포획 구간: 0.32 → 0.63, 0.42 → 0.60), 조용하면 감쇠한다. 학습 정책은 관측 7개를
다 써서 `cohesion` 을 0.83~0.95 로 안정되게 유지하고 `cover` 를 Utility 의 수 배로 쓴다.
§9.8-5 의 폐루프(포획 → 지역 EMA → 행동)가 이제 **실제 포획으로** 돈다.

> **이전 수치는 두 번 폐기했다.** 처음 표는 개체가 정지한 상태에서 잰 값이었고
> (7절 "속도를 위치에"), 두 번째 표는 뒤에서 온 포식자에게는 잡히지 않는 규칙에서 잰
> 값이었다 (4.1절). 위 표가 두 문제를 다 고친 뒤의 값이다.

화면 표시:

| 표시 | 뜻 |
|---|---|
| 점 (화면 12픽셀) 파랑 → 빨강 | 초식. 색 = `cohesion` 0 → 1 |
| 점에서 뻗은 가는 선 | 초식 진행 방향 |
| 굵은 노란 선 | 도주 중 (§3.3 도주 분기). 포식자 반대 방향 |
| 빨간 X / 회색 X | 포식자 — 사냥 중 / 식사 중(쿨다운) |
| X 앞 부채꼴 | 포식자 시야. 반경 28m × 150°. 이 안의 초식만 쫓는다 |
| X 에서 나간 빨간 선 | 추격 중인 표적 |
| 주황 구 (1.5초) | 방금 포획된 지점 |
| 파란 두 겹 원 | 은신처. 더미 월드의 고정 4곳 (±0.45 × WorldExtent), 반경 25m. 안의 초식은 포식자에게 2.5배 멀어 보인다 |
| 회색 원 / 검은 사각형 | 스폰 반경 / 시뮬레이션 경계 (`WorldExtent`) |

### 4.1 포획 규칙 — 파이썬과 달랐던 것

`UEcoPredationProcessor` 는 원래 **초식이 본** 포식자까지의 거리(`DistPredMin`)로 포획을
판정했다. 그 값은 초식 시야(120°) 안의 포식자만 센다. 파이썬 §4.2 는 포식자 쪽에서 판정하고
초식의 시야와 무관하다. 그래서 세 가지가 어긋나 있었다:

| | 파이썬 §4.2 | 수정 전 언리얼 |
|---|---|---|
| 뒤에서 온 포식자 | 잡힌다 | **안 잡힌다** — 추격은 대개 뒤에서 일어나므로 포획이 드물었다 |
| 은신처 | 체감 거리 × 2.5 | **효과 없음** — `bInCover` 를 설정만 하고 아무도 안 읽었다 |
| 한 포식자의 포획 | 스텝당 한 마리 + 식사 쿨다운 5스텝 | 한 틱에 여러 마리, 쿨다운 없음 |

이제 포식자 쿼리를 돌며 파이썬과 같은 규칙으로 판정한다 (`FEcoPredatorStateFragment` 에
쿨다운). 포식자 상수는 `default.yaml` → `export_weights.py` → `EcoBehaviorConfig.h` 로
넘어온다 (`PredCatchRadiusCm`, `PredEatCooldownS`, `CoverHideMult` 등).
`Tests/EcoPredationTest.cpp` 의 세 테스트가 **수정 전 코드에서 모두 실패하는 것을 먼저 보고**
고쳤다.

테스트 레벨의 포식자 AI 도 파이썬과 맞췄다. 예전에는 맵 전체의 최근접 초식을 직선으로 쫓는
전지적 추격이라, 초식이 먼저 발견하는 이점(초식 시야 40m > 포식자 28m)이 없었다. 지금은
시야 부채꼴 안의 표적만 체감 거리로 고르고, 없으면 스텝마다 ±0.15rad 로 배회하고, 벽에서
반사한다. 잡힌 초식은 파이썬 §4.3 처럼 월드 전체 랜덤 위치로 즉시 리스폰한다 — 이게 없을 때는
HP 0 인 개체가 계속 달리고 포식자가 그 "시체"를 영원히 쫓았다.

## 5. 이 환경에서 막히는 것 두 가지

**둘 다 우리 코드와 무관하다.**

1. **엔진 설치본의 `Bridge`(Megascans)·`Fab` 플러그인 바이너리가 엔진과 안 맞는다.**
   DLL 은 있지만 로드가 실패한다 (`UnrealEditor-Bridge.dll` → `GetLastError=126`,
   `UnrealEditor-MegascansPlugin.dll` → `127` "프로시저를 찾을 수 없음"). 플러그인 DLL 은
   2026-06-21, 엔진 코어(`UnrealEditor-Engine.dll`)는 2026-05-13 빌드다 — 플러그인이 더
   새 엔진에 맞춰져 있다. 에디터가 시작 직후 `EngineExit()` 으로 종료된다. 위 명령들이 전부
   `-DisablePlugins=Bridge,Fab` 를 다는 이유다. GUI 로 열려면 Epic Games Launcher 에서
   UE 5.8 을 복구 설치하거나 `.uproject` 에 두 플러그인을 `"Enabled": false` 로 박는다.
   (처음에는 "바이너리가 없다"고 적었는데 틀렸다. 파일은 있고 버전이 안 맞는 것이다.)

2. **`Content/` 에셋 144개가 UE 5.8 보다 새 엔진에서 저장돼 로드되지 않는다.**
   `OpenWorld.umap`, `BP_SkyManager`, `BP_WeatherManager` 등.
   ```
   Custom version is too new; UE5-Release: Package: 68, HeadCode: 65
   ```
   LFS 포인터 문제가 아니라 실제 에셋이고 헤더 버전이 이 엔진보다 높다.
   그래서 테스트 레벨을 `/Game/EcoTest/` 에 **새로** 만들었다 — 기존 콘텐츠에 의존하지 않는다.

## 6. 아직 안 한 것

- **플레이어 사냥이 아직 피식으로 안 잡힌다.** `UEcoPredationProcessor` 가 포식자 포획은
  보고하지만, 플레이어가 잡은 경우는 해당 코드에서
  `UEcoRegionPredationSubsystem::ReportPredation(Location)` 을 직접 불러야 한다 (§9.6).
- **피식된 개체의 생명주기.** `UEcoPredationProcessor` 는 HP 를 0으로 두고 보고만 한다.
  실제 제거·리스폰은 기존 Lifecycle 계층 몫이다. 파이썬은 슬롯을 즉시 리스폰한다 (§4.3).
  테스트 레벨에서는 `AEcoPolicyTestSpawner::RespawnCaught()` 가 그 대역을 한다 — 실제
  콘텐츠에 트레잇으로 배치하면 이 대역이 없으니 Lifecycle 연결이 필요하다.
- **테스트 레벨은 학습 환경과 다르다.** 시연용이라 다음이 빠져 있다. 행동을 보는 데는
  충분하지만 정책 우열을 재는 데는 쓰면 안 된다.
  - 밀도: 파이썬은 한 변 120~220m 에 128마리, 테스트 레벨은 300m 에 96마리 (약 1/4)
  - 원거리형 포식자: 파이썬은 에피소드마다 0~50% 가 원거리형(느림, 포획 거리 3, 확률 포획)
  - 에너지: 대사·섭식 프로세서가 없어 스폰 때 값에 고정된다. 관측 `energy` 가 변하지 않는다
  - 먹이: 더미 사인 격자. 파이썬은 저주파 잡음 + 문턱값 패치다
  - 포식자 속도: 파이썬은 0.8~1.2 에서 뽑는다. 레벨은 `PredatorSpeedRatio` 한 값
- **`UEcoPredationSaveGame` 이 자동 저장되지 않는다.** §9.6 은 세션 간 유지를 요구한다.
  `SaveToSlot`/`LoadFromSlot` 은 구현돼 있으니 게임의 세이브 흐름에 걸면 된다.
- **공유 설정을 프로세서가 안 읽는다.** `FEcoBehaviorConfigSharedFragment` 가 트레잇
  템플릿에는 들어가지만 프로세서는 `EcoBehaviorConfig.h` 상수를 직접 쓴다. 종별로 다른
  값을 주려면 프로세서에 `AddConstSharedRequirement` 를 붙이면 된다 — 에셋 재작성은 불필요.
- **전부 게임 스레드에서 돈다.** 공유 이웃 색인 때문이다. 병렬화하려면 색인을 읽기 전용으로
  굳히고 `bRequiresGameThreadExecution = false` 로 바꿔야 한다.
- **Mass 표현(ISM)이 없다.** 테스트 스포너는 디버그 드로우로 그린다. 실제 콘텐츠는
  `UMassVisualizationTrait` 을 엔티티 config 에 붙여야 한다.

## 7. 엔진 버전 마이그레이션 체크리스트

§9.1 이 UE 5.1 기준 MassFlock 을 가정했으나 **MassFlock 은 쓰지 않았다** — 5.8 까지의
API 변경 폭이 크고 필요한 건 반경 조회 하나뿐이라 균일 격자를 직접 만들었다.

UE 5.8 에서 실제로 부딪힌 것들 (다음 엔진 업그레이드 때 다시 볼 곳):

| 항목 | 5.8 에서 |
|---|---|
| `UMassProcessor::ConfigureQueries` | `(const TSharedRef<FMassEntityManager>&)` 를 받는다 |
| 쿼리 등록 | 생성자 이니셜라이저 `EntityQuery(*this)` |
| `FTransformFragment` | `MassCommonFragments.h` 가 아니라 `Mass/EntityFragments.h` (MassCore) |
| const 공유 프래그먼트 | `FMassConstSharedFragment` 상속 필요 (§9.2 는 `FMassSharedFragment` 로 적혀 있다) |
| 트레잇에서 엔티티 매니저 | `UE::Mass::Utils::GetEntityManagerChecked(World)` |
| `EAutomationTestFlags` | `EAutomationTestFlags_ApplicationContextMask` 형태 |
| 테스트에서 프로세서 직접 실행 | `Context.SetExecutionType(EMassExecutionContextType::Processor)` 없으면 어설션 |
| **속도를 위치에** | `UMassApplyMovementProcessor` 는 `FMassDesiredMovementFragment` + `FMassCodeDrivenMovementTag` 를 **둘 다** 요구한다. 없으면 쿼리에 안 걸려 좌표가 영영 그대로다 (오류 없이 조용히). `UEcoSteeringProcessor` 가 직접 적분하는 이유 — 그 프래그먼트를 넣으면 엔진 가감속 모델을 타서 §3.3 의 "속력 일정" 계약과 어긋난다 |
| 트레잇과 엔진 이동 트레잇 | `UMassMovementTrait` 는 기본값(`bIsCodeDrivenMovement = true`)에서 `FMassCodeDrivenMovementTag` 를 붙인다. 초식 트레잇이 `FMassCustomMovementTag` 를 붙여 엔진 이동 프로세서를 막는다 — 없으면 두 트레잇을 같이 쓸 때 이동이 이중으로 적용되거나 속도가 덮어써진다 |
| `Build.cs` 의 `StructUtils` | 아직 동작하지만 `uproject` 에 플러그인 의존이 없다는 경고가 난다 |
