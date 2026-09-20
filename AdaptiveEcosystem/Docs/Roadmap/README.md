# AdaptiveEcosystem MVP Milestone Roadmap

> 기준 엔진: **Unreal Engine 5.8**  
> 목표: **Steam 멀티플레이 + Server 권위 Mass 생태계 + PPO 정책의 MVP 완성**

---

## 1. 방향성 검증 결과

현재 프로젝트의 최종 방향을 PPO + MassEntity 동적 생태계로 통일하는 것은 적절하다. Network 경계를 초기에 확정하는 것도 Stable ID, Server/Client Processor, Representation 구조에 영향을 주므로 필요하다.

다만 개발 순서는 다음 원칙을 따른다.

- 전체 Network 기능을 먼저 완성하지 않고, 권위 계약과 최소 복제 수직 슬라이스만 먼저 검증한다.
- Host가 방을 생성하는 초기 MVP는 Steam Lobby/Session 기반 Listen Server로 정의한다.
- Server만 생태계를 계산하고 Client는 관련 범위의 Mass 프록시를 표현한다.
- PPO보다 먼저 Utility Baseline으로 폐루프 Simulation을 완성한다.
- Dedicated Server 전환은 동일한 권위 계약을 유지하는 후속 확장으로 둔다.

---

## 2. Milestone 구성

| Milestone | 목표 | 주요 결과 |
| :---: | :--- | :--- |
| [M0](M0_ARCHITECTURE_AUTHORITY.md) | 아키텍처와 권위 통일 | 단일 상태 소유권과 Network Contract 확정 |
| [M1](M1_STEAM_SESSION_FOUNDATION.md) | Steam 방 생성/참가 | Listen Server 기반 멀티플레이 수직 슬라이스 |
| [M2](M2_MASS_NETWORK_VERTICAL_SLICE.md) | Mass 네트워크 검증 | Server Entity와 Client Mass 프록시 연결 |
| [M3](M3_ECOLOGY_SIMULATION_CORE.md) | 생태 Simulation 본체 | Food, Energy, Death, Migration 폐루프 |
| [M4](M4_REPRESENTATION_INTERACTION.md) | 표현과 상호작용 | Client LOD 표현과 플레이어 포식 피드백 |
| [M5](M5_PPO_CLOSED_LOOP.md) | PPO 정책 통합 | C++ 추론과 전체 생태 피드백 연결 |
| [M6](M6_MVP_VALIDATION.md) | MVP 검증 | 멀티플레이·성능·정합성 통합 검증 |

Milestone은 선행 단계의 완료 조건을 만족한 뒤 진행한다. 각 문서는 세부 클래스 구현서가 아니라 해당 단계의 목적, 범위와 완료 판단 기준만 정의한다.

---

## 3. MVP 완료 상태

MVP가 완료되면 Host가 Steam Session을 열고 여러 Client가 동일한 Gameplay Level에 참가할 수 있어야 한다. Host Server World에서는 Mass 개체와 지역 생태가 권위적으로 변화하고, 각 Client는 자신의 관심 영역에 있는 개체와 공통 지역 요약을 일관되게 볼 수 있어야 한다.

PPO와 Utility Baseline은 동일한 관측/행동 계약을 사용하며 전환 가능해야 한다. 플레이어의 포식 행동은 Server 검증을 거쳐 개체 사망과 지역 위험도에 반영되고, 이 결과가 다음 정책 판단으로 되돌아가야 한다.

---

## 4. MVP 이후

Dedicated Server 배포, Host Migration, 영속 월드, 대규모 매치메이킹과 Save/Load는 MVP 이후 단계로 둔다. Listen Server에서 확정한 Server Authority Contract를 유지하면 Dedicated Server 전환 시 생태 로직을 다시 설계하지 않아도 된다.
