# 1-5 사전 등록: Gate E2 (v2.2 경계·threat_recency, v1 먹이 위)

- 작성: 2026-10-03 (토). 게이트를 돌리기 전, 결과를 보기 전에 적었다. 도구 시험(scratchpad, 작은 조건)도 이 문서를 쓴 뒤에 한다.
- 이 문서를 결과를 본 뒤 바꾸면 맨 아래 변경 기록에 날짜와 이유를 남긴다(계획서 6.1-3).
- 근거: `AdaptiveEcosystem/Docs/RL_Policy/RL_V2_PLAN.md`
  - 1단계 표 1-4·1-5 행. 1-5: "구간 = {포식자 보임, 최근 위협(threat_recency > θ)·안 보임, 평시}. E2a: 경계 허용 C2-seg vs 경계 금지 C2-seg. E2b: '최근 위협·안 보임' 구간에서 경계 vs 계속 뛰기(나머지 동일)". 기준: "E2a: G_γ 유의 차. E2b: 경계가 G_γ와 피식률에서 유의하게 이긴다. E2b 실패 시 B3를 2차로 내리고 1차를 B1, B2, B5′로 바꾼 뒤 4.4 장치 후보를 검토한다".
  - 4.2 관측 표 idx 7 threat_recency(개체별, 보이면 1, 안 보이면 감쇠, 리스폰 0, "감쇠 상수는 Gate E2에서 정한다"), 4.3 행동 idx 5 vigilance(0.5 초과면 경계, speed보다 우선), 4.4 1단계 표 경계 행(속력 0, 섭식 0, 360°·반경 그대로, heading: 보이면 가장 가까운 포식자 쪽, 안 보이면 마지막 위협 방향), ThreatDir 개체별·리스폰 초기화, "S2가 이득이라는 근거는 아직 없다"와 E2b 실패 때의 장치 후보(얼어붙기, 추격 포기 — 이번에는 넣지 않는다), 4.7 초기화(vigilance 편향 −0.84), 5.0 게이트 공통 규칙(C2-seg vs C2, G_γ, 각 112 trial·같은 보정 시드, 보정 최대 2회, 보상은 바꾸지 않음, G_0.998 보고), 6.1(G_γ 정의, 평가 시드 10000~10019 × 5000스텝 짝지은 t, |t| > 2.093), 6.2 B3·B4·B5·B5′와 '경계 지표와 360°' 주의, 9절 "경계 미사용·남용, 놓친 직후 경계가 이득이 없음" 행, 10절 #1(threat_recency)·#5(360°만, 반경 그대로)·#18(위협 반대 조향 항은 넣지 않고 시작, E2b '계속 뛰기' 쪽 변형도 잰다)·#27(γ_sel 0.9917).
  - 기반: Gate E1-b 통과 계수(`configs/v2_1.yaml`, `results/v2/e1/judge_e1b.md`), 1-4 구현(`env_v2/world.py` `_vigil_step`·`_perceive`·`vigil_stats`, `configs/v2_2.yaml`).
- 계산 코드: `diagnose_v2.py constsearch`(C2, `--seg-bins`·`--seg-dims`의 C2-seg, `--const-action`의 고정 상수·구간표 평가, `--g998`)와 그것을 부르고 판정하는 `gate_e2.py`(`configs`·`run`·`judge`). `gate_e2.py`의 상수(`DECAYS`, `THETA`, `SEG_BIN`, `ROUND_COEF`, `C2_ENQUEUE`, `E2B_FLEE`, `T_CRIT`, `VIG_FRAC_RANGE`)와 함수(`round_config`, `cand_commands`, `e2b_table`, `judge_e2a`, `judge_e2b`, `judge_t18`, `select`, `next_round`)가 이 문서를 옮긴 것이다. 단위 테스트는 `tests/test_gate_e2.py`. 코드와 이 문서가 어긋나면 이 문서가 기준이다. 어긋남을 찾으면 코드를 고치고 변경 기록에 남긴다.
- 이 게이트를 위해 env_v2 에 더한 것(결과 보기 전, 10-03): vigilance 계수 `threat_flee`(10절 #18 변형 항의 배수, `env_v2/world.py` `_threat_flee_term`, `env_v2/steering.py` `steer(extra=)`). `configs/v2_2.yaml`은 0(끔)이고 0이면 1-4 구현과 비트 단위로 같다(`steer`에 아무것도 더하지 않는다, `tests/test_vigilance_v2.py`). E2b의 R18 팔(3.7) 설정 사본만 1로 둔다.

## 0. 이 게이트가 묻는 것

- E2a: 환경이 상태에 따라 경계를 켜고 끄는 해에 G_γ 이득을 주는가(9절의 '환경 실패' 검사). 상수로 경계를 늘 켜면 섭식 0 이라 굶으므로, 이득이 있다면 구간별로 켜고 끄는 해에서만 나온다.
- E2b: S2(도주하다 놓친 개체가 멈춰서 위협 쪽을 본다)가 '계속 뛰기'보다 이득인가. 4.4: 포식자는 기억 없이 시야 안 최근접을 매 스텝 추격하므로 놓친 뒤 멈추면 거리를 잃을 수 있다. 360° 시야로 뒤의 포식자를 먼저 찾는 이득과 맞바뀐다.
- threat_recency 감쇠 상수(4.2 "Gate E2에서 정한다")와 '최근 위협' 문턱 θ를 정한다.

## 1. 무엇을 재나

| 항목 | 고정값 |
|---|---|
| 세계 | `configs/v2_2.yaml`(version 2.2 = v2.1 세계 + vigilance). 포식자 속도 ×0.6~0.95(E1-b overrides), speed는 E1-b 통과 계수(c_rest 15/21, c_move 37.5/21, 섭식 [1, 0.5, 0], 문턱 [1/3, 2/3], 속력 [0, 0.4, 1.0]), 먹이는 v1 그대로(food_v 끔), 보상 4.5 그대로(`net_energy_reward: true`). vigilance 규칙값: 문턱 0.5(a > 0.5 면 경계), 경계 섭식 배수 0, 경계 시야 360°·반경 see_r 그대로, threat_flee 0 |
| 후보 = threat_recency 감쇠 | decay ∈ {0.9, 0.95, 0.975}. 반감기 6.6 / 13.5 / 27.4스텝(0.9 / 1.8 / 3.7초). 제안값은 0.95(`configs/v2_2.yaml` 시작값, v1 관측 5 recent_predation EMA와 같은 척도, 계획서 2.2 T7). `gate_e2.py configs`가 후보마다 vigilance.decay(와 4절 보정 계수)만 바꾼 사본을 `results/v2/e2/configs/<회차>_<후보>.yaml`(후보 이름 `d0_9`, `d0_95`, `d0_975`)로 만든다. #18 변형(3.7)은 threat_flee만 1로 둔 사본 `<회차>_<후보>_tf1.yaml`이다 |
| θ | 0.5 고정(후보 아님). '최근 위협' = 놓친 뒤 반감기 안. `env_v2/world.py` `RECENT_THREAT`(vigil_stats 구간 정의)와 같다. θ에서 놓친 뒤 '최근 위협'에 머무는 스텝 수 K = floor(ln θ / ln decay)는 후보별 6 / 13 / 27이다(놓친 뒤 k번째 관측의 tr = decay^k) |
| 구간 (C2-seg) | 관측 7 threat_recency 하나의 문턱 [θ, 1](`--seg-bins threat_recency:0.5,1`): **s0 평시**(tr < θ), **s1 최근 위협·안 보임**(θ ≤ tr < 1), **s2 포식자 보임**(tr = 1). 포식자가 보이면(관측 1 > 0) `_perceive`가 tr을 1로 두고, 안 보이면 tr ≤ decay < 1이라 'tr ≥ 1' ⇔ '보임'이다(float32 관측에서도 성립, `tests/test_gate_e2.py`). 계획서의 'tr > θ'와 구간 도구의 'tr ≥ θ'는 tr = θ에서만 다른데, 후보에서 decay^k = 0.5가 되는 k가 없어 같다. 보임은 그 개체의 결정 관측 기준이다(직전 스텝에 경계한 개체는 360°) |
| γ | γ_train = `configs/ppo_best.yaml`의 0.9916661555611042(#27). G_γ 꼬리 600스텝 제외, 앞 제외 없음 |
| 정책 | 모두 결정적 상수 정책(학습 정책 없음). 행동 모드 비교(6.1-7)는 상수에는 없다 |
| 평가 | 평가 시드 10000~10019(20개) × 5000스텝. 보정 시드(탐색 0~7, 재측정 100~119)와 겹치지 않는다. 같은 평가 시드에서 짝지어 비교한다 |

- C2-seg에게 decay와 θ는 K(놓친 뒤 몇 스텝까지 '최근'인가)로만 보인다. 학습 정책은 tr의 연속값을 보므로, 이 게이트가 고르는 것은 'K 창'이고 연속값의 쓸모는 1-6의 C4-threat로 본다(6절 한계).

## 2. 정책과 탐색 (회차마다 같은 절차)

| 정책 | 절차 |
|---|---|
| **C2** (상태 안 보는 최적 상수, 행동 6개) | Optuna TPE 112 trial(시드 0, constant_liar, 7개씩 묶음), 목표 G_γ. 탐색 시드 0~7 × 3000스텝, 상위 5개를 재측정 시드 100~119 × 3000스텝으로 다시 재서 가장 높은 것(`diagnose_v2.py` 기본값, E1과 같다). 시작점 3개(112 안에 든다): E1-b가 고른 v2.1 C2 [0.9710, 0.7849, 0.2182, 0.0336, 0.4914](`results/v2/e1/judge_e1b.json` final.c2) + vigilance 0.25, v1 최적 상수 [0.4207, 0.8656, 0.1054, 0.0044] + speed 0.5 + vigilance 0.25, v1 학습 전 최고 상수 [0.39, 0.99, 0.92, 0.15] + 0.5 + 0.25. vigilance 0.25는 '경계 아님' 띠의 가운데(`diagnose_v2.PRETRAIN_EXTRA`). **회차마다 한 번**, 제안 후보(d0_95) 설정에서 찾는다: 상수는 관측을 읽지 않고, decay는 관측 7과 통계만 바꾸므로(threat_flee 0) 상수의 세계는 후보마다 비트 단위로 같다(`tests/test_gate_e2.py`). 판정 때 후보마다 A-금지의 시드별 G_γ가 C2와 비트 단위로 같은지 본다(C2의 vigilance ≤ 0.5일 때) |
| **A-금지** | C2의 앞 5개 + vigilance 0.0. 탐색 없음. C2의 vigilance가 0.5 이하이면 C2와 같은 세계다 |
| **A-허용** (구간별 vigilance + 바탕 C2) | C2-seg, `--seg-dims vigilance`(구간 3개 × 1), 바탕 = C2. 같은 TPE 112 trial, 같은 탐색·재측정 시드·스텝, 같은 목표. 시작점은 C2 자체(모든 구간 = C2 값, 도구 기본값) |
| **B-금지** (구간별 speed, vigilance 0 고정) | C2-seg, `--seg-dims speed`(3), 바탕 = A-금지. 같은 TPE 112 trial. 시작점은 C2 자체 |
| **B-허용** (구간별 speed + vigilance) | C2-seg, `--seg-dims speed vigilance`(6), 바탕 = C2. 같은 TPE 112 trial. 시작점 2개: C2 자체, B-금지의 최적 구간표(vigilance는 C2 값). 허용 탐색 공간이 금지 공간을 포함하므로 금지의 최적점을 시작점으로 넣어 탐색 예산의 불리함을 줄인다 |
| **E2b V·R** (손으로 만든 짝, 탐색 없음) | 바탕 상수: forage·cohesion·cover = C2, **flee_dist 1.0**, speed = C2, vigilance 0. 구간표(`--seg-dims speed vigilance`): s0 평시 (C2 speed, 0), s2 보임 (1.0 = 뛰기, 0), s1 최근 위협·안 보임: **V** = (C2 speed, 1.0 = 경계), **R** = (1.0 = 뛰기, 0). 두 팔은 s1에서만 다르다. flee_dist 1.0의 이유: '도주하다 놓친'(S2) 전제를 만들려면 보일 때 늘 도주 분기(d_pred < flee_dist·see_r)에 들어야 한다. 도주 분기는 포식자가 보일 때만 작동하므로 flee_dist는 s2에서만 행동을 바꾼다 — 두 팔에 같다 |
| **R18** (#18 변형, 보고) | R과 같은 정책을 threat_flee 1 설정 사본에서 잰다. 항 = threat_flee · flee_weight(3.0) · threat_recency · (−ThreatDir)를 결정 관측에서 포식자가 안 보인 개체의 조향 합에 정규화 전에 더한다(보인 개체는 v1 도주 항이 맡아 0, 위협을 본 적 없으면 0). s1뿐 아니라 tr < θ인 s0 개체에도 θ·3 이하의 크기로 걸린다 |
| **E2b-표** (보고) | 바탕 = C2, 구간표 = B-허용 최적표에서 s1만 바꾼다: V = (그 표의 s1 speed, 1.0), R = (1.0, 0) |
| **G_0.998 보고** | A-금지, A-허용, B-금지, B-허용, E2b V·R을 `--g998`(γ 0.998, 10000스텝, 앞 500·끝 2500 제외)로 같은 평가 시드에서 다시 잰다. 탐색은 γ_train으로만 한다 |

- 결과 지표(수명, 번식, 피식률, 아사율, 리턴), 보행 지표(`World.gait_stats`), 경계 지표(`World.vigil_stats`)는 롤아웃 전체 값이고 표의 값은 평가 시드 20개의 평균이다. 경계 지표의 시야 합침 열은 360° 경계 지속 때문에 치우친다(6.2 '경계 지표와 360°'). 판정에는 경계 비율(`vig_frac`, 3.1 (iii))만 쓰고 나머지는 기술용이다.
- Utility v2(C5)는 아직 없어 넣지 않는다(E1과 같다).

## 3. 판정 (후보마다. γ_train G_γ와 평가 시드 짝지은 t)

1. **E2a (판정 갈래 A: 구간별 vigilance + 바탕 C2 vs C2·vigilance 0)**. 5.0 공통 규칙("C2-seg는 이번 버전에 추가된 행동만 구간별, 나머지는 C2 값" vs C2)을 문자 그대로 쓴 것이다. 경계 허용 C2-seg = 구간별 vigilance + 바탕 C2, 경계 금지 = 같은 바탕에 vigilance 0 고정. 셋 다 성립해야 통과다.
   - (i) **유의하게 높다**: d(s) = G_γ(A-허용, s) − G_γ(A-금지, s), t = mean(d)/(sd(d, ddof=1)/√20). mean(d) > 0이고 t > 2.093. sd = 0이면 성립하지 않는다.
   - (ii) **구간별 경계 상태가 서로 다르다**(5.0 "구간별 최적값이 서로 다르다"): A-허용 표의 세 값을 문턱 0.5로(> 0.5 = 경계) 바꿨을 때 경계·비경계가 둘 다 있다.
   - (iii) **경계 비율이 0 근처·과반이 아니다**(9절 환경 실패 신호): A-허용 평가의 경계 비율(`vig_frac`, 개체-스텝, 시드 평균)이 0.01 이상 0.5 이하. 0.01은 4.7 탐색 붕괴 감시의 1%와 같은 문턱이다.
2. **E2a 갈래 B (보고, 멈춤 조건)**: B-허용 vs B-금지에 1의 (i)~(iii)을 그대로 쓴다. 1-5의 'C2-seg vs C2-seg'를 둘 다 구간 구조가 있는 C2-seg로 읽으면 v2.2에서 vigilance 말고 구간별로 둘 행동은 speed뿐이라 이 갈래가 된다. A는 보행이 상수(C2)라 '다시 보이면 뛴다'를 쓸 수 없다. B는 PASS를 정하지 않는다. 다만 A가 모든 후보에서 실패하고 B가 통과한 후보가 있으면 실패가 '상수 보행' 제약 때문일 수 있으므로 환경 보정(4절)을 하지 않고 멈춰 보고한다(사람 결정).
3. **후보 선택**: A를 통과한 후보 가운데 제안값(0.95)이 있으면 그것, 없으면 A의 t가 가장 큰 후보. 한 회차에 통과한 후보가 있으면 그 회차에서 멈춘다. 다중 비교 보정은 하지 않는다(후보 3개를 따로 판정하고 고르는 규칙을 미리 정해 둔다, E1과 같다). B 갈래 멈춤의 보고 후보도 같은 규칙(B의 통과·t)으로 고른다.
4. **E2b** (고른 후보에서 판정, 다른 후보는 보고): V − R을 평가 시드마다 짝짓는다. (G) mean(G_γ(V) − G_γ(R)) > 0이고 t > 2.093, (P) mean(피식률(V) − 피식률(R)) < 0이고 t < −2.093. 피식률 = 피식 사망 / (스텝 × N)(`World.stats` predation_rate). **E2b 통과 = (G)와 (P) 둘 다.** E2a가 실패하면 E2b는 판정하지 않고 보고만 한다(B 갈래 멈춤이면 그 후보, 아니면 제안 후보).
5. **0.998 갈래**(5.0 "0.998에서만 통과하면 그 버전은 0.998로 학습한다"): 어떤 후보가 A에서 (i)만 γ_train으로 실패하고 G_0.998 보고에서 같은 기준(Δ > 0, t > 2.093)을 넘으며 (ii)·(iii)은 통과하면, 보정 회차로 가지 않고 멈춰 보고한다. 0.998 재탐색은 사람이 정한다(#27 γ_sel과 달라지므로).
6. **보조 지표**(판정 아님): A·B 허용·금지와 E2b V·R의 결과 지표(수명, 피식률, 아사율, 번식, 아사 비중)와 짝지은 t, 경계 지표(구간 비율, 구간별 P(경계), b3_narrow·b3_truth, b4_narrow, b8_vig, 360° 관측 비율), 보행 지표(정지·걷기·뛰기, B1, B2, B8). 구성 검사: 정책의 바탕·표가 2절과 같은지, A-금지가 C2와 비트 단위로 같은지.
7. **#18 보고**: R18 − V, R18 − R(G_γ, 피식률, 수명, 짝지은 t). **'크게 이김' = R18이 V와 R 둘 다보다 G_γ에서 유의하게 높다(Δ > 0, t > 2.093)** — 그러면 조향 계약 변경안 후보로 보고한다(결정은 사람, #18). 게이트 판정에는 들어가지 않는다.

## 4. 보정 (최대 2회: V1, V2. 대상은 9절의 경계 섭식 손실과 반경 배수뿐이다)

- 보정은 **E2a가 A·B 두 갈래 모두에서 통과한 후보가 없을 때만** 한다(9절 '환경 실패'). 3.2의 B 멈춤, 3.5의 0.998 갈래가 먼저다. 기준 후보(0.95)의 A-허용이나 B-허용 경계 비율이 0.5를 넘으면(과반, 남용) 경계를 더 싸게 하는 보정은 반대 방향이라 멈춰 보고한다.
- 사다리(고정, `gate_e2.ROUND_COEF`):
  - **V1**: 경계 섭식 배수 eat_mult 0 → 0.5(경계 중에도 걷기만큼 먹는다). 계약 항목이 아니다.
  - **V2**: eat_mult 0.5 + 경계 반경 배수 M_vig 1.5. 정의(V2에 갈 때만 구현한다): 경계한 스텝 뒤 관측의 포식자 탐지 반경 = see_r × M_vig(동족 시야는 see_r 그대로), 관측 2의 분모를 모든 개체에서 고정 상수 see_r × M_vig로 바꾼다(4.2 "그때는 분모를 고정 상수 see_r × M_vig로 바꾼다(계약 항목)"). threat_recency의 '보임'도 같은 탐지를 쓴다. 구현과 테스트를 마친 뒤 V2 설정을 만들고 변경 기록에 남긴다.
- 보정 회차도 1~3절 절차를 그대로 쓴다(C2부터 다시 찾는다. 같은 탐색·재측정·평가 시드, 같은 후보 3개). 보정 시드를 회차마다 다시 쓰므로 보정 시드 과적합 위험이 있다. 평가 시드는 탐색에 쓰지 않는다.
- 같은 계수 회차가 다시 나오면 결정적 탐색이라 같은 결과가 나오므로 멈춘다(E1 4절 보충과 같다). V2 뒤에도 통과한 후보가 없으면 **멈추고 보고한다**(다음은 사람이 정한다).
- 보상(4.5), speed 계수, 포식자 규칙은 바꾸지 않는다. 4.4의 장치 후보(얼어붙기, 추격 포기)는 넣지 않는다.
- **E2b 실패는 보정하지 않는다.** 실패로 기록하고, B3를 2차로 내리고 1차를 B1·B2·B5′로 바꾸는 것과 4.4 장치 후보 검토는 사람이 정한다(1-5 행).
- 회차마다 대상·값·이유를 `judge_e2.md`의 "다음" 줄과 보고서 보정 이력에 적는다.

## 5. 통과 뒤

- **E2a PASS**: 고른 후보의 decay(와 그 회차의 eat_mult·반경 배수)를 `configs/v2_2.yaml`에 반영하고 주석에 날짜·이유·결과 경로를 적는다. θ 0.5는 그대로다(`env_v2/world.py` `RECENT_THREAT`). 0.95가 고르면 값은 그대로 두고 게이트 통과 주석만 더한다. 계획서 4.2·4.4의 계수 문구는 값이 바뀔 때 같이 고친다. decay는 E2a 선택 규칙이 정하므로 E2b 결과와 무관하게 반영한다.
- E2b 결과는 계획서 1-5 행과 `configs/v2_2.yaml` 주석에 적는다. E2b FAIL이면 B3를 1-6에서 어떻게 다룰지는 사람 결정이다.
- 1-6 완료 기준 "학습 실패 감지: C0의 G_γ가 … E1·E2의 C2-seg보다 유의하게 낮지 않다"의 E2 C2-seg는 고른 후보의 A-허용 C2-seg다(B-허용은 함께 보고한다). 같은 평가 조건으로 C0을 잰다.
- 학습(1-6)은 이 문서 범위 밖이다.

## 6. 한계 (결과 보기 전에 적는다)

- 상수 탐색은 TPE 시드 하나다. 학습 시드 층이 없어 IQM·부트스트랩은 없다. 평가 시드 20개의 짝지은 t만 쓴다.
- C2-seg에게 decay·θ는 K 창으로만 보인다(1절). θ를 고정했으므로 '창 길이' 선택은 decay 후보 셋(K 6·13·27)에 묶인다.
- A는 보행이 상수(C2)라 '경계로 찾고 뛰어 도망'을 쓸 수 없다. 그 경우는 B와 E2b가 본다. B-허용은 6차원이라 금지(3차원)보다 탐색이 어렵다(시작점으로 일부 보완).
- E2b는 손으로 만든 짝이다(보일 때 늘 뛰며 도주, 평시는 C2). 최적 정책 안의 비교가 아니라 'S2 전제'의 직접 비교다. E2b-표(보고)는 B-허용 최적표 위의 같은 비교다.
- 경계 지표는 360° 경계 지속으로 치우친다(6.2). 판정에 경계 비율만 쓰고 나머지는 기술용이다.
- v1 먹이(즉시 재생) 위의 값이다. v2.3에서 먹이 2층을 넣으면 경계의 섭식 비용이 달라질 수 있다.
- 보정 시드를 회차마다 다시 쓴다(4절). 후보 3개 × 갈래 2개의 다중 비교를 보정하지 않는다(판정은 A 하나, 선택 규칙은 고정).

## 7. 실행 명령 (Git Bash, 작업 디렉터리 `herbivore_rl/`)

```bash
python -m pytest -q
python gate_e2.py configs --round V0
python -u gate_e2.py run --round V0 --c2 --workers 18
python -u gate_e2.py run --round V0 --cand d0_9 --workers 6 &
python -u gate_e2.py run --round V0 --cand d0_95 --workers 6 &
python -u gate_e2.py run --round V0 --cand d0_975 --workers 6 &
wait
python gate_e2.py judge
# 보정 회차(필요할 때만): judge_e2.md 의 "다음" 줄이 정한 회차로 configs → run --c2 → run --cand ×3 → judge
```

후보 하나의 `run`이 순서대로 부르는 명령(값은 앞 단계 결과로 채운다. 전문은 후보마다 `run.json`에 남는다. `<seg>` = `--seg-bins threat_recency:0.5,1`):

```bash
# 회차 C2 (results/v2/e2/<회차>/c2)
python diagnose_v2.py constsearch --config results/v2/e2/configs/<회차>_d0_95.yaml --workers 18 --out results/v2/e2/<회차>/c2 \
    --enqueue <E1-b C2 5개> 0.25 --enqueue 0.4207 0.8656 0.1054 0.0044 0.5 0.25 --enqueue 0.39 0.99 0.92 0.15 0.5 0.25
# 후보 (results/v2/e2/<회차>/<후보>, 설정 <회차>_<후보>.yaml)
python diagnose_v2.py constsearch --config <후보 설정> --workers 6 --out <후보> --tag a_forbid --const-action <C2 앞 5개> 0.0
python diagnose_v2.py constsearch ... --tag a_allow <seg> --seg-dims vigilance --base-action <C2 6개>
python diagnose_v2.py constsearch ... --tag b_forbid <seg> --seg-dims speed --base-action <C2 앞 5개> 0.0
python diagnose_v2.py constsearch ... --tag b_allow <seg> --seg-dims speed vigilance --base-action <C2> \
    --enqueue <C2 speed, C2 vig> ×3 --enqueue <B-금지 s0, C2 vig, s1, C2 vig, s2, C2 vig>
python diagnose_v2.py constsearch ... --tag e2b_vig <seg> --seg-dims speed vigilance \
    --base-action <C2 forage> <C2 cohesion> 1.0 <C2 cover> <C2 speed> 0.0 --const-action <C2 speed> 0.0 <C2 speed> 1.0 1.0 0.0
python diagnose_v2.py constsearch ... --tag e2b_run (같음) --const-action <C2 speed> 0.0 1.0 0.0 1.0 0.0
python diagnose_v2.py constsearch --config <후보>_tf1.yaml ... --out <후보>/tf --tag e2b_run18 (e2b_run 과 같은 정책)
python diagnose_v2.py constsearch ... --tag e2b_tab_vig|e2b_tab_run <seg> --seg-dims speed vigilance --base-action <C2> --const-action <B-허용 표, s1 만 바꿈>
python diagnose_v2.py constsearch ... --out <후보>/g998 --tag <a_forbid|a_allow|b_forbid|b_allow|e2b_vig|e2b_run> --g998 ...
```

- 예상 시간(추정): C2 탐색 1회(워커 18) 약 10분. 후보 하나 = 탐색 3회(A-허용, B-금지, B-허용, 각 약 16분, 워커 6) + 평가 약 25분이라 약 75분이고, 후보 3개를 동시에 돌려 회차 하나 약 1.5시간.
- 기존 결과와 캐시는 덮지 않는다. 출력은 `results/v2/e2/` 아래뿐이다. `gate_e2.py run`은 다른 설정의 결과가 있는 디렉터리에 쓰지 않는다.

## 변경 기록

- 2026-10-03: 처음 작성(결과 보기 전). 같은 날 결과 보기 전에 env_v2 vigilance 계수 `threat_flee`(#18 변형, 0 = 끔)를 더했다(머리말).
- 2026-10-03(V0 시작 전): 도구 시험 1회. V0 세 후보를 scratchpad 에서 `--smoke`(탐색 3 trial·1시드·700스텝, 평가 2시드 × 1300스텝, G_0.998 2시드)로 돌려 명령 순서·JSON·판정표(`judge_e2`)가 끝까지 도는지 봤다. 그 값은 판정에 쓰지 않는다. 구성 검사(바탕·표, A-금지 = C2 비트 일치)가 세 후보에서 맞았다. 도구 결함은 없었다(규칙 변경 없음).
- 2026-10-03(V0 판정 뒤): V0에서 d0_95만 A 갈래를 통과했다(Δ G_γ +0.470, t +3.93, 구간별 경계 —·경계·—, 경계 비율 0.161). d0_9는 (i) t +2.08로 기준 미달, d0_975는 A-허용이 C2 자체(경계 안 씀)였다. 3.3 선택 규칙으로 d0_95를 골랐고 **E2a PASS**다(보정 회차 없음). 고른 후보의 E2b는 (G) Δ +0.959·t +5.53, (P) Δ −0.00057·t −9.16으로 **E2b PASS**다. B 갈래는 세 후보 모두 B-금지·B-허용이 C2 자체(걷기·경계 끔)로 실패했다(PASS에는 영향 없음, 3.2). 5절대로 `configs/v2_2.yaml`에 통과 주석을 더했다(값 그대로: decay 0.95, eat_mult 0). 판정 규칙·기준 변경 없음. 판정과 별도로 사전 등록 밖 탐색을 한 번 했다(재측정 시드 100~119 × 3000스텝, 평가 시드는 쓰지 않음, 판정에 쓰지 않음): A-허용 대 '최근 위협 구간에서 경계 없이 정지', 경계 시야 120° 사본, 경계 섭식 1.0 사본. 기록은 보고서 `report.md`.
