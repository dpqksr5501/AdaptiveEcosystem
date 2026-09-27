# M2 — Mass Network Vertical Slice

## 목표

Server에서 생성한 Mass Entity를 Client별 관심 영역에 따라 전달하고, Client가 이를 로컬 Mass 프록시로 표현할 수 있음을 작은 수직 슬라이스로 검증한다.

## 범위

- Server 전용 Mass Entity 생성
- `StableAgentId`와 Mass Network ID의 역할 분리
- MassReplication 기반 Client relevancy와 Client Bubble
- Client Mass 프록시 생성, 갱신과 제거
- Transform과 최소 Presentation 데이터의 전달
- Server Processor와 Client Processor의 실행 범위 분리

## 아키텍처 방향

Server는 전체 Mass Entity 집합을 소유한다. Client는 자신의 관심 영역에 필요한 일부 Entity만 보유하며, Client Entity는 권위 개체가 아닌 표현 프록시다.

## 완료 기준

- Server에 생성된 Entity가 Client 관심 영역에 따라 선택적으로 나타남
- Client마다 보유하는 로컬 Entity 집합이 달라도 StableAgentId가 일치함
- 관심 영역 진입과 이탈 시 중복 없이 Entity가 생성·제거됨
- Client가 생태 상태를 독립적으로 변경하지 않음
- Late Join Client가 현재 상태를 정상 수신함

## 제외 범위

Food, Energy, PPO, Migration과 최종 그래픽 품질은 이 단계의 성공 조건이 아니다.
