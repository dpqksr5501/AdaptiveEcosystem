# 자연 개체군·성장·세부 기획 반영 기록

2026-10-30, `codex/social-shelter-handoff` 작업 트리(시작 HEAD `ecb898e`). 사용자 요청의 자연스러움은 초기 배치·다양한 나이/덩치·성장·관계/생활·식생 군락을 뜻한다. [계약](../Architecture/NATURAL_POPULATION_CONTRACT_20261030.md), [기획 §1–27 대조](../Architecture/INDIVIDUAL_TRAIT_DESIGN_AUDIT_20261030.md), [최종 관찰 JSON](../Architecture/Evidence/NaturalPopulation_20261030.json)을 우선한다. 기존 작업 트리/원본 팀 에셋은 보존하며 이번 변경을 commit/push/main 완료라고 설명하지 않는다.

## 수정 분류와 실제 동작

- 초기 사슴 모두 Born=-180이던 문제는 profile 기반 혼합 연령/초기 성별 분포와 stable seed 순열로 수정했다. 유전 크기 차이와 나이 차이를 분리했다.
- 성숙 경계에서 외형 ID가 바뀌던 문제는 성별 ID 고정·권위 Maturity DTO·연속 비율 보정으로 줄였다. 뿔 전용 리그가 없으므로 owned Doe/Stag 상보적 마스크 전환은 **구조적 표현 우회**다. 실제 뿔/전용 새끼 아트 완성이 아니다.
- 부모/보호자와의 행동 연결 부재는 Native의 기존 Graze 안에서만 동행 간격/관찰 목표를 적용해 보완했다. 초기 무리의 사회적 보호자와 실제 부모 혈통을 구분한다. `Caregiver`는 보존하고 임시 동행 `FamilyObserved`를 별도로 둔다. 순간 분리로 가족이 바뀌지 않는다.
- food만으로 군락 전체를 비슷하게 표시하던 문제는 저장되는 cell cohort 발달·환경 적합 시간·guild별 속도·연속 emergence로 보완했다. 식물 한 포기마다 독립 생애가 생긴 것은 아니다.
- 기획 대조에서 빠진 개체별 Caution/Sociability/Coat의 제한 유전, 체격 분산 설정, 기존 Energy/HP 기반 살집, 자연 번식의 건강/기존 위협 조건을 추가했다.
- 사용자의 마지막 학습 담당 경계 지시에 맞춰 신규 Caution 도주/호기심 결정 보정은 제거했다. Caution은 데이터만 제공하고 기존 Memory.Decide/안전거리는 유지한다. 모델/관측/행동/보상/추론/학습 코드는 보존했다. Sociability는 이미 선택된 Graze 안의 혼잡/옆자리만 조정한다.

이것은 게임 세계/표현/개체 생명주기 개선이다. 새 정책 학습이나 전체 학습 세계 parity를 완료한 것이 아니다. Native가 유일한 이동·대사·섭식 writer이며 M4 장부/인구·기존 SocialControl=0을 유지한다.

## 실행 버전

최종 C++ 직접 UBT: `Saved/IntegrationBuilds/Milestone_Final_20261030_110338.log` **Succeeded**. 최종 실행 폴더는 `Saved/NaturalPopulationBoundary_20261030`와 `_Network`, 별도 레벨은 `Saved/NaturalPopulationBoundaryTransfer_20261030`이다. `NaturalPopulation*`의 이전 폴더는 작업 중 다른 빌드의 이력이며 최종 증거와 혼합하지 않는다.

처음 C++ 테스트의 include 순서/`FMemory` 타입 이름 충돌은 최초 compiler 오류를 확인해 수정했다. 빌드/Editor를 강제 종료하거나 중복 빌드를 시작하지 않았다. 사용자 학습 경계 지시가 온 때의 진행 중 PIE는 정상 완료한 뒤 다음 예약 검증 실행만 보류하고, 정책 보정 제거 후 최종 빌드를 다시 실행했다.

| 최종 실행 | 실제 결과 |
|---|---|
| 전체 자동화 | 234개 = 233 Success + 기존 예상 warning1, 실패/미실행0 |
| owned Ecosystem 실제 PIE165초 | 초기 사슴144 중 어린 개체36. 초기 나이70.66..1799.73 게임 초, 성별83/61. 유전 size0.9211..1.0790, speed0.9213..1.0790 및 Caution/Sociability/Coat 분산 확인 |
| 동일 ID 성장 | 실제9번 개체의 maturity 약0.557→1, BodyScale0.859375→0.953125. 원래 가족 관계 유지, 임시 관찰/동행 별도 |
| 권위/표현 대조 | 실제 표현1007건의 나이/색·성별/메시와 살아 있는 개체의 권위 나이 일치. 사체의 표현 성숙도는 사망 뒤 증가하지 않음 |
| 가족/휴식 | 관찰된37개체에 따라가기 누적. 이동 의도에 오래된 관찰 사용0, 가족 관계 재지정0. 누적 내부 휴식180 Native steps, 가장자리 휴식0. 어린 관목 은폐는 이번 짧은 실행에서 별도 성공 표본을 확보했다고 주장하지 않음 |
| 먹이/식생 | 관찰2700 logical cells의 development 유효 범위와 M4 food/성장/섭취/손실 장부 오차0 |
| Dedicated + Client2 | 실제 동시 접속30.156초. 근거리 지역 검사164/22표본에서 누락0, Client 논리/Native Step0. 늦은 Client가 자연 자식157/158/159 수신, 크기 불일치0 |
| 동일 빌드 저장→새 프로세스 | 144 living 개체의 나이/유전/혈통/가족·기억·장부 exact 복원. **2700 cells의 발달도/수분/스트레스/food/capacity exact 복원**. 손상/버전/missing·live rollback 거절 후 상태 비변경 |
| 별도 레벨 | TransferMeadow/Dunes/Summit의 Z0/2500/6000cm fixture 40초/5표본, 36지면 probe missing0. 지역별 얕은 물 한도와 도달 불가 높이 거절 확인. 팀 통합 레벨 acceptance 아님 |
| 학습 담당 경계 | 관측/정규화 계약·가중치·추론/기본 행동 설정12개 파일을 HEAD와 정규화된 텍스트/해시로 대조해 동일. V3 18관측/mask2·Native 단일 writer 유지, Caution의 정책 consumer 없음. 학습 폴더 diff 없음 |

Native batch p95는 이번 PIE 장면에서 약8.474ms/max14.753ms이며 전체 서버 frame CPU나1000개체 성능이 아니다. 기존 `Leaking landscape physical material tasks` 경고가 남아 있다. 메모리/production streaming의 영구 안정성 수정으로 설명하지 않는다. 단기 출생/이주 표본은 충분한 집단 분석 gate를 충족하지 않아 유익한 진화·영구 평형·기아0 결론을 내리지 않는다.

최초 최종 네트워크 검증은 늑대 주변 관찰 카메라와 자연 새끼의 거리가 약118..126m여서 새끼 relevance 범위를 방문하지 못했다. 게임 전송 오류라고 단정하거나 수신 필수 검사를 완화하지 않고, 명시적 `-ChildCoverage` QA가 실제 살아 있는 자식도 방문하도록 관찰 Pawn만 이동했다. 중간 도구의 `get_pawn` API 오류는 UE 헤더의 ScriptName `GetControlledPawn`을 확인해 수정했다. 각 실행은 정상 종료까지 기다렸고 실패 원시 증거를 `Saved/NaturalPopulationBoundaryNetworkFailure_20261030`, `Saved/NaturalPopulationBoundaryObserverApiFailure_20261030`에 보존했다. 마지막 재검증은 관찰25회의 실제 자식 방문과 late join 수신을 확인했다. 이 변경은 observer 범위/도구 수정이며 생태계나 전송의 root-cause 수정으로 부르지 않는다.

대표 화면: [혼합 연령 장면](../Architecture/Evidence/NaturalPopulation_20261030/MixedAges.png), [성장·체격·털색 장면](../Architecture/Evidence/NaturalPopulation_20261030/GrowthAndCoats.png). 카메라는 실제9번을 따라가지만 주변 다른 개체도 화면에 포함된다. 전용 새끼/뿔 성장 아트와 기존 회색 이동 흔적 placeholder는 최종 비주얼 완성으로 표시하지 않는다.

중간 검증의 생성 스크린샷24장(44.41MiB)은 정리하고 최신 대표2장을 해시 확인 후 위 Evidence에 보존했다. 삭제 전 경로/reparse·해시·exclusive open을 확인했으며 `Saved/EcosystemCleanupPopulation_20261030.json`에 기록했다. 실패/최종 JSON·로그·checkpoint·소스/Content/LFS를 정리 대상으로 삼지 않았다.

## 재현과 역할 인계

프로젝트 `Tools/Editor/run_natural_habitat_validation.ps1`의 `Population`, `Automation`, `PopulationPlay`, `Network`, `Persistence`, `Transfer`를 사용한다. `Population` authoring은 owned 자연 사슴/프로필만 변경하고 vendor 원본은 보존한다. `PopulationPlay`는 threat를 끈 관찰 Pawn/카메라만 옮겨 같은 실제 개체의 성장 화면을 본다. Python은 QA observer이며 런타임 추론이 아니다.

`verify_natural_population.py <AuditFolder>`는 실제 나이/성별·고정 가족 관계·관찰 TTL·외형/색 DTO·군락 발달·M4 수지·정책 차원/보존 파일을 독립 확인한다. 출생·부모 기여·분산과 이주 표본은 구분하고, 분석 gate가 미충족이면 집단 변화 결론을 유보한다. 이 도구가 유전/자원을 수정하지 않는다.

저장 검증은 같은 최종 runtime image의 실제 새 프로세스 복원이다. 다른 빌드/맵/설정 파일을 자동 변환하지 않는다. 초기 103204 빌드의 검증은 기존 자동화용 `NaturalHabitatRelease23` 슬롯을 재사용했다. 이후 도구는 AuditFolder별 슬롯으로 분리해 기존 검증 슬롯 재사용을 피한다. 사용자 운영 슬롯을 지우거나 LFS를 정리하지 않았다.

현재 새 package/cook·production World Partition lifecycle·다층 동굴·수영·부모 수유/구조·실제 뿔 계절/질병·임의 종 backend·신규 RL 세계 mirror/재학습을 검증 완료로 표시하지 않는다. 미래 팀 통합 레벨은 레벨 담당의 실제 지면/자원/동물/서버·Client acceptance가 필요하다.
