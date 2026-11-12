# R9 동물 세계 1 단계 — 학습·시험 시작 (물소·표범·여우 + 사슴·늑대·멧돼지)

설계: `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md` (몸 표 3 절·몸 규칙 4 절·기대 5 절·학습 계획 6 절·시험·보고 7 절).
설정: `herbivore_rl/configs/v3_r9_fauna.yaml` (옛 `v3_r9.yaml`·`v3_r9_judge.yaml` 은 바이트 그대로 — 새 설정을 쓸 때만 새 몸 규칙이 켜진다).

- 모든 명령은 `herbivore_rl/` 폴더에서. 한 줄씩 복사해 쓴다(PowerShell).
- 시험 비행은 **정식 풀 밖·S′ 관문 전 값**이다. 결과는 '몸 숫자가 맞나' 확인용이고 판정이 아니다.
- 물소 물가는 2 단계(섬 지형·물), 쥐·까마귀는 3 단계다. 1 단계는 평지다.

## 0. 시작 판 복사 (한 번 — 2026-11-13 구현 때 해 두었다)

`ckpt/` 는 git 밖이다. 데모 두뇌(옛 세 종 출발점)를 동물 세계 시작 폴더로 복사한다.

```powershell
$src = "C:\Users\Sinhyeok\AppData\Local\Temp\claude\C--kwon-univ-3-1-GameContentsCapstoneDesign-AdaptiveEcosystem\929c780f-6f46-4644-81c6-914789098bd9\scratchpad\r9\demo\ckpt\A"
New-Item -ItemType Directory -Force ckpt\r9_fauna\start\src | Out-Null
foreach ($n in "deer_r0_20013056", "wolf_r0_7845120", "boar_r0_10027008") { foreach ($e in "zip", "npz", "json") { Copy-Item "$src\$n.$e" ckpt\r9_fauna\start\src\ } }
```

- 있는지 보기: `Get-ChildItem ckpt\r9_fauna\start\src` → 파일 9 개.

## 1. 시험 (구현 확인 — 학습 전에)

```powershell
$env:OMP_NUM_THREADS="1"; $env:MKL_NUM_THREADS="1"; $env:PYTHONDONTWRITEBYTECODE="1"
python -m pytest -p no:cacheprovider tests/test_r9_fauna.py
```

- 약 1~2 분. F-1(S′ 비트 같음)·F-2~F-13(몸 규칙·감각·이름표 없음·난수·학습 줄기 작은 스모크·몸 점검·규칙 두뇌 가지·은신처 보호·변형·조각) 모두 통과해야 시험 비행.
- 옛 시험 전부(STATUS 8 절 C0-8 명령 + 동물 시험, 약 7 분):

```powershell
python -m pytest -p no:cacheprovider tests/test_r9.py tests/test_r9_body.py tests/test_r9_brains.py tests/test_r9_life.py tests/test_r9_eval.py tests/test_r9_eval_s.py tests/test_r9_s_world.py tests/test_r9_train.py tests/test_r8.py tests/test_vec_env.py tests/test_rep_policy_v3.py tests/test_r9_fauna.py
```

- 설계 F-9 그대로의 학습 줄기 스모크(물소·표범·여우 각 10만 결정, 세계 12, 시드 44180~44199, 약 5 분):

```powershell
$env:R9_FAUNA_F9_FULL="1"; python -m pytest -p no:cacheprovider tests/test_r9_fauna.py -k f9_train; Remove-Item Env:R9_FAUNA_F9_FULL
```

## 2. 몸 점검 보고 (학습 없이, 규칙 두뇌만 — 몇 분)

```powershell
python -X utf8 results/v3/r9/fauna_report.py --rules-only --worlds 12 --decisions 300 --name rules_check
```

- 결과 `results/v3/r9/fauna_reports/rules_check.md`·`.json`. 규칙 두뇌는 잣대일 뿐이라 숫자는 '몸이 그렇게 할 수 있나'만 본다.

## 3. 시험 비행 (학습 — 사용자 확인 뒤에만 띄운다, 약 3 시간)

먼저 명령만 보기:

```powershell
python -X utf8 results/v3/r9/fauna_flight.py --branch A --dry-run
```

띄우기(창 없는 떨어진 프로세스):

```powershell
python -X utf8 results/v3/r9/spawn_detached.py --log results/v3/r9/logs/fauna_flight_A.log --what "fauna flight A" -- results/v3/r9/fauna_flight.py --branch A
```

- 0 단계(수 초): 옛 세 종 데모 두뇌를 동물 세계 몸으로 옮김(`rebody_r9.py`) → `ckpt/r9_fauna/start/{deer,wolf,boar}_v0.npz` (메타 `init_from` 에 원래 몸 해시).
- 1 단계(약 1.4 시간, 프로세스 6 개): 물소 10M(멧돼지 zip 에서)·표범 5M(늑대 zip)·여우 5M(늑대 zip) 동시에. 상대 = 옛 세 종 v0, 새 종끼리 규칙 두뇌.
- 2 단계(약 1.1 시간): 늑대 10M 이어 배우기(학습률 1e-4). 상대 = 사슴·멧돼지 v0, 물소·표범·여우 = 1 단계 마지막 판.
- 3 단계(약 30 분): `fauna_report.py --flight ckpt/r9_fauna/flight/A`.
- 진행 보기: `Get-Content results/v3/r9/logs/fauna_flight_A.log -Tail 20`, 묶음별 화면 `results/v3/r9/logs/fl_A_<종>.log`, 학습 기록 줄 `results/v3/r9/logs/fl_A_<종>.log.jsonl`(5M 마다 한 줄 — `fauna` 칸에 종 사이 죽임·받기).
- 단계 기록: `ckpt/r9_fauna/flight/A/flight.json`(명령·시작/끝·멈춤 이유·결과 판·sha256). 한 묶음이라도 `error`·`nan`·`cut` 이면 그 단계에서 멈추고 적는다.
- 묶음 하나만 따로(예: 물소): `fauna_flight.py --dry-run` 이 찍은 줄 하나를 그대로 쓴다.

## 4. 보고만 다시 (시험 비행 뒤)

```powershell
python -X utf8 results/v3/r9/fauna_report.py --flight ckpt/r9_fauna/flight/A
```

- 결과 `results/v3/r9/fauna_reports/flight_A.md`·`.json`. 학습 두뇌 판과 규칙 두뇌 판을 나란히 적는다. 행동은 가장 높은 칸(판정과 같음, `--stochastic` 이면 확률).
- 일부만: `--only S1` · `--only S2` · `--only N`. 두뇌를 바꿔 끼우기: `--brains wolf=ckpt/…/wolf_r0_….npz buffalo=…`.

## 5. 결과 읽는 법 (보고만 — 판정 숫자 없음)

| 칸 | 무엇 | 기대 (설계 5·7 절) | 이상 신호 |
|---|---|---|---|
| S1 | 늑대 n(1·2·3·4·6) 마리 대 물소 무리(어른 3 + 송아지 1), 칸마다 40 세계 × 300 결정 | 1~2 마리는 어른을 거의 못 잡고 다치거나 죽음, 3~4 마리부터 오름 (MacNulty 2014: 혼자 0.01, 마리당 오즈 × 1.4) | 어른 1 마리 성공 ≥ 0.2 (물소가 너무 쉬움) |
| S2 | 늑대 1 ↔ 표범 1 | 대개 다치고 떨어짐 | '둘 다 죽음' 잦음 |
| T-A (N) | 자연 세계 덤빔: 무리 크기 × 물소 나이 × 그 세계 사슴 수 | 사슴 많은 칸의 어른 물소 덤빔 0 은 **정상**. buffalo_land 꼴에서 무리 덤빔이 늘어남, 송아지 먼저 | — |
| T-C | 물소가 늑대·표범 위협(5 단위 안 다가옴) 때 마주 봄·도망·받기·동족 거리 | 줄지어 맞섬 | 도망 > 마주 봄 |
| T-D | 표범 죽임 종·무게 띠별 Jacobs D (−1 피함 ~ +1 고름) | 멧돼지·새끼·여우 위주 | 어른 사슴 죽임이 대부분 |
| T-H | 종 사이 죽임 표(물림·반격·받기), 표범 죽음 원인, 은신처 안 물림, 물소 받기 HP | 늑대 ↔ 표범 드묾, 물소의 초식동물 받기 ≈ 0 | 물소가 사슴·멧돼지를 자주 받음 |
| T-K | 사슴이 느낀 늑대·표범이 6 칸에서 밀려난 몫 | ≤ 1% | > 5% 면 2 단계 칸 바꿈(6 → 10) 앞당김 |
| T-M | 표범·여우 가장 가까운 동족 거리, 함께 덤빔 몫 | 현실은 혼자 — 1 단계엔 같은 종 다툼이 없어 꼭 혼자일 까닭이 없음(보고만) | — |
| C0-F9 | 묶음별 결정/초 | 정식 묶음 결정 수 등록에 씀 | — |

- 등록 문장: "사슴이 많은 세계에서 늑대가 어른 물소를 안 건드리는 것은 이상 신호가 아니다. '무리로 잡을 수 있나'는 장면 S1, '실제로 무리로 덤비나'는 buffalo_land 꼴 자연 세계로 본다."
- 첫 밤으로는 늑대 협력이 안 보일 수 있다(몇 바퀴 필요). 안 나오면 '안 나왔다'고 적는다 — 몸 숫자를 결과에 맞춰 고치지 않는다.

## 6. 시드·범위

- 스모크·속도 44180~44199 · 동물 학습 풀 46000~46499 · 보고 장면·자연 세계 46680~46719 · 동물 판정 46800~46999(46900~46999 는 학습 코드가 거부).
- 1b 로 미룬 것: 판정 6 종 세계(`v3_r9_fauna_judge.yaml`)·리그 묶음 G·H·나머지 지표(T-B·E·F·G·I·J·L)·C0-F7/F2/F12/F14. 언리얼 옮김은 2 단계 입출력이 정해진 뒤 한 번.
