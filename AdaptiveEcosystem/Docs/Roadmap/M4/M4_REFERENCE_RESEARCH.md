# M4 참고 조사 — 공식 문서와 공개 구현의 비교

> 조사일: 2026-10-05 / 프로젝트 기준: UE 5.8\
> 관련 계획: [M4_IMPLEMENTATION_PLAN.md](M4_IMPLEMENTATION_PLAN.md)\
> 확인 범위: Epic 공식 문서, 원저자 저장소 README/라이선스, 아래 명시한 공개 소스. 외부 프로젝트를 설치·빌드·벤치마크하지 않았다.

## 1. 조사 결과와 근거 수준

우리 목표인 **서버 권위 Mass 생태계 + Client별 복제 LOD + PPO + 자원/피식/사망/이주 피드백** 전체를 같은 방식으로 구현하고 규모까지 검증한 공개 프로젝트는 이번 조사에서 확인하지 못했다. 여러 프로젝트의 각 부분을 참고할 수 있다.

이 문서에서 유사도는 우리 코드/계획과의 비교 판단이다. 공개 README의 목표, 읽어 본 소스의 구현, 실제 운영 성능을 구분한다. 최신 브랜치 이름이나 문서의 엔진 버전 표시는 빌드 호환성의 증거가 아니다. UE API 링크는 갱신될 수 있으므로 설치된 5.8 소스와 대조한다.

| 참고 대상 | 가까운 부분 | 근거 | 한계 |
| --- | --- | --- | --- |
| Epic MassReplication / MassCrowd | Client Bubble, Network ID, LOD, FastArray | 공식 API + 설치된 엔진 소스 | 생태 규칙·Eco 표본 주기·terminal 상태는 프로젝트 구현 |
| Epic City Sample | 대규모 월드, Mass 표현, 근거리/원거리 시각화 | 공식 프로젝트 설명 | 자원 폐루프·우리 멀티플레이 규모의 증거가 아님 |
| arkena00/sample.mass | Replicator/Bubble/PositionYaw 연결 | 실제 Replicator/Bubble 소스 + README | 최소 예제, UE 5.6, 라이선스 파일 확인 안 됨 |
| PiotrJezyna/MassFlock | HashGrid 이웃 검색, 군집 힘, Simulation LOD | 실제 Utilities 소스 + README | UE 5.1, PPO/복제/자원 폐루프 확인 안 됨 |
| Megafunk/MassSample | Fragment/Query/Processor/Observer 학습 | README + 라이선스 | README의 복제 예제는 후속 예정으로 표시 |
| OnAllFronts-Public | 목표 공간 Grid, Mass HP/사망·지연 파괴 | 실제 Grid/Damage 소스 + README | 공개 과거 코드, 최신은 비공개; 네트워크 완성 확인 안 됨 |
| pvigier/Quadtree | 2D 공간 후보 질의 자료구조 | 실제 header + README | Mass/네트워크 연결은 제공하지 않음 |
| marl-aquarium | 포식자/피식자·FOV·MARL | README + 원논문 | 학습 환경; 대규모 UE 전송/표현을 제공하지 않음 |
| Neural MMO | 자원·생존·전투·개별 관측·학습 평가 | 원저자 환경/문서 | Python 연구 플랫폼; UE Client별 복제 LOD와 다름 |
| NetLogo Wolf Sheep Predation | 먹이·에너지·사망·개체군의 동적 피드백 | 원저자 모델 문서 | 단순 ABM, 상용 코드 복사에 NC 라이선스 고려 |

## 2. 마일스톤별 공식 자료의 적용 범위

계획서의 각 M4.0~M4.9/M4.X 절에도 공식 링크를 직접 연결했다. 여기서는 세부 책임을 대조한다.

| 단계/세부사항 | 공식 참고 | 우리에게 필요한 추가 구현 |
| --- | --- | --- |
| M4.0 World별 Entity/Fragment/Processor 조사 | [Mass Debugger](https://dev.epicgames.com/documentation/en-us/unreal-engine/mass-debugger-overview) | Stable ID 진단과 baseline 기록. UPROPERTY 없는 필드는 별도 진단 필요 |
| M4.0·9 연결/packet/bytes 측정 | [Networking Insights](https://dev.epicgames.com/documentation/unreal-engine/networking-insights-in-unreal-engine) | 검색/직렬화/전환 구간별 계측·생태 정합성 지표 |
| M4.0 Host/Client·복수 World | [PIE Multiplayer Options](https://dev.epicgames.com/documentation/unreal-engine/play-in-editor-multiplayer-options-in-unreal-engine) | TemplateID·StableAgentId·Late Join 시나리오 |
| M4.1·2 거리/수/간격/히스테리시스 | [ReplicationParameters](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassReplication/FMassReplicationParameters) | Eco Modify callback 시간 gate·연결 전체 예산 |
| M4.1·X Network ID/Client/Bubble | [ReplicationSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassReplication/UMassReplicationSubsystem) | 장기 StableAgentId와 전송 ID 분리·mapping 수명 |
| M4.1·8 FastArray Add/Change/Remove | [FastArraySerializer](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/NetCore/FFastArraySerializer), [FastArray 설명](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/NetCore/TFastArrayTypeHelper) | Dirty API를 적용하고 Array index 대신 ReplicationID 사용. death 중간 상태 보장은 별도 계약 |
| M4.3 공간 갱신/후보 검색 | [GridProcessor](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassReplication/UMassReplicationGridProcessor), [HierarchicalHashGrid2D](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/AIModule/THierarchicalHashGrid2D) | 후보 false positive의 정확한 거리 검사·분포별 benchmark |
| M4.X 3D 트리 | [TOctree2](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Core/TOctree2) | membership·이동·root 관리와 replication 후보 경계 통합 |
| M4.X·6 복제 Processor 확장 | [ReplicationProcessor](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassReplication/UMassReplicationProcessor) | 현재 엔진 export/override 검토, 기본 경로와 중복 실행 방지 |
| M4.4 Transform 수신 | [BubbleTransformHandler](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassReplication/TMassClientBubbleTransformHandle-) | 표본 시각·버퍼·teleport·stale 규칙·단일 Transform writer |
| M4.5 시각 LOD/가시성 | [RepresentationLODFragment](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassRepresentation/FMassRepresentationLODFragment), [RepresentationSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassRepresentation/UMassRepresentationSubsystem) | visual mapping·Legacy 격리·ID 유지·중복 표현 방지 |
| M4.5 Actor 생성/취소/pool | [ActorSpawnerSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassActors/UMassActorSpawnerSubsystem) | pool reset·binding generation·예산·필수 대상 우선순위 |
| M4.6 중요도·목록·카테고리 예산 | [Significance Manager](https://dev.epicgames.com/documentation/unreal-engine/significance-manager-in-unreal-engine), [Replication Graph](https://dev.epicgames.com/documentation/unreal-engine/replication-graph-in-unreal-engine) | Actor/UObject 시스템의 설계를 참고하여 Mass Client별 선정에 적용 |
| M4.7 RPC 소유권 | [RPC](https://dev.epicgames.com/documentation/unreal-engine/remote-procedure-calls-in-unreal-engine), [Owning Connection](https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-owner-and-owning-connection-in-unreal-engine) | 서버 명중/Alive/거리/sequence/rate 검증과 요청 버퍼 |
| M4.8 구조 변경/파괴 관찰 | [CommandBuffer](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/MassEntity/FMassCommandBuffer), [DestructionObserver](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassReplication/UMassReplicationEntityDestructio-) | 한 번의 death commit·피식 기록·소비/예약 정리 |
| M4.4·9 지연/손실·세션 실행 | [Network Emulation](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-network-emulation-in-unreal-engine), [Testing Guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/testing-and-debugging-networked-games-in-unreal-engine) | 조건별 오차·수명 정합성·soak 판정 |

공식 기능과 프로젝트 설계의 구분이 특히 필요한 항목은 **전송 주기 제한, Client 보간, 생태 death commit, 연결 전체 예산**이다. 문서의 클래스/설정 이름만으로 해당 기능이 우리 런타임에 이미 적용됐다고 판단하지 않는다.

## 3. 엔진 소스에서 읽을 구현 위치

`Engine/Plugins/Runtime/MassGameplay/Source/` 아래 경로는 다음과 같다.

| 소스 | 읽을 내용 | 연결 단계 |
| --- | --- | --- |
| `MassReplication/Private/MassReplicationProcessor.cpp` | Viewer별 Grid 질의, HandledEntities 합치기, 중복 제거, Client 상태 sync | M4.3·6·X |
| `MassReplication/Public/MassReplicationProcessor.h` | CalculateClientReplication Add/Modify/Off Remove/pending destruction | M4.2·8 |
| `MassReplication/Private/MassReplicationGridProcessor.cpp` | PostPhysics membership 갱신, Off tag 제외, 제거 observer | M4.3·X |
| `MassReplication/Public/MassReplicationTransformHandlers.h` | Position/Yaw dirty tolerance, Client Transform apply | M4.2·4 |
| `MassReplication/Public/MassClientBubbleHandler.h` | Bubble agent 수명/handle/삭제 정리 | M4.0·4·8 |
| `MassRepresentation/Private/MassRepresentationProcessor.cpp` | 표현 전환·Actor/인스턴스 선택 경계 | M4.5 |
| `MassRepresentation/Private/MassVisualizationLODProcessor.cpp` | 거리/가시성 LOD 계산 경계 | M4.5·6 |
| `MassActors/Public/MassActorSpawnerSubsystem.h` | pool, 요청 취소, 생성/파괴 시간 예산 API | M4.5·6 |

추가 위치: `Engine/Plugins/AI/MassCrowd/Source/MassCrowd/Private/MassCrowdReplicator.cpp`와 `Public/MassCrowdBubble.h`는 Epic의 Replicator/Bubble 타입 구성을 대조하는 자료다. MassCrowd는 엔진 라이선스 소스이며 일반 MIT 프로젝트로 분류하지 않는다. [공식 Replicator API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MassCrowd/UMassCrowdReplicator)

공간 구조 원본은 `Engine/Source/Runtime/AIModule/Public/HierarchicalHashGrid2D.h`, `Engine/Source/Runtime/Core/Public/Math/GenericOctree.h`다. 엔진 내부 구현은 버전마다 달라질 수 있으므로 소스 위치가 있다고 해서 모든 내부 API를 게임 모듈에서 link/override할 수 있다고 가정하지 않는다.

## 4. 공개 프로젝트와 우리 구조의 구체적인 비교

### 4.1 arkena00/sample.mass — 전송 흐름이 가장 직접적으로 유사

[프로젝트/README](https://github.com/arkena00/sample.mass). 확인 커밋은 `3ae73b647721b029b868c3562973686e967335b6`; `.uproject`는 UE 5.6이다.

실제 [MSReplicator.cpp](https://github.com/arkena00/sample.mass/blob/3ae73b647721b029b868c3562973686e967335b6/Source/MassSample/Mass/Replication/MSReplicator.cpp)는 PositionYaw handler, Cache/Add/Modify/Remove callback, CalculateClientReplication을 사용한다. [MSBubbleInfo.cpp](https://github.com/arkena00/sample.mass/blob/3ae73b647721b029b868c3562973686e967335b6/Source/MassSample/Mass/Replication/MSBubbleInfo.cpp)는 수신 Add/Change를 Transform handler에 전달한다.

우리 `UEcoMassReplicator`/Bubble과 같은 패턴이다. 우리 코드는 여기에 StableAgentId·종·지역과 템플릿 지연 등록 처리를 추가했다. 이 예제도 Modify에서 LOD/Time을 사용하지 않으므로 M4.2의 간격 gate를 대신하지 않는다. Client Config 사전 로딩도 README에 명시되어 있다.

**적용:** M4.0~2/4의 최소 비교 예제. 공개 트리에서 LICENSE를 확인하지 못했으므로 MIT 오픈소스로 단정하지 않고, 직접 코드 도입 전 이용 조건을 확인한다. README의 65k-byte 경고를 UE 5.8의 보편적 개체 수 상한으로 인용하지 않는다.

### 4.2 PiotrJezyna/MassFlock — 공간 이웃과 군집 조향이 유사

[프로젝트/README](https://github.com/PiotrJezyna/MassFlock). MIT, UE 5.1, 확인 커밋 `fc58ee3cbc2c61060383ad7078d5df00e8f8e64b`.

읽은 [FlockUtilities.h](https://github.com/PiotrJezyna/MassFlock/blob/fc58ee3cbc2c61060383ad7078d5df00e8f8e64b/Source/MassFlock/FlockUtilities/FlockUtilities.h)는 `FNavigationObstacleHashGrid2D`에서 가까운 셀을 찾아 거리순으로 탐색하고 이웃 결과 수를 제한한다. README는 Cohesion/Alignment/Avoidance와 Simulation LOD 사용을 설명한다.

우리에게 가까운 부분은 Entity 이웃 질의와 힘 합성이다. **Navigation 이웃 Grid와 Client 복제 Grid는 소비자/반경/수명 계약이 다르므로 같은 인덱스로 자동 통합하지 않는다.** 우리 PPO는 개체별 행동 배율을 쓰며 원거리 생태 계산도 유지해야 한다.

**적용:** M4.3 공간 비교, M5 조향 참고. 원저자의 프레임/개체 수 결과를 우리 네트워크 생태계의 성능으로 확대하지 않는다. 기존 [외부 통합 전략](../../Integration/THIRD_PARTY_INTEGRATION.md)에 이미 참조 계획이 있다.

### 4.3 Megafunk/MassSample — Mass 작성 방식의 참고

[README](https://github.com/Megafunk/MassSample/blob/main/README.md), [MIT LICENSE](https://github.com/Megafunk/MassSample/blob/main/LICENSE). README는 5.7 업데이트와 일부 이전 예제의 갱신 필요를 함께 표시한다.

Fragment/Shared Fragment/Query/Processor/Subsystem traits/Observer 설명이 우리 ECS 경계와 가깝다. 다만 README의 MassReplication 절은 복제 예제를 후속 예정으로 설명하므로 완성된 M4 네트워크 참조로 평가하지 않는다.

**적용:** 역할별 query·thread access·deferred 변경을 이해하는 M4.1/8 입문 자료. UE 5.8의 API 호출은 현지 엔진 헤더와 대조한다.

### 4.4 On All Fronts 공개 코드 — 공간 대상 탐색과 사망 수명이 유사

[원저자 저장소](https://github.com/HaywireInteractive/OnAllFronts-Public). 이전 이름은 ProjectM이다. MIT 공개 코드이며 README는 최신 개발이 closed source로 전환됐다고 명시한다. 확인 커밋은 `97fcd109fc6885acbcb4e7a050302d200e7c004c`.

[MassTargetGridProcessors.cpp](https://github.com/HaywireInteractive/OnAllFronts-Public/blob/97fcd109fc6885acbcb4e7a050302d200e7c004c/Source/ProjectM/Private/MassTargetGridProcessors.cpp)는 Movement 이후 공간 membership을 갱신하고 비스레드안전 Add의 병렬화를 피한다. [MassProjectileDamageProcessor.cpp](https://github.com/HaywireInteractive/OnAllFronts-Public/blob/97fcd109fc6885acbcb4e7a050302d200e7c004c/Source/ProjectM/Private/MassProjectileDamageProcessor.cpp)는 Mass Health 변경, 사망 시 행동 tag 제거, 지연 파괴 Fragment 추가를 사용한다.

**적용:** M4.X·7·8의 공간 질의와 생명주기 참고. 우리에게는 서버 실행 조건·Alive·중복 피식 방지·지역 집계 계약을 추가해야 한다. 읽은 Processor는 All 실행 플래그이므로 Server Authority 규칙을 그대로 보장하지 않는다. README의 대규모 지향과 멀티플레이 roadmap을 공개 구현의 달성 성능으로 판단하지 않는다.

### 4.5 pvigier/Quadtree — 쿼드트리 알고리즘 자체의 참고

[프로젝트](https://github.com/pvigier/Quadtree), [원저자 설계 글](https://pvigier.github.io/2019/07/28/quadtree-collision-detection.html). MIT, C++17 header library. 코드 확인은 [include/Quadtree.h](https://github.com/pvigier/Quadtree/blob/master/include/Quadtree.h)의 Add/Remove/Query·Threshold/MaxDepth 구조를 대상으로 했다. 설계 글 본문은 이번 조사에서 열리지 않아 상세 주장 근거로 사용하지 않았다.

범위 후보 질의·분할/병합 구조를 M4.3의 비교 backend에 참고할 수 있다. 제공 코드가 그대로 우리 계획의 loose quadtree나 동시 읽기 snapshot이 되는 것은 아니다. Mass EntityHandle 수명, 이동 재등록, UE allocator/좌표·thread 경계·Client 후보 통합은 별도 구현이다. UE의 기본 HashGrid보다 빠르다는 결론은 우리 데이터 분포의 실측으로 판단한다.

### 4.6 Aquarium — 포식자/피식자 학습의 참고

[프로젝트](https://github.com/michaelkoelle/marl-aquarium), [원논문](https://arxiv.org/abs/2401.07056). MIT. PettingZoo 인터페이스, 개체별 시야/가시거리·포획·보상·선택적 번식이 우리 정책 학습 목적과 가깝다.

Unreal C++ inference, Region Food 회계, Client별 network LOD는 별도 구현이다. `prey_replication_age`의 replication은 번식 의미이며 네트워크 복제를 뜻하지 않는다.

**현재 프로젝트의 실제 상태:** `herbivore_rl/env/world.py`와 requirements는 Aquarium 확장 대신 자체 World를 선택했다고 명시한다. [선택 근거](../../../../herbivore_rl/docs/aquarium_notes.md)를 따른다. Aquarium은 학습 설계 참고이며 현재 런타임 의존성으로 표시하지 않는다. M5의 동일한 7/4 계약과 parity는 우리 환경에서 검증한다.

### 4.7 Neural MMO — 학습과 자원/생존 피드백이 유사

[환경 저장소](https://github.com/NeuralMMO/environment), [원저자 2.0 문서](https://neuralmmo.github.io/beta/_build/html/rst/landing.html), [게임 규칙](https://neuralmmo.github.io/beta/_build/html/rst/game_wiki.html). 환경 저장소는 MIT로 표시되어 있다. 연구용 virtual world의 다중 agent 자원 수집·생존·전투·학습 평가를 참고할 수 있다.

**비교 판단:** 행동이 자원/생존 결과를 바꾸는 목표는 가깝다. 구현은 Python 연구 플랫폼이며 우리 Mass Fragment/Region 집계/7차원 관측/C++ 추론/Client Bubble과 다르다. 2.0 문서는 역사적 버전 자료이고 저장소는 조사 시점 2.1 브랜치를 노출하므로 버전 간 규칙을 섞지 않는다.

**적용:** M5·M6의 자원 압력, 생존율, 정책 비교 실험 설계. MMO 명칭이나 학습 병렬화를 UE 네트워크 연결 수·Actor 표현 성능의 근거로 사용하지 않는다.

### 4.8 NetLogo Wolf Sheep Predation — 생태 안정성의 최소 참고 모델

[원저자 모델 문서](https://ccl.northwestern.edu/netlogo/models/WolfSheepPredation). 풀을 소비하는 양, 양을 먹는 늑대, 에너지 고갈 사망, 재생/번식과 개체군 변화를 설명한다.

**비교 판단:** Food→Energy→Death/Population→Food 압력의 피드백을 이해하기 좋다. 네트워크·Mass·PPO·다지역 이주의 구현 예제는 아니다. 우리 M3에서 보류한 재생·번식 기능이 이미 있는 것으로 해석하지 않는다.

**적용:** M5·M6의 멸종/진동/자원 고갈 실험 아이디어. 해당 모델 문서는 CC BY-NC-SA 3.0으로 표시되므로 MIT 라이브러리처럼 상용 코드에 복사하지 않는다. 모델 관찰과 자체 규칙 구현의 참고 자료로 사용한다.

## 5. 공식 City Sample과 큰 월드의 추가 연결

[Epic City Sample](https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration)은 Mass 기반 crowd/traffic과 World Partition을 연결한다. 공식 설명의 근거리 rigged 캐릭터/원거리 vertex-animated Static Mesh 구성은 M4.5의 표현 비용 분산과 유사하다. 확인 범위는 공식 설명이며 이번 조사에서 샘플 전체를 내려받아 실행하지 않았다. 일반 MIT 오픈소스가 아닌 Epic sample이다.

큰 월드에서는 다음 자료를 함께 읽는다.

| 공식 자료 | 담당 문제 | 우리에게 적용할 설계 판단 |
| --- | --- | --- |
| [World Partition](https://dev.epicgames.com/documentation/unreal-engine/world-partition-in-unreal-engine) | 지형/Actor 셀의 load/unload·streaming source | Region/Bootstrap 로딩 수명과 논리 생태 수명을 분리. 셀 unload로 논리 개체를 임의 파괴하지 않음 |
| [Data Layers](https://dev.epicgames.com/documentation/unreal-engine/world-partition---data-layers-in-unreal-engine) | 월드 콘텐츠의 동적 활성화 | 시각/충돌 로딩 상태를 표현·서버 명중 검사에 반영 |
| [World Partitioned NavMesh](https://dev.epicgames.com/documentation/unreal-engine/world-partitioned-navigation-mesh) | NavMesh chunk load/unload | 향후 M5의 장거리 이동에서 서버에 필요한 nav/collision 범위 확보. 공식 문서는 Experimental 표시 |
| [HLOD](https://dev.epicgames.com/documentation/unreal-engine/world-partition---hierarchical-level-of-detail-in-unreal-engine) | 먼 정적 월드의 proxy mesh·draw call | 지형/식생 표시 비용에 적용. 동적 개체의 Mass Replication LOD는 별도 유지 |

이 표의 적용 내용은 공식 기능에서 도출한 프로젝트 설계 판단이다. World Partition streaming grid, AI 이웃 Grid, Mass replication grid는 각각 콘텐츠 로딩·행동·전송을 담당한다. 같은 셀 크기/대상을 쓰는 것으로 가정하지 않는다.

`AEcologyRegion`/Bootstrap이 unload될 때의 논리 상태 보존은 큰 월드 확장에서 명시적으로 설계해야 한다. 현재 A/B Box 검증 결과만으로 전체 월드 streaming 수명이 해결됐다고 판단하지 않는다. M4.0/9에서는 양쪽 초기 Bootstrap/EntityConfig 로딩을 확인하고, 실제 streaming 확대는 별도 게이트로 남긴다.

## 6. 적용 우선순위와 코드 도입 기준

1. **지금 M4.0~2:** 설치 엔진 Replication 소스 + 공식 API + sample.mass의 전송 패턴을 비교한다.
2. **M4.3/X:** UE HashGrid/TOctree2를 baseline으로 삼고 MassFlock/PVigier를 공간 알고리즘 참고로 사용한다.
3. **M4.4~6:** 공식 Transform handler/Representation/ActorSpawner와 City Sample 표현 방식을 참고한다.
4. **M4.7~8:** 공식 RPC 소유권/CommandBuffer/DestructionObserver에 On All Fronts의 damage/deferred lifetime 구조를 대조한다.
5. **M5~6:** 자체 herbivore World를 기준으로 Aquarium/Neural MMO/NetLogo의 생존·자원·위험 실험 아이디어를 비교한다.

공개 코드의 존재는 도입 완료가 아니다. 코드를 실제로 도입할 때 커밋·라이선스·변경점·UE 5.8 빌드·runtime 검증을 기록하고 필요한 notice를 추가한다. 이번 조사에서는 외부 소스 코드를 저장소에 복사하거나 dependency를 추가하지 않았다.
