# M4 에디터 확인 — A~F 빠른 시작

UE 5.8. 자동화 테스트를 생략한다. [실제 실행 기록](M4_IMPLEMENTATION_PROGRESS.md)과 [파일별 계약](M4_RUNTIME_INTEGRATION_CONTRACT.md)을 먼저 구분한다.

**사용자가 Integration Test를 복사해 만드는 새 레벨은 [수동 배치·팀 연결 가이드](M4_NEW_LEVEL_MANUAL_SETUP.md)를 기준으로 설정한다.** 아래 기존 맵 이름은 이미 수행한 기준선 시나리오다. 새 레벨은 사용자가 만든 실제 경로로 실행하고 새 결과를 별도로 기록한다.

## 공통 설정

1. Live Coding과 Editor를 종료하고 `Tools/Integration/build_integration_milestone.ps1 -Milestone Final`로 빌드를 완료한 뒤 `.uproject`를 연다. 실행 중인 다른 빌드에 겹쳐 실행하지 않는다.
2. 동물은 `L_EcoCreatureIntegration`(평면·2지역) → `LV_Ecosystem_IntegrationTest`(실맵·3지역) 순서로 확인한다. 기존 EntityConfig/GameMode/Spawner를 유지하고 같은 맵에 M3 Box Bootstrap을 추가하지 않는다.
3. 최초 비교는 Enable Waves=false, Predator Survival=false, Simulation LOD=false, Region Food Regeneration Rate=0, Rainfall Affects Regeneration=false. `eco.UseLearnedPolicy 1`, `eco.Policy.PredationSource 0`, `eco.Policy.Parallel 0`.
4. Standalone으로 먼저 실행한다. 네트워크 확인은 Play 설정의 Players=2, Play As Client, Dedicated Server로 바꾼다. 마지막에는 별도 서버/Client로 동일 서버 재접속을 확인한다.
5. Output Log/콘솔의 `eco.Integration.Dump details`로 개체·자원·수신 값을 읽는다. 지속 로그가 필요할 때만 `eco.Integration.LogDetails 1`을 켠다. 값/배치 변경 뒤에는 PIE를 다시 시작한다.

## 마일스톤별 최소 확인

| 단계 | 에디터/콘솔 설정 | 확인할 결과 | 상세 |
| --- | --- | --- | --- |
| A | Box `Jang_lv`, 동물 두 맵; Standalone | 빌드·Ready, 이동, Shelter 도착/점유, 같은 ID의 지역 도착 | [A](Milestone_A_EDITOR_CHECK.md) |
| B | Dedicated + Client; 서버 `eco.M4.TraceSamples 1` | velocity/flag-only 수신, 작은 teleport reset, 거리 이탈/재진입, 재접속, 권위 Owned 0 | [B](Milestone_B_EDITOR_CHECK.md) |
| C | `t.MaxFPS 20/30/60`, 정책 LOD/worker off | 약 7.5회/개체·초, dead 정책/이동 제외, heading, 피식 분모, hitch debt | [C](Milestone_C_EDITOR_CHECK.md) |
| D | `Debug.Starvation <RegionId>`, `Debug.FoodSupply <RegionId> 100` | 실제 먹이 지급·단일 사망·예약 해제·이주, 지역/종별 Birth-Death+In-Out=Population | [D](Milestone_D_EDITOR_CHECK.md) |
| E | Region Rate=2, rainfall response=true, Dry=0.5/Wet=1.5; Adapter BP 배치 | 강수 0/1에서 1/3 Food/s, 다음 관측/소비, Client 하늘/날씨 요약 | [E](Milestone_E_EDITOR_CHECK.md) |
| F | Project Settings → Adaptive Ecosystem → Connection Budget; 별도 사본의 Actor=32/Add=8/Relevant=128 | 여러 종 합산 상한, pool reset, 대량 진입, 계측; worker/LOD는 별도 opt-in 비교 | [F](Milestone_F_EDITOR_CHECK.md) |

강수량/clock Adapter의 Blueprint 이벤트는 기존 하늘·날씨 에셋 노드에 직접 연결해야 한다. 새 에셋이나 기존 맵 배치를 자동 수정하지 않았다. 서버 권위 `ApplyWeather`와 Client의 `OnEnvironmentUpdated`/`OnClockUpdated` 표시를 구분한다.

## 판정

현재 직접 UBT와 기록된 CLI/NullRHI 실행은 통과했다. 자동화/Golden Vector, GUI 화면·애니메이션·오디오, 작은 teleport·손실/지연 주입, 다중 동시 Client, cook, 규모/장기 성능 판정은 해당 문서의 수동 확인 후 기록한다. CLI 19개체 실행을 512개체 지원이나 상용 완료로 읽지 않는다.
