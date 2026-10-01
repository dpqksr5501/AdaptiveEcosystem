# M3.2 — 정기 소비·낮밤 이벤트·자원 조정

> 상위 계획: [M3 개발 계획](M3_IMPLEMENTATION_PLAN.md)  
> 선행: [M3.1 — 지역·낮밤·권위 스폰](M3_1_WORLD_AND_SPAWN.md)  
> 다음: [M3.3 — 실제 이주·표시·통합 검증](M3_3_MIGRATION_AND_VALIDATION.md)  
> 상태: 코드 구현 및 UE 5.8 Editor 빌드 성공 / PIE 검증 대기. 자동화 테스트는 사용자 요청으로 생략.
> 구현 상세·일일 개체 수 기준·수동 확인: [M3.2 에디터 테스트](M3_2_EDITOR_TEST.md)
> 예상 개발량: **1.5~2인일**

## 1. 목표와 완료 결과

Mass 개체의 존재 시간이 소비 요청을 만들고, Server가 공정하게 배분하여 Food를 차감한다. Day/Night 자원 감소 이벤트를 같은 조정 경로에 연결해 **소비 고갈과 이벤트 고갈을 각각 재현**한다.

이 단계에서는 개체가 고갈된 Region에 그대로 남아 있어도 된다. Food/원인/개체 수는 서버 로그로 검증하고 실제 이동과 Client 요약 표시를 M3.3에 인계한다. 고갈 전에 Entity를 죽여 이주 검증 대상을 없애지 않는다.

## 2. 선행 계약과 책임 분리

M3.1의 두 Region, 단일 시계, 실제 생성 시각/NextFeedTime, Alive/Authority Entity와 기본 집계를 사용한다. 별도 소비 Actor나 Player Timer를 만들지 않는다.

| 계층 | 이 단계의 책임 | 금지할 책임 |
| :--- | :--- | :--- |
| World | 기존 시간/Phase snapshot과 환경 제공 | Event 실행을 이유로 Food 직접 변경 |
| Ecology Simulation | Phase별 이벤트 예약, 손실 조정, 소비 batch 배분, Food snapshot 게시 | 개체별 생애 시각·Energy·이주 상태 소유 |
| Mass | 소비 대상 판정, 개체별 요청/결과와 NextFeedTime 관리 | UObject 호출·공유 Food 동시 차감 |
| Core | 식별 가능한 요청/결과/환경 손실 값 계약 | Legacy Evolution 또는 Network/Mass 구현 의존 |
| 조정 경계 | worker 종료 뒤 수집·검증·Ecology 호출·결과 전달 | 별도 Food 저장소·자원 변경 규칙 |
| Network/Debug | 기존 Box 유지, 검증 로그/표시 읽기 | 소비 요청 복제·Client 자원 판정 |

환경 이벤트의 **일정과 자원 의미는 Ecology**가 소유하고 World는 시간/Phase 변화만 제공한다. 정기 소비의 **대상 여부는 Mass**가 판정하며 지급량과 총 차감은 Ecology가 결정한다. 계층 간 연결 때문에 이 두 책임을 한 Processor loop에 합치지 않는다.

## 3. 입력·출력과 정확히 한 번 처리

| 계약 | 생산자 → 소비자 | 의미 |
| :--- | :--- | :--- |
| 소비 요청 | Mass → Ecology | StepId, StableAgentId, RegionId 및 런타임 검증용 index, RequestedAmount, 소비 예정 시각 |
| 소비 결과 | Ecology → Mass | 요청 key, 유효/거부 사유, 실제 GrantedAmount |
| 환경 손실 요청/결과 | Ecology 이벤트 예약 → 자원 조정 | WorldEpoch/CycleId/Phase/EventId/RegionId, 요청 손실과 실제 손실 |
| 완료 자원 snapshot | Ecology → 다음 스폰/Migration/집계·게시 경계 | StepId, RegionId/index, Food/Capacity, 고갈 여부 |

기존 `FEcoFoodConsumptionRequest`를 재사용하고 StepId 등 실행 정보는 런타임 envelope/Fragment로 보강한다. Core DTO에 UObject나 `FMassEntityHandle`을 넣지 않는다. ID→Entity 결과 적용 매핑은 Mass 내부에서 검증한다.

생태 step 안에 여러 소비 예정 시각이 catch-up되는 경우, 각각의 예정 시각을 포함한 요청 key를 사용하거나 별도의 하위 StepId를 부여한다. `(StepId, StableAgentId)` 하나로 서로 다른 정상 소비를 중복 처리로 오인하지 않는다. 같은 key 재전송은 결과를 다시 지급하지 않는다.

## 4. 최소 기능 규칙

### 정기 소비

- 생성 후 20초부터 10초 간격으로 Food 1을 요청한다. Wave별 생성 시각 차이를 유지한다.
- 살아있는 Authority Entity 중 Resident만 소비한다. Traveling/Waiting 상태의 판정 입력은 M3.3이 연결하며 기본 상태는 Resident다.
- 해당 Region의 전체 Population을 곱해 Food를 차감하지 않는다. 개체별 섭취 예정 시각·생존·소속을 검증한다.
- 유효한 예정 소비를 처리하면 실제 지급이 0이어도 다음 예약을 10초 뒤로 진행시켜 매 step 반복 요청을 막는다.
- Energy/HP는 이 단계에서 변경하지 않는다. GrantedAmount를 기록하여 후속 Energy 연결이 가능하게 한다.

### 낮밤 이벤트

- 기본 이벤트 시각은 Day 구간의 25/60, Night 구간의 1/4 지점이다. 60초 Phase에서는 기존 계획의 +25초/+15초이고, 현재 10초 Phase에서는 +약 4.167초/+2.5초다. 대상 지역·비율·손실량·활성 여부는 Project Settings에서 편집한다. Phase마다 한 번 실행한다.
- Phase 전환 시 Food를 초기화하지 않는다. 이전 Phase의 예약은 취소하고 새 Phase key를 사용한다.
- 실제 손실은 `min(남은 Food, 요청 손실)`이며 음수·NaN/Inf·무효 Region을 거부한다.
- 환경 손실을 Food 섭취나 PredationHistory 증가로 기록하지 않는다.

### 같은 시각의 처리

World 시간 입력 → 예정 환경 손실 → 현재 Food 기준 스폰 승인(M3.1) → 소비 배분 → 완료 snapshot/고갈 확정 순서로 처리한다. 소비와 이벤트가 같은 시각이면 이벤트가 우선이다. 서로 다른 예정 시각은 경과 시각 순서대로 처리하며 긴 frame 뒤 이벤트 전체를 소비보다 먼저 몰아서 적용하지 않는다.

고갈 epsilon은 작은 고정/Capacity 비례 허용 오차로 명시하고, 양수 잔여량을 정상 소비 없이 임의로 큰 폭 제거하지 않는다. 배분 후 소수 잔차 보정도 보존 로그에 포함한다.

## 5. 구현 작업 순서

1. **순수 배분 helper:** 지역별 요청 합과 Food를 받아 비례 배분하는 순수 계산을 만든다. 지급 합≤가용량, 각 지급≤요청량을 검증한다.
2. **요청/결과 Fragment:** chunk마다 개체 자신의 요청/결과만 기록한다. 공유 TArray에 worker들이 동시에 Add하지 않도록 한다.
3. **소비 Mass pass:** M3.1의 SpawnTime/NextFeedTime에서 due 대상을 판정한다. MVP 구현은 조정 경계가 동기 로컬 쿼리를 명시적으로 호출한다. immutable 시간 입력을 사용하고 loop에서 Subsystem을 조회하지 않는다. 추후 자동 Processor/병렬화로 옮기면 수집 및 완료 barrier를 유지한다.
4. **GameThread 조정:** worker 완료 후 요청을 수집하고 ID/Region/생존/시각/유한값을 검증한다. 유효 요청만 모아 Ecology batch API를 호출하고 Region마다 Food를 한 번 차감한다.
5. **이벤트 예약:** 기존 World clock snapshot으로 Day/Night의 due 이벤트를 수집한다. 중복 key 거부 및 실제 손실 로그를 연결한다.
6. **고갈 결과 연결:** 조정 후 새 Food snapshot을 게시한다. M3.1의 다음 스폰 판단이 갱신된 값을 읽어 고갈 Region의 웨이브를 건너뛰게 한다.
7. **단독/통합 검증:** 추가 Spawn/이벤트/소비의 on/off를 fixture 설정으로 분리하여 각 원인을 재현한다.

단건 `ApplyFoodConsumption()`을 Entity 순서대로 반복하여 선착순 지급하지 않는다. Blueprint/Debug Actor의 직접 Food setter로 테스트 이벤트를 흉내 내지 않는다.

## 6. 주 수정 영역과 M3.3 인계

| 영역 | 작업 |
| :--- | :--- |
| `Core/EcoEventTypes.h` 또는 작은 활성 계약 헤더 | 환경 자원 손실 및 실행 envelope 정의 |
| `Ecology/` | 순수 배분 helper, batch API, Phase 이벤트 예약 및 고갈 snapshot |
| `Mass/` | 개체별 소비 요청/결과/예약 처리, 안전한 수집·적용 경계 |
| `Debug/`, 핵심 자동화 | 원인별 fixture와 보존·중복·시각 검증 |

인계할 결과는 StepId가 있는 완료 Food snapshot, 실제 지급 결과, 원인별 EventLoss/ConsumedFood 로그와 소비 일정을 갱신하는 Mass 내부 경로다. M3.3은 Traveling 시작 시 요청을 중단하고 도착 시 NextFeedTime을 도착+10초로 설정할 수 있어야 한다. 공유 Food 변경 API를 Migration에 새로 만들지 않는다.

## 7. 검증 및 종료 기준

- [ ] 생성 20초 전에는 소비하지 않는다. 다른 시각의 웨이브도 자신의 생성 시각을 따른다.
- [ ] A Food 24·8마리·웨이브/이벤트 off에서 20/30/40초에 각 8 소비하여 40초에 0이 된다.
- [ ] 동일 10개 요청 각각 2·가용량 5에서 각각 0.5 지급한다. 입력 순서 변경 후 같은 결과다.
- [ ] `FoodBefore - EventLoss - GrantedTotal = FoodAfter`가 명시한 허용 오차 안에서 성립한다.
- [ ] 첫 소비 전 A Food 40을 이벤트로 40 감소시켜 이벤트만으로 고갈된다.
- [ ] Day/Night 이벤트가 각 Phase당 한 번 발생하고 실제 손실을 소비 로그와 구분한다.
- [ ] 0 Food/Capacity, 잘못된 ID/index, 중복·낡은 key 및 NaN/Inf를 안전하게 처리한다.
- [ ] 30/60 FPS·긴 frame에서 예정 소비/이벤트가 누락·중복되지 않는다.
- [ ] Food 고갈 후 추가 스폰이 중단되며 Vitals/Alive 수는 자원 이벤트 때문에 바뀌지 않는다.
- [x] UE 5.8 Editor UBT 빌드가 통과한다.
- [ ] Authority/Entity 처리 경계와 소비·이벤트 결과를 에디터 시나리오로 확인한다. 자동화 테스트는 사용자 요청에 따라 생략한다.

이 단계 종료는 Food 고갈까지다. 이주·Client 요약·전체 관찰 성공은 M3.3에서 확인한다.
