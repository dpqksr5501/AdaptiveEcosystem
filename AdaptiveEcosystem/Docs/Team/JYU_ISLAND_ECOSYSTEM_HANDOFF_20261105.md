# 팀 섬 레벨의 생태계 적용

## 2026-11-13 최신 팀 통합

기준은 `origin/main` `9c961e48`과 조연우 `e81a2ac3`이다. 권신혁 `origin/Branch_Sinhyeok` `35179936`과 송해찬 `origin/feat/ecosystem-integration-map` `7e3fdce5`는 이미 기준 이력에 들어 있다. 장원준 `wonkii/jwj-1024` `ef44df15`를 병합해 Native 공간 검색, 식생 에셋 경로 복구와 공유 풀, 지역 순차 이주, 1102 4지역 맵을 가져왔다. 지역 순차 이주와 기존 무리 이주는 각각의 승인 조건을 지키며, 기존 이동과 도착 장부를 사용한다. 물길은 수생 규칙 종의 경로로 유지한다. 팀 날씨의 유효 상태를 사용하며 지역 액터가 스트리밍에서 빠지는 동안에는 마지막으로 완료한 환경 스냅샷을 유지한다.

최신 실행 맵은 `/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed`다. 송해찬 원본의 World Partition 지형, 눈·들판·고원, 네 호수(Oasis 포함), 세 강, 바다와 폭포를 복제하고 기존 수위와 지면에 맞춰 생태 배치를 다시 적용했다. 원본의 비식생 액터와 변환값을 대조해 빠지거나 변한 원본 배치가 없음을 확인했다. 원본 식생 19,818개를 포함해 복사본에 31,900개 인스턴스가 있다. 생태 배치는 강둑 20구간, 호안 91구간, 지상 먹이 12곳과 보금자리 8곳이다. 기존 송해찬 섬 맵, 조연우 초기 복사본, JWJ 1102 맵은 각자 브라우저에서 열 수 있다.

재작성 시 복사본 생성은 `Tools/Editor/apply_jyu_island_ecosystem.py`, 다종 배치는 `Tools/Editor/author_jyu_island_fauna.py`에 각각 `-EcoIslandRefresh`를 사용한다. 검증은 새 맵에서 시드 20000과 `audit_jyu_island_fauna.py`로 실행했다. 실제 DX12 PIE에서 초기 16종 118마리, 사슴 R7e, 강의 물고기 16마리 이동, 세 물고기 그룹의 섭식, 육상과 수생 출생을 확인했다. 강의 첫 잉어 출생 시 사슴용 공간 먹이 격자를 요구해 권위 실행이 정지하던 문제를 고쳤다. 강의 출생은 기존 수생 산란장·먹이 조건 및 지역·전체 개체수 제한을 거친다. 같은 시드로 잉어 출생 후 210 게임초까지 실행했고 검증 오류는 0이었다. UE 5.8 직접 빌드와 AdaptiveEcosystem 자동화 332건이 통과했다.

JWJ 1102 맵은 별도 DX12 PIE에서 55 실시간 초 동안 실행했다. 네 지역의 권위 식생 필드와 먹이 풀을 확인했다. 이 실행에는 이주 완료가 기록되지 않았다. 기록은 `Saved/TeamIslandIntegration/JWJ1102_Runtime.json`에 있다.

섬 결과는 `Saved/FaunaAudit/IslandRefreshInventory.json`, `Saved/FaunaAudit/IslandFaunaPIE.json`, `Saved/Logs/IslandRefreshPIEAfterBirthFix.log`, `Saved/Logs/IslandRefreshAutomationFinal.log`에 있다. 장시간 개체군 균형, 이주 도착, 멀티플레이 접속, HLOD 재빌드·패키징은 후속 검증 항목이다. 체크포인트 포맷 11에 순차 이주 상태를 함께 싣는다. 이전 포맷의 체크포인트는 새 실행에서 불러올 수 없다.

## 이전 섬 복사본 적용 기록

- 원본은 `/Game/Map/LV_SHC_IslandEcosystem1_WP`이다.
- 실행용 복사본은 `/Game/JYU/Maps/LV_JYU_IslandEcosystem`이다. 에디터의 New Level From Template으로 복제해 World Partition 외부 액터도 새 맵 경로에 저장했다. 원본 팀 맵과 공유 지형·물 재질은 그대로 참조한다.
- `Tools/Editor/apply_jyu_island_ecosystem.py`는 복사본의 `JYU.IslandEcology` 태그를 가진 배치만 교체한다. 네 지역의 좌표는 전체 섬의 바이옴 경계가 아닌 시연용 초기 위치이며, 팀의 지역 경계가 확정되면 함께 맞춘다.

| 구역 | 중심 XY (cm) | 생태 입력 |
| --- | --- | --- |
| Snowfield | 20,000 / −10,000 | Alpine, −4°C, 낮은 강수량 |
| Grassland | 90,000 / 60,000 | 아래쪽 평지, TemperateMosaic, 초지, 보통 배수 |
| Riverbank | 36,500 / 34,800 | 상류의 육지 쪽, TemperateMosaic, 습윤 식생, 느린 배수 |
| Highland | 50,700 / 49,500 | 절벽 안쪽 고원, Alpine, 서늘한 기후, 빠른 배수 |

복사본의 JYU 게임 모드에서 초원 플레이어 시작점을 사용한다. 기존 Native v3 코디네이터 하나에 식생, 출생·성장, 지역별 권위 강수 입력을 연결했다. 각 구역의 지면을 직접 투영한 뒤 배치한다. 팀 정책/가중치와 런타임 C++는 그대로 사용한다. 이주 경로를 연결하려면 지역 간 경사·단차·수심을 별도로 확인한다.

## 폭포와 수원

섬에는 WaterBodyRiver 3개, WaterBodyLake 2개, WaterBodyOcean 1개가 있다. 폭포 연출은 별도 메시와 폼·물보라 액터로 구성된다. 이번 적용은 강가의 식생 유형과 배수만 명시한다. 폭포는 생태 수원·도하·이주 경로에 연결하지 않았고, 강·호수의 실제 수면 높이와 지면 연결이 확인되면 기존 `EcoVegetationHabitat` 수원 입력을 적용할 수 있다. 폭포 표시 버그의 원인과 수정을 별도로 검증한다.

## 실행과 확인

콘텐츠 브라우저에서 복사 맵을 열어 플레이한다. 방목 이력·웅덩이·새순 색을 포함한 후속 규칙을 보려면 Unreal 실행 인자에 `-EcoHabitatDynamics`를 추가한다. 이 인자는 자연 서식지 설정이 있는 월드에서만 쓰인다.

에디터 설정 검사 `Errors=0`을 확인했다. `-EcoHabitatDynamics`로 실행한 Standalone(NullRHI)의 25초 표본에서 코디네이터가 준비됐고 네 구역에 권위 개체 64마리가 있었다. 지면이 연결된 식생 셀은 Snowfield 900, Grassland 900, Riverbank 897, Highland 730개였다. Riverbank의 수변 유형 셀은 121개로 집계됐다. 보고서는 `Saved/IslandEcologyRuntime.json`, 실행 로그는 `Saved/Logs/IslandPlayDiagnostics.log`에 있다.

## 렌더링을 켠 플레이 점검

UE 5.8 D3D12 PIE에서 네 지점을 순회했다. Snowfield는 눈 덮인 지면, Highland는 절벽과 고원 경계에 해당한다. 처음 Grassland도 눈 덮인 고원에 있어 아래쪽 풀밭으로 이동했다. Riverbank의 첫 배치에서는 사슴과 식생이 물 표면 안쪽에 보였다. 중심을 서쪽 육지로 이동했고 이후 화면에는 사슴과 식생이 육지에 보였다. 이 비교는 확인한 화면 범위다. 강·호수 전체의 수심이나 도하 판정을 검증한 결과가 아니다.

강가 구역을 64m 폭으로 줄인 중간 실행에서는 Native 초기 자리 검사를 통과한 수가 사슴 11/12, 늑대 3/4여서 기존 실행으로 되돌아갔다. 중심을 옮긴 상태에서 폭을 84m로 복원한 최종 PIE는 네 지역 Native 실행과 권위 개체 64마리로 시작했다. 섬의 기존 나무와 지형 장식은 레벨의 표현이며, 먹이량을 가진 풀·수변 식생·관목과 동물은 네 생태 구역에서 작동한다.

폭포 아래에서 물줄기 위쪽의 직선 경계가 절벽 위로 떠 보이는 현상을 재현했다. 복사본의 폭포 메시 높이를 위쪽에서 줄이고 하단 위치를 유지했다. 위쪽 각도에서 폭포는 연결돼 보이지만 아래에서 보이는 직선 경계는 남아 있다. 메시/재질의 경계 원인을 확정하지 않았으며 수원 연결도 보류했다.

### 강수와 낮밤

권위 지역 강수의 변화와 PIE의 비 표현을 확인했다. 강수 어댑터는 비/맑음을 발행한다. 설산의 눈 덮인 지면은 팀 레벨의 재질이며, 강설·적설 변화는 이 점검에서 확인하지 않았다.

기존 자연 서식지 조명 제어기는 지정된 태그를 가진 조명만 사용한다. 섬 복사본에서 태양·스카이라이트와 전역 노출 볼륨을 연결했다. 태양만 있는 밤 표본에서 지면이 거의 검게 보여 달빛을 추가했다. 같은 카메라를 사용한 최종 PIE에서 낮 태양·달 광도는 각각 8.0/0.0, 권위 시계 88초의 Night 구간에서는 0.0/0.12였다. 비 오는 밤에도 지면과 사슴이 보였다. 이 비교는 QA에서 시간 배율 3을 사용했으며, 강수 및 낮밤 계산은 기존 경로를 사용했다. 지역의 기존 `FRegionEnvironmentState.DayPhase`는 이 표본에서 Day로 남았으므로 낮밤 확인에는 `EcoGameState`의 권위 시계를 사용한다.

화면 증거는 개인 발표자료 폴더의 `2026-11-05/스크린샷/섬`, `섬_최종`, `섬_조명`에 있다. 전용 서버·클라이언트, 패키징과 장시간 개체군 안정성은 별도 검증 범위다.

## 기존 강과 호안의 다종 배치

2026-11-13 후속 작업은 `LV_JYU_IslandEcosystem`에 저장했다. `LV_JYU_IntegrationR7eFauna`에 잘못 적용했던 이번 배치는 되돌렸다. 이 섬 복사본에는 기존 호수 두 곳과 강 세 곳이 있으며 최신 원본의 Lake3와 Oasis는 아직 복사본에 없다.

- 하류의 기존 담수 약 130m에 연결되는 수영 구역 10개와 수중 먹이·산란 후보 6곳을 작성했다. 초기 배치는 메기 3, 잉어 6, 임시 담수 프로필의 미확인 모델 7, 밍크 2다. 별도 수면이나 하상을 추가하지 않았다. 바닥 검사와 수영 스윕은 WaterBody의 수면 쿼리 콜리전을 건너뛰고 실제 지형을 읽는다. 폭포와 하구에는 민물고기 초기 개체를 배치하지 않았다. [하천 서식처 분류](https://pubs.usgs.gov/of/2002/ofr02438/) · [아리아케 메기 산란 연구](https://cir.nii.ac.jp/crid/1910020910704301952) · [잉어 정착·가입 연구](https://doi.org/10.1080/00028487.2012.754791)
- 초지는 말 5, 돼지 4, 물소 4, 까마귀 3을, 고원은 큰뿔양 5와 게임에서 검독수리로 표현한 대체 모델 2를 사용한다. 상류 쪽 육상에는 산토끼 계열 4, 여우 2, 쥐 6, 표범 1을 놓았다. 기존 네 육상 지역은 사슴 R7e와 늑대 Native 규칙을 유지하고 하류는 규칙 종의 스폰만 허용한다. [말의 무리 행동](https://www.blm.gov/blog/2022-03-18/managing-wild-geldings-public-lands) · [큰뿔양의 절벽 서식지](https://home.nps.gov/jeca/learn/nature/bighorn-sheep-ovis-canadensis.htm)
- 하류 양안 20개와 두 호안 62개의 지형 단면에서 물가를 찾았다. 수중 수초 4,584개, 정수 식생 2,586개, 초본·관목 1,040개, 나무 196개와 돌·뿌리 등 398개를 인스턴스로 저장했다. 고산 호안은 큰 활엽수와 고사리 대신 낮은 식생 위주로 배치했다. 별도로 섭취 가능한 육상 군락 12곳을 기존 재고 및 재생 표현에 연결했다. 네 육상 지역의 보금자리 여덟 곳은 중심과 반경 10.4m의 지면을 검사해 물에서 높이 65cm 이상 떨어지도록 했다. 이 수치는 배치 기준이며 수위가 변하는 범람 시험은 별도다. [연안 수심별 식생](https://www.dnr.state.mn.us/shorelandmgmt/apg/wheregrow.html) · [호안의 식생 완충대](https://www.michigan.gov/egle/about/organization/Water-Resources/inland-lakes-and-streams/shoreline-protection)

작성은 [섬 배치 스크립트](../../Tools/Editor/author_jyu_island_fauna.py), 재검증은 [PIE 검사](../../Tools/Editor/audit_jyu_island_fauna.py)를 사용한다. 배치와 PIE 결과 및 1920×1080 화면은 `Saved/FaunaAudit/IslandFauna*`에 있다.

최종 UE 5.8 직접 빌드와 저장본의 D3D12 PIE(시드 20000, 175.27 게임초)를 확인했다. 5개 지역에서 16종 118마리로 시작했고, 사슴 두뇌는 `v3_r7_g995_s1_20m@40d8710d`였다. 하류에서 사슴·늑대가 생성되던 경로를 차단했다. 여섯 수심 표본은 약 1.49–1.50m였고 물고기 16마리의 이동, 잉어 6건과 메기 2건의 수중 먹이 섭취가 기록됐다. 육상 섭식과 큰뿔양·말·돼지·물소·산토끼 등 8종의 출생도 기록됐다. 밍크의 입수와 상륙, 미확인 물고기의 섭취, 부화·지역 간 이주·전체 섬 수용력, 섬의 HLOD 전환과 장시간 개체군은 이번 실행에서 확인하지 않았다.

PR 준비 시 태양과 달의 방향광 우선순위가 모두 0이라 물·포그가 사용할 방향광을 선택하는 경고가 표시되는 것을 확인했다. 섬 작업본의 태양에 우선순위 1을 지정했다. 저장본 재실행에서 해당 경고가 재현되지 않았으며, 수중·호안·고원 화면과 먹이 섭취를 다시 확인했다. 동물 16종과 돼지 별도 프리셋의 표현 17개에서 메시, 머티리얼 슬롯, 텍스처 참조를 검사해 누락 0건을 확인했다. `origin/main` 병합본의 직접 빌드와 AdaptiveEcosystem 자동화 320건이 통과했다. 로그는 `Saved/Logs/IslandMaterialBindings.log`, `IslandFaunaPRVerification.log`, `IslandPRAutomation.log`에 있다.

### 공유 후속 작업

[PR #19](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/19)의 검증 기준 커밋은 `fa0c04dd`다. 최신 팀 지형으로 옮길 때는 [지형 이식 이슈](https://github.com/dpqksr5501/AdaptiveEcosystem/issues/20)에 기존 수역과 보금자리 단면의 차이를 기록한다. 수생 생명주기, 렌더·스트리밍, 경사 표현, 플레이어와 장시간 검증은 [팀 후속 이슈 목록](FAUNA_TEAM_REQUESTS_20261113.md#pr-19-후속-이슈)을 따른다.
