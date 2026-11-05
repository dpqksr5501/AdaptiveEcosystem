# 06. 네트워크 정합성과 성능

상태: 기존 복제·예산·LOD의 검증 및 실측 기반 개선 계획. [전체 구조·기준](../README.md)을 따른다.

## 필요한 기능

두 Client가 서버의 현재 상태를 일관되게 보고, 관심 영역 밖·no-player에서도 생태가 진행되어야 한다. 복제·보간·Actor 풀·연결 예산·정책 LOD는 기존 구현을 활용한다.

## 구현 방향

```text
Server Mass·Ecology → 완료 snapshot → 연결별 Bubble·전송 예산
  → Client Proxy → 이동 보간·Activity 표시 → Actor 풀
```

1. Dedicated/Listen + 동시 Client 2개에서 접속·이탈·재진입·teleport·정지 중 상태 변경을 확인한다.
2. 이동 SampleSequence와 VisualRevision을 구분하고 Actor 풀 재사용 시 ID·행동·오디오 잔류를 확인한다.
3. no-player·원거리에서 Food·생존·예약 lease는 계속 진행시킨다. 표현 relevance와 simulation LOD를 분리한다.
4. 소규모 정합성 통과 후 32→128→256→512개체에서 CPU·packet·메모리·p95/p99 지연을 측정한다. 기존 512 상한은 성능 보장이 아니다.
5. 감각·경로·충돌·복제 중 실제 병목을 먼저 개선한다. 순수 수치 계산만 worker 후보로 두고 UObject·Nav·commit의 스레드 경계를 유지한다.

## 기술과 완료 기준

Mass 복제·Client Bubble, relevance·LOD, 표본 보간, 데이터 지향 청크 순회·공간 검색, Unreal/Network Insights를 익힌다. 비동기 Nav·ORCA는 실측 뒤의 별도 확장이다.

완료: Client 논리 계산 0, 생태 보존식 유지, 재진입·풀 재사용 정상. 목표 hardware·규모·FPS·허용 지연을 먼저 기록하고 실측으로 판단한다.

관련: [복제·시간 계약](../../../Integration/M4_RUNTIME_INTEGRATION_CONTRACT.md), [M4 검증 범위](../../../Integration/M4_IMPLEMENTATION_PROGRESS.md).
