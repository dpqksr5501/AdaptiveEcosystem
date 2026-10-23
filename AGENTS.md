# AGENTS.md — AdaptiveEcosystem Root AI Guidelines

이 문서는 `AdaptiveEcosystem` 저장소에서 작업하는 모든 AI coding agent의 최상위 지침이다.

## 0. 모든 팀원과 AI agent의 공통 맥락

새 채팅/독립 작업을 시작할 때 [프로젝트 공통 맥락](AdaptiveEcosystem/Docs/PROJECT_CONTEXT.md)을 먼저 읽고 실제 branch/Source와 담당 계약을 확인한다. 이 문서는 목표·현재 구현·후속 제안을 구분하는 공통 진입점이다. 환경·식생·몬스터 간 상호작용·플레이어 활동이 함께 작동하는 MMORPG용 동적 생태계를 목표로 하며, 플레이어 영향만의 시스템이나 관찰 전용으로 축소하지 않는다. 사슴·늑대는 현재 예시이고 종의 식성/공격성/사회성/이동 능력/실행 backend를 분리해 확장한다. 현재 Native 늑대 구현이 임의 몬스터를 이미 지원한다는 뜻은 아니다. 세부 제안은 [고도화 기획](AdaptiveEcosystem/Docs/Architecture/DYNAMIC_ECOSYSTEM_DETAILED_DESIGN_20261023.md)을 참고하며, 현재 요청 범위를 넘어 기능을 일괄 활성화하지 않는다.

---

## 1. 프로젝트 기준 정보

- **실제 Unreal Engine 프로젝트 루트**: `AdaptiveEcosystem/` (`AdaptiveEcosystem/AdaptiveEcosystem.uproject`)
- **표준 엔진 버전**: **Unreal Engine 5.8**
- **핵심 목표**: **MassEntity 기반 동적 생태계 + Python PPO 학습 + Unreal C++ Policy Inference + Social Runtime + 단일 Steering/Movement 경로의 폐루프 통합**
- **모듈 구조**: 단일 런타임 모듈 `AdaptiveEcosystem` (`AdaptiveEcosystem/Source/AdaptiveEcosystem/`)
- **설계 및 참조 문서 위치**:
  - `AdaptiveEcosystem/Docs/Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md`: 동적 생태계 최신 아키텍처 정의서
  - `AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V1.md`: PPO 관측/행동 사양 및 정규화 계약서
  - `AdaptiveEcosystem/Docs/Mass/MASS_PROCESSOR_ORDER.md`: Mass Processor 실행 순서 및 스레드 안전성
  - `AdaptiveEcosystem/Docs/조연우/README.md`: 조연우 역할·최신 진행상황·다른 채팅의 작업 재개를 위한 시작 문서
  - `AdaptiveEcosystem/Docs/조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md`: Social의 현재 main 구현·검증 범위와 Production Integration 우선순위
  - `AdaptiveEcosystem/Docs/조연우/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md`: Herd / Alarm / Shelter 책임 경계
  - `AdaptiveEcosystem/Docs/조연우/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md`: 현재 TASK 4 통합 작업과 과거 MVP 구현 가이드
  - `AdaptiveEcosystem/Docs/조연우/SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md`: Social 이동 Request/Feedback·예약 상태/유지/정리 계약 및 소비자 연결 지점
  - `AdaptiveEcosystem/Docs/RL_Policy/RL_TRAINING_PIPELINE.md`: Python 학습 환경 및 Export 파이프라인
  - `AdaptiveEcosystem/Docs/Migration/AdaptiveEcosystem_PPO_Mass_Migration_Agent_Prompt.md`: 전환 마스터 가이드라인
  - `AdaptiveEcosystem/Docs/초기 문서/`: 초기 기반 아키텍처, 영속 식별자 계약, 에셋 감사 및 부트스트랩 히스토리

---

## 2. 필수 준수 원칙

1. **동적 생태계 폐루프(Feedback Loop)가 본체다**:
   - 시스템의 성공 기준은 단순 PPO 이동이 아닌, 환경/플레이어 압력에 의해 지역 생태 상태(`FRegionEcologyState`)가 변하고, 개체 관측 및 PPO 행동이 달라지며, 먹이 소비·생존·피식·사망·이주 결과가 다시 자원(`FoodAmount`)과 개체군(`Population`)을 변화시키는 닫힌 루프의 완성이다.
2. **Server / Standalone World가 최종 권위(Authority)다**:
   - 논리적 생태계 상태, 자원 잔여량, 피식 기록(`PredationHistory`), Mass Entity 논리 상태는 Server / Standalone World에만 존재한다.
   - Client는 요약(Summary) DTO 및 시각적 표현(Actor)만 수신한다.
3. **PPO Policy는 Shared Model, Per-Agent Observation으로 동작한다**:
   - 모든 개체는 하나의 학습된 가중치 네트워크(7 → 64 → 64 → 4)를 공유하며, 각자의 개별 관측(`FEcoObservationFragment`)을 입력받아 개별 행동 가중치(`FEcoPolicyOutputFragment`)를 출력한다.
   - PPO 출력(forage, cohesion, flee_dist, cover)은 절대 `Shared Fragment`에 저장하지 않고 개체별 `Entity Fragment`에 저장하여 Archetype churn을 방지한다.
4. **Unreal C++ Native Deterministic Inference**:
   - 게임 런타임에 Python 인터프리터를 내장하거나 Game Thread를 블로킹하는 외부 프로세스 추론을 일절 사용하지 않는다.
   - Python에서 학습/익스포트된 가중치(Weights & Biases)를 C++ Native 계산 함수로 직접 고속 추론한다.
5. **Sim-to-Sim 파리티(Parity) 준수**:
   - 실제 Python 학습 환경(`herbivore_rl/`)과 C++ 관측의 순서, 정규화 공식, 클램프 범위, 행동(4개) 역매핑 공식은 `AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V1.md`와 대조하고 Golden Vector 테스트로 검증한다. Aquarium은 초기 설계 참조다. 현재 생성 상수/Utility/조향과 V1 문서 간 알려진 차이는 보고하며, 문서 감사 중 가중치나 수치를 임의 변경하지 않는다.
6. **Subsystem은 Replication Transport가 아니다**:
   - `UEcologySimulationSubsystem`, `UEcologyWorldSubsystem` 등은 로컬 서비스 관리자이며 직접 네트워크 프로퍼티나 RPC를 갖지 않는다.
7. **책임 경계 (Layer Boundaries)**:
   - **World**: 지리적 경계(`AEcologyRegion`), 날씨/낮밤 물리 환경(`FRegionEnvironmentState`) 제공.
   - **Ecology Simulation**: 생태계 총괄 관리(`UEcologySimulationSubsystem`), 지역 자원(`FoodAmount`), 피식 기록(`PredationHistory`), 개체군 집계 관리.
   - **Mass Logical Creatures**: 대규모 개체 생명주기(Vitals, Travel, Observation, Policy, Steering, Lifecycle). 단일 진실값(Source of Truth).
   - **Behavior Policy**: 개체별 `FEcoPolicyOutputFragment::Action`에 Raw Action을 생성. PPO 관측/행동/학습/가중치는 RL 담당 영역.
   - **Social Behavior Runtime**: Persistent Herd, 가입/이탈·집계, Alarm 전파·감쇠, Shelter 차폐/평가·슬롯 예약·해제와 행동 의도 보정. Raw Action을 읽어 `FEcoSocialBehaviorFragment::ModulatedAction`과 `FEcoShelterIntentFragment::TargetPosition`을 제공한다. Vitals/지역 자원/복제 transport/실제 위치 적분의 소유자가 아니다.
   - **Steering / Movement**: Social 의도를 받아 실제 경로·조향·위치/속도 갱신을 실행하는 담당 계층. **Herd != Flock**: Herd는 지속적인 논리적 무리, Flock은 실제 이동 행동이다.
   - **Creature Representation**: Mass 개체의 시각화(Mesh, Anim, Collision, Actor). 논리 상태의 주인이 아님.
8. **영속 ID 및 런타임 식별 원칙**:
   - 장기 식별: `StableAgentId` (`int64`), `RegionId` (`FName`), `SpeciesId` (`FName`).
   - Mass Hot-path: `RegionRuntimeIndex`, `SpeciesRuntimeIndex` 등 compact index 활용.
9. **Legacy LLM Trait Evolution 분리**:
   - 기존의 세대별 바디스케일 변형, LLM Proposal/Validator 기반 Trait Evolution 코드는 신규 동적 생태계 경로에 영향을 주지 않도록 격리하며, 신규 코드가 이를 의존하지 않는다.
10. **구현 사실과 목표 설계를 구분한다**:
   - 구현 상태는 현재 컴파일 가능한 Source를 최종 사실 기준으로 확인하고, Root AGENTS.md의 불변 원칙·Active Contract·기타 설계를 순서대로 대조한다. Source와 계약의 충돌은 기록하며 현재 동작을 의도한 계약처럼 조용히 정당화하지 않는다.
   - 목표는 `Policy Raw Action → Social ModulatedAction / TargetPosition → Steering / Movement`다. 2026-09-30 main `295ac2f`의 Steering은 아직 Raw Action과 Dummy Cover를 사용한다. M3 Box Bootstrap은 PPO Herbivore/Custom Movement 혼용을 거부한다. 이 가드를 제거하거나 Trait를 합치기 전에 단일 movement writer와 인계 계약을 정한다.
   - Social의 현재 단계는 Production Integration이다. `codex/social-threat-integration`은 기존 포식자 Grid/Actor ThreatSource를 읽는 감지→Alarm을 추가했다. 계약/검증은 `Docs/조연우/SOCIAL_THREAT_ALARM_INTEGRATION.md`를 따른다. production EntityConfig/JYU/Client 확인 후 행동·목적지 인계, 도착/점유 및 생명주기 예약 정리를 연결한다. Merge/Split, multi-hop gossip, ORCA, 자동 Cover 생성은 Deferred다.
   - `codex/social-shelter-handoff`는 `9461ae7` 기반으로 Social Request/Feedback과 Moving/Occupied·lease·실패/죽음/삭제/이주 정리를 구현했다. 계약은 `Docs/조연우/SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md`를 따른다. 실제 이동 writer 소비와 JYU 이동/도착·Client 검증은 대기다. Social에 Transform/Velocity 적분을 추가하거나 기존 Bootstrap 가드를 제거하지 않는다.

---

## 3. 작업 전/후 확인 절차

1. 소스 수정 전 항상 핵심 계약(`Source/AdaptiveEcosystem/Core/`, `AI/Policy/`, `Mass/`)을 확인한다.
2. Social 작업은 CURRENT_STATE의 기준 commit·검증 범위를 확인하고, production Entity 구성과 Server/Standalone 실행 조건을 먼저 대조한다. 설계 문서의 예시 Processor를 구현 완료로 간주하지 않는다.
3. C++/빌드 입력 변경 후 직접 `UnrealBuildTool.exe`로 `AdaptiveEcosystemEditor Win64 Development` 빌드를 실행하고 완료까지 기다린다. UBT, dotnet, Unreal Editor, Live Coding, MSBuild, ShaderCompileWorker가 실행 중이면 새 빌드를 시작하거나 실행 중 빌드를 중단하지 않는다. dotnet 예외 창은 최초 UBT/compiler 오류와 Windows Application Event Log를 확인한 뒤 판단한다.
4. 문서만 변경한 경우 링크·Source 근거·diff를 검증하고 새 UBT/PIE 검증을 했다고 기록하지 않는다. 코드 변경이 포함되면 위 빌드 규칙을 적용한다.


## 4. 2026-10-15 opt-in M4/v3 통합 경로

`codex/m4-v3-creature-integration`의 별도 `/Game/JYU/Maps/LV_JYU_V3Integration`은 M4 공통 권위·identity/lifecycle/resource/replication을 권신혁 Native v3 **R1b 18관측/5행동·mask2**에 연결한다. 이는 기본 V1 7관측/4출력을 변경하는 경로가 아니다. v3의 단일 Native movement/vitals writer를 유지하고 V1/Custom Movement 혼용 가드를 제거하지 않는다. Client는 수신 표현만 수행하며 런타임 Python 추론은 금지한다. 원본 팀 레벨 대신 복사 맵·owned 에셋에 authoring한다.

실제 계약·검증 범위·known gap은 [JYU M4/v3 통합 기록](AdaptiveEcosystem/Docs/조연우/JYU_M4_V3_INTEGRATION.md)과 [IK 검증](AdaptiveEcosystem/Docs/조연우/JYU_IK_VALIDATION.md)을 따른다. v3 Social ModulatedAction/slot arrival feedback·migration/wave는 연결 완료로 간주하지 않는다. 기존 V1 handoff를 보존한다. 단일 runtime 모듈은 유지하며 AnimGraph authoring만 별도 `AdaptiveEcosystemEditor` Editor 모듈로 분리했다.


## 5. 2026-10-16 작업 위치 통합

검증 커밋 `8e2f34f`의 M4/v3/JYU 구현은 기존 `codex/social-shelter-handoff`와 원래 저장소 폴더로 반영했다. 앞으로 원래 `AdaptiveEcosystem/AdaptiveEcosystem.uproject`를 사용한다. 복사 맵 `/Game/JYU/Maps/LV_JYU_V3Integration`과 원본 팀 레벨의 분리는 유지한다. 4절의 브랜치명은 최초 구현 이력이다. 세부 보존·재검증·worktree 정리는 [작업 위치 통합 기록](AdaptiveEcosystem/Docs/조연우/JYU_WORKTREE_RETURN_20261016.md)을 따른다.

UBT는 프로젝트 외부 엔진 캐시에도 쓰므로 필요한 쓰기 권한이 있는 승인된 실행 환경에서 시작한다. 권한 오류로 시작한 빌드를 임의 중단하거나 중복 실행하지 않는다. 2026-10-16의 중단 허용은 사용자가 특정 실패 실행 1회에만 허용한 예외이며 지속적인 예외가 아니다.


## 6. 2026-10-16 v3 감지·야생 규칙 추가 통합

기존 통합본 위에 권신혁 `origin/Branch_Sinhyeok` `3916496`의 후속 16개 커밋을 반영했다. `RL_V3_WILD1_SPEC.md`의 시야·청각·도주·비축·포만 규칙을 사용하지만 R1b 내장 학습 가중치와 V1 계약은 그대로다. `request`(PPO)와 `flight_override`(세계 규칙), `executed`(실제 행동)를 구분한다. MassFlock은 외부 패키지 도입 완료가 아닌 설계 참조이며 실제 이웃·조향은 자체 구현이다. v3의 경보 소음/표현과 Native `kin_alarm`은 Social Persistent Herd→ModulatedAction 연결 완료를 뜻하지 않는다. 정확한 활성 backend·검증·남은 연결은 [위협·backend 감사](AdaptiveEcosystem/Docs/조연우/JYU_THREAT_AND_BACKEND_AUDIT_20261016.md)를 따른다.

## 7. 2026-10-16 v3 실제 Social 행동·슬롯 인계

권신혁 최신 `b5c7384`(Wild1 검증 자료)와 원준 M4 `67c860c`를 포함한 기존 브랜치에서 v3 Social 연결을 추가했다. 2절 10항·4절·6절의 미연결 설명은 당시 이력이며 현재 범위는 [v3 Social 인계 계약과 검증](AdaptiveEcosystem/Docs/조연우/JYU_V3_SOCIAL_HANDOFF.md)을 따른다.

실제 경로는 Native 직접 감지/Player.Footstep → 별도 Herd observed 채널 → 기존 Alarm/SocialResponse → Shelter Request → Native control hook → 단일 이동/섭식/대사 → 실제 body 위치의 Feedback → 점유/예약 정리다. v3 요청을 Social 선호로 명시적으로 projection하며 V1 PPO 출력이나 v3 Raw Request를 덮어쓰지 않는다. Shared 기억을 직접 관측으로 재발행하지 않고, 이동 소비자도 lease/slot/안전 방향을 확인한다. 기존 V1 경로와 Bootstrap 가드는 유지한다.

직접 UBT 성공, 자동화 140개(139 Success + 1 예상 저장 파일 warning, 실패 0), 복사 맵 일반 PIE 및 Dedicated+Client 2개를 검증했다. 실제 Moving→Occupied와 Client 논리 개체/Native Step 0을 확인했다. migration/wave 활성화·외부 MassFlock 설치·NavMesh 전환·재학습은 이번 작업 범위가 아니다. 사용자 변경 에셋 68개는 원본 바이트를 보존하고 이번 코드 커밋에서 제외했다.

후속 [근접 장면 진단](AdaptiveEcosystem/Docs/조연우/JYU_THREAT_SCENE_DIAGNOSIS_20261016.md)에서 **은신처 안전 계약 미충족**을 확인했다. 명세의 늑대 진입 금지/안전과 달리 현재 Native cover는 탐지·포획 거리 배수이며 물리적 진입 금지/면역이 아니다. 웅크림 중 포획도 사용자 로그에 있다. 보이는 엄폐물도 자동 배치하지 않는다. 숨기=미감지 또는 완전한 안전이라고 설명하지 않는다. 새 읽기 전용 진단은 Native 감지와 Social 위급 경보를 구분하며, 후속 141개 자동화와 일반 PIE를 검증했다. 이 진단이 세계 규칙 불일치를 해결한 것은 아니다.

## 8. 2026-10-16 실제 보호 은신처

사용자 요청에 따라 새 복사 맵 `/Game/JYU/Maps/LV_JYU_RefugeSafety`에 수풀·바위 Blueprint 은신처 12개를 배치했다. 기존 `LV_JYU_V3Integration`과 사용자 에셋 변경은 보존한다. 통합 v3에서 `eco.IntegratedV3.ProtectedRefuges=1`은 실제 영역의 늑대 swept 이동 차단·내부 사슴 포획 후보 제외·지면 슬롯/실제 도착 검증을 활성화한다. Native 단일 movement writer를 유지한다. 등록 전 외형을 숨기고 지형 준비 후 재시도하며 제거·등록 index 재사용도 처리한다.

이는 Unreal 세계 규칙 확장이며 PPO 가중치나 기본 Python 세계를 변경하지 않았다. Native 기준 설정은 OFF로 유지한다. ON 세계까지 Python 파리티/재학습이 완료됐다고 간주하지 않는다. 실제 계약·검증·에디터 위치는 [보호 은신처 구현 기록](AdaptiveEcosystem/Docs/조연우/JYU_REFUGE_SAFETY_20261016.md)을 따른다. 이전 문서의 “은신처 진입 금지/안전 미구현”은 이 변경 전의 진단이다.

## 9. 개인 발표 자료 저장 위치

사용자 요청에 따라 개인 주간 발표 PPT, 발표 대본, 멘토 검토용 PDF와 제작·렌더·임시 산출물은 **저장소 밖의 바탕화면 `AdaptiveEcosystem_발표자료/`** 아래에 날짜·용도별로 저장한다. 작업 폴더도 그 외부 경로 안에 만든다. 저장소의 `Deliverables/`, `output/`, `tmp/`에는 새 발표 산출물을 생성하거나 추적하지 않는다. 해당 경로는 Git 제외 규칙으로 보호한다.

프로젝트 소스·Unreal 에셋·설계/계약 문서·동작 검증 근거는 기존 저장소 구조를 유지한다. 팀원이 관리하는 기존 `Docs/Roadmap/M3/Presentation` 등 공유 설계 자료는 개인 발표 분리 대상으로 간주하지 않는다. 사용자 개인 발표 파일을 push하거나 공개 이력을 다시 쓰지 않는다.

## 10. 2026-10-22 PR #12 main 후속 통합

`main a74fcac`를 작업 브랜치에 병합했다. 현재 통합 v3의 `eco.IntegratedV3.SocialControl` 기본값은 **0**이며 기존 Social 처리·경보 표현과 Native 행동 개입을 구분한다. 기존 훅의 opt-in 연결은 보존한다. main의 은신처 먹이 규칙으로 늦은 은신처 등록 시 용량·남은 먹이가 변하므로 `AdjustSpatialFoodHabitat` 거래로 권위 장부에 반영하고, 제거 시 용량만 복구하며 먹이를 생성하지 않는다. 기존 자원 보존 검사를 우회하거나 두 번째 이동 writer를 추가하지 않는다. 최신 검증·한계·로컬 병합 상태는 [PR #12 main 통합 기록](AdaptiveEcosystem/Docs/조연우/JYU_PR12_MAIN_INTEGRATION_20261022.md)을 따른다.

## 11. 2026-10-23 신호 계약·무리 이주 통합

PR #14는 2026-10-23 사용자 요청으로 기능·디버그를 push하고 Ready for review로 전환했다. 확인 당시 OPEN·미병합이다. v3 기본 SocialControl=0 신호 경로를 유지하고 `ReadSignal`의 증거/수신 시각·TTL·Herd 일치 계약을 제공한다. opt-in `UEcoHerdMigrationSubsystem`은 완료된 M4 자원 경계에서 Persistent Herd 공동 계획·기존 Travel·실제 Native context 인계·기존 Migration receipt/인구 집계를 연결한다. Native Step이 유일한 이동·대사 writer다. Client는 기존 Bubble 표현만 받는다.

기존 맵의 이주 옵션은 OFF이며 `/Game/JYU/Maps/LV_JYU_HerdMigration`만 ON이다. 팀 JWJ 대형 레벨의 owned 복사 맵이고 Barren↔Forest 지면 경로를 authoring했다. 원본 팀 레벨은 변경하지 않는다. 기본 가중치·V1 계약·Python ON 세계 파리티/재학습을 변경 완료로 간주하지 않는다. 정확한 실행·검증·한계는 [무리 이주와 신호 계약](AdaptiveEcosystem/Docs/조연우/HERD_MIGRATION_AND_SIGNAL_CONTRACT.md)을 따른다. 개발 가뭄 fixture는 명시적으로 실행한 세션에만 적용하며 자연 발생 생태 균형 검증으로 설명하지 않는다.

## 12. 2026-10-23 이주 경로·목적지 디버그

새 이주 맵은 읽기 전용 HUD 지도·실제 Native 개체 위치·선택 계획의 경로/현재 목적지를 표시한다. `M` 토글, `[`/`]` 계획 선택이며 기존 맵/Client의 논리 권위를 확장하지 않는다. snapshot은 Mass processing 외 GameThread에서 만들고 HUD는 4Hz로 읽는다. `Blocked`는 무진행 진단이며 지형 충돌 확정으로 설명하지 않는다. [표시 계약·재현·검증](AdaptiveEcosystem/Docs/조연우/HERD_MIGRATION_DEBUG_20261023.md)을 따른다. 개인 PPT·캡처와 제작 작업은 9절의 저장소 밖 발표자료 폴더에 두며 Git에 넣지 않는다.

## 13. 2026-10-23 최신 재개 기준과 문서 이력

현재 작업 시작점은 [최신 조연우 인수인계](AdaptiveEcosystem/Docs/조연우/JYU_CHAT_HANDOFF_20261023.md)다. 기능 기준 `581ce1d`, 디버그 기준 `e22dbbd`, 통합 main `a74fcac`이며 이후 문서 커밋은 별도 확인한다. 앞 절과 설계 문서의 날짜별 미연결·Pending·Draft·push 전 설명은 당시 이력이다. 현재 기본 `SocialControl=0`, 기존 맵 이주 OFF·새 owned 이주 맵 ON을 유지한다. Native의 단일 이동·대사 writer와 기존 자원/인구/복제 계약을 보존한다.

현재 통합 `ShelterSafe=1`은 Python realism_shelter에 맞춘 Native 안전 규칙, `ProtectedRefuges=1`은 실제 은신처 생명주기다. ShelterSafe=0일 때만 JYU 보호 규칙이 안전을 맡으며 중첩하지 않는다. 8절의 Native 보호 기본 OFF는 하위 `FWorldConfig` 기본값을 의미한다. 기존 안전 기준 세계의 파리티와 새 이주 ON 세계 전체 궤적 파리티/재학습 미완료를 구분한다. V1 7관측/4출력과 opt-in v3 18관측/5행동·mask2를 서로 대체하지 않는다.

사용자의 후속 이동 요청에 따라 최종 개인 PPT `겜캡디_조연우_1023.pptx`는 바탕화면 바로 아래에 있다. 캡처·대본·렌더/제작 작업은 9절의 외부 날짜별 폴더를 유지한다. 개인 파일을 Git에 넣지 않는다. 이번 문서 감사는 Source·링크·diff를 확인하고 새 UBT/PIE를 실행하지 않는다.

## 14. 2026-10-24 soil/life 통합과 팀 AI 작업 진입점

후속 soil/life 구현은 `d095948`에 기록했다. 최신 재개는 [팀 AI 공통 안내](AdaptiveEcosystem/Docs/Team/ECOSYSTEM_AI_COLLABORATION_20261024.md), [현재 구현 상태](AdaptiveEcosystem/Docs/Architecture/ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md), [life 실행 계약](AdaptiveEcosystem/Docs/Architecture/ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md)를 먼저 읽는다. 앞 절의 날짜별 Pending/로컬 미커밋 설명은 당시 이력이다. 새 owned `/Game/JYU/Maps/LV_JYU_Ecosystem`만 soil/life를 opt-in하고 원본 팀 맵·기존 맵 옵션·V1/v3 모델/계약·SocialControl=0·Native 단일 writer와 기존 M4 장부를 보존한다.

서버·네트워킹은 [역할별 안내](AdaptiveEcosystem/Docs/Network/ECOSYSTEM_SERVER_NETWORK_AGENT_GUIDE_20261024.md), 학습은 [역할별 안내](AdaptiveEcosystem/Docs/RL_Policy/ECOSYSTEM_RL_AGENT_GUIDE_20261024.md)를 따른다. 복사 가능한 [작업 시작 프롬프트](AdaptiveEcosystem/Docs/Team/ECOSYSTEM_AGENT_START_PROMPTS_20261024.md)와 [실제 부분 예제](AdaptiveEcosystem/Docs/RL_Policy/Examples/README.md)를 제공한다. 예제는 training_ready=false이며 진단 정답/부분 cell을 기존 정책 관측이나 전체 복원 상태로 사용하지 않는다. 현재 Client proxy와 권위 논리를 구분하고 새 학습/임의 종/분산 서버 완료로 확대하지 않는다.

225개 자동화·PIE/멀티·저장·패키지 수치는2026-10-23 실행의 근거다. 10-24 안내/공유 갱신은 새 UBT/PIE 실행을 뜻하지 않는다. 새 담당자가 코드를 변경하면 기존3절 빌드 규칙과 해당 역할의 실제 acceptance를 적용한다. 다른 PC의 같은 Git SHA라도 checkpoint의 runtime image hash가 달라질 수 있으므로 재빌드 간 자동 복원을 가정하지 않는다.
