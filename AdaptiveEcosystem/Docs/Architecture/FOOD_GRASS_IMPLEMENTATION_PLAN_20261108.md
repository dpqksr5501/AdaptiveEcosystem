# 서버 먹이와 실제 풀 표현 연결 — 단계별 구현 계획

작성일: **2026-11-08**. 상태: **기존 월드에 연결하는 방식으로 구현 진행**.

사용자 요청: 지역별 실제 먹이 분포를 풀의 위치·밀도·높이에 연결하고, 섭식·환경 손실·재생이 화면에 드러나게 한다. 각 단계는 독립적으로 시험 가능해야 하며, 사용자가 디버그 화면에서 환경을 변경하여 결과를 확인할 수 있어야 한다.

아래 단계는 설계 목표다. 실제 조작법과 검증 범위는 [사용자 테스트 안내](FOOD_GRASS_TEST_GUIDE_20261108.md), [루트 진행 기록](../../../PROGRESS.md)과 §7의 기록을 기준으로 한다. 기존 Field Actor를 유지하기 위해 첫 전송 구현은 지역 경계 기반 relevance와 Fast Array 셀 변경분을 사용한다.

## 1. 다음 작업 시작점과 보존 대상

먼저 [프로젝트 공통 맥락](../PROJECT_CONTEXT.md), [팀 AI 안내](../Team/ECOSYSTEM_AI_COLLABORATION_20261024.md), [soil 계약](ECOSYSTEM_VEGETATION_CONTRACT_20261023.md), [life 실행 계약](ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md), [날씨 담당 안내](../Team/ECOSYSTEM_WEATHER_AGENT_GUIDE_20261024.md)를 읽는다. 구현 전 Root AGENTS와 Core/AI Policy/Mass 계약을 다시 확인한다.

- 조사 기준: branch `jwj-1024`, HEAD `395992ab`. 이것은 checkout/reset 지시가 아니다. 시작 때 실제 HEAD와 diff를 다시 확인한다.
- 기존 미커밋 변경: `AI/Policy/EcoObservationV3.h`, `EcoThreatModel.h`, `EcoWorldV3.h`.
- 기존 미추적 작업: `AI/Policy/EcoSpatialIndexV3.h`, `Docs/Performance/`, `Tools/EcoSpatialBenchmark/`.
- 위 작업을 덮어쓰거나 이번 구현에 섞어 커밋하지 않는다. 특히 `EcoWorldV3.h`는 공유 수정 지점이므로 변경 내용을 먼저 읽고 작은 범위로 수정한다.
- 기본 V1/v3 관측·행동·가중치, SocialControl=0, 단일 Native movement/metabolism/feeding writer, M4 장부, 기존 맵 옵션을 보존한다.
- 기존 `/Game/JYU/Maps/LV_JYU_Ecosystem`과 기존 Integrated Native V3 spawner를 재사용한다. 추가 맵·게임모드·플레이어는 범위에서 제외한다.
- 새 풀의 실제 생태 연결은 Integrated Native V3 대상으로 시작한다. V1/SpeciesAI 등 다른 먹이 소비 경로까지 자동 지원한다고 표시하지 않는다.

## 2. Source에서 확인한 현재 상태

| 항목 | 현재 구현 사실 | 이번 작업의 차이 |
|---|---|---|
| 먹이 저장 | `FFoodGrid`의 Food/Cap/Regen 연속 배열, 선택적으로 VegetationCells/Habitats | 별도 풀 잔고나 풀별 Mass Entity를 만들지 않음 |
| 격자 | 기본 FoodCell=2 native units, 1 unit=200cm. 실제 값은 설정에 따름 | 격자 해상도를 외형 개선만을 위해 임의 변경하지 않음 |
| 초기 분포 | 셀 난수를 평활화하고 임계값을 적용하여 Cap 생성, Food=Cap에서 시작. 활성 장애물/은신처 규칙 반영 | 우선 이 분포를 정확히 표현. 새 생태 분포 알고리즘은 별도 변경 |
| 지면 | `AEcoVegetationField::GatherGround`가 셀 중심을 trace, 32셀/frame, 순회 후 5초 재검사 | 여러 풀 후보의 지면 정렬과 생태/표현 책임을 구분 |
| 표현 | 지역별 Field Actor의 ISM, 최대256개 표본, 대체로 표본당 한 무더기, 1Hz 갱신 | 주변 셀의 완전한 상태와 셀 내부 여러 고정 후보로 풀밭 표현 |
| 먹이 표시 | `Food/Cap`을 uint8로 보내 크기 조절, 1% 이하 숨김 | 절대 용량 차이도 표현하고 작은 양의 표시 오차를 명시 |
| 갱신 | `OnRep_Cells`에서 모든 ISM instance 삭제 후 재생성 | 안정 ID로 유지하고 변경 셀만 갱신 |
| 식물 종류 | 현재 Source는 Grass/Riparian/Shrub별 component/mesh 선택 | 과거 문서의 “모두 같은 grass”를 현재 사실로 사용하지 않음 |
| 시야 | 현재 `FFoodGrid::BlocksSight`는 비Grass의 Shade·Food/Cap 등을 사용 | 새 시각 밀도를 논리 감각에 다시 쓰지 않음 |
| 표시/토양 옵션 | 식생 활성화와 Field 생성·soil 경로가 결합됨 | 외형 OFF여도 기존 soil/지면 입력은 유지하도록 분리 |
| 기존 환경 명령 | `eco.Environment.Rain <RegionId> <0..1>`은 권위 지역 강수 변경 | 자동 adapter가 덮을 수 있으므로 소유권을 갖는 테스트 세션 추가 |
| 기존 재생 명령 | `eco.Environment.Regeneration ...`은 지역 재생 프로필 설정 | SpatialFood의 soil 성장 속도 조절 명령으로 오인하지 않음 |

핵심 파일(이 문서 기준 상대 링크):

- [먹이 격자·Native 실행](../../Source/AdaptiveEcosystem/AI/Policy/EcoWorldV3.h), [토양 계산](../../Source/AdaptiveEcosystem/AI/Policy/EcoVegetationV3.h)
- [식생 Field](../../Source/AdaptiveEcosystem/World/EcoVegetationField.cpp), [식생 DTO와 설정](../../Source/AdaptiveEcosystem/World/EcoVegetationField.h)
- [환경 adapter](../../Source/AdaptiveEcosystem/World/EcoRegionEnvironmentAdapter.cpp), [기존 환경 명령](../../Source/AdaptiveEcosystem/Debug/EcoEnvironmentDiagnostics.cpp)
- [World별 디버그 명령 등록](../../Source/AdaptiveEcosystem/Debug/EcoDebugCommandSubsystem.cpp), [Inspector HUD](../../Source/AdaptiveEcosystem/Creature/Debug/EcoCreatureInspection.cpp)
- [통합 환경 입력](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp), [통합 초기화](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.cpp)
- [SpatialFood 거래](../../Source/AdaptiveEcosystem/Ecology/EcologySpatialFood.cpp), [기존 식생 자동화](../../Source/AdaptiveEcosystem/AI/Policy/Tests/EcoVegetationTest.cpp)

## 3. 최종 구조와 불변 조건

```text
디버그 화면에서 지역 선택·강수/기온/수원 변경
  → 해당 권위 World의 환경 입력 경로
  → 기존 Native 고정 step의 토양 수분·성장·손실·실제 섭식
  → 기존 FoodGrid + M4 완료 거래
  → 버전이 있는 셀 표현 snapshot / 변경분
  → 클라이언트의 고정 후보 위치 + ISM 밀도·높이·색 갱신
```

1. 실제 잔고는 서버 FoodGrid와 이를 검증하는 기존 M4 장부다. 구조체/배열 기반을 유지하며 풀마다 Actor/Entity/잔고를 추가하지 않는다.
2. 외형 설정, 카메라, LOD, ISM index, client frame rate는 먹이량·생장·감각·PPO 난수 결과를 변경하지 않는다.
3. 식생 표시 OFF와 soil 시뮬레이션 OFF는 다른 설정이다. 표시 OFF는 지면·서식지 입력까지 끄면 안 된다. Soil OFF 경로에서도 먹이 표현은 가능하되 수분/스트레스는 “미지원”으로 표시한다.
4. 기존 수지 `Before - Consumed + Regenerated - EnvironmentLost = After`와 별도 habitat 제거 거래를 보존한다. 화면 비율이나 합계로 장부를 역산하지 않는다.
5. `RegionId + GridRevision + CellIndex`가 셀 식별 기준이다. 월드 재시작은 WorldEpoch로 구분한다. 격자는 한 세션 동안 고정하며 layout 변경은 새 revision/full snapshot을 요구한다.
6. 후보 위치는 `RegionId의 안정적 인코딩 + CellIndex + CandidateIndex + LayoutSeed + LayoutVersion`으로 생성한다. FName runtime index/프로세스별 hash/Native RNG를 사용하지 않는다.
7. 카메라 근처에서 완전한 셀 분포를 보여주기 전까지 “전체 먹이의 풀 표현 완료”라고 기록하지 않는다. 옛 256개 표본을 주변 전체 상태인 것처럼 보간하지 않는다.
8. 시각 풀 한 포기가 특정 먹이량의 독립 소유자는 아니다. 실제 섭식 해상도는 셀 단위이며 입 바로 아래 한 포기 단위 소비는 이번 범위에서 제외한다.

### 3.1 표현 데이터와 위치 계약

- 정적 지역 정보: WorldEpoch, RegionId, GridRevision, LayoutVersion/Seed, 원점, 셀 폭·행렬 크기, 식물 외형 프로필.
- 셀 상태: CellIndex, Capacity, Food 또는 충분한 정밀도의 정량화 값, 선택적 Moisture/Stress, Plant, GroundReady/배치 가능 상태, Sequence·서버 시각.
- 후보 ID: CellIndex+CandidateIndex. ISM index는 가변 매핑이며 영속 저장하지 않는다.
- 절대량: 1차안은 용량에 비례한 최대 피복과 Food/Capacity 잔량 비율의 조합. 서로 용량이 다른 만량 셀을 똑같이 풍성하게 표시하지 않는다. 프로필의 표현 상한/포화 구간을 HUD에 명시한다.
- 정량화: 0은 정확히 보존한다. 작은 양이 0으로 반올림될 수 있는 한계를 정하고, 근거리에서는 비제로 표시 또는 최소 표시 단위를 설계한다. 물리적 먹이 단위를 풀 개수와 동일시하지 않는다.
- 지면: 서버의 생태적 유효 셀 판단과 렌더 후보의 세부 지면 projection을 분리한다. 클라이언트 projection 실패는 표시 대기이며 food 삭제가 아니다. 지형 스트리밍 후 재시도한다.
- 저장: 후보 전체 Transform/ISM index는 저장하지 않고 재생성한다. seed/version의 기존 world save 파생 가능성을 먼저 확인한다. 새 영속 필드가 필요하면 codec 버전·구버전 거절/이행 규칙과 회귀를 함께 변경한다.

## 4. 단계별 실행 계획

각 단계는 코드만 추가하고 끝내지 않는다. 빌드·자동화·사용자 조작 시험·기록까지 완료해야 다음 단계로 넘어간다. §7의 결과 기록을 기준으로 이어간다.

### P0 — 기준 장면과 측정값 확정

**작업**

- 현재 맵/backend/생태 flags/격자/seed/에셋 참조를 검사한다. Source의 옛 `/Game/MWLandscapeAutoMaterial/...` 경로와 현재 Content 위치, redirector/cook 가능성을 확인한다.
- 기존 생태계 맵에서 같은 높이·식물 타입·capacity 범위의 관찰 셀을 선정한다. 식생 전용 무동물 시험과 실제 사슴 섭식 시험을 재시작으로 선택할 수 있게 준비한다.
- 카메라가 생태계 위협으로 개입하지 않는 관찰 모드를 사용한다. 서로 다른 seed/동물 수/날씨의 결과를 A/B로 섞지 않는다.
- 전체 서버/클라이언트 메모리, FoodGrid 버퍼, Field/지면 캐시, ISM 수, 서버/GT/렌더 p95·max, 식생 transport bytes를 측정할 항목을 고정한다.

**단계 테스트**: 기존 강수 명령 적용과 자동 날씨의 덮어쓰기 여부, 실제 ground/food/ledger/256 표본 수를 기록한다. 이 시점의 시각 누락은 baseline으로 기록한다.

**완료 기준**: 맵·backend·seed·active flags·관찰 좌표·현재 실패·측정 환경이 재현 기록에 있고, 사용자 기존 변경을 보존했음이 diff로 확인된다. 후속 테스트를 위한 정상 지면 셀을 최소 1개 확보한다.

### P1 — 환경 디버그 세션과 관찰 화면

**작업**

- 기존 `AEcoCreatureInspectorHUD`의 별도 식생 패널/입력 helper로 추가한다. 기존 Tab/중클릭/R/M/대괄호 입력을 침범하지 않는다. 패널 열기 명령과 마우스 버튼을 제공하고 최종 키는 충돌 검사 후 안내서에 고정한다.
- 지역 선택, 셀 선택(지면 클릭 또는 격자 지도), 현재량/용량·수분·스트레스·성장/소비/손실·장부 오차·환경 입력/적용값·시험 경과를 표시한다. 전체 셀을 매 frame 직렬화하지 않는다.
- `수동 환경 시작`, `강수`, `기온`, `건조`, `회복 강수`, `자동 환경 복귀`, `결과 저장`을 구현한다. UI와 콘솔이 동일한 검증·적용 함수를 호출하게 한다.
- 지역 단위 override로 기존 adapter의 해당 지역 자동 쓰기만 유예한다. 하나의 adapter가 여러 지역을 맡는 경우 Actor Tick 전체를 끄지 않는다. 동일 지역의 복수 writer가 발견되면 충돌 사유를 보여주고 시작을 거절한다.
- 입력은 권위 GameThread의 안전한 경계에서 검증·적용한다. Mass processing 중이면 큐에 넣고 중복/잘못된 값/종료된 세션을 거절한다. UI에는 요청값과 실제 적용값을 따로 보여준다.
- 세션 종료·PIE 종료·맵 unload 시 override를 정리한다. 자동 복귀는 현재 시각의 정상 환경 writer로 제어를 반환하는 것이며 food/개체/시계를 되감지 않는다. 완전 초기화는 PIE 재시작이다.
- 테스트 제어는 Development/Editor 권위 World 전용이다. 일반 Client는 읽기 전용이며 새로운 임의 날씨 변경 RPC를 열지 않는다. Dedicated는 서버 콘솔/테스트 runner로 같은 입력을 실행한다.

**단계 테스트**: 사용자 `지역 선택 → 수동 시작 → 강수 변경 → 자동 복귀`. 자동화는 잘못된 지역/NaN/범위 초과/Client 쓰기/2개 PIE World 격리/지역별 자동 writer 보존/teardown을 검사한다.

**완료 기준**: 선택 지역의 실제 native 환경 입력이 바뀌고 비선택 지역은 덮어쓰지 않는다. 장부 직접 수정 없이 수분 변화가 관찰되며 패널에 적용/거절 사유가 나온다. 초기에는 기존 표본 풀로 시험 가능하다.

### P2 — 먹이 표현 계약과 시뮬레이션 분리

**작업**

- 기존 Field의 soil/ground 입력 서비스와 메시 표시 책임을 분리한다. 새 전역 먹이 Subsystem을 만들지 않고 기존 region context/Field 생명주기를 재사용한다.
- 표현 ON/OFF와 soil ON/OFF를 독립화한다. 기존 맵 저장값의 의미를 보존하고 새 맵에서만 명시적으로 선택한다. Dedicated는 메시/재질을 로드하지 않는다.
- §3.1의 셀 snapshot과 안정 ID, capacity 반영·정량화 규칙을 구현한다. 우선 제한된 테스트 구역에서 서버 직접 snapshot과 같은 소비자를 사용한다.
- 외형 프로필은 메시·재질·피복/높이·거리 설정만 소유한다. 서버 growth/capacity와 섞지 않는다.

**단계 테스트**: 동일 seed/환경의 새 실행끼리 표현 ON/OFF를 비교하고 food·섭식·Native 결과가 같음을 확인한다. soil OFF+표현 ON에서도 food는 표시되고 수분은 미지원임을 확인한다. 서로 용량이 다른 셀의 같은 잔량 비율/같은 절대량 비교, 0·미세 잔량·만량·잘못된 수치를 검사한다.

**완료 기준**: 외형 토글로 생태 궤적이 바뀌지 않는다. snapshot은 authoritative 완료 상태만 읽는다. 기존 V1/v3 모델·생태 수치에 임의 변경이 없다.

### P3 — 셀 내부의 안정적인 풀 위치와 지면 배치

**작업**

- 셀 안에 고정 후보를 생성하고 간격·회전·크기 편차를 준다. 후보 순서는 잔량에 따라 보일 subset을 안정적으로 선택하도록 고정한다.
- 지역 경계/절벽/수면/장애물/도로·건물 제외 영역을 구분한다. 단순 수직 trace가 바위·지붕을 땅으로 오인하지 않도록 허용 표면/채널 규칙을 시험한다.
- 렌더 후보 지면 조회는 시간·개수 예산을 적용하고 캐시한다. 지면 미준비는 대기→재시도 상태로 처리한다. 화면 외 구역도 기존 생태 입력은 지속한다.
- 생태적 제외 영역이 필요하면 owned habitat authoring에 명시하고 기존 habitat 조정/환경 손실 거래로 적용한다. 제거 시 용량만 복구하고 food를 즉시 채우지 않는다. 변경 전후 중복 손실을 방지한다.
- 부분적으로 막힌 셀의 사용 가능 면적을 정한다. 후보가 없다는 렌더 결과로 Cap를 역산하지 않는다. 지역 전체 capacity=0은 현재 거래가 거절하므로 초기 범위에서는 변경 전에 거절하고 이유를 표시한다.
- 계획된 수원 디버그를 이 단계에서 추가한다. 선택 셀에 대응하는 owned 시험 habitat의 공급 연결을 바꾸며 위치/수면/상승 범위를 검증하고 Ground/Habitat revision으로 반영 여부를 표시한다.

**단계 테스트**: `셀 테두리/후보 위치 표시 → 카메라 이동·복귀 → 동일 seed 재시작`. 수원 연결 ON/OFF와 배치 제외 영역 등록/제거를 시험한다. 늦은 지형 로딩·경계·급경사·바위/지붕·수면 높이·안전 재시도를 자동/장면 시험으로 분리한다.

**완료 기준**: 동일 layout의 후보 ID/XY가 반복 실행·Client 사이에서 같다. 허용 표면에 바닥이 정렬되고 변경 없는 셀에서 위치가 재추첨되지 않는다. 수원 연결은 실제 soil 입력까지 추적된다.

### P4 — 풀밭 밀도·성장·고갈의 시각 연결

**작업**

- 셀당 여러 풀을 ISM에 묶고 capacity/food로 피복·높이를 표현한다. 수분/스트레스는 기존 재질 입력으로 색에 반영한다. 먹이량과 건강색은 서로 다른 정보다.
- Grass/Riparian/Shrub 외형을 소유 에셋/프로필로 연결한다. 바람·alpha·normal을 유지하고 원본 팀 재질을 수정하지 않는다.
- stable 후보→ISM index 매핑, 변경분 갱신, 제한된 생성/삭제 예산을 구현한다. 전체 ClearInstances 반복을 제거한다.
- 경계 부근에서 풀이 반복 등장하지 않도록 표시 임계값/보간을 설계한다. 0잔량을 오래 풍성하게 보여주는 보간은 금지한다. 정량화·보간의 최대 시각 지연을 계측한다.
- `실제 소비량`, `성장량`, `환경 손실`을 셀/지역 진단에 구분한다. 부족한 셀별 진단은 기존 writer에 읽기용 누적 계측으로 추가하며 별도 지급 계산을 하지 않는다.

**단계 테스트**: P1의 건조→회복 강수, P3의 수원 연결을 반복한다. 별도 재시작의 실제 사슴 시험에서 섭식 발생 셀의 food와 외형 감소를 확인한다. 순변화는 성장 때문에 증가할 수 있으므로 소비 누적과 수지를 함께 판정한다.

**완료 기준**: 고갈 셀의 먹이 풀은 표시 정책의 제한 시간 안에 사라지고, 회복 시 같은 후보 자리에서 돌아온다. 기존 장식 풀이 남아서 고갈을 가리는지 owned 시험 구역을 검수한다. 실제 섭식이 안 일어난 실행은 성공으로 처리하지 않는다.

### P5 — 주변 구역 전송·멀티플레이·성능

**작업**

- 큰 region Actor 하나의 원점 relevance에 의존하지 않고 spatial chunk 단위 transport를 설계한다. 기존 네트워크 계약과 충돌 없이 chunk Actor 등 Unreal의 공간 relevance를 사용하며 Subsystem 자체를 복제하지 않는다.
- 초기 full snapshot과 변경 셀/제거 항목, sequence/epoch/grid revision을 구현한다. 신규/늦은 접속·관심 구역 재진입 시 현재 상태로 재동기화한다.
- cell capacity/plant/ground 변경도 전송한다. 없는 데이터와 food=0, pending-ground를 구분한다. 오래된 메시지·다른 epoch·불완전 baseline을 적용하지 않는다.
- client는 주변 풀 후보만 만들고 먼 곳은 LOD/표시 예산을 적용한다. cull은 생태 상태를 제거하지 않는다. 서로 다른 그래픽 품질에서도 수신 food는 같다.
- 실제 측정 후 정량화·전송 간격·chunk 크기·최대 인스턴스·캐시 예산을 확정한다. 전체 grid를 매 frame 모든 Client에 전송하지 않는다.

**단계 테스트**: Dedicated+Client2에서 서버 강수/기온을 변경하고 같은 셀 snapshot을 비교한다. 늦은 접속, 구역 이탈·재진입, 지형 스트리밍, 지연/손실 시험을 추가한다. 사용자 단독 PIE에서는 진단 패널의 변경 셀 수·표시 수·전송 지연을 확인한다.

**완료 기준**: Client에 권위 FoodGrid/Native step이 생기지 않고 두 Client의 해당 revision 값이 일치한다. Dedicated에 시각 인스턴스/메시 로드가 없다. 고정된 장면·해상도·장비 조건의 before/after 보고서와 성능 상한이 있다.

### P6 — 통합 회귀·사용자 간편 시험·인수인계

**작업**

- 테스트 패널에 `건조 → 회복 관찰` 순차 시나리오와 저장 기능을 제공한다. 지역 자동 선택 조건과 준비 실패 이유를 표시한다. 생태계의 먹이를 직접 늘려 시험 결과를 만들지 않는다.
- 사용자는 맵 열기→Play→패널 열기→지역 선택→시나리오 실행으로 시작할 수 있어야 한다. 완료/실패/관찰 중/준비 필요를 명확히 구분한다.
- 실제 운영과 가까운 기존 동물 동시 실행, 장시간 재생/고갈, 맵 teardown, 에셋 cook·Development 패키지, 기존 저장/재시작 회귀를 확인한다.
- 문서의 예정 명령/버튼을 실제 명칭으로 바꾸고 스크린샷·재현 결과·알려진 한계·다음 할 일을 기록한다. 원본 팀 맵으로 확대 적용은 별도 범위로 남긴다.

**단계 테스트**: [사용자 안내](FOOD_GRASS_TEST_GUIDE_20261108.md)의 각 시나리오를 처음부터 실행한다. 명령 없이 UI만으로 가능한지, 실패 시 사용자에게 조치가 표시되는지 확인한다.

**완료 기준**: 수동 환경 조작→토양→실제 먹이→풀→Client 표시의 연결을 같은 실행 증거로 추적할 수 있다. 미실행 시험은 미실행으로 남기며 과거 225개 테스트 결과를 이번 성공으로 재사용하지 않는다.

## 5. 디버그 UI·명령의 구현 계약

아래 이름은 **제안 이름**이다. 구현 중 확정하며 존재 여부를 검사한 후 사용자 안내에 승격한다. 공통 prefix `eco.Grass.*`의 중복 등록부터 확인한다.

| 예정 버튼/명령 | 의미 | 제공 단계 |
|---|---|---|
| `eco.Grass.Debug 1` | 현재 화면에 패널/범례 표시. Client는 수신 상태만 표시 | P1 |
| `eco.Grass.Test.Begin <RegionId>` | 선택 지역의 수동 환경 override 시작 | P1 |
| `eco.Grass.Test.Climate <Rain01> <TemperatureC>` | 활성 시험 지역의 실제 기후 입력 변경, 기온은 soil 허용 범위까지 검증 | P1 |
| `eco.Grass.Test.Preset Dry / Recovery` | 건조/회복 기후 프리셋. 먹이 직접 변경 없음 | P1 |
| `eco.Grass.Test.End` | override 해제·정상 자동 환경으로 복귀 | P1 |
| `eco.Grass.Test.Export` | 상태/입력 이력·수지·시간·build/seed/flags를 JSON 저장 | P1, 단계별 확장 |
| `eco.Grass.Cells 1` | 선택 지역 셀 경계와 현재량/용량/유효성 표시 | P2–P3 |
| `eco.Grass.Visual 0 / 1` | 외형만 OFF/ON. 생태/지면 계산 유지 | P2 |
| `eco.Grass.Test.Water <HabitatId> 0 / 1` | 등록된 owned 시험 수원의 실제 공급 연결 변경 | P3 |
| `eco.Grass.Test.Run DryRecovery` | 조건 확인 후 건조/회복 순차 실행·판정·결과 저장 | P6 |

시각 토글은 로컬 표시 상태이고 기후/수원 제어는 권위 World에만 적용한다. UI에 현재 World/NetMode/Region/시험 활성 여부를 항상 표시한다. 명령 인자 생략으로 모든 지역을 바꾸지 않는다.

### 5.1 환경 프리셋과 기다리는 시간

- 초기 시험 후보: Dry=`Rainfall 0, Temperature 30℃`, Recovery=`Rainfall .5, Temperature 20℃`. 현재 soil 계수 기준 검증을 거쳐 실제 값을 확정한다. 무조건 초당 food 증가/감소를 보장하는 숫자로 설명하지 않는다.
- 초지·침수 없음·정상 지면·물 공급 분리·capacity>0 셀에서 무동물 기준을 먼저 만든다. 지역마다 cap와 기존 수분이 다르므로 서로 다른 지역의 절대 food만 단순 비교하지 않는다.
- HUD에 즉시 적용 확인, 수분 변화 확인, food 변화 확인을 따로 보여준다. 기후 변경은 즉시 풀을 채우는 동작이 아니다.
- 최소 관찰 기간·변화 문턱·timeout은 P1에서 현재 계수로 측정해 확정한다. 사용자가 기다릴 시간을 안내서에 simulation seconds와 예상 wall seconds로 함께 기록한다.
- 가속이 필요하면 기존 fixed-step benchmark/실행 경로를 먼저 확인한다. 모든 관련 생태 clock과 receipt를 함께 진행할 수 있음이 검증된 개발 runner만 사용한다. 큰 dt 주입·food 강제 세팅·soil만 여러 번 갱신으로 빠른 시연을 만들지 않는다. 대화형 가속은 필수 완료 조건이 아니다.
- 관찰 시간이 끝나도 조건이 없으면 실패/관찰 불충분으로 기록한다. food 감소를 재현하려고 사용자 모르게 동물을 굶기거나 잔고를 제거하지 않는다.

### 5.2 환경 시험과 강제 fixture 분리

기존 `ApplyFoodFractionForAudit` 계열의 가뭄 fixture는 실제 먹이를 제거하거나 재생을 중지하는 별도 시험이다. 일반 “건조” 버튼에서 호출하지 않는다. 0잔량·경계값 자동화가 필요하면 독립 테스트 세계에서 명시적인 fixture로 준비하고 receipt 및 실행 조건에 표시한다. 런타임 UI에 Food=100% 버튼은 이번 기본 범위에 포함하지 않는다.

## 6. 자동화·성능·판정 기준

| 시험 묶음(예정) | 핵심 검증 |
|---|---|
| `AdaptiveEcosystem.Grass.Debug` | 입력 거절·권위·World 격리·writer override·복귀·teardown |
| `AdaptiveEcosystem.Grass.Contract` | Food/Cap/정량화·0·capacity 변경·순서·생태 OFF 회귀 |
| `AdaptiveEcosystem.Grass.Placement` | seed 안정성·경계·지면·제외·streaming·후보 매핑 |
| `AdaptiveEcosystem.Grass.Visual` | instance 유지·food=0·재성장·renderer OFF 비간섭 |
| `AdaptiveEcosystem.Grass.Network` | full/delta·epoch/revision·late join·relevance·Client 무권위 |
| 기존 Vegetation/Policy/SpatialFood/저장/통합 회귀 | 기존 모델·수지·기능 OFF·단일 writer 보존 |

- 원칙적으로 기존 `CommitSpatialFood`의 수치 허용 오차를 그대로 검사한다. double grid와 float 지역 Summary는 별도 정밀도로 비교하고 정확히 같은 값이라고 요구하지 않는다.
- 동일 revision에서 server encode→client decode는 명시한 정량화 오차 이하여야 한다. 양자화 범위를 벗어난 값은 조용히 clamp하지 않고 원인을 기록한다.
- 표시 지연 초안: 정상 로컬 실행에서 서버 게시 완료부터 0잔량 외형 반영까지 2초 이내. 신규 지면 준비/관심 구역 진입은 별도 측정한다. P0/P1에서 최종 수치를 확정하고 문서에 변경 이유를 남긴다.
- 메모리는 FoodGrid(보조 버퍼 포함), 지면/후보 캐시, 서버 transport, client instance CPU/GPU를 분리한다. Mass Entity 전환을 절감 근거 없이 도입하지 않는다.
- 성능 gate는 P0 장비·목표 instance/region/client 수 기준으로 P2 전에 수치 확정한다. 평균뿐 아니라 p95/max, 늦은 접속 burst/프레임 hitch, 10회 구역 왕복 후 캐시 상한을 기록한다. 현재 계획은 실측된 성능 보장을 의미하지 않는다.
- 운영 관찰과 fixture/정책 강제 시험을 분리한다. 사슴 실제 섭식 시험은 LastIntake/Consumed 증거를 필수로 하고, 성장과 소비가 함께 있는 순 food 변화만으로 판정하지 않는다.

## 7. 빌드·증거·단계 완료 기록

- C++/빌드 입력 변경 후 직접 `UnrealBuildTool.exe AdaptiveEcosystemEditor Win64 Development`를 실행해 완료를 기다린다. [기존 helper](../../Tools/Integration/build_integration_milestone.ps1)는 실제 실행 전 다시 읽고 해당 규칙대로 사용한다.
- UBT/dotnet/Unreal Editor/Live Coding/MSBuild/ShaderCompileWorker 실행 중에는 새 빌드를 시작하거나 기존 프로세스를 중단하지 않는다. 외부 엔진 캐시 쓰기 권한을 확보한 실행 환경을 사용한다.
- 단계에 맞는 의미 있는 테스트를 실행하고 통과 후 이유 없이 반복/확대하지 않는다. 최종 단계에서 관련 통합 회귀·멀티·cook를 수행한다.
- 원시 로그/CSV/JSON은 `AdaptiveEcosystem/Saved/FoodGrass/<RunId>/` 아래 둔다. 공유 가능한 작은 결과 요약만 `Docs/Architecture/Evidence/`에 명시적으로 추가한다. 개인 발표 산출물은 저장소에 넣지 않는다.
- 실행 manifest에 SHA와 dirty 여부, 맵, 모델/backend/flags, seed, WorldEpoch, 시각 layout version, grid/cell 단위, 입력 이력, simulation/wall 시간, 기기·해상도·인스턴스·클라이언트 수를 남긴다.
- 본 계획 작성은 문서 작업이다. 새 UBT/PIE/네트워크/메모리 측정을 수행한 것으로 기록하지 않는다.

| 단계 | 상태 | 실제 변경/commit | 검증 로그/결과 | 남은 문제/다음 작업 |
|---|---|---|---|---|
| P0 기준 장면 | 기존 맵 기준 확보 | 미커밋 | FoodGrass_20261108_Retry | 전용 복사 맵 계획을 기존 맵 시험으로 변경 |
| P1 환경 디버그 | 기본 구현·실행 검증 | 기존 Region/HUD/명령 확장 | GrassDebugClimate 및 Play Dry/Rain/Auto 성공 | 수원/입력 이력 검증 보완 |
| P2 표현 계약 | 기본 구현 | spawner/Field soil 독립 opt-in | 직접 UBT 성공 | 표현 ON/OFF·soil OFF 회귀 보완 |
| P3 위치/지면 | 기본 구현·fixture/실제 Client streaming 검증 | Field ISM 고정 후보/지면 캐시·기존 Client QA | 실제 ISM 위치 회귀, Travel 안정 방문11/10/11 및 terrain proxy 로드/해제·복귀 통과 | 모든 지형 종류·지연 조건까지의 범용 검증은 아님 |
| P4 시각 연결 | 기본 구현·실제0/회복 계측 통과 | 기존 재질 redirect·기후 QA 확장 | 기존 맵120초에서236셀의 정확한0/ISM 제거→같은 셀 회복/ISM 복귀, 장부 오차0·Dry/Rain 캡처 확인 | 기존 장식/은신처와 사용자 구분 검수 |
| P5 멀티/성능 | 기본 멀티·CPU/컨테이너·송신/payload 기준선 통과 | 기존 Field FastArray/CSV·읽기 전용 NetAudit/기존 QA 확장 | Client2/late join/반복 streaming 통과. ProfileComplete6583frame. NetAudit190/55 serializer 이벤트·소켓/실제 payload·최신 base 상태 대조 통과 | 전체 GPU/ACK이력/채널 메모리·IP/UDP packet capture·관심 구역 세분화·배포 최종 예산 |
| P6 통합/인계 | 기본 실행 검증 통과·보완 중 | 기존 사용법과 PROGRESS 기록 | 자동화233 성공+2 경고, 실패0, Game UBT/cook/패키지90초 정상 종료 | 경계값/배치/성능·UI 검수 |

## 8. 다음 개발 채팅에서 사용할 요청

> Root AGENTS.md와 PROJECT_CONTEXT.md를 읽고 FOOD_GRASS_IMPLEMENTATION_PLAN_20261108.md의 단계 기록을 확인해 주세요. 현재 branch/HEAD와 기존 미커밋 변경을 보존하고 첫 미완료 단계부터 진행합니다. 서버 FoodGrid/M4 단일 자원 경로를 유지하며, 사용자에게 각 단계의 디버그 환경 시험이 가능한 상태로 연결해 주세요. 환경 조작과 먹이 강제 제거 fixture를 구분하고, 완료한 단계만 실제 빌드·시험 근거와 함께 기록합니다. FOOD_GRASS_TEST_GUIDE_20261108.md의 예정 명칭을 구현된 조작법으로 갱신하고, 미검증 사항은 그대로 남겨 주세요.
