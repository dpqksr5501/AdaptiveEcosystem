# 1102_Integration_JWJ — 2,000개체를 위한 탐색 비용 절감 구현 계획

작성: 2026-11-06. 상태: **Source 감사에 기반한 구현 제안. 아직 구현·성능 검증하지 않았다.**

사용자 목표: `/Game/JWJ/1102_Integration_JWJ`, 한 레벨 총 2,000개체, 동시 접속 2명, 서버 30Hz, 클라이언트 60FPS. 이번 문서는 전체 최적화 순서 중 **1번: 탐색·반복 조회 비용 절감**의 실행 계획이다. 실제 동작을 유지하면서 검사할 후보와 반복 작업을 줄인다.

## 1. 기준과 범위

- 감사 기준은 `jwj-1024`, HEAD `867d39ed`의 현재 Source다. 사용자 콤보 에셋·문서·Editor 도구의 미커밋 변경은 보존한다.
- [프로젝트 공통 맥락](../PROJECT_CONTEXT.md), [팀 안내](../Team/ECOSYSTEM_AI_COLLABORATION_20261024.md), [Mass 순서](../Mass/MASS_PROCESSOR_ORDER.md), [기존 P3](../Integration/P3_SPATIAL_AND_QUERY_OPTIMIZATION.md)를 따른다. 기존 P3의 2026-10-11 진단을 현재 구현 사실로 복사하지 않는다.
- [현재 사냥 통합 기록](PLAYER_HUNTING_IMPLEMENTATION_AND_TEST_20261106.md)에 따르면 목표 맵은 life·vegetation·journey·player combat을 연결한 경로다. 실행 개체 수는 Native override 영향을 받는다. 문서/에셋의 수량과 실제 스폰 수를 별도로 기록한다. 이번 감사가 해당 맵을 새로 실행한 것은 아니다.
- Native v3의 7.5Hz 고정 스텝, 기존 Raw Request·SocialControl 기본값, 단일 이동/대사 writer, M4 자원/인구 장부, Client authority 0을 유지한다. V1 및 SpeciesAI의 동작을 이번 변경으로 전환하지 않는다.
- 감지 거리·이웃 개수 제한·PPO 모델·시야/청각·포획 규칙·생태 지역 경계·난수 순서·갱신 주기를 바꾸지 않는다.
- 지면 캐시, 물리 Sweep 생략, Simulation LOD, worker 병렬화, Actor/복제 LOD, 스트리밍 통합은 후속 단계다. 이번 단계는 그 측정에 필요한 후보/시간 카운터를 제공한다.
- 실제 2,000개체 맵 시험에는 별도의 규모 제한 확장이 필요하다. 현재 스포너의 512 제한, checkpoint의 개체 1,024행 제한 등을 이번 탐색 패치에서 몰래 해제하지 않는다.

## 2. 설계 결정

**v3의 권위 위치와 계산 단계에 맞춘 엔진 독립 2D 공간 인덱스를 만들고, 원래 배열의 행 번호를 반환한다. 기존 판정 함수는 그 후보에 똑같은 수식·순서로 적용한다.**

첫 구현은 사슴 동족 탐색이다. 그다음 사슴의 위협 관측, 늑대의 표적/포획, 추가 반복 조회를 순서대로 연결한다. 작은 무리·밀집 상황에서는 기존 전체 순회로 돌아갈 수 있게 한다. 공간 인덱스는 게임 상태의 새 소유자가 아니라 버릴 수 있는 작업 캐시다.

선택할 자료구조는 **셀별로 정렬한 연속 배열을 쓰는 균일 격자**다. 초기 구축은 `O(N log N)` 정렬, 조회는 셀 조회+후보 수집+원래 행 순서 정렬이다. 전체 구축/조회/정렬 비용을 측정하며 단순히 O(N)이라고 설명하지 않는다. 2,000개체에서 단순성과 결정성을 우선하고, 측정 결과가 필요성을 입증하면 dense CSR/counting 방식과 비교한다.

## 3. 기존 격자를 그대로 연결하지 않는 이유

[UEcoNeighborhoodSubsystem](../../Source/AdaptiveEcosystem/AI/Policy/EcoNeighborhoodSubsystem.h)은 이미 2D 균일 격자와 반경 조회를 제공한다. 구현 방식·테스트 경험은 재사용할 자산이다. 다만 [Gather](../../Source/AdaptiveEcosystem/AI/Policy/EcoNeighborhoodGatherProcessor.cpp)는 V1 태그와 `FTransformFragment`를 읽고, UObject/UE 자료형에 의존한다.

v3에는 다음 차이가 있다.

| 구분 | 기존 격자 | 이번 v3 인덱스 |
|---|---|---|
| 위치 | 프레임의 UE Transform, cm | 해당 계산 단계의 Native Body/Threat 위치, double |
| 시간 | 프레임 단위 Gather | 사슴 이동 뒤, 관측 직전 등 단계별 구축 |
| 식별 | Entity/StableAgentId | 현재 배열의 OriginalRow, 검증용 ID 매핑 |
| 실행 범위 | World 서비스 | 지역 컨텍스트 소유 작업 버퍼 |
| 엔진 없는 검증 | 직접 사용 불가 | EcoV3Eval·C++ 하네스와 같은 구현 사용 |

단위를 잘못 섞거나 보간 위치를 감각에 넣지 않는다. 신규 모듈·전역 Subsystem은 만들지 않는다. 기존 V1/Social 격자는 유지하고, 추후 별도 회귀가 갖춰질 때 공통 저수준 구현 추출을 검토한다.

## 4. 실제 탐색 지점과 우선순위

| 순서 | 현재 함수/파일 | 현재 작업 | 이번 적용 방법 |
|---|---|---|---|
| A | `EcoObservationV3.h::PerceiveKin` | 각 사슴이 지역 전체 동족 순회 | 최대 시야/분리 반경의 셀 후보, 원래 행 순회 |
| B | `EcoWorldV3.h::ObserveHerb`, `PerceiveThreats` | 위협 전체 순회, 개체별 차폐 계산 | 시야와 청각을 모두 포함한 후보 |
| C | `EcoThreatModel.h::Step` | 늑대마다 전체 먹잇감에서 표적·포획 선택 | 표적용/포획용 후보를 각각 제공 |
| C | `PackPeek`, `NightUpdate` | 미리 보기·밤잠의 먹잇감 조회 | 같은 시점의 Prey 인덱스 재사용 |
| D | `EvidenceThreatHook` | CaptureMask 생성·전수 거리 검사·ID Find | 기존 차폐 검사 반경 후보, 정렬 ID 이진 탐색 |
| D | `JourneyControlHook` | 이주 사슴마다 전체 Deer 순회 | 세계 좌표의 같은 계획 이웃 후보 |
| D | `ProcessNaturalBirths` | 5초마다 부모 후보 쌍 중첩 순회 | 지역/종별 후보 인덱스, 첫 유효 쌍 순서 보존 |
| D | `TallyNearEatingWolves` | 사슴×늑대 근접 진단 순회 | 정확한 진단 시점의 반경 후보 |
| E | Gather·BuildViews·`BuildAgentLookup` | 프레임별 수집·정렬·배열 재구성 | 용량 재사용 및 수명 보장된 조회 개선 |

`PackGoals`는 별도 주의가 필요하다. 현재 도움 가능 여부는 **동료 늑대까지의 거리**가 아니라 **그 동료가 추격하는 먹잇감까지의 거리**로 정한다. 늑대 위치 반경 검색으로 바꾸면 동작이 달라진다. 초기에는 유지하고, 비용이 크면 먹잇감 위치에 `(LeaderRow, PreyRow)` 항목을 둔 별도 인덱스로 최적화한다. 같은 먹잇감을 쫓는 여러 리더도 서로 다른 항목이다.

NavModifierVolume·은신처·장애물 목록 탐색은 이번에 카운터와 비용만 분리한다. 특히 가장 가까운 은신처는 단순 고정 반경으로 자를 수 없고 원판 크기도 다르다. 동물 점 인덱스를 검증하기 전에 이들까지 일괄 교체하지 않는다.

## 5. 반드시 보존할 결과 계약

### 5.1 원래 행 번호와 순서

통합 처리기는 Deer/Wolves를 StableAgentId로 정렬한 뒤 지역 목록을 만든다. 평면 기준 세계에서는 배열 슬롯 순서가 기준이다. **후보는 현재 원본 배열의 행 번호 오름차순**으로 처리한다. 거리순이나 셀 순서로 처리하지 않는다.

- `Nearest`, `NearestEv`, `Target`, `Caught`, `PreferredTarget`, `CaughtBy`, `CaptureAllowed[i]`, `RangedRoll[i]`는 원본 행을 가리켜야 한다.
- 후보 수를 `NumPrey`에 덮어쓰지 않는다. 포식 제한 `N > 8`, EMA 분모, 먹이 배분 등 전체 개체 수의 의미를 유지한다.
- 동점에서 기존의 엄격한 `<`와 첫 행 선택을 그대로 적용한다.
- 동족 중심·분리 방향의 덧셈 순서를 보존한다. SIMD 재배열·fast-math·병렬 reduction은 이번 범위에 없다.
- 후보 상한에 걸렸다고 뒤쪽 개체를 버리지 않는다. 메모리/조회 범위를 감당하지 못하면 기존 전체 순회로 fallback한다.

### 5.2 시야·청각·세계 규칙

후보 검색은 지각 결과가 아니다. 기존 거리·시야각·잠·은신처·차폐·청각 판정을 통과해야 관측에 반영한다. 서버가 가진 좌표를 인지하지 못한 동물에게 새 지식으로 주지 않는다.

Native `EThreatType::Player`는 실제 플레이어 Pawn 전체와 같은 개념이 아니며, 현재 위협 모델에서는 표적 선택의 시야 범위를 전역으로 취급하는 분기가 있다. 이 타입은 초기 최적화에서 표적 선택을 전체 순회로 유지한다.

### 5.3 사망과 난수

- 현재 Step은 E~F 관측에서 이번 스텝 사망 개체도 위치상 동족으로 세고, 통합 호출부가 Step 뒤 목록에서 제거한다. 인덱스가 먼저 죽은 개체를 제외하면 기존 세계와 달라진다.
- 여러 늑대의 포획 후보는 기존 `ResolveCatches`로 해결한다. 앞 늑대가 고른 사슴을 공간 인덱스에서 즉시 빼지 않는다.
- 원거리 포획의 `RangedRoll`은 전체 원본 행에 대해 기존 횟수/순서로 생성한다. 후보만큼 난수를 생성하지 않는다.
- 인덱스 구축·조회·fallback·진단은 시뮬레이션 RNG를 사용하지 않는다.

### 5.4 알려진 규모 제한

`UpdateWildFlight`는 현재 지역 위협의 앞 64개와 비트 기록을 사용하는 경로가 있다. 이를 2,000개체 전체의 일반 지원으로 설명하지 않는다. 이번 작업은 기존 선택 범위를 보존하며, 지역당 64개 초과 위협 지원은 별도 세계 규칙/기록/파리티 작업으로 남긴다. 실제 생태 지역을 임의 분할해서 제한을 우회하지 않는다.

## 6. 자료구조와 API 제안

신규 파일명은 제안이며 아직 존재하지 않는다.

`AI/Policy/EcoSpatialIndex2D.h`에는 UE 의존 없이 다음 자료형을 둔다.

| 자료형 | 내용과 수명 |
|---|---|
| `FSpatialPoint2D` | double X/Y, int32 OriginalRow. 읽기 전용 위치 복사 |
| `FCellEntry` | signed cell X/Y와 OriginalRow. 셀→행 순서로 정렬 |
| `FCellRun` | 셀 키와 Entries의 시작/개수. 연속 배열 |
| `FSpatialStamp` | context generation, Native step, phase, membership revision, build serial |
| `FCandidateView` | FullScan/Indexed 모드, 행 목록·길이, 원본 길이, stamp |
| `FSpatialQueryStats` | build/query/fallback/candidate/capacity 카운터. 논리 상태 아님 |

`FCandidateView`는 **비어 있는 Indexed 결과**와 **FullScan**을 명시적으로 구분한다. null pointer 하나로 두 의미를 표현하지 않는다. 후보 목록의 소유자는 호출자 scratch이며 다음 scratch 재사용 후 참조하지 않는다. 표적/포획 후보가 동시에 필요하면 별도 버퍼를 쓴다.

제안 인터페이스는 다음과 같다. 실제 시그니처는 기존 C++ 표준과 테스트 호출부를 대조해 확정한다.

```cpp
Build(points, count, cellSize, stamp);
QueryConservativeBox(centerX, centerY, radius, expectedStamp, outRows);
// 성공 시 outRows: unique OriginalRow 오름차순. 후보에는 false positive 허용.
// 실패/지원 범위 밖: FullScan. 좁은 단계의 기존 판정은 호출자가 수행.
```

`AI/Policy/EcoV3SpatialQueries.h`에는 v3의 검색 반경 계산과 단계별 scratch를 둔다. `FEcoV3RegionContext`가 `FEcoV3SearchScratch`를 소유한다. `FWorldState`의 논리 상태·checkpoint 직렬화에 인덱스를 넣지 않는다. 엔진 없는 실행에서는 호출자가 같은 scratch를 소유한다.

`Step`, `ObserveAll`, `ObserveAndDecideAll`, `ObserveAndDecideRows`에 선택적 검색 컨텍스트를 전달하는 경로를 추가한다. 기존 시그니처는 기본 인자 또는 wrapper로 유지한다. 미전달이면 기존 전체 순회다. 실제 판정 수식을 여러 곳에 복사하지 말고, 원본 배열 행을 순회하는 공통 helper에 기존 식을 한 번만 둔다. 최적화 전 원본은 테스트 oracle로 별도 고정하여 공통 helper의 동일 버그를 두 경로가 공유하는 문제도 검출한다.

### 6.1 셀 구축·조회 알고리즘

1. Native 위치에서 `floor(X / CellSize)`, `floor(Y / CellSize)`로 signed 셀 좌표를 만든다. 음수를 0 방향으로 잘라 계산하지 않는다.
2. 셀 좌표는 비교 가능한 두 정수로 유지한다. 음수 signed shift나 좁은 비트 패킹에 의존하지 않는다. 유한값·정수 변환 범위를 검사하고 불가능한 입력은 fallback한다.
3. 각 점을 한 셀에만 넣고 `(CellX, CellY, OriginalRow)` 순으로 정렬한다. 연속 셀 범위를 만든다.
4. 질의 AABB의 셀 범위를 찾는다. 초기 정확성 구현은 경계 셀을 보수적으로 확장하고 기존 거리식을 최종 판정으로 사용한다. epsilon은 후보 포함에만 쓰며 기존 판정 문턱은 바꾸지 않는다.
5. 셀 범위를 나열해 occupied run을 찾는다. 반경이 너무 크면 빈 셀을 무제한 순회하지 않고 전체 순회로 전환한다. 셀 범위 곱셈 overflow도 먼저 검사한다.
6. 후보 행을 모아 원본 행 오름차순으로 정렬한다. 각 점 1셀 원칙을 검사하고 중복 행을 허용하지 않는다.
7. 기존 함수가 기존 `sqrt`·나눗셈·각도·비교식을 실행한다. 이 단계에서 거리 제곱 비교로까지 바꾸지 않는다.

초기 비교 CellSize는 **5/10/20 Native units = 10/20/40m**다. 출발값은 10 units이며 배포 기본값 확정이 아니다. 기존 동족 SeeR=20 units(40m), SepRadius=5 units(10m)와 비교한다. 셀 크기는 성능만 바꾸고 결과는 바꾸지 않아야 한다.

### 6.2 작은 집단·밀집 fallback

- 최초 실험에서는 N≤64를 전체 순회로 처리하는 후보 설정을 비교한다. 고정된 정답이나 지원 상한이 아니다.
- 셀에 들어 있는 후보의 추정 합이 전체의 약 75% 이상이면 수집/정렬 대신 전체 순회를 선택하는 방안을 측정한다. 행위는 같아야 한다.
- 보수적 범위 검증 실패, stamp 불일치, 너무 많은 셀 방문, 미지원 반경은 FullScan으로 처리하고 사유 카운터를 남긴다. 비정상 위치 자체가 유효해지는 것은 아니며 기존 런타임 검증도 유지한다.
- 모든 개체가 반경 안에 있으면 유효한 상호작용 자체가 N²이므로 격자가 이를 선형으로 만들 수 없다. 최근접 K개 제한은 별도 근사 설계이며 이 계획에 넣지 않는다.

## 7. 언제 인덱스를 만들고 버리는가

프레임 번호나 Native T 하나만으로 유효성을 판단하지 않는다. 한 프레임에 여러 Step이 실행되거나, 같은 T에서 입양·복구·부분 관측이 있을 수 있다.

| 단계 | 위치/목록 | 인덱스와 소비자 |
|---|---|---|
| 초기 입양·이주 후 부분 관측 | 현재 Views 전체, 새 행만 관측 | Kin/Threat 인덱스 전체 구축, 부분 행 질의 |
| B 제어 훅 | 이동 전 실제 위치 | Journey용 별도 세계 좌표 인덱스 |
| C1 사슴 이동 완료→C2 | 이동 뒤 `W.Prey`, 늑대 이동 전 기준점 | Prey 인덱스 구축; PackPeek·표적·포획·CaptureMask |
| D 밤잠 갱신 | 현재 코드가 보유한 W.Prey와 이동 뒤 늑대 위치 | Prey 위치가 변하지 않았을 때만 동일 인덱스 재사용 |
| E~F 관측 | 사슴·늑대 이동 완료, 새 낮밤 상태 | BuildKinInputs/BuildThreatInputs 직후 Kin/Threat 구축 |
| G 평면 테스트 respawn | 바뀐 사슴 위치 | Kin 재구축 후 재관측; 늑대 위치가 같아도 stamp 확인 |
| Step 후 통합 목록 정리 | 죽음·지역 변경으로 행 매핑 변동 | 과거 CandidateView/행 매핑 무효화 |

환경 변경에 따른 밀어내기, 로드, 재생성, region context 재사용에도 stamp를 갱신한다. 인덱스는 **Native 실제 위치**로 구축하며 `FTransformFragment`의 보간값으로 대체하지 않는다.

### 7.1 Journey의 별도 규칙

현재 `JourneyControlHook`은 같은 계획의 개체를 모든 context에서 읽는다. 이 동작을 지역 인덱스 하나로 줄이면 경계를 사이에 둔 같은 무리를 놓칠 수 있다.

GT에서 현재 전체 Deer의 Native→cm 위치를 만든 세계 좌표 인덱스를 사용하고, **220cm 이내** 후보에 기존 plan 일치·활성·생존 판정을 적용한다. `Distance>0.1`/동위치 StableId 분기와 덧셈 순서를 유지한다.

현재 지역별 Step은 순서대로 진행되므로 나중 지역의 훅이 앞 지역의 이미 갱신된 위치를 볼 수 있다. 따라서 초기 전체 인덱스를 지역 Step 완료 후 갱신/재구축해 이 시간 의미를 보존한다. 스텝 시작 위치로 일괄 고정하는 변경은 이번에 하지 않는다. 구축 비용이 이득보다 크면 Journey 최적화는 OFF로 유지한다.

## 8. 소비자별 보수적 반경

| 소비자 | 후보 범위 | 보존 조건 |
|---|---|---|
| 동족 관측 | `max(ObsCfg.SeeR, ObsCfg.SepRadius)` | 분리는 시야 밖에도 작용하므로 FOV로 후보를 자르지 않음 |
| 사슴 위협 관측 | `max(SeePred*SeeMult, MaxHearRadius)` | 날씨 적용 뒤 실제 ThreatIn HearR, ExternalThreats 포함; cap-to-sight는 기존 판정에서 적용 |
| 늑대 표적 | `PredViewR*WeatherViewMult / MinDetectMult` | 현재 Prey 상태의 양수 detect 배수 하한을 한 번 계산. 0/음수/비유한/전역 Player면 전체 순회 |
| 늑대 포획 | `Spec.CatchRadius / MinCatchMult` | 수정된 실제 Spec 기준, 이동 전 QX/QY 기준, 기존 차폐·RangedRoll·은신처 판정 |
| 밤잠 주변 사슴 | `NightSettleR` | 호출 시점의 늑대 위치와 기존 W.Prey, Alive 조건 그대로 |
| CaptureMask 차폐 검사 | 기존 `Spec.CatchRadius*3` | 현재 hook과 같은 시점; 전체 길이 mask 기본 1은 유지, 후보 행만 기존 ClearLine 수행 |
| 부모 후보 | 10 Native units(20m) | 기존 제곱거리≤100, 같은 지역·종, 원래 ID 쌍 순서 |
| 근접 식사 진단 | 기존 `kNearEatingWolfUnits` | 실제 호출 시점의 상태·목록 그대로 |

`MinDetectMult`와 `MinCatchMult`는 현재 Prey 상태/설정에서 안전한 하한을 얻는다. 기존 배수가 항상 1 이상이라고 하드코딩하지 않는다. life 훅이 늑대의 CatchRadius를 바꾸므로 hook 적용 전 반경을 재사용하지 않는다.

ThreatIn의 앞 M개는 Native 위협, 뒤쪽은 ExternalThreats다. 합친 원본 행의 순서를 보존하고, 검색 결과의 로컬 인덱스로 다시 번호를 매기지 않는다.

`ObserveHerb`는 현재 shared `ThreatIn.bOccluded`를 관찰자마다 덮어쓴다. 후보 경로에서도 **현재 관찰자에게 해당하는 차폐를 다시 계산**해야 한다. 앞 사슴의 bOccluded를 뒤 사슴에게 재사용하지 않는다. 순수 관측 비교에서는 관찰자 로컬 scratch를 써 오염을 방지하고, 다른 소비자가 이 mutable 필드를 어떻게 읽는지도 회귀한다.

`UpdateWildFlight`는 첫 배포에서는 전체 순회를 유지한다. 후속 최적화 시 보이는 위협뿐 아니라 보이지 않아도 SafeR 안에서 도주를 유지시키는 위협을 포함해야 한다. 같은 pair의 차폐 캐시는 위치/heading·날씨·행동·장애물 revision과 phase가 모두 같을 때만 허용한다. 감지 결과와 도주 유지 결과를 같은 목록으로 단순 통합하지 않는다.

## 9. 반복 조회·메모리 개선의 구체적 범위

1. `EvidenceThreatHook`의 StableId→Herb row는 이미 오름차순인 `StableViewIds`에 이진 탐색을 우선 적용한다. persistent map을 새로 유지할 필요가 없다. 매 BuildViews와 같은 수명의 목록만 사용한다.
2. CaptureMask는 전체 원본 길이를 보존한다. 초기에는 `Init(1,N)` 비용을 남겨 두고 거리/차폐 후보 순회만 줄인다. 이후 계측에서 mask 초기화가 크면 generation-stamped mask를 별도 회귀 후 검토한다.
3. `ProcessNaturalBirths`는 기존 5초 주기와 지역/종당 첫 유효 쌍을 유지한다. outer 부모 I를 기존 ID순으로 순회하고, 인덱스가 돌려준 J 중 J>I를 같은 순서로 검사한다. eligibility·혈연·부모 비용·예약은 그대로다.
4. 배열은 capacity를 유지하고 메모리 최대치를 계측한다. actor 수와 무관하게 모든 개체 쌍의 후보/거리 행렬을 N²로 저장하지 않는다. 질의별 재사용 scratch를 사용한다.
5. 현재 `BuildAgentLookup`은 중복 ID 검증도 수행한다. 계측 없이 삭제하거나 오래된 map을 그대로 쓰지 않는다. 증분화는 spawn/death/migration/load/구조 변경을 모두 추적할 revision이 준비됐을 때 별도 패치로 한다.
6. Mass Fragment 포인터는 현재 Query/Execute 안에서만 재획득·사용한다. 프레임 사이에 정렬된 raw pointer 목록을 캐시하지 않는다. durable 캐시에는 StableId/EntityHandle만 저장하더라도 사용 시 epoch·유효성을 다시 검사한다.
7. `Steps==0`이라고 Integrated Execute를 즉시 건너뛰지 않는다. 입양·환경·모델 변경·부분 관측·출력 동기화의 필요 여부를 먼저 분리해야 한다. 첫 배포는 기존 수집 흐름을 유지한다.
8. 두 플레이어의 샘플 순회는 현재 규모에서 작은 작업이다. 플레이어 위치 인덱스나 새 관리자보다 N² 동족 탐색을 우선한다. 피격 Proxy의 전역 후보 선택은 후속 계측 결과로 결정한다.

## 10. 계측과 성능 목표

먼저 기존 경로의 비용을 분해한다. 현재 Native batch 타이머는 Gather/Sort 이전부터 시작하지 않으므로 그것만 비교하면 일부 비용을 놓친다.

| 범위 | 시간/카운터 |
|---|---|
| GT 통합 | Gather, Sort, BuildViews, Native Step, 후처리, 전체 Execute |
| 공간 구축 | Phase별 build 수·ms, point/cell 수, sort ms, capacity/재할당 |
| 질의 | consumer별 query 수·셀 방문 수·후보 수·query/sort ms |
| 정밀 판정 | 실제 검사 수·수용 수·거리/FOV/LOS 탈락 수, LOS 호출 수 |
| fallback | SmallN, Dense, LargeRange, InvalidStamp, Unsupported 등의 횟수 |
| 정합성 | candidate miss, 행 중복, stamp 실패, oracle 결과 불일치 |
| 통합 결과 | 서버 GT p50/p95/p99/max, Native debt, 두 Client 논리 실행 수, 장부 오류 |

엔진 무관 core는 정수 카운터를 모으고 UE adapter/standalone harness가 타이머를 감싼다. 성능 측정 때 oracle·상세 per-agent 로그는 OFF다. 계측 비용 자체를 ON/OFF 대조한다. exclusive 시간과 inclusive 전체 시간을 구분하여 중복 합산하지 않는다.

전체 작업량은 대략 `Build + Σ(Query cells + Candidates + Candidate ordering) + NarrowPhase`다. 기존 `Σ N_region² + Σ N_region*M_region`과 비교한다. 가까운 동물 수가 고정되는 분산 환경에서는 이득이 크고, 좁은 영역의 밀집에서는 제한된다.

**채택 목표(측정 전 제안):**

- 후보 누락/중복, 원본 인덱스 오류, 상태·사건 불일치 0.
- 분산된 512개체 및 2,000점 합성 입력에서 구축·정렬 포함 해당 탐색 CPU p95를 기존보다 30% 이상 줄이는 것을 목표로 한다.
- 32/128 소규모 및 밀집 입력은 p95 회귀 5% 이내를 목표로 한다. 차이가 실행 잡음보다 작은 경우 반복/신뢰구간과 함께 보류하고 우월성을 주장하지 않는다.
- 단계별 총 GT도 함께 비교한다. 탐색만 빨라지고 전체 frame이 나빠지면 기본 활성화하지 않는다.
- warm-up 후 고정 수량에서는 query buffer 재할당 0을 목표로 한다. 메모리는 N+셀+질의 scratch에 비례하며 장시간 단조 증가하지 않아야 한다.
- 30Hz 전체 생태계 예산 달성은 이 단계만으로 보장하지 않는다. 지형 질의가 남으면 전체 개선은 작을 수 있다.

현재 무대 크기의 예인 한 변 120m에 1,800마리 사슴을 균일하게 넣고 40m를 검색하면, 경계 밖 잘림을 무시한 원 안 평균은 약 `1800*π*40²/120² ≈ 628`마리다. 사각 후보는 더 많다. 따라서 격자 적용만으로 후보가 항상 수십 마리나 O(N)이 된다고 약속하지 않는다. 개체 수 증가와 밀도 증가를 분리해 측정한다.

## 11. 테스트 설계

### 11.1 독립 인덱스와 소비자 대조

전체 순회로 얻은 유효 결과와 후보 경로를 같은 입력에서 대조한다.

| 사례 | 확인할 오류 |
|---|---|
| N=0/1, 셀 경계·음수 좌표·동위치 | 누락·중복·floor 오류·자기 자신 제외 |
| 정확한 반경 경계와 바로 안/밖 | inclusive 비교, float/double 반올림 차이 |
| 셀 크기 5/10/20, 큰 반경 | cell 방문 범위 누락·overflow·fallback |
| SepRadius>SeeR, 뒤쪽 동족 | 시야 기반 후보 잘림으로 분리 힘 누락 |
| HearR>시야, 차폐된 소리, 날씨 변경 | 청각 누락·잘못된 차폐 재사용 |
| ExternalThreats, 동점, PreferredTarget | 원본 행·tie-break 유지 |
| detect/catch 배수<1·0·비유한 | 안전 반경·fallback |
| Native Player 타입·원거리 포획 | 전역 표적·RNG 호출 순서 |
| 같은 Step에서 죽음/포획 중복 | 기존 관측·ResolveCatches 의미 |
| respawn·입양·부분 관측·같은 T 재구축 | stamp/행 매핑 오류 |
| 무리 이주 경계·지역 순서 | 다른 context의 현재 위치 누락 |
| 번식 동점·형제/부모 배제 | 첫 유효 부모 쌍 보존 |

같은 바이너리의 brute-force/optimized 비교는 필드별 정확 일치를 우선한다. 메모리 padding을 포함한 구조체 memcmp를 하지 않는다. 실수 차이가 생기면 먼저 누적 순서·경계·부호 0·비유한 처리 원인을 분석한다. 허용 오차를 임의로 넓혀 실패를 숨기지 않는다. 플랫폼 간/Python 비교는 기존 Golden/계약의 허용치를 별도로 따른다.

### 11.2 전체 Native 궤적 대조

동일 seed·초기 세계·모델·환경 스케줄로 두 **독립 세계**를 초기화하고 OFF/ON을 실행한다. `FReferenceWorld`를 얕게 복사하면 Views가 원본 배열을 가리킬 수 있으므로 각 세계의 포인터를 자체 배열에 재결합한다.

매 스텝 관측·Raw Request·mask·실행 행동·위치/속도·에너지/비축·표적/포획·RNG 상태·Food·죽음/출생 기록을 필드별로 비교하고 첫 차이의 입력을 남긴다. 인덱스·성능 카운터는 논리 hash에서 제외한다. 최소 3개 seed, seed당 10,000 Native steps를 초기 회귀 범위로 제안한다. life hook 포함 Unreal 통합은 별도 검증이다.

살아 있는 서버에서 생태 Step이나 World trace 훅을 두 번 실행해 shadow 검증하지 않는다. 순수 함수는 입력 복사로 비교하고, side effect 있는 훅/장부/이동은 독립 실행 또는 고정된 입력·결과 재생으로 비교한다.

기존 `herbivore_rl/tests/test_threat_golden_v3.py`, `test_repertoire_golden_v3.py`, `test_flight_golden_v3.py`, `test_export_v3.py`, `test_ceval_v3.py` 및 관련 Wild/Realism 테스트를 영향 범위에 맞춰 수행한다. Python 전체 life 세계 파리티가 새로 완성됐다고 기록하지 않는다.

### 11.3 규모·실제 맵 검증

- 커널 시험: 32/128/256/512/1000/2000점, 같은 면적에서 밀도 증가와 같은 밀도에서 면적 증가를 분리한다. 균일/군집/일렬 corridor/전체 한 셀을 포함한다.
- 각 조합은 동일 입력으로 OFF/ON을 번갈아 실행하고 warm-up 후 최소 5회 반복한다. AABB 후보, 최종 수용 후보, build/query/sort 시간을 별도 기록한다.
- Native 전체 시험은 지원 위협 수·모델/세계 설정을 지킨다. 2,000점 커널 성공을 2,000마리 life/Unreal 검증으로 표현하지 않는다.
- 현재 스포너 지원 범위에서 목표 맵의 32/128/256/512 실행을 준비한다. 실제 Alive/종별/지역별 수를 기록하고 starvation으로 수량이 줄어든 구간을 고정 N 성능으로 섞지 않는다.
- Dedicated+2Client: 같은 지역, 다른 지역, 플레이어 사냥·늑대 공격, 집단 도주, 이주 경계, 은신처 접근, 신규 출생/사망, 재접속. Client 권위/Native 실행 0을 확인한다.
- 사용자 작업 맵을 재저작하지 않고 검증용 런타임 override/명시적 fixture를 우선한다. 맵 authoring이 필요하면 사용자 에셋 변경과 구분해 별도 작업으로 진행한다.
- 초기 실제 측정은 warm-up 30초+120초 구간 3회, 통과 뒤 30분 soak를 제안한다. 전투·도주 burst의 최대 frame과 p99를 따로 적는다.
- 1,000/2,000 실제 개체 시험은 스폰·출생·저장·위협 수 제한의 별도 확장 acceptance를 통과한 뒤 수행한다.

## 12. 구현 단위와 완료 게이트

| 패치 | 구현할 것 | 완료 조건 |
|---|---|---|
| SQ-0 | 현재 실행 manifest와 세부 계측, 기준 결과 저장 | 실제 맵/개체 수·전체 Execute·Native·소비자 비용 분리 |
| SQ-1 | 엔진 독립 격자·stamp·FullScan fallback·독립 oracle | 경계/무작위/밀집에서 후보 누락·중복 0, 비용 표 |
| SQ-2 | PerceiveKin과 초기/부분/Step/respawn 관측 연결 | 기존 동족 결과·관측·행동·궤적 일치 |
| SQ-3 | ThreatIn 인덱스·시야/청각/ExternalThreats | 청각/차폐/동점/행 인덱스 회귀 통과 |
| SQ-4 | Prey 인덱스·늑대 표적/포획·PackPeek/NightUpdate·hook | 표적/포획/RNG/안전 규칙/실제 플레이어 전투 일치 |
| SQ-5 | Journey·번식·진단·ID lookup·버퍼 재사용 중 측정상 유효한 항목 | 각 시간 경계/선택 순서 보존, 총비용 개선 |
| SQ-6 | 실제 맵 지원 수량 검증·문서·기본 활성화 판단 | 정확성 0오류, 성능 목표 판정, 한계·rollback 명시 |

첫 구현 요청 단위는 **SQ-0~SQ-2**가 적절하다. 최소 end-to-end 동족 경로를 완성한 뒤 다음 소비자로 확장한다. 모든 최적화를 한 번에 켜서 차이 원인을 잃지 않는다.

## 13. 파일별 변경 계획

| 파일 | 계획 |
|---|---|
| `AI/Policy/EcoSpatialIndex2D.h` (신규) | 엔진 독립 셀 인덱스·후보 view·stamp·카운터 |
| `AI/Policy/EcoV3SpatialQueries.h` (신규) | 반경 계산·단계별 scratch·v3 adapter |
| [EcoObservationV3.h](../../Source/AdaptiveEcosystem/AI/Policy/EcoObservationV3.h) | 원본 행 후보를 받는 관측 순회, 기존 API 보존 |
| [EcoWorldV3.h](../../Source/AdaptiveEcosystem/AI/Policy/EcoWorldV3.h) | 정확한 단계에서 인덱스 구축·선택적 scratch 전달 |
| [EcoThreatModel.h](../../Source/AdaptiveEcosystem/AI/Policy/EcoThreatModel.h) | 표적/포획/밤잠 후보 view, 기존 결과 인덱스 유지 |
| [IntegratedSubsystem.h](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.h) | 지역별 transient scratch 수명 |
| [IntegratedProcessors.cpp](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp) | 계측·scratch 전달·hook/ID lookup·단계 무효화 |
| [EcoCreatureNaturalBirth.cpp](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureNaturalBirth.cpp) | SQ-5에서 부모 후보 검색만 교체 |
| `AI/Policy/Tests/EcoSpatialQueryTests.cpp` (신규) | 인덱스·소비자·잘못된 stamp·통합 회귀 |
| `Tools/EcoV3Eval`의 별도 spatial benchmark 소스 (신규) | 기존 공통 Native 헤더를 쓰는 재현 가능한 OFF/ON 대조 |
| [기존 P3](../Integration/P3_SPATIAL_AND_QUERY_OPTIMIZATION.md) 및 본 문서 | 구현된 범위·측정·미완료를 후속 갱신 |

코드 변경 시 `Core/`, `AI/Policy/`, `Mass/` 계약과 변경 시점의 실제 Source를 다시 확인한다. 새 C++/빌드 입력은 AGENTS 규칙대로 기존 UBT/dotnet/Editor/LiveCoding/MSBuild/ShaderCompileWorker 실행 여부를 확인한 뒤, 승인된 실행 환경에서 직접 `UnrealBuildTool.exe`의 `AdaptiveEcosystemEditor Win64 Development` 빌드를 실행하고 완료를 기다린다. 실행 중 프로세스를 종료하거나 중복 빌드하지 않는다. 공통 Native 헤더 변경은 엔진 없는 평가기도 재빌드한다.

## 14. 활성화·롤백·저장

제안 설정 이름은 `eco.IntegratedV3.SpatialQueries`(0=기존, 1=후보), `SpatialQueryConsumerMask`, 개발용 `SpatialQueryVerify`다. **현재 존재하는 CVar가 아니다.** 구현 시 동등한 기존 옵션이 있는지 재확인한다.

- 초기 기본 OFF. 순수 함수 shadow 대조→소비자별 opt-in→독립 세계 궤적→실제 맵 검증 순으로 활성화한다.
- 모드/셀 크기 변경은 Native 경계에서 적용하고 인덱스를 무효화한다. 중간 상태나 RNG를 초기화하지 않는다.
- 잘못된 stamp나 지원하지 않는 범위는 즉시 전체 순회로 복귀한다. 검증 불일치는 증거를 남기고 해당 소비자의 최적화를 끈다. 이미 잘못 반영한 논리 결과를 자동 복구했다고 주장하지 않는다.
- 인덱스는 checkpoint에 저장하지 않고 로드/입양/지역 재생성 후 구축한다. 모델/관측 schema는 유지한다.
- 현재 same-build checkpoint의 runtime hash 제한은 유지된다. 저장 필드를 추가하지 않았어도 재빌드 전 파일이 자동 호환된다고 설명하지 않는다.
- rollback은 소비자 옵션 OFF로 기존 순회를 복원한다. 기능 비교를 위해 최적화 전 oracle/전체 순회를 제거하지 않는다.

## 15. 참고 기술·오픈소스와 실제 적용 방침

확인일: 2026-11-06. 아래는 도입 완료 목록이 아니다. 외부 코드 복사/의존성 추가는 아직 하지 않았다.

| 출처 | 기술 | 프로젝트 적용 결정 |
|---|---|---|
| [프로젝트 기존 격자](../../Source/AdaptiveEcosystem/AI/Policy/EcoNeighborhoodSubsystem.cpp) | 균일 2D 셀과 반경 검색 | 첫 구현의 설계 출발점. v3 단위·시점·행 순서에 맞춘 순수 자료구조로 적용 |
| [Epic THierarchicalHashGrid2D](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/AIModule/THierarchicalHashGrid2D) · [QuerySmall](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/AIModule/THierarchicalHashGrid2D/QuerySmall) | 크기에 따라 레벨을 나누는 2D 격자, 보수적 후보 반환 | 크기가 다양한 장애물의 UE adapter 비교 후보. UE 라이선스의 엔진 소스이며 일반 오픈소스로 분류하지 않음. Native 공통 코어에는 직접 의존시키지 않음 |
| [nanoflann](https://github.com/jlblancoc/nanoflann) · [BSD-2-Clause 원문](https://github.com/jlblancoc/nanoflann/blob/master/COPYING) | C++ 헤더 기반 KD-tree, 반경 검색 | 균일 격자의 분포 민감도가 문제일 때 standalone benchmark의 비교 구현으로 검토. 초기 production 의존성은 추가하지 않음 |
| [Box2D dynamic tree](https://box2d.org/documentation/md_collision.html) · [MIT 원문](https://github.com/erincatto/box2d/blob/main/LICENSE) | AABB 기반 동적 트리·영역/광선 후보 검색 | 큰 장애물·크기가 다른 은신처 검색의 후속 설계 참고. 물리 엔진이나 movement solver를 도입하지 않음 |

nanoflann 비교 구현은 같은 입력 double XY를 adapter로 제공하고 exact 검색만 사용한다. L2 반경이 제곱거리 단위라는 API 조건, 포함 경계의 차이를 보수적인 후보 범위+기존 narrow 판정으로 처리하고, 반환 순서를 원본 행순으로 재정렬한다. **재구축+조회+결과 정렬+메모리** 전체가 격자보다 유리한지를 비교한다. 동적이라는 이름만으로 매 스텝 움직이는 모든 점의 갱신이 싸다고 가정하지 않는다.

Box2D 자료에서 가져올 것은 AABB와 객체 ID로 후보를 줄이는 분리 원칙이다. 실제 코드를 채택한다면 double Native 위치에서 float AABB로 변환할 때 보수적으로 바깥 경계를 잡고 누락 검증을 해야 한다. 현재는 참조만 하므로 이 추가 작업도 발생하지 않는다.

외부 라이브러리를 실제 채택할 때는 비교에 사용한 release/commit과 파일 hash를 고정하고 저작권·라이선스 고지를 함께 보존한다. 라이선스명만 적고 구현 파일을 출처 없이 복사하지 않는다. 이번 단계에는 MassFlock·새 ECS·ORCA를 설치할 필요가 없다.

## 16. 납품물과 이번 문서 검증 범위

구현 완료 때 남길 것은 코드/테스트, 실행 manifest, OFF/ON 비용 표, 첫 불일치 재현 입력, 원시 trace 위치, 실제 개체 수·지역 밀도·하드웨어·서버/Client 조건, 불변식 결과, 미지원 규모와 rollback 방법이다. 원시 성능 산출물은 `Saved`의 작업별 경로에 두고 작은 요약만 Evidence 문서로 관리한다.

이번 작업은 **이 계획 문서와 기존 P3의 연결만 작성**했다. Source 근거와 상대 링크·diff를 검증하며, C++·맵·에셋·모델·설정을 변경하지 않는다. 새 UBT·PIE·성능·Python 파리티 검증을 수행한 것으로 기록하지 않는다.
