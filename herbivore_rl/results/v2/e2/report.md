# Gate E2 보고서 (1-5, v2.2 경계·threat_recency)

- 2026-10-03 (토). 사전 등록 `results/v2/e2/PREREG.md`(결과 보기 전 작성), 판정표 `results/v2/e2/judge_e2.md`(+ `.json`), 도구 `gate_e2.py`, 테스트 `tests/test_gate_e2.py`.
- **결론: E2a PASS, E2b PASS (회차 V0, 보정 없음).** threat_recency 감쇠는 0.95(제안값, 반감기 13.5스텝), '최근 위협' 문턱 θ는 0.5로 고정했다. 그래서 포식자를 놓친 뒤 13스텝까지가 '최근 위협'이다. `configs/v2_2.yaml`의 값은 그대로다(통과 주석만 더함).

## 1. 무엇을 쟀나

- 세계: `configs/v2_2.yaml`(v2.1 + vigilance: 포식자 ×0.6~0.95, speed는 E1-b 계수, v1 먹이). 후보마다 vigilance.decay만 바꾼 사본(`results/v2/e2/configs/V0_d0_*.yaml`)을 썼다.
- 구간: 관측 7의 문턱 [θ, 1]로 나눈다. s0 평시(tr < 0.5), s1 최근 위협·안 보임(0.5 ≤ tr < 1), s2 포식자 보임(tr = 1). 포식자가 보이면 tr = 1이므로 'tr ≥ 1'은 '보임'과 같다(테스트로 고정). C2-seg에게 decay는 창 K(6/13/27스텝)로만 보인다.
- C2: 6차원, TPE 112 trial. C2는 감쇠와 무관하므로 회차에 한 번만 찾았다. 고른 값은 E1-b의 C2 + vigilance 0.25 = [0.971, 0.785, 0.218, 0.034, 0.491, 0.25]이고 G_γ 1.482다. E1-b C2의 평가 G_γ와 비트 단위로 같아서, 경계를 쓰지 않는 v2.2 세계가 v2.1과 같다는 것을 결과로도 확인했다.
- E2a 판정 갈래 A(5.0 문자 그대로): 구간별 vigilance + 바탕 C2 대 C2(vigilance 0). 기준은 (i) Δ G_γ > 0이고 t > 2.093, (ii) 구간별 경계 상태가 둘 이상, (iii) 경계 비율 0.01~0.5.
- E2a 갈래 B(멈춤 조건): 구간별 speed+vigilance 대 구간별 speed(vigilance 0).
- E2b: 보이면 뛰며 도주(flee_dist 1.0), 평시는 C2 보행으로 둔다. '최근 위협' 구간에서만 경계(V)와 계속 뛰기(R)를 바꾼다. V가 G_γ에서 유의하게 높고 피식률에서 유의하게 낮아야 통과다.
- #18 보고 팔: R을 threat_flee 1 사본에서 잰다(R18). 항은 flee_weight·threat_recency·(−ThreatDir)이고, 포식자가 안 보일 때 조향 합에 더한다.

## 2. 판정 표 (평가 시드 10000~10019 × 5000스텝, 짝지은 t, 기준 2.093)

### E2a 갈래 A (판정)

| 후보 | 반감기 (K) | 구간별 경계 [평시·최근·보임] (값) | G_γ 금지 → 허용 (Δ, t) | (i) | (ii) | 경계 비율 | (iii) | G_0.998 Δ (t) | 판정 |
|---|---|---|---|---|---|---|---|---|---|
| d0_9 | 6.6 (6) | —·경계·— (0.12, 0.64, 0.14) | 1.482 → 1.799 (+0.317, +2.08) | 실패 | 통과 | 0.147 | 통과 | +1.152 (+3.68) | FAIL |
| d0_95 | 13.5 (13) | —·경계·— (0.12, 0.64, 0.14) | 1.482 → 1.952 (+0.470, +3.93) | 통과 | 통과 | 0.161 | 통과 | +1.616 (+6.22) | **PASS** |
| d0_975 | 27.4 (27) | —·—·— (C2 그대로) | 1.482 → 1.482 (0, nan) | 실패 | 실패 | 0.000 | 실패 | 0 | FAIL |

- 선택 규칙(제안값 먼저)으로 d0_95를 골랐다. 0.998 갈래(γ_train만 실패)는 d0_9에 해당하지 않는다. d0_9는 0.998에서는 통과하지만 A가 이미 d0_95로 통과했으므로 규칙상 의미가 없다.
- d0_95 결과 지표(금지 → 허용, t):
  - 수명 421.7 → 458.2 (+3.82)
  - 아사율 0.00043 → 0.00030 (−3.11)
  - 피식률 0.00238 → 0.00230 (−1.41, 유의 아님)
  - 번식 15.63 → 16.31 (+1.77, 유의 아님)
- 이득은 평가 시드에서는 주로 아사가 줄고 수명이 느는 쪽에서 왔다.

### E2a 갈래 B (보고·멈춤 조건)

- 세 후보 모두 B-금지와 B-허용이 C2 자체(걷기 ×3, 경계 끔)라 Δ 0으로 실패했다.
- B-금지: 구간별 보행을 허용해도 TPE가 상태 의존 보행을 찾지 못했다. 재측정 상위 5개가 모두 걷기와 같은 값이다.
- B-허용: 6차원 TPE가 A의 해(최근 위협에서만 경계)를 찾지 못했다(77/112 시점에도 C2). 탐색력의 한계라 B는 정보가 없다. A가 통과했으므로 판정에는 영향이 없다(PREREG 3.2).

### E2b (판정은 d0_95)

| 후보 | G_γ R → V (Δ, t) | 피식률 R → V (Δ, t) | 수명 R → V | 아사율 R → V | G_0.998 Δ (t) | 판정 |
|---|---|---|---|---|---|---|
| d0_9 | −0.954 → −0.541 (+0.413, +2.43) | 0.00185 → 0.00117 (−0.00068, −8.95) | 315.5 → 386.8 | 0.00226 → 0.00196 | +0.060 (+0.16) | PASS |
| d0_95 | −1.509 → −0.550 (+0.959, +5.53) | 0.00173 → 0.00116 (−0.00057, −9.16) | 277.2 → 386.1 | 0.00280 → 0.00196 | +1.142 (+3.94) | **PASS** |
| d0_975 | −1.795 → −0.821 (+0.974, +4.84) | 0.00165 → 0.00115 (−0.00050, −8.21) | 264.8 → 371.8 | 0.00326 → 0.00207 | +1.316 (+4.37) | PASS |

- 두 팔 모두 G_γ가 음수다. '보이면 늘 뛰며 도주'라는 손으로 만든 짝은 상수로 보면 비싸다. E2b는 그 짝 안에서 S2 전제(놓친 뒤 멈춰 보기 대 계속 뛰기)를 직접 비교한 것이다.
- 보고용 E2b-표(B-허용 표 = C2 위에서 최근 구간만 경계 대 뛰기): 0.95에서 G_γ 0.942 → 1.952 (+1.010, t +6.32)이고, 피식률 차는 유의하지 않다(−0.00005, t −1.06).

### #18 (보고, 판정 아님)

| 후보 | R18 G_γ | R18 − V G_γ (t) | R18 − R G_γ (t) | R18 − V 피식률 (t) | 크게 이김 |
|---|---|---|---|---|---|
| d0_9 | 0.057 | +0.598 (+3.85) | +1.011 (+6.53) | +0.00023 (+6.17) | 예 |
| d0_95 | −0.360 | +0.189 (+1.84) | +1.148 (+8.13) | +0.00007 (+2.87) | 아니오 |
| d0_975 | −0.885 | −0.064 (−0.45) | +0.910 (+4.81) | −0.00010 (−3.85) | 아니오 |

- 위협 반대 항은 계속 뛰기를 크게 개선한다. 그러나 고른 후보 0.95에서는 경계를 유의하게 넘지 못한다.
- 0.9에서 경계보다 G_γ가 높을 때는 피식률이 오히려 높다.
- 조향 계약 변경안에 올릴지는 사람이 정한다(#18). 추천: 지금은 올리지 않는다.

## 3. 보정 이력

- 없음. V0에서 A가 통과해 V1(경계 섭식 0.5)과 V2(+ 경계 반경 ×1.5, 미구현)는 돌리지 않았다. 사전 등록 변경도 없다(변경 기록은 도구 시험과 V0 판정 기록뿐).

## 4. 최종 계수 (`configs/v2_2.yaml`, config_digest efc8f775f1e1 = `results/v2/e2/configs/V0_d0_95.yaml`)

- vigilance: threshold 0.5, **decay 0.95**, eat_mult 0.0, fov_deg 360.0, threat_flee 0.0
- θ = 0.5 (`env_v2/world.py` RECENT_THREAT = `gate_e2.THETA`)
- 나머지(speed, overrides, train, init_action_bias −0.84)는 그대로다.
- 1-6 비교 대상(E2 C2-seg)은 d0_95 A-허용이다: 바탕 C2, 구간별 vigilance [0.1183, 0.6399, 0.1434], 평가 G_γ 1.952.

## 5. 사전 등록 밖 탐색 (판정에 쓰지 않음, 보정 시드 100~119 × 3000, `results/v2/e2/explore/`)

| 비교 | Δ G_γ (t) | Δ 피식률 (t) | Δ 수명 (t) |
|---|---|---|---|
| A-허용 − C2 | +0.181 (+1.79) | −0.00019 (−4.01) | +19.1 (+2.41) |
| A-허용 − 최근 구간에서 정지(경계 아님, 먹음, 120°) | +0.215 (+1.87) | −0.00020 (−4.39) | +28.3 (+3.63) |
| 정지 − C2 | −0.033 (−0.30) | +0.00001 (+0.21) | −9.3 (−1.44) |
| A-허용 − A-허용(경계 시야 120° 사본) | −0.085 (−0.69) | −0.00003 (−0.89) | −4.3 (−0.58) |
| A-허용(120°) − C2 | +0.267 (+2.69) | −0.00016 (−2.72) | +23.4 (+3.68) |
| A-허용(경계 섭식 1.0 사본) − A-허용 | +0.110 (+1.17) | −0.00001 (−0.48) | +11.6 (+1.52) |

- 이득은 멈춤 자체에서 오지 않는다. 경계 없이 멈추면 먹어도 이득이 없다.
- 360° 시야에서 오는 것도 아니다. 시야 120° 사본도 같은 이득이다.
- 남는 차이는 '위협 쪽으로 돌아보기(ThreatDir heading)'다. 다음 120° 관측에서 포식자를 다시 찾게 해 '보임' 구간이 0.28 → 0.40으로 는다. 계획서 4.4의 "'위협 쪽 보기'는 연출이다"는 경계 스텝의 360° 탐지에 대해서만 맞고, 경계를 푼 뒤의 120° 재탐지에는 맞지 않는다.
- 언리얼 이식(V2a) 때 Facing 쓰기 순서가 행동에 영향을 준다는 뜻이다.
- 경계의 섭식 손실은 작다(섭식 1.0으로 둬도 차가 유의하지 않다).
- 결과 지표의 경로는 시드 집합마다 다르다(평가 시드는 아사·수명, 보정 시드는 피식률). 판정 양은 G_γ다.

## 6. 한계와 사람 결정 거리

- 상수 탐색은 TPE 시드 하나이고, 평가 시드 20개의 짝지은 t만 쓴다. 후보 3개의 다중 비교를 보정하지 않았다(규칙은 사전 등록).
- 고른 것은 'K = 13 창'이다. 연속값 threat_recency의 쓸모는 1-6 C4-threat로 본다.
- 갈래 B는 TPE가 A의 해를 못 찾아 정보가 없다. '경계 + 상태 의존 보행'은 E2b와 학습(1-6)이 본다.
- E2b는 손으로 만든 짝이다(두 팔 모두 G_γ < 0).
- 경계 지표는 360° 경계 지속으로 치우친다. 판정에는 경계 비율만 썼다.
- v1 먹이 위의 값이다. v2.3에서 먹이 2층을 넣으면 경계의 섭식 비용이 달라질 수 있다.
- 사람 결정:
  - (1) #18 항을 조향 계약 변경안에 올릴지(추천: 보류)
  - (2) 5절의 '위협 쪽 보기' 발견을 계획서 4.4와 V2a 안건에 반영할지
  - (3) E2b가 통과했으므로 B3를 1차로 유지한다. 1차 정의(b3_narrow / b3_truth / C4[1,2,7] 대비)는 1-6 사전 등록에서 정한다.

## 7. 바꾼 파일

- 새 파일: `gate_e2.py`, `tests/test_gate_e2.py`(19개), `results/v2/e2/`(PREREG.md, configs/, V0/, judge_e2.md·json, explore/)
- 결과 보기 전, #18 변형용으로 바꾼 것:
  - `env_v2/world.py`: `_threat_flee_term`, `_vigil_params`의 threat_flee
  - `env_v2/steering.py`: `steer(extra=None)`. None이면 계약 조향과 같은 줄
  - `env_v2/features.py`: PARAM_KEYS에 `threat_flee`
  - `replay_v2.py`: 설명줄
  - `configs/v2_2.yaml`: `threat_flee: 0.0`
  - `tests/test_vigilance_v2.py`: 6개 추가
- 결과 뒤: `configs/v2_2.yaml` 통과 주석, `env_v2/world.py` RECENT_THREAT 주석, 계획서 머리말·4.2 idx 7·1-4·1-5 행
- v1 파일, 언리얼 C++, 기존 결과·체크포인트·캐시는 바꾸지 않았다.

## 8. 검증

- `python -m pytest -q`: 466 통과 + 1 skip. threat_flee 0이면 항을 만들지 않고 steer(None)이 계약 조향과 같다.
- 후보 설정은 decay·eat_mult·threat_flee만 다르다.
- 상수의 세계가 감쇠와 무관하다. A-금지가 세 후보에서 C2와 비트 단위로 같았다(판정표 구성 검사).
- 도구 시험(scratchpad `--smoke`)으로 명령 순서와 판정표를 확인했다.
- 실행 시간: C2 406초(워커 18), 후보마다 약 4620초(워커 6, 세 후보 동시).

## 9. 명령 전문 (작업 디렉터리 `herbivore_rl/`)

python -m pytest -q
python gate_e2.py configs --round V0
python -u gate_e2.py run --round V0 --c2 --workers 18
python -u gate_e2.py run --round V0 --cand d0_9 --workers 6 &
python -u gate_e2.py run --round V0 --cand d0_95 --workers 6 &
python -u gate_e2.py run --round V0 --cand d0_975 --workers 6 &
wait
python gate_e2.py judge
PYTHONPATH=. python results/v2/e2/explore/mechanism.py > results/v2/e2/explore/mechanism.txt

`run`이 부른 diagnose 명령(d0_95. 다른 후보는 설정·출력 경로만 다르고, 표 값은 각 run.json에 있다):

python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 18 --out results/v2/e2/V0/c2 --enqueue 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.25 --enqueue 0.4207 0.8656 0.1054 0.0044 0.5 0.25 --enqueue 0.39 0.99 0.92 0.15 0.5 0.25
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95 --tag a_forbid --const-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.0
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95 --tag a_allow --seg-bins threat_recency:0.5,1 --seg-dims vigilance --base-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.25
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95 --tag b_forbid --seg-bins threat_recency:0.5,1 --seg-dims speed --base-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.0
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95 --tag b_allow --seg-bins threat_recency:0.5,1 --seg-dims speed vigilance --base-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.25 --enqueue 0.4913744307309694 0.25 0.4913744307309694 0.25 0.4913744307309694 0.25 --enqueue 0.4913744307309694 0.25 0.4913744307309694 0.25 0.4913744307309694 0.25
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95 --tag e2b_vig --seg-bins threat_recency:0.5,1 --seg-dims speed vigilance --base-action 0.9709889334578663 0.7849404966375042 1.0 0.03358694847233987 0.4913744307309694 0.0 --const-action 0.4913744307309694 0.0 0.4913744307309694 1.0 1.0 0.0
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95 --tag e2b_run --seg-bins threat_recency:0.5,1 --seg-dims speed vigilance --base-action 0.9709889334578663 0.7849404966375042 1.0 0.03358694847233987 0.4913744307309694 0.0 --const-action 0.4913744307309694 0.0 1.0 0.0 1.0 0.0
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95_tf1.yaml --workers 6 --out results/v2/e2/V0/d0_95/tf --tag e2b_run18 --seg-bins threat_recency:0.5,1 --seg-dims speed vigilance --base-action 0.9709889334578663 0.7849404966375042 1.0 0.03358694847233987 0.4913744307309694 0.0 --const-action 0.4913744307309694 0.0 1.0 0.0 1.0 0.0
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95 --tag e2b_tab_vig --seg-bins threat_recency:0.5,1 --seg-dims speed vigilance --base-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.25 --const-action 0.4913744307309694 0.25 0.4913744307309694 1.0 0.4913744307309694 0.25
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95 --tag e2b_tab_run --seg-bins threat_recency:0.5,1 --seg-dims speed vigilance --base-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.25 --const-action 0.4913744307309694 0.25 1.0 0.0 0.4913744307309694 0.25
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95/g998 --tag a_forbid --g998 --const-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.0
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95/g998 --tag a_allow --g998 --seg-bins threat_recency:0.5,1 --seg-dims vigilance --base-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.25 --const-action 0.11827442586893322 0.6399210213275238 0.1433532874090464
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95/g998 --tag b_forbid --g998 --seg-bins threat_recency:0.5,1 --seg-dims speed --base-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.0 --const-action 0.4913744307309694 0.4913744307309694 0.4913744307309694
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95/g998 --tag b_allow --g998 --seg-bins threat_recency:0.5,1 --seg-dims speed vigilance --base-action 0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.25 --const-action 0.4913744307309694 0.25 0.4913744307309694 0.25 0.4913744307309694 0.25
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95/g998 --tag e2b_vig --g998 --seg-bins threat_recency:0.5,1 --seg-dims speed vigilance --base-action 0.9709889334578663 0.7849404966375042 1.0 0.03358694847233987 0.4913744307309694 0.0 --const-action 0.4913744307309694 0.0 0.4913744307309694 1.0 1.0 0.0
python diagnose_v2.py constsearch --config results/v2/e2/configs/V0_d0_95.yaml --workers 6 --out results/v2/e2/V0/d0_95/g998 --tag e2b_run --g998 --seg-bins threat_recency:0.5,1 --seg-dims speed vigilance --base-action 0.9709889334578663 0.7849404966375042 1.0 0.03358694847233987 0.4913744307309694 0.0 --const-action 0.4913744307309694 0.0 1.0 0.0 1.0 0.0
