# Soil-v1 수분·식생·기존 자원 연결

전체 상태와 남은 B–G 기능: [구현 상태표](ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md). 이는 opt-in Native 세계 확장이며 PPO가 새 수분 세계를 학습했다는 의미가 아니다.

## 실행 경계

`AEcologyRegion::GetEnvironmentState` → GT Integrated Step 직전 Rainfall/Temperature/Native Dark snapshot → `FFoodGrid::Regrow`의 soil-v1 → 같은 셀 Food → 기존 food blur/gradient·PPO 관측 0·다음 실제 조향/섭식 → `CommitSpatialFood` → M4 FoodAmount·shortage/인구·기존 Summary. Raw Request·18관측/5행동·mask2와 V1은 그대로다. Native가 환경 갱신과 먹이 잔량을 소유하고 M4는 동일 결과 거래를 검증한다. M4의 지역 재생은 SpatialFood 등록 지역에서 기존처럼 제외한다.

순서: 기존 C4 실제 경합 섭식·에너지 → C8 수분/환경 손실/성장 → 관측 → 완료 receipt. 단위는 기존 food 단위, 수분/강수/차폐/침수는 0..1, 기온 ℃, 시간 Native 2/15 simulation seconds, 지면 위치 cm다. 긴 dt>0.25/NaN/미지원 plant는 거절하며 프레임 hitch의 wall time으로 여러 시간을 한 번에 적용하지 않는다.

수분은 강수 침투 + 명시적으로 연결된 수원 + 침수 − 기온/일조/그늘의 증발 − 배수 − 식생 소비다. Grass/Riparian/Shrub의 최적 구간과 침수 내성이 다르다. 현재량=0인 셀도 capacity gap을 통해 회복할 수 있다. capacity는 기존 장애물·은신처 규칙의 값이며 수분 모델이 별도 capacity/먹이 잔고를 만들지 않는다. 안정 ID는 RegionId+row-major cell index이며 grid 크기는 한 session 동안 고정이다.

`Before - Consumed + Regenerated - EnvironmentLost = After`. 환경 손실은 비음수 별도 항목이다. 기존 6인자 호출은 Lost=0으로 호환한다. Before 불일치, sequence 재사용/역행, 음수/NaN, capacity 초과, 재생 전 overdraft는 거절한다. 거절 시 Native 통합을 기존 fail-closed 경로로 중지하며 잔고를 몰래 재등록하지 않는다. `AdjustSpatialFoodHabitat`는 기존 은신처 용량 변경/개발 fixture의 별도 장부다.

## 지면·수원 authoring과 표현

회전·scale이 있는 habitat는 component local box로 포함 여부를 판정한다. 회전한 volume의 world AABB 모서리에 물 공급이 새지 않게 한다. Plant의 큰 정수가 byte enum으로 wrap하지 않도록 cast 전 범위를 검사하고, 연결 수원의 높이/상승 범위가 잘못되면 명시적으로 거절한다. 이 authoring 조건은 실제 Actor를 사용하는 자동화에 포함한다.

후속 점검에서 0-scale/0 extent·잘못된 transform도 거절하도록 보완했다. 해당 지역의 잘못된 habitat는 선택 셀 포함 여부 전에 거절하여 inverse-transform이 무한 축처럼 해석되지 않게 한다. 유한 mirror scale은 유지한다. ON soil의 배열/격자/설정 구조가 맞지 않으면 Native Step/Field가 실패 처리하며 legacy OFF 재생으로 복귀하지 않는다. [수정·회귀·최신 실행](ECOSYSTEM_INTEGRATION_REVIEW_20261023.md)을 따른다.

`AEcoVegetationHabitat`를 owned 맵에 놓고 RegionId, Bounds, Plant(0 grass/1 riparian/2 shrub), Drainage, Shade를 설정한다. 수원 공급은 `bConnectedFreshWater=true`와 실제 WaterSurfaceZ/MaxSupplyRiseCm가 필요하다. 수평 거리 하나로 공급하지 않으며 지면이 수면보다 높으면 지정된 상승 범위 내에서만 공급한다. 아래 지면은 깊이/100cm를 침수로 소비한다. 이 연결은 authoring된 수문 연결성이다. 실제 지형을 넘는 유체·경로 탐색을 추정하지 않는다. 겹치는 volume은 actor 경로 이름 순 첫 일치만 소비한다. 값이 잘못되면 통합을 거절한다.

권위 `AEcoVegetationField`는 region당 하나이며 새 Subsystem/food owner가 아니다. PostUpdateWork GT에서 Mass processing 중이면 대기하고, 프레임 최대 32개 지면을 조회한다. 끝나면 5초 후 재검사하여 streaming·늦은 지형/이동·volume 제거를 반영한다. 미준비 셀은 표현을 숨기고 다시 시도한다. 논리 생태는 streaming 때문에 중단하지 않는다. 첫 지면 확인 전에는 기본 중성 토양값을 사용한다. slope normal.z<0.65인 확인 셀은 성장 불가·남은 food를 환경 손실로 제거한다. 벽 뒤 연결성/복잡한 수역은 자동 추정하지 않는다.

전송은 replicated Actor의 snapshot이며 지역당 최대 256개의 일정 stride 표본 셀을 1Hz로 보낸다. 전체 grid와 구별한다. 표본마다 현재량/capacity·수분·스트레스 uint8와 지면 anchor를 전달하고 client ISM은 그 값만 소비한다. 전송 표본은 자원 분할/이전이 아니다. native 셀 수와 표본 수를 같다고 설명하지 않는다. late join은 최신 배열을 수신한다. Actor relevance 밖에서도 서버 native 모델은 계속 실행된다.

Native 기본 표현은 기존 GrassD다. 새 owned 맵의 `BP_JYU_VegetationField`는 GrassA와 전용 `MI_JYU_EcosystemGrass`를 사용한다. bottom bound를 지면에 정렬하고 수신 먹이 비율로 scale을 바꾸며 1% 이하는 숨긴다. collision/navigation은 없다. custom data 0=food fraction, 1=moisture, 2=stress다. 새 재질은 기존 grass의 alpha/normal/wind 그래프와 texture parameter를 복사·보존하고, 수분 부족/스트레스에 따른 녹색→마른색 tint를 BaseColor에 곱한다. 원본 팀 재질은 수정하지 않는다. Dedicated는 mesh를 로드/ISM 생성하지 않는다. Blueprint/AnimNotify/client가 먹이를 차감하지 않는다. 일반 식생이 자동 protected refuge가 되지 않는다.

## 팀별 실제 확장 지점

새 `/Game/JYU/Maps/LV_JYU_Ecosystem`은 기존 authority adapter를 부모로 하는 날씨 BP 3개를 실제 지역에 연결한다. `UEcoWorldClockSubsystem`의 권위 simulation seconds로 180초 건조/강수 순환을 계산하며 지역 offset은 Forest 0/Barren 30/Highland 60초다. 고정 날씨 override와 순환을 동시에 켜면 거절한다. Client는 순환을 계산하거나 World 날씨를 쓰지 않고 기존 GameState Environment summary를 날씨 연출에 소비한다. 이 순환은 맵에 명시적으로 authoring한 게임 규칙이며 확률 날씨/계절·자연 균형을 검증한 결과가 아니다.

이전 `LV_JYU_HerdMigration` 검증은 authority API의 강수0→.65 전환 fixture였다. 새 BP 맵 검증은 `-VegetationAuthored`로 sampler의 날씨 쓰기를 끄고 저장된 BP만 관찰한다. 시각 BP만 비를 내리는 다른 팀 맵까지 모두 연결했다는 뜻은 아니다. 기존 맵의 기본값·날씨 연출은 그대로다. [BP 배치·실행 안내](JYU_ECOSYSTEM_BP_SETUP_20261023.md)를 따른다.

| 연결할 분야 | 입력/수정 지점 | 결과/확인법 | 중복 금지 |
|---|---|---|---|
| World/날씨 | 기존 `EcoRegionEnvironmentAdapter::ApplyRainfall(.65, Rain)` / `ApplyWeather` | 다음 native step에서 `VegetationWeather`, 수분은 시간 적분 | VFX에서 Food/HP 직접 갱신 |
| 지형/수원 | owned `AEcoVegetationHabitat` bounds·수면 높이·연결성 | 지면 재조회 후 셀별 habitat; 실패 시 명시적 reject | 물가 거리만으로 수원 허가 |
| Ecology | `CommitSpatialFood(..., After, Lost)` / `GetSpatialFoodAudit` | sequence·소비/성장/환경 손실·현재 잔고 | 별도 patch ledger·음수 regeneration |
| Native/RL | `EcoVegetationV3.h`·`FFoodGrid` / Integrated snapshot 입력 | 기존 실제 food sensing·섭식과 native outcome | Raw Request/obs slot 의미 덮어쓰기 |
| 표현/네트워크 | `EcoVegetationField`/`FEcoVegetationVisualCell`/ISM custom data | client 수신 배열·instance 수·late join | client 수분/성장 계산·food 추정 writeback |
| 진단 | `CaptureDiagnostics()` JSON | grid 합=ledger_amount, 소비/성장/손실 누적 일치 | HUD/샘플러의 논리 authority |

공통 충돌 파일은 `EcoWorldV3.h`, Integrated Step/Subsystem, `EcologySimulationSubsystem.h`/SpatialFood, `EcoResourceTypes.h`다. SpeciesAI를 공간 feeding 소비자로 바꾸려면 기존 region FeedRequest 대신 동일 grid의 실제 접근 셀과 부분 지급 contract를 먼저 연결해야 한다. 현재 경로를 이미 연결됐다고 표시하지 않는다.

## RL 인계: 기존 모델과 새 세계 구분

현재 모델은 논리 식물 유형 3개이며 메시 표현은 모두 같은 grass 표본을 사용한다. 새 BP 맵의 건조색 재질은 연결했지만 riparian/shrub 전용 외형, 실제 물가 authored volume 장면, 식생 차폐의 Native 감각 연결은 남은 작업이다. World 입력은 Shipping에서도 수분에 소비되지만 기존 v3 감각 날씨 감시/연출의 Shipping 범위와 cook/패키징은 별도 계약이며 이 변경으로 모두 검증됐다고 설명하지 않는다.

수분·기온·일조·plant/ground/capacity가 같은 Native regrow producer를 통해 실제 food와 관측 0을 바꾼다. 관측 0 의미는 여전히 local food이며 새 수분값을 그 칸에 대신 쓰지 않는다. 현재 모델/backend는 기존 native R1b(-F) + 명시적 soil-v1 규칙이며 별도 정책 writer나 온라인 학습을 추가하지 않는다. 새 경험/출생의 fallback은 아직 연결하지 않았다.

기존 `eco_v3_snapshot` version 1은 soil 상태/수원/plant를 표현하지 못하고 Python mirror와 evaluator도 이해하지 못한다. ON일 때 해당 export를 명시적으로 거절하여 적응 고리가 다른 세계를 같은 snapshot으로 학습하지 못하게 한다. ON 세계 입력 계약/새 snapshot·mirror·Golden·재학습은 RL 후속이다. OFF에서는 기존 export/모델·Golden 경로가 유지된다. 전체 ecology save를 구현한 API가 아니다.

engine-free `EcoVegetationV3::Advance`와 Native reference world를 UE 자동화에서도 사용한다. 예제: default moisture=.5, grass, drainage=.5, capacity=1, food=0, rain=.5/temp20/light1에서 한 step 뒤 food>0; 같은 시작을 4500 step 강수 .5 대 건조0/temp30으로 실행하면 수분·성장/손실·food가 달라지며 각 수지는 정확히 닫혀야 한다. 침수 Grass와 Riparian, 빈셀 회복, NaN·긴 dt 거절도 포함한다. 이는 C++ 계약 검증이며 Python parity의 대체가 아니다.

## 실행과 acceptance

`Tools/EcoVegetationEval/build_and_run.ps1`은 엔진/빌드가 모두 끝난 뒤 engine-free C++ reference world를 컴파일·실행한다. seed 11/23/47 × OFF/비/건조/초지 침수, 각 600 simulation seconds, 48사슴/4늑대·respawn OFF다. terrain/Social/migration/통합 야생 설정이 없는 기준 세계이며 이 수치를 production 맵의 생존율이나 서버 p95로 확대하지 않는다. OFF의 balance_checked=false는 수지 별도 측정 제외이고 OFF trajectory는 UE 자동화로 검증한다. ON 수지, 실제 native feeding과 표적 소실/죽음 이후 slot 제거가 포함된다. 출력은 `Saved/Vegetation_20261023/EngineFree.json`이다.

Play 전에 `eco.Vegetation 1` 또는 실행 인수 `-EcoVegetation`. 맵 `/Game/JYU/Maps/LV_JYU_HerdMigration`, 기본 48사슴+4늑대/지역. 자동 맵 재생성/원본 저장은 하지 않는다. OFF로 재시작하면 기존 세계다.

새 `/Game/JYU/Maps/LV_JYU_Ecosystem`은 spawner `bEnableVegetation=true`와 `VegetationFieldClass=BP_JYU_VegetationField`를 저장했다. 별도 콘솔 입력 없이 Play한다. 이 맵의 OFF 비교는 spawner 옵션을 끈 복사/미저장 세션에서 실행하고 원본 저장을 피한다. 전체 맵을 켜는 global 기본값은 여전히 0이다.

직접 UBT는 `Tools/Integration/build_integration_milestone.ps1 -Milestone A`. 빌드 전 모든 engine/build 프로세스 검사, 완료까지 대기. GoogleDriveFS가 executor/obj/UHT 파일을 잠근 실패가 있었으며 Application Event Log도 확인했다. 현재 helper는 UBA 임시 저장소만 OS temp의 build별 폴더로 분리한다. 외부 엔진 캐시 쓰기 권한이 필요하다.

자동화 `AdaptiveEcosystem.Vegetation`은 수분 수지·식물 침수 차이·고갈 회복·환경 receipt/replay·실제 Native feeding·OFF trajectory·회전 habitat/미지원 설정·권위 climate clock을 검증한다. 전체 `AdaptiveEcosystem` 회귀도 실행한다.

`Tools/Editor/audit_vegetation_runtime.py`는 실제 owned PIE(`-VegetationPIE`) 또는 dedicated 완료 relay에서 강수0→.65 입력만 바꾸고 샘플을 기록한다. food 제거/에너지/개체 teleport/정책 강제는 하지 않는다. 관찰자 위협은 명시적으로 OFF다. 이 시험의 날씨 전환은 개발 fixture이며 자연 발생 날씨 빈도/생태 균형 검증이 아니다. client 관찰은 `audit_vegetation_client.py`다. 최종 결과·미수행 범위는 상태표에서 갱신한다.

새 BP 맵에서는 위 sampler에 `-VegetationAuthored -VegetationMap=LV_JYU_Ecosystem -VegetationAuditFolder=EcosystemBP_20261023`를 전달한다. sampler는 날씨를 변경하지 않는다. 재현 명령과 최종 로그·통계는 [BP 안내](JYU_ECOSYSTEM_BP_SETUP_20261023.md)와 [공유 증거](Evidence/EcosystemBP_20261023.json)를 따른다. 초기 fixture 증거 [Vegetation_20261023.json](Evidence/Vegetation_20261023.json)은 그 단계의 이전 결과로 보존한다.
