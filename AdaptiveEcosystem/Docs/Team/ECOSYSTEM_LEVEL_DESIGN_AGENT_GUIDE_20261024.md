# 레벨 디자인 담당·AI agent 작업 안내

작성일 **2026-10-24**. 구현 기준 `d095948`, 공통 안내 기준 `9858e61` 이후 문서 보완이다. 실제 branch/HEAD와 Source·에셋을 확인하고 시작한다. 이 문서는 새 레벨 배치나 런타임 테스트를 수행한 기록이 아니다.

## 1. 시작할 때 읽을 것

1. [프로젝트 공통 맥락](../PROJECT_CONTEXT.md)과 [팀 AI 공통 안내](ECOSYSTEM_AI_COLLABORATION_20261024.md).
2. [현재 구현 상태](../Architecture/ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md), [life 실행 계약](../Architecture/ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md).
3. [BP 배치 안내](../Architecture/JYU_ECOSYSTEM_BP_SETUP_20261023.md), [식생 계약](../Architecture/ECOSYSTEM_VEGETATION_CONTRACT_20261023.md). 최초 구축 이력의 9 habitat·미배치 수원·미연결 설명은 최신 life 상태와 구분한다.
4. [날씨 담당 안내](ECOSYSTEM_WEATHER_AGENT_GUIDE_20261024.md), [실제 검증 근거](../Architecture/Evidence/EcosystemLife_20261023.json).

현재 `/Game/JYU/Maps/LV_JYU_Ecosystem`은 식생/life가 켜진 owned 검증 맵이다. BP 7종, habitat 10개, 날씨 adapter 3개와 기존 이주 경로를 사용한다. 기존 팀 맵을 같은 상태로 일괄 변경하지 않는다. 최초 생성 스크립트 `Tools/Editor/setup_jyu_ecosystem.py`로 현재 맵을 재생성하지 않는다.

## 2. 레벨 담당자가 결정하는 것과 실행 코드가 결정하는 것

| 대상 | 레벨 담당의 입력 | 실제 소유자·주의 |
|---|---|---|
| 지역 | 고유 RegionId, 지리 범위, 인접 지역, 도착 위치 | World 등록·M4 자원/인구; 이름 변경은 저장/경로/날씨 참조까지 영향 |
| 지면 | Landscape/정적 지면, 충돌, 경사, 통행 가능한 실제 공간 | Native 이동·지면 조회; NavMesh만 그려도 기존 Native가 자동 사용하지 않음 |
| 식생 | habitat 범위·Plant·배수·그늘, owned mesh/material | 실제 FoodGrid가 먹이 잔량·회복·손실 소유 |
| 물 | 확인한 수면 높이·지면·수문 연결성 | 명시적 공급 입력; 유체/수영/강 흐름 시뮬레이션 아님 |
| 은신처 | 실제 지면 슬롯·보호 footprint와 일치하는 외형 | 기존 Shelter/Refuge 등록·Native 안전 규칙; 장식 수풀은 자동 안전지대 아님 |
| 이주 | 이동 가능한 world 좌표 경로·양 끝 stage·폭 | 기존 계획/Travel·Native 단일 이동 writer; 선을 그렸다고 도착 완료 아님 |
| 연출 | 장식용 풀/바위/물·조명·안개·소리 | 표현; 먹이/HP/위치 writer를 BP에 추가하지 않음 |

Source 경로는 실제 프로젝트의 `Source/AdaptiveEcosystem/` 아래다. 확인할 파일은 `World/EcologyRegion.h/.cpp`, `World/EcoVegetationField.h/.cpp`, `Mass/EcoHerdMigration.h/.cpp`, `AI/Social/Shelter/EcoRefugeHabitat.h/.cpp`, 기존 `Creature/` 통합 spawner와 Runtime이다. 새 시스템을 복제하기 전에 이 소비자를 확인한다.

## 3. 맵 작업을 안전하게 시작하는 순서

1. 현재 branch/HEAD·dirty 에셋·LFS 상태와 맵 owner를 기록한다. 다른 팀의 저장되지 않은 편집이 있는지 확인한다.
2. 원본 팀 레벨에 작업해야 한다는 명시적 범위가 없다면 담당 owned 복사 맵과 폴더를 정한다. 기존 생태계 맵도 무작정 재생성하지 않는다.
3. World Settings/GameMode, 통합 spawner 개수·backend·식생/life/이주 옵션, 지역 목록과 날씨 writer를 조사한다. 복사로 중복된 spawner/region/날씨 manager를 먼저 찾는다.
4. 변경 목적을 한 가지로 좁힌다. 예: “Forest 수원 주변의 지면·riparian 범위가 실제 공급 셀과 일치하게 한다.”
5. 기준 화면과 실제 진단 값을 저장하고, 수정 후 저장·재로드·일반 PIE·필요한 멀티/패키지를 순서대로 확인한다.

팀별 `.umap`/`.uasset` 동시 편집은 수작업 텍스트 병합으로 해결하지 않는다. World Partition은 맵과 해당 `__ExternalActors__`/`__ExternalObjects__`를 함께 검토한다. 임의 파일 복사만으로 안전한 맵 복제가 완료됐다고 판단하지 않는다.

## 4. 지역과 실제 이동 공간

`AEcologyRegion`의 RegionId는 장기 식별자다. Outliner 라벨만 바꾸는 것과 다르다. `AdjacentRegionIds`, route 양 끝, habitat, 날씨 `RegionIds`, 저장/진단 참조를 함께 대조한다. 중복 ID·빠진 인접 ID를 빈 지역으로 조용히 대체하지 않는다.

RegionBounds는 논리 영역이며 벽/울타리 collision을 만드는 기능이 아니다. `ContainsPosition`은 local box의 XYZ를 검사하지만 날씨 presenter의 카메라 지역 판정은 XY를 사용한다. 높은 관찰 카메라에서 날씨가 보이는 것과 개체가 같은 3D 영역에 포함되는 것은 다를 수 있다. 다층/실내/겹친 지역은 별도 설계가 필요하다.

`InitialFoodAmount`, `FoodCapacity`, `FoodRegenerationRate`는 초기 authoring이다. 런타임 잔량 변경 UI로 해석하지 말고 새 PIE로 초기화를 확인한다. spatial food가 활성화된 지역에 별도의 BP 재생을 더하지 않는다. 생태계가 보기 좋게 유지된다는 이유로 food/Population을 직접 보충하지 않는다.

통행성은 성체·어린 개체의 실제 body/접지, 급경사·절벽·벽·좁은 통로·경계 인계로 확인한다. 지면 이동만 지원하는 backend를 물/비행으로 보내지 않는다. “Blocked” 진단은 무진행이며 지형 충돌 확정이 아니다. 실제 좌표·목적지·충돌·예약을 함께 확인한다.

## 5. 먹을 수 있는 식생과 장식 풀

현재 풀은 개별 BP마다 먹이를 보유하는 구조가 아니다. 서버의 실제 FoodGrid를 지역별 `AEcoVegetationField`가 표본화하고 ISM으로 표현한다. 먹으면 잔량 비율에 따라 폭·높이가 줄며 1% 이하는 숨긴다. 회복 시 다시 표현된다. mesh를 잘라내거나 모든 풀 Actor를 삭제하는 파괴 연출은 아니다.

표현은 지역당 최대 256개 일정 stride의 셀 표본이며 전체 논리 셀/전체 풀과 다르다. 장식 foliage·PCG 풀은 자동 섭식 대상이 아니다. 장식 풀만 남아 있는데 먹이가 부족한 장면을 피하려면 색/밀도·배치를 읽기 쉽게 조정하되, 시각 풀 수를 새 FoodAmount로 환산해 쓰지 않는다. Field는 spawner가 지역별 생성하므로 수동 중복 배치하지 않는다.

현재 Grass/Riparian/Shrub 표현은 구분되어 있고 기존 grass mesh·owned 재질을 사용한다. custom data 0=food fraction, 1=moisture, 2=stress 계약을 유지한다. 일반 식생은 충돌/navigation을 소유하지 않는다. 임의 collision을 켜면 지면 trace·이동·LOS의 의미가 달라질 수 있다.

`AEcoVegetationHabitat`의 설정:

| 항목 | 의미·검증 |
|---|---|
| RegionId | 실제 등록 지역과 일치 |
| Bounds | 회전/scale을 반영한 local box로 지면 포함 판정 |
| Plant | 0 grass / 1 riparian / 2 shrub; 다른 값 거절 |
| Drainage, Shade | 0..1; 실제 월드 입력의 authoring 값 |
| bConnectedFreshWater | 실제 확인한 수원 연결만 true |
| WaterSurfaceZ | world cm의 실제 수면 높이 |
| MaxSupplyRiseCm | 0..200cm 범위의 명시적 상승 공급 한도 |

Shade는 현재 광원/그림자에서 자동 측정하지 않는다. 나무를 놓았다고 토양 그늘 값이 자동 변경되는 것은 아니다. volume이 겹치면 현재 Actor 경로 이름 순 첫 일치가 소비된다. 이름/복제에 따라 우선순위가 달라질 수 있으므로 의도하지 않은 겹침을 없애고 명시적 우선순위 기능을 구현했다고 설명하지 않는다. 0-scale/0 extent/잘못된 transform·입력은 거절 대상이다.

지면은 현재 `ECC_WorldStatic` 상하 trace로 확인한다. 장식 바위·지붕 등 잘못된 정적 표면을 먼저 맞지 않는지 살핀다. 프레임당 최대32셀을 조회하고 한 순회 완료 후5초 뒤 재조회하므로 이동/streaming 반영이 즉시는 아니다. 지면 미준비 표본은 숨기고 재시도하며 논리 생태 전체를 정지하지 않는다. 확인 전 중성 토양이 사용될 수 있다. normal.z<0.65인 확인 셀은 성장 불가/환경 손실 처리다.

## 6. 수원·은신처·이주 경로 authoring

현재 `BP_JYU_AuthoredSpring`은 Forest (33800,28700), 수면Z 약-1084.09448cm의 얕은 수원 사례다. 이 좌표를 새 지형에 그대로 복사하지 않는다. 지면/수면과 최대 수심·둑·공급 상승 범위를 새로 측정한다. `WaterSurfaceSizeCm`는 외형 크기이며 논리 Bounds와 자동 동의어가 아니다. 물 mesh가 보인다는 이유만으로 연결을 true로 하지 않는다. 현재 벽/유역을 넘는 수리 연결을 자동 추론하지 않는다.

은신처는 보호 영역과 보이는 수풀/바위·실제 슬롯·접지가 일치해야 한다. 등록 준비·실제 도착 전 점유, 제거/stream-out 후 예약, 지형 재준비 시 재등록을 검증한다. 현재 통합 `ShelterSafe=1`과 `ProtectedRefuges=1`의 역할을 보존하며 안전 배수를 중복 적용하지 않는다. [보호 은신처 기록](../조연우/JYU_REFUGE_SAFETY_20261016.md)과 최신 life 계약을 함께 읽는다.

`AEcoHerdMigrationRoute`는 world 좌표 Points를 사용한다. 현재 제한은 2..256 유한 점, 구간당 최대200m·전체1km이며 양 끝은 해당 Native stage 안에 있어야 한다. 실제 지형을 따라 충분한 점을 놓고 `CorridorWidth`의 cm 단위·양방향 통행·도착 공간을 확인한다. Actor를 옮겨도 world 좌표 Points가 원하는 대로 이동했다고 가정하지 않는다. 배열을 다시 확인한다.

`bSharesHabitatReports`는 단순 디버그 옵션이 아니라 미방문 목적지 정보의 authoring된 공유 지식 입력이다. 레벨 편의로 켜기 전에 학습/생태 담당과 관측·기억 의미를 맞춘다. HUD 경로는 읽기 전용이며 선이 연결됐다고 실제 인계/정착이 성공한 것은 아니다. [이주 계약](../조연우/HERD_MIGRATION_AND_SIGNAL_CONTRACT.md)을 따른다.

## 7. 변경 종류별 acceptance

| 변경 | 최소 확인할 결과 |
|---|---|
| 장식/재질 | 저장·재로드, 실제 조명/거리별 외형, 원본 재질 보존, collision·cook 영향 |
| 지형/충돌 | 지면 표본·접지·경사·이주 양방향·출생 자리·은신처 슬롯, streaming 재진입 |
| habitat/물 | 포함/제외 셀·회전/겹침·수면/공급/침수, food 장부와 실제 표현 |
| region/route | ID·인접성·양 끝 stage·실제 Native 인계/정착·실패 정리·checkpoint 영향 |
| 통합 옵션/새 참조 | 기본 맵 OFF 보존·기존 backend 가드·복수 Client late join·실제 cook/패키지 |

식생 진단 `CaptureDiagnostics()`와 M4 audit로 실제 food/consumed/regenerated/environment loss를 확인한다. 기본 수지는 Before−Consumed+Regenerated−EnvironmentLost=After다. 화면만 보고 수지 성공으로 처리하지 않는다. 진단 실패를 값 강제 설정/새 잔고 등록으로 숨기지 않는다.

전체 맵 대상 기존 audit를 실행하기 전 스크립트의 MAP/owner/부작용을 읽는다. 예를 들어 `audit_ecosystem_level.py`는 팀 통합 테스트 맵을 대상으로 하므로 현재 owned 생태계 맵용이라고 가정하지 않는다. 자산 감사/저장 도구도 읽기 전용인지 확인한다. 재현 실행은 [life 계약의 명령](../Architecture/ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md#재현-순서)을 기준으로 새 audit 폴더와 실제 대상 맵을 지정한다. 이번 문서 작성에서 이 실행을 새로 수행하지 않았다.

## 8. 협업·성능·최종 인계

날씨 담당에게 지역 ID/Bounds/날씨 writer·실내/수역·카메라 경계 조건을 넘긴다. 서버 담당에게 상시 로드할 논리 입력, streaming 수명, 표본/Actor 상한과 soft 참조를 넘긴다. 학습 담당에게 새 경사/수원/은신처/이주 공유 지식과 기존 세계와의 차이를 넘긴다. 식생 차폐의 실제 소비와 화면상의 불투명도를 동일시하지 않는다.

성능은 장식 풀 밀도·ISM/HISM instance·그림자·translucency·LOD·streaming hitch와 논리 셀 비용을 나눠 비교한다. 화면을 풍성하게 만든 결과로 서버 food 잔고/개체 수를 늘리지 않는다. Nanite/HLOD/품질 설정을 켰다는 사실만으로 성능 목표를 통과했다고 쓰지 않는다.

최종 인계에는 맵/에셋 경로, 변경 전후 화면·좌표/범위, RegionId와 flags, 실제 실행 시간·개체/접속 수, 장부/접지/통행/late join·cook 결과, 미검증 항목을 적는다. World Partition 외부 에셋·LFS까지 push를 확인한다. 원시 Saved/개인 발표/빌드 출력은 제외한다. [공통 종료 양식](ECOSYSTEM_AGENT_START_PROMPTS_20261024.md#5-종료-인수인계-양식)을 사용한다.

## 9. AI에게 전달할 시작 요청

```text
루트 AGENTS.md, Docs/PROJECT_CONTEXT.md, 팀 AI 공통 안내와
Docs/Team/ECOSYSTEM_LEVEL_DESIGN_AGENT_GUIDE_20261024.md를 먼저 읽고
내가 지정한 맵/에셋 범위의 레벨 작업을 진행해줘.
실제 프로젝트는 AdaptiveEcosystem/AdaptiveEcosystem.uproject, UE5.8이야.
branch/HEAD·dirty/LFS·World Partition·owner와 현재 Source 소비자를 확인해줘.
원본 팀 맵과 다른 사람 WIP를 보존하고 기존 owned 생태계 맵을 재생성하지 마.
RegionId/인접성·지면 충돌/접지·habitat/수면 연결·은신처 슬롯·world 좌표 이주 경로,
중복 spawner/날씨 writer와 실제 실행 backend/flags를 먼저 확인해줘.
장식 foliage/물/VFX를 별도 먹이/HP/위치 writer로 만들지 말고
기존 Native 단일 writer와 M4·Field/Bubble 표현을 유지해줘.
변경 전후를 저장·재로드·실제 PIE와 필요한 streaming/멀티/cook으로 검증하고,
자동으로 지원되지 않는 NavMesh/수영/새 종/수리 모델은 구분해서 보고해줘.
C++/빌드 입력 변경은 루트의 직접 UBT·프로세스 대기 규칙을 따르고
미실행 검증은 통과했다고 쓰지 마. 수정 범위·evidence·미지원·다음 작업을 한글로 인계해줘.
```
