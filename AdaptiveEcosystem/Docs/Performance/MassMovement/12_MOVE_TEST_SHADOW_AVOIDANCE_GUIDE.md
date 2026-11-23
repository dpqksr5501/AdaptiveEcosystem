# 사슴 예측 회피 비교

[회피 통합 계획](09_AVOIDANCE_INTEGRATION_SPEC_20261112.md)의 3단계다. `ShadowHeadOn`은 두 사슴이 같은 선을 따라 서로 접근하는 장면, `Crossing`은 두 경로가 직각으로 만나는 장면이다. `Run HeadOn`은 [4단계 실제 적용 비교](13_MOVE_TEST_APPLIED_AVOIDANCE_GUIDE.md)를 연다.

## Native 비교 실행

1. Unreal Editor 5.8에서 본인 레벨을 연다.
2. 상단 **Play** 옆 **⋯ → Multiplayer Options**에서 **Number of Players = 1**, **Net Mode → Play Standalone**을 설정한다.
3. **New Editor Window (PIE)**를 선택해 **Play**한다.
4. 게임 창에서 **백틱**을 누르고 `eco.MoveTest Run ShadowHeadOn`을 입력한다. **Output Log**에서 `Scenario=HeadOn Mode=Shadow`를 검색해 완료 줄과 저장 경로를 확인한다.
5. 완료 후 같은 게임 콘솔에 `eco.MoveTest Run Crossing`을 입력한다. **Output Log**에서 `Scenario=Crossing`을 검색한다.

기본값은 90 Native 스텝, 시드 20000이다. 마지막에 스텝과 시드를 지정할 수 있다. 예를 들어 `eco.MoveTest Run Crossing 120 20001`이다. 진행 확인은 `eco.MoveTest Status`, 중단 결과 저장은 `eco.MoveTest Stop`을 사용한다.

```text
[Eco MoveTest] Passed RunId=<id> Scenario=HeadOn Mode=Shadow Steps=90/90 Seed=20000 MismatchMask=0 RiskRows=<count> ProposedRows=<count> Reason=ShadowParityAndCoverage Path=<path>
```

`Passed`는 두 사본의 Native 관측·결정·이동·난수·먹이 결과가 일치하고, 위험 상대와 회피 제안을 실제로 기록했다는 뜻이다. 접촉 전에 끝낸 짧은 실행은 `EncounterNotCovered`로 끝날 수 있다.

## 보고서 읽기

- 각 장면은 현재 Play 월드와 분리된 평면 Native 세계 두 개를 같은 위치·목표·시드로 시작한다. 목적지 조향을 시나리오에서 지정하고 기존 Life 분리 함수, 접촉 검사 및 Native 이동을 재사용한다. 활성 레벨의 개체는 기존 실행을 계속한다.
- `Samples.csv`는 사슴별로 목표·기존 분리 델타·실제 변위·제안 델타를 cm 또는 cm/스텝으로 기록한다. 예측은 이동 전 동일 시점의 XY·계획 속도·몸 반경을 읽고 8스텝 안의 최소 몸통 간격을 계산한다. 몸 가장자리 간격이 음수면 원형 몸통이 겹치는 예측이다.
- `existing_local_gap_cm`·`proposed_local_gap_cm`은 다른 사슴의 기존 움직임을 고정했을 때의 비교다. `threat_id=0`인 행은 보존된 상대가 없으므로 이 두 값을 해석에서 제외한다. `combined_proposal_pair_gap_cm`은 양쪽에 제안을 동시에 가정한 값이다. `actual_swept_pair_gap_cm`은 실행된 시작·끝 위치를 한 스텝 동안 선형 보간해 구한 간격이다.
- 위험 후보는 최소 예측 간격·그 시점·ID 순서로 최대 8개를 유지한다. 초과 후보 수, 근접 평가 횟수, 제안 함수 자체의 소요 시간을 기록한다. 두 사슴 장면에서 초과 후보는 0이며 별도 자동화에서 상한을 검증한다.
- `Summary.json`에는 동등성 결과와 예측 간격 개선·악화 스텝이 있다. 제안을 적용한 주행 결과와 실제 레벨 지형·Mass·M4·표현의 검증은 후속 단계 범위다.

## Unreal Automation 테스트 클릭 순서

1. Play 중이면 상단 **Stop**을 누른다.
2. **Tools → Session Frontend → Automation**을 연다.
3. 검색창에 `AdaptiveEcosystem.Policy.V3.Movement.Avoidance`를 입력한다.
4. **AvoidanceShadowParity**와 **AvoidanceCandidateLimit**을 체크한 뒤 **Start Tests** ▶를 누른다.
5. 두 행의 **Success**를 확인한다. `Summary.json`과 `Samples.csv`는 위 콘솔 절차에서 생성된다.
