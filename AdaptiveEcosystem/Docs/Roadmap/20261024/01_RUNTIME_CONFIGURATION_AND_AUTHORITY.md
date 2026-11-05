# T01. 실행 구성·권위·정책별 상태 소유권

상태: 개발 명세 초안 / 기준: M4 `8836558` / 책임 제안: 원준, 권신혁·조연우·World 담당 공동 검토.

공통 규칙·검증 기록은 [전체 안내](README.md)를 따른다. 확인 항목: [F01·F02·F03·F08·F17](99_DECISIONS_AND_CONFIRMATIONS.md).

## 1. 목적과 필요성

V1·SpeciesAI·v3가 같은 저장소에 존재해도 개체 하나가 둘 이상의 이동·대사 경로에서 처리되면 안 된다. 맵·template·backend·옵션이 고정되지 않으면 이후 네트워크 실패와 정책 차이를 구분할 수 없다. 먼저 실행 구성과 상태 소유권을 재현 가능한 형태로 고정한다.

## 2. 현재 구현과 공백

| 확인한 구현 | 남은 업무 |
|---|---|
| Creature와 Box는 별도 coordinator이며 혼용 가드가 있다 | 공식 검증 맵의 실제 조립 상태 기록 |
| v3 Client composition은 표현 fragment 추가 후 반환한다 | packaged/late join에서도 논리 0인지 확인 |
| Client가 양쪽 v3 canonical template을 미리 등록한다 | 실제 TemplateID·시작 순서·에셋 로딩 진단 |
| v3는 기존 대사·섭식을 배제하고 M4 결과 회계를 사용한다 | 정책별 writer 표와 안전 commit 순서 문서화 |
| 전역 기본 V1, v3 SocialControl 기본 OFF | Root·이후 협업 요청의 차이를 F02/F03로 결정 |

현재 단일 runtime 모듈을 유지하며 AnimGraph 제작은 별도 Editor 모듈이다. Editor 모듈 추가를 Client 논리 모듈 추가로 해석하지 않는다.

## 3. 범위

포함: 읽기 전용 구성 감사, 시작 검증, runtime 구성 manifest, authority/template 진단, 모델·환경 옵션 기록.

제외: PPO 수치·가중치 변경, Social 기본값 변경, 원본 맵 자동 수정, Bootstrap 가드 삭제, 서로 다른 정책의 Trait 병합.

## 4. 구성 manifest 제안

다음은 새 진단 산출물의 논리 필드이며 현재 API 이름이 아니다.

| 필드 | 기록할 내용 |
|---|---|
| Run/Build | RunId, commit, UE 5.8, 빌드 종류·프로토콜 판 |
| World | 맵 경로, NetMode, WorldEpoch, coordinator 종류/개수 |
| Backend | V1/SpeciesAI/v3, 종별 Config 경로·TemplateID |
| Writers | Transform/Velocity/Vitals/Food/Death/Summary별 최종 처리자 |
| Policy | 내장/로더 모델 ID·계약 해시·관측 차원·마스크 판 |
| Options | SocialControl, ShelterSafe, ProtectedRefuges, Weather, Foliage, EnvWatch, AutoAdapt |
| Limits | 세계·지역 개체 상한, 연결 relevance/Actor/Add 예산 |
| Authored inputs | 지역 ID·종 ID·스폰/은신처·줄기·환경 Adapter |

Client는 모델 파일이나 가중치를 받지 않는다. F17이 채택되면 서버 모드/모델 ID 같은 작은 메타데이터만 표시한다. manifest의 local path나 절대 경로를 접속자에게 무조건 전송하지 않는다.

## 5. 필수 writer 구성

| 경로 | 판단·제어 | 이동·생존 소유권 | 공통 소비 |
|---|---|---|---|
| Box | 기존 Box 경로 | 엔진 이동 + Box lifecycle | Ecology·Bubble |
| V1 Creature | V1 Raw → Social 의도 | 기존 초식 Steering/늑대 경로·생존 adapter | 공통 Death·Food·Summary |
| SpeciesAI | Utility/StateTree Activity | 종별 Nav·ground movement, 공통 생존 | 기존 예약·공격 결과·Summary |
| v3 Creature | Native 요청·Arbiter·세계 규칙 | Native 단일 이동·대사·공간 먹이 | 공통 Death·인구·공간 receipt·Bubble |
| Client | 수신 결과만 | 보간된 표현 Actor, 논리 적분 없음 | 로컬 AnimBP·오디오 |

표는 종별 실제 Query·Tag까지 대조한다. 예를 들어 v3에 V1 HerbivoreTag나 SpeciesAI 이동 Tag를 붙여 기능을 결합하지 않는다. v3 Social을 켜는 별도 실험은 이동 writer를 늘리지 않고 기존 control hook만 사용한다.

## 6. 시작·실패 처리

1. 맵을 읽고 coordinator가 하나인지, RegionId가 유효·고유한지 검사한다.
2. Network Bubble 등록과 서버/Client template 등록을 완료한다.
3. 정책별 필수/금지 fragment와 혼용 가드를 검사한다.
4. 서버는 환경·지면·인구·자원 초기화 후에만 Ready를 올린다.
5. Client는 template 지연 Add를 기존 큐로 재시도하되 잘못된 Config를 자동 생성해 숨기지 않는다.
6. 실패는 구체 원인과 Config/TemplateID를 기록하고 해당 runtime을 Ready=false로 둔다. 다른 backend로 조용히 전환하지 않는다.
7. EndPlay/맵 이동에서는 template 대기·callback·폴더 감시·모델 상태·관찰 버퍼의 world 수명을 정리한다.

## 7. 구현 작업 순서

- T01-A: 현재 맵 후보를 읽고 manifest 필드·writer 표를 작성한다.
- T01-B: 기존 ValidateEditorSetup/RegisterTemplates 검사와 중복되지 않게 누락 진단만 추가한다.
- T01-C: 시작 로그에 유효 backend·실제 옵션을 남긴다. CVar 기본값과 실행 중 최종값을 구분한다.
- T01-D: F02/F03 결정은 계약 변경 기록과 필요한 RL 골든 범위를 함께 남긴다.
- T01-E: 빌드·최소 Standalone/서버+Client에서 각 backend를 독립 검증한다.

## 8. 검증 시나리오

| ID | 조건 | 기대 결과 |
|---|---|---|
| RC01 | v3 서버, Client에 v3 실행 인자 없음 | canonical proxy 생성, Client 논리 0 |
| RC02 | 잘못된 종별 Config/서버 Tag가 섞인 Client | 시작 검사가 원인과 함께 거부 |
| RC03 | Box와 Creature coordinator 혼용 | 기존 가드가 거부 |
| RC04 | v3에 StateTree/엔진 이동 Tag 혼합 | 단일 writer 검사 실패 |
| RC05 | template보다 Add가 먼저 도착 | 대기 후 1회 생성, 제거된 대기 항목은 생성 안 함 |
| RC06 | 맵 이동 후 새 epoch, 같은 수치의 agent ID | 이전 world 버퍼·binding 재사용 안 함 |
| RC07 | AutoAdapt/Social 옵션 기본 실행 | 기록된 Source 기본값 유지 |

## 9. 완료 조건과 인계

모든 활성 경로에 구성 manifest와 writer 표가 있고, invalid composition을 거부하며 Client 논리 0을 실제 기록한다. T02/T03에 맵·Config·TemplateID·옵션을 넘긴다. T07/T08에는 생성·문맥 이전을 실행할 안전 경계를 넘긴다. 미결 F항목을 임의 값으로 채워 최종 통과 처리하지 않는다.

## 10. Source·계약 근거

- [Spawner와 설정](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.h)
- [template 등록·composition 검사](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureTemplateValidation.cpp)
- [v3 Trait](../../../Source/AdaptiveEcosystem/AI/Policy/EcoCreatureV3Trait.cpp)
- [v3 설정·활성화](../../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.cpp)
- [공통 실행 계약](../../Integration/M4_RUNTIME_INTEGRATION_CONTRACT.md), [SpeciesAI 책임](../../Integration/SpeciesAI/SOURCE_RESPONSIBILITIES.md)
