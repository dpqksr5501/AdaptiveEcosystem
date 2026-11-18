# 공유 풀 패치 S0 조사와 S1 첫 구현

2026-11-08. [개발 명세](FOOD_PATCH_GRAZING_IMPLEMENTATION_SPEC_20261108.md)의 첫 구현 단위다. 기준 branch `jwj-1024`, HEAD `395992ab`와 작업 전부터 존재한 미커밋 변경을 보존했다. 새 맵/풀 Actor/Entity/Smart Objects는 추가하지 않았다. **현재 소비는 기존 셀 단위다. S1 anchor를 패치별 섭식 완료로 설명하지 않는다.**

## 1. S0 Food/Capacity writer 조사

아래는 production Native 경로의 writer 목록이다. Golden fixture가 테스트 입력을 직접 만드는 경로와 JSON snapshot의 읽기 전용 출력은 별도다. cell 배열은 public이므로 S2에서는 이 목록을 거래 API로 바꾸고 추가 direct writer가 없는지 다시 검색해야 한다.

| 원인 | Source와 실제 함수 | 순서/장부 연결 | S2 변경 지점 |
|---|---|---|---|
| 초기 생성 | `AI/Policy/EcoWorldV3.h` `FFoodGrid::Build` | noise→blur→threshold capacity, obstacle capacity 조정, `Food=Cap`, cover/habitat, fields 계산 | 기존 난수 draw/초기 셀 총량 유지 후 고정 패치 배분 |
| obstacle 용량 | 같은 파일 `ApplyObstacleFood` | Build의 `Food=Cap` 이전. 4×4 표본 비율 | 초기 capacity 가중치에 반영, 중복 손실 금지 |
| shelter 용량/먹이 clamp | 같은 파일 `ApplyShelterFood` | `Cap0` 기준 새 Cap, `Food=min(Food,Cap)`, Regen 변경 | 패치 capacity 변경·초과량 제거를 같은 거래에서 처리 |
| shelter 런타임 등록/해제 | `AI/Policy/EcoPolicyV3IntegratedSubsystem.cpp` `RefreshRefuges` | 기존 Before/After 차이→`AdjustSpatialFoodHabitat` receipt. 제거 시 capacity 복구만 | 패치 배분이 receipt와 같은 경계에서 변경되어야 함 |
| 실제 섭식 | `EcoWorldV3.h` `Step` C4 | 이동 후 body cell에 Want 합산→cell별 min/demand 비율→Food 감소·Stats.FoodEaten·LastIntake/energy | S3 도착/lease 검증 후 목표 patch 단위 합산. body cell fallback 금지 |
| 재생/soil 성장·환경 손실 | 같은 파일 `FFoodGrid::Regrow`, `EcoVegetationV3::Advance` | C8에서 cell당 한 번. soil ON은 Loss/Growth 누적, OFF는 기존 regen 식 | 증가를 빈 용량 비례, 감소를 잔량 비례로 배분. 패치마다 모델 재실행 금지 |
| 개발용 가뭄 | `Mass/EcoHerdMigration.cpp` `ApplyFoodFractionForAudit` | 권위 receipt 승인 후 Food 각 셀 ×fraction. 선택적으로 Regen=0 | 같은 비율 손실을 패치에도 적용. 명시적 QA fixture로 기록 |
| checkpoint 저장/복원 | `Creature/Runtime/EcoEcosystemArchive.h` `Grid`/`World`, `EcoEcosystemCheckpoint.cpp` `Run` | v1 배열 직렬화·checksum/runtime hash·staging 검증 후 context 교체 | S5에 schema/version과 patch 분포 추가. 현재 S1 ON save/load는 명시적으로 거절 |
| M4 지역 장부 | `Ecology/EcologySpatialFood.cpp` `RegisterSpatialFood`, `CommitSpatialFood`, `AdjustSpatialFoodHabitat` | Native 총량을 승인하는 authority 장부. patch/native 값을 별도로 쓰지 않음 | 기존 receipt 보존, 새로운 두 번째 food writer 금지 |
| 일반 공급/고갈 이벤트 | `Ecology/EcologyResourceSimulation.cpp`, `RegisterSpatialFood` | SpatialFood 등록 시 충돌하는 pending 일반 공급/고갈/환경 이벤트를 거절. Native 공간 먹이 공급 API는 별도 미구현 | 기존 일반 이벤트가 패치 공급까지 지원한다고 가정하지 말 것 |

기후 debug는 `AEcologyRegion`→환경 adapter→VegetationWeather 입력을 바꾸며 Food를 직접 쓰지 않는다. Field/ISM/CaptureDiagnostics는 읽기 전용이다.

실행 순서는 Native A/B 관측/정책/세계 반사→`FStepHooks::HerbControl`(기존 Social/Travel 훅)→C1 단일 Native 이동→`HerbMove` 실제 지면 제약→위협 이동/포획 후보→C4 소비/대사→C5/C6 생명주기→C8 재생→관측 갱신→`CommitSpatialFood`다. Field는 Mass processing 밖 GT에서 지면 snapshot과 표현 DTO를 게시한다. S1은 이 순서를 변경하지 않았다.

## 2. S0 로컬 비용 기준선

`Saved/FoodPatchGrazing_20261108_S0/PIE_Runtime.json`, `ProfileSummary.json`, `PIE.log`, `Saved/Profiling/CSV/EcosystemLife_FoodPatchGrazing_20261108_S0_PIE.csv`에 원본을 보관했다. 새 C++ 구현 전 실행한 seed23/기존 1102 저장본/4지역/사슴48·늑대16/1280×720/D3D11/65초 Editor PIE다. 실제 CSV 59.987초, 3159frames. CPU Ryzen 5 9600X, GPU RTX3060, UE5.8.3. 보고서 모든 기존 gate 통과, M4 차이 ≤1e-6.

| 항목 | 실측 |
|---|---:|
| RefreshVisuals active frame p95 / max | 1.5756 / 2.6572ms |
| GatherGround all frame p95 / max | 0.1339 / 0.2739ms |
| PublishCells active frame p95 / max | 0.1610 / 0.1776ms |
| FrameTime p95 / max | 20.9698 / 48.6682ms |
| 후보 trace 합산 max/frame | 146회 (기존 각 Field 예산의 합. 신규 World96 예산과 구별) |
| 표시 instance peak | 3279 |
| FoodGrid buffer 총 peak | 556352bytes |
| visual DTO / render cache / cell ground cache 총 peak | 95136 / 374224 / 191232bytes |

Native step 시간과 frame time은 별개다. 이 표는 한 seed의 짧은 로컬 기준선이며 정식 warmup30+측정180초×3seed, GPU/ISM 전체 메모리, socket/serializer 대조, 30분 soak를 대체하지 않는다. 기존 다른 맵의 네트워크 숫자를 1102 기준선으로 재사용하지 않았다. 새로운 A/B 비용은 검증 후 아래에 추가한다.

## 3. S1 구현과 사용법

- `Core/EcoFoodPatchLayout.h/.cpp`: descriptor, `(RegionId, Epoch, Cell, Candidate)` ID, 순수 고정 XY/yaw 함수, 상대좌표/normal/revision 연속 배열. 기존 CRC/hash/RandomStream 순서와 float 할당을 유지한다. 설정 hash·버전·범위를 검사하고 같은 descriptor는 재생성하지 않는다. 다른 배치는 증가한 epoch만 허용한다.
- 기존 `FEcoV3RegionContext::FoodPatchCache`가 authority static snapshot을 소유한다. 카메라/표시 OFF/Field render cache 정리는 Native cache를 지우지 않는다. 아직 Food/Capacity 배열이나 예약은 없다.
- 기존 Field에 `eco.Grass.PatchLayout`(기본0) / BP 기본 설정 `bEnablePatchLayout`을 추가했다. **Play 전에** 켜면 S1 authority anchor만 사용한다. 1102 에셋의 기본값은 바꾸지 않았다.
- 지면 trace는 GT에서 네 지역이 공통 World96회/frame을 사용한다. 각 Field의 cell12+patch12 slice를 사용하며 스캔도128개/frame으로 제한한다. 정상 지면은 재검사하지 않고 실패 지면만 다음 sweep에 재시도한다. 정적 지형 변경은 authority `InvalidatePatchGround`로 즉시 표시 무효화→재검사한다. 자동 World Partition 충돌 제거 감지/이동 지형은 아직 지원하지 않는다.
- 기존 Field의 추가 FastArray에 cell별 완결된 authority ground snapshot/epoch/hash/revision/valid mask를 전달한다. 첫 멀티 시험에서 원시 FVector 배열의 초기 bunch가171180~176424bytes로65536 상한을 초과해 실패했다. 현재 XY를 공통 배치에서 재구성하고 높이는 cell 최솟값+가변 bit 차이의1cm code로 보낸다. normal은 Native authority cache에 유지하며 S1 wire에는 보내지 않는다. Client는 descriptor와 cell이 맞을 때만 표시하고 독립 지면 trace로 anchor를 바꾸지 않는다. 처음 descriptor 판정이 도착하기 전 표시를 보류한다. 개별 패치 잔량 복제·전체 snapshot staging·손실 시험은 S4 범위다.
- S1 실제 Field opt-in은1~9후보만 지원한다.10~25는 명시적 오류로 거절한다. 공통 생성기/Native cache/wire 단위 테스트는25까지 검사하지만25후보의 전체 초기 snapshot을 전송 완료로 확대하지 않는다. S4에서 패킷 예산/staging을 확장한 뒤 통합 상한을 올린다.
- 기존 OFF 표현도 같은 순수 함수 결과를 local cell cache에 보관한다. 카메라 이탈 시 local cache를 정리한다. Gameplay patch count는 첫 context 초기화 때 고정하며 이후 CandidatesPerCell 편집/LOD와 분리한다.
- `CaptureDiagnostics`에 allocated bytes, layout epoch/hash/count, 지면 준비 수/checksum, World trace 수, 렌더 anchor 오차를 추가했다. 상세 캡처에 실제 render anchor 목록을 포함한다. 기존 feeding audit는 body→실제 보이는 anchor XY 거리를 기록한다. 아직 mouth/arrival 판정이 아니므로 이 거리만으로 F01~F03 통과/실패를 선언하지 않는다.

기본OFF 경로는 기존 소비·모델·이동 writer를 보존한다. ON도 아직 셀 소비이므로 화면상 섭식 일치 기능의 제품 사용은 S2/S3 이후다. 체크포인트는 schema 추가 전 S1 ON save/load를 거절해 미지원 복원이 조용히 일부만 적용되지 않게 했다.

## 4. 검증과 다음 작업

직접 `UnrealBuildTool.exe AdaptiveEcosystemEditor Win64 Development` 성공. 초기 추가4개+기존10개 식생 자동화14개 전부 Success, warning/failure/notRun0. Golden literal3개와 기존 생성식225후보 대조,8100패치 서버/Client parity·지면 확인/무효화·이전 epoch/설정 hash 거절·World trace96 상한·실제 ISM authority anchor/지면 snapshot 미수신/잘린 cell/렌더 옵션 변경을 검증했다. 증거: `Saved/FoodPatchGrazing_20261108_S0/S1_Automation/index.json`, `S1_Build.log`, 후속 계측 빌드 로그. 후속 wire 자동화의 첫 실패는 의도적으로 잘린 FBitReader의 엔진 ensure를 예상 오류로 등록하지 않은 테스트 harness 문제였다. overflow를 예상 오류1개로 명시 검증하도록 수정했고 결과/실패 로그를 보존한다. 최신 runtime/네트워크 결과는 실행 완료 후 갱신한다.

첫 S1 로컬 실행 `FoodPatchGrazing_20261108_S1Profile`은65초/CSV59.983초/3163frames, M4/기존 gate 통과다.32,400패치 중32,399 지면 유효, 미확인1개는 보류하며 먹이 총량은 보존했다. Native static record36bytes/전체1,166,400bytes, ground DTO 컨테이너1,846,784bytes, local layout sample cache239,084bytes를 관찰했다. 전체 allocator/replication history/ISM/GPU 메모리는 아니다. RefreshVisuals active p95=1.9033ms로 기존1.5756ms보다 늘어 반복 descriptor hash 검증을 hot loop 밖으로 옮겼다. 이 첫 실행 CSV 종료 중 일시적 Windows writer file lock traceback이 있었지만 뒤에 flush/정상 종료/완성 footer를 확인했다. 감사 도구가 그 잠금을 같은 deadline 내 pending read로 처리하도록 수정했다. 수정 후 최종 비용은 재측정한다.

1102 셀 소비 네트워크 기준 `FoodPatchGrazing_20261108_NetA`는 Dedicated/Client2/late join/동시28.109초, Client 권위0·네 Field 수신을 확인했다. 원래 legacy3지역 카메라 순회/출생 개체 수신 gate는 실패해 `Relevance_LegacyGate.json`에 보존했다. 별도 `--food-patch` 검수는 모든 지역 Field delivery/권위0와 anchor를 검사하며 원래 life/카메라 gate를 대체 완료로 설명하지 않는다. nprof 종료 후 이어진 writer 로그를 명시적인 profile stop event에서 구분해 재대조했으며 각 연결의 uint16 wrap/전체 이벤트 순서가 일치했다. 연결 평균 socket18,001.16/16,954.39bytes/s, VisualGrid payload 환산13,078.43/12,925.19bytes/s다. 이는 raw socket 송신과 순수 필드 payload의 다른 계층이다. packet capture/전체 연결 메모리는 미측정이다.

다음은 S2다. 조사한 모든 writer를 같은 셀/패치 transaction으로 바꾸고 conservation/경계값/OFF golden부터 통과시킨다. 이어 S3의 stable owner/generation lease·접근 슬롯·이동 후 mouth 도착 판정·목표 패치 C4 소비를 연결한다. 그 전 새 설정을 1102 저장 에셋에 켜거나 기존 소비를 패치 소비로 설명하지 않는다. S4 잔량/활동 PatchId 표현·복제, S5 저장/기존 HUD 연결, S6 정식 A/B·F01~F12는 미완료다.

## 5. 최종 첫 구현 검증 (22:48 KST)

- 직접 Editor UBT 최종 성공: `FoodPatchGrazing_20261108_S0/S1_CompactBuild.log`, `S1_WireTestBuild.log`. 최종 식생15개 Success, 경고/실패/notRun0: `S1_WireAutomation/index.json`.1/9/25개 cell wire round-trip,1cm 높이 오차≤0.5cm·잘린 bitstream의 예상 오류 거절을 포함한다. 이전 실패는 `S1_FinalAutomation`에 남겼다.
- 최종1102 S1 opt-in65초/CSV59.979초/3225frames 정상 종료: `FoodPatchGrazing_20261108_S1Final`. RefreshVisuals active p95/max1.5782/1.9646ms, frame p95/max19.9828/26.9318ms. 이전1.5756ms 대비+0.165%로 단일 짧은 실행에서는 개선/악화를 확정하지 않는다. Ground trace는 cell48+patch48 합산 상한96/frame. M4 오차 gate 통과. Native static1,166,400bytes, ground DTO1,883,232bytes, local layout cache239,084bytes. 동적 FoodGrid 버퍼556,352bytes와 분리한 컨테이너 비용이며 전체 메모리는 아니다.
- 압축 수정 후 Dedicated+Client2/95초 late join: `FoodPatchGrazing_20261108_NetCompact`, 모든 프로세스0, observer FINISHED, 근거리97/9표본 누락0, 동시28.109초. 두 Client에서 네 지역의 epoch/hash/valid-mask/1cm anchor code checksum이 서버 snapshot과 일치했고 수신 anchor 대비 렌더 오차>2cm 표본0, Client 논리개체/Native Step0. 실제 mouth나 Food 배분 일치의 F09 완료는 아니다.
- 추가 ground DTO 최대 실제 property payload152816bits=19102bytes(FFastArray support bit 포함). 최초 snapshot/관련성 재진입만 전송되고 이 실행의 steady ground delta는0이었다. 각 연결 실제 ground payload 총1,644,895/896,340bits, writer 이벤트11/6개는 nprof uint16 wrap·순서와 모두 일치했다. 기존 VisualGrid payload 환산13,127.61/13,741.42bytes/s, 전체 socket 평균20,042.65/21,260.50bytes/s. 초기 전송과 steady를 섞은 평균이므로 정식 steady1.5배 예산 통과로 선언하지 않는다.
- 별도 기존 셀 소비45초/기후·먹이 직접 쓰기 없음: `FoodPatchGrazing_20261108_S0Location` 정상 종료. 같은 Native/게시 step25회, source cell10437, intake184표본, 실제 렌더와 대조된165표본. body→현재 보이는 가장 가까운 anchor XY 거리 중앙값147.26cm/p95=240.80cm/max4275.16cm. 전체 Field의 현재 표시 후보를 기준으로 하므로 LOD/시야 밖/지면 지연·비표시 후보가 섞일 수 있다. 이 거리를 실제 mouth/식용 footprint 거리나 잘못된 소비 횟수로 해석하지 않는다. 원본 위치·후보 ID가 feeding JSON에 남는다.

통합 기계 판독 결과는 `Saved/FoodPatchGrazing_20261108_Start/Manifest.json`이다. `evidence_checks_passed=true`, `formal_budget_qualified=false`이며 F01~F12는 전부 완료하지 않은 상태로 남겼다. 같은 맵/seed/해상도의 초기 비교지만 full grazing B/C/D,3seed·180초 측정,30분 soak, 저장/기존 HUD/입 애니메이션/Game·패키지 회귀는 남는다.

재현은 기존 `test_vegetation_network.ps1`의 `-Map /Game/JWJ/1102_Integration_JWJ -AuthoredWeather -DeerPerRegion 12 -PatchLayout -FoodPatchCheck -NetworkProfile`을 사용한다. `-FoodPatchCheck`는 풀 전용 검수이며 legacy life/카메라 검수는 그대로 별도다. 로컬은 `test_food_patch_layout.ps1 -Mode Profile -Duration 65 -PatchLayout -AuditFolder <새 폴더>` 또는 `-Mode Feeding -Duration 45`다. 폴더는 새 이름을 쓰며 실행 중인 엔진/빌드를 중단하거나 겹쳐 실행하지 않는다. 요약기는 `summarize_food_patch_start.py`이고 상세 인자는 `--help`로 확인한다.
