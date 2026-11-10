# R9 — 사슴·늑대·멧돼지가 각자 배우는 생태계 (파이썬 학습·평가 줄기)

설계: `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md`(커밋 8f1f516e). 지금 상태·등록 값·다음 할 일: `STATUS.md`.

세 종이 같은 관측 107 칸·행동 19 칸·보상식으로 각자 처음부터 배운다. 한 바퀴 = 먹이 묶음(사슴 A·B, 멧돼지 A·B 동시) → 늑대 묶음(늑대 A·B).
배우지 않는 종은 세계 안의 고정 두뇌(풀의 지금 판 50%·예전 판 30%·규칙 20%, 0 바퀴는 규칙)로 돈다. 갈래 A·B 는 끝까지 섞지 않는다(7-2).

| 파일 | 내용 |
|---|---|
| `herbivore_rl/env_v2/r9_body.py` | 몸 표·관측/행동 계약·계약 해시 |
| `herbivore_rl/env_v2/r9_world.py` | 세계 (K, S) — 학습 세계·판정 세계, 숨은 기록(record) |
| `herbivore_rl/env_v2/r9_life.py` | 언리얼 생애 옮김(해시·번식·판정 세계 출생·막힘 셈) |
| `herbivore_rl/env_v2/r9_brains.py` | 고정 두뇌 npz·규칙 두뇌 7 개·세계마다 같은 모양 블록 결정 |
| `herbivore_rl/env_v2/r9_vec_env.py` | `R9VecEnv(learner=종)`: 학습 칸 조각, 세계 번호별 마릿수, 엇갈린 교체 + 상대 고르기, 늑대 세계 조각 프로세스 |
| `train_r9.py` | 묶음 하나(종·갈래·바퀴)의 PPO: 새로 / `PPO.load(env=…, learning_rate=…)`, 첫 롤아웃 가치망만, 결정 수 + 벽시계 상한, 묶음 안 판 zip·npz·JSON, 종별 기록 |
| `league_r9.py` | 바퀴·묶음 차례, 창 없이 띄우고 기다리기, 풀·상태 파일 `ckpt/r9/league_state.json`, 띄우기 전 확인 3 가지 + 보정 값 확인, 끊긴 묶음은 시작 사본에서 처음부터, `--dry-run` |
| `watch_r9.py` | 5 분마다 `logs/progress.md` (진행·속도·종별 숫자·9-5 이상 신호) |
| `eval_r9.py` · `r9_eval_core.py` | 보정 관문(`calibrate`)·이름표 점검(`leak`)·J1(`mixed`)·J2·J3(`judge`, 조각 합치기 `judge-merge`)·장면·이상·바퀴 끝 점검(`check`)·요약(`summary`) |
| `plot_r9.py` · `r9_replay.py` | 종별 학습 곡선·개체 수 곡선 · 위에서 본 궤적 PNG |
| `spawn_detached.py` · `launch_league.ps1` | 창 없는 콘솔·새 프로세스 묶음·작업 묶음 밖으로 띄우기 (R8 복사) |
| `bundle_decisions.json` | C0-9 로 등록한 묶음 결정 수 (STATUS 3절, `configs/v3_r9.yaml` `train.bundle_decisions` 와 같은 값) |
| `smoke/` | C0-9 측정 요약(`c09_train_*.json`·`c09_judge_*.json`)·Fix 단계 확인 (등록 근거, 판정 아님) |
| `herbivore_rl/tests/test_r9*.py` | 시험 1~27 (12절) + Fix 단계 시험 |

모든 명령은 `herbivore_rl/` 에서 `PYTHONUTF8=1`, 파이썬 `C:/Users/Sinhyeok/anaconda3/python.exe`. 시드(10절): 학습 풀 43000~43999(학습 코드 기본값),
보정 44000~44179, 스모크·속도 44180~44199, 점검 44200~44299, 시험 44350~44399. **판정 44800~44999 는 학습·점검·보정 코드가 거부하고, judge·mixed 는 잠금 파일로 한 번만.**

## 1. 보정 관문 (띄우기 전, 9-1) — 차례 C0-6 → C0-5 → C0-7 → C0-1~4 → C0-11 → C0-7b·7c, 그다음 밤에 C0-10

```
python results/v3/r9/eval_r9.py calibrate --phase pick        # 고르기 시드, 관문 차례대로. 못 넘거나 물어야 하면 멈추고 C0_STATE.json 에 적는다
python results/v3/r9/eval_r9.py calibrate --phase pick --gates C0-6          # 관문 하나만
python results/v3/r9/eval_r9.py calibrate --phase confirm     # 모든 값이 정해진 뒤 확인 시드에서 모든 관문 다시
python results/v3/r9/eval_r9.py calibrate --gates C0-10 --c010-commands       # C0-10 짧은 학습 명령만 만든다 (돌리지 않음)
```

- 결과: `calib/C0_STATE.json`(고른 값·고친 값·대비책 F·J2 주 기준), `calib/C0_<phase>.json·md`, STATUS 에 덧붙일 글 `calib/C0_STATUS_append.md`.
- **고른 값은 `configs/v3_r9.yaml` 에 옮겨 적는다.** judge·mixed·check·리그는 `C0_STATE.json` 의 값·F 가 YAML 과 다르면 거부한다(옮겨 적기를 잊지 않게).
- 사냥 시도·막힘 셈 정의: 기본은 8-2 문장(`--hunt-def pair` · `--block-def scan`). 다른 정의(`episode` · `once`)는 늘 함께 계산해 결과 파일에 적고,
  사용자가 고르면 모든 평가 명령에 같은 인자를 준다(STATUS 0절). 결과 JSON 에 `metric_defs` 로 남는다.

## 2. 띄우기 (C0 관문 뒤, 밤에, 언리얼을 끈 뒤)

1. 묶음 결정 수·조각 수는 이미 등록했다(STATUS 3절, `bundle_decisions.json`·YAML `train`). 바꾸지 않는다.
2. 차례 확인: `python results/v3/r9/league_r9.py --dry-run --plan-rounds 2 --decisions-json results/v3/r9/bundle_decisions.json`
3. 띄우기: `powershell -ExecutionPolicy Bypass -File results/v3/r9/launch_league.ps1 -DecisionsJson results/v3/r9/bundle_decisions.json -Rounds 10 -CheckCmd "results/v3/r9/eval_r9.py check --round {round} --branches {branch} --league-state {state} --preview-seeds 44200 44249"`
   (조각 수·프로세스 상한·프로세스 메모리는 YAML·기본값이 STATUS 등록 값이다: 늑대 조각 `train.wolf_shards`, `-MaxProcs 6`, `-ProcMemGB 0.5`.)
4. 보기: `python results/v3/r9/watch_r9.py --once` → `results/v3/r9/logs/progress.md`. 사건 `logs/league_events.log`, 화면 `logs/league.log`·`logs/train_<실행>.log`.
5. 10 바퀴 끝에 리그가 멈춘다(`halted: rounds_done`). 멈춤 규칙(9-4)을 점검 시드로 본 뒤 `-Rounds 12` 처럼 늘려 다시 띄우면 상태 파일에서 이어 간다(최대 18).

- 리그가 죽어도 학습 프로세스는 돈다(작업 묶음 밖). 다시 띄우면 도는 묶음을 기다리고(두 벌 막음), 끝 기록 없이 끝난 묶음은 시작 사본에서 처음부터 다시 돌린다.
- 일시 실패(커밋 메모리 바닥의 MemoryError, 조각 작업 프로세스가 죽음·파이프 끊김·120 초 안에 안 열림)는 끝 기록 `stop: cut` → 리그가 같은 묶음을 시작 사본에서 다시 돌린다.
  NaN·그 밖의 오류는 `stop: nan|error` → 리그가 멈추고 사람이 본다(같은 시드면 같은 실패). `--max-attempts 3` = **띄움 최대 3 번(처음 포함, 다시 2 번)**.
- 언리얼 에디터·UBT·ShaderCompileWorker 가 돌면 리그는 띄우지 않고 기다린다(끄지 않는다). 남은 커밋 메모리가 `1.5 × 0.5 GB × 띄울 프로세스 + 6 GB` 보다 적어도 기다린다.
- 짝수 바퀴 점검(8-5)은 `--check-cmd` 에 `{branch}` 를 넣으면 갈래 A·B 를 **동시에** 따로 돈다(두 결과가 모이면 멈춤 규칙 9-4 를 함께 쓴다). 미리 보기 세계 수는 STATUS 등록 값(50 세계 = 44200~44249).
- 처방(9-4, 갈래 안에서만): 상태 파일 `prescriptions.<갈래>` 에 `{"from_round": r, "shares": {"current": 0.4, "past": 0.4, "rule": 0.2}}` 를 더하면 그 바퀴부터 상대 몫이 바뀐다.
- C0-10(γ 두 후보 짧은 학습)은 묶음 하나씩: `train_r9.py --species deer --branch C0_10_g0997 --model-seed 0 --round 0 --gamma 0.997 --decisions 20000000
  --wall-hours <상한> --run-name <이름> --out ckpt/r9/c010/g0997` (0 바퀴 상대 몫이 이미 규칙·늑대 묶음은 규칙 70%·늘 먹기 30% 다. 늘 먹기 100% 는
  `--shares '{"*": {"always_eat": 1.0}}'`). `eval_r9.py calibrate --gates C0-10 --c010-commands` 가 만드는 명령은 이 꼴과 다른 데가 있다(STATUS 7절) — 이 꼴을 쓴다.

## 3. 판정 (멈춘 바퀴의 마지막 두뇌, 판정 시드 — 한 번만)

- 판정 시드에서는 `--seeds` 를 꼭 적고, 최종 두뇌 6 개(`--brain A:deer=… B:boar=…`)를 다 적고, 크기를 줄이거나 `--set` 을 주지 않는다. 잠금 파일은
  `results/v3/r9/eval/JUDGE_LOCK.json` 하나뿐이다(두뇌 sha256·설정 digest·세계 코드 digest). 몸 해시 확인을 통과한 뒤에 잠근다.
- 프로세스 4 개로 나눠 돌리고 합친다 (STATUS 4절의 배치 차례). 예:
```
python results/v3/r9/eval_r9.py judge --seeds 44900 44999 --batches L_A X_AB --long --for-branches A --brain <6 개> --tag _p1
python results/v3/r9/eval_r9.py judge --seeds 44900 44999 --batches L_B X_BA --long --for-branches B --brain <6 개> --tag _p2
python results/v3/r9/eval_r9.py judge --seeds 44900 44999 --batches RULE P_A P_B W_A --brain <6 개> --tag _p3
python results/v3/r9/eval_r9.py judge --seeds 44900 44999 --batches W_B --brain <6 개> --tag _p4 ;  python results/v3/r9/eval_r9.py mixed --seeds 44800 44899 --brain <6 개>
python results/v3/r9/eval_r9.py judge-merge --parts _p1 _p2 _p3 _p4      # → eval/judge.json (판정 문장은 9-2)
python results/v3/r9/eval_r9.py summary
```
- 덧붙임 판(둘째 물결): `judge --seeds 44900 44999 --long-only --for-branches A --variants L0 L1 LS --brain <6 개> --tag _v1` 처럼 갈래마다 나눠 돌리고 `judge-merge` 에 함께 넣는다.

## 4. 묶음 하나만 (보정·스모크)

```
python results/v3/r9/train_r9.py --species deer --branch A --round 0 --decisions 300000 --wall-hours 0.2 --run-name smoke_deer \
    --seeds 44180 44200 --out <밖의 폴더>/ckpt --log-dir <밖의 폴더>/logs
python results/v3/r9/train_r9.py --species wolf --branch A --round 1 --pool <pool.json> --shards 3 ...   # pool.json = {"pool": {"deer": [npz…], "boar": [npz…]}}
```

판 이름: `<out>/<갈래>/<종>_r<바퀴>_<묶음 안 결정 수>.zip`(SB3, 옵티마이저 포함) · `.npz`(세계가 싣는 고정 두뇌, 몸 해시 확인) · `.json`. 묶음 끝 기록 `<out>/<갈래>/<실행>.json`,
상대·시드 기록 `<실행>.history.json`, 학습 기록 `<log-dir>/<실행>.log.jsonl`.
