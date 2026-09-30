# M3 검증 기록

기준일: 2026-09-28. 코드/빌드 확인과 실제 플레이 실행 결과를 구분한다. M3 전체 완료 선언이 아니다.

| 단계 | 코드 및 빌드 | 수동 실행 기록 |
| --- | --- | --- |
| M3.1 | 기존 문서에 UE 5.8 Editor 빌드 성공 기록 있음 | [M3.1 절차](M3_1_EDITOR_TEST.md) 참고. 이번 작업에서 재실행하지 않음 |
| M3.2 | 기존 소비/이벤트/Starvation 경로 재사용 | [M3.2 절차](M3_2_EDITOR_TEST.md) 참고. 이전 기록을 이번 실행 결과로 간주하지 않음 |
| M3.3 | 이주·이동·도착·집계·요약 복제·읽기 전용 표시 구현 | 첨부 Standalone 로그에서 A→B 이주 확인. [M3.3 설정 및 절차](M3_3_EDITOR_TEST.md)의 동시 Spawn Waves/네트워크 재확인 대기 |

이번 요청에서는 자동화 테스트를 작성하거나 실행하지 않았다.

## 빌드

UE 5.8 `Build.bat AdaptiveEcosystemEditor Win64 Development -Project=.../AdaptiveEcosystem.uproject -WaitMutex -NoHotReloadFromIDE -NoXGE` 실행 성공. `Manual Migration Test` 우회 설정 제거 후 같은 빌드를 다시 실행해 성공했다. 기존 StructUtils 플러그인 및 MassEntityHandle include deprecation 경고가 남아 있다. `git diff --check`로 변경 형식 확인.

## 실행 확인 대기표

| 시나리오 | 재현 설정/판정 | 실제 결과 |
| --- | --- | --- |
| 수동 A→B 이주 | A/B 양방향 인접, A Starvation → 같은 ID의 B 도착 | 첨부 Standalone 로그에서 A Food=50→0, ID 1~8 도착, Day 3 A/B=0/16 확인 |
| 수동 이벤트와 생성 주기 공존 | Spawn Waves=true, Day/Night 간격이 Phase보다 짧음. A 고갈 후 A 웨이브 스킵/B 웨이브 진행 | 우회 설정 제거 후 PIE 재확인 필요 |
| 이동 중 양쪽 고갈 | A 이주 중 B Starvation → 현재 위치 대기, 전체 16/ID 유지 | 미실행 |
| 소비/낮/밤 이벤트 고갈 | M3.3 절차의 개별 설정 | 미실행 |
| 도착 소비 예약 | Arrived 로그 NextFeed=Observed+10, 해당 ID는 B 소비 참여 | 미실행 |
| 생성 상한과 이주 | B Population이 64를 넘더라도 도착 허용, 전체 개체 수 보존 | 미실행 |
| Host/Client | 요약 일치, 관련 Box의 Transform/Region 전달 | 미실행 |
| Late Join/재진입/PIE 재시작 | 중복·잔여 프록시 및 재스폰 없음 | 미실행 |
| 30/60 FPS·긴 프레임 | 도착 중복 및 밀린 소비 폭주 없음 | 미실행 |
| 128개체 15분 | 자원/집계/예약 안정성 | 미실행 |

실행 기록에는 월드 이름, Epoch, Step, ID, 이벤트 ActualLoss, 도착 Observed/NextFeed, 지역 Pop 합을 남긴다. 전체 Population과 Client relevance 부분집합의 프록시 수를 혼동하지 않는다.

## 범위와 남은 일

기존 레벨·EntityConfig 에셋은 변경하지 않았다. 수동 이주 테스트가 모든 Spawn Waves를 끄던 `Manual Migration Test` 설정과 `DefaultGame.ini`의 해당 키를 제거했다. 현재는 각 Project Settings 스위치가 독립적으로 적용된다. 사용자가 에디터에서 인접 지역, 식량/개체 수, Arrival 높이를 설정할 수 있다. 기본 이주 판단은 1초, 조향/이동은 프레임마다, 도착 검사는 자원 완료 단계, 요약은 1초다. 엔진 0.1초 이동 delta clamp에 따른 hitch 시 이동 지연은 문서화했다.

본체는 Mass이며 Actor는 표현만 담당한다. 자동 Food 재생, Energy/기아·사망, V1 Observation/Utility 확장, NavMesh/장애물 회피/정교한 Flock은 남은 범위다. 수동 시나리오의 기대 결과를 검증 완료로 표시하지 않았다.
