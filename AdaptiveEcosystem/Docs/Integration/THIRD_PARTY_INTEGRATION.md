# THIRD PARTY INTEGRATION STRATEGY

> 기준 엔진: **Unreal Engine 5.8**  
> 모듈: `AdaptiveEcosystem`  
> 연계 문서: [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md)
> Source 대조 기준: main `295ac2f` / 2026-09-30. 아래 원래 적응 전략은 Historical / Target plan이며 runtime 도입 완료 기록이 아님

## 현재 Source에서 확인한 사용·참조 구분

| 대상 | 현재 관계 | 담당/주의 |
| :--- | :--- | :--- |
| MassFlock | 초기 movement design reference. 별도 패키지/UEcoFlockSteeringProcessor 구현은 프로젝트 Source에서 확인되지 않음 | 실제 PPO 이동은 자체 격자 + EcoPolicy::Steer + 직접 적분. Movement/RL 담당 영역이며 Social 기여로 기록하지 않음 |
| Aquarium / marl-aquarium | 초기 환경 design reference; herbivore_rl/requirements.txt가 미사용을 명시 | 실제 Python은 자체 World/VecEnv. Aquarium adapter 구현 완료로 표현하지 않음 |
| Stable-Baselines3 / Optuna / NumPy 등 | herbivore_rl Python 학습·튜닝 도구 의존 | C++ 게임 런타임에 Python/PyTorch 추론을 내장하지 않음 |
| OpenSteer / Reynolds | Social/Herd 및 steering conceptual reference | 외부 런타임 의존/소스 포팅 완료를 뜻하지 않음 |
| ARGoS3 | Alarm local broadcast conceptual reference | runtime dependency가 아님 |
| CoverGenerator-UE4 | Shelter/LOS/scoring design reference | 자동 cover 생성·UE4 플러그인 포팅은 Deferred |
| RVO2 / ORCA / DetourCrowd / HRVO | future local avoidance candidate | Production Integration 뒤 Movement 담당이 기존 UE 기능과 필요성 평가 |
| DynamicWeather | 기존 고지의 날씨/에셋 참조 영역 | 이번 Source 감사는 에셋 provenance/라이선스를 재검증하지 않음. Social runtime 의존으로 분류하지 않음 |

근거: [EcoNeighborhoodSubsystem](../../Source/AdaptiveEcosystem/AI/Policy/EcoNeighborhoodSubsystem.h), [EcoSteering](../../Source/AdaptiveEcosystem/AI/Policy/EcoSteering.h), [Python requirements](../../../herbivore_rl/requirements.txt), [정책 통합 문서](../RL_Policy/UNREAL_POLICY_INTEGRATION.md). Build.cs의 MassMovement/MassNavigation 의존은 UE 엔진 모듈이며 MassFlock 외부 도입의 증거가 아니다.

참고와 실제 복사/적응 코드를 구분한다. 아래 과거 전략과 기존 license 고지를 유지하되, 새로운 Source를 도입할 때 해당 upstream LICENSE·적용 범위·파일 provenance를 확인하고 고지를 갱신한다. 기존 고지의 존재만으로 현재 runtime dependency를 단정하지 않는다.

---

## 1. 외부 라이브러리 및 오픈소스 활용 원칙

외부 알고리즘을 설계 참조로 활용할 수 있지만 실제 코드 도입과 구분합니다. 다른 팀원의 RL/Movement 구현을 Social의 OSS 도입 성과로 서술하지 않습니다.

---

## 2. Historical / Target Plan — MassFlock (PiotrJezyna/MassFlock — 기존 MIT 고지)

- **원본 기능**:
  - UE 5.1 기반 MassEntity Flocking (Separation, Alignment, Cohesion)
  - `MassNavigation` HashGrid 기반 공간 이웃 탐색(Spatial Neighbor Lookup)
  - `FMassForceFragment` 기반 조향 힘 누적
- **UE 5.8 적응 전략 (Reference-based Adaptation)**:
  - 초기 계획은 알고리즘 및 HashGrid 구조를 참고한 `UEcoFlockSteeringProcessor` 적응이었습니다. 현재 이 후보 Processor는 구현되어 있지 않으며 `UEcoSteeringProcessor`의 자체 이동과 구분합니다.
  - **가장 중요한 차이점**:
    - 원본 MassFlock: Cohesion/Separation 가중치가 종별 `FMassSharedFragment`에 존재함.
    - 본 프로젝트: PPO의 개체별 행동 출력(`FEcoPolicyOutputFragment`)이 개별 배율(Multiplier)로 적용됨:
      $$\vec{F}_{\text{cohesion, entity}} = \text{SharedBaseForce} \times \text{EntityPolicyOutput.Cohesion}$$
  - 라이선스 준수: `THIRD_PARTY_NOTICES.md`에 MIT 라이선스 및 저작권 명시.

---

## 3. Historical / Target Plan — Aquarium (기존 MIT 고지)

- **선정 이유**:
  - 2D 연속 공간에서 다중 에이전트(Predator/Prey)의 시야각(FOV), 가시거리, 조향 및 피식 관계를 시뮬레이션할 수 있는 경량 PettingZoo 환경.
- **확장 내용**:
  - 지역 식생 자원(`FoodAmount`) 및 재생 메커니즘 추가
  - 은신처 구역(Cover Zone) 배치
  - 개체별 에너지 소모/충전 상태 추가
- **적응 원칙**:
  - 초기 후보는 서브클래싱/래퍼(`AdaptiveAquariumEnv`) 확장이었습니다. 실제 구현은 자체 World이며 이 래퍼의 도입 완료를 뜻하지 않습니다.

---

## 4. 현재 RL 도구와 과거 PettingZoo 계획

- 실제 의존 선언은 `herbivore_rl/requirements.txt`입니다. 현재는 `>=` 최소 버전 범위를 사용하며 엄격한 version pin/lock 완료로 표현하지 않습니다. `Tools/RL`/PettingZoo adapter는 초기 계획입니다.
- PyTorch / SB3의 추론 런타임을 언리얼 엔진에 직접 임베딩하지 않고, **순수 C++ 전방 추론 함수로 가중치만 추출**하여 바이너리 크기와 크래시 리스크를 최소화합니다.
