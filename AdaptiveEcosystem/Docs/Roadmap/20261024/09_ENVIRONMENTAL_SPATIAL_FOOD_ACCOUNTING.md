# T09. 환경 변화에 따른 공간 먹이 조정·보존 원장

상태: **F10 선택 시 구현하는 조건부 명세** / 기준: `8836558` / 책임 제안: 원준 자원 원장, 권신혁 Native food grid·Python, World 환경 변화.

선행: [T05](05_WORLD_WEATHER_AND_CLOCK_REPLICATION.md), [T06](06_DYNAMIC_OBSTACLE_REPLICATION.md)의 확정 환경 revision. 확인: [F10](99_DECISIONS_AND_CONFIRMATIONS.md).

## 1. 목적과 현재 구현

실행 중 나무·식생·환경 변화가 먹이 용량·현재량도 바꾸도록 선택할 때, 그 변화를 소비·재생과 구분해 한 번만 적용한다. Native 격자와 Ecology 지역 장부가 달라지는 문제를 막는다.

현재 RegisterSpatialFood는 지역별 source를 한 번 등록하고 용량/양을 지정한다. CommitSpatialFood는 증가하는 sequence, Before 일치, 유한값, 범위, Before-Consumed+Regenerated=After를 검사한다. 이 지역의 일반 자원 writer는 배제된다.

현재 EnvWatch의 새 나무는 Food를 바꾸지 않는다. Python snapshot도 같은 먹이 지도를 사용한다. 따라서 환경에 따른 Food 변경을 원하지 않으면 **현재 동작을 유지하고 T09를 Deferred로 닫을 수 있다.** 공간 먹이 연결 자체를 재구현하지 않는다.

## 2. 금지할 단순 해결

- CommitSpatialFood의 Before/상한/보존식 검사를 느슨하게 하지 않는다.
- 나무가 생겼다는 이유로 초기 food grid를 매번 다시 생성해 소비된 먹이를 복구하지 않는다.
- 양의 재생으로 음의 환경 손실을 감추거나 capacity 감소를 소비로 기록하지 않는다.
- Native와 Ecology에 각각 setter를 호출하고 부분 실패를 무시하지 않는다.
- 같은 지역의 기존 일반 재생·섭식 writer를 다시 켜지 않는다.

## 3. 조정 요청 제안

실제 API 이름은 구현 시 정한다. 팀 요청의 AdjustSpatialFood는 예시 이름이며 기존 함수가 아니다.

| 필드 | 계약 |
|---|---|
| WorldEpoch/RegionId/AdjustmentId | 권위 world·source·멱등성 key |
| EnvironmentRevision | 변경 원인과 적용 환경 |
| ExpectedFoodSequence/BeforeAmount/BeforeCapacity | 과거 상태의 조정 거부 |
| GridRevision/ChangeDescriptor | Native cell 변경 또는 그 검증 결과 |
| NewCapacity/NewAmount | 유한값, 0<=Amount<=Capacity, capacity 0 지원 정책 명시 |
| Reason | TreeAdded/Removed·VegetationChange 등 확정 사유 |
| EffectiveTime/NativeStep | 적용 논리 시각·세계 step |

결과는 Committed/Rejected/Stale·이전/이후량·실제 공급/손실·확정 revision·reason을 담는다. Client에는 현재 Food/Capacity 요약을 우선 전달하고 전체 grid는 별도 요구가 없으면 보내지 않는다.

## 4. 양·용량·단위 계약

```text
AfterAmount
 = BeforeAmount + Regenerated + Supplied
   - Consumed - EnvironmentLoss - OtherExplicitLoss
```

CapacityDelta와 AmountDelta는 다르다. capacity가 줄어도 현재량이 이미 새 capacity보다 작으면 추가 손실이 없을 수 있다. 초과량을 잘라야 하면 실제 잘린 양을 EnvironmentLoss로 기록한다.

capacity 증가가 곧 Food 공급을 뜻하지 않는다. F10 권고는 현재량을 유지하고 이후 합의된 재생 규칙이 채우는 방식이다. 즉시 공급을 선택하면 Supplied에 명시한다.

Native double 먹이 단위와 기존 V1/지역 float 표시를 구분한다. 단위 변환·허용 오차는 기존 spatial source 계약을 기준으로 정하고, 원장 오차를 표시용 반올림 차이와 구분한다. capacity=0은 현행 등록이 허용하지 않으므로 지원한다면 validation·depletion·pressure·division-by-zero를 모두 수정한다.

## 5. 안전 적용 순서

1. Native 계산이 끝나고 열린 resource step이 없는 지정 경계를 선택한다. 환경/먹이/summary step의 적용 순서를 기록한다.
2. 환경 revision과 기존 sequence·Before 상태를 검사하고 중복 AdjustmentId면 이전 결과를 반환한다.
3. 현재 grid를 바탕으로 영향받는 cell만 변경한 후보와 합·용량·명시 손실을 계산한다.
4. Native grid와 Ecology source 양쪽의 유효성을 전부 검사한다. 무효 요청은 어느 쪽도 바꾸지 않는다.
5. 같은 Game Thread commit 구간에서 후보 grid·source·revision·receipt를 함께 공개한다. 실행 중 view를 재할당하지 않는다.
6. 다음 일반 CommitSpatialFood의 Before는 새 확정 Amount를 사용한다. sequence를 중복·되감지 않도록 환경 receipt와 일반 step의 순서 계약을 정한다.
7. Food gradient·blur·observation cache를 필요한 범위에서 무효화하고 다음 관측을 갱신한다.
8. 완료 summary와 외부 학습 snapshot이 같은 확정 grid/revision을 보게 한다.

환경 적용과 자원 조정을 완전히 동시에 처리할 수 없다면 둘의 적용 revision과 지연을 명시한다. 연결 실패 때 일부 상태를 성공으로 publish하지 않는다. 복구 불가능한 원장 불일치는 기존 runtime stop 정책으로 드러낸다.

## 6. 환경별 규칙을 결정할 때

| 변화 | 결정할 내용 |
|---|---|
| 새 줄기·바위 | 덮인 cell의 capacity/양 감소 식·부분 면적 처리 |
| 나무 제거 | capacity 복원 범위, Food 즉시 복구 여부 |
| 불·벌목 | reason·손실량, 기존 소비와의 동시 사건 순서 |
| 비·눈 | 기존 감각/속도 효과만인지 재생 효과도 추가할지 |
| 반복 환경 감시 | 같은 원판 목록을 재발견해도 조정 0회 |

현재 v3 날씨에 재생 효과를 임의로 붙이지 않는다. 정책 결과를 바꾸는 규칙은 Python 구현·snapshot 변환·평가를 함께 갱신한다.

## 7. 멱등성·실패·스냅숏

같은 환경 revision·AdjustmentId는 한 번만 반영한다. 그 전에 일반 step이 진행돼 Before가 달라졌다면 stale 후보를 거부하고 최신 상태로 다시 계산한다. 옛 후보를 단순 델타로 더하지 않는다.

외부 학습 snapshot은 grid/용량/revision·변경 사유를 재현할 수 있어야 한다. 기존 변환기가 모르는 환경 변경은 조용히 생략하지 않고 거부 또는 명시적으로 미지원 처리한다. 모델 교체가 Food를 되돌리지 않게 한다.

## 8. 구현 단계

- FD-A: F10의 ON/OFF와 양·용량 규칙을 결정한다.
- FD-B: 기존 Register/Commit을 보존하며 조정 요청/결과·원장 항목을 추가한다.
- FD-C: Native candidate→검증→공통 commit·cache 갱신을 연결한다.
- FD-D: summary·Python snapshot·parity를 검증한다.
- FD-E: 반복·경합·0용량·실패 원장을 검증하고 결과를 T11에 넘긴다.

## 9. 검증 시나리오

| ID | 조건 | 기대 결과 |
|---|---|---|
| FD01 | 소비 후 나무 추가 | 이미 소비된 Food 복원 안 됨, 명시 손실 |
| FD02 | 제거로 capacity 증가 | 선택한 공급 정책, 공짜 재충전 없음 |
| FD03 | 같은 환경 revision 반복 | 조정 1회 |
| FD04 | 조정 대기 중 일반 소비 step | stale 거부/재계산, 원장 일치 |
| FD05 | capacity가 Amount 아래로 감소 | 초과 손실을 정확히 기록 |
| FD06 | NaN/음수/범위 밖/잘못된 epoch | 양쪽 상태 변경 0 |
| FD07 | 부분 초기화/commit 실패 | 부분 publish 없음, 진단 |
| FD08 | 조정 직후 일반 Commit | Before·sequence 정상 |
| FD09 | snapshot→Python mirror | 양·용량·변경 규칙 재현 또는 명시 거부 |
| FD10 | Client late join | 새 Food/Capacity 요약, 자원 역기입 없음 |

## 10. 완료 조건과 근거

F10 ON일 때만 기능 완료를 요구한다. Native 합과 Ecology 양이 단위·오차 계약 안에서 일치하고 명시 공급/손실을 포함한 보존식을 유지한다. OFF면 기존 격자 유지와 외형만 변하는 범위를 문서에 기록한다.

- [공간 먹이 등록·commit](../../../Source/AdaptiveEcosystem/Ecology/EcologySpatialFood.cpp)
- [일반 resource step](../../../Source/AdaptiveEcosystem/Ecology/EcologyResourceSimulation.cpp)
- [Native receipt](../../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp), [환경 변화 감시](../../../Source/AdaptiveEcosystem/AI/Policy/EcoV3EnvWatch.cpp)
- [공통 resource 형식](../../../Source/AdaptiveEcosystem/Core/EcoResourceTypes.h), [팀의 조정 API 요청](../../RL_Policy/TEAM_REQUESTS_V3.md)
