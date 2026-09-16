# 05. AI / LLM Boundary

## 1. AI 담당자가 먼저 해야 하는 일

모델부터 만들지 않는다.
각 AI 문제마다 다음 5개를 먼저 계약한다.

```text
1. Problem Definition
2. Input Schema
3. Output/Action Schema
4. Dataset/Prompt Schema
5. Evaluation Metric
```

---

# Part A. Creature Evolution LLM

## 2. 목적

플레이어와 환경이 만든 압력을 보고 **장기 Species Trait 변화 방향과 변화량**을 판단한다.

AI가 직접 Creature를 조종하거나 Mesh를 생성하지 않는다.

```text
Environment
+ Pressure
+ Population
+ Current Profile
     ↓
Evolution LLM
     ↓
Trait Delta Proposal
```

---

## 3. Input

`FEvolutionContext`

예 Feature:

- HuntingPressure
- EncounterPressure
- PursuitPressure
- ThreatPressure
- IntrusionPressure
- Day/Night pressure
- Food / Vegetation / Rainfall
- Population
- Current BodyScale/Speed/Fear/Aggression
- Generation

Raw kill log나 Actor reference를 모델에 직접 전달하지 않는다.

---

## 4. Output

구조화된 JSON 또는 같은 의미의 모델 output.

예:

```json
{
  "body_scale_delta": -0.03,
  "leg_scale_delta": 0.02,
  "move_speed_delta": 0.04,
  "fear_delta": 0.07,
  "aggression_delta": -0.05,
  "migration_delta": 0.03,
  "night_activity_delta": 0.05
}
```

중요:
- 개발자가 A/B/C Variant를 미리 고르는 구조가 아니다.
- AI가 허용된 continuous trait space에서 조합을 제안한다.
- 새 topology/mesh 생성은 하지 않는다.

---

## 5. Validator

LLM의 책임이 아니다. Server/Evolution layer가 수행.

검사:
- WorldEpoch/ContextRevision
- Schema/Model compatible
- parse success
- finite number
- min/max
- max delta
- mutation budget
- species constraints
- trade-off

실패 시 Dummy/Rule-based Provider로 fallback 가능해야 한다.

---

## 6. Evaluation

단순 문장 품질로 평가하지 않는다.

평가 후보:
- schema parse success rate
- valid proposal rate
- same context consistency
- pressure 변화에 대한 방향성 설명 가능성
- validator reject rate
- gameplay demo에서 변화가 식별 가능한가
- extreme trait output frequency

LLM prompt/model revision을 기록한다.

---

# Part B. Simulation Policy AI

## 7. 목적

현재 Simulation과 Server Runtime 상태를 보고 적절한 **Simulation Policy**를 추천한다.

```text
Simulation State
+ Runtime Metrics
+ Current Policy
    ↓
Policy AI
    ↓
Suggested PolicyId
```

Evolution LLM과 완전히 별개 문제다.

---

## 8. Feature Schema

모든 Feature에 정의:

- Name
- Meaning
- Unit
- Valid Range
- Missing Handling
- Normalization
- Schema Version

후보:
- EntityCount
- PopulationDistribution
- AverageEnergy
- Resource/Risk
- ProcessorCost
- ServerCPU
- ActiveRepresentationCount
- LOD distribution
- Observer count/distance summary
- CurrentPolicyId

---

## 9. Policy Schema

초기에는 discrete policy 권장.

```text
Policy 0: Quality
Policy 1: Balanced
Policy 2: Performance
...
```

Server가 PolicyId → 실제 Near/Mid/Far Hz 등으로 매핑한다.
모델이 arbitrary runtime knob를 직접 쓰지 않는다.

---

## 10. Dataset

Server가 같은 Observation Schema로 기록한다.

```text
Observation
AppliedPolicy
Outcome
```

Outcome 후보:
- CPU frame/processor cost
- simulation error
- reaction delay
- distribution error
- resource/energy error

Training과 Runtime은 **동일 Observation Schema**를 사용한다.

---

## 11. Offline / Runtime

### Offline — AI 담당
- dataset analysis
- preprocessing
- train/validation/test
- model training
- evaluation
- model export
- version metadata

### Runtime — Server 담당
- observation snapshot
- inference invocation
- async result queue
- proposal validation
- commit/fallback

---

## 12. Async / Version

Proposal에는 최소:

```text
ObservationId
WorldEpoch
ModelRevision
FeatureSchemaRevision
PolicySchemaRevision
SuggestedPolicyId
Confidence
```

Reset 후 old WorldEpoch proposal은 reject.
너무 오래된 observation도 Server 정책에 따라 reject.

---

## 13. Fallback

다음 경우 Rule-Based:

- load failure
- inference timeout
- invalid output
- version mismatch
- low confidence (정책에 따라)
- stale observation

AI가 실패해도 Simulation은 계속된다.

---

## 14. 최종 성공 기준

Policy AI는 반드시 쓰이는 것이 목표가 아니다.

비교:

```text
Fixed
vs Rule-Based
vs AI-Based
```

성공:
- 같은 quality에서 cost 감소
또는
- 비슷한 cost에서 quality 개선

차이가 없으면 Rule-Based 유지도 올바른 결론이다.
