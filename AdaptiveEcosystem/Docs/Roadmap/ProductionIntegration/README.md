# Production Integration — wonkii 다음 작업

작성일: 2026-10-21 KST / UE 5.8. 필요한 기능·구현 방향·전체 구조를 정리한 **계획**이며 완료 보고가 아니다.

## 기준과 현재 상태

- 로컬 구현 기준: `M4 / 67c860c`. 이후 `b0978cc`, `273c484`, `89dbc47`은 기존 에셋·레벨·조사 문서를 보존한 커밋이며 C++ 변경은 없다.
- 협업 기준: [RL v3 PR #12](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/12)의 `2464dcbedcae6de7ebaaf6803ea4b06b8684532f`(작성 시 열림), [날씨 PR #13](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/13)(main `ff4f287`에 병합). 로컬 M4와 원격 PR의 구현을 합산해 로컬 완료로 표기하지 않는다.
- M4에는 생존·사망·먹이·이주·인구 회계·복제와 SpeciesAI 코드가 있다. v3 PR에는 M4 병합, 공간 먹이 장부·Client 연결도 있어 재구현 대상이 아니다.
- v3는 현재 이주·웨이브를 끈다. 실제 출생 API와 정책별 계약 정리, 새 레벨 실행 검증이 주요 후속 작업이다.
- Root [AGENTS.md](../../../../AGENTS.md)의 V1·Social 계약과 v3 동작의 차이는 먼저 기록·합의한다. 이 로드맵이 기존 계약을 교체하거나 v3 예외를 승인하지 않는다.

## 전체 구조

```text
World: 지역·환경·공통 시각
  → 정책별 관측·판단(V1 / StateTree / v3)
  → Social 의도 또는 계약된 신호
  → 개체당 하나의 이동 writer
  → 섭식·피식·출생·사망·실제 이주 결과
  → Ecology 자원·인구 회계 → 다음 관측
                         └→ Network DTO → Client 표현
```

권위 상태는 Server/Standalone의 Mass·Ecology가 소유한다. World는 환경, Social은 무리·경보·예약, 표현 Actor는 표시를 담당한다. Subsystem은 복제 transport가 아니다.

## 주제별 계획과 순서

| 순서 | 문서 | 핵심 결과 |
| --- | --- | --- |
| 1 | [실행 계약](01_RuntimeContract/README.md) | 정책별 상태 소유권·EntityConfig·실행 순서 확정 |
| 2 | [출생](02_BirthLifecycle/README.md) | 지정 위치의 새 ID 발급·안전한 생성·Births 반영 |
| 3 | [이주](03_RegionalMigration/README.md) | 기존 ID·상태를 보존하는 v3 지역 문맥 이전 |
| 4 | [환경·자원](04_EnvironmentResources/README.md) | 서버 환경과 먹이·관측·Client 날씨의 일치 |
| 5 | [이동·예약](05_MovementInteraction/README.md) | 실제 지형에서 단일 이동·도착·중단·정리 검증 |
| 6 | [네트워크·성능](06_NetworkPerformance/README.md) | 다중 Client·no-player·규모별 정합성과 비용 확인 |
| 7 | [정책 비교](07_PolicyEvaluation/README.md) | 같은 환경·실행 조건에서 판단 방식 비교 |
| 후속 | [생태계 확장](08_FutureExtensions/README.md) | 시체 자원·다종 관계·원거리 집계·영속 복원 |

이동·예약의 소수 개체 검증은 출생·이주 개발 중에도 선행한다. 정책 비교 전에 이동·자원·생존 조건이 안정되어야 한다.

## 첫 완료 시나리오

A/B 두 지역에서 먹이 부족 → 이주 → 도착 후 섭식, 포식 → 단일 사망 확정, 출생 → 새 ID·인구 증가를 확인한다. 두 Client가 같은 결과를 받고, 관심 영역 밖에서도 서버 생태가 진행되어야 한다.

완료 시각별 `Population = 이전 Population + Births - Deaths + MigrationIn - MigrationOut`을 확인한다. 빌드·에셋 로드·게임 행동·네트워크·성능 결과는 각각 기록한다.

## 근거와 검증 범위

- [M4 구현·검증 이력](../../Integration/M4_IMPLEMENTATION_PROGRESS.md), [SpeciesAI 책임과 한계](../../Integration/SpeciesAI/SOURCE_RESPONSIBILITIES.md)
- [V1 정책 계약](../../RL_Policy/POLICY_CONTRACT_V1.md), [v3 계약](https://github.com/dpqksr5501/AdaptiveEcosystem/blob/2464dcbedcae6de7ebaaf6803ea4b06b8684532f/AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V3.md), [협업 요청](https://github.com/dpqksr5501/AdaptiveEcosystem/blob/2464dcbedcae6de7ebaaf6803ea4b06b8684532f/AdaptiveEcosystem/Docs/RL_Policy/TEAM_REQUESTS_V3.md)

이번 정리는 문서·링크·Source 근거를 확인한다. 새 UBT/PIE/자동화·성능 검증은 수행하지 않는다. 기존 조사 문서와 바이너리 에셋 저장을 현재 게임 실행 통과로 해석하지 않는다.
