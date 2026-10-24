# 실시간 두뇌 교체 — 언리얼·파이썬 주고받기 약속 (2026-10-21)

- 작성: 권신혁(RL·정책). 코드 주석의 'LIVE_ADAPT_SPEC.md n절' 은 이 문서다. 쓰는 법·시연 결과는 `herbivore_rl/results/v3/live/README.md`,
  관문 규칙은 `herbivore_rl/results/v3/live/LIVE_GATE.md`.
- 사용자 말(10-20·10-21): '게임 중 실시간 두뇌 교체를 이어서 하자'. 사람 결정 10-20: **환경이 변하는 규칙은 우리가 만들지 않는다 — 레벨(팀) 작업이다.**
  우리 몫은 레벨에서 바뀐 환경에 맞춰 게임 중에 두뇌가 바뀌게 하는 것뿐이다. '학습할 때는 늑대 포만을 끈다(게임은 그대로)'.
- 사람 결정 10-21: 관문 1차 = '포만 없는 세계'(학습과 같은 세계)에서 덜 잡힘, 지킴 = 실제 게임 세계(포만 켬)에서 나빠지지 않음. 한 바퀴 '빠른 판 10~15분'.
  두뇌는 '관측 21로 올려 배움'(첫 판 = R1b-F + 0 열, 다음 판부터 지금 두뇌에서).
- 사용자 10-21 (3) 기준 바꿈: 1차 = 같은 포만 없는 세계에서 **스스로 벗어난 도망(은신처·나무 줄기·늑대 시야 밖)의 쫓긴 시간이 짧음**('똑같이 도망을 가도 숲속으로
  잘 숨어서 늑대 시야에 잘 벗어나 도망가는 시간이 더 짧은 사슴'), 잡힘·도망 횟수·달린 시간은 지킴(나빠지지 않음). 주고받는 파일 꼴은 그대로이고 `adapt.gate`·상태 줄
  글만 바뀐다(아래 3·4절 예). 규칙 `LIVE_GATE.md` 변경 기록 (3) — 크기는 예비 측정 뒤 확정, 그 전에는 파이썬이 실제 폴더에서 판·감시를 돌리지 않는다.
- 사람 결정 10-23 (6) 기준 바꿈: 1차 = 같은 포만 없는 세계에서 **늑대에게 쫓긴 도망 가운데 은신처에 들어 끝나고 그 뒤 10 초 안에 잡히지 않은 몫(숨음 비율)이
  큼**('사슴 하나가 늑대에게 쫓겼을 때 잡히는지 아니면 살아서 은신처에 잘 숨는지 이걸 관측하게 해서 비율로 판정'). 새 지킴 GH = 쫓긴 도망 가운데 잡힌 몫이
  늘지 않음, 쫓긴 시간은 보고만. 판정 실행기는 C++ 평가기 ceval(10 초 지켜보기를 같은 날 C++ 도망 기록에 옮김 — 옮기기 전 잠깐 파이썬). 주고받는 파일 꼴은
  그대로이고 `adapt.gate`·상태 줄 글만 바뀐다(아래 3·4절 예). 규칙 `LIVE_GATE.md` 변경 기록 (6) — 크기는 예비 측정 뒤 확정(그 전 실제 폴더 잠금 그대로).
- 사람 결정 10-24 (7) "'쫓김 사건' 단위로 셈": 같은 사슴의 이어진 도망(은신처 끝 뒤 10 초 안, 그 밖 끝 뒤 5 초 안에 다시 뜀)을 한 사건으로 묶어, 1차 =
  쫓긴 사건 가운데 숨음 사건 몫(사건 숨음 비율), GH = 쫓긴 사건 가운데 잡힘 사건 몫, 새 지킴 GE = 사건 시작 수(GR 자리). 옛 도망 단위 비율·쫓긴 시간은 보고만.
  R7 결과를 본 뒤 '은신처 들락날락'이 숨음을 두 번 세는 것을 막으려고 바꿨다. 판정 실행기는 C++ 평가기 ceval(사건 셈을 같은 날 C++ 도망 기록에 옮겨 파이썬과
  `flight.episode` 까지 같다 — 옮기기 전 잠깐 파이썬). 주고받는 파일 꼴은 그대로이고 `adapt.gate`·상태 줄 글만 '사건 숨음 비율'로 바뀐다. 게임 화면 도망 줄도
  '쫓긴 사건 중 숨음 a% · 잡힘 b%'(닫힌 사건)이고, 스냅숏 flight 에 `episode` 블록이 더해졌다. 규칙 `LIVE_GATE.md` 변경 기록 (7)·'10-24 덧붙임'.
- 10-24 (8) 두 길·판 5 두뇌 (R7e 판정 통과·C++ 이식 `80bbf13` 뒤): 게임에 판 5 두뇌 파일(관측 24 두 길 + 반사 밖 두뇌 FLEE 막음, 계약 `0xad7bad5e1acaf071` —
  `EcoBrains/v3_r7_g995_s1_20m.json`)을 `eco.V3Brain.Startup`·`-EcoV3Brain=`·`eco.V3Brain.Load` 로 건 Play 의 스냅숏이면, 파이썬이 그 두뇌를 '지금 두뇌'로
  받아 판 5 세계에서 판정하고 판 5 그대로 이어 배워 판 5 두뇌 파일을 낸다(아래 2·6절). 주고받는 파일 꼴은 그대로다(스냅숏은 이식 2/2 에서 더한 칸을 읽을 뿐).
  게임 기본 두뇌(내장 R1b-F)·기본 설정·관측 21 고리는 그대로이고, 판 4 두뇌(route0·R6)를 건 Play 의 스냅숏은 거부(refused)한다. 규칙 `LIVE_GATE.md` 변경 기록 (8).

## 0. 고리 한눈에

```
레벨(팀)이 나무·날씨를 바꿈  ─▶  언리얼 환경 감시(EcoV3EnvWatch) ─▶ 결정 스텝 경계에서 지역 세계에 넣음 ─▶ 자동 스냅숏 (snapshots/)
                                                                                                        │
언리얼 두뇌 감시(eco.V3Brain) ◀─ brains/live_r<판>_<시도>.json ◀─ 관문 통과 ◀─ 포만 없는 세계에서 이어 배움 ◀─ 파이썬 live.py watch
  └▶ 다음 결정 스텝 경계에서 교체 · 화면 알림 · 판 번호 · eco.V3Brain.Rollback 되돌리기
```

## 1. 폴더와 파일 (모두 `AdaptiveEcosystem/Saved/EcoAdapt/` 아래 — `**/Saved/` 라 git 밖)

| 경로 | 쓰는 쪽 | 읽는 쪽 | 비고 |
|---|---|---|---|
| `snapshots/eco_v3_snapshot_s<세션 시드>_t<전역 스텝>_e<환경 판>.json` | 언리얼 | 파이썬 감시 | `<이름>.json.tmp` 에 쓰고 옮겨 바꾼다 (반쯤 쓴 파일이 보이지 않게) |
| `brains/live_r<판>_<시도 이름>.json` | 파이썬 | 언리얼 (`eco.V3Brain.WatchFolder`) | `<이름>.json.tmp` 에 써서 다시 읽어 확인한 뒤 `os.replace`. 같은 이름은 덮지 않는다 |
| `status.json` | 파이썬 | 언리얼 (상태 줄) | `os.replace` (언리얼이 2 초마다 열므로 잠깐 잠기면 다시 시도) |
| `live/state.json`, `live/rounds/<시도 이름>/…`, `live/watch.lock` | 파이썬 | 파이썬 | 판·시도 번호, 판마다 변환·평가·관문·기록 |
| (모델) `herbivore_rl/ckpt/v3/live/<시도 이름>/*.zip` | 파이썬 | 파이썬 | git 밖 |

## 2. 스냅숏에 더한 칸 (형식 `eco_v3_snapshot` 판 1 그대로 — 새 칸은 더하기만, 없으면 옛 스냅숏처럼 읽는다)

맨 위:
```json
"play_id": "p20261021T153000_0badcafe",   // 적응 고리 Play 번호 (eco.IntegratedV3.AutoAdapt 일 때 Play 마다 새로, 끄면 빈 값)
"env": {
  "watch": true,                    // eco.IntegratedV3.EnvWatch 가 켜져 있었다
  "revision": 2,                    // Play 시작 뒤 넣은 환경 바뀜 묶음 수 (0 = 그대로)
  "changed_step": 1530,             // 마지막으로 넣은 전역 스텝 (없으면 0)
  "first_changed_step": 900,
  "trigger": "env_change",          // env_change | periodic | console | scheduled
  "changes": [                       // Play 시작 뒤 넣은 바뀜 모두, 오래된 것부터
    {"revision": 1, "step": 900, "seconds": 120.0, "region": "Barren", "kind": "trees", "detail": "나무 0→20 (+20 −0)", "source": "test"},
    {"revision": 2, "step": 1530, "seconds": 204.0, "region": "Barren", "kind": "weather", "detail": "맑음→비 1.00",
     "source": "cvar:eco.IntegratedV3.WeatherBarren"}
  ]
}
```
`source` = `level`(레벨 나무 액터) · `cvar:<이름>`(우리 지역 날씨 콘솔 변수) · `team_env`(팀 `FRegionEnvironmentState`) · `test`(시험용 대역).
`brain` 안에 `"adapt": {"round", "attempt", "run", "snapshot"}`(지금 두뇌 파일에 adapt 블록이 있었을 때, 없으면 `{}`). 지역 `obstacles` 안에 `"level_trunks"`(지금 무대 안 줄기 막이 수).

10-24 두 길 두뇌 이식(`80bbf13`, `RL_V3_ROUTE_CPP_PORT_PLAN.md` 15-1)이 더한 칸 — 파이썬이 읽는다(변경 기록 (8)):
- `brain.contract_hash`·`obs_dim`(이식 전부터)·`mask_version`(2·4·5)·`route`·`flee_gate`: 파이썬 시작 모델 고르기(`live.resolve_start`)가 계약 해시로 묶음을
  정하고(관측 21 `0xbc4fc2d45c47c5fd` · 관측 24 판 5 `0xad7bad5e1acaf071`, 판 4 `0xe302dee198197444` 는 거부), `mask_version` 이 있으면 그 묶음의 판과 같아야 한다.
- 지역 `world.wild_flight.route`·`brain_flee_outside_reflex`(게임이 지금 두뇌로 실제로 건 값): 있으면 시작 모델 묶음(판 5 = 참·거짓, 관측 21 = 거짓·참)과
  같아야 한다(`live.check_snapshot_route` — 다르면 거부). 판정·학습 세계의 두 길 칸은 이 칸이 아니라 묶음의 바탕 설정이 정한다(`adapt.convert` 는 이 칸을 읽지 않는다).
- 지역 `flight.route`(길 통계): 보고만 — 파이썬은 쓰지 않는다.

## 3. 두뇌 파일 `adapt` 블록 (파이썬이 쓰고, 언리얼은 있으면 읽는다 — 없거나 값이 깨져도 거부하지 않는다)
```json
"adapt": {
  "round": 3,                 // 받아들인 판 번호 1.. (내장 = 0, 기각된 시도는 판 번호를 받지 않는다)
  "attempt": 5,               // 시도 번호 (기각 포함)
  "run": "a5_20261021T153200_e2",
  "snapshot": "eco_v3_snapshot_s20004_t480_e1.json",
  "env": "Barren 나무 0→20, 비 1.0",
  "gate": "포만 없는 세계 사건 숨음 비율 11.9%→14.0% (t +2.4), 잡힘·도망 나빠짐 없음",   // 10-24 (7) 뒤 꼴 (10-23 (6): '포만 없는 세계 숨음 비율 13.1%→15.0% (t +2.4), …', 10-21 (3)~(5): '포만 없는 세계 쫓긴 시간 6.3→5.1초 (t −2.4), 잡힘·도망 나빠짐 없음', 그 전: '포만 없는 세계 잡힘 31.2→28.4% (t −2.9), 게임 세계 나빠짐 없음')
  "created_utc": "2026-10-21T10:32:00Z",
  "play_id": "p20261021T153000_0badcafe"   // 바탕 스냅숏의 play_id — 언리얼 감시는 지금 Play 와 다르면 받지 않는다 (앞 Play 의 판이 늦게 끝난 경우)
}
```
`model.name` = `live_r<판>_<시도 이름>` (언리얼 id = `<model.name>@<가중치 sha256 앞 8자리>`).

## 4. status.json (파이썬 → 언리얼 상태 줄)
```json
{"format": "eco_v3_live_status", "version": 1, "updated_unix": 1760000000.0, "pid": 1234,
 "state": "idle|waiting|converting|checking|training|evaluating|gating|exporting|exported|rejected|refused|superseded|error",
 "attempt": 5, "round": 3, "snapshot": "…json", "env": "Barren 나무 0→20",
 "message": "학습 중 0.6M/1M", "progress": 0.6, "last_result": "기각: 1차 사건 숨음 비율 11.9%→12.2% t +0.6 (문턱 +1.99)"}
```
`round` = 마지막으로 받아들인 판. 언리얼은 `updated_unix` 가 120 초 안이면 `적응 고리 | <message>`, 아니면 `적응 고리 | 응답 없음 (<n>초 전)`,
파일이 없으면 `적응 고리 | 파이썬 감시 없음` 을 보인다.

## 5. 언리얼 (개발 빌드 — 콘솔 변수·명령은 `#if !UE_BUILD_SHIPPING`)

### 5.1 환경 감시 (`S/AI/Policy/EcoV3EnvWatch.cpp`)
- `eco.IntegratedV3.EnvWatch` (기본 1) · `EnvWatchSeconds` (실시간 1 초): 그 주기마다와 액터가 생기거나 지워진 다음 프레임에 레벨 나무와 날씨 출처를 다시 읽고,
  바뀐 것을 다음 **전역 결정 스텝 경계**(두뇌 바꾸기와 같은 곳, 스텝 앞)에서 지역 세계에 넣는다. 바뀐 것이 없으면 아무것도 하지 않는다 — 지금까지의 실행과 비트 단위로 같다.
  0 = 옛 동작(Play 시작 때 환경 고정).
- 나무 = 꼬리표 `EcoV3Trunk` 줄기 막이(`EcoV3PlaceTreesCommandlet` 이 놓는 나무 메시(충돌 없음, `EcoV3Tree`) + 숨긴 원기둥 줄기 막이(BlockAll) 짝).
  넣는 원판 목록은 그 나무들로 Play 를 시작했을 때 `TryCreateContexts` 가 만들었을 목록과 같다(바위 등 시작 읽기 원판은 그대로, (x, y, r) 순 —
  자동화 `Policy.V3.EnvWatch.Trees`). 새 원판 안 산 사슴·늑대는 밖으로 밀고 돌아가기를 지운다. **먹이 격자는 그대로**(팀 자원 계약
  `CommitSpatialFood` 가 스텝 밖 먹이 합 변화를 거부하고 통합 모드를 끈다 — 줄기 원판은 먹이 셀 1/6 밑). 장애물을 끈 판·원판을 가져온 판은 무시.
- 날씨 출처: ① 우리 지역 콘솔 변수 `eco.IntegratedV3.WeatherForest|WeatherHighland|WeatherBarren` 를 Play 중에도 읽는다(값이 바뀌면, 빈 값 = 팀 설계 기본),
  ② 팀 `FRegionEnvironmentState`(`UEcologyWorldSubsystem::GetEnvironmentState`) — 지역 세계를 만들 때 값이 바탕, 바뀌면 비·폭풍 → 비(세기 = Rainfall, 0 이면 1),
  맑음·가뭄 → 맑음(팀에는 눈이 없다). 팀 콘솔 `eco.Environment.Rain <지역> <0..1>` 이 레벨 쪽 계기로 쓰인다. 세계 설정 `Weather.Kind·Intensity` 를 바꾸고
  `UpdateDayNight` 로 배수를 다시 정한다. 시간표(`Weather.Schedule`)는 쓰지 않는다. 날씨를 끈 판은 무시.
- 넣은 묶음마다 환경 판 + 1, 기록 `[EcoV3I] 환경 바뀜 #<판> | <초> (전역 스텝 <t>) | Barren: 나무 0→20 (+20 −0) | …`, 화면 알림.
- 은신처는 다루지 않는다(`RefreshRefuges` 가 맡고, 파이썬은 바뀐 은신처를 거부한다). 보기 `eco.IntegratedV3.EnvInfo`.

### 5.2 자동 스냅숏 (`S/AI/Policy/EcoV3Snapshot.cpp`)
- `eco.IntegratedV3.AutoAdapt` (기본 0, 명령줄 `-EcoV3AutoAdapt`): 적응 고리 큰 스위치. 켜면 — 환경 바뀜 뒤 자동 스냅숏, 두뇌 감시 폴더 기본
  `Saved/EcoAdapt/brains`(`eco.V3Brain.WatchFolder` 가 비었을 때), Play 시작 때 있던 파일은 읽지 않음, Play 번호(`play_id`), 상태 줄(`Saved/EcoAdapt/status.json`),
  Play 마다 내장 두뇌(판 0)에서 시작(레벨이 Play 마다 처음 상태로 돌아오므로 — `eco.V3Brain.Startup` 을 주면 그 두뇌).
- `eco.IntegratedV3.AutoSnapshot` (기본 −1 = AutoAdapt 따름, 0 끔, 1 켬): 마지막 환경 판이 `AutoSnapshotSettle`(시뮬레이션 3 초) 동안 그대로면 판마다 한 번.
- `eco.IntegratedV3.SnapshotEvery` (시뮬레이션 초, 기본 0 = 끔): 주기 스냅숏(`periodic`). `eco.IntegratedV3.AutoSnapshotOut` (기본 `Saved/EcoAdapt/snapshots`).
- 모든 스냅숏 쓰기(자동·주기·콘솔·예정)는 `.tmp` 에 쓰고 옮겨 바꾼다.

### 5.3 시험용 대역 (레벨 팀이 할 일을 흉내 낼 뿐 — 세계 규칙이 아니다)
- `eco.IntegratedV3.Test.AddTrees <지역> <수> [씨]`: 명령(`EcoV3PlaceTreesCommandlet`)과 같은 나무 + 줄기 막이 짝을 무대 안 빈자리(은신처·다른 줄기·가장자리에서 떨어진 곳,
  땅에 붙임)에 놓는다. `Test.RemoveTrees <지역> <수>`: 놓은 짝을 나중 것부터. **단독 실행만**(짝을 복제하지 않아 서버에서 놓으면 클라이언트 충돌과 달라진다).
- `eco.IntegratedV3.Test.At <초> <명령>[; <명령>…]`, 명령줄 `-EcoV3TestAt=<초> -EcoV3TestCmd="명령1; 명령2"`(쌍 여러 개): 시뮬레이션 초에 콘솔 명령을 한 번.
  예약 명령이 바꾼 콘솔 변수는 Play 가 끝나면 예약 전 값으로 되돌린다.

### 5.4 두뇌 교체 화면·되돌리기 (`S/AI/Policy/EcoV3Brain.{h,cpp}`, `SyncBrain`)
- 되돌리기 쌓개(16): 바꿀 때마다 나가는 두뇌를 쌓는다. `eco.V3Brain.Rollback`(다음 결정 스텝 경계에서 바로 앞 두뇌로, 두 번 누르면 둘 앞), `eco.V3Brain.History`.
- 두뇌 파일 `adapt` 블록(3절)을 읽어 판 번호를 보인다. 감시: Play 시작 때 있던 파일은 읽지 않음(`PrimeWatch`), 3 초 안에 깨진 새 파일은 다시 읽음,
  `adapt.play_id` 가 지금 Play 와 다르면 받지 않음(까닭 '다른 Play').
- 화면 알림(`eco.V3Brain.Notice`, 기본 1 — `eco.V3Debug` 와 상관없이, 그리는 실행에서만, 클라이언트 아님. 모든 알림은 기록 `[EcoV3I] 알림 | …` 으로도 남는다):
  새 두뇌(판·id·환경·관문·되돌리기 안내), 되돌림, 두뇌 파일 거부, 환경 바뀜, 스냅숏 내보냄, 그리고 상태 줄
  `두뇌 판 3 (live_r3…@abcd) · 교체 3번 · 환경 #2 · 적응 고리 | <status.message>`.
- `eco.V3Brain.NoticeShot` (기본 0): 바꿈·되돌림 알림 1.5 초 뒤 화면 찍기(`Saved/EcoAdapt/shots`). `eco.V3Brain.StatusFile`(기본 빈 값 = AutoAdapt 면 `Saved/EcoAdapt/status.json`).

## 6. 파이썬 (`herbivore_rl/results/v3/live/live.py`, 시험 `herbivore_rl/tests/test_live_v3.py`)
- `watch`(감시 데몬) · `round --snapshot F`(한 판) · `pilot --snapshot F`(예비 측정 — 시드 34900~34999 만). 적응 고리 `results/v3/adapt/adapt.py` 를 쓴다.
- 새 스냅숏 → 환경 지문(원판·날씨·먹이 용량·은신처) + 두뇌 sha 가 지난 것과 같으면 건너뜀. 판 도중 다른 환경 스냅숏이 오면 그 판을 끝내고 새 것으로.
- 세 세계: G 게임(스냅숏 그대로, 포만 켬), N 포만 없는 세계(G 에서 포만만 끔), T 학습(N + R5 학습 조리법, 무작위 숲 없음, 스냅숏 먹이 지도).
- 시작 모델: 관측 18 + R1b-F → `ckpt/v3/v3_r1_g995_s3_obs21zero.zip`, 관측 21 → 두뇌 파일의 같은 가중치 zip, 10-24 (8) 관측 24 · 판 5 → 두뇌 파일의 같은
  가중치 zip(R7e 면 `ckpt/v3/v3_r7_g995_s1_20m.zip`), 그 밖(관측 24 · 판 4 포함) 거부. 판 5 면 G·N 바탕 `configs/v3_wild3_route5_mirror.yaml`, T 조리법
  `configs/v3_r7_train.yaml`(f_dec 0.714694), PPO `configs/ppo_r6_lam098.yaml`(λ 0.98) — 시작 모델 계약의 묶음(`live.PROFILES`)이 정한다.
- 관문(`LIVE_GATE.md`, 10-24 (7) 뒤): R(바뀜 없는 스냅숏만) → P1(N 쫓긴 사건 가운데 숨음 사건 몫(사건 숨음 비율 — 마지막 도망이 은신처 끝 + 10 초 안
  안 잡힘·다시 안 뜀) 증가, 짝 t) → GH(N 쫓긴 사건 가운데 잡힘 사건 몫이 늘지 않음) → GN(N 잡힘·굶음·산) → GF·GE·GV·GC(N 도망 시작·사건 시작·달린 시간·
  잡힘/잘림으로 끝난 도망이 늘지 않음) → GG(G 잡힘·굶음·산·쫓긴 시간) → G4(은신처 안 잡힘 0) → G5(끼임) → G6(악용) → A5(다시 읽기). N 도망 단위 숨음·잡힘
  비율과 쫓긴 시간은 보고만. 판정 실행기 `LIVE.evaluator` 'ceval'(C++ 평가기 — 10-24 쫓김 사건 `flight.episode` 셈을 C++ 에 옮긴 뒤 파이썬과 세계 기록이
  같아 'python' 에서 되돌렸다. 쫓김 사건·숨은 뒤 10 초 지켜보기를 세지 못하는 실행기는 거부). 10-24 (8) 두 길(판 5) 판은 설계 12절 길 지킴 GT·GTr·GR 을
  `gate.md` '길 기록' 절에 보고만 한다(관문 칸 아님 — GR 자리는 GE).
- 내보내기 A5 계약: 시작 모델 묶음의 계약·관측 수·마스크 판(관측 21, 또는 관측 24 · 판 5 — 골든 세계 판 5 거울).
- 내보내기: `brains/live_r<판>_<시도>.json`(adapt 블록, `play_id` 포함), `status.json`·`state.json` 갱신.
