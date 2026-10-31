# 문서 감사·갱신 기록 — 2026-10-23

요청: 기능 추가 뒤 여러 문서를 읽고 현재 동작·연결·실행·제한과 최신 작업 인계를 정리한다. 구현 Source 기준은 `581ce1d` + `e22dbbd`, 통합 main `a74fcac`다. 이번 변경은 Markdown뿐이며 C++/에셋/빌드 입력은 바꾸지 않았다.

## 발견한 불일치와 수정

| 발견 | 반영 |
|---|---|
| 최신 기능 문서에 PR14 Draft/원격 push 없음이 남음 | 사용자 요청으로 push·Ready 전환한 실제 상태를 현재 인계/계약/진입점에 반영. 날짜별 예전 기록은 과거로 표시 |
| 여러 최신 배너 아래 10-08/10-16 HEAD·맵·소비자 미연결을 현재로 오독 | 새 10-23 인수인계 추가, README 진입점 정리, 이전 인계/감사에 역사 범위 명시 |
| 루트 README가 서버 LLM 프로젝트로만 설명 | 실제 Mass/PPO Native·권위·폐루프 목표, V1/v3 구분과 핵심 문서 안내로 교체 |
| Source와 무관하게 Social 행동 훅이 항상 활성으로 읽힘 | 기본 SocialControl=0 신호 API와 보존한 opt-in 행동 제어를 구분 |
| 보호 Native struct 기본 OFF를 통합 기본값과 혼동 | 통합 ShelterSafe=1/ProtectedRefuges=1, 안전 담당 하나·생명주기와의 구분. 기존 Python 안전 파리티와 새 이주 ON 미검증 범위를 분리 |
| 지역 진입/여정 완료/복귀 집계의 의미가 섞임 | 실제 Region/context 인계와 끝점 정착, Finished에 복귀 포함, Blocked는 무진행 진단임을 실행 인계에 명시 |
| 오래된 Processor/TASK4 대기 목록이 현재 지시로 읽힘 | 현재 v3 완료 경계/소유권을 추가하고 초기 감사·목표 설계는 이력으로 유지 |
| 팀 요청의 후속 구현 추적 부재 | 작성자의 원문을 보존하고 조연우 통합 결과 표 추가. RL 학습·공식 맵·다른 담당 요청을 일괄 종료하지 않음 |
| 발표 위치가 예전 1016/출력 폴더로 남음 | 새 인계에 현재 바탕화면 최종 PPT와 외부 제작/캡처 폴더 명시. 개인 파일 미추적 유지 |

## 주요 갱신 문서

- [최신 인수인계](JYU_CHAT_HANDOFF_20261023.md), [조연우 시작 문서](README.md), [현재 상태](SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md).
- [이주·신호 계약](HERD_MIGRATION_AND_SIGNAL_CONTRACT.md), [디버그/재현](HERD_MIGRATION_DEBUG_20261023.md).
- [Social 아키텍처](SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md), [구현 가이드](SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md), [이동/예약 생명주기](SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md), [감각 계약](SOCIAL_SENSORY_RUNTIME.md).
- [v3 Social 인계](JYU_V3_SOCIAL_HANDOFF.md), [M4/v3 통합](JYU_M4_V3_INTEGRATION.md), [보호 은신처](JYU_REFUGE_SAFETY_20261016.md).
- [전체 아키텍처](../Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md), [Mass 실행 순서](../Mass/MASS_PROCESSOR_ORDER.md), [팀 요청 후속 확인](../RL_Policy/TEAM_REQUESTS_V3.md), 루트 README/AGENTS.
- 10-22 인수인계/main 병합/PR12 통합, 10-16 backend 감사는 최신 인계로 가는 이력 안내 추가. 당시 검증 수치·사용자 승인 기록은 재작성하지 않음.

## 확인 근거와 남긴 제한

Source의 `EcoPolicyV3SocialBridge.*`/감각 snapshot, `EcoHerdMigration.*`, `EcoCreatureLifecycle.cpp`, `EcoPolicyV3IntegratedSubsystem.cpp`, `EcoHerdMigrationDebug.*`/Inspector와 체크인 [기능 증거](Evidence/JYU_V3/HerdMigration_20261023.json)·[시각화 증거](Evidence/JYU_V3/HerdVisualization_20261023.json)를 대조했다. 현재 API·CVar·맵 파일 존재, 변경 문서 링크와 Git diff를 확인했다. 새로 추가한 상대 파일 링크의 누락은 없으며, 감각 문서의 사라진 로컬 로그 링크 2개는 이력 경로 표기로 고쳤다. 외부 발표자료 `먼저읽기.md`도 실제 바탕화면 PPT 경로로 맞췄다.

Source CVar 도움말의 SocialControl=1 설명에는 슬롯 없는 사슴의 외부 도주를 경고하던 예전 문구가 남아 있다. 현재 ApplyControl 보호 guard와 다르므로 도움말만으로 현재 동작을 판단하지 않는다. 이번 문서 작업에서는 C++ 문자열을 바꾸지 않았다.

문서의 코드/모형 예시는 여전히 목표 설계를 포함한다. 자동화 성공 수를 임의로 늘리거나 새 테스트를 실행했다고 기록하지 않는다. 이전 최종 실행은 기능 Build13/Automation07, 디버그 Build04/Automation03 각각 203개(202 성공 + 예상 warning 1), 실패/미실행 0이다. 발표 촬영은 Build03 Story03이며 최종 Build04 수정 후 다시 촬영했다는 뜻이 아니다.

새 UBT·PIE·멀티·Shipping/cook은 실행하지 않았다. 장기 균형, 모든 무리 성공, Highland corridor, 출생/새끼, merge/split, 포식자 공동 이주, Client 계획 복제, 새 이주 ON 세계 전체 Python 파리티/재학습을 완료로 확대하지 않는다. 추가 기능 후보와 완료 기준은 최신 인수인계에 기록했다.
