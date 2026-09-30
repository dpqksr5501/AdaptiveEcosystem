# M3 — Authoritative Ecology Simulation Core

> 개발 착수용 상세 계획: [M3 MVP 구현 계획](M3_IMPLEMENTATION_PLAN.md)

관찰 범위의 세부 개발 순서:

1. [M3.1 — 지역·낮밤·권위 스폰 기반](M3_1_WORLD_AND_SPAWN.md)
2. [M3.2 — 정기 소비·이벤트·자원 조정](M3_2_RESOURCE_AND_EVENTS.md)
3. [M3.3 — 실제 이주·표시·통합 검증](M3_3_MIGRATION_AND_VALIDATION.md)

이 세 단계는 아래 전체 M3 범위 중 현재 합의한 관찰 시나리오를 개발한다. 단계 간 상태 소유권, 인계 계약과 종료 기준은 각 문서를 따른다.

## 현재 개발 우선순위 (2026-09-28)

우선 플레이어 없이 2개 Region에서 낮밤 주기에 따라 Entity를 생성하고, 존재 시간에 따른 정기 소비와 낮/밤 자원 감소 이벤트로 Food가 고갈되면 같은 Entity가 다른 Region으로 이동하는 모습을 기존 Box 표현으로 검증한다. Food 재생은 사용자 요청에 따라 이번 우선 구현에서 제외하고 재생률을 0으로 둔다.

이 관찰 단계 뒤에 Energy/HP, 기아·사망, V1 Observation/Utility 및 장시간 안정성을 연결한다. 관찰 데모만으로 아래의 M3 전체 완료 기준을 충족했다고 판단하지 않는다. 플레이어 행동에 따른 출생 특성 결정은 별도 후속 기획으로 둔다.

## 목표

플레이어와 PPO 없이도 Server에서 Mass 개체와 지역 자원이 스스로 변화하는 최소 동적 생태계 폐루프를 완성한다.

## 범위

- 두 개 이상의 Region과 지역별 권위 자원 상태
- Mass 개체의 Identity, Vitals, Region과 Travel 상태
- 소비 요청과 공정한 자원 조정 (Food 재생은 현재 우선 구현에서 보류)
- Energy 감소·회복, 기아와 사망
- 저주기 Migration과 Population 집계
- Utility Baseline을 이용한 최소 행동 결정
- Region Summary의 Client 전달

## 아키텍처 방향

Region UObject나 Subsystem을 Entity 병렬 루프에서 직접 변경하지 않는다. Entity는 요청과 이벤트를 기록하고, Server의 조정 단계가 지역 상태를 한 번에 갱신한다.

## 완료 기준

- 일정 수의 Mass 개체가 Actor 없이 Server에서 장시간 실행됨
- Food와 Energy가 유효 범위를 벗어나지 않음
- Alive Entity 수와 Population 집계가 일치함
- 자원 부족이 사망 또는 Migration으로 이어짐
- Client가 지역 요약과 관련 개체 결과를 읽기 전용으로 확인할 수 있음

## 제외 범위

학습된 PPO, 고품질 군집 조향, 완성된 전투와 최종 Representation은 이후 단계로 둔다.
