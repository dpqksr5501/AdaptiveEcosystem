# 생태계 life-v1 실행·팀 연결 계약

사용자의 “남은 작업 전부 진행” 요청으로 연결한 soil-v1/life-v1의 실제 실행·지원 범위·검증·팀 인계 기록이다. 목표 전체와 현재 지원 범위는 [상태표](ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md)를 구분해 읽는다. branch `codex/social-shelter-handoff`, 작업 시작 HEAD `ecfd82f`, 구현 기록 **`d095948`**이다. 기존 dirty 변경을 보존했으며 10-23의 로컬 검증 뒤10-24 사용자 요청으로 공유 커밋을 만들었다. 새 역할별 작업은 [팀 AI 안내](../Team/ECOSYSTEM_AI_COLLABORATION_20261024.md)를 따른다.

## 현재 실행 경로

`/Game/JYU/Maps/LV_JYU_Ecosystem`의 기존 spawner `bEnableEcosystemLife`만 opt-in한다. Native `FWorldConfig::bEcosystemLife`는 **life-v1 세계 규칙 묶음**이며 PPO의 관측/출력 차원이나 새 학습 가중치가 아니다. 원본 팀 맵과 기존 다른 맵의 기본 설정은 유지한다. `SocialControl=0`도 유지한다.

기존 `FEcoIntegratedV3Fragment` 안에 개체별 `EcoLifeV3::FIndividual`을 두며 새 전역 생태 관리자나 복제 Subsystem을 만들지 않는다. Native Step이 위치·대사·섭식·포획 writer다. 기존 spawner의 완료 GT 경계가 부모/스폰/피해 결과를 조정하고 M4가 인구·사망·이주 receipt를 확정한다. Client는 기존 Bubble DTO와 식생 Field DTO만 받는다.

## 연결한 기능과 계약

| 기능 | producer → consumer → 실제 결과 |
|---|---|
| 이주 실패 | 기존 무진행 진단 → 한 번 복귀 → 재실패 시 `Abandoned`. 지역 안 개체는 주민으로 복귀한다. 지역 밖 개체는 `bStranded`로 계획/목적지 예약을 해제하고, Native no-clamp/no-feeding guard를 유지한 채 멈춘다. teleport나 무한 경로 재시도는 하지 않는다. 대사·사망은 계속된다. |
| 장소 보고 | authored route `bSharesHabitatReports` → 30초 간격·90초 TTL·정량화된 목적지 보고 → 먹이/30초 회복 전망/수원/위험/은신 면적/혼잡/거리 점수. 기존 맵의 OFF 경로는 원래 판단을 유지한다. 보고가 없는 원격 지역의 현재 정답을 개체가 조회하지 않는다. |
| 개체 다양성 | session seed + StableAgentId → 재현 가능한 founder genome. 자식은 부모 평균 + 제한 변이, speed/size `[.9,1.1]`. 큰/빠른 몸은 유지 비용을 낸다. 유전과 경험은 별도 상태다. |
| 조건부 출생 | 성숙 180초·영양·주민/이주 상태·부모 둘·혈연 제외·30초 incubation → 실제 지면/자리/공간 식량·상한 재검증 → 기존 Mass spawn와 인구 예약 완료. 성공할 때만 부모 에너지 각 `.2`와 300초 cooldown·후손 기여를 반영한다. 자식 에너지 `.4`, 초식 비축량 **0**으로 성체 초기 비축을 복제하지 않는다. initial/recovery/natural origin을 구분한다. |
| 공간 출생 예산 | 기존 비공간 압력의 food 단위를 Native에 그대로 대입하지 않는다. `RequestNaturalBirth`가 spatial ledger의 예상 인구당 food≥1과 기존 global/regional/projected population reservation을 사용한다. 기존 wave와 비공간 압력 계산은 보존한다. 정상 예산 거절은 Count=0 예약을 완료하여 정리한다. |
| 성장/표현 | 나이 0..180초 → 성장 `.75..1` → 실제 이동 능력·terrain sweep 반경 + Bubble BodyScale byte/128 → 표현 Actor scale·크기 보정 locomotion/stride·기존 지면 IK. 새 리그/morph/비행 지원을 주장하지 않는다. |
| 경험 | 직접 FOV·실제 static LOS·관측 위치와 속도 → harmless/noise/pursuit/damage/witness. familiarity/curiosity/fear/hostility와 Unknown damage fear를 분리한다. 기억 decay·16 episode dedup·5초 노출 상한·보고 TTL을 사용한다. shared report는 직접 관측 시각/좌표를 만들거나 재전파하지 않는다. |
| 플레이어 피해 | 새 세계의 F 입력 → owner RPC → 서버에서 요청 주기/실제 몸의 거리·방향·LOS 검사 → 최대32 대기 입력 → 완료 경계의 HP 피해 → 기존 M4 external death receipt. Client target/position/damage 입력은 받지 않는다. 공격자를 못 보면 Unknown이며 사람에게 원인을 돌리지 않는다. |
| 흔적 조사 | 실제 Native 이동 → 지역별 256개/64 spatial bucket·20초 TTL 흔적 → 후보≤16·시야/LOS·최대12초 조사/4초 무진행/8초 cooldown → 기존 Native threat Step의 방향 의도. 현재 표적 좌표를 흔적 대신 질의하지 않는다. |
| 협동 | 기존 Pack 실제 감지/공유 → stable target 기반 Lead/Intercept 3초 lease → 재확인·역할 변경/근거 소실/휴식·죽음 시 정리. 최종 capture는 Native 단일 경로이며 근접 terrain LOS 거절 mask를 소비한다. |
| 식생/수원 | 기존 맵에 새 얕은 수원 BP 하나. Forest 후보9개 지면 조사, 선택 patch 수심 최대 약12cm·은행 높이 약82cm. 명시적 hydraulic connectivity만 공급한다. 수변/관목 ISM 형태·높이를 구분하고 실제 food density가 줄면 2D Native sight screen도 줄어든다. 보호 은신처/포획 면역은 아니다. |
| 지속 규칙 | life-v1은 지역 사슴≤8이면 신규 포획을 제한하고 지역당60초의 포획 상한2를 적용한다. 이는 콘텐츠 보호용 게임 규칙이며 자연 평형을 증명한 결과가 아니다. |

초기 founder는 시연 장면의 기존 성체이므로 `Born=현재시각−180`이다. 실제 자식만 `Origin=NaturalBirth`, 부모 ID와 `max(parent generation)+1`을 기록한다. Native 기존 `Body.Generation`의 respawn 의미와 혼용하지 않는다. 한 번 피해를 받았다고 기존 유전자가 변하지 않는다.

## 저장과 복원

`eco.Ecosystem.Save <slot>` / `eco.Ecosystem.Load <slot>` 또는 spawner의 Blueprint API를 사용한다. 파일은 `Saved/Ecosystem/<slot>.eco`, slot은 길이≤48의 문자/숫자/`_`/`-`로 제한한다.

- schema1, 길이·checksum, **같은 runtime module hash**·맵·모델을 검사한다. 현재 형식은 동일 빌드의 실제 프로세스 재시작용이며 다른 빌드/Editor→packaged 변환을 자동 migration하지 않는다. 미지원 저장을 새 자원/개체로 초기화하지 않는다.
- GT/Mass processing 밖·resource transaction 완료·pending spawn 없음에서만 수행한다. Native grid/수분/환경/난수·시계, 실제 개체/부모/유전/경험·출생 대기, 기존 인구/자원/receipt watermarks, persistent herd/이주/보고/흔적을 함께 저장한다.
- Entity handle/Actor/ISM index는 영속 identity로 사용하지 않는다. stable ID/지역/종/무리 ID에서 새 런타임 개체와 index를 재결합한다.
- 읽은 상태 전체를 검증한 뒤 새 개체를 준비하고 commit한다. 준비 실패는 이전 개체/allocator/counter를 유지한다. 새 프로세스의 world epoch를 사용하며 실제 서버 시계부터 복구한다. offline 무제한 catch-up은 하지 않는다.
- 일시적 Shelter lease와 아직 결과가 없는 player input은 취소한다. 실제 완료된 사망/섭식/출생을 다시 실행하지 않는다. 출생 incubation은 저장한 부모/기한으로 다시 검증한다.

저장은 Native 사망을 M4가 아직 확정하지 않은 경계에서 거절하므로 다음 완료 경계에 재시도한다. `Step` 또는 Native 시간이 뒤로 가는 live rollback은 거절한다. 재시작 후 새 초기 세계보다 앞선 checkpoint를 복원하는 용도다. Native adoption ordinal도 저장하여 이후 개체 초기화 순서를 유지하고, 이동 discontinuity revision은 새 world의 최대 revision보다 크게 부여한다.

저장 행은 사체를 포함해 최대1024/현재 living cap의 2배로 제한하되, 살아 있는 개체만 기존 인구 cap에 청구한다. 죽은 개체의 제거 시각을 보존하고 추적 대상의 일시 배열 index는 버린다. 은신처는 저장된 policy cover 순서를 보존하면서 실제 새 World의 위치·크기·등록을 확인해 재결합한다. 늦은 등록 순서가 달라도 같은 실제 은신처면 복원하며, 지형/크기/위치가 달라진 경우는 거절한다.

## 위험 기억과 운영 복구

실제로 인식된 사람 피해/목격만 지역 위험에 반영한다. 지역당32 episode, 5초 노출 제한, 300초 감쇠를 사용하며 사람의 실시간 위치를 저장하지 않는다. 이 값도 기존30초 장소 보고·90초 TTL을 통해 이웃 계획에 전달하고 checkpoint에 보존한다. Unknown 피해를 사람 위험으로 바꾸지 않는다.

`Spawner->QueuePopulationRecovery(RegionId, bPredator)` 또는 `eco.Ecosystem.Recover <region> <Herbivore|Wolf>`는 명시적인 서버 운영 요청이다. 해당 종의 실제 인구가0일 때만 최대2 founder를 기존 food/인구 예약·실제 지면/빈 자리에 생성한다. 큐32·중복 대기 거절·15초 기한·지역/종별300초 cooldown을 적용한다. 부모0/세대0/Origin=Recovery이며 자연 출생으로 세지 않는다. cooldown은 저장하고 미완료 요청은 로드 시 취소한다. 자동 보충·loot/퀘스트 지급 경로는 추가하지 않았다.

## 실제 검증 근거

직접 UBT `Milestone_Final_20261023_234012.log` 성공 후 전체 자동화 `EcosystemLife_20261023/AutomationFinal`은 **225개 = 224 Success + 기존 예상 warning1, 실패/미실행0**이다. 이주 종료/no teleport, 경험/Unknown/dedup/TTL, 유전/성장/transport, Native codec·은신처 재결합, 흔적 상한/만료, capture 거절, 차폐 제거, 지면 projection·출생 Energy/Reserve와 editor-only 은신처 template 회귀를 포함한다.

저장된 BP7종/10 habitat/날씨3개·life/soil opt-in·실제 rig/morph를 새 프로세스에서 재로드 확인했다. 무해 방문·급습·실제 달리기 추격은 동일 seed23/늑대0 fixture로 감각/경험/실행 반응을 확인했다. 운영 복구는 실제 권위 공격으로 빈 종을 만든 뒤 API로2 founder를 공급했다. 이 fixture는 자연 급습·자연 멸종 분포를 뜻하지 않는다.

최신 동일 빌드에서 자연 세계156 living 개체(자연 자식 포함), 실제 Unknown 경험144 living 개체, 사체가 남은 운영 복구 세계150 living 개체를 각각 새 프로세스에 정확 복원했다. missing/checksum/version 거절·live rollback 거절은 상태 비변경을 대조했다. 재시작 후 실제 Step/자원 수지가 계속 일치했다.

장기 실행/최종 시각·멀티·성능·패키지 수치와 실행 조건은 [최종 evidence](Evidence/EcosystemLife_20261023.json)에 집계한다. 과거 관찰 도구의 잘못된 World/Python API와 출생 reserve 수정 전 결과는 Saved 이력으로 남기며 최종 결론에 혼합하지 않는다. 런타임 오류 여부와 관찰 도구 오류를 분리한다.

## 장기·화면·멀티와 성능

Native life/movement/복제의 장기·PIE·동시 클라이언트 검증은 `Milestone_Final_20261023_230551.log` 빌드다. 이후 변경은 에디터 전용 FacingArrow template·해당 회귀 검사와 label cook 설정이며 Native 규칙은 바꾸지 않았다. `234012` 빌드에서 전체 자동화/저장/가뭄 이주/패키지를 다시 통과했다. 최종 성공 여부와 원시 파일은 evidence를 따른다.

| 관찰 | 실제 결과 |
|---|---|
| seed11, 1800 simulation seconds | 종료66(초식64/늑대2), 관찰 자연 자식57, 최대 세대3 |
| seed23, 1800 simulation seconds | 종료117(초식112/늑대5), 관찰 자연 자식97, 최대 세대2 |
| seed47, 1800 simulation seconds | 종료67(초식65/늑대2), 관찰 자연 자식64, 최대 세대3 |
| seed23 동일600초 life ON/OFF | ON140/자식32, OFF96/자식0. **soil은 양쪽ON**이다. 여러 규칙 묶음의 비교이며 개별 원인의 인과 효과가 아니다. |
| 협동 사냥 | 위 세 장기 실행에서 Lead/Intercept가 같은 표적에 동시에 배정된 관찰 표본24/23/24. 표본 수를 독립 사냥 횟수로 읽지 않는다. 실제 역할/이동 변경과 영양 수지는 JSON에 기록한다. |
| 수지 | 모든 최종 관찰의 food/소비/성장/환경 손실과 M4 장부 오차0. 사체 영양의 최대 잔차 약2.11e-15. |
| 실제125초 PIE | 자연 자식157의 Actor/Native scale 일치, 약.73→.828125, `ABP_JYU_Deer_C`, 근거리 기존 IK alpha1.0. 실제 풀·얕은 물과 어린 몸 화면을 직접 확인했다. 성체 리그를 축소한 prototype이다. |
| Dedicated160초/관찰110초 + Client2 | 두 연결을 동시에28.19초 관찰. 근거리 검사118/29표본의 field 누락0, Client 논리/Native/이주 subsystem0. late join 자식157 scale 오차 허용2/128 내, 불일치0. |

장기 실험은 fixed-step benchmark로 가속한 **시뮬레이션 시간**이다. 위 자연 실행의 지역 이전은0이었으므로 부족→이주 인계는 별도 가뭄 fixture19건으로 검증했다. cohort의 평균 유전자/후손 기여는 관찰된 표본이며 평형·유익한 선택·인구 증가가 항상 좋은 결과라는 증명이 아니다.

동시 클라이언트는 같은 PC의 D3D11 960×540 두 프로세스다. Native batch p95 약2.244ms/max31.30ms는 Native 실행 구간이며 전체 서버 frame CPU가 아니다. CSV의 서버 FrameTime p95 약34.02ms는30Hz pacing을 포함한다. 서버의 `Exclusive/GameThread/*` 중 이름이 EventWait인 scope를 제외한 합계 p95는4.10ms이며 **계측된 scope의 파생 합계**다. 전체 GT CPU로 부르거나 Native 값과 합산하지 않는다. 이 scope의 최대1304ms에는 QA의 마지막 JSON 직렬화/저장이 포함된다. production은 이 Python 관찰기를 실행하지 않는다.

ClientA/B의 CSV GameThread p95는2.762/2.769ms, RenderThread4.221/4.449ms, Frame4.237/4.481ms다. ClientA 최대 frame350ms의 hitch가 남아 있어 p95만으로 감추지 않는다. 접속/지역 전환의 원인별 profiling은 후속 성능 개선 지점이다. 물리 메모리 p95는 서버2005/ClientA2593/ClientB2574MB였다. NetDriver total·표본 byte rate와 전체 p95/max는 evidence에 있다. 현재 장면/표현 수의 결과이며500/1000개체·WAN/손실 네트워크 지원 검증이 아니다.

이 실행에서 Driver의 직접 `*BytesPerSecond` 카운터는0으로 남았으므로 무통신으로 해석하지 않는다. 보고서의 대역폭은 **누적 NetDriver total byte 차분 / 실제 관찰 wall seconds**이며54개 유효 구간의 수신 p95 약13,172/송신22,910B/s, 최대19,010/39,072B/s다. 전체 NetDriver 트래픽이며 생태 DTO만의 크기가 아니다. 샘플이2초 안팎이므로 순간 패킷 burst의 최대치도 아니다.

## cook·패키지

직접 `AdaptiveEcosystem Win64 Development` UBT 성공 후 UAT는 compile을 건너뛰고 owned 맵 cook/stage/pak/archive를 완료했다. 실행 파일은 `Saved/EcosystemLifePackage/Windows/AdaptiveEcosystem.exe`다. D3D11 1280×720/NoSound/observer pawn cycle의 실제90초 실행에서 Ready1·Step90·자연 출생·사체 결과·정상 종료와 실제 화면을 확인했다. Python 관찰기/추론을 실행하지 않는다. 음소거 시험을 실제 소리 청취 검증으로 설명하지 않는다.

초기 package의 weather soft/string 참조 누락을 owned `PAL_JYU_EcosystemRuntime`의 explicit AlwaysCook과 DefaultGame의 non-editor-only PrimaryAssetLabel scan으로 수정했다. registry의 이름만으로는 부족하므로 실제 `ReferencedSet.txt`와 런타임 load를 대조한다. 기존 은신처의 FacingArrow도 `CreateEditorOnlyDefaultSubobject`로 고쳐 파생 BP의 template import 오류를 제거했다. 원본 팀 맵·SHC 에셋·기존 은신처 BP 바이트는 수정하지 않았다. 최종 package runtime의 Error/알려진 missing FX는0이다. [패키지 화면](Evidence/EcosystemLife_Packaged_20261023.png)은 관찰 Pawn 재배치 시험이며 일반 플레이의 카메라/캐릭터 연출 품질을 보장하는 장면은 아니다.

## RL 인계

`herbivore_rl/env_v2/vegetation_v1.py`는 soil-v1 leaf mirror이고 기존 training config에는 자동 활성화하지 않았다. `Tools/EcoVegetationEval/soil_parity.cpp`와 `check_soil_parity.py`로 실제 C++ leaf **2400개를 비교해 최대 절대 오차0**을 확인했다. 전체 life-v1 Python world mirror/새 가중치/재학습 완료를 뜻하지 않는다. V1 7/4와 기존 v3 18/5·mask2/opt-in21 계약을 보존한다.

| 기존 정책과 달라진 세계 | RL 연결 시 합의/재현할 것 |
|---|---|
| Soil growth/환경 손실/수원·차폐 | 기존18 슬롯의 의미/정규화는 유지한다. 새 입력이 필요하면 별도 schema/version으로 선언한다. 실제900셀 snapshot과2400개 leaf parity를 시작점으로 사용한다. |
| 개별 경험·호기심/공포·Unknown | 현재 `IntegratedControlHook`의 명시적인 rules-v1 overlay다. Unknown은 공격자 좌표/사람 원인 라벨을 주지 않는다. 학습의 정답과 관측 증거를 분리한다. |
| Genome/growth·유지 비용 | 제한된 speed/size가 실제 속도/대사/접근 반경을 바꾼다. founder/부모/출생 시각·seed를 실제 snapshot에서 복원한다. policy request 자체를 새 행동처럼 덮어쓰지 않는다. |
| 흔적/협동/포획 제약 | 현재 `EvidenceThreatHook`과 capture mask가 읽는 rules-v1이다. TTL/lease·조사 중단·보호/포획 상한을 Python 세계에도 명시해야 한다. |
| 영양·출생·이주 보고 | 사체 접촉 영양·부모 비용/Reserve0·30초 보고·90초 TTL·실패 종료를 재현한다. 기존 world의 reward/instant reward를 중복 보존하지 않는다. |

기존 [V3 입력 순서·정규화/action/mask](../RL_Policy/POLICY_CONTRACT_V3.md)와 모델 registry 검증을 유지한다. Native 단위1=200cm, Step=2/15 simulation seconds이며 경험/출생/TTL은 서버 simulation seconds를 사용한다. `*_LearningSnapshot.json`의 관측/request/mask·실행·실제 부모/규칙/세계 seed·시간은 평가 예제이고 `training_ready=false`다. 새 정책은 현 규칙을 명시적으로 대체하거나 유지할 adapter 버전을 선택한 뒤 Golden/전체 궤적 비교가 필요하다. 새 가중치 생산/보상 튜닝은 사용자 지시에 따라 RL 담당 후속으로 남긴다.

## 팀별 연결 지점과 실패 확인

파일은 `Source/AdaptiveEcosystem/` 기준이다. 다른 backend의 능력을 이 표의 Native 지원으로 확대하지 않는다. `bEnableEcosystemLife`는 Integrated Native V3에서만 유효하며 지원하지 않는 조합은 시작 검증에서 거절한다.

| 계층 | 확장할 실제 지점 | 소비 시점·결과·주의 |
|---|---|---|
| World / 환경 | `World/EcoRegionEnvironmentAdapter`, `AEcologyRegion::SetEnvironmentState`, `AEcoVegetationHabitat` | 서버 환경을 기존 native 환경 인계가 읽는다. 물은 `ConnectedFreshWater`·실제 수면 Z·높이/배수로 공급한다. 시각 물 재질이나 Niagara가 food를 생성하지 않는다. |
| 공간 자원 | `AI/Policy/EcoVegetationV3.h`, `EcoWorldV3.h::FFoodGrid`, `Ecology/EcologySpatialFood.cpp` | native 한 Step의 성장·섭식·환경 손실을 기존 `CommitSpatialFood`로 확정한다. `FoodGrid`와 별개 patch 잔고를 추가하지 않는다. 부분 지급·0잔고는 기존 배분 경로다. |
| Social / 무리 | `Mass/EcoHerdMigration.cpp`, `FEcoHerdTravelFragment` | 30초의 authored 목적지 보고와 90초 TTL을 소비한다. 공동 목적지/실패 상태만 소유한다. 실제 몸 이동과 M4 `RecordMigrations` 완료를 별도로 확인한다. `Abandoned`와 stranded를 임의 teleport로 처리하지 않는다. |
| 경험 / 감각 | `EcoPolicyV3IntegratedProcessors.cpp::ObservePlayers`, `EcoLifeHistoryV3.h::FMemory` | GT가 실제 Pawn 위치·속도·눈높이와 최대16개 실제 Player.Footstep emission을 수집한다. FOV/정적 LOS/식생 차폐·거리·날씨 청각 검사를 통과한 증거만 개체 기억으로 넣는다. `Suffer`의 공격자 식별은 후속 소리로 바뀌지 않는다. |
| 플레이어 전투 | `Creature/Player/EcoPlayerEcologyComponent::TryStrike`, `EcoCreaturePlayerOutcomes.cpp` | F 키 또는 `Bridge->TryStrike()` → owner RPC → 서버 요청 큐(32)·1초 cooldown·3초 기한 → 완료 자원 경계의 실제 HP−30. 대상/위치/피해량을 RPC 인자로 추가하지 않는다. 실제 LOS/300cm/방향/높이 검증이 실패하면 피해가 발생하지 않는다. |
| 사냥 / 영양 | `EcoMovementTracesV3.h`, Native `EvidenceThreatHook`, `EcoCreatureCarcass.cpp` | 기존 threat Step이 유일한 포획 경로다. M4가 사망을 수락한 뒤에만 총 `.6` 사체 영양을 실제 최근 참여자에게 분할한다. 20초의 유효 식사 위치에 실제 도착해야 섭취한다. 기존 instant reward는 life 세계에서 함께 지급하지 않는다. |
| 출생 / 개체 | `EcoCreatureNaturalBirth.cpp`, `RequestNaturalBirth`, `FEcoIntegratedV3Fragment::Individual` | 부모 둘·성숙·영양·실제 자리와 기존 인구 예약을 검사하고 기존 `Spawn`을 소비한다. 실패/0승인은 예약을 완료한다. 실제 출생만 부모·세대·비용/후손 기여를 기록한다. `SpeciesTotals.Births`의 기존 누적 논리 생성 의미를 자연 출생 횟수로 바꾸어 읽지 않는다. |
| 표현 / 네트워크 | `EcoCreatureLifecycle.cpp`, Bubble `BodyScale`, `EcoCreatureAnimInstance.cpp` | 서버 Activity와 byte/128 크기를 기존 DTO로 전달한다. Client는 받은 크기와 Activity로 움직임/경계 pose·stride·기존 IK만 표현한다. AnimNotify/Actor에서 피해·섭식·출생을 실행하지 않는다. |
| 저장 | `EcoEcosystemCheckpoint.cpp`, `EcoEcosystemArchive.h` | 완료 GT 경계에서 `Spawner->SaveEcosystem(TEXT("MySlot"))` / `LoadEcosystem` 또는 동일 콘솔 명령. false면 첫 `[EcoCheckpoint]` 거절 이유를 읽는다. 다른 빌드 파일을 지우거나 자동 새 세계로 바꾸지 않는다. |
| RL | `AEcoVegetationField::CaptureDiagnostics(true)`, Inspector JSON | 실제 셀 900개/지역과 seed·시간·환경/규칙을 복사한다. `Saved/EcosystemLife_20261023/LifeRestart_LearningSnapshot.json`은 실제 세계/개체 예제다. 학습 가능 모델 입력으로 자동 승격하지 않는다. |

`CaptureAgent`의 `life`에는 원인/반응·부모/유전/성장·사체 수지가 있고 기존 `request`·`executed`는 그대로다. HUD Tab 선택/R 기록으로도 읽는다. Client의 논리 개체 목록은 항상 빈 목록이어야 한다. 읽기 전용 `CaptureStepPerformance()`의 p95는 **Native batch/step CPU**이며 전체 서버 frame p95와 같지 않다. process memory와 NetDriver byte/rate도 별도 단위다.

## 재현 순서

프로젝트 폴더에서 모든 빌드/에디터 프로세스가 정상 종료된 뒤 실행한다. `run_ecosystem_validation.ps1`은 시작 시 busy를 검사하고 기존 프로세스를 종료하지 않는다.

```powershell
./Tools/Integration/build_integration_milestone.ps1 -Milestone Final
./Tools/Editor/run_ecosystem_validation.ps1 -Check automation
./Tools/Editor/run_ecosystem_validation.ps1 -Check assets
./Tools/Editor/run_ecosystem_validation.ps1 -Check harmless
./Tools/Editor/run_ecosystem_validation.ps1 -Check ambush
./Tools/Editor/run_ecosystem_validation.ps1 -Check chase
./Tools/Editor/run_ecosystem_validation.ps1 -Check recovery
./Tools/Editor/run_ecosystem_validation.ps1 -Check pie
./Tools/Editor/run_ecosystem_life.ps1 -Mode load -Name RecoveryLoad -Slot RecoveryRestart -Wolves 2 -Duration 20
./Tools/Editor/run_ecosystem_life.ps1 -Mode load -Name EncounterLoad -Slot Encounter_ambush -Wolves 0 -Duration 20
./Tools/Editor/run_ecosystem_life.ps1 -Mode save -Name FinalSave -Seed 23 -Duration 115 -SaveAt 95 -Csv
./Tools/Editor/run_ecosystem_life.ps1 -Mode load -Name FinalLoad -Seed 23 -Duration 25
foreach($taskSeed in @(11,23,47)) {
  ./Tools/Editor/run_ecosystem_life.ps1 -Name "FinalExtended$taskSeed" -Seed $taskSeed -SimulationSeconds 1800 -Benchmark -SampleSeconds 15 -Duration 600
}
./Tools/Editor/run_ecosystem_life.ps1 -Name FinalOn23_600 -Seed 23 -SimulationSeconds 600 -Benchmark -Duration 300
./Tools/Editor/run_ecosystem_life.ps1 -Name FinalOff23 -Seed 23 -SimulationSeconds 600 -Benchmark -Life 0 -Duration 300
./Tools/Editor/run_ecosystem_life.ps1 -Name FinalDrought23 -Seed 23 -SimulationSeconds 600 -Benchmark -SampleSeconds 5 -Duration 300 -Wolves 0 -DroughtRegion Barren
./Tools/Editor/test_vegetation_network.ps1 -Map /Game/JYU/Maps/LV_JYU_Ecosystem -AuthoredWeather -AuditFolder EcosystemLifeConcurrent_20261023 -OverlapClients -ClientAAt 10 -ClientBAt 60 -Duration 110 -ExitAfter 160
./Tools/Editor/package_ecosystem.ps1
./Tools/Editor/test_ecosystem_package.ps1
# 마지막으로 일반 Python에서 Tools/Editor/summarize_ecosystem_life_evidence.py를 실행한다.
```

플레이어 시험은 동일 seed·늑대0·실제 authority Pawn 재배치 fixture다. chase는 실제 CharacterMovement 입력, 피해는 실제 `TryStrike`를 사용한다. 개체 위치·기억·HP/food를 직접 설정하지 않는다. 자연 플레이/자연 급습 분포로 설명하지 않는다. `FINISHED`는 각 조건에 필요한 실제 반응 검사를 포함한다.

`-DroughtRegion Barren`은 별도의 명시적 개발 fixture다. 기존 `ApplyFoodFractionForAudit`가 실제 food를0으로 줄이며 기존 M4 habitat 제거 receipt를 남기고 해당 세션의 재생을 중지한다. 자연 날씨/평형 실험과 혼합하지 않는다. 이600초 실행에서 실제 Barren→Forest 인계19건·정착과 장부 오차0을 확인했다. 돌아갈 수 없는 지형의 Abandoned 계약은 단위 회귀로 검사했으며 이 장면을 그 실패 장면으로 설명하지 않는다.

## 수정할 때의 주의

기존 `setup_jyu_ecosystem.py`로 맵을 재생성하지 않는다. 후속 `extend_jyu_ecosystem_life.py`는 기존 owned 맵만 편집하고 label/owner 충돌을 거절한다. UBT/에디터/LiveCoding/dotnet/MSBuild/ShaderCompileWorker가 실행 중이면 새 UBT를 시작하거나 중단하지 않는다. Source·Content는 `d095948`에 기록됐고 이후 작업 트리 상태는 실제 Git을 확인한다.
