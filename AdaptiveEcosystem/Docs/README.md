# AdaptiveEcosystem Documentation Hub

AdaptiveEcosystem 프로젝트의 전체 기술 문서 및 사양서 허브입니다.  
최종 목표는 **MassEntity 기반 동적 생태계 + Python PPO 학습 + Unreal C++ Native Inference + Social Runtime + Steering/Movement의 폐루프**입니다. 현재 main `295ac2f`(2026-09-30 감사)에는 M3 관찰 경로와 PPO/Social/표현 구현이 있지만 전체 production 연결은 진행 중입니다. MassFlock/Aquarium은 초기 설계 참조이며, 현재 PPO는 `herbivore_rl/`과 자체 격자·조향을 사용합니다.

---

## 📚 카테고리별 문서 목차

### 1. Architecture (아키텍처)
시스템의 최상위 계층 구조, 닫힌 생태계 피드백 루프 및 설계 배경을 다룹니다.
- 📘 [PPO_MASS_ECOSYSTEM_ARCHITECTURE.md](Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md) : 동적 생태계 최신 종합 아키텍처 및 데이터 흐름 명세서
- 📘 [ACTIVE_RUNTIME_BOUNDARIES.md](Architecture/ACTIVE_RUNTIME_BOUNDARIES.md) : 활성 계약·상태 소유권·Legacy 경계
- 📘 [COLLABORATOR_ECOSYSTEM_INTEGRATION_PLAN.md](Architecture/COLLABORATOR_ECOSYSTEM_INTEGRATION_PLAN.md) : 역할별 통합 계획과 과거 분석의 최신 main 대조
- 📖 [아키텍처_설명.md](Architecture/아키텍처_설명.md) : **Historical / Legacy** 설계 배경. 현재 runtime 완료 상태의 근거로 사용하지 않음

### 2. RL & Policy (강화학습 및 정책 계약)
개체 행동 정책(PPO), 관측/행동 사양 및 Python 학습 파이프라인을 다룹니다.
- 📋 [POLICY_CONTRACT_V1.md](RL_Policy/POLICY_CONTRACT_V1.md) : 7차원 관측 / 4차원 행동 정규화 계약, 신경망 구조($7 \to 64 \to 64 \to 4$) 및 Utility Baseline 규격
- 🧪 [RL_TRAINING_PIPELINE.md](RL_Policy/RL_TRAINING_PIPELINE.md) : 초기 Aquarium/Tools/RL 파이프라인 설계. 현재 학습 구현은 아래 herbivore_rl 요약과 정책 통합 문서 참고
- ✅ [POLICY_TEST_AND_API_GUIDE.md](RL_Policy/POLICY_TEST_AND_API_GUIDE.md) : 테스트 레벨에서 확인할 것, 열어 둔 값, 다른 시스템이 연결할 API
- 🔧 [UNREAL_POLICY_INTEGRATION.md](RL_Policy/UNREAL_POLICY_INTEGRATION.md) : 파이썬 → 언리얼 정책 통합의 빌드·검증·가중치 갱신 절차와 구현 세부
- 🐍 [herbivore_rl/docs/PROJECT_SUMMARY.md](../../herbivore_rl/docs/PROJECT_SUMMARY.md) : 파이썬 학습 환경·PPO 학습·평가의 전체 과정과 결과

### 3. Mass Entity (대규모 개체 시뮬레이션)
수천 마리의 논리 개체 처리, 조향력 합성 및 멀티스레드 병렬 안전성을 다룹니다.
- ⚙️ [MASS_PROCESSOR_ORDER.md](Mass/MASS_PROCESSOR_ORDER.md) : 목표 파이프라인과 현재 M3/PPO/Social 실행 경로·writer 분리·병렬 안전 수칙

### 4. Integration (외부 오픈소스 연동)
외부 검증된 프레임워크의 참조 적응 및 라이선스 고지를 다룹니다.
- 🔌 [THIRD_PARTY_INTEGRATION.md](Integration/THIRD_PARTY_INTEGRATION.md) : 실제 사용·설계 참조·future candidate와 과거 적응 계획 구분
- 📜 [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md) : 루트 오픈소스 라이선스 고지서

### 5. Migration (마이그레이션 로드맵)
기존 Server+LLM 구조에서 PPO+Mass 구조로의 단계별 전환 마스터 가이드를 다룹니다.
- 🗺️ [AdaptiveEcosystem_PPO_Mass_Migration_Agent_Prompt.md](Migration/AdaptiveEcosystem_PPO_Mass_Migration_Agent_Prompt.md) : PR별 단계별 전환 계획 및 완료 기준(DoD)

### 6. Network (멀티플레이 권위 계약)
Steam Session과 MassEntity 멀티플레이의 권위 및 복제 경계를 다룹니다.
- 🌐 [MASS_NETWORK_AUTHORITY_CONTRACT.md](Network/MASS_NETWORK_AUTHORITY_CONTRACT.md) : Listen Server, Client Mass 프록시, Region Summary와 상태 소유권 계약

### 7. Roadmap (MVP Milestones)
PPO + Mass 생태계와 Steam 멀티플레이를 단계별로 완성하기 위한 MVP 로드맵입니다.
- 🧭 [Roadmap/README.md](Roadmap/README.md) : 방향성 검증 결과, Milestone 순서 및 MVP 완료 기준
- 📌 [M3 구현 현황](Roadmap/M3/M3_IMPLEMENTATION_SUMMARY.md) / [검증 기록](Roadmap/M3/M3_VALIDATION_REPORT.md) : Food/스폰/고갈 이주의 실제 구현과 미실행 항목. M3 전체 생명주기 폐루프 완료와 구분

### 8. 초기 문서 (기반 문서 및 히스토리)
프로젝트 초기 부트스트랩 단계에서 수립된 불변 원칙과 개발 이력을 보존합니다.
- 🏛️ [01_기반_아키텍처_및_Mass설계.md](초기%20문서/01_기반_아키텍처_및_Mass설계.md) : World vs Server vs Creature 3대 계층 경계 및 Mass 기본 설계
- 🔑 [02_영속식별자_및_초기데이터계약.md](초기%20문서/02_영속식별자_및_초기데이터계약.md) : `StableAgentId`, `RegionId`, `SpeciesId` 등 영속 식별자 계약
- 📦 [03_에셋_감사_보고서.md](초기%20문서/03_에셋_감사_보고서.md) : `Content/` 폴더 내 필수 보존 에셋 및 템플릿 삭제 후보 분류표
- 📜 [04_부트스트랩_히스토리_및_역할.md](초기%20문서/04_부트스트랩_히스토리_및_역할.md) : 1·2차 부트스트랩 안정화 진행 이력 및 팀 역할 분담

### 9. Social Behavior & Shelter (사회적 행동 및 은신처 런타임)
동적 무리(Herd), 위험 전파(Alarm), 은신처(Shelter) 예약 및 PPO 행동 변조를 다룹니다.
- 📌 [조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md](조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md) : **현재 소셜 런타임 구현 및 에디터 검증 현황 (Source of Truth)**
- 🔗 [조연우/SOCIAL_THREAT_ALARM_INTEGRATION.md](조연우/SOCIAL_THREAT_ALARM_INTEGRATION.md) : 실제 포식자/플레이어 위협 → Herd Alarm 구현, 입력 종료 계약, 자동화 검증과 JYU 설정
- 🔗 [조연우/SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md](조연우/SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md) : Social Request/Feedback 인계, Moving/Occupied·예약 유지/정리, 이동 담당자 연결 지점과 검증 범위
- 📘 [조연우/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md](조연우/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md) : 사회적 행동 및 은신처 시스템 아키텍처 명세서
- 📋 [조연우/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md](조연우/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md) : **CURRENT PRIORITY / TASK 4 — Production Integration** 및 과거 MVP 설계
- 📋 [조연우/SHELTER_COVER_MVP_AGENT_PROMPT.md](조연우/SHELTER_COVER_MVP_AGENT_PROMPT.md) : **Historical** Shelter MVP 작업 범위. 현재 다음 작업 지시가 아님

**Herd != Flock**. Policy가 Raw Action을 생성하고 Social이 ModulatedAction/TargetPosition을 제공하며, Movement 담당이 실제 이동을 실행하는 것이 목표입니다. 현재 production handoff는 미통합입니다.

---

## 🎯 추천 읽기 순서
1. [Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md](Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md) (전체 그림 파악)
2. [Architecture/ACTIVE_RUNTIME_BOUNDARIES.md](Architecture/ACTIVE_RUNTIME_BOUNDARIES.md) (활성 계약·Source of Truth)
3. [RL_Policy/POLICY_CONTRACT_V1.md](RL_Policy/POLICY_CONTRACT_V1.md) (7→4 계약과 알려진 수치 충돌 확인)
4. [조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md](조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md) (main 구현·기존 검증·현재 통합 공백)
5. [Architecture/COLLABORATOR_ECOSYSTEM_INTEGRATION_PLAN.md](Architecture/COLLABORATOR_ECOSYSTEM_INTEGRATION_PLAN.md) (담당 계층과 통합 계획)
6. [Mass/MASS_PROCESSOR_ORDER.md](Mass/MASS_PROCESSOR_ORDER.md) (실제 실행 경로와 목표 순서 구분)
7. [Network/MASS_NETWORK_AUTHORITY_CONTRACT.md](Network/MASS_NETWORK_AUTHORITY_CONTRACT.md) (멀티플레이 권위·복제 경계)
8. [Roadmap/README.md](Roadmap/README.md) 및 M3 구현/검증 기록 (Milestone 목표와 현재 증거)
9. [조연우/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md](조연우/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md) (Social TASK 4 작업)

Coding Agent는 먼저 루트 [AGENTS.md](../../AGENTS.md)를 읽습니다. 현재 Source가 구현 사실의 기준이며, 설계/과거 문서와 충돌하면 차이를 보고하고 검증 전 완료로 기록하지 않습니다.
