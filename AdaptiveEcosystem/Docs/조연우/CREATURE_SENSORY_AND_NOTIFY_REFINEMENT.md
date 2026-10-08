# 늑대 감각·발 접촉 Notify·지형 표면 연결

2026-10-08, `codex/social-shelter-handoff`의 `edba605` 이후 작업 트리. [이전 발소리 연결](CREATURE_FOOTSTEPS_AND_SENSE_DEBUG.md)을 고도화한 현재 계약이다. 적용 레벨은 `/Game/Map/LV_Ecosystem_IntegrationTest`; 기존 M3/JYU 전체 전환과 구분한다. 후각은 제외한다.

## 현재 데이터 흐름과 담당 경계

| 입력 | 소비자 | 결과/권위 |
|---|---|---|
| 사슴의 PPO Raw Action | 기존 Social, 단일 Steering/Movement | 기존 관측 7개·행동 4개·가중치 유지 |
| 사슴의 위협 Sight/Hearing/Memory | 개인 감각 → Herd Alarm → Social | 기존 경보·은신처 Request/Feedback 경로 |
| 늑대의 먹잇감 Sight/Hearing/Memory | `FEcoPreySenseFragment` → 기존 Predator Movement | 마지막 감지 위치를 기존 writer가 추적; 감각 Processor는 위치를 쓰지 않음 |
| 권위 Mass의 실제 이동 거리 | 논리 발걸음 → `UEcoNoiseSubsystem` | 서버/Standalone만 생성. 사슴 소리는 경보 강도 0이지만 늑대는 먹잇감 단서로 소비 |
| 복제된 표현의 실제 이동 + AnimNotify | 로컬 Footsteps component → SA/SC | 공간 오디오만 재생. Client에서 AI 이벤트를 보고하지 않음 |
| 발 뼈 아래 Visibility trace의 Physical Material | `DA_EcoFootsteps` | 실제 Grass/Dry 우선, 미등록/누락 재질만 기존 Region fallback |

Social은 감각·무리·경보·은신처 의도와 표현 연결을 맡는다. PPO 학습/관측 스키마, 자원·Vitals 소유권, 복제 transport, 실제 위치 적분은 각 기존 계층의 책임이다. 새 소리 RPC나 감각 복제 필드는 추가하지 않았다.

## 늑대의 먹잇감 감각

`UEcoPredatorPerceptionProcessor`는 권위 월드에서 Neighborhood Gather 이후, Predation 이전에 Game Thread로 0.2초마다 스캔한다. opt-in Creature 포식자 구성에만 별도 먹잇감 감각 Fragment를 추가하며 Client proxy에는 추가하지 않는다.

- 살아 있는 식별된 초식동물만 후보. 현재 생성 상수의 늑대 시야 2800cm/FOV 150도를 사용하고 수평 각도·차폐·Visibility LOS를 검사한다. 가까운 후보 우선, 동률은 StableAgentId로 결정한다.
- 사슴의 논리 발소리에는 위협 강도가 0이어도 먹잇감 단서가 있다. 자기 소리 제외, 소비 Noise ID 기록, `min(청각 범위, Noise 최대 범위)`·거리·차폐·최소 신뢰도 적용. Sight를 우선하고 Hearing은 감쇠한 약한 단서를 대체한다.
- 감지 위치는 스냅샷이다. 시야 밖 사슴의 현재 위치를 추적 입력으로 계속 읽지 않는다. 기존 개인 감각 감쇠/유효기간을 재사용하고 읽을 때도 시각을 검증한다. 마지막 위치 도착, 만료, 대상 사망·삭제·Entity handle 재사용 시 잊는다.
- 늑대 먹잇감 기억은 사슴의 위협 기억 및 Herd Alarm과 분리된다. 먹잇감을 무리 경보로 방송하지 않는다.
- opt-in 포식은 최근 0.25초 안의 직접 Sight 대상 일치 및 즉시 LOS를 요구한다. 소리만 듣거나 벽 너머에 가까워졌다는 이유로 포식하지 않는다. 해당 Fragment가 없는 기존 V1/테스트 archetype은 기존 포식 규칙을 유지한다.

환경 multiplier 연결은 기존 Rain/DayPhase 입력을 사용하지만 기본 배율은 1이다. 이 작업에서 임의의 야행성·강우 수치를 새로 정하지 않았다. 관측/가중치 Golden Vector는 통과했지만 **opt-in 포식자 감각·포식 조건은 Python 기본 시뮬레이션과 다른 시나리오**다. 학습 담당은 재학습 전 이 차이를 학습 환경에 반영할지 합의해야 한다.

## 발 접촉 애니메이션

원본 AnimalVarietyPack 애니메이션은 보존한다. `/Game/Creatures/Integrated/FootContacts`에 늑대 6개(Walk/좌우 WalkTurn/Run/좌우 RunTurn), 사슴 4개(Walk/좌우 WalkTurn/Run)를 복사했다. 각 클립에 네 발의 `EcoFootContact` Notify, 총 **40개**를 적용하고 실제 FootBone을 지정했다.

접촉 후보는 120구간의 component-space 발 높이에서 최저 높이 + 진폭 15%로 내려오는 시점을 구했다. 이것은 샘플 기반 접촉 근사이며 모든 지형에서 발 접지가 정확하다는 보장은 아니다. foot IK/경사 자세 보정은 별도 애니메이션 작업이다. 검토 가능한 시각·뼈 데이터는 `Tools/Editor/Data/creature_foot_contacts.json`에 저장했다.

기존 2D Turning BlendSpace는 새 복사본을 소비하고 `HighestWeightedAnimation`으로 Notify를 발생시킨다. 사슴/늑대 BP에 `Use Footstep Notifies`가 저장돼 있다. Idle 원본은 접촉 Notify가 없다.

Native gate는 실제 XY 이동을 관찰하고 최소 이동 크레딧 10cm·최소 속도 40cm/s·접촉 간격 0.07초를 요구한다. 동시에 착지하는 발과 BS 전환의 가까운 중복은 한 소리로 합친다. 정지/막힘/죽음, 최초 bind, 2500cm 초과 snap, 0.5초 초과 hitch, 오래된 입력은 재생하지 않는다. Notify 모드는 거리 기반 로컬 재생을 끄므로 이중 재생하지 않는다. 기존 BP의 기본 거리 모드는 계속 사용 가능하다.

서버 논리 소음은 **여전히 실제 이동 거리 기반**이다. Dedicated에는 Mesh가 없으며 화면에 보이거나 애니메이션이 평가되는지에 따라 AI 감지를 바꾸지 않는다. 로컬 접촉음과 서버 소음 이벤트는 프레임 단위로 동일한 이벤트가 아니다.

## 실제 지형 표면

`/Game/Audio/Footsteps/Surfaces`의 owned `M_EcoLandscapeFootsteps`/`MI_EcoLandscapeFootsteps`는 기존 MWAM master/instance의 복사본이다. 원본의 rock/stones/grass/dirt/snow/water **6개 Physical Material Output 가중치 연결을 그대로 사용**하고 Grass 슬롯만 `PM_EcoGrass`, 나머지는 `PM_EcoDry`로 매핑한다. 시각 shader·파라미터·지형 sculpt는 변경하지 않는다. Grass/Dry 두 종류의 현재 사운드 분류이므로 눈·돌·물 전용 소리를 구현했다는 뜻은 아니다. 실제 물 영역 진입은 기존 이동 guard가 제한한다.

같은 레벨의 Landscape/StreamingProxy에 owned MI를 연결하고 `landscape.RebuildPhysicalMaterial`로 충돌 표면 데이터를 생성·저장했다. 발 뼈 위치 위 100cm에서 아래 300cm까지 complex Visibility trace + ReturnPhysicalMaterial로 표면을 얻는다. SA 3–40m 감쇠/차폐, SC 전역 최대 8개 및 원본 Grass/Dry SoundWave는 기존 설정을 유지한다.

설정 중 Physical Material Output을 추가한 첫 시도는 기존 출력과 충돌했다. owned 복사본의 시험 노드를 제거하고 기존 6개 출력을 재사용하도록 수정했다. 이후 지형 외형과 실제 trace의 `PM_EcoGrass`/`PM_EcoDry`를 PIE에서 확인했다.

## 에디터 확인과 재생성

1. 위 실제 레벨을 열고 Play. 동물 근처에서 발소리를 듣고 `eco.Footsteps.Log 1`의 `Trigger=Notify Material=PM_EcoGrass/PM_EcoDry`를 확인한다.
2. `eco.Senses.DrawFOV 1`: 사슴 초록, 늑대 주황 수평 부채꼴. `eco.Senses.DrawHearing 1`: 청록 수신 구. `eco.Senses.Debug 1`: 감지 위치/신뢰도. `eco.Senses.PreyLog 1`: 늑대 개인 먹잇감 단서(Source 0=None/1=Sight/2=Hearing/3=Memory).
3. `eco.Senses.DrawLimit 2`는 각 감각 Processor의 표시 수 제한이다. 두 Processor 합계 제한은 아니다. Senses는 권위 월드에만 표시되고 로컬 SA 구 `eco.Footsteps.Debug 1`은 Client에서도 가능하다.
4. `eco.Shelter.Log 1`로 Moving→Occupied 및 사망/종료 해제를 본다. 웨이브가 꺼져 있으므로 동물이 줄면 PIE를 재시작한다.

재생성 도구는 UE Python 콘솔에서 `py import runpy; runpy.run_path('프로젝트 절대경로/Tools/Editor/스크립트.py')`로 실행한다.

| 스크립트 | 용도 |
|---|---|
| `audit_creature_contacts.py` → 일반 Python `build_contact_manifest.py` | 새 애니메이션의 발 높이/접촉 후보 산출. Saved 결과를 검토한 뒤 Data manifest에 반영 |
| `configure_creature_contacts.py` | 체크인된 Data manifest로 복사본 Notify·BS·BP 재생성 |
| `configure_creature_locomotion.py` | owned 접촉 클립이 모두 있으면 유지. 부분 구성은 오류로 중단하며 원본/Notify 없는 클립을 조용히 혼합하지 않음 |
| `configure_landscape_footstep_materials.py` | 원본 6개 출력 재사용·owned MI·DA 연결. 이후 physical material rebuild 및 레벨 저장 필요 |
| `audit_creature_refinement.py` | Play 이전 등록. 관찰자만 이동하여 Wolf/Grass/Dry 각 6초 master submix와 로컬 카운터 저장. 마이크 녹음 아님 |

## 검증 기록

- 직접 UBT `AdaptiveEcosystemEditor Win64 Development -WaitMutex -NoUBA` 최종 성공. 두 최초 컴파일 오류(새 테스트 include, 테스트 관찰자 Pawn 반환 타입)는 해당 줄을 수정한 뒤 재빌드했다. 실행 중 빌드를 중단하지 않았다.
- 최종 전체 자동화 **43/43 성공**, 종료 코드 0. 신규 4개는 접촉 이동 gate·Physical Material 우선순위, 늑대 Sight/Hearing/개인 기억·만료·사망, 차폐 및 포식 가드다. 기존 PPO Golden Vector·Movement/Shelter·Facing 검사도 통과했다.
- MCP/Computer Use로 실제 에셋·BP/BS 저장 및 PIE 실행. 늑대·사슴의 Notify 재생, Grass/Dry trace, 모든 샘플의 거리 재생 카운터 0 확인. 엔진 master 출력: Wolf peak 0.1411/RMS 0.00467, Grass 0.1160/0.00403, Dry 0.0564/0.00702(각 약 6초). 소리 시작 로그는 청취 증거와 구분한다.
- 실제 레벨에서 늑대 Source=Sight/Hearing 확인. 벽 차폐·Memory 만료는 자동 테스트로 검증했다. 사슴 은신처 Moving→Occupied 및 DeadOrInvalidHP 반환 로그 확인. 이번 PIE 구간의 Error/Fatal/Processor cycle 로그는 없다.
- 로컬 증거: `Saved/CreatureContactSetup.json`, `LandscapeFootstepSetup.json`, `CreatureRefinementAudit/PIE_PlaybackCounters.json`, 출력 WAV와 `OutputValidation.json`, `Saved/Logs/CreatureRefinementPIE.log`, `CreatureRefinementAutomationFinal.log`. Saved는 Git 제외다.

### 별도 서버·렌더 Client·재접속

`Tools/Editor/test_creature_rejoin.ps1`로 같은 Dedicated 서버에 42초 Client A 정상 종료 후 Client B를 바로 새로 접속했다. 서버 160초 및 Client 2회 모두 exit 0이고 Ready=1이다. 서버 최종 Step=157, Client는 Step=0/LogicalOwned=0. `validate_creature_rejoin.py`로 다음 로그/조건을 확인했다.

| 실행 | Forest Grass/PM_EcoGrass | Barren Dry/PM_EcoDry | Highland Dry/PM_EcoDry | 최대 방향 오차 |
|---|---:|---:|---:|---:|
| Client A | 87 | 165 | 113 | 10.00도 |
| Client B 재접속 | 66 | 73 | 87 | 6.82도 |

표의 횟수는 **로컬 AudioComponent 시작 로그**이며 Client 출력 WAV를 새로 기록한 것은 아니다. 엔진 출력의 실제 비무음 검증은 위 PIE master 녹음에 근거한다. 두 Client 모두 Trigger=Notify만 기록했고 각 2회 카운터 감소/초기화가 관찰됐다(지역별 relevance 탈출·재진입 시 표현 재생성). Client A에서 복제 사슴·늑대, Client B에서 남은 늑대 표현을 확인했다. 포식으로 개체 수가 달라지므로 접속별 동물 수를 동일하게 만들지 않았다.

Dedicated는 Visuals=0/로컬 오디오 0에서 논리 Noise 6665건과 늑대 PreySense를 생성했다. Sight 343/Hearing 5/Memory 4개 스캔 로그를 확인했다. Client에는 NoiseSubsystem을 생성하지 않는 native guard와 Authority Fragment 없는 Trait 구성이 유지된다. 관련 로그에 Error/Fatal은 없다. 증거는 `Saved/Logs/CreatureRejoinServer.log`, `CreatureRejoinClientA.log`, `CreatureRejoinClientB.log`, `Saved/CreatureRejoinValidation.json`, `CreatureRejoinProcessResults.json`이다.

이 fixture의 `-EcoIntegrationObserverCycle`은 `WITH_DEV_AUTOMATION_TESTS` 및 양수 `-EcoIntegrationExitAfter`가 있을 때만 켜진다. 기존 GameState의 서버 시각으로 12초마다 Forest/Barren/Highland를 순회하고 **서버의 observer Pawn 및 Client 카메라만** 이동한다. 기존 Mass Viewer/Bubble·레벨 streaming을 검증하기 위한 명시적 테스트 입력이며 production 플레이어 이동 구현이 아니다. 보통 Play에는 자동 순회가 없다. 서버는 Mesh를 만들지 않는다.

첫 별도 실행에서도 Client 213회 Notify와 세 지역 표면을 확인했다. 수동 재접속 명령은 이미 160초 서버가 종료된 뒤 실행돼 실패했고, 해당 게임은 MCP로 정상 닫았다. 그 시도는 재접속 성공의 근거가 아니며 위 단일 PS 실행의 두 Join을 성공 근거로 사용한다.

최종 에디터·테스트 게임·UBT·dotnet·ShaderCompileWorker 프로세스가 모두 종료된 것을 확인했다.

## 다른 담당자에게 남은 연결

| 담당 | 후속 작업 |
|---|---|
| 학습 | 현재 opt-in 감각/포식 조건을 Python 시뮬레이션과 비교. 청각을 PPO 입력으로 넣으면 관측 계약·정규화·재학습·export·Golden Vector 함께 변경 |
| 서버/네트워크 | production 플레이어 이동/관찰 범위와 장시간 웨이브/끊김/지연 검증. 감각·소음을 Client에서 생성하지 않는 계약 유지 |
| 레벨/환경 | 비/지역 날씨·식생 크기·물/수분·먹이 분포의 실제 공급자를 연결. 현재 환경 multiplier 기본 1을 야행성 구현으로 간주하지 않음 |
| 표현 | 새 종·클립의 접촉 재검토, 필요 시 foot IK 및 종별/젖음/눈 등 추가 표면 소리. 실제 Player Character 발걸음 입력은 현재 비행 관찰자와 별도 |

ORCA/복잡한 우회 경로, 자동 Cover 생성, 무리 Merge/Split은 기존 Deferred 범위다. 이번 작업은 감각 단서와 단일 이동 인계 및 로컬 표현의 완성을 목표로 한다.
