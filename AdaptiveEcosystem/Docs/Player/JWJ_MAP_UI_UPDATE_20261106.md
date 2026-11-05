# 현재 레벨 생태계 지도 표시 수정

2026-11-06 사용자 요청 반영. 맵/에셋은 변경하지 않았다.

- 지도 좌표의 지역 중심 Y에 이름을 배치하던 방식은 두 지역이 동서 방향으로 나란할 때 이름과 Food/Pop이 겹쳤다. 지도 아래에 지역별 44px 행을 할당하고 이름과 Food/Pop을 분리했다.
- 지도 영역을 패널 전체 너비로 확장했다. 패널은 HP 아래에서 시작하며 지역 수에 따라 높이를 계산한다. 긴 문구는 패널 너비에 맞춰 말줄임한다.
- 사슴 초록, 늑대 빨강, 살아 있는 플레이어 노랑으로 표시한다. 선택한 이주 계획 소속 사슴은 흰 테두리를 덧붙이며 종별 색상을 유지한다.
- 기존 사슴 Native body 위치와 새 늑대 Native state 위치, 서버 PlayerController가 소유한 Pawn 위치를 읽는다. 늑대/플레이어는 별도 표시 배열에 저장하므로 무리 인원/도착 집계에 섞이지 않는다. JSON의 wolves/players는 추가 필드다.
- 기존 4Hz snapshot/권위 전용 표시를 유지한다. 지도에 포함된 서식지·경로 경계 밖의 개체는 표시하지 않는다. Client에 권위 데이터를 새로 복제하거나 생태계 논리를 변경하지 않는다.

직접 UBT `AdaptiveEcosystemEditor Win64 Development` 성공: `Saved/IntegrationBuilds/Milestone_Final_20261106_023021.log`. 첫 빌드의 const GetPawn 반환형 추론 오류를 명시적 APawn 포인터로 수정한 후 성공했다.

현재 `/Game/JWJ/1102_Integration_JWJ`의 실제 1280×720 Standalone 화면에서 겹침 해소·세 종류 색상을 캡처 확인했다. snapshot은 사슴24·늑대8·플레이어1이며 플레이어 위치가 실제 Pawn 위치와 일치한다. 정상 종료 0. 근거: `Saved/PlayerHunting_20261105/MapUI/{MapUI.png,Snapshot.json,Result.json}` 및 `MapUI.log`. 전체 자동화/멀티플레이·여러 해상도 검증을 새로 실행한 것은 아니다.

최초 지도 구현의 Git 작성자는 **조연우**, 커밋 `e22dbbdbb346387c0d11bf1e5f90134af297e736`(2026-10-23), 제목은 `feat: 무리 이주 경로·목적지와 실제 진행 디버그 시각화`다. 이번 겹침/종별 마커 변경은 이 채팅에서 Codex가 수행했고 커밋/push하지 않았다.

관련 코드: [지도 그리기와 읽기 전용 위치 수집](../../Source/AdaptiveEcosystem/Creature/Debug/EcoHerdMigrationDebug.cpp), [스냅샷 구조](../../Source/AdaptiveEcosystem/Creature/Debug/EcoHerdMigrationDebug.h).
