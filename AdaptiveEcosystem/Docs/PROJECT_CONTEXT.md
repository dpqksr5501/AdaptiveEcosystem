# 프로젝트 공통 맥락과 작업 시작 안내

갱신일 **2026-10-24**. 팀원과 각 AI agent가 대화 기록 없이 프로젝트의 목표·제품 방향·구현 경계를 이해하기 위한 공통 진입 문서다. 개인 담당 인수인계보다 먼저 읽고 작업 분야의 Source/계약으로 이어간다. 종 이름과 예시는 교체 가능한 표현이며 현재 구현을 과장하는 근거가 아니다.

사용자의 후속 전체 구현은 원래 저장소에서 진행해 **`d095948`**로 기록했다. 최신 시작점은 [팀 AI 공통 안내](Team/ECOSYSTEM_AI_COLLABORATION_20261024.md), [전체 상태표](Architecture/ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md), [life-v1 실행/팀 API 계약](Architecture/ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md)이다. owned `/Game/JYU/Maps/LV_JYU_Ecosystem`만 식생·경험/흔적·출생/유전/성장·사체 영양·저장/운영 복구를 opt-in한다. 아래의 soil 최초 구축·미연결 설명은 당시 이력이다. 기존 맵/기본 SocialControl=0·단일 Native writer·모델 차원을 보존하며 재학습/임의 종 지원 완료로 확대하지 않는다.

대화 없이 이어갈 때는 [life-v1 최신 인수인계](Architecture/ECOSYSTEM_LIFE_HANDOFF_20261023.md)의 §1–27 대응·직전 실패 수정·실행 도구·후속 경계도 읽는다.

서버·네트워킹 담당은 [역할별 서버 안내](Network/ECOSYSTEM_SERVER_NETWORK_AGENT_GUIDE_20261024.md), 학습 담당은 [역할별 RL 안내](RL_Policy/ECOSYSTEM_RL_AGENT_GUIDE_20261024.md)와 [실제 부분 예제](RL_Policy/Examples/README.md)를 따른다. [시작 프롬프트](Team/ECOSYSTEM_AGENT_START_PROMPTS_20261024.md)에는 작업 요청·검증·인계 양식이 있다. 2026-10-24는 Source/문서/샘플·링크 감사를 수행한 날이며 이전225개 자동화·PIE/멀티/패키지를 새로 실행한 날로 기록하지 않는다.

## 1 만들려는 게임 시스템

레벨 디자인 담당은 [레벨·지형·수원·배치 안내](Team/ECOSYSTEM_LEVEL_DESIGN_AGENT_GUIDE_20261024.md), 날씨 담당은 [권위 날씨·낮밤·연출 연결 안내](Team/ECOSYSTEM_WEATHER_AGENT_GUIDE_20261024.md)를 함께 읽는다. 두 안내에는 복사 가능한 AI 시작 요청과 담당별 acceptance가 있다. 장식 foliage/물/비와 실제 생태 입력, 지역 날씨와 Native 감각 날씨·Dark의 차이를 먼저 확인한다.

**MMORPG 환경을 고려해, 환경·식생·자원·몬스터 간 상호작용·플레이어 활동이 함께 작동하면서 개체의 행동·지역별 분포·개체군과 장기적인 집단 특성이 달라지는 동적 생태계를 만든다.**

플레이어가 없어도 먹기·포식·휴식·경쟁·이주·자원 회복이 돌아간다. 플레이어도 사냥·접근·소음·방문으로 그 안에 영향을 주는 존재다. 고정된 사냥터에 개체만 보충하는 시스템이나 생태계 관찰 전용 도구로 범위를 해석하지 않는다. 게임에서 원인을 읽을 수 있는 변화와 지속 가능한 사냥 콘텐츠를 함께 목표로 한다.

환경과 강수/낮밤 → 토양 수분과 식생/먹이 → 개체의 욕구·감각·기억 → 개체 행동과 무리 계획 → 단일 실제 실행 → 먹이 소비·피식·생존·이주/출생 → 지역 자원·개체군·경험과 후손 분포의 변화가 공통 흐름이다. 이 전체를 이미 구현 완료했다는 뜻은 아니다.

MMORPG는 적용 대상과 설계 조건이다. 이번 프로젝트가 완성된 MMO 서비스·cross-shard·운영 인프라 전체를 구현했다는 뜻은 아니다. 작업별 실제 동시 접속·개체 수·맵·시간·배포 범위를 정하고 검증한다.

## 2 사용자와 합의한 목표와 제안의 구분

| 방향 | 목표 의미 | 완료로 오해하지 말 것 |
|---|---|---|
| 자율 생태계 | 사람이 없어도 환경과 몬스터 간 상호작용이 변화의 원인 | 플레이어 사냥 압력만으로 모든 변화 설명 |
| 환경·식생 | 비/건조/낮밤과 지면 조건이 성장·먹이·서식 선택에 연결 | 물가면 모든 식물이 무조건 커짐, VFX가 직접 자원 생성 |
| 몬스터 생활 | 섭식·사냥·경계·탐색·휴식·무리 이동과 종별 활동 리듬 | 모든 개체가 상시 전투하거나 동일 시간에 같은 행동 |
| 플레이어 관계 | 무해 접촉의 익숙함과 반복 사냥의 위험이 지역/무리 반응에 반영 | 특정 한 계정만 회피, 모든 지역이 즉시 같은 사실을 앎 |
| 구체적 경험 | 목격한 급습/추격/노출 등 맥락이 이후 선택에 영향 | 전지적 원인 분석·플레이 중 PPO 온라인 재학습 완료 |
| 다양성과 장기 변화 | 개체의 크기/체형/성향 차이, 성장·유전·번식 결과 구분 | 살아 있는 개체가 피해를 받을 때마다 유전적으로 즉시 강화 |
| 간단한 출생 | 복잡한 교미/출산 연출 없이 조건부 스폰으로 새 개체 생성 | 죽을 때마다 새 세대, Actor 재생성이 새 출생 |
| 게임 지속성 | 과도한 멸종·빈 사냥터·악용을 진단하고 회복 정책 설계 | 몰래 자원/능력을 무제한 생성해 균형 완료로 주장 |

위 방향은 제품 맥락이다. 상세 계수·자료형·플러그인·판단 알고리즘은 [세부 기획](Architecture/DYNAMIC_ECOSYSTEM_DETAILED_DESIGN_20261023.md)의 제안이며 실제 작업 계약으로 채택·구현·검증하는 절차가 필요하다. 이 문서를 읽었다고 모든 기능을 한 번에 구현하거나 기존 기본값을 켤 권한이 새로 생기지 않는다. 현재 사용자의 작업 범위를 우선한다.

## 3 종에 독립적인 설계 원칙

현재 사슴·늑대는 초식/포식과 행동을 보여 주기 쉬운 검증 예시다. 목표 구조는 특정 이름·Mesh·Skeleton·현재 상태 enum에 묶이지 않는다. 다만 현재 Native 늑대/사슴 backend는 구체적 구현이므로 새 종을 자동 지원한다고 주장하지 않는다.

식성, 공격/적대 관계, 사회성, 이동 방식, 생활 리듬, 감각, 신체·전투 능력, 실행 backend를 분리한다. 육식이라고 항상 공격적이거나 무리 사냥하는 것은 아니며, 초식/비섭식 몬스터도 영역 방어나 적대 관계로 공격할 수 있게 기획한다. 관계는 상황·대상 종/진영/역할을 기준으로 평가하며 포식과 전투를 구분한다.

공통 질의·기억·계획은 capability를 보고 선택하고, 실행 adapter는 기존 Native/Movement/Combat 경로 하나에 연결한다. 종 설정에 없는 능력을 계획하거나 지원하지 않는 비행/수영/원거리 공격을 지상 늑대 실행으로 처리하지 않는다. 지원하지 않는 조합은 authoring 검증에서 거절하고 이유를 기록한다.

설정만으로 기존 종의 새 변형을 추가하는 경우와 새 이동·전투 backend를 구현해야 하는 경우를 구분한다. 새 종 추가 완료 기준은 [세부 기획 §21](Architecture/DYNAMIC_ECOSYSTEM_DETAILED_DESIGN_20261023.md#21-종에-독립적인-능력과-실행-계약)을 따른다.

## 4 작업에서 보존할 아키텍처

| 소유 계층 | 책임 | 금지되는 중복 |
|---|---|---|
| World/환경 | 지형·지역·인접성·권위 날씨/시계 입력 | 시각 날씨 BP에서 별도 Food/HP writer |
| Ecology/M4 | 자원·개체군·출생/죽음/이주 결과·요약 장부 | Native와 두 번 자원 생성/소비 |
| 개체 논리/선택된 실행 backend | 감각/관측·결정·실제 이동/대사/포획 | Social·BP·새 BT가 별도 위치 적분 |
| Social/무리 | 영속 정체성·경보·예약·공동 의도 | Herd를 단순 flock이나 복제 transport로 취급 |
| RL | 관측·행동·정규화·가중치·Python mirror 계약 | 문서 작업 중 schema/수치/가중치 임의 변경 |
| Representation/Client | 수신 위치·활동·체형/식생 요약의 표현 | Mesh·AnimNotify·client PCG가 논리 개체/먹이 생성 |

단일 writer는 모든 개체가 같은 클래스 하나를 사용해야 한다는 뜻이 아니라 **각 개체에서 최종 위치/자원 갱신 경로가 중복 실행되지 않는다**는 뜻이다. opt-in SpeciesAI의 지면 이동 writer와 v3 Native writer를 같은 개체에 겹치지 않는다.

설정 DA는 종/서식지/표현의 규칙과 허용 범위다. 개체의 유전·기억·욕구·정책 출력은 개체별 런타임 데이터이며 공유 DA/Shared Fragment의 한 값으로 덮어쓰지 않는다. 런타임 Python 추론과 외부 LLM 의존을 추가하지 않는다. 과거 LLM Trait Evolution은 신규 경로와 격리한다.

공통 계약은 관측 Snapshot → 의도 Request → 실제 Outcome → 장부 Receipt다. 안정 ID·epoch/sequence·단위·유효기간·생성/소비 단계·중복 방지·실패 정리 규칙을 함께 정의한다. 서버가 아는 사실과 개체가 지각한 증거, 개인 기억과 공유 정보, 원 증거 시각과 수신 시각을 구분한다.

## 5 현재 구현 기준을 확인하는 법

이 문서 작성 시 확인한 작업 branch는 `codex/social-shelter-handoff`, 코드 기준은 `581ce1d`(신호/표현/무리 이주)와 `e22dbbd`(이주 디버그), 통합한 main은 `a74fcac`다. 문서/기획 후속 커밋은 별도다. 이 기능이 모든 팀 branch/main에 이미 있다는 뜻은 아니다. 작업 시작 시 실제 branch/HEAD/Source를 확인한다.

- 원래 프로젝트 `AdaptiveEcosystem/AdaptiveEcosystem.uproject`, Unreal Engine 5.8. 단일 runtime 모듈을 유지한다.
- V1 7관측/4출력과 opt-in v3 R1b 18관측/5행동·mask2를 구분한다. 한 종의 모든 행동을 같은 PPO 구조가 이미 지원한다고 가정하지 않는다.
- 현재 통합 v3 SocialControl=0 신호 경로와 기존 행동 훅 opt-in을 유지한다.
- 기존 맵 이주 OFF, `/Game/JYU/Maps/LV_JYU_HerdMigration`은 ON. 알려진 Barren↔Forest corridor가 현재 검증 범위다.
- 통합 ShelterSafe=1 안전/ProtectedRefuges=1 생명주기를 구분하고 보호 규칙을 중첩하지 않는다.
- 다른 팀원이 만든 opt-in [SpeciesAI 경로](Integration/SpeciesAI/README.md)에는 UEcoSpeciesAIProfile, 공통 실행/이동/예약과 종별 구현이 있다. [파일 책임](Integration/SpeciesAI/SOURCE_RESPONSIBILITIES.md)·실제 Source와 [마일스톤](Integration/SpeciesAI/IMPLEMENTATION_MILESTONES.md)을 먼저 확인해 기존 기반을 재사용한다. 새 기획이 이를 대체하거나 현재 v3에 모두 연결됐다는 뜻은 아니다.
- 현재 상세 동작/PIE·Client 검증과 한계는 [조연우 최신 인수인계](조연우/JYU_CHAT_HANDOFF_20261023.md), [이주·신호 계약](조연우/HERD_MIGRATION_AND_SIGNAL_CONTRACT.md), 담당 분야 Source를 따른다.

오래된 문서의 main/HEAD/Pending/Draft/테스트 수는 날짜별 이력이다. Source는 구현 사실의 기준이며, 불변 원칙/활성 계약과 충돌하면 기록하고 해결한다. 현재 버그를 발견했다고 그 동작을 새 목표 계약으로 조용히 정당화하지 않는다.

## 6 팀원과 AI agent의 작업 시작 절차

1. 새 채팅/독립 작업 시작 시 [루트 AGENTS.md](../../AGENTS.md)와 이 문서를 읽는다. 작업 중 목표/분야/기준 commit이 바뀌면 다시 대조한다. 같은 내용이 이미 확인됐다면 불필요하게 모든 과거 문서를 반복 읽지 않는다.
2. 실제 branch·HEAD·로컬 변경을 확인하고 작업 분야의 Source/계약/가장 최근 검증 범위를 읽는다.
3. 이번 변경이 어떤 생태계 입력/판단/실행/결과를 연결하는지 정하고, 기존 소유 계층·단위·authority·단일 writer를 확인한다.
4. 구현/통합/실행 검증/제안/미지원 상태를 분리한다. 이미 있는 기능을 이름만 바꿔 재구현하거나 오래된 TODO를 현재 미구현으로 단정하지 않는다.
5. 교차 분야 계약 변경은 producer/consumer·실패/취소·저장/복제·parity 영향을 함께 적고 실제 작업 범위에 따라 연결한다. 미승인 외부 메시지 전송이나 새 전역 매니저 생성은 기본 절차가 아니다.
6. 새 C++/빌드 입력은 루트 UBT 규칙으로 검증한다. 문서만 바꾸면 링크/Source/diff만 확인하고 새 빌드/PIE 성공을 기록하지 않는다.
7. 결과에 변경 범위·검증 조건·한계·후속 연결을 남긴다. 기능별 계약은 해당 문서에, 프로젝트 목표 변화는 이 공통 문서에 반영한다.

## 7 분야별 다음 읽기

| 작업 분야 | 읽을 문서 |
|---|---|
| 전체 구조/실행 순서 | [종합 아키텍처](Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md), [Mass 순서](Mass/MASS_PROCESSOR_ORDER.md) |
| 환경/식생/자원/장소 선호 | [세부 기획 §4–7](Architecture/DYNAMIC_ECOSYSTEM_DETAILED_DESIGN_20261023.md), 실제 World/FFoodGrid/M4 거래 |
| 감각/경험/Social/공동 행동 | [세부 기획 §8–10/21–23](Architecture/DYNAMIC_ECOSYSTEM_DETAILED_DESIGN_20261023.md), [현재 Social](조연우/SOCIAL_BEHAVIOR_RUNTIME_CURRENT_STATE.md) |
| RL/새 Native 세계 | [V1](RL_Policy/POLICY_CONTRACT_V1.md), [v3](RL_Policy/POLICY_CONTRACT_V3.md), [팀 요청](RL_Policy/TEAM_REQUESTS_V3.md) |
| 출생/유전/체형/애니메이션 | [세부 기획 §11–12/21](Architecture/DYNAMIC_ECOSYSTEM_DETAILED_DESIGN_20261023.md), 실제 lifecycle/표현/Native 신체 계약 |
| 기존 종별 backend/StateTree 비교 | [SpeciesAI 시작](Integration/SpeciesAI/README.md), [파일별 책임](Integration/SpeciesAI/SOURCE_RESPONSIBILITIES.md), [PPO 비교 범위](Integration/MASS_STATETREE_PPO_COMPARISON_DEVELOPMENT_PLAN_2026-10-14.md) |
| 네트워크/저장/규모 | [세부 기획 §15–18/24–26](Architecture/DYNAMIC_ECOSYSTEM_DETAILED_DESIGN_20261023.md), 담당 transport와 생명주기 Source |

첫 구현 범위는 기존 종·맵에서 원인을 추적할 수 있는 세로 흐름을 완성하는 것이다. 새 종·새 생리 변수·플러그인·종분화·분산 서버는 필요와 지원 범위를 확인하고 확장한다.

## 8 공유용 시작 문구

2026-10-23 후속 구현의 실제 상태·남은 항목은 [구현 상태표](Architecture/ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md), 첫 opt-in 수분→기존 먹이→섭식→표현 연결은 [식생 계약·팀 연결](Architecture/ECOSYSTEM_VEGETATION_CONTRACT_20261023.md)을 따른다. 전체 세부 기획의 구현 완료를 의미하지 않는다.

저장된 BP와 배치까지 연결한 실행 맵은 `/Game/JYU/Maps/LV_JYU_Ecosystem`이다. [BP 실행·배치 안내](Architecture/JYU_ECOSYSTEM_BP_SETUP_20261023.md)를 따라 Play한다. 다른 맵의 식생 기본값이나 원본 팀 맵을 바꾸지 않았다.

후속 [전체 통합 점검](Architecture/ECOSYSTEM_INTEGRATION_REVIEW_20261023.md)에서 이주 혼잡 중복·경로/서식지/soil 검증과 관찰 World 선택을 보완했다. 최신213개 자동화와 실제 재검증 범위는 이 기록을 우선한다. 전체 기획의 미구현 기능을 완료로 선언한 것은 아니다.

조연우의 후속 전체 구현을 다른 채팅에서 시작할 때는 [구현 시작 프롬프트](Architecture/ECOSYSTEM_IMPLEMENTATION_START_PROMPT_20261023.md)를 사용한다. 기존 구조의 개선 허용 범위, 팀 연결 기반, 학습 대기 중 실행 가능한 기준 동작, 단계별 실제 완료 조건을 담았다. 이 문서가 추가된 것만으로 새 기능이 구현되거나 기본 설정이 변경된 것은 아니다.

다른 AI가 AGENTS.md를 자동으로 읽지 않는 도구라면 다음 문구로 시작할 수 있다.

> 작업 전에 루트 AGENTS.md와 AdaptiveEcosystem/Docs/PROJECT_CONTEXT.md를 읽고 실제 branch/Source 및 담당 계약을 확인해 주세요. 사슴·늑대는 현재 예시이며 종별 규칙/능력/실행을 분리합니다. 제품 목표·현재 구현·후속 제안을 구분하고 서버 권위, 단일 이동/자원 writer, 기존 RL/parity·복제 계약을 보존하면서 요청한 범위만 진행해 주세요.

이 문서가 존재하는 것만으로 모든 도구가 자동 로드하는 것은 아니다. root AGENTS/README에 연결했으며 다른 팀원이 사용할 checkout에도 해당 변경을 가져와야 한다.
