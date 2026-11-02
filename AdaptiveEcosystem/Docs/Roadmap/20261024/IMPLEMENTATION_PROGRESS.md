# JWJ 멀티플레이 구현 진행 — 2026-10-24

작업 시작 Source: `jwj-1024 / a7eb12d`. 이전 명세 기준 `8836558` 이후 soil/life·자연 출생·성장·무리 이주·공간 자원 조정 구현이 추가됐다. 오래된 T07~T09의 미구현 설명을 그대로 재개발하지 않는다.

## 2026-11-02 사용자 결정: 세션 접속 후속 작업 보류

사용자 요청에 따라 **멀티플레이 세션 접속의 추가 구현·수정·실환경 검증은 현재 상태에서 멈추고 추후 재개한다.** 기존 세션 코드·UI·설정·JWJ 맵·시험 도구는 현재 작업 결과로 보존한다. 보류는 기능 제거 또는 런타임 비활성화를 뜻하지 않으며, 이번 문서 갱신으로 기본 설정을 변경하지 않는다.

현재 확인된 경계는 로컬 NULL/IP의 Host 1 + Client 10 접속·재참가·연결 종료 복구와 실제 Steam Host 생성이다. 동일 계정 두 프로세스의 Steam 검색 실패는 미해결이며, 서로 다른 계정·PC의 검색/참가 및 Steam Host 1 + Client 10 시험은 미완료로 남긴다. 세션 접속 전체를 완료로 선언하지 않는다.

재개 요청 시 같은 패키지의 서로 다른 Steam 계정·PC 2대로 검색→참가부터 확인한 뒤 11명 시험으로 확장한다. 아래 검증 수치는 **2026-10-24 실행 이력**이며, 2026-11-02에는 문서·Source·diff·기존 로그를 확인했으며 새 UBT/PIE/접속 시험은 실행하지 않았다.

## 사용자 결정

- F01 확정: 기존 `/Game/JWJ/Integration_JwJ`를 직접 수정해 사용한다. 복사 맵 권고보다 이 사용자 지시가 우선한다.
- F02 범위 지시: 원준 담당인 공통 서버·네트워킹을 구현한다. V1은 기존 PPO 가중치 출력, v3는 팀의 행동 선택 Native 경로, SpeciesAI는 별도 StateTree 경로다. backend 변경·새 학습·타 담당 gameplay 확장은 이번 세션 업무에 넣지 않는다. JWJ의 실제 기존 구성을 보존한다.
- F04 확정: Steam Session 생성·검색·참가·종료, 원격 Client 10명. Listen Host 1명을 더해 총 11명이다.
- F05 보류: 목표 하드웨어·FPS·지연·생태계 규모 성능 수치는 나중에 결정한다. 접속·권위·수명 정합성 검증은 진행한다.
- 나머지 미확정 gameplay 선택은 기존 기본값을 유지한다.

## 이번 구현 범위

| 영역 | 구현/검증 대상 |
|---|---|
| T01 | JWJ 실행 설정·canonical template 보존·session/권위 진단 |
| T02/T04 | 기존 BodyScale 포함 payload·수신/보간/풀 보존, 접속 회귀 |
| T03 | 동시 10 Client·재접속·버전/정원 초과 거부 |
| T05/T06 | 기존 환경/장애물 보존; 새로운 규칙·Snow schema·벌목 기능은 활성화하지 않음 |
| T07~T09 | 현재 통합된 공통 생명주기/장부 재사용, v3/life 옵션 변경 없음 |
| T10 | 기존 플레이어 컴포넌트/요청 보존, 원격 소유 경계 확인 |
| T11 | Steam lobby API·소규모 방 UI·정원·실행 도구·설정 인계 |

## 구현

UGameInstanceSubsystem은 로컬 Session API와 UI 수명만 관리한다. Subsystem replication은 추가하지 않는다. Steam lobby 생성은 presence/lobby를 함께 켜고 프로젝트 tag·protocol·map으로 결과를 검사한다. 오래된 검색 결과의 참가를 막는다.

기존 Mass Bubble/GameState·Client 프록시를 재사용한다. 정원은 Steam public slots와 서버 GameSession에서 함께 제한한다. 게임 세션은 Host 포함 11명, Dedicated 시험은 10명이다. 실제 접속 완료와 Mass Ready를 별도로 표시한다.

기본 UI는 기존 PlayerController·HUD Blueprint 변경 없이 사용할 수 있는 Native Widget이다. F10으로 방 이름·목록·생성·참가·나가기를 제공한다. 정책/생태 계산을 UI에 넣지 않는다.

## 실제 JWJ 구성

| 항목 | 저장한 구성 |
|---|---|
| 원본 맵 | `/Game/JWJ/Integration_JwJ` 직접 수정 |
| GameMode | 새 `JWJ/Multiplayer/BP_JWJ_MultiplayerGameMode`, 기존 Creature GameMode 상속 |
| 플레이어/HUD | 기존 GameMode의 Pawn·Controller·HUD·Spectator class 보존 |
| 입장 서비스 | `AEcoGameSession`, Listen 11명·Dedicated 10명 |
| 시작 위치 | 기존 1개 보존 + 지면 검증한 10개, 총 11개 |
| 종별 Config | 기존 `DA_EcoDeer`·`DA_EcoWolf` 보존 |
| 지역/개체 | Forest 8+1, Barren 8+1, Highland 8+0: 사슴 24·늑대 2 |
| 실행 옵션 | UseV3Policy=false, Waves=false, EcosystemLife=false, HabitatStreaming=true 보존 |
| 기존 설정 보완 | Barren/Highland의 사슴 생성 위치가 4개씩 부족했다. 기존 위치·개체 수를 유지하고 각 4개를 실제 지면에 추가 |

전용 Blueprint와 10개 PlayerStart 외부 패키지는 JWJ 경로에만 생성한다. 기존 정책·모델·동물 에셋은 수정하지 않는다. 원본 `.umap` 백업은 `Saved/Network20261024/BeforeJWJMultiplayer`에 있다. World Partition 저장 결과에는 coordinator 외부 패키지 변경도 포함된다.

`Tools/Editor/configure_jwj_multiplayer.py`는 기본 감사 모드이며 `-EcoJWJApply`일 때만 저장한다. 편집 helper는 Editor 모듈 안에 있고 정확히 이 JWJ 맵의 지면만 로드한다. 재실행 시 소유 태그가 있는 PlayerStart를 중복 생성하지 않는다.

### 실제 처리 소유권

- 판단·이동·생존: 기존 JWJ V1 Creature 구성과 공통 adapter. v3/SpeciesAI로 전환하지 않았다.
- 자원·인구·고유 ID: 기존 권위 Ecology/Mass 경계.
- 전송: 기존 GameState 완료 요약과 Mass Bubble.
- Client: 수신 프록시·표현·보간. 정책·자원·생존을 새로 실행하지 않는다.
- Session Subsystem: 방 API·메뉴·연결 수명만 담당한다.

ClientTravel 도중 이전 Standalone World에 pending net driver가 먼저 붙는 엔진 순서를 확인했다. 이 구간에서 coordinator 갱신을 멈추고, 종료 정리는 현재 NetMode 대신 BeginPlay 당시의 권위 소유 여부로 결정한다. 새 Client 월드의 권위 fragment 검사는 유지한다.

## 검증 기록

- 직접 UBT Build01: const·헤더 경로·클래스 멤버 이름 충돌로 실패. 최초 compiler 오류를 확인하고 수정했다.
- 직접 UBT Build02: `AdaptiveEcosystemEditor Win64 Development` 성공.
- 직접 UBT Build03~07: Editor 빌드 성공. 메뉴 생성 시점, LAN provider/driver 혼용, 검색 BuildUniqueId, 월드 전환 수명을 실제 시험 결과에 맞게 보완했다.
- 자동화 1개: `AdaptiveEcosystem.Network.Session.CapacityAndCompatibility` 성공. 후속 전체 회귀 결과는 실행 후 기록한다.
- 첫 JWJ 실행은 부족한 spawn point로 실패했고 맵 설정을 보완했다. 다음 LAN 검색 시험은 고정 BuildUniqueId 때문에 결과를 받지 못해 엔진 build ID를 유지하도록 수정했다. 이 실패 로그도 보존한다.
- 최종 로컬 Smoke `Smoke-20261024-191158`: 생성·검색·참가, 명시적 LeaveSession, 같은 프로세스 재참가, 새 프로세스 재참가 성공. 모든 프로세스 ExitCode=0, runtime 중단/충돌 없음.
- 동시 접속 `Capacity-20261024-191434`: Listen Host 1 + 원격 Client 10 성공. Players=11/Capacity=11/Ready=1이 28개 표본·136.3초 구간에서 관측됐다. 추가 원격 Client는 `Server full.`, protocol=0은 `ECO_INCOMPATIBLE_PROTOCOL`로 거부됐다. Host·10 Client·거부 시험 2개 모두 정상 종료했다.
- Client 10개 각각 40개 진단 표본에서 Client 논리 owned/정책 step=0. 표현 수신 존재. Active+Pool 최대는 Client01=13, 나머지=12였고 설정 ActorBudget=64 위반은 0이었다. `CapacitySummary.json`에 집계했다.
- 전체 자동화 `Regression`: **226개, 225 Success + 1 경고 포함 Success, 실패/미실행 0**. 경고는 기존 missing-save 검사의 `EcoPredEmaTest_None.sav` 부재다. Steam 비활성화/기존 foliage MapCheck 메시지는 별도 시작 로그다.
- 위 접속 시험은 **NULL/IP loopback**, NullRHI·10FPS 시험 pacing·관찰 Pawn 순환 fixture다. 실제 Steam 서비스·WAN·11개 기기 렌더링 성능을 검증한 것으로 해석하지 않는다.
- 직접 UBT Build08: Editor 성공. 이후 변경은 메뉴 대비/레이아웃·같은 이름의 방 구분·provider 정리 중 중복 실패 처리 보호다.
- `Menu02.log` / `Menu_Verified.png`: D3D11 1280×720 실제 렌더링에서 메뉴·한글·상태·입력칸 표시를 확인했다. 첫 `Menu.log`는 첫 그래픽 캐시 생성으로 도구의 180초 대기를 넘었으나 엔진을 중단하지 않았고 이후 자체 타이머로 정상 종료했다. 최초 캡처의 문구 겹침·낮은 대비를 수정했다.
- `SteamHost.log`: **실제 STEAM provider/App ID 480**으로 생성→시작→`SteamSocketsNetDriver_0 started listening on 7789`→Ready=1→정상 종료 성공. 이는 한 계정의 Host 시험이며 원격 Steam 10명 참가 통과를 뜻하지 않는다.
- `SteamDiscoveryHost.log` / `SteamDiscoverySearch.log`: 동일 Steam 계정의 두 프로세스로 추가 검색을 시도했다. 서비스가 후보 1개를 돌려줬으나 OSS의 lobby data 수신이 약 15초 뒤 실패했고 앱은 Error를 표시했다. **Steam 브라우저 검색은 이 실행에서 실패, Steam 참가·10계정 동시는 미실행**이다. 프로세스 ExitCode=0을 기능 성공으로 기록하지 않는다. 설치된 UE5.8 OSS는 이미 가입한 lobby의 matchmaking을 지원하지 않는다고 명시하고 있으나, 이 실행의 원인을 같은 계정 때문이라고 확정하지 않는다. 서로 다른 계정·기기에서 같은 패키지로 우선 재현해야 한다. 엔진 metadata/timeout 검사를 우회하지 않았다.
- `Disconnect-20261024-193448`: Host 종료 후 Client ConnectionLost→세션 정리→새 Standalone epoch/Ready=1 복원 성공. 두 프로세스 정상 종료. 원인에 해당하는 예상 `LogNet Error: ConnectionLost`는 충돌로 분류하지 않는다.
- 직접 `AdaptiveEcosystem Win64 Development` Game UBT 성공. 이후 cook/stage/archive와 패키지 실행 결과는 완료 후 기록한다.
- 최초 `Package.log`: **cook/stage/pak/archive 성공**, 794개 에셋 처리, UAT ExitCode=0. 최초 그래픽 캐시와 분산 작업의 로컬 fallback으로 약 35분 22초가 걸렸다. 이를 게임 프레임 성능으로 해석하지 않는다.
- 최종 `Build09.log` / `GameBuild09.log`: Editor와 Game 직접 UBT 성공. 자동 메뉴를 JWJ로 한정하고 검색 revision·누적 travel 경과 진단과 정원 안내를 정리했다. 정책·wire schema·에셋 변경은 없어 기존 cooked 에셋을 재사용한 `Package09.log` stage/pak/archive도 성공했다.
- 최종 `Regression09`: **226개, 225 Success + 1 예상 경고 포함 Success, 실패/미실행 0**. 후속 cook의 로컬 worker 옵션도 `r.ShaderCompiler.AllowDistributedCompilation=0, LastSetBy=SystemSettingsIni`로 적용됨을 확인했다. 현재 프로젝트의 런타임 INI 값으로 저장한 변경은 아니다.
- `PackageSmoke-20261024-202029`: **최종 Win64 Development 패키지**에서 LAN 생성→검색→참가→명시적 나가기→같은 프로세스 재참가→다른 프로세스 참가 성공. Client 논리 owned/step=0·표현 수신·Ready=1, 모든 프로세스 정상 종료.
- `PackageMenu.log` / `Package_Menu_Verified.png`: 최종 패키지의 실제 D3D11 렌더링에서 JWJ 자동 메뉴·한글·정원·Ready 표시 확인, 정상 종료. 화면 상단의 기존 생태 디버그 겹침은 기존 레벨 진단이며 접속 메뉴와 분리돼 있다.
- `PackageSteamHost.log`: 최종 패키지에서도 **실제 Steam 생성→SteamSockets Listen→Ready=1→정상 종료** 성공. Steam 검색/참가의 다중 계정 검증 공백은 위 기록대로 남아 있다.
- `FinalMapAudit.log` / `JWJAudit.json`: 저장 없는 최종 asset 감사 성공. 전용 GameMode·PlayerStart 11개·지역별 사슴 위치 8개씩, 기존 `EcoCreatureNetworkTrait` 두 종 모두 `bUseSpeciesAI=false`·`bUseV3Policy=false`를 확인했다. 따라서 이번 JWJ의 V1 구성 설명은 맵 bool만의 추정이 아니라 실제 Config trait와 함께 확인한 사실이다.

### 최종 산출물과 남은 검증

실행 파일: `Saved/JWJMultiplayerPackage/Windows/AdaptiveEcosystem.exe`. `Windows` 폴더 전체가 실행 자료다. 내부 exe 한 개만 복사하지 않는다. 개발용 Steam ID는 480이다.

이번 결과는 네트워크·세션 1차 구현이며 11개 최초 명세 전체 완료 선언이 아니다. T05의 Snow/World 연출, T06 동적 나무, T10의 보행 캐릭터/위협 선택 등 추가 gameplay 결정은 별도다. T07~T09의 기존 통합 코드를 다시 구현하거나 JWJ의 v3/life를 켜지 않았다. F05 성능 목표는 보류한다.

추후 세션 접속 작업 재개 시 필요한 실환경 시험은 다른 Steam 계정으로 검색→참가가 성공하는지 먼저 확인하고, 같은 패키지로 Host 1 + Client 10을 검증하는 것이다. 이 후속 작업은 2026-11-02 사용자 요청으로 보류했다. 현재 PC 한 계정의 실패를 통과로 바꾸거나 원인을 확정하지 않았다.

실행 로그와 원시 결과는 `AdaptiveEcosystem/Saved/Network20261024/`에 저장한다. 새 실행이 없는 기존 225개 테스트/멀티 결과를 이번 통과로 옮기지 않는다.

## 관련

- [전체 명세](README.md), [확인 항목](99_DECISIONS_AND_CONFIRMATIONS.md)
- [실행·설정 인계](MULTIPLAYER_SETUP.md)
- [현재 서버 인수인계](../../Network/ECOSYSTEM_SERVER_NETWORK_AGENT_GUIDE_20261024.md)
