# wonkii의 다음 작업과 팀 통합 실행 계획

작성일: 2026-10-13 (한국 시간) / 기준 엔진: Unreal Engine 5.8

## 1. 결론과 이번 계획의 기준

**wonkii의 다음 작업은 M4 병합 오류 복구 → 복제 정확성 확보 → 동물 경로의 공통 생명주기 통합이다.** 이 세 가지가 팀의 레벨·Social·정책 작업을 실제 하나의 생태계로 연결하는 선행 조건이다. V3 준비는 별도 계약 작업으로 함께 진행하고, 두 대륙·다종·대규모 최적화는 이 기준선 이후에 진행한다.

현재 프로젝트는 소규모 동물 통합을 시연하고 일부 실행을 검증한 프로토타입이다. 팀원 PR의 기능을 활용할 기반은 갖췄다. 그러나 현재 M4 소스에는 병합 잔여 문법 오류가 있고, Box와 Creature의 생존 규칙이 다르며, 연결별 복제·표현 예산은 아직 집행되지 않는다. 상용 규모나 장기 지속 생태계를 보장하는 단계로 평가할 근거는 없다.

이번 확인 범위:

- 로컬 `M4` HEAD와 원격 wonkii/M4: `6235742365db42c64fef539ac5841f9adfd4f0e8`.
- 팀 원격 main: `f54e1124aaba40cfabf25f589040689efad0822c`. 로컬 M4는 이 커밋을 포함한다.
- RL 원격 `Branch_Sinhyeok`: `9dd13935f42a43a6e2228e891c051b66aaa6472d`. 로컬 remote-tracking ref는 `0c9632b`로 뒤처져 있어 최신 문서·커밋은 GitHub API에서 따로 읽었다.
- 공개 PR 목록을 두 저장소에서 조회했다. 팀 저장소에 열린 PR은 없고, wonkii 저장소에서는 PR 항목이 반환되지 않았다. 아래는 이미 병합된 PR와 아직 main에 반영되지 않은 RL 브랜치를 구분한 계획이다.
- 현재 작업 트리의 기존 Docs/README 수정, P1~P6, 10월 11일 감사 문서는 보존했다. 이번에는 이 계획서만 추가했다.
- Source 정적 대조와 원격 PR/브랜치 조회를 수행했다. **이번 작업에서 UBT, 자동화, PIE, 에셋 내부 검사, 패키징, 성능 측정은 수행하지 않았다.** 과거 성공 기록은 해당 커밋과 조건의 증거다.

## 2. 다른 사람의 PR에서 실제로 가져온 것

| 기여 / 근거 | 현재 활용 가능한 결과 | 다음 연결과 남은 한계 |
| --- | --- | --- |
| avaroki [PR #1](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/1), [PR #10](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/10) | 날씨·낮밤 시각 효과, World Partition 통합 맵, 초원/황무지/설원, 물·수풀·NavMesh·HLOD 작성 | 날씨가 권위 지역 환경·자원 변화로 들어오는 연결은 후속. NavMesh 배치가 동물의 경로 탐색 소비를 보증하지 않는다. cook/HLOD와 실제 이동 통과를 따로 확인해야 한다 |
| sinhyeok04 [PR #6](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/6), [PR #7](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/7) | V1 Python PPO 학습·Export, 7→64→64→4 Native 추론, Utility 비교, Golden Vector, CustomMovementTag로 이동 중복 방지 | 기존 모델의 의미·수치·시간을 보존할 계약 정합성이 필요. 최신 버그 수정과 V3 실험은 이 두 PR 이후 브랜치 작업이다 |
| 조연우 [PR #5](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/5) | authored Shelter 평가·결정론적 슬롯 예약 | 초기 PR의 예약까지라는 한계를 현재 상태에 그대로 적용하지 않는다. 실제 이동 인계는 #11에서 추가됐다 |
| 조연우 [PR #11](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/11) | 사슴·늑대 EntityConfig/BP, V1→Social Request→종별 단일 이동→Feedback, 실제 Shelter Moving/Occupied/해제, 배치 자원·사망·인구 피드백, 감각·발소리·Client 표현 | opt-in Creature 경로의 구현·검증이다. Box 생존 경로와 규칙 통합, M4 변경 후 복제 회귀, 포식자 에너지, 실제 식물 소비, 규모 검증은 남는다 |
| wonkii [PR #4](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/4), [PR #9](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/9), M4의 `f2454aa`/`4260525`/`85d057b` | 권위 Mass 생성·Client proxy·Bubble, 지역 자원/요약, Box 생존·과밀/기아·압력 이주, 연결별 표본 간격 | M4 후속 변경은 main 미반영. 현재 합쳐진 HEAD의 빌드·동물 경로 회귀부터 확보해야 한다 |

PR #11 설명은 직접 UBT, 자동화 43개, PIE, 동일 서버 재접속 검증을 보고한다. RL의 오늘 병합 커밋 `e5b849a`는 main을 RL 브랜치로 가져온 뒤 UBT와 전체 자동화 64/64를 보고한다. **둘 다 현재 wonkii M4의 검증 결과는 아니다.** 테스트 개수만 비교해서 더 완성된 브랜치를 선택할 수 없다.

기여는 구현 커밋과 PR 작성자로 구분한다. wonkii가 병합한 Social PR을 wonkii가 작성한 기능으로 계산하지 않는다.

## 3. 현재 차단 문제와 냉정한 판정

| 순위 | 확인한 사실과 Source 근거 | 판정 / 필요한 조치 |
| --- | --- | --- |
| P0 | [EcoMassReplicator.cpp](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp) 71/89/125행에 미완성 lambda 선언, 뒤에 중복 선언. capture도 사용 변수와 불일치 | 현재 소스를 빌드 기준선으로 삼을 수 없다. 중복 정리와 view 수명·capture 복구가 첫 작업. 이번에 compiler 로그로 재현한 것은 아니다 |
| P0 | [EcoMassMigration.h](../../Source/AdaptiveEcosystem/Mass/EcoMassMigration.h) 21행과 [EcoMassMigration.cpp](../../Source/AdaptiveEcosystem/Mass/EcoMassMigration.cpp) 37행에 구형 함수 인자 줄이 남음. cpp에는 구형 직접 변경과 신규 snapshot/commit 로직이 함께 남음 | 문법만 지우면 이동 의미를 잃을 위험이 있다. 과밀/생존 전망·도착 결과와 Creature의 Resident 속도 보존·초식만 식량 이주 조건을 함께 보존해 하나의 실행 경로로 복구 |
| P0 | Replicator 156행의 `SetPresentation` dirty가 sequence 갱신 조건에 포함되지 않음. [Receive](../../Source/AdaptiveEcosystem/Mass/EcoMassPresentationFragments.h)는 동일 sequence를 거부하고 [Bubble](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.cpp) 184행은 실패 시 반환 | velocity/행동 flag만 변한 payload를 수신 적용하지 못할 수 있는 정적 경로다. 빌드 복구 뒤 실행 재현·수정 필요 |
| P1 | [Creature Reconcile](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.cpp) 297행 이후와 [Box Lifecycle](../../Source/AdaptiveEcosystem/Mass/EcoMassLifecycleSubsystem.cpp) 318행 이후가 별도 생존·자원·사망 순서를 가짐 | 현재 같은 개체가 양쪽에서 이중 처리된다고 단정하지 않는다. 생성 경로별 규칙 차이와 M4 기능의 동물 미소비를 해결한다 |
| P1 | Creature 대사 pass는 HP>0인 `Herbivore`만 처리. [공통 DeathCause](../../Source/AdaptiveEcosystem/Core/EcoSurvivalTypes.h)는 None/Starvation/ExternalDamage. Creature는 별도 `bPredated` 사용 | 포식 결과·원인·포식자 보상·늑대 생존이 하나의 계약으로 닫혀 있지 않다. 종별 규칙 adapter와 공통 결과 확정이 필요 |
| P1 | M4 관측 5는 지역 PredationHistory 우선. RL 오늘 병합은 전역 EMA로 변경. V1 문서는 지역 의미. M4 정책 결정은 여전히 프레임 카운터 | 동작 차이는 버그 수정과 계약 변경을 구분해야 한다. 최신 RL 브랜치 전체 병합으로 조용히 의미를 바꾸지 않는다 |
| P1 | [SyncVisuals](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.cpp) 434행 이후는 수동 Actor 생성/삭제, VInterpTo, 로컬 Sequence. M4 Previous/Current/reset 표본을 실제 동물 보간에서 소비하지 않음 | 표본 수신 계약과 동물 표현을 연결해야 한다. 작은 teleport/reset·재진입·지연 상황 회귀 필요 |
| P2 | [ConnectionBudget](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassNetworkSettings.h)의 relevance/Actor/Add 예산은 설정과 유효성 검사만 확인됨 | 설정 추가는 런타임 제한 완료가 아니다. 종/Template을 합친 연결 전체 예산 집행 필요 |
| P2 | Creature는 결과마다 Owned 재검색, 지역마다 Owned 집계, Predator perception은 prey 후보 순회 | 최악 반복 비용은 개선 후보다. 실제 병목 순위와 개선 배율은 미측정 |
| P2 | [M4 검증 기록](../Roadmap/M4/M4_VALIDATION_REPORT.md)에 서로 다른 거리의 두 Client, packet/CPU trace, Late Join 회귀 등이 미실행/미측정 | M4를 완료로 선언할 근거가 부족하다. 동일 commit·실제 동물 맵에서 검증표를 채운다 |

현재 Creature에는 실제 Provider와 Social 소비가 있다. 오래된 문서의 “전부 Dummy”, “은신처 목적지 미소비”, “사망 미구현”을 최신 동물 경로의 공백으로 반복해서 적으면 잘못된 작업을 배정하게 된다. 반대로 opt-in 구현을 전체 Bootstrap·모든 맵의 전환 완료로 확대해서도 안 된다.

## 4. 이번 주에 확정할 팀 결정

아래 권고는 계획의 기본안이다. 기존 V1·Food 재생 0·Social 책임 경계를 이번 문서 작성으로 변경하지 않는다. 결정 기록에는 선택, 적용 모드, 담당자, 근거, 재검증 범위를 남긴다.

| 결정 | 권고 | 결정 전 진행 가능한 작업 |
| --- | --- | --- |
| 통합 기준 | 먼저 M4를 복구하고 필수 버그 수정만 작은 PR로 main에 반영. 팀 main/릴리스 후보 SHA를 한 개 지정 | 병합 잔여 조사·회귀 시나리오·복제 재현 준비 |
| V1 관측 5 | 기존 가중치의 학습 의미와 production 지역 의미를 명시적으로 대조. 전역 EMA 채택 시 정책 계약에 예외/수정과 평가를 기록. 지역 PredationHistory는 Ecology 권위 저장소로 유지 | 기존 분모 버그 재현, 지역 사건/정책 feature 분리 설계 |
| 시간·사건 순서 | Policy의 실시간 스케줄 수정과 Ecology의 완료 step을 각각 정의. 조향/포획 순서 선택을 Python 및 종별 writer와 검증 | 두 브랜치 실행 의존성 도식과 cycle 검사 준비 |
| V3 도입 범위 | V1을 유지하고 V3를 별도 opt-in 모드로 계약화. V3가 기존 Social을 우회한다면 루트 계약의 명시적 예외가 필요 | RL export/Golden 초안, wonkii DTO·ID·수명 인터페이스 초안 |
| 경보·Shelter 주인 | 모드별 권위 writer 하나. V1은 현재 Social. V3는 Social 예약을 학습에 포함할지, 학습 규칙의 별도 모드를 둘지 결정 | 표시 DTO와 예약 세대/해제 회귀 설계 |
| 먹이·재스폰 | 생태 검증은 기존 재생 0/웨이브 꺼짐을 기본. 반복 시연은 별도 preset에 공급/재생/재스폰을 기록 | 자원·Birth/Death 회계와 spawn 요청 계약 |
| 제품 목표 | 최소 목표 기기, 서버 tick, Client FPS, 최대 논리/관련 개체·Client, 세션 길이, 시연 마감 지정 | 19/64/128개 기준선 시나리오와 측정 도구 준비 |

RL 브랜치 안의 다른 사용자의 승인 기록과 일정 제안은 참고 근거다. 팀 main의 계약 변경이나 wonkii의 기능 범위 승인을 자동으로 대신하지 않는다.

## 5. wonkii가 구현할 순서와 PR 단위

각 PR은 문제·최종 동작·검증 SHA/설정/로그를 포함한다. 아래 이름은 작업 제안이며 새 PR/브랜치를 이번에 생성한 것은 아니다.

### 작업 A — M4 병합 복구와 빌드 기준선 (예상 1~3인일)

- Replicator의 CacheViews/Add/Modify 선언과 capture를 하나씩 복구한다.
- Migration의 h/cpp/call sites를 하나의 인자 계약으로 맞춘다. 신규 압력 전망·도착 Outcome을 살리고, Creature에서 Resident의 종별 이동 속도를 덮어쓰지 않게 한다. 늑대에 식생 고갈 이주를 적용하지 않는다.
- 같은 패스에 구형 직접 Region/Travel 변경과 신규 commit이 모두 실행되는 잔여를 제거한다. fragment 접근 권한·const/mutable view도 확인한다.
- Box는 엔진 이동, 통합 사슴/늑대는 각 Custom writer라는 현재 분리를 보존한다. Bootstrap 혼용 가드를 유지한다.
- 실행 중 UBT/dotnet/Unreal Editor/Live Coding/MSBuild/ShaderCompileWorker를 확인한 뒤 직접 UBT `AdaptiveEcosystemEditor Win64 Development`를 실행하고 완료까지 기다린다. 실행 중 작업을 중단하지 않는다.

**완료 게이트 A:** 현재 SHA에서 직접 빌드 성공. Box 고갈 이주/기아와 Creature 일반 이동/Shelter/지역 이주가 모두 회귀 통과. 빌드만 통과하고 동물 속도를 0으로 만드는 수정은 완료로 인정하지 않는다.

### 작업 B — 복제 갱신·수신 정확성 (예상 2~4인일, A 이후)

- movement 표본과 presentation 갱신의 sequence/revision 관계를 명시한다. 첫 권고는 transport payload revision과 실제 movement 표본 시각을 구분하는 계약이다. 위치가 그대로인 표현 변경을 새 위치 표본으로 취급하지 않는다.
- accepted 변경이 stale 검사에 막히지 않도록 송신·수신을 함께 바꾼다. HP/Energy의 중복 byte 경로와 round/truncate 차이를 하나의 규칙으로 맞춘다.
- 먼저 재현할 회귀: 위치/HP 고정 + velocity만 변경, flag만 변경, 동일/이전 sequence, 작은 teleport+reset, Remove→동일 ID 재진입, 재접속 후 stale binding.
- Creature 표시가 서버 표본/reset을 소비하게 연결한다. 로컬 프레임 Sequence를 서버 수신 revision으로 사용하지 않는다.

**완료 게이트 B:** 별도 서버+Client에서 위 변경을 실제 수신·표현. 중복/과거 표본은 재적용 0회. reset/첫 진입은 snap, 일반 이동은 정의된 표본 시간으로 보간. 순수 단위 테스트 통과와 실연결 검증을 둘 다 기록한다.

### 작업 C — RL의 필수 버그 수정 통합 (예상 2~4인일, RL 담당 공동)

- `f431e33` 생존 필터, `bc0b365` 시간 스케줄, `3abe777` heading, `4c33405` 피식 EMA 및 후속 보정의 최종 구현을 작은 범위로 검토한다. 오늘 main 병합 `e5b849a`의 충돌 해결도 참고한다.
- 최신 브랜치 전체를 가져오는 방식 대신 V1 수정 묶음과 V3 Python 실험을 분리한 PR을 권고한다. 해당 수정은 기존 커밋을 무조건 cherry-pick하면 해결된다고 가정하지 않는다.
- M4의 Social Request/Feedback, ConstrainStep, bPredated, StableAgentId, 시각 payload를 유지한다. 조향↔포획의 ExecuteAfter 순환을 검사한다.
- 관측 5 전역/지역 선택은 §4 결정 이후 적용한다. 분모를 고치는 작업과 feature 의미를 바꾸는 작업을 검증표에서 분리한다.
- 20/30/60FPS와 긴 frame에서 정책 결정 횟수·EMA 감쇠·포획 사건을 따로 기록한다. 정책 시계 수정이 포획의 FPS 독립성까지 보장한다고 쓰지 않는다.

**완료 게이트 C:** 죽은 개체의 정책·이동·이웃 집계 배제, FPS별 정책 주기 일치, 최종 속도 기반 heading, EMA 분모 검증, cycle 0. V1 기존 Golden과 Creature/Social 회귀 통과.

### 작업 D — 공통 생명주기 결과 확정 (예상 5~8인일)

- [P1 계획](P1_AUTHORITY_LIFECYCLE_INTEGRATION.md)을 실제 Creature에 연결한다. 우선 clock/feeding/death/migration/summary의 공통 결과 경계부터 재사용한다. 종별 행동 writer를 전부 재작성하는 작업으로 확대하지 않는다.
- Energy 대사·지급 환산·기아 유예/피해는 종별 adapter를 통해 제공한다. Box 값을 사슴/늑대에 일괄 적용하지 않는다. V3는 나중에 행동·보행별 대사/섭식을 같은 adapter로 공급한다.
- Death 결과에 Epoch/Step/StableAgentId/Region/Species/Cause를 유지한다. 포식 사건에는 필요한 predator ID·보상 receipt를 연결한다. 원인 모를 외부 피해를 포식으로 추정하지 않는다.
- HP=0, Alive 제거, 예약/pending feeding/Travel 정리, Death 기록, Population/PredationHistory, proxy 제거를 한 결과 수명으로 관리한다. 구조 변경 뒤 fragment 참조를 재취득한다.
- feeding 결과는 이번 step ID lookup으로 적용하되 ID/handle/Alive/epoch/step/이전 적용 여부를 검증한다.
- 동일 completed step의 지역×종 Population, Energy, Food, Birth/Death/이주를 집계한다. 전환한 Entity만 기존 Creature 생존 pass에서 제외한다.

**완료 게이트 D:** 동일 개체의 대사·지급·사망 결과 중복 0. Box와 Creature는 설정 차이가 설명 가능하며 결과 적용·집계 규칙은 동일. 과밀 출발 제한·예정 유입/유출·실제 도착은 동물 경로에서 재검증.

### 작업 E — 3지역 폐루프와 실제 환경 압력 (예상 3~5인일, World/Social 공동)

- 현재 3지역 맵·사슴/늑대를 고정 fixture로 사용한다. 플레이어 또는 포식 압력 한 종류, Food shortage 한 종류로 시작한다.
- World 담당은 논리 clock→시각 하늘과 날씨→지역 EnvironmentState adapter를 제공한다. Ecology는 그 입력이 어느 자원 공급/재생 규칙에 영향을 주는지 정의한다.
- 현 V1 관측에 들어가지 않는 환경 필드를 추가해도 학습이 그것에 반응했다고 주장하지 않는다. 계약에 허용된 Food/위험 feature의 변화를 통해 연결하거나 V3 새 계약에서 직접 반영한다.
- 고갈·공급회복·피식·위협 clear·이주 중 죽음·은신처 실패를 각각 주입해 다음 관측까지 추적한다. 기본 Food 재생 0 시나리오와 반복 시연 preset을 별도 유지한다.

**완료 게이트 E:** `환경/플레이어 압력 → 권위 지역 상태 → 개별 관측/정책 → Social/이동 → 섭식·피식·사망·이주 → Food/Population/다음 관측`을 동일 ID·step 로그로 추적. 눈에 보이는 날씨 변화만으로 완료 처리하지 않는다.

### 작업 F — Client 비용 제한과 측정에 따른 최적화 (예상 6~10인일)

- [P2](P2_PROFILING_AND_BASELINE.md) 계측은 A/B 이후 곧 시작한다. D 이후 동일 fixture로 다시 비교한다. 서버 simulation, 복제, Client Actor/애니메이션을 따로 측정한다.
- [P4](P4_CREATURE_REPLICATION_AND_REPRESENTATION.md): 연결 전체 relevance/Add budget, Actor budget, 전환 hysteresis, pooling, 재바인딩 reset을 실제 적용한다. Template마다 예산을 따로 적용해 합계가 넘는 구현을 피한다.
- [P3](P3_SPATIAL_AND_QUERY_OPTIMIZATION.md): step ID lookup과 단일 지역×종 집계부터. 감각 broad phase는 기존 grid를 재사용하고 brute-force 결과와 비교한다.
- [P5](P5_PARALLEL_PROCESSING_AND_TIME_SCHEDULING.md): 측정된 순수 계산만 snapshot→worker→GameThread commit으로 옮긴다. UObject/LOS/예약/자원을 worker에서 직접 변경하지 않는다.
- [P6](P6_SIMULATION_LOD_AND_SCALE_VALIDATION.md): 먼저 ID/Fragment를 유지하며 비싼 계산 주기만 줄인다. 화면 밖의 생존·예약 lease·이주·Population은 계속 관리한다.

**완료 게이트 F:** 정한 기기/Client 수/개체 수에서 성능 예산과 기능 불변 조건 모두 충족. p50/p95/p99, hitch, 메모리, packet/wire bandwidth를 기록. 테스트 목표 수치를 지원 규모로 발표하지 않는다.

## 6. V3 전환에 대한 판단과 wonkii의 담당 범위

오늘 추가된 [RL V3 Unreal 통합 계획](https://github.com/dpqksr5501/AdaptiveEcosystem/blob/9dd13935f42a43a6e2228e891c051b66aaa6472d/AdaptiveEcosystem/Docs/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md)은 중요한 입력이다. main을 RL 브랜치로 합치는 단계는 오늘 커밋에서 빌드·64개 자동화 성공으로 보고되어 있다. 문서 본문의 아직 합쳐야 한다는 일정은 그 후속 커밋과 구분해서 읽는다.

| 항목 | 현재 production V1 | V3 제안 | wonkii가 먼저 준비할 것 |
| --- | --- | --- | --- |
| 정책 | 7관측/4연속 행동 가중치 | R1b 18관측/5 logits, R2 19관측/5 logits. sleep은 마스크로 막힌 상태 | Policy schema/model/mask/contract hash 구분. 기존 payload·Entity와 혼용하지 않는 설정 |
| 행동 | V1 Raw→Social 보정→Steering | 이산 행동+Arbiter+행동 제어기. V3에서 Social 강제 은신/출력 보정 우회 제안 | 행동 ID/phase/gait/sequence/start time의 복제 의미. 이주/죽음 우선순위 |
| 경보/은신처 | Herd Alarm와 유한 예약 슬롯 | M8 경보, 학습 은신 규칙·무정원 모델 제안 | 권위 주인·mode 전환 시 예약 해제·수신 reset 계약 |
| 생존/생성 | Creature 별도 대사, 재스폰 꺼짐 | 행동·보행별 비용, 시연 재스폰/재생 | 공통 생존 adapter와 Birth/Death 기록. 새 생명은 새 StableAgentId |
| 모델 변경 | 생성 헤더 재빌드 | 개발용 `.ecopol` 검증·안전 지점 교체/되돌리기 제안 | world/step 경계와 모델 revision 전달. 입력 차원·mask 불일치 거부 |

냉정한 평가:

1. R1b 후보의 새 시드 통과는 Python 평가 근거다. 해당 계획서는 FSM 우세를 보고하지만 R_base와의 우세는 보고하지 않는다(t=-0.89). Unreal에서 V3가 더 낫다는 결론은 아직 없다.
2. “학습 범위의 일부만 게임에 사용”은 합리적인 출발점이지만 안전성 증명은 아니다. 속력·은신처·밀도·리스폰·지각의 조합, 슬롯 경쟁·지형·네트워크·이주가 새로운 분포를 만든다. 레벨 복제 평가와 실제 Unreal 비교가 모두 필요하다.
3. 1.5m/4슬롯 Shelter를 8~12m/무정원으로 바꾸거나 Social을 끄는 것은 밸런스 미세 조정이 아니라 시스템 의미 변경이다. 기존 Social 통합의 가치를 보존할지 학습에 포함할지 팀 결정으로 처리한다.
4. 현재 V1 계약에서 18/19 관측과 5 logits로 조용히 교체할 수 없다. 별도 계약·태그·생성 헤더 namespace·모드별 순서·Golden이 먼저다.
5. 반복 시연의 개체 보충은 관찰 편의를 위한 공급 규칙이다. 번식·장기 생태 평형의 증거가 아니다. 재생/리스폰을 켜서 전멸을 가리는 평가를 피한다.

**wonkii의 V3 우선 책임은 학습 개발보다 공통 생명주기, StableAgentId, 행동 상태 복제, 완료 step, Client 표현 reset이다.** 관측·마스크·Arbiter·위협 수치·Export·학습 평가는 RL 담당이 소유한다. 같은 Entity의 최종 이동 writer는 하나로 유지한다.

V3 완료 게이트: 순전파뿐 아니라 관측/마스크/argmax/Arbiter 다중 step/제어기/경보/위협 Golden, UBT·자동화, 평면 맵→실맵 비교, 별도 서버/Client 행동 상태 수신. R2는 보고와 후보 결정 이후 도입하며 실패 시 계약이 맞는 이전 후보/검증된 규칙 모드로 남는다.

## 7. 실제 먹이사슬·다종·두 대륙은 언제 하는가

현재 FoodHint는 분포 중심 표시이고 실제 식물 잔량이 아니다. 사슴은 지역 밀도와 Forage에 따라 먹이를 받는다. 이를 식물까지 접근해 먹는 게임으로 확장하려면 [먹이사슬 계획](../Architecture/FOOD_CHAIN_AND_BP_REPRESENTATION_PLAN.md)의 권위 자원 레코드가 필요하다.

권고 순서:

1. **D/E 완료 뒤 한 지역의 소수 authored 식물 자원**: ResourceId/위치/잔량/Revision, 도달·거리·식성 검증, 경합 배분. 지역 Food는 동일 원장의 합계로 유지하고 중복 차감하지 않는다. 기존 Box 지역 식사는 검증 모드로 유지한다.
2. **한 초식종+한 포식종의 에너지 루프**: 사슴 실제 지급량, 늑대 실제 포식 성공 보상, 각 종의 생존·사망·집계. 늑대 이주는 먹잇감/에너지 기준으로 설계하며 식생 Food 기준을 그대로 쓰지 않는다.
3. **다종 정의 데이터화**: Species와 Role/식성/먹잇감 관계·Config·표현 에셋을 분리. conspecific 관측이 다른 초식종까지 세지 않게 한다. V1 공유 정책이 모든 새 종에 적합하다고 가정하지 않는다.
4. **두 대륙과 unload 계약**: UWorld 전체 RegionId 고유성, 논리 상태와 작성 Actor 수명 분리, 스트리밍 off에도 ID/Food/Population 유지. 대륙 경계·원거리·이주·Late Join 검증.

식물 접근/슬롯/지각을 실제 학습 동역학으로 바꾸면 RL 평가·필요시 재학습도 동반한다. V3 이식과 공간 식물/다종을 한 번에 넣으면 행동 실패 원인을 분리하기 어렵다. 먼저 어느 기능을 시연 필수로 할지 지정한다.

장기 지속 월드가 제품 목표일 때만 저장/복원·ID 발급 상태·spawn cursor·사건 중복 방지를 필수 단계로 승격한다. 짧은 로컬 시연과 같은 완료 기준으로 묶지 않는다.

## 8. 팀 역할과 인계 산출물

실제 작업 배정·일정 승인 전의 권고안이다. 이번에 다른 사람에게 메시지를 보내거나 PR을 작성하지 않았다.

| 담당 | 우선 작업 | 상대방에게 넘겨야 할 산출물 |
| --- | --- | --- |
| wonkii | A/B/D, 계측·복제 예산, 공통 ID/clock/outcome, V3 상태 복제 | 빌드 가능한 SHA, 생명주기/자원 API와 불변 조건, DTO·수신 계약, 재현 로그/trace |
| sinhyeok04 | C의 최종 버그 수정 분리, V1 feature 결정, V3 계약/Export/Golden, 레벨 복제 평가·R2/R3 | main 기준의 작은 수정 PR, policy/mask/version, 수치·시간·ID 규칙, 후보별 평가와 Unreal 적용 조건 |
| 조연우 | 이동/예약 회귀, 공통 생존 adapter 연결, V3 경보·Shelter 경계, 늑대/표현 | 모드별 writer·우선순위·예약 정리 표, 행동 표시 상태, 실제 도착/막힘/Client 회귀 |
| avaroki | 환경 adapter, authored Shelter/식물·스폰·충돌, 실맵 이주 구간, cook/HLOD | 재현 가능한 맵 preset, 배치 값·도달 가능성, 지역 환경 입력과 스트리밍 조건 |

공통 편집 파일은 EcoBehaviorProcessors.cpp, EcoMassMigration.*, EcoCreatureIntegrationSpawner.*, ReplicationTypes/Replicator/Bubble이다. 파일별 주 편집자를 지정하고 작은 PR을 먼저 합친다. 병렬 작업은 서로 독립된 계약/파일에 한정하며 완료되지 않은 PR을 서로의 기준선으로 쌓지 않는다.

## 9. 일정과 범위 관리

시연 마감과 실제 가용 시간이 정해지지 않았다. 아래는 순개발 인일 기준의 추정이며 실행 환경/LFS/빌드/에셋 오류가 생기면 늘어난다. A~F의 표기 단순 합은 약 19~34인일이다. 협업·리뷰·병합 회귀와 V3 공동 작업을 포함하면 wonkii 계획에는 **25~40인일의 여유**를 두는 것이 현실적이다. 실제 학생/업무 일정의 달력 기간은 별도로 계산해야 한다.

| 구간 | 시작 조건 | 우선 산출물 |
| --- | --- | --- |
| 즉시, 10/13~10/16 목표 | 현재 Source 대조 완료 | A 복구, B 재현, §4의 정책 feature/모드/생존 경계 결정 기록 |
| 이후 첫 1~2개 개발 주 | A 통과, feature 의미 결정 | B/C 완료, D의 사망·feeding 공통 경계, 19개체/1~2 Client smoke |
| 다음 1~2개 개발 주 | D의 결과/시간 계약 안정 | D/E 통과, 64/128개체 baseline, Client 표본/예산 적용 |
| 다음 2~3개 개발 주 | baseline과 V3 계약 준비 | 측정된 F 항목, V3 상태 복제/생명주기 연결, cooked 서버/Client smoke |
| 추가 범위 | 위 게이트 통과와 시연 우선순위 결정 | authored 식물, 다종, 두 대륙, 지속성·대규모 확장 |

RL 새 계획의 10/16~11/11 계약·C++ 이식, 11/11~11/20 실맵 검증은 해당 담당자의 초안 일정이다. main 합치기는 후속 커밋에서 이미 완료로 보고됐다. 남은 일정은 팀 의존성·계약 결정·M4 복구와 함께 재산정한다. 11월 20일까지 식물/다종/두 대륙/시즌 재학습까지 모두 완료하는 일정으로 읽지 않는다.

마감이 짧으면 A/B/C와 최소 D/E, 소규모 서버/Client 검증에 집중한다. 암사슴 변형, 추가 연출, 물/갈증, 두 대륙, 자동 Cover, ORCA, 원거리 집계, 시즌 재학습은 후순위다. 가중치 로더를 제외할지는 RL 쪽 사용자 결정과 팀 합의를 확인해 정한다.

## 10. 검증표와 정량적 완료 조건

### 기능·권위 검증

| 시나리오 | 기대 결과 / 기록 |
| --- | --- |
| 먹이 경합·중복 요청·늦은 결과 | 지급 합계≤가용량, 음수 Food 0, Energy는 실제 지급량만 증가, 결과 중복 적용 0 |
| 기아/포식/외부 피해 동시 후보 | 정의된 우선순위로 Death 1회. 다른 원인이 자동 포식 기록으로 바뀌지 않음 |
| Shelter→이주/죽음/실패/위협 clear | 이전 ReservationId 해제, lease 누수 0, 과거 Feedback이 새 예약을 바꾸지 않음 |
| A→B 이주 | 같은 StableAgentId, 실제 도착 후 Region 변경, 세계 인구 보존, 원인·출발/도착 시간 보존 |
| 재접속/Late Join/Off→재진입 | 현재 ID/생존/Region/행동 상태 수신, stale Actor/애니메이션/Notify 0 |
| 다른 거리의 Client 2개 | 각자 다른 relevance/LOD를 사용하면서 서버 논리 상태는 한 벌. Client Vitals/Policy/Social 권위 실행 0 |
| 긴 frame/저 FPS | policy 결정·생존·lease의 논리 시간 정의 준수, backlog 관측, 조용한 시간 삭제 0 |
| 지역/표현 unload | 표현 off로 논리 Death/Population 감소가 생기지 않음. 지원하지 않는 coordinator unload는 명시적 제한 |

공통 회계:

```text
Food_end = Food_start + 실제 공급 + 실제 재생 - 실제 지급 - 명시적 손실
Alive_end = Alive_start + 성공 생성 - 단일 사망 - 명시적 논리 Despawn
지역 Population 변화 = 생성 - 사망 - Despawn + 이주 유입 - 이주 유출
세계 Population에서 이주 유입/유출 합계 = 0
동일 Epoch의 StableAgentId 중복 = 0
같은 사건의 Food/Energy/Death/Predation 중복 반영 = 0
```

상한 clamp의 넘침은 손실 항목으로 기록한다. 시각 Actor 파괴와 논리 Despawn을 구분한다. 한 step의 여러 생성으로 SummaryRevision이 반복되는 경로도 검증한다.

### 규모·성능 검증

- 순서: 실맵 기본 19 → 64 → 128 → 256 → 512. 각 단계에서 기본 스폰/충돌·개체군 불변 조건을 먼저 통과한다.
- 현재 Creature 초기화에는 GlobalPopulationLimit 512 상한이 있다. 1,000/5,000개 시험은 상한·spawn fixture·예산을 확장한 이후의 별도 목표다. 숫자만 바꿔 지원 규모를 선언하지 않는다.
- Client 1/2/4, 밀집/분산, 정지/이동, 대량 진입, 이주/죽음 burst를 나눠 측정한다. 실제 렌더 Client와 NullRHI 결과를 구분한다.
- 예산 제안: 30Hz 서버와 60FPS Client를 선택한다면 총 frame 예산은 각각 약 33.3ms/16.7ms다. 생태계·네트워크·표현에 줄 부분 예산은 목표 기기 baseline 후 정한다.
- 5분 warm-up 뒤 15분 성능 캡처, 최소 30분 누수/수명 soak를 초기 검증안으로 권고한다. 지속 월드는 목표 세션 길이로 추가한다. 이 시간은 실행한 기록이 아니다.
- 산출물에는 SHA·엔진·기기·맵·정책/mask/model·seed·개체/Client 수·debug 설정·p50/p95/p99·메모리·사건/queue backlog·trace 경로를 담는다.

### 출하/발표 판정

- Editor UBT 성공, 자동화 통과, PIE, 별도 서버/Client, cooked build는 각각 별도 칸으로 기록한다.
- 현재 에셋/GUID/LFS와 정확히 같은 코드로 cook/패키징한 Server/Client 연결까지 확인한다. uncooked 서버의 정상 실행이 cook/HLOD 검증을 대신하지 않는다.
- 발표 가능한 표현은 “특정 commit·맵·규모·기기에서 확인한 기능”이다. PPO 연구 결과와 Unreal 통합 성능, 시연 유지 장치와 생태 평형을 분리해서 보고한다.

## 11. 실패 시 중단·축소 기준

- **A가 3인일을 넘으면:** 신규 기능을 멈추고 두 정상 부모의 동작 비교·함수별 병합 복구로 집중한다. 문제가 난 M4 전체를 main에 병합하지 않는다.
- **D에서 사건 중복/회계 불일치가 남으면:** 병렬화·Simulation LOD·spawn 확대를 보류하고 completed step/receipt/수명 경계를 먼저 수정한다.
- **V3의 레벨 복제 평가가 실패하면:** 실패를 기록하고 R3 또는 합의된 레벨 조정을 선택한다. 같은 평가를 통과로 보이게 만들기 위해 자원·리스폰·은신 규칙을 임의로 바꾸지 않는다.
- **Client 예산 초과 시:** 관련/표현 개체 수를 낮춰 명시적 지원 프로필을 정한다. 서버 개체를 죽이거나 숨겨 Population을 맞추지 않는다.
- **팀 결정이 늦으면:** A/B, 계측, 공통 ID/outcome 설계, V1 회귀를 진행한다. 결정이 필요한 V3/Social/재생 변경은 적용하지 않는다.

## 12. 바로 시작할 첫 작업 묶음

1. `6235742`의 Replicator와 Migration 병합 잔여를 정리한 **빌드 복구 PR**.
2. 동일 SHA의 Box/동물 두 fixture를 실행한 **기준선 검증표**.
3. velocity/flag-only 갱신의 **복제 stale 재현과 수정 PR**.
4. RL 담당의 오늘 수정에서 V1 필수 수정만 분리한 **협업 PR**, 관측 5·죽음·순서 결정 첨부.
5. 공통 death/feeding commit을 동물에 적용하는 **첫 P1 PR**.

이 다섯 개가 끝나면 wonkii의 M4와 팀원 PR을 실제 통합 기준선으로 평가할 수 있다. 그 다음에 V3 상태 복제와 기능 확장을 같은 기반 위에서 진행한다.

## 13. 근거와 추가 읽기

- [루트 AGENTS.md](../../../AGENTS.md), [Policy V1](../RL_Policy/POLICY_CONTRACT_V1.md), [Mass 순서](../Mass/MASS_PROCESSOR_ORDER.md).
- [조연우 최신 시작 문서](../조연우/README.md), [CURRENT_STATE](../조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md), [Creature 통합](../조연우/CREATURE_PRODUCTION_INTEGRATION.md), [실맵 배치](../조연우/ECOSYSTEM_LEVEL_RUNTIME_PLACEMENT.md), [감각·Notify](../조연우/CREATURE_SENSORY_AND_NOTIFY_REFINEMENT.md).
- [M3 생존 검증](../Roadmap/M3/OVERCROWDING_STARVATION_VALIDATION_REPORT.md), [M4 검증](../Roadmap/M4/M4_VALIDATION_REPORT.md), [10월 11일 감사](WONKII_COMMERCIAL_READINESS_AUDIT_2026-10-11.md), [기존 P1~P6](README.md).
- [현재 wonkii M4 커밋](https://github.com/wonkii/AdaptiveEcosystem/commit/6235742365db42c64fef539ac5841f9adfd4f0e8), [팀 main PR #11](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/11).
- [RL 최신 조회 기준](https://github.com/dpqksr5501/AdaptiveEcosystem/commit/9dd13935f42a43a6e2228e891c051b66aaa6472d), [오늘 RL의 main 병합/64개 테스트 보고](https://github.com/dpqksr5501/AdaptiveEcosystem/commit/e5b849a), [R2 노려보기 제외·경보 세계 전환](https://github.com/dpqksr5501/AdaptiveEcosystem/commit/084c7c7).
- [RL V3 통합 초안 원문, 조회 SHA 고정](https://github.com/dpqksr5501/AdaptiveEcosystem/blob/9dd13935f42a43a6e2228e891c051b66aaa6472d/AdaptiveEcosystem/Docs/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md).

원격 상태는 2026-10-13 조회 시점의 snapshot이다. 이후 PR/브랜치 변경은 다음 구현 시작 전에 다시 확인한다.
