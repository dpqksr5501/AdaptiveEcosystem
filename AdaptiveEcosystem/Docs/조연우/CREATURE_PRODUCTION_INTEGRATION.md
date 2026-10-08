# 사슴·늑대 BP / PPO·Social·Mass 네트워크 통합

작성: 2026-10-08. 기준: 자산 이주 commit `47faebc` 이후 현재 작업 트리. 아래는 별도 opt-in 통합 레벨의 구현·검증 기록이며 기존 JYU/M3 맵 전체의 전환 완료를 뜻하지 않는다.

## 바로 실행

1. UE 5.8에서 `/Game/Creatures/Integrated/L_EcoCreatureIntegration`을 연다.
2. Play 또는 Standalone을 실행한다. 초기 구성은 Forest_A 사슴 8 + 늑대 1, Forest_B 사슴 4 + 늑대 1이다.
3. Play 설정에서 Players=2, Play As Client 및 전용 서버 실행을 선택하면 같은 맵·EntityConfig로 복제를 확인할 수 있다. Single Process PIE는 이번 CLI 검증과 별개이며 아래 실제 별도 프로세스 테스트를 우선 근거로 삼는다.
4. 서버/Standalone 콘솔에서 `eco.Shelter.Log 1`을 입력하면 예약 → Moving → Occupied, 사망·요구 종료 시 해제를 확인할 수 있다. `eco.Social.ActionAudit 1`은 Raw/Effective 보정 진단이다.
5. 개발 빌드의 `Debug.Starvation.Forest_A`는 기존 자원 이벤트 API로 A 지역 먹이를 고갈시킨다. 이주는 인접 Region의 먹이와 실제 도착 위치를 기준으로 결정한다.

동물 BP를 맵에 단독 배치하면 논리 Entity가 생기지 않는다. 배치할 대상은 지역·은신처와 `BP_EcoCreatureIntegration` 조정자 하나다. 그 조정자가 Mass Entity를 만들고 해당 BP를 수동 표현으로 연결한다. 기존 `AEcoMassNetworkBootstrap`과 같은 맵에 놓으면 충돌을 감지하고 시작을 거부한다.

웨이브는 기본 꺼져 있다. 포식으로 사슴이 줄어들어도 재스폰하지 않으며 자원/인구 요약은 계속 갱신된다. 반복 관찰이 필요하면 조정자의 `Enable Waves`와 각 그룹의 기존 Spawn Schedule을 설정한다. 웨이브 운영과 장시간 개체군 균형은 기본 시나리오 검증 범위 밖이다.

## 저장된 에셋

| 에셋 (`/Game/Creatures/Integrated/`) | 용도 |
|---|---|
| `BP_EcoDeer`, `BP_EcoWolf` | 이주한 AnimalVarietyPack 사슴/늑대 Mesh를 가진 passive 표현 Actor |
| `BS_EcoDeer`, `BS_EcoWolf` | Speed 0/300/900cm/s → IdleBreathe/Walk/Run, 호환 Skeleton·in-place Animation |
| `DA_EcoDeer`, `DA_EcoWolf` | `UEcoCreatureEntityConfig`와 역할별 native Trait; 저장된 GUID로 서버/Client TemplateID 일치 |
| `BP_EcoCreatureIntegration` | configs, BP classes, 2개 지역 스폰 그룹, 낮/밤 각 30초 설정 |
| `L_EcoCreatureIntegration` | 바닥, 인접한 두 지역, 수동 Shelter 4개, 조명·관찰용 PlayerStart, 전용 GameMode |

BS는 일반 `UBlendSpace1D` 에셋이다. 표현 Actor가 `AnimSingleNodeInstance`로 실제 수신 속도를 넣어 재생하므로 별도 AnimBP 그래프가 필요하지 않다. 사망 시 각 종의 Death Animation을 재생한다. Eating은 현재 상태 DTO만 전달하고 별도 먹기 Animation은 연결하지 않았다. Root Motion과 Actor AI 이동은 사용하지 않는다. 모델 교체 시 Mesh, BS, Death Animation의 Skeleton 호환성을 함께 확인한다.

재생성 도구: [`Tools/Editor/create_creature_integration.py`](../../Tools/Editor/create_creature_integration.py). Editor Python API로 새 디렉터리만 생성/갱신한다. 기존 맵·원본 동물 자산은 수정하지 않는다. 실행하면 이 통합 맵의 그룹/회전/참조는 명시된 기본값으로 다시 저장되므로 사용자 편집을 보존할 때에는 무조건 재실행하지 않는다. Config가 이미 있으면 다시 구성하거나 GUID를 바꾸지 않는다.

## 실행 경로와 책임

```text
Server / Standalone
regional FoodAmount / PredationHistory + authored Shelter geometry
  → 기존 개체별 Observation → 기존 Native PPO Raw Action
  → Social 감지·무리·경보·Response → Request(EffectiveAction / 목적지 / lease)
  → 단일 종별 이동 writer → Transform / Velocity → Feedback
  → 세계 프레임 종료: 먹이 배분·Energy·사망 정리·이주·지역 인구·요약
  → 기존 Mass Bubble: 위치/yaw + 시각용 속도/생존/먹기/추적/HP·Energy 요약
Client
  → 저장된 동일 GUID의 proxy template → 수신 fragment → passive BP / BS
```

| 영역 | 연결 및 소유권 |
|---|---|
| RL 담당 | 기존 7→64→64→4 가중치·관측 순서·정규화·역매핑 유지. 사슴은 기존 Native Policy를 사용한다. 늑대는 기존 포식 판정/탐색 규칙을 사용하는 별도 이동 Processor이며 PPO로 학습된 늑대라고 표현하지 않는다. |
| 조연우 Social | 기존 Herd/Alarm/개인·무리 감각/차폐·슬롯 예약, Raw를 보존한 EffectiveAction, 목적지·lease, 도착/실패/죽음/삭제/이주 해제. 후각 추가 없음. Social 내부에는 위치 적분·먹이 차감·복제 transport를 추가하지 않았다. |
| 이동 | 사슴 `UEcoSteeringProcessor`, 늑대 `UEcoCreaturePredatorProcessor`. 두 종은 서로 다른 쿼리이며 CustomMovementTag로 엔진 ApplyMovement를 제외한다. IntegratedTag는 기존 Migration Steering에서도 제외한다. 기존 M3 가드는 유지한다. |
| 자원/생명주기 연결 | 별도 조정자가 기존 Ecology 배치 API를 사용한다. 지역 먹이 차감 후 받은 양을 Energy에 반영하고 실제 생존 인구·PredationHistory를 다시 집계한다. 기존 M3 Lifecycle은 이 시나리오에서 시작하지 않는다. |
| 네트워크 담당 | 기존 MassReplication/Bubble/FastArray 사용. 새 visual payload를 추가했으므로 서버·Client를 같은 코드로 다시 빌드해야 한다. Client는 Vitals/Policy/Social/Travel 논리 template을 생성하지 않는다. Subsystem에 RPC를 추가하지 않았다. |
| World/레벨 담당 | Region·인접성·바닥 collision·authored Shelter·환경 상태 제공. 새 맵은 평면 검증 맵이며 황폐/숲/고지대의 최종 지형을 대신하지 않는다. |

중요한 소스:

- [`Creature/Runtime/EcoCreatureNetworkTrait.cpp`](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureNetworkTrait.cpp): Server/Client 구성 분리.
- [`Creature/Runtime/EcoCreatureMovement.h`](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureMovement.h): 이동 우선순위, 예약 세대별 Feedback.
- [`AI/Policy/EcoBehaviorProcessors.cpp`](../../Source/AdaptiveEcosystem/AI/Policy/EcoBehaviorProcessors.cpp): Raw/Effective 소비, 단일 사슴 이동, 실제 자원/피식 관측.
- [`Creature/Runtime/EcoCreatureIntegrationSpawner.cpp`](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.cpp): 폐루프 연결·실제 지역 집계·표현 수명.
- [`Creature/Representation/EcoCreatureRepresentationActor.cpp`](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureRepresentationActor.cpp): 논리와 분리된 수신 상태/BS 재생.
- [`Network/Mass/EcoMassReplicator.cpp`](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp), [`EcoMassClientBubble.cpp`](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.cpp): 선택적인 visual fragment 복제.

## 이동·예약·프레임 계약

- 우선순위는 죽음/무효 HP 정지 → Traveling/Waiting → 유효 ShelterTravel/Hold → Effective PPO 조향(없으면 기존 Raw)이다. Traveling은 Shelter Feedback에 Yielded를 반환한다.
- Movement는 Request를 읽고 해당 ReservationId의 Moving/Arrived/Failed/Yielded를 반환한다. Social Lifecycle은 다음 패스에서 이를 소비한다. Raw Action은 덮어쓰지 않는다.
- 지역 밖 이동, 정적 장애물 sweep, 바닥 부재/급경사 실패는 정지하고 lease가 있으면 Failed를 반환한다. 현재 직선 조향에는 NavMesh 장애물 우회·ORCA가 없다. 지역 이주 중에는 출발 지역 경계를 넘을 수 있고 목적지 Region 내부에 실제 도착해야 resident로 바뀐다.
- 조정은 `OnWorldPostActorTick`에서 해당 World만 처리한다. Mass 전체 phase의 완료 이후에 Alive 제거·batch destruction을 처리해 replication destruction observer가 삭제 전 fragment를 읽게 한다. `IsProcessing()==false`만으로는 phase observer lock 해제를 보증하지 않으므로 Actor의 PostPhysics Tick에서 구조 변경하지 않는다.
- Alive 제거는 archetype을 바꾼다. StableAgentId를 미리 복사하고 fragment 참조를 재취득한다. 사망 표현은 약 2초 후 정리된다.
- 자원 처리 실패는 Runtime stopped 로그와 readiness=false로 명시한다. 개발 테스트 종료 인자는 실패 상태에서도 실행되어 테스트 프로세스가 무한 대기하지 않는다.

## 통합 완료와 남은 담당 연결 구분

- 구현됨: 저장된 실제 사슴/늑대 BP·BS, 개체별 기존 PPO, Social Request/Feedback 실제 소비, 실제 Shelter 도착·점유/해제, 배치 자원 소비·Energy·피식/죽음/인구 피드백, 기존 네트워크 프록시 표현.
- 기존 낮/밤 clock을 Social이 읽는 경로를 사용한다. 시각 sky cycle·밤/낮 전용 trait 진화나 새 PPO 관측을 구현한 것은 아니다.
- 기존 World 환경 상태를 감각 계층이 읽는다. 이 맵에 날씨 BP→지역 EnvironmentState 또는 날씨→식생 크기/먹이 재생률 어댑터를 새로 붙이지 않았다. World 담당자가 기존 `UEcologyWorldSubsystem` 환경 갱신 API와 Ecology 자원 경계를 연결해야 한다.
- FoodDensity/Gradient는 실제 지역 FoodAmount/Capacity와 검증용 공간 분포를 사용한다. 개별 식물의 남은 양·성장·물 자원을 별도 원장으로 구현한 것이 아니다. 원본 Legacy vegetation/LLM Evolution에 의존하지 않는다.
- 기존 Python/C++ 생성 상수·Utility/조향과 V1 문서 사이에 알려진 차이는 유지한다. 새 평면+Social 시나리오가 기존 학습 분포와 다르므로 좋은 행동 품질/새 환경 parity를 보증하지 않는다. RL 담당자의 재학습·관측 확장 결정은 별도다.
- 기존 Steam session/로비/인터넷 접속, JYU 기존맵 이식, NavMesh 복잡 지형, 사운드 실제 청취, 성능/패키징 검증은 이번 기록에 포함하지 않는다. 로컬 IP의 실제 별도 서버·Client 연결을 검증했다.

## 검증 기록

UE 5.8 직접 UBT `AdaptiveEcosystemEditor Win64 Development -WaitMutex -NoHotReload -NoUBA` 빌드 성공. 실행 중 빌드/에디터와 겹쳐 새 빌드를 시작하지 않았다. 최초 UBA 권한 반복 정체 빌드의 종료는 사용자 명시 허용 후 수행했고, 이후는 직접 UBT 완료를 기다렸다.

| 검증 | 근거/결과 |
|---|---|
| 전체 자동화 | 33개 통과, 실패 0. 기존 Policy/Social/Mass/Network 테스트와 신규 integration 4개 포함. 최종 report는 `Saved/Automation/CreatureIntegrationFinal2/index.json`. |
| 실제 이동 인계 | 자동화에서 예약 획득→실제 Steering 도착→Occupied 정지, Raw 보존, 이주 Yielded/해제, 죽음 정지 확인. 만료/NaN/Hold Request 별도 검사. |
| 저장 에셋 | 실제 BP/BS/config load, 종별 authority template, Skeleton·3개 in-place samples, 실제 SingleNode BS playback, 시각 payload delta 검사. |
| 실제 Standalone | `CreatureIntegrationStandalone3.log`: 90 simulation seconds, 인구 14→2, 먹이 소비, Moving→Occupied, 사망 정리 후 Step85 이상 유지. 후속 프레임 경계 수정은 아래 별도 서버 테스트 및 최종 자동화에서 검증. |
| 실제 별도 서버/Client | `CreatureIntegrationServer4.log` 80초 정상 종료, Ready=1 Step79, initial14→wolves2, dedicated Visuals=0. `CreatureIntegrationClient4.log` 40초 정상 종료, NetMode3 LogicalOwned=0, 수신 deer BP의 Mesh/Speed900 확인. LOD 관련 개체만 수신하므로 Client Visuals=14 고정을 기대하지 않는다. |
| 실제 Shelter 서버 | Server4 로그 Reserved→Moving→Occupied와 죽음/요구 종료 lease 해제 확인. |
| 실제 렌더 | `CreatureIntegrationRender5.log`: Ready=1, 카메라 Pitch=-30/Yaw=90, 저장된 동물 Mesh/BS 표현 확인. `Saved/Screenshots/WindowsEditor/HighresScreenshot00004.png`를 직접 열어 평면 위 동물과 지면 그림자를 확인했다. |
| 실제 자원 고갈/이주 | `CreatureIntegrationMigration.log`: 기존 Debug.Starvation.Forest_A로 먹이 0 → A 사슴 Traveling → ID4/8이 21/22초에 실제 B 도착·Resident → B 배치 섭취. 70 simulation seconds 정상 종료, Step70 유지. |

로그 디렉터리: `Saved/Logs/`. 엔진 시작의 UnifiedErrorTest 자체 진단 출력과 프로젝트 테스트의 실패를 구분한다. 전체 자동화의 succeeded/failed와 실제 게임 실행의 assertion/Runtime stopped/종료 로그를 함께 확인했다.

MCP/Computer Use skill을 초기화했지만 이 세션의 native UI RPC(`sky`)는 구성되지 않았다. 마우스 조작 완료라고 기록하지 않는다. 자산 생성·저장은 Unreal Editor Python/native API로 수행했고 실제 엔진 프로세스/자동화/렌더 결과로 검증한다. 이후 팀원의 에디터 수동 편집은 위 에셋과 인계 계약을 따른다.
