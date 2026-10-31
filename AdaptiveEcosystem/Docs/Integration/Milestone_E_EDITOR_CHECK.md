# E — World 입력·자원 폐루프 수동 확인

자동화 테스트 생략. [진행 기록](M4_IMPLEMENTATION_PROGRESS.md).

새 레벨의 기존 Sky/Weather BP 인계는 [수동 설정 가이드 §6](M4_NEW_LEVEL_MANUAL_SETUP.md#6-기존-날씨하늘-blueprint-연결)를 따른다. `ApplyRainfall`은 각 지역의 온도/습도를 유지한다. Native Adapter는 Actor HasAuthority 대신 World NetMode로 권위를 구분해 Client의 완료 DTO 표시 이벤트를 실행한다.

1. `LV_Ecosystem_IntegrationTest` 사본에 `EcoRegionEnvironmentAdapter` 하나를 배치한다. RegionIds는 Forest 등 실제 ID 또는 빈 배열(전체).
2. Apply Authored Weather=true, Authored Weather에서 Rainfall/Weather/Temperature/Humidity 설정. 기존 날씨 Blueprint는 `ApplyWeather`를 서버에서 호출하도록 연결할 수 있다.
3. 하늘 Blueprint를 Adapter 파생 BP의 `OnClockUpdated` 이벤트에 연결한다. PhaseProgress로 해당 낮/밤 구간의 태양/밝기를 갱신한다. `OnEnvironmentUpdated`로 지역 날씨를 표시한다. Client는 GameState의 완료 요약을 읽는다. 기존 하늘 BP 에셋의 노드는 직접 연결해야 한다.
4. 기본 Region Food Regeneration Rate=0, Rainfall Affects Regeneration=false를 유지해 고갈 폐루프를 확인한다. 반복 시연용 사본에서만 Rate=2, Rainfall Affects=true, Dry=0.5, Wet=1.5를 설정한다. Rainfall=0이면 1 Food/s, 1이면 3 Food/s다. 실제 공급은 FoodCapacity까지의 남은 양으로 제한된다.
5. 콘솔만으로 비교하려면 서버에서 `eco.Environment.Regeneration Forest 2 1 0.5 1.5`, `eco.Environment.Rain Forest 0` 또는 `1`. Adapter가 Apply Authored Weather=true면 다음 tick에 값을 덮어쓰므로 콘솔 비교 중에는 꺼둔다. 이 명령은 PIE 실행에만 적용되며 맵을 저장하지 않는다.
6. `Debug.Starvation Forest`, `Debug.FoodSupply Forest 100`, 위협 접근/해제 후 `eco.Integration.Dump details`로 Food·PredationHistory·개체 ObsFood/ObsPredation·Raw/SocialForage·지급량·인구를 같은 실행에서 추적한다. 이미 받은 먹이 또는 포식 receipt를 날씨가 다시 지급하지 않아야 한다.

통과 기준: World 강수량 → Ecology 재생 실제량 → Food 관측 → 기존 V1 정책/Social → 소비/인구 → 다음 관측 연결. 자원 step당 재생/위험 감쇠 한 번, 재생 실제량은 공급 원장에 포함된다. 강수량 자체는 V1의 신규 관측이 아니다. 위 선형 성장 계수는 명시적인 시연 설정이며 재학습·식물 개체 성장 모델을 의미하지 않는다.
