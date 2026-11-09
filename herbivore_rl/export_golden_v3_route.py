"""v3 두 길 두뇌(RUN·SHELTER) 장면 골든 내보내기 — 파이썬 두 길 세계(env_v2/world.py 모듈 docstring '야생 1단계' (w3) 두뇌 길, `World._route_step`·
`_route_apply`·`flight_route_geometry` 의 SHELTER·`route_stats`, env_v2/rep_policy.py 마스크 판 4)를 언리얼 C++ 이식(설계
AdaptiveEcosystem/Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 16-12·16-14 단계 6 — C++ 은 RUN·SHELTER 기하만)과 대조할 골든을 만든다.

    # herbivore_rl/ 에서 (PYTHONUTF8=1). 헤더는 언리얼 모듈 폴더(AI/Policy)에, 같은 내용 JSON 은 results/v3/route/port/ 에 쓴다 (10-24 C++ 이식 —
    # 검사 본문 AI/Policy/Tests/RouteGoldenCheckV3.h, g++ 하네스 tests/cpp/route_v3_main.cpp)
    python export_golden_v3_route.py
    # 시험용 다른 폴더 (헤더·JSON 둘 다)
    python export_golden_v3_route.py --out <폴더>

세계: configs/v3_wild3_route_mirror.yaml (관측 21 거울 + wild_flight.route — 관측 24·마스크 판 4, 계약 0xe302dee198197444), 다시 난 개체는
configs/v3_r6_train.yaml (R6 학습 세계 — 40 m 밖 부활). 이 내보내기 전용 탐색 시드 32080~32099 만 쓴다: 32097(부활 세계)·32096(길 셈 루프)·32099(손 장면
그릇)·32098(난수 기하·관측 사례)·32080~32095 가운데 첫 조건 맞는 시드(기준 루프). 판정·학습·고르기 시드는 쓰지 않는다(check_seeds).
이식 계획서 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_ROUTE_CPP_PORT_PLAN.md 10-1 의 묶음 1~6 에 맞춘다(아래 [1]~[6]). 판 단위 궤적 대조(10-2)는
results/v3/route/port/make_traces.py 가 만든다.

묶음 (C++ 꼴은 헤더 머리 주석, 같은 이름의 배열이 JSON 에도 있다):
  [1] 기하  SHELTER 기하 순수 함수 사례 90 (`flight_route_geometry(..., cover=False)` 의 shelter_*·keep_*): 손 사례 — 기본·μ = 2 경계와 바로 밑·± 1 ulp,
            cos = 0 경계와 바로 밑·cos = −0.0, e = 20 경계와 바로 위·± 1 ulp, 은신처 안(e ≤ 0)·둘레 위(e = 0)·중심(|v| = 0·|v| < EPS — 유지 방향),
            같은 e(낮은 번호)·가까운 가장자리, S 밖 늑대는 셈 밖·S 빔(μ = +∞), 벽 여유(x·y 성분 지움·다 지워짐), 유지 μ = 0 경계와 바로 밑·± 1 ulp,
            k* 와 다른 유지 은신처, 후보 밖(뒤쪽·e 42)인데 유지 — 그리고 거울 은신처 넷의 난수 사례 56 (벽 가까이 1/5).
  [2] 길 단계·적용
       손 장면  거울 세계 그릇(사슴 4·늑대 4)의 사슴 0 하나에 길 상태·덮기 전환·늑대 자리를 놓고 `_route_step`(스텝 끝 H)·`_route_apply`(다음 스텝 첫머리)를
                그대로 부른다 (15 장면): 도주 시작 두 칸(SHELTER·RUN 고름)·한 칸(칸 4 를 마스크 밖에서 내면 RUN·bad_shelter), SHELTER 문턱 근처(μ = 2·바로
                밑), SHELTER 무효(늑대가 문에 먼저 — 무효 뒤 다른 은신처 다시 고름·한 칸 결정 포함)·유지 문턱 μ = 0 경계, 2 초 잠금 안·뒤 RUN 다시 고르기
                (가능 0 → 1·1 → 0)·같으면 그대로, SHELTER 유지(잠금 안·뒤 가능 바뀜에도 이음·은신처 원 안), 길 상태 없는 열린 도주(cur < 0 — 두뇌 교체,
                계획서 2-2 넷째 조건) 두 칸·한 칸, 도주 끝·웅크림·죽음에서 지움. 틱마다 길 통계.
       길 셈 루프  거울 숲 N 세계(사슴 32, 늑대 포만 끔) 900 스텝 — 마스크 안 균등 요청 + 길 결정 줄은 정해진 무늬로 SHELTER(열렸을 때 3/4)·RUN.
                `_route_step` 을 부를 때마다 도주 사슴·길을 지우는 사슴의 줄(결정·지움·가능 바뀜 줄은 모두, RUN·SHELTER 비결정 줄은 무늬로 솎음), 다음
                스텝 `_route_apply` 줄(모두), 50 스텝마다 길 통계, 100 스텝마다 모든 사슴의 관측 21~23·길 상태, 끝에 도망 기록의 길 덩어리.
  [3] 관측  관측 세 칸 사례 37 (WriteRouteObs — μ = 2·10·+∞·문턱 위 ulp, e 아주 작음·20·20 밑 ulp, 도주 아님·가능 아님 + 난수 24). 같은 식이 길 셈 줄의
            세계 관측을 모두 다시 내는지도 본다.
  [4] 마스크 판 4 줄: 손 줄 + 길 셈 루프에서 갈래마다 처음 몇 줄(도주 결정 두 칸·한 칸·도주 비결정 RUN·SHELTER·웅크림·그 밖 판 2 — 결정·비결정).
            10-24 이식 계획서 13-3: 판 5(= 판 4 + 반사 밖 두뇌 FLEE 막음 — rep_peek 의 brain_flee_outside_reflex = False) 손 줄(종류 'gate' — 덮기 밖 결정·기상
            결정은 칸 1 막힘, 덮기 밖 비결정 FLEE 한 칸·도주 결정·도주 비결정·웅크림은 판 4 그대로)도 더한다.
  [5] 기준 루프 거울 세계(사슴 48, 부활 없음, 길 켬) 450 스텝을 두뇌 둘의 argmax 로 돌린 스텝마다 지문(헤더 머리 주석)·90 스텝마다 기록. 두뇌 = route0
            (ckpt/v3/v3_r1_g995_s3_obs24route0.zip — 내장 R1b + 0 열 + 칸 4 = 칸 1 − 2)과 늘 SHELTER 시험 두뇌(같은 꼴, 칸 4 = 칸 1 + 2 — 학습·판정에 쓰지
            않는다). 시작 상태는 길 끈 같은 시드 세계의 평가기 일(ceval.native_job)과 같고(길은 reset 난수를 쓰지 않는다 — 확인), 세계 난수는 PCG64 날 64
            비트. 시드는 두뇌 둘 모두 근접 동점(< 1e-4)·두뇌 파일 순전파 argmax 차가 없고, 늘 SHELTER 두뇌가 은신처 길로 끝난 도망과 잡힘이 있는 첫 시드.
  [6] 도망 길 기록 by_route·drop_obstacle·chased_steps·hidden_steps·refled — 길 셈 루프 끝·기준 루프 두뇌마다 끝 + 짜 맞춘 장면 하나(`_fl_update` 를
            재료로 직접 부른다 — export_golden_v3_flight.py 짜 맞춘 장면과 같은 재료 비트 + 실행한 길·스텝 번호): 세계 루프에 없는 경계 — 살아 끝난 도망 뒤
            38 스텝 째 새 도망(refled)·39 스텝 째(아님)·죽음이 마지막 끝 스텝을 지움, 반사 스텝 동점(앞 번호 RUN)·반사 없는 두뇌 FLEE(none), 한 사슴을
            늑대 둘이 원판 놓침(늑대마다 셈)·쫓는 늑대 하나만 가림(hidden 아님), 열린 도망의 truncated(길별). 틱마다 길 덩어리·사슴 칸.
  다시 난   R6 학습 세계(사슴 48, 부활 — 길 결정은 열리면 늘 SHELTER)에서 길 상태가 있던 사슴이 죽어 다시 난 사건: 스텝 전·뒤 덮기·길 상태, 다시 난 사슴의 관측 21~23, 죽은 사슴의
            terminal_obs 21~23 (늘 0). 통합 세계(부활 없음)의 죽음 지움은 길 셈 루프 줄(alive0 참·다음 덮기 없음)에 있다.
덮는지 셈 `coverage(data)` (tests/test_route_port_v3.py 가 같은 함수를 부른다): 계획 장면 꼬리표마다 줄 수 — 하나라도 0 이면 멈춘다.
C++ 꼴 스칼라 참조 tests/cpp/route_ref_main.cpp (헤더 머리 주석의 식을 사슴 하나·double 로 옮긴 것 — 엔진 코드 아님)가 기하·길 셈 줄·적용·손 장면 통계·
마스크·다시 난 개체·관측 사례·도망 길 기록 장면의 길 칸(놓침·쫓김·가림·refled·길별 반사 스텝·마지막 끝 스텝)을 비트 단위로 다시 낸다(g++ 가 있으면
시험이 컴파일해 돌린다). 10-24 C++ 이식 뒤에는 엔진 함수(EcoWorldV3.h Detail::RouteShelterGeometry·RouteStep·RouteApply, EcoObservationV3.h WriteRouteObs,
EcoPolicyV3Inference.h ApplyRouteMaskRows, FlightUpdate 의 도망 길 기록)와 기준 루프 지문·기록·도망 길 기록 장면의 끝 까닭별 by_route 를
AI/Policy/Tests/RouteGoldenCheckV3.h 가 보고 g++ 하네스 tests/cpp/route_v3_main.cpp 가 그것을 돌린다(UE 자동화 Route.* 는 다음 단계).
기준 루프 세계 설정은 템플릿 FillWorldConfig(TConfig&) 라 이 헤더는 EcoWorldV3.h 없이도 컴파일된다(C.WildFlight.bRoute 를 쓴다). 기준 루프 두뇌의 바탕(내장 R1b = PolicyWeightsV3.h)이 route0 의 앞 18 열·출력층과 같은지도
본다(C++ 이 내장 망을 24 열로 늘려 같은 두뇌를 만든다는 머리 주석의 전제).
이름: '길 셈 루프'(kLoop* — 사슴 32, 900 스텝, 줄을 적는 루프)와 '기준 루프'(kWorld* — 사슴 48, 450 스텝, 두뇌 둘의 지문)는 다른 루프다.
결정성: 시각·절대 경로를 적지 않는다. 같은 코드·설정이면 바이트 단위로 같은 헤더·JSON 이 나온다(시험).
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

for _p in ("live", "adapt", "mirror", "r4", "wild2"):              # 기준 루프의 평가기 일(ceval.native_job)·도망 보고(export_golden_v3_foliage) — foliage 골든과 같다
    _q = str(Path(__file__).resolve().parent / "results" / "v3" / _p)
    if _q not in sys.path:
        sys.path.insert(0, _q)

import export_weights_v3 as ew
from env_v2.config import load_v2_config
from env_v2.rep_policy import (FLEE_GATE_KEY, HIDE_COVER_OBS, MASK_VERSION_ROUTE, MASK_VERSION_ROUTE_GATE, ROUTE_SLOT_RESERVED, ROUTE_SLOT_RUN,
                               ROUTE_SLOT_SHELTER, THREAT_RECENCY_OBS, action_mask, allowed_mask_of, mask_version_of, rep_params, sample_masked)
from env_v2.repertoire import FLEE, FREEZE, GRAZE, HIDE, SLEEP
from env_v2.steering import EPS
from env_v2.world import (ROUTE_FEAS_SHELTER, ROUTE_LOCK_STEPS, ROUTE_NAMES, ROUTE_NONE, ROUTE_OBS_NAMES, ROUTE_RUN, ROUTE_SHELTER,
                          ROUTE_SHELTER_COS_MIN, ROUTE_SHELTER_EDGE_NORM_U, ROUTE_SHELTER_ENTER_U, ROUTE_SHELTER_EXIT_U, ROUTE_SHELTER_MAX_EDGE_U,
                          ROUTE_SHELTER_REACH_U, WF_ALERT, WF_NONE, WF_PANIC, WF_SHELTER, FLIGHT_CAUSES, World, flight_route_geometry, obs_names)

HERE = Path(__file__).resolve().parent
ROUTE_CFG = HERE / "configs" / "v3_wild3_route_mirror.yaml"
R6_CFG = HERE / "configs" / "v3_r6_train.yaml"
LAYOUT = HERE / "results" / "v3" / "wild2" / "trees" / "tree_layout.json"
DEFAULT_OUT = HERE / "results" / "v3" / "route" / "port"                                    # JSON (파이썬 시험·판 단위 대조 자료 옆)
DEFAULT_HEADER_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"   # 헤더 (다른 *GoldenVectorsV3.h 와 같은 자리)
HEADER = "RouteGoldenVectorsV3.h"
JSON_NAME = "RouteGoldenVectorsV3.json"
CONTRACT_OBS24 = 0xE302DEE198197444
SEED_RESPAWN = 32097
SEED_LOOP = 32096
SEED_BENCH = 32099
SEED_GEO = 32098                  # 난수 기하 사례
SEED_OBS = 32098                  # 난수 관측 사례 (기하와 다른 생성기 — 같은 시드 다른 용도)
WORLD_SEEDS = tuple(range(32080, 32096))   # 기준 루프(두뇌 둘) 시드 후보 — 계획서 10-1 의 5 '탐색 시드 32080~32099 안에서 고른다'
N_GEO_RANDOM = 56
N_OBS_RANDOM = 24
N_WORLD = 48
WORLD_STEPS = 450
WORLD_EVERY = 90
ROUTE0_ZIP = HERE / "ckpt" / "v3" / "v3_r1_g995_s3_obs24route0.zip"
ROUTE0_BRAIN = HERE / "results" / "v3" / "route" / "brains" / "v3_r1_g995_s3_obs24route0.json"
ROUTE0_DELTA = -2.0               # route0: B2[4] = B2[1] − 2 (results/v3/route/route_extend.py SHELTER_BIAS)
SHELTER_DELTA = 2.0               # 늘 SHELTER 시험 두뇌: B2[4] = B2[1] + 2 (학습·판정에 쓰지 않는다 — 계획서 10-1 의 5·10-2)
WORLD_BRAINS = (("route0", ROUTE0_DELTA), ("shelter2", SHELTER_DELTA))
NEAR_TIE = 1e-4
# 판정·학습·고르기·점검 시드 범위 (설계 16-9 확인 목록 + R6 범위) — 골든에 쓰지 않는다
JUDGE_SEED_RANGES = ((10000, 10020), (10200, 10220), (10300, 10320), (12160, 12200), (14000, 14040), (15000, 15040), (32000, 32050),
                     (33000, 33200), (34900, 35000), (35000, 35200), (36000, 36200), (37000, 37200))
N_BENCH = 4
N_LOOP = 32
LOOP_STEPS = 900
LOOP_STATS_EVERY = 50
LOOP_OBS_EVERY = 100
LOOP_ACTS_SEED = 23
LOOP_RUN_KEEP = 7                 # RUN 비결정 도주 줄은 (t + 사슴) % 7 == 0 인 것만 적는다 (잠금 안 가능 바뀜 줄은 모두)
LOOP_HOLD_KEEP = 3                # SHELTER 유지 줄은 (t + 사슴) % 3 == 0 인 것만 적는다 (가능 바뀜 줄은 모두). 결정·지움 줄은 모두
N_RESPAWN = 48
RESPAWN_STEPS = 3000
RESPAWN_WANT = 3                  # 길별(RUN·SHELTER) 다시 난 사건을 이만큼 모으면 멈춘다
MASK_PER_KIND = 6
SHELTER_PATTERN = 4               # 길 결정 줄: (t·7 + 사슴) % 4 != 0 이면 SHELTER (열렸을 때), 아니면 RUN
RESPAWN_PATTERN = 0               # 다시 난 개체 세계: 열리면 늘 SHELTER (SHELTER 길에서 죽는 사건이 드물다)
INF_LIT = 1e300                   # ±∞ 표기 (유지 은신처 없음 keep_mu = −∞)
M_GOLD = 4                        # 늑대 수 (거울 세계·R6 세계 모두 4)
FAR_WOLVES = ((5.0, 5.0), (5.0, 25.0), (25.0, 5.0))      # 손 장면의 S 밖 늑대 (사슴에서 safe_r 20 밖)

# 줄 칸 (C++ 꼴 — 헤더 머리 주석)
ROW_INT = ("src", "tick", "slot", "prev_mode", "next_mode", "alive0", "executed", "b_route", "b_k", "b_age", "b_feas", "s_bits")
ROW_IN = ("px", "py", "a0x", "a0y", "runx", "runy")
ROW_OUT_I = ("decide", "onset", "route", "k", "age", "feas", "sok", "cand_k", "dec_prev", "invalid", "refeas", "keep_ok")
ROW_OUT_D = ("mu", "e", "dirx", "diry", "shx", "shy", "keep_mu")
APPLY_INT = ("row", "req", "sok", "cand_k", "route", "k", "bad", "switch")
APPLY_D = ("b_dirx", "b_diry", "dirx", "diry")
STATS_INT = ("src", "tick", "onsets", "onset_shelter", "decisions", "redecide_feas", "switches", "invalid_shelter", "picked_run",
             "picked_shelter", "choice", "bad_shelter", "steps_run", "steps_shelter")
GEO_INT = ("set", "keep_k", "kind")
GEO_IN = ("px", "py", "a0x", "a0y", "size", "mg")
GEO_OUT_I = ("k", "ok", "keep_ok")
GEO_OUT_D = ("mu", "e", "dirx", "diry", "keep_mu", "keep_dirx", "keep_diry")
MASK_INT = ("kind", "override", "rdecide", "route_now", "reads", "wake", "behavior", "a0", "a1", "a2", "a3", "a4", "m0", "m1", "m2", "m3", "m4")
RESPAWN_INT = ("t", "slot", "cause", "b_mode", "b_route", "b_k", "b_age", "b_feas", "a_mode", "a_route", "a_k", "a_age", "a_feas", "a_decide")
MASK_KINDS = ("dec2", "dec1", "keep_run", "keep_shelter", "crouch", "other_reads", "other_hold", "other_wake", "hand", "gate")
SRC_SCENE, SRC_LOOP = 0, 1


def check_seeds(*seeds) -> None:
    for s in seeds:
        for lo, hi in JUDGE_SEED_RANGES:
            if lo <= int(s) < hi:
                raise SystemExit(f"시드 {s} 는 판정·학습·측정 시드 [{lo}, {hi}) 다 — 골든에 쓰지 않는다")


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def region_discs() -> dict:
    d = json.loads(LAYOUT.read_text(encoding="utf-8"))
    return {r["region"]: [[float(v) for v in row] for row in r["discs"]] for r in d["regions"]}


def away(p, qs) -> np.ndarray:
    """`_wf_update` 의 도주 방향 a₀ 와 같은 식 (S 늑대들의 거리 역수 가중 반대 — 0 이면 가장 가까운 늑대 반대)."""
    p = np.asarray(p, dtype=np.float64)
    q = np.asarray(qs, dtype=np.float64).reshape(-1, 2)
    ex, ey = q[:, 0] - p[0], q[:, 1] - p[1]
    pd = np.sqrt(ex * ex + ey * ey)
    pinv = 1.0 / np.maximum(pd, EPS)
    wt = 1.0 / np.maximum(pd, 0.5)
    s = np.array([-(ex * pinv * wt).sum(), -(ey * pinv * wt).sum()])
    n = math.sqrt(float(s[0] * s[0] + s[1] * s[1]))
    if n > EPS:
        return s / n
    j = int(pd.argmin())
    return np.array([-ex[j] * pinv[j], -ey[j] * pinv[j]])


def stats_row(w: World, src: int, tick: int) -> list[int]:
    rs = w.route_stats()
    return [src, tick, rs["onsets"], rs["onset_shelter"], rs["decisions"], rs["redecide_feas"], rs["switches"], rs["invalid"]["shelter"],
            rs["picked"]["run"], rs["picked"]["shelter"], rs["choice"], rs["bad_shelter"], rs["steps"]["run"], rs["steps"]["shelter"]]


# --------------------------------------------------------------------- #
# 기록 (`_route_step`·`_route_apply` 를 감싼다 — 감싼 함수는 원래 함수를 그대로 부른다)
# --------------------------------------------------------------------- #


class Book:
    """모든 묶음의 줄을 한곳에 모은다 (줄 번호·틱 번호가 묶음 사이에 이어진다)."""

    def __init__(self):
        self.tick_t: list[int] = []
        self.tick_q: list[list[float]] = []
        self.row_int: list[list[int]] = []
        self.row_in: list[list[float]] = []
        self.row_oi: list[list[int]] = []
        self.row_od: list[list[float]] = []
        self.row_obs: list[list[float]] = []
        self.ap_int: list[list[int]] = []
        self.ap_d: list[list[float]] = []
        self.stats: list[list[int]] = []
        self.tags: dict[int, set] = {}

    def tag(self, row: int, *names) -> None:
        self.tags.setdefault(row, set()).update(names)


class Rec:
    """`w._route_step`·`w._route_apply` 를 감싸 줄을 적는다. hand = 손 장면(사슴 0 의 줄을 늘 적는다)."""

    def __init__(self, w: World, book: Book, src: int, hand: bool):
        if not w._route_brain:
            raise ValueError("골든 세계는 wild_flight.route 를 켠 두 길 세계여야 한다")
        self.w, self.book, self.src, self.hand = w, book, src, hand
        self._step, self._apply = w._route_step, w._route_apply
        self.last_row = np.full(w.N, -1, dtype=np.int64)
        self.t = 0                                   # 길 셈 루프: 지금 스텝 번호 (부르는 쪽이 맞춘다)
        w._route_step = self.step_hook
        w._route_apply = self.apply_hook

    def step_hook(self, prev, nxt, dirs, a0, near_h, pd, alive0, executed):
        w, b = self.w, self.book
        b_route = w.flight_route.astype(np.int64).copy()
        b_k, b_age, b_feas = w.route_k.copy(), w.route_age.copy(), w.route_feas.astype(np.int64).copy()
        out = self._step(prev, nxt, dirs, a0, near_h, pd, alive0, executed)
        N = w.N
        pan = nxt == WF_PANIC
        on = pan & (prev != WF_PANIC)
        cur = np.where(on, ROUTE_NONE, b_route)
        # 셈 다시 하기 (줄의 무효·가능 바뀜·유지 μ — 세계 값과 같은지도 본다)
        geo = None
        ip = np.flatnonzero(pan)
        if len(ip):
            keep = np.where(cur[ip] == ROUTE_SHELTER, b_k[ip], -1)
            geo = flight_route_geometry(w.pos[ip], a0[ip], w.pred_pos, near_h[ip], pd[ip], w.cov_c, w.cov_r, np.zeros((0, 3)), w.size,
                                        w._wf["wall_margin"], w._wf["edge_r"], None, keep, None, cover=False)
            sok = geo["shelter_ok"]
            if not (np.array_equal(sok, w.route_cand_ok[ip, ROUTE_SHELTER]) and np.array_equal(geo["shelter_k"], w.route_cand_k[ip])
                    and np.array_equal(np.where(sok, geo["shelter_mu"], 0.0), w.route_shelter_mu[ip])
                    and np.array_equal(np.where(sok, geo["shelter_e"], 0.0), w.route_shelter_e[ip])
                    and np.array_equal(geo["shelter_dir"], w.route_cand_dir[ip, ROUTE_SHELTER])):
                raise SystemExit("다시 잰 SHELTER 기하가 세계 값과 다르다")
        inval = np.zeros(N, dtype=bool)
        refeas = np.zeros(N, dtype=bool)
        keep_ok = np.zeros(N, dtype=bool)
        keep_mu = np.zeros(N)
        keep_dir = np.zeros((N, 2))
        if geo is not None:
            c = cur[ip]
            kp = c == ROUTE_SHELTER
            inval[ip] = kp & ~geo["keep_ok"]
            keep_ok[ip] = kp & geo["keep_ok"]
            keep_mu[ip] = np.where(kp, geo["keep_mu"], 0.0)
            keep_dir[ip] = np.where(kp[:, None], geo["keep_dir"], 0.0)
            feas = np.where(geo["shelter_ok"], ROUTE_FEAS_SHELTER, 0)
            age = np.where(on[ip], 0, b_age[ip] + 1)
            refeas[ip] = (c >= 0) & ~inval[ip] & (age >= ROUTE_LOCK_STEPS) & (feas != b_feas[ip]) & (c != ROUTE_SHELTER)
            dec = on[ip] | (c < 0) | inval[ip] | refeas[ip]
            if not np.array_equal(dec, w.route_decide[ip]):
                raise SystemExit("다시 셈한 결정이 세계 결정과 다르다")
        if self.hand:
            rows = np.array([0])
        else:
            rd = w.route_decide
            trans = ~pan & (b_route >= 0)
            fch = pan & ~rd & (np.where(w.route_cand_ok[:, ROUTE_SHELTER], ROUTE_FEAS_SHELTER, 0) != w.route_feas)   # 가능 바뀜(다시 고르지 않음)
            pat = np.arange(N) + self.t
            hold = pan & ~rd & (w.flight_route == ROUTE_SHELTER) & ((pat % LOOP_HOLD_KEEP) == 0)
            run_keep = pan & ~rd & (w.flight_route == ROUTE_RUN) & ((pat % LOOP_RUN_KEEP) == 0)
            rows = np.flatnonzero((pan & rd) | trans | fch | hold | run_keep)
        if not len(rows):
            return out
        tick = len(b.tick_t)
        b.tick_t.append(int(self.t))
        b.tick_q.append([float(v) for v in w.pred_pos.reshape(-1)])
        if w.M != M_GOLD:
            raise SystemExit(f"늑대 수 {w.M} != {M_GOLD}")
        for i in rows:
            i = int(i)
            s_bits = sum((1 << m) for m in range(w.M) if bool(near_h[i, m])) if pan[i] else 0
            r = len(b.row_int)
            b.row_int.append([self.src, tick, i, int(prev[i]), int(nxt[i]), int(bool(alive0[i])), int(executed[i]), int(b_route[i]), int(b_k[i]),
                              int(b_age[i]), int(b_feas[i]), s_bits])
            b.row_in.append([float(w.pos[i, 0]), float(w.pos[i, 1]), float(a0[i, 0]), float(a0[i, 1]), float(dirs[i, 0]), float(dirs[i, 1])])
            b.row_oi.append([int(bool(w.route_decide[i])), int(bool(w.route_onset[i])), int(w.flight_route[i]), int(w.route_k[i]),
                             int(w.route_age[i]), int(w.route_feas[i]), int(bool(w.route_cand_ok[i, ROUTE_SHELTER])), int(w.route_cand_k[i]),
                             int(w._rt_dec_prev[i]), int(bool(inval[i])), int(bool(refeas[i])), int(bool(keep_ok[i]))])
            b.row_od.append([float(w.route_shelter_mu[i]), float(w.route_shelter_e[i]), float(out[i, 0]), float(out[i, 1]),
                             float(w.route_cand_dir[i, ROUTE_SHELTER, 0]), float(w.route_cand_dir[i, ROUTE_SHELTER, 1]), float(keep_mu[i])])
            b.row_obs.append([float(np.float32(v)) for v in w.route_obs[i]])
            self.last_row[i] = r
            self._tags(r, i, pan, on, cur, b_route, inval, refeas, keep_ok, keep_dir, alive0, nxt, dirs, out)
        return out

    def _tags(self, r, i, pan, on, cur, b_route, inval, refeas, keep_ok, keep_dir, alive0, nxt, dirs, out):
        w, b = self.w, self.book
        dec, sok = bool(w.route_decide[i]), bool(w.route_cand_ok[i, ROUTE_SHELTER])
        if pan[i]:
            if on[i]:
                b.tag(r, "onset_two" if sok else "onset_one")
            if inval[i]:
                b.tag(r, "invalid")
                if sok:
                    b.tag(r, "invalid_then_two")
            if refeas[i]:
                b.tag(r, "lock_redecide_two" if sok else "lock_redecide_one")
            if not dec and cur[i] == ROUTE_RUN and w.route_age[i] < ROUTE_LOCK_STEPS and (ROUTE_FEAS_SHELTER if sok else 0) != w.route_feas[i]:
                b.tag(r, "lock_inside_no_redecide")
            if not dec and cur[i] == ROUTE_RUN and w.route_age[i] >= ROUTE_LOCK_STEPS:
                b.tag(r, "run_after_lock_same")
            if not on[i] and b_route[i] < 0:
                b.tag(r, "cur_none")
            if not dec and cur[i] == ROUTE_SHELTER:
                b.tag(r, "shelter_hold")
                kk = int(b.row_int[r][8])
                if math.hypot(w.cov_c[kk, 0] - w.pos[i, 0], w.cov_c[kk, 1] - w.pos[i, 1]) - w.cov_r[kk] <= 0.0:
                    b.tag(r, "shelter_hold_inside")
                if (ROUTE_FEAS_SHELTER if sok else 0) != w.route_feas[i]:
                    b.tag(r, "shelter_hold_feas_changed")
                    if w.route_age[i] >= ROUTE_LOCK_STEPS:
                        b.tag(r, "shelter_hold_after_lock")
                if not np.array_equal(out[i], keep_dir[i]):
                    raise SystemExit("SHELTER 유지 줄의 덮기 방향이 유지 은신처 방향이 아니다")
                b.tag(r, "exec_shelter_hold")
            if keep_ok[i] and float(b.row_od[r][6]) == 0.0:
                b.tag(r, "keep_mu_zero")
            if w.flight_route[i] == ROUTE_RUN and np.array_equal(out[i], dirs[i]):
                b.tag(r, "exec_run")
            if sok:
                b.tag(r, "obs_two")
                o1 = b.row_obs[r][1]
                if o1 == float(np.float32(0.2)):
                    b.tag(r, "obs_reach_min")
            else:
                b.tag(r, "obs_one")
        else:
            if b_route[i] >= 0:
                b.tag(r, "clear_" + ("crouch" if nxt[i] == WF_SHELTER else "end"))
                if alive0[i] and w.alive is not None and not w.alive[i]:
                    b.tag(r, "clear_dead")
        if not any(b.row_obs[r]):
            b.tag(r, "obs_zero")

    def apply_hook(self, req):
        w, b = self.w, self.book
        if w._rt_applied:
            return self._apply(req)
        dec = w.route_decide & (w.wf_mode == WF_PANIC)
        if w.alive is not None:
            dec = dec & w.alive
        idx = np.flatnonzero(dec)
        bd = w.wf_dir[idx].copy()
        sok = w.route_cand_ok[idx, ROUTE_SHELTER].copy()
        ck = w.route_cand_k[idx].copy()
        dp = w._rt_dec_prev[idx].copy()
        self._apply(req)
        req = np.asarray(req)
        for j, i in enumerate(idx):
            i = int(i)
            row = int(self.last_row[i])
            if row < 0:
                raise SystemExit(f"사슴 {i} 의 결정 줄이 적히지 않았다")
            rq = int(req[i])
            chosen = int(w.flight_route[i])
            bad = int(rq == ROUTE_SLOT_SHELTER and not sok[j])
            sw = int(dp[j] >= 0 and chosen != dp[j])
            a = len(b.ap_int)
            b.ap_int.append([row, rq, int(bool(sok[j])), int(ck[j]), chosen, int(w.route_k[i]), bad, sw])
            b.ap_d.append([float(bd[j, 0]), float(bd[j, 1]), float(w.wf_dir[i, 0]), float(w.wf_dir[i, 1])])
            names = ["apply_" + ("shelter" if chosen == ROUTE_SHELTER else "run")]
            if chosen == ROUTE_RUN and sok[j]:
                names.append("apply_run_open")
            if bad:
                names.append("apply_bad")
            if sw:
                names.append("apply_switch")
            if chosen == ROUTE_SHELTER:
                names.append("exec_shelter_apply")
            b.tag(-1 - a, *names)            # 적용 줄 꼬리표는 음수 열쇠 (−1 − 적용 번호)


# --------------------------------------------------------------------- #
# SHELTER 기하 손 사례 (순수 함수)
# --------------------------------------------------------------------- #


def geo_cases(mirror_covers) -> tuple[list, list]:
    """(은신처 묶음 목록, 사례 목록). 사례 = dict(set, p, a0 또는 None(늑대에서 셈), q, S, keep_k, size, mg, kind, want=(k, ok) 또는 None).
    mirror_covers = 거울 세계 은신처 넷 (난수 사례의 묶음)."""
    sets = [
        ("solo", [[30.0, 30.0, 6.0]]),
        ("tie", [[20.0, 30.0, 5.0], [40.0, 30.0, 5.0]]),
        ("two", [[20.0, 30.0, 5.0], [45.0, 30.0, 3.0]]),
        ("wall", [[59.8, 45.0, 3.0], [59.9, 59.9, 0.1]]),
        ("none", []),
        ("far", [[10.0, 30.0, 3.0]]),
        ("wall_low", [[30.0, 0.5, 0.3]]),
        ("mirror", [[float(v) for v in row] for row in mirror_covers]),
    ]
    S0, TIE, TWO, WALL, NONE_, FAR, WALL_LOW, MIRROR = range(8)
    far = [list(v) for v in FAR_WOLVES]
    cases = []
    up = lambda x: float(np.nextafter(float(x), np.inf))      # noqa: E731  1 ulp 위
    dn = lambda x: float(np.nextafter(float(x), -np.inf))     # noqa: E731  1 ulp 밑

    def case(kind, set_k, p, wolf, want, keep_k=-1, s_mask=None, extra=(), a0=None, q_all=None):
        if q_all is None:
            q = [list(map(float, wolf))] + [list(map(float, x)) for x in extra]
            q += far[:M_GOLD - len(q)]
            S = [True] * (1 + len(extra)) + [False] * (M_GOLD - 1 - len(extra)) if s_mask is None else list(s_mask)
        else:
            q, S = [[float(v) for v in x] for x in q_all], list(s_mask)
        cases.append(dict(kind=kind, set=set_k, p=[float(p[0]), float(p[1])], q=q, S=[bool(s) for s in S], keep_k=int(keep_k), size=60.0, mg=1.0,
                          want=want, a0=None if a0 is None else [float(a0[0]), float(a0[1])]))

    # 은신처 (30, 30) r 6. 사슴 (39, 30): |v| 9, e 3, 문 (36, 30)
    case("basic", S0, (39.0, 30.0), (44.0, 30.0), (0, True))                     # μ = 8 − 3 = 5
    case("mu_eq_enter", S0, (39.0, 30.0), (40.0, 33.0), (0, True))               # 문까지 5 → μ = 2 (들어갈 때 문턱 ≥ 2), cos 0.316
    case("mu_below_enter", S0, (39.0, 30.0), (40.0, 33.0 - 1e-9), (-1, False))
    case("cos_eq_zero", S0, (39.0, 30.0), (39.0, 35.0), (0, True))               # a₀ = (0, −1) → cos 0 (≥ 0), μ = √34 − 3
    case("cos_below_zero", S0, (39.0, 30.0), (39.0 - 1e-9, 35.0), (-1, False))
    case("edge_eq_max", S0, (56.0, 30.0), (59.0, 30.0), (0, True))               # e = 20 (≤ 20), μ = 23 − 20
    case("edge_over_max", S0, (56.000001, 30.0), (59.0, 30.0), (-1, False))
    case("inside_cover", S0, (33.0, 30.0), (39.0, 30.0), (-1, False))            # e = −3
    case("on_rim", S0, (36.0, 30.0), (40.0, 30.0), (-1, False))                  # e = 0 (0 < e 이어야)
    case("at_center", S0, (30.0, 30.0), (36.0, 30.0), (-1, False))               # |v| = 0
    case("not_in_S_ignored", S0, (39.0, 30.0), (44.0, 30.0), (0, True), extra=[(36.5, 30.0)],
         s_mask=[True, False, False, False], a0=(-1.0, 0.0))                     # 문 옆 늑대는 S 밖 — μ 셈에서 빠진다
    case("in_S_blocks", S0, (39.0, 30.0), (44.0, 30.0), (-1, False), extra=[(36.5, 30.0)],
         s_mask=[True, True, False, False], a0=(-1.0, 0.0))                      # 같은 늑대가 S 안 — μ < 2
    case("tie_low_index", TIE, (30.0, 30.0), (30.0, 25.0), (0, True))            # e 5·5, cos 0·0 → 낮은 번호
    case("nearest_edge", TWO, (31.0, 30.0), (31.0, 37.0), (0, True))             # e 6 대 11
    case("nearest_blocked", TWO, (31.0, 30.0), (24.0, 31.0), (1, True), a0=(0.0, -1.0))   # 가까운 문 옆 늑대 → 먼 은신처
    case("wall_strip_x", WALL, (59.2, 30.0), (59.2, 20.0), (0, True))            # v = (0.6, 15) — 동쪽 벽 여유 안 → x 성분 지움
    case("wall_strip_all", WALL, (59.5, 59.5), (50.0, 59.5), (1, True), a0=(1.0, 0.0))    # 모서리 — 두 성분 다 지움 → v/|v| 그대로
    case("keep_mu_zero", S0, (39.0, 30.0), (36.0, 33.0), (-1, False), keep_k=0)  # 유지 μ = 3 − 3 = 0 (유지 문턱 ≥ 0), cos < 0
    case("keep_mu_below", S0, (39.0, 30.0), (36.0, 33.0 - 1e-9), (-1, False), keep_k=0)
    case("keep_other", TWO, (31.0, 30.0), (31.0, 37.0), (0, True), keep_k=1)     # 유지 은신처 1 ≠ k* 0
    case("no_covers", NONE_, (30.0, 30.0), (36.0, 30.0), (-1, False))
    # 계획서 10-1 의 1 문턱 ± 1 ulp (입력 한 칸을 1 ulp 옮김 — 사슴 (39, 30), 문 (36, 30), e 3)
    case("mu_ulp_at_enter", S0, (39.0, 30.0), (41.0, 30.0), (0, True))          # |q − 문| = 5 → μ = 2 그대로
    case("mu_ulp_above_enter", S0, (39.0, 30.0), (up(41.0), 30.0), (0, True))
    case("mu_ulp_below_enter", S0, (39.0, 30.0), (dn(41.0), 30.0), (-1, False))
    case("edge_ulp_below_max", S0, (dn(56.0), 30.0), (59.0, 30.0), (0, True))   # e = 20 − 1 ulp 쯤
    case("edge_ulp_above_max", S0, (up(56.0), 30.0), (59.0, 30.0), (-1, False))
    case("keep_mu_ulp_above", S0, (39.0, 30.0), (36.0, up(33.0)), (-1, False), keep_k=0)
    case("keep_mu_ulp_below", S0, (39.0, 30.0), (36.0, dn(33.0)), (-1, False), keep_k=0)
    case("cos_neg_zero", S0, (39.0, 30.0), (39.0, 35.0), (0, True), a0=(0.0, -1.0))   # v·a₀ = −0.0 + −0.0 = −0.0 ≥ 0 (참)
    case("s_empty_inf", S0, (39.0, 30.0), (44.0, 30.0), (0, True), s_mask=[False] * M_GOLD, a0=(-1.0, 0.0))   # S 빔 → μ = +∞ (관측 22 = 1)
    case("keep_behind_far", FAR, (55.0, 30.0), (58.0, 30.0), (-1, False), keep_k=0, a0=(1.0, 0.0))  # 유지 은신처가 뒤쪽·e 42 (후보 밖)인데 μ 3 ≥ 0
    case("keep_at_center", S0, (30.0, 30.0), (36.0, 30.0), (-1, False), keep_k=0)          # |v| = 0 → 유지 방향 영벡터 그대로
    case("keep_center_below_eps", S0, (30.0 + 5e-10, 30.0), (36.0, 30.0), (-1, False), keep_k=0)   # |v| < EPS → v / EPS 를 벽 여유가 단위화
    case("wall_strip_y_low", WALL_LOW, (40.0, 0.6), (48.0, 0.6), (0, True))      # 아래 벽 여유 안 (y ≤ 1) ∧ v_y < 0 → y 성분 지움
    # 난수 사례 (거울 은신처 넷 — 사슴 자리·늑대 넷·S = 거리 ≤ safe_r·유지 은신처를 고르게 뽑는다, 벽 가까이 1/5)
    rng = np.random.default_rng(SEED_GEO)
    size, safe_r = 60.0, 20.0
    for _ in range(N_GEO_RANDOM):
        if rng.random() < 0.2:
            p = np.array([rng.choice([rng.uniform(0.2, 1.5), rng.uniform(58.5, 59.8)]), rng.uniform(1.0, 59.0)])
            if rng.random() < 0.5:
                p = p[::-1].copy()
        else:
            p = rng.uniform(2.0, 58.0, 2)
        ang = rng.uniform(0.0, 2.0 * math.pi, M_GOLD)
        rad = rng.uniform(1.0, 30.0, M_GOLD)
        q = np.clip(p[None, :] + np.c_[rad * np.cos(ang), rad * np.sin(ang)], 0.0, size)
        S = np.sqrt(((q - p) ** 2).sum(1)) <= safe_r
        a0 = None
        if not S.any():
            t = rng.uniform(0.0, 2.0 * math.pi)
            a0 = (math.cos(t), math.sin(t))
        case("random", MIRROR, p, None, None, keep_k=int(rng.integers(-1, len(mirror_covers))), s_mask=S, q_all=q, a0=a0)
    return sets, cases


def run_geo(sets, cases) -> list[dict]:
    out = []
    for c in cases:
        cov = np.asarray([x for x in sets[c["set"]][1]], dtype=np.float64).reshape(-1, 3)
        p = np.asarray(c["p"])
        q = np.asarray(c["q"])
        S = np.asarray(c["S"], dtype=bool)
        a0 = away(p, q[S]) if c["a0"] is None else np.asarray(c["a0"])
        c["a0v"] = [float(a0[0]), float(a0[1])]
        dist = np.sqrt(((q - p) ** 2).sum(1))
        g = flight_route_geometry(p[None], a0[None], q, S[None], dist[None], cov[:, :2], cov[:, 2], np.zeros((0, 3)), c["size"], c["mg"], 5.0,
                                  None, np.array([c["keep_k"]]), None, cover=False)
        k, ok = int(g["shelter_k"][0]), bool(g["shelter_ok"][0])
        if c["want"] is not None and (k, ok) != tuple(c["want"]):
            raise SystemExit(f"기하 사례 {c['kind']}: (k, ok) = {(k, ok)}, 기대 {c['want']}")
        kmu = float(g["keep_mu"][0])
        c["out"] = dict(k=k, ok=ok, keep_ok=bool(g["keep_ok"][0]) if c["keep_k"] >= 0 else False,
                        mu=float(g["shelter_mu"][0]), e=float(g["shelter_e"][0]), dir=[float(v) for v in g["shelter_dir"][0]],
                        keep_mu=kmu if c["keep_k"] >= 0 else 0.0, keep_dir=[float(v) for v in g["keep_dir"][0]])
        out.append(c)
    # 경계 사례가 정말 경계인지 (식이 바뀌면 멈춘다)
    by = {c["kind"]: c for c in out}
    if by["mu_eq_enter"]["out"]["mu"] != ROUTE_SHELTER_ENTER_U or by["edge_eq_max"]["out"]["e"] != ROUTE_SHELTER_MAX_EDGE_U:
        raise SystemExit("μ = 2·e = 20 경계 사례가 정확한 경계가 아니다")
    if by["keep_mu_zero"]["out"]["keep_mu"] != ROUTE_SHELTER_EXIT_U or not by["keep_mu_zero"]["out"]["keep_ok"]:
        raise SystemExit("유지 μ = 0 경계 사례가 정확한 경계가 아니다")
    if by["keep_mu_below"]["out"]["keep_ok"] or by["wall_strip_x"]["out"]["dir"] != [0.0, 1.0]:
        raise SystemExit("유지 바로 밑·벽 여유 사례가 기대와 다르다")
    o = {k: by[k]["out"] for k in by}
    if not (o["mu_ulp_at_enter"]["mu"] == 2.0 and o["mu_ulp_above_enter"]["mu"] > 2.0 and o["edge_ulp_below_max"]["e"] < 20.0
            and o["keep_mu_ulp_above"]["keep_ok"] and o["keep_mu_ulp_above"]["keep_mu"] > 0.0 and not o["keep_mu_ulp_below"]["keep_ok"]
            and o["keep_mu_ulp_below"]["keep_mu"] < 0.0):
        raise SystemExit("± 1 ulp 문턱 사례가 문턱 양쪽에 있지 않다")
    c = by["cos_neg_zero"]
    p, a0, cv = np.asarray(c["p"]), np.asarray(c["a0v"]), sets[c["set"]][1][0]
    vx, vy = cv[0] - p[0], cv[1] - p[1]
    cs = (vx * a0[0] + vy * a0[1]) / max(math.sqrt(vx * vx + vy * vy), EPS)
    if not (cs == 0.0 and math.copysign(1.0, cs) < 0.0):
        raise SystemExit(f"cos −0.0 사례의 cos 가 −0.0 이 아니다: {cs!r}")
    if not (o["s_empty_inf"]["mu"] == math.inf and o["keep_behind_far"]["keep_ok"] and o["keep_at_center"]["keep_dir"] == [0.0, 0.0]
            and o["wall_strip_y_low"]["dir"] == [-1.0, 0.0]):
        raise SystemExit("S 빔·뒤쪽 먼 유지·중심 유지·아래 벽 사례가 기대와 다르다")
    rnd = [c for c in out if c["kind"] == "random"]
    if not (any(c["out"]["ok"] for c in rnd) and any(not c["out"]["ok"] for c in rnd) and any(c["out"]["keep_ok"] for c in rnd)
            and any(c["keep_k"] >= 0 and not c["out"]["keep_ok"] for c in rnd)):
        raise SystemExit("난수 기하 사례가 가능·불가·유지·무효를 다 갖지 않는다")
    return out


# --------------------------------------------------------------------- #
# 손 장면 (거울 세계 그릇의 사슴 0)
# --------------------------------------------------------------------- #


class Bench:
    """거울 세계(길 켬, 사슴 N_BENCH)를 그릇으로 쓴다: 사슴 0 의 길 상태·덮기 전환·늑대 자리를 틱마다 놓고 `_route_step`·`_route_apply` 를 부른다.
    다른 사슴은 늑대에서 먼 곳에 서 있고 도주가 아니다. 은신처 0 = (45, 45) r 6, 사슴 0 = (54, 45)(|v| 9, e 3, 문 (51, 45))."""

    P = (54.0, 45.0)

    def __init__(self, book: Book, name: str):
        cfg = load_v2_config(ROUTE_CFG).replace(N=N_BENCH)
        self.w = w = World(cfg, seeds=[SEED_BENCH])
        if tuple(w.cov_c[0]) != (45.0, 45.0) or w.cov_r[0] != 6.0 or w.M != M_GOLD:
            raise SystemExit("손 장면 그릇: 은신처 0 이 (45, 45) r 6 이 아니거나 늑대 수가 4 가 아니다")
        w._route_reset()
        self.book, self.name = book, name
        self.rec = Rec(w, book, SRC_SCENE, hand=True)
        self.first_row = len(book.row_int)
        self.first_apply = len(book.ap_int)
        self.ticks = 0

    def tick(self, wolf, prev, nxt, before=(ROUTE_NONE, -1, 0, 0), req=None, alive0=True, p=None):
        w = self.w
        N, M = w.N, w.M
        p = self.P if p is None else p
        pos = w.pos.copy()
        pos[0] = p
        for i in range(1, N):
            pos[i] = (30.0 + 2.0 * i, 30.0)
        w.pos = pos
        q = np.array([list(wolf)] + [list(x) for x in FAR_WOLVES[:M - 1]], dtype=np.float64)
        w.pred_pos = q
        r, k, age, feas = before
        w.flight_route = np.full(N, ROUTE_NONE, dtype=np.int8)
        w.flight_route[0] = r
        w.route_k = np.full(N, -1, dtype=np.int64)
        w.route_k[0] = k
        w.route_age = np.zeros(N, dtype=np.int64)
        w.route_age[0] = age
        w.route_feas = np.zeros(N, dtype=np.int8)
        w.route_feas[0] = feas
        prev_a = np.full(N, WF_NONE, dtype=np.int8)
        prev_a[0] = prev
        nxt_a = np.full(N, WF_NONE, dtype=np.int8)
        nxt_a[0] = nxt
        ex = q[:, 0][None, :] - w.pos[:, 0:1]
        ey = q[:, 1][None, :] - w.pos[:, 1:2]
        pd = np.sqrt(ex * ex + ey * ey)
        near_h = pd <= w._wf["safe_r"]
        a0 = np.zeros((N, 2))
        a0[0] = away(p, q[near_h[0]])
        dirs = a0.copy()                         # RUN 방향 = 반사 방향 (손 장면은 은신처 굽히기·가장자리 굽히기 없이 a₀ 그대로)
        executed = np.full(N, ROUTE_NONE, dtype=np.int64)
        executed[0] = r if prev == WF_PANIC else ROUTE_NONE
        alive0_a = np.ones(N, dtype=bool)
        alive0_a[0] = alive0
        self.rec.t = self.ticks
        out = w._route_step(prev_a, nxt_a, dirs, a0, near_h, pd, alive0_a, executed)
        w.wf_mode, w.wf_dir = nxt_a, out
        if req is not None:
            ra = np.full(N, float(FLEE))
            ra[0] = float(req)
            w._route_apply(ra)
        self.book.stats.append(stats_row(w, SRC_SCENE, len(self.book.tick_t) - 1))
        self.ticks += 1
        return dict(decide=bool(w.route_decide[0]), route=int(w.flight_route[0]), k=int(w.route_k[0]), age=int(w.route_age[0]),
                    feas=int(w.route_feas[0]), sok=bool(w.route_cand_ok[0, ROUTE_SHELTER]), obs=w.route_obs[0].copy(), dir=w.wf_dir[0].copy())

    def close(self) -> dict:
        return dict(name=self.name, first_row=self.first_row, rows=len(self.book.row_int) - self.first_row, first_apply=self.first_apply,
                    applies=len(self.book.ap_int) - self.first_apply)


# 사슴 0 = (54, 45), 문 (51, 45)
W_EAST = (59.0, 45.0)              # 문까지 8 → μ = 5 (SHELTER 가능, 관측 (1, 0.5, 0.15))
W_DOOR = (52.0, 46.0)              # 문까지 √2 → μ < 0 (가능 아님·유지 깨짐)
W_MU2 = (55.0, 48.0)               # 문까지 5 → μ = 2 (들어갈 때 문턱 그대로 — 가능, 관측 22 = 0.2)
W_MU2_BELOW = (55.0, 48.0 - 1e-9)  # μ 가 2 바로 밑 — 가능 아님
W_MU1 = (51.0, 49.0)               # 문까지 4 → μ = 1 (유지는 되고 들어갈 때 문턱 밑)
W_MU0 = (51.0, 48.0)               # 문까지 3 → μ = 0 (유지 문턱 그대로)
W_MU0_BELOW = (51.0, 48.0 - 1e-9)  # μ 가 0 바로 밑 — 무효
SH0 = (ROUTE_SHELTER, 0)


def scenes(book: Book) -> list[dict]:
    out = []

    def expect(r, **kw):
        for k, v in kw.items():
            got = r[k]
            if k == "obs":
                got = [float(x) for x in got]
                v = [float(np.float32(x)) for x in v]
            elif k == "dir":
                got = [float(x) for x in got]
            if got != v:
                raise SystemExit(f"손 장면 {sc.name}: {k} = {got}, 기대 {v}")

    sc = Bench(book, "도주 시작 두 칸 → SHELTER → 이음 → 도주 끝")
    expect(sc.tick(W_EAST, WF_NONE, WF_PANIC, req=SLEEP), decide=True, route=ROUTE_SHELTER, k=0, age=0, feas=2, sok=True,
           obs=[1.0, 0.5, 0.15], dir=[-1.0, 0.0])
    expect(sc.tick(W_EAST, WF_PANIC, WF_PANIC, (*SH0, 0, 2)), decide=False, route=ROUTE_SHELTER, k=0, age=1, dir=[-1.0, 0.0])
    expect(sc.tick(W_EAST, WF_PANIC, WF_NONE, (*SH0, 1, 2)), decide=False, route=ROUTE_NONE, k=-1, age=0, feas=0, obs=[0.0, 0.0, 0.0])
    out.append(sc.close())

    sc = Bench(book, "도주 시작 한 칸 (늑대가 문 옆) → RUN → 이음")
    expect(sc.tick(W_DOOR, WF_NONE, WF_PANIC, req=FLEE), decide=True, route=ROUTE_RUN, sok=False, feas=0, obs=[1.0, 0.0, 0.0])
    expect(sc.tick(W_DOOR, WF_PANIC, WF_PANIC, (ROUTE_RUN, -1, 0, 0)), decide=False, route=ROUTE_RUN, age=1)
    out.append(sc.close())

    sc = Bench(book, "한 칸 결정에서 칸 4 (마스크 밖) → RUN·bad_shelter")
    expect(sc.tick(W_DOOR, WF_NONE, WF_PANIC, req=SLEEP), decide=True, route=ROUTE_RUN, sok=False)
    if sc.w._rt_bad_shelter != 1:
        raise SystemExit("bad_shelter 가 1 이 아니다")
    out.append(sc.close())

    sc = Bench(book, "SHELTER 문턱 근처 (μ = 2 가능·바로 밑 불가)")
    expect(sc.tick(W_MU2, WF_NONE, WF_PANIC, req=SLEEP), decide=True, route=ROUTE_SHELTER, sok=True, obs=[1.0, 0.2, 0.15])
    expect(sc.tick(W_MU2_BELOW, WF_NONE, WF_PANIC, req=SLEEP), decide=True, route=ROUTE_RUN, sok=False, obs=[1.0, 0.0, 0.0])
    out.append(sc.close())

    sc = Bench(book, "SHELTER 무효 (늑대가 문에 먼저 — 잠금 안이어도 다시 고름)")
    expect(sc.tick(W_EAST, WF_NONE, WF_PANIC, req=SLEEP), route=ROUTE_SHELTER)
    expect(sc.tick(W_EAST, WF_PANIC, WF_PANIC, (*SH0, 0, 2)), decide=False, route=ROUTE_SHELTER, age=1)
    expect(sc.tick(W_DOOR, WF_PANIC, WF_PANIC, (*SH0, 1, 2), req=FLEE), decide=True, route=ROUTE_RUN, age=0, feas=0, sok=False,
           obs=[1.0, 0.0, 0.0])
    out.append(sc.close())

    sc = Bench(book, "유지 문턱 (μ_k = 0 이음·바로 밑 무효)")
    expect(sc.tick(W_MU0, WF_PANIC, WF_PANIC, (*SH0, 3, 2)), decide=False, route=ROUTE_SHELTER, age=4, sok=False, obs=[1.0, 0.0, 0.0])
    expect(sc.tick(W_MU0_BELOW, WF_PANIC, WF_PANIC, (*SH0, 4, 2), req=FLEE), decide=True, route=ROUTE_RUN, age=0, feas=0)
    out.append(sc.close())

    sc = Bench(book, "무효 뒤 다른 은신처 (두 칸으로 다시 고름 → SHELTER)")
    p = (52.0, 30.0)
    w0 = sc.w
    e0 = math.hypot(45.0 - p[0], 45.0 - p[1]) - 6.0
    door0 = (p[0] + (45.0 - p[0]) * e0 / (e0 + 6.0), p[1] + (45.0 - p[1]) * e0 / (e0 + 6.0))
    r = sc.tick((door0[0] + 0.5, door0[1] + 0.5), WF_PANIC, WF_PANIC, (*SH0, 2, 2), req=SLEEP, p=p)
    expect(r, decide=True, route=ROUTE_SHELTER, sok=True)
    if r["k"] == 0 or w0.route_k[0] != r["k"]:
        raise SystemExit("무효 뒤 다른 은신처를 고르지 않았다")
    out.append(sc.close())

    sc = Bench(book, "RUN 잠금 (2 초 안 그대로·뒤 가능 0 → 1 다시 고름·같으면 그대로·1 → 0 한 칸)")
    expect(sc.tick(W_EAST, WF_PANIC, WF_PANIC, (ROUTE_RUN, -1, 13, 0)), decide=False, age=14, sok=True, feas=0)
    expect(sc.tick(W_EAST, WF_PANIC, WF_PANIC, (ROUTE_RUN, -1, 14, 0), req=SLEEP), decide=True, age=0, feas=2, route=ROUTE_SHELTER)
    expect(sc.tick(W_EAST, WF_PANIC, WF_PANIC, (ROUTE_RUN, -1, 40, 2)), decide=False, age=41, route=ROUTE_RUN)
    expect(sc.tick(W_DOOR, WF_PANIC, WF_PANIC, (ROUTE_RUN, -1, 40, 2), req=FLEE), decide=True, age=0, feas=0, route=ROUTE_RUN)
    expect(sc.tick(W_DOOR, WF_PANIC, WF_PANIC, (ROUTE_RUN, -1, 40, 0)), decide=False, age=41)
    out.append(sc.close())

    sc = Bench(book, "SHELTER 유지 (μ = 1: 잠금 안·뒤 가능 바뀜에도 이음, 방향 = 유지 은신처 쪽)")
    expect(sc.tick(W_MU1, WF_PANIC, WF_PANIC, (*SH0, 3, 2)), decide=False, route=ROUTE_SHELTER, age=4, sok=False, feas=2, dir=[-1.0, 0.0])
    expect(sc.tick(W_MU1, WF_PANIC, WF_PANIC, (*SH0, 40, 2)), decide=False, route=ROUTE_SHELTER, age=41, sok=False, dir=[-1.0, 0.0],
           obs=[1.0, 0.0, 0.0])
    expect(sc.tick(W_EAST, WF_PANIC, WF_PANIC, (*SH0, 40, 2)), decide=False, route=ROUTE_SHELTER, age=41, sok=True)
    out.append(sc.close())

    sc = Bench(book, "지움 (웅크림·도주 끝·경계 — 다음 덮기가 도주가 아님. 죽음 지움은 길 셈 루프 clear_dead 줄)")
    expect(sc.tick(W_EAST, WF_PANIC, WF_SHELTER, (ROUTE_RUN, -1, 5, 2)), route=ROUTE_NONE, k=-1, age=0, feas=0, obs=[0.0, 0.0, 0.0])
    expect(sc.tick(W_EAST, WF_PANIC, WF_NONE, (*SH0, 5, 2)), route=ROUTE_NONE, k=-1, decide=False)
    expect(sc.tick(W_EAST, WF_ALERT, WF_ALERT), route=ROUTE_NONE, decide=False, obs=[0.0, 0.0, 0.0])
    out.append(sc.close())

    # 계획서 2-2 넷째 결정 조건 cur < 0 (길 없는 두뇌 → 판 4 두뇌 교체 때 열린 도주 — 파이썬에서는 시작과 겹쳐 따로 나지 않는다)
    sc = Bench(book, "길 상태 없는 열린 도주 (cur < 0 — 두뇌 교체) → 두 칸 결정 → SHELTER → 이음")
    expect(sc.tick(W_EAST, WF_PANIC, WF_PANIC, (ROUTE_NONE, -1, 0, 0), req=SLEEP), decide=True, route=ROUTE_SHELTER, k=0, age=0, feas=2, sok=True,
           obs=[1.0, 0.5, 0.15], dir=[-1.0, 0.0])
    expect(sc.tick(W_EAST, WF_PANIC, WF_PANIC, (*SH0, 0, 2)), decide=False, route=ROUTE_SHELTER, age=1, dir=[-1.0, 0.0])
    out.append(sc.close())

    sc = Bench(book, "길 상태 없는 열린 도주 (cur < 0) → 한 칸 결정 → RUN")
    expect(sc.tick(W_DOOR, WF_PANIC, WF_PANIC, (ROUTE_NONE, -1, 7, 0), req=FLEE), decide=True, route=ROUTE_RUN, age=0, feas=0, sok=False,
           obs=[1.0, 0.0, 0.0])
    out.append(sc.close())

    sc = Bench(book, "도주 시작 두 칸에서 RUN 고름 (choice 1·picked_run)")
    expect(sc.tick(W_EAST, WF_NONE, WF_PANIC, req=FLEE), decide=True, route=ROUTE_RUN, sok=True, feas=2, obs=[1.0, 0.5, 0.15])
    expect(sc.tick(W_EAST, WF_PANIC, WF_PANIC, (ROUTE_RUN, -1, 0, 2)), decide=False, route=ROUTE_RUN, age=1, sok=True)
    out.append(sc.close())

    sc = Bench(book, "SHELTER 유지 — 은신처 원 안 (e ≤ 0, 방향 = 중심 쪽)")
    expect(sc.tick(W_EAST, WF_PANIC, WF_PANIC, (*SH0, 3, 2), p=(47.0, 45.0)), decide=False, route=ROUTE_SHELTER, k=0, age=4, dir=[-1.0, 0.0])
    out.append(sc.close())

    sc = Bench(book, "SHELTER 무효 → 한 칸 결정에서 칸 4 (마스크 밖 — RUN·bad_shelter·길 바꿈)")
    expect(sc.tick(W_DOOR, WF_PANIC, WF_PANIC, (*SH0, 1, 2), req=SLEEP), decide=True, route=ROUTE_RUN, sok=False, feas=0)
    if sc.w._rt_bad_shelter != 1 or sc.w._rt_switches != 1:
        raise SystemExit("무효 뒤 칸 4 장면: bad_shelter·길 바꿈이 1 이 아니다")
    out.append(sc.close())
    for s in out:
        if s["rows"] < 1:
            raise SystemExit(f"손 장면 {s['name']} 에 줄이 없다")
    # 손 장면 꼬리표 (이름으로 — 세계 줄 꼬리표는 Rec 이 단다)
    for s in out:
        for r in range(s["first_row"], s["first_row"] + s["rows"]):
            book.tag(r, "scene")
    return out


# --------------------------------------------------------------------- #
# 기준 루프·마스크·다시 난 개체
# --------------------------------------------------------------------- #


def loop_policy(w: World, rp: dict, rng, t: int, pattern: int = SHELTER_PATTERN):
    """마스크 안 균등 요청 + 길 결정 줄 무늬 (SHELTER 열렸고 (t·7 + 사슴) % pattern != 0 이면 SHELTER, 아니면 RUN — pattern 0 이면 열리면 늘 SHELTER)."""
    obs = w.observe()
    pk = w.rep_peek()
    m = action_mask(pk, obs, rp, obs_names=w.obs_names)
    a = sample_masked(np.ones(m.shape), m, rng.random(w.N)).astype(np.float64)
    rd = np.asarray(pk["route_decide"], dtype=bool)
    pick = rd & m[:, SLEEP]
    if pattern > 0:
        pick &= ((t * 7 + np.arange(w.N)) % pattern) != 0
    a[rd] = float(FLEE)
    a[pick] = float(SLEEP)
    if not m[np.arange(w.N), a.astype(np.int64)].all():
        raise SystemExit("기준 루프 요청이 마스크 밖이다")
    return a[:, None], pk, m, obs


def mask_kind(pk, m, i) -> int:
    ov, rd = int(pk["override"][i]), bool(pk["route_decide"][i])
    if ov == WF_PANIC:
        if rd:
            return MASK_KINDS.index("dec2" if m[i, SLEEP] else "dec1")
        return MASK_KINDS.index("keep_shelter" if pk["route_now"][i] == ROUTE_SHELTER else "keep_run")
    if ov == WF_SHELTER:
        return MASK_KINDS.index("crouch")
    if pk["wake_decide"][i]:
        return MASK_KINDS.index("other_wake")
    return MASK_KINDS.index("other_reads" if pk["reads"][i] else "other_hold")


def mask_row(kind, pk, m, obs, allowed, i) -> tuple[list[int], list[float]]:
    ri = [int(kind), int(pk["override"][i]), int(bool(pk["route_decide"][i])), int(pk["route_now"][i]), int(bool(pk["reads"][i])),
          int(bool(pk["wake_decide"][i])), int(pk["behavior"][i])] + [int(bool(x)) for x in allowed] + [int(bool(x)) for x in m[i]]
    return ri, [float(np.float32(v)) for v in obs[i]]


def run_loop(book: Book, discs) -> dict:
    cfg = _with(load_v2_config(ROUTE_CFG).replace(N=N_LOOP), wild_weather=dict(region="Forest"), obstacles=dict(fixed=discs["Forest"]),
                wild_satiation=dict(enabled=False))
    w = World(cfg, seeds=[SEED_LOOP])
    if w.alive is None or not w._route_brain or w.M != M_GOLD:
        raise SystemExit("길 셈 루프 세계는 부활 없는 두 길 세계(늑대 4)여야 한다")
    w.track_flight = True
    rp = rep_params(cfg)
    allowed = rp["allowed_mask"]
    rec = Rec(w, book, SRC_LOOP, hand=False)
    rng = np.random.default_rng(LOOP_ACTS_SEED)
    first_row, first_apply, first_stats = len(book.row_int), len(book.ap_int), len(book.stats)
    mask_rows, mask_obs = [], []
    per = {k: 0 for k in MASK_KINDS}
    obs_checks, route_checks, check_t = [], [], []
    deaths = 0
    for t in range(1, LOOP_STEPS + 1):
        a, pk, m, obs = loop_policy(w, rp, rng, t)
        for i in range(w.N):
            if w.alive is not None and not w.alive[i]:
                continue
            k = mask_kind(pk, m, i)
            if per[MASK_KINDS[k]] < MASK_PER_KIND:
                per[MASK_KINDS[k]] += 1
                ri, ro = mask_row(k, pk, m, obs, allowed, i)
                mask_rows.append(ri)
                mask_obs.append(ro)
        rec.t = t
        o, r, d, to = w.step(a)
        deaths += int(d.sum())
        if t % LOOP_STATS_EVERY == 0:
            book.stats.append(stats_row(w, SRC_LOOP, t))
        if t % LOOP_OBS_EVERY == 0:
            check_t.append(t)
            k0 = w.obs_names.index(ROUTE_OBS_NAMES[0])
            obs_checks += [float(np.float32(v)) for v in o[:, k0:k0 + 3].reshape(-1)]
            for i in range(w.N):
                route_checks += [int(w.wf_mode[i]), int(w.flight_route[i]), int(w.route_k[i]), int(w.route_age[i]), int(w.route_feas[i]),
                                 int(bool(w.route_decide[i])), int(bool(w.alive[i]))]
    f = w.flight_stats()
    rb = f["route"]
    fr = flight_route_row(rb)
    return dict(first_row=first_row, rows=len(book.row_int) - first_row, first_apply=first_apply, applies=len(book.ap_int) - first_apply,
                first_stats=first_stats, stats=len(book.stats) - first_stats, mask_rows=mask_rows, mask_obs=mask_obs, mask_per=per,
                obs_checks=obs_checks, route_checks=route_checks, check_t=check_t, flight_route=[int(v) for v in fr], deaths=deaths,
                hide=f["hide"], route_stats={k: v for k, v in rb.items() if k in ("decisions", "choice", "picked", "switches", "invalid")},
                N=w.N, config_digest=ew.config_digest(cfg))


def hand_mask_rows(names) -> tuple[list, list]:
    """손 마스크 줄: 관측 22 가 0 이 아닌 가장 작은 값(0.2)·0, 결정이 지금 길을 이김, 판 2 그 밖 줄."""
    allowed = allowed_mask_of(("graze", "flee", "hide"))
    k22 = list(names).index("shelter_reach")
    rows, obs_rows = [], []
    base = np.zeros(len(names), dtype=np.float32)
    base[list(names).index("pred_count")] = np.float32(0.125)
    base[list(names).index("cover_dist")] = np.float32(0.05)

    def one(override, rdecide, route_now, reads, wake, behavior, o22, gate=False):
        o = base.copy()
        o[k22] = np.float32(o22)
        o[k22 - 1] = np.float32(1.0 if override == WF_PANIC else 0.0)
        pk = dict(override=np.array([override], dtype=np.int8), route_decide=np.array([rdecide]), route_now=np.array([route_now]),
                  reads=np.array([reads]), wake_decide=np.array([wake]), behavior=np.array([behavior], dtype=np.int64))
        if gate:
            pk[FLEE_GATE_KEY] = False           # 판 5 (rep_peek 이 판 5 세계에서 알리는 값 — rep_policy.mask_version_of)
        if gate != (mask_version_of(names, pk.get(FLEE_GATE_KEY, True)) == MASK_VERSION_ROUTE_GATE):
            raise SystemExit("판 5 손 줄의 마스크 판이 5 가 아니다")
        m = action_mask(pk, o[None], {"allowed_mask": allowed}, obs_names=names)
        ri, ro = mask_row(MASK_KINDS.index("gate" if gate else "hand"), pk, m, o[None], allowed, 0)
        rows.append(ri)
        obs_rows.append(ro)

    one(WF_PANIC, True, ROUTE_RUN, True, False, FLEE, 0.2)          # 두 칸 (가장 작은 가능 값)
    one(WF_PANIC, True, ROUTE_RUN, True, False, FLEE, 0.0)          # 한 칸
    one(WF_PANIC, True, ROUTE_SHELTER, True, False, FLEE, 0.0)      # 지금 길 SHELTER 여도 결정이면 RUN (+ 가능이면 4)
    one(WF_PANIC, False, ROUTE_SHELTER, False, False, FLEE, 0.0)    # 비결정 SHELTER 한 칸 (관측 22 와 상관없다)
    one(WF_PANIC, False, ROUTE_RUN, False, False, FLEE, 0.7)        # 비결정 RUN 한 칸
    one(WF_SHELTER, False, ROUTE_NONE, False, False, HIDE, 0.0)     # 웅크림 HIDE 한 칸
    one(WF_NONE, False, ROUTE_NONE, True, False, GRAZE, 0.0)        # 그 밖 결정: 허용 ∧ 가능 (얼기·잠 막힘)
    one(WF_NONE, False, ROUTE_NONE, True, True, GRAZE, 0.0)         # 기상 결정
    one(WF_NONE, False, ROUTE_NONE, False, False, HIDE, 0.0)        # 비결정: 지금 행동 한 칸
    # 10-24 판 5 (이식 계획서 13-3 — 덮기 밖 결정 + 위협을 앎(FLEE 가능)이면 칸 1 막힘, 덮기 줄·비결정은 판 4 그대로)
    one(WF_NONE, False, ROUTE_NONE, True, False, GRAZE, 0.0, gate=True)      # 덮기 밖 결정: 판 2 − 칸 1 = {0, 2}
    one(WF_NONE, False, ROUTE_NONE, True, True, HIDE, 0.0, gate=True)        # 기상 결정: 잠 막힘 + 칸 1 막힘
    one(WF_NONE, False, ROUTE_NONE, False, False, FLEE, 0.0, gate=True)      # 덮기 밖 비결정 FLEE (반사가 끝난 뒤 잠금 중): FLEE 한 칸 그대로
    one(WF_PANIC, True, ROUTE_RUN, True, False, FLEE, 0.2, gate=True)        # 도주 길 결정: {1, 4} 그대로
    one(WF_PANIC, False, ROUTE_SHELTER, False, False, FLEE, 0.0, gate=True)  # 도주 비결정 SHELTER: {4} 그대로
    one(WF_SHELTER, False, ROUTE_NONE, False, False, HIDE, 0.0, gate=True)   # 웅크림: {2} 그대로
    return rows, obs_rows


def run_respawn() -> dict:
    cfg = load_v2_config(R6_CFG).replace(N=N_RESPAWN)
    w = World(cfg, seeds=[SEED_RESPAWN])
    if w.alive is not None or not w._route_brain:
        raise SystemExit("다시 난 개체 세계는 부활이 있는 두 길 세계(R6 학습 세계)여야 한다")
    rp = rep_params(cfg)
    rng = np.random.default_rng(SEED_RESPAWN)
    k0 = w.obs_names.index(ROUTE_OBS_NAMES[0])
    rows, obs_rows = [], []
    got = {ROUTE_RUN: 0, ROUTE_SHELTER: 0}
    seen = {}
    orig = w._wf_update

    def wf_hook(done, caught=None, *rest, **kw):     # 이번 스텝 잡힘 (부활 세계는 death_cause 가 없다 — `_wf_update` 의 인자를 그대로 넘긴다)
        seen["caught"] = None if caught is None else np.asarray(caught, dtype=bool).copy()
        return orig(done, caught, *rest, **kw)

    w._wf_update = wf_hook
    for t in range(1, RESPAWN_STEPS + 1):
        a, pk, m, obs = loop_policy(w, rp, rng, t, RESPAWN_PATTERN)
        # 덮기 실행기가 쓰는 길은 `_route_apply` 뒤 값이다 — 같은 호출을 먼저 해 둔다(멱등, `step` 첫머리 호출은 아무것도 하지 않는다)
        w._route_apply(a[:, 0])
        bm, br, bk, ba, bf = (w.wf_mode.copy(), w.flight_route.astype(np.int64).copy(), w.route_k.copy(), w.route_age.copy(),
                              w.route_feas.astype(np.int64).copy())
        o, r, d, to = w.step(a)
        for i in np.flatnonzero(d):
            i = int(i)
            if br[i] < 0:
                continue
            cg = seen.get("caught")
            cause = 1 if cg is not None and cg[i] else 2
            rows.append([t, i, cause, int(bm[i]), int(br[i]), int(bk[i]), int(ba[i]), int(bf[i]), int(w.wf_mode[i]), int(w.flight_route[i]),
                         int(w.route_k[i]), int(w.route_age[i]), int(w.route_feas[i]), int(bool(w.route_decide[i]))])
            obs_rows.append([float(np.float32(v)) for v in o[i, k0:k0 + 3]] + [float(np.float32(v)) for v in to[i, k0:k0 + 3]])
            got[int(br[i])] += 1
            if to[i, k0:k0 + 3].any():
                raise SystemExit("죽은 사슴의 terminal_obs 길 칸이 0 이 아니다")
        if min(got.values()) >= RESPAWN_WANT:
            break
    if min(got.values()) < 1:
        raise SystemExit(f"다시 난 사건이 길마다 하나 이상 없다: {got}")
    return dict(rows=rows, obs=obs_rows, got={ROUTE_NAMES[k]: v for k, v in got.items()}, steps=t, config_digest=ew.config_digest(cfg))


# --------------------------------------------------------------------- #
# 관측 세 칸 (계획서 3절 WriteRouteObs — float 비트)
# --------------------------------------------------------------------- #


def route_obs_ref(panic: bool, ok: bool, mu: float, e: float) -> list[float]:
    """world.py `_route_step` 의 route_obs 식 그대로: float64 로 clip(μ/10)·clip(e/20) 을 셈해 float32 칸에 넣는다 (도주가 아니면 0, 가능 아니면 뒤 둘 0)."""
    r = np.zeros(3, dtype=np.float32)
    if panic:
        r[0] = 1.0
        r[1] = np.where(ok, np.minimum(np.maximum(np.array([mu]) / ROUTE_SHELTER_REACH_U, 0.0), 1.0), 0.0)[0]
        r[2] = np.where(ok, np.minimum(np.maximum(np.array([e]) / ROUTE_SHELTER_EDGE_NORM_U, 0.0), 1.0), 0.0)[0]
    return [float(v) for v in r]


def obs_cases(book: Book) -> list[tuple]:
    """(panic, ok, μ, e, 관측 세 칸) 사례: 손 값(μ = 2·10·+∞·문턱 위 ulp, e 아주 작음·20·20 밑 ulp, 십진으로 끝나지 않는 몫, 도주 아님·가능 아님) + 난수.
    같은 식이 길 셈 줄(Book)의 세계 관측을 모두 다시 내는지도 본다 (식 = 세계)."""
    hand = [(1, 1, 2.0, 3.0), (1, 1, 10.0, 20.0), (1, 1, math.inf, 5.0), (1, 1, 2.0, 1e-12), (1, 1, 2.0, 5e-324), (1, 1, 12.5, 0.75),
            (1, 1, float(np.nextafter(2.0, 3.0)), float(np.nextafter(20.0, 0.0))), (1, 1, float(np.nextafter(10.0, 11.0)), 7.0),
            (1, 1, 10.0 / 3.0, 20.0 / 3.0), (1, 1, 2.7, 13.1), (1, 1, 4.9999999999999991, 0.30000000000000004), (1, 0, 0.0, 0.0), (0, 0, 0.0, 0.0)]
    rng = np.random.default_rng([SEED_OBS, 1])
    rnd = [(1, 1, float(rng.uniform(2.0, 12.0)), float(rng.uniform(1e-6, 20.0))) for _ in range(N_OBS_RANDOM)]
    out = [(p, o, m, e, route_obs_ref(bool(p), bool(o), m, e)) for p, o, m, e in hand + rnd]
    bad = 0
    for r in range(len(book.row_int)):
        pan = book.row_int[r][4] == WF_PANIC
        ok = bool(book.row_oi[r][6])
        if route_obs_ref(pan, ok, book.row_od[r][0], book.row_od[r][1]) != book.row_obs[r]:
            bad += 1
    if bad:
        raise SystemExit(f"관측 식이 길 셈 줄 {bad} 개의 세계 관측과 다르다")
    return out


# --------------------------------------------------------------------- #
# 기준 루프 — 두뇌 둘 (계획서 10-1 의 5·6)
# --------------------------------------------------------------------- #


def load_route0():
    from stable_baselines3 import PPO

    if not ROUTE0_ZIP.exists():
        raise SystemExit(f"{ROUTE0_ZIP} 없음 (results/v3/route/route_extend.py 가 만든다)")
    return PPO.load(str(ROUTE0_ZIP), device="cpu")


def brain_model(delta: float):
    """route0 zip 에서 만든 길 두뇌: 출력층 칸 4 편향 = 칸 1 편향 + delta (float32 셈), 그 밖은 route0 그대로 (W2[4] = W2[1], 첫 층 18 열 뒤 여섯 열 0).
    delta −2 = route0 그대로 (다시 셈해 같은지 본다), +2 = 늘 SHELTER 시험 두뇌. C++ 은 내장 R1b(kBuiltinNet)를 24 열로 늘려 같은 식으로 만든다."""
    import torch as th

    m = load_route0()
    sd = m.policy.state_dict()
    W, B = sd["action_net.weight"], sd["action_net.bias"]
    if not th.equal(W[ROUTE_SLOT_SHELTER], W[ROUTE_SLOT_RUN]):
        raise SystemExit("route0 의 W2[4] 가 W2[1] 과 다르다")
    for key in ("mlp_extractor.policy_net.0.weight", "mlp_extractor.value_net.0.weight"):
        if sd[key][:, 18:].abs().max().item() != 0.0:
            raise SystemExit(f"route0 의 {key} 18 열 뒤가 0 이 아니다 — C++ 이 내장 R1b 를 24 열로 늘려 만들 수 없다")
    nb = B.clone()
    nb[ROUTE_SLOT_SHELTER] = B[ROUTE_SLOT_RUN] + th.tensor(delta, dtype=B.dtype)
    if delta == ROUTE0_DELTA and not th.equal(nb, B):
        raise SystemExit("route0 의 B2[4] 가 B2[1] − 2 가 아니다")
    sd["action_net.bias"] = nb
    m.policy.load_state_dict(sd, strict=True)
    return m


BUILTIN_WEIGHTS = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy" / "PolicyWeightsV3.h"


def check_builtin_base(model) -> None:
    """기준 루프 두뇌의 바탕 확인 (머리 주석 — C++ 은 내장 R1b kBuiltinNet 을 24 열로 늘려 두뇌를 만든다): route0 의 W0 앞 18 열·B0·W1·B1·W2 0~3 행·
    B2 0~3 = 생성 헤더 PolicyWeightsV3.h 의 kW0·kB0·kW1·kB1·kW2·kB2 (float32 비트), W0 18 열 뒤 0, W2[4] = W2[1]. 읽기만 한다."""
    import re

    if not BUILTIN_WEIGHTS.exists():
        raise SystemExit(f"{BUILTIN_WEIGHTS} 없음 — 내장 R1b 가중치 헤더")
    txt = re.sub(r"//[^\n]*", "", BUILTIN_WEIGHTS.read_text(encoding="utf-8"))
    hb = {}
    for k in ("W0", "B0", "W1", "B1", "W2", "B2"):
        m = re.search(r"\bk%s\[[^\]]*\]\s*=\s*\{(.*?)\};" % k, txt, re.S)
        if m is None:
            raise SystemExit(f"PolicyWeightsV3.h 에 k{k} 가 없다")
        hb[k] = np.array([np.float32(v.strip().rstrip("fF")) for v in m.group(1).split(",") if v.strip()], dtype=np.float32)
    W = ew.extract(model)
    w0 = hb["W0"].reshape(W["W0"].shape[0], -1)
    ok = (w0.shape[1] == 18 and np.array_equal(W["W0"][:, :18], w0) and not W["W0"][:, 18:].any() and np.array_equal(W["B0"], hb["B0"])
          and np.array_equal(W["W1"], hb["W1"].reshape(W["W1"].shape)) and np.array_equal(W["B1"], hb["B1"])
          and np.array_equal(W["W2"][:4], hb["W2"].reshape(W["W2"].shape)[:4]) and np.array_equal(W["W2"][ROUTE_SLOT_SHELTER], W["W2"][ROUTE_SLOT_RUN])
          and np.array_equal(W["B2"][:4], hb["B2"][:4]))
    if not ok:
        raise SystemExit("route0 이 내장 R1b(PolicyWeightsV3.h) + 0 열 + 칸 4 = 칸 1 꼴이 아니다 — C++ 이 같은 두뇌를 만들 수 없다")


def weights_sha(model) -> str:
    import hashlib

    return hashlib.sha256(ew.weights_bytes(ew.extract(model))).hexdigest()


def world_cfg(n: int, route: bool = True):
    cfg = load_v2_config(ROUTE_CFG).replace(N=n)
    return cfg if route else _with(cfg, wild_flight=dict(route=False))


def _same_start(a: World, b: World) -> None:
    """길 켬·끔 두 세계의 시작 상태가 같다 (길은 reset 난수를 쓰지 않는다 — 시작 상태를 길 끈 세계의 평가기 일로 옮길 수 있다)."""
    for k in ("pos", "head", "energy", "pred_pos", "pred_head", "pred_type", "pred_speed", "cov_c", "cov_r", "obstacles", "food", "food_cap"):
        if not np.array_equal(np.asarray(getattr(a, k)), np.asarray(getattr(b, k))):
            raise SystemExit(f"길 켬·끔 시작 상태 {k} 가 다르다")
    if a.rng.bit_generator.state != b.rng.bit_generator.state:
        raise SystemExit("길 켬·끔 시작 난수 상태가 다르다")


def world_hash(w: World, alive0: np.ndarray, req: np.ndarray, tgt: np.ndarray | None = None) -> int:
    """지문 (모듈 docstring '기준 루프 지문'). tgt = 늑대 표적 덮기 (시작 지문은 −1)."""
    N = w.N
    cause = np.asarray(w.death_cause).astype(np.int64)
    keep = np.asarray(w.wf_mode).astype(np.int64)
    reserve = w.reserve if w._wr is not None else np.zeros(N)
    obs = np.asarray(w._obs, dtype=np.float32)
    if obs.shape != (N, 24):
        raise SystemExit(f"관측 칸 수 {obs.shape} — 관측 24 세계여야 한다")
    req = np.asarray(req).reshape(-1).astype(np.int64)
    live = cause == 0
    keep_ok = live & (keep < 2)
    b = bytearray()
    b += np.asarray([w.dark, w.pred_ema], dtype="<f8").tobytes()
    for a in (w.pos[:, 0], w.pos[:, 1], w.head[:, 0], w.head[:, 1], w.energy, reserve):
        b += np.ascontiguousarray(a, dtype="<f8").tobytes()
    b += cause.astype("<i4").tobytes() + keep.astype("<i4").tobytes()
    b += np.asarray(w._rs.behavior)[alive0].astype("<i4").tobytes()
    b += np.ascontiguousarray(obs[alive0], dtype="<f4").tobytes()
    b += req[keep_ok].astype("<i4").tobytes()
    for a in (w.pred_pos[:, 0], w.pred_pos[:, 1], w.pred_head[:, 0], w.pred_head[:, 1]):
        b += np.ascontiguousarray(a, dtype="<f8").tobytes()
    tgt = np.asarray(getattr(w, "pred_target", np.full(w.M, -1)) if tgt is None else tgt, dtype=np.int64)
    for a in (w.pred_cd, getattr(w, "pred_sat", np.zeros(w.M)), tgt):
        b += np.asarray(a).astype("<i4").tobytes()
    rd = np.asarray(w.route_decide, dtype=bool)
    rreq = np.where(rd & (keep == WF_PANIC) & live, req, -1)
    for a in (w.flight_route, w.route_k, w.route_age, w.route_feas, rd, rreq):
        b += np.asarray(a).astype(np.int64)[live].astype("<i4").tobytes()
    pan = live & (keep == WF_PANIC)
    b += np.ascontiguousarray(np.asarray(w.wf_dir, dtype=np.float64)[pan], dtype="<f8").tobytes()
    import hashlib

    return int.from_bytes(hashlib.sha256(bytes(b)).digest()[:8], "little")


ROUTE_STATS_KEYS = ("onsets", "onset_shelter", "decisions", "redecide_feas", "switches", "invalid_shelter", "picked_run", "picked_shelter", "choice",
                    "bad_shelter", "steps_run", "steps_shelter")
HIDE_KEYS = ("chased", "hidden", "watching", "cover_then_caught", "cover_then_starved")


def route_stats_row(rs: dict) -> list[int]:
    return [rs["onsets"], rs["onset_shelter"], rs["decisions"], rs["redecide_feas"], rs["switches"], rs["invalid"]["shelter"], rs["picked"]["run"],
            rs["picked"]["shelter"], rs["choice"], rs["bad_shelter"], rs["steps"]["run"], rs["steps"]["shelter"]]


def flight_route_row(rb: dict) -> list[int]:
    """도망 기록 길 덩어리 (by_route n·steps·contact × 길 다섯 × 끝 까닭, drop_obstacle·chased_steps·hidden_steps × 길 다섯, refled, refled_steps)."""
    names = ROUTE_NAMES + ("none",)
    fr = []
    for key in ("n", "steps", "contact"):
        for nm in names:
            fr += [rb["by_route"][nm][key][c] for c in FLIGHT_CAUSES]
    for key in ("drop_obstacle", "chased_steps", "hidden_steps"):
        fr += [rb[key][nm] for nm in names]
    fr += [rb["refled"], rb["refled_steps"]]
    return [int(v) for v in fr]


def world_check_row(w: World) -> list[int]:
    """잡힘·굶음·산 + 도망 보고 52 칸 (export_golden_v3_foliage.stats_row_any — 49 + lost_foliage 0 0 0) + 길 통계 12 + 숨은 뒤 지켜보기 5."""
    import export_golden_v3_foliage as fg

    cause = np.asarray(w.death_cause)
    f = w.flight_stats()
    return ([int(np.count_nonzero(cause == 1)), int(np.count_nonzero(cause == 2)), int(np.count_nonzero(cause == 0))] + fg.stats_row_any(f)
            + route_stats_row(f["route"]) + [int(f["hide"][k]) for k in HIDE_KEYS])


# --------------------------------------------------------------------- #
# 도망 길 기록 짜 맞춘 장면 (계획서 10-1 의 6 — `_fl_update` 를 재료로 직접 부른다)
# --------------------------------------------------------------------- #

FS_N = 8
FS_TRACK = 6                       # 사슴 칸: _fl_rsteps (run·cover·shelter·open), _fl_last_t, _fl_len
FS_NOT_LAST = -(10 ** 9)           # _fl_last_t 의 '살아 끝난 도망 없음' (reset·죽음)
FS_REFLEE = 38                     # world.py FLIGHT_REFLEE_STEPS (아래에서 같은지 본다)


def flight_scene() -> dict:
    """도망 길 기록 장면 (사슴 8·늑대 4, 틱 = 스텝 번호 s — w.t = s + 1, `step` 이 `_wf_update` 앞에서 t 를 올린 것과 같다). 재료 비트는
    export_golden_v3_flight.py 짜 맞춘 장면과 같다(사슴: 1 FLEE·2 반사·4 죽음·8 잡힘·16 은신처 원 안·32 첫머리 산, 늑대: 1 스텝 끝 사냥·2 고르기 때
    사냥·4 쌍 칸 있음·8 반경 안·16 반경과 시야각 안·32 원판이 가림·64 은신처 표적 제외 — 쌍 = (늑대, 지난 표적)). 더한 재료: 사슴마다 실행한 길(−1 없음).
    시간은 건너뛴다(s = 5 → 10, 11 → 40) — 도망 기록은 받은 스텝 번호만 쓰고, 건너뛰는 틱 앞뒤로 끝나는 도망은 없다.
      d0·d1·d2: s 0~2 RUN 반사, s 3 에 살아 끝남(안 쫓김 — 마지막 끝 스텝 2). d0 은 s 40 에 새 도망(38 스텝 째 — refled), d1 은 s 41 (39 — 아님, SHELTER).
               d2 는 s 5 에 죽고(마지막 끝 스텝을 지움) s 10 에 반사 없는 두뇌 FLEE 로 새 도망(refled 아님) → s 11 끝(길 none).
      d3: RUN 2·SHELTER 2 (동점 → RUN), d4: RUN 1·SHELTER 3 (→ SHELTER), d5: 반사 없는 두뇌 FLEE (→ none). 늑대 0→d3, 1·2→d4, 3→d5 가 s 0·1 에 쫓고
          s 1 은 늑대 2 만 눈길이 트였다(d4 는 가려진 스텝 아님), s 2 에 모두 원판 뒤에서 놓친다(d4 는 늑대 둘 — 놓침 2). s 4 에 끝(obstacle).
      d6: s 3~4 RUN 반사 중 s 4 에 잡힘 → 다음에 s 41 반사 없는 새 도망(죽음 뒤라 refled 아님, 열린 채 — none truncated).
      d7: s 10·11 RUN 반사 + s 40·41 두뇌 FLEE (열린 채 — RUN truncated)."""
    from env_v2.world import FLIGHT_REFLEE_STEPS

    if FLIGHT_REFLEE_STEPS != FS_REFLEE:
        raise SystemExit(f"FLIGHT_REFLEE_STEPS {FLIGHT_REFLEE_STEPS} != {FS_REFLEE} — 장면의 38·39 경계를 다시 짠다")
    w = World(load_v2_config(ROUTE_CFG).replace(N=FS_N), seeds=[SEED_BENCH])
    if w.M != M_GOLD or not w._route_brain or w.alive is None:
        raise SystemExit("도망 길 기록 장면 세계는 부활 없는 두 길 세계(늑대 4)여야 한다")
    if w._ob is not None and w._ob["foliage"] is not None:
        raise SystemExit("도망 길 기록 장면은 숲 시야 끈 세계 (drop_foliage 칸 없음)")
    w.track_flight = True
    w._fl_reset()
    N, M = w.N, w.M
    R_, S_ = ROUTE_RUN, ROUTE_SHELTER
    rows = dict(t=[], deer=[], route=[], wolf=[], block=[], track=[])
    refled_at = {}

    def tick(s, flee=(), reflex=None, done=(), caught=(), tgt=None, blk=()):
        """reflex = {사슴: 실행한 길} (반사 스텝 — FLEE 에도 넣는다). flee 는 반사 없는 두뇌 FLEE 사슴. blk = 원판이 가린 (늑대, 사슴) 쌍."""
        reflex = dict(reflex or {})
        fl = np.zeros(N, dtype=bool)
        fl[list(flee) + list(reflex)] = True
        rx = np.zeros(N, dtype=bool)
        rx[list(reflex)] = True
        re_ = np.full(N, ROUTE_NONE, dtype=np.int64)
        for i, r in reflex.items():
            re_[i] = r
        d = np.zeros(N, dtype=bool)
        d[list(done)] = True
        cg = np.zeros(N, dtype=bool)
        cg[list(caught)] = True
        w.t = s + 1
        w.pred_target = np.full(M, -1, dtype=np.int64) if tgt is None else np.asarray(tgt, dtype=np.int64)
        w.pred_cd = np.zeros(M, dtype=np.int64)
        if getattr(w, "pred_asleep", None) is not None:
            w.pred_asleep = np.zeros(M, dtype=bool)
        if getattr(w, "pred_sat", None) is not None:
            w.pred_sat = np.zeros(M, dtype=np.int64)
        no = np.zeros((M, N), dtype=bool)
        b = no.copy()
        for m, i in blk:
            b[m, i] = True
        w._fl_pred = (np.ones(M, dtype=bool), np.ones((M, N), dtype=bool), np.ones((M, N), dtype=bool), b, no.copy())
        live = ~d
        in_cov = np.zeros(N, dtype=bool)
        # 재료 (export_golden_v3_flight.Recorder 와 같은 비트)
        tp = w._fl_tgt.copy() if w._fl_tgt.shape == (M,) else np.full(M, -1, dtype=np.int64)
        hunt_end = w._wf_hunting()
        fp = w._fl_pred
        bits = []
        for m in range(M):
            x = int(bool(hunt_end[m])) | 2 * int(bool(fp[0][m])) | 4
            i = int(tp[m])
            rng_, vis0, bk, cv = True, True, False, False
            if 0 <= i < N:
                rng_, vis0, bk, cv = bool(fp[1][m, i]), bool(fp[2][m, i]), bool(fp[3][m, i]), bool(fp[4][m, i])
            bits.append(x | 8 * int(rng_) | 16 * int(vis0) | 32 * int(bk) | 64 * int(cv))
        rows["t"].append(int(w.t))
        rows["deer"].append([int(fl[i]) | 2 * int(rx[i]) | 4 * int(d[i]) | 8 * int(cg[i]) | 16 * int(in_cov[i]) | 32 for i in range(N)])
        rows["route"].append([int(v) for v in re_])
        rows["wolf"].append([v for m in range(M) for v in (bits[m], int(w.pred_target[m]), int(tp[m]) if 0 <= tp[m] < N else -1)])
        ref0 = int(w._flr_refled)
        w._fl_update(fl, rx, d, cg, live, in_cov, route_exec=re_)
        refled_at[s] = int(w._flr_refled) - ref0
        rows["block"].append(flight_route_row(w.flight_stats()["route"]))
        rows["track"].append([int(v) for i in range(N) for v in (*w._fl_rsteps[i], w._fl_last_t[i], w._fl_len[i])])

    tgt01 = [3, 4, 4, 5]
    tick(0, flee=[5], reflex={0: R_, 1: R_, 2: R_, 3: R_, 4: R_}, tgt=tgt01)
    tick(1, flee=[5], reflex={0: R_, 1: R_, 2: R_, 3: R_, 4: S_}, tgt=tgt01, blk=[(0, 3), (1, 4), (3, 5)])
    tick(2, flee=[5], reflex={0: R_, 1: R_, 2: R_, 3: S_, 4: S_}, blk=[(0, 3), (1, 4), (2, 4), (3, 5)])
    tick(3, flee=[5], reflex={3: S_, 4: S_, 6: R_})
    tick(4, reflex={6: R_}, done=[6], caught=[6])
    tick(5, done=[2])
    tick(10, flee=[2], reflex={7: R_})
    tick(11, reflex={7: R_})
    tick(40, flee=[7], reflex={0: R_})
    tick(41, flee=[6, 7], reflex={0: R_, 1: S_})
    rb = w.flight_stats()["route"]
    by = rb["by_route"]

    def n(route, cause):
        return by[route]["n"][cause]

    tr = np.asarray(rows["track"][-1]).reshape(N, FS_TRACK)
    checks = {
        "fs_refled_38": refled_at[40] == 1 and rb["refled"] == 1,
        "fs_not_refled_39": refled_at[41] == 0 and int(w._fl_len[1]) == 1,
        "fs_dead_reset": refled_at[10] == 0 and rows["track"][5][2 * FS_TRACK + 4] == FS_NOT_LAST and n("none", "unchased") == 1,
        "fs_tie_run": n("run", "obstacle") == 1 and n("shelter", "obstacle") == 1,
        "fs_none_route": n("none", "obstacle") == 1 and rb["chased_steps"]["none"] == 2 and rb["hidden_steps"]["none"] == 2,
        "fs_drop_per_wolf": rb["drop_obstacle"] == dict(run=0, cover=0, shelter=3, open=0, none=1),
        "fs_hidden_partial": rb["chased_steps"]["shelter"] == 3 and rb["hidden_steps"]["shelter"] == 2 and rb["chased_steps"]["run"] == 1
                             and rb["hidden_steps"]["run"] == 1,
        "fs_truncated": (n("run", "truncated"), n("shelter", "truncated"), n("none", "truncated")) == (2, 1, 1),
        "fs_caught": n("run", "caught") == 1 and n("run", "unchased") == 3,
    }
    if not all(checks.values()) or tuple(tr[:, 4]) != (2, 2, 10, 3, 3, 3, FS_NOT_LAST, FS_NOT_LAST):
        raise SystemExit(f"도망 길 기록 장면이 기대와 다르다: {checks}, refled {refled_at}, 마지막 끝 스텝 {tr[:, 4].tolist()}, by_route "
                         f"{ {k: {c: v for c, v in by[k]['n'].items() if v} for k in by} }")
    return dict(rows=rows, checks=checks, ticks=len(rows["t"]), final=flight_route_row(rb))


def world_loop(seed: int, model) -> dict:
    """거울 세계(사슴 N_WORLD, 부활 없음, 길 켬)를 두뇌 model 의 argmax 로 WORLD_STEPS 스텝. 시작 상태는 길 끈 같은 세계의 평가기 일(ceval.native_job),
    세계 난수는 PCG64 날 64 비트. 모든 결정(산 사슴, 열린 칸 둘 이상)의 1·2위 로짓 차와 두뇌 파일 순전파(numpy float32) argmax 도 잰다."""
    import ceval
    from env_v2.rollout import RepLearned

    w = World(world_cfg(N_WORLD), seeds=[seed])
    off = World(world_cfg(N_WORLD, route=False), seeds=[seed])
    if w.alive is None or not w._route_brain or w.M != M_GOLD or off._route_on:
        raise SystemExit("기준 루프 세계는 부활 없는 두 길 세계(늑대 4)여야 한다")
    _same_start(w, off)
    job = ceval.native_job(dict(seed=seed, region="golden", steps=WORLD_STEPS), 0, world=off)
    w.track_flight = True
    g = np.random.Generator(np.random.PCG64())
    g.bit_generator.state = w.rng.bit_generator.state
    raw = [int(x) for x in g.bit_generator.random_raw(WORLD_STEPS * w.M)]
    pol = RepLearned(model)
    pol.bind_world(w)
    W = ew.extract(model)
    gaps = dict(all=math.inf, route=math.inf, mismatch=0, decisions=0, route_decisions=0)

    def decide():
        obs = w.observe()
        a = pol(obs)[:, 0]
        m = pol.last_mask
        live = np.asarray(w.death_cause) == 0
        lg = ew.forward_np(obs, W, np.float32)
        gaps["mismatch"] += int(np.count_nonzero((ew.masked_argmax(lg, m) != a.astype(np.int64)) & live))
        gp = ew.top_gap(lg, m)
        multi = live & (m.sum(1) >= 2)
        rd = live & np.asarray(w.route_decide, dtype=bool) & (np.asarray(w.wf_mode) == WF_PANIC)
        if multi.any():
            gaps["all"] = min(gaps["all"], float(gp[multi].min()))
            gaps["decisions"] += int(multi.sum())
        if (rd & multi).any():
            gaps["route"] = min(gaps["route"], float(gp[rd & multi].min()))
            gaps["route_decisions"] += int((rd & multi).sum())
        return a

    a = decide()
    hashes = [world_hash(w, np.ones(w.N, dtype=bool), a, np.full(w.M, -1))]
    checks = []
    for t in range(1, WORLD_STEPS + 1):
        alive0 = np.asarray(w.death_cause) == 0
        w.step(a[:, None])
        a = decide()
        hashes.append(world_hash(w, alive0, a))
        if t % WORLD_EVERY == 0:
            checks.append(world_check_row(w))
    if w.rng.bit_generator.state["state"] != g.bit_generator.state["state"]:
        raise SystemExit("기준 루프: 세계 난수가 스텝마다 늑대 M 개 말고도 뽑혔다 — 날 수열로 옮길 수 없다 (계획서 9절 R12)")
    f = w.flight_stats()
    return dict(w=w, job=job, raw=raw, hashes=hashes, checks=checks, final=f, route_row=flight_route_row(f["route"]), gaps=gaps,
                caught=int(np.count_nonzero(np.asarray(w.death_cause) == 1)))


def pick_world(models: list) -> tuple[int, list]:
    """두뇌 둘 모두 근접 동점(< 1e-4)·두뇌 파일 argmax 차가 없고, 늘 SHELTER 두뇌가 SHELTER 를 골라 은신처 길로 끝난 도망이 있고 잡힘이 있는 첫 시드."""
    for seed in WORLD_SEEDS:
        try:
            runs = [world_loop(seed, m) for m in models]
        except ValueError as e:                     # world_block 거부 (예: 야행성 늑대) — 다음 시드
            print(f"  시드 {seed}: {e}")
            continue
        g = [r["gaps"] for r in runs]
        sh = runs[1]["final"]["route"]
        caught = [r["caught"] for r in runs]
        print(f"  시드 {seed}: 최소 로짓 차 {[round(x['all'], 5) for x in g]} (길 결정 {[round(x['route'], 5) for x in g]}), argmax 차 "
              f"{[x['mismatch'] for x in g]}, 잡힘 {caught}, SHELTER 고름 {sh['picked']['shelter']} 은신처 길 도망 "
              f"{sum(sh['by_route']['shelter']['n'].values())} 무효 {sh['invalid']['shelter']}")
        if any(x["all"] < NEAR_TIE or x["mismatch"] for x in g):
            continue
        if sh["picked"]["shelter"] > 0 and sum(sh["by_route"]["shelter"]["n"].values()) > 0 and min(caught) > 0:
            return seed, runs
    raise SystemExit(f"시드 {WORLD_SEEDS} 가운데 기준 루프 조건을 만족하는 시드가 없다")


def world_config_code(wb: dict) -> list[str]:
    """world 블록 → `template <class TConfig> void FillWorldConfig(TConfig& C)` 본문 (export_golden_v3_foliage.config_code 와 같은 대응표 — 모든 칸을
    옮긴다, 모르는 칸이 있으면 멈춘다). 템플릿이라 이 헤더는 EcoWorldV3.h 없이도 컴파일된다(g++ 참조). 날씨 종류는 정수 (EcoWorldV3 kWeather*)."""
    import export_golden_v3_foliage as fg

    def lit(v, kind):
        if kind == "d":
            return d_lit(v)
        if kind in ("i", "i64"):
            return str(int(v))
        if kind == "u64":
            return f"{int(v)}ULL"
        if kind == "b":
            if not isinstance(v, (bool, np.bool_)):
                raise SystemExit(f"참/거짓 칸이 아니다: {v!r}")
            return "true" if v else "false"
        if kind == "weather":
            k = ("clear", "rain", "snow").index(v)
            return f"static_cast<decltype(C.Weather.Kind)>({k})"
        raise SystemExit(kind)

    out, used = [], set()
    for key, lhs, kind in fg.CFG_TOP:
        out.append(f"\t\t{lhs} = {lit(wb[key], kind)};")
        used.add(key)
    for b, v in enumerate(wb["world_allowed"]):
        out.append(f"\t\tC.WorldAllowed[{b}] = {int(v)};")
    used.add("world_allowed")
    for blk, fields in fg.CFG_BLOCKS.items():
        d = wb[blk]
        got = set()
        for key, lhs, kind in fields:
            out.append(f"\t\t{lhs} = {lit(d[key], kind)};")
            got.add(key)
        left = {k for k in d if k not in got and (blk, k) not in fg.CFG_SKIP and (blk, k) not in fg.CFG_OPTIONAL_KEYS}
        if left:
            raise SystemExit(f"world 블록 {blk} 에 C++ 로 옮기지 않은 칸: {sorted(left)}")
        used.add(blk)
    used |= fg.CFG_OPTIONAL_BLOCKS
    left = set(wb) - used
    if left:
        raise SystemExit(f"world 블록에 C++ 로 옮기지 않은 칸: {sorted(left)}")
    if wb["weather"].get("schedule_rows", 0):
        raise SystemExit("날씨 시간표는 옮기지 않는다")
    out += fg.optional_code(wb, lit)           # 10-27 선택 칸 (끈 세계는 줄이 없다 — 옛 골든 바이트 그대로)
    out.append("\t\tC.Obstacles.Foliage.bEnabled = C.Obstacles.bEnabled && C.Obstacles.Foliage.bEnabled;   // EcoV3Eval ConfigOf 와 같다")
    out.append("\t\tC.WildFlight.bRoute = true;   // ★ 두뇌 길 (계획서 1-2 — InitWorld 가 bEnabled 와 묶는다. 평가기는 두뇌 판이 SetModelRoute 로 정한다)")
    out.append("\t\tC.bSenseStats = false;   // 평가기와 같다 (기록만)")
    out.append("\t\tC.bFlightStats = true;")
    return out


# --------------------------------------------------------------------- #
# 덮는지 셈
# --------------------------------------------------------------------- #

PLAN = (
    # (꼬리표, 뜻) — 과제 '도주 시작 결정(두 칸/한 칸), SHELTER 문턱 근처, SHELTER 무효, 2 초 잠금 뒤 RUN 다시 고르기·SHELTER 유지, 관측 21~23,
    # 마스크 판 4 줄, 실행 덮기 방향, 길 통계, 다시 난 개체'
    ("onset_two", "도주 시작 결정 — SHELTER 가능(두 칸)"),
    ("onset_one", "도주 시작 결정 — SHELTER 불가(한 칸)"),
    ("geo_mu_enter_edge", "SHELTER 문턱 근처: μ = 2 가능·바로 밑 불가 (기하)"),
    ("geo_cos_edge", "cos = 0 가능·바로 밑 불가 (기하)"),
    ("geo_e_edge", "e = 20 가능·바로 위 불가 (기하)"),
    ("scene_threshold", "SHELTER 문턱 근처 (손 장면 — 관측 22 = 0.2)"),
    ("obs_reach_min", "관측 22 가 가장 작은 가능 값 0.2"),
    ("invalid", "SHELTER 무효 — 늑대가 문에 먼저 (μ_k < 0)"),
    ("invalid_then_two", "무효 뒤 다른 은신처가 가능한 결정"),
    ("keep_mu_zero", "유지 문턱 μ_k = 0 에서 이음"),
    ("lock_inside_no_redecide", "RUN 잠금 안(age < 15) — 가능이 바뀌어도 그대로"),
    ("lock_redecide_two", "2 초 잠금 뒤 RUN 다시 고르기 (가능 0 → 1, 두 칸)"),
    ("lock_redecide_one", "2 초 잠금 뒤 RUN 다시 고르기 (가능 1 → 0, 한 칸)"),
    ("run_after_lock_same", "잠금 뒤 가능이 같으면 RUN 그대로"),
    ("shelter_hold", "SHELTER 유지 (결정 아님)"),
    ("shelter_hold_after_lock", "잠금 뒤 가능이 바뀌어도 SHELTER 유지 (10-22 고침)"),
    ("obs_two", "관측 21~23 — 도주·SHELTER 가능"),
    ("obs_one", "관측 21~23 — 도주·SHELTER 불가 (1, 0, 0)"),
    ("obs_zero", "관측 21~23 — 도주 아님 (0, 0, 0)"),
    ("clear_end", "도주 끝에 길 지움"),
    ("clear_crouch", "웅크림에 길 지움"),
    ("clear_dead", "죽음(통합 세계 — 부활 없음)에 길 지움"),
    ("exec_run", "실행 덮기 방향 — RUN = 반사 방향 그대로"),
    ("exec_shelter_apply", "실행 덮기 방향 — 결정에서 SHELTER = k* 쪽"),
    ("exec_shelter_hold", "실행 덮기 방향 — SHELTER 유지 = 유지 은신처 쪽"),
    ("geo_wall", "실행 덮기 방향 — 벽 여유 (성분 지움·다 지워짐)"),
    ("apply_shelter", "두뇌 칸 4 → SHELTER"),
    ("apply_run", "두뇌 칸 1 → RUN"),
    ("apply_bad", "칸 4 인데 가능 아님 → RUN·bad_shelter"),
    ("apply_switch", "길 바꿈 셈"),
    ("mask_dec2", "마스크 판 4 — 도주 결정 두 칸"),
    ("mask_dec1", "마스크 판 4 — 도주 결정 한 칸"),
    ("mask_keep_run", "마스크 판 4 — 도주 비결정 RUN"),
    ("mask_keep_shelter", "마스크 판 4 — 도주 비결정 SHELTER"),
    ("mask_crouch", "마스크 판 4 — 웅크림 HIDE"),
    ("mask_other_reads", "마스크 판 4 — 그 밖 결정 (판 2)"),
    ("mask_other_hold", "마스크 판 4 — 그 밖 비결정 (판 2)"),
    ("mask_gate_free", "마스크 판 5 — 덮기 밖 결정에서 칸 1(FLEE) 막힘 (위협을 앎)"),
    ("mask_gate_hold", "마스크 판 5 — 덮기 밖 비결정 FLEE 한 칸은 그대로"),
    ("mask_gate_over", "마스크 판 5 — 도주·웅크림 줄은 판 4 그대로"),
    ("stats_scene", "길 통계 — 손 장면 틱마다"),
    ("stats_loop", "길 통계 — 기준 루프"),
    ("respawn_run", "다시 난 개체 — RUN 길에서 죽음"),
    ("respawn_shelter", "다시 난 개체 — SHELTER 길에서 죽음"),
    # 계획서 10-1 에 맞춰 더한 것 (2-2 넷째 결정 조건, 1 의 문턱 ± 1 ulp·−0.0·dc ≈ EPS·S 빔·후보 밖 유지, 3·5·6 묶음)
    ("cur_none", "길 상태 없는 열린 도주 (cur < 0 — 두뇌 교체) 결정"),
    ("apply_run_open", "SHELTER 가 열린 결정에서 RUN 고름"),
    ("shelter_hold_inside", "SHELTER 유지 — 은신처 원 안 (e ≤ 0)"),
    ("geo_mu_ulp", "μ = 2 ± 1 ulp (기하)"),
    ("geo_e_ulp", "e = 20 ± 1 ulp (기하)"),
    ("geo_keep_ulp", "유지 μ_k = 0 ± 1 ulp (기하)"),
    ("geo_cos_neg_zero", "cos = −0.0 (기하)"),
    ("geo_s_empty", "S 빔 → μ = +∞ (기하)"),
    ("geo_keep_far_behind", "유지 은신처가 후보 밖(뒤쪽·e > 20)인데 유지 (기하)"),
    ("geo_center_eps", "|v| ≤ EPS 의 유지 방향 (기하)"),
    ("geo_random", "난수 기하 사례 (거울 은신처 넷)"),
    ("obs_cases", "관측 세 칸 사례 (μ = 2·10·+∞, e 작은 값·20 — float 비트)"),
    ("world_route0", "기준 루프 지문 — route0 (길 결정 모두 RUN)"),
    ("world_shelter", "기준 루프 지문 — 늘 SHELTER 시험 두뇌 (SHELTER 고름)"),
    ("fr_by_route_run", "도망 길 기록 — RUN 길 도망 by_route"),
    ("fr_by_route_shelter", "도망 길 기록 — SHELTER 길 도망 by_route"),
    ("fr_chased", "도망 길 기록 — 쫓긴 FLEE 스텝 (길별)"),
    ("fr_drop", "도망 길 기록 — 원판 놓침 (길별)"),
    ("fr_hidden", "도망 길 기록 — 쫓는 늑대 모두에게 가려진 FLEE 스텝 (길별)"),
    ("fr_refled", "도망 길 기록 — 다시 도망 (refled)"),
    # 계획서 10-1 의 6 짜 맞춘 장면 (세계 루프에 없는 경계 — flight_scene)
    ("fs_refled_38", "도망 길 기록 장면 — 살아 끝난 도망 뒤 38 스텝 째 새 도망은 refled"),
    ("fs_not_refled_39", "도망 길 기록 장면 — 39 스텝 째 새 도망은 refled 아님"),
    ("fs_dead_reset", "도망 길 기록 장면 — 죽음이 마지막 끝 스텝을 지움 (다시 난 개체의 새 도망은 refled 아님)"),
    ("fs_tie_run", "도망 길 기록 장면 — 길별 반사 스텝 동점은 앞 번호(RUN)"),
    ("fs_none_route", "도망 길 기록 장면 — 반사 없는 두뇌 FLEE 도망·놓침·쫓김은 none"),
    ("fs_drop_per_wolf", "도망 길 기록 장면 — 원판 놓침은 늑대마다 센다"),
    ("fs_hidden_partial", "도망 길 기록 장면 — 쫓는 늑대 하나라도 눈길이 트이면 가려진 스텝 아님"),
    ("fs_truncated", "도망 길 기록 장면 — 열린 도망은 보고 때 길별 truncated"),
    ("fs_caught", "도망 길 기록 장면 — 반사 도주 중 잡힘(caught)·안 쫓긴 끝(unchased)"),
)
FR_CAUSES = len(FLIGHT_CAUSES)
FR_ROUTES = len(ROUTE_NAMES) + 1
FR_LEN = 3 * FR_ROUTES * FR_CAUSES + 3 * FR_ROUTES + 2
WORLD_CHECK_LEN = 3 + 52 + len(ROUTE_STATS_KEYS) + len(HIDE_KEYS)       # 잡힘·굶음·산 + 도망 보고 52 + 길 통계 12 + 숨은 뒤 지켜보기 5
WC_PICKED_RUN = 3 + 52 + ROUTE_STATS_KEYS.index("picked_run")
WC_PICKED_SHELTER = 3 + 52 + ROUTE_STATS_KEYS.index("picked_shelter")


def coverage(data: dict) -> dict:
    """계획 꼬리표마다 줄 수 (data = 이 파일이 쓴 JSON 을 읽은 dict — 시험이 같은 함수를 부른다)."""
    c = {k: 0 for k, _ in PLAN}
    tags = data["tags"]
    for names in tags["rows"]:
        for nm in names:
            if nm in c:
                c[nm] += 1
    for names in tags["applies"]:
        for nm in names:
            if nm in c:
                c[nm] += 1
    for nm in tags["scenes"]:
        if nm in c:
            c[nm] += 1
    gi = data["kGeoInt"]
    gk = [data["meta"]["geo_kinds"][gi[3 * j + 2]] for j in range(len(gi) // 3)]
    c["geo_mu_enter_edge"] = int("mu_eq_enter" in gk and "mu_below_enter" in gk)
    c["geo_cos_edge"] = int("cos_eq_zero" in gk and "cos_below_zero" in gk)
    c["geo_e_edge"] = int("edge_eq_max" in gk and "edge_over_max" in gk)
    c["geo_wall"] = int("wall_strip_x" in gk and "wall_strip_all" in gk)
    nk = len(MASK_INT)
    mk = [data["kMaskInt"][nk * j] for j in range(len(data["kMaskInt"]) // nk)]
    for kind in ("dec2", "dec1", "keep_run", "keep_shelter", "crouch", "other_reads", "other_hold"):
        c["mask_" + kind] = sum(1 for x in mk if MASK_KINDS[x] == kind)
    mr = [data["kMaskInt"][nk * j:nk * (j + 1)] for j in range(len(data["kMaskInt"]) // nk)]
    gr = [r for r in mr if MASK_KINDS[r[0]] == "gate"]      # 칸: kind·override·rdecide·route_now·reads·wake·behavior·a0..a4·m0..m4
    c["mask_gate_free"] = sum(1 for r in gr if r[1] == WF_NONE and r[4] and r[7 + FLEE] and not r[12 + FLEE])
    c["mask_gate_hold"] = sum(1 for r in gr if r[1] == WF_NONE and not r[4] and r[6] == FLEE and r[12 + FLEE])
    c["mask_gate_over"] = sum(1 for r in gr if r[1] in (WF_PANIC, WF_SHELTER))
    ns = len(STATS_INT)
    st = data["kStatsInt"]
    c["stats_scene"] = sum(1 for j in range(len(st) // ns) if st[ns * j] == SRC_SCENE)
    c["stats_loop"] = sum(1 for j in range(len(st) // ns) if st[ns * j] == SRC_LOOP)
    nr = len(RESPAWN_INT)
    rr = data["kRespawnInt"]
    c["respawn_run"] = sum(1 for j in range(len(rr) // nr) if rr[nr * j + 4] == ROUTE_RUN)
    c["respawn_shelter"] = sum(1 for j in range(len(rr) // nr) if rr[nr * j + 4] == ROUTE_SHELTER)
    c["geo_mu_ulp"] = int("mu_ulp_above_enter" in gk and "mu_ulp_below_enter" in gk)
    c["geo_e_ulp"] = int("edge_ulp_below_max" in gk and "edge_ulp_above_max" in gk)
    c["geo_keep_ulp"] = int("keep_mu_ulp_above" in gk and "keep_mu_ulp_below" in gk)
    c["geo_cos_neg_zero"] = int("cos_neg_zero" in gk)
    c["geo_s_empty"] = int("s_empty_inf" in gk)
    c["geo_keep_far_behind"] = int("keep_behind_far" in gk)
    c["geo_center_eps"] = int("keep_at_center" in gk and "keep_center_below_eps" in gk)
    c["geo_random"] = sum(1 for k in gk if k == "random")
    c["obs_cases"] = len(data["kObsCaseInt"]) // 2
    wc = data["kWorldCheck"]
    nb, nck = len(WORLD_BRAINS), len(wc) // (len(WORLD_BRAINS) * WORLD_CHECK_LEN)
    last = [wc[(b * nck + nck - 1) * WORLD_CHECK_LEN:(b * nck + nck) * WORLD_CHECK_LEN] for b in range(nb)]
    full = len(data["kWorldHash"]) == nb * (data["meta"]["world"]["steps"] + 1)
    c["world_route0"] = int(full and last[0][WC_PICKED_SHELTER] == 0) * last[0][WC_PICKED_RUN]
    c["world_shelter"] = int(full) * last[1][WC_PICKED_SHELTER]
    fr = [data["kWorldFlightRoute"][b * FR_LEN:(b + 1) * FR_LEN] for b in range(nb)] + [data["kLoopFlightRoute"]]
    rsum = lambda r: sum(row[r * FR_CAUSES + j] for row in fr for j in range(FR_CAUSES))      # noqa: E731  길 r 의 by_route n 합
    base = 3 * FR_ROUTES * FR_CAUSES
    c["fr_by_route_run"] = rsum(ROUTE_RUN)
    c["fr_by_route_shelter"] = rsum(ROUTE_SHELTER)
    c["fr_drop"] = sum(row[base + j] for row in fr for j in range(FR_ROUTES))
    c["fr_chased"] = sum(row[base + FR_ROUTES + j] for row in fr for j in range(FR_ROUTES))
    c["fr_hidden"] = sum(row[base + 2 * FR_ROUTES + j] for row in fr for j in range(FR_ROUTES))
    c["fr_refled"] = sum(row[base + 3 * FR_ROUTES] for row in fr)
    fsc = data["meta"].get("flight_scene", {}).get("checks", {})
    for k in ("fs_refled_38", "fs_not_refled_39", "fs_dead_reset", "fs_tie_run", "fs_none_route", "fs_drop_per_wolf", "fs_hidden_partial",
              "fs_truncated", "fs_caught"):
        c[k] = int(bool(fsc.get(k)) and len(data.get("kFsBlock", ())) == data["meta"]["flight_scene"]["ticks"] * FR_LEN)
    return c


# --------------------------------------------------------------------- #
# 조립 (헤더와 JSON 은 같은 배열 목록에서 나온다)
# --------------------------------------------------------------------- #


def d_lit(x) -> str:
    v = float(x)
    if math.isinf(v):
        return "1e300" if v > 0 else "-1e300"
    if math.isnan(v):
        raise SystemExit("골든에 NaN 이 있다")
    s = repr(v)
    return s if ("." in s or "e" in s) else s + ".0"


def _fin(x: float) -> float:
    v = float(x)
    if math.isnan(v):
        raise SystemExit("골든에 NaN 이 있다")
    return INF_LIT if v == math.inf else (-INF_LIT if v == -math.inf else v)


def build() -> dict:
    """모든 묶음을 만들어 {meta, consts, arrays(이름 → (C 꼴, 값, 줄당, 설명)), tags} 를 돌려준다."""
    check_seeds(SEED_RESPAWN, SEED_LOOP, SEED_BENCH, SEED_GEO, SEED_OBS, *WORLD_SEEDS)
    if not all(32080 <= s <= 32099 for s in (SEED_GEO, SEED_OBS, SEED_RESPAWN, SEED_LOOP, SEED_BENCH, *WORLD_SEEDS)):
        raise SystemExit("골든 시드는 탐색 시드 32080~32099 안이어야 한다 (계획서 10-1 의 5)")
    cfg = load_v2_config(ROUTE_CFG)
    names = obs_names(cfg)
    if len(names) != 24 or tuple(names[21:]) != ROUTE_OBS_NAMES or mask_version_of(names) != MASK_VERSION_ROUTE:
        raise SystemExit(f"관측 24·판 4 세계가 아니다: {names}")
    chash = ew.contract_hash(names, MASK_VERSION_ROUTE)
    if chash != CONTRACT_OBS24:
        raise SystemExit(f"계약 해시 0x{chash:016x} != 0x{CONTRACT_OBS24:016x}")
    if (ROUTE_SLOT_RUN, ROUTE_SLOT_SHELTER, ROUTE_SLOT_RESERVED) != (FLEE, SLEEP, FREEZE) or (FLEE, SLEEP, FREEZE) != (1, 4, 3):
        raise SystemExit("길 칸 번호가 바뀌었다")
    if (ROUTE_NONE, ROUTE_RUN, ROUTE_SHELTER) != (-1, 0, 2) or (WF_NONE, WF_ALERT, WF_PANIC, WF_SHELTER) != (0, 1, 2, 3):
        raise SystemExit("길·덮기 번호가 바뀌었다")
    probe = World(cfg.replace(N=8), seeds=[SEED_BENCH])
    wf = probe._wf
    book = Book()
    sets, gcases = geo_cases(np.c_[probe.cov_c, probe.cov_r].tolist())
    gcases = run_geo(sets, gcases)
    sc = scenes(book)
    discs = region_discs()
    lp = run_loop(book, discs)
    rs = run_respawn()
    hm, ho = hand_mask_rows(names)
    mask_int = hm + lp["mask_rows"]
    mask_obs = ho + lp["mask_obs"]
    oc = obs_cases(book)
    models = [brain_model(d) for _, d in WORLD_BRAINS]
    wsha = [weights_sha(m) for m in models]
    r0 = json.loads(ROUTE0_BRAIN.read_text(encoding="utf-8"))
    if wsha[0] != r0["weights_sha256"]:
        raise SystemExit(f"route0 가중치 sha256 {wsha[0][:16]} 이 두뇌 파일 {r0['weights_sha256'][:16]} 과 다르다")
    check_builtin_base(models[0])
    fs = flight_scene()
    print("기준 루프 시드 고르기 (두뇌 route0·늘 SHELTER):")
    wseed, wruns = pick_world(models)
    wjob = wruns[0]["job"]
    if wruns[1]["job"] != wjob or wruns[1]["raw"] != wruns[0]["raw"]:
        raise SystemExit("두뇌 둘의 기준 루프 시작 상태·난수가 다르다")
    wsplit = next((k for k, (x, y) in enumerate(zip(wruns[0]["hashes"], wruns[1]["hashes"])) if x != y), None)
    if wsplit is None:
        raise SystemExit("두뇌 둘의 기준 루프 지문이 같다 — SHELTER 가 한 번도 걸리지 않았다")

    # 꼬리표 (줄·적용·장면 이름) — 손 장면 이름 꼬리표
    scene_tags = []
    for s in sc:
        if "문턱" in s["name"]:
            scene_tags.append("scene_threshold")
    row_tags = [sorted(book.tags.get(r, ())) for r in range(len(book.row_int))]
    ap_tags = [sorted(book.tags.get(-1 - a, ())) for a in range(len(book.ap_int))]

    geo_kinds = list(dict.fromkeys(c["kind"] for c in gcases))      # 같은 종류(난수)는 한 번
    A: list[tuple] = []        # (C 꼴, 이름, 값 목록, 줄당, 설명)

    def arr(ctype, name, vals, per, comment=""):
        A.append((ctype, name, list(vals), per, comment))

    # 은신처 묶음: 0 = 거울 세계 은신처 넷, 1.. = 기하 손 묶음
    cs_index, cs_data = [], []
    all_sets = [("mirror", np.c_[probe.cov_c, probe.cov_r].tolist())] + sets
    for _, rows in all_sets:
        cs_index += [len(cs_data) // 3, len(rows)]
        for x in rows:
            cs_data += [float(v) for v in x]
    arr("std::int32_t", "kCoverSetIndex", cs_index, 16, "묶음마다 (첫 원 번호, 원 수). 0 = 거울 세계 은신처 넷(기준 루프·손 장면), 1.. = 기하 손 묶음")
    arr("double", "kCoverSetData", cs_data, 6, "원마다 (x, y, r)")
    gi, gin, gq, gs, goi, god = [], [], [], [], [], []
    for c in gcases:
        gi += [c["set"] + 1, c["keep_k"], geo_kinds.index(c["kind"])]
        gin += [c["p"][0], c["p"][1], c["a0v"][0], c["a0v"][1], c["size"], c["mg"]]
        for m in range(M_GOLD):
            gq += [c["q"][m][0], c["q"][m][1]]
        gs.append(sum(1 << m for m in range(M_GOLD) if c["S"][m]))
        o = c["out"]
        goi += [o["k"], int(o["ok"]), int(o["keep_ok"])]
        god += [_fin(v) for v in (o["mu"], o["e"], o["dir"][0], o["dir"][1], o["keep_mu"], o["keep_dir"][0], o["keep_dir"][1])]
    arr("std::int32_t", "kGeoInt", gi, 15, "사례마다 " + "·".join(GEO_INT) + " (set = kCoverSetIndex 묶음, kind = kGeoKinds)")
    arr("double", "kGeoIn", gin, 6, "사례마다 " + "·".join(GEO_IN))
    arr("double", "kGeoThreat", gq, 8, "사례마다 늑대 4 × (x, y)")
    arr("std::int32_t", "kGeoS", gs, 24, "사례마다 S 비트 (늑대 m → 1 << m)")
    arr("std::int32_t", "kGeoOutI", goi, 15, "사례마다 " + "·".join(GEO_OUT_I))
    arr("double", "kGeoOutD", god, 7, "사례마다 " + "·".join(GEO_OUT_D) + " (keep_* 는 keep_k ≥ 0 일 때만 뜻이 있다, 아니면 0)")
    arr("std::int32_t", "kTickT", book.tick_t, 20, "틱마다 스텝 번호 (손 장면은 장면 안 틱 번호)")
    arr("double", "kTickThreat", [v for row in book.tick_q for v in row], 8, "틱마다 늑대 4 × (x, y) (스텝 끝)")
    arr("std::int32_t", "kRowInt", [v for row in book.row_int for v in row], 12, "줄마다 " + "·".join(ROW_INT))
    arr("double", "kRowIn", [v for row in book.row_in for v in row], 6, "줄마다 " + "·".join(ROW_IN))
    arr("std::int32_t", "kRowOutI", [v for row in book.row_oi for v in row], 12, "줄마다 " + "·".join(ROW_OUT_I))
    arr("double", "kRowOutD", [_fin(v) for row in book.row_od for v in row], 7, "줄마다 " + "·".join(ROW_OUT_D))
    arr("float", "kRowObs", [v for row in book.row_obs for v in row], 6, "줄마다 관측 21~23 (in_panic·shelter_reach·shelter_edge)")
    arr("std::int32_t", "kApplyInt", [v for row in book.ap_int for v in row], 16, "적용마다 " + "·".join(APPLY_INT))
    arr("double", "kApplyD", [v for row in book.ap_d for v in row], 4, "적용마다 " + "·".join(APPLY_D))
    arr("std::int32_t", "kStatsInt", [v for row in book.stats for v in row], 14, "통계마다 " + "·".join(STATS_INT))
    arr("std::int32_t", "kSceneIndex", [v for s in sc for v in (s["first_row"], s["rows"], s["first_apply"], s["applies"])], 16,
        "손 장면마다 (첫 줄, 줄 수, 첫 적용, 적용 수)")
    arr("std::int32_t", "kLoopIndex", [lp["first_row"], lp["rows"], lp["first_apply"], lp["applies"], lp["first_stats"], lp["stats"]], 6,
        "길 셈 루프 (첫 줄, 줄 수, 첫 적용, 적용 수, 첫 통계, 통계 수)")
    arr("std::int32_t", "kLoopCheckT", lp["check_t"], 12, "관측·길 상태를 적은 스텝")
    arr("float", "kLoopObsCheck", lp["obs_checks"], 12, "확인마다 사슴 32 × 관측 21~23")
    arr("std::int32_t", "kLoopRouteCheck", lp["route_checks"], 14, "확인마다 사슴 32 × (덮기, 길, k, age, feas, 결정, 산)")
    arr("std::int64_t", "kLoopFlightRoute", lp["flight_route"], 11,
        "끝 도망 기록 길 덩어리(선택): by_route n·steps·contact × 길(run·cover·shelter·open·none) × 끝 까닭 11, drop_obstacle·chased_steps·"
        "hidden_steps × 길 5, refled, refled_steps")
    arr("std::int32_t", "kMaskInt", [v for row in mask_int for v in row], 17, "줄마다 " + "·".join(MASK_INT) + " (a = 허용, m = 마스크)")
    arr("float", "kMaskObs", [v for row in mask_obs for v in row], 8, "줄마다 관측 24")
    arr("std::int32_t", "kRespawnInt", [v for row in rs["rows"] for v in row], 14, "사건마다 " + "·".join(RESPAWN_INT))
    arr("float", "kRespawnObs", [v for row in rs["obs"] for v in row], 6, "사건마다 다시 난 사슴 관측 21~23, 죽은 사슴 terminal_obs 21~23")
    arr("std::int32_t", "kObsCaseInt", [v for p, o, _, _, _ in oc for v in (p, o)], 24, "관측 사례마다 (도주, SHELTER 가능)")
    arr("double", "kObsCaseIn", [_fin(v) for _, _, m, e, _ in oc for v in (m, e)], 4, "관측 사례마다 (μ*, e*) — +∞ 는 kInf")
    arr("float", "kObsCaseOut", [v for *_, r in oc for v in r], 6, "관측 사례마다 관측 21~23 (WriteRouteObs 결과 float 비트)")
    # 기준 루프 (두뇌 둘): 시작 상태 = 평가기 일 (길 끈 같은 세계 — 길은 reset 에 난수를 쓰지 않는다)
    arr("float", "kWorldBrainDelta", [d for _, d in WORLD_BRAINS], 4, "두뇌마다 출력층 칸 4 편향 = 칸 1 편향 + 이 값 (W2[4] = W2[1], 첫 층은 내장 R1b 18 열 + 0 여섯 열)")
    dj, wv, fd = wjob["deer"], wjob["wolves"], wjob["food"]
    if dj["slot"] != list(range(N_WORLD)) or [a["slot"] for a in wv] != list(range(M_GOLD)):
        raise SystemExit("기준 루프 슬롯이 0..N−1 · 0..M−1 이 아니다")
    arr("double", "kWorldCovers", np.asarray(wjob["covers"], dtype=np.float64).reshape(-1), 6, "은신처 (x, y, r)")
    arr("double", "kWorldDiscs", np.asarray(wjob["discs"], dtype=np.float64).reshape(-1), 6, "원판 (평가기 일 discs 꼴 그대로 — 원판마다 칸 kWorldDiscCols)")
    arr("double", "kWorldCap", fd["cap"], 6, "먹이 용량 (gw × gw, 행 우선)")
    arr("double", "kWorldFood", fd["food"], 6, "먹이")
    arr("double", "kWorldRegen", fd["regen"], 6, "재생률")
    arr("double", "kWorldDeer", [v for i in range(N_WORLD) for v in (dj["x"][i], dj["y"][i], dj["hx"][i], dj["hy"][i], dj["energy"][i], dj["reserve"][i])],
        6, "사슴 (슬롯 순서) x, y, hx, hy, energy, reserve")
    arr("std::int32_t", "kWorldDeerRepro", dj["repro_cd"], 24, "사슴 번식 쿨다운")
    arr("double", "kWorldWolves", [v for a in wv for v in (a["x"], a["y"], a["hx"], a["hy"], a["speed"])], 5, "늑대 (위협 슬롯 순서) x, y, hx, hy, 기본 속력")
    arr("std::int32_t", "kWorldWolfStalker", [int(a["kind"] == "stalker") for a in wv], 8, "늑대 잠행형인가")
    arr("std::uint64_t", "kWorldRaw", wruns[0]["raw"], 4, "세계 난수: numpy PCG64 날 64 비트 (스텝마다 늑대 슬롯 순서 배회 선회 — FRng::External)")
    arr("std::uint64_t", "kWorldHash", [h for r in wruns for h in r["hashes"]], 4, "두뇌마다 지문 kWorldSteps + 1 개 (0 번 = 시작, 머리 주석 '기준 루프 지문')")
    arr("std::int64_t", "kWorldCheck", [v for r in wruns for row in r["checks"] for v in row], 12,
        f"두뇌마다 {WORLD_EVERY} 스텝마다 잡힘·굶음·산 + 도망 보고 52 + 길 통계 12 ({'·'.join(ROUTE_STATS_KEYS)}) + 숨은 뒤 지켜보기 5 ({'·'.join(HIDE_KEYS)})")
    arr("std::int64_t", "kWorldFlightRoute", [v for r in wruns for v in r["route_row"]], 11, "두뇌마다 끝 도망 기록 길 덩어리 (kLoopFlightRoute 와 같은 꼴)")
    # 도망 길 기록 짜 맞춘 장면 (계획서 10-1 의 6 — 머리 주석 '도망 길 기록 장면')
    fr_ = fs["rows"]
    arr("std::int32_t", "kFsTickT", fr_["t"], 16, "틱마다 w.t (= 스텝 번호 + 1 — C++ FlightUpdate 의 StepNow = 이 값 − 1)")
    arr("std::int32_t", "kFsDeer", [v for row in fr_["deer"] for v in row], 16, "틱마다 사슴 kFsN 재료 비트 (1 FLEE·2 반사·4 죽음·8 잡힘·16 은신처 원 안·32 첫머리 산)")
    arr("std::int32_t", "kFsRoute", [v for row in fr_["route"] for v in row], 16, "틱마다 사슴 kFsN 실행한 길 (−1 없음 — 반사 스텝만 쓴다)")
    arr("std::int32_t", "kFsWolf", [v for row in fr_["wolf"] for v in row], 12,
        "틱마다 늑대 4 × (재료 비트, 이번 표적, 지난 표적 _fl_tgt) — 비트 1 스텝 끝 사냥·2 고르기 때 사냥·4 쌍 칸 있음·8 반경 안·16 시야각 안·32 원판이 가림·"
        "64 은신처 표적 제외 (쌍 = 늑대, 지난 표적)")
    arr("std::int64_t", "kFsBlock", [v for row in fr_["block"] for v in row], 11, "틱마다 그 뒤 도망 기록 길 덩어리 (kLoopFlightRoute 와 같은 꼴, 열린 도망은 truncated)")
    arr("std::int64_t", "kFsTrack", [v for row in fr_["track"] for v in row], 12,
        "틱마다 사슴 kFsN × (길별 반사 스텝 run·cover·shelter·open, 마지막 살아 끝난 도망의 끝 스텝 — 없으면 kFsNotLast, 열린 도망 FLEE 스텝 수)")

    consts = [
        ("std::uint64_t", "kContractHashObs24Mask4", f"0x{CONTRACT_OBS24:016x}ULL", CONTRACT_OBS24, "export_weights_v3.contract_hash(관측 24, 판 4)"),
        ("std::int32_t", "kObsDim", "24", 24, ""),
        ("std::int32_t", "kRouteObsFirst", "21", 21, "관측 21·22·23 = in_panic·shelter_reach·shelter_edge"),
        ("std::int32_t", "kMaskVersion", str(MASK_VERSION_ROUTE), MASK_VERSION_ROUTE, ""),
        ("std::int32_t", "kSlotRun", str(ROUTE_SLOT_RUN), ROUTE_SLOT_RUN, "도주 중 칸 1 = RUN"),
        ("std::int32_t", "kSlotShelter", str(ROUTE_SLOT_SHELTER), ROUTE_SLOT_SHELTER, "도주 중 칸 4 = SHELTER"),
        ("std::int32_t", "kSlotReserved", str(ROUTE_SLOT_RESERVED), ROUTE_SLOT_RESERVED, "칸 3 = COVER 자리 (판 4 에서 늘 막힘)"),
        ("std::int32_t", "kRouteNone", str(ROUTE_NONE), ROUTE_NONE, "길 번호 (파이썬 ROUTE_*)"),
        ("std::int32_t", "kRouteRun", str(ROUTE_RUN), ROUTE_RUN, ""),
        ("std::int32_t", "kRouteShelter", str(ROUTE_SHELTER), ROUTE_SHELTER, ""),
        ("std::int32_t", "kFeasShelter", str(ROUTE_FEAS_SHELTER), ROUTE_FEAS_SHELTER, "가능 비트 (판 4 는 SHELTER 하나)"),
        ("std::int32_t", "kModeNone", str(WF_NONE), WF_NONE, "덮기 번호 (WF_* = C++ kKeep*)"),
        ("std::int32_t", "kModeAlert", str(WF_ALERT), WF_ALERT, ""),
        ("std::int32_t", "kModePanic", str(WF_PANIC), WF_PANIC, ""),
        ("std::int32_t", "kModeShelter", str(WF_SHELTER), WF_SHELTER, ""),
        ("std::int32_t", "kLockSteps", str(ROUTE_LOCK_STEPS), ROUTE_LOCK_STEPS, "결정 뒤 2 초"),
        ("double", "kMaxEdgeU", d_lit(ROUTE_SHELTER_MAX_EDGE_U), ROUTE_SHELTER_MAX_EDGE_U, "0 < e ≤ 20"),
        ("double", "kCosMin", d_lit(ROUTE_SHELTER_COS_MIN), ROUTE_SHELTER_COS_MIN, "v·a₀/|v| ≥ 0"),
        ("double", "kEnterU", d_lit(ROUTE_SHELTER_ENTER_U), ROUTE_SHELTER_ENTER_U, "들어갈 때 μ ≥ 2"),
        ("double", "kExitU", d_lit(ROUTE_SHELTER_EXIT_U), ROUTE_SHELTER_EXIT_U, "유지 μ ≥ 0"),
        ("double", "kReachNormU", d_lit(ROUTE_SHELTER_REACH_U), ROUTE_SHELTER_REACH_U, "관측 22 = clip(μ*/10)"),
        ("double", "kEdgeNormU", d_lit(ROUTE_SHELTER_EDGE_NORM_U), ROUTE_SHELTER_EDGE_NORM_U, "관측 23 = clip(e*/20)"),
        ("double", "kEps", d_lit(EPS), EPS, "|v| > EPS"),
        ("double", "kInf", d_lit(INF_LIT), INF_LIT, "±∞ 표기"),
        ("double", "kWorldSize", d_lit(probe.size), float(probe.size), "거울 세계 무대 한 변"),
        ("double", "kWallMargin", d_lit(wf["wall_margin"]), float(wf["wall_margin"]), "벽 여유 (SHELTER 방향 → wf_wall_keep)"),
        ("double", "kSafeR", d_lit(wf["safe_r"]), float(wf["safe_r"]), "S = 깨어 있는 늑대 ∧ 거리 ≤ safe_r (hold_awake)"),
        ("std::int32_t", "kThreats", str(M_GOLD), M_GOLD, ""),
        ("std::int32_t", "kObsPredCount", str(list(names).index("pred_count")), list(names).index("pred_count"), "판 2 가능 칸 재료 (마스크 줄)"),
        ("std::int32_t", "kObsThreatRecency", str(list(names).index("threat_recency")), list(names).index("threat_recency"), ""),
        ("std::int32_t", "kObsCoverDist", str(list(names).index("cover_dist")), list(names).index("cover_dist"), ""),
        ("float", "kThreatRecencyObs", ew.f32_lit(THREAT_RECENCY_OBS), float(np.float32(THREAT_RECENCY_OBS)),
         "위협을 앎 = pred_count > 0 ∨ threat_recency ≥ 이 값 (float 끼리)"),
        ("float", "kHideCoverObs", ew.f32_lit(HIDE_COVER_OBS), float(np.float32(HIDE_COVER_OBS)), "HIDE 가능 = 위협을 앎 ∧ cover_dist < 이 값"),
        ("std::int32_t", "kCoverSets", str(len(all_sets)), len(all_sets), ""),
        ("std::int32_t", "kGeoCases", str(len(gcases)), len(gcases), ""),
        ("std::int32_t", "kTicks", str(len(book.tick_t)), len(book.tick_t), ""),
        ("std::int32_t", "kRows", str(len(book.row_int)), len(book.row_int), ""),
        ("std::int32_t", "kApplies", str(len(book.ap_int)), len(book.ap_int), ""),
        ("std::int32_t", "kStats", str(len(book.stats)), len(book.stats), ""),
        ("std::int32_t", "kScenes", str(len(sc)), len(sc), ""),
        ("std::int32_t", "kLoopN", str(lp["N"]), lp["N"], "길 셈 루프 사슴 수 (기준 루프 kWorldN 과 다른 루프)"),
        ("std::int32_t", "kLoopSteps", str(LOOP_STEPS), LOOP_STEPS, ""),
        ("std::int32_t", "kLoopChecks", str(len(lp["check_t"])), len(lp["check_t"]), ""),
        ("std::int32_t", "kMaskRows", str(len(mask_int)), len(mask_int), ""),
        ("std::int32_t", "kRespawnRows", str(len(rs["rows"])), len(rs["rows"]), ""),
        ("std::int32_t", "kObsCases", str(len(oc)), len(oc), "관측 세 칸 사례 수"),
        ("std::int32_t", "kFlightRouteLen", str(FR_LEN), FR_LEN, "도망 기록 길 덩어리 칸 수 (kLoopFlightRoute·kWorldFlightRoute 한 벌)"),
        ("std::int32_t", "kWorldBrains", str(len(WORLD_BRAINS)), len(WORLD_BRAINS), "기준 루프 두뇌 수 (0 = route0, 1 = 늘 SHELTER 시험 두뇌)"),
        ("std::int32_t", "kWorldSeed", str(wseed), wseed, "기준 루프 세계 시드 (탐색 시드 — 판정 시드 밖)"),
        ("std::int32_t", "kWorldN", str(N_WORLD), N_WORLD, ""),
        ("std::int32_t", "kWorldM", str(M_GOLD), M_GOLD, ""),
        ("std::int32_t", "kWorldSteps", str(WORLD_STEPS), WORLD_STEPS, ""),
        ("std::int32_t", "kWorldEvery", str(WORLD_EVERY), WORLD_EVERY, ""),
        ("std::int32_t", "kWorldChecks", str(len(wruns[0]["checks"])), len(wruns[0]["checks"]), "두뇌마다 기록 줄 수"),
        ("std::int32_t", "kWorldCheckLen", str(WORLD_CHECK_LEN), WORLD_CHECK_LEN, ""),
        ("std::int32_t", "kWorldFirstSplit", str(wsplit), wsplit, "두뇌 둘의 지문이 처음 다른 번호 (기록만)"),
        ("std::int32_t", "kWorldCoverCount", str(len(wjob["covers"])), len(wjob["covers"]), ""),
        ("std::int32_t", "kWorldDiscCount", str(len(wjob["discs"])), len(wjob["discs"]), ""),
        ("std::int32_t", "kWorldDiscCols", str(np.asarray(wjob["discs"]).shape[1]), int(np.asarray(wjob["discs"]).shape[1]), ""),
        ("std::int32_t", "kWorldGw", str(int(fd["gw"])), int(fd["gw"]), ""),
        ("double", "kWorldCell", d_lit(fd["cell"]), float(fd["cell"]), ""),
        ("double", "kWorldMinTopGap", d_lit(min(r["gaps"]["all"] for r in wruns)), float(min(r["gaps"]["all"] for r in wruns)),
         f"두뇌 둘의 모든 결정(산 사슴, 열린 칸 ≥ 2)에서 1·2위 로짓 차 최솟값 (numpy float32 — 근접 동점 {NEAR_TIE:g} 보다 커야 한다)"),
        ("std::int32_t", "kFsN", str(FS_N), FS_N, "도망 길 기록 장면 사슴 수 (늑대 kThreats)"),
        ("std::int32_t", "kFsTicks", str(fs["ticks"]), fs["ticks"], ""),
        ("std::int32_t", "kFsTrackLen", str(FS_TRACK), FS_TRACK, "사슴 칸 수 (kFsTrack)"),
        ("std::int64_t", "kFsNotLast", f"{FS_NOT_LAST}LL", FS_NOT_LAST, "마지막 살아 끝난 도망 없음 (reset·죽음 — world.py _fl_last_t)"),
        ("std::int32_t", "kFsRefleeSteps", str(FS_REFLEE), FS_REFLEE, "살아 끝난 도망 뒤 이 스텝 안 새 도망 = refled (FLIGHT_REFLEE_STEPS, 경계 포함)"),
    ]
    meta = dict(
        format="eco_v3_route_golden", version=1,
        config="configs/v3_wild3_route_mirror.yaml", config_respawn="configs/v3_r6_train.yaml",
        loop_config_digest=lp["config_digest"], respawn_config_digest=rs["config_digest"],
        seeds=dict(respawn=SEED_RESPAWN, loop=SEED_LOOP, bench=SEED_BENCH, loop_acts=LOOP_ACTS_SEED),
        obs_names=list(names), route_names=list(ROUTE_NAMES), flight_causes=list(FLIGHT_CAUSES),
        geo_kinds=geo_kinds, cover_sets=[n for n, _ in all_sets], scenes=[s["name"] for s in sc], mask_kinds=list(MASK_KINDS),
        fields=dict(row_int=ROW_INT, row_in=ROW_IN, row_out_i=ROW_OUT_I, row_out_d=ROW_OUT_D, apply_int=APPLY_INT, apply_d=APPLY_D,
                    stats_int=STATS_INT, geo_int=GEO_INT, geo_in=GEO_IN, geo_out_i=GEO_OUT_I, geo_out_d=GEO_OUT_D, mask_int=MASK_INT,
                    respawn_int=RESPAWN_INT),
        loop=dict(deaths=lp["deaths"], mask_per=lp["mask_per"], hide=lp["hide"], route=lp["route_stats"]),
        respawn=dict(got=rs["got"], steps=rs["steps"]),
        flight_scene=dict(n=FS_N, ticks=fs["ticks"], checks={k: bool(v) for k, v in fs["checks"].items()}),
        plan="AdaptiveEcosystem/Docs/RL_Policy/RL_V3_ROUTE_CPP_PORT_PLAN.md 10-1 (묶음 1 기하·2 길 단계/적용·3 관측·4 마스크·5 기준 루프·6 도망 길 기록)",
        world=dict(seed=wseed, n=N_WORLD, steps=WORLD_STEPS, every=WORLD_EVERY, config="configs/v3_wild3_route_mirror.yaml",
                   config_digest=ew.config_digest(world_cfg(N_WORLD)), world_block=wjob["world"], route=True, first_split=wsplit,
                   check_fields=["caught", "starved", "alive"] + [f"flight[{j}]" for j in range(52)] + list(ROUTE_STATS_KEYS) + list(HIDE_KEYS),
                   brains=[dict(name=nm, delta=d, weights_sha256=s, source="ckpt/v3/v3_r1_g995_s3_obs24route0.zip" + ("" if d == ROUTE0_DELTA else
                                                                                                                      f" + B2[4] = B2[1] + {d:g}"),
                                min_top_gap=r["gaps"]["all"], min_route_gap=r["gaps"]["route"] if math.isfinite(r["gaps"]["route"]) else None,
                                decisions=r["gaps"]["decisions"], route_decisions=r["gaps"]["route_decisions"], argmax_mismatch=r["gaps"]["mismatch"],
                                caught=r["caught"], route={k: v for k, v in r["final"]["route"].items() if k in ("decisions", "choice", "picked",
                                                                                                                  "switches", "invalid")},
                                hide=r["final"]["hide"])
                           for (nm, d), s, r in zip(WORLD_BRAINS, wsha, wruns)]),
    )
    tags = dict(rows=row_tags, applies=ap_tags, scenes=scene_tags)
    data = dict(meta=meta, consts={n: v for _, n, _, v, _ in consts}, arrays={n: v for _, n, v, _, _ in A}, tags=tags)
    flat = dict(meta=meta, tags=tags, **{n: v for _, n, v, _, _ in A})
    cov = coverage(flat)
    miss = [k for k, v in cov.items() if v <= 0]
    if miss:
        raise SystemExit(f"골든이 계획 장면을 다 덮지 않는다: {miss}")
    data["coverage"] = cov
    return dict(data=data, consts=consts, arrays=A, scenes=sc, loop=lp, respawn=rs, geo=gcases, obs=oc,
                world=dict(seed=wseed, runs=wruns, job=wjob, split=wsplit, sha=wsha))


def render_header(b: dict) -> str:
    d = b["data"]
    m = d["meta"]
    cov = d["coverage"]
    L = [
        "// 자동 생성 — herbivore_rl/export_golden_v3_route.py (손으로 고치지 않는다). 세계 configs/v3_wild3_route_mirror.yaml (다시 난 개체는",
        f"// configs/v3_r6_train.yaml), 탐색 시드 {SEED_RESPAWN}(다시 난)·{SEED_LOOP}(길 셈 루프)·{SEED_BENCH}(손 장면·도망 길 기록 장면)·{SEED_GEO}(난수 기하·관측)·"
        f"{b['world']['seed']}(기준 루프). 같은 내용 JSON = {JSON_NAME} (배열 이름이 같다).",
        "// v3 두 길 두뇌(RUN·SHELTER — 설계 Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 16절) 장면 골든. 정의: herbivore_rl/env_v2/world.py 모듈 docstring",
        "// '야생 1단계' (w3) 두뇌 길 (`_route_step`·`_route_apply`·`flight_route_geometry` SHELTER·`route_stats`), env_v2/rep_policy.py 마스크 판 4.",
        "// 10-24 C++ 이식: 검사 본문 Tests/RouteGoldenCheckV3.h (g++ herbivore_rl/tests/cpp/route_v3_main.cpp — 엔진 함수), 같은 내용 JSON 은",
        "// herbivore_rl/results/v3/route/port/ (판 단위 궤적 지문·세계 기록 옆).",
        "//",
        "// 길 셈 한 줄 (사슴 하나, 스텝 끝 H — `_route_step`). 입력: prev_mode·next_mode(덮기 WF_*), alive0(스텝 첫머리 산), executed(이번 스텝에 실행한 길 —",
        "//   길 통계 steps), 전 상태 b_route·b_k·b_age·b_feas, 사슴 자리 p, a₀(은신처 굽히기 전 반사 방향), run(반사 최종 방향 — 은신처 굽히기·가장자리·벽 뒤),",
        "//   틱의 늑대 자리(kTickThreat), S 비트(깨어 있고 거리 ≤ safe_r 인 늑대 — 도주 줄만), 은신처 = kCoverSetIndex 0, 무대 kWorldSize·벽 kWallMargin.",
        "//   onset = next 도주 ∧ prev 도주 아님. cur = onset ? NONE : b_route. 도주 줄만 기하: k* = argmin e (후보 = |v| > EPS ∧ 0 < e ≤ 20 ∧ cos ≥ 0 ∧",
        "//   μ ≥ 2, 같으면 낮은 번호), 유지 = cur SHELTER 면 μ_{b_k} ≥ 0. invalid = cur SHELTER ∧ ¬유지. feas = sok ? 2 : 0. age = onset ? 0 : b_age + 1.",
        "//   refeas = cur ≥ 0 ∧ ¬invalid ∧ age ≥ 15 ∧ feas ≠ b_feas ∧ cur ≠ SHELTER. decide = onset ∨ cur < 0 ∨ invalid ∨ refeas.",
        "//   출력: route = decide ? RUN : cur (도주 아니면 NONE), k = route SHELTER ? b_k : −1, age = decide ? 0 : age, feas = decide ? feas : b_feas,",
        "//   dir = route SHELTER ? 유지 방향(keep_dir) : run (도주 아니면 run 그대로 — 덮기 방향은 반사 줄이 정한다), mu·e = sok ? μ*·e* : 0,",
        "//   sh = SHELTER 후보 방향(k* 쪽 → wf_wall_keep), 관측 = 도주 ? (1, sok ? clip(μ*/10) : 0, sok ? clip(e*/20) : 0) : 0 (float),",
        "//   dec_prev = decide ? cur : −1 (길 바꿈 셈), 도주가 아니면 route NONE·k −1·age 0·feas 0.",
        "// 적용 한 줄 (다음 스텝 첫머리 `_route_apply` — 그 사슴의 결정 줄 row): req == 4 ∧ sok 면 SHELTER(k = cand_k, dir = sh), 아니면 RUN(dir 그대로).",
        "//   bad = req == 4 ∧ ¬sok (마스크 밖 — 학습·판정에서는 0), switch = dec_prev ≥ 0 ∧ 고른 길 ≠ dec_prev.",
        "// 길 통계 (route_stats, 두뇌 길): onsets·onset_shelter·decisions·redecide_feas 는 `_route_step`, switches·picked·choice·bad_shelter 는 적용,",
        "//   invalid_shelter 는 무효, steps_* = 산(alive0) 사슴의 executed 길별 수.",
        "// 마스크 판 4 한 줄: override 도주면 결정 ? {1, 4 (관측 22 > 0)} : {지금 길 한 칸}, 웅크림이면 {2}, 그 밖 = 판 2 (a ∧ 가능 ∧ reads, 기상 결정은 잠",
        "//   막음, reads 가 아니면 지금 행동 한 칸). reads·wake 는 판 4 미리 보기 값(덮기 스텝은 결정이 아니다).",
        "//   종류 'gate' 줄은 판 5 (= 판 4 + 반사 밖 두뇌 FLEE 막음 — 이식 계획서 13-1): override 가 도주·웅크림이 아니고 reads 면 칸 1 도 막는다.",
        "// 관측 세 칸 한 사례 (WriteRouteObs(bPanic, bOk, Mu, E) — 계획서 3절): 도주 ? (1, ok ? (float)clip(μ/10) : 0, ok ? (float)clip(e/20) : 0) : 0.",
        "//   double 로 나누고(역수 곱 아님) clip 한 뒤 float 로 내린다(가까운 짝수). μ = +∞ 는 1.",
        "// 기준 루프 (계획서 10-1 의 5·6, 두뇌 둘): 거울 세계(부활 없음, 길 켬) kWorldN 마리 kWorldSteps 스텝. 시작 상태 = 길 끈 같은 시드 세계의 평가기 일",
        "//   (ceval.native_job — 길은 reset 난수를 쓰지 않아 같다) + FillWorldConfig 의 bRoute, 세계 난수 = kWorldRaw (PCG64 날 64 비트). 두뇌 = 내장 R1b",
        "//   (kBuiltinNet) 첫 층을 24 열로 늘리고(새 여섯 열 0) 출력층 W2[4] = W2[1], B2[4] = B2[1] + kWorldBrainDelta (float). 가중치 sha256 = kWorldBrainSha256",
        "//   (0 = route0 — results/v3/route/brains 두뇌 파일과 같다, 1 = 늘 SHELTER 시험 두뇌 — 학습·판정에 쓰지 않는다). 결정은 마스크 argmax.",
        "//   기준 루프 지문 (스텝마다, 리틀 엔디언 바이트를 이 순서로 이어 sha256 → 앞 8 바이트 리틀 엔디언 uint64 — FoliageGoldenVectorsV3.h 지문 + 길):",
        "//   f64 dark·pred_ema · f64 x·y·hx·hy·energy·reserve (칸마다 N) · i32 death_cause·wf_mode (N) · i32 행동 (스텝 첫머리 산 슬롯) · f32 관측 24 (같은",
        "//   슬롯, 행 우선) · i32 다음 요청 (스텝 끝 산 ∧ 덮기 < 2) · f64 늑대 x·y·hx·hy (M) · i32 쿨다운·배부름·표적 (−1 없음) · i32 길·route_k·route_age·",
        "//   route_feas·route_decide·route_req (칸마다 스텝 끝 산 슬롯 — route_req = 길 결정(route_decide ∧ 도주) 사슴의 두뇌 출력 1·4, 아니면 −1) · f64",
        "//   덮기 방향 x, y (스텝 끝 산 ∧ 도주 슬롯, 행 우선 — H 뒤·다음 A 앞의 KeepDir). 0 번 = 시작 상태(첫 관측·첫 요청 뒤, 표적 −1).",
        "// 도망 길 기록 장면 (계획서 10-1 의 6, kFs*): 틱마다 재료(kFsDeer·kFsRoute·kFsWolf, 스텝 번호 kFsTickT − 1)를 FlightUpdate(+ 길 기록 RS)에",
        "//   그대로 먹이면 그 뒤 길 덩어리 = kFsBlock, 사슴 칸 = kFsTrack. 길 칸 ri = 반사 ∧ 길 ≥ 0 ? 길 : none(4). 살아 끝난 도망은 끝 스텝 = StepNow − 1 을",
        "//   남기고(kFsTrack 넷째), 새 도망은 StepNow − 그 값 ≤ kFsRefleeSteps 면 refled, 죽음(재료 4)은 kFsNotLast 로 지운다. 원판 놓침은 늑대마다, 쫓김·",
        "//   가림은 사슴마다(쫓는 늑대 모두의 쌍이 원판에 가려야 가림). 시간은 건너뛰지만(5 → 10, 11 → 40) 건너뛰는 틱 앞뒤로 끝나는 도망은 없다.",
        "// ±∞ 는 kInf (1e300) 로 적는다. double 은 다시 읽으면 같은 값이 되는 가장 짧은 표기, float 는 f32 가장 짧은 표기.",
        f"// 줄 {len(d['arrays']['kRowInt']) // len(ROW_INT)} (손 장면 {sum(s['rows'] for s in b['scenes'])} · 길 셈 루프 {b['loop']['rows']}), "
        f"적용 {len(d['arrays']['kApplyInt']) // len(APPLY_INT)}, 기하 {len(b['geo'])}, 마스크 {len(d['arrays']['kMaskInt']) // len(MASK_INT)}, "
        f"다시 난 {len(b['respawn']['rows'])}, 통계 {len(d['arrays']['kStatsInt']) // len(STATS_INT)}, 관측 사례 {len(b['obs'])}, "
        f"기준 루프 시드 {b['world']['seed']} × 두뇌 {len(WORLD_BRAINS)}, 도망 길 기록 장면 틱 {d['meta']['flight_scene']['ticks']}.",
        "// 덮는 계획 꼬리표 (줄 수): " + ", ".join(f"{k} {v}" for k, v in cov.items()),
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace EcoWorldV3::GoldenRoute",
        "{",
        "\t// ---- 계약·상수 ----",
    ]
    for ctype, name, lit, _, comment in b["consts"]:
        L.append(f"\tinline constexpr {ctype} {name} = {lit};" + (f"   // {comment}" if comment else ""))
    L.append("\tinline constexpr const char* kRouteObsNames[3] = {" + ", ".join(f'"{n}"' for n in ROUTE_OBS_NAMES) + "};")
    L.append("\tinline constexpr const char* kGeoKinds[" + str(len(m["geo_kinds"])) + "] = {" + ", ".join(f'"{n}"' for n in m["geo_kinds"]) + "};")
    L.append("\tinline constexpr const char* kMaskKinds[" + str(len(MASK_KINDS)) + "] = {" + ", ".join(f'"{n}"' for n in MASK_KINDS) + "};")
    L.append("\tinline constexpr const char* kWorldBrainNames[" + str(len(WORLD_BRAINS)) + "] = {" + ", ".join(f'"{n}"' for n, _ in WORLD_BRAINS) + "};")
    L.append("\tinline constexpr const char* kWorldBrainSha256[" + str(len(WORLD_BRAINS)) + "] = {" + ", ".join(f'"{s}"' for s in b["world"]["sha"]) + "};")
    L.append("")
    L.append("\t/** 기준 루프 세계 설정 (평가기 일의 world 블록 — EcoV3Eval.cpp ConfigOf 와 같은 대응 + 두뇌 길). TConfig = EcoWorldV3::FWorldConfig. */")
    L.append("\ttemplate <class TConfig>")
    L.append("\tinline void FillWorldConfig(TConfig& C)")
    L.append("\t{")
    L += world_config_code(b["world"]["job"]["world"])
    L.append("\t}")
    L.append("")
    fmt = {"double": d_lit, "float": ew.f32_lit, "std::int32_t": ew._i32, "std::int64_t": lambda v: f"{int(v)}LL",
           "std::uint64_t": lambda v: f"{int(v)}ULL"}
    for ctype, name, vals, per, comment in b["arrays"]:
        if ctype == "std::uint64_t":                 # np.asarray 가 2^63 넘는 파이썬 정수를 float64 로 바꾸지 않게 (c_array 는 np.asarray 를 건다)
            vals = np.asarray(vals, dtype=np.uint64)
            if [int(v) for v in vals] != [int(v) for v in b["data"]["arrays"][name]]:
                raise SystemExit(f"{name}: uint64 배열 값이 바뀌었다")
        L.append(ew.c_array(ctype, name, vals, per, fmt[ctype], comment))
    L.append("}")
    L.append("")
    return "\n".join(L)


def render_json(b: dict) -> str:
    d = b["data"]
    parts = ["{"]
    keys = ["meta", "consts", "coverage", "tags"]
    items = [(k, d[k]) for k in keys] + list(d["arrays"].items())
    for j, (k, v) in enumerate(items):
        sep = "," if j + 1 < len(items) else ""
        parts.append(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, separators=(',', ':'), allow_nan=False)}{sep}")
    parts.append("}")
    return "\n".join(parts) + "\n"


def write(out: Path | None = None) -> dict:
    """out 이 있으면 헤더·JSON 을 그 폴더에(시험), 없으면 헤더는 DEFAULT_HEADER_OUT(Source AI/Policy)·JSON 은 DEFAULT_OUT(results/v3/route/port)에 쓴다."""
    b = build()
    hdir = Path(out) if out is not None else DEFAULT_HEADER_OUT
    jdir = Path(out) if out is not None else DEFAULT_OUT
    for d in (hdir, jdir):
        d.mkdir(parents=True, exist_ok=True)
    h = render_header(b)
    j = render_json(b)
    (hdir / HEADER).write_text(h, encoding="utf-8", newline="\n")
    (jdir / JSON_NAME).write_text(j, encoding="utf-8", newline="\n")
    return dict(build=b, header=h, json=j, header_path=hdir / HEADER, json_path=jdir / JSON_NAME)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=None, help="헤더·JSON 을 함께 쓸 폴더 (시험용). 없으면 헤더 = Source AI/Policy, JSON = results/v3/route/port")
    a = ap.parse_args(argv)
    out = None if a.out is None else (a.out if a.out.is_absolute() else Path.cwd() / a.out)
    r = write(out)
    b = r["build"]
    print(f"썼다: {r['header_path']} ({len(r['header'].encode('utf-8'))} 바이트), {r['json_path']} ({len(r['json'].encode('utf-8'))} 바이트)")
    print(f"손 장면 {len(b['scenes'])}: " + " / ".join(f"{s['name']} (줄 {s['rows']}·적용 {s['applies']})" for s in b["scenes"]))
    lp = b["loop"]
    print(f"기하 {len(b['geo'])} · 길 셈 루프 줄 {lp['rows']}·적용 {lp['applies']}·통계 {lp['stats']}·죽음 {lp['deaths']} · 마스크 "
          f"{len(b['data']['arrays']['kMaskInt']) // len(MASK_INT)} {lp['mask_per']} · 다시 난 {len(b['respawn']['rows'])} {b['respawn']['got']}")
    wd = b["data"]["meta"]["world"]
    print(f"관측 사례 {len(b['obs'])} · 기준 루프 시드 {wd['seed']} (두뇌 지문 첫 갈림 {wd['first_split']}): " + " / ".join(
        f"{x['name']} 결정 {x['decisions']}·길 결정 {x['route_decisions']}·최소 로짓 차 {x['min_top_gap']:.4g}·잡힘 {x['caught']}·SHELTER 고름 "
        f"{x['route']['picked']['shelter']}·숨음 {x['hide']['hidden']}/{x['hide']['chased']}" for x in wd["brains"]))
    print("덮음: " + ", ".join(f"{k} {v}" for k, v in b["data"]["coverage"].items()))


if __name__ == "__main__":
    main()
