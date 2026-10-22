# M4.1 구현 계약

기준: UE 5.8, 기존 M3 Box EntityConfig. [M4.2 주기 제한](M4_2_REPLICATION_INTERVAL.md)은 구현했다. M4.4 보간·M4.5 표현 전환·M4.6 예산 집행은 아직 구현하지 않았다.

## 설정

`Eco Network Agent`의 상속된 `Params`가 유일한 Replication LOD 설정이다. 거리 cm, 간격 초, High 시작 거리 0, 이후 경계 엄격 증가, 모든 간격 양수/유한값, 개수 0 이상, 히스테리시스 0~100%를 검증한다. Bootstrap은 잘못된 설정을 템플릿 생성 전에 거부하고 오류를 출력한다.

Trait의 `Apply M4 Experimental Preset`은 명시적으로 선택하는 실험 프리셋이다. 기존 에셋 기본값을 자동으로 변경하지 않는다. High/Medium/Low/Off 시작 거리 = 0/2000/8000/20000cm, 간격 = 0.1/0.2/0.5/1초, 개수 = 64/256/680/0, 히스테리시스 = 10%. Off 간격은 검증용 값이며 Off 개체는 표본 대신 Remove한다.

설정은 다음 PIE/템플릿 생성부터 반영한다. UE 5.8은 현재 `LODMaxCountPerViewer`로 calculator를 초기화하므로 실제 사용 필드를 확인해야 한다. LODMaxCount와 LODMaxCountPerViewer 모두 연결 전체 예산으로 해석하지 않는다.

Project Settings → Adaptive Ecosystem → M4 Connection Budget: 관련 개체 1000, Actor 64, update당 Add 64를 시작 계약으로 제공한다. Actor/Add 수는 관련 개체 예산 안이어야 한다. **이 값은 M4.6 집행 전까지 검증용 설정이며 현재 전송·Actor 수를 제한하지 않는다.** 여러 Template/Species와 Viewer를 합친 연결 전체에서 집행할 예정이다.

## Payload

| 필드 | 의미 |
| --- | --- |
| 기존 NetworkID / TemplateID | 엔진 전송 식별과 로컬 템플릿 선택 |
| StableAgentId / SpeciesId / RegionId | 영속 논리 ID / 종 / 마지막 commit 지역 |
| PositionYaw | 엔진 기존 위치와 라디안 yaw. Snapshot에서는 도 단위 Rotation으로 변환 |
| HealthByte / EnergyByte | 서버 Vitals 비율을 0~255로 반올림, Client에서 /255. 최대 양자화 오차 약 0.002 |
| LifeState | Alive Tag를 읽은 지속 상태 Alive/Dead. Client relevance Remove와 구분 |
| VisualRevision | 해당 Bubble entry의 양자화된 vitals/life 상태 변경 횟수 |
| SampleSequence | Bubble entry별 uint32 순서. Add=1, 실제 dirty 변경마다 증가 |
| ServerSampleRealTimeSeconds | 서버 GetRealTimeSeconds. WorldClock/Epoch/Step과 별개 |
| MovementDiscontinuityRevision | 서버 per-entity uint32 revision. teleport/reset 작성자가 증가시켜야 함 |

Observation/PolicyOutput/Runtime Index/EntityHandle은 전송하지 않는다. Sequence와 VisualRevision은 연결마다 다를 수 있으며 영속 ID가 아니다. 모든 실행 인스턴스는 같은 코드와 EntityConfig GUID를 사용해야 한다. 구버전 payload와의 혼합 접속은 지원하지 않는다.

정지 개체에 timestamp만 갱신해 dirty를 만들지 않는다. 위치/yaw는 기존 엔진 tolerance(1cm / 약 0.25도)를 유지한다. Region/identity, 양자화 시각 상태, reset 변경은 움직이지 않아도 dirty가 된다. Reset은 tolerance와 무관하게 현재 Transform 전체를 담는다. Add는 현재 상태를 담고 Remove는 서버 사망을 뜻하지 않는다.

M4.2는 일반 Transform을 interval gate로 제한하고 Add/Region commit/visual revision/death/reset/Off Remove를 우선 처리한다. High 승격 때 최신 Transform을 즉시 검사한다. 검사 후에는 dirty 여부와 무관하게 현재 연결의 LastUpdateTime을 갱신한다. 구현 상세와 실제 간격 측정 절차는 [M4.2 문서](M4_2_REPLICATION_INTERVAL.md)와 [수동 테스트](M4_EDITOR_TEST.md)를 따른다. 실제 PIE 간격 실측은 아직 수행하지 않았다.

## 역할별 Fragment / 작성자

| 역할 | 추가 Fragment | 작성자와 제한 |
| --- | --- | --- |
| Authority / Standalone | FEcoMovementDiscontinuityFragment | 권위 teleport/reset 작성자만 revision 증가 |
| ClientProxy | FEcoClientPresentationFragment | Bubble 수신만 Previous/Current Snapshot과 수신 real time 갱신 |
| Inspector | 양쪽 Fragment | 구성 검사 전용, 실제 World 역할 아님 |

Client에는 Vitals/Travel/Feeding/서버 이동 Fragment를 새로 추가하지 않는다. FEcoRepresentationSnapshot은 Legacy Evolution에 의존하지 않는다. Listen Host/Standalone 표현은 기존 권위 Transform을 사용하며 Client 수신 버퍼를 만들지 않는다.

현재 Client Transform 작성자는 엔진 Bubble Transform handler 하나다. 새 Fragment는 보간할 두 표본만 보관하고 Transform을 쓰지 않는다. 첫 Add/ID 변경/reset revision 변경에는 Previous=Current로 초기화한다. 같은 ID의 동일/이전 Sequence는 snapshot·Transform 모두 무시한다. uint32 차이의 signed 비교를 사용하며 연속 표본 사이 차이가 2^31 미만인 것을 전제로 한다. relevance 재진입에는 새 프록시로 상태가 초기화된다.

Client 수신 시각과 서버 real time의 차이는 편도 latency가 아니다. M4.4에서 시계 offset 또는 상대 표본 간격 기반 렌더 타임라인을 별도로 구현해야 한다. Missing Template의 지연 Add는 최신 FastArray payload로 초기화하며 pending Remove는 생성 대기를 취소한다.

Dead는 HP=0 추측이 아닌 서버 Alive Tag 제거 결과다. M4.8의 Death commit/잔류/ACK/전송 후 파괴 정책은 아직 없다. Dead와 즉시 Remove가 합쳐지면 Client에서 사망 연출을 관찰할 수 있다는 보장은 없으며, Late Join은 관련 있고 서버에 남아 있는 entry의 최신 상태만 수신한다.
