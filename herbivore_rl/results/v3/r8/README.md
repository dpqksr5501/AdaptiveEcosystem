# R8 — 위험을 스스로 배우는 사슴 (파이썬 파일럿)

설계: `AdaptiveEcosystem/Docs/RL_Policy/RL_R8_LEARN_DANGER_DESIGN.md`. 지금 상태: `STATUS.md`.

사슴 감각에 '늑대' 이름표가 없고(주변 동물을 같은 꼴로만 본다), 언제·어디로 도망할지를 두뇌가 정하며(도주 반사·마스크 없음), 보상은 생존·먹기뿐인 세계에서
처음부터 PPO 로 배운다. 늑대와 겉모습·평소 걸음이 같은 '해 없는 짐승'을 섞어, 두뇌가 경험(죽음)만으로 늑대를 더 피하게 되는지 본다.
언리얼 게임 두뇌(R7e)·기존 파이썬 세계(`env_v2/world.py`)와 무관한 새 세계다.

| 파일 | 내용 |
|---|---|
| `herbivore_rl/env_v2/r8_world.py` | 세계(관측 65·행동 11·보상·늑대·짐승·곰·다시 남·숨은 기록) |
| `herbivore_rl/env_v2/r8_vec_env.py` | SB3 VecEnv (세계 32 × 사슴 32, 엇갈린 교체) |
| `herbivore_rl/configs/v3_r8_pilot.yaml`·`v3_r8_pilot_h0.yaml` | 본 세계·대조(짐승 0) |
| `train_r8.py` | 학습 (`--config --seed --steps --wall-hours --run-name`) |
| `eval_r8.py` | `calibrate`(C0-1·2·4) · `leak`(C0-3, 탈진 나무 AUC 덧붙임) · `eval`(판정, 참고 기준 `rule_aim` 은 `--baselines` 로) · `bear`(곰 시험) |
| `r8_replay.py` | 위에서 본 궤적 PNG |
| `r8_replay_video.py` | 위에서 본 무대 애니메이션 mp4 (왼쪽 R8 · 오른쪽 늘 먹기, 같은 시드, 정한 규칙으로 장면 고름) + 포스터 PNG·곁 파일 JSON |
| `plot_talk.py` | 발표용 막대: 평가 summary.json → 잡힘 비·먹음 비·늑대/짐승 앞 도망 몫 (`--split` 칸마다 따로) |
| `launch_train.ps1` | 본 학습 3 + 대조 1 을 떨어진 프로세스로 (창 없음 — `spawn_detached.py` 를 거친다) |
| `spawn_detached.py` | 파이썬 스크립트 하나를 창 없는 콘솔·새 프로세스 묶음으로 띄우고 끝나는 띄우개, PID 를 `logs/pids.txt` 에 |
| `watch_train.py` · `launch_watch.ps1` | 밤새 지켜보기: 5 분마다 `logs/progress.md`(진행·이상 신호·25/50/75/100% 지점), 체크포인트 점검(점검 시드 41800~41839) `checkpoints/`, 곡선 다시 그리기 |
| `plot_curve.py` | `curve`(학습 곡선 `checkpoints/curve.png`, `--talk` 발표용 큰 글자 칸 셋) · `bands`(평가 summary.json → 거리 띠별 늑대/짐승 도망 막대) |
| `herbivore_rl/tests/test_r8.py` | 시험 12 개 |
| `leak_probe.py` | 학습 전 검토(11-05) 이름표 점검: 동물 칸 하나로 늑대·짐승을 숨은 상태별로 맞히는 나무 분류기 |
| `calib/` | 보정 관문 기록 (`calibrate_design.json` = 설계 값, `calibrate.json` = 고친 값, `calibrate_<꼬리>.json` = 탐색, `*review*` = 학습 전 검토 뒤 지금 설정) |
| `logs/` · `smoke/` · `checkpoints/` | 학습 기록(`aborted_1705/` = 17:05 에 창 닫힘으로 죽은 첫 판) · 스모크 점검 · 학습 중 체크포인트 점검(판정 아님) |

모든 명령은 `herbivore_rl/` 에서 `PYTHONUTF8=1`, 파이썬 `C:/Users/Sinhyeok/anaconda3/python.exe` 로 돌린다. 시드: 학습 41100~41399, 개발·보정 41400~41449,
학습 중 점검 41800~41839, 평가 41900~41999 (설계 11절).
