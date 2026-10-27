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
- 사용자 결정 10-27: "변화하는 레벨은 팀에 맡기고 나는 변했을 때 어떻게 반응할지에 대해서만 설계하자. 그래서 일단은 모드를 하나 만들어서 해당 모드에서는 숲이 점점 자라게
  만들고 그걸 언리얼이 인식하면 그에 맞춰 두뇌 다시 만들어서 교체하는걸로 가자." 다시 배우기 기준 = '큰 변화만'(날씨 종류 바뀜 또는 나무 수가 문턱 이상 바뀜, 세기 흔들림은
  세계에만 넣음, 잦은 변화는 묶음), Play 때 파이썬 감시 자동 시작. 구현: 숲 자람 모드(5.3), 자동 스냅숏 규칙(5.2), 감시 자동 시작(5.5) — 설계·구현 기록과 확인 결과는
  [FOREST_GROWTH_MODE.md](FOREST_GROWTH_MODE.md). 주고받는 파일 꼴은 그대로다(스냅숏 `env` 에 칸을 더하기만 — 2절).

## 0. 고리 한눈에

```
레벨(팀)이 나무·날씨를 바꿈 (시험: 숲 자람 모드 5.3) ─▶ 언리얼 환경 감시(EcoV3EnvWatch) ─▶ 결정 스텝 경계에서 지역 세계에 넣음
                                                                                             └▶ '큰 변화만'일 때 바뀜이 멈춘 뒤 한 번 자동 스냅숏 (snapshots/, 5.2)
                                                                                                        │
언리얼 두뇌 감시(eco.V3Brain) ◀─ brains/live_r<판>_<시도>.json ◀─ 관문 통과 ◀─ 포만 없는 세계에서 이어 배움 ◀─ 파이썬 live.py watch
  └▶ 다음 결정 스텝 경계에서 교체 · 화면 알림 · 판 번호 · eco.V3Brain.Rollback 되돌리기          (AutoAdapt Play 가 창 없이 띄우고 Play 끝에 끝냄, 5.5)
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
`source` = `level`(레벨 나무 액터) · `cvar:<이름>`(우리 지역 날씨 콘솔 변수) · `team_env`(팀 `FRegionEnvironmentState`) · `test`(시험용 대역) ·
`forest_growth`(10-27 숲 자람 모드가 다 자란 나무를 넣음 — 5.3. `detail` 은 같은 `나무 a→b (+n −m)` 꼴).

10-27 '큰 변화만'·숲 자람이 더한 칸 (`env` 안 — 파이썬은 모르는 칸을 읽지 않는다. `live.py`·`adapt.py` 는 바꾸지 않았다):
```json
"rule": "big",                     // 자동 스냅숏 규칙: big (eco.IntegratedV3.AutoSnapshotRule 1, 기본) | each (0 — 옛 동작). 콘솔·예정 스냅숏에도 적힌다
"big": {                           // rule big 일 때만 — 쓰는 순간의 셈 (5.2)
  "baseline_step": 0, "big_trees": 10, "weather_hold_s": 120, "settle_s": 20, "max_wait_s": 300,
  "trees": {"Forest": 0, "Barren": 24, "Highland": 0},          // 지역마다 기준선과 세계 원판의 대칭차
  "weather": {"Forest": {"base": "rain", "now": "rain", "held_s": 0}, …},
  "condition": true, "quiet_s": 20.0, "held_s": 100.0,          // 마지막 큰 변화 바뀜 뒤 초 · 조건이 선 뒤 초
  "level_change_hold": false, "capped": false
},
"forest": {"on": true, "region": "Barren", "target": 24, "planned": 24, "mature": 24, "saplings": 0, "per_stage": 6,   // 숲 자람 모드를 켰을 때만
           "start_seconds": 30, "stage_seconds": 40, "grow_seconds": 20, "next_mature_step": -1, "done": true}
```
`trigger` 는 그대로 `env_change` 다. 자동 스냅숏의 `why` 는 규칙 1 이면 `큰 변화 — 메마른 땅 나무 +24/10 · 날씨 그대로 (기준 전역 스텝 0) · 바뀜 없이 20.0초 · 조건 뒤 100.0초`.
`brain` 안에 `"adapt": {"round", "attempt", "run", "snapshot"}`(지금 두뇌 파일에 adapt 블록이 있었을 때, 없으면 `{}`). 지역 `obstacles` 안에 `"level_trunks"`(지금 무대 안 줄기 막이 수).

10-24 두 길 두뇌 이식(`80bbf13`, `RL_V3_ROUTE_CPP_PORT_PLAN.md` 15-1)이 더한 칸 — 파이썬이 읽는다(변경 기록 (8)):
- `brain.contract_hash`·`obs_dim`(이식 전부터)·`mask_version`(2·4·5)·`route`·`flee_gate`: 파이썬 시작 모델 고르기(`live.resolve_start`)가 계약 해시로 묶음을
  정하고(관측 21 `0xbc4fc2d45c47c5fd` · 관측 24 판 5 `0xad7bad5e1acaf071`, 판 4 `0xe302dee198197444` 는 거부), `mask_version` 이 있으면 그 묶음의 판과 같아야 한다.
- 지역 `world.wild_flight.route`·`brain_flee_outside_reflex`(게임이 지금 두뇌로 실제로 건 값): 있으면 시작 모델 묶음(판 5 = 참·거짓, 관측 21 = 거짓·참)과
  같아야 한다(`live.check_snapshot_route` — 다르면 거부). 판정·학습 세계의 두 길 칸은 이 칸이 아니라 묶음의 바탕 설정이 정한다(`adapt.convert` 는 이 칸을 읽지 않는다).
- 지역 `flight.route`(길 통계): 보고만 — 파이썬은 쓰지 않는다.

10-27 사용자 보고 두 고침(`RL_V3_WILD1_SPEC.md` 13절 — 먹기 걷기 고침·거리 두기)이 더한 칸 — 파이썬이 읽는다:
- 지역 `world.graze_calm{graze_edge_r, graze_edge_w, graze_inertia, graze_wall_margin}`(실제로 쓰는 `W.RepCfg` 값)·`world.wild_flight.rest_keep·rest_keep_margin·
  rest_keep_band·rest_keep_asleep`: `adapt.FEATURE_MAPS` 가 `features.repertoire.graze_*`·`features.wild_flight.rest_keep*`(선택 키)로 옮긴다. 바탕 설정에 없는 칸은
  끔 값을 바탕 값으로 보고, 칸이 없는 옛 스냅숏(10-26 까지)은 끈 세계로 읽는다. `settings.rest_keep`·`graze_calm`(콘솔 스위치)은 기록만.
- **영향 메모**: 게임 기본(`eco.IntegratedV3.GrazeCalm`·`RestKeep` 1)의 스냅숏은 두 고침을 켠 세계로 옮겨진다(`configs/v3_wild3_calm_mirror.yaml` 과 같은 규칙).
  그래서 고리의 판정·학습 세계도 켠 세계다. 지금 판정 기준선(예비 측정·R7e 판정의 사건 숨음 등)은 끈 세계에서 잰 값이라 켠 세계 판정과 섞지 않는다 — 판정
  저장 열쇠(`live.eval_code_tag` — `world.py` 바이트 포함)가 바뀌어 옛 저장 값과 저절로 갈린다. 켠 세계의 기준선은 다시 잰다(`herbivore_rl/results/v3/live/LIVE_GATE.md`
  변경 기록 (9)). 평가기(`Tools/EcoV3Eval`)는 같은 칸을 world 블록에서 읽는다 — 이 칸이 든 소스로 다시 빌드해야 한다.

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
- **시작 날씨 = 팀 날씨 출처** (10-27 사용자 결정 (C), `eco.IntegratedV3.TeamWeatherStart` 기본 1): 팀 날씨 출처가 있는 지역은 지역 세계를 만들 때(`InitContextEnv`)
  팀 `FRegionEnvironmentState` 를 위 ② 와 같은 식으로 규칙 날씨에 넣는다. 우리 고정 날씨(팀 설계 기본 숲 비 1·고지 눈 1·메마른 땅 맑음, 덮기 글자)는 출처가 없는
  지역에서만 쓴다. 고치기 전에는 조연우 맵(팀 날씨 BP `BP_JYU_EcosystemWeather` — 비 주기 180 초, 위상 숲 0·메마른 땅 30·고지 60 초)에서 팀 값이 처음 바뀔 때까지
  (숲 0~73 초·고지 0~13 초) 규칙 ≠ 화면이었다(식생 맵 보기 연출은 팀 지역 환경을 그린다).
  - 출처 판정(`EcoV3EnvWatch.cpp` `FindTeamWeatherSource`) = 그 지역을 맡는 팀 환경 어댑터 `AEcoRegionEnvironmentAdapter`(자식 BP 포함)가 쓰는 길을 켰나. 어댑터
    `Tick` 이 지역 환경을 쓰는 조건을 그대로 본다: ① `RegionIds` 에 그 지역이 있거나 목록이 비었다(모든 지역), ② 비 주기(`bCycleRainfall` — `EvaluateCycleRainfall`
    이 설정을 받아들임. 작성 날씨와 함께 켜면 어댑터가 거부한다) 또는 작성 날씨(`bApplyAuthoredWeather`, 비 주기 끔). 둘 다 끈 어댑터(블루프린트가 `ApplyRainfall`
    을 직접 부르는 다리일 수 있다), 팀 지역 환경을 쓰지 않는 그리기 BP(SHC `BP_SHC_*RegionalWeather`), 팀 콘솔 `eco.Environment.Rain` 은 출처가 아니다 — 그 값은
    지금처럼 바뀔 때 `team_env` 바뀜으로 따른다. '팀 지역 환경을 썼는가'로 판정하지 않는 까닭: 어댑터는 팀 월드 시계가 돈 뒤 0.2 초마다 쓰므로 지역 세계를 만드는
    순간에는 아직 안 썼을 수 있고, 처음 쓴 값이 레벨에 적힌 값과 같으면 썼는지 알 수 없다.
  - 10-27 확인(읽기 전용 — 맵은 고치지 않았다. `Content/` 전체에서 어댑터 클래스·`BP_JYU_EcosystemWeather` 를 가리키는 애셋 찾기 + 맵 넷 읽기): 출처가 있는 맵은
    `/Game/JYU/Maps/LV_JYU_Ecosystem`·복사본 `/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem` 둘뿐이다(맵마다 지역 셋 모두 비 주기 어댑터). 팀 통합
    `/Game/Map/LV_Ecosystem_IntegrationTest`·SHC 날씨 시험 맵 등 나머지는 출처가 없어 지금 그대로 우리 고정 날씨로 시작한다.
  - Play 시작 덮기 글자(`eco.IntegratedV3.WeatherForest|WeatherHighland|WeatherBarren`, 비지 않고 읽힘)가 날씨를 고르면 그것으로 시작한다(사람이 고른 값 — 팀 값은
    다음 팀 바뀜부터 따른다). 못 읽는 글자는 빈 값처럼 팀 값. 콘솔 변수는 편집기 프로세스에 남아 앞 Play 에서 친 값이 덮기가 될 수 있으므로 기록 줄
    `[EcoV3I] <지역> 시작 날씨 | …` 가 어느 쪽으로 시작했는지 적는다. 보기 `eco.IntegratedV3.EnvInfo` 지역 줄 '팀 날씨 출처'.
  - 바뀜이 아니라 시작값이다 — 환경 판·`env.changes`·알림은 그대로(판 0). 같은 T 에서 `InitWorld` 직후 날씨만 바꾸고 `UpdateDayNight` 하므로 그 날씨로 세계를
    만든 것과 같다(`InitWorld` 는 날씨로 난수·먹이를 정하지 않는다 — 자동화 `Policy.V3.EnvWatch.TeamWeatherStart` 가 같은 날씨를 덮기 글자로 고른 세계와 견준다).
    늦게 등록된 지역은 처음 읽을 때 팀 값을 바뀜(`team_env`)으로 넣는다(출처 없는 지역은 지금처럼 바탕만).
  - 감시 끔(`EnvWatch 0` — 옛 동작, `results/v3/level_jyu_eco` 대조 모드 `-EcoV3EnvWatch=0`)·`TeamWeatherStart 0`(10-27 전 — 앞선 전체 모드 측정 다시 내기:
    `-ini:Engine:[ConsoleVariables]:eco.IntegratedV3.TeamWeatherStart=0`)이면 지금까지처럼 우리 고정 날씨로 시작한다.
  - v3 세계 규칙·배수는 바꾸지 않았다. 스냅숏 지역 `world.weather`(와 `ObstacleExport` 의 지역 `weather`)가 세계 설정 날씨를 적으므로 파이썬 변환·짝 비교는 그대로 맞는다.
  - 남는 점(기록만): 출처 없이 식생 맵 보기(조정자 `bUseV3Policy ∧ bEnableVegetation`)를 쓰는 맵은 화면 = 팀 지역 환경, 규칙 = 우리 고정 날씨로 다를 수 있다(10-27
    `Content/` 찾기로 `bEnableVegetation` 을 켠 맵은 출처가 있는 위 둘뿐이라 지금은 없다). 팀 비 주기의 전환 구간(한 번에 18 초, 위상 0.4~0.5·0.9~1.0)에는 팀 값이 0.2 초마다 바뀌어 환경 판이 감시 주기(실시간 1 초)마다 오른다(10-27 복사본
    헤드리스 기록: 고지 첫 전환 13~31 초에 판 7개 — 이번 고침 전과 같다. `results/v3/level_jyu_eco/README.md` 5절의 잦은 작은 변화 문제).
  - 10-27 확인 (창 없는 헤드리스 `UnrealEditor-Cmd -game -NullRHI -benchmark -fps=30`, 세션 20010, 사슴 128 × 지역 셋): UBT 두 판(적응 unity·`-DisableAdaptiveUnity`)
    성공, 자동화 `AdaptiveEcosystem` 255 개 실패 0 (`Policy.V3.EnvWatch.TeamWeatherStart` 포함).
    - 조연우 복사 맵: 세 지역 모두 시작 줄이 `시작 날씨 | 팀 날씨 출처 JYU_Ecosystem_Weather_<지역> (BP_JYU_EcosystemWeather_C · 비 주기 180초·위상 0·30·60초) → 맑음
      (팀 지역 환경 Clear·비 세기 0.00)` 이다. 0~84 초 동안 2 초마다 `getall EcologyRegion EnvironmentState`(팀 값)와 규칙 날씨를 견줬다 — 어긋난 칸(종류 다름 또는
      비 세기 차 0.10 넘음): 숲 고치기 전 41/43 → 고친 뒤 3/43, 고지 11/43 → 5/43, 메마른 땅 4/43 → 6/43. 시작 구간(숲 0~72 초·고지 0~12 초)은 모두 맞는다.
      남은 칸은 모두 팀 비 주기 전환 구간(한 번에 18 초)에서 팀 값이 0.2 초마다 바뀌는 동안 실시간 1 초 감시가 뒤따르는 늦음이다. 헤드리스는 실시간보다 몇 배 빨리
      돌아 감시 간격이 시뮬레이션 몇 초가 되므로 늦음이 커 보인다 (이번 고침과 무관 — 고치기 전에도 같은 구간이 어긋났다).
    - 팀 통합 맵 `/Game/Map/LV_Ecosystem_IntegrationTest`: 출처가 없어 '시작 날씨' 줄 없이 우리 고정 날씨로 시작한다. 같은 시드 121 초 사슴 줄 `[EcoV3Obs]` 343218 개가
      변경 전 빌드(`28baef7`)와 바이트까지 같다 (`TeamWeatherStart 0` 판도 같다).
    - 조연우 복사 맵은 같은 빌드·같은 설정 두 판끼리도 사슴 줄이 다르다 (`TeamWeatherStart 0` 두 판은 고지 108 스텝부터, 기본 두 판은 고지 119 스텝부터). 팀 날씨 바뀜을
      실시간 주기로 읽어 넣으므로 넣는 스텝이 실행마다 달라서다. 그래서 이 맵은 같은 시드 바이트 비교에서 뺐다.
    - 10-27 적대적 확인 (코드 그대로, 창 없는 `UnrealEditor-Cmd -game -NullRHI` 실시간): 원본 `/Game/JYU/Maps/LV_JYU_Ecosystem`(읽기만 — 저장 없음) 80 초 단독에서도
      세 지역 시작 줄이 `팀 날씨 출처 JYU_Ecosystem_Weather_<지역> … → 맑음 … 우리 고정 날씨 (숲 비 1.00·메마른 땅 맑음·고지 눈 1.00) 대신` 이다.
      출처가 없는 통합 맵(리슨·데디케이티드 판)은 '시작 날씨' 줄이 0 개이고 시작 날씨가 숲 비 1·메마른 땅 맑음·고지 눈 1 (고정) 그대로다. `Content/` 찾기로
      어댑터·`BP_JYU_EcosystemWeather` 를 가리키는 맵은 위 두 맵(원본·복사본)의 외부 액터뿐이다 — 나머지 맵(통합·SHC 날씨 시험·`LV_JYU_V3Integration`·`LV_JYU_RefugeSafety` 등)의 시작은 바뀌지 않는다.
- 넣은 묶음마다 환경 판 + 1, 기록 `[EcoV3I] 환경 바뀜 #<판> | <초> (전역 스텝 <t>) | Barren: 나무 0→20 (+20 −0) | …`, 화면 알림('큰 변화만' 규칙이 돌면 세기만 바뀐
  판은 알림 없음, 큰 바뀜과 섞인 묶음은 세기만 바뀐 지역을 알림 글에서 뺀다 — 5.2, 10-27 확인 고침).
- 은신처는 다루지 않는다(`RefreshRefuges` 가 맡고, 파이썬은 바뀐 은신처를 거부한다). 보기 `eco.IntegratedV3.EnvInfo`.

### 5.2 자동 스냅숏 (`S/AI/Policy/EcoV3Snapshot.cpp`)
- `eco.IntegratedV3.AutoAdapt` (기본 0, 명령줄 `-EcoV3AutoAdapt`): 적응 고리 큰 스위치. 켜면 — 환경 바뀜 뒤 자동 스냅숏, 두뇌 감시 폴더 기본
  `Saved/EcoAdapt/brains`(`eco.V3Brain.WatchFolder` 가 비었을 때), Play 시작 때 있던 파일은 읽지 않음, Play 번호(`play_id`), 상태 줄(`Saved/EcoAdapt/status.json`),
  Play 마다 내장 두뇌(판 0)에서 시작(레벨이 Play 마다 처음 상태로 돌아오므로 — `eco.V3Brain.Startup` 을 주면 그 두뇌). 10-27: 기본 폴더 셋은 `eco.IntegratedV3.AdaptRoot`
  (빈 값 = `Saved/EcoAdapt`) 아래이고, Play 때 파이썬 감시를 창 없이 띄워 Play 끝에 끝낸다(5.5 — `eco.IntegratedV3.AutoWatch 0` 이면 지금까지처럼 사람이 띄운다).
- `eco.IntegratedV3.AutoSnapshot` (기본 −1 = AutoAdapt 따름, 0 끔, 1 켬): 환경 바뀜 자동 스냅숏. 언제 쓰는지는 아래 규칙.
- **`eco.IntegratedV3.AutoSnapshotRule`** (10-27, 기본 1 = 큰 변화만 — `S/AI/Policy/EcoV3BigChange.h`, 판정은 `MaybeAutoSnapshot`, 셈은 `ApplyEnvChange`):
  - 기준선 = Play 시작(지역 세계를 만든 때) 또는 마지막 **자동** 스냅숏 때의 지역마다 (세계 원판, 날씨 종류). 주기·콘솔·예정 스냅숏은 기준선을 바꾸지 않는다.
  - 나무: 한 지역 세계 원판과 기준선 원판의 대칭차(같은 (x, y, r) 끼리 하나씩 지우고 남은 양쪽 합) ≥ `eco.IntegratedV3.BigTrees`(10).
  - 날씨: 지역 날씨 종류(맑음·비·눈)가 기준선과 다르고 그 종류가 된 뒤 `eco.IntegratedV3.WeatherHold`(시뮬레이션 120 초) 이상 이어짐 — 팀 비 주기 180 초의 반 주기(약 90 초)를
    넘지 않는 오가는 비는 큰 변화가 아니다. **세기만 바뀐 묶음은 세계에는 넣지만 셈·바뀜 시계에 넣지 않는다.**
  - 묶기: 조건이 선 뒤 큰 변화 바뀜(원판·날씨 종류)이 `eco.IntegratedV3.BigSettle`(20 초) 없을 때 한 번. 숲 자람 모드가 아직 자라는 동안('레벨 바뀜 진행 중' —
    `SetLevelChangeHold` 로 다른 쪽도 걸 수 있다)은 기다린다. 조건 뒤 `eco.IntegratedV3.BigMaxWait`(300 초)가 지나면 진행 중·묶기와 상관없이 쓴다(`capped`).
  - 쓰면(쓰기에 실패해도) 기준선 = 지금. 조건이 처음 선 때 기록 `[EcoV3I] 다시 배우기 조건 됨 | 90.0초 (전역 스텝 675) | 메마른 땅 나무 +12/10 · 날씨 그대로 | 기다림: …`.
  - 규칙이 돌 때(자동 스냅숏 켬 ∧ 규칙 1) 세기만 바뀐 환경 판은 화면 알림을 내지 않는다 — 기록 줄 `[EcoV3I] 환경 바뀜 #n | … | 세기만 바뀜 — 다시 배우기 셈·화면 알림 없음`
    은 남는다 (`eco.IntegratedV3.EnvNoticeMinor 1` = 늘 알림). 자동 스냅숏이 꺼졌으면 알림은 지금까지와 같다.
    10-27 확인 고침: 나무 다 자람처럼 큰 바뀜과 **한 묶음에 든 세기만 바뀐 지역도 알림 글에서 뺀다** (고치기 전 조연우 맵 `환경 바뀜 #27 — Barren: 나무 0→6 · Barren: 비→비`
    → 고친 뒤 `환경 바뀜 #27 — Barren: 나무 0→6`, 기록 줄의 날씨 칸은 그대로 — 자동화 `Policy.V3.EnvWatch.BigRule` 1b).
  - 10-27 확인 (창 없는 실제 실행 — FOREST_GROWTH_MODE.md 9.4): 통합 맵 기본 숲 = 190.0 초(전역 스텝 1425) 스냅숏 하나, 숲 목표 9(+9) = 0·목표 10 = 110.0 초 하나.
    조연우 복사 맵 실시간 400 초: 숲 끔 = 환경 판 247(세기만 234)·화면 알림 13(종류만)·**스냅숏 0**(비 약 108 초·맑음 약 72 초 이어져 120 초 못 넘김),
    숲 켬 = 213.1 초(전역 스텝 1598) 하나 — 나무 조건으로 쓰고 고지 종류 바뀜(193.1 초) + 20 초만큼 늦었다.
  - 상태 줄(AutoAdapt — 5.4)의 `환경 #n` 뒤 칸: `다시 배우기까지: 메마른 땅 나무 +7/10 · 날씨 그대로` → `다시 배우기: 조건 됨 — 숲이 다 자랄 때까지 기다림 (45/300초)` →
    `다시 배우기: 조건 됨 — 바뀜이 멈추길 기다림 12/20초`. `eco.IntegratedV3.EnvInfo` 첫 줄에도 같은 글.
  - 이 규칙은 **언제 쓰는지만** 바꾼다 — 세계에 넣는 것은 그대로다 (10-27 확인: 규칙 0·1 두 판의 사슴 줄이 바이트까지 같고 스냅숏 수만 4 → 1, FOREST_GROWTH_MODE.md 9절).
  - `0` = 옛 동작: 마지막 환경 판이 `AutoSnapshotSettle`(시뮬레이션 3 초) 동안 그대로면 판마다 한 번 (자동화 `Policy.V3.EnvWatch.AutoSnapshot` 은 규칙 0 을 걸고 본다).
  - 명령줄 시작값: `-EcoV3AutoSnapshotRule=`·`-EcoV3BigTrees=`·`-EcoV3WeatherHold=`·`-EcoV3BigSettle=`·`-EcoV3BigMaxWait=`·`-EcoV3EnvNoticeMinor=`.
- `eco.IntegratedV3.SnapshotEvery` (시뮬레이션 초, 기본 0 = 끔): 주기 스냅숏(`periodic`). `eco.IntegratedV3.AutoSnapshotOut` (기본 `<AdaptRoot>/snapshots` — 5.5).
- 모든 스냅숏 쓰기(자동·주기·콘솔·예정)는 `.tmp` 에 쓰고 옮겨 바꾼다.

### 5.3 시험용 대역 (레벨 팀이 할 일을 흉내 낼 뿐 — 세계 규칙이 아니다)
- `eco.IntegratedV3.Test.AddTrees <지역> <수> [씨]`: 명령(`EcoV3PlaceTreesCommandlet`)과 같은 나무 + 줄기 막이 짝을 무대 안 빈자리(은신처·다른 줄기·가장자리에서 떨어진 곳,
  땅에 붙임)에 놓는다. `Test.RemoveTrees <지역> <수>`: 놓은 짝을 나중 것부터. **단독 실행만**(짝을 복제하지 않아 서버에서 놓으면 클라이언트 충돌과 달라진다).
- `eco.IntegratedV3.Test.At <초> <명령>[; <명령>…]`, 명령줄 `-EcoV3TestAt=<초> -EcoV3TestCmd="명령1; 명령2"`(쌍 여러 개): 시뮬레이션 초에 콘솔 명령을 한 번.
  예약 명령이 바꾼 콘솔 변수는 Play 가 끝나면 예약 전 값으로 되돌린다.
- **숲 자람 모드** (10-27 — `S/AI/Policy/EcoV3ForestGrowth.{h,cpp}`·`EcoV3ForestTree.{h,cpp}`, 시험 모드·세계 규칙 아님. 설계·확인 FOREST_GROWTH_MODE.md):
  `eco.IntegratedV3.ForestGrowth`(기본 0, 명령줄 `-EcoV3ForestGrowth`). 켜면 `ForestRegion`(기본 Barren) 무대에 `ForestPerStage`(6) 그루씩 `ForestStageSeconds`(40 초)마다
  묘목이 돋아 `ForestGrowSeconds`(20 초) 뒤 다 자라고 `ForestTarget`(24)에서 멈춘다. 첫 단계 `ForestStartSeconds`(30 초), 자리 씨 `ForestSeed`(−1 = 세션 시드), 묘목 크기 몫
  `ForestSapling`(0.15, 그리기만). 모두 Play 시작 때 한 번 읽는다(명령줄 `-EcoV3Forest*=`).
  - 자리: 지역 세계가 생긴 직후 목표 수만큼 한꺼번에 — `Test.AddTrees` 와 같은 규칙(벽 4 m·은신처 원 + 2 m·다른 원판 + 3 m 밖, 크기 1.8~2.2, 땅에 붙임), 난수
    `HashChain3("V3FG", 씨, 지역 색인 + 1)` 하나에서 그루 순서대로. 씨가 같으면 같은 자리.
  - 묘목(복제 액터 `AEcoV3ForestTree`, 꼬리표 `EcoV3Tree`·`EcoV3TreeId_<지역>_F<nn>`)은 줄기 막이 충돌이 없고 꼬리표 `EcoV3Trunk` 도 없어 아무것도 막지 않는다.
  - 다 자람은 처리기 결정 스텝 경계(`ForestStepBoundary` — 환경 넣기 바로 앞)의 정확한 전역 스텝(기본 375·675·975·1275)에서: 줄기 막이 BlockAll·꼬리표 `EcoV3Trunk` →
    나무만 다시 읽기(`PollEnvironment(true, true)`) → 같은 경계의 `ApplyEnvChange` 가 출처 `forest_growth` 로 넣는다 — 레벨 나무와 같은 길, 먹이 격자 그대로.
    실시간 읽기 주기·fps·프레임 나눔과 무관하다 (10-27 확인: fps 30·20 판의 사슴 줄이 바이트까지 같다).
  - 복제(bReplicates·bAlwaysRelevant, 계획 값은 double 그대로, 다 자람 `bMature` 는 서버 값)라 단독·리슨·데디케이티드 + 클라이언트가 같은 나무·줄기 충돌을 갖는다
    (클라이언트도 같은 정적 함수로 변환을 셈한다). 다 자랄 때 기록 `[EcoV3I] 숲 Barren_F07 다 자람 (단독|리슨 서버|데디케이티드 서버|클라이언트) | 줄기 충돌 켬 · 줄기 변환 지문 …`.
  - 화면 줄 `숲이 자라는 중 — 메마른 땅 나무 12/24 (묘목 6 그루 자라는 중)`(키 732005, 클라이언트도 복제된 나무를 세어 같은 줄). 보기 `eco.IntegratedV3.ForestInfo`.
  - 거부(아무것도 놓지 않고 까닭 한 줄): 그 지역 v3 무대 없음·환경 감시 끔·그 지역 장애물 끔·원판 가져옴·실행 중 무대 나무가 서 있음.
  - `Test.RemoveTrees` 는 숲 나무를 지우지 않고, `Test.AddTrees` 는 숲 자리를 피한다. 끄면 숲 코드가 돌지 않는다 (10-27 확인: 끈 판의 사슴 줄이 바꾸기 전 빌드와 바이트까지 같다).
  - 10-27 확인 (구현 뒤 창 없는 실제 실행 — FOREST_GROWTH_MODE.md 9.4, `UnrealEditor-Cmd … -game -NullRHI -benchmark -fps=30 -EcoV3ForestGrowth`, 시드 20010): 묘목 30·70·110·150 초,
    다 자람 50·90·130·170 초(전역 스텝 375·675·975·1275)에만 세계 원판이 늘고(40 초 `EnvInfo` = 묘목 6 · Barren 세계 원판 0), 24/24 에서 `더 돋지 않음`. 같은 씨 230 초 사슴 줄
    644202 개가 세 판 모두 같고, 끈 판 121 초 343218 개가 `ae91f90` 기록(md5 `6386f290…`)과 같다. 리슨 + 클라이언트 1·데디케이티드 + 클라이언트 2(늦게 들어온 하나 포함):
    클라이언트 다 자람 줄기 지문 24/24 = 서버, 크기·회전·줄기 막이 24/24 같음, 클라이언트는 숲을 따로 계획·돋우지 않는다(계획 줄 0 개).

### 5.4 두뇌 교체 화면·되돌리기 (`S/AI/Policy/EcoV3Brain.{h,cpp}`, `SyncBrain`)
- 되돌리기 쌓개(16): 바꿀 때마다 나가는 두뇌를 쌓는다. `eco.V3Brain.Rollback`(다음 결정 스텝 경계에서 바로 앞 두뇌로, 두 번 누르면 둘 앞), `eco.V3Brain.History`.
- 두뇌 파일 `adapt` 블록(3절)을 읽어 판 번호를 보인다. 감시: Play 시작 때 있던 파일은 읽지 않음(`PrimeWatch`), 3 초 안에 깨진 새 파일은 다시 읽음,
  `adapt.play_id` 가 지금 Play 와 다르면 받지 않음(까닭 '다른 Play').
- 화면 알림(`eco.V3Brain.Notice`, 기본 1 — `eco.V3Debug` 와 상관없이, 그리는 실행에서만, 클라이언트 아님. 모든 알림은 기록 `[EcoV3I] 알림 | …` 으로도 남는다):
  새 두뇌(판·id·환경·관문·되돌리기 안내), 되돌림, 두뇌 파일 거부, 환경 바뀜, 스냅숏 내보냄, 그리고 상태 줄
  `두뇌 판 3 (live_r3…@abcd) · 교체 3번 · 환경 #2 · 적응 고리 | <status.message>`.
- `eco.V3Brain.NoticeShot` (기본 0): 바꿈·되돌림 알림 1.5 초 뒤 화면 찍기(`Saved/EcoAdapt/shots`). `eco.V3Brain.StatusFile`(기본 빈 값 = AutoAdapt 면 `<AdaptRoot>/status.json`).

### 5.5 Play 때 파이썬 감시 자동 시작 (10-27 — `S/AI/Policy/EcoV3WatchLauncher.{h,cpp}`, 훅은 `EcoPolicyV3IntegratedSubsystem.cpp`)
- **AGENTS.md 원칙과의 관계**: 게임 런타임 추론은 지금처럼 **C++ 네이티브만**이다 — 사슴 결정은 내장·두뇌 파일 가중치를 C++ 가 계산한다. 자동으로 띄우는 것은
  **학습 파이프라인(`live.py watch`)을 따로 띄우는 개발용 도구**다: 추론이 아니고, 게임 스레드를 막지 않으며(띄우기 몇 ms, 살아 있나 보기는 2 초마다 기다림 없는
  `WaitForSingleObject(…, 0)`, 끝낼 때만 최대 3 초), `#if !UE_BUILD_SHIPPING` 이고, `eco.IntegratedV3.AutoAdapt` 를 켰을 때만, 서버·단독 월드에서만 돈다. 파이썬이 내는 것은
  지금처럼 두뇌 파일뿐이고, 언리얼은 그것을 결정 스텝 경계에서 C++ 가중치로 바꿔 끼운다.
- 스위치 (Play 시작 때 읽음): `eco.IntegratedV3.AutoWatch`(기본 1 = AutoAdapt 를 따름, 0 = 안 띄움, `-EcoV3AutoWatch=`) · `AutoWatchPython`(기본 `python` — PATH 에서 찾아 전체
  경로로 기록, `\WindowsApps\` 스토어 대역은 쓰지 않음. 이 컴퓨터는 `C:\Users\Sinhyeok\anaconda3\python.exe`) · `AutoWatchCmd`(시험용 덮기 — 실행 파일 뒤 인자, 자리표
  `{root}`·`{play}`·`{log}`) · `AutoWatchDir`(빈 값 = `<프로젝트>/../herbivore_rl`) · **`eco.IntegratedV3.AdaptRoot`**(빈 값 = `Saved/EcoAdapt` — 스냅숏 `<root>/snapshots`·두뇌 감시
  `<root>/brains`·상태 파일 `<root>/status.json`·감시 `--root` 의 기본을 하나로 묶는다. 시험은 이것 하나만 바꿔 실제 폴더를 건드리지 않는다, `-EcoV3AdaptRoot=`).
- 띄우는 명령: 작업 폴더 `herbivore_rl` 에서 `<python> -X utf8 -u results/v3/live/live.py watch --root "<root>"`, 표준 출력·오류 = `<root>/watch_<play_id>.log`(최근 20 개만 남김).
  `-X utf8` = `PYTHONUTF8=1` (편집기 환경 변수는 바꾸지 않는다). `--existing` 은 주지 않는다(앞 Play 의 스냅숏으로 배우지 않게).
- 창 없이·나무째: `CreateProcessW`(`CREATE_NO_WINDOW` — 숨은 콘솔을 판·학습 자식이 물려받아 창이 없다, 물려줄 손잡이는 기록·NUL 둘뿐)를 **멈춘 채** 만들어 윈도 작업 개체
  (`KILL_ON_JOB_CLOSE`)에 넣은 뒤 깨운다 — 감시가 자식을 띄우기 전에 작업 개체 안이다. Play 끝(서브시스템 `Deinitialize`, 띄운 그 서브시스템만)에 작업 개체째 끝내고
  (`[EcoV3I] 파이썬 감시 끝냄 | pid n (우리가 띄움) · 학습 자식 포함 프로세스 나무째 (작업 개체) · 기록 … · 까닭: Play 끝`), 편집기가 죽으면 작업 개체 손잡이가 닫히며 함께 끝난다.
  10-27 적대적 검토 고침: Play 중 통합 v3 모드가 꺼지면(조정자 시작 실패·자원 계약 거부) 그 뒤 첫 프레임에 같은 길로 끝낸다(`까닭: 통합 v3 모드가 꺼짐` — 꺼진 뒤에는 스냅숏·
  두뇌 교체·감시 살핌이 멈추므로). 확인(FOREST_GROWTH_MODE.md 9.5): 자동화 `Policy.V3.WatchLauncher.Deactivate`, 한글·빈칸 든 `AdaptRoot` 로 진짜 감시가 뜨고, Play 를 셋 잇고,
  우리 `UnrealEditor-Cmd` 를 강제로 끝내도(크래시 대역) 감시 나무가 남지 않는다.
- 중복 방지(먼저 맞는 것에서 멈춤): 이 편집기가 띄운 감시가 산다 → `<root>/live/watch.lock`(live.py 잠금) 주인이 산 python(시작 시각 0.5 초 안) → `[EcoV3I] 파이썬 감시 | 이미 돈다 —
  사람이 띄움, 건드리지 않음 — pid n` (상태 줄 끝에 ` (사람이 띄운 감시)`) → `<root>/watcher.pid`(언리얼이 띄울 때 쓰는 JSON) 주인이 산다 → 다른 언리얼이 띄움. 죽은 pid 의
  `watcher.pid` 는 지운다. 그래도 경주가 나면 live.py 의 O_EXCL 잠금이 마지막 심판이다. 사람이 띄운 감시·다른 워크플로의 파이썬·live.py 의 파일은 건드리지 않는다.
- 안 띄움: AutoWatch 0 · AutoAdapt 0 · 자동화 시험 중 · 클라이언트 · **폴더 안전장치**(스냅숏·두뇌 감시·상태 파일이 한 root 아래가 아님 — 예 `level_jyu_eco` 스모크처럼 따로
  덮은 시험 꾸밈) · python·live.py 없음 → 상태 줄 `적응 고리 | 파이썬 감시를 못 켬 — <까닭>`.
- 상태 줄 '적응 고리 | …' (FOREST_GROWTH_MODE.md 3.7·3.8): 우리가 띄웠고 `status.json` 이 띄운 뒤에 고쳐지지 않았으면 `파이썬 감시 켜는 중 (n초)`, 감시가 끝나면 기록 끝
  줄로 까닭 — `flight_sizes_confirmed`(실제 폴더 잠김) → `파이썬 감시 꺼짐 — 실제 폴더 잠김 (관문 크기 확정 전)` + 화면 알림 한 번, `다른 실시간 고리` → `다른 감시가 돈다 (pid n)`,
  그 밖 종료 코드 ≠ 0 → `파이썬 감시 꺼짐 — 종료 코드 n (기록 watch_<play>.log)` + 알림, 0 → `파이썬 감시 끝남`. 다시 띄우지 않는다. 글이 바뀌면 기록
  `[EcoV3I] 적응 고리 감시 | …`.
- 쓰는 순서가 바뀐다: 사람이 `live.py watch` 를 먼저 띄워 두면 언리얼은 그것을 쓴다(위 중복 방지). 언리얼이 먼저 띄웠는데 사람이 또 띄우면 사람 쪽이 live.py 잠금으로
  '다른 실시간 고리' 로 끝난다. 실제 폴더 고리의 두뇌 묶음 규칙(`LIVE_GATE.md` 변경 기록 (10) — 판 5 두뇌로 시작한 Play 만)은 언리얼에 다시 적지 않고 파이썬 상태 글을 그대로 보인다.
- 10-27 확인 (창 없는 실제 실행 — FOREST_GROWTH_MODE.md 9.4. 모두 `-EcoV3AdaptRoot=<scratch>`, 실제 `Saved/EcoAdapt` 파일 29 개는 전후 그대로, 우리 프로세스의 보이는 창 0):
  - 진짜 감시: `-EcoV3AutoWatchCmd="-X utf8 -u results/v3/live/live.py watch --root {root} --ckpt <scratch> --steps 20000 --judge-seeds 35000-35001 … --workers 4"`(시험 root·시험 크기),
    짧은 숲 + `-EcoV3Brain=v3_r7_g995_s1_20m` 실시간: 상태 줄 `켜는 중 (0초)` → `스냅숏 기다림` → 55.1 초 스냅숏 → `새 환경 — 시도 1 시작` → `학습 중 0/20k` → `후보 판정 0/15 세계`
    → `기각 — 게임 두뇌 그대로 (1차 사건 숨음 비율 19.8%→20.6% t +0.5 (문턱 +12.71))` (스냅숏부터 52 초). 시험 크기(판정 시드 2)라 관문에서 멈춘다. `--force-export` 를 더하면
    `exported` → 94.3 초(전역 스텝 707) `두뇌 바꿈 | v3_r7_g995_s1_20m@40d8710d → live_r1_…@06b992e9`. 학습 400k 로 Play 가 판정 중(3/15)에 끝나도 감시·`round`·`train-one`·
    일꾼·`EcoV3Eval` 자손 15 개가 모두 사라졌다. 다른 워크플로의 python 은 우리 자손에 한 번도 없었고 그쪽 주 프로세스는 전후 살아 있었다.
  - 중복 방지: 손으로 먼저 띄운 가짜 감시(`live/watch.lock`)가 있으면 `이미 돈다 — 사람이 띄움, 건드리지 않음 — pid 25440` 이고 그 감시는 언리얼이 끝난 뒤에도 제 수명까지 돌았다.
    같은 root 로 언리얼 둘이면 뒤 것이 `이미 돈다 — 다른 언리얼 프로세스가 띄움 — pid 33116` 이고, 먼저 끝나도 앞 것의 감시를 끄지 않는다.

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
