"""실시간 적응 고리 — 게임 중 레벨(팀)이 나무·날씨를 바꾸면 언리얼이 쓴 환경 스냅숏을 받아, 지금 사슴 두뇌를 늑대 포만 없는 세계에서 이어 배우고,
미리 적은 빠른 관문(results/v3/live/LIVE_GATE.md)을 넘은 두뇌만 언리얼이 지켜보는 폴더에 두뇌 파일로 쓴다 (10-20·10-21 사용자 '게임 중 실시간
두뇌 교체'). 환경을 바꾸는 규칙은 만들지 않는다 — 레벨이 바꾼 것을 옮길 뿐이다(10-20 '환경이 변하는 규칙은 우리가 만들지 않는다 — 레벨(팀) 작업').
한 판의 변환·세계 돌리기·끼임 세기·두뇌 파일 확인은 results/v3/adapt/adapt.py 를 그대로 쓴다.
10-21 (3) 사용자 기준 바꿈: 1차 = '잘 안 잡히는 두뇌'가 아니라 '똑같이 도망을 가도 숲속으로 잘 숨어 늑대 시야에서 벗어나 도망 시간이 짧은 두뇌'
— 포만 없는 세계에서 스스로 벗어난 도망(은신처에 숨거나·나무 줄기·바위가 늑대 눈길을 가리거나·늑대 시야각·시야 반경 밖으로 빠져 쫓기를 끝냄)의
쫓긴 시간(도망 시작부터 늑대가 이 사슴을 마지막으로 표적으로 둔 순간까지)이 유의하게 짧다. 잡힘·도망 횟수·달린 시간·잡혀 끝난 도망은 지킴(유의하게
나빠지지 않음)이다. 도망 = FLEE 를 실행한 스텝 묶음(도주 반사·두뇌가 고른 FLEE 모두) — env_v2/world.py 모듈 docstring '야생 1단계' (w3) 도망 기록
(World.flight_stats, 판정 실행기가 켠다). 이 기준의 크기는 예비 측정 뒤 확정한다 — 확정 전(LIVE flight_sizes_confirmed 거짓)에는 실제 폴더에서 판·감시를
돌리지 않는다.

    # herbivore_rl/ 에서 (Anaconda base python, PYTHONUTF8=1)
    python results/v3/live/live.py watch                        # 감시: <프로젝트>/Saved/EcoAdapt/snapshots 를 2초마다 보고, 새 환경이면 한 판
                                                                  #   (켠 뒤에 생긴 스냅숏만 — 있던 것도 보려면 --existing)
    python results/v3/live/live.py round --snapshot <파일>        # 한 판 (앞에서 — 감시 없이)
    python results/v3/live/live.py pilot --snapshot <파일>        # 예비 측정 (시드 34900~34999 만 — 관문 크기를 고르려고, 관문이 아니다)
    python results/v3/live/live.py pilot --snapshot <파일> --extra-models a=ckpt/v3/x.zip --flight-cost 0 0.005   # 더 견줄 두뇌·도주 비용 후보
    # 시험 크기 (관문 상수가 아님 — --root 로 다른 폴더를 줄 때만 받는다, 실제 brains 폴더에는 쓰지 않는다)
    python results/v3/live/live.py round --snapshot <파일> --root <임시 폴더> --steps 20000 --judge-seeds 35000-35002 --horizon 300 --workers 4

주고받는 파일 (설계 명세 1~4절, <root> = AdaptiveEcosystem/Saved/EcoAdapt — git 밖):
  snapshots/eco_v3_snapshot_s<세션>_t<스텝>_e<환경 판>.json   언리얼이 쓴다(임시 이름 → 옮기기). *.tmp 는 보지 않고, JSON 이 다 읽힐 때까지 기다린다
  brains/live_r<판>_<시도 이름>.json                            여기서 쓴다: <이름>.json.tmp → 다시 읽어 확인(A5) → os.replace. 같은 이름은 덮지 않는다
  status.json                                                  여기서 쓴다(os.replace): 언리얼 상태 줄 '적응 고리 | <message>'
  live/state.json, live/rounds/<시도 이름>/                       시도·판 번호, 처리한 환경, 판마다 변환·판정·관문·기록

세계 셋 (사람 결정 10-21 '포만 없는 세계 1차 (추천)', 10-20 '학습할 때는 늑대 포만을 끈다 (게임은 그대로)'):
  G 게임 세계  = 스냅숏 세계(늑대 포만은 게임 값 그대로, 부활 없음, 사슴 = 입양 수)                     → 지킴 GG·G4·G5·G6
  N 포만 없는 세계 = G + features.wild_satiation.enabled false                                    → 1차 P1(쫓긴 시간)·지킴 GN·GF·GV·GC·G4
  T 학습 세계  = N + R5 학습 조리법(학습 전용 40 m 밖 부활·학습 시드 32000~32049·지역 섞기, 무작위 숲 없음) + 스냅숏 먹이 지도
                 (+ LIVE train_flight_cost > 0 이면 FLEE 를 실행한 스텝마다 보상에서 그만큼 뺀다 — wild_flight.flight_cost, 기본 0)
두뇌는 관측 21 계약(R5 장애물 관측 0xbc4fc2d45c47c5fd)으로 배운다(사람 결정 10-21 '관측 21로 올려 배움'): 스냅숏의 지금 두뇌가 R1b-F(관측 18)면
R1b-F + 0 열(ckpt/v3/v3_r1_g995_s3_obs21zero.zip — 결정이 비트 단위로 같다)에서, 관측 21 두뇌면 그 두뇌 파일의 모델 zip 에서 시작한다(가중치 sha256 을
다시 맞춰 본다). 다른 관측 18 파일 두뇌는 거부(refused). 판정의 '지금 두뇌' = 시작 zip.

한 판: 변환(converting) → 재현 확인 R(checking, 환경 판 0·두뇌 바꿈 없음일 때만) → 학습 K 모델 × S 스텝 ‖ 지금 두뇌 판정 N·G·끼임(training)
→ 후보 고르기(K > 1, N 고르기 시드) → 후보 판정 N·G·끼임(evaluating) → 관문(gating) → 내보내기·다시 읽기 A5(exporting) → exported·rejected.
감시 중 다른 환경의 새 스냅숏이 오면 돌던 판의 프로세스 나무(학습·워커 풀)를 곧바로 끝내고(superseded) 새 스냅숏으로 다시 시작한다.
같은 환경(환경 지문 + 두뇌 가중치)이면 건너뛴다('환경 같음 — 건너뜀'). 어떤 예외도 상태 error 로 적고 감시는 이어 간다(오류 난 환경은 ERROR_RETRY 번까지).
한 <root> 에는 고리 하나만 돈다(live/watch.lock). 판·학습 프로세스는 따로 된 프로세스 묶음이라 감시 창의 Ctrl+C 는 감시만 받고, 감시가 나무째 끝낸다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from functools import reduce
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
for p in (ROOT, ROOT / "results" / "v3" / "adapt", ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "r4",
          ROOT / "results" / "v3" / "wild2"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

import adapt as ad  # noqa: E402

PROJECT = ROOT.parent / "AdaptiveEcosystem"                                   # 언리얼 프로젝트 폴더 (.uproject)
DEFAULT_ROOT = PROJECT / "Saved" / "EcoAdapt"                                 # 주고받는 파일 (git 밖 **/Saved/)
BRAIN_FOLDERS = (PROJECT / "EcoBrains", PROJECT / "Saved" / "EcoBrains")      # 관측 21 두뇌의 모델 zip 을 찾는 곳 (+ <root>/brains)
TEMPLATE_OBS = ROOT / "configs" / "v3_wild3_obs_mirror.yaml"                  # 관측 21 거울 (세계는 v3_wild3_mirror.yaml 과 비트 단위로 같다)
R5_TRAIN = ROOT / "configs" / "v3_r5_train.yaml"                              # 학습 조리법 (train 블록·부활 계수 — 무작위 숲은 쓰지 않는다)
OBS21ZERO = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip"              # R1b-F + 0 열 (관측 21, 결정 = R1b-F)
R5S3 = ROOT / "ckpt" / "v3" / "v3_r5_g995_s3_20m.zip"                         # 예비 측정의 견줄 두뇌 (행동이 다른 관측 21 두뇌)
CKPT = ROOT / "ckpt" / "v3" / "live"                                          # 후보 모델 (git 밖)
TB = ROOT / "runs" / "v3_live"                                                # 학습 TensorBoard (git 밖 — 판 폴더 아래는 윈도 경로 길이 260 을 넘길 수 있다)
PPO_CONFIG = ROOT / "configs" / "ppo_best.yaml"
LIVE_GATE_MD = HERE.parent / "LIVE_GATE.md"
CONTRACT_OBS18 = "0x7eea0107339be4ce"                                         # 관측 18 계약 (빌드 내장 R1b)
CONTRACT_OBS21 = "0xbc4fc2d45c47c5fd"                                         # 관측 21 계약 (R5 장애물 관측)
STATUS_FORMAT, STATE_FORMAT, ROUND_FORMAT = "eco_v3_live_status", "eco_v3_live_state", "eco_v3_live_round"

# 빠른 관문 (LIVE_GATE.md 와 같은 값 — 10-21 예비 측정 p_20261021T050321 뒤 확정. 바꾸면 LIVE_GATE.md 변경 기록에 먼저 적는다)
LIVE = dict(
    horizon=1800,                           # H_N: 포만 없는 세계 N 판정 길이 1800 스텝 = 4 분 (P1·GN)
    judge_seeds=(35000, 35079),             # N 판정: 시드 n = 80 × 지역, 짝 = 시드(지역 합) — 문턱 t_crit(n − 1)
    horizon_g=3600,                         # H_G: 게임 세계 G 판정 길이 3600 스텝 = 8 분 (GG·G4·G5·G6)
    judge_seeds_g=(35000, 35039),           # G 판정: 시드 n_G = 40 × 지역 (N 판정 시드 앞 40) — 문턱 t_crit(n_G − 1)
    select_seeds=(35100, 35119),            # 후보 고르기 (K > 1 일 때만, N 세계, H_N): 시드 20 × 지역
    stuck_seeds=(35000, 35004),             # 끼임 세기 (G 세계, H_G): 판정 시드 앞 5 × 지역
    check_seeds=(35180, 35199),             # 재현 확인 R (G 세계, 스냅숏 시각까지): 시드 20 × 지역
    train_steps=2_000_000,                  # S: 모델마다 학습 스텝
    model_seeds=(0,),                       # K = 1
    shelter_x=2.0, use_min=0.01,            # G6: 은신처 안 몫 ≤ 지금의 2배, 먹기·도망·숨기 모두 1% 넘게
    f_dec=None,                             # T 세계 f_dec — None = R5 조리법 값 그대로 (예비 측정 T 값 0.885549 는 기록만: 예비 후보가 R5 값으로 배웠다)
    # 10-21 (3) 사용자 기준 바꿈 — 1차 = 쫓긴 시간 (LIVE_GATE.md 변경 기록 (3), 크기는 이 기준의 예비 측정 뒤 다시 정한다)
    flight_own=("cover", "obstacle", "fov", "range"),   # P1: 스스로 벗어난 도망 = 이 끝 까닭 (env_v2/world.py FLIGHT_OWN 과 같다)
    flight_unsafe=("caught", "starved", "truncated"),   # GC: 잡힘·굶음·잘림으로 끝난 도망 (env_v2/world.py FLIGHT_UNSAFE 와 같다)
    flight_min_episodes=1,                  # P1 짝: 두 두뇌 모두 스스로 벗어난 도망이 이만큼 있는 시드만 (빠진 시드는 기록)
    flight_min_effect_s=0.0,                # P1 최소 차이 δ (초): 후보 − 지금 ≤ −δ — 0 = 유의성만, 예비 측정 뒤 정한다
    train_flight_cost=0.0,                  # T 세계 wild_flight.flight_cost (FLEE 를 실행한 스텝마다 보상에서 뺌) — 0 = 끔, 예비 측정 뒤 정한다
    flight_sizes_confirmed=False,           # 위 크기·δ·도주 비용과 H·n·S·K 를 이 기준의 예비 측정으로 확정해 LIVE_GATE.md 에 적기 전에는 거짓 —
                                            #   거짓이면 실제 폴더(Saved/EcoAdapt)에서 판·감시를 돌리지 않는다 (plan_from_args)
)
STEP_S = 2.0 / 15.0                         # 1 스텝 = 2/15 초 (게임 결정 간격 — 1800 스텝 = 240 초)
GATE_SEEDS = (35000, 35199)                 # 관문 시드 (판정·고르기·끼임·재현 확인) — 예비 측정은 쓰지 않는다
PILOT_SEEDS = (34900, 34999)                # 예비 측정 시드 — 관문은 쓰지 않는다
PILOT = dict(horizons=(1800, 3600), steps=(1_000_000, 2_000_000), model_seeds=(0, 1), seeds=(34900, 34999), cand_seeds=(34900, 34929),
             fdec_seeds=(32000, 32001, 32002), scale_steps=3000)
NOSAT = dict(name="nosat", sets={"wild_satiation.enabled": False})           # N = G + 늑대 포만 끔
POLL_S = 2.0                                # 스냅숏 폴더 보기 간격 (초)
HEARTBEAT_S = 5.0                           # 상태 파일 다시 쓰기 간격 (언리얼은 120 초 넘게 묵으면 '응답 없음')
BAD_SNAPSHOT_S = 30.0                       # 이만큼 지나도 JSON 으로 안 읽히는 스냅숏은 깨진 것으로 본다
ERROR_RETRY = 2                             # 같은 환경에서 오류가 이만큼 나면 그 환경은 다시 하지 않는다
TICK_RETRY = 5                              # 감시가 같은 스냅숏을 처리하다 예외가 이만큼 나면 그 스냅숏은 더 보지 않는다
LOCK_STALE_S = 10.0                         # 내용이 아직 안 쓰인 잠금 파일은 이만큼 지나야 죽은 것으로 본다
TERMINAL = ("exported", "rejected", "refused", "error")
MSG_MAX = 90                                # 상태 줄 한 줄 길이 (글자)


# --------------------------------------------------------------------- #
# 작은 도구
# --------------------------------------------------------------------- #


def default_workers() -> int:
    """워커 수 기본값 = max(2, CPU − 6) (언리얼이 CPU 를 함께 쓴다)."""
    return max(2, (os.cpu_count() or 8) - 6)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def replace_retry(src: Path, dst: Path, tries: int = 60, wait: float = 0.05) -> None:
    """os.replace — 윈도에서 읽는 쪽(언리얼)이 대상 파일을 잠깐 열고 있으면 PermissionError 가 나므로 잠깐 쉬고 다시 한다."""
    for k in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if k == tries - 1:
                raise
            time.sleep(wait)


def atomic_write_text(path: Path, text: str) -> None:
    """임시 파일(<이름>.<pid>.<스레드>.tmp — *.json 에 걸리지 않는다)에 쓰고 os.replace 로 바꿔 넣는다. 읽는 쪽은 옛 파일이나 새 파일만 본다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        replace_retry(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_write_json(path: Path, d, indent: int | None = 1) -> None:
    atomic_write_text(path, json.dumps(d, ensure_ascii=False, indent=indent, default=str) + "\n")


def read_json(path: Path):
    """JSON 읽기 — 없거나 덜 쓰였거나 깨졌으면 None."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_text_retry(path: Path, tries: int = 60, wait: float = 0.05) -> str:
    """글 읽기 — 윈도에서 다른 프로세스가 os.replace 하는 순간이면 PermissionError 가 나므로 잠깐 쉬고 다시 한다. 없으면 FileNotFoundError,
    끝내 못 읽으면 그 오류를 그대로 낸다."""
    for k in range(tries):
        try:
            return Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            raise
        except OSError:
            if k == tries - 1:
                raise
            time.sleep(wait)
    raise AssertionError("닿지 않는다")


def own_group() -> dict:
    """자식 프로세스를 따로 된 프로세스 묶음으로 띄우는 Popen 인자: 창의 Ctrl+C 는 띄운 쪽만 받고, 자식 나무는 띄운 쪽이 kill_tree·stop_procs 로
    끝낸다 (윈도 CREATE_NEW_PROCESS_GROUP — 그 묶음은 Ctrl+C 를 받지 않는다. 그 밖은 새 세션)."""
    if os.name == "nt":
        return dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    return dict(start_new_session=True)


def proc_create_time(pid: int) -> float | None:
    """프로세스 시작 시각 (psutil — pid 재사용을 가린다). 모르면 None."""
    try:
        import psutil

        return float(psutil.Process(int(pid)).create_time())
    except Exception:
        return None


def proc_alive(pid, create_time) -> bool:
    """pid 가 살아 있고 시작 시각도 같은가. psutil 이 없으면 알 수 없으므로 산 것으로 본다."""
    try:
        import psutil
    except ImportError:
        return True
    try:
        p = psutil.Process(int(pid))
        return create_time is None or abs(p.create_time() - float(create_time)) < 0.01
    except (psutil.Error, TypeError, ValueError):
        return False


# 양쪽 5% t 임계값 표 (scipy 가 없을 때 — 자유도 사이는 1/자유도 로 선형 보간)
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
         13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064,
         25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042, 40: 2.021, 50: 2.009, 60: 2.000, 80: 1.990, 100: 1.984,
         120: 1.980}
_Z975 = 1.959964


def t_crit_table(df: int) -> float:
    df = int(df)
    if df < 1:
        return math.inf
    if df in _T975:
        return _T975[df]
    keys = sorted(_T975)
    if df > keys[-1]:
        return _Z975 + (_T975[keys[-1]] - _Z975) * keys[-1] / df
    lo = max(k for k in keys if k < df)
    hi = min(k for k in keys if k > df)
    f = (1.0 / lo - 1.0 / df) / (1.0 / lo - 1.0 / hi)
    return _T975[lo] + f * (_T975[hi] - _T975[lo])


def t_crit(df: int) -> float:
    """짝 t 문턱 (양쪽 5%, 자유도 df = 시드 수 − 1). scipy 가 있으면 정확한 값, 없으면 표."""
    if int(df) < 1:
        return math.inf
    try:
        from scipy.stats import t as _t
    except ImportError:
        return t_crit_table(df)
    return float(_t.ppf(0.975, int(df)))


def tfmt(x: float, nd: int = 2) -> str:
    """t·차이 글자 (빼기는 −)."""
    if x != x:
        return "nan"
    if math.isinf(x):
        return "+∞" if x > 0 else "−∞"
    return f"{x:+.{nd}f}".replace("-", "−")


def fmt_steps(n: float) -> str:
    n = float(n)
    if n >= 1e6:
        return f"{n / 1e6:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1e3:
        return f"{n / 1e3:.0f}k"
    return f"{n:.0f}"


def short(text, n: int = MSG_MAX) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def seed_range(text: str) -> tuple[int, int]:
    """'35000-35039' · '35000' → (처음, 끝)."""
    a, _, b = str(text).strip().partition("-")
    lo, hi = int(a), int(b or a)
    if hi < lo:
        raise ValueError(f"시드 범위 {text} 의 끝이 앞보다 작다")
    return lo, hi


def inside(lohi, box) -> bool:
    return box[0] <= int(lohi[0]) <= int(lohi[1]) <= box[1]


def seeds_of(lohi) -> list[int]:
    return ad.seed_list(lohi)


def path_text(p: Path) -> str:
    """두뇌 파일 model.path: herbivore_rl/ 안이면 상대 경로(저장소 두뇌 파일과 같은 꼴), 밖이면 절대 경로 (다음 판이 zip 을 찾는다)."""
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


# --------------------------------------------------------------------- #
# 스냅숏: 읽기·환경 지문·요약
# --------------------------------------------------------------------- #


def read_snapshot(path: Path) -> dict:
    """스냅숏 읽기. 덜 쓰인 파일은 ValueError(JSON) — 부르는 쪽이 다음에 다시 본다. 형식·판이 다르면 adapt.Refused."""
    return ad.load_snapshot(Path(path))


def _r6(x) -> float:
    return round(float(x), 6)


def env_digest(snap: dict) -> str:
    """파이썬 쪽 환경 지문 (명세 6절): 지역마다 원판·날씨(종류·세기)·먹이 용량·은신처 원. 먹이 남은 양·사슴 수·시각은 넣지 않는다
    (같은 환경의 주기 스냅숏은 같은 지문). 원판 순서는 세계가 쓰는 그대로 둔다."""
    rows = []
    for r in sorted(snap["regions"], key=lambda r: str(r["region"])):
        wx = r["world"]["weather"]
        kind = str(wx.get("kind", "clear"))
        cap = np.round(np.asarray(r["food"]["cap"], dtype=np.float64), 9)
        rows.append(dict(region=str(r["region"]), discs=[[_r6(v) for v in d] for d in r["obstacles"]["discs"]],
                         weather=[kind, _r6(wx.get("intensity", 0.0)) if kind != "clear" else 0.0],
                         cap=hashlib.sha256(np.ascontiguousarray(cap, dtype="<f8").tobytes()).hexdigest()[:16],
                         covers=[[_r6(v) for v in c] for c in r["covers"]]))
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def brain_sha(snap: dict) -> str:
    return str(snap["brain"].get("weights_sha256", ""))


def pair_key_of(digest: str, wsha: str, play_id: str = "") -> str:
    base = f"{digest}|{str(wsha)[:16]}"
    return f"{base}|{play_id}" if play_id else base


def pair_key(snap: dict) -> str:
    """건너뛰기 열쇠 = 환경 지문 + 스냅숏 두뇌 가중치 sha256 + Play 번호(play_id, 있으면).
    Play 번호를 넣는 까닭 (10-21 시연 1차): 언리얼은 다른 Play 의 번호가 적힌 두뇌를 받지 않는다. 새 Play 가 앞 Play 와 같은 환경을 다시 만들면
    (같은 지문·같은 두뇌) 열쇠가 같아 건너뛰게 되고, 그러면 새 Play 에는 두뇌가 영영 오지 않는다 — 새 Play 의 스냅숏은 새 판이다(앞 Play 의 판은 그만둔다)."""
    return pair_key_of(env_digest(snap), brain_sha(snap), str(snap.get("play_id") or ""))


def env_info(snap: dict) -> dict:
    """스냅숏 env 블록 (없으면 옛 스냅숏 — 환경 판 0)."""
    e = snap.get("env") or {}
    return dict(watch=bool(e.get("watch", False)), revision=int(e.get("revision", 0) or 0), changed_step=int(e.get("changed_step", 0) or 0),
                first_changed_step=int(e.get("first_changed_step", 0) or 0), trigger=str(e.get("trigger", "")),
                changes=len(e.get("changes") or []))


WEATHER_KO = {"clear": "맑음", "rain": "비", "snow": "눈"}


def env_summary(snap: dict) -> str:
    """Play 시작과 견준 짧은 환경 요약 (예: 'Barren 나무 0→20, 비 1.0'). 나무는 첫 바뀜의 앞 수 → 마지막 바뀜의 뒤 수, 날씨는 지금 값."""
    try:
        ch = (snap.get("env") or {}).get("changes") or []
        if not ch:
            return "환경 그대로"
        regs = {str(r["region"]): r for r in snap.get("regions", [])}
        order = []
        for c in ch:
            if str(c.get("region")) not in order:
                order.append(str(c.get("region")))
        parts = []
        for reg in order:
            rows = [c for c in ch if str(c.get("region")) == reg]
            items = []
            trees = [c for c in rows if c.get("kind") == "trees"]
            if trees:
                m0 = re.search(r"(\d+)\s*→\s*(\d+)", str(trees[0].get("detail", "")))
                m1 = re.search(r"(\d+)\s*→\s*(\d+)", str(trees[-1].get("detail", "")))
                items.append(f"나무 {m0.group(1)}→{m1.group(2)}" if m0 and m1 else short(trees[-1].get("detail", ""), 30))
            if any(c.get("kind") == "weather" for c in rows):
                wx = (regs.get(reg) or {}).get("world", {}).get("weather") or {}
                kind = str(wx.get("kind", ""))
                if kind in WEATHER_KO:
                    items.append(WEATHER_KO[kind] if kind == "clear" else f"{WEATHER_KO[kind]} {float(wx.get('intensity', 0.0)):.1f}")
                else:
                    items.append(short([c for c in rows if c.get("kind") == "weather"][-1].get("detail", ""), 30))
            for c in rows:
                if c.get("kind") not in ("trees", "weather"):
                    items.append(short(c.get("detail", c.get("kind", "")), 30))
            parts.append(f"{reg} " + ", ".join(dict.fromkeys(items)))
        return short(" · ".join(parts), 80)
    except Exception:                                   # 요약은 보이기용 — 실패해도 판을 멈추지 않는다
        return f"환경 #{env_info(snap)['revision']}"


def r_applicable(snap: dict) -> tuple[bool, str]:
    """재현 확인 R 은 Play 시작부터 환경·두뇌가 그대로였을 때만 (명세 6절). 아니면 (False, 까닭)."""
    rev = env_info(snap)["revision"]
    ls = snap["brain"].get("last_swap_step", -1)
    ls = -1 if ls is None else int(ls)
    if rev != 0:
        return False, f"중간 변화로 재현 확인 없음 (환경 #{rev})"
    if ls > 0:
        return False, f"중간 변화로 재현 확인 없음 (두뇌 바꿈 전역 스텝 {ls})"
    if int(snap.get("global_step", 0)) <= 0:
        return False, "스냅숏 시각 0 — 견줄 결과 없음"
    return True, ""


def make_run_id(attempt: int, snap: dict) -> str:
    """시도 이름 a<시도>_<현지 시각>_e<환경 판> — 시도 번호가 있어 겹치지 않는다."""
    return f"a{int(attempt)}_{datetime.now():%Y%m%dT%H%M%S}_e{env_info(snap)['revision']}"


# --------------------------------------------------------------------- #
# 고리 기록(state.json)·상태 파일(status.json)
# --------------------------------------------------------------------- #

HISTORY_KEYS = ("attempt", "run", "snapshot", "key", "state", "round", "verdict", "why", "last_result", "env", "brain_file", "wall_s", "stages",
                "plan_test")


def rounds_dir(root: Path) -> Path:
    return Path(root) / "live" / "rounds"


def state_path(root: Path) -> Path:
    return Path(root) / "live" / "state.json"


def new_state() -> dict:
    return dict(format=STATE_FORMAT, version=1, attempt=0, round=0, last_result="", processed=[], history=[])


def load_state(root: Path) -> dict:
    """state.json 읽기. 없으면 새 기록. 잠깐 못 읽으면(잠김) 다시 하고 끝내 못 읽으면 오류를 낸다 — 판 번호·처리한 열쇠를 잃지 않게 새로 시작하지 않는다.
    JSON·형식이 깨졌을 때만 옆에 남기고 새로 시작한다(쓰기는 os.replace 라 반쯤 쓰인 파일은 없다)."""
    p = state_path(root)
    try:
        text = read_text_retry(p)
    except FileNotFoundError:
        return new_state()
    try:
        d = json.loads(text)
    except ValueError:
        d = None
    if not isinstance(d, dict) or d.get("format") != STATE_FORMAT:
        try:                                             # 깨진 기록은 옆에 남기고 새로 시작한다
            p.rename(p.with_name(f"state.json.bad_{datetime.now():%Y%m%dT%H%M%S}"))
        except OSError:
            pass
        return new_state()
    for k, v in new_state().items():
        d.setdefault(k, v)
    return d


def save_state(root: Path, st: dict) -> None:
    atomic_write_json(state_path(root), st)


def begin_attempt(root: Path) -> int:
    """시도 번호 하나 올리기 (기각·거부·그만둠도 시도다)."""
    st = load_state(root)
    st["attempt"] = int(st["attempt"]) + 1
    save_state(root, st)
    return int(st["attempt"])


def is_processed(st: dict, key: str) -> bool:
    """이미 끝낸 환경인가: 끝난 판(내보냄·기각·거부)이나 내보낸 두뇌의 짝이 있으면 예. 오류는 ERROR_RETRY 번까지 다시 한다."""
    rows = [p for p in st.get("processed", []) if p.get("key") == key]
    if any(p.get("state") != "error" for p in rows):
        return True
    return sum(1 for p in rows if p.get("state") == "error") >= ERROR_RETRY


def finish_attempt(root: Path, res: dict) -> dict:
    """판 결과를 state.json 에 적는다: 내보냈으면 판 번호, 끝난 판이면 처리한 열쇠(내보냈으면 '같은 환경 + 새 두뇌' 열쇠도 — 바꿔 끼운 뒤의 스냅숏을
    다시 배우지 않는다), 기록 한 줄."""
    st = load_state(root)
    state = res.get("state")
    if state == "exported" and res.get("round"):
        st["round"] = max(int(st["round"]), int(res["round"]))
    if state in TERMINAL and res.get("key"):
        st["processed"].append(dict(key=res["key"], state=state, attempt=res.get("attempt"), snapshot=res.get("snapshot"), time=utc_now()))
        if state == "exported" and res.get("env_digest") and res.get("exported_weights_sha256"):
            st["processed"].append(dict(key=pair_key_of(res["env_digest"], res["exported_weights_sha256"], str(res.get("play_id") or "")), state="adopted",
                                        attempt=res.get("attempt"), snapshot=res.get("snapshot"), time=utc_now()))
    st["processed"] = st["processed"][-500:]
    if res.get("last_result"):
        st["last_result"] = res["last_result"]
    st["history"].append({k: res.get(k) for k in HISTORY_KEYS} | {"time": utc_now()})
    save_state(root, st)
    return st


def lock_path(root: Path) -> Path:
    return Path(root) / "live" / "watch.lock"


def acquire_lock(root: Path, what: str) -> Path:
    """<root> 하나에 실시간 고리 하나만 (감시 둘이나 감시 + 앞에서 돌리는 판이 같은 폴더를 쓰면 시도 번호·시도 이름·체크포인트·판 번호가 겹친다).
    live/watch.lock 을 O_EXCL 로 만들어 pid·시작 시각을 적는다. 주인이 죽은 잠금은 치우고 잡는다. 다른 고리가 살아 있으면 SystemExit."""
    p = lock_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    me = dict(pid=os.getpid(), create_time=proc_create_time(os.getpid()), what=what, time=utc_now())
    for _ in range(5):
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            d = read_json(p)
            if isinstance(d, dict):
                if proc_alive(d.get("pid"), d.get("create_time")):
                    raise SystemExit(f"다른 실시간 고리({d.get('what')}, pid {d.get('pid')}, {d.get('time')})가 {root} 를 쓰고 있다 — 하나만 돌린다 "
                                     f"(그 프로세스가 없으면 {p} 를 지운다)")
            else:
                try:
                    if time.time() - p.stat().st_mtime < LOCK_STALE_S:      # 막 만들어 아직 안 썼다
                        raise SystemExit(f"다른 실시간 고리가 {root} 를 막 잡았다 — 하나만 돌린다 ({p})")
                except FileNotFoundError:
                    continue
            try:
                p.unlink()                                                 # 주인이 죽은 잠금
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(me, ensure_ascii=False))
        return p
    raise SystemExit(f"잠금 {p} 을 잡지 못했다")


def release_lock(p: Path) -> None:
    """내가 잡은 잠금만 지운다."""
    d = read_json(p)
    if isinstance(d, dict) and d.get("pid") == os.getpid():
        try:
            Path(p).unlink()
        except OSError:
            pass


class Status:
    """status.json (명세 4절). 단계가 바뀔 때마다 쓰고, 긴 단계에서는 맥박 스레드가 HEARTBEAT_S 마다 다시 쓴다(provider 가 글·진행을 준다)."""

    KEYS = ("state", "attempt", "round", "snapshot", "env", "message", "progress", "last_result")

    def __init__(self, root: Path):
        st = load_state(root)
        self.path = Path(root) / "status.json"
        self.f = dict(format=STATUS_FORMAT, version=1, updated_unix=0.0, pid=os.getpid(), state="idle", attempt=int(st["attempt"]),
                      round=int(st["round"]), snapshot="", env="", message="", progress=-1.0, last_result=str(st.get("last_result", "")))
        self.provider = None
        self.lock = threading.Lock()
        self._stop: threading.Event | None = None

    def set(self, provider=None, **kw) -> None:
        with self.lock:
            for k, v in kw.items():
                if k in self.KEYS:
                    self.f[k] = v
            if "message" in kw:
                self.f["message"] = short(kw["message"])
            self.provider = provider
            self._apply()
            self._write()

    def refresh(self) -> None:
        with self.lock:
            self._apply()
            self._write()

    def adopt(self, d: dict) -> None:
        """다른 프로세스(판)가 쓴 상태를 이어받는다 (감시가 맥박을 이어 쓰려고)."""
        with self.lock:
            for k in self.KEYS:
                if k in d:
                    self.f[k] = d[k]
            self.provider = None

    def _apply(self) -> None:
        if self.provider is None:
            return
        try:
            m, p = self.provider()
            self.f["message"] = short(m)
            self.f["progress"] = round(float(p), 4)
        except Exception:
            pass

    def _write(self) -> None:
        self.f["updated_unix"] = time.time()
        self.f["pid"] = os.getpid()
        try:
            atomic_write_json(self.path, self.f)
        except OSError as e:
            print(f"[live] 상태 파일 쓰기 실패: {e}", flush=True)

    def start_heartbeat(self, every: float = HEARTBEAT_S) -> None:
        if self._stop is not None:
            return
        self._stop = threading.Event()

        def loop(ev=self._stop):
            while not ev.wait(every):
                self.refresh()

        threading.Thread(target=loop, daemon=True, name="live-status").start()

    def stop_heartbeat(self) -> None:
        if self._stop is not None:
            self._stop.set()
            self._stop = None


# --------------------------------------------------------------------- #
# 시작 모델
# --------------------------------------------------------------------- #

_SHA: dict = {}
_CONTRACT: dict = {}


def _zkey(path: Path) -> tuple:
    p = Path(path)
    return str(p.resolve()), p.stat().st_mtime_ns


def zip_weights_sha(path: Path) -> str:
    """모델 zip 의 두뇌 가중치 sha256 (언리얼 로더와 같은 바이트, adapt.model_weights_sha256 — 파일·mtime 마다 한 번만 잰다)."""
    k = _zkey(path)
    if k not in _SHA:
        _SHA[k] = ad.model_weights_sha256(Path(path))
    return _SHA[k]


def zip_contract(path: Path) -> str:
    """모델 zip 의 입출력 계약 해시 (관측 이름·마스크 판)."""
    k = _zkey(path)
    if k not in _CONTRACT:
        import export_weights_v3 as ex
        from stable_baselines3 import PPO

        pol = PPO.load(str(path), device="cpu").policy
        _CONTRACT[k] = f"0x{ex.contract_hash(tuple(pol.rep_obs_names), int(getattr(pol, 'rep_mask_version', 1))):016x}"
    return _CONTRACT[k]


def find_brain_zip(want: str, folders) -> Path | None:
    """두뇌 파일 폴더들에서 weights_sha256 == want 인 파일의 model.path zip (zip 을 다시 재어 같을 때만)."""
    for folder in folders:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for f in sorted(folder.glob("*.json")):
            b = read_json(f)
            if not isinstance(b, dict) or b.get("weights_sha256") != want:
                continue
            text = (b.get("model") or {}).get("path")
            if not text:
                continue
            p = Path(text)
            p = p if p.is_absolute() else ROOT / p
            if p.exists() and zip_weights_sha(p) == want:
                return p
    return None


def brain_folders(root: Path) -> tuple:
    return tuple(BRAIN_FOLDERS) + (Path(root) / "brains",)


def resolve_start(snap: dict, folders) -> dict:
    """스냅숏의 지금 두뇌 → 이어 배울 시작 모델 (명세 6절). 관측 18 이고 가중치가 R1b-F 면 R1b-F + 0 열, 관측 21 이면 두뇌 파일들에서 같은 가중치의
    모델 zip. 스냅숏 두뇌 계약(brain.contract_hash, 옛 스냅숏은 맨 위 contract_hash)이 그 두뇌의 모델 계약과 같아야 하고, 시작 모델은 관측 21 계약이어야
    한다. 아니면 adapt.Refused."""
    b = snap["brain"]
    want = brain_sha(snap)
    obs = int(b.get("obs_dim") or 18)
    bc = str(b.get("contract_hash") or snap.get("contract_hash", ""))
    if obs == 18:
        if want != zip_weights_sha(ad.R1BF):
            raise ad.Refused(f"지금 두뇌 {b.get('id')} 는 R1b-F 가 아닌 관측 18 두뇌다 — 관측 21 로 올려 배울 시작점은 R1b-F(+ 0 열)뿐이다")
        cur, start, why = ad.R1BF, OBS21ZERO, "R1b-F(관측 18) → R1b-F + 0 열(관측 21, 결정 같음)"
    elif obs == 21:
        z = find_brain_zip(want, folders)
        if z is None:
            raise ad.Refused(f"관측 21 두뇌 {b.get('id')} (가중치 sha256 {want[:16]}) 의 모델 zip 을 두뇌 파일 폴더에서 찾지 못했다 — 이어 배울 시작점이 없다")
        cur, start, why = z, z, "관측 21 두뇌 → 그 두뇌 파일의 모델 zip"
    else:
        raise ad.Refused(f"관측 {obs} 칸 두뇌는 받지 않는다 (관측 18·21 만)")
    if not Path(start).exists():
        raise ad.Refused(f"시작 모델 {start} 가 없다")
    cc = zip_contract(cur)
    if cc != bc:
        raise ad.Refused(f"계약 해시가 다르다: 스냅숏 두뇌 {bc} 대 모델 {cc} ({path_text(cur)})")
    sc = zip_contract(start)
    if sc != CONTRACT_OBS21:
        raise ad.Refused(f"시작 모델 계약 {sc} 이 관측 21 계약 {CONTRACT_OBS21} 이 아니다")
    return dict(zip=Path(start), current_model=Path(cur), obs_dim=obs, brain=str(b.get("id", "")), brain_contract=bc, start_contract=sc,
                weights_sha256=want, why=why)


# --------------------------------------------------------------------- #
# 변환 → 한 판 폴더 (세계 G·N·T)
# --------------------------------------------------------------------- #


def prepare(snap_path: Path, snap: dict, rd: Path, folders, f_dec: float | None = None, flight_cost: float | None = None) -> dict:
    """스냅숏 → 판 폴더 rd: snapshot.json(그대로)·world.yaml(G)·train.yaml(T)·regions.json·convert.json. N 은 G + NOSAT 변형(판정 때 덮는다).
    flight_cost (None = LIVE train_flight_cost) > 0 이면 T 에 wild_flight.flight_cost 를 적는다(0 이면 적지 않는다 — train.yaml 이 그대로).
    반환 = adapt 의 run 정보 꼴 {record, regions, dir} + start. 거부는 adapt.Refused (도주 반사를 끈 세계도 — 관문이 도망 기록을 쓴다)."""
    start = resolve_start(snap, folders)
    ref = json.loads(ad.REFERENCE.read_text(encoding="utf-8")) if ad.REFERENCE.exists() else None
    out = ad.convert(snap, ref, template=TEMPLATE_OBS, start=start["zip"], contract=CONTRACT_OBS21, recipe=R5_TRAIN)
    world, train = out["world"], out["train"]
    if not bool(world["features"]["wild_flight"]["enabled"]):
        raise ad.Refused("도주 반사(wild_flight)를 끈 세계다 — 1차 쫓긴 시간·지킴 도망 기록을 잴 수 없다 (LIVE_GATE.md 5-1)")
    sat_g = bool(world["features"]["wild_satiation"]["enabled"])
    train["features"]["wild_satiation"]["enabled"] = False             # T: 학습할 때는 늑대 포만을 끈다 (게임 G 는 그대로)
    fc = float(LIVE["train_flight_cost"] if flight_cost is None else flight_cost)
    if fc < 0.0:
        raise ValueError(f"flight_cost 는 0 이상이어야 한다: {fc}")
    if fc > 0.0:
        train["features"]["wild_flight"]["flight_cost"] = fc           # T: FLEE 를 실행한 스텝마다 보상에서 뺀다 (10-21 (3) — 학습 세계 전용)
    train["version"] = "3.live.train"
    rep = train["train"]["repertoire"]
    fd = LIVE["f_dec"] if f_dec is None else f_dec
    fd_src = "R5 학습 조리법 값 그대로 (포만 켠 R5 세계에서 잰 값 — 예비 측정의 measure-fdec 로 T 값을 잰다)"
    if fd is not None:
        rep["f_dec"] = float(fd)
        rep["ent_coef_base"] = round(0.01 * float(fd), 8)              # 범주 엔트로피 계수 0.01 그대로 (R5 와 같은 셈)
        fd_src = "LIVE_GATE.md f_dec (T 세계에서 잰 값)"
    rd = Path(rd)
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "snapshot.json").write_text(Path(snap_path).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    e = env_info(snap)
    head = (f"# 실시간 적응 {rd.name} — 자동 생성 (results/v3/live/live.py, 손으로 고치지 않는다).\n"
            f"# 스냅숏 {Path(snap_path).name}: 지도 {snap.get('map')} 세션 {snap['session_seed']} 전역 스텝 {snap['global_step']} 환경 #{e['revision']}, "
            f"두뇌 {snap['brain'].get('id')}\n")
    ad.write_yaml(rd / "world.yaml", world, head + f"# G 게임 세계 (부활 없음, 늑대 포만 = 게임 값 {'켬' if sat_g else '끔'}) = "
                                                   "configs/v3_wild3_obs_mirror.yaml + convert.json 'changed'. N = 이 세계 + wild_satiation 끔\n")
    ad.write_yaml(rd / "train.yaml", train, head + "# T 학습 세계 = world.yaml + 늑대 포만 끔 + R5 학습 조리법(학습 전용 40 m 밖 부활·학습 시드 "
                                                   "32000~32049·지역 섞기, 무작위 숲 없음)"
                  + (f" + 도주 비용 wild_flight.flight_cost {fc:g}" if fc > 0.0 else "") + "\n")
    (rd / "regions.json").write_text(json.dumps(out["regions"], ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    rec = dict(out["record"])
    rec["f_dec_note"] = fd_src
    rec["live"] = dict(start=path_text(start["zip"]), start_why=start["why"], current_brain=start["brain"], brain_contract=start["brain_contract"],
                       start_contract=start["start_contract"], satiation_game=sat_g, f_dec=float(rep["f_dec"]), flight_cost=fc,
                       worlds=dict(G="world.yaml (늑대 포만 게임 값)", N="world.yaml + wild_satiation.enabled false", T="train.yaml (늑대 포만 끔)"),
                       env=e, env_summary=env_summary(snap), env_digest=env_digest(snap), brain_weights_sha256=brain_sha(snap))
    (rd / "convert.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return dict(record=rec, regions=out["regions"], dir=rd, start=start)


def train_variant(rd: Path, flight_cost: float) -> Path:
    """판 폴더 T 세계(train.yaml)에서 wild_flight.flight_cost 만 바꾼 사본 train_fc<값>.yaml (예비 측정 --flight-cost 후보). 0 이면 그 키를 뺀다."""
    import yaml

    rd = Path(rd)
    fc = float(flight_cost)
    if fc < 0.0:
        raise ValueError(f"flight_cost 는 0 이상이어야 한다: {fc}")
    d = yaml.safe_load((rd / "train.yaml").read_text(encoding="utf-8"))
    wf = d["features"]["wild_flight"]
    if fc > 0.0:
        wf["flight_cost"] = fc
    else:
        wf.pop("flight_cost", None)
    p = rd / f"train_fc{fc:g}.yaml"
    ad.write_yaml(p, d, f"# 실시간 적응 {rd.name} 예비 측정 — train.yaml 에서 wild_flight.flight_cost 만 {fc:g} 로 바꾼 T 세계 (자동 생성, 손으로 고치지 않는다)\n")
    return p


# --------------------------------------------------------------------- #
# 세계 돌리기 (워커 풀 하나에 여러 판을 섞어 넣는다)
# --------------------------------------------------------------------- #


def _world_multi(job: dict) -> dict:
    """예비 측정 세계 하나: r4_eval._one 과 같은 요약(끝 시각) + 판정 길이마다 잡힘·굶음·산(죽은 스텝 death_t 로 센다)·도망 기록(그 길이에서 끊은 것)."""
    import run_mirror as rm

    hs = [int(h) for h in job.pop("horizons")]
    ad._patch_food(job.pop("snap_food"))
    job["flight_at"] = hs
    res = rm.run_world(job)
    m, dg = res["meta"], res["meta"]["diag"]
    cause, dt = np.asarray(m["death_cause"]), np.asarray(m["death_t"])
    out = dict(seed=m["seed"], region=job["region"], n=m["n"], caught=int((cause == 1).sum()), starved=int((cause == 2).sum()),
               alive=int((cause == 0).sum()), shelter_steps=m["shelter_steps"], live_steps=m["live_steps"], beh_steps=dg["beh_steps"],
               catch_cover=dg["catch_cover"], hunt=m["hunt"], wall_s=m["wall_s"])
    if "flight" in m:
        out["flight"] = m["flight"]
    out["at"] = {str(h): dict(caught=int(((cause == 1) & (dt <= h)).sum()), starved=int(((cause == 2) & (dt <= h)).sum()),
                              alive=int(((cause == 0) | (dt > h)).sum())) for h in hs}
    for h in hs:
        f = (m.get("flight_at") or {}).get(str(h))
        if f is not None:
            out["at"][str(h)]["flight"] = f
    return out


def _scale_one(job: dict) -> dict:
    """도주 비용 기준 크기(예비 측정 'scale'): T 세계(부활 있음, 그 지역 스냅숏 먹이 지도) 하나를 두뇌로 job['steps'] 스텝 돌려 사슴-스텝 보상을 나눠 센다.
    도주 = 그 스텝에 FLEE 를 실행한 사슴(도주 반사·두뇌 FLEE 모두 — 스텝 뒤 rs.behavior, 리스폰 칸은 죽음 스텝이라 빠진다), 그 가운데 반사 = 실행한 덮기
    WF_PANIC. 에너지 칸 = 보상 − rew_alive (죽음·번식 스텝은 뺀다 — 보상 ±10 이 섞인다). 동역학은 그대로다."""
    from env.config import Config
    from env_v2 import repertoire as rep
    from env_v2 import rollout as ro
    from env_v2.world import WF_PANIC, World

    cfg = Config(job["cfg"])
    w = World(cfg, seeds=[int(job["seed"])])
    ad.apply_snapshot_food(w, job["snap_food"])
    pol = ro.build_policy({"kind": "rep_learned", "path": str(job["model"])}, int(job["seed"]))
    ro.forward_bind(pol, w)
    acc = dict(steps=0, rew=0.0, deaths=0, repro=0, flee_n=0, flee_e=0.0, other_n=0, other_e=0.0, reflex_n=0)
    for _ in range(int(job["steps"])):
        pan0 = w.wf_mode == WF_PANIC
        _, rew, done, _ = w.step(np.asarray(pol(w.observe()), dtype=np.float64))
        pan = w._rs.behavior == rep.FLEE
        rep_ = rew > 0.5 * float(cfg.rew_repro)
        ok = ~done & ~rep_
        acc["reflex_n"] += int(np.count_nonzero(ok & pan & pan0))
        e = rew - float(cfg.rew_alive)
        acc["steps"] += int(w.N)
        acc["rew"] += float(rew.sum())
        acc["deaths"] += int(np.count_nonzero(done))
        acc["repro"] += int(np.count_nonzero(rep_))
        acc["flee_n"] += int(np.count_nonzero(ok & pan))
        acc["flee_e"] += float(e[ok & pan].sum())
        acc["other_n"] += int(np.count_nonzero(ok & ~pan))
        acc["other_e"] += float(e[ok & ~pan].sum())
    return dict(acc, region=job["region"], seed=int(job["seed"]))


def _job(item):
    """워커에서 도는 일 하나: (종류, 꼬리표, 세계 job) → (꼬리표, 결과)."""
    kind, tag, job = item
    if kind == "world":
        return tag, ad._world_one(job)
    if kind == "stuck":
        return tag, ad._stuck_one(job)
    if kind == "multi":
        return tag, _world_multi(job)
    if kind == "scale":
        return tag, _scale_one(job)
    raise ValueError(f"모르는 일 {kind}")


class Pool:
    """워커 풀 (env_v2.rollout.make_executor — 1 이하면 같은 프로세스). 예외·그만둠이면 남은 일을 지우고 워커를 끝낸다."""

    def __init__(self, workers: int):
        from env_v2 import rollout as ro

        self.ex = ro.make_executor(int(workers))

    def run(self, items: list, on_done=None) -> list:
        if self.ex is None:
            out = []
            for it in items:
                out.append(_job(it))
                if on_done:
                    on_done()
            return out
        from concurrent.futures import as_completed

        futs = {self.ex.submit(_job, it): k for k, it in enumerate(items)}
        out = [None] * len(items)
        for f in as_completed(futs):
            out[futs[f]] = f.result()
            if on_done:
                on_done()
        return out

    def close(self, kill: bool = False) -> None:
        if self.ex is None:
            return
        if kill:
            procs = list((getattr(self.ex, "_processes", None) or {}).values())
            self.ex.shutdown(wait=False, cancel_futures=True)
            for p in procs:
                try:
                    p.kill()
                except Exception:
                    pass
        else:
            self.ex.shutdown(wait=True)
        self.ex = None

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        self.close(kill=et is not None)
        return False


def eval_items(info: dict, tag: str, model: Path, seeds, steps: int, world: str, kind: str = "world", horizons=None) -> list:
    """판정 세계 일: world 'N' = 포만 없는 세계(G + NOSAT), 'G' = 게임 세계. kind 'multi' 면 판정 길이마다 요약(예비 측정)."""
    jobs = ad.make_jobs(info, Path(model), seeds, steps, True, NOSAT if world == "N" else None)
    if horizons is not None:
        for j in jobs:
            j["horizons"] = list(horizons)
    return [(kind, f"{tag}:{world}", j) for j in jobs]


def stuck_items(info: dict, tag: str, model: Path, seeds, steps: int) -> list:
    """끼임 세기 일 (G 세계 — adapt.cmd_stuck 과 같은 job)."""
    jobs = ad.make_jobs(info, Path(model), seeds, steps, diag=False)
    for j in jobs:
        j.pop("log_every", None)
        j.pop("diag", None)
    return [("stuck", f"{tag}:stuck", j) for j in jobs]


def gather(results: list, models: dict, steps: dict) -> dict:
    """(꼬리표, 결과) 목록 → 꼬리표마다 판 {meta, worlds} (r4_eval 지표 꼴) 또는 끼임 {summary, model}."""
    import stuck_check

    by: dict = {}
    for tag, r in results:
        by.setdefault(tag, []).append(r)
    out = {}
    for tag, rows in by.items():
        brain, world = tag.rsplit(":", 1)
        model = ad._rel(models[brain])
        if world == "stuck":
            out[tag] = dict(summary=stuck_check.summarize(rows), model=model)
        else:
            out[tag] = dict(meta=dict(model=model, world=world, seeds=sorted({int(w["seed"]) for w in rows}), regions=sorted({w["region"] for w in rows}),
                                      steps=int(steps.get(tag, 0)), worlds=len(rows)), worlds=rows)
    return out


# --------------------------------------------------------------------- #
# 학습 (모델 시드마다 프로세스 하나, 스레드 1)
# --------------------------------------------------------------------- #


def launch_training(info: dict, rd: Path, start: Path, rid: str, seeds, steps: int, every: int, ckpt: Path, config: Path | None = None,
                    tag: str = "") -> list[dict]:
    """train_v3.py 를 live.py train-one 으로 띄운다 (스냅숏 먹이 지도 + 진행 파일). config = T 세계 설정(기본 판 폴더 train.yaml — 예비 측정의
    도주 비용 후보는 train_variant 사본), tag = 이름에 붙일 꼬리(같은 시드의 다른 설정 후보를 가른다). 반환 = 프로세스 기록 목록."""
    rec = info["record"]
    (rd / "logs").mkdir(parents=True, exist_ok=True)
    config = Path(config) if config is not None else rd / "train.yaml"
    procs = []
    for s in seeds:
        name = f"live_{rid}_cand{tag}_s{int(s)}"
        out = Path(ckpt) / rid / f"{name}.zip"
        out.parent.mkdir(parents=True, exist_ok=True)
        prog, log = rd / "logs" / f"progress{tag}_s{int(s)}.json", rd / "logs" / f"train{tag}_s{int(s)}.log"
        src = (f"실시간 적응 {rid}: 스냅숏 {rec['snapshot'].get('why') or ''} 전역 스텝 {rec['snapshot']['global_step']}, 지금 두뇌 "
               f"{rec['snapshot']['brain']} — 포만 없는 학습 세계 T ({config.name}), 시작 {rec['live']['start']}")
        args = ["--config", str(config), "--seed", str(int(s)), "--steps", str(int(steps)), "--init-from-model", str(start),
                "--init-source", src, "--run-name", name, "--out", str(out), "--tb", str(TB), "--threads", "1",
                "--ppo-config", str(PPO_CONFIG), "--every", str(int(every))]
        cmd = [sys.executable, str(HERE), "train-one", "--dir", str(rd), "--progress", str(prog), "--"] + args
        fh = open(log, "w", encoding="utf-8")
        p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONUTF8="1"), **own_group())
        procs.append(dict(seed=int(s), out=out, log=log, prog=prog, fh=fh, proc=p, steps=int(steps), t0=time.perf_counter(), wall_s=None))
        record_pids(rd, procs)
        print(f"  학습 시작: 모델 시드 {s} × {fmt_steps(steps)} → {out} (기록 {log})", flush=True)
    return procs


def record_pids(rd: Path, procs: list) -> None:
    """학습 프로세스 pid·시작 시각을 판 폴더 logs/pids.json 에 적는다 — 판 프로세스가 정리 없이 죽어도(윈도는 고아를 남긴다) 감시가 kill_recorded 로 끝낸다."""
    rows = [dict(pid=int(p["proc"].pid), create_time=proc_create_time(p["proc"].pid), seed=p["seed"]) for p in procs]
    atomic_write_json(Path(rd) / "logs" / "pids.json", dict(procs=rows))


def kill_recorded(rd: Path) -> int:
    """판 폴더 logs/pids.json 에 적힌 학습 프로세스 가운데 아직 사는 것(과 그 자손)을 끝낸다. 시작 시각이 다르거나 없으면(pid 재사용) 건드리지 않는다.
    반환 = 끝낸 수."""
    d = read_json(Path(rd) / "logs" / "pids.json")
    if not isinstance(d, dict):
        return 0
    try:
        import psutil
    except ImportError:
        return 0
    n = 0
    for r in d.get("procs", []):
        if r.get("create_time") is None or not proc_alive(r.get("pid"), r["create_time"]):
            continue
        try:
            p = psutil.Process(int(r["pid"]))
            kids = p.children(recursive=True)
            for k in kids + [p]:
                try:
                    k.kill()
                except psutil.Error:
                    pass
            psutil.wait_procs(kids + [p], timeout=10)
            n += 1
        except psutil.Error:
            pass
    return n


def train_done_steps(procs: list) -> int:
    total = 0
    for p in procs:
        if p["proc"].poll() is not None and p["proc"].returncode == 0:
            total += p["steps"]
            continue
        d = read_json(p["prog"]) or {}
        total += min(int(d.get("steps", 0)), p["steps"])
    return total


def wait_training(procs: list) -> list[dict]:
    """학습 프로세스를 기다린다. learn_s·steps_per_sec = train_v3 메타(<out>.json)의 순수 학습 시간·속도 (프로세스 시작·기다린 시간 빼고)."""
    rows = []
    for p in procs:
        rc = p["proc"].wait()
        p["fh"].close()
        p["wall_s"] = round(time.perf_counter() - p["t0"], 1)
        meta = read_json(Path(p["out"]).with_suffix(".json")) or {}
        rows.append(dict(seed=p["seed"], rc=rc, model=str(p["out"]), log=str(p["log"]), ok=rc == 0 and p["out"].exists(), wall_s=p["wall_s"],
                         learn_s=round(float(meta["elapsed_min"]) * 60, 1) if meta.get("elapsed_min") is not None else None,
                         steps_per_sec=meta.get("steps_per_sec")))
    return rows


def stop_procs(procs: list) -> None:
    for p in procs:
        try:
            kill_tree(p["proc"])
        except Exception:
            pass
        try:
            p["fh"].close()
        except Exception:
            pass


# --------------------------------------------------------------------- #
# 도망 기록 (10-21 (3) 1차 = 쫓긴 시간 — env_v2/world.py World.flight_stats, r4_eval._one 'flight')
# --------------------------------------------------------------------- #

NAN = float("nan")
FLIGHT_SUMS = ("started", "live_steps", "flee_steps", "reflex_steps", "shelter_end")     # 시드 합으로 더하는 도망 기록 칸


def ratio(x: float, y: float) -> float:
    return x / y if y else NAN


def flight_of(w: dict) -> dict:
    """세계 요약 하나의 도망 기록 (env_v2/world.py World.flight_stats). 없거나 옛 꼴이면 ValueError — 관문은 도망 기록 없는 판을 받지 않는다."""
    f = w.get("flight")
    if not isinstance(f, dict):
        raise ValueError(f"세계 (시드 {w.get('seed')}, {w.get('region')}) 에 도망 기록 flight 가 없다 — wild_flight 세계를 지금 실행기(run_mirror.run_world)로 돌린다")
    if not all(k in f for k in FLIGHT_SUMS + ("contact",)):
        raise ValueError(f"세계 (시드 {w.get('seed')}, {w.get('region')}) 의 도망 기록이 옛 꼴이다(쫓긴 시간·산 사슴-스텝 없음) — 지금 실행기로 다시 돌린다")
    return f


def flight_seed(res: dict) -> dict:
    """판 {meta, worlds} → 시드마다 도망 합(지역 합): FLIGHT_SUMS 칸, own_n·own_contact = 스스로 벗어난 도망(LIVE flight_own) 수·쫓긴 스텝,
    unsafe_n = 잡힘·굶음·잘림(LIVE flight_unsafe) 수, n·steps·contact = 끝 까닭별 수·FLEE 스텝·쫓긴 스텝."""
    out: dict = {}
    for w in res["worlds"]:
        f = flight_of(w)
        a = out.setdefault(int(w["seed"]), dict({k: 0 for k in FLIGHT_SUMS}, own_n=0, own_contact=0, unsafe_n=0, n={}, steps={}, contact={}))
        for k in FLIGHT_SUMS:
            a[k] += int(f[k])
        a["own_n"] += sum(int(f["n"][c]) for c in LIVE["flight_own"])
        a["own_contact"] += sum(int(f["contact"][c]) for c in LIVE["flight_own"])
        a["unsafe_n"] += sum(int(f["n"][c]) for c in LIVE["flight_unsafe"])
        for key in ("n", "steps", "contact"):
            for c, v in f[key].items():
                a[key][c] = a[key].get(c, 0) + int(v)
    return out


def flight_pair(cand: dict, cur: dict) -> dict:
    """1차 P1 의 짝: 시드마다 스스로 벗어난 도망(LIVE flight_own — 은신처·원판·시야각·반경)의 쫓긴 시간 평균(초) = (그 시드 지역 셋의 쫓긴 스텝 합 ÷ 수)
    × 2/15, 후보 − 지금. 두 두뇌 모두 그런 도망이 flight_min_episodes 이상인 시드만 쓴다 — 빠진 시드는 dropped. 시드 목록이 다르면 멈춘다.
    쓸 시드가 없으면 n 0·nan."""
    import r4_eval as re_

    a, b = flight_seed(cand), flight_seed(cur)
    if sorted(a) != sorted(b):
        raise ValueError("두 판의 시드가 다르다 — 같은 세계끼리만 견준다")
    k = int(LIVE["flight_min_episodes"])
    both = [s for s in sorted(a) if a[s]["own_n"] >= k and b[s]["own_n"] >= k]
    if both:
        p = re_.paired({s: a[s]["own_contact"] / a[s]["own_n"] * STEP_S for s in both}, {s: b[s]["own_contact"] / b[s]["own_n"] * STEP_S for s in both})
    else:
        p = dict(a=NAN, b=NAN, diff=NAN, se=NAN, t=NAN, n=0)
    return dict(p, dropped=[s for s in sorted(a) if s not in both], seeds=len(a))


def flight_rate(a: dict, key: str) -> float:
    """시드 합 하나의 지킴 몫: starts = 1000 산 사슴-스텝당 시작한 도망(GF), flee = 산 사슴-스텝 가운데 FLEE 를 실행한 몫(GV — 반사·스스로 고른 것 모두),
    unsafe = 시작한 도망 가운데 잡힘·굶음·잘림으로 끝난 몫(GC). 분모가 0 이면 0."""
    if key == "starts":
        return 1000.0 * a["started"] / a["live_steps"] if a["live_steps"] else 0.0
    if key == "flee":
        return a["flee_steps"] / a["live_steps"] if a["live_steps"] else 0.0
    if key == "unsafe":
        return a["unsafe_n"] / a["started"] if a["started"] else 0.0
    raise ValueError(f"모르는 지킴 몫 {key}")


def flight_rate_pair(cand: dict, cur: dict, key: str) -> dict:
    """지킴 GF·GV·GC 의 짝: 시드마다 flight_rate(key), 후보 − 지금."""
    import r4_eval as re_

    a, b = flight_seed(cand), flight_seed(cur)
    return re_.paired({s: flight_rate(v, key) for s, v in a.items()}, {s: flight_rate(v, key) for s, v in b.items()})


def flight_pooled(res: dict) -> dict:
    """판 전체 도망 합 (보고 — 시드 평균이 아니라 전체 합의 비율이라 1차 P1 의 시드 평균과 셈이 다르다): 시작한 도망 수·시드당·1000 산 사슴-스텝당,
    끝 까닭 몫(시작한 도망 가운데)·까닭별 평균 도망 초·쫓긴 초, 스스로 벗어난 도망 수·몫·쫓긴 시간 평균 초(own_contact_s), 잡힘·굶음·잘림 몫·잘림 몫,
    은신처 원 안에서 끝난 몫(살아 끝난 도망 가운데), 산 사슴-스텝 가운데 실행 FLEE 몫(반사 포함)·반사 몫·스스로 고른 FLEE 몫, 쫓긴 시간 칸."""
    W = res["worlds"]
    t = {k: 0 for k in FLIGHT_SUMS}
    n, st, ct, hist = {}, {}, {}, None
    for w in W:
        f = flight_of(w)
        for k in FLIGHT_SUMS:
            t[k] += int(f[k])
        for d, key in ((n, "n"), (st, "steps"), (ct, "contact")):
            for c, v in f[key].items():
                d[c] = d.get(c, 0) + int(v)
        h = np.asarray(f.get("hist") or [], dtype=np.int64)
        hist = h if hist is None else hist + h
    S, live = t["started"], t["live_steps"]
    own, uns = tuple(LIVE["flight_own"]), tuple(LIVE["flight_unsafe"])
    on, oc, un = sum(n.get(c, 0) for c in own), sum(ct.get(c, 0) for c in own), sum(n.get(c, 0) for c in uns)
    return dict(started=S, started_per_seed=S / max(len({int(w["seed"]) for w in W}), 1), starts_per_1k=ratio(1000.0 * S, live), live_steps=live,
                n=n, share={c: ratio(v, S) for c, v in n.items()}, mean_s={c: ratio(st[c] * STEP_S, v) for c, v in n.items()},
                contact_s={c: ratio(ct[c] * STEP_S, v) for c, v in n.items()}, own_n=on, own_share=ratio(on, S), own_contact_s=ratio(oc * STEP_S, on),
                unsafe_share=ratio(un, S), truncated_share=ratio(n.get("truncated", 0), S), shelter_end_share=ratio(t["shelter_end"], S - un),
                flee_share=ratio(t["flee_steps"], live), reflex_share=ratio(t["reflex_steps"], live),
                self_flee_share=ratio(t["flee_steps"] - t["reflex_steps"], live), hist=[] if hist is None else hist.tolist())


# --------------------------------------------------------------------- #
# 관문 (LIVE_GATE.md 5절 — 10-21 변경 기록 (3) 1차 = 쫓긴 시간)
# --------------------------------------------------------------------- #


def gate_live(ev: dict, stuck: dict | None, check: dict | None) -> dict:
    """빠른 관문 (LIVE_GATE.md 5절, 변경 기록 (3) 사용자 10-21 '도망 시간' — 1차 = 쫓긴 시간). ev = {'N': {'current', 'candidate'}, 'G': {...}} (판 {meta, worlds},
    세계마다 도망 기록 flight), stuck = {'current', 'candidate'} (끼임 {summary}), check = 재현 확인 결과(ok None = 건너뜀).
    1차 P1 = N 세계 시드마다 스스로 벗어난 도망(은신처·원판·시야각·반경)의 쫓긴 시간 평균 초: 후보 − 지금 < 0 이고 ≤ −δ(LIVE flight_min_effect_s),
    짝 t ≤ −t_crit(n₁ − 1), n₁ = 두 두뇌 모두 그런 도망이 있는 시드 수.
    지킴 (문턱 t_crit(n − 1), n = 짝 시드 수) = N: GN(잡힘 — 옛 1차 — ·굶음·산), GF(1000 산 사슴-스텝당 시작한 도망), GV(실행 FLEE 몫),
    GC(잡힘·굶음·잘림으로 끝난 도망 몫) / G: GG(잡힘·굶음·산·쫓긴 시간) / G4·G5·G6. 통과 = R(했으면)·P1·지킴 모두 — A5 는 내보낼 때."""
    import r4_eval as re_

    N, G = ev["N"], ev["G"]
    c: dict = {}
    if check is None or check.get("ok") is None:
        c["R_check"] = dict(ok=None, skipped=True, why=(check or {}).get("why", "재현 확인 없음"), rule="환경 판 0·두뇌 바꿈 없음일 때만")
    else:
        c["R_check"] = dict(ok=bool(check["ok"]), steps=check.get("steps"), rule="재현 확인 (adapt GATE.md 변경 기록 (1) 규칙)")
    pc = re_.paired(re_.per_seed(N["candidate"], "caught"), re_.per_seed(N["current"], "caught"))
    n = int(pc["n"])
    T = t_crit(n - 1)
    n_g = int(re_.paired(re_.per_seed(G["candidate"], "caught"), re_.per_seed(G["current"], "caught"))["n"])
    TG = t_crit(n_g - 1)                                     # G 세계는 판정 시드 수가 따로다 (LIVE judge_seeds_g)
    p = flight_pair(N["candidate"], N["current"])
    n1 = int(p["n"])
    T1 = t_crit(n1 - 1)                                      # 1차 문턱은 두 두뇌 모두 스스로 벗어난 도망이 있는 시드 수에서
    dl = float(LIVE["flight_min_effect_s"])

    def t_ok(q: dict, cond: bool) -> bool:
        # 시드 하나면 표준오차가 nan 이고 t 가 ±∞ 라 어느 쪽 문턱도 넘는다 — 짝 t 를 셀 수 없으면 어떤 t 기준도 통과로 두지 않는다
        return bool(int(q["n"]) >= 2 and math.isfinite(q["se"]) and cond)

    c["P1_N_chase"] = dict(p, ok=t_ok(p, p["diff"] < 0 and p["diff"] <= -dl and p["t"] <= -T1),
                           rule=("N: 스스로 벗어난 도망의 쫓긴 시간 평균 초 후보 − 지금 < 0" + (f" 이고 ≤ −{dl:g}초" if dl > 0 else "")
                                 + f", 짝 t ≤ −{T1:.3f} (시드 {n1}, 빠진 시드 {len(p['dropped'])})"))
    c["GN_caught"] = dict(pc, ok=t_ok(pc, pc["t"] < T), rule=f"N: 짝 t < +{T:.3f} (옛 1차 — 유의하게 더 잡히지 않는다)")
    for key, sign in (("starved", 1), ("alive", -1)):
        q = re_.paired(re_.per_seed(N["candidate"], key), re_.per_seed(N["current"], key))
        c[f"GN_{key}"] = dict(q, ok=t_ok(q, q["t"] < T if sign > 0 else q["t"] > -T),
                              rule=f"N: 짝 t {'<' if sign > 0 else '>'} {'+' if sign > 0 else '−'}{T:.3f}")
    for key, name, why in (("starts", "GF_flight_starts", "1000 산 사슴-스텝당 시작한 도망 — 짧게 자주 도망쳐 평균만 줄이지 않는다"),
                           ("flee", "GV_flee_time", "산 사슴-스텝 가운데 실행 FLEE 몫(반사·스스로 고른 것) — 더 오래·일찍 달려 쫓김을 피하지 않는다"),
                           ("unsafe", "GC_flight_unsafe", "시작한 도망 가운데 잡힘·굶음·잘림 몫 — 긴 추격을 잡힘·잘림으로 바꿔 1차 평균에서 빼지 않는다")):
        q = flight_rate_pair(N["candidate"], N["current"], key)
        c[name] = dict(q, ok=t_ok(q, q["t"] < T), rule=f"N: 짝 t < +{T:.3f} ({why})")
    for key, sign in (("caught", 1), ("starved", 1), ("alive", -1)):
        q = re_.paired(re_.per_seed(G["candidate"], key), re_.per_seed(G["current"], key))
        c[f"GG_{key}"] = dict(q, ok=t_ok(q, q["t"] < TG if sign > 0 else q["t"] > -TG),
                              rule=f"G: 짝 t {'<' if sign > 0 else '>'} {'+' if sign > 0 else '−'}{TG:.3f}")
    q = flight_pair(G["candidate"], G["current"])
    TGc = t_crit(int(q["n"]) - 1)
    c["GG_chase"] = dict(q, ok=t_ok(q, q["t"] < TGc), rule=f"G: 쫓긴 시간(1차와 같은 셈) 짝 t < +{TGc:.3f} (시드 {q['n']}, 빠진 시드 {len(q['dropped'])})")
    an, ag, bg = re_.pooled(N["candidate"]), re_.pooled(G["candidate"]), re_.pooled(G["current"])
    c["G4_catch_in_shelter"] = dict(N=an["catch_cover"], G=ag["catch_cover"], ok=bool(an["catch_cover"] == 0 and ag["catch_cover"] == 0),
                                    rule="후보 N·G 판정 세계 모두 0")
    if stuck is not None and stuck.get("candidate") is not None and stuck.get("current") is not None:
        sd, sw = re_.stuck_counts(stuck["candidate"]), re_.stuck_counts(stuck["current"])
        c["G5_stuck"] = dict(candidate=sd, current=sw, ok=bool(sd["deer"] == 0 and sd["wolf"] <= sw["wolf"]), rule="G: 사슴 원판 끼임 0, 늑대 원판 끼임 ≤ 지금")
    else:
        c["G5_stuck"] = dict(ok=False, rule="끼임 세기가 없다 (통과로 두지 않는다)")
    use_ok = all(ag["beh"][x] > LIVE["use_min"] for x in ("graze", "flee", "hide"))
    c["G6_no_exploit"] = dict(shelter=ag["shelter"], shelter_current=bg["shelter"], beh=ag["beh"],
                              ok=bool(ag["shelter"] <= LIVE["shelter_x"] * bg["shelter"] and use_ok),
                              rule="G: 은신처 안 몫 ≤ 지금의 2배, 먹기·도망(실행 FLEE — 반사 포함)·숨기 모두 1% 넘게")
    p1 = c["P1_N_chase"]
    drop = len(p1["dropped"])
    bad = [k for k, v in c.items() if k.startswith(("GN_", "GF_", "GV_", "GC_", "GG_", "G4", "G5", "G6")) and v["ok"] is not True]
    if c["R_check"]["ok"] is False:
        verdict, why, brief = "기각", "재현 확인 실패 — 거울이 지금 게임과 다르다", "재현 확인 실패"
    elif n < 2 or not math.isfinite(pc["se"]):
        verdict, why, brief = "기각", f"판정 시드 {n}개 — 짝 t 를 셀 수 없다 (2개 이상이어야 한다)", f"판정 시드 {n}개 (2개 이상)"
    elif n1 < 2 or not math.isfinite(p1["se"]):
        verdict = "기각"
        why = f"쫓긴 시간을 잴 시드 {n1}개 — 두 두뇌 모두 스스로 벗어난 도망이 있는 시드가 2개 이상이어야 한다 (빠진 시드 {drop})"
        brief = f"쫓긴 시간 잴 시드 {n1}개 (2개 이상)"
    elif not p1["ok"]:
        verdict = "기각"
        why = (f"1차 P1 실패: 포만 없는 세계 스스로 벗어난 도망의 쫓긴 시간 평균 후보 {p1['a']:.2f}초 대 지금 {p1['b']:.2f}초 (짝 t {tfmt(p1['t'])}, "
               f"문턱 −{T1:.3f}" + (f", 최소 차이 −{dl:g}초" if dl > 0 else "") + f", 시드 {n1}, 빠진 시드 {drop})")
        brief = f"1차 쫓긴 시간 {p1['b']:.1f}→{p1['a']:.1f}초 t {tfmt(p1['t'], 1)} (문턱 −{T1:.2f})"
    elif bad:
        verdict, why = "기각", "지킴 기준 실패: " + ", ".join(bad)
        brief = "지킴 " + ", ".join(f"{k} (t {tfmt(c[k]['t'], 1)})" if "t" in c[k] else k for k in bad)
    else:
        verdict, why = "통과", "1차 P1(쫓긴 시간)·지킴 GN·GF·GV·GC·GG·G4·G5·G6 모두 통과" + ("" if c["R_check"]["ok"] else " (재현 확인 없음 — 중간 변화)")
        brief = ""
    summary = f"포만 없는 세계 쫓긴 시간 {p1['b']:.1f}→{p1['a']:.1f}초 (t {tfmt(p1['t'], 1)})" + (", 잡힘·도망 나빠짐 없음" if not bad else ", 지킴 실패")
    rep = dict(pooled_N=dict(candidate=an, current=re_.pooled(N["current"])), pooled_G=dict(candidate=ag, current=bg),
               shelter_G=re_.paired(re_.per_seed(G["candidate"], "shelter"), re_.per_seed(G["current"], "shelter")),
               flight={w: dict(candidate=flight_pooled(ev[w]["candidate"]), current=flight_pooled(ev[w]["current"])) for w in ("N", "G")})
    return dict(verdict=verdict, passed=verdict == "통과", why=why, brief=brief, summary=summary, n=n, t_crit=T, n_g=n_g, t_crit_g=TG,
                n_flight=n1, t_crit_flight=T1, dropped_flight=p1["dropped"], criteria=c, report=rep,
                rules={k: v for k, v in LIVE.items()},
                live_gate_md_sha256=hashlib.sha256(LIVE_GATE_MD.read_bytes()).hexdigest() if LIVE_GATE_MD.exists() else None)


def pct(x: float) -> str:
    return "—" if x != x else f"{x * 100:.1f}%"


def cause_parts(f: dict, causes) -> str:
    """끝 까닭 묶음 하나: 몫(시작한 도망 가운데)과 까닭마다 수 '몫 (수·수·…)'."""
    k = sum(f["n"].get(c, 0) for c in causes)
    return f"{pct(ratio(k, f['started']))} ({'·'.join(str(f['n'].get(c, 0)) for c in causes)})"


def flight_groups(f: dict) -> tuple:
    """끝 까닭 셋 묶음: 스스로 벗어남(LIVE flight_own), 그 밖 살아 끝남(바꿈·그만둠·끝까지 쫓김·안 쫓김), 잡힘·굶음·잘림(LIVE flight_unsafe)."""
    own, uns = tuple(LIVE["flight_own"]), tuple(LIVE["flight_unsafe"])
    return own, tuple(c for c in f["n"] if c not in own and c not in uns), uns


def fmt_flight(g: dict) -> str:
    """gate.md 도망 기록 표 (보고 — 전체 합의 비율): 세계·두뇌마다 시작한 도망(1000 산 사슴-스텝당), 스스로 벗어난 도망의 쫓긴 시간(전체 합),
    끝 까닭 묶음 몫(시작한 도망 가운데), 은신처에서 끝난 몫, 실행 FLEE 몫(반사 포함)·스스로 고른 FLEE 몫. 아래 줄에 1차 P1·GG_chase 의 시드 평균."""
    rep = g["report"]
    L = ["", "## 도망 기록 (보고 — 전체 합. 끝 까닭 몫은 시작한 도망 가운데, 정의 env_v2/world.py '야생 1단계' (w3) 도망 기록)", "",
         "| 세계 | 두뇌 | 시작 (1000 산 사슴-스텝당) | 쫓긴 시간 초 (스스로 벗어남, 전체 합) | 스스로 벗어남 (은신처·원판·시야각·반경) | "
         "그 밖 살아 끝남 (바꿈·그만둠·끝까지·안 쫓김) | 잡힘·굶음·잘림 | 은신처에서 끝 (살아 끝난 도망 가운데) | 실행 FLEE 몫 (반사 포함) | 스스로 고른 FLEE 몫 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for w in ("N", "G"):
        for b, nm in (("current", "지금"), ("candidate", "후보")):
            f = rep["flight"][w][b]
            own, oth, uns = flight_groups(f)
            L.append(f"| {w} | {nm} | {f['started']} ({f['starts_per_1k']:.2f}) | {f['own_contact_s']:.2f} | {cause_parts(f, own)} | {cause_parts(f, oth)} | "
                     f"{cause_parts(f, uns)} | {pct(f['shelter_end_share'])} | {pct(f['flee_share'])} | {pct(f['self_flee_share'])} |")
    p1, gg, dr = g["criteria"]["P1_N_chase"], g["criteria"]["GG_chase"], g["dropped_flight"]
    L += ["", f"- 1차 P1 (시드마다 평균을 낸 뒤 평균 — 위 표의 전체 합과 셈이 다르다): N 지금 {p1['b']:.2f}초 → 후보 {p1['a']:.2f}초, "
              f"짝 시드 {g['n_flight']} (빠진 시드 {len(dr)}{': ' + ', '.join(map(str, dr)) if dr else ''})",
          f"- G 쫓긴 시간 (지킴 GG_chase, 같은 셈): 지금 {gg['b']:.2f}초 → 후보 {gg['a']:.2f}초 (짝 t {tfmt(gg['t'])}, 시드 {gg['n']})"]
    return "\n".join(L)


# --------------------------------------------------------------------- #
# 내보내기 (임시 파일 → 다시 읽기 A5 → os.replace)
# --------------------------------------------------------------------- #


def export_brain(model: Path, brains: Path, round_no: int, attempt: int, rid: str, snapshot: str, env_text: str, gate: str,
                 play_id: str = "") -> dict:
    """두뇌 파일 brains/live_r<판>_<시도 이름>.json 을 쓴다: model.name = live_r<판>_<시도 이름>(언리얼 id = <이름>@<sha8>), adapt 블록(명세 3절).
    play_id = 스냅숏의 Play 번호 (언리얼은 적응 고리 Play 마다 새 번호를 정하고, 다른 Play 의 번호가 적힌 두뇌는 받지 않는다 — 앞 Play 에서 시작한 판이 늦게 끝난 경우).
    <이름>.json.tmp 에 써서 다시 읽어 확인(sha256·골든·행동·유한, 관측 21 계약)한 뒤에만 os.replace. 같은 이름이 있으면 쓰지 않는다."""
    import torch as th

    import export_weights_v3 as ex

    name = f"live_r{int(round_no)}_{rid}"
    brains = Path(brains)
    brains.mkdir(parents=True, exist_ok=True)
    final, tmp = brains / f"{name}.json", brains / f"{name}.json.tmp"
    if final.exists():
        raise FileExistsError(f"두뇌 파일 {final} 이 이미 있다 — 같은 이름은 덮지 않는다")
    prev = th.get_num_threads()
    th.set_num_threads(1)
    try:
        m = ex.load_model(Path(model))
        d = ex.brain_dict(m, Path(model), ex.brain_golden_config_for(m.policy.rep_obs_names),
                          world_label=f"실시간 적응 {rid} (포만 없는 스냅숏 세계 T)")
    finally:
        th.set_num_threads(prev)
    wsha = d["weights_sha256"]
    d["id"] = f"{name}@{wsha[:8]}"
    d["model"]["name"] = name
    d["model"]["path"] = path_text(model)
    d["exporter"] = "herbivore_rl/results/v3/live/live.py (export_weights_v3.brain_dict)"
    d["adapt"] = dict(round=int(round_no), attempt=int(attempt), run=rid, snapshot=snapshot, env=env_text, gate=gate, created_utc=utc_now(),
                      play_id=str(play_id or ""))
    try:
        ex.write_brain_file(tmp, d)
        v = ad.verify_brain_file(tmp)
        back = read_json(tmp) or {}
        v["contract_ok"] = bool(back.get("contract_hash") == CONTRACT_OBS21 and int(back.get("obs_dim", 0)) == 21)
        v["adapt_ok"] = back.get("adapt") == d["adapt"] and (back.get("model") or {}).get("name") == name
        v["ok"] = bool(v["ok"] and v["finite"] and v["contract_ok"] and v["adapt_ok"])
        if not v["ok"]:
            return dict(ok=False, name=name, id=d["id"], verify=v, why="다시 읽기 확인(A5) 실패")
        if final.exists():
            raise FileExistsError(f"두뇌 파일 {final} 이 그새 생겼다 — 같은 이름은 덮지 않는다")
        replace_retry(tmp, final)
    finally:
        tmp.unlink(missing_ok=True)
    return dict(ok=True, file=str(final), name=name, id=d["id"], weights_sha256=wsha, verify=v, adapt=d["adapt"])


# --------------------------------------------------------------------- #
# 한 판
# --------------------------------------------------------------------- #


def default_plan(**kw) -> dict:
    return dict(horizon=LIVE["horizon"], judge=LIVE["judge_seeds"], horizon_g=LIVE["horizon_g"], judge_g=LIVE["judge_seeds_g"],
                select=LIVE["select_seeds"], stuck=LIVE["stuck_seeds"],
                check=LIVE["check_seeds"], steps=LIVE["train_steps"], model_seeds=tuple(LIVE["model_seeds"]), workers=default_workers(),
                flight_cost=float(LIVE["train_flight_cost"]), skip_check=False, force_export=False, ckpt=CKPT, test=False) | kw


def plan_from_args(a) -> dict:
    """명령 인자 → 판 크기. 관문 상수와 다른 크기·시험 깃발이면 test (그때는 --root 가 실제 폴더가 아니어야 한다)."""
    pl = default_plan(workers=int(a.workers) if a.workers else default_workers(), ckpt=Path(a.ckpt) if a.ckpt else CKPT)
    for key, attr in (("judge", "judge_seeds"), ("judge_g", "judge_seeds_g"), ("select", "select_seeds"), ("stuck", "stuck_seeds"),
                      ("check", "check_seeds")):
        v = getattr(a, attr, None)
        if v:
            pl[key] = seed_range(v)
            if not inside(pl[key], GATE_SEEDS):
                raise SystemExit(f"--{attr.replace('_', '-')} {v} 는 관문 시드 {GATE_SEEDS[0]}~{GATE_SEEDS[1]} 안이어야 한다")
            if key in ("judge", "judge_g", "select") and pl[key][1] - pl[key][0] < 1:
                raise SystemExit(f"--{attr.replace('_', '-')} {v} 는 시드가 2개 이상이어야 한다 (짝 t 자유도 n − 1 ≥ 1)")
    if a.horizon:
        pl["horizon"] = int(a.horizon)
    if getattr(a, "horizon_g", None):
        pl["horizon_g"] = int(a.horizon_g)
    if a.steps:
        pl["steps"] = int(a.steps)
    if a.model_seeds:
        pl["model_seeds"] = tuple(int(s) for s in a.model_seeds)
    if getattr(a, "flight_cost", None) is not None:
        if float(a.flight_cost) < 0.0:
            raise SystemExit(f"--flight-cost {a.flight_cost} 는 0 이상이어야 한다")
        pl["flight_cost"] = float(a.flight_cost)
    pl["skip_check"], pl["force_export"] = bool(a.skip_check), bool(a.force_export)
    base = default_plan()
    pl["test"] = any(pl[k] != base[k] for k in ("horizon", "judge", "horizon_g", "judge_g", "select", "stuck", "check", "steps", "model_seeds",
                                                "flight_cost")) \
        or pl["skip_check"] \
        or pl["force_export"]
    if pl["test"] and Path(a.root).resolve() == DEFAULT_ROOT.resolve():
        raise SystemExit("시험 크기·시험 깃발은 --root 로 실제 폴더(Saved/EcoAdapt)가 아닌 곳을 줄 때만 쓴다 — 미리 적은 관문이 아니다")
    if not LIVE["flight_sizes_confirmed"] and Path(a.root).resolve() == DEFAULT_ROOT.resolve():
        raise SystemExit("1차 쫓긴 시간 기준의 크기(H·n·S·K·δ·도주 비용)를 아직 예비 측정으로 확정하지 않았다 (LIVE flight_sizes_confirmed 거짓, "
                         "LIVE_GATE.md 변경 기록 (3)) — 확정해 LIVE_GATE.md 와 LIVE 에 먼저 적기 전에는 실제 폴더에서 판·감시를 돌리지 않는다. "
                         "시험은 --root 로 다른 폴더를 준다")
    return pl


def plan_args(pl: dict) -> list[str]:
    """감시가 판 프로세스에 넘기는 인자 (크기 그대로)."""
    out = ["--workers", str(pl["workers"]), "--ckpt", str(pl["ckpt"])]
    base = default_plan()
    for key, flag in (("judge", "--judge-seeds"), ("judge_g", "--judge-seeds-g"), ("select", "--select-seeds"), ("stuck", "--stuck-seeds"),
                      ("check", "--check-seeds")):
        if pl[key] != base[key]:
            out += [flag, f"{pl[key][0]}-{pl[key][1]}"]
    if pl["horizon"] != base["horizon"]:
        out += ["--horizon", str(pl["horizon"])]
    if pl["horizon_g"] != base["horizon_g"]:
        out += ["--horizon-g", str(pl["horizon_g"])]
    if pl["steps"] != base["steps"]:
        out += ["--steps", str(pl["steps"])]
    if pl["model_seeds"] != base["model_seeds"]:
        out += ["--model-seeds"] + [str(s) for s in pl["model_seeds"]]
    if pl["flight_cost"] != base["flight_cost"]:
        out += ["--flight-cost", repr(float(pl["flight_cost"]))]
    if pl["skip_check"]:
        out.append("--skip-check")
    if pl["force_export"]:
        out.append("--force-export")
    return out


def plan_record(pl: dict) -> dict:
    return {k: (str(v) if isinstance(v, Path) else (list(v) if isinstance(v, tuple) else v)) for k, v in pl.items()}


def run_round(snap_path: Path, root: Path, attempt: int, rid: str, plan: dict, st: Status) -> dict:
    """한 판 (모듈 docstring '한 판'). 반환 = 판 결과 (state ∈ exported·rejected·refused·error). 학습 프로세스·워커 풀은 끝날 때 모두 닫는다."""
    root = Path(root)
    rd = rounds_dir(root) / rid
    rd.mkdir(parents=True, exist_ok=True)
    t_all = time.perf_counter()
    stages: dict = {}
    res = dict(format=ROUND_FORMAT, version=1, attempt=int(attempt), run=rid, snapshot=Path(snap_path).name, state="error", plan=plan_record(plan),
               plan_test=bool(plan["test"]), stages=stages, started_utc=utc_now())
    procs: list = []
    W, K = int(plan["workers"]), len(plan["model_seeds"])
    H, HG = int(plan["horizon"]), int(plan["horizon_g"])          # N 세계(P1·GN) 길이, G 세계(GG·G4~G6·끼임) 길이

    def mark(name, t0):
        stages[name] = round(time.perf_counter() - t0, 1)
        print(f"== {name}: {stages[name]}초", flush=True)
        atomic_write_json(rd / "progress.json", dict(stages=stages, state=st.f.get("state")))

    try:
        t0 = time.perf_counter()
        snap = read_snapshot(snap_path)
        e = env_info(snap)
        env_txt = env_summary(snap)
        res.update(key=pair_key(snap), env_digest=env_digest(snap), brain_weights_sha256=brain_sha(snap), env=env_txt, env_revision=e["revision"],
                   play_id=str(snap.get("play_id") or ""),
                   brain=snap["brain"].get("id"))
        st.set(state="converting", attempt=int(attempt), snapshot=Path(snap_path).name, env=env_txt, progress=-1.0,
               message=f"변환 중 — 시도 {attempt}, 환경 #{e['revision']}")
        st.start_heartbeat()                                 # 재현 확인·판정처럼 긴 단계에서도 HEARTBEAT_S 마다 다시 쓴다
        try:
            info = prepare(snap_path, snap, rd, brain_folders(root), flight_cost=plan["flight_cost"])
        except ad.Refused as ex_:
            res.update(state="refused", why=str(ex_), last_result=f"거부: {short(ex_, 60)}")
            mark("convert", t0)
            return res
        mark("convert", t0)
        start = Path(ad.ROOT / info["record"]["anchor"])
        res["start"] = info["record"]["anchor"]
        print(f"시도 {attempt} ({rid}): 스냅숏 {Path(snap_path).name} · 환경 #{e['revision']} {env_txt} · 두뇌 {snap['brain'].get('id')} → 시작 {res['start']}",
              flush=True)

        # R 재현 확인 (환경·두뇌가 처음 그대로일 때만)
        ok_r, why_r = r_applicable(snap)
        if plan["skip_check"]:
            ok_r, why_r = False, "시험: 재현 확인 건너뜀 (--skip-check)"
        if ok_r:
            t0 = time.perf_counter()
            seeds = seeds_of(plan["check"])
            st.set(state="checking", message=f"재현 확인 중 — 시드 {len(seeds)} × 지역, {snap['global_step']} 스텝", progress=-1.0)
            check = ad.check_eval(info, seeds, W)
            atomic_write_json(rd / "check.json", check)
            mark("check", t0)
            if check.get("ok") is False:
                res.update(state="rejected", verdict="기각", why="재현 확인 실패 — 학습하지 않는다 (check.json)", last_result="기각: 재현 확인 실패")
                return res
        else:
            check = dict(ok=None, why=why_r)
            atomic_write_json(rd / "check.json", check)
        res["check"] = dict(ok=check.get("ok"), why=check.get("why"))

        # 학습 ‖ 지금 두뇌 판정(N·G)·끼임 (학습 프로세스 수만큼 워커를 덜 쓴다)
        t0 = time.perf_counter()
        procs = launch_training(info, rd, start, rid, plan["model_seeds"], plan["steps"], plan["steps"], plan["ckpt"])
        judge, judge_g = seeds_of(plan["judge"]), seeds_of(plan["judge_g"])
        items = (eval_items(info, "current", start, judge, H, "N") + eval_items(info, "current", start, judge_g, HG, "G")
                 + stuck_items(info, "current", start, seeds_of(plan["stuck"]), HG))
        done = [0]
        total_train = K * int(plan["steps"])

        def msg_train():
            s = train_done_steps(procs)
            ev_ = f" · 지금 두뇌 판정 {done[0]}/{len(items)}" if done[0] < len(items) else ""
            return (f"학습 중 {fmt_steps(s)}/{fmt_steps(plan['steps'])} (모델 {K}개){ev_}",
                    0.5 * s / max(total_train, 1) + 0.5 * done[0] / max(len(items), 1))

        st.set(state="training", provider=msg_train)
        t1 = time.perf_counter()
        with Pool(max(1, min(W - K, len(items)))) as pool:
            out = pool.run(items, on_done=lambda: done.__setitem__(0, done[0] + 1))
        stages["eval_current"] = round(time.perf_counter() - t1, 1)
        models = {"current": start}
        steps_of = {"current:N": H, "current:G": HG}
        cur = gather(out, models, steps_of)
        for tag, r in cur.items():
            atomic_write_json(rd / f"{tag.replace(':', '_')}.json", r, indent=None)
        tr = list(procs)                                     # 맥박이 읽는 목록은 고정 (아래 procs = [] 뒤에도 0 으로 돌아가지 않는다)
        st.set(state="training", provider=lambda: (f"학습 중 {fmt_steps(train_done_steps(tr))}/{fmt_steps(plan['steps'])} (모델 {K}개)",
                                                   train_done_steps(tr) / max(total_train, 1)))
        rows = wait_training(procs)
        st.set(state="evaluating", message="학습 끝 — 후보 판정 준비", progress=-1.0)
        procs = []
        stages["train_learn"] = round(max([r["learn_s"] or 0.0 for r in rows] + [0.0]), 1)      # 순수 학습 (프로세스 시작 빼고)
        mark("train_and_eval_current", t0)
        atomic_write_json(rd / "train.json", dict(steps=int(plan["steps"]), runs=rows))
        okr = [r for r in rows if r["ok"]]
        if not okr:
            raise RuntimeError("학습에 성공한 후보가 없다: " + ", ".join(f"s{r['seed']} rc {r['rc']}" for r in rows))

        # 후보 고르기 (K > 1 — N 세계 고르기 시드, 스스로 벗어난 도망의 쫓긴 시간 최저 → 잡힌 몫 → 굶은 몫 → 모델 시드. 10-21 (3) 뒤 1차와 같은 잣대)
        import r4_eval as re_

        if len(okr) > 1:
            t0 = time.perf_counter()
            sel = seeds_of(plan["select"])
            models_s = {f"s{r['seed']}": Path(r["model"]) for r in okr}
            items = [it for tag, m in models_s.items() for it in eval_items(info, tag, m, sel, H, "N")]
            done = [0]
            st.set(state="evaluating", provider=lambda: (f"후보 고르기 {done[0]}/{len(items)} 세계 (모델 {len(okr)}개)", done[0] / max(len(items), 1)))
            with Pool(max(1, min(W, len(items)))) as pool:
                out = pool.run(items, on_done=lambda: done.__setitem__(0, done[0] + 1))
            sres = gather(out, models_s, {})
            srows = []
            for r in okr:
                p = re_.pooled(sres[f"s{r['seed']}:N"])
                fs = flight_pooled(sres[f"s{r['seed']}:N"])["own_contact_s"]
                srows.append(dict(seed=r["seed"], model=r["model"], flight_s=fs, caught=p["caught"], starved=p["starved"], alive=p["alive"]))
            srows.sort(key=lambda x: (x["flight_s"] if x["flight_s"] == x["flight_s"] else math.inf, x["caught"], x["starved"], x["seed"]))
            atomic_write_json(rd / "select.json", dict(chosen=srows[0]["model"], rule="N 세계 고르기 시드 쫓긴 시간(스스로 벗어난 도망) 최저 → 잡힌 몫 → 굶은 몫 → 모델 시드",
                                                        rows=srows))
            cand = Path(srows[0]["model"])
            mark("select", t0)
        else:
            cand = Path(okr[0]["model"])
        res["candidate"] = str(cand)

        # 후보 판정 N·G + 끼임
        t0 = time.perf_counter()
        items = (eval_items(info, "candidate", cand, judge, H, "N") + eval_items(info, "candidate", cand, judge_g, HG, "G")
                 + stuck_items(info, "candidate", cand, seeds_of(plan["stuck"]), HG))
        done = [0]
        st.set(state="evaluating", provider=lambda: (f"후보 판정 {done[0]}/{len(items)} 세계", done[0] / max(len(items), 1)))
        with Pool(max(1, min(W, len(items)))) as pool:
            out = pool.run(items, on_done=lambda: done.__setitem__(0, done[0] + 1))
        cnd = gather(out, {"candidate": cand}, {"candidate:N": H, "candidate:G": HG})
        for tag, r in cnd.items():
            atomic_write_json(rd / f"{tag.replace(':', '_')}.json", r, indent=None)
        mark("eval_candidate", t0)

        # 관문
        t0 = time.perf_counter()
        st.set(state="gating", message="관문 셈", progress=-1.0)
        ev = {w: dict(current=cur[f"current:{w}"], candidate=cnd[f"candidate:{w}"]) for w in ("N", "G")}
        g = gate_live(ev, dict(current=cur.get("current:stuck"), candidate=cnd.get("candidate:stuck")), check)
        g.update(candidate=ad._rel(cand), current=ad._rel(start), plan=plan_record(plan),
                 profile="시험 크기 (관문 상수 아님 — 판정 아님)" if plan["test"] else "LIVE_GATE.md 관문 상수")
        atomic_write_json(rd / "gate.json", g)
        (rd / "gate.md").write_text(f"# 실시간 관문 {rid}\n\n후보 `{g['candidate']}` 대 지금 두뇌 `{g['current']}` (규칙 LIVE_GATE.md, {g['profile']}, "
                                    f"N 시드 {g['n']}·문턱 {g['t_crit']:.3f}, 1차 쫓긴 시간 시드 {g['n_flight']}·문턱 {g['t_crit_flight']:.3f}, "
                                    f"G 시드 {g['n_g']}·문턱 {g['t_crit_g']:.3f})\n\n{ad.fmt_gate(g)}\n{fmt_flight(g)}\n",
                                    encoding="utf-8", newline="\n")
        mark("gate", t0)
        res.update(verdict=g["verdict"], why=g["why"], gate_summary=g["summary"])
        print(f"1차 P1 쫓긴 시간: 짝 시드 {g['n_flight']}/{g['n']} (두 두뇌 모두 스스로 벗어난 도망이 없어 빠진 시드 {len(g['dropped_flight'])})", flush=True)
        print(f"관문 {g['verdict']} — {g['why']}", flush=True)
        if not g["passed"] and not plan["force_export"]:
            res.update(state="rejected", last_result=f"기각: {g['brief']}")
            return res

        # 내보내기 (판 번호 = 지난 채택 + 1)
        t0 = time.perf_counter()
        round_no = int(load_state(root)["round"]) + 1
        st.set(state="exporting", round=round_no - 1, message=f"두뇌 파일 쓰는 중 — 판 {round_no} (다시 읽어 확인)", progress=-1.0)
        gate_txt = g["summary"] if g["passed"] else f"시험 내보내기(--force-export) — 관문 {g['verdict']}: {g['brief']}"
        xo = export_brain(cand, root / "brains", round_no, attempt, rid, Path(snap_path).name, env_txt, gate_txt, play_id=str(snap.get("play_id") or ""))
        atomic_write_json(rd / "export.json", xo)
        mark("export", t0)
        if not xo["ok"]:
            res.update(state="rejected", verdict="기각", why=f"A5 실패: {xo['why']}", last_result="기각: 두뇌 파일 다시 읽기(A5) 실패")
            return res
        res.update(state="exported", round=round_no, brain_file=xo["file"], brain_id=xo["id"], exported_weights_sha256=xo["weights_sha256"],
                   last_result=f"통과: 판 {round_no} — {g['summary']}" if g["passed"] else f"시험 내보내기: 판 {round_no} (관문 {g['verdict']})")
        print(f"두뇌 파일 {xo['file']} ({xo['id']}) — 판 {round_no}", flush=True)
        return res
    except KeyboardInterrupt:                             # 사람이 멈췄다 — 오류가 아니다 (처리한 환경으로 적지 않는다: superseded 는 열쇠를 남기지 않는다)
        res.update(state="superseded", why="중단됨 (KeyboardInterrupt)", last_result="그만둠: 중단됨 (Ctrl+C)")
        return res
    except BaseException as ex_:                          # 어떤 예외도 상태 error 로 남긴다 (감시는 이어 간다)
        res.update(state="error", why=f"{type(ex_).__name__}: {ex_}", last_result=f"오류: {short(f'{type(ex_).__name__}: {ex_}', 60)}")
        traceback.print_exc()
        return res
    finally:
        st.stop_heartbeat()
        stop_procs(procs)
        res["wall_s"] = round(time.perf_counter() - t_all, 1)
        res["ended_utc"] = utc_now()


def final_status(st: Status, res: dict, round_now: int) -> None:
    """판이 끝난 뒤 상태 줄."""
    s = res.get("state", "error")
    msg = {"exported": f"판 {res.get('round')} 내보냄 — 언리얼이 다음 결정 경계에서 바꿔 끼움",
           "rejected": f"기각 — 게임 두뇌 그대로 ({short(str(res.get('last_result', '')).removeprefix('기각: '), 50)})",
           "refused": f"거부 — {short(res.get('why', ''), 60)}",
           "superseded": f"그만둠 — {short(res.get('why', ''), 60)}",
           "error": f"오류 — {short(res.get('why', ''), 60)}"}.get(s, s)
    st.set(state=s, round=int(round_now), message=msg, progress=1.0 if s in ("exported", "rejected") else -1.0,
           last_result=res.get("last_result") or st.f.get("last_result", ""))


def cmd_round(a) -> int:
    root = Path(a.root)
    pl = plan_from_args(a)
    for sub in ("snapshots", "brains", "live"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    lock = None if a.child else acquire_lock(root, "round")        # 감시가 띄운 판은 감시의 잠금 아래에서 돈다
    try:
        return _round(a, root, pl)
    finally:
        if lock is not None:
            release_lock(lock)


def _round(a, root: Path, pl: dict) -> int:
    attempt = int(a.attempt) if a.child and a.attempt else begin_attempt(root)
    if a.child and a.run_id:
        rid = a.run_id
    else:
        try:
            snap = read_snapshot(a.snapshot)
            rid = make_run_id(attempt, snap)
        except Exception:
            rid = f"a{attempt}_{datetime.now():%Y%m%dT%H%M%S}_e0"
    st = Status(root)
    res = run_round(Path(a.snapshot), root, attempt, rid, pl, st)
    state = finish_attempt(root, res)
    atomic_write_json(rounds_dir(root) / rid / "result.json", res)
    final_status(st, res, int(state["round"]))
    print(f"시도 {attempt} 끝: {res['state']} — {res.get('last_result', '')} ({res.get('wall_s')}초, 단계 {res['stages']})", flush=True)
    return 0 if res["state"] in ("exported", "rejected", "refused") else 1


# --------------------------------------------------------------------- #
# 감시
# --------------------------------------------------------------------- #


def kill_tree(proc, timeout: float = 15.0) -> None:
    """자식 프로세스와 그 아래(학습 프로세스·워커 풀) 모두 끝낸다. 윈도에서 Popen.terminate 는 그 프로세스 하나만 끝내므로, 먼저 멈춰 세우고 자손 목록을
    잡은 뒤 모두 끝낸다(psutil — 없으면 taskkill /T /F)."""
    if proc.poll() is not None:
        return
    kids = []
    try:
        import psutil
    except ImportError:
        psutil = None
    if psutil is not None:
        try:
            me = psutil.Process(proc.pid)
            try:
                me.suspend()                                  # 새 자손을 더 띄우지 못하게
            except psutil.Error:
                pass
            kids = me.children(recursive=True)
        except psutil.Error:
            kids = []
        for k in kids:
            try:
                k.kill()
            except psutil.Error:
                pass
    elif os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=timeout)
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout)
    if psutil is not None and kids:
        _, alive = psutil.wait_procs(kids, timeout=timeout)
        for k in alive:
            try:
                k.kill()
            except psutil.Error:
                pass


def newest_snapshot(folder: Path, cut: float = 0.0) -> Path | None:
    """스냅숏 폴더의 가장 새 *.json (mtime, 이름 순 — *.tmp 는 보지 않는다). cut 보다 오래된 파일은 보지 않는다."""
    best, bk = None, None
    if not Path(folder).is_dir():
        return None
    for p in Path(folder).glob("*.json"):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if m < cut:
            continue
        k = (m, p.name)
        if bk is None or k > bk:
            best, bk = p, k
    return best


def decide(key: str, running_key: str | None, st: dict) -> str:
    """새 스냅숏을 어떻게 할까: 'keep' (같은 환경의 판이 돈다), 'supersede' (다른 환경의 판이 돈다 — 끝내고 새로), 'skip' (이미 끝낸 환경), 'start'."""
    if running_key is not None:
        return "keep" if key == running_key else "supersede"
    return "skip" if is_processed(st, key) else "start"


def default_launcher(cmd: list[str], fh) -> subprocess.Popen:
    """판 프로세스 — 따로 된 프로세스 묶음(감시 창의 Ctrl+C 는 감시만 받고, 판 나무는 감시가 kill_tree 로 끝낸다)."""
    return subprocess.Popen(cmd, cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONUTF8="1"), **own_group())


def exported_brain(brains: Path, rid: str, attempt: int):
    """이 시도가 쓴 두뇌 파일 brains/live_r<판>_<시도 이름>.json (adapt.run·attempt 가 맞고 판 번호가 있을 때만) → (경로, 내용) 또는 None.
    os.replace 는 다시 읽기(A5) 뒤에만 하므로 있으면 확인을 마친 파일이다."""
    for f in sorted(Path(brains).glob(f"live_r*_{rid}.json")):
        b = read_json(f)
        a_ = (b or {}).get("adapt") if isinstance(b, dict) else None
        if isinstance(a_, dict) and a_.get("run") == rid and a_.get("attempt") == int(attempt) and int(a_.get("round") or 0) > 0:
            return f, b
    return None


class Watcher:
    """스냅숏 폴더 감시 (명세 6절). tick() 한 번 = 판 프로세스 끝남 확인 → 가장 새 스냅숏 보기(시작·건너뜀·그만두고 새로) → 쉬는 동안 맥박."""

    def __init__(self, root: Path, plan: dict, launcher=default_launcher, new_only: bool = False, log=None):
        self.root = Path(root)
        self.snapdir = self.root / "snapshots"
        for sub in ("snapshots", "brains", "live"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        self.plan, self.launcher = plan, launcher
        self.status = Status(self.root)
        self.child: dict | None = None
        self.last_sig = None
        self.bad_since: dict = {}
        self.tries: dict = {}                                # 스냅숏(sig)마다 처리하다 난 예외 수 (TICK_RETRY)
        self.err_tries: dict = {}                            # 열쇠마다 이 감시에서 오류로 끝난 판 수 (ERROR_RETRY)
        self.cut = time.time() if new_only else 0.0
        self.last_beat = 0.0
        self.log = log or (lambda s: print(f"[live {datetime.now():%H:%M:%S}] {s}", flush=True))
        self.status.set(state="idle", message="스냅숏 기다림 — 환경이 바뀌면 언리얼이 씀", progress=-1.0)

    def tick(self) -> None:
        if self.child is not None and self.child["proc"].poll() is not None:
            self._finish_child()
        p = newest_snapshot(self.snapdir, self.cut)
        if p is not None:
            try:
                s = p.stat()
                sig = (str(p), s.st_mtime_ns, s.st_size)
            except OSError:
                sig = None
            if sig is not None and sig != self.last_sig:
                self._consider(p, sig)
        if self.child is None and time.time() - self.last_beat >= HEARTBEAT_S:
            self.status.refresh()
            self.last_beat = time.time()

    def _consider(self, p: Path, sig) -> None:
        try:
            snap = read_snapshot(p)
        except ad.Refused as e:
            self.last_sig = sig
            self.log(f"스냅숏 {p.name} 거부: {e}")
            if self.child is None:                           # 판이 돌면 상태 줄은 판의 것
                self.status.set(state="waiting", message=f"스냅숏 형식 거부 — {p.name}", progress=-1.0)
            return
        except (ValueError, OSError) as e:                   # 아직 덜 쓰였다 — 다음에 다시 본다
            first = self.bad_since.setdefault(sig, time.time())
            if time.time() - first > BAD_SNAPSHOT_S:
                self.last_sig = sig
                self.log(f"스냅숏 {p.name} 이 {BAD_SNAPSHOT_S:.0f}초 넘게 읽히지 않는다 — 건너뜀 ({type(e).__name__})")
            return
        self.last_sig = sig
        try:
            self._act(p, snap)
            self.tries.pop(sig, None)
        except BaseException:                               # 그만두기·시작이 끝까지 못 갔다 — 다음 tick 에 같은 스냅숏을 다시 본다 (TICK_RETRY 번까지)
            n = self.tries[sig] = self.tries.get(sig, 0) + 1
            if n < TICK_RETRY:
                self.last_sig = None
            else:
                self.log(f"스냅숏 {p.name}: 처리하다 {n}번 실패 — 더 보지 않는다")
            raise

    def _act(self, p: Path, snap: dict) -> None:
        key = pair_key(snap)
        st = load_state(self.root)
        act = decide(key, self.child["key"] if self.child else None, st)
        if act == "keep":
            self.log(f"스냅숏 {p.name}: 돌고 있는 판과 같은 환경 — 그대로")
            return
        if act == "supersede":
            self._supersede(p.name)
            act = "skip" if is_processed(load_state(self.root), key) else "start"
        if act == "skip":
            self.log(f"스냅숏 {p.name}: 환경 같음 — 건너뜀 ({key})")
            self.status.set(state="waiting", snapshot=p.name, env=env_summary(snap), message="환경 같음 — 건너뜀", progress=-1.0)
            return
        self._start(p, snap, key)

    def _start(self, p: Path, snap: dict, key: str) -> None:
        attempt = begin_attempt(self.root)
        rid = make_run_id(attempt, snap)
        rd = rounds_dir(self.root) / rid
        rd.mkdir(parents=True, exist_ok=True)
        cmd = ([sys.executable, str(HERE), "round", "--snapshot", str(p), "--root", str(self.root), "--attempt", str(attempt), "--run-id", rid,
                "--child"] + plan_args(self.plan))
        fh = open(rd / "round.log", "w", encoding="utf-8")
        try:
            proc = self.launcher(cmd, fh)
        except BaseException:
            fh.close()
            raise
        self.child = dict(proc=proc, fh=fh, key=key, rid=rid, attempt=attempt, snapshot=p.name, t0=time.time())
        env_txt = env_summary(snap)
        self.status.set(state="converting", attempt=attempt, snapshot=p.name, env=env_txt, progress=-1.0,
                        message=f"새 환경 — 시도 {attempt} 시작 ({env_txt})")
        self.log(f"시도 {attempt} 시작: {p.name} → {rid} (pid {proc.pid}, 기록 {rd / 'round.log'})")

    def _supersede(self, newer: str) -> None:
        c = self.child
        if c["proc"].poll() is not None:                     # 그새 스스로 끝났다 — 보통 끝맺음
            self._finish_child()
            return
        c["stopped"] = f"새 스냅숏 {newer} (다른 환경)"       # 끝낸 뒤 정리가 실패해 다음 tick 에 다시 정리해도 까닭을 잃지 않는다
        kill_tree(c["proc"])                                 # 끝낼 때까지 self.child 를 쥐고 있다 (실패하면 다음 tick 에 다시)
        res = self._settle(c)
        self.child = None
        self.log(f"시도 {c['attempt']} 그만둠 — 새 스냅숏 {newer} (판 프로세스 나무를 끝냈다): {res.get('state')} — {res.get('last_result', '')}")

    def _settle(self, c: dict) -> dict:
        """판 프로세스가 끝난 뒤(스스로, 또는 감시가 끝냄 — c['stopped'] 에 까닭) 결과를 한 번만 적는다.
        1) 판이 이미 finish_attempt 로 적었으면(state.json 기록에 이 시도가 있다) 그 결과를 쓴다 — 두 번 적지 않는다.
        2) 아니고 이 시도의 두뇌 파일이 brains/ 에 있으면(os.replace 뒤, 기록 전에 끝남) 내보냄으로 적는다 — 판 번호, '같은 환경 + 새 두뇌' 열쇠.
           언리얼은 이미 그 파일을 받았을 수 있다.
        3) 아니면 끝냈으면 superseded, 스스로 끝났으면 error.
        남은 학습 프로세스(판 프로세스가 정리 없이 죽었을 때)와 다시 읽기 전에 끝난 임시 두뇌 파일도 치운다."""
        rc, stopped = c["proc"].returncode, c.get("stopped")
        try:
            c["fh"].close()
        except OSError:
            pass
        rd = rounds_dir(self.root) / c["rid"]
        k = kill_recorded(rd)
        if k:
            self.log(f"시도 {c['attempt']}: 남은 학습 프로세스 {k}개를 끝냈다")
        for t in (self.root / "brains").glob(f"live_r*_{c['rid']}.json.tmp"):
            t.unlink(missing_ok=True)
        st = load_state(self.root)
        row = next((h for h in reversed(st["history"]) if h.get("attempt") == c["attempt"] and h.get("run") == c["rid"]), None)
        base = dict(format=ROUND_FORMAT, version=1, attempt=c["attempt"], run=c["rid"], snapshot=c["snapshot"], key=c["key"],
                    wall_s=round(time.time() - c["t0"], 1))
        if row is not None:                                  # 1) 판이 적었다
            res = read_json(rd / "result.json")
            if isinstance(res, dict) and res.get("format") == ROUND_FORMAT and stopped is None:
                d = read_json(self.status.path)
                if isinstance(d, dict) and d.get("format") == STATUS_FORMAT:
                    self.status.adopt(d)
                self.status.refresh()
                return res
            if not isinstance(res, dict) or res.get("format") != ROUND_FORMAT:       # 기록 뒤 result.json 전에 끝났다
                res = base | {k_: v for k_, v in row.items() if k_ in HISTORY_KEYS and v is not None}
                atomic_write_json(rd / "result.json", res)
            final_status(self.status, res, int(st["round"]))
            return res
        xb = exported_brain(self.root / "brains", c["rid"], c["attempt"])
        if xb is not None:                                   # 2) 두뇌 파일을 쓴 뒤 기록 전에 끝났다
            f, b = xb
            rno, gate = int(b["adapt"]["round"]), str(b["adapt"].get("gate", ""))
            res = base | dict(state="exported", round=rno, brain_file=str(f), brain_id=b.get("id"), env_digest=str(c["key"]).split("|")[0],
                              exported_weights_sha256=b.get("weights_sha256"),
                              why=f"두뇌 파일을 쓴 뒤 판 프로세스가 기록 전에 끝났다 ({stopped or f'rc {rc}'}) — 내보냄으로 적는다",
                              last_result=f"내보냄: 판 {rno} — {short(gate, 50)}")
        elif stopped is not None:                            # 3) 끝냈다
            res = base | dict(state="superseded", why=stopped, last_result=f"그만둠: {short(stopped, 60)}")
        else:
            res = base | dict(state="error", why=f"판 프로세스가 결과 없이 끝났다 (rc {rc}) — {rd / 'round.log'}",
                              last_result=f"오류: 시도 {c['attempt']} 비정상 종료 (rc {rc})")
        atomic_write_json(rd / "result.json", res)
        st = finish_attempt(self.root, res)
        final_status(self.status, res, int(st["round"]))
        return res

    def _finish_child(self) -> None:
        c = self.child
        res = self._settle(c)
        self.child = None
        rc = c["proc"].returncode
        if res.get("state") == "error" and not is_processed(load_state(self.root), c["key"]):
            n = self.err_tries[c["key"]] = self.err_tries.get(c["key"], 0) + 1
            if n < ERROR_RETRY:                              # 같은 스냅숏을 다음에 다시 본다 (환경마다 스냅숏은 하나뿐이다)
                self.last_sig = None
                self.log(f"시도 {c['attempt']} 오류 — 같은 환경을 한 번 더 한다")
        self.last_beat = time.time()
        self.log(f"시도 {c['attempt']} 끝 (rc {rc}): {res.get('state')} — {res.get('last_result', '')}")

    def stop(self) -> None:
        if self.child is not None:
            c = self.child
            if c["proc"].poll() is None:
                c["stopped"] = "감시를 멈췄다"
                kill_tree(c["proc"])
            self._settle(c)
            self.child = None
        self.status.set(state="idle", message="파이썬 감시 멈춤", progress=-1.0)


def cmd_watch(a) -> int:
    pl = plan_from_args(a)
    lock = acquire_lock(Path(a.root), "watch")
    try:
        w = Watcher(Path(a.root), pl, new_only=not a.existing)
        w.log(f"감시 시작: {w.snapdir} (워커 {pl['workers']}, 학습 {fmt_steps(pl['steps'])} × 모델 {len(pl['model_seeds'])}, 판정 시드 "
              f"N {pl['judge'][0]}~{pl['judge'][1]} × {pl['horizon']} 스텝 · G {pl['judge_g'][0]}~{pl['judge_g'][1]} × {pl['horizon_g']} 스텝, 1차 = 쫓긴 시간"
              + (", 도주 비용 {:g}".format(pl["flight_cost"]) if pl["flight_cost"] > 0 else "") + (", 시험 크기)" if pl["test"] else ")"))
        try:
            while True:
                try:
                    w.tick()
                except Exception as e:                      # 감시는 멈추지 않는다
                    traceback.print_exc()
                    w.status.set(state="error", message=f"감시 오류 — {short(f'{type(e).__name__}: {e}', 60)}", progress=-1.0)
                time.sleep(POLL_S)
        except KeyboardInterrupt:
            w.log("멈춤 (Ctrl+C)")
        finally:
            w.stop()
    finally:
        release_lock(lock)
    return 0


# --------------------------------------------------------------------- #
# 예비 측정 (시드 34900~34999 만)
# --------------------------------------------------------------------- #


def at_horizon(res: dict, h: int) -> dict:
    """예비 측정 판 → 판정 길이 h 의 잡힘·굶음·산·도망 기록(그 길이에서 끊은 것)으로 바꾼 판 (r4_eval 지표 꼴)."""
    return dict(meta=res["meta"], worlds=[dict(w, **w["at"][str(int(h))]) for w in res["worlds"]])


def subset(res: dict, seeds) -> dict:
    s = {int(x) for x in seeds}
    return dict(meta=res["meta"], worlds=[w for w in res["worlds"] if int(w["seed"]) in s])


def pilot_pair(a: dict, b: dict, h: int) -> dict:
    """a − b 잡힌 몫 짝 차이 (판정 길이 h): 평균·sd(시드마다 차이)·t, 그리고 그 sd 로 차이 d 를 5%·검정력 80% 로 가를 시드 수."""
    import r4_eval as re_

    p = re_.paired(re_.per_seed(at_horizon(a, h), "caught"), re_.per_seed(at_horizon(b, h), "caught"))
    sd = float(p["se"] * math.sqrt(p["n"])) if p["n"] > 1 else float("nan")
    need = {f"{d * 100:g}%p": (int(math.ceil(((_Z975 + 0.8416) * sd / d) ** 2)) if sd == sd else None) for d in (0.005, 0.01, 0.02)}
    return dict(p, sd=sd, n_needed=need)


def pilot_flight_pair(a: dict, b: dict, h: int) -> dict:
    """a − b 쫓긴 시간 짝 차이 (판정 길이 h, 관문 1차 P1 과 같은 셈 `flight_pair` — 빠진 시드 dropped): 평균·sd(시드마다 차이)·t, 그 sd 로
    0.25·0.5·1 초를 5%·검정력 80% 로 가를 시드 수, 지킴 GF·GV·GC 와 같은 셈의 짝 차이(starts·flee·unsafe)."""
    A, B = at_horizon(a, h), at_horizon(b, h)
    p = flight_pair(A, B)
    sd = float(p["se"] * math.sqrt(p["n"])) if p["n"] > 1 else NAN
    need = {f"{d:g}s": (int(math.ceil(((_Z975 + 0.8416) * sd / d) ** 2)) if sd == sd else None) for d in (0.25, 0.5, 1.0)}
    guards = {}
    for key in ("starts", "flee", "unsafe"):
        q = flight_rate_pair(A, B, key)
        guards[key] = dict(a=q["a"], b=q["b"], diff=q["diff"], t=q["t"], n=q["n"])
    return dict(p, sd=sd, n_needed=need, **guards)


def scale_items(info: dict, model: Path, seeds, steps: int) -> list:
    """도주 비용 기준 크기 일: T 세계(train.yaml, 지역 섞기의 지역마다 그 지역 설정) × 학습 시드 — 지역 스냅숏 먹이 지도를 덮는다(학습 train-one 과 같다)."""
    from env_v2.config import load_v2_config
    from env_v2.vec_env import region_configs, region_mix_params

    cfg = load_v2_config(Path(info["dir"]) / "train.yaml")
    cfgs = region_configs(cfg, region_mix_params(cfg.v2["train"]["region_mix"], cfg))
    food = {n: r["cap"] for n, r in info["regions"].items()}
    return [("scale", f"scale:{r}", dict(cfg=c.to_dict(), seed=int(s), steps=int(steps), model=str(model), region=r, snap_food=food[r]))
            for r, c in cfgs.items() for s in seeds]


def scale_summary(rows: list, train_yaml: Path) -> dict:
    """도주 비용 기준 크기 (LIVE_GATE.md 변경 기록 (3) — flight_cost 를 고르는 자료): 사슴-스텝 평균 보상(죽음·번식 포함), FLEE 스텝(그 가운데 반사 몫)·그 밖 스텝의
    평균 에너지 칸(보상 − rew_alive, 죽음·번식 스텝 뺌)과 그 차이, 설정에서 셈한 뛰기 대사 비용 rew_energy × energy_drain × (c_rest + c_move·뛰기²)과
    걷기·정지 대사 비용."""
    from env_v2.config import load_v2_config

    cfg = load_v2_config(Path(train_yaml))
    sp = cfg.v2["features"]["speed"]
    gs = [float(x) for x in sp["gait_speed"]]
    mult = [float(sp["c_rest"]) + float(sp["c_move"]) * g * g for g in gs]
    unit = float(cfg.rew_energy) * float(cfg.energy_drain)
    t = {k: sum(r.get(k, 0) for r in rows) for k in ("steps", "rew", "deaths", "repro", "flee_n", "flee_e", "other_n", "other_e", "reflex_n")}
    fe = t["flee_e"] / t["flee_n"] if t["flee_n"] else NAN
    oe = t["other_e"] / t["other_n"] if t["other_n"] else NAN
    return dict(worlds=len(rows), deer_steps=t["steps"], reward_per_step=t["rew"] / max(t["steps"], 1), rew_alive=float(cfg.rew_alive),
                deaths_per_1k=1000.0 * t["deaths"] / max(t["steps"], 1), repro_per_1k=1000.0 * t["repro"] / max(t["steps"], 1),
                flee_share=t["flee_n"] / max(t["flee_n"] + t["other_n"], 1), reflex_share=t["reflex_n"] / max(t["flee_n"] + t["other_n"], 1),
                energy_flee=fe, energy_other=oe, energy_gap=oe - fe,
                metabolic=dict(stop=unit * mult[0], walk=unit * mult[1], run=unit * mult[2]), run_extra_over_stop=unit * (mult[2] - mult[0]))


def cmd_pilot(a) -> int:
    """예비 측정 (명세 6절 — LIVE_GATE.md 변경 기록 (3) 뒤 '쫓긴 시간' 기준): 지금 두뇌 대 R5 s3·--extra-models 두뇌(N·G, 판정 길이마다 — 잡힘과
    쫓긴 시간의 시드마다 짝 차이 sd, 0.25·0.5·1 초를 가를 시드 수, 지킴 GF·GV·GC 차이, 끝 까닭 몫), T 세계 measure-fdec, 도주 비용 기준 크기(scale),
    --flight-cost 값마다 K 모델 × S 후보 대 지금 두뇌, 단계별 시간. 시드 34900~34999 만 쓴다 (관문 시드 35000~35199 는 쓰지 않는다). 결과로 LIVE_GATE.md
    크기를 고른다 — 판정이 아니다."""
    import r4_eval as re_

    root = Path(a.root)
    seeds_lh, cand_lh = seed_range(a.seeds), seed_range(a.cand_seeds)
    for name, lh in (("--seeds", seeds_lh), ("--cand-seeds", cand_lh)):
        if not inside(lh, PILOT_SEEDS):
            raise SystemExit(f"{name} {lh} 는 예비 측정 시드 {PILOT_SEEDS[0]}~{PILOT_SEEDS[1]} 안이어야 한다 (관문 시드를 쓰지 않는다)")
    extras: dict = {}
    for item in a.extra_models or []:
        tag, sep, path = str(item).partition("=")
        p = Path(path) if Path(path).is_absolute() else ROOT / path
        if not sep or not tag or tag in ("current", "r5") or tag in extras or ":" in tag:
            raise SystemExit(f"--extra-models {item} 는 '이름=모델 zip' 이어야 한다 (이름은 겹치지 않고 current·r5 가 아니다)")
        if not p.exists():
            raise SystemExit(f"--extra-models {item}: 모델 {p} 가 없다")
        extras[tag] = p
    fcs = sorted({float(x) for x in (a.flight_cost if a.flight_cost else [LIVE["train_flight_cost"]])})
    if any(x < 0.0 for x in fcs):
        raise SystemExit(f"--flight-cost {fcs} 는 0 이상이어야 한다")
    hs = sorted({int(h) for h in a.horizons})
    H = hs[-1]
    S_list = sorted({int(s) for s in a.steps})
    every = reduce(math.gcd, S_list)
    K = [int(s) for s in a.model_seeds]
    W = int(a.workers) if a.workers else default_workers()
    parts = set(a.parts)
    pid = f"p_{datetime.now():%Y%m%dT%H%M%S}"
    pd = root / "live" / "pilot" / pid
    snap = read_snapshot(a.snapshot)
    times: dict = {}
    t0 = time.perf_counter()
    info = prepare(Path(a.snapshot), snap, pd, brain_folders(root))
    times["convert"] = round(time.perf_counter() - t0, 1)
    start = Path(ad.ROOT / info["record"]["anchor"])
    print(f"예비 측정 {pid}: 스냅숏 {Path(a.snapshot).name}, 시작(지금 두뇌) {info['record']['anchor']}, 시드 {seeds_lh[0]}~{seeds_lh[1]}, "
          f"판정 길이 {hs}, 후보 {len(K)} × {[fmt_steps(s) for s in S_list]} × 도주 비용 {fcs}, 더 견줄 두뇌 {list(extras)}, 워커 {W}", flush=True)
    procs, fproc, fh = [], None, None
    res: dict = {}
    out_rows: dict = dict(pilot=pid, snapshot=Path(a.snapshot).name, seeds=list(seeds_lh), cand_seeds=list(cand_lh), horizons=hs, steps=S_list,
                          model_seeds=K, flight_costs=fcs, extra_models={k: path_text(v) for k, v in extras.items()}, workers=W, times=times,
                          criterion="1차 = 포만 없는 세계 스스로 벗어난 도망의 쫓긴 시간 (LIVE_GATE.md 변경 기록 (3))")
    try:
        t_train = time.perf_counter()
        if "cands" in parts:
            for fc in fcs:
                base = fc == float(LIVE["train_flight_cost"])
                cfg_p = pd / "train.yaml" if base else train_variant(pd, fc)
                tag = "" if base and len(fcs) == 1 else f"_fc{fc:g}"
                for p in launch_training(info, pd, start, pid, K, S_list[-1], every, Path(a.ckpt) if a.ckpt else CKPT, config=cfg_p, tag=tag):
                    procs.append(dict(p, fc=fc, tag=tag))
            record_pids(pd, procs)
        if "fdec" in parts:
            (pd / "logs").mkdir(parents=True, exist_ok=True)
            fh = open(pd / "logs" / "measure_fdec.log", "w", encoding="utf-8")
            fcmd = [sys.executable, str(HERE), "measure-fdec", "--dir", str(pd), "--", "--config", str(pd / "train.yaml"), "--seeds"] + [
                str(s) for s in PILOT["fdec_seeds"]]                       # T 세계 = 스냅숏 먹이 지도 (학습 train-one 과 같은 덮기)
            fproc = subprocess.Popen(fcmd, cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONUTF8="1"), **own_group())
        busy = len(procs) + (1 if fproc is not None else 0)
        seeds = seeds_of(seeds_lh)
        models = {"current": start, "r5": R5S3} | extras
        if "brains" in parts or "scale" in parts:
            items = []
            if "brains" in parts:
                items += [it for tag, m in models.items() for w in ("N", "G") for it in eval_items(info, tag, m, seeds, H, w, "multi", hs)]
            if "scale" in parts:
                items += scale_items(info, start, PILOT["fdec_seeds"], PILOT["scale_steps"])
            t0 = time.perf_counter()
            nw = max(1, min(W - busy, len(items)))
            done = [0]
            with Pool(nw) as pool:
                out = pool.run(items, on_done=lambda: (done.__setitem__(0, done[0] + 1),
                                                       print(f"  두뇌 판 {done[0]}/{len(items)}", flush=True) if done[0] % 50 == 0 else None))
            times["eval_brains"] = round(time.perf_counter() - t0, 1)
            sc = [r for tag, r in out if tag.startswith("scale:")]
            out = [(tag, r) for tag, r in out if not tag.startswith("scale:")]
            if sc:
                out_rows["scale"] = scale_summary(sc, pd / "train.yaml") | dict(model=path_text(start), seeds=list(PILOT["fdec_seeds"]),
                                                                                steps=PILOT["scale_steps"])
            if out:
                res.update(gather(out, models, {}))
                wall = [w["wall_s"] for _, w in out]
                times["world_wall_mean_s"] = round(float(np.mean(wall)), 2)
                times["sec_per_world_step"] = float(np.mean(wall)) / H
                times["eval_brains_workers"] = nw
        if fproc is not None:
            fproc.wait()
            fh.close()
            txt = Path(fh.name).read_text(encoding="utf-8", errors="replace")
            m = re.search(r"f_dec = ([0-9.]+)", txt)
            out_rows["f_dec_T"] = float(m.group(1)) if m else None
            times["measure_fdec_rc"] = fproc.returncode
            fproc = None
        if procs:
            rows = wait_training(procs)
            meta = list(procs)
            procs = []
            times["train_wait"] = round(time.perf_counter() - t_train, 1)                 # 학습 띄움 → 다 끝남 (measure-fdec 기다림 포함)
            times["train_learn"] = round(max([r["learn_s"] or 0.0 for r in rows] + [0.0]), 1)
            rates = [float(r["steps_per_sec"]) for r in rows if r.get("steps_per_sec")]
            times["train_steps_per_sec"] = round(float(np.mean(rates)), 1) if rates else None
            cands = {}
            for r, pm in zip(rows, meta):
                if not r["ok"]:
                    continue
                for S in S_list:
                    z = Path(r["model"]) if S == S_list[-1] else Path(r["model"]).with_name(f"{Path(r['model']).stem}_{S / 1e6:g}m.zip")
                    if z.exists():
                        cands[f"s{r['seed']}{pm['tag']}_{fmt_steps(S)}"] = z
            out_rows["candidate_models"] = {k: path_text(v) for k, v in cands.items()}
            cseeds = seeds_of(cand_lh)
            items = [it for tag, m in cands.items() for w in ("N", "G") for it in eval_items(info, tag, m, cseeds, H, w, "multi", hs)]
            have_cur = "current:N" in res and set(cseeds) <= set(res["current:N"]["meta"]["seeds"])
            if not have_cur:
                items += [it for w in ("N", "G") for it in eval_items(info, "current", start, cseeds, H, w, "multi", hs)]
            t0 = time.perf_counter()
            with Pool(max(1, min(W, len(items)))) as pool:
                out = pool.run(items)
            times["eval_candidates"] = round(time.perf_counter() - t0, 1)
            cres = gather(out, dict(cands, current=start), {})
            cur_c = {w: (subset(res[f"current:{w}"], cseeds) if have_cur else cres[f"current:{w}"]) for w in ("N", "G")}
            out_rows["candidates"] = {tag: {w: {str(h): pilot_pair(cres[f"{tag}:{w}"], cur_c[w], h) for h in hs} for w in ("N", "G")} for tag in cands}
            out_rows["candidates_flight"] = {tag: {w: {str(h): pilot_flight_pair(cres[f"{tag}:{w}"], cur_c[w], h) for h in hs} for w in ("N", "G")}
                                             for tag in cands}
            out_rows["candidate_pooled"] = {tag: {w: re_.pooled(cres[f"{tag}:{w}"]) for w in ("N", "G")} for tag in cands}
            cp = {tag: {w: cres[f"{tag}:{w}"] for w in ("N", "G")} for tag in cands} | {"current": cur_c}
            out_rows["candidate_flight_pooled"] = {tag: {w: {str(h): flight_pooled(at_horizon(r, h)) for h in hs} for w, r in by.items()}
                                                   for tag, by in cp.items()}
        if "current:N" in res:
            others = [t for t in models if t != "current" and f"{t}:N" in res]
            out_rows["vs_current"] = {t: {w: {str(h): dict(caught=pilot_pair(res[f"{t}:{w}"], res[f"current:{w}"], h),
                                                            flight=pilot_flight_pair(res[f"{t}:{w}"], res[f"current:{w}"], h)) for h in hs}
                                          for w in ("N", "G")} for t in others}
            out_rows["caught_current"] = {w: {str(h): re_.pooled(at_horizon(res[f"current:{w}"], h))["caught"] for h in hs} for w in ("N", "G")}
            out_rows["pooled"] = {tag: re_.pooled(r) for tag, r in res.items() if not tag.endswith(":stuck")}
            out_rows["flight_pooled"] = {t: {w: {str(h): flight_pooled(at_horizon(res[f"{t}:{w}"], h)) for h in hs} for w in ("N", "G")}
                                         for t in models if f"{t}:N" in res}
        out_rows["estimates"] = round_estimates(times, out_rows, W)
    finally:
        stop_procs(procs)
        if fproc is not None:
            kill_tree(fproc)
        if fh is not None and not fh.closed:
            fh.close()
    atomic_write_json(pd / "pilot.json", out_rows)
    text = fmt_pilot(out_rows)
    (pd / "pilot.md").write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    print(f"-> {pd / 'pilot.json'}, {pd / 'pilot.md'}")
    return 0


def round_estimates(times: dict, rows: dict, W: int, regions: int = 3) -> list[dict]:
    """판 하나 벽시계 어림 (K = 1): 변환 + max(학습, 지금 두뇌 판정 N·G + 끼임) + 후보 판정 N·G + 끼임 + 내보내기. 세계-스텝 시간·학습 속도는 이번 측정 값."""
    sps, rate = times.get("sec_per_world_step"), times.get("train_steps_per_sec")
    if not sps or not rate:
        return []
    out = []
    stuck_n = LIVE["stuck_seeds"][1] - LIVE["stuck_seeds"][0] + 1
    for n in (20, 30, 40, 60, 100):
        for H in rows.get("horizons", []):
            for S in rows.get("steps", []):
                ev = (2 * n + stuck_n) * regions * H * sps
                cur = ev / max(1, W - 1)
                cand = ev / W
                tr = S / rate + 10.0                                  # 학습 프로세스 시작(가져오기·세계 만들기) 약 10 초
                tot = times.get("convert", 10.0) + max(cur, tr) + cand + 15.0 + 3 * 8.0
                out.append(dict(n=n, horizon=H, steps=S, eval_current_s=round(cur), train_s=round(tr), eval_candidate_s=round(cand),
                                total_min=round(tot / 60, 1), t_crit=round(t_crit(n - 1), 3)))
    return out


def fmt_pilot(r: dict) -> str:
    def need(p):
        return " · ".join("—" if v is None else str(v) for v in p["n_needed"].values())

    def causes(f):
        own, oth, uns = flight_groups(f)
        return (f"{f['starts_per_1k']:.2f} | {f['own_contact_s']:.2f} | {cause_parts(f, own)} | {cause_parts(f, oth)} | {cause_parts(f, uns)} | "
                f"{pct(f['shelter_end_share'])} | {pct(f['flee_share'])} | {pct(f['self_flee_share'])}")

    def guards(f):
        return " · ".join(f"{tfmt(f[k]['diff'], nd)} ({tfmt(f[k]['t'])})" for k, nd in (("starts", 2), ("flee", 4), ("unsafe", 4)))

    head_c = ("| 두뇌 | 세계 | 길이 | 시작 /1000 산 사슴-스텝 | 쫓긴 시간 초 (스스로 벗어남, 전체 합) | 스스로 벗어남 (은신처·원판·시야각·반경) | "
              "그 밖 살아 끝남 (바꿈·그만둠·끝까지·안 쫓김) | 잡힘·굶음·잘림 | 은신처에서 끝 | 실행 FLEE 몫 (반사 포함) | 스스로 고른 FLEE 몫 |",
              "|---|---|---|---|---|---|---|---|---|---|---|")
    L = [f"# 실시간 고리 예비 측정 {r['pilot']} (보고만 — 관문 크기를 고르는 자료, 시드 {r['seeds'][0]}~{r['seeds'][1]})", "",
         f"- 기준: {r.get('criterion', '')}. 끝 까닭 몫은 시작한 도망 가운데, 끝 까닭 표는 전체 합(정의 env_v2/world.py '야생 1단계' (w3) 도망 기록)",
         f"- 스냅숏 {r['snapshot']}, 워커 {r['workers']}, 더 견줄 두뇌 {r.get('extra_models') or {}}, 도주 비용 후보 {r.get('flight_costs')}",
         f"- 시간 {json.dumps(r['times'], ensure_ascii=False)}",
         f"- T 세계(늑대 포만 끔, 스냅숏 먹이 지도) f_dec = {r.get('f_dec_T')} (R5 조리법 값 0.858922)", ""]
    if r.get("vs_current"):
        L += ["## 두뇌 − 지금 두뇌 (시드마다 짝 차이 — 1차 P1·지킴 GF·GV·GC 와 같은 셈)", "",
              "| 두뇌 | 세계 | 길이(스텝) | 쫓긴 시간 지금 초 | 두뇌 초 | 차이 | sd | t | 시드 (빠짐) | 0.25·0.5·1 초 가를 시드 수 | "
              "GF 시작/1000 · GV FLEE 몫 · GC 잡힘·잘림 몫 차이 (t) | 잡힘 차이 (t) | 잡힘 0.5·1·2%p 가를 시드 수 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for t, by in r["vs_current"].items():
            for w, hh in by.items():
                for h, x in hh.items():
                    f, c = x["flight"], x["caught"]
                    L.append(f"| {t} | {w} | {h} | {f['b']:.2f} | {f['a']:.2f} | {tfmt(f['diff'])} | {f['sd']:.2f} | {tfmt(f['t'])} | {f['n']} "
                             f"({len(f['dropped'])}) | {need(f)} | {guards(f)} | {tfmt(c['diff'] * 100)} %p ({tfmt(c['t'])}) | {need(c)} |")
        L.append("")
    if r.get("flight_pooled"):
        L += ["## 도망 끝 까닭 (두뇌마다, 두뇌 견줌 시드)", "", *head_c]
        for t, by in r["flight_pooled"].items():
            for w, hh in by.items():
                for h, f in hh.items():
                    L.append(f"| {t} | {w} | {h} | {causes(f)} |")
        L.append("")
    if r.get("candidates"):
        L += ["## 후보 − 지금 두뇌 (후보 시드)", "",
              "| 후보 | 세계 | 길이 | 쫓긴 시간 차이 초 | sd | t | 시드 (빠짐) | GF · GV · GC 차이 (t) | 잡힘 차이 | sd | t |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for tag, by in r["candidates"].items():
            for w, hh in by.items():
                for h, p in hh.items():
                    f = r["candidates_flight"][tag][w][h]
                    L.append(f"| {tag} | {w} | {h} | {tfmt(f['diff'])} | {f['sd']:.2f} | {tfmt(f['t'])} | {f['n']} ({len(f['dropped'])}) | "
                             f"{guards(f)} | {tfmt(p['diff'] * 100)} %p | {p['sd'] * 100:.2f} | {tfmt(p['t'])} |")
        L += ["", "### 후보 도망 끝 까닭 (후보 시드)", "", *head_c]
        for tag, by in r.get("candidate_flight_pooled", {}).items():
            for w, hh in by.items():
                for h, f in hh.items():
                    L.append(f"| {tag} | {w} | {h} | {causes(f)} |")
        L.append("")
    if r.get("scale"):
        s = r["scale"]
        m = s["metabolic"]
        L += ["## 도주 비용 기준 크기 (T 세계, 지금 두뇌 — flight_cost 를 고르는 자료)", "",
              f"- 세계 {s['worlds']}개 × {s['steps']} 스텝 (학습 시드 {s['seeds']}), 사슴-스텝 {s['deer_steps']}: 평균 보상 {s['reward_per_step']:+.5f}/스텝 "
              f"(살아 있음 {s['rew_alive']:+.3f} 포함, 죽음 {s['deaths_per_1k']:.2f}·번식 {s['repro_per_1k']:.2f} /1000 사슴-스텝), 실행 FLEE 몫 {pct(s['flee_share'])}"
              f" (그 가운데 반사 {pct(s.get('reflex_share', NAN))})",
              f"- 에너지 칸(보상 − 살아 있음, 죽음·번식 스텝 뺌): FLEE 스텝 {s['energy_flee']:+.5f}, 그 밖 {s['energy_other']:+.5f}, 차이 {s['energy_gap']:+.5f}",
              f"- 설정 대사 비용(rew_energy × energy_drain × 대사 배수): 정지 {m['stop']:.5f}, 걷기 {m['walk']:.5f}, 뛰기(도주) {m['run']:.5f} /스텝 — "
              f"뛰기가 정지보다 {s['run_extra_over_stop']:.5f} 더", ""]
    if r.get("estimates"):
        L += ["## 판 하나 벽시계 어림 (K = 1)", "", "| 시드 n | 길이 H | 학습 S | 지금 판정 초 | 학습 초 | 후보 판정 초 | 합 분 | 문턱 |", "|---|---|---|---|---|---|---|---|"]
        for e in r["estimates"]:
            L.append(f"| {e['n']} | {e['horizon']} | {fmt_steps(e['steps'])} | {e['eval_current_s']} | {e['train_s']} | {e['eval_candidate_s']} | "
                     f"{e['total_min']} | {e['t_crit']} |")
    return "\n".join(L)


# --------------------------------------------------------------------- #
# 학습 프로세스 하나 (round·pilot 이 띄운다)
# --------------------------------------------------------------------- #


def cmd_train_one(a) -> int:
    """train_v3.main 을 그대로 부르고, 학습 세계를 만들 때마다 그 지역 스냅숏 먹이 지도를 덮는다(adapt.snapshot_food_vec_env). --progress 면
    롤아웃마다(약 3만 스텝) 진행 파일을 쓴다 (상태 줄 '학습 중 0.6M/1M')."""
    import train_v3

    rd = Path(a.dir)
    regions = json.loads((rd / "regions.json").read_text(encoding="utf-8"))
    food = {n: r["cap"] for n, r in regions.items()}
    train_v3.MultiWorldVecEnv = ad.snapshot_food_vec_env(train_v3.MultiWorldVecEnv, food)
    print(f"학습 먹이 지도: 스냅숏 ({', '.join(food)})", flush=True)
    if a.progress:
        prog = Path(a.progress)
        base = train_v3.RepLogCallback

        class ProgressCallback(base):
            def _on_training_start(self) -> None:
                super()._on_training_start()
                self._prog()

            def _on_rollout_end(self) -> None:
                super()._on_rollout_end()
                self._prog()

            def _prog(self) -> None:
                try:
                    atomic_write_json(prog, dict(steps=int(self.num_timesteps), unix=time.time()))
                except OSError:
                    pass

        train_v3.RepLogCallback = ProgressCallback
    return int(train_v3.main(a.rest) or 0)


def snapshot_food_world(Base, food: dict):
    """World + 스냅숏 먹이 지도: 세계를 만들 때 그 지역(features.wild_weather.region) 스냅숏 용량 격자를 덮는다 — 학습 train-one 의
    adapt.snapshot_food_vec_env 와 같은 덮기(adapt.apply_snapshot_food). measure-fdec 가 T 세계(스냅숏 먹이 지도)에서 재게 하려고
    env_v2.world.World 자리에 넣는다 (그 프로세스 안에서만)."""

    class SnapshotFoodWorld(Base):
        def __init__(self, cfg, *args, **kw):
            super().__init__(cfg, *args, **kw)
            region = str(((cfg.v2.get("features") or {}).get("wild_weather") or {}).get("region", ""))
            if region not in food:
                raise SystemExit(f"measure-fdec: 지역 {region!r} 의 스냅숏 먹이 지도가 없다 ({', '.join(food)}) — T 세계는 지역 섞기 세계다")
            ad.apply_snapshot_food(self, food[region])

    return SnapshotFoodWorld


def cmd_measure_fdec(a) -> int:
    """train_v3.py measure-fdec 를 T 세계 그대로 — 학습(train-one)처럼 세계마다 그 지역 스냅숏 먹이 지도를 덮는다. 예비 측정이 띄운다.
    train_v3.measure_fdec 는 World 를 함수 안에서 env_v2.world 에서 가져오므로 그 자리만 바꾼다(정책 공간용 MultiWorldVecEnv 는 그대로)."""
    import env_v2.world as ew
    import train_v3

    regions = json.loads((Path(a.dir) / "regions.json").read_text(encoding="utf-8"))
    food = {n: r["cap"] for n, r in regions.items()}
    ew.World = snapshot_food_world(ew.World, food)
    print(f"measure-fdec 먹이 지도: 스냅숏 ({', '.join(food)})", flush=True)
    return int(train_v3.main(["measure-fdec"] + list(a.rest)) or 0)


# --------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------- #


def _size_args(s) -> None:
    s.add_argument("--root", default=str(DEFAULT_ROOT), help="주고받는 폴더 (기본 AdaptiveEcosystem/Saved/EcoAdapt)")
    s.add_argument("--workers", type=int, default=None, help="워커 수 (기본 max(2, CPU − 6))")
    s.add_argument("--ckpt", default=None, help=f"후보 모델 폴더 (기본 {CKPT})")
    g = s.add_argument_group("시험 크기 (관문 상수와 다르면 시험 — --root 가 실제 폴더가 아닐 때만)")
    g.add_argument("--steps", type=int, default=None, help=f"모델마다 학습 스텝 S (관문 {LIVE['train_steps']})")
    g.add_argument("--model-seeds", type=int, nargs="+", default=None, help=f"모델 시드 (관문 {list(LIVE['model_seeds'])})")
    g.add_argument("--flight-cost", type=float, default=None,
                   help=f"T 세계 도주 비용 wild_flight.flight_cost (관문 {LIVE['train_flight_cost']} — FLEE 를 실행한 스텝마다 보상에서 뺀다)")
    g.add_argument("--horizon", type=int, default=None, help=f"판정 길이 H 스텝 (관문 {LIVE['horizon']})")
    g.add_argument("--judge-seeds", default=None, help="N 판정 시드 처음-끝 (관문 {0}-{1})".format(*LIVE["judge_seeds"]))
    g.add_argument("--horizon-g", type=int, default=None, help=f"G 판정 길이 스텝 (관문 {LIVE['horizon_g']})")
    g.add_argument("--judge-seeds-g", default=None, help="G 판정 시드 처음-끝 (관문 {0}-{1})".format(*LIVE["judge_seeds_g"]))
    g.add_argument("--select-seeds", default=None)
    g.add_argument("--stuck-seeds", default=None)
    g.add_argument("--check-seeds", default=None)
    g.add_argument("--skip-check", action="store_true", help="시험: 재현 확인 R 건너뜀")
    g.add_argument("--force-export", action="store_true", help="시험: 관문과 상관없이 내보내기 경로를 시험한다 (실제 폴더에서는 받지 않는다)")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("train-one", "measure-fdec"):
        ap1 = argparse.ArgumentParser()
        ap1.add_argument("cmd")
        ap1.add_argument("--dir", required=True)
        ap1.add_argument("--progress", default=None)
        cut = argv.index("--")
        a1 = ap1.parse_args(argv[:cut])
        a1.rest = argv[cut + 1:]
        return cmd_train_one(a1) if a1.cmd == "train-one" else cmd_measure_fdec(a1)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("watch", help="스냅숏 폴더 감시 (판을 자식 프로세스로 돌린다)")
    _size_args(s)
    s.add_argument("--existing", action="store_true", help="감시를 켜기 전에 있던 가장 새 스냅숏도 본다 (기본: 켠 뒤에 생긴 것만 — 지난 Play 의 스냅숏으로 배우지 않게)")
    s = sub.add_parser("round", help="한 판 (앞에서)")
    s.add_argument("--snapshot", type=Path, required=True)
    _size_args(s)
    s.add_argument("--attempt", type=int, default=None, help=argparse.SUPPRESS)
    s.add_argument("--run-id", default=None, help=argparse.SUPPRESS)
    s.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    s = sub.add_parser("pilot", help="예비 측정 (시드 34900~34999 만)")
    s.add_argument("--snapshot", type=Path, required=True)
    s.add_argument("--root", default=str(DEFAULT_ROOT))
    s.add_argument("--workers", type=int, default=None)
    s.add_argument("--ckpt", default=None)
    s.add_argument("--seeds", default="{0}-{1}".format(*PILOT["seeds"]), help="두뇌 견줌 시드 (34900~34999 안)")
    s.add_argument("--cand-seeds", default="{0}-{1}".format(*PILOT["cand_seeds"]), help="후보 견줌 시드 (34900~34999 안)")
    s.add_argument("--horizons", type=int, nargs="+", default=list(PILOT["horizons"]), help="판정 길이들 (스텝 — 1800 = 240 초, 3600 = 480 초)")
    s.add_argument("--steps", type=int, nargs="+", default=list(PILOT["steps"]), help="후보 학습 스텝들")
    s.add_argument("--model-seeds", type=int, nargs="+", default=list(PILOT["model_seeds"]))
    s.add_argument("--extra-models", nargs="+", default=None, metavar="이름=ZIP", help="지금 두뇌·R5 s3 와 함께 견줄 관측 21 두뇌 (herbivore_rl/ 기준 경로)")
    s.add_argument("--flight-cost", type=float, nargs="+", default=None,
                   help=f"후보 학습의 T 세계 도주 비용 값들 (기본 [{LIVE['train_flight_cost']}] — 값마다 모델 시드 × 학습)")
    s.add_argument("--parts", nargs="+", default=["brains", "fdec", "cands", "scale"], choices=["brains", "fdec", "cands", "scale"])
    a = ap.parse_args(argv)
    return {"watch": cmd_watch, "round": cmd_round, "pilot": cmd_pilot}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
