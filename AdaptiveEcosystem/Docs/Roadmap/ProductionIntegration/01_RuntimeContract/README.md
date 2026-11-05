# 01. 정책별 공통 실행 계약

상태: 계획. [전체 구조·기준](../README.md)을 따른다.

## 필요한 기능

V1 PPO, SpeciesAI StateTree, v3가 공통 생명주기·복제를 사용하되 위치·에너지·먹이·사망을 중복 변경하지 않는 구성이 필요하다.

| 경로 | 판단 | 확인할 실행 경계 |
| --- | --- | --- |
| V1 | 관측 7 → 행동 가중치 4 | Raw → Social 보정 → Steering |
| SpeciesAI | StateTree·Utility | Activity → Nav → 지면 이동 → 요청 공격 |
| v3 PR | 기본 관측 18·추가 21 지원 → 행동 5·마스크 | 별도 실행기·대사·공간 먹이, Social 행동 연결 기본 끔 |

## 구현 방향

1. 정책별 EntityConfig/Tag, Processor 순서, Transform·Velocity·Vitals·Food의 최종 writer를 표로 고정한다.
2. 관측·판단·의도·실행·결과 확정을 나누고, 정책의 결과를 공통 생명주기 Adapter로 전달한다.
3. v3의 에너지 소유권·Social 예외를 Root 계약과 대조하고 합의된 버전만 명시적으로 활성화한다. 기존 혼용 방지 가드를 유지한다.
4. 표현 상태 enum과 변환표의 개수를 맞춘다. 이전 분석에서 확인한 v3 늑대 9개 상태/7칸 표현 배열은 통합 시 재확인·수정한다.

```text
정책별 입력 → 판단 → 의도/제어 → 단일 이동 → 공통 결과 확정
```

## 기술과 완료 기준

Mass Fragment/Shared Fragment, Query 읽기·쓰기 선언, Processor 의존성, GameThread 경계, Trait 구성을 익힌다. 가변 개체 상태는 Shared Fragment에 넣지 않는다.

완료: 각 구성에서 writer가 겹치지 않고 Client에는 논리 판단·생존·이동 계산이 없다. Root 계약과 충돌한 항목의 처리 결정을 기록한다.

관련: [SpeciesAI 실행 구조](../../../Integration/SpeciesAI/SOURCE_RESPONSIBILITIES.md), [M4 실행 계약](../../../Integration/M4_RUNTIME_INTEGRATION_CONTRACT.md).
