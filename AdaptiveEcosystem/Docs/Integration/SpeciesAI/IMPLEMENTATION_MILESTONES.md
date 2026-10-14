# Species AI 구현 마일스톤과 간단한 수동 확인

기준: UE 5.8 / 2026-10-14. 자동화 테스트는 사용자 요청으로 추가·실행하지 않는다. C++ 빌드 성공과 에디터/네트워크 실행 확인은 별도 증거로 기록한다.

| 마일스톤 | 코드 범위 | 수동 확인 |
| --- | --- | --- |
| M1 독립 구성·프로필 | EnabledSpecies, 종별 immutable profile, 기존 coordinator 연결 | 기존 통합 레벨 복사 후 DeerOnly/WolfOnly를 선택하고 반대 Config를 비워 단독 스폰 확인 |
| M2 StateTree·경로·이동 | Mass Task/Evaluator, 예산형 NavMesh, grounded writer, 기존 writer 배제 | NavMesh가 있는 평면에서 배회/정지와 벽 회피, 막힌 목적지 실패·재시도 확인 |
| M3 사슴 생활·예약 | Utility 생활/위협·Social Shelter, Smart Object slot, 실제 Graze exposure | 먹이 옆 이동→섭식→Energy/Food 변화, 위협/슬롯 제거 때 중단·해제 확인 |
| M4 늑대·상호작용 | 감각 기억/수색/추적·request attack/cooldown, fixture provider | WolfOnly 대역 추적/표적 상실 후 포기, Both에서 실제 포획·단일 보상 확인 |
| M5 LOD·복제·인계 | 중요도/주기·진단, 최소 활동 표시, 설정 생성 도구 | 원거리/no-player 생태 유지, Server+2 Client의 상태·관련성 확인, 프로파일 캡처 |

## 공통 설정

기존 팀 레벨/Config를 덮어쓰지 않고 복사본을 사용한다. 기존 coordinator 하나와 EcologyRegion을 유지하고 M3 Box Bootstrap은 같은 월드에 배치하지 않는다. GameMode는 EcoCreatureIntegrationGameMode를 사용한다. 지형/충돌 셀을 로드하고 Region Bounds·스폰 지점을 검증한다.

생성된 Config/프로필과 정확한 적용 순서는 [Editor 빠른 시작](EDITOR_QUICK_START.md)에 있다. 임의로 engine Movement Trait를 기존 PPO Config에 섞지 않는다. 파일별 owner와 실제 구현 계약은 [Source 책임](SOURCE_RESPONSIBILITIES.md)에 있다.

## 검증 기록

2026-10-14, branch M4의 기존 working tree 위에서 구현했다. baseline HEAD는 `3062180f895c7dc7e738f8f9efdc720788f40ef1`이다. 기존 미커밋 Source·맵·오디오 변경은 보존했다. 커밋·PR·기존 팀 레벨 수정은 수행하지 않았다.

| 검증 | 실제 결과 | 증거/범위 |
| --- | --- | --- |
| 직접 UBT `AdaptiveEcosystemEditor Win64 Development` | **Succeeded** | `Saved/SpeciesAI/Build-final.log`; UE 5.8.3 CL58210709 |
| StateTree 3개와 Profile/EntityConfig 3쌍, 기본 SO 작성 | 생성·저장 | `/Game/Experiments/SpeciesAI`의 10개 `.uasset` |
| 새 Editor-Cmd 프로세스의 저장 에셋 재로드 | **exit 0, 0 error(s), 0 warning(s)** | `Saved/SpeciesAI/AssetAuthoring-final.log` |
| 설정 적용 | `StockHeightAutoRegister=0` 확인 | 동일 로그; 새 grounded 개체와 엔진 높이 writer 배타 설정 |
| StateTree/profile/config 참조 검사 | Deer/Wolf/DeerV1 각각 `TreeReady=1 ProfileValid=1 ConfigReferenceValid=1` | 동일 로그 |
| 기본 SmartObject Definition | Validate 성공·재로드 성공 | 동일 에셋 작성 도구의 성공 결과 |
| 자동화 테스트 | **추가·실행 안 함** | 사용자 요청 준수. 에셋 작성/컴파일은 게임 자동화 테스트가 아님 |
| PIE/Standalone 실제 행동·다중 Client·Dedicated Server/cook·soak/성능 | **미수행** | 아래 수동 gate에서 확인 필요 |

최초 에셋 생성은 메모리 컴파일을 통과했지만 재로드에서 authoring schema 수명 오류가 발견됐다. 엔진 compiler가 EditorData의 schema를 Tree에 복제하는 구조에 맞춰 수정하고, 생성한 에셋을 보수·재저장한 뒤 새 프로세스 재로드를 통과했다. 최초 성공 로그를 최종 에셋 검증으로 대신하지 않았다.

## M1 — 독립 역할과 설정

구현: EnabledSpecies 필터, 활성 Config/표현 클래스/스폰/wave 검증, 공유 프로필 검증, 외부 데이터가 맞는 Mass StateTree 에셋 3종, opt-in template assembly. 반대 종 Config 없이 준비할 수 있다.

수동 확인(약 3분):

1. 복제한 레벨에서 DeerOnly/EC_Deer/사슴 1마리로 설정하고 Wolf Config를 비운다. Validate Editor Setup의 오류를 해결한 뒤 PIE를 시작한다.
2. `eco.M4.Dump details`와 `eco.SpeciesAI.Status`에서 논리 사슴 1, 늑대 0을 확인한다.
3. PIE를 종료하고 WolfOnly/EC_Wolf/늑대 1마리로 바꾼다. Herbivore Config를 비우고 같은 확인을 한다.
4. 잘못된 role/profile 또는 컴파일 안 된 StateTree를 복제 Config에 넣으면 스폰 전에 거부되는지 확인한다.

완료 기준: 반대 Config 미지정이 활성 종의 시작을 막지 않음; client 구성에 권위 fragment가 추가되지 않음. **수동 결과 미기록**.

## M2 — 공통 경로와 단일 이동

구현: budget형 동기 full path·aging·revision/deadline·corridor/short path, stock PathFollow/Boundary/Steering/Avoidance/ApplyForce 재사용, capsule/지면/지역/금지영역 제약, actual 도착/진행 timeout, 기존 writer와 stock height writer 배제.

수동 확인(약 5분):

1. 평탄한 NavMesh 지면에 한 마리와 벽을 배치한다. Graze 장소 없이 사슴 Energy를 `eco.M4.SetVitals <ID> 1 0.55`로 맞추어 배회를 관찰한다.
2. 경로를 따라 벽을 돌아가며 실제 위치가 바닥에 붙는지 확인한다. `eco.SpeciesAI.Capture`로 MoveRevision/실패/BlockedFrames를 기록한다.
3. 통로를 막거나 끊긴 NavMesh 너머에 장소를 두고 bounded timeout/재시도·새 장소 선택을 확인한다. 위치가 벽/Null Area/현재 Region 밖으로 넘어가면 실패다.
4. `eco.SpeciesAI.PathQueries 1`로 낮춘 뒤 여러 마리를 켜서 Pending 대기와 일반 요청의 aging을 확인한다. 종료 후 기본 8로 복원한다.

완료 기준: 중복 위치 적분·허위 도착 없음, 막힘이 영구 pending이 되지 않음. **수동 결과 미기록**.

## M3 — 사슴 생활·Social·슬롯·섭식

구현: 점수/배고픔 hysteresis, 배회/Forage→Graze/Rest/Regroup/Flee/Recover, 실제 Herd 중심, Social ModulatedAction·Shelter Request, Graze/Rest SO claim/lease/occupied/invalidation/release, 실제 Graze exposure→기존 Ecology FeedRequest/grant→Energy.

수동 확인(약 5분):

1. 지역 Food를 충분히 두고 먹이 hint 옆 Graze 장소를 1개 배치한다. Definition=SO_ActivitySlot, RegionId 일치, For Predator=false를 확인한다.
2. 사슴 Energy를 0.2로 맞춘 뒤 접근→실제 도착→Graze를 확인한다. Output Log/`eco.Integration.Dump`에서 Food 감소와 Energy 증가를 같이 확인한다.
3. 사슴 2마리·슬롯 1개로 바꾸고 중복 점유가 없는지 확인한다. 슬롯이 없는 개체가 이동 중인데도 Graze로 지급받으면 실패다.
4. 접근/섭식 중 장소를 삭제하거나 위협 fixture를 보이게 한다. Claims/Releases/Slots와 행동을 기록하고 섭식 중단·예약 해제를 확인한다.
5. 실제 차폐가 있는 ShelterAnchor를 배치한다. 도착 전에 Occupied가 되지 않고, 실제 도착 후 다음 Social 패스에서 점유되는지 확인한다. 사망/Travel/삭제 시 예약도 해제되어야 한다.

완료 기준: 실제 이용 시간만 자원 요청으로 이어짐; Shelter와 일반 슬롯의 중복 owner 없음. **수동 결과 미기록**.

## M4 — 늑대 독립 감각·추격·공격과 실제 통합

구현: 개인 prey 감각 기억 재사용, fixture의 FOV/range/LOS·coarse hearing, cue 조사/추격 제한/표적 cooldown, 공격 mailbox·freshness/거리/LOS/region 재검증, 실패 backoff/성공 cooldown, 실제 lethal candidate와 기존 death commit, 별도 fixture receipt 영양.

수동 확인(약 5분):

1. WolfOnly, Predator Survival=true, Energy=0.2로 두고 visible 정지 prey fixture를 앞쪽에 배치한다. FixtureCaptures와 AttackSuccess 증가·일회 영양을 확인한다.
2. Visible=false, Noise=false로 바꾸고 숨은 실제 좌표를 계속 따라가지 않는지 확인한다. 마지막 cue 조사 후 timeout/cooldown·휴식/배회로 돌아와야 한다.
3. 뒤쪽 noise-only, 벽 뒤, 도달 불가 후보를 각각 시험한다. hearing-only 공격 성공·무제한 실패 요청·같은 실패 장소의 영구 점유는 실패다.
4. 늑대 2마리로 같은 대역을 공격하게 하고 대역 한 회 capture당 reward 1건인지 확인한다.
5. PIE를 끝내고 Both, fixture=false, 사슴 4/늑대 1로 바꾼다. 실제 포식에서 prey 하나의 death receipt·Population 감소·PredationHistory·포식자 영양을 확인한다. fixture 성공 수로 이 결과를 대신하지 않는다.

완료 기준: Brain에는 감각 cue만, resolver만 현재 실제 위치 사용; 기존 자동 포획과 새 공격의 중복 없음. **수동 결과 미기록**.

## M5 — LOD·연결별 복제·계측·비교 인계

구현: Simulation High/Medium/Low 보호·평온 결정 주기 1/2/4배, no-player Low·Off/variable movement tick 배제, 기존 연결별 Bubble/ReplicationLOD에 Activity byte 추가, 표현/AnimBP 읽기 전용 인계, Status/CSV/manifest·trace scopes.

수동 확인(약 10분):

1. 두 Client로 서로 다른 거리에서 관찰하고 `eco.M4.Dump`로 각 connection relevance/수신 개체 수를 확인한다. Client의 `eco.SpeciesAI.Status`에서 UnexpectedLogic=0이어야 한다.
2. Client가 relevance 밖으로 나가 표현이 없어져도 서버 Food/Energy/Population/기억/lease가 진행되는지 확인한다. 다시 접근하면 상태가 복원되어야 한다.
3. no-player 전용 서버와 원거리 동물을 확인한다. 평온 Low는 결정 주기만 줄고 이동/생태 clock이 멈추지 않아야 한다. 공격/위협/슬롯/Travel은 High로 보호되어야 한다.
4. 1→32→128→512 범위에서 Unreal Insights로 Input/Nav/Movement/Attack과 engine avoidance를 기록한다. Logical cap은 512 그대로이며 이 확인을 넘는 성능을 보장하지 않는다.
5. 기존 PPO/EC_DeerV1/full EC_Deer를 같은 초기 맵·생존·늑대 조건으로 각각 실행한다. [비교 설정](EDITOR_QUICK_START.md)의 정책 비교와 전체 시스템 비교를 분리한다.

완료 기준: client 논리 실행 없음, 연결별 복제와 server simulation 독립, profiler 결과/최대 지연과 오차 공개. **수동 결과 미기록**.

## 남은 release gate와 확장

M1~M5의 기본 코드는 작성·빌드했고 에셋 저장/재로드를 확인했다. 종별 D8/W8 release와 I0~I6 통합 gate는 위 실제 실행 결과를 채운 이후 통과로 표시한다. 새 레벨/NavMesh/SmartObject 장소 배치와 전용 공격/섭식 애니메이션 편집은 빠른 시작을 따라 별도로 설정한다.

Carcass resource/영양 원장, Pack, stamina/체온/수분, patch 잔고, ORCA, 비동기 Nav, 집계 원거리 simulation, 512 초과 상한 확장은 기존 상세 계획의 후속 범위다. 이 기능을 이미 구현한 것으로 기록하지 않는다.
