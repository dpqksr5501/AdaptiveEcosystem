# R9 클라우드 학습 안내 — 다른 컴퓨터·OpenAI Dots 에서 6 종 이어 학습

작성 2026-11-13 · RL 담당 권신혁 · 코드 `herbivore_rl/results/v3/r9/chain_r9.py`·`pack_r9.py` · 출발 팩 `herbivore_rl/results/v3/r9/packs/fauna_r2/`

## 0. 한눈에

**로컬 개발과 Dots 실행 범위.** 로컬에서 언리얼 섬의 먹이·식생·물길·날씨와 Python 대응 세계를 개발하고, RL 담당이 정책 계약과 학습 설정을 확정한다. Dots는 고정된 커밋과 팩으로 학습을 수행한다. 현재 실행기는 사슴·늑대·멧돼지·물소·표범·여우 6종을 이어 학습한다. 16종 학습은 종별 감각·이동·먹이 및 Python–언리얼 검증이 끝난 별도 인계본에서 시작한다. [환경 개발·검증 순서](../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#로컬-환경-개발과-dots-학습)

**실행 전 인계.** 승인 커밋, 설정과 출발 팩, 줄 이름, 라운드 수 또는 시간 한도, 중단 기준, 결과 보관 위치를 확인한다. 아래 실행 예시의 10라운드는 학습 규모 예시다. 준비 검토만 요청받았으면 접근 가능 여부, 예상 자원, 재개 조건과 명령을 먼저 보고한다. 실제 실행을 승인받은 뒤 설치·팩 검사·대상 테스트·스모크 순서로 진행한다.

- **무엇**: R9 동물 세계 6 종(사슴·늑대·멧돼지·물소·표범·여우) 두뇌를 이 PC 가 아닌 컴퓨터(리눅스 클라우드)에서 **이어 학습**한다.
  언리얼·GPU 는 필요 없다. 파이썬과 CPU 만 쓴다.
- **받는 것**: 저장소의 파이썬 부분 + 출발 팩(6 종 두뇌, 4.2 MB).
- **하는 것**: 설치 → 확인 → 작은 시험 → 학습 띄우기 → 가끔 진행 보기.
- **돌려주는 것**: 학습한 마지막 판을 팩으로 묶어 새 가지 `r9-train/<줄 이름>` 에 push 한다.
- **하지 않는 것**: 세계 규칙·보상·관측·행동·몸 숫자·설정 파일 바꾸기, 판정 시드 쓰기, 언리얼·C++ 빌드. 이것들은 RL 담당이 정한다(9 절).
- **누가 무엇을 정하나**: 어느 설정으로 몇 바퀴를 돌릴지는 RL 담당이 알려 준다. 아래 예시는 2026-11-13 에 정한 **M1 회전 한계 세계**
  (`configs/v3_r9_fauna_motion.yaml`, [몸 움직임 설계](RL_R9_TURN_EFFORT_DESIGN.md))다.
  이 PC 에서 바퀴 1·2 를 지킴 선과 함께 보는 중이고, 그 결과를 보고 몇 바퀴를 더 돌릴지 정한다.

## 1. 구조 — 무엇이 어디서 돌고 무엇이 오가나

### 16종 확장에 필요한 대응 장면

현재 Python `species_of()`는 6종까지 허용한다. 내부 목록에 쥐·까마귀 이름이 있어도 현재 설정 검사는 둘을 거부한다. 언리얼 섬에서 사슴은 R7e, 늑대는 Native v3 위협 규칙을 사용하며 나머지 종의 권위 동작은 각 규칙 실행기가 맡는다. R9의 기존 6종은 Python 학습과 비교 기준에 사용한다. [Python 종 검증](../../../herbivore_rl/env_v2/r9_body.py) · [언리얼 실행기 진단](../../Source/AdaptiveEcosystem/Creature/Debug/EcoCreatureInspection.cpp)

| 실행기 | 추가 종 | Python–언리얼 첫 대응 장면에서 비교할 결과 |
| --- | --- | --- |
| 지상 | 쥐, 큰뿔양, 산토끼 계열, 말 | 같은 경사·단차·몸 배율에서 통과 또는 정지. 같은 재고의 두 군락에서 선택 요청, 도착, 실제 차감과 에너지 지급. 쥐는 먹이터와 가림 사이의 통과도 기록한다. |
| 비행 | 까마귀, 검독수리 | 이륙·순항·착지 요청과 실제 단계, 착지 표면이 막혔을 때의 결과. 검독수리는 급강하 후 접촉과 섭취, 까마귀는 사체 도착과 섭취를 기록한다. |
| 수륙 | 밍크 | 같은 하상과 저수위·고수위에서 입수, 유영, 상륙, 실패 후 다른 출구 이용과 도착 후 섭취. |
| 유영 | 아리아케 메기류, 잉어, 가상 담수 소형어류 | 같은 깊이·유속에서 몸체 통과, 먹이 접근과 실제 지급. 산란장 예약·퇴수·치어 연결은 별도 장면으로 비교한다. |

첫 인계는 작은 장면별 입력과 실제 결과를 버전으로 고정한다. 종 ID·몸 크기·단위·시간 스텝, 개체 초기 상태, 월드 입력, 요청·허용·실행 결과, 거래 영수증을 기록한다. 진단이 아는 전체 재고·대상 ID를 정책에 노출하는지는 RL 담당이 감각 계약에서 정한다. 종 목록, 스키마 및 몸 해시 변경은 RL 담당의 버전과 기존 팩 호환 검증을 거친다. 현재 표의 신규 장면은 `training_ready=false`이며 Python 실행이나 신규 모델 학습 증거는 섬 결과와 별도로 남긴다. [언리얼 현장 비교](../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md) · [기존 부분 예제의 제한](Examples/README.md)

최신 섬의 30·60게임분 보고서는 종별 활성 실행기, 권위 시각, 지역별 개체 수와 작성 먹이 재고를 담는다. 새 두뇌를 인계받으면 같은 소유 맵·시드·시작 개체·재생 예산에서 실행기만 바꾼 비교에 사용한다. 종별 생존에 앞서 실제 먹이 지급과 고갈, 지역 이동, 수위에 따른 접근부터 대응시킨다. 이 장기 보고서는 집계 비교에 사용하며, 관측·행동 Golden Vector에는 별도의 같은 스텝 입력과 권위 실행 결과가 필요하다. [최신 섬 장기 기준선](../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md#최신-저장본의-종별-장기-비교)

11월 14일 로컬에서 원래 Fauna 설정으로 출발 팩의 6종 몸 해시가 모두 일치했다. M1 설정에서는 파일·I/O 검사를 통과했고, 6종 몸 해시 차이는 기존 M1 상대 정책 변환 경로의 입력으로 확인했다. `chain_r9.py run --dry-run`도 6종 명령을 생성했다. 이 검증의 범위는 로컬 팩과 실행 계획이다. 실제 Dots 환경의 패키지 설치, 스모크, 본 학습은 Dots 기록에서 확인한다. 신규 종은 [수변 발췌](Examples/island_shore_recovery_actual_20261114.json)를 포함한 대응 장면을 사용한다.

같은 날 Windows 환경에서 4절의 세 테스트 파일을 재실행해 41개 통과, 1개 건너뜀, 1개 실패를 확인했다. 건너뛴 테스트는 데모 출발 두뇌 복사본을 요구한다. 다중 프로세스 늑대의 결과 일치 테스트는 작업 프로세스와 Windows named pipe 연결이 120초 안에 성립하지 않아 비교까지 진행하지 못했다. Python 표준 라이브러리만 쓴 별도 자식 프로세스에서도 서버가 파이프를 연 뒤 부모의 연결이 성립하지 않았다. Dots Linux에서는 Unix 소켓을 쓰므로 현지에서 같은 테스트와 스모크를 실행해 다중 프로세스를 확인한다.

같은 날 19시 50분대에 Python 3.12.13 환경에서 다시 실행했다. 42개 통과·1개 건너뜀·실패 0으로, 앞서 연결에 실패했던 다중 프로세스 테스트도 포함됐다. 원래 Fauna 설정에서 출발 팩의 여섯 몸 해시가 다시 일치했다. Dots Linux에서의 시험 결과는 현지 실행으로 확인한다.

여섯 NPZ를 원래 Fauna 장면의 몸 해시와 대조한 뒤 별도 로컬 폴더에 `.r9brain`으로 내보냈다. 시드 44190의 Unreal R9 데모가 여섯 파일의 페이로드 해시를 표시했고, 실시간 112스텝을 실행한 뒤 정상 종료했다. 데모는 같은 레벨의 지형에서 자체 개체군과 자원으로 실행한다. 이 결과는 파일 내보내기·로더·C++ 추론을 확인하며, 섬 권위 실행기와 연결하는 경로는 별도다. 원본은 `Saved/Logs/IslandHandoffFaunaR2.log`에 있다.

사체 비교는 [최신 섬의 플레이어 사냥 표본과 R9 기준 실행](Examples/README.md#플레이어-사냥에서-공유-사체와-섭취까지)을 사용한다. 기존 M1에서는 사체를 입력한 뒤 섭취 거리·자리·요청·감소량을 개발 시드로 실행했다. 플레이어가 생성한 사체, 라이브 먹이로의 전환, 위협 이탈과 Unreal의 만료 거래는 같은 입력으로 맞춰야 할 환경 차이다. 섬의 사체 수치를 R9 고기 단위로 직접 가져오거나 이 발췌를 신규 학습 입력으로 사용하지 않는다.

### 기존 6종 실행 흐름

```
[GitHub 저장소]  코드 + 출발 팩(packs/fauna_r2)
      │  git clone (언리얼 에셋·LFS 빼고, herbivore_rl 만)
      ▼
[클라우드 컴퓨터]  cloud_setup.sh → chain_r9.py check → run --smoke → run --detach
      │  ckpt/r9_cloud/<줄>/  (판·기록 — git 밖, 컴퓨터 안에만)
      │  chain_r9.py pack → packs/<줄>_r<N>/ (돌려줄 판·보고, 약 5 MB)
      ▼  git push origin r9-train/<줄>
[RL 담당 PC]  pack_r9.py verify → 다음 줄의 출발 팩 또는 R9 데모 검증용으로 사용
```

- `swap_brain.py`의 출력은 Unreal의 별도 R9 데모용 `.r9brain`이다. 최신 JYU 섬에서 같은 종을 비교하려면 섬의 권위 관측과 요청·실행 경로를 연결하고 실제 구동 실행기를 확인한다. [데모 내보내기](../../../herbivore_rl/results/v3/r9/swap_brain.py) · [섬 비교 절차](Examples/README.md#향후-두뇌-수령-시-섬에서-비교하는-절차)
- **팩**은 판(두뇌)을 옮기는 단위다. `manifest.json` 에 모든 파일의 sha256 과 몸 해시를 적는다. 받는 쪽은 `verify` 로 같은 판인지 확인한다.
  출발 팩과 돌려받는 팩의 꼴이 같다. 그래서 돌려받은 팩을 다음 학습의 출발 팩으로 그대로 쓸 수 있다.
- **줄**은 이어 학습 하나다(예 `dots1`). 줄마다 출발 팩·설정·모델 시드·묶음 크기가 `plan.json` 에 고정된다.
  끊겨도 같은 명령을 다시 내리면 이어 간다.
- **바퀴** r 하나: 6 종이 동시에 자기 앞 바퀴 마지막 판에서 이어 배운다(종마다 5M 결정). 상대는 다른 종의 팩 판과 바퀴 r 앞의 모든 판이다
  (지금 판 50%·예전 판 30%·규칙 두뇌 20%). 모두 끝나면 자연 세계 N 보고를 남긴다.
  이 PC 의 `fauna_chain`·`motion_chain`(2026-11-13)과 같은 방식이다.

## 2. 클라우드 환경 조건

| 항목 | 필요 | 비고 |
|---|---|---|
| 운영체제 | 리눅스 (윈도우·맥도 됨) | 2026-11-13 WSL 우분투 24.04 에서 새로 받기부터 학습까지 확인 (12 절) |
| 파이썬 | 3.12 이상 | 확인한 판 3.12·3.13. 시스템 파이썬이 3.12 보다 낮으면(데비안 12 = 3.11) 설치 스크립트가 uv 로 3.12 를 받는다. 학습 줄기는 3.10·3.11 문법으로도 읽히지만 판정 도구 `eval_r9.py` 는 3.12 문법이다 |
| 권한 | sudo 필요 없음 | 가상 환경은 저장소 안 `herbivore_rl/.venv-r9/` |
| 인터넷 | 설치 때만 | github.com, pypi.org, download.pytorch.org, astral.sh(uv) |
| GPU | 쓰지 않음 | torch 는 CPU 판(약 200 MB). CUDA 판(수 GB)은 깔지 않는다 |
| CPU·메모리 | 6 종 기본: 프로세스 10 개 ≈ 4.5 GB | CPU 가 8 개 이하이거나 메모리가 빠듯하면 실행기가 프로세스 6 개(≈ 2.7 GB)로 줄인다. 프로세스 수는 속도만 바꾸고 결과는 같다 |
| 디스크 | 약 2 GB | 가상 환경 ≈ 1.2 GB, 파이썬 checkout ≈ 280 MB, 10 바퀴 판 ≈ 0.3 GB |

- **OpenAI Dots**: 2026-09 에 나온 에이전트이고, 에이전트마다 따로 클라우드 컴퓨터를 쓴다. 공식 사양은 아직 공개되지 않았다.
  공개 보고에 따르면 데비안 VM, vCPU 약 9 개, 메모리 약 10 GB, GPU 없음, sudo 없음이다 [확인 안 됨].
  실제 값은 `chain_r9.py check` 가 첫 줄에 적는다.
- **속도 어림**: 이 PC(20 코어, 10 프로세스 동시)에서 M1 세계 1 바퀴 = 종마다 5M 결정이다. 결정/초는 사슴 3,500, 늑대·멧돼지·물소 약 1,200, 표범·여우 약 1,000 이다.
  가장 느린 종에 맞춰 약 1.5 시간 + 평가 약 5 분이 걸린다. vCPU 9 개 클라우드는 1.5~2 배 느릴 수 있다 [어림]. 실제 값은 `status` 의 결정/초로 본다.

## 3. 받기 — 언리얼 에셋 없이 파이썬 부분만

저장소에는 언리얼 에셋이 Git LFS 파일 4,456 개(수 GB) 들어 있다. 학습에는 필요 없다. LFS 를 받으면 팀 LFS 전송량만 줄어든다.

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none --no-checkout https://github.com/dpqksr5501/AdaptiveEcosystem.git
cd AdaptiveEcosystem
git sparse-checkout set --cone herbivore_rl AdaptiveEcosystem/Docs/RL_Policy
GIT_LFS_SKIP_SMUDGE=1 git checkout Branch_Sinhyeok
```

- 받는 양은 약 280 MB 다(파이썬·결과 기록·RL 문서). 저장소 루트 `AGENTS.md` 도 함께 온다.
- 클라우드에서 읽기 접근을 먼저 확인한다. 결과 브랜치로 돌려줄 때(7 절)는 쓰기 권한도 필요하다.
  **토큰·비밀번호를 파일·로그·커밋·채팅 기록에 적지 않는다.**
- 나중에 새 코드를 받을 때: `git pull` (같은 sparse 설정이 유지된다).

섬 대응 자료를 받은 커밋에서 Python으로 재생하려면 아래 경로를 추가한다. 이 검사는 엔진·학습 의존성 없이 실행되며, 소유 섬에서 기록한 먹이·수위·비행 결과와 대응 코드의 입출력을 확인한다. [재생할 수 있는 섬 자료](Examples/README.md#엔진-없이-실행하는-섬-대조)

```bash
git sparse-checkout add AdaptiveEcosystem/Tools/EcoVegetationEval
```

Dots에서 시작할 때는 검증한 PR 커밋을 체크아웃하고 `git rev-parse HEAD`를 줄 기록에 남긴다. 같은 줄을 재개할 때는 해당 커밋과 출발 팩, 설정을 사용한다. 클라우드 VM 교체 후에도 디스크가 유지되는지 먼저 확인한다. 유지가 보장되지 않으면 완료된 바퀴마다 결과 팩을 외부에 보관하고, 새 VM에서 같은 줄을 그대로 재개해야 할 경우에는 해당 줄의 `ckpt/r9_cloud/<줄>/`도 함께 백업한다. 결과 팩만 있으면 그 팩을 출발점으로 새 줄을 만든다.

## 4. 설치와 확인

```bash
bash herbivore_rl/results/v3/r9/cloud_setup.sh
```

- `herbivore_rl/.venv-r9/` 에 가상 환경을 만든다. 그다음 CPU torch 와 `herbivore_rl/requirements-r9.txt` 를 깐다.
  다시 불러도 되고, 그때는 빠진 것만 깐다.
- `python3 -m venv` 가 안 되는 컴퓨터(데비안·우분투에 `python3-venv` 가 없을 때 흔함)에서는 uv 를 `~/.local/bin` 에 받아 쓴다.
- 끝에 `chain_r9.py check` 가 돈다. 파이썬·패키지·CPU·메모리·디스크·팩 sha256·몸 해시·동시 프로세스 수를 보고 `결과: 통과` 를 적어야 한다.

아래 명령은 모두 `herbivore_rl/` 폴더에서 이 두 줄을 먼저 하고 쓴다.

```bash
cd herbivore_rl
export PYTHONUTF8=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
PY=.venv-r9/bin/python
```

시험 (약 2~4 분): 팩·실행기 시험, 그리고 이 컴퓨터의 세계가 윈도우에서 잰 기준과 비트까지 같은지(F-1·M-1) 본다.

```bash
$PY -m pytest -p no:cacheprovider -q tests/test_r9_chain.py tests/test_r9_fauna.py tests/test_r9_motion.py
```

전체 R9 평가·리플레이 테스트까지 실행할 때는 같은 Python 환경에 `scikit-learn`과 `matplotlib`를 설치한다. 두 패키지는 클라우드 학습 전용 설치 목록에서 제외되어 있다.

작은 학습 (약 5~10 분, 학습 줄과 섞이지 않게 `ckpt/r9_cloud_smoke/` 에 쓴다):

```bash
$PY -X utf8 results/v3/r9/chain_r9.py run --pack results/v3/r9/packs/fauna_r2 --config configs/v3_r9_fauna_motion.yaml --line dots1 --smoke
```

- 마지막 줄에 `끝 — 바퀴 2 까지 다 돎` 이 나와야 한다. 기록은 `ckpt/r9_cloud_smoke/dots1/chain.log` 에 남는다.

## 5. 학습 띄우기·보기·멈추기

```bash
# 계획만 보기 (아무것도 띄우지 않음)
$PY -X utf8 results/v3/r9/chain_r9.py run --pack results/v3/r9/packs/fauna_r2 --config configs/v3_r9_fauna_motion.yaml --line dots1 --rounds 10 --dry-run
# 띄우기 — 창 없이 떨어진 프로세스로 띄우고 바로 돌아온다 (셸이 끊겨도 계속 돈다)
$PY -X utf8 results/v3/r9/chain_r9.py run --pack results/v3/r9/packs/fauna_r2 --config configs/v3_r9_fauna_motion.yaml --line dots1 --rounds 10 --detach
# 진행 보기 (종마다 최신 판·결정/초·마지막 평가·기록 끝 8 줄)
$PY -X utf8 results/v3/r9/chain_r9.py status --line dots1
# 멈추기: 지금 바퀴는 끝내고 다음 바퀴를 안 띄움 / --now 는 도는 묶음도 끝냄 (그 바퀴는 다음에 처음부터)
$PY -X utf8 results/v3/r9/chain_r9.py stop --line dots1 [--now]
```

- **이어 가기**: 컴퓨터가 다시 켜지거나 실행기가 죽었으면 **같은 run 명령**을 다시 내린다. 끝난 바퀴·묶음은 건너뛴다.
  끝 기록 없이 끊긴 묶음은 그 바퀴 판을 `_partial/` 로 옮기고 앞 바퀴 마지막 판에서 다시 한다(종마다 최대 3 번).
  아직 살아 있는 학습 프로세스는 다시 띄우지 않고 기다린다. 같은 줄의 실행기가 두 개 뜨지 않게 막는다.
- **멈춘 뒤 다시**: `ckpt/r9_cloud/<줄>/STOP` 파일을 지우고 같은 run 명령을 내린다.
- **바퀴 늘리기**: `--rounds 14` 처럼 더 큰 수로 같은 명령을 내린다.
- **시각 상한**: `--until 2026-11-20T09:00` 을 주면 그 시각 전에 끝낼 수 없는 바퀴는 띄우지 않는다.
- **줄 이름**: 컴퓨터·사람·실험마다 다른 이름을 쓴다(`dots1`, `dots2`, `hj-m1` …). 소문자로 시작한다. `A`·`B` 는 이 PC 리그 갈래라 못 쓴다.
  같은 줄 이름을 두 컴퓨터에서 동시에 쓰지 않는다. 모델 시드는 줄 이름에서 정해지므로(100~999) 줄마다 다른 학습이 된다.

| 줄에 고정되는 값 (`plan.json`, 바꾸면 거부) | 다시 띄울 때 바꿔도 되는 값 |
|---|---|
| 출발 팩·그 manifest sha256, 설정 파일과 설정 요약값, 종, 모델 시드, γ(0.99), 종마다 바퀴당 결정 수(5M), 판 저장 간격(1M), 상대 몫 | `--rounds`, `--until`, `--wall-hours`(묶음 벽시계 상한, 기본 4 h), `--shards`, `--eval-worlds`, `--round-hook` |

- 고정 값을 바꿔야 하면 새 줄 이름을 쓴다. `--replan` 은 같은 줄에서 바꾸고 `plan.json` 에 그 사실을 적는다. RL 담당이 시킬 때만 쓴다.
- **바퀴 뒤 검사 연결**: `--round-hook "<셸 명령>"` 은 바퀴마다 평가 뒤에 돈다. `{round}`·`{line_dir}`·`{config}`·`{python}` 을 바꿔 넣는다.
  0 이 아닌 값으로 끝나면 STOP 을 쓰고 멈춘다. 이 PC 의 M1 '지킴 선'처럼 사람이 볼 선을 연결하는 자리다.

줄 폴더 `herbivore_rl/ckpt/r9_cloud/<줄>/` (git 밖):

| 경로 | 내용 |
|---|---|
| `plan.json` · `state.json` · `chain.log` · `runner.out` | 고정 값 · 지금 단계·바퀴·도는 pid · 사건 기록 · 실행기 화면 |
| `start/` | 팩 몸이 설정 몸과 다를 때 옮긴(rebody) 상대 판 — 가중치는 그대로, 메타에 원래 판 sha256 |
| `<줄>/` | 판 `<종>_r<바퀴>_<결정>.zip·npz·json`, 묶음 끝 기록 `ch_<줄>_<종>_r<바퀴>.json` |
| `logs/` · `eval/` · `_partial/` | 묶음 화면·학습 줄(jsonl)·상대 판 목록 · 바퀴마다 자연 세계 N 보고 · 끊긴 시도 |

## 6. 몸이 다른 세계로 이어 가기 (rebody)

출발 팩 `fauna_r2` 는 지금 몸 세계(`configs/v3_r9_fauna.yaml`)에서 배운 판이다. M1 설정 몸 해시와 다르므로 `run` 이 상대 판 npz 를
`rebody_brain`(=`rebody_r9.py` 와 같은 길)으로 M1 몸에 옮겨 `start/` 에 둔다. 가중치는 한 비트도 바꾸지 않고, 그 사실을 메타 `init_from` 에 적는다.
배우는 쪽은 팩 zip 에서 이어 배운다. 이 PC 의 `motion_chain` 과 같은 출발이다.
`pack_r9.py verify <팩> --config <설정>` 은 종마다 '이 설정 몸 그대로 / 몸 다름' 을 알려 준다.

## 7. 돌려주기

```bash
$PY -X utf8 results/v3/r9/chain_r9.py pack --line dots1              # → results/v3/r9/packs/dots1_r<마지막 바퀴>/
$PY -X utf8 results/v3/r9/pack_r9.py verify results/v3/r9/packs/dots1_r10 --config configs/v3_r9_fauna_motion.yaml
git switch -c r9-train/dots1
git add results/v3/r9/packs/dots1_r10
git commit -m "R9 클라우드 학습 dots1 바퀴 1~10 (M1 세계, 팩 fauna_r2 출발)"
git push -u origin r9-train/dots1
```

- 팩에는 종마다 마지막 판(zip·npz·json)이 들어간다. 바퀴별 평가 보고, 묶음 끝 기록, 학습 줄, `plan.json`·`state.json`·`chain.log` 도 함께 들어간다.
  크기는 약 5 MB 다. 바퀴마다 생기는 모든 판까지 넣으려면 `--versions all` 을 쓴다(10 바퀴면 약 200 MB — 권하지 않음).
- `Branch_Sinhyeok`·`main` 에 바로 push 하지 않는다. `ckpt/` 와 가상 환경은 올리지 않는다(.gitignore).
- 학습이 실패했어도 팩으로 돌려준다. 예: `pack --line dots1 --name dots1_err` 로 묶고, `ckpt/r9_cloud/dots1/logs/*.out` 끝부분을 커밋 메시지나 PR 에 붙인다.

## 8. 돌려받은 팩 쓰기 (RL 담당 PC)

```bash
git fetch origin r9-train/dots1
git checkout origin/r9-train/dots1 -- herbivore_rl/results/v3/r9/packs/dots1_r10
python -X utf8 results/v3/r9/pack_r9.py verify results/v3/r9/packs/dots1_r10 --config configs/v3_r9_fauna_motion.yaml
```

- **다음 학습의 출발 팩으로**: `chain_r9.py run --pack results/v3/r9/packs/dots1_r10 --config … --line <새 줄>`.
- **언리얼 데모에 넣기**: `swap_brain.py <종 npz …> --fauna` ([R9 README](../../../herbivore_rl/results/v3/r9/README.md) · swap_brain 머리말).
  장면(`scene.txt`)의 몸 해시가 두뇌와 같아야 들어간다. M1 두뇌는 M1 장면에만 들어간다([몸 움직임 설계](RL_R9_TURN_EFFORT_DESIGN.md) 10-8).
- **판정은 따로**: 돌려받은 팩은 '학습 판'이다. 관문·판정(J1~J3, 판정 시드 44800~44999)은 RL 담당이 이 PC 에서 한 번만 한다.

## 9. 지킬 것

1. 세계 규칙·보상·관측·행동·몸 숫자·설정 YAML 을 바꾸지 않는다. 바꿀 일이 생기면 RL 담당과 정한 뒤 **새 설정 파일 + 새 줄**로 한다.
   몸 해시 검사가 다른 몸의 두뇌가 조용히 섞이는 일을 막는다. 이 검사를 끄지 않는다.
2. 판정 시드 44800~44999 를 쓰지 않는다(`eval_r9.py judge`·`mixed` 를 돌리지 않음). 학습 시드는 설정 값(동물 세계 46000~46499)이다.
3. 언리얼·C++ 은 이 일과 상관없다. 빌드하거나 에셋을 받지 않는다.
4. 정책 출력·관측 계약(115 → 64 → 64 → 19)은 R9 계약이다. V1·v3 게임 기본 두뇌와 섞지 않는다(루트 `AGENTS.md`).
5. 개인 토큰·비밀번호를 저장소 파일·로그·커밋에 넣지 않는다. 학습 기록에도 경로 말고 비밀이 적히지 않는다.
6. 이 학습이 사용자·RL 담당의 다른 결정(예 M1 지킴 선)을 대신하지 않는다. 멈춤 선을 넘는 숫자가 보이면 멈추고 알린다.

## 10. 막힐 때

| 증상 | 할 일 |
|---|---|
| `python3 -m venv` 실패, `ensurepip` 없음 | 설치 스크립트가 uv 로 넘어간다. uv 를 못 받으면(인터넷 막힘) 그 컴퓨터에서 파이썬 3.10 이상 가상 환경을 만들고 `R9_VENV` 로 그 폴더를 가리킨다 |
| torch 설치가 수 GB 를 받음 | CUDA 판이다. `pip install --index-url https://download.pytorch.org/whl/cpu torch==2.11.0` 로 CPU 판을 먼저 깐다 |
| `plan.json 과 고정 값이 다르다` | 같은 줄을 다른 조건으로 띄웠다. 새 줄 이름을 쓴다 |
| `실행기가 이미 돈다` | `status` 로 본다. 정말 죽었는데 이 말이 나오면 `ckpt/r9_cloud/<줄>/runner.pid` 를 지운다 |
| 묶음 `cut`(MemoryError·조각 프로세스 잃음) | 실행기가 같은 바퀴를 다시 한다(최대 3 번). 반복되면 `--shards 1` 로 다시 띄운다 |
| 묶음 `error`·`nan` 으로 멈춤 | `logs/ch_<줄>_<종>_r<바퀴>.out` 끝을 보고 RL 담당에게 알린다. 같은 시드면 같은 실패라 그냥 다시 돌리지 않는다 |
| 너무 느림 | `status` 의 결정/초를 2 절 어림과 비교한다. CPU 가 프로세스 수보다 적으면 `--shards 1` 이 나을 수 있다 |
| 에이전트 셸 명령이 시간 초과로 끊김 | 학습은 `--detach` 로 띄운다. 에이전트는 가끔 `status` 만 부른다 |
| 다른 시험 `tests/test_r9_brains.py::test_16_numpy_equals_sb3_predict` 실패 (`1.14e-05 < 1e-05`) | 리눅스 CPU torch 에서 알려진 차이다. 로짓 최대 32 에서 numpy·torch 행렬 곱 반올림이 1e-5 기준을 조금 넘는다. 고르는 행동은 SB3 와 같고 동점에 가까운 경우도 0 이다(12 절). 학습에는 영향이 없다. 4 절 시험 셋에는 들어 있지 않다 |

## 11. Dots(또는 다른 코딩 에이전트)에게 줄 시작 지시문

```text
AdaptiveEcosystem 저장소의 R9 동물 두뇌 이어 학습을 이 클라우드 컴퓨터에서 돌려 줘.
안내서: AdaptiveEcosystem/Docs/RL_Policy/R9_CLOUD_TRAINING.md (3~7 절 차례대로). 저장소 루트 AGENTS.md 도 먼저 읽어.
- 실행 전 승인 SHA·설정·출발 팩·줄 이름·라운드 또는 시간 한도·중단 기준·결과 보관 위치를 확인한다. 아래 절차는 실행 승인 뒤 적용한다.
- 받기: 3 절의 sparse checkout 명령을 사용한다. 섬 대응 자료까지 재생하려면 같은 절의 선택 경로를 추가한다. Git LFS 에셋은 받지 않는다.
- 설치·확인: bash herbivore_rl/results/v3/r9/cloud_setup.sh → '결과: 통과' 확인 → 4 절 pytest → --smoke 학습.
- 학습: 줄 이름 <줄 이름>, 설정 <설정 파일>, 팩 results/v3/r9/packs/fauna_r2, 바퀴 <N> 으로 run --detach.
  그 뒤에는 가끔 status 만 보고, 바퀴가 끝날 때마다 마지막 평가 줄과 종마다 결정/초를 짧게 알려 줘.
- 끝나면 7 절대로 pack → verify → 새 가지 r9-train/<줄 이름> 에 커밋·push. Branch_Sinhyeok·main 에는 push 하지 마.
- 하지 말 것: 코드·설정·보상·관측·몸 숫자 바꾸기, 판정 시드(44800~44999) 쓰기, 언리얼 에셋 받기, 토큰을 파일에 적기.
  막히면 10 절을 보고, 안 풀리면 고치지 말고 멈춘 뒤 오류 끝부분을 알려 줘.
```

## 12. 확인 기록

- 로컬 작업본에서 출발 팩의 매니페스트와 Git 객체를 읽어 대조했다. 로컬 `origin/Branch_Sinhyeok` 기준 `062de0b741d6ae27ede2b454be18eb72ad6226d6`의 `herbivore_rl` 트리가 작업 커밋과 일치한다. `fauna_r2/manifest.json` SHA-256은 `016c748a6b221c78d0ea1f4012c107b88d64d3ee8d5ff857ec96009ef1fc27d6`이다. 목록 22개 파일의 SHA-256이 모두 맞고, 6종 ZIP·NPZ 압축 무결성, NPZ 배열 크기·종·원래 몸 해시와 공통 I/O 해시를 확인했다. 파일 검사에는 표준 라이브러리를 사용했다. Dots에서의 새 설치, 로드 및 학습 실행은 별도다. [Dots 인계 문서](DOTS_ECOSYSTEM_TRAINING_HANDOFF_KO.txt)
- 2026-11-13 윈도우(파이썬 3.13, numpy 2.1.3, torch 2.11.0+cpu, SB3 2.9.0): `tests/test_r9_chain.py` 9 통과. `run --dry-run`(M1 설정, 줄 dots1, 모델 시드 990) 명령 확인.
- 2026-11-13 WSL 우분투 24.04(CPU 20, 메모리 15.5 GB; 파이썬 3.12.3, `ensurepip` 없음, uv 없음, g++ 없음 — sudo 없는 클라우드와 같은 조건). 3 절 명령 그대로 진행했다.
  - 받기: 이 PC 저장소를 file:// 로 sparse clone 했다. 93 초, 360 MB.
  - 설치: `cloud_setup.sh` 가 venv 실패를 보고 uv 0.13.8 을 받았다. uv venv 3.12 로 torch 2.11.0+cpu(181 MB)·numpy 2.1.3·SB3 2.9.0·psutil 7.2.2 를 깔았고 `check` 통과까지 왔다.
  - 시험: `test_r9_chain`·`test_r9_fauna`(F-1 세계 sha256 이 윈도우 기준과 같음)·`test_r9_motion`·`test_r9_body`·`test_r9_brains` 62 통과, 1 건너뜀(g++ 없음), 1 실패.
    실패는 `test_16` 오차 기준(1.14e-5 > 1e-5, 로짓 최대 32)이다. 고르는 행동은 SB3 와 1,024 개 모두 같고 동점에 가까운 경우는 0 이다.
  - `run --smoke`(M1 설정, 줄 wsl1): rebody 6 종 → 바퀴 2 까지 212 초. 같은 명령을 다시 내리면 할 일 없이 끝난다. 다른 설정으로 같은 줄을 띄우면 거부한다.
    `pack` 은 83 파일·4.2 MB 이고 `verify` 를 통과했다.
  - `--detach` → `stop --now` → STOP 지우고 같은 명령: 학습·조각 프로세스 0 개로 정리, 끊긴 판은 `_partial/`, 띄운 횟수에 넣지 않고 바퀴 1 부터 다시 해 바퀴 2 까지 끝났다.
    이 시험에서 '멈춘 바퀴도 평가가 돈다'는 잘못을 찾아 고쳤다(`STOPPED`).
    고친 뒤(줄 wsl3) 다시 확인했다. 멈춘 바퀴에는 평가가 없다. 멈추기 전에 끝난 사슴 묶음은 그대로 두고 나머지 다섯 종만 다시 했다. 바퀴 1·2 평가가 모두 남았다.
  - 파이썬 3.10·3.11 문법: 학습 경로는 읽힌다. `results/v3/r9/eval_r9.py`(판정)·`gate_f.py`(옛 관문)는 3.12 문법이라 설치 스크립트가 3.12 를 고집한다.
