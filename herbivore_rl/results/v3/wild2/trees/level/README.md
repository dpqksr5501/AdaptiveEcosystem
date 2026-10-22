# 레벨 나무 (10-18) — Play 때 띄우지 않고 통합 레벨에 진짜 액터로

사용자 요청(10-18): "일단 플레이시 장애물이 생성되게 하지 말고 그냥 우리 통합레벨에 배치를 해 테스트하는 레벨에."

10-17 에는 통합 v3 모드가 Play 할 때마다 배치 표(`../tree_layout.json`, `trees-1017a`)대로 나무를 띄웠다(`eco.IntegratedV3.StageTrees`).
이제 같은 나무가 `/Game/Map/LV_Ecosystem_IntegrationTest` 에 진짜 액터로 있다. 사용자가 이 레벨 편집을 허락했다. 우리 액터만 더했고, 팀 액터와 맵 파일은 그대로다.

## 한 줄 결론

- 숲 24·고지 9·메마른 땅 0 그루. 자리·방향·크기·땅 묻기(가장 낮은 땅보다 10 cm)는 10-17 실행 중 나무와 같다.
- 레벨 읽기가 읽은 줄기 원판 = 배치 표 = 10-18 실행 중 나무 판의 원판이다. 지도 9장 모두 비트 단위로 같다.
- 헤드리스 240초 세 판의 기록 줄이 실행 중 나무 판과 모두 같다(나무를 놓는 길 때문에 바뀌는 줄만 빼고). 그래서 사슴·늑대 결과도 같다.
- 팀 이동 제약은 줄기에서만 막는다. 줄기 가로지르기 33/33 이 막히고, 잎 아래 둘레 걸음 396 은 하나도 막히지 않는다.
- 화면도 같다. 10-17 사진과 화소 평균 차이가 0.35~2.1 / 255 이고, 줄기 막이는 보이지 않는다.

## 무엇을 놓았나

나무마다 액터 둘. 월드 아웃라이너 폴더는 `EcoV3_Trees`, 늘 불림(공간 스트리밍 안 함)이다.

| 액터 | 메시 | 충돌 | 보임 | 꼬리표 |
|---|---|---|---|---|
| `EcoV3Tree_<지역>_<번호>` | 팀 `Beech_Tree`(애셋 그대로) | 없음(이 액터만) | 보임, 그림자 켬 | `EcoV3Tree`, `EcoV3TreeId_<지역>_<번호>` |
| `EcoV3Trunk_<지역>_<번호>` | 엔진 `/Engine/BasicShapes/Cylinder` | `BlockAll` | 게임에서 숨김, 그림자 없음 | `EcoV3Trunk`, `EcoV3TreeId_<지역>_<번호>` |

- 줄기 막이는 나무 액터에 붙어 있다. 그래서 나무를 옮기면 따라간다.
- 반지름은 줄기 원판 반지름(밑동 꼭짓점 반경 40.45 cm × 크기 = 0.74~0.89 m)이다. 원기둥의 충돌 상자가 ±50 cm 라서 크기 = 반지름 ÷ 50 이다. 높이는 땅 − 30 cm ~ + 4 m.
- 내비 메시에는 영향이 없다(팀 내비 데이터를 바꾸지 않으려고).
- 나무 메시 충돌을 끈 까닭: `Beech_Tree` 의 단순 충돌은 잎까지 덮는 볼록 하나(28 × 27 × 25 m)다. 그대로 두면 줄기에서 8~13 m 떨어진 빈 땅이 막힌다(`../../level_shc/README.md`).
- 새로 생긴 파일: 외부 액터 66 개(`AdaptiveEcosystem/Content/__ExternalActors__/Map/LV_Ecosystem_IntegrationTest/…`), 폴더 1 개(`…/__ExternalObjects__/…`). 맵 파일(`.umap`)은 그대로다.

## 놓는 법·옮기기·지우기

편집기를 닫고 우리 모듈의 편집기 전용 명령을 쓴다(`AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoV3PlaceTreesCommandlet.{h,cpp}`).

```
UnrealEditor-Cmd.exe <uproject> -run=EcoV3PlaceTrees -unattended -nopause -nosplash      # 놓기·고치기
    -DryRun     # 계산과 확인만 (저장 안 함)
    -Remove     # 우리 액터(꼬리표 EcoV3Tree·EcoV3Trunk)와 폴더를 지움
    -Force      # 같아도 다시 저장
    -Map=<맵>   # 기본 /Game/Map/LV_Ecosystem_IntegrationTest
```

- 하는 일:
  - 맵과 모든 액터를 불러 온다.
  - 통합 모드와 같은 규칙으로 무대 원점을 찾는다(`StageCenterCm` — 조정자 그룹의 먹이 자리, 지역 상자 안, 높이 = 중심 지면).
  - 같은 지면 검사(`GroundStageTree`)로 놓는다.
  - 끝에 레벨 읽기로 원판이 표와 같은지 확인한다. 다르면 저장하지 않는다.
- 다시 돌려도 우리 꼬리표 액터만 고친다. 이미 같으면 저장하지 않는다(두 번째 실행: 그대로 66, 저장 0, 파일 바이트 그대로).
- 편집기에서 나무를 옮기면 통합 모드 시작 줄에 '표와 다름'이 뜬다. 그 줄기는 읽은 자리 그대로 원판이 된다. 파이썬 거울과 원판이 달라지니 배치 표를 다시 만든다.
- 지우기: 아웃라이너에서 폴더 `EcoV3_Trees` 를 지우고 저장하거나, `-Remove`. 지운 뒤에도 v3 모드에서 나무를 보려면 `-EcoV3StageTrees=1`(예전처럼 실행 중에 놓기).

## 언리얼에서 바뀐 것

`AI/Policy/EcoPolicyV3IntegratedSubsystem.{h,cpp}`

- `eco.IntegratedV3.StageTrees` 기본 0. 1 은 예비다 — 레벨 나무가 없는 무대에만 실행 중에 놓는다. 레벨 나무가 있는 무대는 켜도 놓지 않는다(두 번 놓지 않게).
- 레벨 읽기(`ScanStageObstacles`)는 꼬리표 `EcoV3Trunk` 원판을 레벨 나무로 센다. 그 지역 배치 표 줄기와 중심·반지름 모두 1 cm 안이면 표 값을 그대로 쓴다(`SnapToLayout`).
  읽은 값과 표의 차이는 최대 3.3e-12 cm 였다. 맞춘 수·다른 수·차이 최대를 기록한다. 파이썬 거울(`tree_layout.json`)과 비트 단위로 같게 하려는 것이다.
- 시작 자리 계획(`PlanStage`)은 같은 레벨 줄기 원판을 피한다(`GatherLevelTrunks` → `LevelTrunkDiscs`). 스트리밍 전 계획에도 쓴다(늘 불린 액터라 그때도 있다).
- 무대를 만들 때 나무마다 팀 이동 제약을 재 본다(`ProbeLevelTrunks`, 기록만): 줄기를 가로지르는 걸음과, 줄기 가장자리 + 1.3 m 둘레를 30° 마다 도는 30 cm 걸음.
- 시작 줄: `[EcoV3I] <지역> 나무 | 레벨 나무 줄기 n … 배치 표 … 맞춤 n … 세계 원판 = 표 · 시작 자리가 피한 원판 n 은 세계 줄기 원판과 같다 | 이동 검사(팀 ConstrainStep): … | 실행 중 나무 놓지 않음`.
  10초 일곱째 줄의 원판 출처는 `레벨 나무 n + 그 밖 레벨에서 읽음 n`. 원판 내보내기에 `level_trees_on`·`level_tree_discs`·`level_trees_snapped`·`level_trees_unmatched`·`level_tree_max_snap_cm`·`plan_trunk_discs`·`trunk_probe`.
- 왜 줄기 막이가 v3 이동을 더 막지 않나: v3 세계는 사슴·늑대 중심을 줄기 원판 + 몸 30 cm 밖에 둔다. 미끄러짐은 원판에 닿은 자리의 접선을 따라가서, 이동 선도 그 둘레 밖이다.
  팀 이동 제약은 반경 30 cm 구로 쓸어 보므로 반지름 R 원기둥에 닿지 않는다. 헤드리스 세 판에서 실제로 한 번도 더 막히지 않았다(기록 줄이 같다).

## 확인

`python results/v3/wild2/trees/level/compare_level.py --sessions 20000-20002` → `compare_level.json`

- 언리얼 헤드리스: 통합 레벨, 기본값(레벨 나무 + 날씨), 사슴 128, 240초, 세션 20000~20002. 기록 `unreal_logs/`(`../../../wild1/trim_unreal_log.py` 로 고름), 내보내기 `unreal_exports/`.
- 견줌: 10-18 실행 중 나무 판(`results/v3/wild3/unreal_logs`·`unreal_exports`, 같은 세션 — 그때 기본값 = 실행 중 나무 + 날씨).

| 칸 | 결과 |
|---|---|
| 세계 원판 = 배치 표 = 앞 판 원판 (모든 칸 `float.hex`) | 지도 9장 모두 같음 (숲 24 · 고지 9 · 메마른 땅 0) |
| 레벨 줄기 원판 = 표, 시작 자리가 피한 원판 = 표 | 같음 (맞춤 33, 다름 0, 차이 최대 4.3e-12 cm) |
| 무대 원점 · 은신처 원 · 날씨 | 앞 판과 같음 |
| 기록 줄 | 1662 줄 모두 같음 (시각·CPU 칸 빼고). 따로 센 줄: 설정 '무대 나무:' 1, 시작 '장애물 \|' 3·'나무 \|' 2, 명령줄·내보내기 경로 2 — 판마다 |
| 이동 검사 (팀 ConstrainStep) | 줄기 가로지르기 숲 24/24·고지 9/9 막힘(모두 줄기 막이에 닿음), 잎 아래 둘레 걸음 288·108 막힘 0 |
| EcoV3I 경고·오류, 다른 Error·Ensure | 0 · 0 |

- 놓기 명령 확인(편집기 월드): 무대 원점 숲 (28200, 40500, −1631)·고지 (28000, −55000, 2640) = 통합 모드와 같음, 밑동 아래 땅 높낮이 최대 숲 19.9 cm·고지 5.1 cm(실행 중 나무 판 19.9·5.1 cm), 레벨 읽기 원판 = 표.
- GPU 사진 `shots/`(세션 20000, `-EcoV3Weather=0` — 10-17 사진과 같은 세계, 1920×1080 을 1280×720 으로 줄임): 10-17 실행 중 나무 사진 `../shots/` 와 화소 평균 차이(0~255)

| 사진 | 10-17 사진과 차이 | 무엇 |
|---|---|---|
| `shots/forest_top.png` | 1.15 (32 넘게 다른 화소 0.11%) | 숲 무대 위에서 |
| `shots/forest_ground_debug.png` | 2.06 (0.27%) | 은신처 곁 3 m 높이, 디버그 — 줄기 밑동에 초록 원 |
| `shots/highland_ground.png` | 0.35 (0.001%) | 고지 낮은 자리 |

  다시 찍기: `UnrealEditor.exe <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3Seed=20000 -EcoV3Weather=0 -EcoV3Film=lvtrees -EcoV3FilmOut=<폴더>
  "-EcoV3FilmShots=Forest,top,0,9,0.2,,,,0;Forest,shelter,2,15,0.2,20,3,315,1;Highland,wide,0,18,0.2,20,4,300,0" -benchmark -fps=30 -seconds=22 -windowed -ResX=1920 -ResY=1080 -NoSound -nosplash -DisablePlugins=Bridge,Fab`
  (장면마다 마지막 장 = f_00005·f_00011·f_00017). 차이 수는 `shots/diff_vs_runtime_trees.json`, 장면 기록은 `shots/film_shots.json`.
- 시험: `Policy.V3.StageTrees.LevelActors`(새)·`Layout`·`StartPoints`. 자동 시험 172 모두 성공(기존 경고 1 포함), 실패 0. 빌드 두 방식 통과.

## 남은 것

- 팀 v1 동물은 길 찾기가 없어서 줄기 앞에서 그 걸음이 멈출 수 있다(v3 사슴·늑대는 줄기를 돌아간다). 팀에 알렸다(`AdaptiveEcosystem/Docs/RL_Policy/TEAM_REQUESTS_V3.md` 7절).
- 공식 레벨이 정해지면 같은 명령(`-Map=`)으로 옮겨 놓을 수 있다. 그 맵에 조정자·지역이 있어야 한다.
- 잎이 은신처 가장자리 위로 드리우는 것은 10-17 그대로다(`../README.md` 6절).
