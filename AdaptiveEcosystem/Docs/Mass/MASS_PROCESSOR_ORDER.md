# MASS PROCESSOR EXECUTION ORDER & THREAD SAFETY

> 기준 엔진: **Unreal Engine 5.8**  
> 모듈: `AdaptiveEcosystem`  
> 참조 C++ 헤더: `AdaptiveEcosystem/Source/AdaptiveEcosystem/Mass/EcoMassFragments.h`

---

## 1. Processor 명시적 파이프라인 (Execution Order)

아래 도식은 전체 생태계의 목표 파이프라인이다. 현재 M3.3 Box 관찰 경로의 실제 실행 순서는 다음 절을 따른다. 아직 보류된 Energy/사망/PPO 연결까지 구현되었다는 의미가 아니다.

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

## 3. M3.3 Box 관찰 경로의 실제 경계

1. **OnWorldPreActorTick / GameThread, Mass가 processing 중이 아닐 때:** 기존 완료 Transform(이전 프레임 엔진 이동 결과)을 사용할 수 있다. World 시계를 전진하고 최대 0.25초 자원 단계를 Phase/이벤트/스폰/소비/이주 판단/요약 기한에서 분할한다. 프레임당 catch-up은 최대 8단계다.
2. **각 단계:** 현재 Mass 집계 → 환경/수동 Starvation 이벤트 → 스폰 → Resident의 소비 수집/배분/결과 적용 → `CompleteResourceStep`. Traveling/Waiting은 소비 예약 조회와 요청에서 제외한다.
3. **같은 단계의 자원 완료 이후:** World 공간 snapshot과 동일 Epoch/Step/Time의 완료 Food를 검증하여 `EcoMassMigration::Reconcile`을 실행한다. 후보 선택/목적지 재평가는 기본 1초마다, 도착 검사는 각 완료 단계마다 한다. 최근 Transform이 목표 반경과 Bounds 내부를 동시에 만족하고 목적지에 Food가 있을 때 Region ID/index를 한 번에 commit한다. 다음 소비는 실제 처리시각+Interval이다.
4. **도착 commit 직후:** 기존 단일 집계 query로 Population/AverageEnergy/TravelingCount/WaitingCount를 재계산한다. 여행/대기는 마지막 commit Region에 집계하며 모든 지역(인구 0 포함)을 게시한다. 초기 완료 단계 및 매 1초에 World 시각+완료 Food+완료 Mass 집계를 하나의 `FEcoCompletedWorldSummary`로 GameState에 전달한다. 이는 해당 완료 경계의 요약이며 실시간 Transform 스트림과는 갱신 주기가 다르다.
5. **Mass PrePhysics:** `UEcoMigrationSteeringProcessor`는 ApplyForces 그룹 뒤, Movement 그룹 앞에서 실행된다. Travel Fragment만 읽어 목표까지 이번 프레임에 초과 이동하지 않는 DesiredVelocity를 쓴다. Resident/Waiting은 0이다. 다음 Movement 그룹의 엔진 `UMassApplyMovementProcessor`가 위치를 적분한다. 새 Transform의 도착 여부는 다음 자원 완료 경계에서 검사한다. 한 프레임의 catch-up 자원 단계마다 엔진 이동을 다시 실행하지 않는다.
6. **표현/복제:** 엔진 Representation이 위치를 표시하고, PostPhysics의 기존 MassReplication/MassReplicator/Bubble 경로가 PrePhysics 이동 이후 Transform 및 마지막 commit Region을 전달한다. GameState 요약의 RepNotify는 같은 속성 묶음의 시간/지역만 소비하며 Client는 자원/이주를 재계산하지 않는다. 서버 Debug는 Mass 조회에서 값만 수집한 뒤 query 밖에서 그린다. Client 지역 표시는 수신 GameState 요약으로 그린다.

Mass의 이주 상태는 `FEcoTravelFragment::State` enum 하나다. `FEcoMigratingTag`/별도 bool을 갱신하지 않고 Entity를 생성·파괴하지 않으므로 이주 pass에는 구조적 변경 및 Deferred flush가 필요 없다. Feeding Apply가 모두 끝난 다음 이주를 수행하고, pending 소비가 남으면 실패하여 중복 적용을 차단한다. 스폰은 기존 CreationContext 해제 이후 완성된 Fragment를 노출한다.

이 경로의 이동 query는 Authority+Alive와 서버 이동 Fragment를 요구하며 ClientProxy를 배제한다. Client `Eco Network Agent` 템플릿은 이 이동 Fragment/CodeDrivenMovement Tag를 추가하지 않는다. 다른 Trait에서 추가하더라도 새 조향 query의 Authority 조건을 충족하지 않는다. M3 Bootstrap은 PPO Herbivore/Custom/Spring Movement 및 Simulation LOD 혼용을 거부하여 중복 위치 작성과 Off simulation LOD의 이동 정지를 방지한다. Visualization/Replication LOD는 기존대로 유지한다.
