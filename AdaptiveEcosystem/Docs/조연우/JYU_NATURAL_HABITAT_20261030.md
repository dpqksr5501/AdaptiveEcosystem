# 자연 서식지·식생·실제 플레이 표현 후속

2026-10-30 작업 트리. 사용자는 식생/서식지뿐 아니라 이전 사진의 8개 항목 전체와 통합 레벨 재사용을 요청했다. 이전 [플레이 흐름 수정](JYU_PLAYFLOW_FIX_20261029.md)의 후속이며 원본 팀 레벨·기본 V1/v3 모델/관측 차원·SocialControl=0·Native 단일 writer를 유지한다. 아래의 구현·초기 실패·최종 제한된 검증 범위를 구분한다. commit/push/main 반영을 완료했다는 뜻은 아니다.

## 범위 추적

| 사용자가 지정한 항목 | 구현 | 확인 기준 |
|---|---|---|
| 먹이 배치 | 안정 seed의 연속 군락 + cell 내부 stratified jitter + 후보별 실제 지면/법선 + region/profile 재사용 | 실제 PIE·서버/Client 일치·저장 재진입 |
| 식물 외형 | Grass/Riparian/Shrub mesh, 건조/고산 profile 밀도/높이, 잔량에 따른 새싹/소모, 마른 비섭식 잔재 | 여러 생육/잔량 상태와 명확한 먹이 구분 |
| 먹는 모습 | 실제 Native intake에서만 local bite 증거·주변 tuft 감소, 실제 intake의 eating flag | 정지/이동/먹이 0과 애니메이션·표현 대응 |
| 은신처 모양·내부 행동 | 불규칙 수풀·돌 울타리 제거, 내부 자리/수용량/경계/휴식/재도주 | 가장자리 즉시 앉음 0, 내부 휴식과 위협 재접근, 야생 은폐의 포획 가능 |
| 수원·지형 | 불규칙 수면 mesh, 실제 depth fade/움직임, 수분/젖은 지면 및 생물군계 색 전이, 경사·단차·낙차·깊은 물 검사 | actual rendering shader·지면 높이·수면·수지 및 경로 |
| 밤·날씨 | 명시적 태그의 기존 광원/노출만 조정, moon hard shadow 완화, owned 비/눈 renderer 재질 | 읽을 수 있는 밤·발광 구슬 제거·단일 연출 writer |
| 개체 다양성 | 기존 Stag/Doe 전용 mesh/애니메이션 + 어린 개체 silhouette/head 비율 | 실제 표시/Client late join·성장 단계·기존 pooling |
| 이주 후 분포 | 실제 도착 이후 bounded local 분산 섭식, 개체별 목표 점수·실제 물/먹이·점유 경쟁 | 동일 seed drought 반복·분산/실제 인계·유한 자원/기아 기록 |

공통 [자연 계약과 조사 자료](../Architecture/NATURAL_HABITAT_CONTRACT_20261030.md), [레벨 담당 적용 순서](../Team/NATURAL_HABITAT_LEVEL_HANDOFF_20261030.md)를 따른다. 물 mesh를 자동 수원으로, 장식 풀을 자동 먹이로, 수풀을 무적 영역으로 취급하지 않는다.

## 구현/분류

- 프로필/명시적 ID·우선순위/지면 확인·범위·경사·수원 연결을 분리한 것은 레벨 재사용을 위한 구조 보완이다. 실제 식물 생리·동물 생태의 정밀 복제는 아니다.
- 경계 포함을 휴식 도착으로 보던 조건, 도주 반사의 반복 HIDE 진입과 종료 시 즉시 잠금 해제는 내부 접근/경계 시간을 끊는 원인이었다. 자연 opt-in에서 실제 내부 도착과 bounded approach를 사용하며 기존 보호 fixture는 보존한다.
- `bWildRefuges`는 늑대 진입/포획 후보를 강제로 제외하지 않는다. 은폐 깊이의 탐지 이점은 근사이며 수풀 내부에서의 실제 포획은 정상 결과다. 실제 바위 차단은 collision으로 authoring한다.
- 식생 배치/마른 잔재/물/지면 색/deer morph/조명/강수는 표현 또는 world input이다. 두 번째 자원·이동 writer가 아니다. AnimNotify가 먹이를 제거하지 않는다.
- 어린 개체는 저장소의 Doe rig와 별도 비율/AnimBP를 활용한 표현이다. 실제 fawn 전용 모델·성별 행동/교배/뿔의 계절 성장 모델을 새로 완성했다는 뜻은 아니다.
- 완전한 겹친 동굴 층·수영·유체/지하수·생물군계별 실재 종 전체·분산 서버·새 세계 Python mirror/재학습은 완료하지 않았다. 현재 지면 backend가 지원하지 않는 조합은 명시적으로 거절/보고한다.

## 중간 실행과 재검증 이유

1. 초기 전체 자동화 231개 = 230 Success + 기존 예상 warning 1, 실패 0. 이후 코드를 추가했으므로 이 수치를 최종 검증으로 재사용하지 않는다.
2. 초기 자연 profile 600 simulation seconds/seed23/포식자 OFF에서는 최종 144마리와 M4 식생 수지 일치를 확인했다. 이 실행은 포식/휴식 완성을 증명하지 않는다.
3. 첫 일반 PIE 165초에서 Stag/Doe/어린 외형, 불규칙 수풀·군락과 비 줄기를 확인했다. 밤이 과도하게 어두웠고 water shader alpha 연결 오류가 드러나 수정했다. 이 캡처를 최종 화면으로 제시하지 않는다.
4. 첫 PIE에서는 접근/경계/재도주는 관찰됐으나 내부 rest counter가 0이었다. 단순 성공으로 처리하지 않고 실제 반사의 재진입/해제 경로를 추적해 수정했으며 새 실행으로 확인한다.

초기 Raw 결과는 `Saved/NaturalHabitat_20261030`에 남긴다. 최종 실행은 `Saved/NaturalHabitatRelease_20261030`, 네트워크는 `Saved/NaturalHabitatRelease_20261030_Network`다. `Tools/Editor/run_natural_habitat_validation.ps1`의 모드별 실행은 engine/build가 없는 상태에서 정상 종료까지 기다린다. 개인 발표 산출물이 아니다.

## 반복 생태 실행

`Saved/NaturalHabitatRelease_20261030`에서 직접 UBT 성공 빌드 `022631`의 동일 AI/자원 규칙을 확인했다. 후속 transport/지면 태그 수정은 아래 별도 검증과 구분한다.

| 실행 | simulation seconds | 최종 생존 | 관찰한 출생 | 관찰한 지역 인계 | 내부 휴식 누적 step | 가장자리 휴식 step |
|---|---:|---:|---:|---:|---:|---:|
| Natural seed23 | 1800 | 123 | 102 | 5 | 857 | 0 |
| Natural seed47 | 600 | 99 | 5 | 3 | 280 | 0 |
| Barren 명시적 가뭄 seed23, 포식자 OFF | 600 | 96 | 9 | 25 | 0 | 0 |
| 포식자 OFF seed47 | 600 | 143 | 3 | 31 | 0 | 0 |

M4 잔량/용량/소모/생장/환경 손실의 최대 차이는 이 실행들에서 `5.69e-14` 이하의 부동소수점 오차다. seed23 자연 실행에서 은폐 안 포획 counter는 Forest 2/Barren 1/Highland 11이었다. 개체별 사본을 중복 합산하지 않고 context별 누적 최대를 사용한다. 내부 휴식 counter도 사라진 개체를 포함한 ID별 마지막 값을 사용한다.

가뭄은 Barren 먹이를 0으로 만들고 해당 지역 재생을 중단한 명시적 fixture이며 자연 가뭄 발생 검증이 아니다. 목적지의 오래된 개체 수 보고가 이미 도착한 개체를 누락하던 문제에 현재 committed population 하한과 보수적인 먹이 예산을 적용했다. 예산 부족은 `DestinationFoodBudgetInsufficient`로 보고한다. 도착지 과수용을 줄이는 대신 출발지에 남은 개체가 죽는 tradeoff가 있다. 이 가뭄 실행의 최초 Barren 48마리 중 마지막에 살아 있는 것은 5마리이며, 이를 모든 이주 개체 구제 또는 기아 해결로 설명하지 않는다. 유한한 자원·실제 경로·보고된 지식 조건의 수용 결정이다.

## 후속 검증에서 찾은 원인과 수정

- 첫 late join에서는 식생 actor의 전체 site 배열이 121–187 KiB bunch를 만들어 UE의 64 KiB 한도를 초과했다. Client actor 수만 보면 통과했지만 지역 ID가 None이고 식생/실제 자식 도착 검사는 실패했다. `FailedNetworkInitial`에 근거를 남겼다. 전송 한도를 늘리지 않고 최대 64 sampled cells/576 sites의 공간 chunk actor로 분리했다. Client에는 표현 DTO만 보내며 해제/재수신이 식량을 쓰지 않는다. 실제 재접속 실행으로 검증한다.
- 실 렌더에서 비 재질의 NiagaraSprites usage flag 누락으로 검은 기본 재질 사각형이 보였다. owned rain/snow 재질에 Sprite/Mesh usage를 명시하고 재생성했다. 단순 NullRHI authoring 성공을 시각 성공으로 보지 않는다.
- 두 번째 작은 레벨의 두꺼운 tagged static-mesh 바닥이 거대한 나무/바위 원판으로 처리되어 Native 용량이 0이 됐다. 최초 오류는 `Spatial food registration rejected`였으며 장부 가드를 제거하지 않았다. 명시적 지면 actor/component는 지면 backend가 다루고 obstacle disc 수집에서 제외한다. 실제 collision/경사/단차 검사는 유지하며 기존 obstacle 회귀 검사에 actor/component 바닥 사례를 추가했다.
- 별도 경로 검사에서는 최종 도착 높이도 확인한다. 같은 XY의 다른 층을 수평 경로 성공으로 보고하지 않는다.

최종 빌드/자동화·새 레벨·late join·실 렌더·저장 결과는 [축약 실행 근거](../Architecture/Evidence/NaturalHabitat_20261030.json)에 기록한다. 축약 도구는 누락된 결과를 성공으로 만들지 않는다. 미래 팀 통합 레벨·production streaming·새 cook/package·500/1000 규모 검증은 수행하지 않았다.

## 다른 레벨의 실제 실행

지면 수정 검증 빌드 `Milestone_Final_20261030_030326.log`는 직접 UBT 성공, 전체 231개 자동화는 230 Success + 기존 예상 warning 1/실패 0/미실행 0이다. 기존 LevelScan 회귀에도 두꺼운 actor-tag/component-tag 바닥을 포함했다.

`LV_JYU_HabitatTransferFixture`의 다른 지역 ID `TransferMeadow/Dunes/Summit`와 지면 Z=0/2500/6000cm에서 같은 공통 코드를 실행했다. 설정 조사 36 probe/미확인·겹친 지면 0, 각 지역 profile TemperateMosaic/Dryland/Alpine, 최종 실제 ground sites 5812/2578/3271을 확인했다. 사슴 24마리로 시작해 실제 출생 2마리를 포함한 26마리가 마지막 표본에 있으며 모두 소속 바닥 높이와 60cm 이내였다. 동일 XY의 도달 불가능한 +600cm 목표 거절도 통과했다. 서로 분리된 platform의 40초 PIE이며 산길 이동/모든 생물군계·팀 통합 레벨 검증은 아니다.

검증 도구의 첫 재로드는 `load_asset(World)`로 Python이 월드를 붙잡은 채 `load_level`을 호출해 Editor의 world-leak guard가 종료했다. 최초 로그의 해당 World reference chain을 확인했고, map asset을 미리 로드하지 않고 LevelEditorSubsystem으로 직접 여는 방식으로 수정했다. 엔진/벤더 실행 파일·장부/GC 가드를 바꾸거나 저장 에셋을 삭제하지 않았다.

## 최종 표현·복제 검증

최종 직접 UBT 빌드는 `Milestone_Final_20261030_031414.log` 성공이다. 이 빌드의 전체 자동화는 다시 230 Success + 기존 예상 warning 1, 실패/미실행 0이다. 기존 감지 4..5 bit를 외형에 재사용했던 오류는 미사용 6..7 bit로 옮겼으며 모든 감지/외형 조합의 독립성을 검사한다. 사슴 외형은 herbivore body에만 설정한다. 사망한 어린 개체의 외형 나이도 사망 시각에 고정한다. `FailedMorphInitial`은 수정 전 실패 근거다.

같은 빌드에서 transfer 맵을 다시 열고 실행해 위의 지면/프로필/26마리 결과가 반복됐다. Dedicated authority + 10초/95초 late join의 실제 Client 2개가 정상 종료했다. 두 Client 모두 세 지역을 수신했고 실제 카메라의 근거리 검사 164/29회에서 grace 이후 누락이 없었다. 동시 접속 관찰 약 28.3초, late join에서 실제 자식 ID160과 올바른 body scale을 수신했다. 외형 mesh/AnimBP·크기 payload 일치, Client 권위 개체/이주 subsystem/Native step 모두 0, bunch 크기 초과/장부 거절 0이다.

일반 PIE 165초/17표본도 정상 종료했다. 실제 Stag/Doe/어린 외형 및 intake에 따른 먹기 표현을 관찰했다. 아래 대표 캡처는 사용자 정리 요청에 따라 오전 재점검의 최신 화면으로 갱신했다. 풍경 전체의 완성도 또는 모든 biome의 종 라이브러리를 증명하지 않는다.

- [실제 얕은 수원과 부드러운 경계](../Architecture/Evidence/NaturalHabitat_20261030/Water.png)
- [해 질 무렵의 서로 다른 개체/불규칙 수풀](../Architecture/Evidence/NaturalHabitat_20261030/Day.png)
- [완화한 밤 조명/강수 표현](../Architecture/Evidence/NaturalHabitat_20261030/Night.png)

PIE 로그에는 `Leaking landscape physical material tasks` 엔진 경고가 남아 있다. 약 100초/160초 표본의 process physical memory는 4.14/4.20GB였고 정상 종료했지만, 이를 영구적인 누수 해결 또는 production streaming 검증으로 해석하지 않는다. 이 경고의 원인 수정은 이번에 완료하지 않았다. 원본 지형/에셋을 지우거나 엔진 가드를 끄지 않았다.

같은 최종 빌드에서 75초 시점의 144개체 checkpoint 저장/새 프로세스 startup 복원을 확인했다. 실제 복원 일치, 이미 시작된 세계의 live rollback 거절, 거절 뒤 상태 불변을 모두 통과했다. 이전 빌드의 저장 슬롯이 새 빌드에 자동 호환된다는 뜻은 아니다. 실제 byte 수/해시는 축약 근거와 Raw Save/Load report를 따른다.

## 사용자 요청 재점검 — 2026-10-30 오전

이전 결과를 복사하지 않고 `Saved/NaturalHabitatRecheck_20261030`과 `_Network`에 일반 PIE 165초 및 Dedicated+Client 2개를 다시 실행했다. 별도 검증 도구 `verify_natural_habitat_recheck.py`로 종료 여부 외의 실제 데이터도 대조했다. [재점검 근거](../Architecture/Evidence/NaturalHabitatRecheck_20261030.json)를 따른다.

- 사슴 표현과 Native 섭식량 931회 비교: 불일치 0. 각 지역의 실제 소비/성장과 browse 증거는 양수다.
- 완전한 어둠으로 관찰된 12개 지역·구간의 성장 누적 증가 0. cell별 식량/수분/스트레스 유효 범위 위반 0, M4 장부 최대 오차 `8.53e-14`.
- 사라진 개체를 포함한 ID별 마지막 counter에서 내부 휴식 119 step, 가장자리 휴식 0. 10초 snapshot 사이 짧은 휴식도 counter로 확인했다.
- Client A/B의 근거리 검사 164/28회에서 grace 이후 지역 누락 0. 실제 자식 ID159 수신과 외형/크기 일치. Client 권위 개체/Native step 0. 두 Client 동시 관찰 약 28.3초.

코드 감사에서는 **검사 보고서의 실제 설정 불일치**를 찾았다. 이동은 지역 프로필을 사용하지만 `CaptureHabitatAuthoringReport`는 경사 normal .65와 수심 40cm를 고정 사용했다. 보고서도 지역의 실제 이동 프로필을 사용하도록 수정했다. 로컬 생육 프로필의 식물 설정과 지역 이동 설정을 구분한다. 이는 진단 도구의 원인 수정이며 생태 균형 개선으로 설명하지 않는다.

직접 UBT `Milestone_Final_20261030_094607.log` 성공 후 transfer 맵에서 허용 수심을 메모리에서만 40→10cm로 바꾸어 deep-water 판정이 증가하는 회귀 검증을 통과했다. 값을 복원한 뒤 3개 높이의 기존 실행도 FINISHED다. 원본 profile 에셋은 저장하지 않는다. Transfer 도구/driver의 출력 폴더도 지정한 AuditFolder를 사용하도록 고쳤다.

이번 재실행에서도 Landscape physical-material-task 경고가 남았다. 이전 명시적 가뭄의 기아·장기 평형, 실제 팀 통합 레벨의 production streaming/cook, 다층 동굴/수영은 해결·검증 완료로 확대하지 않는다. 이번에 새 가뭄 실험이나 저장/복원 실험을 다시 실행한 것은 아니다. 재생/소모·휴식·표현/전송이라는 핵심 경로의 정상과 전체 생태 안정화를 구분한다.

## 최신 비주얼 평가와 산출물 정리

### 개체군·나이·성장의 자연스러움: 수정 전 진단

후속 구현은 [자연 개체군 계약](../Architecture/NATURAL_POPULATION_CONTRACT_20261030.md), [기획 대조](../Architecture/INDIVIDUAL_TRAIT_DESIGN_AUDIT_20261030.md), [실행 기록](JYU_NATURAL_POPULATION_20261030.md)을 따른다. 아래 동년 성체/불연속 전환 설명은 수정 전 진단이다.

사용자가 말한 자연스러움은 재질 품질보다 배치/연령 구성/개체별 성장과 행동의 차이다. 이 기준에서는 현재 구현이 완성됐다고 설명하면 안 된다. 재점검 첫 표본의 사슴 144마리는 모두 Born=-180인 같은 초기 성체 나이였다. Size gene은 약 0.9505..1.0491로 다르지만 크기 차이가 곧 나이 차이는 아니다. 이후 실제 출생 사슴 3마리의 Born은 약 61/91/127초로 서로 달랐다.

현재 Growth는 출생 후 180 simulation seconds 동안 0.75→1로 선형 증가하고 BodyScale/SpeedScale에 반영된다. 실제 동물의 성장 시간 또는 정교한 신체 성장 곡선은 아니다. 어린 외형은 Doe rig의 몸 비율/머리 scale을 바꾼 근사이며 growth .97에서 성체 Stag/Doe 외형으로 불연속 전환한다. 성체 외형 선택은 StableId hash이고 실제 성별·생식 조건을 모델링한 것이 아니다. 초기 혼합 연령 구성·노령 단계·어린 개체의 부모 추종/양육은 완료로 볼 수 없다.

식생도 토양·수분·온도·그늘과 군락 jitter에 반응하는 셀 자원/표현이다. 개별 식물마다 나이·발아·성숙·노화를 가진 개체 모델은 아니다. 무리의 회피/간격/이주와 내부 자리는 구현했지만 자연스러운 가족 구성과 연령별 무리 행동의 완성을 뜻하지 않는다. 초기 연령 분포, 성장 전환의 연속성, 연령별 사회 행동과 실제 군락의 자원 분포를 다음 구현·검증 대상으로 구분한다.

사용자의 비주얼 재확인/옛 캡처 정리 요청으로 최신 water/day/night 화면을 직접 확인했다. 수면은 아직 평평한 지면 위 색 얼룩처럼 읽히며 실제 물가 단면/퇴적·젖은 띠의 표현이 약하다. 넓은 지면 재질의 반복과 해 질 무렵의 긴 강한 그림자, 듬성한 풀 표본도 추가 art pass 대상이다. 밤/낮 구분과 Stag/Doe/어린 외형 구분은 개선됐지만 비주얼 완성이라고 표현하지 않는다.

`Saved`의 지정한 생태 실험 폴더 및 10월8일 Unreal 고해상도 캡처에서 오래된/중복 화면과 완료 보고서가 대체한 Progress JSON 89개를 정리해 122.87MiB를 확보했다. 각 파일의 절대 경로 범위·reparse 조상·exclusive open 가능 여부를 확인했다. 삭제 목록/크기/SHA256은 `Saved/EcosystemCleanup_20261030.json`에 남겼다. 최신 대표 3장은 위 Evidence 링크에, 최신 추가 시점/기본 뷰 3장은 `Saved/NaturalHabitatRecheck_20261030`에 남겼다. 예전 Raw JSON의 screenshot 경로는 당시 이력이며 정리 후 이미지 파일이 없을 수 있다. 최종 보고서·실패 로그·체크포인트·소스/Content/LFS는 보존했다. 이 정리는 디스크 산출물 정리이며 누수나 비주얼의 원인 수정이 아니다. 새 UBT/PIE를 실행하지 않았다.
