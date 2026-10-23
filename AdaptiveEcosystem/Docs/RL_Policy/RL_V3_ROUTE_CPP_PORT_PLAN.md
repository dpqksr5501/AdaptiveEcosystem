# 두 길 두뇌 C++ 이식 계획서 (RUN·SHELTER, 관측 24·마스크 판 4)

- 상태: 계획만 적었다. 코드·빌드·UBT·자동화·학습은 하지 않았다.
  - 10-23 검토: 파이썬 줄과 다시 대조해 의사 코드의 남은 값 버그 둘(2-7 (나) 길 읽음 지우기 자리, (다) `bCommittedRouteReads`), `A0` 범위, 도주 아님 지울 칸,
    refled 스텝 번호를 고쳤다. 10-1·10-2 를 실제로 만든 골든·판 대조 자료(`results/v3/route/port/`)에 맞췄다(시드 2 개, 스텝 지문, 도망 길 기록 장면).
- 기준 커밋: 파이썬 두 길 구현 `c109bf0`, 10 초 지켜보기 `2aac3e5`(HEAD).
  - 파이썬 줄 번호는 HEAD `2aac3e5` 의 `herbivore_rl/…` 이다(작업 트리와 같다).
  - C++ 줄 번호는 `git show 2aac3e5:AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/<파일>` 이다. 작업 트리의 `EcoWorldV3.h` 는 다른 갈래(숨음·잡힘 비율)가
    고치는 중이라 줄이 밀려 있다.
- 설계: `RL_V3_FLIGHT_ROUTE_DESIGN.md` 16절(16-12 'C++ (다음 단계)', 16-14 단계 6)을 구체화한다. 뜻이 부딪치면 16절을 따르고, 이 문서의 '열린 질문'(12절)에 적는다.
- 지킬 것 (AGENTS.md 2절 4·5·10항):
  1. **끈 세계는 지금 C++ 와 비트 단위로 같다.** 새 줄은 모두 `W.Config.WildFlight.bRoute` 안에 둔다. 판 2 두뇌(관측 18·21)는 길이 늘 꺼져 있다.
  2. **옮기는 것은 두뇌 길(`wild_flight.route`)의 RUN·SHELTER 뿐이다.** COVER 기하, OPEN, 측정 전용 `route_fixed`, 끝 규칙 `quiet_end`, 오라클
     `route_redecide`, 학습 전용(`rep_peek`·ε 섞기·f_dec·`flight_cost`)은 옮기지 않는다.
  3. 런타임 파이썬 없음. 추론은 지금 `EcoPolicyV3::RunPolicyV3` 그대로다(망 모양 그대로, 첫 층 열만 24).
  4. 단일 이동 writer 그대로다. 길은 덮기 방향 `FHerbDecision::KeepDir` 만 바꾼다. 실행 행동은 늘 FLEE 다(애니메이션·Social 인계·G6 그대로).

---

## 0. 한눈에 — 파이썬 줄 ↔ C++ 자리

| 파이썬 (HEAD) | 하는 일 | C++ 자리 (새 = ★) |
|---|---|---|
| `env_v2/world.py:1416-1436` | 길 번호·잠금 15·SHELTER 문턱·관측 분모·칸 번호 | ★ `EcoWorldV3.h` 상수 묶음(`FWildFlightConfig` :164 옆), ★ `EcoObservationV3.h` 관측 칸(:470-479 뒤) |
| `world.py:1548-1586` `_wild_flight_params` | 선택 키 `route` 검사 | ★ `FWildFlightConfig::bRoute`, `InitWorld` :1712 정리, 로더·평가기 검사 |
| `world.py:832-833` `obs_names` | 관측 24 이름 | ★ `kRouteObsNames`, `EcoV3Brain.cpp:34-38` 계약 줄 |
| `world.py:2339-2346` `wf_wall_keep` | 벽 여유 | ★ `Detail::WallKeep` = `UpdateWildFlight` :2451-2462 를 함수로 뽑음(연산 그대로) |
| `world.py:2487-2526` `_route_shelter` | SHELTER 후보·k*·μ*·e*·유지 | ★ `Detail::RouteShelterGeometry` |
| `world.py:5876-5877`, `5911-5916` | a₀ 뜨기, 길 단계 부르기 | `UpdateWildFlight` :2415 뒤 `A0`, :2463 뒤 ★ `RouteStep` |
| `world.py:5981-6095` `_route_step` | 결정 표시·무효·잠금·관측 세 칸 | ★ `Detail::RouteStep` (UpdateWildFlight 안, 사슴마다) |
| `world.py:4105-4109`, `6097-6126` `_route_apply` | 다음 스텝 첫머리에 두뇌 요청 적용 | `Step` A 루프 :2709 첫머리 ★ `Detail::RouteApply` |
| `world.py:4334-4340` | 관측 21~23 쓰기 | ★ `FHerbPerception::RouteObs[3]` (H 에서 RouteStep 이 씀), `DecideHerb` 망 입력 :2182-2196 |
| `env_v2/rep_policy.py:261-281` `_route_rows` | 판 4 마스크 줄 | `DecideHerb` 덮기 분기 :2160-2176 안 ★ 길 결정 줄 |
| `rep_policy.py:176-195`, `rollout.py:747-749` | 판 판정·얼기·잠 막힘 | `EcoV3Brain.cpp` 계약 표·허용 검사, ★ `SyncBrain`·평가기 `Init` 실제 허용 검사 |
| `export_weights_v3.py:230-257` | 계약 키·해시 | `EcoPolicyV3Inference.h:61-65` ★ `kContractHashObs24Mask4` |
| `world.py:7172-7176` | 결정 셈(decide_frac) | `Step` A :2757 `Stats.Decisions` 에 길 결정 더함 |
| `world.py:6146-6161`, `6219-6237`, `6257-6268`, `6285-6395`, `6464-6489` | 길 통계·도망의 길별 기록 | ★ `FRouteStats`, ★ `FFlightRouteStats`, `FlightUpdate` :742 선택 인자 |
| `results/v3/live/ceval.py:332-336` 외 | 평가기가 길 세계 거부 | `ceval.py` 받기, `Tools/EcoV3Eval/EcoV3Eval.cpp` LoadBrain·Init·trace·WriteFlight |

---

## 1. 설정 키와 C++ 칸

### 1-1. 파이썬 키

- `features.wild_flight.route` (OPTIONAL_KEYS 기본 `False` — `env_v2/features.py:333-334`). 끄면 `World._route_brain` 거짓이고(`world.py:2695`) 길 코드 경로를 타지 않는다.
- 켤 수 있는 조건(`world.py:1575-1585`): bool, `route_fixed` 와 함께 못 켬, `repertoire.obs_extra` ∧ `obstacle_obs` 필수(관측 21 위), `alarm` 과 함께 못 켬.
  `quiet_end` 와는 파이썬이 막지 않는다(R6 설정은 0). C++ 은 `quiet_end` 를 옮기지 않으므로 평가기는 `quiet_end > 0` 세계를 계속 거부한다(12절 질문 14).
- 판정 거울 `configs/v3_wild3_route_mirror.yaml`(= `v3_wild3_obs_mirror.yaml` + `route: true`), R6 학습 `configs/v3_r6_train.yaml`.

### 1-2. C++ 칸 (모두 기본 꺼짐)

| 칸 | 기본 | 뜻·정하는 곳 |
|---|---|---|
| `FWildFlightConfig::bRoute` (★, :164-179 끝에 더함) | `false` | 두뇌 길. **세계 설정이 아니라 두뇌가 정한다** — 통합 모드는 `SetModelRoute`(★)가 판 4 두뇌일 때만 켠다. 평가기·골든은 일의 `world.wild_flight.route` 로 넣는다 |
| `InitWorld` :1712 | — | `W.Config.WildFlight.bRoute = C.WildFlight.bRoute && C.WildFlight.bEnabled` (파이썬도 wild_flight 없이 못 켠다) |
| `SetModelRoute(FWorldState&, bool)` (★, `SetModelObsDim` :1792 옆) | — | `bRoute = b && W.Config.WildFlight.bEnabled` (InitWorld 와 같은 묶음 — 도주 반사가 없는 지역에서 켜지지 않는다. 걸기 전 거부는 8-2). 끌 때 길 상태는 다음 H 에서 지운다(8-2) |
| `SetModelObsDim` :1792-1795 | 18 | 24 도 받게 고친다: `ObsDim ∈ {21, 24}` 이면 그 값, 아니면 18. `ObserveObstacleObs` :2072 의 `W.ObsDim >= 21` 조건은 24 에도 맞으므로 그대로 |
| `EcoObservationV3::kMaxObsDim` :475 | 21 | 24 로 올리거나 지운다(쓰는 곳 없음 — grep 확인). `EcoPolicyV3::kMaxObsDim` :56 은 이미 32 라 그대로 |

### 1-3. 계약 상수 (설정이 아니다 — 해시가 지킨다)

`world.py:1416-1436` 와 같은 값의 C++ 리터럴. COVER·OPEN 상수(1419-1426)는 옮기지 않는다.

```
kRouteNone −1, kRouteRun 0, kRouteCover 1(자리만), kRouteShelter 2, kRouteOpen 3(자리만), kNumRoutes 4   // world.py:1416 — 기록 칸 번호까지 같게
kRouteLockSteps 15                                                                                   // :1418
kRouteShelterMaxEdgeU 20.0, kRouteShelterCosMin 0.0, kRouteShelterEnterU 2.0, kRouteShelterExitU 0.0  // :1427-1429
kRouteShelterReachU 10.0, kRouteShelterEdgeNormU 20.0                                                // :1430, :1435
kRouteFeasShelter 2                                                                                  // :1431 (COVER 비트 1 은 쓰지 않는다)
kRouteSlotRun 1 (FLEE), kRouteSlotShelter 4 (SLEEP), kRouteSlotReserved 3 (FREEZE)                   // :1436, rep_policy.py:87
kFlightRefleeSteps 38                                                                                // :1437 (도망 기록 GR)
관측: kNumRouteObs 3, kObsDimRoute 24, kObsInPanic 21, kObsShelterReach 22, kObsShelterEdge 23,
      kRouteObsNames = {"in_panic", "shelter_reach", "shelter_edge"}                                 // :1434
계약: kContractHashObs24Mask4 = 0xe302dee198197444ULL                                                 // export_weights_v3.py:230-257, 16-5
```

---

## 2. 스텝 안 차례

### 2-1. 파이썬 한 스텝과 C++ 한 Step 의 짝

| 순서 | 파이썬 `World.step` | C++ `Step` (EcoWorldV3.h) |
|---|---|---|
| 1 | `4105-4109` `_route_override` 를 뜬 뒤 `_route_apply(a[:, 0])` — 지난 H 의 길 결정에 두뇌 요청을 적용 | A 루프 :2709 첫머리 ★ `RouteApply` (Commit 앞) |
| 2 | `4116-4118` `wf_exec`·`rt_exec`(적용 **뒤** 길)를 떠 둔다 | 실행한 길 = 이 뒤 `D.Route` (H 의 `FlightStepEnd` 까지 그대로) |
| 3 | `4127` `_rep_step` — 덮기 FLEE, 제어기 `away_from_pred = wf_dir` (`4592-4597`) | A :2726-2734 `CommitFlight`, B :2779-2786 `FlightControlInput`(`KeepDir`) |
| 4 | `4282` t+1, `4285` `_rep_accumulate` 결정 셈 (`7172-7176`) | A :2757 `Decisions` 셈 (★ 길 결정 더함), D :3230 T+1 |
| 5 | `4302-4319` 관측 (길 세 칸은 0 — `4028-4029`) | E :3261 `ObserveAll` (`RouteObs` 는 건드리지 않는다) |
| 6 | `4321-4331` 리스폰·매장 (`5625-5627` 길 지움) | G :3266-3305 (C++ 은 `UpdateWildFlight` 의 죽음 분기가 지운다) |
| 7 | `4333` `_wf_update` → 반사(5826-5908) → `5876-5877` a₀ → `5911-5916` `_route_step` → `5926-5929` `_fl_update(rt_exec)` | H :3308-3316 `FlightStepEnd`(실행한 길) → `UpdateWildFlight` (+★ `RouteStep`·관측 세 칸) |
| 8 | `4334-4340` 관측 21~23 쓰기, 죽은 사슴 `terminal_obs` 0 | ★ `RouteStep` 이 `FHerbPerception::RouteObs` 에 쓴다 |
| 9 | (step 밖) 정책: 관측 24 + 판 4 마스크 → `a` | H :3317 `DecideAll` → ★ 길 결정이면 망을 돌려 `D.RouteRequest` |

- **파이썬은 두뇌 출력을 다음 step 첫머리에 적용하고, C++ 은 H 에서 고른 뒤 다음 A 에서 적용한다.** 둘 사이에 이 값을 읽는 것이 없어 같은 결과다.
  - H 에서 곧바로 `D.Route`·`KeepDir` 를 바꾸지 않는 까닭: 고른 길·바꿈 셈을 파이썬처럼 '적용한 스텝'에 세야 하고(6-1), 궤적 대조에서 스텝 끝 `route` 칸이
    파이썬(`_route_apply` 전 값 — 결정 스텝은 RUN)과 같아야 하기 때문이다(7-3).
- `FlightStepEnd` 가 `UpdateWildFlight` 앞이라 도망 기록은 **실행한** 길(= 적용 뒤, 길 단계 전)을 읽는다. 파이썬 `rt_exec`(4118)와 같다.

### 2-2. 결정 조건 (`world.py:5998-6037`, 설계 16-3)

```
pan    = Next == kKeepPanic                       (5998 — nxt == WF_PANIC, 죽은 사슴은 5862 에서 이미 WF_NONE)
onset  = pan ∧ Prev ≠ kKeepPanic                  (5999 — Prev = D.KeepActive, 파이썬 prev = 이번 스텝 wf_mode)
cur    = onset ? NONE : D.Route                   (6019)
keep   = cur == SHELTER ? D.RouteK : −1           (6021)
feas   = SHELTER 가능 ? 2 : 0                      (6028 — COVER 비트 없음)
inval  = cur == SHELTER ∧ ¬keep_ok                (6029 — RUN 은 무효가 없다)
age    = onset ? 0 : D.RouteAge + 1               (6033 — 먼저 더하고 본다: 결정 뒤 15 스텝을 실행하면 다시 고를 수 있다)
refeas = cur ≥ 0 ∧ ¬inval ∧ age ≥ 15 ∧ feas ≠ D.RouteFeas ∧ cur ≠ SHELTER    (6034-6036 — refeas_from = RUN 만)
dec    = onset ∨ cur < 0 ∨ inval ∨ refeas         (6037)
```

- 결정 조건은 셋(시작·SHELTER 무효·RUN 길에서 2 초 뒤 가능 바뀜)에 **넷째 `cur < 0`** 이 있다. 파이썬에서는 시작과 겹쳐 따로 일어나지 않지만,
  C++ 두뇌 교체(길 없는 두뇌 → 판 4 두뇌)에서는 열린 도망이 길 상태 없이 들어오므로 이 줄이 실제로 쓰인다(12절 질문 1).
- COVER 가능이 바뀌어도 다시 고르지 않는다(COVER 를 셈하지 않으므로 저절로 그렇다).

### 2-3. 결정 뒤 상태 (`world.py:6038-6073`)

```
new        = dec ? RUN : cur                      (6039-6046 — 두뇌 모드는 want = RUN, ok[RUN] 늘 참)
Dir        = new == SHELTER ? keep_dir : 반사 Dir (6047-6055 — RUN 행은 반사 방향 비트 그대로, 결정 스텝도 RUN)
D.Route    = new;  D.RouteK = new == SHELTER ? keep : −1             (6056-6057)
D.RouteAge = dec ? 0 : age;  D.RouteFeas = dec ? feas : (그대로)     (6059-6060)
D.bRouteDecide = dec; D.bRouteSok = SHELTER 가능; D.RouteCandK = k*(불가 −1); D.RouteShelterDir = shelter_dir   (6061-6064)
D.RouteMu = 가능 ? μ* : 0;  D.RouteE = 가능 ? e* : 0;  D.RouteDecPrev = dec ? cur : NONE                       (6066-6070)
RouteObs   = (1, 가능 ? f32(clip(μ*/10)) : 0, 가능 ? f32(clip(e*/20)) : 0)                                       (6071-6073)
도주 아님(Next ≠ Panic): Route NONE, RouteK −1, Age 0, Feas 0, bRouteDecide 거짓, bRouteSok 거짓, CandK −1, RouteShelterDir 0, RouteMu·RouteE 0,
                        RouteDecPrev NONE, RouteObs 0     (6000-6014 의 기본값 — new_*·c_ok·c_k·c_mu·c_e·dec_prev·r_obs, 5973-5979)
```

- 상태 지우기(도주 끝·웅크림·죽음·다시 남·reset)는 모두 '도주 아님' 줄 하나로 된다. C++ 죽은 사슴은 `UpdateWildFlight` :2333-2344 분기에서 지운다.
  `InitHerb`·`AdoptHerb`(:1806, :1917)는 `FHerbDecision()`·`FHerbPerception()` 기본값이라 따로 지울 것이 없다.

### 2-4. SHELTER 가능·유지·무효 (`world.py:2487-2526`, 설계 6절 S)

입력: 사슴 p(스텝 끝 위치), a₀, 늑대 위치 q_m, S = `near_h`(C++ `NearH[m]`, m < Mc), 은신처 원(c_k, r_k), 무대 Size, 벽 여유 mg, 유지 은신처 keep.

```
k 마다 (낮은 번호부터):
  vx = c_k.x − p.x;  vy = c_k.y − p.y                      (2499-2500)
  dc = sqrt(vx·vx + vy·vy)                                 (2501)
  ed = dc − r_k                                            (2502)  가장자리 거리 e_k
  ds = max(dc, EPS)                                        (2503)  C++: dc > kEps ? dc : kEps
  ux = vx / ds;  uy = vy / ds                              (2504)
  xx = p.x + ed·ux;  xy = p.y + ed·uy                      (2505)  입구
  md = min_{m∈S} sqrt((q_m.x − xx)² + (q_m.y − xy)²)       (2506-2508)  S 가 비면 +∞
  mu = md − ed                                             (2508)  경주 여유 μ_k
  cs = (vx·a₀.x + vy·a₀.y) / ds                            (2509)
  후보 = dc > EPS ∧ ed > 0 ∧ ed ≤ 20 ∧ cs ≥ 0 ∧ mu ≥ 2       (2510-2511)
k* = 후보 가운데 ed 가 가장 작은 것, 같으면 낮은 번호         (2512-2514 — argmin 첫 번째, C++ 은 엄격한 <)
μ* = mu[k*], e* = ed[k*]                                   (2515-2516)
shelter_dir = WallKeep(p, (vx/ds, vy/ds)[k*])              (2517-2518 — 가장자리 굽히기 없음)
keep_mu  = keep ≥ 0 ? mu[keep] : −∞                        (2519-2521 — 후보 조건(ed·cos·2)은 보지 않는다)
keep_ok  = keep_mu ≥ 0                                     (2525)
keep_dir = WallKeep(p, (vx/ds, vy/ds)[keep])               (2522-2523)
```

- **가능(들어갈 때)** = 후보가 있음. **유지** = `keep_ok`(μ ≥ 0, 늑대가 문에 먼저 닿지 않음). 유지가 깨지면 무효 → 결정(그때는 다른 은신처를 고를 수 있다).
- 무리 늑대가 문을 지키는 은신처는 μ < 2 라 후보에서, μ < 0 이면 유지에서도 빠진다.
- 늑대 속도·날씨 배수는 쓰지 않는다(거리만).
- `WallKeep(p, d)` = `world.py:2339-2346` = C++ :2451-2462 의 줄 그대로다. 성분을 지우지 않았어도 **늘 Normalize 를 거친다** — 이를 빼면 끝자리가 달라진다(9절 R2).
- C++ 전용 두 줄 (파이썬 세계에는 없는 경우라 비트 일치와 무관):
  - 반경 0 원(통합 모드 지워진 은신처 — `RefreshRefuges` 가 번호를 남기고 반경만 0)은 후보에서 뺀다(`UpdateWildFlight` :2424, `PerceiveCover` :373 과 같은 규칙).
  - 유지 은신처가 반경 0 이거나 번호가 원 목록 밖이면 `keep_ok` 거짓(무효 → 결정).
- 도주 중이면 S 는 늘 비어 있지 않다(Nh ⊆ NearH — :2367·:2370, `world.py:5843-5849`). 그래도 μ = +∞ 이면 `clip` 이 1 로 받는다(9절 R7).

### 2-5. COVER 는 계산하지 않는다

- 두뇌 모드는 `flight_route_geometry(…, cover=False)`(`world.py:2435-2440`)로 COVER·숲 시야 그늘을 셈하지 않는다. OPEN 방향(2431)은 셈하지만 쓰지 않는다.
- 그래서 C++ 은 `SightBlocked`·`FoliageBlocked` 를 길에 부르지 않는다. 비용은 사슴마다 '은신처 수 × 늑대 수' 거리 계산뿐이다(16-12).
- 칸 3(COVER 자리)은 판 4 마스크에서 늘 막힌다(4절).

### 2-6. 실행 행동과 덮기 방향

- 실행 행동은 늘 FLEE 다. `DecideHerb` 의 덮기 분기 :2167 이 `Request = FLEE` 로 두는 것을 바꾸지 않는다. 고른 길은 `D.Route`(행동과 따로)에 둔다.
- 방향: RUN = 반사 `Dir`(가장자리 굽히기·반사의 은신처 쪽 도주 :2416-2444·벽 여유 포함 — 비트 그대로).
  SHELTER 결정 스텝 = A 에서 `KeepDir = D.RouteShelterDir`(H 의 k* 쪽), 유지 스텝 = H 에서 `Dir = keep_dir`(유지 은신처 쪽, 그 스텝 위치로 다시 잰 값).
- 이동 제어기(FLEE·`obstacle_slide`·돌아가기)는 그대로 `KeepDir` 만 받는다(`FlightControlInput` :2563-2571 = `world.py:4592-4597`).

### 2-7. C++ 의사 코드 (세 곳)

**(가) H — `UpdateWildFlight` 사슴 루프 안** (:2327 루프. 기존 줄은 그대로)

```cpp
const std::int32_t ExecRoute = D.Route;                        // 이번 스텝에 실행한 길 (world.py:5994·5995 executed)
if (bRoute && ExecRoute >= 0) ++W.Stats.Route.Steps[ExecRoute]; // world.py:5995-5997 — 죽음 분기(:2333) 앞
if (H.Body->DeathCause != kDeathNone) { …지금 줄…; ClearRoute(D, *H.Perception); continue; }
…위협 판정·Next (:2345-2388) 그대로…
FVec2 Dir; FVec2 A0;                                           // A0 는 :2389 의 Dir 옆에 둔다 — 경계·도주 블록(:2391-2463) 밖의 RouteStep 이 읽는다
…경계·도주 블록 안 반사 방향 (:2391-2415) 그대로…
A0 = Dir;                                                      // world.py:5876-5877 — :2415 와 :2416 사이 (영벡터 대신 가장 가까운 늑대 반대 뒤)
…반사의 은신처 쪽 도주·가장자리·벽 여유 (:2416-2462) 그대로…
if (bRoute) { if (Next == kKeepPanic) RouteStep(W, D, P, A0, NearH, Mc, Threats, Prev, Dir); else ClearRoute(D, Perc); }  // world.py:5911-5916
else if (D.Route != kRouteNone) ClearRoute(D, Perc);           // 길 끈 두뇌로 바뀐 뒤 남은 상태 (끈 세계에서는 늘 NONE 이라 비트 그대로)
…:2464 통계·:2471 풀림·:2477 D.KeepDir = Dir 그대로…
```

**(나) H — `DecideHerb`** (지우기는 함수 첫머리 :2154 `FHerbDecision& D` 뒤 — 모든 갈래, 망 부르기는 덮기 분기 :2160-2176 의 `D.bPrepared = true` 앞)

```cpp
// 함수 첫머리 (덮기·두뇌 결정·입양 첫 결정 모든 갈래): 지난 결정의 값이 남지 않게. 덮기 분기 안에서만 지우면 도주가 끝난 사슴의 bRouteReads 가 참으로
// 남아 다음 A 의 결정 수에 두 번 들고(2-7 (다)) trace 의 route_req 도 옛 값이 된다
D.RouteRequest = -1; D.bRouteReads = false;
…
// 덮기 분기 안 (Feasible·Mask·Logits 를 0 으로 둔 뒤)
if (W.Config.WildFlight.bRoute && D.KeepMode == kKeepPanic && D.bRouteDecide)
{
    D.Mask[kFlee] = 1;                                                    // rep_policy.py:278 (결정 줄 칸 1)
    D.Mask[kSleep] = H.Perception->RouteObs[1] > 0.0f ? 1 : 0;            // :276·:279 — 관측 22 > 0, 칸 3 은 0 그대로
    float NetIn[EcoPolicyV3::kMaxObsDim] = {};  /* 18 | 장애물 3 | 길 3 */
    D.RouteRequest = EcoPolicyV3::RunPolicyV3(Net, NetIn, D.Mask, D.Logits);   // 1 또는 4
    D.bRouteReads = true;                                                  // world.py:7175 — 길 결정은 결정이다
}
```
- 덮기가 아닌 결정의 망 입력(:2180-2200)도 `Net.ObsDim == 24` 면 `RouteObs` 세 칸을 붙인다(도주 밖이라 0).
- 길 결정 사슴은 `D.Mask`·`D.Logits` 가 이제 0 이 아니다(지금 덮기 사슴은 모두 0). `CommittedMask` 를 읽는 곳(평가기 trace 의 마스크 칸, 두뇌 몫
  기록 `FEcoV3BrainTally`, 마스크 확인 :2753-2756 — 덮기는 `W.Allowed` 로 보므로 그대로)이 '덮기 줄 = 0' 을 가정하지 않는지 이식 때 확인한다.
  실행 요청 `D.Request` 는 FLEE 그대로라 `MaskViolations` 는 바뀌지 않는다.

**(다) A — `Step` A 루프 첫머리** (방어 `DecideHerb` :2714-2718 뒤, `D.PrevBehavior` :2719 앞)

```cpp
D.bCommittedRouteReads = bRoute && D.bRouteReads;                         // if 밖 — 판 4 → 길 없는 두뇌로 바꾼 뒤 옛 참이 남지 않게
if (bRoute) {
    if (D.bRouteDecide && D.KeepMode == kKeepPanic) {                     // world.py:6106-6108
        const bool bWant = D.RouteRequest == kRouteSlotShelter;           // :6111
        const bool bSh = bWant && D.bRouteSok;                            // :6112
        R.BadShelter += bWant && !bSh; R.Choice += D.bRouteSok;           // :6113-6114
        ++R.Picked[bSh ? kRouteShelter : kRouteRun];                      // :6115-6116
        const std::int32_t Chosen = bSh ? kRouteShelter : kRouteRun;
        R.Switches += D.RouteDecPrev >= 0 && Chosen != D.RouteDecPrev;    // :6117-6119
        if (bSh) { D.Route = kRouteShelter; D.RouteK = D.RouteCandK; D.KeepDir = D.RouteShelterDir; }   // :6120-6126
    }
}
…
W.Stats.Decisions += (D.bCommittedReads || D.bCommittedRouteReads) ? 1 : 0;   // :2757 — world.py:7175 (dec ∧ ¬덮기) ∨ 길 결정
```
- `bRouteDecide` 는 지우지 않는다(다음 H 가 다시 정한다). A 는 Step 마다 한 번이라 파이썬 `_rt_applied`(6103-6105)와 같은 '한 번만'이 저절로 된다.

### 2-8. 새 상태 칸

- `FHerbDecision` (:1442-1468) 끝에 더한다: `Route`(−1), `RouteK`(−1), `RouteAge`, `RouteFeas`, `bRouteDecide`, `bRouteSok`, `RouteCandK`(−1),
  `RouteShelterDir`, `RouteRunDir`(12절 질문 2), `RouteMu`, `RouteE`, `RouteDecPrev`(−1), `RouteRequest`(−1), `bRouteReads`, `bCommittedRouteReads`.
- `FHerbPerception` (:1427-1439) 끝에 `float RouteObs[3] = {}`. `Obs[18]` 길이는 그대로 둔다(팀 진단이 그 길이를 관측 칸 수로 쓴다 — :1436 주석).
- 둘 다 Mass 조각(`EcoPolicyV3Fragments.h:54`, `:111`)에 들어 크기만 늘고, 끈 세계 값은 기본값 그대로다. 조각 전체를 memcmp 하는 시험은 없다(배열 칸 단위만).

---

## 3. 관측 21~23

| 칸 | 이름 | 값 | 파이썬 |
|---|---|---|---|
| 21 | `in_panic` | 다음 스텝 덮기가 도주면 1.0f, 아니면 0 | `world.py:6071` |
| 22 | `shelter_reach` | SHELTER 가능이면 `(float)Clip01(μ* / 10.0)` ∈ [0.2, 1], 아니면 0 | `:6072` |
| 23 | `shelter_edge` | SHELTER 가능이면 `(float)Clip01(e* / 20.0)` ∈ (0, 1], 아니면 0 | `:6073` |

- **계산 위치와 시점**: H 의 `UpdateWildFlight` 안, `Next` 를 정한 뒤(= 파이썬 `_wf_update` 뒤 `step` 4334-4340). E 의 `ObserveHerb` 는 건드리지 않는다
  (파이썬 `_obs_from` 도 이 세 칸을 0 으로 둔다 — `4028-4029`).
- **0 인 때**: 도주 밖(경계·웅크림 포함), reset 직후(`world.py:5963` — C++ 기본값), 입양 첫 관측(`ObserveAndDecideRows` — 기본값), 이번 스텝에 죽은 사슴
  (C++ 죽음 분기. 파이썬 `terminal_obs` 0 — `4340`, 부활 없는 세계의 관측 행도 `nxt[~live]` 라 0), SHELTER 가 가능하지 않은 도주(22·23 만).
- 도주 스텝마다 다시 잰 값이다(결정 스텝만이 아니다). SHELTER 를 유지하는 중에도 22·23 은 **새로 고를 수 있는 k\*** 의 값이다(12절 질문 6).
- `Clip01`(`EcoObservationV3.h:438`) = `np.minimum(np.maximum(x, 0), 1)` (NaN 없음, +∞ → 1). 나눗셈은 역수 곱으로 바꾸지 않는다.
- float 변환은 `static_cast<float>(double)`(가까운 짝수 반올림) = 파이썬 float64 → float32 배열 대입(`r_obs` dtype float32 — `6014`).
- **관측 24 계약 이름 순서**: `kObsNames` 18 칸(:57-60) → `escape_room`, `obstacle_near`, `threat_hidden`(:479) → `in_panic`, `shelter_reach`, `shelter_edge`.
  망 입력은 `[Obs 0..17 | ObstacleObs 0..2 | RouteObs 0..2]`. 로더 계약 줄의 `ExtraNames` 는 여섯 이름 배열이다(5절).
- 새 함수 `EcoObservationV3::WriteRouteObs(bool bPanic, bool bOk, double Mu, double E, float Out[3])` 하나에 둔다(골든이 이 함수를 직접 부른다).

---

## 4. 마스크 판 4

`rep_policy.py:261-281` `_route_rows` 와 `:254-255`(판 4 일 때만 덮기 행을 덮음). 판은 관측 이름으로 정한다(`:176-184` — `in_panic` 이 있으면 4).

| 상황 (C++ 조건) | 열리는 칸 | C++ |
|---|---|---|
| 도주 ∧ 길 결정 (`KeepMode == Panic ∧ bRouteDecide`) | 1 RUN, 4 SHELTER(관측 22 > 0) | `DecideHerb` 덮기 분기에서 망을 돌린다(2-7 (나)) |
| 도주 ∧ 결정 아님 | 지금 길 한 칸(1 또는 4), log π = 0 | 망을 부르지 않는다(지금 그대로 — 결과가 같다) |
| 웅크림 덮기 (`KeepMode == Shelter`) | HIDE 한 칸 | 지금 그대로 |
| 그 밖 | 판 2 그대로(허용 ∧ 가능 ∧ 결정) | `ComposeActionMask(W.Allowed, …)` :2179 그대로 |

- 칸 3 은 판 4 에서 늘 0 이다: 결정 줄은 1·4 만 켜고, '그 밖'은 실제 허용이 막는다.
- **얼기·잠 = 실제 허용(두뇌 ∧ 세계) 검사**(`rep_policy.py:187-195`, 계약 `freeze_sleep_must_be_blocked: "effective_allowed"`):
  - C++ 실제 허용은 `FWorldState::Allowed`(:1617-1620, `SetModelAllowed` :1779-1785). 판 4 두뇌를 걸 때 `Allowed[kFreeze] == 0 ∧ Allowed[kSleep] == 0` 을 본다.
  - 세계 칸 `FWorldConfig::WorldAllowed` 만 보지 않는다 — 통합 세계는 잠을 허용하고(`[1,1,1,0,1]`) 두뇌 목록이 막는다.
  - 검사 자리: 통합 `SyncBrain`(8-2), 평가기 `Init`(:676-677 뒤). 어긋나면 그 두뇌를 거부한다(지금 두뇌 유지).
- 파이썬 학습의 '덮기 스텝도 결정' 결함 고침(판 4 만 — `rep_peek` reads)은 C++ 이 처음부터 그렇게 한다(:2164 `bReads = false`). 이식은 길 결정만 더한다.
- 동점: `SelectAction`(:180-194)은 엄격한 > 라 같으면 낮은 번호, 곧 RUN(칸 1 < 4). route0 은 SHELTER 로짓이 RUN 보다 2 작아 늘 RUN 이다(16-6).

---

## 5. 두뇌 파일 로더

### 5-1. 계약 줄 (`EcoV3Brain.cpp:34-38`, `EcoV3Brain.h:103-114`)

- `kNumContracts` 2 → 3. 셋째 줄: `{kContractHashObs24Mask4, 24, 4, 6, kRouteContractExtraNames, TEXT("관측 24 · 마스크 판 4 (두뇌 길 — 21 칸 + in_panic·shelter_reach·shelter_edge)")}`.
  - `kRouteContractExtraNames[6]` = 장애물 세 이름 + 길 세 이름(`ContractObsName` :242 가 i ≥ 18 을 이 배열에서 읽는다). `FContract::NumExtra` 주석
    '(0 또는 3)'(`EcoV3Brain.h:108`)과 '받는 계약 수' 주석(:113)도 셋째 줄에 맞춘다.
- `static_assert(kObsDimRoute <= EcoPolicyV3::kMaxObsDim)` 를 :24 옆에 더한다.
- `FEcoV3Brain` 에 `MaskVersion`(내장 = `kMaskVersion` 2)을 더한다. 지금은 해시·관측 수만 들고 있어 판을 알 수 없다. `bRoute()` = `MaskVersion == 4`.
- `Describe` :413-427: 관측 24 면 `", 관측 24 도망길"`(21 은 지금처럼 `", 관측 21 장애물"`). 계약 거부 글 :525-526 에 셋째 해시를 넣는다.
- 머리 주석 `EcoV3Brain.h:17-25` '받는 계약'에 셋째 줄을 적는다.

### 5-2. 판 4 거부 조건 (`Parse` :488-731, 순서 그대로)

1. 해시가 `0xe302dee198197444` 인데 `obs_dim` ≠ 24 → `Dims`. 이름 24 개가 5-1 순서가 아니면 → `Names`.
2. `mask_version` ≠ 4 → `Mask` (:567 은 계약 줄의 판과 견주므로 줄만 맞으면 된다).
3. 문턱(:576-579)은 지금과 같다(판 4 파일도 `thresholds.alarm_mask_obs` 0.4 를 싣는다 — route0 파일에서 확인).
4. 허용(:589-617): 판 4 인데 모델 허용에 `freeze`·`sleep` 이 있으면 → `Allowed`. 파이썬은 학습 설정 목록(`rep_policy.py:143-147`)에서 이미 막아 이런 파일을
   만들지 못한다. 그래서 실제로는 걸리지 않는 방어 줄이다(12절 질문 10).
5. (선택) 파일의 `contract.flight_route`(`export_weights_v3.py:230-251`)를 읽어 C++ 상수와 견준다: `slots {run 1, shelter 4, reserved_masked [3]}`,
   `obs`, `decide {lock_steps 15, on [...], feasible ["shelter"], refeas_from ["run"]}`, `shelter {max_edge_u 20, cos_min 0, enter_margin_u 2, exit_margin_u 0,
   reach_norm_u 10, edge_norm_u 20}`, `freeze_sleep_must_be_blocked "effective_allowed"`. 해시가 이미 덮으므로 다르면 `Contract` 로 거부하고 까닭만 자세히 적는다
   (12절 질문 11).
6. 골든 자체 확인(:671-731)은 그대로다. 판 4 파일은 `route_edge`·`route`·`route_single` 사례(마스크 `[0,1,0,0,1]`·`[0,1,0,0,0]`)를 싣고(`export_weights_v3.py:795-807`),
   `RunPolicyV3` 가 그대로 돈다. route0 파일: 34 사례, 그 가운데 길 8 사례, `err_np32` 9.5e-7.

### 5-3. 옛 두뇌와 함께 받기

- 18·21 줄은 바이트까지 그대로다. 옛 두뇌 파일·`EcoBrains/` 의 세 파일은 그대로 받아야 한다(시험 10-3).
- route0 두뇌 파일 `herbivore_rl/results/v3/route/brains/v3_r1_g995_s3_obs24route0.json`(가중치 sha256 `078c56be3d4b…`)을 `AdaptiveEcosystem/EcoBrains/` 에 복사해
  시험이 이름으로 찾게 한다(`LoadObs21` 시험 :363 과 같은 꼴).
- 평가기 `Tools/EcoV3Eval/EcoV3Eval.cpp` `LoadBrain` :317-420 은 따로 짠 로더다. 같은 규칙을 넣는다: 해시 셋(:324-332), `mask_version` 2 또는 4(:333-337 —
  해시와 짝), 판 4 면 허용 3·4 가 0, `FBrain` 에 `MaskVersion`. `--brain-check` 줄(:1249)에 `mask_version` 을 더한다.

---

## 6. 세계 통계와 도망 기록

### 6-1. 길 통계 `FRouteStats` (★, `FWorldStats` :1496 끝) — 파이썬 `route_stats()` `world.py:6146-6161`

| 칸 (파이썬 키) | 셈 시점 | 파이썬 줄 |
|---|---|---|
| `steps{run,cover,shelter,open}` | H, 이번 스텝 실행한 길(스텝 첫머리 산 사슴) | 5995-5997 |
| `onsets`, `onset_shelter` (`onset_cover`·`onset_both` 늘 0) | H | 6075-6078 |
| `decisions`, `redecide_feas` | H | 6079-6080 |
| `invalid{…}` (SHELTER 칸만) | H | 6084-6085 |
| `picked{run,shelter}`, `switches`, `choice`, `bad_shelter` | **A (다음 스텝 첫머리)** | 6113-6119 |
| `fallback` 늘 0, `fixed` null, `quiet_end` 0, `brain` 참 | — | 6152-6160 |

- **셈 시점이 중요하다.** 파이썬은 고른 길을 다음 step 첫머리(`_route_apply`)에 센다. 판이 끝나는 마지막 스텝 H 의 결정은 `picked`·`choice` 에 들지 않는다.
  C++ 도 A 에서 세야 기록이 같다(2-7 (다)).
- 결정 셈(decide_frac): 파이썬 `_rep_decide`(7172-7176) = `(arbitrate decide ∧ ¬덮기) ∨ 길 결정`, 스텝 안(A 뒤)에 센다. C++ `Stats.Decisions`(:2757)에
  `bCommittedRouteReads` 를 더하면 같다(2-7 (다)). 판 2·3 세계는 파이썬이 덮기 스텝을 결정으로 세고 C++ 은 세지 않는 **기존 차이**가 그대로다(12절 질문 15).

### 6-2. 도망의 길별 기록 `FFlightRouteStats` (★) — 파이썬 `_fl_update`·`_flight_route_block`

| 파이썬 칸 | 뜻 | 파이썬 줄 | C++ 자리 |
|---|---|---|---|
| `_fl_rsteps` (사슴 × 길) | 열린 도망의 길별 반사 스텝 | 6222, 6366-6370 | ★ `FFlightTrack::RouteSteps[4]` |
| `by_route{run,cover,shelter,open,none}{n,steps,contact}[11 까닭]` | 닫힌 도망을 '반사 스텝이 가장 많은 길'(같으면 앞 번호, 없으면 none)에 | 6257-6264, 6474-6482 | `FlightClose` :688 에서 ★, 보고 때 열린 도망은 잘림 |
| `drop_obstacle{…}`·`drop_foliage{…}` | 원판(잎) 놓침 사건을 그 스텝 실행한 길에 | 6360-6365 | `FlightUpdate` 놓침 루프 :788-802 안(늑대마다 — 한 사슴을 늑대 둘이 놓치면 2) |
| `chased_steps{…}`·`hidden_steps{…}` | 쫓기는 FLEE 스텝, 그 가운데 쫓는 늑대 모두의 눈길이 가려진 스텝 | 6371-6381 | `FlightUpdate` :808 근처 (`Prev` 비트 늑대의 `bBlocked` — 사슴마다 한 번, 지난 표적이 이 사슴인 늑대 가운데 하나라도 안 가리면 가림 아님. 이번 스텝 사냥을 그만둔 늑대도 지난 표적이면 든다) |
| `refled`, `refled_steps` 38 | 살아 끝난 도망 뒤 38 스텝 안 새 도망 | 6321-6322, 6326-6327, 6394-6395 | ★ `FFlightTrack::LastEndT`(처음 −10⁹). `StepNow` = 이번 스텝 번호 = H 의 `W.T − 1`(D :3230 뒤라 파이썬 `self.t − 1`). 살아 끝난 도망을 닫을 때 `LastEndT = StepNow − 1`(끝 FLEE 스텝 = 지난 스텝, 6322 `self.t − 2`), 새 도망이면 `StepNow − LastEndT ≤ 38` 일 때 refled(경계 포함, 6327), 이번 스텝 죽은 사슴은 `LastEndT = −10⁹`(6395 — 부활 세계의 새 개체에 잇지 않는다) |
| `_fl_closed`·`_fl_last_*` | 오라클 전용 | 6233-6237, 6265-6268 | 옮기지 않는다 |

- 길 칸 `ri` = 반사 스텝이면 실행한 길, 아니면 'none'(6288-6290). C++ `FFlightDeerStep` 끝에 ★ `Route`(−1 = 없음)를 더하고 `FlightStepEnd` :2654-2660 이
  `D.KeepActive == kKeepPanic ? D.Route : −1` 로 채운다.
- **바꾸는 꼴**: `FlightUpdate(…, FFlightRouteStats* RS = nullptr, std::int64_t StepNow = 0)` — `nullptr` 이면 지금 줄 그대로(도망 골든·평가기 기록 바이트 그대로).
  `StepNow` 는 이번 스텝 번호(`Step` H 에서 `W.T − 1`)이고 refled 만 쓴다. 골든 도망 길 기록 장면은 이 값을 `kFsTickT − 1` 로 준다(10-1 의 6).
  `Step` H :3311 은 `bRoute` 일 때만 넘긴다.
- 보고: ★ `FlightRouteReportOf(RouteStats, FlightRouteStats, 열린 도망)` → 파이썬 `flight_stats()['route']` 와 같은 키(6483-6488 + `route_stats` 칸).
- **도망 기록과의 관계**: 길 기록은 `FFlightStats`(끝 까닭·쫓긴 시간·10-23 숨은 뒤 지켜보기 hide)를 하나도 바꾸지 않는 **덧붙임 칸**이다. 지켜보기(hide)는 다른 갈래가
  `FFlightTrack::Watch`·`FFlightStats` 에 넣는 중이고, 길 기록은 그 위에 쌓는다(11-3). 파이썬도 `hide` 와 `route` 는 따로다(6455-6465).

---

## 7. 평가기 (EcoV3Eval·ceval.py)

### 7-1. 길 세계 받기 — `ceval.py`

- `world_block` :332-336 의 거부에서 `route` 만 뺀다(`route_fixed`·`quiet_end` 거부는 그대로). `wb["wild_flight"]["route"] = bool(w._wf["route"])` 를 더한다.
- `_FREE_EXTRA` :104 에 `"wild_flight": ("route",)` — 바탕 `REF_CFG`(:101, 관측 21 거울)와 다른 칸으로 받게 한다.
- 두뇌·세계 짝 검사: 두뇌 파일 `mask_version` 4 ⇔ `w._wf["route"]` 참(파이썬 `check_mask_version` 과 같은 뜻). 어긋나면 일을 만들지 않는다.
- `compare --world-set features.wild_flight.route=true --brain <판 4 두뇌>` 로 판정 거울(`v3_wild3_route_mirror.yaml`)과 같은 세계를 만든다.

### 7-2. 길 세계 돌리기 — `EcoV3Eval.cpp`

- 세계 블록 읽기 :504-518 에 `K.bRoute = F.BoolOr("route", false)`(옛 일 파일은 키가 없다).
- `Init` :674-677: `SetModelAllowed` → `SetModelObsDim(Brain.ObsDim)` → ★ `SetModelRoute(Brain.MaskVersion == 4)`. 세계 `route` 와 두뇌 판이 어긋나면 그 일은 오류 줄.
  판 4 면 실제 허용 3·4 가 0 인지 본다(4절).
- 기록: `WriteFlight` :808-845 에 `route` 블록(길 켬 세계만 — 6-2 키). `at` 판정 길이 기록(:1100)도 같은 보고를 쓴다.
- trace `WriteState` :917-1010: `obs` :963-976 에 `RouteObs` 세 칸(관측 24 두뇌만), 사슴 칸 `route`·`route_k`·`route_age`·`route_feas`·`route_decide`·`route_req`.

### 7-3. compare 넓히기 — `ceval.py`

- `python_trace` :668-700: 길 켬 세계면 `route=w.flight_route`, `route_k`, `route_age`, `route_feas`, `route_decide`, `route_req`(길 결정 사슴의 정책 출력 `a`,
  아니면 −1)를 더한다. 관측은 `w._obs` 라 24 칸이 저절로 들어간다.
  - 같은 때의 값이다: 파이썬 스냅숏은 `step` 뒤·다음 `_route_apply` 앞이고, C++ 은 H 뒤·다음 A 앞이다. 결정 스텝의 `route` 는 양쪽 모두 RUN 이다(2-1).
- `trace_diff` :703-745: 길 칸이 다른 사슴 수를 이산 칸(`disc`)에 넣는다. `request` 비교는 지금처럼 덮기 사슴을 빼고(:718·:725), 대신 `route_req` 를 길 결정 사슴끼리
  견준다. 길 결정 사슴의 로짓 차 |ℓ₄ − ℓ₁| 도 적어 갈림 까닭을 가른다(9절 R13).
- `METRICS` :599-608 에 `route_decisions`, `route_picked_shelter`, `route_steps_shelter`, `route_switches`, `route_invalid_shelter` 를 더한다. `exact_worlds` :651 은
  `flight.route` 를 공통 칸으로 견준다(지금은 파이썬에만 있어 `python_only` 로 빠진다).
- `VERSION_TAG` 는 셈 길이 바뀌므로 올린다(`ceval-1` → `ceval-2`).

---

## 8. 게임 (통합 서브시스템)

### 8-1. 실시간 고리에서 판 4 두뇌가 들어오는 길

```
(R6 통과 뒤 — 16-11) 파이썬 live: 시작점을 계약 해시로 고름 → 판 4 학습 → 두뇌 파일(관측 24·판 4) → A5 확인
 → Saved/EcoAdapt/brains → EcoV3Brain 감시·Parse(5절) → 줄 → 결정 스텝 경계 SyncBrain(8-2) → 그 스텝 끝 H 부터 길
```
- 파이썬 쪽(live.py `resolve_start`·A5·템플릿을 `v3_wild3_route_mirror.yaml` 로)은 16-11 의 몫이고 이 이식의 범위 밖이다. 이식은 C++ 이 판 4 파일을 받고 돌리게만 한다.

### 8-2. `SyncBrain` (`EcoPolicyV3IntegratedSubsystem.cpp:3295-3400`)

1. **걸기 전 검사**(지역마다): 새 두뇌가 판 4 면 `WildFlight.bEnabled` 가 켜져 있어야 하고, `SetModelAllowed` 뒤 실제 허용 3·4 가 0 이어야 한다.
   하나라도 어긋나면 줄의 두뇌를 버리고 지금 두뇌를 둔다 + 거부 알림(`PostNotice(ENotice::Reject)` :3329 와 같은 꼴). 저장소에 '대기 두뇌 버리기' 함수가
   없으면 `FEcoV3BrainRegistry` 에 더한다(12절 질문 12).
2. :3346-3348 뒤에 `SetModelRoute(Ctx->Sim, Now->bRoute())`. 첫 시작(:3208-3211)도 같은 세 줄로.
3. **교체 순간 규칙**(설계 11절·16-11):
   - 길 없는 두뇌 → 판 4: 열린 도망은 `D.Route` 가 NONE 이라 그 스텝 H 에서 `cur < 0` 결정이 나고 새 두뇌가 곧바로 고른다. 경계 스텝 자체는 앞 H 의 반사 방향(RUN)이다.
     설계 글 'RUN 으로 두고(age 0)'와 다르다(12절 질문 1).
   - 판 4 → 길 없는 두뇌: A 의 `RouteApply` 를 건너뛰어 앞 두뇌의 대기 SHELTER 선택을 버리고, 열린 도망의 `KeepDir` 를 `D.RouteRunDir`(그 H 의 반사 방향)로 바꿔
     '곧바로 RUN'을 지킨다. 길 상태는 그 스텝 H 에서 지운다(2-7 (가) 마지막 else).
   - 판 4 → 판 4(되돌리기 포함): 상태 그대로. 경계 스텝은 앞 두뇌가 앞 H 에서 고른 길을 실행하고(지금 '경계 스텝은 앞 두뇌의 요청' 규칙과 같다), 그 스텝 H 부터 새 두뇌.

### 8-3. 화면·기록

- 사슴 글자·색 `DeerLabel` :544-590: 도주 덮기면 `D.Route` 로 가른다 — RUN '도주(트인 쪽)' 노랑 계열, SHELTER '도주(은신처)' 파랑 계열.
  지금 도주 주황(255,110,20)·웅크림 파랑(60,150,255)과 겹치지 않게 고른다(12절 질문 9). `KeepModeNameKo` :537 은 그대로.
- 지역 글 `FlightLine` :4132-4145 에 한 줄: `길 RUN a% · 은신처 b% · 결정 n · 은신처 고름 m · 무효 i`(최근 60 초 — `FRouteStats` 누적 차).
- 10 초 기록 '[EcoV3I] <지역> 두뇌 |'(:3876 근처)에 같은 칸. 두뇌 몫 `FEcoV3BrainTally`(`EcoPolicyV3IntegratedSubsystem.h:554`, 처리기 `EcoPolicyV3IntegratedProcessors.cpp:483-544`)는
  도주 덮기를 이미 `Reflex` 로 따로 센다 — 그 안을 RUN·SHELTER 스텝으로 가르는 두 칸을 더한다.
- 두뇌 바꿈 알림·촬영 감독 글은 `Describe` 를 쓰므로 '관측 24 도망길'이 저절로 붙는다.
- 스냅숏 `EcoV3Snapshot.cpp`: `brain` 블록(:461-476)에 `mask_version`, `world.wild_flight`(:263-265)에 `route`(기록 — 두뇌가 정한 값). `settings`(:378-379)에 새 칸을 넣으면
  `adapt.py IGNORE_SETTINGS`(:107-111)에도 넣어야 기준 스냅숏 견주기가 깨지지 않는다(adapt 는 FEATURE_MAPS 밖 world 칸은 읽지 않는다 — :295-297).
- 장애물 관측 대조 기록 `LogObsParity`(:3425)는 관측 24 면 길 세 칸도 적는다(선택).
- 클라이언트 복제 칸은 더하지 않는다. 실행 행동이 FLEE 그대로라 애니메이션·Social 인계가 바뀌지 않는다. 길 색은 서버 디버그 그리기만이다.
- 주의: `eco.IntegratedV3.SocialControl 1`(기본 0)이면 Social 제어 훅(`EcoPolicyV3IntegratedProcessors.cpp:41-57`)이 도주 사슴을 다른 은신처 자리로 끌 수 있다(12절 질문 8).

---

## 9. 비트 일치 위험 (파이썬 줄과 함께)

| # | 위험 | 파이썬 | C++ 에서 지킬 것 |
|---|---|---|---|
| R1 | 식 차례 | `world.py:2499-2509` | `vx`, `vy` → `dc = sqrt(vx*vx + vy*vy)` → `ed = dc − r` → `ds` → `ux = vx/ds` → `xx = p.x + ed*ux` → `dx = q.x − xx` → `sqrt(dx*dx + dy*dy)` → `mu = md − ed` → `cs = (vx*a0x + vy*a0y)/ds`. 곱셈 교환은 IEEE 에서 같다. 더하기 묶음은 바꾸지 않는다 |
| R2 | 벽 여유의 늘 Normalize | `2339-2346`, `steering.py:38-41` | 지운 성분이 없어도 `Normalize` 를 부르고, 다 지워지면 입력 그대로. 단위벡터를 다시 나누면 끝자리가 1 ulp 바뀔 수 있다 |
| R3 | argmin 동점 | `2513` (`np.where(cand, ed, inf).argmin`) | 첫 최소 = 낮은 번호. C++ 은 `Ed < Best` 엄격한 < |
| R4 | `np.where` 는 두 갈래를 다 셈 | `2517-2518`, `2520-2523` (`np.clip(keep_k, 0, C−1)`) | 버려지는 갈래(후보 없음·keep < 0)의 값은 쓰지 않는다. C++ 은 그 갈래를 셈하지 않아도 된다 — 0 을 넣는다 |
| R5 | float64 / float32 경계 | `2413-2423`(전부 float64), `6014`·`6072-6073`(float32 대입) | 기하는 double, 관측 세 칸만 `static_cast<float>` |
| R6 | 나눗셈을 역수 곱으로 바꾸지 않음 | `2504`, `2509`, `2517`, `2522`, `6072`(/10), `6073`(/20) | `Mu / 10.0`, `E / 20.0`, `Vx / Ds` 그대로 |
| R7 | 무한대 | `2508`(`min(initial=inf)`), `2496`·`2521`(keep −∞) | S 가 비면 md = +∞ → mu = +∞ → 관측 1. keep 없으면 −∞ → `keep_ok` 거짓 |
| R8 | 문턱 비교 방향 | `2510-2511`(ed > 0, ed ≤ 20, cs ≥ 0, mu ≥ 2), `2525`(≥ 0), `6034`(age ≥ 15), rep_policy `276`(obs > 0) | 그대로. −0.0 ≥ 0 은 양쪽 모두 참 |
| R9 | 늑대 합 차례 (a₀ 재료) | `5867-5869` (`(ex*pinv*wt).sum(1)`) | 기존 반사 방향과 같은 값이다. numpy 는 늑대 8 마리 이상에서 8 칸 나눠 더하기(pairwise)라 C++ 차례 합과 끝자리가 갈릴 수 있다 — 지금 무대는 4 마리(기존 위험, 12절 질문 7). C++ 은 늑대 64 마리 상한(:2325) |
| R10 | 사슴 사이 의존 없음 | `5981-6095` 벡터 | 길 단계는 사슴마다 독립이다(통계 정수 합만 공유) → 사슴 루프 안에서 해도 같다 |
| R11 | 정수 칸 크기 | int8·int64 | C++ int32. 값 범위 안이라 무관 |
| R12 | 난수 | `5937`·`2395` "난수 없음" | 길은 세계 난수를 뽑지 않는다. 거울 세계의 스텝 안 뽑기는 늑대 배회 선회(위협 슬롯마다 하나)뿐이라 사슴이 SHELTER 를 골라도 수열이 같다(평가기 PCG64 이어 받기 그대로) |
| R13 | 망 순전파 근접 동점 | `rep_policy.py:468-473`(torch float32) | C++ float 누적과 1e-6 쯤 다르다(`EcoPolicyV3Inference.h:129-130`). 길 결정의 ℓ₄ − ℓ₁ 이 그만큼 작으면 argmax 가 갈린다. route0(차 2)·늘 SHELTER 시험 두뇌(차 2)는 안전, R6 두뇌는 판 대조에서 갈림 까닭으로 따로 적는다 |
| R14 | 셈 시점 | `6097-6126` (다음 step 첫머리) | 고른 길·바꿈·choice 는 A 에서 센다(6-1) |
| R15 | 결정의 적용 시점 | `4105-4109` | H 에서 바로 `Route`·`KeepDir` 를 바꾸면 궤적은 같아도 스텝 끝 `route` 칸·셈이 갈린다 → A 에서 적용 |
| R16 | 컴파일러 부동소수 | — | 평가기는 `/fp:precise`(`build.ps1` 5·25 행). 기존 골든이 UE 빌드에서도 `==` 로 통과하므로 지금 플래그에서 묶어 곱하기가 없다고 보지만, 새 식 `p + ed*ux` 를 골든에 넣어 UE·g++·평가기 셋에서 확인한다. 골든은 묶어 곱하기를 잡는다(10-23: g++ 참조를 `-mfma -ffp-contract=fast` 로 돌리면 μ·e 427 칸이 갈린다) |
| R17 | sqrt | `np.sqrt` / `std::sqrt` | 둘 다 IEEE 바른 반올림 — 같다 |

---

## 10. 시험 계획

### 10-1. 장면 골든 (UE 자동화 + g++ 하네스)

- 내보내기 `herbivore_rl/export_golden_v3_route.py`(만들었다 — 손으로 고치지 않는 생성 파일). 지금은 Source 밖
  `herbivore_rl/results/v3/route/port/RouteGoldenVectorsV3.h` + 같은 내용 `RouteGoldenVectorsV3.json` 에 쓴다((나) 갈래와 겹치지 않게). 이식 11-1 단계 2 에서
  `--out` 으로 `AI/Policy/RouteGoldenVectorsV3.h` 에 쓰고 검사 본문 `Tests/RouteGoldenCheckV3.h`, UE `Tests/EcoRouteV3Test.cpp` 를 더한다
  (꼴은 `export_golden_v3_foliage.py`·`FoliageGoldenCheckV3.h`).
  - 지금 있는 시험: g++ 스칼라 참조 `herbivore_rl/tests/cpp/route_ref_main.cpp`(헤더 머리 주석의 식을 사슴 하나로 옮긴 참조 — 엔진 코드가 아니다),
    pytest `herbivore_rl/tests/test_route_port_v3.py`(다시 만든 헤더·JSON 이 바이트까지 같음, 헤더 = JSON, 계획 꼬리표를 모두 덮음, g++ 참조 통과,
    판 단위 자료 신선도). 이식 단계에서 참조 하네스 자리를 엔진 함수(`Detail::RouteShelterGeometry`·`RouteStep`·`RouteApply`·`WriteRouteObs`)를 부르는
    `herbivore_rl/tests/cpp/route_v3_main.cpp` 로 바꾼다.
- 세계: 거울 `configs/v3_wild3_route_mirror.yaml`, 다시 난 개체만 R6 학습 세계 `configs/v3_r6_train.yaml`(부활). 탐색 시드 32080~32099 만 —
  32096 길 셈 루프, 32097 다시 난 개체, 32098 난수 기하·관측, 32099 손 장면·도망 길 기록 장면, 32080 기준 루프.
- 묶음 (만든 수 — 헤더 끝 줄 '덮는 계획 꼬리표'가 장면마다 줄 수를 적는다):
  1. **SHELTER 기하** 90 사례(손 34 + 거울 은신처 넷의 난수 56, 벽 가까이 1/5): 입력 p·a₀·q·S·원·Size·mg·keep → k*·μ*·e*·`shelter_dir`·`keep_mu`·
     `keep_ok`·`keep_dir`. 문턱 e = 20·μ = 2·μ_keep = 0 의 경계와 ± 1 ulp, cos = 0·−0.0, e 동점(낮은 번호), |v| = 0·|v| < EPS, 벽 여유(x·y·둘 다),
     S 빔(μ = +∞), 후보 밖(뒤쪽·e 42)인데 유지. 다시 단위화(R2)·나눗셈(R6)·묶어 곱하기(R16)에 갈리는 사례가 들어 있다(FMA 를 켜면 g++ 참조가 실패한다).
  2. **길 단계·적용**: 손 장면 15(줄 32·적용 15 — 시작 두 칸·한 칸, μ = 2 문턱, 무효·무효 뒤 다른 은신처·무효 뒤 한 칸에서 칸 4, 유지 문턱 μ = 0, RUN 잠금
     안·뒤 0 → 2·2 → 0·같음, SHELTER 유지·원 안, `cur < 0` 두 칸·한 칸, 지움) + 길 셈 루프(거울 숲 N, 사슴 32, 900 스텝 — 줄 891·적용 102·통계 18; 결정·
     지움·가능 바뀜 줄은 모두, 비결정 RUN·SHELTER 줄은 무늬로 솎음). 줄 = 사슴 하나의 H 입력(p·a₀·반사 최종 방향·늑대 자리·S 비트·전 상태)과 출력.
  3. **관측 세 칸** 37 사례(`WriteRouteObs` float 비트 — μ = 2·10·+∞·문턱 위 ulp, e 아주 작음·20·20 밑 ulp + 난수) + 줄 923 의 세계 관측.
  4. **마스크 판 4** 51 줄(손 9 + 길 셈 루프 갈래마다 6): 도주 결정 두 칸·한 칸, 비결정 RUN·SHELTER, 웅크림, 그 밖 판 2 결정·비결정·기상.
  5. **기준 루프 지문**(foliage 골든 꼴): 거울 세계(사슴 48, 부활 없음) 시드 32080 의 시작 상태·늑대 선회 난수(PCG64 날 64 비트), 450 스텝 스텝마다 지문
     (자리·heading·에너지·덮기·행동·관측 24 float·다음 요청·늑대·`Route`·`RouteK`·`RouteAge`·`RouteFeas`·`bRouteDecide`·`RouteRequest`·도주 사슴의
     `KeepDir`) + 90 스텝마다 기록 72 칸. 두뇌 둘:
     - route0 = 내장 R1b(`PolicyWeightsV3.h`)를 24 열로 늘리고(새 여섯 열 0) W2[4] = W2[1], B2[4] = B2[1] − 2. 내보내기가 route0 zip 이 이 꼴인지
       (생성 헤더와 비트 같음) 확인하고, 가중치 sha256 `078c56be…` 를 적는다 — C++ 이 만든 망의 sha256 이 같아야 한다.
     - 늘 SHELTER(시험 전용, `v3_obs24route_shelter2`) = 같은 꼴, B2[4] = B2[1] **+ 2**.
     - 내보내기는 두 두뇌의 모든 결정에서 근접 동점(< 1e-4)이 없고(최소 로짓 차 0.0177), 두뇌 파일 순전파와 torch argmax 가 같음을 확인했다.
  6. **도망 길 기록**: 짜 맞춘 장면 하나(사슴 8·틱 10, 재료 = `export_golden_v3_flight.py` 장면 비트 + 실행한 길 + 스텝 번호 → 틱마다 길 덩어리 182 칸·
     사슴 칸 6) + 길 셈 루프·기준 루프 끝 보고. 장면은 세계 루프에 없는 경계를 넣었다(기준 루프에는 38·39 스텝 째 새 도망이 하나도 없고 none 길 놓침도 없다):
     살아 끝난 뒤 38 스텝 째 새 도망 = refled, 39 = 아님, 죽음이 끝 스텝을 지움, 반사 스텝 동점 → RUN, 반사 없는 두뇌 FLEE → none, 한 사슴을 늑대 둘이
     원판 놓침 → 2, 쫓는 늑대 하나만 트임 → 가림 아님, 열린 도망 truncated(길별), 반사 중 잡힘. g++ 참조는 끝 까닭이 필요 없는 길 칸(길별 반사 스텝·끝
     스텝·놓침·쫓김·가림·refled)을 다시 내고, 끝 까닭별 by_route 는 UE `Route.FlightRecord` 가 실제 `FlightUpdate` 로 본다.
  - 그 밖: 다시 난 개체 9 사건(R6 학습 세계 — RUN 6·SHELTER 3, 죽은 사슴 terminal_obs 0).
- 골든 상수 이름은 골든 이름공간(`EcoWorldV3::GoldenRoute`) 안 이름이라 1-3 의 엔진 상수와 다르다. UE 시험은 짝마다 `static_assert` 로 값이 같은지 본다:

  | 골든 `GoldenRoute::` | 엔진 (1-3·이식 뒤) |
  |---|---|
  | `kContractHashObs24Mask4` | `EcoPolicyV3::kContractHashObs24Mask4` |
  | `kObsDim` 24 · `kRouteObsFirst` 21 | `kObsDimRoute` · `kObsInPanic` (22·23 = `kObsShelterReach`·`kObsShelterEdge`) |
  | `kSlotRun`·`kSlotShelter`·`kSlotReserved` | `kRouteSlotRun`·`kRouteSlotShelter`·`kRouteSlotReserved` |
  | `kRouteNone`·`kRouteRun`·`kRouteShelter` | 같은 이름 |
  | `kFeasShelter` · `kLockSteps` | `kRouteFeasShelter` · `kRouteLockSteps` |
  | `kModeNone`·`kModeAlert`·`kModePanic`·`kModeShelter` | `kKeepNone`·`kKeepAlert`·`kKeepPanic`·`kKeepShelter` (0·1·2·3) |
  | `kMaxEdgeU`·`kCosMin`·`kEnterU`·`kExitU` | `kRouteShelterMaxEdgeU`·`kRouteShelterCosMin`·`kRouteShelterEnterU`·`kRouteShelterExitU` |
  | `kReachNormU`·`kEdgeNormU` | `kRouteShelterReachU`·`kRouteShelterEdgeNormU` |
  | `kFsRefleeSteps` | `kFlightRefleeSteps` |
  | `kEps` | `R3::kEps` |
  | `kWorldSize`·`kWallMargin`·`kSafeR` | 상수가 아니라 세계 설정 칸(`WorldSize`·`WildFlight.WallMargin`·`WildFlight.SafeR`) |

- 받아들일 조건: 모든 실수 칸 `==`(double·float 비트), 정수 칸 같음, 지문 sha256 같음. 실패 0.

### 10-2. 판 단위 궤적 대조 (`herbivore_rl/results/v3/route/port/` — 만들었다)

```
herbivore_rl/results/v3/route/port/
  make_traces.py                         이 자료를 만든다 (--check = 지금 코드로 다시 만들어 바이트 같은지만 본다)
  MANIFEST.json                          만든 커밋·명령·세계·두뇌·판마다 파일 sha256·요약, 일 지문 12, 신선도 입력 sha256 (world.py·rep_policy.py·
                                         features.py·rollout.py·export_weights_v3.py·거울 설정 둘·adapt.py·스냅숏·route0 두뇌 파일)
  brains/v3_r1_g995_s3_obs24route0.json  route0 (= results/v3/route/brains, 가중치 078c56be…)
  brains/v3_obs24route_shelter2.json     늘 SHELTER 시험 두뇌 (+ 모델 zip — ceval 이 zip 을 찾는다, *.zip 무시 규칙으로 git 밖이고 같은 바이트로 다시 만든다).
                                         학습·판정에 쓰지 않는다
  brains/v3_r6_<후보>.json               (가) 갈래의 R6 후보 — 학습·판정이 끝난 뒤에만 넣는다 (아직 없다)
  traj/<두뇌>__<N|G>__<지역>__<시드>.jsonl.gz   스텝 s = 0..1800 마다 칸 아홉(clock·deer·fate·beh·obs·req·kin·wolf·route)의 sha256 앞 8 자리.
                                         전체 궤적이 아니라 지문이다(전체는 수백 MB). C++ trace(7-2)를 ceval 이 읽은 dict 에 같은 함수
                                         `make_traces.digest_state` 를 걸면 처음 갈린 스텝·칸을 바로 안다(그 스텝만 python_trace 로 다시 뽑아 본다)
  stats/<두뇌>__<N|G>__<지역>__<시드>.json      세계 기록(adapt._world_one = r4_eval._one 칸 + flight.route·flight.hide), 판 끝 repertoire(decide_frac),
                                         두뇌 확인(torch 와 두뇌 파일 순전파 argmax 차·근접 동점), 칸마다 지문 사슬, 길 결정·죽음 사건,
                                         route0 은 같은 일의 길 끈 obs21zero 기록과 같은가
```
- 세계: 스냅숏 `eco_v3_snapshot_s20004_t475_e1.json`, 시드 **34900·34901** × 지역 셋(Barren·Forest·Highland) × N·G, 1800 스텝 = 판 12 × 두뇌 2 = 24 —
  10-22 파리티 검사와 같은 판(판정 시드가 아니다). 숲 시야 끔(게임 기본). 처음 적은 34900~34904 를 자료 크기·시간 때문에 둘로 줄였다
  (평가기 compare 는 시드를 더 돌려도 된다 — 그 판은 파이썬 기록과만 견준다).
- 돌리기(평가기가 길 세계를 받은 뒤 — 7절): `ceval.py compare --snapshot results/v3/live/pilot/eco_v3_snapshot_s20004_t475_e1.json
  --world-set features.wild_flight.route=true --brain results/v3/route/port/brains/<두뇌>.json --seeds 34900-34901 --horizon 1800 --worlds N G --trace 1800`.
- 받아들일 조건 (세계마다 판 6 = 지역 3 × 시드 2):
  1. route0: N 6/6·G 6/6 기록 정확히 같음, 궤적 지문 첫 차이 없음, 길 결정은 모두 RUN. 그리고 이 판 = 길 끈 세계 + obs21zero 판(16-6 '배포 동일')과
     기록이 같다(파이썬 쪽은 12 판 모두 확인 — stats 의 `route_off.same`).
  2. 늘 SHELTER: N 6/6·G 6/6, 지문 첫 차이 없음, `flight.route` 같음(파이썬 쪽: SHELTER 가 열린 결정에서 늘 SHELTER, picked shelter = choice > 0).
  3. R6 후보: 같거나, 첫 갈림이 근접 동점 길 결정(|ℓ₄ − ℓ₁| < 1e-4)에서 났음을 trace 가 보일 것. 그 밖 까닭의 갈림은 0.
- 파이썬 쪽 확인(지금): 두 두뇌 24 판 모두 torch 와 두뇌 파일 순전파 argmax 차 0·근접 동점 0, `bad_shelter` 0.

### 10-3. 자동화 시험 이름

| 시험 | 내용 |
|---|---|
| `AdaptiveEcosystem.Policy.V3.Route.Geometry` | 10-1 의 1 |
| `AdaptiveEcosystem.Policy.V3.Route.StepGolden` | 10-1 의 2·3 |
| `AdaptiveEcosystem.Policy.V3.Route.MaskRows` | 10-1 의 4, 칸 3 늘 0 |
| `AdaptiveEcosystem.Policy.V3.Route.World` | 10-1 의 5 (route0·늘 SHELTER 지문) |
| `AdaptiveEcosystem.Policy.V3.Route.FlightRecord` | 10-1 의 6 — 도망 길 기록 장면을 `FlightUpdate`(+ `FFlightRouteStats`, `StepNow = kFsTickT − 1`)로 다시 돌려 틱마다 `kFsBlock`·`kFsTrack` 같음, 루프 끝 보고 |
| `AdaptiveEcosystem.Policy.V3.Route.Off` | `bRoute` 끔 = 지금: 기준 루프 해시·기존 골든 지문 그대로, 판 2 두뇌는 `Route` 칸이 늘 NONE |
| `AdaptiveEcosystem.Policy.V3.Route.ZeroIdentity` | C++ 안에서 route0(길 켬) 궤적 = obs21zero(길 끔) 궤적, 1800 스텝 × 지역 셋 |
| `AdaptiveEcosystem.Policy.V3.Brain.LoadObs24Route` | route0 파일 받음(해시·이름 24·판 4·sha·골든 34·길 8 사례), `Describe` 글 |
| `AdaptiveEcosystem.Policy.V3.Brain.RejectRoute` | 판 4 인데 obs 21·mask 2·이름 순서·허용에 얼기/잠·`flight_route` 다름 → 거부 까닭. 옛 18·21 은 그대로 받음 |
| `AdaptiveEcosystem.Policy.V3.Integrated.BrainObs24Route0` | 통합 세계에서 route0 = obs21zero (`BrainObs21Zero` 꼴) |
| `AdaptiveEcosystem.Policy.V3.Integrated.BrainRouteSwap` | 18 → 24 → 21 → builtin(되돌리기 포함) 열린 도망 중 교체: 8-2 규칙, 관측 칸 수, 길 상태 지움, 셈 |
| `AdaptiveEcosystem.Policy.V3.Integrated.RouteRefugeLifecycle` | SHELTER 유지 중 은신처 지움(반경 0) → 무효 결정, 늦게 붙은 은신처 후보 |
| `AdaptiveEcosystem.Policy.V3.Integrated.RouteRequiresWildFlight` | WildFlight 끈 지역에 판 4 두뇌 → 거부 |

- 기존 시험 전부(지금 141 개 근처)는 그대로 통과해야 한다. 기존 골든 헤더 여럿은 다시 만들어도 바이트가 같아야 한다(`test_*_golden_v3.py`).
- 빌드: 직접 UBT `AdaptiveEcosystemEditor Win64 Development` + unity 를 끈 전체 빌드(`-DisableAdaptiveUnity`). 다른 UBT·에디터가 돌면 시작하지 않는다(AGENTS 3절).
  복사 맵 PIE: route0 → 늘 SHELTER 시험 두뇌로 `eco.V3Brain.Load` 교체, 사슴 색·지역 줄·은신처 도착 웅크림을 눈으로 확인.

---

## 11. 작업 순서·예상 크기·겹침

### 11-1. 순서

| 단계 | 일 | 손으로 쓰는 줄 (어림) |
|---|---|---|
| 0 | (나) 숨음·잡힘 갈래가 커밋될 때까지 기다린 뒤 그 위에서 시작 | — |
| 1 | 상수·계약: `EcoPolicyV3Inference.h` 해시, `EcoObservationV3.h` 칸·이름·`WriteRouteObs` | 40 |
| 2 | `RouteShelterGeometry`·`WallKeep` + 골든을 `--out` 으로 `AI/Policy/` 에 + 검사 머리(1·3 묶음) | C++ 100 (파이썬 내보내기는 만들었다) |
| 3 | 상태 칸·`RouteStep`·`DecideHerb`·`RouteApply`·`SetModelRoute`·`SetModelObsDim` + 검사 머리(2·4·5 묶음) | C++ 230 |
| 4 | `FRouteStats`·`FFlightRouteStats`·`FlightUpdate` 선택 인자·보고 + 검사 머리(6 묶음 — 도망 길 기록 장면) | C++ 170 |
| 5 | 로더(`EcoV3Brain.h/.cpp`) + `EcoBrains/` route0 복사 + 시험 | C++ 110 + 시험 120 |
| 6 | 평가기 `EcoV3Eval.cpp` + `ceval.py` + port 대조(10-2) | C++ 130, 파이썬 90 |
| 7 | 통합 서브시스템·처리기·스냅숏 + 통합 시험 + UBT·unity 끈 빌드·PIE | C++ 170 + 시험 250 |
| 8 | 계약 문서 `POLICY_CONTRACT_V3.md` 2-5(관측 24)·3절(판 4), 설계 16-14 단계 6 상태 | 문서 150 |

- 합: 실행 C++ 약 950 줄, C++ 시험(검사 머리·UE 시험·g++ 하네스) 약 1,150 줄, 파이썬 약 700 줄, 문서 약 150 줄. 생성 헤더 `RouteGoldenVectorsV3.h` 4,000~8,000 줄.
  - 10-23: 골든 내보내기·판 대조 자료와 그 시험(약 3,400 줄 — `export_golden_v3_route.py`·`port/make_traces.py`·`test_route_port_v3.py`·g++ 참조
    `route_ref_main.cpp`, 위 파이썬 700 줄 어림보다 많다)과 생성 헤더(약 7,600 줄)는 만들었다. 남은 파이썬은 `ceval.py` 약 90 줄이다.
- 기간 어림: 사람 손 2~3 일 (16-14 의 '약 1일'은 C++ 실행 줄만 본 어림이다).

### 11-2. 지금 두 갈래와 겹치는 곳

| 파일 | (가) R6 학습 | (나) 숨음·잡힘 C++ | 이 이식 | 합칠 때 주의 |
|---|---|---|---|---|
| `env_v2/*.py`, `configs/v3_r6*` | 학습이 읽음 | — | **고치지 않는다** | R6 이 끝날 때까지 파이썬 세계 바이트를 바꾸지 않는다. C++ 이 파이썬을 따라간다 |
| `EcoWorldV3.h` 머리 주석 :76-79, 도망 기록 :519-901 | — | `FFlightTrack::Watch`, `FFlightStats` hide 칸, `FlightUpdate`·`FlightReportOf` | `FFlightTrack` 끝 두 칸, `FFlightDeerStep::Route`, `FlightUpdate` 선택 인자, 새 구조체 | (나) 커밋 뒤 rebase. 새 칸은 구조체 **끝**에(위치 지정 초기화가 깨지지 않게). 길 줄은 `RS != nullptr` 안 |
| `EcoWorldV3.h` 나머지(상수·상태·UpdateWildFlight·DecideHerb·Step A·H) | — | 거의 없음 | 대부분 | 충돌 작음 |
| `FlightGoldenVectorsV3.h`, `export_golden_v3_flight.py`, `Tests/FlightGoldenCheckV3.h` | — | 다시 만듦 | **고치지 않는다** | 이식 뒤 다시 만들어도 바이트가 같아야 한다(길 끈 세계) |
| `Tools/EcoV3Eval/EcoV3Eval.cpp` | — | `WriteFlight` hide 블록 | LoadBrain·Init·trace·WriteFlight route 블록 | 같은 함수 — (나) 뒤에. 일 파일 키는 둘 다 선택(옛 일 받음) |
| `results/v3/live/ceval.py` | — | `HIDE_WATCH` 참, 판정 실행기 | world_block·trace·METRICS·VERSION_TAG | 같은 파일 — (나) 뒤에. `VERSION_TAG` 는 한 번만 올린다 |
| `results/v3/live/live.py` | 결과를 씀 | evaluator 기본값 | 이번에는 고치지 않음(16-11 은 R6 통과 뒤) | — |
| `EcoV3FlightTally.h` | — | 화면 숨음 비율 | 고치지 않음(길 줄은 서브시스템에) | — |

---

## 12. 열린 질문 (고치지 않았다 — 정할 것)

1. **판 4 두뇌로 바꾸는 순간의 열린 도망.** 설계 11절은 'RUN 으로 두고(age 0), 다음 결정 시점부터'라고 적었다. 파이썬 규칙대로면 길 상태가 없는 도주(`cur < 0`,
   `world.py:6037`)는 바로 그 H 에서 결정이다. 'RUN·age 0'으로 두면 결정 때 가능 비트(`route_feas`)를 무엇으로 둘지 정해야 하고, SHELTER 가 이미 가능하면
   잠금이 끝날 때까지 고를 기회가 없다. **권고: 파이썬 `cur < 0` 규칙(교체 스텝 H 에서 새 두뇌가 곧바로 고름).**
2. **판 4 → 길 없는 두뇌의 경계 스텝.** 앞 H 가 정한 SHELTER 유지 방향이 그대로면 한 스텝 은신처 쪽으로 간다. '곧바로 RUN'을 글자 그대로 지키려면 H 의 반사 방향을
   따로 남겨야 한다(`D.RouteRunDir`, 8-2). 남길지, 한 스텝 늦음을 받을지 정한다.
3. **부활 세계의 다시 난 사슴(기존 차이).** 파이썬 `_wf_update` 는 다시 난 사슴도 새 자리로 덮기·길 관측을 셈한다(`test_route2_v3.test_obs_respawn_world`).
   C++ 은 그 스텝에 덮기가 없다(:2333-2344 — `DeathCause` 가 남아 있다). 판정·게임(부활 없음)과 무관하지만, C++ 기준 루프(부활)를 파이썬 학습 세계와 견주면 갈린다.
   골든은 부활 없는 세계로만 만든다.
4. **지워진 은신처(반경 0)·늦게 붙은 은신처.** 파이썬 세계에는 없다(adapt 는 그런 스냅숏을 거부한다 — `adapt.py:289-292`). 2-4 의 C++ 전용 두 줄(후보에서 뺌,
   유지 중이면 무효)로 충분한지, 늦게 붙은 은신처를 진행 중인 판정과 견줄 일이 있는지 정한다.
5. **셈 시점.** 파이썬은 고른 길·바꿈·choice 를 '다음 스텝 첫머리'에 세서 판 끝 마지막 결정을 세지 않는다. 뜻이 '실행된 결정'이면 맞고, '내린 결정'이면 하나씩
   모자란다. C++ 은 파이썬과 같게 맞추지만(6-1), 보고 칸 뜻을 문서에 적어야 한다.
6. **관측 22·23 의 뜻.** 유지 중인 은신처(`route_k`)가 아니라 '지금 새로 고를 수 있는 k\*' 의 값이고, 유지 중 가능 비트가 0 이면 0 이다(`test_route2_v3.py:537-539`).
   망·가치망이 지금 가는 은신처를 모른다(설계 16-4 관측 25 대안과 이어진다).
7. **늑대 8 마리 이상(기존 위험).** a₀ 재료 합(`world.py:5869`)이 numpy 8 칸 나눠 더하기라 C++ 차례 합과 끝자리가 갈릴 수 있다. 지금 무대는 4 마리라 드러나지
   않았다. 늑대 수를 늘릴 일이 있으면 파이썬 `_seq_sum`(`world.py:2617`) 꼴로 바꿀지 정한다. C++ 은 64 마리 상한(:2325)도 있다.
8. **Social 제어와 SHELTER 길.** `eco.IntegratedV3.SocialControl 1` 이면 Social 훅이 같은 사슴을 다른 은신처 자리로 보낼 수 있다(두 이동 의도). 기본 0 이라
   파리티와 무관하다. 켤 때 어느 쪽이 앞서는지 팀이 정한다.
9. **디버그 색.** 설계는 SHELTER 파랑이지만 지금 웅크림이 파랑(60,150,255)이다. 다른 색(예: 하늘색)을 쓸지 정한다.
10. **로더의 허용 검사 위치.** 파일 읽을 때 '모델 허용에 얼기·잠 없음'으로 거부하면 설계 16-2 의 '실제 허용(두뇌 ∧ 세계)'보다 엄격하다. 파이썬이 그런 파일을 만들
    수 없어 실제 차이는 없다. 둘 다 둘지(파일 + 걸 때 실제 허용), 걸 때만 볼지 정한다.
11. **두뇌 파일의 `contract.flight_route` 대조.** 해시가 이미 덮으므로 필요 없지만, 읽어서 어긋난 칸을 거부 글에 적으면 진단이 쉽다. 할지 정한다.
12. **WildFlight 를 끈 지역의 판 4 두뇌.** 파이썬은 `wild_flight` 없이 관측 24 세계를 만들 수 없다. C++ 은 거부(권고)인지, 길 없이 관측 21~23 을 0 으로 두고 돌릴지
    정한다. 거부면 저장소에 '대기 두뇌 버리기'가 필요하다.
13. **R6 두뇌의 근접 동점.** 내보내기 골든은 근접 동점(< 1e-4)을 빼지만, 판 전체에서는 길 결정의 ℓ₄ − ℓ₁ 이 작을 수 있다. 판 대조에서 '근접 동점 갈림 허용'
    (10-2 조건 3)을 받아들일지, 학습 쪽에서 동점을 피할 장치가 필요한지 정한다.
14. **옮기지 않는 것 확인.** 설계 10절 C++ 목록의 `RouteFixed`·`QuietEndSteps`·CVar `eco.IntegratedV3.FlightQuietEnd`·COVER 기하·디버그 초록은 이번 이식에서 뺀다.
    그래서 평가기는 `route_fixed`·`quiet_end` 세계를 계속 거부한다.
15. **판 2·3 세계의 결정 셈(기존 차이).** 파이썬 판 2·3 은 덮기 스텝을 결정으로 세고(`rep_peek` 결함 — 판 4 에서만 고침) C++ 은 세지 않는다. 판 4 는 이식 뒤
    같아진다. 판 2 세계의 decide_frac 을 C++ 과 견줄 일이 있으면 정의를 문서에 적는다.
16. **RUN 길에서 가능 2 → 0 바뀜의 결정.** 잠금 뒤 SHELTER 가 불가로 바뀌면 열린 칸이 RUN 하나뿐인 결정이 생긴다(age·feas 만 새로 둔다). 고를 것이 없는데
    결정 수(f_dec·decide_frac)에 들어간다. 의도한 것인지 확인한다(파이썬 고침 대상은 아니다).
17. **교체 경계 스텝의 도망 길 기록(10-23 검토에서 더함).** `FlightStepEnd` 는 `UpdateWildFlight` 앞에서 `D.Route` 를 읽는다. 길 없는 두뇌 → 판 4 로
    바꾼 스텝의 열린 반사 도주는 `D.Route` 가 NONE 이라 그 한 스텝이 도망 기록의 'none' 칸(반사 없는 두뇌 FLEE 자리)에 든다. 파이썬에는 없는 경우다.
    그대로 둘지(경계 한 스텝 — 판정·학습과 무관), 반사 스텝이면 RUN 으로 셀지 정한다.

---

## 부록: 파이썬 줄 묶음 (HEAD `2aac3e5`)

- `herbivore_rl/env_v2/world.py`: 모듈 설명 339-363(길)·330-338(지켜보기), `obs_names` 818·832-833, 상수 1413-1437, 키 검사 1548-1586, `wf_wall_keep` 2339-2346,
  `flight_route_geometry` 2391-2484, `_route_shelter` 2487-2526, 길 켬 표시 2694-2696·2728-2729, `_obs_from` 4028-4029, `step` 4105-4118·4318-4341, `rep_peek` 4512-4545,
  `_route_override` 4547-4553, 제어기 4592-4597, `_respawn` 5619-5627, `_wild_reset` 5718-5729, `_wf_update` 5816-5930, `_route_reset` 5936-5971, `_route_clear` 5973-5979,
  `_route_step` 5981-6095, `_route_apply` 6097-6126, `route_redecide` 6128-6144(옮기지 않음), `route_stats` 6146-6161, `_fl_reset` 6187-6237, `_fl_close` 6239-6275,
  `_fl_update` 6277-6424, `flight_stats` 6426-6466, `_flight_route_block` 6468-6489, `_rep_accumulate` 7156-7176.
- `herbivore_rl/env_v2/rep_policy.py`: 상수 83-87, `rep_params` 143-147, `effective_allowed` 162, `mask_version_of` 176-184, `check_route_allowed` 187-195,
  `check_mask_version` 198-211, `action_mask` 232-258, `_route_rows` 261-281, `rep_argmax` 468-473. `env_v2/rollout.py:747-749`. `env_v2/features.py:300-306`·`333-334`.
- `herbivore_rl/export_weights_v3.py`: 골든 개수 108-110, `contract_dict` 207-227, `flight_route_contract` 230-251, `contract_hash` 254-257, `brain_golden` 766-833,
  `brain_dict` 836-891, `brain_golden_config_for` 900-910.
- `herbivore_rl/results/v3/route/route_extend.py`(route0 — 칸 4 = 칸 1 − 2, `SHELTER_BIAS` −2), `make_route_configs.py`, `tests/test_route2_v3.py`(장면 `_Scene` 459-497,
  결정 때 500-595, 관측 405-451, 계약 해시 686-710).
