"""v3 숲 시야 골든 내보내기 — 파이썬 숲 시야(env_v2/world.py 모듈 docstring '야생 2단계' 3 의 7), `foliage_chord`·`foliage_blocked`, 12880eb)와 그것을
쓰는 곳 가운데 C++ 에 옮긴 셋 — 사슴의 위협 보임(`_geometry` pvis — 도주 반사 알아챔·감지 기록이 같은 판정), 늑대 표적 고르기(`_step_predators_v3` —
무리 미리 보기 포함), 관측 threat_hidden(`obstacle_obs_values`) — 과 도망 기록 lost_foliage(`_fl_update`·`_fl_close`)를 언리얼 C++ (EcoThreatModel.h
FoliageChord·FoliageBlocked·InputSightBlocked, EcoObservationV3.h ObstacleObsValues, EcoWorldV3.h FObstacleConfig::Foliage·FlightPairOf·FlightUpdate)와
대조할 골든 헤더를 만든다 (10-22). 넷째 쓰는 곳 도망길 COVER 그늘(`flight_route_geometry`)은 C++ 에 도망길이 없어 파이썬 전용이다.

    # herbivore_rl/ 에서 (Anaconda base python, PYTHONUTF8=1). 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_foliage.py
    # 시험용 다른 폴더
    python export_golden_v3_foliage.py --out <폴더>

세계: configs/v3_wild3_obs_mirror.yaml (언리얼 통합 기본의 거울 — 부활 없음, 숲 나무 원판 24·늑대 4·도주 반사·은신처 안전·관측 21) + 숲 시야
{r 3.0, block 2.0, trees = 원판마다 0/1 — 넷째 원판마다 0 이라 나무 표 길도 함께 본다}. 시드는 이 내보내기 전용 탐색 32090~32097 만 쓴다 (판정 시드 밖).

묶음:
  눈길 길이   foliage_chord 사례: 손 사례(비낌·접함·꿰뚫음·끝점 안·둘 다 안·겹친 원 합집합·길이 0·세로 선분·넓은 거르기 경계·문턱과 같은 길이·같은 원 두 번·
              바위 빼기) + 난수 사례(손 원판·거울 숲 원판·덩어리 숲 — 한 눈길에 잎 구간이 64 개 넘는 사례 포함 — 나무 표 켬·끔). 사례마다 길이(double 비트)·
              가림. C++ 은 a → b 와 b → a 를 모두 재서 둘 다 같아야 한다.
  관측        obstacle_obs_values(…, foliage) 사례: 거울 숲 원판 둘레에 사슴·위협을 놓아 줄기 가림·잎만 가림·안 가림이 모두 나오게 — E·N(비트)·가림.
  쌍 장면     `_step_predators_v3` 한 번 (export_golden_v3_flight.py 쌍 장면과 같은 꼴, 숲 시야 켬): 늑대마다 사냥 가능·표적(pred_target), 쌍마다 반경 안·
              반경과 시야각 안·가림(줄기 ∨ 잎)·은신처 표적 제외·잎만 가림(_fl_pred_fol). C++ 은 위협 Step 사본·FlightPairOf.
  도망 기록   `_fl_update` 재료 장면 (짜 맞춘 장면 + 난수 장면, export_golden_v3_flight.py 장면과 같은 꼴): 늑대 재료 비트에 잎만 가림 128 을 더한다.
              틱마다 보고 49 칸 + lost_foliage 3 칸, 사슴 칸 7 + _fl_why_fol.
  기준 루프   거울 세계(사슴 48) 숲 시야 켬 450 스텝을 R1b-F 관측 21 두뇌(ckpt/v3/v3_r1_g995_s3_obs21zero.zip — 내장 R1b + 0 열, 그래서 C++ 은 내장 망
              kBuiltinNet 에 관측 21 세계로 돈다)로 돌린다. 시작 상태는 평가기 일(results/v3/live/ceval.py native_job)과 같고, 세계 난수는 numpy PCG64 의
              날 64 비트(스텝마다 늑대 슬롯 순서의 배회 선회 — 거울 세계의 스텝 안 뽑기는 그것뿐)를 적는다. 스텝마다 상태 지문(아래)·90 스텝마다 기록(잡힘·
              굶음·산, 도망 보고 49 칸 + lost_foliage 3 칸)을 적고, 같은 시작의 숲 시야 끔 판도 적는다 (끔 = 지금 그대로, 언리얼 Policy.V3.Foliage.Off).
              동족 차례 합: 파이썬 World._geometry 는 10-22 부터 동족 무리 중심·분리를 C++ PerceiveKin 과 같은 j 차례 합(`_seq_sum`)으로 더한다(ceval.py
              머리 주석 '파리티'). 그 전에는 행렬곱이라 이 루프만 진단 기하(ceval.seq_kin_geometry — 같은 차례 합)를 붙여 돌렸고, 지금은 world.py 그대로
              돈다 — 루프 데이터는 진단 기하 판과 바이트 단위로 같다(바뀐 것은 이 주석과 헤더 설명 줄뿐).

지문 (스텝마다, 리틀 엔디언 바이트를 이 순서로 이어 sha256 → 앞 8 바이트를 리틀 엔디언 uint64 로): f64 dark·pred_ema · f64 x·y·hx·hy·energy·reserve (칸마다 슬롯
  N 개) · i32 death_cause·wf_mode (같음) · i32 행동 (그 스텝 첫머리에 산 슬롯) · f32 관측 21 (같은 슬롯, 행 우선) · i32 다음 요청 (스텝 끝에 산 ∧ 덮기 < 2
  슬롯) · f64 늑대 x·y·hx·hy (칸마다 M 개) · i32 쿨다운·배부름·표적 슬롯 (−1 없음). 0 번 = 시작 상태 (첫 관측·첫 요청 뒤). ceval.py trace_diff 가 견주는 칸과
  같은 범위다 (죽은 슬롯의 행동·관측은 파이썬만 계속 계산하므로 뺀다).
결정성: 시각·절대 경로를 적지 않는다. 같은 코드·설정이면 바이트 단위로 같은 헤더가 나온다 (tests/test_foliage_golden_v3.py).
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import hashlib
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for _p in (HERE / "results" / "v3" / "live", HERE / "results" / "v3" / "adapt", HERE / "results" / "v3" / "mirror", HERE / "results" / "v3" / "r4",
           HERE / "results" / "v3" / "wild2"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from env_v2 import repertoire as rep  # noqa: E402
from env_v2 import rollout as ro  # noqa: E402
from env_v2.config import load_v2_config  # noqa: E402
from env_v2.features import OPTIONAL_KEYS  # noqa: E402
from env_v2.world import (FL_DROP_COVER, FL_DROP_FOV, FL_DROP_NONE, FL_DROP_OBSTACLE, FL_DROP_RANGE, FL_DROP_STOP, FL_DROP_SWITCH,  # noqa: E402
                          FLIGHT_CAUSES, FLIGHT_HIST_STEPS, PT_STALKER, ST_EXHAUST, ST_POUNCE, ST_ROAM, World, foliage_blocked, foliage_chord,
                          obstacle_inside, obstacle_obs_values)

OBS = HERE / "configs" / "v3_wild3_obs_mirror.yaml"
MODEL = HERE / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip"
DEFAULT_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
HEADER = "FoliageGoldenVectorsV3.h"
FOL_R, FOL_BLOCK = 3.0, 2.0
SEED_CHORD = 32090
SEED_OBS = 32091
SEED_FLIGHT = 32092
SEED_PAIR = 32093
LOOP_SEEDS = (32094, 32095, 32096, 32097)
JUDGE_SEED_RANGES = ((10000, 10020), (10200, 10220), (12160, 12200), (14000, 14040), (15000, 15040), (10300, 10320), (33000, 33200), (34900, 35000))
N_LOOP = 48
LOOP_STEPS = 450
LOOP_EVERY = 90
N_PAIR = 16
PAIR_SCENES = 48
N_FL = 6
FL_TICKS = 300
STATS_LEN = 4 + 3 * len(FLIGHT_CAUSES) + 4 + len(FLIGHT_HIST_STEPS) + 1      # 49 (export_golden_v3_flight.py 와 같은 순서)
ROW_LEN = STATS_LEN + 3                                                          # + lost_foliage n·steps·contact
TRACK_LEN = 8                                                                    # _fl_len·contact·reflex·chased·why·end_now·end_cov + _fl_why_fol
CHECK_LEN = 3 + ROW_LEN                                                          # 잡힘·굶음·산 + 보고


def check_seeds(*seeds) -> None:
    for s in seeds:
        for lo, hi in JUDGE_SEED_RANGES:
            if lo <= int(s) < hi:
                raise SystemExit(f"시드 {s} 는 판정 시드 [{lo}, {hi}) 다 — 골든에 쓰지 않는다")


def d_lit(x) -> str:
    """double 리터럴: 파이썬 repr (다시 읽으면 같은 float64 가 되는 가장 짧은 표기)."""
    x = float(x)
    if not math.isfinite(x):
        raise SystemExit(f"헤더에 유한하지 않은 값: {x}")
    s = repr(x)
    return s if ("." in s or "e" in s) else s + ".0"


def f_lit(x) -> str:
    """float 리터럴 (float32 값을 double 로 적고 f — 같은 float 으로 읽힌다)."""
    return d_lit(float(np.float32(x))) + "f"


def i_lit(x) -> str:
    return str(int(x))


def i64_lit(x) -> str:
    return f"{int(x)}LL"


def u64_lit(x) -> str:
    return f"{int(x)}ULL"


def c_array(ctype: str, name: str, flat, per_line: int, fmt) -> str:
    flat = list(flat)
    if not flat:
        raise SystemExit(f"{name} 가 비었다 — C++ 배열은 크기 0 일 수 없다")
    lines = [f"\tinline constexpr {ctype} {name}[{len(flat)}] = {{"]
    for k in range(0, len(flat), per_line):
        lines.append("\t\t" + ", ".join(fmt(v) for v in flat[k:k + per_line]) + ",")
    lines.append("\t};")
    return "\n".join(lines)


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def tree_mask(k: int) -> list[int]:
    """원판 k 개의 나무 표: 넷째마다 0 (바위로 본다 — 잎 없음), 나머지 1."""
    return [0 if i % 4 == 3 else 1 for i in range(k)]


def mirror_world() -> tuple[np.ndarray, float, float]:
    """거울 숲 원판 (K, 3), 무대 한 변, 몸 반지름."""
    w = World(load_v2_config(OBS).replace(N=4), seeds=[SEED_CHORD])
    if w._ob is None or w._ob["fixed"] is None or not len(w.obstacles):
        raise SystemExit("v3_wild3_obs_mirror.yaml 은 고정 원판(숲 나무)을 켠 세계여야 한다")
    return w.obstacles.copy(), float(w.size), float(w._ob["body_r"])


def fol_cfg(cfg, on: bool, trees):
    return _with(cfg, obstacles=dict(foliage=dict(enabled=bool(on), r=FOL_R, block=FOL_BLOCK, trees=list(trees))))


# --------------------------------------------------------------------- #
# 눈길 길이 사례
# --------------------------------------------------------------------- #


def disc_sets(rng: np.random.Generator) -> list[tuple[str, np.ndarray, list[int]]]:
    """(이름, 원판 (K, 3), 나무 표). 0 손 원판, 1 거울 숲 24, 2 덩어리 숲 160 (10 × 10 단위), 3 난수 숲 60 (40 × 40)."""
    hand = np.array([[0.0, 0.0, 0.1], [5.0, 0.0, 0.1], [5.5, 0.5, 0.12], [20.0, 20.0, 0.1], [-3.0, 10.0, 0.1], [0.0, 0.0, 0.2],
                     [12.0, -4.0, 0.3], [14.0, -4.0, 0.3]])
    hand_t = [1, 1, 1, 1, 1, 1, 0, 1]
    mir = mirror_world()[0]
    clump = np.c_[rng.uniform(30.0, 40.0, (160, 2)), rng.uniform(0.05, 0.15, 160)]
    forest = np.c_[rng.uniform(0.0, 40.0, (60, 2)), rng.uniform(0.05, 0.75, 60)]
    return [("손", hand, hand_t), ("거울 숲", mir, tree_mask(len(mir))), ("덩어리 숲", clump, tree_mask(len(clump))),
            ("난수 숲", forest, [int(rng.random() < 0.8) for _ in range(len(forest))])]


def chord_cases(sets, rng: np.random.Generator) -> list[dict]:
    """사례 (묶음, 나무 표 씀, r, block, a, b, 이름)."""
    cs = []

    def add(s, masked, r, block, a, b, name):
        cs.append(dict(set=s, masked=int(masked), r=float(r), block=float(block), a=(float(a[0]), float(a[1])), b=(float(b[0]), float(b[1])), name=name))

    # 손 사례 (묶음 0: 원 (0,0)·(5,0)·(5.5,0.5)·(20,20)·(−3,10)·(0,0) 두 번째·(12,−4) 바위·(14,−4))
    add(0, 1, 3.0, 2.0, (-30.0, -30.0), (-25.0, -28.0), "비낌 (먼 눈길)")
    add(0, 1, 3.0, 2.0, (-5.0, 3.0), (1.0, 3.0), "접함 (Δ = 0 → 0)")
    add(0, 1, 3.0, 2.0, (-6.0, 1.0), (1.0, -1.5), "꿰뚫음 (원 하나)")
    add(0, 1, 3.0, 2.0, (0.5, 0.5), (-7.0, 4.0), "끝점 a 가 원 안")
    add(0, 1, 3.0, 2.0, (-7.0, 4.0), (0.5, 0.5), "끝점 b 가 원 안")
    add(0, 1, 3.0, 2.0, (0.5, 0.5), (-1.0, -1.0), "두 끝점 모두 원 안 (길이 = 눈길)")
    add(0, 1, 3.0, 2.0, (-4.0, 0.2), (9.0, 0.2), "겹친 원 합집합 (같은 원 두 번 포함)")
    add(0, 1, 3.0, 2.0, (0.2, 0.3), (0.2, 0.3), "길이 0")
    add(0, 1, 3.0, 2.0, (0.5, 5.0), (0.5, -5.0), "세로 선분 (x 같음 → y 순서)")
    add(0, 1, 3.0, 2.0, (-6.0, 0.0), (-3.0, 0.0), "넓은 거르기 경계 (중심 = 상자 끝, 원에 끝점만 닿음)")
    add(0, 1, 3.0, 2.0, (-1.0, 0.0), (1.0, 0.0), "문턱과 같은 길이 (2.0 ≥ 2.0 가림)")
    add(0, 1, 3.0, 2.0001, (-1.0, 0.0), (1.0, 0.0), "문턱보다 조금 짧음")
    add(0, 1, 3.0, 2.0, (10.0, -4.0), (12.0, -4.0), "바위(나무 표 0) — 잎 없음")
    add(0, 0, 3.0, 2.0, (10.0, -4.0), (12.0, -4.0), "같은 원판, 나무 표 안 씀 — 모두 나무")
    add(0, 1, 1.5, 1.0, (-2.0, 0.1), (7.0, 0.3), "작은 잎 원 1.5·문턱 1.0")
    add(0, 1, 3.0, 2.0, (2.0, 0.0), (3.0, 0.0), "두 원이 겹친 구간 안의 짧은 눈길")
    add(0, 1, 3.0, 2.0, (17.0, 20.0), (23.0, 20.0), "원 지름 (길이 = 6)")
    add(0, 1, 3.0, 2.0, (-3.0, 7.0), (-3.0, 13.0), "세로 지름")
    # 난수 사례
    k = 0
    for s, (_, d, _) in enumerate(sets):
        lo, hi = d[:, :2].min(0) - 4.0, d[:, :2].max(0) + 4.0
        n = 160 if s != 2 else 60
        for _ in range(n):
            a = rng.uniform(lo, hi)
            u = rng.random()
            if u < 0.4:
                b = a + rng.normal(0.0, 4.0, 2)              # 짧은 눈길
            elif u < 0.8:
                b = rng.uniform(lo, hi)                      # 긴 눈길
            else:
                c = d[int(rng.integers(0, len(d))), :2]      # 원판을 꿰는 눈길
                b = 2.0 * c - a + rng.normal(0.0, 0.5, 2)
            r = float(rng.choice([1.5, 3.0, 3.0, 4.5]))
            block = float(rng.choice([1.0, 2.0, 2.0, 3.5]))
            add(s, rng.random() < 0.7, r, block, a, b, f"난수 {k}")
            k += 1
    # 덩어리 숲을 길게 가로지르는 눈길 (한 눈길에 잎 구간 64 개 넘음 — C++ 차례 고르기 길)
    for j in range(6):
        y = 30.0 + 2.0 * j
        add(2, j % 2, 3.0, 2.0, (25.0, y), (45.0, 70.0 - y), f"덩어리 숲 가로지르기 {j}")
    return cs


def chord_eval(sets, cs) -> None:
    """사례마다 파이썬 값·가림·구간 수 (a ↔ b 비트 동일 확인)."""
    for c in cs:
        d = sets[c["set"]][1]
        t = np.asarray(sets[c["set"]][2], dtype=bool) if c["masked"] else np.ones(len(d), dtype=bool)
        cen = d[t, :2]
        a, b = np.array([c["a"]]), np.array([c["b"]])
        v = foliage_chord(a, b, cen, c["r"])
        v2 = foliage_chord(b, a, cen, c["r"])
        if v.tobytes() != v2.tobytes():
            raise SystemExit(f"파이썬 foliage_chord 가 a ↔ b 에 비트 단위로 같지 않다: {c['name']}")
        c["want"] = float(v[0])
        c["blocked"] = int(bool(foliage_blocked(a, b, cen, c["r"], c["block"])[0]))
        if bool(c["blocked"]) != (c["want"] >= c["block"]):
            raise SystemExit("foliage_blocked ≠ foliage_chord ≥ block")
        c["spans"] = _span_count(c["a"], c["b"], cen, c["r"])


def _span_count(a, b, cen, r) -> int:
    """잎 구간 수 (C++ 쌓아 두기 칸 64 를 넘는 사례가 있는지 보려고 — 값에는 쓰지 않는다)."""
    (ax, ay), (bx, by) = a, b
    if ax > bx or (ax == bx and ay > by):
        ax, ay, bx, by = bx, by, ax, ay
    dx, dy = bx - ax, by - ay
    dd = dx * dx + dy * dy
    n = 0
    for cx, cy in cen:
        if not (ax - r <= cx <= bx + r and min(ay, by) - r <= cy <= max(ay, by) + r):
            continue
        fx, fy = ax - cx, ay - cy
        beta = fx * dx + fy * dy
        gam = fx * fx + fy * fy - r * r
        dsc = beta * beta - dd * gam
        if dd > 0.0 and dsc > 0.0:
            s = math.sqrt(dsc)
            if min((-beta + s) / dd, 1.0) > max((-beta - s) / dd, 0.0):
                n += 1
    return n


# --------------------------------------------------------------------- #
# 관측 threat_hidden 사례
# --------------------------------------------------------------------- #


def obs_cases(disc: np.ndarray, trees: list[int], rng: np.random.Generator, size: float, body_r: float) -> dict:
    """거울 숲 원판 둘레: 사슴을 원판 중심에서 1~4.5 단위(잎 안·밖), 위협을 그 반대쪽 3~16 단위에 (가끔 무작위·위협 모름·원판 위)."""
    n = 192
    p = np.zeros((n, 2))
    th = np.zeros((n, 2))
    for i in range(n):
        k = int(rng.integers(0, len(disc)))
        c = disc[k, :2]
        a = rng.uniform(0.0, 2.0 * math.pi)
        u = np.array([math.cos(a), math.sin(a)])
        p[i] = c + u * rng.uniform(disc[k, 2] + body_r + 0.05, 4.5)
        if rng.random() < 0.8:
            th[i] = c - u * rng.uniform(1.0, 14.0) + rng.normal(0.0, 0.8, 2)
        else:
            th[i] = rng.uniform(0.0, size, 2)
    p = np.clip(p, 0.0, size)
    th = np.clip(th, 0.0, size)
    ang = rng.uniform(0.0, 2.0 * math.pi, n)
    head = np.stack([np.cos(ang), np.sin(ang)], 1)
    seen = rng.random(n) < 0.85
    away = p - th
    nrm = np.linalg.norm(away, axis=1, keepdims=True)
    away = np.where(seen[:, None], away / np.maximum(nrm, 1e-9), 0.0)
    cen = disc[np.asarray(trees, dtype=bool), :2]
    e, near, hid = obstacle_obs_values(p, head, seen, away, th, disc, body_r, size, True, (cen, FOL_R, FOL_BLOCK))
    e0, near0, hid0 = obstacle_obs_values(p, head, seen, away, th, disc, body_r, size, True)
    if e.tobytes() != e0.tobytes() or near.tobytes() != near0.tobytes():
        raise SystemExit("숲 시야가 E·N 을 바꿨다 — 가림만 바꿔야 한다")
    return dict(p=p, head=head, seen=seen, away=away, th=th, e=e, near=near, hid=hid, hid0=hid0)


# --------------------------------------------------------------------- #
# 쌍 장면 (`_step_predators_v3` 한 번 — export_golden_v3_flight.py 쌍 장면과 같은 꼴, 숲 시야 켬)
# --------------------------------------------------------------------- #


def pair_scenes(trees: list[int]):
    w = World(fol_cfg(load_v2_config(OBS), True, trees).replace(N=N_PAIR), seeds=[SEED_PAIR])
    if w._zc is not None or w._sd is not None or w._zt is not None or w._pred_ranged_v1.any() or w.M != w.M_base:
        raise SystemExit("쌍 장면은 추격 고정·노려보기·지형·원거리형·플레이어가 없어야 한다(C++ 위협 모델에 없다)")
    if not (w._zs and w._zs["untargetable"] and w._zs["player_too"]) or w._ob is None or not w._ob["block_sight"] or w._ob["foliage"] is None:
        raise SystemExit("쌍 장면은 은신처 표적 제외·원판 눈길 가림·숲 시야를 켠 세계여야 한다")
    w.track_flight = True
    w._fl_reset()
    rng = np.random.default_rng(SEED_PAIR + 1)
    S, M, N = w.size, w.M, w.N
    rp, disc, body = w._rp, w.obstacles, w._ob["body_r"]
    tr = np.asarray(trees, dtype=bool)
    sights = (1.0, w._wx_sight if w._wx is not None else 1.0, 0.7)
    out = []
    for s in range(PAIR_SCENES):
        q = np.zeros((M, 2))
        for m in range(M):
            for _ in range(400):
                c = rng.uniform(0.0, S, 2)
                if not w._rz_inside_disc(c[None, :])[0] and not obstacle_inside(c[None, :], disc, body)[0]:
                    break
            q[m] = c
        ang = rng.uniform(0, 2 * np.pi, M)
        head = np.stack([np.cos(ang), np.sin(ang)], 1)
        cd = np.zeros(M, dtype=np.int64)
        sat = np.zeros(M, dtype=np.int64)
        st = np.full(M, ST_ROAM, dtype=np.int8)
        left = np.zeros(M, dtype=np.int64)
        asleep = np.zeros(M, dtype=bool)
        for m in range(M):
            u = rng.random()
            if u < 0.06:
                cd[m] = int(rng.integers(1, 39))
            elif u < 0.10:
                sat[m] = int(rng.integers(1, 451))
            elif u < 0.14:
                asleep[m] = True
            elif u < 0.22 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_POUNCE, int(rng.integers(0, 13))
            elif u < 0.26 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_EXHAUST, int(rng.integers(1, 31))
        # 사슴: 늑대 앞쪽에서 나무 원판 뒤 (잎 안·밖 — 잎만 가림이 나오게), 은신처 둘레, 무작위
        p = rng.uniform(0.0, S, (N, 2))
        for i in range(N):
            m = int(rng.integers(0, M))
            u = rng.random()
            if u < 0.55:
                k = int(rng.choice(np.flatnonzero(tr))) if rng.random() < 0.85 else int(rng.integers(0, len(disc)))
                v = disc[k, :2] - q[m]
                nv = max(float(np.linalg.norm(v)), 1e-9)
                p[i] = disc[k, :2] + v / nv * rng.uniform(disc[k, 2] + body + 0.05, 5.0) + rng.normal(0.0, 0.6, 2)
            elif u < 0.75:
                a = math.atan2(head[m, 1], head[m, 0]) + rng.normal(0.0, 1.2)
                p[i] = q[m] + rng.uniform(1.0, 20.0) * np.array([math.cos(a), math.sin(a)])
            elif u < 0.88:
                k = int(rng.integers(0, len(w.cov_r)))
                a = rng.uniform(0.0, 2.0 * math.pi)
                p[i] = w.cov_c[k] + rng.uniform(0.0, w.cov_r[k] + 1.5) * np.array([math.cos(a), math.sin(a)])
        p = np.clip(p, 0.0, S)
        beh = rng.choice([rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP], N, p=[0.4, 0.2, 0.2, 0.1, 0.1]).astype(np.int8)
        arrived = (beh == rep.HIDE) & (rng.random(N) < 0.6)
        crouch = (beh == rep.HIDE) & arrived
        sight = float(sights[s % len(sights)])
        w.pos = p.copy()
        w._pack_p0 = p.copy()
        w._rs.behavior[:] = beh
        w._rs.arrived[:] = arrived
        w._rep_still = (beh == rep.FREEZE) | (beh == rep.SLEEP) | crouch
        w._rep_cover = rep.cover_mult(rp, beh, crouch)
        w.alive = np.ones(N, dtype=bool)
        w.pred_pos, w.pred_head = q.copy(), head.copy()
        w.pred_cd, w.pred_sat = cd.copy(), sat.copy()
        w.stalk_state, w.stalk_left = st.copy(), left.copy()
        w.pred_asleep = asleep.copy()
        w._pred_speed_mult = np.where(asleep, 0.0, 1.0)
        w.dark = 0.0
        w._zn_hunt = np.zeros(M, dtype=bool)
        w._hunt_on = np.zeros(M, dtype=bool)
        if w._wx is not None:
            w._wx_sight = sight
            w._wx_view = w.cfg.pred_view_r * sight
        elif sight != 1.0:
            raise SystemExit("날씨를 끈 세계는 시야 배수 1 만")
        in_cov = w._in_cover(w.pos)
        w._fl_pred = None
        w._fl_pred_fol = None
        w._step_predators_v3()
        fp = w._fl_pred
        fo = w._fl_pred_fol
        if fp is None or fp[1].shape != (M, N) or fo is None or fo.shape != (M, N):
            raise SystemExit("쌍 장면: _fl_pred·_fl_pred_fol 이 없다")
        out.append(dict(q=q, head=head, cd=cd, sat=sat, st=st, left=left, asleep=asleep, p=p, beh=beh, arrived=arrived, in_cov=in_cov,
                        sight=sight, hunt=fp[0].copy(), rng=fp[1].copy(), vis0=fp[2].copy(), blk=fp[3].copy(), cov=fp[4].copy(), fol=fo.copy(),
                        target=np.asarray(w.pred_target, dtype=np.int64).copy()))
    consts = dict(size=S, M=M, N=N, discs=disc.copy(), kinds=w.pred_type.copy(), eat_cd=int(w.cfg.pred_eat_cd), sat_steps=int(w._ws_sat_steps),
                  pred_speed_mult=float(w.pred_speed_mult), view_r=float(w.cfg.pred_view_r), fov_cos=float(w.cfg.pred_fov_cos), body=float(body),
                  c_still=float(rp["c_still"]), cover_mult=(float(rp["cover_mult_crouch"]), float(rp["cover_mult_graze"]), float(rp["cover_mult_sleep"]),
                                                             float(rp["cover_mult_other"])))
    return out, consts


# --------------------------------------------------------------------- #
# 도망 기록 장면 (`_fl_update` 재료 — lost_foliage)
# --------------------------------------------------------------------- #


def stats_row(f: dict) -> list[int]:
    out = [f["started"], f["live_steps"], f["flee_steps"], f["reflex_steps"]]
    for key in ("n", "steps", "contact"):
        out += [f[key][c] for c in FLIGHT_CAUSES]
    out += [f["own_n"], f["own_steps"], f["own_contact"], f["shelter_end"]]
    out += list(f["hist"])
    lf = f.get("lost_foliage")
    if lf is None:
        raise SystemExit("숲 시야 켬 세계의 flight_stats 에 lost_foliage 가 없다")
    out += [lf["n"], lf["steps"], lf["contact"]]
    if len(out) != ROW_LEN:
        raise SystemExit(f"보고 칸 수 {len(out)} != {ROW_LEN}")
    return [int(v) for v in out]


def track_rows(w: World) -> list[int]:
    out = []
    for i in range(w.N):
        out += [int(w._fl_len[i]), int(w._fl_contact[i]), int(w._fl_reflex[i]), int(bool(w._fl_chased[i])), int(w._fl_why[i]),
                int(bool(w._fl_end_now[i])), int(bool(w._fl_end_cov[i])), int(bool(w._fl_why_fol[i]))]
    return out


class FlScene:
    """export_golden_v3_flight.py Scene 과 같은 꼴 (숲 시야 켬 세계 — `_fl_update` 가 잎 놓침을 센다). 재료를 짜 맞춰 `_fl_update` 를 부르고 적는다."""

    def __init__(self, name: str, n: int, trees):
        self.name = name
        self.w = World(fol_cfg(load_v2_config(OBS), True, trees).replace(N=n), seeds=[SEED_FLIGHT])
        if self.w._ob["foliage"] is None or self.w._wf is None or self.w._wf.get("route_fixed") is not None:
            raise SystemExit("도망 기록 장면: 숲 시야·wild_flight 를 켜고 route_fixed 를 끈 세계여야 한다")
        self.w.track_flight = True
        self.w._fl_reset()
        self.deer, self.wolf_bits, self.wolf_tgt, self.wolf_prev = [], [], [], []
        self.stats, self.tracks, self.prev_after = [], [], []

    def tick(self, flee, reflex, done, caught, in_cov, tgt, idle, pred, fol):
        """재료 한 스텝: 마스크·행렬을 그대로 넣는다 (pred = (사냥 가능, 반경 안, 반경과 시야각 안, 가림, 은신처), fol = 잎만 가림 (M, N))."""
        w = self.w
        N, M = w.N, w.M
        flee, reflex, done, caught, in_cov = (np.asarray(x, dtype=bool) for x in (flee, reflex, done, caught, in_cov))
        tgt = np.asarray(tgt, dtype=np.int64)
        w.pred_target = tgt.copy()
        w.pred_cd = np.where(np.asarray(idle, dtype=bool), 30, 0).astype(np.int64)
        if getattr(w, "pred_asleep", None) is not None:
            w.pred_asleep = np.zeros(M, dtype=bool)
        if getattr(w, "pred_sat", None) is not None:
            w.pred_sat = np.zeros(M, dtype=np.int64)
        w._fl_pred = pred
        w._fl_pred_fol = fol
        live = np.ones(N, dtype=bool) & ~done
        alive0 = live | done
        self.deer.append([int(flee[i]) | 2 * int(reflex[i]) | 4 * int(done[i]) | 8 * int(caught[i]) | 16 * int(in_cov[i]) | 32 * int(alive0[i])
                          for i in range(N)])
        hunt_end = w._wf_hunting()
        tp = w._fl_tgt.copy() if w._fl_tgt.shape == (M,) else np.full(M, -1, dtype=np.int64)
        bits = []
        for m in range(M):
            b = int(bool(hunt_end[m])) | 2 * int(bool(pred[0][m])) | 4
            i = int(tp[m])
            rng_, vis0, blk, cov, fo = True, True, False, False, False
            if 0 <= i < N:
                rng_, vis0, blk, cov, fo = bool(pred[1][m, i]), bool(pred[2][m, i]), bool(pred[3][m, i]), bool(pred[4][m, i]), bool(fol[m, i])
            b |= 8 * int(rng_) | 16 * int(vis0) | 32 * int(blk) | 64 * int(cov) | 128 * int(fo)
            bits.append(b)
        self.wolf_bits.append(bits)
        self.wolf_tgt.append([int(v) for v in tgt])
        self.wolf_prev.append([int(v) if 0 <= v < N else -1 for v in tp])
        w._fl_update(flee, reflex, done, caught, live, in_cov)
        self.stats.append(stats_row(w.flight_stats()))
        self.tracks.append(track_rows(w))
        self.prev_after.append([int(v) if 0 <= v < N else -1 for v in w._fl_tgt])


def fl_scenes(trees) -> list[FlScene]:
    # 짜 맞춘 장면: 잎만 가린 놓침 → 원판(잎) / 같은 스텝 줄기·잎 함께 → 원판(줄기) / 잎 놓침 뒤 줄기 놓침 → 줄기 / 잎 놓침 뒤 은신처 놓침(큰 번호) → 은신처 /
    #               잎 놓침 뒤 다시 쫓김·끝 스텝에도 표적 → 붙잡힘 / 잎 놓침 뒤 FLEE 중 잡힘 → 잡힘 (lost_foliage 아님)
    sc = FlScene("짜 맞춘 잎 놓침", N_FL, trees)
    M, N = sc.w.M, sc.w.N
    yes = np.ones((M, N), dtype=bool)
    no = np.zeros((M, N), dtype=bool)
    ones = np.ones(M, dtype=bool)
    z = np.zeros(N, dtype=bool)

    def mk(ix):
        a = np.zeros(N, dtype=bool)
        a[list(ix)] = True
        return a

    def t(**pairs):
        return [pairs.get(f"w{m}", -1) for m in range(M)]

    def P(blk=None, cov=None, rng_=None):
        return (ones.copy(), yes.copy() if rng_ is None else rng_, yes.copy() if rng_ is None else rng_.copy(), no.copy() if blk is None else blk,
                no.copy() if cov is None else cov)

    blk = no.copy()
    blk[0, 0] = blk[1, 1] = blk[2, 1] = blk[0, 2] = True
    fol = no.copy()
    fol[0, 0] = fol[1, 1] = fol[0, 2] = True             # 사슴 1: 늑대 1 은 잎만·늑대 2 는 줄기 → 줄기
    sc.tick(mk([0, 1, 2, 3]), z, z, z, z, t(w0=0, w1=1, w2=1, w3=3), np.zeros(M, dtype=bool), P(), no.copy())
    sc.tick(mk([0, 1, 2, 3]), z, z, z, z, t(w0=2, w3=3), np.zeros(M, dtype=bool), P(blk=blk), fol)
    sc.tick(mk([2, 3]), z, z, z, z, t(w3=3), np.zeros(M, dtype=bool), P(), no.copy())      # 0·1 끝 (원판: 0 = 잎, 1 = 줄기)
    blk2 = no.copy()
    blk2[0, 2] = True
    sc.tick(mk([2, 3]), z, z, z, z, t(w3=3), np.zeros(M, dtype=bool), P(blk=blk2), no.copy())   # 2: 지난 표적 늑대 0 없음 — 놓침 없음
    sc.tick(mk([2, 3, 4]), z, z, z, z, t(w0=4, w3=3), np.zeros(M, dtype=bool), P(), no.copy())
    blk3 = no.copy()
    blk3[0, 4] = True
    fol3 = blk3.copy()
    sc.tick(mk([2, 3, 4]), z, z, z, z, t(w3=4), np.zeros(M, dtype=bool), P(blk=blk3), fol3)      # 4: 잎 놓침, 3: 늑대 3 이 바꿈
    cov4 = no.copy()
    cov4[3, 4] = True
    sc.tick(mk([2, 4]), z, z, z, z, t(), np.zeros(M, dtype=bool), P(cov=cov4), no.copy())        # 4: 은신처 놓침 (큰 번호) — 잎 아님
    sc.tick(mk([4, 5]), z, z, z, z, t(w1=5), np.zeros(M, dtype=bool), P(), no.copy())
    blk5 = no.copy()
    blk5[1, 5] = True
    sc.tick(mk([4, 5]), z, z, z, z, t(), np.zeros(M, dtype=bool), P(blk=blk5), blk5.copy())     # 5: 잎 놓침
    sc.tick(mk([5]), z, z, z, z, t(w2=5), np.zeros(M, dtype=bool), P(), no.copy())              # 5: 다시 쫓김
    sc.tick(z, z, z, z, z, t(), np.zeros(M, dtype=bool), P(), no.copy())                         # 5: 끝 (붙잡힘이 아니라 지난 FLEE 끝 표적 → held)
    sc.tick(mk([1]), z, z, z, z, t(w0=1), np.zeros(M, dtype=bool), P(), no.copy())
    blk6 = no.copy()
    blk6[0, 1] = True
    sc.tick(mk([1]), z, z, z, z, t(), np.zeros(M, dtype=bool), P(blk=blk6), blk6.copy())       # 1: 잎 놓침
    sc.tick(mk([1]), z, mk([1]), mk([1]), z, t(), np.zeros(M, dtype=bool), P(), no.copy())      # 1: FLEE 중 잡힘 — lost_foliage 아님
    sc.tick(z, z, z, z, z, t(), np.zeros(M, dtype=bool), P(), no.copy())
    # 난수 장면 (export_golden_v3_flight.py scene_random 과 같은 꼴 + 잎만 가림 ⊆ 가림)
    rs = FlScene("난수 장면", N_FL, trees)
    rng = np.random.default_rng(SEED_FLIGHT + 1)
    M, N = rs.w.M, rs.w.N
    flee = np.zeros(N, dtype=bool)
    for _ in range(FL_TICKS):
        flip = rng.random(N) < 0.25
        flee = np.where(flip, ~flee, flee)
        reflex = flee & (rng.random(N) < 0.6)
        done = rng.random(N) < 0.03
        caught = done & (rng.random(N) < 0.7)
        in_cov = rng.random(N) < 0.2
        focus = int(rng.integers(0, N))
        tgt = np.where(rng.random(M) < 0.5, focus, rng.integers(-1, N, M))
        idle = rng.random(M) < 0.15
        hunt = rng.random(M) < 0.9
        rng_ = rng.random((M, N)) < 0.8
        vis0 = rng_ & (rng.random((M, N)) < 0.8)
        blk = vis0 & (rng.random((M, N)) < 0.35)
        cov = rng.random((M, N)) < 0.15
        fol = blk & (rng.random((M, N)) < 0.6)
        rs.tick(flee.copy(), reflex, done, caught, in_cov, tgt, idle, (hunt, rng_, vis0, blk, cov), fol)
        flee = flee & ~done
    return [sc, rs]


# --------------------------------------------------------------------- #
# 기준 루프 (거울 세계 숲 시야 켬·끔 — world.py 그대로, 동족 합은 C++ 과 같은 j 차례)
# --------------------------------------------------------------------- #


def step_hash(w: World, alive0: np.ndarray, req: np.ndarray, tgt: np.ndarray | None = None) -> int:
    """지문 (모듈 docstring '지문'). tgt = 늑대 표적 덮기 (시작 지문은 −1 — 아직 위협 스텝이 없다)."""
    N = w.N
    cause = np.asarray(w.death_cause).astype(np.int64)
    keep = np.asarray(w.wf_mode).astype(np.int64)
    reserve = w.reserve if w._wr is not None else np.zeros(N)
    obs = np.asarray(w._obs, dtype=np.float32)
    if obs.shape != (N, 21):
        raise SystemExit(f"관측 칸 수 {obs.shape} — 관측 21 세계여야 한다")
    keep_ok = (cause == 0) & (keep < 2)
    b = bytearray()
    b += np.asarray([w.dark, w.pred_ema], dtype="<f8").tobytes()
    for a in (w.pos[:, 0], w.pos[:, 1], w.head[:, 0], w.head[:, 1], w.energy, reserve):
        b += np.ascontiguousarray(a, dtype="<f8").tobytes()
    b += cause.astype("<i4").tobytes() + keep.astype("<i4").tobytes()
    b += np.asarray(w._rs.behavior)[alive0].astype("<i4").tobytes()
    b += np.ascontiguousarray(obs[alive0], dtype="<f4").tobytes()
    b += np.asarray(req).reshape(-1)[keep_ok].astype("<i4").tobytes()
    for a in (w.pred_pos[:, 0], w.pred_pos[:, 1], w.pred_head[:, 0], w.pred_head[:, 1]):
        b += np.ascontiguousarray(a, dtype="<f8").tobytes()
    tgt = np.asarray(getattr(w, "pred_target", np.full(w.M, -1)) if tgt is None else tgt, dtype=np.int64)
    for a in (w.pred_cd, getattr(w, "pred_sat", np.zeros(w.M)), tgt):
        b += np.asarray(a).astype("<i4").tobytes()
    return int.from_bytes(hashlib.sha256(bytes(b)).digest()[:8], "little")


def check_row(w: World) -> list[int]:
    cause = np.asarray(w.death_cause)
    return [int(np.count_nonzero(cause == 1)), int(np.count_nonzero(cause == 2)), int(np.count_nonzero(cause == 0))] + stats_row_any(w.flight_stats())


def stats_row_any(f: dict) -> list[int]:
    """보고 49 칸 + lost_foliage 3 칸 (끈 세계는 0 0 0 — C++ 도 늘 0 이다)."""
    out = [f["started"], f["live_steps"], f["flee_steps"], f["reflex_steps"]]
    for key in ("n", "steps", "contact"):
        out += [f[key][c] for c in FLIGHT_CAUSES]
    out += [f["own_n"], f["own_steps"], f["own_contact"], f["shelter_end"]] + list(f["hist"])
    lf = f.get("lost_foliage", dict(n=0, steps=0, contact=0))
    out += [lf["n"], lf["steps"], lf["contact"]]
    return [int(v) for v in out]


def loop_world(seed: int, on: bool, trees):
    import ceval

    cfg = fol_cfg(load_v2_config(OBS), on, trees).replace(N=N_LOOP)
    w = World(cfg, seeds=[seed])
    if w.alive is None or w._wf is None or not len(w.obstacles) or w._zs is None or (w._ob["foliage"] is not None) != on:
        raise SystemExit("기준 루프 세계는 부활 없음·도주 반사·원판·은신처 안전·숲 시야(켬 판)여야 한다")
    w.track_flight = True
    job = ceval.native_job(dict(seed=seed, region="golden", steps=LOOP_STEPS), 0, world=w)
    g = np.random.Generator(np.random.PCG64())
    g.bit_generator.state = w.rng.bit_generator.state
    raw = [int(x) for x in g.bit_generator.random_raw(LOOP_STEPS * w.M)]
    pol = ro.build_policy({"kind": "rep_learned", "path": str(MODEL)}, int(seed))
    ro.forward_bind(pol, w)
    a = np.asarray(pol(w.observe()), dtype=np.float64)
    hashes = [step_hash(w, np.ones(w.N, dtype=bool), a, np.full(w.M, -1))]
    checks = []
    for t in range(1, LOOP_STEPS + 1):
        alive0 = np.asarray(w.death_cause) == 0
        w.step(a)
        a = np.asarray(pol(w.observe()), dtype=np.float64)
        hashes.append(step_hash(w, alive0, a))
        if t % LOOP_EVERY == 0:
            checks.append(check_row(w))
    # 세계 난수: 스텝 안 뽑기 = 스텝마다 늑대 M 개 (끝 상태가 날 수열 끝과 같아야 C++ 이 같은 선회를 받는다)
    if w.rng.bit_generator.state["state"] != g.bit_generator.state["state"]:
        raise SystemExit("기준 루프: 세계 난수가 스텝마다 늑대 M 개 말고도 뽑혔다 — 날 수열로 옮길 수 없다")
    return dict(w=w, job=job, raw=raw, hashes=hashes, checks=checks, final=w.flight_stats())


def pick_loop(trees):
    """잎 놓침(lost_foliage)과 잡힘이 있고 숲 시야 켬·끔 궤적이 갈리는 첫 시드."""
    for seed in LOOP_SEEDS:
        try:
            on = loop_world(seed, True, trees)
        except ValueError as e:                     # world_block 거부 (예: 야행성 늑대) — 다음 시드
            print(f"  시드 {seed}: {e}")
            continue
        lf = on["final"]["lost_foliage"]
        caught = int(np.count_nonzero(np.asarray(on["w"].death_cause) == 1))
        print(f"  시드 {seed}: 잎 놓침 {lf['n']} · 원판 놓침 {on['final']['n']['obstacle']} · 잡힘 {caught} · 시작 도망 {on['final']['started']}")
        if lf["n"] > 0 and caught > 0:
            off = loop_world(seed, False, trees)
            jo, jf = dict(on["job"]), dict(off["job"])
            for j in (jo, jf):
                j["world"] = {k: (dict(v) if isinstance(v, dict) else v) for k, v in j["world"].items()}
                for k in ("foliage", "foliage_r", "foliage_block"):
                    j["world"]["obstacle_rules"].pop(k, None)
                j.pop("foliage_trees", None)
            if jo != jf or on["raw"] != off["raw"]:
                raise SystemExit("숲 시야 켬·끔의 시작 상태가 다르다 (숲 시야만 달라야 한다)")
            div = next((k for k, (x, y) in enumerate(zip(on["hashes"], off["hashes"])) if x != y), None)
            if div is None:
                raise SystemExit(f"시드 {seed}: 숲 시야 켬·끔 궤적이 같다 — 숲 시야가 걸리지 않았다")
            return seed, on, off, div
    raise SystemExit(f"시드 {LOOP_SEEDS} 가운데 잎 놓침·잡힘이 있는 기준 루프가 없다")


# 세계 설정 (ceval.world_block — 스냅숏 지역 world 블록 꼴) → C++ FWorldConfig 칸 (EcoV3Eval.cpp ConfigOf 와 같은 대응). 형 d·i·u64·b·weather
CFG_TOP = (("world_size", "C.WorldSize", "d"), ("seed", "C.Seed", "i64"), ("rng_stream", "C.RngStream", "u64"),
           ("num_herbivores", "C.NumHerbivores", "i"), ("num_stalkers", "C.NumStalkers", "i"), ("num_chasers", "C.NumChasers", "i"),
           ("num_ranged", "C.NumRanged", "i"), ("num_nocturnal", "C.NumNocturnal", "i"), ("player_proxy", "C.bPlayerProxy", "b"),
           ("pred_speed_mult", "C.PredSpeedMult", "d"), ("pred_eat_cd", "C.PredEatCdOverride", "i"), ("eat_in_place", "C.bEatInPlace", "b"),
           ("realism_night", "C.bRealismNight", "b"), ("respawn_dead", "C.bRespawnDead", "b"), ("pred_ema_denominator", "C.PredEmaDenominator", "i"),
           ("day_period", "C.DayPeriod", "i"), ("day_offset", "C.DayOffset", "i"), ("twilight_steps", "C.TwilightSteps", "i"),
           ("shelter_safe", "C.bShelterSafe", "b"), ("shelter_wolf_margin", "C.ShelterWolfMargin", "d"), ("protected_refuges", "C.bProtectedRefuges", "b"))
CFG_BLOCKS = {
    "food_rules": (("cell", "C.FoodCell", "d"), ("patch_blur", "C.FoodPatchBlur", "i"), ("patch_threshold", "C.FoodPatchThreshold", "d"),
                   ("grad_blur", "C.FoodGradBlur", "i"), ("regen_base", "C.FoodRegenBase", "d"), ("regen_mult", "C.FoodRegenMult", "d"),
                   ("cover_regen_mult", "C.FoodCoverRegenMult", "d")),
    "wild_flight": (("enabled", "C.WildFlight.bEnabled", "b"), ("alert_r", "C.WildFlight.AlertR", "d"), ("flight_r", "C.WildFlight.FlightR", "d"),
                    ("safe_r", "C.WildFlight.SafeR", "d"), ("approach", "C.WildFlight.Approach", "d"), ("alert_w", "C.WildFlight.AlertW", "d"),
                    ("rest_alert", "C.WildFlight.bRestAlert", "b"), ("shelter_cos", "C.WildFlight.ShelterCos", "d"),
                    ("shelter_r", "C.WildFlight.ShelterR", "d"), ("crouch", "C.WildFlight.bCrouch", "b"), ("wall_margin", "C.WildFlight.WallMargin", "d"),
                    ("hold_awake", "C.WildFlight.bHoldAwake", "b"), ("edge_r", "C.WildFlight.EdgeR", "d")),
    "wild_reserve": (("enabled", "C.WildReserve.bEnabled", "b"), ("reserve_days", "C.WildReserve.ReserveDays", "d"), ("init", "C.WildReserve.Init", "d"),
                     ("refill_e", "C.WildReserve.RefillE", "d"), ("refill_frac", "C.WildReserve.RefillFrac", "d"), ("weak_e", "C.WildReserve.WeakE", "d"),
                     ("weak_speed", "C.WildReserve.WeakSpeed", "d")),
    "wild_satiation": (("enabled", "C.WildSatiation.bEnabled", "b"), ("sat_days", "C.WildSatiation.SatDays", "d"),
                       ("rest_speed", "C.WildSatiation.RestSpeed", "d")),
    "realism_vision": (("enabled", "C.RealismVision.bEnabled", "b"), ("threat_fov_deg", "C.RealismVision.ThreatFovDeg", "d")),
    "realism_hearing": (("enabled", "C.RealismHearing.bEnabled", "b"), ("s_silent", "C.RealismHearing.SSilent", "d"),
                        ("s_quiet", "C.RealismHearing.SQuiet", "d"), ("s_loud", "C.RealismHearing.SLoud", "d"), ("r_quiet", "C.RealismHearing.RQuiet", "d"),
                        ("r_loud", "C.RealismHearing.RLoud", "d"), ("roam_quiet", "C.RealismHearing.bRoamQuiet", "b"),
                        ("cap_to_sight", "C.RealismHearing.bCapToSight", "b")),
    "shelter_food": (("enabled", "C.ShelterFood.bEnabled", "b"), ("cap_frac", "C.ShelterFood.CapFrac", "d"), ("regen_frac", "C.ShelterFood.RegenFrac", "d")),
    "pack_hunt": (("enabled", "C.PackHunt.bEnabled", "b"), ("join_r", "C.PackHunt.JoinR", "d"), ("lead", "C.PackHunt.Lead", "d"),
                  ("door_r", "C.PackHunt.DoorR", "d"), ("door_cos", "C.PackHunt.DoorCos", "d"), ("wait_r", "C.PackHunt.WaitR", "d")),
    "obstacle_rules": (("enabled", "C.Obstacles.bEnabled", "b"), ("body_r", "C.Obstacles.BodyR", "d"), ("block_sight", "C.Obstacles.bBlockSight", "b"),
                       ("no_food", "C.Obstacles.bNoFood", "b"), ("detour", "C.Obstacles.Detour.bEnabled", "b"),
                       ("detour_block", "C.Obstacles.Detour.BlockFrac", "d"), ("detour_free", "C.Obstacles.Detour.FreeFrac", "d"),
                       ("detour_probe", "C.Obstacles.Detour.Probe", "d"), ("detour_steps", "C.Obstacles.Detour.MaxSteps", "i"),
                       ("detour_help_block", "C.Obstacles.Detour.HelpBlock", "i"), ("detour_help_drop", "C.Obstacles.Detour.HelpDrop", "i"),
                       ("foliage", "C.Obstacles.Foliage.bEnabled", "b"), ("foliage_r", "C.Obstacles.Foliage.R", "d"),
                       ("foliage_block", "C.Obstacles.Foliage.Block", "d")),
    "weather": (("enabled", "C.Weather.bEnabled", "b"), ("kind", "C.Weather.Kind", "weather"), ("intensity", "C.Weather.Intensity", "d"),
                ("rain_sight", "C.Weather.RainSight", "d"), ("rain_hear", "C.Weather.RainHear", "d"), ("snow_sight", "C.Weather.SnowSight", "d"),
                ("snow_hear", "C.Weather.SnowHear", "d"), ("snow_deer_speed", "C.Weather.SnowDeerSpeed", "d"), ("snow_wolf_speed", "C.Weather.SnowWolfSpeed", "d"),
                ("obs_visibility", "C.Weather.bObsVisibility", "b")),
}
# 옮기지 않는 칸: 날씨 시간표 줄 수(늘 0 — 따로 본다), 10-24 두 길 두뇌의 세계 키(wild_flight.route·brain_flee_outside_reflex — 평가기는 두뇌 판으로 켜고
# 세계 키는 짝 검사에만 쓴다. 두 길 골든 FillWorldConfig 는 C.WildFlight.bRoute 를 따로 적는다)
CFG_SKIP = {("weather", "schedule_rows"), ("wild_flight", "route"), ("wild_flight", "brain_flee_outside_reflex")}
# 10-27 선택 칸 (거리 두기 wild_flight.rest_keep*·먹기 걷기 고침 블록 graze_calm — EcoV3Eval.cpp ConfigOf 의 선택 칸). 끔 값(= C++ 기본값)이면 줄을 적지 않는다 —
# 끈 세계의 골든(이 파일·두 길 골든 FillWorldConfig)은 바이트가 그대로다. 켠 세계(calm 골든)만 줄이 생긴다. (블록, 칸, C++ 칸, 형, 끔 값)
CFG_OPTIONAL = (("wild_flight", "rest_keep", "C.WildFlight.bRestKeep", "b", False),
                ("wild_flight", "rest_keep_margin", "C.WildFlight.RestKeepMargin", "d", 2.0),
                ("wild_flight", "rest_keep_band", "C.WildFlight.RestKeepBand", "d", 0.0),
                ("wild_flight", "rest_keep_asleep", "C.WildFlight.bRestKeepAsleep", "b", False),
                ("graze_calm", "graze_edge_r", "C.GrazeCalm.EdgeR", "d", 0.0),
                ("graze_calm", "graze_edge_w", "C.GrazeCalm.EdgeW", "d", 0.0),
                ("graze_calm", "graze_inertia", "C.GrazeCalm.Inertia", "d", 0.0),
                ("graze_calm", "graze_wall_margin", "C.GrazeCalm.WallMargin", "d", 0.0))
CFG_OPTIONAL_KEYS = {(blk, key) for blk, key, _, _, _ in CFG_OPTIONAL}
CFG_OPTIONAL_BLOCKS = {blk for blk, _, _, _, _ in CFG_OPTIONAL} - set(CFG_BLOCKS)


def optional_code(wb: dict, lit) -> list[str]:
    """world 블록의 10-27 선택 칸 가운데 끔 값이 아닌 것 → FillWorldConfig 줄 (CFG_OPTIONAL — 끈 세계는 빈 목록). 모르는 칸이 있는 선택 블록이면 멈춘다."""
    for blk in sorted(CFG_OPTIONAL_BLOCKS):
        left = {k for k in wb.get(blk, {}) if (blk, k) not in CFG_OPTIONAL_KEYS}
        if left:
            raise SystemExit(f"world 블록 {blk} 에 C++ 로 옮기지 않은 칸: {sorted(left)}")
    out = []
    for blk, key, lhs, kind, off in CFG_OPTIONAL:
        v = wb.get(blk, {}).get(key, off)
        if v != off or isinstance(v, bool) != isinstance(off, bool):
            out.append(f"\t\t{lhs} = {lit(v, kind)};")
    return out
WEATHER_KIND = {"clear": "EcoWorldV3::kWeatherClear", "rain": "EcoWorldV3::kWeatherRain", "snow": "EcoWorldV3::kWeatherSnow"}


def config_code(wb: dict) -> list[str]:
    """world 블록 → `inline void FillWorldConfig(FWorldConfig& C)` 본문 (모든 칸을 옮긴다 — 모르는 칸이 있으면 멈춘다)."""

    def lit(v, kind):
        if kind == "d":
            return d_lit(v)
        if kind == "i":
            return i_lit(v)
        if kind == "i64":
            return i64_lit(v)
        if kind == "u64":
            return u64_lit(v)
        if kind == "b":
            if not isinstance(v, (bool, np.bool_)):
                raise SystemExit(f"참/거짓 칸이 아니다: {v!r}")
            return "true" if v else "false"
        if kind == "weather":
            return WEATHER_KIND[v]
        raise SystemExit(kind)

    out = []
    used = set()
    for key, lhs, kind in CFG_TOP:
        out.append(f"\t\t{lhs} = {lit(wb[key], kind)};")
        used.add(key)
    wa = wb["world_allowed"]
    for b, v in enumerate(wa):
        out.append(f"\t\tC.WorldAllowed[{b}] = {i_lit(v)};")
    used.add("world_allowed")
    for blk, fields in CFG_BLOCKS.items():
        d = wb[blk]
        got = set()
        for key, lhs, kind in fields:
            out.append(f"\t\t{lhs} = {lit(d[key], kind)};")
            got.add(key)
        left = {k for k in d if k not in got and (blk, k) not in CFG_SKIP and (blk, k) not in CFG_OPTIONAL_KEYS}
        if left:
            raise SystemExit(f"world 블록 {blk} 에 C++ 로 옮기지 않은 칸: {sorted(left)}")
        used.add(blk)
    used |= CFG_OPTIONAL_BLOCKS
    left = set(wb) - used
    if left:
        raise SystemExit(f"world 블록에 C++ 로 옮기지 않은 칸: {sorted(left)}")
    if wb["weather"].get("schedule_rows", 0):
        raise SystemExit("날씨 시간표는 옮기지 않는다")
    out += optional_code(wb, lit)           # 10-27 선택 칸 (끈 세계는 줄이 없다 — 옛 골든 바이트 그대로)
    out.append("\t\tC.Obstacles.Foliage.bEnabled = C.Obstacles.bEnabled && C.Obstacles.Foliage.bEnabled;   // EcoV3Eval ConfigOf 와 같다")
    out.append("\t\tC.bSenseStats = false;   // 평가기와 같다 (기록만)")
    out.append("\t\tC.bFlightStats = true;")
    return out


# --------------------------------------------------------------------- #
# 헤더
# --------------------------------------------------------------------- #


def build_header() -> str:
    check_seeds(SEED_CHORD, SEED_OBS, SEED_FLIGHT, SEED_PAIR, *LOOP_SEEDS)
    if (FL_DROP_NONE, FL_DROP_RANGE, FL_DROP_SWITCH, FL_DROP_FOV, FL_DROP_STOP, FL_DROP_OBSTACLE, FL_DROP_COVER) != (0, 1, 2, 3, 4, 5, 6):
        raise SystemExit("놓침 까닭 번호가 바뀌었다 — C++ kFlDrop* 와 맞춘다")
    fdef = dict(OPTIONAL_KEYS["obstacles"]["foliage"])
    if (fdef["enabled"], float(fdef["r"]), float(fdef["block"]), fdef["trees"]) != (False, FOL_R, FOL_BLOCK, "all"):
        raise SystemExit(f"features.OPTIONAL_KEYS obstacles.foliage 가 바뀌었다: {fdef}")
    rng = np.random.default_rng(SEED_CHORD)
    sets = disc_sets(rng)
    cs = chord_cases(sets, rng)
    chord_eval(sets, cs)
    mir = sets[1][1]
    mtrees = tree_mask(len(mir))
    _, size, body_r = mirror_world()
    oc = obs_cases(mir, mtrees, np.random.default_rng(SEED_OBS), size, body_r)
    pairs, pc = pair_scenes(mtrees)
    fls = fl_scenes(mtrees)
    print("기준 루프 시드 고르기:")
    seed, on, off, div = pick_loop(mtrees)

    L = []
    L.append("// 자동 생성 — herbivore_rl/export_golden_v3_foliage.py (손으로 고치지 않는다). 세계 configs/v3_wild3_obs_mirror.yaml + 숲 시야, "
             f"시드 {SEED_CHORD}~{max(LOOP_SEEDS)}.")
    L.append("// v3 숲 시야 골든 (world.py 모듈 docstring '야생 2단계' 3 의 7) — `foliage_chord`·`foliage_blocked`, 사슴 위협 보임·늑대 표적·관측 threat_hidden·"
             "도망 기록 lost_foliage). 검사는 Tests/FoliageGoldenCheckV3.h (AdaptiveEcosystem.Policy.V3.Foliage.*, g++ tests/cpp/foliage_v3_main.cpp).")
    L.append("#pragma once")
    L.append("")
    L.append("#include <cstdint>")
    L.append("")
    L.append('#include "EcoWorldV3.h"')
    L.append("")
    L.append("namespace EcoWorldV3::GoldenFoliage")
    L.append("{")
    L.append("\t// ---- 정의 (features.OPTIONAL_KEYS obstacles.foliage 의 켤 때 값 — C++ FFoliageConfig 기본값과 같아야 한다) ----")
    L.append(f"\tinline constexpr double kDefaultR = {d_lit(FOL_R)};")
    L.append(f"\tinline constexpr double kDefaultBlock = {d_lit(FOL_BLOCK)};")
    L.append("")

    # 눈길 길이
    L.append("\t// ---- 눈길 길이: 원판 묶음 (x, y, r) 과 나무 표, 사례 (묶음, 나무 표 씀, a·b·r·block) → foliage_chord (double 비트)·가림·잎 구간 수 ----")
    L.append(f"\tinline constexpr std::int32_t kSetCount = {len(sets)};")
    starts, cnt, flat, tflat = [], [], [], []
    for _, d, t in sets:
        starts.append(len(flat) // 3)
        cnt.append(len(d))
        flat += [float(v) for v in d.reshape(-1)]
        tflat += [int(v) for v in t]
    L.append(c_array("std::int32_t", "kSetStart", starts, 8, i_lit))
    L.append(c_array("std::int32_t", "kSetNum", cnt, 8, i_lit))
    L.append(c_array("double", "kSetDiscs", flat, 6, d_lit))
    L.append(c_array("std::uint8_t", "kSetTrees", tflat, 32, i_lit))
    L.append(f"\tinline constexpr std::int32_t kChordCount = {len(cs)};")
    L.append(f"\tinline constexpr std::int32_t kChordHand = {sum(1 for c in cs if not c['name'].startswith('난수') and not c['name'].startswith('덩어리'))};"
             "   // 앞 사례 = 손 사례 (이름은 내보내기 chord_cases)")
    L.append(c_array("std::int32_t", "kChordSet", [c["set"] for c in cs], 24, i_lit))
    L.append(c_array("std::uint8_t", "kChordMasked", [c["masked"] for c in cs], 32, i_lit))
    L.append(c_array("double", "kChordIn", [v for c in cs for v in (c["a"][0], c["a"][1], c["b"][0], c["b"][1], c["r"], c["block"])], 6, d_lit))
    L.append(c_array("double", "kChordWant", [c["want"] for c in cs], 4, d_lit))
    L.append(c_array("std::uint8_t", "kChordBlocked", [c["blocked"] for c in cs], 32, i_lit))
    L.append(c_array("std::int32_t", "kChordSpans", [c["spans"] for c in cs], 24, i_lit))
    L.append("")

    # 관측
    n = len(oc["p"])
    L.append("\t// ---- 관측 threat_hidden: 원판 = 거울 숲 (kSetStart[1]), 나무 표 = kSetTrees 그 묶음, 사례마다 (사슴 x, y, heading x, y, away x, y, 위협 x, y)·")
    L.append("\t//      위협을 아나 → E·N (double 비트)·가림 (숲 시야 켬)·줄기만의 가림 (끔 — 그때 값) ----")
    L.append(f"\tinline constexpr std::int32_t kObsCount = {n};")
    L.append(f"\tinline constexpr double kObsBodyR = {d_lit(body_r)};")
    L.append(f"\tinline constexpr double kObsStageSize = {d_lit(size)};")
    L.append(c_array("double", "kObsIn", [v for i in range(n) for v in (oc["p"][i, 0], oc["p"][i, 1], oc["head"][i, 0], oc["head"][i, 1], oc["away"][i, 0],
                                                                          oc["away"][i, 1], oc["th"][i, 0], oc["th"][i, 1])], 4, d_lit))
    L.append(c_array("std::uint8_t", "kObsSeen", [int(v) for v in oc["seen"]], 32, i_lit))
    L.append(c_array("double", "kObsWantE", oc["e"], 4, d_lit))
    L.append(c_array("double", "kObsWantN", oc["near"], 4, d_lit))
    L.append(c_array("std::uint8_t", "kObsWantHidden", [int(v) for v in oc["hid"]], 32, i_lit))
    L.append(c_array("std::uint8_t", "kObsTrunkHidden", [int(v) for v in oc["hid0"]], 32, i_lit))
    L.append("")

    # 쌍 장면
    P, M, N = len(pairs), pc["M"], pc["N"]
    L.append("\t// ---- 쌍 장면 (`_step_predators_v3` — 낮 d = 0, 늑대 순번 짝수 잠행·홀수 추격, 은신처 표적 제외·원판 눈길 가림·숲 시야 켬, 원판 = 거울 숲, 나무 표 =")
    L.append("\t//      kSetTrees 의 묶음 1). 늑대 입력 (x, y, hx, hy)·(쿨다운, 배부름, 잠행 상태, 남은 수, 잠), 사슴 입력 (x, y)·(행동, HIDE 도착, 은신처 원 안),")
    L.append("\t//      장면 시야 배수, 결과 늑대 사냥 가능·표적(pred_target, 없으면 −1)·쌍 비트 (1 반경 안 · 2 반경과 시야각 안 · 4 가림 · 8 은신처 표적 제외 ·")
    L.append("\t//      16 잎만 가림) ----")
    L.append(f"\tinline constexpr std::int32_t kPairScenes = {P};")
    L.append(f"\tinline constexpr std::int32_t kPairWolves = {M};")
    L.append(f"\tinline constexpr std::int32_t kPairPrey = {N};")
    L.append(f"\tinline constexpr double kPairWorldSize = {d_lit(pc['size'])};")
    L.append(f"\tinline constexpr double kPairPredSpeedMult = {d_lit(pc['pred_speed_mult'])};")
    L.append(f"\tinline constexpr double kPairBody = {d_lit(pc['body'])};")
    L.append(f"\tinline constexpr std::int32_t kPairEatCd = {pc['eat_cd']};")
    L.append(f"\tinline constexpr std::int32_t kPairSatSteps = {pc['sat_steps']};")
    L.append(f"\tinline constexpr double kPairViewR = {d_lit(pc['view_r'])};")
    L.append(f"\tinline constexpr double kPairFovCos = {d_lit(pc['fov_cos'])};")
    L.append(f"\tinline constexpr double kPairCStill = {d_lit(pc['c_still'])};")
    L.append(c_array("double", "kPairCoverMult", list(pc["cover_mult"]), 4, d_lit))
    L.append(c_array("std::int32_t", "kPairStalker", [int(k == PT_STALKER) for k in pc["kinds"]], 8, i_lit))
    if pc["discs"].tobytes() != mir.tobytes():
        raise SystemExit("쌍 장면 원판이 거울 숲 묶음과 다르다")
    wf, wi, pf, pi, sg, hu, tg, fl = [], [], [], [], [], [], [], []
    for sc in pairs:
        for m in range(M):
            wf += [sc["q"][m, 0], sc["q"][m, 1], sc["head"][m, 0], sc["head"][m, 1]]
            wi += [int(sc["cd"][m]), int(sc["sat"][m]), int(sc["st"][m]), int(sc["left"][m]), int(sc["asleep"][m])]
            hu.append(int(bool(sc["hunt"][m])))
            tg.append(int(sc["target"][m]))
            for i in range(N):
                fl.append(int(sc["rng"][m, i]) | 2 * int(sc["vis0"][m, i]) | 4 * int(sc["blk"][m, i]) | 8 * int(sc["cov"][m, i]) | 16 * int(sc["fol"][m, i]))
        for i in range(N):
            pf += [sc["p"][i, 0], sc["p"][i, 1]]
            pi += [int(sc["beh"][i]), int(sc["arrived"][i]), int(sc["in_cov"][i])]
        sg.append(sc["sight"])
    L.append(c_array("double", "kPairWolfIn", wf, 4, d_lit))
    L.append(c_array("std::int32_t", "kPairWolfInI", wi, 20, i_lit))
    L.append(c_array("double", "kPairPreyIn", pf, 4, d_lit))
    L.append(c_array("std::int32_t", "kPairPreyInI", pi, 24, i_lit))
    L.append(c_array("double", "kPairSight", sg, 6, d_lit))
    L.append(c_array("std::uint8_t", "kPairHunt", hu, 32, i_lit))
    L.append(c_array("std::int32_t", "kPairTarget", tg, 24, i_lit))
    L.append(c_array("std::uint8_t", "kPairFlags", fl, 32, i_lit))
    L.append("")

    # 도망 기록 장면
    L.append("\t// ---- 도망 기록 장면 (`_fl_update`, 숲 시야 켬): 틱마다 사슴 재료 비트 N (1 FLEE · 2 반사 · 4 죽음 · 8 잡힘 · 16 은신처 · 32 첫머리에 산),")
    L.append("\t//      늑대 재료 비트 M (1 스텝 끝 사냥 · 2 표적 고르기 때 사냥 · 4 쌍 있음 · 8 반경 안 · 16 반경과 시야각 안 · 32 가림 · 64 은신처 · 128 잎만 가림)·")
    L.append(f"\t//      표적·지난 표적, 그 뒤 보고 {ROW_LEN} 칸 (49 + lost_foliage n·steps·contact)·사슴 칸 {TRACK_LEN} × N (7 + _fl_why_fol)·늑대 지난 표적(뒤) ----")
    L.append(f"\tinline constexpr std::int32_t kRowLen = {ROW_LEN};")
    L.append(f"\tinline constexpr std::int32_t kTrackLen = {TRACK_LEN};")
    L.append(f"\tinline constexpr std::int32_t kFlSceneCount = {len(fls)};")
    L.append(c_array("std::int32_t", "kFlSceneN", [s.w.N for s in fls], 8, i_lit))
    L.append(c_array("std::int32_t", "kFlSceneM", [s.w.M for s in fls], 8, i_lit))
    L.append(c_array("std::int32_t", "kFlSceneTicks", [len(s.stats) for s in fls], 8, i_lit))
    deer, wb, wt, wp, st, tr, pa = [], [], [], [], [], [], []
    for s in fls:
        for k in range(len(s.stats)):
            deer += s.deer[k]
            wb += s.wolf_bits[k]
            wt += s.wolf_tgt[k]
            wp += s.wolf_prev[k]
            st += s.stats[k]
            tr += s.tracks[k]
            pa += s.prev_after[k]
    L.append(c_array("std::uint8_t", "kFlDeer", deer, 24, i_lit))
    L.append(c_array("std::uint8_t", "kFlWolfBits", wb, 24, i_lit))
    L.append(c_array("std::int32_t", "kFlWolfTarget", wt, 24, i_lit))
    L.append(c_array("std::int32_t", "kFlWolfPrev", wp, 24, i_lit))
    L.append(c_array("std::int64_t", "kFlStats", st, 13, i64_lit))
    L.append(c_array("std::int32_t", "kFlTracks", tr, 24, i_lit))
    L.append(c_array("std::int32_t", "kFlPrevAfter", pa, 24, i_lit))
    L.append("")

    # 기준 루프
    w, job = on["w"], on["job"]
    f = on["final"]
    fo = off["final"]
    Nw, Mw = w.N, w.M
    caught_on = int(np.count_nonzero(np.asarray(w.death_cause) == 1))
    caught_off = int(np.count_nonzero(np.asarray(off["w"].death_cause) == 1))
    L.append(f"\t// ---- 기준 루프: 거울 세계 사슴 {Nw}·늑대 {Mw}, 시드 {seed}, 숲 시야 켬 {LOOP_STEPS} 스텝 (R1b-F 관측 21 = 내장 망 + 0 열, 파이썬 world.py 그대로).")
    L.append(f"\t//      켬: 잡힘 {caught_on} · 시작 도망 {f['started']} · 원판 놓침 {f['n']['obstacle']} 가운데 잎 {f['lost_foliage']['n']} · 스스로 벗어남 {f['own_n']}")
    L.append(f"\t//      끔: 잡힘 {caught_off} · 시작 도망 {fo['started']} · 원판 놓침 {fo['n']['obstacle']} · 스스로 벗어남 {fo['own_n']} · 켬·끔 첫 갈림 지문 {div} ----")
    L.append(f"\tinline constexpr std::int32_t kWorldN = {Nw};")
    L.append(f"\tinline constexpr std::int32_t kWorldM = {Mw};")
    L.append(f"\tinline constexpr std::int32_t kWorldSteps = {LOOP_STEPS};")
    L.append(f"\tinline constexpr std::int32_t kWorldEvery = {LOOP_EVERY};")
    L.append(f"\tinline constexpr std::int32_t kWorldChecks = {len(on['checks'])};")
    L.append(f"\tinline constexpr std::int32_t kWorldCheckLen = {CHECK_LEN};   // 잡힘·굶음·산 + 보고 {ROW_LEN} 칸")
    L.append(f"\tinline constexpr std::int32_t kWorldFirstSplit = {div};   // 숲 시야 켬·끔 지문이 처음 다른 번호 (기록만)")
    L.append("")
    L.append("\t/** 세계 설정 (평가기 일의 world 블록 — EcoV3Eval.cpp ConfigOf 와 같은 대응). 숲 시야 켬 판이다 (끔 판은 Foliage.bEnabled 만 다르다). */")
    L.append("\tinline void FillWorldConfig(FWorldConfig& C)")
    L.append("\t{")
    L += config_code(job["world"])
    L.append("\t}")
    L.append("")
    cov = np.asarray(job["covers"], dtype=np.float64).reshape(-1)
    dsc = np.asarray(job["discs"], dtype=np.float64).reshape(-1)
    L.append(f"\tinline constexpr std::int32_t kWorldCoverCount = {len(job['covers'])};")
    L.append(c_array("double", "kWorldCovers", cov, 6, d_lit))
    L.append(f"\tinline constexpr std::int32_t kWorldDiscCount = {len(job['discs'])};")
    L.append(c_array("double", "kWorldDiscs", dsc, 6, d_lit))
    if len(job["foliage_trees"]) != len(job["discs"]):
        raise SystemExit("기준 루프 나무 표 길이 ≠ 원판 수")
    L.append(c_array("std::uint8_t", "kWorldTrees", job["foliage_trees"], 32, i_lit))
    fd = job["food"]
    L.append(f"\tinline constexpr std::int32_t kWorldGw = {int(fd['gw'])};")
    L.append(f"\tinline constexpr double kWorldCell = {d_lit(fd['cell'])};")
    L.append(c_array("double", "kWorldCap", fd["cap"], 6, d_lit))
    L.append(c_array("double", "kWorldFood", fd["food"], 6, d_lit))
    L.append(c_array("double", "kWorldRegen", fd["regen"], 6, d_lit))
    dj = job["deer"]
    if dj["slot"] != list(range(Nw)):
        raise SystemExit("기준 루프 사슴 슬롯이 0..N−1 이 아니다")
    L.append("\t// 사슴 (슬롯 순서) x, y, hx, hy, energy, reserve · 번식 쿨다운")
    L.append(c_array("double", "kWorldDeer", [v for i in range(Nw) for v in (dj["x"][i], dj["y"][i], dj["hx"][i], dj["hy"][i], dj["energy"][i],
                                                                              dj["reserve"][i])], 6, d_lit))
    L.append(c_array("std::int32_t", "kWorldDeerRepro", dj["repro_cd"], 24, i_lit))
    wv = job["wolves"]
    if [a["slot"] for a in wv] != list(range(Mw)):
        raise SystemExit("기준 루프 늑대 슬롯이 0..M−1 이 아니다")
    L.append("\t// 늑대 (위협 슬롯 순서) x, y, hx, hy, 기본 속력 · 잠행형인가")
    L.append(c_array("double", "kWorldWolves", [v for a in wv for v in (a["x"], a["y"], a["hx"], a["hy"], a["speed"])], 5, d_lit))
    L.append(c_array("std::uint8_t", "kWorldWolfStalker", [int(a["kind"] == "stalker") for a in wv], 8, i_lit))
    L.append(f"\t// 세계 난수: numpy PCG64 날 64 비트 {len(on['raw'])} 개 (스텝마다 늑대 슬롯 순서 배회 선회 — FRng::External 로 넣는다)")
    L.append(c_array("std::uint64_t", "kWorldRaw", on["raw"], 4, u64_lit))
    L.append(f"\t// 지문 (머리 주석 '지문', 0 번 = 시작) — 숲 시야 켬·끔")
    L.append(c_array("std::uint64_t", "kWorldHashOn", on["hashes"], 4, u64_lit))
    L.append(c_array("std::uint64_t", "kWorldHashOff", off["hashes"], 4, u64_lit))
    L.append(f"\t// {LOOP_EVERY} 스텝마다 기록 (잡힘·굶음·산 + 보고 {ROW_LEN} 칸 — 끔 판의 lost_foliage 칸은 0)")
    L.append(c_array("std::int64_t", "kWorldCheckOn", [v for r in on["checks"] for v in r], 13, i64_lit))
    L.append(c_array("std::int64_t", "kWorldCheckOff", [v for r in off["checks"] for v in r], 13, i64_lit))
    L.append("}")
    L.append("")

    nb = sum(c["blocked"] for c in cs)
    big = sum(1 for c in cs if c["spans"] > 64)
    fol_only = sum(1 for a, b in zip(oc["hid"], oc["hid0"]) if a and not b)
    pf_ = sum(1 for v in fl if v & 16)
    pb_ = sum(1 for v in fl if v & 4)
    print(f"눈길 길이 {len(cs)} (가림 {nb}, 구간 64 넘음 {big}) · 관측 {n} (가림 {int(oc['hid'].sum())}, 잎만 {fol_only}) · 쌍 장면 {P} (가림 {pb_}, 잎만 {pf_}, "
          f"표적 {sum(1 for v in tg if v >= 0)}/{len(tg)}) · 도망 기록 장면 {len(fls)} (끝 lost_foliage {[s.stats[-1][-3:] for s in fls]}) · 기준 루프 시드 {seed} "
          f"(켬 잎 놓침 {f['lost_foliage']['n']}, 켬·끔 첫 갈림 {div})")
    if big == 0 or fol_only == 0 or pf_ == 0 or all(s.stats[-1][-3] == 0 for s in fls):
        raise SystemExit("골든에 숲 시야 사례가 모자란다 (구간 64 넘음·관측 잎만·쌍 잎만·도망 잎 놓침)")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    text = build_header()
    out = args.out / HEADER
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"썼다: {out} ({len(text.encode('utf-8'))} 바이트)")


if __name__ == "__main__":
    main()
