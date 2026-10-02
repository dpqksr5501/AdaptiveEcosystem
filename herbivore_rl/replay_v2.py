"""V2 리플레이 영상 (계획서 6.4 표시 규칙, 0단계 0-4).

    python replay_v2.py --model ckpt/final.zip --seed 10000 --steps 1800 --stride 2 \
        --out results/v2/replay_v1_baseline.mp4
    python replay_v2.py --compare learned:ckpt/final.zip perm:learned:ckpt/final.zip \
        fixed:0.421,0.866,0.105,0.004 --labels "C0 학습" "C1′ 행동 순열" "C2 최적 상수" \
        --steps 600 --out results/v2/replay_v1_compare.mp4
    # S7 땅 회복 타임랩스 (부재 시험 (ii)). α 0.03 은 Gate F R1(보정 1회차)의 선택값이다. Gate F 는 이 값에서도
    # (c) 로 실패했다(results/v2/gate_f/report.md). α 를 yaml 에 정하면 --alpha 를 뺀다.
    python replay_v2.py --config configs/v2_0b.yaml --policy fixed:0.421,0.866,0.105,0.004 \
        --labels "C2 최적 상수 · 왼쪽 과방목 교란 (V 0.3·cap0)" --half-life 693 --alpha 0.03 \
        --overgraze-left 0.3 --steps 4200 --stride 4 --png 693 --png-dpi 150 \
        --caption "환경 장면 · 상수 정책(C2)에서도 같다 — 땅의 회복은 정책이 만든 것이 아니다" \
        --out results/v2/replay_s7_food_v.mp4
    # 같은 장면의 제안값 α 0.5 (Gate F R0, 실패 기록). --alpha 가 없어 yaml α(지금 0.5)를 쓴다. yaml α 를 바꾸면
    # --alpha 0.5 를 더한다(같은 세계, 같은 그림). 커밋하는 것은 .png 다(results/v2/*.mp4 는 .gitignore).
    python replay_v2.py --config configs/v2_0b.yaml --policy fixed:0.421,0.866,0.105,0.004 \
        --labels "C2 최적 상수 · 왼쪽 과방목 교란 (V 0.3·cap0) · α 0.5 제안값" --half-life 693 \
        --overgraze-left 0.3 --steps 4200 --stride 4 --png 693 --png-dpi 150 \
        --caption "제안값 α 0.5 (yaml) — Gate F 사전 등록 실패: 땅이 하한 근처로 붕괴해 교란과 대조가 같아진다" \
        --out results/v2/replay_s7_food_v_a0.5.mp4
    # 1-3 v2.1 학습 정책(C0, v2_1_s0) 대 행동 순열(C1′), S1·S0 장면 (results/v2/stage1_v2_1.md). 정지 화면 스텝 884 는
    # 이 시드·1800스텝에서 C0 의 뛰기 개체가 가장 많은 프레임이다(그림용, 판정 아님). 커밋하는 것은 .png 다.
    python replay_v2.py --config configs/v2_1.yaml --compare learned:ckpt/v2/v2_1_s0.zip \
        perm:learned:ckpt/v2/v2_1_s0.zip --labels "C0 학습 정책 (v2_1_s0)" \
        "C1′ 행동 순열 (보행 빈도 같음, 상태와의 짝만 끊김)" --seed 10000 --steps 1800 --stride 2 \
        --png 884 --png-dpi 150 \
        --caption "1-3 v2.1 · 평가 시드 10000 · 같은 세계·카메라. 점 색: 정지 회색, 걷기 초록, 뛰기 주황" \
        --out results/v2/replay_v2_1_compare.mp4

`env_v2.world.World` 를 돌린다. 기능 스위치를 모두 끄면 v1 과 같은 세계다.
v1 `replay.py` 를 참고했지만 그 파일은 건드리지 않는다.
정책은 `env_v2.rollout.build_policy(spec, seed)` 로 만든다. 래퍼 스펙(C1′ 등)도 그대로 쓴다.
래퍼의 시드는 세계 시드다. 그래서 C1′ 순열이 `diagnose_v2.py` 의 같은 시드 롤아웃과 같다.

표시 (6.4):
- 배경 = 먹이 지도, 어두운 원 = 은신처, 빨간 X = 근접 포식자, 연한 x = 원거리 포식자.
- 시야 부채꼴은 일부만 그린다. 초식 `--fov-herbs` 마리(반경 see_r, 각 fov_deg, 경계 중이면 360° 원),
  포식자 `--fov-preds` 마리(반경 pred_view_r, 각 pred_fov_deg). 대담함 훅이 있으면 초식은
  궤적을 그리는 두 개체를 먼저 고른다.
- 초식 점 색 = 보행 상태. 정지 회색, 걷기 초록, 뛰기 주황.
  v1·v2.0 은 항상 최고 속력이라 전부 주황이 정상이다. v2.1(speed)은 World.gait(실제 적용 보행)를 그대로 칠하고,
  설명줄에 speed 계수(문턱·속력·섭식·대사 배수·에너지 보상 방식)를 한 줄 더 적는다.
  행동 5개 세계: `fixed:a,b,c,d,s` (s = speed), `random:<seed>` 는 행동 수를 설정에서 맞춘다. Utility(4개)는 못 쓴다.
      python replay_v2.py --config configs/v2_1.yaml --compare fixed:0.4,0.8,0.4,0.1,0.2 \
          fixed:0.4,0.8,0.4,0.1,0.5 fixed:0.4,0.8,0.4,0.1,0.9 --labels "항상 정지" "항상 걷기" "항상 뛰기" \
          --steps 600 --out results/v2/replay_v2_1_gaits.mp4
- 경계 (v2.2, vigilance): `World.vigilant` 인 개체는 흰 테두리와 짧은 시선선(`World.gaze` = 위협 쪽 heading)으로,
  시야 부채꼴은 360° 원으로 그린다. 점 색은 실제 보행(경계는 속력 0 이라 정지 회색)이다. 하단 흰 선은 경계 비율,
  설명줄에 vigilance 계수(문턱·threat_recency 감쇠·섭식·시야각) 한 줄을 더 적는다. 행동 6개: `fixed:a,b,c,d,s,v`.
      python replay_v2.py --config configs/v2_2.yaml --compare learned:ckpt/v2/v2_2_s0.zip \
          perm:learned:ckpt/v2/v2_2_s0.zip --labels "C0" "C1′" --steps 1800 --out results/v2/replay_v2_2_compare.mp4
- 모든 초식에 짧은 heading 화살표. 리스폰 직후 몇 프레임은 흐리게 그린다(순간이동 착시 방지).
- 하단 시계열: 보행 비율(정지/걷기/뛰기), 경계 비율, 지역 기억, 포획 누적. 게임 시각 mm:ss.
- `--compare` 는 같은 시드·같은 카메라로 정책 여러 개를 나란히 그린다. 칸들은 x축과
  포획 누적 축을 함께 쓴다(눈으로 비교할 때 높이가 같으면 수도 같다).
- 먹이 상태 (v2.0b, `food_v` 훅): F 는 위 먹이 색 그대로. V/cap0 가 낮은 셀에 채도를 낮춘 회갈색 막
  ("짓밟힌 땅", `trample_weight`)을 덮는다. 맵 좌우 절반(v2.3 전 지역 대용) 경계는 점선, 절반마다
  V·F 라벨. 하단에 시계열 칸을 하나 더 붙여 절반별 V/cap0(실선)·F/cap0(점선)을 그린다
  (지역 비율 ΣV/Σcap0, `World.food_stats`). food_v 를 끈 설정은 이 표시가 하나도 없고 그림이 v2.0 과 같다.
- 부재 시험 (ii) 과방목 교란 (6.4, S7): `--overgraze-left 0.3` 은 reset 직후 왼쪽 절반 V 를 0.3·cap0 로
  바꾼다(`overgraze_left`, 난수를 뽑지 않는다). 같은 시드·같은 정책의 교란 없는 대조도 돌려 왼쪽 V/cap0 를
  하단에 가는 점선으로 겹치고, t0·t0+h·t0+3h 의 값을 출력한다(h = 이 세계의 회복 반감기).
  `--half-life`·`--alpha` 는 장면용으로 yaml 계수 하나를 바꾼다. 바꾼 값은 화면 아래 설명줄에 남는다.

뒤 버전용 훅. World 에 아래 속성이 있으면 그린다. 없으면 건너뛴다.

| 속성 | 모양 | 버전 | 읽는 때 | 표시 |
|---|---|---|---|---|
| `food_v` | (gw,gw) | v2.0b | 스텝 전 | 짓밟힌 땅 막, 좌우 절반 라벨, 하단 V/cap0·F/cap0 (`food_stats()` 를 함께 읽는다) |
| `gait` | (N,) int | v2.1 (구현) | 스텝 뒤 | 이번 스텝에 실제로 적용된 보행 (0 정지, 1 걷기, 2 뛰기). 가장 우선 |
| `vel` | (N,2) | v2.1 (구현) | 스텝 뒤 | 이번 스텝 속도. `gait` 가 없을 때 |v|/herb_speed 로 판정 |
| `vigilant` | (N,) bool | v2.2 (구현) | 스텝 뒤 | 흰 테두리, 짧은 시선선, 360° 시야 원, 경계 비율 |
| `gaze` | (N,2) | v2.2 (구현) | 스텝 뒤 | 시선 방향(스텝 뒤 heading, 경계 개체는 ThreatDir 쪽). 없으면 heading |
| `region_id`, `region_mem` | (gw,gw) int, (R,) | v2.3 | 스텝 전 | 지역 배경 반투명 빨강, m_A·m_B 시계열 |
| `boldness` | (N,) | v2.4 | 스텝 전 | 대담함 최대·최소 개체 2마리 궤적 |

`gait`·`vel` 이 모두 없으면(v1·v2.0) 같은 관측으로 조향식을 다시 계산해 속력을 얻는다.
"스텝 뒤" 값은 이번 스텝 행동이 적용된 상태다. 보행·경계·시선을 같은 스텝에서 읽어 서로
어긋나지 않게 한다. 위치·heading·먹이·포획 수는 스텝 전 상태다. World 는 리스폰 때 스텝 뒤 훅을
바꾸지 않는다고 가정한다. 바꾸면 죽은 슬롯의 마지막 프레임에 새 개체 값이 보인다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch 보다 먼저 (learned 정책)

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.animation as animation  # noqa: E402
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgba  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, Patch, Rectangle, Wedge  # noqa: E402
from matplotlib.ticker import FuncFormatter, MultipleLocator  # noqa: E402

from env_v2.config import load_v2_config  # noqa: E402
from env_v2.features import features_of  # noqa: E402
from env_v2.rollout import adapt_spec, build_policy  # noqa: E402
from env_v2.steering import steer  # noqa: E402
from env_v2.world import ACT_DIM, World  # noqa: E402

ROOT = Path(__file__).resolve().parent

# --------------------------------------------------------------------- #
# 표시 상수
# --------------------------------------------------------------------- #

GAIT_STOP, GAIT_WALK, GAIT_RUN = 0, 1, 2
GAIT_NAMES = ("정지", "걷기", "뛰기")
GAIT_COLORS = ("#9a9a9a", "#4cd964", "#ff9500")
GAIT_RGBA = np.array([to_rgba(c) for c in GAIT_COLORS])
STOP_EPS = 1e-6          # 이 비율 이하는 정지로 본다 (부동소수 잔차)
WALK_MAX = 0.6           # |v|/herb_speed 가 이 값 이하면 걷기, 넘으면 뛰기

BG = "#111111"
FG = "#dddddd"
BOLD_COLOR = "#ffd34d"
TIMID_COLOR = "#6fd3ff"
MEM_RGB = (1.0, 0.25, 0.25)
MEM_LINE_COLORS = ("#ff6b6b", "#c58bff", "#6fd3ff", "#ffd34d")
VIG_LINE_COLOR = "white"
HERB_FOV_FACE = (1.0, 1.0, 1.0, 0.06)
HERB_FOV_EDGE = (1.0, 1.0, 1.0, 0.40)
PRED_FOV_FACE = (1.0, 0.2, 0.2, 0.09)
PRED_FOV_EDGE = (1.0, 0.35, 0.35, 0.45)

ARROW_LEN = 2.2          # heading 화살표 길이 (격자 단위)
GAZE_LEN = 4.0           # 경계 시선선 길이
DIM_ALPHA = 0.22         # 리스폰 직후 투명도 (여기서 1 로 회복)

# 먹이: 맨땅(갈색) → 무성함(초록). v1 replay.py 와 같은 색.
FOOD_CMAP = LinearSegmentedColormap.from_list(
    "food", ["#2a2118", "#4a3b23", "#5d7a35", "#8fc44a"]
)

# 짓밟힌 땅 (v2.0b, 6.4): V/cap0 가 낮은 셀에 덮는 회갈색 막. 갓 뜯겨 F 만 낮은 셀(진갈색, 곧 다시 자란다)과
# 용량 V 자체가 깎인 셀(회갈색, 반감기 h 로 천천히 돌아온다)을 구분하려고 맨땅 색보다 밝고 채도가 낮다.
TRAMPLE_RGB = to_rgba("#a39a8c")[:3]
TRAMPLE_ALPHA = 0.85         # V/cap0 ≤ TRAMPLE_FULL 일 때 막의 불투명도
TRAMPLE_FULL = 0.3           # 이 비율 이하는 막을 다 덮는다 (과방목 교란 0.3·cap0, init_frac 아래 끝)
TRAMPLE_NONE = 0.9           # 이 비율 이상은 막이 없다 (Gate F (a) 창의 위 끝). 사이는 선형
TRAMPLE_CAP = 0.2            # cap0 가 이보다 작은 패치 가장자리는 cap0/TRAMPLE_CAP 배로 옅게. cap0 = 0 셀은 막 없음
HALF_COLORS = ("#f0a35e", "#6fb8ff")      # 맵 왼쪽·오른쪽 절반 (라벨, 하단 V/cap0·F/cap0)
HALF_NAMES = ("왼쪽", "오른쪽")
CONTROL_COLOR = "#bbbbbb"    # 부재 시험 대조(교란 없는 같은 시드)의 왼쪽 V/cap0


def _use_korean_font() -> None:
    """라벨에 한글이 있다. 있는 한글 폰트를 찾아 쓴다."""
    have = {f.name for f in fm.fontManager.ttflist}
    for name in ("Malgun Gothic", "NanumGothic", "Gulim", "Batang", "MS Gothic"):
        if name in have:
            matplotlib.rcParams["font.family"] = name
            matplotlib.rcParams["axes.unicode_minus"] = False
            return


_use_korean_font()


# --------------------------------------------------------------------- #
# 판정 · 시간
# --------------------------------------------------------------------- #


def gait_state(speed: np.ndarray, herb_speed: float) -> np.ndarray:
    """속력 → 보행 상태 (0 정지, 1 걷기, 2 뛰기). 비율 = |v|/herb_speed."""
    ratio = np.asarray(speed, dtype=np.float64) / float(herb_speed)
    g = np.full(ratio.shape, GAIT_RUN, dtype=np.int8)
    g[ratio <= WALK_MAX] = GAIT_WALK
    g[ratio <= STOP_EPS] = GAIT_STOP
    return g


def gait_fractions(gait: np.ndarray) -> np.ndarray:
    """보행 상태 배열 → [정지, 걷기, 뛰기] 비율."""
    return np.bincount(np.asarray(gait, dtype=np.int64), minlength=3)[:3] / max(len(gait), 1)


def applied_gait(world, v_pre: np.ndarray | None) -> np.ndarray:
    """스텝 뒤에 부른다. 이번 스텝에 적용된 보행. 우선순위: `gait` 훅 → `vel` 훅 → `v_pre`.

    `v_pre` 는 스텝 전에 같은 관측으로 다시 계산한 조향 속도다(v1·v2.0 에서는 이것이 곧 속도다).
    """
    g = getattr(world, "gait", None)
    if g is not None:
        return np.array(g, dtype=np.int8, copy=True)
    v = getattr(world, "vel", None)
    if v is None:
        v = v_pre
    if v is None:
        raise ValueError("보행을 정할 수 없다: gait·vel 훅이 없고 조향식도 계산하지 않았다")
    return gait_state(np.linalg.norm(np.asarray(v, dtype=np.float64), axis=1), world.cfg.herb_speed)


def region_name(r: int) -> str:
    """지역 번호 → 표시 이름 (0 → m_A, 1 → m_B, ...)."""
    return f"m_{chr(ord('A') + r)}" if r < 26 else f"m_{r}"


def fov_slots(n: int, k: int, bold: np.ndarray | None = None) -> list:
    """시야 부채꼴을 그릴 초식 슬롯 k 개.

    대담함 훅이 있으면 궤적을 그리는 두 개체(최대, 최소)를 먼저 넣고, 남는 자리는 앞 슬롯으로 채운다.
    """
    k = max(0, min(int(k), n))
    picks = []
    if bold is not None and k > 0:
        b = np.asarray(bold)
        picks = list(dict.fromkeys([int(b.argmax()), int(b.argmin())]))[:k]
    for s in range(n):
        if len(picks) >= k:
            break
        if s not in picks:
            picks.append(s)
    return picks


def step_seconds(cfg) -> float:
    """1 스텝의 게임 시간(초). 정책 주기 8프레임 / 60fps = 0.1333초 (§9.7)."""
    return float(cfg.policy_interval) / 60.0


def fmt_clock(seconds: float) -> str:
    """게임 시각 mm:ss. 1시간을 넘으면 분이 60을 넘어간다."""
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def clock_tick(seconds: float, max_ticks: int = 8) -> int:
    """시계열 x축 눈금 간격(초). 5초~1시간 중 눈금이 max_ticks 이하가 되는 가장 작은 값."""
    for step in (5, 10, 15, 30, 60, 120, 300, 600, 1200, 1800):
        if seconds / step <= max_ticks:
            return step
    return 3600


class RespawnTracker:
    """슬롯마다 마지막 리스폰 뒤 지난 스텝 수와 생애 번호를 센다.

    시작 개체는 리스폰이 아니므로 흐리게 그리지 않는다. `update(done)` 은 world.step 이
    돌려준 done 을 받는다. done 슬롯은 같은 스텝 끝에 이미 새 위치로 리스폰돼 있다.
    """

    def __init__(self, n: int, fade_steps: int):
        self.fade_steps = max(int(fade_steps), 0)
        self.age = np.full(n, np.iinfo(np.int32).max // 2, dtype=np.int64)
        self.life = np.zeros(n, dtype=np.int64)

    def update(self, done: np.ndarray) -> None:
        self.age += 1
        done = np.asarray(done, dtype=bool)
        self.age[done] = 0
        self.life[done] += 1

    def alpha(self) -> np.ndarray:
        """리스폰 직후 DIM_ALPHA 에서 fade_steps 동안 1 로 선형 회복한다."""
        if self.fade_steps == 0:
            return np.ones(len(self.age))
        k = np.clip(self.age / self.fade_steps, 0.0, 1.0)
        return DIM_ALPHA + (1.0 - DIM_ALPHA) * k


# --------------------------------------------------------------------- #
# 먹이 상태 (v2.0b)
# --------------------------------------------------------------------- #


def trample_weight(food_v: np.ndarray, food_cap: np.ndarray) -> np.ndarray:
    """짓밟힘 정도 [0,1]. V/cap0 ≤ TRAMPLE_FULL 이면 1, ≥ TRAMPLE_NONE 이면 0, 사이는 선형이다.

    cap0 < TRAMPLE_CAP 인 패치 가장자리는 cap0/TRAMPLE_CAP 배로 줄인다(원래 거의 맨땅이라 회갈색 테두리가
    패치를 감싸 보이지 않게). cap0 = 0 셀은 0 이다(0 나눗셈 없음).
    """
    cap = np.asarray(food_cap, dtype=np.float64)
    ratio = np.divide(np.asarray(food_v, dtype=np.float64), cap, out=np.ones_like(cap), where=cap > 0.0)
    w = np.clip((TRAMPLE_NONE - ratio) / (TRAMPLE_NONE - TRAMPLE_FULL), 0.0, 1.0)
    return w * np.clip(cap / TRAMPLE_CAP, 0.0, 1.0)


def trample_rgba(food_v: np.ndarray, food_cap: np.ndarray) -> np.ndarray:
    """짓밟힌 땅 막 (gw,gw,4). 색은 TRAMPLE_RGB 하나, 불투명도 = TRAMPLE_ALPHA × `trample_weight`."""
    w = trample_weight(food_v, food_cap)
    rgba = np.empty(w.shape + (4,))
    rgba[..., :3] = TRAMPLE_RGB
    rgba[..., 3] = TRAMPLE_ALPHA * w
    return rgba


def food_v_config(cfg, half_life: float | None = None, alpha: float | None = None):
    """food_v 계수 일부를 바꾼 설정 사본 (장면용, `--half-life`·`--alpha`). 둘 다 None 이면 `cfg` 그대로.

    원본은 yaml 이다. 바꾼 블록도 World 가 같은 검사(`features.parse_features`, `_food_v_params`)를 거친다.
    `half_life` 는 학습용 목록 대신 반감기 하나로 고정한다(판정·장면은 설계값 693 하나, v2_0b.yaml 주석).
    """
    if half_life is None and alpha is None:
        return cfg
    if not features_of(cfg).enabled("food_v"):
        raise ValueError("--half-life·--alpha 는 food_v 를 켠 설정(예: configs/v2_0b.yaml)에서만 쓴다")
    feats = dict(cfg.v2["features"])
    block = dict(feats["food_v"])
    if half_life is not None:
        block["recovery_half_lives"] = [float(half_life)]
    if alpha is not None:
        block["alpha"] = float(alpha)
    feats["food_v"] = block
    return cfg.replace(v2=dict(cfg.v2, features=feats))


def overgraze_left(world: World, frac: float) -> None:
    """부재 시험 (ii) 과방목 교란 (계획서 6.4): 맵 왼쪽 절반(v2.3 전 지역 A 대용)의 V 를 frac·cap0 로 바꾼다.

    reset 직후, 스텝 전에 부른다. 오른쪽 절반은 reset 이 뽑은 값 그대로다. F 는 min(F, V) 로 자르고
    관측·기하를 다시 계산한다. 난수를 뽑지 않으므로 v1 스트림과 food_v 스트림이 교란 없는 같은 시드(대조)와
    같다(`features.py` 규칙 2: 뽑은 뒤 결과만 덮어쓴다). `food_v_init` 은 뽑은 값 기록이라 바꾸지 않는다.
    """
    if getattr(world, "food_v", None) is None:
        raise ValueError("과방목 교란은 food_v 를 켠 세계에서만 쓴다 (예: --config configs/v2_0b.yaml)")
    if world.t != 0:
        raise ValueError(f"과방목 교란은 reset 직후(t = 0)에만 준다. 지금 t = {world.t}")
    floor = float(world._fv["floor"])
    if not floor <= float(frac) <= 1.0:
        raise ValueError(f"교란 V 비율은 floor({floor}) 이상 1 이하여야 한다. 받은 값: {frac}")
    left = world._left_half()
    world.food_v[left] = float(frac) * world.food_cap[left]
    np.minimum(world.food, world.food_v, out=world.food)
    world._g = world._geometry()
    world._obs = world._obs_from(world._g)


FOOD_KEYS = ("v_left", "v_right", "f_left", "f_right")


def _food_row(fstats: dict) -> tuple:
    """`World.food_stats()` → (왼쪽 V, 오른쪽 V, 왼쪽 F, 오른쪽 F) 지역 비율 (ΣV/Σcap0, ΣF/Σcap0)."""
    return tuple(fstats[k] for k in ("v_ratio_left", "v_ratio_right", "f_ratio_left", "f_ratio_right"))


def food_series(world: World, policy, steps: int, stride: int) -> dict:
    """부재 시험 대조용: 그림 없이 `stride` 스텝마다 먹이 지역 비율만 남긴다 (`collect` 와 같은 시점, 스텝 전)."""
    stride = max(int(stride), 1)
    t, rows = [], []
    for k in range(steps):
        if k % stride == 0:
            t.append(k)
            rows.append(_food_row(world.food_stats()))
        world.step(policy(world.observe()))
    arr = np.asarray(rows, dtype=np.float64).reshape(-1, 4)
    return dict(t=np.asarray(t), **{key: arr[:, j] for j, key in enumerate(FOOD_KEYS)})


# --------------------------------------------------------------------- #
# 정책 스펙
# --------------------------------------------------------------------- #


def _resolve(path: str) -> str:
    """상대 경로가 현재 폴더에 없으면 이 파일 폴더 기준으로 찾는다."""
    p = Path(path)
    if not p.exists() and not p.is_absolute() and (ROOT / p).exists():
        p = ROOT / p
    return str(p)


def _resolve_spec(spec: dict) -> dict:
    """JSON 스펙 안의 learned 모델 경로(래퍼 안쪽 포함)를 `_resolve` 로 찾는다."""
    spec = dict(spec)
    if "policy" in spec:
        spec["policy"] = _resolve_spec(spec["policy"])
    elif spec.get("kind") == "learned" and "model" in spec:
        spec["model"] = _resolve(spec["model"])
    return spec


def perm_spec(base: dict, salt: int = 0) -> dict:
    """C1′ 행동 순열 스펙. `diagnose_v2.control_specs` 의 C1′ 과 같은 모양이다."""
    return {"policy": base, "wrap": [{"kind": "act_permute", "salt": int(salt)}]}


def parse_spec(text: str) -> dict:
    """문자열 → `env_v2.rollout.build_policy` 스펙.

    `learned:<zip>`, `fixed:a,b,c,d[,s[,v]]`, `utility`, `utility:default`, `random:<seed>`,
    `perm:<바탕 스펙>` (C1′ 행동 순열, 예: `perm:learned:ckpt/final.zip`),
    또는 JSON 딕셔너리 문자열 (래퍼 꼴 `{"policy": ..., "wrap": [...]}` 포함).
    fixed 는 v1 행동 4개 이상을 받는다. 세계의 행동 수와 맞는지는 `fit_spec` 이 설정을 읽은 뒤 본다.
    """
    text = text.strip()
    if text.startswith("{"):
        return _resolve_spec(json.loads(text))
    kind, _, arg = text.partition(":")
    kind = kind.strip().lower()
    if kind == "perm":
        if not arg.strip():
            raise ValueError(f"perm 은 바탕 스펙이 필요하다 (예: perm:learned:ckpt/final.zip): {text!r}")
        return perm_spec(parse_spec(arg))
    if kind == "learned":
        return {"kind": "learned", "model": _resolve(arg or "ckpt/final.zip")}
    if kind == "fixed":
        vals = [float(x) for x in arg.replace(" ", ",").split(",") if x]
        if len(vals) < ACT_DIM:
            raise ValueError(f"fixed 는 행동 {ACT_DIM}개 이상(설정의 행동 수)이 필요하다: {text!r}")
        return {"kind": "fixed", "action": vals}
    if kind == "utility":
        return {"kind": "utility", "params": "default"} if arg == "default" else {"kind": "utility"}
    if kind == "random":
        return {"kind": "random", "seed": int(arg) if arg else 0}
    raise ValueError(f"알 수 없는 정책 스펙: {text!r}")


def fit_spec(spec: dict, act_dim: int, act_names=()) -> dict:
    """스펙을 행동 `act_dim` 개 세계에 맞춘다(`env_v2.rollout.adapt_spec`: random 의 행동 수). fixed 길이가 다르거나
    Utility(행동 4개)를 행동 수가 다른 세계에 쓰면 ValueError 다. 래퍼 안쪽 바탕 정책도 본다."""
    spec = adapt_spec(spec, act_dim)
    base = spec
    while "policy" in base:
        base = base["policy"]
    names = f" {list(act_names)}" if act_names else ""
    if base.get("kind") == "fixed" and len(base["action"]) != act_dim:
        raise ValueError(f"fixed 는 이 설정의 행동 {act_dim}개{names} 가 필요하다. 받은 값: {base['action']}")
    if base.get("kind") == "utility" and act_dim != ACT_DIM:
        raise ValueError(f"Utility 는 행동 4개만 낸다. 이 설정은 행동 {act_dim}개{names} 다 (Utility v2 없음)")
    return spec


_WRAP_LABELS = {"act_permute": "행동 순열", "act_fix": "행동 고정", "obs_fix": "관측 고정",
                "obs_permute": "관측 순열", "seg_const": "구간별 상수"}


def spec_label(spec: dict) -> str:
    """스펙의 짧은 표시 이름. 래퍼 스펙은 `래퍼 · 바탕` 꼴이다."""
    if "policy" in spec:
        wraps = [_WRAP_LABELS.get(w.get("kind"), w.get("kind") or w.get("factory", "?"))
                 for w in spec.get("wrap", [])]
        return " · ".join(wraps[::-1] + [spec_label(spec["policy"])])
    kind = spec["kind"]
    if kind == "learned":
        return f"학습 정책 ({Path(spec['model']).name})"
    if kind == "fixed":
        return "상수 [" + " ".join(f"{x:.3f}" for x in spec["action"]) + "]"
    if kind == "utility":
        return "Utility (기본값)" if spec.get("params") == "default" else "Utility"
    if kind == "random":
        return f"랜덤 (seed {spec.get('seed', 0)})"
    return kind


# --------------------------------------------------------------------- #
# 수집
# --------------------------------------------------------------------- #


@dataclass
class Run:
    """정책 하나의 리플레이 기록."""

    label: str
    world: World
    frames: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    overgraze: float | None = None       # 과방목 교란을 줬으면 왼쪽 V 시작 비율
    control: dict | None = None          # 부재 시험 대조(교란 없는 같은 시드)의 `food_series`


def _hook(world, name: str):
    """뒤 버전 훅 속성. 없으면 None, 있으면 사본."""
    v = getattr(world, name, None)
    return None if v is None else np.array(v, copy=True)


def _snapshot(world: World, tracker: RespawnTracker, t: int) -> dict:
    """스텝 전 상태 중 그릴 것만 복사한다."""
    food_v = _hook(world, "food_v")
    return dict(
        t=t,
        pos=world.pos.copy(),
        head=world.head.copy(),
        alpha=tracker.alpha(),
        life=tracker.life.copy(),
        pred=world.pred_pos.copy(),
        pred_head=world.pred_head.copy(),
        food=world.food.copy(),
        caught=int(world._pred_deaths),
        starved=int(world._starve_deaths),
        mem=_hook(world, "region_mem"),
        bold=_hook(world, "boldness"),
        food_v=food_v,
        fstats=None if food_v is None else world.food_stats(),
    )


def _applied(world: World, v_pre: np.ndarray | None) -> dict:
    """스텝 뒤에 읽는 값: 이번 스텝에 적용된 보행·경계·시선. 같은 스텝이라 서로 어긋나지 않는다."""
    return dict(
        gait=applied_gait(world, v_pre),
        vig=_hook(world, "vigilant"),
        gaze=_hook(world, "gaze"),
    )


def collect(world: World, policy, steps: int, stride: int, fade_frames: int = 6) -> list:
    """`steps` 스텝을 돌리며 `stride` 스텝마다 한 프레임을 남긴다."""
    stride = max(int(stride), 1)
    tracker = RespawnTracker(world.N, fade_frames * stride)
    frames = []
    for t in range(steps):
        a = policy(world.observe())
        snap, v_pre = None, None
        if t % stride == 0:
            snap = _snapshot(world, tracker, t)
            if getattr(world, "gait", None) is None:     # gait 훅이 없을 때만 조향식을 다시 계산
                v_pre = steer(world._g, np.asarray(a, dtype=np.float64), world.cfg)
        _, _, done, _ = world.step(a)
        if snap is not None:
            snap.update(_applied(world, v_pre))
            frames.append(snap)
        tracker.update(done)
    return frames


def series(frames: list) -> dict:
    """하단 시계열 패널용 배열 (프레임마다 한 값)."""
    gait = np.stack([gait_fractions(f["gait"]) for f in frames])         # (F,3)
    vig = np.array(
        [np.nan if f["vig"] is None else float(np.mean(f["vig"])) for f in frames]
    )
    mems = [f["mem"] for f in frames]
    mem = None if mems[0] is None else np.stack([np.ravel(m) for m in mems])
    food = None
    if frames[0].get("fstats") is not None:
        arr = np.array([_food_row(f["fstats"]) for f in frames], dtype=np.float64)
        food = {key: arr[:, j] for j, key in enumerate(FOOD_KEYS)}
    return dict(
        t=np.array([f["t"] for f in frames]),
        gait=gait,
        vig=vig,
        mem=mem,
        food=food,
        caught=np.array([f["caught"] for f in frames]),
        starved=np.array([f["starved"] for f in frames]),
    )


def caught_ylim(caught_max: int) -> float:
    """포획 누적 축의 위 끝. 칸끼리 같은 값을 쓴다."""
    return max(int(caught_max), 1) * 1.08


def shared_scale(runs: list, step_sec: float) -> tuple[float, int]:
    """나란히 그릴 칸들이 함께 쓸 (x 끝(초), 포획 누적 최대). 칸마다 따로 맞추면 수가 달라도
    선이 같은 높이에서 끝나 눈으로 비교할 수 없다."""
    x_end = max(max(float(r.frames[-1]["t"]) * step_sec for r in runs), step_sec)
    caught_max = max(max(int(f["caught"]) for f in r.frames) for r in runs)
    return x_end, caught_max


def run_policy(cfg, spec: dict, seed: int, steps: int, stride: int, label: str | None = None,
               fade_frames: int = 6, overgraze: float | None = None, control: bool = True) -> Run:
    """같은 시드의 새 세계에서 정책 하나를 돌린다. 래퍼(C1′ 순열 등)의 시드도 같은 `seed` 다.

    `overgraze` 를 주면 시작 직후 과방목 교란(`overgraze_left`)을 준다. `control` 이면 교란 없는 같은 시드·
    같은 정책도 돌려 먹이 지역 비율을 `Run.control` 에 남긴다(부재 시험의 대조, 계획서 6.4).
    """
    world = World(cfg, seeds=[seed])
    ctl = None
    if overgraze is not None:
        overgraze_left(world, overgraze)
        if control:
            ctl = food_series(World(cfg, seeds=[seed]), build_policy(spec, seed), steps, stride)
    frames = collect(world, build_policy(spec, seed), steps, stride, fade_frames)
    return Run(label or spec_label(spec), world, frames, world.stats(), overgraze, ctl)


def absence_lines(run: Run, step_sec: float) -> list:
    """부재 시험 (ii) 출력줄: 왼쪽 V/cap0·F/cap0 를 t0, t0+h, t0+3h (h = 이 세계의 회복 반감기)에서,
    교란 vs 대조. 프레임은 stride 마다라 각 시점에 가장 가까운 프레임을 쓴다(실제 스텝을 함께 적는다).
    마지막 프레임을 넘는 시점은 건너뛴다."""
    if run.overgraze is None or run.frames[0].get("fstats") is None:
        return []
    h = float(run.frames[0]["fstats"]["half_life"])
    t = np.array([f["t"] for f in run.frames])
    ser = series(run.frames)["food"]
    lines = []
    for name, mult in (("t0", 0.0), ("t0+h", 1.0), ("t0+3h", 3.0)):
        target = mult * h
        if target > t[-1]:
            continue
        i = int(np.abs(t - target).argmin())
        row = (f"  {name:6s} step {int(t[i]):5d} ({fmt_clock(t[i] * step_sec)})  "
               f"교란 V {ser['v_left'][i]:.3f} F {ser['f_left'][i]:.3f}")
        if run.control is not None:
            j = int(np.abs(run.control["t"] - target).argmin())
            row += f"  | 대조 V {run.control['v_left'][j]:.3f} F {run.control['f_left'][j]:.3f}"
        lines.append(row)
    return lines


# --------------------------------------------------------------------- #
# 렌더
# --------------------------------------------------------------------- #


def _trail(frames: list, i: int, slot: int, length: int) -> np.ndarray:
    """프레임 i 까지 슬롯의 같은 생애 궤적 (최대 length 프레임)."""
    life = frames[i]["life"][slot]
    pts = []
    for k in range(i, max(i - length, -1), -1):
        if frames[k]["life"][slot] != life:
            break
        pts.append(frames[k]["pos"][slot])
    return np.asarray(pts[::-1]).reshape(-1, 2)


def _vig_mask(f: dict) -> np.ndarray:
    """프레임의 경계 여부 (N,) bool. 훅이 없으면 모두 False."""
    vig = f["vig"]
    return np.zeros(len(f["pos"]), dtype=bool) if vig is None else np.asarray(vig, dtype=bool)


class _Panel:
    """정책 하나의 지도 + 시계열 칸."""

    def __init__(self, fig, run: Run, rect_map, rect_ser, step_sec: float, fov_preds: int,
                 trail_len: int, x_end: float, caught_max: int, fov_herbs: int = 0, rect_food=None):
        """`x_end`(초)와 `caught_max` 는 칸끼리 같은 축을 쓰도록 바깥에서 정해 넘긴다.
        `rect_food` 는 먹이 시계열 칸(v2.0b). 이 칸의 run 에 `food_v` 훅이 없으면 쓰지 않는다."""
        self.run, self.frames, self.step_sec = run, run.frames, step_sec
        self.trail_len = trail_len
        w, cfg = run.world, run.world.cfg
        self.ser = series(self.frames)
        f0 = self.frames[0]

        ax = self.ax = fig.add_axes(rect_map)
        ax.set_facecolor(BG)
        ax.set_xlim(0, w.size)
        ax.set_ylim(0, w.size)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#444444")
        ax.set_title(run.label, color="white", fontsize=12, pad=6)

        extent = (0, w.gw * cfg.food_cell) * 2
        self.food_im = ax.imshow(
            f0["food"], origin="lower", extent=extent, cmap=FOOD_CMAP, vmin=0.0, vmax=1.0,
            interpolation="bilinear", zorder=0,
        )
        # 짓밟힌 땅 (v2.0b 훅): F 위에 V/cap0 막, 좌우 절반 경계 점선과 절반 라벨. 훅이 없으면 아무것도 안 만든다.
        self.trample_im, self.half_text, self.food_ax = None, [], None
        if f0["food_v"] is not None:
            self.food_cap = w.food_cap.copy()
            self.trample_im = ax.imshow(
                trample_rgba(f0["food_v"], self.food_cap), origin="lower", extent=extent,
                interpolation="bilinear", zorder=0.25,
            )
            # _left_half 는 셀 중심 x < size/2 다. 경계선은 그 셀 열의 오른쪽 끝에 긋는다.
            x_b = float(w._left_half()[0].sum()) * cfg.food_cell
            ax.axvline(x_b, color="white", lw=0.9, ls=(0, (3, 3)), alpha=0.5, zorder=1.5)
            for k, (xa, ha) in enumerate(((0.01, "left"), (0.99, "right"))):
                self.half_text.append(ax.text(
                    xa, 0.01, "", transform=ax.transAxes, ha=ha, va="bottom", color=HALF_COLORS[k],
                    fontsize=9, zorder=6,
                    bbox=dict(facecolor="black", alpha=0.55, edgecolor="none", pad=2.5),
                ))
        # 지역 기억 (v2.3 훅). region_id 는 먹이 격자와 같은 모양이다.
        self.region_id = getattr(w, "region_id", None)
        self.mem_im = None
        if self.region_id is not None and f0["mem"] is not None:
            self.mem_im = ax.imshow(
                self._mem_rgba(f0["mem"]), origin="lower", extent=extent,
                interpolation="nearest", zorder=0.5,
            )
        # 은신처는 판정(_in_cover)과 같은 정확한 원으로 그린다.
        for (cx, cy), cr in zip(w.cov_c, w.cov_r):
            ax.add_patch(Circle((cx, cy), cr, facecolor="black", alpha=0.55,
                                edgecolor="#5566aa", linewidth=0.8, zorder=1))

        # 포식자 시야 부채꼴: 앞쪽 몇 마리만.
        half = 0.5 * float(cfg.pred_fov_deg)
        self.half_fov = half
        self.wedges = []
        for k in range(min(int(fov_preds), w.M)):
            wd = Wedge(tuple(f0["pred"][k]), float(cfg.pred_view_r), 0.0, 2 * half,
                       facecolor=PRED_FOV_FACE, edgecolor=PRED_FOV_EDGE, linewidth=0.8, zorder=2)
            ax.add_patch(wd)
            self.wedges.append(wd)
        # 초식 시야 부채꼴 (판정과 같은 see_r, fov_deg). 경계 중이면 360° 원이다(4.4).
        self.herb_half_fov = 0.5 * float(cfg.fov_deg)
        self.herb_wedges = []
        for _ in range(max(0, min(int(fov_herbs), w.N))):
            wd = Wedge((0.0, 0.0), float(cfg.see_r), 0.0, 2 * self.herb_half_fov,
                       facecolor=HERB_FOV_FACE, edgecolor=HERB_FOV_EDGE, linewidth=0.8, zorder=2)
            ax.add_patch(wd)
            self.herb_wedges.append(wd)
        self._update_herb_wedges(f0, _vig_mask(f0))

        # 궤적 (v2.4 훅): 대담 최대, 최소.
        self.trail_bold, = ax.plot([], [], color=BOLD_COLOR, lw=1.3, alpha=0.9, zorder=2.5)
        self.trail_timid, = ax.plot([], [], color=TIMID_COLOR, lw=1.3, alpha=0.9, zorder=2.5)

        n = w.N
        self.arrows = ax.quiver(
            f0["pos"][:, 0], f0["pos"][:, 1], f0["head"][:, 0] * ARROW_LEN,
            f0["head"][:, 1] * ARROW_LEN, angles="xy", scale_units="xy", scale=1.0,
            width=0.0028, headwidth=3.2, headlength=3.6, headaxislength=3.2,
            color=[(1, 1, 1, 0.65)] * n, zorder=3,
        )
        self.gaze = LineCollection([], colors="white", linewidths=1.2, zorder=3.5)
        ax.add_collection(self.gaze)
        self.herb = ax.scatter(f0["pos"][:, 0], f0["pos"][:, 1], s=24, zorder=4)
        self.melee = ax.scatter([], [], marker="X", c="#ff2d2d", s=150,
                                edgecolors="white", linewidths=0.8, zorder=5)
        self.ranged = ax.scatter([], [], marker="x", c="#ff7a7a", s=100, linewidths=2.2, zorder=5)
        self.ranged_mask = w.pred_ranged.copy()
        self.status = ax.text(
            0.01, 0.99, "", transform=ax.transAxes, ha="left", va="top", color="white",
            fontsize=9, family="monospace", zorder=6,
            bbox=dict(facecolor="black", alpha=0.55, edgecolor="none", pad=2.5),
        )
        self._series_axes(fig, rect_ser, x_end, caught_max)
        if self.trample_im is not None and rect_food is not None:
            self._food_axes(fig, rect_food, x_end)

    # --- 시계열 ---

    @staticmethod
    def _mask_cursor(ax, x_end: float):
        """미래 구간 덮개와 현재 시각 세로선."""
        mask = Rectangle((0, 0), x_end, 1, transform=ax.get_xaxis_transform(),
                         facecolor=BG, alpha=0.72, edgecolor="none", zorder=10)
        ax.add_patch(mask)
        return mask, ax.axvline(0, color="white", lw=0.9, zorder=11)

    def _series_axes(self, fig, rect, x_end: float, caught_max: int) -> None:
        s = self.ser
        x = s["t"] * self.step_sec
        ax = self.ser_ax = fig.add_axes(rect)
        ax.set_facecolor("#1a1a1a")
        ax.stackplot(x, s["gait"].T, colors=GAIT_COLORS, alpha=0.85, linewidth=0)
        if np.isfinite(s["vig"]).any():
            ax.plot(x, s["vig"], color=VIG_LINE_COLOR, lw=1.3)
        if s["mem"] is not None:
            for r in range(s["mem"].shape[1]):
                ax.plot(x, s["mem"][:, r], color=MEM_LINE_COLORS[r % len(MEM_LINE_COLORS)],
                        lw=1.2, ls="--")
        ax.set_xlim(0, x_end)
        ax.set_ylim(0, 1)
        ax.set_ylabel("비율", color=FG, fontsize=8)
        ax.xaxis.set_major_locator(MultipleLocator(clock_tick(x_end)))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_clock(v)))
        ax2 = self.caught_ax = ax.twinx()
        ax2.plot(x, s["caught"], color="#ff3b30", lw=1.4)
        ax2.set_ylim(0, caught_ylim(caught_max))
        ax2.set_ylabel("포획 누적", color="#ff6b6b", fontsize=8)
        for a in (ax, ax2):
            a.tick_params(colors=FG, labelsize=7, length=2)
            for sp in a.spines.values():
                sp.set_color("#444444")
        # 미래 구간은 어둡게 덮고, 현재 시각에 세로선을 둔다. 덮개는 위쪽(ax2)에 둔다.
        self.mask, self.cursor = self._mask_cursor(ax2, x_end)
        self.x_end = x_end

    def _food_axes(self, fig, rect, x_end: float) -> None:
        """v2.0b 먹이 시계열: 절반별 V/cap0(실선)·F/cap0(점선), 지역 비율 ΣV/Σcap0·ΣF/Σcap0.

        V 하한(floor) 은 회색 일점쇄선. 부재 시험이면 대조(교란 없는 같은 시드)의 왼쪽 V/cap0 를 가는 점선으로,
        t0+h·t0+3h 를 세로 점선으로 표시한다.
        """
        s, x = self.ser["food"], self.ser["t"] * self.step_sec
        ax = self.food_ax = fig.add_axes(rect)
        ax.set_facecolor("#1a1a1a")
        ax.axhline(float(self.run.world._fv["floor"]), color="#777777", lw=0.7, ls="-.", zorder=1)
        ctl = self.run.control
        if ctl is not None:
            ax.plot(ctl["t"] * self.step_sec, ctl["v_left"], color=CONTROL_COLOR, lw=1.1, ls=":",
                    zorder=2)
        if self.run.overgraze is not None:
            h = float(self.frames[0]["fstats"]["half_life"])
            for mult, name in ((1, "t0+h"), (3, "t0+3h")):
                if mult * h * self.step_sec <= x_end:
                    ax.axvline(mult * h * self.step_sec, color="#888888", lw=0.7, ls=":", zorder=1)
                    ax.text(mult * h * self.step_sec, 0.97, f" {name}", color="#aaaaaa", fontsize=7,
                            ha="left", va="top", transform=ax.get_xaxis_transform(), zorder=1)
        for side, c in zip(("left", "right"), HALF_COLORS):
            ax.plot(x, s["v_" + side], color=c, lw=1.6, zorder=3)
            ax.plot(x, s["f_" + side], color=c, lw=1.0, ls="--", zorder=3)
        ax.set_xlim(0, x_end)
        ax.set_ylim(0, 1)
        ax.set_ylabel("V·F / cap0", color=FG, fontsize=8)
        ax.xaxis.set_major_locator(MultipleLocator(clock_tick(x_end)))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_clock(v)))
        ax.tick_params(colors=FG, labelsize=7, length=2)
        for sp in ax.spines.values():
            sp.set_color("#444444")
        self.ser_ax.tick_params(labelbottom=False)          # x 눈금 글자는 맨 아래 칸에만
        self.food_mask, self.food_cursor = self._mask_cursor(ax, x_end)

    def _mem_rgba(self, mem: np.ndarray) -> np.ndarray:
        m = np.clip(np.ravel(mem)[np.asarray(self.region_id)], 0.0, 1.0)
        rgba = np.zeros(m.shape + (4,))
        rgba[..., :3] = MEM_RGB
        rgba[..., 3] = 0.35 * m
        return rgba

    # --- 프레임 갱신 ---

    def update(self, i: int):
        f = self.frames[i]
        pos, alpha = f["pos"], f["alpha"]
        self.food_im.set_data(f["food"])
        if self.trample_im is not None:
            self.trample_im.set_data(trample_rgba(f["food_v"], self.food_cap))
            row = _food_row(f["fstats"])
            for k, tx in enumerate(self.half_text):
                tx.set_text(f"{HALF_NAMES[k]} · V {row[k] * 100:.0f}% · F {row[2 + k] * 100:.0f}%")
        if self.mem_im is not None and f["mem"] is not None:
            self.mem_im.set_data(self._mem_rgba(f["mem"]))

        face = GAIT_RGBA[f["gait"]]
        face[:, 3] = alpha
        vig = _vig_mask(f)
        edge =np.where(vig[:, None], (1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0))
        edge[:, 3] *= alpha
        self.herb.set_offsets(pos)
        self.herb.set_facecolor(face)
        self.herb.set_edgecolor(edge)
        self.herb.set_linewidths(np.where(vig, 1.4, 0.35))

        arrow = np.ones((len(pos), 4))
        arrow[:, 3] = 0.65 * alpha
        self.arrows.set_offsets(pos)
        self.arrows.set_UVC(f["head"][:, 0] * ARROW_LEN, f["head"][:, 1] * ARROW_LEN)
        self.arrows.set_color(arrow)

        gdir = f["head"] if f["gaze"] is None else f["gaze"]
        segs = np.stack([pos[vig], pos[vig] + gdir[vig] * GAZE_LEN], 1) if vig.any() else []
        self.gaze.set_segments(segs)

        if f["bold"] is not None:
            b = np.asarray(f["bold"])
            for line, slot in ((self.trail_bold, int(b.argmax())), (self.trail_timid, int(b.argmin()))):
                tr = _trail(self.frames, i, slot, self.trail_len)
                line.set_data(tr[:, 0], tr[:, 1])

        m = ~self.ranged_mask
        self.melee.set_offsets(f["pred"][m] if m.any() else np.empty((0, 2)))
        self.ranged.set_offsets(f["pred"][~m] if (~m).any() else np.empty((0, 2)))
        for k, wd in enumerate(self.wedges):
            ang = float(np.degrees(np.arctan2(f["pred_head"][k, 1], f["pred_head"][k, 0])))
            wd.set_center(tuple(f["pred"][k]))
            wd.set_theta1(ang - self.half_fov)
            wd.set_theta2(ang + self.half_fov)
        self._update_herb_wedges(f, vig)

        sec = f["t"] * self.step_sec
        run_frac = float(np.mean(f["gait"] == GAIT_RUN))
        vig_s = "" if f["vig"] is None else f"vig {float(np.mean(vig)) * 100:3.0f}%  "
        self.status.set_text(
            f"{fmt_clock(sec)}  step {f['t']:5d}  run {run_frac*100:3.0f}%  {vig_s}"
            f"caught {f['caught']:4d}  starved {f['starved']:3d}"
        )
        self.mask.set_x(sec)
        self.mask.set_width(max(self.x_end - sec, 0.0))
        self.cursor.set_xdata([sec, sec])
        if self.food_ax is not None:
            self.food_mask.set_x(sec)
            self.food_mask.set_width(max(self.x_end - sec, 0.0))
            self.food_cursor.set_xdata([sec, sec])

    def _update_herb_wedges(self, f: dict, vig: np.ndarray) -> None:
        """초식 부채꼴: heading 기준 ±fov/2, 경계 중이면 360° 원. 리스폰 흐림을 따른다."""
        if not self.herb_wedges:
            return
        slots = fov_slots(len(f["pos"]), len(self.herb_wedges), f["bold"])
        for wd, s in zip(self.herb_wedges, slots):
            if vig[s]:
                t1, t2 = 0.0, 360.0
            else:
                ang = float(np.degrees(np.arctan2(f["head"][s, 1], f["head"][s, 0])))
                t1, t2 = ang - self.herb_half_fov, ang + self.herb_half_fov
            wd.set_center(tuple(f["pos"][s]))
            wd.set_theta1(t1)
            wd.set_theta2(t2)
            a = float(f["alpha"][s])
            wd.set_facecolor(HERB_FOV_FACE[:3] + (HERB_FOV_FACE[3] * a,))
            wd.set_edgecolor(HERB_FOV_EDGE[:3] + (HERB_FOV_EDGE[3] * a,))


def _n_regions(runs: list) -> int:
    """기억 훅이 있는 칸 중 가장 많은 지역 수. 훅이 없으면 0."""
    return max((np.size(f0["mem"]) for f0 in (r.frames[0] for r in runs) if f0["mem"] is not None),
               default=0)


def _legend_handles(runs: list, fov_herbs: int = 0, fov_preds: int = 0) -> list:
    """범례: 보행 3색, 리스폰, 포식자, 은신처, 시야, 하단 선, 훅이 있으면 경계·궤적·지역별 기억·먹이 상태."""
    dot = dict(marker="o", ls="none", markersize=7, markeredgecolor="black")
    h = [Line2D([], [], color=c, label=n, markerfacecolor=c, **dot)
         for n, c in zip(GAIT_NAMES, GAIT_COLORS)]
    h.append(Line2D([], [], label="리스폰 직후(흐림)", markerfacecolor=(1.0, 0.58, 0.0, DIM_ALPHA),
                    **dot))
    has = {k: any(r.frames[0].get(k) is not None for r in runs) for k in ("vig", "bold", "food_v")}
    if has["vig"]:
        h.append(Line2D([], [], label="경계(흰 테두리)", marker="o", ls="none", markersize=7,
                        markerfacecolor=GAIT_COLORS[0], markeredgecolor="white",
                        markeredgewidth=1.5))
    h.append(Line2D([], [], label="근접 포식자", marker="X", ls="none", markersize=9,
                    markerfacecolor="#ff2d2d", markeredgecolor="white"))
    h.append(Line2D([], [], label="원거리 포식자", marker="x", ls="none", markersize=8,
                    color="#ff7a7a", markeredgewidth=2))
    h.append(Line2D([], [], label="은신처", marker="o", ls="none", markersize=9,
                    markerfacecolor="black", markeredgecolor="#5566aa"))
    if has["food_v"]:
        bare = np.array(FOOD_CMAP(0.05)[:3])
        h.append(Patch(facecolor=FOOD_CMAP(1.0), label="먹이 많음"))
        h.append(Patch(facecolor=bare, label="맨땅·뜯긴 셀"))
        h.append(Patch(facecolor=TRAMPLE_ALPHA * np.array(TRAMPLE_RGB) + (1 - TRAMPLE_ALPHA) * bare,
                       label="짓밟힌 땅"))
    if fov_herbs > 0:
        label = "초식 시야(경계 시 360°)" if has["vig"] else "초식 시야"
        h.append(Patch(facecolor=HERB_FOV_FACE[:3] + (0.18,), edgecolor=HERB_FOV_EDGE, label=label))
    if fov_preds > 0:
        h.append(Patch(facecolor=PRED_FOV_FACE[:3] + (0.25,), edgecolor=PRED_FOV_EDGE,
                       label="포식자 시야"))
    h.append(Line2D([], [], color="#ff3b30", lw=1.6, label="포획 누적(하단)"))
    if has["vig"]:
        h.append(Line2D([], [], color=VIG_LINE_COLOR, lw=1.4, label="경계 비율(하단)"))
    if has["bold"]:
        h.append(Line2D([], [], color=BOLD_COLOR, lw=1.6, label="대담 최대"))
        h.append(Line2D([], [], color=TIMID_COLOR, lw=1.6, label="대담 최소"))
    for r in range(_n_regions(runs)):
        h.append(Line2D([], [], color=MEM_LINE_COLORS[r % len(MEM_LINE_COLORS)], lw=1.4, ls="--",
                        label=f"지역 기억 {region_name(r)}(하단)"))
    if has["food_v"]:
        for name, c in zip(HALF_NAMES, HALF_COLORS):
            h.append(Line2D([], [], color=c, lw=1.6, label=f"{name} V/cap0"))
        h.append(Line2D([], [], color=FG, lw=1.0, ls="--", label="F/cap0(점선)"))
        if any(r.control is not None for r in runs):
            h.append(Line2D([], [], color=CONTROL_COLOR, lw=1.1, ls=":", label="대조 왼쪽 V"))
    return h


def _row_major(handles: list, ncol: int) -> list:
    """범례는 열 우선으로 채워진다. 행 우선으로 읽히게 순서를 바꾸고 빈칸을 채운다."""
    rows = -(-len(handles) // ncol)
    pad = handles + [Line2D([], [], ls="none", label=" ")] * (rows * ncol - len(handles))
    return [pad[i * ncol + j] for j in range(ncol) for i in range(rows)]


def _layout(ncols: int, col_w: float, food: bool = False, bottom_extra: float = 0.0):
    """칸마다 (지도 rect, 시계열 rect, 먹이 시계열 rect 또는 None) 와 그림 크기(인치). 픽셀이 짝수가 되게 맞춘다.

    `food` 면 시계열 아래에 먹이 칸(v2.0b)을 붙인다. `bottom_extra` 는 범례 줄·설명줄이 늘어난 만큼의 아래 여백.
    둘 다 없으면 v2.0 그림과 같은 크기·위치다(0.0 을 더하는 것은 부동소수에서도 값이 그대로다).
    """
    top, gap, ser_h, bottom = 0.45, 0.30, col_w * 0.27, 1.15 + bottom_extra
    food_h, food_gap = (col_w * 0.20, 0.10) if food else (0.0, 0.0)
    map_h = col_w - 0.25
    W = ncols * col_w
    H = round((top + map_h + gap + ser_h + food_gap + food_h + bottom) / 0.02) * 0.02
    rects = []
    for i in range(ncols):
        x0 = i * col_w + 0.125
        y_ser = bottom + food_h + food_gap
        m = (x0 / W, (y_ser + ser_h + gap) / H, map_h / W, map_h / H)
        s = ((x0 + 0.45) / W, y_ser / H, (map_h - 0.95) / W, ser_h / H)
        fd = ((x0 + 0.45) / W, bottom / H, (map_h - 0.95) / W, food_h / H) if food else None
        rects.append((m, s, fd))
    return (W, H), rects


def gait_source(world) -> str:
    """보행을 어디서 읽었나 (화면 아래 설명줄용)."""
    if getattr(world, "gait", None) is not None:
        return "보행 = World.gait (실제 적용 상태)"
    src = "World.vel" if getattr(world, "vel", None) is not None else "조향식"
    return f"보행 = |v|/herb_speed, v={src} (0 정지, ≤{WALK_MAX} 걷기, 초과 뛰기)"


def speed_line(runs: list) -> str | None:
    """v2.1 설명줄: 이 영상에 쓴 speed 계수(yaml). speed 를 끈 설정이면 None (그림이 v2.0 과 같다)."""
    sp = getattr(runs[0].world, "_sp", None)
    if sp is None:
        return None
    j = lambda xs, f: "/".join(format(float(x), f) for x in xs)      # noqa: E731
    return (f"speed 문턱 {j(sp['thresholds'], '.3f')} | 정지/걷기/뛰기: 속력 {j(sp['speed'], 'g')}×herb_speed · "
            f"섭식 {j(sp['eat'], 'g')} · 대사 {j(sp['drain_mult'], '.3g')}×energy_drain | 에너지 보상 "
            + ("순변화" if sp["net_energy_reward"] else "v1 획득량"))


def vigil_line(runs: list) -> str | None:
    """v2.2 설명줄: 이 영상에 쓴 vigilance 계수(yaml). vigilance 를 끈 설정이면 None (그림이 v2.1 과 같다)."""
    vg = getattr(runs[0].world, "_vg", None)
    if vg is None:
        return None
    hl = vg["half_life"]
    hl_s = "∞" if not np.isfinite(hl) else f"{hl:.1f}"
    tf = vg.get("threat_flee", 0.0)
    return (f"vigilance 문턱 > {vg['threshold']:g} | 경계: 속력 0 · 섭식 {vg['eat_mult']:g} · 정지 대사 · "
            f"시야 {vg['fov_deg']:g}°(반경 see_r) · 위협 쪽 보기 | threat_recency 감쇠 {vg['decay']:g}"
            f"(반감기 {hl_s}스텝)" + (f" | #18 위협 반대 조향 ×{tf:g}" if tf > 0.0 else ""))


def food_line(runs: list) -> str | None:
    """v2.0b 설명줄: 이 영상에 쓴 food_v 계수(yaml 또는 `--half-life`·`--alpha` 로 바꾼 값)와 V 시작 비율.
    food_v 훅이 없으면 None."""
    f0 = runs[0].frames[0]
    if f0.get("fstats") is None:
        return None
    w0, fs = runs[0].world, f0["fstats"]
    h, sec = float(fs["half_life"]), step_seconds(w0.cfg)
    og = "" if runs[0].overgraze is None else "(교란)"
    return (
        f"food_v α {w0._fv['alpha']:g} · 하한 {w0._fv['floor']:g} · 반감기 {h:g}스텝({h * sec:.0f}초) | "
        f"시작 V/cap0 왼쪽 {fs['v_ratio_left']:.2f}{og}·오른쪽 {fs['v_ratio_right']:.2f} | 지역 = 좌우 절반"
    )


LINE_IN = 8.5 * 1.4 / 72     # 설명줄 한 줄 높이(인치): 글자 8.5pt × 줄 간격 1.4
LEGEND_ROW_IN = 0.21         # 범례 한 줄 높이(인치, 대략)


def build_figure(runs: list, fps: int = 30, dpi: int = 100, fov_preds: int = 2,
                 trail_len: int = 120, fov_herbs: int = 2, caption: str | None = None):
    """그림과 칸들을 만든다. 반환: (fig, update(i), 프레임 수, 칸 목록).

    칸들은 x축 끝과 포획 누적 축 위 끝을 함께 쓴다(`shared_scale`). `caption` 은 설명줄 위의 자막 한 줄이다.
    먹이 칸·자막이 없고 범례가 두 줄 이하면 v2.0 그림과 크기·위치가 같다.
    """
    n_frames = min(len(r.frames) for r in runs)
    if n_frames == 0:
        raise ValueError("프레임이 없다")
    w0 = runs[0].world
    step_sec = step_seconds(w0.cfg)
    stride = int(runs[0].frames[1]["t"] - runs[0].frames[0]["t"]) if n_frames > 1 else 1
    col_w = 6.4 if len(runs) == 1 else 5.6
    food = any(r.frames[0].get("food_v") is not None for r in runs)

    handles = _legend_handles(runs, fov_herbs=min(fov_herbs, w0.N), fov_preds=min(fov_preds, w0.M))
    per_row = max(1, int(len(runs) * col_w / 1.2))  # 범례 한 칸 약 1.2인치
    rows = -(-len(handles) // per_row)
    ncol = -(-len(handles) // rows)
    speedup = stride * step_sec * fps
    world_line = (
        f"seed={w0.seed} | world={w0.size:.0f} | M={w0.M} (원거리 {int(w0.pred_ranged.sum())}) | "
        f"은신처 {w0.cover_frac_actual*100:.0f}%"
    )
    time_line = (
        f"1스텝={step_sec:.4f}초, stride {stride}, {fps}fps → x{speedup:.1f} | {gait_source(w0)}"
    )
    sep = " | " if len(runs) > 1 else "\n"
    info = world_line + sep + time_line
    extra = [x for x in (speed_line(runs), vigil_line(runs), food_line(runs)) if x is not None]
    for line in extra:
        info += "\n" + line
    # 설명줄(아래) → 자막 → 범례 순으로 쌓는다. 늘어난 만큼 아래 여백을 키운다.
    n_info = info.count("\n") + 1
    cap_y = 0.06 + n_info * LINE_IN + 0.04
    legend_y = 0.40
    if extra or caption:
        legend_y = max(0.40, cap_y + (LINE_IN + 0.04 if caption else 0.0))
    bottom_extra = (legend_y - 0.40) + LEGEND_ROW_IN * max(rows - 2, 0)
    size, rects = _layout(len(runs), col_w, food, bottom_extra)

    fig = plt.figure(figsize=size, dpi=dpi)
    fig.patch.set_facecolor(BG)
    x_end, caught_max = shared_scale(runs, step_sec)
    panels = [_Panel(fig, r, m, s, step_sec, fov_preds, trail_len, x_end, caught_max, fov_herbs, fd)
              for r, (m, s, fd) in zip(runs, rects)]

    fig.legend(handles=_row_major(handles, ncol), loc="lower center", ncol=ncol,
               bbox_to_anchor=(0.5, legend_y / size[1]), frameon=False, labelcolor=FG,
               fontsize=8.5, handletextpad=0.3, columnspacing=1.1)
    fig.text(0.5, 0.06 / size[1], info, ha="center", va="bottom",
             color="#aaaaaa", fontsize=8.5, linespacing=1.4)
    if caption:
        fig.text(0.5, cap_y / size[1], caption, ha="center", va="bottom", color="#ffe08a", fontsize=9)

    def update(i):
        for p in panels:
            p.update(i)
        return []

    return fig, update, n_frames, panels


def render_png(runs: list, out: Path, step: int, fps: int = 30, dpi: int = 100, fov_preds: int = 2,
               trail_len: int = 120, fov_herbs: int = 2,
               caption: str | None = None) -> tuple[Path, int]:
    """스텝 `step` 에 가장 가까운 프레임 한 장을 PNG 로 (발표·문서용). 반환: (경로, 그 프레임의 스텝).

    `fps` 는 설명줄의 배속 표시에만 쓴다(같이 만든 영상과 같은 글이 되게).
    """
    fig, update, n_frames, _ = build_figure(runs, fps, dpi, fov_preds, trail_len, fov_herbs, caption)
    t = np.array([f["t"] for f in runs[0].frames[:n_frames]])
    i = int(np.abs(t - int(step)).argmin())
    update(i)
    out = Path(out)
    fig.savefig(str(out), dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out, int(t[i])


def render(runs: list, out: Path, fps: int = 30, dpi: int = 100, bitrate: int | None = None,
           fov_preds: int = 2, trail_len: int = 120, fov_herbs: int = 2,
           caption: str | None = None) -> Path:
    """Run 여러 개를 나란히 한 영상으로. 실제로 쓴 경로(gif 로 떨어졌으면 .gif)를 돌려준다."""
    fig, update, n_frames, _ = build_figure(runs, fps, dpi, fov_preds, trail_len, fov_herbs, caption)
    anim = animation.FuncAnimation(fig, update, frames=n_frames, interval=1000 // fps)
    bitrate = bitrate or 2600 * len(runs)
    writer, out = pick_writer(Path(out), fps, bitrate)
    try:
        anim.save(str(out), writer=writer)
    except Exception as e:                       # mp4 인코딩 실패 → gif
        if out.suffix != ".mp4":
            raise
        print(f"mp4 저장 실패({e}). gif 로 저장한다.", file=sys.stderr)
        out = out.with_suffix(".gif")
        anim.save(str(out), writer=animation.PillowWriter(fps=fps))
    plt.close(fig)
    return out


def _ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe is None:
        try:
            import imageio_ffmpeg

            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            exe = None
    return exe


def pick_writer(out: Path, fps: int, bitrate: int = 2600):
    """mp4를 우선하고, ffmpeg이 없으면 gif로 떨어진다."""
    exe = _ffmpeg_exe()
    if exe and out.suffix == ".mp4":
        matplotlib.rcParams["animation.ffmpeg_path"] = exe
        return animation.FFMpegWriter(fps=fps, bitrate=bitrate), out
    if out.suffix == ".mp4":
        print("ffmpeg을 찾지 못했다. gif로 저장한다. (pip install imageio-ffmpeg)", file=sys.stderr)
        out = out.with_suffix(".gif")
    return animation.PillowWriter(fps=fps), out


def video_info(path: Path) -> dict:
    """영상 파일 크기(MB)와 프레임 수·길이(초). mp4 는 ffmpeg 로 센다."""
    path = Path(path)
    info = {"path": str(path), "mb": path.stat().st_size / 1e6}
    try:
        if path.suffix == ".gif":
            from PIL import Image

            with Image.open(path) as im:
                info["frames"] = int(getattr(im, "n_frames", 1))
        else:
            import imageio_ffmpeg

            n, secs = imageio_ffmpeg.count_frames_and_secs(str(path))
            info["frames"], info["secs"] = int(n), float(secs)
    except Exception:
        pass
    return info


# --------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="V2 리플레이 영상 (계획서 6.4)")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--model", default=None, help="학습 정책 zip. --policy learned:<zip> 와 같다")
    src.add_argument("--policy", default=None,
                     help="정책 스펙: learned:<zip> | fixed:a,b,c,d | utility[:default] | "
                          "random:<seed> | perm:<바탕 스펙> | JSON")
    src.add_argument("--compare", nargs="+", default=None, metavar="SPEC",
                     help="같은 시드·카메라로 나란히 그릴 정책 스펙들. 예: C0·C1′·C2 = "
                          "learned:<zip> perm:learned:<zip> fixed:a,b,c,d")
    p.add_argument("--labels", nargs="+", default=None, help="정책별 표시 이름 (스펙 수 이하)")
    p.add_argument("--seed", type=int, default=10000, help="평가 시드 기본값")
    p.add_argument("--steps", type=int, default=1800)
    p.add_argument("--stride", type=int, default=2, help="몇 스텝마다 한 프레임 (타임랩스)")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--out", default=None)
    p.add_argument("--config", default=None, help="V2 yaml. 기본 configs/v2.yaml")
    p.add_argument("--fade-frames", type=int, default=6, help="리스폰 뒤 흐리게 그릴 프레임 수")
    p.add_argument("--fov-herbs", type=int, default=2,
                   help="시야 부채꼴을 그릴 초식 수 (대담함 훅이 있으면 궤적 두 개체 먼저)")
    p.add_argument("--fov-preds", type=int, default=2, help="시야 부채꼴을 그릴 포식자 수")
    p.add_argument("--trail", type=int, default=120, help="궤적 길이 (프레임)")
    p.add_argument("--dpi", type=int, default=100)
    p.add_argument("--bitrate", type=int, default=None, help="kbps. 기본 칸당 2600")
    # v2.0b 먹이 장면 (food_v 를 켠 설정에서만)
    p.add_argument("--half-life", type=float, default=None, metavar="H",
                   help="food_v 회복 반감기를 H 스텝 하나로 고정 (학습 목록 대신. 판정·장면 설계값 693)")
    p.add_argument("--alpha", type=float, default=None,
                   help="food_v 훼손 계수 α 를 바꾼다 (장면용. 기본은 yaml 값, 바꾼 값은 설명줄에 남는다)")
    p.add_argument("--overgraze-left", type=float, default=None, metavar="FRAC",
                   help="부재 시험 (ii) 과방목 교란: 왼쪽 절반 V 를 FRAC·cap0 로 시작 (계획서 6.4, 예: 0.3). "
                        "교란 없는 같은 시드 대조도 돌린다")
    p.add_argument("--no-control", action="store_true", help="--overgraze-left 의 대조 실행을 건너뛴다")
    p.add_argument("--png", type=int, default=None, metavar="STEP",
                   help="이 스텝에 가장 가까운 프레임을 --out 과 같은 이름의 .png 로도 저장")
    p.add_argument("--png-dpi", type=int, default=None, help="PNG 해상도. 기본 --dpi")
    p.add_argument("--caption", default=None, help="설명줄 위 자막 한 줄")
    return p


def specs_and_labels(p: argparse.ArgumentParser, args) -> tuple[list, list]:
    """인자 → (스펙 목록, 라벨 목록). 라벨이 스펙보다 많으면 p.error 로 끝낸다."""
    try:
        if args.compare:
            specs = [parse_spec(s) for s in args.compare]
        elif args.policy:
            specs = [parse_spec(args.policy)]
        else:
            specs = [parse_spec(f"learned:{args.model or 'ckpt/final.zip'}")]
    except ValueError as e:                     # JSONDecodeError 도 ValueError 다
        p.error(str(e))
    labels = list(args.labels or [])
    if len(labels) > len(specs):
        p.error(f"--labels {len(labels)}개가 정책 스펙 {len(specs)}개보다 많다: {labels}")
    labels += [None] * (len(specs) - len(labels))
    return specs, labels


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    specs, labels = specs_and_labels(p, args)

    cfg = load_v2_config(args.config)
    try:                                        # 무엇을 돌리기 전에 계수·교란 비율·행동 수를 검사한다
        cfg = food_v_config(cfg, args.half_life, args.alpha)
        probe = World(cfg, seeds=[args.seed])
        if args.overgraze_left is not None:
            overgraze_left(probe, args.overgraze_left)
        specs = [fit_spec(sp, probe.act_dim, probe.act_names) for sp in specs]
    except ValueError as e:
        p.error(str(e))
    runs = []
    for spec, label in zip(specs, labels):
        print(f"수집 중: {label or spec_label(spec)} — {args.steps} 스텝, 매 {args.stride}스텝 1프레임")
        runs.append(run_policy(cfg, spec, args.seed, args.steps, args.stride, label,
                               args.fade_frames, args.overgraze_left, not args.no_control))

    name = "replay_v2_compare.mp4" if len(runs) > 1 else "replay_v2.mp4"
    out = Path(args.out) if args.out else ROOT / "results" / "v2" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"렌더 중: {len(runs[0].frames)} 프레임 × {len(runs)}칸 -> {out}")
    out = render(runs, out, args.fps, args.dpi, args.bitrate, args.fov_preds, args.trail,
                 args.fov_herbs, args.caption)

    info = video_info(out)
    extra = f", {info['frames']} 프레임" if "frames" in info else ""
    extra += f", {info['secs']:.1f}초" if "secs" in info else ""
    print(f"완료: {out}  ({info['mb']:.2f} MB{extra})")
    if args.png is not None:
        png, t_png = render_png(runs, out.with_suffix(".png"), args.png, args.fps,
                                args.png_dpi or args.dpi, args.fov_preds, args.trail, args.fov_herbs,
                                args.caption)
        print(f"PNG: {png}  (step {t_png}, {png.stat().st_size / 1e6:.2f} MB)")
    step_sec = step_seconds(cfg)
    for r in runs:
        lines = absence_lines(r, step_sec)
        if lines:
            print(f"  [{r.label}] 부재 시험 (ii) 왼쪽 V/cap0·F/cap0 (지역 비율), 교란 {r.overgraze:g}·cap0 vs 대조")
            print("\n".join(lines))
    for r in runs:
        g = np.mean([gait_fractions(f["gait"]) for f in r.frames], axis=0)
        vig = [f["vig"] for f in r.frames if f["vig"] is not None]
        print(
            f"  [{r.label}] mean_return={r.stats['mean_return']:.2f}  "
            f"survival={r.stats['survival']:.0f}  repro={r.stats['repro']:.2f}  "
            f"predation_rate={r.stats['predation_rate']:.5f}  "
            f"보행 정지/걷기/뛰기={g[0]:.4f}/{g[1]:.4f}/{g[2]:.4f}"
            + (f"  경계={float(np.mean(vig)):.4f}" if vig else "")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
