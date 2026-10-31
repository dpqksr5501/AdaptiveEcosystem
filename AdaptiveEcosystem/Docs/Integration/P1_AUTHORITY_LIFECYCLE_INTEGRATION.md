# P1 — 공통 생명주기와 권위 실행 경로 통합

작성일: 2026-10-11 / UE 5.8 / 기준: `M4`, `6235742` / 상태: 구현 계획, 신규 실행 검증 없음.

[전체 순서](README.md) · 다음: [P2 계측](P2_PROFILING_AND_BASELINE.md)

## 1. 목적과 범위

사슴·늑대의 종별 행동은 유지하면서 생존·섭식·사망·이주·집계를 공통 권위 계약에 연결한다. 최종 결과는 같은 논리 개체의 HP/Energy/Food/Population과 Client 표현이 하나의 사건을 반영하는 폐루프다. 모든 행동을 하나의 거대한 Processor에 합치는 작업이 아니다.

## 2. 현재 구현 근거

| Source | 확인한 사실 |
| --- | --- |
| [EcoMassLifecycleSubsystem.cpp](../../Source/AdaptiveEcosystem/Mass/EcoMassLifecycleSubsystem.cpp) | Box의 World 시계·자원·스폰·생존·이주·집계 실행 |
| [EcoMassSurvival.cpp](../../Source/AdaptiveEcosystem/Mass/EcoMassSurvival.cpp) | 대사·기아·사망 결과와 Dead 정리 |
| [EcoCreatureIntegrationSpawner.cpp](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.cpp) | `Reconcile`에 별도 에너지/기아/사망 처리, 자원 요청·요약·표현 조정 |
| [EcoCreatureNetworkTrait.cpp](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureNetworkTrait.cpp) | 기존 Network Trait 상속, 서버 종별 논리와 Client 표현 구분 |
| [EcoMassNetworkBootstrap.cpp](../../Source/AdaptiveEcosystem/Mass/EcoMassNetworkBootstrap.cpp) | PPO/Custom/Spring/Simulation LOD 혼용 거부 |

동물 조정자도 M3 Bootstrap과의 동시 배치를 거부한다. 두 경로의 존재는 현재 이중 이동의 증거가 아니다. 동물 경로는 기존 Ecology·ID·지역·Bubble을 사용하지만 공통 생존 실행기로의 전환은 끝나지 않았다.

## 3. 변경 전에 확정할 계약

| 항목 | 확정할 내용 |
| --- | --- |
| 실행 총괄 | World당 논리 시계·자원 step을 전진시키는 권위 실행 주체 하나 |
| 생존 | 대사·기아 유예·피해·섭취 회복·사망 원인의 종별 설정과 적용 시각 |
| Feeding | 행동/공간 조건은 요청 생성자가 제공, 배분과 Food 총량은 Ecology가 결정 |
| Death | Epoch/ID/사건 식별과 단일 commit, 피식·기아·외부 피해 구분 |
| Migration | Travel 상태·마지막 commit Region·도착·기다림·진행 중 소비 취소 |
| Movement | 종별 writer와 Query 대상을 명시, Traveling/Resident/Dead 우선순위 |
| Summary | 완료된 동일 Step의 Food와 Mass 집계로 요약 생성 |

Box와 Creature의 기존 대사·사망 타이밍/잔류가 다르므로 한쪽 값을 조용히 기본 계약으로 삼지 않는다. 설정 및 기존 시나리오의 before/after를 기록한다. 늑대의 에너지·섭식 규칙도 사슴 규칙으로 자동 대체하지 않는다.

## 4. 구현 작업 순서

1. 실제 EntityConfig와 서버/Client Fragment·Tag·writer를 표로 수집한다. 같은 Entity가 공통 처리와 종별 처리를 각각 어디서 받는지 명시한다.
2. `Core`·`Mass`의 생존/소비/이주 계약을 기준으로 동물 요청과 결과의 adapter 경계를 설계한다. 클래스 이름/구현 이동은 이 설계 뒤 결정한다.
3. clock·resource-step·생존·사망·집계 총괄을 공통 실행 경계로 연결한다. 이전 경로는 선택적 비교 구성을 유지하되 동일 개체의 중복 소비/대사/사망은 차단한다.
4. 사슴 Raw/Social 행동값은 섭식·이동 요청으로, 늑대 감각/포획 결과는 검증된 피식 사건으로 전달한다. 기존 PPO 수치와 Social 예약 알고리즘은 유지한다.
5. 사망·despawn·이주 시 pending 소비/예약/Travel을 정리하고 Dead 상태·복제 잔류·삭제 순서를 맞춘다. Alive 제거 뒤 Fragment 참조 재획득과 replication destruction observer 경계를 보존한다.
6. Query·이동 인계·도착 Feedback을 검증한 뒤 구성의 혼용 허용 여부를 판단한다. 가드를 먼저 제거해서 통합하지 않는다.

종별 행동은 서로 다른 Processor에 남아도 된다. 핵심은 각 종이 공통 권위 생명주기·이벤트·자원 장부에 연결되는 것이다.

## 5. 완료 및 검증 기준

- 같은 StableAgentId에 대사·GrantedFood 적용·Death commit이 중복되지 않는다.
- Food 배분 합계와 실제 차감이 일치하고 ResourceStep 미완료/pending 요청이 다음 생명주기에 유출되지 않는다.
- 기아와 외부 피해를 포식으로 기록하지 않는다. 확인된 포식은 지역 피식 기록과 Population 감소에 한 번 반영된다.
- 은신처 이동→점유→사망/실패/이주 정리에서 슬롯 누수가 없다.
- 같은 ID의 A→B 이주가 도착 시 Region ID/index와 집계에 일관되게 반영된다.
- Client에 Vitals/Policy 권위 계산이 없고, relevance Remove와 사망 표시를 구분한다.
- Standalone·Listen Host/Client·Dedicated/Client·재접속에서 같은 규칙을 확인한다. 기존 테스트 기록을 새 통합의 통과로 재사용하지 않는다.

C++/빌드 입력 변경 후 실행 중 UBT/dotnet/Editor/Live Coding/MSBuild/ShaderCompileWorker를 먼저 확인하고, 실행 중인 작업을 중단하거나 새 빌드를 겹치지 않는다. 직접 UBT 빌드 완료 후 변경에 해당하는 회귀 검증을 수행한다.

## 6. 담당 연결과 인계

wonkii는 공통 실행·자원·사망·집계, 조연우는 감각/피식·예약 정리, sinhyeok04는 행동값·시간·파리티, avaroki는 실제 레벨 조건을 연결하는 것이 제안 경계다. 인계 산출물은 Entity 구성표, writer/실행 순서표, 단일 사건 계약, 회귀 결과다.

참조: [생존 검증 범위](../Roadmap/M3/OVERCROWDING_STARVATION_VALIDATION_REPORT.md), [Creature 통합](../조연우/CREATURE_PRODUCTION_INTEGRATION.md), [Shelter 인계](../조연우/SOCIAL_MOVEMENT_HANDOFF_AND_SHELTER_LIFECYCLE.md), [Mass 실행 순서](../Mass/MASS_PROCESSOR_ORDER.md).
