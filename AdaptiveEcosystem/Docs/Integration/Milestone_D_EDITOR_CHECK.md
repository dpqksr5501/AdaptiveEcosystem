# D — 생존·먹이·사망·이주 수동 확인

자동화 테스트 생략. [진행 기록](M4_IMPLEMENTATION_PROGRESS.md).

- 맵: 평면 `L_EcoCreatureIntegration`부터. Coordinator → Vitals의 기존 Energy Drain=1, Energy Per Food=5, Grace=0, Damage=5. Enable Waves=false, Region Food Regeneration Rate=0.
- `eco.Integration.Dump details` → `Alive = Births - Deaths`. LastFeed/Granted/TotalFood와 지역/종별 summary를 GameState에서 확인한다.
- GameState → Ecology Summary → Species: 각 지역/종의 `Population = Births - Deaths + MigrationIn - MigrationOut`. 누적 사건 수는 같은 WorldEpoch의 완료 step 기준이다. Population=0인 멸종 row도 Death 기록을 유지해야 한다.
- 서버 `Debug.Starvation.Forest_A`, 이후 `Debug.FoodSupply Forest_A 100`: 고갈→이주/기아, 실제 공급→섭식 회복을 각각 확인한다.
- `eco.M4.SetVitals <ID> 1 0` → 유예/기아 피해, `0 0` → ExternalDamage. 기아·외부 피해가 PredationHistory를 올리지 않아야 한다.
- Predator Survival=true인 별도 테스트 사본: Predator Energy Drain=1, Capture Gain=25. 포식 성공 때만 늑대 Energy 회복, 먹잇감이 없으면 기아 사망. 기본 늑대 설정과 구분한다.
- 순수 과밀 사본: 충분한 Food, Region Ecological Comfort Population을 초기 초식 수보다 낮게 설정. Population Pressure=true. 지속 문턱과 지역당 출발 상한을 확인한다.
- Shelter 점유 중 사망/이주/위협 clear: 예약 release 로그와 슬롯 재사용 확인.

통과 기준: Food 차감=Granted 합계, Energy는 실제 지급만 반영, 고유 Death 한 번, 동일 ID의 실제 지역 도착, 세계 인구에서 이주가 상쇄. 전멸 시 재생/공급 없는 조건인지 기록한다.
