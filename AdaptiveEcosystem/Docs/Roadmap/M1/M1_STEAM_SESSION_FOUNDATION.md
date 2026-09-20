# M1 — Steam Session Multiplayer Foundation

## 목표

Host가 Steam을 통해 방을 생성하고, 정해진 수의 Client가 방을 찾아 지정 Gameplay Level에 참가할 수 있는 멀티플레이 기반을 만든다.

## 범위

- Steam Lobby/Session 기반 방 생성, 검색, 참가와 종료 흐름
- Listen Server Level Travel과 Client 접속
- 공통 GameMode, GameState와 PlayerController의 멀티플레이 수명주기
- 접속 인원 제한과 기본 Session Metadata
- Server와 Client World의 역할 확인

## 아키텍처 방향

Steam은 Session 탐색과 연결을 담당하고, 실제 게임 권위는 Listen Server Host가 가진다. 이후 Dedicated Server로 교체하더라도 Gameplay 및 생태계의 Authority 규칙은 변경하지 않는다.

## 완료 기준

- Host가 방을 생성하고 지정 Gameplay Level을 열 수 있음
- 여러 Client가 방을 검색하거나 초대로 참가할 수 있음
- 모든 참가자가 동일한 Server GameState를 관찰함
- Host 종료 시 Session이 명확하게 종료됨
- 아직 Mass 생태계가 없어도 멀티플레이 흐름을 독립적으로 검증할 수 있음

## 제외 범위

Host Migration, Dedicated Server 배포, 영속 Session, 대규모 매치메이킹과 완성된 Lobby UI는 MVP 범위에서 제외한다.
