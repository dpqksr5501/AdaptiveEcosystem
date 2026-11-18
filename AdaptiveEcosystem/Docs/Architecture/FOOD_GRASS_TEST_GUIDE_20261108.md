# 먹이와 풀 연결 — 기존 맵 테스트 안내

## 실행

기존 `/Game/JYU/Maps/LV_JYU_Ecosystem`을 열고 Standalone Play를 시작한다. 이 맵의 기존 식생 설정은 토양과 풀을 함께 사용한다. 기존 검사 HUD가 있는 화면에서 **Alt+G**로 식생 패널을 연다.

| 조작 | 결과 |
|---|---|
| Alt+1 | 현재 수신된 지역을 순서대로 선택 |
| Alt+2 | 선택 지역에 건조 프리셋 적용 |
| Alt+3 | 선택 지역에 회복 강수 프리셋 적용 |
| Alt+4 | 선택 지역의 수동 기후·수원 상태를 해제하고 자동 환경 사용 |
| Alt+5 | 선택 지역 진단을 `Saved/FoodGrass/`에 JSON으로 저장 |

패널의 권위 화면에서 먹이 현재량/용량, 소비, 성장, 환경 손실, 수지 오차, 적용된 강수·기온과 수분을 확인한다. 수분과 먹이는 시뮬레이션 시간에 따라 바뀐다. 건조·회복 조작은 실제 환경 입력만 바꾼다. 처음 상태에서 비교하려면 Play를 재시작한다.

## 단계별 확인

1. **환경** — 지역 선택 후 Alt+2, Alt+3을 누른다. Manual과 강수/기온이 바뀌는지, Alt+4로 Auto가 돌아오는지 확인한다. 다른 지역에 Manual 표시가 생기면 실패다.
2. **표현 분리** — 콘솔에서 `eco.Grass.Visual 0`, 이후 `eco.Grass.Visual 1`을 실행한다. 풀 외형은 숨었다 돌아오고 패널의 먹이와 토양은 계속 갱신된다.
3. **풀 위치** — 같은 풀밭을 떠났다가 돌아온다. 보이는 후보 수는 잔량과 거리에 따라 달라지고 같은 후보의 XY 위치는 유지된다. 건물/바위 등 제외 표면은 Field BP의 trace 채널과 맵 충돌 설정으로 확인한다.
4. **수원** — 권위 콘솔에서 `eco.Grass.Water <지역> 0`과 `eco.Grass.Water <지역> 1`을 순서대로 실행한다. 기존 연결 수원이 있는 지역에서 지면 갱신 후 패널의 Wet cells가 달라지는지 확인한다. 특정 수원만 선택하려면 지역과 0/1 사이에 해당 Habitat Actor 이름을 넣는다.
5. **고갈과 회복** — Alt+2로 건조 상태를 유지한 뒤 Alt+3으로 전환한다. 수분·먹이와 풀 크기를 같은 구역에서 비교한다. 변화 속도는 초기 수분, 배수, 수원, 섭식에 따라 달라진다. 먹기 애니메이션과 별도로 소비 누적을 확인한다.
6. **멀티** — Dedicated 서버에서 콘솔로 환경을 변경한다. Client 패널은 수신 셀/인스턴스만 보여준다. 늦게 접속한 Client와 지역을 다시 방문한 Client에서 최신 풀이 나타나는지 확인한다.

## 기존 레벨에 설정

기존 Integrated Native V3 spawner의 **Enable Food Grass**로 먹이 표시를 켤 수 있다. 임시 시험은 Play 전에 `eco.Grass.Enable 1`을 설정한다. 토양도 시험하려면 해당 spawner의 기존 **Enable Vegetation**을 사용하거나 Play 전에 `eco.Vegetation 1`을 설정한다.

기존 `Vegetation Field Class`의 클래스 기본값에서 풀 메시/재질, 셀당 후보 수, 상세 표시 반경, 지면 trace 채널과 경사 기준, 조회 예산을 조절한다. 프리셋 강수·기온은 기존 Inspector HUD 클래스의 Grass Debug 기본값이다.

## 콘솔로 시험

- `eco.Grass.Climate <지역> <강수 0..1> <기온 °C>` — 선택 지역의 적용 기후 조작.
- `eco.Grass.Auto <지역>` — 수동 상태 해제. 생태 상태는 현재 시점부터 계속 진행.
- `eco.Grass.Export <지역>` — 먹이/토양 진단 저장.
- `eco.Grass.Visual 0/1` — 로컬 외형 표시 설정.

기존 `Tools/Editor/audit_vegetation_runtime.py`에 `-VegetationGrassDebug` 모드가 있다. 기존 맵에서 Dry → Rain → Auto, 다른 지역 격리, FoodGrid와 장부 일치를 확인한다. 개발·실행 검증 상태는 [구현 계획의 결과 기록](FOOD_GRASS_IMPLEMENTATION_PLAN_20261108.md)을 따른다.

## 2026-11-08 확인한 시험 결과

기존 맵 seed23에서 건조24초 동안 선택 지역 수분은 약0.499→0.379, food는125.73→110.43으로 변했다. 다음 회복 강수 구간에서는 수분 약0.370→0.433, food110.02→119.44를 관찰했다. 실제 동물이 있는 개발 시험이므로 모든 셀에서 같은 변화량을 기대하지 않는다. 처음 확인할 때 각 프리셋을 약30초 유지하고 선택한 셀의 수분·소비·성장을 함께 본다.

- `-VegetationGrassVisualCheck`로 표시 OFF/ON 중 Native 진행과 풀 복귀를 검사했다.
- `-VegetationGrassWaterCheck`로 기존 Forest 수원 OFF에서 공급 셀0, ON에서9를 확인했다.
- `-VegetationGrassSoilOff -VegetationPIE -VegetationAuthored -VegetationGrassVisualCheck`로 기존 맵40초 시험을 통과했다. 이 QA 모드는 기존 spawner의 토양 설정을 메모리에서 끄고 먹이 표시를 켜며, 종료 시 원래 값으로 복구한다. GrassDebug/WaterCheck/EcoVegetation 인수와 함께 사용하면 시작 검증에서 거절한다.
- `test_vegetation_network.ps1`의 로컬 검사는 `-nosteam`과 현재 접속 프로토콜을 사용한다.
- 자연 출생 개체까지 넓게 관찰할 QA에서는 `-ClientVisualDistanceCm 20000`을 명시한다. 현재 기본 표시 거리1000cm로 시험한 결과와 구분해서 기록한다.
- 기존 맵/메시/재질의 옛 경로는 정확한 package redirect로 현재 에셋에 연결했다. 회색 불투명 판처럼 그려지던 풀의 alpha와 색이 복구됐다.

진행 중인 패키지 및 남은 검증은 [루트 진행 기록](../../../PROGRESS.md)에 갱신한다.

먹이 표현의 수치 경계는 `AdaptiveEcosystem.Vegetation.GrassAmountEncoding`으로 확인한다. Publisher와 renderer가 실제 사용하는 코드에서 0/양의 미세 잔량/용량0, 음수·NaN·무한대, 16bit 포화·단조성·오차 한 단위 이내를 검사한다. 2026-11-08 11:13 기준 이 검사를 포함한 식생8개 회귀가 통과했다.

지면 재시도 예산의 공정성은 `AdaptiveEcosystem.Vegetation.GrassGroundRefreshFairness`로 확인한다. 실패/성공 재시도가 섞인1200개 후보를 회당24개씩 처리할 때 오래 대기한 뒤쪽 후보도 검사받는지 확인한다. 11:44 기준 식생9개 회귀와 기존 맵40초 표시 숨김·복귀 시험이 통과했다. 실제 지형 스트리밍 제거/복귀 장면 검증은 진행 기록의 남은 작업에 포함한다.

`AdaptiveEcosystem.Vegetation.GrassVisualLifecycle`은 실제 엔진 바닥 충돌과 기존 Field/ISM을 사용한다. 표현 DTO의 먹이 감소→0 제거→미세 잔량→회복, 시야 거리 이탈/복귀, 지면 충돌 제거/복귀, anchor 변경 대기, 후보 위치·유지된 인스턴스 ID를 확인한다. 12:15 기준 식생10개 회귀가 모두 통과했다. 실제 Native 섭식이나 World Partition unload를 실행한 시험과는 범위가 다르다.

기존 `audit_vegetation_runtime.py`의 `-VegetationPIE -VegetationAuthored -VegetationGrassFeedingCheck -VegetationMap=LV_JYU_Ecosystem -VegetationAuditDuration=45`는 실제 섭식과 표현을 대조하는 선택 시험이다. `-VegetationGrassRegion=<RegionId>`로 대상 지역을 지정할 수 있다(기본 Forest). 진단의 `native_step`과 `published_native_step`이 같은 표본에서 Native 먹이/용량의 정량화 코드와 셀 DTO가 일치하는지 검사한다. 같은 step에 `last_intake>0`인 개체의 셀을 추적하여, 이후 로컬 갱신에서 해당 DTO 코드가 실제 ISM에 반영됐는지 별도로 검사한다. 먹이/동물/정책을 직접 변경하지 않는다.

결과는 지정한 Saved 감사 폴더의 `PIE_Feeding.json`과 `PIE_Runtime.json`에 남는다. `visual_samples`는 상세 진단(`CaptureDiagnostics(true)`/기존 Export)에서만 생성하며 Client에는 권위 Native step을 추가 전송하지 않는다. 현재 source와 과거 DTO의 차이를 오류로 오해하지 않도록 step이 다른 표본은 동기 비교에서 제외한다. 순 먹이 변화에는 섭식과 환경 손실/성장이 함께 포함되므로 `changes`만으로 섭식량을 추정하지 않는다. 이 계측 모드의 빈번한 상세 조회는 성능 벤치마크로 사용하지 않는다.

16:37 기준 `Saved/FoodGrass_20261108_FeedingRetry`의45초 시험이 FINISHED/프로세스0으로 통과했다. Forest에서 동기30시점/13976셀 코드가 일치했고 실제 섭식1006관측, 같은 코드의 ISM913관측(194고유 셀)을 확인했다. 셀44의 먹이0.398→0.085에서 실제 풀4→1을 확인했다. 순 감소247건/증가412건은 성장·환경 손실도 포함한 표본 변화이며 순수 섭식량이나 완전0 고갈 증거로 확대하지 않는다. 첫 실행은 맵 인수를 빠뜨려 초기화 deadline으로 실패했으며 해당 로그도 보존했다.

성능 계측은 같은 감사 도구에 `-VegetationPIE -VegetationAuthored -VegetationGrassProfile -VegetationMap=LV_JYU_Ecosystem -VegetationAuditDuration=65 -VegetationAuditFolder=<결과폴더>`를 지정한다. 상세 개체/셀 조회와 고해상도 캡처는 제외하고, 시작5초 이후 CSV를 기록한다. 종료 시 CSV 저장 완료를 기다리며30초 안에 완성되지 않으면 실패로 기록한다. 기존 맵/에셋을 저장하지 않는다.

실행 후 프로젝트 폴더에서 `python Tools/Editor/summarize_vegetation_evidence.py --grass-profile <결과폴더>`로 `Saved/<결과폴더>/ProfileSummary.json`을 생성한다. 잘린 CSV는 거절하며, UE가 마지막에 기록하는 최종 header로 가변 열을 해석한다. `EcoGrass/GameThread/RefreshVisuals`, `GatherGround`, `PublishCells`는 모든 Field를 합한 프레임당 CPU 시간(ms), `EcoGrass/CandidateTraces`는 후보 지면 조회 횟수다. `active_frames`는0인 프레임을 제외한다. 후보 수/조회 수 상한, 먹이 장부 일치, 상세 dump/캡처 제외도 검사한다.

컨테이너 메모리 수치는 실제 배열/map의 할당량과 Native FoodGrid의 보조 버퍼를 포함한다. 공유 메시/재질, allocator 부가비용, ISM CPU/render/GPU 버퍼, 연결별 복제 버퍼까지 합친 전체 메모리가 아니다. 이 실행은 한 관찰자의 Standalone Editor PIE 기준선이며, 실제 통신량·World Partition unload·다중 Client 성능이나 배포 환경의 고정 프레임 예산을 검증하지 않는다. CSV의 시스템 해상도와 별도 PIE viewport의 실제 해상도도 구분한다.

17:07 기준 `FoodGrass_20261108_ProfileComplete`는65초 Play/CSV 저장/프로세스0/요약 검사 모두 통과했다. CSV59.985초/6583frame, Ryzen5 9600X·RTX3060·D3D11·시스템1280×720 조건이다(별도 PIE viewport 해상도 미계측). 세 지역 합산 RefreshVisuals 실행 프레임 p95/max는1.3486/2.0671ms, PublishCells는0.0893/0.1195ms였다. 전체 Editor FrameTime p95/max10.3979/28.6024ms를 식생 비용 자체와 구분한다. 후보trace max117은 합산 설정 상한288 이내, 총 인스턴스 표본 최대2290개였다. DTO/후보/지면/흔적 컨테이너 할당량 합산 표본 최대494624bytes, Native FoodGrid 버퍼417264bytes다. 앞선 Profile은 잘린 CSV, ProfileRetry는 종료 판정 오류로 최종 통과에서 제외했다.

실제 스트리밍·반복 방문은 기존 `Tools/Editor/test_vegetation_network.ps1`의 선택적 `-GrassTravelCheck -TravelDuration 380`을 사용한다. 예시 실행 인수는 `-Map /Game/JYU/Maps/LV_JYU_Ecosystem -AuthoredWeather -Duration 430 -ExitAfter 480 -ClientAAt 30 -ClientBAt 95 -OverlapClients -ClientVisualDistanceCm 20000 -AuditFolder <결과폴더>`다. 기존 권위 observer fixture의12초 간격 세 지역 순환을 유지하고 ClientA를380초 관찰하며, ClientB는 기존 짧은 late join 시험을 수행한다. 저장된 맵과 기본 표현 거리는 바꾸지 않는다.

Client 보고서의 `grass_travel`은 실제 LandscapeStreamingProxy 이름 집합의 추가/제거, World Partition 완료 상태, near/coarse 인스턴스, 후보 캐시 상한과 지역 방문을 기록한다. 최종 `Relevance.json`은2초 이상 머문 방문을 세어 각 지역10회 이상과 각 방문에서 streaming 완료 후 근거리 풀이 나타났는지도 검사한다. 짧은 좌표 흔들림을 여러 번 방문한 것으로 세지 않는다. 서버 habitat streaming source는 유지하고 Client에서 논리 개체·Native step을 실행하지 않는 기존 검사를 함께 수행한다.

이 시험의 near/coarse 계수는 기본 후보9에서 실제 인스턴스의 detail 배율1/확대 배율을 구분한다. 후보 수를1로 바꾸면 두 표현의 배율이 같아 coarse 계수가0일 수 있으므로, 기본 설정의 거리별 표현 acceptance와 구분한다.

`PrepareCopiedWorld`의 Editor 준비 경로는 넓은 범위의 셀을 로드한다. 이 경로의 단독 PIE를 실제 지형 unload 근거로 사용하지 않는다. LandscapeStreamingProxy 집합 변화는 실제 지형 Actor의 로드/해제 증거이며, 모든 지형 종류·GPU LOD·충돌 지연 조건 전체를 검증했다는 뜻은 아니다.

17:39 기준 `Saved/FoodGrass_20261108_Travel`의 장기 시험은 종합 passed=true, 서버와 두 Client 모두 종료0이다. ClientA380.5초/381표본에서2초 이상 안정 방문 Forest11/Barren10/Highland11회, 모든 방문의 streaming 완료 후 근거리 풀 표시를 확인했다. 실제 proxy 집합 추가316/제거321건(동시 로드29~44개), near/coarse와 캐시 상한도 통과했다. 후보 최대는 Forest1510≤4329, Barren1263≤3906, Highland776≤3177이었다. 두 Client의 논리 개체/Native step은0, 근거리509/30표본 누락0, 동시 관찰28.344초, late join 자식159의 scale 수신 검사도 통과했다. 서버212표본의 FoodGrid/M4 차이는0이다. 이는 개발 observer fixture와 QA 표현 거리20000cm의 결과이며 일반 플레이 장기 균형이나 전체 메모리 누수 검증으로 확대하지 않는다.

정확한0 고갈/회복 시험은 기존 runtime 감사 도구에 `-VegetationPIE -VegetationGrassDepletionCheck -VegetationGrassRegion=Forest -VegetationGrassDryTemperature=50 -VegetationAuditDuration=120 -VegetationMap=LV_JYU_Ecosystem -VegetationAuditFolder=<결과폴더>`를 지정한다. 이 선택 모드는 Dry(0강수/50℃)48초 → Rain(0.5강수/20℃)48초 → Auto24초로 기존 명령만 실행한다. 상세 Native/DTO 동기 표본과 실제 ISM에서 **양수·표시 → 정확한0·제거 → 같은 셀의 양수·표시 복귀**를 기록하고 `PIE_Depletion.json`과 최종 `PIE_Runtime.json`으로 판정한다. Profile/Feeding/Water/표시 토글 시험과는 함께 사용하지 않는다.

수동 확인은 `eco.Grass.Climate Forest 0 50`, 약48초 뒤 `eco.Grass.Climate Forest .5 20`, 이후 `eco.Grass.Auto Forest` 순서다. 50℃는 기존 TempSuit를0으로 만들어 성장을 멈추고 실제 동물 섭식으로 정확한0에 도달하는지 확인하는 명시적 디버그 조건이다. 환경 손실 자체는 지수 비율이므로 짧은 가뭄만으로 모든 셀이 정확히0이 되지는 않는다. 기본 HUD Dry 프리셋과 일반 GrassDebug는 계속30℃이며 모델·저장된 기후·먹이량을 직접 변경하지 않는다. 실제 섭식 위치와 관찰 범위에 따라 확인되는 셀 수는 달라질 수 있다.

18:02 기준 `Saved/FoodGrass_20261108_Depletion`의120초 시험은 FINISHED/오류 없음/프로세스0이다. 양수 먹이와 실제 풀을 관찰한456셀 중236셀에서 정확한0/인스턴스0을 확인했고, Rain 구간에 같은236셀의 먹이·ISM이 복귀했다. Native/DTO 동기84시점, FoodGrid/M4 오차0, 선택 지역 기후 적용·다른 지역 수동 override 격리·Auto 해제도 통과했다. 예를 들어 셀0은 food0.486577/풀1 → food0/풀0(32.703초) → food0.008796/풀1(49.984초)이었다. Dry/Rain 캡처에서 정상 지면·재질 표현도 직접 확인했다. 화면에 남는 기존 장식/은신처 풀까지 먹이 잔량이라고 해석하지 않도록 기존 HUD 조준 셀 진단을 함께 사용한다.

전송량 계측은 기존 네트워크 runner에 `-NetworkProfile`을 추가한다. 예시: `-Map /Game/JYU/Maps/LV_JYU_Ecosystem -AuthoredWeather -Duration 145 -ExitAfter 185 -ClientAAt 30 -ClientBAt 95 -OverlapClients -ClientVisualDistanceCm 20000 -AuditFolder <결과폴더> -NetworkProfile`. 기존 엔진의 `netprofile enable/disable`과 기본OFF인 `eco.Grass.NetAudit 1`로 소켓 송신·실제 VisualGrid writer bits·최신 base state 동적 메모리를 같은 실행에서 기록한다. 게임 종료 뒤 프로젝트 폴더에서 `python Tools/Editor/summarize_vegetation_evidence.py --grass-network <결과폴더>`를 실행하면 `NetworkProfileSummary.json`이 생성된다.

분석기는 설치된 UE5.8 nprof v14와 단일 VisualGrid struct의 프로토콜을 따른다. 끝 marker·연결·Actor initial/delta와 실제 serializer 이벤트 순서를 확인한다. 엔진의 property NumBits는16비트여서 큰 VisualGrid가 wrap된다. 따라서 원시 `raw_u16_bits`를 실제 풀 크기로 사용하지 않고, writer의64비트 차이와 엔진이 struct 앞에 쓰는 지원 bit1개를 합산한다. 각 이벤트의16비트 나머지가 nprof와 순서까지 일치하는지 검사한다. 일반 shared 속성은 기록의 연결 정보가 생략될 수 있어 Field별 비용으로 귀속하지 않고, 명시적 연결이 있는 VisualGrid만 집계한다.

소켓 bytes는 모든 Actor·RPC·프로토콜을 포함한 서버 송신 payload다. IP/UDP/link 헤더까지의 패킷 캡처 수치는 아니다. VisualGrid payload bits는 패킷 합치기 전 셀 데이터이며 공유 header·재전송·packet-handler 비용을 포함하지 않는다. `newest_base_dynamic_peak_by_region`은 최신 base state의 동적 컨테이너만 세고 object 자체·ACK/history 보관·채널·shared shadow·allocator 부가비용은 포함하지 않는다.

18:44 기준 `Saved/FoodGrass_20261108_NetAudit`의 종합 실행·요약은 passed=true이며 모든 프로세스가 정상 종료했다. nprof147.675초/4369frame에서 두 연결의 소켓 송신3,414,359/940,211bytes(평균32.26/29.84kB/s), VisualGrid 실제 payload20,596,961/5,880,090bits(활성 기간 환산24.32/23.33kB/s)를 구분했다. 초기/델타 단일 업데이트 실제 최대121341bits로, 원시16bit counter55805bits를 그대로 사용하면 과소 집계된다. 실제190/55이벤트 전체의 나머지와 순서가 nprof와 일치했다. 최신 base 동적 메모리 peak는 Forest10416/Barren10416/Highland7680bytes다. 근거리136/29표본 누락0, late join 자식157/159 수신·BodyScale 일치와 FoodGrid/M4 오차0도 확인했다. 이 로컬2 Client 장면의 기준선이며 고정 운영 예산이나 delta가 항상 일부 셀만 변경된다는 보장이 아니다.
