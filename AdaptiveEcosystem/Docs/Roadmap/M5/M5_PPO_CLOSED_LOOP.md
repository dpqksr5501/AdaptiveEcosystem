# M5 — PPO Policy & Closed Ecosystem Loop

## 목표

Python에서 학습한 공유 PPO 정책을 Unreal C++ Mass Processor에 연결하고, 환경과 플레이어 압력이 행동과 생태 결과로 순환하는 최종 폐루프를 완성한다.

## 범위

- Policy Contract V1의 7차원 Observation과 4차원 Action 유지
- 공유 모델과 개체별 Observation/Policy Output 구조
- Unreal C++ Native deterministic inference
- Utility Baseline과 PPO 런타임 전환
- PPO 가중치를 반영한 Forage, Cohesion, Flee와 Cover 조향
- Food, Death, Migration, Population 결과의 다음 Observation 반영
- Python과 C++ Golden Vector parity

## 아키텍처 방향

PPO는 Client에서 권위적으로 실행하지 않는다. Server Mass Entity가 정책 결과를 사용해 행동하고 Client는 최종 이동과 표현 상태를 전달받는다. PPO 출력은 Entity Fragment이며 Shared Fragment가 아니다.

## 완료 기준

- Python과 C++ 정책 출력이 허용 오차 안에서 일치함
- PPO와 Utility 모드를 동일한 시나리오에서 비교할 수 있음
- 자원과 포식 위험 변화가 Observation과 행동 변화를 유발함
- 행동 결과가 다시 Food, Energy, Death, Migration과 Population에 반영됨
- 정책 실패 시 Utility Baseline으로 안전하게 전환됨

## 제외 범위

런타임 Python, 외부 프로세스 추론, LLM Trait Evolution과 Client 권위 정책 실행은 허용하지 않는다.
