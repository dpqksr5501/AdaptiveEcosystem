# AdaptiveEcosystem

Unreal Engine 5.8 기반 MassEntity 동적 생태계 프로젝트다. Python에서 학습한 PPO 정책을 C++ Native로 추론하고, 환경·자원·개체 행동·피식·지역 이동 결과를 생태계 장부에 연결한다. 서버/Standalone이 논리 권위를 가지며 Client는 기존 복제로 표현을 수신한다.

- **팀원·AI 작업 시작:** [프로젝트 목표와 공통 맥락](AdaptiveEcosystem/Docs/PROJECT_CONTEXT.md)을 먼저 읽고 담당 Source/계약으로 이어간다. 환경·식생·몬스터·플레이어가 함께 만드는 MMORPG용 생태계가 목표이며 사슴·늑대는 현재 검증 예시다.
- 프로젝트: [AdaptiveEcosystem.uproject](AdaptiveEcosystem/AdaptiveEcosystem.uproject). 작업 규칙은 [AGENTS.md](AGENTS.md).
- [아키텍처와 책임 경계](AdaptiveEcosystem/Docs/Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md), [Mass 실행 순서](AdaptiveEcosystem/Docs/Mass/MASS_PROCESSOR_ORDER.md).
- 정책은 [V1 계약](AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V1.md)과 [v3 계약](AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V3.md)을 구분한다. v3 통합이 V1의 관측·행동 사양을 대체하지 않는다. Legacy LLM Trait Evolution은 신규 경로와 분리한다.
- Social·감각·표현·무리 이주의 최신 시작점: [조연우 문서](AdaptiveEcosystem/Docs/조연우/README.md), [2026-10-23 인수인계](AdaptiveEcosystem/Docs/조연우/JYU_CHAT_HANDOFF_20261023.md).
- 이주 확인 맵은 `/Game/JYU/Maps/LV_JYU_HerdMigration`. [실행·기능 계약](AdaptiveEcosystem/Docs/조연우/HERD_MIGRATION_AND_SIGNAL_CONTRACT.md), [지도·경로 디버그 사용법](AdaptiveEcosystem/Docs/조연우/HERD_MIGRATION_DEBUG_20261023.md). 기존 맵에서는 이주가 기본 비활성이다.

개인 발표 자료는 저장소 밖에 보관한다. 테스트 증거의 범위와 미검증 항목은 각 기능 문서를 따른다.
