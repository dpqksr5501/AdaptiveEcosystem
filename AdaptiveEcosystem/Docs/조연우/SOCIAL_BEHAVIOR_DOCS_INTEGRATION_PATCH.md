# Social Behavior Docs Integration — Recommended Repository Updates

이 문서는 Social Behavior 문서를 Repository의 공식 문서 흐름에 연결하기 위한 작은 수정 가이드다.

---

# 1. 왜 필요한가

현재 Repository에는 프로젝트 전체 구조를 설명하는 문서가 충분히 존재한다.

특히:

```text
/AGENTS.md
Docs/Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md
Docs/RL_Policy/POLICY_CONTRACT_V1.md
Docs/Mass/MASS_PROCESSOR_ORDER.md
Docs/RL_Policy/RL_TRAINING_PIPELINE.md
Docs/Integration/THIRD_PARTY_INTEGRATION.md
Docs/Migration/AdaptiveEcosystem_PPO_Mass_Migration_Agent_Prompt.md
```

만으로 기존 AdaptiveEcosystem의 핵심 구조는 파악 가능하다.

다만 Social Behavior & Shelter Runtime은 새 확장 영역이므로,
현재 Root `AGENTS.md`와 `Docs/README.md`에서는 자동 발견되지 않는다.

또한:

```text
Docs/Architecture/아키텍처_설명.md
```

에는 최신 PPO 전환 안내와 함께 과거 LLM / Evolution 설명이 상당량 남아 있어
AI agent가 모든 문서를 indiscriminate하게 읽을 경우 현재 구조와 혼동할 수 있다.

따라서 아래 작은 문서 연결 수정이 필요하다.

---

# 2. 권장 디렉터리

```text
AdaptiveEcosystem/Docs/
└─ SocialBehavior/
   ├─ SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md
   └─ SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md
```

---

# 3. Root AGENTS.md에 추가할 항목

`## 1. 프로젝트 기준 정보`의 설계 및 참조 문서 목록에 추가:

```md
- `AdaptiveEcosystem/Docs/SocialBehavior/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md`:
  Dynamic Herd, Alarm Communication, Shelter Runtime의 책임 경계와 전체 구조
- `AdaptiveEcosystem/Docs/SocialBehavior/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md`:
  Social Runtime 구현 순서, Mass 데이터 설계, 성능/스레드 안전 규칙 및 AI agent 작업 지침
```

---

# 4. Root AGENTS.md 책임 경계에 추가할 항목

`책임 경계 (Layer Boundaries)`에 추가 권장:

```md
- **Social Behavior Runtime**:
  Persistent Herd membership, Alarm Communication, Shelter query/reservation을 담당한다.
  PPO Observation/Action 계약을 소유하지 않으며 MassFlock local steering을 재구현하지 않는다.
```

그리고 다음 문장을 추가:

```md
Social Runtime 작업 시 MassFlock은 다른 Movement/Flocking 담당자의 소유 영역으로 간주한다.
Herd는 persistent logical group이며 Flock steering과 동일한 개념이 아니다.
```

---

# 5. Docs/README.md에 새 카테고리 추가

권장:

```md
### Social Behavior & Shelter

MassEntity 개체의 지속적 무리 상태, 위험 정보 전파, Shelter 탐색/예약을 다룹니다.

- [SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md](SocialBehavior/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md)
  : Social Runtime의 역할, RL/MassFlock과의 경계, Herd/Alarm/Shelter 전체 데이터 흐름
- [SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md](SocialBehavior/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md)
  : Codex/Antigravity용 단계별 구현 지침, Source Audit, 성능/스레드 안전 규칙, Definition of Done
```

---

# 6. Docs/README.md 추천 읽기 순서 갱신

기존 1~4 이후 Social 작업자에게:

```md
5. `SocialBehavior/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md`
6. `SocialBehavior/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md`
```

를 추가한다.

단, Social 기능을 작업하지 않는 팀원에게는 필수 읽기 문서가 아니다.

---

# 7. `아키텍처_설명.md` 상태 명확화 권장

파일 상단에 이미 PPO 전환 안내가 있지만,
본문에는 과거 LLM / Evolution 설계가 장문으로 남아 있다.

이 파일을 삭제할 필요는 없다.

다만 상단에 다음 정도를 더 명확히 표시하는 것을 권장한다.

```md
> [!WARNING]
> 이 문서는 프로젝트의 역사적 설계 이유를 함께 보존하는 혼합 문서입니다.
> 현재 Runtime 구현의 Source of Truth가 아닙니다.
> 최신 구현 판단은 `PPO_MASS_ECOSYSTEM_ARCHITECTURE.md`,
> `POLICY_CONTRACT_V1.md`, `MASS_PROCESSOR_ORDER.md`,
> 그리고 현재 Source Code를 우선하십시오.
```

이렇게 하면 AI agent가 Legacy Evolution 설명을 현재 요구사항으로 복원하는 위험을 줄일 수 있다.

---

# 8. Third-party 문서

현재 Social Runtime에서 조사한:

```text
OpenSteer
ARGoS3
CoverGenerator-UE4
RVO2
DetourCrowd
HRVO
```

는 모두 아직 실제 Runtime dependency라는 뜻이 아니다.

따라서 조사했다는 이유만으로 `THIRD_PARTY_NOTICES.md`에 추가하지 않는다.

실제 Source 복사/수정/벤더링 시점에만:

```text
THIRD_PARTY_NOTICES.md
Docs/Integration/THIRD_PARTY_INTEGRATION.md
```

를 갱신한다.

---

# 9. AI agent에게 실제로 줄 파일

Social Behavior 코드 작업에서는 최소 다음 두 파일을 함께 읽게 한다.

```text
SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md
SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md
```

다만 별도 첨부보다 Repository 안에 두고
AI agent에게:

```text
Root AGENTS.md와 Docs/SocialBehavior의 두 문서를 먼저 읽고,
TASK 0 Source Audit만 수행해.
아직 구현 코드는 수정하지 마.
```

라고 지시하는 것이 가장 안정적이다.

이후 Audit 결과를 검토한 다음 Herd MVP를 시작한다.
