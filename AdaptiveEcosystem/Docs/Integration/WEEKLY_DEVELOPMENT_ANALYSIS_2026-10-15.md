# 주간 개발 분석 및 테스트 실행 안내 — 2026-10-12~10-15

작성일: 2026-10-15, 한국 시간. 분석 대상: 로컬 `M4`, HEAD `67c860c`(`origin/M4`와 동일), 직전 주 기준점 `6235742` 이후 9개 커밋.

이번 주의 핵심은 **동물이 움직이는 기능을 생존·자원·사망·이주·복제로 이어지는 공통 실행 경로에 연결하고, 그 위에서 사슴·늑대 StateTree를 독립적으로 실험할 기반을 추가한 것**이다.

이 보고서는 커밋 diff, 현재 Source, 문서, 로컬 Saved 로그를 대조했다. 이번 분석 중 새 빌드·게임·자동화 테스트를 실행하지 않았다. 아래 성공 기록은 기존 실행의 증거이며 현재 HEAD 전체의 게임 회귀 통과 선언이 아니다. 특히 10월 13일 M4 실행 뒤 추가된 10월 14일 SpeciesAI는 별도의 행동 검증이 필요하다.

## 1. 범위와 변경 규모

- 기간은 월요일 10월 12일~현재 10월 15일이다. 해당 M4 커밋은 10월 13·14일에 있다.
- 총 331개 파일 변경: Source 100, Docs 30, Content 198, 기타 3. 전체 diff는 8,396줄 추가, 1,227줄 삭제다. Content에는 World Partition 외부 Actor와 LFS 포인터가 포함되므로 파일 수를 기능 수로 해석하지 않는다.
- 분석 시작 시 작업 폴더에 미커밋 변경은 없었다.
- `Branch_Sinhyeok`/`upstream/Branch_Sinhyeok`에 별도 V3·R2·R3 개발 이력이 있지만 현재 M4에 포함된 구현으로 합산하지 않는다. 이번 M4 diff에서 Python 학습 디렉터리 `herbivore_rl/` 변경은 없다.
- 10월 8~11일에 이미 들어온 동물 BP·감각·Social Shelter handoff·기초 생존/복제는 이번 주 신규 개발의 기반이다. 이번 주에 그 전체를 처음 만든 것으로 계산하지 않는다.

| 커밋 | 날짜 | 실제 변경과 의미 |
| --- | --- | --- |
| `3062180` | 10/13 | P1~P6 통합 계획, 상용 준비 감사, 팀 다음 작업·외부 피드백 문서. 우선순위와 미검증 항목을 정리한 단계다. |
| `5fcdbc5` | 10/14 | 강수량·환경 snapshot, 자원 재생 원장, 먹이 소비 종 수와 인구/환경 DTO 확장. |
| `c8fec69` | 10/14 | 이동 표본과 표현 revision 분리, Client 보간 상태, 연결별 예산 계약. |
| `54d5d5b` | 10/14 | M4 생명주기·정책·이주 보강과 SpeciesAI 공통 런타임, 경로/이동/예약/공격 구현. |
| `231f59d` | 10/14 | A~F 수동 검증, 새 레벨 조립, 실제 실행 계약과 빌드 보조 도구. |
| `5c410ae` | 10/14 | SpeciesAI 독립 개발·적용·구현 범위, PPO와의 비교 방법. |
| `f9d3462` | 10/14 | StateTree 3개, 프로필/EntityConfig 3쌍, SmartObject 정의 등 실험 에셋. |
| `64a8cd0` | 10/14 | `/Game/JWJ/Integration_JwJ`와 World Partition 데이터 추가. 배치 추가와 게임 검증은 별개다. |
| `67c860c` | 10/14 | Dry 7개·Grass 7개 발소리 SoundWave 갱신. 청감·공간 음향의 개선 여부는 에셋 diff만으로 판정할 수 없다. |

## 2. 무엇을 위해 어떻게 구현했는가

### 2.1 생존·자원·사망·이주의 공통 실행 경로

**목적:** 동물의 개별 움직임이 실제 Food와 Population 변화로 이어지고, 같은 사망·섭식·이주를 중복 처리하지 않게 한다.

기존 `AEcoCreatureIntegrationSpawner`의 큰 구현을 Spawn/TemplateValidation/Lifecycle/Population/Presentation/Scheduling 등 책임별 파일로 분리했다. 기존 Blueprint 클래스 identity는 유지한다. Box의 `UEcoMassLifecycleSubsystem`과 Creature coordinator는 같은 월드에서 함께 쓰지 않는다.

Mass 작업 뒤 완료 경계에서 다음 순서로 처리한다.

1. 종별 생존 계산 → 사망 후보 → 공통 사망 확정과 예약·Travel·feeding 정리.
2. 사망 receipt → 원인별 집계와 피식 기록 → 확인된 포식자에만 설정된 보상.
3. 살아 있는 인구 확인 → 환경 snapshot → 자원 재생·감쇠·손실·공급.
4. 켜 둔 경우에만 wave 생성 → 실제 birth 반영.
5. 섭식 요청 → Ecology 배분 → ID/시각/지역/생존/중복 검증 → 실제 지급량만 Energy 반영.
6. 실제 도착의 지역 변경 확정 → 새 인구·압력으로 이주 의도 결정.
7. 같은 완료 step의 지역·종 요약을 GameState로 공개.

검증식은 세계 `Alive = Births − Deaths`, 지역×종 `Population = Births − Deaths + MigrationIn − MigrationOut`이다. 지역을 떠나거나 Client에 보이지 않는 개체를 사망으로 계산하지 않는다. Population=0인 종의 row도 누적 사망 기록을 보존한다.

Food 압력 계산에는 전체 개체 수와 실제 지역 먹이를 소비하는 개체 수를 구분하는 계약을 추가했다. 늑대까지 사슴과 같은 지역 식물 소비자로 계산하는 문제를 피하기 위한 구조다. 늑대 생존·포획 영양은 명시적으로 켜는 별도 설정이다.

**분석:** 이번 변화의 큰 가치는 화면의 행동과 생태 회계를 연결한 데 있다. 다만 catch-up은 과거의 물리 이동·충돌을 전부 재현하지 않는다. 직접 Entity를 삭제하는 임의 despawn/저장 복원 시스템까지 완성한 것은 아니다.

근거: [실행 계약](M4_RUNTIME_INTEGRATION_CONTRACT.md), [Lifecycle Source](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp), [Population Source](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePopulation.cpp).

### 2.2 World 날씨 → Ecology 자원 → 행동의 폐루프

**목적:** 외부 날씨·시간이 화면 효과에 머물지 않고 지역 자원과 다음 행동의 입력이 되도록 한다.

`EcoRegionEnvironmentAdapter`가 기존 Weather/Sky Blueprint와 World 입력을 연결한다. 권위 서버의 입력을 자원 완료 경계에서 snapshot하고 GameState 요약으로 Client에 전달한다. 강수량 재생 반응은 기본 꺼짐이다.

```text
초당 재생량 = Rate × lerp(DryMultiplier, WetMultiplier, Rainfall)
실제 공급량 = FoodCapacity까지 남은 양으로 제한한 재생량 × 경과 시간
```

Rate=2, Dry=0.5, Wet=1.5이면 Rainfall=0에서 1 Food/s, 1에서 3 Food/s다. 재생 공급도 자원 원장의 Supplied에 포함한다. 날씨·위험 감쇠를 같은 자원 step에서 중복 적용하지 않는다.

`ApplyRainfall`은 기존 온도·습도를 보존한다. 전체 환경을 바꾸는 `ApplyWeather`와 구분한다. 비복제 배치 Actor의 `HasAuthority` 대신 World NetMode로 실제 서버/Client 권위를 구분하도록 보완했다.

**분석:** V1에 강수량 관측을 새로 추가한 것은 아니다. 비가 Food를 바꾸고 기존 Food 관측이 달라지는 간접 반응이다. 실제 하늘 BP 연결과 Client 렌더는 아직 별도 확인이 필요하다.

근거: [환경 Source](../../Source/AdaptiveEcosystem/Ecology/EcologyEnvironmentSimulation.cpp), [자원 Source](../../Source/AdaptiveEcosystem/Ecology/EcologyResourceSimulation.cpp), [Adapter Source](../../Source/AdaptiveEcosystem/World/EcoRegionEnvironmentAdapter.cpp).

### 2.3 이동 표본과 표현 갱신 분리

**목적:** HP·Energy·행동만 바뀌었는데 이동 보간의 시간축이 바뀌거나, 정지 동물의 상태가 Client에 늦게 반영되는 문제를 줄인다.

| 값 | 의미 |
| --- | --- |
| `SampleSequence` / 서버 표본 실시간 | 실제 이동·identity·reset 표본의 순서와 시각 |
| `VisualRevision` | HP/Energy/life/속도/Activity 등 표현 변경 |
| `MovementDiscontinuityRevision` | teleport/reset으로 보간을 끊어야 하는 사건 |

동일 이동 serial에서도 새 VisualRevision을 받는다. 표현만 수신하면 movement Previous/Current timeline은 바꾸지 않는다. 일반 이동은 두 표본 사이에서 clamp 보간하고, 최초 Add·reset·재진입은 즉시 정렬한다. 과거·중복 표본 거부 경로도 있다.

연결별 Bubble은 여러 Template/종을 합산해 관련 개체·신규 Add를 제한한다. 로컬 표현은 거리·기존 binding 유지 bias로 선택하고, active Actor+hidden pool의 총량을 제한한다. 반납 시 identity·상태를 초기화한다.

**분석:** Dirty 횟수 감소나 예산 코드 추가는 packet 절감·FPS 향상의 실측 증거가 아니다. 현재 admission은 기존 관련 개체를 유지하고 초과 신규 후보를 보류한다. 새로 접근한 중요 개체를 위해 기존 개체를 강제로 교체하는 우선순위 eviction은 후속 범위다. 외삽·다중 표본 jitter buffer도 없다.

근거: [Replicator](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassReplicator.cpp), [Client 표본](../../Source/AdaptiveEcosystem/Mass/EcoMassPresentationFragments.h), [표현·풀](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePresentation.cpp).

### 2.4 PPO 실행 주기와 순수 추론 batch

**목적:** FPS가 바뀌어도 정책의 초당 실행 빈도를 유지하고, 대규모 추론을 분리해 측정할 수 있도록 한다.

- V1 7→64→64→4, 기존 학습 가중치와 개체별 Raw Action을 유지한다.
- 정책 주기를 `8/60초`, 약 7.5회/개체·초로 계산한다. 한 프레임에 한 번 추론하며 긴 frame의 미처리 시간은 debt로 남긴다.
- 죽은 개체·pending death·Client proxy·새 StateTree Brain을 기존 PPO 실행에서 제외한다.
- 피식 EMA 분모는 해당 cell의 살아 있는 전체 prey snapshot을 사용한다.
- 여러 chunk의 due 입력을 모으고, 선택적으로 수치 추론만 worker에서 처리한다. World/UObject 조회와 결과 적용은 Game Thread에 남긴다.
- `eco.Policy.Parallel 1`이어도 한 실행의 due 입력이 64개 이상일 때만 실제 병렬 경로를 선택한다.
- 기본 `eco.Policy.PredationSource 0`은 지역 Ecology 의미다. `1`의 전역 EMA는 명시적인 실험이다.

**분석:** 정책 실행 빈도의 안정화와 행동 결과의 FPS 독립성은 별개다. 포획 순서·물리 이동·초기 결정 위상까지 Python과 같다는 증거는 없다. Golden Vector도 이번 통합 작업에서 실행하지 않았다.

근거: [Policy Processor](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyProcessor.cpp), [수치 batch](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyBatch.cpp), [V1 계약](../RL_Policy/POLICY_CONTRACT_V1.md).

### 2.5 사슴·늑대 SpeciesAI 독립 개발 기반

**목적:** 상대 종 구현이 끝나기 전에도 감각·생활·추격·실패 처리를 단독 개발하고, 기존 PPO와 비교한다.

- `EnabledSpecies=DeerOnly/WolfOnly/Both`로 활성 종의 Config·스폰만 검사한다. 두 번째 생태 clock/coordinator는 만들지 않는다.
- 종별 StateTree는 Highest Utility로 행동을 고른다. 점수는 C++ Utility 함수, 선택은 StateTree, 실제 실행 의도는 종별 Execution이 담당한다.
- 사슴은 배회·먹이 접근·실제 Graze·휴식·무리 복귀·도주·회복과 기존 Social Shelter를 연결한다.
- 늑대는 감각 기억·수색·추격 포기·공격 요청·실패 backoff·성공 cooldown을 사용한다.
- NavMesh full query는 기본 frame당 최대 8개, soft 2ms 예산이다. 한 번의 동기 query를 2ms에서 중단시키는 hard limit은 아니다.
- engine PathFollow/Steering/Avoidance/ApplyForce를 사용하고, 최종 Transform/Velocity는 grounded Movement 하나가 쓴다. 기존 사슴/늑대 writer와 stock height writer는 새 grounded Entity를 제외한다.
- 일반 Graze/Rest SmartObject 예약과 Social Shelter 예약의 owner는 구분한다. 실제 도착·점유·저속·무위협 상태의 Graze 노출 시간만 공통 섭식 요청으로 연결한다.
- 공격 resolver는 fresh sight·현재 거리/LOS·지역·생존·cooldown을 다시 검사한다. 실제 prey 사망의 최종 집계·영양 반영은 기존 coordinator가 담당한다.
- Fixture는 시험 대역이며 실제 prey Death/Population/PredationHistory와 다른 domain이다. Both에서 fixture를 켜는 설정은 거부한다.
- 평온 Brain은 High/Medium/Low에서 주기를 1/2/4배로 조정한다. no-player는 Low이며 이동·생존·자원 clock을 끄지 않는다. 위협·추격·예약·Travel 등은 High로 보호한다.

제공 에셋은 `/Game/Experiments/SpeciesAI`의 `ST/DA/EC_Deer`, `ST/DA/EC_Wolf`, `ST/DA/EC_DeerV1`, `SO_ActivitySlot`이다. 실제 SpeciesId는 `Herbivore`, `Wolf`다.

`EC_DeerV1`은 정책 비교를 위해 기존 이동·섭식 경로를 유지한다. `EC_Deer/EC_Wolf`는 새 NavMesh·슬롯·공격을 포함한 전체 시스템 실험이다. 두 결과를 같은 정책 비교로 섞으면 원인을 분리할 수 없다.

**분석:** 구조와 에셋은 준비됐지만 실제 행동은 아직 미검증이다. 기본 프로필 몸체/속도, 경로 예산, 슬롯 경쟁, Mass StateTree 실행 순서, 지형 충돌은 작은 수부터 검증해야 한다. 512는 현재 논리 상한이며 성능 보장 수치가 아니다.

근거: [Source 책임·실제 제약](SpeciesAI/SOURCE_RESPONSIBILITIES.md), [구현/미검증 범위](SpeciesAI/IMPLEMENTATION_MILESTONES.md), [실제 적용](SpeciesAI/EDITOR_QUICK_START.md).

## 3. 실제 확인된 테스트와 증거의 한계

문서의 기록 외에 로컬 빌드 로그의 `Result: Succeeded`, 에셋 검사 출력, M4 Audit를 확인했다. 표의 실행은 서로 다른 시점의 Source를 사용했으며 모든 결과가 현재 HEAD의 동일 binary에서 나온 것은 아니다.

| 기존 실행 | 확인된 결과 | 그 결과로 보장하지 않는 것 |
| --- | --- | --- |
| 10/14 최종 M4 UBT | `Milestone_Final_20261014_201332.log`: Succeeded | 게임 행동·네트워크 회귀 |
| SpeciesAI UBT | `Saved/SpeciesAI/Build-final.log`: Succeeded | StateTree 실제 게임 동작 |
| SpeciesAI 에셋 재로드 | Deer/Wolf/DeerV1 모두 TreeReady/ProfileValid/ConfigReferenceValid=1, StockHeightAutoRegister=0, 0 errors/0 warnings | PIE·cook·실제 경로·공격 |
| 동물 기준선 | 평면 14개체/90초, Shelter Moving→Occupied 기록, 정상 종료 기록 | 메시·애니메이션 화면 품질 |
| Box 이주 | 300초, ID 1~8 Forest_A→Forest_B 실제 도착 기록 | 동물 NavMesh 이주·기아 검증 |
| Dedicated+순차 Client | 140초 서버, Client 42초 접속 2회, authority Owned=0·표현 전용 수신·reset 기록 | 두 Client 동시 접속·손실 주입·고의 stale packet |
| 정책 스케줄 | 기본 경로 약 7.5회/개체·초, 관측된 fallback 0 | Golden/행동 품질·모든 FPS의 동일 생존 결과 |
| Box 기아 | 16개체 Time115 기아 사망, Time117 정리 | 동물 전체 경로에서 같은 시각에 사망 |
| 동물 이주·회계 | 최종 Alive2=Births14−Deaths12, Actor2+pool12≤64, 실제 지역 도착 기록 | 512개체 성능·장기 평형 |
| 건조/비 | Regeneration 각각 1.000/3.000, 약 7.508/7.495 정책 결정/초 | 날씨가 생존율을 개선한다는 인과 비교 |
| 10/13 후속 template 검사 | Dedicated/Client 역할 검사와 Client LogicalOwned0 기록 | 이후 추가된 SpeciesAI의 다중 Client 통과 |

건조 실행은 20FPS, 비 실행은 60FPS였다. 공급 공식과 스케줄의 근거로만 사용한다. 날씨 효과를 비교할 때는 FPS와 나머지 조건을 동일하게 해야 한다.

초기 `Integration_B_ClientB.log`는 서버가 먼저 종료된 실행이므로 재접속 성공 근거로 쓰지 않는다. 이후 `Integration_Final_ClientA/B.log`의 정상 순차 접속 기록과 구분한다.

## 4. 모든 수동 테스트의 공통 준비

1. UE 5.8 프로젝트를 사용한다. 다른 UBT/dotnet/Editor/Live Coding/MSBuild/ShaderCompileWorker 실행이 끝난 상태에서 빌드한다. 진행 중인 빌드를 중단하거나 겹쳐 시작하지 않는다.
2. 저장소 루트 PowerShell에서 다음 보조 스크립트를 실행한다. 이 스크립트는 직접 UBT `AdaptiveEcosystemEditor Win64 Development`를 실행하며 자동화 suite는 호출하지 않는다.

```powershell
& '.\AdaptiveEcosystem\Tools\Integration\build_integration_milestone.ps1' -Milestone Final
```

3. `AdaptiveEcosystem/AdaptiveEcosystem.uproject`를 열고 먼저 `/Game/Creatures/Integrated/L_EcoCreatureIntegration` 평면 맵을 사용한다. 다음으로 `/Game/Map/LV_Ecosystem_IntegrationTest` 실맵으로 확장한다.
4. 원본 변경 대신 Editor에서 레벨을 복제한다. World Partition 맵은 `.umap`만 파일 복사하지 않는다. 새 `/Game/JWJ/Integration_JwJ`도 실제 배치를 검사한 뒤 사용한다.
5. GameMode=`EcoCreatureIntegrationGameMode`, coordinator=`EcoCreatureIntegrationSpawner` 정확히 하나. 같은 월드에 M3 Box Bootstrap/일반 MassSpawner를 중첩하지 않는다.
6. 기존 PPO 기준선 Config는 `/Game/Creatures/Integrated/DA_EcoDeer`, `DA_EcoWolf`, 표현은 `BP_EcoDeer`, `BP_EcoWolf`, 발소리는 `DA_EcoFootsteps`다. 이름에 DA가 있어도 여기서는 기존 EntityConfig 참조를 따른다.
7. RegionId와 Groups, 인접 지역, 초기 수/지역·세계 cap을 맞춘다. 스폰·FoodPatchPosition은 world-space, Arrival Offset은 Region local-space다. 지면·충돌·금지영역과 로드된 셀을 확인한다.
8. coordinator의 **Validate Editor Setup**을 누르고 Output Log `[Eco Setup] Errors=0`을 확인한다. 이 버튼은 지면·경로의 모든 안전성을 증명하지 않는다.
9. 최초 설정은 Waves=false, Predator Survival=false, 기존 Simulation LOD=false, Food Regeneration Rate=0, Rainfall Affects Regeneration=false다. 다음 값을 설정한다.

```text
eco.UseLearnedPolicy 1
eco.Policy.PredationSource 0
eco.Policy.Parallel 0
eco.Integration.Dump details
eco.M4.Dump details
```

10. 먼저 Standalone으로 확인한다. 이후 Dedicated+Client로 진행한다. 게임 상태를 바꾸는 명령은 서버/Standalone 콘솔에서 실행한다. 아래 `<ID>`, `<RegionId>`는 Dump에서 확인한 실제 값으로 바꾼다.
11. 평면 맵의 RegionId는 Forest_A/B, 실맵은 Forest/Barren/Highland이므로 명령에 맞는 ID를 쓴다. 테스트마다 새 실행으로 시작하고 Config/개체 수/예산 변경 시 PIE를 재시작한다.

## 5. 기존 PPO/M4 경로 A~F 테스트

### A. 시작·기본 이동·Social 인계

1. 평면 맵에서 사슴 2, 늑대 0, Waves=false로 시작한다.
2. `eco.Integration.Dump details`: Ready=1, Births=초기 수, Runtime stopped/Fatal/Assertion 없음.
3. 정상 지면 이동을 보고 이후 소수 늑대를 추가한다. 기존 스폰 좌표를 수량만큼 준비한다.
4. `eco.Shelter.Log 1`, `eco.Social.ActionAudit 1`을 켜고 실제 차폐와 접근 가능한 슬롯이 있는 Shelter에 위협을 준다. 필요하면 Pawn에 `EcoThreatSourceComponent`, Threat Enabled=true, Strength=1을 설정한다.
5. Raw→Social Effective→Request→이동→Feedback과 Reserved→Moving→Occupied→release를 확인한다. 위협 clear는 Threat Enabled=false로 시험한다.

통과: 도착 전에 Occupied가 되지 않고, 실제 도착·해제와 슬롯 재사용이 일치한다. 이주 reconcile 때문에 평온 Resident 속도가 0으로 덮어써지지 않는다. 기존 CLI 기록은 있지만 새 레벨·GUI는 새로 확인한다.

### B. Client 수신·보간·reset·재접속

1. 실맵에서 Dedicated 서버와 Client 하나를 실행한다. PIE의 Play As Client 설정에서 실제 Client 인스턴스 수를 확인한다. 두 관찰자를 비교할 때는 Client 창이 실제로 두 개 떠 있어야 한다.
2. 서버 `eco.M4.TraceSamples 1`, Client `eco.Integration.Dump details`, `eco.M4.Dump details`를 실행한다.
3. 늑대 추적→정지/식사, HP/Energy 변화를 관찰한다. 동일 SampleSequence에서도 VisualRevision·Presentation 수신이 갱신되고 movement timeline은 유지되어야 한다.
4. 서버에서 `eco.M4.Teleport <ID> <X> <Y> <Z>`로 실제 지면 위 작은 오프셋을 준다. Reset 증가와 즉시 정렬을 확인한다.
5. relevance 밖 이탈→재진입, 늦은 접속, 서버를 유지한 재접속을 각각 시험한다.
6. 별도 실행에서 Client 두 개를 다른 거리에 둔다. 또 별도 조건으로 Network Emulation 지연 100ms/손실 1%를 시험한다.

통과: Client LogicalOwned=0, ghost/중복 binding/stale 표현 없음, 정상 이동 보간, reset snap. Rejected=0인 정상 로그는 고의 과거·중복 표본 거부 시험을 대신하지 않는다. 자동 생성된 보간만으로 jitter 품질까지 판정하지 않는다.

### C. 정책 주기·사망 필터·heading

1. 기존 PPO Config, worker/LOD off로 시작한다. 새 StateTree Config로 이 테스트를 대신하지 않는다.
2. `t.MaxFPS 20`, 30, 60을 각각 독립 실행하고 동일 생존 ID의 `Decisions / AliveSeconds`를 비교한다.
3. 약 7.5회/초인지 확인한다. 초기 phase·짧은 종료 구간의 1회 차이는 구분한다. 긴 frame이 생긴 경우 debt가 남고 이후 해소되는지 기록한다.
4. `eco.M4.SetVitals <ID> 0 0`으로 사망시킨다. 다음 생존 step 이후 이동·관측·이웃 집계에서 빠지고 Death가 한 번만 처리되는지 확인한다.
5. `eco.Creature.DrawFacing 1`로 정지→출발·180도 반전에서 실제 속도와 모델 방향을 확인한다.
6. Utility 비교가 필요하면 새 실행에서 `eco.UseLearnedPolicy 0`으로 바꾼다. PredationSource=1 실험도 별도 기록한다.

통과: 빈도·dead 제외·heading 정상. 전체 물리 결과나 Python 파리티는 별도 검증이다. 피식 cell 분모는 Source/관련 계측과 함께 대조한다.

### D1. 섭식·기아·단일 사망

1. 기존 사슴 생존 Drain=1, Energy Per Food=5, Grace=0, Damage=5를 기록한다. 새 프로필 테스트와 혼합하지 않는다.
2. `Debug.Starvation <RegionId>`로 Food를 고갈시킨다. 순수 기아를 보려면 늑대와 공급/재생/wave를 끄고, 이주로 먹이를 찾을 수 없는 조건을 별도 구성한다.
3. `eco.M4.SetVitals <ID> 1 0`으로 Energy 고갈을 만들고 HP 감소·Starvation 사망·예약 해제를 관찰한다.
4. 다른 실행에서 `eco.M4.SetVitals <ID> 0 0`을 사용해 외부 피해 사망과 구분한다. 두 원인 모두 PredationHistory를 올리지 않아야 한다.
5. 살아 있는 개체가 남은 별도 실행에서 `Debug.FoodSupply <RegionId> 100`을 주고 Granted/TotalFood·Food 감소·Energy 증가를 확인한다.

통과: Energy는 실제 지급만 반영한다. 같은 사망이 두 번 집계되지 않는다. Food 전후 차이는 재생/공급/명시 손실/실제 섭식/반올림을 포함한 원장으로 맞춘다. Food가 0이어도 이주하거나 기존 Energy가 남아 있으면 즉시 죽지 않는 것이 가능하다.

### D2. 실제 이주·지역×종 회계·포식자 생존

1. 평면 두 지역의 AdjacentRegionIds와 안전한 도착 지점을 설정한다. 기준선에서 공급과 재생은 끈다.
2. Forest_A 고갈 후 살아 있는 StableAgentId를 기록한다. 의도만 바뀐 상태와 실제 B 도착을 구분한다.
3. GameState Ecology Summary의 완료 step·Species row를 읽고 Births−Deaths+In−Out=Population을 확인한다. 세계 인구에서 이주는 상쇄되어야 한다.
4. 별도 과밀 실행은 Food를 충분히 두고 Comfort Population을 초기 수보다 작게, Population Pressure=true로 설정한다. 지속 문턱·출발 상한을 확인한다.
5. 별도 늑대 생존 실행은 Predator Survival=true, Drain=1, Capture Gain=25를 사용한다. 실제 포식에만 영양 보상하고 먹잇감 없이는 기아가 진행되는지 확인한다.

통과: 동일 ID의 실제 도착, 단일 death/reward, 지역·세계 인구 보존. Box 회귀는 `/Game/JWJ/Jang_lv`에서 별도로 실행하며 동물 coordinator를 추가하지 않는다.

### E. 강수량·자원 공급·다음 행동·Client 하늘

1. 사본 맵에 `EcoRegionEnvironmentAdapter` 또는 파생 BP 하나를 둔다. 대상 RegionIds를 실제 ID로 지정한다.
2. 콘솔 시험 중에는 Apply Authored Weather=false로 둔다. true이면 다음 tick에 콘솔 값을 덮어쓴다.
3. 서버에서 다음을 실행한다.

```text
eco.Environment.Regeneration Forest 2 1 0.5 1.5
eco.Environment.Rain Forest 0
eco.Integration.Dump details
```

4. 새 실행에서 같은 FPS·초기 Food·개체 수·정책·늑대 조건으로 Rain을 1로 바꾼다. 평면 맵이면 Forest 대신 Forest_A를 쓴다.
5. Rain=0/1의 Regeneration 1/3, 원장 Supplied, Food, ObsFood, Raw/SocialForage, 실제 Granted·Population을 같은 완료 step 흐름으로 기록한다. capacity가 꽉 차면 실제 공급은 더 작아진다.
6. BP 연결은 서버 Weather→`ApplyRainfall`, Adapter `OnEnvironmentUpdated`→기존 비/구름 표시, `OnClockUpdated`→기존 해/밝기 표시 순서다. 실제 기존 BP의 함수 이름을 확인해서 연결한다.
7. Client에서는 GameState 요약→표시 이벤트만 소비한다. Client 표시에서 논리 날씨를 다시 결정하지 않는다. PhaseProgress는 하루 전체가 아닌 해당 Day/Night phase의 0..1이다.

통과: 재생/소비가 중복 적용되지 않고 자원→관측→행동→소비/인구→다음 관측이 이어진다. GUI 하늘·날씨·Client 이벤트는 기존 NullRHI 실행으로 확인된 항목이 아니다.

### F1. 연결·Actor 예산과 풀 재사용

1. 기존 실맵 19개체에서 Project Settings→Adaptive Ecosystem→Connection Budget을 사본 조건으로 Relevant=8, Actor=4, Adds=2로 낮추고 다시 시작한다.
2. `eco.M4.Dump details`, `eco.Integration.Dump`로 Bubble Entries·BudgetDeferredAdds·Actors·Pool을 확인한다.
3. 대량 진입, relevance 이탈/재진입, 서로 다른 종이 섞인 경우를 시험한다. 종별로 따로 상한을 적용해 총량이 초과하지 않아야 한다.
4. 풀 반납 뒤 다른 identity를 받을 때 종/HP/Activity/애니메이션·갱신 주기가 이전 개체에서 남지 않는지 확인한다.

통과: 연결의 합산 상한과 active+hidden Actor pool 총량을 지킨다. 신규 후보 보류는 의도된 정책이다. 가까운 신규 개체의 최우선 표시까지 보장하는 정책은 아니다.

### F2. 병렬·원거리 정책 LOD·규모

1. 기본 경로를 통과한 평면 fixture를 64→128→256→512로 늘린다. 지역/세계 cap·안전 스폰 배열·Food도 해당 시험 목적에 맞춘다.
2. 동일 조건에서 `eco.Policy.Parallel 0/1`을 비교한다. `ParallelDecisions>0`으로 실제 경로 선택을 확인한다. 살아 있는 수가 64여도 같은 frame에 due인 입력이 64 미만이면 worker를 사용하지 않을 수 있다.
3. 기존 coordinator Simulation LOD=true, Far Distance=20000cm, Far Multiplier=4를 별도 실행한다. 원거리 평온 Resident의 정책만 느려지고 위협/예약/이주 때 full-rate로 돌아와야 한다.
4. 화면 밖에서도 생존·예약 lease·Food·Population이 진행되는지 확인한다. 기존 정책 LOD와 SpeciesAI High/Medium/Low scheduler는 다른 경로다.
5. 성능 측정 전 상세 log/draw를 끈다. `eco.Integration.LogDetails 0`, `eco.M4.TraceSamples 0`, Print Resource Changes=false로 맞추고 재시작한다.
6. Unreal Insights CPU에서 EcoCreature/EcoPolicy/EcoSenses/EcoReplication 구간, 별도 Network Insights packet trace에서 전송량을 측정한다.

기록: SHA·hardware·FPS·맵·실제 초기 수/생존 수·Client 수·정책/EMA/LOD·p50/p95/p99·hitch·메모리·wire bytes·debt·생성 대기·Actor/pool. 초기 비교안은 워밍업 5분/캡처 15분/수명 반복 30분이다. 실행 전 허용 지연·FPS·메모리 목표를 정하고 실측으로 판정한다.

## 6. 새 SpeciesAI M1~M5 테스트

### 공통: 기존 PPO와 별도 사본 준비

1. 위 공통 레벨 조건을 유지하고 1~8마리로 시작한다. NavMeshBoundsVolume을 배치하고 Navigation을 빌드한다. `P`로 연속된 이동면을 확인한다.
2. 기본 몸체 radius=30cm/height=130cm를 Supported Agents가 지원하는지 확인한다. NavData 없이는 full Config 시작이 거부된다.
3. 기존 표현 BP·오디오를 유지하고 `/Game/Experiments/SpeciesAI`의 Config를 사용한다. Movement/StateTree/SmartObject Trait를 임의로 중복 추가하지 않는다.
4. `Config/DefaultMass.ini`의 stock height writer 비활성 설정을 함께 적용한다. 설정 누락을 가드를 지워 우회하지 않는다.
5. `eco.SpeciesAI.Status`와 `eco.SpeciesAI.Capture`를 사용한다. Capture는 순간 CSV/manifest이며 누적 성능 측정이 아니다. 이 경로에는 기존 PPO Decisions 값만으로 실행 빈도를 판정하지 않는다.

### M1. 반대 종 없이 시작·잘못된 설정 거부

1. DeerOnly, Herbivore Config=EC_Deer, 사슴1, Wolf Config 비움, fixture=false로 설정한다.
2. Validate 후 PIE에서 Status의 Deer1/Wolf0을 확인한다.
3. 종료 후 WolfOnly, Wolf Config=EC_Wolf, 늑대1, Herbivore Config 비움으로 반복한다.
4. 복제 Config에 잘못된 predator 역할/프로필/컴파일 안 된 Tree를 연결해 스폰 전에 거부되는지 확인한다.

통과: 활성 종만으로 시작하며 잘못된 구성은 논리 개체 생성 전에 거부한다. 이 수동 결과는 아직 기록되지 않았다.

### M2. 단일 이동·벽 우회·막힘·경로 예산

1. 평면 NavMesh, 벽, 사슴1로 시작한다. Graze 장소는 없애고 `eco.M4.SetVitals <ID> 1 0.55`로 배회가 선택될 조건을 만든다.
2. 벽 주변 우회·지면 접지·방향을 관찰하고 Capture의 MoveRevision/Failures/BlockedFrames를 기록한다.
3. 경로 통로를 막거나 끊긴 NavMesh 너머에 장소를 둔다. timeout·실패·재시도·새 장소 선택을 확인한다.
4. 여러 마리에서 `eco.SpeciesAI.PathQueries 1`로 낮추고 Pending 대기·aging을 본다. 종료 후 기본 8로 복원한다. soft 시간 예산은 `eco.SpeciesAI.PathMilliseconds 2`다.

통과: 중복 이동·허위 도착·영구 Pending 없음. 벽/Null Area/Resident 지역 경계를 무단 통과하지 않는다. 긴 hitch에서 ClampedSeconds, feeding의 ExposureDropped도 함께 기록한다.

### M3. 실제 Graze·슬롯 경쟁·중단·Shelter

1. DeerOnly/EC_Deer, Food 충분. `EcoSpeciesAIActivitySite`를 지면·NavMesh·FoodPatchPosition 근처에 둔다. RegionId 일치, Kind=Graze, For Predator=false, SmartObject Definition=SO_ActivitySlot.
2. Energy=0.2로 낮추고 접근→실제 도착→Graze를 관찰한다. Food 감소·Granted·Energy 증가를 함께 확인한다.
3. 사슴2/슬롯1로 바꾸어 동시 점유와 이동 중 허위 섭식이 없는지 본다.
4. 접근/섭식 중 site를 삭제하거나 위협 fixture를 켠다. fixture 시험은 Enable Species AI Fixtures=true, Prey=false, Visible=true, Makes Noise=false, Motion Radius=0부터 시작한다.
5. Claims/Releases/Slots를 기록하고 중단·해제를 확인한다. 일반 Rest 장소도 같은 방법으로 Kind=Rest로 시험한다.
6. 별도로 기존 EcoShelterAnchor를 차폐 위치에 두고 실제 도착 후 다음 Social 패스에서 Occupied가 되는지 확인한다. 사망/이주/삭제 시 예약을 정리한다.

통과: 실제 이용 시간만 자원 요청으로 연결한다. 일반 SmartObject와 Social Shelter의 예약 owner가 중복되지 않는다. Food는 site 자체가 아닌 Region Ecology가 소유한다.

### M4a. 늑대 대역 감각·기억·공격

1. WolfOnly/EC_Wolf, Predator Survival=true, 늑대1, Enable Species AI Fixtures=true로 시작한다.
2. Prey=true, Visible=true, Motion Radius=0인 `EcoSpeciesAIFixture`를 앞쪽 감각 범위에 둔다. 늑대 Energy=0.2로 낮춘다.
3. Status의 Hits/FixtureCaptures 증가와 일회 nutrition을 확인한다. 필요하면 포획 뒤 Motion Radius/Period를 바꿔 움직이는 대역을 시험한다.
4. Visible=false, Makes Noise=false로 바꾼다. 숨은 현재 좌표를 계속 따라가지 않고 마지막 cue 조사→포기/휴식으로 전환하는지 확인한다.
5. 뒤쪽 noise-only, 벽 뒤, 도달 불가 후보를 각각 독립 실행한다. hearing-only는 공격에 필요한 fresh sight를 제공하지 않아야 한다.
6. 늑대2가 같은 대역을 공격하도록 해 대역의 한 번 capture당 성공·보상이 1건인지 확인한다.

통과: 기억과 현재 실제 위치가 혼동되지 않고 무한 공격 요청·중복 보상이 없다. fixture 성공은 실제 사슴 Death/Population/PredationHistory를 바꾸지 않는다.

### M4b. 실제 사슴·늑대 통합 포식

1. 새 실행에서 Both, EC_Deer/EC_Wolf, 사슴4/늑대1, fixture=false로 설정한다. 안전 스폰 간격과 각 종 이용 장소를 준비한다.
2. 탐지→도주/추격→공격을 관찰한다. WolfOnly 대역 결과로 이 시험을 대신하지 않는다.
3. 동일 prey ID의 HP=0 후보 뒤 공통 Death receipt가 한 번 발생하는지 확인한다.
4. Population 감소, PredationHistory, 포식자 nutrition, Shelter/일반 슬롯 해제를 대조한다. 보상 확인을 위해 Predator Survival=true를 사용한다.

통과: 새 요청 공격과 기존 자동 근접 포획이 중복되지 않고 한 prey당 하나의 최종 사망·보상이 발생한다. 실제 게임 행동 검증은 대기 상태다.

### M5. no-player·원거리 생태·Client 읽기 전용·규모

1. Dedicated 서버와 Client 두 개를 실행해 서로 다른 거리에서 관찰한다.
2. 각 Client `eco.SpeciesAI.Status`의 UnexpectedLogic=0, 기존 Dump의 LogicalOwned=0을 확인한다.
3. 한 Client를 relevance 밖으로 보낸다. 표현이 사라져도 서버 Food/Energy/Population/기억/lease는 진행되어야 한다. 재진입 시 현재 상태를 받아야 한다.
4. Client가 없는 서버도 실행해 no-viewer Low tier에서 결정만 느려지고 이동·생존 clock은 진행되는지 본다.
5. 위협/추격/공격 cooldown/예약/Travel/매우 낮은 Energy에서 High 보호를 확인한다.
6. 1→32→128→512로 확대하며 Input/Nav/Movement/Attack/engine avoidance를 측정한다. F2의 기록 항목을 함께 남긴다.

통과: Client 논리 없음, server simulation과 relevance 분리, 처리 지연·비용·정확성을 실제 수치로 확인한다. 지금은 수동 결과 미기록이다.

## 7. PPO와 StateTree 비교를 해석하는 방법

| 비교 | 설정 | 고정해야 하는 조건 | 해석 |
| --- | --- | --- | --- |
| 기존 Utility↔PPO | 기존 DA_EcoDeer, eco.UseLearnedPolicy 0/1 | 이동·Social·늑대·초기값 동일 | 기존 정책 내부 비교 |
| PPO↔StateTree V1 | 기존 DA_EcoDeer↔EC_DeerV1 | 기존 늑대·이동·섭식·관측 encoder·EMA 동일 | 정책 선택 방식 비교 |
| 기존↔전체 SpeciesAI | 기존 Config↔EC_Deer/EC_Wolf | 차이가 나는 이동/섭식/늑대 항목을 공개 | 전체 시스템 비교 |

1. 같은 맵·스폰·Stable ID/seed 조건·Food·생존 계수·FPS·실행 길이를 고정한다. waves/재생/pressure/Client·LOD도 기록한다.
2. 정책 비교에서는 새 늑대·새 몸체 속도·NavMesh·슬롯 생활을 동시에 바꾸지 않는다.
3. 시작과 동일 시점의 관측·결정 시각·이동 결과를 기록한다. PPO와 V1 StateTree의 최초 결정 위상은 같다고 검증되지 않았다.
4. Capture CSV에서 ObservationValid=1인 행만 V1 관측으로 해석한다. full 행동/늑대의 미수집 관측을 0값의 실제 V1 관측으로 해석하지 않는다.
5. 생존 시간·섭식량·피식/기아/이주·예약 실패와 CPU/경로 대기·packet 비용을 함께 비교한다. 같은 조건을 반복하고 분포를 본다.
6. 순간 CSV 한 장이나 살아남은 한 개체만으로 정책 우열을 판정하지 않는다. 현재 비교 결과 자체는 아직 없다.

## 8. 신규 맵·발소리 테스트

이번 주 추가 레벨과 오디오의 실제 체감 검증은 별도로 필요하다.

1. `/Game/JWJ/Integration_JwJ`를 열고 누락 에셋, 외부 Actor, World Partition cell, 상시 로딩 논리 Actor를 확인한다. 본 보고서는 이 맵의 내부 배치를 Editor에서 조사하지 않았다.
2. Validate Editor Setup을 실행하고 GameMode/Region/Config/스폰·도착 지면을 확인한다. 기존 다른 맵의 성공 기록을 새 맵 통과로 옮겨 적지 않는다.
3. GUI Standalone에서 사슴·늑대 보행/달리기·회전·정지·피식/사망을 관찰한다. root motion/notify가 논리 위치·HP를 변경하지 않아야 한다.
4. Dry와 Grass 실제 surface에서 각 발소리가 나는지 확인한다. 좌우 발·접지 시점·중복 재생·걷기/달리기 cadence·거리 감쇠를 듣는다.
5. Dedicated+Client에서도 동일 조건을 반복하고 relevance 이탈/Actor 풀 재사용 뒤 유령 발소리·이전 종 오디오가 남지 않는지 본다.

통과: 에셋 로드·시각·오디오가 실제 사용 경로에서 정상이다. 14개 SoundWave 갱신 사실만으로 소리 품질 개선을 단정하지 않는다.

## 9. 현재 평가와 다음 검증 우선순위

1. **우선 M4 기본 회귀:** 현재 HEAD binary로 평면 시작·생존/자원·이주·Dedicated/Client를 다시 확인한다. 과거 실행과 이후 SpeciesAI 변경 사이의 공백을 줄인다.
2. **SpeciesAI 소수 개체 행동:** M1→M2→M3→M4a→M4b 순서로 진행한다. 이동/슬롯이 불안정한 상태에서 대규모나 PPO 우열 평가로 넘어가면 원인을 분리하기 어렵다.
3. **실제 레벨 표시·오디오·환경 BP:** JWJ 맵, Weather/Sky 연결, teleport/reset·재진입을 GUI에서 확인한다.
4. **동시 Client·지연/손실·cook:** 순차 Client와 에셋 재로드가 검증하지 않은 경계를 채운다.
5. **성능·장기·정책 비교:** 실제 worker dispatch, no-player/LOD, 규모별 CPU/packet/메모리, 장기 자원/인구 보존을 측정한 뒤 정책 비교를 진행한다.

현재 확인 가능한 평가는 **M4 소규모 논리 통합의 실행 증거가 있고, SpeciesAI의 코드·설정 에셋 기반이 빌드·재로드를 통과했다**는 것이다. 아직 전체 시스템의 행동 완성·512개체 처리 성능·상용 출하 준비를 선언할 단계는 아니다.

Carcass 자원/섭식 원장, Wolf Pack, stamina/체온/수분, patch별 잔고, ORCA, 비동기 Nav, 집계형 원거리 simulation, 두 대륙 unload/영속 복원, V3/R3 모델 전환은 후속 범위다.

## 10. 기록 양식과 주요 자료

각 시험은 다음 정보를 한 묶음으로 남긴다.

```text
테스트 이름 / 날짜 / commit SHA / binary 빌드 로그
맵 / Config·Profile / 초기 개체·Food / 생존·이주·wave·재생 설정
Standalone 또는 서버·Client 구성 / FPS / hardware / LOD·병렬 모드
조작 순서와 시각 / 관찰한 StableAgentId / 완료 step
기대 결과 / 실제 결과 / 통과·실패·미수행 / 로그·CSV·화면·trace 경로
```

- [M4 구현·실행 이력](M4_IMPLEMENTATION_PROGRESS.md)
- [M4 수동 레벨 설정과 팀 BP 연결](M4_NEW_LEVEL_MANUAL_SETUP.md)
- [M4 실행 계약](M4_RUNTIME_INTEGRATION_CONTRACT.md)
- [SpeciesAI 실제 적용](SpeciesAI/EDITOR_QUICK_START.md)
- [SpeciesAI 마일스톤과 검증 상태](SpeciesAI/IMPLEMENTATION_MILESTONES.md)
- [SpeciesAI 코드 책임·실제 구현 한계](SpeciesAI/SOURCE_RESPONSIBILITIES.md)
- [PPO·StateTree 비교 계획](MASS_STATETREE_PPO_COMPARISON_DEVELOPMENT_PLAN_2026-10-14.md)
- 기존 로그: 프로젝트 `Saved/IntegrationBuilds/`, `Saved/Logs/`, `Saved/SpeciesAI/`. Saved 파일은 로컬 증거이며 Git에 보존된 문서와 구분한다.

이 보고서는 문서만 추가했다. Source·Content·Config를 변경하거나 새 UBT/PIE/자동화 검증을 수행하지 않았다.
