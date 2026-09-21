# herbivore_rl

초식 몬스터 행동 정책 학습. 사양서는 `herbivore_policy_spec.md` (저장소 밖, 프로젝트 루트 상위).
아래 §는 전부 그 사양서의 절 번호다.

**현재 상태: Phase 1 (학습 환경) 완료.**

## 설치

```bash
pip install -r requirements.txt
```

Python 3.10+ (개발·검증 환경 3.13.5). `marl-aquarium` 은 **필요 없다** — §11-A 판단으로
자체 World를 쓴다. 근거: [docs/aquarium_notes.md](docs/aquarium_notes.md) §7.

## 확인

```bash
python -m pytest tests/ -q
```

```bash
python -m env.bench
```

```bash
python replay.py --policy random
```

## 구조

| 경로 | 내용 |
|---|---|
| `configs/default.yaml` | 파이썬·언리얼 공유 상수 (§9.7). **상수는 여기에만 적는다** |
| `env/config.py` | yaml 로더. `cfg.see_r` 처럼 속성으로 읽는다 |
| `env/world.py` | 환경 본체 (§4). N=128 슬롯 고정, 전부 numpy 벡터 연산 |
| `env/steering.py` | §3.3 조향 참조 구현. **언리얼 C++(§9.5)와 한 줄씩 대응한다** |
| `env/bench.py` | 속도 측정 (§4.6) |
| `replay.py` | 리플레이 영상 (§4.6) |
| `tests/` | §4.6 완료 기준 + 조향 계약 검증 |
| `docs/aquarium_notes.md` | §4.1 Aquarium 조사와 §11-A 판단 |
| `docs/phase1_env_calibration.md` | 스펙이 값을 안 정한 상수를 어떻게 정했는지 |

## 계약 요약

관측 7개 / 행동 4개 / 조향 수식 / 보상은 §3이 정한다. 이 저장소에서 바꾸지 않는다
(§11-D). 특히:

- `World.step()` 은 **항상 [0,1] 행동**을 받는다 (§1.3). (−3,3) → sigmoid 변환은
  Phase 3의 VecEnv 래퍼 책임이다.
- 관측 정규화는 **고정 상수**로만 나눈다 (§1.2). 포식자 수 M이나 개체 수 N으로
  나누지 않는다 — 언리얼에서 같은 상수를 써야 하기 때문이다.
- 도주 항은 다른 항을 **대체하지 않고 더한다** (§3.3). 대체하면 도망칠 때 무리가 흩어진다.
- 학습 시드 0~999, 평가 시드 10000~10019 (§3.5). 섞지 않는다.

## 다음

Phase 2 (§5): `policies/utility.py`, `tune_utility.py`, `configs/utility_best.yaml`.
시작 전에 [docs/phase1_env_calibration.md](docs/phase1_env_calibration.md) §4의 남은
한계를 읽을 것.
