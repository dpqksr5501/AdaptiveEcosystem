# 숲 자람 모드 · '큰 변화만' 다시 배우기 · 파이썬 감시 자동 시작 — 설계와 구현 (2026-10-27)

- 작성: 권신혁(RL·정책). **상태: 구현했다 (10-27, `Branch_Sinhyeok`).** 1~8절은 설계이고, 구현하면서 바꾼 점은 각 절에 '구현:' 으로 적었다. 바꾼 파일·콘솔 변수·
  확인 결과(UBT 두 판·자동화 263 개 실패 0·창 없는 헤드리스 확인)는 9절. [LIVE_ADAPT_SPEC.md](LIVE_ADAPT_SPEC.md) 2·5.2·5.3·새 5.5절도 구현대로 고쳤다.
  구현 커밋(`51130c0`) 뒤 실제 실행 확인과 그때 찾아 고친 알림 글(나무 다 자람 묶음에 섞인 '비→비')은 **9.4절 '10-27 확인'**.
  그 뒤 `ae91f90..171c384` C++ 적대적 검토(찾은 것·고친 것 — Play 중 통합 v3 모드가 꺼지면 감시도 끝냄 — 과 남은 점)는 **9.5절**.
  10-29 기본 두뇌 R7e 뒤 두뇌 인수 없는 AutoAdapt + 숲 자람 실행 확인은 **9.6절 '10-29 확인'**.
- 기준: C++ 은 `Branch_Sinhyeok` `ae91f90`(그 뒤 커밋 `8f191c0` 은 파이썬 예비 측정 자료뿐). 파이썬은 커밋본과 **다른 워크플로의 10-27 작업 사본**
  (`LIVE_GATE.md` 변경 기록 (10) '실제 폴더 잠금 풀자' — 이 문서를 쓸 때 아직 커밋 전) 둘 다 읽었다. **구현하는 동안 그쪽이 커밋했다**(`2708a78` 잠금 풀기·`94e1b17` δ 인자·
  `7445bc6` 적대적 확인) — 아래 '작업 사본'은 이제 그 커밋이고, '커밋본(잠김)'은 `8f191c0` 까지다. 읽은 코드: `S/AI/Policy/EcoV3EnvWatch.cpp`·`EcoV3Snapshot.cpp`·`EcoV3PlaceTreesCommandlet.cpp`·
  `EcoPolicyV3IntegratedSubsystem.cpp`(AutoAdapt·상태 줄·알림)·`EcoPolicyV3IntegratedProcessors.cpp`(결정 스텝 고리)·`EcoV3Brain.cpp`(상태 파일),
  `herbivore_rl/results/v3/live/live.py`(watch·잠금·상태, **읽기만**), 엔진 `Engine/Source/Runtime/Core/Private/Windows/WindowsPlatformProcess.cpp`.
  (`S/` = `AdaptiveEcosystem/Source/AdaptiveEcosystem/`)
- 사용자 결정 (10-27, 원문): "변화하는 레벨은 팀에 맡기고 나는 변했을 때 어떻게 반응할지에 대해서만 설계하자. 그래서 일단은 모드를 하나 만들어서 해당
  모드에서는 숲이 점점 자라게 만들고 그걸 언리얼이 인식하면 그에 맞춰 두뇌 다시 만들어서 교체하는걸로 가자." 다시 배우기 기준 = "큰 변화만" — 날씨
  '종류'가 바뀜 또는 나무 수가 문턱 이상 바뀜. 세기 흔들림은 세계에는 넣되 다시 배우기는 하지 않는다. 잦은 변화는 묶는다. Play 때 파이썬 감시를 자동으로 띄운다.

## 한눈에 (쉬운 말)

1. **숲 자람 모드**(가)는 레벨 팀이 할 '레벨 바뀜'을 흉내 내는 **시험 모드**다. 세계 규칙이 아니다. 켜면 메마른 땅에 나무가 묶음으로 돋아,
   작은 묘목이 20 초 동안 자라고, 다 자란 순간부터 줄기가 사슴·늑대·사람을 막는다. 6 그루씩 40 초마다, 24 그루가 되면 멈춘다. 끄면 지금과 똑같다.
2. **큰 변화만 다시 배우기**(나)는 스냅숏을 '나무가 10 그루 이상 바뀜' 또는 '날씨 종류가 2 분 이상 바뀐 채'일 때만, 그리고 바뀜이 멈춘 뒤 한 번만 쓴다.
   비 세기만 흔들리는 것은 세계에 넣지만 알림도 스냅숏도 내지 않는다. 숲이 다 자랄 때까지 기다리므로 파이썬 판이 중간에 끊기지 않는다.
3. **파이썬 감시 자동 시작**(다)은 AutoAdapt Play 를 시작하면 `live.py watch` 를 창 없이 띄우고, Play 가 끝나면 학습 자식까지 함께 끝낸다.
   사람이 직접 띄운 감시가 이미 돌면 새로 띄우지도, 끄지도 않는다. 실제 폴더가 잠겨 있으면(`8f191c0` 까지) 감시가 곧바로 끝나고 화면 상태 줄이 그 까닭을 보인다.
   잠금을 푼 뒤(`2708a78` — 지금)에도 실제 폴더 고리는 **판 5 두뇌(R7e)로 시작한 Play 만** 다시 배운다 — 기본 내장 두뇌로 시작하면 스냅숏마다 '거부'가 보인다(3.7).
   **10-29 덧붙임**: 사용자 결정 '기본 두뇌 R7e로'에 따라 이제 통합 v3 Play 의 기본 두뇌(적응 고리 판 0)가 R7e 다(빌드에 넣은 두뇌 — [LIVE_ADAPT_SPEC.md](LIVE_ADAPT_SPEC.md) 5.6).
   그래서 아무것도 고르지 않고 AutoAdapt Play 를 해도 실제 폴더 고리가 다시 배운다. 아래 3.7-2·4절 15·8절의 '판 5 두뇌로 시작(`-EcoV3Brain=v3_r7_g995_s1_20m`)'은 10-27 의 이력이다.
   내장 R1b-F 로 시작하려면 `eco.V3Brain.Startup builtin`(`-EcoV3Brain=builtin`) — 그 Play 의 스냅숏은 여전히 실제 폴더에서 거부된다.

## 0. 지금 코드에서 읽은 사실 (설계의 근거)

| 사실 | 근거 |
|---|---|
| 환경 감시는 실시간 `EnvWatchSeconds`(1 초)마다·액터가 생기거나 지워진 다음 프레임(`kDirtyPollGapSeconds` 0.1 초 간격)에 `PollEnvironment` 로 줄기·날씨를 읽고, 처리기가 **전역 결정 스텝 경계(스텝 앞)**에서 `ApplyEnvChange` 로 넣는다 | `EcoV3EnvWatch.cpp` 545~719, `EcoPolicyV3IntegratedProcessors.cpp` 768~796 |
| 프레임 순서: `OnWorldPreActorTick`(→ `TickEnvWatch`: 예약 명령·읽기) → Mass `PrePhysics` 게임 스레드 처리기(스텝 고리: `ApplyEnvChange` → `SyncBrain` → `MaybeScheduledSnapshot` → `MaybeAutoSnapshot` → 스텝 → `FinishGlobalStep`) | `EcoPolicyV3IntegratedSubsystem.cpp` 2799~2845, 처리기 474~480·768~979 |
| 그래서 지금 레벨·시험용 나무가 세계에 들어가는 **스텝은 실시간 읽기 주기와 프레임 나눔에 따라 실행마다 다를 수 있다**(`Test.At` 도 프레임 시작의 `GlobalT` 로 판정) | 같은 곳 |
| 줄기 원판 = 꼬리표 `EcoV3Trunk` 액터의 정적 메시 컴포넌트 가운데 **쿼리 충돌 ∧ WorldStatic 막음**인 것만 (`GatherLevelTrunks` → `BlocksTeamMovement`). 충돌을 끈 컴포넌트는 세지 않는다 | `EcoPolicyV3IntegratedSubsystem.cpp` 1772~1775·2173~2208 |
| `Test.AddTrees` 자리 규칙: 벽 `kWallClearM` 4 m·은신처 원 + `kCoverClearM` 2 m·다른 원판 + 3 m 밖, 크기 1.8~2.2, 땅(`GroundStageTree` 7 점 선 검사)에 붙임, 400 번 시도, 씨 = `HashChain3("V3TT", 씨, 지역+1)` | `EcoV3EnvWatch.cpp` 1117~1238, `TreeLayoutV3.h` |
| 시험용 나무 짝은 **복제하지 않아 단독 실행만** 받는다 (`RefuseNetworked`) | `EcoV3EnvWatch.cpp` 346~357 |
| 메마른 땅(Barren) 배치 표는 0 그루 — 시작 때 나무가 없다 | `TreeLayoutV3.h` `kStages` |
| 자동 스냅숏 = 환경 판이 오르고 `AutoSnapshotSettle`(시뮬 3 초) 그대로면 **판마다 한 번**(`AutoSnapshotRevision`) | `EcoV3Snapshot.cpp` 871~933 |
| 환경 바뀜마다 화면 알림(`ENotice::Env`, 키 732002) — 세기만 바뀌어도 낸다 | `EcoV3EnvWatch.cpp` 991~993 |
| 상태 줄(키 732004)은 AutoAdapt 이거나 감시 폴더가 켜졌을 때만 1 초마다: `두뇌 판 … · 교체 n번 · 환경 #n · 적응 고리 \| <파이썬 상태> · 도망 요약`. 상태 파일이 없으면 `적응 고리 \| 파이썬 감시 없음`, 120 초 넘게 묵으면 `응답 없음 (n초 전)` | `EcoPolicyV3IntegratedSubsystem.cpp` 4502~4542, `EcoV3Brain.cpp` 519~538 |
| 조연우 복사 맵은 팀 비 주기 180 초(맑음↔비 반 주기 약 90 초, 전환 18 초 동안 세기가 0.2 초마다 바뀜)라 환경 판이 감시 주기마다 오른다 — 보통 속도에서 파이썬 판이 약 30 초마다 새 스냅숏에 끊겼다 | [LIVE_ADAPT_SPEC.md](LIVE_ADAPT_SPEC.md) 5.1, `herbivore_rl/results/v3/level_jyu_eco/README.md` 5절 |
| 조연우 복사 맵 스냅숏은 팀 life·식생이 켜져 있으면 거부된다 → 그 맵 확인에는 `-EcoEcosystemLife=0`·`setnopec EcoCreatureIntegrationSpawner bEnableVegetation False`·`eco.HerdMigration 0` | `EcoV3Snapshot.cpp` 463~470, `level_jyu_eco.py` `MODES` |
| `live.py watch` 는 **첫 줄에서** `plan_from_args` 를 부르고, 실제 폴더(`Saved/EcoAdapt`)인데 `LIVE.flight_sizes_confirmed` 가 거짓이면 `SystemExit("1차 사건 숨음 비율 기준의 크기…(LIVE flight_sizes_confirmed 거짓, …")` — **잠금·상태 파일을 쓰기 전에** 끝난다(종료 코드 1, 글은 stderr). 커밋본(`8f191c0`)은 거짓 | `live.py` 2332~2372·2964~2989 (커밋본) |
| 다른 워크플로의 10-27 작업 사본(변경 기록 (10), 커밋 전): `flight_sizes_confirmed` **참**. 대신 실제 폴더에서는 크기를 확정한 두뇌 묶음(`PROFILES sizes_confirmed` — 지금은 판 5 `route5` 만)의 지금 두뇌일 때만 판을 돌리고, 관측 18·21 지금 두뇌(**게임 기본 내장 R1b-F 포함**)의 스냅숏은 변환 전에 거부한다(`check_profile_sizes` → 상태 refused, 그 환경은 처리한 것으로 적혀 다시 하지 않음). 학습 S 2M → 1M, δ_H 1 %p. 예비 측정에서 이어 배운 후보 36 개가 모두 덜 숨어 통과 0 — '실제 판도 거의 다 기각될 것'으로 미리 적혀 있다. 한 바퀴 2M 3.9 분·1M 중간 기각 2.1 분 | 작업 사본 `live.py`·`LIVE_GATE.md`, 커밋 `8f191c0` 메시지 |
| 감시 하나만: `live/watch.lock`(O_EXCL, `{pid, create_time, what, time}`), 주인이 죽은 잠금은 치운다(`proc_alive` — psutil 시작 시각까지 견줌). 다른 고리가 살아 있으면 `SystemExit("다른 실시간 고리(…)가 … 를 쓰고 있다")` | `live.py` 765~808 |
| 감시는 켠 뒤 생긴 스냅숏만 본다(`--existing` 없으면 `cut = 시작 시각`), 2 초마다 보고, 판은 따로 된 프로세스 묶음(`CREATE_NEW_PROCESS_GROUP`)의 자식, **다른 환경의 새 스냅숏이 오면 돌던 판 나무를 끝낸다(superseded)**. 환경 지문(`env_digest`)에는 원판·날씨 종류·**세기**·먹이 용량·은신처가 든다 | `live.py` 54·585~613·2778~2874 |
| `status.json` 은 감시가 5 초마다 다시 쓴다(`HEARTBEAT_S`), `pid` 칸은 쓴 프로세스(감시 또는 판 자식)다. `state.json` 은 시도·판 번호·처리한 열쇠 | `live.py` 167~172·683~880 |
| 엔진 `CreateProc`: `CREATE_NO_WINDOW` 는 **`bLaunchDetached` 와 `bLaunchReallyHidden` 이 함께 참일 때만** 붙는다. `bLaunchReallyHidden` 만이면 `SW_HIDE` 뿐이라 GUI 편집기에서 띄운 콘솔 프로그램은 새 콘솔을 받는다. `CreateProc` 은 작업 개체(Job)에 넣지 않는다(편집기가 죽으면 자식이 남는다). `TerminateProc(…, KillTree=true)` 는 부모 pid 를 따라 자손을 먼저 끝낸다(부모가 먼저 죽어 끊긴 손자는 못 찾는다) | `WindowsPlatformProcess.cpp` 538~720·751~812 |
| 사용자 컴퓨터의 `python`: 사용자 PATH 맨 앞이 `C:\Users\Sinhyeok\anaconda3`(그 뒤 `Library\…\bin`·`Scripts`, 그 뒤 `WindowsApps`·`msys64`), 시스템 PATH 에는 파이썬 없음 → `python` = `C:\Users\Sinhyeok\anaconda3\python.exe` (Anaconda base, Python 3.13.5). 다른 워크플로가 지금 돌리는 python.exe 도 같은 파일이다. `live.py` 머리 주석도 'Anaconda base python, PYTHONUTF8=1' | 10-27 `where python`·사용자/시스템 PATH 읽기·프로세스 목록(읽기만) |

## 1. (가) 숲 자람 모드

### 1.1 무엇이고 무엇이 아닌가

- 레벨 팀이 할 '숲이 자라는 레벨 바뀜'을 **흉내 내는 시험 모드**다. `Test.AddTrees` 와 같은 자리(5.3 시험용 대역)이고 세계 규칙이 아니다.
  v3 세계 규칙·배수·관측·두뇌·먹이 격자는 바꾸지 않는다 — 다 자란 나무는 지금 레벨 나무와 **똑같은 길**(꼬리표 `EcoV3Trunk` 줄기 막이 → 환경 감시 →
  결정 스텝 경계 `ApplyEnvChange`)로 세계에 들어간다. 먹이 격자는 그대로다(팀 자원 계약, 5.1).
- 맵과 무관하다: 통합 v3 모드가 도는 어느 맵이든 고른 지역에 v3 무대가 있으면 돈다. 서버·단독에서만 자라고, 클라이언트는 복제된 나무를 그리기만 한다.

### 1.2 스위치 (개발 빌드 `#if !UE_BUILD_SHIPPING`, **Play 시작 때 한 번 읽는다** — 같은 씨 같은 결과를 위해 Play 중 바꿈은 다음 Play 부터)

| 콘솔 변수 | 기본 | 뜻 |
|---|---|---|
| `eco.IntegratedV3.ForestGrowth` | 0 | 1 = 켬. 명령줄 `-EcoV3ForestGrowth`(= 1) 또는 `-EcoV3ForestGrowth=0\|1` 은 시작값 |
| `eco.IntegratedV3.ForestRegion` | `Barren` | 자랄 지역 (메마른 땅이 숲이 되는 이야기). 명령줄 `-EcoV3ForestRegion=` |
| `eco.IntegratedV3.ForestPerStage` | 6 | 한 단계에 돋는 그루 수 |
| `eco.IntegratedV3.ForestStageSeconds` | 40 | 단계 간격 (시뮬레이션 초) |
| `eco.IntegratedV3.ForestGrowSeconds` | 20 | 묘목이 다 자라는 데 걸리는 시뮬레이션 초 (1~600 으로 자름 — 1 초 밑이면 묘목 액터가 생기기 전에 다 자랄 수 있다) |
| `eco.IntegratedV3.ForestTarget` | 24 | 이 수에서 멈춤 (1~64) |
| `eco.IntegratedV3.ForestStartSeconds` | 30 | 첫 단계 시뮬레이션 초 (사슴이 자리 잡은 뒤) |
| `eco.IntegratedV3.ForestSeed` | −1 | 자리 씨 (−1 = 세션 시드 `eco.IntegratedV3.Seed`) |
| `eco.IntegratedV3.ForestSapling` | 0.15 | 묘목 처음 크기 몫 (그리기만 — 세계와 무관) |

시간은 모두 **전역 결정 스텝**으로 바꿔 쓴다: 스텝 수 = 반올림(초 ÷ 2/15). '시뮬레이션 초' = `GlobalT × 2/15` (`Test.At`·스냅숏 `sim_seconds` 와 같은 시계).

### 1.3 기본 시간표 (단계 k = 0..K−1, K = ⌈목표 ÷ 단계 그루⌉ = 4)

| 단계 | 묘목 돋음 | 다 자람 = 세계에 들어감 | 메마른 땅 줄기 |
|---|---|---|---|
| 1 | 30 초 (스텝 225) | 50 초 (스텝 375) | 0 → 6 |
| 2 | 70 초 (525) | 90 초 (675) | 6 → 12 |
| 3 | 110 초 (825) | 130 초 (975) | 12 → 18 |
| 4 | 150 초 (1125) | 170 초 (1275) | 18 → 24 — 멈춤 |

마지막 단계는 `min(단계 그루, 목표 − 앞서 놓은 수)` 그루. 다 자란 단계마다 환경 판이 하나 오른다(한 단계 = 한 묶음 `나무 6→12 (+6 −0)`, 출처 `forest_growth`).
목표에 닿으면 더 돋지 않고, 나무는 Play 가 끝날 때까지 그대로 있다 — 파이썬 판이 끝까지 돌 수 있게(2.6절).

### 1.4 자리 고르기 (Play 시작 때 한 번 모두 정한다)

- 지역 세계가 생긴 직후(`TryCreateContexts` 가 성공한 그 프레임 — 시작 직전 지면 검사로 무대 땅이 불린 뒤) **목표 수만큼 자리를 한꺼번에** 정한다.
  규칙은 `Test.AddTrees` 그대로다: 벽 4 m·은신처 원 + 2 m·다른 원판(그때 세계 원판 + 앞서 고른 숲 자리) + 3 m 밖, 크기 1.8~2.2·방위 0~360°,
  `MakeLevelTree` 로 기준점, `GroundStageTree` 로 땅(7 점, 가운데 점 필수) 높이 `MinZ`, 한 그루에 400 번 시도.
- 씨: `HashChain3("V3FG", 씨, 지역 색인 + 1)` 에서 시작해 그루 순서대로 뽑는다. 씨가 같으면 같은 자리다.
  - 구현: 난수 하나로 목표 수 모두를 차례로 뽑는다 (단계마다 따로 시작하지 않는다 — 시작 때 모두 정하므로 같은 결정성). 뽑는 순서는 `Test.AddTrees` 와 같은 크기·방위·X·Y
    (`EcoV3ForestGrowth.h` `PlanSlots`, 순수 함수 — 땅은 `GroundStageTree` 를 넘겨 묻는다). 씨 기본은 세션 시드.
- 까닭(단계 때 고르지 않고 시작 때 다 고르는 것): 자리가 Play 중 세계 상태·스트리밍·프레임 나눔에 기대지 않는다(1.9 결정성). 지형은 그대로이고, 시작 때
  무대 땅은 이미 검사했다. 자리를 못 찾은 그루는 빼고(기록) 목표를 그만큼 줄인다 — 같은 씨면 같은 결과다.
- 단계 때 다시 보는 것은 하나뿐: 다 자랄 때 그 자리 원판이 그새 생긴 다른 줄기(레벨 팀·`Test.AddTrees`)와 겹치면(중심 거리 < 두 반지름 합) 그 그루는 빼고
  묘목을 지운다(`[EcoV3I] 숲 자람 | Barren F07 자리 겹침 — 뺌`).

### 1.5 한 그루의 일생

1. **묘목 돋음** (단계 시각, 그리기만): 처리기가 스텝 경계에서 '돋을 차례'를 표시하고, 다음 `HandlePreActorTick`(Mass 처리 밖, 게임 스레드)에서 서버가
   숲 나무 액터 `AEcoV3ForestTree` 를 놓는다. 꼬리표 `EcoV3Tree`·`EcoV3TreeId_<지역>_F<nn>`(줄기 꼬리표는 아직 없음). 나무 메시는 충돌 없음,
   줄기 막이 원기둥(`/Engine/BasicShapes/Cylinder`)은 숨김·**충돌 없음**. 그래서 `GatherLevelTrunks` 가 세지 않고 세계·사슴·늑대·사람을 막지 않는다
   ('작은 묘목은 막지 않음'). 액터가 생기면 환경 감시가 한 번 읽지만 바뀐 줄기가 없어 아무것도 하지 않는다.
   - 구현: 표시 없이 `HandlePreActorTick` 의 `ForestPreActorTick` 이 '전역 스텝 ≥ 그 단계 돋음 스텝'을 보고 놓는다. 아주 짧은 자람 초·긴 프레임으로 다 자람 경계가 먼저
     오면 그 경계에서 놓고 곧바로 다 자람으로 바꾼다(세계에 닿는 값은 계획에서 정해져 같다). 기록 `숲 자람 | 30.0초 (전역 스텝 225) 묘목 6 돋음 (F00~F05) — 놓은 때 전역 스텝 n`.
2. **자람** (그리기만): 크기 = 최종 크기 × (`ForestSapling` + (1 − `ForestSapling`) × smoothstep(경과 ÷ `ForestGrowSeconds`)). 경과는 서버 월드 시각
   (`AGameStateBase::GetServerWorldTimeSeconds`)이다 — 클라이언트도 같은 식으로 그린다. 크기마다 `MakeLevelTree(X, Y, 크기, 방위)` 로 기준점을 다시
   셈해 줄기 중심이 움직이지 않게 한다(메시 기준점 → 밑동 차 3.7 cm × 크기).
3. **다 자람** (세계 규칙, **정확한 스텝**): 처리기 스텝 고리에서 `HasPendingEnvChange` 바로 앞에 `ForestStepBoundary()` 를 부른다. `GlobalT` 가 그 단계의
   다 자람 스텝이면:
   - 서버가 그 단계 나무를 다 자람으로 바꾼다: 최종 크기, 줄기 막이 `BlockAll`(명령·`SpawnLevelTreePair` 와 같은 프로파일), 꼬리표 `EcoV3Trunk` 더함,
     복제 칸 `bMature` 참·`ForceNetUpdate`.
   - 곧바로 **나무만 다시 읽기**(`PollEnvironment(bForce=true, bTreesOnly=true)` — 날씨 칸·실시간 읽기 주기는 건드리지 않는다)를 하고, 출처를
     `forest_growth` 로 적는다(`bEnvTestEdit` 처럼 표시 하나).
   - 같은 경계에서 이어지는 `ApplyEnvChange` 가 넣는다 — 새 원판 안 사슴·늑대 밀어냄, 돌아가기 지움, 기록 `환경 바뀜 #n | … | Barren: 나무 6→12 (+6 −0) (출처
     forest_growth …)`, 화면 알림. 원판 값은 액터에서 읽은 값이라 `Test.AddTrees` 와 같은 셈이다(시험 `Policy.V3.EnvWatch.Trees` 가 본 길).
   - 이 순간 뒤의 정기 읽기는 같은 줄기를 보므로 아무것도 하지 않는다(액터 = 세계 원판이 늘 맞다 — 줄기를 액터 없이 세계에만 넣으면 다음 정기 읽기가
     '줄기가 없어졌다'로 되돌리므로 그렇게 하지 않는다).

### 1.6 복제 — 단독·리슨·데디케이티드 + 클라이언트 모두 같은 나무

`AEcoV3ForestTree` (새 액터, `S/AI/Policy/EcoV3ForestTree.{h,cpp}`) — 팀 `AEcoRefugeHabitat` 와 같은 꼴:
`bReplicates = true`, `bAlwaysRelevant = true`(24 그루뿐), `SetReplicateMovement(false)`, `RF_Transient`(저장 안 함), 다 자란 뒤 휴면(`DORM_DormantAll`).
- 구현: 휴면은 쓰지 않았다 — 갱신 빈도 1 Hz(`SetNetUpdateFrequency`) + 바뀔 때 `ForceNetUpdate` (많아야 64 그루라 값 견주기가 싸다. 휴면 전환 시각에 바뀐 값이 빠지는 일을
  피했다). 계획 칸은 구조체 `FEcoV3ForestPlan` 하나(`ReplicatedUsing = OnRep_Plan` — 한 번에 받는다)이고 `R` 은 기록·보기용으로만 함께 보내며(변환에는 쓰지 않는다 — 10-27 적대적 검토가 바로잡은 글) `PivotX/Y` 는 보내지 않고 `MakeLevelTree(X, Y, Scale, YawDeg)` 로
  서버·클라이언트가 같이 셈한다. 액터 변환은 늘 원점·단위 변환이라 구성요소의 세계 변환 = 상대 변환(합성 오차 없음). 나무 메시는 실행 중에 읽는다(생성자에서 읽으면
  편집기를 켤 때마다 팀 애셋을 불러온다).

| 복제 칸 (`ReplicatedUsing = OnRep_Plan`, 한 번) | 뜻 |
|---|---|
| `double OriginX, OriginY, OriginZ` | 무대 원점 (cm) |
| `double X, Y, R, YawDeg, Scale` | 줄기 중심·반지름(무대 단위)·방위·최종 크기 — `FTree` 그대로 |
| `double GroundMinZ` | 서버가 잰 땅 높이 (클라이언트는 다시 재지 않는다 — 클라이언트 지형 스트리밍과 무관) |
| `double GrowStartServerTime`, `float GrowSeconds`, `float SaplingFrac` | 자람 그리기 |
| `FName RegionId`, `int32 Index, Target` | 기록·클라이언트 보기 |
| `bool bMature` (`ReplicatedUsing = OnRep_Mature`) | **권위 값** — 참이면 최종 크기·줄기 충돌 켬 |

- 실수 칸은 `double` 로 따로 둔다(8 바이트 그대로 — `FVector` 양자화 여부에 기대지 않는다). 클라이언트는 받은 값으로 서버와 **같은 정적 함수**
  (`MakeLevelTree`·`LevelTreeTransform`·`LevelTrunkTransform`, 같은 엔진 원기둥 메시)를 불러 변환을 만든다 → 줄기 충돌 모양이 서버와 같다.
- 클라이언트·데디케이티드 서버의 일: 클라이언트는 v3 서브시스템이 꺼져 있으므로(표현만) 액터가 스스로 그린다. 데디케이티드 서버는 그리지 않으므로 Tick 을 끈다
  (`NM_DedicatedServer`) — 다 자람 때 최종 크기만 놓는다.
- 늦게 들어온 클라이언트도 `bMature` 를 함께 받아 곧바로 다 자란 나무·충돌을 갖는다.
- **남는 차이 (기록)**: 서버가 줄기 충돌을 켠 스텝과 클라이언트가 `OnRep_Mature` 를 받는 순간 사이(지연 절반쯤)에 클라이언트 폰이 그 자리에 들어가면 서버
  보정으로 한 번 되돌려진다. 묘목이 20 초 동안 같은 자리에서 자라 보이므로 드물다. 다 자랄 때 폰이 줄기 안에 서 있으면 캐릭터 이동의 겹침 풀기에 맡긴다(확인 6.4).
- **어렵다면 빼는 순서와 근거** (구현 중 막히면 이 순서로 줄이고 문서에 적는다):
  1. 클라이언트 화면 알림 줄(1.7)은 빼도 된다 — 나무는 보인다.
  2. 사람(폰) 막기를 뺀다: 줄기 막이를 `BlockAll` 대신 '쿼리만·WorldStatic 막음·Pawn 무시' 프로파일로. `BlocksTeamMovement` 는 그대로 참이라 세계 원판·
     사슴·늑대는 같고, 클라이언트 보정 문제가 아예 없어진다. 대신 사람은 줄기를 지나간다(레벨 나무와 다름 — 사용자에게 알린다).
  3. 복제를 빼는 것(단독만)은 **하지 않는다** — `Test.AddTrees` 가 이미 그 꼴이고, 이 모드를 따로 만드는 까닭이 리슨·데디케이티드에서도 보이는 것이다.

### 1.7 화면 알림·기록·보기

- 숲 줄(새 키 732005, 그리는 실행·클라이언트 아님, `eco.V3Brain.Notice` 1 일 때, AutoAdapt 와 상관없이 1 초마다):
  `숲이 자라는 중 — 메마른 땅 나무 12/24 (묘목 6 그루 자라는 중)` → 다 자라면 `숲이 다 자랐다 — 메마른 땅 나무 24/24` 를 10 초 보이고 끈다.
  숫자 = 다 자란 그루/목표. 지역 이름은 숲·고지·메마른 땅(그 밖은 ID).
- 다 자람마다 지금 환경 알림 그대로: `환경 바뀜 #2 — Barren: 나무 6→12`.
  - 10-27 확인 고침(9.4): '큰 변화만' 규칙이 돌 때 같은 결정 스텝 묶음에 든 **세기만 바뀐 지역은 알림 글에서 뺀다** — 조연우 맵에서 다 자람 묶음에 팀 비 세기
    흔들림이 섞여 `환경 바뀜 #27 — Barren: 나무 0→6 · Barren: 비→비` 로 보였다. 기록 줄 `[EcoV3I] 환경 바뀜 #n | …` 에는 날씨 칸이 그대로 남는다.
- 클라이언트 줄(덤, 1.6-1 에서 뺄 수 있음): 클라이언트는 복제된 숲 나무 액터를 세어 같은 글을 그린다(`Target`·`RegionId` 는 액터 칸).
- 기록(헤드리스 증거): Play 시작 `[EcoV3I] 숲 자람 | 켬 — Barren 6 그루 × 40초, 묘목 20초, 목표 24, 첫 단계 30초, 씨 n | 자리 24/24: F00 (x, y) r … · …`
  (또는 `끔`·거부 까닭), 단계마다 `[EcoV3I] 숲 자람 | 30.0초 (전역 스텝 225) 묘목 6 돋음 (F00~F05)`·`… 50.0초 (전역 스텝 375) 6 그루 다 자람 → 세계에 넣음`.
- 보기 명령 `eco.IntegratedV3.ForestInfo`: 서버 = 계획·단계·다 자람 스텝·자리, 클라이언트 = 받은 숲 나무 액터마다 `bMature`·줄기 충돌 켬·줄기 변환 해시
  (서버와 견줄 값 — 6.4).
- 구현: 다 자랄 때 나무마다 한 줄 `[EcoV3I] 숲 Barren_F07 다 자람 (단독|리슨 서버|데디케이티드 서버|클라이언트) | 줄기 충돌 켬 · 줄기 변환 지문 <FNV-1a 64>` —
  클라이언트는 `OnRep_Mature` 에서 같은 줄을 남겨 명령 없이 서버와 견줄 수 있다(9절 리슨·데디케이티드 확인). 클라이언트 화면 줄은 색인 0 나무가 1 초마다 그린다.
- 스냅숏 `env` 에 더하기만: `"forest": {"on": true, "region": "Barren", "target": 24, "planned": 24, "mature": 12, "stage_seconds": 40, "grow_seconds": 20,
  "next_mature_step": 975, "done": false}`. 바뀜 줄 `source` 에 `forest_growth` 가 새로 생긴다(파이썬은 `source`·모르는 칸을 읽지 않는다 — `live.py`·`adapt.py`
  찾기로 확인. `env_summary` 는 `나무 a→b` 꼴을 읽으므로 그 꼴을 지킨다).

### 1.8 거부·조심 (그때는 아무것도 놓지 않고 까닭을 한 줄 남긴다)

- 고른 지역에 v3 무대가 없음 → `eco.IntegratedV3.ForestRegion` 으로 고르라고 적는다.
- 그 지역 장애물이 꺼졌거나(`eco.IntegratedV3.Obstacles 0`) 원판을 가져왔거나(`ObstacleImport`), 환경 감시가 꺼짐(`EnvWatch 0`) → 줄기가 세계에 들어가지 않으므로
  거부(겉모습만 자라는 숲은 이 모드의 뜻이 아니다).
- 그 지역에 실행 중 무대 나무가 서 있음(`StageTrees 1` 이고 레벨 줄기가 없던 무대) → 거부. 첫 줄기가 다 자라는 순간 `ApplyEnvChange` 가 시작 규칙대로
  무대 나무 전부를 빼기 때문이다(메마른 땅은 배치 표가 0 그루라 해당 없음).
- 목표 < `eco.IntegratedV3.BigTrees` → 경고만: '숲 자람만으로는 다시 배우기 스냅숏이 나오지 않는다'.
- `Test.RemoveTrees` 는 숲 나무를 지우지 않는다(클래스로 뺀다 — 숲은 자라기만 한다). `Test.AddTrees` 는 숲 자리를 피할 원판에 넣고, 숲 액터를 땅 검사에서 뺀다.

### 1.9 결정성과 '끄면 비트 동일'

- 세계에 닿는 것은 '다 자람' 하나이고, 그것은 **전역 스텝 번호로 정해진 경계**(처리기 스텝 고리 안)에서 일어난다 → 프레임 나눔·fps·실시간 읽기 주기와
  무관하게 같은 씨면 같은 스텝·같은 원판이다. 자리는 시작 때 정한다(1.4). 묘목 돋음·자람 그림은 세계에 닿지 않으므로 프레임·벽시계로 해도 된다.
- 끔(기본): 숲 코드는 Play 시작 설정 한 칸(`bForestGrowth`)으로 막혀 액터도, 강제 읽기도, 스냅숏 칸도 없다 → 지금 실행과 비트 단위로 같다(확인 6.3-a).
- 남는 비결정(이 모드 밖): 조연우 맵 팀 날씨를 실시간 주기로 읽는 것(5.1 — 그 맵은 원래 같은 시드 바이트 비교에서 뺐다), `Test.At` 예약(프레임 단위).

## 2. (나) '큰 변화만' 다시 배우기 — 자동 스냅숏을 언제 쓰나

### 2.1 규칙

- **기준선** = Play 시작(지역 세계를 만든 때) 또는 마지막 **자동** 스냅숏 때의 지역마다 (세계 원판 모음, 날씨 종류). 주기·콘솔·예정 스냅숏은 기준선을 바꾸지 않는다.
- **나무 큰 변화**: 어느 지역이든 지금 세계 원판(`W.Config.Obstacles.Discs`)과 기준선 원판의 **대칭차 개수**(같은 (x, y, r) 끼리 하나씩 지우고 남은 양쪽 합 —
  `MinusDiscs` 두 번) ≥ `BigTrees`(10). 줄기 원판이 아니라 세계 원판 전체로 세는 까닭: 바위 등은 Play 중 바뀌지 않으므로 보통은 줄기 차와 같고, 실행 중 무대 나무를
  빼거나 다시 넣는 드문 경우도 세계가 실제로 바뀐 만큼 센다. 장애물을 끈·가져온 지역은 늘 0.
- **날씨 큰 변화**: 어느 지역이든 지금 세계 날씨 종류(맑음·비·눈)가 기준선과 다르고, 그 종류가 된 뒤 `WeatherHold`(시뮬 120 초) 이상 이어짐.
  120 초인 까닭: 팀 비 주기 180 초의 맑음·비 반 주기(약 90 초)는 넘지 않게 — 조연우 맵의 오가는 비는 큰 변화가 아니다. 종류가 기준선으로 돌아오면 셈은 없어진다.
- **세기만 바뀜**(같은 종류의 세기): 세계에는 지금처럼 넣는다. 큰 변화 셈·바뀜 시계에는 넣지 않는다.
- **묶기**: 큰 변화 조건이 선 뒤, 큰 변화에 드는 바뀜(아래 2.3)이 `BigSettle`(시뮬 20 초) 동안 없을 때 **한 번** 쓴다.
- **숲이 자라는 동안 기다림**: 숲 자람 모드가 아직 목표에 닿지 않았으면(돋을 단계나 자라는 묘목이 남음) 쓰지 않는다. 기다림은 조건이 선 때부터
  `BigMaxWait`(시뮬 300 초)까지 — 넘으면 쓰고 기록한다(목표를 아주 크게 줘 끝없이 기다리는 일을 막는다). 기본 숲(조건 90 초 → 다 자람 170 초)은 80 초 기다린다.
  - 왜 `BigSettle` 만으로 안 되나: 기본 단계 간격 40 초 > 20 초라, 묶기만으로는 단계 2 가 다 자란 뒤 20 초에 한 번, 단계 4 뒤에 또 한 번 써서 첫 판이 끊긴다(2.6).
  - 일반 꼴: 기다림 입력은 '레벨 바뀜이 아직 진행 중'이라는 표시 하나다(`SetLevelChangeHold(이름, 참/거짓)`). 지금은 숲 자람 모드만 쓴다. 레벨 팀이 같은 표시를
    쓰고 싶으면 이 함수 하나로 붙는다(쓰지 않아도 `BigSettle` 묶기는 돈다).
- 쓴 뒤: 기준선 = 지금, `AutoSnapshotRevision = EnvRevision`, 조건·기다림 시계 지움.
- 옛 동작: `eco.IntegratedV3.AutoSnapshotRule 0` = 지금처럼 환경 판마다 `AutoSnapshotSettle`(3 초) 뒤 한 번.
- 구현 (`S/AI/Policy/EcoV3BigChange.h` — 엔진 없는 순수 함수 `CountDiff`·`OnTrees`·`OnWeather`·`Evaluate`·`Tick`·`Rebase`·`ProgressText`):
  - 상한은 묶기도 넘는다 — 조건 뒤 `BigMaxWait` 가 지나면 '진행 중'·바뀜 멈춤과 상관없이 그 경계에서 쓴다(`capped`). 레벨이 쉬지 않고 바꿔도 끝없이 기다리지 않게.
  - 쓰기에 실패해도 기준선을 다시 정한다(경계마다 다시 쓰지 않게 — 규칙 0 의 '판마다 한 번'과 같은 뜻).
  - 기준선은 `AddContext`(지역 세계를 만든 때 — 10-27 (C) 시작 날씨를 넣은 뒤)에 지역마다 적는다. 장애물을 끈·원판을 가져온 지역은 원판 바뀜을 넣지 않으므로 늘 0 이다.

### 2.2 스위치 (개발 빌드, Play 중 바꿔도 다음 결정 스텝부터 — 세계에 닿지 않으므로 결정성과 무관)

| 콘솔 변수 | 기본 | 뜻 |
|---|---|---|
| `eco.IntegratedV3.AutoSnapshotRule` | 1 | 1 = 큰 변화만 (AutoAdapt 기본), 0 = 옛 동작 (판마다) |
| `eco.IntegratedV3.BigTrees` | 10 | 한 지역 세계 원판 대칭차 문턱 |
| `eco.IntegratedV3.WeatherHold` | 120 | 바뀐 날씨 종류가 이어져야 하는 시뮬레이션 초 |
| `eco.IntegratedV3.BigSettle` | 20 | 조건이 선 뒤 큰 변화 바뀜이 없어야 하는 시뮬레이션 초 |
| `eco.IntegratedV3.BigMaxWait` | 300 | '레벨 바뀜 진행 중' 기다림의 상한 (시뮬레이션 초) |
| `eco.IntegratedV3.EnvNoticeMinor` | 0 | 1 = 세기만 바뀐 환경 판도 화면 알림 (옛 동작). 0 = 기록 줄만 |

`eco.IntegratedV3.AutoSnapshot`(−1 = AutoAdapt 따름)·`SnapshotEvery`(주기)·`AutoSnapshotOut`·콘솔 `eco.IntegratedV3.Snapshot`·예정 `SnapshotAt` 은 그대로다.
명령줄 `-EcoV3AutoSnapshotRule=`·`-EcoV3BigTrees=` 등은 시작값(다른 스위치와 같은 `SetIfUnset`).

### 2.3 무엇을 세나 (모두 `ApplyEnvChange` 안 — 결정 스텝 경계)

| 일 | 큰 변화 바뀜 시계(구현 `FState::LastActivityStep`) | 지역 날씨 종류 시작(`KindSinceStep`) | 화면 알림 |
|---|---|---|---|
| 줄기 원판이 바뀐 묶음 (레벨·시험·숲) | 지금 스텝 | — | 지금처럼 |
| 날씨 종류가 바뀐 묶음 | 지금 스텝 | 지금 스텝 | 지금처럼 |
| 세기만 바뀐 묶음 | 그대로 | 그대로 | `EnvNoticeMinor 0` 이면 없음 (기록 `[EcoV3I] 환경 바뀜 #n | …` 은 늘) |
| 숲 묘목 돋음 | 그대로 (세계가 바뀌지 않았다 — 기다림은 2.1 의 '진행 중' 표시가 맡는다) | — | 숲 줄 |

조건 판정은 `MaybeAutoSnapshot`(스텝 경계마다)이 한다. 원판 대칭차는 원판이 바뀐 묶음과 기준선을 바꿀 때만 다시 세어 지역마다 들고 있는다(스텝마다 셀 필요 없음).
- 구현: 세기만 바뀐 묶음의 알림 끄기는 **규칙이 돌 때만**(자동 스냅숏 켬 ∧ `AutoSnapshotRule 1` ∧ `EnvNoticeMinor 0`) 한다. 자동 스냅숏이 꺼진 Play(AutoAdapt 0 기본)는
  기록·알림 모두 지금까지와 같다 — '끄면 지금과 같음'을 기록 줄까지 지키려고. 끈 묶음의 기록 줄 끝에 ` | 세기만 바뀜 — 다시 배우기 셈·화면 알림 없음 (eco.IntegratedV3.EnvNoticeMinor 0)`.

### 2.4 화면·기록·스냅숏

- 상태 줄 `환경 #n` 뒤에 한 칸(AutoAdapt 상태 줄이 그려질 때):
  - 쌓는 중: `다시 배우기까지: 메마른 땅 나무 +7/10 · 날씨 그대로` (가장 많이 바뀐 지역 하나, 지운 것이 섞이면 `±7/10`), 날씨가 바뀌어 기다리면
    `숲 날씨 맑음→비 45/120초`.
  - 조건 됨: `다시 배우기: 조건 됨 — 숲이 다 자랄 때까지 기다림` 또는 `다시 배우기: 조건 됨 — 바뀜이 멈추길 기다림 12/20초`.
  - 옛 동작: `다시 배우기: 환경 판마다 (eco.IntegratedV3.AutoSnapshotRule 0)`.
- 기록: 조건이 처음 선 때 `[EcoV3I] 다시 배우기 조건 됨 | 90.0초 (전역 스텝 675) | Barren 나무 +12/10 · 날씨 그대로 | 기다림: 숲 자라는 중`,
  쓸 때 지금 `[EcoV3I] 환경 스냅숏 | …` 줄과 `why` = `큰 변화 — Barren 나무 +24 (기준 전역 스텝 0) · 날씨 그대로 · 바뀜 없이 20.0초 · 기다림 80.0초`.
- 스냅숏 `env` 에 더하기만: `"rule": "big"`(옛 동작 `"each"`), `"big": {"baseline_step": 0, "trees": {"Barren": 24, "Forest": 0, "Highland": 0},
  "weather": {"Forest": {"base": "rain", "now": "rain", "held_s": 0}, …}, "quiet_s": 20.0, "held_s": 80.0, "capped": false}`. `trigger` 는 그대로 `env_change`
  (파이썬은 `trigger` 를 기록만 한다).
- 구현: `big.held_s` = **조건이 선 뒤 흐른 초**다(기본 숲은 90 초 조건 → 190 초 쓰기 = 100 초, 위 예의 80 은 '숲이 다 자랄 때까지'만 센 값이었다). `big` 에는
  `big_trees`·`weather_hold_s`·`settle_s`·`max_wait_s`·`condition`·`level_change_hold` 도 적는다. `why` = `큰 변화 — 메마른 땅 나무 +24/10 · 날씨 그대로 (기준 전역 스텝 0) ·
  바뀜 없이 20.0초 · 조건 뒤 100.0초`. 상태 줄 칸은 자동 스냅숏이 켜졌을 때만 붙고(`eco.IntegratedV3.EnvInfo` 첫 줄에도), 기다림 글은 `… 숲이 다 자랄 때까지 기다림 (45/300초)`.

### 2.5 예: 기본값 두 맵

- **팀 통합 맵 + 숲 자람(기본)**: 50·90·130·170 초에 환경 판 #1~#4(메마른 땅 6→…→24). 90 초에 나무 +12 ≥ 10 으로 조건 됨, 숲 자라는 중이라 기다림,
  170 초에 다 자람 → 바뀜 없이 20 초 → **190 초(전역 스텝 1425)에 스냅숏 한 번**. 날씨 출처가 없어 날씨 바뀜 없음.
- **조연우 복사 맵 + 숲 자람**: 팀 비 주기로 환경 판이 자주 오르지만 세기 판은 알림·셈이 없고, 종류 판(약 90 초마다)은 120 초를 넘기지 못해 큰 변화가 아니다.
  종류 판은 바뀜 시계를 0 으로 돌리므로 스냅숏이 최대 20 초 늦어질 수 있다. 결과는 위와 같이 한 번(190~210 초 사이).
  스냅숏에 적히는 날씨는 쓰는 순간의 날씨다(4절 열린 질문 6).
  - 구현 확인(9.3): 한 번은 맞고 217.7 초였다 — 숲이 다 자란 뒤 다른 두 지역의 종류 바뀜이 잇따라(183.9·197.7 초) 바뀜 시계를 되돌렸다. 세 지역 위상이 30 초씩
    어긋나 종류 바뀜이 약 30 초마다 오므로 20 초 고요는 늘 오지만, 늦어짐은 '최대 20 초'가 아니라 '마지막 종류 바뀜 + 20 초'다.
  - 10-27 확인(9.4, 400 초 실시간 두 판): 숲 켬 = 213.1 초 하나(고지 종류 바뀜 193.1 초 + 20 초), 숲 끔 = 0 — 팀 비 주기만으로는 큰 변화가 아니다
    (비 약 108 초·맑음 약 72 초 이어짐 < 120 초).

### 2.6 파이썬 판이 끊기지 않게 (live.py 는 이번에 바꾸지 않는다)

`live.py watch` 는 판 도중 다른 환경(지문이 다른 — 날씨 세기까지 든다) 스냅숏이 오면 돌던 판을 끝내고 새로 시작한다. 그래서 언리얼이 스냅숏을 덜, 그리고 바뀜이
멈춘 뒤에만 써야 한다:

| 끊김 원인 | 막는 것 |
|---|---|
| 팀 비 세기 흔들림 (조연우 맵 — 10-25 스모크에서 약 30 초마다 끊김) | 세기만 바뀜은 큰 변화가 아니다 → 스냅숏 없음 |
| 맑음↔비 오감 (약 90 초) | `WeatherHold` 120 초 > 반 주기 |
| 숲이 계속 자람 (40 초마다 6 그루) | '진행 중' 기다림 + 목표 수에서 멈춤 → 다 자란 뒤 한 번 |
| 레벨이 나무를 여럿 차례로 놓음 | `BigSettle` 20 초 묶기 |

- 기본 숲에서 첫 스냅숏은 190 초다. 판 한 바퀴는 실시간 몇 분이다(작업 사본 학습 1M 스텝 — 예비 측정 커밋 `8f191c0`: 2M 3.9 분, 1M 중간 기각 2.1 분.
  변환·재현 확인·G 판정 포함 전체는 그보다 길 수 있다). 숲은 멈춰 있고 조연우 맵 날씨도 큰 변화가 되지 않으므로 그 판은 끝까지 돈다.
  **사람이 할 일: 두뇌가 올 때까지(또는 '기각' 이 보일 때까지) Play 를 이어 둔다** — Play 를 끝내면 감시와 판도 끝난다(3.6).
- 결과 기대: 지금 학습 조리법이면 판은 거의 다 '기각 — 게임 두뇌 그대로' 로 끝날 것으로 `LIVE_GATE.md` (10) 에 미리 적혀 있다. 이 설계는 '바뀜을 알아채고 다시
  배우고 관문을 거쳐 바꿔 끼우는 길'을 끝까지 잇는 것이고, 통과 여부는 학습 쪽 몫이다.
- 그 판 도중에 진짜 큰 변화(레벨 팀이 또 나무를 크게 바꿈 등)가 오면 끊기는 것은 뜻대로다 — 옛 환경에 맞춘 두뇌는 더 쓸모없다.
- 내보낸 두뇌로 바꾼 뒤에도 기준선은 마지막 자동 스냅숏이므로, 같은 숲에서 다시 쓰지 않는다(파이썬의 '같은 환경 + 새 두뇌' 열쇠에 기대지 않는다 — 그 열쇠는
  날씨 세기까지 들어 조연우 맵에서는 맞지 않는다).

### 2.7 바뀌지 않는 것

- 세계에 넣는 것은 그대로다(세기 포함, 같은 스텝). 이 규칙은 **언제 스냅숏을 쓰나**와 알림만 바꾼다 → 규칙 0·1 의 세계는 비트 단위로 같다(확인 6.3-b).
- 스냅숏 형식 `eco_v3_snapshot` 판 1 그대로(더하기만). 두뇌 감시·교체·되돌리기·`play_id` 그대로.

## 3. (다) Play 때 파이썬 감시 자동 시작

### 3.1 AGENTS.md 원칙과의 관계

- 게임 런타임 추론은 지금처럼 **C++ 네이티브만**이다 — 사슴 결정은 내장·두뇌 파일 가중치를 C++ 가 계산한다. 자동으로 띄우는 것은 **학습 파이프라인(`live.py watch`)을
  따로 띄우는 개발용 도구**다: 추론이 아니고, 게임 스레드를 막지 않으며(띄우기는 몇 ms, 살아 있나 보기는 2 초마다 기다림 없는 `WaitForSingleObject(…, 0)`,
  끝낼 때만 최대 3 초), `#if !UE_BUILD_SHIPPING` 이고, `eco.IntegratedV3.AutoAdapt` 를 켰을 때만, 서버·단독 월드에서만 돈다. 파이썬이 내는 것은 지금처럼
  두뇌 파일뿐이고, 언리얼은 그것을 결정 스텝 경계에서 C++ 가중치로 바꿔 끼운다.

### 3.2 스위치 (개발 빌드, Play 시작 때 읽음)

| 콘솔 변수 | 기본 | 뜻 |
|---|---|---|
| `eco.IntegratedV3.AutoWatch` | 1 | 1 = AutoAdapt 를 따름(켠 Play 에서 띄움), 0 = 띄우지 않음. 명령줄 `-EcoV3AutoWatch=0\|1` |
| `eco.IntegratedV3.AutoWatchPython` | `python` | 파이썬 실행 파일. 경로 구분자가 없으면 PATH 에서 찾아 **전체 경로로 바꿔 기록**한다. `\WindowsApps\` 아래 것(스토어 대역 — 파이썬이 없으면 스토어 창을 띄운다)은 쓰지 않는다. 이 컴퓨터에서는 `C:\Users\Sinhyeok\anaconda3\python.exe` 가 된다(0절) |
| `eco.IntegratedV3.AutoWatchCmd` | (빈 값) | 시험용 명령 덮기 — 실행 파일 뒤 인자 전체. 자리표 `{root}`·`{play}`·`{log}`. 빈 값이면 3.3 기본 |
| `eco.IntegratedV3.AutoWatchDir` | (빈 값) | 작업 폴더. 빈 값 = `<프로젝트>/../herbivore_rl` (`results/v3/live/live.py` 가 없으면 띄우지 않음) |
| `eco.IntegratedV3.AdaptRoot` | (빈 값) | 적응 고리 폴더 하나 = 스냅숏·두뇌·상태 파일·감시 `--root`·기록의 기본. 빈 값 = `Saved/EcoAdapt`. 시험이 실제 폴더를 건드리지 않게 이것 하나만 바꾼다 (`AutoSnapshotOut`·`eco.V3Brain.WatchFolder`·`StatusFile` 은 지금처럼 따로 덮을 수 있다). 명령줄 `-EcoV3AdaptRoot=` |

- 안전장치: 스냅숏 폴더·두뇌 감시 폴더·상태 파일이 모두 `<root>/snapshots`·`<root>/brains`·`<root>/status.json` 이 아니면(사람이 따로 덮은 시험 꾸밈 —
  예 `level_jyu_eco` 스모크) 자동으로 띄우지 않는다: `[EcoV3I] 파이썬 감시 | 안 띄움 — 스냅숏·두뇌·상태 폴더가 한 root 아래가 아니다 (…)`.
  자동 감시가 엉뚱한 폴더를 보는 일을 막는다.
- 자동화 시험 중(`GIsAutomationTesting`)에는 띄우지 않는다.

### 3.3 띄우는 명령

```
작업 폴더: <프로젝트>/../herbivore_rl
<python 전체 경로> -X utf8 -u results/v3/live/live.py watch --root "<root 절대 경로>"
표준 출력·오류: <root>/watch_<play_id>.log
```

- `-X utf8` = `PYTHONUTF8=1` 과 같은 UTF-8 모드다. 편집기 프로세스 환경 변수를 바꾸지 않으려고 깃발로 준다(`live.py` 는 판 자식에게 `PYTHONUTF8=1` 을 스스로 넘긴다).
  `-u` 는 기록이 곧바로 파일에 보이게.
- `--root` 를 늘 준다: 언리얼이 쓰는 폴더와 같게. 실제 폴더면 `Path.resolve()` 가 `DEFAULT_ROOT` 와 같아 `live.py` 의 잠금 규칙이 그대로 걸린다.
- `--existing` 은 주지 않는다: 앞 Play 의 스냅숏으로 배우지 않게(그 두뇌는 `play_id` 가 달라 어차피 거부된다). 감시는 Play 시작 때 뜨고 첫 스냅숏은 빨라야
  `BigSettle` 뒤라 파이썬 시작(토치 불러오기 몇 초)보다 늦다. 옛 동작 규칙(0)으로 시작 몇 초 안에 스냅숏이 나오면 놓칠 수 있다(4절 위험 7).
- 시험용 덮기 예: `eco.IntegratedV3.AutoWatchCmd "-X utf8 -u <scratch>/fake_watch.py --root {root}"` (자식 하나를 띄우고 상태 파일을 쓰는 가짜 감시 — 6.5).

### 3.4 창 없이

- 엔진 `FPlatformProcess::CreateProc(실행 파일, 인자, bLaunchDetached = true, bLaunchHidden = true, bLaunchReallyHidden = true, &Pid, 0, 작업 폴더, 표준 출력, nullptr, 표준 오류)`.
  0절대로 `CREATE_NO_WINDOW` 는 `bLaunchDetached` 까지 참이어야 붙는다 — 콘솔이 창 없이 생기고, 감시가 띄우는 판·학습 자식도 그 숨은 콘솔을 물려받아 창이 없다.
  (`DETACHED_PROCESS` 는 손자가 새 콘솔 창을 띄울 수 있어 쓰지 않는다 — 엔진 주석과 같은 까닭.)
- 구현: 엔진 `CreateProc` 대신 `CreateProcessW` 를 직접 부른다 (`EcoV3WatchLauncher.cpp`, `#if PLATFORM_WINDOWS`): `CREATE_NO_WINDOW | CREATE_SUSPENDED |
  EXTENDED_STARTUPINFO_PRESENT`, 물려줄 손잡이 = 기록 파일·NUL 둘뿐(`PROC_THREAD_ATTRIBUTE_HANDLE_LIST` — 편집기의 다른 상속 가능 손잡이를 넘기지 않는다), 표준 입력 = NUL.
  멈춘 채 만들어 작업 개체에 넣은 뒤 `ResumeThread` 하므로 3.6 의 '넣기 전 경주'가 없다. 그 밖 플랫폼은 띄우지 않는다('이 플랫폼에서는 못 띄움').
- 기록 파일: 윈도에서는 `<root>/watch_<play_id>.log` 를 상속 가능한 손잡이(`CreateFileW`, 읽기·쓰기 공유)로 열어 표준 출력·오류 자리에 넘기고, 띄운 뒤 언리얼 쪽
  손잡이는 닫는다. 파이프(`FPlatformProcess::CreatePipe`)는 쓰지 않는다 — 언리얼이 비우지 않으면(중단점·긴 프레임) 파이썬이 `print` 에서 멈춘다.
  손잡이 넘기기가 막히면 대안은 `cmd.exe /d /s /c ""python" … 1>>"log" 2>&1"`(프로세스 하나 더, 나무 끝내기는 같다).
- 기록 파일은 `watch_*.log` 최근 20 개만 남긴다(띄울 때 오래된 것부터 지움).

### 3.5 중복 방지 (먼저 맞는 것에서 멈춘다)

1. `<root>/live/watch.lock`(live.py 의 잠금) 이 있고 그 `pid` 가 살아 있음 — 프로세스 이름이 `python*.exe` 이고 시작 시각이 잠금의 `create_time` 과 0.5 초 안
   (psutil 의 `create_time` 과 같은 윈도 `GetProcessTimes` 값) → 띄우지 않는다: `[EcoV3I] 파이썬 감시 | 이미 돈다 — pid n (watch, 사람이 띄움 — 건드리지 않음)`.
   `what` 이 `round`(사람이 앞에서 돌리는 한 판)여도 같다 — 한 폴더에 고리 하나.
2. 우리 기록 `<root>/watcher.pid` (언리얼이 띄울 때 쓰는 JSON `{pid, create_unix, play_id, editor_pid, exe, args, log, started_utc}`) 의 pid 가 살아 있고 같은
   시작 시각 → 띄우지 않는다(다른 언리얼 프로세스가 막 띄워 아직 잠금을 잡기 전 — 토치를 불러오는 몇 초). 죽은 pid 면 그 파일을 지우고 넘어간다.
3. 이 편집기 프로세스가 이미 띄운 감시(프로세스 전역 관리자 `FEcoV3WatchLauncher` 가 손잡이를 쥠)가 살아 있음 → 그대로 쓴다(같은 Play 안 두 번 부름 막기).
- 그래도 경주가 나면 `live.py` 의 O_EXCL 잠금이 마지막 심판이다: 늦게 뜬 감시는 '다른 실시간 고리' 로 곧바로 끝나고(3.7 표), 언리얼은 잠금 주인을 보여 준다.
- 구현 순서 (`EcoV3Watch::Decide` — 순수 함수, 시험 `Policy.V3.WatchLauncher.Command`): AutoWatch 0 → AutoAdapt 0 → 자동화 시험 중 → 클라이언트 → 폴더 안전장치 →
  이 편집기가 띄운 감시가 삶 → 잠금 주인이 산 python(그 pid 가 `watcher.pid` 의 pid 면 '다른 언리얼', 아니면 '사람') → `watcher.pid` 주인이 삶 → python 없음 → live.py·작업 폴더
  없음 → 띄움. 사람이 띄운 감시면 상태 줄 끝에 ` (사람이 띄운 감시)`.

### 3.6 정리 — 우리가 띄운 감시만, 프로세스 나무째

- 띄우자마자 윈도 작업 개체(Job) 하나를 만들어(`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) 감시를 넣는다. 감시가 띄우는 판·학습 프로세스는 그 작업 개체를 물려받는다
  (`live.py` 는 `CREATE_NEW_PROCESS_GROUP` 만 쓰고 떼어 나가기를 하지 않는다).
- Play 끝(편집기 Play 멈춤·게임 종료 = 서브시스템 `Deinitialize`, 띄운 그 월드일 때만): `TerminateJobObject` → 감시 손잡이를 최대 3 초 기다림 → 손잡이·작업 개체 닫기 →
  `watcher.pid` 지움 → `[EcoV3I] 파이썬 감시 끝냄 | pid n (우리가 띄움) · 학습 자식 포함 프로세스 나무째 · 기록 …`.
  작업 개체는 부모가 먼저 죽어 끊긴 손자까지 끝낸다(`TerminateProc` 나무 걷기는 못 한다). 작업 개체를 못 쓰면(`AssignProcessToJobObject` 실패) `TerminateProc(KillTree)` 로.
  - 10-27 적대적 검토 고침: **Play 중 통합 v3 모드가 꺼지면**(조정자 시작 실패·자원 계약 거부 — `Deactivate` 또는 `bActive` 거짓) 그 뒤 첫 프레임
    (`HandlePreActorTick` → `StopAutoWatchIfInactive`)에 우리가 띄운 감시를 같은 길로 끝낸다. 꺼진 뒤에는 스냅숏·두뇌 교체·감시 살핌(`DrawBrainNotices`)이 모두 멈추는데,
    고치기 전에는 감시와 (이미 받은 스냅숏의) 학습 자식이 Play 끝까지 돌았다. 기록 끝에 까닭이 붙는다: `… · 기록 … · 까닭: Play 끝` / `까닭: 통합 v3 모드가 꺼짐`.
- 편집기가 죽으면 작업 개체 손잡이가 닫히며 감시 나무도 끝난다(고아 감시가 남지 않는다). — 10-27 적대적 검토에서 확인(9.5): 우리가 띄운 `UnrealEditor-Cmd` 를
  밖에서 강제로 끝냈더니(크래시 대역) 진짜 `live.py watch` 와 그 콘솔 호스트가 모두 사라졌다.
- 건드리지 않는 것: 사람이 띄운 감시·판, 다른 워크플로의 파이썬, `live.py` 의 파일(`watch.lock`·`status.json`·`state.json` — 끊긴 잠금은 다음 감시가 `proc_alive` 로 치운다).
  학습 중 끊긴 시도는 `state.json` 에 시도 번호만 오르고 기록 줄이 없다 — 다음 Play 는 `play_id` 가 달라 그 판의 두뇌를 어차피 받지 않는다.
- 남는 경주: `CreateProcess` 와 작업 개체 넣기 사이에 감시가 자식을 띄우면 그 자식은 빠진다. 감시는 시작 몇 초 동안 토치를 불러오고 스냅숏이 와야 자식을
  띄우므로 실제로는 없다(4절 위험 10).
  - 구현: 멈춘 채 만들어 넣은 뒤 깨우므로(3.4 구현) 이 경주는 없다.

### 3.7 실제 폴더 잠금 — 잠겼을 때와 푼 뒤

**(1) 잠겼을 때 (`LIVE.flight_sizes_confirmed` 거짓 — 커밋본 `8f191c0`)**

- 감시는 토치·`adapt` 를 불러온 뒤(몇 초) `plan_from_args` 에서 `SystemExit` 로 끝난다: 종료 코드 1, stderr(→ 기록 파일)에 '1차 사건 숨음 비율 기준의 크기…를 아직
  예비 측정으로 확정하지 않았다 (LIVE flight_sizes_confirmed 거짓, …)'. **잠금·`status.json`·`state.json` 은 쓰지 않는다.**
- 언리얼은 2 초마다 감시 손잡이를 보다가 끝난 것을 알면 종료 코드와 기록 끝 줄(읽기·쓰기 공유로 열어 UTF-8 로 읽음)을 읽어 까닭을 고른다:

| 기록 끝 줄에 든 글 | 상태 줄 | 화면 알림 (한 번, 거부 색) |
|---|---|---|
| `flight_sizes_confirmed` | `적응 고리 \| 파이썬 감시 꺼짐 — 실제 폴더 잠김 (관문 크기 확정 전)` | `파이썬 감시가 끝났다 — 실제 폴더 잠김 (관문 크기 확정 전). 두뇌는 그대로다` |
| `다른 실시간 고리` | 잠금 주인을 다시 읽어 `적응 고리 \| 다른 감시가 돈다 (pid n)` + 그 상태 파일 글 | 없음 |
| 그 밖 (종료 코드 ≠ 0) | `적응 고리 \| 파이썬 감시 꺼짐 — 종료 코드 n (기록 watch_<play>.log)` | `파이썬 감시가 멈췄다 — 기록 watch_<play>.log` |
| 종료 코드 0 | `적응 고리 \| 파이썬 감시 끝남` | 없음 |

- 다시 띄우지 않는다(되풀이 막기). 그 Play 의 나머지는 감시 없는 지금과 같다 — 스냅숏은 쓰이고 두뇌는 오지 않는다. 다른 워크플로가 잠금을 풀면 다음 Play 부터
  감시가 돈다. 파이썬 글이 바뀌어 찾는 말이 없어지면 '그 밖' 줄로 떨어질 뿐이다.

**(2) 푼 뒤 (다른 워크플로 작업 사본 — 변경 기록 (10))**

- 감시는 정상으로 뜨고(`status.json` '스냅숏 기다림 — 환경이 바뀌면 언리얼이 씀'), 감시 기록에 '실제 폴더: 판을 돌리는 지금 두뇌 묶음 = route5 … — 그 밖(obs21 —
  게임 기본 내장 R1b-F 포함)은 거부' 줄을 남긴다.
- AutoAdapt Play 는 기본으로 **내장 두뇌(판 0, R1b-F — 묶음 obs21)에서 시작**한다(`OnWorldBeginPlay`, `eco.V3Brain.Startup` 이 비었을 때). 그래서 그대로 Play 하면
  큰 변화 스냅숏이 와도 판이 변환 전에 거부되고 상태 줄이 `적응 고리 | 거부 — 지금 두뇌 묶음 obs21 은 실제 폴더 관문 크기 미확정 …` 이 된다. 그 환경은 처리한 것으로
  적혀 같은 Play 안에서 다시 하지 않는다. 다시 배우기를 보려면 **판 5 두뇌로 시작**한다: `-EcoV3Brain=v3_r7_g995_s1_20m` 또는 `eco.V3Brain.Startup v3_r7_g995_s1_20m`(8절).
- 언리얼은 이 묶음 규칙을 C++ 에 다시 적지 않는다(파이썬 관문 규칙이 바뀌면 어긋나므로). 파이썬이 쓰는 '거부' 상태 글을 그대로 보인다. 덤으로 Play 시작 기록에 한 줄만
  남긴다: `[EcoV3I] 파이썬 감시 | 참고: 실제 폴더 고리는 묶음마다 관문 크기 확정 여부가 다르다 — 거부가 보이면 LIVE_GATE.md 변경 기록 (10)` (지금 두뇌가 내장일 때만).
- 10-29: 기본 두뇌가 R7e(판 5)가 되어 기본 AutoAdapt Play 는 위 '거부' 없이 실제 폴더에서 판을 돈다. 참고 줄은 이제 **시작 두뇌가 판 5 가 아닐 때만**
  (`eco.V3Brain.Startup builtin`·관측 21 파일 등) `[EcoV3I] 파이썬 감시 | 참고: 시작 두뇌 <id> 는 마스크 판 n 다 — … 기본 두뇌 R7e(판 5)로 시작하려면 eco.V3Brain.Startup 을 비우거나 default`
  로 남긴다 ([LIVE_ADAPT_SPEC.md](LIVE_ADAPT_SPEC.md) 5.6).

### 3.8 상태 줄 '적응 고리 | …' 고르기 (위에서부터)

| 감시 상태 | 보이는 글 |
|---|---|
| 우리가 띄움, 끝남 | 3.7 표 |
| 우리가 띄움, 살아 있음, `status.json` 의 `updated_unix` < 띄운 시각 | `파이썬 감시 켜는 중 (n초)` — 앞 Play 가 남긴 옛 글(120 초 안이면 '학습 중 …'으로 보였을 것)을 보이지 않는다 |
| 사람이 띄움 (3.5-1) | 지금처럼 `status.json` 글 + ` (사람이 띄운 감시)` |
| 띄우지 못함 (python 없음·live.py 없음·폴더 안전장치) | `파이썬 감시를 못 켬 — <까닭>` |
| 그 밖 | 지금처럼 (`EcoV3Brain::LiveStatusText`) |

- 구현: `UEcoPolicyV3IntegratedSubsystem::WatchStatusText`. 다른 언리얼 프로세스가 띄운 감시면 ` (다른 언리얼 프로세스가 띄운 감시 pid n)`, 띄우기 실패(CreateProcess·기록 파일)도
  '못 켬' 줄. 글이 바뀌면(켜는 중 초 세기는 한 번) 기록 `[EcoV3I] 적응 고리 감시 | …` — 헤드리스 증거(9절 E1~E4).

### 3.9 PIE 여러 번·여러 프로세스·크래시

- PIE 마다: 시작 때 띄우고 끝에 끝낸다. 그때마다 파이썬 시작(몇 초)이 든다. 앞 Play 의 판은 끝나며, 그 두뇌는 `play_id` 가 달라 받지 않는다(지금 규칙).
- 한 프로세스 PIE(리슨·데디케이티드 + 클라이언트들): 서버 월드만 서브시스템이 켜지므로 하나만 띄운다. 따로 된 프로세스면 서버 프로세스만 띄운다(클라이언트는 `NM_Client`).
- 헤드리스 여러 판을 같은 root 로 함께 돌리면 첫 판만 띄운다(3.5). 시험은 판마다 `AdaptRoot` 를 따로 준다.
- 편집기 크래시: 작업 개체가 감시 나무를 끝낸다. `watcher.pid` 는 남지만 다음 Play 가 죽은 pid 로 보고 지운다. `live/watch.lock` 도 남지만 다음 감시가
  `proc_alive` 로 치운다 (10-27 적대적 검토 9.5 — 한 `-game` 프로세스에서 예약 `open` 으로 Play 셋을 이어 진짜 감시가 매번 '감시 시작'까지 떴다).

## 4. 위험·열린 질문

1. **복제 틈** (1.6): 다 자람 순간과 클라이언트 `OnRep_Mature` 사이의 보정. 줄이는 법은 1.6 '빼는 순서' 2.
2. **나무 메시 굽기**: 숲 메시 `/Game/SHC/Fab/Realistic_Beech_Tree_3D_Vegetation/Beech_Tree`(팀 에셋 — 읽기만)는 그 메시를 가리키는 맵(통합 맵 레벨 나무)과
   함께만 구워진다. 패키지 빌드에서 다른 맵으로 이 모드를 쓰면 메시가 없을 수 있다 → 줄기 막이만 보이고 기록에 적는다. 편집기·`-game` 비패키지 실행은 영향 없음.
   굽기 목록에 넣을지는 팀 설정(`DefaultGame.ini`)이라 이번에 하지 않는다.
3. **자리 정할 때의 지형**: 시작 때 무대 땅이 다 불려 있어야 같은 자리가 나온다. 월드 파티션 맵에서 무대 끝 땅이 늦게 불리면 그 그루를 빼게 되고 실행마다 다를 수
   있다 → 6.3-c 에서 두 판의 자리 줄이 같은지 본다. 다르면 '가운데 점이 안 맞은 그루는 다 자람 단계 때 다시 잰다'로 바꾼다.
4. **다 자랄 때 폰이 줄기 안**: 캐릭터 이동이 겹침을 풀어 밀어낼 것으로 본다(확인 6.4).
5. **'진행 중' 기다림의 일반화**: 레벨 팀은 진행 중 표시를 주지 않는다. 그때는 `BigSettle` 묶기만 돈다 — 팀 바뀜 간격이 20 초보다 길면 판이 끊길 수 있다.
   팀 작업을 볼 때 `BigSettle` 기본을 다시 정하거나 `SetLevelChangeHold` 를 쓰게 한다.
6. **스냅숏 날씨 = 쓰는 순간 날씨**: 조연우 맵에서는 비가 오가므로, 숲 스냅숏을 쓴 순간이 비였으면 파이썬은 '비 세계'로 배운다(파이썬 세계는 고정 날씨). 기준선 종류나
   그 지역 '주된 종류'를 적어야 하는지는 파이썬 담당과 정할 일이다(이번에는 그대로).
7. **감시 시작 전 스냅숏**: `cut = 감시 시작 시각` 이라 감시가 뜨기 전에 쓴 스냅숏은 보지 않는다. 큰 변화 규칙에서는 첫 스냅숏이 20 초 넘게 뒤라 문제없고, 옛 규칙(0)에서
   시작 몇 초 안의 바뀜은 놓칠 수 있다(기록에 남음).
8. **잠긴 폴더 글 찾기**: 3.7 은 파이썬 글의 `flight_sizes_confirmed` 에 기댄다. 다른 워크플로가 글을 바꾸면 '그 밖'으로 떨어진다(기능은 같음).
9. **CPU**: 학습 워커 수 = CPU − 6(`default_workers`). 편집기·게임 프레임이 떨어질 수 있다(지금도 같음). 헤드리스 빠른 실행에서는 두뇌가 시뮬레이션 시간으로 더 늦게 온다.
10. **작업 개체**: 편집기가 이미 다른 작업 개체 안이어도(디버거·런처) 윈도 8 뒤는 겹친 작업 개체를 받는다. 넣기 전 경주는 3.6. — 구현은 멈춘 채 넣어 경주가 없고,
    넣지 못하면 기록에 `작업 개체 못 씀` 으로 남기고 끝낼 때 엔진 `TerminateProc(KillTree)` 로 프로세스 나무를 걷는다.
11. **같은 root 여러 프로세스**: 3.5 의 pid 확인과 파이썬 O_EXCL 잠금으로 막는다. 늦은 쪽은 '다른 감시' 로 보인다.
12. **PIE 마다 판이 버려짐**: 사용자 결정대로다. 같은 레벨 바뀜을 여러 Play 에 걸쳐 배우고 싶어지면 감시를 Play 밖에서 사람이 띄우면 된다(3.5-1 로 건드리지 않음).
13. **기존 시험**: 기본 규칙이 1 로 바뀌므로 `AdaptiveEcosystem.Policy.V3.EnvWatch.AutoSnapshot`(판마다 한 번을 보는 시험)은 `AutoSnapshotRule 0` 을 걸고 되돌리게
    고친다. 세기만 바뀐 판의 알림을 세는 시험이 있으면 `EnvNoticeMinor 1` 을 건다. — 고쳤다 (알림을 세는 시험은 없었다).
14. **먹이**: 메마른 땅이 숲이 되어도 먹이 격자는 그대로다(팀 자원 계약 — 스텝 밖 용량을 바꾸는 길이 없다). 이야기로는 어색하지만 이 모드의 범위 밖이다.
15. **기본 두뇌는 실제 폴더에서 거부됨** (3.7-2): 잠금을 푼 작업 사본은 판 5 묶음만 받는다. 기본 AutoAdapt Play(내장 R1b-F)로는 숲이 자라도 두뇌가 바뀌지 않는다.
    사용자에게 '판 5 두뇌로 시작'을 쓰는 법(8절)으로 알린다. 내장 두뇌 묶음(obs21)의 예비 측정·크기 확정은 학습 쪽 일이다.
16. **다른 워크플로 변경이 아직 커밋 전**: 이 문서의 3.7-2·8절은 작업 사본 기준이다. 그쪽 커밋이 달라지면 Build 단계에서 다시 읽고 고친다.
    — 10-27 그쪽이 `2708a78` 로 커밋했다(작업 사본과 같은 규칙 — 실제 폴더는 판 5 묶음만, 관측 18·21 지금 두뇌는 변환 전 거부). 그래서 지금 실제 폴더에서 자동 감시는
    잠기지 않고 뜨며, 기본 AutoAdapt Play(내장 R1b-F)의 스냅숏은 '거부' 로 보인다 — 다시 배우기를 보려면 판 5 두뇌로 시작한다(8절). 3.7-1 '잠김' 줄은 커밋 `8f191c0` 이하나
    잠금을 다시 걸 때의 길로 남는다(9.3 에서 가짜 스크립트로 확인).
    — **10-29 풀림**: 기본 두뇌가 R7e(판 5, 묶음 route5)라 기본 AutoAdapt Play 의 스냅숏을 실제 폴더 고리가 받는다(LIVE_ADAPT_SPEC.md 5.6). 내장 R1b-F 로 시작한 Play 만 15 그대로다.

## 5. 작업 목록 (Build 단계)

**10-27 모두 했다** — 실제 파일·시험 이름은 9.1. 표와 다른 점: 휴면 대신 1 Hz 갱신(A1), 묘목 '돋을 차례 표시' 없이 프레임 앞에서 스텝을 봄(A2), 큰 변화 규칙은 새
`EcoV3BigChange.h` 순수 함수(B1), `CreateProc` 대신 `CreateProcessW`(C1), 상태 줄 고르기는 `EcoV3Brain.cpp` 가 아니라 서브시스템 `WatchStatusText`(C2), T2 는 새 파일
`EcoV3BigChangeTest.cpp` 의 `AutoSnapshot.BigRule`·`EnvWatch.BigRule`(옛 동작 `.Each` 는 고친 `EnvWatch.AutoSnapshot` 이 본다 — 세기만 바뀐 알림은 화면이 없는 시험이라
기록 줄로 9.3 에서 봤다), T3 에 윈도 프로세스 시험 `WatchLauncher.Process` 를 더했다.

| # | 일 | 파일 |
|---|---|---|
| A1 | 숲 나무 액터 `AEcoV3ForestTree`: 두 메시 컴포넌트, 복제 칸, `OnRep_Plan`·`OnRep_Mature`, 자람 Tick(데디 끔), `SetMature()`, 휴면 | `S/AI/Policy/EcoV3ForestTree.{h,cpp}` (새) |
| A2 | 설정·명령줄(1.2), 계획(1.4 — `TryCreateContexts` 성공 뒤), 돋을 차례 표시·`HandlePreActorTick` 에서 놓기, `ForestStepBoundary()`(다 자람·겹침 빼기·나무만 읽기), 숲 줄 알림, `ForestInfo`, 스냅숏 `env.forest` | `EcoV3EnvWatch.cpp`(또는 새 `EcoV3ForestGrowth.cpp`), `EcoPolicyV3IntegratedSubsystem.{h,cpp}`, `EcoV3Snapshot.cpp` |
| A3 | `PollEnvironment(bForce, bTreesOnly)`·출처 `forest_growth` 표시 | `EcoV3EnvWatch.cpp` |
| A4 | 처리기 스텝 고리: `HasPendingEnvChange` 앞에 `Sub->ForestStepBoundary()` | `EcoPolicyV3IntegratedProcessors.cpp` |
| A5 | `Test.RemoveTrees` 숲 나무 빼기, `Test.AddTrees` 피할 원판에 숲 자리 | `EcoV3EnvWatch.cpp` |
| B1 | 스위치(2.2), 기준선·대칭차·종류 시작·바뀜 시계·기다림 상태, `SetLevelChangeHold` | `EcoV3Snapshot.cpp`, `EcoV3EnvWatch.cpp`(`ApplyEnvChange` 셈), 서브시스템 헤더 |
| B2 | `MaybeAutoSnapshot` 규칙 1·0 갈림, `why`·`env.rule`·`env.big` | `EcoV3Snapshot.cpp` |
| B3 | 세기만 바뀐 판 알림 끄기(`EnvNoticeMinor`), 상태 줄 '다시 배우기' 칸, 조건 기록 줄 | `EcoV3EnvWatch.cpp`, `EcoPolicyV3IntegratedSubsystem.cpp` |
| C1 | `FEcoV3WatchLauncher`(프로세스 전역): 명령 만들기, python 찾기(WindowsApps 거부), 폴더 안전장치, 중복 방지(3.5), `CreateProc`(3.4)·기록 손잡이·작업 개체, 살핌·끝 까닭 읽기, 끝내기(3.6), `watcher.pid` | `S/AI/Policy/EcoV3WatchLauncher.{h,cpp}` (새, 윈도 부분 `#if PLATFORM_WINDOWS`) |
| C2 | 훅: `OnWorldBeginPlay`(PlayId 뒤)·`DrawBrainNotices`(2 초 살핌, 그릴 수 없는 실행도)·`Deinitialize`. 스위치 3.2, `AdaptRoot` 로 기본 폴더 셋 묶기 | `EcoPolicyV3IntegratedSubsystem.cpp`, `EcoV3Brain.cpp`(상태 줄 3.8), `EcoV3Snapshot.cpp`(`AutoSnapshotPath` 기본) |
| T1 | 자동화: `Policy.V3.ForestGrowth.Plan`(같은 씨 같은 자리·규칙 지킴·목표 수), `.Schedule`(돋음·다 자람 스텝, 묘목은 줄기로 안 셈, 다 자람 묶음 `나무 a→b`·출처), `.Off`(끔이면 아무것도 없음), `.Refuse`(1.8) | `S/AI/Policy/Tests/EcoV3ForestGrowthTest.cpp` (새) |
| T2 | 자동화: `Policy.V3.AutoSnapshot.BigRule`(+6 없음, +12 기다림, 다 자람 뒤 20 초에 한 번, 세기만 없음, 종류 < 120 초 없음·≥ 120 초 있음, 되돌아온 종류 없음, 상한), `.Each`(규칙 0 = 옛 동작), `.MinorNotice` | `EcoV3EnvWatchTest.cpp` 고침·더함 |
| T3 | 자동화(프로세스 없이 순수 함수): 명령 글·자리표, PATH 찾기·WindowsApps 거부, 잠금 JSON 읽기, 기록 끝 줄 → 까닭, 폴더 안전장치 | `S/AI/Policy/Tests/EcoV3WatchLauncherTest.cpp` (새) |
| D1 | 문서: LIVE_ADAPT_SPEC 2절(`forest_growth`·`env.rule`·`env.big`·`env.forest`), 5.2(규칙), 5.3(숲 자람), 새 5.5(자동 감시와 AGENTS 원칙), 이 문서 '상태' | `Docs/RL_Policy/` |

## 6. 확인 계획 (창 없이 — `-windowed` 없음, OS 키 메시지 없음)

결과는 9.3. 6.4 의 예약 `ForestInfo` 대신 다 자랄 때 나무마다 남기는 기록 줄(서버·클라이언트 같은 꼴)로 견줬고, 실시간 판 길이는 숲 시간표를 줄여 80~85 초로 했다.

공통: UBT 두 판(기본 적응 unity·`-DisableAdaptiveUnity`), 자동화 `UnrealEditor-Cmd … -ExecCmds="Automation RunTests AdaptiveEcosystem;Quit" -unattended -nullrhi -NoSound
-ini:Engine:[ConsoleVariables]:eco.IntegratedPolicyVersion=1` 실패 0. 측정 실행은 `UnrealEditor-Cmd <uproject> <맵> -game -NullRHI -unattended -nosplash -nopause
-NoSound -DisablePlugins=Bridge,Fab -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=20010` 에 `-benchmark -fps=30 -seconds=N`(결정성) 또는 실시간.
화면이 필요하면 `-RenderOffscreen`. 모든 측정은 `-EcoV3AdaptRoot=<scratch>/…` 로 실제 `Saved/EcoAdapt` 를 건드리지 않는다(6.6 만 예외 조건부).

### 6.1 빌드·자동화
- 위 공통. 새 시험 T1~T3 와 고친 `EnvWatch.AutoSnapshot` 포함.

### 6.2 숲 자람 (팀 통합 맵 `/Game/Map/LV_Ecosystem_IntegrationTest`, 단독, `-benchmark -fps=30 -seconds=220 -EcoV3ForestGrowth`)
- 기록에 묘목 30·70·110·150 초, 다 자람 50·90·130·170 초(전역 스텝 375·675·975·1275), `환경 바뀜 #1~#4 | Barren: 나무 0→6 … 18→24 (출처 forest_growth)`.
- `eco.IntegratedV3.EnvInfo`(예약 `-EcoV3TestAt=60 -EcoV3TestCmd="eco.IntegratedV3.EnvInfo"`)로 메마른 땅 무대 안 줄기 6·세계에 넣은 줄기 6.
- 묘목 동안 줄기로 세지 않음: 40 초 `EnvInfo` 에 줄기 0(묘목 6 이 서 있어도).

### 6.3 결정성·'끄면 같음'
- a. **끔 = 지금과 바이트 같음**: 같은 시드 121 초 `[EcoV3Obs]` 사슴 줄(343218 개)을 `ae91f90` 빌드와 견준다(10-27 `TeamWeatherStart` 확인과 같은 방법).
- b. **규칙 0·1 세계 같음**: `-EcoV3AutoAdapt -EcoV3AutoWatch=0` 으로 `AutoSnapshotRule 0`·`1` 두 판의 사슴 줄이 바이트 같고, 스냅숏 수만 다름.
- c. **숲 켬 같은 시드 두 판**: `-fps=30` 두 판의 사슴 줄·자리 줄·다 자람 스텝이 바이트 같음. `-fps=20` 한 판도 다 자람 스텝·`환경 바뀜` 줄이 같음(프레임 나눔 무관).

### 6.4 복제 (같은 컴퓨터 127.0.0.1, 실시간, 10-27 하늘 확인과 같은 꼴)
- 리슨 호스트(`-game -NullRHI …?listen`) + 클라이언트 1(`-game -NullRHI 127.0.0.1`), 데디케이티드(`-server`) + 클라이언트 2, 각 200 초, 서버에 `-EcoV3ForestGrowth`.
- 예약 `eco.IntegratedV3.ForestInfo` 를 서버·클라이언트에서 60·100·200 초에: 클라이언트 액터 수 = 서버 놓은 수, `bMature` 수 같음, 줄기 변환 해시 같음, 클라이언트 줄기
  충돌 켬 = `bMature`.
- 클라이언트 폰 보정: 예약 콘솔 명령으로 폰을 다음 다 자람 자리로 옮겨(개발 빌드 치트 명령 — 키 메시지 없이. 치트 명령이 막혀 있으면 이 항목은 빼고 그렇게 적는다)
  다 자람 전후 서버 보정 기록(`LogNetPlayerMovement` 경고) 수를 센다. 다 자랄 때 폰이 줄기 안이면 몇 프레임 안에 밖으로 나오는지(위치 기록).
- 보이는 창 0 개(0.25 초마다 언리얼 프로세스 창 찾기 — 하늘 확인과 같음).

### 6.5 큰 변화 규칙·자동 감시 (가짜 감시로 — 다른 워크플로의 파이썬과 실제 폴더를 건드리지 않음)
- 가짜 감시 `<scratch>/fake_watch.py`: `--root` 받아 `status.json` 을 5 초마다 쓰고 자식 `python -c "import time; time.sleep(3600)"` 하나를 띄움, pid 를 기록.
- 통합 맵 + 숲 + `-EcoV3AutoAdapt -EcoV3AdaptRoot=<scratch>/r1 -ini:Engine:[ConsoleVariables]:eco.IntegratedV3.AutoWatchCmd=…fake…`, `-seconds=230`:
  스냅숏 정확히 하나(190 초 근처, `env.rule` big, `env.big.trees.Barren` 24), 기록 `다시 배우기 조건 됨` 90 초, 가짜 감시 pid 가 기록에 있고 게임 끝 뒤
  그 pid 와 자식 pid 가 모두 없음(`Get-Process -Id` — **기록한 pid 만** 본다). 상태 줄 대신 기록 `[EcoV3I] 적응 고리 | …` 줄로 '켜는 중' → 가짜 글.
- 중복 방지: 미리 가짜 감시를 손으로 띄우고 `<scratch>/r2/live/watch.lock` 에 그 pid·시작 시각을 적은 뒤 게임 → '이미 돈다 — 건드리지 않음', 게임 끝 뒤에도 살아 있음.
  그 뒤 그 pid 만 끝낸다.
- PIE 여러 번 대신: 한 `-game` 프로세스에서 예약 `open <맵>` 두 번(월드 닫기·새 월드) → Play 마다 띄우고 끝냄, 남는 프로세스 0.
- 조연우 복사 맵(`/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem`, `-EcoEcosystemLife=0 -ExecCmds="eco.HerdMigration 0, setnopec EcoCreatureIntegrationSpawner bEnableVegetation False"`,
  실시간 300 초): 세기만 바뀐 판의 `[EcoV3I] 알림 |` 줄 0, 종류 판 알림 있음, 날씨 때문의 스냅숏 0, 숲 스냅숏 하나.

### 6.6 실제 폴더 (진짜 감시는 실제 폴더에서 띄우지 않는다)
- 10-27 작업 사본은 잠금을 풀었으므로(3.7-2) 진짜 `live.py watch` 를 실제 root 로 띄우면 실제 판·학습이 돌고 `Saved/EcoAdapt/live/` 를 쓴다 — 다른 워크플로의 일과
  겹치므로 **Build 단계 확인에서는 하지 않는다.** 대신:
  - 3.7-1 표: 잠금 글(`… LIVE flight_sizes_confirmed 거짓 …`)을 stderr 에 쓰고 종료 코드 1 로 끝나는 가짜 스크립트로 → 상태 기록 '실제 폴더 잠김', 알림 한 번, 다시 안 띄움.
  - 3.7-2: 가짜 감시가 `status.json` 에 `state: refused`·'거부 — 지금 두뇌 묶음 obs21 …' 글을 쓰게 해 상태 줄이 그 글을 그대로 보이는지.
  - 진짜 감시 + 시험 root(`-EcoV3AdaptRoot=<scratch>/real` 과 `AutoWatchCmd` 로 `--root {root}` + 시험 크기 깃발 — 시험 폴더라 받아진다)는 학습이 CPU 를 많이 쓰므로
    다른 워크플로의 파이썬이 다 끝난 뒤, 사용자가 원할 때만 한 번(예: `--steps 20000 --judge-seeds 35000-35001 … --workers 4`, 10-25 스모크와 같은 꼴).

## 7. 구현 뒤 고칠 문서

- [LIVE_ADAPT_SPEC.md](LIVE_ADAPT_SPEC.md): 2절 `source` 에 `forest_growth`, `env.rule`·`env.big`·`env.forest` 칸 / 5.2 자동 스냅숏 규칙 1·0 / 5.3 숲 자람 모드 /
  새 5.5 파이썬 감시 자동 시작(3.1 의 AGENTS 원칙 문장 포함) / 0절 고리 그림에 '큰 변화만'·'자동 감시'. — **고쳤다 (10-27).**
- 이 문서: 맨 위 '설계만' → 구현 커밋·확인 결과. — **고쳤다 (9절).**
- 고치지 않은 것: `herbivore_rl/results/v3/live/README.md` 의 '감시를 먼저 띄운다' 쓰는 법 — 그 폴더는 다른 워크플로가 작업 중이라 읽기만 했다. 사람이 먼저 띄워도 언리얼은
  그 감시를 쓰므로(3.5) 그대로 맞다. AutoAdapt Play 가 먼저면 언리얼이 띄운다.

## 8. 쓰는 법

- 편집기: Play 전에 콘솔 `eco.IntegratedPolicyVersion 3` · `eco.IntegratedV3.AutoAdapt 1` · `eco.IntegratedV3.ForestGrowth 1` · `eco.V3Brain.Startup v3_r7_g995_s1_20m`
  (실제 폴더 고리가 판을 도는 판 5 두뇌 — 3.7-2) → Play. 파이썬 감시는 저절로 뜨고 Play 를 멈추면 저절로 끝난다. 사람이 감시를 따로 띄워 두었으면 그것을 쓴다.
  10-29 부터 기본 두뇌가 R7e 라 `eco.V3Brain.Startup …` 은 빼도 된다(적응 고리 Play 는 늘 기본 두뇌 판 0 에서 시작 — LIVE_ADAPT_SPEC.md 5.6).
- 독립형·헤드리스: `-EcoIntegratedV3 -EcoV3AutoAdapt -EcoV3ForestGrowth -EcoV3Brain=v3_r7_g995_s1_20m` (+ 창 없이 `-NullRHI` 또는 `-RenderOffscreen`). 10-29 부터 `-EcoV3Brain=` 은 빼도 된다.
- 보는 것: 숲 줄 '숲이 자라는 중 — 메마른 땅 나무 12/24', 상태 줄 '다시 배우기까지: …' → 190 초쯤 '스냅숏 #4 내보냄 → 파이썬 학습 대기' →
  '적응 고리 | 학습 중 …' → '새 두뇌 — 판 1 …' 또는 '기각 — 게임 두뇌 그대로'.
- 끄기: `eco.IntegratedV3.ForestGrowth 0`(다음 Play), 자동 감시만 끄기 `eco.IntegratedV3.AutoWatch 0`, 옛 스냅숏 규칙 `eco.IntegratedV3.AutoSnapshotRule 0`,
  세기 알림 되살리기 `eco.IntegratedV3.EnvNoticeMinor 1`.
- 시험 폴더로 돌리기: `-EcoV3AdaptRoot=<폴더>` 하나로 스냅숏·두뇌·상태 파일·감시 `--root` 가 모두 그 폴더로 간다(실제 `Saved/EcoAdapt` 를 건드리지 않음).
  가짜 감시로 보기: `"-EcoV3AutoWatchCmd=-X utf8 -u <가짜>.py --root {root} --play {play}"`.
- 보기: `eco.IntegratedV3.ForestInfo`(숲 자리·다 자람·줄기 변환 지문), `eco.IntegratedV3.EnvInfo` 첫 줄(다시 배우기 진행·숲 나무 수).

## 9. 구현 기록 (10-27)

### 9.1 바꾼 파일 (`S/` = `AdaptiveEcosystem/Source/AdaptiveEcosystem/`)

| 파일 | 한 일 |
|---|---|
| `S/AI/Policy/EcoV3ForestGrowth.h` (새) | 숲 자람 순수 계획: 설정·값 자르기, 시간표(초 → 전역 스텝 반올림), 자리 고르기 `PlanSlots`(Test.AddTrees 규칙), 묘목 크기 몫 |
| `S/AI/Policy/EcoV3ForestGrowth.cpp` (새) | 콘솔 변수, 계획(`PlanForest` — 거부 까닭), 묘목 놓기(`ForestPreActorTick`), 다 자람(`ForestStepBoundary` — 겹침 빼기·나무만 다시 읽기), 숲 화면 줄, `eco.IntegratedV3.ForestInfo` |
| `S/AI/Policy/EcoV3ForestTree.{h,cpp}` (새) | 복제 숲 나무 액터 `AEcoV3ForestTree` (계획 구조체 `FEcoV3ForestPlan`, `bMature`, 자람 그리기, 다 자람 기록 줄, 클라이언트 화면 줄) |
| `S/AI/Policy/EcoV3BigChange.h` (새) | '큰 변화만' 순수 규칙 (대칭차·날씨 종류·묶기·기다림·상한·기준선·상태 줄 글) |
| `S/AI/Policy/EcoV3WatchLauncher.{h,cpp}` (새) | 감시 명령·python 찾기·잠금/pid 파일·끝 까닭·폴더 안전장치·판정(순수), 윈도 `CreateProcessW` + 작업 개체·살핌·끝내기·기록 정리 |
| `S/AI/Policy/EcoV3EnvWatch.cpp` | `PollEnvironment(bForce, bTreesOnly)`·출처 `forest_growth`, `ApplyEnvChange` 의 큰 변화 셈·세기만 바뀐 묶음 알림(`eco.IntegratedV3.EnvNoticeMinor`), Test.AddTrees 숲 자리 피함·Test.RemoveTrees 숲 나무 뺌, EnvInfo 첫 줄. 10-27 확인 고침: 큰 바뀜과 한 묶음에 든 세기만 바뀐 지역은 알림 글에서 뺌(9.4) |
| `S/AI/Policy/EcoV3Snapshot.cpp` | `AutoSnapshotRule`·`BigTrees`·`WeatherHold`·`BigSettle`·`BigMaxWait`·`AdaptRoot` 콘솔 변수, `MaybeAutoSnapshot` 규칙 1·0, `env.rule`·`env.big`·`env.forest`, `AdaptRootDir`·`AutoSnapshotDir` |
| `S/AI/Policy/EcoPolicyV3IntegratedSubsystem.{h,cpp}` | 새 멤버·API, `AutoWatch*` 콘솔 변수, 명령줄 시작값, Play 시작(숲 설정·적응 폴더·감시 띄우기)·끝(감시 끝냄·숲 지움), 프레임 앞 숲, 지역 세계 뒤 숲 계획, 기준선, 상태 줄 칸. 10-27 확인 고침: 마지막 환경 알림 글 `GetLastEnvNotice` (자동화가 본다) |
| `S/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp` | 스텝 고리 `HasPendingEnvChange` 바로 앞에 `Sub->ForestStepBoundary()` |
| `S/AI/Policy/Tests/EcoV3BigChangeTest.cpp` (새) | `Policy.V3.AutoSnapshot.BigRule`(순수), `Policy.V3.EnvWatch.BigRule`(서브시스템·스냅숏 파일; 10-27 확인 고침 뒤 1b 장면 — 나무 +2 와 세기만 바뀜 한 묶음의 알림 = 나무만, 규칙 0 은 옛 글) |
| `S/AI/Policy/Tests/EcoV3ForestGrowthTest.cpp` (새) | `Policy.V3.ForestGrowth.Plan`·`.Schedule`·`.Off`·`.Refuse` |
| `S/AI/Policy/Tests/EcoV3WatchLauncherTest.cpp` (새) | `Policy.V3.WatchLauncher.Command`(순수 + 이 프로세스 살았나·기록 끝·기록 정리), `.Process`(윈도 — cmd.exe 를 창 없이 띄워 잠김 까닭·작업 개체째 끝냄) |
| `S/AI/Policy/Tests/EcoV3EnvWatchTest.cpp` | `EnvWatch.AutoSnapshot` 은 규칙 0 을 걸고 끝에 되돌린다 (판마다 한 번 = 옛 동작을 본다) |

### 9.2 콘솔 변수 (모두 개발 빌드 `#if !UE_BUILD_SHIPPING`, 명령줄 값은 시작값 — `SetIfUnset`)

| 콘솔 변수 | 기본 | 명령줄 | 언제 읽나 | 뜻 |
|---|---|---|---|---|
| `eco.IntegratedV3.ForestGrowth` | 0 | `-EcoV3ForestGrowth` (`=0\|1`) | Play 시작 | 숲 자람 모드 (시험 모드) |
| `eco.IntegratedV3.ForestRegion` | Barren | `-EcoV3ForestRegion=` | Play 시작 | 자랄 지역 |
| `eco.IntegratedV3.ForestPerStage` | 6 | `-EcoV3ForestPerStage=` | Play 시작 | 한 단계 그루 (1~64) |
| `eco.IntegratedV3.ForestStageSeconds` | 40 | `-EcoV3ForestStageSeconds=` | Play 시작 | 단계 간격 (시뮬레이션 초) |
| `eco.IntegratedV3.ForestGrowSeconds` | 20 | `-EcoV3ForestGrowSeconds=` | Play 시작 | 묘목 → 다 자람 (1~600 초) |
| `eco.IntegratedV3.ForestTarget` | 24 | `-EcoV3ForestTarget=` | Play 시작 | 목표 (1~64) |
| `eco.IntegratedV3.ForestStartSeconds` | 30 | `-EcoV3ForestStartSeconds=` | Play 시작 | 첫 단계 |
| `eco.IntegratedV3.ForestSeed` | −1 | `-EcoV3ForestSeed=` | Play 시작 | 자리 씨 (−1 = 세션 시드) |
| `eco.IntegratedV3.ForestSapling` | 0.15 | `-EcoV3ForestSapling=` | Play 시작 | 묘목 처음 크기 몫 (그리기만) |
| `eco.IntegratedV3.AutoSnapshotRule` | 1 | `-EcoV3AutoSnapshotRule=` | 경계마다 | 1 = 큰 변화만, 0 = 판마다 (옛 동작) |
| `eco.IntegratedV3.BigTrees` | 10 | `-EcoV3BigTrees=` | 경계마다 | 한 지역 원판 대칭차 문턱 |
| `eco.IntegratedV3.WeatherHold` | 120 | `-EcoV3WeatherHold=` | 경계마다 | 바뀐 날씨 종류가 이어져야 하는 시뮬레이션 초 |
| `eco.IntegratedV3.BigSettle` | 20 | `-EcoV3BigSettle=` | 경계마다 | 조건 뒤 큰 변화 바뀜이 없어야 하는 초 |
| `eco.IntegratedV3.BigMaxWait` | 300 | `-EcoV3BigMaxWait=` | 경계마다 | 조건 뒤 기다림 상한 |
| `eco.IntegratedV3.EnvNoticeMinor` | 0 | `-EcoV3EnvNoticeMinor=` | 바뀜마다 | 1 = 세기만 바뀐 판도 화면 알림 (0 이어도 규칙이 돌 때만 끈다) |
| `eco.IntegratedV3.AutoWatch` | 1 | `-EcoV3AutoWatch=` | Play 시작 | 1 = AutoAdapt Play 에서 감시 자동 시작 |
| `eco.IntegratedV3.AutoWatchPython` | python | `-EcoV3AutoWatchPython=` | Play 시작 | 실행 파일 (PATH → 전체 경로, WindowsApps 거부) |
| `eco.IntegratedV3.AutoWatchCmd` | (빈 값) | `-EcoV3AutoWatchCmd="…"` | Play 시작 | 시험용 인자 덮기 (`{root}`·`{play}`·`{log}`) |
| `eco.IntegratedV3.AutoWatchDir` | (빈 값) | `-EcoV3AutoWatchDir=` | Play 시작 | 작업 폴더 (빈 값 = `<프로젝트>/../herbivore_rl`) |
| `eco.IntegratedV3.AdaptRoot` | (빈 값) | `-EcoV3AdaptRoot=` | Play 시작·쓸 때 | 적응 고리 폴더 하나 (빈 값 = `Saved/EcoAdapt`) |

명령: `eco.IntegratedV3.ForestInfo` (서버·단독 = 계획·액터, 클라이언트 = 받은 숲 나무와 줄기 변환 지문).

### 9.3 확인 (창 없음 — 모두 `UnrealEditor-Cmd … -NullRHI`, `-windowed`·OS 키 메시지 없음. AutoAdapt 판은 모두 `-EcoV3AdaptRoot=<scratch>` 라 실제 `Saved/EcoAdapt` 를 건드리지 않았다)

- **빌드**: UBT `AdaptiveEcosystemEditor Win64 Development` 기본 적응 unity·`-DisableAdaptiveUnity` 두 판 성공 (경고 0).
- **자동화**: `Automation RunTests AdaptiveEcosystem` (`-ini:Engine:[ConsoleVariables]:eco.IntegratedPolicyVersion=1`) **263 개 성공, 실패 0** (새 8 개 포함 — 경고는 앞서부터 있던
  `EcoPredEmaTest_None.sav` 읽기 1 개, 예상된 것).
- 공통 조건 (따로 적지 않으면): 팀 통합 맵 `/Game/Map/LV_Ecosystem_IntegrationTest`, `-game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=20010 -EcoV3ObsParityLog=1`, `-benchmark -fps=30`.

| 확인 (6절) | 결과 |
|---|---|
| 6.3-a 끔 = 지금과 바이트 같음 | 121 초 사슴 줄 `[EcoV3Obs]` **343218 개가 바꾸기 전 빌드(`ae91f90` 소스로 지은 편집기, 같은 명령)와 바이트까지 같다** (md5 `6386f290…`). 시작 줄 `숲 자람: 끔` 만 더해졌다 |
| 6.2 숲 자람 (기본값, 200 초) | 묘목 30·70·110·150 초(전역 스텝 225·525·825·1125), `환경 바뀜 #1~#4 \| 50.0·90.0·130.0·170.0초 (전역 스텝 375·675·975·1275) \| Barren: 나무 0→6 … 18→24 (+6 −0) (출처 forest_growth)`, 밀어냄 사슴 0·늑대 0. 예약 `EnvInfo` 40 초: 묘목 6 이 서 있어도 `무대 안 줄기 막이 0 · 세계 원판 0`, 60 초: `줄기 막이 6 · 넣은 줄기 6 · 세계 원판 6` |
| 묘목은 세계에 닿지 않음 | 숲 켠 판과 끈 판의 사슴 줄이 첫 다 자람 경계(전역 스텝 375)까지 같고 그 뒤 `t 376` 결정 지문 줄에서 처음 갈린다 |
| 6.3-b 규칙 0·1 세계 같음 | `-EcoV3AutoAdapt -EcoV3AutoWatch=0` + 숲, 200 초: 규칙 1·0 사슴 줄 561852 개 바이트 같음. 스냅숏은 규칙 1 = **190.0초 (전역 스텝 1425) 하나** (`why` `큰 변화 — 메마른 땅 나무 +24/10 · 날씨 그대로 (기준 전역 스텝 0) · 바뀜 없이 20.0초 · 조건 뒤 100.0초`, `env.rule big`·`env.big.trees.Barren 24`·`env.forest.done`), 규칙 0 = 판마다 넷 (전역 스텝 398·698·998·1298). 조건 기록 `다시 배우기 조건 됨 \| 90.0초 (전역 스텝 675) \| 메마른 땅 나무 +12/10 · 날씨 그대로 \| 기다림: 숲이 다 자랄 때까지` |
| 6.3-c 같은 시드 두 판·fps | fps 30 두 판과 **fps 20** 한 판: 사슴 줄 561852 개 바이트 같음, 다 자람 스텝·환경 바뀜 줄·24 그루 줄기 변환 지문 모두 같음 |
| 6.4 리슨 호스트 + 클라이언트 1 (실시간 80 초, 숲 10 초 시작·15 초 간격·10 초 자람·목표 12) | 호스트 `(리슨 서버)` 와 클라이언트 `(클라이언트)` 다 자람 줄 12 개의 줄기 충돌 켬·줄기 변환 지문이 모두 같다. 실행 중 0.5 초마다 40 번 본 보이는 언리얼 창 0 개 |
| 6.4 데디케이티드 + 클라이언트 2 (실시간 85 초, 같은 숲 설정) | 서버 `(데디케이티드 서버)`·클라이언트 둘의 12 그루 지문이 모두 같고, 리슨 판과도 같다 (같은 씨) |
| 6.5 자동 감시 (가짜 감시 — `AutoWatchCmd` 로 scratch 의 `fake_watch.py`, 숲 켬, 200 초) | `파이썬 감시 \| 띄움 — pid n · C:\Users\Sinhyeok\anaconda3\python.exe -X utf8 -u …` (PATH 에서 찾은 전체 경로, 작업 개체 켬), 상태 기록 `적응 고리 감시 \| 적응 고리 \| 가짜 감시 — 스냅숏 기다림`, 190 초 스냅숏 하나를 가짜 감시가 봄, 게임 끝에 `파이썬 감시 끝냄 \| … (작업 개체)` 뒤 **가짜 감시 pid 와 그 자식 pid 둘 다 없음** |
| 3.7-1 잠긴 폴더 흉내 (`fake_locked.py` — stderr 잠금 글·종료 코드 1, 40 초) | `켜는 중 (0초)` → `파이썬 감시 끝남 \| … 종료 코드 1 · 적응 고리 \| 파이썬 감시 꺼짐 — 실제 폴더 잠김 (관문 크기 확정 전)`, 알림 한 번 `파이썬 감시가 끝났다 — 실제 폴더 잠김 …`, 다시 띄우지 않음, `watcher.pid` 지움 |
| 6.5 중복 방지 (손으로 띄운 가짜 감시가 live.py 꼴 `live/watch.lock` 을 잡음) | `파이썬 감시 \| 이미 돈다 — 사람이 띄움, 건드리지 않음 — pid n (watch, 잠금 …)`, 상태 기록 끝 ` (사람이 띄운 감시)`, 게임(30 초)이 끝난 뒤에도 그 감시가 제 수명(150 초)까지 돌았다 |
| 6.5 Play 여러 번 (한 `-game` 프로세스에서 20 초마다 예약 `open <맵>`, 75 초) | Play 넷 모두 `띄움` → `켜는 중` → `끝냄 (작업 개체)`, 게임 끝 뒤 가짜 감시·자식 pid 8 개 모두 없음 |
| 6.5 조연우 복사 맵 (`/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem`, `-EcoEcosystemLife=0`·식생·이주 끔, AutoAdapt·숲 켬, 300 초) | 환경 판 45 개 가운데 **세기만 바뀐 32 개는 화면 알림 없음** (기록 줄 끝 `세기만 바뀜 — …`), 알림 13 개 = 날씨 종류 9·나무 4. 날씨 때문의 스냅숏 0 (바뀐 종류가 120 초를 넘긴 적 없음), **숲 스냅숏 하나 — 217.7초 (전역 스텝 1633)**: 숲이 170 초에 다 자란 뒤 숲·고지의 종류 바뀜(183.9·197.7 초)이 바뀜 시계를 되돌려 고지 바뀜 + 20 초에 썼다 (2.5 의 '190~210 초' 보다 조금 늦다). 그 순간 고지는 비였다(4절 6 그대로) |

- 하지 않은 것: 6.4 클라이언트 폰 보정 수 세기(치트 명령으로 폰을 다 자랄 자리로 옮기기) — 하지 않았다. 묘목이 20 초 자라 보인 뒤 막히므로 드물 것으로 보지만 확인 전이다(4절 1·4).
  3.7-2 '거부' 글 흉내 — 상태 글을 그대로 보이는 길은 가짜 감시의 '스냅숏 기다림' 글로 같은 코드(`LiveStatusText`)를 봤다. 진짜 `live.py watch` 를 띄운 확인 — 다른 워크플로가
  파이썬 쪽을 쓰는 중이라 하지 않았다(6.6 — 시험 root 로는 9.4 에서 했다). 편집기 PIE — 창이 필요해 하지 않았다(헤드리스 `open` 으로 Play 여러 번만 봤다).
- 결정성 메모: 숲 켠 판의 결정성은 '다 자람을 결정 스텝 경계에서 강제로 읽는 것'에 기댄다. 조연우 맵처럼 팀 날씨를 실시간 주기로 읽는 맵은 원래 같은 시드 바이트 비교가
  안 된다(5.1) — 이번에도 그 맵은 바이트 비교에서 뺐다.

### 9.4 10-27 확인 (구현 커밋 `51130c0` 뒤 실제 실행 — 창 없음)

- 방법: 모두 `UnrealEditor-Cmd <uproject> <맵> -game -NullRHI -unattended -nosplash -nopause -NoSound`(화면 찍기만 `-RenderOffscreen -ResX=1280 -ResY=720`),
  `-windowed`·OS 키 메시지 없음 — 명령은 예약 `-EcoV3TestAt=<초> -EcoV3TestCmd="…"` 과 CSV 프레임 명령(`-csvCaptureFrames=100000000 -csvExecCmds="r<N>:<명령>"`)만 썼다.
  AutoAdapt 판은 모두 `-EcoV3AdaptRoot=<scratch 폴더>` — 실제 `Saved/EcoAdapt` 의 파일 29 개는 확인 전후 크기·고친 시각이 같다. 실행마다 0.25 초마다 보이는 창을
  모두 보고, 우리 언리얼과 그 자손(1 초마다 부모 pid 로 모음)이 가진 새 창을 셌다 — **모든 판 0 개**(사이에 뜬 창은 메신저·탐색기·캡처 도구 같은 사용자 앱뿐).
- 공통: 세션 시드 20010(`-EcoV3Seed=20010`), 사슴 128 × 지역 셋(`-EcoV3DeerPerRegion=128`), `-EcoIntegratedV3`, 숲은 따로 적지 않으면 기본값(6 그루 × 40 초, 묘목 20 초,
  목표 24, 첫 단계 30 초). 같은 컴퓨터에서 다른 워크플로가 헤드리스 언리얼·파이썬을 같이 돌렸다(빌드 때만 잠금 파일로 비킴).
- **찾아 고친 것**: 조연우 복사 맵 실시간 판에서 나무 다 자람과 같은 결정 스텝 묶음에 팀 비 세기만 바뀐 지역이 섞이면 화면 알림이
  `환경 바뀜 #27 — Barren: 나무 0→6 · Barren: 비→비` 처럼 '비→비'를 보였다(400 초 판의 다 자람 넷 가운데 셋 — #27·#56·#104). '큰 변화만' 규칙이 돌 때(세기만 바뀐 알림 끔)
  세기만 바뀐 지역을 알림 글에서 뺀다 — 기록 줄 `[EcoV3I] 환경 바뀜 #n | …` 의 날씨 칸은 그대로. 규칙이 돌지 않으면(자동 스냅숏 끔·규칙 0·`EnvNoticeMinor 1`) 옛 글 그대로다
  (`S/AI/Policy/EcoV3EnvWatch.cpp` `ApplyEnvChange`, 시험용 읽기 `GetLastEnvNotice`, 자동화 `Policy.V3.EnvWatch.BigRule` 1b 장면 — 나무 +2 와 비 0.8→0.9 한 묶음의 알림이
  `환경 바뀜 #2 — Forest: 나무 0→2`, 끝의 규칙 0 장면은 `… Forest: 비→비` 그대로). 세계에 넣는 것·스냅숏·다시 배우기 셈은 바뀌지 않는다.
- 고친 뒤 UBT `AdaptiveEcosystemEditor Win64 Development` 기본 적응 unity·`-DisableAdaptiveUnity` 두 판 성공, 자동화 `Automation RunTests AdaptiveEcosystem`
  (`-ini:Engine:[ConsoleVariables]:eco.IntegratedPolicyVersion=1`) **263 개 성공, 실패 0** (경고 1 = 앞서부터의 저장 파일 읽기).

| 확인 | 명령 (요점) | 결과 |
|---|---|---|
| ① 단계대로 자람·다 자란 뒤에만 세계에 | 팀 통합 맵 `/Game/Map/LV_Ecosystem_IntegrationTest`, `-benchmark -fps=30 -seconds=230 -EcoV3ObsParityLog=1 -EcoV3ForestGrowth -EcoV3AutoAdapt -EcoV3AdaptRoot=<scratch> -EcoV3AutoWatchCmd="-X utf8 -u <scratch>/fake_watch.py --root {root} --play {play}"`, 예약 `eco.IntegratedV3.EnvInfo; eco.IntegratedV3.ForestInfo` 29·40·51·95·175·225 초 | 묘목 30·70·110·150 초(전역 스텝 225·525·825·1125) 6 그루씩 `묘목은 아무것도 막지 않음`, 다 자람 50·90·130·170 초(스텝 375·675·975·1275) `환경 바뀜 #1~#4 \| … Barren: 나무 0→6 … 18→24 (출처 forest_growth · 세계 원판 0→6 …)`. 40 초 `EnvInfo`: 묘목 6 이 서 있어도 Barren `무대 안 줄기 막이 0 · 세계 원판 0`, 51 초 `6 · 6`. 숲 켠 판과 끈 판의 사슴 줄은 Barren `t 376` 결정 지문에서 처음 갈리고 숲·고지 줄은 끝까지 같다 |
| ① 목표에서 멈춤 | 같은 판 175·225 초 `ForestInfo` · 문턱 판 `-EcoV3ForestPerStage=5 -EcoV3ForestTarget=9`·`=10 -EcoV3AutoWatch=0`, 150 초 | `놓음 24 · 다 자람 24 · 묘목 0 · 단계 4/4 다 자람 · 다음 다 자람 전역 스텝 -1`, `다 자랐다 — Barren 나무 24/24 (뺌 0) · 더 돋지 않음, Play 끝까지 그대로`. 문턱 판은 `9/9`·`10/10` 에서 멈춤 |
| ① 큰 변화 규칙 ('나무 +10 넘고 20 초 조용') | 위 두 가지 | 기본: 90 초 `다시 배우기 조건 됨 \| … 메마른 땅 나무 +12/10 · 날씨 그대로 \| 기다림: 숲이 다 자랄 때까지`, 170 초 마지막 다 자람 + 20 초 = **190.0 초(전역 스텝 1425) 하나** (`why` `큰 변화 — 메마른 땅 나무 +24/10 · 날씨 그대로 (기준 전역 스텝 0) · 바뀜 없이 20.0초 · 조건 뒤 100.0초`). 목표 9(+9) → **스냅숏 0**. 목표 10(+10) → 90 초 조건, 숲이 다 자라 기다림 없이 **110.0 초(스텝 825) 하나** |
| ① 같은 씨 두 판 | 위 숲 판 셋 (고치기 전 빌드 둘·고친 뒤 하나) | 230 초 사슴 줄 `[EcoV3Obs]` 644202 개 md5 `efc46a20…` 셋 모두 같다 |
| ① 끄면 같음 | 같은 시드 `-benchmark -fps=30 -seconds=121 -EcoV3ObsParityLog=1`, 숲 끔 | 사슴 줄 343218 개 md5 `6386f290…` — `ae91f90` 빌드 기록(9.3)과 같다 (고치기 전·뒤 빌드 모두) |
| ② 조연우 맵 — 팀 비 주기만 | `/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem` 실시간 400 초(`t.MaxFPS=60`), `-EcoEcosystemLife=0 -ExecCmds="eco.HerdMigration 0, setnopec EcoCreatureIntegrationSpawner bEnableVegetation False"`, `-EcoV3AutoAdapt -EcoV3AutoWatch=0`, 고친 뒤 빌드 | 환경 판 247 = 세기만 234 + 날씨 종류 13. 화면 알림 13 (종류 바뀜만), 세기만 바뀐 판은 기록 줄 `… \| 세기만 바뀜 — 다시 배우기 셈·화면 알림 없음 (eco.IntegratedV3.EnvNoticeMinor 0)` 만. **스냅숏 0** — 비는 약 108 초, 맑음은 약 72 초 이어져 120 초를 넘지 않는다 (예 고지 12.3 초 맑음→비, 120.4 초 비→맑음) |
| ② 숲과 겹침 | 같은 맵·설정 + `-EcoV3ForestGrowth` | 환경 판 247 (세기만 230), 환경 알림 17 (종류 13·나무 4) + 스냅숏 알림 1. **스냅숏 하나 213.1 초(전역 스텝 1598)** `큰 변화 — 메마른 땅 나무 +24/10 · 고지 날씨 맑음→비 20/120초 (기준 전역 스텝 0) · 바뀜 없이 20.0초 · 조건 뒤 123.1초` — 나무 조건으로 썼고 날씨 칸은 아직 20/120 초다. 늦어짐 = 고지 종류 바뀜(193.1 초) + 20 초. 다 자람 묶음 셋(#27·#56·#104)에 세기 바뀜이 섞였는데 알림은 `환경 바뀜 #27 — Barren: 나무 0→6` 처럼 나무만 (기록 줄은 `… \| Barren: 날씨 비 0.22→비 0.27 (출처 team_env)` 그대로). 고치기 전 같은 판은 `… · Barren: 비→비` |
| ③ 리슨 + 클라이언트 1 | 통합 맵 `"<맵>?listen" -game -NullRHI -port=17791` + `127.0.0.1:17791 -game -NullRHI`, 실시간 240 초, 둘 다 `-EcoV3ForestGrowth`. 서버 예약 덤프 45·100·185·205 초, 클라이언트는 CSV 프레임 명령 `r1200:` 로 같은 덤프 — `ForestInfo`·`getall EcoV3ForestTree Plan`·`bMature`·`getall StaticMeshComponent RelativeScale3D\|RelativeLocation\|RelativeRotation Name=TreeMesh`·`… Name=TrunkBlocker` | 클라이언트 다 자람 줄 24 개의 줄기 변환 지문이 서버와 **24/24 같고** 줄기 충돌 켬 24, 서버보다 0.01~0.02 초 늦게. 마지막 덤프: 나무 크기·회전·줄기 막이 자리·크기·계획·`bMature` 24/24 같음, 메시 자리 차 최대 9.2e-5 cm(복제 반올림). 클라이언트 기록에 숲 계획·묘목 돋음 줄 0 개(서버 5 개) — 숲을 따로 키우지 않고 받은 나무만 센다(`숲 자람 (클라이언트) \| 받은 숲 나무 6 · 다 자람 0` → `24 · 24`). 묘목 크기는 클라이언트에서도 0.29 → 1.96 으로 자란다 |
| ③ 데디케이티드 + 클라이언트 2 | `<맵> -server -port=17791` 240 초 + 클라이언트 c1(처음부터)·c2late(`Barren_F11` 다 자란 뒤 = 약 90 초에 들어옴) | 두 클라이언트 모두 지문 24/24 같음·충돌 켬 24, 크기·회전·줄기 24/24 같음, 메시 자리 차 최대 9.9e-5 cm. 늦게 들어온 c2late 는 첫 덤프부터 `12 그루 · 다 자람 12` (다 자란 채로 받음) |
| 자동 감시 — 가짜 감시 | ① 숲 판 (`AutoWatchCmd` 로 scratch `fake_watch.py`) | `파이썬 감시 \| 띄움 — pid n · C:\Users\Sinhyeok\anaconda3\python.exe -X utf8 -u …`, 상태 `가짜 감시 — 스냅숏 기다림`, 끝에 `파이썬 감시 끝냄 \| … 학습 자식 포함 프로세스 나무째 (작업 개체)` 뒤 가짜 감시·그 자식 모두 없음 |
| 중복 방지 — 사람이 띄운 감시 | scratch `fake_watch.py --lock --life 240` 을 먼저 손으로 띄워(`<root>/live/watch.lock`) 같은 root 로 60 초 판 | `파이썬 감시 \| 이미 돈다 — 사람이 띄움, 건드리지 않음 — pid 25440 (watch, 잠금 …)`, 상태 기록 끝 `(사람이 띄운 감시)`. 언리얼이 끝난 뒤에도 그 감시가 살아 있다가 제 수명(240 초, 맥박 120 번)에 스스로 끝났다 |
| 중복 방지 — 언리얼 둘 | 같은 root 로 A(400 초)가 감시를 띄운 뒤 B(60 초) 시작 | B: `이미 돈다 — 다른 언리얼 프로세스가 띄움 — pid 33116`, 상태 끝 `(다른 언리얼 프로세스가 띄운 감시 pid 33116)`. B 가 먼저 끝나도 A 의 감시는 그대로였고 A 끝에 `끝냄`·`watcher.pid` 지움, 남은 프로세스 0 |
| ④ 진짜 `live.py watch` | 통합 맵 실시간(`t.MaxFPS=60`) 170 초, 짧은 숲(`-EcoV3ForestStartSeconds=10 -EcoV3ForestStageSeconds=15 -EcoV3ForestGrowSeconds=10 -EcoV3ForestTarget=12`), `-EcoV3Brain=v3_r7_g995_s1_20m`, `-EcoV3AutoWatchCmd="-X utf8 -u results/v3/live/live.py watch --root {root} --ckpt <scratch> --steps 20000 --judge-seeds 35000-35001 --judge-seeds-g 35000-35001 --horizon 300 --horizon-g 300 --stuck-seeds 35000-35000 --workers 4"` (시험 root — 실제 폴더 아님, 시험 크기) | 상태 줄: `파이썬 감시 켜는 중 (0초)` → 4 초 뒤 `스냅숏 기다림` → 55.1 초 스냅숏(스텝 413, 나무 0→12) → 2.7 초 뒤 `새 환경 — 시도 1 시작` → `학습 중 0/20k` → `후보 판정 0/15 세계` → `기각 — 게임 두뇌 그대로 (1차 사건 숨음 비율 19.8%→20.6% t +0.5 (문턱 +12.71))` (스냅숏부터 52 초 — 변환 4.1·학습과 지금 판정 15.4·후보 판정 26.5 초). **시험 크기(판정 시드 2)라 t 문턱이 커서 관문에서 멈춘다** |
| ④ 시험 내보내기 | 같은 판 + `--force-export` | `exported — 시험 내보내기: 판 1 (관문 기각)` → 언리얼 **94.3 초(전역 스텝 707)** `두뇌 바꿈 \| v3_r7_g995_s1_20m@40d8710d → live_r1_…@06b992e9` (골든 27 사례 최대 로짓 오차 4.77e-06), 알림 `새 두뇌 — 판 1 · … 관문: 시험 내보내기(--force-export) — 관문 기각 …` |
| ④ Play 끝 정리 | 같은 판, `--steps 400000` — 학습·판정 중에 Play 가 끝남 | 끝날 때 상태 `후보 판정 3/15 세계`. 감시·`round`·`train-one`·멀티프로세싱 일꾼 6·`EcoV3Eval` 3 등 자손 15 개 모두 사라짐 |
| ④ 다른 python 그대로 | 판마다 실행 전후 python·`EcoV3Eval` 목록 + 1 초마다 우리 자손 목록 | 다른 워크플로의 python 은 우리 자손 목록에 한 번도 없었고, 그쪽 주 프로세스(예 `r7e_game.py`)는 전후 모두 살아 있었다. 사이에 바뀐 pid 는 그쪽 작업 풀이 스스로 바꾼 것이다(작업 개체는 우리 감시가 띄운 프로세스만 담는다) |
| ⑤ 화면 | 통합 맵 `-RenderOffscreen -ResX=1280 -ResY=720` 실시간(`t.MaxFPS=30`) 235 초, 기본 숲, 내장 두뇌, 진짜 `live.py watch`(시험 root), 예약 `eco.Cam.Region Barren; eco.Cam.Top; eco.Cam.Help`, `-csvExecCmds="r150:shot showui filename=…,r151:shot filename=…"` | 저장소 밖 `week8_assets/forest/` 5 장 — 자라기 전 23 초·중 157 초(18/24 + 묘목 6)·후 173 초(24/24, 같은 자리 위에서), 같은 순간 화면 글(알림 `환경 바뀜 #4 — Barren: 나무 18→24`·`숲이 다 자랐다 — 메마른 땅 나무 24/24`·상태 `다시 배우기: 조건 됨 — 바뀜이 멈추길 기다림 2/20초`), 193 초(`스냅숏 #4 내보냄 → 파이썬 학습 대기`·`적응 고리 \| 새 환경 — 시도 1 시작 (Barren 나무 0→24)`). 이 판의 감시는 190 초 스냅숏을 받아 `기각 (9.7%→9.7%)` 으로 끝났다 |

- 빌드 메모: 리슨·데디 판·문턱 판·진짜 `live.py` 판 셋(①의 문턱, ③, ④)은 고치기 전 빌드(`51130c0`)로 돌렸다. 고침은 알림 글만 바꾸고, 날씨 출처가 없는 통합 맵에서는
  날씨 바뀜이 없어 고친 길을 타지 않는다. 숲 판·끔 판·조연우 맵 두 판·화면 판은 고친 뒤 빌드로 다시 돌렸다.
- 남은 점 (고치지 않음): 막 돋은 묘목(크기 몫 0.15 언저리)은 위에서 보면 몇 초 동안 검은 덩이로 그려진다 — 그리기만의 일이다. 관찰 카메라 칸(오른쪽 위)이 긴 상태 줄의
  끝을 가린다. 클라이언트 캐릭터가 막 자란 줄기에 걸릴 때의 위치 되돌림 수는 여전히 세지 않았다(9.3). 진짜 감시를 실제 폴더(`Saved/EcoAdapt`)에서 띄우는 확인은
  실제 폴더에 파일을 남기지 않기 위해 하지 않았다 — 그래서 '실제 폴더 고리는 판 5 두뇌로 시작한 Play 만'(3.7)의 거부 글은 이번에도 직접 보지 않았다. 편집기 PIE 는 창이 필요해 하지 않았다.

### 9.5 10-27 적대적 검토 (`ae91f90..171c384` C++ 줄 단위 — 창 없음)

- 방법: 새·고친 C++(`EcoV3BigChange.h`·`EcoV3ForestGrowth.{h,cpp}`·`EcoV3ForestTree.{h,cpp}`·`EcoV3WatchLauncher.{h,cpp}`·`EcoV3EnvWatch.cpp`·`EcoV3Snapshot.cpp`·서브시스템·처리기)를
  줄 단위로 읽고 깨 보려 했다. 프로세스 쪽은 엔진 `WindowsPlatformProcess.cpp`·`live.py`(읽기만)와 대조했다. 실행은 모두 `UnrealEditor-Cmd … -game -NullRHI -unattended -nosplash -NoSound`
  (`-windowed`·OS 키 메시지 없음), AutoAdapt 판은 `-EcoV3AdaptRoot=<scratch>` 라 실제 `Saved/EcoAdapt` 를 건드리지 않았다. 판마다 0.25 초마다 보이는 창을 봤다 — 새 창 0 개.
- **찾아 고친 것** — Play 중 통합 v3 모드가 꺼지면(조정자 시작 실패·자원 계약 거부 — `Deactivate` 또는 `bActive` 거짓) 스냅숏·두뇌 교체·감시 살핌(`DrawBrainNotices` 는
  `bActive` 일 때만 불린다)이 모두 멈추는데, 우리가 띄운 감시와 (이미 받은 스냅숏의) 학습 자식은 Play 끝(`Deinitialize`)까지 돌았다. 이제 꺼진 뒤 첫 프레임
  (`HandlePreActorTick` → `StopAutoWatchIfInactive`)에 같은 길(작업 개체째)로 끝낸다. 기록 끝에 까닭: `… · 까닭: 통합 v3 모드가 꺼짐` (Play 끝은 `까닭: Play 끝`).
  사람·다른 언리얼이 띄운 감시는 그대로다. 새 자동화 `AdaptiveEcosystem.Policy.V3.WatchLauncher.Deactivate`(cmd.exe → ping 나무를 서브시스템 주인으로 띄움: 켜진 동안 그대로,
  `RejectResourceContract` 뒤 나무째 끝남·`watcher.pid` 지움). 시험용 `LaunchWatchForTest` 를 더했다(판정 없이 띄움 — `StartForestForTest` 와 같은 꼴).
- **바로잡은 글**: 1.6 '구현' (`R` 은 복제 칸에 있다 — 변환에만 쓰지 않는다), 2.3 표의 바뀜 시계 이름(구현 `LastActivityStep`), LIVE_ADAPT_SPEC 5.3 의 다 자람 기록 꼴
  (`단독|리슨 서버|데디케이티드 서버|클라이언트`), 3.6·3.9 (크래시·꺼짐 정리).
- **고친 뒤**: UBT `AdaptiveEcosystemEditor Win64 Development` 기본 적응 unity·`-DisableAdaptiveUnity` 두 판 성공(경고 0), 자동화(`-ini:Engine:[ConsoleVariables]:eco.IntegratedPolicyVersion=1`)
  **264 개 성공, 실패 0** (새 `Deactivate` 포함, 경고 1 = 앞서부터의 저장 파일 읽기). 숲 끔 121 초 사슴 줄 `[EcoV3Obs]` 343218 개 md5 `6386f290…` — `ae91f90` 기록과 같다.
  보통 Play 끝(한글·빈칸 root, 진짜 감시)은 `파이썬 감시 끝냄 | … (작업 개체) · … · 까닭: Play 끝`, 남은 자손 0.

| 확인 (고치기 전 빌드 `171c384` 로 — 감시 정리 길은 이번 고침과 같은 함수) | 결과 |
|---|---|
| 한글·빈칸 든 `AdaptRoot` + **기본 명령**(진짜 `live.py watch`, 스냅숏 없음 → 학습 없음) | `--root "…/한글 폴더 A"` 따옴표 그대로 떠 `watch_<play>.log` 에 `감시 시작: …\한글 폴더 A\snapshots`, 상태 `켜는 중 (0초)` → `스냅숏 기다림` |
| Play 여러 번 (한 `-game` 프로세스, 예약 `open` 25 초마다) | Play 셋 모두 `띄움` → 다음 `open` 때 `끝냄 (작업 개체)` → 새 감시가 남은 `live/watch.lock`(죽은 pid)을 치우고 `감시 시작` |
| 크래시 대역 — 우리 `UnrealEditor-Cmd` 를 65 초에 밖에서 강제로 끝냄 (그 pid 만) | 그때 돌던 셋째 Play 의 감시와 그 콘솔 호스트가 사라짐(앞 두 Play 의 감시는 Play 가 바뀔 때 이미 끝남 — 남은 자손 0). `watcher.pid`·`live/watch.lock` 은 남는다 — 다음 Play·감시가 죽은 pid 로 보고 치운다(3.9) |
| python 없음 (`-EcoV3AutoWatchPython=C:/nope/python.exe`) | `파이썬 감시 \| 못 켬 — python 없음 — python 실행 파일 C:/nope/python.exe 가 없다`, 상태 `파이썬 감시를 못 켬 — …`, 아무것도 띄우지 않음 |
| 다른 워크플로 python | 판마다 전후 같은 pid 그대로 (우리 자손에 한 번도 없음) |
| 기록 근거 다시 셈 | 9.4 ③ 리슨·데디 기록에서 다 자람 지문 서버·클라이언트 24/24 (c1·c2late 포함) 같음, ② 조연우 맵 환경 판 247·세기만 234/230 — 문서 숫자와 같다 |

- **검토했지만 문제가 아니었던 것** (근거):
  - 끔 = 비트 동일: 끈 Play 에서 새 코드가 하는 일은 설정 읽기·기준선 복사(`BigAddRegion` — 읽기만)·`ApplyEnvChange` 안 `BigState` 셈·알림 글 고르기(규칙이 돌 때만)뿐이다.
    숲 액터·강제 읽기·난수·스텝 경계 호출은 없다(`ForestStepBoundary`·`ForestPreActorTick` 은 `bForestOn` 거짓이면 곧바로 돌아간다). 숲 자리 난수는 따로 된 `FRng` 라 켠 판에서도
    세계 난수를 쓰지 않는다. 위 md5 로 다시 확인.
  - 큰 변화 경계: 정확히 10 은 ≥ 라 조건, 생겼다 지워지면 대칭차 0 → 조건·조건 시각 지움, 종류가 `WeatherHold` 전에 돌아오면 조건 없음(종류 시작 시각은 바뀔 때마다 다시),
    기준선은 자동 스냅숏을 쓸 때만(쓰기 실패여도) 다시 — 주기·콘솔 스냅숏은 아니다. `BigState` 는 서브시스템마다라 Play·PIE 를 다시 시작하면 새로 선다.
  - 숲: 다 자람은 처리기 스텝 고리의 정확한 전역 스텝(`GlobalT ≥ 다 자람 스텝` while — 시계 다시 맞춤으로 스텝이 뛰어도 빠지지 않는다)에서 줄기 충돌·꼬리표를 켜고 같은 경계의
    `ApplyEnvChange` 가 넣는다. 실시간 읽기는 그 사이에 끼지 못한다(다 자람과 넣기가 같은 경계). 클라이언트는 서브시스템이 꺼져 숲을 따로 키우지 않는다(복제 액터만).
  - 감시 창: `CREATE_NO_WINDOW` 숨은 콘솔을 판·학습·`taskkill`·`EcoV3Eval` 자식이 물려받는다(`live.py` 는 `CREATE_NEW_PROCESS_GROUP` 만 쓴다). 남의 프로세스: 끝내는 길은 작업 개체
    (우리가 넣은 감시의 자손만)와 그 대안뿐이고, 잠금·pid 파일은 시작 시각까지 견줘 읽기만 한다.
- **남은 점 (고치지 않음)**:
  1. 작업 개체를 못 쓸 때의 대안 엔진 `TerminateProc(KillTree)` 는 부모 pid 만 보고 걷는다(시작 시각을 보지 않는다) — pid 재사용으로 남의 프로세스를 끝낼 이론상 위험이 있다.
     윈도 8 뒤 겹친 작업 개체를 받으므로 이번 모든 판은 작업 개체 길이었다.
  2. 팀 날씨 출처를 지역 세계가 생긴 **뒤에** 처음 알게 되면(늦은 등록) 그 처음 값이 기준선 종류와 다를 때 종류 바뀜으로 센다 — 그 종류가 `WeatherHold` 넘게 이어지면 레벨이
     바뀌지 않았어도 스냅숏 하나. 지금 두 맵은 해당 없다(조연우 맵은 시작 때 출처를 알아 기준선이 팀 날씨, 통합 맵은 출처 없음).
  3. 숲 자리 땅 높이는 `GroundStageTree`(WorldStatic 채널 선 검사)로 잰다 — 계획 순간 그 자리에 폰처럼 그 채널을 막는 액터가 있으면 나무가 떠 보일 수 있다(세계 원판은 가로
     자리만 쓰므로 세계·결정성은 같다). `Test.AddTrees` 와 같은 길이라 함께 두었다.
  4. 숲 자리는 계획 때의 은신처 원만 피한다 — `ProtectedRefuges` 맵에서 늦게 등록된 은신처 원 안에 숲 줄기가 들 수 있다(다 자랄 때는 다른 줄기와의 겹침만 다시 본다).
  5. 다 자랄 때 겹쳐 뺀 그루가 있으면 클라이언트 화면 줄은 계획 수를 목표로 세어 '자라는 중' 에 머물고, `F00` 을 뺐으면 클라이언트 줄이 없다(화면만 — 네트워크 판에서는
     `Test.AddTrees` 가 거부되므로 레벨 팀이 실행 중에 그 자리에 줄기를 놓을 때만).
  6. 숲 나무를 밖에서 지우면(팀 도구 등) `ForestState` 는 '다 자람' 으로 남는다 — 세계 원판은 환경 감시가 맞추고 숲 셈 글만 어긋난다.
  7. 진짜 판의 학습 일꾼 = CPU − 6 (이 컴퓨터 14, 감시 기록 `워커 14`) — 편집기 프레임이 떨어질 수 있다(4절 9).
  8. 앞서부터 남은 것: 클라이언트 보정 수, 실제 폴더에서 진짜 감시, 편집기 PIE (창이 필요).

### 9.6 10-29 확인 (기본 두뇌 R7e 커밋 `16cef08` 뒤 — 두뇌 인수 없는 AutoAdapt Play, 창 없음)

- 방법: 팀 통합 맵 `/Game/Map/LV_Ecosystem_IntegrationTest`, `UnrealEditor-Cmd … -game -RenderOffscreen -ResX=1280 -ResY=720` 실시간 180 초,
  `-ini:Engine:[ConsoleVariables]:eco.IntegratedPolicyVersion=3 -EcoIntegratedV3 -EcoV3Seed=20010 -EcoV3DeerPerRegion=128 -EcoV3ForestGrowth`(짧은 숲
  `-EcoV3ForestStartSeconds=10 -EcoV3ForestStageSeconds=15 -EcoV3ForestGrowSeconds=10 -EcoV3ForestTarget=12`), `-EcoV3AutoAdapt -EcoV3AdaptRoot=<scratch>/root`,
  진짜 `live.py watch`(명령 덮기 `-EcoV3AutoWatchCmd="-X utf8 -u results/v3/live/live.py watch --root {root} --ckpt <scratch> --steps 20000 --judge-seeds 35000-35001 …"`).
  **`-EcoV3Brain=` 없음** (9.4 ④ 는 `-EcoV3Brain=v3_r7_g995_s1_20m` 이었다). `-windowed` 없음, 새 보이는 창 0, 실제 `Saved/EcoAdapt` 29 파일 앞뒤 같음.
- 결과: 시작 고르기 `적응 고리 Play 시작 — 기본 두뇌 R7e(판 0)에서 시작`, 화면 상태 줄 `두뇌 판 0 (기본 R7e) · 두 길(마스크 판 5) …`. 나무 0→6(20.0 초)→12(35.1 초),
  `다시 배우기 조건 됨 … 나무 +12/10` → 55.1 초 스냅숏(`brain.default` 참·관측 24·판 5) → 감시 `새 환경 — 시도 1 시작` → 판 기록 묶음 `route5`
  (`시작 ckpt/v3/v3_r7_g995_s1_20m.zip`) → `기각 — 게임 두뇌 그대로 (1차 사건 숨음 비율 19.8%→20.6% t +0.5 (문턱 +12.71))` — 9.4 ④ 의 R7e 파일 판과 같은 수다.
  Play 끝에 우리 언리얼의 자손 19 개(감시·`round`·`train-one`·일꾼 파이썬 9·`EcoV3Eval` 7 등) 모두 사라짐. 같은 스냅숏은 실제 폴더 기준 입구 검사(`check_profile_sizes` 등, 읽기만)도 지난다.
  그 밖의 10-29 확인(두 맵 같은 세계·리슨/데디케이티드·두뇌 파일 없음·깨짐)과 고친 기록 글은 [LIVE_ADAPT_SPEC.md](LIVE_ADAPT_SPEC.md) 5.6 '10-29 확인'.
