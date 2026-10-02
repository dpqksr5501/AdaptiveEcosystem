# 시즌 내보내기 명세: 게임 서버 → 시뮬레이터

- **작성**: sinhyeok04
- **날짜**: 2026-10-02
- **상태**: 초안 2판(검토 반영). 합의 전이므로 값과 이름은 바뀔 수 있다.
- **받는 사람**: 서버 담당. wonkii 님으로 추정한다. 근거는 계획:100과 `D/Architecture/COLLABORATOR_ECOSYSTEM_INTEGRATION_PLAN.md:91`이다.
- **합의할 사람**
  - 조연우 님: 스키마 버전과 명명 규칙, `PredationHistory` 계약, 플레이어 집계 범위
  - World 담당(미정, avaroki 님으로 추정, 계획:101): 날씨 필드
- **관련 문서**: `D/RL_Policy/RL_V2_PLAN.md`(계획서), `D/RL_Policy/POLICY_CONTRACT_V1.md`, `D/Network/MASS_NETWORK_AUTHORITY_CONTRACT.md`, `D/Architecture/ACTIVE_RUNTIME_BOUNDARIES.md`. 학습 절차 문서 `RL_SEASON_RETRAIN_PLAN.md`는 아직 없다(작성 예정).
- **한 줄 요약**: 서버는 시즌 창(최소 600초)이 끝날 때마다 지역 단위 요약값을 담은 JSON 파일 하나를 쓴다. 파이썬은 그 파일로 시뮬레이터 설정을 만든다. 그 설정에서 현재 정책의 성적이 게임 성적과 비슷하게 나오는지 확인한 뒤 이어서 학습한다. 개체 궤적과 플레이어 개인 정보는 보내지 않는다.
- **서버 담당이 먼저 볼 곳**: 8절 P0(지금 할 일), 6.1~6.2절(창과 표본 지점), 7.1절(M3 예시 파일).

---

## 0. 읽는 법

### 0.1 경로 약칭
| 약칭 | 실제 경로 |
|---|---|
| `S/` | `AdaptiveEcosystem/Source/AdaptiveEcosystem/` |
| `P/` | `S/AI/Policy/` |
| `D/` | `AdaptiveEcosystem/Docs/` |
| `H/` | `herbivore_rl/` |
| `G` | `AdaptiveEcosystem/Config/DefaultGame.ini` |
| `E` | `AdaptiveEcosystem/Config/DefaultEngine.ini` |
| 계획:줄 | `D/RL_Policy/RL_V2_PLAN.md`의 줄 |

### 0.2 인용 기준
- 줄 번호는 Branch_Sinhyeok의 HEAD **8a6399e** 기준이다.
- 이 문서를 쓰는 시점에 `E`(3번째 줄 `EditorStartupMap` 한 줄)가 커밋되지 않았다. 이 문서는 `E`의 4·79줄만 인용하고, 그 두 줄은 바뀌지 않았다.
- 같은 시점에 다른 작업이 `H/` 파일(`H/diagnose_v2.py`, `H/env_v2/rollout.py`, `H/train_v2.py` 등)을 고치고 있다. `H/` 인용은 모두 HEAD 8a6399e 기준이다.
- `S/`에서 `AI/Policy/`와 `Debug/EcoPolicyTestSpawner.*`를 뺀 나머지, 그리고 `G`는 origin/main(295ac2f)과 내용이 같다. 그래서 같은 줄 번호를 `@main:`으로 읽어도 된다.
- `P/`와 `Debug/EcoPolicyTestSpawner.*`는 main과 다르다(10-01 결함 수정 4건, 계획:412). main 기준으로 적을 때는 `@main:`을 붙인다.
- 계획서와 `H/`는 다른 작업이 고치는 중일 수 있다. 줄이 밀렸으면 `git show 8a6399e:<경로>`로 읽는다. 계획서의 결정은 결정 번호(#15 등)도 함께 적었다.
- 10-02에 v2.0b(먹이 2층)를 2단계로 미뤘다(계획:520). 이 문서의 "v2.0b" 표기는 그대로 두되 5.0절에 그 뜻을 적었다.

### 0.3 표기
- **(추정)**: 코드로 확인하지 못한 해석이다.
- **(제안)**: 이 문서가 처음 제안하는 값이나 이름이다. 합의 대상이다.
- **확인 필요**: 조사에서 원천을 찾지 못했다. 지어내지 않고 비워 둔다.
- **C++ 호출자 0건**: C++ 코드에서 부르는 곳이 없다는 뜻이다. `BlueprintCallable` 함수는 블루프린트 호출 여부를 따로 확인해야 한다(확인 필요).

### 0.4 "지금 상태" 열의 뜻
상태 열은 **원천 값**의 상태다. 내보내기 코드는 아직 하나도 없으므로 모두 새로 만든다.

| 표기 | 뜻 |
|---|---|
| 있음 | 값이 실제로 채워지고 바뀐다 |
| 있음(M3) | M3 레벨 `Jang_lv`에서만 있다 |
| 있음(L_test) | 정책 테스트 레벨 `L_EcoPolicyTest`에서만 있다 |
| 값 안 채워짐 | 필드는 있지만 값을 바꾸는 활성 코드가 없어 상수로 남는다. 파일에는 null과 `NOT_DRIVEN`으로 쓰고, 잰 값을 `raw_value`에 적는다 |
| 없음 | 언리얼에 원천이 없다 |
| 엔진 API | 저장소 코드는 없고 엔진 함수로 바로 얻는다 |

### 0.5 두 레벨은 서로 겹치지 않는다
이 사실이 명세 전체에 영향을 준다.

| 레벨 | 있는 것 | 없는 것 |
|---|---|---|
| `Jang_lv` (M3) | 지역, `StableAgentId`, 개체 스폰 시각, 월드 시계, 먹이 장부, 이주, 접속 플레이어 수 | 정책, 관측, 포식자, 피식, 사망 |
| `L_EcoPolicyTest` (L_test) | 정책, 포식자, 피식, 더미 먹이·은신처, 접속 플레이어 수(추정, 5.1 `world_epoch` 행) | 지역, `StableAgentId`, 월드 시계, 생태 스텝과 1초 요약, Ecology 먹이 장부 |

- 지금은 한 파일에 모든 값이 들어가지 않는다. 레벨마다 있는 값만 채우고, 없는 값은 null과 이유 코드(6.5절)로 적는다.
- 두 레벨이 합쳐지는 시점은 "M3 Bootstrap이 우리 초식 태그와 커스텀 이동을 거부한다"(계획:415)를 해결하는 일정에 달려 있다(10절 Q4).

---

## 1. 목적과 흐름

### 1.1 목적
"시즌 재학습"의 목표는 지금의 게임 세계와 비슷한 세계를 시뮬레이터에 만들고, 현재 정책을 그 세계에 맞게 이어서 학습시키는 것이다. 시뮬레이터는 개체 경험을 그대로 배우지 않는다. 시뮬레이터에 필요한 것은 세 가지다.

1. **세계를 재현할 요약값**: 맵 구조, 먹이 상태, 위협, 개체군, 시간·날씨
2. **재현이 맞는지 확인할 성적**: 현재 정책이 게임에서 낸 행동과 결과의 통계
3. **메타정보**: 스키마 버전, 시즌 번호, 시간 구간, 설정, 정책 가중치 식별자

### 1.2 흐름
```
[게임 서버 / Standalone]
  시즌 창 동안 집계한다 (게임 스레드에서는 POD 덧셈과 복사만 한다)
  창이 끝나면 JSON 직렬화와 파일 쓰기를 백그라운드에서 한다
        │  Saved/EcoSeason/eco_season_*.json
        ▼  (사람이 옮긴다. Saved/는 git 무시 대상이다)
[파이썬 herbivore_rl]
  ① 받기와 검사 (스키마, 상수, 보존식)       9.1
  ② 창 합치기                                 9.1
  ③ 시뮬레이터 설정 생성 (configs/season_<id>.yaml)   9.2
  ④ 재현 확인: 같은 가중치로 시뮬레이터 성적과 게임 성적 비교   9.3
  ⑤ 통과하면 이어서 학습한다. 실패하면 변환과 보정을 먼저 고친다
  ⑥ export → P/PolicyWeights.h, 골든 벡터
        │
        ▼
[언리얼] 다시 빌드한다 (가중치는 헤더로 컴파일된다. 런타임 로딩은 없다, AGENTS §2.4) → 다음 시즌
```

### 1.3 누가 무엇을 하나
| 단계 | 담당 | 내용 |
|---|---|---|
| Ecology·Mass·World 집계와 파일 쓰기 | 서버 담당 (wonkii 추정) | `meta`, `map.regions`, `food.regions`, `population.regions`, `time_weather`, `threat.region_risk`, `threat.player`를 채우고 파일을 쓴다 |
| 정책 계층 집계 (`P/`) | sinhyeok04 (우리) | `policy_outcome`, `threat.predators`, `threat.predation`, `map.covers`, `map.boundary`, `food.policy_food_provider`, `population.policy_test`, `meta.constants`, `meta.policy`를 집계해 POD로 넘긴다. 계획:98에 따라 `P/`는 우리 몫이다 |
| 스키마·명명 합의 | 조연우 님 | 스키마 버전 관례, `PredationHistory` 감쇠식, 플레이어 집계 범위 |
| 날씨 | World 담당 (미정) | 날씨 상태를 서버에서 갱신한다. 지금은 갱신 주체가 없다(계획:420) |
| 변환, 재현 확인, 학습, export | sinhyeok04 | 9절 |

### 1.4 정책 계층과 서버 내보내기의 경계 (제안)
- 집계 구조체는 서버 담당이 `S/Core/EcoSeasonTypes.h`에 둔다(제안). 스키마의 주인은 서버 쪽이다.
- 정책 쪽 값은 우리가 `P/`의 집계기(제안 이름 `UEcoPolicySeasonStatsSubsystem`)에서 그 구조체에 채운다.
- 내보내기 서브시스템은 `P/` 헤더를 include하지 않는다. 대신 우리가 내보내기 서브시스템에 공급 함수를 등록한다(제안 `RegisterPolicySource(TFunction<bool(FEcoSeasonPolicyStats&)>)`). 창을 닫을 때 내보내기가 이 함수를 불러 값을 받고, 우리 쪽 누적값을 0으로 되돌린다.
- 시계가 없는 레벨(L_test)에서는 창 경계를 우리가 정한다. 그래서 내보내기 서브시스템에 `CloseWindow(EBoundaryKind)` 같은 게임 스레드 호출 지점이 필요하다(제안).

---

## 2. 보내지 않는 것과 원칙

### 2.1 보내지 않는 것
| 보내지 않는 것 | 이유 |
|---|---|
| 개체별 매 프레임 궤적, 개체별 관측·행동 기록 | 시뮬레이터는 개체 경험을 배우지 않는다. 필요한 것은 분포와 집계뿐이다 |
| `StableAgentId` 목록 | `StableAgentId`는 장기 논리 ID라서 저장해도 계약 위반은 아니다(`D/Network/MASS_NETWORK_AUTHORITY_CONTRACT.md:67`, AGENTS §2.8). 그래도 시뮬레이터가 개체를 따라가지 않으므로 쓸 곳이 없고 파일만 커진다. 서버 안에서 수명 같은 집계의 키로만 쓴다 |
| `FMassEntityHandle`, Region·Species Runtime Index | 저장·네트워크 식별자로 쓰지 않는 값이다(`D/Network/MASS_NETWORK_AUTHORITY_CONTRACT.md:69-70`, `D/Architecture/ACTIVE_RUNTIME_BOUNDARIES.md:46`) |
| `FMassNetworkID` | 서버·클라이언트 프록시를 잇는 전송용 ID다(`D/Network/MASS_NETWORK_AUTHORITY_CONTRACT.md:68`). 시뮬레이터에는 의미가 없다 |
| 플레이어 ID, 이름, 계정, IP, 플레이어별로 나눈 통계, 플레이어 궤적 | 개인 정보다. 플레이어 값은 전체 합계와 분포로만 보낸다. 접속자가 적은 창에서는 6.7절 규칙으로 분포를 지운다. M4도 "플레이어별 기억"을 범위에서 뺐다(`D/Roadmap/M4/M4_REPRESENTATION_INTERACTION.md:30`) |
| 클라이언트 쪽 값 | 클라이언트는 이 파일을 쓰지 않는다. 생태 상태의 권위는 서버에 있다(AGENTS §2.2) |
| 보상, G_γ, 번식 수 | 게임에 없는 값이다. 파이썬에서만 쓴다 |
| 레거시 Trait Evolution 데이터 | 신규 경로와 분리한다(AGENTS §2.9) |

### 2.2 원칙
1. **서버(권위) 전용이다.**
   - 내보내기 서브시스템의 `ShouldCreateSubsystem`은 `IsGameWorld() && GetNetMode() != NM_Client`다. 관례는 `S/Ecology/EcologySimulationSubsystem.cpp:11-26`, `S/Mass/EcoMassLifecycleSubsystem.cpp:22-26`이다.
   - Subsystem은 복제 통로가 아니다(AGENTS §2.6). 파일만 쓴다.
2. **게임 스레드를 막지 않는다.**
   - 게임 스레드에서는 POD 집계값만 더하고 복사한다.
   - 직렬화와 파일 쓰기는 백그라운드 작업에서 한다. 저장소에 있는 패턴은 `S/Evolution/DummyEvolutionDecisionProvider.cpp:98-108`의 `AsyncTask(ENamedThreads::AnyBackgroundThreadNormalTask, …)`다. 레거시 코드이므로 의존하지 않고 패턴만 참고한다.
   - Mass가 처리 중이면(`Manager.IsProcessing()`) 조회하지 않는다. 관례는 `S/Mass/EcoMassLifecycleSubsystem.cpp:264, 293`이다.
   - 생태 읽기 API `GetRegionState`는 게임 스레드 전용이다(`S/Ecology/EcologySimulationSubsystem.cpp:121-135`).
3. **집계만 보낸다.** 지역 단위 시간 계열(`series`, 5.8절)도 지역 합계라서 허용한다. 단 플레이어 계열은 6.7절을 따른다.
4. **쓰기 전용 요약 파일이다.**
   - 게임은 이 파일을 다시 읽어 상태를 복원하지 않는다. 세션 간 영속은 범위 밖이다(계획:93, `D/Roadmap/README.md:48`).
   - 복원이 필요해지면 버전 있는 별도 계약을 정한다(`D/Roadmap/M3/MIGRATION_AWARE_SPAWN_PLAN.md:65`).
5. **읽기만 한다.** 내보내기는 생태 상태를 바꾸지 않는다. 범용 덮어쓰기 API는 금지다(`D/Architecture/ACTIVE_RUNTIME_BOUNDARIES.md:52`).

---

## 3. 파일 형식

| 항목 | 규칙 |
|---|---|
| 형식 | JSON 객체 하나. 최상위 키는 `meta`, `map`, `food`, `threat`, `population`, `time_weather`, `policy_outcome`, `series`(선택), `missing` |
| 키 이름 | 이 문서의 snake_case를 그대로 쓴다(제안). `FJsonObjectConverter`는 키 첫 글자를 소문자로 바꾸고 `ID`를 `Id`로 바꾼다(추정, 엔진 동작). 그래서 `FJsonObject`와 `TJsonWriter`로 키를 직접 쓰기를 권한다(Q7) |
| 인코딩 | UTF-8, BOM 없음. `FFileHelper::SaveStringToFile(…, EEncodingOptions::ForceUTF8WithoutBOM)`을 쓴다. 기본값 AutoDetect는 비ASCII 문자가 있으면 UTF-16으로 쓴다(엔진 동작). 줄바꿈 종류는 파서에 상관없다. 압축 출력(`TCondensedJsonPrintPolicy`)을 권한다 |
| 숫자 | JSON 숫자로 쓴다. NaN과 Inf는 금지하고 null과 이유 코드로 바꾼다. 쓰기 전에 `FMath::IsFinite`로 검사한다. int64 값(StepId, CycleId)은 2^53보다 작으므로 숫자로 써도 된다 |
| 스키마 버전 | `meta.season_export_schema_version`(int)이고 1부터 시작한다. 0은 "필드 없는 옛 파일"이다. 버전이 다르면 파이썬이 읽기를 거부하고 이전 형식으로 변환하지 않는다. 관례는 `P/EcoRegionPredationSubsystem.h:34-36`이다. 정책 스키마(`PolicySchemaVersion`, `P/EcoPolicyContracts.h:15`)와는 따로 둔다 |
| 위치 | `FPaths::ProjectSavedDir()/EcoSeason/`. 에디터에서는 `AdaptiveEcosystem/Saved/EcoSeason/`이다. 패키지 빌드에서는 사용자 폴더로 바뀔 수 있다(추정). 쓸 때 절대 경로를 로그로 남긴다 |
| 이름 | `eco_season_s{season_id:03}_{level_name}_{session8}_w{window_index:02}.json`(제안). `session8`은 `meta.export_session_id`의 앞 8자다. 세션마다 새 GUID라서 L_test처럼 `match_instance_id`가 없거나 같은 시즌에 세션을 여러 번 돌려도 이름이 겹치지 않는다. 예: `eco_season_s003_Jang_lv_5B1E0C2D_w00.json` |
| 쓰기 절차 | ① 게임 스레드에서 집계 구조체를 복사한다 ② 백그라운드에서 직렬화해 같은 폴더의 `.tmp`에 쓴다 ③ `IFileManager::Move(목표, 임시, bReplace=false)`로 이름을 바꾼다. 같은 이름이 있으면 덮어쓰지 않고 Warning을 남긴다 ④ `[Eco Season Export] <절대 경로> bytes=<n>` 로그를 남긴다. 실패해도 Warning 로그만 남기고 게임은 계속 돈다 |
| 언제 쓰나 | 시즌 창이 끝날 때 쓴다(6.1절). M3 기본은 "창이 시작되고 `SeasonMinSeconds`(제안 600초)가 지난 뒤 처음 오는 낮 시작"이다. 그 밖에 시계 없는 레벨용 규칙, 콘솔 명령, 시스템 실패가 있다 |
| 시즌과 창 | 시즌(`season_id`)은 운영자가 정한 기간이다. 한 세션은 창을 여러 개 낼 수 있다(`window_index`). 한 시즌은 여러 세션의 파일 묶음이다. 파이썬은 9.1절 규칙으로 합친다 |
| 전달 | `Saved/`는 git 무시 대상이다(`.gitignore:60-61`). 그래서 사람이 파일을 옮긴다(Q14) |

**크기 예상 (추정)**
| 내용 | 크기 |
|---|---|
| 지역 2개, 히스토그램, 메타 | 10~30 KB |
| `series` (600초 창, 10초 간격 60행 × 지역 2개 × 계열 6개) | 약 10 KB 추가 |
| 선택 블록 `food.grid` (셀 400 cm) | 지역 상자 30 m × 30 m: 8×8셀로 무시할 정도다. 100 m × 100 m(기본 반폭 5000): 25×25셀 × 배열 5개로 약 25 KB. 300 m 맵 전체: 75×75셀로 약 250 KB |

어느 경우든 1 MB보다 작다.

---

## 4. 좌표·단위·시간 규약

### 4.1 파일 안의 값 (서버가 쓰는 단위)
| 양 | 단위 | 비고 |
|---|---|---|
| 길이·좌표 | cm, 언리얼 월드 좌표, Z가 위, 원점은 레벨 원점 | 정책 경로는 XY만 쓴다(`P/EcoBehaviorProcessors.cpp:659-667`) |
| 속력 | cm/s | 수평(XY) 성분 |
| 시간 | 초(double) | M3는 서버 시계 0초가 시작이다(`S/Core/EcoTimeTypes.h:29`). L_test는 정책 스텝 시계다(6.1). 실제 시각은 `meta.written_utc`에만 쓴다 |
| 각도 | deg | |
| 먹이 | 무차원 먹이량 | 1회 섭식 Amount는 1.0이다(`G:11`). 지역 기본값은 1000/2000이다(`S/World/EcologyRegion.h:39, 41`) |
| 비율 | [0, 1] | |

**서버는 시뮬레이터 단위로 바꾸지 않는다. 변환은 모두 파이썬 변환기가 한다(제안).**

### 4.2 파이썬 변환 (참고. 파이썬이 한다)
| 양 | 식 | 근거 |
|---|---|---|
| 길이 | 1 u = 200 cm | `H/configs/default.yaml:86`, `P/EcoBehaviorConfig.h:17` |
| 시간 | 1 스텝 = 8/60 s = 0.1333 s. 스텝 = 초 ÷ 0.1333 | `H/configs/default.yaml:87`, `P/EcoBehaviorConfig.h:18, 31` |
| 속력 | u/스텝 = (cm/s) ÷ 1500. 900 cm/s = 0.6 u/스텝 | `P/EcoBehaviorConfig.h:20`, `H/configs/default.yaml:9` |
| 반감기 | h 스텝 = t½ ÷ 0.1333. ρ = 1 − 2^(−1/h) | `H/env_v2/world.py:211, 220` |
| 이완율 | 간격 dt로 잰 r_dt를 스텝 단위로 바꾼다: r = 1 − (1 − r_dt)^(0.1333/dt) | `H/env_v2/world.py:588-593` |
| 좌표와 맵 모양 | 시뮬레이터는 정방형 [0, size]²만 받는다. 대응 규칙은 9.2.4절에 둔다 | `H/env_v2/world.py:146, 430, 529-532` |

### 4.3 지역·종 ID
- `region_id`는 `AEcologyRegion::RegionId`(FName, `S/World/EcologyRegion.h:31`)의 문자열 그대로 쓴다. 중복은 초기화 실패로 처리된다(`S/Mass/EcoMassLifecycleSubsystem.cpp:94-101`).
- 지역 배열은 `FNameLexicalLess` 순서다(`S/Mass/EcoMassLifecycleSubsystem.cpp:138-140`). 런타임 인덱스는 쓰지 않는다.
- 어느 지역에도 속하지 않는 위치는 `"_unassigned"`다(제안, 6.4절).
- 초식 종은 `FEcoIdentityFragment::SpeciesId`(`S/Mass/EcoMassFragments.h:33`)다. Bootstrap 기본값은 `"Species.Default"`다(`S/Mass/EcoMassNetworkBootstrap.h:53`).
- L_test 포식자에는 SpeciesId가 없다(`FEcoPredatorTag`, `P/EcoBehaviorFragments.h:32-35`). 고정 라벨 `"Predator.TestMelee"`를 쓴다(제안).
- 위상 문자열은 `"day"`, `"night"` 둘뿐이다. 시계가 Dusk와 Dawn을 내지 않는다(`S/World/EcoWorldClockSubsystem.cpp:16-21, 25-31`).

---

## 5. 필드 명세

### 5.0 구조와 공통 규칙
```
meta{…, window{…}, systems{…}, policy{…}, constants{…}, runtime_settings{…}}
map{coordinate_system, bounds_kind, bounds, boundary, regions[], covers_source, covers[], shelters[]?, water, obstacles}
food{regions[], grid?, grid_update_interval_s, present_area_frac, policy_food_provider}
threat{predators{kinds[], ranged_frac, by_region}, predation{…}, region_risk[], player{…}}
population{regions[], migration_matrix[], migration_by_cause?, by_species?, policy_test{…}}
time_weather{clock_running, …, weather{regions[]}, environment?}
policy_outcome{…}   series?{…}   missing{경로: {reason, …}}
```

**필수와 선택**
| 표기 | 뜻 |
|---|---|
| 필수 | 키가 반드시 있어야 한다 |
| 필수(null 허용) | 값이 없으면 null을 쓰고 `missing`에 이유를 적는다 |
| 필수(vX부터) | 그 버전 학습이 시작되기 전에 값이 있어야 한다. 그 전에는 null과 `DEFERRED` 또는 다른 이유 코드를 쓴다 |
| 선택 | 키를 생략해도 된다. 키를 쓰고 값이 null이면 `missing`에 적는다 |

**"버전" 열**
| 표기 | 뜻 |
|---|---|
| v2.0 | 지금 학습 분포(무작위화 스칼라 6개)를 정하거나 재현을 확인하는 데 쓴다 |
| v2.0b | 먹이 2층. **10-02에 2단계(v2.3 시점)로 미뤘다**(계획:520). 이 표기 필드는 v2.3 착수 전에 있으면 된다. M3 먹이 장부 값은 지금도 기록으로 받는다 |
| v2.1 | 에너지 |
| v2.3 | 지역, 기억, 플레이어형 위협(#15, 계획:538) |
| v2.4 | 낮밤 |
| v2.5a | 지역 환경 |
| v2.5b | 이주 |
| v2.6 | 비 |
| v2.8 | 물 |
| R1 | 경계와 장애물 |

**요약 표기**
- `{start, end, mean, min, max}`는 6.2절의 시간 가중 요약이다.

### 5.1 meta

| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `meta.season_export_schema_version` | int | — | 이 명세의 버전. 1부터 | 신설 상수(제안). 관례 `P/EcoRegionPredationSubsystem.h:34-36` | 없음 | 로더가 검사하고, 다르면 거부한다 | v2.0 | 필수 |
| `meta.season_id` | int | — | 운영자가 정한 시즌 번호. 0은 미지정 | 신설 설정 `UEcoRuntimeSettings.SeasonId`(제안). 명령줄 `-EcoSeasonId=`로 덮기(제안, Q3). `S/`에 "Season"은 0건이다 | 없음 | 출력 폴더, 창 합치기 | v2.0 | 필수 |
| `meta.export_session_id` | string (GUID) | — | 내보내기 서브시스템이 `Initialize`에서 만든 세션 키 | `FGuid::NewGuid()` | 엔진 API | 파일 이름, 같은 세션의 창 묶기 | v2.0 | 필수 |
| `meta.window_index` | int | — | 세션 안 창 번호. 0부터 | 신설 | 없음 | 창 합치기(9.1) | v2.0 | 필수 |
| `meta.world_epoch` | int32 | — | 매치마다 무작위 해시. 시즌 번호로 쓰지 않는다 | `AEcoGameState::GetWorldEpoch`(`S/Network/EcoGameState.h:50`). 채우는 곳 `S/AdaptiveEcosystemGameMode.cpp:24, 37` | 있음(M3). L_test도 있음(추정): 레벨에 GameMode 덮어쓰기가 없어 `E:4`의 기본 GameMode를 쓰고, 그 부모가 `E:79`의 리다이렉트로 `AAdaptiveEcosystemGameMode`가 되며, 이 GameMode는 `AEcoGameState`를 쓴다(`S/AdaptiveEcosystemGameMode.cpp:16`). PIE에서 `GetGameState<AEcoGameState>()`로 확인한다(Q24) | 기록 | v2.0 | 필수(null 허용) |
| `meta.match_instance_id` | string (GUID) | — | 같은 매치 판별 | `S/Network/EcoGameState.cpp:35`, `.h:47` | 위와 같다 | 기록 | v2.0 | 필수(null 허용) |
| `meta.level_name` | string | — | 맵 이름. PIE 접두사를 뗀다 | `UWorld::RemovePIEPrefix(World->GetMapName())`. `GetMapName()`만 쓰면 PIE에서 `UEDPIE_0_` 접두사가 붙는다(엔진 동작) | 엔진 API | M3인지 L_test인지 판별, 창 합치기 키 | v2.0 | 필수 |
| `meta.map_package_name` | string | — | 원래 패키지 이름 | `World->GetOutermost()->GetName()` | 엔진 API | 기록 | v2.0 | 선택 |
| `meta.net_mode` | string | — | `"standalone"` / `"listen_server"` / `"dedicated_server"` | `GetNetMode()` | 엔진 API | 기록 | v2.0 | 필수 |
| `meta.written_utc` | string (ISO 8601) | UTC | 파일을 쓴 실제 시각. 기록에만 쓴다 | `FDateTime::UtcNow()` | 엔진 API | 같은 시즌 안 순서 | v2.0 | 필수 |
| `meta.engine_version` | string | — | | `FEngineVersion::Current()` | 엔진 API | 기록 | v2.0 | 선택 |
| `meta.build_id` | string | — | 서버 빌드 식별자 | 확인 필요. 런타임 빌드 식별자 경로를 찾지 못했다(Q13) | 없음 | 기록 | v2.0 | 선택 |
| `meta.window.boundary_kind` | string | — | `"day_start"` / `"elapsed_seconds"` / `"console"` / `"system_failed"` (6.1) | 신설 | 없음 | 창 해석 | v2.0 | 필수 |
| `meta.window.complete` | bool | — | 창이 `SeasonMinSeconds`를 채웠고 시스템 실패가 없었는지 | 신설 | 없음 | 짧은 창 거르기 | v2.0 | 필수 |
| `meta.window.time_source` | string | — | `"world_clock"` / `"policy_step_clock"` | 신설 | 없음 | 시간 해석 | v2.0 | 필수 |
| `meta.window.start_server_time_s`, `end_server_time_s` | double | s | 창은 [시작, 끝) 구간이다(6.1) | M3: 경계 생태 스텝의 `Time.ServerTimeSeconds`(`S/Core/EcoTimeTypes.h:29`). L_test: 정책 스텝 경계 수 × `StepSeconds`(6.1) | 있음(M3). L_test는 정책 스텝 시계로 대신한다 | 초를 스텝으로 바꾼다 | v2.0 | 필수 |
| `meta.window.duration_s` | double | s | end − start | 파생 | — | 비율의 분모, 창 합치기 가중치 | v2.0 | 필수 |
| `meta.window.start_step_id`, `end_step_id` | int64 | 생태 스텝 | [start, end). `end_step_id`는 다음 창의 첫 스텝이다 | `UEcoMassLifecycleSubsystem::StepId`(`S/Mass/EcoMassLifecycleSubsystem.h:42`) | 있음(M3) | 기록 | v2.0 | 필수(null 허용) |
| `meta.window.start_cycle_id`, `end_cycle_id` | int64 | 일 | 창 시작 스텝과 경계 스텝의 `CycleId`. 경계 규칙(6.1)이 쓴다 | `FEcoDayCycleState.CycleId`(`S/Core/EcoTimeTypes.h:13`) | 있음(M3, 시계가 돌 때) | 창 안의 일 수 | v2.0 | 필수(null 허용) |
| `meta.window.ecology_steps` | int | 회 | 창 안 생태 스텝 수 = end_step_id − start_step_id | 신설 계수기 | 없음 | 표본 부족 판정 | v2.0 | 필수(null 허용) |
| `meta.window.summary_samples` | int | 회 | 창 안 (b) 표본 수. M3 전용 | 신설 계수기 | 없음 | 표본 부족 판정 | v2.0 | 필수(null 허용) |
| `meta.window.policy_step_boundaries` | int | 회 | 창 안 (c) 표본 수. 정책이 도는 레벨 전용 | 신설 계수기(우리) | 없음 | 시간 해석, 표본 부족 판정 | v2.0 | 필수(null 허용) |
| `meta.window.policy_multi_step_frames` | int | 프레임 | 한 프레임에 정책 스텝 경계가 2번 이상 지나간 프레임 수(`P/EcoBehaviorProcessors.cpp:541-546`의 `Steps > 1`) | 신설 계수기(우리) | 없음 | 결정 누락과 EMA 분모 0 스텝의 규모 판단(5.7) | v2.0 | 필수(null 허용) |
| `meta.systems.*` | bool | — | 이 창에서 실제로 돈 시스템. 정의는 아래 표 | 아래 표 | 신설 | null 해석, 재현 가능 여부 판정 | v2.0 | 필수 |
| `meta.policy.policy_schema_version` | int | — | V1이면 1 | `P/EcoPolicyContracts.h:15` | 있음 | 계약 일치 확인 | v2.0 | 필수 |
| `meta.policy.controller` | string | — | `"learned"` / `"utility"` / `"mixed"` / `"none"`. (d) 결정 사건마다 CVar 값을 센다. 창 안에서 섞이면 `"mixed"` | CVar `eco.UseLearnedPolicy`(`P/EcoBehaviorProcessors.cpp:37-41, 312`). 실행 중 콘솔로 바꿀 수 있다(`S/Debug/EcoPolicyTestSpawner.h:20`) | 있음(L_test) | 재현 확인에 쓸 정책 선택 | v2.0 | 필수 |
| `meta.policy.learned_frac` | float | [0,1] | 학습 정책으로 낸 결정 사건의 비율 | 위와 같다 | 있음(L_test) | `"mixed"` 해석 | v2.0 | 필수(null 허용) |
| `meta.policy.weights_id` | string | — | 게임에 들어간 가중치의 식별자. `"crc32:XXXXXXXX"`(제안) | 지금은 없다. `P/PolicyWeights.h:6`의 생성 시각과 원본 경로는 주석뿐이다. 제안: 정책 계층이 시작할 때 `W0, B0, W1, B1, W2, B2`(`P/PolicyWeights.h:12-643`)의 float32 바이트를 이 순서로 CRC32 한다. 파이썬도 내보낸 배열로 같은 값을 계산한다. 생성기를 바꾸지 않으므로 헤더 바이트 일치 시험(`H/tests/test_export.py:209-218`)에 영향이 없다. 담당 우리 | 없음 | 재현 확인에 같은 가중치를 쓰는지 확인 | v2.0 | 필수(null 허용) |
| `meta.policy.predation_check_cadence` | string | — | `"per_frame"` / `"per_policy_step"` | 지금은 프레임마다 판정한다(`D/RL_Policy/UNREAL_POLICY_INTEGRATION.md:183`, 계획:424) | 있음(상수로 적는다) | 피식률 비교 해석 | v2.0 | 필수 |
| `meta.constants.*` | number | 아래 | 생성 헤더의 상수 22개 전부(아래 목록) | `P/EcoBehaviorConfig.h:17-38`. 담당 우리(정책 POD에 넣는다) | 있음 | `H/configs/default.yaml`과 단위 변환 뒤 같아야 한다. 다르면 거부한다(9.1) | v2.0 | 필수 |
| `meta.runtime_settings.{day_duration_s, night_duration_s}` | double | s | 설정값 | `S/Core/EcoRuntimeSettings.h:45-48`(기본 60/60), `G:7-8`(10/10) | 있음 | 5.6과 대조 | v2.4 | 필수 |
| `meta.runtime_settings.feeding{enabled, first_delay_s, interval_s, amount}` | | s, 먹이량 | | `G:11`, 구조체 `S/Core/EcoResourceTypes.h:8-26` | 있음 | 섭식 시간표 해석 | v2.0b | 필수 |
| `meta.runtime_settings.migration{enabled, decision_interval_s, speed_cm_s, arrival_radius_cm, arrival_spread_cm, food_epsilon}` | | s, cm/s, cm, 먹이량 | `food_epsilon`은 절대 먹이량이다(코드 확인: `S/Mass/EcoMassMigration.cpp:77`의 `Food > Settings.FoodEpsilon`) | `G:10`, `S/Core/EcoMigrationTypes.h:14-40` | 있음 | v2.5b 안전망 ε(비율)로 바꿀 때 `cap0_total`로 나눈다 | v2.5b | 필수 |
| `meta.runtime_settings.{day_food_event, night_food_event}{enabled, region_id, phase_fraction, food_loss}` | | 먹이량 | | `G:9, 12`, `S/Core/EcoResourceTypes.h:29-47` | 있음(밤 이벤트 켜짐) | 학습 분포 밖이라 경고한다(계획:437) | v2.0b | 필수 |
| `meta.runtime_settings.{spawn_waves_enabled, global_population_limit, required_region_count, legacy_evolution_enabled}` | bool, int | | | `G:13`, `S/Core/EcoRuntimeSettings.h:56, 58`, `G:6` | 있음 | 기록 | v2.0 | 필수 |
| `meta.runtime_settings.spawn_schedule[]{region_id, species_id, initial_agent_count, day_interval_s, day_count, night_interval_s, night_count, region_population_limit}` | | s, 마리 | Bootstrap별 설정 | `S/Core/EcoSpawnTypes.h:7-27`, `S/Mass/EcoMassNetworkBootstrap.h:47, 53, 62`. Jang_lv의 실제 값은 레벨 에셋에만 있다(확인 필요) | 있음(M3) | v2.5a 리스폰 비교 | v2.5a | 선택 |
| `meta.region_assignment` | string | — | 위치 사건을 지역에 귀속하는 규칙. 지금은 `"position_in_bounds"`(6.4) | 신설 | 없음 | 지역별 통계 해석 | v2.3 | 필수 |
| `meta.notes` | string[] | — | 운영 메모 | — | — | 기록 | — | 선택 |

**`meta.constants` 목록** (모두 `P/EcoBehaviorConfig.h`의 이름을 snake_case로 바꾼 것)

`grid_unit_cm` 200, `policy_interval` 8, `see_radius_cm` 4000, `herb_speed_cm_s` 900, `max_energy` 1, `obs_pred_count_norm` 8, `obs_kin_count_norm` 20, `obs_cover_norm_cm` 4000, `fov_deg` 120, `sep_weight` 1.35, `sep_radius_cm` 1000, `flee_weight` 3, `predation_ema_decay` 0.95, `predation_ema_gain` 10, `step_seconds` 0.1333333, `pred_view_radius_cm` 2800, `pred_fov_deg` 150, `pred_catch_radius_cm` 200, `pred_eat_cooldown_s` 0.6666667, `pred_wander_turn_rad` 0.15, `cover_hide_mult` 2.5, `init_energy_frac` 0.5.

**`meta.systems` 정의** (관측된 활동으로 정한다. "서브시스템이 있다"로 정하지 않는다)
| 플래그 | 참이 되는 조건 | 이유 |
|---|---|---|
| `m3_population` | 창을 닫을 때 `IsPopulationReady()`(`S/Mass/EcoMassLifecycleSubsystem.h:23`)이고 `ecology_steps > 0` | |
| `world_clock` | `UEcoWorldClockSubsystem::IsClockRunning()` | |
| `policy_inference` | `policy_outcome.agent_policy_steps > 0` | 더미 Provider·Registry·피식 서브시스템은 생성 가드가 없어 모든 월드에 생긴다(`P/EcoWorldProviders.h:75-80, 146-165`, `P/EcoRegionPredationSubsystem.h:42-48`). 있다는 것만으로는 판정할 수 없다 |
| `predators` | (c) 표본의 포식자 수 최댓값 > 0 | 위와 같다 |
| `predation_report` | `policy_step_boundaries > 0` (피식 처리기가 스텝 경계를 닫았다) | 위와 같다 |
| `player_report`, `food_regeneration`, `food_grid`, `weather_server`, `water`, `energy_metabolism`, `death_lifecycle` | 지금은 코드 상수 false. 해당 기능이 들어갈 때 그 기능의 켜짐 조건으로 바꾼다 | 확인할 서브시스템 자체가 없다 |

### 5.2 map

| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `map.coordinate_system` | string | — | 상수 `"ue_world_cm_z_up"` | — | — | 변환기 검사 | v2.0 | 필수 |
| `map.bounds_kind` | string | — | `"policy_world_extent"` / `"region_union"` | 신설 | — | bounds 해석 | v2.0 | 필수 |
| `map.bounds{min_x_cm, min_y_cm, max_x_cm, max_y_cm}` | float | cm | 개체가 움직이는 XY 범위 | 정책 레벨: `UEcoDummyWorldProviderSubsystem::WorldExtent` = ±15000(`P/EcoWorldProviders.h:105-106`, 조향이 읽는 곳 `P/EcoBehaviorProcessors.cpp:580`). M3에는 맵 경계 개념이 없어서 지역 AABB의 합집합으로 대신한다(Q11) | 있음(L_test). M3는 파생값 | `rand.world_size`(9.2). 학습 범위는 한 변 60~110 u = 120~220 m다(`H/configs/default.yaml:73`). L_test는 300 m라 범위 밖이다 | v2.0 | 필수 |
| `map.boundary{extent_cm, margin_cm, push_weight, clamp}` | float, bool | cm | 언리얼에만 있는 경계 반발. 경계에서 `margin_cm` 안이면 밀어내는 벡터 × `push_weight`를 방향에 섞고 속력은 유지한 뒤 좌표를 자른다 | `P/EcoBehaviorProcessors.cpp:628-643`(여백 = SeeRadius × 0.25 = 1000 cm `:632`, 가중치 2 `:641`), 자르기 `:659-667`. 담당 우리 | 있음(정책 레벨) | R1 (i) 경계 반발 파리티의 근거. 시뮬레이터는 지금 좌표를 자르기만 한다(`H/env_v2/world.py:430`) | R1 | 필수(정책이 없으면 null) |
| `map.regions[].region_id` | string | — | | `S/World/EcologyRegion.h:31` | 있음(M3: Forest_A, Forest_B) | 지역 A/B 대응(9.2.4) | v2.3 | 필수(L_test는 배열 전체가 null) |
| `map.regions[].transform{location_cm{x,y,z}, rotation_deg{yaw,pitch,roll}, scale{x,y,z}}` | float | cm, deg | 지역 상자의 월드 변환 | `FEcoRegionSpatialSnapshot.BoundsTransform`(`S/Core/EcoMigrationTypes.h:43-56`), `UEcologyWorldSubsystem::BuildSpatialSnapshots`(`S/World/EcologyWorldSubsystem.cpp:80-106`, 게임 스레드 전용 `:82`) | 있음(M3). 실제 배치값은 레벨 에셋에만 있다 | v2.3 지역 분할 | v2.3 | 필수 |
| `map.regions[].extent_unscaled_cm{x,y,z}` | float | cm | 스케일 전 반폭 | `FEcoRegionSpatialSnapshot.BoundsExtent`. 기본 (5000, 5000, 1000)(`S/World/EcologyRegion.cpp:16`) | 있음(M3) | 위와 같다 | v2.3 | 필수 |
| `map.regions[].aabb_cm{min_x, min_y, max_x, max_y}` | float | cm | 위 두 값으로 계산한 월드 XY 축정렬 상자. 회전이 있으면 감싸는 상자다. 포함 판정 자체는 로컬 좌표로 한다(`S/Core/EcoMigrationTypes.h:50-55`) | 서버가 계산하는 파생값 | 파생 | v2.5a 틈(학습 0~5 u = 0~10 m, 계획:229)과 중심 간격(학습 30~55 u = 60~110 m, 계획:230). 경계 합집합 | v2.5a | 필수 |
| `map.regions[].arrival_point_cm{x,y,z}` | float | cm | 개체별 퍼짐을 더하기 전의 월드 도착점 | `ArrivalOffset`(`S/World/EcologyRegion.h:45`), 월드 변환 `S/World/EcologyWorldSubsystem.cpp:92`. 퍼짐은 `S/Mass/EcoMassMigration.cpp:13-25` | 있음(M3) | 시뮬레이터 도착점은 "지역 중심 + 1.5 u 원판"으로 정해져 있어(계획:231) 기록만 한다 | v2.5b | 필수 |
| `map.regions[].adjacent_region_ids[]` | string[] | — | 방향 있는 인접 목록 | `S/World/EcologyRegion.h:43`, 검증 `S/Mass/EcoMassLifecycleSubsystem.cpp:108-114` | 있음(M3) | v2.5b 이주 가능한 쌍 | v2.5b | 필수 |
| `map.regions[].initial_food_amount`, `food_capacity` | float | 먹이량 | 등록할 때의 값 | `S/World/EcologyRegion.h:39, 41`, `S/World/EcologyRegion.cpp:49-50` | 있음(M3) | 기록, 9.1 검사 | v2.0b | 필수 |
| `map.covers_source` | string | — | `"policy_dummy"` / `"external_provider"` / `"none"` | `Registry->GetCoverProvider()`를 더미 포인터와 비교한다. 판별 패턴은 `S/Debug/EcoPolicyTestSpawner.cpp:461-464`다 | 있음 | 관측 6이 쓰는 은신처 체계를 알린다(Q5) | v2.0 | 필수 |
| `map.covers[]{x_cm, y_cm, radius_cm}` | float | cm | 관측 6과 조향이 실제로 쓰는 은신처 원. `policy_inference`가 참일 때만 채운다 | 더미의 `GetCoverPoints()`·`GetCoverRadius()`(`P/EcoWorldProviders.h:109-110`). 배치 (±0.45·15000, ±0.45·15000)(`P/EcoWorldProviders.cpp:9-20`), 반경 2500(`.h:124-125`). 인터페이스에는 목록 함수가 없다(`.h:50-63`). 그래서 외부 Provider면 null(`NOT_IMPLEMENTED`)이다. `SetCoverProvider`는 C++ 호출자 0건이다. 담당 우리 | 있음(L_test, 더미 상수) | `rand.cover_frac`(합집합 넓이 ÷ 맵 넓이, 학습 0.05~0.30), `cover_r_min/max`(학습 4~9 u = 800~1800 cm라 2500은 범위 밖). 위치는 버린다(9.2.3) | v2.0 | 필수(정책이 없는 레벨은 null) |
| `map.shelters[]{x_cm, y_cm, z_cm, radius_cm, capacity, quality}` | float, int | cm | Social 은신처 앵커 | `AEcoShelterAnchor`의 Capacity·Quality·Radius(`S/AI/Social/Shelter/EcoShelterAnchor.h:31, 35, 39`), 목록 `GetShelters()`(`S/AI/Social/Shelter/EcoShelterSubsystem.h:80`). 점 구조체(`S/AI/Social/EcoSocialTypes.h:113-131`)에 반경이 없어서 액터에서 읽는다 | 있음(Lvl_JYU에 3개, 추정: 맵 파일 문자열에서 `EcoShelterAnchor_0~2`를 확인했다. 에디터 확인 필요. Jang_lv·L_test에는 0개, 추정) | 지금은 쓰지 않는다. 정책 은신처로 통일되면 covers로 옮긴다(Q5) | v2.0 | 선택 |
| `map.water[]{x_cm, y_cm, radius_cm, amount}` | float | cm | 물 지점 | 없음. 코드, 에셋, Water 플러그인 모두 0건(계획:420). 담당 없음(#26, 계획:549) | 없음 | v2.8 웅덩이 2~4개(계획:205, 236) | v2.8 | 필수(v2.8부터) |
| `map.obstacles[]{x_cm, y_cm, radius_cm}` | float | cm | 원으로 근사한 장애물 | 없음. 조향이 위치를 직접 쓴다(`P/EcoBehaviorProcessors.cpp:659-667`). 담당: World 스냅샷은 미정, 장애물 반발은 우리, 지면 추적은 wonkii(계획:421, 438) | 없음 | R1 원형 장애물(맵 넓이 0~5%, 계획:239) | R1 | 필수(R1부터) |

### 5.3 food

`food.regions[]`는 M3에만 있다. L_test에는 Ecology 지역이 없으므로 배열 전체를 null(`NOT_IN_LEVEL`)로 쓴다.

| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `food.regions[].region_id` | string | — | | | 있음(M3) | | v2.0b | 필수 |
| `food.regions[].food_amount{start, end, mean, min, max}` | float | 먹이량 | `start`는 창 첫 스텝의 장부 Before(= 앞 창의 `end`), `end`는 닫는 경계 시점의 값이다(6.1). mean·min·max는 (a) 표본 | `FRegionEcologyState.FoodAmount`(`S/Core/EcoRegionTypes.h:79`). 스텝 장부 Before는 `S/Ecology/EcologyResourceSimulation.cpp:66-67`, 스냅샷은 `:167-200`(직전 스텝 하나만 보관 `:198`) | 있음(M3). 지역 하나에 스칼라 하나이고 지역 안은 균일하다 | 9.1 보존식, 기록 | v2.0b | 필수 |
| `food.regions[].cap0_total` | float | 먹이량 | 식생 기준 용량 Σcap0. 바뀌지 않는다. **모든 먹이 비율의 분모다** | #20 전에는 지금의 `FoodCapacity`와 같다(`S/Core/EcoRegionTypes.h:83`. 등록 뒤 바꾸는 API가 없다, `S/Ecology/EcologySimulationSubsystem.cpp:98-119`). #20 뒤에는 격자 cap0의 합이다(담당 wonkii) | 있음(M3) | 시뮬레이터 비율의 분모 Σcap0(`H/env_v2/world.py:748-749`) | v2.0b | 필수 |
| `food.regions[].food_capacity{start, end, mean, min, max}` | float | 먹이량 | 장부의 용량 필드 | `S/Core/EcoRegionTypes.h:83` | 있음(M3, 지금은 고정이라 모든 값이 `cap0_total`과 같다). 계획 #20 계약안은 격자 도입 뒤 `FoodCapacity`를 ΣV로 파생한다(계획:435). 그때부터 시간에 따라 변한다 | 기록 | v2.0b | 필수 |
| `food.regions[].food_ratio{start, end, mean, min}` | float | [0,1] | 표본마다 `food_amount ÷ cap0_total`를 구한 뒤 시간 가중한다. `food_capacity`로 나누지 않는다 | 파생 | 있음(M3) | 시뮬레이터 `f_ratio` = ΣF/Σcap0(`H/env_v2/world.py:719, 749`) | v2.0b | 필수 |
| `food.regions[].vegetation_total{start, end, mean, min}` | float | 먹이량 | 식생 용량 층 ΣV. `vegetation_total ÷ cap0_total`이 시뮬레이터 `v_ratio`다 | 없음. 2층 장부가 없다. 담당 wonkii. 선행: 격자 장부안(#20, 계획:435, 543) | 없음 | `food_v.init_frac`, Gate F의 `v_ratio`(`H/env_v2/world.py:748`) | v2.0b | 필수(null 허용) |
| `food.regions[].consumed_total` | double | 먹이량 | 창 안 Σ Consumed | `FEcoResourceSnapshot.Consumed`(`S/Ecology/EcologyResourceSimulation.cpp:185`), 섭식 일괄 처리 `ResolveFeeding`(`:106-165`) | 있음(M3) | 보존식, 섭식 압력 | v2.0b | 필수 |
| `food.regions[].event_loss_total` | double | 먹이량 | Σ EventLoss(낮·밤 먹이 이벤트, `Debug.Starvation`) | `S/Ecology/EcologyResourceSimulation.cpp:68-102` | 있음(M3) | 학습에 없는 손실이다. 0이 아니면 경고한다 | v2.0b | 필수 |
| `food.regions[].rounding_adjustment_total` | double | 먹이량 | Σ RoundingAdjustment. 정의는 Before − EventLoss − Granted − After다 | `S/Ecology/EcologyResourceSimulation.cpp:186`. 절대값이 1e-6 × Before를 넘으면 스텝이 실패한다(`:187-192`) | 있음(M3) | 보존식 | v2.0b | 필수 |
| `food.regions[].regenerated_total` | double | 먹이량 | 장부 밖에서 늘어난 양. 창 안 각 스텝에 대해 (그 스텝의 Before − 직전 스텝의 After)를 더하고, 마지막으로 (닫는 경계의 값 − 마지막 스텝의 After)를 더한다 | 재생은 `TickSimulation`이 장부 밖에서 `FoodAmount`를 바꾸고 용량에서 자른다(`S/Ecology/EcologySimulationSubsystem.cpp:80-83`). 그래서 rate × 시간은 실제 증가량이 아니다 | 있음(M3, 지금은 0. `TickSimulation`은 C++ 호출자 0건이고 BlueprintCallable이다, `.h:44-45`) | 보존식, 재생 재개 뒤 `rand.food_regen_mult` 검산 | v2.0 | 필수 |
| `food.regions[].depleted_time_frac` | float | [0,1] | `bDepleted`(Food == 0)가 참인 시간의 비율 | `S/Ecology/EcologyResourceSimulation.cpp:183` | 있음(M3) | 기록 | v2.5a | 필수 |
| `food.regions[].below_epsilon_time_frac` | float | [0,1] | Food ≤ `Migration.FoodEpsilon`인 시간의 비율 | 이주 판단 `HasFood`(`S/Mass/EcoMassMigration.cpp:75-78`) | 있음(M3) | v2.5b 안전망 s_r = 1[F_r ≤ ε]의 빈도(계획:546). `bDepleted`와 기준이 달라서 따로 둔다 | v2.5a | 필수 |
| `food.regions[].depletion_events` | int | 회 | `bDepleted`가 false에서 true로 바뀐 횟수 | 파생 | 있음(M3) | 기록 | v2.5a | 선택 |
| `food.regions[].feed_grants` | int | 건 | 지급량이 0보다 큰 섭식 결과 수 | `FEcoFeedResult`(`S/Core/EcoResourceTypes.h:59-63`) | 있음(M3) | 개체당 섭식 빈도 | v2.0b | 선택 |
| `food.regions[].consumption_pressure_per_s` | float | /s | 무차원 소비 압력 = `consumed_total ÷ duration_s ÷ cap0_total` | 파생 | 있음(M3) | 시뮬레이터 대응값은 Σtaken/스텝 ÷ Σcap0 ÷ 0.1333이다. 지금은 재현하지 않는다(9.2.3) | v2.0b | 필수 |
| `food.regions[].regeneration_rate_per_s` | float | 먹이량/s (선형) | 창 평균 재생률 | `FRegionEcologyState.FoodRegenerationRate`(`S/Core/EcoRegionTypes.h:87`) | 값 안 채워짐. 등록할 때 0으로 둔다(`S/World/EcologyRegion.cpp:51`). 재생 함수 `TickSimulation`(`S/Ecology/EcologySimulationSubsystem.cpp:67-96`)은 C++ 호출자 0건이다. 담당 wonkii. 선행: 재생 재개와 용량 API(계획:414) | `rand.food_regen_mult`(9.2), v2.5a 재생비, v2.6 비 배수 | v2.0 | 필수(null 허용) |
| `food.regions[].regeneration_model` | string | — | `"none"` / `"linear"` / `"relax_to_capacity"` / `"two_layer"` | 지금 함수는 선형이지만 호출되지 않는다 | 지금은 `"none"` | 환산식 선택(9.2) | v2.0 | 필수 |
| `food.regions[].recovery_half_life_s` | float | s | 식생 V의 휴식 회복 반감기 | 없음(#20) | 없음 | `food_v.recovery_half_lives`(s ÷ 0.1333) | v2.0b | 필수(null 허용) |
| `food.grid[]{region_id, origin_cm{x,y}, cell_size_cm, nx, ny, cap0[], f_end[], v_end[], eaten_total[], last_eaten_s[]}` | object | cm, 먹이량, s | 지역별 셀 격자. 행 우선 [iy][ix]이고 셀 한 변은 400 cm다(계획:435) | 없음. 담당 wonkii. 선행 #20 | 없음 | 지금 World는 지도를 받지 않는다(9.2.3). 쓰는 곳은 `present_area_frac` 계산과 Gate F 흔적 비교다 | v2.0b | 선택 (#20 합의 뒤 필수) |
| `food.grid_update_interval_s` | float | s | 격자 갱신 간격 dt. 0.1333을 권한다(계획:435) | 없음 | 없음 | r과 ρ를 환산하고 α를 다시 보정한다(`H/env_v2/world.py:588-593`) | v2.0b | 필수(null 허용. 격자가 있으면 값 필수) |
| `food.present_area_frac` | float | [0,1] | Ecology 먹이 용량이 0보다 큰 넓이 ÷ 맵 넓이 | 격자가 없으면 계산하지 않는다. 지역 상자 넓이로 대신할 수는 있지만 M3 섭식이 위치와 무관해서 뜻이 없다 | 없음 | `food_patch_threshold` 역산. 학습 시드 0~999의 cap0 > 0 셀 비율은 0.024~0.802, 중앙값 0.2705다(평가 시드 10000~10019 중앙값 0.266. `H/env/world.py` World로 10-02에 다시 쟀다) | v2.0 | 필수(null 허용) |
| `food.policy_food_provider{kind, wavelength_cm, threshold, cell_cm, consumption_enabled, regen_per_s, present_area_frac}` | | cm, /s, [0,1] | 관측 0과 조향 food_grad가 실제로 읽는 먹이. Ecology의 FoodAmount와 무관하다 | 더미 사인 격자(`P/EcoWorldProviders.cpp:22-55`). 파장 6000, 문턱 0.35, 회복 0.02/s, 셀 400 cm(`P/EcoWorldProviders.h:113-125, 137`). 이 값들은 protected라 읽기 함수를 더해야 한다(담당 우리). `kind`는 Registry의 Food Provider 포인터를 더미와 비교해 정한다. `consumption_enabled`는 false다: `ConsumeFood`·`RegenerateConsumed`(`P/EcoWorldProviders.cpp:69-90`) 호출자가 0건이라 먹이가 줄지도 회복되지도 않는다. 그래서 `regen_per_s`는 null(`NOT_DRIVEN`, raw 0.02)로 쓴다. `present_area_frac`는 raw 먹이 > 0인 넓이 비율로 약 0.72다(10-02 표본 추정, 우리 집계기가 400 cm 격자 표본으로 계산한다) | 있음(L_test 더미) | 관측 0 분포를 해석한다. 게임 관측 0 평균(약 0.30, 10-02 표본 추정)은 시뮬레이터(보정 기록 0.051, `H/results/v2/diag_final/calib.json`)와 구조적으로 다르다(9.3) | v2.0 | 필수(정책이 없는 레벨은 null) |

### 5.4 threat

**포식자 (`threat.predators`)**. 정책 경로에만 있다. M3는 블록 전체가 null(`NOT_IN_LEVEL`)이다. M3 레벨에 포식자 종과 스폰을 넣는 일은 wonkii 님과 팀의 결정 사항이다(계획:417).
| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `threat.predators.kinds[].kind` | string | — | `"melee"` / `"ranged"` / `"player_like"` | — | — | 종류별 계수 | v2.0 | 필수 |
| `threat.predators.kinds[].species_label` | string | — | 포식자 종 이름 | 고정 라벨(4.3) | 있음(L_test) | 기록 | v2.0 | 필수 |
| `threat.predators.kinds[].count_mean`, `count_max` | float, int | 마리 | (c) 표본의 포식자 수 평균과 최댓값 | 피식 처리기의 포식자 쿼리(`P/EcoBehaviorProcessors.cpp:465-534`). 테스트 스포너 설정 5(`S/Debug/EcoPolicyTestSpawner.h:49`) | 있음(L_test) | `rand.predator_count`(학습 [2, 12]) | v2.0 | 필수 |
| `threat.predators.kinds[].speed_cm_s` | float | cm/s | 설정된 속력 | 900 × `PredatorSpeedRatio`(`S/Debug/EcoPolicyTestSpawner.h:61`, `.cpp:275`). 우리 집계기가 스포너에서 읽는다 | 있음(L_test) | `rand.pred_speed_mult` = speed ÷ 900(학습 [0.8, 1.2]) | v2.0 | 필수 |
| `threat.predators.kinds[].{catch_radius_cm, view_radius_cm, fov_deg, eat_cooldown_s}` | float | cm, deg, s | 규칙 상수 | `P/EcoBehaviorConfig.h:32-35` | 있음 | `meta.constants`와 함께 검사 | v2.0 | 필수 |
| `threat.predators.kinds[].catch_prob_per_step` | float | /스텝 | 원거리형의 스텝·쌍당 포획 확률. 원거리형에만 쓴다 | 없음. 게임에 원거리형이 없다 | 없음 | `pred_ranged_catch_p` | v2.0 | 선택 |
| `threat.predators.ranged_frac` | float | [0,1] | 원거리형 마릿수 ÷ 전체 | 파생 | 있음(지금은 0) | `rand.ranged_frac` | v2.0 | 필수 |
| `threat.predators.by_region[]{region_id, kind, count_mean}` | | 마리 | (c) 표본마다 위치로 지역에 귀속한다(6.4) | 없음. L_test에 지역이 없고 M3에 포식자가 없다 | 없음 | v2.3 지역 포식자 M_r(9.2.2) | v2.3 | 필수(v2.3부터) |

**피식 (`threat.predation`, 포식자가 잡은 것)**. 정책 경로에만 있다.
| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `threat.predation.deaths_total` | int | 마리 | 창 안 **포식자 포획** 수. `UEcoPredationProcessor`의 호출 지점에서 센다. 서브시스템에서 세지 않는다 | `P/EcoBehaviorProcessors.cpp:527-529` | 있음(L_test) | `predation_rate` | v2.0 | 필수 |
| `threat.predation.exposure_alive_agent_s` | double | 마리·s | 산 초식 수의 시간 적분 = Σ_프레임 Alive × Dt | 프레임마다 세는 산 개체 수(`P/EcoBehaviorProcessors.cpp:437-449`)와 그 프레임의 Dt(`:456`). 서브시스템의 `StepPopulation`은 쓰지 않는다: 스텝 안 최댓값만 남기고 `Tick`마다 0으로 되돌려서(`P/EcoRegionPredationSubsystem.cpp:24-27, 39-40`) 한 프레임에 여러 스텝이 지나면 둘째 스텝부터 0이다 | 있음(원천) | 피식률의 분모(5.7) | v2.0 | 필수 |
| `threat.predation.by_region[]{region_id, deaths, exposure_alive_agent_s}` | | 마리, 마리·s | 사망 위치를 지역 상자에 귀속한다(6.4) | 없음. 지금 `ReportPredation`은 위치를 버린다(`P/EcoRegionPredationSubsystem.cpp:13-22`). main은 17000 cm 격자 키로 나누는데(`@main:S/AI/Policy/EcoRegionPredationSubsystem.h:90-100`) `AEcologyRegion`이 아니다. 담당: 위치 전달은 우리, 지역 귀속은 wonkii | 없음 | v2.3 기억 신호 deaths_r ÷ pop_r(계획:174) | v2.3 | 필수(v2.3부터) |
| `threat.predation.by_phase{day{deaths, exposure_alive_agent_s}, night{…}}` | | | 사건 시각의 위상 | 월드 시계가 필요하다. L_test에서는 시계가 돌지 않는다(계획:419) | 없음 | v2.4 밤 위험 | v2.4 | 필수(v2.4부터) |
| `threat.predation.by_phase_bin[8]` | int[] | 마리 | 6.3의 8구간 | 위와 같다 | 없음 | 박명 압력(#15) | v2.4 | 선택 |
| `threat.predation.prey_in_cover` | int | 마리 | 은신처 안에서 잡힌 수 | 포획한 엔트리의 `bInCover`(판정 `P/EcoBehaviorProcessors.cpp:497-498`, 채우는 곳 `:121`) | 있음(원천) | `cover_hide_mult` 효과 확인 | v2.0 | 선택 |
| `threat.predation.ema{mean, max, end}` | float | [0,1] | 관측 5의 값. (c) 표본마다 `Tick()` 뒤에 읽는다 | `GetRecentPredation()`(`P/EcoRegionPredationSubsystem.cpp:7-11`, [0,1]로 자른다), 스텝 `Tick`(`:29-41`), 호출 `P/EcoBehaviorProcessors.cpp:540-546` | 있음(L_test) | 관측 5 분포 비교. 정상 상태 값은 10 × 스텝당 피식률이다(`:38`, gain 10 `P/EcoBehaviorConfig.h:30`) | v2.0 | 필수(정책이 없는 레벨은 null) |
| `threat.predation.raw_ema_max` | float | [0, ∞) | 자르기 전 EMA의 최댓값 | `GetRawEma()`(`P/EcoRegionPredationSubsystem.h:81`, 테스트·디버그용) | 있음(L_test) | 기록 | v2.0 | 선택 |

- 이 EMA는 `ReportPredation`으로 들어온 모든 사망을 합친다. 그 함수는 "포식자 포획이든 플레이어 사냥이든" 받는 단일 입구다(`P/EcoRegionPredationSubsystem.h:59-64`). 플레이어 사냥이 이 입구로 들어오게 되면 원인 인자를 더한다(8절 P3, 우리). 그 뒤에도 `deaths_total`은 포식자 포획만 센다.

**지역 위험 기록 (`threat.region_risk[]`)**. M3에만 있다. L_test는 배열 전체가 null(`NOT_IN_LEVEL`)이다.
| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `threat.region_risk[]{region_id, predation_history{start, end, mean, max}}` | float | [0,1] | 지역 위험 기억. (a) 표본 | `FRegionEcologyState.PredationHistory`(`S/Core/EcoRegionTypes.h:94`) | 값 안 채워짐. 증가 `ApplyPredationEvent`(`S/Ecology/EcologySimulationSubsystem.cpp:174-189`)는 래퍼 `RecordPredationEvent`(`:218-224`)만 부르고, 감쇠(`:86-94`)는 `TickSimulation` 안에 있다. 둘 다 C++ 호출자 0건이다(BlueprintCallable `.h:44-45, 68-69, 80-81`). 담당 wonkii, 조연우(계획:418) | v2.3 m_r 초기값(`end`). 단 감쇠 0.05/s(반감기 약 13.9초, `.h:120`)는 학습 τ(반감기 300~7000스텝 = 40~933초, 계획:205)와 다르다(Q10) | v2.3 | 필수(null 허용) |

**플레이어 (`threat.player`, 모두 전체 합계)**. 6.7절의 개인정보 억제 규칙을 따른다.
| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `threat.player.player_count{mean, max}` | float, int | 명 | 접속 플레이어 수. M3는 (b), 정책 레벨은 (c) 표본 | `AEcoGameState::GetConnectedPlayerCount()`(`S/Network/EcoGameState.h:59`). GameMode가 PostLogin·Logout 때 갱신한다(`S/AdaptiveEcosystemGameMode.cpp:81-98`) | 있음 | 플레이어형 위협 마릿수, 6.7 억제 판정 | v2.0 | 필수 |
| `threat.player.presence_by_region[]{region_id, player_seconds}`, `presence_outside_s` | float | 명·s | (b) 표본마다 플레이어 Pawn 위치를 지역 상자에 귀속하고 1초씩 더한다 | Pawn 위치(엔진) + 포함 판정(6.4). 신규 경로(`P/`, `Mass/`, `Ecology/`의 활성 코드)에는 Player 참조가 0건이다. 레거시 `EcologyServerSubsystem`의 `RegionalPlayerPressure`(`S/Ecology/EcologyServerSubsystem.cpp:85, 318-340`)만 있고 꺼져 있다(`:25`, `G:6`) | 원천 있음, 집계 없음(`DEFERRED`). 담당: 집계는 서버 담당, 위협 취급은 wonkii·조연우(계획:422) | 등장 지역·일정, 압력 전환 간격(계획:205) | v2.3 | 필수(v2.3부터) |
| `threat.player.near_herd_seconds` | float | 명·s | 산 초식 하나 이상이 4000 cm(see_r) 안에 있던 플레이어 표본의 시간 합 | 신설. 초식은 128마리 이하이고 1 Hz라 전수 비교로 충분하다(추정) | 원천 있음, 집계 없음(`DEFERRED`) | 위협 노출 시간 | v2.3 | 필수(v2.3부터) |
| `threat.player.approach_speed_hist{edges, counts}` | | cm/s | near_herd 표본에서 플레이어의 수평 속력 분포. 구간은 6.3 | Pawn 속도(엔진) | 원천 있음, 집계 없음(`DEFERRED`) | 플레이어형 위협의 속력 배수(÷ 900) | v2.3 | 필수(v2.3부터) |
| `threat.player.kills.total` | int | 마리 | 플레이어가 죽인 초식 수 | 없음. M4의 Player Kill → PredationHistory가 구현되지 않았다(`D/Roadmap/M4/M4_REPRESENTATION_INTERACTION.md:26`). 레거시 `IngestEcologyEvent(CreatureKilled)`(`S/Ecology/EcologyServerSubsystem.cpp:318-323`)는 꺼져 있다. 담당 wonkii, 조연우(계획:422, #15 계획:538) | 없음 | 플레이어형 위협 포획률, 기억 신호 | v2.3 | 필수(v2.3부터) |
| `threat.player.kills.by_region_phase[]{region_id, day, night}` | int | 마리 | 사냥 위치와 시각 | 위와 같다 | 없음 | 지역 압력, 박명 낮 압력(#15) | v2.3 | 필수(v2.3부터) |
| `threat.player.kills.by_phase_bin[8]` | int[] | 마리 | 6.3의 8구간 | 위와 같다 | 없음 | 박명 낮 압력 | v2.4 | 선택 |
| `threat.player.kills.distance_hist{edges, counts}` | | cm | 사냥 순간 플레이어와 피식자 사이 수평 거리 | 위와 같다 | 없음 | 포획 거리(근접 200 / 원거리 600) | v2.3 | 필수(v2.3부터) |
| `threat.player.kills.bearing_hist{front, side, rear}` | int | 마리 | 피식자 진행 방향 기준 플레이어 방위(6.3) | 위와 같다 | 없음 | FOV(120°) 밖에서 다가온 비율 | v2.3 | 선택 |
| `threat.player.kills.prey_in_cover` | int | 마리 | 은신처 안에서 사냥된 수 | 위와 같다 | 없음 | 은신처 효과 | v2.3 | 선택 |

### 5.5 population

**M3 지역별 (`population.regions[]`)**. L_test는 배열 전체가 null(`NOT_IN_LEVEL`)이다.
| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `population.regions[].region_id` | string | — | | | 있음(M3) | | v2.0 | 필수 |
| `population.regions[].population{start, end, mean, min, max}` | float | 마리 | (a) 표본, 시간 가중. 소속 Fragment 기준이다(6.4). `start`는 창을 여는 시점의 값이라 첫 창에서는 초기 스폰 직후 값이다 | `FRegionEcologyState.Population`(`S/Core/EcoRegionTypes.h:98`), 집계 `ReconcilePopulation`(`S/Mass/EcoMassLifecycleSubsystem.cpp:188-239`) | 있음(M3) | 밀도로 `world_size`를 정한다(9.2). v2.5a I1·I2의 N_A/N_B | v2.0 | 필수 |
| `population.regions[].traveling_mean`, `waiting_mean` | float | 마리 | (a) 시간 가중 | `S/Core/EcoRegionTypes.h:102, 104`, 집계 `S/Mass/EcoMassLifecycleSubsystem.cpp:226-227` | 있음(M3) | v2.5b 이동 중 비율 | v2.5b | 필수 |
| `population.regions[].average_energy_mean` | float | [0,1] | 개체 수 가중 평균 Σ(AvgE·Pop·Δt) ÷ Σ(Pop·Δt). Pop = 0인 표본은 뺀다(빈 지역의 AverageEnergy는 0이다) | 매 스텝 `ReconcilePopulation`이 Energy/MaxEnergy 평균을 다시 계산한다(`S/Mass/EcoMassLifecycleSubsystem.cpp:228-235`, 저장 `S/Ecology/EcologySimulationSubsystem.cpp:203`) | 값 안 채워짐. 파생값은 갱신되지만 원천 Energy를 바꾸는 코드가 없다(템플릿 기본 100/100, `S/Mass/EcoMassFragments.h:55, 58`). 그래서 개체가 있으면 1.0이다. 파일에는 null(`NOT_DRIVEN`)과 잰 값을 `raw_value`로 쓴다. 담당 wonkii. 선행: 에너지 대사(계획:413) | v2.1 에너지 경제 비교 | v2.1 | 필수(null 허용) |
| `population.regions[].spawned_total` | int | 마리 | 창 안에서 실제로 스폰된 수. 첫 창을 열기 전에 하는 초기 스폰(`S/Mass/EcoMassLifecycleSubsystem.cpp:161-172`)은 넣지 않는다 | 웨이브 스폰 루프의 `ExecuteSpawnRequest` 반환값(`:305`), 로그 `[Eco Spawn]`(`S/Mass/EcoMassNetworkBootstrap.cpp:218-222`) | 있음(M3) | 출생·이입 비교, v2.5a 리스폰 규칙 | v2.5a | 필수 |
| `population.regions[].spawn_waves_skipped` | int | 회 | 요청 수가 0인 웨이브(먹이·상한 때문) | `[Eco Spawn Skipped]`(`S/Mass/EcoMassLifecycleSubsystem.cpp:309-311`) | 있음(M3) | 먹이 0인 지역의 스폰 제외 확인 | v2.5a | 선택 |
| `population.regions[].departures` | int | 마리 | 이주 결정에서 Resident → Traveling이면서 목표 ≠ 현재 지역인 전이 수. 출발 지역에 센다 | `S/Mass/EcoMassMigration.cpp:101-108`(전이), 비교 기준 `:71-73`. 코드에는 "출발 commit"이 없다 | 있음(M3, 지금은 로그만) | v2.5b 이주율 | v2.5b | 필수 |
| `population.regions[].arrivals` | int | 마리 | From ≠ To인 도착 commit 수. 도착 지역에 센다 | `S/Mass/EcoMassMigration.cpp:116-127`(From `:73`). 같은 지역으로 돌아오는 commit도 있다(현재 지역에 먹이가 있으면 목표가 현재 지역이 된다 `:86`, 이때 Resident가 아니면 Traveling이 된다 `:97-108`) | 있음(M3, 지금은 로그만 `:133-138`) | v2.5b I지표 | v2.5b | 필수 |
| `population.regions[].return_arrivals` | int | 마리 | From == To인 도착 commit 수(귀환) | 위와 같다 | 있음(M3) | 기록 | v2.5b | 선택 |
| `population.regions[].retargets` | int | 회 | Traveling 중 목표가 바뀐 전이 수(OldTarget ≠ Target, `:72, 104`) | 위와 같다 | 있음(M3) | 왕복(I5) 해석 | v2.5b | 선택 |
| `population.regions[].deaths{predation, starvation, player, other}` | int | 마리 | 원인별 사망 | M3에는 사망 경로가 없다. `FEcoPendingDeathTag`(`S/Mass/EcoMassTags.h:20`)는 정책 처리기(`P/EcoBehaviorProcessors.cpp:33`)와 테스트 스포너만 쓰고, 시체 정리 Lifecycle이 없다. 담당 wonkii(계획:413) | 없음 | `starve_rate`, `starve_share`(`H/env_v2/rollout.py:303-305`), 피식률 | v2.1 | 필수(null 허용) |
| `population.regions[].lifespan{completed_count, completed_mean_in_window_s, censored_count, censored_mean_in_window_s, censored_mean_age_s}` | | 마리, s | `completed_*`: 창 안에서 죽은 개체. `censored_*`: 창 끝에 살아 있는 개체. `*_in_window_s`는 창 시작에서 왼쪽을 자른 값, 곧 창 안에서 산 시간이다(6.2). `censored_mean_age_s`는 자르지 않은 나이다 | 스폰 시각 `FEcoLifetimeFragment::SpawnTimeSeconds`(`S/Mass/EcoMassFragments.h:145-151`). 스폰할 때 채운다(`S/Mass/EcoMassNetworkBootstrap.cpp:210-211`), 템플릿에 들어 있다(`S/Mass/EcoMassNetworkTrait.cpp:34, 51`). 창을 닫을 때 Authority·Alive 개체를 조회한다(Mass가 처리 중이 아닐 때) | `censored_*`는 있음(M3). `completed_*`는 없음(사망 경로가 없다, 담당 wonkii) | `survival`(s ÷ 0.1333, 정의 6.2) | v2.1 | 필수(null 허용) |
| `population.migration_matrix[]{from_region_id, to_region_id, count}` | int | 마리 | 창 안 From ≠ To 도착 commit 수 | 위 이주 원천 | 있음(M3, 지금은 로그만) | v2.5b I지표 | v2.5b | 필수(L_test는 null) |
| `population.migration_by_cause{food_depletion, player_threat, predator_threat, other}` | int | 마리 | 원인별 이주 | 원인 분류는 문서에만 있다(`D/Roadmap/M3/MIGRATION_AWARE_SPAWN_PLAN.md:38-39`). 코드에는 0건이다(`git grep FoodDepletion` 0건) | 없음 | v2.5b 해석 | v2.5b | 선택 |
| `population.by_species[]{species_id, alive_mean}` | | 마리 | | `FEcoIdentityFragment.SpeciesId`(`S/Mass/EcoMassFragments.h:33`) | 있음(M3) | 종이 하나인지 확인 | v2.0 | 선택 |

**정책 테스트 레벨 (`population.policy_test`)**. L_test에서만 쓴다. 다른 레벨은 null(`NOT_IN_LEVEL`)이다. 모두 우리 집계기가 스포너에서 읽는다.
| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `population.policy_test.herbivore_count` | int | 마리 | 설정된 수(96) | `S/Debug/EcoPolicyTestSpawner.h:45` | 있음(L_test) | 밀도(9.2) | v2.0 | 필수 |
| `population.policy_test.alive_mean` | float | 마리 | `exposure_alive_agent_s ÷ duration_s` | 파생 | 있음(L_test) | 밀도 | v2.0 | 필수 |
| `population.policy_test.respawns_total` | int | 마리 | 포획 뒤 되살아난 수 | `RespawnCaught`(`S/Debug/EcoPolicyTestSpawner.cpp:206-256`) | 있음(L_test) | 즉시 리스폰 구조가 같은지 확인 | v2.0 | 선택 |
| `population.policy_test.spawn_radius_cm` | float | cm | 12000 | `S/Debug/EcoPolicyTestSpawner.h:53` | 있음(L_test) | 초기 배치 범위 | v2.0 | 선택 |
| `population.policy_test.lifespan{…}` | | | M3와 같은 구조 | 테스트 초식에는 Identity와 Lifetime Fragment가 없다(구성 `S/Debug/EcoPolicyTestSpawner.cpp:126-139`). 담당 우리: Lifetime Fragment를 더하고 리스폰할 때 스폰 시각을 갱신한다 | 없음 | `survival` | v2.0 | 선택 |

### 5.6 time_weather

| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `time_weather.clock_running` | bool | — | 창 동안 월드 시계가 돌았는지 | `UEcoWorldClockSubsystem::IsClockRunning()`. 시작은 M3 조정자가 성공한 뒤에만 한다(`S/Mass/EcoMassLifecycleSubsystem.cpp:173`) | 있음(M3). L_test에서는 false | 낮밤 필드를 쓸 수 있는지 | v2.0 | 필수 |
| `time_weather.day_duration_s`, `night_duration_s` | double | s | 실제 시계의 상 길이 | 고정 주기 계산(`S/World/EcoWorldClockSubsystem.cpp:7-23`). 설정 `G:7-8`(10/10), 코드 기본값 60/60(`S/Core/EcoRuntimeSettings.h:46, 48`). 외부 제공자 `IEcoDayCycleProvider`(`S/World/EcoDayCycleProvider.h:18-22`)는 구현이 0건이다 | 있음(M3) | 낮밤 주기 T = (D + N) ÷ 0.1333 스텝. 학습은 {600, 900, 1800}(계획:205)이다. 지금 20초는 150스텝이라 범위 밖이다(#21, 계획:544) | v2.4 | 필수(null 허용) |
| `time_weather.day_fraction` | float | [0,1] | D ÷ (D + N) | 파생 | 있음(M3) | 학습은 0.5로 고정이다 | v2.4 | 필수(null 허용) |
| `time_weather.cycles_in_window` | float | 일 | duration_s ÷ (D + N) | 파생 | 있음(M3) | 창 길이 확인 | v2.4 | 필수(null 허용) |
| `time_weather.phase_at_start{phase, cycle_id, elapsed_in_phase_s}` | | s | 창 시작 시점의 위상 | `FEcoDayCycleState{CycleId, Phase, PhaseStartSeconds, PhaseEndSeconds}`(`S/Core/EcoTimeTypes.h:8-20`) | 있음(M3) | 시작 위상 o(학습은 균등하게 뽑는다) | v2.4 | 선택 |
| `time_weather.twilight` | null | — | 박명 | 없음. 시계가 Day와 Night만 낸다. 파이썬 박명 0.05·T는 계약값이라 받지 않아도 된다 | 없음 | — | v2.4 | 선택 |
| `time_weather.weather.regions[]{region_id, state_time_frac{clear, rain, storm, drought}, rain_spells{count, mean_duration_s, censored_count}, clear_spells{…}}` | float, int | s | (b) 표본으로 지역별 날씨 상태의 시간 비율과 구간 길이를 구한다. "비"는 Rain + Storm이다(제안, Q16). 창 경계에 걸친 구간은 경계에서 자르고 `censored_count`로 따로 센다. `mean_duration_s`는 잘리지 않은 구간만으로 구한다(제안) | `FRegionEnvironmentState.WeatherState`(`S/Core/EcoRegionTypes.h:55`, 열거 `:25-31`), 읽기 `UEcologyWorldSubsystem::GetEnvironmentState`(`S/World/EcologyWorldSubsystem.cpp:70-78`) | 값 안 채워짐. 편집기 입력값 그대로이고 C++에서 쓰는 곳이 0건이다. BP `SetEnvironmentState`(`S/World/EcologyRegion.h:59-60`)만 있다. 담당 World 담당(미정, avaroki 추정, 계획:101, 420) | v2.6 평균 지속(맑음 1500, 비 400스텝 = 200초, 53초, 계획:234), 가뭄 비율 | v2.6 | 필수(v2.6부터) |
| `time_weather.environment.regions[]{region_id, temperature_mean, humidity_mean, rainfall_mean}` | float | 단위 정의 없음 | 시간 평균 | `S/Core/EcoRegionTypes.h:43, 46, 49` | 값 안 채워짐(편집값) | 시뮬레이터에서 쓰는 곳이 없다. v2.5a의 "지역 환경"은 재생비로 정의되어 있다 | — | 선택 |

### 5.7 policy_outcome (재현 확인용)

정책이 도는 레벨(지금은 L_test)에서만 채운다. M3에서는 블록 전체가 null(`NOT_IN_LEVEL`)이다. 모두 우리(`P/`) 몫이다.
- 표본: (d) 개체 결정 사건. `AdvanceDecisionPhase`가 참을 돌려준 개체만 센다(`P/EcoBehaviorProcessors.cpp:341-385`). 개체마다 결정 위상이 흩어져 있어서(`:335-344`, 테스트 스포너 `S/Debug/EcoPolicyTestSpawner.cpp:186-187`) 모든 개체가 동시에 결정하는 시점은 없다.
- 결정은 개체당 프레임마다 많아야 한 번이다(`P/EcoPolicyClock.h:56-80`). 그래서 한 프레임이 8틱보다 길면 결정 수가 `exposure ÷ StepSeconds`보다 적게 나온다. 두 값을 함께 보고 차이가 크면 `meta.window.policy_multi_step_frames`를 본다.
- 합과 제곱합 누적기는 double로 둔다(43만 표본에서 float32는 상쇄 오차가 크다). 파일에 쓸 때만 float로 반올림한다.
- 행동 순서: forage, cohesion, flee_dist, cover(`D/RL_Policy/POLICY_CONTRACT_V1.md:50-53`)
- 관측 순서: food_density, predator_count, predator_distance, conspecific_count, energy, recent_predation, cover_distance(`D/RL_Policy/POLICY_CONTRACT_V1.md:34-40`)

| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `policy_outcome.agent_policy_steps` | int | 개체·스텝 | 결정 사건 수. 행동·관측 평균의 분모로만 쓴다 | 결정 루프(`P/EcoBehaviorProcessors.cpp:341-385`) | 있음(원천) | 평균의 분모(`H/env/world.py:514`) | v2.0 | 필수 |
| `policy_outcome.counts{pred_seen, hungry, in_cover}` | int | 개체·스텝 | 조건별 결정 사건 수. 창을 합칠 때 가중치로 쓴다 | 아래 각 행 | 있음(L_test) | 창 합치기(9.1) | v2.0 | 필수 |
| `policy_outcome.action_mean[4]`, `action_std[4]` | float | [0,1] | 개체·스텝 평균과 모집단 표준편차(6.2) | `FEcoPolicyOutputFragment::Action`(`S/Mass/EcoMassFragments.h:113-120`, 쓰는 곳 `P/EcoBehaviorProcessors.cpp:380-384`) | 있음(L_test). 지금은 5초마다 그 순간 개체들의 평균을 로그로만 찍는다(`S/Debug/EcoPolicyTestSpawner.cpp:378-386, 486-519`) | `cohesion_mean`, `flee_dist_mean`, `flee_dist_std`(`H/env/world.py:551-553`), 보정의 `mean_action`(`H/diagnose_v2.py:355-359`) | v2.0 | 필수 |
| `policy_outcome.obs_mean[7]`, `obs_std[7]` | float | [0,1] | 개체·스텝 평균과 표준편차 | `FEcoObservationFragment`(`S/Mass/EcoMassFragments.h:100-107`), 채우는 곳 `P/EcoBehaviorProcessors.cpp:350-364` | 있음(L_test) | 입력 분포 비교(`H/diagnose_v2.py:356`) | v2.0 | 필수 |
| `policy_outcome.pred_seen_frac` | float | [0,1] | 관측 1 > 0(= 시야 안 포식자 수 > 0)인 결정 사건 비율 | 위와 같다 | 있음(L_test) | 위협 노출 비교 | v2.0 | 필수 |
| `policy_outcome.action_mean_pred_seen[4]`, `action_mean_pred_unseen[4]` | float | [0,1] | 관측 1 > 0인지에 따른 조건부 평균 | 위와 같다 | 있음(L_test) | `react_pred` = 인덱스 1·2·3 차이의 절댓값 평균(`H/env/world.py:519-524, 541-544`) | v2.0 | 필수 |
| `policy_outcome.forage_mean_hungry`, `forage_mean_full` | float | [0,1] | **결정 시점의 관측 4** < 0.5인지에 따른 조건부 forage 평균 | 관측 4(`P/EcoBehaviorProcessors.cpp:358-359`) | 있음(제한). 에너지가 스폰 값 U[20,100]/100과 리스폰 값 0.5에서 변하지 않는다(`S/Debug/EcoPolicyTestSpawner.cpp:185, 246`). 개체 사이 차이만 반영한다. 에너지 루프 담당은 wonkii(계획:413) | `react_hunger`(`H/env/world.py:526-530`). 파이썬은 섭식·번식을 처리한 **뒤**의 에너지로 판정한다(`H/env_v2/world.py:437-450, 676`). 9.3에 적었다 | v2.0 (의미 있는 값은 v2.1) | 필수 |
| `policy_outcome.cover_frac` | float | [0,1] | 결정 시점에 은신처 안에 있던 결정 사건 비율 | `IEcoWorldCoverProvider::IsInCover(Self)`(`P/EcoWorldProviders.h:62`) | 있음(원천) | `cover_frac`(`H/env/world.py:554`) | v2.0 | 필수 |
| `policy_outcome.predation_rate_per_step` | float | /개체·스텝 | `deaths_total ÷ (exposure_alive_agent_s ÷ StepSeconds)`. 분모는 이것 하나로 통일한다 | 파생 | 있음(L_test) | `predation_rate`(`H/env/world.py:550`) | v2.0 | 필수 |
| `policy_outcome.starve_rate_per_step` | float | /개체·스텝 | 아사 수 ÷ (exposure ÷ StepSeconds) | 없음(아사가 없다). 담당 wonkii(계획:413) | 없음 | `starve_rate`(`H/env_v2/rollout.py:304`) | v2.1 | 필수(null 허용) |
| `policy_outcome.survival_mean_steps` | float | 스텝 | 수명 평균(6.2 정의) | 없음(5.5의 `policy_test.lifespan`, 담당 우리) | 없음 | `survival`(`H/env/world.py:536-537, 548`) | v2.0 | 선택 |

`mean_return`, `g_gamma`, `repro`는 게임에 해당 값이 없어서 보내지 않는다.

### 5.8 series (지역 시간 계열, 선택이며 v2.3부터 필수)
M3 (b) 표본에서 만든다. 플레이어 계열은 6.7절 억제 규칙을 따른다.
| 필드 경로 | 타입 | 단위 | 의미·집계 | 언리얼 원천 | 지금 상태 | 시뮬레이터에서 쓰는 곳 | 버전 | 필수/선택 |
|---|---|---|---|---|---|---|---|---|
| `series.interval_s` | float | s | 계열 간격. 10초를 제안한다 | 신설 | 없음 | — | v2.3 | 필수(v2.3부터) |
| `series.t_start_s[]` | double[] | s | 각 구간의 시작 서버 시간 | 신설 | 없음 | — | v2.3 | 필수(v2.3부터) |
| `series.regions[]{region_id, population_mean[], food_ratio_mean[], predation_deaths[], player_kills[], player_seconds[], departures[]}` | float[], int[] | 5.3~5.5와 같다 | 구간별 평균 또는 합 | 5.3~5.5와 같다 | 있는 것은 있음(M3: population, food, departures) | v2.3 압력 전환 간격(고압 지역이 바뀌는 평균 간격 ÷ 0.1333), 기억 τ 검증, 먹이 회복 동역학(v2.0b를 v2.3 시점에 다시 설계할 때) | v2.3 | 필수(v2.3부터) |

---

## 6. 집계 규칙과 결측값 규칙

### 6.1 창과 경계
1. **M3 기본 경계 (`day_start`)**
   - 판정 위치는 `ProcessEcologyStep` 안, `ReconcilePopulation`(`S/Mass/EcoMassLifecycleSubsystem.cpp:293`) 뒤와 `BeginResourceStep`(`:294`) 앞이다. 이 시점에 그 스텝의 `Time.DayCycle`을 이미 안다.
   - 조건: `Phase == Day`이고, `CycleId`가 창 시작 스텝의 `CycleId`보다 크고, `Time.ServerTimeSeconds − 창 시작 ≥ SeasonMinSeconds`(제안 600초).
   - 조건이 참이면 **이 스텝의 사건을 더하기 전에** 지금 창을 닫고 새 창을 연다. 경계 스텝의 사건(스폰, 섭식, 이벤트, 이주)은 새 창에 들어간다. 이것이 [start, end) 규칙이다.
   - 닫는 창의 `end` 값(먹이, 개체 수)은 이 시점의 지역 상태다. 같은 값이 새 창의 `start`가 된다. 그래서 창 사이 값이 이어진다.
   - 생태 스텝 시각에는 상 경계가 반드시 들어간다(다음 일정 시각의 후보가 `PhaseEndSeconds`다, `S/Ecology/EcologyResourceSimulation.cpp:31`). 그래서 `end_server_time_s`는 정확히 낮 시작 시각이다.
   - **첫 창**은 t = 0 생태 스텝의 같은 위치에서 연다. 이 스텝은 `InitializePopulation` 안에서 `bInitialized`를 세우기 전에 돈다(`:176-177`). 내보내기 서브시스템은 이 호출도 받아야 한다. 초기 스폰(`:161-172`)은 창을 열기 전이므로 `spawned_total`에 들어가지 않고 `population.start`에 들어간다.
   - 지금 있는 일 경계 판별 `ReportDailyPopulation`(`:343-369`)은 스텝 끝, 곧 섭식·이주가 끝난 뒤에 돈다. 그래서 창 경계에는 쓰지 않는다.
   - **600초로 정한 이유**: 학습 세계의 reset 주기가 4000스텝 = 533초다(`H/configs/v2.yaml:28`). 하루가 60/60초면 5일이고, 지금 ini의 10/10초면 30일이다. V 회복 반감기(최대 933초)처럼 느린 동역학은 파이썬이 이어진 창들을 붙여서 본다.
2. **시계가 없는 레벨 (`elapsed_seconds`, 우리)**
   - L_test는 정책 스텝 경계 수 × `StepSeconds` ≥ `SeasonMinSeconds`(= 4500 경계)가 되는 `Predation->Tick()` 경계에서 닫는다(`P/EcoBehaviorProcessors.cpp:540-546`).
   - 시간 원점은 피식 처리기가 처음 스텝 경계를 닫은 시점이다. 이 시계는 논리 시간이다. 한 프레임이 8.5초를 넘으면 나머지를 버린다(`P/EcoPolicyClock.h:27-46`).
3. **콘솔 (`console`)**
   - `Eco.Season.Export`(제안)는 지금 창을 바로 닫고 새 창을 연다. Mass가 처리 중이면 다음 프레임 pre-actor 틱으로 미룬다.
   - 등록은 `UEcoDebugCommandSubsystem::RegisterCommand`(`S/Debug/EcoDebugCommandSubsystem.cpp:23-57`)로 한다. 서버와 Standalone 전용이다(`:41-45`). `ECVF_Cheat`로 등록되므로 Shipping 빌드에는 없을 것이다(`:49`, 추정).
   - 길이가 모자라면 `complete = false`로 쓴다.
4. **시스템 실패 (`system_failed`)**
   - M3 조정자가 `Fail()`하면(`S/Mass/EcoMassLifecycleSubsystem.cpp:63-69`) 그 뒤 생태 스텝이 영구히 멈춘다(`:243`).
   - 내보내기는 실패 시점까지를 `boundary_kind = "system_failed"`, `complete = false`로 쓴다. 파이썬은 보고만 하고 설정에 넣지 않는다.
5. **세션 종료**
   - `EEcoWorldPhase::Ending`(`S/Network/EcoMatchTypes.h:16`)을 설정하는 코드가 없다.
   - Deinitialize 시점에 쓰는 것은 Mass가 정리되는 중이라 위험하다(추정). 그래서 지금은 끝나지 않은 창을 버린다(제안, Q2).
6. 창은 겹치지 않고 이어진다. 앞 창의 끝이 다음 창의 시작이다.

### 6.2 표본 지점과 요약
| 표본 | 시점 | 간격 | 쓰는 필드 |
|---|---|---|---|
| (a0) 생태 스텝 시작 (M3) | `ProcessEcologyStep`의 `:293`과 `:294` 사이 | 생태 스텝마다 | 창 경계 판정, 창의 `start`·`end` 값 |
| (a) 생태 스텝 끝 (M3) | `ProcessEcologyStep` 끝(`:339` 다음). `OnWorldPreActorTick`에서 불리고 Mass 처리 전이다(`:241-246, 264`) | 가변, 최대 0.25초. 한 프레임에 최대 8스텝을 따라잡는다(`:265-267`) | food, population, region_risk |
| (b) 1초 요약 (M3) | 1초 분기 `if (Time >= NextSummaryTime)`(`:334-338`). `PublishCompletedSummary` 안이 아니라 분기에서 부른다. 그 함수는 `AEcoGameState`가 없으면 바로 반환한다(`:373-374`) | 서버 시간 1초 | 플레이어 수·체류·속력, 날씨, series |
| (c) 정책 스텝 경계 (정책 레벨) | `UEcoPredationProcessor`의 `Predation->Tick()` 반복 안(`P/EcoBehaviorProcessors.cpp:543-546`), `Tick()` 바로 뒤 | 논리 시간 0.1333초 | 포식자 수, EMA, 정책 레벨의 플레이어 수, `policy_step_boundaries` |
| (d) 개체 결정 사건 (정책 레벨) | 결정 루프에서 결정이 난 개체(`:341-385`) | 개체마다 0.1333초(위상이 흩어져 있다) | policy_outcome |
| (e) 프레임 (정책 레벨) | `UEcoPredationProcessor::Execute`의 산 개체 수(`:437-449`) | 프레임 | `exposure_alive_agent_s` |

L_test에는 (a)·(b)가 없다. `ProcessEcologyStep`은 `IsPopulationReady()`일 때만 돌고(`:250`), L_test에는 Bootstrap이 없어 `InitializePopulation`이 성공하지 않는다(`S/AdaptiveEcosystemGameMode.cpp:60-66`, 지역 2개 미만이면 실패 `S/Mass/EcoMassLifecycleSubsystem.cpp:103-104`). 그래서 L_test 파일의 `ecology_steps`·`summary_samples`는 null(`NOT_IN_LEVEL`)이다.

| 요약값 | 정의 |
|---|---|
| `start` / `end` | (a0)에서 창을 열 때의 값 / 닫을 때의 값. 먹이의 `start`는 첫 스텝의 장부 Before와 같다 |
| `mean` | 시간 가중 평균 = Σ v_k·Δt_k ÷ Σ Δt_k. 표본 값이 다음 표본까지 유지된다고 본다. 마지막 표본의 Δt는 창 끝까지다 |
| `min` / `max` | `start`, `end`와 창 안 표본을 모두 포함한 최소와 최대 |
| `…_total`, 횟수 | 창 안 스텝에서 일어난 사건의 합 |
| 개체·스텝 평균과 표준편차 | 모든 결정 사건에 대한 평균. 표준편차는 √max(E[x²] − E[x]², 0)이다. 파이썬과 같다(`H/env/world.py:538-539`). 누적기는 double이다 |
| 수명 평균 | (창 안 완료 수명의 합 + 창 끝 산 개체의 창 안 나이 합) ÷ (완료 수 + 산 개체 수). 나이는 창 시작에서 자른다: 창 안 나이 = 끝 − max(스폰 시각, 창 시작). 파이썬 `survival`도 reset 뒤 스텝만 센다(`H/env/world.py:536-537`, reset 때 0 `H/env_v2/world.py:642`) |
| 정밀도 | 시각과 합계는 double, 나머지 float32 값은 유효숫자 7자리까지 쓴다 |

### 6.3 구간 정의
| 구간 | 정의 | 근거 |
|---|---|---|
| 위상 | 사건 시각의 `FEcoDayCycleState.Phase`. `"day"` 또는 `"night"` | `S/Core/EcoTimeTypes.h:8-20` |
| 위상 8구간 | bin = (night ? 4 : 0) + floor(4 × (t − PhaseStartSeconds) ÷ (PhaseEndSeconds − PhaseStartSeconds)), 0~7. 0은 낮의 첫 1/4(새벽 쪽), 3은 낮의 마지막 1/4(저녁 쪽), 4~7은 밤이다 | 박명 압력 확인(#15) |
| 방향 | θ는 피식자 전방(Transform yaw의 XY 단위벡터)과 피식자→플레이어 벡터 사이의 각이다. front: \|θ\| ≤ 60°, side: 60° < \|θ\| ≤ 120°, rear: \|θ\| > 120°. 경계값은 앞 구간에 넣는다 | 초식 FOV 120°의 절반(`P/EcoBehaviorConfig.h:25`) |
| 거리 (cm) | [0, 200), [200, 600), [600, 1000), [1000, 2800), [2800, 4000), [4000, ∞) | 근접 포획 200, 원거리 포획 600(`H/configs/default.yaml:56`의 3 u), 분리 반경 1000, 포식자 시야 2800, 초식 시야 4000 |
| 속력 (cm/s) | [0, 360), [360, 720), [720, 900), [900, 1080), [1080, 1500), [1500, ∞) | v2.1 걷기 0.4 × 900 = 360, 포식자 속력 배수 0.8·1.2 × 900 = 720·1080, 초식 900 |
| 히스토그램 형식 | `{"edges": [0, 200, …, null], "counts": [...]}`. null은 ∞이고, counts 길이 = edges 길이 − 1이다 | (제안) |

### 6.4 지역 귀속
- **개체 수**(`population.*`)는 지금처럼 소속 Fragment를 따른다(`FEcoRegionFragment.CurrentRegionId`, `S/Mass/EcoMassFragments.h:64-74`).
- **위치 사건**(피식, 플레이어 사냥, 플레이어 체류, 포식자 수 표본)은 사건 위치를 지역 상자에 넣어 판정한다. 판정은 이주 도착 판정과 같은 `FEcoRegionSpatialSnapshot::Contains`(`S/Core/EcoMigrationTypes.h:50-55`, Z 포함)다. 상자는 `BuildSpatialSnapshots`로 얻는다.
  - 여러 상자에 들면 사전순으로 첫 지역에 넣는다.
  - 어디에도 들지 않으면 `"_unassigned"`에 넣는다.
- 소속은 Travel 도착 commit에서만 바뀐다(계획:416). 그래서 두 방식의 결과가 어긋날 수 있다. 10-27의 소속 규칙 결정(#23, #24, 계획:546-547)이 나오면 그 규칙을 따르고 `meta.region_assignment`를 바꾼다.

### 6.5 결측값 규칙
1. 이 명세의 키는 "선택"을 빼고 모두 파일에 있어야 한다. 값이 없으면 null을 쓴다.
2. null인 값은 `missing`에 경로와 이유를 적는다. 블록이나 배열 전체가 null이면 그 경로 하나만 적는다. 반대로 `missing`에 적은 경로의 값은 null이어야 한다.
3. 경로는 점으로 구분한다. 배열 원소는 `[region_id]`나 `[인덱스]`로 적고, `[*]`는 모든 원소를 뜻한다. 예: `food.regions[*].regeneration_rate_per_s`.
4. **0, 빈 배열, null을 구분한다.**
   - 시스템이 돌았는데 사건이 없었으면 0이다.
   - 시스템이 있는데 대상이 0개면 빈 배열 `[]`이다.
   - 시스템이 없어서 볼 수 없으면 null이다. 이것은 배열에도 같다. 예: L_test의 `map.regions`는 `[]`가 아니라 null(`NOT_IN_LEVEL`)이다.
5. NaN과 Inf는 금지한다. 분모가 0이면 null과 `NO_SAMPLES`로 쓴다.
6. 항목 형식은 `{"reason": 코드, "raw_value": 값(선택), "owner": 담당(선택), "note": 문장(선택)}`이다.
7. `NOT_DRIVEN`의 `raw_value`는 코드에 박힌 상수가 아니라 **창 안에서 잰 값**이다. 창 안에서 min = max이면 그 값을 쓴다.

| 이유 코드 | 뜻 | 예 |
|---|---|---|
| `NOT_IMPLEMENTED` | 언리얼에 원천이 없다 | 플레이어 사냥, 물, 격자 장부, 사망 |
| `NOT_DRIVEN` | 필드는 있으나 값을 바꾸는 활성 코드가 없어 상수다. `raw_value`를 반드시 적는다 | 재생률 0, PredationHistory 0, AverageEnergy 1.0, 날씨 편집값 |
| `NOT_IN_LEVEL` | 이 레벨에 해당 시스템이 없다 | Jang_lv의 포식자와 정책, L_test의 지역 |
| `CLOCK_NOT_RUNNING` | 월드 시계가 돌지 않았다 | L_test의 위상별 값 |
| `DISABLED_BY_CONFIG` | 설정으로 껐다 | `bEnableSpawnWaves=False` |
| `DEFERRED` | 원천은 있지만 그 필드가 필요한 버전 전이라 아직 집계하지 않는다 | 플레이어 체류(v2.3) |
| `NO_SAMPLES` | 표본이 0이거나 분모가 0이다 | 산 개체가 없는 지역의 평균 나이 |
| `PARTIAL_WINDOW` | 시스템이 창 중간에 시작했다 | 창 도중 시계 시작 |
| `SYSTEM_FAILED` | 시스템이 창 중간에 멈춰 값을 잴 수 없다 | M3 조정자 `Fail()` 뒤 |
| `SUPPRESSED_PRIVACY` | 6.7절 규칙으로 지웠다 | 1인 세션의 플레이어 계열 |

### 6.6 이유 코드에 따른 변환 동작 (파이썬)
| 이유 코드 | 변환기가 하는 일 |
|---|---|
| `NOT_DRIVEN` | `raw_value`가 게임 세계의 실제 값이다. 9.2절 표의 각 행이 "재현한다(raw 값을 쓴다)" 또는 "재현하지 않는다(기본 범위를 두고 보고서에 '게임 값 X, 반영 안 함'을 적는다)" 중 하나를 정해 둔다 |
| `NOT_IN_LEVEL` | 이 파일은 그 항목의 원천이 아니다. 같은 시즌의 다른 레벨 파일에서 가져온다. 없으면 기본 범위다. "구조적 0"(예: `predator_count [0, 0]`)으로 쓰는 것은 9.2절 행에 명시한 경우만이다 |
| `NOT_IMPLEMENTED`, `DEFERRED`, `NO_SAMPLES`, `CLOCK_NOT_RUNNING`, `SUPPRESSED_PRIVACY` | 기본 범위 |
| `DISABLED_BY_CONFIG` | 게임 값은 "꺼짐"이다. 시뮬레이터에 같은 기능이 있으면 끈다 |
| `PARTIAL_WINDOW`, `SYSTEM_FAILED` | 그 창을 설정 생성에서 뺀다. 보고만 한다 |

### 6.7 플레이어 개인정보 억제 (제안)
- 기준: 창의 `threat.player.player_count.max < k`, k = 3(제안, Q8).
- 기준에 걸리면 다음을 null과 `SUPPRESSED_PRIVACY`로 쓴다: `series.regions[*].player_seconds`, `series.regions[*].player_kills`, `threat.player.approach_speed_hist`, `threat.player.kills.by_region_phase`, `kills.by_phase_bin`, `kills.distance_hist`, `kills.bearing_hist`. 1인 세션에서는 이 값들이 곧 그 사람의 이동 경로와 사냥 기록이 되기 때문이다.
- 창 단위 합계(`player_count`, `presence_by_region`, `near_herd_seconds`, `kills.total`, `kills.prey_in_cover`)는 남긴다. 이것도 1인 세션에서는 개인 값이므로 팀이 정한다(Q8).

---

## 7. 예시 JSON

값은 모두 **예시**이고 실제로 잰 값이 아니다. 지역 상자는 `D/Roadmap/M3/M3_3_EDITOR_TEST.md:29`의 문서 예시(A 중심 (0,0,100), B 중심 (4000,0,100), 반폭 1500)를 따랐다. 설정값은 `G`의 실제 값이다. 선택 블록 `series`, `food.grid`, `environment`, `shelters`, `spawn_schedule`은 생략했다. 두 예시 모두 그대로 로더 시험의 고정 자료로 쓸 수 있게 완전한 파일로 실었다.

### 7.1 `Jang_lv` (M3) 창
```json
{
  "meta": {
    "season_export_schema_version": 1,
    "season_id": 3,
    "export_session_id": "5B1E0C2D-7A64-4F0E-9C3B-2D8E61A4F905",
    "window_index": 0,
    "world_epoch": 1834201177,
    "match_instance_id": "9F3C2A1B-5D6E-4F70-8A91-B2C3D4E5F607",
    "level_name": "Jang_lv",
    "map_package_name": "/Game/JWJ/UEDPIE_0_Jang_lv",
    "net_mode": "listen_server",
    "written_utc": "2026-10-20T06:12:44Z",
    "engine_version": "5.8.3",
    "build_id": null,
    "window": {
      "boundary_kind": "day_start",
      "complete": true,
      "time_source": "world_clock",
      "start_server_time_s": 0.0,
      "end_server_time_s": 600.0,
      "duration_s": 600.0,
      "start_step_id": 1,
      "end_step_id": 2432,
      "start_cycle_id": 0,
      "end_cycle_id": 30,
      "ecology_steps": 2431,
      "summary_samples": 600,
      "policy_step_boundaries": null,
      "policy_multi_step_frames": null
    },
    "systems": {
      "m3_population": true, "world_clock": true, "policy_inference": false,
      "predators": false, "predation_report": false, "player_report": false,
      "food_regeneration": false, "food_grid": false, "weather_server": false,
      "water": false, "energy_metabolism": false, "death_lifecycle": false
    },
    "policy": {
      "policy_schema_version": 1,
      "controller": "none",
      "learned_frac": null,
      "weights_id": "crc32:3A9F04C1",
      "predation_check_cadence": "per_frame"
    },
    "constants": {
      "grid_unit_cm": 200.0, "policy_interval": 8, "see_radius_cm": 4000.0, "herb_speed_cm_s": 900.0,
      "max_energy": 1.0, "obs_pred_count_norm": 8.0, "obs_kin_count_norm": 20.0, "obs_cover_norm_cm": 4000.0,
      "fov_deg": 120.0, "sep_weight": 1.35, "sep_radius_cm": 1000.0, "flee_weight": 3.0,
      "predation_ema_decay": 0.95, "predation_ema_gain": 10.0, "step_seconds": 0.1333333,
      "pred_view_radius_cm": 2800.0, "pred_fov_deg": 150.0, "pred_catch_radius_cm": 200.0,
      "pred_eat_cooldown_s": 0.6666667, "pred_wander_turn_rad": 0.15, "cover_hide_mult": 2.5,
      "init_energy_frac": 0.5
    },
    "runtime_settings": {
      "day_duration_s": 10.0,
      "night_duration_s": 10.0,
      "feeding": {"enabled": true, "first_delay_s": 5.0, "interval_s": 5.0, "amount": 1.0},
      "migration": {"enabled": true, "decision_interval_s": 1.0, "speed_cm_s": 400.0,
                    "arrival_radius_cm": 30.0, "arrival_spread_cm": 300.0, "food_epsilon": 0.0001},
      "day_food_event": {"enabled": false, "region_id": "Forest_A", "phase_fraction": 0.4166667, "food_loss": 40.0},
      "night_food_event": {"enabled": true, "region_id": "Forest_B", "phase_fraction": 0.25, "food_loss": 40.0},
      "spawn_waves_enabled": true,
      "global_population_limit": 128,
      "required_region_count": 2,
      "legacy_evolution_enabled": false
    },
    "region_assignment": "position_in_bounds",
    "notes": []
  },
  "map": {
    "coordinate_system": "ue_world_cm_z_up",
    "bounds_kind": "region_union",
    "bounds": {"min_x_cm": -1500.0, "min_y_cm": -1500.0, "max_x_cm": 5500.0, "max_y_cm": 1500.0},
    "boundary": null,
    "regions": [
      {
        "region_id": "Forest_A",
        "transform": {"location_cm": {"x": 0.0, "y": 0.0, "z": 100.0},
                      "rotation_deg": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
                      "scale": {"x": 1.0, "y": 1.0, "z": 1.0}},
        "extent_unscaled_cm": {"x": 1500.0, "y": 1500.0, "z": 1000.0},
        "aabb_cm": {"min_x": -1500.0, "min_y": -1500.0, "max_x": 1500.0, "max_y": 1500.0},
        "arrival_point_cm": {"x": 0.0, "y": 0.0, "z": 100.0},
        "adjacent_region_ids": ["Forest_B"],
        "initial_food_amount": 1000.0,
        "food_capacity": 2000.0
      },
      {
        "region_id": "Forest_B",
        "transform": {"location_cm": {"x": 4000.0, "y": 0.0, "z": 100.0},
                      "rotation_deg": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
                      "scale": {"x": 1.0, "y": 1.0, "z": 1.0}},
        "extent_unscaled_cm": {"x": 1500.0, "y": 1500.0, "z": 1000.0},
        "aabb_cm": {"min_x": 2500.0, "min_y": -1500.0, "max_x": 5500.0, "max_y": 1500.0},
        "arrival_point_cm": {"x": 4000.0, "y": 0.0, "z": 100.0},
        "adjacent_region_ids": ["Forest_A"],
        "initial_food_amount": 1000.0,
        "food_capacity": 2000.0
      }
    ],
    "covers_source": "none",
    "covers": null,
    "water": null,
    "obstacles": null
  },
  "food": {
    "regions": [
      {
        "region_id": "Forest_A",
        "food_amount": {"start": 1000.0, "end": 0.0, "mean": 468.3, "min": 0.0, "max": 1000.0},
        "cap0_total": 2000.0,
        "food_capacity": {"start": 2000.0, "end": 2000.0, "mean": 2000.0, "min": 2000.0, "max": 2000.0},
        "food_ratio": {"start": 0.5, "end": 0.0, "mean": 0.23415, "min": 0.0},
        "vegetation_total": null,
        "consumed_total": 1000.0,
        "event_loss_total": 0.0,
        "rounding_adjustment_total": 0.0,
        "regenerated_total": 0.0,
        "depleted_time_frac": 0.06667,
        "below_epsilon_time_frac": 0.06667,
        "depletion_events": 1,
        "feed_grants": 1000,
        "consumption_pressure_per_s": 0.0008333,
        "regeneration_rate_per_s": null,
        "regeneration_model": "none",
        "recovery_half_life_s": null
      },
      {
        "region_id": "Forest_B",
        "food_amount": {"start": 1000.0, "end": 0.0, "mean": 213.5, "min": 0.0, "max": 1000.0},
        "cap0_total": 2000.0,
        "food_capacity": {"start": 2000.0, "end": 2000.0, "mean": 2000.0, "min": 2000.0, "max": 2000.0},
        "food_ratio": {"start": 0.5, "end": 0.0, "mean": 0.10675, "min": 0.0},
        "vegetation_total": null,
        "consumed_total": 340.0,
        "event_loss_total": 660.0,
        "rounding_adjustment_total": 0.0,
        "regenerated_total": 0.0,
        "depleted_time_frac": 0.44583,
        "below_epsilon_time_frac": 0.44583,
        "depletion_events": 1,
        "feed_grants": 340,
        "consumption_pressure_per_s": 0.0002833,
        "regeneration_rate_per_s": null,
        "regeneration_model": "none",
        "recovery_half_life_s": null
      }
    ],
    "grid_update_interval_s": null,
    "present_area_frac": null,
    "policy_food_provider": null
  },
  "threat": {
    "predators": null,
    "predation": null,
    "region_risk": [
      {"region_id": "Forest_A", "predation_history": null},
      {"region_id": "Forest_B", "predation_history": null}
    ],
    "player": {
      "player_count": {"mean": 1.0, "max": 1},
      "presence_by_region": null,
      "presence_outside_s": null,
      "near_herd_seconds": null,
      "approach_speed_hist": null,
      "kills": null
    }
  },
  "population": {
    "regions": [
      {
        "region_id": "Forest_A",
        "population": {"start": 4, "end": 15, "mean": 8.6, "min": 4, "max": 15},
        "traveling_mean": 0.0,
        "waiting_mean": 1.0,
        "average_energy_mean": null,
        "spawned_total": 3,
        "spawn_waves_skipped": 2,
        "departures": 0,
        "arrivals": 8,
        "return_arrivals": 0,
        "retargets": 0,
        "deaths": null,
        "lifespan": {"completed_count": null, "completed_mean_in_window_s": null,
                     "censored_count": 15, "censored_mean_in_window_s": 301.7, "censored_mean_age_s": 301.7}
      },
      {
        "region_id": "Forest_B",
        "population": {"start": 4, "end": 0, "mean": 3.5, "min": 0, "max": 8},
        "traveling_mean": 0.16,
        "waiting_mean": 0.0,
        "average_energy_mean": null,
        "spawned_total": 4,
        "spawn_waves_skipped": 6,
        "departures": 8,
        "arrivals": 0,
        "return_arrivals": 0,
        "retargets": 0,
        "deaths": null,
        "lifespan": {"completed_count": null, "completed_mean_in_window_s": null,
                     "censored_count": 0, "censored_mean_in_window_s": null, "censored_mean_age_s": null}
      }
    ],
    "migration_matrix": [{"from_region_id": "Forest_B", "to_region_id": "Forest_A", "count": 8}],
    "policy_test": null
  },
  "time_weather": {
    "clock_running": true,
    "day_duration_s": 10.0,
    "night_duration_s": 10.0,
    "day_fraction": 0.5,
    "cycles_in_window": 30.0,
    "phase_at_start": {"phase": "day", "cycle_id": 0, "elapsed_in_phase_s": 0.0},
    "twilight": null,
    "weather": null
  },
  "policy_outcome": null,
  "missing": {
    "meta.build_id": {"reason": "NOT_IMPLEMENTED"},
    "meta.policy.learned_frac": {"reason": "NOT_IN_LEVEL"},
    "meta.window.policy_step_boundaries": {"reason": "NOT_IN_LEVEL"},
    "meta.window.policy_multi_step_frames": {"reason": "NOT_IN_LEVEL"},
    "map.boundary": {"reason": "NOT_IN_LEVEL"},
    "map.covers": {"reason": "NOT_IN_LEVEL"},
    "map.water": {"reason": "NOT_IMPLEMENTED", "note": "담당 없음(계획:420)"},
    "map.obstacles": {"reason": "NOT_IMPLEMENTED", "owner": "World(미정)"},
    "food.regions[*].vegetation_total": {"reason": "NOT_IMPLEMENTED", "owner": "wonkii", "note": "#20 격자 장부"},
    "food.regions[*].regeneration_rate_per_s": {"reason": "NOT_DRIVEN", "raw_value": 0.0, "owner": "wonkii"},
    "food.regions[*].recovery_half_life_s": {"reason": "NOT_IMPLEMENTED", "owner": "wonkii", "note": "#20"},
    "food.grid_update_interval_s": {"reason": "NOT_IMPLEMENTED", "owner": "wonkii"},
    "food.present_area_frac": {"reason": "NOT_IMPLEMENTED", "note": "#20 전에는 섭식이 위치와 무관하다"},
    "food.policy_food_provider": {"reason": "NOT_IN_LEVEL"},
    "threat.predators": {"reason": "NOT_IN_LEVEL", "owner": "wonkii, 팀", "note": "계획:417"},
    "threat.predation": {"reason": "NOT_IN_LEVEL"},
    "threat.region_risk[*].predation_history": {"reason": "NOT_DRIVEN", "raw_value": 0.0, "owner": "wonkii, 조연우"},
    "threat.player.presence_by_region": {"reason": "DEFERRED"},
    "threat.player.presence_outside_s": {"reason": "DEFERRED"},
    "threat.player.near_herd_seconds": {"reason": "DEFERRED"},
    "threat.player.approach_speed_hist": {"reason": "DEFERRED"},
    "threat.player.kills": {"reason": "NOT_IMPLEMENTED", "owner": "wonkii, 조연우"},
    "population.regions[*].average_energy_mean": {"reason": "NOT_DRIVEN", "raw_value": 1.0, "owner": "wonkii",
                                                  "note": "Energy 대사 없음. 빈 지역 표본은 뺐다"},
    "population.regions[*].deaths": {"reason": "NOT_IMPLEMENTED", "owner": "wonkii"},
    "population.regions[*].lifespan.completed_count": {"reason": "NOT_IMPLEMENTED", "owner": "wonkii"},
    "population.regions[*].lifespan.completed_mean_in_window_s": {"reason": "NOT_IMPLEMENTED", "owner": "wonkii"},
    "population.regions[Forest_B].lifespan.censored_mean_in_window_s": {"reason": "NO_SAMPLES"},
    "population.regions[Forest_B].lifespan.censored_mean_age_s": {"reason": "NO_SAMPLES"},
    "population.policy_test": {"reason": "NOT_IN_LEVEL"},
    "time_weather.twilight": {"reason": "NOT_IMPLEMENTED"},
    "time_weather.weather": {"reason": "NOT_DRIVEN", "raw_value": "Clear", "owner": "World(미정)"},
    "policy_outcome": {"reason": "NOT_IN_LEVEL"}
  }
}
```

예시 숫자는 서로 맞게 정했다.
- 먹이 보존식(9.1): A는 1000 − 1000 − 0 − 0 + 0 = 0, B는 1000 − 340 − 660 − 0 + 0 = 0이다.
- B의 밤 먹이 이벤트는 밤마다 40씩이다. 16번째 밤까지 640, 17번째 밤(시각 332.5초)에 남은 20을 잃고 고갈된다. 그래서 고갈 시간 비율은 (600 − 332.5) ÷ 600 = 0.44583이다. A는 560초에 고갈되어 0.06667이다.
- 개체: A는 4 + 3 + 8 = 15, B는 4 + 4 − 8 = 0이다. 이동 중 개체는 도착 commit 전까지 출발 지역(B)에 속한다.
- `waiting_mean`: A의 15마리가 마지막 40초 동안 기다렸다. 15 × 40 ÷ 600 = 1.0이다. `traveling_mean`: B의 8마리가 12초 이동했다. 8 × 12 ÷ 600 = 0.16이다.
- 스텝: 2432 − 1 = 2431이다. 1초 표본은 0초부터 599초까지 600개다.
- 하루: 20초씩 30일 = 600초다. 600초가 31번째 낮의 시작이라 그 시각에 창을 닫았다.
- 소비 압력: A는 1000 ÷ 600 ÷ 2000 = 0.0008333/s, B는 340 ÷ 600 ÷ 2000 = 0.0002833/s다.
- 접속자가 1명이라 6.7절 억제 대상이지만, 억제할 분포 필드가 이미 null이다.

### 7.2 `L_EcoPolicyTest` 창
```json
{
  "meta": {
    "season_export_schema_version": 1,
    "season_id": 3,
    "export_session_id": "C07D4B19-2E8A-4D35-B6F1-7A90E3C2D4B8",
    "window_index": 0,
    "world_epoch": 902114453,
    "match_instance_id": "1D2E3F40-5A6B-4C7D-8E9F-A0B1C2D3E4F5",
    "level_name": "L_EcoPolicyTest",
    "map_package_name": "/Game/EcoTest/UEDPIE_0_L_EcoPolicyTest",
    "net_mode": "standalone",
    "written_utc": "2026-10-20T07:03:10Z",
    "engine_version": "5.8.3",
    "build_id": null,
    "window": {
      "boundary_kind": "elapsed_seconds",
      "complete": true,
      "time_source": "policy_step_clock",
      "start_server_time_s": 0.0,
      "end_server_time_s": 600.0,
      "duration_s": 600.0,
      "start_step_id": null,
      "end_step_id": null,
      "start_cycle_id": null,
      "end_cycle_id": null,
      "ecology_steps": null,
      "summary_samples": null,
      "policy_step_boundaries": 4500,
      "policy_multi_step_frames": 3
    },
    "systems": {
      "m3_population": false, "world_clock": false, "policy_inference": true,
      "predators": true, "predation_report": true, "player_report": false,
      "food_regeneration": false, "food_grid": false, "weather_server": false,
      "water": false, "energy_metabolism": false, "death_lifecycle": false
    },
    "policy": {
      "policy_schema_version": 1,
      "controller": "learned",
      "learned_frac": 1.0,
      "weights_id": "crc32:3A9F04C1",
      "predation_check_cadence": "per_frame"
    },
    "constants": {
      "grid_unit_cm": 200.0, "policy_interval": 8, "see_radius_cm": 4000.0, "herb_speed_cm_s": 900.0,
      "max_energy": 1.0, "obs_pred_count_norm": 8.0, "obs_kin_count_norm": 20.0, "obs_cover_norm_cm": 4000.0,
      "fov_deg": 120.0, "sep_weight": 1.35, "sep_radius_cm": 1000.0, "flee_weight": 3.0,
      "predation_ema_decay": 0.95, "predation_ema_gain": 10.0, "step_seconds": 0.1333333,
      "pred_view_radius_cm": 2800.0, "pred_fov_deg": 150.0, "pred_catch_radius_cm": 200.0,
      "pred_eat_cooldown_s": 0.6666667, "pred_wander_turn_rad": 0.15, "cover_hide_mult": 2.5,
      "init_energy_frac": 0.5
    },
    "runtime_settings": {
      "day_duration_s": 10.0,
      "night_duration_s": 10.0,
      "feeding": {"enabled": true, "first_delay_s": 5.0, "interval_s": 5.0, "amount": 1.0},
      "migration": {"enabled": true, "decision_interval_s": 1.0, "speed_cm_s": 400.0,
                    "arrival_radius_cm": 30.0, "arrival_spread_cm": 300.0, "food_epsilon": 0.0001},
      "day_food_event": {"enabled": false, "region_id": "Forest_A", "phase_fraction": 0.4166667, "food_loss": 40.0},
      "night_food_event": {"enabled": true, "region_id": "Forest_B", "phase_fraction": 0.25, "food_loss": 40.0},
      "spawn_waves_enabled": true,
      "global_population_limit": 128,
      "required_region_count": 2,
      "legacy_evolution_enabled": false
    },
    "region_assignment": "position_in_bounds",
    "notes": ["runtime_settings 는 프로젝트 설정값이다. 이 레벨에서는 M3 조정자가 돌지 않는다"]
  },
  "map": {
    "coordinate_system": "ue_world_cm_z_up",
    "bounds_kind": "policy_world_extent",
    "bounds": {"min_x_cm": -15000.0, "min_y_cm": -15000.0, "max_x_cm": 15000.0, "max_y_cm": 15000.0},
    "boundary": {"extent_cm": 15000.0, "margin_cm": 1000.0, "push_weight": 2.0, "clamp": true},
    "regions": null,
    "covers_source": "policy_dummy",
    "covers": [
      {"x_cm": 6750.0, "y_cm": 6750.0, "radius_cm": 2500.0},
      {"x_cm": -6750.0, "y_cm": 6750.0, "radius_cm": 2500.0},
      {"x_cm": 6750.0, "y_cm": -6750.0, "radius_cm": 2500.0},
      {"x_cm": -6750.0, "y_cm": -6750.0, "radius_cm": 2500.0}
    ],
    "water": null,
    "obstacles": null
  },
  "food": {
    "regions": null,
    "grid_update_interval_s": null,
    "present_area_frac": null,
    "policy_food_provider": {
      "kind": "dummy_sine",
      "wavelength_cm": 6000.0,
      "threshold": 0.35,
      "cell_cm": 400.0,
      "consumption_enabled": false,
      "regen_per_s": null,
      "present_area_frac": 0.72
    }
  },
  "threat": {
    "predators": {
      "kinds": [
        {"kind": "melee", "species_label": "Predator.TestMelee", "count_mean": 5.0, "count_max": 5,
         "speed_cm_s": 900.0, "catch_radius_cm": 200.0, "view_radius_cm": 2800.0, "fov_deg": 150.0,
         "eat_cooldown_s": 0.6666667}
      ],
      "ranged_frac": 0.0,
      "by_region": null
    },
    "predation": {
      "deaths_total": 160,
      "exposure_alive_agent_s": 57600.0,
      "by_region": null,
      "by_phase": null,
      "prey_in_cover": 3,
      "ema": {"mean": 0.0037, "max": 0.021, "end": 0.0031}
    },
    "region_risk": null,
    "player": {
      "player_count": {"mean": 1.0, "max": 1},
      "presence_by_region": null,
      "presence_outside_s": null,
      "near_herd_seconds": null,
      "approach_speed_hist": null,
      "kills": null
    }
  },
  "population": {
    "regions": null,
    "migration_matrix": null,
    "policy_test": {
      "herbivore_count": 96,
      "alive_mean": 96.0,
      "respawns_total": 160,
      "spawn_radius_cm": 12000.0,
      "lifespan": null
    }
  },
  "time_weather": {
    "clock_running": false,
    "day_duration_s": null,
    "night_duration_s": null,
    "day_fraction": null,
    "cycles_in_window": null,
    "twilight": null,
    "weather": null
  },
  "policy_outcome": {
    "agent_policy_steps": 431712,
    "counts": {"pred_seen": 38854, "hungry": 103611, "in_cover": 30220},
    "action_mean": [0.62, 0.41, 0.55, 0.18],
    "action_std": [0.21, 0.17, 0.24, 0.15],
    "obs_mean": [0.30, 0.013, 0.964, 0.48, 0.55, 0.0037, 0.70],
    "obs_std": [0.17, 0.04, 0.12, 0.28, 0.24, 0.0021, 0.33],
    "pred_seen_frac": 0.09,
    "action_mean_pred_seen": [0.51, 0.47, 0.81, 0.33],
    "action_mean_pred_unseen": [0.63, 0.40, 0.52, 0.16],
    "forage_mean_hungry": 0.71,
    "forage_mean_full": 0.59,
    "cover_frac": 0.07,
    "predation_rate_per_step": 0.00037037,
    "starve_rate_per_step": null,
    "survival_mean_steps": null
  },
  "missing": {
    "meta.build_id": {"reason": "NOT_IMPLEMENTED"},
    "meta.window.start_step_id": {"reason": "NOT_IN_LEVEL"},
    "meta.window.end_step_id": {"reason": "NOT_IN_LEVEL"},
    "meta.window.start_cycle_id": {"reason": "CLOCK_NOT_RUNNING"},
    "meta.window.end_cycle_id": {"reason": "CLOCK_NOT_RUNNING"},
    "meta.window.ecology_steps": {"reason": "NOT_IN_LEVEL"},
    "meta.window.summary_samples": {"reason": "NOT_IN_LEVEL"},
    "map.regions": {"reason": "NOT_IN_LEVEL"},
    "map.water": {"reason": "NOT_IMPLEMENTED", "note": "담당 없음(계획:420)"},
    "map.obstacles": {"reason": "NOT_IMPLEMENTED", "owner": "World(미정)"},
    "food.regions": {"reason": "NOT_IN_LEVEL"},
    "food.grid_update_interval_s": {"reason": "NOT_IN_LEVEL"},
    "food.present_area_frac": {"reason": "NOT_IN_LEVEL", "note": "정책이 읽는 먹이는 policy_food_provider 에 있다"},
    "food.policy_food_provider.regen_per_s": {"reason": "NOT_DRIVEN", "raw_value": 0.02, "owner": "sinhyeok04",
                                              "note": "ConsumeFood·RegenerateConsumed 호출 0건"},
    "threat.predators.by_region": {"reason": "NOT_IN_LEVEL"},
    "threat.predation.by_region": {"reason": "NOT_IN_LEVEL"},
    "threat.predation.by_phase": {"reason": "CLOCK_NOT_RUNNING"},
    "threat.region_risk": {"reason": "NOT_IN_LEVEL"},
    "threat.player.presence_by_region": {"reason": "NOT_IN_LEVEL"},
    "threat.player.presence_outside_s": {"reason": "NOT_IN_LEVEL"},
    "threat.player.near_herd_seconds": {"reason": "DEFERRED"},
    "threat.player.approach_speed_hist": {"reason": "DEFERRED"},
    "threat.player.kills": {"reason": "NOT_IMPLEMENTED", "owner": "wonkii, 조연우"},
    "population.regions": {"reason": "NOT_IN_LEVEL"},
    "population.migration_matrix": {"reason": "NOT_IN_LEVEL"},
    "population.policy_test.lifespan": {"reason": "NOT_IMPLEMENTED", "owner": "sinhyeok04"},
    "time_weather.day_duration_s": {"reason": "CLOCK_NOT_RUNNING"},
    "time_weather.night_duration_s": {"reason": "CLOCK_NOT_RUNNING"},
    "time_weather.day_fraction": {"reason": "CLOCK_NOT_RUNNING"},
    "time_weather.cycles_in_window": {"reason": "CLOCK_NOT_RUNNING"},
    "time_weather.twilight": {"reason": "NOT_IMPLEMENTED"},
    "time_weather.weather": {"reason": "NOT_IN_LEVEL"},
    "policy_outcome.starve_rate_per_step": {"reason": "NOT_IMPLEMENTED", "owner": "wonkii"},
    "policy_outcome.survival_mean_steps": {"reason": "NOT_IMPLEMENTED", "owner": "sinhyeok04"}
  }
}
```

검산
- 시간: 4500 경계 × 0.1333 = 600초다.
- 노출: 리스폰이 같은 틱에 일어나 산 개체가 늘 96마리다. 96 × 600 = 57600 마리·s이고 `alive_mean` = 57600 ÷ 600 = 96이다.
- 결정 사건: 96 × 4500 = 432000에서, 한 프레임에 두 스텝이 지난 3프레임 동안 96마리가 결정을 한 번씩 놓쳐 288을 뺐다. 431712다.
- 피식률: 160 ÷ (57600 ÷ 0.1333) = 160 ÷ 432000 = 3.7037e-4다.
- EMA: 정상 상태 EMA는 10 × 스텝당 피식률 = 0.0037이다. `obs_mean[5]`도 같은 값이다.
- 조건부 평균: 0.09 × [0.51, 0.47, 0.81, 0.33] + 0.91 × [0.63, 0.40, 0.52, 0.16] ≈ [0.62, 0.41, 0.55, 0.18]다. 배고픔: 0.24 × 0.71 + 0.76 × 0.59 ≈ 0.62다.
- 비율: 38854 ÷ 431712 = 0.090, 103611 ÷ 431712 = 0.240, 30220 ÷ 431712 = 0.070이다.
- 은신처 위치: ±0.45 × 15000 = ±6750이다. 합집합 넓이 비율은 4 × π × 2500² ÷ 30000² ≈ 0.087이다(원이 겹치지 않는다).

---

## 8. 서버 쪽 구현 체크리스트

우선순위는 "지금 있는 값으로 v2.0 최소 파일을 쓰는 일"이 먼저다. 그 뒤는 버전 순서다.

### P0: 지금 있는 값으로 파일 쓰기
| # | 작업 | 위치 (제안) | 담당 | 채워지는 필드 |
|---|---|---|---|---|
| 0-1 | 내보내기 서브시스템 `UEcoSeasonExportSubsystem : UWorldSubsystem`을 만든다. 서버 전용 생성 가드를 두고, `Initialize`에서 `export_session_id`를 만든다. 정책 공급 함수 등록과 `CloseWindow` 호출 지점을 둔다(1.4) | `S/Ecology/EcoSeasonExportSubsystem.{h,cpp}`, 구조체 `S/Core/EcoSeasonTypes.h`. 생성 관례 `S/Ecology/EcologySimulationSubsystem.cpp:11-26` | 서버 담당 | `meta` 머리 |
| 0-2 | 설정 `bEnableSeasonExport`, `SeasonId`, `SeasonMinSeconds`(600)를 더한다. 명령줄로 `SeasonId`를 덮을 수 있게 한다(Q3) | `S/Core/EcoRuntimeSettings.h`, `G` | 서버 담당 | `meta.season_id`, 6.1 |
| 0-3 | 생태 스텝 시작 훅 (a0): 창 경계를 판정하고, 닫을 때 `end`, 열 때 `start`를 기록한다 | `S/Mass/EcoMassLifecycleSubsystem.cpp:293`과 `:294` 사이. t = 0 스텝(`:176`)도 지나간다 | 서버 담당 | `meta.window`, 모든 `start`·`end` |
| 0-4 | 생태 스텝 끝 훅 (a): `GetResourceSnapshots`(`S/Ecology/EcologySimulationSubsystem.h:108`)와 지역 상태(`GetRegionState`)를 복사해 합과 시간 가중 누적에 더한다. Before·After로 `regenerated_total`을 구한다 | `S/Mass/EcoMassLifecycleSubsystem.cpp:339` 다음 | 서버 담당 | `food.regions[]`, `population.regions[]`, `region_risk` |
| 0-5 | 1초 훅 (b): `summary_samples`, 접속자 수(`AEcoGameState::GetConnectedPlayerCount`) | `:334-338` 분기 안. `PublishCompletedSummary` 안이 아니다 | 서버 담당 | `summary_samples`, `threat.player.player_count` |
| 0-6 | 이주와 스폰을 센다. `EcoMassMigration::Reconcile`은 지금 bool만 돌려주므로(`S/Mass/EcoMassMigration.cpp:28-31`) 전이 계수를 받을 출력 인자를 더해야 한다. 이 함수의 시그니처 변경은 wonkii 님 합의 사항이다(Q19). 정의는 5.5절 departures·arrivals 행이다 | `S/Mass/EcoMassMigration.cpp:101-108, 116-127`, 호출 `S/Mass/EcoMassLifecycleSubsystem.cpp:329-331`, 스폰 `:305-311` | 서버 담당 | `departures`, `arrivals`, `return_arrivals`, `retargets`, `migration_matrix`, `spawned_total`, `spawn_waves_skipped` |
| 0-7 | 창을 닫을 때: 산 개체의 `FEcoLifetimeFragment.SpawnTimeSeconds`를 조회해 나이를 구하고, `map.regions[]`(`BuildSpatialSnapshots`, `S/World/EcologyWorldSubsystem.cpp:80-106`), `meta.runtime_settings`, `time_weather`를 채운다. 0-3 안에서 닫으므로 Mass가 처리 중이 아니다(`:293`) | 0-1과 같은 위치 | 서버 담당 | `lifespan.censored_*`, 5.1, 5.2, 5.6 |
| 0-8 | 파일을 쓴다. Build.cs에 `Json` 모듈을 더하고(`S/AdaptiveEcosystem.Build.cs:11-35`. 변환기를 쓸 때만 `JsonUtilities`), 백그라운드 `AsyncTask`, `ForceUTF8WithoutBOM`, `.tmp` 쓰기, 덮어쓰지 않는 이름 바꾸기, 로그 순서로 한다(3절) | 0-1과 같은 위치. 패턴 `S/Evolution/DummyEvolutionDecisionProvider.cpp:98-108` | 서버 담당 | 3절 |
| 0-9 | 콘솔 명령 `Eco.Season.Export`를 등록한다 | `S/Debug/EcoDebugCommandSubsystem.cpp:23-57` | 서버 담당 | `boundary_kind = "console"` |
| 0-10 | 정책 계층 집계기. (c)·(d)·(e) 표본 누적(double), 포획 수와 은신처 안 포획, 포식자 수, EMA, 컨트롤러 표본, 더미 Provider 읽기 함수, 스포너 값, 상수, 경계 반발 상수, 은신처 목록을 공급 함수로 넘긴다 | `P/EcoBehaviorProcessors.cpp:341-385, 437-449, 527-529, 543-546`, `P/EcoWorldProviders.h:112-125` | **우리** | `policy_outcome`, `threat.predators`, `threat.predation`, `map.covers`, `map.boundary`, `food.policy_food_provider`, `population.policy_test`, `meta.constants`, `meta.policy` |
| 0-11 | 가중치 식별자: 시작할 때 가중치 배열의 CRC32를 계산한다(5.1) | `P/` 정책 계층 | **우리** | `meta.policy.weights_id` |
| 0-12 | L_test 창 경계(`elapsed_seconds`)를 정하고 `CloseWindow`를 부른다 | `P/EcoBehaviorProcessors.cpp:543-546` | **우리** | 6.1 (2) |

### P1 이후 (버전 순서)
| 순위 | 버전 | 작업 | 담당 | 선행 | 채워지는 필드 |
|---|---|---|---|---|---|
| P1 | v2.0 | L_test 초식에 Lifetime Fragment를 더하고 리스폰 때 스폰 시각을 갱신한다 | 우리 | — | `policy_test.lifespan`, `survival_mean_steps` |
| P1 | v2.0 | 먹이 재생 재개와 용량 API | wonkii | 계획:414 | `regeneration_rate_per_s`, `regeneration_model`, `regenerated_total`이 0이 아니게 된다 |
| P2 | v2.1 | 에너지 대사, 아사, 사망 Lifecycle | wonkii | 계획:413 | `average_energy_mean`, `deaths`, `lifespan.completed_*`, `starve_rate_per_step` |
| P3 | v2.0b(v2.3 시점) | 지역 셀 격자 장부(F·V 2층, 셀 400 cm, 고정 간격 0.1333초 갱신) | wonkii | #20 합의(계획:435, 543). v2.0b 재설계(계획:520) | `food.grid`, `vegetation_total`, `cap0_total`(격자 합), `food_capacity`(ΣV), `grid_update_interval_s`, `recovery_half_life_s`, `present_area_frac` |
| P3 | v2.3 | `ReportPredation`이 위치와 원인을 받는다. 지역 귀속을 한다 | 우리(위치·원인 인자), wonkii(지역 귀속) | 6.4 규칙 합의 | `threat.predation.by_region` |
| P3 | v2.3 | `PredationHistory` 활성화와 감쇠식 계약 | wonkii, 조연우 | 계획:418, 434, Q10 | `threat.region_risk` |
| P3 | v2.3 | 플레이어 체류·근처 시간·속력 집계(원천 있음) | 서버 담당 | 0-5 | `threat.player.presence_*`, `near_herd_seconds`, `approach_speed_hist` |
| P3 | v2.3 | 플레이어 사냥 보고(M4 Player Kill) | wonkii, 조연우 | 계획:422, #15(계획:538) | `threat.player.kills.*` |
| P3 | v2.3 | M3 레벨 포식자 종 | wonkii, 팀 | 계획:417 | `threat.predators.by_region` |
| P3 | v2.3 | 지역 시간 계열 | 서버 담당 | 0-5 | `series` |
| P4 | v2.4 | 테스트 레벨 위상원, 하루 길이 900스텝(60/60초) 고정 | wonkii, 팀, 우리 | 계획:419, 437, #21(계획:544) | `threat.predation.by_phase`, L_test의 `time_weather.*` |
| P5 | v2.5a·b | 지역별 재생률, 소속 규칙 확정 | wonkii | 계획:416, 436, #23·#24(계획:546-547) | 재생비, 이주 필드의 의미 |
| P6 | v2.6 | 날씨 서버 갱신과 스냅샷 경로 | World 담당(미정) | 계획:420, 438 | `time_weather.weather` |
| P7 | v2.8 / R1 | 물 지점, 원형 장애물 스냅샷 | 물은 담당 없음 / 장애물은 World 스냅샷 미정, 반발항 우리 | 계획:420, 421, 438, #26(계획:549) | `map.water`, `map.obstacles` |

**게임 스레드 비용 (추정)**
- 0-3~0-5는 지역 수(지금 2개)에 비례하는 상수 작업이다.
- 0-6은 이미 도는 이주 루프 안에서 하는 정수 덧셈이다.
- 0-7은 창마다 한 번 하는 Mass 조회다(128마리 이하).
- 0-10은 정책 처리기가 이미 도는 개체 루프 안에서 하는 덧셈과 `IsInCover` 한 번이다(은신처 4개).
- 직렬화와 쓰기는 백그라운드에서 한다.

---

## 9. 파이썬 쪽이 하는 일 (참고)

이 절은 서버 담당이 구현할 것이 아니다. 받은 값이 어디에 쓰이는지 보이려고 적는다. 도구 이름은 제안이다.

### 9.1 받기, 검사, 창 합치기
**검사**
1. `season_export_schema_version`이 다르면 거부한다.
2. `meta.constants`를 단위 변환한 뒤 `H/configs/default.yaml`과 비교한다(예: `see_radius_cm ÷ grid_unit_cm = see_r`). 상대 오차 1e-6(float32 유효숫자)을 넘으면 거부한다.
3. 먹이 보존식: `end = start − consumed_total − event_loss_total − rounding_adjustment_total + regenerated_total`. 허용 오차는 1e-3 × `cap0_total`이다(제안). 여기서 `start`는 창 첫 스텝의 장부 Before다(6.1).
4. `duration_s = end − start`, 횟수 ≥ 0, `missing`과 null이 서로 맞는지 확인한다(6.5).
5. `complete = false`나 `system_failed` 창은 보고만 하고 설정에는 넣지 않는다(제안).

**창 합치기 키**: (`season_id`, `level_name`, 맵 구성 해시). 해시는 파이썬이 `map` 블록(bounds, regions의 변환·반폭·인접, covers)으로 계산한다. 서버는 할 일이 없다. 레벨이나 맵이 다른 파일은 섞지 않는다.

**필드별 합치기 규칙**
| 종류 | 규칙 |
|---|---|
| `…_total`, 횟수, 히스토그램 `counts`, `exposure_alive_agent_s`, `agent_policy_steps`, `counts{}` | 합 |
| 시간 가중 `mean`, `…_time_frac`, `traveling_mean`·`waiting_mean` | `duration_s` 가중 평균 |
| `average_energy_mean` | Σ(값 × `population.mean` × `duration_s`) ÷ Σ(`population.mean` × `duration_s`) |
| `start` / `end` | 시간 순서로 첫 창의 `start` / 마지막 창의 `end` |
| `min` / `max` | 최솟값 / 최댓값 |
| 결정 사건 평균(`action_mean`, `obs_mean`) | `agent_policy_steps` 가중 평균 |
| 조건부 평균 | 해당 `counts`(예: `pred_seen`, `agent_policy_steps − pred_seen`) 가중 평균 |
| 표준편차 | 창마다 E[x²] = std² + mean²로 되돌려 가중 합친 뒤 √(E[x²] − E[x]²) |
| 비율(`pred_seen_frac`, `cover_frac`, 피식률) | 합친 분자 ÷ 합친 분모로 다시 계산한다 |
| 수명 | 창마다 6.2 정의로 구한 값을 (완료 수 + 진행 수)로 가중 평균한다(제안) |
| 9.2가 쓰는 `.end` 값 | `written_utc`가 가장 늦은 세션의 마지막 창 값 |

### 9.2 시뮬레이터 설정 만들기

#### 9.2.1 구성 규칙
- 시즌 설정 `configs/season_<id>.yaml`은 해당 버전 설정을 복사한 뒤 `overrides`와 기능 계수만 바꾼 파일이다. 지금 쓸 수 있는 버전 설정은 `H/configs/v2.yaml`이다. `H/configs/v2_0b.yaml`은 사용 금지 표시가 있고(`H/configs/v2_0b.yaml:8-11, 27`) v2.0b를 미뤘으므로(계획:520) 쓰지 않는다.
- 최상위 키는 `version`, `overrides`, `features`, `train`뿐이다(`H/env_v2/config.py:23`).
- `overrides`는 v1 키만 덮는다. 모르는 키는 거부된다(`H/env_v2/config.py:44-46`). V2 계수(`food_v` 등)는 `features.<기능>` 아래에 둔다.
- `overrides`는 얕게 덮인다(`:47`). 그래서 `rand`를 덮을 때는 키 6개를 모두 쓴다.
- 기능을 켜면 그 기능의 계수를 모두 적어야 한다(`H/env_v2/features.py:197-201`).
- **아래 표에 없는 키는 `default.yaml`과 버전 설정의 값을 그대로 쓴다.**

#### 9.2.2 대응 표
**`overrides` (v1 키, `H/configs/default.yaml`)**
| 시뮬레이터 키 | 게임 필드 | 식 | 값이 없을 때 / 게임 값 처리 |
|---|---|---|---|
| `rand.world_size` | `map.bounds`, 개체 수 | (a) 넓이 보존 s = √(W·H) ÷ 200 또는 (b) 밀도 보존 s = √(N ÷ ρ), ρ = 평균 초식 수 ÷ (W·H ÷ 200²). 어느 쪽인지는 Q21. L_test는 (a) 150 u, (b) 173.2 u이고, 7.1 예시 M3는 (a) 22.9 u다. 모두 학습 범위 [60, 110] 밖이다 | 기본 범위. 범위 밖이면 보고서에 적는다 |
| `rand.predator_count` | `threat.predators.kinds[].count_mean` | 반올림한 값 m으로 [m, m] | `NOT_IN_LEVEL`(M3): 같은 시즌 L_test 파일에서 가져온다. 없으면 기본 [2, 12] |
| `rand.pred_speed_mult` | `speed_cm_s` | ÷ 900 | 기본 범위 |
| `rand.ranged_frac` | `threat.predators.ranged_frac` | 그대로 | 기본 범위 |
| `rand.cover_frac` | `map.covers` | 원의 합집합 넓이 ÷ 맵 넓이(L_test 약 0.087) | 기본 범위 |
| `rand.food_regen_mult` | `regeneration_rate_per_s` G, `cap0_total` C | 선형 재생이면 t½ = C ÷ (2G), r = 1 − 2^(−0.1333 ÷ t½), mult = r ÷ 0.026(`H/configs/default.yaml:40`) | `NOT_DRIVEN`(raw 0): 재현하지 않는다. 재생 0 세계는 먹이가 영구히 고갈되는 세계라 학습 분포 밖이다. 기본 범위를 두고 보고서에 적는다 |
| `cover_r_min`, `cover_r_max` | `map.covers[].radius_cm` | ÷ 200(2500 → 12.5 u, 학습 4~9 밖) | 기본값 |
| `food_patch_threshold` | `food.present_area_frac`(#20 뒤) | 시드 표본으로 cap0 > 0 셀 비율이 맞는 문턱을 찾는다(방법은 우리가 정한다) | 기본 0.60 |
| `N` | 개체 수 | Q21: 128로 고정하고 (b)로 넓이를 맞추거나, 개체 수로 덮는다 | 128 |

**`features.<기능>` (V2 계수. 구현된 기능만 켤 수 있다)**
| 기능(버전) | 계수 | 게임 필드 | 식 | 상태 |
|---|---|---|---|---|
| `food_v`(v2.0b) | `init_frac`, `recovery_half_lives`, `alpha`, `floor` | `vegetation_total.end ÷ cap0_total`, `recovery_half_life_s` | `init_frac` 하한은 max(`floor`, `food_ratio.end`)로 자른다(World 검사 `H/env_v2/world.py:70-71`). `alpha`·`floor`는 게임 필드로 정하지 않는다. Gate F 보정값을 쓰고, 정해지기 전에는 시즌 학습에 이 기능을 켜지 않는다 | 지금은 켜지 않는다(v2.0b 연기, 계획:520) |
| v2.3 지역·기억(미구현) | 지역 포식자 M_r, m_r 초기값, 기억 반감기, 이득 g, 압력 전환 간격 | `threat.predators.by_region`, `region_risk[].predation_history.end`, `series` | M_r = 지역별 `count_mean`. 압력 전환 간격 = 고압 지역이 바뀌는 평균 간격 ÷ 0.1333. m_r 초기값은 Q10 계약 뒤 환산. g는 파이썬 보정값(계획:174) | 기능 구현 뒤 |
| v2.3 플레이어형 위협(#15) | 속력 배수, 포획 거리, 등장 지역·일정 | `threat.player.*` | 속력 ÷ 900, 거리 ÷ 200, 지역 체류 비율 | 기능 구현 뒤. 값이 없으면 기능을 끈다 |
| v2.4 낮밤 | 주기 T | `day_duration_s + night_duration_s` | ÷ 0.1333 | 학습 {600, 900, 1800}. 20초(150스텝)는 범위 밖이라 보고서에 적는다 |
| v2.5a 지역 환경 | 재생비 R_A:R_B, 지역 틈 | 지역별 재생률, `aabb_cm` | 비율, 거리 ÷ 200 | 기본 범위(1:1~1:4, 0~5 u) |
| v2.5b 이주 | 안전망 ε | `migration.food_epsilon ÷ cap0_total` | 비율 | 기본 |
| v2.6 비 | 맑음·비 평균 지속, 가뭄 | `rain_spells`, `clear_spells` | `mean_duration_s ÷ 0.1333` | 기본 1500, 400스텝 |
| v2.8 물 | 웅덩이 수, 포식자 물가 편향 | `map.water` | 개수. 물가 편향은 게임 원천이 없다 | 기본 범위(2~4개, 편향 0~1) |
| R1 | 경계 반발 상수, 장애물 개수·반경·면적 | `map.boundary`, `map.obstacles` | 상수 그대로, 면적 비율 | 기본 |

#### 9.2.3 게임에 원천이 있어도 쓰지 않는 값, 위치 정보의 처리
| 대상 | 처리와 이유 |
|---|---|
| 에너지 계수(`init_energy`, `energy_drain`, `max_energy`) | 기본값. 게임 Energy가 변하지 않는다 |
| 섭식(`food_eat_rate`, `food_energy_per_unit`) | 기본값. 게임 섭식은 위치·행동과 무관한 시간표(5초마다 1.0)다(계획:413). 소비 압력도 크게 다르다: 시뮬레이터 대사 수요는 128 × 0.002 ÷ 0.5 = 0.512/스텝, 평가 시드 Σcap0 평균 120.8에 대해 약 3.2%/s이고, 7.1 예시 A는 0.083%/s다. 그래서 소비 압력은 재현하지 않고, `food_ratio` 비교는 참고로만 본다 |
| 번식(`repro_threshold`, `repro_cd`) | 기본값. 게임에 번식이 없다(계획 #14) |
| 원거리형(`pred_ranged_*`) | 기본값. 게임에 원거리형이 없다 |
| 포식자 규칙 상수(`pred_view_r`, `pred_eat_cd`, `pred_wander_turn` 등) | 덮지 않는다. `meta.constants` 일치 검사로만 쓴다 |
| `food_cover_regen_mult`, `food_grad_blur`, `food_patch_blur`, `cover_max_count`, `train_seeds`, `eval_seeds` | 기본값. 게임 대응값이 없거나 파이썬 전용이다 |
| 스폰 웨이브, 밤 스폰, 밤 먹이 이벤트 | 학습에 없다(파이썬은 총 개체 수 고정, 계획:437). 학습 분포 밖이라고 보고서에 적는다 |
| 은신처 위치 | 버린다. `cover_frac`과 반경만 쓴다. World는 은신처 중심을 무작위로 뽑는다(`H/env_v2/world.py:156-169`). 10-02 검증용 임시 측정에서 게임 관측 6 평균 0.699 대 변환 시뮬레이터 0.727, 은신처 안 비율 0.088 대 0.104로 통계는 대체로 맞았다(추정). 네 모서리 배치 같은 구조는 사라진다 |
| cap0 지도(`food.grid`) | 버린다. `present_area_frac`으로 문턱만 맞춘다. 지도를 넣으려면 World 확장이 필요하다(제안 이름 `food_cap_map`, 담당 sinhyeok04, v2.3 이후) |
| 초기 먹이 F | World는 F = cap0(v2.0)이나 F = min(cap0, V)(v2.0b)로 시작한다(`H/env_v2/world.py:150-151, 224`). 게임의 `food_ratio.end`를 시작 상태로 넣으려면 World 확장이 필요하다(제안 `food_f_init_frac`, 담당 sinhyeok04) |
| 지역별 V 초기 비율 | World는 두 절반의 비율을 같은 `init_frac` 범위에서 따로 뽑는다(`H/env_v2/world.py:218, 222`). 지역별로 다른 값을 지정할 수 없다. 필요하면 World 확장 `init_frac_left/right`(제안, sinhyeok04)를 선행 작업으로 둔다 |
| 도착점 | 시뮬레이터 규칙(지역 중심 + 1.5 u 원판, 계획:231)이 따로 있어 쓰지 않는다 |
| 물, 장애물 위치 | 개수·반경·면적 비율로만 쓴다 |

#### 9.2.4 좌표 대응 (제안)
- 직사각형 경계 W × H를 정방형 한 변 s로 옮길 때 축별로 비례시킨다: x_u = (X − min_x) ÷ W × s, y_u = (Y − min_y) ÷ H × s. 넓이를 보존하는 정방형에 원래 비율 그대로 좌표를 넣으면 긴 변 쪽 위치가 맵 밖으로 나간다. 7.1 예시에서 경계는 35 × 15 u이고 넓이 보존 한 변은 22.9 u인데, Forest_B 중심은 (27.5, 7.5) u라 밖이다.
- 지역 정렬: 두 지역 중심의 차가 큰 축을 시뮬레이터 x축으로 본다. 그 축 좌표가 작은 지역이 왼쪽 절반(x < s/2, `H/env_v2/world.py:202-204`)이다.
- 게임 상자는 맵 가운데에서 나뉘지 않을 수 있어 이 대응은 근사다. 틈과 간격은 9.2.2의 v2.5a 행으로 따로 맞춘다.

**기타**
- 점값보다 범위로 둔다(제안). 측정값 ±20%로 둔다. 점값 하나로만 학습하면 그 세계에 과적합될 수 있다(추정).
- 학습 범위 밖의 값은 목록으로 만들어 `season_<id>_report.json`에 적는다. 예: 하루 20초, 은신처 반경 2500, 맵 300 m, 밤 먹이 손실 이벤트, 재생 0.

### 9.3 재현 확인 기준 (제안)
**방법**
- 게임과 같은 가중치(`weights_id`)로 9.2의 설정을 돌린다. 평가 시드 20개 × 5000스텝으로, v1 진단 규약(계획:62)과 같다.
- 시뮬레이터 지표와 `policy_outcome`·`threat.predation`을 비교한다.
- 각 지표는 아래 허용 오차 안에 들거나, 시뮬레이터의 시드별 [최소, 최대] 범위 안에 들면 통과다.

| 지표 | 통과 기준 (제안) | 비고 |
|---|---|---|
| `obs_mean[1, 2, 3, 6]` | \|Δ\| ≤ 0.10 | 입력 분포가 맞는지 먼저 본다 |
| `obs_mean[0]`, `obs_mean[4]` | 판정하지 않는다(L_test) | 아래 "L_test의 한계" |
| `obs_mean[5]` | 판정하지 않는다 | 값이 작아 \|Δ\|가 의미가 없다. `predation_rate`로 대신 본다 |
| `pred_seen_frac` | 시뮬레이터 ÷ 게임 = 0.67~1.5 | |
| `cover_frac` | \|Δ\| ≤ 0.10 | |
| `predation_rate` | 비율 0.5~2.0 | 게임 사망이 30건 이상일 때만 판정한다. 포획 판정 주기(`per_frame`)를 같이 적는다 |
| `action_mean[i]`, `action_std[2]`, `react_pred` | \|Δ\| ≤ 0.05. **L_test에서는 참고로만 본다** | 아래 "L_test의 한계" |
| `food_ratio.mean` | \|Δ\| ≤ 0.15, 참고로만 본다 | 소비 압력을 재현하지 않으므로(9.2.3) |
| `react_hunger`, `starve_rate`, `survival` | 게임 값이 null이거나 에너지가 변하지 않으면 판정하지 않는다 | v2.1부터. `react_hunger`는 게임이 결정 시점의 관측 4로, 파이썬은 섭식·번식 뒤 에너지로 판정한다(`H/env_v2/world.py:437-450, 676`, v1 `H/env/world.py:526`). v2.1 판정 전에 파이썬 정의를 관측 4 기준으로 맞춘다(우리) |

**L_test의 한계**
- 정책 성적이 나오는 레벨은 지금 L_test 하나다. 여기서 관측 0(먹이)과 관측 4(에너지)는 구조적으로 맞출 수 없다.
  - 먹이: 더미 사인 격자는 소비·회복 경로가 불리지 않아 고정 지형이다. raw 먹이 > 0인 넓이 비율이 약 0.72, 관측 0 평균이 약 0.30이다(10-02 표본 추정). 시뮬레이터는 보정 기록의 관측 0 평균이 0.051이다(`H/results/v2/diag_final/calib.json`). 차이 약 0.25는 허용 오차 0.10을 넘고, 9.2에 이것을 맞출 손잡이가 없다.
  - 에너지: 게임은 U[20,100]/100과 리스폰 0.5에서 바뀌지 않는다. 시뮬레이터는 스텝마다 0.002씩 줄고(`H/configs/default.yaml:16`) 보정 기록의 평균이 0.69다.
- 입력 둘이 다르면 행동도 달라지므로, L_test에서는 행동 지표를 판정하지 않고 참고로 적는다. 파이썬·C++ 사이 수치 파리티는 골든 벡터 테스트로 따로 확인한다(AGENTS §2.5).
- 행동까지 판정하려면 둘 중 하나가 선행 작업이다(Q22, 담당 sinhyeok04): (1) 시뮬레이터 World에 외부 먹이장(더미 사인 격자)과 고정 에너지를 넣는 확장 (2) 언리얼에 실제 먹이 Provider와 에너지 루프 연결(계획:98, 413).

**판정**
| 결과 | 조치 |
|---|---|
| 모두 통과 | 이어서 학습한다 |
| 관측 또는 위협 지표가 실패 | 세계 재현이 틀린 것이다. 학습하지 않고 9.2의 변환과 보정을 먼저 고친다 |
| 관측은 맞는데 행동만 실패(행동을 판정하는 레벨에서) | 같은 입력에 다른 출력이 나온 것이다. 파이썬과 C++ 사이 파리티 문제를 의심하고 골든 벡터 테스트를 다시 돌린다 |

### 9.4 반영
- 학습된 가중치로 `P/PolicyWeights.h`와 골든 벡터를 만든다(v1 7·4 정책은 `H/export_weights.py`).
- 그다음 `AdaptiveEcosystemEditor Win64 Development`를 빌드한다(AGENTS §3).
- 런타임 로딩이 없으므로 가중치를 바꾸려면 서버를 다시 빌드해야 한다.
- 새 가중치의 CRC가 다음 시즌 파일의 `meta.policy.weights_id`에 찍힌다.

---

## 10. 열린 질문과 합의할 항목

| # | 질문 | 이 문서의 제안 | 상대 |
|---|---|---|---|
| Q1 | 이 명세를 받는 서버 담당이 wonkii 님이 맞나 | 근거가 가장 많아 그렇게 추정했다 | wonkii |
| Q2 | 시즌 창 경계: 낮 시작 + `SeasonMinSeconds` 600초로 충분한가. 세션 종료 시점에 끝나지 않은 창을 쓸 것인가(`Ending` 전이가 없다) | 600초. 끝나지 않은 창은 버린다 | wonkii |
| Q3 | `season_id`는 누가 정하나. 운영 설정(ini, 명령줄)인가, 파이썬이 받은 순서인가 | 운영 설정. 0이면 파이썬이 정한다 | wonkii, 우리 |
| Q4 | 시즌 데이터는 어느 레벨에서 나오나. M3와 L_test가 겹치지 않는데 통합 레벨은 언제 생기나(계획:415) | 통합 전에는 두 레벨의 파일을 따로 받는다 | wonkii, 팀 |
| Q5 | 관측 6이 쓰는 "진짜" 은신처는 정책 더미 Provider인가, `AEcoShelterAnchor`인가. 반경(학습 800~1800 cm)과 게임 값(2500 / 300)이 맞지 않는다 | Shelter 앵커를 정책 Provider로 연결한다 | 조연우, 우리 |
| Q6 | 먹이 원천은 Ecology 지역 스칼라인가, 격자 장부(#20)인가. 문서끼리 충돌한다(`D/Architecture/ACTIVE_RUNTIME_BOUNDARIES.md:42` 대 `@main:D/조연우/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md:109-117`) | Ecology 소유 격자. 지역 총량은 격자 합에서 파생한다 | wonkii, 조연우 |
| Q7 | JSON 키: snake_case를 직접 쓸 것인가, `FJsonObjectConverter`의 camelCase를 받을 것인가 | snake_case를 직접 쓴다 | wonkii |
| Q8 | 플레이어 집계: 억제 기준 k = 3이 적당한가. 1인 세션의 창 단위 합계(체류, 사냥 수)도 지울 것인가. 구간 경계(거리, 속력, 방향)는 맞나 | k = 3. 분포·계열은 지우고 창 합계는 남긴다 | 팀, 조연우 |
| Q9 | 사건의 지역 귀속: 위치 포함 판정인가, 소속 Fragment인가 | 위치 포함 판정. 10-27 소속 결정(#23, #24)을 따른다 | wonkii |
| Q10 | `PredationHistory` 감쇠: 지금 0.05/s(반감기 약 13.9초)는 학습 τ(반감기 40~933초)와 다르다. 어느 식으로 통일하나 | 계약 V2의 기억식(계획:174)으로 맞춘다 | 조연우, wonkii |
| Q11 | M3에는 맵 경계가 없다. 지역 합집합 AABB로 충분한가, 레벨 경계 볼륨을 따로 둘 것인가 | 당분간 `region_union` | wonkii |
| Q12 | 시계가 없는 레벨의 창 길이를 정책 스텝 시계로 재도 되나 | 된다(`P/EcoPolicyClock.h`) | 우리 |
| Q13 | 서버 빌드 식별자(`build_id`)는 어떻게 얻나 | 확인 필요 | wonkii |
| Q14 | 파일 전달 경로: `Saved/`는 git 무시 대상이다. 공유 폴더로 할까 | 수동 전달로 시작한다 | 팀 |
| Q15 | 포획 판정이 아직 프레임마다 이루어진다. 정책 스텝 판정으로 바꿀 것인가 | 바꾼다(우리 몫. 피식률 비교가 정확해진다) | 우리 |
| Q16 | `EEcoWeatherState`의 Storm을 "비"에 넣나. Drought를 가뭄 배수 ×0.3과 대응시키나 | Rain + Storm = 비, Drought = 가뭄 | World 담당 |
| Q17 | 지금 하루 10/10초 설정을 시즌 운영에서도 유지하나. 학습은 900스텝(60/60초) 고정을 제안했다(#21) | 60/60으로 되돌린다 | wonkii, 팀 |
| Q18 | 이주 원인 분류(`FoodDepletion`, `PlayerThreat` 등)를 코드에 넣을 계획이 있나(지금 코드 0건) | 없으면 `migration_by_cause`는 선택으로 둔다 | wonkii |
| Q19 | 이주 계수를 위해 `EcoMassMigration::Reconcile`에 출력 인자를 더해도 되나 | 전이 계수 구조체 하나를 출력 인자로 더한다 | wonkii |
| Q20 | 플레이어 사냥을 `ReportPredation`으로 보낼 때 원인 인자(enum)를 계약에 넣을 것인가 | 넣는다. `P/` 쪽 변경은 우리가 한다 | 조연우, wonkii |
| Q21 | (파이썬) `world_size`를 넓이 보존과 밀도 보존 중 무엇으로 정하나. `N = 128` 고정을 유지하나 | 밀도 보존 + N 128 고정을 먼저 시험한다 | 우리 |
| Q22 | (파이썬) L_test의 관측 0·4 차이를 판정에서 뺄 것인가, 시뮬레이터에 더미 먹이장·고정 에너지 확장을 넣을 것인가 | 당분간 판정에서 뺀다 | 우리 |
| Q23 | `TickSimulation`, `ApplyPredationEvent`, `RecordPredationEvent`, `SetEnvironmentState`를 부르는 블루프린트가 Jang_lv 에셋에 있나 | 확인 필요. 있으면 해당 필드의 상태를 바꾼다 | wonkii, World 담당 |
| Q24 | L_test에서 `AEcoGameState`가 실제로 만들어지나 | PIE에서 확인한다 | 우리 |

---

## 부록. 검토 지적 가운데 반영하지 않은 것
| 지적 | 판단 |
|---|---|
| "중심 간격 30~55 u는 계획:229-230이 아니라 계획:187에 있다" | 반영하지 않았다. 계획:230에 "파이썬 지역 중심 간격은 맵 절반(30~55단위 = 60~110m)"이 있다. 그래서 틈은 계획:229, 중심 간격은 계획:230으로 나눠 적었다. 계획:187은 횡단 시간 표라서 인용하지 않았다 |
| "기준 HEAD는 e631581이다" | 방향은 반영했지만 기준은 그보다 새 HEAD 8a6399e로 적었다. 검토 뒤 계획서에 커밋이 하나 더 들어갔다(v2.0b 연기, 계획:520) |
| "`H/configs/v2_0b.yaml`의 alpha 0.5 대신 보정값을 쓰는 food_v 대응을 9.2에 넣는다" | 대응 규칙(하한 자르기, alpha·floor를 게임 값으로 정하지 않음)은 적었다. 다만 10-02에 v2.0b를 미뤘으므로(계획:520) 지금 시즌 설정에서는 food_v를 켜지 않는다고 정했다 |
