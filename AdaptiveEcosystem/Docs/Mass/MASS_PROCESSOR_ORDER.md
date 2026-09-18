# MASS PROCESSOR EXECUTION ORDER & THREAD SAFETY

> 기준 엔진: **Unreal Engine 5.8**  
> 모듈: `AdaptiveEcosystem`  
> 참조 C++ 헤더: `AdaptiveEcosystem/Source/AdaptiveEcosystem/Mass/EcoMassFragments.h`

---

## 1. Processor 명시적 파이프라인 (Execution Order)

MassEntity 기반 동적 생태계는 프레임당 다음의 정밀한 순서로 처리됩니다. 상위 프로세서의 출력이 하위 프로세서의 입력으로 전달됩니다.

```text
[1. Eco.Environment/Region Update]
        │ Region 환경/날씨 및 리소스 재생 계산 (저주기)
        ▼
[2. Eco.Observation Processor]
        │ 주변 환경, 동족, 포식자, 자원, 에너지 수집 -> FEcoObservationFragment 갱신
        ▼
[3. Eco.Policy Processor]
        │ FEcoObservationFragment -> C++ Native Forward / Utility -> FEcoPolicyOutputFragment (저주기 or 매 N 틱)
        ▼
[4. Eco.Steering Processor]
        │ HashGrid 공간 조회 + Separation/Align + PPO 가중치(Forage, Cohesion, Flee, Cover) 합성 -> FMassForceFragment
        ▼
[5. Mass Movement Processor]
        │ 힘 적분 및 위치/속도 업데이트 (엔진 내장 MassMovement)
        ▼
[6. Eco.Interaction Processor]
        │ 먹이 도달 시 소비 요청 버퍼링, 포식 공격 판정
        ▼
[7. Eco.Vitals / Lifecycle Processor]
        │ 시간당 기본 에너지 소모, 섭취 에너지 반영, 기아/사망 판정 (사망 시 FEcoAliveTag 제거)
        ▼
[8. Eco.Migration Processor]
        │ 지역 자원 고갈 또는 과밀 시 다른 Region으로의 이주 상태(FEcoTravelFragment) 전이
        ▼
[9. Eco.Aggregation / Metrics Processor]
        │ 살아있는 개체수, 평균 에너지, 지역별 인구 집계 -> UEcologySimulationSubsystem 반영
        ▼
[10. Representation / LOD Processor]
        │ 카메라 거리에 따른 Actor 스폰/스왑 및 ISM 렌더링 LOD 조정
```

---

## 2. 멀티스레드 병렬 안전성 수칙 (Strict Concurrency Rules)

MassEntity는 태스크 그래프(TaskGraph) 상에서 여러 워커 스레드에 청크(Chunk) 단위로 병렬 디스패치됩니다. 다음 행위는 엔진 크래시를 유발하므로 엄격히 금지됩니다:

1. **Entity Loop 내부에서 UObject 직접 접근/수정 금지**:
   - `AEcologyRegion`이나 `UEcologySimulationSubsystem`의 메서드를 엔티티 청크 반복문 내부에서 직접 호출하지 않습니다.
2. **동기식 Food 차감 금지**:
   - 수백 마리의 엔티티가 동시에 지역의 `FoodAmount`를 깎으면 경쟁 상태(Data Race)가 발생합니다.
   - 엔티티는 소비 희망량(`FoodConsumptionRequest`)만 기록하고, 프레임 종료 전 단일 쓰레드 단계(`Aggregation / Reconciliation`)에서 지역 총량을 차감한 후 엔티티 에너지로 피드백합니다.
3. **구조적 변경(Archetype Mutation)은 Deferred Command Buffer 사용**:
   - 태그 추가/제거(`FEcoAliveTag`, `FEcoMigratingTag`)나 엔티티 파괴는 반드시 `FMassCommandBuffer`를 통하여 일괄 지연 실행합니다.
