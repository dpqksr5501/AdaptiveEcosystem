# Client 표시 거리와 서버 논리 지도

2026-11-06. 작업 브랜치 `jwj-1024`, 시작 HEAD `73672683`. 이 문서의 지도는 `EcoHerdMigrationDebug`의 이주 지도/`CaptureMigration`을 말한다.

## 확인한 구조

- 지도는 서버/Standalone의 살아 있는 Native 사슴 body와 늑대 threat state에서 실제 위치를 읽는다. 동물 representation Actor의 존재, Client 카메라 거리, 표시 예산에 의존하지 않는다. 전체 종/사체를 전부 표시하는 범용 지도라는 뜻은 아니다.
- HUD는 0.25초마다 권위 snapshot을 갱신한다. 이 지도는 Client에서 비활성화되어 있으며 서버 전체 개체 위치를 Client에 새로 복제하지 않는다.
- Client는 기존 Mass Bubble relevance 안의 수신 proxy에서 보간 위치/시각 상태를 읽어 수동적 representation Actor를 표시한다. Actor가 없거나 pool에 숨겨져 있어도 서버 개체가 삭제되거나 죽는 것은 아니다.
- 기존 설정 `HostVisualDistance`는 서버의 로컬 화면/Standalone에만 적용됐다. Client에는 별도 거리 제한 없이 수신 proxy와 Actor 예산이 적용됐다.

근거: `Creature/Debug/EcoHerdMigrationDebug.cpp::Capture/Mode`, `EcoCreatureInspection.cpp::DrawHUD`, `Creature/Runtime/EcoCreaturePresentation.cpp::SyncVisuals`, `Mass/EcoMassPresentationFragments.h`.

## 에디터에서 시연

1. 레벨의 `EcoCreatureIntegrationSpawner` 또는 파생 Blueprint 인스턴스를 선택한다.
2. Details의 **Creature → Visual → Client Visual Distance**를 설정하고 레벨을 저장한 뒤 멀티플레이 PIE를 다시 시작한다. 새 기본값은 **1000cm = 10m**다. **500cm = 5m**로 줄이면 차이가 더 분명하다. 거리는 플레이어 발 위치가 아닌 **로컬 카메라부터 동물까지의 3차원 거리**다.
3. Client 창에서 멀어지면 몸체/이름표/체력 바가 함께 숨겨지고, 범위에 다시 들어오면 같은 StableAgentId의 최신 수신 상태로 재바인딩된다. 기존 보간과 Actor/Add 예산 때문에 반영에 프레임 지연이 있을 수 있다.
4. 서버/Listen Host 창의 이주 지도와 비교한다. Client의 표시가 사라져도 지도 점/논리 위치는 계속 갱신된다. Dedicated 서버는 화면이 없으므로 개발용 `CaptureMigration` 진단 자료로 비교한다.

**0은 추가 Client 거리 제한 해제**다. 네트워크 relevance와 개수 예산까지 해제하는 값은 아니다. Client 거리는 replication 송신 범위나 서버 연산량을 바꾸지 않는다. 실제 보이는 범위는 수신 relevance·이 거리·Actor 개수 예산·렌더 가림에 함께 제한된다.

Standalone/Listen Host 로컬 화면은 기존 **Host Visual Distance**를 조절한다. `Client Visual Distance`를 줄여도 서버 창의 representation은 그대로일 수 있다. 서버 지도와 같은 창에서 시연하려면 Host 값을 500cm로 줄인다. Host 값 0은 기존 동작을 유지하며 Client의 0과 의미가 다르다.

기본 10m는 이번 시연 요청에 따른 짧은 값이다. 일반 플레이에 복귀할 때 해당 레벨 인스턴스에서 원하는 값이나 0으로 저장한다. 기존 맵/Blueprint 바이너리는 수정하지 않았다.

## 구현 경계

거리 검사는 retention bias/전투 우선순위보다 먼저 수행한다. 우선 표시 대상으로 지정됐더라도 거리 밖 Actor를 유지하지 않는다. 기존 `ClearBinding`/pool/재바인딩 경로를 사용하며 논리 Mass 삭제·죽음·이주/자원 장부·Native 이동 writer·정책/가중치·Bubble payload는 변경하지 않는다. 로컬 viewer가 아직 없는 Client는 양수 제한에서 Actor를 표시하지 않는다.

## 검증

- 직접 UBT `AdaptiveEcosystemEditor Win64 Development`: 성공. 기존 StructUtils deprecation 및 XGE license 경고가 있으며 컴파일 실패는 없다.
- 실제 Dedicated 서버 + Client 1개, `/Game/JYU/Maps/LV_JYU_HerdMigration`, seed23, 사슴144/늑대0, 약24초: 서버·Client 모두 PASS 및 정상 종료. `Tools/Editor/run_client_visual_distance.ps1` / `verify_client_visual_distance.py`로 실행했다.
- Client 56표본에서 1000cm → 1cm → 1000cm → 1cm → 0 순으로 설정을 변경했다. 활성 Actor는 각각 1 → 0 → 1 → 0 → 4개이며, 표시가 사라진 두 구간 모두 대상 수신 proxy는 유지됐다. 같은 대상 ID가 두 번 재바인딩됐고 Client 권위 개체 목록은 계속 비어 있었다.
- 서버 지도90표본에서 사슴144개가 유지됐고 대상 Native 위치는 `(33866.8,26904.5,-981.3)`에서 `(40000.0,26008.7,-953.2)`cm로 변했다. Client 표시 제거가 서버 개체 정지/제거가 아님을 확인했다.
- 결과는 `Saved/ClientVisualDistanceValidation/{Build.log,Client.json,Server.json,Client.log,Server.log}`에 남겼다. NullRHI에서 실제 Actor binding/거리/pool/proxy/권위 snapshot을 검사했으며, 새 렌더 화면·PIE·2Client 동시 실행은 이번 검증에 포함하지 않았다. 기존 지도 에셋 로드 중 grass/stone 참조 경고/오류는 남아 있으며 이번 거리 변경으로 수정하지 않았다. QA Python은 개발 검증용이며 게임 런타임 추론이 아니다.
- 이 변경 전부터 있던 체력 바/플레이어 변경은 보존하며 이번 기능의 수정 범위와 구분한다.
