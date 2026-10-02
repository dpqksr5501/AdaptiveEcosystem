# 1-2 Gate E1-b 보고서 (포식자 속도 ×0.6~0.95, v2.1 보행·대사, v1 먹이 위)

- 작성: 2026-10-02. 판정: **PASS**(B1, 팔 r2_5_ew0_5).
- 사전 등록: `PREREG.md`. E1-b 변경 기록 1건(사람 승인)과 회차 기록 2건(B0 판정 뒤, B1 판정 뒤)이 있다.
- 자동 판정표: `judge_e1b.md`, `judge_e1b.json`(`python gate_e1.py judge --attempt E1-b`). E1의 `judge.md`·`judge.json`·R0·R1 결과는 건드리지 않았다.
- E1과 바뀐 것은 세계의 포식자 속도 범위 하나다: `rand.pred_speed_mult` [0.8, 1.2] → [0.6, 0.95](`configs/v2_1.yaml` overrides).
- 절차·판정 규칙·기준·시드는 E1과 같다.
  - 팔마다 C2와 C2-seg를 TPE 112 trial로 찾았다(탐색 시드 0~7 × 3000, 재측정 100~119 × 3000, 상위 5개).
  - C2-seg는 구간 (관측2 < 0.5) × (energy < 0.5)마다 speed만 따로 갖는다.
  - 평가는 평가 시드 10000~10019 × 5000스텝이고, G_γ는 γ 0.9917(끝 600스텝 제외)이다.
  - 걷기 대사 배수는 1로 고정했다: c_move = 25(R−1)/21, c_rest = (21−4(R−1))/21.

## 1. 결론
- **PASS**: B1의 r2_5_ew0_5. 뛰기 배수 R 2.5, c_rest 15/21 = 0.7142857142857143, c_move 37.5/21 = 1.7857142857142858, e_walk 0.5. 대사 배수 [정지, 걷기, 뛰기] = [0.714, 1, 2.5].
  - 공통 규칙: Δ G_γ +0.329, t +2.65. 구간 보행은 정지·걷기·걷기·걷기다.
  - (a) 아사 비중 0.126, energy<0.5 비율 0.342. (b) 걷기 0.938. (c) 통과.
  - G_0.998은 Δ +0.727, t +3.63이다(보고만).
- **B0(R {2, 3.625, 6})는 세 팔 모두 실패했다.**
  - R 2와 R 3.625는 C2-seg가 C2 자체였다(WWWW, Δ 0).
  - R 6은 SSWW였지만 t +1.75였고, (a) 아사 비중 0.097 < 0.10이었다.
  - 기준 팔은 제안 팔이다. 통과 항목이 3개로 같아 동률 규칙으로 정했다. 그 팔은 공통 규칙만 실패했으므로 규칙 4로 B1 배수를 정했다.
- **B1(R {1.5, 2.5, 4.5}, e_walk 0.5)**:
  - R 2.5만 통과했다.
  - R 4.5는 공통 규칙을 통과했지만(t +3.82) (a) 아사 비중이 0.084였다.
  - R 1.5는 공통 규칙에서 t +0.81이었다.
  - 회차 선택 규칙(3.5)으로 r2_5_ew0_5를 골랐다. 보정은 1회(B1)만 썼고 B2는 돌리지 않았다.
- **통과의 내용은 "포식자가 가깝고 배고프면 멈춰 먹는다"이고, 뛰기가 아니다.**
  - 고른 팔의 C2-seg와 C2를 짝지은 t로 비교했다:
    - 아사율 −0.00010(t −2.64)
    - 번식 +0.74(t +2.12)
    - 수명 +12.6(t +1.53)
    - 피식률 +0.00001(t +0.16)
  - 여섯 팔 모두 C2와 C2-seg의 뛰기 비율이 0이다(B1 = 0). 포식자가 뛰기보다 느린 세계에서도 상수 탐색은 "가까우면 뛴다"를 고르지 않았다.
  - 그래서 이 게이트 통과는 계획서 1단계 S1("포식자가 다가오면 뛴다")의 근거가 아니다. B2(배고플 때 멈춰 먹기)와 맞바꿈 (a)·(b)의 근거다(4절).
- `configs/v2_1.yaml`의 c_rest·c_move를 고른 팔 값으로 바꿨다(PREREG 5절). gait_eat는 그대로다. config_digest가 a34de9ad4123에서 f068496361f9로 바뀌었다(`results/v2/e1/configs/B1_r2_5_ew0_5.yaml`과 같다).

## 2. 판정표
(`judge_e1b.md`와 같은 값이다. 보행 기호: S 정지, W 걷기, R 뛰기. 구간 순서: s0 가까움·배고픔, s1 가까움·배부름, s2 멂/안 보임·배고픔, s3 멂/안 보임·배부름.)

| 회차/팔 | 대사 배수 [정지, 걷기, 뛰기] | C2 speed (보행) | C2-seg 보행 s0~s3 | G_γ C2 → C2-seg (Δ, t) | 공통 | 아사 비중 | energy<0.5 | 걷기 | 아사율 걷기 / 뛰기 | G_0.998 Δ (t) | 판정 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 r2_ew0_5 | [0.810, 1, 2] | 0.436 (W) | W W W W | 1.483 → 1.483 (0, —) | 실패 (보행 같음) | 0.135 | 0.364 | 0.997 | 0.00038 / 0.00661 | 0 (—) | FAIL |
| B0 r3_625_ew0_5 | [0.5, 1, 3.625] | 0.482 (W) | W W W W | 1.670 → 1.670 (0, —) | 실패 (보행 같음) | 0.131 | 0.348 | 0.997 | 0.00038 / 0.01292 | 0 (—) | FAIL |
| B0 r6_ew0_5 | [0.048, 1, 6] | 0.390 (W) | S S W W | 1.608 → 1.919 (+0.311, +1.75) | 실패 | **0.097** | 0.321 | 0.821 | 0.00040 / 0.02225 | +0.618 (+1.39) | FAIL |
| B1 r1_5_ew0_5 | [0.905, 1, 1.5] | 0.443 (W) | S W W W | 1.663 → 1.806 (+0.143, +0.81) | 실패 | 0.112 | 0.348 | 0.938 | 0.00035 / 0.00486 | +0.707 (+1.67) | FAIL |
| **B1 r2_5_ew0_5** | [0.714, 1, 2.5] | 0.491 (W) | S W W W | 1.482 → 1.811 (+0.329, +2.65) | 통과 | 0.126 | 0.342 | 0.938 | 0.00043 / 0.00849 | +0.727 (+3.63) | **PASS** |
| B1 r4_5_ew0_5 | [0.333, 1, 4.5] | 0.554 (W) | S S W W | 1.620 → 2.129 (+0.509, +3.82) | 통과 | **0.084** | 0.306 | 0.824 | 0.00037 / 0.01642 | +1.162 (+3.25) | FAIL |

- (c)는 여섯 팔 모두 통과했다. 항상 걷기와 항상 뛰기의 아사율을 짝지은 t로 비교하면 −28.7에서 −116.1 사이다.
- G_0.998로만 통과하는 팔(3.6 갈래)은 없다.
- C2 조향 [forage, cohesion, flee_dist, cover]는 다음과 같다.
  - forage 0.61~0.98, cohesion 0.79~0.98, flee_dist 0.15~0.32, cover 0.01~0.04다.
  - C2 speed는 모두 걷기 띠(0.39~0.55) 안에 있다.
- 보조 지표(판정 아님, C2-seg):

| 팔 | 수명 C2 / C2-seg | 피식률 C2 / C2-seg | 번식 C2 / C2-seg | 정지 / 걷기 / 뛰기 | B1 | B2 | B8 (/초) |
|---|---|---|---|---|---|---|---|
| B0 r2_ew0_5 | 412.6 / 412.6 | 0.00244 / 0.00244 | 15.91 / 15.91 | 0.003 / 0.997 / 0 | 0 | 0 | 0.001 |
| B0 r3_625_ew0_5 | 424.9 / 424.9 | 0.00246 / 0.00246 | 16.45 / 16.45 | 0.003 / 0.997 / 0 | 0 | 0 | 0.001 |
| B0 r6_ew0_5 | 430.0 / 435.5 | 0.00239 / 0.00241 | 15.81 / 16.55 | 0.179 / 0.821 / 0 | 0 | −0.052 | 0.160 |
| B1 r1_5_ew0_5 | 422.8 / 432.2 | 0.00237 / 0.00239 | 16.12 / 16.56 | 0.062 / 0.938 / 0 | 0 | 0.146 | 0.058 |
| **B1 r2_5_ew0_5** | 421.7 / 434.2 | 0.00238 / 0.00239 | 15.63 / 16.37 | 0.062 / 0.938 / 0 | 0 | 0.148 | 0.056 |
| B1 r4_5_ew0_5 | 429.6 / 449.3 | 0.00238 / 0.00240 | 15.89 / 17.19 | 0.176 / 0.824 / 0 | 0 | −0.034 | 0.163 |

- B8은 모든 팔에서 0.5 이하다(10절 #3의 K 신호 없음).
- 고정 보행 3종(C2 조향 그대로)의 전체 표는 `judge_e1b.md`에 있다.
  - 항상 뛰기: G −5.2~−8.5, 수명 40~145, 아사 비중 0.73~0.91.
  - 항상 정지: G −0.13~−1.82.
  - 항상 걷기: C2와 같다.
  - 항상 뛰기의 피식률(0.0019~0.0026)은 항상 걷기(0.0024)와 큰 차이가 없다.

## 3. 보정 이력
| 회차 | 대상·값 | 이유 (사전 등록 4절) | 결과 |
|---|---|---|---|
| B0 | R {2, 3.625, 6}, e_walk 0.5 | E1-b 첫 회차. 팔은 R0와 같고 세계만 다르다(PREREG E1-b 변경 기록) | 3팔 실패. 기준 팔 = 제안 팔(통과 3개, R 2와 동률이라 제안 배수 우선). 실패는 공통 규칙뿐(C2-seg = C2) |
| B1 | R {1.5, 2.5, 4.5}, e_walk 0.5 | 규칙 4: 공통 규칙만 실패하면 e_walk는 그대로 두고 배수를 바꾼다. B0와 계수가 달라 반복 멈춤에 걸리지 않는다 | r2_5_ew0_5 통과(4개 모두). 회차 선택 → PASS. 여기서 멈춘다(3.5) |
| B2 | 돌리지 않음 | B1에서 통과 | — |

- E1-b의 보정 예산은 새로 셌다(최대 2회, PREREG E1-b 변경 기록). 그중 1회를 썼다.

## 4. 해석 (판정이 아니다)

### 4.1 E1과 같은 계수끼리 비교 (세계만 다름)

| R | E1 C2 G / 피식률 / 아사 비중 | E1 C2-seg (Δ, t, 아사 비중) | E1-b C2 G / 피식률 / 아사 비중 | E1-b C2-seg (Δ, t, 아사 비중) |
|---|---|---|---|---|
| 1.5 | 1.502 / 0.00272 / 0.111 | WWWW (0, —, 0.111) | 1.663 / 0.00237 / 0.120 | SWWW (+0.143, +0.81, 0.112) |
| 2 | 1.421 / 0.00270 / 0.118 | SWWW (+0.138, +1.54, 0.111) | 1.483 / 0.00244 / 0.135 | WWWW (0, —, 0.135) |
| 2.5 | 1.422 / 0.00275 / 0.115 | SSWW (+0.215, +2.02, 0.095) | 1.482 / 0.00238 / 0.152 | SWWW (+0.329, +2.65, 0.126) |
| 3.625 | 1.378 / 0.00280 / 0.112 | WWWW (0, —, 0.112) | 1.670 / 0.00246 / 0.131 | WWWW (0, —, 0.131) |
| 4.5 | 1.466 / 0.00277 / 0.115 | SWWW (+0.207, +1.49, 0.092) | 1.620 / 0.00238 / 0.128 | SSWW (+0.509, +3.82, 0.084) |
| 6 | 1.321 / 0.00288 / 0.111 | SWWW (+0.337, +2.89, 0.083) | 1.608 / 0.00239 / 0.140 | SSWW (+0.311, +1.75, 0.097) |

1. 포식자가 느려지자 걷는 C2의 피식률이 0.0027~0.0029에서 0.0024~0.0025로 약 12% 내려갔다. C2의 G_γ도 올랐고, 사망 가운데 아사의 비중이 0.11~0.12에서 0.12~0.15로 커졌다. (a) 아래쪽 경계에서 조금 멀어진 것이 R 2.5 통과의 한 이유다. E1 R1의 R 2.5는 t +2.02, 아사 비중 0.095로 두 항목 모두 경계 바로 밖에서 실패했다.
2. 상태 의존은 E1과 같은 종류다. C2-seg가 쓰는 것은 "가까운 구간에서 정지"(SWWW 또는 SSWW)뿐이다. 이득은 아사가 줄고 번식이 느는 데서 온다. 피식은 줄지 않았다(고른 팔 t +0.16). 정지 섭식 배수 1.0이 걷기 0.5의 두 배라 "멈춰 먹기"가 에너지를 번다. 그 구간이 "포식자 가까움"인 이유는 이번 측정만으로 가를 수 없다.
3. 뛰기는 E1-b에서도 상수 해로 나오지 않았다.
   - C2-seg TPE가 시도한 보행 패턴은 81가지 가운데 22~30가지다.
   - 가까운 구간(s0·s1)에 뛰기를 둔 패턴은 팔마다 6~11가지를 시도했다.
     - B0 세 팔과 B1의 R 2.5·4.5에서는 그런 패턴의 최고 탐색 점수가 WWWW보다 낮았다.
     - B1의 R 1.5에서는 SRWW(가깝고 배부르면 뛰기)가 1.539로 WWWW 1.420보다 높았다. 다만 SWWW 1.719보다는 낮았다.
   - RRWW(가까우면 뛰기)는 어느 팔에서도 시도되지 않았다.
   - C2-seg는 조향(flee_dist 0.15~0.32)을 C2에서 물려받는다. 그래서 "뛰어 도망"의 값은 이 게이트에서 낮게 잡힐 수 있다. `report.md` 4절 참고 시험에서는 flee_dist 0.5에서도 E1 세계의 집단 이득이 없었다.
   - 소수 침입 시험(`report.md` 8절)의 개체 이득(×0.6~0.95, flee_dist 0.5, 피식 −23%)은 집단 상수 비교에서는 나타나지 않았다.
4. 고른 팔의 C2-seg 표(0.315, 0.364, 0.570, 0.439)는 TPE 시작 무작위 표본(trial 13)이다.
   - TPE 시드가 0으로 같고, 앞 묶음 두 개(trial 0~13)는 완료 trial이 10개 미만일 때 뽑힌다. 그래서 같은 값이 E1 R0 r2·r6, R1 r4.5, E1-b B1 r1.5·r2.5에 똑같이 나온다.
   - 보행 띠 안의 값은 행동이 같으므로, 이 표는 패턴 SWWW 하나를 뜻한다.
5. 통과 여유가 작다.
   - t +2.65는 기준 2.093을 넘는다. 사전 등록대로 다중 비교 보정은 하지 않았다.
   - 참고로 본페로니 보정을 적용한 임계값(자유도 19)은 다음과 같다. 판정에는 쓰지 않는다.
     - B1 팔 3개: 2.625. 겨우 넘는다.
     - E1-b 팔 6개: 2.944. 넘지 못한다.
     - E1·E1-b 팔 12개: 3.255. 넘지 못한다.
   - 고른 팔의 C2 G_γ(1.482)는 E1-b C2 가운데 낮은 편이다(다른 팔 1.48~1.67). 팔마다 계수가 달라 직접 비교할 수는 없지만, C2 탐색의 편차가 Δ에 섞였을 수 있다.
6. 평가 시드가 완전히 독립이지 않다(PREREG E1-b 한계 (1)). 범위를 고른 근거 시험이 평가 시드 10000~10019를 썼다.
7. R 2.5에서는 c_rest/c_move = 0.4다. 그래서 걷기와 뛰기의 거리당 대사가 같다(1/0.4 = 2.5/1). 거리당 비용이 가장 낮은 속도는 √0.4 ≈ 0.63·herb_speed로 걷기와 뛰기 사이에 있다. 제안값 R 3.625에서는 그 속도가 걷기와 같았다. 따라서 v2.1에서 뛰기의 비용은 대사보다 섭식 0(뛰는 동안 못 먹음)에서 주로 온다.

## 5. 최종 계수와 바꾼 파일
- `configs/v2_1.yaml`
  - `c_rest: 0.7142857142857143`, `c_move: 1.7857142857142858`로 바꿨다(전에는 0.5, 3.125). `gait_eat [1.0, 0.5, 0.0]`, 문턱, 속력, overrides는 그대로다.
  - 머리 주석과 speed 주석에 날짜, 이유, 회차, 결과 경로를 적었다.
  - config_digest는 a34de9ad4123에서 f068496361f9로 바뀌었다. `configs/v2.yaml`은 ab330a9b27fd 그대로다.
- `AdaptiveEcosystem/Docs/RL_Policy/RL_V2_PLAN.md`
  - 4.4 계수 문구 뒤에 "10-02 변경(Gate E1-b 통과)"을 더했다(v2_1.yaml 머리 주석의 규칙).
  - 1단계 표 1-2 행의 상태를 "E1 실패 → E1-b 통과"로 바꾸고 결과 한 문장을 더했다. 1-3의 비교 대상 C2-seg가 이 팔의 것이라는 점도 적었다.
- `results/v2/e1/PREREG.md` 변경 기록 2건
  - B0 판정 뒤, B1 결과 보기 전: B1 계수를 규칙 4로 정했다.
  - B1 판정 뒤: PASS, 선택, v2_1.yaml 반영, 테스트 수정.
- 테스트
  - `tests/test_gate_e1.py`
    - 바꾼 것: 제안값 검사는 B0 제안 팔 설정으로 옮겼다. 설정 보호 장치 테스트는 B0 run.json의 digest와 기록된 B0 설정 파일 내용을 비교한다.
    - 새 테스트 2개:
      - `test_v2_1_has_gate_e1b_selected_coefficients`: v2_1.yaml = metabolism(2.5) = judge_e1b.json의 최종 팔 = B1 r2_5 run.json digest.
      - `test_existing_e1b_results_unchanged`: judge_e1b.md를 다시 만들어도 한 글자도 같다. 회차는 B0·B1이다.
  - `tests/test_speed_v2.py`: 대사 배수 기대값을 `DRAIN_MULT = (15/21, 1, 2.5)` 하나로 모았다. 바꾼 곳은 3곳이다.
  - pytest: 378 통과 + 1 skip(준비 단계 376 + 새 2).
- v1 파일(`configs/default.yaml`, `env/*`)은 바꾸지 않았다. E1의 R0·R1 결과와 설정은 덮지 않았다. `gate_e1.py`도 이번 단계에서는 바꾸지 않았다.

## 6. 사람이 볼 것
1. **S1(위협 의존 뛰기)의 근거가 아직 없다.** E1-b 통과는 "가깝고 배고프면 정지"(B2 쪽)로 났고, B1 = 0이다. 1-3에서 PPO가 조향과 보행을 함께 바꾸면 상수 해와 다를 수 있다. 다만 이 게이트는 "뛰기 상태 의존 해가 있다"를 보이지 못했다. 이 문제를 1-3 결과를 보고 다룰지, 지금 다룰지 정해야 한다. 지금 다룬다면 `report.md` 6절의 선택지가 그대로 남아 있다(도주 분기 뛰기 강제 #2, C2-seg에 flee_dist 구간화).
2. 통과 여유가 작다(t 2.65, 4절 5). 같은 TPE 시드로 다시 돌리면 같은 결과가 나온다(결정적). 다른 TPE 시드로 재현되는지는 재지 않았다.
3. 1-3 완료 기준 "C0이 E1의 C2-seg보다 유의하게 낮지 않다"의 비교 대상은 이 팔의 C2-seg다(PREREG 5절). G_γ는 1.811(평가 시드 10000~10019 × 5000스텝, 결정 모드)이고, 표는 `B1/r2_5_ew0_5/constsearch_seg.json`에 있다.
4. 언리얼 정책 테스트 레벨의 `PredatorSpeedRatio`(기본 1.0)는 V2a 이식 때 [0.6, 0.95] 안으로 맞춘다(계획서 7.2, 기존 항목).

## 7. 산출물
- `results/v2/e1/judge_e1b.md`, `judge_e1b.json`: E1-b 자동 판정표.
- `results/v2/e1/configs/B0_*.yaml`, `B1_*.yaml`: 팔 설정. `B1_r2_5_ew0_5`는 지금 `configs/v2_1.yaml`과 같은 설정이다. `B0_r3_625_ew0_5`는 바꾸기 전 v2_1.yaml과 같다.
- `results/v2/e1/B0/<팔>/`, `B1/<팔>/`: constsearch(C2), constsearch_seg(C2-seg), fixed_stop·walk·run, g998/c2seg_g998 각각의 `.json`·`.md`. `run.json`에 명령 전문, 소요 시간, 종료 코드가 있고, `run.log`에 진행 로그가 있다.
- 소요 시간: 팔 하나 36.1~36.8분. 세 팔을 동시에 돌려(워커 6 × 3) 회차 하나가 약 37분이었다.

## 8. 명령 전문

실행 순서(Git Bash, 작업 디렉터리 `herbivore_rl/`):

```bash
python -m pytest -q                                                   # 376 passed, 1 skipped (실행 전)
python gate_e1.py configs --round B0 --run-mult 2 3.625 6 --walk-eat 0.5
python -u gate_e1.py run --round B0 --arm r2_ew0_5 --workers 6 &
python -u gate_e1.py run --round B0 --arm r3_625_ew0_5 --workers 6 &
python -u gate_e1.py run --round B0 --arm r6_ew0_5 --workers 6 &
wait
python gate_e1.py judge --attempt E1-b                                # B0 FAIL → 다음: calibrate R [1.5, 2.5, 4.5], e_walk 0.5
python gate_e1.py configs --round B1 --run-mult 1.5 2.5 4.5 --walk-eat 0.5
python -u gate_e1.py run --round B1 --arm r1_5_ew0_5 --workers 6 &
python -u gate_e1.py run --round B1 --arm r2_5_ew0_5 --workers 6 &
python -u gate_e1.py run --round B1 --arm r4_5_ew0_5 --workers 6 &
wait
python gate_e1.py judge --attempt E1-b                                # B1 r2_5_ew0_5 PASS
# configs/v2_1.yaml 의 c_rest·c_move 반영, 테스트 수정 뒤
python -m pytest -q                                                   # 378 passed, 1 skipped
```

팔마다 `gate_e1.py run`이 부른 명령(각 `run.json`의 `steps[].command`를 그대로 옮겼다):

`B0/r2_ew0_5` (config_digest 6b282600cc91, 합 36.6분, 종료 코드 모두 0):

```bash
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r2_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r2_ew0_5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.1667 --enqueue 0.4207 0.8656 0.1054 0.0044 0.5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.8333 --enqueue 0.39 0.99 0.92 0.15 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r2_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r2_ew0_5 --seg-bins 2:0.5 4:0.5 --seg-dims speed
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r2_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r2_ew0_5 --tag fixed_stop --const-action 0.7203765843296412 0.7993797902071986 0.21365336570539406 0.03999742564062034 0.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r2_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r2_ew0_5 --tag fixed_walk --const-action 0.7203765843296412 0.7993797902071986 0.21365336570539406 0.03999742564062034 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r2_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r2_ew0_5 --tag fixed_run --const-action 0.7203765843296412 0.7993797902071986 0.21365336570539406 0.03999742564062034 1.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r2_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r2_ew0_5/g998 --tag c2seg_g998 --g998 --seg-bins 2:0.5 4:0.5 --seg-dims speed --base-action 0.7203765843296412 0.7993797902071986 0.21365336570539406 0.03999742564062034 0.4359374074031739 --const-action 0.4359374074031739 0.4359374074031739 0.4359374074031739 0.4359374074031739
```

`B0/r3_625_ew0_5` (config_digest a34de9ad4123, 합 36.6분, 종료 코드 모두 0):

```bash
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r3_625_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r3_625_ew0_5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.1667 --enqueue 0.4207 0.8656 0.1054 0.0044 0.5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.8333 --enqueue 0.39 0.99 0.92 0.15 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r3_625_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r3_625_ew0_5 --seg-bins 2:0.5 4:0.5 --seg-dims speed
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r3_625_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r3_625_ew0_5 --tag fixed_stop --const-action 0.8340684589740917 0.8673857905072123 0.15276665904833553 0.02957586353414975 0.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r3_625_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r3_625_ew0_5 --tag fixed_walk --const-action 0.8340684589740917 0.8673857905072123 0.15276665904833553 0.02957586353414975 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r3_625_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r3_625_ew0_5 --tag fixed_run --const-action 0.8340684589740917 0.8673857905072123 0.15276665904833553 0.02957586353414975 1.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r3_625_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r3_625_ew0_5/g998 --tag c2seg_g998 --g998 --seg-bins 2:0.5 4:0.5 --seg-dims speed --base-action 0.8340684589740917 0.8673857905072123 0.15276665904833553 0.02957586353414975 0.4822761677310872 --const-action 0.4822761677310872 0.4822761677310872 0.4822761677310872 0.4822761677310872
```

`B0/r6_ew0_5` (config_digest 8ec55cdd72d4, 합 36.8분, 종료 코드 모두 0):

```bash
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r6_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r6_ew0_5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.1667 --enqueue 0.4207 0.8656 0.1054 0.0044 0.5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.8333 --enqueue 0.39 0.99 0.92 0.15 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r6_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r6_ew0_5 --seg-bins 2:0.5 4:0.5 --seg-dims speed
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r6_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r6_ew0_5 --tag fixed_stop --const-action 0.9814966727581358 0.9779505025866796 0.16563769972771386 0.011169712487204282 0.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r6_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r6_ew0_5 --tag fixed_walk --const-action 0.9814966727581358 0.9779505025866796 0.16563769972771386 0.011169712487204282 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r6_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r6_ew0_5 --tag fixed_run --const-action 0.9814966727581358 0.9779505025866796 0.16563769972771386 0.011169712487204282 1.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B0_r6_ew0_5.yaml --workers 6 --out results/v2/e1/B0/r6_ew0_5/g998 --tag c2seg_g998 --g998 --seg-bins 2:0.5 4:0.5 --seg-dims speed --base-action 0.9814966727581358 0.9779505025866796 0.16563769972771386 0.011169712487204282 0.39011859094031115 --const-action 0.323450576775678 0.21578654236890715 0.4514306676665461 0.5300479260087613
```

`B1/r1_5_ew0_5` (config_digest e12537e77bde, 합 36.1분, 종료 코드 모두 0):

```bash
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r1_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r1_5_ew0_5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.1667 --enqueue 0.4207 0.8656 0.1054 0.0044 0.5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.8333 --enqueue 0.39 0.99 0.92 0.15 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r1_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r1_5_ew0_5 --seg-bins 2:0.5 4:0.5 --seg-dims speed
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r1_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r1_5_ew0_5 --tag fixed_stop --const-action 0.608491755868374 0.8528914663102306 0.3186928974608414 0.017043635014859893 0.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r1_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r1_5_ew0_5 --tag fixed_walk --const-action 0.608491755868374 0.8528914663102306 0.3186928974608414 0.017043635014859893 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r1_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r1_5_ew0_5 --tag fixed_run --const-action 0.608491755868374 0.8528914663102306 0.3186928974608414 0.017043635014859893 1.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r1_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r1_5_ew0_5/g998 --tag c2seg_g998 --g998 --seg-bins 2:0.5 4:0.5 --seg-dims speed --base-action 0.608491755868374 0.8528914663102306 0.3186928974608414 0.017043635014859893 0.4434717061343869 --const-action 0.31542835092418386 0.3637107709426226 0.5701967704178796 0.43860151346232035
```

`B1/r2_5_ew0_5` (config_digest f068496361f9, 합 36.4분, 종료 코드 모두 0):

```bash
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r2_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r2_5_ew0_5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.1667 --enqueue 0.4207 0.8656 0.1054 0.0044 0.5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.8333 --enqueue 0.39 0.99 0.92 0.15 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r2_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r2_5_ew0_5 --seg-bins 2:0.5 4:0.5 --seg-dims speed
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r2_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r2_5_ew0_5 --tag fixed_stop --const-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r2_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r2_5_ew0_5 --tag fixed_walk --const-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r2_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r2_5_ew0_5 --tag fixed_run --const-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 1.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r2_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r2_5_ew0_5/g998 --tag c2seg_g998 --g998 --seg-bins 2:0.5 4:0.5 --seg-dims speed --base-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 --const-action 0.31542835092418386 0.3637107709426226 0.5701967704178796 0.43860151346232035
```

`B1/r4_5_ew0_5` (config_digest 94d95aa0f1c5, 합 36.3분, 종료 코드 모두 0):

```bash
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r4_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r4_5_ew0_5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.1667 --enqueue 0.4207 0.8656 0.1054 0.0044 0.5 --enqueue 0.4207 0.8656 0.1054 0.0044 0.8333 --enqueue 0.39 0.99 0.92 0.15 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r4_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r4_5_ew0_5 --seg-bins 2:0.5 4:0.5 --seg-dims speed
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r4_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r4_5_ew0_5 --tag fixed_stop --const-action 0.7682948980991011 0.9216841923808368 0.2159122493787158 0.020698426383369828 0.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r4_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r4_5_ew0_5 --tag fixed_walk --const-action 0.7682948980991011 0.9216841923808368 0.2159122493787158 0.020698426383369828 0.5
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r4_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r4_5_ew0_5 --tag fixed_run --const-action 0.7682948980991011 0.9216841923808368 0.2159122493787158 0.020698426383369828 1.0
python diagnose_v2.py constsearch --config results/v2/e1/configs/B1_r4_5_ew0_5.yaml --workers 6 --out results/v2/e1/B1/r4_5_ew0_5/g998 --tag c2seg_g998 --g998 --seg-bins 2:0.5 4:0.5 --seg-dims speed --base-action 0.7682948980991011 0.9216841923808368 0.2159122493787158 0.020698426383369828 0.5536489064824605 --const-action 0.10233105379346588 0.2076082497126884 0.6340997197455132 0.4116220874825391
```
