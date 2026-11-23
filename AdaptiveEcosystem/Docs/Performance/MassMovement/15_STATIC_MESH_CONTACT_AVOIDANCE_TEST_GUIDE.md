# Static Mesh 접촉 회피 사용자 검증

[교체 명세](14_STATIC_MESH_CONTACT_AVOIDANCE_SPEC_20261118.md)의 A와 B를 같은 에디터 빌드에서 실행한다. A는 기존 사슴 원판과 지형 이동, B는 권위 Native v3 사슴의 실제 몸체 스윕과 접선 한 번이다. 원판을 불러온 지역과 충돌 없는 합성 무대 나무를 쓰는 지역은 기존 이동 계약을 사용한다.

## Forest_A 기준선과 비교

1. UE 5.8에서 `/Game/JWJ/1102_Integration_JWJ`를 연다. **Play → New Editor Window (PIE)**, **Net Mode → Play Standalone**, **Number of Players = 1**, **Run Under One Process**를 선택한다.
2. **Play 전에** 에디터 **Output Log** 콘솔에 아래 명령을 한 줄씩 입력한다. 30마리는 지역당 요청값이다. 보고서의 실제 시작 개체 수를 확인한다. A와 B의 시작 설정, 시작 위치와 카메라, Foliage 충돌 메시와 인스턴스, 실행 시간을 맞춘다.

   ```text
   eco.IntegratedPolicyVersion 3
   eco.IntegratedV3.Seed 20000
   eco.IntegratedV3.DeerPerRegion 30
   eco.IntegratedV3.Obstacles 1
   eco.IntegratedV3.ObstacleDetour 1
   eco.IntegratedV3.StageTrees 0
   eco.IntegratedV3.StaticMeshContact 0
   eco.V3Debug.Obstacles 0
   t.MaxFPS 60
   ```

3. Play 후 월드 파티션 셀과 사슴이 준비되면 `Forest_A`에서 게임 콘솔에 `eco.MoveTest Run StaticMeshAvoidance 600`을 입력한다. `eco.MoveTest Status`로 진행을 확인하고, 중간 기록이 필요하면 `eco.MoveTest Stop`을 사용한다. Output Log의 `RunId`와 `Path`를 적는다.
4. PIE를 종료한 뒤 `eco.IntegratedV3.StaticMeshContact 1`로 바꾼다. 같은 조건으로 다시 Play하고 같은 명령을 실행한다. A와 B를 각각 반복해 프레임 비용의 실행 간 편차를 구한다.
5. `Saved/Profiling/EcoMovement/<RunId>/Summary.json`에서 `mode`, `setup.regions`, `loaded_blocking_instanced_mesh_assets`를 확인한다. B의 대상 지역은 `contact=true`여야 한다. `SM_pine02_ForestA`가 해당 장면의 줄기라면 맵에 배치된 컴포넌트가 그 메시를 참조하며 **Collision Enabled**에서 Query가 활성이고 **WorldStatic**을 Block하는지 확인한다. 두 실행에서 `ObstacleImport`는 빈 상태로 둔다.

## 선택 개체와 물리 검증

성능 기록과 별도 PIE에서 B를 켠다. `eco.V3Debug.Obstacles 1`과 `eco.MoveTest Observe <StableAgentId> 120`을 실행한다. 또는 `eco.Cam.Deer <StableAgentId>`와 `eco.Cam.MassDebug 1`로 권위 월드에서 사슴을 따라간다. 노랑은 예정 스윕, 초록은 검증된 직진, 청록은 접선과 허용 종점, 빨강은 실제 쿼리의 접점과 수평 법선이다. 접점 라벨은 차단 컴포넌트와 인스턴스 번호를 표시한다. 갈색 원은 스캐너 자료이며, B에서는 사슴 몸 반경을 더한 외곽 원을 숨긴다.

폭을 재현할 때는 소유한 테스트 맵에서 단순 충돌 표면 사이를 64cm와 58cm로 맞춘다. 지면을 평평하게 두고 `Observe` 보고서의 `body_radius_cm`가 30인 사슴의 예정 이동이 각 틈을 직선으로 향하는 샘플을 확보한다. 측정은 렌더 메시 표면과 독립적인 실제 충돌 표면을 기준으로 한다.

| 장면 | 판정 |
| --- | --- |
| 64cm 및 58cm 틈 | 64cm에서 직진 통과, 58cm에서 관통 0회. 예정 이동이 통로를 향하지 않은 구간은 미관측으로 기록한다. |
| 얇은 줄기, 회전한 바위, ISM/HISM | 형상을 가로지르지 않고 이동한다. 실제로 접촉한 행만 `static_mesh_hit`이 1이다. 인스턴스 번호는 그 시점의 진단에만 쓴다. |
| 시작 겹침, 코너의 두 번째 장애물, 수심과 경사 | 겹침으로 시작하면 제자리 또는 이미 검증된 종점에 머문다. 접선이 다시 막히면 검증된 구간까지만 이동한다. `static_straight_block`과 `static_final_block`으로 첫 판정과 최종 판정을 확인한다. |
| 빈 초원과 밀집 숲의 동시 도주·이주 | `Frames.csv`의 이동 의도·진행·정체·스윕 수를 함께 대조한다. 이주가 작성된 월드에서 필요하면 `eco.HerdMigration 1`과 개발용 `eco.HerdMigration.Test.Drought Forest_A`를 사용한다. A/B에서 가뭄 투입 시각을 맞추고 실제 도착을 기록한다. |
| 낮은 FPS와 프레임당 여러 Native 스텝 | 성능용 PIE에서 `t.MaxFPS 5`로 낮춰 `native_steps > 1` 행을 확보한다. 기본값에서 프레임별 `tangents <= 24`, `tangent_sweeps <= 64`인지 본다. `body_sweeps`에는 필수 직진 스윕도 포함된다. |
| 전용 서버와 클라이언트 2개 | **Play As Client**, **Number of Players = 2**로 실행한다. 같은 프로세스 PIE에서는 위의 시작 CVar를 공유한다. **Editor Preferences → Level Editor → Play**의 **Network Emulation**에서 같은 지연·손실 설정을 A/B에 적용한다. 두 클라이언트를 서로 다른 거리에서 움직여 셀 재진입을 비교한다. 권위 월드에서 `Run StaticMeshAvoidance`, 클라이언트 게임 콘솔에서 `eco.MoveTest Observe <StableAgentId> 120`을 사용한다. 전체 프레임 비용과 연결별 전송은 Unreal Insights 및 네트워크 추적으로 확인한다. |

`Frames.csv`는 실제 이동 어댑터와 A의 이주 사전 검사에서 원판, 몸체 스윕, 지면, 제외 볼륨, 접선 비용을 기록한다. 접선 시간에는 접선 내부의 스윕과 지면 시간도 들어 있으므로 합산하지 않는다. `world_tick_to_post_actor_us`는 해당 World 델리게이트 사이의 시간이다. `native_step_sum_per_active_frame_us`는 Native Step을 실행한 프레임에 대한 지역별 실행 시간 합이다. `Recorded`는 표본 수집 결과다. 시각적 통행·서버 p99·도착률·네트워크 acceptance는 각 장면으로 판정한다. 빈 구간 스윕 생략 C는 B 비용을 측정한 뒤 결정한다.

첫 B 설정은 근거리 25m, 중거리 88m다. 근거리는 접촉마다, 중거리는 사슴별로 분산해 최대 4스텝마다 접선을 시도한다. 더 멀거나 서버 관찰자가 없으면 8스텝 동안 정체된 뒤부터 재시도한다. `NearCm`, `MiddleCm`, `Candidates`, `Sweeps`는 `eco.IntegratedV3.StaticMeshContact.` 아래에 있다. 설정을 비교하려면 각 실행 시작 전에 고정한다.

## Unreal Automation 회귀 실행

1. PIE를 종료하고 `eco.IntegratedV3.StaticMeshContact 0`으로 설정한다. **Tools → Session Frontend → Automation**을 열고 현재 로컬 에디터 세션을 선택한다.
2. 아래 이름으로 찾은 뒤 **Start Tests**를 누른다. 목록이 비어 있으면 **Refresh Tests**를 누른다.

   - `AdaptiveEcosystem.Policy.V3.Obstacle`
   - `AdaptiveEcosystem.Policy.V3.Integrated.BlockedMoveHooks`
   - `AdaptiveEcosystem.Policy.V3.Integrated.TerrainBlocking`
   - `AdaptiveEcosystem.Policy.V3.Movement.Avoidance`
   - `AdaptiveEcosystem.Policy.V3.HerdMigration.NativeJourneyAndIdentity`

3. 이 항목들은 기존 원판·Native 이동 훅·회피·이주 회귀를 확인한다. B의 64/58cm, 실제 Foliage 인스턴스, 전용 서버 및 스트리밍 판정은 위 PIE 장면에서 기록한다.
