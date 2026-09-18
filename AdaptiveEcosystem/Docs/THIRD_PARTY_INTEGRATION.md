# THIRD PARTY INTEGRATION STRATEGY

> 기준 엔진: **Unreal Engine 5.8**  
> 모듈: `AdaptiveEcosystem`  
> 연계 문서: [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)

---

## 1. 외부 라이브러리 및 오픈소스 활용 원칙

본 프로젝트는 검증된 오픈소스 알고리즘을 효과적으로 레버리지하되, 불필요한 전체 코드베이스 복제나 블랙박스 의존성을 지양합니다.

---

## 2. MassFlock (PiotrJezyna/MassFlock — MIT)

- **원본 기능**:
  - UE 5.1 기반 MassEntity Flocking (Separation, Alignment, Cohesion)
  - `MassNavigation` HashGrid 기반 공간 이웃 탐색(Spatial Neighbor Lookup)
  - `FMassForceFragment` 기반 조향 힘 누적
- **UE 5.8 적응 전략 (Reference-based Adaptation)**:
  - 원본 리포지토리를 무작정 엔진 플러그인으로 벤더링하지 않고, **알고리즘 및 HashGrid 이웃 탐색 구조를 참고하여 본 프로젝트에 맞게 직접 C++ Processor(`UEcoFlockSteeringProcessor`)로 재구현**합니다.
  - **가장 중요한 차이점**:
    - 원본 MassFlock: Cohesion/Separation 가중치가 종별 `FMassSharedFragment`에 존재함.
    - 본 프로젝트: PPO의 개체별 행동 출력(`FEcoPolicyOutputFragment`)이 개별 배율(Multiplier)로 적용됨:
      $$\vec{F}_{\text{cohesion, entity}} = \text{SharedBaseForce} \times \text{EntityPolicyOutput.Cohesion}$$
  - 라이선스 준수: `THIRD_PARTY_NOTICES.md`에 MIT 라이선스 및 저작권 명시.

---

## 3. Aquarium (michaelkoelle/marl-aquarium — MIT)

- **선정 이유**:
  - 2D 연속 공간에서 다중 에이전트(Predator/Prey)의 시야각(FOV), 가시거리, 조향 및 피식 관계를 시뮬레이션할 수 있는 경량 PettingZoo 환경.
- **확장 내용**:
  - 지역 식생 자원(`FoodAmount`) 및 재생 메커니즘 추가
  - 은신처 구역(Cover Zone) 배치
  - 개체별 에너지 소모/충전 상태 추가
- **적응 원칙**:
  - Upstream 코드를 불필요하게 수정하지 않고 서브클래싱/래퍼(`AdaptiveAquariumEnv`) 패턴으로 확장.

---

## 4. Stable-Baselines3, PettingZoo & Optuna

- Python RL 도구체인은 `Tools/RL/requirements.txt`에 버전을 엄격히 핀(Pin)하여 팀원 및 CI 환경 간 재현성을 확보합니다.
- PyTorch / SB3의 추론 런타임을 언리얼 엔진에 직접 임베딩하지 않고, **순수 C++ 전방 추론 함수로 가중치만 추출**하여 바이너리 크기와 크래시 리스크를 최소화합니다.
