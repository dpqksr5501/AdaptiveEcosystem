# 자연 서식지·식생 공통 계약

작성일 2026-10-30. 현재 작업 트리의 추가 구현이며 main/push 완료를 뜻하지 않는다. 이전 [life rules v2](../조연우/JYU_PLAYFLOW_FIX_20261029.md) 위의 명시적 opt-in이다. 실제 실행 결과는 [검증 기록](../조연우/JYU_NATURAL_HABITAT_20261030.md)에서 구분한다.

## 자연 자료를 게임 규칙으로 옮기는 기준

| 근거 | 자료에서 가져온 방향 | 이번 구현과 해석의 한계 |
|---|---|---|
| [USDA NRCS: Ecological Site Descriptions](https://www.nrcs.usda.gov/getting-assistance/technical-assistance/ecological-sciences/ecological-site-descriptions) | 토양·지형·기후·물과 식물 군집을 함께 다루며 환경 변화가 완만한 곳에는 넓은 전이대가 존재한다. | Region 이름만으로 식생을 선택하지 않고 지면과 habitat volume의 배수·그늘·연결 수원 및 생육 profile을 소비한다. Priority/고유 HabitatId/경계 혼합으로 authoring을 분리한다. |
| [University of Minnesota: Water and Light](https://open.lib.umn.edu/horticulture/part/chapter-11-water-and-light/) | 물·빛·온도가 생장과 식물의 수분 이용에 영향을 준다. | 수분 허용 구간·온도 최저/적정/최고·그늘 내성을 guild별 설정으로 제공한다. 자연 profile에서는 완전한 어둠에 새 biomass를 생성하지 않는다. 실제 광합성·탄소저장 모델은 아니다. |
| [USGS: Ground Water and Surface Water](https://pubs.usgs.gov/circ/circ1139/htdocs/natural_processes_of_ground.htm), [NRCS: Woody Plants Field Guide](https://www.nrcs.usda.gov/plantmaterials/idpmcpu12618.pdf) | 물가 식생은 지하수위·실제 수문 연결·침수 및 현장 조건에 의존한다. | 확인한 연결 수원 volume과 지면/수면 높이만 공급 입력이다. 가까운 물 mesh로 벽·절벽 너머 물을 생성하지 않는다. 비수변 guild의 깊은 침수는 성장 불가다. 수리망/지하수/유체 해석은 미구현이다. |
| [NPS: Desert Ecosystem](https://www.nps.gov/para/learn/nature/desert-ecosystem.htm) | 사막의 수분 제한과 식물 사이의 빈 공간을 고려한다. | Dryland profile의 수분·온도 허용 범위 및 표현 밀도/크기를 별도 authoring한다. 개별 뿌리 경쟁을 계산하지 않으며 모든 사막 식물을 하나의 실제 종으로 취급하지 않는다. |
| [NPS: Alpine Vegetation & Soils](https://home.nps.gov/im/gryn/alpine-vegetation-soils.htm) | 고산의 낮은 기온·바람·짧은 생육기와 낮은 식물 형태를 고려한다. | Alpine profile의 낮은 적정 온도·낮은 표현 높이·경사 제한을 제공한다. 풍식·설피·계절별 생육기/종자 휴면은 후속이다. 고도만으로 기온을 중복 보정하지 않는다. |
| [Montana State University: White-tailed Deer Management](https://animalrangeextension.montana.edu/wildlife/private_land_wildlife_mgmt/whitetail-mgmt.html), [Washington DFW: Deer](https://wdfw.wa.gov/species-habitats/living/species-facts/deer) | 은폐·휴식·온열 환경과 먹이터 배치를 구분하고, 가까운 위험에는 은폐물 사이로 벗어나는 행동을 참고한다. | 내부 자리→경계→휴식과 실제 감지한 가까운 위협에서 재도주한다. 수풀은 무적이 아니며 발견과 포획을 분리한다. 특정 사슴 종의 행동 시간·서식 면적을 그대로 복사하지 않는다. |

프로필의 수분 0..1·온도 한계·3–7초 경계 시간·군락 크기·밀도·자리 간격은 **자료의 정성적 방향을 옮긴 조정 가능한 게임 값**이다. 자료에서 검증한 실측 계수 또는 현실 생태의 정밀 재현이라고 설명하지 않는다. 시간은 기존 Native simulation seconds이며 현실의 생장 연/월/일을 뜻하지 않는다.

## 책임과 opt-in

`AEcoCreatureIntegrationSpawner::NaturalHabitatProfile`이 null이면 기존 life-v2/soil-v1 안전·성장·표현 경로를 유지한다. 지정하려면 Native v3 + life + vegetation과 유효한 `UEcoNaturalHabitatProfile`이 필요하다. owned `LV_JYU_Ecosystem`에만 프로필을 지정한다. 팀 원본 레벨·기존 RefugeSafety/V3Integration 맵에 일괄 적용하지 않는다.

프로필은 공유 설정이며 개체 상태를 담지 않는다. 전역 profile은 공통 군락 시드/범위/지면 검사·시각 설정을 제공한다. 개별 `AEcoVegetationHabitat::GrowthProfile`은 해당 volume의 dryland/alpine 생육 변형을 제공한다. Plant는 기존 Grass/Riparian/Shrub 세 guild이며 새 식물 종 backend를 완료했다는 뜻이 아니다.

World 지면/날씨/토양 입력 → Native 기존 성장/환경 손실 → M4 단일 거래 → Field 시각 DTO가 흐름이다. 군락 샘플/mesh 수를 FoodAmount로 환산하거나 BP/Client/ISM에서 먹이를 생성하지 않는다. 식생 확장은 기존 용량 거래와 이후 Native 재생을 유지한다. 원본 PPO 모델·관측 차원·Raw Request·SocialControl=0은 보존한다. 새로운 세계 규칙의 Python mirror/재학습은 미완료다.

## 레벨에 제공하는 입력

사슴의 외형 번호는 기존 presentation flags의 미사용 6..7 bit로 전달한다. 4..5 bit의 기존 Sight/Hearing/Memory를 보존한다. 사슴용 adult Stag/Doe/immature 번호는 실제 herbivore body에만 설정하며 늑대/기존 맵의 외형 번호는 0이다. 감지 변화로 외형이 바뀌거나 외형으로 감지 근거를 덮어쓰지 않는다.

- `RegionId`: 실제 지역과 일치. 서로 다른 층/동굴을 같은 Native XY cell에 겹쳐 넣지 않는다.
- `NaturalHabitatProfile`: 기본 군락/생육/지면 검사 설정. 맵 좌표나 JYU label을 공통 C++에 넣지 않는다.
- `HabitatId`: 지역 내 고유하고 이름 변경과 독립적으로 유지하는 FName. 중복/누락은 거절한다.
- `Priority`: 낮은 순서부터 혼합하고 높은 우선순위가 뒤에서 덮는다. 동률은 HabitatId의 lexical 순서로 결정한다.
- `BlendDistanceCm`: volume 안쪽 XY 경계 전이 폭. Z 포함은 명시적 volume 범위로 검사한다. 수문 연결은 이 범위를 넘겨 추측하지 않는다.
- `Drainage`, `Shade`, `Plant`, `GrowthProfile`: 실제 토양/수관 조건을 authoring한다. 나무 그림자나 landscape 재질에서 자동으로 측정했다고 해석하지 않는다.
- `bConnectedFreshWater`, `WaterSurfaceZ`, `MaxSupplyRiseCm`: 실제 확인된 수원 연결. 겹친 volume은 가산하지 않고 bounded blend한다.
- `ProbeAboveCm`, `ProbeBelowCm`: Region ground datum을 기준으로 한 허용 수직 조사 범위. Landscape 또는 actor/component `Eco.VegetationGround` 태그를 허용한다. `Eco.NoVegetation`은 제외한다. 바위/지붕을 기본 지면으로 오인하지 않는다.

같은 XY 조사에서 서로 다른 적격 표면이 150cm 이상 떨어져 있으면 식생 표본을 거절한다. 지면 미로딩/모호함은 토양 불모의 증거가 아니므로 잔량을 삭제하지 않는다. 경사가 확인되어 생육 한계를 넘은 경우와 구분한다. 한 cell의 중심과 최대9개의 표현 후보를 각각 실제 지면에서 검사하며 바닥 법선에 맞춘다. 지면 갱신은 bounded slice다.

군락은 RegionId+profile seed+cell+ordinal로 안정화한다. 넓은 연속 noise는 미세 서식처를 표현하는 조형적 대용치다. 어느 seed에서도 동일한 규칙을 쓰며 전 세계를 하나의 격자 십자 패턴으로 채우지 않는다. 먹이를 먹으면 같은 후보가 성기고 작아지고, 회복하면 같은 자리에서 복원된다. Client는 서버가 검사한 GroundSites와 Food/Moisture/Stress DTO를 사용하고 새 식생/지면을 논리적으로 계산하지 않는다.

## 은폐·휴식·안전의 구분

식생 위치/잔량의 네트워크 표현은 공간 chunk당 최대 64개 표본 cell과 576개 실제 지면 site로 분리한다. 메타데이터 field와 별도 actor로 복제하며 같은 거리 relevance를 쓴다. Client는 받은 chunk를 모아 표시하고 지면 재검사/자원 계산을 하지 않는다. 늦은 접속의 단일 대형 bunch를 막는 구조이며 NetDriver 전송 한도를 키우지 않는다. chunk 해제/재수신은 권위 식량·개체를 생성/제거하지 않는다.

명시적 지면 태그의 mesh는 Native 나무/바위 원판으로 취급하지 않는다. 물리 충돌·지면 경사/단차 검사는 그대로다. 벽까지 포함한 actor 전체에 지면 태그를 붙이지 않고 복합 actor는 실제 바닥 component에 지정한다.

profile의 `bWildRefuges=true`인 세계는 등록/해제·height binding·먹이 페널티를 유지하되 ShelterSafe/JYU protected wall과 내부 포획 후보 제외를 적용하지 않는다. 일반 은폐에서 포획되면 정상 결과이며 안전 계약 위반 counter로 올리지 않는다. 기존 protected fixture와 구분한다.

Native control hook은 기존 단일 이동 writer에 의도만 제공한다. HIDE/영역 내부 SLEEP은 개체별 내부 후보를 선택하고 실제 지면과 시작 이동을 확인한다. 몸·다른 개체/선택 자리·해당 anchor의 수용 인원을 확인한다. 매 이동은 기존 Native terrain/contact constraint를 통과한다. 장기간 무진행/자리 상실/영역·등록 변화에는 다시 선택하고, 자리를 못 찾으면 가장자리에 앉지 않는다. 이주와 유효한 Social 예약에는 중복 자리 소유자가 되지 않는다.

내부 목표에 도착하고 몸 여유·개인 위협 관측/최근 경계·개체별 대기 시간이 충족되어야 휴식한다. 접근·경계·휴식·도주·자리 실패는 별도 진단 상태다. 실제로 본 가까운 위협에는 다시 달아난다. 숨었다고 개인 기억/포식자의 기존 증거를 삭제하지 않는다. 일반 수풀의 안쪽일수록 제한된 탐지 거리 이점이 있으나 실제 포획 거리에는 마법 배수를 주지 않는다. Predator의 물리 경로/LOS·포획 판정은 그대로 소비한다.

`AEcoRefugeHabitat::bNaturalLayout`은 수풀 군락의 불규칙 외형을 선택한다. 기존 원형 바위 울타리/십자 통로를 제거하며, 자연 경로에서는 기본 cosmetic boulder 수가 0이다. 물리 바위/동굴은 별도 실제 collision으로 authoring한다. 장식 바위가 늑대의 몸을 막는다고 설명하지 않는다. 런타임 수풀 위치도 authority가 지면을 검사해 복제하며 Client마다 다른 지면에서 다시 배치하지 않는다.

## 통합 레벨 적용과 지원 경계

1. 기존 supported Native region/stage와 실제 연결 가능한 이주 경로를 먼저 준비한다.
2. 지역 ground datum과 profile probe band를 새 지형에 맞추고 지면 태그/경사를 확인한다.
3. 프로필을 지정하고 고유 ID·우선순위·XYZ 범위를 가진 soil/vegetation/water volume을 배치한다.
4. 은폐는 실제 지면과 수풀/수관·출구·먹이터 관계를 보며 배치한다. 새 profile이 기존 실제 장애물/이주 경로를 자동 생성하지 않는다.
5. 저장/재로드, 일반 PIE, 실제 섭식·성장·도착·포식·이주, Dedicated/late join, cell별 M4 수지를 확인한다.

현재 Native는 수평 좌표+지면 추종인 2.5D다. 다층 동굴·겹친 지표의 동시 시뮬레이션, 수영/물속 먹이·강 유속/범람 전파·자동 nav graph·모든 생물군계의 실재 종 라이브러리·완전한 계절 천이는 완료하지 않았다. 본 구조는 서로 다른 높이의 **지면을 따라 연결된 공간**에 재사용할 입력/검증을 제공한다. 겹친 층을 완전 지원하려면 SurfaceLayerId/접근 연결을 Native food·감각·이주 identity까지 확장해야 한다.

World Partition에서 시각 actor가 사라졌다는 이유로 권위 자원/인구를 새로 생성하지 않는다. 전체 production streaming/cook acceptance와 장기 개체군 평형은 별도 검증 항목이다.

현재 Native stage 한 변은 120..220m 범위다(`StageSizeUnits=60..110`, `kUnitCm=200`). 큰 레벨의 RegionBounds를 늘리는 것만으로 무제한 stage를 만들지 않는다. 지원하는 지역·stage와 실제 이주 연결로 authoring하며, 전역 규모 backend 확장은 별도 계약/측정 대상이다.
