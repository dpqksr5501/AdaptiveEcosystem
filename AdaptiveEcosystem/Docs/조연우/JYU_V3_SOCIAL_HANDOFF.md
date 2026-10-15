# v3 실제 Social 경보·은신처 인계

2026-10-16, 기존 `codex/social-shelter-handoff`, 원래 프로젝트 폴더, 복사 맵 `/Game/JYU/Maps/LV_JYU_V3Integration`에서 구현한다. 신혁 최신 `b5c7384`와 원준 M4 `67c860c`를 포함한다. 직전 [감지 감사](JYU_THREAT_AND_BACKEND_AUDIT_20261016.md)의 **Social 미연결 항목을 이번 변경으로 연결**한다. 원본 팀 맵·사용자 에셋 변경은 보존한다.

## 실제 실행 경로와 책임

```text
Persistent Herd membership / aggregate
  → Native v3 직접 감지 또는 실제 Player.Footstep
  → 독립 Native observed-alarm 채널
  → 기존 AlarmPropagation (거리·시간 감쇠, 개인/공유 정보 분리)
  → 기존 SocialResponse (v3 요청의 명시적 preference projection)
  → 기존 Shelter Query → Reservation → Lifecycle / Request
  → Native v3 Control hook → 기존 한 번의 이동·섭식·대사·포획 적분
  → 실제 body/ground 기반 Moving·Arrived feedback
  → 다음 Social 패스에서 점유·lease 갱신·실패/사망/삭제/수요 종료 정리
  → 공통 M4 표현 DTO → Client Actor / AnimBP / 발소리
```

- **정책과 Social을 분리한다.** v3 R1b 18관측·5행동 가중치/마스크 계산·관측 인코딩은 유지한다. `Decision.Request/CommittedRequest`를 덮어쓰지 않는다. 기존 V1 7관측·4출력도 변경하지 않는다.
- `ProjectPolicy`는 v3 이산 요청을 기존 Social 선호 계약으로 명시적으로 옮기는 adapter다. GRAZE→Forage=1, FLEE→FleeDist=1, HIDE→Cover=1, Cohesion 기준은 기존 repertoire 값이다. 이를 V1 PPO 추론이라고 표현하지 않는다. `FEcoPolicyOutputFragment`는 compatibility 기본값으로 보존한다.
- `SocialResponse`는 매 패스 새 projection에서 `ModulatedAction`을 계산한다. 이전 보정값을 다시 곱해 누적하지 않는다. 이동은 이 결과와 유효 Request를 한 번 소비한다.
- 새 `HerbControl` hook은 Native 정책·기본 제어 뒤, 약함 보정·이동·섭식·대사 앞에만 실행된다. hook 없는 Native/Python 골든 경로는 그대로다. Social은 위치·Vitals·먹이 장부를 직접 적분하지 않는다.
- Native Step/Visual은 Movement 그룹에서 Shelter Lifecycle 뒤 실행된다. Social은 이전 완료 Native snapshot을 감지하며 Feedback은 다음 Lifecycle에서 소비한다. 프레임 내 순환 의존성을 만들지 않는다.
- v3에는 Social fragments/shared config와 전용 adapter만 추가한다. V1 HerbivoreTag·legacy SteeringGeometry·SpeciesAI/engine 이동을 덧붙이지 않는다. Client에는 기존 표현·transport 구성만 둔다.

## 경보·청각의 규칙

직접 감지한 깨어 있는 **사냥 중** 늑대만 새 Native herd threat를 발행한다. 식사·포만·수면 중인 늑대를 새 공격 경보의 근거로 사용하지 않는다. 감지 거리/시야/청각은 현재 Native v3 설정을 읽고 표현 시야는 Unreal LOS도 확인한다. 0.2초 sensory scan 예산으로 물리 trace가 매 render frame 반복되지 않게 한다.

직접 관찰자가 근처 같은 종의 무리에 한 hop으로 보고하고, 기존 AlarmPropagation이 감쇠·Panic/Alert/Recovering을 계산한다. `SharedThreatPosition`, 개인 기억, `Herd.Alarm` 소음은 새 직접 관측으로 재발행하지 않는다. Native 감지 채널과 기존 V1 감지·수동 주입 채널을 분리하여 서로의 입력을 지우지 않는다. 모든 관찰자가 없어져도 채널을 정리한다.

실제 서버 CharacterMovement에서 나온 `Player.Footstep`도 직접 청각으로 연결한다. 위치는 원본 소음 snapshot이며 숨은 플레이어의 현재 좌표를 추적하지 않는다. loudness가 유효 청각 거리를 줄이며 noise ID watermark로 같은 발소리를 재생하지 않는다. 공유 보고는 passive 표현 cue에서만 Hearing으로 옮긴다. Social 개인 기억에 가짜 Sight/Hearing을 기록하지 않는다.

Panic은 직접 본 위협이 없어도 보고된 위치 반대로 FLEE한다. Alert는 고개를 들고 걸어서 물러나며 실제 섭식 배수를 줄인다. Recovering/Regrouping은 보정 cohesion·forage를 소비한다. 직접 위급한 Native 도주 방향을 공유 보고가 반대로 돌리지 않는다.

## 은신처 이동과 버그 방지

- 예약 후보와 이동 소비자 양쪽에서 Native 무대 범위 및 현재 Native cover 안의 실제 슬롯만 허용한다. 다른 지역·필터에서 제외한 작은 anchor를 반복 선택하지 않는다.
- 급박한 Native 도주 중 위험 쪽 슬롯은 후보에서 제외한다. 이미 받은 예약이 위험해졌으면 Yielded를 반환하고 도주한다.
- 예약 번호·소유자·유효 시각·실제 slot 좌표를 확인한다. 만료되거나 교체된 토큰으로 이동/점유하지 않는다.
- 이동 속도는 기존 repertoire의 보행 속도다. 마지막 스텝을 목적지까지 남은 거리로 제한하여 슬롯 주위를 지나쳐 진동하지 않는다. 실제 body+ground의 3D 거리로 Arrived를 보고한다. desired target이나 Actor를 움직여 도착한 것으로 만들지 않는다.
- 도착 뒤에는 실제 위치를 유지하고 feeding=0인 crouch/hold를 표현한다. 죽음·이주 자격 소실·삭제·수요 종료·실패·정체·feedback 중단 정리는 기존 Lifecycle 계약을 사용한다.
- **반복 놀람 버그:** 공유 Panic이 유지되는데 Native arbiter가 개인 시야 없는 FLEE를 다시 GRAZE로 돌리면, 매번 Enter(FLEE)가 startle를 초기화할 수 있었다. Social의 연속 도주에서 한 번 시작한 startle countdown을 이어 사용하여 제자리에 묶이는 문제를 고쳤다.
- 기존 coordinator feeding은 `FEcoIntegratedV3Fragment`를 명시적으로 제외한다. 새 Social Request가 유효해져도 먹이가 두 번 차감되지 않는다. 기존 spatial receipt·사망 원인·포식자 ID·Client canonical config를 보존한다.

## 눈으로 확인하기

일반 Play에서 Tab/가운데 버튼으로 실제 사슴을 선택한다. `request`와 `executed`, `native_threat_count`, `social_state`, `alarm_strength`, `social_override`, `shelter_state`를 비교한다. R로 JSONL 기록할 수 있다.

- social_state: 0 Calm, 1 Alert, 2 Panic, 3 Recovering, 4 Regrouping.
- social_override: 0 없음, 1 경계, 2 도주, 3 슬롯 이동, 4 슬롯 유지, 5 재집결/회복.
- shelter_state: 0 None, 1 Searching, 2 Reserved, 3 Moving, 4 Occupied.
- `native_behavior_before_social`과 실제 `executed`로 Native 규칙과 Social 보정의 차이를 구분한다. `native_threat_count=0`인데 Social 보정으로 움직이는 기록은 간접 정보 소비의 근거다.

`eco.Shelter.Log 1`, `eco.Social.ActionAudit 1`로 슬롯 상태 전이와 선호 보정을 확인한다. 자동 관찰은 복사 맵에서 `run_jyu_threat_audit.py`를 사용하고 CLI에 `-JYUSocialV3Audit -JYUThreatCamera`를 더하면 실제 개체를 관찰한 JSON·화면·로그를 `Saved/SocialV3_20261016/`에 저장한다. 생성하는 것은 PIE 임시 카메라뿐이며 원본 동물 위치/정책을 주입하지 않는다.

## 검증과 범위

직접 UBT `AdaptiveEcosystemEditor Win64 Development` 최종 빌드 성공(`Build09.log`). 전체 자동화 **140개: 139 Success + 1 예상 warning, 실패 0·미실행 0**이다. warning은 기존 `Predation.SaveLoadGlobalEma`의 없는 저장 파일 검사다. 기존 V1/v3 골든·야생 규칙·M4 자원/복제/순서에 다음 실제 연결 검사를 추가했다.

| 회귀 검사 | 검증한 결과 |
| --- | --- |
| BlindMemberReaction | 직접 관찰자→Herd→개인 감지 없는 수신자의 Panic, Raw Graze 보존·실제 Flee·섭식 0, 반복 startle 종료 뒤 생존 개체의 실제 이동, 공유 기억 재발행 방지 |
| SlotMovementAndCleanup | 실제 Query/Reserve/Lifecycle/Native 이동으로 Moving→Occupied, 실제 도착 거리, 섭식 0, 사망 뒤 lease·Request 정리 |
| EvidenceChannelsAndUnsafeTarget | 위험 방향 슬롯 Yield, 만료/잘못된 lease 거부, Native 채널 정리가 기존 V1 관측 채널을 지우지 않음 |
| PlayerFootstepEvidence | 실제 서버 noise의 위치·청각 출처, 동일 event 재생 방지, 작은 sneak 소리의 거리 밖 미탐지 |

BlindMemberReaction은 실제 사냥 상태인 늑대의 속도만 fixture에서 0으로 둔다. 처음에는 4m 거리의 움직이는 늑대가 3스텝 놀람 중 사슴을 포획하여 이동 assertion을 끝낼 수 없었다. 반응 계약 검사와 포획 결과를 분리했으며 기존 포획 회귀 검사와 아래 일반 PIE에서는 사냥 이동·포획을 유지했다. 모델·실제 레벨 속도는 변경하지 않았다.

**일반 PIE 35초, 70회 표본:** 실제 사슴 기록 3,274건, 비교용 임시 사슴 0건. 모두 Social 활성·Native 단일 이동·SpeciesAI 이동 비활성이다. 실제 FLEE 87건, HIDE 123건, Social 경계 29건·슬롯 이동 16건·슬롯 유지 3건이다. 직접 위협 감지 0인 상태의 Social 경계/은신처 반응은 25건이며 회복/재집결까지 포함하면 265건이다. 이는 고유 개체 수가 아닌 표본 기록 수다.

실제 사슴 #47의 점유 표본은 슬롯 `(32400,49500,-1590.64)`에서 약 36.4cm 이내였다. 속도 0·섭식 0이었으며 같은 위치를 유지했다. 새 Flee/슬롯 이동/유지 표본에서 실제 섭식은 모두 0이었다. 자연 PIE에서는 Raw Graze→공유 Panic Flee 사례가 표본에 없었으므로 해당 분기는 위 회귀 테스트의 근거와 구분한다. [실제 레벨 화면](Evidence/JYU_V3/SocialHandoff_20261016.png), [수치·테스트·네트워크 근거](Evidence/JYU_V3/SocialHandoff_20261016.json).

**Dedicated 110초 + 순차 Client 두 번(각 12초):** 세 프로세스 정상 종료(코드 0), Ready=1. 서버 표현 0, 두 Client는 LogicalOwned=0·Step=0이며 수신 Actor/mesh를 생성했다. 서버도 #179의 Moving→Occupied(시간 94.09초, 거리 32.7cm)를 기록했다. 최종 shelter summary는 MissingFeedbackBuffer=0·ArrivalRejected=0이었다. 저장소 루트에서 `AdaptiveEcosystem/Tools/Editor/test_jyu_social_network.ps1`을 실행하면 같은 복사 맵·정상 종료 시나리오를 재현할 수 있다. 전체 로그와 원시 관찰은 `Saved/SocialV3_20261016/`에 있다.

에디터 시작 시 `LowLevelTestAdapter`의 `Condition failed` 메시지 15개가 PIE 이전에 출력된다. 직전 성공한 `ThreatPIE04.log` 등에서도 동일하게 있었으며 이번 수정으로 해결했다고 주장하지 않는다. 새 PIE 관찰 구간의 Python 오류나 서버/Client의 별도 런타임 오류는 없었다. 사용자 변경 에셋 68개는 시작 백업 SHA256과 모두 일치하며 이번 스테이징에서 제외했다.

이 작업은 v3 Social 행동·슬롯 인계이며 migration/wave를 새로 켜거나 SpeciesAI NavMesh 이동으로 바꾸는 작업이 아니다. Native 지형 제약과 기존 progress timeout을 사용하며 모든 장애물의 경로 탐색을 보장하지 않는다. 외부 MassFlock 패키지는 설치하지 않았고 자체 이웃/조향을 사용한다. 현재 Python에 torch/numpy/pytest가 없어 Python 학습 테스트와 재학습은 하지 않았으며 엔진 Native 골든 검증은 통과했다. Social이 만드는 세계 궤적은 기존 Native-only Python 비교 궤적과 달라질 수 있다. 학습 계약과 세계 규칙 개입을 구분한다.
