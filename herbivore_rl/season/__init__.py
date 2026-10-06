"""시즌 재학습 사이드트랙 SR1 코드 (계획서 `Docs/RL_Policy/RL_SEASON_RETRAIN_PLAN.md`, 이하 SEASON).

SEASON 4.1 의 원칙대로 새 파일만 둔다. `train.py`, `train_v2.py`, `diagnose_v2.py`, `export_weights.py`, `env_v2/*` 는
고치지 않고 함수만 가져다 쓴다. 가져다 쓰는 함수의 서명은 `tests/test_season_signatures.py` 가 고정한다.

모듈:
- `common`: 경로, 앵커 두 개와 sha1, 평가·보류 시드, 시즌 설정 읽기(허용 키 검사), 실행 이름
- `mixed_vec_env`: G 세계 4개 묶음과 B 세계 4개 묶음을 이어 붙인 학습 VecEnv (SEASON 4.1 분포)
- `train_season`: 앵커에서 이어 학습한다. 방식 M0~M3 (SEASON 5.4). 앵커 KL 항은 SB3 `PPO.train()` 을 덮어쓴다
- `eval_worlds`: G·Ge·B 세계 설정, 판정 평가 묶음(SEASON 4.2), 평가 행 캐시
- `gate`: 채택 판정 A1~A5, 보류 시드 재확인, SR1 통과 규칙 (SEASON 4.2, 5.4)
- `sr1`: SR1 실행기. `--dry-run` 이면 잡 목록과 계산 추정만 낸다
- `seasons/`: 합성 시즌 (a)(b)(c) 설정 (SEASON 5.4)

실행은 `herbivore_rl/` 에서 `python -m season.<모듈>` 로 한다.
"""
