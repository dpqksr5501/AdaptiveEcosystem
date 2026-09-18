# 01. 기반 아키텍처 및 Mass 설계 (Original Architecture & Mass Design)

> 본 문서는 프로젝트 초기 수립된 아키텍처 계층 원칙과 대규모 군집(MassEntity) 시뮬레이션 기본 설계의 핵심 가치를 보존한 문서입니다.  
> 최신 PPO 동적 생태계 사양은 [Docs/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md](../PPO_MASS_ECOSYSTEM_ARCHITECTURE.md)를 참조하십시오.

---

## 1. 최상위 계층 분리 원칙

```text
┌────────────────────────────────────────────────────────┐
│ 1. WORLD / LEVEL                                       │
│    - 공간 및 환경 파라미터(날씨, 낮밤, 지형 볼륨) 제공   │
│    - 생태 결정권 없음                                  │
└───────────────────────────┬────────────────────────────┘
                            │ FRegionEnvironmentState
                            ▼
┌────────────────────────────────────────────────────────┐
│ 2. SERVER ECOLOGY / MASS RUNTIME                       │
│    - 논리 생태계 및 대규모 개체의 유일한 권위(Authority)│
│    - 자원 분배, 피식 기록, 개체군 집계, 이주 결정      │
│    - MassEntity 기반 초경량 논리 시뮬레이션            │
└───────────────────────────┬────────────────────────────┘
                            │ StableAgentId / Snapshot
                            ▼
┌────────────────────────────────────────────────────────┐
│ 3. CREATURE RUNTIME (Representation)                   │
│    - ACreatureCharacter                                │
│    - 카메라 근거리 / 중요 개체에 한해 선택적 액터 표현 │
│    - 렌더링, 애니메이션, 충돌 처리                     │
└────────────────────────────────────────────────────────┘
```

### 핵심 책임 경계
1. **World**: 지리적 경계와 물리적 환경(`FRegionEnvironmentState`)만을 제공하며, 개체의 생존/사망/이동을 직접 결정하지 않습니다.
2. **Server / Ecology**: 시뮬레이션의 최종 권위자입니다. 모든 자원 잔여량, 개체 상태, 피식 기록은 서버에만 존재합니다.
3. **Creature Runtime**: 결정자가 아닌 **표현자(Presenter)**입니다. 서버 또는 Mass로부터 확정된 스냅샷(`FCreatureSpawnData`)을 받아 시각적으로 표출할 뿐 내부 생태 로직을 알지 못합니다.

---

## 2. MassEntity 초기 설계 및 원칙

### 1) 논리 개체(Logical Creature)와 액터의 분리
- 수천~수만 마리의 개체를 모두 `ACharacter`(SkeletalMesh, AnimBP, AIController)로 생성하면 심각한 성능 저하가 발생합니다.
- 따라서 **원거리 개체는 MassEntity(데이터 청크)**로만 연산하고, **플레이어 주변의 근거리 개체만 ACreatureCharacter로 스왑(Representation)**합니다.
- 이 과정에서 개체의 신원은 `StableAgentId`(`int64`)를 통해 완벽히 보존됩니다.

### 2) 자원 분배 공식 (Resource Allocation Framework)
동시 다발적인 자원 소비 경쟁 상태(Race Condition)를 방지하기 위해 단일 프레임 4단계 분배 파이프라인을 사용합니다:

```text
1. 가용 자원 계산:
   Available = Clamp(Resource + RegenPerSec * dt, 0, Capacity)

2. 총 요구량 집계 및 축소 비율:
   Scale = (RequestSum > 0) ? Min(1.0, Available / RequestSum) : 0.0

3. 개체별 배분:
   Grant_i = Request_i * Scale

4. 차감 및 에너지 반영:
   ResourceNext = Available - Sum(Grant_i)
   EnergyNext_i = Clamp(Energy_i + Efficiency * Grant_i - Metabolism_i * dt, 0, MaxEnergy)
```

### 3) 이주 판단 (Migration Score)
개체는 주변 자원 고갈 및 포식 위험도에 따라 다른 지역으로의 이주를 평가합니다:
$$\text{Score}(h) = w_{\text{food}} \cdot \text{ExpectedFood} - w_{\text{risk}} \cdot \text{Risk} - w_{\text{travel}} \cdot \text{TravelCost} - w_{\text{crowd}} \cdot \text{Crowding}$$
- 진동(Oscillation) 현상을 막기 위해 최소 체류 시간(Minimum Stay)과 불감대(Hysteresis)를 적용합니다.

---

## 3. Simulation LOD 정책

거리 및 중요도에 따라 틱 빈도를 차등 적용하여 CPU 부하를 제어합니다:

| 처리 항목 | 실행 빈도 기준 | 비고 |
| :--- | :---: | :--- |
| **자원 재생 / 환경 상태 / 지역 통계** | 1 Hz | 저주기 백그라운드 연산 |
| **근거리 Mass 조향 및 이동** | 10 Hz | 부드러운 움직임 보장 |
| **중거리 Mass 개체 연산** | 2 Hz | 중간 수준 갱신 |
| **원거리 순수 논리 연산** | 0.5 Hz | 최소한의 생명주기/자원 소모만 유지 |
| **액터 Representation 전환** | $\le 0.2$s 반응 | 시야 진입 시 즉각 액터화 |
