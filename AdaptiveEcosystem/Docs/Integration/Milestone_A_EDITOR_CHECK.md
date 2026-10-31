# A — 기준선 복구 수동 확인

상태: 구현 중, 직접 빌드/실행 결과는 [진행 기록](M4_IMPLEMENTATION_PROGRESS.md) 참조. 자동화 테스트 생략.

새 복사 레벨에서는 [수동 설정 가이드](M4_NEW_LEVEL_MANUAL_SETUP.md)의 Actor/Groups 설정 후 Coordinator의 **Validate Editor Setup** 버튼으로 Errors=0을 먼저 확인한다. 이 버튼은 배치를 수정하지 않는다. 서버/Client의 role별 fragment 구성도 생성 전에 검사한다.

1. Editor 종료 상태에서 직접 UBT 빌드를 완료한다. 실행 중 빌드/Editor를 중단하거나 새 빌드를 겹치지 않는다.
2. Box: `/Game/JWJ/Jang_lv`, Play → Standalone. 기존 Forest_A/B Bootstrap·EntityConfig·서로의 AdjacentRegionIds 유지.
3. `Debug.Starvation.Forest_A` → 같은 ID가 A→B 실제 도착. `eco.M4.Dump details`로 Region/Alive 확인.
4. 동물: `/Game/Creatures/Integrated/L_EcoCreatureIntegration` 또는 `/Game/Map/LV_Ecosystem_IntegrationTest`. Coordinator 하나, 기존 M3 Bootstrap 없음, Enable Waves=false.
5. `eco.Integration.Dump`, `eco.Shelter.Log 1` → Ready=1, 사슴/늑대 이동, Reserved→Moving→Occupied→release.

통과 기준: 양쪽 fixture에서 Runtime stopped/Assertion/Fatal 없음, 동물 Resident 속도가 이주 reconcile 때 0으로 덮어써지지 않음. 빌드 성공과 이 수동 통과를 별도 기록한다.
