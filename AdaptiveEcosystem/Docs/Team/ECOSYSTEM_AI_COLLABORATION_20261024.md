# 생태계 통합 이후 팀 AI 작업 안내

작성일: **2026-10-24**. 구현 기준 커밋은 **`d095948`**, 작업 브랜치는 `codex/social-shelter-handoff`다. 서버·네트워킹·학습 담당자가 이전 채팅 없이 AI agent로 후속 작업을 시작하기 위한 공통 진입 문서다. 개인별 담당 수락이나 새 기능의 완료를 대신 선언하지 않는다.

## 1. 지금부터 무엇을 읽고 시작할까

| 순서 | 문서 | 목적 |
|---|---|---|
| 1 | [루트 AGENTS.md](../../../AGENTS.md), [프로젝트 공통 맥락](../PROJECT_CONTEXT.md) | 작업 위치·엔진·권위·단일 writer·빌드 규칙 |
| 2 | [현재 구현 상태](../Architecture/ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md) | 구현과 미지원 범위 구분 |
| 3 | [life-v1 실행 계약](../Architecture/ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md), [soil 계약](../Architecture/ECOSYSTEM_VEGETATION_CONTRACT_20261023.md) | 실제 생산자→소비자→결과→장부·저장·표현 |
| 4A | [서버·네트워킹 AI 작업 안내](../Network/ECOSYSTEM_SERVER_NETWORK_AGENT_GUIDE_20261024.md) | 권위·transport·저장/운영·성능 후속 |
| 4B | [학습 AI 작업 안내](../RL_Policy/ECOSYSTEM_RL_AGENT_GUIDE_20261024.md) | 세계 mirror·입출력 계약·모델 교체·평가 후속 |
| 5 | [AI 시작 프롬프트](ECOSYSTEM_AGENT_START_PROMPTS_20261024.md) | 역할별 복사 가능한 실행 요청 |
| 6 | [최종 검증 근거](../Architecture/Evidence/EcosystemLife_20261023.json) | 테스트 조건과 수치의 실제 범위 |

`d095948`을 무조건 checkout/reset하라는 뜻이 아니다. 먼저 현재 HEAD·작업 트리·원격 상태를 확인하고, 이 기준 이후 변경도 읽는다. 이 문서는 합의된 구현을 이어가기 위한 안내이며, 열려 있는 PR의 자동 병합 지시가 아니다.

## 2. 구현된 결과를 짧게 이해하기

실행 맵은 **`/Game/JYU/Maps/LV_JYU_Ecosystem`**이다. 맵에 식생/life opt-in과 필요한 BP 설정을 저장했다. 원본 팀 맵·기존 JYU 맵의 옵션을 일괄 변경하지 않았다. 검증 예시는 사슴·늑대이며 임의 몬스터 전체의 실행 backend를 구현한 것은 아니다.

| 현재 기능 | 실제 실행 결과 | 확대 해석하면 안 되는 것 |
|---|---|---|
| 환경·식생 | 권위 강수/기온/빛·지면/수원→토양 수분→기존 FoodGrid 성장·손실·섭식→식생 표현 | VFX가 자원을 생성하거나 완전한 수리 모델이 작동함 |
| 감각·기억 | 실제 시야/소리/속도/피해·목격→개인 기억/지역 위험→호기심·경계·회피 | 온라인 PPO 학습, 전지적 공격자 식별 |
| 사냥·영양 | 유효 흔적 조사·역할 lease→Native 포획→M4 확정 사망→사체 접촉 영양 | 모든 육식종의 일반 전투·플레이어 전투·loot 전체 |
| 자연 출생 | 부모/성숙/영양/거리·실제 자리/인구 예약→자식·부모 비용·유전/성장 | 사망 respawn을 다음 세대로 세거나 유익한 진화 증명 |
| 이주 | 제한된 장소 보고→Persistent Herd 계획→실제 몸 이동/지역 인계→정착/실패 정리 | 목적지 선택만으로 도착 완료, 실패 개체 teleport |
| 저장·복구 | 같은 빌드 재시작 checkpoint·실제 ID 재결합·명시적 빈 종 운영 공급 | cross-build migration·live rollback·분산 서버·플레이어 저장 전체 |
| 표현·멀티 | 기존 Bubble과 Field DTO→수신 Actor·크기·Activity·기존 ABP/IK | Client의 논리 시뮬레이션, 새로운 Morph/어린 개체 전용 리그 |

## 3. 공통 소유권: 새 manager보다 기존 경계를 먼저 찾기

```text
권위 환경/지면 snapshot
  → Native FoodGrid·개체 관측·Raw Request
  → Social/이주/경험 규칙의 유효한 의도
  → Native 단일 이동·대사·섭식·포획
  → 완료 GT 경계의 피해/생명주기/출생 조정
  → M4 자원·사망·인구·이주 receipt
  → 저장 또는 요약/Bubble/Field transport
  → Client의 수신 표현
```

| 책임 | 현재 소유자/실제 파일 | 새 작업에서 금지할 중복 |
|---|---|---|
| 공간 먹이 | `AI/Policy/EcoWorldV3.h::FFoodGrid`, `Ecology/EcologySpatialFood.cpp` | 별도 patch 잔고·BP 재생·두 번째 섭식 지급 |
| 실제 개체 실행 | `EcoWorldV3.h`, `EcoPolicyV3IntegratedProcessors.cpp`, 기존 movement hook | Client/Actor/AnimNotify/새 Processor의 위치·대사 재적분 |
| 완료 조정 | `Creature/Runtime/EcoCreatureLifecycle.cpp`와 같은 spawner의 partial 구현 파일 | 출생/죽음/사체 영양을 다른 manager에서 재확정 |
| 지역/인구 장부 | `UEcologySimulationSubsystem` | 진단/복제/학습 코드의 직접 Population 수정 |
| Persistent Herd·의도 | `AI/Social/`, `Mass/EcoHerdMigration.*` | Herd를 flock 이동 writer로 만들기 |
| 복제 | `Network/Mass/`, `AEcoVegetationField`, 기존 GameState | Subsystem에 RPC/복제 프로퍼티 추가 |
| 모델 제안 | 기존 Native 정책 추론·`EcoV3Brain` registry | Python 실시간 추론, Raw Request와 실행 결과 혼합 |

표의 파일 경로는 `AdaptiveEcosystem/Source/AdaptiveEcosystem/` 기준이다. 상세 순서는 [Mass 실행 계약](../Mass/MASS_PROCESSOR_ORDER.md)을 따른다. Native v3와 기존 SpeciesAI/V1은 다른 경로이며 같은 개체에 동시에 붙이지 않는다.

## 4. 역할별 우선 작업과 의존 관계

아래는 후속 작업의 **권장 순서**다. 이 문서만으로 담당자가 배정되거나 모든 항목이 한 번에 활성화되는 것은 아니다.

| 단계 | 서버·네트워킹 | 학습 | 서로 넘길 것 |
|---|---|---|---|
| P0 기준 고정 | 동일 Source/Content/LFS·활성 flag·서버/Client 역할 확인 | 동일 world/model/schema/mask·단위·seed 확인 | 기준 SHA, 변경 파일, baseline manifest |
| P1 계약 보존 | Add/성장/죽음/삭제/relevance/재접속·이주 reset 회귀 | soil leaf 및 기존 정책 Golden/OFF 회귀 | 실제 실패 사례와 최소 재현 |
| P2 부족한 증거 보완 | 연결별 Actor/Add·보간·대역폭·hitch 원인 계측 | life 세계의 시간·비용·관측/규칙 mirror 및 differential 평가 | 입력 snapshot, 예측/실행/receipt·오차 보고 |
| P3 작은 변경 | 확인된 병목 하나 또는 저장/운영 계약 하나를 개선 | 합의한 버전의 모델/adapter 하나를 평가 | 변경 전후 비교, rollback 경로 |
| P4 통합 | 같은 모델을 실제 서버/복수 Client에서 검증 | C++ 추론·mask·실행 parity와 장기 holdout 평가 | acceptance 결과, 한계, PR·인수인계 |

서버가 transport를 바꾸는 동안 학습 담당이 같은 DTO에 새 관측을 추가하지 않는다. 학습 담당이 에너지/시간 의미를 바꾸면 서버의 자원 장부·저장·사체/출생 비용 검증이 선행한다. 공통 파일은 “누가 마지막에 저장했는가”로 해결하지 않고, 필드/함수 단위 변경 계약을 먼저 적는다.

## 5. AI agent 작업 한 건의 표준 절차

1. 현재 branch/HEAD, `git status`, 관련 하위 지침, 실제 Source·맵·기능 flag를 확인한다. 오래된 문서의 Pending을 그대로 새 기능으로 구현하지 않는다.
2. 이번 문제의 trigger와 실제 잘못된 결과를 적는다. 새 설계라면 현재 미지원인지 먼저 구분한다.
3. producer→snapshot/request→consumer→단일 writer→outcome/receipt→표현/저장 경로를 짧게 적는다. 이름만 있는 interface로 종료하지 않는다.
4. 수정할 파일·건드리지 않을 공유 계약·예상 충돌을 정한다. 다른 사람의 미커밋 변경은 보존한다.
5. 가장 작은 실행 가능한 변경을 만든다. 새로운 상태의 취소/실패/죽음/TTL/재시작 정리까지 함께 연결한다.
6. 변경에 맞는 단위/negative test와 실제 장면을 검증한다. C++/빌드 입력 변경이면 직접 UBT를 실행하고 종료까지 기다린다.
7. baseline과 candidate를 같은 조건에서 비교한다. 기존 코드·새 규칙·fixture·모델의 효과를 섞지 않는다.
8. Source·설정·검증 범위·미지원 항목·재현 명령을 문서에 갱신한다. PR에는 다른 팀의 완료로 기록하지 않는다.
9. stage diff와 LFS 대상·비밀정보·대용량 산출물을 검토한다. push/PR/merge는 해당 작업의 사용자 승인 범위를 따른다. 공유 브랜치 force push로 해결하지 않는다.

C++ 빌드 중 UBT/dotnet/Unreal Editor/Live Coding/MSBuild/ShaderCompileWorker가 실행 중이면 새 빌드를 시작하거나 중단하지 않는다. dotnet 예외는 첫 UBT/compiler 오류와 Windows Application Event Log부터 확인한다. `git pull`로 미커밋 소스나 에셋을 덮어쓰거나 캐시/출력을 무작정 삭제하지 않는다.

## 6. 공유 파일 변경 요청 양식

```text
문제/재현:
현재 기준 SHA·맵·backend·flags:
수정하려는 producer/consumer와 파일:
필드 의미·단위·시간 기준·ID/epoch/sequence:
최종 writer와 기존 receipt 경로:
중복/오래된 요청/취소/실패·죽음/재시작 처리:
Client로 보낼 값 / 서버에만 남길 값:
기존 모델·저장·네트워크·에셋 호환 영향:
상한/후보 수·주기/과부하 정책:
baseline / candidate / acceptance / rollback:
상대 담당에게 필요한 입력과 제공할 결과:
```

문서에 제안만 쓰고 다른 agent에게 자동으로 작업을 배정하지 않는다. 다른 채팅·팀원에게 메시지를 보내는 것은 별도 사용자 지시가 있을 때 수행한다. 이 양식은 사람 간 합의와 실제 변경을 추적하기 위한 것이다.

## 7. 팀이 놓치기 쉬운 경계

- **깨끗한 clone에는 Saved가 없다.** 원시 로그·CSV·`.eco`·전체 learning snapshot은 Git 제외다. 공유된 요약 JSON·PNG와 [작은 실제 RL 예제](../RL_Policy/Examples/README.md)를 읽고, 필요하면 도구로 새 빌드에서 재생성한다.
- **동일 Git SHA라도 checkpoint가 항상 호환되는 것은 아니다.** 현재 codec는 runtime image hash를 검사한다. 다른 PC/재빌드/Editor→패키지의 바이트가 달라지면 거절할 수 있다. 배포용 migration은 별도 계약이다.
- **서버의 논리와 Client proxy를 구분한다.** Client에 Mass 표현 proxy가 존재할 수 있지만 권위 개체·Native Step·이주 판단은0이어야 한다. relevance Remove는 사망/멸종이 아니다.
- **시간을 구분한다.** Native step은2/15 simulation seconds, 길이1 native unit은200cm다. world clock·Native tick·렌더 보간·wall time을 임의로 동일시하지 않는다. 외부 모델의 step 비용도 맞춘다.
- **ID를 구분한다.** StableAgentId와 world epoch, transport ID, Entity handle, compact index, ISM instance index는 다른 수명이다. JSON/JS에서 int64를 무조건 number로 바꾸면 정밀도를 잃을 수 있다.
- **관찰값과 정답을 구분한다.** Inspector의 HP/부모/현재 위치/지역 전체 셀은 서버 진단 정답일 수 있다. 학습 observation이나 Client에게 그대로 제공할 권한을 뜻하지 않는다. Unknown 피해를 사람 위치로 채우지 않는다.
- **LOD와 결과를 분리한다.** 화면에 안 보인다는 이유로 자원/사망 receipt를 생략하지 않는다. pooling 재사용은 새로운 자연 출생이 아니다.
- **증거를 분리한다.** 자연 무인 관찰, 플레이어를 움직인 encounter fixture, 가뭄으로 food를 제거한 시험, 운영 복구는 서로 다른 실험이다.
- **운영 경로는 신뢰 경계다.** Save/Load/Recover를 일반 Client가 인자만 보내 호출할 수 있게 노출하지 않는다. 관리자 인증·감사·rate limit을 구현했다는 별도 증거 없이 운영 서비스 완료로 표시하지 않는다.
- **cook과 Editor 성공은 다르다.** soft/string 의존성, PrimaryAssetLabel scan 설정, editor-only subobject, 플러그인·shader·소리까지 실제 패키지에서 확인한다. registry에 이름만 있는 것은 충분하지 않다.
- **선택과 학습은 다르다.** 자식의 유전자 분포·생존 변화가 곧 PPO 개선이나 유익한 진화의 증명은 아니다. 운영 보충 개체를 자연 번식 성과로 세지 않는다.

## 8. 검증 수치의 현재 의미

2026-10-23 검증을 기록한 구현 커밋이 `d095948`이다. 전체 자동화225개는224 Success+기존 예상 warning1, 실패/미실행0이었다. PIE125초, Dedicated world와 동시 Client2, 세 seed의1800 simulation seconds, 정확 저장 복원, Win64 Game build/cook/90초 패키지 실행을 확인했다. 장기/PIE/네트워크와 마지막 editor-only/cook 보완의 빌드 범위는 evidence의 `verification_scopes`를 따른다.

이 문서 작성·링크/Source 감사는 **2026-10-24의 새 UBT/PIE 실행을 뜻하지 않는다**. 새 담당자가 코드를 바꾸면 자신의 새 검증을 남긴다. 같은 PC·장면·인구에서 얻은 p95를500/1000개체, WAN/패킷 손실, Steam session, Linux Dedicated 배포의 검증으로 확대하지 않는다. Client의 최대 약350ms hitch는 원인별 후속 profiling 대상이다.

이번 문서 작업의 별도 근거는 [10-24 문서 감사 JSON](../Architecture/Evidence/DocumentationAudit_20261024.json)이다. 상대 링크·문서 명령 구문·예제와 실제 원본의 값 일치·Python 구문·runtime Source/Content/Config 비변경과 LFS pointer 검사를 수행했다. 모델 학습이나 새로운 런타임 테스트 결과와 섞지 않는다.

## 9. Git·에셋·인수인계

새 담당자는 작업 성격에 맞는 `codex/` 브랜치에서 기준 SHA와 owner 파일을 기록한다. 공유 checkout을 무조건 reset/clean하거나 다른 사람의 WIP를 stash·삭제하지 않는다. 같은 `.umap`/`.uasset`을 동시에 편집하지 말고 owned 복사 또는 담당 에셋을 정한다. World Partition 맵은 해당 `__ExternalActors__`/`__ExternalObjects__`와 함께 검토한다. `.umap` 하나만 복사했다고 통합이 끝난 것이 아니다.

`.uasset`/`.umap`/PNG 등은 Git LFS 대상이다. `git lfs install`, `git lfs pull` 후 실제 파일을 확인하고 LFS pointer만 있는 파일을 손상된 UE 에셋으로 판단하지 않는다. push 시 Git 커밋과 LFS 객체 업로드가 모두 성공해야 한다. 개인 발표·raw Saved·모델 대용량 체크포인트·엔진 캐시·실행 파일을 섞어 올리지 않는다.

종료 인수인계에는 실제 SHA·작업 트리 상태, 구현/제안 구분, 맵/backend/flags, 수정 파일·공통 계약, 실행한 테스트/하지 않은 테스트, 알려진 실패·한계, 재현 명령, 다음 작은 작업과 필요한 외부 입력을 남긴다. 증거에 없는 “모든 네트워크/모든 종/완전한 MMO/학습 완료” 표현을 피한다.
