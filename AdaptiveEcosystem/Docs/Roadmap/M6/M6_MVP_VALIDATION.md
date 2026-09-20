# M6 — MVP Integration, Validation & Release Readiness

## 목표

Steam Listen Server 멀티플레이와 PPO + Mass 생태계가 하나의 플레이 가능한 MVP로 안정적으로 동작하는지 통합 검증한다.

## 범위

- Host와 복수 Client의 Session 생성·참가·종료 검증
- Late Join과 Client 관심 영역 변화 검증
- Server/Client 상태 권위와 데이터 정합성 검증
- Food, Energy, Death, Migration과 Population의 장시간 안정성 검증
- Policy parity와 PPO/Utility 비교
- Mass Processor, Representation과 Network 대역폭 프로파일링
- 오류 로그, 디버그 지표와 재현 가능한 테스트 시나리오 정리

## 대표 MVP 시나리오

```text
Host가 Steam Session 생성
→ Client들이 Gameplay Level 참가
→ Server에서 지역 자원과 Mass 개체 시뮬레이션
→ Client별 관련 개체 표현
→ 플레이어 포식 사건 발생
→ 개체 사망과 PredationHistory 증가
→ 살아남은 개체의 Observation과 행동 변화
→ Population과 Region Summary가 모든 Client에 반영
```

## 완료 기준

- Host와 목표 수의 Client가 반복적으로 같은 Session에 참가 가능함
- Client가 권위 생태 상태를 변경할 수 없음
- 장시간 실행에서 Food와 Population이 논리적으로 일관됨
- 관심 영역 진입·이탈과 Late Join에서 Mass 프록시가 중복되지 않음
- 네트워크 지연과 손실 상황에서도 Client 표현이 회복됨
- 목표 Entity 수에서 Processor 시간과 네트워크 사용량이 기록됨
- UnrealBuildTool 빌드와 핵심 자동화 테스트가 통과함

## MVP 이후 전환

Dedicated Server는 이 단계 이후의 확장으로 둔다. Listen Server Host가 갖던 Server Authority를 Dedicated Server World로 옮기되, Mass/Simulation/Client 계약은 변경하지 않는다.
