# 04. 환경과 자원 폐루프

상태: 기존 환경·먹이 연결의 공통화 계획. [전체 구조·기준](../README.md)을 따른다.

## 필요한 기능

서버의 날씨·낮밤이 먹이와 감각·행동에 영향을 주고, Client가 같은 환경을 표시해야 한다. M4 환경 Adapter, #13 비·눈 표현, v3의 지역별 날씨 규칙·공간 먹이 장부는 기존 구현으로 활용한다.

## 구현 방향

```text
서버 World 환경 snapshot → 자원 재생 / 감각·관측 → 행동·소비
                        → GameState DTO → Client 하늘·날씨
소비 결과 → Ecology 원장 → 다음 관측
```

1. 지역별 날씨 종류·세기·시각·완료 step을 공통 입력으로 정하고 v3의 고정 날씨 설정과 연결한다.
2. 기존 ApplyWeather/ApplyRainfall 및 OnClockUpdated/OnEnvironmentUpdated를 활용해 Weather/Sky BP를 연결한다.
3. v3 공간 먹이는 PR의 RegisterSpatialFood/CommitSpatialFood를 재사용한다. 같은 지역에 기존 재생·섭식 writer가 중복 적용되지 않게 한다.
4. 같은 완료 step의 환경·Food·관측·실제 섭식·인구를 비교한다. 환경 계수 변경은 Python 파리티·평가와 함께 진행한다.

## 기술과 완료 기준

읽기 snapshot, 완료 step, 공통 clock과 표시 시간의 구분, Blueprint 이벤트, 자원 보존식을 익힌다.

완료: `다음 Food = 이전 Food + 재생·공급 - 소비·손실`이 맞고, 카메라가 지역을 떠나도 서버 환경·생태가 계속된다. v3 공간 먹이 원장 자체를 새 기능으로 중복 개발하지 않는다.

관련: [환경 Adapter](../../../../Source/AdaptiveEcosystem/World/EcoRegionEnvironmentAdapter.h), [M4 자원·환경 계약](../../../Integration/M4_RUNTIME_INTEGRATION_CONTRACT.md).
