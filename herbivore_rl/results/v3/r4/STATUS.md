# v3 R4 진행 상황 (사전 등록 `PREREG.md`)

- 상태: **본 학습 6 시드 진행 중** (2026-10-18 05:01:46~49 시작 — 이 컴퓨터 시계. 끝 예상 **05:27~05:35** — 첫 3.5분에 3M, 각 약 14,000 스텝/초.
  조기 중단 점검이 워커 6개를 함께 써서 조금 늦어질 수 있다).
- 사전 등록·설정 커밋: `7fb8d73`(push 뒤 학습 시작). 이 파일과 점검 도구 커밋은 그 다음.

## 1. 띄운 학습

| 모델 시드 | python PID | cmd PID | 실행 이름 | 화면 기록 |
|---|---|---|---|---|
| 0 | 4764 | 22072 | v3_r4_g995_s0_20m | `logs/train_s0.log` |
| 1 | 17924 | 26848 | v3_r4_g995_s1_20m | `logs/train_s1.log` |
| 2 | 34536 | 3516 | v3_r4_g995_s2_20m | `logs/train_s2.log` |
| 3 | 6656 | 4672 | v3_r4_g995_s3_20m | `logs/train_s3.log` |
| 4 | 22028 | 16192 | v3_r4_g995_s4_20m | `logs/train_s4.log` |
| 5 | 23888 | 17192 | v3_r4_g995_s5_20m | `logs/train_s5.log` |
| 조기 중단 점검 | 15480 | 8632 | `early_checks.py --seeds 0 1 2 3 4 5 --at 2 5` | `logs/early_checks.log` |

- 띄운 방법: `powershell -ExecutionPolicy Bypass -File results/v3/r4/launch_train.ps1`(WMI 로 셸과 떨어진 프로세스 — 이 세션이 끝나도 이어진다). PID 목록 `logs/pids.txt`.
- 체크포인트: `ckpt/v3/v3_r4_g995_s<시드>_20m_<k>m.zip`(1M 마다), 끝 `ckpt/v3/v3_r4_g995_s<시드>_20m.zip` + `.json`(메타·지역 차례) + `.log.jsonl`(1M 마다 행동 몫) + `.init.json`(시작 가중치 출처).
- TensorBoard: `tensorboard --logdir runs/v3_r4`.

## 2. 진행 보기 (herbivore_rl/ 에서)

```bash
tail -n 3 results/v3/r4/logs/train_s*.log                  # 1M 마다 '[스텝] 사용 G… F… H…' 줄, 끝나면 '저장: … (분, 스텝/초)'
ls ckpt/v3/v3_r4_g995_s*_20m_*m.zip | wc -l                # 체크포인트 수 (시드마다 20 이면 끝)
powershell -Command "Get-Process -Id <python PID> -ErrorAction SilentlyContinue"   # 살아 있나
```
- 끝난 표시: 화면 기록 끝 줄 `config_digest a0d95473e1c7, 체크포인트 20개, …`, 파일 `ckpt/v3/v3_r4_g995_s<시드>_20m.zip`.
- 멈추기(조기 중단 5절에 걸린 시드만): `powershell -Command "Stop-Process -Id <python PID>"`.

## 3. 학습이 끝나면 돌릴 명령 (PREREG 5~7절 순서, herbivore_rl/ 에서)

### 3-1. 조기 중단 점검 (2M·5M, 시드마다) — 기준 판 `runs/early_base.json` 은 이미 있다(R1b-F, 시드 32050~32059 × 지역 셋 × 16분)

**이미 띄워 두었다**: `results/v3/r4/early_checks.py --seeds 0 1 2 3 4 5 --at 2 5`(PID 15480)가 체크포인트가 생기는 대로 점검한다(판 하나 약 3~4분, 12판 약 45분 —
05:50 쯤 끝 예상). 결과: 판마다 `logs/check_s<시드>_<k>m.txt`, 모음 `logs/early_checks.json`, 화면 `logs/early_checks.log` 끝 줄 '멈춤 시드: …'.
점검이 '멈춤'이라고 적어도 학습 프로세스를 멈추지는 않는다 — 사람이(또는 메인 세션이) PREREG 5절대로 그 시드를 고르기에서 빼고, 3 시드 이상이면 대응 1회를 정한다.
점검 프로세스가 죽었으면 아래를 손으로 돌린다.

```bash
for s in 0 1 2 3 4 5; do for k in 2 5; do
  python results/v3/r4/r4_eval.py run --model ckpt/v3/v3_r4_g995_s${s}_20m_${k}m.zip --seeds 32050-32059 --steps 7200 --workers 6 --name early_s${s}_${k}m
  python results/v3/r4/r4_eval.py check --run runs/early_s${s}_${k}m.json --base runs/early_base.json | tee results/v3/r4/logs/check_s${s}_${k}m.txt
done; done
```
- '멈춤'이 나온 시드는 고르기에서 뺀다. 3 시드 이상이면 대응 1회(PREREG 5절 — 변경 기록에 먼저 적고 학습률 1/3, 모델 시드 6~11).
- 판 하나 약 3분(워커 6). 12판 약 40분.

### 3-2. 게임 모델 고르기 (멈추지 않은 시드의 20M)

```bash
for s in 0 1 2 3 4 5; do
  python results/v3/r4/r4_eval.py run --model ckpt/v3/v3_r4_g995_s${s}_20m.zip --seeds 32060-32079 --steps 7200 --workers 6 --name select_s${s}
done
python results/v3/r4/r4_eval.py run --model r1bf --seeds 32060-32079 --steps 7200 --workers 6 --name select_base     # 보고만
python results/v3/r4/r4_eval.py select --runs runs/select_s0.json runs/select_s1.json runs/select_s2.json runs/select_s3.json runs/select_s4.json runs/select_s5.json --base runs/select_base.json | tee results/v3/r4/logs/select.txt
```
- 멈춘 시드는 `--runs` 에서 뺀다. 판 하나 약 6분.

### 3-3. 판정 (고른 모델 M 하나, 판정 시드 33000~33099 — 여기서 처음 쓴다)

```bash
M=ckpt/v3/v3_r4_g995_s<고른 시드>_20m.zip
python results/v3/r4/r4_eval.py run --model $M   --seeds 33000-33099 --steps 7200 --workers 12 --name judge_r4_16m
python results/v3/r4/r4_eval.py run --model r1bf --seeds 33000-33099 --steps 7200 --workers 12 --name judge_base_16m
python results/v3/r4/r4_eval.py run --model $M   --seeds 33000-33099 --steps 1800 --workers 12 --name judge_r4_240s
python results/v3/r4/r4_eval.py run --model r1bf --seeds 33000-33099 --steps 1800 --workers 12 --name judge_base_240s
python results/v3/wild2/stuck_check.py --config configs/v3_wild3_mirror.yaml --model $M --seeds 33000-33029 --steps 7200 \
    --unreal-maps 20000-20009 --replicates 1 --unreal-obstacles results/v3/wild2/trees/tree_layout.json --workers 12 --out results/v3/r4/runs/stuck_r4.json
python results/v3/wild2/stuck_check.py --config configs/v3_wild3_mirror.yaml --model ckpt/v3/v3_r1_g995_s3_20m.zip --seeds 33000-33029 --steps 7200 \
    --unreal-maps 20000-20009 --replicates 1 --unreal-obstacles results/v3/wild2/trees/tree_layout.json --workers 12 --out results/v3/r4/runs/stuck_base.json
python results/v3/r4/r4_eval.py judge --r4 runs/judge_r4_16m.json --base runs/judge_base_16m.json --r4-short runs/judge_r4_240s.json \
    --base-short runs/judge_base_240s.json --stuck-r4 runs/stuck_r4.json --stuck-base runs/stuck_base.json --out results/v3/r4/judge.md
```
- 계산 어림(워커 12): 16분 300 세계 모델당 약 18~20분, 240초 약 5분, 끼임 세기 약 5분씩 → 모두 약 1시간 10분.
- `judge` 끝 줄 `R4 성공`/`R4 실패`(종료 코드 0/1). 결과 `judge.md`·`judge.json`.

### 3-4. 성공이면 (PREREG 7절)
- `export_weights_v3.py` 로 C++ 가중치 교체 → 골든 → 두 방식 빌드 → 자동 시험 → 헤드리스 세션 20010~20019 와
  `python results/v3/mirror/run_mirror.py --config configs/v3_wild3_mirror.yaml --model $M --unreal-maps 20010-20019 --replicates 3 --seeds 32000-32089 --unreal-obstacles results/v3/wild2/trees/tree_layout.json --name r4_pair_u20010-20019`.

## 4. 지금까지 (학습 전)
- f_dec 0.854956(`measure_fdec.log`), 관측 범위(`obs_support.md` — visibility 날씨 밖, energy 0 가장자리), 스모크·동시 6 속도(`logs/smoke_*.log`), 시험판 점검(`pilot/`, `logs/pilot.log`),
  조기 중단 기준 판(`runs/early_base.json` — R1b-F 잡힘 21.80%·굶음 25.36%·산 52.84%·은신처 안 6.09%·도망 8.18%·숨기 2.32%, 30 세계 179초).
- 시험: `tests/test_r4_train.py` 9개 통과(직전 코드 77b3484 와 비트 동일 포함). 파이썬 전체(고치기 전 한 번, `logs/pytest_full.log`) 1509 통과·1 건너뜀·7 실패 — 실패 5 는 전부터 있던 `test_r3_gate.py`(직전 단계 기록과 같음),
  2 는 등록부 시험(`test_r3_world.py::test_registry_and_keys`·`test_unreal_mirror.py::test_registry_and_config` — 새 선택 키를 몰라서)이고 시험을 고친 뒤 통과. 고친 뒤 기준 1511 통과·1 건너뜀·실패 5(전부터).
