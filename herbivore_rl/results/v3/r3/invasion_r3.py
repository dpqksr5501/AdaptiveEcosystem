"""v3 R3 관문 — 얼기 없는 세계의 손 규칙 소수 침입·무리 확인·역침입 (명세 `Docs/RL_Policy/RL_V3_R3_SPEC.md` 7절, 사전 등록
`PREREG.md` — 같은 폴더). `results/v3/r2/invasion_r2.py` 의 사본에서 출발했다(칸·덮기·통계·판정 규칙은 R0·R2 와 같다).

    # herbivore_rl/ 에서 — 사전 등록 폴더(results/v3/r3/gate/, gate_b/)는 사전 등록 조건만 받고, PREREG.md 제목에 '초안'이 있으면 거부한다
    python results/v3/r3/invasion_r3.py search --workers 14            # 1) 거주 R_base(θ, a) 탐색(탐색 시드 33000~33039, 한 번)
    python results/v3/r3/invasion_r3.py run --workers 14               # 2) 묶음 A 침입 + T0·확인표(관문 판정 시드 15000~15039)
    python results/v3/r3/invasion_r3.py pop --x keep --workers 14      # 3) 조건부 통과를 따질 때만: 무리 확인·역침입 → gate.json 에 H1
    python results/v3/r3/invasion_r3.py run --cal 1 --gates keep       # 보정 1 (니치 실패에만, 변경 기록에 먼저 적고) → gate/cal1/keep/
    python results/v3/r3/invasion_r3.py pop --stage2 --passed keep run crouch   # 관문 2단계 무리 확인(보고만, 11절)
    python results/v3/r3/invasion_r3.py run --bundle b                 # 묶음 B(SLEEP, 선택) → gate_b/
    python results/v3/r3/invasion_r3.py report                         # 최종 관문표 → gate/final.json, results/v3/r3/report_gate.md
    # smoke·도구 점검: 다른 시드(보정 20000~20019·탐색 32000~32099·33000~33099 — 판정 시드는 받지 않는다)·짧은 스텝·칸 일부·문턱 고정,
    # 사전 등록 폴더가 아닌 --out 이 꼭 필요하다
    python results/v3/r3/invasion_r3.py run --seeds 33080 33081 --steps 200 --theta 4 --approach 0.9 --cells ps0.3_pl_T600 \
        --gates keep run --out <임시 폴더> --workers 2

세계: `configs/v3_r3_on.yaml`(R3 판정 세계, 규칙 여덟, 허용 GRAZE·FLEE·HIDE, 마스크 판 2). 칸 8개 = 잠행형 비율 {0.3, 0.7} ×
플레이어 {있음, 없음} × 하루 길이 {600, 1800}(덮기는 R0·R2 와 같다). 시작 전에 칸 덮기가 세계 배치(맵·늑대 수·은신처 원판·먹이·지형
격자·은신처 먹이 배수 f)를 바꾸지 않는지 시드마다 확인한다(`layout_check`). 묶음 B 는 같은 세계에 허용 목록 SLEEP 을 더한 메모리 사본이고
규칙의 SLEEP 가능 조건이 ¬K 다(판 4, 사전 등록 9-2).
- search (4절): 128마리 모두 R_base(θ, a), 격자 θ {2, 4, 6, 8} × a {0.6, 0.75, 0.9}, 칸 8개·시드 평균 개체-스텝당 보상이 가장 큰 (θ, a)
  (같으면 작은 θ, 큰 a). 결과 `gate/search.json` 을 고정한다(조건이 다른 캐시는 덮지 않는다).
- run (5·6·10절): 슬롯 0~15(침입)만 R3 규칙 X(`repertoire_rules.r3_wrap`, 고를 수 있는 자리에서만 요청)를 거주 규칙 위에 더한다. 판정 관문
  keep(G1)·run(G2)·leave(G3, 거주 = R_base + camp)·crouch(G4a)·early(G6, 거주 a* > 0.6 일 때만)는 niche·out·cross, 악용 점검
  shelter_all(G0)·camp(G0b)는 niche 하나(기준 (2)형), G1-H(keep_hide)는 보고 팔이다. 같은 칸·시드의 모두 거주 팔(R_base, G3 의 R_base +
  camp)도 돌린다(보상 이중차). 사전 등록 실행은 거주 R_base 팔로 T0·사용자 추격 모형 확인표(`results/v3/r3/pre/eval_pre.py` 지표 코드,
  `gate/t0_chase.*`)도 잰다.
- 판정 (6절, 관문마다): (1) 니치 5칸 이상 양수 & 유의 음수 0, (2) 니치 밖 5칸 이상 t < −2.023, (3) 교차 5칸 이상 t < −2.023.
  표본 하한: 판마다 칸별 '바뀐 결정'(40시드 합) 400 이상인 칸이 5칸 미만이면 그 판은 판정 불가 — 니치 판이면 관문이 '판정 불가', 니치 밖
  판이면 '멈춤(사람이 본다)', 교차 판이면 '교차 판정 불가'(조건부 통과 길). (1)·(2) 통과 & (3)만 실패 & 교차 칸 침입 '덮은 스텝' 몫 평균 <
  0.05 면 '판정 불능'. 악용 점검은 5칸 이상 t < −2.023 이면 '손해 확인', 아니면 '손해 아님(악용 위험)'.
  · 바뀐 결정 = 결정 시점에 침입 규칙이 거주 규칙(같은 관측)과 다른 행동을 요청했고 그것이 실행된 결정. 덮은 스텝 = 가장 최근 결정이 바뀐
    결정이었던 개체-스텝.
- pop (6·11절): --x 의 관문마다 128마리 모두 '거주 + X 니치' 대 모두 거주(칸별 시드 짝 t), 역침입(슬롯 0~15 거주, 나머지 거주 + X
  니치) → H1 조건부 통과(유의 음수 칸 0 & 8칸 평균 > 0 & 역침입에서 거주가 유의하게 이긴 칸 0)를 gate.json 에 적는다. --stage2 는 모두
  R_base, 모두 R_base + 통과 니치 규칙, 모두 FSM_R3, 모두 늘 먹기, 통과 규칙의 역침입(보고만).
- report (11절): 관문 최종 결과(보정·H1 반영)를 `gate/final.json` 과 `results/v3/r3/report_gate.md` 에 적는다. 교사·판정 도구는
  final.json 을 읽는다(`r3_tools.gate_setup`, 9-2 표).
사전 등록 폴더(16-2): PREREG.md 제목에 '초안'이 없어야 하고, 설정 `configs/v3_r3_on.yaml` 의 digest 가 사전 등록 값(PREREG_DIGEST)과
같아야 한다. search 는 탐색 시드 33000~33039, run·pop 은 관문 판정 시드 15000~15039 × 3000스텝·칸 8개·격자·관문 모두와 보고 팔·T0 만,
--theta/--approach 는 탐색 캐시 값과 같아야 하고 탐색 캐시의 설정 digest 가 지금과 같아야 한다. 결과는 한 번 쓴다(있으면 거부, --force 는
받지 않는다). pop 은 폴더와 조건도 본다: H1 무리 확인은 첫 판정 폴더(보정 회차면 gate/cal1/<관문>/, 관문 하나)에서 그 gate.json 과 같은
조건(설정·시드·스텝·문턱·칸·묶음·보정)일 때만, 2단계 무리 확인은 gate/ 에서 최종표(final.json)의 통과 니치·보정 1 그대로일 때만 받는다.
사전 등록 폴더 밖 실행은 관문·최종 판정 시드를 받지 않는다.
보정 대상(cal_eligible)은 (1) 니치 실패 & (2) 니치 밖 통과인 관문뿐이다. (2) 가 떨어지면 (1) 과 무관하게 '사람이 본다'(human)이고 보정하지
않는다(9-1). report 는 사람이 볼 관문을 '멈춤'에 적는다.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: F401,E402  ← torch(규칙의 가능 조건 rep_policy)보다 먼저
import numpy as np  # noqa: E402

import r3_tools as rt  # noqa: E402

CONFIG = rt.CONFIG_R3
SEARCH_SEEDS = list(range(33000, 33040))   # 거주 탐색(사전 등록 2절 — 관문 판정 시드와 따로)
GATE_SEEDS = list(rt.GATE_JUDGE)           # 관문 판정 15000~15039
STEPS = 3000
FOCAL = list(range(16))
T_CRIT = 2.023                             # 짝 t, 자유도 39 (양측 5%)
T_POWER80 = 0.851
GRID_THETA = (2.0, 4.0, 6.0, 8.0)
GRID_APPROACH = (0.6, 0.75, 0.9)
CELLS = {f"ps{p}_{'pl' if pl else 'np'}_T{T}": (p, pl, T)
         for p in (0.3, 0.7) for pl in (True, False) for T in (600, 1800)}
MODES = ("niche", "out", "cross")
GATE_MIN_CELLS = 5
EVENT_K = 60
LOW_COVER = 0.05                           # 판정 불능: 교차 칸 침입 '덮은 스텝' 몫 평균 < 0.05 (6절)
MIN_CHANGED = 400                          # 표본 하한: 칸별 바뀐 결정(40시드 합) (6절)
JUDGED = {"a": ("keep", "run", "leave", "crouch", "early"), "b": ("sleep_r3",)}
EXPLOIT = {"a": ("shelter_all", "camp"), "b": ("camp_sleep",)}
REPORT_X = {"a": ("keep_hide",), "b": ()}
BUNDLE = {k: JUDGED[k] + EXPLOIT[k] + REPORT_X[k] for k in JUDGED}
PREREG = HERE.parent / "PREREG.md"
GATE_DIR, GATE_B_DIR = rt.GATE_DIR, rt.GATE_B_DIR
OUT_DIR = {"a": GATE_DIR, "b": GATE_B_DIR}
REPORT_GATE = HERE.parent / "report_gate.md"
# 사전 등록 1절의 digest(10-15 작업 트리 값). 첫 실행 전에 커밋한 코드에서 다시 재서 사전 등록 변경 기록과 여기를 함께 고친다
PREREG_DIGEST = dict(config="fccf955cd1c9", world="92e1be9d6d66")
SPLIT_COVER, SPLIT_TERR = 0.175, 0.12      # 보고 칸 경계(3절): 은신처 실제 셀 몫, 눈 + 거친 땅 실제 셀 몫
CATCH_COLS = ("catch_rate_chaser", "catch_rate_ranged", "catch_rate_stalker", "catch_rate_player")
TERR = ("normal", "snow", "rough", "none")
WIN = 22                                   # 3 s
MINUTE = 450                               # 1분
EXIT_WIN = 225                             # 은신처를 나간 뒤 30 s (10-2 G3)
EDGE_BAND = 2.0                            # 은신처 가장자리 밖 띠(10-2 공통)
HUNGRY_E, FOOD_OK = 0.35, 0.06             # 배고픔(E < 0.35)·먹이 셀(용량 ≥ 0.06) (10-2 G3, H16)
HUNGRY_BINS = (0, 23, 46, 91, 226, 451, 10 ** 9)
ANGLE_BINS = 6                             # HIDE 시작 때 은신처 방향과 위협 방향 사이 각, 30° 칸 (10-2 G2)
FLEE_LEN_BINS = (0, 8, 9, 16, 23, 46, 91, 10 ** 9)
HIDE_OUT = ("reached", "caught", "switched", "other", "censored")
_VERDICT = {"pass": "통과", "fail": "실패", "low_power": "판정 불능(검정력 부족)", "insufficient": "판정 불가(표본 부족)",
            "out_insufficient": "멈춤 — 니치 밖 판정 불가(사람이 본다)", "cross_insufficient": "교차 판정 불가(조건부 통과 길)",
            "conditional_pass": "조건부 통과", "exploit_loss": "손해 확인(통과)", "exploit_risk": "손해 아님(악용 위험 — 사람이 본다)",
            "not_run": "돌리지 않음", "report": "보고만"}


def resident_of(x: str) -> str:
    """관문 X 의 거주 규칙: G3(leave)만 R_base + camp, 나머지는 R_base (사전 등록 4절)."""
    return "camp" if x == "leave" else "rbase"


# --------------------------------------------------------------------- #
# 설정·세계
# --------------------------------------------------------------------- #


def cell_cfg(cell: str, config: str = CONFIG, bundle: str = "a"):
    """칸의 설정: 세계 설정 + obs_extra + 칸 덮기(p_stalk 고정, 플레이어 있음·없음, 하루 길이 하나). 묶음 B 는 허용 목록에 sleep 을 더한다
    (메모리 사본 — 세계 동역학은 같다)."""
    from env_v2.config import load_v2_config

    import repertoire_rules as rr

    p, player, T = CELLS[cell]
    cfg = rr.with_obs_extra(load_v2_config(ROOT / config))
    v2 = dict(cfg.v2)
    f = {k: dict(v) for k, v in v2["features"].items()}
    f["threats"] = dict(f["threats"], stalk_frac=[p, p], player_frac=1.0 if player else 0.0)
    f["daynight"] = dict(f["daynight"], periods=[T])
    v2["features"] = f
    if bundle == "b":
        tr = dict(v2["train"])
        tr["repertoire"] = dict(tr["repertoire"], allowed=list(rr.r3_allowed(cfg, sleep=True)))
        v2["train"] = tr
    return cfg.replace(v2=v2)


def config_digest(cfg) -> str:
    """eval_v3.config_digest 와 같은 식(torch 를 싣지 않으려고 여기 다시 적는다)."""
    return hashlib.sha1(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]


def world_digest(cfg) -> str:
    """warmstart_v3.world_digest 와 같은 식(설정에서 version·train 을 빼고 허용 목록만 다시 넣은 dict 의 sha1 앞 12자리)."""
    d = cfg.to_dict()
    v2 = dict(d.get("v2") or {})
    v2.pop("version", None)
    train = v2.pop("train", None) or {}
    d = dict(d, v2=v2, allowed=list((train.get("repertoire") or {}).get("allowed") or []))
    return hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:12]


def prereg_digests(config: str = CONFIG) -> dict:
    """지금 작업 트리의 판정 설정 digest·world_digest (사전 등록 1절과 견준다)."""
    from env_v2.config import load_v2_config

    cfg = load_v2_config(ROOT / config)
    return dict(config=config_digest(cfg), world=world_digest(cfg))


def layout_key(cfg, seed: int) -> str:
    """세계 배치(사전 등록 3절: 맵·늑대 수·은신처 원판·먹이·지형 격자·은신처 먹이 배수 f)의 sha1 앞 12자리."""
    from env_v2.world import World

    w = World(cfg, seeds=[int(seed)])
    h = hashlib.sha1()
    for x in (np.float64(w.size), np.int64(w.M_base), w.pred_pos[:w.M_base], w.cov_c, w.cov_r, w.food_cap, w.food,
              getattr(w, "terrain_cell", np.zeros(0)), np.float64(getattr(w, "cover_food_cap", np.nan))):
        h.update(np.ascontiguousarray(np.asarray(x)).tobytes())
    return h.hexdigest()[:12]


def layout_check(seeds, config: str = CONFIG, cells=None, bundle: str = "a") -> dict:
    """칸 덮기가 세계 배치를 바꾸지 않는지 시드마다 본다(사전 등록 3절). 다르면 ValueError. 반환 {시드: 배치 digest}."""
    cells = list(cells or CELLS)
    cfgs = {c: cell_cfg(c, config, bundle) for c in cells}
    out = {}
    for s in seeds:
        keys = {c: layout_key(cfgs[c], s) for c in cells}
        if len(set(keys.values())) != 1:
            raise ValueError(f"시드 {s}: 칸 덮기가 세계 배치를 바꿨다 {keys} — 칸 덮기는 위협 유형·플레이어·하루 길이만 바꿔야 한다")
        out[str(s)] = next(iter(keys.values()))
    return out


_EP = None


def eval_pre():
    """재학습 전 측정 도구 `results/v3/r3/pre/eval_pre.py`(지표 코드 — Spy·도주 묶음·쫓김 묶음·확인표). 한 번 싣는다."""
    global _EP
    if _EP is None:
        name = "r3_eval_pre"
        if name in sys.modules:
            _EP = sys.modules[name]
        else:
            spec = importlib.util.spec_from_file_location(name, HERE.parent / "pre" / "eval_pre.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            _EP = mod
    return _EP


# --------------------------------------------------------------------- #
# 정책 스펙
# --------------------------------------------------------------------- #

# 관문 2단계 '모두 R_base + 통과 니치 규칙'에서 씌우는 순서(뒤가 앞을 덮는다 — FSM_R3 우선순위의 반대: early < keep < run < camp·leave <
# crouch). leave 가 들어가면 그 거주 규칙 camp 를 leave 앞에 함께 씌운다
STACK_ORDER = ("early", "keep", "run", "leave", "crouch")


def build_specs(cfg, theta: float, approach: float, variant: tuple, bundle: str = "a") -> tuple[dict, dict, dict | None]:
    """변형 → (정책 스펙, 거주 스펙(같은 관측의 '바탕 요청' — 바뀐 결정 세기), 사건 조건 규칙 래퍼(침입만, 아니면 None)).
    ("base", resident) 모두 거주 · ("inv", x, mode, cal) 슬롯 0~15 만 X · ("pop", xs, cal) 모두 거주 + xs 니치 · ("rev", xs, cal) 슬롯
    16~ 만 xs 니치 · ("fsm", lines, cal) 모두 FSM_R3 · ("graze",) 모두 늘 먹기. cal 은 보정 1 을 쓴 규칙의 목록이다."""
    import repertoire_rules as rr

    sleep = bundle == "b"
    kind = variant[0]

    def resident_spec(res):
        return rr.r3_rule_spec(cfg, theta, approach, resident=res, sleep=sleep)
    if kind == "base":
        sp = resident_spec(variant[1])
        return sp, sp, None
    if kind == "graze":
        return {"kind": "fixed", "action": [0.0]}, resident_spec("rbase"), None
    if kind == "fsm":
        lines, cal = variant[1], variant[2]
        return (rr.fsm_r3_spec(cfg, theta, approach, lines=lines, cal=[x for x in cal if x in lines], sleep=sleep),
                resident_spec("rbase"), None)
    if kind == "inv":
        x, mode, cal = variant[1], variant[2], variant[3]
        res = resident_of(x)
        spec = resident_spec(res)
        w = rr.r3_wrap(cfg, x, mode, FOCAL, theta=theta, approach=approach, cal=1 if x in cal else 0, sleep=sleep)
        spec["wrap"].append(w)
        return spec, resident_spec(res), dict(w, slots=None)
    if kind in ("pop", "rev"):
        xs, cal = tuple(variant[1]), tuple(variant[2])
        slots = None if kind == "pop" else list(range(len(FOCAL), int(cfg.N)))
        if len(xs) == 1:
            res = resident_of(xs[0])
            spec = resident_spec(res)
            spec["wrap"].append(rr.r3_wrap(cfg, xs[0], "niche", slots, theta=theta, approach=approach,
                                           cal=1 if xs[0] in cal else 0, sleep=sleep))
            return spec, resident_spec(res), None
        spec = resident_spec("rbase")
        for x in STACK_ORDER:
            if x not in xs:
                continue
            if x == "leave":
                spec["wrap"].append(rr.r3_wrap(cfg, "camp", "niche", slots, sleep=sleep))
            spec["wrap"].append(rr.r3_wrap(cfg, x, "niche", slots, theta=theta, approach=approach, cal=1 if x in cal else 0,
                                           sleep=sleep))
        return spec, resident_spec("rbase"), None
    raise ValueError(f"모르는 변형 {variant!r}")


def x_actions(variant: tuple) -> tuple[int, ...]:
    """'X 사용' 으로 세는 행동(침입 변형만): 규칙의 주 행동(keep_hide 는 HIDE, camp_sleep 은 HIDE·SLEEP)."""
    import repertoire_rules as rr
    from env_v2.repertoire import HIDE, SLEEP

    if variant[0] != "inv":
        return ()
    x = variant[1]
    return (HIDE, SLEEP) if x == "camp_sleep" else (rr.R3_X_BEHAVIOR[x],)


# --------------------------------------------------------------------- #
# 롤아웃 하나 (워커)
# --------------------------------------------------------------------- #


def _job(args):
    """롤아웃 하나. args = (칸, θ, a, 변형, 시드, 스텝, 설정, 묶음, full). full 이면 eval_pre 의 Spy(기록만 한다)로 보고 지표(포기율 A·도주
    묶음·쫓김 묶음·HIDE 이동·배고픔·은신처 안 시간·섭취·경계·늑대)를 침입(슬롯 0~15)과 거주(나머지)로 나눠 센다. 판정 값(보상·피식·아사
    차, 바뀐 결정, 덮은 스텝, 사건 조건)은 full 과 무관하게 같다(Spy 는 궤적을 바꾸지 않는다 — 시험이 본다)."""
    from env_v2 import rollout as ro
    from env_v2.repertoire import FLEE, HIDE, N_BEHAVIORS
    from env_v2.world import World

    import repertoire_rules as rr

    cell, theta, approach, variant, seed, steps, config, bundle, full = args
    cfg = cell_cfg(cell, config, bundle)
    spec, base_spec, cond_w = build_specs(cfg, theta, approach, variant, bundle)
    pol = ro.build_policy(spec, seed)
    basep = ro.build_policy(base_spec, seed)
    cond_rule = rr.R3Rule(None, cond_w) if cond_w is not None else None
    ep = eval_pre() if full else None
    Base = ep._spy_class() if full else World

    class W(Base):
        def _accumulate(self, a, rew, repro, caught, starved, done):
            self.last = (caught.copy(), starved.copy(), np.asarray(repro, dtype=bool).copy())
            super()._accumulate(a, rew, repro, caught, starved, done)

        def _eat(self, e_drained, mult=None):
            g = super()._eat(e_drained, mult)
            self.last_gain = np.asarray(g, dtype=np.float64).copy()
            return g

    w = W(cfg, seeds=[seed])
    if full:
        w._spy_init()
    N, M = w.N, w.M
    foc = np.zeros(N, dtype=bool)
    foc[FOCAL] = True
    groups = (foc, ~foc)
    names = list(w.obs_names)
    ci = {c: names.index(c) for c in ("pred_count", "threat_recency", "cover_dist", "energy")}
    xa = x_actions(variant)
    rew_s, pred_s, starve_s, repro_s, use_s = (np.zeros(N) for _ in range(5))
    chg, dec_n, cov_steps = np.zeros(N, dtype=np.int64), np.zeros(N, dtype=np.int64), np.zeros(N, dtype=np.int64)
    last_chg = np.zeros(N, dtype=bool)
    cond_prev = np.zeros(N, dtype=bool)
    win = np.full(N, -1, dtype=np.int64)
    win_rew = np.zeros(N)
    win_terr = np.zeros(N, dtype=np.int64)
    ev = np.zeros((2, 4, 4))                                  # [침입·거주] × 땅(시작 때) × [창 수, 보상 합, 피식, 아사]
    T = steps
    if full:
        beh = np.zeros((T, N), dtype=np.int8)
        done_a = np.zeros((T, N), dtype=bool)
        caught_a = np.zeros((T, N), dtype=bool)
        purs_d = np.full((T, N), np.inf, dtype=np.float32)
        purs_cls = np.full((T, N), -1, dtype=np.int8)
        purs_kind = np.full((T, N), -1, dtype=np.int8)
        near_d = np.full((T, N), np.inf, dtype=np.float32)
        near_cls = np.full((T, N), -1, dtype=np.int8)
        seen_dec = np.zeros((T, N), dtype=bool)
        in_cov = np.zeros((T, N), dtype=bool)
        terr = np.full((T, N), 3, dtype=np.int8)
        a_opp = np.zeros((2, 4, N_BEHAVIORS), dtype=np.int64)
        opp_ev = ([], [])
        tp1 = np.full(M, -1, dtype=np.int64)
        tp2 = np.full(M, -1, dtype=np.int64)
        intake = np.zeros((2, 3))                             # [그룹] × [전체, 은신처 안, 가장자리 밖 2단위 띠]
        cov_k = np.zeros((2, 2), dtype=np.int64)              # [그룹] × [은신처 안 개체-스텝(관측), 그중 K]
        hide_tab = np.zeros((2, 4, len(HIDE_OUT)), dtype=np.int64)
        hide_angle = np.zeros((2, ANGLE_BINS), dtype=np.int64)
        hide_act = {}                                         # 개체 → [시작 스텝, 땅]
        hung = np.full(N, -1, dtype=np.int64)                 # 배고파진 스텝(은신처 안에서, 밖 먹이 셀에 닿기 전), 없으면 −1
        hung_hist = np.zeros((2, len(HUNGRY_BINS) - 1 + 2), dtype=np.int64)    # 칸 + [죽음, 잘림]
        e_prev = None
        wolf = ~w.pred_is_player if w._th is not None else np.ones(M, dtype=bool)
        wolf_catch = 0
        has_terr = w._zt is not None
        has_ps = w._ps is not None
        food_cells = getattr(w, "cover_food_cell", w.cover_cell)
    for t in range(T):
        obs = w.observe()
        pk = w.rep_peek()
        dec = np.asarray(pk["reads"], dtype=bool)
        a = np.asarray(pol(obs), dtype=np.float64)
        req = a[:, 0].astype(np.int64)
        breq = np.asarray(basep(obs), dtype=np.float64)[:, 0].astype(np.int64)
        tr_now = rt.terrain_now(w)
        if cond_rule is not None:
            cond = cond_rule.target(obs, breq, slots=False)[0]
            onset = cond & ~cond_prev & (win < 0) & (t <= T - EVENT_K)
            win[onset] = EVENT_K
            win_rew[onset] = 0.0
            win_terr[onset] = tr_now[onset]
            cond_prev = cond
        if full:
            seen_dec[t] = obs[:, ci["pred_count"]] > 0.0
            inc_o = obs[:, ci["cover_dist"]] <= 0.0
            kk = seen_dec[t] | (obs[:, ci["threat_recency"]] >= rr.R3_RECENCY)
            awake_now = ~w.pred_asleep if has_ps else np.ones(M, dtype=bool)
            purs_now = np.full(N, np.inf)
            for tg in (tp1, tp2):
                ms = np.flatnonzero((tg >= 0) & awake_now)
                if len(ms):
                    dd = np.sqrt(((w.pred_pos[ms] - w.pos[tg[ms]]) ** 2).sum(1))
                    np.minimum.at(purs_now, tg[ms], dd)
            in_cov_now = w._in_cover(w.pos)
            pos0, ppos0 = w.pos.copy(), w.pred_pos.copy()
            e_now = obs[:, ci["energy"]].astype(np.float64)
            for k, gm in enumerate(groups):
                cov_k[k] += (int((inc_o & gm).sum()), int((inc_o & kk & gm).sum()))
            # 배고픔(H16): 은신처 안에서 E 가 0.35 아래로 내려간 순간
            if e_prev is not None:
                start_h = (hung < 0) & (e_now < HUNGRY_E) & (e_prev >= HUNGRY_E) & inc_o
                hung[start_h] = t
            e_prev = e_now
            if dec.any():
                idx = np.flatnonzero(dec)
                opp = (pk["behavior"][idx] == FLEE) & (purs_now[idx] < rt.PURSUE_R) & ~in_cov_now[idx]
                if opp.any():
                    oi = idx[opp]
                    ch = req[oi]
                    tr_o = tr_now[oi]
                    for k, gm in enumerate(groups):
                        sel = gm[oi]
                        np.add.at(a_opp[k], (tr_o[sel], ch[sel]), 1)
                        opp_ev[k].extend(zip([t] * int(sel.sum()), oi[sel].tolist(), ch[sel].tolist(), tr_o[sel].tolist()))
        _, r, d_, _ = w.step(a)
        ro.forward_done(pol, d_)
        ro.forward_done(basep, d_)
        c, s, rp_ = w.last
        rew_s += r
        pred_s += c
        starve_s += s
        repro_s += rp_
        if xa:
            use_s += np.isin(w.behavior, xa)
        changed = dec & (req != breq)
        rs = w._rs
        executed = changed & ((w.behavior == req) | (rs.waking & (rs.wake_target == req)))
        chg += executed
        dec_n += dec
        last_chg = np.where(dec, executed, last_chg)
        cov_steps += last_chg
        last_chg = last_chg & ~d_
        if cond_rule is not None:
            op = win > 0
            win_rew[op] += r[op]
            win[op] -= 1
            closed = op & (d_ | (win == 0))
            for k, gm in enumerate(groups):
                for q in range(4):
                    cm = closed & gm & (win_terr == q)
                    ev[k, q] += (np.count_nonzero(cm), win_rew[cm].sum(), np.count_nonzero(cm & c), np.count_nonzero(cm & s))
            win[closed] = -1
            cond_prev = cond_prev & ~d_
        if full:
            sp = w.spy
            pre = sp["pre"]
            beh[t] = w.behavior
            done_a[t], caught_a[t] = d_, sp["caught"]
            in_cov[t] = pre["in_cov"]
            near_d[t], near_cls[t], purs_d[t], purs_cls[t] = sp["near_d"], sp["near_cls"], sp["purs_d"], sp["purs_cls"]
            purs_kind[t] = sp["purs_kind"]
            if has_terr:
                terr[t] = w._rz_terrain_of(pre["pos"])
            wolf_catch += int(np.count_nonzero(sp["got"] & wolf))
            gain = w.last_gain
            if len(w.cov_r):
                edge = w._cover_edge(pre["pos"])[2].min(1)
            else:
                edge = np.full(N, np.inf)
            band = (edge > 0.0) & (edge <= EDGE_BAND)
            for k, gm in enumerate(groups):
                intake[k] += (gain[gm].sum(), gain[gm & pre["in_cov"]].sum(), gain[gm & band].sum())
            # HIDE 이동(G2): 은신처 밖에서 HIDE 를 시작한 개체 → 닿음·잡힘·바꿈·그 밖(굶음)·잘림
            for i in list(hide_act):
                t0_, q0 = hide_act[i]
                out = None
                if sp["caught"][i]:
                    out = "caught"
                elif d_[i]:
                    out = "other"
                elif pre["in_cov"][i]:
                    out = "reached"
                elif w.behavior[i] != HIDE:
                    out = "switched"
                if out is not None:
                    hide_tab[int(foc[i] == 0), q0, HIDE_OUT.index(out)] += 1
                    del hide_act[i]
            new_h = (w.behavior == HIDE) & ~d_ & ~(obs[:, ci["cover_dist"]] <= 0.0)
            if t > 0:
                new_h &= ~((beh[t - 1] == HIDE) & ~done_a[t - 1])
            for i in np.flatnonzero(new_h):
                if pre["in_cov"][i] or i in hide_act:
                    if pre["in_cov"][i]:
                        hide_tab[int(foc[i] == 0), int(tr_now[i]), 0] += 1
                    continue
                hide_act[int(i)] = [t, int(tr_now[i])]
                k_t = int(rs.hide_target[i])
                aw = ~w.pred_asleep if has_ps else np.ones(M, dtype=bool)
                if k_t >= 0 and M and aw.any():
                    vc = w.cov_c[k_t] - pos0[i]
                    dv = ppos0 - pos0[i]
                    dd = np.where(aw, np.sqrt((dv * dv).sum(1)), np.inf)
                    vt = dv[int(dd.argmin())]
                    nc, nt = np.linalg.norm(vc), np.linalg.norm(vt)
                    if nc > 1e-9 and nt > 1e-9:
                        ang = math.degrees(math.acos(max(-1.0, min(1.0, float(vc @ vt) / (nc * nt)))))
                        hide_angle[int(foc[i] == 0), min(int(ang // 30.0), ANGLE_BINS - 1)] += 1
            # 배고픔 끝: 밖의 먹이 셀(은신처 셀이 아니고 용량 ≥ 0.06)에 닿음, 죽음
            hh = np.flatnonzero(hung >= 0)
            if len(hh):
                ix, iy = w._cell_index(w.pos[hh])
                okc = ~food_cells[iy, ix] & (w.food_cap[iy, ix] >= FOOD_OK) & ~d_[hh]
                for i, ok in zip(hh, okc):
                    k = int(foc[i] == 0)
                    if d_[i]:
                        hung_hist[k, -2] += 1
                        hung[i] = -1
                    elif ok:
                        hung_hist[k, np.searchsorted(HUNGRY_BINS, t - hung[i], side="right") - 1] += 1
                        hung[i] = -1
            hung[d_] = -1
            tp2, tp1 = tp1, sp["tgt"].copy()
            if d_.any() and e_prev is not None:
                e_prev = e_prev.copy()
                e_prev[d_] = 1.0                                  # 새 개체: 배고파진 순간을 이전 개체와 잇지 않는다
    sums = (("rew", rew_s), ("pred", pred_s), ("starve", starve_s))
    out = {k: float(v[foc].mean() / T - v[~foc].mean() / T) for k, v in sums}
    out.update({k + "_all": float(v.mean() / T) for k, v in sums})
    sc = w.rep_slot_counts()
    out.update(sw_f=int(sc["switch"][foc].sum()), sw_r=int(sc["switch"][~foc].sum()),
               fl_f=int(sc["flicker"][foc].sum()), fl_r=int(sc["flicker"][~foc].sum()))
    out.update(use_focal=float(use_s[foc].mean() / T), use_res=float(use_s[~foc].mean() / T),
               chg_f=int(chg[foc].sum()), chg_r=int(chg[~foc].sum()), dec_f=int(dec_n[foc].sum()), dec_r=int(dec_n[~foc].sum()),
               cov_f=float(cov_steps[foc].sum() / (foc.sum() * T)), cov_r=float(cov_steps[~foc].sum() / ((~foc).sum() * T)),
               repro_f=float(repro_s[foc].mean() / T), repro_r=float(repro_s[~foc].mean() / T))
    if cond_rule is not None:
        out["ev"] = ev.tolist()
        nan = float("nan")
        for k, sfx in ((0, "f"), (1, "r")):
            e = ev[k].sum(0)
            out[f"ev_n_{sfx}"] = int(e[0])
            out[f"ev_rew_{sfx}"] = float(e[1] / e[0]) if e[0] else nan
            out[f"ev_pred_{sfx}"] = float(e[2] / e[0]) if e[0] else nan
            out[f"ev_starve_{sfx}"] = float(e[3] / e[0]) if e[0] else nan
    ts = w.threats_stats()
    out.update({k: float(ts[k]) for k in CATCH_COLS})
    n_wolf = int(np.count_nonzero(~w.pred_is_player)) if w._th is not None else int(M)
    out["world"] = dict(cover_frac_actual=float(w.cover_frac_actual),
                        snow_frac_actual=float(getattr(w, "snow_frac_actual", 0.0)),
                        rough_frac_actual=float(getattr(w, "rough_frac_actual", 0.0)), M=int(M), n_wolf=n_wolf)
    if full:
        out["rep"] = _full_report(ep, groups, beh, done_a, caught_a, purs_d, purs_cls, near_d, near_cls, seen_dec, purs_kind,
                                  in_cov, terr, a_opp, opp_ev, intake, cov_k, hide_tab, hide_angle, hide_act, hung,
                                  hung_hist, wolf_catch, w, T)
    return cell, theta, approach, variant, seed, out


def _hist_counts(xs, bins) -> list[int]:
    return np.histogram(np.asarray(xs, dtype=np.float64), bins=bins)[0].astype(int).tolist() if len(xs) else [0] * (len(bins) - 1)


def _full_report(ep, groups, beh, done, caught, purs_d, purs_cls, near_d, near_cls, seen_dec, purs_kind, in_cov, terr, a_opp,
                 opp_ev, intake, cov_k, hide_tab, hide_angle, hide_act, hung, hung_hist, wolf_catch, w, T) -> dict:
    """한 롤아웃의 보고 지표(침입·거주별, 모두 수 — 모을 때 더한다). eval_pre 의 도주 묶음·쫓김 묶음·고른 행동별 뒤 잡힘·경계 넘나듦을
    그룹의 열만 잘라 그대로 쓴다."""
    from env_v2.repertoire import FLEE

    rep = {}
    for k, gm in enumerate(groups):
        idx = np.flatnonzero(gm)
        b = ep.flee_bouts(beh[:, idx], done[:, idx], caught[:, idx], purs_d[:, idx], purs_cls[:, idx], near_d[:, idx],
                          near_cls[:, idx], seen_dec[:, idx], FLEE, purs_kind[:, idx], in_cov[:, idx], terr[:, idx])
        ch = ep.chase_episodes(purs_d[:, idx], purs_kind[:, idx], beh[:, idx], done[:, idx], caught[:, idx], in_cov[:, idx],
                               terr[:, idx])
        ao = ep.opp_outcomes(opp_ev[k], caught, done)
        cr = ep.cover_crossings(in_cov[:, idx], done[:, idx])
        # 은신처를 나간 뒤 30초 안 잡힘(G3): 나감 = 지난 스텝 원 안 → 이번 스텝 밖(같은 개체), 땅 = 나간 스텝
        ex = np.zeros((4, 2), dtype=np.int64)
        ic, dn, cg = in_cov[:, idx], done[:, idx], caught[:, idx]
        tt, ii = np.nonzero(ic[:-1] & ~ic[1:] & ~dn[:-1])
        for t0, i in zip(tt + 1, ii):
            if t0 + EXIT_WIN > T:
                continue
            hit = False
            for k2 in range(t0, t0 + EXIT_WIN):
                if cg[k2, i]:
                    hit = True
                    break
                if dn[k2, i]:
                    break
            ex[int(terr[t0, idx[i]])] += (1, int(hit))
        censored_h = sum(1 for i in hide_act if bool(gm[i]))
        ht = hide_tab[k].copy()
        ht[:, HIDE_OUT.index("censored")] += np.bincount([hide_act[i][1] for i in hide_act if bool(gm[i])], minlength=4)[:4] \
            if censored_h else 0
        hh = hung_hist[k].copy()
        hh[-1] += int(np.count_nonzero((hung >= 0) & gm))
        rep["fr"[k]] = dict(
            n=int(len(idx) * T),
            bouts=dict(n=len(b["lengths"]), len_hist=_hist_counts(b["lengths"], FLEE_LEN_BINS), n_end=b["n_end"],
                       pursued=b["pursued"], stopgo=b["stopgo"], reflee=b["reflee"], caught_w=b["caught_w"],
                       caught60=b["caught60"], p_terr=b["p_terr"]),
            chase=dict(tab=ch["tab"], lat=ch["lat"]),
            a_opp=a_opp[k].tolist(), a_out=ao.tolist(), cross=cr, exit=ex.tolist(),
            in_cover=int(in_cov[:, idx].sum()), intake=intake[k].tolist(), cov_k=cov_k[k].tolist(),
            hide=ht.tolist(), hide_angle=hide_angle[k].tolist(), hungry=hh.tolist())
    rep["wolf"] = dict(catch=int(wolf_catch), n_wolf=int(np.count_nonzero(~w.pred_is_player)) if w._th is not None else int(w.M),
                       steps=int(T))
    clean = lambda d: {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in d.items()}   # noqa: E731
    if w._rz:
        rep["realism"] = clean(w.realism_stats())
    if w._r3:
        rep["r3"] = clean(w.r3_stats())
        if w._zw:
            rep["r3"]["blocking_n"] = int(w._zw_sel.sum())
    return rep


def _t0_job(args):
    """모두 거주 R_base 팔의 T0·사용자 추격 모형 확인표(사전 등록 10-3): eval_pre.job_world(같은 Spy·지표 코드)에 관문 칸 설정과
    R_base(θ, a)를 준다. 큰 목록(도주 길이·거리)은 빼고 돌려준다."""
    from env_v2 import rollout as ro

    import repertoire_rules as rr

    cell, theta, approach, seed, steps, config = args
    cfg = cell_cfg(cell, config)
    pol = ro.build_policy(rr.rule_spec(cfg, theta, approach), seed)
    r = eval_pre().job_world(cfg, pol, cell, "rbase_gate", seed, steps)
    keep = ("variant", "seed", "steps", "n", "g_gamma", "pred_rate", "starve_rate", "a_opp", "a_out", "pounce", "charge",
            "pounce_tdead", "chase", "r3", "world", "catch_n", "wolf_catch", "n_wolf", "rim", "stuck_hist", "stuck_max")
    out = {k: r[k] for k in keep if k in r}
    out["chase"] = {k: r["chase"][k] for k in ("tab", "lat", "tlen")}
    return cell, seed, out


def paired(d) -> dict:
    """시드별 차 → 평균·짝 t·MDE80. nan 은 뺀다. 표준편차 0 이거나 2개 미만이면 t None (R0·R2 와 같다)."""
    d = np.asarray(d, dtype=np.float64)
    d = d[np.isfinite(d)]
    n = len(d)
    if n == 0:
        return dict(mean=float("nan"), t=None, n=0, mde80=None)
    sd = float(d.std(ddof=1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else 0.0
    return dict(mean=float(d.mean()), t=float(d.mean() / se) if se > 0 else None, n=n,
                mde80=float((T_CRIT + T_POWER80) * se) if se > 0 else None)


def _map(fn, jobs, workers):
    if workers <= 1 or len(jobs) <= 1:
        return [fn(j) for j in jobs]
    from env.rollout import _init_worker

    with ProcessPoolExecutor(min(workers, len(jobs)), initializer=_init_worker) as ex:
        return list(ex.map(fn, jobs, chunksize=1))


# --------------------------------------------------------------------- #
# 거주 탐색
# --------------------------------------------------------------------- #


class StaleCache(RuntimeError):
    """조건이 다른 탐색 캐시가 이미 있다(--force 없이 덮지 않는다)."""


def search_meta(seeds, steps, config=CONFIG, grid_theta=GRID_THETA, grid_approach=GRID_APPROACH, cells=None) -> dict:
    cells = list(cells or CELLS)
    return dict(config=config, digest={c: config_digest(cell_cfg(c, config)) for c in cells}, seeds=list(seeds),
                steps=int(steps), grid_theta=list(grid_theta), grid_approach=list(grid_approach), cells=cells)


def search(seeds, steps, workers, out: Path, config=CONFIG, grid_theta=GRID_THETA, grid_approach=GRID_APPROACH, cells=None,
           force=False) -> dict:
    """거주 규칙 문턱 탐색(사전 등록 4절). 같은 조건의 캐시가 있으면 다시 돌리지 않는다."""
    cells = list(cells or CELLS)
    meta = search_meta(seeds, steps, config, grid_theta, grid_approach, cells)
    path = out / "search.json"
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("meta") == meta and not force:
            return old
        if not force:
            diff = sorted(k for k in meta if old.get("meta", {}).get(k) != meta[k])
            raise StaleCache(f"{path} 에 조건이 다른 탐색 캐시가 있다(다른 항목: {diff}). 사전 등록 탐색은 한 번 하고 고정한다 — "
                             "고정한 값으로 시험하려면 --theta/--approach, 아니면 --out 에 다른 폴더를 준다")
    jobs = [(c, th, a, ("base", "rbase"), s, steps, config, "a", False) for th in grid_theta for a in grid_approach
            for c in cells for s in seeds]
    t0 = time.time()
    per = {}
    for c, th, a, _, s, o in _map(_job, jobs, workers):
        per.setdefault(f"{th:g}|{a:g}", {}).setdefault(c, {})[str(s)] = {k: o[k] for k in ("rew_all", "pred_all", "starve_all")}
    table = {}
    for key, by_cell in per.items():
        def m(k):
            return float(np.mean([[by_cell[c][str(s)][k] for c in cells] for s in seeds]))
        table[key] = dict(rew=m("rew_all"), pred=m("pred_all"), starve=m("starve_all"))
    order = sorted(table, key=lambda k: (-table[k]["rew"], float(k.split("|")[0]), -float(k.split("|")[1])))
    th, a = (float(x) for x in order[0].split("|"))
    res = dict(meta=meta, best=dict(theta=th, approach=a), table=table, per_seed=per, elapsed_s=round(time.time() - t0, 1))
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


# --------------------------------------------------------------------- #
# 판정
# --------------------------------------------------------------------- #


def _sig_neg(v, key="rew"):
    return v[key]["t"] is not None and v[key]["t"] < -T_CRIT


def gate_verdict(summary: dict, cells, x: str, key: str = "rew") -> dict:
    """판정 관문 X 의 판정(사전 등록 6절). summary[f"{x}|{mode}|{cell}"] 는 `summarize_arms` 의 행."""
    def col(mode):
        return [summary.get(f"{x}|{mode}|{c}") for c in cells]
    nich, outs, cross = col("niche"), col("out"), col("cross")
    if any(v is None for v in nich + outs + cross):
        return dict(complete=False)
    floor = {m: int(sum(v["chg_f"] >= MIN_CHANGED for v in col(m))) for m in MODES}
    ok = {m: floor[m] >= GATE_MIN_CELLS for m in MODES}
    n_pos = sum(v[key]["mean"] > 0 for v in nich)
    n_neg1 = sum(_sig_neg(v, key) for v in nich)
    n_neg2 = sum(_sig_neg(v, key) for v in outs)
    n_neg3 = sum(_sig_neg(v, key) for v in cross)
    c1 = n_pos >= GATE_MIN_CELLS and n_neg1 == 0
    c2 = n_neg2 >= GATE_MIN_CELLS
    c3 = n_neg3 >= GATE_MIN_CELLS
    cross_cov = float(np.mean([v["cov_f"] for v in cross]))
    import repertoire_rules as rr

    if not ok["niche"]:
        verdict = "insufficient"
    elif not ok["out"]:
        verdict = "out_insufficient"
    elif c1 and c2 and ok["cross"] and c3:
        verdict = "pass"
    elif c1 and c2 and not ok["cross"]:
        verdict = "cross_insufficient"
    elif c1 and c2 and not c3 and cross_cov < LOW_COVER:
        verdict = "low_power"
    else:
        verdict = "fail"
    # 보정 대상 = (1) 니치 실패이고 (2) 니치 밖은 통과(9-1). (2) 가 떨어지면 (1) 과 무관하게 보정하지 않고 사람이 본다 — 보정은 니치만 좁혀
    # 니치 밖 판(같은 정의·같은 시드)은 다시 돌려도 결과가 같으므로, 보정 회차가 (2) 를 고칠 수 없다
    return dict(complete=True, kind="judged", niche_pos=int(n_pos), niche_sig_neg=int(n_neg1), out_sig_neg=int(n_neg2),
                cross_sig_neg=int(n_neg3), c1=bool(c1), c2=bool(c2), c3=bool(c3), floor=floor, floor_ok=ok,
                cross_cov_focal=cross_cov, verdict=verdict,
                cal_eligible=bool(verdict == "fail" and not c1 and c2 and x in rr.R3_CAL1),
                human=bool(verdict == "out_insufficient" or (verdict == "fail" and not c2)))


def exploit_verdict(summary: dict, cells, x: str, key: str = "rew") -> dict:
    """악용 점검(G0·G0b·G0b-S): 기준 (2)형 — 5칸 이상 t < −2.023 이면 손해 확인. 표본 하한은 없다(6절)."""
    vs = [summary.get(f"{x}|niche|{c}") for c in cells]
    if any(v is None for v in vs):
        return dict(complete=False)
    n_neg = int(sum(_sig_neg(v, key) for v in vs))
    return dict(complete=True, kind="exploit", sig_neg=n_neg, verdict="exploit_loss" if n_neg >= GATE_MIN_CELLS else "exploit_risk")


def h1_verdict(gx: dict, popx: dict | None) -> dict:
    """H1 '조건부 통과'(사전 등록 6절, R2 4절 그대로). gx = gate_verdict 한 행, popx = pop 요약의 그 X 행."""
    if not gx.get("complete") or popx is None:
        return dict(complete=False)
    cond = bool(gx["c1"] and gx["c2"] and gx["verdict"] in ("fail", "low_power", "cross_insufficient")
                and popx["sig_neg"] == 0 and popx["mean8"] > 0 and popx["rev_res_wins"] == 0)
    verdict = gx["verdict"] if gx["verdict"] == "pass" else ("conditional_pass" if cond else gx["verdict"])
    return dict(complete=True, gate_verdict=gx["verdict"], pop_sig_neg=popx["sig_neg"], pop_mean8=popx["mean8"],
                rev_res_wins=popx["rev_res_wins"], conditional=cond, verdict=verdict)


def summarize_arms(per: dict, base: dict, ss: list, steps: int, n_agents: int, per_sec: float) -> dict:
    """per[f"{x}|{mode}|{cell}"][시드] → 칸별 요약(판정 값과 보고 값). base[거주][칸][시드] 는 모두 거주 팔(이중차 기준)."""
    summary = {}
    for key, by_seed in per.items():
        x, mode, c = key.split("|")
        b = base[resident_of(x)][c]
        v = summary[key] = {k: paired([by_seed[s][k] for s in ss]) for k in ("rew", "pred", "starve")}
        v["rew_did"] = paired([by_seed[s]["rew"] - b[s]["rew"] for s in ss])
        v["repro"] = paired([by_seed[s]["repro_f"] - by_seed[s]["repro_r"] for s in ss])      # 번식(G0·G0b 보고)
        v["use_focal"] = float(np.mean([by_seed[s]["use_focal"] for s in ss]))
        v["use_res"] = float(np.mean([by_seed[s]["use_res"] for s in ss]))
        v["chg_f"] = int(sum(by_seed[s]["chg_f"] for s in ss))
        v["dec_f"] = int(sum(by_seed[s]["dec_f"] for s in ss))
        v["cov_f"] = float(np.mean([by_seed[s]["cov_f"] for s in ss]))
        v["rew_per_cov"] = v["rew"]["mean"] / v["cov_f"] if v["cov_f"] > 0 else float("nan")
        for k in ("rew", "pred", "starve"):
            v[f"ev_{k}"] = paired([by_seed[s][f"ev_{k}_f"] - by_seed[s][f"ev_{k}_r"] for s in ss])
        v["ev_n_f"] = int(sum(by_seed[s]["ev_n_f"] for s in ss))
        v["ev_n_r"] = int(sum(by_seed[s]["ev_n_r"] for s in ss))
        sw_f, sw_r = (sum(by_seed[s][k] for s in ss) for k in ("sw_f", "sw_r"))
        fl_f, fl_r = (sum(by_seed[s][k] for s in ss) for k in ("fl_f", "fl_r"))
        n_f, n_r = len(FOCAL) * steps * len(ss), (n_agents - len(FOCAL)) * steps * len(ss)
        v["flicker_f"] = fl_f / sw_f if sw_f else float("nan")
        v["flicker_r"] = fl_r / sw_r if sw_r else float("nan")
        v["switch_per_sec_f"] = sw_f / n_f * per_sec
        v["switch_per_sec_r"] = sw_r / n_r * per_sec
    return summary


def seed_world(base: dict, ss) -> dict:
    """시드마다 세계 성질(은신처 실제 셀 몫, 눈·거친 땅 실제 셀 몫) — 칸 덮기는 배치를 바꾸지 않으므로 첫 칸의 값."""
    rows = next(iter(base["rbase"].values()))
    return {s: rows[s]["world"] for s in ss}


def event_by_terrain(per: dict, key_a: str, key_b: str | None, cells, ss) -> dict:
    """사건 조건 창 보상의 땅별 대비(10-2 G1, 보고만): 땅 = 창을 연 순간 사슴 위치의 셀. 시드마다 칸을 합친 창당 보상으로 (key_b 가 없으면)
    침입 − 거주(같은 팔, G1 니치면 FLEE − GRAZE), 있으면 key_a 침입 − key_b 침입(G1 니치 대 G1-H 면 FLEE − HIDE)의 시드 짝 t."""
    out = {}
    for q, name in enumerate(TERR[:3]):
        d = []
        for s in ss:
            def rate(key, g):
                e = np.sum([per[f"{key}|{c}"][s]["ev"][g][q] for c in cells if f"{key}|{c}" in per], axis=0)
                return e[1] / e[0] if e[0] else float("nan")
            a = rate(key_a, 0)
            b = rate(key_a, 1) if key_b is None else rate(key_b, 0)
            d.append(a - b)
        out[name] = paired(d)
    return out


def report_cells(per: dict, keys, cells, ss, world: dict) -> dict:
    """보고 칸(사전 등록 3절, 판정에 쓰지 않는다): 칸 8개의 시드별 차를 먼저 평균하고 세계 성질 묶음마다 시드 짝 t."""
    groups = {"cover_lo": lambda w: w["cover_frac_actual"] < SPLIT_COVER, "cover_hi": lambda w: w["cover_frac_actual"] >= SPLIT_COVER,
              "terr_lo": lambda w: w["snow_frac_actual"] + w["rough_frac_actual"] < SPLIT_TERR,
              "terr_hi": lambda w: w["snow_frac_actual"] + w["rough_frac_actual"] >= SPLIT_TERR,
              "no_snow": lambda w: w["snow_frac_actual"] <= 0.0, "snow": lambda w: w["snow_frac_actual"] > 0.0}
    out = {}
    for xm in keys:
        cm = [f"{xm}|{c}" for c in cells]
        if any(k not in per for k in cm):
            continue
        mean_seed = {s: float(np.mean([per[k][s]["rew"] for k in cm])) for s in ss}
        out[xm] = {g: dict(paired([mean_seed[s] for s in ss if fn(world[s])]),
                           seeds=[int(s) for s in ss if fn(world[s])]) for g, fn in groups.items()}
        out[xm]["all"] = paired([mean_seed[s] for s in ss])
    return out


# --------------------------------------------------------------------- #
# 보고 지표 모으기
# --------------------------------------------------------------------- #


def _ratio(x, y):
    return float(x) / float(y) if y else None


def pool_report(rows: list[dict]) -> dict:
    """한 팔(관문·모드)의 칸·시드 보고 지표(rep)를 더한다 → 침입(f)·거주(r) 별 비율."""
    from env_v2.repertoire import BEHAVIOR_NAMES

    ab = list(rt.abandon_ids())
    out = {}
    for g in ("f", "r"):
        R = [r["rep"][g] for r in rows]
        n = sum(x["n"] for x in R)
        ao = np.sum([x["a_opp"] for x in R], axis=0)                # [땅, 행동]
        A_seed = []
        for x in R:
            a = np.asarray(x["a_opp"])
            A_seed.append(_ratio(a[:, ab].sum(), a.sum()))
        aout = np.sum([x["a_out"] for x in R], axis=0)              # [땅, 행동, 3]
        bt = [x["bouts"] for x in R]
        pt = np.sum([b["p_terr"] for b in bt], axis=0)
        ch = np.sum([x["chase"]["tab"] for x in R], axis=0)         # [종류, 칸, 땅, 결과]
        ex = np.sum([x["exit"] for x in R], axis=0)
        hd = np.sum([x["hide"] for x in R], axis=0)                 # [땅, 결과]
        ha = np.sum([x["hide_angle"] for x in R], axis=0)
        hu = np.sum([x["hungry"] for x in R], axis=0)
        it = np.sum([x["intake"] for x in R], axis=0)
        ck = np.sum([x["cov_k"] for x in R], axis=0)
        cr_n, cr_q = sum(x["cross"]["n"] for x in R), sum(x["cross"]["quick"] for x in R)
        pursued = sum(b["pursued"] for b in bt)
        ep = eval_pre()
        out[g] = dict(
            agent_steps=int(n),
            A=dict(pooled=_ratio(ao[:, ab].sum(), ao.sum()), n_opp=int(ao.sum()),
                   seed_mean=(float(np.mean([a for a in A_seed if a is not None])) if any(a is not None for a in A_seed) else None),
                   choice={b: _ratio(ao[:, k].sum(), ao.sum()) for k, b in enumerate(BEHAVIOR_NAMES)},
                   by_terr={TERR[q]: dict(n=int(ao[q].sum()), A=_ratio(ao[q, ab].sum(), ao[q].sum())) for q in range(4)
                            if ao[q].sum()}),
            A_out={b: dict(n=int(aout[:, k, 0].sum()), caught3s=_ratio(aout[:, k, 1].sum(), aout[:, k, 0].sum()),
                           caught8s=_ratio(aout[:, k, 2].sum(), aout[:, k, 0].sum()))
                   for k, b in enumerate(BEHAVIOR_NAMES) if aout[:, k, 0].sum()},
            A_out_terr={TERR[q]: {b: dict(n=int(aout[q, k, 0]), caught3s=_ratio(aout[q, k, 1], aout[q, k, 0]))
                                  for k, b in enumerate(BEHAVIOR_NAMES) if aout[q, k, 0]} for q in range(4) if aout[q, :, 0].sum()},
            bouts=dict(n=int(sum(b["n"] for b in bt)), per_1k=_ratio(1000.0 * sum(b["n"] for b in bt), n),
                       len_hist=np.sum([b["len_hist"] for b in bt], axis=0).tolist(),
                       pursued_end_frac=_ratio(pursued, sum(b["n_end"] for b in bt)),
                       stop_go_per_1k=_ratio(1000.0 * sum(b["stopgo"] for b in bt), n),
                       stop_go_given_pursued=_ratio(sum(b["stopgo"] for b in bt), pursued),
                       caught3s_given_pursued=_ratio(sum(b["caught_w"] for b in bt), pursued),
                       by_terr={TERR[q]: dict(n=int(pt[q, 0]), stop_go=_ratio(pt[q, 1], pt[q, 0]), caught3s=_ratio(pt[q, 2], pt[q, 0]))
                                for q in range(4) if pt[q, 0]}),
            chase=ep._chase_table(ch, np.sum([x["chase"]["lat"] for x in R], axis=0)),
            exit={TERR[q]: dict(n=int(ex[q, 0]), caught30s=_ratio(ex[q, 1], ex[q, 0])) for q in range(4) if ex[q, 0]},
            hide={TERR[q]: dict(n=int(hd[q].sum()), **{o: _ratio(hd[q, j], hd[q].sum()) for j, o in enumerate(HIDE_OUT)})
                  for q in range(4) if hd[q].sum()},
            hide_angle=dict(n=int(ha.sum()), share=[_ratio(v, ha.sum()) for v in ha]),
            hungry=dict(n=int(hu.sum()), hist=hu[:-2].tolist(), died=int(hu[-2]), censored=int(hu[-1])),
            in_cover_frac=_ratio(sum(x["in_cover"] for x in R), n),
            intake_cover_share=_ratio(it[1], it[0]), intake_edge_share=_ratio(it[2], it[0]),
            cover_k_share=_ratio(ck[1], ck[0]),
            cross_per_min=_ratio(cr_n * MINUTE, n), cross_quick=_ratio(cr_q, cr_n))
    wolf = [r["rep"]["wolf"] for r in rows]
    out["wolf_catch_per_min"] = _ratio(sum(x["catch"] for x in wolf) * MINUTE, sum(x["n_wolf"] * x["steps"] for x in wolf))
    if all("r3" in r["rep"] for r in rows):
        z = {k: sum((r["rep"]["r3"].get(k) or 0.0) for r in rows) for k in ("chase_held_n", "chase_lock_n", "chase_rel_cover_n",
                                                                          "chase_rel_lost_n", "chase_rel_state_n", "chase_rel_catch_n",
                                                                          "chase_catch_own_n", "chase_rel_dead_n", "wall_push_n",
                                                                          "wall_slide_n", "wall_stuck_n", "wall_inside_n")}
        thr = sum(r["world"]["M"] * r["rep"]["wolf"]["steps"] for r in rows)                  # 위협-스텝(eval_pre 와 같다)
        wolf_steps = sum(r["rep"]["wolf"]["n_wolf"] * r["rep"]["wolf"]["steps"] for r in rows)
        blk = sum(r["rep"]["r3"].get("blocking_n", 0) * r["rep"]["wolf"]["steps"] for r in rows)
        rel = {k: z[f"chase_rel_{k}_n"] for k in ("cover", "lost", "state", "catch", "dead")}
        out["chase_lock"] = dict(held_share=_ratio(z["chase_held_n"], thr), release_share={k: _ratio(v, sum(rel.values()))
                                                                                           for k, v in rel.items()},
                                 own_catch_share=_ratio(z["chase_catch_own_n"], z["chase_rel_catch_n"]),
                                 lost_by_cover_per_wolf_min=_ratio(z["chase_rel_cover_n"] * MINUTE, wolf_steps))
        out["wall"] = dict(inside_n=int(z["wall_inside_n"]), push_share=_ratio(z["wall_push_n"], blk),
                           slide_share=_ratio(z["wall_slide_n"], blk), dead_share=_ratio(z["wall_stuck_n"], blk))
    if all("realism" in r["rep"] for r in rows):
        n_all = sum(r["rep"]["f"]["n"] + r["rep"]["r"]["n"] for r in rows)
        out["immune_per_1k"] = _ratio(1000.0 * sum((r["rep"]["realism"].get("safe_saved_n") or 0.0) for r in rows), n_all)
    return out


# --------------------------------------------------------------------- #
# 침입 시험
# --------------------------------------------------------------------- #


def gate_list(bundle: str, gates, approach: float) -> tuple[list, dict]:
    """(돌릴 (규칙, 모드) 목록, 돌리지 않은 관문과 까닭). G6 은 거주 a* 가 0.6 보다 클 때만 뜻이 있다(5-1 읽는 법)."""
    import repertoire_rules as rr

    variants, skipped = [], {}
    for x in gates:
        if x == "early" and approach <= rr.R3_NICHES["early"]["app"]:
            skipped[x] = f"거주 a* {approach:g} ≤ 0.6 — 거주자가 이미 그 자리에서 도망한다(사전 등록 5-1 읽는 법)"
            continue
        modes = ("niche",) if x in rr.R3_SINGLE else MODES
        variants += [(x, m) for m in modes]
    return variants, skipped


def run(seeds, steps, workers, out: Path, theta: float, approach: float, config: str = CONFIG, cells=None, gates=None,
        bundle: str = "a", cal=(), t0: bool = True) -> dict:
    """침입 시험(묶음 A·B, 보정 회차) + 모두 거주 팔(+ 묶음 A 의 T0·확인표). 결과: invasion.json·gate.json·invasion.md(판정표 먼저)."""
    from env_v2.config import load_v2_config

    cells = list(cells or CELLS)
    gates = list(gates or BUNDLE[bundle])
    cfg0 = load_v2_config(ROOT / config)
    per_sec, n_agents = 60.0 / float(cfg0.policy_interval), int(cfg0.N)
    t_start = time.time()
    layout = layout_check(seeds, config, cells, bundle)
    variants, skipped = gate_list(bundle, gates, approach)
    residents = sorted({resident_of(x) for x, _ in variants} | {"rbase"})
    cal = tuple(cal)
    jobs = [(c, theta, approach, ("inv", x, m, cal), s, steps, config, bundle, True) for x, m in variants for c in cells
            for s in seeds]
    jobs += [(c, theta, approach, ("base", r), s, steps, config, bundle, True) for r in residents for c in cells for s in seeds]
    per, base, rep_rows = {}, {}, {}
    for c, _, _, var, s, o in _map(_job, jobs, workers):
        rep = o.pop("rep", None)
        if var[0] == "base":
            base.setdefault(var[1], {}).setdefault(c, {})[str(s)] = o
            key = f"base_{var[1]}"
        else:
            per.setdefault(f"{var[1]}|{var[2]}|{c}", {})[str(s)] = o
            key = f"{var[1]}|{var[2]}"
        if rep is not None:
            rep_rows.setdefault(key, []).append(dict(rep=rep, world=o["world"]))
    ss = [str(s) for s in seeds]
    summary = summarize_arms(per, base, ss, steps, n_agents, per_sec)
    import repertoire_rules as rr

    g, g_did = {}, {}
    for x in gates:
        if x in skipped:
            g[x] = g_did[x] = dict(complete=True, kind="skipped", verdict="not_run", reason=skipped[x])
        elif x in rr.R3_EXPLOIT:
            g[x], g_did[x] = exploit_verdict(summary, cells, x), exploit_verdict(summary, cells, x, "rew_did")
        elif x in REPORT_X[bundle]:
            g[x] = g_did[x] = dict(complete=True, kind="report", verdict="report")
        else:
            g[x], g_did[x] = gate_verdict(summary, cells, x), gate_verdict(summary, cells, x, "rew_did")
    extra = {}
    if "keep" in gates and "keep_hide" in gates and "keep" not in skipped:      # G1-H: FLEE 침입 − HIDE 침입 (보고만)
        extra["g1h"] = {c: paired([per[f"keep|niche|{c}"][s]["rew"] - per[f"keep_hide|niche|{c}"][s]["rew"] for s in ss])
                        for c in cells}
    if "keep" in gates and "keep" not in skipped:              # 사건 조건 보상의 땅별 FLEE − GRAZE·FLEE − HIDE (10-2 G1, 보고만)
        extra["event_terrain"] = {"flee_minus_graze": event_by_terrain(per, "keep|niche", None, cells, ss)}
        if "keep_hide" in gates:
            extra["event_terrain"]["flee_minus_hide"] = event_by_terrain(per, "keep|niche", "keep_hide|niche", cells, ss)
    world = seed_world(base, ss)
    extra["report_cells"] = report_cells(per, sorted({k.rsplit("|", 1)[0] for k in per}), cells, ss, world)
    report = {k: pool_report(v) for k, v in rep_rows.items()}
    meta = dict(bundle=bundle, config=config, seeds=list(seeds), steps=int(steps), theta=theta, approach=approach, cells=cells,
                gates=gates, variants=[list(v) for v in variants], cal=list(cal), skipped=skipped, t_crit=T_CRIT,
                event_k=EVENT_K, low_cover=LOW_COVER, min_changed=MIN_CHANGED, layout=layout,
                digest={c: config_digest(cell_cfg(c, config, bundle)) for c in cells}, prereg_digest=prereg_digests(config),
                elapsed_s=None)
    res = dict(meta=meta, gate=g, gate_did=g_did, summary=summary, extra=extra, report=report,
               per_seed=dict(per, base=base))
    if t0 and bundle == "a" and not cal:
        res["t0"] = t0_chase(seeds, steps, workers, theta, approach, config, cells)
    meta["elapsed_s"] = round(time.time() - t_start, 1)
    out.mkdir(parents=True, exist_ok=True)
    (out / "invasion.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (out / "gate.json").write_text(json.dumps(dict(meta=meta, gate=g, gate_did_report_only=g_did), indent=1), encoding="utf-8")
    (out / "invasion.md").write_text(report_md(res), encoding="utf-8")
    if "t0" in res:
        (out / "t0_chase.json").write_text(json.dumps(res["t0"], indent=1, default=str), encoding="utf-8")
        (out / "t0_chase.md").write_text(t0_md(res["t0"], meta), encoding="utf-8")
    return res


def t0_chase(seeds, steps, workers, theta, approach, config=CONFIG, cells=None) -> dict:
    """모두 거주 R_base 팔의 T0·확인표(사전 등록 10-3). T0 는 칸 8개의 시드별 땅별 잡힘 비율을 평균한 뒤 시드 짝 t(그 땅이 없는 시드는 뺀다)."""
    cells = list(cells or CELLS)
    rows = _map(_t0_job, [(c, theta, approach, s, steps, config) for c in cells for s in seeds], workers)
    ep = eval_pre()
    by_seed = {}
    for c, s, r in rows:
        by_seed.setdefault(int(s), []).append(r)
    per = []
    for s in seeds:
        rr_ = by_seed[int(s)]
        rate = {}
        for t in ("normal", "snow", "rough"):
            v = [r["r3"][f"catch_{t}_n"] / r["r3"][f"deer_n_{t}"] for r in rr_ if r["r3"].get(f"deer_n_{t}")]
            rate[t] = float(np.mean(v)) * 1000.0 if v else None
        deer = {t: float(sum(r["r3"][f"deer_n_{t}"] or 0.0 for r in rr_)) for t in ("normal", "snow", "rough")}
        catch = {t: float(sum(r["r3"][f"catch_{t}_n"] or 0.0 for r in rr_)) for t in ("normal", "snow", "rough")}
        per.append(dict(seed=int(s), rate_per_1k=rate, deer=deer, catch=catch))
    t0 = dict(per_seed=per)
    for t in ("snow", "rough"):
        a = [p["rate_per_1k"][t] for p in per]
        b = [p["rate_per_1k"]["normal"] if p["rate_per_1k"][t] is not None else None for p in per]
        d = [x - y if x is not None and y is not None else float("nan") for x, y in zip(a, b)]
        t0[f"{t}_minus_normal"] = paired(d)
    tot_d = {t: sum(p["deer"][t] for p in per) for t in ("normal", "snow", "rough")}
    tot_c = {t: sum(p["catch"][t] for p in per) for t in ("normal", "snow", "rough")}
    t0["pooled_per_1k"] = {t: _ratio(1000.0 * tot_c[t], tot_d[t]) for t in tot_d}
    t0["deer_share"] = {t: _ratio(tot_d[t], sum(tot_d.values())) for t in tot_d}
    t0["catch_share"] = {t: _ratio(tot_c[t], sum(tot_c.values())) for t in tot_c}
    R = [r for _, _, r in rows]
    pounce = ep._pounce_table(np.sum([r["pounce"] for r in R], axis=0))
    charge = ep._pounce_table(np.sum([r["charge"] for r in R], axis=0))
    chase = ep._chase_table(np.sum([r["chase"]["tab"] for r in R], axis=0), np.sum([r["chase"]["lat"] for r in R], axis=0),
                            np.sum([r["chase"]["tlen"] for r in R], axis=0))
    ao = np.sum([r["a_out"] for r in R], axis=0)
    from env_v2.repertoire import BEHAVIOR_NAMES

    a_out = {b: dict(n=int(ao[:, k, 0].sum()), caught3s=_ratio(ao[:, k, 1].sum(), ao[:, k, 0].sum()),
                     caught8s=_ratio(ao[:, k, 2].sum(), ao[:, k, 0].sum())) for k, b in enumerate(BEHAVIOR_NAMES) if ao[:, k, 0].sum()}
    rim = np.sum([r["rim"] for r in R], axis=0)
    wall = dict(inside_blocking=int(rim[:, 2].sum()), rim_share_wolf=_ratio(rim[0, 1], rim[0, 0]),
                stuck_hist_wolf=np.sum([r["stuck_hist"] for r in R], axis=0)[0].tolist(),
                stuck_max_wolf=int(max(r["stuck_max"][0] for r in R)), stuck_max_player=int(max(r["stuck_max"][1] for r in R)))
    return dict(t0=t0, pounce=pounce, charge=charge, chase=chase, a_out=a_out, wall=wall, theta=theta, approach=approach,
                seeds=list(seeds), steps=int(steps), cells=cells)


# --------------------------------------------------------------------- #
# 무리 확인·역침입
# --------------------------------------------------------------------- #


def pop(seeds, steps, workers, out: Path, theta: float, approach: float, config: str = CONFIG, cells=None, xs=(),
        stage2: bool = False, passed=(), cal=(), bundle: str = "a") -> dict:
    """무리 확인·역침입(사전 등록 6·11절). xs 의 관문마다(H1 근거) 또는 stage2(통과 규칙 묶음 — 모두 R_base·R_base + 통과 규칙·
    FSM_R3·늘 먹기·역침입). 판정이 아니다. gate.json 이 같은 조건이면 H1 을 그 관문 행에 적는다."""
    cells = list(cells or CELLS)
    cal = tuple(cal)
    arms = {}
    if stage2:
        ps = tuple(passed)
        arms = {"base_rbase": ("base", "rbase"), "pop": ("pop", ps, cal), "rev": ("rev", ps, cal),
                "fsm": ("fsm", tuple(x for x in ps if x in rt.FSM_GATES), cal), "graze": ("graze",)}
    else:
        for x in xs:
            arms[f"base_{resident_of(x)}"] = ("base", resident_of(x))
            arms[f"pop|{x}"] = ("pop", (x,), cal)
            arms[f"rev|{x}"] = ("rev", (x,), cal)
    jobs, names = [], []
    for name, v in arms.items():
        for c in cells:
            for s in seeds:
                jobs.append((c, theta, approach, v, s, steps, config, bundle, False))
                names.append(name)
    t0 = time.time()
    raw = {}
    for name, (c, _, _, _, s, o) in zip(names, _map(_job, jobs, workers)):
        raw.setdefault(name, {}).setdefault(c, {})[str(s)] = o
    ss = [str(s) for s in seeds]
    summ = {}
    for name in raw:
        if name.startswith("base_"):
            continue
        res_name = "base_rbase" if (stage2 or "|" not in name) else f"base_{resident_of(name.split('|')[1])}"
        rows = {}
        for c in cells:
            if name.startswith("rev"):      # 역침입: 슬롯 0~15(거주) − 나머지(거주 + X)
                v = paired([raw[name][c][s]["rew"] for s in ss])
            else:                           # 무리: 128마리 개체-스텝당 보상, 그 변형 − 모두 거주
                v = paired([raw[name][c][s]["rew_all"] - raw[res_name][c][s]["rew_all"] for s in ss])
            v["pred_all"] = float(np.mean([raw[name][c][s]["pred_all"] for s in ss]))
            v["starve_all"] = float(np.mean([raw[name][c][s]["starve_all"] for s in ss]))
            for k in CATCH_COLS:
                v[k] = float(np.mean([raw[name][c][s][k] for s in ss]))
            rows[c] = v
        ts = [rows[c]["t"] for c in cells]
        summ[name] = dict(cells=rows, mean8=float(np.mean([rows[c]["mean"] for c in cells])),
                          sig_pos=int(sum(t is not None and t > T_CRIT for t in ts)),
                          sig_neg=int(sum(t is not None and t < -T_CRIT for t in ts)))
    base_rows = {name: {c: dict(rew_all=float(np.mean([raw[name][c][s]["rew_all"] for s in ss])),
                                pred_all=float(np.mean([raw[name][c][s]["pred_all"] for s in ss])),
                                starve_all=float(np.mean([raw[name][c][s]["starve_all"] for s in ss])))
                        for c in cells} for name in raw if name.startswith("base_")}
    h1_input = {}
    if not stage2:
        for x in xs:
            h1_input[x] = dict(sig_neg=summ[f"pop|{x}"]["sig_neg"], mean8=summ[f"pop|{x}"]["mean8"],
                               rev_res_wins=summ[f"rev|{x}"]["sig_pos"])
    meta = dict(bundle=bundle, config=config, seeds=list(seeds), steps=int(steps), theta=theta, approach=approach, cells=cells,
                xs=list(xs), stage2=bool(stage2), passed=list(passed), cal=list(cal), t_crit=T_CRIT,
                elapsed_s=round(time.time() - t0, 1), digest={c: config_digest(cell_cfg(c, config, bundle)) for c in cells})
    res = dict(meta=meta, summary=summ, base=base_rows, h1_input=h1_input)
    gpath = out / "gate.json"
    if not stage2 and gpath.exists():
        gj = json.loads(gpath.read_text(encoding="utf-8"))
        gm = gj.get("meta", {})
        same = all(gm.get(k) == meta[k] for k in ("config", "seeds", "steps", "theta", "approach", "cells", "bundle"))
        same = same and sorted(gm.get("cal", [])) == sorted(meta["cal"])
        if same:
            h1 = {x: h1_verdict(gj["gate"].get(x, {}), h1_input[x]) for x in xs}
            res["h1"] = h1
            gj.setdefault("h1", {}).update(h1)
            gj.setdefault("pop_meta", {}).update({x: meta for x in xs})
            gpath.write_text(json.dumps(gj, indent=1), encoding="utf-8")
        else:
            res["h1"] = {x: dict(complete=False, reason="gate.json 의 조건(설정·시드·스텝·문턱·칸·보정)이 이 무리 확인과 다르다")
                         for x in xs}
    out.mkdir(parents=True, exist_ok=True)
    res["per_seed"] = raw
    name = "pop_stage2" if stage2 else "pop"
    (out / f"{name}.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (out / f"{name}.md").write_text(pop_md(res), encoding="utf-8")
    return res


# --------------------------------------------------------------------- #
# 최종 관문표 (사전 등록 9-2·11절)
# --------------------------------------------------------------------- #


def final_verdicts(gate_dir: Path = GATE_DIR, gate_b_dir: Path = GATE_B_DIR) -> dict:
    """관문마다 최종 결과: 첫 판정 → (보정 1 을 돌렸으면) 보정 결과 → (H1 을 적었으면) 조건부 통과. 묶음 B 는 gate_b/ 가 있을 때만."""
    out = {}
    for d in (gate_dir, gate_b_dir):
        p = d / "gate.json"
        if not p.exists():
            continue
        gj = json.loads(p.read_text(encoding="utf-8"))
        for x, g in gj["gate"].items():
            v, src, c, hum = g.get("verdict"), str(p), 0, bool(g.get("human"))
            h = gj.get("h1", {}).get(x)
            if h and h.get("complete"):
                v = h["verdict"]
            cp = d / "cal1" / x / "gate.json"
            if cp.exists() and g.get("cal_eligible"):
                cj = json.loads(cp.read_text(encoding="utf-8"))
                cg = cj["gate"].get(x, {})
                v, src, c, hum = cg.get("verdict"), str(cp), 1, bool(cg.get("human"))
                h = cj.get("h1", {}).get(x)
                if h and h.get("complete"):
                    v = h["verdict"]
            out[x] = dict(verdict=v, cal=c, source=src, human=hum)
    return out


def report(gate_dir: Path = GATE_DIR, gate_b_dir: Path = GATE_B_DIR, out_md: Path = REPORT_GATE) -> dict:
    """gate/final.json 과 report_gate.md (판정표 먼저, 그다음 FSM_R3 줄과 판정 U 목록 — 9-2 표)."""
    import repertoire_rules as rr

    sp = gate_dir / "search.json"
    if not sp.exists() or not (gate_dir / "gate.json").exists():
        raise SystemExit(f"{gate_dir} 에 search.json·gate.json 이 없다 — 관문을 먼저 돌린다")
    search_ = json.loads(sp.read_text(encoding="utf-8"))
    gates = final_verdicts(gate_dir, gate_b_dir)
    final = dict(gates=gates, theta=search_["best"]["theta"], approach=search_["best"]["approach"],
                 generated=time.strftime("%Y-%m-%d %H:%M:%S"))
    setup = rt.setup_from_final(final, search_)
    (gate_dir / "final.json").write_text(json.dumps(final, indent=1, ensure_ascii=False), encoding="utf-8")
    L = ["# v3 R3 관문 보고 (사전 등록 results/v3/r3/PREREG.md 11절)", "",
         f"거주 R_base(θ {final['theta']:g}, a {final['approach']:g}) — 탐색 {sp}. 사람이 확인한 뒤 판정 사전 등록으로 간다.", "",
         "## 관문표", "", "| 관문 | 규칙 | 최종 결과 | 보정 | 근거 |", "|---|---|---|---|---|"]
    for x, v in gates.items():
        L.append(f"| {rr.R3_GATE_NAME.get(x, x)} | {x} | {_VERDICT.get(v['verdict'], v['verdict'])} | {v['cal'] or '—'} | "
                 f"`{Path(v['source']).relative_to(ROOT).as_posix() if Path(v['source']).is_relative_to(ROOT) else v['source']}` |")
    L += ["", "## 학습과 판정에 쓰이는 방식 (9-2 표)", "",
          f"- FSM_R3 관문 줄: {', '.join(setup['lines']) or '없음'} (줄 4 R_base·줄 7 GRAZE 는 늘). 보정 1 을 쓴 줄: "
          f"{', '.join(setup['cal']) or '없음'}. 잠 줄: {'넣음' if setup['sleep'] else '없음(SLEEP 은 막힌 채)'}.",
          f"- 판정 U: {', '.join('U_' + u.upper() for u in setup['u_judged'])}. 보고만: "
          f"{', '.join('U_' + u.upper() for u in setup['u_report']) or '없음'}.",
          f"- P3(포기율 A): {'판정 조건' if setup['p3'] else '보고만 — 사람에게 보인다'}. HIDE 사용 하한: "
          f"{'건다' if setup['hide_floor'] else '걸지 않는다'}.",
          "- 악용 점검이 '손해 아님'이면 학습 전에 멈추고 사람이 본다. 니치 밖 판정 불가·(2) 실패도 멈추고 사람이 본다."]
    stop = [x for x, v in gates.items() if v["verdict"] in ("exploit_risk", "out_insufficient") or v.get("human")]
    if stop:
        L.append(f"- **멈춤**: {', '.join(stop)}")
    text = "\n".join(L) + "\n"
    out_md.write_text(text, encoding="utf-8")
    return dict(final=final, setup=setup, md=text)


# --------------------------------------------------------------------- #
# 보고서
# --------------------------------------------------------------------- #


def _f(x, nd=5):
    if x is None or x["n"] == 0 or not math.isfinite(x["mean"]):
        return "—"
    return f"{x['mean']:+.{nd}f} ({x['t']:+.2f})" if x["t"] is not None else f"{x['mean']:+.{nd}f}"


def _num(x, fmt):
    return format(x, fmt) if x is not None and isinstance(x, (int, float)) and math.isfinite(x) else "—"


def _pc(x):
    return "—" if x is None else f"{100.0 * x:.1f}%"


def report_md(res: dict) -> str:
    import repertoire_rules as rr

    m, g, s = res["meta"], res["gate"], res["summary"]
    gd = res.get("gate_did", {})
    small = len(m["seeds"]) < 40 or m["steps"] < STEPS or len(m["cells"]) < len(CELLS)
    head = f"# v3 R3 관문 묶음 {m['bundle'].upper()}" + (f" — 보정 {', '.join(m['cal'])}" if m["cal"] else "")
    L = [head + " (손 규칙 소수 침입)" + (" — smoke·부분 실행, 판정 아님" if small else ""), "",
         f"설정 {m['config']} + obs_extra, 시드 {m['seeds'][0]}~{m['seeds'][-1]} ({len(m['seeds'])}개) × {m['steps']}스텝, 칸 "
         f"{len(m['cells'])}개, 거주 R_base(θ {m['theta']:g}, a {m['approach']:g}) (G3 는 + camp). 값 = 침입 16 − 거주 112, 개체-스텝당. "
         f"짝 t 임계 {m['t_crit']}. 설정 digest {m['prereg_digest']['config']}, world_digest {m['prereg_digest']['world']}.", "",
         "## 판정 (사전 등록 6절)", "",
         "| 관문 | (1) 니치 양수 / 유의 음수 | (2) 니치 밖 유의 음수 | (3) 교차 유의 음수 | 바뀐 결정 ≥ 400 칸 (니치·밖·교차) | "
         "교차 덮은 스텝(침입) | 판정 | 이중차 판정(보고만) |", "|---|---|---|---|---|---|---|---|"]
    for x, v in g.items():
        name = f"{rr.R3_GATE_NAME.get(x, x)} {x}"
        vd = gd.get(x, {})
        if v.get("kind") == "skipped":
            L.append(f"| {name} | — | — | — | — | — | {_VERDICT['not_run']}: {v['reason']} | — |")
        elif v.get("kind") == "report":
            L.append(f"| {name} | — | — | — | — | — | 보고만(아래 G1-H) | — |")
        elif not v.get("complete"):
            L.append(f"| {name} | — | — | — | — | — | (칸 부족) | — |")
        elif v["kind"] == "exploit":
            L.append(f"| {name} | — | {v['sig_neg']} (기준 (2)형) | — | — | — | {_VERDICT[v['verdict']]} | "
                     f"{_VERDICT.get(vd.get('verdict'), '—')} |")
        else:
            fl = v["floor"]
            L.append(f"| {name} | {v['niche_pos']} / {v['niche_sig_neg']} {'○' if v['c1'] else '×'} | {v['out_sig_neg']} "
                     f"{'○' if v['c2'] else '×'} | {v['cross_sig_neg']} {'○' if v['c3'] else '×'} | {fl['niche']}·{fl['out']}·"
                     f"{fl['cross']} | {v['cross_cov_focal']:.4f} | {_VERDICT[v['verdict']]}"
                     + (" — 보정 1 대상" if v.get("cal_eligible") else "") + (" — 사람이 본다" if v.get("human") else "")
                     + f" | {_VERDICT.get(vd.get('verdict'), '—')} |")
    L += ["", "H1 '조건부 통과'는 `pop --x <관문>` 이 무리 확인·역침입을 잰 뒤 gate.json 에 적는다(6절). 최종 결과는 `report` 가 모은다."]
    ex = res.get("extra", {})
    if ex.get("g1h"):
        L += ["", "## G1-H (보고만): FLEE 침입 − HIDE 침입 (G1 니치, 칸별 시드 짝 t)", "", "| 칸 | 차 (t) |", "|---|---|"]
        L += [f"| {c} | {_f(v)} |" for c, v in ex["g1h"].items()]
    rc = ex.get("report_cells", {})
    if rc:
        L += ["", "## 보고 칸 (3절, 판정에 쓰지 않는다): 칸 8개 평균 보상 차의 세계 성질 묶음별 시드 짝 t", "",
              "| 규칙·모드 | 모두 | 은신처 < 0.175 | ≥ 0.175 | 지형 < 0.12 | ≥ 0.12 | 눈 없음 | 눈 있음 |", "|---|---|---|---|---|---|---|---|"]
        for xm, d in rc.items():
            L.append(f"| {xm} | {_f(d['all'])} | " + " | ".join(f"{_f(d[k])} [{len(d[k]['seeds'])}]" for k in
                                                              ("cover_lo", "cover_hi", "terr_lo", "terr_hi", "no_snow", "snow")) + " |")
    L += ["", "## 칸별 값", "",
          "이중차(보고만) = 침입 차 − 같은 시드·칸의 모두 거주 실행의 슬롯 0~15 − 나머지 차. 바뀐 결정 = 침입 규칙이 거주 규칙과 다른 행동을 "
          "요청해 실행된 결정(40시드 합). 덮은 스텝 = 가장 최근 결정이 바뀐 결정인 침입 개체-스텝 몫. 희석 보정 = 보상 차 ÷ 덮은 스텝 몫. "
          f"사건 조건 = X 조건에 들어선 순간부터 {m['event_k']}스텝 창, 침입 − 거주.", "",
          "| X | 모드 | 칸 | 보상 (t) | MDE80 | 바뀐 결정 | 덮은 스텝 | 희석 보정 | 보상 이중차 (t) | 피식 (t) | 아사 (t) | X 사용 침입·거주 | "
          "사건 조건 보상 (t) | 창 수 | 깜빡임 침입·거주 | 초당 전환 침입·거주 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(s):
        x, mode, c = key.split("|")
        v = s[key]
        L.append(f"| {x} | {mode} | {c} | {_f(v['rew'])} | {_num(v['rew']['mde80'], '.5f')} | {v['chg_f']} | {v['cov_f']:.4f} | "
                 f"{_num(v['rew_per_cov'], '+.4f')} | {_f(v['rew_did'])} | {_f(v['pred'])} | {_f(v['starve'])} | "
                 f"{v['use_focal']:.3f} · {v['use_res']:.3f} | {_f(v['ev_rew'], 3)} | {v['ev_n_f']} · {v['ev_n_r']} | "
                 f"{_num(v['flicker_f'], '.3f')} · {_num(v['flicker_r'], '.3f')} | {v['switch_per_sec_f']:.3f} · "
                 f"{v['switch_per_sec_r']:.3f} |")
    rep = res.get("report", {})
    if rep:
        L += ["", "## 보고 지표 (10-2절, 칸·시드 합침, 침입 / 거주)", "",
              "| 팔 | 포기율 A (기회) | 도주 묶음 /1000 | 쫓김 끝 몫 | 멈춤-재도주 /1000 | 쫓김 끝 뒤 3초 잡힘 | 은신처 안 시간 | 은신처 안 섭취 | "
              "가장자리 띠 섭취 | 은신처 안 & K | 넘나듦 /분 | 3초 안 되돌아옴 | 늑대 분당 포획 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in rep.items():
            f_, r_ = v["f"], v["r"]

            def two(a, b, fmt=_pc):
                return f"{fmt(a)} / {fmt(b)}"
            L.append(f"| {k} | {two(f_['A']['pooled'], r_['A']['pooled'])} ({f_['A']['n_opp']}·{r_['A']['n_opp']}) | "
                     f"{two(f_['bouts']['per_1k'], r_['bouts']['per_1k'], lambda z: _num(z, '.2f'))} | "
                     f"{two(f_['bouts']['pursued_end_frac'], r_['bouts']['pursued_end_frac'])} | "
                     f"{two(f_['bouts']['stop_go_per_1k'], r_['bouts']['stop_go_per_1k'], lambda z: _num(z, '.3f'))} | "
                     f"{two(f_['bouts']['caught3s_given_pursued'], r_['bouts']['caught3s_given_pursued'])} | "
                     f"{two(f_['in_cover_frac'], r_['in_cover_frac'])} | {two(f_['intake_cover_share'], r_['intake_cover_share'])} | "
                     f"{two(f_['intake_edge_share'], r_['intake_edge_share'])} | {two(f_['cover_k_share'], r_['cover_k_share'])} | "
                     f"{two(f_['cross_per_min'], r_['cross_per_min'], lambda z: _num(z, '.3f'))} | "
                     f"{two(f_['cross_quick'], r_['cross_quick'])} | {_num(v['wolf_catch_per_min'], '.3f')} |")
        L += ["", "땅별(결정 시점 사슴 위치의 셀, 침입): 포기율 A, 쫓김 끝 뒤 3초 안 잡힘, HIDE 이동 결과(은신처 밖에서 HIDE 를 시작함), 은신처를 "
              "나간 뒤 30초 안 잡힘. 그리고 HIDE 시작 때 은신처 방향과 위협 방향 사이 각(30° 칸, H15)과 배고파진 뒤 밖 먹이 셀에 닿기까지 "
              "스텝(칸 0~22·23~45·46~90·91~225·226~450·451+, H16):", "",
              "| 팔 | A 보통 · 눈 · 거친 땅 | 쫓김 끝 3초 잡힘 (보통·눈·거친 땅) | HIDE 닿음·잡힘 (보통 / 눈 / 거친 땅) | 나간 뒤 30초 잡힘 | "
              "HIDE 각 0~30°…150~180° | 배고픔 → 먹이 셀 (죽음·잘림) |", "|---|---|---|---|---|---|---|"]
        for k, v in rep.items():
            f_ = v["f"]
            a_t = " · ".join(_pc((f_["A"]["by_terr"].get(t) or {}).get("A")) for t in TERR[:3])
            b_t = " · ".join(_pc((f_["bouts"]["by_terr"].get(t) or {}).get("caught3s")) for t in TERR[:3])
            h_t = " / ".join(f"{_pc((f_['hide'].get(t) or {}).get('reached'))}·{_pc((f_['hide'].get(t) or {}).get('caught'))}"
                             for t in TERR[:3])
            e_t = " · ".join(_pc((f_["exit"].get(t) or {}).get("caught30s")) for t in TERR[:3])
            an = "·".join(_pc(x) for x in f_["hide_angle"]["share"]) if f_["hide_angle"]["n"] else "—"
            hu = f_["hungry"]
            hg = f"{hu['hist']} ({hu['died']}·{hu['censored']})" if hu["n"] else "—"
            L.append(f"| {k} | {a_t} | {b_t} | {h_t} | {e_t} | {an} | {hg} |")
        L += ["", "G0·G0b 보고(침입 − 거주, 개체-스텝당): 번식 차는 칸별 값 JSON(summary 의 repro)에 있다. 은신처 안 시간·아사는 위 표와 칸별 값."]
        et = ex.get("event_terrain")
        if et:
            L += ["", "사건 조건 창 보상의 땅별 대비(G1 니치, 보고만, 시드 짝 t): FLEE − GRAZE = 침입 − 거주, FLEE − HIDE = G1 침입 − G1-H 침입",
                  "", "| 대비 | 보통 | 눈 | 거친 땅 |", "|---|---|---|---|"]
            for k, d in et.items():
                L.append(f"| {k} | " + " | ".join(_f(d[t], 3) for t in TERR[:3]) + " |")
        L += ["", "(i)·(f) 점검(팔 전체): 원 안 막는 위협-스텝(늘 0), 밀어냄·접선·막다른 곳 몫, 추격 고정을 쥔 위협-스텝 몫, 고정 표적을 잡은 몫, "
              "은신처 진입으로 표적을 잃음 /늑대-분, 면역 접촉 /1000:", ""]
        for k, v in rep.items():
            wl, cl = v.get("wall") or {}, v.get("chase_lock") or {}
            L.append(f"- {k}: 원 안 {wl.get('inside_n', '—')}, 밀어냄 {_pc(wl.get('push_share'))}·접선 {_pc(wl.get('slide_share'))}·"
                     f"막다른 곳 {_pc(wl.get('dead_share'))}, 고정 쥠 {_pc(cl.get('held_share'))}, 고정 표적 잡음 "
                     f"{_pc(cl.get('own_catch_share'))}, 표적 잃음 {_num(cl.get('lost_by_cover_per_wolf_min'), '.4f')}, 면역 "
                     f"{_num(v.get('immune_per_1k'), '.4f')}")
    return "\n".join(L) + "\n"


def t0_md(t: dict, meta: dict) -> str:
    """gate/t0_chase.md — T0 와 사용자 추격 모형 확인표(10-3, 보고만)."""
    T0 = t["t0"]
    L = ["# v3 R3 관문 — 세계 점검 T0 와 사용자 추격 모형 확인표 (보고만, 사전 등록 10-3)", "",
         f"모두 거주 R_base(θ {t['theta']:g}, a {t['approach']:g}) 팔, 시드 {t['seeds'][0]}~{t['seeds'][-1]} ({len(t['seeds'])}개) × "
         f"{t['steps']}스텝, 칸 {len(t['cells'])}개. 지표 코드는 results/v3/r3/pre/eval_pre.py. 배수·넓이를 고치는 데 쓰지 않는다.", "",
         "## T0 — 땅별 개체-스텝당 잡힘 (/1000)", "",
         f"- 모아서: 보통 {_num(T0['pooled_per_1k']['normal'], '.4f')}, 눈 {_num(T0['pooled_per_1k']['snow'], '.4f')}, 거친 땅 "
         f"{_num(T0['pooled_per_1k']['rough'], '.4f')}",
         "- 사슴-스텝 몫: " + ", ".join(f"{k} {_pc(v)}" for k, v in T0["deer_share"].items()),
         "- 잡힘 몫: " + ", ".join(f"{k} {_pc(v)}" for k, v in T0["catch_share"].items()),
         f"- 눈 − 보통 (칸 평균 뒤 시드 짝 t): {_f(T0['snow_minus_normal'], 4)} [{T0['snow_minus_normal']['n']}시드]",
         f"- 거친 땅 − 보통: {_f(T0['rough_minus_normal'], 4)} [{T0['rough_minus_normal']['n']}시드]", "",
         "## 확인표 — 잠행형 돌진 (새 사냥 / 이어 사냥, 시작 칸별 표적 잡힘)", "",
         "| 칸 | 모두 n · 잡힘 | 새 사냥 n · 잡힘 | 이어 사냥 n · 잡힘 | 시작 실거리 <2 · 2~4 · 4+ |", "|---|---|---|---|---|"]
    P = t["pounce"]
    for cat in [k for k in P if not k.startswith("_")]:
        v = P[cat]
        fr = (P["_follow"]["fresh"].get(cat) or {})
        fo = (P["_follow"]["follow"].get(cat) or {})
        bd = " · ".join(_pc((v["by_dist"].get(lab) or {}).get("hit")) for lab in ("<2", "2-4", "4+"))
        L.append(f"| {cat} | {v['n']} · {_pc(v['hit'])} | {fr.get('n', 0)} · {_pc(fr.get('hit'))} | {fo.get('n', 0)} · "
                 f"{_pc(fo.get('hit'))} | {bd} |")
    L += ["", "## 확인표 — 쫓김 묶음 (추격형, 쫓기는 스텝의 행동, 안전에 닿기 전 잡힘)", "",
          "| 행동 칸 | n | 잡힘 | 은신처 |", "|---|---|---|---|"]
    ch = t["chase"]["chaser_all"]
    for cat, v in ch["cats"].items():
        L.append(f"| {cat} | {v['n']} | {_pc(v['caught'])} | {_pc(v['cover'])} |")
    L += ["", "땅별 쫓김 묶음(추격형): 잡힘, 첫 반응까지 스텝(중앙값·평균), 반응 없음:", ""]
    for q, v in ch["by_terr"].items():
        L.append(f"- {q}: n {v['n']}, 잡힘 {_pc(v['caught'])}, 첫 반응 {_num(v['latency_p50'], '.1f')}·{_num(v['latency_mean'], '.1f')}스텝, "
                 f"반응 없음 {_pc(v['no_react'])}")
    L += ["", "## 결정 단위 — 쫓기며 도주하던 결정에서 고른 행동별 뒤 잡힘 (3초·8초)", "", "| 행동 | 기회 | 3초 안 잡힘 | 8초 안 잡힘 |",
          "|---|---|---|---|"]
    for b, v in t["a_out"].items():
        L.append(f"| {b} | {v['n']} | {_pc(v['caught3s'])} | {_pc(v['caught8s'])} |")
    wl = t.get("wall")
    if wl:
        L += ["", f"(i) 점검(거주 R_base 팔): 원 안에 있는 막는 위협-스텝 {wl['inside_blocking']}(늘 0), 늑대가 원 둘레에 붙은 몫 "
              f"{_pc(wl['rim_share_wolf'])}, 끼임 연속 길이 칸 [1, 2, 3~5, 6~10, 11~30, 31+] {wl['stuck_hist_wolf']} — 가장 긴 끼임 "
              f"늑대 {wl['stuck_max_wolf']}스텝·플레이어 {wl['stuck_max_player']}스텝(서서 먹는 늑대도 원 둘레에서는 끼임으로 센다 — "
              "pre/eat38/tables.md 8-2)."]
    return "\n".join(L) + "\n"


def pop_md(res: dict) -> str:
    m, s = res["meta"], res["summary"]
    small = len(m["seeds"]) < 40 or m["steps"] < STEPS
    what = f"관문 2단계(통과 규칙 {m['passed']})" if m["stage2"] else f"관문 {m['xs']}"
    L = [f"# v3 R3 무리 확인·역침입 — {what}" + (" — smoke, 판정 아님" if small else ""), "",
         f"설정 {m['config']}, 시드 {m['seeds'][0]}~{m['seeds'][-1]} ({len(m['seeds'])}개) × {m['steps']}스텝, R_base(θ {m['theta']:g}, "
         f"a {m['approach']:g}), 보정 {m['cal'] or '없음'}. 무리 = 128마리 개체-스텝당 보상의 (변형 − 모두 거주) 시드 짝 t, 역침입 = 슬롯 "
         "0~15(거주) − 나머지(거주 + X). 보고만 한다(H1 근거).", ""]
    if res.get("h1"):
        L += ["## H1 (사전 등록 6절)", ""]
        for x, h in res["h1"].items():
            if h.get("complete"):
                L.append(f"- {x}: 관문 판정 {_VERDICT.get(h['gate_verdict'], h['gate_verdict'])} → **{_VERDICT.get(h['verdict'], h['verdict'])}** "
                         f"(무리 유의 음수 칸 {h['pop_sig_neg']}, 8칸 평균 {h['pop_mean8']:+.5f}, 역침입에서 거주가 유의하게 이긴 칸 "
                         f"{h['rev_res_wins']})")
            else:
                L.append(f"- {x}: 계산하지 않음 — {h.get('reason', 'gate.json 이 없다')}")
        L.append("")
    L += ["| 변형 | 칸 평균 | 유의 양수 칸 | 유의 음수 칸 | " + " | ".join(m["cells"]) + " |", "|---" * (4 + len(m["cells"])) + "|"]
    for name, v in s.items():
        L.append(f"| {name} | {v['mean8']:+.5f} | {v['sig_pos']} | {v['sig_neg']} | " + " | ".join(_f(v["cells"][c]) for c in m["cells"]) + " |")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------- #
# 사전 등록 폴더 보호 (16-2)
# --------------------------------------------------------------------- #


def prereg_folder(out: Path) -> str | None:
    """`out` 이 사전 등록 폴더(gate/·gate_b/ 와 그 아래 보정 폴더)면 그 묶음('a'·'b'), 아니면 None."""
    o = Path(out).resolve()
    for b, d in OUT_DIR.items():
        if o == d.resolve() or o.is_relative_to(d.resolve()):
            return b
    return None


def prereg_problems(a, seeds, out: Path) -> list[str]:
    """사전 등록 폴더에 쓰는 실행의 조건 검사(비면 문제 없음, 모듈 docstring)."""
    bad = []
    if a.cmd in ("t0", "layout"):
        bad.append(f"{a.cmd} 는 사전 등록 폴더 밖에서만 한다(사전 등록 실행은 run 이 T0·확인표와 배치 확인을 함께 한다)")
    if rt.prereg_draft(PREREG):
        bad.append(f"사전 등록 {PREREG.name} 제목에 '초안'이 있다(첫 실행 전에 사람 결정·도구 검토·확인표를 마치고 지운다)")
    folder = prereg_folder(out)
    if folder != a.bundle:
        bad.append(f"--bundle {a.bundle} 은 {OUT_DIR[a.bundle]} 에 쓴다")
    want = SEARCH_SEEDS if a.cmd == "search" else GATE_SEEDS
    if list(seeds) != want:
        bad.append(f"--seeds (사전 등록 {want[0]}~{want[-1]})")
    if a.steps != STEPS:
        bad.append(f"--steps (사전 등록 {STEPS})")
    if a.cells is not None and sorted(a.cells) != sorted(CELLS):
        bad.append("--cells (사전 등록 칸 8개 모두)")
    if list(a.grid_theta) != list(GRID_THETA) or list(a.grid_approach) != list(GRID_APPROACH):
        bad.append("--grid-theta/--grid-approach (사전 등록 격자)")
    if a.config != CONFIG:
        bad.append(f"--config (사전 등록 {CONFIG})")
    else:
        now = prereg_digests(CONFIG)
        if now != PREREG_DIGEST:
            bad.append(f"설정 digest {now} 가 사전 등록 1절 값 {PREREG_DIGEST} 과 다르다(코드나 설정이 바뀌었다 — 다시 재서 사전 등록과 "
                       "PREREG_DIGEST 를 함께 고친다)")
    if a.force:
        bad.append("--force (사전 등록 폴더의 결과는 한 번 쓴다)")
    if a.cmd == "search" and a.bundle != "a":
        bad.append("search 는 묶음 A 폴더(gate/)에 한 번만 한다(묶음 B 는 같은 탐색 값을 쓴다)")
    cal = tuple(getattr(a, "cal_gates", ()) or ())
    if a.cmd == "run":
        if getattr(a, "no_t0", False) and not cal and a.bundle == "a":
            bad.append("--no-t0 (사전 등록 첫 판정은 T0·확인표를 잰다)")
        if not cal:
            if a.gates is not None and sorted(a.gates) != sorted(BUNDLE[a.bundle]):
                bad.append(f"--gates (사전 등록은 묶음 {a.bundle.upper()} 의 관문 모두와 보고 팔: {list(BUNDLE[a.bundle])})")
            if Path(out).resolve() != OUT_DIR[a.bundle].resolve():
                bad.append(f"--out (첫 판정은 {OUT_DIR[a.bundle]})")
        else:
            bad += _cal_problems(a, out)
    if a.cmd == "pop":
        gp = Path(out) / "gate.json"
        bad += _pop_folder_problems(a, seeds, out)
        if not a.stage2 and not gp.exists():
            bad.append(f"{gp} 가 없다(무리 확인은 관문 판정 뒤, 조건부 통과를 따질 때만)")
        elif not a.stage2:
            gj = json.loads(gp.read_text(encoding="utf-8"))
            for x in a.x:
                gx = gj["gate"].get(x) or {}
                if not (gx.get("complete") and gx.get("c1") and gx.get("c2")
                        and gx.get("verdict") in ("fail", "low_power", "cross_insufficient")):
                    bad.append(f"--x {x} (조건부 통과는 (1)·(2) 통과 & (3) 실패·판정 불능·교차 판정 불가일 때만 따진다: {gx.get('verdict')})")
            # H1 은 gate.json 과 조건이 같을 때만 적힌다. 다르면 pop.json 만 한 번 쓰이고 바른 무리 확인을 다시 못 하므로 미리 거부한다
            gm = gj.get("meta") or {}
            th, apr = a.theta, a.approach
            if th is None and (GATE_DIR / "search.json").exists():
                best = json.loads((GATE_DIR / "search.json").read_text(encoding="utf-8"))["best"]
                th, apr = best["theta"], best["approach"]
            want = dict(config=a.config, seeds=list(seeds), steps=int(a.steps), theta=th, approach=apr, bundle=a.bundle,
                        cells=list(a.cells or CELLS))           # pop() 이 H1 을 적을 때 보는 조건과 같은 비교(칸은 순서까지)
            diff = [k for k, v in want.items() if gm.get(k) != v]
            cal_now = list(getattr(a, "cal_gates", None) or []) if a.cal else []
            if sorted(gm.get("cal") or []) != sorted(cal_now):
                diff.append("cal")
            if diff:
                bad.append(f"{gp} 의 조건과 다르다({diff}) — 그대로 돌리면 H1 을 적지 못한다")
        if a.stage2 and not a.passed:
            bad.append("--passed (2단계 무리 확인은 통과 니치 규칙을 준다)")
        name = "pop_stage2.json" if a.stage2 else "pop.json"
        if (Path(out) / name).exists():
            bad.append(f"{Path(out) / name} 가 이미 있다(결과는 한 번 쓴다)")
    if a.cmd == "run" and (Path(out) / "invasion.json").exists():
        bad.append(f"{Path(out) / 'invasion.json'} 가 이미 있다(결과는 한 번 쓴다)")
    if a.cmd in ("run", "pop"):
        sp = GATE_DIR / "search.json"
        cache = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else None
        if cache is None:
            bad.append(f"{sp} 가 없다(거주 탐색을 먼저 한다)")
        else:
            cm = cache.get("meta", {})
            if cm.get("seeds") != SEARCH_SEEDS or cm.get("steps") != STEPS or sorted(cm.get("cells", [])) != sorted(CELLS):
                bad.append("탐색 캐시의 조건(탐색 시드 33000~33039 × 3000, 칸 8개)이 사전 등록과 다르다")
            if cm.get("digest") != {c: config_digest(cell_cfg(c, CONFIG)) for c in CELLS}:
                bad.append("설정 digest (탐색 캐시를 만든 뒤 설정이 바뀌었다 — 옛 탐색 값으로 판정하지 않는다)")
            if a.theta is not None and (cache["best"]["theta"], cache["best"]["approach"]) != (a.theta, a.approach):
                bad.append(f"--theta/--approach (사전 등록 폴더에서는 탐색 캐시의 값과 같아야 한다: {cache['best']})")
    return bad


def _cal_problems(a, out: Path) -> list[str]:
    """보정 회차(9-1): 보정 1 만, 관문 하나, 첫 판정에서 (1) 니치 실패(보정 대상)인 관문, 폴더 gate/cal1/<관문>/."""
    bad = []
    if a.cal != 1:
        bad.append("--cal (보정은 1 만 도구로 한다 — G2 의 2) H15 는 사람 승인과 코드 변경이다)")
    if len(a.cal_gates) != 1:
        bad.append("--gates (보정 회차는 관문 하나씩)")
        return bad
    x = a.cal_gates[0]
    want = OUT_DIR[a.bundle] / f"cal{a.cal}" / x
    if Path(out).resolve() != want.resolve():
        bad.append(f"--out (보정 결과는 {want})")
    gp = OUT_DIR[a.bundle] / "gate.json"
    if not gp.exists():
        bad.append(f"{gp} 가 없다(보정은 첫 판정 뒤)")
    else:
        gx = json.loads(gp.read_text(encoding="utf-8"))["gate"].get(x) or {}
        if not gx.get("cal_eligible"):
            bad.append(f"{x} 는 보정 대상이 아니다(보정은 (1) 니치 실패에만 건다, 첫 판정 {gx.get('verdict')})")
    return bad


def _pop_folder_problems(a, seeds, out: Path) -> list[str]:
    """무리 확인의 폴더(6·11절): H1 무리 확인은 첫 판정 폴더(gate/·gate_b/), 보정 회차의 H1 은 gate/cal1/<관문>/(관문 하나, 보정 1,
    첫 판정의 보정 대상). 2단계 무리 확인은 묶음 A 폴더 gate/ 에서, 관문 1단계 최종표(final.json — report)의 통과 니치(FSM_R3 줄)와
    보정 1 그대로만 받는다. 결과는 한 번 쓰므로 폴더·조건이 틀린 실행이 바른 실행의 자리를 먼저 차지하지 않게 한다."""
    bad = []
    here = Path(out).resolve()
    if a.stage2:
        if a.bundle != "a" or here != GATE_DIR.resolve():
            bad.append(f"--out (2단계 무리 확인은 {GATE_DIR}, --bundle a)")
        fp, sp = GATE_DIR / "final.json", GATE_DIR / "search.json"
        if not fp.exists() or not sp.exists():
            bad.append(f"{fp} 가 없다(2단계 무리 확인은 관문 1단계 최종표 뒤 — report)")
        else:
            st = rt.setup_from_final(json.loads(fp.read_text(encoding="utf-8")), json.loads(sp.read_text(encoding="utf-8")))
            if sorted(a.passed) != sorted(st["lines"]):
                bad.append(f"--passed (최종표의 통과·조건부 통과 니치 {list(st['lines'])})")
            cal_now = list(a.cal_gates) if a.cal else []
            if sorted(cal_now) != sorted(st["cal"]):
                bad.append(f"--cal/--gates (최종표의 보정 1 니치 {list(st['cal'])})")
        return bad
    if a.cal:
        if a.cal != 1:
            bad.append("--cal (보정은 1 만 도구로 한다)")
        if len(a.x) != 1 or list(a.cal_gates) != list(a.x):
            bad.append("--x (보정 회차의 무리 확인은 그 관문 하나)")
            return bad
        want = OUT_DIR[a.bundle] / f"cal{a.cal}" / a.x[0]
        gp0 = OUT_DIR[a.bundle] / "gate.json"
        if gp0.exists():
            g0 = json.loads(gp0.read_text(encoding="utf-8"))["gate"].get(a.x[0]) or {}
            if not g0.get("cal_eligible"):
                bad.append(f"{a.x[0]} 는 보정 대상이 아니었다(첫 판정 {g0.get('verdict')}) — 보정 회차 무리 확인이 없다")
    else:
        want = OUT_DIR[a.bundle]
    if here != want.resolve():
        bad.append(f"--out (이 무리 확인은 {want})")
    return bad


def main(argv=None) -> int:
    import repertoire_rules as rr

    ap = argparse.ArgumentParser(description="v3 R3 관문(손 규칙 소수 침입·무리 확인·역침입·최종 관문표)")
    ap.add_argument("cmd", choices=("search", "run", "pop", "t0", "layout", "report"))
    ap.add_argument("--bundle", choices=("a", "b"), default="a", help="묶음 A(필수 관문) 또는 B(SLEEP, 선택)")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--out", default=None, help="결과 폴더. 기본값은 사전 등록 폴더(gate/·gate_b/, 보정은 gate/cal1/<관문>/)")
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--seeds", type=int, nargs="+", default=None)
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--cells", nargs="+", default=None, choices=sorted(CELLS))
    ap.add_argument("--theta", type=float, default=None, help="거주 θ (주면 탐색 캐시를 쓰지 않는다)")
    ap.add_argument("--approach", type=float, default=None, help="거주 a (--theta 와 함께)")
    ap.add_argument("--grid-theta", type=float, nargs="+", default=list(GRID_THETA))
    ap.add_argument("--grid-approach", type=float, nargs="+", default=list(GRID_APPROACH))
    ap.add_argument("--gates", nargs="+", default=None, choices=rr.R3_X, help="돌릴 관문 규칙(기본: 묶음의 모두)")
    ap.add_argument("--cal", type=int, default=0, help="보정 회차(0 = 첫 판정, 1 = 보정 1)")
    ap.add_argument("--no-t0", action="store_true", help="T0·확인표를 빼고 잰다(사전 등록 폴더 밖만)")
    ap.add_argument("--x", nargs="+", default=[], choices=rr.R3_X, help="pop: H1 을 따질 관문")
    ap.add_argument("--stage2", action="store_true", help="pop: 관문 2단계 무리 확인(통과 규칙 묶음)")
    ap.add_argument("--passed", nargs="+", default=[], choices=rr.R3_X, help="pop --stage2: 통과 니치 규칙")
    ap.add_argument("--force", action="store_true", help="조건이 다른 탐색 캐시를 덮는다(사전 등록 폴더 밖만)")
    a = ap.parse_args(argv)
    if (a.theta is None) != (a.approach is None):
        ap.error("--theta 와 --approach 는 함께 준다")
    if a.cmd == "report":
        r = report()
        print(r["md"])
        return 0
    seeds = a.seeds or (SEARCH_SEEDS if a.cmd == "search" else GATE_SEEDS)
    a.cal_gates = list(a.gates or []) if a.cal else []
    if a.cmd == "pop" and a.cal and not a.gates:
        a.cal_gates = list(a.x)
    if a.out is None:
        if a.cal:
            a.out = str(OUT_DIR[a.bundle] / f"cal{a.cal}" / (a.cal_gates[0] if a.cal_gates else "_"))
        else:
            a.out = str(OUT_DIR[a.bundle])
    out = Path(a.out)
    if a.cmd == "layout":
        bad = rt.seed_problems(seeds)
        if bad:
            ap.error("시드: " + ", ".join(bad))
        print(json.dumps(layout_check(seeds, a.config, a.cells, a.bundle), indent=1))
        return 0
    if prereg_folder(out) is not None:
        bad = prereg_problems(a, seeds, out)
        if bad:
            ap.error(f"사전 등록 폴더 {out} 에는 사전 등록 조건만 쓴다(결과를 덮지 않게). 다른 조건: " + "; ".join(bad)
                     + ". smoke·부분 실행은 --out 에 다른 폴더를 준다")
    else:
        bad = rt.seed_problems(seeds)
        if bad:
            ap.error("사전 등록 폴더 밖 실행은 관문·최종 판정 시드를 쓰지 않는다: " + ", ".join(bad))
    if a.cal and a.cmd == "run" and not a.cal_gates:
        ap.error("--cal 은 --gates 로 관문 하나를 준다")
    try:
        if a.cmd == "search":
            res = search(seeds, a.steps, a.workers, out, a.config, a.grid_theta, a.grid_approach, a.cells, a.force)
            print(json.dumps(res["best"]), flush=True)
            return 0
        if a.theta is None:
            sp = GATE_DIR / "search.json" if prereg_folder(out) else out / "search.json"
            if not sp.exists():
                ap.error(f"{sp} 가 없다 — search 를 먼저 하거나 --theta/--approach 를 준다")
            best = json.loads(sp.read_text(encoding="utf-8"))["best"]
            th, apr = best["theta"], best["approach"]
        else:
            th, apr = a.theta, a.approach
    except StaleCache as e:
        ap.error(str(e))
    cal = tuple(a.cal_gates) if a.cal else ()
    if a.cmd == "run":
        run(seeds, a.steps, a.workers, out, th, apr, a.config, a.cells, a.gates, a.bundle, cal, not a.no_t0)
        print((out / "invasion.md").read_text(encoding="utf-8"))
    elif a.cmd == "t0":
        res = t0_chase(seeds, a.steps, a.workers, th, apr, a.config, a.cells)
        out.mkdir(parents=True, exist_ok=True)
        (out / "t0_chase.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        (out / "t0_chase.md").write_text(t0_md(res, {}), encoding="utf-8")
        print((out / "t0_chase.md").read_text(encoding="utf-8"))
    else:
        if not a.stage2 and not a.x:
            ap.error("pop 은 --x <관문> 또는 --stage2 --passed <규칙> 을 준다")
        name = "pop_stage2" if a.stage2 else "pop"
        pop(seeds, a.steps, a.workers, out, th, apr, a.config, a.cells, a.x, a.stage2, a.passed, cal, a.bundle)
        print((out / f"{name}.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
