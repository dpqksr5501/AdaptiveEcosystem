# AGENTS.md — AdaptiveEcosystem Root AI Guidelines

이 문서는 `AdaptiveEcosystem` 저장소에서 작업하는 모든 AI coding agent의 최상위 지침이다.

---

## 1. 프로젝트 기준 정보

- **실제 Unreal Engine 프로젝트 루트**: `AdaptiveEcosystem/` (`AdaptiveEcosystem/AdaptiveEcosystem.uproject`)
- **표준 엔진 버전**: **Unreal Engine 5.8**
- **모듈 구조**: 단일 런타임 모듈 `AdaptiveEcosystem` (`AdaptiveEcosystem/Source/AdaptiveEcosystem/`)
- **설계 및 참조 문서 위치**:
  - `AdaptiveEcosystem/Docs/초기설정/`: 아키텍처, 데이터 계약, 역할 정의 문서
  - `AdaptiveEcosystem/Docs/초기설정2/`: 부트스트랩 안정화 작업 지침

---

## 2. 필수 준수 원칙

1. **Server가 최종 권위(Authority)다**:
   - 논리적 생태계 상태, 개체군, 자원, 에너지, 환경 압력, 확정된 진화 프로필(`FSpeciesEvolutionProfile`)은 Server/Standalone World에만 존재한다.
   - Client는 복제된 Actor 및 요약(Summary) DTO만 수신한다.
2. **AI / LLM은 제안(Proposal)만 생성한다**:
   - LLM 및 Policy AI는 `FEvolutionProposal` 또는 `FSimulationPolicyProposal`과 같은 구조화된 제안만 반환한다.
   - AI가 Unreal Actor, Mass Entity, 게임 상태를 직접 수정(Mutate)하는 것은 엄격히 금지된다.
   - 모든 제안은 Server-side Validator(`EvolutionValidator`)를 통과한 뒤에만 커밋된다.
3. **실제 LLM Blocking Inference 금지**:
   - Game Thread를 차단하는 동기식 LLM 추론을 만들지 않는다.
   - `IEvolutionDecisionProvider::RequestProposal`은 Rule-based/더미 fallback용이며, 실제 LLM은 비동기 Worker/Task 및 결과 큐를 통해 통합한다.
4. **Subsystem은 Replication Transport가 아니다**:
   - `UEcologyServerSubsystem`, `UEcologyWorldSubsystem` 등의 `UWorldSubsystem`은 로컬 서비스 관리자이며 직접 네트워크 복제 프로퍼티나 RPC를 갖지 않는다.
   - 복제는 `AGameStateBase` 파생 클래스 또는 명시적인 Replicated Actor/Component를 통해 수행한다.
5. **책임 경계 (Layer Boundaries)**:
   - **World**: 지리적 공간, 환경 파라미터(`FRegionEnvironmentState`), 스폰 영역을 제공하며, 진화나 개체군을 결정하지 않는다.
   - **Server / Ecology**: 서버 권위 상태, 플레이어 압력 집계, 대규모 논리 시뮬레이션(Mass), 상태 커밋을 담당한다.
   - **Creature Runtime**: 확정된 프로필(`FSpeciesEvolutionProfile`)을 받아 외형(스케일, 메시, 머티리얼) 및 행동(이동속도, AI 성향)으로 표현할 뿐, 진화의 이유나 서버 내부 상태를 알지 못한다.
6. **영속 ID 식별 원칙**:
   - Mass Entity handle, Actor pointer, ISM instance index는 외부 영속 ID가 아니다.
   - 장기 논리 ID는 `StableAgentId` (`int64`), `RegionId` (`FName`), `SpeciesId` (`FName`), `WorldEpoch` / `ProfileRevision`을 사용한다.
7. **과도한 임의 리팩터링 금지**:
   - 팀 합의 없이 대규모 디렉터리 이동, 임의 플러그인 추출, 템플릿 에셋 일괄 삭제를 수행하지 않는다.

---

## 3. 작업 전/후 확인 절차

1. 소스 수정 전 항상 기존 C++ 계약(`Source/AdaptiveEcosystem/Core/EcoDataContracts.h`) 및 문서를 확인한다.
2. 컴파일 안전성을 유지하며, 변경 후 반드시 UnrealBuildTool(`AdaptiveEcosystemEditor Win64 Development`) 빌드를 수행하여 검증한다.
