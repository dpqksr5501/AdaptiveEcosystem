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
| `eval_r8.py` | `calibrate`(C0-1·2·4) · `leak`(C0-3) · `eval`(판정) · `bear`(곰 시험) |
| `r8_replay.py` | 위에서 본 궤적 PNG |
| `launch_train.ps1` | 본 학습 3 + 대조 1 을 떨어진 프로세스로 |
| `herbivore_rl/tests/test_r8.py` | 시험 11 개 |
| `calib/` | 보정 관문 기록 (`calibrate_design.json` = 설계 값, `calibrate.json` = 고친 값, `calibrate_<꼬리>.json` = 탐색) |
| `logs/` · `smoke/` | 학습 기록 · 스모크 점검 |

모든 명령은 `herbivore_rl/` 에서 `PYTHONUTF8=1`, 파이썬 `C:/Users/Sinhyeok/anaconda3/python.exe` 로 돌린다. 시드: 학습 41100~41399, 개발·보정 41400~41449,
학습 중 점검 41800~41839, 평가 41900~41999 (설계 11절).
