# 4단계 사슴 회피 적용 검증

[회피 통합 계획](09_AVOIDANCE_INTEGRATION_SPEC_20261112.md)의 4단계다. 개발용 명령은 권위 Play 월드 안에서 독립된 Native v3 실험 세계 두 개를 생성한다. 두 세계는 같은 R1b 내장 모델과 시드·배치로 시작하고, 회피 적용 여부만 다르다. 실험용 개체와 자원은 각 세계 안에 생성하므로 기존 맵을 Play 창의 호스트로 사용할 수 있다.

## Unreal Automation 클릭 순서

1. **Unreal Editor 5.8**에서 `AdaptiveEcosystem.uproject`를 연다. Play 중이면 상단 **Stop**을 누른다.
2. **Tools → Session Frontend → Automation**을 연다. 세션 선택 화면이 보이면 **Session Browser**에서 현재 로컬 에디터 세션을 선택한 뒤 **Automation**으로 돌아온다.
3. 검색창에 `AdaptiveEcosystem.Policy.V3.Movement.Avoidance`를 입력한다.
4. **AvoidanceAppliedComparison**, **AvoidanceTerrainGuard** 두 항목을 체크한다.
5. **Start Tests** ▶를 누르고 두 행의 **Success**를 확인한다. 목록이 비어 있으면 **Refresh Tests**를 누른다.

## 콘솔 비교 실행

1. 상단 **Play** 옆 **⋯ → Multiplayer Options**에서 **Number of Players = 1**, **Net Mode → Play Standalone**을 선택한다.
2. **New Editor Window (PIE)**를 선택하고 **Play**한다.
3. 게임 창에서 백틱 키를 누르고 `eco.MoveTest Run HeadOn`을 입력한다. 완료 후 `eco.MoveTest Run Graze`, `eco.MoveTest Run Flight`를 같은 방식으로 하나씩 실행한다.
4. **Output Log**에서 `Mode=OffVsEnabled`를 검색한다. 완료 줄의 `RunId`와 `Path`를 확인한다.

기본값은 모드당 90 Native 스텝, 시드 20000이다. 예를 들어 `eco.MoveTest Run Graze 120 20001`로 바꿀 수 있다. 진행 확인은 `eco.MoveTest Status`, 중단 결과 저장은 `eco.MoveTest Stop`을 사용한다.

| 장면 | 비교하는 내용 |
| --- | --- |
| `HeadOn` | 같은 선에서 마주 오는 두 사슴의 방향 반전, 몸통 겹침, 접촉 거절과 목표 도착 |
| `Graze` | 원형 장애물을 돌아 목표 쪽으로 복귀하는 사슴과 그 경로에 놓인 제자리 섭식 개체의 간격, 도착과 섭식량. 정지 개체의 초기 먹이 셀은 두 모드에 같은 양을 배치한다. 회피 후보는 기존 detour 이후의 속도를 사용한다. |
| `Flight` | 도주 반사의 놀람 정지가 끝난 첫 이동 스텝에서 시작한다. 앞에 정지 개체를 두고 회피 제안이 있어도 두 세계의 Native FLEE 속도·이동 시작 스텝이 일치하는지 본다. |

```text
[Eco MoveTest] Passed RunId=<id> Scenario=HeadOn Mode=OffVsEnabled Steps=90/90 Seed=20000 AppliedRows=<count> Reason=AppliedComparisonChecks Path=<path>
```

## 결과 확인

- `Saved/Profiling/EcoMovement/<RunId>/Summary.json`에는 Off/Enabled별 실제 반전, 겹침, 목표 도착, 섭식, 도주 시작 및 이동 스텝이 있다. `Samples.csv`는 기존 목표 조향과 분리, detour 전후, 제안, 적용 제어와 실제 변위를 cm 단위로 담는다. 섭식은 Native 먹이 단위다. 위험 후보 평가는 Enabled에서 수행한다.
- 첫 스텝의 고정 입력에서 실행 행동·요청·마스크를 비교한다. 이후에는 이동이 다음 관측에 반영된다. 정지 또는 긴급 행동의 속도 변경, 겹침 증가, Off에서 완료한 목표의 상실, 섭식 상실은 실패로 표시한다. 장면을 충분히 지나지 못했거나 도주가 시작되지 않은 실행은 `Incomplete`로 표시한다.
- `EncounterNotCovered`는 Enabled에서 위험 간격에 진입한 행이 0개인 경우다. `AvoidanceNotApplied`는 위험 행이 있고 적용 행이 0개인 경우다. 자동화 실패 줄에 위험·적용·detour 행 수와 섭식량을 표시한다.
- 방향 반전은 동일 목표에서 연속한 두 실제 변위의 내적이 음수인 경우다. 도착은 목표 반경 24cm에 처음 들어간 시점이다. 두 모드의 도주 이동 시작 차이 목표는 0스텝이다. 반전 30% 감소와 도착·성능의 제안 문턱은 별도로 수치를 비교한다. `native_step_p95_us`는 이 두 개체 실험의 측정값이며 성능 판정에는 더 긴 고정 조건의 측정이 필요하다.
- Native는 지형 우회 직후의 동일 시점에서 회피를 제안받고, 제약을 만족하는 속도만 기존 이동 경로에 전달한다. 측정 범위는 실험 세계의 Native 이동과 섭식이다.
