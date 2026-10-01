# M3.2 구현 및 에디터 확인

> M3.3 이후에 아래의 **이주 없는 M3.2 기준값**을 재현하려면 Migration Enabled=false로 설정한다. 현재 통합 이주·Spawn Waves 동작은 [M3.3 에디터 테스트](M3_3_EDITOR_TEST.md)를 따른다.

## 구현/검증 상태

2026-09-28 구현. UE 5.8 `AdaptiveEcosystemEditor Win64 Development` 빌드 성공. 자동화 테스트는 사용자 요청에 따라 작성/실행하지 않았다. 아래 PIE 시나리오는 기대 결과이며 실제 실행 완료 기록이 아니다. 기존 레벨/EntityConfig 에셋과 사용자의 낮밤·스폰 간격 설정은 변경하지 않았다.

새 Fragment와 설정이 있으므로 에디터를 완전히 종료한 뒤 다시 열어 테스트한다. EntityConfig의 기존 `Eco Network Agent` Trait가 서버 템플릿에 새 Feeding Fragment를 제공하므로 소비 Trait를 추가할 필요는 없다.

## 책임과 실행 흐름

| 영역 | 구현 | 책임 |
| --- | --- | --- |
| Core | `EcoResourceTypes.h` | 설정, 소비 요청/결과 envelope, 완료 자원 snapshot |
| World | 기존 `EcoWorldClockSubsystem`/DayCycleProvider | 서버 시간과 Phase 제공 |
| Mass | `EcoMassFeeding.*`, Lifetime/Feeding Fragment | 대상 판정, 개체별 예약/요청/지급 결과 관리 |
| Ecology | `EcologyResourceSimulation.cpp`, `EcoFoodAllocation.*` | 환경 손실 일정, 지역별 비례 배분, 식량 차감 및 보존 확인 |
| 조정 경계 | `EcoMassLifecycleSubsystem` | 순서 연결, 실제 Mass Population 집계, 일일 요약 출력 |

매 처리 시각에 환경 이벤트 → 현재 식량에 따른 스폰 → 소비 요청/배분/결과 적용 → 완료 자원 snapshot → 해당하는 경우 일일 요약 순으로 실행한다. 이전 시각 작업이 끝나야 다음 시각으로 진행한다. 최대 0.25초 간격을 Phase 경계·웨이브·이벤트·개체 소비 예정 시각에서 더 나누며, 프레임당 최대 8회까지 처리하고 나머지는 다음 프레임에 이어서 처리한다.

MVP에서는 별도 자동 Tick Processor를 등록하지 않고 GameThread에서 명시적인 동기 Mass pass를 호출한다. 요청은 먼저 개체별 Fragment에 쓰고, 순차 gather가 끝난 뒤 Ecology batch API를 호출한다. Entity loop 안에서 UObject를 호출하거나 병렬 worker가 공유 요청 배열을 수정하지 않는다. 모든 로컬 쿼리는 같은 World의 EntityManager로 초기화한다. 향후 병렬화 시 수집 단계와 완료 barrier를 별도로 유지해야 한다.

WorldEpoch + StepId + StableAgentId + 예정 시각으로 요청을 구별한다. 중복/낡은 요청은 지급하지 않는다. 지급량이 0이어도 다음 소비 시각은 진행한다. 결과 적용 전 ID/Region/예약/Resident 상태를 다시 확인한다. 실패하면 해당 실행을 중단하며 동일 요청을 자동 재지급하지 않는다.

식량은 0 이하로 내려가지 않고 재생되지 않는다. 요청량이 부족한 식량 이상이면 정확히 0으로 만든다. 그 외 양수 잔여량을 임의의 고갈 epsilon으로 없애지 않는다. float 저장 오차는 `Rounding`에 기록하며 보존 허용 오차는 `1e-6 * max(1, FoodBefore)`이다. `Before - EventLoss - Consumed - Rounding = After`를 확인한다.

M3.3이 사용할 `GetResourceSnapshots()`는 마지막 완료 StepId와 지역별 Food/Capacity/Depleted를 반환한다. 개체별 `LastGrantedAmount`, `TotalGrantedAmount`는 Mass에 남으며 Energy/HP는 바꾸지 않는다. 현재 Traveling 개체는 소비 대상에서 제외한다. M3.3에서 Waiting 상태와 도착 후 `NextFeedTime = 도착 + Interval` 연결이 필요하다. 사망/장시간 개체 교체가 도입되면 Ecology의 개체별 소비 receipt watermark 제거도 함께 연결한다.

## 편집 항목

**Project Settings → Adaptive Ecosystem → M3**에서 변경한 뒤 PIE를 재시작한다. 시뮬레이션 규칙은 시작 시 복사되며 실행 도중 설정 변경을 반영하지 않는다.

| 항목 | 기본값 | 의미 |
| --- | --- | --- |
| Resources / Feeding / Enabled | true | 개체 정기 소비 |
| First Feed Delay Seconds | 20 | 실제 생성 후 최초 소비 유예 |
| Interval Seconds | 10 | 다음 소비 간격 |
| Amount | 1 | 1회 요청량 |
| Day Food Event / Enabled, Region Id | false, Forest_A | 기본 비활성화. 자동 낮 이벤트를 확인할 때만 활성화 |
| Day Food Event / Phase Fraction | 25/60 ≈ 0.416667 | 해당 낮의 약 41.67% 시점 |
| Night Food Event / Enabled, Region Id | true, Forest_B | 밤 이벤트 대상 |
| Night Food Event / Phase Fraction | 0.25 | 해당 밤의 25% 시점 |
| 두 이벤트 / Food Loss | 각각 40 | 1회 요청 손실 |
| Print Resource Changes | true | 이벤트와 소비/보존 로그 |
| Population / Enable Spawn Waves | true | 추가 웨이브만 제어, 초기 생성은 유지 |
| Print Daily Population | true | 매일 낮 시작 지역별/전체 실제 개체 수 |
| Print Daily Population To Screen | true | 서버 화면에도 8초간 출력 |

이벤트 fraction 범위는 `0 이상 1 미만`이다. 0이면 Phase 시작에 발생하며, 최초 초기 개체 생성 뒤 적용한다. 기본값은 60초 낮밤에서는 낮+25초/밤+15초, **10초 낮밤에서는 낮+약 4.167초/밤+2.5초**가 된다. 이벤트 대상 이름은 실제 RegionId와 맞춰야 한다. 한 Phase마다 한 번 발생하며 Food를 초기화하지 않는다.

초기 식량/Capacity는 기존처럼 각 `EcologyRegion` Details에서 지정한다. 화면의 논리 개체 수는 Actor Outliner 수가 아니라 서버 Mass의 Alive Entity 수다. Client 표현 개수는 relevancy/LOD에 따라 다를 수 있다.

## 1. 사용자 설정으로 스폰 개수만 확인

1. 각 Bootstrap에 초기 8개, 낮 간격 5초/수량 4, 밤 간격 4초/수량 6, 지역 상한 64를 설정한다. Project Settings에서 낮밤 각각 10초/전체 상한 128을 유지한다.
2. 두 지역 식량을 양수로 설정하고, Feeding Enabled와 Day/Night Event Enabled를 모두 끈다. Enable Spawn Waves와 Print Daily Population은 켠다.
3. Standalone으로 실행한다. Output Log에서 `Eco Daily`를 검색한다. 콘솔 `mass.debug.DrawAllEntities 1`로 위치를 확인할 수 있다.

Phase 종료 시각은 제외되므로 낮은 +5초 한 번, 밤은 +4/+8초 두 번이다. 한 지역의 하루 증가량은 `4 + 6 + 6 = 16`이다.

| 낮 시작 | 서버 시간 | A AliveEntities | B AliveEntities | 전체 | 지역별 Delta |
| --- | --- | --- | --- | --- | --- |
| 1일차 | 0 | 8 | 8 | 16 | 0 (기준값) |
| 2일차 | 20 | 24 | 24 | 48 | +16 |
| 3일차 | 40 | 40 | 40 | 80 | +16 |
| 4일차 | 60 | 56 | 56 | 112 | +16 |
| 5일차 | 80 | 64 | 64 | 128 | +8 (상한) |
| 이후 | 100, 120… | 64 | 64 | 128 | 0 |

`[Eco Daily]`에는 Day, Epoch, Step, Due, Observed, Region, AliveEntities, Delta, Food를 출력하고 `[Eco Daily Total]`에는 같은 집계의 합을 출력한다. Due는 처리 기준 서버 시각, Observed는 실제 처리 프레임의 서버 시각이다. 지연 프레임에서는 차이가 커질 수 있다. 실제 생성된 개체의 첫 소비는 `[Eco Spawn]`의 Born + FirstFeedDelay를 따른다.

이 표는 자원 압력/사망/이주가 없는 기준값이다. M3.2 소비/이벤트를 켜 식량이 고갈되면 그 지역의 추가 스폰이 중단되므로 더 작은 수에서 유지될 수 있다. 기존 첨부 로그에는 일일/스폰 기록이 없어 그 실행이 이 표를 충족했다고 소급 확정할 수 없다.

## 2. 소비만으로 고갈

1. Enable Spawn Waves=false, Feeding Enabled=true, Day/Night Event Enabled=false.
2. A 초기 식량 24, 초기 개체 8. 소비 유예 20초/간격 10초/요청량 1.
3. 실행 후 `Eco Food`를 검색한다. A에서 다음을 확인한다.

| 서버 시간 | 요청 수 | 실제 소비 합 | 남은 식량 |
| --- | --- | --- | --- |
| 0~20초 전 | 0 | 0 | 24 |
| 20초 | 8 | 8 | 16 |
| 30초 | 8 | 8 | 8 |
| 40초 | 8 | 8 | 0 |
| 50초 | 8 | 0 | 0 |

Food가 0이어도 개체 수는 8로 남아야 한다. 매 프레임 소비가 반복되지 않고 10초 간격 예약이 유지되어야 한다.

## 3. 식량 부족 배분

소비만 켠 상태에서 A 초기 식량 5, 초기 개체 10, Amount=2로 재시작한다. 최초 소비에서 요청 10개, 실제 지급 합 5, 잔여 0이어야 한다. 비례 배분 규칙상 각 개체 지급량은 0.5다. 서버 로그로 합계를 확인하고 개별 지급량은 Mass Feeding Fragment의 `LastGrantedAmount`에서 확인한다.

## 4. 이벤트만으로 고갈

1. Feeding Enabled=false, Enable Spawn Waves=false. Day/Night Event를 모두 켠다. Day Event는 기본 비활성화되어 있으므로 명시적으로 활성화한다.
2. A/B 초기 식량 각각 40, Food Loss 각각 40. 낮밤 길이는 10초, 이벤트 fraction은 기본값.
3. A는 서버 약 4.167초, B는 12.5초에 각각 Food=0이어야 한다. `Eco Food Event`의 Phase/Cycle/Region과 `ActualLoss=40`을 확인한다.
4. 다음 날에는 같은 이벤트가 Phase당 한 번 발생하되 ActualLoss=0이다. 소비 로그의 Consumed는 0이고 개체 수는 그대로다.

## 5. 통합 및 시간 충돌

소비/이벤트/추가 스폰을 모두 켜고 실행한다. 적은 식량의 A와 충분한 식량의 B를 비교한다. A가 고갈되면 `Eco Spawn Skipped`가 나오고, 일일 요약의 A 개체 수 증가가 멈추며 B는 계속 증가해야 한다. 이동은 M3.3 범위이므로 고갈 지역의 개체가 남아 있는 것이 정상이다.

동시 시각 검증은 Day Event fraction=0.5, First Feed Delay=5, A 식량=40, 이벤트 손실=40, 낮 스폰 간격=5로 실행한다. 5초에 이벤트가 먼저 식량을 0으로 만든 뒤 추가 스폰이 생략되고, 초기 개체의 소비 지급은 0이어야 한다. 같은 이벤트 key나 같은 소비 예약이 반복 적용되면 안 된다.

Standalone 확인 후 Listen Server + Client에서 서버의 자원/일일 로그가 하나의 권위 흐름으로 기록되고 기존 Box 표시가 유지되는지 확인한다. Client 자원 요약 복제는 M3.3에서 연결한다. 같은 프로세스 PIE의 화면 Print는 창 간 공유될 수 있으므로 월드 이름/Epoch가 있는 로그를 기준으로 판정한다.

## 이번 빌드에서 함께 수정한 사항

새 파일 추가로 Unity 빌드 묶음이 바뀌면서 기존 Social/Debug 코드의 `FEcoAliveTag` include 누락이 드러났다. 해당 6개 cpp에 `Mass/EcoMassTags.h`를 명시적으로 추가했다. 해당 코드의 동작은 변경하지 않았다. 엔진/플러그인 deprecation 경고는 남아 있다.

## 수동 기아 Debug 이벤트

서버/Standalone PIE 게임 뷰포트 콘솔에서 `Debug.Starvation.Forest_A`를 실행한다. `Forest_A`는 배치된 `EcologyRegion`의 `RegionId`여야 한다. Forest_A의 낮 자동 이벤트는 기본 비활성화되어 있으므로 이 명령 없이 A가 자동 고갈되지 않는지 먼저 확인한다. 명령 시각에 맞춘 자원 단계에서 A의 Food가 0이 되며, `Eco Food Event`에 `Source=Debug.Starvation`, `Eco Food`에 `After=0`, `Depleted=1`이 기록된다. B는 별도의 밤 자동 이벤트 또는 소비가 있을 수 있으므로 그 영향을 분리하려면 Night Event와 Feeding도 끈다. `Debug.Starvation Forest_A` 일반형도 지원한다. 재사용 가능한 등록 방식은 [Debug 명령 문서](../../Debug/DEBUG_COMMANDS.md)를 참고한다. M3.2에서는 고갈 후 추가 스폰만 중단하며 기존 개체의 이동은 M3.3에서 연결한다.
