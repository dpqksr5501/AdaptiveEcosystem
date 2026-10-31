# 과밀 재이주와 기아 사망 연결 구현 계획

> 작성일: 2026-10-06 / Unreal Engine 5.8
> 상태: 구현 전 계획안. 런타임 코드는 이번 요청에서 변경하지 않는다.
> 우선 대상: 현재 M3 Box Server/Standalone 경로. M4 사망 전송과 M5 PPO 연결에 공통 기반을 제공한다.
> 검증: 에디터 빌드와 수동 시나리오. 자동화 테스트 작성·실행은 생략한다.

## 1. 목표와 권장 정책

이주자는 목적지에 같은 StableAgentId로 도착하며, 실제 인구가 설정 상한을 넘어도 빠짐없이 집계한다. 과밀 자체로 개체를 삭제하거나 인구를 상한으로 잘라 표시하지 않는다. 추가 생성 억제, 먹이 경쟁, 일부 개체의 재이주, 에너지 부족에 따른 기아 사망으로 압력을 해소한다.

목표 폐루프는 다음과 같다.

```text
유입 증가 → 지역 혼잡/예상 식량 부족
                  ├→ 신규 생성 억제
                  ├→ 일부 개체 재이주 → 출발/도착 인구·수요 변화
                  └→ 실제 먹이 부족 → Energy 감소 → 기아 피해 → 사망
                                                        ↓
                                        Alive/Population/소비 수요 감소
                                                        ↓
                                  다음 지역 압력·스폰·관측에 반영
```

기아는 개체의 섭취 부족과 생명 상태로 판정한다. 인구 수치가 높다는 이유만으로 HP를 차감하지 않는다. 기아 사망은 PredationHistory를 증가시키지 않는다. 실제 포식·플레이어 사냥 원인만 별도 검증된 위협 이벤트로 전달한다.

## 2. 현재 코드에서 확인한 출발점

| 영역 |현재 동작 | 추가 작업 |
| --- | --- | --- |
| 먹이 | Collect → Ecology 비례 배분 → Apply. 부족하면 요청자에게 같은 비율로 배분 | 실제 GrantedAmount를 Energy 회복에 한 번 연결 |
| Vitals | FEcoVitalsFragment의 HP/MaxHP/Energy/MaxEnergy 존재 | 시간 기반 대사, 기아 유예·피해·사망 판정 |
| 이주 | 음식 고갈 시 인접한 먹이 있는 지역 선택. 목표 반경+Bounds 도착 후 Region commit | 과밀/식량 전망 압력, 후보 수요 반영, 출발 수 제한, 쿨다운 |
| Population | Alive Tag + 현재 commit Region으로 집계. 이동 중 출발 지역에 포함 | Resident/유출/유입 분리 진단, 사망 확정 이후 재집계 |
| 생성 제한 | RegionPopulationLimit/GlobalPopulationLimit로 추가 Spawn 제한 | 생태 압력 설정과 분리, 유입 예정 수를 생성 판단에 반영 |
| 사망 | PendingDeath Tag 정의 있음. 별도 Policy 포식 경로는 HP=0과 자체 지역 보고 | Box 경로의 단일 Death commit/정리 구현. 이후 다른 피해 경로를 같은 입력으로 통합 |
| 전송 | M4.1에 health/energy/life 상태·revision·수신 buffer 기반 있음 | 실제 Alive 제거와 Dead 전달, 잔류 후 Remove 연결 |

기존 Population 불일치 의심은 별도 선행 확인 대상이다. 영역 진입과 도착 commit은 다르고, 요약은 기본 1초마다 게시된다. 아래 기능을 추가해서 집계 오류를 가리지 않는다.

참조: [M3 실행 순서](../../Mass/MASS_PROCESSOR_ORDER.md), [기존 이주 계획](M3_3_MIGRATION_AND_VALIDATION.md), [이주 이력 기반 생성 계획](MIGRATION_AWARE_SPAWN_PLAN.md), [M4.1 계약](../M4/M4_1_DATA_CONTRACT.md), [M5 폐루프](../M5/M5_PPO_CLOSED_LOOP.md).

## 3. 스폰 상한과 생태 수용력의 분리

기존 RegionPopulationLimit는 당분간 추가 생성 제한으로 유지한다. 새 EcologicalComfortPopulation은 혼잡을 판단하는 기준이며 강제 입장 제한이 아니다. FoodCapacity는 먹이 저장 용량으로, 개체 수를 뜻하지 않는다.

첫 버전은 지역별 정적 혼잡 기준과 짧은 시간의 식량 전망을 함께 쓴다. 재생률 기반의 장기 수용력은 별도 단계로 미룬다. 현재 Box 경로는 먹이를 재생하지 않으므로 충분한 시간이 지나면 모든 지역의 먹이가 고갈될 수 있다. 영구적인 안정 개체군이 유지된다고 약속하지 않는다.

### 지역 집계

- Population: 해당 Region에 소속된 전체 Alive. 기존 의미 유지.
- ResidentCount: 현재 Region에 정착하여 정상 섭취할 수 있는 개체.
- OutboundCount: 다른 Region을 향해 Traveling 중인 소속 개체.
- IncomingCount: 다른 Region에서 해당 Region을 목적지로 Traveling 중인 개체.
- WaitingCount: 목적지를 찾지 못해 대기하는 소속 개체. 일반 주민과 구별한다.
- ProjectedPopulation = Population - OutboundCount + IncomingCount.

동일 지역 복귀 이동은 Outbound/Incoming에 넣지 않는다. 한 개체는 Population에 한 번, 외부 이동이면 유출/유입에 각각 한 번만 기여한다. 목적지 취소/변경/사망은 다음 결정 경계의 Mass 집계에 반영한다. 별도 영구 인구 장부나 Actor 수 기반 집계를 만들지 않는다.

이주 중 소속 인구는 출발지에 남아 있지만 실제 출발지 먹이 수요는 줄어든다. 혼잡 완화와 목적지 평가에는 ProjectedPopulation을 사용하고, 당장의 섭취 배분은 Resident의 실제 요청만 사용한다.

### 식량 전망

첫 버전의 한 종 Box에서는 다음과 같이 계산한다.

```text
개체당 예상 소비율 q = Feeding.Amount / Feeding.IntervalSeconds
예상 수요 D = ProjectedPopulation × q × ForecastHorizonSeconds
식량 충족 전망 S = D > 0 ? clamp(FoodAmount / D, 0, 1) : 1
혼잡 비율 C = ProjectedPopulation / EcologicalComfortPopulation
```

초기 버전은 재생량을 0으로 간주한다. 다종 통합 시 종별 소비율을 합산한다. 생태 수용력 판단에 클램프되지 않은 C를 보존한다. 외부 유입은 도착 시각을 정밀 예측하기보다 전망 기간 내 도착한다고 보수적으로 계산한다. 비용과 정확성을 측정한 뒤 도착 예상 시각을 확장한다.

## 4. Energy와 기아 피해

### 소유권과 데이터

`Core/EcoVitalsTypes.h`에 검증 가능한 설정과 죽음 원인 enum을 추가하고, `Mass/EcoMassVitals.*`에 Box 생명 처리 pass를 마련한다. 이름은 구현 시 확정한다.

| 데이터 | 권장 소유자 | 내용 |
| --- | --- | --- |
| 대사/기아 설정 | 종별 불변 설정, Box에서는 세션 설정을 초기값으로 적용 | 기본 대사율, 이동 대사율, FoodEnergyGain, 기아 유예, HP 피해율 |
| FEcoVitalsRuntimeFragment | Authority per-entity | 마지막 처리 Epoch/Step/Time, 연속 Energy=0 시간 |
| FEcoDeathFragment | Authority per-entity | committed 여부, 원인, 사망 시각·지역·revision, 제거 기한 |
| DeathOutcome DTO | Core 값 계약 | Epoch, StableAgentId, SpeciesId, committed Region, 원인, 시각 |

기존 FEcoSpeciesSharedFragment의 EnergyDecayRate/FoodEnergyGain을 실제 초기화 경로에서 사용하거나 새 const shared 설정으로 통합한다. 같은 대사율을 여러 설정에 저장해 서로 다른 계산에 쓰지 않는다. 개체별 시간과 Death 상태를 Shared Fragment에 넣지 않는다.

### 시간 계산

- WorldClock의 처리 구간 `[이전 완료 시각, 이번 단계 시각]`을 사용한다. 네트워크 real time과 실제 프레임 Delta를 별도 대사 입력으로 중복 사용하지 않는다.
- 신규 개체는 SpawnTime 이후의 시간만 처리한다. catch-up 중 과거 단계에서 미래에 생성된 개체를 소급 대사하지 않는다.
- 동일 Epoch/Step을 두 번 적용하지 않는다. 0 길이 단계는 대사·기아 시간을 늘리지 않는다.
- 첫 버전은 Resident/Waiting에 기본 대사, Traveling에 기본+고정 이동 대사를 적용한다. 과거 경로를 복원하지 않는 현행 catch-up에서 현재 Velocity를 과거 여러 단계에 재사용하지 않는다.

```text
Energy = clamp(Energy - MetabolicRate × dt, 0, MaxEnergy)
섭취 적용: Energy = min(MaxEnergy, Energy + GrantedAmount × FoodEnergyGain)
```

Energy가 구간 중간에 0이 되면 전체 dt가 아닌 실제 0 이후 시간만 누적한다. 예: Energy=1, 대사율=2/초, dt=1초라면 기아 시간은 0.5초다. 유예 시간 이후의 구간에만 HP 피해를 적분한다. Energy가 실제로 회복되면 연속 기아 시간이 초기화된다. HP는 최초 버전에서 음식으로 자동 회복하지 않는다.

먹이 배분 결과 검증이 끝난 뒤 Energy를 한 번만 회복하고 `LastFeedTime`/pending 해제와 같은 성공 경계에서 완료한다. 같은 결과의 재적용을 막는다. MaxEnergy 초과 회복이 있어도 이미 소비한 Food를 환불하지 않는 정책을 명시한다. 에너지에 따른 요청량 최적화는 이후 단계다.

기아가 진행되는 구간에 HP가 0이 되면 죽음이 확정되며, 그 뒤 도착하는 식사로 되살리지 않는다. 정확히 같은 timestamp에 lethal starvation과 식사가 겹치면 **사망 우선**으로 정한다. Energy=0이지만 HP>0인 생존자는 해당 시각의 식사로 회복할 수 있다. 이동/대기 개체도 대사하며, 현재 계약상 이동 중 섭취하지 않는다.

## 5. 한 번의 사망 확정과 정리

모든 사망 원인이 하나의 commit 경로를 공유하도록 만든다. 기아부터 연결하고 M4 플레이어 피해/포식은 이후 같은 경로로 합친다. 기존 Policy 포식 경로의 직접 HP=0 및 좌표 기반 보고를 곧바로 RegionId 기반 보고와 중복 연결하지 않는다.

권장 순서:

1. Authority Alive 개체의 lethal 상태를 검사하고 StableAgentId로 Death 요청을 모은다.
2. `(WorldEpoch, StableAgentId)` 기준으로 한 생애의 commit을 한 번만 수행한다. 같은 시각에 원인이 겹치면 lethal 사건 시각과 고정 tie-break 규칙으로 주원인을 결정하고 보조 원인을 진단에 남긴다.
3. Death 상태를 확정하고 이동 입력/Velocity를 0으로 만든다. 소비 요청·Travel 목적지를 정리한다.
4. Deferred Command Buffer로 Alive 제거 및 PendingDeath 추가. Mass가 processing 중이 아닌 명시적 경계에서 적용한 뒤 다음 살아있는 개체 query를 수행한다.
5. Alive 집계에서 제외하고 지역의 StarvationDeathCount 등 원인별 통계를 갱신한다. 자동 음식 환원/사체 자원 생성은 MVP에서 제외한다.
6. M4 표본에서 Dead를 전달할 짧은 잔류 기간 동안 Entity를 보존한다. 기간 종료 후 Entity 파괴를 defer한다.
7. Ecology의 개체별 feeding 중복 방지 기록(`LastAcceptedFeedTime`)과 해당 개체의 대기 기록도 안전한 시점에 정리한다. 죽은 ID는 재사용하지 않는다.

PendingDeath에는 더 이상 소비·이주·조향이 적용되지 않아야 한다. HP=0인데 Alive가 여러 단계 남아 인구에 포함되는 구간을 만들지 않는다. 정상 pending 먹이 요청은 배분/적용을 마친 동일 단계에 없어야 하며, 외부 lethal 피해가 중간에 들어오면 다음 단계 시작에서 commit한 뒤 Collect 대상에서 제외한다. 이미 차감·적용 완료된 음식을 사망했다고 재차 환불하지 않는다.

잔류 Entity는 Alive 인구에서 제외되지만 아직 복제·표현 대상일 수 있다. Dead 전달은 M4.2의 일반 interval gate보다 우선한다. 예시 2초 잔류는 시각 연출용 최선 노력이지 ACK 보장이 아니다. relevance 밖 Client와 잔류 종료 후 Late Join은 사망 연출을 못 볼 수 있다. 신뢰성 있는 사망 연출이 필수라면 M4.8에서 별도 terminal event/ACK/timeout 예산을 설계한다.

기아 DeathOutcome의 집계 지역은 마지막 committed Region으로 통일한다. Traveling 중 실제 사망 위치는 별도 진단 위치로 남긴다. 향후 포식 위험은 별도 검증된 위치→Region 결정 규칙으로 적용하며, 개체 소속 지역과 실제 포식 장소를 혼동하지 않는다.

## 6. 과밀 판단과 분산 재이주

### 출발 조건

식량 0인 기존 긴급 이주를 유지한다. 새로운 과밀 출발은 혼잡 C 또는 식량 전망 S의 임계값이 일정 시간 지속될 때 활성화한다. 낮은 Energy는 후보 우선순위에 사용하되 HP 피해가 본격화되기 전에 판단할 수 있도록 전망 기간을 확보한다.

임계값 진입/해제에 다른 값을 사용하고 최소 거주 시간·재이주 cooldown을 둔다. 긴급 고갈은 cooldown을 우회할 수 있지만 똑같은 실패 목적지로 반복 출발하지 않도록 최근 실패 목적지/재시도 간격을 둔다.

새 상태 enum을 무조건 늘리지 않는다. Resident/Traveling/WaitingForFood를 유지하면서 `MigrationReason`, 출발 시각, 마지막 도착 시각, 다음 결정 가능 시각을 개체 Fragment에 추가한다. 과밀인데 먹이가 있는 개체는 목적지가 없더라도 Resident로 남아 섭취한다. WaitingForFood는 실제 먹이 고갈·대기 계약에 사용한다.

### 목적지 선택

기존 인접 지역만 후보로 사용하는 MVP를 유지한다. 목표 개체를 가상으로 더한 뒤 목적지의 ProjectedPopulation/예상 소비율/식량 충족 전망을 평가한다. 출발지보다 충분히 개선되고, Food>epsilon이며 이동 가능한 후보만 선택한다.

후보 점수는 식량 충족·혼잡·거리·최근 실패 패널티를 정규화하여 구성한다. 첫 버전은 기존 completed Food와 새 인구 snapshot을 이용하며 위험도 가중치는 M4 사냥 통합 때 확장한다. 동점은 RegionId, 출발 후보 동점은 StableAgentId로 정해 query/chunk 순서에 의존하지 않는다.

기아가 임박한 개체가 너무 먼 목적지로 이동하지 않도록 단순 거리/Speed 예상 시간과 남은 Energy·유예·HP를 비교하는 안전성 필터를 추가한다. 실제 경로 생존 보장은 아니며 NavMesh 경로 비용 확장은 별도 작업이다.

### 한꺼번에 몰리는 문제 방지

동일 snapshot만 읽고 모든 개체가 B를 선택하면 재이주가 또 과밀을 만든다. 따라서 다음의 두 단계 결정을 권한다.

1. query에서 값 snapshot과 후보를 모은다. UObject 접근과 구조 변경 없이 수집한다.
2. query 밖 GameThread에서 원인/시급성/StableAgentId 순서로 일부 후보만 선정한다. 선정 직후 계산용 유출/유입 수요를 갱신하여 다음 후보는 그 결정을 고려한다.
3. 검증된 결과를 개체 Travel Fragment에 적용한다. Region은 실제 도착 전까지 바꾸지 않는다.

출발 수는 `필요 완화 인원`, `지역당 결정 주기 최대 출발 수`, `이웃이 받아들일 수 있는 개선 수요` 중 작은 값으로 제한한다. 최근 한 지역이 동률 후보를 영구 독점하지 않도록 대기 시간 우선순위를 둘 수 있다.

Incoming은 Traveling Fragment에서 매 결정 경계 재구성하는 **계획 수요**다. 하드 입장권이나 이중 Population 장부가 아니다. 결정 pass 안의 가상 유입은 임시 계산에만 사용하며 적용 후 Traveling 상태에서 다시 도출한다.

### 이동 중·도착 시 정책

목적지가 단순 혼잡해졌다는 이유로 이동 중 매 초 목적지를 바꾸지 않는다. Food 고갈/목적지 무효 같은 강한 조건에는 재평가하고, 일반 압력 변화는 충분한 개선 차이가 있을 때만 변경한다.

도착하면 정원이 넘었더라도 기존 도착 반경+Bounds+Food 조건 아래 Region을 한 번 commit한다. 새 최소 거주 시간 이후 과밀 재이주 후보가 된다. 도착 시 Food가 0이면 기존대로 commit을 보류하고 다음 결정 경계에서 대체 목적지/대기를 선택한다.

모든 지역이 과밀이면 신규 생성은 억제하고, 실제 개선되는 목적지가 없는 주민은 머물러 먹이 경쟁을 한다. 모든 지역이 고갈이면 대사·기아·사망이 진행된다. 목적지가 없다는 이유로 강제 생성·삭제·순간이동하지 않는다.

## 7. 생성과 이주 이력 연결

전역 생성 상한은 실제 전체 Alive와 outstanding Spawn 예약으로 유지한다. 이주는 세계 전체 Alive를 늘리지 않는다. 사망 후에는 실제 빈자리만 다음 정상 웨이브에서 생성할 수 있다.

지역 생성은 기존 소속 인구 제한을 보존하면서 유입 예정 인구와 먹이 전망도 검사한다. 예를 들어 지역 가용 수는 `max(Population, ProjectedPopulation)` 및 기존 생성 예약을 고려해 계산한다. 이주자가 아직 출발지 소속인 동안 출발지에서 즉시 새 개체를 채워 전역 인구를 늘리는 현상을 피한다. 목적지에는 유입 직전 웨이브로 빈자리를 모두 채우지 않는다.

과밀 또는 전망 부족으로 건너뛴 웨이브를 이후 일괄 보상하지 않는다. 초기 생성과 정규 웨이브의 적용 규칙은 구분하고 설정·로그에 명시한다.

기존 [이주 이력 기반 생성 설계](MIGRATION_AWARE_SPAWN_PLAN.md)의 MigrationOutcome 원인에 Overcrowding/FoodShortage를 확장한다. 유출/유입 이력은 서로 다른 Region으로 도착 commit했을 때만 기록한다. 의사결정 횟수, 목적지 변경, 취소를 성공 이주로 세지 않는다. 이번 MVP는 출생 특성 적응까지 필수 구현 범위로 확대하지 않는다.

## 8. 한 단계의 권장 실행 순서

기존 `ProcessEcologyStep`을 확장하되 Mass 이동은 계속 PrePhysics의 단일 writer를 유지한다.

1. 이전 완료 시각→현재 단계의 대사·기아 피해를 적분한다. 이전 프레임 외부 lethal 피해도 수집한다.
2. lethal Death commit을 적용하고 Deferred Alive/정리 변경을 안전하게 완료한다.
3. Alive 인구/Resident/유출/유입을 집계한다.
4. 자원 단계 시작 → 환경 손실/수동 이벤트 → 제한된 정상 Spawn.
5. 생존 Resident 먹이 요청 → Ecology 배분 → 소비 결과/Energy 회복 1회 적용.
6. 자원 완료 snapshot을 확정한다.
7. 실제 Transform 기반 도착 처리·Region commit 후 인구/계획 수요를 갱신한다.
8. 판단 주기가 도래하면 과밀/고갈 후보 수집 → 분산 목적지 선정 → Travel 적용.
9. 최종 Alive/Population/유출/유입/사망 통계·압력 요약을 확정하고 GameState에 게시한다.
10. 제거 기한이 지난 Dead Entity를 deferred 파괴한다. 실제 이동은 다음 Mass phase에서 수행한다.

진단 snapshot은 동일 Epoch/Step에서 읽은 값을 담는다. 게임 요약, 네트워크 표본, 화면 Actor 수가 같은 순간에 일치한다고 가정하지 않는다. catch-up은 기존 프레임당 최대 처리 단계 제한을 유지하며, 한 단계마다 실제 이동을 다시 적분하지 않는다. lethal crossing과 식사 등 정확한 이벤트 경계가 필요하면 scheduler의 next-due 계산을 확장한다.

## 9. 단계별 구현과 완료 게이트

아래 단계 이름은 이 기능의 작업 구분이며 기존 M3/M4 마일스톤 완료 선언이 아니다.

| 단계 | 작업/주요 파일 | 완료 게이트 |
| --- | --- | --- |
| P0 집계 확인 | Lifecycle ReconcilePopulation, Migration 로그, M4 dump | 초기 A/B/총 Alive와 arrival commit 후 이동량이 일치. 현재 의심 현상을 별도 재현/판정 |
| P1 계약·설정 | Core Vitals/Pressure/Event/Migration, RuntimeSettings, 역할별 Trait | 단위·시간·원인·ownership 확정, 설정 검증, Client에 논리 상태 없음 |
| P2 섭취·대사 | Mass/EcoMassFeeding.*, 새 Mass/EcoMassVitals.*, Lifecycle | 실제 섭취만 회복, 중복 없음, 프레임/시간 보존, 여행/대기 대사 |
| P3 기아 Death | 새 Death 처리, Tags, Lifecycle, Ecology 정리 | Death commit 1회, Alive/전체 인구 일치, pending 기록 정리, 기아는 위협 증가 없음 |
| P4 압력 snapshot | Core/Region, Ecology, Mass 집계 | Resident/유출/유입/예상 수요 일치, 이동/사망 시 잔여 예약 누수 없음 |
| P5 분산 재이주 | Mass/EcoMassMigration.*, Core/Migration | 일부 출발, 목적지 수요 순차 반영, ID 유지, cooldown/히스테리시스, 목적지 없음 처리 |
| P6 Spawn·Network·Debug | EcoSpawnSchedule/Simulation, Mass Bubble/Replicator, GameState/Debug | 유입 고려 Spawn, Dead→Remove, 원인별 요약과 진단 |
| P7 통합 검증 | 수동 테스트·검증 문서, processor order 문서 | 아래 시나리오 기록, UnrealBuildTool Editor Win64 Development 통과 |

P0→P1→P2→P3를 먼저 완료하고, P4→P5→P6로 연결한다. HP/사망이 불완전한 상태에서 대규모 재이주부터 구현하지 않는다. 각 소스 변경 묶음은 AGENTS.md에 따라 UBT 빌드를 수행한다.

M5에는 Energy/AverageEnergy/Population/Migration 결과를 기존 V1 관측 구성에 전달한다. 7개 관측·4개 행동 계약은 유지한다. PopulationPressure를 8번째 관측으로 임의 추가하지 않는다. 이번 Box 구현에 PPO/Social custom movement를 함께 붙이지 않는다. 단일 이동 writer의 통합은 별도 M5 작업이다.

## 10. 초기 조정값과 수동 검증

예시 값은 빠른 Box 관찰용이며 적용·성능 보장값이 아니다.

| 항목 | 예시 |
| --- | --- |
| MaxEnergy / 기본 대사 | 100 / 1 Energy/초 |
| 이동 대사 추가 | 0.5 Energy/초 |
| 섭취 주기·양 / EnergyGain | 10초·Food 1 / Food당 Energy 12 |
| 기아 유예 / 피해 | 5초 / 10 HP/초 |
| 식량 전망 / 판단 주기 | 30초 / 1초 |
| 혼잡 진입 / 해제 | 1.10 / 0.95 |
| 과밀 유지 시간 / 최소 거주 시간 | 3초 / 10초 |
| 지역당 출발 제한 | 판단 주기당 2마리 |

충분한 음식이면 10초당 대사 10과 섭취 회복 12가 균형을 이루고, 이동 중에는 더 빨리 고갈되는 예시다. 생존 시간과 이동 거리는 함께 조정한다. 두 지역 테스트만으로 장기 안정성을 주장하지 않는다. 일부 재이주를 성공시키는 시험에는 먹이와 여유가 있는 세 번째 Region을 권한다.

| 시나리오 | 준비 | 확인할 결과 |
| --- | --- | --- |
| 기존 집계 | Spawn off, A/B 초기 수 고정, A만 고갈 | 진입과 commit 구분, 도착 수만큼 A 감소/B 증가, 총 Alive 유지 |
| 정상 식사 | 음식 충분, Spawn/이주 off | Food 감소와 Energy 회복량 대응, HP 유지, 재적용 없음 |
| 부분 배급 | Resident 총 요청보다 적은 Food | 비례 배분, 실제 GrantedAmount만 회복, ID 순서에 의한 독식 없음 |
| 기아 | 이동할 이웃 없음, Food=0, 낮은 초기 Energy | 정확한 depletion/유예/피해, HP=0 Death 1회, 인구 감소 |
| 기아 직전 회복 | HP>0인 유예/피해 중 식량 공급 | 식사 후 Energy 회복·기아시간 reset. 죽은 개체는 복구되지 않음 |
| 과밀 분산 | B에 comfort 초과, C에 충분한 Food/여유 | B의 전원이 아닌 제한된 수가 이동, Incoming 반영, B↔C 진동 없음 |
| 목적지 동시 경쟁 | A와 B 모두 C를 선택 가능 | 첫 선정의 유입을 다음 선정에 반영, 초과 유입 폭주 방지 |
| 이동 중 고갈/사망 | 목적지 고갈 또는 장거리 이동 | retarget/대기/기아, Incoming 해제, 죽은 개체 이동 없음 |
| 모두 과밀/고갈 | 모든 후보 부족 | 무한 재선정 없음, Resident 섭취 또는 고갈 대기, 실제 기아로 감소 |
| Spawn과 유입 | 목적지 웨이브 직전 Incoming 생성 | 유입 고려 생성 억제, 세계 상한 유지, 놓친 웨이브 보상 없음 |
| 여러 사망 원인 | 같은 개체에 기아와 외부 lethal 피해 | Death 1회, 원인 우선순위 일관, 위협 이벤트 중복 없음 |
| Host+Client/Late Join | 실행 중 연결/이탈·재진입 | Client 논리 계산 없음, Dead/Remove 정상, relevancy 이탈로 인구 변화 없음 |
| 시간·재시작 | 30/60 FPS, 긴 frame, pause, PIE 재시작 | Epoch/Step 중복 없음, 대사·식사·사망 누락/중복 없음, 잔여 기록 초기화 |

사망 보존식: `Alive(t) = 초기 성공 Spawn + 이후 성공 Spawn - 고유 Death commit 수`. 모든 Region Population 합은 Alive와 같아야 한다. 이주만으로 Alive는 바뀌지 않는다. Dead 잔류 수와 Client 프록시 수는 Alive와 별도 표시한다.

먹이 보존식은 현재 자원 단계 계약을 유지한다. 사망을 이유로 Food를 생성하지 않고, 배분 총량은 실제 소비량과 일치해야 한다. 로그에는 Epoch/Step/Time, StableAgentId, Region, Energy/HP, GrantedAmount, 압력, MigrationReason, target, DeathCause를 남긴다. snapshot 수집 후 query 밖에서 출력하며 성능 측정 구간에서는 상세 개체 로그를 끈다.

## 11. 주요 위험과 제외 범위

- 과밀 스폰 억제가 개체 수를 줄이는 유일한 장치가 아니다. 실제 기아/사망 또는 이동이 연결되어야 압력이 해소된다.
- 현행 무재생 Food에서는 장기적으로 전멸이 자연스러운 결과일 수 있다. 재생·날씨 기반 장기 평형은 별도 계약과 테스트가 필요하다.
- 여러 스폰/피해/포식 경로를 한번에 통합하면 이동·Energy·사망 작성자가 중복될 수 있다. Box 경로부터 연결하고 각 기존 경로의 작성자를 명시한다.
- Dead 잔류와 replication budget은 별도 비용이다. 죽은 개체가 생태 인구에는 없지만 네트워크에 남는 시간을 측정해야 한다.
- Species별 압력, NavMesh 장거리 경로, 이동 중 채집, 사체 먹이, 음식에 의한 HP 회복, 출생 특성 적응, PPO 재학습은 첫 구현에서 제외한다.

권장 첫 구현 단위는 **정확한 Population 확인 → 실제 섭취의 Energy 회복 → 시간 대사 → 기아 Death commit과 인구 감소**다. 그 뒤 동일 completed snapshot에 기반한 과밀 분산 재이주를 연결한다.
