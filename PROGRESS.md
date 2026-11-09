# 먹이와 풀 표현 개발 진행

## 사슴 지역 순차 이주 첫 구현 (2026-11-09)

[구현·간단 테스트·남은 검증](AdaptiveEcosystem/Docs/Architecture/REGIONAL_DEER_MIGRATION_IMPLEMENTATION_20261109.md)을 먼저 읽는다. `eco.HerdMigration.Regional 1` opt-in에서 등록 순서의 개별 출발, 지역 episode·생태 지원 인원·출발 예약·잔류 하한/누적 승인 한도를 연결했다. PlanId 키와 체크포인트 v2, 지도 지역 중단 이유를 추가했다. 직접 Editor UBT 성공, 관련 자동화13개 성공/실패0. 1102 실제 관측은 Python 속성 오류 후 수정했으나 재실행 엔진 감지 및 후속 프로세스 확인 승인 거절로 완료하지 못했다. 신규 모드 실제 지형 도착·다지역 경쟁·저장 왕복·멀티는 남아 있다. 기본 Regional=0이며 아래 ‘계획만 작성’은 앞선 작업 이력이다.

## 사슴 이주 후속 재개 — 지역별 순차 승인 계획 (2026-11-09)

사용자 요청으로 [지역 생태 기반 사슴 순차 이주 개발 계획](AdaptiveEcosystem/Docs/Architecture/REGIONAL_DEER_MIGRATION_PLAN_20261109.md)을 작성했다. 다음 **사슴 이주 구현**은 지역 등록 배열 순서, 지역별 부족 episode, 예상 잔류/목적지 예약, 생태 목표 인원과 누적 출발 한도를 따른다. 최소 2마리 Herd 조건은 새 경로의 자격 조건에서 제거하고 단독 개체도 평가한다. 등록 순서·PlanId·저장/생명주기 변경이 필요하므로 가드 한 줄 삭제로 완료하지 않는다. 25% 잔류/3초당 1마리 등의 수치는 초기 검증용 제안이다. 이번 작업은 문서만 작성했고 새 코드·빌드·런타임 검증은 없다. 아래 풀 패치 S1 완료/S2 미구현 상태는 그대로이며 전체 개발 완료를 뜻하지 않는다.

## 최신 재개 — 공유 패치 첫 구현 (2026-11-08)

사용자 요청의 6단계를 명세 S0~S6 순서로 착수했다. [S0 조사·S1 구현 기록](AdaptiveEcosystem/Docs/Architecture/FOOD_PATCH_GRAZING_S0_S1_20261108.md)을 우선 읽는다. **현재 실제 소비는 기존 셀 단위이며 패치별 예약/도착 소비 완료가 아니다.** 기존 1102 4지역·미커밋 에셋/소스는 보존했다. 새 맵/Smart Objects/이동 writer를 추가하지 않았다.

| 사용자 단계 | 현재 작업 상태 |
|---|---|
| 1 동작·비용 기준선 | production writer/hook 조사, 구현 전1102 seed23/65초 CPU·컨테이너 메모리, 셀 소비 Dedicated 전송, 별도45초 위치 표본 완료. 정식180초×3seed 기준선은 남음 |
| 2 고정 위치·ID | 공통 함수/descriptor·hash·epoch ID·Native static cache·World96 trace·높이 압축 DTO·같은 anchor 렌더 첫 구현. 기본OFF, 실제1102/Client2/late join 네 지역 anchor checksum 대조 통과. 통합1~9후보 지원,25후보 snapshot·자동 지형 unload 무효화는 남음 |
| 3 패치 배분·보존 | writer 목록 확정, S2 미구현. 아직 패치별 Food/Capacity 없음 |
| 4 검색·예약·이동·도착 소비 | S3 미구현. 기존 Native 이동·소비 보존 |
| 5 표현·복제·저장·디버그 | S1 지면/ID DTO·진단 계측부터 연결. 개별 잔량/먹기 연출/HUD·체크포인트 schema는 S4/S5 미구현. S1 ON save/load는 명시 거절 |
| 6 기능·비용 비교 | 최종 식생15개 자동화 성공(경고/실패0), 직접 Editor UBT 성공,1102 S0/S1 비용·Dedicated 실제 writer/소켓 비교 완료. 정식 full grazing A/B·F01~F12·Game/패키지·장기 시험은 미완료 |

사용법: Play 전 `eco.Grass.PatchLayout 1`은 **S1 anchor만** 활성화하며 소비 동작을 바꾸지 않는다. 1102 저장 에셋의 기본값은 OFF다. 원본 증거는 `AdaptiveEcosystem/Saved/FoodPatchGrazing_20261108_*`에 보관한다. 아래 ‘명세만 완료/전체 미구현’ 문구와 과거 통계는 날짜별 이력이다.

다음 코드 작업은 S2 FoodGrid의 원자적 셀/패치 배분이다. 현재 S1 검증을 마친 뒤 writer 전체·재생/손실/공급·capacity clamp·구버전 이전·동시 소비 보존을 검증하고 S3로 간다. 완성 전 전체 grazing을 ON 하거나 패치 먹기 완료로 기록하지 않는다.

최종 결과(22:48 KST): `Saved/FoodPatchGrazing_20261108_Start/Manifest.json`의 evidence_checks_passed=true, formal_budget_qualified=false. S1 최종65초 CPU RefreshVisuals active p95=1.5782ms(이전1.5756ms, +0.165%, 단일 seed로 효과 판정하지 않음), Native static1,166,400bytes, ground DTO1,883,232bytes, local layout cache239,084bytes. Dedicated NetCompact/Client2·95초 late join·동시28.109초, 네 지역 anchor checksum 일치/근거리 누락0/Client 논리0/모든 프로세스0. ground serializer max152816bits=19102bytes, steady delta0. 이전 원시 DTO의 bunch 초과 실패는 NetS1에 보존했고 압축 후 오류0이다. 기존 cell 소비45초 별도 관측은 동기25시점/섭취184표본/실제 render anchor 거리165표본을 기록했다. body→현재 보이는 anchor 거리이며 mouth 도착 판정으로 확대하지 않는다.

재현 도구: `Tools/Editor/test_food_patch_layout.ps1`(Profile/Feeding, -PatchLayout 선택), 기존 `test_vegetation_network.ps1`의 -PatchLayout/-FoodPatchCheck/-DeerPerRegion12, `summarize_food_patch_start.py`. -FoodPatchCheck는 풀 delivery/anchor 검증이며 기존 life/카메라 순회 승인을 뜻하지 않는다. 원래 legacy gate 실패는 NetA/Relevance_LegacyGate.json에 남겼다. baseline 전송18.00/16.95kB/s와 S1 20.04/21.26kB/s는 전체 socket 평균이며 Field serializer bytes와 구분한다. 아래 과거 재개 지시보다 이 최신 단락/첫 작업을 우선한다.

이전 명세 작업(2026-11-08): [공유 풀 패치·실제 위치 섭식 개발 명세](AdaptiveEcosystem/Docs/Architecture/FOOD_PATCH_GRAZING_IMPLEMENTATION_SPEC_20261108.md)를 작성했다. Smart Objects 플러그인 없이 기존 Native/Field에 검색→접근 슬롯 예약→이동→도착 소비를 적용한다. 다중 고정 패치와 셀 장부 보존, 서버 지면/ID/epoch, 복제·LOD·저장, S0~S6 구현 순서, F01~F12 테스트, CPU/메모리/전송량 비교와 초기 제안 예산을 정했다. 당시 작업은 문서만 변경했으며 새 런타임 구현·빌드·성능 실측은 없었다.

최신 사용자 피드백(2026-11-08)은 사슴과 보이는 풀의 섭식 위치 불일치다. Source에서 4m×4m 셀 소비와 분산 ISM 후보 표현이 개별 위치로 연결되지 않은 점을 확인했다. 후속 계획 B-2에 공통 섭식 패치·도착 판정·소비 위치에 맞는 표현과 멀티 검증을 추가했다. 포만 구현에 앞서 이 위치 일치 항목을 처리한다.

후속 공식자료 조사에서 Random Streams·ISM·Networking·Smart Objects·Timing Insights를 확인했다. 여러 분산 무더기를 유지하려는 요구에는 서버의 경량 패치 배열과 공통 PatchId를 우선 제안한다. 후보 수 최대32,400개와16~32bytes 레코드의 약0.49~0.99MiB는 설계 산술 예시다. Source/기존 JSON·공식문서 감사 및 계획 갱신만 수행했으며 새 성능 측정/런타임 구현은 없다.

최신 실행(2026-11-08): 1102에 기존 `JWJ_WildlifeTest`·`JWJ_HuntingMeadow`를 유지하고 `JWJ_SouthRange`·`JWJ_WestRange`를 추가해 4지역을 저장했다. 기존 스포너가 JYU `BP_JYU_VegetationField`를 직접 사용한다. 별도 프로세스의 53초 Play에서 네 지역 표시/카메라 회전과 식생 장부를 검증했고 계획 C의 포만 구현 전 기준선을 기록했다.

최신 사용자 범위(2026-11-08): 기존 `/Game/JWJ/1102_Integration_JWJ`에서 풀 표현·사슴의 먹이 부족 이주·늑대의 증거 기반 추적 이주·포만 시 비섭식 행동을 시험하도록 후속 계획을 작성했다. [JWJ 1102 후속 개발 계획](AdaptiveEcosystem/Docs/Architecture/JWJ_1102_FOOD_MIGRATION_SATIETY_PLAN_20261108.md)을 다음 재개의 우선 문서로 사용한다. 이번 요청은 계획 문서 작성이며 새 기능/레벨 설정은 변경하지 않았다. 아래 기존 풀 구현·검증 증거는 그대로 유효하되 1102/새 행동의 검증 완료로 확대하지 않는다.

갱신일 2026-11-08 18:44 KST. 기본OFF인 기존 FastArray 직렬화 계측의 Editor 빌드와 Dedicated+Client2/late join, 네트워크 프로파일 대조가 통과했다. 연결 전체 소켓 송신 평균29.84~32.26kB/s와 VisualGrid payload 환산23.33~24.32kB/s를 분리 측정했다. nprof의16bit wrap을 실제 writer/프로토콜 bit·이벤트 순서로 검증해 과소 집계를 방지했다. 최신 base 동적 메모리는 지역별7680~10416bytes이며 전체 연결 메모리는 아니다. 이전0/회복·streaming·CPU 증거도 보존한다. 전체 GPU/복제 이력 메모리·배포 예산·HUD 승인 검수·최종 회귀/Game/패키지가 남았다. branch jwj-1024, HEAD395992ab이며 변경은 미커밋 상태다.

## 목표와 완료 조건

추가 완료 조건(모두 미완료): 1102 저장본/실행 기준선 감사, 플레이어 카메라에 따른 풀 표현 검증, 만복/단독 개체를 포함한 사슴 부족 이주, 늑대의 관측/흔적 기반 실제 지역 인계, 포만→휴식/경계/탐색→허기 재개, 기존 HUD 시나리오/기록, 해당 맵 멀티·저장·패키지 회귀. 상세 단계 A~F는 위 후속 계획을 따른다. 기존 풀 완료 조건과 합쳐 판단한다.

기존 지역 생태계의 서버 FoodGrid/M4 먹이가 풀 위치·밀도·높이·색으로 이어지고 실제 섭식·환경 손실·재성장이 기존 맵에서 보이게 한다. 기존 Field와 ISM 구성요소, spawner, 환경 공급자, Inspector HUD를 확장한다. 레벨·게임모드·플레이어 추가 없이 설정 가능한 구조로 구현한다.

- [x] 기존 맵에서 셀별 먹이 분포와 고갈/재생 외형을 확인 (Native/DTO/실제 ISM236셀0→회복·실행 캡처)
- [ ] 환경 디버그에서 지역 선택·강수·기온·수원·자동 복귀·진단 저장 확인
- [x] 표시 OFF/ON 동안 Native 진행과 풀 복귀 확인
- [x] 실제 ISM의 후보 위치 재현, 지면 충돌 재시도, 미세 잔량/0 제거·회복 확인 (표현 DTO/바닥 fixture)
- [x] 실제 생태 섭식 셀의 잔량과 표시를 같은 실행에서 대조 (기존 맵45초, Forest)
- [x] Dedicated+Client2와 late join, 지역 이탈/재진입 확인 (QA 표시 범위20000cm 조건)
- [ ] 변경분 전송과 메모리/프레임/인스턴스 예산 측정
- [x] 단일 관찰자 Editor의 Field CPU·컨테이너 메모리·후보/trace 상한 기준선 계측
- [x] 연결별 소켓 송신과 VisualGrid 실제 payload·최신 base 동적 상태 계측 및 엔진 통계 대조
- [x] 실제 Client 지형 Actor 로드/해제와 세 지역 각10회 이상 안정 방문·거리별 표시·캐시 상한 확인
- [ ] 최종 코드 상태의 직접 Editor/Game UBT, 관련 자동화와 통합 Play·멀티·패키지 실행 검증 (Editor/멀티는18:44 최신, 식생 자동화/Game/패키지는 이전 보강 기준)
- [ ] 실제 사용법과 남은 한계를 문서에 기록

계획은 AdaptiveEcosystem/Docs/Architecture/FOOD_GRASS_IMPLEMENTATION_PLAN_20261108.md, 사용법은 같은 폴더의 FOOD_GRASS_TEST_GUIDE_20261108.md를 참고한다. 문서의 계획 목표와 검증된 구현은 구분한다.

## 재실행 규칙

1. AGENTS.md, PROJECT_CONTEXT.md, 이 문서를 읽고 branch/HEAD·git status·diff·실행 중 프로세스를 확인한다.
2. 기존 수정·미추적 파일과 현재 Source를 대조하고 첫 미완료 작업부터 이어간다.
3. 작업 단위 완료 때 이 파일의 상태·파일·증거·다음 작업을 갱신한다.
4. 사용량 제한이면 재시도를 중단하고 다음 예약을 기다린다. 필요한 승인을 우회하지 않는다.
5. Unreal/UBT/dotnet/Live Coding/MSBuild/ShaderCompileWorker 실행 중 새 빌드를 시작하거나 실행을 중단하지 않는다.
6. 모든 완료 조건을 충족하면 현재 대화의 개발 heartbeat를 비활성화한다.

## 기준과 기존 사용자 작업

확인 기준 branch jwj-1024, HEAD 395992ab. 이번 개발 시작 전부터 EcoObservationV3.h, EcoThreatModel.h, EcoWorldV3.h 수정과 EcoSpatialIndexV3.h, Docs/Performance/, Tools/EcoSpatialBenchmark/ 작업이 있었다. 변경을 보존하고 관련 diff를 섞어 커밋하지 않는다.

## 구현한 기능과 변경 파일

구현 여부와 해당 기능의 검증 범위를 함께 기록한다. 모든 목표가 완료될 때까지 미완료 체크 항목을 유지한다.

| 기능 | 변경 파일 (AdaptiveEcosystem/ 기준) | 검증 |
|---|---|---|
| 공유 패치/예약/도착 소비의 개발 명세와 수치 검증 계약 (런타임 미구현) | Docs/Architecture/FOOD_PATCH_GRAZING_IMPLEMENTATION_SPEC_20261108.md, JWJ_1102_FOOD_MIGRATION_SATIETY_PLAN_20261108.md, Docs/PROJECT_CONTEXT.md, 루트 PROGRESS.md | 문서4개 UTF-8·로컬 링크67개·S0~S6/F01~F12 존재·코드 fence 확인 통과. 기존 단일 군락 제안과 재개 우선순위 충돌 정리 |
| 전체 셀의 먹이/용량 Fast Array 변경분 전송, 안정 후보 배치·증분 ISM, 거리별 표시, trace 예산, 실제 경로 기본값/호환 fallback | Source/AdaptiveEcosystem/World/EcoVegetationField.h/.cpp | 마지막 Editor/Game UBT, 실제 Play, Client2 수신 통과 |
| soil OFF에서도 food 외형 opt-in | Creature/Runtime/EcoCreatureIntegrationSpawner.h, AI/Policy/EcoPolicyV3IntegratedSubsystem.cpp | 기존 맵40초 PIE에서 세 지역 soil=false, 실제 풀과 Native 진행·장부 일치 확인 |
| 지역 수동 기후와 최신 자동값 복귀 | World/EcologyRegion.h/.cpp, AI/Policy/EcoPolicyV3IntegratedProcessors.cpp, Ecology/EcologyEnvironmentSimulation.cpp | 신규 GrassDebugClimate 자동화 성공 |
| 기후·수원·진단 저장 명령 | Debug/EcoEnvironmentDiagnostics.cpp, World/EcoVegetationField.h/.cpp | 기후·수원 실제 입력 반영/해제 통과. UI 저장 조작 직접 확인은 남음 |
| 기존 HUD의 Alt+G 패널과 Alt+1..5 지역/기후/복귀/저장, 조준 셀 진단 | Creature/Debug/EcoCreatureInspection.h/.cpp | 마지막 Editor/Game UBT 성공. 키보드 조작 화면 검수는 남음 |
| 기존 runtime 감사 도구의 Dry/Rain/Auto·표시·수원 검사 | Tools/Editor/audit_vegetation_runtime.py | Retry/Material/VisualToggle/WaterToggle 모두 FINISHED |
| 옛 은신처 메시 참조를 현재 Content 경로로 수정 | AI/Social/Shelter/EcoRefugeHabitat.cpp | RefugeVisualComposition 자동화 통과 |
| 기후 override·거절·이웃 격리·최신 자동값 복귀 회귀 | AI/Policy/Tests/EcoVegetationTest.cpp | GrassDebugClimate 성공 |
| 먹이·용량의16bit 표현 경계와 고갈/양의 미세 잔량 표시 조건 | World/EcoVegetationField.h/.cpp, AI/Policy/Tests/EcoVegetationTest.cpp | GrassAmountEncoding 및 기존 식생8개 모두 성공 |
| 후보 지면 재검사 공정성·anchor 변경 시 이전 표현 정리 | World/EcoVegetationField.h/.cpp, AI/Policy/Tests/EcoVegetationTest.cpp | GrassGroundRefreshFairness 포함 식생9개·기존 맵40초 표시 회귀 통과 |
| 실제 ISM 고갈/회복·거리 이탈/재진입·지면 재시도·안정 ID/위치 | World/EcoVegetationField.h/.cpp, AI/Policy/Tests/EcoVegetationTest.cpp | GrassVisualLifecycle 포함 식생10개 성공, 실제 엔진 지면 충돌/ISM 사용 |
| 실제 섭식 셀의 Native 소스·전송 DTO·ISM 계측 | World/EcoVegetationField.h/.cpp, Tools/Editor/audit_vegetation_runtime.py | 기존 Ecosystem45초 FINISHED. 동기13976셀 표본 일치, 섭식1006관측, ISM913관측/194고유 셀 |
| Field CPU CSV·실제 컨테이너 할당량·QA 프로파일 모드/요약 | World/EcoVegetationField.cpp, Tools/Editor/audit_vegetation_runtime.py, summarize_vegetation_evidence.py | ProfileComplete65초 FINISHED/CSV flush/프로세스0/요약 passed=true. 6583frame, 후보/trace 상한·M4 차이0 |
| 실제 Client streaming·장기 방문·near/coarse·캐시 상한 계측 | World/EcoVegetationField.cpp, Tools/Editor/audit_vegetation_client.py, test_vegetation_network.ps1, validate_vegetation_relevance.py | Travel 종합 passed=true. 안정 방문11/10/11, proxy 추가316/제거321, 모든 방문의 near 복귀·Client 권위0·Native0 |
| 실제0 고갈/같은 셀 회복 기후 QA | Tools/Editor/audit_vegetation_runtime.py | Depletion120초 FINISHED/종료0. 실제 양수 ISM456셀 중236셀0/인스턴스0→같은236셀 양수/ISM 복귀, 동기84시점·장부 오차0·기후 격리/Auto 통과 |
| 연결별 송신/실제 serializer·최신 base 메모리 계측 | World/EcoVegetationField.h/.cpp, Tools/Editor/test_vegetation_network.ps1, audit_vegetation_runtime.py, summarize_vegetation_evidence.py | NetAudit 종합/요약 passed=true. 2연결245개 serializer 이벤트의 순서·uint16 나머지 일치, 실제 전체 payload26,477,051bits, EOS 완성 |
| 기존 풀 재질·텍스처·함수의 이동 후 경로 연결 | Config/DefaultEngine.ini | 정확한 package redirect16개 대상 존재 확인, Editor/패키지 캡처 확인 |
| 현재 로컬 접속 조건과 선택적 QA 표시 범위 적용 | Tools/Editor/test_vegetation_network.ps1, audit_vegetation_client.py | Client2/late join 종합 검사 통과 |
| 패키지 결과·아카이브 폴더 선택 | Tools/Editor/package_ecosystem.ps1, test_ecosystem_package.ps1 | 별도 Saved 폴더의 패키지 생성/90초 실행 통과 |
| 구현 계획·사용법·공통 진입 링크 | Docs/Architecture/FOOD_GRASS_*.md, Docs/PROJECT_CONTEXT.md | 현재 결과와 남은 작업 반영 |
| 작업 재개 및 완료 조건 추적 | 저장소 루트 PROGRESS.md | 실제 Git 상태·Source·검증 로그 대조, 작업 단위별 갱신 규칙 기록 |

Source 파일 표는 Source/AdaptiveEcosystem/ 아래 축약 경로도 포함한다.

## 실행한 테스트와 결과

현재 결과를 아래 표로 요약한다. 증거 경로는 AdaptiveEcosystem/Saved/ 기준이다. 과거 실패와 수정 과정은 마지막 재개 기록에 보존한다.

| 검증 | 결과 | 증거 |
|---|---|---|
| 공유 패치 명세 정적 검증 | 문서4개 UTF-8 정상, 로컬 링크67개 누락0, S0~S6/F01~F12 포함, fence 균형, PROJECT_CONTEXT git diff --check 통과. 새 엔진/성능 시험 없음 | 이번 문서 검증 도구 출력 및 명세 §7~10 |
| 직접 Editor UBT | NetAudit 기본OFF 진단·동일 serializer 반환 경로 연결 후 성공, 10 action/29.34초 | FoodGrass_20261108_NetAudit/Build.log |
| 연결별 전송/serializer 대조·Client2/late join | 종합/요약 passed=true, 모든 프로세스0. nprof147.675초/4369frame, 소켓3,414,359/940,211bytes, 실제 VisualGrid20,596,961/5,880,090bits. 190/55이벤트 모두16bit counter wrap 확인·순서 대조 성공, 초기/델타 실제 최대121341bits. 근거리136/29표본 누락0·late join157/159·M4 오차0 | FoodGrass_20261108_NetAudit/NetworkProfileSummary.json, Relevance.json, Server.log, NetworkProcesses.json 및 Saved/Profiling의PID35048 nprof |
| 실제 먹이0 고갈·ISM 제거·같은 셀 회복 | 기존 Ecosystem120초 FINISHED/프로세스0. Dry0/50℃48초→Rain.5/20℃48초→Auto24초.456셀 양수 표시 관찰 중236셀의 정확한0/제거와 같은236셀 양수/ISM 복귀, Native/DTO 동기84시점·M4 오차0. 캡처3개 중 Dry/Rain 직접 확인 | FoodGrass_20261108_Depletion/PIE_Depletion.json, PIE_Runtime.json, PIE.log, VegetationPIE_0/1.png |
| 실제 streaming·반복 방문·Client2/late join | 종합 passed=true/모든 프로세스0. ClientA380.5초/381표본, 안정 방문 Forest11/Barren10/Highland11, proxy 추가316/제거321, 후보 상한·near/coarse·각 방문의 streaming 후 near 복귀 통과. 근거리509/30표본 누락0, 동시28.344초, late join ID159 scale 일치, 서버212표본 M4 차이0 | FoodGrass_20261108_Travel/Relevance.json, ClientA_Client.json, Server_Runtime.json, NetworkProcesses.json |
| 로컬 Editor 성능/메모리 기준선 | 65초 Play FINISHED, CSV59.985초/6583frame 완성·요약 passed=true. Refresh active p95/max1.3486/2.0671ms, 후보trace max117≤합산288, 후보/인스턴스 상한·장부 일치 | FoodGrass_20261108_ProfileComplete/PIE.log, PIE_Runtime.json, ProfileSummary.json 및 Profiling/CSV의 동일 실행 파일 |
| 실제 Native 섭식→DTO→ISM 대조 | 기존 맵45초 FINISHED/프로세스0. 동기30시점/13976셀 코드 일치, 섭식1006관측, ISM913관측/194고유 셀. 셀44 먹이0.398→0.085에 풀4→1, M4 차이0 | FoodGrass_20261108_FeedingRetry/PIE_Feeding.json 및 PIE_Runtime.json |
| 식생 자동화8개 | 정량화 보강 후 성공8, 경고/실패/미실행0 | FoodGrass_20261108_AmountEncoding/Automation/index.json |
| 식생 자동화9개 및 Play | 공정성 보강 후 성공9, 경고/실패/미실행0. 기존 맵40초 표시 숨김·복귀 FINISHED | FoodGrass_20261108_GroundFairness/Automation/index.json 및 PIE_Runtime.json |
| 식생 자동화10개 | 실제 ISM lifecycle 추가 후 성공10, 경고/실패/미실행0 | FoodGrass_20261108_VisualLifecycle/Automation/index.json |
| 전체 자동화235개 | 성공233 + 경고 포함 성공2, 실패0/미실행0. GrassDebugClimate/RefugeVisualComposition 포함 | FoodGrass_20261108_Retry/Automation/index.json |
| 지역 기후 Dry/Rain/Auto·격리·FoodGrid/M4 수지 | 65초 시험 FINISHED | FoodGrass_20261108_Retry/PIE_Runtime.json |
| 재질 경로 복구·실제 화면 | 65초 시험 FINISHED, 캡처 직접 확인 | FoodGrass_20261108_Material/PIE_Runtime.json 및 VegetationPIE_0.png |
| 표시 OFF/ON | 숨김 중 Native 진행·복구 후 풀 표시 FINISHED | FoodGrass_20261108_VisualToggle/PIE_Runtime.json |
| soil OFF+풀 표시 ON 및 OFF/ON 전환 | 기존 맵40초 FINISHED, 오류0. 세 지역 soil=false, soil 성장/손실0, Native 진행·장부 일치·풀 복귀 확인 | FoodGrass_20261108_SoilOff/PIE_Runtime.json |
| 실제 수원 OFF/ON | 공급 셀0→9, FINISHED | FoodGrass_20261108_WaterToggle/PIE_Runtime.json |
| Dedicated+Client2/late join/지역 전환 | 종합 passed=true, 근거리99/38표본 누락0, 동시28.313초. QA 표시 거리20000cm | FoodGrass_20261108_NetworkWideView/Relevance.json |
| 직접 Game UBT | AdaptiveEcosystem Win64 Development 성공, 64.92초 | FoodGrass_20261108_Package/GameBuild.log |
| cook/stage/pak/archive | BUILD SUCCESSFUL, ExitCode0 | FoodGrass_20261108_Package/Package.log |
| Development 패키지90초 실행 | 정상 종료·생태 진행·풀 화면 확인 | FoodGrass_20261108_Package/PackagedSmoke.log |
| 문서·변경 형식 | git diff --check 오류0, 문서 링크 확인 | 이번 문서 갱신 시 재확인 |

## 진행 중인 작업

- 최신 공유 패치 작업: S0 조사/짧은 비용 기준선과 S1 첫 구현/로컬·멀티 검증 완료. 다음 코드는 S2 셀/패치 거래이며, 정식3seed 성능·25후보 네트워크/자동 지형 무효화와 S2~S6 완료 검증은 남아 있다.
- 경계값·배치 재현·명시적 성능 예산 등 잔여 완료 조건의 보완
- 기존 Inspector HUD의 실제 키보드 조작 화면 검수와 입력 이력/진행 안내 보완
- 현재 대화의 30분 heartbeat를 통해 미완료 작업 이어가기

## 미완료 작업

- 공유 패치 S2~S6의 배분/예약/도착 소비·잔량 복제·저장·F01~F12/정식 성능 검증. S1 고정 배치·권위 지면/1cm 높이 복제는 첫 검증을 마쳤고1~9후보만 opt-in한다. 자동 지형 unload 무효화/25후보 전체 snapshot은 아직 미지원이다.
- 실제0 고갈/같은 셀 회복은 명시적 기후 디버그 조건에서 완료. 기존 은신처/장식 foliage와 먹이 Field 외형을 사용자가 구별하는 조작·표시 검수는 남음
- Client Landscape Actor streaming·반복 방문·near/coarse·후보 캐시 상한은 완료. 모든 지형 종류/충돌 지연·GPU mesh LOD까지의 범용 검증으로 확대하지 않음
- 완료된 Client2/late join 검증을 기반으로 셀 변경분 정량화·오래된 데이터·재동기화 경계 검증 보강
- 로컬 CPU/컨테이너·소켓 송신/VisualGrid payload·연결별 최신 base 동적 상태 기준선은 완료. IP/UDP/link packet capture, ACK/history/채널 포함 전체 복제 메모리, ISM CPU/render/GPU 전체 비용·배포 목표 예산과 저장/재시작 회귀는 남음
- 환경 시험 자동 진행/판정·입력 이력 기록 등 계획 대비 빠진 UI/진단 항목 확인
- 기존 Field Actor 단위 relevance는 지역 전체를 전송한다. 공간 chunk별 관심 구역 전송은 현재 미구현이며 검증/범위 판단 필요

## 다음 실행의 첫 작업

**최신 첫 코드 작업은 B-2 명세 S2다.** [S0/S1 기록](AdaptiveEcosystem/Docs/Architecture/FOOD_PATCH_GRAZING_S0_S1_20261108.md)의 writer 표와 최신 Source/diff를 확인하고 FFoodGrid의 셀/패치 Food·Capacity를 동일 거래로 commit한다. Build/ApplyShelterFood/Regrow/C4/개발 가뭄/저장 경로를 빠뜨리지 않는다. S1 ON은 아직 셀 소비이며 신규 patch 배분과 lease/arrival가 갖춰지기 전1102 에셋 기본값을 켜지 않는다. 단일 군락/4지역 재생성은 하지 않는다. 정식 비용 예산은 미판정이다.

**B-2 완료 후:** 계획 C의 실제 포만 규칙으로 이어간다. 1102의 높은 E·가득 찬 비축 상태의 섭취 표본을 기준으로 기존 Native 실행 훅에 설정 가능한 섭식 시작/종료와 비섭식 행동을 연결한다. 늑대는 포만 타이머와 영양량을 별도로 관측하는 시험부터 한다. B의 실제 Client 관심 범위·성능과 D~F의 이주·통합 검증은 남아 있다.

**기존 A/B 기준선 유지:** 1102 4지역 저장본/실행 감사 결과를 재사용하고 authoring 스크립트를 그대로 재실행하지 않는다. 카메라 거리 표시와 방향별 후보 최적화를 구별하며 E/Reserve·Nutrition/SatLeft·Raw/실제 행동을 진단한다. B-2→C→D→E→F로 진행한다. 아래 기존 최종 빌드/패키지·HUD·예산 미완료는 F 회귀에 함께 추적하며 삭제하지 않는다. 실행 중인 엔진/빌드를 중단하지 않는다.

1. git status/diff와 실행 중인 프로세스를 확인한다. 이번 세션의 cook/패키지 실행은 정상 종료했다. 완료 기록과 현재 Source를 대조해 새 변경부터 판정한다.
2. 완료된 직접 UBT·자동화·Play·NetworkWideView·WaterToggle 검증을 중복 구현/반복하지 않는다. 변경이나 새 실패가 있을 때 필요한 검증을 재실행한다.
3. 기존 landscape procedural 누락 Display 경고와 이번에 복구한 풀 재질을 구분한다. 식생 색·alpha는 실제 Editor/패키지 캡처로 확인했다.
4. HUD의 실제 화면/단축키 검수는 컴퓨터 사용 승인 대기다. 사용자의 응답 없이 같은 승인 요청을 매 회차 반복하거나 다른 입력 경로로 우회하지 않는다. 승인이 준비되면 Alt+G·지역 선택·기후 조작·자동 복귀·진단 저장을 확인한다.
5. 다음 첫 독립 작업은 현재 NetAudit C++ 변경 이후의 관련 식생 회귀와 최종 Game UBT/cook/패키지 검증을 최신화하는 것이다. 실행 중 엔진/빌드가 있으면 기다린다. 계획 대비 입력 이력/자동 판정·장식 구분 UI의 남은 요구도 기존 코드와 대조한다. 소켓/payload/최신 base 계측은 완료했으며 전체 연결·GPU 메모리/배포 예산과 구분한다. Depletion/Travel/ProfileComplete는 관련 변경 없이 반복하지 않는다.
6. 자동 시험 진행/입력 이력, 장기 반복·저장 회귀 등 남은 완료 조건을 수행하고 실제 결과를 이 문서에 갱신한다. 프로젝트 전체 완료 전 heartbeat를 끄지 않는다.

## 차단 요인과 해결 이력

이번 명세 작성의 차단은 없다. 일반 git status는 git-lfs filter의 로컬 sh 권한 오류로 실패하여 해당 읽기 명령에서만 LFS filter를 비활성화해 상태를 확인했다(저장소 설정 변경 없음). 과거 HUD 승인/빌드 실행 중 기록은 아래에 보존하며 다음 실제 실행 전에 재확인한다. 문서 작성에서는 런타임 검증을 시도하지 않았다.

2026-11-08 18:54 KST 최종 검증 시작 전 검사에서 Unreal Editor와 Live Coding Console 실행을 확인했다. 식생 자동화, Game 빌드, 패키징을 시작하지 않았으며 실행 중인 프로세스는 유지했다. 다음 회차에는 엔진이 비어 있을 때 `FoodGrass_20261108_FinalBuild`에 식생 자동화 결과를 기록하고, 통과 후 같은 실행 폴더로 Game UBT·패키징·90초 실행을 순차 검증한다.

실제 HUD 화면/키보드 검수는 컴퓨터 사용 도구의 앱 승인 시간초과로 차단됐다. 창 선택 후 상태 캡처를 요청했지만 “Computer Use app approval timed out”이 반환됐으며 입력 동작은 수행하지 않았다. 사용자가 컴퓨터 사용 요청을 승인할 수 있을 때 해당 검수를 재개한다. 코드/서버 진단 기반의 독립 검증은 이어갈 수 있다.

- 직전 마지막 빌드 시도가 자동 승인 검토의 사용량 제한으로 실행되지 않았다. 재개 후 승인된 빌드·시험을 수행했으므로 현재 그 차단은 해소됐다.
- Get-CimInstance를 사용하는 기존 빌드 helper는 제한된 실행 환경에서 접근 오류가 있었다. Get-Process로 선행 검사 후 직접 UBT를 실행했던 경로를 따른다. 외부 엔진 캐시 쓰기에는 승인된 실행 환경이 필요하다.
- 과거 실패한 Play 테스트 에디터는 명령줄·로그로 확인하여 정리했다. 새 빌드/시험 전 프로세스 검사를 계속 적용한다.
- 첫 멀티는 로컬 Steam 접속·프로토콜 조건 때문에 실패했다. -nosteam/EcoProtocol=1 및 명시적 QA 표시 범위 적용 후 종합 검사가 통과하여 해결됐다.
- 기존 landscape procedural 패키지 누락 Display 경고는 남아 있다. 이번 cook은 성공했으며 이후 원인별 자산 감사 시 별도 확인한다.

## 예약

30분 주기의 현재 대화 heartbeat를 생성하고 설정 파일까지 확인했다. ID는 automation-2, 이름은 생태계 풀 표현 개발 이어가기, 상태는 ACTIVE다. 대상 대화 ID는 01a1b884-8a95-7900-a841-24f7e2e7e188이다. 완료 조건 달성 후 이 예약을 비활성화한다.

2026-11-08 사용자 재요청으로 같은 예약을 갱신하고 ACTIVE 상태를 재확인했다. 현재 대화 유지·새 대화 생성 금지, 매회 PROGRESS/Git/코드 대조, 사용량 제한 시 다음 회차 대기, 구현/테스트 후 기록, 완료 시 예약 비활성화, 승인 필요 시 중단·보고를 예약 지시문에 명시했다.

## 2026-11-08 재개 기록

아래는 작업 당시의 순차 기록이다. 현재 완료/진행/미완료 판정은 위 요약을 우선한다.

- PROGRESS.md를 생성하고 실제 Source·Git 상태와 이전 로그를 대조했다.
- 첫 재빌드 선행 검사에서 다른 프로젝트 GE_AIReplication의 빌드와 과거 테스트 에디터를 발견하여 새 빌드를 시작하지 않았다. 다른 프로젝트 빌드는 이후 자연 종료했다.
- 남은 PID 18544는 명령줄을 통해 이번 대화가 시작한 감사 도구 실패 에디터로 확인했다. 정상 종료 요청 후 프로세스 종료를 확인하고 재빌드한다.
- 해당 실행은 정상 종료 창이 없어 CloseMainWindow가 실패했다. 시작 오류 로그와 명령줄을 대조한 뒤 그 테스트 PID만 종료했다.
- 마지막 수정분 직접 UBT가 성공했다. 14개 action, 종료 코드 0, 35.43초. 기존 은신처 에셋 경로와 지면 예산·셀 진단·mesh fallback을 포함한다.
- FoodGrass_20261108_Retry 폴더에서 전체 자동화와 65초 기존 맵 Play 검증을 순차 실행 중이다. 종료 결과를 확인해 이 문서를 갱신한다.
- 재개 후 전체 자동화는 235개 중 성공 233, 경고 포함 성공 2, 실패 0, 미실행 0이다. RefugeVisualComposition 수정과 GrassDebugClimate가 통과했다. 증거는 AdaptiveEcosystem/Saved/FoodGrass_20261108_Retry/Automation/index.json에 있다.
- 기존 맵 65초 Play 감사는 FINISHED, 오류 없음, 캡처 2개다. 선택 지역 기후/다른 지역 격리/자동 복귀/먹이 장부가 통과했다.
- 캡처를 직접 확인해 기존 JYU 풀 재질의 누락 텍스처/함수 때문에 회색 불투명 판이 그려지는 문제를 발견했다. Config/DefaultEngine.ini에 실제 존재하는 이사 후 패키지로 정확한 경로 redirect를 추가했다. 새 에셋 생성 없이 기존 재질 그래프를 유지한다. 화면 재검증 대기다.
- listen 서버에서 remote controller 대신 local controller를 선택하도록 변경하고, 후보 난수의 X/Y 호출 순서를 명시하여 컴파일러 평가 순서 차이를 제거했다. 이 수정의 직접 UBT와 배치·네트워크 재검증이 필요하다.
- 위 수정 직접 UBT가 성공했다. 4 action, 종료 코드 0, 52.05초. FoodGrass_20261108_Material에서 재질 화면/기후 시험, 이후 FoodGrass_20261108_Network에서 Dedicated+Client2/late join을 실행 중이다.
- 재질 경로 복구 후 기존 맵 65초 Play가 FINISHED로 종료했다. 새 캡처에서 풀의 잎 alpha와 색이 정상으로 복구된 것을 직접 확인했다. 해당 재질 compile 실패 로그가 사라졌다. 기존 맵과 에셋 바이트를 유지하고 설정의 정확한 package redirect로 연결했다.
- 첫 멀티 실행은 기존 감사 runner가 Steam 로컬 접속 및 현재 세션 protocol 인자를 반영하지 않아 연결 실패했다. 기능 성공으로 세지 않는다. 기존 다른 네트워크 runner와 동일하게 test_vegetation_network.ps1에 -nosteam과 EcoProtocol=1을 적용했다. 실행 중 프로세스의 정상 종료를 기다린 후 새 폴더에서 재검증한다.
- FoodGrass_20261108_NetworkLocal의 두 Client는 passed=true, 권위 개체0, 로컬 이주 Subsystem0, 실제 풀 수신을 확인했다. 각 Client의 best 표본은 2개 Field/풀2275개이며 전체 관찰에서 세 지역을 모두 수신했다.
- 근거리 relevance 검사는 ClientA 102표본, ClientB 38표본에서 누락0이다. 2 Client 동시 관찰은 15표본/28.343초로 통과했다.
- 같은 종합 runner의 late_join_life 검사는 서버에서 자연 출생157/158/159를 관찰했으나 ClientB에서 그 ID를 관찰하지 못해 실패했다. 전체 runner 결과는 실패로 기록한다. 식생 전송 검사 통과와 자연 출생 표현 증거 부족을 구분한다. 실제 relevance 범위/관찰자 위치를 분석해야 한다.
- 동일 PC D3D11 960×540에서 Client A/B 관찰 frame p95는 약19.77/31.58ms, max24.68/57.50ms다. 단기 두 프로세스 시험값이며 고정 성능 예산이나 개선율로 확대하지 않는다.
- 기존 audit_vegetation_runtime.py에 -VegetationGrassVisualCheck 선택 회귀를 추가했다. 8~14초 표시 OFF 뒤 ON으로 복귀하고, 숨김 중 Native step 진행·복귀 후 실제 인스턴스를 검사한다. FoodGrass_20261108_VisualToggle에서 실행 중이다.
- VisualToggle 시험은 FINISHED로 통과했다. 별도 WaterToggle 실행에서는 실제 authored 수원 OFF/ON이 soil의 connected_water_cells에 반영되는지 추가 검사 중이다.
- 자연 출생 late join 관찰 부족 원인을 확인했다. 현재 ClientVisualDistance 기본값은1000cm이며 관찰된 자식들은 시점에서 그 밖에 있었다. 기본 동작을 유지하고 기존 멀티 QA 도구에 선택적 ClientVisualDistanceCm 인자를 추가했다. 넓은 관찰 범위를 명시한 재시험으로 종합 life 수신 여부를 확인한다.
- WaterToggle 시험도 FINISHED로 통과했다. Forest의 기존 연결 수원을 끈 20~28초 표본은 공급 셀0, 복구한 48~64초 표본은 공급 셀9로 실제 soil 입력 반영을 확인했다.
- FoodGrass_20261108_NetworkWideView에서 QA Client 표시 거리20000cm를 명시한 종합 멀티 재시험 중이다. 프로젝트의 저장된 표시 거리 기본값은 변경하지 않았다.
- 기존 package_ecosystem.ps1/test_ecosystem_package.ps1에 선택적 결과/아카이브 폴더 인자를 추가했다. 기본 호출은 기존 경로를 유지하며, 이번 패키지는 Saved/FoodGrass_20261108_Package 및 Saved/FoodGrassPackage로 분리한다.
- 멀티 프로세스가 끝난 후에만 게임 타깃 UBT→cook/stage/archive→패키지 실행을 시작하도록 대기 실행을 준비했다. 현재 단계와 실제 결과는 로그/실행 프로세스를 확인해 갱신한다.
- NetworkWideView 종합 검사가 passed=true로 끝났다. 두 Client 근거리 검사99/38표본에서 누락0, 동시28.313초, late join 자식157/159의 BodyScale 오차0으로 기존 허용 범위를 통과했다. QA 표시 거리20000cm라는 조건을 유지해 해석한다.
- 멀티가 종료된 뒤 게임 타깃 AdaptiveEcosystem Win64 Development 직접 UBT가 시작됐다. 최종 패키지/cook 결과를 확인할 때까지 완료로 표시하지 않는다.
- 게임 타깃 직접 UBT가 38 action/64.92초로 성공했다. 기존 맵의 UAT cook이 시작됐으며 새 shader/texture 캐시를 생성하고 있다. 기존 landscape procedural 패키지의 누락 경고도 있어 최종 cook 결과와 최초 실제 오류를 확인한다. 실행 중 cook을 중단하거나 겹쳐 빌드하지 않는다.
- UAT cook/stage/pak/archive가 BUILD SUCCESSFUL, ExitCode=0으로 완료됐다. 실행 파일은 AdaptiveEcosystem/Saved/FoodGrassPackage/Windows/AdaptiveEcosystem.exe다. 기존 landscape procedural 누락 Display 경고는 남아 있다.
- 생성된 Development 패키지의 90초 실행 검사 중이다. 결과는 Saved/FoodGrass_20261108_Package/PackagedSmoke.log와 해당 패키지의 Screenshots를 확인한다.
- 90초 Development 패키지 검사가 ECOSYSTEM_PACKAGED_SMOKE_FINISHED, 종료 코드0으로 끝났다. 실제 캡처에서 잎 alpha·색과 기존 맵의 표현을 확인했다. 캡처는 Saved/FoodGrassPackage/Windows/AdaptiveEcosystem/Saved/Screenshots/Windows/HighresScreenshot00000.png다.
- 마지막 git diff --check는 오류가 없었다. 새 레벨/게임모드/플레이어/콘텐츠 에셋을 생성하지 않았고 이번 기능은 기존 구성요소와 설정 확장으로 연결했다. 변경은 아직 미커밋이다.
- 현재 장기 실행 프로세스는 정상 종료했다. 전체 목표 중 경계값/배치 재현/장기 반복/성능 예산·UI 검수가 남아 있으므로 heartbeat automation-2는 ACTIVE를 유지한다.

## 2026-11-08 10:42 예약 실행 기록

- 대화 목표·AGENTS/PROJECT_CONTEXT/PROGRESS·Git 변경을 대조했다. 기존 C++ 구현을 재사용하고 첫 미완료 항목인 soil OFF 표시 조합부터 시험했다.
- 기존 audit_vegetation_runtime.py에 선택적 -VegetationGrassSoilOff 모드를 추가했다. 기존 레벨 spawner의 enable_vegetation/enable_food_grass를 Play 전 메모리에서 변경하고 종료 시 원래 값으로 복구한다. 맵/에셋을 저장하지 않는다.
- 기존 LV_JYU_Ecosystem, seed23, 40초, -VegetationGrassVisualCheck 조합에서 FINISHED/오류0/프로세스 exit0을 확인했다.
- 모든 지역의 soil=false, soil 성장/환경 손실0, FoodGrid와 M4 장부 오차0, 숨김 중 Native 진행과 표시 복귀를 검사했다. 마지막 표본의 Forest/Barren 인스턴스는1512/780개이며 먼 Highland는 거리 제한으로0개다.
- git diff --name-only -- AdaptiveEcosystem/Content 결과가 비어 있어 저장된 콘텐츠 변경이 없음을 확인했다.
- 이번 작업은 QA Python·문서 변경이며 새 C++ 빌드/전체 자동화는 실행하지 않았다. 새 UBT 검증이 필요한 C++ 변경도 없다.
- 다음 우선 작업을 0/미세 잔량·용량 정량화 경계로 갱신했다. 확정된 차단 요인은 없고 전체 완료 조건이 남아 있으므로 예약을 유지한다.

## 2026-11-08 11:12 예약 실행 기록

- 목표·지침·기존 diff와 실행 프로세스를 확인하고 정량화 경계 작업을 이어갔다.
- 기존 FEcoVegetationVisualCell에 실제 publisher가 사용하는 EncodeAmount와 renderer가 사용하는 HasRenderableFood를 연결했다. 16bit 표현에서 0/양의 미세 잔량 구분, 유한값의 [0,1] 포화 의미를 유지한다. 비유한 값은0으로 표현하도록 보강했다. Native FoodGrid/M4 잔고는 수정하지 않는다.
- 기존 EcoVegetationTest.cpp에 GrassAmountEncoding 회귀를 추가했다. 음수/NaN/무한대/0/미세 잔량/만량/포화, 용량0 숨김, 4097점 단조성·정량화 오차 한 단위 이내·먹이/용량 순서 보존을 검사한다.
- 직접 Editor UBT는 10 action/33.21초로 성공했다. 증거는 Saved/FoodGrass_20261108_AmountEncoding/Build.log다.
- 해당 빌드의 AdaptiveEcosystem.Vegetation 자동화를 실행 중이다. 종료 결과를 확인하고 현재 상태를 갱신한다. 기존 Game/패키지 성공 기록은 이 정량화 보강 이전 빌드의 증거다.
- 해당 식생 자동화는 성공8, 경고/실패/미실행0, 프로세스 종료0으로 완료했다. 새 GrassAmountEncoding과 기존 soil/장부/Native feeding/OFF trajectory/기후·저작 검사를 함께 통과했다.
- 이번 변경은 Source/AdaptiveEcosystem/World/EcoVegetationField.h/.cpp와 기존 AI/Policy/Tests/EcoVegetationTest.cpp다. 새 레벨/에셋·게임모드·플레이어 추가는 없다.
- 다음 작업을 후보 지면 재검사 예산/streaming 공정성으로 갱신했다. Game/패키지는 최종 변경을 묶어 필요한 시점에 재검증하며 이번 빌드의 성공으로 소급하지 않는다. git diff --check는 오류0이다.

## 2026-11-08 11:42 예약 실행 기록

- 현재 지침·목표·Git/실제 Field 구현을 대조하고 지면 재검사 예산을 점검했다. 고정 배열 앞에서부터 매번 재검사하던 경로는 빠른 실패 재시도가 많거나 후보 수가 예산보다 많으면 뒤쪽 후보를 계속 밀어낼 수 있었다.
- 기존 Field 캐시에서 기한이 가장 오래 지난 후보부터 예약 예산만큼 선택하도록 수정했다. 같은 기한은 안정 후보 ID 순서를 사용한다. 새 후보 조회 예산은 별도로 유지한다.
- 기준 지면 anchor가 바뀌면 기존 인스턴스를 숨기고 재검사 대기 상태로 돌려, 과거 지면에 풀이 남는 경우도 처리했다. 새 manager/Actor/정책 writer는 추가하지 않았다.
- 기존 EcoVegetationTest.cpp에 GrassGroundRefreshFairness를 추가했다. 역순 삽입1200개/회당24개/실패1초·성공5초 재시도에서 모든 후보가 첫 검사를 받기 전에 재검사된 후보가 예산을 선점하지 않음, 기한/안정 ID 순서, 미래 기한 유예·예산0을 검사한다.
- 직접 Editor UBT가 10 action/29.17초로 성공했다. Saved/FoodGrass_20261108_GroundFairness/Build.log를 남겼다.
- 식생 자동화와 기존 맵40초 표시 OFF/ON 회귀를 순차 실행 중이다. 실제 종료 결과를 확인한다.
- 식생 자동화는 성공9, 경고/실패/미실행0, 종료 코드0으로 완료했다. 새 공정성 회귀와 정량화/기후/토양/장부/Native feeding/OFF trajectory 검사를 포함한다.
- 기존 LV_JYU_Ecosystem의40초 Play와 표시 OFF/ON도 FINISHED, 오류0, 프로세스 종료0이었다. 마지막 표본은 풀1952개, Native step288이며 FoodGrid/M4 수지를 유지했다.
- 변경 파일은 기존 World/EcoVegetationField.h/.cpp 및 AI/Policy/Tests/EcoVegetationTest.cpp다. Game/패키지·멀티는 이전 검증 기준을 유지하며 이 수정의 결과로 소급하지 않는다.
- 다음 작업을 후보 위치 재현성과 실제0 잔량 인스턴스 제거/복귀로 갱신했다. git diff --check는 오류0이며 전체 완료 조건이 남아 있어 예약을 유지한다.

## 2026-11-08 12:13 예약 실행 기록

- 기존 지침·목표·Git 상태·Field/ISM 구현을 대조하고 다음 항목인 위치 재현/실제0 잔량 표현 회귀를 진행했다.
- 기존 RefreshVisuals의 로컬 시점 취득과 실제 후보 갱신을 분리했다. 정상 진입점은 같은 RefreshPlants를 호출한다. 테스트만을 위한 공개 API나 새 runtime Actor/manager는 추가하지 않았다.
- 기존 EcoVegetationTest.cpp에 GrassVisualLifecycle을 추가했다. 기존 테스트 World/Field와 실제 엔진 Cube 바닥 충돌·ISM으로9개 생성, 안정 ID 유지, 먹이 감소3개,0 잔량 제거, 미세 잔량1개, 완전 회복, 거리 이탈/재진입, 지면 충돌 제거/복귀, anchor 변경 시 과거 표현 정리를 검사한다.
- 해당 시험은 표현 DTO fixture를 입력하며 Native 먹이/장부를 조작하지 않는다. 실제 생태계의 자연 고갈/재성장 장면 검증과 구분한다.
- 직접 Editor UBT는14 action/40.45초로 성공했다. 증거는 Saved/FoodGrass_20261108_VisualLifecycle/Build.log다.
- 실제 ISM 회귀를 포함한 식생 자동화를 실행 중이며 종료 결과를 확인한다.
- 식생 자동화는 성공10, 경고/실패/미실행0, 프로세스 종료0으로 완료했다. 새 GrassVisualLifecycle을 포함한 실제 ISM·충돌 fixture에서 계획한 모든 단계를 통과했다.
- source 변경은 기존 Field의 시점 입력/후보 갱신 분리와 기존 테스트 파일의 회귀 추가다. 생산 코드의 후보 배치·섭식·장부 의미는 유지했다.
- 다음 우선 작업을 기존 HUD 직접 조작과 진단 저장 검수로 갱신했다. 실제 생태계 섭식/고갈과 World Partition 검증을 DTO/바닥 fixture 성공으로 대체하지 않는다. 전체 완료 조건이 남아 있어 예약을 유지한다.

## 2026-11-08 12:42 예약 실행 기록

- 현재 목표·지침·Git 상태·기존 HUD/명령 구현을 대조하고 실제 UI 검수를 시작했다.
- 기존 LV_JYU_Ecosystem의 -game 실행을 사용한다. 새 레벨·게임모드·플레이어를 만들지 않는다.
- 첫 테스트를 Hidden 창으로 실행하여 컴퓨터 사용 도구의 대상 목록에 나타나지 않았다. 이 실행의240초 정상 종료를 기다린 후 직접 단축키 조작을 위한 표시 창으로 재실행한다. 사용자 앱이나 진행 중 빌드를 중단하지 않는다.
- UI 동작은 아직 통과로 기록하지 않는다. 기존 진단 명령의 백엔드 검증과 실제 키보드/화면 검수를 구분한다.
- 첫 Hidden 테스트는240초 정상 종료했다. 그 후 기존 맵을 조작 가능한 표시 창으로 실행했고, 도구 목록에서 단일 AdaptiveEcosystem 게임 창을 선택했다.
- 실제 창 상태 캡처 요청은 컴퓨터 사용 앱 승인 시간초과로 종료됐다. Alt+G 등 키보드 입력이나 기후/저장 조작은 수행하지 않았으며 검수 통과로 세지 않는다. 승인을 우회하지 않고 해당 작업을 중단했다.
- 표시 창 실행도 -EcoIntegrationExitAfter=240으로 제한돼 있다. 로그는 Saved/FoodGrass_20261108_HUD/InteractiveHUD.log다. 정상 종료 상태를 확인한 뒤 기록한다.
- 후속 확인에서 표시 창도12:49:12에 정상 종료한 로그를 확인했다. 승인 시간초과 결과를 받은 뒤16:22에 진행 기록을 갱신했다. 대기 중 테스트 창을 무기한 남겨두지 않았다.
- 이번 회차는 실행/문서 작업이며 새 C++ 또는 에셋 변경이 없다. 이 승인에 대한 사용자 응답 전 같은 UI 승인 요청을 반복하지 않고 독립적인 검증을 다음 작업으로 진행할 수 있게 기록했다.

## 2026-11-08 16:23 예약 실행 기록

- 목표·AGENTS/PROJECT_CONTEXT/PROGRESS·Git diff와 실행 프로세스를 확인했다. HUD 승인 요청은 반복하지 않고 독립적인 실제 Native 섭식 셀 검증을 이어간다.
- 기존 CaptureDiagnostics(true)에 현재 Native 소스의 먹이 코드, 마지막 publication Native step, 셀별 DTO·실제 ISM 유효 인스턴스·같은 먹이 코드로 갱신된 인스턴스 수를 추가했다. 평소 요약/네트워크 payload/먹이 장부는 유지한다.
- 기존 audit_vegetation_runtime.py에 선택적 GrassFeedingCheck를 추가했다. 같은 Native step의 source→DTO 일치를 검사하고, 실제 intake>0 개체가 있는 셀의 DTO가 다음 로컬 refresh에서 ISM에 반영되는지 추적한다. 직접 먹이/개체 writer는 추가하지 않았다.
- Python 구문과 diff 형식은 통과했다. C++ 변경의 직접 Editor UBT와 기존 맵 시험을 시작하며 최종 결과 전에는 검증 완료로 표시하지 않는다.- 직접 Editor UBT는10 action/37.81초, 종료0으로 성공했다. 증거는 Saved/FoodGrass_20261108_Feeding/Build.log다.
- 첫 실행 명령에 감사 스크립트의 VegetationMap 인수를 빠뜨려 기존 기본 HerdMigration 맵으로 전환됐다. 이 실행은 의도한 Ecosystem 시험으로 세지 않는다. 실행 중 프로세스는 중단하지 않고 기존 관찰 deadline의 정상 종료를 기다린다. 새 feeding 모드의 기본 맵을 Ecosystem으로 명시해 같은 설정 실수를 예방했다.
- 첫 실행은 기존 deadline으로 FAILED/Initialization-observation deadline을 기록하고 프로세스0으로 정상 종료했다. 이후에만 명시적 VegetationMap=LV_JYU_Ecosystem으로 새 실행을 시작했다.
- Saved/FoodGrass_20261108_FeedingRetry의45초 재시험은 FINISHED/오류 없음/프로세스0이다. 동기30시점의13976셀 Food/Capacity 코드가 모두 Native source와 일치하고 M4 차이는0이었다.
- 실제 intake>0 개체의1006관측과 해당 셀 DTO를 추적했다. 이후 실제 ISM의 같은 Food/Capacity 코드913관측(194고유 셀)을 확인했다. 셀44는 Native step18 food0.398026/code26085/풀4개에서 step26 food0.084942/code5567/풀1개로 변했다.
- 먹이 변화659관측 중 감소247/증가412가 있었으며, 성장·환경 손실도 함께 작동하므로 순 감소를 순수 섭식량으로 해석하지 않는다. 완전0 고갈과 회복 장면의 acceptance는 계속 미완료로 둔다. 종료 때 대기8셀은 전체 셀의 표시 완료 보장이 아니라 일부 실제 섭식 셀의 표현 대조라는 시험 범위를 유지한다.
- 이 회차의 변경 파일은 기존 Field.h/.cpp, audit_vegetation_runtime.py, 테스트 안내와 PROGRESS다. 새 콘텐츠/레벨/플레이어/게임모드·먹이 writer는 없다. Python 구문·git diff --check 오류0, 실행 중 빌드/에디터 없음도 확인했다.
- 다음 첫 작업은 World Partition/LOD 또는 상세 진단을 끈 정상 실행의 성능·메모리·전송량 계측이다. 기존 HUD 승인 대기는 그대로이며 새 승인 요청을 반복하지 않았다. 전체 완료 조건이 남아 있어 automation-2를 유지한다.
## 2026-11-08 16:53 예약 실행 기록

- 목표·지침·PROGRESS·Git 실제 diff와 프로세스를 확인했다. 현재 다른 빌드/에디터는 없으며 기존 사용자 변경은 보존한다. HUD 승인 요청은 반복하지 않았다.
- 기존 Field에 CSV 실행 시간(GatherGround/PublishCells/RefreshVisuals)과 후보 지면 trace 수 계측을 추가했다. 일반 진단에는 visual DTO 배열·후보/지면 캐시·흔적 배열의 실제 컨테이너 할당량, 후보 상한, Native FoodGrid의 보조 배열 포함 버퍼 할당량을 추가했다. 공유 메시/재질·ISM render/GPU 버퍼·allocator 부가비용을 포함한 전체 메모리로 설명하지 않는다.
- 기존 runtime 감사 도구에 선택적 GrassProfile 모드를 추가했다. 상세 개체/셀 조회·화면 캡처를 제외하고 CSV를 기록한다. 평소 기능과 저장된 맵/에셋, Native writer·FoodGrid/M4 권위는 유지한다.
- Python 구문·diff 형식은 통과했다. 이 C++ 변경의 직접 Editor UBT와 기존 맵 실측 결과는 완료 후 갱신한다.- 직접 Editor UBT는4 action/51.59초, 종료0으로 성공했다. Saved/FoodGrass_20261108_Profile/Build.log가 근거다.
- 첫65초 Play는 FINISHED/프로세스0이지만 CSV 비동기 저장 완료 전 quit로 파일 끝의 최종 header/metadata가 잘렸다. 기존 summary 초안이 가변 열 수를 잘못 처리해89frame만 통과시킨 것도 확인했다. 이 초기 ProfileSummary.json은 passed=false/invalid_reason으로 명시적으로 무효화하고 원본 로그/파일을 보존했다. 이 수치로 성능 통과를 주장하지 않는다.
- 기존 audit 도구가 CSV 완성 footer를 확인한 뒤 종료하도록 보완했다(30초 제한, 미완성 시 FAILED 기록). 기존 summarize_vegetation_evidence.py에 선택적 --grass-profile을 추가해 최종 header·전체 capture duration·CPU scope/trace/메모리·캐시 상한을 검증한다. 잘린 첫 CSV를 새 요약기가 거절하는 것도 확인했다.
- 재측정은 별도 FoodGrass_20261108_ProfileRetry에서 진행 중이다. 완료·CSV flush·프로세스 종료 후 결과를 기록한다.- ProfileRetry는 CSV6595frame·약60초가 완성됐지만 UE의 마지막 metadata 줄에 개행이 없다는 형식 차이로 종료 검사에서30초 후 FAILED를 기록했다. 실제 파일 완성과 실행 gate 실패를 구분하고 이 회차를 최종 통과로 세지 않는다. 완료 footer와 파일 크기 안정 상태로 판정을 수정한 ProfileComplete를 시작했다. C++ 변경은 없으며 새 UBT는 필요 없다.
- ProfileComplete의65초 Play는 FINISHED/오류 없음, VEGETATION_PROFILE_CSV_FLUSHED, 프로세스0으로 정상 종료했다. 요약기는 CSV59.985초/6583frame의 최종 header/metadata를 읽고 passed=true를 기록했다.
- 로컬 Ryzen5 9600X/RTX3060/D3D11, CSV 시스템1280×720(PIE viewport 별도 미계측)에서 세 지역 합산 RefreshVisuals 실행 프레임 p95/max1.3486/2.0671ms, PublishCells0.0893/0.1195ms, GatherGround0.1266/0.2761ms였다. 전체 Editor FrameTime10.3979/28.6024ms와 식생 자체 시간을 구분한다.
- 후보 지면 trace는 프레임 최대117회로 합산 설정 상한288회 이내였고, 후보 수 상한·먹이/M4 일치·실제 표시·상세 dump/캡처 제외를 모두 통과했다. 총 인스턴스 표본 최대2290개, 표시 컨테이너 할당 합산 표본 최대494624bytes, Native FoodGrid 보조 버퍼 포함417264bytes였다. 공유 에셋/ISM CPU/render/GPU·복제 연결 전체 비용과 실제 wire bytes는 미계측이다.
- 최종 변경은 기존 Field.cpp의 CSV/읽기 전용 메모리 진단, 기존 runtime/summary QA 도구와 계획·사용법·PROGRESS다. 이번 회차의 새 C++ 기능은 계측뿐이므로 관련 기존 자동화10개를 이유 없이 반복하지 않았으며 Game/패키지를 새 검증으로 소급하지 않는다.
- 다음 작업은 기존 World Partition 준비 helper/Client streaming 경로를 읽고 권위 지면을 보존하는 구역 왕복/LOD 시험을 구성하는 것이다. 최종 예산·실제 네트워크 계측·HUD 승인 대기·전체 완료 조건이 남아 있어 automation-2를 유지한다.
## 2026-11-08 17:23 예약 실행 기록

- 목표·AGENTS/PROJECT_CONTEXT/PROGRESS·Git diff와 프로세스를 확인했다. 새 빌드/에디터가 없고 기존 사용자 수정은 보존한다.
- PrepareCopiedWorld는 Editor의 ±1000000cm 범위를 로드한다. 이 준비 경로의 단독 PIE를 실제 streaming unload 증거로 쓰지 않는다. 기존 Dedicated 권위 spawner는 HabitatStreamingSource를 유지하고 Client에서는 이 source를 끄는 경계를 확인했다.
- 기존 Field 진단에 near/coarse 실제 인스턴스, 지면 대기 후보, grid extent를 추가했다. 기존 Client 감사 도구에는 선택적 GrassTravelCheck를 추가해 실제 관찰자 지역 방문, LandscapeStreamingProxy 로드/해제, streaming 완료, 거리별 표현·캐시 상한·Client 무권위를 기록한다.
- 기존 네트워크 runner의 선택 인수로 ClientA를380초 관찰하도록 확장했다. 기존 서버 observer cycle을 그대로 사용하며 새 레벨/플레이어/manager나 Client pawn·먹이 writer를 추가하지 않는다. 이번 실행은 직접 Editor UBT와 정상 종료까지 확인한 뒤 판정한다.- 직접 Editor UBT는4 action/51.61초, 종료0으로 성공했다(Saved/FoodGrass_20261108_Travel/Build.log). Python/PowerShell 구문과 diff 형식도 통과했다.
- 기존 네트워크 runner를 Duration430/ExitAfter480, ClientA380초 관찰, ClientB late join, QA 표현 거리20000cm로 시작했다. 서버/Client의 기존 정상 종료 타이머를 유지하고 실행 중 빌드를 중단하거나 추가 빌드하지 않는다. 아직 최종 통과로 표시하지 않는다.- ClientB의 짧은 late join은 passed=true, 권위 개체0/Native step0, 세 지역 수신, near/coarse 표현 확인으로 완료됐다. ClientA 장기 실행과 전체 runner는 아직 진행 중이다.
- 기존 validate_vegetation_relevance.py에 장기 보고서가 있을 때만 적용되는 판정을 추가했다.2초 이상 유지된 지역 방문을 세어 각 지역10회 이상과 방문별 streaming 완료 후 근거리 풀 표시를 확인한다. 순간적인 nearest-region 변화만으로 방문 수를 부풀리지 않는다.- ClientA380초 감사가 passed=true로 저장되고 정상 종료했다. 원시 지역 방문은 Barren/Forest/Highland 각각11회, Landscape proxy 집합 추가316/제거321건, streaming 완료·near/coarse·후보 캐시 상한이 통과했다. Client 권위 개체/Native step은0이다.
- ClientA/B가 모두 정상 종료했다. 최종2초 이상 안정 방문 판정·전체 서버 기록·서버 정상 종료·종합 relevance/life 검사는 아직 결과를 기다린다.
- 서버와 두 Client가 정상 종료했고 전체 runner는 VEGETATION_NETWORK_FINISHED/종료0이다. 최종 Relevance.json passed=true,2초 이상 안정 방문은 Forest11/Barren10/Highland11회이며 각 방문의 streaming 완료 후 near 풀 표시가 모두 확인됐다.
- ClientA의381표본/380.5초에서 실제 Landscape proxy 추가316/제거321건, 동시 로드29~44개를 관찰했다. 후보 최대 Forest1510≤4329/Barren1263≤3906/Highland776≤3177, 후보 캐시 할당 peak156264/156264/80584bytes로 기록했다. 전체 CPU/GPU 메모리 누수 보장으로 설명하지 않는다.
- 근거리 누락 검사는 ClientA509/ClientB30표본에서0, 두 Client 동시 관찰28.344초, late join 자식159의 BodyScale 일치, 두 Client 권위 개체0/Native step0이었다. 서버 감사212표본의 FoodGrid/M4 오차는0, 마지막 Native step은 세 지역3231이다.
- 최종 변경은 기존 Field.cpp 읽기 전용 진단, audit_vegetation_client.py/test_vegetation_network.ps1/validate_vegetation_relevance.py 선택 QA 확장과 계획·안내·PROGRESS다. 실제 실행은 기본 후보9와 QA 표현 거리20000cm 조건이다. 후보1에서 near/coarse 배율이 같아지는 진단 한계도 안내했다.
- 다음 우선 작업은 기존 기후 디버그로 실제0 고갈→동일 셀 회복/ISM 복귀를 확인하는 것이다. Native soil의0 도달 조건부터 대조하고 직접 먹이 writer를 만들지 않는다. wire bytes·최종 예산·HUD 승인·최종 Game/패키지 등 남은 완료 조건이 있으므로 automation-2를 유지한다.
## 2026-11-08 17:53 예약 실행 기록

- 대화 목표·AGENTS/PROJECT_CONTEXT/PROGRESS·Git diff·실행 프로세스를 확인하고 실제0 고갈/회복 항목을 이어갔다. 다른 빌드/에디터는 없다. 기존 사용자 변경과 HUD 승인 대기는 유지한다.
- Native soil Advance는 usable 지면에서 기존 먹이에 비례한 지수 손실을 사용한다. 가뭄/환경 손실만으로 짧은 시간의 정확한0을 보장하지 않으며, 기온50℃에서는 TempSuit=0으로 성장이 멈춘다. 이 조건에서 기존 C4 섭식으로 실제 고갈 후 Rain20℃로 회복시키는 명시적 기후 디버그 시험을 선택했다. 모델/기본값/먹이 writer는 변경하지 않는다.
- 기존 audit_vegetation_runtime.py에 선택적 GrassDepletionCheck와 DryTemperature 인수를 추가했다. 상세 Native/DTO 동기 source를 확인하고 실제 양수 ISM이 있던 셀의0/인스턴스0, 이후 동일 셀의 양수/ISM 복귀를 in-range에서 추적한다. 지역 장부·기후 격리/Auto도 기존 판정으로 검사한다. 일반 GrassDebug 기본30℃와 기존 HUD 프리셋은 유지한다.
- 이번 수정은 QA Python뿐이며 새 C++/빌드 입력 변경이 없다. 구문/diff 형식은 통과했다. 기존 맵120초 시험의 최종 결과를 확인하기 전에는 기능 완료로 표시하지 않는다.
- FoodGrass_20261108_Depletion의120초 기존 맵 시험은 FINISHED/오류 없음, 프로세스0으로 정상 종료했다. Native/DTO 동기84시점, 양수·ISM 표시456셀 중236셀에서 정확한food0/code0/인스턴스0을 확인했고 Rain 구간에 같은236셀 모두 양수·동일 DTO 코드의 ISM이 복귀했다.
- 예시 셀0:0.218초 Native step4 food0.486577367/코드31888/용량코드31888/인스턴스1 →32.703초 step248 food0/코드0/용량 유지/인스턴스0 →49.984초 step378 food0.008795636/코드576/인스턴스1. 관찰은 cull 범위 안에서 진행하고 실제 기존 C4 섭식 누적 증가를 확인했다.
- 전체 일반 표본60개의 FoodGrid/M4 차이는0, 선택 지역 Dry50℃/Rain20℃·수동 override의 다른 지역 격리·Auto 복귀도 통과했다. 일반 GrassDebug의30℃는 그대로다. 이는 명시적 고온 기후 디버그 조건이며 평상시 자연 균형/모든 셀 고갈을 보장하는 시험이 아니다.
- 실행 캡처3개를 생성했고 Dry20초/Rain60초 이미지를 직접 확인했다. 정상 지면·재질을 유지한다. 캡처만으로 모든 기존 장식/은신처를 먹이 Field라고 해석하지 않으며 사용자 구분/UI 검수는 별도 미완료로 보존한다.
- 이번 변경은 기존 audit_vegetation_runtime.py와 계획·사용법·PROGRESS뿐이다. 새 C++/빌드 입력/콘텐츠 변경이 없어 새 UBT·기존 식생 자동화·멀티를 반복하지 않았다. 마지막 C++ 빌드/멀티는17:39의 Travel 결과다.
- 다음은 실제 전송량/연결별 복제 비용 계측 경로 감사다. wire bytes·전체 GPU/연결 메모리·배포 예산·HUD 승인 검수·최종 Game/패키지 등의 완료 조건이 남아 automation-2를 유지한다.
## 2026-11-08 18:23 예약 실행 기록

- 목표·AGENTS/PROJECT_CONTEXT/PROGRESS·Git diff·실행 프로세스를 확인했다. 기존 사용자 변경·HUD 승인 대기는 보존하며 새 C++ 변경 없이 전송 계측 경로를 감사했다.
- 설치된 UE5.8 NetworkProfiler.cpp의 v14 형식, Archive.cpp의 LSB-continuation SerializeIntPacked, DataChannel.cpp의 Actor 복제 종료 시점 기록 순서를 확인했다. SocketSendTo의 실제 소켓 payload bytes와 Field 속성 직렬화 bits는 서로 다른 계층이다. IP/UDP 헤더나 공유 패킷 오버헤드를 풀 payload로 환산하지 않는다.
- 기존 네트워크 runner에 선택적 NetworkProfile을 추가했다. 기존 서버 ExecCmds의 netprofile enable과 감사 종료 시 disable을 사용해 end-of-stream을 남긴다. 기존 summary 도구의 --grass-network로 v14 기록·연결·Field Actor/VisualGrid 속성·initial/delta를 읽는 경로를 추가했다. 미지원/잘린 형식은 거절하며 새 transport·런타임 manager·먹이 writer는 없다.
- Duration145/ExitAfter185, Client2 overlap/late join, QA 표현 거리20000cm의 기존 맵 시험을 진행 중이다. 서버 로그에서 NetworkProfiler 활성화와 실제 기록 파일 생성을 확인했다. 구문 검사 통과. 이번 변경은 QA 도구뿐이므로 새 UBT를 실행하지 않는다. 최종 정상 종료·형식 검증·종합 결과를 확인한다.- 첫 NetProfile 실행은 서버·Client 모두 정상 종료, 종합 passed=true였다. 엔진 기록은 v14/EOS 완성으로 해석됐고 소켓 평균 약30~33kB/s를 관찰했다. 다만 v14 property NumBits가uint16인 점을 확인해 초기/큰 속성 payload의 완전성을 별도 검증하기로 했다. 최초 요약의 raw property 값을 최종 정확한 payload 예산으로 사용하지 않는다.
- 기존 FEcoVegetationVisualGrid의 같은 FastArray 호출을 out-of-line으로 옮기고 기본OFF인 eco.Grass.NetAudit를 추가했다. 실제 Writer bit 차이(int64)와 현재 연결의 새 base state CountBytes만 읽어 로그로 기록한다. ACK/history 전체 메모리를 세었다고 주장하지 않는다. 기존 writer/자료/호출 결과는 보존한다.
- 직접 Editor UBT는10 action/29.34초, 종료0으로 성공했다(Saved/FoodGrass_20261108_NetAudit/Build.log). 신규 소스 계측과 nprof를 같은 새 실행에서 대조하는 재시험을 시작했다. 기본OFF 진단이며 새 actor·transport·food writer는 없다.- 실제 NetAudit 로그에서 Forest121340/Barren109496/Highland89387 struct bits를 관찰해 nprof uint16 property counter의 실제 wrap을 확인했다. 원시 nprof property 값만으로 풀 payload를 계산하면 과소 집계된다.
- 설치된 FRepLayout::SendCustomDeltaProperty는 단일 VisualGrid struct(ArrayDim1)의 callback 전 FastArray 지원 bit1개를 쓴다. 요약기는 직접 writer struct bits+이 bit를 전체 property payload로 집계하고, 각 이벤트의uint16 나머지 합이 nprof VisualGrid 합과 정확히 같은지 검증한다. 이1bit는 프로토콜 근거이며 수치 보정을 임의 추정한 것이 아니다.
- newest base state의 동적 할당량은 Field별10416/10416/7680bytes를 관찰했다. 이는 최신 상태의 CountBytes 결과이며 ACK/history 보관·채널·object 자체·전체 연결 메모리는 포함하지 않는다. 최종 EOS·연결 대조·종합 판정은 실행 완료 후 확인한다.
- NetAudit 재시험은 서버·두 Client 정상 종료/종합 passed=true였다. nprof147.675초/4369frame/EOS를 모두 해석했고 Writer190/55개 이벤트의uint16 나머지뿐 아니라 순서 전체가 일치했다. VisualGrid 실제 property payload는20,596,961/5,880,090bits, 전체26,477,051bits였다. 각 이벤트가65535bits를 넘었으며 초기/델타 최대121341bits다.
- 두 연결의 소켓 송신은3,414,359/940,211bytes, 평균32,255.78/29,840.79bytes/s, 최대1초 bin69,576/51,030bytes다. VisualGrid payload 환산 평균24,322.69/23,328.08bytes/s와 구분한다. 해당 payload가 전체 소켓 송신량 이내인지도 확인했다. 실제 socket payload이며 IP/UDP/link 헤더까지의 packet capture 수치는 아니다.
- 일반 shared 속성 token은 연결을 생략할 수 있어 Actor별 귀속에 섞이는 한계를 확인했다. 최종 요약은 Connection이 명시되는 VisualGrid custom-delta만 집계하고 다른 일반 속성을 Field 비용으로 보고하지 않는다. Actor 클래스도 이름 substring을 가정하지 않고 실제 서버 진단의 visual_class로 선택한다. 이 수정은 기존 완성 기록에 재적용해 모든 대조가 통과했다.
- 최신 base state 동적 메모리 peak는 두 연결 모두 Forest10416/Barren10416/Highland7680bytes다. ACK/history의 보관 상태·object 자체·채널/shared shadow/allocator·전체 연결/ISM GPU 메모리로 확대하지 않는다. initial은 actor/channel 초기·relevance 재진입을 포함하며, delta라도 이 장면에서는 많은 셀이 변경되어 전송될 수 있다.
- 근거리136/29표본 누락0, 두 Client 동시28.282초, late join 자식157/159의 scale 수신·일치, Client 권위 개체/Native step0과 서버72표본 FoodGrid/M4 차이0을 함께 통과했다. NetworkProfileSummary.json의8개 gate가 모두true다.
- 변경 파일은 기존 Field.h/.cpp의 기본OFF 읽기 전용 계측, 기존 runtime/네트워크 runner/summary 도구와 계획·사용법·PROGRESS다. 새 레벨·게임모드·플레이어·transport나 먹이/이동 writer는 추가하지 않았다. Python/PowerShell 구문·git diff --check 오류0, 콘텐츠 diff 없음과 실행 중 빌드/에디터0도 확인했다.
- 다음 실행은 최신 C++ 변경의 관련 식생 자동화와 Game UBT/cook/패키지 검증을 먼저 수행한다. 입력 이력/자동 판정·장식 구분의 남은 계획도 대조한다. 전체 메모리/배포 예산·HUD 승인 등 미완료 조건이 남아 automation-2는 유지한다.

## 2026-11-08 18:54 예약 실행 기록

- AGENTS.md, PROJECT_CONTEXT.md, PROGRESS.md와 현재 Git 및 Field 구현을 대조했다. 기준은 jwj-1024의 395992ab와 작업 트리다.
- 기존 UE 식생 자동화와 Game UBT·패키징·90초 실행의 순서를 준비했다. 실행 전 전체 프로세스 검사에서 UnrealEditor PID37220과 LiveCodingConsole PID37944가 확인되어 시작을 보류했다. 새 검증 결과는 없다.
- HUD와 P1/P6 계획을 대조했다. 현재 구현은 지역 선택과 수동 기후 프리셋, Auto, 현재 시점 JSON 저장을 지원한다. Dry→Rain→Auto 자동 판정은 Editor 감사 도구에서 실행할 수 있다. HUD 내 순차 실행과 입력 이력이 포함된 결과 저장은 미완료다.
- 이번 변경은 PROGRESS.md 기록뿐이다. 다음 작업은 에디터와 Live Coding이 종료된 상태에서 최신 식생 자동화와 Game 패키지 검증을 시작하는 것이다. automation-2를 유지한다.

## 2026-11-08 사용자 요청: 1102 후속 개발 계획

- 변경 파일: `Docs/Architecture/JWJ_1102_FOOD_MIGRATION_SATIETY_PLAN_20261108.md` 신규, `Docs/PROJECT_CONTEXT.md` 진입 링크, 루트 `PROGRESS.md` 목표/재개 순서 갱신. C++·에셋·기본 설정 변경 없음.
- 실제 Source에서 사슴의 대사 후 미세 부족분 반복 섭식, 별도 비축량, 늑대 Nutrition 표시와 포만 타이머 분리, life 사냥 보호 조건, 초식 전용 무리 이주와 카메라 거리 기반 풀 표현을 확인했다. 사용자가 본 개체의 원인은 실행 계측 전이므로 확정하지 않는다.
- 기존 1102 authoring/11-06 검증 기록에 두 지역/route/Field 연결이 있으나 이 맵의 실제 이주 도착은 미검증이었다. 현재 저장본을 새로 읽은 결과로 설명하지 않는다. 설정 스크립트에 다른 전투/스폰 변경도 있어 단순 재실행을 금지했다.
- 계획: A 저장본 감사 → B 풀/카메라 적용 → C 포만/생활 행동 → D 사슴 부족 이주 → E 늑대 증거 기반 추적 이주 → F 기존 HUD 시나리오와 회귀. 시작/중단 기준은 설정화하고 Native 단일 writer·FoodGrid/M4·PPO 원출력·기존 맵을 보존한다.
- 검증은 문서 링크 존재·Source 근거·Git diff 형식 확인으로 한정한다. 이번 작업에 새 UBT/PIE/자동화/패키지 결과는 없다. 1102 저장본/실제 실행, 새 포만/늑대 이주, 최종 회귀는 미완료다.
- 실제 문서 검증 결과: 세 문서의 상대 링크 60개 모두 존재, `git diff --check` 오류 0. 기존 C++ 파일의 줄바꿈 경고만 있었으며 이번 작업에서 해당 코드는 변경하지 않았다.
- 차단: 문서 작성 차단은 없음. 기존 HUD 승인/최종 빌드 보류 이력은 보존하며 현재 프로세스 상태는 이번 문서 작업에서 다시 조사하지 않았다. 다음 실행에서 새로 확인한다. 전체 조건 미충족이므로 예약 완료 처리하지 않았다.

## 2026-11-08 사용자 요청: 1102 4지역과 JYU 풀 적용

- 기존 1102 맵을 로드해 단일 Native 스포너, `JWJ_WildlifeTest`, `JWJ_HuntingMeadow`와 기존 양방향 경로를 확인했다. 중심에서 남쪽과 서쪽 150m 위치를 각각 49개 지면 점과 29개 경로 점으로 검사했다.
- `JWJ_SouthRange`·`JWJ_WestRange`, 기존 중심 지역과 각각 연결하는 양방향 route, 두 신규 지역의 JYU GrassHabitat를 저장했다. 기존 두 지역의 토양을 보존했다. 1102의 스포너는 JYU `BP_JYU_VegetationField`를 참조하고 soil·무리 이주를 켠다. 네이티브 먹이 장부·이동·대사 권위는 기존 경로를 사용한다.
- 변경 파일은 `Content/JWJ/1102_Integration_JWJ.umap`, 이 레벨의 World Partition external Actor 패키지 8개(기존 2개 수정, 신규 6개), `Tools/Editor/setup_jwj_1102_food_grass.py`, `Tools/Editor/audit_vegetation_runtime.py`, 후속 계획서, PROGRESS다. 에셋 범위는 Git 상태로 확인했다. 새 레벨·게임모드·플레이어·JYU 에셋 변경 없음.
- `Saved/JWJFoodGrass_20261108/Apply.json`과 `ApplyRetry.log`에 검사·저장 기록이 있다. 앞선 시도들은 Python 프로퍼티 이름 오류로 저장에 도달하지 않았고 수정 후 저장했다. 별도 에디터 재로드에서 네 지역 모두 Native 단계가 진행했고 시작 개체는 지역별 사슴 12·늑대 4였다. 초기 12개 관측에서 4지역 FoodGrid/M4 잔량 차이 0, 각 지역 양수 ISM을 확인했고 플레이어 화면을 직접 확인했다.
- 계획 C의 기준선: `PIE_Camera_Runtime.json`의 초기 12개 표본에서 사슴 23개 ID가 표시 에너지 95 이상·실제 섭취 양수인 표본을 124회 남겼다. 예시 ID22는 E99.994/비축1/섭취0.002922였다. 같은 표본에서 늑대 영양 95 이상과 사냥 가능이 동시에 기록된 사례는 0이다. 이 시험으로 늑대 포만 문제를 재현했다고 해석하지 않는다.
- 첫 PIE 검사 종료 판정은 JYU 전용 테스트 카메라 호출과 Python 플레이어 바인딩 오류 때문에 실패했다. 정상 플레이어 카메라로 바꾼 별도 `CameraRetry.log` 실행에서 네 지역 방문·180도 회전·숨김 중 Native 진행·재표시를 판정한다. 이번 변경은 에셋/QA Python/문서이며 C++ 직접 빌드는 새로 실행하지 않았다.
- 최종 `PIE_CameraRetry_Runtime.json` 53초/27개 표본, FINISHED, 프로세스 종료0. 네 지역의 0°/180° 실제 카메라 방향과 양수 near ISM을 각각 관측했다. 풀을 숨긴 표본에서 네 지역 인스턴스가 모두0이고 Native step73→88로 진행했다. 복귀 표본은 네 지역 모두 양수였다. FoodGrid/M4 잔량 차이는 전체 108개 지역 표본에서0이며 네 지역 누적 섭취가 모두 양수였다. 첫 검사 오류를 해결했다.
- 후속 섭식 위치 감사에서 C4의 body 위치 셀 소비, 셀 폭400cm, Field의 ±168cm XY 후보 분산·잔량에 따른 후보 끝 번호 제거를 확인했다. 서버/Client가 개별 풀 위치를 다르게 가진다는 사실은 이번 감사로 확정하지 않았다. 서버 게시1초/표시0.25초의 시차와 Client 지면 재검사는 추가 진단 대상이다. 계획 B-2와 다음 재개 우선순위를 갱신했으며 이번에는 문서 변경만 수행했다.
- Python 구문 및 문서/스크립트 변경 형식 검사 통과. 현재 남은 항목은 포만 실행 구현, 1102 사슴 도착, 늑대 추적, 시야 후보 최적화 필요성 계측과 Dedicated·저장·패키지다.
