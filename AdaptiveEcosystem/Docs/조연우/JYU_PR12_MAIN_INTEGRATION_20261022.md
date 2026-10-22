# PR #12 병합 이후 main 통합 — 2026-10-22

사용자 요청으로 최신 `origin/main` **`a74fcac`**(PR #12 병합)을 로컬 `main`에 fast-forward하고, `5e270f4`의 `codex/social-shelter-handoff`에 병합했다. Git 충돌은 없었다. PR #12는 GitHub에서 실제 MERGED 상태를 확인했다. 이번 작업은 로컬 병합이며 원격 작업 브랜치 push와 PR #14 병합은 수행하지 않는다.

## main 기준으로 유지한 변경

- v3 두뇌 로더·교체, 환경 감시·스냅숏, 장애물·날씨·숲 시야 및 관련 테스트·학습 기록을 반영했다. 숲 시야 등 선택 기능을 임의로 켜지 않았다.
- `eco.IntegratedV3.SocialControl` 기본 **0**을 유지한다. 기존 Social 처리·경보 표현은 남지만 Native 제어 훅은 옵션을 켰을 때만 연결된다. 기존 문서의 10월 16일 Social 활성 상태를 현재 기본값으로 해석하지 않는다. 연결 자체를 확인하려면 Play 전 `-EcoV3SocialControl=1`을 사용한다.
- main의 `ShelterSafe`·`ShelterFood` 규칙과 기존 `ProtectedRefuges` 생명주기를 유지한다. PPO 가중치·V1 계약·단일 Native 이동 writer는 이번 복구에서 수정하지 않았다.
- JYU 콘텐츠·ExternalActors는 이전 작업 브랜치와 Git diff가 없다. main에서 들어온 원본 팀 맵 변경은 그대로 반영했으며 별도 재저작하지 않았다.
- `TEAM_REQUESTS_V3.md`의 신호 전용 Social 재설계 등 신규 요청을 이번 병합 범위로 확대하지 않았다.

## 실제 실행에서 발견하고 복구한 문제

첫 빌드와 자동화 200개는 통과했으나 JYU 보호 맵은 `Highland`의 첫 결정 스텝에서 `Resource conservation receipt rejected`로 멈췄다. 프로세스 exit 0만으로 성공을 판정하지 않았다.

지형 준비 후 늦게 등록된 은신처를 `RefreshRefuges`가 추가하면 main의 `ApplyShelterFood`가 셀 용량과 남은 먹이를 줄인다. 기존 지역 자원 장부는 이 변화를 몰라 다음 소비·재생 거래의 시작량이 맞지 않았다. 은신처 제거로 용량이 복구되는 경우에도 장부 용량이 뒤처질 수 있었다.

`UEcologySimulationSubsystem::AdjustSpatialFoodHabitat`를 추가해 환경 변경에 따른 용량·먹이 감소를 별도 거래로 반영한다. 권위·거래 순서·직전량·유한값·보존식을 검증하고, 감소량은 섭식·재생과 별도로 누적한다. 은신처를 제거해 용량을 복구해도 먹이는 생성하지 않는다. 기존 `CommitSpatialFood` 검사를 완화하거나 매번 장부를 재등록하지 않는다. 거래가 거절되면 Native 스텝 전에 중단한다.

회귀 테스트는 늦은 은신처 등록 후 실제 Native 스텝 진행·지역 장부 동기화·제거 후 용량 복구와 먹이 보존을 확인한다. 기존 장부 테스트에는 오래된 양·중복 순번·비보존·NaN·먹이 생성 거절 및 이후 섭식·재생 진행을 추가했다.

## 검증 결과와 한계

- 최종 직접 `UnrealBuildTool.exe AdaptiveEcosystemEditor Win64 Development` 성공(exit 0, `Build02.log`). 실행 중 빌드·에디터를 중단하거나 중복 빌드하지 않았다.
- 전체 자동화 **201개: 성공 200, 예상 warning 1, 실패 0, 미실행 0**. warning은 기존 missing-save fixture다. 새 `AdaptiveEcosystem.Policy.V3.Refuge.LateRegistrationFoodLedger`도 성공했다.
- `/Game/JYU/Maps/LV_JYU_RefugeSafety`를 NullRHI Standalone으로 Social OFF/ON 각각 40초 구동하고 정상 타이머 종료(exit 0)했다. 두 실행 모두 자원 계약 오류·런타임 중단 없음. ON은 `Moving->Occupied` 전환 45건, OFF는 0건이다.
- 각 실행의 마지막 지역별 안전 로그는 세 지역 모두 Native step 225이며 내부 늑대·내부 포획 위반 0이다. 40초 종료 시점 전체 스텝 수와 마지막 30초 주기 로그를 혼동하지 않는다.
- 이번에는 화면 PIE·IK/오디오 시각 확인·Dedicated/Client·Python 재학습/파리티를 새로 검증하지 않았다. NullRHI `-game`에서 Editor AnimGraph 패키지 import와 천둥 AttachComponent warning이 있어, 이 실행만으로 표현의 무결함을 주장하지 않는다. 이전 10월 22일 화면/네트워크 검증과 별도 실행이다.

[체크인 검증 요약](Evidence/JYU_V3/MainMerge_PR12_20261022.json). 로컬 raw 로그·자동화 보고서는 `Saved/MainMerge_PR12_20261022/`에 보관하며 최초 실패 실행도 남겼다. 현재 병합 커밋은 `git log --merges -1`로 확인한다.
