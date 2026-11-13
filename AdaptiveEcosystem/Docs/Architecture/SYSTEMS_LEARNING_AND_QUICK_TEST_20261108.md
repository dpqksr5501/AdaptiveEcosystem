# 현재 시스템·학습 자료·간단 테스트 안내 — 2026-11-08

## 1. 확인 기준

- 실제 checkout: `jwj-1024`, HEAD `395992ab2e7af58e8eef58a228d7e5d3bc841c5b`.
- 엔진: 프로젝트의 `EngineAssociation`은 **UE 5.8**. 최근 실행 기록은 UE 5.8.3이다.
- 범위: 이 checkout의 Source, 설정, 개발 기록, 로컬 검증 manifest. 다른 브랜치나 원격 main이 같은 상태라는 의미는 아니다.
- 11-06까지 커밋된 기능과 그 위의 **미커밋 공간 탐색·식생·공유 패치 S1·1102 맵 변경**을 함께 확인했다. 새 clone에서 HEAD만 checkout하면 오늘의 변경까지 재현되지 않는다.
- 이 문서는 조사·사용 안내다. 작성 중 새 UBT/PIE/자동화/네트워크 시험은 실행하지 않았다. 아래 결과는 날짜와 조건이 있는 기존 기록이다.

먼저 [공통 맥락](../PROJECT_CONTEXT.md), [최신 진행 기록](../../../PROGRESS.md)을 읽는다. 옛 상태표의 시각 셀 256개 제한, 풀 1% 이하 숨김 등의 설명은 오늘 변경 전 이력이다. 현재 풀은 전체 셀 변경분과 양의 미세 잔량 표현을 다룬다.

## 2. 지금 구현된 시스템

| 시스템 | 현재 동작 | 기술과 확인 위치 |
|---|---|---|
| Mass 논리 개체·생태 장부 | StableAgentId/지역/종으로 개체를 관리하고 자원·개체군·사망·포식·이주 결과를 권위 경계에서 확정 | Fragment/Processor, `Core/`, `Mass/`, `Ecology/`. [실행 순서](../Mass/MASS_PROCESSOR_ORDER.md) |
| PPO 정책과 Native 실행 | 개체별 관측으로 정책을 추론하고 실제 이동·섭식·대사·포획은 선택한 실행 경로 하나가 처리 | [V1 7관측/4출력](../RL_Policy/POLICY_CONTRACT_V1.md), [v3 18관측/5행동](../RL_Policy/POLICY_CONTRACT_V3.md). 런타임 Python 추론 없음. 현재 늑대의 Native FSM을 PPO 학습 완료로 읽지 않는다 |
| 시각·청각·위험 반응 | 거리/시야/차폐·발소리·날씨/어둠 등의 기존 규칙을 사용해 감지·도주·추적 | `AI/Policy/EcoObservationV3.h`, `EcoThreatModel.h`, `EcoWorldV3.h`. 정책 request와 세계 flight override, 실제 executed 행동을 구분 |
| Social·무리·은신처 | Persistent Herd, 경보 감쇠/전파, 은신처 슬롯 예약·이동/점유·실패 정리. v3 인계 훅 존재 | [v3 Social 인계](../조연우/JYU_V3_SOCIAL_HANDOFF.md). **SocialControl 기본 0**이므로 경보 처리와 Native 행동 개입은 구분 |
| 보호 은신처 | 실제 refuge 생명주기와 지면 슬롯, 안전 규칙에 따른 포획/접근 제약 | [은신처 기록](../조연우/JYU_REFUGE_SAFETY_20261016.md). 현재 통합 ShelterSafe 안전과 ProtectedRefuges 생명주기를 구분하며 보호 규칙을 중첩하지 않음 |
| 사슴 무리 이주 | 부족 지속→목적지 평가→공동 계획→기존 Travel/Native 이동→실제 지역 인계·인구 receipt | [이주·신호 계약](../조연우/HERD_MIGRATION_AND_SIGNAL_CONTRACT.md), `Mass/EcoHerdMigration.cpp`. opt-in이며 맵/경로별 도착 검증 범위가 다름 |
| 토양·수원·식생 폐루프 | 기후·지면·수원→수분/식물 내성→성장·환경 손실→FoodGrid→섭식→자원 장부 | [life 실행 계약](ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md), `AI/Policy/EcoVegetationV3.h`, `World/EcoVegetationField.*`. 장식 비/물/foliage가 자동으로 생태 입력이 되는 구조는 아님 |
| 경험·흔적·협동 사냥·사체 | 개인의 사람 접촉 기억, 제한된 흔적 조사, 사냥 역할/lease, 단일 포획·참여자 영양 배분·사체 접촉 섭취 | [구현 상태표 C/D](ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md), `Creature/Runtime/`. 서버 정답과 개체가 지각한 증거를 구분 |
| 출생·유전·성장·체형 | 부모/성숙/영양/자리/인구 조건에 따른 출생, 안정 seed의 개체 다양성, 성장과 uniform scale·속력/비용 반영 | [life 실행 계약](ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md). 자연 출생·초기 생성·운영 복구를 구분. 새 리그/Morph·임의 종 backend·온라인 진화 학습 전체 완료는 아님 |
| 서버 시계·공통 게임 기반 | 공통 GameMode/PlayerState/입력 기반, 서버 낮밤 시계와 GameState 수신 경로 | `World/EcoWorldClockSubsystem.*`, `Network/EcoGameStateClock.cpp`, `AdaptiveEcosystemGameMode.*`. 모든 맵의 Sky/날씨 BP가 자동 연결됐다는 뜻은 아님 |
| 플레이어 사냥·전투 | GAS 콤보, 손/발 sweep, 서버 피격 proxy, 총기 장착/조준/trace 사격, 실제 대상 검증, 늑대의 플레이어 공격·HP/사망/부활 | [사냥 테스트](PLAYER_HUNTING_IMPLEMENTATION_AND_TEST_20261106.md), `Player/`. F 콤보, 우클릭 조준·좌클릭 사격. 현재 총기는 placeholder 외형 사용 |
| 복제·체력 바·표현 풀링 | Mass Bubble 수신 상태로 Actor/애니메이션/크기/체력 % 표시, 거리 밖 숨김과 재바인딩 | [체력 바](../Player/CREATURE_HEALTH_BARS_20261106.md), [표시 거리](../Network/CLIENT_VISUAL_DISTANCE_20261106.md). Client 표시 거리 기본 1000cm. 보이지 않는 개체도 서버에서는 진행 |
| 저장·운영 복구 | grid/수분/RNG/시계·개체/부모/경험·무리/이주·장부를 checkpoint로 저장·재결합. 빈 종의 명시적 운영 공급 | [저장 계약](ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md). 동일 runtime image hash·맵·모델 등 검사. S1 패치 ON 저장/복원은 현재 명시 거절 |
| 지도·Inspector·환경 진단 | 권위 지도에 지역 Food/Population, 사슴/늑대/플레이어와 이주 진행 표시. Inspector와 식생 패널/JSON | [지도 UI](../Player/JWJ_MAP_UI_UPDATE_20261106.md), [풀 테스트](FOOD_GRASS_TEST_GUIDE_20261108.md). 권위 지도는 Client 전용 창에 표시하지 않음 |
| 공간 탐색 최적화 — 로컬 변경 | 동족·위협·늑대 표적/포획 후보에 XY 해시 격자, 밀집 시 전체 탐색 fallback. 기존 후보 순서 보존 | [측정/한계](../Performance/SPATIAL_SEARCH_20261106.md). Native CPU 벤치마크이며 2000개체 게임 프레임 검증 완료는 아님 |
| 먹이 기반 풀 표현 — 오늘 로컬 변경 | 전체 셀 Food/Capacity 변경분 전송, 안정 후보 ISM, 거리별 표현·지면 재시도, 먹이 0 제거/회복, 기후·수원 진단 | [풀 테스트](FOOD_GRASS_TEST_GUIDE_20261108.md), `World/EcoVegetationField.*`. 별도 풀 Actor마다 자원을 소유하지 않음 |
| 공유 풀 패치 S1 — 오늘 로컬 변경 | 공통 배치 함수·ID/epoch/hash, Native static cache, 서버 지면 anchor·압축 DTO, Client의 동일 anchor 렌더 | [S0/S1 기록](FOOD_PATCH_GRAZING_S0_S1_20261108.md), `Core/EcoFoodPatchLayout.*`. **기본 OFF, 소비는 여전히 셀 단위** |

Source 경로의 생략된 앞부분은 `AdaptiveEcosystem/Source/AdaptiveEcosystem/`이다. 각 시스템의 기본값이 모든 맵에서 ON이라는 의미는 아니다.

추가로 [SpeciesAI](../Integration/SpeciesAI/README.md)에는 StateTree/Utility·NavMesh·Smart Object 기반의 별도 opt-in 코드/설정이 있다. 기본 M1~M5 코드와 에셋 재로드 기록은 있으나 해당 기록의 실제 PIE/네트워크 gate는 미수행이다. 현재 1102의 Native v3 경로를 이것으로 교체하거나 두 이동 writer를 함께 켜지 않는다. 프로젝트에서 SmartObjects 플러그인이 enabled인 것과 오늘 공유 풀 패치가 Smart Objects를 사용한다는 것은 다르다.

## 3. 최근에 무엇이 추가됐나

| 시점 | 추가/확장 |
|---|---|
| 10-16~23 | v3 Social 인계, 보호 은신처, 신호 계약, 무리 식량 이주와 지도, soil/life 실행·저장·멀티 연결 |
| 11-06 커밋 | 공통 게임 기반·서버 낮밤 시계, GAS 사냥/콤보·피격/부활, 1102 사냥 지역/경로, 총기, 지도 UI 개선, 공통 체력 바, Client 카메라 기준 표시 거리 |
| 11-06 이후 현재 로컬 | 공간 탐색 격자와 결정성 비교/벤치마크 |
| 11-08 현재 로컬 | 먹이 격자 풀 표현·고갈/회복·환경 진단·복제/streaming 계측, 1102 4지역 배치, 공유 풀 패치 S0 조사/S1 위치·지면 연결 |

### 아직 완료되지 않은 사용자 체감 기능

- **특정 풀 패치 검색→예약→접근→입/도착 판정→그 패치 소비**: S2~S6 중 후속 구현이 필요하다. 현 소비는 이동 후 body가 속한 4m×4m 셀을 사용한다. 먹은 위치와 사라진 풀 무더기가 어긋나는 문제를 S1 완료로 해결됐다고 설명하지 않는다.
- **배부른 사슴의 지속적인 식사 중단/휴식·경계·탐색 전환**과 Nutrition을 함께 보는 늑대 포만 규칙: 후속 계획이다. 기존 늑대 포만 timer는 있으나 요청된 생활 흐름 전체가 완성된 것은 아니다.
- **늑대의 증거 기반 지역 간 추적 이주**: 지역 내 감지/추격·흔적 조사와 구분한다. 사슴 Migration을 늑대에 연결 완료한 상태가 아니다.
- **1102의 강화된 부족 이주/실제 도착 전체 검수**: JYU의 기존 검증과 1102의 새 4지역·지속 가능성 요구를 구분한다.
- 새 life/이주/패치 세계 전체 Python parity·재학습, 대규모/WAN·분산 서버, 최신 전체 코드의 Game/패키지 회귀는 별도 완료 항목이다.

상세 후속 범위는 [1102 개발 계획](JWJ_1102_FOOD_MIGRATION_SATIETY_PLAN_20261108.md), [패치 명세](FOOD_PATCH_GRAZING_IMPLEMENTATION_SPEC_20261108.md)를 따른다.

## 4. 이해를 위한 공식 문서

아래 링크는 2026-11-08 웹 확인 기준이다. Epic 문서는 UE **5.8** 버전을 선택해서 읽는다. 공식 문서는 엔진 기능을 설명하며 프로젝트 고유의 FoodGrid·장부·안전 규칙 자체를 보장하지 않는다.

| 읽을 순서/주제 | 자료 | 프로젝트에서 이해할 것 |
|---|---|---|
| 1. 개체 데이터와 실행 | [Epic: MassEntity Overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-mass-entity-in-unreal-engine) | Fragment/Entity/Archetype/Chunk/Processor, 데이터와 처리 분리 |
| 2. 서버 권위 | [Epic: Networking Overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/networking-overview-for-unreal-engine) | 서버 논리와 Client 수신 표현, Actor/RPC의 역할 |
| 3. 변경분 전송 | [Epic: FFastArraySerializer](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/NetCore/FFastArraySerializer) | 셀/개체 배열의 변경 추적과 delta serialization. 엔진 API 문서와 프로젝트 publisher를 함께 확인 |
| 4. 풀 대량 표현 | [Epic: Instanced Static Mesh Component](https://dev.epicgames.com/documentation/en-us/unreal-engine/instanced-static-mesh-component-in-unreal-engine) | 동일 메시의 여러 인스턴스, component/instance 데이터, ISM/HISM 차이 |
| 5. 같은 풀 배치 재현 | [Epic: Random Streams](https://dev.epicgames.com/documentation/en-us/unreal-engine/random-streams-in-unreal-engine) | seed와 난수 호출 순서가 고정 배치를 만드는 원리. terrain Z 동기화는 별도 프로젝트 계약 |
| 6. 대형 맵 | [Epic: World Partition](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine) | streaming source·grid·거리별 로드. 지형 unload와 생태 논리 중단은 별개 |
| 7. 전투 | [Epic: Gameplay Ability System](https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-for-unreal-engine), [ASC와 Attributes](https://dev.epicgames.com/documentation/unreal-engine/gameplay-ability-system-component-and-gameplay-attributes-in-unreal-engine) | ASC/Ability/Attribute/Effect, PlayerState와 Pawn의 관계, HP와 부활 인계 |
| 8. 비용 확인 | [Epic: Unreal Insights](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-insights-in-unreal-engine) | 프레임/작업 시간 계측. 후보 감소·컨테이너 메모리·전체 게임 비용을 분리 |
| 9. 멀티 시험 | [Epic: Testing Multiplayer](https://dev.epicgames.com/documentation/en-us/unreal-engine/testing-multiplayer-in-unreal-engine) | PIE의 인원/NetMode·창 설정, Listen과 Dedicated의 차이 |
| 선택: 별도 AI 경로 | [Epic: StateTree](https://dev.epicgames.com/documentation/en-us/unreal-engine/state-tree-in-unreal-engine), [Smart Objects](https://dev.epicgames.com/documentation/en-us/unreal-engine/smart-objects-in-unreal-engine) | 상태/전이와 예약 가능한 활동. 현 Native v3/shared patch가 이 엔진 기능들로 실행된다고 해석하지 않음 |

### 게임 기술 자료·원전

| 자료 | 읽는 이유와 적용 경계 |
|---|---|
| [Craig Reynolds — Steering Behaviors for Autonomous Characters, GDC 1999](https://www.red3d.com/cwr/steer/) | Seek/Flee/Arrival/Path Following과 separation/alignment/cohesion 이해. 이동 목표·조향·실제 locomotion을 나눠 읽는다. Persistent Herd의 정체성은 별도다 |
| [Game AI Pro 3, Mike Lewis — Choosing Effective Utility-Based Considerations](https://www.gameaipro.com/GameAIPro3/GameAIPro3_Chapter13_Choosing_Effective_Utility-Based_Considerations.pdf) | Guild Wars 2: Heart of Thorns의 행동 평가·정규화/response curve 사례. 종·상황별 행동 선택을 이해하는 비교 자료이며 현 PPO 정책을 Utility AI로 교체했다는 뜻은 아님 |
| [GDC 2015, Mike Lewis / Dave Mark — Building a Better Centaur: AI at Massive Scale](https://gdcvault.com/play/1021848/Building-a-Better-Centaur-AI) | MMO의 다수 종·행동을 모듈식 Utility와 influence map으로 구성한 제작 사례. 프로젝트의 현재 구현 방식과 비교해서 읽는다 |
| [Glenn Fiedler — Snapshot Interpolation](https://gafferongames.com/post/snapshot_interpolation/) | 서버 표본과 Client의 보간된 표시 위치가 다른 이유, 지연과 부드러움의 관계 이해. 현재 transport를 이 글과 동일한 구현으로 단정하지 않음 |
| [Schulman 외 — Proximal Policy Optimization Algorithms, 2017](https://arxiv.org/abs/1707.06347) | PPO 학습 알고리즘 원전. 먼저 프로젝트 관측/행동 계약을 읽고 clipped objective와 학습/추론의 차이를 확인 |

처음에는 **Mass → Networking → ISM/Random Streams → GAS → 프로젝트 life 계약** 순서가 이해하기 쉽다. AI 담당이면 PPO 계약·Reynolds·Utility 사례를, 서버 담당이면 FastArray·보간·checkpoint 계약을 이어 읽는다.

## 5. 가장 간단한 수동 테스트

### 공통 세팅

| 항목 | 권장 입력 |
|---|---|
| 프로젝트 | 원래 `AdaptiveEcosystem/AdaptiveEcosystem.uproject` |
| 첫 실행 모드 | Play 메뉴 **Standalone Game**, 플레이어 1명. 첫 확인은 서버 권위가 있는 단일 게임으로 진행 |
| 사냥·4지역 풀 | `/Game/JWJ/1102_Integration_JWJ` |
| 토양·환경·life | `/Game/JYU/Maps/LV_JYU_Ecosystem` |
| 이주 전용 기준 장면 | `/Game/JYU/Maps/LV_JYU_HerdMigration` |
| 기존 spawner | 해당 맵의 기존 `EcoCreatureIntegrationSpawner`/파생 BP 하나를 사용. 새 bootstrap/coordinator를 추가하지 않음 |
| 식생/생활 | 기존 맵에 저장된 `Use V3 Policy`, `Enable Vegetation`, `Enable Ecosystem Life` 설정 유지. 풀만 기존 맵에 임시 활성화할 때는 시작 전에 `eco.Grass.Enable 1` |
| 1102 풀 Field | 현재 저장된 `BP_JYU_VegetationField`. 맵 setup 스크립트는 점검 목적으로 재실행하지 않음 |
| 행동 기준 | `eco.IntegratedV3.SocialControl 0`, `eco.Grass.PatchLayout 0`을 기준으로 시작. waves/새 AI backend는 시험을 위해 임의 활성화하지 않음 |
| 보기 범위 | Standalone은 **Host Visual Distance**, Client는 **Client Visual Distance**. 넓게 관찰할 때 임시 `20000cm` 권장. Client 기본은 `1000cm=10m` |
| 관찰 수치 | Inspector `eco.Inspector.Visible 1`, 식생 Alt+G, 지도 M. 지도는 권위 창에서 확인 |

`eco.Grass.Enable`, `eco.Vegetation`, `eco.Grass.PatchLayout`은 **게임 월드 시작 전** 설정이다. 별도 Standalone 프로세스에 editor console 값이 전달된다고 가정하지 말고 필요한 경우 Launch의 Additional Launch Parameters에 `-ExecCmds="eco.Grass.PatchLayout 1"`처럼 전달한다. 실행 중 표현 토글/환경 명령은 해당 게임 창 콘솔에서 수행한다. 매번 필수로 전체 옵션을 바꾸지 말고 저장된 맵 설정부터 확인한다.

1102의 현재 지역은 `JWJ_WildlifeTest` (0,0), `JWJ_HuntingMeadow` (+15000,0), `JWJ_SouthRange` (0,-15000), `JWJ_WestRange` (-15000,0)cm다. 중심 연결점과 각 주변 지역 사이의 왕복 경로를 사용한다. S0/S1 seed23 실행의 시작 개체는 지역별 사슴12·늑대4였지만 저작 SpawnGroup와 Native override를 구분하고 실행 HUD/log를 우선한다.

### A. 3분: 풀과 생태 논리가 연결됐는지

1. JYU Ecosystem 맵으로 Standalone을 시작하고 **Alt+G**를 누른다. **Alt+1**로 지역 선택, **Alt+2** 건조 → 약30초 → **Alt+3** 회복 강수 → 약30초 → **Alt+4** 자동 환경 복귀를 시험한다. HUD 키 조작의 최종 화면 검수는 남아 있으므로 실패하면 아래 콘솔로 같은 입력을 확인한다.
2. 콘솔 `eco.Grass.Visual 0` → `eco.Grass.Visual 1`. 풀이 숨었다 돌아와도 Food/수분/개체 상태가 계속 진행해야 한다.
3. 소비·성장·환경 손실과 잔량을 함께 읽는다. 장식 foliage와 은신처 외형은 별도이므로 풀 전체가 FoodGrid를 뜻한다고 보지 않는다. 먹는 애니메이션만으로 실제 섭취를 판단하지 않는다.

```text
eco.Grass.Climate Forest 0 30
eco.Grass.Climate Forest 0.5 20
eco.Grass.Auto Forest
eco.Grass.Export Forest
```

위 명령은 **한 줄씩, 관찰 시간을 두고** 실행한다. `Forest`는 JYU 예시다. 1102라면 실제 RegionId인 `JWJ_WildlifeTest` 등으로 바꾼다. 정확한 0 고갈을 더 빨리 시험하는 개발 조건은 `0강수/50℃ 약48초 → 0.5강수/20℃ 약48초 → Auto`다. 이것은 자연 기후 시험이 아니며 모든 셀이 같은 시간에 0이 되지는 않는다. 권위 콘솔만 기후/수원을 바꿀 수 있다. Export는 `Saved/FoodGrass/`에 JSON을 쓴다.

### B. 3분: 사냥·체력·부활

1. 1102 맵의 기존 common player로 접근한다. **F**로 콤보를 시작하고 회수 구간에 다시 눌러 다음 타격을 연결한다. 길게 누르는 것과 재입력은 다르다. 낮은 늑대에게 손이 빗나가면 발차기까지 확인한다.
2. 현재 총기 입력은 **우클릭 조준, 좌클릭 사격**이다. common player의 initial weapon 설정을 사용한다. 무기가 없으면 기존 Pawn/Input/Equipment 참조를 먼저 점검하고 setup 스크립트로 맵을 덮어쓰지 않는다.
3. 동물 체력 바가 감소하고 같은 타격 창의 중복 피해가 없는지 확인한다. 로그 `[EcoCombo] Contact`는 접촉, `[EcoCombat][Outcome]`은 피해 확정, `[EcoCombat][DeathCommitted]`는 단일 사망 장부다.
4. 늑대 근처에서 플레이어 HP 변화를 관찰한다. 기존 규칙의 명중 피해20, HP100→0 이후 기본5초 뒤 새 Pawn/HP100 복귀가 기준이다. 차폐·방향·늑대 상태에 따라 공격이 지연/실패할 수 있다.

### C. 2~5분: 이주 계획과 실제 이동 구분

**11-09 후속 진단:** Standalone에서 가뭄 성공 로그가 나와도 계획이 없을 수 있다. 현재 이주는 같은 Persistent Herd의2마리 이상만 출발 후보로 다룬다. 동일1102/seed20000 기존 관측은 사슴12마리가 각각1마리 무리를 유지했다. 최신 사용자 실행의 가뭄 성공·Plan 로그 부재, 가장 유력한 차단 조건과 아직 미확정인 항목은 [계획 없음 진단](JWJ_HERD_MIGRATION_NO_PLAN_DIAGNOSIS_20261109.md)을 먼저 확인한다. 아래 절차를1102의 계획 생성/도착 검증 완료로 읽지 않는다.

처음에는 이주 기준 맵을 권장한다. 1102에서는 기존 경로를 재현하는 시험이며 새 4지역 요구 전체가 이미 통과한 것은 아니다. **Standalone Game의 권위 콘솔**에서 다음을 실행한다.

**1102 실행 모드 주의:** Play 버튼 옆 메뉴의 **Standalone Game**으로 별도 게임 프로세스를 실행한다. 일반 Selected Viewport/New Editor Window PIE에서 NetMode만 Standalone으로 설정하는 것과 다르다. 현재 가뭄 fixture는 JWJ 맵 패키지를 `/Game/JWJ/1102_Integration_JWJ`와 정확히 비교하므로 `/Game/JWJ/UEDPIE_0_1102_Integration_JWJ`는 거절한다. 세 명령은 게임 창 콘솔에서 **한 줄 입력→Enter**를 각각 반복한다. 여러 줄을 한 번에 붙여 넣으면 명령이 붙어 첫 CVar만 적용될 수 있다.

```text
eco.HerdMigration 1
eco.HerdMigration.Debug 2
eco.HerdMigration.Test.Drought JWJ_WildlifeTest
```

2026-11-09 실제 사용자 실행 로그에서 두 입력 문제를 확인했다. 최초 입력은 `eco.HerdMigration 1eco.HerdMigration.Debug 2eco.HerdMigration.Test.Drought JWJ_WildlifeTest`로 합쳐졌다. 이후 명령을 나눠 실행했지만 일반 PIE 맵이어서 마지막 명령이 `Drought fixture rejected (owned authority map and region required).`로 거절됐다. 이 경우 가뭄에 의한 먹이 제거는 적용되지 않았으므로 기다리는 것만으로 이 시험을 진행할 수 없다.

별도 Standalone Game에서 다시 실행한 뒤 첫 확인은 `[HerdMigration][AuditFoodLoss] Region=JWJ_WildlifeTest ... After=0.000000 SuspendRegen=1` 로그다. 이 성공 로그가 없으면 이주 관찰보다 입력/실행 모드 확인을 먼저 한다. 코드를 수정하거나 맵 검사를 해제한 것은 아니며, 이 문서 보완 중 새 Play를 실행하지 않았다.

마지막 지역은 1102용이다. JYU HerdMigration에서는 실제 지역 ID인 `Barren`을 사용한다. 이 시험의 질문은 **“먹이가 사라진 지역의 사슴 무리가 다른 지역으로 실제로 옮겨 정착하는가?”**다. 늑대의 지역 간 추적 이주를 확인하는 시험은 아니다.

`Debug 2`를 실행하면 지도는 이미 켜진다. 보일 때 `M`을 누르면 오히려 꺼지므로, `M`은 필요할 때만 토글한다. `[`/`]`로 출발지가 `JWJ_WildlifeTest`인 계획을 고른다. 새 4지역 구성에서는 목적지를 동쪽 Meadow로 미리 단정하지 말고 선택한 계획의 `출발지 -> 목적지`를 읽는다.

| 순서 | 어디를 볼 것인가 | 관찰해야 하는 변화 | 그 단계의 의미 |
|---|---|---|---|
| 1. 가뭄 적용 | 지도에서 `JWJ_WildlifeTest`의 `Food`, 로그의 `[HerdMigration][AuditFoodLoss]` | 실행 전 Food를 기록하고 명령 뒤 감소했는지 비교. 로그의 Before/After·SuspendRegen 확인 | 시험 입력이 적용됨. 아직 출발 성공은 아님 |
| 2. 계획 생성 | 지도 아래 `Herd / Plan`, `출발지 -> 목적지`, 상태 | `No departure...` 대신 해당 지역에서 출발하는 계획이 나타남. `Preparing`은 집결, `Traveling`은 이동 단계 | 부족을 인식하고 목적지를 선택함 |
| 3. 실제 이동 | 흰 테두리의 초록 점(선택한 계획의 사슴), `waypoint x/y` | 같은 점들이 출발 지역에서 하늘색 경로 방향으로 움직이고 waypoint가 전진 | 실제 Native body가 이동 중. 고정된 하늘색 경로선만 보이는 것은 이동 증거가 아님 |
| 4. 목적지 진입 | 선택한 계획의 `In target a/b` | a가0에서 증가. b는 현재 살아 있는 계획 구성원 수 | 일부 개체의 실제 RegionId가 목적지로 변경됨. 경로 끝까지 도착한 상태와는 다름 |
| 5. 경로 끝 도착 | 같은 줄의 `Finished`, `Dead`와 상태 | Finished 증가 후 `Settled`. 현재 목적지가 의도한 다른 지역인지, `(return)`이 아닌지 함께 확인 | 살아남은 구성원의 실제 정착 확인. 사망/복귀로 종료된 계획과 구분 |

예를 들어 **사망 없이6마리인 무리**가 다른 지역에 모두 도착했다면 `In target 6/6`, 같은 계획의 `Finished 6`, `Dead 0`, 상태 `Settled`가 기대된다. 이는 표시 해석 예시이며 실제 시작 마릿수나 전원 생존을 보장하는 값은 아니다. 위쪽 요약 `Active herds ... Finished ...`의 Finished는 **끝난 계획 수**, 아래 선택 계획의 Finished는 **경로 여행을 마친 개체 수**여서 서로 다르다.

부족 기준은 기본 잔량25% 미만이8초 지속되는 것이지만 목적지 보고·무리·유효 경로도 필요하므로8초 뒤 반드시 출발하는 것은 아니다. `Resting`/`Regrouping`이면 휴식·재집결 후 재개하는지 본다. `Blocked`면 점/waypoint가 멈췄는지와 Reason을 기록한다. 이는 무진행 진단이며 지형 충돌 확정은 아니다. `(return)`이면 복귀이며 처음 목적지로의 이주 성공과 구분한다. 플레이어가 계속 사슴을 쫓아가면 회피 반응이 섞이므로 떨어져서 지도 위주로 관찰한다.

간단한 화면 검수는 위5단계로 진행한다. 자원/인구 장부의 엄밀 검증은 별도로 MigrationOut/In과 개체 RegionId를 대조해야 하며, 현재 지도에는 MigrationOut/In 숫자를 직접 표시하지 않는다. 지도 `Pop`은 출생·사망·다른 무리 이동에도 변하므로 그것만으로 이주 건수를 계산하지 않는다. 이 가뭄은 개발 fixture로 먹이를 제거/재생 정지하므로 자연 사냥이 만든 이주로 설명하지 않는다. PIE 이름/Client 권위 제한으로 거절되면 Standalone과 정확한 맵부터 확인한다.

### D. 별도 선택: 오늘 S1만 보기

1102 시작 전에 `eco.Grass.PatchLayout 1`을 전달한다. 같은 셀의 패치 후보 위치·지면 anchor가 서버와 Client에서 맞는지 확인하는 모드다. **예약·도착 섭식은 바뀌지 않는다.** 이 모드의 save/load는 schema 미완료로 거절된다. 기준 세계로 돌아가려면 다음 실행을 `eco.Grass.PatchLayout 0`으로 시작한다.

## 6. 멀티·자동 재현을 더 하고 싶을 때

수동 PIE는 New Editor Window, Players=2, NetMode=Play As Client의 Dedicated 구성을 사용한다. 로컬 접속 실패를 생태계 실패로 혼동하지 않도록 프로젝트 runner의 `-nosteam`, `EcoProtocol=1` 조건을 참고한다. Client에서는 풀/체력/위치 수신을 관찰하고 기후·생태 장부/이주 명령은 서버에서 실행한다. Client의 권위 논리 개체/Native Step은0이어야 한다. Client 표시 거리0은 로컬 거리 제한만 해제하며 network relevance와 Actor 예산은 유지한다.

재현 도구는 **기존 Unreal/UBT/dotnet/Live Coding/MSBuild/ShaderCompileWorker가 종료된 상태**에서 저장소 루트 PowerShell로 실행한다. 이 도구들은 실행 중 프로세스를 중단하지 않고 사용 중이면 거절한다. 결과 폴더 이름은 새 이름을 사용한다.

```powershell
# 65초 S1 로컬 위치·CPU 관찰. 저장된 맵/에셋을 바꾸지 않는다.
& ./AdaptiveEcosystem/Tools/Editor/test_food_patch_layout.ps1 -Mode Profile -Duration 65 -PatchLayout -AuditFolder QuickPatch_20261108_A

# 총기 입력부터 두 Client의 동일 체력 바 수신까지 재현하는 기존 fixture
& ./AdaptiveEcosystem/Tools/Editor/run_health_bar_network.ps1 -RenderedClients

# 1102 S1 전용 풀/anchor + Dedicated/Client2/late join 검사
& ./AdaptiveEcosystem/Tools/Editor/test_vegetation_network.ps1 -Map /Game/JWJ/1102_Integration_JWJ -AuthoredWeather -DeerPerRegion 12 -PatchLayout -FoodPatchCheck -Duration 145 -ExitAfter 185 -ClientAAt 30 -ClientBAt 95 -OverlapClients -ClientVisualDistanceCm 20000 -AuditFolder QuickGrassNet_20261108_A
```

마지막 시험은 풀/anchor acceptance이며 일반 life/카메라 순회·입 도착·패치 소비 전체 검수가 아니다. 체력 fixture는 위치/무적과 조준을 제어하는 UI 검증이므로 수동 조준 적중률·lag compensation 증거로 읽지 않는다. 자동화 UI에서는 `AdaptiveEcosystem.Vegetation` 그룹으로 현재 식생/패치 테스트를 찾을 수 있다.

저장 시험은 별도로 **PatchLayout 0**, 같은 map/model/runtime binary를 사용한다. `eco.Ecosystem.Save QuickTest` 후 새 프로세스에서 초기 상태보다 앞선 checkpoint를 이른 시점에 `eco.Ecosystem.Load QuickTest`로 복원한다. 같은 실행을 오래 진행한 뒤 옛 상태로 되감는 live rollback은 거절된다. 파일은 `Saved/Ecosystem/QuickTest.eco`이며 재빌드 후 호환을 가정하지 않는다.

## 7. 검증 기록과 현재 한계

| 기존 근거 | 확인한 범위 |
|---|---|
| 10-23 life | 자동화225개(224 Success+예상 warning1), PIE/동시 Client2·장기 seed 비교·동일 빌드 재시작 저장·당시 패키지 실행. 현재 모든 변경의 회귀 통과 수가 아님 |
| 11-06 체력 바 | 렌더 Dedicated+Client2, 같은 대상 HP100→70→40과 두 Client의 수신 체력 비율 일치. 관련 Visual/Combat11개 성공(기존 warning1 포함) |
| 공간 탐색 로컬 | 직접 Editor UBT, V3 자동화128개 성공, 전체 탐색/격자 결과 비교. 분산1024사슴 조건의 Native100스텝 CPU38.38% 감소, 밀집 조건1.37% 증가. 엔진 프레임 개선률이 아님 |
| 오늘 풀 | JYU에서 실제 섭식 셀→DTO→ISM, 정확0 제거/같은 셀 회복, Client2/late join·실제 terrain streaming·CPU/전송량 계측 기록 |
| 오늘 S1 | 로컬 manifest의 식생15개 성공/경고·실패0, 직접 Editor UBT 성공. 1102 Dedicated+Client2/late join의 네 지역 anchor checksum 일치, Client 논리/Native0. `evidence_checks_passed=true`, **`formal_budget_qualified=false`** |

오늘 S1의 근거는 로컬 `Saved/FoodPatchGrazing_20261108_Start/Manifest.json`과 [S0/S1 기록](FOOD_PATCH_GRAZING_S0_S1_20261108.md)이다. 원시 Saved는 Git 제외이므로 팀원의 clone에 자동 제공되지 않는다. 오늘 전체 grazing A/B·3seed×180초 정식 비용 비교·30분 soak·최신 저장/기존 HUD/Game/패키지 회귀까지 끝났다고 간주하지 않는다.

이번 정리는 Source/문서/기존 manifest와 공식 웹 자료를 읽어 새 Markdown 안내만 추가했다. 소스·에셋·기본값은 변경하지 않았으며 빌드·Play는 새로 실행하지 않았다.
