# AGENTS.md — AdaptiveEcosystem Root AI Guidelines

이 문서는 `AdaptiveEcosystem` 저장소에서 작업하는 모든 AI coding agent의 최상위 지침이다.

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
