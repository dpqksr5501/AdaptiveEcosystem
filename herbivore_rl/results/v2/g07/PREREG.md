# 0-7 사전 등록: γ 비교와 결정·확률 모드 비교 (v2.0 세계)

- 작성: 2026-10-02 (금). 학습·평가를 돌리기 전, 결과를 보기 전에 적었다. 학습을 시작하기 전에 사람이 읽고 확인한다.
- 이 문서를 결과를 본 뒤 바꾸면 맨 아래 변경 기록에 날짜와 이유를 남긴다(계획서 6.1-3).
- 근거: `AdaptiveEcosystem/Docs/RL_Policy/RL_V2_PLAN.md`
  - 0단계 표 0-7 행. 10-02 변경으로 v2.0b 기록 학습은 하지 않는다. γ 비교와 두 모드 비교만 v2.0 세계(`configs/v2.yaml`)에서 한다.
  - 4.7 학습 표의 γ 행: {0.9917, 0.995, 0.998}을 2시드로 비교한다. 선택 규칙(사전 등록)은 "γ 후보마다 G_0.998·수명·아사율·피식률을 같은 평가로 재고, G_0.998이 최고값과 유의하게 다르지 않은 가장 작은 γ를 고른다"이다. 게이트의 G_γ는 γ_train과 0.998 둘 다로 보고한다.
  - 6.1 원칙 1(G_γ 정의), 3(기준 고정, 2차 지표 Holm), 4(평가 시드 10000~10019, 짝지은 t |t|>2.093, 학습 시드 IQM·층화 부트스트랩, γ=0.998 보고 평가는 10000스텝 × 20시드에 앞 500스텝 제외), 7(결정·확률 모드를 함께 재고, 판정은 결정 모드).
  - 10절 #27(γ, 0.998 평가는 10000스텝)과 #29(배포 행동 모드).
- 계산 코드: `diagnose_v2.py`의 `gamma_select`, `mode_compare`, `train_gamma_table`. 이 문서의 절차를 그대로 옮겼고, 단위 테스트는 `tests/test_g07_tools.py`에 있다. 코드와 이 문서가 어긋나면 이 문서가 기준이다. 어긋남을 찾으면 코드를 고치고 변경 기록에 남긴다.

## 1. 무엇을 비교하나

| 항목 | 고정값 |
|---|---|
| 세계 | `configs/v2.yaml` (version 2.0, 기능 모두 끔. v1 세계와 비트 단위로 같다) |
| γ 후보 | 0.9916661555611042(`ppo_best.yaml` 값. 계획서의 0.9917), 0.995, 0.998 |
| 학습 시드 | 0, 1. 세 팔 모두 같다 |
| 학습 | 20M 스텝, 무작위 초기화, 세계 8개, 리셋 4000스텝, rollout_world_steps 256. `ppo_best.yaml` 튜닝값을 그대로 쓰고 γ만 `--gamma`로 바꾼다. `--save-at 10000000`은 기록용이고 판정에 쓰지 않는다 |
| γ 0.9917 팔 | 기존 `ckpt/v2/v2_0_s0.zip`과 `v2_0_s1.zip`을 그대로 쓴다. 설정, 학습 코드 경로, 학습량이 새 팔과 같다. 0-1b 뒤에도 기능을 모두 끈 세계는 비트 단위로 같고, 학습 코드에는 γ 지정 옵션만 더했다. 메타 JSON에 `gamma`·`gamma_source` 키가 없는 것은 그 옵션 이전 파일이기 때문이다. 모델 zip의 γ는 0.9916661555611042다. 검토(10-02, 결과 보기 전): 체크포인트를 만든 코드(92ab1a0)와 지금 코드로 같은 짧은 학습(131,072스텝, 리셋 40스텝 → 세계 33개, threads 1, 시드 0)을 돌리면 가중치가 비트 단위로 같았다. 지금 코드에 `--gamma 0.9916661555611042`를 줘도 같았다 |
| 제외 | `v2_0_s2`는 판정에도, 이 문서의 표에도 넣지 않는다. s2가 상수에 가깝다는 것(0-5)은 이미 알고 있다. 결과를 보고 시드를 넣거나 빼지 않도록, 세 팔 모두 시드 0·1로 미리 고정한다 |
| 새 체크포인트 | `ckpt/v2/g07_g995_s0`, `g07_g995_s1`, `g07_g998_s0`, `g07_g998_s1` (`.zip`과 메타 `.json`) |
| 학습 사고 | 프로세스가 죽으면 같은 명령(같은 시드)으로 다시 돌리고 그 사실을 적는다. std 폭주나 상수 수렴 같은 학습 결과는 그대로 판정에 넣는다. 결과를 보고 시드를 바꾸거나 다시 학습하지 않는다 |
| 실행 시간 | `g07_g998_s0`를 혼자 먼저 돌려 단독 실행 시간을 잰다(4.1 "단독 실행 시간은 0-7에서 잰다"). 나머지 셋은 동시에 돌린다. 둘 다 `--threads 3` |

## 2. 평가

평가는 두 종류이고, 모델 6개 각각을 두 행동 모드로 잰다. 명령은 모두 `diagnose_v2.py ablate`다. 대조군 C0, C1, C3-k, C1′와 Utility 참고 행이 함께 나온다.

| 이름 | 용도 | 조건 |
|---|---|---|
| **E998** | 판정(4.7). #29 비교 | `--g998`: γ=0.998, 평가 시드 10000~10019(20개) × 10000스텝. G_0.998 평균에서 앞 500스텝과 끝 2500스텝(ceil(5/(1−0.998)))을 뺀다. 그래서 t ∈ [500, 7500)의 개체-스텝 평균이다 |
| **Etrain** | G_γtrain 보고(5.0). #29 비교. 0.9917 팔 재현 검사 | 기본값: γ = 모델의 학습 γ, 평가 시드 10000~10019 × 5000스텝, 끝 ceil(5/(1−γ))스텝 제외(0.9917 → 600, 0.995 → 1000, 0.998 → 2500), 앞 제외 없음 |

- **G 정의(6.1-1):** 모든 개체-스텝의 할인 리턴-투-고 평균이다. 사망에서 끊고, 리스폰 뒤 보상은 넣지 않는다. 리턴-투-고는 롤아웃 전체로 계산한다. 앞 제외는 평균을 낼 때만 적용한다.
- **결과 지표**(수명, 아사율, 피식률, 리턴, 번식)는 `World.stats()`의 롤아웃 전체 값이다. 앞 500스텝 제외는 G에만 적용한다. 기존 결과와 같은 정의다.
- **행동 모드**
  - 결정(기본): sigmoid(clip(μ, −3, 3)). 언리얼 `EcoPolicyInference`와 같다.
  - 확률(`--act-mode stochastic`): sigmoid(clip(μ + exp(log_std)·ε, −3, 3)), ε ~ N(0, I). 학습 롤아웃과 같은 분포다. ε는 평가 시드에서 유도한 전용 스트림 `default_rng([평가 시드, 303, 0])`에서 스텝마다 (128, 4)개씩 뽑는다. 그래서 다시 돌리면 같은 값이 나온다. 이 스트림은 v1 세계(`[seed]`), 기능(`[seed, 2, id, part]`), 순열 대조군(`[seed, 101|202, salt]`)의 스트림과 겹치지 않는다. 확률 모드에서는 보정 롤아웃(C1 평균 행동)도 확률 모드로 잰다.
  - #29가 계약에 넣을 잡음은 Φ⁻¹(hash(StableAgentId, 결정 틱))다. 여기서 쓰는 잡음은 분포는 그것과 같지만 표본 경로가 다르다. 그래서 이 비교는 "분포에서 뽑는가, 평균을 쓰는가"의 효과만 본다.
- **보정:** 학습 시드 0~19 × 3000스텝. 평가 시드와 겹치지 않는다(기존과 같다).
- **재현 검사:** 0.9917 팔의 Etrain 결정 모드 결과(`per_seed`)는 기존 `results/v2/diag_v2_0_s0`, `diag_v2_0_s1`의 `ablate.json`과 같아야 한다. 결정적 평가이고 같은 모델·시드·스텝이기 때문이다. 다르면 원인을 찾기 전에는 판정하지 않는다.

## 3. γ 선택 규칙 (판정. E998, 결정 모드만 쓴다)

기호: G[γ][r][s]는 γ 팔, 학습 시드 r ∈ {0, 1}, 평가 시드 s(20개)의 C0 G_0.998이다.

1. **팔 평균** m_γ = G[γ]의 40개 값 평균. **최고값** γ* = m_γ가 가장 큰 γ. 평균이 정확히 같으면 작은 γ를 γ*로 한다.
2. γ ≠ γ*마다 아래 두 층으로 검정한다.
   - (a) **짝지은 t.** 평가 시드마다 학습 시드 평균을 낸다: x_γ(s) = (G[γ][0][s] + G[γ][1][s]) / 2. d(s) = x_γ(s) − x_γ*(s)이고 t = mean(d) / (sd(d, ddof=1) / √20)이다. 자유도 19, 양측. |t| > 2.093이면 (a)가 성립한다. sd(d) = 0이라 t가 정의되지 않으면 (a)는 성립하지 않는다.
   - (b) **층화 부트스트랩.** 층은 평가 시드 20개다. 2000회 반복하고 난수 시드는 0이다. 각 층에서 두 팔의 학습 시드 2개를 **팔마다 따로** 복원추출한다. 학습 시드 번호가 같아도 γ가 다르면 다른 학습이므로 팔끼리 짝짓지 않는다. 통계량은 팔 평균의 차(γ − γ*)다. 95% 퍼센타일 CI가 0을 포함하지 않으면(lo > 0 또는 hi < 0) (b)가 성립한다. CI 끝이 정확히 0이면 0을 포함한 것으로 본다.
   - **"유의하게 다르다" = (a) 그리고 (b).** 둘 중 하나만 성립하면 "유의하게 다르지 않다"로 치고, 표에 "층 불일치"로 적는다.
     - 이유 1: 6.1-4는 통계를 두 층으로 본다. (a)는 학습 시드를 평균한 뒤 평가 시드끼리만 짝지어서 학습 시드 사이 퍼짐을 보지 않는다. (b)가 그 퍼짐을 넣는다(학습 시드는 팔마다 2개뿐이다).
     - 한계(10-02 검토에서 적음, 규칙은 그대로): (b)도 학습 시드 사이 퍼짐을 일부만 넣는다. 층마다 학습 시드를 따로 뽑으므로, 모든 평가 시드에서 한 학습 시드가 일정하게 높으면 그 학습 시드 사이 표준편차의 약 1/√(2·20)배만 팔 평균의 부트스트랩 표준편차에 들어간다(rliable 층화 부트스트랩과 같은 성질). 예: 한 팔의 두 시드 평균이 9와 11이면 그 팔에서 오는 CI 반폭은 약 0.3이다. 그래서 "한 학습 시드가 만든 차이"를 (b)가 다 막지는 못한다. 판정표의 "학습 시드별" 열을 함께 적고, `summary.md`에서 시드별 순서가 팔 평균 순서와 다르면 그 사실을 적는다. 이 관찰은 선택을 바꾸지 않는다.
     - 이유 2: 이 규칙은 "다르지 않은 가장 작은 γ"를 고른다. 증거가 약하면 짧은 지평 쪽으로 가는 것이 규칙의 기본값이다.
3. **자격**은 γ*와 유의하게 다르지 않은 것이다. γ*는 늘 자격이 있다. **선택 γ_sel**은 자격 있는 γ 가운데 가장 작은 값이다. 그래서 규칙은 늘 답을 하나 낸다.
4. **다중 비교 보정은 하지 않는다.** γ*와의 비교는 최대 2개이고, 각각을 계획서 관례(|t| > 2.093)로 본다. γ*를 셋 중 최대값으로 뽑았으므로 다른 팔과의 차가 약간 커 보일 수 있다(선택 편향). 이 점은 받아들이고 적어 둔다.
5. **G에 nan이 있으면 판정하지 않는다.** 이 평가 설정(10000 > 500 + 2500)에서는 nan이 생기지 않는다. 생기면 설정 오류로 보고 고친다.
6. **판정은 결정 모드로만 한다(6.1-7).** 확률 모드 E998 값은 5절 표에 함께 적지만 γ_sel을 바꾸지 않는다.
7. IQM과 팔 평균의 층화 부트스트랩 CI(학습 시드 복원추출, 층 = 평가 시드)는 함께 보고만 한다. 판정은 t 검정과 같은 추정량인 평균으로 한다.
8. **2차 지표:** 수명, 아사율, 피식률은 E998에서 같이 잰다(4.7). **선택에는 쓰지 않는다.** γ_sel과 다른 팔의 차를 (a)와 같은 방식의 짝지은 t로 내고, p 값에는 비교마다 Holm 보정(m = 3, α = 0.05)을 한다. 선택 γ가 이 지표에서 유의하게 나빠도 선택은 바뀌지 않는다. 그 사실을 기록하고 1단계 계획에서 다룬다.
9. **결과의 쓰임:** γ_sel을 1~2단계 학습 γ로 쓴다(4.7). v2.4·v2.5b 학습 전에 {γ_sel, 0.998}을 같은 절차로 다시 비교한다. γ_sel이 0.998이면 1단계부터 0.998로 학습한다. 그때 G_γtrain의 꼬리는 2500스텝이라 게이트 trial 길이가 바뀐다. 이것은 5.0 예산 문구를 따른다.

## 4. 결정·확률 모드 비교 (#29. 기록이고, 판정 대상이 아니다)

- **짝:** 같은 모델(model_sha1)의 결정·확률 결과를 같은 평가 조건(E998끼리, Etrain끼리)에서 짝짓는다. D[r][s] = 확률 − 결정이다.
- **t:** 평가 시드마다 학습 시드 평균을 낸 20쌍으로 짝지은 t를 계산한다(자유도 19).
- **CI:** D를 층화 부트스트랩한다. 층 = 평가 시드, 학습 시드 복원추출, 통계량은 평균, 2000회, 난수 시드 0이다. 같은 모델의 두 모드라 학습 시드 안에서 짝이 맞다.
- **G**(E998은 G_0.998, Etrain은 G_γtrain): |t| > 2.093이고 CI가 0을 포함하지 않으면 유의하다.
- **결과 지표 3개**(수명, 아사율, 피식률): Holm(m = 3) 보정 p < 0.05이고 CI가 0을 포함하지 않으면 유의하다.
- **리턴, 번식, 행동 지표**(cohesion_mean, flee_dist_mean, flee_dist_std, cover_frac, react_pred, react_hunger, starve_share): 차, t, CI만 적는다. 우열을 가리지 않는다.
- **#29 신호:** **γ_sel 팔에서** E998이나 Etrain 중 하나라도 G가 유의하거나, 결과 지표가 하나라도 유의하면 신호가 있는 것이다. 신호가 있으면 #29의 "개체별 재현 가능 표본" 안을 V2 계약 안건(7.2·7.3)으로 연다. 0-7에서는 계약을 바꾸지 않는다. 다른 γ 팔의 신호는 참고로만 적는다. 학습 시드가 하나인 묶음은 판정하지 않는다(코드에서 `결론 없음`).

## 5. 보고할 표 (`results/v2/g07/`)

| # | 파일 | 내용 |
|---|---|---|
| 1 | `gammasel.md` 판정표 | γ, 학습 시드, G_0.998 팔 평균 [95% CI], 학습 시드별 평균, IQM, γ* 대비 Δ, t, Δ 95% CI, 유의(층 불일치 표시), 자격, 선택 |
| 2 | `gammasel.md` 결과 지표 | 같은 E998의 수명, 아사율, 피식률, 리턴(보고만). γ_sel과의 Δ (t, Holm p) |
| 3 | `gammasel.md` G_γtrain | Etrain의 γ_train, 꼬리, G_γtrain 평균, 학습 시드별, C0 − C1 (t). 팔끼리 비교하지 않는다(6.1-1) |
| 4 | `gammasel.md` 참고 | E998에서 팔마다 C0 − C1 (G_0.998). 긴 지평에서 상태 의존 이득이 있는지 본다 |
| 5 | `modecmp_e998.md`, `modecmp_etrain.md` | 팔마다 지표, 결정, 확률, Δ, t, CI, 판정, #29 신호 |
| 6 | `summary.md`(손으로 쓴다) | 학습 기록(run, γ, 시드, 단독·동시 실행 시간, actual_timesteps, worlds_seen, 끝 R²), 재현 검사 결과, γ_sel, #29 신호, 계획서 반영 문구(0-7 행, 4.7 γ, 0단계 완료 기준) |

## 6. 실행 명령 (Git Bash, 작업 디렉터리 `herbivore_rl/`)

```bash
# 0) 확인
python -m pytest -q
mkdir -p results/v2/g07

# 1) 학습: 단독 1회(실행 시간 측정) → 나머지 3개 동시
python -u train_v2.py --steps 20000000 --seed 0 --gamma 0.998 --run-name g07_g998_s0 --save-at 10000000 --threads 3 > results/v2/g07/train_g07_g998_s0.log 2>&1
python -u train_v2.py --steps 20000000 --seed 1 --gamma 0.998 --run-name g07_g998_s1 --save-at 10000000 --threads 3 > results/v2/g07/train_g07_g998_s1.log 2>&1 &
python -u train_v2.py --steps 20000000 --seed 0 --gamma 0.995 --run-name g07_g995_s0 --save-at 10000000 --threads 3 > results/v2/g07/train_g07_g995_s0.log 2>&1 &
python -u train_v2.py --steps 20000000 --seed 1 --gamma 0.995 --run-name g07_g995_s1 --save-at 10000000 --threads 3 > results/v2/g07/train_g07_g995_s1.log 2>&1 &
wait

# 2) 평가: 모델 6개 × {E998, Etrain} × {결정, 확률}. --name 은 보정 캐시 이름(runs/v2_diag/<이름>/)이다
python diagnose_v2.py ablate --model ckpt/v2/v2_0_s0.zip --name g07_g9917_s0 --out results/v2/g07/g9917_s0/e998_det --g998 --workers 10
python diagnose_v2.py ablate --model ckpt/v2/v2_0_s0.zip --name g07_g9917_s0 --out results/v2/g07/g9917_s0/e998_stoch --g998 --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/v2_0_s0.zip --name g07_g9917_s0 --out results/v2/g07/g9917_s0/etrain_det --workers 10
python diagnose_v2.py ablate --model ckpt/v2/v2_0_s0.zip --name g07_g9917_s0 --out results/v2/g07/g9917_s0/etrain_stoch --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/v2_0_s1.zip --name g07_g9917_s1 --out results/v2/g07/g9917_s1/e998_det --g998 --workers 10
python diagnose_v2.py ablate --model ckpt/v2/v2_0_s1.zip --name g07_g9917_s1 --out results/v2/g07/g9917_s1/e998_stoch --g998 --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/v2_0_s1.zip --name g07_g9917_s1 --out results/v2/g07/g9917_s1/etrain_det --workers 10
python diagnose_v2.py ablate --model ckpt/v2/v2_0_s1.zip --name g07_g9917_s1 --out results/v2/g07/g9917_s1/etrain_stoch --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g995_s0.zip --name g07_g995_s0 --out results/v2/g07/g995_s0/e998_det --g998 --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g995_s0.zip --name g07_g995_s0 --out results/v2/g07/g995_s0/e998_stoch --g998 --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g995_s0.zip --name g07_g995_s0 --out results/v2/g07/g995_s0/etrain_det --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g995_s0.zip --name g07_g995_s0 --out results/v2/g07/g995_s0/etrain_stoch --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g995_s1.zip --name g07_g995_s1 --out results/v2/g07/g995_s1/e998_det --g998 --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g995_s1.zip --name g07_g995_s1 --out results/v2/g07/g995_s1/e998_stoch --g998 --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g995_s1.zip --name g07_g995_s1 --out results/v2/g07/g995_s1/etrain_det --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g995_s1.zip --name g07_g995_s1 --out results/v2/g07/g995_s1/etrain_stoch --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g998_s0.zip --name g07_g998_s0 --out results/v2/g07/g998_s0/e998_det --g998 --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g998_s0.zip --name g07_g998_s0 --out results/v2/g07/g998_s0/e998_stoch --g998 --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g998_s0.zip --name g07_g998_s0 --out results/v2/g07/g998_s0/etrain_det --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g998_s0.zip --name g07_g998_s0 --out results/v2/g07/g998_s0/etrain_stoch --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g998_s1.zip --name g07_g998_s1 --out results/v2/g07/g998_s1/e998_det --g998 --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g998_s1.zip --name g07_g998_s1 --out results/v2/g07/g998_s1/e998_stoch --g998 --act-mode stochastic --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g998_s1.zip --name g07_g998_s1 --out results/v2/g07/g998_s1/etrain_det --workers 10
python diagnose_v2.py ablate --model ckpt/v2/g07_g998_s1.zip --name g07_g998_s1 --out results/v2/g07/g998_s1/etrain_stoch --act-mode stochastic --workers 10

# 3) 재현 검사 (둘 다 True 여야 판정으로 간다)
python -c "import json; f=lambda p: json.load(open(p, encoding='utf-8'))['per_seed']; print(all(f(f'results/v2/diag_v2_0_s{s}/ablate.json') == f(f'results/v2/g07/g9917_s{s}/etrain_det/ablate.json') for s in (0, 1)))"

# 4) 판정과 비교
python diagnose_v2.py gammasel --out results/v2/g07 --dirs results/v2/g07/g9917_s0/e998_det results/v2/g07/g9917_s1/e998_det results/v2/g07/g995_s0/e998_det results/v2/g07/g995_s1/e998_det results/v2/g07/g998_s0/e998_det results/v2/g07/g998_s1/e998_det --train-dirs results/v2/g07/g9917_s0/etrain_det results/v2/g07/g9917_s1/etrain_det results/v2/g07/g995_s0/etrain_det results/v2/g07/g995_s1/etrain_det results/v2/g07/g998_s0/etrain_det results/v2/g07/g998_s1/etrain_det
python diagnose_v2.py modecmp --out results/v2/g07 --tag modecmp_e998 --det results/v2/g07/g9917_s0/e998_det results/v2/g07/g9917_s1/e998_det results/v2/g07/g995_s0/e998_det results/v2/g07/g995_s1/e998_det results/v2/g07/g998_s0/e998_det results/v2/g07/g998_s1/e998_det --stoch results/v2/g07/g9917_s0/e998_stoch results/v2/g07/g9917_s1/e998_stoch results/v2/g07/g995_s0/e998_stoch results/v2/g07/g995_s1/e998_stoch results/v2/g07/g998_s0/e998_stoch results/v2/g07/g998_s1/e998_stoch
python diagnose_v2.py modecmp --out results/v2/g07 --tag modecmp_etrain --det results/v2/g07/g9917_s0/etrain_det results/v2/g07/g9917_s1/etrain_det results/v2/g07/g995_s0/etrain_det results/v2/g07/g995_s1/etrain_det results/v2/g07/g998_s0/etrain_det results/v2/g07/g998_s1/etrain_det --stoch results/v2/g07/g9917_s0/etrain_stoch results/v2/g07/g9917_s1/etrain_stoch results/v2/g07/g995_s0/etrain_stoch results/v2/g07/g995_s1/etrain_stoch results/v2/g07/g998_s0/etrain_stoch results/v2/g07/g998_s1/etrain_stoch
```

- 예상 시간(추정)
  - 학습: 단독 1회 약 10~14분, 동시 3회 약 14분.
  - 평가: E998 1회는 약 5~6분이다. 기존 5000스텝 ablate가 워커 10개로 168초였으므로 그 두 배로 잡았다. Etrain 1회는 약 3분이다. 합치면 약 100분이다.
  - 평가 두 줄을 동시에 돌리면(각 워커 10) 절반으로 줄어든다. 적힌 순서대로 두 줄씩(같은 모델의 결정·확률 짝) 돌린다. 같은 `--name`의 같은 모드 두 줄(예: e998_det와 etrain_det)을 동시에 돌리지 않는다. 둘이 같은 보정 캐시 파일을 함께 쓴다.
- 기존 결과와 캐시는 덮지 않는다.
  - 출력은 모두 `results/v2/g07/` 아래에 쓴다.
  - 보정 캐시는 `runs/v2_diag/g07_*`에 새로 만든다. 확률 모드 캐시는 같은 디렉터리의 `calib_stochastic.npz`다.
  - `diag_v2_0_s*`와 `runs/v2_diag/v2_0_s*`는 읽기만 한다.

## 변경 기록

- 2026-10-02: 처음 작성(결과 보기 전).
- 2026-10-02: 반박 검토 반영(새 학습·본 평가 전). 판정 규칙은 바꾸지 않았다. 도구 시험으로 `v2_0_s0` 하나를 평가 시드 10000·10001에서 E998·Etrain × 두 모드로 돌려 봤다(scratchpad, 캐시 따로). 아래 수정은 그 값과 무관하게 그 전에 찾은 것이고, 그 값은 판정에 쓰지 않는다.
  - 코드 결함: `modecmp`가 모든 결과의 γ·꼬리가 같기를 요구해서, 6절의 `modecmp_etrain`(팔마다 학습 γ로 잰 Etrain)이 실행되지 않고 멈췄다. 이제 평가 시드·스텝·앞 제외·설정은 모든 결과에서, γ·꼬리는 짝과 팔 안에서 같은지 본다. 팔끼리 γ가 다르면 모든 결과가 자기 학습 γ로 잰 것이어야 한다(E998과 Etrain을 섞지 않는다).
  - 입력 검사 추가(5절 표가 사전 등록 조건의 결과만 받게): `gammasel`은 v2.0 세계(config_version 2.0)만 받고, 학습 메타로 시드를 알 수 있으면 팔마다 학습 시드 묶음이 같아야 한다. G_γtrain 표는 Etrain 조건(결정 모드, 10000~10019 × 5000스텝, 앞 제외 0, 끝 ceil(5/(1−γ_train)), v2.0 세계)만 받는다. `train_v2.py`는 롤아웃 버퍼(GAE)의 γ도 지정값인지 본다.
  - 3절 이유 1의 근거를 바로잡고 (b)의 한계를 적었다.
  - 6절에 동시 실행 순서를 적었다.
  - 확인한 것: (1) 결정 모드. 지금 코드로 `diag_v2_0_s0`, `diag_v2_0_s1`의 ablate 전체(20시드 × 5000스텝, 대조군 8개)를 다시 돌리면 `per_seed`, `controls`, `calib`, calib.json이 같고, MD는 생성 줄만 다르다. (2) 확률 모드. 실제 `v2_0_s0` 모델에서 SB3 학습 경로(분포 표본 → [−3, 3] 자르기 → sigmoid)와 `StochasticLearned`의 행동을 2만 번씩 뽑아 비교했다. 128 × 4 칸의 평균 차 z는 평균 0.000, 표준편차 1.03이었다. log_std는 상태와 무관하고 squash가 없다(use_sde False, squash_output False). (3) γ. `--gamma 0.998`은 모델과 버퍼에 들어가고, 같은 짧은 학습에서 가중치가 기본 γ와 달라진다.
