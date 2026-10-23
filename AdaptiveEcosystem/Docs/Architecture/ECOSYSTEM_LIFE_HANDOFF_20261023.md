# life-v1 재개·팀 인수인계

원래 checkout `codex/social-shelter-handoff`, 기반 HEAD `ecfd82f`의 로컬 구현이다. Source/Content/문서는 미커밋이며 push/PR/merge는 수행하지 않았다. 시작 시 사용자 변경은 보존했다. 원본 팀 맵이 아닌 **`/Game/JYU/Maps/LV_JYU_Ecosystem`**만 authoring했다.

현재 결과/수치는 [상태표](ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md), 실제 실행 순서·API·저장 제한은 [life-v1 계약](ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md), 에셋은 [BP 안내](JYU_ECOSYSTEM_BP_SETUP_20261023.md), 최종 계측은 [증거 JSON](Evidence/EcosystemLife_20261023.json)을 우선한다. soil/BP/첫 review 문서의 과거 Pending은 당시 상태다.

## 처음 실행

루트 AGENTS.md·PROJECT_CONTEXT와 실제 `git status`를 읽는다. UE5.8에서 위 맵을 열고 Play한다. 저장된 vegetation/life opt-in, SocialControl=0을 사용하며 V1/v3 가중치를 바꾸지 않는다. F는 실제 근접 공격, Tab/기존 Inspector는 개체, M/대괄호는 기존 이주 표시다. 운영 명령은 `eco.Ecosystem.Save Slot`, 새 프로세스에서 `eco.Ecosystem.Load Slot`, 빈 종 복구는 `eco.Ecosystem.Recover Forest Wolf`다. 복구는 자동 보충이 아니다.

프로젝트 폴더의 `Tools/Editor/run_ecosystem_validation.ps1`, `run_ecosystem_life.ps1`, `test_vegetation_network.ps1`, `package_ecosystem.ps1`이 실제 재현 도구다. UBT/Editor/LiveCoding/dotnet/MSBuild/ShaderCompileWorker 실행 중 새 빌드를 시작하거나 중단하지 않는다. 각 도구는 busy 거절 및 정상 종료 대기를 사용한다. 엔진이 쓰는 외부 캐시 권한이 필요하다.

## 기획 §1–27과 현재 범위

| 원래 세부 기획 | 실제 연결/남은 경계 |
|---|---|
| §1–3 아키텍처·시간 | 기존 Native 단일 writer→완료 경계→M4 receipt. 서버 simulation time, 제한된 catch-up/스캔·큐·TTL. |
| §4–6 지형·수분·식생·상호작용 | FoodGrid 수분/내성/성장·손실·섭식, 실제 지면/얕은 수원, Field ISM/시야 차폐. 완전한 수리/식물 아트는 별도. |
| §7 장소·이주 | 지연된 제한 보고·회복 전망·위험/혼잡·기존 Travel·실제 context 이전, 복귀 실패 종료/no teleport. |
| §8 사람 경험 | 실제 시야·발소리·속도·피해·목격→개인 기억/지역 위험→규칙 반응. Unknown과 공유 증거 분리. |
| §9–10 사냥·흔적 | 제한 공간 흔적·조사/포기·역할 lease·실제 이동/LOS 포획·사체 접촉 영양. 새 후각/임의 몬스터 전투는 없음. |
| §11 다양성·출생 | founder/inheritance·부모/세대/비용·실제 예산/자리·후손 기여. 반복 cohort 관찰은 유익한 선택/평형의 증명이 아님. |
| §12 체형·표현 | 실제 능력/대사/접근 반경과 uniform scale·stride·기존 ABP/IK·Bubble. 실제 리그 Morph가 없어 새 bone 비율은 미지원. |
| §13 생활 리듬 | 기존 Wild1 낮밤/수면/휴식·날씨를 보존하고 수면 중 새 시각 기억을 금지. 새 계절/질병 세계는 범위 밖. |
| §14 추가 확장 | 핵심 흐름 우선. 질병·종분화·수중/비행·분산 서버는 활성화하지 않음. |
| §15–16 규모·운영 | 제한 큐/공간 후보/표현 LOD, 같은 빌드 checkpoint, 명시적 빈 종 운영 복구/게임 포획 상한. MMO 서비스/loot/퀘스트 구현은 별도. |
| §17–20 설정·검증·제품 결정 | 기존 DA/backend 설정, opt-in과 unsupported 조합 거절. 실제 장면/negative gate/계측·RL 담당 인계. |
| §21 종 독립 능력 | 기존 SpeciesAI 데이터/능력/backend 경계 유지. life-v1 Native 사슴/늑대만 검증. 새 종은 profile뿐 아니라 consumer/몸/공격/네트워크 acceptance가 필요. |
| §22 욕구·경합 | 기존 graze/cover/sleep/threat와 새 생식·영양·호기심/이주 우선순위 연결. 임의 종의 영역 방어/일반 전투는 미지원. |
| §23 정보·인과 | 직접/공유/TTL·Unknown·실제 damage 식별, 신호를 좌표 정답으로 승격하지 않음. |
| §24 변경·복구 | 같은 build/map/model/schema 검사, 원본 보존, transient 취소·실제 은신처 재결합·rollback 거절. cross-build 변환은 미지원. |
| §25 가독성·공정성 | Activity/Inspector 원인·몸 크기/풀/물/흔적 표시, 서버 거리/LOS/쿨다운. 새 UI 아트·전용 어린 개체 리그는 별도. |
| §26–27 실험·자료 | 실제 seed/시간/프로세스·Raw Saved와 작은 공유 evidence를 분리. 출처 문서는 설계 참고이며 구현 증거로 간주하지 않음. |

## 실패를 다시 만들지 않기

- Google Drive 동기화가 과거 빌드 출력/UHT 타임스탬프를 잠갔다. 사용자 정상 종료 후 빌드했고 파일 삭제·프로세스 강제 종료로 우회하지 않았다.
- 잘못된 동명 UWorld 선택은 도구 오류였다. 실제 Controller/GameState와 owner World를 검증하는 관찰기를 유지한다.
- 저장 당시와 다른 은신처 등록 순서는 영속 identity가 아니다. saved cover 순서를 보존하고 실제 geometry/registration에 재결합한다. 진짜 geometry 변경은 거절한다.
- 사체 포함 행 수와 살아 있는 인구 cap을 혼용하지 않는다. 미확정 Native 사망은 다음 완료 경계에 저장한다.
- 출생 시 Energy=.4뿐 아니라 초식 Reserve=0을 지킨다. 이전 `LongSeed*`/`Extended*` 결과는 이 수정 전 이력이고 최종 생물학적 결론에서 제외한다.
- 런타임 string/soft 참조의 날씨 FX/소리는 cook 의존성이 필요하다. owned PrimaryAssetLabel을 제거하지 않는다. package 성공과 실제 렌더 smoke를 각각 확인한다.
- UE5.8 기본 PrimaryAssetLabel type은 editor-only여서 label의 AlwaysCook만으로는 실제 에셋이 cook되지 않았다. DefaultGame의 type scan 설정과 ReferencedSet·실제 load를 함께 확인한다. registry에 이름이 있다는 것만으로 통과시키지 않는다. 은신처 FacingArrow는 CreateEditorOnlyDefaultSubobject를 유지한다.
- 직접 NetDriver 초당 카운터0을 무통신으로 읽지 않는다. 이번 대역폭은 실제 누적 total byte와 관찰 wall time의 차분으로 계산했다. 서버 frame pacing·Native CPU·CSV 계측 scope와 QA 기록 비용도 구분한다.
- `setup_jyu_ecosystem.py`로 맵을 재생성하지 않는다. 소유 actor/metadata를 확인해 필요한 부분만 갱신한다.

## 후속 담당 작업

RL 담당은 실제 learning snapshot·규칙 차이를 받아 전체 life 세계 Python mirror/평가/새 모델을 합의한다. [기존 RL 요청](../RL_Policy/TEAM_REQUESTS_V3.md)을 따른다. leaf soil parity와 전체 궤적 parity를 혼용하지 않는다. 모델을 새로 넣을 때도 기존 관측 슬롯 의미/가중치를 몰래 바꾸지 않는다.

아트/애니메이션은 현재 prototype shrub/riparian·이동 마크·성체 리그 축소를 전용 자산으로 바꿀 수 있다. 실제 collision/능력/stride/IK/LOD·패키지 의존성을 다시 검사한다. 추가 규모는 현재 인구 제한에서 단계적으로 계측하며 500/1000마리 지원을 선포하지 않는다. 이번 결과를 저장소 모든 코드의 무결함 보증이나 자연 생태 평형으로 설명하지 않는다.
