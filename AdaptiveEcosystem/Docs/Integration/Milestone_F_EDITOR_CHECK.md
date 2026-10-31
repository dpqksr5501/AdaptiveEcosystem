# F — 예산·성능·병렬·LOD 수동 확인

자동화 테스트 생략. [진행 기록](M4_IMPLEMENTATION_PROGRESS.md).

- 먼저 19개체·Client 1/2에서 통과한 뒤 평면 fixture를 64→128→256→512로 확대한다. 실제 맵의 authored spawn 배열은 인원 수만큼 안전한 위치를 준비해야 한다.
- Project Settings → Adaptive Ecosystem → Connection Budget: 예시 Relevant=128, Actor=32, Adds/Update=8. 기본값과 비교 사본의 값을 따로 기록한다.
- 19개체에서 상한을 바로 확인하려면 Relevant=8/Actor=4/Adds=2로 별도 실행한다. `eco.M4.Dump`의 BudgetDeferredAdds와 각 Bubble의 Entries를 확인한다. 측정 중 상한을 바꾸지 말고 PIE를 재시작한다.
- `eco.Integration.Dump`, `eco.M4.Dump details`: Client/Host Actor 상한, pool, Bubble entry 상한, 접속/대량 진입 생성 분산, 이탈/재진입 초기화 확인.
- `eco.Policy.Parallel 0`과 `1`을 같은 조건에서 비교. 이번 Processor 실행의 모든 chunk에서 due agent를 합쳐 64 이상일 때만 worker를 사용한다. 입력을 수치 batch로 snapshot한 뒤 계산 완료를 기다리고 새 fragment view로 commit한다. UObject·World trace·자원 commit은 Game Thread에 남는다.
- `eco.Integration.Dump`의 ParallelDecisions는 실제 ParallelFor 경로에서 계산한 결정 수다. 설정 1만으로 병렬 dispatch/성능 향상을 선언하지 않는다. 현 시점에 살아 있거나 dead-retention 중인 Owned 개체의 합계라 사망 정리 후 누적값이 내려갈 수 있다.
- Coordinator → Simulation LOD=true, Far Distance=20000cm, Far Policy Multiplier=4를 별도 실행한다. 원거리 무위협 Resident만 정책 주기가 줄고, 위협/예약/이주 중에는 full-rate로 돌아와야 한다.
- Unreal Insights CPU capture에서 `EcoCreature_*`, `EcoPolicy_*`, `EcoSenses_PredatorScan`, `EcoReplication_Connection` 구간을 확인한다. Network Insights는 별도 packet trace를 캡처한다.
- 상세 debug draw/log는 측정에서 끈다. `eco.Integration.LogDetails 0`, `eco.M4.TraceSamples 0`, Project Settings의 Print Resource Changes=false를 설정하고 PIE를 재시작한다. 워밍업 5분→캡처 15분→수명 반복 30분을 초기 비교안으로 사용한다.

기록: SHA·기기·맵·정책/EMA/LOD 모드·개체/Client 수, p50/p95/p99, hitch, 메모리, packet/wire bytes, debt, active/pool/queued 생성. 512 초과 지원·실측 성능 향상·장기 평형을 이 문서만으로 선언하지 않는다.
