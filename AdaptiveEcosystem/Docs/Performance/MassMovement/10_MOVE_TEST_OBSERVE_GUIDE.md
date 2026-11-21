# 사슴 이동 관찰 실행 가이드

[회피 통합 계획](09_AVOIDANCE_INTEGRATION_SPEC_20261112.md)의 1단계다. 관찰은 현재 실행 중인 Native v3 사슴의 기록을 수집한다. 정책, 시드, 초기 배치 및 이동 규칙은 현재 세션 설정을 사용한다.

## 에디터에서 관찰 기록 만들기

1. Unreal Editor 5.8에서 `AdaptiveEcosystem.uproject`를 연다. **Content Drawer**를 클릭하고 `LV_JYU_IslandEcosystemRefreshed`를 검색해 레벨 에셋을 더블클릭한다. 경로는 `Content/JYU/Maps`다.
2. 상단 툴바 **Play** 옆 **⋯** 메뉴를 클릭한다. **Number of Players**를 **1**, **Net Mode**를 **Play Standalone**, 실행 창을 **New Editor Window (PIE)**로 지정한다.
3. **Play**를 누른다. 게임 창을 클릭하고 사슴이 나타날 때까지 기다린다. 사슴을 화면에 두고 **마우스 가운데 버튼**을 누르거나 **Tab**을 반복해 **ECO INSPECTOR**에 `Herbivore #…`가 표시되게 한다.
4. 게임 창에서 **백틱** 키를 눌러 콘솔을 연다. `eco.MoveTest Observe`를 입력하고 **Enter**를 누른다. 다른 사슴을 ID로 지정하거나 길이를 바꾸려면 `eco.MoveTest Observe <StableAgentId> <Steps>`를 입력한다. 예를 들어 ID가 123이면 `eco.MoveTest Observe 123 90`이다.
5. 화면 아래 `MoveTest Observe` 진행 표시를 확인한다. 기본 90 Native 스텝은 12 게임초다. 기록 도중 **eco.MoveTest Status**로 스텝과 경로를 확인하고 **eco.MoveTest Stop**으로 수집분을 저장할 수 있다.
6. 완료 후 에디터 하단 **Output Log**를 클릭하고 `[Eco MoveTest]`를 검색한다. `Recorded` 줄의 `RunId` 또는 줄 전체를 전달한다. Windows 탐색기 주소창에 같은 줄의 `Path`를 붙여넣으면 세 파일을 열 수 있다.

```text
[Eco MoveTest] Recorded RunId=<id> Agent=123 Mode=Authority Native=90/90 Visual=<count> Reason=Completed Path=<project>/Saved/Profiling/EcoMovement/<id>
```

직접 **Stop**하거나 대상이 사망하거나 Play가 끝나면 `Incomplete`와 이유를 기록한다. Client 콘솔에서 같은 명령을 실행하면 현재 표현되는 사슴을 같은 게임 시간 동안 관찰한다. 이때 권위 스텝·정책은 서버에서 별도로 기록하며, 전용 서버 콘솔에서는 StableAgentId를 직접 지정한다.

## 보고서 읽기

- `Summary.json`에는 실행 환경, 시드와 모델, 측정 길이, 관찰 결과 및 누락 트랙이 들어 있다. `Recorded`는 관찰 수집 결과이며 회피 성능 판정은 후속 단계에 해당한다.
- `Samples.csv`는 권위 스텝당 한 행이다. `base`는 Native repertoire 제어 출력, `pre_adapter`는 Native 도주·경계 조정 후, `pre_detour`는 통합 제어와 속도 배수 적용 후, `final`은 장애물·해안 조향 후의 예정 이동이다. `actual`은 Native 위치의 실제 차이다. 이 벡터들의 단위는 cm/스텝이다. 차단된 접촉·지면 후보의 횟수는 별도 열에 있으며, 대체 방향이 승인되면 실제 이동이 생길 수 있다.
- `goal_kind`와 `goal_id`가 명시된 행은 해당 목표를 비교할 수 있다. `None`은 점 목표가 기록되지 않은 경우이며 도주 방향은 `flee_dir`에 남는다. 동일 명시 목표는 같은 지역·행동에서 목표 종류와 ID가 같고 XY가 25 cm 이내인 연속 스텝이다. 반전은 이전·현재 이동 길이가 각각 1 cm 이상이고 내적이 음수인 경우다.
- `VisualSamples.csv`는 로컬 Actor 실제 yaw와 표현 입력을 최대 30 Hz로 기록한다. Native 스텝과 표현 프레임의 빈도는 다르며, `world_s` 및 `native_samples_collected`로 같은 관찰 구간을 찾는다. 표현이 없는 Dedicated 권위 실행은 `NoLocalRepresentationSamples`를 기록한다.

## 기존 Unreal Automation 회귀 테스트

1. Play 중이면 상단 **Stop**을 클릭한다.
2. **Tools → Session Frontend → Automation**을 연다.
3. 테스트 검색창에 `AdaptiveEcosystem.Policy.V3.Integrated`를 입력해 Native v3 통합 항목을 펼친다.
4. **BlockedMoveHooks**, **TerrainBlocking**, **MultiStepDeathExclusion** 체크박스를 선택한다.
5. **Start Tests** ▶를 클릭하고 각 항목의 결과를 확인한다. `eco.MoveTest Observe`와 파일 저장 자체는 위의 Play 절차에서 확인한다.
