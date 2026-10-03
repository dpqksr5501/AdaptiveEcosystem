# 1-6b 사전 등록: 탐색 붕괴 대응 두 팔 비교(3시드)와 1-6 판정 재실행

- 작성: 2026-10-03 (토). **학습 전, 결과를 보기 전에 적었다.** 이 시점에 `ckpt/v2/v2_2a_*`·`v2_2b_*`, `runs/v2/v2_2a_*`·`v2_2b_*`, `results/v2/diag_v2_2a*`·`diag_v2_2b*`, `runs/v2_diag/v2_2a_*`·`v2_2b_*`, `results/v2/s1_6b/`(이 문서 말고)는 없다(`_stage1_6b_compare.py precheck --arms a b --seeds 0 1 2` 통과).
- 결과를 본 뒤 이 문서를 바꾸면 맨 아래 변경 기록에 날짜와 이유를 남긴다(계획서 6.1-3). 8절의 약속을 따른다.
- 근거:
  - **10-03 사람 결정**(계획서 `AdaptiveEcosystem/Docs/RL_Policy/RL_V2_PLAN.md` 10절): 탐색 붕괴 대응 두 방법을 3시드씩 빠르게 비교(기록용)하고, 나은 쪽으로 1-6 판정을 다시 한다. 팔 A = ent_coef 3e-3(나머지 그대로, 경계 시작 편향 −0.84). 팔 B = 경계 시작 편향 0(처음 확률 모드 경계 약 50%, 결정 모드는 문턱 경계값), ent_coef는 기존 튜닝값 그대로. 세계 설정은 바꾸지 않는다.
  - 1-6 결과(`results/v2/stage1_v2_2.md`, 커밋 c4b49c6): 학습 실패(C0의 G_γ가 E1-b·E2 C2-seg보다 유의하게 낮다). 5시드 모두 결정 모드 경계 0, 5M `vig/frac` 0.0001~0.0078(1% 미만), 포식자가 안 보일 때 과도한 정지, #29 신호(확률 모드가 G_γ +1.103).
  - 계획서 4.7(탐색 붕괴 감시: 5M 시점 경계 비율 1% 미만이면 (a) 해당 차원 log_std 재설정 (b) ent_coef 3e-3 재학습), 5.0(학습 실패 규칙과 대응 (a)~(d)), 1단계 완료 기준(10-03 문구), 6.1~6.4.
  - 1-6 사전 등록 `results/v2/s1_6/PREREG.md`(판정 재실행의 규칙·정의·기준은 그 문서를 그대로 쓴다, 5절).
- 기반: 커밋 c4b49c6 위에 이번에 바꾼 도구(학습 전, 같은 날):
  - `train_v2.py`: `--ent-coef`(엔트로피 계수만 덮음), `--init-bias 이름=값`(설정 `train.init_action_bias` 위에 행동별 시작 편향을 덮음). 메타 JSON에 `ent_coef`·`ent_coef_source`, `init_action_bias`·`init_action_bias_source`, `config_digest`를 남긴다. 옵션이 없으면 기존과 같다.
  - `results/v2/_stage1_6_v2_2.py`: `--prefix`(실행 이름 접두사, 기본 `v2_2`)·`--sdir`(B6·B7 결과와 판정표 폴더, 기본 `s1_6`)·`--seeds`. 기본 인자로 다시 낸 judge 출력이 `s1_6/stage1_6_v2_2.json`과 `generated`·`script` 칸만 다르다(판정 칸 모두 같다).
  - `results/v2/_stage1_6b_compare.py`(새 파일): 이 문서 1~4절을 옮긴 비교 집계·선택(`compare`), 학습 전 확인(`precheck`), 학습 메타 확인(`checktrain`), 선택 팔 읽기(`selected`), 팔의 학습 옵션(`armargs`). 상수 `ARMS`, `COMPARE_SEEDS`, `JUDGE_SEEDS`, `TRAIN_STEPS`, `COLLAPSE_STEP`, `COLLAPSE_FRAC`, `TIE_ARM`, `SEG`, `SELECT_CLAIMS`와 함수 `summarize_arm`, `boot_diff_stat`, `select_arm`, `tb_summary`가 이 문서를 옮긴 것이다. 조건 검사·행 읽기·묶음 통계는 `_stage1_6_v2_2.py`의 것(`Cond`, `rows_of`, `check_const`, `bundle_delta`, `PRIMARY`)을 그대로 쓴다.
  - 시험 `tests/test_s1_6b_tools.py`(28개). pytest 494 통과 + 1 skip(이전 466 + 28).
  - 코드와 이 문서가 어긋나면 이 문서가 기준이다. 어긋남을 찾으면 코드를 고치고 변경 기록에 남긴다.
- 바꾸지 않은 것: `configs/v2_2.yaml`(config_digest **efc8f775f1e1**, `git diff 5eaa21b -- configs/v2_2.yaml` 비어 있음), `configs/ppo_best.yaml`, v1 파일, 1-6 결과·체크포인트·캐시(`v2_2_s*`, `diag_v2_2*`, `s1_6/`).

## 0. 이 묶음이 묻는 것

1. **비교(기록용, 1~4절):** 4.7 탐색 붕괴 대응 두 방법 — 팔 A(ent_coef 3e-3)와 팔 B(경계 시작 편향 0) — 가운데, 학습 실패가 아니고 경계 탐색이 붕괴하지 않는 쪽이 있는가. 있으면 어느 쪽인가. 학습 시드 3개씩의 빠른 비교라 1단계 판정이 아니다. 결과는 판정 재실행에 쓸 팔 하나를 고르는 데만 쓴다.
2. **판정 재실행(5절):** 고른 팔로 새 학습 시드 5개(5~9)를 학습해, 1-6과 같은 규칙으로 1단계 완료 기준(크기·쓸모·입력 의존·학습 실패 감지·영상)을 다시 판정한다. 1-6 판정(`v2_2_s0~4`)은 덮지 않고 나란히 둔다.

## 1. 두 팔 (학습 설정만 다르다)

| 팔 | 실행 이름 | ent_coef | 마지막 층 편향 vigilance | 시작 경계 확률(확률 모드, log_std 0) | 학습 옵션 |
|---|---|---|---|---|---|
| A | `v2_2a_s{0,1,2}` | **0.003** (`--ent-coef 3e-3`, 메타 `ent_coef_source` = cli) | −0.84 (설정 `train.init_action_bias` 그대로, 출처 config) | 약 0.20 | `--ent-coef 3e-3` |
| B | `v2_2b_s{0,1,2}` | 0.0008971496690499397 (`configs/ppo_best.yaml` 튜닝값 그대로, 출처 ppo_config) | **0** (`--init-bias vigilance=0`, 출처 cli) | 약 0.50 | `--init-bias vigilance=0` |

- 같은 것: 설정 `configs/v2_2.yaml`(세계·기능 계수 모두, config_digest efc8f775f1e1), γ 0.9916661555611042(`--gamma`), 학습량 20,000,000(`--steps 20000000`, 롤아웃 단위로 올림), 중간 저장 10,000,000(`--save-at 10000000`), 무작위 초기화(`--init` 없음), speed 편향 0, 나머지 하이퍼파라미터는 `configs/ppo_best.yaml` 그대로(learning_rate 6.8132e-05, clip_range 0.378, n_epochs 15), 망 구조 8-64-64-6.
- 학습 시드: 0, 1, 2(`--seed`, PPO 시드이자 세계 선택 시드). 두 팔이 같은 번호를 쓰지만 통계에서 짝짓지 않는다(3절).
- 팔 B의 결정 모드 시작 경계: 결정값 sigmoid(clip(μ))의 μ가 편향 0 근처(마지막 층 가중치 gain 0.01)라 문턱 0.5 위아래로 개체마다 갈린다. 학습이 μ를 조금만 내려도 결정 모드 경계가 0이 될 수 있다(한계, 7절). 판정은 20M 값으로 한다.
- 스레드: `--threads 3`, 6개를 동시에 돌린다(코어 20개). 실행 조건으로 기록만 한다.
- 학습 전 확인(학습 명령 직전): pytest 494 통과 + 1 skip, `git diff 5eaa21b -- configs/v2_2.yaml`이 비어 있다, `_stage1_6b_compare.py precheck --arms a b --seeds 0 1 2`가 통과한다(설정 지문 efc8f775f1e1, ppo_best ent_coef가 위 값, 새 이름의 체크포인트·TensorBoard·진단·캐시·로그가 없다).
- 학습 뒤 확인: `checktrain --arms a b --seeds 0 1 2` — 학습 메타의 seed, steps 20,000,000(실제 학습량 이상), γ와 출처 cli, ent_coef와 출처, init_action_bias와 출처, config_digest efc8f775f1e1, `init` 없음, 다른 튜닝값이 ppo_best와 같음, version 2.2, `.zip`·`_10m.zip`이 있음. 하나라도 다르면 멈춘다. 시작 경계 확률(메타 `init_policy.vigilance.vig_prob`)은 표로 기록한다.

## 2. 비교 평가 (모델마다)

| 단계 | 명령 | 쓰는 행 |
|---|---|---|
| 결정 모드 | `diagnose_v2.py ablate` (1-6과 같은 묶음: C0, C1, C3-k, C1′) | C0 (나머지 행은 기록만) |
| E2 C2-seg | `diagnose_v2.py constsearch --tag c2seg_e2` (1-6 PREREG 4절의 C2-seg-E2 그대로: 구간 `threat_recency:0.5,1`, vigilance만 구간별 [0.11827442586893322, 0.6399210213275238, 0.1433532874090464], 바탕 E2 C2) | C2-seg, C0(= ablate의 C0인지 확인), C2(바탕 상수, 기록) |
| 확률 모드 | `diagnose_v2.py ablate --act-mode stochastic` (잡음 스트림 `[평가 시드, 303, 0]`) | C0 (기록만, 선택에 쓰지 않는다) |

- 평가 조건은 1-6 PREREG 2절과 같다: 평가 시드 10000~10019(20개) × 5000스텝, G_γ는 γ_train으로 재고 끝 600스텝을 뺀다, 앞 제외 0, 보정은 세계 시드 0~19 × 3000스텝.
- 조건 검사(하나라도 다르면 집계가 멈춘다): 모든 결과의 config_digest efc8f775f1e1, 평가 시드·스텝·γ·꼬리·앞 제외·모드가 위와 같다. 모델마다 세 결과의 model_sha1이 같고 체크포인트와 같다. C2-seg의 구간·행동·바탕·상수가 위 값과 같다. c2seg_e2의 C0 행이 ablate의 C0 행과 같다.
- 재현 검사(기록, 선택에 쓰지 않음): 다시 잰 C2-seg 행이 `results/v2/e2/V0/d0_95/a_allow.json`의 C2-seg 행과, C2 행이 `results/v2/e2/V0/c2/constsearch.json`의 C2 행과 비트 단위로 같아야 한다(상수 정책이라 학습과 무관). 다르면 비교는 이번에 다시 잰 행으로 하고 세계 차이 신호로 보고한다.
- 학습 시드 값 = 평가 시드 20개 평균(nan 제외).

## 3. 비교 지표 (결정 모드. 확률 모드는 같은 열을 기록)

| 지표 | 정의 | 쓰임 |
|---|---|---|
| **탐색 붕괴 신호** (학습 시드마다) | (a) TensorBoard `runs/v2/<실행 이름>_1`의 `vig/frac`(학습 분포의 경계 비율, 행동 5의 sigmoid(clip(표본)) > 0.5)에서 **5,000,000 이상 첫 롤아웃**의 값이 0.01 미만, 또는 (b) 결정 모드 C0의 경계 비율 `vig_frac`(평가 시드 20개 평균)이 0보다 크지 않다. 둘 중 하나면 신호 | 선택 (2) |
| **팔의 붕괴 없음** | 그 팔의 학습 시드 **3개 모두** 붕괴 신호가 없다 | 선택 (2) |
| **학습 실패** (팔마다) | Δ = C2-seg-E2 − C0의 G_γ, (학습 시드 3 × 평가 시드 20) 행렬 IQM, 층화 부트스트랩(층 = 평가 시드, 층마다 학습 시드 복원추출) 2000회·난수 시드 0의 95% 퍼센타일 CI. **하한 > 0이면 학습 실패**(C0이 E2 C2-seg보다 유의하게 낮다). 시드별 짝지은 t도 적는다 | 선택 (1) |
| **G_γ** | C0 G_γ 행렬의 IQM과 같은 부트스트랩 CI. 팔 사이 차 Δ = IQM(A) − IQM(B)의 CI는 층마다 **팔마다 따로** 학습 시드를 복원추출하는 층화 부트스트랩 2000회·시드 0의 95% 퍼센타일 CI(`boot_diff_stat`. 같은 번호 시드라도 다른 학습이라 짝짓지 않는다). CI가 0을 빼면 '유의' | 선택 (3) |
| **B1·B2·B3 크기** | 1-6 PREREG 3절과 같은 열·기준: B1 `b1` ≥ 0.3, B2 `b2` ≥ 0.1, B3 `b3_truth` ≥ 0.2. 학습 시드마다 값과 통과 여부, 팔마다 통과 시드 수(3개 중) | 선택 (3)은 B1·B3 통과 시드 수의 합(팔마다 최대 6). B2는 기록 |
| **아사율** | `starve_rate` 학습 시드 값과 묶음 IQM·CI | 기록 |

- 함께 기록(선택에 쓰지 않음): 피식률·수명·번식, 명령 보행 비율, `p_stop_hungry`·`p_stop_full`, B8, `b3_narrow`, `p_vig_recent_truth`·`p_vig_calm_truth`, C2 − C0의 G_γ, 확률 모드 C0의 같은 열과 G_γ·아사율 IQM, 확률 − 결정 G_γ. 학습 기록: `vig/frac` 1M·5M·10M·마지막 값, 5%·1%를 처음 밑돈 시점, 5M 이후 최대, vigilance·speed log_std(5M·마지막), 학습 분포 speed·vigilance std(처음·5M·마지막·최소와 처음 대비 비율), speed std 최소가 처음의 10% 미만인지(4.7의 다른 붕괴 신호, 기록만).
- 비교의 학습 실패는 사람 결정대로 E2 A-허용 C2-seg 하나로 본다. E1-b C2-seg는 비교에서 재지 않고 판정 재실행(5절)에서 1-6대로 둘 다 본다.

## 4. 선택 규칙 (결과 보기 전 고정)

1. **학습 실패가 아닌 팔**만 후보다(3절 학습 실패 칸).
2. 그 가운데 **붕괴가 없는 팔**(3시드 모두 붕괴 신호 없음)만 남긴다.
3. 남은 팔이
   - **0개**: 선택하지 않는다. **판정 재실행을 하지 않고 멈춘다.** 다음은 사람이 정한다(5.0 (b) 학습량 2배 ~ (d) C2-seg 모방 초기화, 또는 1단계 범위 축소).
   - **1개**: 그 팔.
   - **2개**: 결정 모드 C0 G_γ IQM 차(A − B)의 CI가 0을 빼면 IQM이 높은 팔(CI 하한 > 0이면 A, 상한 < 0이면 B). CI가 0을 포함하면 **B1·B3 크기 통과 시드 수 합**(결정 모드)이 많은 팔. 그것도 같으면 **팔 A**.
- 이 밖의 것(확률 모드, 아사율, 2차 지표, 학습 곡선, 영상)은 선택에 쓰지 않는다.
- `compare`가 `results/v2/s1_6b/compare.json`의 `selection`에 고른 팔(`arm`: a | b | null), 실행 이름 접두사, 학습 옵션, 판정 학습 시드, 단계별 근거(`trace`)를 남긴다. `selected`가 그 팔을 읽고, 판정 재실행의 `precheck`는 고른 팔 하나만 받는다.

## 5. 판정 재실행 (선택한 팔 X)

- **학습:** 팔 X의 설정(1절 표의 학습 옵션) 그대로, **새 학습 시드 5, 6, 7, 8, 9**, 실행 이름 `v2_2<X>_s{5..9}`(예: `v2_2a_s5`), 20M, γ 0.9916661555611042, 중간 저장 10M, `--threads 3`, 5개 동시.
  - 시드 5~9는 비교에 쓴 0~2와 겹치지 않는다(같은 시드로 고르고 판정하면 선택 편향이 들어간다). 1-6의 0~4와도 겹치지 않는다. 비교 시드(0~2)의 결과는 판정에 넣지 않는다.
  - 학습 전 `precheck --arms X --seeds 5 6 7 8 9`(compare.json이 X를 골랐는지, 설정 지문, 새 이름·묶음·판정표가 없는지), 학습 뒤 `checktrain --arms X --seeds 5 6 7 8 9`.
- **판정 규칙·정의·기준: `results/v2/s1_6/PREREG.md` 그대로다.** 바꾸는 것은 실행 이름·학습 시드·학습 설정(팔 X)·출력 폴더뿐이다. 1-6 PREREG 1절 표의 '학습 시드 0~4', '이름 v2_2_s*', '초기화'는 이 절이 대신한다. 나머지는 그대로다:
  - 평가 조건과 통계 틀(1-6 2절): 결정 모드 판정, 평가 시드 10000~10019 × 5000스텝, 묶음 유의는 (학습 시드 5 × 평가 시드 20) Δ 행렬 IQM의 층화 부트스트랩 2000회·시드 0 95% CI, 조건 검사.
  - 1차 지표(3절): B1 `b1` ≥ 0.3, B2 `b2` ≥ 0.1, **B3 = `b3_truth`** ≥ 0.2.
  - 대조군(4절): C0, C1, C1′, C3-k 6개, C4(pred_dist·energy·threat_recency의 fix·perm), C2(E2), C2-seg-E1b, C2-seg-E2, 재현 검사.
  - 판정 규칙(5절): **크기** = 5시드 중 4시드 이상. **쓸모** = 결과 지표 필수(B1·B3 피식률, B2 아사율 또는 번식)에서 C0이 C1′와 C2 **둘 다**보다 유의하게 낫다(G_γ는 보고만). **입력 의존** = 크기를 넘은 시드 모두에서 해당 C4 고정이 기준 아래. **학습 실패 감지** = Δ G_γ(C2-seg − C0) CI 하한 > 0이면 학습 실패, **E1-b·E2 C2-seg 둘 다** 본다. 1단계 완료(수치) = 세 주장 성립이고 학습 실패가 아니다.
  - 2차 지표(6절, Holm m = 7, B4 v1 기준선은 `results/v2/s1_6/b4_v1_baseline.json` 그대로), 행동 모드 #29 기록(7절), 판정 문장 형식(9절).
  - 탐색 붕괴 감시(1-6 1절): 5M `vig/frac` 1% 미만·speed std 초기 10% 미만을 기록한다. 신호가 있어도 판정 묶음을 그대로 돌려 기록한다.
- **영상(1-6 8절 그대로):** 같은 시드·같은 카메라로 C0와 C1′를 나란히(S0), 평가 시드 10000, 1800스텝, stride 2. 학습 시드 V = 1차 세 지표의 크기를 모두 넘은 학습 시드 가운데 번호가 가장 작은 것(없으면 첫 시드 5), 정지 화면 스텝 = C0 칸에서 경계 개체 수가 가장 많은 스텝(같으면 이른 스텝). 둘 다 judge의 `video` 칸이다. '보인다·사라진다'는 사람이 본다. mp4는 로컬, png는 커밋 대상이다. png를 만든 명령은 `replay_v2.py` 머리 주석에 더한다(`tests/test_replay_v2.py`가 `results/v2/replay_*.png`마다 요구한다. 코드 변경 아님).
- **출력:** 진단 `results/v2/diag_v2_2<X>_s{5..9}`·`_stoch`, 묶음 `results/v2/diag_v2_2<X>/`(report·modecmp), B6·B7 `results/v2/s1_6b/b67_v2_2<X>_s{5..9}.json`, 판정표 `results/v2/s1_6b/stage1_6_v2_2<X>.json`, 영상 `results/v2/replay_v2_2<X>_compare.mp4`·`.png`, 보고서 `results/v2/stage1_v2_2<X>.md`. judge·b67·compare는 출력이 있으면 덮지 않는다(`--overwrite`로만).
- 판정이 미충족이어도 이 사전 등록 안에서는 더 학습하지 않는다. 다음은 사람이 정한다.

## 6. 실행 명령 (Git Bash, 작업 디렉터리 `herbivore_rl/`)

10분 넘는 단계(학습, 진단)는 백그라운드로 돌리고 로그로 확인한다. 예상 시간(추정): 비교 학습 6개 동시 20~30분, 비교 진단 6개 동시(모델마다 워커 3) 30~40분, 비교 집계 1분, 판정 학습 5개 동시 20~30분, 시드별 진단 5개 동시 1~1.5시간, 묶음 수 분, 영상 약 6분.

```bash
# 0) 학습 전 확인
python -m pytest -q                                   # 494 passed, 1 skipped
git diff 5eaa21b -- configs/v2_2.yaml                 # 비어 있어야 한다
python results/v2/_stage1_6b_compare.py precheck --arms a b --seeds 0 1 2
G=0.9916661555611042
C2="0.9709889334578663 0.7849404966375042 0.2182330585135458 0.03358694847233987 0.4913744307309694 0.25"
E1B="0.31542835092418386 0.3637107709426226 0.5701967704178796 0.43860151346232035"
E2S="0.11827442586893322 0.6399210213275238 0.1433532874090464"

# 1) 비교 학습: 팔 A·B × 시드 0·1·2 (6개 동시)
for s in 0 1 2; do
  python train_v2.py --config configs/v2_2.yaml --steps 20000000 --seed $s --gamma $G --run-name v2_2a_s$s \
      --save-at 10000000 --threads 3 --ent-coef 3e-3 > results/v2/train_v2_2a_s$s.log 2>&1 &
  python train_v2.py --config configs/v2_2.yaml --steps 20000000 --seed $s --gamma $G --run-name v2_2b_s$s \
      --save-at 10000000 --threads 3 --init-bias vigilance=0 > results/v2/train_v2_2b_s$s.log 2>&1 &
done; wait
python results/v2/_stage1_6b_compare.py checktrain --arms a b --seeds 0 1 2

# 2) 비교 진단: 모델마다 결정 모드 ablate → E2 C2-seg → 확률 모드 ablate (6개 동시, 모델 안에서는 이 순서)
for r in v2_2a_s0 v2_2a_s1 v2_2a_s2 v2_2b_s0 v2_2b_s1 v2_2b_s2; do (
  M="--config configs/v2_2.yaml --model ckpt/v2/$r.zip --name $r --workers 3"
  python diagnose_v2.py ablate $M
  python diagnose_v2.py constsearch $M --tag c2seg_e2 --seg-bins threat_recency:0.5,1 --seg-dims vigilance \
      --base-action $C2 --const-action $E2S
  python diagnose_v2.py ablate --config configs/v2_2.yaml --model ckpt/v2/$r.zip --name ${r}_stoch \
      --act-mode stochastic --workers 3
) > results/v2/diag_$r.log 2>&1 & done; wait

# 3) 비교 집계와 선택 (4절)
python results/v2/_stage1_6b_compare.py compare        # → results/v2/s1_6b/compare.json
X=$(python results/v2/_stage1_6b_compare.py selected)  # a | b | 빈 값(후보 없음)
if [ -z "$X" ]; then echo "후보 없음: 판정 재실행 없이 멈춘다(사람 결정)"; exit 0; fi
P=v2_2$X
EXTRA=$(python results/v2/_stage1_6b_compare.py armargs --arm $X)   # a: --ent-coef 3e-3 / b: --init-bias vigilance=0

# 4) 판정 재실행 학습: 팔 X × 시드 5~9 (5개 동시)
python results/v2/_stage1_6b_compare.py precheck --arms $X --seeds 5 6 7 8 9
for s in 5 6 7 8 9; do
  python train_v2.py --config configs/v2_2.yaml --steps 20000000 --seed $s --gamma $G --run-name ${P}_s$s \
      --save-at 10000000 --threads 3 $EXTRA > results/v2/train_${P}_s$s.log 2>&1 &
done; wait
python results/v2/_stage1_6b_compare.py checktrain --arms $X --seeds 5 6 7 8 9

# 5) 시드별 진단 (s = 5..9 동시. 시드 안에서는 이 순서 — permute·constsearch 가 ablate 의 C0 행을 다시 쓴다. 1-6 PREREG 10절 2)와 같다)
for s in 5 6 7 8 9; do (
  M="--config configs/v2_2.yaml --model ckpt/v2/${P}_s$s.zip --name ${P}_s$s --workers 3"
  python diagnose_v2.py ablate $M
  python diagnose_v2.py permute $M --obs pred_dist energy threat_recency
  python diagnose_v2.py constsearch $M --const-action $C2
  python diagnose_v2.py constsearch $M --tag c2seg_e1b --seg-bins 2:0.5 4:0.5 --seg-dims speed --base-action $C2 --const-action $E1B
  python diagnose_v2.py constsearch $M --tag c2seg_e2 --seg-bins threat_recency:0.5,1 --seg-dims vigilance --base-action $C2 --const-action $E2S
  python diagnose_v2.py constsearch $M --out results/v2/diag_${P}_s$s/g998 --tag c2seg_e2_g998 --g998 \
      --seg-bins threat_recency:0.5,1 --seg-dims vigilance --base-action $C2 --const-action $E2S      # 참고 G_0.998
  python diagnose_v2.py curves $M
  python diagnose_v2.py r2 $M
  python diagnose_v2.py ablate --config configs/v2_2.yaml --model ckpt/v2/${P}_s$s.zip --name ${P}_s${s}_stoch \
      --act-mode stochastic --workers 3                                                            # 확률 모드 (#29)
  python results/v2/_stage1_6_v2_2.py b67 --prefix $P --sdir s1_6b --seed $s --workers 3          # B6·B7
) > results/v2/diag_${P}_s$s.log 2>&1 & done; wait

# 6) 묶음과 판정
python diagnose_v2.py report --config configs/v2_2.yaml --dirs ${P}_s5 ${P}_s6 ${P}_s7 ${P}_s8 ${P}_s9 --name $P
python diagnose_v2.py modecmp --config configs/v2_2.yaml --out results/v2/diag_$P --tag modecmp \
    --det ${P}_s5 ${P}_s6 ${P}_s7 ${P}_s8 ${P}_s9 \
    --stoch ${P}_s5_stoch ${P}_s6_stoch ${P}_s7_stoch ${P}_s8_stoch ${P}_s9_stoch
python results/v2/_stage1_6_v2_2.py judge --prefix $P --sdir s1_6b --seeds 5 6 7 8 9   # → results/v2/s1_6b/stage1_6_$P.json

# 7) 영상 (V·Q 는 stage1_6_$P.json 의 video.train_seed · video.png_step)
python replay_v2.py --config configs/v2_2.yaml --compare learned:ckpt/v2/${P}_s$V.zip perm:learned:ckpt/v2/${P}_s$V.zip \
    --labels "C0 학습 정책 (${P}_s$V)" "C1′ 행동 순열 (보행·경계 빈도 같음, 상태와의 짝만 끊김)" --seed 10000 --steps 1800 \
    --stride 2 --png $Q --png-dpi 150 \
    --caption "1-6b 판정 재실행 v2.2 팔 $X · 평가 시드 10000 · 같은 세계·카메라. 점 색: 정지 회색, 걷기 초록, 뛰기 주황 · 흰 테두리 = 경계" \
    --out results/v2/replay_${P}_compare.mp4
# 위 명령(실제 V·Q·X 값)을 replay_v2.py 머리 주석에 더한다
python -m pytest -q                                   # 494 passed, 1 skipped (평가 뒤)
```

- `compare`·`judge`·`b67`은 출력이 있으면 덮지 않는다. 기존 결과·체크포인트·캐시는 덮지 않는다(새 이름 `v2_2a_*`·`v2_2b_*`, `diag_v2_2a*`·`diag_v2_2b*`, `s1_6b/`만 쓴다). `precheck`가 학습 전에 이것을 확인한다.

## 7. 한계 (결과 보기 전에 적는다)

- 비교는 팔마다 학습 시드 3개다. 검정력이 낮아 팔 사이 G_γ 차가 유의하지 않을 수 있다. 그래서 규칙 (3)에 크기 통과 시드 수와 팔 A 우선을 정해 두었다. 비교 결과는 팔 선택에만 쓰고 1단계 판정이 아니다.
- 두 팔은 한 설정씩만 다르다. 둘을 함께 쓴 팔(ent_coef 3e-3 + 편향 0)과 4.7 (a) log_std 재설정은 비교하지 않는다. 비교는 '어느 쪽이 붕괴를 막는가'만 답하고 원인을 나누지 않는다.
- 팔 A의 ent_coef 3e-3은 경계만이 아니라 모든 행동 차원의 엔트로피 항을 키운다(튜닝값의 약 3.3배). 계획서 4.7은 ent_coef 0.01에서 std 폭주 이력을 적었다. speed 등 다른 차원의 std·log_std를 기록한다.
- 팔 B의 결정 모드 시작 경계는 문턱 위아래로 갈리는 값이라, 학습 초기에 μ가 조금만 내려가도 결정 모드 경계가 0이 된다. 학습 초기의 결정 모드 값으로는 보지 않고, 붕괴 신호 (b)는 20M 모델로만 잰다.
- 붕괴 신호 (b) '결정 모드 경계 비율 > 0'은 아주 작은 경계(평가 시드 20 × 5000스텝 가운데 한 스텝이라도)도 붕괴 없음으로 친다. 경계가 쓸모 있는 크기인지는 크기 기준(B3 ≥ 0.2)이 따로 본다.
- 1-6 학습의 다른 실패 모습(포식자가 안 보일 때 과도한 정지, 아사율이 C2의 2배)은 두 팔 어느 쪽도 직접 겨냥하지 않는다. 이 실패는 학습 실패 칸(G_γ)이 함께 잡는다.
- 비교의 학습 실패는 E2 C2-seg 하나로 본다(사람 결정). 판정 재실행은 1-6대로 E1-b·E2 둘 다 본다.
- 판정 재실행의 학습 시드(5~9)가 1-6(0~4)과 달라 두 판정을 시드끼리 짝지어 비교하지 않는다. 학습 시드는 세계 선택 시드이기도 해 학습 세계 순서도 다르다.
- 1-6 PREREG 11절의 한계(학습 시드 5개, `b3_truth`의 측정 특성, B1·B3 쓸모가 같은 결과 지표, B4 v1 세계 기준선, C5 없음, v1 먹이)는 판정 재실행에 그대로 남는다.

## 8. 결과 뒤 약속

- 1~5절의 팔 정의·비교 지표·붕괴와 학습 실패의 정의·선택 규칙·판정 재실행의 시드와 규칙(1-6 PREREG 그대로)은 **결과를 본 뒤 바꾸지 않는다.**
- 선택 규칙이 고른 팔이 기대와 달라도 팔을 바꾸지 않는다. 후보가 없으면 판정 재실행을 하지 않는다. 비교 결과(`compare.json`)와 판정표는 덮지 않는다.
- 판정 재실행 결과가 불리해도 다시 학습하거나 시드·정의를 바꿔 다시 판정하지 않는다. 다음은 사람이 정하고, 하면 새 사전 등록으로 따로 적어 이 결과와 나란히 둔다.
- 결과를 본 뒤 더할 수 있는 것은 판정·선택에 쓰지 않는 기술용 열과 표뿐이다. 더하면 보고서에 "결과 뒤 추가"로 표시한다.
- 도구 결함으로 수치가 틀린 것을 찾으면 코드를 고쳐 다시 집계하고 변경 기록에 남긴다. 이때도 규칙은 바꾸지 않는다.

## 변경 기록

- 2026-10-03: 처음 작성(학습 전). 같은 날 결과 보기 전에 도구를 바꾸고 시험했다(판정·선택에 쓰는 값 없음):
  - `train_v2.py` `--ent-coef`·`--init-bias`와 메타 `config_digest`, `_stage1_6_v2_2.py` `--prefix`·`--sdir`·`--seeds` 일반화, `_stage1_6b_compare.py` 작성, 시험 28개 추가(pytest 494 통과 + 1 skip).
  - 일반화 재현: 기본 인자의 `judge`(scratchpad 출력)가 `s1_6/stage1_6_v2_2.json`과 `generated`·`script` 칸만 다르다. 일반화한 `b67`(학습 시드 1, 평가 시드 10000·10007, scratchpad 출력)의 C0·C1′ 행이 `s1_6/b67_v2_2_s1.json`의 같은 행과 같다.
  - 비교 도구 시험(scratchpad): `configs/v2_2.yaml`로 팔 A·B × 시드 0·1을 98,304스텝 학습(`armargs`의 옵션) → `checktrain --smoke`(팔 A 시작 경계 확률 0.200~0.201, 팔 B 0.499~0.500) → 진단(평가 시드 2개 × 1500스텝, 보정 시드 2개 × 300스텝, 보정 캐시도 scratchpad) → `compare --smoke --collapse-step 65536`까지 끝까지 돌았다. 그 작은 모델은 두 팔 모두 결정 모드 경계가 0이었다(팔 B는 3회 갱신 뒤 vigilance μ 평균 약 −0.16). 이 값들은 판정·선택에 쓰지 않는다. 규칙 변경 없음.
