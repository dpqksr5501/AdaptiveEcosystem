# M4.0~M4.2 검증 기록

기준 엔진 UE 5.8. M4.1 기반 코드와 M4.2 연결별 간격 제한·우선 변경·수동 진단을 구현했다. 자동화 테스트는 요청에 따라 작성·실행하지 않았다.

## M4.2 — 2026-10-06

| 항목 | 결과 |
| --- | --- |
| M4.2 최초 UBT 빌드 | 성공: AdaptiveEcosystemEditor Win64 Development, 10 actions, Result: Succeeded |
| 최종 진단 코드 포함 UBT 빌드 | 성공: 동일 target, 4 actions, Result: Succeeded, 6.76초 |
| 변경 형식 검사 | git diff --check 통과 (기존 LF/CRLF 안내만 출력) |
| 일반 Transform 간격 | 현재 연결 AgentData.LastUpdateTime과 Params.UpdateInterval 비교; 검사 후 정지 여부와 무관하게 시간 갱신 |
| 우선 상태 | Add, Region/identity, 양자화 HP/Energy/life, reset, High 승격 검사 구현 |
| Remove | 기존 엔진 Off/pending destruction 경로 유지; Modify gate를 통과하지 않음 |
| 연결별 상태 보존 | 설치된 UE 5.8 SyncToMass/SyncFromMass 경계 확인; 마지막 시각은 연결별 AgentsData에 저장 |
| 수동 계측 | Bubble별 누적 Adds/Removes, per-LOD Entries/Gated/Checks/Dirty/Priority/HighPromotions, TraceSamples |
| 수동 편집 | authority-only SetVitals/Teleport; Mass processing 외 경계·중복 ID 거부·Alive 개체 한정 |
| 정지/이동 LOD 간격 실측, 서로 다른 거리의 두 Client | 미실행 |
| Region/visual/death/reset 우선 전달, High 승격, Off/파괴 Remove | PIE 미실행; 소스와 빌드 검증만 완료 |
| Late Join / 재진입 / 지연 템플릿 / 접속 종료 | M4.2 변경 이후 미실행 |
| CPU/Network trace / 대규모 승격 비용 / 대역폭 | 미측정 |

[구현 계약·관련 소스](M4_2_REPLICATION_INTERVAL.md), [수동 실행 절차](M4_EDITOR_TEST.md)를 연결했다. Docs/README, Roadmap/README 및 M4 개요·계획에서도 접근할 수 있다. 첫 sandbox 내 빌드는 초기 도구 실행 이후 진전이 없어 해당 실행만 중단했고, 엔진/빌드 캐시에 접근할 수 있는 빌드로 위 성공 결과를 확인했다.

Energy/HP 변화는 우선 표본이므로 기본 대사·식사 설정에서 Low 간격보다 자주 dirty가 생길 수 있다. 순수 이동 실측에는 테스트 사본에서 대사/식사를 잠시 고정하는 절차를 제공했다. 서버 dirty 표본 간격을 packet 간격으로 간주하지 않는다. M4.0 baseline 실측과 M4.2 PIE 완료 게이트가 남아 있으며 M4 전체 완료를 선언하지 않는다.

기존 레벨·Bootstrap 에셋·DefaultGame.ini는 이번 M4.2 작업에서 편집하지 않았다. 기존 StructUtils 및 MassEntityHandle include deprecation 경고는 남아 있다. M4.4 보간/M4.5 표현/M4.6 연결 예산/M4.8 플레이어 사망 피드백과 ACK 보장은 후속 범위다.

## 이전 M4.0~M4.1 기록

| 항목 | 결과 |
| --- | --- |
| 첫 코드 변경 Editor Win64 Development UBT 빌드 | 성공 |
| 최종 변경 UBT 빌드 | 성공: AdaptiveEcosystemEditor Win64 Development, 10 actions, Result: Succeeded |
| 변경 형식 검사 | git diff --check 통과 |
| 설정/역할/ID/표본/연결 예산 계약 | M4_1_DATA_CONTRACT.md에 기록 |
| 수동 진단 | eco.M4.Dump, eco.M4.Dump details |
| Standalone / Host+1 / Host+2 / Late Join | 미실행 |
| 관심 범위 이탈·재진입 / 지연 템플릿 / Reset | 미실행 |
| CPU/Network baseline trace / Actor·인스턴스 수 / 대규모 성능 | 미측정 |

실제 PIE/네트워크 검증과 baseline 캡처는 M4_EDITOR_TEST.md대로 수행해야 한다. M4 전체 또는 M4.0 완료 보고서가 아니다. 새 진단은 월드별 authority/proxy 수, Alive 수, 중복/무효 ID, Bubble별 entry/pending 수와 상세 ID/Template/Sequence/time/revision을 출력한다. 후보 검색 시간, per-LOD 수, Actor/ISM 수를 자동 계측하지 않는다.

기존 StructUtils 플러그인 및 MassEntityHandle include deprecation 경고는 이번 작업 범위에서 수정하지 않았다. 기존 변경 파일과 레벨은 보존했다.
