# v3 R6 진행 상황 (사전 등록 `PREREG.md`)

- 상태: **학습 전** — 사전 등록·설정 갈래·도구·시험을 커밋·push 했다(이 파일과 같은 커밋). 조기 점검·본 학습은 아직 띄우지 않았다.
- 차례(PREREG 5~7절): ① 조기 점검 6 조합(5M) → (λ, c) 고르기 → ② 본 학습 20M × 시드 0~2 + 대조 '길 끔' 20M × 1 (2M·5M 점검) → ③ 모델 고르기 → ④ 판정.
- 시간 어림(언리얼 끈 PC, CPU 20, 워커 14 — PREREG 9절, 잰 값 `logs/smoke_tools.log`): ① 약 25~30 분, ② 약 40~45 분, ③ 약 7 분, ④ 약 50 분 — 모두 기계 시간
  약 2~2.3 시간(사람이 다음 명령을 넣는 틈 빼고). 언리얼이 함께 돌면 더 느리다.

## 1. 띄울 명령 (herbivore_rl/ 에서)

### 1-1. 조기 점검 6 조합 (PREREG 5-2)

```powershell
powershell -ExecutionPolicy Bypass -File results/v3/r6/launch_train.ps1 -Phase combos -Checks
```

- 학습 6 개(λ 0.95·0.98 × c 0·0.0027·0.005, 5M, 모델 시드 0 — `v3_r6e_l<λ>_c<c>_s0_5m`)와 점검 프로세스(`early_checks.py combos`)를 셸과 떨어진 프로세스로 띄운다.
  PID 목록 `logs/pids.txt`. 먼저 `-DryRun` 으로 명령만 볼 수 있다.
- 결과: 조합마다 `logs/check_l<λ>_c<c>.txt`, 모음 `logs/early_combos.json`, 고른 조합 `logs/early_pick.json`, 화면 `logs/early_checks_combos.log` 끝 줄
  '고른 조합: …' 과 다음 명령(아래 1-2). 멈춤이면 끝 줄 '멈춤: …' — 본 학습을 띄우지 않고 보고한다(PREREG 5-2 멈춤 넷).
  (b) 는 조합의 학습 λ 로 셈한 λ-수익 목표의 설명 분산이다(몬테카를로는 보고만 — PREREG 5-1).
- 점검 프로세스가 죽었으면 손으로: `python results/v3/r6/early_checks.py combos` (이미 잰 판은 `runs/` 에서 다시 쓴다).

### 1-2. 본 학습 (PREREG 3·5-3 — `logs/early_pick.json` 의 λ·c 로)

```powershell
powershell -ExecutionPolicy Bypass -File results/v3/r6/launch_train.ps1 -Phase main -Lam <95|98> -Cost <0|0027|005> -Checks
```

- 학습 4 개: R6 `v3_r6_g995_s0_20m`·`s1`·`s2`(route0 에서, 길 켬 설정) + 대조 '길 끔' `v3_r6off_g995_s0_20m`(obs21zero 에서, 같은 λ·c). 점검 `early_checks.py main --seeds 0 1 2
  --control --at 2 5 --cost <c> --lam <λ>`.
- 결과: `logs/check_s<시드>_<k>m.txt`·`logs/check_off_<k>m.txt`, 모음 `logs/early_main.json`(제외 시드·멈춤), 화면 `logs/early_checks_main.log` 끝 줄 '제외 시드: … · 멈춤: …'.
  점검이 '제외'라고 적어도 학습 프로세스를 멈추지 않는다 — 그 시드를 고르기에서 뺀다. '멈춤'이면 사람에게 보고한다.

### 1-3. 모델 고르기 (PREREG 6절 — 제외된 시드는 뺀다)

```bash
PYTHONUTF8=1 python results/v3/r6/r6_eval.py select --models ckpt/v3/v3_r6_g995_s0_20m.zip ckpt/v3/v3_r6_g995_s1_20m.zip ckpt/v3/v3_r6_g995_s2_20m.zip
```

- 고르기 시드 37100~37119 × 지역 셋. 끝 줄 '고른 모델: …', 표 `logs/select.txt`. 마지막 모델 꼴이 아니거나 `logs/early_main.json` 이 제외한 시드는 도구가
  받지 않는다(`select_guard`).

### 1-4. 판정 (PREREG 4·7절 — 판정 시드 37000~37099 는 여기서 처음 쓴다)

```bash
PYTHONUTF8=1 python results/v3/r6/r6_eval.py judge --model ckpt/v3/v3_r6_g995_s<고른 시드>_20m.zip --off ckpt/v3/v3_r6off_g995_s0_20m.zip
```

- `--model` 은 `logs/select.txt` 의 '고른 모델' 이어야 한다(다르면 도구가 멈춘다).
- N(R6·route0·대조·'늘 SHELTER' 각 300 세계)·G(R6·route0 각 120 세계)·끼임(각 15 세계)을 돌리고 A5 두뇌 파일 `brains/v3_r6_g995_s<시드>_20m.json` 을 쓴 뒤
  `judge.md`·`judge.json` 을 쓴다. 끝나면 `README.md` 맨 위에 결과를 쉬운 말로 적고 PREREG 변경 기록에 차례를 적는다.

## 2. 진행 보기

```bash
tail -n 3 results/v3/r6/logs/train_v3_r6*.log          # 1M 마다 '[스텝] 사용 G… F… H… · 길 결정 … (두 칸 …, π SHELTER …)', 끝나면 '저장: … (분, 스텝/초)'
ls ckpt/v3/v3_r6*_*m.zip | wc -l                       # 체크포인트 수 (조기 점검 시드마다 5, 본 학습 시드마다 20)
cat results/v3/r6/logs/early_checks_*.log              # 점검 (판마다 통과/못 넘음, 끝 줄 고른 조합·제외 시드·멈춤)
tensorboard --logdir runs/v3_r6e                       # 또는 runs/v3_r6
```
- 멈추기(사람이 정할 때만): `powershell -Command "Stop-Process -Id <python PID>"` (PID 는 `logs/pids.txt`).
