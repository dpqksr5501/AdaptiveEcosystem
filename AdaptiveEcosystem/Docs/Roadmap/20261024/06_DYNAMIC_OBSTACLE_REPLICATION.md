# T06. 실행 중 나무·장애물 생성·변경·제거 복제

상태: 조건부 동적 World 기능 명세 / 기준: `8836558` / 책임 제안: World 규칙·에셋, 원준 권위·전송, 권신혁 Native obstacle adapter.

선행: [T01](01_RUNTIME_CONFIGURATION_AND_AUTHORITY.md), [T05](05_WORLD_WEATHER_AND_CLOCK_REPLICATION.md)의 revision 원칙. 확인: [F09·F10](99_DECISIONS_AND_CONFIRMATIONS.md).

## 1. 목적·범위

서버에서 나무가 생기거나 사라지면 Client에도 같은 외형과 플레이어 충돌이 있어야 한다. 서버 동물이 허공을 돌아가거나 Client에서만 보이는 벽이 생기는 문제를 막는다.

기존 배치 나무를 읽는 경로는 유지한다. 게임 중 생성·제거 기능을 제품에 넣을 때만 이 업무를 활성화한다. 벌목·화재·성장 규칙과 시각 에셋은 World 담당, 결과 전달과 늦은 참가는 Network 담당이다.

## 2. 현재 구현

레벨 나무는 EcoV3Tree 메시(충돌 OFF)와 EcoV3Trunk 줄기 막이(BlockAll)의 짝이다. Native는 서버의 충돌·태그를 읽어 원판으로 근사하며 EnvWatch가 변경을 step 경계에 반영한다. Beech_Tree 원본 메시의 큰 수관 충돌을 그대로 원판으로 쓰면 허공까지 막을 수 있다.

Test.AddTrees/Test.RemoveTrees는 시험 대역이고 복제가 없어 Standalone 전용이다. 이를 그대로 Listen/Dedicated에 허용하는 것으로 이번 업무를 끝내지 않는다. StageTrees 기본도 OFF다.

## 3. 전송 방식 제안

F09 권고는 소규모 동적 장애물부터 하나의 replicated World actor가 변경 목록/현재 상태를 관리하는 방식이다. 개별 replicated Actor 방식도 가능하지만 둘 중 하나를 먼저 선택한다. Subsystem 자체에 Replicated/RPC를 붙이지 않는다.

| 논리 항목 | 제안 계약 |
|---|---|
| WorldEpoch + ObstacleId + Generation | world·객체·재생성 구분; EntityHandle 사용 안 함 |
| Revision + OperationId | 변경 순서·중복 요청 판정 |
| RegionId + Transform | 서버 확정 위치, 단위 Unreal cm |
| VisualType | 허용된 에셋 종류 키, 임의 Client 에셋 경로 아님 |
| Collision radius/height/config | 줄기 물리와 Native 원판을 재현할 입력 |
| Active/Removed | 현존 상태·제거 이력 |
| AppliedEnvironmentRevision | Native 반영과 연결하는 진단/상태 |

기존 배치 액터는 deterministic authored key로 식별하고 동적 객체와 구분한다. 저장된 원본 나무를 제거하는 기능은 원본 맵을 저장 수정하지 않고 세션 overlay 상태로 표현한다. 늦은 참가자는 제거 overlay도 받아야 한다.

## 4. 권위 처리와 경계

1. World 규칙이 서버 로컬 생성/변경/제거 요청을 제출한다. Client 상호작용이 원인이면 소유·거리·대상·cooldown을 서버에서 검사한다.
2. 서버는 유효 지역·지면·충돌·수량 상한과 시각/줄기 짝을 검증한다.
3. 안전 Game Thread 경계에서 후보 상태를 staging한다. 현재 Native 순회 중 원판 배열이나 view를 재할당하지 않는다.
4. 서버 충돌과 Native 목록을 계약한 다음 결정 경계에 맞춰 갱신한다. 몸이 새 원판 안에 있으면 기존 Native 밀어내기와 reset 의미를 확인한다.
5. 성공한 revision을 publish하고 Client가 동일 변환으로 외형·충돌을 구성한다. 전체 원판이 아니라 재현 가능한 descriptor를 보낼 수 있으나 근사 규칙 판을 고정한다.
6. 실패하면 이전 확정 상태를 유지하고 사유를 기록한다. Native 적용 전 임의로 전체 변경 완료를 알리지 않는다.

충돌·Native 목록·Client 수신은 서로 다른 시점에 적용될 수 있다. revision·ready 상태로 아직 준비되지 않은 구간을 드러내며 한 packet의 전역 원자성을 가정하지 않는다. 플레이어 위치·충돌의 최종 권위는 서버다.

## 5. relevance·late join·streaming

동물 relevance만으로 장애물 충돌을 제거하면 안 된다. 플레이어가 접근할 영역의 충돌 준비 범위를 별도로 정의한다. 초기 소규모 fixture는 제한된 수의 동적 객체를 항상 관련 상태로 보내 정확성을 확인하고, 공간 relevance 최적화는 T11 실측 뒤 진행한다.

늦은 참가자는 현재 active 집합과 authored 제거 overlay를 받는다. 중간 생성 이벤트를 모두 재생하지 않아도 현재 상태를 만들 수 있어야 한다. Remove→동일 ID 재생성은 generation으로 과거 변경과 구분한다.

World Partition unload와 실제 벌목 제거를 구분한다. 서버가 논리에 필요한 충돌을 unload한 경우 기존 목록을 묵시적으로 삭제하지 않고 지원 범위를 진단한다. Client의 mesh 지연 로딩과 충돌 ready 지연도 별도로 기록한다.

## 6. Food·숲 시야와의 경계

T06 단독 변경은 Food를 바꾸지 않는다. F10에서 선택한 경우에만 [T09](09_ENVIRONMENTAL_SPATIAL_FOOD_ACCOUNTING.md)의 원장 조정과 묶는다. 숲 잎 시야 Foliage는 기본 OFF를 유지한다. 나무 복제가 들어왔다고 새 시야 규칙·덤불 배치를 자동으로 채택하지 않는다.

## 7. 개발 단계·산출물

- DO-A: 생성 규칙·전송 방식·최대 수·streaming 지원 범위를 F09로 확정한다.
- DO-B: authored/dynamic ID, descriptor·revision·삭제 수명을 구현한다.
- DO-C: 서버 충돌/Native adapter와 Client 외형/충돌 소비를 연결한다.
- DO-D: 생성·변경·제거·late join·세션 종료를 검증한다.
- DO-E: descriptor 목록·서버/Client 충돌 probe·Native 원판 비교·실행 로그를 인계한다.

## 8. 검증 시나리오

| ID | 조건 | 기대 결과 |
|---|---|---|
| DO01 | 서버가 나무 1개 생성 | A/B 모두 외형·줄기 충돌, Native 회피 |
| DO02 | 이동·크기 변경 | 동일 ID의 새 revision, 오래된 변경 거부 |
| DO03 | 제거 직후 late join | 나무·충돌·Native 원판 없음 |
| DO04 | Remove 후 같은 ID 새 generation | 과거 Add/Modify로 부활하지 않음 |
| DO05 | 수관 아래 빈 땅·줄기 probe | 수관은 통과, 줄기만 의도대로 막음 |
| DO06 | 새 원판 안에 동물 존재 | Native 안전 처리, Client reset/보간 회귀 없음 |
| DO07 | 지면 미준비·유효하지 않은 지역 | 대기/거부 명시, 유령 충돌 없음 |
| DO08 | Client 권한 없는 생성 요청 | 서버 거부, 확정 세계 변화 없음 |
| DO09 | unload/reload·월드 종료 | generation/overlay 유지 범위대로 처리, 잔류 Actor 0 |

## 9. 완료 조건

선택된 동적 기능 범위에서 서버/Client 충돌과 Native descriptor가 같은 revision에 수렴한다. 늦은 참가·제거·수량 상한을 통과한다. 원본 맵/에셋 충돌을 무단 변경하지 않고 별도 owned 복사·세션 상태로 개발한다.

## 10. Source·계약 근거

- [레벨 나무 배치 도구](../../../Source/AdaptiveEcosystem/AI/Policy/EcoV3PlaceTreesCommandlet.cpp)
- [환경 감시·시험용 대역](../../../Source/AdaptiveEcosystem/AI/Policy/EcoV3EnvWatch.cpp)
- [Native 세계 장애물](../../../Source/AdaptiveEcosystem/AI/Policy/EcoWorldV3.h)
- [팀 요청의 나무 짝·동적 복제](../../RL_Policy/TEAM_REQUESTS_V3.md), [시험 명령의 Standalone 제한](../../RL_Policy/LIVE_ADAPT_SPEC.md)
