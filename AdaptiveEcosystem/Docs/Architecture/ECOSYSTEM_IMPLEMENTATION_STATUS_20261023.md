# 동적 생태계 구현 상태 — 2026-10-23

사용자의 [전체 구현 요청](ECOSYSTEM_IMPLEMENTATION_START_PROMPT_20261023.md)에 따라 아래 지원 범위의 실제 실행·에셋·검증을 완료했다. branch `codex/social-shelter-handoff`, 작업 시작 HEAD `ecfd82fab04d16531ae7e00a2adaf3a4737d2fcf`, **구현 기록 `d095948`**이다. 시작 시 있던 공통 맥락/README 변경과 사용자 에셋을 보존했다. 2026-10-23 검증 당시 미커밋이던 구현을 사용자의 10-24 공유 요청에 따라 커밋했다. 공개 검토는 [PR #14](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/14)를 따른다. 자동 병합은 수행하지 않는다.

2026-10-24 추가한 [팀 AI 공통 안내](../Team/ECOSYSTEM_AI_COLLABORATION_20261024.md), [서버·네트워킹](../Network/ECOSYSTEM_SERVER_NETWORK_AGENT_GUIDE_20261024.md), [학습](../RL_Policy/ECOSYSTEM_RL_AGENT_GUIDE_20261024.md), [실제 예제](../RL_Policy/Examples/README.md)를 새 작업의 진입점으로 사용한다. 기존225개/장면 증거는10-23 실행이며 이번 문서 감사의 새 UBT/PIE 결과가 아니다.

실행 맵은 **`/Game/JYU/Maps/LV_JYU_Ecosystem`**이다. 원본 팀 맵·이전 JYU 맵은 변경하지 않는다. 기존 맵의 기본 flag와 V1 7/4·v3 18/5 mask2·opt-in21·가중치를 유지한다. 새 맵의 `bEnableVegetation=true`, `bEnableEcosystemLife=true`가 후속 세계 규칙을 켠다. 기본 `SocialControl=0`, Native 단일 이동/대사/섭식·포획 writer를 유지한다.

최신 구현·단위/시간·실패 정리·팀 API·재현은 [life-v1 실행 계약](ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md)을 우선한다. 아래는 목표 설계와 현재 Source를 구분한 상태표다. 완료하지 않은 실행 gate는 완료로 표시하지 않는다.

| 범위 | 현재 실제 연결 | 지원 범위 / 제한 |
|---|---|---|
| A 환경·식생 | 서버 기후→수분/식물 내성→기존 FoodGrid 성장/손실→동시 부분 섭식→M4 보존 장부→Field DTO/ISM | 별도 food 잔고 없음. 실제 조사한 얕은 수원 BP 1개, habitat 총10개. 900 논리 셀/지역 중 시각 최대256개 표본. 전용 식물 아트/완전한 수리 모델은 아님. |
| B 장소·이주 | 회복 전망/물/위험/은신/혼잡/거리의 30초 authored 보고·90초 TTL→기존 Persistent Herd 계획/Travel/context 이전/M4 receipt | 출발·실제 지역 진입·끝 정착을 구분. 복귀도 실패하면 Abandoned. 지역 밖 stranded는 멈추고 대사·사망은 계속하며 teleport/무한 재시도 없음. |
| C 경험·사람 | 실제 시야/눈높이/정적 LOS/식생 차폐·Pawn 속도·발소리·권위 피해→개인 familiarity/curiosity/fear/hostility/Unknown→제한된 호기심·경계·회피와 실제 body | 직접/공유·TTL·노출·episode 중복 분리. 근접 F 공격은 실제 거리/방향/LOS를 통과해야 HP−30. 원인을 알 수 없는 피해는 사람의 좌표/원인을 생성하지 않음. 새로운 PPO 학습 결과가 아닌 규칙 adapter. |
| D 흔적·사냥 | 실제 이동 흔적256/공간 bucket64→최대16개 근처 조사→기존 Native 사냥/협동 Lead·Intercept lease→단일 포획→M4 사망→사체 영양 | 조사 기한/무진행/cooldown·표적 재확인. 성공한 먹이 총 .6을 실제 최근 참여자에게 분할하고 실제 접촉 섭취·20초 만료·영양 대사/기아를 실행. instant reward 중복 없음. 후각/임의 몬스터 전투 backend는 추가하지 않음. |
| E 다양성·출생 | 안정 ID/seed genome→성장/능력/유지 비용→성숙·영양·부모 둘·혈연/거리/자리·인구 예산→실제 자식/부모 비용·후손 기여 | 초식/포식 모두 조건부 출생. initial/recovery/natural origin·부모·세대를 구분. 기존 Births 합계를 자연 출생 횟수로 읽지 않음. 관찰된 세대/집단 수만 실제 증거로 보고. |
| F 체형·표현 | 제한된 genome/growth→Native 속력/대사·terrain sweep/catch 반경→Bubble 크기→Actor·locomotion/stride·기존 ABP/IK | 검증 범위는 uniform scale. 리그 Morph/Bone 비율의 추가 authoring·비행/수영·Mutable/신규 리그를 지원 완료로 표시하지 않음. curiosity/vigilance/investigation Activity는 실제 전송 경로 사용. |
| G 저장·규모·멀티 | 실제 grid/수분/RNG/시계·개체/유전/부모/경험·M4 장부/watermark·Herd/계획/흔적→명시 save/load→ID 재결합 | 동일 runtime module hash의 재시작만 지원. 다른 build/map/model/schema·손상 파일 거절, transient 입력/자리 취소. 관심 영역은 표현이며 원격 논리도 계속 실행. 완전한 MMO/분산 저장·서비스/loot/퀘스트 backend는 별도. |
| RL 인계 | 실제 900 셀/지역과 개체 관측/request/mask·규칙 결과 snapshot, C++ leaf/Python mirror 비교 도구 | soil leaf 2400개 parity 오차0. 전체 life 세계 Python mirror·새 가중치·재학습/전체 궤적 parity는 RL 담당 후속. 런타임 Python 추론 없음. |

## 검증 기록을 읽는 법

이전 soil/BP 최초 구축은 [식생 계약](ECOSYSTEM_VEGETATION_CONTRACT_20261023.md), [BP 실행 안내](JYU_ECOSYSTEM_BP_SETUP_20261023.md), [첫 통합 점검](ECOSYSTEM_INTEGRATION_REVIEW_20261023.md)에 당시 빌드/209·213개 자동화·PIE/멀티 증거를 보존한다. 그때의 미구현 설명은 후속 life 구현 전 이력이다.

최신 직접 UBT는 `Saved/IntegrationBuilds/Milestone_Final_20261023_234012.log` Succeeded. `Saved/EcosystemLife_20261023/AutomationFinal/index.json`은 **225개 = 224 Success + 기존 예상 warning1, 실패/미실행0**이다. 실제 지면 projection, 출생 비축량, 은신처 재결합·경험/TTL·저장/거래·editor-only template 회귀를 포함한다.

동일 최신 빌드의 실제 저장→새 서버 복원은156개체/위치/유전/부모/기억·수분/food·장부 exact 비교를 통과했다. 실제 피해 후 비영 Unknown 기억144개체와 사체가 남은 운영 복구 세계150 living 개체도 새 프로세스에서 exact 복원했다. 잘못된 파일·버전/checksum 및 실행 중 과거 checkpoint는 거절하고 이전 상태를 유지했다.

출생 때 무상 성체 비축량을 제거했으므로 이전 `LongSeed*`/`Extended*`의600/1800초 수치를 최종 생물학적 결론에서 제외한다. `FinalExtended11/23/47`의 실제1800초·`FinalOff23`600초 결과와 최종 PIE/동시 Client/패키지 gate는 [life evidence](Evidence/EcosystemLife_20261023.json)에 집계한다. 관찰 cohort/생존 차이는 자연 평형이나 유익한 선택의 증명이 아니다.

최종 scene 검증은125초 PIE, Dedicated160초/Client2개 동시 접속·late join, 여러 seed1800초, 실제 가뭄 인계19건, 직접 Game UBT와 cook/package·D3D11 패키지90초 정상 종료까지 통과했다. 날씨 cook 누락과 FacingArrow template 오류를 실제 package에서 발견해 수정·재실행했고 최종 로그의 runtime Error/missing FX는0이다. 장기/PIE/동시 Client는230551의 Native 코드이며 이후234012 변경은 editor-only template·회귀와 cook 설정이다. 최신 저장/자동화/가뭄/패키지는234012에서 실행했다.

현재 남은 범위는 RL 담당의 전체 세계 mirror/새 학습·파리티, 전용 식물/물/어린 개체·체형 아트, 관찰된 접속/지역 전환 hitch의 추가 profiling, 새 종/수중·비행 및 검증 범위를 늘리는 별도 확장이다. 현재 장면 결과를500/1000개체나 완전한 MMO/자연 평형 검증으로 확대하지 않는다.

## 팀 연결과 다음 채팅

- World/자원: [soil-v1 생산자·소비자 계약](ECOSYSTEM_VEGETATION_CONTRACT_20261023.md).
- 개체/경험/출생/사냥/저장/복제: [life-v1 팀별 API와 실패 확인](ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md#팀별-연결-지점과-실패-확인).
- SpeciesAI: [기존 backend의 책임](../Integration/SpeciesAI/SOURCE_RESPONSIBILITIES.md). Native의 후속 기능을 임의 종으로 확대하지 않는다.
- RL: [기존 담당 요청](../RL_Policy/TEAM_REQUESTS_V3.md). 학습 요청은 담당 수락/완료와 구분한다.

새 채팅에서는 루트 AGENTS.md·PROJECT_CONTEXT·이 문서와 `git status`를 먼저 읽는다. 기존 owned 맵을 `setup_jyu_ecosystem.py`로 재생성하지 않는다. 후속은 `extend_jyu_ecosystem_life.py`처럼 기존 소유 actor의 필요한 부분만 수정한다. UBT/에디터/LiveCoding/dotnet/MSBuild/ShaderCompileWorker가 실행 중이면 새 빌드를 시작하거나 중단하지 않는다. 개인 발표 자료는 바탕화면 외부 폴더에 유지한다.

세부 기획 §1–27 대응과 직전 실패·실제 도구·후속 담당은 [최신 인수인계](ECOSYSTEM_LIFE_HANDOFF_20261023.md)를 따른다.
