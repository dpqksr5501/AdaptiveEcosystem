# 동물 발소리·감각 범위 연결

> **최신 2026-10-08 고도화:** 통합 사슴/늑대 BP는 접촉 Notify 40개를 소비하며 실제 지형 Physical Material을 우선한다. 늑대의 별도 먹잇감 Sight/Hearing/Memory도 연결했다. 아래 최초 거리/지역 연결 기록과 검증 수치는 당시 이력이다. 현재 계약·에셋·43개 자동 테스트 및 실행법은 [감각·Notify 고도화](CREATURE_SENSORY_AND_NOTIFY_REFINEMENT.md)를 먼저 읽는다.

2026-10-08. 사용자가 편집한 Grass/Dry M4A 14개를 원본 보존 상태로 mono 48kHz PCM16 WAV로 변환하고 Unreal SoundWave로 임포트했다. 파일은 프로젝트 `Content/Audio/Footsteps/Grass`, `Dry`에 함께 있다. 자동 자르기·정규화는 적용하지 않았다. 지역 배치는 [팀 레벨 런타임 배치](ECOSYSTEM_LEVEL_RUNTIME_PLACEMENT.md)를 따른다.

## 에디터에서 확인

1. `/Game/Map/LV_Ecosystem_IntegrationTest`를 열고 Play. 사슴·늑대 근처로 비행 관찰자를 이동하면 발소리가 들린다. 처음에는 19마리이고 포식·죽음으로 감소하므로 반복 확인은 PIE를 다시 시작한다.
2. 발 아래 등록된 Physical Material에 따라 Grass/Dry 각 7개 중 랜덤 선택한다. 재질이 누락/미등록일 때만 `Forest` Grass, 나머지 Dry 지역 fallback을 사용한다. 같은 클립의 바로 다음 반복을 피하고 pitch 0.97–1.03을 적용한다.
3. 동물에 접근/멀어지며 SA 감쇠를 확인한다. 이 설정은 3m 안쪽 최대 볼륨, 3–40m 선형 감쇠, 40m 바깥 무음이다. 실제 볼륨은 원본 음량·거리·Visibility 충돌 차폐·전체 동시 재생 제한에 따라 달라진다.
4. 콘솔에서 아래 표시를 각각 켠다. 여러 범위를 동시에 켜면 선이 겹치므로 목적에 맞게 선택한다. 끌 때는 값 `0`.

| 콘솔 명령 | 표시 의미 |
|---|---|
| `eco.Footsteps.Debug 1` | 파랑 3m 안쪽 / 보라 40m 바깥쪽: 로컬 SA 범위. Client에서도 가능 |
| `eco.Senses.DrawNoise 1` | 주황: 실제로 수락된 게임플레이 소리 이벤트의 최대 전달 범위, 현재 20m |
| `eco.Senses.DrawHearing 1` | 청록: 개체별 청각 수신 범위. 종·개체 배율·비 상태 반영 |
| `eco.Senses.DrawFOV 1` | 사슴 초록/늑대 주황: 실제 수평 시야각·거리·진행 방향. 낮밤·비·개체 배율 반영 |
| `eco.Senses.DrawLimit 4` | 시야/청각 범위 표시 개체 수 제한, 기본 16 |
| `eco.Senses.Debug 1` | 직접 시각/청각/기억의 위치·신뢰도·불확실성 표시 |
| `eco.Footsteps.Log 1` | 시작한 로컬 AudioComponent·클립·StableAgentId·지역 로그 |
| `eco.Senses.NoiseLog 1` | 논리 개체의 서버 발소리 이벤트 로그. Dedicated에서도 가능 |
| `eco.Senses.PreyLog 1` | 늑대의 개인 먹잇감 Sight/Hearing/Memory 인계 로그 |

Senses 표시는 **Server/Standalone**에서 확인한다. Client에 권위 감각 상태를 새로 복제하지 않았다. 초록 선은 기복 있는 지형에서도 보이도록 전경 overlay로 그린다. 부채꼴/구 안이라는 사실만으로 감지 성공을 뜻하지 않으며, 실제 LOS·차폐·거리 감쇠·최소 신뢰도 검사는 따로 적용한다. 현재 시각 검사는 수평 FOV이므로 세로 시야각을 가진 3D 원뿔처럼 표시하지 않는다. 사슴은 개인 위협과 무리 경보를, 늑대는 별도의 개인 먹잇감 단서를 관찰한다. 늑대의 먹잇감 기억은 무리 경보로 방송하지 않는다. `DrawLimit`은 각 감각 Processor별 제한이다.

## 에셋과 조정 지점

- `/Game/Audio/Footsteps/Settings/DA_EcoFootsteps`: Grass/Dry 배열, 우선할 Grass/Dry Physical Material 목록, fallback Grass 지역 목록, 볼륨·보폭·최소 속도·AI 소리 범위·늑대 위협 강도.
- `SA_EcoFootsteps`: 공간화, 3m 안쪽/37m falloff, Visibility occlusion, 차폐 볼륨 0.35/LPF 2500Hz.
- `SC_EcoFootsteps`: 모든 동물 합계 최대 8개 동시 재생, StopQuietest. 동물마다 8개가 아니다.
- 레벨 `Eco_CreatureRuntime`의 `FootstepAudioSet`에 위 DA가 저장돼 있다. 기존 평면 `L_EcoCreatureIntegration` 조정자에는 자동으로 연결하지 않았다. 다른 레벨에서 사용할 때도 이 속성을 지정한다.

원본 M4A와 변환 WAV는 파일 탐색기에서 보이고, Unreal Content Browser에서는 생성된 SoundWave/SA/SC/DA가 보인다. 새 파일 추가 후 `Tools/Editor/convert_footsteps.py` 실행 → 에디터 Python 콘솔에서 `configure_creature_audio.py` 실행으로 다시 임포트한다. WAV는 원본과 함께 Content에 보존하므로 다른 작업자의 Reimport 경로도 유지된다. `.m4a`, `.wav`, `.uasset`는 Git LFS 대상이다. Python/ffmpeg는 편집 도구이며 게임 런타임에 사용하지 않는다.

## 책임과 네트워크 계약

`Policy Raw → Social Request → 기존 단일 Movement writer → 실제 Transform/Velocity → 발소리 관찰` 순서다. 오디오 코드가 위치·PPO 관측·Raw Action·가중치·이동 writer를 변경하지 않는다.

- 권위 측 조정자는 Mass 작업 완료 후 개체별 `FEcoCreatureFootstepFragment`에서 이동 거리를 누적한다. 죽은 개체·정지·가로막혀 위치가 변하지 않은 개체는 소리를 생성하지 않는다. 초기 생성·2500cm 초과 점프·0.5초 초과 hitch도 재설정하여 catch-up burst를 막는다.
- 실제 이동 거리가 보폭에 도달하면 `UEcoNoiseSubsystem::ReportCreatureFootstep`에 immutable Position, StableAgentId, SpeciesId를 전달한다. Actor가 필요 없으므로 Dedicated에서도 동작한다. 늑대의 위협 강도는 0.8, 초식동물은 0으로 설정하여 같은 무리의 발소리가 포식자 경보가 되지 않게 한다. 자기 StableAgentId의 소리도 제외한다. 늑대의 개인 먹잇감 감각은 위협 강도 0인 사슴 발소리도 읽는다.
- 기존 Hearing → Personal Sense → Herd Alarm → Social 의도 보정 경로가 이를 소비한다. 소리 이벤트 수명 0.6초, 큐 한도 128·overflow reject 계약은 유지된다. 발소리는 PostActorTick에 생성돼 다음 감지 pass에서 읽힌다.
- 통합 동물 BP의 native `Footsteps` component는 표시 위치/속도의 실제 이동을 검증한 뒤 발 접촉 Notify에서 공간 오디오만 재생한다. AI 이벤트를 보고하지 않는다. 실제 Physical Material을 우선하고 기존 복제의 RegionId는 fallback에 사용한다. Notify 모드에서는 거리 기반 로컬 재생을 끈다. 새 소리 RPC/복제 필드를 추가하지 않았고 Client에 논리 cadence/vitals/policy/noise subsystem을 만들지 않는다.
- Dedicated는 렌더 Actor나 AudioComponent를 만들지 않고 논리 소리만 생성한다. SA 40m와 AI 이벤트 20m는 다른 목적의 값이다. AI의 실제 수신 범위는 `min(청각 범위, 이벤트 최대 범위)`이고 비/거리/차폐/신뢰도로 더 감소한다.

## 최초 구현의 한계와 인계 — 아래 두 문단은 고도화 이전 기록

최초 구현은 BS에 발 접촉 Notify를 추가하지 않은 **실제 이동 거리 기반 보폭 근사**였다. 걸음 140cm → 달리기 220cm 보폭으로 보간하며 최소 속도 40cm/s, 최소 이벤트 간격 0.12초를 사용한다. 네 발의 정확한 접촉 프레임 동기화가 필요하면 애니메이션 담당이 접촉 Notify/종별 보폭을 조정해야 한다. Client의 보간 cadence는 소리를 중복 방송하지 않지만 서버 걸음과 프레임 단위로 동일하지는 않는다. 정확한 특수 공격/일회성 소리 동기화는 별도 서버 이벤트 계약이 필요하다.

최초 표면 선택은 **RegionId 기반**이었고 Landscape Physical Material 연결 전이었다. 현재는 Physical Material을 우선하지만 젖은 바닥/물/눈 전용 소리 세분화는 후속 작업이다. 현재 Dry는 황무지·고지대 공용, Grass/Dry 클립은 사슴·늑대 공용이다. 실제 walking Player Character의 발 접촉 입력 연결은 별도 작업이며 비행 관찰자는 가짜 발소리를 내지 않는다. PPO V1 관측을 늘리지 않았다. 학습 담당이 청각 관측을 추가할 경우 정규화·학습 환경·Golden Vector 계약을 함께 갱신해야 한다.

## 검증 기록

- 엔진 직접 UBT `AdaptiveEcosystemEditor Win64 Development -NoUBA` 성공. 전체 자동 테스트 39개 성공: 실제 거리/가로막힘/정지/죽음/teleport/hitch, SA·전역 동시 재생 설정, Actor 없는 늑대 소리의 후방 청각 감지·자기 소리 제외·초식동물 경보 제외 포함. 기존 Policy Golden Vector·Movement/Shelter·BS/Facing 검사도 통과.
- MCP Computer Use로 실제 레벨에서 임포트·DA/SA/SC 저장·PIE 실행. 초원/황무지 각 약 6초 엔진 **master submix** 출력 WAV 확인: Grass peak 0.1108/RMS 0.00491, Dry peak 0.0415/RMS 0.00577. 마이크 녹음이 아니라 엔진 오디오 출력이며, 원본이나 기록을 정규화하지 않았다. 사슴과 늑대의 로컬 재생 로그 확인.
- 최신 빌드의 PIE에서 위에서 내려다본 사슴의 초록 수평 FOV overlay를 확인했다. 기복 있는 지형 위에서도 선이 표시된다. SA 구와 논리 소리 이벤트 범위도 PIE에서 확인했다.
- Dedicated + 렌더 클라이언트 실제 접속 확인: Dedicated는 `NetMode=1`, `Visuals=0`에서 논리 발소리를 생성하고 로컬 Audio 로그는 0건이다. Client는 `NetMode=3`, `LogicalOwned=0`, `Step=0`에서 복제된 사슴의 Grass 클립을 21회 시작했고 논리 소리 로그는 0건이다. Client 85초 테스트는 `Ready=1 Step=0`으로 타이머 정상 종료했다. Dry의 실제 오디오 출력은 위 Standalone PIE에서 검증했고 네트워크 클라이언트 Dry 재생까지 새로 검증한 것은 아니다.
- 로컬 증거는 `Saved/FootstepImportManifest.json`, `Saved/FootstepEditorSetup.json`, `Saved/FootstepAudioAudit/PIE_Grass.wav`, `PIE_Dry.wav`, `PIE_PlaybackCounters.json`, `OutputValidation.json`, `Saved/Logs/FootstepsAutomation.log`에 있다. Saved는 Git 제외다.
- 네트워크 증거는 `Saved/Logs/FootstepsDedicatedFollow.log`, `FootstepsClientFollow.log`에 있다. 첫 60초 서버 실행은 클라이언트가 늦게 접속하여 관찰 범위의 동물이 없었고 서버 종료 시 연결이 닫혔다. 이후 120초 서버/85초 클라이언트로 접속 순서와 종료 시간을 조정해 재생을 확인했다. 추가 관찰자 이동은 MCP 창 활성화 오류로 수행하지 않았으며, 이 로그는 기본 관찰자 위치에서의 재생 결과다.
- 최종 Dedicated 120초 실행도 `Ready=1 Step=118`로 정상 종료했다. 후속 서버/클라이언트 로그에 Error/Fatal은 없었고, 종료 후 Unreal Editor·테스트 게임·UBT·dotnet·ShaderCompileWorker 프로세스가 모두 없음을 확인했다.

게임 레벨은 별도 복제본이 아니라 main에서 병합한 같은 맵 경로에 우리 브랜치의 owned runtime Actor를 연결한 구성이다. 작업·감각 가이드는 현재 Source의 opt-in Creature 경로를 기준으로 하며 기존 M3 Bootstrap의 가드는 유지한다.
