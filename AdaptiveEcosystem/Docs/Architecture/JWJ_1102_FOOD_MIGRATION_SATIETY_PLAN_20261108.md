# JWJ 1102 먹이·풀·사슴/늑대 이주·포만 행동 개발 계획

2026-11-08 사용자 요청에 따른 **후속 구현 계약과 테스트 계획**. 최초 계획 작성 이후 4지역 저작과 풀 설정을 적용했다. 기준은 `jwj-1024`, `395992ab`와 현재 미커밋 작업 트리다. 재개할 때 실제 Git diff를 다시 확인한다.

대상은 기존 `/Game/JWJ/1102_Integration_JWJ`다. 새 레벨·게임모드·플레이어를 만들지 않는다. 기존 Field/ISM, Region, spawner, Native backend, Migration, Inspector를 확장한다. 이번 사용자 지정은 이 레벨을 후속 적용 대상으로 삼는 근거이며 다른 팀 맵 변경으로 확대하지 않는다.

## 0. 4지역 저작과 JYU 풀 설정 적용

후속 사용자 요청으로 1102의 기존 `JWJ_WildlifeTest`와 `JWJ_HuntingMeadow`를 유지하고, `JWJ_SouthRange`와 `JWJ_WestRange`를 추가했다. 아래 좌표는 월드 XY이며 각 중심은 기존 WildlifeTest 기준 150m 떨어져 있다.

| 지역 | 중심 XY (cm) | 상태 |
|---|---:|---|
| `JWJ_WildlifeTest` | (0, 0) | 기존, 이주 경로의 연결점 |
| `JWJ_HuntingMeadow` | (15000, 0) | 기존 동쪽 지역과 양방향 경로 |
| `JWJ_SouthRange` | (0, -15000) | 신규, 남쪽 양방향 경로 |
| `JWJ_WestRange` | (-15000, 0) | 신규, 서쪽 양방향 경로 |

신규 지역별 49개 지면 점과 29개 경로 점을 검사했다. 기존 스포너의 Field Class를 JYU의 `BP_JYU_VegetationField`로 지정했다. 공유 GrassA 메시·`MI_JYU_EcosystemGrass`·280cm 폭·60cm 높이·150m 상세 반경·셀당 후보 9개가 적용된다. 새 지역의 토양은 JYU의 `BP_JYU_GrassHabitat`를 참조하고, 기존 두 지역의 토양은 그대로 사용한다. 사슴 무리 이주 옵션을 켰다. 저작 도구는 [setup_jwj_1102_food_grass.py](../../Tools/Editor/setup_jwj_1102_food_grass.py)다.

에디터에서 지역 이름을 World Outliner로 찾고, 각 지역 가까이에서 `eco.Grass.Visual 0` → `eco.Grass.Visual 1`을 실행해 먹이 풀의 숨김과 복귀를 확인한다. 단계별 실제 실행 결과는 [PROGRESS.md](../../../PROGRESS.md)에 기록한다.

## 1. 목표와 완료 조건

1. 지역 서버 먹이가 실제 풀의 양으로 표시되고 사슴의 실제 섭식이 같은 먹이를 차감한다. 플레이어 위치/카메라에 따라 표현 비용을 줄이되 화면 밖에서도 생태계는 진행한다.
2. 먹이가 지속적으로 부족해진 지역의 사슴 무리가 유효한 인접 경로를 따라 더 적합한 지역으로 이동한다. 실제 도착과 인구 장부까지 일치한다.
3. 사슴을 찾지 못하는 늑대는 목격/흔적/기억에 근거해 사슴이 이동한 방향을 추적하고 지역 경계를 넘을 수 있다. 사슴의 전역 실시간 위치를 몰래 읽지 않는다.
4. 충분히 먹은 사슴은 계속 조금씩 먹는 대신 휴식·경계·탐색 등으로 전환하고, 충분히 먹은 늑대는 계속 사냥하지 않는다. 다시 배고파지면 섭식/사냥을 재개한다.
5. 위 네 흐름을 **1102 레벨 자체**에서 Standalone 및 Dedicated+Client 2/late join으로 확인한다. 기존 JYU 맵 통과를 이 레벨 통과로 대체하지 않는다.
6. 단계별 환경 디버그, 실제 행동 이유, 수치/ID/이주 거래를 기존 HUD·JSON으로 확인하고 종료/복귀할 수 있다. 최신 빌드·관련 자동화·저장/재시작·패키지 검증까지 기록한다.

## 2. 확인한 현재 구현과 아직 남은 차이

| 항목 | Source/기존 기록에서 확인 | 후속 필요 사항 |
|---|---|---|
| 1102 기존 구성 | 11-06 기록과 `setup_player_hunting_ecosystem.py`에 `JWJ_WildlifeTest` ↔ `JWJ_HuntingMeadow`, 기존 Field BP, 토양, 양방향 route가 있다. 당시 life/vegetation/journeys/combat ON, waves OFF | 현재 저장된 Actor/BP·override·실제 플레이 인원 재감사. 스크립트가 있다는 이유로 현재 저장본을 확정하지 않는다 |
| 풀과 먹이 | `AEcoVegetationField`는 서버 FoodGrid를 Fast Array로 보내고 결정적 후보 위치의 ISM을 갱신. 실제 섭식→0→회복은 기존 JYU 시험에서 확인 | 1102의 BP override/메시/재질/지면/표현 거리와 같은 결과 확인 |
| 플레이어 관심 범위 | `RefreshVisuals/RefreshPlants`가 첫 로컬 플레이어의 카메라 위치에서 near/coarse/cull을 계산. Field 네트워크 relevance는 지역 경계까지의 거리 기준 | 카메라 방향은 현재 후보 선택에 사용하지 않는다. 화면 밖 렌더링 제거와 후보 생성/갱신 절약을 구분해서 검증/보강 |
| 사슴 이주 | `UEcoHerdMigrationSubsystem`에 부족 지속·무리 계획·경로·휴식/실패/복귀·실제 Native context 인계가 있음 | 1102의 실제 도착은 과거 기록상 미검증. 배부른 무리의 선제 이동 조건 보강 필요 |
| 늑대 지역 추적 | 현재 무리 이주 질의는 `FEcoHerbivoreBodyV3Fragment`를 요구. Native 늑대의 지역 내 감지/추격은 존재 | 늑대에 초식 Fragment를 붙여 해결하지 않는다. 늑대용 의도와 실제 context 이동을 기존 경로에 확장해야 함 |
| 사슴 섭식 | C4에서 대사를 뺀 뒤 `EatWant`로 부족분을 먹음. 배부를 때 식사를 끝내는 별도 지속 상태가 이 경로에는 없음 | 섭식 시작/중단의 다른 기준, 최소 유지 시간, 대체 행동 필요 |
| 늑대 포만 | `WildSatiation` 통합 기본 1, 식사 cooldown 뒤 SatLeft 동안 사냥 금지. life 모드 표시 Energy는 `Individual.Nutrition`에서 옴 | 영양량·포만 타이머·사냥 허용을 함께 진단하고 결합. 두 값이 이미 같은 판단 기준이라고 설명하지 않음 |

1102 과거 1,800 simulation seconds 비교에서는 자연 부족→이주가 발생하지 않았고 입출 장부는 0이었다. 과거 진단의 “PlayerStart 없음”은 이후 authoring 기록보다 이전 정보다. 어느 쪽도 현재 저장본 확인을 대체하지 않는다. 기존 setup 스크립트는 공격 에셋·스폰 설정도 바꾸므로 **레벨 점검 용도로 재실행하지 않는다**.

## 3. 에너지 100 근처에서도 먹는 이유와 해결 방향

### 사슴

현재 `EcoRepertoire.h::EatWant`는 대사 후 부족 에너지를 먹이 단위로 바꾼 뒤 섭식 속도로 제한한다. 즉 에너지가 1.0이어도 다음 스텝에 대사로 0.99가 되면 GRAZE 실행 중 부족분을 다시 먹을 수 있다. 표시 반올림까지 겹치면 계속 100처럼 보인다. 이것은 최대치를 넘어 무제한 흡수하는 문제와 다르지만, 거의 항상 풀을 뜯는 행동을 만들 수 있다.

`WildReserveStep`은 에너지와 별도 비축량을 관리한다. 따라서 에너지만 보고 모든 섭식을 막기 전에 E/Reserve/실제 LastIntake를 같이 확인해야 한다. GRAZE 요청·먹는 애니메이션·실제 섭취량도 서로 구분한다. 사용자 장면의 정확한 원인은 해당 개체 기록으로 확정한다.

제안은 기존 개체 상태에 **섭식 필요 상태**를 추가하는 것이다. 배고픔 진입값과 포만 종료값을 다르게 두고(히스테리시스), 안전한 최소 휴식 시간을 둔다. 예를 들어 E≤0.65에서 먹기 시작해 E≥0.90이고 비축 목표를 충족하면 멈추는 값은 시험용 후보일 뿐 확정 기본값이 아니다. E가 높은데 비축이 낮을 때에도 별도 제한된 보충 조건·섭식 상한을 두며 무한 섭식의 예외로 만들지 않는다. 기존 비축 회계가 실제로 이를 지원하는지 먼저 대조한다.

멈춤은 먹이 소비만 0으로 하는 것으로 끝내지 않는다. 기존 행동 목록의 휴식/경계/탐색 의도로 전환하고 실제 행동·애니메이션도 맞춘다. 위협 회피와 긴급 생존은 휴식보다 우선한다. 자연 대사는 계속 진행하므로 다시 배고파지면 식사를 재개한다. 이주 판단은 현재 배고픔과 별개로 지역 자원의 지속 가능성을 본다.

### 늑대

기존 포만 타이머는 재사용한다. 현재 통합 설정의 기본 설명은 식사가 끝난 뒤 약 60초 동안 사냥하지 않는 것이다. 실제 시간은 DayPeriod/설정에 따라 확인한다. life 모드의 영양량은 화면 Energy에 반영되지만 Native 사냥 가능 여부는 cooldown/포만/수면/피로 등의 조건으로 정해진다. **높은 영양량이 곧 사냥 중단을 뜻하지 않는다.**

제안은 기존 Nutrition과 SatLeft를 함께 써서 사냥 시작/중단 기준을 만드는 것이다. 포만 중에는 포획을 시도하지 않고 쉬거나 천천히 이동한다. 플레이어에 대한 방어/전투 의도는 먹이를 위한 사냥과 구별하며 기존 전투 계약을 보존한다. 포만이더라도 사냥터가 비었다는 최근 증거가 있으면, 휴식 뒤 비사냥 이동으로 재배치할 수 있다. 이주는 먹기와 동일한 행동이 아니다.

추가로 life 경로에는 현재 `N>8 && HuntWindowCaptures<2`인 지역 단위 사냥 제한이 있다. 이것은 개체의 배고픔과 다른 생태 보호 조건이다. 사슴이 1~8마리 남았는데 사냥을 안 하는 상태를 “포만”이나 “사슴 없음”으로 오진하지 않도록 이유를 표시하고, 기존 조건을 포만 구현 과정에서 조용히 제거하지 않는다.

### 학습 계약

Raw PPO 요청은 보존하고 실제 실행이 달라진 이유를 별도 기록한다. 사슴 V1/v3 관측·행동 차원을 임의 변경하지 않는다. 우선 기존 실행 훅에 명시적 opt-in 생활 규칙을 연결한다. 이것도 학습 세계 변경이므로 Python mirror·경계 golden 검증을 동반하고 ON 세계의 학습/장기 궤적 동등성은 별도 과제로 남긴다. 늑대의 현재 Native FSM을 PPO 학습 완료로 설명하지 않는다.

## 4. 확장 구조와 책임

- 설정: 기존 spawner/종 profile/Field BP에 적합한 설정 묶음을 추가한다. 식성·능력·backend로 분기하고 RegionId/종 이름 문자열을 런타임 분기값으로 하드코딩하지 않는다. 아래 새 설정 이름은 제안이며 아직 속성이나 명령으로 존재하지 않는다.
- 개체 상태: 기존 Mass fragment/Native body에 배고픔 latch, 전환 시각, 사냥 필요, 추적 증거 참조 등 최소 데이터만 둔다. 공유 DA에는 개체 상태를 쓰지 않는다. 식물마다 논리 Entity/먹이 장부를 만들지 않는다.
- 의도: 기존 Migration/Travel을 재사용해 목표·이유·경로를 만든다. 새 Tick manager나 별도 BP 위치 보정은 만들지 않는다. 초식/포식 실행 adapter는 각 backend 상태를 보존한다.
- 실행: Native Step만 이동·섭식·대사를 갱신한다. 이주 인계는 완료된 M4 경계에서 StableAgentId·월드 위치·생명/영양·기억을 보존하고 기존 receipt로 개체군을 한 번만 변경한다.
- 표현: 기존 Field/ISM과 Inspector를 확장한다. 화면 밖은 풀 렌더링만 줄이며 FoodGrid·섭식·이주를 중단하지 않는다. Dedicated에는 렌더 인스턴스를 만들지 않는다.
- 저장/네트워크: 새 지속 상태는 기존 checkpoint 버전/호환 정책과 복원 검증에 반영한다. Client는 요약만 받고 논리 판단/자원 writer를 갖지 않는다. 이주 중 사망/저장/복원·late join의 중복 인구·중복 개체를 검사한다.

## 5. 단계별 구현과 통과 기준

### A. 1102 저장본과 실제 실행 기준선 — 다음 개발의 첫 작업

기존 레벨을 읽기 전용 감사한다. WorldSettings의 GameMode, 기존 Player/카메라·HUD, runtime 개수/설정, RegionId·인접성, FoodGrid 범위, Field BP override, 토양/수원/날씨 writer, route/지면/streaming, life/journeys/Native override를 JSON으로 남긴다. 스폰 수는 저작값과 실행값을 둘 다 기록한다. 기존 두 지역 밖에 생태 지역이 더 있으면 전체 목록을 먼저 확정한다.

통과: 중복 runtime/Field·빈 RegionId·유효하지 않은 지면/경로가 없고 두 지역 이상의 실제 서버 자원과 종별 개체를 읽는다. 문제가 있으면 기존 Actor/컴포넌트 설정만 고치고 변경한 값과 이유를 기록한다. 새 레벨/모드/플레이어 생성으로 우회하지 않는다.

### B. 기존 풀 표현의 1102 적용 및 카메라 대응

기존 `BP_JWJ_HuntingVegetation`과 Field 설정을 연결/검증한다. 거리별 상세/간략 표시, 인스턴스 cull, 엔진의 시야/차폐 culling을 먼저 계측한다. 부족하면 기존 Field에 화면 방향을 고려한 후보 갱신 우선순위·시야 여유각·짧은 유지 시간·프레임 예산을 추가한다. 화면 회전 때마다 풀을 전부 제거/재생성하지 않는다. 카메라 방향이 먹이 데이터 전송이나 권위 시뮬레이션을 차단하지 않게 한다.

통과: 지역별 Food/Capacity와 풀 양 일치, 소비/고갈/회복 반영, 제자리 180도 회전·앞뒤 이동·지역 왕복·카메라 변경 뒤 같은 셀의 배치 안정, 화면 밖 섭식 지속. Client 2가 서로 다른 방향/지역을 봐도 각각 표현이 맞는다. 렌더 비용과 지역 전체 DTO 전송 비용은 따로 보고한다. 다중 로컬 플레이어 지원은 현재 첫 카메라 구현과 구별해 범위를 명시한다.

### B-2. 실제 섭식 지점과 풀 패치 일치 — 사용자 피드백 우선 항목

**최신 구현 계약:** [공유 풀 패치·실제 위치 섭식 개발 명세](FOOD_PATCH_GRAZING_IMPLEMENTATION_SPEC_20261108.md)의 S0~S6을 따른다. Smart Objects 플러그인은 도입하지 않고 기존 Native/Field에 검색·예약·접근·도착 소비를 연결한다. 여러 고정 패치의 공간 배분을 채택했으며 아래 단일 군락 제안은 이전 검토 이력이다. 구현/성능 실측은 아직 수행하지 않았다.

2026-11-08 사용자는 사슴이 보이는 풀과 떨어진 위치에서 먹을 때 풀이 사라지는 현상을 보고했다. 현재 Source의 C4는 이동 후 `CellOf(Body.Pos)`로 선택한 셀의 먹이를 차감한다. 기본 셀은 4m×4m이며 개별 ISM이나 입 위치와의 거리 검사가 없다. Field는 같은 셀 중심에서 XY 각각 ±0.42×셀 폭으로 후보를 분산하고, 잔량에 따른 후보 수만큼 0번부터 표시한다. 소비로 수가 줄면 끝 번호 후보가 제거되므로 먹은 개체와 멀리 있는 무더기가 사라질 수 있다. 이 구조는 Standalone에서도 동일하다.

서버가 공유하는 것은 셀 중심·잔량·배치 seed다. 각 풀 후보의 지면 높이는 표시 World에서 다시 검사한다. 원칙적으로 같은 후보의 XY는 재현되지만, 소비 판정은 그 후보를 사용하지 않는다. 서버 게시 주기 1초와 로컬 표시 갱신 0.25초 및 네트워크 지연은 시점 차이를 추가할 수 있다. 사용자 실행에서 Client 후보 좌표나 지면 높이까지 잘못되었는지는 별도 동시 계측이 필요하다.

**이전 검토 이력: 셀별 단일 섭식 군락과 도착 판정. 현재 구현 대상은 위 명세의 다중 고정 패치다.**

- 기존 FoodGrid/Field의 셀별 지면 정보와 공통 배치 계산을 이용해 서버가 유효성을 확인한 섭식 중심/범위를 제공한다. 근거리 풀 무더기를 그 범위 안에 모아 표시한다. 셀당 먹이 잔고는 기존 값을 사용하고 표시 풀마다 독립 Actor/Entity를 만들지 않는다.
- 기존 Native 조향 훅이 음식 탐색 뒤 이 패치를 실제 목표로 삼는다. 사슴의 서버 body/heading과 설정된 입 앞쪽 오프셋으로 섭식 위치를 계산한다. Dedicated의 애니메이션 socket 계산에 의존하지 않는다.
- C4에서 목표 CellId, 유효 지면, 도착 거리·방향·속도와 섭식 의도를 확인한다. 통과한 실제 수요만 기존 같은 셀 분배/소비 경로에 넣는다. 도착 전이나 길이 막힌 동안은 섭취0이며 도달 가능한 다른 패치를 탐색한다. 목표 셀 경계를 넘는 경우도 명시적으로 처리한다.
- 먹는 애니메이션의 방향/머리 위치를 실제 섭식 패치에 맞춘다. 표시 갱신에는 권위 섭식 step/위치 정보를 사용해 개체 표현과 풀 감소의 시점을 대조한다. 숨김·LOD·Client 지형 준비 여부는 권위 소비 조건이 아니다.

단일 군락 방식은 분산된 현재 풀 후보를 작은 범위로 모으므로 분포 외형이 달라진다. 최신 명세에서는 여러 무더기를 유지하기 위해 처음부터 고정 패치와 공간별 배분 상태를 사용한다. 실제로 소비한 패치의 양/외형이 줄고 셀 총량과 패치 배분 합이 일치해야 한다. 동시 소비·성장·환경 손실·저장/복원·late join도 이 배분을 공유한다. 단순히 Client에서 사슴 가까운 풀만 지우는 방식은 사용하지 않는다.

기존 Inspector/Field에 Cell 경계, 섭식 중심/범위, 사슴의 논리 위치/입 기준점, 실제 표시 위치, 목표 CellId/섭취량, 서버 step와 수신 시각을 함께 표시해 확인한다. Standalone와 Dedicated+Client2에서 다음 조건을 검증한다.

1. 같은 셀이어도 섭식 범위 밖이면 LastIntake=0이고 소비량 증가가 없다. 환경 손실은 별도 집계한다.
2. 목표에 도착하고 섭식하는 동안 해당 패치의 먹이/표현만 감소한다.
3. 셀 경계·급회전·이동 중·동시 섭식·표시 OFF·거리 LOD 전환에서도 원격 패치가 섭식 때문에 사라지지 않는다.
4. 지면 미로드/서로 다른 Client 카메라와 지연 조건에서도 논리 FoodGrid/M4 거래와 공통 패치 식별이 일치한다.
5. 기존 R1b 섭식 세계와 다른 도착 규칙은 명시적 설정으로 연결하고 Python mirror/기존 OFF golden 및 ON 규칙 검증을 수행한다.

이번 항목은 Source 원인 감사와 해결 제안이다. 런타임 코드를 수정하거나 새 PIE/네트워크 시험을 실행하지 않았다.

### B-2 후속 조사 메모 — 분산 풀 무더기를 서버와 공유

사용자는 여러 실제 풀 위치에서 섭취하는 모습을 원하며 서버 위치 관리 비용에 대한 공식 근거를 요청했다. 현재 분산은 RegionId/LayoutSeed의 CRC와 CellId hash를 seed로 쓰는 FRandomStream이다. 후보마다 X/Y를 [-0.42,+0.42]×셀 폭에서 뽑고 yaw를 [0,360]에서 뽑는다. 4m 셀에서는 중심 기준 각 축 ±1.68m다. 후보 사이 최소 간격 검사와 3×3 소구역 분할은 없다. 근거리 표시 수는 양수 먹이에 대해 max(1,ceil(9×Density)), 원거리에는 후보0 하나가 남는다. 같은 seed·알고리즘·호출 순서로 후보 XY를 재현할 수 있으나 현재 Z/표시 가능 여부는 각 World의 지면 trace에 좌우된다.

여러 무더기를 유지하는 요구에는 **서버가 관리하는 소수의 식용 패치와 클라이언트 ISM의 공통 PatchId**를 채택한다. 앞의 단일 군락 제안은 검토 이력으로만 남긴다. RegionId/CellId/CandidateId와 배치 버전, 공통 설정으로 위치를 계산하고 서버가 지면/유효성·필요한 높이 보정을 확정한다. 배열 슬롯으로 관리하며 지역 좌표의 FVector3f/양자화 데이터 등을 검토한다. 서버 섭식은 PatchId에 도착한 뒤 확정하고 그 패치의 잔량/표현만 갱신한다. 셀 내부 배분량 합과 기존 FoodGrid/M4 총량이 일치하도록 성장·손실·동시 소비·복원 거래를 연결한다. 렌더 인스턴스 index는 안정적인 게임 ID로 쓰지 않는다.

성능 산술 예시는 현재 저장된 4지역×900셀×9후보=32,400개다. 후보 레코드를 명시적으로16~32bytes로 설계하면 원시 배열 약0.49~0.99MiB다. 실제 UE FVector/FTransform, 배열·지도·예약·복제/체크포인트 부가비용을 포함한 실측값은 아니다. 현재 셀+이웃8셀을 검색하면 최대81후보이며 목표를 유지하는 동안에는 해당 패치만 검사할 수 있다. 주변에 목표가 없을 때의 넓은 탐색도 단계별 예산을 둔다. 지면 검사는 초기 로드/변경 시 캐시하고 한 프레임에 전체 후보를 검사하지 않는다. 위치 캐시가 가볍다는 추정과 전체 기능 성능 통과를 구분한다.

Client는 같은 PatchId를 렌더하며 근거리에서는 사슴이 먹는 패치를 표시한다. 현재 원거리 후보0 통합 표현은 섭식 위치가 화면에 보이는 거리에서는 실제 패치를 가리지 않도록 보완한다. 같은 입력으로 XY가 같더라도 Client별 충돌 지면·설정·버전 차이는 진단한다. 시각 잎의 바람 변형은 패치의 안정적인 지면/섭식 범위를 기준으로 처리한다. 변경 패치와 권위 소비 시점을 기존 Field 전송에 넣고 가까운 활동 패치의 갱신 우선순위를 둔다.

공식 근거와 프로젝트 설계의 구분은 다음과 같다. 아래 자료는 엔진 기능/원리를 설명하며 이 프로젝트의 연산량을 보증하지 않는다.

- [Epic Random Streams](https://dev.epicgames.com/documentation/en-us/unreal-engine/random-streams-in-unreal-engine)는 같은 seed의 난수 순서 재현을 설명한다. 공통 배치 함수와 버전 검증은 프로젝트 적용 설계다.
- [Epic ISM](https://dev.epicgames.com/documentation/en-us/unreal-engine/instanced-static-mesh-component-in-unreal-engine)은 동일 메시의 효율적 인스턴싱과 Per Instance Custom Data를 설명한다. 식용 패치 상태를 각 ISM의 먹힘/높이 표현으로 연결하는 데 사용한다.
- [Epic Networking Overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/networking-overview-for-unreal-engine)는 서버 권위 상태와 Client 표현의 역할을 설명한다. 공통 패치 데이터가 양쪽의 기준이 된다.
- [Epic Smart Objects](https://dev.epicgames.com/documentation/en-us/unreal-engine/smart-objects-in-unreal-engine---overview)는 공간 질의·슬롯 선택/예약·접근 구조를 설명한다. 기존 Native/Field에서 같은 상호작용 순서를 구현하는 설계 근거이며 풀마다 SmartObject를 추가할 필요는 없다.
- [Epic Timing Insights](https://dev.epicgames.com/documentation/en-us/unreal-engine/timing-insights-in-unreal-engine)로 배치 생성·지면 검사·목표 탐색·섭식·전송 관련 CPU 비용을 분리 계측한다. 실제 통과 기준에는 동시 개체 수와 전송/메모리 비용을 함께 기록한다.

이번 조사에서는 Source와 기존 1102 진단 JSON을 확인하고 공식 문서를 읽었다. 새 런타임 코드나 성능 시험은 수행하지 않았다.

### C. 포만·생활 행동과 진단

섭식 위치 일치 요구가 추가되어 앞의 B-2를 먼저 구현·검증한 뒤 포만 조건을 연결한다.

E/Reserve 또는 Nutrition, 섭취량, Raw request/executed action, 사냥 cooldown/SatLeft, 전환 이유를 기존 Inspector에 모은다. 기존 설정을 읽는 생활 규칙과 C4 섭식/ThreatInput 사냥 gate를 연결한다. 최소 유지 시간·재개 기준·긴급 예외를 설정화한다. 기준을 억지로 맞추려고 기본 에너지 소모/먹이 생산량부터 바꾸지 않는다.

통과: 배고픔→식사→포만→비섭식 행동→자연 대사→다시 배고픔이 적어도 2회 반복된다. 안전한 포만 구간에는 LastIntake=0/신규 포획=0이고 에너지가 자연 감소한다. 비축 보충 예외는 별도 이유/상한으로 증명한다. 위협 회피·수면·번식 비용·저장 복원도 회귀 확인한다. 변경 OFF의 기존 golden 결과를 보존한다.

### D. 사슴의 지속적 부족→실제 이주

2026-11-09 사용자 후속 요구의 상세 구현 계획은 [지역 생태 기반 사슴 순차 이주](REGIONAL_DEER_MIGRATION_PLAN_20261109.md)를 우선한다. 지역 등록 배열 순서로 개별 승인하고, 생태 목표 인원·최소 잔류·부족 기간 누적 승인 한도·목적지 예약으로 추가 이주를 멈춘다. 아래 최소 2마리 제한은 현재 구현의 결함/제약 설명이며 새 자격 조건이 아니다. 현재 문서 계획만 작성했고 런타임은 미변경이다.

기존 기본 조건은 먹이 비율 25% 미만 8초이며, 아직 굶주린 구성원이 없고 먹이 비율이 5% 이상이면 출발하지 않는다. 이번 목표를 위해 **개체의 현재 허기와 지역 자원 부족을 분리**한다. 기존 설정에 자원 부족 지속/회복 기준·출발 cooldown을 두어 배부른 사슴도 곧 고갈될 지역을 떠날 수 있게 한다. 목적지 먹이/수용량/위험·정보 신선도·유효 경로 조건은 유지한다.

기존 구현은 최소 2마리 무리를 요구한다. 단독 생존 개체도 굶지 않게 같은 Travel 경로로 fallback을 설계/검증한다. 알 수 없거나 막힌 목적지는 실패 이유를 남기고 재시도/복귀하며 순간이동하지 않는다. 1102 기존 route를 먼저 사용하고 추가 지역 연결이 필요하면 같은 route 클래스/설정으로 확장한다.

통과: 자연 환경 변화 시험과 명시적 부족 fixture를 분리한다. 같은 StableAgentId가 실제 경로를 지나 목적지 Native context로 넘어가고 MigrationIn/Out·종별 인구·에너지/비축 보존이 일치한다. 잠깐의 부족은 출발하지 않고 회복 경계에서 왕복 진동하지 않는다. 만복 무리·단독 개체·경로 없음·목적지 고갈·이동 중 사망을 각각 확인한다.

### E. 늑대의 증거 기반 추적 이주

지역 서버의 사슴 0은 테스트 정답으로 사용하되 늑대의 즉시 전지적 목적지 정보로 쓰지 않는다. 기존 감지/경험/흔적 저장을 감사한 뒤 재사용한다. `ObservedAt`, 출처, 마지막 위치/진행 방향, 신뢰도, TTL, 알고 있는 경로를 구분해 유효한 정보가 있을 때 추적 이동 의도를 만든다. 사슴이 잠시 가려진 상태와 충분히 찾았지만 없는 상태를 다르게 처리한다.

최근 사슴의 이동을 목격하거나 유효 흔적을 얻은 늑대는 해당 인접 경로로 이동한다. 증거가 없거나 만료되면 마지막 위치 탐색→알려진 경로 탐색/휴식으로 전환하며 정답 지역으로 자동 유도하지 않는다. 포만 상태에서는 사냥하지 않는 재배치, 허기 상태에서는 추적/사냥으로 연결한다. 목표 사망/방향 변경/막힌 길을 처리한다.

기존 Native Threat Step에 이동 의도 소비를 연결하고 stage clamp·지역 로컬 좌표·위협/먹잇감 슬롯·캐시를 안전하게 인계한다. StableAgentId, 영양/HP, SatLeft/cooldown/수면/기억을 보존한다. 지역별 index를 영속 표적 ID로 재사용하지 않는다. 이주 중간에는 한 context만 실행하고 도착 거래는 한 번만 확정한다. 새로운 허기 조건이 기존 플레이어 전투/보호 은신처를 우회하지 않게 한다.

통과: D에서 떠난 사슴을 관측한 늑대가 같은 경로로 따라가 실제 목적지에 도착한다. 출발지 사슴 0·목적지 사슴 존재·늑대 ID와 인구 장부로 대조한다. 화면에서 사슴이 사라졌다는 이유만으로 출발하지 않는다. 증거 없음/만료/거짓 오래된 위치에서는 목적지 정답을 자동 취득하지 않는다. 경로 폐쇄·표적 사망·도중 저장·Client late join도 확인한다.

### F. 기존 디버그로 한 번에 시험하고 회귀 검증

기존 Inspector 환경 패널에 지역 선택, 기준선/가뭄/회복, 현재 실험 단계·취소/복귀와 결과 저장을 확장한다. 기존 명령을 재사용하고 시간·지역·기온/강수·실제 수원 연결값을 설정으로 받는다. 포만/허기는 기본적으로 자연 섭식/대사로 재현하며 빠른 상태 fixture가 필요하면 별도 개발용 조작으로 명확히 표시하고 권위 경계에서만 적용한다.

JSON에 seed/설정, 조작 이력, 단계별 판정, FoodGrid/M4 동기 시점, StableAgentId, 이동 이유/증거 시각, 행동 점유 시간/섭취량/포획량을 기록한다. 토글 전 값 복원과 새 세션 초기화가 가능해야 한다. C++ 변경 후 직접 Editor UBT·관련 식생/이주/생명/Native golden 테스트, 1102 실제 Standalone·멀티·Game 패키지와 장시간 여러 seed 비교를 수행한다. 표본 시간/개체 수/장비/예산을 명시하고 “자연 균형 완성”으로 과장하지 않는다.

## 6. 사용자가 간단히 확인할 순서

**아래 1~3은 현재 존재하는 명령이다. 1102 최신 동작은 재검증 전이며, 4~5는 후속 구현 후 제공할 합격 기준이다.** 임의로 새 명령 이름을 만들어 안내하지 않는다.

1. 기존 1102를 Standalone Game으로 실행한다. `eco.Inspector.Visible 1`로 개체 패널을 켠다. `eco.Grass.Visual 0` → `eco.Grass.Visual 1`로 서버 먹이와 연결된 풀과 기존 장식 foliage를 구분한다. 두 지역을 이동하며 화면 방향도 돌려 본다.
2. `eco.Grass.Climate JWJ_WildlifeTest 0 50`으로 성장 억제 환경을 만든다. 실제 섭식과 먹이 감소를 확인하고 `eco.Grass.Climate JWJ_WildlifeTest 0.5 20`으로 회복시킨다. `eco.Grass.Auto JWJ_WildlifeTest`로 수동 환경을 해제한다. 50℃는 명시적 시험 조건이며 자연 균형 값이 아니다. 실제 고갈/이주 시간은 개체 수·토양·포만 변경에 따라 달라진다.
3. 사슴 이동 경로만 빠르게 확인하려면 **별도 새 Standalone 세션**에서 다음을 사용한다.

   ```text
   eco.HerdMigration 1
   eco.HerdMigration.Debug 2
   eco.HerdMigration.Test.Drought JWJ_WildlifeTest
   ```

   이 fixture는 먹이를 직접 장부 거래로 제거하고 재생 관련 값을 바꾼다. 일반 기후 Auto로 완전 복구한다고 가정하지 말고 **Play를 종료 후 재시작**한다. soil 모드에서 성장 억제가 실제 유지되는지도 검사한다. 정확한 맵 이름 검사 때문에 일반 PIE 접두사에서는 거절될 수 있다. M 및 [ / ]로 계획/실제 이동을 본다. 명령 성공만으로 도착 성공을 판정하지 않는다.
4. C 구현 후: 사슴을 선택해 E/Reserve/LastIntake/행동을 본다. 충분히 먹으면 섭식이 멈추고 쉬거나 경계하며 다시 배고플 때만 먹어야 한다. 늑대는 Nutrition/SatLeft/사냥 이유를 함께 보고 포만 중 신규 포획이 없어야 한다.
5. E 구현 후: 사슴이 떠나는 것을 목격할 수 있는 늑대를 관찰한다. 추적 증거와 목적지가 표시되고 실제 경로를 거쳐 도착해야 한다. 늑대에게 단서를 주지 않은 비교 실행에서는 같은 목적지를 즉시 알아서는 안 된다.
6. 현재 `eco.Grass.Export JWJ_WildlifeTest`는 현재 시점의 풀 진단을 `Saved/FoodGrass`에 저장한다. 전체 입력 이력/추적/포만 단계 자동 판정 저장은 F 완료 후 제공한다. 과거 단일 snapshot을 전체 시나리오 통과 증거로 사용하지 않는다.

## 7. 재개 파일과 검증 근거

| 책임 | 먼저 읽을 기존 파일 |
|---|---|
| 진행 상태/기존 풀 시험 | [루트 PROGRESS](../../../PROGRESS.md), [풀 구현 계획](FOOD_GRASS_IMPLEMENTATION_PLAN_20261108.md), [풀 테스트 안내](FOOD_GRASS_TEST_GUIDE_20261108.md) |
| 1102 기존 authoring/미확인 항목 | [플레이어 사냥 구현·테스트](PLAYER_HUNTING_IMPLEMENTATION_AND_TEST_20261106.md), [기존 설정 도구](../../Tools/Editor/setup_player_hunting_ecosystem.py), [기존 실행 감사](../../Tools/Editor/audit_player_hunting_loop.py) |
| 풀/관심 영역 | [Field.h](../../Source/AdaptiveEcosystem/World/EcoVegetationField.h), [Field.cpp](../../Source/AdaptiveEcosystem/World/EcoVegetationField.cpp) |
| 이주/Native context | [HerdMigration](../../Source/AdaptiveEcosystem/Mass/EcoHerdMigration.cpp), [Migration types](../../Source/AdaptiveEcosystem/Core/EcoMigrationTypes.h), [Integrated subsystem](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.cpp) |
| 섭식/포만/영양 | [Repertoire](../../Source/AdaptiveEcosystem/AI/Policy/EcoRepertoire.h), [WorldV3](../../Source/AdaptiveEcosystem/AI/Policy/EcoWorldV3.h), [ThreatModel](../../Source/AdaptiveEcosystem/AI/Policy/EcoThreatModel.h), [Integrated processors](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp), [LifeHistory](../../Source/AdaptiveEcosystem/AI/Policy/EcoLifeHistoryV3.h) |
| 디버그/설정 | [Inspector](../../Source/AdaptiveEcosystem/Creature/Debug/EcoCreatureInspection.cpp), [환경 명령](../../Source/AdaptiveEcosystem/Debug/EcoEnvironmentDiagnostics.cpp), [Spawner](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.h) |

재개 시 루트 PROGRESS의 실제 검증 결과를 확인해 미완료 단계부터 시작한다. 기존 FoodGrass runtime 감사 도구에는 정확한 1102 경로와 4지역 기준을 추가했다. Client/네트워크 도구는 별도 확장과 재검증이 필요하다. 기존 사용자 공간 탐색 최적화 diff를 보존하며 같은 코드 영역을 덮어쓰지 않는다.

최초 계획 작성 당시에는 Source와 Git diff 및 과거 문서를 대조했다. 후속 1102 적용·실행 기록과 기존 JYU 근거는 PROGRESS에서 구분해 추적한다.
