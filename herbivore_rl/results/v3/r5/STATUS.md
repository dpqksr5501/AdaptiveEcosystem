# v3 R5 진행 상황 (사전 등록 `PREREG.md`)

- 상태: **본 학습 6 시드 진행 중** (2026-10-19 04:21:37~41 시작 — 이 컴퓨터 시계). 첫 1M 이 04:23:08 에 6 시드 모두 나왔다(약 1.5분, 각 약 11,000 스텝/초).
  3M 은 04:25:22~51(점검과 함께 1M 에 약 1.2분). 끝 예상 **04:45~05:00**(조기 중단 점검이 워커 6개를 함께 써서 조금 늦어질 수 있다).
  조기 중단 점검은 05:10~05:25 쯤 끝 예상(12판, 판 하나 약 3~4분 — 학습이 끝나면 빨라진다).
- 사전 등록·설정 커밋: `c3c570c`(push 뒤 학습 시작). 이 파일은 그 다음 커밋.

## 1. 띄운 학습

| 모델 시드 | python PID | cmd PID | 실행 이름 | 화면 기록 |
|---|---|---|---|---|
| 0 | 17328 | 18740 | v3_r5_g995_s0_20m | `logs/train_s0.log` |
| 1 | 30052 | 37416 | v3_r5_g995_s1_20m | `logs/train_s1.log` |
| 2 | 38172 | 32424 | v3_r5_g995_s2_20m | `logs/train_s2.log` |
| 3 | 39808 | 38076 | v3_r5_g995_s3_20m | `logs/train_s3.log` |
| 4 | 4176 | 39772 | v3_r5_g995_s4_20m | `logs/train_s4.log` |
| 5 | 20476 | 37492 | v3_r5_g995_s5_20m | `logs/train_s5.log` |
| 조기 중단 점검 | 30316 | 24624 | `early_checks.py --seeds 0 1 2 3 4 5 --at 2 5 --workers 6` | `logs/early_checks.log` |

- 띄운 방법: `powershell -ExecutionPolicy Bypass -File results/v3/r5/launch_train.ps1`(WMI 로 셸과 떨어진 프로세스 — 이 세션이 끝나도 이어진다). PID 목록 `logs/pids.txt`.
- 체크포인트: `ckpt/v3/v3_r5_g995_s<시드>_20m_<k>m.zip`(1M 마다), 끝 `ckpt/v3/v3_r5_g995_s<시드>_20m.zip` + `.json`(메타·지역 차례 region_history·숲 꼴 차례 forest_history)
  + `.log.jsonl`(1M 마다 행동 몫) + `.init.json`(시작 가중치 출처 — `v3_r1_g995_s3_obs21zero.zip`).
- TensorBoard: `tensorboard --logdir runs/v3_r5`.
- 1M 학습 세계 기록(판정 아님): 먹기 0.830~0.885·도망 0.077~0.117·숨기 0.038~0.063, 얼기·잠 0.

## 2. 진행 보기 (herbivore_rl/ 에서)

```bash
tail -n 3 results/v3/r5/logs/train_s*.log                  # 1M 마다 '[스텝] 사용 G… F… H…' 줄, 끝나면 '저장: … (분, 스텝/초)'
ls ckpt/v3/v3_r5_g995_s*_20m_*m.zip | wc -l                # 체크포인트 수 (시드마다 20, 모두 120 이면 끝)
cat results/v3/r5/logs/early_checks.log                    # 조기 중단 점검 (판마다 '계속'/'멈춤', 끝 줄 '멈춤 시드: …')
powershell -Command "Get-Process -Id 17328,30052,38172,39808,4176,20476,30316 -ErrorAction SilentlyContinue"   # 살아 있나
```
- 끝난 표시: 화면 기록 끝 줄 `config_digest a119c35118d8, 체크포인트 20개, …`, 파일 `ckpt/v3/v3_r5_g995_s<시드>_20m.zip`.
- 멈추기(조기 중단 5절에 걸린 시드만 — 사람이 정한다): `powershell -Command "Stop-Process -Id <python PID>"`.

## 3. 학습이 끝나면 돌릴 명령 (PREREG 5~7절 순서, herbivore_rl/ 에서)

### 3-1. 조기 중단 점검 (2M·5M, 시드마다) — 기준 판 `runs/early_base.json` 은 이미 있다(R1b-F, 32050~32059 × 지역 셋 × 16분 = R4 기준 판과 같은 값)

**이미 띄워 두었다**(PID 30316). 결과: 판마다 `logs/check_s<시드>_<k>m.txt`, 모음 `logs/early_checks.json`, 화면 `logs/early_checks.log` 끝 줄 '멈춤 시드: …'.
점검이 '멈춤'이라고 적어도 학습 프로세스를 멈추지는 않는다 — PREREG 5절대로 그 시드를 고르기에서 빼고, 3 시드 이상이면 대응 1회를 정한다(변경 기록에 먼저 적는다).
점검 프로세스가 죽었으면 손으로:

```bash
for s in 0 1 2 3 4 5; do for k in 2 5; do
  python results/v3/r5/r5_eval.py run --model ckpt/v3/v3_r5_g995_s${s}_20m_${k}m.zip --seeds 32050-32059 --steps 7200 --workers 6 --name early_s${s}_${k}m
  python results/v3/r5/r5_eval.py check --run results/v3/r5/runs/early_s${s}_${k}m.json --base results/v3/r5/runs/early_base.json | tee results/v3/r5/logs/check_s${s}_${k}m.txt
done; done
```
- 시험판(PREREG 9절)에서 1M 스모크의 굶음이 R1b-F 의 1.4배였다 — 규칙 3(1.5배)이 걸릴 수 있다. 걸려도 문턱을 바꾸지 않는다.

### 3-2. 게임 모델 고르기 (멈추지 않은 시드의 20M, PREREG 6절)

```bash
for s in 0 1 2 3 4 5; do   # 멈춘 시드는 뺀다
  python results/v3/r5/r5_eval.py run --model ckpt/v3/v3_r5_g995_s${s}_20m.zip --seeds 32060-32079 --steps 7200 --workers 12 --name select_s${s}
done
python results/v3/r5/r5_eval.py run --model r1bf --seeds 32060-32079 --steps 7200 --workers 12 --name select_base     # 보고만
python results/v3/r5/r5_eval.py select --runs results/v3/r5/runs/select_s0.json results/v3/r5/runs/select_s1.json results/v3/r5/runs/select_s2.json \
    results/v3/r5/runs/select_s3.json results/v3/r5/runs/select_s4.json results/v3/r5/runs/select_s5.json --base results/v3/r5/runs/select_base.json \
    | tee results/v3/r5/logs/select.txt
```
- 끝 줄 '고른 모델: …' 이 M 이다. 판 하나 약 4~6분(워커 12).

### 3-3. 판정 (고른 모델 M 하나, 판정 시드 33100~33199 — 여기서 처음 쓴다, PREREG 4절)

판정 전에 할 것: 보고만 도구 `results/v3/r5/situ_r5.py`(PREREG 4절 B3 정의 그대로 — R4 `situ_eval.py` 꼴, 두 두뇌 모두 관측 21 세계에서 돌리고 R1b-F 는 앞 18 칸만)를
만들고 PREREG 변경 기록에 적는다. 판정 시드로 도구를 시험하지 않는다(32080~32099 로 시험).

```bash
M=ckpt/v3/v3_r5_g995_s<고른 시드>_20m.zip
E="python results/v3/r5/r5_eval.py run --workers 12"
$E --model $M   --seeds 33100-33199 --steps 7200 --name judge_r5_16m
$E --model r1bf --seeds 33100-33199 --steps 7200 --name judge_base_16m
$E --model $M   --seeds 33100-33199 --steps 1800 --name judge_r5_240s
$E --model r1bf --seeds 33100-33199 --steps 1800 --name judge_base_240s
# 끼임 세기 (G5) — 관측 21 두뇌는 관측 21 거울, R1b-F 는 관측 18 거울 (세계는 같다)
python results/v3/wild2/stuck_check.py --config configs/v3_wild3_obs_mirror.yaml --model $M --seeds 33100-33129 --steps 7200 \
    --unreal-maps 20000-20009 --replicates 1 --unreal-obstacles results/v3/wild2/trees/tree_layout.json --workers 12 --out results/v3/r5/runs/stuck_r5.json
python results/v3/wild2/stuck_check.py --config configs/v3_wild3_mirror.yaml --model ckpt/v3/v3_r1_g995_s3_20m.zip --seeds 33100-33129 --steps 7200 \
    --unreal-maps 20000-20009 --replicates 1 --unreal-obstacles results/v3/wild2/trees/tree_layout.json --workers 12 --out results/v3/r5/runs/stuck_base.json
# 판정표 (인자 이름 --r4 는 R4 도구 그대로 — R5 판을 준다)
python results/v3/r5/r5_eval.py judge --r4 results/v3/r5/runs/judge_r5_16m.json --base results/v3/r5/runs/judge_base_16m.json \
    --r4-short results/v3/r5/runs/judge_r5_240s.json --base-short results/v3/r5/runs/judge_base_240s.json \
    --stuck-r4 results/v3/r5/runs/stuck_r5.json --stuck-base results/v3/r5/runs/stuck_base.json --out results/v3/r5/judge.md
```
- 계산: 16분 300 세계 모델당 약 20~30분(워커 12), 240초 약 6분, 끼임 세기 판 하나 약 5분.

보고만(판정 뒤 — 판정을 바꾸지 않는다):

```bash
# B1 빽빽한 숲 (2차)
$E --model $M   --world dense --seeds 33100-33199 --steps 7200 --name dense_r5_16m
$E --model r1bf --world dense --seeds 33100-33199 --steps 7200 --name dense_base_16m
python results/v3/r5/r5_eval.py dense --r5 results/v3/r5/runs/dense_r5_16m.json --base results/v3/r5/runs/dense_base_16m.json --out results/v3/r5/dense.md
# B3 나무 곁 결정 (situ_r5.py — 판정 전에 만든 도구, 판정 세계·빽빽한 숲)
python results/v3/r5/situ_r5.py run --model $M   --world unreal --seeds 33100-33199 --steps 7200 --workers 12 --name situ_r5_16m
python results/v3/r5/situ_r5.py run --model r1bf --world unreal --seeds 33100-33199 --steps 7200 --workers 12 --name situ_base_16m
python results/v3/r5/situ_r5.py run --model $M   --world dense  --seeds 33100-33199 --steps 7200 --workers 12 --name situ_r5_dense
python results/v3/r5/situ_r5.py run --model r1bf --world dense  --seeds 33100-33199 --steps 7200 --workers 12 --name situ_base_dense
python results/v3/r5/situ_r5.py report --r5 runs/situ_r5_16m.json --base runs/situ_base_16m.json --r5-dense runs/situ_r5_dense.json \
    --base-dense runs/situ_base_dense.json --check-r5 runs/judge_r5_16m.json --check-base runs/judge_base_16m.json --out results/v3/r5/situ.md
```

### 3-4. 성공이면 (P1 과 G1~G6 모두 통과 — PREREG 7절)

```bash
# 1) 두뇌 파일 (헤더는 바꾸지 않는다 — 내장 두뇌는 R1b-F 그대로). 골든 세계는 도구가 관측 21 거울로 고른다
python export_weights_v3.py --model $M --brain-file ../AdaptiveEcosystem/EcoBrains/v3_r5_g995_s<고른 시드>_20m.json
python -m pytest -q tests/test_brain_file_v3.py tests/test_zero_brain_obs21.py
```
2) 언리얼 불러오기 확인 — 에디터·UBT·cl·link·ShaderCompileWorker 가 돌고 있지 않을 때만(사용자 에디터가 열려 있으면 기다린다):
   - 에디터 Play 또는 헤드리스에서 `eco.V3Brain.Load v3_r5_g995_s<고른 시드>_20m` → `[EcoV3Brain] 검사 통과 …`, `eco.V3Brain.Info` 가 계약 `0xbc4fc2d45c47c5fd`(관측 21)을 적는다.
     되돌리기 `eco.V3Brain.Load builtin`.
   - 자동 시험 `Policy.V3` 묶음 통과(지금 183 성공 + 기존 경고 1, 실패 0). C++ 를 바꾸지 않으면 빌드는 필요 없다.
3) 헤드리스 세션 20010~20019(사슴 128, 240초, 나무 + 날씨 기본값):

```
UnrealEditor-Cmd.exe <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=<s> \
    -EcoV3Brain=v3_r5_g995_s<고른 시드>_20m -EcoV3ObsParityLog=75 -EcoV3ObstacleExport=<폴더>/unreal_exports/s<s>.json \
    -benchmark -fps=60 -seconds=240 -NullRHI -NoSound -unattended -nosplash -nopause -DisablePlugins=Bridge,Fab -abslog=<전체 기록>
```
```bash
python results/v3/mirror/run_mirror.py --diag --config configs/v3_wild3_obs_mirror.yaml --model $M --deer 128 --unreal-maps 20010-20019 --replicates 3 \
    --seeds 32000-32089 --unreal-obstacles results/v3/wild2/trees/tree_layout.json --out-dir results/v3/r5/unreal_check/runs --name r5_240
python results/v3/wild3/compare_weather.py --unreal-dir <모은 기록> --python results/v3/r5/unreal_check/runs/r5_240.json --exports <폴더>/unreal_exports
python results/v3/r5/unreal_parity.py --logs <전체 기록 폴더> --parity <판 이름…> --out results/v3/r5/unreal_check/parity   # 관측 대조 어긋남 0
```
   - 통과: 지역마다·합쳐서 산·잡힘·굶음·은신처 안 몫 |z| < 2, 오류·ensure·EcoV3I 경고 0, 관측 대조 어긋남 0. 안 되면 게임에 넣지 않고 차이부터 찾는다.
   - 내장 두뇌로 바꿀지는 사용자 결정이다.

### 3-5. 실패면 (PREREG 8절)

- 게임 두뇌는 R1b-F 그대로. `judge.md`·`dense.md`·`situ.md` 로 보고하고 다음 갈래(레벨 나무 늘리기·제어기 규칙)를 사용자에게 묻는다.
