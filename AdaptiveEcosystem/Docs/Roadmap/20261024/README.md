# 2026-10-24 병합 이후 개발 명세 — 네트워크·공통 서버 통합

작성일: 2026-10-24 KST / 엔진: Unreal Engine 5.8 / 기준 브랜치: M4 / Source 기준: `883655841227696f48f91b3fb77dd5619c448227`.

문서 상태: **개발 명세 초안**. 이번 문서 작성으로 구현·팀 배정·계약 변경·빌드·PIE·성능 통과를 선언하지 않는다. 각 문서의 제안 타입·로그 이름은 아직 존재하는 API가 아니다.

**후속 개발 시작:** 사용자 F01/F04 결정과 F02 범위 지시를 반영한 [실제 구현 진행](IMPLEMENTATION_PROGRESS.md), [Steam 실행·설정 인계](MULTIPLAYER_SETUP.md)를 먼저 확인한다. 최신 Source는 `a7eb12d` 위이며 기존 출생/life·이주 구현을 재개발하지 않는다. 아래는 최초 명세 기준의 이력이다.

**2026-11-02 현재 상태:** 사용자 요청으로 멀티플레이 세션 접속의 추가 구현·수정·실환경 검증은 현재 상태에서 보류한다. 기존 구현·설정은 보존하며 Steam 검색 실패와 다중 계정 참가 미검증을 남긴다. 재개 범위와 기존 검증 이력은 [구현 진행](IMPLEMENTATION_PROGRESS.md)을 따른다.

## 1. 범위와 읽는 순서

이번 문서 묶음은 upstream/main 병합 설명에서 도출한 네트워크·공통 서버 업무 11개를 구현 가능한 단위로 구체화한다. 원준의 통합 업무를 중심으로 권신혁·조연우·World 담당의 입력과 인계 조건을 함께 명시한다. RL 신규 학습 자체나 레벨 전체 재제작은 해당 담당의 별도 작업이다.

먼저 이 안내와 01을 읽고, 맡은 업무 문서의 현재 근거·요구사항·검증을 읽는다. 팀이 정할 내용은 [확인 사항 통합 목록](99_DECISIONS_AND_CONFIRMATIONS.md)에만 답을 모은다. 기존 구현의 설명과 이번에 제안하는 변경을 혼동하지 않는다.

| 업무 ID | 개발 명세 | 핵심 산출물 | 선행 조건 |
|---|---|---|---|
| T01 | [실행 구성·권위·정책 계약](01_RUNTIME_CONFIGURATION_AND_AUTHORITY.md) | 맵·정책별 구성표, 단일 writer, 시작 진단 | Source 감사 |
| T02 | [행동·감각 표현 데이터](02_AGENT_PRESENTATION_REPLICATION.md) | 표현 필드·revision·우선순위 계약 | T01 |
| T03 | [동시 Client·재접속 정합성](03_MULTICLIENT_AUTHORITY_VALIDATION.md) | 동시 접속·늦은 참가·no-player 실행 증거 | T01, T02 |
| T04 | [보간·불량망·Actor 풀](04_INTERPOLATION_AND_ACTOR_POOL.md) | 표본 수신·reset·재사용 회귀 | T02, T03 최소 구성 |
| T05 | [날씨·시계·Client 환경](05_WORLD_WEATHER_AND_CLOCK_REPLICATION.md) | 공통 환경 snapshot과 Client 표현 | T01, F07 |
| T06 | [동적 나무·장애물](06_DYNAMIC_OBSTACLE_REPLICATION.md) | 서버 변경·Client 충돌·늦은 참가 | T01, T05의 revision 원칙 |
| T07 | [실제 출생·생성 API](07_BIRTH_AND_SPAWN_LIFECYCLE.md) | 지정 위치 출생·고유 ID·회계·복제 | T01, F11, F12 |
| T08 | [v3 지역 이주](08_V3_REGIONAL_MIGRATION.md) | 동일 ID의 이동·문맥 이전·In/Out | T01, F13, F14 |
| T09 | [환경 변화와 공간 먹이](09_ENVIRONMENTAL_SPATIAL_FOOD_ACCOUNTING.md) | 조건부 환경 자원 조정·보존식 | T05, T06, F10 |
| T10 | [플레이어 입력·서버 소음](10_PLAYER_INPUT_AND_AUTHORITATIVE_NOISE.md) | 원격 gait·서버 감지·로컬 오디오 분리 | T01, T03, F16 |
| T11 | [성능·LOD·패키지·세션](11_PERFORMANCE_LOD_AND_SESSION_DELIVERY.md) | 규모별 실측, 패키지 접속 결과 | 소규모 정합성, F04, F05, F18 |

T09는 환경 변화가 Food까지 바꿔야 할 때만 구현하는 조건부 업무다. T07·T08은 기존 기반을 확장하며, 현재 v3의 스위치만 켜는 작업이 아니다.

## 2. 병합 기준과 현재 사실

병합 `8836558`의 첫 부모는 `4bf5f81`, 받아온 upstream/main은 `a74fcac`이다. 새로 도달한 이력은 214개이고 실제 차이는 3,210개 파일이다. RL 결과 자료 2,331개, Unreal 에셋 484개, C++ 소스·헤더 146개 등이 포함된다. 커밋 수를 기능 수나 개인 기여도로 해석하지 않는다.

기존 M4의 생명주기·복제·보간·연결 예산·Actor 풀·SpeciesAI는 이번 명세에서 재사용한다. v3 Native 행동·세계 규칙·공간 먹이 연결, Social bridge·보호 은신처·표현, 외부 학습·모델 교체 도구가 추가로 통합됐다.

| 항목 | 8836558 Source에서 확인한 기준 | 후속 주의 |
|---|---|---|
| 전역 통합 정책 선택 | `eco.IntegratedPolicyVersion=1` | 맵의 `bUseV3Policy`나 실행 인자로 v3 선택 가능 |
| v3 기본 모델 | 내장 R1b 계열, 기본 NoFreeze로 R1b-F 실행 | 21관측 지원과 새 모델 채택은 별개 |
| v3 Social 이동 개입 | `SocialControl=0` | Social 처리·경보 표현 자체는 별개 |
| 보호 은신처 | v3 `ShelterSafe=1`, `ProtectedRefuges=1` | 10-16 문서의 당시 OFF/미연결 설명과 구분 |
| 장애물·돌아가기·지역 날씨 | v3 기본 ON | 실제 레벨 입력·Client 표현 연결은 따로 확인 |
| 무대 나무 실행 중 자동 생성 | `StageTrees=0` | 기존 배치 액터를 읽음 |
| 숲 잎·덤불 시야 | `Foliage=0` | 선택 실험, 자동으로 켜지 않음 |
| 환경 감시·모델 교체 | 개발 빌드 경로; EnvWatch 기본 1, AutoAdapt 기본 0 | Shipping 적용·#S1 미확정 |
| 적응 고리 최신 관문 | 쫓긴 시간 기준 크기 확정 전 실제 폴더 실행 잠금 | 단순 ON으로 production 재학습 완료 아님 |
| v3 이주·웨이브 | 통합 적용 시 명시적으로 OFF | 별도 통합 전 활성화 금지 |
| 실제 새끼 생성 | 지정 위치의 공통 출생 API 필요 | 기존 초기 Spawn·번식 표시와 구분 |

## 3. 상태 소유권과 담당 연결

| 상태·결과 | 권위 소유자 | 구현 중심 / 협업 |
|---|---|---|
| 지역 지리·지형·날씨 입력 | World | avaroki / 원준의 snapshot·transport |
| StableAgentId·Food·사망·인구 회계 | 공통 Mass·Ecology 및 coordinator | 원준 / 정책별 adapter 담당 |
| v3 관측·요청·Arbiter·Native 이동·대사 | v3 Native 경로 | 권신혁 / 공통 경계는 원준 |
| Herd·Alarm·Shelter 예약·Feedback | Social | 조연우 / 실제 이동 소비자는 정책별 담당 |
| Bubble·지역 DTO·Client 예산 | Network | 원준 / 조연우 표현 소비 |
| Mesh·AnimBP·IK·로컬 발소리 | 수동적 표현 | 조연우 / 원준 수신·풀·LOD |
| 학습·평가·Export·골든 | 외부 Python + Native 수치 검증 | 권신혁 / 서버 환경 snapshot 협업 |

담당 표는 책임 경계에 따른 제안이며 당사자의 새 업무 수락을 뜻하지 않는다. 원본 팀 레벨과 JYU 복사 맵의 소유권을 보존하고, 같은 BP·맵 파일을 동시에 수정하지 않는다.

## 4. 모든 업무가 유지할 계약

1. Server/Standalone만 생태·정책·자원·사망·이주를 확정한다. Client의 Mass 프록시는 표시용이다.
2. 같은 개체의 Transform·Velocity 최종 적분은 하나다. V1·StateTree·v3 Trait를 단순 합치지 않고 Bootstrap 혼용 가드를 유지한다.
3. v3의 Native 대사·공간 먹이와 M4 생존·섭식을 중복 적용하지 않는다. 공통 계층은 확인된 결과와 회계를 연결한다.
4. Subsystem은 로컬 서비스다. 복제는 기존 GameState·Mass Bubble 또는 명시적인 replicated Actor/component를 쓴다.
5. 장기 식별은 StableAgentId/RegionId/SpeciesId다. EntityHandle·runtime index·Actor 주소를 네트워크 식별자로 쓰지 않는다.
6. Policy Raw Request와 Social 신호·실행 결과를 구분한다. 공유 가중치와 개체별 관측·행동 출력을 유지하고, 가변 정책 출력을 Shared Fragment에 옮기지 않는다. 문서 작성만으로 Root V1 계약이나 Social 예외를 승인하지 않는다.
7. relevance Remove·Actor 풀 반환·Client 종료는 서버 사망이 아니다. 초기 spawn도 현행 누적 Births에 포함되므로 비교식의 기준을 명시한다.
8. UObject·Nav·Mass 구조 변경·자원 commit은 정해진 Game Thread 안전 경계에서 처리한다. worker에 fragment view·UObject 수명을 넘기지 않는다.
9. 런타임 Python 추론을 추가하지 않는다. 외부 학습과 서버 Native 추론을 유지한다.
10. 재시도 가능한 새 요청은 epoch·ID·revision으로 중복과 과거 결과를 거부한다. 구체 필드는 각 업무의 제안 계약을 따른다.

## 5. 단계와 의존 관계

- G0 구성: T01, F01~F03을 확인한다. 미확정 동안 Source 기본값을 유지하는 읽기 감사·진단은 진행할 수 있다.
- G1 소규모 복제: T02~T04·T10으로 동시 Client, 정지 상태 변경, 재진입·풀 회귀를 확인한다.
- G2 환경: T05, 선택한 동적 환경이 있으면 T06, Food도 바꾸면 T09를 연결한다.
- G3 생명주기: T07과 T08을 각각 독립 검증한 뒤 환경·Social과 결합한다. 두 작업이 서로 완료돼야만 시작할 필요는 없다.
- G4 납품: T11의 계측 기준선은 G1부터 수집하고, 규모·패키지·Steam 최종 게이트는 기능 정합성 뒤 통과시킨다.

작업별 C++ 변경은 직접 UBT로 검증하되, 빌드 성공·headless 실행·GUI PIE·실제 다중 접속·성능 결과를 별도 기록한다.

## 6. 공통 검증·기록 형식

문서 작성 시 수행한 것은 Source·계약·링크·diff 확인뿐이다. 아래는 미래 구현의 검증 명세다.

각 실행은 RunId, commit, 변경 목록, UE 버전, 맵, backend, NetMode, 빌드 종류, 옵션, seed, 개체/Client 수, 장비, 실시간/생태시각 기준을 기록한다. 결과는 Pass/Fail/NotRun/Blocked와 실제 근거 경로를 남긴다. 기존 기록을 새 맵·새 commit의 통과로 복사하지 않는다.

네트워크 진단의 공통 상관 키는 `RunId / WorldEpoch / CompletedStep / RegionId / SpeciesId / StableAgentId / ConnectionId`를 권장한다. 모든 필드가 현재 wire payload에 있다는 뜻은 아니며 서버·Client 로그를 연결하는 진단 메타데이터다. 네트워크 지연은 서버·Client 시계 차이를 교정해 재고, 서로 다른 PC의 로컬 시각을 그대로 빼지 않는다.

불변 조건:

```text
기간 Population 변화 = Births - Deaths + MigrationIn - MigrationOut
세계 전체 MigrationIn 합 = MigrationOut 합
다음 Food = 이전 Food + 재생 + 공급 - 소비 - 손실
Client authoritative logical owned / policy step = 0
Actor active + hidden pool <= 설정 상한
```

각 문서의 시나리오 표는 구현 후 실행할 회귀 목록이다. 계약·수치 코드에는 의미 있는 자동화/골든을 사용하고, 표현·패키지·실제 접속에는 수동 실행·계측을 병행한다. 과거 특정 M4 작업의 자동화 생략 요청을 모든 후속 작업의 영구 규칙으로 확대하지 않는다.

C++/빌드 입력 변경 후 Root 규칙에 따라 `UnrealBuildTool.exe`로 `AdaptiveEcosystemEditor Win64 Development`를 직접 실행하고 완료를 기다린다. UBT/dotnet/Editor/Live Coding/MSBuild/ShaderCompileWorker 실행 중에는 새 빌드를 시작하거나 기존 실행을 중단하지 않는다. 필요한 엔진 캐시 쓰기 권한을 갖춘 실행 환경을 사용한다.

## 7. 기존 문서와 충돌 처리

Root의 [AGENTS.md](../../../../AGENTS.md)를 불변 원칙으로 적용한다. Source는 현재 동작의 근거이며, 계약 충돌을 조용히 정당화하는 근거가 아니다. 10-16 JYU 문서는 당시 구현·시험, 10-22 팀 요청과 현재 스위치는 이후 기본 동작을 설명한다.

특히 v3 Social 기본 OFF, 보호 은신처의 후속 Python/C++ 비교, 기본 모델 유지와 모델 로더 존재를 분리한다. [기존 Production Integration](../ProductionIntegration/README.md)은 10-21의 PR 병합 전 계획을 보존한다. 이 폴더는 8836558 통합 후 상세 명세이며 과거 검증 기록을 대체하지 않는다.

## 8. 공통 근거

- [M4 실행 계약](../../Integration/M4_RUNTIME_INTEGRATION_CONTRACT.md), [구현·검증 범위](../../Integration/M4_IMPLEMENTATION_PROGRESS.md)
- [Network 권위 계약](../../Network/MASS_NETWORK_AUTHORITY_CONTRACT.md), [Mass 실행 순서](../../Mass/MASS_PROCESSOR_ORDER.md)
- [v3 계약](../../RL_Policy/POLICY_CONTRACT_V3.md), [팀 요청](../../RL_Policy/TEAM_REQUESTS_V3.md), [실시간 적응 계약](../../RL_Policy/LIVE_ADAPT_SPEC.md)
- [JYU v3 통합](../../조연우/JYU_M4_V3_INTEGRATION.md), [Social 인계](../../조연우/JYU_V3_SOCIAL_HANDOFF.md), [보호 은신처](../../조연우/JYU_REFUGE_SAFETY_20261016.md)
