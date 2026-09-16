# 04. Server / Mass / Network Implementation Guide

이 문서는 장원준 담당 문서의 핵심 기술을 팀 프로젝트에 통합한 실행 가이드다.

## 1. 목적

Server 계층은 다음을 동시에 만족해야 한다.

- 논리 생태 상태의 단일 Authority
- 많은 개체를 Actor-per-agent보다 저비용으로 유지
- 근거리만 active Actor로 표현 가능
- 원거리 Simulation이 계속 진행
- 최소 Replication
- 상태 전환 후 ID/HP/Energy 일관성
- 성능 측정 가능

---

## 2. Mass 초기 상태

첫 Mass 실험:

```text
100 Entities
1 Species
2 Habitats 또는 Forest_A 내부 두 sub-area
Forage / Travel / Rest
```

초기 Fragment 후보:

```text
FEcoIdentityFragment
FEcoVitalsFragment
FEcoHabitatFragment
FEcoTravelFragment
FEcoSimulationLODFragment
FEcoRepresentationStateFragment
FEcoLastUpdateFragment
```

Mass를 팀 프로젝트의 모든 시스템에 노출하지 않는다.
공개 API는 Stable ID + plain USTRUCT 위주다.

---

## 3. Resource / Energy

공통 1Hz 후보:

```text
available = clamp(resource + regenPerSec*dt, 0, capacity)
scale = requestSum > 0 ? min(1, available/requestSum) : 0
grant_i = request_i * scale
resourceNext = available - sum(grant_i)
energyNext_i = clamp(energy_i + efficiency*grant_i - metabolism_i*dt, 0, 100)
```

공유 자원을 worker가 임의로 직접 차감하지 않는다.
Request → reduction → final allocation → apply 단계로 분리한다.

---

## 4. Migration/Habitat score

```text
Score(h)
= foodWeight * expectedFoodPerAgent
- riskWeight * risk
- travelWeight * travelCost
- crowdWeight * crowding
+ habitatPreference
```

목표 변경에는 threshold/minimum stay/hysteresis를 둬 oscillation을 피한다.

팀 프로젝트의 `MigrationTendency`, Player Pressure, World Environment가 이 score에 영향을 줄 수 있다.

---

## 5. Simulation LOD 초기 정책

초기 실험값:

| 계산 | 빈도 후보 |
|---|---:|
| Resource/Energy/Region pressure | 1Hz |
| Near logical movement | 10Hz |
| Mid | 2Hz |
| Far | 0.5Hz |
| Representation candidate | <= 0.2s 반응 목표 |

숫자만 바꾸는 것이 아니라 실제 Processor 실행 횟수가 줄어드는지 counter로 검증한다.

비교 지표:
- Region distribution error
- Average Energy error
- Resource error
- Reaction delay
- Travel completion bias

---

## 6. Representation correctness

필수 검증:

- 같은 StableAgentId Actor 중복 0
- activation/release 반복 후 logical population 보존
- 피해 후 멀어졌다 재접근해도 같은 HP
- death/activation race에서 death 1회
- reset 후 old callback reject
- stale ControlEpoch update reject

상태 예:

```text
Inactive
→ Requested
→ Active
→ ReleaseRequested
→ Inactive

Requested/Active → Failed or Dead
```

---

## 7. Network

### Active actor

일반 Unreal replication/CharacterMovement 사용.

전송:
- StableAgentId
- Transform/Movement
- HP/Combat
- SpeciesId/ProfileRevision

### Region/Species Summary

저주기 객체 또는 GameState component.

전송:
- WorldEpoch / SummaryRevision
- Population
- Resource / Risk / AverageEnergy
- Species Profile Revision/Profile

### Client가 받지 않는 것

- all entity transforms
- Mass fragment raw state
- LLM raw output
- Utility internals

---

## 8. State ownership

| 상태 | Writer |
|---|---|
| Energy / Habitat target / alive | Server Runtime |
| HP logical result | Server Runtime confirmed event |
| Resource / Risk | Server Runtime |
| logical Position/travel | Runtime/Mass |
| Actor visual transform | Representation/Character replication |
| Species Profile | Evolution commit |
| Visual morphology | Creature derived |

Actor가 피해 의도를 제출할 수 있지만 최종 HP는 Server가 확정한다.

---

## 9. Performance / Memory

반드시 기록:

```text
sizeof(each fragment)
500 / 2K / 10K / 25K entity memory
Processor timings
LOD execution counts
active actor spikes
```

Hot/Cold 분리 검토.

Parallel 실험은 먼저 profiling으로 병목을 찾고, 1순위 후보는 resource demand aggregation.

비교:

```text
Sequential
vs Parallel
```

작은 규모에서 느려져도 결과를 숨기지 않는다.
Break-even 규모를 찾는 것이 목표다.

---

## 10. Server/AI 연결점

Server가 제공:

### Evolution LLM
- `FEvolutionContext`

Server가 받음:
- `FEvolutionProposal`

### Simulation Policy AI
- `FSimulationAIObservation`

Server가 받음:
- `FSimulationPolicyProposal`

AI는 Server internals를 직접 읽지 않는다.

---

## 11. 첫 3개 마일스톤

### S1 — 100 Mass Entity standalone
- stable id
- resource/energy
- simple travel
- summary

### S2 — Representation
- near actor activation
- HP/ID preservation
- duplicate prevention

### S3 — Network
- listen server + client
- active actor replication
- region/species summary sync

그 다음 Evolution/Profile/AI와 결합한다.
