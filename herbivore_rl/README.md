# herbivore_rl

초식 몬스터 행동 정책 학습. 사양서는 `herbivore_policy_spec.md` (저장소 밖, 프로젝트 루트 상위).
아래 §는 전부 그 사양서의 절 번호다.

**현재 상태: Phase 1~6 전부 진행 완료. §6.6 만 미달 — §11-B 판단 대기 중.**

> **파이썬 → 언리얼이 끝까지 돈다.** 학습 가중치를 C 헤더로 내보내고, 실제 UE 5.8
> 모듈에서 빌드하고, 엔진 자동화 테스트 3개를 통과했다 — 골든 벡터 100쌍 최대 오차
> **1.192e-07** (기준 1e-5). 모델을 새로 학습해 다시 내보내도 반복 통과한다.
>
> 조향도 마찬가지다 — §3.3 수식을 `EcoSteering.h` 로 빼서 파이썬 `steer()` 와
> 골든 100쌍을 대조한다 (최대 오차 **1.788e-07**, 도주 분기 32개 포함).
>
> §6.6의 "+20%" 는 미달이다. §4.4 완화(§11-B 결정) 후 부호는 뒤집혔지만
> (−1.5% → 2M에서 **+11.2%**), 목표에는 못 미친다. 그리고 **2M 모델이 10M 모델보다
> 낫다** — 근거는 [docs/phase3_ppo_findings.md](docs/phase3_ppo_findings.md) §6.

> **전체 과정과 결론은 [docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md) 에 정리돼 있다.**
> Phase 1~6 각 단계의 판단, 사양서를 고친 3건과 그 사유, 최종 수치, 남은 한계.

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
| `export_weights.py` | §8.1 가중치 → C 헤더. **언리얼 모듈에 자동 복사** |
| `tests/cpp/parity_main.cpp` | 엔진 없이 g++ 로 §9.8-1·§9.8-2 파리티를 재는 하네스 |
| `evaluate.py` | §7 비교 평가. `results/compare.{csv,md}` 생성 |
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

## 파이썬 → 언리얼

```bash
python export_weights.py
```

`export/` 에 헤더를 만들고 **동시에** `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/`
에 복사한다. 손으로 옮기지 않는다 (§12).

| 언리얼 쪽 파일 | 내용 |
|---|---|
| `AI/Policy/EcoPolicyInference.h` | §9.3 `RunPolicy`. **엔진 비의존** (`<cmath>` 만) — 그래서 gcc로도 검증된다 |
| `AI/Policy/EcoSteering.h` | §3.3 `Steer()`. 역시 엔진 비의존. 경계 반발은 여기 없다 (언리얼 전용 항) |
| `AI/Policy/EcoPolicyInference.cpp` | §5.1 `RunUtilityPolicy` 를 C++로 |
| `AI/Policy/EcoBehaviorFragments.h` | §9.2 태그 + 공유 설정 + 기하 캐시 |
| `AI/Policy/EcoWorldProviders.h/.cpp` | §9.4 월드팀 인터페이스 + 더미 구현 |
| `AI/Policy/EcoNeighborhoodSubsystem.h/.cpp` | 이웃 조회 (균일 격자) |
| `AI/Policy/EcoRegionPredationSubsystem.h/.cpp` | §9.6 전역 피식 EMA(관측 5) + SaveGame |
| `AI/Policy/EcoBehaviorProcessors.h/.cpp` | §9.4 Policy + §9.5 Steering (+ 게더·지각) |
| `AI/Policy/PolicyWeights.h` | 자동 생성 (7-64-64-4) |
| `AI/Policy/UtilityParams.h` | 자동 생성 (§5.2 튜닝 계수) |
| `AI/Policy/EcoBehaviorConfig.h` | 자동 생성 (§9.7 단위 대응) |
| `AI/Policy/PolicyGoldenVectors.h` | 자동 생성 (§9.8-1 검증용 100쌍) |
| `AI/Policy/SteeringGoldenVectors.h` | 자동 생성 (§9.8-2 검증용 100쌍) |
| `AI/Policy/Tests/EcoPolicyInferenceTest.cpp` | 엔진 내 자동화 테스트 5개 |

프로세서 실행 순서 (§9.5 "Policy → Steering → Mass 이동"):

```
NeighborhoodGather  (매 틱)  개체 위치 색인
  → Perception      (매 틱)  §3.3 기하 입력
  → Policy          (0.133초마다, 시간 기준) 관측 7개 → RunPolicy/RunUtilityPolicy → 행동 4개
  → Steering        (매 틱)  §3.3 조향 → 속도, 위치 적분, 바라보는 방향(yaw)
  → Predation       (매 틱)  포획 판정, 생존 수 보고, 0.133초마다 피식 EMA 스텝
  (초식 쿼리는 전부 FEcoAliveTag 를 요구한다. 잡히면 Alive → PendingDeath)
```

콘솔 변수 `eco.UseLearnedPolicy` 로 학습 정책(1)과 §5.1 Utility 비교군(0)을 바꾼다.

엔진 자동화 테스트 실행:

```bash
"C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" <절대경로>/AdaptiveEcosystem.uproject "-ExecCmds=Automation RunTests AdaptiveEcosystem.Policy" "-testexit=Automation Test Queue Empty" -unattended -nopause -nosplash -NullRHI -log
```

빌드·테스트:

```bash
"C:/Program Files/Epic Games/UE_5.8/Engine/Build/BatchFiles/Build.bat" AdaptiveEcosystemEditor Win64 Development -Project=<절대경로>/AdaptiveEcosystem.uproject
```

> **UE 5.8.3 에서 확인했다.** 팀 에셋은 5.8.2·5.8.3 으로 저장돼 있다. 정식 5.8.0 보다
> 이전 빌드에서는 에디터가 시작 직후 꺼지고(Bridge·Fab 플러그인 로드 실패) `Content/` 에셋이
> `Custom version is too new` 로 안 열린다. Epic Games Launcher 에서 5.8 을 최신 핫픽스로
> 업데이트한다.

## §7 비교 평가 결과

```bash
python evaluate.py
```

시드 10000~10019 × 5000스텝, `deterministic=True` (§7.1). 산출물은 `results/`.

| 정책 | mean_return |
|---|---|
| random | 66.5 |
| utility (§5.2 튜닝) | 145.9 |
| **learned (2M)** | **164.4** |
| learned (10M, 폐기) | 149.6 |

**학습 정책이 규칙 기반 비교군을 네 성능 지표 전부에서 유의하게 이긴다**
(mean_return t=+4.24, survival t=+3.84, repro t=+4.12, predation_rate t=−2.44).
행동도 유의하게 다르다 — 점수 차이가 행동 차이에서 온다.

§11-B 결정으로 본 학습량을 10M → **2M** 으로 정정했다 (스펙 §6.3 에 사유·측정표 기록).
이 환경에서 PPO 는 2M 근처가 정점이고 그 이상은 과학습이다 — 10M 모델은 도주를 거의
포기한다 (`flee_dist` 0.379 → 0.201).

## 남은 한계

**§6.6 의 "모방 초기화 대비 +20%" 는 여전히 미달이다 (+11.2%).** 그 기준 자체는 고치지
않았다 — 달성 못 한 것을 달성한 것처럼 만들지 않기 위해서다 (§0).
근거: [docs/phase3_ppo_findings.md](docs/phase3_ppo_findings.md) §6.
