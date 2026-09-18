# POLICY CONTRACT V1 — PPO & Baseline Specification

> 버전: **1.0.0**  
> 스키마 버전: `PolicySchemaVersion = 1`  
> 적용 엔진: **Unreal Engine 5.8** & **Python 3.10+ (Stable-Baselines3)**  
> 참조 C++ 헤더: `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoPolicyContracts.h`

---

## 1. 신경망 아키텍처 (Network Architecture)

```text
Input Layer (7) 
    ──[Linear 7 -> 64]──> Tanh 
    ──[Linear 64 -> 64]──> Tanh 
    ──[Linear 64 -> 4]──> Raw Action Logits (4)
```

- **공유 정책(Shared Policy)**: 월드의 모든 동일 종(Species) 개체는 동일한 가중치 행렬을 공유합니다.
- **활성화 함수**: 은닉층 전체에 `Tanh`를 사용합니다.
- **출력 처리 (Post-Processing)**:
  1. `Raw Logits` 클램프: `[-3.0, +3.0]`
  2. 시그모이드(`Sigmoid`) 적용: $\sigma(x) = \frac{1}{1 + e^{-x}} \in (0.0, 1.0)$
  3. 파라미터 매핑: 최종 `[0.0, 1.0]` 범위의 무차원 행동 가중치(Behavior Weight)로 산출.

---

## 2. 관측 공간 (Observation Vector V1 — 7 Dimensions)

모든 특징(Feature)은 `0.0 ~ 1.0`의 무차원 정규화 값으로 정의되며, 순서가 C++ 및 Python에서 엄격히 일치해야 합니다.

| Index | Feature Name | 물리적 의미 | 정규화 공식 | 결측/누락 처리 |
| :---: | :--- | :--- | :--- | :--- |
| **0** | `food_density` | 현재 에이전트 주변 반경 내 식생/먹이 풍부도 | $\text{Clamp}(\frac{\text{LocalFood}}{\text{FoodCapacity}}, 0, 1)$ | 0.0 |
| **1** | `predator_count` | 시야(`ViewDistance`) 내 감지된 포식자(플레이어/천적) 수 | $\text{Clamp}(\frac{\text{Count}}{\text{MaxPredatorCap}}, 0, 1)$<br>(기본 `MaxCap = 5`) | 0.0 |
| **2** | `predator_distance`| 가장 가까운 포식자와의 상대 거리 | $\text{Clamp}(\frac{\text{Distance}}{\text{ViewDistance}}, 0, 1)$ | 1.0 (시야 밖) |
| **3** | `conspecific_count`| 시야 내 감지된 동종(Conspecific) 개체 수 | $\text{Clamp}(\frac{\text{Count}}{\text{MaxFlockCap}}, 0, 1)$<br>(기본 `MaxCap = 20`) | 0.0 |
| **4** | `energy` | 개체의 현재 에너지 잔여량 | $\text{Clamp}(\frac{\text{CurrentEnergy}}{\text{MaxEnergy}}, 0, 1)$ | 0.0 |
| **5** | `recent_predation` | 개체가 속한 지역(`Region`)의 최근 포식 발생 이력 | $\text{RegionPredationHistory} \in [0, 1]$ | 0.0 |
| **6** | `cover_distance` | 가장 가까운 은신처(Shelter/Cover)와의 상대 거리 | $\text{Clamp}(\frac{\text{Distance}}{\text{CoverSearchRadius}}, 0, 1)$ | 1.0 (탐색 반경 밖) |

---

## 3. 행동 공간 (Action Vector V1 — 4 Dimensions)

직접적인 위치나 선속도(Velocity)를 출력하지 않고, **MassFlock 조향 엔진의 합성 가중치**를 출력합니다.

| Index | Action Name | 범위 | 의미 및 조향 영향 |
| :---: | :--- | :---: | :--- |
| **0** | `forage` | `[0.0, 1.0]` | 가장 가까운 먹이 자원 방향으로의 조향 가중치 |
| **1** | `cohesion` | `[0.0, 1.0]` | 주변 동족 중심점으로 모이려는 군집 응집 가중치 |
| **2** | `flee_dist` | `[0.0, 1.0]` | 포식자로부터 도망을 개시하는 거리 임계치 / 도주 민감도 |
| **3** | `cover` | `[0.0, 1.0]` | 가장 가까운 은신처(Cover) 방향으로의 대피 가중치 |

### 최종 조향 힘(Steering Force) 합성 공식:
$$\vec{F}_{\text{total}} = \vec{F}_{\text{separation}} + \vec{F}_{\text{align}} + (\text{cohesion} \times \vec{F}_{\text{cohesion}}) + (\text{forage} \times \vec{F}_{\text{forage}}) + (\text{flee\_dist} \times \vec{F}_{\text{flee}}) + (\text{cover} \times \vec{F}_{\text{cover}})$$

---

## 4. Utility AI 비교군 (Baseline Model)

PPO 정책의 성능을 객관적으로 비교하고 Fallback을 제공하기 위해 동일한 입출력 시그니처를 갖는 규칙 기반 Utility 수식을 정의합니다:

```cpp
FEcoPolicyActionV1 EvaluateUtilityBaseline(const FEcoPolicyObservationV1& Obs)
{
    FEcoPolicyActionV1 Action;
    // 1. 배고플수록 먹이 탐색 강화
    Action.Forage   = FMath::Clamp(1.0f - Obs.Energy, 0.0f, 1.0f);
    // 2. 포식 위험이 높을수록 동족 결속 강화
    Action.Cohesion = FMath::Clamp(Obs.RecentPredation * 0.8f + Obs.PredatorCount * 0.2f, 0.0f, 1.0f);
    // 3. 포식자가 가깝거나 최근 포식률이 높으면 도주 민감도 극대화
    Action.FleeDist = FMath::Clamp((1.0f - Obs.PredatorDistance) * 0.7f + Obs.RecentPredation * 0.3f, 0.0f, 1.0f);
    // 4. 포식자가 감지되면 은신처 이동 가중치 부여
    Action.Cover    = FMath::Clamp(Obs.PredatorCount * 0.8f + (1.0f - Obs.CoverDistance) * 0.2f, 0.0f, 1.0f);
    return Action;
}
```

---

## 5. Sim-to-Sim 검증 (Golden Vector Parity)

- Python Export 스크립트는 100개의 표준 테스트 입력 벡터와 이에 대한 Python deterministic 출력을 `GoldenVectors.json`으로 저장합니다.
- C++ Automation Test는 빌드 시 이 테스트 벡터를 로드하여 C++ 추론 결과와 오차를 비교합니다.
- 허용 오차 한계: $\max |Y_{\text{Python}} - Y_{\text{C++}}| \le 1 \times 10^{-5}$
