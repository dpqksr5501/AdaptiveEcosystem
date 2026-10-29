# 생태계 통합 이후 학습 담당 AI 작업 가이드

작성일: **2026-10-24** / 구현 기준: **`d095948`**. [공통 작업 안내](../Team/ECOSYSTEM_AI_COLLABORATION_20261024.md), 루트 AGENTS.md, [기존 RL 팀 요청](TEAM_REQUESTS_V3.md)을 먼저 읽는다. 이 문서는 학습 담당의 다음 실제 작업과 acceptance를 설명한다. 새 학습·새 가중치·전체 life 세계 parity의 완료 기록이 아니다.

## 1. 지금 학습 담당자에게 필요한 결론

환경·개체 실행을 새로 만들 필요는 없다. C++에서 soil/life 규칙과 기존 정책을 실제 Native 실행·장부·출생/사망·저장/복제에 연결했다. 현재 새 경험/호기심·협동/흔적·영양/유전은 **규칙 adapter와 세계 규칙**이다. 기존 PPO가 이 경험을 새로 학습한 것이 아니다.

우선순위는 **기준 고정→세계 차이 목록→작은 mirror/differential 평가→입출력 버전/adapter 결정→승인 범위의 학습→holdout/Golden→C++/게임 검증**이다. 새 관측을 기존 슬롯에 몰래 넣거나 기존 가중치를 교체해 처음부터 결과를 뒤섞지 않는다.

실제 Python 프로젝트는 저장소 루트의 `herbivore_rl/`다. `Tools/RL`·Aquarium·PettingZoo를 현재 프로젝트 구조로 새로 생성하지 않는다. [기존 pipeline 문서](RL_TRAINING_PIPELINE.md)의 historical 표시와 [Python 요약](../../../herbivore_rl/docs/PROJECT_SUMMARY.md)을 확인한다.

## 2. 유지할 정책 계약

| 경로 | 현재 의미 | 후속 작업의 제한 |
|---|---|---|
| V1 | 7관측/4개 연속 선호 출력 | v3의 행동 번호/로짓과 혼용 금지 |
| v3 내장 R1b | 기본18관측/5행동·mask2 | 기본 모델/Golden/슬롯 의미 보존 |
| v3 opt-in21 | 장애물 관측을 포함하는 별도 입출력 계약 | 새 경험·유전 입력이 자동으로 포함된 것이 아님 |
| v3 다른 mask/경보 판 | [V3 계약](POLICY_CONTRACT_V3.md)의 별도 경로 | default R1b와 같은 판이라고 가정 금지 |
| v3 기본 두뇌 R7e (10-29 덧붙임) | 통합 v3 Play 시작 두뇌 = 빌드에 넣은 R7e(관측 24·mask5, 계약 `0xad7bad5e1acaf071`, `PolicyBrainV3Default.h`) | 위 '내장 R1b' 줄은 그대로(평가기·골든·평면 v3 경로의 바탕, `eco.V3Brain.Startup builtin` 으로 고름). 고르는 규칙·되돌리는 법은 [LIVE_ADAPT_SPEC.md](LIVE_ADAPT_SPEC.md) 5.6 |

입력 순서·정규화·clamp·mask/argmax·동점 규칙은 [V1](POLICY_CONTRACT_V1.md), [V3](POLICY_CONTRACT_V3.md)와 실제 `EcoObservationV3.h`, `EcoPolicyV3Inference.h`, Python encoder/export를 대조한다. 충돌을 발견하면 Source/계약 차이를 기록하고 담당자 합의로 수정한다. Golden 기대값을 새 코드에 맞춰 덮어써서 통과시키지 않는다.

기존 obs18/mask2 계약 hash는 `0x7eea0107339be4ce`, obs21/mask2는 `0xbc4fc2d45c47c5fd`다. **이 hash는 입출력 계약이며 전체 학습 세계의 동일성을 증명하지 않는다.** 실제 가중치 지문·학습 config·world profile·feature flags·encoder와 Native 버전도 별도로 고정해야 한다.

## 3. 실제 코드와 교체 지점

아래 C++ 경로는 `AdaptiveEcosystem/Source/AdaptiveEcosystem/` 기준이다.

| 역할 | 실제 경로 | 바꿀 때 함께 확인할 것 |
|---|---|---|
| 순수 세계/섭식/물리 실행 | `AI/Policy/EcoWorldV3.h` | C1..단계 순서·시간·난수·실행비용·OFF Golden |
| 토양 leaf | `EcoVegetationV3.h` ↔ `herbivore_rl/env_v2/vegetation_v1.py` | 실제 식·clamp·bounded dt·특수값/비활성 경로 |
| 개인 유전/기억/영양 | `EcoLifeHistoryV3.h` | 개인별 상태·감쇠·기여/혈통·cost·Unknown |
| 흔적 | `EcoMovementTracesV3.h` | spatial 후보 상한·TTL·조사/포기·목표 재확인 |
| 감각/의도 adapter | `EcoPolicyV3IntegratedProcessors.cpp`의 `ObservePlayers`, `IntegratedControlHook`, `EvidenceThreatHook` | GT gather와 서버 증거·우선순위, Raw Request 보존 |
| 실제 hook 형식 | `EcoWorldV3::FStepHooks` | `HerbControl`/`HerbTravel`/`ThreatInput`과 최종 이동 hook 책임 |
| 모델/추론 | `EcoV3Brain.*`, `EcoPolicyV3Inference.h`, 기존 weights/registry | schema/obs/mask/contract hash·유한값·선택·실행 경계 |
| 실제 결과 | `Creature/Runtime/EcoCreatureNaturalBirth.cpp`, `EcoCreatureCarcass.cpp`, `EcoCreaturePlayerOutcomes.cpp`, 기존 M4 장부 | parent/cost·실제 접촉 영양·피해 식별·중복 결과 금지 |
| 평가/내보내기 | `herbivore_rl/eval_v3.py`, `export_weights_v3.py`, `export_golden_v3_world.py`, 기존 tests | 실제 parser와 현재 config를 읽고 새 후보 산출물 격리 |
| 실제 진단 | Inspector `CaptureAgent`, `AEcoVegetationField::CaptureDiagnostics(true)` | 진단 정답과 policy observation의 경계 |

`FStepHooks::HerbControl`은 제어 의도를, `ThreatInput`은 기존 위협 Step의 입력을 보정한다. 새 학습 adapter도 여기서 의도만 공급하고 위치·대사·섭식·포획을 다시 적분하지 않는다. 함수가 연결돼 있다고 현재 가중치가 새 입력을 읽는 것은 아니다.

## 4. Python 세계가 따라야 할 차이 목록

| 항목 | 현재 C++ soil/life 의미 | mirror/평가 acceptance |
|---|---|---|
| 시간·길이 | Native1unit=200cm, step2/15 simulation seconds | cm↔native, tick↔초 변환을 명시. 서버 시작 offset·wall time·렌더 시계와 분리 |
| 토양/식물 | 강수·기온/빛·배수·그늘·수원/침수·식물별 내성→수분·성장/손실 | 같은 초기 cell/food/capacity/regen·순서·clamp·dt에서 leaf 비교 |
| 자원 | 기존 FoodGrid가 유일한 공간 잔고, M4 보존 receipt | After=Before−Consumed+Grown−EnvironmentLost. habitat 제거 거래는 별도 항목 |
| 감각 | 실제 FOV/눈높이·static LOS·식생 차폐, 실제 발소리·속도 | 직접 관측·공유·TTL·청각·추격 맥락을 동일 의미로 재현 |
| 사람 경험 | familiarity/curiosity/fear/hostility/Unknown 분리,16 episode·5초 노출 제한 | Unknown 피해에 공격자 좌표/사람 원인을 추가하지 않음 |
| 지역 위험/장소 지식 | 인식된 피해/목격의 제한 집계,30초 정량 보고·90초 TTL | 원격 지역의 매 step 실시간 정답을 개체 입력으로 주지 않음 |
| 유전/성장 | stable ID/seed founder, 부모 평균+제한 변이, speed/size 범위·성장180초 | 큰/빠른 몸의 실제 유지 비용·속도/접근 반경을 함께 반영 |
| 자연 출생 | 성숙·영양·부모/혈연·실제 거리/자리·인구 예산·incubation/cooldown | 성공 때 부모 각.2, 자식Energy.4, 초식 Reserve0. 초기/복구 성체 비축과 구분 |
| 사체 영양 | 확정 사망 후 총.6을 실제 참여자에 분할, 접촉 섭취·20초 만료 | instant reward 중복 금지. issued=consumed+wasted+remaining |
| 포획 제한 | 실제 LOS/차폐·은신처 안전, 사슴≤8 보호·지역60초 상한2 | 자연 평형이 아닌 명시 게임 규칙으로 version/config에 포함 |
| 흔적/협동 | 흔적256/bucket64·후보16·TTL20초, 역할3초 lease·조사/포기 | 현재 숨은 표적 좌표를 매번 조회하지 않음. 역할 계획과 실행 결과 구분 |
| 이주 | Persistent Herd 계획·단일 Native 이동·실제 지역 인계·실패 종료 | 목적지 선택=도착 아님. stranded no-clamp/no-food·대사 유지 |
| 사건 원인 | initial/natural/recovery/fixture 구분 | 운영 공급·초기 스폰·proxy 생성·이주 유입을 자연 번식으로 세지 않음 |

정확한 식·상수·enum·단계 순서는 현재 Source를 함께 읽는다. 이 표만 복제한 근사 세계를 전체 궤적 parity로 승인하지 않는다. Unreal 지면 trace·2.5D 충돌/안전·외부 Pawn/noise 입력은 pure leaf에 없으므로, 입력 재생 계약 또는 합의된 geometry mirror와 그 허용 오차가 별도로 필요하다.

## 5. 관측·정답·Unknown을 분리하기

1. **정책 관측**: 실제 encoder가 해당 개체에게 제공한 벡터와 mask. 순서/판/정규화는 버전 계약을 따른다.
2. **의도/실행**: `request`, `executed`, 규칙의 `flight_override`, 다음 요청/마스크와 실제 결과를 분리한다. 현재 규칙이 만든 행동을 PPO가 직접 선택한 행동이라고 표기하지 않는다.
3. **서버 평가 정답**: 전체900셀, 살아 있는 모든 몸의 현재 좌표·HP, 부모·유전, 숨은 위협의 위치, M4 장부 등. 분석/차이 진단용이며 observation 권한이 아니다.
4. **사건 근거**: 직접 보임/들림/목격·수신 시각·증거 시각·TTL·shared와 Unknown. ID만 안다고 현재 위치를 알 수 있는 것은 아니다.

새 입력을 제안하면 각 필드의 producer, 개체에게 알려지는 조건, 단위/정규화/범위, 결측 의미·mask, 증거/수신 시각, TTL, 업데이트 주기, 부모→자식 초기화, 저장/reset 의미를 정의한다. 0이 정상 값인 필드에 Unknown을 무조건0으로 넣지 않는다. StableAgentId/RNG state로 미래 결과를 알아내는 지름길이나 전체 세계 정답을 학습 observation에 섞지 않는다.

현재 진단의 `energy`(M4 Vitals 단위), `energy_fraction`(표현 양자화 값), Native body의 정규화 Energy는 동일 정밀도/단위가 아니다. `life.nutrition`은 현재 늑대 영양에 사용하는 값이므로 초식의 Energy/Reserve로 해석하지 않는다. `last_damage_attacker_known=false`도 피해가 없을 때 기본값일 수 있다. [예제 주의사항](Examples/README.md)처럼 실제 사건/시점·비영 기억과 함께 읽는다. 이 차이를 없애려고 원본 JSON을 임의 보정하지 말고 필요한 정확 capture 계약을 별도로 정한다.

## 6. 공유 예제와 깨끗한 clone

[작은 실제 예제](Examples/README.md)는 실제 실행 snapshot에서 부모/자식·피해 경험 개체와 일부 cell을 그대로 골라낸 자료다. 데이터 값을 맞춰 만든 Golden이 아니다. `partial=true`, `training_ready=false`이며 전체 세계 복원·학습 dataset·입력 정답 사양이 아니다.

전체 learning snapshot과 `.eco`는 `Saved/` 아래에 있으므로 clone/pull로 오지 않는다. 현재 도구로 재생성한다. 다음 명령은 **프로젝트 폴더 `AdaptiveEcosystem/`에서**, 엔진/빌드가 종료된 뒤 실행한다.

```powershell
./Tools/Editor/run_ecosystem_validation.ps1 -Check ambush
./Tools/Editor/run_ecosystem_life.ps1 -Mode save -Name TeamLearningSave -Slot TeamLearning -Seed 23 -Duration 115 -SaveAt 95
```

결과는 `Saved/EcosystemLife_20261023/Encounter_ambush_LearningSnapshot.json`, `TeamLearning_LearningSnapshot.json`이다. helper의 출력 폴더 날짜는 기존 호환 경로이며 실행 날짜/새 SHA는 별도 manifest에 적는다. 사용자가 수동 편집한 맵을 생성 스크립트로 덮어쓰지 않는다.

`CaptureDiagnostics(true)`는 전체 cell을 복사하므로 학습/평가 요청 때 명시적으로 사용한다. 모든 production tick마다 full world JSON을 저장하지 않는다. `OnRuntimeSample`의 저주기 관찰이나 이 JSON만으로 모든 Native step 입력/내부 상태를 복원할 수 있다고 가정하지 않는다. 정확한 trajectory Golden에는 필요한 per-step 입력/상태·순서/난수 계약을 추가로 정의해야 한다. binary checkpoint는 별도의 same-build codec다.

## 7. 다음 작업의 단계별 완료 조건

### R0. baseline manifest와 실패 재현

현재 SHA·working tree, Native/encoder/model·weights 지문, 활성 backend, schema/obs/mask/contract hash, world profile/flags/config hash, seed·맵/geometry·관찰 시간 기준을 기록한다. 기존 V1/R1b/옵션21의 파일·Golden·OFF 결과를 보존한다. 오래된 `LongSeed*`/`Extended*`의 무상 성체 비축 버그 수정 전 결과는 새 생물학적 결론에서 제외한다.

### R1. leaf·기존 추론 파리티

현재 soil leaf는 C++/Python2400case, 최대 절대 오차0을 검증했다. [평가 도구](../../Tools/EcoVegetationEval/check_soil_parity.py)는 첫 인자로 실제 컴파일한 `soil_parity.cpp` 실행 파일, 둘째로 새 결과 JSON을 받는다. `build_and_run.ps1`은 별도의 통합 flat 평가기이며 이2400case 실행 파일과 혼동하지 않는다. 기존 `SoilParity.json`의 header 지문과 현재 파일도 대조한다.

이 결과는 soil leaf만의 증거다. 기존 neural Golden 통과, 전체 세계의 센서/운동/행동 궤적 일치, 통합 level의 장기 균형은 각각 별도 gate다. 비활성 flag·경계값·dt/물리 시간·유한값·허용 오차를 포함한다.

### R2. life 세계 mirror와 differential 평가

새 Python world/config는 기존 V1/v3 경로의 이름을 재사용해 조용히 의미를 바꾸지 않는다. leaf→개별 비용/기억/출생→한 지역→명시 입력 replay→다지역/이주 순으로 작은 executable slice를 닫는다. 각 단계에서 C++와 Python의 첫 divergence를 같은 초기 상태와 사건 순서로 좁힌다.

자원 보존·부분 섭식·부모 비용/Reserve0·영양 만료·episode dedup·Unknown·TTL·역할 lease·실패/죽음·인구 reservation·reset/재시작의 negative case를 포함한다. 실제 geometry를 mirror하지 못한 단계는 지원하는 slice와 제외한 조건을 명시한다. 예제 JSON의 일부 cell을30×30 전체 grid로 취급하지 않는다.

### R3. 무엇을 학습할지 선택

두 가지 작업을 구분한다. **기존 관측18에서 달라진 세계에 대한 강건성 평가/재학습**과 **새 경험/신체/장소 지식 입력을 쓰는 새 정책 계약**이다. 후자는 새 schema/obs 순서·normalization·mask/Golden·registry/adapter 버전이 먼저 필요하다. 기존 opt-in21은 장애물용이며 경험 입력3개를 넣는 빈 슬롯이 아니다.

최종 의도 우선순위와 rule/model/fallback 소유자를 적는다. 생존/안전·실제 이주·Social 선호·개인 욕구·정책 요청이 충돌할 때 어느 지점에서 거절/보정됐는지 진단해야 한다. 여러 모델/규칙이 같은 개체의 위치/대사를 최종 writer로 동시에 쓰지 않는다.

### R4. 학습과 평가

현재 문서 작업에서는 새 학습을 시작하지 않는다. 담당 사용자가 요청한 범위·장비·시간/스텝·비용 내에서 학습한다. 이미 승인된 범위를 매번 다시 확인할 필요는 없지만, 예산/새 외부 비용이 불명확하면 비학습 mirror/평가부터 진행하고 필요한 조건을 확인한다.

train/validation/holdout seed·장면·날씨/밀도·초기 gene/food·기간을 분리하고 사전 성공 기준을 고정한다. 단일 seed나 가장 좋은 checkpoint만 골라 개선을 주장하지 않는다. 자연 무인, 무해 방문, 실제 급습/추격, 명시 가뭄, 운영 복구를 분리한다. 시간 배속/세대 단축/포획 상한도 config로 명시한다.

평가는 생존·개체당/지역별 food/영양 수지, 대사/사냥 비용·기아·포식·출생 원인, 이주 출발/실제 인계/정착/실패, Unknown 누출·행동 비율, 실제 후손 기여와 cohort 분포를 포함한다. 보상을 올리기 위해 자연 개체를 무한 공급하거나 보호 규칙을 몰래 끄지 않는다. 출생을 단순히 많이 만든 정책이 게임에 더 좋은 정책인지는 별도 제품 판단이다.

### R5. export·Native 교체·롤백

`export_weights_v3.py`는 기본 `--out`이 실제 UE `AI/Policy` 경로다. **candidate는 먼저 별도 Saved/작업 폴더로 export**하고 diff를 검토한다. 실제 parser의 `--model`, `--config`, `--out`, 선택적 `--brain-file`을 확인한다. 이 문서는 존재하지 않는 life 학습 config나 학습 완료 모델 파일을 제공한다고 주장하지 않는다.

기존 runtime registry의 `eco.V3Brain.Startup`/명령줄 `-EcoV3Brain=` 등은 모델 파일 선택 지점이다. 모델이 I/O 검사를 통과해 로드됐다는 사실만으로 ON-world 적합성·환경 파리티를 승인하지 않는다. `--world-label` 문자열도 mirror/환경 호환 검증을 대신하지 않는다. 실패 시 기존 모델/세계 상태를 보존하는 거절·fallback을 실제 테스트한다.

입력 schema/hash·mask·shape·dtype·activation·weights 지문·유한값, masked logits/argmax와 tie, 결정/교체 시점, 기존 request/executed/규칙 의도의 분리를 검증한다. 잘못된/손상된 파일·obs/mask/version 불일치·NaN·금지 행동은 negative case로 둔다. C++/빌드 입력 변경이면 직접 Editor UBT→전체 관련 자동화→실제 서버·복수 Client/패키지 확인 순서다. Python 런타임 추론을 넣지 않는다.

## 8. 모델 인계 묶음의 최소 항목

| 묶음 | 포함할 내용 |
|---|---|
| 기준 | Source SHA/dirty 유무, Python/UE·필수 library 버전, 실행 명령·기간·seed·장비/비용 |
| 모델 | model ID·파일 sha256, encoder/schema/obs 순서·정규화·mask·argmax·weights 구조 |
| 세계 | world profile/version·flags/config hash, geometry/외부 입력·시간/단위·난수·동작 순서·차이 목록 |
| adapter | producer/consumer·rule/model/fallback 우선순위, 누가 Raw Request/최종 의도를 작성하는지 |
| 평가 | baseline/candidate·holdout 결과·분산/실패 사례, Golden·첫 divergence·음성 케이스 |
| 게임 결과 | 실제 outcome·M4 수지/인구·후손·이주, Client authority0·시각/패키지 검증 |
| 배포 | 후보/승인 상태, 기존 모델 보존·rollback 경로, save/build 호환·미지원 범위 |

모델 metadata를 설계할 때 필요한 항목이라는 뜻이며 현재 모든 항목의 runtime 자동 검사가 구현됐다는 뜻은 아니다. 큰 `.zip`/체크포인트·데이터셋을 무조건 Git LFS에 넣지 말고 팀 저장 위치·용량·보관 정책을 정한다. PR에는 재현 가능한 작은 계약/Golden/manifest와 결과를 남긴다. 생태 저장 파일이나 사람 식별정보를 공개 모델 학습 자료에 섞지 않는다.

## 9. 서버·네트워킹 담당과의 인계

학습 담당은 모델/encoder/세계/adapter 판과 예상 비용·주기를 제공한다. 서버 담당은 실제 권위 snapshot·감각 입력 gather·실행 outcome/장부·새 모델 적용/거절 경계와 동일 build Client 구성을 확인한다. Actor 보간 위치·수신 요약으로 서버 policy를 학습하거나 Client에 모델/기억 전체를 복제해서 연결 문제를 해결하지 않는다.

새 관측 때문에 `EcoMassReplicationTypes`를 수정할 필요가 있는지 먼저 따진다. 기본 policy 입력은 서버 내부 데이터다. 신체/Activity가 실제 클라이언트 표현에 필요할 때만 작은 DTO 필드를 별도 검토한다. 저장·ID·자원 거래를 바꾸면 서버 안내의 호환/재시작 acceptance를 함께 수행한다.

## 10. 완료 보고에서 구분할 말

- “leaf parity 통과”, “정책 inference Golden 통과”, “해당 world slice trajectory 일치”, “실제 UE ON-world 검증”, “재학습 성능 개선”은 다른 주장이다.
- “데이터를 export할 수 있음”은 “그 데이터로 학습 가능/정상화 계약 완료”가 아니다.
- “자식 gene 평균 변화”는 “경험이 유전됨/PPO 온라인 학습/유익한 자연선택 증명”이 아니다.
- 현재 여러 seed1800초·동시 Client2·패키지 증거는 새 모델의 holdout 결과가 아니다. 새 모델 적용 후 자기 검증을 남긴다.
- 다른 담당의 수락/훈련 완료를 대신 기록하거나, 실패한 candidate 때문에 기존 weights/Golden/기준 세계를 삭제하지 않는다.

후속 AI 시작 요청은 [역할별 프롬프트](../Team/ECOSYSTEM_AGENT_START_PROMPTS_20261024.md)를 사용한다. 이 안내를 읽는 것 자체가 학습·모델 교체·대규모 비용 작업의 실행 승인이라는 뜻은 아니다.
