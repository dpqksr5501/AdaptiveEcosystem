# M4 — Representation & Player Interaction

## 목표

복제된 Mass 개체를 Client에서 효율적으로 표현하고, 플레이어 상호작용이 Server의 생태 상태에 안전하게 반영되도록 연결한다.

## 범위

- 거리와 중요도에 따른 Mass Representation LOD
- Client Transform 보간과 시각 상태 표현
- 중요한 개체의 Actor Representation 전환
- StableAgentId를 이용한 Mass와 Actor 대응
- 플레이어 공격과 포식 사건의 Server 검증
- 사망, 위험도와 Population 변화의 Client 반영

## 아키텍처 방향

Actor와 Client Mass 프록시는 표현자이며 논리 상태의 주인이 아니다. 상호작용 결과는 Server Mass Entity에 먼저 확정되고, 이후 Client 표현에 전달된다.

## 완료 기준

- 원거리와 근거리 개체가 적절한 표현 수준으로 전환됨
- Representation 전환 전후 StableAgentId와 주요 상태가 유지됨
- 같은 개체의 Mass 표현과 Actor 표현이 중복되지 않음
- Client의 공격 요청이 Server 검증 후 생태 상태에 반영됨
- Player Kill이 PredationHistory와 후속 개체 행동에 영향을 줄 기반이 완성됨

## 제외 범위

복잡한 전투 시스템, 플레이어별 기억, 길들이기와 개별 평판은 MVP에서 다루지 않는다.
