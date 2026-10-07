# AdaptiveEcosystem — GPT-6.1 Project Context / Role Documentation Audit Prompt

## 목적

현재 `dpqksr5501/AdaptiveEcosystem` 저장소의 **실제 Source와 Docs를 함께 감사(audit)** 한 뒤,
앞으로 Codex / GPT coding agent가 저장소를 처음 열어도 다음 3가지를 혼동하지 않도록 문서를 정리해줘.

1. 이 프로젝트가 최종적으로 무엇을 구현하려는지
2. 각 핵심 계층의 책임과 Source of Truth가 무엇인지
3. **Social Behavior & Shelter Runtime 담당 영역과 현재 다음 작업이 무엇인지**

이번 작업의 핵심은 **새 기능 구현이 아니라 문서와 실제 Source의 정합성 확보**다.

---

# 0. Repository / 기준

Repository:

`https://github.com/dpqksr5501/AdaptiveEcosystem`

기준 브랜치:

`main`

엔진:

`Unreal Engine 5.8`

작업 시작 전 반드시 현재 `main`을 기준으로 실제 Source와 Docs를 직접 읽어라.

문서가 Source와 충돌하면:

> **현재 컴파일 가능한 Source > Root AGENTS.md > Active Contract Docs > 기타 설계/과거 문서**

순으로 판단한다.

추측으로 문서를 갱신하지 말고, 실제 코드에서 확인되지 않는 내용은
`planned`, `deferred`, `not yet integrated`, `requires verification` 등으로 명확히 표시한다.

---

# 1. 반드시 먼저 읽을 자료

## 최상위 지침

- `/AGENTS.md`

## Documentation Hub / Architecture

- `AdaptiveEcosystem/Docs/README.md`
- `AdaptiveEcosystem/Docs/Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md`
- `AdaptiveEcosystem/Docs/Architecture/ACTIVE_RUNTIME_BOUNDARIES.md`
- `AdaptiveEcosystem/Docs/Architecture/COLLABORATOR_ECOSYSTEM_INTEGRATION_PLAN.md`

## PPO / Mass

- `AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V1.md`
- `AdaptiveEcosystem/Docs/RL_Policy/UNREAL_POLICY_INTEGRATION.md`
- `AdaptiveEcosystem/Docs/Mass/MASS_PROCESSOR_ORDER.md`

## Roadmap

- `AdaptiveEcosystem/Docs/Roadmap/README.md`
- `AdaptiveEcosystem/Docs/Roadmap/M3/`
- `AdaptiveEcosystem/Docs/Roadmap/M4/M4_REPRESENTATION_INTERACTION.md`
- `AdaptiveEcosystem/Docs/Roadmap/M5/M5_PPO_CLOSED_LOOP.md`

## Social Runtime

- `AdaptiveEcosystem/Docs/조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md`
- `AdaptiveEcosystem/Docs/조연우/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md`
- `AdaptiveEcosystem/Docs/조연우/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md`
- `AdaptiveEcosystem/Docs/조연우/SHELTER_COVER_MVP_AGENT_PROMPT.md`

## Third-party / OSS

- `AdaptiveEcosystem/Docs/Integration/THIRD_PARTY_INTEGRATION.md`
- `/THIRD_PARTY_NOTICES.md`

---

# 2. 반드시 확인할 Source

문서만 보고 결론 내리지 말고 다음 Source를 실제로 읽어라.

## Core / Mass / Ecology

- `AdaptiveEcosystem/Source/AdaptiveEcosystem/Core/`
- `AdaptiveEcosystem/Source/AdaptiveEcosystem/Mass/`
- `AdaptiveEcosystem/Source/AdaptiveEcosystem/Ecology/`
- `AdaptiveEcosystem/Source/AdaptiveEcosystem/Network/`

특히:

- `Mass/EcoMassFragments.h`
- `Mass/EcoMassMigration.cpp`
- `Mass/EcoMassNetworkTrait.cpp`
- `Mass/EcoMassNetworkBootstrap.cpp`

## PPO / Behavior

- `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/`

특히:

- `EcoPolicyContracts.h`
- `EcoBehaviorFragments.h`
- `EcoBehaviorProcessors.cpp`
- `EcoBehaviorTraits.cpp`
- `EcoSteering.h`
- `EcoWorldProviders.*`

## Social Runtime

- `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Social/`

특히:

- `EcoSocialFragments.h`
- `EcoSocialTypes.h`
- `EcoSocialTrait.*`
- `Herd/`
- `Alarm/`
- `Shelter/`

## Debug / Test Harness

- `AdaptiveEcosystem/Source/AdaptiveEcosystem/Debug/`

Herd / Alarm / Shelter 테스트 하네스와 실제 production path를 구분해서 확인한다.

---

# 3. 프로젝트의 현재 목표를 다시 정리

현재 프로젝트를 아래와 같은 **Closed-loop Dynamic Ecosystem**으로 이해하고,
실제 Source와 다르면 그 차이를 보고해라.

```text
World / Region
    ↓
Ecology State
(Food / Predation / Population / Environment)
    ↓
Mass Creature Observation
    ↓
Utility / PPO Policy
    ↓
Social Behavior Runtime
(Herd / Alarm / Shelter)
    ↓
Steering / Movement
    ↓
Consumption / Predation / Death / Migration
    ↓
Ecology State
    ↺
```

중요:

- 프로젝트의 성공 기준은 단순히 PPO 몬스터가 움직이는 것이 아니다.
- 행동 결과가 Food / Energy / Death / Migration / Population / PredationHistory에 반영되고,
  그 결과가 다시 Observation과 행동에 영향을 주는 폐루프가 목표다.
- Server / Standalone이 authoritative logical state를 소유한다.
- Client Actor / Representation은 논리 상태의 Source of Truth가 아니다.

---

# 4. Social Behavior Runtime 역할을 명확하게 고정

Social Runtime의 책임은 다음과 같이 문서에 명확히 드러나야 한다.

```text
RL / PPO
= 개체가 무엇을 하고 싶은지 결정
  Forage / Cohesion / FleeDist / Cover

Social Behavior Runtime
= 사회적 문맥을 해석하고 행동 의도를 보정/구체화
  Dynamic Herd
  Alarm Communication
  Shelter / Cover Resolution

Movement / Steering
= 실제로 어떻게 이동할지 실행
```

Social Runtime이 소유하는 것:

### Dynamic Herd
- Persistent Herd identity / runtime membership
- Join / Leave
- Hysteresis
- Herd center
- Average velocity
- Member count
- Representative context

### Alarm Communication
- Herd-level threat injection / propagation
- Distance / time decay
- Calm / Alert / Panic / Recovering / Regrouping
- Direct observation과 별개의 social danger context

### Shelter / Cover
- Shelter registry
- Threat-relative LOS / Occlusion
- Candidate scoring
- Capacity / Slot
- Deterministic reservation
- `TargetPosition`
- Reservation release lifecycle

Social Runtime이 소유하지 않는 것:

- PPO Observation / Action / Reward 설계
- PPO 학습
- PPO network weight
- actual low-level steering implementation
- MassFlock 자체 구현
- Region resource authority
- Vitals / lifecycle source of truth
- network replication transport

특히 문서에서 반드시 다음 문장을 명시해라.

> **Herd != Flock**

- Herd = 논리적/사회적 무리
- Flock / Steering = 실제 이동 및 조향

---

# 5. 현재 구현 상태를 Source 기준으로 검증

다음 상태가 실제 Source / Editor validation 기록과 일치하는지 확인하고,
틀리면 Source 기준으로 수정해라.

```text
Dynamic Herd MVP
- implemented
- Editor Verified

Alarm Communication MVP
- implemented
- Editor Verified

Shelter / Cover MVP
- implemented
- Editor Verified for LOS / occlusion / reservation visualization
- 실제 Movement arrival / Occupied까지는 아직 production integration 필요
```

또한 PPO Raw Action을 Social이 직접 파괴하지 않고:

```text
FEcoPolicyOutputFragment::Action
    ↓ ReadOnly
FEcoSocialBehaviorFragment::ModulatedAction
```

으로 분리하는 계약이 유지되는지 확인해라.

---

# 6. 현재 가장 중요한 Integration Gap을 반드시 문서화

현재 Source를 직접 읽어서 다음 질문에 답해라.

## A. PPO / Steering

- `UEcoSteeringProcessor`가 현재 어떤 Action Fragment를 읽는가?
- `FEcoSocialBehaviorFragment::ModulatedAction`을 실제로 소비하는가?
- 아니면 아직 Raw `FEcoPolicyOutputFragment::Action`을 직접 읽는가?

## B. Shelter

- `FEcoShelterIntentFragment::TargetPosition`이 실제 movement에서 소비되는가?
- 아니면 현재는 예약 및 목적지 계산까지만 되어 있는가?

## C. Threat

- Alarm이 실제 Player / Predator event와 연결되어 있는가?
- 아니면 현재 테스트 하네스 중심인가?

## D. Movement Writer Ownership

다음을 모두 조사해라.

- PPO Steering
- Mass Movement
- Migration Steering
- `FMassDesiredMovementFragment`
- `FMassVelocityFragment`
- 직접 Transform 적분 코드
- MassFlock / custom steering 관련 구현

그리고 **동일 Entity의 위치/속도에 여러 writer가 동시에 개입할 위험이 있는지** 정리해라.

중요:

> 이 Audit 단계에서 임의로 Movement 시스템 전체를 갈아엎지 마라.

먼저 최종 movement ownership / handoff contract를 문서화한다.

---

# 7. 현재 Social Runtime의 다음 우선순위

문서에는 다음이 **CURRENT PRIORITY**로 명확히 표시되어야 한다.

```text
1. Real Player / Predator Threat → Alarm 연결
2. PPO Raw Action → Social ModulatedAction → Steering handoff
3. Shelter TargetPosition → Movement handoff
4. Reserved → Moving / Occupied lifecycle integration
5. Threat clear / Death / Despawn / Migration 시 reservation cleanup
6. 전체 end-to-end scenario validation
```

최종 데모 목표:

```text
Player / Predator 접근
    ↓
Threat 감지
    ↓
Herd Alarm
    ↓
같은 Herd 구성원의 social response
    ↓
ModulatedAction
    ↓
Safe Shelter 선택
    ↓
Slot reservation
    ↓
TargetPosition
    ↓
Movement
    ↓
Shelter 도착 / Occupied
    ↓
Threat clear / Death / Migration
    ↓
Reservation release
```

---

# 8. 지금 구현하지 말아야 할 것

현재 Production Integration이 끝나기 전에는 다음 기능을 시작하지 마라.

```text
- Herd Merge / Split 고도화
- Cross-Herd Multi-hop Gossip
- RVO2 / ORCA custom avoidance
- 자동 Cover Generation
- 복잡한 Leader AI
- Group Shelter 최적화
- 새로운 PPO Observation / Action 추가
```

이 기능들은 `Deferred` / `Future`로 유지한다.

---

# 9. 문서 수정 대상

Audit 이후 최소한 다음 문서를 갱신해라.

## 1) `/AGENTS.md`

목표:

- Social Runtime을 공식 Layer Boundary에 추가
- Social Runtime 핵심 문서를 필수 읽기 자료에 추가
- Codex / Agent가 처음 들어왔을 때
  `PPO → Social → Movement` 관계를 즉시 이해하도록 수정
- Source > Docs 원칙 유지

추가되어야 할 개념:

```text
Behavior Policy
    ↓ Raw Action
Social Behavior Runtime
    ↓ ModulatedAction / TargetPosition
Steering / Movement
```

---

## 2) `Docs/Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md`

현재 전체 아키텍처 그림과 설명에
Social Runtime이 누락되거나 PPO → Steering으로 바로 연결되어 있다면 수정한다.

목표 구조:

```text
World / Ecology
    ↓
Mass Observation
    ↓
PPO / Utility
    ↓
Social Runtime
    ↓
Steering / Movement
    ↓
Interaction / Lifecycle
    ↓
Ecology Feedback
```

단, 실제 Source가 아직 미통합 상태라면:

- `Target Architecture`
- `Current Implementation Gap`

을 구분해서 작성한다.

---

## 3) `Docs/조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md`

이 문서는 Social Runtime의 **현재 실제 구현 상태에 대한 Single Source of Truth**로 유지한다.

반드시 최신화:

```text
Current Base: main
Current Phase: Production Integration
```

그리고:

### Completed
- Herd MVP
- Alarm MVP
- Shelter selection / LOS / reservation

### Integration Pending
- real threat source
- ModulatedAction → Steering
- TargetPosition → Movement
- arrival / occupied
- death / migration / threat-clear cleanup
- full end-to-end validation

을 명확히 구분한다.

과거 브랜치 이름이 현재 상태처럼 보이지 않도록 정리한다.

---

## 4) `Docs/조연우/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md`

문서 상단에 반드시 `CURRENT PRIORITY` 섹션을 추가한다.

예:

```text
CURRENT PRIORITY

Verified Herd / Alarm / Shelter MVP를
production PPO / Steering / Lifecycle path와 통합한다.

Do NOT start:
- Merge / Split
- Multi-hop Gossip
- ORCA
until the production integration is complete.
```

과거 Task 0~3은 Historical / Completed 단계로 보이도록 정리하고
현재는 `TASK 4 — Integration`이 핵심임을 명확히 해라.

---

## 5) `Docs/README.md`

Social Runtime 문서가 추천 읽기 순서에서 빠져 있다면,
Codex가 전체 Architecture 다음에 현재 Social state를 쉽게 찾을 수 있도록 링크를 보완한다.

예:

```text
Architecture
→ Policy Contract
→ Social CURRENT_STATE
→ Collaborator Integration Plan
→ Mass Processor Order
→ Roadmap
```

정확한 순서는 전체 문서 의존관계를 보고 판단해라.

---

# 10. OSS 문서 주의

Social Runtime에서 참고한 OSS와 실제 포함된 Source를 혼동하지 마라.

대략적인 역할:

```text
OpenSteer / Reynolds
- Herd / steering behavior conceptual reference

ARGoS3
- local broadcast / swarm communication conceptual reference

CoverGenerator-UE4
- cover point / LOS / scoring conceptual reference

RVO2 / ORCA
- optional future local avoidance candidate
```

실제 소스 코드가 repository runtime dependency로 포함되지 않았다면
`used`가 아니라:

- reference
- conceptual reference
- design reference
- future candidate

로 표현한다.

MassFlock / RL tooling 등 다른 팀원의 영역도 Social Runtime contribution처럼 서술하지 마라.

---

# 11. 문서 중복 / 오래된 내용 정리

다음 문제를 검사해라.

- 동일 개념이 여러 문서에서 서로 다른 이름으로 정의되어 있는가?
- 과거 branch 상태가 현재 상태처럼 적혀 있는가?
- 구현 완료된 기능이 아직 `planned`로 적혀 있는가?
- 미구현 기능이 `implemented`처럼 보이는가?
- Aquarium / MassFlock 등의 과거 계획이 실제 현재 Source와 다른가?
- Social의 역할이 PPO / Movement와 중복돼 보이게 서술된 부분이 있는가?

필요하면 문장을 수정하되,
과거 설계 히스토리를 무조건 삭제하지 말고 `Historical` 또는 `Legacy`로 구분한다.

---

# 12. Source를 직접 수정할지 여부

이번 작업의 기본 범위는 **Documentation Audit / Alignment**다.

원칙:

```text
Docs 수정 = 허용
Source 수정 = 기본적으로 금지
```

단, Source에서 명백한 치명적 오류를 발견하면 즉시 고치지 말고:

```text
Critical Source Issue
- file
- symbol
- problem
- impact
- recommended fix
```

형태로 보고하고 멈춘다.

사용자 승인 없이 대규모 Source refactor를 시작하지 마라.

---

# 13. 작업 완료 보고 형식

작업이 끝나면 반드시 다음 형식으로 보고해라.

## 1. Repository Understanding

한 문단으로:

- 프로젝트 최종 목표
- 현재 milestone
- Social Runtime의 위치

## 2. Social Runtime Ownership

다음 표:

| Area | Owner | Current status |
|---|---|---|
| PPO / RL | RL | ... |
| Herd | Social | ... |
| Alarm | Social | ... |
| Shelter | Social | ... |
| Steering / Movement | Movement | ... |
| Ecology / Lifecycle | Ecology/Mass | ... |

## 3. Source-derived Integration Gaps

실제 Source에서 확인된 미연결 지점만 작성.

## 4. Documentation Changes

수정한 파일과 핵심 변경 내용.

## 5. Conflicts / Stale Docs

Source와 충돌하거나 오래된 문서가 있다면 목록화.

## 6. Next Recommended Task

새 기능 추가가 아니라,
현재 Production Integration을 위한 **가장 작은 다음 작업 단위**를 제안.

---

# 14. 성공 조건

이번 작업은 다음 조건을 만족하면 완료다.

1. 새 Codex / GPT Agent가 `/AGENTS.md`부터 읽어도 프로젝트 전체 목적을 이해할 수 있다.
2. Social Runtime이 PPO와 Movement 사이에 왜 존재하는지 이해할 수 있다.
3. Herd와 Flock을 혼동하지 않는다.
4. Social Runtime의 구현 완료 범위와 미통합 범위를 구분할 수 있다.
5. 다음 작업이 Merge/Split/ORCA가 아니라 **Production Integration**임을 이해한다.
6. 문서가 실제 `main` Source보다 앞서거나 뒤처진 내용을 명확히 구분한다.
7. 다른 팀원의 RL / Movement / Network 작업을 Social Runtime의 기여로 오인하지 않는다.
8. Source 변경 없이 문서만으로도 이후 agent가 올바른 방향으로 작업을 시작할 수 있다.

---

# 최종 지시

먼저 Repository와 Source를 충분히 읽고,
바로 수정하지 말고 짧게 **Audit Findings**를 정리한 뒤 문서 수정에 들어가라.

특히 다음 질문에 답하지 못한 상태에서는 문서를 확정하지 마라.

```text
1. 현재 PPO output을 실제 Steering은 무엇에서 읽는가?
2. Social ModulatedAction은 production movement에 연결되어 있는가?
3. Shelter TargetPosition은 실제 movement에 연결되어 있는가?
4. 실제 Alarm input은 test harness인가, production threat event인가?
5. Migration과 일반 Steering의 movement writer는 어떻게 분리되어 있는가?
6. Social Runtime이 현재 production entity template에 어떤 방식으로 포함되는가?
7. Server / Standalone에서만 Social logical state가 실행되는가?
```

Source가 최종 사실 기준이다.
문서는 Source를 설명해야지, Source가 문서를 억지로 따라가게 만들지 마라.
