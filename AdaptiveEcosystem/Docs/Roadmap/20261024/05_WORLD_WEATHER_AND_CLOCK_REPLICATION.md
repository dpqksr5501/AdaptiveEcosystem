# T05. 공통 날씨·시계·Client 환경 동기화

상태: 공통 계약 확장·연결 명세 / 기준: `8836558` / 책임 제안: World 환경 입력, 원준 snapshot·transport, 권신혁 v3 adapter, 조연우 표면·표현.

선행: [T01](01_RUNTIME_CONFIGURATION_AND_AUTHORITY.md). 확인: [F07·F08](99_DECISIONS_AND_CONFIRMATIONS.md). 회귀: T03/T10, 공간 먹이 영향은 T09.

## 1. 목적과 필요성

서버가 눈으로 속도·시야를 줄인다면 Client도 같은 지역의 눈을 표시해야 한다. 카메라 진입이나 로컬 날씨 BP가 서버 규칙을 결정하지 않게 하고, 늦은 참가자에게 현재 환경을 제공한다.

## 2. 현재 구현과 실제 공백

- 공통 FRegionEnvironmentState는 Temperature/Humidity/Rainfall/WeatherState를 가진다. enum은 Clear/Rain/Storm/Drought이며 Snow가 없다.
- AEcoRegionEnvironmentAdapter는 서버 ApplyWeather/ApplyRainfall, Client의 GameState 요약 소비와 OnEnvironmentUpdated/OnClockUpdated 이벤트를 제공한다.
- FEcoCompletedWorldSummary는 같은 완료 시점의 clock·지역·종 정보를 한 property로 전달한다.
- v3는 자체 기본 날씨(숲 비·고지 눈·메마른 땅 맑음)를 사용한다. EnvWatch는 팀 상태의 변화와 v3 CVar를 읽는다.
- v3 WeatherPresenter는 Dedicated와 Client에서 시작하지 않는다. 현재 공통 요약에 v3 고지의 눈이 자동으로 들어간다고 해석하지 않는다.

## 3. 개발 범위

포함: 공통 환경 형식 결정, Source 변환, 적용 revision/시각, Client 날씨·하늘 표현, 지역 전환·늦은 참가 검증.

제외: 날씨가 바뀌는 게임 규칙의 신규 설계, 임의 성장·Food 계수 변경, 새로운 PPO 학습, 모델 교체 Shipping 활성화. 비·눈에 따른 Native 계수는 기존 계약을 보존한다.

## 4. 데이터·버전 제안

F07 권고안은 기존 enum 끝에 Snow를 추가하고 세기 의미를 분리하는 것이다. 아래 논리 필드는 설계안이며 전부 새 wire 필드로 강제하지 않는다. 기존 FEcoCompletedWorldSummary를 우선 확장·재사용한다.

| 항목 | 계약 |
|---|---|
| WorldEpoch/RegionId | 서버 world·지역 식별 |
| EnvironmentRevision | 지역 환경 확정 변경마다 증가 |
| WeatherKind/Intensity | 맑음·비·폭풍·가뭄·눈과 유효 세기 0~1 |
| Temperature/Humidity/Rainfall | 기존 의미 유지; Snowfall 채택 여부는 F07 |
| EffectiveTime/CompletedStep | 환경이 확정·요약된 공통 시각 |
| NativeAppliedStep | v3 내부 적용 step과의 매핑 진단; 공통 step과 혼동 금지 |
| Source | World/BP/개발 override 출처, 진단용 |

Snow를 넣으면 enum 끝값 비교, ApplyWeather/ApplyRainfall 입력 검사, Blueprint switch, serialization·save 호환 여부, Native 변환을 함께 수정한다. 기존 Rainfall을 눈의 강수량으로 조용히 재정의하지 않는다.

## 5. 권위 입력·처리 순서

```text
서버 World 날씨 결정
 → 범위·지역·revision 검증
 → 공통 환경 staging
 → 정해진 경계에서 공통 snapshot + v3 적용
 → 완료 환경을 GameState에 publish
 → Client 이벤트 → 카메라별 비/눈/하늘/오디오
```

1. World 담당이 지역별 변경을 서버에 제출한다. 환경 Adapter는 World NetMode로 권위를 검사한다.
2. 동시에 입력되는 BP·AuthoredWeather 반복 적용·CVar override의 우선순위를 F07에서 고정한다. 원복도 새로운 환경 revision으로 남긴다.
3. Native step과 Ecology resource step의 빈도는 다르다. 적용 시각을 매핑하고, 아직 Native가 반영하지 않은 값을 반영 완료로 발표하지 않는다.
4. 단일 summary는 공통 clock·Food·환경을 같은 완료 경계로 묶는다. agent FastArray와의 전역 원자적 도착은 보장하지 않는다.
5. Client는 최신 epoch/revision을 읽고 표현만 갱신한다. World subsystem의 논리 입력을 역으로 수정하지 않는다.
6. WeatherPresenter를 공통 DTO 소비자로 바꾸거나 기존 Weather BP를 연결하는 방식을 한 가지로 선택한다. 두 연출기가 같은 비·눈·오디오를 중복 생성하지 않는다.

## 6. 낮밤·지역·수명

낮밤은 공통 서버 clock을 사용한다. 기존 SkyManager의 자체 SunSpeed로 논리 낮밤과 화면이 분리되지 않게 OnClockUpdated를 연결한다. Time dilation·pause·catch-up 사용 여부는 실행 manifest에 남긴다.

날씨는 지역별 상태이고 연출은 로컬 카메라별이다. Dedicated는 FX·오디오를 만들지 않는다. Client A가 숲, B가 고지에 있으면 서로 다른 연출을 보되 두 지역의 권위 입력은 공통 상태를 따른다. 경계에서 히스테리시스나 crossfade를 쓰더라도 논리 지역을 바꾸지 않는다.

맵 이동·EndPlay는 Niagara/오디오/타이머를 정리한다. 처음 접속한 Client는 과거 전환 이벤트 없이 현재 상태를 만들 수 있어야 한다.

## 7. 구현 단계

- WT-A: F07 형식·입력 우선순위를 결정하고 모든 관련 switch·enum 검사를 검색한다.
- WT-B: 공통 환경·Native 적용 시점과 revision 연결을 구현한다.
- WT-C: Client DTO 소비와 Sky/Weather BP 인계를 연결한다.
- WT-D: 기본 날씨·서버 runtime 변경·늦은 참가를 각각 검증한다.
- WT-E: F08에서 선택한 빌드 종류별 동작을 기록한다. 개발 전용 EnvWatch를 Shipping에서 동작한다고 표기하지 않는다.

## 8. 검증 시나리오

| ID | 조건 | 기대 결과 |
|---|---|---|
| WT01 | 숲 비·고지 눈·메마른 땅 맑음 | 서버 Native와 공통 summary·Client 일치 |
| WT02 | 서버 Rainfall 변경 | 다음 계약 경계 반영, Client 지연 측정 |
| WT03 | 눈→비→맑음, 세기 0·1 | 필드 의미 보존, 잔류 FX·소리 없음 |
| WT04 | A/B 다른 지역·경계 왕복 | 각 카메라 연출만 변경, 서버 입력 유지 |
| WT05 | 변경 후 늦은 참가·재접속 | 현재 환경 즉시 구성, 과거 이벤트 불필요 |
| WT06 | NaN/범위 밖/없는 RegionId | 전체 요청 거부·사유 기록 |
| WT07 | Dedicated no-player | 환경·생태 진행, FX/오디오 0 |
| WT08 | CVar/BP/AuthoredWeather 충돌 | 확정 우선순위로 1개 입력, 진동 없음 |
| WT09 | 낮밤 속도·저 FPS | 화면 clock과 완료 snapshot 일치 |

## 9. 완료 조건

환경 source·세기·눈 계약과 버전 처리가 확정돼 있고, 서버·Native·Client의 revision/시각 상관 기록이 있다. 화면의 날씨만 바뀌었는데 논리는 그대로인 상태를 성공으로 기록하지 않는다. T06/T09에 환경 revision·적용 경계를 인계한다.

## 10. Source·문서 근거

- [환경 형식](../../../Source/AdaptiveEcosystem/Core/EcoRegionTypes.h), [Adapter](../../../Source/AdaptiveEcosystem/World/EcoRegionEnvironmentAdapter.cpp)
- [공통 clock](../../../Source/AdaptiveEcosystem/World/EcoWorldClockSubsystem.cpp), [지역 DTO](../../../Source/AdaptiveEcosystem/Network/EcologyNetworkTypes.h)
- [v3 환경 감시](../../../Source/AdaptiveEcosystem/AI/Policy/EcoV3EnvWatch.cpp), [v3 연출기](../../../Source/AdaptiveEcosystem/AI/Policy/EcoV3WeatherPresenter.cpp)
- [팀 환경 요청](../../RL_Policy/TEAM_REQUESTS_V3.md), [실시간 환경 계약](../../RL_Policy/LIVE_ADAPT_SPEC.md)
