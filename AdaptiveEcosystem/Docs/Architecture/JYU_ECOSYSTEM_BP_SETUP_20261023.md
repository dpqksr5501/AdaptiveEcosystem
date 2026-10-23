# 실제 생태계 BP·배치·실행 — 2026-10-23

실행 맵은 **`/Game/JYU/Maps/LV_JYU_Ecosystem`**이다. 기존 owned 이주 맵의 복사본이며 원본 팀 레벨과 `LV_JYU_HerdMigration`은 저장하지 않았다. 맵을 열고 **Play**하면 저장된 옵션으로 수분·식생이 켜진다. 추가 콘솔 명령이나 수동 BP 연결은 필요 없다. 전체 기획의 완료 여부는 [상태표](ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md), 소유권·자원 계약은 [식생 계약](ECOSYSTEM_VEGETATION_CONTRACT_20261023.md)을 따른다.

**최신 상태는 [life-v1 계약](ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md)과 [전체 상태표](ECOSYSTEM_IMPLEMENTATION_STATUS_20261023.md)를 우선한다.** 아래 최초 구축 시점의209/213개 자동화와9개 habitat·미구현 설명은 당시 이력이다. 맵을 다시 생성하지 않는다.

## life-v1 후속 배치와 사용

담당자 후속 작업은 [레벨 디자인 안내](../Team/ECOSYSTEM_LEVEL_DESIGN_AGENT_GUIDE_20261024.md)와 [날씨 안내](../Team/ECOSYSTEM_WEATHER_AGENT_GUIDE_20261024.md)를 따른다. 현재 상태를 보존해 수정하고 아래 최초 구축 이력의 미완료 설명으로 맵을 재생성하지 않는다.

현재 같은 맵에 `bEnableEcosystemLife=true`, 식생 true를 저장했다. **BP7종·habitat10개·날씨3개**다. 새 `BP_JYU_AuthoredSpring` 하나를 Forest `(33800,28700)`에 배치하고 수면Z `-1084.09448cm`를 지면 조사로 정했다. 최대 수심 약12cm/둑 높이 약82cm의 작은 얕은 물 표현이며 강/수영 backend는 아니다. Field는 shrub에 GrassB, riparian에 GrassC를 사용하며 논리 food 감소가 외형과 Native 시야 차폐를 함께 줄인다. 기존 grass 재질 복사본과 새 water 재질만 사용한다.

`PAL_JYU_EcosystemRuntime`은 동적 soft/string 참조의 비·눈·소리와 식물/물 mesh·material에 AlwaysCook을 명시하는 owned PrimaryAssetLabel이다. **DefaultGame의 PrimaryAssetLabel type scan도 non-editor-only여야 이 규칙이 실제 cook에 적용된다.** 표준 /Game scan·Map 규칙과 다른 label의 Unknown은 유지했다. 원본 SHC 날씨 에셋을 수정하지 않는다. 재현 도구는 `extend_jyu_ecosystem_life.py`, `ensure_ecosystem_runtime_dependencies.py`, 저장 후 재로드 감사와 실제 패키지 smoke다. registry에 이름이 보이는 것만으로 cook을 판정하지 않는다.

Play하면 실제 자연 출생·성장·개체 기억·흔적/사냥·사체 영양·기후/이주가 실행된다. **F**는 실제 근접 공격이며 거리/방향/LOS/1초 cooldown을 서버가 검증한다. `eco.Ecosystem.Save MySlot`, 새 서버에서 `eco.Ecosystem.Load MySlot`은 같은 빌드 복원이다. `eco.Ecosystem.Recover Forest Wolf`는 그 지역 늑대가 실제로0일 때만 최대2 founder를 운영 공급하며 자연 출생과 분리한다. 상세 실패 조건과 재현은 life-v1 문서를 따른다.

체형은 기존 사슴/늑대 ABP·IK를 유지한 uniform growth/유전 scale이다. 실제 mesh에는 Morph Target이 없으므로 새 bone 비율/어린 사슴 전용 리그를 구현했다고 표시하지 않는다. 새 화면·멀티·cook 결과는 [life evidence](Evidence/EcosystemLife_20261023.json)에 기록한다.

## 최초 soil-v1 구축 이력

## 저장한 BP와 실제 배치

에셋 폴더는 `/Game/JYU/Ecosystem`이다. BP는 공통 C++ producer/consumer를 상속해 설정을 제공하며, 개별 풀 Tick이나 별도 food 잔고를 만들지 않는다.

| BP | 맵에서의 사용 | 실제 연결 |
|---|---|---|
| `BP_JYU_VegetationField` | spawner의 `VegetationFieldClass`; 실행 시 지역별 하나씩 생성 | Native 셀 → 서버 표본 DTO → GrassA ISM·양/건조색 |
| `BP_JYU_EcosystemWeather` | 지역별 1개, 총 3개 | 권위 simulation clock → 지역 Rainfall → 수분/재생·GameState → 비 연출 |
| `BP_JYU_GrassHabitat` | 지역별 1개 | drainage .6/shade .1/grass |
| `BP_JYU_MoistSoilHabitat` | 지역별 1개 | drainage .2/shade .35/grass; 물을 임의 공급하지 않음 |
| `BP_JYU_ShrubHabitat` | 지역별 1개 | drainage .6/shade .6/shrub 논리 내성 |
| `BP_JYU_RiparianHabitat` | **미배치 템플릿** | 수원 표면·수문 연결성을 실제 확인한 곳에만 설정 후 배치 |

서식지 BP는 총 **9개**, 날씨 BP는 **3개**를 저장했다. Outliner의 `JYU_Ecosystem_<Region>_<Kind>`와 `JYU_Ecosystem_Weather_<Region>` 라벨로 찾는다. 각 habitat의 Box는 지면 trace에 포함되는 셀에만 작용한다. 복사 맵의 기존 은신처·사슴/늑대·이주 route는 보존한다. Field는 생성 경로가 이미 있으므로 수동으로 중복 배치하지 않는다.

날씨는 180 simulation seconds 주기의 건조→비→건조다. Forest/Barren/Highland 위상차 0/30/60초를 둔다. `RainCycleSeconds`, `DryRainfall`, `WetRainfall`, `RainTransitionFraction`, `RegionIds`를 날씨 BP 인스턴스에서 조절한다. `bApplyAuthoredWeather`와 `bCycleRainfall`을 동시에 켜지 않는다. 이 주기는 명시적으로 만든 날씨 규칙이며 확률 날씨나 장기 자연 균형을 뜻하지 않는다.

`eco.IntegratedV3.WeatherVisuals 0`은 로컬 비/소리만 끄며 권위 강수·수분 계산을 끄지 않는다. `eco.IntegratedV3.WeatherRainDensity 2`는 빗줄기 밀도만 바꾼다. 새 수신 weather 뷰도 이 기존 설정을 따른다. 복사 맵의 옛 `BP_WeatherManager_PlayerFollow` Actor 한 개는 중복 연출을 방지하기 위해 제거했으며 원본 SHC BP/맵은 수정하지 않았다.

기존 초원 재질 그래프를 새 `M_JYU_EcosystemGrass`에 복사하고 `MI_JYU_EcosystemGrass`에서 기존 texture 설정을 보존했다. custom data 수분/스트레스가 녹색→마른색 tint를, food 비율이 패치 폭·높이·숨김을 바꾼다. 기존 MWAM 재질/SHC 에셋은 수정하지 않았다. Shrub/Riparian의 전용 외형은 아직 없으며 같은 grass 표본을 쓴다.

## 열고 확인하기

1. `AdaptiveEcosystem/AdaptiveEcosystem.uproject`를 UE 5.8로 연다.
2. Content Browser에서 `/Game/JYU/Maps/LV_JYU_Ecosystem`을 연 뒤 Play한다. 기존 스폰·이주 HUD·개체 선택 방법을 사용할 수 있다.
3. 강수가 변하면 즉시 food를 생성하지 않고 토양 수분을 적분한다. 이동·섭식으로 같은 셀의 food가 줄고 표본 풀의 크기가 감소한다. 시간이 지나면 지면/배수·그늘·식물 내성에 따라 회복이 달라진다.
4. `CaptureDiagnostics()`는 선택 Field의 실제 food·누적 소비/성장/손실·장부·BP/mesh/material 경로를 JSON으로 돌려준다. 표시되는 풀은 지역당 최대 256개 **실제 셀 표본**이며 전체 땅의 모든 풀을 채운 외형이 아니다.

기본 `SocialControl=0`, Native 단일 이동/대사 writer, 기존 V1/v3 모델·가중치와 기존 맵 opt-in은 유지했다. Client는 수신 표현만 수행한다. 일반 풀은 보호 은신처가 아니며 `ShelterSafe`/`ProtectedRefuges` 기존 계약을 대체하지 않는다.

## 생성·검증 도구와 재현

`Tools/Editor/setup_jyu_ecosystem.py`는 최초 생성 도구다. **대상 맵이 이미 있으면 거절한다.** 수동 작업을 덮어쓰는 재생성 용도로 실행하지 않는다. 기존 owned 에셋 변경은 소유 metadata·현재 인스턴스를 확인하고 필요한 항목만 편집한다. 새 프로세스의 `audit_jyu_ecosystem_assets.py`로 BP 기본값·soft reference·맵 opt-in·3개 날씨/9개 habitat의 저장/재로드를 확인했다.

최종 직접 UBT 로그는 `Saved/IntegrationBuilds/Milestone_Final_20261023_151545.log`다. 전체 자동화는 `Saved/EcosystemBP_20261023/Automation02/index.json`을 따른다. 실제 일반 PIE는 날씨/food/개체를 강제하지 않는 observer로 최초210초, 중복 날씨 제거 후125초(`PIE02`) 실행했다. observer의 플레이어 위협만 꺼서 무인 세계에 가까운 관찰 조건을 만들었다. 일상적인 Play는 이 observer를 실행할 필요가 없다.

125초 PIE/270초 멀티는 `Milestone_B_20261023_145312` 빌드의 실행이다. 그 이후 수신 연출의 OFF/밀도 설정 보존만 보완해 최종 UBT·전체 자동화를 다시 실행했다. 최종 빌드의 `audit_ecosystem_weather_controls.py` 실제 PIE는 저장된 기후에서 비가 시작되기를 기다린 후 OFF→ON/밀도2→OFF를 검사한다. 모델/장부/전송 DTO는 이 마지막 보완에서 바꾸지 않았다. 초기 검증 스크립트가 시작 직후 이미 비가 온다고 가정한 실패는 `WeatherControls_InitialDryTiming.json`에 보존하고, 실제 강수를 기다리는 방식으로 고쳤다.

Dedicated + 두 차례 late join 재현(프로젝트 루트 기준):

```powershell
& ./Tools/Editor/test_vegetation_network.ps1 `
  -Map /Game/JYU/Maps/LV_JYU_Ecosystem -AuthoredWeather `
  -AuditFolder EcosystemBP_20261023 -Duration 210 -ExitAfter 270 -ClientBAt 190
```

모든 build/editor 프로세스가 끝난 상태에서 실행한다. 직접 UBT 빌드 역시 기존 지침대로 엔진의 `UnrealBuildTool.exe`를 쓰고 완료를 기다린다. 새 맵에는 저장된 식생 opt-in이 있으므로 이 검증은 `-EcoVegetation`이나 강수 fixture를 전달하지 않는다. 서버는 정상 타이머로 종료하고 ClientA/B는 각 30초 후 정상 종료한다. 로그·원시 표본은 `Saved/EcosystemBP_20261023`에 있다.

최종 공유 결과는 [BP 검증 JSON](Evidence/EcosystemBP_20261023.json)과 실제 PIE [초기 화면](Evidence/EcosystemBP_PIE_0_20261023.png)·[강수 화면](Evidence/EcosystemBP_PIE_2_20261023.png)이다. 증거 집계는 `Tools/Editor/summarize_ecosystem_bp_evidence.py`를 사용한다. 원시 대용량 개체 표본과 개인 발표 파일은 Git에 추가하지 않는다.

| 최종 확인 | 결과 |
|---|---|
| 직접 UBT + 전체 자동화 | Succeeded, 208 Success + 기존 예상 warning 1, 실패/미실행 0 |
| 125초 PIE/210초 서버 표본 | food·소비·성장·환경 손실과 장부 오차 0 |
| 최종 270초 Dedicated + 두 Client | 모두 정상 종료. Client 논리 개체/Native Step/이주 Subsystem 0, 수신 Field 3개씩 |
| 강제 가뭄 없는 기존 이주 연결 | 210초 표본에서 실제 Barren→Forest 이전 13건. 270초 로그에서 여정 완료 6건; 일부 완료는 구성원 사망을 포함 |
| 이주 뒤 접속 ClientB | 서버에서 Forest로 이전한 stable ID 7개의 Forest 표현 수신 |
| 최종 빌드 연출 제어 PIE | 실제 강수를 기다린 후 OFF→ON/밀도2→OFF 통과. 공개 Niagara/Audio API로 활성·SpawnRate·실제 소리 재생을 확인했고, OFF 중 강수/수분/Native Step 지속 |

연출 제어 검사 과정의 초기 건조 타이밍·Python 보호 진단 멤버 접근 실패는 Saved에 보존했다. 최종 스크립트는 보호 멤버를 노출하거나 우회하지 않고 실제 컴포넌트의 공개 getter를 사용한다. 이는 새 C++ 기능을 바꾼 작업이 아니며 최종 `WeatherControls.json`이 acceptance 결과다.

## 남은 검증과 다음 수정 지점

실제 수원 surface가 현재 Native stage에 확인되지 않아 수원 연결을 꾸며서 켜지 않았다. Riparian BP를 놓기 전에 실제 물 표면 높이·연결성·침수 깊이·지면이 같은 지역 stage에 있는지 확인한다. 이 준비 없이 `ConnectedFreshWater`를 켜면 authoring 사실과 세계가 어긋난다.

장소의 회복 전망/위험 기억·경험/흔적·조건부 자연 출생/유전·체형·전체 저장/복원은 후속 구현이다. 짧은 관찰은 장기 생존/이주 정착을 증명하지 않는다. Python soil-v1 mirror·새 학습·ON-world parity, 서버/Client p95·대역폭, cook/패키징도 미완료다. 새 BP 맵의 생성·PIE/멀티 성공을 전체 구현 완료로 확대하지 않는다.
