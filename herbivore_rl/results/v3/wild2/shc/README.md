# 팀 날씨·나무 시험 레벨 거울 — 언리얼과 같은 원판으로 짝 비교 (10-17)

팀(avaroki 님) PR `ff8c8f4` 의 시험 레벨 `/Game/SHC/Maps/LV_SHC_RegionalWeatherTest`(지역 비·눈 날씨, `Beech_Tree` 11 그루)를 파이썬 거울에 그대로 옮기고,
언리얼 헤드리스와 같은 지도·같은 원판으로 견줬다. 레벨 확인은 `../level_shc/README.md`. 두뇌는 게임 두뇌 R1b-F 그대로(재학습 없음).
레벨·콘텐츠·설정·C++ 는 바꾸지 않았다(언리얼은 측정 전용 원판 가져오기로만 돌렸다).

## 한 줄 결론

- **그 레벨의 나무는 우리 동물 무대(120 m 상자) 셋 어디에도 들어오지 않는다.** 그래서 언리얼과 똑같이 맞춘 파이썬 세계는 무대마다 원판 0 이고,
  지금 기본 거울(`pair_d128_packfood_…`)과 비트 단위로 같은 세계다. 언리얼 쪽도 지금 기본 판(`../unreal_logs/packfood_s20000-20002`)과 기록 줄이 같다.
- **원판 대조**: 언리얼이 쓴 원판(내보내기) = 우리가 만든 지도 = 파이썬 세계의 원판. 지도 9장 모두 모양 (0, 3) 으로 비트 단위 같다.
- **짝 비교**: 산·잡힘·굶음·은신처 안 몫은 같다(지도 9장 |z| ≤ 0.9, 숲 ≤ 1.0). 다른 칸은 이미 알려진 것 그대로다 — 언리얼이 사냥을 더 많이 시작하고
  (118 대 103.2, z +3.6) 돕기·은신처 문 몫이 크다(z +3.5·+3.6). 숲만 보면 모든 칸 |z| ≤ 2.0.
- **끼임**: 사슴 0 · 늑대 원판 끼임 0(원판이 없어서 정의상 0). 늑대 은신처 둘레 기어감 22 번(돕는 늑대 17)·가장 김 6.0 초(90 세계 × 240 초) — 원판과
  상관없이 원래 있던 일이다(16 분 판은 원판 없는 기준과 같은 32 번·5.3 초).
- **학습**: 이 환경에서는 학습해도 바뀌는 것이 없다(사슴 길에 나무가 없다 — 지금 게임 두뇌가 이미 쓰는 세계). 학습할 거리가 생기려면 팀이 나무를
  무대 안에 줄기 충돌로 놓아야 한다(`../level_shc/README.md` 6절, 팀 요청 문서 4절 1).

## 1. 무엇을 맞췄나

그 레벨에는 통합 조정자·은신처가 없어서 우리 통합 v3 모드가 돌지 않는다. 대신 그 레벨이 통합 레벨 `LV_Ecosystem_IntegrationTest` 의 사본(지형·지역 상자·
먹이 자리가 같다 = 무대 자리가 같다)이라는 점을 써서, **레벨 읽기 결과의 나무를 통합 레벨 무대 좌표에 겹치고 우리 레벨 읽기 규칙을 그대로 걸었다**.

- `make_shc_obstacle_maps.py`: `../level_shc/scan_LV_SHC_RegionalWeatherTest.json` 의 나무마다 충돌 상자(우리 규칙 `ObstacleCollisionBox` — 중심·가로 반폭
  평균 13.85 m·높이 24.9 m)를 무대 원점(`../level_shc/v3_export_integration_s20000.json`)으로 옮기고, C++ `ScanStageObstacles` 와 같은 순서로 거른다
  (중심이 무대 밖 → 충돌 없음 → 반지름 25 cm 밑 → 높이 50 cm 밑 → 은신처 원 안). 결과 `obstacle_maps/s20000~20002.json`(세션은 무대 자리를 바꾸지 않아
  셋이 같다): 무대마다 **원판 0**, 11 그루 모두 '중심이 무대 밖'(`dropped` 에 무대 단위 자리와 함께 적었다).
- 무대까지 거리(`trees_in_stage_frame.json`, 원판 중심 기준):

| 무대 | 가장 가까운 나무 | 중심까지 | 원판 가장자리까지 | 몸(30 cm)을 더한 가장자리 |
|---|---|---|---|---|
| 숲(Forest) | Beech_Tree11 (무대 y = 0 변 밖) | 13.95 m | 0.11 m 밖 | **0.19 m 안으로 걸침** |
| 숲 | 그다음 Beech_Tree2 (x = 0 변 밖) | 38.1 m | 24.3 m 밖 | 24.0 m 밖 |
| 메마른 땅(Barren) | Beech_Tree5 | 273.5 m | 259.6 m 밖 | 259.3 m 밖 |
| 고지(Highland) | Beech_Tree5 | 762.6 m | 748.8 m 밖 | 748.5 m 밖 |

  Beech_Tree11 은 중심이 무대 밖이라 우리 규칙이 뺀다. 원판이 무대에 걸치는지로 고른다면 숲 무대 y = 0 벽 곁 19 cm 띠만 막는다(사슴은 무대 벽에서
  잘리므로 사실상 차이 없음). 규칙은 바꾸지 않았다.
- **언리얼**: 통합 레벨 헤드리스, 기본값 그대로(장애물·돌아가기 켬) + `-EcoV3ObstacleImport=obstacle_maps/s<s>.json -EcoV3ObstacleExport=<내보내기>`.
  시작 줄 `[EcoV3I] Forest 장애물 | 가져온 원판 0 (넓이 0.00%) 으로 돈다 — 측정 전용, 레벨에서 읽은 원판 0 대신`(통합 레벨의 숲 무대 메시 20 은 모두 충돌 없는
  풀이라 레벨에서 읽어도 0). 세션 20000~20002, 사슴 128, 240 초. 오류·ensure·EcoV3I 경고 0. 기록 `unreal_logs/`, 내보내기 `unreal_exports/`.
- **파이썬**: 장애물 거울 `configs/v3_wild2_obstacle_mirror.yaml`(늑대 4 + 협동 + 은신처 먹이 부족 + 몸 여유 + 장애물·돌아가기)에 짝 지도
  `--unreal-maps 20000-20002 --replicates 10` 과 `--unreal-obstacles shc/obstacle_maps`(지도마다 그 원판을 `obstacles.fixed` 로 — 난수 없음). 새 설정 파일은
  만들지 않았다(이미 있는 선택지로 충분하다). 짝이 아닌 판은 `--set obstacles.fixed=[]` 가 같은 세계다.

## 2. 같은 세계인가

`check_discs.py` → `disc_check.json` (지도 (세션, 지역) 9장, 파이썬 세계는 `run_mirror.py` 짝 비교와 같은 길로 만든다)

| 칸 | 결과 |
|---|---|
| 원판 수 언리얼 내보내기 · 우리 지도 · 파이썬 `World.obstacles` | 9장 모두 0 · 0 · 0 (모양 (0, 3)) |
| 언리얼 = 지도, 언리얼 = 파이썬 (모양 + 모든 칸 `float.hex`) | 9장 모두 같음 |
| 언리얼 '가져옴' · 레벨에서 읽은 원판 | 9장 모두 가져옴 · 0 |
| 무대 원점 · 한 변 | 같음 (60 단위 = 120 m) |
| 은신처 원 4 개 | 가장 큰 차이 3.6e-15 단위 (1e-9 안) |

- 은신처 원은 비트 단위로 같지 않다(전부터 있던 것, 이번에 바꾸지 않음): 파이썬 무대 배치는 1/4·3/4 자리를 cos·sin 으로 셈해 14.999999999999996 이 되고,
  언리얼은 놓은 은신처 앵커 자리(cm)에서 셈해 15 다(골든 헤더들도 파이썬 값을 쓴다). 1e-14 m 쯤이라 결과에 닿지 않는다.
- **파이썬**: `pair_d128_shc_u20000-20002_k10` 는 10-17 고침 기본값 짝 `pair_d128_packfood_u20000-20002_k10`(원판 없는 무리 거울)과 90 세계 모두 10초 줄·
  죽은 때·사냥 셈·은신처 스텝·진단이 비트 단위로 같다(원판이 0 이면 장애물 규칙 — 미끄러짐·돌아가기·시선 가림·원판 밑 먹이 — 을 타지 않는다).
  `tests/test_wild2_shc.py` 가 300 스텝 궤적으로도 본다.
- **언리얼**: 세션 셋 모두 `[EcoV3I]` 줄이 지금 기본 판 `../unreal_logs/packfood_s20000-20002` 와 같다(442·428·437 줄, 다른 것은 CPU 시간 칸과 장애물 시작 줄뿐).
  헤드리스는 같은 시드면 같은 세계를 돈다.

그래서 아래 짝 비교는 `../README.md` '10-17 고침' 의 '언리얼 지금 기본 (20000~20002)' 줄과 같은 수다(그 판을 새로 돌려 확인한 것).

## 3. 짝 비교 (230초 줄)

`python results/v3/wild2/compare_unreal_wild2.py --unreal-dir results/v3/wild2/shc/unreal_logs --python results/v3/wild2/runs/pair_d128_shc_u20000-20002_k10.json`
(전체 출력 `compare_unreal.md`). 언리얼 한 판 대 파이썬 반복 10 판 평균 [최소..최대], z = (언리얼 − 파이썬 평균) ÷ 파이썬 반복 표준편차.

지도 9장 합 (사슴 128 × 9):

| 판 | 산 % | 잡힘 % | 굶음 % | 사냥 시작·끝·성공 | 사냥 성공률 % | 은신처 안 사슴·스텝 % | 돕기 % | 은신처 문 % | 협동 포획 / 늑대 포획 |
|---|---|---|---|---|---|---|---|---|---|
| 언리얼 | 95.1 | 4.95 | 0 | 118·114·58 | 50.9 | 8.1 | 7.6 | 2.77 | 21 / 58 |
| 파이썬 | 94.8 [94.4..95.2] | 5.18 [4.77..5.56] | 0 | 103.2·101.3·60.7 | 60.0 [52.8..67.0] | 7.6 [6.4..8.7] | 5.9 [5.0..6.5] | 2.08 [1.76..2.33] | 18.0 / 61.0 |
| z | +0.9 | −0.9 | — | **+3.6**·+2.9·−0.8 | −2.3 | +0.6 | **+3.5** | **+3.6** | +0.9 / −1.0 |

숲(Forest)만 (지도 3장):

| 판 | 산 % | 잡힘 % | 굶음 % | 사냥 시작·끝·성공 | 사냥 성공률 % | 은신처 안 사슴·스텝 % | 돕기 % | 은신처 문 % | 협동 포획 / 늑대 포획 |
|---|---|---|---|---|---|---|---|---|---|
| 언리얼 | 95.3 | 4.69 | 0 | 40·40·18 | 45.0 | 9.0 | 7.6 | 2.92 | 8 / 18 |
| 파이썬 | 94.9 [94.3..95.8] | 5.08 [4.17..5.73] | 0 | 36.5·35.7·19.6 | 55.7 [42.1..73.3] | 7.7 [5.4..9.8] | 6.2 [4.2..8.5] | 2.14 [1.47..3.23] | 5.7 / 19.7 |
| z | +0.7 | −0.7 | — | +0.9·+1.0·−0.7 | −1.1 | +1.0 | +1.3 | +1.5 | +2.0 / −0.8 |

- 산·잡힘·굶음·은신처 안은 언리얼과 파이썬이 같다. 둘 다 240 초 안에 굶은 사슴은 없다.
- 차이가 큰 칸(사냥 시작 +3.6, 돕기 +3.5, 은신처 문 +3.6)은 이 판에서 새로 생긴 것이 아니라 지금 기본값 판에 있던 것이다(`../README.md` '10-17 고침',
  명세 `RL_V3_WILD2_SPEC.md` 6-6 — 까닭은 아직 모름). 잡힌 수는 같아서 사슴 쪽 결과에는 드러나지 않는다. 둘째 묶음(20006~20008)에서는 사냥 시작 +1.9·돕기 +0.9 였다.
- 원판이 없어서 장애물 칸(원판 닿음·물러남·돌아감·돕기 그만둠)은 언리얼 일곱째 줄이 없고 파이썬도 모두 0 이다.

## 4. 끼임 (파이썬, `stuck_check.py`)

끼임 정의는 `../README.md` '끼임 세기'(3 초 창 내내 움직이려 했는데 순 이동 < 1 m 이고, 창 안에 원판 부딪힘이 있음). 이번에 `stuck_check.py` 에 짝 지도
선택지(`--unreal-maps`·`--replicates`·`--unreal-obstacles`, `run_mirror.py` 와 같은 짝)를 더해 언리얼과 같은 지도·원판으로 셌다.

| 판 | 세계 × 시간 | 사슴 끼임 | 늑대 원판 끼임 | 늑대 은신처 둘레 기어감 (돕는 늑대) · 가장 김 | 기어간 몫 (움직이려 한 3 초 창) |
|---|---|---|---|---|---|
| **짝 지도 + SHC 원판 (모두)** | 90 × 240 초 | 0 | 0 | 22 (17) · 6.0 초 | 0.033% |
| 숲 | 30 × 240 초 | 0 | 0 | 7 (6) · 6.0 초 | 0.029% |
| 메마른 땅 | 30 × 240 초 | 0 | 0 | 8 (5) · 5.2 초 | 0.039% |
| 고지 | 30 × 240 초 | 0 | 0 | 7 (6) · 4.5 초 | 0.032% |
| 원판 0 (`--set obstacles.fixed=[]`) | 30 × 16 분 | 0 | 0 | 32 (25) · 5.3 초 | 0.029% |

- 원판이 없으면 끼임 정의상 사슴·늑대 원판 끼임은 0 일 수밖에 없다(도구는 원판 부딪힘이 있는 창만 끼임으로 센다). 원판 앞에서 사슴이 어떻게 하는지는
  이 레벨로는 볼 수 없다 — 원판이 있는 판의 결과는 `../README.md` '10-17 장애물 끼임 고침'(돌아가기 켬: 사슴 0·늑대 1 번).
- 볼 수 있는 것은 늑대 은신처 둘레 기어감이다(10-16 늑대 진입 금지의 접선 미끄러짐 — 목표가 원 너머일 때 느리다). 16 분 판은 원판 없는 무리 거울 기준
  (`../stuck/packfood.txt`)과 모든 칸이 같다(같은 세계). 가장 긴 것 6.0 초는 지도 20002 숲의 돕는 늑대다. 원판이 없는 세계의 이 규칙은 아직 그대로다(명세 8절 다음 일).
- 끼임 요약 `stuck_pair.txt`(짝 지도, 지역별 `by_region` 포함)·`stuck_long.txt`(16 분).

## 5. 학습에 대해

- 언리얼과 같은 이 환경은 원판 0 이라 지금 게임 두뇌 R1b-F 가 이미 학습·검증된 세계와 같다. 여기서 학습해도 사슴이 '나무를 잘 알아보도록' 배울 것이 없다.
- 학습할 거리가 생기는 순서: (1) 팀이 나무를 무대 안에(먹이 자리 둘레 120 m) 놓고, (2) 충돌을 줄기 캡슐(반경 약 0.8 m)로 바꾸고(지금 충돌로는 나무 하나가
  반경 13.8 m 원판 = 무대 넓이 4.2%), (3) 땅에 붙인다. 그러면 이 폴더와 같은 길로 다시 맞춘다 — 통합 레벨 헤드리스 `-EcoV3ObstacleExport=` 로 레벨이 쓴 원판을
  내보내고, 파이썬은 `--unreal-obstacles <내보내기 폴더>` 로 같은 원판을 읽어 짝 비교·끼임 세기를 한 뒤 학습이 필요한지 정한다.
- 원판이 있는 숲(파이썬 거울의 숲 배치, 줄기 1 ha 250)에서는 돌아가기를 넣은 지금 두뇌가 이미 언리얼과 같게 돈다(`../README.md` '10-17 장애물 끼임 고침',
  모든 칸 |z| ≤ 2.1).

## 6. 다시 만들기 (herbivore_rl/ 에서)

```
python results/v3/wild2/shc/make_shc_obstacle_maps.py --sessions 20000-20002
# 언리얼 (세션 s = 20000, 20001, 20002)
UnrealEditor-Cmd.exe <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=<s>
    -EcoV3ObstacleImport=<이 폴더>/obstacle_maps/s<s>.json -EcoV3ObstacleExport=<이 폴더>/unreal_exports/export_s<s>.json
    -benchmark -fps=60 -seconds=240 -NullRHI -NoSound -unattended -nosplash -nopause -DisablePlugins=Bridge,Fab -abslog=<전체 기록>
python results/v3/wild1/trim_unreal_log.py results/v3/wild2/shc/unreal_logs <전체 기록>...
# 파이썬 짝 · 원판 대조 · 견줌 · 끼임
python results/v3/mirror/run_mirror.py --diag --out-dir results/v3/wild2/runs --deer 128 --unreal-maps 20000-20002 --replicates 10 --seeds 32000-32089 \
    --config configs/v3_wild2_obstacle_mirror.yaml --unreal-obstacles results/v3/wild2/shc/obstacle_maps --name pair_d128_shc_u20000-20002_k10
python results/v3/wild2/shc/check_discs.py --sessions 20000-20002
python results/v3/wild2/compare_unreal_wild2.py --unreal-dir results/v3/wild2/shc/unreal_logs --python results/v3/wild2/runs/pair_d128_shc_u20000-20002_k10.json
python results/v3/wild2/stuck_check.py --seeds 32000-32089 --steps 1800 --unreal-maps 20000-20002 --replicates 10 \
    --unreal-obstacles results/v3/wild2/shc/obstacle_maps --out results/v3/wild2/runs/stuck_shc_pair.json
python results/v3/wild2/stuck_check.py --seeds 32000-32029 --steps 7200 --set 'obstacles.fixed=[]' --out results/v3/wild2/runs/stuck_shc_long.json
```

`../run_all.sh` 끝 묶음에도 넣었다(언리얼 실행 빼고).

## 파일

- `make_shc_obstacle_maps.py` — SHC 나무 → 무대 원판 지도(C++ 읽기 규칙과 같은 순서). `obstacle_maps/` — 그 지도(세션 20000~20002, 무대마다 원판 0, 뺀 나무와 까닭).
  `trees_in_stage_frame.json` — 나무마다 무대마다 무대 단위 자리와 무대 상자까지 거리.
- `check_discs.py` → `disc_check.json` — 언리얼 내보내기·지도·파이썬 세계 원판 대조.
- `unreal_logs/` — 줄을 고른 언리얼 기록(`trim_unreal_log.py`), `unreal_exports/` — 언리얼이 쓴 원판·은신처 원(`-EcoV3ObstacleExport`).
- `compare_unreal.md` — 견줌 전체 출력(지도마다 표 포함). `stuck_pair.txt`·`stuck_long.txt` — 끼임 요약.
- 시험 `tests/test_wild2_shc.py` 4개: 읽기 규칙 순서(손 장면), 올려 둔 지도 = 다시 만든 지도·무대마다 0, 원판 0 개 장애물 거울 = 무리 거울(300 스텝 궤적),
  `stuck_check.py` 짝 지도 = `run_mirror.py` 짝(367 원판 지도와 0 원판 지도). 야생 2단계 시험 5개 파일 59개 통과.
