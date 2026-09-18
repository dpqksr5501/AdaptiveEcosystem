# AGENTS.md — AdaptiveEcosystem Root AI Guidelines

이 문서는 `AdaptiveEcosystem` 저장소에서 작업하는 모든 AI coding agent의 최상위 지침이다.

---

## 1. 프로젝트 기준 정보

- **실제 Unreal Engine 프로젝트 루트**: `AdaptiveEcosystem/` (`AdaptiveEcosystem/AdaptiveEcosystem.uproject`)
- **표준 엔진 버전**: **Unreal Engine 5.8**
- **핵심 목표**: **MassEntity 기반 동적 생태계 + Python PPO 학습 + Unreal C++ Policy Inference + MassFlock 조향**
- **모듈 구조**: 단일 런타임 모듈 `AdaptiveEcosystem` (`AdaptiveEcosystem/Source/AdaptiveEcosystem/`)
- **설계 및 참조 문서 위치**:
  - `AdaptiveEcosystem/Docs/Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md`: 동적 생태계 최신 아키텍처 정의서
  - `AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V1.md`: PPO 관측/행동 사양 및 정규화 계약서
  - `AdaptiveEcosystem/Docs/Mass/MASS_PROCESSOR_ORDER.md`: Mass Processor 실행 순서 및 스레드 안전성
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
   - Python Gym/Aquarium 관측(7개)과 C++ 관측의 순서, 정규화 공식, 클램프 범위, 행동(4개) 역매핑 공식은 `Docs/POLICY_CONTRACT_V1.md`에 완벽히 일치해야 하며 Golden Vector 테스트로 검증한다.
6. **Subsystem은 Replication Transport가 아니다**:
   - `UEcologySimulationSubsystem`, `UEcologyWorldSubsystem` 등은 로컬 서비스 관리자이며 직접 네트워크 프로퍼티나 RPC를 갖지 않는다.
7. **책임 경계 (Layer Boundaries)**:
   - **World**: 지리적 경계(`AEcologyRegion`), 날씨/낮밤 물리 환경(`FRegionEnvironmentState`) 제공.
   - **Ecology Simulation**: 생태계 총괄 관리(`UEcologySimulationSubsystem`), 지역 자원(`FoodAmount`), 피식 기록(`PredationHistory`), 개체군 집계 관리.
   - **Mass Logical Creatures**: 대규모 개체 생명주기(Vitals, Travel, Observation, Policy, Steering, Lifecycle). 단일 진실값(Source of Truth).
   - **Creature Representation**: Mass 개체의 시각화(Mesh, Anim, Collision, Actor). 논리 상태의 주인이 아님.
8. **영속 ID 및 런타임 식별 원칙**:
   - 장기 식별: `StableAgentId` (`int64`), `RegionId` (`FName`), `SpeciesId` (`FName`).
   - Mass Hot-path: `RegionRuntimeIndex`, `SpeciesRuntimeIndex` 등 compact index 활용.
9. **Legacy LLM Trait Evolution 분리**:
   - 기존의 세대별 바디스케일 변형, LLM Proposal/Validator 기반 Trait Evolution 코드는 신규 동적 생태계 경로에 영향을 주지 않도록 격리하며, 신규 코드가 이를 의존하지 않는다.

---

## 3. 작업 전/후 확인 절차

1. 소스 수정 전 항상 핵심 계약(`Source/AdaptiveEcosystem/Core/`, `AI/Policy/`, `Mass/`)을 확인한다.
2. 컴파일 안전성을 최우선으로 유지하며, 변경 후 반드시 UnrealBuildTool(`AdaptiveEcosystemEditor Win64 Development`) 빌드를 수행하여 검증한다.
