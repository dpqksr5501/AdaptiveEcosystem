# M0 — Architecture & Authority Alignment

## 목표

기존 LLM Trait Evolution 경로와 신규 PPO + Mass 경로가 동시에 본체가 되지 않도록 프로젝트의 활성 아키텍처를 하나로 통일한다. Network, Simulation, Mass, World와 Representation의 상태 소유권을 먼저 고정한다.

## 범위

- PPO + MassEntity 아키텍처를 신규 런타임의 기준으로 확정
- `FRegionEcologyState`를 지역 자원의 단일 권위 상태로 확정
- Mass Entity를 개체 논리 상태의 단일 진실값으로 확정
- Listen Server와 Client의 실행 책임 구분
- Stable ID, Network ID와 Runtime Handle의 역할 분리
- Legacy Evolution 경로를 신규 핵심 코드가 의존하지 않도록 격리

## 주요 산출물

- [Mass Network Authority Contract](../Network/MASS_NETWORK_AUTHORITY_CONTRACT.md)
- 정리된 공통 데이터 계약
- Server/Client Processor 분류 기준
- Legacy와 Active Runtime의 명확한 경계

## 완료 기준

- Food, Population, Agent Vitals의 소유자가 각각 하나로 정의됨
- Client가 권위 Simulation을 실행하지 않는다는 규칙이 문서와 코드 구조에 반영됨
- 신규 코드가 Evolution Profile을 핵심 생태 상태로 사용하지 않음
- 프로젝트가 UnrealBuildTool 빌드를 통과함

## 제외 범위

Steam 세션 구현, 실제 Mass 복제, PPO 학습과 최종 Representation은 이 단계에서 구현하지 않는다.
