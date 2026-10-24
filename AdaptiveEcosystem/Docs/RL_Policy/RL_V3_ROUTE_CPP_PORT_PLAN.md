# 두 길 두뇌 C++ 이식 계획서 (RUN·SHELTER, 관측 24·마스크 판 4)

- 상태: 처음에는 계획만 적었다(코드·빌드·UBT·자동화·학습 없음). 10-24 에 아래 차례로 이식하고 검토했다.
  - 10-23 검토: 파이썬 줄과 다시 대조해 의사 코드의 남은 값 버그 둘(2-7 (나) 길 읽음 지우기 자리, (다) `bCommittedRouteReads`), `A0` 범위, 도주 아님 지울 칸,
    refled 스텝 번호를 고쳤다. 10-1·10-2 를 실제로 만든 골든·판 대조 자료(`results/v3/route/port/`)에 맞췄다(시드 2 개, 스텝 지문, 도망 길 기록 장면).
  - 10-23 R7: R6 기각 뒤 다음 후보는 마스크 판 5(= 판 4 + 반사 밖 두뇌 FLEE 막음)다. 바뀐 마스크 줄·계약·이식 영향은 13절(설계 17절). 이식은 R7 통과 뒤다.
  - 10-24 이식 1/2 (엔진 무관 부분 — R7e 판정 통과 뒤): 엔진 무관 헤더(EcoWorldV3.h·EcoObservationV3.h·EcoPolicyV3Inference.h)·평가기(Tools/EcoV3Eval)·
    `ceval.py` 에 판 4·5 를 옮기고 골든을 Source 로 옮겼다. 한 것·정한 것(12절 질문)·대조 결과는 14절. UE 로더·통합 서브시스템·UE 자동화·UBT 는 2/2 몫이다.
  - 10-24 이식 2/2 (게임 쪽): UE 두뇌 로더(판 4·5)·통합 서브시스템(SyncBrain 걸기 전 검사·길 켜고 끄기)·화면·스냅숏·UE 자동화 14 개를 더했다. 직접 UBT 두 가지
    빌드(기본·`-DisableAdaptiveUnity`) 성공, 자동화 `AdaptiveEcosystem` 214 개 실패 0. 게임 기본 두뇌·기본 설정은 그대로다(R1b-F, 두 길은 판 4·5 두뇌를 걸 때만).
    한 것·정한 것·검증은 15절. 계약 문서 `POLICY_CONTRACT_V3.md` 갱신(11-1 의 8)과 눈으로 보는 PIE 는 남았다.
  - 10-24 적대적 검토 (1/2·2/2 뒤): 파이썬 줄과 C++ 줄을 다시 견줘 결함 셋(게임 refled 시계, `ceval.py` 근접 동점 진단, 계약 대조의 `decide.on`)을 고쳤다.
    세계 동역학·두뇌 출력·파이썬 대조 값은 바뀌지 않았다. 고친 것·다시 확인한 것·남은 차이·검증은 16절.
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
  - (10-24 적대적 검토 — 16-1 의 1: `Step` H 는 `W.T − 1` 대신 도망 기록 시계 `FFlightStats::Clock` 을 넘긴다. 차이가 같아 파이썬·골든 값은 그대로이고,
    통합 모드에서 팀 시계에 다시 맞출 때 `W.T` 가 뛰어도 refled 가 틀리지 않는다.)
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

- (10-24 이식 1/2 에서 헤더를 Source `AI/Policy/` 로 옮기고 검사 본문 `Tests/RouteGoldenCheckV3.h`·g++ `route_v3_main.cpp` 를 더했다 — 14-1. 아래는 그 전 글이다.)
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

> 10-24 이식 1/2 에서 정한 것은 14-2 에 적었다(권고가 있으면 권고대로, 없으면 파이썬 동작과 같게 — 비트 일치 우선). 아래 글은 그때 물은 그대로 둔다.

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

## 13. 10-23 R7 — 마스크 판 5 (설계 `RL_V3_FLIGHT_ROUTE_DESIGN.md` 17절)

- 상태: 파이썬만 바꿨다(학습·판정 전). **C++ 은 고치지 않는다 — R7 이 판정을 통과한 뒤 이 절대로 옮긴다.** R6 는 기각이라 판 4 두뇌를 게임에 걸 일이 없다.
  이식이 시작되면 위 1~12절의 판 4 줄은 판 5 에도 그대로 쓰이고, 아래만 더한다.
- 판 5 = 판 4 + **반사 밖 두뇌 FLEE 막음**: 덮기(도주·웅크림) 밖 결정 행에서 칸 1(FLEE)을 막는다. 도주는 반사만 시작하고 두뇌는 '어디로'(RUN·SHELTER)만 고른다.
  도주 길 결정·도주 비결정·웅크림 행과 관측 24·길 기하·결정 때는 판 4 그대로다.

### 13-1. 바뀐 마스크 줄 (4절 표의 '그 밖')

| 상황 | 판 4 | 판 5 | C++ |
|---|---|---|---|
| 그 밖 ∧ 결정(`bReads`) | 판 2(허용 ∧ 가능) | 판 2 − 칸 1 | `DecideHerb` 의 `ComposeActionMask` 뒤(`EcoWorldV3.h` :2271 근처, `fc0662f` 기준) ★ `if (D.Prep.bReads && W.bFleeGate) D.Mask[kFlee] = 0;` |
| 그 밖 ∧ 결정 아님 | 지금 행동 한 칸 | 같다(반사가 끝난 뒤 잠금 중인 FLEE 포함) | 그대로 |
| 도주·웅크림 | 4절 그대로 | 같다 | 덮기 분기는 지금도 망을 부르지 않는다 — 그대로 |

- 파이썬: `env_v2/rep_policy.py` `_gate_free_rows`(덮기 밖 결정 행 = `reads ∧ override == WF_NONE`), `action_mask` 가 `rep_peek` 의 `brain_flee_outside_reflex: False`
  를 보고 판 5 로 셈한다. 세계 동역학·관측·보상·난수는 그대로라 같은 행동이면 판 4 세계와 궤적이 같다(`tests/test_r7_mask5.py`).
- 빈 줄 없음: GRAZE 는 늘 허용 ∧ 가능이다. C++ 은 판 5 두뇌를 걸 때 실제 허용 `W.Allowed[kGraze] == 1` 을 본다(지금도 늘 1).
- 부활 없는 세계의 죽은 슬롯: 파이썬 마스크는 죽은 슬롯의 덮기 밖 결정 행에서도 칸 1 을 끈다(시체는 움직이지 않고 아무것도 바꾸지 않는다). C++ 은 죽은 사슴을
  처리기 목록에서 빼므로 견줄 것이 없다. 판 대조(10-2)의 사슴 줄은 산 사슴만 본다.

### 13-2. 계약·로더 (5절에 더함)

- 계약 dict: 판 5 는 판 4 dict(`flight_route` 같은 값) + 키 `"brain_flee_outside_reflex": false`, `mask.version` 5.
  **`kContractHashObs24Mask5 = 0xad7bad5e1acaf071ULL`** (`export_weights_v3.contract_hash(관측 24, 5)`). 옛 넷(관측 18·19·21·24)의 해시는 그대로다.
- `kNumContracts` 에 넷째 줄 `{kContractHashObs24Mask5, 24, 5, 6, kRouteContractExtraNames, …}`. `FEcoV3Brain::MaskVersion` 5 를 받고 `bRoute()` = 판 4·5,
  ★ `bFleeGate()` = 판 5. 판 5 거부 조건은 5-2 와 같고 `mask_version` 만 5, 파일의 `contract.brain_flee_outside_reflex` 가 `false` 가 아니면 `Contract`.
- 판 6(R7 대조 '길 끔', 관측 21 — 해시 `0xe4b66ac546da1d77`)은 파이썬 학습 대조 전용이다. 두뇌 파일을 만들지 않고(`export_weights_v3.brain_golden_config_for`
  가 멈춘다) C++ 계약 줄에 넣지 않는다.
- 두뇌 파일 골든: 판 5 파일의 다중 칸 결정(`rollout`)은 판 5 마스크라 칸 1 이 늘 0 이다. 골든 세계 `configs/v3_wild3_route5_mirror.yaml`.
  시작 두뇌 파일 `herbivore_rl/results/v3/r7/brains/v3_r1_g995_s3_obs24route0m5.json` — 가중치 바이트는 route0 파일과 같고 계약만 판 5 다.

### 13-3. 세계·게임 (1-2·8절에 더함)

- ★ `FWorldState::bFleeGate`(기본 `false`) — **두뇌가 정한다**(1-2 의 `bRoute` 와 같은 꼴). `SetModelRoute` 옆 ★ `SetModelFleeGate`: 판 5 두뇌일 때만 켠다.
  파이썬 학습·판정 세계는 세계 키(`wild_flight.brain_flee_outside_reflex: false`)로 켜지만, 게임 세계에는 이 설정이 없다. 평가기는 일의
  `world.wild_flight.brain_flee_outside_reflex` 로 넣는다(`ceval.py` 받기 — 지금은 거부).
- **WildFlight 를 끈 지역에는 판 5 두뇌를 걸지 않는다.** 반사가 없으면 도망을 시작할 길이 아예 없어진다. 파이썬은 `wild_flight` 를 끈 세계에서 이 키를 읽지 않는다
  (`route` 키와 같다 — 멈추지 않고 무시한다). 그 세계는 관측에 `in_panic` 이 없는 판 2 라 판 5 두뇌가 연결 때 거부된다(12절 질문 12 와 같은 자리).
- 결정 셈(`Stats.Decisions`)·덮기 스텝 처리는 판 4 와 같다. 통계 ★ `FleeGateFree`·`FleeGateFlee`(파이썬 `flee_gate_stats` — 덮기 밖 결정 수, 그 가운데 두뇌
  FLEE 수, 마스크를 지키면 0)는 선택이다.
- 시험: 장면 골든에 '덮기 밖 결정 + 위협을 앎(FLEE 가능)' 줄을 더해 판 5 마스크 `[1,0,·,0,0]`·argmax 가 FLEE 가 아님을 본다. 판 대조는 10-2 꼴로 판 5 거울에서 한다.
- 옮길 파이썬 줄(`fc0662f` 다음의 R7 구현 커밋): `rep_policy.py` `mask_version_of`·`world_mask_version`·`check_mask_version`·`_gate_over_rows`·`_gate_free_rows`,
  `world.py` `_wild_flight_params`(키 검사)·`rep_peek`·`_route_override`·`step` 첫머리·`flee_gate_stats`·`_rep_accumulate`, `export_weights_v3.py` `contract_dict`·
  `brain_golden_config_for`, `features.py` OPTIONAL_KEYS.

---

## 14. 10-24 이식 1/2 — 엔진 무관 부분 (한 것·정한 것·대조)

- 범위: R7e 판정 통과(`ae789ce`·`1e26df6`) 뒤 판 4·5 를 엔진 무관 헤더·평가기·`ceval.py` 에 옮겼다. 파이썬 세계 코드(`env_v2`)·게임 기본 두뇌(R1b-F)·기본 설정은
  고치지 않았다. 두 길은 두뇌가 켠다(SetModelRoute·SetModelFleeGate — 기본 끔). UE 로더(`EcoV3Brain.h/.cpp`)·통합 서브시스템·화면·스냅숏·UE 자동화 `Route.*`·
  UBT·unity 끈 빌드·PIE 는 2/2 몫이다(빌드는 그때 함께 한다 — 이번에는 g++ 하네스·평가기 빌드까지).

### 14-1. 한 것

| 자리 | 한 것 |
|---|---|
| `EcoObservationV3.h` | 관측 21~23 칸 번호·이름(`kObsInPanic`·`kObsShelterReach`·`kObsShelterEdge`·`kRouteObsNames`), `kObsDimRoute` 24, `kMaxObsDim` 21 → 24, `WriteRouteObs` (3절) |
| `EcoPolicyV3Inference.h` | 계약 해시 `kContractHashObs24Mask4`·`kContractHashObs24Mask5`, 판 번호 `kMaskVersionRoute` 4·`kMaskVersionRouteGate` 5, 길 칸 `kRouteSlot*`, `ApplyRouteMaskRows`(판 4·5 덮기 줄 + 판 5 반사 밖 FLEE 막음 — 4절·13-1). 마스크 코드는 `ComposeActionMask` 가 있는 이 파일에 두었다(`EcoRepertoire.h` 는 고치지 않았다) |
| `EcoWorldV3.h` 상수·상태 | 1-3 의 길 상수, `FWildFlightConfig::bRoute`, `FWorldState::bFleeGate`, `FHerbDecision` 길 칸 15 개·`FHerbPerception::RouteObs`(2-8), `FRouteStats`·`FFlightRouteStats`·`FFlightRouteReport`(6절), `FFlightTrack::RouteSteps`·`LastEndT`, `FFlightDeerStep::Route`, `FFlightOpen` 길별 잘림 |
| `EcoWorldV3.h` 함수 | `InitWorld`(bRoute ∧ bEnabled), `SetModelObsDim`(24 받음), `SetModelRoute`·`SetModelFleeGate`, `Detail::WallKeep`(반사 줄에서 뽑음 — 연산 그대로), `Detail::RouteShelterGeometry`·`ClearRoute`·`RouteStep`·`RouteApply`(사슴 하나의 순수 함수 — 골든이 직접 부른다), `Detail::NetInputOf`(망 입력 18·21·24), `DecideHerb`(첫머리 길 요청 지움·길 결정 줄 망·판 5 막음), `UpdateWildFlight`(실행한 길 셈·죽음 분기 지움·a₀·길 단계), `FlightStepEnd`(실행한 길·도망 길 기록 RS·StepNow), `FlightClose`·`FlightUpdate`(선택 인자 RS·StepNow — nullptr 면 지금 줄 그대로), `FlightRouteReportOf`, `Step` A(`RouteApply`·결정 수에 길 결정) |
| 골든 | `RouteGoldenVectorsV3.h` 를 Source `AI/Policy/` 로 옮겼다(내보내기 기본 자리, 같은 내용 JSON 은 `port/` 에 남김). 13-3 의 판 5 마스크 손 줄 6 개(종류 `gate`)를 더했다(마스크 51 → 57 줄, 꼬리표 `mask_gate_free`·`mask_gate_hold`·`mask_gate_over`) |
| 검사 | `AI/Policy/Tests/RouteGoldenCheckV3.h`(엔진 함수 검사 본문 — 2/2 의 UE `Route.*` 가 같은 본문을 부른다), g++ `herbivore_rl/tests/cpp/route_v3_main.cpp`, 스칼라 참조 `route_ref_main.cpp` 는 판 5 줄·Source 헤더로, 새 시험 셋(`test_route_port_v3.py` 엔진 하네스, `test_ceval_v3.py` 길 세계 짝·150 스텝 비트 동일), `test_r7_mask5.py` 의 'ceval 은 판 5 를 거부' 시험을 '판 5 받음·판 6 거부'로 바꿈 |
| 평가기 `Tools/EcoV3Eval` | 계약 넷(18·21 판 2, 24 판 4·5), 관측 이름 차례·`contract.flight_route`·`brain_flee_outside_reflex` 대조, 판 4·5 모델 허용의 얼기·잠 거부, 일의 `world.wild_flight.route`·`brain_flee_outside_reflex` 와 두뇌 판 짝(어긋나면 그 일 오류)·WildFlight 끈 세계 거부·실제 허용 확인, `flight.route` 기록(파이썬 `_flight_route_block` 과 같은 칸), trace 관측 24·길 칸·`route_gap`·`gap`, 선택 칸 `trace_digest`(궤적 지문 — `make_traces.digest_state` 와 같은 바이트), 근접 동점 진단(`min_gap`·`near_ties`·`min_route_gap`), `--brain-check` 의 `mask_version` |
| `ceval.py` | `world_block` 이 route·판 5 를 받는다(판 6 은 거부, `route_fixed`·`quiet_end` 거부 그대로), `native_job` 두뇌 판 짝 검사, `python_trace`·`trace_diff` 길 칸·갈린 결정 로짓 차, `METRICS` 길 다섯, `VERSION_TAG` ceval-2 |
| 그 밖 | `export_golden_v3_foliage.py` `CFG_SKIP`(world 블록 새 칸 — 숲 골든 바이트 그대로), `port/native_check.py`(판 단위 C++ 대조 — 아래 14-3) |

### 14-2. 정한 것 (12절 질문 — 권고가 있으면 권고대로, 없으면 파이썬 동작과 같게)

| 질문 | 정한 것 |
|---|---|
| 1 판 4 로 바꾸는 순간 | 권고대로 `cur < 0` 결정 — 길 상태 없는 열린 도주는 그 H 에서 새 두뇌가 곧바로 고른다(골든 `cur_none` 줄) |
| 2 판 4 → 길 없는 두뇌 경계 | 8-2 본문대로 남긴다: `RouteStep` 이 `D.RouteRunDir`(그 H 의 반사 방향)를 두고, A 의 `RouteApply` 가 `bRoute` 거짓이면 고른 칸을 버리고 열린 도주의 `KeepDir` 를 그 값으로 둔다(곧바로 RUN). 남은 길 상태는 그 H 가 지운다. 파이썬에 없는 경우이고 끈 세계는 `Route` 가 늘 NONE 이라 그대로다 |
| 3 부활 세계의 다시 난 사슴 | 기존 차이 그대로 둔다 — C++ 을 파이썬처럼 바꾸면 길 끈 부활 세계(평면 맵 기준 루프)도 바뀐다(끈 세계 비트 동일이 앞선다). C++ 죽음 분기가 길 상태·관측 21~23 을 지운다(골든 다시 난 줄의 지움·terminal_obs 0 은 `ClearRoute` 로 본다) |
| 4 지워진·늦게 붙은 은신처 | 2-4 의 C++ 전용 두 줄로 충분(반경 0 은 후보에서 빼고, 유지 은신처가 반경 0·목록 밖이면 유지 거짓 → 무효 결정). 늦게 붙은 은신처는 다음 H 부터 후보다 — 파이썬 세계에 없어 판정과 견줄 일은 없다 |
| 5 셈 시점 | 파이썬과 같게 — `picked`·`switches`·`choice`·`bad_shelter` 는 다음 A 의 적용 때 센다(뜻 = 적용된 결정, 판 끝 마지막 H 결정은 들지 않는다 — `FRouteStats` 주석) |
| 6 관측 22·23 의 뜻 | 파이썬과 같게 — 유지 중에도 새로 고를 수 있는 k\* 의 값 |
| 7 늑대 8 마리 이상 | 그대로(지금 무대 4 마리, C++ 차례 합·64 상한) |
| 8 Social 제어와 SHELTER 길 · 9 디버그 색 | 통합 서브시스템 몫이라 2/2 에서 정한다(이번에 손대지 않았다) |
| 10 로더의 허용 검사 위치 | 둘 다 — 파일을 읽을 때 모델 허용, 걸 때 실제 허용(평가기 `LoadBrain`·`Init`). 파이썬도 학습 설정 목록과 마스크(`check_route_allowed` — 실제 허용) 둘에서 본다 |
| 11 `contract.flight_route` 대조 | 한다 — 평가기가 칸·관측·결정(10-24 검토 뒤 `on` 까지 — 16-1 의 3)·SHELTER 문턱·`freeze_sleep_must_be_blocked`·판 5 의 `brain_flee_outside_reflex` 를 C++ 상수와 견주고 다르면 그 칸 이름으로 거부(UE 로더는 2/2) |
| 12 WildFlight 끈 지역의 판 4·5 두뇌 | 권고대로 거부 — 평가기는 그 일을 오류로 내고, `SetModelRoute`·`SetModelFleeGate` 도 `bEnabled` 와 묶는다. 통합의 '대기 두뇌 버리기'는 2/2 |
| 13 근접 동점 | 10-2 조건 3 그대로(근접 동점 갈림은 허용, 그 밖 갈림 0). R7e 판 30 에서 갈림 없음(14-3) |
| 14 옮기지 않는 것 | 확인 — `route_fixed`·`quiet_end`·COVER·OPEN 은 옮기지 않았고 평가기·`ceval.py` 가 거부한다 |
| 15 판 2·3 의 결정 셈 | 기존 차이 그대로. 판 4·5 는 같다(`Stats.Decisions` = Arbiter 결정(덮기 아님) + 길 결정 = 파이썬 `_rep_accumulate`) |
| 16 RUN 길에서 가능 2 → 0 | 파이썬과 같게 — 한 칸 결정도 결정이다 |
| 17 교체 경계 스텝의 도망 길 기록 | 파이썬 식(`re_ = 반사 ? 실행한 길 : NONE`)과 같게 'none' 칸 — 교체 경계 한 스텝뿐이다 |
| 13절 판 5 | `FWorldState::bFleeGate`·`SetModelFleeGate`·`ApplyRouteMaskRows`(덮기 밖 결정 줄 칸 1 막음)·평가기 판 5 받기. 선택 통계 `FleeGateFree`·`FleeGateFlee` 는 넣지 않았다 |
| 그 밖 | 도주 비결정·웅크림 덮기 줄의 `D.Mask` 는 지금처럼 0 이다(망을 부르지 않는다 — 결과가 같다). 길 결정 줄만 `Mask {1, 4}`·로짓을 남긴다. 덮기 밖 결정의 관측 24 두뇌 망 입력은 길 세 칸(도주 밖이라 0)을 붙인다(`NetInputOf`) |

### 14-3. 대조 결과 (10-24)

| 대조 | 결과 |
|---|---|
| g++ 엔진 하네스 `route_v3_main.cpp` (`-O2 -ffp-contract=off -Wall -Wextra -Werror -Wshadow`) | PASS — 정의, 기하 90, 길 셈 줄 923, 적용 117, 손 장면 통계 32, 마스크 57(판 5 6 줄), 다시 난 9, 관측 37, 도망 길 기록 장면 10 틱(길 덩어리 182 칸·사슴 칸), 기준 루프 두뇌 둘 × 지문 451·기록 5·끝 길 덩어리. 묶어 곱하기(`-mfma -ffp-contract=fast`)면 기하·줄·루프 지문이 어긋난다(골든이 잡는다) |
| g++ 스칼라 참조 `route_ref_main.cpp` (Source 헤더) | PASS |
| MSVC VS2022 `cl /W4 /WX` + 그림자 변수(C4456~4459) 오류 + `/fp:precise` | 같은 검사 본문 모두 통과 (UBT 는 2/2) |
| 기존 g++ 하네스 18 (도망·숲 시야·레퍼토리·파리티·돌아가기·장애물·날씨·무리·위협) | 통과 — 끈 세계 비트 그대로 |
| 판 단위 `port/native_check.py` (route0·늘 SHELTER × N·G × 지역 셋 × 시드 34900·34901 × 1800) | 24/24 — 궤적 지문 1801 스텝 × 칸 아홉 첫 차이 없음, 세계 기록 정확히 같음(`flight.route`·`hide`·`episode` 포함) |
| `ceval.py compare` R7e 두뇌(판 5 세계 — `route=true`·`brain_flee_outside_reflex=false`, 시드 34900~34904 × 지역 셋, 1800) | N 15/15·G 15/15 기록 정확히 같음(파이썬에만 있는 칸 없음), 궤적 셋 첫 비트 차이 없음·갈림 없음. C++ 근접 동점 진단: 망 결정 최소 로짓 차 1.14e-4, 길 결정 3.2e-4, 1e-4 밑 0 |
| `ceval.py compare` 끈 세계(obs21zero, 같은 시드) | N 15/15·G 15/15, 궤적 셋 첫 비트 차이 없음 — 이식 전과 같다 |
| pytest | `test_route_port_v3.py` 13 + 느린 `make_traces.py --check` 1, `test_ceval_v3.py` 를 넣은 골든·평가기 관련 묶음 186, `test_r7_mask5.py`·`test_foliage_v3.py`·`test_live_v3.py` 65 — 모두 통과 |

- 설정 대조의 `world_allowed`(스냅숏 `[1,1,1,0,1]`·네이티브 `[1,1,1,0,0]`)는 이식 전부터 있는 표기 차이다(파이썬 = 실제 허용 목록, 스냅숏 = 세계 칸 — 두뇌 허용과 곱하면 같다, `test_ceval_v3.py`).

## 15. 10-24 이식 2/2 — 게임 쪽 (한 것·정한 것·검증)

- 범위: 1/2 의 엔진 무관 함수(`SetModelRoute`·`SetModelFleeGate`·길 단계)를 게임이 쓰게 했다. 엔진 무관 헤더·평가기·`ceval.py`·파이썬 세계 코드(`env_v2`)는 고치지 않았다.
  게임 기본 두뇌(내장 R1b-F)·기본 설정(콘솔 변수)은 그대로다 — 두 길은 판 4·5 두뇌 파일을 `eco.V3Brain.Load`·`-EcoV3Brain=` 로 걸 때만 켜진다(콘솔 변수가 없다).

### 15-1. 한 것

| 자리 | 한 것 |
|---|---|
| `EcoV3Brain.h/.cpp` (로더) | 계약 줄 넷(셋째 `0xe302dee198197444` 관측 24 판 4, 넷째 `0xad7bad5e1acaf071` 관측 24 판 5 — 여섯 이름 `kRouteContractExtraNames`), `FEcoV3Brain::MaskVersion`·`bRoute()`(판 4·5)·`bFleeGate()`(판 5), `RouteContractDiff`(파일 `contract.flight_route` 의 slots·obs·decide(lock_steps·`on`(10-24 검토에서 더함 — 16-1 의 3)·feasible·`refeas_from`)·shelter 문턱·`freeze_sleep_must_be_blocked "effective_allowed"` 와 판 5 의 `brain_flee_outside_reflex: false`, 판 4 에는 그 칸이 없어야 함 — 평가기와 같은 칸 이름, 다르면 '계약 해시' 로 거부), 판 4·5 모델 허용에 얼기·잠 → '허용 칸' 거부, 거부 글에 해시 넷, `Describe` '관측 24 도망길(·반사 밖 도망 막음)', `eco.V3Brain.Info` 에 마스크 판, 저장소 `DiscardPending`(대기 두뇌 버리기 — 대기 되돌림이면 꺼낸 칸을 쌓개에 돌려놓음). 18·21 줄은 그대로 |
| `EcoBrains/` | route0 `v3_r1_g995_s3_obs24route0.json`(= `results/v3/route/brains`, 가중치 `078c56be…`)·R7e `v3_r7_g995_s1_20m.json`(= `results/v3/r7e/brains`, `40d8710d…`)을 바이트 그대로 복사 — 시험이 이름으로 찾는다. 걸 때만 쓴다(시작 두뇌가 아니다) |
| 통합 서브시스템 | `RouteBrainBlocker`(세계 하나 — 판 4·5 두뇌만: 도주 반사 끔, 실제 허용(두뇌 ∧ 세계 칸)의 얼기·잠, 먹기 없음)·`BrainBlocker`(모든 지역)·`ApplyBrainToWorld`(허용·관측 칸 수·`SetModelRoute(bRoute())`·`SetModelFleeGate(bFleeGate())` — `AddContext`·`SyncBrain` 이 같은 줄). `SyncBrain`: 대기 두뇌를 걸기 전에 검사해 어긋나면 버리고 경고 '[EcoV3I] 두뇌 거부 |'·거부 알림, 저장소 지금 두뇌를 이 월드에 걸 수 없으면(앞 Play·다른 월드가 건 판 5 두뇌를 도주 반사 끈 월드가 받음) 저장소는 그대로 두고 이 월드만 앞 두뇌(처음이면 내장). '두뇌 시작/바꿈' 줄의 지역 허용 뒤 '(두 길)'·'(두 길·반사 밖 도망 막음)' |
| 화면 | 사슴 글자(`DeerLabel` 의 선택 인자 Route — 도주 덮기면 '도주(트인 쪽)' 연노랑 255,240,120·'도주(은신처)' 하늘색 110,230,255, 길 결정 스텝은 두뇌가 고른 칸 `ShownRoute`), 지역 맨 위 줄 '두뇌 <이름> 두 길(·반사 밖 도망 막음)', 넷째 줄 '길 <지역> \| 최근 60초: …'(`FEcoV3RouteTally` — 450 결정 스텝 창, 화면 키 734000 + 지역), 상태 줄 '두 길(마스크 판 n) …'(모든 지역 60 초 합). 두뇌 몫 `FEcoV3BrainTally::ReflexRun·ReflexShelter`(반사 스텝 가운데 실행한 길 — 세계 길 통계의 스텝 차) |
| 기록 | 10 초 기록 '[EcoV3I] <지역> 길 \|'(길 통계가 있는 세계만 — 지금 켰거나 앞 두뇌가 센 누적): 구간·누적 `FEcoV3RouteSum::Text`·도주 시작·바꿈. 아홉째 줄 '<지역> 두뇌 \|' 꼴은 그대로(`compare_swap.py` 정규식) |
| 스냅숏 (판 1 그대로, 더하기만) | `brain.mask_version`·`route`·`flee_gate`, 지역 `world.wild_flight.route`·`brain_flee_outside_reflex`(두뇌가 정한 값 — `ceval.world_block` 과 같은 이름, `adapt.py` 는 FEATURE_MAPS 밖이라 읽지 않는다), 지역 `flight.route`(길 통계가 있을 때만 — 파이썬 `flight_stats()['route']` 와 같은 칸 + 60 초 창). `settings` 는 그대로(새 콘솔 변수 없음 — `adapt.py IGNORE_SETTINGS` 고칠 것 없음) |
| 자동화 (새 14) | `Policy.V3.Route.*` 7 (`Tests/EcoRouteV3Test.cpp` — Geometry·StepGolden·MaskRows·World·FlightRecord 은 1/2 의 검사 본문 `RouteGoldenCheckV3.h` 를 부른다, Off·ZeroIdentity), `Policy.V3.Brain.LoadObs24Route`·`RejectRoute`, `Policy.V3.Integrated.BrainObs24Route0`·`BrainRouteSwap`·`RouteRequiresWildFlight`·`RouteRefugeLifecycle`·`RouteDisplay` |

### 15-2. 정한 것 (12절 질문 8·9·12 와 새로 생긴 것)

| 질문 | 정한 것 |
|---|---|
| 8 Social 제어와 SHELTER 길 | 지금 순서 그대로 둔다 — `eco.IntegratedV3.SocialControl 1`(기본 0)이면 Social 훅(B 의 제어 입력)이 A 의 `RouteApply` 뒤에 와서 슬롯 쪽이 이긴다(덮기 도주와 같은 순서). 훅의 '위험 쪽으로 되돌아가지 않음' 검사는 `KeepDir`(= 고른 길 방향)를 Away 로 쓴다. 기본 0 이라 파리티·판정과 무관하고, 둘을 함께 켤 때의 우선은 팀 결정으로 남긴다 |
| 9 디버그 색 | 계획서 예시대로 SHELTER 는 하늘색(110,230,255 — 웅크림 파랑 60,150,255 과 다름), RUN 은 노랑 계열 가운데 두뇌 도망 노랑(255,215,0)과 다른 연노랑(255,240,120). 길이 없으면(길 끈 두뇌) 지금 주황 그대로 — 끈 세계 글자·색은 바뀌지 않는다(`Integrated.RouteDisplay`) |
| 12 WildFlight 끈 지역 (통합) | 권고대로 거부 — 걸기 전 검사가 한 지역이라도 걸리면 대기 두뇌를 버린다(지금 두뇌 유지). 저장소 함수 `DiscardPending` 을 더했다 |
| 10 걸 때 실제 허용 | `RouteBrainBlocker` 가 두뇌 ∧ 세계 칸(`WorldAllowed`)으로 본다(`SetModelAllowed` 와 같은 식, 세계를 바꾸지 않고 미리). 파일 검사(모델 허용)와 둘 다다 |
| 새: 저장소 지금 두뇌를 걸 수 없는 월드 | 대기 검사를 지나지 않고 들어오는 길(앞 Play 에 건 두뇌가 저장소에 남음·다른 PIE 월드가 걸음)은 저장소를 고치지 않고 이 월드만 앞 두뇌(첫 시작이면 내장)를 쓴다 — 저장소는 프로세스에 하나라 다른 월드의 두뇌를 빼앗지 않는다 |
| 새: 10 초 기록 칸 자리 | 계획 8-3 은 '<지역> 두뇌 \|' 줄에 같은 칸을 붙이자고 했지만, 그 줄 끝을 읽는 정규식(`compare_swap.py`)을 깨지 않게 바로 뒤 따로 '<지역> 길 \|' 줄에 적었다 |
| 새: 화면 길 | 스텝 끝(H 뒤) 길 결정 스텝은 `D.Route` 가 RUN 이고 고른 칸은 다음 A 가 적용한다. 화면은 두뇌가 고른 칸(칸 4 ∧ 가능이면 SHELTER — `ShownRoute`, `RouteApply` 와 같은 판정)을 보인다. 세계는 바꾸지 않는다 |
| 새: 60 초 창 | 도망 기록 창(`EcoV3FlightTally.h`)과 같은 450 결정 스텝. 길을 끈 동안에도 매 스텝 넣어 창이 시각과 맞는다(그동안 길 칸은 늘지 않는다) |

### 15-3. 검증 (10-24)

| 검증 | 결과 |
|---|---|
| 직접 UBT `AdaptiveEcosystemEditor Win64 Development -WaitMutex -NoHotReloadFromIDE` | 성공 (경고 0). 처음 `-DisableAdaptiveUnity` 빌드에서 새 시험의 지역 변수 `W2` 가 v1 전역 `PolicyWeights.h` 를 가려 C4459 — 이름을 바꾼 뒤 성공 |
| 직접 UBT `-DisableAdaptiveUnity` | 성공 (마지막 C++ 고침 뒤 두 빌드 모두 다시 성공) |
| 자동화 `Automation RunTests AdaptiveEcosystem` (-NullRHI) | 214 개 실패 0 (213 Success + 1 기존 예상 경고 `Predation.SaveLoadGlobalEma` 저장 파일). 새 14 개 모두 통과 |
| `Route.Geometry`·`StepGolden`·`MaskRows`·`World`·`FlightRecord` | UE(MSVC, 적응 unity) 빌드에서도 골든과 비트 단위로 같다 — 기하 90·줄 923·적용 117·통계 32·다시 난 9·관측 37·마스크 57·기준 루프 두뇌 둘 × 452·도망 길 기록 10 틱 어긋남 0 (g++ 하네스와 같은 결과) |
| `Route.ZeroIdentity` | 통합 지역 셋(숲·고지·메마른 땅, 사슴 32·늑대 4) × 1800 스텝 route0(길 켬) = obs21zero(길 끔) 첫 갈림 없음, 기록 같음. 길 결정 410·실행한 길 스텝 11133·SHELTER 가 열린 결정 248 가운데 SHELTER 고름 0 |
| `Integrated.BrainObs24Route0` | Mass 두 지역 180 초 route0 = obs21zero (자리·요청·덮기 밖 로짓 칸 0~3 비트 단위 — 칸 4 는 route0 이 출력층 줄을 바꿨고 늘 막힘), 길 결정 110 모두 RUN |
| `Integrated.BrainRouteSwap` | 내장 → R7e 경계의 열린 도주가 그 H 에서 길 없음 결정, R7e 150 프레임 동안 SHELTER 고름 16, R7e → obs21zero 경계 뒤 길 상태 0·길 통계 멈춤, 되돌림 → R7e, 내장으로, 교체 넷, 스냅숏 칸, 마스크 위반·관측 칸 어긋남 0 |
| 헤드리스 게임 (`/Game/JYU/Maps/LV_JYU_V3Integration -game -NullRHI -EcoV3Brain=v3_r7_g995_s1_20m -EcoV3BrainSwapAt=80 -EcoV3BrainSwapTo=builtin`, 100 초) | '두뇌 시작 … 관측 24 도망길·반사 밖 도망 막음 … (두 길·반사 밖 도망 막음)', 10 초마다 '<지역> 길 \|'(예: 80 초 Barren 누적 'RUN 29% · 은신처 71% (반사 사슴-스텝 2207) · 길 결정 114 · 은신처 고름 90/95 · 무효 2'), 반사 밖 두뇌 도망 0%, 80 초 내장으로 바꾼 뒤 '두 길 끔 (앞 두뇌가 센 누적)'·구간 0. 경고·오류 줄 없음 |
| pytest (`herbivore_rl/`, PYTHONUTF8=1) | `test_route_port_v3`·`test_route2_v3`·`test_r7_mask5`·`test_ceval_v3`·`test_live_v3`·`test_flight_v3`·`test_flight_golden_v3` 115 통과·1 건너뜀(느린 `make_traces --check` — `ECO_ROUTE_PORT_SLOW=1` 일 때만, 파이썬·엔진 무관 헤더를 고치지 않았다). `test_ceval_v3` 의 EcoBrains 두뇌 파일 전부 검사(`--brain-check`)에 새 두 파일이 들고 통과 |

- 눈으로 보는 PIE(사슴 색·지역 줄·은신처 도착 웅크림)는 이번에 하지 않았다 — 글자·색은 `Integrated.RouteDisplay`, 길 줄·기록은 헤드리스 게임으로 봤다.

## 16. 10-24 적대적 검토 (이식 1/2·2/2 뒤 — 고친 것·다시 확인한 것·남은 차이·검증)

- 방법: 파이썬 줄(`world.py` `step` 첫머리·`_wf_update`·`_route_step`·`_route_apply`·`_route_shelter`·`_route_override`·`rep_peek`·`_fl_update`·`_fl_close`·
  `_rep_accumulate`, `rep_policy.py` `action_mask`·`_route_rows`·`_gate_free_rows`, `export_weights_v3.py` `contract_dict`·`flight_route_contract`)과 C++ 줄
  (`EcoWorldV3.h` `Step` A·H·`UpdateWildFlight`·`Detail::Route*`·`DecideHerb`·`FlightUpdate`·`FlightClose`, `EcoPolicyV3Inference.h` `ApplyRouteMaskRows`,
  로더·평가기·통합 서브시스템)을 줄마다 다시 견줬다. 볼 것: 스텝 차례·결정 조건·유지/무효·관측 시점·마스크 판 5·로더 계약·통계·사건 셈과의 관계,
  끈 세계 비트 동일, 열린 질문 처리, 게임 교체 경계. 파이썬 세계 코드(`env_v2`)·게임 기본 두뇌·기본 설정은 고치지 않았다.

### 16-1. 고친 것 (결함 셋 — 세계 동역학·두뇌 출력·파이썬 대조 값은 그대로)

| # | 결함 | 고침 | 시험 |
|---|---|---|---|
| 1 | **게임 refled 시계.** `Step` H 가 도망 길 기록에 스텝 번호로 `W.T − 1` 을 넘겼다. 통합 모드의 `W.T` 는 `CheckClockDrift` 가 팀 시계에 다시 맞출 때 4 스텝 넘게 뛴다(뒤로도). 그러면 끝난 도망의 끝 스텝(`FFlightTrack::LastEndT`)과 새 도망의 스텝 번호가 다른 시계라 refled 가 틀린다 — 뒤로 뛰면 50 스텝 뒤 새 도망도 refled, 앞으로 뛰면 20 스텝 뒤 새 도망도 아님(옛 줄을 g++ 로 돌려 확인). 평가기·파이썬 대조에는 시계가 뛰지 않아 드러나지 않았다 | `FlightStepEnd` 가 도망 기록 시계 `FFlightStats::Clock`(FlightUpdate 를 부른 횟수 — 쫓김 사건 이음 창 `EpUntil` 과 같은 시계)을 넘긴다. 스텝마다 1 씩 늘어 `W.T − 1`·파이썬 `self.t − 1` 과 **차이가 같으므로** 평가기·골든·파이썬 값은 그대로다(판 24 의 refled 737 건 그대로). `FlightUpdate` 꼴·골든 장면(`StepNow = kFsTickT − 1`)은 그대로 | `Route.FlightRecord` 에 시계 줄: `W.T` 1000 → 10(뒤로)·100 → 5000(앞으로)·경계 38(refled)/39(아님) |
| 2 | **`ceval.py trace_diff` 의 `split_gap`.** 갈린 결정의 근접 동점 잣대를 `gap`(열린 칸 1·2 위 로짓 차 ≥ 0)과 부호 있는 `route_gap`(ℓ4 − ℓ1)을 함께 `min` 해서 구했다. RUN 쪽으로 갈린 길 결정이면 음수가 적혀 근접 동점처럼 보이고, SHELTER 가 막힌 한 칸 결정의 `route_gap` 도 섞였다(진단 글만 — 판정·기록 무관. R7e 대조는 갈림이 없어 드러나지 않았다) | `gap` 만 읽는다(망 결정·길 결정 모두 열린 칸 둘 이상이면 1·2 위 차) | `test_trace_diff_split_gap_uses_top2_gap` (짜 맞춘 두 스텝 궤적) |
| 3 | **계약 대조의 `decide.on`.** 5-2 의 5 는 `decide {lock_steps, on, feasible, refeas_from}` 을 견주자고 했는데 UE 로더(`EcoV3Brain::RouteContractDiff`)·평가기 `RouteContractDiff` 가 `on` 을 보지 않았다(해시가 덮지만, 해시를 다시 셈하지 않고 손으로 고친 파일의 어긋난 칸 이름을 놓친다) | 둘 다 `on == ["onset", "invalid", "lock_and_feasible_changed"]`(차례 그대로)를 본다. 어긋나면 같은 칸 이름 `flight_route.decide` | `Brain.RejectRoute` 거부 사례 27 가지('flight_route.decide.on 에 invalid 없음'), 평가기 `--brain-check` 로 같은 파일 거부 확인 |

### 16-2. 다시 확인한 것 (고칠 것 없음)

| 볼 것 | 확인 |
|---|---|
| 스텝 차례 | A 첫머리 `RouteApply`(Commit·`KeepActive = KeepMode` 앞 — `KeepMode` = 파이썬 `wf_mode`) → B `FlightControlInput`(`KeepDir`) → … → D `++W.T` → H `FlightStepEnd`(실행한 길 = 적용 뒤·길 단계 전 = `rt_exec`) → `UpdateWildFlight`(실행한 길 셈 → 죽음 분기 지움 → 반사 방향 → a₀ → 은신처 굽히기·가장자리·벽 여유 → `RouteStep`) → `DecideAll`(길 결정 줄 망). `RouteStep` 뒤 `Dir` 를 바꾸는 줄이 없어 `RouteRunDir` = RUN 방향이다 |
| 결정 조건·유지/무효 | onset·cur·keep·feas·inval·age(먼저 더함)·refeas(RUN 만 — `cur ≠ SHELTER`)·dec 와 결정 뒤 칸(new·RouteK·Age·Feas·DecPrev·CandK·ShelterDir·Mu·E·관측)이 `_route_step` 두뇌 줄과 같다. 유지는 후보 조건 없이 μ_keep ≥ 0, 후보 동점은 엄격한 < (argmin 첫 번째), S 가 비면 μ = +∞ |
| 관측 시점 | H 에서 `Next` 를 정한 뒤 쓰고 E 는 건드리지 않는다. 죽음 분기·도주 아님·길 끈 두뇌는 0. SHELTER 가능 ⟺ 관측 22 > 0 (μ* ≥ 2 → μ*/10 ≥ 0.2, +∞ → 1) 이라 마스크(관측 22)와 적용(`bRouteSok`)이 늘 같은 판정이다 |
| 마스크 판 5 | 파이썬 `_gate_free_rows` = `reads ∧ override == WF_NONE`(경계 사슴은 override 가 NONE 이라 든다) = C++ 덮기 밖 갈래(경계 포함)의 `Prep.bReads`. 길 결정 줄(덮기)에는 걸리지 않고, 막은 뒤 GRAZE 가 늘 남는다(걸 때 실제 허용 GRAZE 확인) |
| 결정 셈 | `Stats.Decisions` = `bCommittedReads`(덮기 아님) ∨ `bCommittedRouteReads` = `_rep_accumulate` 의 `(decide ∧ ¬덮기) ∨ 길 결정`(판 4·5). `RouteRequest`·`bRouteReads` 는 `DecideHerb` 첫머리에서 모든 갈래 지움 |
| 통계·도망 길 기록 | picked·switches·choice·bad 는 A(적용 때), steps 는 H 죽음 분기 앞(스텝 첫머리 산 사슴), 길 칸 = 반사 ? 실행한 길 : none, 도망의 길 = 반사 스텝 최다(동점 앞 번호 = `np.argmax`), 원판 놓침 늑대마다·쫓김/가림 사슴마다(지난 표적 늑대 모두 가려야 가림), 열린 도망 잘림, 죽으면 `LastEndT` 지움 |
| 사건 셈과의 관계 | 길 기록은 `FFlightStats`(끝 까닭·지켜보기 hide·쫓김 사건 episode)를 하나도 바꾸지 않는 덧붙임 칸이다(`FlightClose` 의 길 칸 비우기는 끈 세계에서 늘 0). 16-1 의 1 뒤로는 refled 와 사건 이음 창이 같은 시계다 |
| 끈 세계 비트 동일 | 새 줄은 모두 `bRoute`·`bFleeGate`·`RS != nullptr` 안이거나 값이 같은 리팩터다(`WallKeep` — 같은 `kEps²`·같은 `Normalize`·다 지워지면 입력 그대로, `NetInputOf` 관측 21 — 같은 칸 차례). 판 2 두뇌의 `ObsLayoutMismatch`·마스크·결정 셈 그대로 |
| 로더·평가기 계약 | 해시 넷·관측 이름 24 차례·판(해시와 짝)·`flight_route` 칸 전부(16-1 의 3 뒤)·판 5 키(판 4 에는 없음)·모델 허용 얼기/잠 거부가 파이썬 `contract_dict`·`check_route_allowed` 와 같은 뜻이다. 걸 때 실제 허용(두뇌 ∧ 세계)은 평가기 `Init`·통합 `RouteBrainBlocker` 가 다시 본다 |
| 열린 질문 처리 (14-2·15-2) | 권고(1·12)·파이썬 동작(5·6·16·17)과 맞다. 1·2·17 은 교체 경계 한 스텝만, 3·15 는 부활 세계·판 2·3 만이라 판정·게임 기본과 무관하다 |
| 게임 교체 경계 | 내장 → 판 5: 열린 도주는 그 H 에서 `cur < 0` 결정(새 두뇌가 고름). 판 5 ↔ 판 4: 길 상태 그대로, 경계 스텝의 요청·마스크는 앞 두뇌 것(경계 스텝 마스크 확인도 앞 마스크). 판 4·5 → 길 없는 두뇌: A 가 `RouteRunDir`(곧바로 RUN), 그 H 가 지움, 그 스텝부터 도망 길 기록 끔. 대기 두뇌 거부(`DiscardPending`)는 되돌림 쌓개를 복구하고, 폴더 감시는 그 파일을 `WatchedFile` 로 기억해 같은 파일을 되풀이해 거부하지 않는다. 지역 세계는 `TryCreateContexts` 가 한꺼번에 만들고 WildFlight 는 콘솔 변수 하나라 지역마다 걸기 전 검사가 갈리지 않는다 |

### 16-3. 남은 차이 (고치지 않았다)

1. **화면 한 스텝.** 사슴 글자는 덮기를 `KeepActive`(이번 스텝에 실행한 덮기)로, 길을 다음 스텝 길(`ShownRoute`)로 고른다. 도주가 끝나는 스텝은 H 가 길 상태를 지워
   `KeepActive` 만 도주라, 두 길 두뇌에서도 그 한 스텝(2/15 초) '도주(안전해질 때까지)' 주황이 보인다. 세계·기록은 그대로이고 실행한 길을 따로 남겨야 고칠 수 있어 두었다.
2. **Social 제어(기본 꺼짐).** `eco.IntegratedV3.SocialControl 1` 이면 Social 훅(B)이 SHELTER 길보다 나중이라 슬롯 쪽이 이기고(15-2 질문 8), 훅이 도주 사슴의 행동을
   바꿔도 길 통계 steps 는 반사 덮기 기준으로 그 스텝을 센다. 파이썬에 Social 이 없어 파리티와 무관하다.
3. **기존 차이 그대로:** 부활 세계 다시 난 사슴(질문 3), 판 2·3 결정 셈(질문 15), 길 없는 두뇌 → 판 4·5 경계 한 스텝의 도망 길 기록 'none'(질문 17), 도망 길 칸은
   길을 켠 동안만 센다(끈 동안 끝난 도망은 refled 의 끝 스텝을 남기지 않는다), 근접 동점 갈림 허용(질문 13).
4. **계약 문서·눈으로 보는 PIE**(11-1 의 8, 15-3)는 이번에도 하지 않았다.

### 16-4. 검증 (10-24, 고친 뒤)

| 검증 | 결과 |
|---|---|
| 직접 UBT `AdaptiveEcosystemEditor Win64 Development -WaitMutex -NoHotReloadFromIDE` (적응 unity — 바뀐 파일 따로) | 성공, 경고 0 |
| 직접 UBT `-DisableAdaptiveUnity` (바뀐 파일도 unity 묶음) | 성공, 경고 0 |
| 자동화 `Automation RunTests AdaptiveEcosystem` (-NullRHI) | 214 개 실패 0 (213 Success + 1 기존 예상 경고 `Predation.SaveLoadGlobalEma` 저장 파일). `Route.*` 7·`Brain.LoadObs24Route`·`RejectRoute`(27 사례)·`Integrated.*Route*` 5 통과 |
| g++ 하네스 (`-O2 -ffp-contract=off -Wall -Wextra -Werror -Wshadow`) | 엔진 `route_v3_main.cpp`(기하 90·줄 923·적용 117·마스크 57·기준 루프 두뇌 둘·도망 길 기록 장면)·스칼라 참조 `route_ref_main.cpp`·기존 하네스(추론 v1·v3·도망·숲 시야·장애물 관측·레퍼토리·위협·밤·돌아가기·장애물·무리·날씨) — g++ 로 짓고 돌리는 시험 14 개를 넣은 골든 묶음 87 시험 모두 통과 |
| 판 단위 궤적 대조 `port/native_check.py` (route0·늘 SHELTER × N·G × 지역 셋 × 시드 34900·34901 × 1800) | 24/24 — 궤적 지문 1801 스텝 × 칸 아홉 첫 차이 없음, 세계 기록 정확히 같음(`flight.route` refled 합 737 포함) |
| `ceval.py compare` R7e (`route=true`·`brain_flee_outside_reflex=false`, 시드 34900~34904 × 지역 셋, 1800) | N 15/15·G 15/15 기록 정확히 같음, 파이썬에만 있는 칸 없음, 궤적 셋 첫 비트 차이·갈림 없음. 근접 동점: 망 결정 최소 로짓 차 1.14e-4, 길 결정 3.23e-4, 1e-4 밑 0 |
| `ceval.py compare` 끈 세계 (obs21zero, 같은 시드) | N 15/15·G 15/15, 궤적 셋 첫 비트 차이 없음 — 이식 전과 같다 |
| pytest (`ECO_ROUTE_PORT_SLOW=1`) | `test_route_port_v3`(느린 `make_traces --check` 포함)·`test_route2_v3`·`test_r7_mask5`·`test_ceval_v3`(새 `split_gap` 시험 포함)·`test_live_v3`·`test_flight_v3`·`test_flight_golden_v3` 117 통과, 건너뜀 0 |

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
