# 과밀 재이주·기아 사망 에디터 테스트

기준 UE 5.8. 아래는 자동화 테스트가 아닌 수동 PIE 설정과 확인 절차다. 기존 작업 레벨과 EntityConfig를 복제한 테스트 레벨에서 진행하고, 설정 변경 후 PIE를 다시 시작한다. BP Bootstrap 인스턴스의 기존 값이 클래스 기본값보다 우선할 수 있으므로 각 인스턴스 Details를 확인한다.

## 1. 기능별 파일 연결

| 기능 | 연결된 파일 | 책임 |
| --- | --- | --- |
| 설정·값 계약 | [EcoSurvivalTypes.h](../../../Source/AdaptiveEcosystem/Core/EcoSurvivalTypes.h), [EcoRuntimeSettings.h](../../../Source/AdaptiveEcosystem/Core/EcoRuntimeSettings.h) | Survival/Overcrowding 세션 설정·DeathOutcome·계획 수요 |
| 개체 상태/역할 | [EcoMassFragments.h](../../../Source/AdaptiveEcosystem/Mass/EcoMassFragments.h), [EcoMassNetworkTrait.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassNetworkTrait.cpp) | Authority 전용 대사 시각·기아 시간·Death 상태. Client에는 추가하지 않음 |
| 지역별 초기화 | [EcoMassNetworkBootstrap.h](../../../Source/AdaptiveEcosystem/Mass/EcoMassNetworkBootstrap.h), [EcoMassNetworkBootstrap.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassNetworkBootstrap.cpp) | 초기 Energy 비율, 지역 Comfort, 초기 시각과 ID |
| 실제 섭취 회복 | [EcoMassFeeding.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassFeeding.cpp) | 배분 결과 전체 검증 후 GrantedAmount × FoodEnergyGain을 1회 적용 |
| 대사·기아·사망 | [EcoMassSurvival.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassSurvival.cpp) | 시간 적분, lethal 원인, Alive 제거, 정지, Dead 잔류 후 파괴 |
| 인구/식량 압력·기록 | [EcoPopulationPressure.cpp](../../../Source/AdaptiveEcosystem/Ecology/EcoPopulationPressure.cpp), [EcologySimulationSubsystem.cpp](../../../Source/AdaptiveEcosystem/Ecology/EcologySimulationSubsystem.cpp) | 실제/예상 인구, 히스테리시스, 이주·사망 이력, 유입 고려 Spawn |
| 분산 재이주 | [EcoMassMigration.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassMigration.cpp), [EcoMigrationTypes.h](../../../Source/AdaptiveEcosystem/Core/EcoMigrationTypes.h) | 도착 후 판단, 시급성·ID 순서, 예정 유입 반영, quota/cooldown, 실패 목적지 |
| 실행·보존 검사 | [EcoMassLifecycleSubsystem.cpp](../../../Source/AdaptiveEcosystem/Mass/EcoMassLifecycleSubsystem.cpp) | 대사→사망→자원·섭취→도착→판단→집계·요약, Births−Deaths=Alive 검사 |
| Client 전달 | [EcologyNetworkTypes.h](../../../Source/AdaptiveEcosystem/Network/EcologyNetworkTypes.h), [EcoMassReplicator.cpp](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp), [EcoMassClientBubble.cpp](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.cpp) | GameState 지역 요약, health/energy/life 표본, 프록시 수신/Remove |
| 수동 진단·표시 | [EcoMassNetworkDiagnostics.cpp](../../../Source/AdaptiveEcosystem/Debug/EcoMassNetworkDiagnostics.cpp), [EcoMigrationDebugSubsystem.cpp](../../../Source/AdaptiveEcosystem/Debug/EcoMigrationDebugSubsystem.cpp) | ID·Vitals·Travel·Death, 지역 압력·인구, 선택적 HP/Energy/DEAD 라벨 |
| 음식 고갈/회복 | [EcoStarvationDebugSubsystem.cpp](../../../Source/AdaptiveEcosystem/Debug/EcoStarvationDebugSubsystem.cpp), [EcologyResourceSimulation.cpp](../../../Source/AdaptiveEcosystem/Ecology/EcologyResourceSimulation.cpp) | 권위 콘솔 요청을 다음 자원 단계에 적용, 공급까지 보존 장부에 기록 |

표시용 Actor가 논리 상태를 소유하지 않는다. 기존 Box/ISM 표현으로 충분하다. 특성 생성·PPO/Social 이동 통합·사체 자원·HP 회복·네트워크 사망 ACK는 이 Box 기반 작업에 포함하지 않는다.

## 2. 공통 레벨 준비

1. `AEcologyRegion` 두 개: RegionId=`Forest_A`/`Forest_B`, 서로 AdjacentRegionIds에 등록. RegionBounds가 spawn grid 전체와 ArrivalOffset 위치를 포함해야 한다.
2. Region마다 `AEcoMassNetworkBootstrap` 하나. RegionActor로 해당 Region에 바인딩한다. EntityConfig는 같은 Eco Network Agent + 기존 Box 표현/엔진 이동 구성으로 유지한다.
3. `SpawnSchedule.RegionPopulationLimit=64`, 전체 초기 인구 합보다 큰 `GlobalPopulationLimit`(기본 128). **RegionPopulationLimit는 추가 Spawn 상한**, `EcologicalComfortPopulation`은 아래 시험별 생태 혼잡 기준이다.
4. Project Settings → Adaptive Ecosystem에서 `bEnableSpawnWaves=false`, DayFoodEvent/ NightFoodEvent의 Enabled=false로 바꾼다. 현재 저장소 설정에는 NightFoodEvent가 켜져 있으므로 명시적으로 끈다.
5. `bDrawMigrationDebug=true`, `bDrawSurvivalDebug=true`. 둘을 함께 켜야 개체 HP/Energy/DEAD 라벨이 보인다. 대규모 측정 때는 개체 라벨을 끈다.
6. 테스트 GameMode가 `AEcoGameState`를 사용하고 기존 Mass queue 호환 설정을 유지하는지 확인한다. Simulation LOD, PPO Herbivore 또는 custom/spring movement를 기존 Box 이주에 섞지 않는다.

## 3. 실제 섭취와 Energy 유지

| 설정 위치 | 값 |
| --- | --- |
| 각 Region | InitialFoodAmount=500, FoodCapacity≥500 |
| 각 Bootstrap | InitialAgentCount=8, InitialEnergyRatio=1, Comfort=64 |
| Survival | Enabled=true, BaseMetabolism=1, TravelMetabolism=0.5, FoodEnergyGain=12 |
| Feeding | Enabled=true, FirstFeedDelaySeconds=5, IntervalSeconds=10, Amount=1 |
| Migration / Overcrowding | 둘 다 Enabled=false |

Standalone을 60초 실행한다. Energy는 식사 사이 감소하고 실제 식사 때 회복한다. HP는 유지한다. Food는 실제 요청/배분량만 줄어든다. 지역 Population 합=전체 Alive=16을 확인한다. 한 번의 식사를 매 프레임 다시 적용하면 안 된다.

## 4. 빠른 기아 사망

| 설정 위치 | 값 |
| --- | --- |
| 각 Region | InitialFoodAmount=0, FoodCapacity=100 |
| 각 Bootstrap | InitialAgentCount=8, InitialEnergyRatio=0.1 |
| Survival | Enabled=true, BaseMetabolism=1, Grace=5초, Damage=10 HP/초, DeadRetention=2초 |
| Feeding | Enabled=true, FirstFeedDelaySeconds=1, IntervalSeconds=2, Amount=1 |
| Migration / Overcrowding | 둘 다 Enabled=false |

기본 MaxEnergy=100, MaxHP=100인 Box 기준 약 10초에 Energy=0, 약 15초부터 HP가 줄고 약 25초에 사망한다. Alive와 Population은 사망 확정 시 감소하며 Box/Dead Entity는 약 2초 뒤 제거된다. 요약 표시는 기본 1초 주기여서 약간 늦게 반영될 수 있다.

Output Log에서 `[Eco Death] Cause=Starvation`, `[Eco Death Cleanup]`을 확인한다. 같은 ID의 Death가 한 번만 기록되어야 한다. `PredationHistory`는 기아 때문에 올라가면 안 된다. 이주만으로 전체 Alive가 감소하면 안 된다.

## 5. 기아 도중 식량 공급과 회복

위 기아 설정으로 새 PIE를 시작하고 죽기 전에 Host/Standalone 콘솔에서 실행한다.

```text
Debug.FoodSupply Forest_A 100
```

예를 들어 12초에 공급하면 다음 적격 식사에서 A의 살아있는 개체만 Energy를 회복하고 기아 시간이 초기화된다. 이미 받은 HP 피해는 회복하지 않는다. B는 그대로 기아 사망한다. 죽은 개체는 음식을 공급해도 부활하지 않는다.

공급은 FoodCapacity까지만 적용되며 `[Eco Food Supply] Requested/Actual`로 실제 공급량을 확인한다. 동일 자원 단계의 순서는 lethal 사망→음식 손실→수동 공급→Spawn/식사다. 정확히 사망 시각에 공급하면 사망을 되돌리지 않는다. 이 명령은 Client에서 거절된다.

## 6. 순수 과밀 분산 재이주

먹이 부족과 기아 영향을 분리해서 과밀 자체를 확인한다.

| 설정 위치 | Forest_A | Forest_B |
| --- | --- | --- |
| Bootstrap InitialAgentCount | 12 | 0 |
| EcologicalComfortPopulation | 4 | 32 |
| SpawnSchedule.RegionPopulationLimit | 64 | 64 |
| Region InitialFoodAmount / FoodCapacity | 500 / 500 | 500 / 500 |
| AdjacentRegionIds | Forest_B | Forest_A |

Project Settings:

- Survival.Enabled=false, Feeding.Enabled=false, Spawn Waves=false, 모든 FoodEvent=false.
- Migration.Enabled=true, DecisionIntervalSeconds=1, Speed=400, ArrivalRadius=30, ArrivalSpread=300.
- Overcrowding.Enabled=true, EnterCrowdingRatio=1.10, ExitCrowdingRatio=0.95, SustainSeconds=3, MinimumResidenceSeconds=10, MaxDeparturesPerRegion=2, MinimumImprovement=0.1.

약 10초 이후 A에서 최대 2마리/판단 주기로 출발한다. 모든 개체가 같은 프레임에 떠나면 안 된다. Outgoing을 빼고 Incoming을 더한 ProjectedPopulation이 다음 후보 선택에 반영되어야 한다. 이상적 두 지역 조건에서 A 예상 인구가 3 정도로 내려가면 압력이 해제되고 나머지는 남는다. 출발량/도착 시각은 geometry와 실제 후보 개선 조건에 따라 확인한다. 세계 Alive는 계속 12다.

B 영역에 들어온 순간과 도착 commit은 다르다. 해당 ID가 TargetPosition 반경 30cm 및 B Bounds 내부에 도달한 뒤에만 A Population−1/B Population+1이다. `Arrived=1 Reason=Overcrowding`과 MigrationIn/OutCount가 대응해야 한다. 도착 직후 재출발하지 않아야 한다.

여러 지역 경쟁 검증에는 C를 추가하고 RequiredRegionCount=3, C Bootstrap/Region/양쪽 인접 관계도 등록한다. A/B가 C를 동시에 선택할 때 예정 Incoming을 고려하는지 확인한다. 목적지 Food를 이동 중 고갈시켜 취소/재선정 시 Incoming이 해제되는지도 확인한다.

## 7. 혼합 폐루프 및 멀티플레이

Survival/Feeding/Overcrowding/Migration을 모두 켜고 정상 식사 설정으로 시작한다. 콘솔에서 다음을 실행한다.

```text
Debug.Starvation Forest_A
eco.M4.Dump details
```

A 고갈→B 이주→B 압력 변화→일부 재이주/섭취 경쟁→Energy 감소→기아 사망→인구·수요 감소를 확인한다. 두 지역 모두 고갈시키면 개선되는 목적지가 없어 대기하고 기아가 진행돼야 한다. 최근 실패 목적지를 즉시 반복 선택하면 안 된다.

Spawn Waves를 다시 켜고 유입 예정 개체와 목적지 웨이브가 겹치도록 설정한다. 관련 인구/예상 인구, 음식 전망과 압력 때문에 추가 Spawn이 제한되어야 한다. 초기 seeding은 정상 웨이브의 압력 억제와 별개이며, 건너뛴 웨이브를 나중에 일괄 보상하지 않는다.

PIE Play Settings에서 Listen Server+Client 1개, 이후 Client 2개로 확인한다. 각 창의 콘솔에서 `eco.M4.Dump details`를 실행하고 World/NetMode를 구분한다. Client는 health/energy/life와 지역 요약을 수신하며 대사·섭취·사망을 계산하지 않는다. 관련 범위 밖으로 이동해 프록시가 제거되어도 서버 Population은 유지되어야 한다. 실행 중 접속/종료, PIE 재시작도 확인한다.

Dead 잔류 2초는 최선 노력 전송이며 사망 연출 ACK가 아니다. 범위 밖 또는 잔류 종료 후 접속한 Client는 Dead 표본을 못 볼 수 있다. 최종 Actor 사망 애니메이션 대신 현재는 선택적 빨간 DEAD debug 라벨과 Box 제거로 관찰한다.

## 8. 진단값의 의미

`eco.M4.Dump details`는 개체 ID/commit Region/Alive/Health/Energy/ZeroSeconds/State/Target/Reason/DeathCause와 Bubble 수를 출력한다. Health/Energy는 서버에서도 비교를 위해 0~1 비율로 표시한다. State=0 Resident, 1 Traveling, 2 WaitingForFood. Reason=0 None, 1 FoodDepletion, 2 Overcrowding, 3 FoodShortage, 4 ReturnHome. DeathCause=0 None, 1 Starvation, 2 ExternalDamage. Client에는 논리 State/Reason/Cause/ZeroSeconds를 복제하지 않으므로 이 필드는 서버에서 확인한다.

지역 요약에는 Resident/Outbound/Incoming/Projected/Comfort/Crowding/FoodSatisfaction/StarvationDeaths/ExternalDeaths와 완료 이주 이력이 있다. dump의 지역 값은 GameState의 마지막 완료 요약이고 개체 값은 현재 Mass snapshot이다. 서로 다른 시간 경계를 같은 순간으로 비교하지 않는다.

보존 기준:

- Region Population 합 = Authority Alive.
- Authority Alive = 성공 Births − 고유 Death commit 수.
- ProjectedPopulation = Population − Outbound + Incoming.
- 이주만으로 전체 Alive 변화 없음, Client relevance로 서버 인구 변화 없음.
- 자원 Before + 실제 Supply − EventLoss − Consumed = After (허용 반올림 오차 내).

`[Eco Conservation]` 또는 `Population stopped`가 발생하면 입력/상태를 기록하고 원인을 수정한 뒤 PIE를 재시작한다. 계속 실행하며 장부를 임의 보정하지 않는다. 낮은 FPS/긴 frame/일시정지/재시작 검증에서는 같은 Epoch/Step의 대사·섭취·Death 중복이 없어야 한다.
