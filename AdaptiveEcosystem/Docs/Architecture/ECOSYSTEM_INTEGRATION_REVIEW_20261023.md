# 구현 후 통합 점검과 수정 — 2026-10-23

최신 후속 점검은 이 문서 아래 **life-v1 구현 후 재점검**과 [현재 상태표](ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md)·[최종 evidence](Evidence/EcosystemLife_20261023.json)를 우선한다. 아래213개/후속 미구현 설명은 첫 soil 통합 당시의 이력이다.

사용자의 전체 재점검 요청에 따라 이번 구현과 실제 호출되는 Native/M4/World/무리 이주/표현/복제 연결부를 다시 검토했다. 파일 존재나 process exit code만으로 완료를 판정하지 않고 실제 결과와 실패 보고서를 확인한다. 전체 기획의 미구현 항목을 구현 완료로 바꾸는 감사가 아니다. [전체 상태](ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md)와 [BP 실행 안내](JYU_ECOSYSTEM_BP_SETUP_20261023.md)를 함께 읽는다.

## 확인하고 고친 문제

| 문제 | 이전 실패 조건 | 수정과 영향 | 회귀 근거 |
|---|---|---|---|
| 목적지 혼잡 중복 집계 | 개체가 실제 지역에 들어가 Population에 포함됐지만 route 끝에 도착하기 전에는 Incoming에도 포함 | `EcoHerdMigration.cpp`가 살아 있는 현재 계획의 **목적지 밖** 구성원만 예약 인원으로 센다. 이번 Reconcile의 아직 인구 commit 전인 이전 receipt는 지역 인구 delta로 반영. 이동/장부 writer는 그대로 | `HerdIncomingCountsRegionalEntryOnce`: 다음 무리의 실제 출발 의도와 미commit receipt 경계를 함께 검사 |
| 잘못된 경로·무제한 GT sweep | NaN/Inf 좌표·폭, 매우 긴 구간이 물리 trace와 정수 변환/반복에 도달 가능 | `AEcoHerdMigrationRoute::IsValidRoute`를 계획/디버그가 함께 사용. Native 지상 route는 2..256점, 구간200m/총1km 이내, 유한 양수 폭. 직접 `TraceMove`도 좌표 검증·최대1024 substep으로 제한 | `NativeRouteRejectsInvalidAndUnboundedSweep`; 실제 저장 route 29점 재로드 확인 |
| 0배율 서식지의 무한 축 | inverse transform의 0-scale 역수가 0이 되어 멀리 있는 점도 local box 안으로 판정 | 양수 유한 extent·유효 transform·0이 아닌 scale을 검사하고, 해당 지역의 잘못된 habitat를 gather 전에 거절. 유한 mirror scale은 지원 | `HabitatRejectsCollapsedBounds`: 실제 Actor·먼 점·0 extent·음수 mirror 검사 |
| soil ON의 조용한 OFF 복귀·배열 접근 | soil 배열 크기가 맞지 않으면 `Regrow`가 legacy 공식을 사용하고 Field는 없는 배열을 접근할 수 있음 | `FFoodGrid::HasValidVegetationLayout`을 Native Step/Field/Regrow가 공통 소비. ON은 잘못된 구조·설정을 거절하고 다른 세계의 재생을 실행하지 않는다. gather 실패 뒤에도 전송을 중단 | `SoilCannotFallBackOnInvalidLayout`: 실제 grid의 잘못된 ON/정상 ON/기존 OFF 검사 |
| 검증 시간의 비정상 값 | NaN/Inf duration, observer 종료보다 빠른 server exit가 불완전/무기한 관찰을 만들 수 있음 | launcher가 process 시작 전 거절. Python observer도 유한 1..3600초와 안전한 report name을 검사 | NaN duration/Inf exit/관찰시간 초과의 실제 preflight 3건 거절 |
| 동일 이름의 잘못된 관찰 World | WorldPartition이 로드한 비활성 UWorld도 맵 이름이 같아 `ObjectIterator`의 첫 항목이 실제 게임 World를 대신함. 필드뿐 아니라 카메라도 사라진 잘못된 표본을 만듦 | authority observer는 GameState가 있는 World를 유지하고 Client는 GameState/local PlayerController가 있는 World를 유지. peak count만으로 통과시키지 않고 근거리 수신·유효 카메라를 연속 검사 | 실패했던30초 접속과190초 late join을 같은 조건으로 재실행. world identity/candidate metadata와 `Relevance.json` 기록 |

새 거대 manager나 두 번째 생태 잔고를 만들지 않았다. 기존 무리 coordinator·Native 실행 hook·M4 completion/receipt를 보완했다. 경로 제한은 **현재 Native 지상 backend의 예산**이며 장거리 MMO 경로 전체를 같은 호출로 지원한다는 뜻이 아니다. 긴 길은 검증된 구간/계획 계약으로 나누는 후속 작업이 필요하다. 현재 owned route는 그대로 유효하다.

## 전체 연결부에서 재확인한 사항

- Client는 authority Ecology/HerdMigration/Native 개체 writer를 생성하지 않고 수신 Actor/DTO를 소비한다.
- Field는 기존 셀의 양/수분/스트레스를 표시한다. 독립 food balance, BP Tick 섭식, AnimNotify의 중복 피해/섭식은 추가하지 않았다.
- 이주 의도와 기존 긴급 위협/안전 우선순위는 단일 Native control/movement writer에 남긴다. 실제 지역 진입과 route 끝 정착은 다르다.
- M4 자원 식은 `Before - Consumed + Grown - EnvironmentLost = After`이며 늦은 은신처의 capacity/food 조정 거래도 보존한다.
- habitat/경로의 지면 질의는 GT에서 기존 처리 경계를 따른다. Mass processing 중 Field gather를 실행하지 않는다.
- 저장된 BP 6개·재질 soft reference·날씨3/서식지9·기존29점 경로를 새 프로세스에서 확인했다. 원본 팀 맵/에셋에 저장하지 않았다.
- V1/v3 차원·가중치·mask2, SocialControl=0, 다른 맵의 opt-in은 바꾸지 않았다. soil-v1의 Python parity/재학습은 여전히 별도다.

## 검증 결과와 재현

최신 공유 근거는 [통합 점검 JSON](Evidence/IntegrationReview_20261023.json), [실제 PIE 화면](Evidence/IntegrationReview_PIE_20261023.png)이다. 원시 로그는 `Saved/IntegrationReview_20261023`이다. 마지막 C++ 빌드는 직접 `UnrealBuildTool.exe`의 `Milestone_Final_20261023_154448.log` Succeeded이며, 이후 C++/빌드 입력 변경은 없다.

전체 자동화 `Automation02`는 **213개: 212 Success + 기존 예상 missing-save warning 1, 실패/미실행 0**다. 기존 209개와 새 회귀 4개를 함께 실행했다. `Automation01`의 새 테스트 fixture에는 경로 Actor가 빠져 처음 실패했다. 제품 조건을 완화하지 않고 실제 route fixture를 추가한 뒤 전체를 다시 통과했다. Unreal이 이 실패에서도 exit0으로 끝났으므로 **export JSON의 failed/notRun/inProcess와 실행 개수를 판정 기준**으로 사용했다.

engine-free evaluator를 변경한 헤더로 재컴파일해 seed 11/23/47 × OFF/비/건조/초지 침수, 각600초를 다시 실행했다. ON 수지 오차는 약7.67e-13 이하다. 이 별도 flat 기준 세계의 사슴은 모두600초 내 멸종했다. terrain/Social/통합 wild 설정이 다른 평가이며 production 생태 균형이나 서버 성능 통과로 해석하지 않는다.

실제 PIE는125초 관찰·정상 종료하고 사슴/풀/비의 화면을 확인했다. 강수/food/개체를 강제하지 않고 저장 BP 기후를 실행했다. Dedicated/복수 Client의 최종 과정·수치·exit는 공유 JSON을 따른다. 이전 BP 구축 단계 증거는 [EcosystemBP_20261023.json](Evidence/EcosystemBP_20261023.json)으로 보존한다.

최종270초 Dedicated와 두 Client는 모두 exit0으로 정상 종료했다.210초 상세 표본의 먹이·소비·성장·환경 손실과 M4 장부 차이는 모두0이었다. 실제 지역 이전5건, 전체 서버 로그의 여정 완료4건을 기록했고,190초 late join은 이전한 stable ID 4개의 Forest 표현을 수신했다. 여정 완료는 구성원 사망을 포함할 수 있으며 이 한 실행의 횟수로 성공률/장기 안정성을 비교하지 않는다. 두 Client는 각각3지역을 실제 평가했고, 근거리 검증34/30개 표본에서 grace 이후 누락/카메라 소실0, authority 개체/Native Step/이주 Subsystem0이었다.

```powershell
# 프로젝트 루트 AdaptiveEcosystem/ 기준. 먼저 모든 engine/build 종료를 확인한다.
& ./Tools/Integration/build_integration_milestone.ps1 -Milestone Final
& ./Tools/Editor/test_vegetation_network.ps1 `
  -Map /Game/JYU/Maps/LV_JYU_Ecosystem -AuthoredWeather `
  -AuditFolder IntegrationReview_20261023 -Duration 210 -ExitAfter 270 -ClientBAt 190
```

실행 중 UBT/에디터를 중단하거나 빌드를 중복 실행하지 않았다. 검증 스크립트의 Python은 관찰/에셋 authoring 용도이며 게임 런타임 추론이 아니다.

## 식생 관심 범위의 추가 점검

첫18초 Client 표본에서는 시작 지역의 field만 받다가 지역 전환 후 공백이 기록됐다(`InitialClientA_18s.json/log`). 초기 짧은 왕복에서는 재현되지 않았지만 같은30초 접속을26초 관찰하자 **카메라까지 None인 잘못된 World 표본**으로 재현됐다(`WrongWorldClientA_26s.json`, `WrongWorldRelevance.json`). 실제 C++ weather presenter는 동시에 정상 게임 World의 카메라를 기록하고 있었다. 이름만 같은 `UWorld` 첫 항목을 선택하던 도구를 고쳤으며, 관찰 대상의 경로와 동일 이름 후보의 Controller/GameState 유무도 기록한다.

Client 관찰을26초로 늘리고 `validate_vegetation_relevance.py`로 실제 서버 field 원점·거리와 Client 카메라를 대조한다. 연결/지역 진입 후3초 grace를 지나 **가까이 있어야 할 field의 누락**을 검사하고, 두 Client가 각2개 이상 지역을 실제 평가하며 전체3지역을 수신해야 통과한다. 멀리 있는 field의 추가 수신을 실패로 보지 않는다. 별도120초 왕복 시험과 최종270초 시험은 모두 통과했다. 최종 Client 기록에는 동일 이름의 World가50개 안팎 있었지만 실제 Controller/GameState를 가진 관찰 World는1개였다. 이것은 장거리/손실 네트워크나 cold-cache 접속 전반의 보장은 아니다.

실제 기록에서 ClientA의 Barren field만 제거하고 기존 peak count/`passed` 값을 유지한 fault fixture도 검사했다. 새 validator가 누락12개 표본을 찾아 exit1로 거절했으므로, 과거 한 번 받았다는 이유로 지속적인 누락을 숨기는 판정을 방지한다. 게임/서버 자원을 바꾼 실험이 아니라 Saved의 기록에만 오류를 주입한 검증이다. 거리 밖 field의 해제/재생성은 정상 동작으로 구분한다.

## 남은 개선과 재개 경계

1. 돌아갈 수 없는 이주 계획의 최종 회수/종료 계약이 필요하다. stage 밖 body의 이동 guard를 무조건 해제하면 다음 Native Step이 몸을 clamp할 수 있어, 단순 timeout/teleport로 고치지 않았다. 기존 실패/복귀/사망 정리는 보존했다.
2. 목적지 회복 전망과 제한된 장소 지식, 실제 수원 장면, 전용 shrub/riparian 외형·식생 차폐 연결이 남아 있다.
3. 장기 경험/흔적, 조건부 자연 출생·유전·체형, 전체 생태 저장/복원은 전체 상태표의 미구현 범위다. 기존 이벤트/초기 스폰의 이름을 자연 출생 증거로 취급하지 않는다.
4. inherited HLOD/Editor AnimGraph 로드 경고, NavMesh 미존재, cook/패키징, 실제 서버/Client p95·대역폭과 여러 seed 장기 균형은 별도 검증한다.

이번 검토에서 수정한 경계는 직접 Source와 테스트/장면 결과로 확인했다. 모든 미구현 기능이나 저장소의 모든 코드에 오류가 없다는 선언이 아니다. 다음 변경도 현재 계약·단일 writer를 유지하면서 실제 재현 조건으로 수정한다.

## life-v1 구현 후 재점검

위 Pending과213개 수치는 첫 soil 통합 당시 이력이다. 후속 구현/최신 실행은 [life 계약](ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md), [상태표](ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md), [최종 evidence](Evidence/EcosystemLife_20261023.json)를 따른다. 다른 팀 소스도 실제 공유 계약에 필요한 범위에서 수정했고 원본 팀 맵/모델 가중치는 유지했다.

| 확인한 오류/경계 | 최종 수정과 이유 |
|---|---|
| 반복 이주 복귀가 영구 retry가 될 수 있음 | 기존 실패 경로에 Abandoned와 stranded를 연결했다. 밖의 몸을 clamp/teleport하지 않고 예약을 정리한다. |
| 지면 trace가 Pawn을 지면으로 오인 | 실제 static ground projection 계약을 사용한다. 사용자/몬스터 몸 위에 출생하거나 feet가 뜨는 것을 막는다. |
| 감지에서 지면 Z를 눈높이로 사용 | 실제 eye 위치로 시각 LOS를 확인하고 피해 식별에도 식생 차폐를 적용한다. 수면 중 시각 경험도 차단한다. |
| 빠른 접근을 실제 소음 사건으로 기록 | FastApproach를 분리하고 실제 Player.Footstep emission만 청각 근거로 읽는다. Unknown 피해의 원인은 후속 소리로 덮어쓰지 않는다. |
| 포식 보상 중복/원격 식사 가능성 | M4 확정 뒤 사체 영양을 분할하고 실제 접촉 섭취·TTL·issued/consumed/wasted/remaining 수지로 검사한다. |
| 새 자식에 성체 fat reserve가 무상 생성 | NaturalBirth adoption은 Energy=.4/Reserve=0으로 초기화한다. initial/recovery 및 OFF 동작은 보존하고 회귀 검사를 추가했다. 수정 전 장기 수치는 최종 결론에서 제외한다. |
| 보존 중 어린 사체 크기 증가 | 사망 시각의 성장 scale로 고정한다. 살아 있는 개체의 성장/복제는 유지한다. |
| 새 프로세스의 은신처 등록 index가 바뀌면 정상 저장 거절 | 저장 cover 순서를 유지하고 실제 geometry/높이/등록에 재결합한다. 달라진 실제 은신처는 여전히 거절한다. |
| 사체 행을 living cap에 계산 | 저장 행 상한과 살아 있는 인구 상한을 분리한다. 실제 회복 fixture의 사체 포함 복원으로 검증한다. |
| 저장 시 미확정 죽음/단계 역행/배열 표적 재사용 | 완료 경계 저장·뒤로 가는 live load 거절·native adoption ordinal 저장·새 discontinuity revision·일시 target index 폐기로 처리한다. |
| 빈 종 운영 보충을 자연 출생으로 혼용 | 별도 명시 요청·Origin=Recovery·부모0/세대0·기존 예약·cooldown으로 분리한다. 실제 권위 근접 공격으로 빈 종을 만든 뒤 시험한다. |
| cook 성공 뒤 동적 날씨 FX/소리 누락 | owned PrimaryAssetLabel에 실제 soft/string 의존성을 명시하고 다시 cook/실제 package 렌더를 검사한다. 원본 날씨 에셋은 수정하지 않는다. |
| label/registry만으로 실제 cook을 보장하지 못함 | UE5.8 기본 PrimaryAssetLabel type은 editor-only라 AlwaysCook 의존성을 끌어오지 않는다. DefaultGame의 type scan을 non-editor-only로 설정해 개별 label 규칙을 적용한다. 다른 label의 Unknown/Map 규칙·/Game scan은 유지한다. 실제 ReferencedSet와 package load를 함께 판정한다. |
| 은신처 FacingArrow의 패키지 template 누락 | 일반 default subobject 대신 엔진 표준 CreateEditorOnlyDefaultSubobject로 생성한다. 에디터 방향 표시는 유지하고 cook에서 BP의 editor-only override도 제거한다. 실제 CDO 회귀 검사를 추가했다. |
| 장기 관찰기가 종료 직전 마지막 sample을 누락 | 실제 마지막 NativeStep 표본을 추가한다. 요청1800초와 관찰1792초를 같은 결과로 기록하지 않는다. |

새 테스트를 통과했다는 이유로 자연 평형·유익한 진화·500/1000마리·새 종 backend를 보장하지 않는다. 지원/제약과 남은 RL·아트 인계는 [최신 인수인계](ECOSYSTEM_LIFE_HANDOFF_20261023.md)에 남긴다.
