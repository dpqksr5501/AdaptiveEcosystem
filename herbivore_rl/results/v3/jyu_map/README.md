# 팀 생태계 맵의 우리 복사본 (10-25) — `/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem`

사용자 지시(10-24): "그 사람 레벨디자인을 그대로 복사해와서 우리 레벨에서 테스트하자 — 우리가 하던 방식의 테스트를 그사람 맵을 받아와서".

원본은 조연우 님 `/Game/JYU/Maps/LV_JYU_Ecosystem` 이다(설명: [JYU_ECOSYSTEM_BP_SETUP_20261023.md](../../../../AdaptiveEcosystem/Docs/Architecture/JYU_ECOSYSTEM_BP_SETUP_20261023.md)).
원본 맵·팀 에셋·C++·게임 기본 두뇌(R1b-F)·기본 설정은 바꾸지 않았다.

## 한 줄 결론

- 원본을 우리 폴더에 그대로 복사했다. 액터 설명 185(편집기 액터 121 + HLOD 액터 64)·외부 개체 11 이다. 편집기 액터 121 의 꼴·이름·자리·방향·크기·꼬리표·폴더·컴포넌트·메시가 원본과 모두 같다. 은신처 장식 인스턴스(풀 183·돌 20 × 12)의 높이도 같다.
- 같은 인수로 헤드리스를 돌리면 원본과 기록 줄이 같다(팀 날씨 감시를 끈 판 기준. 판마다 새로 뽑는 세션 epoch 와 디버그 등록 줄 순서만 다름).
- 레벨 설정은 바꾸지 않았다. 팀 기능을 끄고 켜는 것은 실행 인수로 한다. 그래서 '대조 모드'와 '전체 모드' 두 가지로 띄운다.
- (복사 때 기록 — 바로 아래 후속 줄로 풀림) 팀 식생(soil-v1)은 끄는 실행 인수가 없다. 그래서 아래 처음 대조 모드 인수만으로는 240초 스냅숏이 거부됐다(`[EcoVegetation] RL snapshot v1 rejected`). 그때는 파이썬 거울과 견주는 시험을 이 맵으로 할 수 없었다(아래 '남은 것' 1).
- **10-25 후속 — 식생은 실행 때만 끈다.** 엔진 콘솔 명령 `setnopec EcoCreatureIntegrationSpawner bEnableVegetation False` 를 대조 모드 `-ExecCmds` 에 더하면 이 Play 의 조정자 값만 꺼진다(맵 파일·C++ 그대로). 그러면 240초 스냅숏이 써지고 파이썬 거울과 견줄 수 있다. 결과와 실행 명령은 [`../level_jyu_eco/README.md`](../level_jyu_eco/README.md) 에 있다. 아래 '남은 것' 1·2 는 그 전의 기록이다.

## 만든 방법

- [`copy_map.py`](copy_map.py) 를 편집기 파이썬으로 돌렸다. 팀 도구(`AdaptiveEcosystem/Tools/Editor/setup_jyu_ecosystem.py` 등)와 같은 `LevelEditorSubsystem.new_level_from_template(대상, 원본)` 이다.
  - 원본을 이름 없는 새 패키지로 불러(템플릿) 대상 경로로 저장한다. 원본 패키지는 저장하지 않는다.
  - 대상이 이미 있으면 거절한다. 다시 만들 때는 대상 맵과 외부 파일을 먼저 지워야 한다.
- 실행: `UnrealEditor-Cmd.exe <uproject> -unattended -nop4 -nosplash -NullRHI -ExecutePythonScript=<copy_map.py> -CopyOut=<보고 json>` (약 20초).
- 그 뒤 맵 패키지에 출처 표식 메타데이터만 더해 맵 파일 하나를 다시 저장했다.
  - 더한 표식: `EcoV3Owner=EcoTest.JYUEcosystemCopy.20261025`, `EcoV3CopySource=/Game/JYU/Maps/LV_JYU_Ecosystem`.
  - 원본에서 함께 온 팀 표식 `JYUOwner=JYU.Ecosystem.SoilV1.20261023` 은 지우지 않았다.
- 새 파일:
  - `AdaptiveEcosystem/Content/EcoTest/Maps/LV_EcoV3_JYUEcosystem.umap`
  - HLOD 층 사본 `AdaptiveEcosystem/Content/EcoTest/Maps/LV_EcoV3_JYUEcosystem_LV_JYU_Ecosystem_LV_JYU_HerdMigration_LV_Ecosystem_IntegrationTest_HLOD0_Instancing.uasset` (템플릿 복사가 맵마다 하나씩 만든다)
  - 외부 액터 185 개 `AdaptiveEcosystem/Content/__ExternalActors__/EcoTest/Maps/LV_EcoV3_JYUEcosystem/…`
  - 외부 개체 11 개 `AdaptiveEcosystem/Content/__ExternalObjects__/EcoTest/Maps/LV_EcoV3_JYUEcosystem/…`
- 우리 것은 아무것도 더 놓지 않았다. 팀 맵에는 나무가 없어서 줄기 막이를 붙일 나무도 없다(아래 '맵 구성').

## 맵 구성 (원본 그대로)

| 항목 | 값 |
|---|---|
| 지역 | 3 곳: Barren(지역 번호 0) · Forest(1) · Highland(2). 모두 1500 × 500 m 상자, 중심 y 0 / 50000 / −50000 |
| v3 무대 (`-EcoIntegratedV3`, 한 변 120 m) | 원점 Forest (28000, 26000, −1286) · Barren (28000, 12000, 170) · Highland (28000, −55000, 2640). 무대 중심 = 조정자 먹이 자리 |
| 사슴·늑대 | `-EcoIntegratedV3` 이면 지역마다 사슴 128·늑대 4. 이 인수 없이 Play 해도 조정자 `bUseV3Policy=true` 라 v3 로 돌고, 사슴은 조정자 값 48 이다 |
| 은신처 | `BP_JYU_ProtectedRefuge` 12 개(지역마다 4, 반지름 12 m, 자리 4·슬롯 4). 무대 기준 (15,15)·(45,15)·(15,45)·(45,45) 단위, 반지름 6 단위 = 파이썬 거울 은신처와 같다 |
| 나무 | 0 그루. 꼬리표 `EcoV3Tree`·`EcoV3Trunk` 0, 충돌하는 스태틱 메시 0. 폴리지 액터 1 개는 비어 있다 → 무대 원판 0 / 0 / 0 |
| 날씨 | `BP_JYU_EcosystemWeather` 3 개: 비 180 초 순환, 비 0.65, 위상 Forest 0 · Barren 30 · Highland 60 초 |
| 식생·life·이주 | 조정자 `bEnableVegetation`·`bEnableEcosystemLife`·`bEnableHerdJourneys` = 켬. 서식지 BP 9 + 샘물 1, 이주 경로 Barren↔Forest 1 개(140 m) |
| 게임 모드·몸 | `BP_JYU_IntegrationGameMode`, `BP_JYU_Deer`·`BP_JYU_Wolf` |

## 두 모드

Git Bash 에서는 `/Game/...` 가 윈도 경로로 바뀌지 않게 `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"` 를 먼저 둔다(PowerShell 은 그대로).
`<UE>` = `C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe`, `<uproject>` = `AdaptiveEcosystem/AdaptiveEcosystem.uproject` 절대 경로.

### 전체 모드 — 팀 기능 모두 켬 (언리얼만)

```
<UE> <uproject> /Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem -game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=20010 \
  -benchmark -fps=30 -seconds=241 -NullRHI -NoSound -unattended -nosplash -nopause -DisablePlugins=Bridge,Fab -abslog=<기록>
```

- 맵에 저장된 그대로다. 식생 soil-v1·life(자연 출생·사체·사냥 상한·개체별 속력/크기)·무리 이주·팀 비 순환이 모두 돈다.
- 팀 비 순환은 우리 환경 감시(`eco.IntegratedV3.EnvWatch` 1)가 v3 지역 날씨로 옮긴다.
- 스냅숏은 거부된다. 파이썬과 견주지 않는다.
- 같은 시드여도 판마다 조금 다르다. 환경 감시가 실시간 1 초마다 팀 날씨를 읽기 때문이다. 원본 맵을 같은 인수로 두 번 돌려도 19초쯤부터 갈라졌다(팀 날씨 바뀜이 들어가는 결정 스텝이 판마다 다름).
- 편집기에서 맵을 열고 Play 하면 이 모드다. 다만 `-EcoIntegratedV3` 가 없으므로 사슴은 지역마다 48 이다.

### 대조 모드 — 우리 v3 규칙 + 이 맵의 지형·은신처·나무(없음)·시작 날씨, 팀 life·이주·날씨 바뀜·식생 끔

```
<UE> <uproject> /Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem -game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=20010 \
  -EcoEcosystemLife=0 -EcoV3EnvWatch=0 "-ExecCmds=eco.HerdMigration 0, setnopec EcoCreatureIntegrationSpawner bEnableVegetation False" \
  -EcoV3SnapshotAt=240 -EcoV3SnapshotOut=<스냅숏 json> \
  -benchmark -fps=30 -seconds=241 -NullRHI -NoSound -unattended -nosplash -nopause -DisablePlugins=Bridge,Fab -abslog=<기록>
```

| 인수 | 끄는 것 | 확인 |
|---|---|---|
| `-EcoEcosystemLife=0` | 팀 life (조정자 BeginPlay 가 읽음) | `[EcoLife]` 줄 0 (전체 모드는 출생·사체 줄이 나옴) |
| `-EcoV3EnvWatch=0` | 팀 날씨 BP 가 바꾸는 날씨를 v3 로 옮기기. v3 날씨는 시작값 Forest 비 1 · Barren 맑음 · Highland 눈 1 로 고정(= 파이썬 `configs/v3_wild3_mirror.yaml`) | 240초까지 v3 날씨 그대로 |
| `"-ExecCmds=eco.HerdMigration 0"` | 무리 이주 새 출발 (팀 콘솔 변수 — 0 프레임에 들어감, 무대는 8 프레임에 만들어짐) | `eco.HerdMigration = "0"`, 이주 줄 0 |
| `setnopec EcoCreatureIntegrationSpawner bEnableVegetation False` (같은 `-ExecCmds` 안, 10-25 후속) | 식생 soil-v1 (이 Play 의 조정자 값만 — 맵 파일·C++ 그대로) | `[EcoVegetation] Enabled` 줄 0, 스냅숏 써짐. 이 명령이 없던 처음 판은 `Enabled … Python parity pending` 이 지역마다 나오고 스냅숏이 거부됐다 |

- 위 명령은 10-25 후속 판([`../level_jyu_eco/README.md`](../level_jyu_eco/README.md))에서 쓴 대조 모드다. 아래 '확인한 것'의 대조 모드 판은 식생 끄기 명령이 없던 처음 판이다.

- 두뇌를 바꾸려면 `-EcoV3Brain=v3_r7_g995_s1_20m` 처럼 더한다(R7e 확인 때와 같다, [`../r7e/unreal_parity.md`](../r7e/unreal_parity.md)).
- 우리 맵과 같은 나무 조건이 필요하면 `-EcoV3StageTrees=1` 을 더한다. 레벨을 바꾸지 않고 Play 때 배치 표 `trees-1017a` 대로 나무를 띄운다(Forest 24 · Barren 0 · Highland 9, 충돌 없음, 줄기 원판은 세계에 넣음). 이 맵에서 확인했다.
- 레벨에 진짜 나무를 놓으려면 `-run=EcoV3PlaceTrees -Map=/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem` 이다([`../wild2/trees/level/README.md`](../wild2/trees/level/README.md)). `-DryRun` 으로만 확인했고 놓지 않았다. 66 개를 놓게 되고, 레벨 읽기 원판이 배치 표와 비트 단위로 같다고 나왔다.

## 확인한 것 (10-25, 헤드리스, 시드 20010)

- 편집기에서 원본·복사본을 따로 열어 모든 액터를 불러 견줬다. 맵 경로만 바꿔 보면 같다.
  - 다른 것은 셋뿐이다.
    - 표시용 TargetPoint 8 개(먹이 힌트 3·물 4·은신처 1)의 액터 설명 경계 상자. x 쪽 끝만 120 cm 다르고 액터 자리는 같다(편집기 표시 컴포넌트 경계로 보인다)
    - 월드 설정의 HLOD 층 경로(복사가 만든 사본을 가리킴)와 런타임 분할 개체 이름
    - 은신처 HISM 의 캐시된 경계
  - 은신처 장식 인스턴스 자리는 원본과 같다. 두 맵 모두 편집기에서 열 때 맵·액터 관련 경고·오류가 0 이다(오디오 장치·크라우드 관리자 같은 늘 나오는 줄은 뺌).
- 같은 인수 짝:
  - 대조 모드에서 이주 끄기만 뺀 판(`-EcoEcosystemLife=0 -EcoV3EnvWatch=0`, 120초): 원본·복사본 모두 생태 기록 줄 914 줄이다. 다른 줄은 판마다 새로 뽑는 세션 epoch 가 든 죽음 줄과 디버그 등록 줄 순서뿐이다.
  - 전체 모드(120초): 첫 팀 날씨 바뀜(약 13초)까지 같다. 그 뒤는 실시간 날씨 감시 때문에 갈라진다. 원본끼리 돌려도 갈라진다(위).
  - 실행 경고도 같다(맵 이름만 다름). HLOD 층 2 줄(편집기 전용 HLOD 빌더 설정 클래스 없음)과 `ABP_JYU_Deer`·`ABP_JYU_Wolf` 편집기 전용 IK 노드 3 줄이다. 둘 다 표현에만 관련된다.
- 대조 모드(240초): 지역 3·사슴 128·늑대 4, 시작 자리 지면 검사 128/128·4/4(세 지역).
  - 무대 은신처는 Forest 4 · Barren 4 · Highland 2(아래 '남은 것' 2)이다. 나무 원판은 0 / 0 / 0 이다.
  - life 0·이주 0, v3 날씨는 그대로다. 생태 경고는 스냅숏 거부 2 줄(`[EcoVegetation] RL snapshot v1 rejected`·`[EcoV3I] 환경 스냅숏을 쓰지 못했다`)뿐이다.
- `-EcoV3StageTrees=1` 을 더한 대조 모드: Forest 24 · Highland 9 그루, 원판 24 / 9(무대 나무 + 레벨 0)이다. 은신처·life·이주·날씨·경고 확인은 위와 같다.

## 남은 것 — 꺼지지 않거나 파이썬과 다른 것 (손대지 않고 그대로 둠)

1. **식생 soil-v1 끄기 인수가 없다.** (10-25 후속: 실행 인수 대신 `setnopec` 콘솔 명령으로 이 Play 만 끄는 것으로 풀었다 — [`../level_jyu_eco/README.md`](../level_jyu_eco/README.md) 2절. 아래는 그 전 기록이다.)
   - 켜지는 조건은 `Config.Vegetation.bEnabled = AEcoVegetationField::IsRequested() || Spawner->bEnableVegetation`(`EcoPolicyV3IntegratedSubsystem.cpp`)이다.
   - `eco.Vegetation`·`-EcoVegetation` 은 켜기만 한다.
   - 이 맵은 조정자에 켬이 저장돼 있어 대조 모드에서도 식생이 돈다. 칸마다 기온·빛·수분 적합도로 재생이 바뀐다.
   - 그래서 스냅숏 판 1 이 거부되고 파이썬 거울 먹이와 다르다.
   - 길은 둘이다(이번에는 하지 않음).
     - (가) life 처럼 조정자 BeginPlay 에 `-EcoVegetation=0` 덮기를 더한다. C++ 변경이라 빌드·자동 시험을 다시 해야 한다.
     - (나) 복사 맵 조정자의 식생 켬을 끈다. 레벨 설정 변경이 되고, 이 경우 전체 모드는 `-EcoVegetation` 으로 다시 켠다(다만 날씨 보기 연출 한 곳 `EcoV3WeatherPresenter` 는 조정자 값을 따로 읽는다).
2. **Highland 은신처 2 개가 늦게 등록된다.** (10-25 후속 진단 스냅숏: 늦은 둘은 (15,15)·(45,15)이고 스텝 3(0.4초)에는 넷이다 — [`../level_jyu_eco/README.md`](../level_jyu_eco/README.md) 1절 표. 아래 '어느 둘인지 확인하지 못했다'는 그 전 기록이다.)
   - 무대를 만들 때(BeginPlay 뒤 약 0.27 초, 8 프레임) Highland 은신처는 2 개만 등록돼 있다. Forest·Barren 은 4 개다.
   - 은신처 BP 는 지면이 불려 있어야 등록되고, 아니면 0.25 초마다 다시 시도한다. 무대가 지형 칸 두 개(y −50400 경계)에 걸쳐 있어 한쪽 칸이 늦게 불린 것으로 보인다. 어느 둘인지는 기록 줄이 없어 확인하지 못했다.
   - 30 초 재시도 끝의 실패 경고(`Ground registration unavailable`)는 없었다. 그러니 뒤에 등록됐고, v3 는 늦은 은신처를 원 목록 끝에 더한다(`RefreshRefuges`).
   - 파이썬 거울은 처음부터 넷이다. 그래서 Highland 시작 자리 계획과 은신처 순서가 거울과 다를 수 있다. 원본 맵도 같다.
3. **팀 날씨를 따라가는 v3 날씨는 파이썬이 받지 못한다.** 대조 모드는 시작 날씨로 고정한다. 팀 비 순환(180초·위상 0/30/60·비 0.65)을 파이썬으로 옮기려면 날씨 시간표를 받는 거울이 필요하다.
4. **나무가 없다.** 그대로 쓰면 R7e 확인 때(우리 맵, 나무 Forest 24 · Highland 9)와 세계가 다르다. 견주려면 `-EcoV3StageTrees=1` 을 쓰고, 파이썬도 같은 배치 표로 돌린다.
5. **HLOD 액터가 바탕 레벨 이름을 담고 있다 (10-25 적대적 검토에서 찾음, 원본에서 물려받음).**
   - 복사본의 외부 액터 가운데 지형 HLOD 액터(`WorldPartitionHLOD`, 지형 조각 `LandscapeStreamingProxy` 의 HLOD) 파일 48 개가 바탕 레벨 이름을 담고 있다.
     - 담은 이름: `/Game/Map/LV_Ecosystem_IntegrationTest`(지형 조각 이름)·`/Game/__ExternalActors__/Map/LV_Ecosystem_IntegrationTest/…`·HLOD 층 `/Game/Map/LV_Ecosystem_IntegrationTest_HLOD0_Instancing`
   - 원본 `LV_JYU_Ecosystem` 도 같은 파일 48 개가 같은 이름을 담는다. 복사 때 생긴 것이 아니고 팀 맵이 우리 통합 테스트 맵에서 복사될 때부터 있던 HLOD 빌드 기록이다.
   - 실행(지형·지면 검사·은신처 등록)에는 영향이 없었다. 우리 맵 `/Game/Map/LV_Ecosystem_IntegrationTest` 나 그 HLOD 층을 지우거나 이름을 바꾸면 두 맵의 HLOD 가 깨질 수 있다.
   - HLOD 를 다시 빌드하면 풀리지만 맵 파일이 바뀐다. 손대지 않았다.
