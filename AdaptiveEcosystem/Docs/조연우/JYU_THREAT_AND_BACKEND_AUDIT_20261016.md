# 늑대 접근 반응 · 팀원 기능 사용 감사 (2026-10-16)

> **2026-10-16 Social 실제 연결 갱신:** v3의 Persistent Herd 경보→행동 보정→예약 슬롯 이동·실제 도착 feedback을 연결했다. 아래의 “v3 Social 미연결”은 이전 시점 기록이다. 현재 계약·검증은 [v3 Social 인계](JYU_V3_SOCIAL_HANDOFF.md)를 우선한다.

현재 실행 위치는 원래 저장소의 `AdaptiveEcosystem/AdaptiveEcosystem.uproject`, 브랜치는 `codex/social-shelter-handoff`, 맵은 `/Game/JYU/Maps/LV_JYU_V3Integration`이다.

## 확인한 문제와 수정

- 원격 fetch 결과 권신혁 `origin/Branch_Sinhyeok`는 `3916496`으로 진전했으며 기존 통합본에는 후속 16개 커밋이 없었다. 장원준 `wonkii/M4`는 `67c860c`이며 기존 통합본에 포함되어 있다.
- 신혁 브랜치의 야생 1단계 규칙을 병합했다. 감지 시야 300°, 늑대 움직임에 따른 청각, 근접 도주 반사, 사슴 지방 비축, 늑대 식사·포만, 점진적 밤잠을 사용한다. 상수·조건은 [Wild1 계약](../RL_Policy/RL_V3_WILD1_SPEC.md)을 따른다.
- **새로 학습한 가중치를 적용한 작업은 아니다.** R1b `18 → 64 → 64 → 5`, mask2 내장 모델은 그대로다. 감지와 도주는 신혁 브랜치가 추가한 세계 규칙이며 PPO 요청과 실제 행동이 달라질 수 있다. V1 7관측/4출력 계약·가중치는 변경하지 않았다.
- 기존 M4 자원 보존 receipt, 사망 원인·포식자 ID, 안정적 prey ID, 실제 플레이어 관측, canonical Client config, 단일 movement writer를 보존했다. 병합 충돌은 prey snapshot 갱신과 새 늑대 통계 집계를 모두 유지해 해결했다.
- 새 청각 감지를 표현에 연결할 때 모든 감지를 Sight로 취급하던 문제를 수정했다. Native perception에 관측 벡터와 무관한 provenance 두 bool을 기록하며, 실제 시야 조건+LOS가 아니고 들리기만 한 위협은 Hearing으로 표현한다.
- `IK ON/OFF` 비교 사슴은 AI가 없는 임시 표현이다. 라벨에 `NO AI`, HUD에 비교 모드 안내를 추가하고 36초 비교 종료 후 PIE를 종료한다. 일반 생태계를 보려면 Play를 다시 시작한다. 기존 사용자 로그에 비교 도구 실행 흔적은 있으나 사용자가 관찰한 사슴을 그것으로 단정하지 않는다.

## 실제 활성화 범위

| 기능 | v3 복사 맵에서의 상태 | 근거 |
|---|---|---|
| Mass Entity·Identity·지역·생명주기 | 사용 | `EcoCreatureV3Trait`, 기존 coordinator |
| M4 Bubble 복제·관심 영역·표현 예산·pool | 사용 | `UEcoMassNetworkTrait`, canonical config, 공통 표현 경로 |
| Python PPO 학습·export | 저장소 학습 도구로 존재 | `herbivore_rl/`; 이번 작업에서 재학습하지 않음 |
| C++ 학습 가중치 추론 | 사용 | `EcoWorldV3::Step` / `DecideHerb` / `kBuiltinNet` |
| v3 응집·분리·이웃 도주 비율 | 사용 | `EcoRepertoire::Control`, `FHerbPerception::Kin` |
| 외부 MassFlock 패키지 | 사용하지 않음 | 자체 grid/steering 구현. [기존 도입 감사](../Integration/THIRD_PARTY_INTEGRATION.md) |
| 기존 SpeciesAI StateTree·NavMesh·engine avoidance 이동 | v3 개체에서 비활성 | 해당 fragments/tags가 없다. 두 이동 writer를 동시에 붙이지 않음 |
| 서버 `Herd.Alarm` noise → 근처 개체 Hearing·경계 표현 | 사용 | `EcoCreatureSensoryPresentation`, 지역 3초 cooldown, heard alarm 재전파 금지 |
| Social Persistent Herd·Alarm → ModulatedAction → v3 이동 | 미연결 | v3 template에 Social 행동 fragments가 없음 |
| Social 슬롯 예약·도착·점유 feedback, migration/wave | v3에서는 미완료/비활성 | 기존 V1 계약은 보존 |

`kin_alarm`은 시야 안 도주 중인 이웃 비율이다. Social Persistent Herd 경보 수신·감쇠와 동일한 값이 아니다. 경보를 들은 모든 사슴이 자동으로 FLEE를 실행한다고 설명하지 않는다. 새 WildFlight는 직접 감지한 사냥 중 늑대에 반응하며, 쉬거나 먹는 늑대에는 경계할 수 있고 은신처에서는 웅크릴 수 있다.

## 사용자가 확인하는 방법

1. 복사 맵을 열고 일반 Play를 시작한다. IK 비교 Python은 실행하지 않는다.
2. Tab 또는 마우스 가운데 버튼으로 실제 사슴을 선택한다. `request`, `executed`, `native_threat_count`, `native_threat_distance_cm`, `native_kin_alarm`, `flight_override`를 확인한다.
3. `flight_override`: 0=두뇌, 1=경계하며 멀어짐, 2=안전해질 때까지 도주, 3=은신처 웅크림이다. `request`와 실제 `executed`는 다를 수 있다.
4. R로 기록하면 `Saved/JYU/`에 JSONL이 생긴다. authority에만 PPO/원생 지각이 있고 Client는 받은 표현만 표시한다.
5. Output Log에서 `eco.Senses.NoiseLog 1`을 켜면 `[Eco AlarmHeard] Listener=... Source=... Event=...`로 실제 경보 수신자를 확인한다. 끌 때는 같은 변수에 0을 넣는다. 이것은 정책 변경 스위치가 아니다.
6. 자동 관찰은 에디터 콘솔 `py <project>/Tools/Editor/run_jyu_threat_audit.py`로 실행한다. 실제 개체만 읽고 저장 에셋·Mass 상태를 바꾸지 않는다. 35초 관찰 후 PIE와 에디터가 정상 종료된다. 직접 수동 관찰은 `audit_jyu_threat_runtime.py`를 실행하면 에디터를 종료하지 않는다.

진단의 `next_request/next_logits/next_mask/observation`은 다음 스텝 준비 값이고 `request/committed_policy_read/flight_override/executed`는 마지막 실행 스텝 값이다. 서로 다른 스텝의 마스크를 비교하여 위반이라고 판단하지 않는다.

## 이번 검증

- 직접 UBT 최종 빌드 성공 (`Build05.log`).
- D3D11 일반 PIE 35초: 70회 표본, 실제 사슴 기록 3,332건. 실제 FLEE 247건, HIDE 180건, kin_alarm > 0은 436건, Hearing 표현 313건. 숫자는 고유 개체 수가 아닌 표본 기록 수다. 모든 기록에서 v3 brain·단일 이동 backend 및 새 시야·청각·도주 설정을 확인했고 비교용 사슴은 0이었다.
- 늑대 근접 중 GRAZE/override 0이던 두 사례는 사슴 #27 ↔ 식사 중 늑대 #2(약 13.5m, 식사 36스텝 남음), 사슴 #12 ↔ 식사 중 늑대 #1(약 10.1m, 23스텝 남음)이었다. 사냥 중 늑대를 무시했다고 판정하지 않는다.
- IK 비교 12조건·142개 발 표본에서 안내 화면과 36초 PIE 종료를 확인했다. 화면은 [AI 없는 비교 표시](Evidence/JYU_V3/IKPreview_NO_AI_20261016.png), 실제 생태계 화면은 [늑대·사슴 일반 Play](Evidence/JYU_V3/ThreatRuntime_20261016.png), [수치 요약](Evidence/JYU_V3/ThreatAudit_20261016.json).
- 시작 전 사용자 변경 에셋 68개를 별도 백업하고 SHA256을 대조했다. 사용자가 저장한 에셋은 이 수정의 스테이징 대상에서 제외한다.

최종 자동화·네트워크 결과는 아래에 기록한다. 전체 로그·JSON은 `Saved/ThreatAudit_20261016/`에 보관한다. 초기 runner/API 오류로 표본이 없던 실행은 성공 결과에서 제외했다. Python 학습 환경 단위 테스트는 현재 Python에 torch/numpy/pytest가 없어 실행하지 않았으며, 재학습하지 않았다. 엔진에서 Python 생성 골든과 C++ 계산을 대조했다.

Native v3 감지는 학습 환경의 평면 거리·방향·원형 cover 모델이다. Unreal 장애물 LOS와 NavMesh 기반 행동을 전부 대체했다고 설명하지 않는다. 지형 이동 hook과 표현 LOS는 별도다.


Dedicated 110초 + 순차 Client 두 번(각 12초) 검증: 세 프로세스 정상 종료. 서버 표현 수는 0, 두 Client는 Ready=1, LogicalOwned=0, Step=0이며 수신 표현을 생성했다. 서버 경보 수신 1452건, 수신자 328개체, (개체·경보 event) 중복 0, 최대 수신 거리 2400cm(3000 × 0.8 유효 범위)였다. 자원 보존 receipt 거부 0, 마스크 위반 0. 이 결과가 Social Persistent Herd의 행동 인계를 검증한 것은 아니다.

최종 바이너리 전체 자동화: **136개 수행, 135 Success + 1 예상 warning, 실패 0·미실행 0**. 기존 없는 save 파일 검사의 warning이다. Wild 6종, 점진적 밤잠, 기존 V1/v3 골든, M4 자원·복제·순서, 실제 v3 template 진단과 Sight/Hearing provenance 검사를 포함한다. 테스트 결과는 `AutomationFinal/index.json`을 기준으로 확인했다.
