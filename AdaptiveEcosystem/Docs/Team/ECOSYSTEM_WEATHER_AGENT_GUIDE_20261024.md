# 날씨·낮밤 담당·AI agent 작업 안내

작성일 **2026-10-24**. 구현 기준 `d095948`, 공통 안내 기준 `9858e61` 이후 문서 보완이다. [공통 맥락](../PROJECT_CONTEXT.md)·[팀 AI 안내](ECOSYSTEM_AI_COLLABORATION_20261024.md)와 [레벨 담당 안내](ECOSYSTEM_LEVEL_DESIGN_AGENT_GUIDE_20261024.md)를 먼저 읽는다. 문서 작성 자체는 새 날씨 기능·런타임 검증·학습 완료가 아니다.

## 1. 현재 날씨 연결을 이해하기

현재 owned `/Game/JYU/Maps/LV_JYU_Ecosystem`에는 `BP_JYU_EcosystemWeather` 3개가 지역별 권위 강수를 공급한다. 180 simulation seconds의 건조→비→건조와 Forest/Barren/Highland 위상차0/30/60초는 명시적으로 만든 순환이다. 확률 날씨/계절·자연 기후 균형을 구현한 것은 아니다.

```text
Server/Standalone Ecology clock
  → AEcoRegionEnvironmentAdapter의 고정 입력 또는 강수 순환
  → AEcologyRegion의 FRegionEnvironmentState
  → GT Native Step 직전 Rainfall/Temperature snapshot
  → FoodGrid soil 수분·성장·환경 손실 → 실제 먹이·섭식·M4 receipt

완료된 regional summary + server time → AEcoGameState
  → Client/관찰 카메라의 날씨·조명·소리 표현
```

이 경로 외에 기존 Native v3 `FWeatherConfig`의 감각/속도 날씨와 Native Dark가 있다. 세 값의 이름이 날씨라고 해서 자동으로 같은 입력이 되는 것은 아니다. 아래 구분을 유지하고 필요한 연결을 별도 계약으로 구현한다.

## 2. 서로 다른 네 가지 입력

| 경로 | 실제 의미·Source | 현재 경계 |
|---|---|---|
| 지역 환경 | `Core/EcoRegionTypes.h`, `World/EcologyRegion.*`, `World/EcoRegionEnvironmentAdapter.*` | Temperature ℃, Humidity/Rainfall 0..1, DayPhase·WeatherState; World 입력 |
| soil 날씨 | `AI/Policy/EcoPolicyV3IntegratedProcessors.cpp`의 VegetationWeather | Rainfall·Temperature와 `1−Ctx.Sim.Dark` 사용; 현재 Humidity/광원 밝기를 직접 대신 넣지 않음 |
| Native 감각/속도 날씨 | `AI/Policy/EcoWorldV3.h`의 FWeatherConfig, Integrated Settings | clear/rain/snow 및 감각·이동 배수; 지역 Rainfall을 바꿨다고 이 설정까지 바뀐다고 가정하지 않음 |
| 로컬 연출 | `AI/Policy/EcoV3WeatherPresenter.*` 및 BP 이벤트 | 수신 summary 또는 기존 Native context를 읽는 표현; 자원/감각 규칙의 writer 아님 |

지역 enum은 Clear/Rain/Storm/Drought이며 **Snow가 없다**. Native 날씨 번호 clear/rain/snow와 enum ordinal을 cast하지 않는다. 현재 식생 맵의 summary 연출 경로는 Rain/Storm + Rainfall>0일 때 비를 표시한다. 기존 Native 경로의 눈 연출을 근거로 이 summary 경로도 눈을 전달한다고 주장하지 않는다. 눈 축적·해빙·적설 공급·Storm의 번개 피해/바람·Drought의 별도 피해 역시 자동 구현된 효과가 아니다.

Native Dark와 권위 DayPhase/조명 진행이 항상 같은 계산이라고 가정하지 않는다. 현재 soil의 빛은 Native Dark에서 가져온다. DirectionalLight 회전·SkyLight 밝기·material에서 측정한 lux를 생태 입력으로 읽는 기능은 이 계약에 없다. 낮밤 통합을 바꿀 때는 실제 Native clock/provider부터 추적하고 수면·감각·성장·기억 TTL·저장/재시작 영향을 함께 검증한다.

## 3. 기존 날씨 BP를 연결하는 방법

기존 visual BP 전체를 새 구현으로 갈아엎기 전에 현재 부모와 실행 경로를 조사한다. `AEcoRegionEnvironmentAdapter`는 Blueprintable이며 다음 API/이벤트를 제공한다.

| API/설정 | 사용법·실패 조건 |
|---|---|
| RegionIds | 명시적 대상 목록 권장; 비어 있으면 현재 등록된 모든 지역 |
| ApplyRainfall(Rainfall, WeatherState) | 권위 GameWorld에서 강수/상태만 갱신; 지역별 Temperature/Humidity 보존 |
| ApplyWeather(FRegionEnvironmentState) | 전체 구조체 갱신; 한 지역의 기본 기온/습도를 모든 biome에 복사할 수 있으므로 주의 |
| bApplyAuthoredWeather + AuthoredWeather | 고정 전체 입력 모드 |
| bCycleRainfall | 권위 clock 기반 순환 강수 모드; 고정 모드와 동시 사용 거절 |
| OnEnvironmentUpdated | 완료 summary의 epoch/revision 변화에 따라 지역별 전달되는 표현 이벤트 |
| OnClockUpdated | Phase와0..1 PhaseProgress의 표현 이벤트; clock을 다시 advance하는 지점 아님 |

API 반환값을 확인한다. RegionId 중 하나가 없으면 대상 전체를 먼저 검증하여 쓰기를 거절한다. NaN·비유한 값·Humidity/Rainfall 범위 밖·잘못된 WeatherState는 거절한다. Temperature는 유한 여부뿐 아니라 downstream soil 허용 범위도 확인한다. UI clamp만을 유효성 보장으로 해석하지 않는다.

Client 배치 Actor의 HasAuthority 값만으로 쓰기 권한을 판단하지 않는다. 기존 adapter는 `NM_Client`를 명시적으로 거절한다. Client는 GameState 수신 값을 읽고 연출하며 자체 랜덤 날씨·clock 진행·FoodGrid를 만들지 않는다. 일반 Client RPC로 모든 지역 날씨를 임의 변경하게 노출하지 않는다.

한 지역·한 입력에 writer 하나를 둔다. 현재 순환 adapter에 외부 manager가 ApplyRainfall을 호출해도 다음 adapter tick이 다시 덮을 수 있다. 외부 날씨를 채택할 때 해당 지역의 고정/순환 자동 쓰기를 명시적으로 정리하고 외부 manager의 권위 갱신 지점을 하나로 연결한다. 외부 manager와 기존 presenter의 중복 Niagara/소리도 별도로 검사한다. 다른 팀 원본 BP를 무단 수정하거나 기존 맵 전체에서 삭제하지 않는다.

## 4. 순환 설정과 시간

현재 adapter tick 간격은0.2초이며 매 프레임 자원을 갱신하지 않는다. 순환은 `UEcoWorldClockSubsystem::GetServerTime().ServerTimeSeconds`를 사용한다. clock은 기존 lifecycle coordinator가 한 번 진행한다. 새 날씨 Tick이 AdvanceClock을 호출하지 않는다.

| 항목 | 현재 허용 값 |
|---|---|
| RainCycleSeconds | 20..86400 simulation seconds |
| RainPhaseOffsetSeconds | 유한 값; 음수도 modulo로 처리 |
| DryRainfall, WetRainfall | 각각0..1 |
| RainTransitionFraction | 0.01..0.25; 주기의 전환 구간 비율 |

현재 순환은 전반 건조→중간 상승→후반 강수→끝 하강을 smoothstep으로 잇는다. Wet이 Dry보다 반드시 큰지 의미 검사는 별개이므로 반전 의도 여부도 확인한다. 시작 직후 비가 온다고 가정하는 테스트를 만들지 말고 실제 phase/강수를 기다린다. clock·phase offset·seed·활성 모드를 evidence에 적는다.

Native step은2/15 simulation seconds, 길이1 native unit은200cm다. renderer의 fade는 world frame seconds다. benchmark·가속·pause·재시작에서 simulation seconds/wall seconds/Native tick을 구분한다. hitch의 wall dt를 soil에 한꺼번에 적용하거나 날씨가 전환될 때 clock을 초기화하지 않는다. 현재 checkpoint가 모든 새 BP schedule/provider 상태까지 저장한다고 가정하지 말고 필드별 저장 범위를 확인한다.

## 5. 강수와 먹이의 실제 관계

강수 입력은 즉시 food를 생성하는 명령이 아니다. 수분은 강수 침투·명시적 수원·침수와 증발·배수·식생 소비를 적분한다. 식물 종류/수분 구간·온도·빛·지면에 따라 성장/손실이 달라진다. “비를 두 배로 하면 먹이도 두 배”를 acceptance로 정하지 않는다.

M4에서 spatial food 등록 지역은 기존 별도 지역 재생을 제외한다. 비 BP가 legacy `ApplyVegetationRegrowth` 또는 직접 FoodAmount를 갱신하면 이중 지급이 된다. 식생 수지는 Before−Consumed+Regenerated−EnvironmentLost=After다. 강수 연출의 SpawnRate·소리 볼륨·물 material을 자원으로 역변환하지 않는다. soil leaf parity가 일치해도 전체 ON 세계 parity/재학습 완료는 아니다.

Humidity는 지역 환경 필드지만 현재 soil snapshot의 수분값 그 자체가 아니다. Rainfall은 정규화 입력이며 mm/h나 습도%와 같은 단위라고 가정하지 않는다. 실제 기상 단위를 도입하면 변환·허용 범위·기간·누적량·Python mirror와 버전을 함께 정의한다.

soil은 숫자 Rainfall을 소비하지만 현재 summary 비 연출은 WeatherState도 검사한다. 예를 들어 Clear인데 Rainfall>0인 입력은 화면과 생태가 어긋날 수 있다. adapter의 기본 범위 검사를 통과했다는 사실만으로 이런 의미 일관성까지 검증된 것은 아니다. 호출자가 상태/강수 조합을 함께 맞추고 실패 사례를 acceptance에 포함한다.

## 6. 날씨 연출·조명·소리

현재 presenter는 카메라 위치를 읽는다. 첫 로컬 PlayerController의 카메라를 사용하므로 Pawn이 다른 지역에 있어도 카메라 지역의 날씨가 보일 수 있다. split-screen 모든 로컬 플레이어 지원을 이미 완료했다고 쓰지 않는다. XY 지역이 겹치면 이름 순 첫 지역이 선택되므로 레벨 담당과 경계/겹침을 확인한다. 실내 비 차단·지붕 검사·동굴별 날씨는 이 기능만으로 제공되지 않는다.

현재 비 Niagara `/Game/SHC/ART/FX/Rain_System`, 소리 `/Game/SHC/Audio/Environment/A_Rain_Cue`, 기존 눈 `/Game/SHC/ART/FX/NiagaraSnowfall/Effects/NS_Blizzard`를 재사용한다. 비는 User.SpawnRate·fade와 세기, 소리는 볼륨/시작/정지를 소비한다. 눈 에셋은 현재 세기 parameter가 없으므로 비와 똑같은 연속 밀도 제어를 가정하지 않는다. Dedicated/렌더 불가 환경은 mesh/FX·소리 표현을 생성하지 않는다.

로컬 제어:

```text
eco.IntegratedV3.WeatherVisuals 0
eco.IntegratedV3.WeatherVisuals 1
eco.IntegratedV3.WeatherRainDensity 2
```

Visuals OFF는 연출만 끄며 권위 강수·수분·Native Step을 끄지 않는다. Density는 빗줄기 배수다. Native 감각 날씨의 `eco.IntegratedV3.Weather`와 이를 혼동하지 않는다. OFF→ON·경계 출입·맑음 전환에서 particle/AudioComponent 실제 활성·잔류·정지를 확인한다. 캡처에 비가 보인다는 사실만으로 소리를 청취 검증했다고 쓰지 않는다.

조명은 OnClockUpdated를 소비해 연출할 수 있지만 권위 clock을 재시작/진행하지 않는다. 별도 timeline·랜덤으로 Client마다 DayPhase가 달라지지 않게 한다. 안개/후처리의 화면 visibility와 Native sight multiplier가 자동 동기화되는 구조는 아니다. 지형 Shade authoring과 실시간 shadow도 구분한다.

## 7. 새로운 날씨를 도입할 때 필요한 계약

| 제안 | 먼저 정할 내용 |
|---|---|
| 눈/적설/해빙 | 지역 schema·DTO·권위 누적/손실·soil 변환·기존 Native snow 매핑·cook·mirror |
| 확률/계절/장기 기후 | seed/RNG 소유·simulation time·schedule/state 저장·재시작·holdout |
| 바람/폭풍 | 벡터 단위·지역 경계·감각/이동/식생 영향과 단일 writer·네트워크 주기 |
| 일조 통합 | Native Dark/World phase의 관계·provider·수면/성장/관측·기존 Golden 영향 |
| 외부 날씨 plugin | 실제 사용 입력/권위·오프라인 fallback·모델 세계 판·라이선스/cook·비용 범위 |

새 WeatherState enum 값을 넣는 작업은 색/이름 추가에 그치지 않는다. old save/DTO·enum 검증·Client fallback·정책/mask/관측·Python 계약을 함께 확인한다. 기존 관측 슬롯을 새 날씨로 조용히 재해석하거나 기본 weights를 덮어쓰지 않는다. 외부 실시간 API/유료 서비스 도입은 이 문서가 자동 승인하지 않는다.

## 8. 검증 순서와 실패 진단

1. 기준 SHA·맵·RegionIds·모드·clock·Native weather flags·현재 환경을 기록한다. 외부 writer/중복 visual manager를 찾는다.
2. 고정 맑음/비와 순환 경계를 각각 확인한다. 입력·지역 환경·Native VegetationWeather·food audit·수신 summary·FX를 따로 기록한다.
3. 잘못된 RegionId·NaN/범위 밖·고정/순환 동시 설정·Client 쓰기 거절을 검사하고 기존 상태가 유지되는지 확인한다.
4. 기온/습도가 다른 두 지역에 ApplyRainfall을 적용해 보존을 확인한다. ApplyWeather 전체 덮어쓰기와 혼동하지 않는다.
5. PIE와 Dedicated+복수 Client에서 서로 다른 카메라 지역·late join·지역 출입·OFF/ON을 확인한다. Client authority 논리0과 수신 표현을 구분한다.
6. 비 visual OFF 중에도 clock/강수/수분·수지가 진행되는지 확인한다. FX를 꺼서 생태 비용이 사라졌다는 식의 성능 결론을 내리지 않는다.
7. 새 soft 참조가 있으면 실제 cook/패키지를 확인한다. 기존 PAL의 AlwaysCook과 non-editor-only type scan·실제 ReferencedSet/런타임 로딩까지 확인한다.

`Tools/Editor/audit_ecosystem_weather_controls.py`는 기존 제어 회귀의 출발점이다. 실행 전 대상·전제·파일 출력과 쓰기를 읽는다. `test_vegetation_network.ps1`의 `-AuthoredWeather`는 observer가 별도 강수를 쓰지 않는 저장 BP 관찰 조건이다. 강제 가뭄 fixture는 food 제거/재생 중지가 포함되어 자연 날씨 실험으로 사용하지 않는다. 상세 명령은 [life 재현](../Architecture/ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md#재현-순서)을 따른다.

2026-10-23 기존 evidence에는 실제 강수를 기다린 연출 OFF/ON·밀도 검사, soil parity, PIE/멀티/패키지 범위가 기록돼 있다. 이번 안내 작성에서 새 UBT/PIE를 실행하지 않았다. 기존 테스트 수를 자신의 새 날씨 코드 검증으로 재사용하지 않는다.

실패를 좁히는 기준: 비만 안 보이면 camera region/summary의 state·rainfall/visual cvar/soft 참조/중복manager를 확인한다. 비는 보이는데 식생이 안 변하면 server 환경→Native snapshot→soil/지면/capacity·실제 시간→장부 순으로 확인한다. 감각만 예상과 다르면 별도 FWeatherConfig·Dark·현재 backend와 기존 모델 계약을 확인한다. 어느 단계가 실패했는지 기록하고 값을 강제 보충해 숨기지 않는다.

## 9. 인계와 AI 시작 요청

레벨 담당에게 region/Bounds·수역/실내/카메라 경계·새 참조를, 서버 담당에게 DTO/주기·authority/late join·저장 state를, 학습 담당에게 Native 규칙 차이·단위/시간/범위·세계 profile을 전달한다. baseline/candidate의 seed·일정·변경 계수를 고정해 규칙과 모델 효과를 구분한다. [종료 양식](ECOSYSTEM_AGENT_START_PROMPTS_20261024.md#5-종료-인수인계-양식)에 미검증 범위까지 적는다.

```text
루트 AGENTS.md, Docs/PROJECT_CONTEXT.md, 팀 AI 공통 안내와
Docs/Team/ECOSYSTEM_WEATHER_AGENT_GUIDE_20261024.md를 읽고
내가 지정한 날씨/낮밤 작업을 실제 소비자까지 연결해줘.
현재 branch/HEAD·WIP·대상 맵/RegionIds·writer·backend/flags를 확인하고
지역 환경/soil 강수·기온/Native 감각 날씨·Native Dark/로컬 연출을 구분해줘.
기존 adapter ApplyRainfall/ApplyWeather와 clock·GameState summary를 사용하고
Client/시각 BP의 food/HP/clock writer나 두 번째 날씨 쓰기를 추가하지 마.
Native snow와 지역 enum을 cast하거나 world 전체 parity/새 학습 완료를 가정하지 마.
고정/순환 충돌·잘못된 지역/입력·Client 쓰기·시간/단위·재시작/저장 영향을 검증해줘.
외형 OFF 중에도 생태가 진행되는지, camera 경계·late join·FX/소리 정지와
필요한 cook/실제 패키지까지 확인해줘. 원본 팀 BP/맵·기존 모델을 보존해줘.
C++/빌드 입력 변경은 루트 직접 UBT·대기 규칙을 따르고
미실행 테스트·미지원 효과를 구분한 한글 인계와 evidence를 남겨줘.
```
