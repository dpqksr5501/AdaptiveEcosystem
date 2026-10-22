# 이주 경로·목적지 디버그와 실제 장면 확인

2026-10-23. 기준 구현 `581ce1d`에 추가한 읽기 전용 표현이다. 이주 정책·Native 단일 이동·자원 거래·복제 transport는 변경하지 않는다. [기존 이주 계약](HERD_MIGRATION_AND_SIGNAL_CONTRACT.md)을 함께 읽는다.

## 에디터에서 확인

`/Game/JYU/Maps/LV_JYU_HerdMigration`을 열어 Play하면 오른쪽에 이주 지도가 자동으로 표시된다. 기존 이주 opt-in이 꺼진 맵에는 자동 표시하지 않는다. Client는 논리 지도 대신 기존 수신 표현만 사용한다.

| 조작 | 표시/동작 |
|---|---|
| `M` | 이주 지도·월드 경로 표시 켜기/끄기 |
| `[` / `]` | 현재 세션의 무리 계획 선택. 완료된 계획도 확인 가능 |
| `Tab` / 가운데 마우스 | 기존 Inspector로 동물을 선택하면 그 개체의 계획을 선택 |
| `eco.HerdMigration.Debug 1` | 지도, 알려진 경로, 선택한 무리와 목적지 표시 |
| `eco.HerdMigration.Debug 2` | 모든 이동 구성원의 실제 위치와 다음 목표 연결선도 표시 |
| `eco.HerdMigration.Debug 0` | 이주 표시 숨기기 |
| `eco.HerdMigration.Debug -1` | authored 이주 world 자동 표시로 복귀 |
| `eco.Creature.Labels 0` | 동물 이름표만 숨기기. 기본값 1 유지 |
| `eco.Inspector.Visible 0` | 왼쪽 상세 패널만 숨기기. 기본값 1 유지 |

가뭄 시연은 `eco.HerdMigration.Test.Drought Barren`을 한 번 실행한다. 명령은 즉시 모든 동물을 이동시키는 대신 실제 먹이 감소와 재생 중단을 적용한다. 지속 부족 확인·집결·경로 이동·실제 진입에는 별도의 시간이 걸린다. Play 종료/재시작으로 초기 조건에 돌아간다.

## 화면을 읽는 법

- **하늘색 선:** authored 경로. 선택한 계획이 있으면 화살표는 그 계획의 진행 방향을 따른다. 복귀 계획은 실제로 뒤집힌 경로 방향을 표시한다.
- **노란 영역/구:** 선택한 계획의 현재 목적지와 경로 끝. 원래 Forest가 목적지였더라도 복귀하면 현재 목적지 Barren을 표시한다.
- **작은 점:** 현재 살아 있는 Native 사슴의 실제 세계 위치. 흰 점/구와 연결선은 선택한 계획의 구성원과 다음 목표다.
- **지역의 사각형:** 전체 `AEcologyRegion` 경계가 아니라 Native habitat footprint다. 현재 경로와 연결된 지역만 범위에 포함해 카메라 밖의 이동을 볼 수 있다.
- **Food/Pop:** 기존 Native `FoodFraction()`과 M4 Ecology의 마지막 완료 개체군 집계를 읽는다. 지도 표시는 자원이나 개체를 만들지 않는다.
- **Active herds / Finished:** 진행 중/종료된 공동 계획 수. Finished에는 안전하게 복귀한 계획도 포함하므로 Forest 도착 수와 같지 않다.
- **In target:** 실제 RegionId가 현재 목적지인 살아 있는 계획 구성원 수. **Finished:** 경로 끝 여행을 완료한 수. 목적지 지역 진입과 여행 완료는 서로 다른 시점이다.

`Preparing` 집결, `Traveling` 이동, `Regrouping` 재집결, `Resting` 휴식, `Blocked` 무진행, `Settled` 종료를 구분한다. **Blocked는 일정 시간 진행이 없다는 진단이며 지형 충돌을 확정한 원인은 아니다.** Native 위협 회피·구성원 대기 등도 진행을 늦출 수 있다. 왼쪽 Inspector의 개체별 `decision_reason`을 함께 확인한다.

## 연결 구조

[EcoHerdMigrationDebug](../../Source/AdaptiveEcosystem/Creature/Debug/EcoHerdMigrationDebug.cpp)는 GameThread의 Mass processing 외 경계에서 값 snapshot을 만든다. HUD는 최대 4Hz로 갱신된 snapshot을 그린다. Native body의 실제 위치·현재 Region·공동 계획·기존 자원 집계만 읽으며 Raw Request/Control/Transform/Velocity/Food를 쓰지 않는다. 새로운 Tick Subsystem이나 replication payload는 없다.

`UEcoCreatureInspectionLibrary::CaptureMigration`은 같은 값을 JSON으로 내보낸다. Client/비활성 Native world에서는 false와 빈 문자열을 반환한다. `SelectAgentForInspection`/`FocusMigrationPlan`은 관찰 대상만 바꾼다.

## 촬영과 검증

`Tools/Editor/capture_jyu_migration_story.py`는 원본 팀 레벨을 저장하지 않고 owned 복사 맵에서 실제 PIE를 시작한다. 카메라를 바꾸고, 관찰자 위협을 비활성화하고, 명시적 가뭄 fixture를 적용한다. 개체를 teleport하거나 PPO 요청/가중치/이주 상태를 강제로 바꾸지 않는다. 출발·경로 이동·휴식/재개·동일 개체의 지역 진입 전후·정착·은신처·막힘 장면과 해당 시점 JSON을 저장한 뒤 정상 EndPlay/종료한다. 성공한 장면을 포착하지 못하면 해당 파일을 만들지 않는다.

개인 발표 캡처는 **필수 `-MigrationStoryOutput=<저장소 밖 경로>`**를 지정해야 한다. 저장소 내부 개인 발표 산출물은 거부한다. PPT/PDF/대본/렌더/임시 작업은 Root AGENTS 9절의 바탕화면 발표자료 폴더에 두고 Git에 넣지 않는다. 저장소에는 기능 Source·재현 도구·계약과 행동 검증 요약만 남긴다.

검증 근거는 `Saved/HerdVisualization_20261023`의 직접 UBT 로그와 Automation 보고서, [검증 요약](Evidence/JYU_V3/HerdVisualization_20261023.json)을 따른다. 전체 자동화에는 기존 실제 Native 여정 시험의 지도 snapshot/경로/두 지역/실제 구성원/JSON 검증을 추가했다. 개인 발표용 PNG는 위 외부 폴더의 촬영 기록과 함께 보존한다.

검증은 제어된 가뭄에서 실제로 관찰한 기능 동작이다. 일부 무리는 Forest 정착, 일부는 무진행 후 복귀했다. 모든 무리가 항상 성공한다거나 장시간 균형·고지대 경로·Python ON 세계 파리티를 검증했다는 뜻이 아니다. PR #14는 Draft, 원격 push 없음 상태를 유지한다.
