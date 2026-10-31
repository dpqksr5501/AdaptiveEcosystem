# B — 복제·보간 수동 확인

자동화 테스트 생략. [진행 기록](M4_IMPLEMENTATION_PROGRESS.md).

- 맵: `LV_Ecosystem_IntegrationTest`. Play 설정: Players=2, Net Mode=Play As Client, Dedicated Server 실행. 가능하면 별도 서버/Client 프로세스로도 반복한다.
- 서버 콘솔 `eco.M4.TraceSamples 1`, `eco.M4.Dump details`. Client 콘솔 `eco.M4.Dump details`, `eco.Integration.Dump details`. Receive Audit의 Sequence/VisualRevision 및 Movement/Presentation/Reset/Rejected 수를 확인한다. relevance 재진입은 새로운 buffer이며 이전 개체 buffer의 누적값을 이어받지 않는다.
- 늑대 추적→식사/정지 전환을 보고 위치가 거의 고정된 상태에서도 속도·flag가 갱신되는지 확인한다. 이동 SampleSequence가 같아도 VisualRevision이 증가하면 수신 가능해야 한다.
- 서버에서 `eco.M4.Teleport <ID> <X> <Y> <Z>`로 실제 지면의 작은 오프셋 위치로 옮긴다. Client는 reset에서 즉시 정렬해야 한다.
- 서로 다른 거리의 두 Client, Off 범위 이탈/재진입, 늦은 접속, 동일 서버 재접속을 반복한다.
- 네트워크 에뮬레이션: PIE Play의 Network Emulation 설정에서 지연 100ms, 손실 1%를 별도 조건으로 비교한다. 정상 조건과 결과를 섞지 않는다.

통과 기준: ghost/중복 bind/stale 애니메이션 없음, 일반 위치는 서버 표본 timeline으로 보간, reset/재진입은 snap, Client 논리 개체 0. 송신 dirty와 실제 packet 횟수는 구분한다.
