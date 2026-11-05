# LV_JYU_Ecosystem 실제 플레이 흐름 점검 — 2026-10-29

이 문서는 수정 전 진단이다. 사용자의 후속 요청으로 수행한 변경과 새 실행 근거는 [플레이 흐름 수정](JYU_PLAYFLOW_FIX_20261029.md)을 따른다.

사용자 요청으로 식생 배치·성장·섭식·표현, 도망·은신·사냥, 이주와 생활 흐름을 새로 실행해 점검했다. **식생 성장/섭식 후 축소/재성장은 작동한다.** 우선 개선할 부분은 **단독 무리의 이주 제외, 지역 경계의 개체 겹침, 야간과 조명 표현 불일치, 낮은 식생 표시 밀도**다.

기준은 `codex/social-shelter-handoff`, HEAD `ecb898e`, UE 5.8의 기존 runtime DLL이다. 소스·Config·맵·BP·가중치·기본값을 수정하거나 저장하지 않았다. 이번 결과는 **진단**이며 root-cause fix/구조적 우회/containment를 수행한 기록이 아니다. C++/빌드 입력 변경이 없어 새 UBT/전체 자동화를 실행하지 않았다.

## 실제 실행 조건

| 실행 | 조건과 결과 |
|---|---|
| NaturalPIE | owned 맵 일반 PIE, D3D11, seed 23, 300 wall seconds. 10초 간격 30표본(0–290초), 정상 종료. 기존 authored 기후·먹이·개체·정책을 유지하고 관찰 Pawn의 위협만 비활성화했다. 처음에는 플레이어 기본 시점, 이후 Forest의 같은 실제 식생 위치를 관찰했다. |
| BoundaryPIE | 별도 새 PIE 120 wall seconds, 같은 seed, 12표본. 관찰 Pawn/카메라만 Highland 경계 근처로 옮겨 표현을 확인했다. 정상 종료. 월드 준비 도구로 terrain을 로드하며 맵은 저장하지 않았다. |
| harmless / chase / ambush | 각각 새 실제 game world, seed 23·늑대 0, 약55초 관찰. 실제 권위 Character를 재배치하는 명시적 fixture다. chase는 CharacterMovement 입력, ambush는 실제 TryStrike를 사용한다. AI 기억/HP를 직접 설정하지 않았다. 세 실행 모두 FINISHED·프로세스 exit 0. 자유 플레이의 자연 발생 빈도를 측정한 것은 아니다. |
| DroughtMigration | 별도 권위 서버, seed 23·늑대 0, 고정 시간 benchmark 600 simulation seconds(관찰 wall 약29.58초). **Barren의 먹이 0·재생 중지**를 기존 audit API/M4 거래로 명시 적용했다. 자연 날씨에 의한 가뭄이나 실시간 프레임 성능 결과가 아니다. FINISHED·exit 0. |

원시 JSON·스크립트·로그·화면은 프로젝트 `Saved/PlayflowAudit_20261029/`, 경계 재확인은 `Saved/PlayflowBoundary_20261029/`에 있다. 기존 10-23 증거는 덮어쓰지 않았다. 작은 공유 집계는 [evidence JSON](../Architecture/Evidence/PlayflowAudit_20261029.json)이다. 관찰 Python은 QA용이며 게임 추론 경로에 추가하지 않았다.

## 확인된 개선 항목

### 1. P1 — 단독 무리는 이주하지 못하고 굶어 죽을 수 있음

가뭄 시험에서 Barren 초기 48마리 중 **19마리가 Forest로 실제 지역 인계되고, 9개 계획 전부 2/2 또는 3/3 정착**했다. 그러나 simulation 102초와 300초에 남은 **29마리는 각각 1마리짜리 무리**였고 `migration_reason=None`이었다. 이후 Barren의 starvation 사망 29건, 600초 시점 Barren 생존 0을 확인했다.

[EcoHerdMigration.cpp](../../Source/AdaptiveEcosystem/Mass/EcoHerdMigration.cpp)의 새 계획 생성은 `Members.Num()<2`이면 건너뛴다. 따라서 단독 무리에 대한 이주 제외는 구현으로 확인한 직접 제한이다. 전체 29마리가 처음부터 singleton이었던 것은 아니다. 최초 표본은 singleton 24개·2마리 무리 12개였으며, 이후 무리 구성이 바뀐다. 왜 재결합되지 않았는지는 별도 분석이 필요하다.

**권장:** 단독 개체의 합류/개별 탈출을 지원할지 계약을 정하고, 출발 불가 사유를 Inspector에 남긴다. 개체 순간이동·무상 먹이 보충·다른 movement writer 추가로 숨기지 않는다. 이번 시험의 극단적인 자원 제거 자체가 자연 생태 균형의 실패를 증명하지는 않는다.

### 2. P1 — 지역 경계에서 정체·몸 겹침

NaturalPIE에서 Highland ID 151/153이 `(40000,-55000,2510.93365)`의 **동일 좌표**에 여러 표본 동안 머물렀다. Forest ID 42/52는 30–60초 표본에서 중심 간 거리 약17.09cm를 유지했다. 새 BoundaryPIE에서도 같은 Forest 쌍의 약17.09cm 간격이 반복됐으며, Highland ID 146/152는 100·110초에 중심 간 약**0.0055cm**였다. `VegetationPIE_1.png`에 사슴 몸이 겹치는 실제 화면도 남았다.

NaturalPIE의 100초 표본은 생존 초식 144마리 중 40마리가 Native 사각 경계에서 5cm 이내였다. 150초에는 초식 142마리 중 46마리의 energy가 5/100 미만이었다. 에너지 저하 전부를 경계 때문이라고 확정하지 않는다.

[EcoRepertoire.h](../../Source/AdaptiveEcosystem/AI/Policy/EcoRepertoire.h)의 `ApplyMove`는 위치를 `[0,WorldSize]`로 자르며 heading은 자르기 전 이동 방향을 따른다. 실제 통합 경로는 [EcoWorldV3.h](../../Source/AdaptiveEcosystem/AI/Policy/EcoWorldV3.h)의 C1 이동이다. **경계 clamp는 확인 사실**, 장기 정체의 선택/조향 원인과 개체 간 분리 부족의 전체 인과는 추가 분석 대상이다.

**권장:** 단일 Native 이동 경로에서 경계 접선/내부 복귀, 무진행 탈출, 실제 몸 크기에 따른 개체 간 분리를 검토한다. 이는 기존 학습 세계 이동 규칙과 parity에 영향을 줄 수 있으므로 임의 계수 변경으로 처리하지 않는다.

### 3. P2 — 생태계는 밤인데 화면은 대낮

NaturalPIE 90초의 세 지역 `light=0`이고 잠든 개체가 8마리였지만, 같은 시각 Forest `VegetationPIE_1.png`는 밝은 지면과 강한 햇빛 그림자였다. BoundaryPIE 80–110초에도 `light=0`이며 90초 Highland 화면은 대낮처럼 보인다. 배치 inventory에서 방향광 2개(초기 intensity 8 / 약.01)를 확인했다. 광원 intensity의 전체 시간 추적은 하지 않았다.

**권장:** 실제 권위 시계/낮밤을 기존 하늘·방향광·노출 표현의 소비자에 연결한다. 논리 시계를 별도로 추가하지 않는다. 논리적 수면과 식생 광량이 변하는 것을 화면 밝기 변화와 동일시하지 않는다.

### 4. P2 — 먹을 수 있는 식생과 보이는 식생의 대응이 약함

각 지역은 30×30=900개, 셀 한 변 400cm다. `AEcoVegetationField::Tick`은 stride 4로 표본화한다. 최종 Forest는 **먹이 용량 양수 셀 481개 중 표시 대상 120개**, Barren 434개 중114개, Highland 353개 중85개였다. Forest 최종 생존 초식47마리 중12마리만 표본화되는 셀에 있었다. **비표본 셀에도 먹이가 있고 정상 섭식할 수 있으므로**, 사슴이 아무 풀도 없는 곳을 먹는 모습이 발생할 구조다.

기본 플레이어 시작 화면도 거의 지면 재질만 보였다. 고정 Forest 시점의 풀이 작고 드문드문하며, 먹이량이 바뀌어도 넓은 녹색 지면 재질은 그대로였다. 이는 성장 정지와 구별되는 가독성 문제다.

**권장:** 실제 섭식 지점/플레이어 근처의 셀을 우선 표시하거나 bounded 방식으로 표시 범위를 개선한다. 먹을 수 있는 풀과 지면·장식 식생을 구분한다. 표현을 늘리면서 자원 잔고나 서버 food를 늘리지 않는다. 관련 구현은 [EcoVegetationField.cpp](../../Source/AdaptiveEcosystem/World/EcoVegetationField.cpp)의 Tick/OnRep_Cells다.

### 5. P2 — 비가 와도 모든 빈 땅에 풀이 새로 생기는 모델은 아님

최종 용량 0 셀은 Forest419/Barren466/Highland547개다. 기존 FoodGrid는 초기 생성한 용량 안에서 회복하며, [EcoVegetationV3.h](../../Source/AdaptiveEcosystem/AI/Policy/EcoVegetationV3.h)의 성장은 남은 용량에 비례한다. **용량이 0이면 강수·수분이 좋아져도 식생이 확산하지 않는다.** 이번 점검에서 발생한 재성장 고장으로 분류하지 않는다.

**권장:** 현재 목표가 기존 패치 회복인지, 비에 따른 식생 영역 확장인지 구분한다. 후자를 원하면 habitat/용량 변화와 기존 M4 보존 거래·학습 세계 계약을 함께 설계해야 한다.

### 6. 추가 원인 분석 — Highland 생존/먹이 접근

NaturalPIE 300초에는 starvation 사망 5건(Forest1/Barren2/Highland2)이 있었다. 별도 늑대0·Barren 가뭄 600초 시험에서는 **Highland에서도 starvation 24건**, Forest1건이 발생했다. Highland에는 먹이 제거 fixture를 직접 적용하지 않았고 최종 food 약37.31이 남았다. 따라서 지역 총량이 남아 있는 상태의 개별 먹이 접근·기온에 따른 회복·장소 선택·경계 정체를 함께 봐야 한다.

이는 해당 seed/구성의 운영·밸런스 위험 신호다. 개체별 섭식 불가능 원인이나 전체 세계의 장기 평형 실패를 이번 실행만으로 확정하지 않는다. 다음 원인 분리 시험은 같은 조건의 무가뭄·늑대0 대조군과 Highland 개체별 셀/섭취/이동 실패 추적이 적절하다.

## 작동을 확인한 항목과 한계

| 항목 | 이번 실제 관찰 |
|---|---|
| 식생 성장 | 0–290초 누적 성장 Forest459.77 / Barren426.33 / Highland179.36. 같은 기간 누적 섭식463.68 / 439.30 / 217.18. 자원 장부 잔량 오차0. 단위는 기존 food units다. |
| 먹으면 크기 감소·재성장 | 실제 동일 셀/동일 메시 종류의 instance 폭·높이와 셀 food를 추적했다. 감소 후 회복이 함께 나타난 셀 Forest86/Barren92/Highland70개. Forest cell0은20→30→40초 food 비율1→.335→.546, height scale1.037→.461→.657. 환경 손실도 별도 집계하므로 모든 감소를 섭식으로 단정하지 않는다. |
| 고갈 숨김/재등장 | 표본 셀의 렌더 instance 누락/복귀를 관찰했다. 표시 갱신1Hz·Food byte 양자화 때문에 최신 논리량과 동일 시각 렌더가 정확히 일치하지 않을 수 있다. 전 셀/전 프레임 정확성 검사는 아니다. |
| 지면·수원·habitat | 두 PIE에서 지역별 지면900셀을 확보했다. 배치 inventory는 habitat10개·날씨3개·권위 지역3개, Forest 실제 연결 수원9셀이다. 수원/관목의 전용 아트 품질·모든 streaming 수명은 별도다. |
| 무해 접근 | subject17, familiarity 최대약.631, Curious 표본7개, 실제 수평거리 최소약15.68m. |
| 추격 | 실제 플레이어 속력 최대900cm/s, Retreat 표본14개. |
| 공격 | 6번 요청(각 그룹2번) 후 subject HP 최소40, Unknown fear 최대약.567. 공격 원인 미식별과 연속 입력 제한 검사 통과. 모든 각도/장애물/클라이언트 공격 검사는 아니다. |
| 포식·휴식·도망 | NaturalPIE에 Flee/Pursue/Stalk/Pounce/Eat/SatedRest/Sleep 활동과 실제 Predation 사망9건을 관찰했다. 단순 Activity 표본만으로 모든 경로·애니메이션 정확성을 보장하지 않는다. |
| 은신처 | ShelterHold 활동과 보호 표본 누적12215, capture violation/inside predator 카운터0. 이번에 강제 경계 진입·삭제·재등록 시험은 하지 않았다. |
| 출생·사망 | NaturalPIE 자연 출생 stable ID9개, 사망14건(포식9/기아5), 생존156→151. 자연 평형/세대 선택의 증거는 아니다. |
| 이주 | 자연300초에는 실제 이주0. 별도 가뭄600초에는19명 인계·9계획 전원 정착, 자원 잔량 장부오차0. 단독 잔류 문제는 위와 같다. |

## 다음 수정 순서

1. 단독 무리의 이주/합류 정책과 실패 사유 표시를 먼저 정한다.
2. 경계 정체·몸 겹침을 단일 Native writer 안에서 해결한다. 원래 trigger와 반복 실행으로 확인한다.
3. 실제 낮밤과 조명, 실제 섭식 셀과 표시 식생의 대응을 개선한다.
4. Highland 무가뭄 대조군으로 생존·먹이 접근 원인을 분리한다.

이번에는 멀티/late join, 저장·재시작, cook/package, streaming 재진입, 다수 seed 장기·500/1000개체를 새로 검증하지 않았다. 시작 직후 엔진 로그의 `LogAutomationTest: Error: Condition failed`와 UnifiedErrorTest 메시지는 map/관찰기 시작 전 발생했다. 이를 생태계 테스트 실패나 검증 성공으로 분류하지 않았으며 원시 로그를 보존했다. 모든 실행을 정상 종료했고 빌드/프로세스를 강제 중단하지 않았다.
