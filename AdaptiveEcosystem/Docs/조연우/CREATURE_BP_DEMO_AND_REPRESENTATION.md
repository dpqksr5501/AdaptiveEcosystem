# 늑대·초식동물 BP 표현과 이동 시연

> 2026-10-05 · UE 5.8 · 테스트 표현/연결 작업
> 실제 동물 모델이 없어 임시 표현으로 먼저 구현한다는 사용자 선택을 반영했다.

## 1. 구현 범위

공통 `AEcoCreatureRepresentationActor`와 늑대/초식동물 자식 클래스는 **Mass 상태를 받아 표시하는 Actor**다.
CharacterMovement, AIController, 실제 이동 적분, Legacy Evolution Profile을 사용하지 않는다.
Mesh 교체 전에는 길쭉한 늑대 박스/큰 초식동물 박스와 서로 다른 색의 이름표를 표시한다.

`AEcoCreatureDemoSpawner`는 기존 `AEcoPolicyTestSpawner`를 재사용하는 **Standalone 평면 시연**이다.
초식동물은 기존 PPO/Steering, 늑대는 기존 테스트 배회·추격 규칙으로 움직인다.
늑대 PPO, 실제 지형 경로, production EntityConfig/지역 자원/Vitals 폐루프, Social 목적지 소비,
M3 이주 및 멀티플레이 통합 완료를 의미하지 않는다.

```text
초식동물: 기존 Perception → Policy → Steering (PrePhysics 위치 작성)
늑대: 기존 TestSpawner.MovePredators (PostPhysics 위치 작성)
                      ↓ 각 개체에 작성자 하나
DemoSpawner가 완료 위치/속도/ID를 읽음 → VisualState → 종별 BP/AnimInstance
```

동일 개체에 엔진 Movement 또는 BP AI MoveTo를 추가하지 않는다.
M3 Bootstrap 가드와 PPO CustomMovement Tag, 정책 7→4 사양·가중치·수식은 유지했다.
새 코드는 Social ModulatedAction이나 인지 정보를 몰래 Policy 대신 소비하지 않는다.

## 2. 생성 에셋과 실행

생성·저장된 다음 Content 경로를 사용한다.

| 에셋 | 부모/용도 |
| --- | --- |
| `/Game/Creatures/Demo/BP_EcoWolf` | `EcoWolfRepresentation`, 임시 늑대 표현 |
| `/Game/Creatures/Demo/BP_EcoHerbivore` | `EcoHerbivoreRepresentation`, 임시 초식동물 표현 |
| `/Game/Creatures/Demo/BP_EcoCreatureDemoSpawner` | `EcoCreatureDemoSpawner`, 표현 클래스 지정·8 초식/1 늑대 |
| `/Game/Creatures/Demo/L_EcoCreatureDemo` | 전용 바닥·조명·PlayerStart·Spawner 테스트 맵 |

1. 빌드 완료 후 에디터에서 `L_EcoCreatureDemo`를 연다.
2. Net Mode를 Standalone으로 설정하고 Play한다. 기본 GameModeBase의 관찰용 Pawn으로 이동한다.
3. 초식동물과 늑대의 위치 변화, 진행 방향, 이름표의 개체 ID를 확인한다.
4. `eco.UseLearnedPolicy 1`은 학습 정책, `0`은 기존 Utility 비교군이다. 이 콘솔 값의 현재 상태는 기존 `[Eco]` 로그로 확인한다.
5. Spawner Details에서 개체 수/종별 Actor Class를 바꿀 수 있다. 총 개체 수 상한은 128이다.
6. Spawner는 `(0,0,0)`에 둔다. 기존 Dummy 경계는 원점 중심이고 경로/지형 검증을 제공하지 않는다.

시연은 포획된 초식동물을 기존 정책 테스트 규칙대로 즉시 reset한다.
이 reset은 같은 테스트 개체의 상태 초기화이며 정식 사망·출생·개체군 변경이 아니다.
reset 시 표현에 discontinuity를 전달해 예전 위치에서 회전 보간하지 않는다.
일반 이동은 실제 위치를 그대로 표시하며 방향만 부드럽게 회전한다.
정지 시 마지막 방향을 유지하고 첫 배치/큰 순간 이동은 방향도 즉시 적용한다.

기본 PPO는 일정 속력이므로 초식동물의 정지/걷기/달리기 선택이 학습된 것처럼 해석하지 않는다.
애니메이션 Run/Walk는 실제 속도로 **표시**한 결과다. 학습 속도 선택은 V2 계약 작업이다.
늑대 Eating 입력은 기존 포획 cooldown이며 실제 영양 자원 모델이 아니다.
기존 늑대는 cooldown 중에도 배회할 수 있으므로 Eating 동작 표시는 정지했을 때만 선택한다.

## 3. 모델·AnimBP 교체

각 BP의 `CreatureMesh`에 Skeletal Mesh를 지정한다. Mesh가 있으면 PlaceholderBody가 숨겨진다.
동물 에셋에 맞춰 **Mesh 컴포넌트**의 상대 위치·회전·크기를 조정한다. 논리 Mass 위치/속도를 수정하지 않는다.
발이 바닥에 닿는 높이와 Mesh의 전방 축을 모델별로 맞춘다.

모델의 Skeleton을 선택해 AnimBP를 만들고 부모를 `EcoCreatureAnimInstance`로 지정한다.
실제 Skeleton/동작 에셋이 없으므로 이번에는 동물 전용 AnimBP/BlendSpace를 생성하지 않는다.
부모는 Actor 소유자를 읽으며 `TryGetPawnOwner`가 필요 없다.

| 애니메이션 입력 | 의미 |
| --- | --- |
| `SpeedCmPerSecond` | 수락된 실제 XY 속도, cm/s |
| `DirectionDegrees` | 표현 방향 기준 이동 방향 |
| `VisualMotion` | Idle/Walk/Run/Eating/Dead 시각 상태 |
| `bAlive`, `bEating`, `bPursuingPrey` | 제공받은 생존/쿨다운/추격 상태 |

Root Motion은 부모 초기화에서 IgnoreRootMotion으로 설정한다.
애니메이션은 in-place로 준비하고 BP에서 별도로 위치 이동·Root Motion 적용·물리 시뮬레이션을 켜지 않는다.
Actor의 `GetVelocity()`도 같은 읽기 전용 속도를 반환한다.
BP `OnVisualStateUpdated` 이벤트는 표시/연출만 갱신한다.

## 4. 데이터와 생명주기

Source: [표현 Actor](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureRepresentationActor.h),
[VisualState](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureVisualState.h),
[AnimInstance](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureAnimInstance.h),
[시연 브리지](../../Source/AdaptiveEcosystem/Debug/EcoCreatureDemoSpawner.cpp).

- ID는 권위 `EcologySimulationSubsystem.AllocateStableAgentId`로 발급해 테스트 Mass Identity Fragment에 기록한다.
  지역 Population 등록/자원 소비/Network 스폰 요청을 우회해 production 개체를 만드는 API는 아니다.
- Actor는 ID/Species를 한 번 바인딩하며 다른 개체의 값으로 조용히 덮어쓰지 않는다.
- 수락할 VisualState는 같은 ID/Species, 증가한 Sequence, 되감기 없는 WorldTime 및 유한한 위치/속도/비율을 요구한다.
- VisualState는 별도 표현 입력이다. 기존 Core/Network DTO에 필드를 추가하거나 Replicated Actor 경로를 만들지 않았다.
- `bHasVitals=false`는 HP/Energy 값이 제공되지 않았다는 뜻이다. 테스트 늑대에는 Vitals가 없으므로 건강/에너지를 추정하지 않는다.
- Mass 개체가 삭제되면 다음 브리지 패스에서 대응 Actor를 해제/삭제한다.
- Spawner EndPlay는 먼저 표현을 삭제하고 기존 Spawner가 소유한 Mass 개체를 정리한다.
- `RebuildVisuals`는 기존 표현을 정리한 뒤 다시 연결한다. 중복 표현을 남기지 않는다.
- Actor만 삭제해도 Mass 개체는 삭제되지 않는다. 필요한 경우 RebuildVisuals로 다시 표현한다.
- 새 시연 Spawner는 Standalone에서만 실행한다. Client/Listen/Dedicated에서 자체 논리 개체/표현 복제 경로를 만들지 않는다.
- 기존 TestSpawner에는 opt-in ID 구성, read-only 조회, reset 알림 및 Client 스폰 제외만 추가했다.
  기존 테스트 행동/추론/포획 수식은 그대로다.

## 5. 에셋 생성 도구

[create_creature_demo.py](../../Tools/Editor/create_creature_demo.py)는 **Editor 전용** 도구다.
게임 Python 추론/런타임 서비스가 아니다. PythonScriptPlugin/EditorScriptingUtilities는 해당 에디터 실행의
`-EnablePlugins`로만 켜며 `.uproject`의 런타임 플러그인 설정은 바꾸지 않는다.
기존 에셋/맵은 재사용하고 기존 기본값/맵 내용을 덮어쓰지 않는다.
생성 결과는 로컬 `Saved/CreatureDemoAssets.json`에 기록한다.
원래 JYU 맵과 기존 GameDefaultMap/EditorStartupMap은 수정하지 않는다.

## 6. 검증 상태와 다음 인계

2026-10-05 검증 기록:

- 직접 UBT Editor Development 빌드 성공: 초기 83.97초, 테스트 주기/종료 조건 수정 후 18.24초.
- 표현 3 + Policy 9 + Social 17 자동화 **29 성공 / 0 실패 / 테스트 경고 0**.
  첫 실행의 28 성공 / 1 실패는 새 fixture가 PolicyInterval 전에 위치를 비교하고 game loop 없는 월드에서 Destroy만 사용했던 문제였다.
  실제 추론 주기와 명시적 EndPlay를 반영한 뒤 통과했다. 정책/이동 수식은 바꾸지 않았다.
- Editor API로 BP 3개/맵 1개 생성·저장. GeneratedClass와 맵 존재 확인 결과는 `Saved/CreatureDemoAssets.json`.
- 저장된 `L_EcoCreatureDemo`를 `-game -NullRHI -benchmark -FPS=60 -Seconds=7`로 실행해 정상 종료 확인.
  `[Eco] 정책=학습 | 개체 8, 이동 8 ... 포획 1`을 확인했다. 이것은 렌더링/애니메이션 시각 검증과 구분한다.
- 실제 저장 BP GeneratedClass를 로드하도록 fixture를 확장한 뒤 직접 UBT 재빌드 성공(4.95초).
  표현 자동화 **3 성공 / 0 실패 / 테스트 경고 0**. BP 종별 바인딩, PPO/추격 이동 반영, 중복 방지와 삭제/종료 정리를 확인했다.
  보고서: `Saved/Automation/CreatureBlueprintVerified/index.json`.
- 로컬 로그: `Saved/Logs/CreatureVisualBuild.log`, `CreatureVisualRebuild.log`, `CreatureVisualVerified.log`,
  `CreatureDemoAssetGeneration.log`, `CreatureDemoGameSmoke.log`, `CreatureBlueprintTestBuild.log`, `CreatureBlueprintVerified.log`.

실제 화면의 동물 모델/애니메이션/발소리, 지형 경로와 Client 표현은 별도 검증한다.

| 후속 담당 | 작업 |
| --- | --- |
| 표현/콘텐츠 | 모델·Skeleton·AnimBP 교체, 축/발 높이/크기 및 LOD 확인 |
| 이동 | 실제 지형의 경로·경사·장애물 처리, Social Request/Feedback 소비, 단일 writer 유지 |
| RL | V2 속도/행동 계약, 감각 입력·학습 환경 정합성, 포식자 학습이 필요하면 별도 계약 |
| 조연우 | 감각/경보/예약 결과 연동, 서버 gameplay 소음과 로컬 SA 연결 |
| Mass/Network | production EntityConfig·ID/생명주기와 기존 복제/LOD 표현 연결 |

새 표현 BP를 기존 M3 Box EntityConfig에 단순 결합해 PPO 이주 통합이 됐다고 가정하지 않는다.
production에서는 기존 Mass Representation과 새 Actor가 같은 개체를 중복 표시하지 않도록 연결 담당자가 하나의 표현 경로를 선택한다.
