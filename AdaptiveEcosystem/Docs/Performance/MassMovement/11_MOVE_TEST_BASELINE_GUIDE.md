# Native v3 동족 탐색 비교

[회피 통합 계획](09_AVOIDANCE_INTEGRATION_SPEC_20261112.md)의 2단계다. 기존 [공간 탐색](../SPATIAL_SEARCH_20261106.md)의 전체 탐색과 동족 인덱스 경로를 같은 Native Step에서 비교한다. 1단계 `Observe`로 기록된 실제 맵 장면은 [관찰 가이드](10_MOVE_TEST_OBSERVE_GUIDE.md)를 따른다.

## 내 레벨에서 Baseline 실행

1. Unreal Editor 5.8에서 사용할 레벨을 연다.
2. 상단 **Play** 옆 **⋯ → Multiplayer Options**에서 **Number of Players = 1**, **Net Mode → Play Standalone**을 설정한다.
3. **New Editor Window (PIE)**를 선택해 **Play**한다.
4. 게임 창을 클릭하고 **백틱** 키로 콘솔을 연다. `eco.MoveTest Run Baseline`을 입력하고 **Enter**를 누른다. 사슴 선택은 필요 없다.
5. **Output Log**에서 `Scenario=Baseline`을 검색한다. `Passed` 또는 `Failed` 줄의 `RunId`와 `Path`를 확인한다.

기본값은 배치별 90스텝, 시드 20000이다. `eco.MoveTest Run Baseline 180 20001`처럼 스텝과 시드를 바꿀 수 있다. 진행 중에는 `eco.MoveTest Status`를 사용한다. `eco.MoveTest Stop` 또는 Play 종료 시 수집분을 `Incomplete`로 저장한다.

예상 완료 줄:

```text
[Eco MoveTest] Passed RunId=<id> Scenario=Baseline StepsPerLayout=90/90 Seed=20000 MismatchMask=0 Reason=ExactNativeParity Path=<project>/Saved/Profiling/EcoMovement/<id>
```

## 보고서 범위

- 명령은 Play 세션에 속한 별도 Native fixture에서 실행한다. 각 배치를 두 번 동일하게 초기화하고 동족 탐색 경로만 다르게 지정한다. 내장 R1b, 같은 지형 입력과 시드, 사슴 128마리 분산 배치 및 사슴 32마리 소규모 배치를 사용한다.
- 모든 사슴의 제어가 끝나고 첫 이동이 시작되기 전에 Native 행 순서대로 위치, 직전 변위, 방향, 예정 변위, 행동·보행·정지·도주 상태를 값으로 복사한다. 격자 쿼리와 전체 탐색은 같은 동족 지각 함수와 누산 순서를 사용한다.
- `Summary.json`과 `Samples.csv`는 초기 상태(스텝 0), 스텝별 비교 및 후보 수를 담는다. 마스크 값은 동족 기하 1, 관측 2, 정책·마스크·요청 4, 이동 8, RNG 16, Native 먹이·생명주기 장부 32, 이동 전 복사본 64이며 여러 차이는 합산 비트로 표시한다.
- `Passed` 조건은 두 배치 모두 차이 0, 분산 배치의 격자 후보 감소, 소규모 배치의 전체 탐색 사용이다. 실제 맵 지형·Mass·M4 권위 장부·복제 및 표현은 이 보고서의 미측정 항목이다.

## Unreal Automation 테스트 클릭 순서

1. Play 중이면 상단 **Stop**을 클릭한다.
2. **Tools → Session Frontend → Automation** 탭을 연다.
3. 검색창에 `AdaptiveEcosystem.Policy.V3.Movement.BaselineParity`를 입력한다.
4. **BaselineParity** 체크박스를 선택하고 **Start Tests** ▶를 클릭한다.
5. 테스트 행에서 **Success**를 확인한다. 콘솔 명령과 파일 저장까지 확인하려면 위의 Play 절차를 실행한다.
