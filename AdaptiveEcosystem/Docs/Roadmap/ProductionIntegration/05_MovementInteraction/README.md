# 05. 단일 이동과 예약·상호작용

상태: 기존 코드의 실제 레벨 검증·보완 계획. [전체 구조·기준](../README.md)을 따른다.

## 필요한 기능

장애물을 우회해 실제 목적지에 도착하고, 도착 뒤에만 섭식·점유·공격이 성립해야 한다. SpeciesAI의 NavMesh 경로와 v3의 원판 장애물 우회는 서로 다른 실행 경로다.

## 구현 방향

```text
정책/Social 목적지 → 경로·국소 회피 → 몸체 sweep·지면 제약
  → 단일 위치 적분 → 실제 도착/실패 feedback → 점유·섭식·공격
```

1. 공식 검증 레벨을 정하고 장소·은신처·줄기 충돌을 해당 무대 안에 배치한다. 저장된 맵 추가만으로 배치·행동 통과를 선언하지 않는다.
2. SpeciesAI 기존 Nav 예산·실패 재시도·지면 writer를 검증한다. v3에 StateTree 이동 Trait를 단순 추가하지 않는다.
3. Shelter와 일반 Smart Object 슬롯의 예약 owner를 구분하고 중단·사망·삭제·이주 때 해제한다.
4. 사슴1 벽 우회 → 도달 불가 → 사슴2/슬롯1 → 늑대 대역 → 실제 사슴·늑대 순서로 확인한다. 공격 성공·사망·영양 보상은 한 번만 확정한다.

## 기술과 완료 기준

NavMesh 경로, Steering/회피, capsule sweep·지면 검사, StateTree Task, Smart Object claim·lease, 실제 이동 feedback을 익힌다. Social·표현·Anim Notify는 논리 위치나 HP의 writer가 아니다.

완료: 관통·허위 도착·영구 Pending·슬롯 누수·중복 포획이 없다. v3 이동 규칙을 바꾸면 Python·Golden Vector·행동 평가를 함께 대조한다.

관련: [SpeciesAI 책임](../../../Integration/SpeciesAI/SOURCE_RESPONSIBILITIES.md), [소수 개체 수동 확인](../../../Integration/SpeciesAI/IMPLEMENTATION_MILESTONES.md).
