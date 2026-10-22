# main 병합과 날씨 클래스 호환 복구 — 2026-10-22

`codex/social-shelter-handoff`의 `5cd07e4`에 `origin/main` **`ff4f287`**을 병합했다. main에만 있던 3개 커밋의 지역별 비·눈·나무 배치 에셋 251개를 반영했다. Git 충돌은 없었으며, main 기준 251개 경로는 병합 후에도 main과 동일하다. 기존 JYU 맵·ExternalActors·소스·설정은 병합으로 변경하지 않았다.

## 커밋·PR 인계

- 병합 커밋: **`29c6491` — 통합: main 날씨·나무 배치 반영과 기존 동물 기능 호환 복구**. `origin/codex/social-shelter-handoff`에 push했다.
- [PR #14 — 동물 행동·경보·애니메이션과 테스트 은신처 통합](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/14): `codex/social-shelter-handoff` → `main`. 기존 동물 기능 전체와 이번 main 호환 복구를 포함한다. 제목·설명은 한글이다.
- 2026-10-22 인계 갱신 전 조회 결과 OPEN / MERGEABLE / REVIEW_REQUIRED, mergeStateStatus BLOCKED. **충돌은 없고 승인 대기**다. main 보호 규칙은 마지막 push 작성자 외 **1명 승인**이며 설정을 바꾸지 않았다. main 병합 완료로 기록하지 않는다.
- 새 채팅은 [작업 인계](JYU_CHAT_HANDOFF_20261022.md)를 읽고 현재 Git 및 PR 상태를 다시 확인한다. 이 절의 추가는 문서 갱신으로, 아래 빌드·게임 검증을 추가 실행한 것은 아니다.

## 복구가 필요했던 실제 참조

main의 `/Game/Actors/BP_WeatherManager_PlayerFollow`는 이동 후 경로 `/Game/SHC/Blueprints/Weather/BP_WeatherManager_PlayerFollow`로 향하는 redirector다. 하지만 대상 Blueprint가 main 트리에 없어 실제 로드가 실패했다. AssetRegistry에서 다음 참조를 확인했다.

- `/Game/__ExternalActors__/JWJ/Integration_JwJ/2/GN/1COCEP0H267C5GEIT6OC2U`
- `/Game/__ExternalActors__/JYU/Maps/LV_JYU_RefugeSafety/D/CC/A8GYD6I4RFY6AXCZATRQZO`
- `/Game/__ExternalActors__/JYU/Maps/LV_JYU_V3Integration/A/G2/YM48ZA2RQF8DTCMOD5JYJJ`

누락된 목적지에 **main의 현재 `BP_WeatherManager`를 상속하는 자식 Blueprint 하나**를 추가했다. 부모가 가진 플레이어 위치 기반 날씨 처리와 SHC 에셋 참조를 그대로 사용하며 별도 이벤트 그래프를 복제하지 않는다. 삭제된 옛 비·소리 에셋을 되살리거나 원본 팀 레벨을 다시 저장하지 않는다. 기존 redirector와 배치 Actor의 클래스 경로를 보존해 JWJ/JYU 참조를 함께 해결한다.

저작·재검증 도구는 [ensure_weather_player_follow_compatibility.py](../../Tools/Editor/ensure_weather_player_follow_compatibility.py)다. 같은 소유 표식·부모의 기존 에셋은 덮어쓰지 않고 검증하며, 다른 작성자의 목적지 에셋이 있으면 중단한다. `LoadBlueprintClass`는 redirector의 AssetRegistry 타입을 먼저 검사하므로 이전 경로 검증은 `unreal.load_class`로 실제 generated class를 로드한다.

## 이번 검증

- 직접 `UnrealBuildTool.exe AdaptiveEcosystemEditor Win64 Development` 성공, exit 0. 실행 중 프로세스를 중단하거나 중복 빌드하지 않았다.
- 전체 자동화 **147개: Success 146, 예상 warning 1, Fail 0, NotRun 0**. 기존 missing-save fixture 경고이며 이 실행은 호환 에셋 추가 전 병합 빌드에서 수행했다. C++/빌드 입력은 이후 바뀌지 않았다.
- 새 엔진 세션에서 날씨 경로 9개의 Blueprint 메모리 컴파일과 이전 generated class → 복원된 자식 클래스 로드를 확인했다. main 원본 에셋은 저장하지 않았다.
- D3D11 실제 에디터·일반 PIE 40초, 80회 관찰: 사슴 기록 3,819개, 늑대 기록 160개. 보호 798·보호 구역 안 앉은 자세 237·점유 141, 관찰된 내부 늑대 0. 은신처 12/12 준비 완료. 이는 반복 표본 수이며 고유 개체 수가 아니다.
- PIE의 세 지역 Native 로그에서 내부 늑대·스텝/내부 포획 위반 0을 확인했다. 체크인 요약에서 카메라 주변 표본과 지역별 로그 집계를 구분한다.
- Dedicated 110초와 같은 서버 Client A/B 순차 접속은 모두 exit 0. 두 Client의 은신처 count/ready/visible은 모두 12이고, 논리 개체·Native Step은 0이다. 수신 표현은 각각 최대 62/48개였다. 서버 세 지역의 750 Native steps 로그에서 내부 늑대·스텝/내부 포획 위반 0, Dedicated 표현 0을 확인했다.
- 체크인 저작 도구의 기존 에셋 재검증도 새 세션에서 성공했다. 부모 상속과 소유 표식을 확인하며 이 경로에서는 파일을 다시 저장하지 않는다.

네트워크 및 최종 재현 결과는 [검증 요약](Evidence/JYU_V3/MainMerge_20261022.json)에 기록한다. [실제 PIE 화면](Evidence/JYU_V3/MainMerge_20261022_RefugeClose.png)에서 테스트 은신처 외형·사슴 자세를 육안 확인했다. 로컬 raw 결과는 `Saved/MainMerge_20261022/`에 있으며 기존 10월 16일 기록은 덮어쓰지 않았다.

기존 `LowLevelTestAdapter`의 시작 시 `Condition failed` 15개는 이번 일반 에디터 시작에도 나타났다. 이전 검증 기록에도 있는 엔진 시작 메시지로, 이를 이번에 해결했다고 주장하지 않는다. 위 147개 프로젝트 자동화의 실패 수와 구분한다. 이번 검증은 새 날씨 모든 상태의 시각 비교나 Python 재학습·보호 세계 파리티 검증이 아니다. 기존 [보호 은신처 계약과 한계](JYU_REFUGE_SAFETY_20261016.md)는 유지한다.
