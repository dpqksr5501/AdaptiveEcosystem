# 통합 레벨 무대 나무 (10-17)

사용자 요청(10-17): "그럼 그냥 우리 쪽 테스트 레벨에 저 사람이 만든 장애물들 적절히 배치해 봐."

팀(avaroki 님)이 만든 나무 `/Game/SHC/Fab/Realistic_Beech_Tree_3D_Vegetation/Beech_Tree` 를 우리 시험 레벨 `/Game/Map/LV_Ecosystem_IntegrationTest` 의 동물 무대에 놓았다.
**레벨·콘텐츠·설정 파일은 하나도 바꾸지 않았다.** 통합 v3 모드가 Play 할 때 고정 배치 표대로 나무를 놓고, 끝나면 사라진다(팀 은신처 덤불·바위를 실행 중에 놓는 것과 같은 방식).

## 한 줄 결론

- 숲 무대 **24 그루**, 고지 무대 **9 그루**, 메마른 땅 **0 그루**. 은신처 4 곳·무대 가운데 빈터·늑대 시작 모서리·무대 벽 곁은 비웠다.
- 나무는 충돌이 없다(메시 그대로). 대신 줄기 굵기만큼의 원판(반지름 **0.74~0.89 m**)이 v3 세계의 장애물이 되어 사슴·늑대가 줄기를 돌아간다. 눈길도 가린다.
- 파이썬 거울이 같은 원판을 쓴다(`configs/v3_wild2_trees_mirror.yaml`, 지역마다는 `tree_layout.json`). 숫자는 비트 단위로 같다(시험으로 확인).
- 화면 확인(GPU 실행 사진 `shots/`): 나무가 땅에 서 있고, 줄기 원판(초록 디버그 원)이 줄기 밑동에 맞고, 은신처 안에 줄기가 없다. 잎은 은신처 가장자리 위로 드리운다.
- 끄기: Play 전에 콘솔 `eco.IntegratedV3.StageTrees 0`, 또는 명령줄 `-EcoV3StageTrees=0`.

## 1. 어디에 무엇을 놓았나

![무대 셋 배치](tree_layout.png)

| 무대 | 그루 | 줄기 중심 간격 | 줄기 원판 반지름 | 원판 넓이 | 근거 (요약) |
|---|---|---|---|---|---|
| 숲 (Forest) | 24 | 9.0 m 밖 (가장 좁은 틈 7.7 m) | 0.74~0.89 m | 무대의 0.33% | 실제 온대 성숙림 줄기 단면적 34 m²/ha ÷ 이 나무 밑동 2.06 m² = 1 ha 16.5 그루 → 1.44 ha 에 24 |
| 고지 (Highland) | 9 | 14.5 m 밖 (가장 좁은 틈 14.0 m) | 0.75~0.88 m | 0.13% | 나무 한계선 가까운 성긴 숲으로 보고 숲의 3/8 (어림) |
| 메마른 땅 (Barren) | 0 | — | — | 0 | 너도밤나무는 가뭄에 약해 메마른 땅에 자라지 않는다. 나무 없는 무대가 있어야 나무 효과를 견준다 |

- 자리는 무대 단위(1 단위 = 2 m, 무대 (0, 0) = x·y 가 가장 작은 모서리)로 `tree_layout.json` 에 있다. 숲 무대 월드 좌표는 무대 원점 (28200, 40500) cm 에 더하면 된다.
- 나무 크기(키)는 1.8~2.2 배(팀 배치 2 배의 ±10%), 방향은 마음대로, 모두 곧게 선다. 키는 약 22~27 m, 잎 넓이 반경은 6~15 m 이다.

## 2. 규칙과 근거

| 규칙 | 값 | 근거 |
|---|---|---|
| 줄기 원판 반지름 | 밑동 꼭짓점 반경 40.45 cm × 크기 | 메시를 편집기 파이썬으로 재 보니 줄기 밑동은 꼭짓점 6 개 육각형(반경 40.45 cm, 크기 2 배면 0.81 m)이고 110 cm 높이에서 32.5 cm 로 가늘어진다. 가장 굵은 밑동의 꼭짓점 반경을 써서 보이는 줄기가 원판 밖으로 나오지 않는다. 동물 몸 30 cm 는 세계가 더한다 |
| 수 | 숲 24·고지 9·메마른 땅 0 | 위 표. 숲 24 는 팀 피드백(`Docs/RL_Policy/FEEDBACK_AVAROKI_1017.md`)의 부탁과 같은 수다 |
| 퍼뜨리기 | 포아송 원반 (무작위로 던져 너무 가까운 것은 버림), 간격 = 빈 넓이 ÷ 그루 수의 제곱근 × 0.5 | 성숙림 큰 나무는 서로 그늘·뿌리 다툼으로 고르게 떨어져 선다(어림). 줄기 사이 틈은 3 m 넘게(숲 가장 좁은 곳 7.7 m) — 사슴이 빠져나간다 |
| 은신처 | 줄기 가장자리가 은신처 원(반경 12 m) 둘레에서 2 m 밖 | 우리 은신처 4 곳(무대 1/4·3/4 지점). 은신처 원 안 나무는 레벨 읽기도 은신처 장식으로 보고 빼는 자리다 |
| 벽 | 줄기 가장자리가 무대 벽에서 4 m 밖 | 무대 벽은 실제 땅에 없는 울타리라 벽과 줄기 사이에 사슴이 끼지 않게 |
| 빈터 | 무대 가운데 반경 22 m 에는 놓지 않음 | 무대 가운데가 팀 먹이 자리이고, 숲 무대에서는 팀 은신처 앵커 둘과 플레이어 시작 자리가 그 안에 있다. 숲 속 빈터(볕이 들어 풀이 자람)에서 사슴이 풀을 뜯는다. v3 먹이 격자는 세션 시드마다 바뀌어 고정 표가 따라갈 수 없다 |
| 늑대 시작 모서리 | 줄기 가장자리가 3 m 밖 | 늑대 시작 자리 계획이 나무 때문에 바뀌지 않게(시험으로 확인: 늑대 자리는 나무 없을 때와 같다) |
| 땅에 붙이기 | 줄기 중심과 둘레 6 곳(줄기 반지름)의 땅 가운데 가장 낮은 곳보다 10 cm 묻음 | 팀 피드백의 '밑동을 0~30 cm 묻기'. 기울어진 땅에서도 밑동이 뜨지 않는다(숲 무대 밑동 아래 높낮이 차 최대 20 cm) |
| 시드 | 숲 32095·고지 32096 (numpy) | 탐색 시드 범위. 같은 시드·규칙이면 같은 표 |

## 3. 언리얼에서 하는 일

`AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.{h,cpp}` 'StageTrees', 표는 `AI/Policy/TreeLayoutV3.h`(생성 파일).

1. **시작 자리**(`PlanStage`, 조정자 시작 전): 줄기 원판(반지름 + 몸 30 cm) 안 자리는 버리고 다음 자리를 뽑는다. 세계의 '원판 안' 판정과 같은 식이라 입양 때 밀어낼 일이 없다(헤드리스 '원판 밖으로 옮김 0').
2. **나무 놓기**(무대를 만들 때, 조정자가 개체를 만든 뒤 — 땅이 다 불려 있다): `AStaticMeshActor` 를 표의 자리·방향·크기로 놓는다. 충돌 없음, 그림자 켬, 꼬리표 `EcoV3StageTree`.
   움직임 가능(Movable)으로 둔다 — 정적(Static) 컴포넌트는 등록된 뒤 메시를 넣을 수 없어서다. 나무는 움직이지 않는다.
   은신처가 표가 가정한 자리에 있지 않거나 레벨 은신처가 무대에 있으면 그 곁(반경 + 2 m) 나무는 빼고 경고를 남긴다(지금 레벨에서는 0).
3. **원판**: 레벨 읽기 원판(지금 0)과 나무 원판을 합쳐 (x, y, r) 순으로 세계에 넣는다. 레벨 읽기는 우리 나무 액터를 빼서 두 번 세지 않는다.
4. **놓지 않는 때**: `eco.IntegratedV3.StageTrees 0`, `eco.IntegratedV3.Obstacles 0`(원판이 없으면 나무도 없다), 무대 한 변이 120 m 가 아닐 때(`eco.IntegratedV3.StageSizeM`), 그 지역 원판을 측정 전용으로 가져올 때(`-EcoV3ObstacleImport=`).
5. **기록**: 시작 줄 `[EcoV3I] 무대 나무: 켬 …`, 지역마다 `[EcoV3I] <지역> 나무 | 배치 표 trees-1017a 24 그루 → 놓음 24 (줄기 원판 반지름 …, 밑동 아래 땅 높낮이 최대 …) · 뺌: … | 세계 원판 24 = 나무 24 + 레벨 0`, 10초 일곱째 줄 `원판 24 (무대 나무 24 + 레벨에서 읽음 0, …)`. 원판 내보내기(`-EcoV3ObstacleExport=`)에 `tree_discs`·`tree_layout` 칸.
6. **디버그 표시**(`eco.V3Debug 1`): 줄기 원판은 초록 원(레벨 원판은 갈색), 바깥 옅은 원은 몸 여유 둘레.

팀 이동 제약(`EcoCreatureMovement::ConstrainStep`)과 플레이어는 나무를 모른다(충돌 없음). v3 사슴·늑대는 v3 세계 원판이 막는다.

## 4. 파이썬에서 같은 나무 쓰기

```
# herbivore_rl/ 에서 — 표·헤더·거울 설정 다시 만들기 (같은 규칙·시드면 바이트 단위로 같다), 확인만
python results/v3/wild2/trees/make_tree_layout.py
python results/v3/wild2/trees/make_tree_layout.py --check
# 숲 무대 하나 (configs/v3_wild2_trees_mirror.yaml = 장애물 거울 + obstacles.fixed 숲 원판)
python results/v3/mirror/run_mirror.py --config configs/v3_wild2_trees_mirror.yaml --deer 128 --seeds 32000-32029
# 지역마다 (메마른 땅 0·숲 24·고지 9) — 언리얼 지도 짝, 원판은 tree_layout.json 의 지역 원판
python results/v3/mirror/run_mirror.py --config configs/v3_wild2_trees_mirror.yaml --deer 128 --unreal-maps 20000-20002 --replicates 10 \
    --seeds 32000-32089 --unreal-obstacles results/v3/wild2/trees/tree_layout.json
```

- `tree_layout.json` 은 언리얼 원판 내보내기와 같은 꼴(`regions[].region`·`discs`)이라 `run_mirror.py`·`stuck_check.py` 의 `--unreal-obstacles` 가 그대로 읽는다.
  언리얼 헤드리스 내보내기(`unreal_exports/s20000~20002.json`)의 원판이 이 표와 비트 단위로 같다(`tests/test_wild2_trees.py`).
- 표를 바꾸면(규칙·시드) 세 파일(JSON·C++ 헤더·거울 설정)이 함께 바뀐다. C++ 는 다시 빌드한다.

## 5. 확인한 것

- 빌드: `-DisableAdaptiveUnity`·기본 두 방식 성공. 자동 시험 166 모두 성공(그중 `SaveLoadGlobalEma` 는 전부터 있던 경고 1 — 저장 파일 없음), 실패 0. 새 시험 3 개:
  - `Policy.V3.StageTrees.Layout` — 표 규칙(벽·은신처·빈터·늑대 모서리·간격·틈 3 m), 반지름 식(비트 단위), 원판 목록 = 표, 다른 크기 무대·모르는 지역 = 표 없음, 기본값 켬.
  - `Policy.V3.StageTrees.StartPoints` — 숲·고지 사슴 128·늑대 4 가운데 줄기 원판 안 시작 자리 0(나무를 끄고 계획하면 숲에서 2), 늑대 자리는 나무 없을 때와 같다, 메마른 땅·다른 크기 무대·장애물 끔은 그대로.
  - `Policy.V3.StageTrees.Spawn` — 시험 바닥 위 24 그루: 메시·충돌 없음·그림자·자리(바닥 − 10 cm)·방향·크기, 레벨 읽기에서 두 번 세지 않음, 은신처를 나무 위로 옮기면 그 나무만 뺌, 땅이 없으면 놓지 않음, 원판 합치기 순서.
- 파이썬 시험 `tests/test_wild2_trees.py` 5 개 통과: 표가 최신·규칙, C++ 헤더 = JSON, 거울 설정 원판 = 숲 표(나머지는 장애물 거울과 같음), 짝 지도 지역마다 0·24·9, 언리얼 내보내기 = 표.
- 언리얼 헤드리스(통합 레벨, 사슴 128, 세션 20000~20002, 240초, 기본값 그대로 — `unreal_logs/`, `unreal_exports/`):
  - 세 세션 모두 숲 24·고지 9 그루를 다 놓음(뺀 것 0), 밑동 아래 땅 높낮이 최대 숲 20 cm·고지 5 cm. 오류·ensure·EcoV3I 경고 0.
  - 원판 밖으로 옮긴 개체 0(시작 자리가 줄기를 피했다), 사슴이 줄기에 닿은 스텝 0.1~0.5%, 물러남 0, 돌아가기 못 찾음 0.
  - 메마른 땅 무대 기록 줄은 나무 넣기 전(`../shc/unreal_logs/`)과 CPU 시간 칸 말고 같다(나무가 다른 무대를 바꾸지 않는다).
  - 230초 산 사슴: 숲 121·120·121 (넣기 전 123·122·121), 고지 121·121·121 (120·122·122). 세 세션뿐이라 효과를 잰 것이 아니다.
- 파이썬 끼임(짝 지도 90 세계 × 240초, `stuck_pair.txt`·`stuck_pair.json`): 아래 '끼임' 절.
- 화면(GPU, 1920×1080 을 1280×720 으로 줄임, 세션 20000, `shots/`):

| 사진 | 무엇을 보나 |
|---|---|
| `shots/forest_top.png` | 숲 무대 위에서. 잎이 무대의 큰 몫을 덮고, 가운데 빈터와 은신처 넷이 트였다 |
| `shots/forest_top_debug.png` | 같은 자리 + 디버그(무대 상자·은신처 원). 은신처 원 안에 줄기가 없다. 은신처 두 곳은 가장자리 위로 잎이 드리운다 |
| `shots/forest_oblique.png` | 숲 무대를 남서쪽 위에서 비스듬히 |
| `shots/forest_ground_debug.png` | 은신처 곁 3 m 높이에서. 줄기마다 밑동에 초록 원(줄기 원판)이 맞고, 줄기가 땅에 서 있고, 은신처 원(파랑) 안은 비었다 |
| `shots/forest_shelter_orbit.png` | 은신처(덤불·바위) 둘레에서. 사슴이 은신처와 나무 사이를 지난다 |
| `shots/highland_top.png` | 고지 무대 위에서. 9 그루, 은신처 넷 비었음 |
| `shots/highland_oblique.png` | 고지 무대 비스듬히 |
| `shots/highland_ground.png` | 고지 낮은 자리에서. 줄기가 눈 덮인 땅에 서 있다 |

  장면 목록은 `shots/film_shots_pass1.json`·`film_shots_pass3.json`(2 번째 판은 카메라가 풀숲에 묻혀 버렸다). 다시 찍기:
  `UnrealEditor.exe <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3Seed=20000 -EcoV3Film=trees -EcoV3FilmOut=<폴더> "-EcoV3FilmShots=Forest,top,0,6,0.2,,,,1;Forest,top,0,9,0.2,,,,0;Forest,wide,0,12,0.2,,,,0;Forest,shelter,0,18,0.2,,,,0;Highland,top,0,21,0.2,,,,1;Highland,wide,0,24,0.2,,,,0" -benchmark -fps=30 -seconds=28 -windowed -ResX=1920 -ResY=1080 -NoSound -nosplash -DisablePlugins=Bridge,Fab`
  (낮은 자리: `Forest,shelter,2,15,0.2,20,3,315,1`·`Highland,wide,0,18,0.2,20,4,300,0`).

### 끼임

`python results/v3/wild2/stuck_check.py --config configs/v3_wild2_trees_mirror.yaml --seeds 32000-32089 --steps 1800 --unreal-maps 20000-20002 --replicates 10 --unreal-obstacles results/v3/wild2/trees/tree_layout.json`
(파이썬 거울, 지도 9 장 × 10 세계, 240초. 정의는 `../stuck_check.py` 머리 주석 — 움직이려 했는데 원판에 막혀 3 초 넘게 1 m 도 못 간 것)

| | 메마른 땅 (나무 0) | 숲 (24) | 고지 (9) | 나무 없는 기준 (`../shc/stuck_pair.txt`, 90 세계) |
|---|---|---|---|---|
| 줄기에 낀 늑대 | 0 | 0 | 0 | 0 |
| 줄기에 낀 사슴 | 0 | 0 | 0 | 0 |
| 은신처 둘레에 걸린 늑대 (나무와 무관, 가장 김) | 8 (5.2초) | 7 (4.1초) | 6 (4.4초) | 22 (6.0초) |

- 돌아가기는 사슴 19730·늑대 159 스텝 썼고 빈 방향을 못 찾은 적은 0 이다.
- 옛 검증 세기로 '줄기에 닿은 채 5 초 넘게 1 m 안에 머문 사슴' 34 은 줄기 곁에 서서 먹는 사슴이다(끼임 아님 — 장애물 거울에서도 같은 까닭으로 667 이었다). 그중 줄기 둘레를 6 초쯤 돈 사슴 2(숲).

## 6. 남은 것·정할 것

- **잎이 은신처 가장자리를 덮는다.** 규칙은 줄기만 비운다(은신처 둘레 + 2 m). 위에서 보면 은신처 두 곳(숲)·한 곳(고지)의 가장자리가 잎에 가린다. 은신처를 위에서도 다 보이게 하려면 줄기를 은신처 둘레에서 잎 반경(6~15 m)만큼 더 떨어뜨려야 하고, 그러면 숲에 24 그루가 들어가지 않는다 — 사람이 정한다.
- **팀이 무대에 줄기 충돌 나무를 놓으면** 레벨 읽기 원판과 우리 나무가 함께 들어간다. 그때는 `-EcoV3StageTrees=0` 으로 끄고 팀 배치를 쓴다(R4 계획의 '팀 배치가 오면 그 원판').
- 플레이어 폰은 줄기를 지나간다(충돌 없음). 팀 이동 제약도 나무를 모른다 — v3 사슴·늑대만 막힌다.
- R4 학습은 하지 않았다. 학습 세계에서 이 배치를 쓰려면 `RL_V3_R4_PLAN.md` 의 배치 셋(원판 0·가는 줄기 숲·굵은 나무 숲)에 이 표를 넣는다.

## 파일

- `make_tree_layout.py` — 배치 표 만들기(규칙·근거는 머리 주석). `--check` 은 쓰지 않고 견준다.
- `tree_layout.json` — 표(지역마다 discs·trees). `tree_layout.png` — 무대 셋 그림.
- `../../../../../AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/TreeLayoutV3.h` — 같은 표의 C++ 헤더(생성). `../../../../configs/v3_wild2_trees_mirror.yaml` — 파이썬 거울 설정(생성).
- `unreal_logs/trees_s20000~20002.log`, `unreal_exports/s20000~20002.json` — 언리얼 헤드리스 기록·원판 내보내기.
- `stuck_pair.txt`·`stuck_pair.json` — 파이썬 끼임 세기(짝 지도).
- `shots/` — GPU 사진과 장면 목록.
