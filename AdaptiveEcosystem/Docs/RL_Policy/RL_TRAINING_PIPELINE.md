# RL TRAINING & POLICY EXPORT PIPELINE

> 환경: **Python 3.10+**, **PyTorch**, **Stable-Baselines3**, **PettingZoo**  
> 위치: `Tools/RL/`  
> 연계 문서: [POLICY_CONTRACT_V1.md](POLICY_CONTRACT_V1.md)

---

## 1. 개요 및 저장소 분리

강화학습 훈련 환경과 에이전트 코드는 Unreal 엔진 소스 코드와 분리되어 `Tools/RL/` 경로에 독립된 Python 패키지로 관리됩니다.

```text
Tools/
└─ RL/
   ├─ pyproject.toml
   ├─ README.md
   ├─ requirements.txt
   ├─ adaptive_ecosystem_rl/
   │  ├─ env/
   │  │  ├─ aquarium_adapter.py      # PettingZoo Multi-Agent -> Gymnasium VecEnv
   │  │  ├─ observation.py           # 7-dim observation normalization
   │  │  ├─ action_mapping.py        # 4-dim action range mapping
   │  │  └─ reward.py                # Multi-objective reward (Survival, Energy, Predation)
   │  ├─ training/
   │  │  ├─ train_ppo.py             # SB3 PPO 학습 스크립트
   │  │  └─ optimize_optuna.py       # Optuna 하이퍼파라미터 튜닝
   │  ├─ baseline/
   │  │  └─ utility_policy.py        # Utility Baseline 벤치마크
   │  ├─ eval/
   │  │  └─ evaluate.py              # 평가 시드 20개 기반 통계 수집
   │  └─ export/
   │     ├─ export_policy.py         # C++ 헤더/인라인 가중치 생성
   │     └─ generate_golden_vectors.py # Parity 검증용 Golden Vector 생성
   └─ tests/
      ├─ test_env_parity.py
      └─ test_export_weights.py
```

---

## 2. Aquarium Multi-Agent Adapter (PettingZoo ↔ SB3)

Aquarium 시뮬레이터는 PettingZoo 다중 에이전트 환경(AEC / ParallelEnv)을 제공합니다. Stable-Baselines3의 PPO 알고리즘을 단일 공유 정책(Parameter-Sharing Policy)으로 적용하기 위해 전용 Adapter를 구성합니다:

1. **Parameter Sharing**:
   - 모든 에이전트가 동일한 Actor-Critic 신경망을 공유하여 경험(Trajectory)을 수집합니다.
2. **사망 에이전트 처리 (Dead Agent Masking)**:
   - 포식 또는 기아로 사망한 개체는 배치 버퍼에서 마스킹되며, 리셋 시점에 재생성됩니다.
3. **Observation & Action Dimension**:
   - `Observation Space`: Box(0.0, 1.0, shape=(7,), dtype=np.float32)
   - `Action Space`: Box(-3.0, 3.0, shape=(4,), dtype=np.float32)

---

## 3. 보상 함수 설계 (Multi-Objective Reward)

단순 생존 시간(Survival time)만을 보상으로 주면 은신처에만 숨어 있는 퇴행적 정책(Degenerate Policy)이 형성됩니다. 따라서 다목적 보상을 적용합니다:

$$R_t = w_{\text{survival}} \cdot 1.0 + w_{\text{food}} \cdot \Delta \text{FoodConsumed} - w_{\text{energy\_drain}} \cdot (1.0 - \text{Energy}) - w_{\text{predation}} \cdot \mathbb{I}_{\text{predated}} - w_{\text{effort}} \cdot \|\vec{a}_t\|^2$$

- 배고플 때 먹이를 먹는 행동 장려
- 포식자 출현 시에만 은신/군집을 선택하도록 유도
- 불필요한 고속 기동 에너지 낭비 페널티

---

## 4. Policy Export 및 C++ Parity 검증

1. **가중치 익스포트 (`export_policy.py`)**:
   - 학습 완료된 Actor 신경망(Linear(7,64) -> Linear(64,64) -> Linear(64,4))의 가중치와 편향을 추출하여 정적 C++ 배열 인라인 헤더(`EcoPolicyWeights.generated.inl`)로 출력합니다.
2. **골든 벡터 생성 (`generate_golden_vectors.py`)**:
   - 100개의 고정된 랜덤 관측 벡터에 대해 Python PPO 추론 결과를 계산하고 JSON 파일로 저장합니다.
3. **Unreal C++ 테스트**:
   - C++ Automation Test에서 동일한 100개 벡터에 대해 네이티브 C++ 추론을 실행하고 허용 오차($\le 10^{-5}$) 내 일치 여부를 검증합니다.
