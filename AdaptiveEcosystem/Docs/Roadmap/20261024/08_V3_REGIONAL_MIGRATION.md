# T08. v3 지역 이주·Native 문맥 이전

상태: 공통 이주 확장 명세 / 기준: `8836558` / 책임 제안: 원준 이주·회계, 권신혁 Native 이동/문맥, 조연우 예약 정리, World 경로·지형.

선행: [T01](01_RUNTIME_CONFIGURATION_AND_AUTHORITY.md). 확인: [F13·F14](99_DECISIONS_AND_CONFIRMATIONS.md). 연계: T03/T05/T07/T09.

## 1. 목적과 현재 공백

동일 개체가 먹이·위험·밀집 압력으로 다른 지역으로 이동하고 도착 지역의 환경·먹이·위협으로 판단을 이어간다. 이주는 Population의 지역 분포를 바꾸되 세계 개체 수나 생애 ID를 바꾸지 않는다.

기존 M4의 지역 graph·pressure·FEcoTravelFragment·Reconcile·arrival receipt는 재사용한다. 현재 v3 ApplyToSpawner는 Migration.bEnabled=false와 waves=false를 설정한다. v3는 지역별 사각 stage·고유 먹이 격자·context로 움직이므로 일반 M4 스위치를 켜는 것만으로 이주가 연결되지 않는다.

## 2. 범위

우선 A/B 인접 두 지역·초식 한 종의 실제 지형 이동에 한정한다. 서버의 이주 의도·제어 인계·이동 중 생존·도착·취소·문맥 이전·예약 정리·복제를 포함한다.

제외: 새 NavMesh/ORCA 도입, 강제 teleport를 정상 이동으로 계산하기, 지역 unload의 영속 저장/복원, 모든 종·대륙·정책의 일반화, Python에 없는 이주 규칙을 조용히 채택하기.

## 3. 요청·결과 제안

| 항목 | 의미 |
|---|---|
| WorldEpoch/StableAgentId/MigrationRequestId | world·생애·요청 식별 |
| Origin/DestinationRegionId | 출발/목표의 영속 ID |
| ExpectedResidenceRevision | 이미 변경된 요청 결과 거부 |
| Reason/DecisionStep/DepartureTime | 기존 reason·압력 snapshot의 근거 |
| DestinationArrivalPosition | World의 안전 도착 후보, Unreal cm |
| MovementRevision/Deadline | 이동 취소·stale Feedback 검증 |
| Result | Pending/Travelling/Arrived/Failed/Cancelled + 실제 시각·위치·사유 |

기존 FEcoMigrationOutcome을 도착 결과의 기본으로 재사용한다. 제안 필드가 현재 모두 존재한다고 해석하지 않는다.

## 4. 실행 상태와 순서

```text
Resident → DepartureValidated → Traveling
 → ArrivalValidated → ContextTransferCommitted → Resident
Traveling → Failed/Cancelled → 합의된 복귀·대기 경로
모든 미확정 상태 → Death → 공통 사망 확정
```

1. 완료 자원·인구 pressure와 지역 인접 graph로 의도를 결정한다.
2. 현재 생존·residence·목표 수용 조건을 검사하고 이주 request revision을 발급한다.
3. 출발지 Shelter·feeding·표적 요청을 owner에게 취소하고 stale Feedback을 차단한다.
4. 이주 의도를 Native 단일 movement writer에 넘긴다. coordinator나 Social이 추가 위치 적분을 하지 않는다.
5. 이동 중 Native 대사·위협 반응·먹이 처리 정책은 F13/F14대로 적용한다. M4 기본 대사를 다시 켜 중복하지 않는다.
6. 실제 body 위치·지역 포함·지면·도착 revision을 검사한다.
7. Mass 순회·Native Step이 끝난 안전 경계에서 ContextIndex/지역 membership/lookup·인구 In/Out을 함께 확정한다.
8. 목적지 첫 관측·최신 날씨·먹이 문맥을 만든 뒤 일반 정책 제어를 재개한다.

## 5. 실제 이동의 선행 설계

현재 Native 지역 stage 경계는 지역 사이 빈 공간의 연속 이동을 기본 지원한다고 가정할 수 없다. F14에서 transit 표현을 정한다.

권고는 Native 단일 writer 안의 명시적 Transit 제어 상태 또는 adapter를 두는 것이다. 원래 stage clamp와 Transit 이동을 구분하고 서버 지면·충돌 제약을 통과시킨다. Native/Unreal 좌표를 왕복 변환하되 마지막 위치를 teleport로 도착시켜 성공 처리하지 않는다.

실제 이동 경로가 없는 fixture에서 논리 Region만 교체하는 시험은 context transfer 단위 검증으로만 기록한다. production 실제 이주 통과와 구분한다.

## 6. 이전할 상태와 재계산할 상태

| 보존 | 목적지에서 재계산/폐기 |
|---|---|
| StableAgentId·Species·출생 시각 | runtime index와 context/index mapping |
| HP·Energy·Reserve·생존 상태 | 목적지 Food/날씨/근처 위협 관측 |
| 행동·phase·유효 cooldown·직접 기억의 시각 | 출발지 pointer·target index·view cache |
| 개체 난수/phase 계약 | 출발지 공간 feeding·slot·경로 요청 |
| 필요한 생애·도망 통계 | 지역별 집계와 목적지 snapshot |

모든 기억은 age·지역 유효성을 재검사한다. region-local target index를 StableAgentId로 변환 없이 그대로 옮기지 않는다. 지역별 predation EMA·환경을 개체 고유 기억처럼 복사하지 않는다.

Native 결정 step과 공통 ecology time의 매핑을 보존한다. 목적지 시각이 다르면 절대 deadline/경과 시간으로 재계산하며 step 숫자만 복사해 cooldown이 되감기지 않게 한다. array 재구축 중 포인터를 보관하지 않는다.

## 7. 회계·실패·취소

권고 회계는 실제 도착 commit까지 origin Population에 포함하고 traveling/outbound와 target incoming을 별도 표시하는 기존 구조를 유지하는 것이다. 도착 때만 origin Out+1, destination In+1을 한 receipt로 확정한다.

이동 중 죽으면 현재 확정 소속 지역에 Death를 한 번 기록한다. 도착 전 사망을 destination Birth/Death나 In으로 만들지 않는다. 도착 중 사망과 이주가 같은 경계에 경쟁하면 기존 공통 사망 우선 원칙을 적용하고 case를 검증한다.

이동 실패·목표 변경은 revision을 바꿔 과거 arrival을 거부한다. 취소했다고 몸이 origin에 없는 상태에서 즉시 Resident로 선언하지 않는다. 복귀·안전 대기·새 경로 중 F13에서 정한 실제 이동 절차를 따른다. 목표 unload/실패는 원래 ID를 삭제·재생성해 해결하지 않는다.

## 8. 구현 단계

- MG-A: 이주 압력·Social/위협 우선순위·Transit 생존 규칙을 합의한다.
- MG-B: Native Transit 이동과 cm↔단위·경계·지면 검증을 소수 개체로 만든다.
- MG-C: context detach/attach·cache 무효화·첫 관측을 구현한다.
- MG-D: 공통 arrival receipt·In/Out·summary·Bubble Region 변경을 연결한다.
- MG-E: 실패/사망/재지시/저 FPS·Client 재진입을 검증한다.

## 9. 검증 시나리오

| ID | 조건 | 기대 결과 |
|---|---|---|
| MG01 | A 먹이 고갈→B 이동 | 실제 body 도착 후 Region/context 변경 |
| MG02 | 이동 후 B의 먹이 섭식 | B Food 감소·같은 ID 에너지 반영 |
| MG03 | 이동 중 위협/은신처 수요 | F13 우선순위, 예약/이동 writer 중복 없음 |
| MG04 | 이동 중 기아·포식 | Death 1회, arrival/In/Out 중복 없음 |
| MG05 | 도착과 사망 경합 | 정의된 사건 순서·보존식 유지 |
| MG06 | 목표 변경·stale arrival | 과거 요청 거부, 잘못된 지역 이전 없음 |
| MG07 | 다른 크기·회전 지역·cm 변환 | 실제 지리 포함·속도·위치 연속 |
| MG08 | 문맥 이전 후 view 재구축 | pointer/index 오염·이중 Native 등록 없음 |
| MG09 | 늦은 접속·relevance 재진입 | 같은 ID의 현재 Region·위치 수신 |
| MG10 | 이동 실패·목적지 미로드 | 실제 복귀/대기, Population 유실 없음 |

## 10. 완료 조건

두 지역의 실제 이동·도착 후 관측/섭식·사망 정리를 통과하고 세계 In 합=Out 합, 세계 Population 불변을 입증한다. Python 세계에 없는 이주 규칙은 별도 계약/평가 범위로 기록한다. 기본 Native 파리티 결과와 이주 ON 결과를 혼합하지 않는다.

## 11. Source·계약 근거

- [이주 형식](../../../Source/AdaptiveEcosystem/Core/EcoMigrationTypes.h), [공통 이주 조정](../../../Source/AdaptiveEcosystem/Mass/EcoMassMigration.cpp)
- [v3 integration/context](../../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.cpp), [Native Step](../../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp)
- [공통 lifecycle 순서](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp), [인구 회계](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePopulation.cpp)
- [기존 이주 계획](../ProductionIntegration/03_RegionalMigration/README.md), [Social 예약 수명](../../조연우/SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md)
