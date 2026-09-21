# herbivore_rl

초식 몬스터 행동 정책 학습. 사양서는 `herbivore_policy_spec.md` (저장소 밖, 프로젝트 루트 상위).
아래 §는 전부 그 사양서의 절 번호다.

**현재 상태: Phase 3 (PPO 학습) 코드 완료, §6.6 기준 미달 — §11-B 판단 대기 중.**

> §6.6의 "10M 후 모방 초기화 대비 +20%" 를 달성하지 못했다 (−1.5%). 측정 결과 이
> 환경에서는 **상태를 안 보는 고정 행동 하나가 튜닝된 Utility AI와 10M PPO를 둘 다
> 이긴다.** 네 정책의 차이가 전부 시드 잡음 안이다. 원인과 §11-B 선택지 검토는
> [docs/phase3_ppo_findings.md](docs/phase3_ppo_findings.md).

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

```bash
python tune_utility.py
```

```bash
python warmstart.py && python train.py --steps 10000000
```

튜닝 스크립트는 SQLite(`optuna_*.db`)에 붙으므로 중단해도 이어서 돈다.

> **Anaconda 주의.** MKL(numpy)과 torch가 Intel OpenMP 런타임을 두 벌 싣는다.
> torch를 쓰는 진입점은 `import env.torch_init` 을 **가장 먼저** 해야 한다
> (`train.py` / `warmstart.py` / `tune_ppo.py` 는 이미 그렇게 돼 있다).
> 안 하면 `OMP: Error #15` 로 죽는다. 이유와 대처는 `env/torch_init.py` 참조.

## 구조

| 경로 | 내용 |
|---|---|
| `configs/default.yaml` | 파이썬·언리얼 공유 상수 (§9.7). **상수는 여기에만 적는다** |
| `configs/utility_best.yaml` | §5.2 튜닝 산출. **자동 생성 — 손으로 고치지 말 것** |
| `env/config.py` | yaml 로더. `cfg.see_r` 처럼 속성으로 읽는다 |
| `env/world.py` | 환경 본체 (§4). N=128 슬롯 고정, 전부 numpy 벡터 연산 |
| `env/steering.py` | §3.3 조향 참조 구현. **언리얼 C++(§9.5)와 한 줄씩 대응한다** |
| `env/rollout.py` | 시드별 롤아웃 → §7.2 통계. 튜닝과 평가가 **같은 목표 함수**를 쓰게 하는 한 곳 |
| `env/vec_env.py` | §6.2 SB3 VecEnv. **(-3,3) → sigmoid 변환이 있는 유일한 곳** (§1.3) |
| `env/torch_init.py` | Anaconda OpenMP 충돌 대처. torch 쓰는 파일이 맨 먼저 import |
| `env/bench.py` | 속도 측정 (§4.6) |
| `policies/utility.py` | §5.1 비교군 수식 + §5.2 탐색 범위 |
| `policies/registry.py` | 정책 스펙(dict) → 콜러블. 워커 프로세스로 넘기려면 picklable해야 한다 |
| `tune_utility.py` | §5.2 Optuna 튜닝 |
| `warmstart.py` | §6.1 모방 초기화. `ckpt/warmstart.zip` + §6.6 기준선 json |
| `train.py` | §6.3 PPO + §6.5 행동 로깅. **PPO 설정의 유일한 출처** |
| `tune_ppo.py` | §6.4 하이퍼파라미터 탐색 (5개만. 구조는 탐색 금지) |
| `replay.py` | 리플레이 영상 (§4.6, §5.3) |
| `tests/` | §4.6 · §5.3 완료 기준 + 조향·수식 계약 검증 |
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

## 스펙에서 고친 것

§1.8에 따라 조용히 우회하지 않고 스펙 문서를 고쳤다. 지금까지 한 건:

- **§5.2 `k_coh` 탐색 범위 0~4 → 0~40.** §3.1 `recent_predation` EMA의 실측 범위가
  0~0.078이라 `cohesion = clip(k_coh × rp)` 가 k_coh=4에서 평균 0.109에 머문다.
  기존 범위로는 §5.3의 "랜덤 대비 2배"가 원리적으로 불가능했다 (상한 1.57배).
  §3.1 EMA 수식 자체는 §11-D에 따라 **바꾸지 않았다.**

## 다음

**Phase 4로 가기 전에 §11-B 결정이 필요하다.**
[docs/phase3_ppo_findings.md](docs/phase3_ppo_findings.md) §4의 선택지 검토를 읽을 것.
현재 상태로 Phase 4를 돌리면 `compare.md` 는 "차이 없음"이 된다 (§7.3이 허용하는
결과이긴 하다).
