# v3 R7 진행 상황 (사전 등록 `PREREG.md`)

- 상태: **사전 등록 확정 — 학습 전.** 이 문서·도구·시험을 커밋·push 한 뒤 1-1 명령으로 본 학습을 띄운다. R7 시드 38000~38199 로 돌린 판은 없다.
- 차례(PREREG 5~7절): ① 본 학습 20M × 시드 0~2 + 대조 '길 끔' 20M × 1 (2M·5M 점검 — (c) 에 GF·GR) → ② 모델 고르기(GF·GR 자격) → ③ 판정.
  R6 와 달리 조기 점검 6 조합은 없다(λ 0.98 · 도주 비용 0 고정 — PREREG 5-3).
- 앞 커밋: R7 구현 `e092f71`(마스크 판 5·6, 설정, 시작 두뇌 route0m5, 시험). 이 사전 등록은 그 위에 도구·문서만 더했다(세계·두뇌 코드 그대로).
- 시간 어림(언리얼 끈 PC, CPU 20, 워커 14 — R6 실측 기준, PREREG 9절): ① 약 35 분, ② 약 5 분, ③ 약 32 분 — 모두 기계 시간 약 1.2 시간.

## 1. 띄울 명령 (herbivore_rl/ 에서)

### 1-1. 본 학습 + 2M·5M 점검 (PREREG 3·5절)

```powershell
powershell -ExecutionPolicy Bypass -File results/v3/r7/launch_train.ps1 -Checks
```

- 학습 4 개: R7 `v3_r7_g995_s0_20m`·`s1`·`s2`(route0m5 에서, `configs/v3_r7_train.yaml`) + 대조 '길 끔' `v3_r7off_g995_s0_20m`(obs21zero_m6 에서,
  `configs/v3_r7off_train.yaml`), 모두 `configs/ppo_r6_lam098.yaml`(λ 0.98)·20M·TensorBoard `runs/v3_r7`. 점검 `early_checks.py --seeds 0 1 2 --control --at 2 5`.
- 셸과 떨어진 프로세스(WMI)로 띄운다. PID 목록 `logs/pids.txt`. 먼저 `-DryRun` 으로 명령만 볼 수 있다. 같은 실행 이름의 끝 모델(`ckpt/v3/<실행 이름>.zip`)이
  이미 있으면 덮어쓰지 않고 멈춘다.
- 결과: `logs/train_<실행 이름>.log`, 점검 `logs/check_s<시드>_<k>m.txt`·`logs/check_off_<k>m.txt`, 모음 `logs/early_main.json`(제외 시드·멈춤), 화면
  `logs/early_checks_main.log` 끝 줄 '제외 시드: … · 멈춤: …'.
  - 점검이 '제외'라고 적어도 학습 프로세스를 멈추지 않는다 — 그 시드를 고르기에서 뺀다. (c) 에는 GF·GR 이 들어 있다(PREREG 5-1).
  - '멈춤'이면 고르기·판정을 하지 않고 사람에게 보고한다(PREREG 5-2). 모든 시드가 GR 로 빠지면 GR 나누기(`results/v3/r6/diag/diag.py` 꼴)를 함께 보고한다.
- 점검 프로세스가 죽었으면 손으로: `PYTHONUTF8=1 python results/v3/r7/early_checks.py --seeds 0 1 2 --control --at 2 5` (이미 잰 판은 `runs/` 에서 다시 쓴다).

### 1-2. 모델 고르기 (PREREG 6절 — 제외된 시드는 뺀다)

```bash
PYTHONUTF8=1 python results/v3/r7/r7_eval.py select --models ckpt/v3/v3_r7_g995_s0_20m.zip ckpt/v3/v3_r7_g995_s1_20m.zip ckpt/v3/v3_r7_g995_s2_20m.zip
```

- 고르기 시드 38100~38119 × 지역 셋. 표 `logs/select.txt`(GF·GR 짝 차이·t·자격 칸), 끝 줄 '고른 모델: …'. 마지막 모델 꼴이 아니거나 점검 기록이 없거나
  `logs/early_main.json` 이 제외한 시드는 도구가 받지 않는다(`select_guard`) — 제외된 시드는 명령에서 뺀다.
- 자격(GF·GR 짝 t < +2.0)을 넘은 모델이 없으면 '고른 모델: 없음' — R7 실패로 보고하고 판정하지 않는다.

### 1-3. 판정 (PREREG 4·7절 — 판정 시드 38000~38099 는 여기서 처음 쓴다)

```bash
PYTHONUTF8=1 python results/v3/r7/r7_eval.py judge --model ckpt/v3/v3_r7_g995_s<고른 시드>_20m.zip --off ckpt/v3/v3_r7off_g995_s0_20m.zip
```

- `--model` 은 `logs/select.txt` 의 '고른 모델' 이어야 한다(다르면 도구가 멈춘다).
- N(R7·route0·대조·'늘 SHELTER'·R6 고른 두뇌 각 300 세계)·G(R7·route0 각 120 세계)·끼임(각 15 세계)을 돌리고 A5 두뇌 파일 `brains/v3_r7_g995_s<시드>_20m.json` 을
  쓴 뒤 `judge.md`·`judge.json` 을 쓴다. 끝나면 `README.md` 맨 위에 결과를 쉬운 말로 적고 PREREG 변경 기록에 차례를 적는다.

## 2. 진행 보기

```bash
tail -n 3 results/v3/r7/logs/train_v3_r7*.log          # 1M 마다 '[스텝] 사용 G… F… H… · 길 결정 … · 반사 밖 두뇌 FLEE 0 / 덮기 밖 결정 …', 끝나면 '저장: …'
ls ckpt/v3/v3_r7*_20m_*m.zip | wc -l                   # 체크포인트 수 (시드마다 20)
cat results/v3/r7/logs/early_checks_main.log           # 점검 (판마다 통과/못 넘음, 끝 줄 제외 시드·멈춤)
cat results/v3/r7/logs/select.txt                      # 모델 고르기 표와 '고른 모델: …'
tensorboard --logdir runs/v3_r7
```
- 멈추기(사람이 정할 때만): `powershell -Command "Stop-Process -Id <python PID>"` (PID 는 `logs/pids.txt`).
- 학습 기록의 '반사 밖 두뇌 FLEE' 는 늘 0 이어야 한다(마스크가 막는다). 0 이 아니면 결함이다 — 점검도 결함으로 멈춘다(PREREG 5-1).
