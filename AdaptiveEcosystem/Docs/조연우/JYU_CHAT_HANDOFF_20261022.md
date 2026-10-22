# 조연우 작업 인계 — 다른 채팅에서 이어가기

> **최신 상태:** main `ff4f287`을 작업 브랜치에 병합하고 날씨 클래스 호환 복구·빌드·PIE·네트워크 검증을 마쳤다. 구현 기준은 `29c6491`이며 push 완료다. [PR #14 — 동물 행동·경보·애니메이션과 테스트 은신처 통합](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/14)은 2026-10-22 확인 시 **OPEN·충돌 없음·승인 대기**다. [main 병합 기록](JYU_MAIN_MERGE_20261022.md)과 아래 PR 인계를 먼저 읽는다. 이 문서 이후의 문서 커밋과 실제 PR 상태는 재개 시 다시 확인한다.

작성일: **2026-10-22**. 이 문서는 대화 기록 없이 현재 프로젝트를 이어가기 위한 시작점이다. 루트 [AGENTS.md](../../../AGENTS.md)를 먼저 읽고, 아래 계약과 실제 Source를 대조한다. 과거 문서의 Pending이나 목표 설계를 현재 구현으로 해석하지 않는다.

## 1. 지금 어디에서 작업하는가

| 항목 | 확인한 상태 |
| --- | --- |
| 저장소 | `C:/Users/I/Documents/GitHub/AdaptiveEcosystem` |
| 프로젝트 | `C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/AdaptiveEcosystem.uproject` |
| 엔진 | UE 5.8, 기존 화면 검증 기록은 5.8.3 |
| 브랜치 / 구현 기준 | `codex/social-shelter-handoff` / `29c6491` (main 병합·호환 복구), 이후 문서 갱신 커밋은 `git log`로 확인 |
| 작업 트리 | 이번 인계 갱신 직전 clean, 로컬 추적 참조 기준 origin과 동일 |
| 병합한 main | `ff4f287` — 지역별 비·눈 날씨와 나무 배치 포함 |
| PR | [#14](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/14), 작업 브랜치 → `main`, 확인 당시 승인 대기 |
| worktree | `git worktree list`에 원래 저장소 한 곳만 있음. 이전 통합 worktree를 열지 않는다 |
| 최신 기능 확인 맵 | `/Game/JYU/Maps/LV_JYU_RefugeSafety` |
| 이전 통합 확인 맵 | `/Game/JYU/Maps/LV_JYU_V3Integration` |

2026-10-22에 fetch 후 main을 병합·검증하고 `29c6491`까지 push했다. 이는 모든 팀 개인 브랜치의 최신 커밋을 추가 통합했다는 뜻은 아니다. 이후 팀 브랜치 통합이 필요하면 작업 트리를 보존하고 fetch 후 실제 차이를 검토한다. **이번 PR 인계 문서 갱신만으로 빌드·PIE를 추가 실행하지는 않았다.**

### PR #14와 다음 채팅에서 할 일

- 제목: **동물 행동·경보·애니메이션과 테스트 은신처 통합**. 기존 Social·감각·M4/v3·애니메이션/IK·발소리·Client 표현·테스트 은신처와 작업 인계를 main에 반영하는 PR이다. 아직 main으로 병합 완료된 상태는 아니다.
- main에만 있던 3개 커밋의 에셋 251개는 충돌 없이 반영했다. 끊어진 `BP_WeatherManager_PlayerFollow` 이동 경로는 main 날씨 관리자를 상속하는 얇은 자식 Blueprint로 복구했다. 원본 main 그래프·배치와 JYU 복사 맵을 보존했다.
- 10월 22일 직접 UBT 성공, 전체 자동화 147개(성공 146·예상 warning 1·실패 0), 날씨 Blueprint 9개 컴파일 및 이전 클래스 경로 로드, 실제 PIE 40초와 화면 확인을 완료했다. Dedicated 110초와 Client 두 차례 접속도 정상 종료했다. 양 Client 논리 개체/Native Step 0, 은신처 ready/visible 12. 서버 세 지역 750 Native steps에서 내부 늑대·내부 포획 위반 0이다. 조건·한계·근거는 [병합 기록](JYU_MAIN_MERGE_20261022.md)에 있다.
- 현재 main 보호 규칙은 **PR 작성자 외 쓰기 권한이 있는 팀원 1명의 승인**이다. 같은 날 사용자 요청으로 `require_last_push_approval`만 false로 바꿨다. 기존 승인이 있어도 새 push 뒤 다시 승인해야 하던 추가 조건을 해제한 것이다. `required_approving_review_count=1`, `dismiss_stale_reviews=false`, 관리자 보호는 유지한다. 이후 push가 기존 승인을 자동 무효화하지 않으므로 변경된 코드는 계속 리뷰해야 한다.
- 설정 변경 후 PR #12는 `APPROVED / CLEAN / MERGEABLE`이 됐고, PR #14는 승인 0개라 `REVIEW_REQUIRED / BLOCKED / MERGEABLE`이었다. PR을 실제 병합한 것은 아니다. 승인 버튼 자체의 UI 비활성화 원인을 고쳤다고 주장하지 않으며, 확인한 병합 차단 조건을 해결한 것이다. 변경 전후 로컬 설정 기록은 `Saved/GitHubReviewFix_20261022/`에 있다.
- 재개하면 `git status`, `git log`, PR #14의 현재 승인/병합 상태부터 확인한다. 기존 PR을 사용하고 중복 PR을 만들지 않는다. 승인·병합이 끝났다면 실제 main 반영 여부를 확인한 뒤 사용자가 지정한 다음 작업으로 이어간다. 아직 새 후속 기능은 지정되지 않았다.

주요 이력은 `22eb1b6`(팀 브랜치·v3 Social 연결), `89f6d2d`(근접 반응 진단), `a88eac8`(보호 은신처), `19429e9`(기존 사용자 에셋 저장본 반영), `5885333`(개인 발표 산출물 분리), `5cd07e4`(작업 인계), `29c6491`(main 병합·날씨 호환 복구)이다. 사용자 에셋 68개를 처음 코드 커밋에서 제외한 기록은 이후 별도 에셋 커밋 전의 이력이다. 다시 미처리 변경으로 간주하지 않는다.

## 2. 프로젝트 목표와 조연우 역할

프로젝트는 **Mass 논리 개체 + Python PPO 학습 + C++ Native 추론 + Social + 단일 이동 경로**를 연결하는 동적 생태계다. 자원 소비·포식·사망·지역 상태가 다시 개체 관측과 행동에 영향을 주는 폐루프가 목표이며, 모든 환경·이주 기능까지 완료된 상태는 아니다.

조연우는 **무리·경보·은신처, 시야·청각·기억, 동물 표현·애니메이션·발소리와 통합 검증**을 담당한다. 권신혁은 PPO/Native v3, 장원준은 M4 공통 런타임·네트워크 관련 구현을 맡는다. 담당 경계는 코드와 팀의 최신 합의를 우선한다.

- 서버/Standalone이 논리 권위다. Client는 DTO를 받아 Actor·Mesh·AnimBP·오디오를 표현한다.
- Social은 행동 의도와 슬롯 Request/Feedback을 관리한다. 위치·Vitals·자원 적분이나 복제 transport를 새로 소유하지 않는다.
- 기본 V1은 7관측/4출력이다. opt-in v3는 R1b **18관측/5행동·mask2**이며 서로 다른 계약이다. 가중치나 관측 차원을 임의 수정하지 않는다.
- v3의 단일 Native movement/vitals writer와 기존 V1/Custom Movement 혼용 가드를 유지한다. 런타임 Python 추론은 금지한다.
- 외부 MassFlock 패키지를 설치한 구현이 아니다. 자체 이웃 탐색·조향을 사용한다. Persistent Herd와 실제 flock 이동은 별개 책임이다.

## 3. 지금 연결된 기능

| 범위 | 현재 구현과 읽을 근거 |
| --- | --- |
| M4 + v3 | 공통 권위·identity/lifecycle/resource/replication에 Native v3 연결. [통합 기록](JYU_M4_V3_INTEGRATION.md), [backend 감사](JYU_THREAT_AND_BACKEND_AUDIT_20261016.md) |
| 실제 Social 인계 | 직접 감지/Player.Footstep → Herd observed 채널 → Alarm/SocialResponse → Shelter 예약/Request → Native control → 실제 이동/도착 Feedback → 점유·lease 정리. Raw Request를 덮어쓰지 않으며 공유 기억을 직접 관측으로 재발행하지 않음. [인계 계약](JYU_V3_SOCIAL_HANDOFF.md) |
| 동물 표현 | 행동 프로필·AnimBP·먹기/경계/숨기 등 자세, 감각 반응, 실제 플레이어 발걸음의 서버 소음, 로컬 발 접촉 오디오, Client 표현, Inspector 기록 연결. [통합 기록](JYU_M4_V3_INTEGRATION.md) |
| 사슴 IK | 입력 포즈 기반 다리 체인 계산, 지면 trace와 AnyThread 포즈 계산 분리, 제한된 발 보정·몸통 하강. 숨기/수면에서는 IK 감쇠. [IK 검증과 한계](JYU_IK_VALIDATION.md) |
| 테스트 은신처 | 새 복사 맵에 수풀·바위 Blueprint 12곳. 실제 영역의 늑대 swept 이동 차단, 내부 사슴 포획 후보 제외, 지면 슬롯·도착 검증, 늦은 지형 등록·삭제 처리. [보호 은신처 계약](JYU_REFUGE_SAFETY_20261016.md) |

통합에 포함됐다고 기록된 팀 기준은 신혁 `b5c7384`, 원준 M4 `67c860c`다. 현재 원격 최신 여부는 별도 확인 대상이다.

보호 은신처는 **Unreal 세계 규칙 확장**이다. 통합 설정/CVar `eco.IntegratedV3.ProtectedRefuges=1`에서는 보호하지만 Native 기준 설정은 OFF다. PPO 가중치·기본 Python 세계는 바꾸지 않았으므로 확장 ON의 Python 파리티나 재학습 완료를 주장하지 않는다. 장식 HISM은 NoCollision이고 늑대 제한은 서버 Native 규칙이 수행한다.

## 4. 에디터에서 무엇을 확인하는가

원래 프로젝트를 열고 `JYU/Maps/LV_JYU_RefugeSafety`를 연다. Outliner의 `JYU_ProtectedRefuge_Forest_0`를 찾아 F로 이동하면 테스트 은신처를 볼 수 있다. Forest/Barren/Highland 각 4곳이다. 레벨 담당자가 최종 은신처를 제작할 예정이므로 현재 배치는 **테스트 은신처**라고 부른다. 원본 팀 레벨과 기존 통합 맵은 보존한다.

일반 PIE에서 실제 사슴을 Tab/가운데 버튼으로 선택하고 `request`, `executed`, `native_threat_count`, `social_state`, `alarm_strength`, `shelter_state`, `refuge_protected_here`, `hide_arrived`를 비교한다. R로 JSONL 기록한다. 사슴이 앉았다는 화면만으로 미감지/버그/안전을 단정하지 말고 직접 감지, 사냥 중인 늑대인지, 공유 경보, 실제 보호 영역·점유 여부를 함께 본다. 필요 시 `eco.Shelter.Log 1`, `eco.Social.ActionAudit 1`을 사용한다.

IK 비교 도구의 `IK ON/OFF`, `NO AI` 사슴은 **임시 표현 Actor**이며 늑대 반응 확인 대상이 아니다. 일반 Play를 다시 시작해 실제 생태계 개체를 확인한다. `Tools/Editor/run_jyu_ik_visual.py`는 촬영 뒤 PIE와 에디터까지 종료하는 자동 runner다. 과거 D3D12에서 device hung/LiveKernelEvent 141이 있어 화면 검증은 D3D11로 진행했으며 기본 렌더링 설정을 바꾼 것은 아니다.

## 5. 마지막 검증과 근거의 범위

아래 목록은 **2026-10-16 구현 당시 개별 조건·기록**이다. 최신 10월 22일 재검증은 위 PR 인계와 [main 병합 기록](JYU_MAIN_MERGE_20261022.md)을 따른다. 서로 다른 실행의 수치와 조건을 합쳐 설명하지 않는다.

- 보호 은신처 최종 직접 UBT Build06 성공. 전체 자동화 **147개: Success 146, 예상 warning 1, 실패 0**. warning은 기존 missing-save fixture다.
- 일반 PIE 40초에서 은신처 12/12 준비, 보호·점유·웅크림 관찰. 300 Native steps의 세 지역 내부 늑대·내부 포획 위반 0.
- Dedicated 110초 + 같은 서버에 Client A/B 순차 접속, 각 프로세스 정상 종료. 두 Client 은신처 ready/visible 12, 논리 개체·Native step 0, 수신 표현 존재. 서버 750 Native steps의 내부 늑대·내부 포획 위반 0.
- 일반 PIE/네트워크 화면·수치는 Build05 실행 근거이고 최종 Build06의 이동 중 은신처 제거 처리는 자동화 회귀로 추가 검증했다. 둘을 같은 실행으로 합쳐 설명하지 않는다.
- IK는 평지·4°/8°/12°와 이동·숨기·수면·감각 반응을 검증했다. 모든 급경사·LOD·원본 클립의 무결함이나 발 잠금을 보장하지 않는다.

체크인 근거는 각 문서와 `Evidence/JYU_V3/`에 있다. 로컬 raw 로그·관찰 결과는 `Saved/RefugeSafety_20261016/`, `Saved/SocialV3_20261016/` 등에 있으며 Git 제외라 다른 체크아웃에는 없을 수 있다. 재현 도구는 `Tools/Editor/run_jyu_refuge_audit.py`, `test_jyu_refuge_network.ps1`, `run_jyu_threat_audit.py`, `test_jyu_social_network.ps1`이다. 실행 전 스크립트의 인자·종료 동작부터 읽는다.

## 6. 남은 작업과 구현 시 주의점

**새 기능 작업은 아직 지정되지 않았다.** 다음 채팅에서는 사용자가 요청한 범위를 확인한 뒤 진행한다. 이미 연결한 Social/IK를 다시 미구현으로 취급하지 않는다.

1. 레벨 담당자의 최종 은신처를 도입할 때 외형과 보호 반경·지면 슬롯·실제 도착 계약을 함께 검증한다. 원본 팀 레벨 대신 복사 맵/owned 에셋에서 작업하고 기존 사용자 변경을 보존한다.
2. 보호 세계의 Python mirror/재학습은 RL 담당과 합의할 후속 과제다. 기존 OFF Golden 기준을 보존한다.
3. migration/wave 활성화, 외부 MassFlock 설치, NavMesh/ORCA 전환, Merge/Split·multi-hop gossip·자동 Cover 생성은 완료 범위가 아니다. 곧바로 필수 구현으로 확대하지 않는다.
4. 대규모·장시간·지연 환경 회귀와 더 다양한 지형/표면·IK 개선은 후속 후보다. 현재 검증 범위를 넘어 보장하지 않는다. 과거 테스트 시 Python 학습 의존성이 없었다는 기록은 현재 설치 상태와 재확인이 필요하다.

Source 진입점은 `AI/Policy/Eco*V3*`, `AI/Social/EcoPolicyV3SocialBridge.*`, `AI/Social/`, `Creature/Representation/EcoGroundFeetNode.*`, `AI/Social/Shelter/EcoRefugeHabitat.*`를 `Source/AdaptiveEcosystem/` 아래에서 검색한다. AnimGraph authoring은 별도 `AdaptiveEcosystemEditor` Editor 모듈에 있고 runtime 책임은 기존 모듈에 남아 있다.

## 7. 발표자료와 디스크 정리

개인 발표자료는 저장소 밖 **`C:/Users/I/Desktop/AdaptiveEcosystem_발표자료/`**에 날짜·용도별로 보관한다. 최신 발표는 `2026-10-16/겜캡디_조연우_1016_수정본.pptx`다. 발표 대본·PDF·제작 스크립트·렌더·임시 작업 폴더도 외부에 둔다. `Deliverables/`, `output/`, `tmp/`는 제외 규칙으로 보호돼 있다. 공유 설계 자료인 `Docs/Roadmap/M3/Presentation`은 분리 대상이 아니다. 사용자 요청 없이 발표자료를 push하거나 공개 이력을 다시 쓰지 않는다.

발표는 교수님이 시스템 개요를 알고 있다는 전제로, **이번에 무엇을 구현했는지 두괄식으로 쉽게 설명**한다. 자연스러운 표현을 쓰고 “팀 코드” 대신 실제 연결 내용을 설명한다. 은신처는 “테스트 은신처”로 부르고 애니메이션 작업도 포함한다.

직전 캐시 정리는 파일 크기 기준 **6,293,910,965 bytes / 33,747개**를 삭제했고 측정 시 C드라이브 여유가 약 3.23GB 증가했다. 빌드 중간 파일, VS 검색 인덱스, 프로젝트/공용 파일 방식 DDC, 오래된 로그가 대상이었다. 에셋·소스·DLL·백업·검증 근거·Git/LFS·발표자료는 보존했다. 공용 Zen 저장소와 성능 기록도 남겼다. 로컬 내역은 `Saved/CleanupReports/20261016/summary.json`이다. 현재 여유 공간이나 현재 캐시 크기로 인용하지 않는다. 다음 빌드·IDE 실행 시 캐시가 재생성될 수 있다.

## 8. 재개 절차와 새 채팅에 붙일 문장

1. 루트 AGENTS와 이 문서, 작업 대상의 최신 계약을 읽고 `git status`, branch/HEAD, 실행 프로세스를 확인한다.
2. 필요한 Source·에셋·팀 브랜치 차이를 확인하고 현재 변경을 보존한다. 새 원격 최신을 확인하지 않고 반영 완료라고 말하지 않는다.
3. C++/빌드 입력 변경 시 직접 `UnrealBuildTool.exe`로 `AdaptiveEcosystemEditor Win64 Development` 빌드하고 완료까지 기다린다. UBT/dotnet/Editor/Live Coding/MSBuild/ShaderCompileWorker가 실행 중이면 중단하거나 새 빌드를 시작하지 않는다. 외부 엔진 캐시 쓰기 권한을 시작 전에 확보한다. 과거 사용자의 특정 실패 실행 중단 허용은 지속적인 예외가 아니다.
4. dotnet 예외 창은 첫 UBT/compiler 오류와 Windows Application Event Log부터 확인한다. 추측으로 경로나 캐시를 삭제하지 않는다.
5. 동작 변경은 적절한 자동화와 실제 에디터 화면/PIE, 필요 시 Dedicated/Client까지 검증한다. 문서만 바꾸면 링크·근거·diff를 확인하며 새 빌드/PIE를 했다고 적지 않는다.

새 채팅에 붙일 문장:

> 나는 조연우야. 루트 AGENTS.md와 AdaptiveEcosystem/Docs/조연우/JYU_CHAT_HANDOFF_20261022.md, JYU_MAIN_MERGE_20261022.md를 읽고 PR #14의 현재 상태부터 확인해줘. main 병합·날씨 호환 복구와 기존 Social·M4/v3·IK·테스트 은신처 연결을 보존해줘. 원본 팀 레벨은 건드리지 말고, 개인 발표자료는 바탕화면 외부 폴더에 둬. 이후 작업은 내가 이어서 지정할게.
