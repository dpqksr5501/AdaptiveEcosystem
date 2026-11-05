# 02. 출생과 개체 생성

상태: 신규 기능 계획. [전체 구조·기준](../README.md)을 따른다.

## 필요한 기능

실행 중 지정 위치에 새 개체를 생성하고 새 StableAgentId·Births·Population·복제에 연결한다. v3의 현재 번식 표시/에너지 변화는 실제 새끼 생성이 아니다. 기존 비공개 Spawn은 그룹 시작 위치 기반이다.

## 구현 방향

```text
RL/생태 규칙 출생 요청 → 서버 검증·상한 예약 → 안전한 Mass 생성
  → ID·지역·종·정책 상태 초기화 → 출생 결과 확정 → 집계·복제
```

1. 요청 ID, 부모 ID, 종·지역, 희망 위치, 요청 시각을 받는 공통 API를 추가한다. 타입·함수명은 구현 시 정한다.
2. 지역 내부·지면·충돌과 지역/세계 상한을 확인하고 대기 중 생성 예약도 상한에 포함한다.
3. Mass 순회와 충돌하지 않는 조정 단계에서 생성한다. v3 Body/문맥 또는 SpeciesAI 상태도 해당 구성에 맞게 초기화한다.
4. 실제 성공 수만 Births에 반영하고 결과와 새 ID를 반환한다. 중복 요청은 다시 생성하지 않으며 실패·예약 취소를 처리한다.

## 기술과 완료 기준

Mass 생성·지연 구조 변경, 요청 큐, 멱등성, 생성 예약, 초기화와 회계를 익힌다. 새 ID는 서버가 발급하고 생년 시각 이전의 catch-up 섭식을 허용하지 않는다.

완료: 요청 1건당 출생 최대 1건, 실패 시 인구 증가 없음, Client 생성·표현 정상. 번식 조건·비용은 RL/생태 규칙 담당과 Python 평가에 함께 반영한다.

관련: [기존 Spawn](../../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureSpawning.cpp), [인구 보존 검사](../../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePopulation.cpp).
