# 팀 레벨의 생태계 런타임 배치

작성: 2026-10-08. `origin/main`의 `908d06f`(레벨 추가 `de891bf`)를 `codex/social-shelter-handoff`에 병합했다. 병합 commit은 `edba605`다. 원본 설명은 [통합 맵 안내](../Integration/ECOSYSTEM_INTEGRATION_MAP_SETUP.md), 동물·PPO·Social·네트워크 책임은 [Creature 통합](CREATURE_PRODUCTION_INTEGRATION.md)을 따른다.

## 에디터에서 바로 확인

현재 동물은 접촉 Notify 및 실제 지형 재질로 발소리를 고르고 늑대도 별도 감각을 사용한다. [최신 감각·Notify 계약](CREATURE_SENSORY_AND_NOTIFY_REFINEMENT.md)을 함께 확인한다.

발소리 Grass/Dry 임포트·SA 연결·시야/청각 범위 표시는 [동물 발소리와 감각 디버그](CREATURE_FOOTSTEPS_AND_SENSE_DEBUG.md)를 참고한다.

1. UE 5.8에서 `/Game/Map/LV_Ecosystem_IntegrationTest`를 열고 **Play**한다. 기본 시작점은 초원 수풀 근처이며 WASD/마우스로 관찰한다.
2. Outliner의 `EcologyRuntime`에 Regions 3개, ResourceHints 3개, Shelters 2개, Coordinator 1개가 있다. 사슴·늑대 BP는 실행 중 Mass 개체를 표현하기 위해 생성되므로 따로 배치하지 않는다.
3. 처음에는 사슴 16 + 늑대 3 = **19마리**다. 웨이브는 꺼져 있어 포식 후 개체 수가 감소한다. 반복 관찰은 PIE를 재시작한다.
4. 서버/Standalone 콘솔 `eco.Shelter.Log 1`로 Moving → Occupied → 해제를 확인한다. `eco.Creature.DrawFacing 1`은 속도와 Mesh 전방 화살표, `eco.Creature.FacingAudit 1`은 정렬 오차 로그다.
5. 클라이언트에는 기존 Mass 복제 거리 안의 개체만 보인다. 현재 Off 거리는 엔진 기본 **5000cm**이며 멀어진 동물이 표시에서 제외되는 것은 전체 생태계가 멈춘 것을 의미하지 않는다.

기존 M3 Bootstrap과 이 조정자를 같은 맵에 함께 배치하지 않는다. 프로젝트 기본 시작 맵을 바꾸지 않았으므로 위 맵을 직접 연다.

## 배치 구성

| 레벨 담당의 기준 | 런타임 RegionId | 초기 사슴 / 늑대 | FoodAmount / Capacity | 인접 지역 |
|---|---|---:|---:|---|
| `TV_Region_Forest`, 초원·수풀 | `Forest` | 8 / 1 | 1400 / 2000 | Barren |
| `TV_Region_Barren`, 황무지 | `Barren` | 4 / 1 | 500 / 1000 | Forest, Highland |
| `TV_Region_Highland`, 설원·고지대 | `Highland` | 4 / 1 | 600 / 1200 | Barren |

원본 TriggerBox는 유지하고 동일한 경계에 `AEcologyRegion`을 추가했다. 각 경계 중심은 `(0, 50000, 0)`, `(0, 0, 0)`, `(0, -50000, 0)`, 반경은 `(75000, 25000, 15000)`cm다. 논리 SpeciesId `Herbivore`가 사슴 BP로 표시되며 늑대는 `Wolf`다. 기존 EntityConfig GUID·PPO 가중치·BS를 재사용한다.

| 배치 위치 (XY, cm; Z는 실제 지면) | 의미 |
|---|---|
| Forest `(약 34000, 약 45700)` | 사슴 무리, 늑대 `(35100, 47100)` |
| Barren `(약 34000, 0)` | 사슴 무리, 늑대 `(35000, 2500)` |
| Highland `(약 34000, -50000)` | 사슴 무리, 늑대 `(35000, -47500)` |
| Forest `(33300, 45100)`, `(34200, 44400)` | 수동 은신처 2개, 각 4슬롯·반경 150·Quality 0.65 |
| Forest/Barren/Highland `(34000, 30000)`, `(34000, 20000)`, `(34000, -30000)` | 인접 경계 방향의 이주 도착점 |
| `(34200, 46500)`, `(34000, 1000)`, `(34000, -49000)` | 각 지역 먹이 밀도 분포 중심 표시 |

은신처는 원본 `TP_Shelter_Forest_01` 주변의 실제 수풀 안에 배치했다. 보이는 수풀과 Quality 기반 보호를 제공하지만, 모든 수풀 Mesh가 물리적 시야 차폐를 보장하지는 않는다. LOS는 실제 충돌에 따라 계산한다. 황무지·설원에는 원본 cover가 없어 은신처를 임의로 만들지 않았다. 은신처 슬롯은 현재 수평 링이므로 4슬롯의 지면 높이 차이가 35cm 이하인 위치만 배치한다.

`Eco_FoodHint_*`는 자원 분포 중심 표시다. 먹이 양은 기존 지역 `FoodAmount`와 배치 먹이 배분 API가 관리하며, 표시 Actor가 별도 식물 재고를 소유하지 않는다. 지역 온도/습도는 각각 20/.7, 30/.2, -5/.4의 **초기 테스트 값**이다. 학습 모델의 수치·정규화 계약 변경은 없다.

## 실제 지형에서 필요한 코드 보완

- 명시적 종별 world-space 스폰 좌표를 지원하며, 초기화 전에 전체 후보의 바닥·경사·장애물·지역 내부·금지 영역을 검사한다. 빈 좌표 배열은 기존 평면 테스트의 원형 배치와 호환된다. 실패하면 조용히 공중/물속에 생성하지 않고 시작을 거부한다.
- 기존 단일 이동 writer가 목적지를 지면에 투영하고, 원본 `NavArea_Null` 볼륨을 가로지르는 구간을 거부한다. 볼륨의 AABB를 30cm 확장한 보수적 검사이며, NavMesh 경로 탐색이나 물 우회 경로 생성까지 구현한 것은 아니다.
- 서버/Standalone의 opt-in Habitat Streaming Source가 초기 스폰·이주 도착점과 현재 논리 개체 주변 반경 100m를 유지한다. 첫 collision streaming 완료 후 시작하고 최대 30초를 기다린다. 위치는 초당 한 번 갱신하고 EndPlay에서 해제한다. Client는 이 authority source를 켜지 않는다.
- 지역·은신처·조정자 및 물 금지 볼륨 2개는 비공간 로딩으로 유지한다. 카메라가 멀어져도 지역 등록, shelter lease와 금지 영역 검사가 사라지지 않게 한다. 관찰 PlayerStart도 비공간 로딩으로 유지하며 기존 50m 복제 범위 안으로 이동했다.
- 원본 Landscape, 폴리지, HLOD 에셋과 물 타깃은 수정하지 않았다. Social에 실제 위치 적분이나 복제 transport를 추가하지 않았다.

## 배치 도구와 수정 방법

[배치 도구](../../Tools/Editor/place_ecosystem_runtime.py)는 해당 맵과 collision cell을 연 상태에서 에디터 콘솔 `py "프로젝트의 절대경로/Tools/Editor/place_ecosystem_runtime.py"`로 실행한다. [읽기 전용 조사](../../Tools/Editor/audit_ecosystem_level.py)도 같은 방식이다.

배치 도구는 모든 지점의 geometry를 먼저 검사하고 `EcoProductionPlacementV1` 태그와 label/class가 일치하는 소유 Actor만 생성·갱신한다. 재실행은 **도구의 좌표·값으로 되돌리는 작업**이므로 수동으로 바꾼 배치를 보존하려면 도구 설정도 먼저 수정한다. 다른 조정자나 같은 label의 외부 Actor가 있으면 중단한다. 생성 Actor와 외부 Actor를 맵과 함께 저장한다. 실행 결과의 자세한 XYZ는 로컬 `Saved/EcosystemRuntimePlacement.json`에 남으며 원본 조사 결과는 `Saved/EcosystemLevelAudit.json`이다.

현재 스폰 좌표 배열은 초기 인원만큼 준비되어 있다. 웨이브를 켤 때는 요청 인원을 만족하는 안전한 좌표를 추가하고 기존 개체와 겹치는 재스폰 및 장시간 개체군 균형을 별도로 검증해야 한다. 서버·클라이언트는 동일한 코드/에셋으로 실행한다.

## 검증 기록

- 직접 `UnrealBuildTool.exe` Editor Win64 Development 빌드 성공. 전체 프로젝트 자동화 **36 성공 / 0 실패 / 0 경고**. 신규 테스트는 실제 바닥 충돌·금지 영역의 스폰/구간 검사·허용 영역을 검증한다. 결과: `Saved/Automation/EcosystemLevelIntegration/index.json`.
- MCP Computer Use로 실제 에디터에서 저장 및 재실행. 재실행해도 편집 Actor 162개로 중복 생성 없음. Forest 약 Z=-1600, Barren 약 Z=1700, Highland 약 Z=2630의 지면에 19마리 정상 스폰했다.
- PIE에서 예약/이동 후 Occupied를 확인했다. Agent 5의 도착 거리 58.7cm와 Request/Feedback sequence 일치, NoShelterDemand 해제, 다른 개체의 사망 해제를 기록했다. 장시간 지역 먹이/인구/낮밤 요약 갱신도 확인했다. 로그: `Saved/Logs/EcosystemLevelPIE.log`.
- 별도 전용 서버에서 19마리·3지역 초기화 및 70초 후 `Ready=1 Step=69`, 서버 Visuals=0 확인. 최초 Client 시나리오에서 시작 시점/복제 거리 문제를 발견해 관찰 위치를 수정했다. 수정 후 결과는 아래에 기록한다.
- 최종 저장 맵을 다시 로드한 전용 서버와 Client를 별도 프로세스로 실행했다. Client는 `LogicalOwned=0 Visuals=7`로 실제 proxy/BP를 생성했고, 가까운 사슴의 움직임·Turn 입력·Mesh 전방 오차 30개 샘플의 최대 6.51도를 기록했다. 30초 후 `Ready=1 Step=0`으로 정상 종료했다. 동물이 50m 밖으로 이동하면서 Visuals가 7 → 1 → 0으로 줄었으며, 같은 시간 서버의 논리 생태계는 계속 진행됐다. 이 실행에서 늑대의 Client facing 샘플은 확보하지 않았으므로 늑대 방향 검증은 앞선 평면 통합 시나리오의 기록을 근거로 한다. 로그: `Saved/Logs/EcosystemLevelServerFinal.log`, `Saved/Logs/EcosystemLevelClientFinal.log`. 이 CLI 실행은 NullRHI이므로 렌더링 확인은 별도 실제 PIE 화면을 근거로 한다.

## 다음 담당자에게 남는 연결

- **World/레벨**: 현재 날씨 BP는 플레이어 주변 시각 효과다. 지역별 날씨를 `FRegionEnvironmentState`에 갱신하는 adapter, 식생 크기/자원 반영을 연결해야 한다. 원본 하늘 자동 주기는 꺼져 있고 논리 낮밤은 각각 60초다. 시각 하늘과 논리 clock 동기화는 미완료다.
- **World/RL**: 원본 `TP_Water_01..04`를 보존했다. 이번 작업은 물 진입 방지이며, 갈증 관측·마시기 행동·소비 계약은 추가하지 않았다. 기존 PPO 계약을 바꾸기 전에 담당자 합의와 parity 검증이 필요하다.
- **이동**: 금지 영역 앞에서 멈추는 것과 돌아가는 것은 다르다. 기존 단일 writer 앞에 목적지 경로/우회 adapter를 연결하고 이주 구간·경사·낭떠러지를 실맵에서 추가 검증한다. ORCA/자동 cover 생성은 Deferred 상태를 유지한다.
- **레벨 최적화**: uncooked 전용 서버 실행에 원본 HLOD의 editor-only builder 및 HLOD Actor GUID 경고가 있다. 런타임 중단은 없었지만 이번 배치 검증은 패키징/전체 HLOD 빌드 검증을 대신하지 않는다. 원본 지형 담당자가 cook/HLOD 경로를 확인한다.
