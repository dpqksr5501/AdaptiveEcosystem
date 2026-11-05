# 레벨 담당: 자연 서식지 적용 순서

2026-10-30 작업 트리 안내. 공통 [자연 서식지 계약](../Architecture/NATURAL_HABITAT_CONTRACT_20261030.md), [실행 검증](../조연우/JYU_NATURAL_HABITAT_20261030.md)을 먼저 확인한다. 실제 통합 레벨이 아직 제공되지 않았으므로 그 레벨의 acceptance를 수행했다고 해석하지 않는다.

## 레벨에서 연결할 것

기존 supported Native v3 coordinator 하나에서 Life/Vegetation을 켜고 `NaturalHabitatProfile`을 지정한다. `RegionHabitatProfiles`에 RegionId별 기본 프로필을 줄 수 있다. 서식지 내부에서는 `GrowthProfile`로 더 작은 토양/식생 변형을 지정한다. 프로필은 새 레벨의 owned 폴더에 복사/생성해도 되며 JYU 좌표·라벨을 런타임 코드에 넣을 필요가 없다.

이 profile은 생육 조건/서식지/표현 입력이며 Native의 초기 먹이 grid preset이나 종 backend 전체를 대체하지 않는다. 새 지역의 초기 자원·개체 밀도·Native stage/종 설정도 기존 backend 계약에 맞게 검토한다. Region의 legacy `InitialFoodAmount`만 바꾸어 Native 초기 분포를 authoring했다고 보지 않는다. 현재 연결은 Native가 만든 실제 grid를 M4에 등록하고 이후 생장/소모 거래를 일치시키는 경로다.

| 레벨 요소 | 레벨 담당이 입력할 값 | 공통 실행이 처리하는 일 |
|---|---|---|
| 지역/생물군계 | 고유 RegionId, Native stage/실제 지면 datum, 지역 기본 프로필 | 공통 식생/개체/장부·지면 검사와 환경 반응 |
| 초원/수풀/고산/건조 토양 | XYZ volume, 고유 HabitatId, Priority, BlendDistanceCm, 배수·그늘·Plant/GrowthProfile | 부드러운 전이, 군락 jitter, 실제 지면·경사 검사, 프로필 생육 조건 |
| 수원·물가 | 연결 여부, 실제 수면 Z, 공급 상승 한도, 물이 영향을 주는 volume | 수분·침수·성장 반응, 지면 backend의 깊은 물 진입 거절, 물가 표현 |
| 은폐/휴식 | 실제 anchor 지면/반경/수용량, `bNaturalLayout`, 수풀 mesh | 개체별 내부 자리·경계·휴식·재도주, 일반 수풀의 취약성 |
| 이주 | 실제 양방향 ground route/폭/지식 공유 여부 | 기존 Travel/이주 거래·개체 인계와 도착 뒤 로컬 분산 섭식 |
| 지면 재질 전이 | profile의 GroundTransitionMaterial/Tint/Strength | 장식용 decal 전이. 식량/날씨 writer가 아니며 원본 Landscape 재질을 변경하지 않음 |
| 낮밤 | 기존 sky manager 소유 여부, 명시적 Sun/Moon/Sky/Exposure 태그 | profile이 소유하도록 켠 경우에만 수신 시계로 기존 지정 광원·노출 조정 |
| 비/눈 | owned RainVisual/SnowVisual | 기존 지역 날씨/수신 summary를 쓰는 local presenter |
| 개체 외형 | 종 representation BP의 AppearanceVariants와 해당 skeleton 전용 profile/AnimBP | 서버 선택 성체/어린 외형을 기존 표현 flags로 전달. Client는 수신 표현만 적용 |

Source에서 지원하지 않는 수영/비행 종을 지상 이동 설정으로 통과시키지 않는다. 수원은 물 mesh의 색이나 거리만으로 연결하지 않는다. 나무 그늘·바위가 있다는 이유만으로 Shade·물리 진입 차단·은폐를 자동으로 완료했다고 판단하지 않는다.

이미 WaterBody/강·호수 렌더러가 있는 레벨에서는 그것을 수면 표현의 소유자로 둔다. `EcoVegetationHabitat`은 수면 Z/연결/범위를 가진 입력 actor로 연결하고, 필요하면 actor의 `Hidden In Game`으로 예제 수면·토양 장식 표시를 숨긴다. 숨김은 생태 입력을 지우지 않는다. `WaterSurfaceSizeCm`의 1..40m 범위는 예제 얕은 수면 장식의 크기이며 실제 공급 volume의 XY 범위를 그 크기로 자르지 않는다. 커다란 물가의 입력은 지역별로 나누고 실제 물 형상을 따라 배치한다.

## 새 레벨 점검

작은 owned `/Game/JYU/Maps/LV_JYU_HabitatTransferFixture`는 재사용 예제다. 서로 다른 `TransferMeadow/Dunes/Summit` ID와 0/2500/6000cm의 실제 tagged 지면, 같은 3개 profile과 별도 연결 수원을 사용한다. `run_natural_habitat_validation.ps1 -Mode Transfer`로 확인한다. 이 fixture는 포식자 OFF/분리된 platform의 제한된 PIE이며 미래 팀 레벨·실제 산길/이주·production streaming acceptance를 대체하지 않는다.

1. 원본 팀 레벨과 owned authoring 범위를 확인하고 coordinator/region/weather writer 중복을 없앤다.
2. 지면은 Landscape 또는 actor/component `Eco.VegetationGround` 태그를 사용한다. 제외할 지붕·장식에는 `Eco.NoVegetation`을 쓴다. 프로필의 ProbeAbove/Below 범위가 실제 지면 층을 가리키도록 한다.
3. habitat의 ID·우선순위·XYZ 범위·지역 참조를 연결한다. 논리 입력 actor는 권위 시뮬레이션 중 사라지지 않게 관리한다. 현재 예제는 `IsSpatiallyLoaded=false`다.
4. 기존 coordinator의 `ValidateEditorSetup`을 실행한다. 현재 레벨을 열어 둔 채 Python 콘솔에서 `py <project>/Tools/Editor/validate_natural_habitat_level.py`를 실행하면 `Saved/HabitatAuthoring/<현재레벨>.json`을 만든다. 이 도구는 맵을 로드·저장·수정하지 않는다. 설정 통과와 실제 플레이 acceptance는 별개다.
5. 지면 미확인/겹친 층·급경사·깊은 물·고유 ID 누락·잘못된 프로필을 고친다. 조사 budget 때문에 truncated이면 범위를 나눠 별도 검증한다.
6. 실제 PIE에서 식생 소모/회복, 물가 포함/제외, 은신처 가장자리/내부, 위협 재접근, 이주/분산과 M4 수지를 확인한다. Dedicated+늦게 들어온 Client에서 표현·외형·시계와 client 논리 0을 확인한다.
7. 프로필/volume/경로 변경 후 저장·재로드, startup checkpoint, 실제 cook/package, production streaming의 로드/해제/재진입을 검증한다. 저장은 같은 runtime image뿐 아니라 생육 프로필·입력 geometry signature가 맞아야 복원한다. 기존 슬롯을 삭제해 오류를 숨기지 않는다.

## 높이와 지원 경계

명시적 `Eco.VegetationGround` 메시는 Native의 나무/바위 장애물 원판 수집에서 제외한다. 실제 collision·지면 법선·경사/단차 검사는 유지한다. 바닥과 벽을 가진 복합 actor는 바닥 component에만 태그를 지정하고 벽/바위는 별도 component로 둔다. actor 전체를 지면으로 지정하면 그 actor의 메시 모두가 해당 역할을 갖는다.

현재 Native stage 한 변은 `StageSizeM`을 내부 60..110 units(1 unit=200cm), 즉 120..220m로 제한한다. 큰 통합 레벨은 지원하는 지역/stage와 실제 이주 경로로 나눠 연결해야 한다. RegionBounds만 크게 키운다고 전체 지형이 하나의 무제한 Native stage가 되지 않는다. 전역 규모 확장은 별도 backend/자원·감각·이동·streaming acceptance가 필요하다.

높이가 달라도 연속 지면으로 연결된 언덕/고산/하천 둑은 동일한 규칙과 지면 검사로 다룬다. 같은 XY에 동굴층/상부 지표가 겹치는 경우, Native의 한 지역 한 XY cell이 두 층을 동시에 소유하지 못한다. 식생 표본은 모호한 적격 층을 거절한다. 완전한 겹친 층 지원은 SurfaceLayerId와 이동·감각·자원·이주 계약 확장이 필요하다. 비행/수영/유속/지하수 해석까지 설정만으로 되는 구조라고 설명하지 않는다.

Profile의 야생 은폐 설정은 무적 안전 구역을 사용하지 않는다. 과거 보호 fixture 맵은 유지하며, 실제 바위틈의 통과 제한은 크기/충돌로 authoring한다. 장식 수풀이나 cosmetic rock을 물리 벽으로 간주하지 않는다. 기존 sky/weather manager가 낮밤을 소유하면 `bDriveDayNightLighting=false`를 유지하고 그 manager가 같은 권위 시계를 소비하도록 연결한다.

## 초기 나이·성장·가족과 군락 발달

후속 [개체군/성장 계약](../Architecture/NATURAL_POPULATION_CONTRACT_20261030.md)을 함께 적용한다. Profile의 Population에서 성숙 시간·초기 어린 개체 비율·암컷 확률·최대 초기 나이를 설정한다. Guild별 MaturationSeconds는 식생 발달의 게임 시간이다. 종별 실제 생태 수치로 설명하지 않는다.

현재 자연 사슴은 coordinator의 HerbivoreActorClass에 `/Game/JYU/Ecosystem/Natural/BP_EcoNaturalDeer`를 지정한다. 새 프로필만 연결하고 기존 Stag 전용 표현을 그대로 두면 연령 논리와 외형이 맞지 않는다. 새 종은 그 종의 실루엣/리그/성장 표현을 별도 authoring한다. Profile의 분포 변경은 새 초기 개체군에 적용되고 저장된 개체/이주 개체를 재추첨하지 않는다.

새 레벨 acceptance에 초기 나이/성별 혼합, 동일 ID의 성장 전후, 위험 시 따라가기 취소, 보호자 분리/사망 후 오래된 목표 제거, 늦은 Client의 성숙도/외형 일치, 저장/복원 후 관계/군락 발달 보존을 추가한다. 기존 명시적 spawn points의 군락/지형/최소 간격도 확인한다. 초기 나이를 다양화한 것만으로 배치/무리 행동의 전체 자연스러움을 통과 처리하지 않는다.

학습 담당 경계도 acceptance에 포함한다. Caution/새 나이·유전 정보를 기존 PPO 관측에 자동 추가하거나 새 도주/공격 정책을 만들지 않는다. 기존 행동/Raw Request를 보존하고 World/신체·Social/자리·Steering 책임에서만 소비한다. 현재 Source/가중치·관측 계약 보존 근거는 [기획 대조](../Architecture/INDIVIDUAL_TRAIT_DESIGN_AUDIT_20261030.md)와 실행 기록을 따른다.
