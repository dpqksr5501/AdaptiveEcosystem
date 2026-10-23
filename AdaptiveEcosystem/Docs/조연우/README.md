# 조연우 작업 시작 문서 — 역할·진행상황·다음 연결

모든 팀원·AI의 공통 목표는 [프로젝트 공통 맥락](../PROJECT_CONTEXT.md)을 먼저 읽는다. 아래 문서는 조연우 분야의 실제 구현·검증 인계다.

이번 채팅의 후속 전체 구현과 최신 재개는 [전체 상태](../Architecture/ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md), [life-v1 실행 계약/팀별 연결 API](../Architecture/ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md)를 우선한다. 아직 미커밋인 `ecfd82f` 이후 로컬 변경이며 아래 PR/기준 커밋의 완료 이력과 구분한다. 새 owned `LV_JYU_Ecosystem`에만 활성화했고, 기존 HerdMigration 맵과 기본 신호 경로는 보존했다.

다음 채팅은 [life-v1 최신 인수인계](../Architecture/ECOSYSTEM_LIFE_HANDOFF_20261023.md)의 실제 범위·실패 수정·재현·후속 담당부터 확인한다.

갱신일: **2026-10-23**. 먼저 [최신 인수인계](JYU_CHAT_HANDOFF_20261023.md)를 읽는다. 구현 기준 `581ce1d` + `e22dbbd`, 통합 main `a74fcac`, 작업 브랜치 `codex/social-shelter-handoff`다. [PR #14 — 먹이 부족에 따른 무리 이주 기능 추가](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/14)는 확인 당시 OPEN·Ready for review·미병합이고 기능/디버그 push를 완료했다.

| 읽을 문서 | 확인할 내용 |
|---|---|
| [최신 인수인계](JYU_CHAT_HANDOFF_20261023.md) | 현재 기본값·위치·연결 범위·기존 검증·후속 작업·발표 자료 위치 |
| [무리 이주와 신호 계약](HERD_MIGRATION_AND_SIGNAL_CONTRACT.md) | ReadSignal, Persistent Herd, 실제 Native 이동/지역 인계, M4 자원·인구·복제 연결 |
| [이주 디버그 사용법](HERD_MIGRATION_DEBUG_20261023.md) | 지도·현재 목적지·실제 구성원·조작·가뭄 재현·촬영 |
| [현재 상태](SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md) | 현재 통합과 과거 V1/MVP 기록의 구분 |
| [문서 감사 기록](JYU_DOCUMENTATION_AUDIT_20261023.md) | 갱신한 문서와 Source 근거·검증 한계 |

현재 확인 맵은 `/Game/JYU/Maps/LV_JYU_HerdMigration`이다. 기존 맵의 이주 옵션은 OFF, 새 맵만 ON이다. v3 기본 `SocialControl=0`을 유지하고, 이주 의도는 Native의 유일한 이동 writer가 소비한다. 실제 지역 진입과 경로 끝 정착은 다르며 모든 무리가 성공하지는 않는다. 일반 PIE·Dedicated/Client 결과는 체크인 Evidence를 따른다. 이 문서 갱신에서 새 UBT·PIE를 실행하지 않았다.

## 다음 기획의 세부 설계

시작 프롬프트를 실행한 후속 로컬 구현은 [전체 구현 상태표](../Architecture/ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md)와 [수분·식생 계약/팀 연결](../Architecture/ECOSYSTEM_VEGETATION_CONTRACT_20261023.md)을 먼저 확인한다. 기존 이주 기본값·Native 단일 writer·V1/v3 모델은 보존하며 새 식생은 opt-in이다. 전체 구현 완료와 구분하고 실제 빌드/PIE/멀티 범위는 해당 문서의 최종 증거를 따른다.

실제 저장 BP·서식지/날씨 배치는 새 `/Game/JYU/Maps/LV_JYU_Ecosystem`에 있다. [BP 실행·배치 안내](../Architecture/JYU_ECOSYSTEM_BP_SETUP_20261023.md)를 따라 별도 콘솔 입력 없이 Play한다. 기존 인수인계의 `LV_JYU_HerdMigration`과 팀 원본은 보존했다.

그 이후 사용자 요청의 [통합 재점검/수정](../Architecture/ECOSYSTEM_INTEGRATION_REVIEW_20261023.md)을 수행했다. 최신 직접 UBT/213개 자동화·실제 맵/멀티 검증은 이 문서가 기준이며, 식생/이주 경계의 오류와 관찰 도구의 동일 이름 World 선택 문제를 수정했다.

[다른 채팅용 전체 구현 프롬프트](../Architecture/ECOSYSTEM_IMPLEMENTATION_START_PROMPT_20261023.md)에 구조 감사·기존 팀 코드 개선·분야별 연결 안내·학습 경계·실제 동작/검증 기준을 정리했다. 새 채팅에 해당 파일을 읽고 진행하도록 요청하면 된다. 이번 문서 추가에서 기능 구현이나 새 빌드/PIE를 실행한 것은 아니다.

[MMORPG 동적 생태계 세부 기획](../Architecture/DYNAMIC_ECOSYSTEM_DETAILED_DESIGN_20261023.md)은 물·토양·식생/섭식, 장소 선호·경험, 흔적·무리 사냥, 출생 스폰·세대 속도, 체형/ABP·규모/저장 구조를 정리한 **제안**이다. 현재 구현 완료 목록과 구분하며 기능 활성화나 정책 변경을 수행한 것은 아니다.

## 이전 통합 이력 — 아래 날짜의 현재/대기는 당시 상태

2026-10-22 main 병합·날씨 호환 검증은 [main 통합 기록](JYU_MAIN_MERGE_20261022.md), 이후 PR #12 `a74fcac` 반영·늦은 은신처 먹이 장부 복구는 [PR #12 통합 기록](JYU_PR12_MAIN_INTEGRATION_20261022.md)에 보존한다. 과거 PR 제목·HEAD·Draft·push 전 상태를 현재 상태로 사용하지 않는다.

> **최신 보호 은신처 구현:** 새 복사 맵 `/Game/JYU/Maps/LV_JYU_RefugeSafety`에 수풀·바위 12곳과 실제 늑대 진입 차단·내부 피식 보호·지면 슬롯/도착 검증을 연결했다. 기존 맵·사용자 변경은 보존한다. [구현·에디터 확인·검증](JYU_REFUGE_SAFETY_20261016.md)을 먼저 읽는다. PPO 재학습 완료를 의미하지 않는다.

> **2026-10-16 Social 실제 연결 갱신:** v3의 Persistent Herd 경보→행동 보정→예약 슬롯 이동·실제 도착 feedback을 연결했다. 아래의 “v3 Social 미연결”은 이전 시점 기록이다. 현재 계약·검증은 [v3 Social 인계](JYU_V3_SOCIAL_HANDOFF.md)를 우선한다.

갱신일: **2026-10-16**. 현재 작업 브랜치는 `codex/social-shelter-handoff`이며 원래 프로젝트 폴더에서 작업한다. 2026-10-15 통합 worktree의 검증 커밋 `8e2f34f`를 기존 브랜치에 fast-forward로 반영했다. 원래 위치의 직접 UBT·119개 자동화·에디터 12조건·서버/Client 재접속 검증 후 별도 worktree 정리를 완료했다. 앞으로 원래 `AdaptiveEcosystem.uproject`를 연다. [위치 통합 기록](JYU_WORKTREE_RETURN_20261016.md). 기존 PR #11은 main에 병합됐고, 아래 2026-10-08 항목은 이전 구현 이력이다.

현재 실행 맵은 원본과 독립적으로 복사한 **`/Game/JYU/Maps/LV_JYU_V3Integration`**이다. M4+권신혁 v3 Native brain, 행동 프로필/AnimBP, 실제 플레이어 발소리, 감각 표현·경보, Client 표현, Inspector 기록을 연결했다. [현재 통합 계약·실행·검증](JYU_M4_V3_INTEGRATION.md)과 [사슴 IK 수정·비교 화면](JYU_IK_VALIDATION.md)을 먼저 읽는다. v3의 Social slot handoff·migration·wave는 완료했다고 간주하지 않는다. V1 경로와 원본 팀 레벨은 보존했다.

2026-10-16 추가 감사: 신혁 `3916496`의 감지·야생 도주 규칙을 병합했다. R1b 가중치 유지, MassFlock은 설계 참조이며 실제 구현은 자체 이웃·조향이다. v3의 경보 표현과 Persistent Herd 행동 인계는 구분한다. [위협·backend 감사](JYU_THREAT_AND_BACKEND_AUDIT_20261016.md).

---

**이하 2026-10-08 기준 상세 기록**

갱신일: **2026-10-08**. 다른 Codex 채팅이나 팀원이 조연우 작업을 이어갈 때 읽는 진입 문서다. 대화 기록 없이 현재 범위와 연결 지점을 파악하는 것이 목적이며, 상세 계약을 대체하지 않는다.

- 구현 기준: `54413ed` (`feat: 테스트 레벨에 동물 감각·발소리와 은신처 연동`).
- 확인 당시 브랜치: `codex/social-shelter-handoff`.
- [PR #11 — 테스트 레벨에 동물 행동·감각·발소리 기능 통합](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/11): 확인 당시 **OPEN**, 대상 `main`. 이후 병합 여부와 현재 HEAD는 작업 전에 다시 확인한다.
- 프로젝트: [AdaptiveEcosystem.uproject](../../AdaptiveEcosystem.uproject), **UE 5.8**. 최상위 규칙은 [루트 AGENTS.md](../../../AGENTS.md).

## 1. 내 역할을 두 문장으로

**개체가 주변 위협과 먹잇감을 시야·청각·기억으로 인지하고, 무리 경보와 은신처 선택으로 행동 의도를 보정하는 Social·감각 시스템을 맡는다. 이 의도를 기존 이동 경로와 연결하고 사슴·늑대 BP·애니메이션·발소리로 표현하며, 실제 이동 계산·PPO 학습·서버 복제는 각 담당 계층의 책임을 유지한다.**

초기 역할은 `Social: 무리·경보·은신처`였고, 사용자 요청으로 감각·인지와 동물 표현·통합 검증까지 확장했다. **후각은 명시적으로 제외**했다.

## 2. 프로젝트 맥락과 책임 경계

프로젝트 목표는 Mass 개체, Python PPO 학습, C++ Native 추론, Social, 단일 이동 경로가 생태계 피드백 루프로 이어지는 것이다. 팀의 환경 방향은 **황무지·숲(보금자리)·고지대**, 지형·물·먹이를 이용한 행동 학습, 날씨에 따른 식생 크기 변화, 밤낮에 따른 몬스터 성향 변화다. 이는 전체 목표이며, 모든 환경 입력과 학습 연결을 이번 Social 작업에서 완료한 것은 아니다.

| 영역 | 조연우의 구현·연결 범위 | 기존 담당 계층의 책임 |
|---|---|---|
| Social | 지속적인 무리 가입/이탈·집계, 경보 전파/감쇠, 은신처 평가·예약·점유·해제, 행동 의도 보정 | 실제 flock 조향·위치/속도 적분은 Steering/Movement |
| 감각·인지 | 시야각·LOS, 청각, 개인 기억, 사슴 위협 정보와 늑대 먹잇감 정보의 분리, 디버그 | 새 PPO 관측/행동 스키마·학습·가중치 변경은 RL 담당 |
| 표현·통합 | 수동적 사슴/늑대 BP, 방향 정렬·2D BS, 발 접촉 Notify·공간 오디오, 실제 팀 레벨 배치와 인계 검증 | Mass 논리 상태·Vitals·지역 자원은 기존 논리/생태계 계층 |
| 네트워크 | 기존 Mass Bubble을 소비하는 Client 표현과 재접속 확인 | 복제 transport·relevance·서버 운용은 네트워크 담당 |
| 환경 | 기존 지역/지형 입력을 읽고 감각·은신처·표현 소비 지점을 제공 | 지역 날씨·낮밤·물·식생 공급자는 World/레벨 담당 |

현재 연결 원칙:

```text
PPO Raw Action → Social ModulatedAction / Shelter Request
              → 기존 단일 Steering/Movement → 도착·실패 Feedback
              → Shelter 점유·예약 유지/정리

위협 Sight/Hearing/Memory → 사슴 개인 인지 → Herd Alarm → Social
먹잇감 Sight/Hearing/Memory → 늑대 개인 인지 → 기존 Predator Movement
권위 Mass 이동 거리 → 서버 논리 소음
수신된 표현 이동 + AnimNotify → 로컬 발소리
```

Social/감각 Processor나 BP에 별도의 논리 Transform/Velocity writer를 추가하지 않는다. 서버/Standalone이 논리 권위이며 Client는 표현만 수행한다. 런타임 Python 추론, 새 소리 RPC, 기존 M3 혼용 가드 제거로 통합을 해결하지 않는다.

## 3. 현재 완료한 범위

1. **PPO–Social–이동 연결**: 기존 7개 관측·4개 행동·가중치를 유지하며 Social Request를 기존 이동 writer가 소비하고 Feedback을 반환한다. 실제 은신처 Moving → Occupied와 사망 시 슬롯 반환을 확인했다.
2. **사슴/늑대 표현**: 실제 동물 BP와 속도·회전 입력의 2D BS를 연결하고 Mesh 전방과 이동 방향을 정렬했다. BP는 논리 개체를 표현하기 위해 런타임 생성한다.
3. **실제 팀 레벨 배치**: `main`의 레벨을 병합해 같은 레벨에 지역·먹이 분포 힌트·은신처·조정자를 배치했다. 별도 복제 테스트 맵을 새로 만든 작업이 아니다.
4. **감각·기억**: 사슴은 위협 감지/무리 경보, 늑대는 별도의 개인 먹잇감 Sight/Hearing/Memory를 소비한다. 기억은 마지막 감지 위치이며 시야 밖 대상의 현재 좌표를 몰래 추적하지 않는다. opt-in 포식에는 최근 직접 Sight와 LOS가 필요하다.
5. **발소리·표면**: Grass/Dry 14개 SoundWave, SA/SC, owned 이동 클립 10개·발 접촉 Notify 40개, 지형 Physical Material 분류와 디버그를 연결했다. 원본 동물 애니메이션과 원본 지형 머티리얼은 보존했다.
6. **권위/표현 분리**: Dedicated는 논리 소음만 생성하고 Mesh/오디오를 만들지 않는다. Client Notify는 로컬 오디오만 재생하며 AI 소음을 보고하지 않는다. 동일 서버에 두 번 접속하는 표현/재생 초기화를 검증했다.

서버 소음은 이동 거리 기반이고 로컬 오디오는 애니메이션 접촉 기반이므로 프레임 단위로 동일한 이벤트는 아니다. 발 접촉 시점은 샘플 기반 근사이며 foot IK는 구현 범위에 포함되지 않는다. 지형 분류는 현재 Grass/Dry 두 가지이며 눈·돌·물 전용 사운드를 뜻하지 않는다.

**검증 기준(2026-10-08 구현 작업):** 직접 UBT 빌드 성공, 자동화 **43/43**, 실제 PIE의 발소리 출력·표면 분류·은신처 이동/점유/해제, Dedicated/Client 및 동일 서버 재접속을 확인했다. 상세 조건과 한계는 [최신 검증 기록](CREATURE_SENSORY_AND_NOTIFY_REFINEMENT.md)에 있다. 이 시작 문서 추가는 문서 작업이며 새 빌드/PIE 실행을 의미하지 않는다.

로컬 `Saved/`의 로그·오디오·검증 JSON은 Git에 포함되지 않아 다른 체크아웃에는 없을 수 있다. 체크인된 상세 기록과 재생성 도구를 먼저 확인한다. 마지막 구현 테스트 후 Unreal Editor와 테스트 게임은 종료했다.

## 4. 에디터에서 이어서 확인할 위치

| 대상 | 경로/방법 |
|---|---|
| 현재 실제 팀 레벨 | `/Game/Map/LV_Ecosystem_IntegrationTest`를 직접 열고 Play. 프로젝트 기본 시작 맵과 구분 |
| 레벨 조정자 | Outliner `EcologyRuntime`의 `Eco_CreatureRuntime`; 3지역·먹이 힌트 3개·숲 은신처 2개 |
| 초기 개체 | 사슴 16 + 늑대 3. 웨이브 OFF이므로 포식 후 감소; 반복 확인은 PIE 재시작 |
| BP / BS | `/Game/Creatures/Integrated/BP_EcoDeer`, `BP_EcoWolf`; `BS_EcoDeer_Turning`, `BS_EcoWolf_Turning` |
| 접촉 클립 | `/Game/Creatures/Integrated/FootContacts`; [체크인 접촉 manifest](../../Tools/Editor/Data/creature_foot_contacts.json) |
| 발소리 설정 | `/Game/Audio/Footsteps/Settings/DA_EcoFootsteps`, `SA_EcoFootsteps`, `SC_EcoFootsteps`; 표면은 `/Game/Audio/Footsteps/Surfaces` |
| 이전 평면 시연 | `/Game/Creatures/Integrated/L_EcoCreatureIntegration`은 초기 시연용; 실제 팀 레벨과 구분 |

주요 콘솔 명령:

```text
eco.Senses.DrawFOV 1
eco.Senses.DrawHearing 1
eco.Senses.Debug 1
eco.Senses.PreyLog 1
eco.Shelter.Log 1
eco.Creature.DrawFacing 1
eco.Footsteps.Debug 1
eco.Footsteps.Log 1
```

감각·은신처 디버그는 권위 월드에서 확인한다. Client의 로컬 발소리 디버그와 구분한다. Client에 보이는 개체 수는 복제 거리의 영향을 받으며 보이지 않는 것이 서버 생태계 중단을 뜻하지 않는다. 기존 M3 Bootstrap을 같은 레벨의 조정자와 함께 배치하지 않는다.

## 5. 먼저 읽을 문서와 Source

| 순서 | 문서 / 읽는 목적 |
|---|---|
| 1 | [루트 AGENTS.md](../../../AGENTS.md): 권위·역할 경계·빌드 규칙 |
| 2 | [CURRENT_STATE](SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md)의 **§1.0, 2026-10-08**: 최신 opt-in 상태. 그 아래 2026-10-05/09-30 표와 헤더의 옛 HEAD는 역사 기준이며 현재 완료 여부로 읽지 않는다 |
| 3 | [최신 감각·Notify·표면 및 검증](CREATURE_SENSORY_AND_NOTIFY_REFINEMENT.md), [실제 팀 레벨 배치](ECOSYSTEM_LEVEL_RUNTIME_PLACEMENT.md) |
| 4 | [Creature production 통합](CREATURE_PRODUCTION_INTEGRATION.md), [이동 인계·은신처 생명주기](SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md), [감각·인지 계약](SOCIAL_SENSORY_RUNTIME.md) |
| 5 | [Social 아키텍처](SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md), [PPO V1 계약](../RL_Policy/POLICY_CONTRACT_V1.md), [Mass 실행 순서](../Mass/MASS_PROCESSOR_ORDER.md) |

| Source 진입점 | 확인할 책임 |
|---|---|
| [EcoSocialFragments.h](../../Source/AdaptiveEcosystem/AI/Social/EcoSocialFragments.h), [EcoSocialMovementTypes.h](../../Source/AdaptiveEcosystem/AI/Social/EcoSocialMovementTypes.h) | ModulatedAction·Request/Feedback 계약 |
| [EcoThreatDetectionProcessor.cpp](../../Source/AdaptiveEcosystem/AI/Social/Alarm/EcoThreatDetectionProcessor.cpp), [EcoPredatorPerception.cpp](../../Source/AdaptiveEcosystem/AI/Social/Senses/EcoPredatorPerception.cpp), [EcoNoiseSubsystem.cpp](../../Source/AdaptiveEcosystem/AI/Social/Senses/EcoNoiseSubsystem.cpp) | 위협/먹잇감 감각, 서버 소음 |
| [EcoShelterLifecycleProcessor.cpp](../../Source/AdaptiveEcosystem/AI/Social/Shelter/EcoShelterLifecycleProcessor.cpp) | 예약·점유·lease·종료 정리 |
| [EcoBehaviorProcessors.cpp](../../Source/AdaptiveEcosystem/AI/Policy/EcoBehaviorProcessors.cpp), [EcoCreaturePredatorProcessor.cpp](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePredatorProcessor.cpp) | 기존 이동 소비자·포식 조건. Social에 이동을 다시 구현하지 않음 |
| [EcoCreatureIntegrationSpawner.cpp](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.cpp), [EcoCreatureNetworkTrait.cpp](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureNetworkTrait.cpp) | opt-in 구성·Authority/Client 분기 |
| [EcoCreatureRepresentationActor.cpp](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureRepresentationActor.cpp), [EcoAnimNotifyFootstep.cpp](../../Source/AdaptiveEcosystem/Creature/Audio/EcoAnimNotifyFootstep.cpp), [EcoFootstepAudioComponent.cpp](../../Source/AdaptiveEcosystem/Creature/Audio/EcoFootstepAudioComponent.cpp) | 수동적 표현·회전·접촉음 |

현재 컴파일 가능한 Source를 구현 사실 기준으로 사용한다. 과거 MVP 프롬프트·발표 초안·목표 설계에 등장하는 기능을 구현 완료로 간주하지 않는다. 최신 opt-in Creature 통합이 기존 JYU/M3 전체 전환을 완료했다는 뜻도 아니다.

## 6. 다음 연결 — 먼저 합의할 항목

| 함께할 담당 | 다음 연결/확인 | 조연우 측 역할 |
|---|---|---|
| 학습 | opt-in 감각/포식 조건과 Python 기본 환경의 차이를 학습 시나리오에 반영할지 결정. 지형·물·먹이 입력 확장 시 V1 계약/Golden Vector와 대조 | 인지 정보·Social 보정·도착/실패 사례 제공. 관측 차원·보상·가중치를 임의 변경하지 않음 |
| 레벨/환경 | 지역 날씨·낮밤·식생·물 공급자의 실제 상태와 갱신 계약 연결 | 기존 환경 multiplier와 표면/은신처 소비 지점 연결. 현재 기본 감각 배율 1을 임의 성향 수치로 대체하지 않음 |
| 네트워크 | 실제 production 플레이어 이동/relevance, 지연·장시간 실행·대규모 개체 검증 | 수동적 표현의 bind/reset·발소리·권위 분리 사례 검증. 기존 transport 확장은 담당자와 합의 |
| 조연우 후속 선택 | 새 은신처/종·애니메이션 도입 시 예약 정리·감각·표현 회귀 확인; 필요하면 발 IK/경사 자세 보정 | 현재 접촉 근사의 개선 작업으로 별도 범위 결정 |

현재 이동에는 지면·장애물·물 금지 구간 guard가 있지만 우회 경로 탐색/ORCA까지 구현한 것은 아니다. Merge/Split, multi-hop gossip, 자동 Cover 생성도 Deferred다. 이 항목들을 완료된 기능의 버그나 이번 문서 작업의 필수 구현으로 취급하지 않는다.

## 7. 다른 Codex 채팅에서 이어가는 방법

아래 문장을 새 채팅에 붙이고, 이어서 원하는 작업을 지정한다:

> 루트 AGENTS.md와 AdaptiveEcosystem/Docs/조연우/README.md를 먼저 읽어줘. 나는 조연우이고 Social·감각·동물 표현 통합을 맡아. 현재 Git 브랜치/HEAD/작업 트리와 PR #11의 상태를 확인한 뒤, 연결된 최신 문서와 Source를 대조해서 완료 범위·다음 연결·담당 경계를 파악해줘. 과거 문서의 Pending을 현재 opt-in 상태와 혼동하거나 이동 writer/PPO/네트워크를 중복 구현하지 말아줘.

작업 시작 시 `git status`, 현재 브랜치/HEAD, 필요한 Source와 계약을 확인하고 다른 작업자의 변경을 보존한다. 에셋 수정은 기존 재생성 도구와 Unreal MCP/컴퓨터 사용 절차를 확인한다. 최근 사용자는 테스트 후 **Unreal Editor만 종료**하도록 요청했으며 PC 종료로 확대하지 않는다.

C++/빌드 입력을 바꾸면 루트 AGENTS.md의 직접 UBT 및 실행 프로세스 확인 규칙을 따른다. 문서만 바꾸면 링크·Source 근거·diff를 검증하고 새 게임 테스트를 했다고 기록하지 않는다. 이 README도 진행에 따라 구현 기준 커밋·검증 범위·미연결 항목을 갱신한다.
