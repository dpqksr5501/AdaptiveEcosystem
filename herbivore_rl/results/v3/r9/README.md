# R9 — 사슴·늑대·멧돼지가 각자 배우는 생태계 (파이썬 학습·평가 줄기)

설계: `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md`(처음 커밋 8f1f516e, 감각만 세계 S′ 고침 2026-11-12 — 16-2 절). 지금 상태·등록 값·다음 할 일: `STATUS.md`.

세 종이 같은 관측 **115 칸**·행동 19 칸·보상식으로 각자 처음부터 배운다(S′, 11-12 — 처음 107 칸).

**감각만 세계 S′ (사용자 원칙 11-11: 몸 = 할 수 있는 것·물리, 감각 = 정보만, 두뇌 = 모든 결정)**
- 관측 115 = 자기 31(그중 `food_dir_0..7` = 23~30: 부채꼴 j = 머리에서 왼쪽 j × 45° = `WALK_{j+1}` 쪽에 느낀 내 먹이의 양, x/(x + `food_here_ref`)) + 다른 종 6 × 11(31~96) + 동족 요약 4(97~100) + 가까운 동족 2 × 7(101~114). 망 115 → 64 → 64 → 19.
- `EAT`(0) = 그 자리에서 먹을 수 있는 것만 서서 먹음(먹을 것이 없으면 그냥 섬, 걸어가지 않음). `SHELTER`(17) = 세 종 모두 제자리 서기(은신처 안이면 보호 — 안에 있음의 효과, 사슴은 짝 맺는 순간 이 행동이면 짝 막힘). 먹이·은신처로 가는 것은 두뇌가 `WALK`(1~8)·`RUN`(9~16)으로.
- 학습 세계 풀 용량 합 70, 학습 칸 사슴 16·24·32·40(상대 16~40) — 사슴 학습 칸 896·롤아웃 28,672(N).
- 규칙 두뇌(비교 잣대)는 관측만 읽는 S4 꼴(사양서 7-5): 먹이 찾기(발밑 → `food_dir` 가장 큰 칸 쪽 걷기 → 동족 쪽 찾기)·막힘 기억·은신처 가기. 늑대 음성 대조 `NOHUNT`·`NOHUNT_RUN`.
- 늑대 물기 몸 규칙은 그대로(앞쪽 원뿔·닿는 거리·다가가는 속도). 사냥은 셀 때 strict 정의로 가른다(사양서 8-2). 한 바퀴 = 먹이 묶음(사슴 A·B, 멧돼지 A·B 동시) → 늑대 묶음(늑대 A·B).
배우지 않는 종은 세계 안의 고정 두뇌(풀의 지금 판 50%·예전 판 30%·규칙 20%, 0 바퀴는 규칙)로 돈다. 갈래 A·B 는 끝까지 섞지 않는다(7-2).

| 파일 | 내용 |
|---|---|
| `herbivore_rl/env_v2/r9_body.py` | 몸 표·관측/행동 계약·계약 해시 |
| `herbivore_rl/env_v2/r9_world.py` | 세계 (K, S) — 학습 세계·판정 세계, 숨은 기록(record) |
| `herbivore_rl/env_v2/r9_life.py` | 언리얼 생애 옮김(해시·번식·판정 세계 출생·막힘 셈) |
| `herbivore_rl/env_v2/r9_brains.py` | 고정 두뇌 npz(`W0` (64, 115))·규칙 두뇌(S4 꼴 + 음성 대조)·세계마다 같은 모양 블록 결정 |
| `herbivore_rl/env_v2/r9_vec_env.py` | `R9VecEnv(learner=종)`: 학습 칸 조각, 세계 번호별 마릿수, 엇갈린 교체 + 상대 고르기, 늑대 세계 조각 프로세스 |
| `train_r9.py` | 묶음 하나(종·갈래·바퀴)의 PPO: 새로 / `PPO.load(env=…, learning_rate=…)`, 첫 롤아웃 가치망만, 결정 수 + 벽시계 상한, 묶음 안 판 zip·npz·JSON, 종별 기록 |
| `league_r9.py` | 바퀴·묶음 차례, 창 없이 띄우고 기다리기, 풀·상태 파일 `ckpt/r9/league_state.json`, 띄우기 전 확인 넷(두 벌·**밤 창**·언리얼/UBT/셰이더/라이브 코딩/MSBuild·커밋 메모리) + 보정 값 확인, 끊긴 묶음은 시작 사본에서 처음부터, `--dry-run` |
| `run_night.py` | **밤 실행기**: C0-10 짧은 학습 6 묶음(밤 창) → 잼 → γ 고르기 → `calib/C0_STATE.json` → 통과하면 리그 + 지켜보기, 떨어지면 `calib/C0-10_FAIL.md`. 상태 `ckpt/r9/night_state.json`(끊겨도 이어 감), `--dry-run` |
| `watch_r9.py` | 5 분마다 `logs/progress.md` (진행·속도·종별 숫자·9-5 이상 신호) |
| `eval_r9.py` · `r9_eval_core.py` | 보정 관문(`calibrate`)·이름표 점검(`leak`)·J1(`mixed`)·J2·J3(`judge`, 조각 합치기 `judge-merge`)·장면·이상·바퀴 끝 점검(`check`)·요약(`summary`) |
| `plot_r9.py` · `r9_replay.py` | 종별 학습 곡선·개체 수 곡선 · 위에서 본 궤적 PNG |
| `spawn_detached.py` · `launch_league.ps1` | 창 없는 콘솔·새 프로세스 묶음·작업 묶음 밖으로 띄우기 (R8 복사). `launch_league.ps1 -Night` = 밤 실행기, `-Window`·`-CheckAnytime` |
| `bundle_decisions.json` | C0-9 로 등록한 묶음 결정 수·근거 속도 `speed_dps` (STATUS 3-1, `configs/v3_r9.yaml` `train.bundle_decisions` 와 같은 값). **11-12 S′ 다시 등록**: 0 바퀴 80.3M / 30.3M / 38.8M, 1 바퀴부터 19.4M / 7.2M / 7.3M (사슴 / 멧돼지 / 늑대). 11-11 값(처음 세계)은 `superseded` 에 기록만 |
| `smoke/` | C0-9 측정 요약 — S′ 등록 근거 `s_c09_train_*.json`·`s_c09_judge_*.json`(11-12), 처음 세계 `c09_train_*.json`·`c09_judge_*.json`(11-11 기록)·Fix 단계 확인 (등록 근거, 판정 아님) |
| `herbivore_rl/tests/test_r9*.py` | 시험 1~27 (12절) + S′ 시험 S1~S11 + Fix 단계 시험 |

모든 명령은 `herbivore_rl/` 에서 `PYTHONUTF8=1`, 파이썬 `C:/Users/Sinhyeok/anaconda3/python.exe`. 시드(10절): 학습 풀 43000~43999(학습 코드 기본값),
보정 44000~44179, 스모크·속도 44180~44199, 점검 44200~44299, 시험 44350~44399. **판정 44800~44999 는 학습·점검·보정 코드가 거부하고, judge·mixed 는 잠금 파일로 한 번만.**

## 1. 보정 관문 (띄우기 전, 9-1) — 차례 C0-6(보고만) → C0-5 → C0-7 → C0-1~4(C0-4 보고만) → C0-11 → C0-7b·7c, 그다음 밤에 C0-10

```
python results/v3/r9/eval_r9.py calibrate --phase pick        # 고르기 시드, 관문 차례대로. 못 넘거나 물어야 하면 멈추고 C0_STATE.json 에 적는다
python results/v3/r9/eval_r9.py calibrate --phase pick --gates C0-6          # 관문 하나만
python results/v3/r9/eval_r9.py calibrate --phase confirm     # 모든 값이 정해진 뒤 확인 시드에서 모든 관문 다시
python results/v3/r9/eval_r9.py calibrate --gates C0-10 --c010-commands       # C0-10 짧은 학습 명령만 만든다 (돌리지 않음)
```

- 정하는 관문의 고르기(11-12 등록): C0-5 = 두 띠를 모두 통과한 후보 중 d = max(|땅속 − 0.65|, |Pianka − 0.35|) 가장 작은 것(차 0.01 안은 표 차례),
  C0-7 = 통과 후보 중 max(|log 사슴비|, |log 멧돼지비|) 가장 작은 것(차 0.05 안은 표 차례) + 등록 조건(0.012 는 끝 수 띠에서 떨어져야, 아니면 묻기)·0.005 보고.
  C0-1 이 떨어지면 다른 값으로 넘어가지 않고 묻는다. C0-2 는 위로 넘치면 U[0.85, 1.00]·아래로 떨어지면 U[0.95, 1.10] 로 한 번만.

- 결과: `calib/C0_STATE.json`(고른 값·고친 값·대비책 F·J2 주 기준), `calib/C0_<phase>.json·md`, STATUS 에 덧붙일 글 `calib/C0_STATUS_append.md`.
- **고른 값은 `configs/v3_r9.yaml` 에 옮겨 적는다.** judge·mixed·check·리그는 `C0_STATE.json` 의 값·F 가 YAML 과 다르면 거부한다(옮겨 적기를 잊지 않게).
- 관문 정의(2026-11-12 정함, STATUS 0·2절): 사냥 시도 = **strict 사냥**(같은 늑대의 겹친 다가감 구간 묶음, 결정 절반 넘게 걷기·뛰기, 느낀 사체 칸 쪽 걷기·뛰기 = 사체로 가는 중), 막힘 = **같은 시드 L0 짝 비교가 주 기준**(`scan`·`once` 는 함께 적음),
  C0-5 = 먹은 양 기준, C0-7 = 띠 ∧ 멸종 없음 ∧ |L0 변화| < 20% · 점수 max(|log 비|) · 0.012 대조, C0-1 = 섞인 무리, C0-2 = strict 성공률, C0-6·C0-4 = 보고만, C0-10 늑대 = 보상 짝 차 ∧ 사냥 성공률 ∧ 사냥 죽임 κ. 인자 이름·기본값은 구현을 따른다(`--help`). 결과 JSON 에 `metric_defs` 로 남는다.

## 2. 띄우기 (C0 관문 뒤, 밤에, 언리얼을 끈 뒤)

0. **밤 창(STATUS 5절, 기본 22:00~09:00) 안에서만 묶음을 시작한다.** 시작 시각 + 그 묶음의 어림 벽시계(등록 결정 수 ÷ 등록 속도 `speed_dps` × 1.1, 속도가 없으면
   벽시계 상한 / 2)가 창 끝을 넘으면 띄우지 않고 다음 창 시작까지 기다린다. 언리얼 에디터·UBT·ShaderCompileWorker·LiveCodingConsole·MSBuild(어느 프로젝트든)가 돌면
   끄지 않고 기다린다. 기다리는 까닭은 `logs/league_events.log`·상태 파일 `waiting`·`logs/progress.md` 에 적힌다. 이미 돌던 묶음은 창이 끝나도 끊지 않는다.
   리그 인자 `--window HH:MM-HH:MM`(자정 넘김 됨), 짝수 바퀴 점검은 학습이 아니라 `--check-anytime` 이면 창 밖에서도(언리얼·메모리 조건은 그대로).
1. 묶음 결정 수·조각 수는 C0-9 로 등록한다(STATUS 3절, `bundle_decisions.json`·YAML `train`). 등록한 뒤 바꾸지 않는다 — **11-12 S′ 로 다시 등록했다(STATUS 3-1, 조각 3·동시 6·프로세스 0.5 GB).**
2. 차례 확인: `python results/v3/r9/league_r9.py --dry-run --plan-rounds 2 --decisions-json results/v3/r9/bundle_decisions.json`
3. 띄우기: `powershell -ExecutionPolicy Bypass -File results/v3/r9/launch_league.ps1 -DecisionsJson results/v3/r9/bundle_decisions.json -Rounds 10 -Window 22:00-09:00 -CheckCmd "results/v3/r9/eval_r9.py check --round {round} --branches {branch} --league-state {state} --preview-seeds 44200 44249"`
   - **C0-10 부터 한 번에 (밤 실행기)**: 같은 명령에 `-Night` 를 붙이면 `run_night.py` 가 뜬다 — 밤 창 안에서 C0-10 짧은 학습(먹이 넷 → 늑대 둘) → 잼(확인 시드) → γ 고르기
     (9-1 + 11-12 등록 조건) → `calib/C0_STATE.json` 에 γ·F → 고른 γ·F 를 `configs/v3_r9.yaml` 에 옮겨 적고(`--no-write-config` 면 다를 때 멈춤) → 같은 인자로 리그 + 지켜보기.
     떨어지면(먹이 둘 다 → 대비책 F 한 번 다시, F 를 이미 C0-11 에서 걸었으면 멈춤 / 늑대만 → 멈춤 — 처방 '0 바퀴 첫 10M 늘 먹기 먹이 100%' 는 리그에 아직 없음 /
     음성 대조 늑대가 통과 → 멈춤) `calib/C0-10_FAIL.md`·`logs/progress.md` 에 적고 멈춘다. 보정 관문 확인(`--phase confirm` 이 confirmed)·C0 값 옮겨 적기
     (C0_STATE 값이 YAML 과 같음 — C0-10 γ 자신 빼고; 잼도 같은 검사)·S′ C0-9 등록(`speed_dps`)이 없으면 띄우지 않는다. 계획 보기: `python results/v3/r9/run_night.py --dry-run`.
     멈춤 셋: 띄우기 전 조건이 안 맞음 = 단계 그대로(맞추고 다시 띄우면 이어 감) · 잼·리그 띄움 실패 = 다시 띄우면 그 단계부터 · 사람이 볼 멈춤(NaN·오류, 끊김 반복,
     고르기 멈춤, `--no-write-config` 옮겨 적기) = 고친 뒤 `run_night.py --resume-from {train,eval,choose,league}`. 학습·잼·리그 모두 `--config` 파일을 읽는다.
   (조각 수·프로세스 상한·프로세스 메모리는 YAML·기본값이 STATUS 등록 값이다: 늑대 조각 `train.wolf_shards`, `-MaxProcs 6`, `-ProcMemGB 0.5`.)
4. 보기: `python results/v3/r9/watch_r9.py --once` → `results/v3/r9/logs/progress.md`. 사건 `logs/league_events.log`, 화면 `logs/league.log`·`logs/train_<실행>.log`.
5. 10 바퀴 끝에 리그가 멈춘다(`halted: rounds_done`). 멈춤 규칙(9-4)을 점검 시드로 본 뒤 `-Rounds 12` 처럼 늘려 다시 띄우면 상태 파일에서 이어 간다(최대 18).

- 리그가 죽어도 학습 프로세스는 돈다(작업 묶음 밖). 다시 띄우면 도는 묶음을 기다리고(두 벌 막음), 끝 기록 없이 끝난 묶음은 시작 사본에서 처음부터 다시 돌린다.
- 일시 실패(커밋 메모리 바닥의 MemoryError, 조각 작업 프로세스가 죽음·파이프 끊김·120 초 안에 안 열림)는 끝 기록 `stop: cut` → 리그가 같은 묶음을 시작 사본에서 다시 돌린다.
  NaN·그 밖의 오류는 `stop: nan|error` → 리그가 멈추고 사람이 본다(같은 시드면 같은 실패). `--max-attempts 3` = **띄움 최대 3 번(처음 포함, 다시 2 번)**.
- 언리얼 에디터·UBT·ShaderCompileWorker 가 돌면 리그는 띄우지 않고 기다린다(끄지 않는다). 남은 커밋 메모리가 `1.5 × 0.5 GB × 띄울 프로세스 + 6 GB` 보다 적어도 기다린다.
- 짝수 바퀴 점검(8-5)은 `--check-cmd` 에 `{branch}` 를 넣으면 갈래 A·B 를 **동시에** 따로 돈다(두 결과가 모이면 멈춤 규칙 9-4 를 함께 쓴다). 미리 보기 세계 수는 STATUS 등록 값(50 세계 = 44200~44249).
- 처방(9-4, 갈래 안에서만): 상태 파일 `prescriptions.<갈래>` 에 `{"from_round": r, "shares": {"current": 0.4, "past": 0.4, "rule": 0.2}}` 를 더하면 그 바퀴부터 상대 몫이 바뀐다.
- C0-10(γ 두 후보 짧은 학습) 명령은 `eval_r9.py calibrate --gates C0-10 --c010-commands`(= `eval_r9.c010_plan`, 밤 실행기가 쓰는 것과 같음):
  `train_r9.py --species deer --branch C0_10_g0997 --model-seed 0 --round 0 --decisions 20000000 --wall-hours <2 × 어림> --gamma 0.997 --run-name r9_c010_g0997_deer
  --out ckpt/r9/c010 --log-dir results/v3/r9/logs` (0 바퀴 상대 몫이 이미 규칙·늑대 묶음은 규칙 70%·늘 먹기 30% 다. 늘 먹기 100% 는 `--shares '{"*": {"always_eat": 1.0}}'`).
  벽시계 상한·어림은 `bundle_decisions.json` 의 `speed_dps.round0`(S′ C0-9 등록) — 없으면 11-11 값 ÷ 2.3 [어림].

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
