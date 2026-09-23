# M3 — Authoritative Ecology Simulation Core

## 목표

플레이어와 PPO 없이도 Server에서 Mass 개체와 지역 자원이 스스로 변화하는 최소 동적 생태계 폐루프를 완성한다.

## 범위

- 두 개 이상의 Region과 지역별 권위 자원 상태
- Mass 개체의 Identity, Vitals, Region과 Travel 상태
- Food 재생, 소비 요청과 공정한 자원 조정
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
