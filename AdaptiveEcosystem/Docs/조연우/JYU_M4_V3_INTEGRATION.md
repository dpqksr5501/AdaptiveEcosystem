# M4 공통 런타임 · v3 정책 · JYU 표현 통합

> **2026-10-23 현재 통합:** [최신 인수인계](JYU_CHAT_HANDOFF_20261023.md)를 먼저 읽는다. 아래 10-15/16의 migration·Social 미연결 설명은 당시 범위다. 현재 SocialControl=0 신호 계약과 보존된 opt-in 행동 훅, 별도 새 맵 `/Game/JYU/Maps/LV_JYU_HerdMigration`의 무리 이주가 연결됐다. 기존 맵 이주 OFF와 v3 개별 이주/wave 비활성 정책은 유지한다. 공동 이주는 실제 Native 이동/context 이전→기존 M4 Migration receipt/인구/Client 표현을 사용한다. 기존 V1 계약·단일 이동 writer·원본 팀 레벨 분리는 유지한다.

> **2026-10-16 Social 실제 연결 갱신:** v3의 Persistent Herd 경보→행동 보정→예약 슬롯 이동·실제 도착 feedback을 연결했다. 아래의 “v3 Social 미연결”은 이전 시점 기록이다. 현재 계약·검증은 [v3 Social 인계](JYU_V3_SOCIAL_HANDOFF.md)를 우선한다.

> **2026-10-16 작업 위치 통합:** 검증 커밋 `8e2f34f`를 기존 `codex/social-shelter-handoff`에 반영했다. 앞으로 원래 저장소 `C:/Users/I/Documents/GitHub/AdaptiveEcosystem`의 `AdaptiveEcosystem/AdaptiveEcosystem.uproject`를 연다. 복사 맵 `/Game/JYU/Maps/LV_JYU_V3Integration`은 그대로 사용한다. 아래 브랜치명은 최초 통합 이력이다. 원래 위치의 빌드·검증 및 worktree 정리는 [작업 위치 통합 기록](JYU_WORKTREE_RETURN_20261016.md)을 따른다.

> **2026-10-16 감지·도주 감사:** 신혁 브랜치 `3916496`의 후속 16개 커밋을 추가 통합했다. R1b 가중치는 유지하고 야생 1단계 세계 규칙을 적용한다. 실제 활성 backend·경보의 연결 범위·새 검증은 [위협·backend 감사](JYU_THREAT_AND_BACKEND_AUDIT_20261016.md)를 따른다. 아래 119개 테스트는 최초 통합 시점 기록이다.

작성일: 2026-10-15. 브랜치 `codex/m4-v3-creature-integration`. 장원준 `wonkii/M4` **67c860c** 위에 권신혁 `origin/Branch_Sinhyeok` **8292856**을 병합하고 충돌 네 파일을 해결했다. 기존 조연우 작업은 main의 PR #11 병합 내용을 유지했다. 사용자의 원래 작업 트리와 레벨 디자이너의 `/Game/Map/LV_Ecosystem_IntegrationTest`는 수정하지 않았다.

## 실행할 맵과 실제 에셋

**`/Game/JYU/Maps/LV_JYU_V3Integration`**를 열어 Play한다. World Partition RenameDuplicate Builder를 **복제 모드**로 실행해 ExternalActors/ExternalObjects까지 독립적으로 복사했다. 원본을 Rename하지 않았다. 에디터 그래픽 문제가 있으면 이 맵 실행에만 `-d3d11`을 사용할 수 있다.

| 위치 | 저장된 구성 |
|---|---|
| `/Game/JYU/Animation` | 사슴·늑대 프로필과 행동 AnimBP, 검증된 네 발 리그 |
| `/Game/JYU/Creatures` | `BP_JYU_Deer`, `BP_JYU_Wolf`, 수동적 표현 Actor |
| `/Game/JYU/Config` | 별도 v3 EntityConfig, Inspector HUD를 사용하는 GameMode |
| `/Game/JYU/Player` | 복사한 실제 Player BP와 서버 보행/위협/발소리 브리지 |
| `/Game/JYU/Audio` | Grass/Dry를 유지하고 Snow/Water/Wet 및 경보 큐 추가 |
| `/Game/JYU/Materials` | 독립 Landscape material/instance와 표면 테스트 발판 |
| 복사 맵 | 3지역, 사슴 지역당 48·늑대 2, 은신처 총 12개, 표면 5종 발판, 플레이어 시작 위치와 조정자 |

기본 프로젝트 시작 맵은 변경하지 않았다. 새 에셋은 `JYU.V3Integration.v1` ownership metadata와 `/Game/JYU` 경로를 확인한 뒤 저장한다. `Tools/Editor/setup_jyu_v3_integration.py`는 재실행 가능한 owned authoring 도구다. 원본 vendor 애니메이션·팀 material·팀 map을 덮어쓰지 않는다. 발소리 변형은 기존 Dry 녹음에서 재생성했고 경보는 **임시 합성 큐**이며 실제 사슴 울음 녹음이 아니다.

## 논리·자원·복제의 책임

M4 분할 Processor 구조를 유지하고 legacy v3 테스트 경로의 phase clock 계약을 보존했다. V1의 7관측/4출력과 가중치는 유지한다. v3는 **명시적 opt-in R1b 18관측/5행동·mask2 계약**이며 별도 Native World/학습 모델을 사용한다. V1 계약을 v3 수치에 맞춰 고치지 않았다. 런타임 Python 추론은 없다.

v3 Native Step이 이동·에너지·포획 결과의 유일한 writer다. V1/Custom Movement 혼용 가드를 유지하며, v3 Entity에는 공통 M4 identity·survival metadata·시각 cue를 붙이고 중복 survival writer를 비활성화한다. Native 사망 원인과 포식자 ID는 M4 death receipt/cleanup으로 전달한다.

`RegisterSpatialFood`/`CommitSpatialFood`는 v3 spatial food를 지역 생태 상태로 연결한다. 지역별 최초 용량/현재량은 Native 모델의 **먹이 단위**이며 일반 V1 수치와 혼용하지 않는다. receipt는 순서·finite·before/consumed/regenerated/after 보존식을 검사한다. 이 source가 활성화된 지역은 일반 재생·직접 소비·manual resource events가 두 번째 writer가 되지 못한다. 실패하면 런타임을 quiesce하고 Ready를 내린다. 개체군·피식 history·지역 summary는 공통 M4에 반영된다.

M4 production V1은 기존 지역 ecology 관측 provider를 유지한다. identity가 없는 legacy RL 경로는 권신혁의 전역 predation EMA/phase clock을 유지한다. 전역/지역 getter와 schema 2 저장 검증을 분리했다. Source 기준으로 설명하며 전역 EMA를 지역 계약처럼 정당화하지 않는다.

서버/Standalone만 논리를 실행한다. Client는 canonical transient EntityConfig를 동일 경로/GUID로 등록해 기존 Mass Bubble DTO를 수동적 표현 Actor에 전달한다. 추가 RPC나 subsystem replication은 만들지 않았다. 기존 payload에 cue bit·focus yaw를 전달하고 add/modify 모두 소비한다. Dedicated는 Mesh·로컬 오디오를 생성하지 않는다.

## 표현과 플레이어 상호작용

행동 프로필의 우선순위·최소 유지시간으로 먹기, 경계, 얼기, 숨기, 수면, 잠행, 돌진/공격, 탈진, 사망을 선택한다. **새 motion capture를 만든 것은 아니며** 기존 Idle/Graze/Rest/Sleep/Attack/Death 클립을 재사용했다. 동물 Actor와 AnimBP는 논리 위치/정책을 소유하지 않는다. 재바인딩 때 사망 포즈·접지·소리 cadence·경보 타이머를 초기화한다.

Sight/Hearing/Memory는 직접 시야, 소리 방향, 마지막으로 감지한 위치를 시각 cue로 전달한다. 새 Sight/Hearing은 먹기를 잠시 중단하고 0.8초 경계한 뒤 원래 동작으로 복귀하며, 지속 cue가 영구 경계를 만들거나 수면·숨기·사망을 덮지 않는다. 늑대의 직접 본 먹잇감 위치는 Native Step의 안정적 View ID에서 보관하고 최근 snapshot+LOS를 확인한다. 기억은 현재 적 좌표를 계속 추적하지 않는다. 사슴의 새로운 직접 Sight 경보는 지역 cooldown과 만료 시간으로 제한한다. 들은 경보를 재전파하지 않고 Client는 지연·dedup된 로컬 경보 큐만 재생한다.

실제 Player CharacterMovement 결과에서 서버 발걸음/위협을 생성한다. Shift 달리기 900cm/s, Ctrl 잠행 270cm/s, 기본 걷기 360cm/s이며 소음 loudness는 1/.12/.4다. RPC는 유효한 gait enum만 받고 클라이언트가 위치/소음을 임의로 보고하는 RPC는 없다. `bUseKeyboardGait=false`면 Enhanced Input/Blueprint의 `SetGait`를 연결할 수 있다. 기존 player 입력은 복사 BP에 보존했다.

표면 우선순위는 명시적 Physical Material이며 copied landscape collision에 남은 기존 Grass/Dry PM도 호환한다. 새로운 Snow/Water/Wet에 사운드가 없으면 무관한 소리로 대체하지 않는다. 동물 Notify는 실제 이동/생존/최신 상태 gate를 거쳐 로컬 오디오만 재생한다.

IK의 구조·실제 스크린샷·수치·한계는 [사슴 IK 검증](JYU_IK_VALIDATION.md)을 따른다. 단일 runtime 모듈을 유지하고, AnimGraph 생성만 별도의 **Editor 전용 모듈** `AdaptiveEcosystemEditor`가 담당한다.

## 비교·기록 도구

Tab으로 visible 개체 순환, 마우스 가운데 버튼으로 선택, R로 1Hz JSONL 기록을 시작/종료한다. 서버/Standalone Inspector는 감지 출처·기억 위치·정책 request와 실제 행동·마스크/phase·목적지·먹은 양을 읽는다. Client는 수신된 표현 정보만 표시한다. 결과는 `Saved/JYU/`이며 원본 논리를 수정하지 않는다.

## 실제 검증과 재현

- 직접 `UnrealBuildTool.exe AdaptiveEcosystemEditor Win64 Development -Project=<uproject> -WaitMutex -NoUBA -NoHotReloadFromIDE` 빌드 성공. 모든 실행은 기존 engine/build process 종료를 확인하고 순차로 진행했다.
- 전체 `Automation RunTests AdaptiveEcosystem`: **119개, 실패 0** (118 Success + 없는 save 파일 로드 검사의 예상 warning 1). policy golden/mask, legacy processor order, spatial conservation/exclusive writer, canonical replication config, saved profiles/graphs, malformed rig·pool rebind·gait bounds를 포함한다.
- 실제 Standalone: 150개 초기 개체의 feeding·capture·death receipt·cleanup, 낮밤/늑대 sleep·서버 소음·표현 cue 확인. v3 mask 위반 0.
- Dedicated/Client: 동일 100초 서버에 Client 두 번 접속, 각 12초 실행. Client logical owned/step 0, 수신 표현 생성·재접속 초기화 확인. Dedicated visual 0. 서버 타임아웃과 겹친 초기 reconnect 시도는 성공 기록에 포함하지 않았다.
- 실제 에디터 PIE: Inspector 선택·JSONL 저장, actual PlayerMovement·서버 발걸음, 동물 Notify 확인. 10조건 IK ON/OFF와 먹기 중 Sight/Hearing 반응 2조건, 총 12조건 화면·소켓 측정 저장. [체크인 근거](Evidence/JYU_V3/IK_summary.json).

자동 검사 출력은 `Saved/IntegrationV3/`에 저장되며 전체 대용량 로그는 체크인하지 않는다. 재현 도구는 `Tools/Editor/run_jyu_ik_visual.py`, `run_jyu_pie_audit.py`다. PIE 오디오 검사에서만 `au.DisableAppVolume 1`을 사용해 배경 창의 무음 영향을 제거한다. 실제 프로젝트/시스템 볼륨 설정을 영구 변경하지 않는다. Python의 직접 enum setter/readback은 이 검사에서 native 상태와 달랐다. 이를 성공 증거로 쓰지 않고 복사 PIE 전용 native gait 검증, 실제 360/270/900cm/s 이동, .4/.12/1 서버 소음으로 확인했다. 원인을 엔진 버그나 게임 입력 버그로 단정하지 않는다. 저장된 5종 발판 모두 실제 Player 재생 로그에서 일치하는 Physical Material과 Sound를 확인했다. [최종 검증 요약](Evidence/JYU_V3/Verification_summary.json)과 [Native 보행·표면 재생 근거](Evidence/JYU_V3/Player_audio_evidence.txt)를 참고한다.

D3D12 실행 중 `DXGI_ERROR_DEVICE_HUNG`, Windows Application WER LiveKernelEvent 141이 발생했다. dotnet 예외로 간주하거나 build 파일을 삭제하지 않았으며 D3D11에서 시각 검증을 계속했다. 이 PC의 D3D12 장기 실행 안정성 검증은 완료하지 않았다.

## 남아 있는 계약 차이와 인계

**v3 R1b 경로는 Social의 ModulatedAction/slot arrival feedback을 정책·이동에 통합한 경로가 아니다.** authored cover geometry는 Native 입력으로 전달하지만 Social Moving/Occupied 예약 상태를 달성했다고 주장하지 않는다. 기존 V1 PPO→Social→Movement→Feedback은 보존한다. R1b 행동/마스크 파리티를 바꾸는 Social override는 RL 담당과 별도의 관측/학습 계약을 정한 뒤 구현해야 한다.

v3의 hearing/기억 cue·경보는 표현 계층이고 R1b에 새 청각 관측이나 수색 정책을 추가하지 않았다. 실제 플레이어는 Native external threat 입력이며 모델이 이동/포획하지 않는다. v3 migration·wave spawn은 현재 비활성화했다. Native population/resource loop는 연결했지만 이주·번식/웨이브까지 완성된 전체 목표로 서술하지 않는다. Synthetic alarm, 모든 지형/LOD의 IK, packaging/cooked build 및 모든 장기 multiplayer 시나리오도 이번 검증의 범위를 넘는다.
