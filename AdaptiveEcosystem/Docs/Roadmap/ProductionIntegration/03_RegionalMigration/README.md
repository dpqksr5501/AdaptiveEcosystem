# 03. 지역 간 이주와 정책 문맥 이전

상태: 기존 M4 이주를 v3까지 연결하는 계획. [전체 구조·기준](../README.md)을 따른다.

## 필요한 기능

같은 개체가 자원·위험 압력에 따라 다른 지역으로 이동하고, 도착 지역의 먹이·환경·위협으로 판단을 이어가야 한다. 현재 v3 통합 설정은 이주·웨이브를 끈다.

## 구현 방향

```text
지역 압력 snapshot → 이주 의도 → 단일 이동 writer
  → 실제 도착 검증 → Region·v3 문맥 변경 → In/Out 집계
```

1. 기존 지역 인접 그래프·압력 계산을 재사용하고 우선 A/B 두 지역으로 제한한다.
2. Traveling 중 정책·Social·예약의 우선순위를 정한다. 출발지 예약·먹이·표적 참조를 정리한다.
3. 실제 도착 때 기존 StableAgentId, Energy·Reserve·기억·행동 상태를 보존하며 지역 문맥을 옮긴다. v3 좌표 단위와 Unreal cm를 변환한다.
4. 이동 실패·경로 변경·도착 중 사망을 처리한다. 확정된 도착만 지역×종 MigrationIn/Out에 반영한다.

## 기술과 완료 기준

상태 머신, 지역 그래프, 좌표계 변환, 요청 revision·취소, 인구 보존을 익힌다. 이주 coordinator는 위치를 직접 적분하지 않는다.

완료: 동일 ID가 B에서 먹고 다음 관측을 만들며 세계 Population은 이주로 변하지 않는다. Python에 없던 이주 조건은 RL 계약·평가를 함께 갱신한 뒤 적용한다.

관련: [기존 Migration](../../../../Source/AdaptiveEcosystem/Mass/EcoMassMigration.cpp), [이주·회계 실행 순서](../../../Integration/M4_RUNTIME_INTEGRATION_CONTRACT.md).
