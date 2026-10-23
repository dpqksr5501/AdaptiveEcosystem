# 팀 AI agent 시작 프롬프트 — 2026-10-24

각 담당자의 올바른 checkout에서 아래 요청을 사용한다. 실제 목표·허용 범위·학습 예산·push/PR 여부를 덧붙인다. `d095948`은 조사 기준이며 기존 작업을 reset할 대상이 아니다. [공통 안내](ECOSYSTEM_AI_COLLABORATION_20261024.md)와 현재 branch/Source를 우선한다.

## 1. 모든 담당자가 먼저 붙일 요청

```text
AdaptiveEcosystem의 현재 구현을 이어서 작업해줘.
루트 AGENTS.md, Docs/PROJECT_CONTEXT.md와
Docs/Team/ECOSYSTEM_AI_COLLABORATION_20261024.md를 먼저 읽어줘.
Docs는 실제 프로젝트 AdaptiveEcosystem/Docs 기준이야.
현재 branch/HEAD·git status·하위 지침·Source/Content·활성 backend/flag를 확인하고
기준 d095948 이후 변경과 다른 사람의 WIP도 보존해줘.

현재 실행 맵 /Game/JYU/Maps/LV_JYU_Ecosystem의 soil/life opt-in,
SocialControl=0, Native 단일 이동·대사·섭식·포획 writer와 기존 M4 장부를 유지해줘.
오래된 Pending을 새로 구현해야 한다고 가정하거나 V1/SpeciesAI/Native를
같은 개체에 중복 활성화하지 마. 현재 검증 예시는 사슴·늑대야.

이번 목표의 producer→입력/의도→consumer→writer→outcome/receipt와
저장/클라이언트 영향을 확인하고 가장 작은 실행 가능한 변경부터 진행해줘.
빈 함수·사용되지 않는 인터페이스·계획만으로 끝내지 말고 연결/실패 정리·검증까지 해줘.
C++/빌드 입력 변경이면 직접 UnrealBuildTool.exe로 Editor target을 빌드하고
완료까지 기다려줘. UBT/dotnet/Editor/LiveCoding/MSBuild/ShaderCompileWorker 실행 중
새 빌드를 시작하거나 강제 종료하지 마. 문서만 바꿨으면 새 UBT/PIE를 했다고 쓰지 마.

이번에 승인한 범위는 자율적으로 끝까지 진행해줘.
별도 지시 없는 main 병합·force push·배포·유료 비용·타 채팅 메시지는 실행하지 마.
원본 팀 맵·개인 자료를 보존하고 Saved/raw/빌드 출력을 Git에 넣지 마.
실제 변경·테스트·지원 범위·알려진 한계·재현 명령을 한글로 인계해줘.
```

## 2. 서버·네트워킹 담당 요청

```text
Docs/Network/ECOSYSTEM_SERVER_NETWORK_AGENT_GUIDE_20261024.md,
기존 권위/M4/P4 계약과 실제 Source를 읽고 서버·네트워킹 작업을 진행해줘.
독립 Server 배포·DB·Steam 서비스까지 이미 완료됐다고 가정하지 마.

Bubble identity/position/vitals/life/Activity/BodyScale,
SampleSequence·VisualRevision·MovementDiscontinuityRevision과 실제 proxy→Actor
소비자를 확인해줘. 버퍼/설정이 있다고 timeline 보간·연결 전체 예산 집행이
완료됐다고 쓰지 마. Client proxy와 권위 개체를 구분하고 Client 논리는 추가하지 마.

현재 2Client 장면의 최대 약350ms frame hitch를 재현하고 streaming·Actor Add·
애니메이션 초기화·수신·QA 기록 비용을 분리해줘. 확인된 원인부터 개선하고
동일 baseline/candidate의 p95/max·논리/Proxy/Actor/Add 수·bytes·메모리를 비교해줘.
한 번에 엔진 transport·보간·pooling·새 manager를 모두 교체하지 마.

Add/성장/정지 dirty·death/잔류/Remove·relevance 재진입·late join/재접속,
오래된 표본/reset·이주/로드 위치 인계·잘못된 owner RPC를 검증해줘.
Save/Recover를 일반 Client 임의 RPC로 노출하지 말고 다른 build의 checkpoint를
거절했다고 세계를 지우거나 자동 초기화하지 마.
Dedicated world+복수 Client를 실제 검증하고 실행하지 않은 Steam/WAN/손실/Linux 배포는
완료로 쓰지 마. 공통 필드 변경의 단위·시간·ID/버전·실패·호환과 학습 인계도 남겨줘.
수정 후 관련 UBT·자동화·실제 장면·영향 있는 패키지 검증까지 진행해줘.
```

기본 목표는 실제 병목/회귀를 찾아 작은 단위로 해결하는 것이다. 특정 서버 기능을 원하는 경우 목표를 그 기능으로 교체한다. 새 운영 서비스/인증·DB·배포는 범위와 검증 환경을 별도로 지정한다.

## 3. 학습 담당: mirror·평가 요청

```text
Docs/RL_Policy/ECOSYSTEM_RL_AGENT_GUIDE_20261024.md, TEAM_REQUESTS_V3.md,
V1/V3 계약과 실제 herbivore_rl 코드를 읽고 새 세계의 mirror·평가 연결을 진행해줘.
기존 V1 7/4, v3 기본18/5 mask2와 별도21·weights/Golden을 보존해줘.
새 soil/life는 현재 규칙 adapter/세계 규칙이며 PPO 새 학습 완료가 아니야.

단위1=200cm·step2/15초, 음식/환경 손실·영양/출생 비용, 감각/Unknown/TTL,
유전/성장·흔적/협동·장소 보고/이주·안전/포획 제약의 실제 차이를 목록화해줘.
leaf→개별 규칙→단일 지역→명시 입력 replay→다지역 순으로 실행되는 mirror와
differential 검증을 만들고 같은 초기 상태/입력의 첫 divergence를 좁혀줘.

Examples JSON은 실제 부분 표본이며 training_ready=false야.
숨은 위치/전체 셀/부모/RNG 같은 진단 정답을 policy 관측에 넣지 말고,
저주기 snapshot으로 전체 Native step 상태를 복원한다고 가정하지 마.
토양 leaf parity·neural Golden·world trajectory·실제 UE 결과를 따로 보고해줘.

새 입력이 필요하면 기존 슬롯/21관측 장애물 칸을 재해석하지 말고
새 계약·정규화·Unknown·mask/Golden·registry/adapter 판부터 정의해줘.
request·규칙 의도·실행을 분리하고 Native 단일 writer와 runtime Python 추론 금지를 지켜줘.

별도 학습 범위/예산이 없으면 대규모 학습을 임의로 시작하지 말고
구현 가능한 mirror·계약·비학습 평가부터 완성해줘.
학습까지 이미 승인됐으면 그 범위에서 계속 진행하고 매번 다시 묻지 마.
train/holdout·seed/기간·성공/실패 기준과 모델 인계 묶음을 작성하고,
기존 Source weights를 기본 export 출력으로 덮어쓰지 말고 후보를 격리해줘.
```

## 4. 승인된 candidate를 실제 게임까지 연결하는 추가 요청

```text
제공한 candidate 모델/세계 config와 승인된 평가 범위로 실제 게임 연결까지 진행해줘.
파일 경로·sha256·encoder/schema/obs/mask/contract hash·world profile/flags/config를
확인하고 빠진 입력을 임의 모델로 대체해 성공했다고 처리하지 마.

기존 registry/loader를 사용하고 손상 파일·obs/mask·NaN·금지 행동·세계 불일치의
거절/fallback을 검증해줘. I/O hash 일치나 world-label 문자열만으로 ON-world parity를
승인하지 마. masked logits/argmax/tie, 기존 Golden/OFF와 holdout 비교를 지켜줘.
유지 비용·부모 비용/Reserve0·사체 접촉 영양·Unknown·제한 보고를 보존하고,
운영 공급을 자연 출생 성과로 세지 마.

기존 model/weights와 rollback을 보존한 채 C++ Native 추론에 연결하고
관련 UBT/자동화·실제 권위 outcome·Client 논리0·필요한 패키지를 검증해줘.
학습 성능·inference parity·world parity·실제 game acceptance를 구분해 보고해줘.
```

## 5. 종료 인수인계 양식

```text
기준/결과 commit·branch와 남은 dirty 파일:
현재 실제 되는 것 / 제안 또는 미지원:
수정 파일·producer/consumer/최종 writer:
단위·시간·ID/epoch/sequence·모델/세계/저장/전송 판:
맵·backend·flags·seed·인구/연결·wall/시뮬레이션 시간:
실행 명령·빌드/자동화·실제 장면·evidence:
실패/negative case·비변경 거절·baseline/candidate:
성능 p95/max·메모리·bytes의 범위와 QA 비용:
호환/rollback·상대 담당에게 필요한 입력/제공 결과:
다음 한 작업과 재현 명령:
push/PR 여부·URL(승인 범위의 실제 결과):
```

이 문서 작성은 새 agent/다른 채팅 생성이나 팀원에게 자동 메시지 전송을 뜻하지 않는다.
