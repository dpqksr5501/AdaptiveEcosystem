# 언리얼 정책 통합 — 빌드·검증·확장 절차

`herbivore_policy_spec.md` §9 의 산출물 문서다. §은 전부 그 사양서의 절 번호.

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
| §9.8-5 지역 연동 | — | **미완** (§6 참조) |

## 2. 파일 지도

모두 `Source/AdaptiveEcosystem/AI/Policy/` 아래.

| 파일 | 역할 | 자동 생성 |
|---|---|---|
| `EcoPolicyInference.h` | §9.3 `RunPolicy`. **엔진 비의존** (`<cmath>` 만) | |
| `EcoPolicyInference.cpp` | §5.1 `RunUtilityPolicy` | |
| `EcoSteering.h` | §3.3 `Steer()`. 역시 엔진 비의존 | |
| `EcoBehaviorFragments.h` | §9.2 태그·공유 설정·기하 캐시 | |
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
| `Tests/EcoPipelineTest.cpp` | §9.8-3 파이프라인 테스트 | |

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

로그에 5초마다 `[Eco] 정책=... | 개체 N, 이동 M, 포식자 본 개체 K, 도주 F | forage ... ` 가 찍힌다.

실측 비교 (96마리, 포식자 5):

| 정책 | forage | cohesion | flee | cover |
|---|---|---|---|---|
| Utility (§5.1) | 0.34 | **0.00** | 0.39 | 0.03 |
| 학습 (PPO) | 0.58 | **0.81** | 0.18 | 0.05 |

Utility 의 cohesion 이 0인 것은 버그가 아니다. §5.1 이 `cohesion = k_coh × recent_predation`
인데 아직 아무도 피식을 보고하지 않아 EMA 가 0이기 때문이다 (§6 참조).

## 5. 이 환경에서 막히는 것 두 가지

**둘 다 우리 코드와 무관하다.**

1. **엔진 설치본에 `Bridge`(Megascans)·`Fab` 플러그인 바이너리가 없다.**
   에디터가 시작 직후 `EngineExit()` 으로 종료된다. 위 명령들이 전부
   `-DisablePlugins=Bridge,Fab` 를 다는 이유다. GUI 로 열려면 Epic Games Launcher 에서
   UE 5.8 을 복구 설치하거나 `.uproject` 에 두 플러그인을 `"Enabled": false` 로 박는다.

2. **`Content/` 에셋 144개가 UE 5.8 보다 새 엔진에서 저장돼 로드되지 않는다.**
   `OpenWorld.umap`, `BP_SkyManager`, `BP_WeatherManager` 등.
   ```
   Custom version is too new; UE5-Release: Package: 68, HeadCode: 65
   ```
   LFS 포인터 문제가 아니라 실제 에셋이고 헤더 버전이 이 엔진보다 높다.
   그래서 테스트 레벨을 `/Game/EcoTest/` 에 **새로** 만들었다 — 기존 콘텐츠에 의존하지 않는다.

## 6. 아직 안 한 것

- **§9.8-5 지역 연동.** `UEcoRegionPredationSubsystem` 은 있지만 **아무도 `ReportPredation()`
  을 부르지 않는다.** 포식자 포획 판정과 플레이어 사냥이 이걸 호출해야 `recent_predation`
  이 움직이고, 그래야 §5.1 Utility 의 cohesion·flee 항이 살아난다. 지금은 그 값이 항상 0이라
  Utility 비교군이 제 성능을 못 낸다.
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
| `Build.cs` 의 `StructUtils` | 아직 동작하지만 `uproject` 에 플러그인 의존이 없다는 경고가 난다 |
