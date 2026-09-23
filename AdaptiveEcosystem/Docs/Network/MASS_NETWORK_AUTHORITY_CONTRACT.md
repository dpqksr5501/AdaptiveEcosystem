# Mass Network Authority Contract

> 기준 엔진: **Unreal Engine 5.8**  
> 상태: **MVP Active Contract**  
> 대상: Steam Lobby/Session 기반 Listen Server 멀티플레이와 MassEntity 생태 시뮬레이션

---

## 1. 목적과 범위

이 문서는 멀티플레이 환경에서 **누가 생태 상태를 결정하고, 어떤 데이터가 Client로 전달되는지**를 정의한다.

MVP의 기본 토폴로지는 다음과 같다.

```text
Steam Lobby / Session
        ↓
Host가 Listen Server 월드 생성
        ↓
여러 Client가 지정 Gameplay Level에 참가
```

Steam은 방 검색, 참가와 네트워크 연결을 제공하지만 생태계의 권위자는 아니다. 실제 게임 상태는 Host의 Server World가 결정한다. 향후 Dedicated Server로 전환하더라도 이 권위 계약은 유지한다.

---

## 2. 권위 원칙

- Listen Server Host 또는 Dedicated Server만 권위 생태 시뮬레이션을 실행한다.
- Client는 복제된 지역 요약과 관련 범위의 Mass 개체를 읽고 표현한다.
- Client의 로컬 결과는 자원, 생존, 사망, 이주, 개체군을 확정하지 않는다.
- Subsystem은 상태 관리자이며 직접적인 Replication Transport로 사용하지 않는다.
- 플레이어 입력과 상호작용 요청은 Server에서 검증한 뒤 권위 상태에 반영한다.

---

## 3. 상태 소유권

| 상태 | 권위 소유자 | Client 역할 |
| :--- | :--- | :--- |
| `FoodAmount`, `FoodCapacity` | Server Ecology Simulation | 지역 요약 표시 |
| `PredationHistory`, `Population` | Server Ecology Simulation | 읽기 전용 표시 |
| `StableAgentId`, HP, Energy, Region | Server Mass Entity | 관련 개체의 복제 상태 표현 |
| Observation, Policy Output | Server Mass Processor | 기본적으로 복제하지 않음 |
| Transform, Velocity | Server Mass Entity | 보간 및 시각화 |
| Mesh, Animation, LOD | Client Representation | 로컬 표현 |

---

## 4. 복제 채널

MVP는 두 종류의 복제 채널을 사용한다.

1. **Region Summary**
   - 지역 자원, 위험도, 개체군과 평균 에너지를 저주기로 전달한다.
   - GameState 또는 별도 Replicated Actor가 전달한다.
2. **Mass Agent Relevancy**
   - Client 주변에서 표현할 개체만 전달한다.
   - MassReplication의 Network ID, Replication Grid, Client Bubble 구조를 사용한다.

모든 Mass Entity를 모든 Client에 복제하지 않으며, Observation과 Food Request 같은 서버 내부 중간값은 전송하지 않는다.

---

## 5. 식별자 계약

- `StableAgentId`는 생애주기와 Representation 전환을 넘는 프로젝트의 장기 논리 ID다.
- `FMassNetworkID`는 Server와 Client Mass 프록시를 연결하는 전송용 ID다.
- `FMassEntityHandle`은 각 World의 로컬 핸들이므로 네트워크나 저장 식별자로 사용하지 않는다.
- Region/Species Runtime Index는 hot path 전용이며 Client와 공유되는 영속 ID로 취급하지 않는다.

---

## 6. Client Simulation의 의미

Client Mass Entity는 권위 개체가 아니라 복제 프록시다. Client에서 허용되는 처리는 Transform 보간, 표현 LOD, 애니메이션과 디버그 시각화다. Food 소비, PPO 판단, Energy 변화, 사망과 Migration은 Server 전용이다.

---

## 7. MVP 세션 수명

- Host가 Session을 생성하고 지정 Gameplay Level을 Listen Server로 연다.
- Client는 Session 검색 또는 초대를 통해 참가한다.
- Host가 종료하면 MVP Session도 종료한다.
- Host Migration, 진행 중인 방의 Dedicated Server 승계와 영속 월드는 MVP 범위에서 제외한다.

---

## 8. 비목표

이 문서는 Steam 설정값, UI 흐름, 포트 구성, 패키징 절차, 매치메이킹 알고리즘과 Dedicated Server 배포 절차를 정의하지 않는다. 해당 내용은 구현 단계의 별도 문서에서 다룬다.

---

## 9. 관련 문서

- [PPO + Mass 생태계 아키텍처](../Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md)
- [Mass Processor 실행 순서](../Mass/MASS_PROCESSOR_ORDER.md)
- [MVP 개발 로드맵](../Roadmap/README.md)
- [UE 5.8 Online Subsystem Steam](https://dev.epicgames.com/documentation/unreal-engine/online-subsystem-steam-interface-in-unreal-engine)
- [UE 5.8 MassReplication API](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassReplication)

## 10. UE 5.8 Processing Queue 호환성

UE 5.8의 현재 MassReplication 구현을 사용하는 동안에는
`Config/DefaultEngine.ini`에서 `mass.UseProcessingQueue=0`을 유지한다.
`UMassReplicationProcessor`는 등록된 엔티티 쿼리를 각
`FMassReplicationSharedFragment`에 복사한 뒤, 클라이언트가 접속하면 그
복사본을 실행한다. 그러나 UE 5.8 Processing Queue는 원본 쿼리 주소만
추적하므로 복사본을 `Processor attempting to run a query it doesn't own`으로
거부한다.

이 설정은 새 Processing Queue 스케줄러만 비활성화한다. Mass Phase는 기존
병렬 실행기를 계속 사용한다. 엔진 쪽에서 동적 복제 쿼리를 Queue에
등록하거나 쿼리 복사 실행을 제거한 버전으로 갱신한 뒤에만 Queue를 다시
활성화한다.

## 11. Client 템플릿 등록과 Bubble 수신 순서

TemplateID는 EntityConfig 에셋의 GUID로 정해지지만, 템플릿 레지스트리는
World마다 독립적이다. 서버에서 템플릿을 생성했다고 Client에 등록되는 것은
아니다. 서버/Client가 같은 EntityConfig 에셋을 사용하고 각자의 World에서
등록해야 한다. 역할에 따른 Authority/ClientProxy Fragment 구성 차이는
같은 TemplateID 안에서 허용된다.

- `UEcoMassNetworkSubsystem.PostInitialize`: World별 Bubble 클래스를 등록한다.
- `AEcoMassNetworkBootstrap.PostInitializeComponents`: 액터 초기화 중 템플릿을
  등록한다. Client의 `BeginPlay`는 Bubble의 첫 FastArray 수신보다 늦을 수
  있으므로, `BeginPlay`는 등록 재시도와 서버 개체 생성에 사용한다.
- `FEcoMassClientBubbleHandler`: 수신한 TemplateID가 로컬 레지스트리에 있을
  때만 엔진의 Add helper를 호출한다. 없으면 FastArray 항목의 ReplicationID로
  대기 상태를 추적하고 Bubble Tick에서 재시도한다. 배열 인덱스와 수신 당시
  데이터는 저장하지 않으므로 항목 삭제 후 인덱스 변경 및 최신 위치 갱신을
  반영한다. 생성 전 Remove는 대기를 취소하고, Reset은 대기 상태를 비운다.
- 대기 항목은 아직 EntityInfo/Proxy가 없으므로 Change/Remove helper에
  전달하지 않는다. 엔진의 전체 Bubble 검증은 대기가 끝난 뒤 재개하며,
  기존 삭제 이력 정리는 대기 중에도 계속한다.

대기는 템플릿을 임의로 생성하거나 다른 TemplateID로 대체하지 않는다.
Client에 Bootstrap이 로드되지 않거나 서로 다른 EntityConfig 에셋을 사용하는
설정 오류가 지속되면 Proxy는 생성되지 않는다. 최초 대기 로그에 누락된
TemplateID를 남기고, 5초 이상 지속되면 오류 로그를 한 번 출력한다.
등록 로그에는 에셋 경로, World 경로, NetMode, TemplateID를 남긴다.
World Partition에서는 초기 개체군의 Bootstrap이 양쪽에서 로드되도록 배치한다.

에디터 수동 확인:

1. 에디터를 재시작하고 같은 맵에서 Listen Server, 2 Players로 PIE를 실행한다.
2. `Registered Eco Mass template` 로그가 서버(NetMode 2)와 Client(NetMode 3)에
   같은 TemplateID로 기록되고, 접속 시 Assertion이 없는지 확인한다.
3. 지연이 있었다면 `Deferring Eco Mass proxies` 뒤에 `Resumed`가 기록되고
   대기가 해소되는지 확인한다. `still waiting` 오류가 남으면 Bootstrap의
   Client 로딩 여부와 양쪽 EntityConfig를 확인한다.
4. 표현 Trait/Mesh가 설정된 상태에서 Client를 관심 영역 밖과 안으로 이동해
   Proxy 제거/재생성을 확인한다. PIE 종료 후 재실행하여 이전 대기 데이터가
   남지 않는지도 확인한다.
