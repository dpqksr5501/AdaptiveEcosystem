# AdaptiveEcosystem Documentation Hub

AdaptiveEcosystem 프로젝트의 전체 기술 문서 및 사양서 허브입니다.  
본 프로젝트는 **MassEntity 기반 동적 생태계 + Python PPO 학습 + Unreal C++ Policy Inference + MassFlock 조향** 구조로 동작합니다.

---

## 📚 카테고리별 문서 목차

### 1. Architecture (아키텍처)
시스템의 최상위 계층 구조, 닫힌 생태계 피드백 루프 및 설계 배경을 다룹니다.
- 📘 [PPO_MASS_ECOSYSTEM_ARCHITECTURE.md](Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md) : 동적 생태계 최신 종합 아키텍처 및 데이터 흐름 명세서
- 📖 [아키텍처_설명.md](Architecture/아키텍처_설명.md) : 계층 분리 원칙과 시스템 설계 철학 상세 해설

### 2. RL & Policy (강화학습 및 정책 계약)
개체 행동 정책(PPO), 관측/행동 사양 및 Python 학습 파이프라인을 다룹니다.
- 📋 [POLICY_CONTRACT_V1.md](RL_Policy/POLICY_CONTRACT_V1.md) : 7차원 관측 / 4차원 행동 정규화 계약, 신경망 구조($7 \to 64 \to 64 \to 4$) 및 Utility Baseline 규격
- 🧪 [RL_TRAINING_PIPELINE.md](RL_Policy/RL_TRAINING_PIPELINE.md) : Python Aquarium 다중 에이전트 어댑터, SB3 PPO 학습, 골든 벡터 검증 파이프라인

### 3. Mass Entity (대규모 개체 시뮬레이션)
수천 마리의 논리 개체 처리, 조향력 합성 및 멀티스레드 병렬 안전성을 다룹니다.
- ⚙️ [MASS_PROCESSOR_ORDER.md](Mass/MASS_PROCESSOR_ORDER.md) : 10단계 Mass 프로세서 명시적 실행 순서 및 병렬 처리 안전 수칙

### 4. Integration (외부 오픈소스 연동)
외부 검증된 프레임워크의 참조 적응 및 라이선스 고지를 다룹니다.
- 🔌 [THIRD_PARTY_INTEGRATION.md](Integration/THIRD_PARTY_INTEGRATION.md) : MassFlock, Aquarium 오픈소스 적응 전략 및 연동 방안
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

### 8. 초기 문서 (기반 문서 및 히스토리)
프로젝트 초기 부트스트랩 단계에서 수립된 불변 원칙과 개발 이력을 보존합니다.
- 🏛️ [01_기반_아키텍처_및_Mass설계.md](초기%20문서/01_기반_아키텍처_및_Mass설계.md) : World vs Server vs Creature 3대 계층 경계 및 Mass 기본 설계
- 🔑 [02_영속식별자_및_초기데이터계약.md](초기%20문서/02_영속식별자_및_초기데이터계약.md) : `StableAgentId`, `RegionId`, `SpeciesId` 등 영속 식별자 계약
- 📦 [03_에셋_감사_보고서.md](초기%20문서/03_에셋_감사_보고서.md) : `Content/` 폴더 내 필수 보존 에셋 및 템플릿 삭제 후보 분류표
- 📜 [04_부트스트랩_히스토리_및_역할.md](초기%20문서/04_부트스트랩_히스토리_및_역할.md) : 1·2차 부트스트랩 안정화 진행 이력 및 팀 역할 분담

### 7. Social Behavior & Shelter (사회적 행동 및 은신처 런타임)
동적 무리(Herd), 위험 전파(Alarm), 은신처(Shelter) 예약 및 PPO 행동 변조를 다룹니다.
- 📌 [조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md](조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md) : **현재 소셜 런타임 구현 및 에디터 검증 현황 (Source of Truth)**
- 📘 [조연우/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md](조연우/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md) : 사회적 행동 및 은신처 시스템 아키텍처 명세서
- 📋 [조연우/SHELTER_COVER_MVP_AGENT_PROMPT.md](조연우/SHELTER_COVER_MVP_AGENT_PROMPT.md) : 차기 은신처(Shelter/Cover) MVP 작업 명세서

---

## 🎯 추천 읽기 순서
1. [Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md](Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md) (전체 그림 파악)
2. [RL_Policy/POLICY_CONTRACT_V1.md](RL_Policy/POLICY_CONTRACT_V1.md) (관측 및 행동 계약 이해)
3. [Mass/MASS_PROCESSOR_ORDER.md](Mass/MASS_PROCESSOR_ORDER.md) (Mass 실행 흐름 이해)
4. [Network/MASS_NETWORK_AUTHORITY_CONTRACT.md](Network/MASS_NETWORK_AUTHORITY_CONTRACT.md) (멀티플레이 권위와 복제 경계 이해)
5. [Roadmap/README.md](Roadmap/README.md) (MVP Milestone 순서 확인)
6. [Migration/AdaptiveEcosystem_PPO_Mass_Migration_Agent_Prompt.md](Migration/AdaptiveEcosystem_PPO_Mass_Migration_Agent_Prompt.md) (상세 전환 계획 확인)
