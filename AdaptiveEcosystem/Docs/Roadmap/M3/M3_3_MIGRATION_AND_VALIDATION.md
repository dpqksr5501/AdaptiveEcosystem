# M3.3 — 실제 이주·읽기 전용 표시·통합 검증

> 상위 계획: [M3 개발 계획](M3_IMPLEMENTATION_PLAN.md)  
> 선행: [M3.2 — 소비·이벤트·자원 조정](M3_2_RESOURCE_AND_EVENTS.md)  
> 상태: 개발 계획 / 미구현·미검증  
> 예상 개발량: **4.5~7인일** (이동 2~3 + 표시/복제 1~1.5 + 통합 검증 1.5~2.5)

## 1. 목표와 완료 화면

소비 또는 낮밤 이벤트로 Food가 고갈되면 같은 ID의 Box가 다른 Region으로 실제 이동한다. 도착 후 Region 소속과 다음 소비 일정이 변경되고, Host/Client가 권위 결과를 확인한다. 양쪽 고갈 시 대기하면서 스폰·이주가 폭주하지 않는다.

이 단계로 **합의한 관찰 범위**를 완료한다. 원래 M3 전체 범위의 Energy·기아·사망·V1 Observation/Utility는 잔여 작업으로 남긴다. 해당 기능을 이 단계의 숨은 완료 조건으로 추가하거나 관찰 완료만으로 M3 전체를 완료 처리하지 않는다.

## 2. 선행 조건과 책임 분리

M3.1의 시간/공간 snapshot과 스폰·기본 집계, M3.2의 완료 Food snapshot·고갈·소비 예약을 사용한다. 자원 손실이나 낮밤 시계를 다시 구현하지 않는다.

| 계층 | 이 단계의 책임 | 금지할 책임 |
| :--- | :--- | :--- |
| World | 인접 Region, Bounds, 도착점의 공간 snapshot 제공 | 고갈 판단을 이유로 Food 변경·개체 강제 재스폰 |
| Ecology Simulation | 완료 Food snapshot 제공, Mass 집계 수신 | 개체 Travel/Region/Transform의 별도 상태 보관 |
| Mass | 후보 선택·Travel 전이·최소 조향·도착 commit, 소비 예약 재설정, 실제 집계 | UObject 조회·Food 차감·Client 권위 이동 |
| Network | 완료 요약의 저주기 복제, 기존 Mass Transform/Region 전달 | 소비/이주 재계산·전체 Entity 일괄 복제 |
| Representation/Debug | 기존 Box, 화살표/라벨/요약 표시 | Server 상태 쓰기·Actor가 개체 본체 역할 수행 |
| 조정 경계 | 처리 순서·Deferred 반영·동일 완료 snapshot 게시 | 별도 논리 Entity/Population 저장소 |

Migration은 Mass 논리 상태 전이다. Ecology는 자원 가용성을 제공하고 이동을 수행하지 않는다. Movement는 `Mass/`에서 연결하며 Social Herd/Alarm/Shelter 코드를 수정해 이동을 맡기지 않는다.

## 3. Migration 입력과 상태 계약

- 입력은 완료 StepId의 Food/Capacity/Region index와 plain-data 공간 snapshot이다. Hot path에서는 compact index를 사용하며 Region UObject를 참조하지 않는다.
- 개체 상태는 Resident, Traveling, WaitingForFood로 정의한다. 기존 `FEcoTravelFragment`를 기반으로 필요한 대기/목적지/도착 정보만 보강한다. bool·Tag·상태 enum을 둘 경우 어느 값이 기준이며 어디에서 함께 갱신하는지 명시한다.
- StableAgentId, Entity, Network ID는 이동 전후 유지한다. `CurrentRegionId/Index`는 마지막 도착 commit의 논리적 소속이다.
- Traveling 동안 Population은 출발 Region에 포함한다. 목적지가 고갈되어 중간에서 대기해도 마지막 commit 소속을 유지한다. 실제 위치가 어느 Bounds에 있는지와 논리적 소속을 혼동하지 않는다.
- Mass는 기존 `FEcoRegionPopulationSnapshot`으로 Population/평균 Energy를 산출한다. TravelingCount는 같은 query에서 계산한 진단 집계이며 개체 Travel의 다른 진실값이 아니다.

## 4. 구현 작업 순서

1. **고갈 후보 판정:** Resident가 속한 Region Food가 epsilon 내 0이면 1초 Migration 판단 주기에 인접 지역을 확인한다. 목적지 Food>0이면 Traveling, 후보가 없으면 WaitingForFood로 전이한다.
2. **최소 이동 연결:** 목표 Region 내부의 도착 위치로 이동 의도를 만들고 엔진 Mass Movement에 연결한다. 기존 client Transform 표현을 유지하며 Client Template이 서버 이동 query를 충족하지 않도록 한다.
3. **이동 중 처리:** 소비 요청을 중단하고 밀린 섭취는 누적하지 않는다. 목적지 Food가 고갈되면 다음 판단에서 재평가한다. 두 지역 모두 고갈이면 현재 위치에서 멈추고 Travel을 해제한다.
4. **도착 commit:** 도착점 허용 반경과 목표 Bounds를 만족한 개체만 RegionId/index를 함께 변경한다. Travel을 초기화하고 NextFeedTime=도착시각+10초로 설정한다. 같은 도착을 재적용하지 않는다.
5. **집계 확장:** M3.1의 단일 집계 query에 이주/대기 진단을 추가한다. 모든 Region을 매 snapshot 게시해 인구가 0이 된 지역도 0으로 갱신한다.
6. **요약 게시:** World 시계·Ecology 완료 자원·Mass 완료 집계에서 같은 완료 경계의 읽기 전용 snapshot을 만든다. `AEcoGameState`가 저주기로 복제하고 Host 로컬 표시도 같은 결과를 읽는다.
7. **Box 관찰 및 통합:** 지역 Bounds/Food/Population/TravelingCount, Day/Night 잔여 시간, 이벤트 실제 손실을 표시하고 아래 시나리오를 실행한다.

Entity loop에서 Tag 추가/제거를 직접 실행하지 않는다. Deferred 반영 전에도 논리 상태를 기준으로 중복 소비·도착을 차단하고 Processor query 사이의 구조적 변경 반영 시점을 검증한다. 최소 조향·엔진 Movement·도착 검사·집계·Replication 사이 순서를 명시하고 [Processor 순서 문서](../../Mass/MASS_PROCESSOR_ORDER.md)에 관찰 경로의 실행 경계를 반영한다.

목표 위치에는 개체 ID 기준 작은 오프셋을 주어 Box 겹침을 줄일 수 있다. 순간이동·재스폰·새 ID 발급·NavMesh·정교한 Flock은 구현하지 않는다.

## 5. Network 및 표시 계약

| 전달 값 | 권위 원천 | Transport / 수신 처리 |
| :--- | :--- | :--- |
| 시간 요약 | World 시간 snapshot | GameState의 WorldEpoch/Phase/CycleId/Phase 기준 시각. Client는 표시만 수행 |
| 지역 요약 | Ecology Food + Mass 집계 | 기존 `FReplicatedRegionSummary`와 GameState. StepId/revision 일관성 명시 |
| TravelingCount | Mass 진단 집계 | 필요 최소 요약 필드로 전달. 개체별 Travel 전체를 복제하지 않음 |
| 관련 개체 Transform/RegionId | Authority Mass Fragment | 기존 Replicator/Bubble의 Add/Change/Remove 경로 |
| 이벤트 감소 원인/실제량 | Ecology 이벤트 결과 | Host 로그 필수. Client 표시가 필요하면 제한된 최신 진단값만 전달 |

2개 Region 요약은 일반 Replicated 배열로 시작한다. 내부 요청·Action·Runtime Index·EntityHandle을 보내지 않는다. Network DTO에는 UObject 구현을 끌어들이지 않고 Core 값 계약을 사용한다.

모든 요약은 1초 주기 및 초기화 완료 시 게시한다. 서로 다른 RepNotify의 수신 순서로 시계와 지역 데이터를 섞지 않도록 공통 revision/StepId를 검증하거나 하나의 게시 묶음을 사용한다. Late Join은 현재 snapshot만 받아야 하며 스폰/이벤트 예약을 Client에서 재실행하지 않는다.

기존 Box를 기본 표현으로 유지한다. 서버 debug draw는 자동 복제되지 않으므로 Client 라벨은 Client가 수신한 요약으로 그린다. Client Bubble은 부분집합이므로 Proxy 수와 전체 Population을 같다고 검증하지 않는다. 전체 이동 관찰은 Host/Standalone 카메라에서 먼저 수행한다.

## 6. 주 수정 영역과 변경 제한

| 영역 | 작업 |
| :--- | :--- |
| `Mass/EcoMassFragments.h`, `EcoMassTags.h`, 신규 최소 Processor | Travel 전이·목적지·조향·도착, 소비 일정 연결 |
| `Mass/` 집계/조정 경계 | 같은 완료 상태의 Population/TravelingCount 집계 및 게시 |
| `Network/EcoGameState.*`, `EcologyNetworkTypes.h` | Region/시간 요약 transport와 읽기 전용 수신 |
| 기존 `Network/Mass/` | Region 변경 dirty 처리 및 프록시 회귀 확인. 필요할 때만 최소 수정 |
| `Debug/`, 테스트 맵, 검증 문서 | Box 라벨/이벤트 원인, 시나리오 재현 및 기록 |

Food를 감소시키는 API는 M3.2의 조정 경로 하나를 유지한다. Network setter는 권위 snapshot을 전달할 뿐 Simulation 규칙을 실행하지 않는다. 새 Creature Actor 또는 Replicated Subsystem을 만들지 않는다.

## 7. 시나리오별 합격 기준

1. **소비 고갈:** A Food 24/B 400, 초기 각 8, 이벤트/웨이브 off. A가 40초에 고갈되고 다음 판단 주기에 동일 8개 ID가 B로 이동한다. 도착 뒤 B 소속/섭취 예약을 확인한다.
2. **Day 이벤트 고갈:** A Food 40, Day 15초에 -40, 웨이브 off. 첫 섭취 이전에 이동이 시작되어 이벤트 원인만 검증한다.
3. **Night 이벤트 고갈:** B Food 40/A 400, Night 진입 15초에 B -40, 소비/웨이브/Day 이벤트 off. B→A 이동을 확인한다.
4. **스폰·소비·이벤트 통합:** 상위 계획의 A 60/B 400·주야 이벤트 -50 preset으로 생성 증가, 고갈, 이동, 도착 소비를 관찰한다.
5. **양쪽/이동 중 고갈:** 신규 웨이브 중단, 이동/대기 전이 확인. Entity가 사라지거나 Region에서 이중 집계되지 않고 무한 왕복하지 않는다.
6. **ID와 집계:** 이동 전후 StableAgentId가 같고 같은 완료 snapshot에서 Alive=모든 Region Population 합이다. 지역 64 생성 제한이 이주 도착을 차단하지 않는다.
7. **네트워크:** Host+Client에서 이주 Region 변경과 Transform을 수신한다. Bubble 반복 진입/이탈, 이주 후 Late Join, PIE 재시작에서 중복/잔여 프록시가 없다.
8. **시간/장시간:** 30/60 FPS 및 긴 frame, 3~5회 주야 전환, 최대 128개체 15분 실행. 고갈 이후에도 예약/요청/이동이 폭주하지 않는다.

기본 자동화는 자원 보존·전이·도착 중복·집계·시간 경계에 집중한다. 실제 PIE, Client relevancy 및 15분 실행은 자동화 통과와 구분하여 기록한다. Phase/Event/StableAgentId/StepId를 남겨 원인과 결과를 추적할 수 있어야 한다.

## 8. 종료 산출물과 후속 작업

- [ ] 소비/낮밤 이벤트에 의한 고갈 및 실제 Box 이주를 각각 재현했다.
- [ ] 도착 후 RegionId/index/소비 일정이 함께 바뀌고 ID가 유지된다.
- [ ] 양쪽 고갈 대기·스폰 상한·자원 보존·Population 정합성이 유지된다.
- [ ] Host/Client 요약·관련 Box 및 Late Join이 읽기 전용으로 정상 표시된다.
- [ ] UE 5.8 Editor UBT, 핵심 자동화, PIE 및 15분 시나리오 결과를 확보했다.
- [ ] `M3_VALIDATION_REPORT.md`에 세 마일스톤의 설정·재현·측정·미완료 항목을 기록했다.

후속 잔여 M3 작업은 실제 지급량→Energy, 기본 소모→기아·사망, V1 Observation/Utility 및 생태 안정성이다. 약 3~5인일의 기존 별도 추정을 유지하며 이번 세 마일스톤에 포함하지 않는다. Food 재생·출생 특성·PPO·최종 표현도 합의한 보류 범위를 유지한다.
