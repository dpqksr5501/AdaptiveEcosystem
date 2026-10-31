# P5 — 순수 계산 병렬화와 논리 시간 스케줄

작성일: 2026-10-11 / UE 5.8 / 기준: `M4`, `6235742` / 상태: 설계·검증 계획, 병렬 성능 실측 없음.

[전체 순서](README.md) · 이전: [P4](P4_CREATURE_REPLICATION_AND_REPRESENTATION.md) · 다음: [P6](P6_SIMULATION_LOD_AND_SCALE_VALIDATION.md)

## 1. 목표와 선행 조건

P1 실행/결과 적용 계약, P2 측정, P3 후보 선별을 바탕으로 순수 개체 계산을 Chunk 단위로 처리하고 필요한 부분을 병렬화한다. 정책·감각·이동·자원의 시간 의미를 서버 FPS에서 분리한다. 실행 플래그나 정책 주기만 바꾸는 최적화가 아니다.

## 2. 현재 근거

- [EcoBehaviorProcessors.cpp](../../Source/AdaptiveEcosystem/AI/Policy/EcoBehaviorProcessors.cpp): 행동 Processor가 GameThread를 요구하며 일반 Chunk 순회 사용. Policy는 `LastPolicyStep` 프레임 카운터로 주기 판정.
- [EcoPolicyInference.cpp](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyInference.cpp): native 추론/Utility 수치 계산의 분리 후보.
- [EcoSteering.h](../../Source/AdaptiveEcosystem/AI/Policy/EcoSteering.h): 테스트 가능한 수치 조향. 실제 이동 guard는 World 조회가 포함됨.
- [Threat Detection](../../Source/AdaptiveEcosystem/AI/Social/Alarm/EcoThreatDetectionProcessor.cpp), [Predator Processor](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePredatorProcessor.cpp): 감각/이동의 World·UObject 접근 확인 지점.

`Branch_Sinhyeok`에는 시간·Alive·EMA 관련 후속 변경이 있지만 현재 main/M4에 모두 적용된 것으로 읽지 않는다. 실제 도입 시 commit·충돌·동물 변경과의 호환성을 검토하고 중복 구현을 피한다.

## 3. 처리 경계 설계

| 단계 | 허용할 작업 | 제한 |
| --- | --- | --- |
| 입력 수집 | 환경·이웃·감각·자원 완료 상태를 읽기 snapshot으로 준비 | World trace/streaming 및 공유 상태 접근의 thread 계약 확인 |
| 순수 계산 | 관측 정규화·공유 가중치 추론·수치 조향·개체 요청 생성 | UObject 호출·Food 차감·예약 commit·전역 map 수정 금지 |
| 결과 조정 | 버퍼 병합·정렬·자원 배분·예약/Death/Region commit | 공통 안전 경계·단일 사건 처리 |
| 이동/표현 | 종별 이동 writer·World guard·Client 표시 | 동일 Entity의 writer 중복 금지 |

worker 결과 버퍼는 job별로 분리하고 ID/Epoch/Step을 포함한다. merge/commit 순서가 scheduler에 따라 바뀌지 않게 정한다. 출력·공유 snapshot의 수명과 갱신 종료 시점을 정의한다.

Epic의 [ParallelForEachEntityChunk API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/MassEntity/FMassEntityQuery/ParallelForEachEntityChunk)는 Chunk 병렬 처리 수단이다. 모든 Processor가 자동 병렬화되거나 GameThread flag 제거만으로 thread-safe해진다는 의미는 아니다. 설치된 5.8의 실행 조건·Query requirement·dependency를 확인하고 실제 worker 실행을 trace로 증명한다.

## 4. 시간 기반 스케줄 작업

1. 정책 decision interval, 감각/기억 감쇠, 피식 cooldown/EMA, 이동 dt, 생태 step, 네트워크 real time을 각각 표로 정의한다.
2. V1 학습 `StepSeconds`/생성 설정과 Unreal의 실제 주기를 대조한다. 고정 틱 가정과 기존 수치 차이를 기록한다.
3. 정책 기한은 논리 시각으로 표현하고 StableAgentId 기반 결정론적 phase 분산을 검토한다. 전체 N의 추론이 같은 frame에 몰리지 않게 한다.
4. 긴 frame/catch-up의 최대 작업량·미처리 경과 시간·최신 입력 선택 규칙을 정의한다. 시간을 버리거나 이동을 생태 substep 수만큼 중복 적분하지 않는다.
5. 정책 주기·입력 snapshot 변경은 행동 분포를 바꿀 수 있다. Golden Vector와 별도 gameplay 비교, 필요 시 Python 대응/재평가를 수행한다.

WorldClock은 생태 시각, 복제 표본은 서버 real time 계약을 따른다. Client 수신 시각 차이를 latency로 단정하지 않는다. 프레임 독립성과 서로 다른 시계의 무조건 통일을 혼동하지 않는다.

## 5. 구현·검증 순서

- 먼저 동일 계산을 snapshot/결과 버퍼로 분리한 직렬 경로를 만들고 기존 결과와 비교한다.
- 순수 policy 등 P2에서 비용이 확인된 구간부터 병렬화한다. 작은 N에서는 job overhead가 더 클 수 있어 적용 기준을 측정한다.
- Shared Model은 읽기 전용, 개체별 output은 자신의 Fragment로 제한한다. hot path에 Python·외부 추론 프로세스를 추가하지 않는다.
- Fragment read/write requirement·Processor 순서와 구조 변경/observer 잠금 경계를 확인한다.
- 동일 입력의 직렬/병렬 정책·조향 Golden Vector, 자원/예약 결정 순서, 중복 Death와 stale 결과를 검증한다. floating-point 허용 오차를 미리 정의한다.
- 저 FPS·긴 frame·pause/time dilation 지원 범위에서 decision 횟수·기억·대사·이동 거리를 비교한다. 동일 입력의 native 결정론과 전체 충돌 세계의 bit-identical 결과를 혼동하지 않는다.

## 6. 완료 기준과 담당 연결

P2와 동일 조건에서 실제 worker 실행·GameThread 감소·전체 frame 비용을 보고하고 정확성 회귀가 없다. 평균 개선만으로 p99 악화·작은 N overhead를 숨기지 않는다. 새 시간 스케줄의 학습 대응과 미지원 조건을 명시한다.

제안 담당: sinhyeok04는 정책/조향/학습 시간·Golden Vector, wonkii는 공통 snapshot/commit/계측, 조연우는 감각·기억·Alarm/lease·예약 순서. C++ 변경 후 루트 규칙의 직접 UBT와 해당 회귀 검증을 완료한다.

참조: [V1 계약](../RL_Policy/POLICY_CONTRACT_V1.md), [Mass 실행/스레드 계약](../Mass/MASS_PROCESSOR_ORDER.md), [Shelter 인계·lease](../조연우/SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md).
