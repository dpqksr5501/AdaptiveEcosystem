# 두 대륙·다지역·다역할 생태계 검토 및 구현 계획

기준일: 2026-10-08. 현재 로컬 작업 트리의 C++ 소스와 문서를 기준으로 검토했다. 미커밋 구현도 현재 상태에 포함했다. Blueprint/레벨 내부 연결과 실제 PIE 동작은 이번 검토에서 확인하지 않았다. 이 문서는 구현 제안이며, 제안한 신규 형식과 기능은 아직 구현되지 않았다.

## 1. 사용자 목표와 판단

후속 요구인 실제 식물 접근 소비, 육식 포식, 종별 Blueprint 표현은 [먹이사슬 및 BP Representation 구현 계획](FOOD_CHAIN_AND_BP_REPRESENTATION_PLAN.md)에 구체화했다. 실제 게임 섭식은 지역 주기 배분을 근접 자원 소비로 전환하고, 첫 시연부터 식물·동물 BP를 함께 사용한다.

사용자가 확인한 목표는 **같은 게임 안의 두 대륙·대형 공간**이다. 하나의 권위 Unreal `UWorld`에 두 대륙을 두고, 각 대륙의 여러 지역에 Bootstrap을 배치한다. 같은 지역의 다른 역할군과 인접 지역의 개체들이 감지·경쟁·포식·회피·이주하고, 그 결과가 지역 자원과 개체군을 바꿔야 한다.

현재의 Server 권위, 지역 자원 관리, StableAgentId, Mass 생명주기와 이주 구조는 적절한 기반이다. 그러나 **지역별 단일 종 Box 실행 경로와 PPO/Social 실험 경로가 아직 통합되지 않았으므로 최종 목표가 구현된 상태는 아니다.** 맵을 두 대륙으로 늘리거나 Bootstrap만 추가하는 것으로 이 공백이 해소되지 않는다.

대륙은 Unreal World와 구분하여 `ContinentId`로 명명한다. 동일한 WorldSubsystem과 Mass EntityManager가 두 대륙을 관리하고, 생태 상태는 지역별로 보유한다. 각 대륙에 같은 이름의 지역을 두더라도 `RegionId`는 해당 UWorld 전체에서 고유해야 한다. 예: `ContinentA.Forest01`, `ContinentB.Forest01`.

## 2. 코드에서 확인한 현재 상태

아래 소스 경로는 `Source/AdaptiveEcosystem/` 기준이다.

| 항목 | 확인한 구현 | 목표에 대한 판단 |
|---|---|---|
| 지역–Bootstrap 연결 | `Mass/EcoMassLifecycleSubsystem.cpp:121–134`에서 RegionId별 Bootstrap 하나를 강제하고 모든 지역의 Bootstrap을 요구 | 지역별 작성 단위로 유지 가능 |
| Bootstrap의 개체 구성 | `Mass/EcoMassNetworkBootstrap.h`에 단일 EntityConfig와 SpeciesId | 지역 내 다종·다역할 구성으로 확장 필요 |
| 권위 | Lifecycle/Ecology Subsystem은 Server/Standalone 게임 월드에만 생성 | 유지 |
| 자원·생존 | 지역별 Food, 공정 식사 배분, Energy 회복, 대사·기아 사망과 집계 경로 존재 | 역할에 따른 식성·소비·회복 규칙 필요 |
| 지역 이주 | `Mass/EcoMassMigration.cpp`가 AdjacentIndices 후보를 평가하고 도착 때 Region을 변경. 기존 ID 유지 | 적절하나 현재 식량 평가를 모든 역할에 적용하는 문제를 확장 시 해결해야 함 |
| PPO 템플릿 통합 | `Mass/EcoMassNetworkBootstrap.cpp:143–149`가 Herbivore/Custom/Spring 이동 등 혼합을 거부 | 의도된 이동 충돌 방지. 검사만 제거해서는 안 됨 |
| 이웃 검색 | `AI/Policy/EcoNeighborhoodSubsystem.h`의 Entry는 위치·방향·포식자 여부 등을 보유. 지역·종·대륙 정보 없음 | 물리적 근접 검색은 있지만 관계 필터와 공간 범위 계약이 없음 |
| 동족 집계 | `AI/Policy/EcoBehaviorProcessors.cpp:215–222`는 포식자가 아닌 근처 개체를 동족으로 집계 | 다종 초식 개체를 넣으면 Conspecific 의미가 깨짐 |
| 관측 Provider | `AI/Policy/EcoWorldProviders.cpp:136–149`에서 Food/Cover에 Dummy를 기본 연결. 소스 검색상 실제 Provider 교체 호출은 확인되지 않음 | 실제 Ecology·Shelter snapshot 연결 필요 |
| 피식 결과 | 행동 Processor는 HP=0과 위치 격자 EMA에 기록. Ecology에도 별도 RegionId 기반 PredationHistory가 있음 | 권위 사건을 하나로 확정하고 정책이 읽는 기록을 통일해야 함 |
| 피식 EMA 분모 | 개체마다 ReportPopulation(..., 1), 수신은 max(Population, Count) | 현재 호출에서 분모가 1에 머물 수 있음. 통합 전에 수정 또는 기존 격자 EMA 경로 제거 필요 |
| Social | 무리 가입·알람·보정 행동·은신처 목적지/예약 구현 존재 | Steering이 Raw Action을 읽으므로 보정 행동과 목적지의 실제 이동 연결 필요 |
| 역할 표현 | 행동에는 Herbivore/Predator Tag가 있고 Social 무리는 SpeciesRuntimeIndex 사용 | 범용 역할군 계약은 없음. Species와 Role을 분리할 필요 |
| 네트워크 | Server Entity와 Client 프록시, 지역 요약, 연결별 복제 간격 기반 존재 | 역할 표시·대륙별 요약·클라이언트 템플릿 등록 확장 및 PIE 검증 필요 |
| 스트리밍 | `Mass/EcoMassLifecycleSubsystem.cpp:337`는 필수 Bootstrap이 unload되면 실패. World 공간 snapshot도 Region Actor가 필요 | 대형 맵 스트리밍 전에 작성 Actor와 논리 상태의 수명을 분리해야 함 |

`Variant_Combat/AI/CombatEnemySpawner.cpp:52–69`의 기존 EnemySpawner는 타이머로 CombatEnemy Actor를 생성한다. 검토한 C++ 경로에는 Region/Bootstrap/Mass 개체와의 연결이 없다. 사용자가 EnemySpawn을 Mass 생성 기능의 의미로 사용했다면 Bootstrap이 그 역할을 한다. `BP_CombatEnemySpawner`를 의미했다면 Blueprint 내부 연결은 에디터에서 추가 확인해야 한다.

과거 문서의 검증 기록은 이번 실행 결과가 아니다. M3 문서에는 A→B 이주 로그 기록이 있지만 여러 네트워크 시나리오는 미실행이며, M4 검증 기록도 빌드 성공과 미실행 PIE를 구분한다.

## 3. 권장 목표 구조

```text
권위 UWorld 1개 / 공통 WorldClock / 공통 Mass EntityManager
├─ 대륙 A
│  ├─ A.Forest01 ── 지역 Bootstrap ── 여러 SpawnGroup
│  │                                  ├─ 초식 종·역할
│  │                                  └─ 포식 종·역할
│  └─ A.Grassland01 ── 지역 Bootstrap ── 여러 SpawnGroup
└─ 대륙 B
   ├─ B.Forest01 ── 지역 Bootstrap ── 여러 SpawnGroup
   └─ B.Grassland01 ── 지역 Bootstrap ── 여러 SpawnGroup

World: 대륙·지역의 위치/경계·환경·연결 그래프
Ecology: 지역 Food·피식 기록·Mass에서 산출한 개체군 집계
Mass: 개체별 식성·생존·관측·정책·사회행동·이동·상호작용
Network/Representation: 읽기 전용 결과 전달·표현
```

**Region 1 : Bootstrap 1 : SpawnGroup N : Entity N**을 권장한다. Bootstrap은 지역의 초기 구성과 생성 요청 실행을 맡는다. 생성된 개체의 이후 판단·생존·이주는 Mass가 담당하며, 생성 Bootstrap이 현재 지역이나 소유권을 결정하지 않는다. A 지역에서 생성된 개체가 B로 이동해도 StableAgentId를 유지한다.

Bootstrap끼리 직접 다른 Bootstrap의 개체를 조작하거나 지역마다 별도 Mass 시뮬레이터를 만들지 않는다. 공통 공간 검색과 지역 그래프를 통해 개체가 만난다.

## 4. 데이터와 책임 변경

### 4.1 대륙·지역

- 지역 작성 데이터에 `ContinentId`와 런타임 대륙 인덱스를 매핑한다. RegionId는 UWorld 전체에서 고유하게 유지해 기존 FName 키를 재사용한다.
- 대륙은 지역 목록·경계·환경 기본값을 제공한다. Food나 개체 HP를 소유하지 않는다.
- 개체의 현재 대륙은 현재 지역에서 파생한다. 이웃 검색 snapshot에 compact index를 넣을 수 있지만 별도 mutable 대륙 상태를 병렬 권위로 두지 않는다.
- 기존 AdjacentRegionIds는 호환 입력으로 유지하고, 필요 시 연결 edge에 `bAllowPerception`, `bAllowMigration`, 통과 위치/폭/이동 비용을 추가한다.
- 기본 인접은 양방향 검증. 일방통행은 별도 명시 입력으로만 허용한다. 잘못된 ID, 자기 연결, 중복 ID, 겹친 경계의 우선순위, 통과 불가능한 연결을 시작 전에 검증한다.
- 두 대륙은 기본적으로 독립 연결 그래프다. 대륙 간 이동이 필요해지면 명시적 통로 edge와 통과 규칙을 추가한다.

### 4.2 지역별 복수 SpawnGroup

제안하는 `FEcoSpawnGroupDefinition`에는 `SpawnGroupId`, SpeciesId, 역할 설정 또는 역할을 가진 EntityConfig, InitialCount, 생성 위치/간격, SpawnSchedule, 초기 Energy 설정을 둔다. 하나의 종 안에 여러 역할이 있어도 표현 가능해야 하므로 SpeciesId를 역할 식별자로 사용하지 않는다. 명시 RoleId와 템플릿 역할 설정을 동시에 둔다면 시작 시 일치를 검증한다.

- 기존 단일 설정을 그룹 하나로 변환해 기존 Bootstrap Blueprint/레벨을 보존한다.
- 스케줄 키, cursor, 최초 생성 receipt, 요청 라우팅을 `(RegionId, SpawnGroupId)`로 변경한다. FEcoSpawnRequest에도 그룹 식별자를 추가한다. Bootstrap 배열만 추가하고 Ecology의 RegionId 단독 키를 남겨두면 두 번째 그룹이 정상적으로 생성되지 않는다.
- 지역 Food와 지역 상태는 그룹 수와 관계없이 한 번만 등록한다.
- 지역 공통 생성 상한과 EcologicalComfortPopulation은 지역 설정으로 옮기고, 그룹별 상한과 구분한다. 월드 상한·지역 상한·그룹 상한을 모든 pending 예약까지 포함하여 검사한다.
- 기존 RegionPopulationLimit는 생성 제한이며 이주 도착을 막는 벽이 아니다. 이주 시에는 soft comfort와 유입 예측으로 압력을 조정한다.
- 초기 검증 완료 뒤에만 상태 등록과 생성을 commit하고 중복 요청을 차단한다. 생성 순서와 상한 경쟁은 고정된 Region/Group 순서로 결정한다.
- 클라이언트에는 각 그룹의 모든 EntityConfig를 사전 등록해야 한다. 클라이언트 Bootstrap은 권위 개체를 생성하지 않는다.

### 4.3 종과 역할

SpeciesId는 생물 종, RoleId는 행동 책임이다. 초기 예시는 초식/포식이며, 향후 같은 종의 정찰/방어 등도 이 구분을 사용할 수 있다. 변하지 않는 역할 설정은 Trait/Shared 설정으로, 변경 가능한 개체 역할 상태는 Entity Fragment로 둔다.

첫 단계의 관계표는 다음 정도로 제한한다.

| 관계 | 초기 규칙 |
|---|---|
| 같은 종의 초식 개체 | 동족 수·무리 중심·분리·알람 |
| 다른 종의 초식 개체 | 먹이 경쟁·충돌 분리. 동족 수에는 미포함 |
| 포식자 → 먹이 관계에 등록된 초식 개체 | 감지·추격·포획·섭취/쿨다운 |
| 초식 개체 → 위협 관계의 포식자 | 위험 관측·도주·은신 |

포식자까지 식생 Food를 같은 양으로 소비하거나, 식생이 고갈되었다는 이유만으로 같은 이주 점수를 주지 않는다. 식성별 먹이 공급, 대사, 목표 지역 평가를 분리한다. 지역 총 Population은 역할별·종별 집계를 합산한 값으로 유지하고 모두 Mass snapshot에서 산출한다.

## 5. 인접 지역 상호작용과 이동

세 종류를 구분한다.

1. **개체 감지/상호작용:** 실제 거리·시야·차폐·관계표 조건을 만족하는 같은 지역 또는 허용된 인접 지역 개체를 조회한다. 인접 지역 전체의 개체가 자동으로 서로 보이는 것은 아니다.
2. **지역 이주:** 그래프의 허용 edge를 따라 이동 의도를 선택하고 실제 도착 시 Region membership을 확정한다. 기존 StableAgentId 보존 경로를 확장한다.
3. **지역의 간접 영향:** 이주로 증가한 유입 Population/수요, 피식 사건과 자원 변화가 다음 관측에 반영된다. 위험의 이웃 지역 전파는 별도 규칙이며 기본적으로 자동 복사하지 않는다.

FEcoNeighborEntry에 StableAgentId, RegionRuntimeIndex, SpeciesRuntimeIndex, 역할 정보, 필요한 대륙 인덱스와 생존 snapshot을 추가한다. Gather/Perception/Policy/Predation/Steering은 Authority+Alive를 요구하고 ClientProxy를 제외한다. 자기 제외는 거리 0이 아니라 ID/Entity 비교로 하여 같은 위치의 다른 개체를 누락하지 않는다.

현재 검색은 XY 거리 기반이다. 다층 지형에서 위아래 개체가 상호작용하는 문제를 막으려면 높이/연결/차폐 조건도 적용한다. 우선 현재 균일 격자를 재사용하고 실제 성능 수치에 따라 대륙별 bucket 등으로 확장한다.

경계는 membership과 물리 위치를 구분해야 한다. 현재 membership은 이주 도착 시 변경된다. 이동 중 개체의 피식 위치는 snapshot으로 해석한 실제 사건 지역에 귀속하고, Population은 확정 membership으로 집계한다. Region 밖 통로의 사건 귀속은 edge/source 등 명시 규칙으로 정한다. 임의 최근접 Region으로 처리하지 않는다. 겹친 경계나 경계 왕복에는 결정론적 우선순위·히스테리시스를 적용한다.

자유 이동/추격으로 지역 경계를 넘는 개체도 membership 확정 규칙을 거쳐야 한다. 장거리 이주가 아니라는 이유로 지역 상태가 영원히 출생지에 남아서는 안 된다.

## 6. 생태계 폐루프와 단일 이동 경로

```text
지역 환경·Food·최근 피식 + 개체 Energy + 실제 이웃
→ 7개 관측
→ 공유 정책의 개체별 Raw Action
→ Social 보정·목적지·역할별 의도
→ 이동 의도 조정
→ 단일 위치 적분
→ 실제 섭식/포획/사망/도착 결과 버퍼
→ GameThread 권위 commit
→ 지역 자원·Population·PredationHistory
→ 다음 관측
```

현재 M3는 Migration Steering→엔진 Movement, PPO 실험은 자체 Steering 위치 적분이다. 통합 시 어느 쪽이 Transform을 쓰는지 하나로 확정해야 한다. 권장은 기존 Python 조향 수식이 만드는 최종 속도를 공통 이동 의도로 전달하고, 검증한 한 적분기가 위치를 한 번 갱신하는 구성이다. 엔진 이동을 쓰더라도 기존 일정 속력 계약과 궤적 파리티를 확인한다. 가감속 설정으로 수치가 바뀌는 것을 묵인하지 않는다.

- Resident 상태가 일반 행동을 수행할 수 있어야 한다. 현 Migration Steering처럼 비이주 개체의 DesiredVelocity를 매번 0으로 쓰는 동작을 공통 경로에서 제거/격리한다.
- 사망 정지, 이동 제약, 긴급 회피, 장거리 목적지, 역할 행동의 충돌을 하나의 의도 조정 단계에서 해결한다. 우선순위와 재계획은 명시적으로 검증한다.
- Raw Action은 보존하고 Social의 ModulatedAction과 은신처 TargetPosition을 실제 조향에 소비한다. 사망·이주·예약 취소 시 슬롯을 해제한다.
- Dummy Food/Cover 대신 Ecology와 Shelter의 읽기 snapshot을 사용한다. 지역 Food 비율은 초기 연결 확인에는 쓸 수 있으나 공간 먹이 밀도·gradient와 동일하지 않으므로 최종 정책 파리티로 간주하지 않는다. 공간 먹이 패치를 추가해도 별도 권위 자원 장부를 만들지 않는다.
- 포획은 피해자/가해자 ID, 사건 시각·위치·지역, 원인 등을 가진 값 요청으로 버퍼링한다. commit에서 사망을 한 번만 확정하고 Alive 제거·이동 정지·예약 해제·집계·위험 기록·포식자 보상을 함께 반영한다.
- 현재 죽음 원인은 None/Starvation/ExternalDamage이다. Predation과 PlayerHunt를 구분해 기아나 일반 외부 피해를 피식으로 기록하지 않는다. 같은 피해자에 대한 중복 포획은 Step/사건 receipt로 차단한다.
- RegionId 기반 Ecology PredationHistory를 권위로 사용한다. 세부 위치별 위험이 필요하면 이 사건에서 파생되는 읽기 캐시로 제공한다. EMA 계산을 기존 계약에 맞추고 분모·시간·감쇠를 Python/C++에서 정합시킨다.
- 테스트 Actor의 즉시 RespawnCaught는 정식 생태계에서 사용하지 않는다. 신규 생성은 스폰 규칙을 통하며 번식과 스폰 웨이브는 구분한다.

새 역할을 넣기 위해 V1 관측 7개에 RoleId나 대륙 정보를 몰래 추가하지 않는다. 현재 초식 정책은 공유 가중치 7→64→64→4를 유지하고 개체별 출력만 Fragment에 저장한다. 초기 포식자의 추격은 역할 규칙으로 구현한다. 초식 정책의 forage/cohesion/flee/cover를 그대로 포식 학습 정책이라고 간주하지 않는다. 역할별 학습 정책이 필요해지면 현재 공유 모델 원칙과의 변경 범위, 별도 계약 버전·데이터·재학습 계획부터 합의한다.

## 7. 권장 구현 순서와 완료 조건

| 단계 | 작업 | 완료 조건 |
|---|---|---|
| 0. 기존 기준선 | 현재 Box M3의 소비·Energy·사망·이주와 M4 네트워크 기록을 재검증. 변경 전 계약·미커밋 작업 보존 | 기존 ID·Food·Population 불변식과 Host/Client 결과 확보 |
| 1. 한 지역 복수 그룹 | Bootstrap SpawnGroups, 그룹별 스케줄/receipt/요청, 지역 단일 등록, 역할·식성·집계 도입 | 한 지역에서 여러 그룹 생성. 상한·예약·자원 중복 없음. 기존 단일 설정 호환 |
| 2. 단일 행동·이동 경로 | Authority/Alive 조건, Provider, Social 목적지, 역할 추격, 공통 의도/위치 적분 연결 | 같은 지역에서 추격/회피/섭식 가능. 비이주 개체도 이동. 위치 이중 갱신 없음 |
| 3. 상호작용 commit | 포획·사망·포식 보상·PredationHistory와 정식 Lifecycle 연결 | 피해자 한 번 사망, 개체군 감소, 위험 관측 변화, 죽은 개체 행동 중지 |
| 4. 한 대륙 두 지역 | 관계별 이웃 검색, 경계 감지·통로 이동·membership, 식성별 이주 점수 | 경계 너머 감지와 실제 이주를 각각 확인. 같은 ID, 목적지 소비/집계 일치 |
| 5. 두 대륙 각 두 지역 | ContinentId, 고유 RegionId, 연결 검증, 대륙별 환경/요약 | A의 사건이 규칙 없이 B에 반영되지 않음. 두 대륙은 같은 clock/ID 발급 체계를 공유 |
| 6. PPO 평가 | Utility로 검증한 폐루프에 공유 PPO 적용. 관측/행동/조향 Golden Vector, 다지역 시나리오 평가 | 단순 추론 일치뿐 아니라 행동 결과→자원/위험→다음 관측 연결 확인 |
| 7. 대형 맵 운용 | 작성 Actor와 지속 논리 데이터 수명 분리, 서버 시뮬레이션 유지, 클라이언트 관심 범위/템플릿/표현 관리 | 카메라 이동·unload/reload·Late Join에서 중복 생성/ID 손실/논리 중단 없음 |

첫 기능 검증은 한 지역 또는 한 대륙의 두 지역에서 수행하되, 최종 인수 시나리오는 **두 대륙 × 두 지역 × 초식/포식 역할**이다. 모든 지역을 서버에 상시 로드한 작은 레벨에서 먼저 검증한다. 서버에도 스트리밍을 적용하기 전에는 단계 7의 지속 descriptor와 논리 수명 계약을 완료해야 한다.

단계 5의 정식 대륙 설정보다 앞서 단계 1의 RegionId를 대륙 이름으로 구분해 둔다. 대륙별 시계나 개체별 정책 모델을 새로 만드는 일은 이 범위에 필요하지 않다.

각 C++ 변경 뒤 UE 5.8 `AdaptiveEcosystemEditor Win64 Development` UBT 빌드를 수행한다. 단계별 변경은 기존 Box 기준선과 호환성을 유지하는 작은 단위로 검증한다.

## 8. 최소 인수 시나리오

초기 64개체 예시: 두 대륙의 네 지역에 각각 초식 12 + 포식 4. 수치는 행동 확인용이며 생태 균형의 권장값이나 성능 근거가 아니다. 모든 지역의 서버 논리를 활성화한다.

1. 같은 지역에서 포식자가 사냥하고 초식 개체가 도주/은신한다. 동종 수에는 다른 초식 종이 섞이지 않는다.
2. 경계 양쪽 개체는 허용 반경·시야·차폐 조건일 때만 서로 감지한다. 멀리 떨어진 인접 지역 개체와 비인접/다른 대륙 개체는 제외한다.
3. A 지역 Food 감소가 실제 소비량/에너지에 반영되고 이주 압력을 만든다. 포식자의 먹이 평가는 식생 고갈과 구분한다.
4. 이주/추격으로 이웃 지역에 들어가도 ID가 유지되고 membership·예약·자원 귀속이 일치한다.
5. 한 피해자를 여러 포식자가 동시에 선택해도 사망·위험 기록·보상은 한 번만 적용된다. 기아는 피식 위험을 올리지 않는다.
6. 대륙 A의 위기에서 대륙 B의 Food/위험/개체군은 관련 규칙이나 이동 없이 바뀌지 않는다. 공통 월드 상한의 경쟁은 명시된 규칙을 따른다.
7. 전체 Alive = 최초 생성 + 실제 후속 생성 − 확정 사망. 지역 Population 합 = 전체 Alive. 이주만으로 합계는 변하지 않는다. Incoming은 전망치이며 실제 Population에 중복 합산하지 않는다.
8. 자원은 Before + Supply − Loss − Granted 범위 내에서 보존되고 Food가 음수/용량 초과가 되지 않는다.
9. 30/60 FPS와 긴 프레임에서 사망/소비/이주 commit이 중복되지 않는다. 정책 주기는 확정 논리 시간으로 검증한다.
10. Host+두 Client와 Late Join에서 사망·지역·역할 표현·요약이 일치한다. Client 관심 범위 밖 개체도 서버 생태계에서 계속 존재한다.
11. 스트리밍 단계에서 생성 Actor 또는 표현이 unload되어도 논리 개체를 재생성하지 않고 template 등록/프록시 복원이 정상 동작한다.

## 9. 기존 계획과의 연결

- [프로젝트 Architecture](PPO_MASS_ECOSYSTEM_ARCHITECTURE.md)의 World/Ecology/Mass/Representation 소유권과 [Active Runtime 경계](ACTIVE_RUNTIME_BOUNDARIES.md)를 유지한다.
- [M3 과밀·생존 계획](../Roadmap/M3/OVERCROWDING_STARVATION_IMPLEMENTATION_PLAN.md)의 장부·생존·이주 불변식을 다역할로 확장한다.
- [M4 계획](../Roadmap/M4/M4_IMPLEMENTATION_PLAN.md)의 Client별 표현·복제와 플레이어 사건 경로를 사용한다. 클라이언트 프록시 수는 서버 Population과 비교하지 않는다.
- [협업 통합 계획](COLLABORATOR_ECOSYSTEM_INTEGRATION_PLAN.md)의 Provider/Social/Lifecycle 연결을 현재 소스 기준으로 구체화한다. 과거의 구현 상태나 빌드 기록을 최신 완료 상태로 대체하지 않는다.
- [Policy V1](../RL_Policy/POLICY_CONTRACT_V1.md)과 생성된 학습 수치의 차이를 먼저 정리한다. 생성 헤더를 임의 수정하지 않고 Export와 Golden Vector로 검증한다.

이 계획의 첫 구현 단위는 **단일 Region Bootstrap의 다중 SpawnGroup 계약과 Ecology 생성 요청 체계 확장**이다. 이후 단일 이동과 권위 상호작용을 연결해야 두 대륙 확장이 기능 확장으로 의미를 갖는다.

## 10. 이번 검토의 검증 범위

- C++/설정/기존 문서 검토 및 신규 계획 문서 작성. 기존 소스·설정·에셋은 편집하지 않았다.
- UE 5.8 `AdaptiveEcosystemEditor Win64 Development` UBT 실행 성공. `Target is up to date`, 0 actions이므로 이번 실행은 기존 빌드 상태 확인이며 신규 C++ 변경의 재컴파일 검증은 아니다.
- 기존 StructUtils 플러그인 deprecation 경고가 출력되었다.
- PIE, Blueprint 내부 연결, 레벨 배치, 네트워크 런타임 및 성능 측정은 이번 검토에서 실행하지 않았다. 단계별 기대 결과를 검증 완료로 간주하지 않는다.
