# C — V1 정책·시간 보정 수동 확인

자동화 테스트 생략. [진행 기록](M4_IMPLEMENTATION_PROGRESS.md).

1. `L_EcoCreatureIntegration` Standalone, Enable Waves=false, Simulation LOD=false, `eco.Policy.Parallel 0`.
2. `eco.UseLearnedPolicy 0/1`을 별도 실행으로 비교. 기본 `eco.Policy.PredationSource 0` 유지. 전역 EMA 비교는 `1`로 명시하고 기록한다.
3. 콘솔 `t.MaxFPS 20`, `30`, `60`으로 각각 실행한다. `eco.Integration.Dump details`의 Decisions/AliveSeconds와 PolicyDebt를 비교한다. 기본 주기는 8/60초(7.5회/개체·초)다. 초기 phase와 짧은 종료 구간은 한 번의 차이를 허용하며, LOD는 끄고 생존한 동일 ID를 비교한다. 긴 frame 직후 한 프레임당 한 번만 추론하고 남은 시간은 debt로 보존한다.
4. `eco.M4.SetVitals <ID> 0 0`으로 죽인다. 다음 생존 step 이후 이동·관측·이웃 집계에서 제외되고 한 번만 Death 처리되는지 확인한다.
5. `eco.Creature.DrawFacing 1` → 실제 속도와 모델 전방이 일치. 정지 후 출발/180도 반전 확인.

통과 기준: 같은 단위시간의 정책 주기, hitch 뒤 debt가 관측되고 해소됨, dead 이동 없음, 같은 cell의 전체 살아 있는 prey가 EMA 분모로 계산됨. 포획의 frame 의존성과 새 정책의 행동 품질은 별도 항목이다.
