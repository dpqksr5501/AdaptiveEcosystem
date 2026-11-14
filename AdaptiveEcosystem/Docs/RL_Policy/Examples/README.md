# soil/life 실제 관찰 예제

작성일: **2026-10-24**. `d095948`의 구현을 검증한 **2026-10-23 실제 QA snapshot**에서 필요한 행을 그대로 골랐다. 전체 원본은 로컬 `Saved/EcosystemLife_20261023`에 있으며 Git에 포함하지 않는다. 이 작은 파일은 clone한 팀원이 데이터 모양·관찰/정답 차이를 먼저 확인하기 위한 자료다.

## 엔진 없이 실행하는 섬 대조

저장소 루트에서 Python 3.10 이상과 표준 라이브러리만으로 아래 명령을 실행한다. Dots에서 기존 학습용 sparse checkout을 쓰는 경우 섬 자료가 포함된 커밋에서 `git sparse-checkout add AdaptiveEcosystem/Tools/EcoVegetationEval`을 먼저 실행한다. 발췌는 Unreal 기록의 대응 검사에 쓰는 부분 자료이며, 신규 종의 학습 세계 설정과 관측 입력은 별도 인계 대상이다.

```bash
examples=AdaptiveEcosystem/Docs/RL_Policy/Examples
checks=AdaptiveEcosystem/Tools/EcoVegetationEval

python "$checks/check_forage_stock_parity.py" --authority-fixture "$examples/island_forage_stock_authority_20261114.json" || exit
for scene in ground_food_choices flooded_ground_forage forage_guild_comparison forage_meal_cap; do
  python "$checks/check_ground_food_choice.py" "$examples/island_${scene}_20261114.json" || exit
done
for scene in water_access_geometry water_food_connectivity carp_food_choices nursery_reservation; do
  python "$checks/check_water_access_parity.py" "$examples/island_${scene}_20261114.json" || exit
done
for scene in water_access_geometry flooded_ground_forage; do
  python "$checks/check_island_shore_world.py" "$examples/island_${scene}_20261114.json" || exit
done
for scene in water_food_connectivity carp_saved_drawdown nursery_reservation shared_forage_drawdown; do
  python "$checks/check_island_water_world.py" "$examples/island_${scene}_20261114.json" || exit
done
python "$checks/check_eagle_hunt_reference.py" "$examples/island_eagle_contact_reference_20261114.json" || exit
python "$checks/check_island_eagle_world.py" "$examples/island_highland_eagle_actual_20261114.json" || exit
python "$checks/check_river_rat_refuge.py" "$examples/island_river_rat_refuge_geometry_20261114.json" || exit
python "$checks/check_island_rat_world.py" "$examples/island_river_rat_refuge_geometry_20261114.json" || exit
python "$checks/check_island_ground_passage.py" "$examples/island_transition_habitat_actual_20261113.json" || exit
python "$checks/check_player_passage.py" "$examples/island_player_passage_20261114.json" || exit
python "$checks/check_ground_hunt_value.py" "$examples/island_leopard_hunt_value_20261114.json" || exit
python "$checks/check_catfish_food_switch.py" "$examples/island_catfish_food_switch_20261114.json" || exit
python "$checks/check_water_day_night.py" || exit
```

같은 실측 수심으로 [Python 수중 환경](../../../Tools/EcoVegetationEval/island_water_reference_world.py)에 이동·섭식 요청을 직접 넣을 수 있다. 두 시드에서 메기·잉어·소형어류의 작은 체급은 저수위의 얕은 칸에 들어갔고, 성체 크기는 높은 수위에서 통과했다. 가상의 자원점을 하나 둔 장면에서는 저수위에 접근·섭취가 막혔고, 고수위에 이동 후 재고에서 0.75를 지급했다. 퇴수 뒤에는 같은 자원의 관측과 섭취가 막혔다. 이동은 1.5m 격자의 네 방향에 한정한다. 자원점·재생·목표 행동은 시험 입력이며 연속 충돌, 유속, 산란, 체력 소모와 R9 감각·행동 계약은 후속 구현 범위다.

```bash
python AdaptiveEcosystem/Tools/EcoVegetationEval/check_island_water_world.py \
  AdaptiveEcosystem/Docs/RL_Policy/Examples/island_water_food_connectivity_20261114.json
```

같은 두 시드의 수심 격자에서 얕은 둑과 본류에 가상의 먹이를 두고 재고와 도달 가능성이 다음 선택에 미치는 영향을 계산했다. 갈수기에는 본류를 선택했고, 물이 차면 같은 거리의 재고가 더 많은 둑 먹이로 바뀌었다. 둑에서 0.75를 먹고 재고가 고갈되면 다음 선택은 다시 본류였다. 퇴수 때 둑에 있던 개체는 현재 칸부터 유영에 필요한 깊이를 잃었고, 재침수한 뒤 본류에 도착해 0.5를 지급받았다. 격자 연결과 거리당 섭취 가치에 따른 개발용 시험이며, 먹이 위치·재고는 통제 입력이다.

Drift에서 SlowShelf까지의 실측 격자도 같은 검사에서 실행한다. 시드 20000·20017의 저수위·고수위·퇴수에서 소형어류 성체 체급으로 각 71칸(106.5m)을 이동했다. 직선 표본 중 15곳은 유효 수주가 없었고 목적지는 낮·밤 모두 시작점의 먹이 감지 범위 밖이었다. 알려진 목적지를 향해 격자 이동을 요청하고, 목적지에 놓은 시험 먹이는 도착 전 지급 0, 도착 후 지급 0.5를 확인했다.

같은 격자에서 목표 좌표를 모르는 제어 탐색기는 인접 칸의 수심과 자체 방문 기억으로 이동한다. 환경이 감지 범위 안의 먹이를 알리면 현재 위치 기준 방향을 읽고, 먹이터에 도착해 섭식을 요청한다. 두 시드와 세 수위 모두 낮 159번째, 밤 160번째 이동에서 처음 감지했고 161번째 이동 후 0.5를 지급했다. 71칸은 모든 격자 깊이를 사용할 수 있는 알려진 목적지 대조값이다. 탐색기의 방문 순서와 격자 이동 수는 시험 결과이며 실제 Unreal 개체의 유영 궤적이나 행동 시간으로 쓰지 않는다.

Python 먹이 감지는 감지 반경 안에서 이어진 수주만 확인한다. 차단물 너머 먹이까지 반경 밖 우회로를 열어도 관측은 그대로였고, 반경 안에 수로를 열자 먹이 방향이 나타났다. 이 조건은 Python 격자에서 먼 지형 상태가 관측에 섞이는 것을 막는다. Unreal의 실제 수중 시야와 물을 통한 감지 판정은 별도 대응 범위다.

수위가 탐색 도중 바뀌는 제어 시험에서는 되돌아갈 칸이 체급에 필요한 깊이 아래로 얕아졌다. 탐색기는 이전 경로를 재사용하기 전에 현재 수심을 확인하고, 이동할 수 있는 칸이 없으면 대기한다. 인접한 선반이 다시 잠기면 그쪽에 도달한 뒤 0.5를 지급받는다. 이 시험의 물 높이와 네 칸 배치는 Python 입력이다.

`WaterForagingEpisode`는 이 격자를 초기화하고 순서대로 행동을 받을 수 있게 묶는다. 다음 관측에는 그 결정에 적용될 수위와 남은 먹이가 함께 들어간다. 두 시드의 실측 수심으로 본류 감지 → 범람한 둑 섭취 → 퇴수 중 이동 거절 → 재침수 후 본류 복귀와 섭취를 한 번에 실행했다. 초기화하면 위치·에너지·재고·수위·스텝이 복원됐고, 같은 행동을 다시 넣었을 때 전체 관측과 결과가 일치했다. 종료는 시험의 스텝 상한이며, 학습 보상·PPO 관측 규격·생존 종료 조건은 별도 계약이다.

두 시드의 실제 하류 수심 지도를 같은 실행 중에 고수위 → 퇴수 → 고수위 순서로 바꾸는 시험도 추가했다. 얕은 칸의 퇴수 깊이는 잉어 약 8.23cm, 메기·소형어류 약 5.06cm였다. 고수위에는 두 체급 모두 진입했고, 퇴수 직후에는 0.75 체급만 시험 먹이 0.5를 지급받고 돌아왔다. 성체는 격자에서 재침수 후 돌아왔다. 이 장면의 먹이와 수위 변경 시점은 통제 입력이다. Unreal 유영기는 주변 18cm의 물을 찾아 짧게 후퇴할 수 있고, 실제 물속 지급은 별도의 1cm 수주 검사를 사용한다. 이 차이를 수심별 접근·권위 섭취의 후속 대조점으로 남긴다.

격자와 별도로 Unreal의 18cm 근거리 후퇴 규칙을 Python에서 재생한다. 실제 선반에서 측정한 깊이를 제어된 방향에 배치해 가장 깊은 통과 후보, 충돌로 인한 대체 방향, 모든 후보가 막힌 경우를 검사했다. 시험 속도·상태의 한 스텝 이동은 최대 3.9cm였고, 깊이가 충분했던 작은 체급에는 후퇴가 발동하지 않았다. 방향별 배치와 충돌 결과는 통제 입력이며 실제 Unreal 회복 궤적과 섭식은 별도 비교 대상이다.

[잉어 치어 퇴수 표본](island_water_access_geometry_20261114.json)에서는 몸 전체가 들어갈 수 있는 수주가 남아 있었지만 치어의 첫 위치가 수면 위에 있었다. Python에서 수주가 유효하면 18cm 주변 후퇴 탐색이 발동하지 않았고, 다음 위치를 그 수주의 몸 중심 높이 범위로 제한했다. 두 시드의 Unreal 후속 표본에서 잠긴 위치를 확인했고, 그 표본의 권위 시각에서 각각 2·1초 뒤 선반 섭취가 기록됐다. Replay에서 추진과 유속을 0으로 고정해 높이 제한만 확인했다. Unreal 위치 표본은 약 0.27 PIE초 간격이며 중간 스텝의 유영 방향과 충돌은 기록하지 않았다.

같은 치어 표본에서 실제 지급 전의 섭식 기하를 별도로 대조했다. 수면 위 첫 위치는 실패했고, 선반을 선택한 뒤 처음 사정거리 안에 기록된 위치는 두 시드에서 각각 18.9·20.1cm로 35cm 조건을 통과했다. Unreal은 섭식용 수주에 1cm 여유를 적용한다. Python 통제 시험은 그 경계, 거리, 개체의 잠김과 먹이점의 잠김을 확인한다. 실제 지급에는 정지·허기·시야·재고 검사도 필요하며, 표본은 권위 지급 직전의 모든 조건을 기록하지 않았다.

소형어류 112번의 권위 섭식에는 별도 지급 진단을 추가했다. 두 시드의 공유 접근점 300게임초 실행에서 실제 지급 20·21건의 수주·거리·에너지 여유·재고 차감을 Python으로 검산했다. 첫 지급은 사정거리 약 5cm에서 2.8을 지급하고 재고 11을 8.2로 차감했다. 진단은 정지·허기 등 앞선 조건을 통과해 수중 먹이터를 검사할 때만 기록한다. 이번 구간은 진단에 들어온 미지급 건이 없었다. 연결 격자 JSON의 `water_payment_attempts`에서 원본 해시와 각 지급을 확인할 수 있다.

Unreal의 `AdaptiveEcosystem.Fauna.Water.DayNightMovement` 자동화는 권위 섭식 함수에 이미 고른 군락을 전달한다. 퇴수로 먹이점만 드러난 경우, 개체만 수면 위로 나온 경우, 사정거리 밖, 이동 중, 최소량 미만, 수중 장애물로 시야가 막힌 경우에는 에너지와 재고가 각각 그대로였다. 장애물 충돌을 해제한 뒤에는 같은 먹이점에서 정확히 2를 지급하고 차감했다. 이 거절 사례는 제어된 테스트 수조에서 실행했다. 원본 보고서는 `Saved/Automation/IslandWetRejection/index.json`이다.

연결 격자 JSON의 `water_meal_control`은 같은 수조의 후속 자동화에서 저장한 좌표·수면·정지·시야·재고 입력과 실제 지급 결과다. Python에 같은 입력을 전달해 거절 6건과 정상 거래 1건의 지급량·잔량을 모두 재현했다. 정지와 시야는 Unreal의 기록에서 읽고, Python은 잠김·거리·한 입 상한·에너지 여유·최소 지급량을 계산한다. 선택 이전의 허기와 경로 행동은 이 시험의 고정 조건이다. 원본 보고서는 `Saved/Automation/IslandWetMealParity/index.json`이다.

```powershell
./AdaptiveEcosystem/Tools/Editor/run_jyu_island_audit.ps1 -Mode Population -PopulationSeconds 300 -Label wet_payment -WaterFoodAuditAgent 112 -Scenario @('-EcoIslandWaterForageShared')
```

실제 Unreal의 짧은 접근은 연결 격자 JSON의 `shared_underwater_access.first_approach`에서 별도로 확인한다. 두 시드의 소형어류 112번은 기준 배치와 추가 접근점 시험에서 처음 먹이를 찾기 시작한 181.033초까지 같은 위치였다. 기준 배치에서는 군락을 선택하지 않았다. 추가점을 선택한 개체는 거리가 53.6·54.1cm에서 23.9·22.6cm로 줄었고, 183초에 각 2.8을 지급받았다. 다음 표본의 거리는 4.9·5.0cm였다. 위치와 허기 상태는 약 1초 간격 표본이고 지급은 권위 거래다. 실제 하류의 장거리 우회 유영과 지급 순간의 정밀 위치는 이 표본에서 확인할 수 없다.

장거리 우회의 물리 조건은 `water_grid.*.surveys.*.detour_edges`에서 확인한다. 두 시드와 세 수위의 경로 426구간에서 25cm 간격의 실제 Unreal 수주를 읽고 소형어류 성체 체급의 구체 충돌을 검사했다. 모든 구간에서 공통 유영 높이와 수평 충돌 여유가 있었고, 인접 구간의 유영 높이 범위도 겹쳤다. 구체 검사는 구간마다 공통 유영 높이의 중간에서 수행했다. 1.5m 격자 중심에서 이어지는 수직 전환 420곳도 같은 구체로 검사해 모두 통과했다. 가장 큰 높이 차이는 저수위·퇴수 약 28.1cm, 고수위 약 24.3cm였다. 실제 개체의 경로 선택과 유영 실행은 별도다. 재현할 때는 위 섬 실행기에 `-EcoIslandShoreRainTrial`, `-EcoIslandSurveyWaterForage`, `-EcoIslandVerifyWaterDetour`를 전달한다.

`small_fish_runtime_coverage`에는 기본 배치·공유 접근점·재고 분산을 두 시드에서 실행한 60게임분 로그의 소형어류 위치와 지급 기록이 있다. 일곱 창시 개체의 최대 직선 이격은 처음 관측 위치에서 1.58m였고, 선반에 가장 가까운 표본은 71.38m 떨어져 있었다. 세 배치 모두 지급은 출발지 주변의 Drift 또는 임시 분산 군락에서 발생했다. 위치는 대략 30게임초 간격이며 최대 이격은 누적 이동 거리가 아니다. 현재 유영기는 목표가 없으면 정해진 Home 주변에서 목표를 고른다. 장거리 탐색의 후속 대조에서는 먹이 예산을 고정하고, 기억한 지점과 탐색 중 감지한 지점을 구분하면서 실제 경유와 외부 군락의 지급을 확인한다.

[수중 공유 먹이의 저장·복원과 퇴수](island_shared_forage_drawdown_20261114.json)는 용량 11인 Drift 한 군락에서 접근점 두 곳이 순차 차감한 실제 지급을 재생한다. 두 시드 모두 별도 프로세스에서 접근 좌표와 재고를 복원했다. 수면을 38.3cm 낮춘 20게임초 동안 잠긴 원래 지점에서만 네 건씩 지급했고, 수위 복구 약 5~7게임초 뒤 다시 추가점에서 지급했다. Python은 각 지점의 실측 수심과 영양 거래를 대조한다. 동시 첫 거래 이후의 대조는 Unreal 영수증에서 지급 직전 재고를 복원한다. 추가점은 PIE에만 배치했고 자료는 `training_ready=false`다.

Python의 `SharedWaterForaging`은 한 스텝에 들어온 여러 개체의 요청을 고정된 처리 순서로 정산한다. 두 시드에서 세 개체의 같은 시각 Unreal 지급을 두 접근점과 한 재고로 재현했다. 퇴수 대조에서는 노출된 지점의 요청을 거절하고 잠긴 지점에만 지급했다. 재생은 개체 수와 무관하게 한 번만 적용하며, 퇴수 대조의 재생량 0.125는 통제 입력이다. 같은 위치로의 이동은 허용하므로 신체 간 충돌과 자리 경쟁은 별도 대응 범위다.

연결 격자 JSON의 `water_stock_ledger`는 실제 섬 300게임초에서 Drift의 재생과 두 접근점의 지급을 한 줄씩 이어 검산한다. 두 시드에서 재생 갱신 306·302건과 지급 36·36건이 일치했다. 기본 재생률 0.13/s, LowerRiver 강수 입력 0.35에서 재고 11로 시작해 약 14.069를 재생했다. 시드별 잔량은 약 0.361·0.120이었다. 이번 실행의 강수 입력은 일정했고, 지급량은 원본 로그의 세 자리 정밀도에서 대조했다. 다음 갱신 전 재고도 직전 지급 뒤 잔량과 일치하는지 확인한다.

```powershell
./AdaptiveEcosystem/Tools/Editor/run_jyu_island_audit.ps1 -Mode Population -PopulationSeconds 300 -Label drift_stock_ledger -Scenario @('-EcoIslandWaterForageShared', '-EcoIslandAuditDriftStock')
```

같은 진단에 `-EcoIslandDriftRainPulse`를 추가하면 약 205~245 권위초 사이 LowerRiver 강수 입력만 0.35에서 0.85로 올렸다 내린다. 비가 강한 동안 저장 한도에 닿지 않은 Drift의 실제 재생은 두 시드 모두 초당 0.12025에서 0.15275로 약 27% 증가했고 이후 원래 재생률로 돌아왔다. 강수 대조의 갱신 611건과 지급 76건을 Python에서 원본 로그 정밀도로 검산했다. 강수 일정은 PIE에 주입한 실험 입력이며 시각 연출이나 실제 하천 생태의 반응 속도를 판정하는 시험과 구분한다.

Python의 공동 스텝에서도 Drift와 같은 일반 수중 군락에 경과 시간과 강수를 전달할 수 있다. 재고 0에서 강수 0.35를 1초 적용하면 0.12025로 최소 섭취량 아래였고, 이어 강수 0.85를 1초 적용하면 0.273으로 한 번의 지급이 가능해졌다. 퇴수 상태에서는 잠긴 접근점에서만 이 재고를 관측하고 지급받았다. 이 대조는 실측 접근점 수심과 런타임의 일반 군락 재생식을 사용한다. 계절성 수생 식생의 수심별 생장·건조 손실은 별도다.

계절성 군락은 Unreal의 `AdaptiveEcosystem.Fauna.Water.SeasonalFoodStock` 제어 수조를 Python 공동 스텝에서 따로 재생한다. 먹이점 위로 10cm가 잠기면 절반 속도로 성장하고, 20cm가 잠기면 최대 속도로 성장했다. 같은 시각을 반복하면 재고가 늘지 않았고, 노출되면 감소해 0에서 멈췄다. 재침수하면 용량 10까지 회복한 뒤 Python에서 두 개체가 같은 재고를 각 2씩 먹었다. 수주를 조회할 수 없는 경우에는 재고를 유지하는 별도 경계도 확인했다. 두 개체의 섭식과 수주 누락은 Python 통제 대조이며, 최신 섬에 계절성 군락을 새로 배치하는 변경은 없다.

최신 섬에서는 `-EcoIslandDriftSeasonalTrial`로 기존 Drift에 제어 수심 80cm와 초당 노출 손실 0.065를 임시로 적용했다. 저장 배치의 용량 11과 기본 재생률 0.13/s를 유지했다. 수면을 약 66.7cm 낮추자 두 접근점이 드러나 지급이 멈췄다. 시드 20000은 노출이 처리되기 전에 이미 고갈됐으며, 시드 20017은 남아 있던 약 0.099가 노출 손실로 줄었다. 수면을 복구하자 두 시드 모두 권위 시각 250초에 0.493을 다시 지급했다. 재고 갱신 609건과 실제 지급 40건을 Python에서 검산했다. 이 비교는 PIE 시험이며 배치 채택은 생태·시각 검증 이후 판단한다.

```powershell
./AdaptiveEcosystem/Tools/Editor/run_jyu_island_audit.ps1 -Mode Population -PopulationSeconds 300 -Label drift_seasonal -Scenario @('-EcoIslandWaterForageShared', '-EcoIslandAuditDriftStock', '-EcoIslandDriftSeasonalTrial')
```

동일한 실측 깊이로 만든 두 칸의 Python 제어 장면에서는 현재 위치와 수위에 따라 군락 ID와 접근점 번호를 함께 선택한다. 퇴수로 추가점이 드러나면 그 점을 대상으로 한 이전 요청은 재고를 차감할 수 없다. 잠긴 지점으로 이동해 그 지점을 명시적으로 요청해야 지급된다. 수위를 복구하면 추가점으로 돌아와 같은 재고에서 먹는다. 두 칸의 간격은 이 동작만 검증하는 시험값이다. 실제 하류의 유영 경로와 이동 시간은 이 장면에 포함되지 않는다.

같은 빌드에서 아래 순서로 Unreal 저장, 일반 복원, 퇴수 대조를 실행한다. 일반 복원은 이어지는 부화를 함께 확인한다. 퇴수에서는 섭식과 수위 복구를 판정하고 부화는 참고 기록으로 남긴다. 두 실행의 먹이 차감 위치는 `Saved/FaunaAudit/IslandAccessBaseline`의 `PatchMeal` 로그 `Access` 값으로 비교한다.

```powershell
$runner = './AdaptiveEcosystem/Tools/Editor/run_jyu_island_audit.ps1'
$scene = @('-EcoIslandRiverRatRefuge=Saved', '-EcoIslandVerifySnowStageBounds',
    '-EcoIslandVerifyGrasslandStageBounds', '-EcoIslandAuditNursery',
    '-EcoIslandCheckpointFinalBank', '-EcoIslandCheckpointRun=wet_share', '-EcoIslandWaterForageShared')
& $runner -Label wet_share_save -Headless -Scenario ($scene + '-EcoIslandCheckpoint=Save')
& $runner -Label wet_share_load -Headless -Scenario ($scene + '-EcoIslandCheckpoint=Load')
& $runner -Label wet_share_drop -Headless -Scenario ($scene + @('-EcoIslandCheckpoint=Load', '-EcoIslandWaterForageSharedDrawdown'))
```

먹이터 연결 격자 JSON의 `small_fish_range`는 최종 섬의 소형어류 112번을 두 시드에서 계측했다. 기준의 첫 300게임초 동안 먹이를 찾은 119회씩 모든 군락이 탐색 범위를 벗어났다. 시드 20000의 가장 가까운 후보는 약 13.4m, 최대 탐색 거리는 약 3m였다. 기존 Drift 용량과 재생의 15%를 Roots 근처에 임시로 나누자 112번이 두 시드에서 각각 네 번 먹었다. 다른 소형어류를 포함해 지급이 확인된 시작 개체는 각각 4/7→7/7, 4/7→6/7이었다. 기존 Drift 쪽 네 개체도 섭취했으며 지급량은 달라졌다. Python은 실제 후보의 거리·재고·감지 범위와 기록된 시야·수중 판정으로 점수·선택·지급을 대조한다. 두 실행 모드의 배속이 달라 장기 생존 효과는 따로 확인해야 한다. 총 작성 용량과 재생률은 같고 분산 배치는 PIE에서 시험했다.

`small_fish_matched60`은 같은 저장 섬·빌드·시드·4배속에서 기존 배치 두 번과 분산 배치 한 번을 비교한다. 두 시드 모두 첫 300게임초 지급은 기존 4/7에서 분산 7/7로 늘었고, 30·60분의 소형어류 생존은 1마리, 잉어는 3마리였다. 소형어류의 60분 지급 합계는 시드 20000에서 408.930→377.234, 20017에서 기존 409.654·413.794→376.769였다. 잉어는 시드별 1515.413→1513.870, 기존 1589.577·1497.672→1551.943이었다. 두 시드의 분산 실행에서 선반 산란장 부화가 한 건씩 추가됐고 생존 수는 같았다. 기존 Drift 쪽으로 가는 공급을 줄이면 접근 개선과 장기 지급량 사이에 비용이 생겨 분산 배치는 저장하지 않았다.

60게임분 대조는 두 조건 모두 `Population` 모드로 실행한다. 기준 명령에서 `-Scenario` 인수를 빼면 저장 섬의 기존 배치로 실행한다.

```powershell
$split = @('-EcoIslandTrialWaterForageSplit','-EcoIslandWaterForageSmallFish',
           '-EcoIslandWaterForageFromDrift','-EcoIslandWaterForageSplitPercent=15')
./AdaptiveEcosystem/Tools/Editor/run_jyu_island_audit.ps1 -Mode Population `
    -Label drift15_matched60 -PopulationSeconds 3600 -WaterFoodAuditAgent 112 -Scenario $split
```

수중 군락도 기존 `ForageAccessPoints`로 한 재고의 여러 섭식 좌표를 표현한다. 수중 상륙용 좌표와는 별도이며, 기존 산란장 중심과 재생 계산은 원래 군락을 따른다. 유영 종은 거리·수심·시야를 좌표마다 검사하고 한 좌표가 막히면 다른 좌표를 다시 고를 수 있다. 지급은 선택한 위치에서 수중·사거리·가시성을 다시 확인한 뒤 같은 군락 재고에서 차감한다. 저장 시 기존 접근 좌표와 개체 상태를 직렬화한다.

`shared_underwater_access`의 두 시드에서 기존 Drift 용량·재생과 시작 조건을 고정한 채 추가 지점 하나를 PIE에 넣었다. 각 시드에서 183초에 기존 지점과 추가 지점이 같은 재고에서 지급받았다. 첫 300초 동안 소형어류 7/7·6/7마리가 먹었고, 60분 소형어류 지급은 388.151·397.094로 분할 배치의 377.234·376.769보다 높았다. 기존 배치의 408.930·409.654~413.794에는 못 미쳤고, 60분 생존은 두 시드 모두 소형어류 1마리와 잉어 3마리였다. 추가 지점 쪽 112번에 장기 지급이 집중돼 이 좌표는 저장 섬에 넣지 않았다. 좌표 별 먹이량 로그는 늘릴 수 있지만 저장·복원과 수면 변화에서 추가 좌표의 동작은 별도 확인이 필요하다.

같은 명령에 [저장 선반의 실제 퇴수 표본](island_carp_saved_drawdown_20261114.json)을 전달하면 잉어 치어의 수주와 먹이 높이로 정상 수위·퇴수·복구의 접근 조건을 계산한다. 퇴수 때 노출된 유입부 수초의 섭식 요청은 거절됐으며, 선반에서 두 시드 각각 네 건의 권위 지급을 재현했다. 복구 뒤에는 유입부 수초에서 첫 지급이 가능했다. 먹이 거래마다 권위 로그의 지급과 잔량으로 거래 직전 재고를 복원했다. 개체 경로·식생 재생·경쟁을 독립적으로 실행하는 검사는 별도다. [Unreal 실행 조건](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#잉어-선반과-두-번째-밍크-출구-적용)

같은 표본의 `wet_shelf_ledger`는 강우가 최대인 시험 구간에서 공유 재고를 연속 계산한다. 초기 재고 16과 저장된 기본 재생 0.18에 강우 계수 1.25를 적용하고, 기록된 순서대로 치어와 기존 개체의 섭식 요청을 처리했다. 전체 지급 11·19건과 잔량을 대조했으며 첫 고갈은 208.000·197.120게임초였다. 같은 시각의 요청 사이에는 재생이 없고, 뒤에 먹는 개체는 앞선 지급 뒤의 재고를 받는다. 여기서 비는 시험 주기의 고정 구간이며, 요청 시각과 순서는 권위 로그를 사용한다.

[잉어 산란장 대응 장면](island_nursery_reservation_20261114.json)을 같은 물 환경 도구에 주면 두 산란장의 예약을 한 시계에서 갱신한다. 퇴수로 유입부의 예약이 취소되면 두 부모의 재시도는 30초 뒤부터 가능하고, 물이 돌아와도 그 예약은 복원되지 않는다. 계속 잠긴 여울 가장자리에서 부화할 수 있게 되면 현장 수심에서 치어의 섭식을 실행한다. 두 시드의 첫 지급 0.681·0.401과 잔량을 대조했다. 부모 상태와 예약 요청 시각은 고정하고, 시야·치어 유영·경쟁의 경과와 거래 직전 재고는 Unreal 기록을 사용한다. 수온·유속·부모 적격성과 실제 생성 위치 판정은 후속 대응 범위다.

[Python 강변 환경](../../../Tools/EcoVegetationEval/island_shore_reference_world.py)은 [실측 지점과 Unreal 지급 기록](island_flooded_ground_forage_20261114.json)을 사용한다. 두 시드에서 범람한 뿌리 쪽 지점에는 물소가 들어갈 수 있었고 말·큰뿔양·산토끼의 이동 요청은 막혔다. 마른 둑을 먹이 접근점으로 지정하자 말이 도착해 실제 Unreal의 첫 지급량과 같은 2.8을 받았고 재고 10은 7.2가 됐다. Python 퇴수 대조에서는 두 번째 말이 뿌리 쪽에서 남은 재고를 꺼낼 수 있었고, 포만 상태에서는 같은 식사가 반복되지 않았다. 연결은 측정 지점 사이에 명시적으로 부여한다. 연속 지형 충돌·가림·이동 시간과 재생, 퇴수 뒤 개체 행동은 이 검사에서 Unreal과 대조하지 않는다.

```bash
python AdaptiveEcosystem/Tools/EcoVegetationEval/check_island_shore_world.py \
  AdaptiveEcosystem/Docs/RL_Policy/Examples/island_flooded_ground_forage_20261114.json
```

같은 강변 검사에 [수생 접근 표본](island_water_access_geometry_20261114.json)을 전달하면 밍크의 기존 강둑이 +24cm 시험 수위에서 잠기고, 저장된 출구와 마른 둑은 사용할 수 있는지 확인한다. 정상 수위에서는 기존 강둑이 다시 드러났다. 새 출구의 상륙 직후 두 위치 표본으로 걷는 속도를 계산하고, 이후 위치와 마른 둑 도착 시각을 비교했다. 두 시드의 예측은 79.89·78.70 PIE초였으며 30Hz 한 스텝 여유를 포함해 실측 도착 구간과 일치했다. 지상 연결은 저장 맵에서 충돌을 검증한 구간을 입력으로 사용한다.

별도 침수 시험에서는 밍크 111번이 물에 들어간 뒤 기존 상륙점이 잠기자 통과 가능한 두 후보 중 가까운 임시 발판 쪽을 골랐다. Python은 기록된 거리와 수심·충돌 판정을 받아 이 선택과 이후 두 판단에서 선택한 경로를 재사용하는 것을 두 시드에서 대조했다. Unreal의 대체 출구 선택은 62.017·61.017게임초, 실제 상륙은 65.900·64.783게임초였다. 이 장면의 두 후보는 모두 시야를 통과했고 최근 통과 실패도 없었다. 수중 시야와 충돌은 Unreal에서 계산한 값을 받으며, Python은 유영 경로를 적분하지 않는다. [침수 시험과 소스](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#잉어-선반과-두-번째-밍크-출구-적용)

`mink_exit_cover`에서는 같은 두 시드의 같은 수위와 후보 거리에서 시야용 장애물 하나를 더했다. 가까운 후보(약 1.53m)가 가려져 밍크는 약 72.46m 떨어진 기존 Roots 쪽을 선택했다. 두 시드 모두 35게임초 뒤의 수위 복구 때도 물속에 있었고, 스태미나는 14.2%·12.3%였다. Python이 재현한 범위는 시야 판정 이후의 후보 선택이다. 유영 경로와 목적지까지의 체력 비용은 이 선택기에서 추가 검증이 필요하다.

후속 `mink_exit_budget` 표본은 출구까지의 유영 거리 추정에 스태미나를 반영한 빌드다. 두 시드의 가림 조건에서 약 72m 후보가 스태미나로 탈락했고, 수위 복구 시 스태미나는 92.7%·93.3%였다. 가까운 후보에 시야가 열려 있으면 각각 65.900·64.783게임초에 실제로 상륙했다. Python은 기록된 판정·스태미나·상륙을 확인한다. 긴 우회 경로와 구간별 유속은 별도 검증 범위다.

`mink_independent_exit`는 같은 출구 두 곳의 수심·유속·좌표와 정지 중인 밍크의 위치·남은 스태미나를 추가로 측정했다. [Python 수륙 전환 모델](../../../Tools/EcoVegetationEval/island_shore_reference_world.py)은 이 입력과 장애물 좌표에서 가까운 출구의 가림, 먼 출구의 스태미나 부족, 가림을 걷었을 때의 출구 선택을 계산했다. 두 시드 모두 Unreal 후보의 거리와 선택이 일치했다. Python 통제 장면에서는 대기 중 스태미나가 유지됐고, 유영 뒤 도착한 둑이 다시 잠기면 상륙이 취소됐다. 스태미나 8%에서 흐름 방향만 뒤집었을 때는 가까운 출구의 도달 가능 여부도 바뀌었다. 출구 선택에 사용한 속도 범위는 32~75cm/s다. [밍크 두 시드의 측정값](island_water_access_geometry_20261114.json)

`mink_swim_track`은 저장 섬의 고수위 복귀에서 계측한 수심과 유속을 적용한다. 유영과 상륙의 각 첫 표본 구간에서 속도를 추정하고 이후 위치를 예측했다. 두 시드의 최대 유영 오차는 1.90·1.96cm, 상륙 접근 오차는 각각 0.01cm였다. 예상 상륙 시각 70.99·69.82 PIE초는 실제 마지막 상륙 중 표본과 첫 육상 표본 사이였다. 스태미나는 유영에서 감소했고 상륙 중에는 유지됐다. 경로와 충돌 결과는 해당 실측 구간의 조건이며 기상이나 대사에 따른 속도 변화·막힌 길의 재탐색은 별도 검증이 필요하다. [유영·상륙 표본](island_water_access_geometry_20261114.json)

메기 낮밤 대조는 `python AdaptiveEcosystem/Tools/EcoVegetationEval/check_water_day_night.py`로 실행한다. Unreal의 낮 50ms 이동량을 공통 속도 계수로 맞추고, 밤의 이동량 1.943486cm를 별도로 확인한다. 재고 10, 거리 220cm의 고요한 수주에서 낮에는 7초 내 지급 0, 밤에는 6초 뒤 첫 지급 2와 잔량 8이 일치했다. 거리를 200cm로 줄인 낮 대조에서는 시작 시 탐색에 잡힌다. 지급은 정지한 개체에만 허용하는 Unreal 조건을 적용한다. 이 실험은 평면의 한 축과 수주 하나를 사용하며, 지형·수류·비선택 탐색 이동은 별도 대응 범위다. [Unreal 실측](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#규칙-전용-지역의-낮밤)

## 제공하는 두 사례

| 파일 | 실제 포함한 값 | 읽을 때의 조건 |
|---|---|---|
| [부모·자식](ecosystem_life_family_actual_20261024.json) | 부모58/78과 자연 자식157의 실제 진단,3지역의 실제 metadata와 각4개 cell | 출생 후 관찰이다. 출생 순간 Energy/Reserve Golden이 아니며 이미 성장·이동·섭식했을 수 있다. |
| [Unknown 피해](ecosystem_life_unknown_damage_actual_20261024.json) | 실제 ambush fixture의 피해 개체17, 비영 Unknown fear·인식 여부·실제 observation/request/executed·지역 표본 | 테스트 Pawn을 재배치하고 실제 TryStrike를 호출한 명시적 fixture다. 자연 플레이의 급습 확률/분포가 아니다. |

각 파일의 metadata에는 원본 snapshot sha256, source 파일/보고서 이름, 실제 전체 agent 수, 선택한 cell index가 있다. `agents` 행과 선택된 cell 값은 원본에서 수정하지 않았다. metadata와 부분 표본 표시만 덧붙였다. 인위적으로 기대값을 만든 fixture/Golden이 아니다.

## 이 파일로 하면 안 되는 것

- `partial=true`, `training_ready=false`, `golden_vector=false`, `restorable_world=false`다. 전체 학습 환경·기존 native snapshot schema·binary checkpoint와 호환된다고 가정하지 않는다.
- region metadata의 총 food/인구는 전체 세계 기준이다. 제공한4개 cell 합계와 맞추거나 나머지896개를0으로 채우지 않는다. 전체900셀은 새 capture로 얻는다.
- 전체 current position·HP·부모·RNG·장부는 진단 정답일 수 있다. 이 JSON 전체를 observation vector로 넣지 않는다. policy 입력은 계약된 `observation`/판/시점만 사용한다.
- ID와 seed/RNG의 문자열을 JavaScript number로 강제 변환하지 않는다. 중요한 int64 정밀도를 잃을 수 있다.
- `energy`는 M4 Vitals 단위, `energy_fraction`은 표현에서 읽은 양자화 값이다. Native 정규화 Energy와 같은 정밀도/단위라고 가정하지 않는다. 정확한 Native body 값이 필요한 mirror에는 별도 capture 계약을 정한다.
- `life.nutrition`은 현재 늑대 영양에 사용하는 상태다. 초식 개체에서 기본값1로 보인다고 실제 초식 Energy/Reserve=1인 것은 아니다. 초식의 비축·섭식과 자기 에너지를 따로 읽는다.
- `last_damage_attacker_known=false`만으로 Unknown 피해를 받았다고 판정하지 않는다. 피해가 전혀 없을 때도 기본 false다. 제공 사례는 실제 피해 시험 보고서와 비영 Unknown fear를 함께 검증했다.
- snapshot의 현재 body·committed policy read·next read/request를 같은 시점으로 섞지 않는다. 저주기 표본은 전체 step 입력/난수/생명주기 순서를 담지 않는다.

## 저장된 섬의 중간 먹이터

산토끼 통로 명령에 `--patch-inputs AdaptiveEcosystem/Docs/RL_Policy/Examples/island_patch_input_population_baseline_20261114.json`을 붙이면 실제 초본 군락의 식생 갱신과 섭취를 연결한다. 출발 재고 0.25, 온도 14°C, 강우 0.66, 습도 0.72와 같은 통로를 고정하고, 군락의 수분 입력만 0.10과 0.55로 바꿨다. 두 시드의 도착은 각각 57초·54초로 같았다. 건조 조건은 재고가 한 입의 최소량인 0.2에 못 미쳐 지급 0이었다. 습윤 조건은 2.8을 지급한 뒤 0.377·0.223이 남았다. 수분은 이 제어 시험의 고정 입력이며, 강우로부터 수분을 계산하는 전체 토양·식생과 개체의 독립 선택은 별도 검증 대상이다.

[플레이어 발소리 대조](island_player_passage_20261114.json)는 같은 위치의 정지·은밀 이동·달리기를 두 시드에서 비교한다. 달리기에서 산토끼가 회피했고 발소리 뒤 첫 통로 경유점은 정지보다 각각 5·9초 늦었다. 첫 먹이는 세 조건 모두 중간 초본에서 2.8이었고, 달리기의 지급 시점은 한 시드에서 5초 늦고 다른 시드에서 5초 빨랐다. `python AdaptiveEcosystem/Tools/EcoVegetationEval/check_player_passage.py AdaptiveEcosystem/Docs/RL_Policy/Examples/island_player_passage_20261114.json`으로 소리 발행, 회피, 경유점, 도착, 지급의 기존 기록을 대조한다.

같은 명령에 `--ground AdaptiveEcosystem/Docs/RL_Policy/Examples/island_transition_habitat_actual_20261113.json`을 붙이면 Python도 발소리 강도와 감쇠를 계산한다. 저장 섬 PIE에서 확인한 `DA_ExpandedFaunaFootsteps`의 산토끼 청각 범위 17m, 감지 문턱 0.12, 가림 시 거리 배율 0.44를 사용한다. 고정 거리 7m에서 열린 달리기만 신호 0.318로 반응했고, 조용한 이동·가림·청각 거리 절반 조건은 정지 기준과 같았다. 이 단순 대조는 주어진 경로를 1.5초 멈췄다가 재개한다. [Unreal 감쇠 계산](../../../Source/AdaptiveEcosystem/Creature/Audio/EcoFootstepAudioSet.cpp)

`-EcoIslandPlayerPassage=Run`의 새 두 시드 실행에서는 산토끼가 회피를 시작하거나 갱신할 때 선택한 소리의 ID와 권위 시각, 음원·수신 좌표, 거리 한계, 음량, 가림, 날씨 배율을 기록했다. 실제 반응 4·3건의 신호를 Python이 재계산했고 모두 오차 0.00003 이내였다. 선택된 소리는 모두 가림 없이 들어왔다. 가려진 조건은 위 제어 대조를 사용하며 듣지 못한 개별 후보는 이 기록에서 검사하지 않는다.

같은 실행의 약 0.27초 간격 위치 표본에서는 회피 전 진행 방향과 회피 구간 순변위 사이 각도가 44.7°·36.0°였다. 순변위는 10.17m·9.89m였고, 마지막 회피 표본은 첫 음원에서 9.50m·9.40m 더 멀었다. 이후 권위 경유점은 37·39초, 중간 지역 도착은 66·52초였다. Python 도구가 위치와 권위 사건 순서를 검사한다. 각도는 회피 구간의 시작·끝 위치로 계산했으며 프레임별 회전이나 경로 최적화는 이 표본의 검증 범위 밖이다.

`--ground`는 기록된 음원 4·3건을 입력으로 받아 Python에서 회피 방향도 계산한다. 첫 반응 위치에서 출발해 현재 위치로 청각 신호를 다시 계산하고, 속도·경계심 형질과 회전·가속 한계로 회피한다. 두 시드에서 회피 순변위는 10.55m·10.68m였다. 경계가 풀리면 원래 경로로 돌아가 첫 식사 2.8을 받는다. 음소거 대조는 회피 없이 같은 양을 더 일찍 받았다. 초기 방향과 통로 복귀 경로는 시험에서 정했으며, 선별된 음원만 사용한다. 실제 섬의 연속 충돌, 임의 재탐색과 첫 지급 시각은 검증 범위 밖이다.

`python AdaptiveEcosystem/Tools/EcoVegetationEval/check_island_ground_passage.py AdaptiveEcosystem/Docs/RL_Policy/Examples/island_transition_habitat_actual_20261113.json`은 산토끼 70번의 실제 출발점, 강변 경계 양쪽, 중간 초본 위치를 잇는 Python 이동을 실행한다. 두 시드에서 권위 지역이 바뀐 뒤에만 2.8을 지급했고, 경계를 닫으면 같은 재고에서 지급 0이었다. Python은 경계를 52·49초에 넘고 첫 지급은 57·54초였다. Unreal은 각각 61·57초와 67·63초였다. Python은 기록된 속도 형질과 기본 보행 속도로 주어진 경로를 즉시 걷는다. 출발 판단·경사·가속·가림·경쟁과 식생 재생이 빠져 있으므로 전체 이동 시간 대조에는 보완이 필요하다.

[섬의 실제 도착·섭식 표본](island_transition_habitat_actual_20261113.json)은 저장 맵을 새 프로세스에서 연 시드 20000·20017의 PIE 보고서에서 발췌했다. 시작 16종 118마리, 작성 먹이 재고 215, 사슴 R7e 조건에서 산토끼 70번이 두 시드 모두 중간 먹이터에 도착해 섭취했다. 두 초본 패치의 설정, 도착·식사 이력 전부, 각 실행의 43개 표본 중 5개와 원본 보고서 SHA-256을 제공한다. 재고와 끼니 지급 에너지는 따로 읽는다.

체크포인트 저장 직후 표본은 시드 20017을 별도로 실행해 얻었다. 해당 이진 체크포인트는 저장 당시 DLL을 사용한 새 프로세스에서 상태 일치와 산토끼의 후속 섭식을 검증했다. 제공하는 부분 JSON은 `partial=true`, `training_ready=false`, `golden_vector=false`, `restorable_world=false`다. 섬의 구현·재현·면적 대조 계획은 [서식지 검증 기록](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md)을 참조한다.

## 저장된 섬의 강우·상륙·부화

[수변의 실제 관찰 표본](island_river_nursery_actual_20261113.json)은 시드 20000·20017의 고수위 강둑 대조에서 뽑았다. 밍크의 입수·상륙, 두 산란장 주변 수심, 잉어의 부화·첫 패치 지급·종료 체력을 포함한다. 밍크 강둑의 수위 변화가 두 잉어 산란장의 건조를 일으키지 않았으므로, 중간 퇴수로 예약이 취소되는 시험과 구분한다. 시각은 PIE 표본과 권위 사건을 나누어 표시하며 원본 보고서·로그 해시를 함께 남겼다. 이 자료는 `training_ready=false`이며 Python 실행 근거가 필요하다. [수변 구현·검증 기록](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#어류-산란장-예약과-퇴수)

## JYU 섬 육상 군락의 토양 수분

[초지 강우와 군락의 실제 표본](island_forage_soil_actual_20261114.json)은 같은 빌드에서 2시드 × 2강우 패턴 × 2토양 입력을 실행한 8개 보고서에서 뽑았다. 초지의 네 군락에 대해 첫 표본, 마지막 비가 그친 시점, 그 뒤 30게임초, 종료 시점의 원본 행 인덱스와 관측값을 제공한다. 권위 로그의 실제 에너지 지급 합계와 각 원본의 SHA-256을 포함한다. 초지 전체 격자의 평균 수분과 군락 중심의 개별 셀 수분을 구분한다. [구현과 대조 결과](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#군락-위치의-토양-수분-연결)

첫 대응 장면은 동일한 강우 일정과 온도에서 두 토양 이력을 준비한 뒤, 마지막 비가 그친 시점의 입력과 각 군락의 재고를 별도로 비교한다. Python과 Unreal에서 같은 위치의 토양 수분을 읽었는지, 권위 시간에 적용한 재생·건조 손실·지급 후 재고가 맞는지를 순서대로 확인한다. 이 발췌에는 고정 시간 간격마다의 완전한 셀 상태와 군락 거래가 없으므로 Python 수치 일치 판정에는 별도의 전체 입력이 필요하다. `training_ready=false`다.

현재 소스의 `soil_parity.cpp`를 직접 컴파일하고 기존 `check_soil_parity.py`로 2,400개 기본 셀 사례를 다시 비교했다. 최대 절대 오차는 0이었으며 새 결과의 소스 SHA-256은 `a2d59dfec132e2f22739b7fef3aebddf65911635ec081ad6fe38e882cc9d8c2c`이다. 이 범위는 기존 기본 셀 계산이며, 자연 서식지 옵션과 군락 위치의 토양 조회, 군락 거래 및 R9 세계 통합은 별도 대응이 필요하다. 로컬 보고서는 `Saved/FaunaAudit/ForageSoilParity/SoilParity.json`에 있다.

군락 대응 시험의 입력은 권위 갱신 간격, 갱신 전 재고, 군락 중심의 수분 또는 대체 입력에 쓰는 강우·습도, 기온, 용량과 재생·건조 계수다. `건조 스트레스 = clamp(1 - 수분 / 요구 수분, 0, 1)`을 사용하고 요구 수분이 0이면 스트레스도 0이다. 수분 입력을 받지 못한 군락은 `0.65 × 강우 + 0.35 × 습도`를 쓴다. 갱신은 `재생률 × 기온·강우 배율 × (1 - 스트레스)² - 건조 손실률 × 스트레스 × 재고 / 용량`을 갱신 간격에 적용하고 재고를 0과 용량 사이에 둔다. 그 뒤 실행기에서 허용된 지급만 요청 순서대로 차감한다. 동일 재고를 공유하는 두 접근점, 0.2 미만의 미지급, 첫 지급이 다음 개체에 남기는 재고까지 확인한다. [언리얼 군락 갱신과 지급](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.cpp) · [군락의 수분·지급 함수](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h)

군락의 한 번 갱신과 이어지는 두 지급을 Python 기준식과 대조했다. 테스트 도구는 현재 `EcoFauna.h`와 `EcoFauna.cpp`에서 해당 함수 본문과 갱신 식을 읽어 간단한 수학 타입을 붙인 C++ 프로그램을 컴파일한다. 세 날씨와 네 수분 조건, 재고·갱신 간격·두 개체의 에너지 부족량을 조합한 540건에서 건조 스트레스, 갱신 재고, 개체별 지급과 잔량의 최대 절대 오차는 0이었다. 0.2 지급 하한과 최대 용량을 포함했다. 이 결과는 입력이 주어진 뒤의 산술을 검증한다. Unreal 월드의 토양 조회, 접근 허용과 자원 장부 갱신, R9 훈련 루프에 연결하는 작업은 별도다. 도구를 호출할 때 로컬 MSVC의 `vcvars64.bat` 경로를 전달한다. [군락 재고 대조 도구](../../../Tools/EcoVegetationEval/check_forage_stock_parity.py)

서쪽 초지·범람원 습윤 초지·접근 초본의 재고 용량·재생·건조 계수는 위의 Unreal 군락 발췌에서 읽고, 온도·강우·수분 반응 계수는 작성 소스를 사용했다. 군락마다 건조 20초→강우 60초→퇴수 후 30초를 모사하는 고정 입력과 주기적인 두 지급 요청을 넣었다. 3개 군락의 2,475회 연속 갱신에서 직전 지급 뒤 잔량을 다음 갱신으로 이어도 최대 절대 오차는 0이었다. 이 시간별 수분·섭식 입력은 비교용 동일 입력이다. 실제 섬의 전 틱 입력과 개체 선택을 재생한 기록은 아니다. [군락 예산 발췌](island_forage_soil_actual_20261114.json) · [반응 계수 작성 소스](../../../Tools/Editor/author_jyu_herbivore_forage.py)

후속으로 `eco.Fauna.ForageStockAudit IslandForageWestMeadow`를 켜고 최신 저장 섬의 실제 서쪽 초지 군락을 기록했다. 직접 UBT 빌드와 시드 20000·20017의 강우 PIE가 정상 종료됐다. 강우·온도·습도, 실제로 조회한 군락 수분, 권위 갱신 간격과 에너지 부족량을 기록하고 `check_forage_stock_parity.py --authority-log <로그>`로 재생했다. 각 시드의 재고 갱신 213회, 실제 지급 24·22건과 각 다음 갱신의 시작 재고가 모두 일치했다. 이 로그는 성공한 지급만 포함하며 접근에 실패하거나 지급 하한을 넘지 못한 요청은 별도 표본이 필요하다. 해당 CVar는 기본값이 비어 있다. 로컬 원본은 `Saved/FaunaAudit/IslandAccessBaseline/{20000,20017}_forage_authority_replay.log`다. [Python 재생 도구](../../../Tools/EcoVegetationEval/check_forage_stock_parity.py) · [권위 갱신 기록](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.cpp)

이후 같은 CVar에 거리·시야·지급 하한을 구분하는 기록을 추가하고 직접 UBT와 두 시드의 강우 PIE를 다시 실행했다. 새 로그에서 각 213회 갱신, 지급 25·26건, 미지급 13·19건과 잔량을 Python으로 재생했다. 미지급 32건은 모두 군락 재고가 0이었던 지급 단계였으며, 거리·시야 거절 표본은 없었다. 이 기록은 정지·허기 검사를 통과하고 군락 목표로 인해 섭식 분기에 도달한 개체를 대상으로 한다. 접근 중인 모든 개체의 목표 변경은 별도 기록이 필요하다. 로컬 원본은 `Saved/FaunaAudit/IslandAccessBaseline/{20000,20017}_forage_attempt_replay.log`다.

[권위 거래 발췌](island_forage_stock_authority_20261114.json)에는 두 원본 로그에서 비가 그치기 직전부터 재고 고갈로 지급이 거절되고, 회복 뒤 다시 지급되는 구간까지의 해당 군락 기록을 순서대로 담았다. 갱신 60건·지급 8건·미지급 8건의 결과와 연속 재고가 Python에서 정확히 일치했다. `training_ready=false`다. 접근과 시야는 Unreal에서 기록된 판정을 사용하며 R9 월드에서 개체 선택을 재현하는 시험은 별도다. Dots에서는 아래 재생기와 JSON을 사용하며, 기존 sparse checkout에는 필요할 때 `git sparse-checkout add AdaptiveEcosystem/Tools/EcoVegetationEval`로 재생기를 포함한다. [재생기](../../../Tools/EcoVegetationEval/check_forage_stock_parity.py)

```bash
python AdaptiveEcosystem/Tools/EcoVegetationEval/check_forage_stock_parity.py \
  --authority-fixture AdaptiveEcosystem/Docs/RL_Policy/Examples/island_forage_stock_authority_20261114.json
```

기존 R9 M1에서는 토양을 계산하는 `vegetation_v1` 도우미와 별개로 격자별 재생 계수로 먹이 재고를 회복한다. 개발 시드 44190·44191에서 초기량 0.2, 용량 0.5인 풀 셀 위에 사슴을 두고 한 결정 동안 `WATCH`를 요청했다. 물리 스텝당 재생 계수 0이면 재고와 관측이 유지됐다. 시험값 0.1이면 두 물리 스텝 뒤 재고는 0.257, 재생 장부는 0.057이었고 `food_here`와 `food_density`가 모두 상승했다. 이 검사는 기존 정책이 풀 재고 변화를 관측하는 경로의 기준이다. 강우·수분이 재생을 바꾸는 과정이나 토양에 따른 군락 건조·섭취 거래는 후속 대응이 필요하다. `training_ready=false`다. [Python 재현 도구](../../../Tools/Editor/check_r9_vegetation_reference.py) · [R9 재생 구현](../../../../herbivore_rl/env_v2/r9_world.py) · [기존 토양 도우미](../../../../herbivore_rl/env_v2/vegetation_v1.py)

같은 도구의 별도 시험은 초기 수분 0.28에서 60초 동안 강우 0 또는 0.7을 주고 두 조건을 30초 더 맑게 뒀다. 토양 도우미가 계산한 한 셀의 재고만 R9 관측 경로에 넣었다. 90초 뒤 건조·강우 조건의 수분은 0.000·0.406, 풀 재고는 0.282·0.422였고 두 개발 시드의 `food_here`와 `food_density`가 재고 차이를 반영했다. 구간별 재고는 기존 재고에 계산된 성장량을 더하고 손실량을 뺀 값과 일치했다. 이 시험에서는 외부에서 계산한 한 셀을 사용했고, 훈련 세계의 물리 스텝이나 Unreal 작성 군락과의 시간별 일치를 검증하지 않았다. [실행 도구](../../../Tools/Editor/check_r9_vegetation_reference.py)

두 강우 이력의 종료 상태마다 R9의 `WATCH`와 `EAT`를 차례로 실행했다. 관찰 요청의 지급은 0이었다. 섭식 요청은 두 시드·두 이력 모두 풀 0.024를 지급했다. 남은 재고는 건조 이력에서 약 0.258, 강우 이력에서 약 0.398이었고 다음 위치 먹이량과 주변 먹이 밀도는 차감분을 반영했다. R9의 자체 재생은 이 거래 동안 0으로 고정했다. 이 결과는 외부 계산 재고를 기존 섭식 장부와 관측이 함께 읽는다는 근거이며, 자발적인 섭식 선택이나 비가 먹는 속도를 바꾸는지를 시험한 결과는 아니다. [섭식·잔여 재고 대조](../../../Tools/Editor/check_r9_vegetation_reference.py)

공유 재고 시험에는 성체 사슴 1마리와 성숙 시간의 25%를 지난 어린 사슴 1마리를 같은 셀에 두고 둘 다 `EAT`를 요청했다. 시작 재고가 0.059일 때는 둘 다 0, 0.060과 0.080에서는 각 0.012, 0.100에서는 각 0.024를 받았다. 재고 0.080에서는 첫 물리 스텝 뒤 남은 0.056이 R9 하한 0.060보다 낮아 두 번째 지급이 없었다. 성장 단계의 슬롯 순서를 바꾼 두 시드의 총 16개 시험에서 거래량과 장부가 일치했다. 하한과 양은 이 설정과 같은 사슴 한 쌍의 결과다. Unreal의 군락별 지급 한도와 여러 종의 우선순위를 비교하려면 같은 실제 요청과 재고에서 별도의 권위 대조가 필요하다. [공유 재고와 성장 단계 대조](../../../Tools/Editor/check_r9_vegetation_reference.py)

Unreal 최신 60게임분 로그에서 같은 군락·기록 시각에 개체 둘 이상이 지급받은 경우는 시드별 10·13건이었다. 이 중 재고가 0이 된 경우는 5·7건이었다. 시드 20000의 잉어 선반에서 228초에 창시 잉어 두 마리가 각각 2.800을 받은 뒤, 실행 중 부화한 137번은 남은 0.365를 받았다. 시드 20017의 200초에는 창시 잉어가 2.800, 실행 중 부화한 134번이 남은 2.333을 받았다. 모든 묶음에서 로그 순서대로 앞 지급의 잔여량에서 다음 지급을 빼면 다음 잔여량과 일치했다. R9의 셀 거래는 같은 물리 스텝에서 총수요와 재고를 비교해 요청량에 비례하여 배분한다. Unreal의 작성 군락 거래는 권위 실행 순서대로 현재 재고를 차감한다. 이 자료에는 실패한 요청과 서로 다른 종이 동일 시각에 지급받은 사례가 없어 종별 우선순위나 고정 순서 효과를 판정할 수 없다. [Unreal 공유 재고 거래 표본](island_saved_stage_population_actual_20261114.json) · [Unreal 지급 규칙](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h) · [R9 셀 거래](../../../../herbivore_rl/env_v2/r9_world.py)

R9 M1에서 사슴과 물소를 같은 풀 셀에 놓고 초기 재고를 섭식 하한인 0.060으로 맞췄다. 두 시드에서 동시에 `EAT`를 요청했을 때 사슴은 0.010843, 물소는 0.049157을 받고 재고가 0이 됐다. 사슴이 한 결정 먼저 먹으면 0.012를 받고 물소는 0, 물소가 먼저 먹으면 0.0544를 받고 사슴은 0이었다. 먼저 먹은 뒤의 잔량 0.048·0.0056은 둘 다 하한보다 낮았다. 이 대조는 한 장소에서의 섭식 요청 시차만 바꿨다. 실제 이동·도착의 시차, 잡식 종의 먹이 전환, Unreal 군락과의 대응은 추가 검증이 필요하다. [두 종의 공유 재고 재현](../../../Tools/Editor/check_r9_vegetation_reference.py)

R9 M1의 멧돼지에게 같은 셀에서 풀 0.200과 뿌리 0.059·0.060·0.100을 주고 사체가 없는 상태에서 `EAT` 한 번을 요청했다. 두 개발 시드 모두 뿌리 0.059는 처음부터 풀을, 0.060은 첫 물리 스텝 뿌리 0.018 이후 두 번째 스텝 풀 0.036을, 0.100은 두 스텝 모두 뿌리 0.018씩을 지급했다. 서로 다른 먹이의 지급과 잔량을 각 자원 장부와 대조했다. 기존 식성 순서는 뿌리→사체→풀이므로 사체가 가까이 있는 조건과 개체가 스스로 섭식을 선택하는 조건은 별도다. [먹이 전환 재현](../../../Tools/Editor/check_r9_vegetation_reference.py) · [R9 식성 설정](../../../../herbivore_rl/configs/v3_r9.yaml)

같은 두 시드에서 뿌리 0.060과 고기 0.200을 주고 사체 거리만 0.5와 5 R9 단위로 바꿨다. 두 경우 첫 스텝에는 뿌리 0.018을 먹었다. 두 번째에는 가까운 사체에서 고기 약 0.005926을 먹었고, 먼 사체 조건에서는 풀 0.036을 먹었다. 별도 조건에서는 뿌리 0.059와 가까운 사체의 고기 0.003을 준비했다. 첫 스텝에 고기가 고갈되자 두 번째 스텝에 풀로 전환했다. 세 자원별 재고와 실제 지급, 고기 부패의 수지는 모두 일치했다. 이 시험은 `EAT`가 요청된 위치에서의 기존 선택 규칙이며, 사체 탐색이나 이동 선택은 입력으로 주지 않았다. [먹이 전환과 사체 거래 재현](../../../Tools/Editor/check_r9_vegetation_reference.py)

기존 학습 가중치 `fauna_r2/boar/boar_r2_7154688.npz`도 원본 Fauna 설정에서 몸 해시 검사를 거쳐 실행했다. 두 개발 시드의 같은 여섯 조건 중 뿌리 0.060과 고기 0.200의 사체가 0.5 R9 단위 안쪽에 있는 조건에서만 최대 점수 행동이 `EAT`였고, 실제 지급은 뿌리→고기로 이어졌다. 사체가 없거나 멀거나 고기가 0.003인 나머지 조건은 `WALK_225`였고 지급은 없었다. 이 결과는 단일 개체·한 결정·최대 점수 추론의 비교다. 환경이 허용하는 먹이 전환과 정책이 먼저 섭식을 요청하는 영향을 함께 볼 수 있으며, 장기 탐색이나 섬에서의 실제 선택은 별도 검증이다. [출발 팩과 검증 절차](../R9_CLOUD_TRAINING.md) · [두뇌 요청과 실제 지급 재현](../../../Tools/Editor/check_r9_vegetation_reference.py)

같은 두뇌와 두 시드로 한 개체를 120결정(32게임초)까지 실행했다. 고기 0.200을 5 R9 단위 떨어진 곳에 두자 첫 결정은 걷기였지만 10·13번째 결정에서 첫 사체 지급을 받았다. 접근 중 기록된 최소 거리는 0.392·0.271 단위, 총 고기 지급은 0.142222·0.154074였다. 가까운 사체에서는 첫 결정부터 지급이 있었고, 사체 없는 대조에서는 120결정 동안 `EAT` 요청이나 지급이 없었다. 모든 실행에서 시작 재고 = 잔여량 + 지급 + 부패를 자원별로 확인했다. 이 대비는 먹이가 한 셀에 모인 작은 세계에서 기존 학습 두뇌의 최대 점수 실행을 재현한다. 다른 동물과 경쟁하거나 지역을 옮기는 경우의 반응은 이 시험 범위 밖이다. [120결정 대조 재현](../../../Tools/Editor/check_r9_vegetation_reference.py)

## 말의 육상 먹이 선택과 실제 지급

[권위 먹이 선택 발췌](island_ground_food_choices_20261114.json)를 Python에서 재생하면 군락 재고·거리·식생 선호·유효 요청을 이용해 말 44번의 지상 판단 32건을 대조한다. 시드 20000의 37.2초에는 두 실행에서 접근 가능한 후보·거리·재고가 같았다. 요청이 없는 말은 열린 초지를 골라 다음 지급으로 53초에 0.270을 받았고, 서쪽 초지 요청을 받은 말은 41초에 서쪽 초지에서 2.431을 받았다. 별도 강우 실행의 서쪽 초지 실제 지급 시도는 83건이었다. 두 시드의 지급 51건과 재고 하한에 걸린 미지급 32건의 값을 다시 계산했다. 이 자료의 지급 시도에는 거리·시야 거절 기록이 없었으며, 지상 후보 점수는 Unreal의 시야·지면 검사를 이미 통과한 행을 사용한다. [Unreal 대조와 재현 조건](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#먹이원-전환과-대체-접근)

```bash
python AdaptiveEcosystem/Tools/EcoVegetationEval/check_ground_food_choice.py \
  AdaptiveEcosystem/Docs/RL_Policy/Examples/island_ground_food_choices_20261114.json
```

[풀과 관목 분류 대조](island_forage_guild_comparison_20261114.json)는 같은 먹이터의 식생 분류만 `GRASS`에서 `BROWSE`로 바꾼 PIE 4회와 시드별 대조 2회를 담았다. 시작 개체·두뇌·재고와 패치별 용량·재생·끼니 에너지는 같았다. 서쪽 초지를 바꾸면 두 시드에서 권위 29.35초의 말 44번 선택이 열린 초지로 이동했지만, 31.15초에는 서쪽을 다시 골랐고 33·32초의 첫 지급은 양쪽 모두 서쪽에서 2.8이었다. 열린 초지를 바꾼 실행은 같은 입력으로 비교 가능한 15개 판단에서 점수는 달라지고 선택은 같았다. 두 시드의 열린 초지 지급 합계는 4.636→7.310과 0→6.178이었다. 후반에는 경쟁 개체가 남기는 재고와 위치도 달라져, 지급이 늘어난 원인을 말의 선호 하나로 귀속할 수 없다. 위 실행 명령의 JSON 경로만 이 파일로 바꾸면 재현된다. 이 시험은 종류별 선택 가중치의 영향이며 영양소나 성장률은 고정했다.

최신 저장 섬의 [고수위 강변 접근점 대조](island_flooded_ground_forage_20261114.json)는 시작 위치·수위·먹이 예산을 고정하고, 시험 중에만 마른 강둑 접근점을 제거한 경우와 저장 상태를 비교한다. 뿌리가 27.4cm 잠긴 조건에서 말은 두 시드 모두 뿌리에서 17.1cm 이내에 들어왔지만 지급은 0이었고 재고 10이 남았다. 실제 저장된 접근점은 수면 위 약 8.6cm였으며, 양쪽에서 31초에 첫 지급을 받아 160초까지 각각 20회 섭취했다. 도하 검사에서는 저수위에 네 종의 두 체급이 통과했고, 고수위 뿌리 경로는 설정상 35cm까지 건너는 물소만 통과했다. 실제 지급을 검증한 개체는 말 41번이다. 위 `check_ground_food_choice.py` 명령의 JSON을 이 자료로 바꾸면 수위·도하 한도와 기록을 대조할 수 있다. [Unreal 지면 검사](../../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureAnimationBuilder.cpp)

[끼니당 지급 상한 대조](island_forage_meal_cap_20261114.json)는 서쪽 초지의 `EnergyPerMeal`만 2.8→1.4로 낮춘 두 시드의 PIE와 각 대조를 담았다. 시작 개체·재고·재생률·식생 분류는 같았다. 두 시드 모두 권위 29.35초의 첫 목표는 열린 초지로 바뀌었고, 첫 지급은 33·32초에 서쪽 초지에서 일어났다. 시드 20000은 서쪽 초지에서 2.8을 한 번 받던 것이 1.4씩 두 번으로 나뉘어 합계가 같았다. 시드 20017은 같은 군락의 합계가 3.213→1.400으로 감소했다. 위 `check_ground_food_choice.py`로 선택과 지급 상한을 재검산한다. Unreal 재현은 `run_jyu_island_audit.ps1 -Headless -GroundFoodAuditAgent 44`에 새 `-Label`과 `-Scenario '-EcoIslandWestMeadowHalfMeal'`을 전달한다. 이 값은 한 거래에서 지급하고 차감할 에너지의 상한이다. 단위 건물량당 영양 밀도를 표현하려면 별도 모델이 필요하다. [군락 지급 코드](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h)

## 플레이어 사냥에서 공유 사체와 섭취까지

[강변 실제 실행 표본](island_player_carrion_actual_20261114.json)은 최신 JYU 섬의 두 시드에서 무발사 대조, 늑대 사냥, 쥐 사냥을 발췌했다. 각 실행의 대상 ID·사망 원인·공유 재고·섭취·만료와 보고서 및 로그 SHA-256을 담는다. 시드 20000의 쥐 사체는 11.711 중 늑대가 8.000을 먹고 3.711이 만료됐다. 20017에서는 여우가 살아 있는 먹이로 전환했고 표범이 위협으로 물러나 12.253 전량이 만료됐다. 플레이어 위치는 시험에서 제어했다. [실행 경계와 대조 기록](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#플레이어-발소리와-강변-통과)

Python에서는 [R9 사체 확인 도구](../../../Tools/Editor/check_r9_carrion_reference.py)를 저장소 루트에서 실행한다. 기존 M1 설정과 개발 시드 44190·44191로 작은 세계에 재고 4의 사슴 사체를 준비한다. 근처 늑대 둘이 `EAT`을 요청하면 자리 1개에서는 가까운 늑대만 먹고 자리 2개에서는 둘 다 먹는다. 같은 위치에서 `WATCH`를 요청하거나 거리 5단위에서 `EAT`을 요청하면 지급은 0이다. 두 시드의 네 조건에서 위치가 유지됐고 생성 재고와 지급·잔여·부패량이 오차 1e-12 안에서 일치했다. `step(actions)`는 물리 두 스텝으로 이루어진 결정 1회다. 근거리 지급은 결정 전체에서 자리 1개 0.032, 2개 0.064 R9 고기 단위였고 각 조건의 부패는 약 0.005926이었다. 실행 환경은 Python 3.12.14, NumPy 2.3.5, PyYAML 6.0.3이다. [R9 실제 먹이 지급과 부패 구현](../../../../herbivore_rl/env_v2/r9_world.py)

| 비교 항목 | 기존 Python R9 | 이 Unreal 장면 |
| --- | --- | --- |
| 사체 발생 | 물기·반격·기아의 사망을 자원으로 전환한다. 확인 도구는 이미 생긴 사체를 입력한다. | 플레이어 피해가 권위 사망으로 확정된 뒤 같은 개체 ID에 공유 재고가 생긴다. |
| 먹기와 선택 | 근처에서 실행한 `EAT`이 같은 혈족의 사체를 제외하고, 거리 순으로 식사 자리를 배분한다. | 권위 실행기는 허기·위협과 살아 있는 먹이·사체를 비교한 뒤 실제 위치에서 지급한다. 규칙 종의 같은 종 허용, 사체의 수역·지역·가용 시간, 자리를 별도로 적용한다. |
| 재고 변화 | R9 고기 단위가 물리 스텝마다 감소한다. | 이 표본은 생명력 에너지 단위로 지급을 기록하고, 남은 분량은 사체 만료 때 장부에 나타난다. |

두 실행은 각자의 공유 재고 수지를 입증한다. 공통 스텝 비교에는 사체 생성·활성·종료 시각, 단위 변환, 같은 종 허용, 시간대·지역·도달 조건, 행동 요청과 실제 지급을 버전으로 고정한 별도 입력이 필요하다. 이 발췌는 `training_ready=false`다.

`check_r9_carrion_reference.py --learned-encounter`는 원본 Fauna의 `fauna_r2` 늑대·표범 두뇌를 몸 해시 검사 후 최대 점수 방식으로 함께 실행한다. 두 개발 시드에서 시작 거리 1.5 또는 5 R9 단위와 중앙 사체 0 또는 0.200을 비교해 각각 120결정(32게임초)을 실행했다. 가까운 조건에 사체를 두면 표범이 두 시드에서 각각 약 0.198519를 섭취했고, 먼 조건에서는 지급이 없었다. 표범은 사체 유무와 관계없이 모든 결정에서 `EAT`를 요청했고 늑대는 한 번도 요청하지 않았다. 여덟 실행에 물림이나 사망이 없었다. 이는 성체 두 마리의 한 방향 배치와 허기에서 얻은 비교다. 자연 실행에서 관찰됐던 드문 늑대–표범 충돌을 배제하는 근거로 쓰지 않는다. [두뇌 실행과 자원 장부 재현](../../../Tools/Editor/check_r9_carrion_reference.py)

시작 거리 1.5인 조건에서 표범의 초기 체력만 1.00에서 0.35로 낮춘 네 실행을 추가했다. 건강한 표범은 120결정 내내 제자리에 있었고, 부상 조건에서는 네 사례 중 세 사례에서 `EAT` 요청 한 번이 이동으로 바뀌어 약 0.20 R9 단위를 이동했다. 같은 시드의 늑대 이동 거리와 두 개체의 최단 표본 거리는 체력 변경 전후 같았다. 사체가 있는 조건의 표범은 두 시드 모두 기존과 같은 고기 약 0.198519를 받았고 물림·사망 기록은 없었다. 이 대조는 한 쌍의 최대 점수 행동에서 부상 입력을 바꾼 결과다. 무리 크기·지형·상대 허기가 다른 장면과 자연 실행의 물림 빈도는 따로 비교한다. [부상 대조 재현](../../../Tools/Editor/check_r9_carrion_reference.py)

출발 팩의 R1·R2 자연 실행 JSON은 학습 모델과 규칙 모델을 각각 보고한다. 늑대가 표범을 물어 죽인 횟수는 기본·물소 중심 순서로 R1 학습 1·1, R2 학습 0·0, 두 보고서의 규칙 모델 2·6이었다. 현재 팩의 R2 학습 두뇌 6종으로 `fauna_report.natural`을 두 조건 각각 10세계·1,350결정 실행했다. 두 조건 모두 기존 R2의 종별 포획 집계와 표범 사망 원인이 일치했다. 물소 중심에서 표범 기아 2건이 있었고, 기본에서는 표범 사망이 없었다. 이 비교는 기존 자연 보고용 설정과 시드를 사용했다. 팩의 R1 보고서는 사건별 좌표·허기·부상·추격 궤적을 포함하지 않고 R1 가중치도 이 팩에 없다. 집계만으로 최초 충돌을 유발한 상태를 역추정하지 않는다. [R1 원본 JSON](../../../../herbivore_rl/results/v3/r9/packs/fauna_r2/reports/eval/fc_r1.json) · [R2 원본 JSON](../../../../herbivore_rl/results/v3/r9/packs/fauna_r2/reports/eval/fc_r2.json) · [자연 실행기](../../../../herbivore_rl/results/v3/r9/fauna_report.py)

같은 자연 실행기에 `--trace-wolf-leopard`를 추가해 기존 집계와 사건을 함께 검증했다. 출발 팩 R2의 6종 학습·규칙 두뇌를 기본·물소 중심 조건에서 각각 10세계×1,350결정 돌렸고, 네 조건 모두 기존 보고서의 종별 포획 집계를 재현했다. 학습 두뇌에는 기본 2건·물소 중심 2건의 비치명 물림이 있었다. 학습 두뇌의 늑대→표범 물림 3건 중 2건은 늑대 에너지가 약 1인 상태에서, 1건은 0.412에서 일어났다. 네 사건 중 세 건은 공격 개체 2 R9 단위 안에 활성 사체가 있었다. 같은 조건의 규칙 두뇌에는 두 종 사이 물림이 각각 19·33건이었다. 사체 근접과 에너지는 사건 시점의 동반 조건이다. 이전 이동 이유나 공격 동기를 판정하려면 연속 관측과 별도 개입 대조가 필요하다. 원본은 `Saved/FaunaAudit/IslandAccessBaseline/r9_wolf_leopard_trace.json`이다. [사건 기록 도구](../../../../herbivore_rl/results/v3/r9/fauna_report.py)

학습 실행의 네 사건을 팩·원본 보고서 해시와 함께 발췌했다. 기본 환경 시드 46680의 299번째 물리 스텝에서 늑대의 현재 행동은 `WALK_180`이었고, 표범까지의 거리 0.367 R9 단위에서 물림 부상이 기록됐다. R9는 이동 뒤 재사용 대기, 상대 체급, 거리·방향·접근 속도와 은신처 조건으로 물림을 판단한다. 걷기·달리기 기록은 정책 요청이고, 물림은 권위 접촉 결과다. 향후 Unreal 대응 자료에도 관측, 요청, 실제 이동·접촉, 피해를 시간순으로 남긴다. `training_ready=false`다. [학습 두뇌 물림 사건 발췌](r9_wolf_leopard_contact_actual_20261114.json) · [R9 접촉 판정](../../../../herbivore_rl/env_v2/r9_world.py)

`--trace-wolf-leopard --trace-carcass-decay-steps 135`는 원래 설정으로 가중치와 몸 해시를 검사한 뒤 진단 세계에서 사체 부패 기간만 기존 1,350→135 물리 스텝으로 바꾼다. R2 학습 두뇌로 두 환경 각각 같은 10세계·1,350결정을 대조했다. 기본 환경의 늑대–표범 물림은 양쪽 모두 2건이었으나 부패가 빠른 쪽에서 늑대가 표범을 물어 죽인 1건이 발생했다. 물소 중심에서는 물림이 2→0건, 표범 기아는 2→3건이었다. 기본 환경의 늑대 고기 섭취 합계는 46.547→36.978, 물소 중심에서는 34.338→19.850이었다. 생성 재고와 지급·부패·초과 유실·잔량은 세계별로 대조했다. 전체 생태 궤적이 달라지는 진단이므로 개별 공격의 원인을 판정하는 데 쓰지 않는다. 원본 `Saved/FaunaAudit/IslandAccessBaseline/r9_carcass_decay_comparison.json`. [진단 실행기](../../../../herbivore_rl/results/v3/r9/fauna_report.py)

## JYU 섬 16종과 R9의 대응 범위

현재 R9 Fauna Motion 학습 설정의 종은 사슴·늑대·멧돼지·물소·표범·여우다. 로컬 섬의 실제 실행은 사슴 R7e, 늑대 Native v3 위협 FSM, 나머지 14종 RuleFauna다. 학습 팩에 종이 들어 있다는 사실과 이 맵에서 그 가중치를 사용했다는 사실을 따로 기록한다. R9 소스의 쥐·까마귀 이름은 예약되어 있고, 현재 1단계 몸 계약은 최대 6종을 허용한다. [종 제한과 몸 계약](../../../../herbivore_rl/env_v2/r9_body.py) · [현재 6종 설정](../../../../herbivore_rl/configs/v3_r9_fauna_motion.yaml)

| 대상 | 기존 Python에서 확인할 수 있는 공통 요소 | 학습 환경에 필요한 대응 |
| --- | --- | --- |
| 사슴·멧돼지·물소 | 지상 이동, 식물 자원·허기·섭취, 체격과 성장 | 섬의 경사·단차·통로, 공간적으로 흩어진 군락과 고갈·재생, 식생 은폐, 시간대·강우·토양 수분을 동일한 단위와 입력 시계에서 비교한다. |
| 늑대·표범·여우 | 지상 사냥, 허기, 공격 가능 관계, 공유 사체 | 감지·접근·접촉·피해·먹이 전환·이탈을 사건별로 기록한다. 희귀 충돌 빈도는 비교 데이터로 쓴다. 플레이어와 가림, 사체 재고·만료를 먼저 맞춘다. |
| 쥐·큰뿔양·산토끼·말 | 지상 이동과 식물 거래의 기존 구성 요소 | 몸 크기에 따른 접근, 은신처와 고원·하류 연결, 종별 식성 및 먹이터 전환을 검증한다. |
| 까마귀·검독수리 | 공유 사체 이용을 대조할 수 있다. | 이륙·순항·착지·횃대, 시야와 공격 접근 및 먹이형의 연결이 필요하다. |
| 밍크 | 공유 먹이 선택과 대사 개념을 대조할 수 있다. | 지상 접근 → 입수 → 유영·섭취 → 상륙 → 마른 지면의 충돌·수심·유속·스태미나를 관측한다. 수위가 바뀌면 입수와 상륙의 가능 여부를 각각 갱신한다. |
| 아리아케 메기류·잉어·가상 소형어류 | 유한 자원과 소비 장부를 대조할 수 있다. | 수면·바닥·유속·수심, 수역 연결, 성장별 몸체 여유, 실제 산란 예약·취소·부화와 섭취 장부를 맞춘다. 가상 소형어류는 참고 생태 유형을 별도로 기록한다. |

인계 시 같은 맵 저작본·초기 개체군·몸·정책 버전·시드·자원 예산을 고정하고 행동 요청, 실행 가능성 검사, 결과, 자원 증감을 시간순으로 기록한다. 6종의 기존 팩과 개발 시드는 그 계약의 기준으로 계속 쓴다. 신규 10종 및 섬 전체 대응 자료의 상태는 `training_ready=false`다. [로컬 적용과 검증 기준](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md) · [Dots 학습 계약](../R9_CLOUD_TRAINING.md)

### 종별 실행과 다음 비교 장면

현재 섬의 시작 실행기는 사슴 R7e, 늑대 Native 위협 FSM, 나머지 14종 RuleFauna다. R9 Fauna Motion의 기존 팩은 첫 여섯 종용이다. Python 종 목록에 쥐·까마귀 이름도 예약돼 있으나 `STAGE1_MAX_SPECIES=6` 이후에 놓여 있고, 이 두 종의 굴·비행 계약과 재개 팩은 아직 필요하다. [Python 종 순서](../../../../herbivore_rl/env_v2/r9_body.py) · [섬의 두 시드 실행기와 결과](island_patch_input_population_baseline_20261114.json)

| Unreal 종 ID | 현재 기준에서 확인한 동작 | 섬 대응에서 먼저 비교할 조건 |
| --- | --- | --- |
| `Herbivore` 사슴 | Native 식생 섭취와 두 시드 60분 생존·출생 | 설원·초지 경계 이동, 셀 재고 차감, 감지·회피와 실제 도착 |
| `Wolf` 늑대 | Native 포식과 공유 사체 섭취 | 살아 있는 먹이와 사체의 경로, 주변 동료와 회피 비용, 실제 피해와 공유 재고 |
| `Pig` 멧돼지 | 두 시드 공유 사체 지급, 통제 시험에서 두 번째 부모 보호 | 식물·사체 선택과 뿌리 파기, 이미 있는 부모가 공격 경로를 막았을 때의 결과 |
| `Buffalo` 물소 | 두 시드 지상 군락 지급, 도섭 가능한 뿌리 쪽 제어 시험 | 체급·성장별 물가 접근, 건강·주변 성체 조건에 따른 피격 가능 여부 |
| `Leopard` 표범 | 기준에서 사체 이용, 통제 시험에서 부상 쥐 선택·포획 | 같은 거리에서 허기·부상·체급만 바꿔 감지, 추적, 포획, 이탈을 비교 |
| `Fox` 여우 | 여우가 선택한 쥐·산토끼 추적과 포획, 공유 사체 지급 | 체급을 바꿔 후보 범위 확인, 대상이 실행 전 죽거나 멀어졌을 때의 결과 |
| `Rat` 쥐 | 저장 섬의 Riverbank 여우 포획, 강변 저상 통로의 체급별 통과와 자력 진입, Python 입구 선택과 가림 계산 대조 | 청각까지 포함한 위협 감지 순서, 연속 지면 이동·이탈, 두 번째 출구로 재진입 |
| `Bighorn` 큰뿔양 | 두 시드 지상 군락 지급, 범람 지점 접근 차이 | 경사·입구 폭을 따로 바꿔 실제 왕복과 군락 지급 비교 |
| `Jackrabbit` 산토끼 | 중간 먹이터 도착·지급, 두 시드 지상 군락 지급 | 경유지 이동비, 가림, 도착 뒤 대체 먹이터 전환 |
| `Horse` 말 | 군락 간 전환, 범람 뒤 마른 접근점 지급 | 공유 재고의 두 접근점, 경쟁자 도착 순서, 독립 귀환 통로 |
| `Crow` 까마귀 | 두 시드의 공용 사체 지급과 멧돼지의 동시 지급, Python 재고 대조 | 이륙·착지 시점, 우선권 전후의 접근과 실제 경쟁 |
| `GoldenEagle` 검독수리 | 고원 포획 후 착지·섭취, 가림과 체폭 충돌·수직 착지·사체 지급의 Python 대응 | 자연 지형의 독립적인 재접근과 착지점 선택, 여러 개체의 현장 경쟁 |
| `Mink` 밍크 | 저장 섬의 입수·섭취·독립 출구·마른 둑 도착, Python의 고수위 출구 선택과 유영·상륙 위치 대조 | 수위와 포만이 지속적으로 바뀌는 왕복, 충돌 후 독립적인 경로 재탐색 |
| `AriakeCatfish` 아리아케 메기류 | 군락↔소형어류 사체 전환과 통제 낮밤 탐색·지급 | 실제 수류·가림 조건에서 감지 범위, 경로, 정지 및 한 입 지급 |
| `CommonCarp` 잉어 | 산란 예약·퇴수 취소·복원 후 부화·치어 섭취 | 생애 단계별 수심 통과, 예약 ID와 수위 순서, 부화 뒤 첫 지급 |
| `UnidentifiedFish` 가상 소형어류 | 저장 섬의 섭취·생존과 실측 물길 우회 후보 | 실제 이동과 재고 감소, 저수위에 물길이 갈라질 때의 피난 선택 |

신규 종의 준비 순서는 기존 지상·재고 요소를 재사용할 수 있는 종, 수심을 쓰는 수생 종, 지상·수중을 오가는 밍크, 연속 비행과 착지가 필요한 조류로 제안한다. 각 종은 대응 세계에서 감각·행동 요청·허용·실행·권위 결과를 연결한 뒤에 학습 대상으로 지정한다. 이 표의 검증 결과에는 서로 다른 시험의 근거가 함께 들어 있다. 60분 기준에서의 4종 생존은 16종의 장기 안정성을 판정하기에 부족하다.

[강변 쥐 통로 발췌](island_river_rat_refuge_geometry_20261114.json)는 시험 입구의 길이·폭·높이와 Unreal에서 읽은 쥐·여우 몸체 값을 제공한다. 시드 20047의 두 배치에서 Python의 평탄 통로 기하가 양방향·두 체급의 스윕 결과 32건과 일치했다. 직선 배치에서는 쥐 한 마리가 지붕 밑에서 관측됐으나 그때 기록된 대피 목표는 없었다. 회전 배치에서는 네 마리가 지붕 밑에 들어갔고 대피 목표도 기록됐다. 위치와 목표는 Unreal 표본이며 Python이 목표 선택과 이동을 독립적으로 계산한 범위는 아니다.

같은 검사에서 두 배치·두 지점마다 쥐의 시작 방향 세 가지를 시험했다. Python은 체폭을 포함해 옆벽 충돌을 계산하고 Unreal의 지면 스윕 36건과 대조했다. 중심으로 직진할 수 없었지만 입구를 거쳐 도달할 수 있는 시작점은 각 배치에서 4개였다. 시작점은 통제 입력이고, 충돌 계산은 평탄한 시험 통로의 보수적인 직사각형 근사다.

Unreal의 `ShelterApproachPoints`는 대피 전용 입구를 정의한다. 지상 종이 도피할 때 직진이 막히면 입구까지의 시야와 두 구간의 체폭 스윕을 검사하고, 선택한 목표를 기존 지상 이동기에 넘긴다. 임시 강변 통로를 사용하는 두 시드에서 입구 쪽으로 실제 이동한 뒤 대피 반경에 들어간 창시 개체가 2·4마리였다. `unreal_approach_trials`에 입구 이동 시각·첫 도달 표본과 원본 해시를 보존했다. 당시 빌드의 별도 프로세스 복원에서 입구 4곳과 군락 재고 24곳이 일치했고, 두 시드에서 예약된 잉어가 이어 부화했다. 입구 하나를 20cm 옮긴 대조는 지도 배치 불일치로 거절됐다. `checkpoint_validation`에 원본 해시와 거절 사유를 기록했다.

이후 소유 섬에 두 강변 대피처를 저장했다. 지붕이 로드된 상태에서도 중심을 작성된 바닥 높이에서 찾도록 초기화를 수정했다. `rat_saved_floor`의 두 시드에서 쥐 2·4마리가 대피 목표를 잡고 실제로 진입했고, 작성 먹이 총용량 215가 유지됐다. 시드 20047의 렌더에서 입구와 주변 개체를 확인했으며, 구조물 외형은 기초 메시다. 바닥 수정 뒤의 [저장 섬 새 기준](island_saved_refuge_regression_20261114.json)은 두 시드의 60게임분과 저장·복원을 기록한다. 60분 생존은 29·30마리였고 쥐는 두 실행 모두 피식됐다. 새 프로세스 복원에서 24곳 재고와 입구 4곳이 일치했고 잉어 부화가 이어졌다.

[Python 강변 대피 모델](../../../Tools/EcoVegetationEval/island_rat_reference_world.py)은 입구·벽·지붕 좌표와 시작 위치로 직진 또는 입구를 경유하는 경로를 고른다. `rat_saved_floor`의 연속 두 이동 행에서 앞 행의 도착 위치로 다음 입구를 계산해 두 시드의 171·235건을 대조했다. `rat_sight_final`에서는 같은 저장 지형에서 벽·지붕·입구를 지나는 Unreal 시야 선 20개와 종의 감지 설정을 읽어 Python과 일치하는지 확인했다. 낮밤의 감지 거리, 시야 방향, 위협 기억과 해제는 Python 통제 시험으로 확인했다. Unreal 쥐의 감지 순서와 이동 궤적까지 비교하려면 청각·실제 추격 상태·가속·지면 대응을 같은 시점에 기록해야 한다. [측정값과 권위 기록](island_river_rat_refuge_geometry_20261114.json)

로컬에서 Fauna Motion을 개발 시드 44190·44191로 열어 20스텝의 관측과 보상이 유한하고 관측 배열이 `[2, 100, 115]`인지 확인했다. 행동 수는 19, I/O 해시는 `0x0fa76480fe9465e0`, 몸 테이블 해시는 `0x8e269ff19752d959`다. 같은 개발 시드의 한 자리·두 자리·관찰·범위 밖 사체 대조 8건도 자원 수지를 통과했다. 이 결과에는 훈련, 평가 시드 판정 또는 새 Unreal 기능의 궤적 검증이 포함되지 않는다. 로컬 원본은 `Saved/FaunaAudit/IslandAccessBaseline/island_r9_contract.json`과 `island_r9_carrion_reference.json`이다. [R9 사체 대조](../../../Tools/Editor/check_r9_carrion_reference.py)

현재 Unreal 빌드의 R9 코어와 Python을 개발 시드 44190의 기존 3종 S′, 6종 Fauna, 6종 Fauna Motion으로 대조했다. 제공된 `dump_fauna.py`를 각 설정에 `--decisions 300 --chain-every 10`으로 실행하고, 덤프를 로컬 `Saved/R9Demo/parity/chain_{sprime,fauna,motion}.txt`에 보관했다. `-EcoR9RequireFauna`로 실행한 `ParityChain`과 `MotionBlocked`는 모두 경고·실패 0이었다. 각 장면의 물리 스텝 600개에서 상태·관측·난수 사용이 일치했고, 회전 한계 장면은 10,821회 회전을 제한하며 허용 각도 초과가 0이었다. 규칙과 혼합 행동을 사용한 기존 R9 코어 대조이며, 섬의 전체 세계나 신규 종 정책의 대응 범위는 위 표에 따른다. 원본 보고서는 `Saved/Automation/IslandR9Checks1454/index.json`이다. [덤프 도구](../../../../herbivore_rl/results/v3/r9/dump_fauna.py) · [Unreal 자동화](../../../Source/AdaptiveEcosystem/AI/Policy/R9/EcoR9DemoTest.cpp)

수변의 첫 대응 장면은 두 개다. 잉어는 같은 하상과 XY에서 수위를 내리고 저장된 선반 높이가 수면 아래인지와 치어의 실제 지급을 확인한다. 밍크는 같은 먹이 예산에서 입수→섭취→상륙→마른 둑 순서를 확인한다. 발췌에는 각각 권위 시간과 사용한 배치, 원본 보고서 해시가 들어 있다. Python에서 필요한 수역·체격·충돌을 재현한 뒤 관측과 실제 결과를 대조할 입력이다. [잉어와 밍크의 실제 수변 발췌](island_shore_recovery_actual_20261114.json)

[수위와 체격 대조 입력](island_water_access_geometry_20261114.json)으로 두 시드의 수주와 상륙 지점을 Python에서 확인할 수 있다. 퇴수 시 유입부 수심은 약 48cm다. 기존 선반 중심은 수면 위였고, 낮춘 중심은 수면 아래 약 24cm로 두 시드의 치어 여유를 충족했다. 첫 위치 표본은 퇴수 수면 위, 다음 표본은 수주 안이었다. 퇴수 중 실제 선반 지급 기록도 시드당 세 건이다. 24cm 범람에서는 이전 밍크 둑 표본이 수면 아래 약 15.7cm, 저장된 독립 경사로의 상륙점은 수면 위 약 10.0cm였다. 두 시드의 입수·섭취·상륙·마른 지면 도달을 권위 사건 순서로 확인했다.

재생기는 Unreal에서 조회한 하상·수면과 몸 중심 여유를 입력으로 삼아 잠김과 수직 통과 조건을 계산한다. 실제 섭취와 도착은 Unreal 결과와 함께 보관한다. Python 경로 탐색, 충돌 스윕, 수류·스태미나, 개체의 먹이 선택을 검증하려면 별도 연속 경로 입력이 필요하다. [수주 조회와 체격 검사](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureMovement.cpp) · [수중 이동과 상륙 구현](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaWaterMovement.cpp)

```bash
python AdaptiveEcosystem/Tools/EcoVegetationEval/check_water_access_parity.py \
  AdaptiveEcosystem/Docs/RL_Policy/Examples/island_water_access_geometry_20261114.json
```

[잉어 산란장 예약과 퇴수](island_nursery_reservation_20261114.json)를 위 Python 명령으로 재생하면 예약한 지점의 잠김을 같은 순서로 검사한다. 두 시드 모두 권위 186초에 유입부 예약이 취소됐고, 190초 이후 다시 잠겨도 원래 예약은 복구되지 않았다. 계속 잠겨 있던 가장자리의 예약은 검사를 통과했으며 Unreal에서는 시드별 한 마리가 부화했다. 유입부 부모의 새 예약은 관찰 종료 때도 부화 예정 시각 전이었다. 같은 예약에 수위만 계속 유지한 Python 대조에서는 원래 예정 시각에 부화 조건을 통과했다. 이 대조에서 부모 상태·개체수 제한·수온·유속·실제 생성 위치 검사는 입력으로 고정하며, 좌표와 수위는 권위 표본이다. [Unreal 산란장 예약과 재현 조건](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#어류-산란장-예약과-퇴수)

[잉어의 실제 먹이터 전환](island_carp_food_choices_20261114.json)은 시드 20000·20017에서 104번의 감각 거리, 현재 재고, 접근 판정, 먹이 점수, 선택과 권위 지급을 연결한다. 양쪽에서 InletPlants를 먹어 재고가 0이 된 다음 판단에 해당 먹이터가 재고 하한으로 제외됐고, 인접한 SlowShelf를 선택해 첫 지급 2게임초 뒤 실제로 0.9를 받았다. 195~225초 발췌에서 앞선 지급으로 재고가 0이 된 뒤 다른 먹이터에서 지급받은 건수는 6·11건이었다. 위 Python 명령에 이 JSON을 전달하면 62개 판단과 25개 지급의 연결을 재현한다. 수중 가림과 통과 판정은 Unreal에서 기록된 값을 사용한다. 신규 종의 관측 벡터나 R9 학습 보상을 정의하려면 별도 계약이 필요하다. Unreal 재실행에는 `run_jyu_island_audit.ps1 -Headless -Label carp_food_choice -Scenario @('-EcoIslandShoreRainTrial','-EcoIslandWaterFoodAuditAgent=104')`를 사용한다. [수중 선택과 계측](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaWaterMovement.cpp)

아리아케 메기의 수중 사체 후보도 같은 감각 단계에서 기록한다. 새 빌드의 두 1,080초 실행에서 각각 1,080개 결정과 사체 점수 54·57건을 확인했다. 두 시드에서 뿌리 군락이 비자 소형어류 사체를 고르고 실제로 1.5를 받았다. 재고가 회복되자 뿌리 군락으로 돌아왔고 전체 먹이 종류 전환은 4·2회였다. [두 시드의 1,018~1,052초 발췌](island_catfish_food_switch_20261114.json)에서 거리·재고·가용 식사량·거절 사유와 점수를 확인할 수 있다. Python은 사체 기본 점수를 다시 계산하고 최종 순위·선택·실제 지급을 대조한다. 수중 가림·예약·권위 지역 판정은 Unreal 기록을 입력으로 사용한다.

```powershell
./AdaptiveEcosystem/Tools/Editor/run_jyu_island_audit.ps1 -Mode Population -PopulationSeconds 1080 -Label catfish_candidate -WaterFoodAuditAgent 102
python AdaptiveEcosystem/Tools/EcoVegetationEval/check_catfish_food_switch.py AdaptiveEcosystem/Saved/FaunaAudit/IslandAccessBaseline/20000_catfish_candidate.log
python AdaptiveEcosystem/Tools/EcoVegetationEval/check_catfish_food_switch.py AdaptiveEcosystem/Docs/RL_Policy/Examples/island_catfish_food_switch_20261114.json
```

[최신 섬의 먹이터 연결 격자](island_water_food_connectivity_20261114.json)에는 같은 저장 맵의 두 시드에서 저수위·고수위·퇴수 후에 읽은 1.5m 간격 수심, 먹이터 좌표와 Unreal의 판정을 담았다. 위 명령의 파일만 이 JSON으로 바꾸면 메기류·잉어·소형어류의 두 체급과 세 수위에 걸친 먹이터 쌍 228건의 연결 여부와 낮·밤의 명목 탐색 거리를 재계산한다. 두 시드 모두 유효 수주가 1,477→1,600→1,477개로 변했지만 조사된 먹이터 쌍의 격자 연결은 유지됐다. 메기의 Roots–GravelInsects는 연결된 약 43.3m 구간으로 직접 탐색 거리 밖이었다. 소형어류의 Drift–SlowShelf는 직선에서 수주가 빠진 15개 지점이 있었고 격자에서는 우회가 연결됐다. 잉어의 InletPlants–SlowShelf가 조사된 쌍 중 낮·밤 모두 명목 직접 탐색 거리 안이었다. 이 대조는 먹이터 쌍의 물리적 연결과 감각 거리의 첫 검사를 제공한다. 실제 경로 선택, 가림, 연속 충돌, 유속과 재고 지급은 별도로 검증한다. Unreal 재실행에는 `run_jyu_island_audit.ps1 -Headless -Label water_depth_parity -Scenario @('-EcoIslandShoreRainTrial','-EcoIslandSurveyWaterForage','-EcoIslandCaptureWaterForageGrid')`를 사용한다. [권위 격자 계측 코드](../../../Tools/Editor/audit_jyu_island_fauna.py)

비행 대응 장면은 검독수리와 쥐의 높이·거리·차폐, 실제 급강하 선택·접촉 요청·포획, 사체별 지급을 구분한다. 고원 배치 대조에서 포획 없이 큰뿔양 사체를 이용한 결과와 실제 포획 후 지급받은 결과를 모두 담았다. 같은 배치의 시야 전용 대조에서는 관측 광선이 가려진 시간과 실제 사냥 로그의 거절 사유가 달랐다. 광선 표본을 관측 가시성이나 행동 목표 그 자체로 사용하려면 양쪽 환경에서 실제 감지 단계와 시간을 맞춰 검증해야 한다. [검독수리·쥐 고원 대조 발췌](island_highland_eagle_actual_20261114.json)

[검독수리 접촉과 지급 기록](island_eagle_contact_reference_20261114.json)은 같은 고원 배치에서 가림을 켜고 끈 실행 각각을 두 시드로 기록했다. 권위가 접촉을 예약한 16회 중 5회는 포획과 해당 사체의 후속 섭취로 이어졌다. 나머지 11회는 공격 실행 시점에 먹잇감과의 간격이 96.4~115.1cm로 현재 접촉 거리 95cm를 넘었다. Python은 실제 사냥 스캔의 후보 점수, 선택 ID, 접촉 예약, 결과, 사체 지급을 시간순으로 대조한다. 시야나 비행 궤적은 기록된 Unreal 결과를 사용하며 가림이 포획률을 바꿨는지는 이 표본만으로 판정할 수 없다.

같은 자료에서 포획 5건 모두 사체 생성 → 검독수리의 지상 상태 전환 → 첫 지급 순서를 원본 로그로 확인했다. 착지 직전 같은 XY의 공중 표본이 있는 두 건에서는 Python의 수직 하강 예상 시간이 실제 마지막 공중과 첫 지상 표본 사이에 들었다. Python에서 생성 당시 재고와 한 입 상한 5를 사용해 총 15건의 지급과 잔량을 다시 계산했다. 거래 대조에는 착지 좌표를 공용 접점으로 사용했다. 까마귀와의 대조는 통제 입력으로 진행해 사냥 개체의 우선권, 공유 시점 이후 한 자리의 경쟁, 유한 재고와 만료를 확인했다. 두 종이 해당 사체에서 직접 경쟁한 현장 기록은 별도로 확인해야 한다.

`mixed_species_stock`은 최종 섬 두 시드의 첫 실행과 반복 실행에서 조류와 다른 종이 함께 이용한 사체 8구를 발췌했다. Python이 생성 시 공유 재고에서 지급 194건을 로그 순서대로 차감해, 고갈 또는 만료 때 버린 양까지 재현했다. 같은 기록 시각에 서로 다른 종이 먹은 묶음은 20개였다. 시드 20017 첫 실행에서 까마귀·멧돼지·늑대는 물소 사체 129번의 120 중 71을 먹었고 49가 남아 만료됐다. 같은 실행의 큰뿔양 사체 128번은 늑대가 16, 검독수리가 30을 먹은 뒤 55.583이 남아 만료됐다. 시각이 없는 Native 늑대 지급은 로그 순서로 반영했다. 검증은 실제 지급과 폐기를 대상으로 하며 실패한 접근, 서로를 밀어낸 행동, 두 조류가 같은 사체를 이용한 사례는 이 발췌 범위 밖이다.

```bash
python AdaptiveEcosystem/Tools/EcoVegetationEval/check_eagle_hunt_reference.py \
  AdaptiveEcosystem/Docs/RL_Policy/Examples/island_eagle_contact_reference_20261114.json
```

[실행형 급강하 대조](../../../Tools/EcoVegetationEval/island_eagle_reference_world.py)는 고원 쥐 두 지점과 검독수리의 비행 속도 900cm/s, 접촉 거리 95cm, 준비 시간 0.10초를 사용한다. 두 시드에서 정지한 쥐는 포획됐고 접촉 예약 뒤 0.10초 동안 22cm 움직인 쥐는 접촉 범위를 벗어났다. 체급을 올리면 급강하가 거절됐고, 바위가 시야를 가렸을 때와 시야 밖에서 몸의 경로만 막았을 때도 구분했다. 포획된 쥐의 유한 사체량은 한 입 상한과 에너지 여유에 맞춰 빠졌고, 실패에서는 사체가 생기지 않았다. 독수리 시작점, 장애물과 쥐의 움직임·체급·사체량은 제어 입력이다. 이 장면은 Unreal 관측 기록과 같은 조건으로 비행 궤적을 재현하거나 가림에 따른 포획률을 산출하지 않는다. 여러 후보의 선택, 현재 시야 방향, 지형 충돌, 에너지·스태미나, 착지와 사체 접근은 확장할 때 별도로 대조한다.

```bash
python AdaptiveEcosystem/Tools/EcoVegetationEval/check_island_eagle_world.py \
  AdaptiveEcosystem/Docs/RL_Policy/Examples/island_highland_eagle_actual_20261114.json
```

같은 파일의 `saved_geometry`는 저장 섬의 고원 두 지점에서 시야 선과 비행체 반경을 별도로 검사한다. 장애물이 없는 경우, 시야만 가리는 경우, 시야 밖에서 몸만 막는 경우, 둘 다 막는 경우를 두 시드에서 비교했다. Python은 상자 좌표와 독수리 체폭으로 Unreal 조회 16건을 맞췄고, 그 조건에서 각각 도달, 급강하 시작 전 취소, 이동 중 차단을 실행했다. 시험 장애물은 임시 배치이며 정밀 검증 범위는 지정 경로의 기하와 Python의 후속 결과다. Unreal 독수리의 자율 급강하 궤적과 포획 결과는 별도 현장 자료에 있다.

**대피처의 관측과 이동.** 기존 R9 M1을 두 개발 시드에서 실행했다. 사슴을 중심 `(30, 30)`, 반경 5인 대피 원의 바깥 `(35.05, 30)`에 두고 중심을 바라보게 했다. 두 시드 모두 전방 대피 관측값 1에서 `SHELTER` 요청은 제자리에 머물렀고, 전방 걷기 요청 뒤 `O_IN_SHELTER`가 켜졌다. R9의 이 관측은 평면 원과의 관계를 읽는다. 고원 Unreal의 규칙 쥐는 별도 위협 감지와 대피 후보 선택을 거친다. 실제 고원 시험의 도피는 6.5m 탐색 범위, 가림, 지면 접근을 거쳤고, 대피처에서 나온 후에도 포획이 기록됐다. 미래 공통 장면에서는 `후보를 관측 → 접근 요청 → 이동 → 실제 대피 반경 진입 → 이탈`을 각각 검증한다. 입력으로 기록할 것은 후보 위치, 지면·가림과 접근 가능한 구간이며, Unreal의 목적지 선택이나 사망 결과는 비교 출력이다. `training_ready=false`다. [Python 재현 도구](../../../Tools/Editor/check_r9_shelter_reference.py) · [Unreal 접근·입구·포획 표본](island_saved_stage_population_actual_20261114.json)

초지–하류 대응 장면에는 이동 비용, 먼저 도착한 개체의 소비, 뒤따른 개체의 첫 지급과 복귀 판단을 담았다. 같은 144m 통로에서 두 번째 말은 첫 번째 말보다 7초 또는 20초 늦게 도착했다. 재고가 있어 실제 먹은 경우에도 복귀는 관찰되지 않았다. Python 대조에서는 같은 총량과 체격 조건에서 경쟁자의 도착 간격, 도착지 재고와 독립적인 귀환 경로를 따로 바꾼다. 통로 일반화 결과나 말 정책의 보상 목표로 이 수치를 사용하지 않는다. [초지–하류 대조 발췌](island_grassland_return_actual_20261114.json)

Native 식생 경계 사례는 설원·초지·강변·고원의 경계 밖 초기 식생과 설원 동쪽 경계만 4.5m 확장한 실제 실행을 묶었다. 동일 좌표의 지면 검사와 실제 개체가 경계를 넘고 섭취한 결과를 각각 기록했다. Python R9 M1은 공용 정사각 월드 경계를 쓰므로 격자 범위 안의 독립적인 지역 경계는 현재 대응하지 않는다. 이 JSON은 권위 비교용이며 학습 준비 상태는 `false`다. [네 지역과 설원 경계 대조 발췌](island_native_food_boundary_actual_20261114.json) · [R9 위치 제한](../../../../herbivore_rl/env_v2/r9_world.py)

최신 저장 섬의 장기 사례는 설원·초지 확장 전후 세 단계, 각 두 시드의 16종별 시작 개체수와 30·60분 생존 개체수, 로그에 기록된 자연 출생·사망 원인·먹이 출처 전환을 담는다. 최신 두 시드에는 권위 시각이 있는 첫 지급, 시각 없이 기록된 지급 개체수, 사슴 Native 지역별 섭취 합계와 늑대 Native 예약량을 추가했다. 지급이 기록되지 않은 종은 사망 원인과 별도로 읽는다. 설원과 초지를 모두 반영한 맵을 이후 두뇌 비교의 로컬 기준으로 사용한다. `training_ready=false`인 권위 비교 표본이다. [세 저장 단계의 장기 비교](island_saved_stage_population_actual_20261114.json)

동일한 설원·초지 맵의 14시 40분 빌드로 60게임분을 다시 검증했다. 기존 두 실행과 초기 개체·위치·두뇌·지역 재고·군락 재고가 같았으며 시드별 60분 결과는 55·54마리였다. [최신 빌드의 16종 표본과 원본 해시](island_current_population_regression_20261114.json)

[부모 보호 수정 뒤 장기 기준](island_guard_population_regression_20261114.json)은 기존과 같은 저장 섬을 15시 44분 빌드로 실행한 결과다. 두 시드의 초기 개체 118마리와 위치·실행기·먹이 재고가 일치했고 60분에 44·50마리가 남았다. 두 실행에서 부모 차단은 관측되지 않았다. 14시 40분 표본과 함께 보존하며, 향후 모델과 비교할 때는 실제 사용한 빌드와 실행기를 기록한다.

같은 JSON의 `receipt_source_transitions`에는 16종별로 군락 변경, 사체 변경, 먹이 종류 변경을 담았다. `between_feeding_kind_receipts`는 메기 102번이 뿌리 군락과 소형어류 사체를 오가며 실제 지급을 받은 행을 담는다. 앞으로 기록을 다시 만들 때 PIE JSON과 서버 로그를 요약기에 전달해 `logged_food_receipt_transitions_by_species`를 확인한다. 시각 없는 지급은 시간 간격을 비워 두고, Native 사슴의 섭취는 전용 집계에서 읽는다. [요약기](../../../Tools/Editor/summarize_fauna_runtime.py)

[저장 섬의 지상 사냥 단계](island_hunt_food_stages_20261114.json)는 6게임분의 두 시드에서 후보가 없는 탐색, 후보가 있었던 탐색, 목표 추적 시작, 공격 준비, 접촉 실패, 포획을 집계한다. 표범은 산 먹이가 후보였던 탐색이 32·40회였지만 추적 시작 기록은 없었다. 밍크는 이 지상 탐색에서 세 먹이 항목이 모두 0이었고, 수중 섭식은 별도 기록에서 확인한다. 여우는 두 시드에서 각각 추적 시작 12회, 공격 준비 11·10회, 포획 11·9회가 있었다. 두 번째 시드의 추가 접촉 실패 1회는 거리가 62.3cm로 허용 범위 안이었고 `HuntTargetUnavailable`로 기록됐다. 집계의 단위는 각 단계의 로그 행이며 여러 탐색이 한 추적으로 이어질 수 있다. Native 늑대의 사냥은 이 지상 규칙 실행기의 탐색 계측 범위 밖이다.

```powershell
./AdaptiveEcosystem/Tools/Editor/run_jyu_island_audit.ps1 -Mode Population -PopulationSeconds 360 -Label hunt_food_stages -HuntAudit
python AdaptiveEcosystem/Tools/Editor/summarize_fauna_runtime.py AdaptiveEcosystem/Saved/FaunaAudit/Island_20000_hunt_food_stages/IslandFaunaPIE.json AdaptiveEcosystem/Saved/FaunaAudit/IslandAccessBaseline/20000_hunt_food_stages.log
```

[표범의 후보 점수 원본](island_leopard_hunt_value_20261114.json)은 같은 섬을 다시 실행해 감지 뒤의 결정을 좁혀 확인한 결과다. 새 6게임분 두 시드에서 표범은 각각 32·48회 후보를 얻었고, 후보 37·58건은 모두 건강한 성체 쥐였다. 기대 섭취 1.82가 기본 위험 비용 2보다 작아 모든 점수가 0이었다. 스태미나가 낮은 표본에서는 위험 비용이 더 컸다. 같은 로그에서 여우는 쥐와 산토끼를 양의 점수로 선택했다. 표본은 표범의 쥐 추적이 시작되지 않은 이유를 보여 준다. 다른 먹잇감이나 기존 R9 두뇌의 반응은 별도 상황에서 확인한다.

```powershell
./AdaptiveEcosystem/Tools/Editor/run_jyu_island_audit.ps1 -Mode Population -PopulationSeconds 360 -Label leopard_food_score -HuntAudit
python AdaptiveEcosystem/Tools/EcoVegetationEval/check_ground_hunt_value.py AdaptiveEcosystem/Docs/RL_Policy/Examples/island_leopard_hunt_value_20261114.json
```

같은 명령에 `--compare-rat-states`를 붙이면 각 시드의 첫 성체 쥐 후보에서 거리·성숙도·사냥 경험을 고정하고 상태만 바꿔 점수를 계산한다. 표범 에너지를 절반으로 낮춰도 쥐의 방어 저항이 0이어서 기존 위험 점수에 변화가 없었다. 쥐 체력을 50%로 낮추면 기대 섭취값이 약 2.14로 올라간다. 표범 스태미나가 약 81.8%였던 첫 시드에서는 점수 0을 유지했고, 스태미나가 100%였던 두 번째 시드에서는 약 0.074가 됐다. 첫 시드에서도 스태미나를 100%로 회복한 상태의 부상당한 쥐는 점수가 약 0.075였다. 두 표본에서 양수가 되는 스태미나 경계는 약 97.23%다. 이 값은 두 기록의 거리와 성체 쥐 설정을 사용한 점수 계산이며, 실제 Unreal 추적·포획이나 부상 처리의 실행 결과는 별도다.

Unreal 자동화 `AdaptiveEcosystem.Creature.Fauna.InjuredRatHunt`에서 평지의 성체 두 마리를 95cm 떨어뜨리고, 표범 에너지 50%·스태미나 100%로 고정했다. 쥐 체력 100%에서는 추적 대상과 예약 공격이 없었다. 체력만 50%로 바꾸면 쥐를 선택해 공격을 예약했고, 준비 중에는 피해가 없었으며 접촉 시 포획됐다. 사망 기록에 포식 원인과 표범 ID가 남았다. `ContestedContact`와 `WindupMomentum`도 함께 통과했다. 이 자동화는 평지의 두 개체 조건을 확인하며, 섬의 자연 발생 조우·장거리 추격·사체 지급은 이전 섬 실행과 별도로 읽는다. [Unreal 시험](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureCombatTests.cpp)

같은 자동화에서 권위 생존 처리와 지역 사망 장부를 거친 쥐의 사망 기록으로 사체를 생성했다. 재고는 13, 사체가 열리기 전 표범 에너지는 50이었다. 시험에서 표범을 멈춘 뒤 권위 시각 2.42초에 첫 식사 9가 지급돼 에너지는 59, 같은 사체의 잔량은 4가 됐다. 각 권위 처리 함수를 순서대로 호출한 시험이며, 혼합 섬의 전체 시계·이동 실행과 사후 경쟁 빈도는 기존 섬 검증으로 비교한다. 원본은 `Saved/Automation/InjuredRatCarcass.log`다.

세 번째 개체로 여우를 추가한 재실행에서도 초기 재고 13과 표범의 첫 식사 9가 일치했다. 사체가 열린 뒤 2.5초의 사냥 성공 개체 우선권이 있을 때, 섭취 거리 안에서 에너지 50인 여우의 선택과 지급은 없었다. 우선권 종료 뒤 시험에서 표범이 물러난 상태와 여우의 원래 위치를 재현하자, 여우는 같은 사체를 선택해 권위 4.87초에 남은 4를 먹었다. 5.87초에 재고가 제거됐고 추가 지급은 0이었다. 원본은 `Saved/Automation/InjuredRatShare.log`이며 같은 실행에서 사냥 자동화 3건을 통과했다.

최종 섬의 자연 실행 60게임분 두 시드에서는 여러 종이 먹은 사체 8·7구를 확인했다. 첫 번째 시드의 물소 33번 재고 120에서 까마귀 10.5, 멧돼지 64, 늑대 40을 먹고 5.5가 남은 채 만료됐다. 두 번째 시드의 물소 130번도 세 종이 먹었고 잔량 0으로 폐기됐다. `summarize_fauna_runtime.py`에 `--audit-carcasses`를 주면 생성량 배분, 로그 순서별 개별 차감, 폐기 잔량을 검증한다. 두 시드의 생성·폐기 285구와 지급 662건은 로그 출력 정밀도에서 일치했다. Native 늑대의 지급 시각이 없는 행은 로그 순서로만 비교한다. 같은 사체를 이용했다는 근거이며 서로 위협하거나 밀어낸 행동은 별도 기록에서 확인한다. [사체별 집계와 세 종의 지급 순서](island_guard_population_regression_20261114.json)

### 향후 두뇌 수령 시 섬에서 비교하는 절차

1. 먼저 같은 종·몸 해시·관측 순서와 정규화·행동과 마스크가 일치하는지 확인한다. Python과 C++에서 같은 입력의 점수·마스크·동작을 대조한다. 기존 R9 데모의 로드는 JYU 섬의 종별 실행기 연결과 별도로 확인한다. [R9 클라우드 안내](../R9_CLOUD_TRAINING.md) · [별도 Unreal R9 로더](../../../Source/AdaptiveEcosystem/AI/Policy/R9/EcoR9DemoLiveSource.cpp)
2. 맵과 설원·초지 외부 액터의 해시, 같은 시드의 기준 설정을 고정한다. `-EcoV3Seed=20000`·`20017`, `-EcoIslandPopulationSeconds=3600`, `-benchmark -fps=30`, `-EcoV3AutoAdapt=0`을 사용한 원본은 위 JSON에 연결돼 있다. [요약기](../../../Tools/Editor/summarize_fauna_runtime.py)의 `--compare-baseline <기준 PIE JSON>`에 교체한 종마다 `--expect-policy-change Fox`처럼 종 ID를 붙인다. 지정한 종에서 두뇌 또는 실행기 표기 변화가 확인돼야 하며, 다른 종의 두뇌, 시작 ID·종·체격·위치·체력·에너지·경로·먹이 재고·시계 차이는 실패로 보고한다. 이 비교는 표기상 변화 여부를 확인한다. 목표 가중치 해시·정책 계약·교체 대상 개체 전체는 별도로 대조한다. 첫 표본은 권위 시각 1초이므로 이미 움직이거나 대사한 후보는 원시 시작 조건과 직접 대조한다. 군락 재생·좌표·접근점은 동일 맵과 외부 액터를 확인하고 별도 짧은 감사의 `patch_budget`도 대조한다.
3. 권위 경로의 합격 조건은 도달한 개체의 실제 지급과 원천 재고 차감 일치, 접근할 수 없는 먹이터의 지급 0, 요청·실행·결과 추적 가능, 저장 뒤 동일 세계에서 다음 거래 재개, 클라이언트의 권위 개체 0이다. 고수위에는 밍크의 별도 마른 둑 상륙과 잉어 치어의 부화·첫 지급을, 먹이 부족에는 대체 먹이터에 실제로 도달했는지 확인한다. 포식 압력에는 접근·포기·포획 결과와 사체의 지급·만료 수지를 확인한다. 기존 수변·토양·사체 표본과 같은 조건으로 먼저 재현한다.
4. 30·60분 생존·첫 섭식까지 걸린 시간·먹이 출처 전환·출생과 사망 원인을 종별·시드별로 검토한다. 허기·부상·주변 동족·경사·가림을 한 번에 하나씩 바꿔 추격·이탈·부상·포획 빈도를 비교한다. 늑대가 표범을 공격하는 일처럼 드문 행동은 실제 조건과 결과를 기록하고, 종 조합별 고정 빈도나 전 종 생존율을 합격 조건으로 두지 않는다. 생존 차이가 생기면 접근 실패, 실제 재고 부족, 탐색 선택, 대사와 포식 기록부터 대조한다.

새 `Population` 보고서는 `initial_patch_inputs`에 활성 단계, 재생률, 식생·수위 반응 계수, 먹이터 중심, 추가 접근점, 입수·상륙·마른 둑 좌표를 기록한다. `--expect-policy-change`를 쓸 때는 기준과 후보 모두 새 형식으로 기록해야 한다. 기존 보고서는 일반 기준 비교에 계속 사용할 수 있다. 맵 외부 액터의 해시와 실제 런타임 정의는 모두 확인한다.

최신 빌드의 `wet_travel_base60`은 [최종 저장 섬 기록](island_saved_refuge_regression_20261114.json)의 `latest_runtime_regression`에 있다. 이전 실행과 시작 개체·실행기·패치 입력이 같았고, 60게임분 후 생존은 시드별 39·27마리였다. 기본 맵의 장기·서버 회귀는 PIE에서 추가한 Drift 접근점을 적용하지 않은 조건이다.

현재 비교 기준은 [강변 대피처가 포함된 최종 저장 섬](island_saved_refuge_regression_20261114.json)이다. `rat_final60`과 `rat_final_repeat60`은 같은 맵, DLL, 시드, 초기 개체와 군락 24곳에서 실행했다. 60분 개체 수는 시드 20000에서 29·46마리, 20017에서 30·51마리였다. 같은 빌드의 개체군 편차를 먼저 기록하고 선택·실행·지급·포획의 사건을 함께 비교한다. 팀 레벨의 면적·우회로·지형 이식은 [레벨 실측](../../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#섬의-물리-구조와-후속-레벨-작업)을 참고한다.

같은 자료의 `feeding_cohorts`는 네 실행에서 16종의 시작 개체와 자연 출생 개체를 나눠, 시각이 있는 지급·시각이 없는 지급·표본 이력만 있는 지급·개체별 근거가 없는 ID를 담는다. 잉어 치어는 네 실행 모두 2마리씩 태어나 두 마리 모두 지급이 기록됐다. 시작 시점에 있던 소형어류는 네 실행 모두 7마리 중 4마리에 지급 기록이 있었다. 표범은 시드 20017의 반복 실행에서만 창시 개체의 지급이 기록됐다.

사슴의 Native 식생 섭취는 개체별 지급 로그와 별도로 관측된다. 같은 저장 섬의 300게임초 두 시드에서 Native의 직전 스텝 섭취량을 11번 읽었다. 각각 창시 사슴 41/48·42/48마리와 출생 사슴 3/4·2/3마리에서 양의 섭취를 확인했다. `native_deer_intake_samples`에 개체 ID·표본 시각·섭취량을 보존했다. 최초로 관측된 양의 표본이며 생애 첫 식사 시각이나 전체 섭취량은 이 표본으로 판정할 수 없다.

[두뇌 교체 비교용 새 60게임분 기준](island_patch_input_population_baseline_20261114.json)에 두 시드의 원본 보고서·로그 경로와 해시, 공통 군락 설정, 생활·사망·자원 장부를 기록했다. 원본은 `patch_baseline60`이라는 이름이다. `check_island_population_receipts.py`에도 `--expect-policy-change`를 사용해 시작 조건과 30·60분 개체수, 지역 장부를 함께 확인할 수 있다.

[밍크 출구 변경 뒤 60게임분 재검증](island_mink_exit_population_regression_20261114.json)은 동일 맵과 초기 입력을 원래 기준과 대조한다. 최신 빌드의 30분은 29·28마리, 60분은 39·44마리였다. 첫 개체수 차이는 밍크 표본의 이동 차이보다 먼저 사슴에서 관측됐으며, 두 실행만으로 생존 차이의 원인을 단정할 수 없다. 새 두뇌를 같은 빌드에서 비교할 때는 새 실행 원본을 사용한다.

같은 DLL의 180게임초 반복에서는 시드 20000의 초지 포획 차이는 재현됐고, 시드 20017의 고원 사슴 88번 포획은 재현되지 않았다. 각 실행의 `early_repeat`에 사망 시각과 포식자 ID를 기록했다. 두뇌 전후 차이를 해석할 때 같은 빌드의 반복 실행에서도 발생할 수 있는 포획 시점 차이를 함께 본다.

두뇌 교체 비교에서도 `check_island_population_receipts.py`의 `sample_comparison`을 사용하면 시작·중간·종료 집계에 더해 30게임초 간격 전체의 첫 개체수 차이와 종별 최대 차이를 확인할 수 있다. 같은 관측 예정 시각을 짝짓고, 실제 권위 시각이 어긋날 수 있으므로 첫 차이에는 양쪽 시각을 함께 기록한다. 두뇌를 바꾸기 전에도 같은 빌드와 시드로 반복해 개체군의 자연 실행 편차를 기록한다.

`same_build_repeat60`에 두 시드의 추가 반복을 보존했다. 각각 60게임분에 44·39마리가 남아 같은 DLL의 첫 결과 39·44마리와 달랐다. 전후가 각각 한 번뿐이면 생존 개체수 차이의 원인을 판정하기 어렵다. 두뇌의 영향을 비교할 때 동일한 시드 세트에서 기준·후보를 모두 반복하고 접근·섭취·포획·출생과 사망 사건을 함께 확인한다.

비교 명령에 `--baseline-log`로 기준 실행의 권위 로그를 추가하면 `species_outcomes`에서 양쪽의 16종별 시작·종료 개체수, 출생, 사망 원인, 첫 시각이 있는 지급, 시각이 없는 지급을 받은 개체수와 먹이 출처 전환을 읽을 수 있다. 최신 네 실행의 종별 장부에서 `시작 + 출생 − 사망 = 종료`가 모두 맞았다. 시드 20000의 사슴은 32→38마리였고, 출생이 4건 늘고 피식이 2건 줄었다. 시드 20017은 38→33마리였고, 출생은 같았으며 피식이 6건 늘고 기아가 1건 줄었다. 쥐는 네 실행 모두 6마리로 시작해 3마리가 태어났고 9마리가 피식됐다. 지급 기록이 없는 종의 섭식 여부는 표만으로 판정할 수 없다. Native 사슴과 늑대의 섭식은 별도 집계로 표시한다.

같은 최신 DLL의 새 프로세스 저장·복원은 조회 가능 개체 117·111개, 22개 군락 재고, 수변 접근 설정 9곳과 지역 환경·토양 수분이 일치했다. 체크포인트 포맷 16, 길이, CRC와 Native 지역별 재고도 대조했고, 복원 뒤 잉어 136·135번이 부화했다. 해당 JSON의 각 실행 `checkpoint_validation`에 보존했다.

같은 DLL의 `dedicated_server_validation`은 저장 맵 시드 20017에서 전용 서버와 시차 접속 클라이언트 두 대를 확인했다. 근거리 표본 29·30개, 식생 필드 각 4곳, 클라이언트 권위 개체 0이었다. 늦게 접속한 클라이언트가 출생 개체 122·124번을 받았고 프로젝트 검증 허용 범위에서 체격 불일치는 없었다.

같은 JSON의 `checkpoint_validation`에 두 시드의 새 프로세스 복원 결과를 추가했다. 저장 당시 DLL과 체크포인트 포맷·길이·CRC, 권위 시각, 네 Native 지역 먹이, 군락 재고 22곳과 수변 좌표 9곳을 대조했다. 잉어 136·134번이 복원 뒤 부화했다. [체크포인트 대조 도구](../../../Tools/Editor/check_island_checkpoint_receipts.py)

`dedicated_server_validation`은 같은 DLL의 전용 서버 93초 관찰과 시차 접속 클라이언트 두 대의 별도 결과다. 근거리 표본 31·39개, 식생 필드 각 4곳, 클라이언트 권위 개체 0을 확인했다. 나중에 접속한 클라이언트에 출생 개체 122·124번과 검증 범위의 체격이 전달됐다. [서버·클라이언트 재실행 도구](../../../Tools/Editor/test_vegetation_network.ps1)

기존 R9의 비교 기준은 [식생 접근 확인 도구](../../../Tools/Editor/check_r9_food_access_reference.py)에서 실행한다. 개발 시드 44190·44191의 평지에서 사슴을 `(29.8, 31)`에 두고 `X=30` 너머 셀에 풀 0.5를 둔다. 두 시드 모두 걷지 않고 섭식하면 지급 0, 기존 걷기 요청으로 해당 셀에 들어가 섭식하면 지급 0.024와 재고 0.476이었다. 이 실행은 현재 평면 세계의 이동과 거래를 입증한다. Unreal의 지역 경계 및 실제 지형을 대응하려면 별도 세계 계약이 필요하다.

## 기존 soil/life 사례 재생성

먼저 실제 프로젝트 폴더 `AdaptiveEcosystem/`에서, engine/build가 모두 종료된 상태로 QA를 실행한다. C++를 바꿨다면 먼저 루트 규칙대로 직접 UBT 검증을 한다.

```powershell
./Tools/Editor/run_ecosystem_validation.ps1 -Check ambush
./Tools/Editor/run_ecosystem_life.ps1 -Mode save -Name FinalSave -Slot LifeRestart -Seed 23 -Duration 115 -SaveAt 95
```

이 명령은 해당 이름의 Saved 결과를 새로 만든다. 이전 원시 근거가 필요하면 먼저 별도로 보존한다. 기존 수동 맵을 setup 스크립트로 재생성하지 않는다. 다음은 일반 Python으로 실행하는 **읽기/문서 추출 도구**다. Unreal이나 학습을 시작하지 않는다.

```powershell
# 같은 프로젝트 폴더에서
python ./Tools/Editor/export_ecosystem_documentation_examples.py --source-implementation-commit d095948 --capture-date 2026-10-23 --release-date 2026-10-24
```

실제 FINISHED 보고서·snapshot이 없거나 부모/자식·Unknown 근거가 없으면 도구가 거절한다. 새 실행의 ID/값은 달라질 수 있으므로 새 기준 SHA·날짜·선택 결과와 본 README의 사례 설명을 함께 갱신한다. provenance 인자는 필수이며 commit 존재/날짜 형식을 검사하지만, 입력 snapshot이 정말 그 빌드에서 만들어졌는지는 실행 기록으로 확인해야 한다. 현재 예시의 `d095948`/2026-10-23을 다른 실행에 그대로 재사용하지 않는다.

정확한 `.eco` 복원이나 per-step trajectory/모델 Golden이 필요하면 [학습 가이드](../ECOSYSTEM_RL_AGENT_GUIDE_20261024.md)와 [실제 codec 계약](../../Architecture/ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md)을 따른다. 원본 snapshot은 모델 학습 완료 증거나 배포 가능한 저장 파일이 아니다.
