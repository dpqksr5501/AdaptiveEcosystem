# 플레이어 사냥·생태계 구현과 직접 테스트

2026-11-05~06 작업. 사용자 요청에 따라 추가 이주 실행 검증을 중지하고 현재 확인 범위를 정리했다. 작업 기준 `jwj-1024`, 시작 HEAD `92e6df20a7ee10d9299551a60ba32d4ab1e8c4ae`. 커밋·push는 하지 않았다. 기존 사용자 변경과 이번 변경이 함께 있는 작업 폴더다.

## 적용 위치와 구현

별도 맵을 만들지 않고 기존 **`/Game/JWJ/1102_Integration_JWJ`**에 적용했다. 기존 `JWJ_WildlifeTest` 지역에 인접한 `JWJ_HuntingMeadow`와 양방향 지면 이주 경로, 두 지역의 식생/토양 입력을 추가했다. 기존 지역의 초기 개체 설정은 보존했다. destination SpawnGroup 저작값은 사슴 8·늑대 1이지만, 현재 Native 설정의 개체 수 override에 의해 **실제 실행은 각 지역 사슴 12·늑대 4**로 시작했다. 저작값과 실행 개체 수를 혼동하지 않는다. 수원은 임의 생성하지 않았다.

- 서버의 가벼운 Query 캡슐이 완료된 동물 논리 위치를 따라간다. HP와 이동 권위는 기존 Mass/Native에 남는다. 기존 서버용 피격 충돌체가 없어 전용 `AEcoCreatureHitProxy`를 추가했다.
- Proxy는 살아 있는 플레이어 주변 기본 18m에서 준비하고, 이미 활성화된 것은 22m까지 유지한다. 여러 플레이어의 필요 영역을 합치며 최대 256개를 가까운 순서로 사용한다. 시각 Actor가 화면에서 사라지는 것과 독립적이다. 멀어진 Proxy는 ID·충돌을 해제하고 pool로 돌아가며, 논리 개체는 계속 살아간다. Client에는 Proxy를 복제하지 않는다.
- 손/발 Sphere sweep이 실제 접촉한 StableAgentId를 전달한다. 기존 전방 최근접 개체 재탐색을 콤보 피해에 사용하지 않는다. 서버 공격 실행·단계·대상·epoch와 유효 시간을 검증한다. 단계별 피해는 공격 DA를 읽으며 기존 고정 1초 제한을 새 콤보에 적용하지 않는다.
- 기존 생태계 완료 경계에서 피해·지각 가능한 기억·사망·종별 개체 수를 처리한다. 동일 단계/대상 중복을 막고 HP 이하의 실제 피해만 확정한다. 사망 장부가 성공한 뒤 `DeathCommitted`를 통지한다.
- 늑대는 시야/거리/차폐와 기존 행동 상태를 확인하고 기존 Native 이동 경로를 통해 플레이어에게 접근한다. 준비 0.5초, 유효 접촉 시 20 피해, 재공격 대기 1.5초다. 새로운 이동 writer는 없다.
- 플레이어 HP는 GAS Health/MaxHealth이며 기본 100이다. 죽으면 능력·이동을 정리하고 기본 5초 후 새 Pawn으로 부활한다. 이전 Pawn/이전 epoch의 요청은 새 대상을 공격하지 않는다. 화면 우측 위에 HP를 표시한다.
- F 입력과 기존 콤보 Montage를 유지했다. 발차기는 실제 오른발 모션에 맞춰 `foot_r` bone으로 수정했다. 왼손/오른손은 높이가 낮은 늑대에게 빗나갈 수 있으며, 콤보 성공을 명중으로 처리하지 않는다.

현재 레벨은 life·vegetation·herd journeys·player combat ON, waves OFF다. 전역 player combat 기본은 OFF로 두어 다른 레벨에서 자동 활성화하지 않는다. SocialControl=0, 기존 모델·관측 차원·Native 단일 이동/대사·M4 자원 장부를 보존했다. Python은 검증 도구이며 게임 추론에 사용하지 않는다.

## 실제 확인 결과

| 항목 | 확인 결과 | 근거(Saved/PlayerHunting_20261105 아래) |
|---|---|---|
| 직접 UBT Editor Development 빌드 | 성공. 마지막 현재 레벨 audit 허용 변경도 직접 빌드 확인 | Saved/IntegrationBuilds의 최신 Milestone_Final 로그 |
| 전투 집중 자동화 3개 | 성공 2·경고 포함 성공 1·실패 0 | AutomationCombat2/index.json |
| 사슴 사냥 PIE | 실제 입력→접촉→HP 감소→사망 PASS | PIE_Deer.log의 PLAYER_HUNTING_PIE_PASS |
| 늑대 사냥 PIE | 실제 오른발 타격 30+30+30+10=100, 사망 1회 PASS | PIE_Hunting_Wolf.json |
| 플레이어 피해·사망·부활 | 실제 늑대 공격 5회, HP 100→0, 5초 뒤 새 Pawn HP100 PASS | PIE_PlayerHealth.json / .log |
| 장시간 사냥 비교 | 동일 seed=23, 각 1,800 simulation seconds, 각 181회 관측 PASS | Loop_baseline_23.json / Loop_hunt_23.json |
| 자원 보존 | 위 두 실행에서 식생 값과 권위 자원 장부의 잔량·누적 소비·성장·환경 손실 일치(오차 1e-5 이내) | 같은 JSON과 audit_player_hunting_loop.py |

전투 집중 자동화는 Proxy ID/Query/재사용, 플레이어 HP 권위/이전 Avatar 거절, 정확한 대상 큐/동시 치명타/단일 사망을 다룬다. 이후 추가한 AvatarRefresh 회귀 테스트는 컴파일했지만 아직 실행하지 않았다. 전체 자동화는 기존 RefugeVisualComposition에서 누락된 MWLandscapeAutoMaterial Mesh 참조로 중단했다. null 방어는 추가·빌드했으나 전체 suite를 재실행하지 않았으므로 전체 통과를 주장하지 않는다.

30분 비교의 **기존 지역 JWJ_WildlifeTest** 결과:

| 값 | 사냥 없음 | 시작 늑대 4마리 실제 사냥 |
|---|---:|---:|
| 시작 사슴 / 늑대 | 12 / 4 | 12 / 4 |
| 종료 사슴 / 늑대 | 11 / 0 | 52 / 0 |
| 플레이어 사냥 사망 | 0 | 4 |
| 누적 먹이 소비 | 524.955 | 1676.358 |
| 종료 먹이 잔량 | 87.791 | 48.072 |
| 이주 입출 장부 | 0 | 0 |

사냥은 실제 콤보를 실행했고 HP/동물/먹이를 직접 수정하지 않았다. 자동 fixture는 플레이어를 대상 근처로 배치하고 사냥 중 무적을 사용했으며, 사냥 후에는 멀리 이동시켰다. 이 결과는 이 초기 조건에서 포식 압력·생존/조건부 출생·먹이 소비가 달라진 관측이다. 자연 균형 보장이나 모든 seed에 대한 통계 검증은 아니다. 사슴이 많아져도 자원 재생·용량과 출생/생존 조건에 따라 부족 시점은 달라진다.

**아직 확인하지 않은 부분:** 이 실행에서 사냥으로 인한 자연 부족→이주 도착은 발생하지 않았다. 강제 가뭄 실행은 기존 JYU 전용 audit map 제한으로 거절되었고, 현재 맵의 실제 경로 도착을 성공으로 확인하지 않았다. 수동 검증을 위해 같은 비 Shipping audit API에 현재 맵의 Standalone 경로를 허용했으며 자동으로 실행하지 않는다. Dedicated+2 Client 시도는 SteamSockets 접속 실패/시간 초과로 끝나 RPC·HP 복제·late join 최종 통과 결과가 없다. 로컬 재검증 도구에 nosteam과 기존 EcoProtocol=1을 추가했지만 재실행하지 않았다. 최신 저장/재시작 검증도 미실행이다. 물리 F 키 입력·패킷 지연/손실·대규모 부하는 자동 입력 검증과 구분한다.

## 직접 확인 순서

### 1. 사냥과 피해 확정

1. 원래 프로젝트를 열고 `/Game/JWJ/1102_Integration_JWJ`에서 **Play**한다. PIE의 Client 전용 모드보다 우선 Standalone(플레이어 1명)으로 확인한다.
2. 동물 가까이 접근해 **F**를 누른다. 왼손/오른손 회수 중 F를 다시 눌러 오른손→발차기로 연결한다. 계속 누르는 것만으로 다음 단계를 예약하지 않는다.
3. 우측 HP와 동물 상세 패널을 확인한다. 패널은 `eco.Inspector.Visible 1`, 개체 선택은 Tab 또는 가운데 마우스다. 공격 sphere가 필요하면 `/Game/JWJ/Gameplay/DA_EcoUnarmedCombo`의 DrawDebug를 켠다.
4. Output Log에서 `[EcoCombo] Contact`와 `[EcoCombat][Outcome]`을 구분한다. Outcome의 `Applied`, `HP`, `Target`을 보고 실제 피해를 확인한다. `[EcoCombat][DeathCommitted]`가 뜨는지 확인한다. 개체가 멀리 가서 안 보이는 것은 죽음이 아니다.
5. 다른 동물이 옆에 있어도 맞은 ID의 HP만 감소하는지, 한 타격 창에서 같은 개체가 반복 피해를 받지 않는지 확인한다. 낮은 늑대는 손 공격이 빗나갈 수 있으므로 실제 발차기까지 연결한다.

### 2. 플레이어 피격과 부활

1. 새 Play 세션을 시작하고 살아 있는 늑대의 앞쪽 가까이 접근한다. 늑대가 식사/수면 등 다른 상태면 공격이 늦을 수 있다.
2. `[EcoCombat][WolfWindup]` 뒤 `[EcoCombat][PlayerDamage]`와 HP 20 감소를 확인한다. 사거리·방향·차폐가 어긋나면 준비 후에도 피해가 확정되지 않을 수 있다.
3. HP0에서 이동/공격이 멈추고 `[EcoCombat][PlayerDeath]`가 출력되는지, 약 5초 뒤 HP100의 새 캐릭터로 돌아오는지 본다.

### 3. 자연 변화 관찰

새 Play에서 늑대를 죽이지 않은 경우와 기존 지역 늑대를 모두 사냥한 경우를 각각 관찰한다. 사슴 수뿐 아니라 식생 잔량·누적 소비·출생/죽음도 함께 비교한다. 플레이어가 계속 쫓아다니면 접근/소음 압력도 달라지므로 사냥 후에는 충분히 떨어져 관찰한다. 사냥 직후 사슴을 즉시 추가 생성하거나 이주를 강제로 성공시키는 규칙은 없다.

### 4. 먹이 부족과 실제 이주 — 사용자 확인 항목

**Play 메뉴의 Standalone Game(별도 게임 프로세스)** 으로 현재 맵을 실행한다. 아래 가뭄 명령은 정확한 현재 맵 패키지를 허용하므로 UEDPIE 접두사가 붙는 일반 PIE에서는 거절될 수 있다. Client가 아닌 권위 게임 창의 콘솔에서 실행한다.

```text
eco.HerdMigration 1
eco.HerdMigration.Debug 2
eco.HerdMigration.Test.Drought JWJ_WildlifeTest
```

이 명령은 **그 세션에서만** 기존 지역의 먹이를 장부 거래로 제거하고 재생을 정지하는 개발용 fixture다. 자연 사냥의 결과로 해석하지 않는다. 기본 기준은 지역 잔량 비율 25% 미만이 8초 지속되는 것이며 목적지의 먹이·보고 정보·무리·경로 조건도 필요하다. 명령 직후 반드시 모든 사슴이 떠나지는 않는다.

- `[HerdMigration][AuditFoodLoss]`가 출력되어야 가뭄이 실제 적용된 것이다. 거절되면 실행 맵/Standalone/권위를 먼저 확인한다.
- **M**으로 지도 표시를 켜고 **[ / ]**로 계획을 선택한다. Debug 2는 구성원의 실제 목적지도 표시한다.
- `Preparing → Traveling` 등의 계획과 실제 사슴 이동을 함께 본다. 목적지는 기존 지역에서 동쪽(+X 약 15,000cm)의 `JWJ_HuntingMeadow`다.
- 목적지 도착 후 실제 개체 RegionId가 바뀌고, 출발 지역 MigrationOut·도착 지역 MigrationIn 및 종별 Population이 함께 갱신되어야 완료다. 이동 화살표나 계획 생성만으로 완료로 판단하지 않는다.
- `Blocked`는 진행 부족 진단이다. 지형 충돌이 원인이라고 단정하지 말고 실제 경로/위치와 로그를 함께 확인한다. Client에는 권위 이주 디버그 지도가 나오지 않으므로 서버/Standalone에서 본다.
- 종료 후 새 Play로 돌아가면 가뭄에 의한 먹이 제거는 맵 에셋에 저장되지 않는다. 콘솔로 바꾼 표시/옵션을 확실히 초기화하려면 에디터/Standalone을 재시작한다.

## 재현 도구와 코드 위치

프로젝트/에디터/빌드가 실행 중이지 않은 별도 환경에서 저장소 루트 PowerShell로 실행한다. 각 도구는 기존 프로세스를 중단하지 않고 사용 중이면 거절한다.

```powershell
& ./AdaptiveEcosystem/Tools/Editor/run_player_hunting_check.ps1 -Check wolf
& ./AdaptiveEcosystem/Tools/Editor/run_player_hunting_check.ps1 -Check deer
& ./AdaptiveEcosystem/Tools/Editor/run_player_hunting_check.ps1 -Check health
```

`-Check baseline/hunt -SimulationSeconds 1800`은 비교 재현용이다. `drought/save/load/automation`과 `run_player_hunting_network.ps1`도 준비되어 있지만 위 미확인 범위에 해당하므로 실행 성공을 전제하지 않는다. fixture는 플레이어 위치/입력 등을 제어한다. 수동 플레이 체감과 구분한다. 결과·로그는 `Saved/PlayerHunting_20261105`에 있으며 Git 추적 대상이 아니다.

- [Proxy](../../Source/AdaptiveEcosystem/Creature/Player/EcoCreatureHitProxy.cpp), [전투 큐/늑대 공격](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureCombat.cpp), [사망 장부 경계](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp)
- [Sphere sweep](../../Source/AdaptiveEcosystem/Player/EcoMeleeHitComponent.cpp), [플레이어 HP/부활](../../Source/AdaptiveEcosystem/Player/EcoPlayerState.cpp), [GAS Attribute](../../Source/AdaptiveEcosystem/Player/EcoHealthAttributeSet.cpp)
- [기존 무리 이주](../../Source/AdaptiveEcosystem/Mass/EcoHerdMigration.cpp), [현재 맵 저작 도구](../../Tools/Editor/setup_player_hunting_ecosystem.py), [기존 계획](PLAYER_HUNTING_ECOSYSTEM_LOOP_PLAN_20261105.md)
