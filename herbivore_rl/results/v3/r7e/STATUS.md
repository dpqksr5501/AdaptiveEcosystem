# v3 R7e 진행 상황 (사전 등록 `PREREG.md`)

- 상태: **사전 등록 확정 — 학습 없음, ① 점검 · ② 고르기 · ③ 판정은 아직 돌리지 않았다.** (10-24)
  - 돌린 것은 도구 스모크(`logs/smoke_tools.log`·`logs/smoke_judge.md`)와 시험(`tests/test_r7e_prereg.py`)뿐이다.
  - 스모크는 스모크 시드 32080~32082 와 R7 시작 두뇌(route0m5·obs21zero_m6)만 썼다.
  - 판정 시드 38000~38099 · 새 점검 38220~38239 · 새 고르기 38200~38219 로 돌린 판은 없다.
- 차례(PREREG 4~6절): ① 2M·5M 점검 → ② 모델 고르기(GF·GE 자격) → ③ 판정.
  - 각 단계는 앞 단계의 기록이 있어야 도구가 시작한다. 고르기는 `logs/early_main.json`, 판정은 `logs/select.txt` 의 고른 모델이 있어야 한다.
- 두뇌는 R7 본 학습 산출 그대로다(`ckpt/v3/v3_r7_g995_s{0,1,2}_20m*.zip`, 대조 `v3_r7off_g995_s0_20m*.zip`). 도구가 sha1 을 R7 값과 견준다(PREREG 1-1).
- 시간 어림(언리얼 끈 PC, CPU 20, 워커 14): ① 약 12 분 · ② 약 5 분 · ③ 약 32 분 — 모두 기계 시간 약 50 분.
- 돌리기 전에 다른 파이썬·언리얼·UBT 프로세스가 무거운 일을 하고 있지 않은지 본다.
  - 같은 작업 트리에서 다른 갈래가 세계 코드(`env_v2/` 등)를 고치는 중이면 끝난 뒤 돌린다.
  - 도구는 세계 셈 길 지문이 다른 판끼리 짝을 짓지 않는다(`same_code`).

## 1. 돌릴 명령 (herbivore_rl/ 에서)

### 1-1. ① 2M·5M 점검 (PREREG 4절 — 점검 시드 38220~38239)

```bash
PYTHONUTF8=1 python results/v3/r7e/r7e_eval.py checks --control 2>&1 | tee results/v3/r7e/logs/checks.log
```

- 돌리는 것: 기준 route0 판(`runs/early_base.json`, 탐침), R7 s0·s1·s2 의 2M·5M 체크포인트 6 판, 대조 '길 끔' 2M·5M 2 판(보고만). 판마다 60 세계다.
- 결과:
  - 판마다 `logs/check_<s시드|off>_<k>m.txt` 를 쓴다. 모음은 `logs/early_main.json` 이다(제외 시드·멈춤).
  - 화면 끝 줄은 '제외 시드: … · 멈춤: …' 이다.
- '멈춤'이면 고르기·판정을 하지 않고 보고한다(PREREG 4-2). 모든 시드가 빠져도 R7e 실패로 보고한다.

### 1-2. ② 모델 고르기 (PREREG 5절 — 고르기 시드 38200~38219, 제외된 시드는 명령에서 뺀다)

```bash
PYTHONUTF8=1 python results/v3/r7e/r7e_eval.py select --models ckpt/v3/v3_r7_g995_s0_20m.zip ckpt/v3/v3_r7_g995_s1_20m.zip ckpt/v3/v3_r7_g995_s2_20m.zip 2>&1 | tee results/v3/r7e/logs/select.log
```

- 결과는 `logs/select.txt`·`logs/select.json` 이다.
  - 표 칸: 사건 숨음 비율, GF·GE 짝 차이·t·자격. 보고만 칸으로 GR·도망 단위 숨음 비율도 적는다.
  - 끝 줄은 '고른 모델: …' 이다.
- 도구가 받지 않는 후보(`select_guard`): 마지막 모델 꼴이 아님, R7e 점검 기록이 없음, 점검이 제외한 시드, sha1 이 R7 과 다름.
- 자격(GF·GE 짝 t < +2.0)을 넘은 모델이 없으면 '고른 모델: 없음' 이다. R7e 실패로 보고하고 판정하지 않는다.

### 1-3. ③ 판정 (PREREG 3·6절 — 판정 시드 38000~38099 는 여기서 처음 쓴다)

```bash
PYTHONUTF8=1 python results/v3/r7e/r7e_eval.py judge --model ckpt/v3/v3_r7_g995_s<고른 시드>_20m.zip --off ckpt/v3/v3_r7off_g995_s0_20m.zip 2>&1 | tee results/v3/r7e/logs/judge.log
```

- `--model` 은 `logs/select.txt` 의 '고른 모델' 이어야 하고, `--off` 는 R7 대조 마지막 모델이어야 한다. 다르면 도구가 멈춘다.
- 돌리는 것:
  - N: R7·route0·대조·'늘 SHELTER'·R6 고른 두뇌 각 300 세계.
  - G: R7·route0 각 120 세계.
  - 끼임: 각 15 세계.
- 그 뒤 A5 두뇌 파일 `brains/v3_r7_g995_s<시드>_20m.json` 을 쓰고 `judge.md`·`judge.json` 을 쓴다.
- 끝나면 `README.md` 맨 위에 결과를 쉬운 말로 적고, PREREG 변경 기록에 차례를 적는다.

## 2. 진행 보기

```bash
cat results/v3/r7e/logs/checks.log | grep -E "^(s|off)[0-9_]*m|제외 시드"    # 점검 판마다 통과/못 넘음, 끝 줄 제외 시드·멈춤
cat results/v3/r7e/logs/select.txt                                               # 고르기 표와 '고른 모델: …'
head -40 results/v3/r7e/judge.md                                                 # 판정 표
```

- 판 파일은 `results/v3/r7e/runs/`(git 밖)에 있다. 같은 조건의 판은 다시 쓰므로, 끊겼으면 같은 명령을 다시 넣는다.

## 3. 도구 스모크 (판정 아님 — 사전 등록 때 한 것, PREREG 8절)

```bash
# <임시> = 세션 임시 폴더. <임시>/ck 에 route0m5 를 v3_r7_g995_s{0,1,2}_20m_{2,5}m.zip 으로, obs21zero_m6 를 v3_r7off_g995_s0_20m_{2,5}m.zip 으로 복사해 둔다
PYTHONUTF8=1 python results/v3/r7e/r7e_eval.py checks --control --ckpt-dir <임시>/ck --smoke 32080-32082 --smoke-steps 300 --out-dir <임시>/checks
PYTHONUTF8=1 python results/v3/r7e/r7e_eval.py select --models route0m5 --smoke 32080-32082 --smoke-steps 300 --out-dir <임시>/sel
PYTHONUTF8=1 python results/v3/r7e/r7e_eval.py judge --model route0m5 --off obs21zero_m6 --smoke 32080-32082 --smoke-steps 300 --out-dir <임시>/judge
PYTHONUTF8=1 python -m pytest tests/test_r7e_prereg.py -q
```
