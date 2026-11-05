# T11. 규모별 성능·Simulation LOD·패키지·세션 납품

상태: 실측·최종 실행 게이트 명세 / 기준: `8836558` / 책임 제안: 원준 계측·복제·세션, 전 담당 기능 회귀.

선행: T01~T04 소규모 정합성. T05~T10은 최종 포함 기능만 결합한다. 확인: [F04·F05·F08·F18](99_DECISIONS_AND_CONFIRMATIONS.md). 이 문서는 Dedicated 운영 배포·Host Migration을 자동으로 범위에 넣지 않는다.

## 1. 목적·현재 근거

코드에 개체 수 상한·LOD·Actor 풀이 있다는 사실을 실제 처리 성능과 구분한다. 목표 장비·개체 수·연결 수에서 권위 생태와 Client 표현이 유지되는지 측정하고, 에디터 밖 실제 접속 경로까지 확인한다.

현재 FEcoConnectionBudgetSettings의 코드 기본은 MaxRelevantAgents=1000, MaxActorRepresentations=64, MaxAddsPerUpdate=64다. 실제 실행 설정을 manifest로 확인한다. v3 세계 상한 512는 검증된 처리량이 아니다.

기존 M4에는 trace·연결 gate·Actor 풀·정책 LOD·worker opt-in이 있지만 과거 문서에 대규모 CPU/packet·일부 옵션 실측 미완료가 남아 있다. V1 정책 스케줄링 개선을 v3 Native에 동일 적용됐다고 주장하지 않는다.

## 2. 검증 단계

| 단계 | 입력 제안 | 완료 판단 |
|---|---|---|
| PF-A 기준선 | 32개체·최종 backend·서버+Client | 기능/계측 정상 |
| PF-B 규모 | 총 32→128→256→512 | 각 단계 비용·보존식·부하 기록 |
| PF-C 연결 | Dedicated A/B, Listen Host+A/B | 연결별 독립 예산·Host 비용 |
| PF-D burst | 동시 relevance 진입·출생·나무 변화 | frame/packet spike·queue 지연 |
| PF-E soak | 고정/변화 시나리오 장시간 | 메모리·pool·pending/lease 누수 |
| PF-F package | cook·패키지 직접 연결 | 참조·template·종료 수명 |
| PF-G session | Steam 생성/검색/참가/종료 | 실제 다른 참가자의 최종 레벨 도달 |

개체 수는 세계 전체 합이다. v3 지역별 사슴 설정·늑대 수·훈련 밀도·하드 상한에 걸리면 맵/수량 구성을 명시하고 지원 범위 안에서 측정한다. 512를 넘기기 위해 상한을 임의로 제거하지 않는다.

## 3. 먼저 확정할 제품 목표

F05에서 서버/Client 장비, UE/build, 렌더 해상도·품질, 목표 Client FPS·서버 처리 budget, 최종 개체·지역·Client 수, 허용 RTT/loss·상태 전달 지연을 정한다. F18에서 최종 기능 묶음·최소 규모·soak 시간을 정한다.

목표가 없을 때도 기준선 수집은 가능하다. 다만 'CPU가 낮았다'거나 설정 상한을 지켰다는 이유로 성능 Pass를 선언하지 않는다. 문서의 초기 시험 수치는 제품 SLA가 아니다.

## 4. 수집할 지표

| 계층 | 필수 지표 |
|---|---|
| 서버 simulation | Native/Policy/Social/감각/충돌/원장/summary별 ms, due/debt·step 지연 |
| 서버 replication | 연결별 relevant/Add/Remove/dirty/priority/gated, 실제 bytes/s·packet 간격 |
| Client | Proxy/Actor active/hidden pool, 생성·재사용, Anim/IK/audio/frame ms |
| 품질 | 보간 오차·정지 프레임·중요 상태 전달 지연·late join ready 시간 |
| 안정성 | peak/current 메모리·pending queue·lease·Actor 잔류·오류 수 |
| 정합성 | Population/Food 보존, 고유 ID, Client 논리 0 |

Unreal/Network Insights 등 실제 사용한 도구·capture 옵션을 기록한다. 서버 dirty 카운트는 전송 packet 수가 아니다. FPS 평균과 함께 frame time p50/p95/p99·최댓값을 기록하고 warm-up/정상/burst 구간을 분리한다. cross-PC 지연은 시계 교정과 event correlation 방법을 남긴다.

## 5. 연결 예산·relevance

모든 종·Template 합산의 연결 전체 cap을 검사한다. 초기 Add 폭주와 steady-state 변경을 분리한다. 현재 관련 개체 유지·초과 신규 후보 보류 정책이 가까운 중요 개체를 너무 늦게 들이는지 측정한다.

가까운 위험·상호작용 대상을 우선해야 한다면 기준·동점·eviction/유지 시간·hysteresis를 정한 뒤 구현한다. 단순 cap 증가를 병목 해결로 삼지 않는다. Local Host에도 표현 예산을 적용한다.

## 6. Simulation LOD·병렬화

표현 Off여도 Food·생존·포식 결과·예약 lease와 인구 회계는 진행돼야 한다. 감각/정책 빈도 절감은 gameplay 결과를 바꿀 수 있으므로 baseline과 비교한다.

기존 UpdateSimulationLOD는 V1 policy fragment와 phase를 읽는 경로다. Native v3의 fixed step·Arbiter·세계 규칙을 같은 옵션으로 느리게 만들지 않는다. v3 LOD는 별도 계약·Python 평가·오차 측정이 필요하다.

병목을 측정한 뒤 후보 공간 검색·중복 순회·표현 비용을 개선한다. worker에는 순수 수치 snapshot만 보내고 UObject·Nav·구조 변경·원장 commit은 안전 GT 경계에 둔다. parallel 옵션을 켰다는 이유로 최적화 완료로 처리하지 않는다.

## 7. 패키지·에셋·개발 전용 기능

Editor 빌드 성공, cook 성공, packaged 실행, 실제 멀티플레이를 별도 게이트로 기록한다. canonical transient Config가 참조하는 BP·AnimBP·프로필·오디오·날씨·맵이 cook되는지 실제 로드로 확인한다. 누락을 Editor 캐시로 가리지 않는다.

F08에서 Development 시연/Shipping 납품과 EnvWatch·모델 loader·AutoAdapt 범위를 확정한다. 현재 개발 전용 코드를 Shipping에서 자동 제공한다고 표기하지 않는다. Native 공통 헤더를 변경하면 엔진 없는 EcoV3Eval도 재빌드·해당 골든/파리티를 확인한다.

같은 빌드·데이터 계약으로 접속하는 것을 우선한다. 상이한 프로토콜/enum/맵 버전은 접속 초기에 판별하는 메타데이터와 실패 안내를 설계하고, 기존 Session metadata와 중복하지 않는다. 모델 가중치 전체를 Client로 보낼 이유는 없다.

## 8. Steam·세션 업무

현재 읽은 C++/설정에서는 Create/Find/Join Steam Session의 완료 증거를 확인하지 못했다. Blueprint/plugin 구현을 먼저 조사하고 있으면 재사용한다. 없으면 [기존 M1](../M1/M1_STEAM_SESSION_FOUNDATION.md) 범위로 구현한다.

| 흐름 | 명세 |
|---|---|
| Host 생성 | 세션/인원/빌드·맵 메타데이터 확정, Listen gameplay level 열기 |
| 검색·초대 | 세션 목록·실패/취소 상태, 중복 요청 방지 |
| 참가 | resolve→travel→GameState/템플릿 ready→현재 환경·개체 수신 |
| 늦은 참가 | 초기 spawn 재실행 없이 현재 world에 합류 |
| 종료·재시도 | 연결/검색/참가 callback 수명 정리, 재생성 가능 |
| Host 종료 | MVP 세션 종료·Client 이탈 처리 |

PIE 한 PC 직접 주소 접속은 Steam 최종 검증이 아니다. 서로 다른 참가 환경에서 실제 세션 탐색·합류·인원 제한·Host 종료를 확인한다. F04에 따라 Steam이 최종 범위가 아니면 해당 PF-G를 Deferred로 명시한다. Dedicated 접속 검증이 있어도 운영 배포/Host 승계 완료로 쓰지 않는다.

## 9. 최종 회귀 시나리오

| ID | 상황 | 기대 결과 |
|---|---|---|
| PF01 | 규모별 고정 seed·동일 품질 | 재현 가능한 성능 표와 보존식 |
| PF02 | A/B 동시 다른/같은 지역 | 연결별 cap·interval 독립 |
| PF03 | 전체 관심 영역 동시 진입 | Add/Actor cap 유지, queue 수렴 |
| PF04 | off/no-player·soak | 논리 계속, 메모리·lease 잔류 관리 |
| PF05 | Worker/LOD ON/OFF | 해당 backend 계약과 결과 차이 기록 |
| PF06 | 새 PC·package 실행 | 모든 필수 에셋·template 로드 |
| PF07 | Host 생성→A/B 참가→재접속 | 같은 서버 world·현재 요약 |
| PF08 | 빌드 불일치·가득 찬 방·접속 실패 | 명시 거부·상태 복구 |
| PF09 | Host 종료·새 세션 재생성 | 과거 callback·binding·world 상태 잔류 없음 |
| PF10 | 출생·이주·환경 변경 결합 | 포함한 기능별 receipt·복제·성능 정상 |

## 10. 최종 산출물·완료 조건

기준선/개선 후 비교표, Insights capture, 서버·각 Client 로그, package/cook 로그, 세션 접속 타임라인, 미통과·미실행 목록을 남긴다. 성능 표는 장비·commit·맵·backend·옵션·개체/연결 수·기간을 포함한다.

F18의 필수 기능·규모·토폴로지에서 F05 목표와 모든 불변 조건을 통과해야 최종 완료다. 정책 학습의 개선 입증은 권신혁 평가의 별도 결과이며 네트워크 FPS로 대체하지 않는다.

## 11. Source·계약 근거

- [연결 예산](../../../Source/AdaptiveEcosystem/Network/Mass/EcoMassNetworkSettings.h), [runtime 설정](../../../Source/AdaptiveEcosystem/Core/EcoRuntimeSettings.h)
- [V1 scheduling/LOD](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureScheduling.cpp), [Actor 예산](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePresentation.cpp)
- [Build 모듈](../../../Source/AdaptiveEcosystem/AdaptiveEcosystem.Build.cs), [프로젝트](../../../AdaptiveEcosystem.uproject), [엔진 설정](../../../Config/DefaultEngine.ini)
- [기존 실측 계획](../../Integration/P2_PROFILING_AND_BASELINE.md), [LOD 계획](../../Integration/P6_SIMULATION_LOD_AND_SCALE_VALIDATION.md)
- [Network 계약](../../Network/MASS_NETWORK_AUTHORITY_CONTRACT.md), [개발 전용 적응 계약](../../RL_Policy/LIVE_ADAPT_SPEC.md)
