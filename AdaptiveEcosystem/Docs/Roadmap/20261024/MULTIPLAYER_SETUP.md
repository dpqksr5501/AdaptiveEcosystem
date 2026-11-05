# JWJ Steam 멀티플레이 실행·설정

대상 맵: `/Game/JWJ/Integration_JwJ`. 목표: Listen Host 1명 + 원격 Client 10명.

## 현재 상태 — 2026-11-02 보류

사용자 요청으로 **멀티플레이 세션 접속의 후속 구현·수정·실환경 검증을 여기서 멈추고 추후 재개한다.** 기존 코드·메뉴·설정·맵·실행 도구는 보존하며 런타임 기본값은 바꾸지 않는다. 아래 실행 순서는 재개 시 참고할 인계 자료다.

로컬 NULL/IP 접속과 실제 Steam Host 생성은 2026-10-24 검증 이력이다. 동일 계정 두 프로세스의 Steam 검색 실패는 미해결이며, 다른 계정·PC의 검색/참가와 Steam 11명 동시는 미검증이다. 재개 시 서로 다른 계정·PC 2대로 검색→참가부터 확인한다. 이번 보류 기록을 새 실행 성공이나 세션 접속 전체 완료로 해석하지 않는다.

## 게임에서 쓰는 순서

1. 모든 PC가 같은 게임 빌드/Content를 사용한다.
2. Steam을 실행하고 각각 다른 Steam 계정으로 로그인한다.
3. 패키지 또는 Editor의 별도 Standalone Game을 실행하고 F10으로 접속 메뉴를 연다. Steam 최종 시험은 여러 PC의 동일한 패키지에서 진행한다.
4. Host가 방 이름을 적고 **방 만들기**를 선택한다. JWJ 레벨을 Listen으로 연다.
5. 참가자는 **방 검색** 후 목록에서 방을 골라 **선택한 방 참가**를 누른다.
6. **방 나가기**는 연결을 정리하고 JWJ의 단독 실행으로 돌아온다. Host가 나가면 참가자 연결도 종료한다.

로컬 메뉴는 게임을 정지시키지 않는다. '서버에 접속'과 '생태계 준비 완료'는 다른 상태다. 최종 준비 여부는 공통 GameState의 Ready를 표시한다.

시작 시 자동 메뉴는 지정한 JWJ 맵에만 표시한다. 다른 팀 맵에서 메뉴가 자동으로 입력을 가로채지 않는다. F10의 수동 메뉴와 Blueprint API는 사용할 수 있다.

## 이미 연결한 프로젝트 설정

| 위치 | 값·의미 |
|---|---|
| DefaultEngine.ini | Steam 기본 provider, SteamSockets driver + IP fallback |
| DefaultGame.ini / EcoSessionSettings | MaxRemoteClients=10, GameplayMap=JWJ, DiscoveryTag=AdaptiveEcosystem.JWJ |
| Steam public slots | Host 포함 11 |
| EcoGameSession | 실제 서버 입장 제한·session protocol 검사 |
| 프로젝트 plugins | OnlineSubsystemSteam·Null·SteamSockets |
| 패키지 맵 목록 | JWJ Integration_JwJ 포함 |

Steam의 기본 App ID는 **개발 시험용 480**이다. 제품의 실제 App ID가 정해지면 SteamDevAppId·배포 환경을 함께 바꿔야 한다. 프로젝트 tag는 480을 공유하는 다른 게임을 목록에서 제외하기 위한 것이며 인증을 대체하지 않는다.

## 사용자·팀에서 준비할 설정

| 설정·준비 | 현재 처리 | 필요한 결정/행동 |
|---|---|---|
| 실제 Steam App ID·테스트 접근권 | 개발값 480 | 실제 App ID가 있으면 제공, 빌드/계정 접근 확인 |
| Steam 동시 시험 환경 | Host 생성/SteamSockets Listen은 실제 성공. 동일 계정 2프로세스 검색은 후보 1개 후 metadata timeout | 먼저 다른 계정·PC 2개로 검색/참가 확인, 이후 Host+Client 10명용 총 11계정·기기 준비 |
| 배포 빌드 | Win64 Development 패키지 생성·LAN 재접속·Steam Host 실제 성공 | 동일 패키지를 각 참가자에게 전달해 Steam 검색/참가 시험 |
| 방 이름·검색 tag | 기본값 제공 | 방 이름은 UI에서 변경, 팀 전용 tag는 Config |
| 공식 레벨 | 기존 JWJ 직접 사용 | 추가 레벨 복사 필요 없음 |
| 생태계 backend | 기존 JWJ 설정 보존 | 이번 세션 기능을 위해 v3/life를 켤 필요 없음 |
| 성능 목표 | F05 보류 | 장비·FPS·허용 지연·총 개체 수는 후속 결정 |

코드·로컬 다중 접속 결과와 실제 Steam 계정 10명 접속 결과는 구분해 기록한다. 로컬 시험을 Steam 서비스 성공으로 설명하지 않는다.

F02의 세 용어는 동물의 행동을 결정하는 방식이다. **V1**은 기존 7개 관측→4개 행동 가중치 PPO 경로, **v3**는 별도 18개 관측→5개 행동 계약의 Native 경로, **SpeciesAI**는 규칙·StateTree 경로다. 이번 JWJ는 기존 V1 구성을 유지한다. Steam 방과 서버 입장 계층은 이 선택과 분리돼 있어, 네트워크 개발을 위해 다른 담당자의 정책을 선택하거나 다시 구현할 필요가 없다.

## 개발·로컬 시험

로컬망 시험은 Steam 대신 Null provider를 사용한다. 시험 프로세스에 `-nosteam`을 사용하고 메뉴의 로컬망 시험을 체크한다. Steam이 활성인 상태에서 LAN만 선택하면 driver와 provider가 섞이므로 재실행 안내와 함께 거부한다. Steam 없이 동작하는 LAN 시험은 실제 Steam 인증/초대/인터넷 릴레이의 증거가 아니다.

콘솔 API:

```text
eco.Session.Host <방이름> [lan]
eco.Session.Find [lan]
eco.Session.Join <목록번호> <검색판번호>
eco.Session.Leave
eco.Session.Menu
eco.Session.Dump
```

콘솔 Join의 결과 번호는 **0부터** 시작한다(UI의 1번 방은 index=0). `eco.Session.Dump`가 기록하는 SearchRevision을 함께 전달한다. `SinceTravelStartSeconds`는 마지막 travel 요청 이후 누적 경과이며 접속 완료 지연 측정값이 아니다.

CLI 자동 흐름은 `-EcoSessionAutoHost -EcoSessionLAN`, `-EcoSessionAutoFind -EcoSessionAutoJoin -EcoSessionLAN`으로 제공한다. UI가 필요 없는 시험은 `-EcoSessionNoUI`를 사용한다.

재현 도구는 저장소 루트에서 다음과 같이 실행한다. 실행 중인 Editor/빌드가 있으면 도구가 시작을 거부한다. 기존 프로세스를 종료하지 않는다.

```powershell
./AdaptiveEcosystem/Tools/Editor/test_jwj_multiplayer.ps1 -Scenario Smoke
./AdaptiveEcosystem/Tools/Editor/test_jwj_multiplayer.ps1 -Scenario Capacity
./AdaptiveEcosystem/Tools/Editor/test_jwj_multiplayer.ps1 -Scenario Disconnect
./AdaptiveEcosystem/Tools/Editor/package_jwj_multiplayer.ps1
./AdaptiveEcosystem/Tools/Editor/test_jwj_multiplayer.ps1 -Scenario Smoke -Packaged
```

Smoke는 실제 LAN 생성·검색·참가·명시적 나가기·같은 프로세스 재접속과 새 프로세스 재참가를 확인한다. Capacity는 Host+Client 10개를 동시에 실행하고 추가 참가/잘못된 protocol 거부를 확인한다. 모든 게임 프로세스는 개발용 자체 종료 타이머를 사용한다. 관심 범위 수신을 재현하기 위해 기존 observer-cycle 시험 옵션으로 서버가 관찰 Pawn 위치를 순환시키므로 일반 플레이 성능 시험으로 해석하지 않는다. 가용 메모리를 확인한 뒤 실행한다.

Disconnect는 Host 정상 종료 후 Client의 ConnectionLost 처리·세션 정리·새 JWJ 단독 월드와 Ready 복원을 확인한다. 이때 예상된 연결 종료 메시지는 runtime 충돌과 구분한다.

원시 결과는 `Saved/Network20261024/Smoke-*`, `Capacity-*`의 로그와 `Results.json`이다. `-EcoSessionAudit`은 개발 빌드에서 5초마다 연결 수·정원·epoch·Ready를 기록한다. `-EcoSessionLeaveAfter=7 -EcoSessionAutoRejoin`은 개발용 1회 나가기/재검색 fixture이며 제품의 자동 재접속 정책이 아니다.

패키지 도구는 직접 Game UBT를 완료한 뒤 JWJ 맵만 cook/stage/archive하고 `Saved/JWJMultiplayerPackage/Windows`에 Development 패키지를 만든다. 설정된 개발 App ID를 실제 게임 실행 파일 옆 `steam_appid.txt`에 기록한다. 이 파일은 개발용이며 실제 Steam 배포 설정과 다르다. 패키지 도구의 존재가 cook/실행 성공을 뜻하지 않으므로 [실제 결과](IMPLEMENTATION_PROGRESS.md)를 확인한다.

**현재 패키지는 생성·실행 검증을 마쳤다.** `Saved/JWJMultiplayerPackage/Windows/AdaptiveEcosystem.exe`로 실행하며 다른 PC에는 `Windows` 폴더 전체를 전달한다. 내부 실행 파일 하나만 전달하면 Content·엔진·Steam DLL이 빠진다. Unreal은 개발 실행 종료 시 `steam_appid.txt`를 정리할 수 있으며 개발 App ID의 원본은 `DefaultEngine.ini`다.

패키지 도구의 후속 실행은 로컬 ShaderCompileWorker 사용을 기본으로 한다. 현재 PC의 분산 컴파일 실패→인프로세스 재계산 지연을 피하기 위한 **cook 프로세스 옵션**이며 게임 그래픽 품질·정책·런타임 설정을 바꾸지 않는다. 분산 컴파일 환경이 준비된 PC에서는 `-LocalShaderWorkers:$false`로 끌 수 있다. 최초 진행 중 cook은 원래 명령으로 끝까지 실행하며 이 후속 도구 옵션이 소급 적용됐다고 기록하지 않는다.

## 이번 범위 밖의 후속 선택

현재 JWJ의 기존 Pawn·Controller·HUD와 행동 구성을 보존했다. 관찰자를 실제 보행 캐릭터로 바꾸고 gait·서버 발소리까지 검증하는 T10/F16, 눈 공통 schema와 날씨 연출 T05/F07, 동적 나무 T06/F09는 별도 gameplay·World 선택이다. 이번 방 기능의 필수 설정으로 요구하지 않는다. 기존 출생/life·이주 코드를 다시 구현하거나 JWJ에서 자동 활성화하지 않았다. 성능 목표 F05도 요청대로 보류한다.

## 실패·수명

- 잘못된 프로젝트/map/protocol의 방은 참가를 거부한다.
- 정원 초과는 lobby뿐 아니라 서버에서도 거부한다.
- 생성·검색·참가·시작·종료의 delegate를 정리하며 겹치는 요청을 막는다.
- 검색 timeout은 취소 요청을 보낸다. 생성/참가처럼 provider의 취소 API가 없는 요청은 늦은 응답을 정리할 때까지 새 요청을 겹치지 않는다.
- Host Migration·운영 Dedicated 배포·상이한 빌드 간 save 복원은 이번 Session 기능의 범위가 아니다.

Steam 구성 근거: [Epic Steam OSS](https://dev.epicgames.com/documentation/en-us/unreal-engine/online-subsystem-steam-interface-in-unreal-engine), 설치된 UE5.8 SteamSockets/OnlineSubsystem API Source. 실제 실행 결과는 [진행 기록](IMPLEMENTATION_PROGRESS.md)에 남긴다.
