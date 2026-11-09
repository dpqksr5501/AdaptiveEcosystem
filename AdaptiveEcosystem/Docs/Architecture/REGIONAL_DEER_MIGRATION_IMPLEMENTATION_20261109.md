# 지역 순차 사슴 이주 구현 및 간단 테스트

> PR #16/main 통합 후에는 지역 이주와 다종 payload를 함께 저장하는 **포맷 5**를 사용한다. 아래 포맷 2는 최초 구현 이력이다. [통합 기록](../Team/PR16_JWJ_MERGE_20261109.md)을 먼저 확인한다.

2026-11-09. [개발 계획](REGIONAL_DEER_MIGRATION_PLAN_20261109.md)의 지역별 등록 순서·개별 출발·누적 한도 경로를 opt-in으로 구현했다. **Editor 빌드와 관련 자동화 13개 성공, 기존 1102 실제 이동·멀티·체크포인트 왕복 실행 검증은 미완료다.**

## 구현 결과

- `eco.HerdMigration.Regional 1`이면 지역의 Native 사슴 등록 순서를 유지하는 배열을 사용한다. Native adoption 때 추가하고 실제 지역 인계 때 목적지 끝에 추가한다. 사망/이탈은 다음 지역 평가에서 상대 순서를 유지하며 정리한다. 복원 상태에 빠진 ID는 결정적인 fallback 순서로 보충한다.
- 지역 부족이 8초 지속되면 episode 시작 인원을 고정한다. 현재 허기·최소 2마리 Herd 조건 없이 개별 후보를 검사한다. 같은 Herd 일부만 출발할 수 있도록 기존 계획 map의 키를 PlanId로 변경했다. Herd 정체성은 유지한다.
- 현재 Food / (최대 설정 보행 대사 × 60초 / FoodEnergyPerUnit)로 유지 가능 사슴 수를 계산한다. EnergyDrain은 decision step당 값이므로 step 길이로 초 단위를 환산한다. 실제 섭취량 0을 수요 0으로 해석하지 않는다. 첫 구현은 미확정 재성장 공급을 더하지 않는 보수적 추정이며 번식 비용·개체별 체형/활동 수요를 완전히 예측하는 모델은 아니다. 현재 통합 사슴 먹이 소비 경로에 한정한다.
- 한 지역에서 최소 3초 간격으로 한 마리만 승인한다. 미도착 출발 예약을 예상 잔류 인원에서 즉시 빼고, 실제 떠난 개체를 다시 빼지 않는다. 목적지 인구는 사슴 수와 전 지역의 미도착 승인 수요를 반영한다.
- episode 초기 인원의 25%(올림)를 잔류 하한으로 둔다. 1마리 지역은 하한 0이다. 누적 승인 ID는 실패/사망 때 줄이지 않는다. 회복 35% 및 지원 가능한 인구 조건이 15초 유지돼야 episode를 닫는다.
- 기존 Native 이동과 실제 Migration receipt를 사용한다. 지도에 `Stay / Support / Keep / Sent`와 지역 중단 이유를 표시하고 읽기 전용 JSON에도 포함한다.
- 등록 순서·episode·승인 이력을 기존 체크포인트에 직렬화한다. **포맷 버전은 2이며 이전 버전 1은 명시적으로 거절한다.** 기존 runtime image hash 제한도 유지한다. 계획 문서의 구버전 이전은 이번 구현에서 제공하지 않았으며 예전 슬롯을 덮어쓰지 말고 새 슬롯을 사용한다. 실제 저장/복원 왕복 검증이 남았다.

## 1분 설정, 2~3분 관찰

1. 최신 빌드로 기존 `/Game/JWJ/1102_Integration_JWJ`를 연다. 첫 시험은 기존 12마리/지역 설정을 권장한다. 인원이 다르면 실제 표시 인원으로 하한을 계산한다.
2. Play 드롭다운에서 **Standalone Game**을 실행한다. 일반 PIE의 NetMode Standalone과 구분한다. 가뭄 fixture는 PIE 접두사가 붙은 JWJ 맵에서 거절된다.
3. 게임 창 콘솔에서 아래 명령을 **한 줄씩 입력하고 Enter**한다.

```text
eco.HerdMigration 1
eco.HerdMigration.Regional 1
eco.HerdMigration.Debug 2
eco.HerdMigration.Test.Drought JWJ_WildlifeTest
```

`[HerdMigration][AuditFoodLoss] Region=JWJ_WildlifeTest ... After=0.000000 SuspendRegen=1`이 먼저 있어야 한다. 마지막 명령은 서버 먹이를 제거하고 재생을 정지하는 개발 fixture다. 자연 고갈/자연 균형 시험으로 기록하지 않는다.

`Debug 2`는 지도를 켠다. 안 보일 때만 `M`을 확인한다. `[`/`]`로 계획을 선택한다. 4지역 HUD가 세로로 길어지므로 1080p 이상의 창을 권장한다.

| 관찰 시점 | 기대할 값/동작 |
|---|---|
| 가뭄 직후 | Food 0%, 부족 지속 시간 누적 |
| 약 8초 이후 | `[HerdMigration] Plan=... Arrived=0/1`, 개별 계획 한 개 생성 |
| 이후 최소 3초 간격 | 지역 등록 순서대로 다음 개체 승인, Sent 증가/Stay 감소 |
| 12마리 시작·추가 사망 없음·유효 목적지 있음 | Keep 3, 최대 Sent 9/9, Stay 3에서 추가 승인 중단 |
| 중단 이후 | 반복 평가해도 Sent 한도가 재충전되지 않음. 경로/목적지 부족이면 9보다 일찍 중단 가능 |
| 이동 중 | 선택 계획의 실제 사슴 위치·waypoint 진행, Traveling만으로 도착 판정하지 않음 |
| 실제 지역 진입/도착 | 동일 StableAgentId의 RegionId 변경과 기존 유입·유출 거래, 경로 끝 도착 시 Settled |

`Stay`는 이미 승인된 출발자를 뺀 **예상 잔류 사슴 수**, `Pop`은 기존 생태 인구 집계다. 승인 순간 Pop이 줄어야 한다고 판단하지 않는다. 사망/출생/유입이 있으면 12→3 예시와 달라질 수 있다. 전체 지도 Plan 수는 다른 지역 계획까지 포함하므로 해당 출발 지역의 Sent를 확인한다.

## 중단 이유 읽기

| 이유 | 의미 |
|---|---|
| ShortageDwell | 부족 지속 시간 대기 |
| RegionSustainable | 예상 잔류 인원을 현재 추정 먹이로 유지 가능 |
| DepartureInterval | 다음 출발 승인 간격 대기 |
| RetentionFloor | 한 마리 더 보내면 잔류 하한 미달 |
| EpisodeBudgetReached | 이번 부족 기간의 누적 승인 한도 도달 |
| NoEligibleCandidate | 현재 후보 모두 이동 중/stranded/cooldown 등으로 제외 |
| NoViableKnownRoute | 알려진 보고·목적지 여력·인접/지면 경로·점수 조건 중 통과 경로 없음 |
| Approved / Recovered | 이번 승인 성공 / 회복 조건 유지 후 episode 종료 |

`NoViableKnownRoute`는 지형 충돌 확정 진단이 아니다. 현 구현은 경로별 거절 사유를 모두 세분화하지 않았으므로 그 경우 로그/route/목적지 자원 추가 조사가 필요하다. 개체별 건너뛴 원인 전체 및 다음 평가 시각 HUD는 후속 보완 대상이다.

## 조절 가능한 설정

| 콘솔 변수 | 기본값 | 영향 |
|---|---|---|
| eco.HerdMigration.Regional | 0 | 1에서 새 지역 순차 평가, 0에서 기존 Herd 경로 |
| eco.HerdMigration.ShortageFraction | 0.25 | 부족 진입 잔량 비율 |
| eco.HerdMigration.ShortageSeconds | 8 | 부족 지속 시간 |
| eco.HerdMigration.DepartureSeconds | 3 | 지역별 승인 간격 |
| eco.HerdMigration.KeepFraction | 0.25 | episode 시작 인원 기준 최소 잔류 비율 |
| eco.HerdMigration.FoodHorizonSeconds | 60 | 현재 먹이로 지원할 기간 |
| eco.HerdMigration.RecoveryFraction | 0.35 | 회복 종료 잔량 비율 |
| eco.HerdMigration.RecoverySeconds | 15 | 회복 유지 시간 |

기본 시험은 값을 바꾸지 않는다. 재시험은 게임 세션을 종료하고 새 Standalone을 실행해 먹이/episode를 초기화한다. 콘솔 설정이 세션 사이 유지될 수 있으므로 표시 값을 확인한다. `eco.HerdMigration 0`은 새 출발을 중단하고 진행 중인 이주는 마치게 한다. 이주 도중 Regional 모드나 KeepFraction을 바꾸는 시험은 검증 범위에 없다.

## 검증 증거와 남은 작업

- UE 5.8 직접 UBT `AdaptiveEcosystemEditor Win64 Development` 최종 빌드 성공.
- `Saved/RegionalMigration_20261109/Automation.log`: `AdaptiveEcosystem.Policy.V3.HerdMigration + AdaptiveEcosystem.Review.Herd + AdaptiveEcosystem.Life`, 13개 Success, 실패 0. 기존 맵의 missing foliage mesh MapCheck warning 1개가 있으며 신규 테스트 실패는 아니다.
- 신규 `RegionalOrderedBudget`: singleton 출발, 같은 Herd 일부 순차 승인, 동일 경계 중복 승인 방지, 12명 중 최대 9명 승인/잔류 3명, 반복 평가의 예산 유지 검증. 기존 NativeJourneyAndIdentity는 기존 모드의 실제 Native 이동/인계 회귀 검증이다.
- 기존 1102의 Standalone 관측은 첫 시도에서 관측 Python의 `use_v3_policy` 속성 접근 오류로 중단했다. 해당 접근을 제거한 뒤 재시도했으나 실행 중 엔진 감지로 시작하지 못했다. 이후 프로세스 확인 명령의 승인이 거절되어 추가 엔진을 시작하지 않았다. 실제 맵 성공으로 기록하지 않는다.
- 남음: 지역 12→8 지원 목표 중단 자동화, 다지역 목적지 경쟁/선택 순서 동점, 신규 모드의 실제 지형 이동/도착, death/return/cooldown 후 재시도, 지역 순서·episode 포함 저장 왕복, Dedicated/Client·late join 검증. 기존 legacy 모드의 테스트 성공을 새 모드 전체 성공으로 확대하지 않는다.

다음 실행은 남은 엔진 프로세스가 없는지 확인한 후 위 1102 명령과 `Saved/RegionalMigration_20261109/observe.py`를 사용한 관측부터 재개한다. 이 Python은 개발 관측 도구이며 런타임 정책 추론기가 아니다. 남은 검증 전 새 모드를 기존 맵의 기본 동작으로 강제 활성화하지 않는다.
