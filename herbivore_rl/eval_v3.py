"""v3 R1 판정 도구 — 행동 고르기 RL 정책을 손 규칙(FSM)·대조군과 비교한다 (명세 `Docs/RL_Policy/RL_V3_R1_SPEC.md` 5절,
사전 등록 `results/v3/r1/PREREG.md` 3·4절).

    # herbivore_rl/ 에서. 학습 모델 하나(모델 시드 하나)의 판정 — 사전 등록 조건(평가 시드 10000~10019 × 10000스텝)
    python eval_v3.py run --model ckpt/v3/v3_r1_g995_s0_20m.zip --name s0 --workers 14
    # FREEZE 판은 기본이 '가까운 위협 앞 얼기'(near, R0 에서 통과한 판)다. 원래 판으로 재려면(보고·비교용)
    python eval_v3.py run --model ... --name s0_orig --freeze-variant orig --out <다른 폴더>
    # 6시드 모아 보기(judge.md, R1 성공 = 6시드 중 4시드 이상 통과)
    python eval_v3.py summarize --names s0 s1 s2 s3 s4 s5
    # 출시 선별(보정 시드 20000~20019)·조기 중단 점검(20000~20002 × 3000스텝, 체크포인트)은 다른 폴더에 쓴다
    python eval_v3.py run --model ckpt/v3/v3_r1_g995_s0_20m_2m.zip --name s0_2m --seeds 20000 20001 20002 --steps 3000 \
        --policies rl fsm --out results/v3/r1/early
    # smoke: 시드 2개 · 300스텝 · tail 100. 사전 등록 폴더가 아닌 --out 이 꼭 필요하다
    python eval_v3.py run --model <zip> --name smoke --seeds 10000 10001 --steps 300 --tail 100 --out <임시 폴더>

- 세계: 판정 설정 `configs/v3_r1_on.yaml`(train.repertoire 블록의 허용 행동이 목록이다 — R0 결과로 graze·flee·hide·freeze,
  SLEEP 은 빠졌다). 정책은 모두 argmax·결정적이다.
- 정책 (명세 5절):
  · rl: 학습 정책(`{"kind": "rep_learned"}`, 마스크 로짓 argmax)
  · fsm: 거주 규칙 R_base(θ 4, a 0.9)에 목록 행동의 니치 규칙(`repertoire_rules.NICHES`)을 얹는다. 우선순위 HIDE > FREEZE >
    SLEEP > R_base (규칙 래퍼를 SLEEP → FREEZE → HIDE 순서로 씌워 뒤 규칙이 앞 규칙을 덮는다. 목록에 없는 행동의 규칙은 빠진다 —
    지금 목록이면 HIDE > FREEZE > R_base). FREEZE 는 --freeze-variant near(기본, R0 에서 통과한 판)면 '가까운 위협 앞' 판(R0 의
    cross 조건: 바탕 규칙이 FLEE 를 고르고 위협이 6 안이거나 접근 ≥ 0.9 면 얼기), orig 면 원래 니치 조건이다
  · c_<행동>: 늘 그 행동을 요청한다. 가능하지 않으면(`rep_policy.feasible_mask`) GRAZE
  · c1p (C1′): 결정 때 RL 의 판정 세계 결정 선택 빈도(모든 평가 시드를 합친 값)를 마스크(허용 ∧ 가능 ∧ 결정)로 다시 맞춰 해시로
    뽑는다. u = U(H(606, 평가 시드, 0, 개체 키, tick)) (`env_v2.rollout` 의 hold_hash·hold_uniform, 개체 키는 리스폰마다 세대가
    오른다). RL 을 먼저 돌린 뒤 돌린다
  · c4_app: RL 에 관측 pred_approach = 0.5 를 넣는다. c4_phase: 위상 관측 visibility·to_transition 을 중립 1·1 로 넣는다.
    망 입력만 바뀌고 마스크는 참 상태로 만든다(`obs_fix` 래퍼)
- 지표 (PREREG 3절):
  · G_γ (γ 0.9916661555611042, tail 600, `env_v2.rollout.g_gamma`), 피식률·아사율(개체-스텝당), 행동별 사용 비중(실행한 행동의
    개체-스텝 비율), 깜빡임(전환 중 3초 안 A-B-A, `World.repertoire_stats` 와 같은 정의 — 시드를 합친 수로 낸다), 결정 비율
  · U_X: 결정 시점(요청을 읽는 개체·스텝, `World.rep_peek`) 표본만으로 센 조건부 선택 확률의 차. 선택 = 그 스텝의 요청(기상 결정의
    SLEEP 요청은 arbitrate 처럼 wake_target). 보임 = 관측 pred_count > 0, 거리 = 관측 pred_dist × see_r(가장 가까운 보이는
    위협), 접근 = 관측 pred_approach, 은신처 = 관측 cover_dist × obs_cover_norm, 밤 d ≥ 0.8·낮 d ≤ 0.2(관측 visibility,
    `repertoire_rules.features_of_obs`). 평가 시드를 합친 수(분자·분모)로 낸다
      U_ESC  = P(FLEE ∪ HIDE ∪ FREEZE | 보임 & 접근 ≥ 0.75 & 거리 < 10) − P(같은 셋 | 위협 없음 = 안 보임)
      U_HIDE = P(HIDE | 보임 & 은신처 ≤ 5) − P(HIDE | 안 보임 & 낮)
      U_FREEZE near = P(FREEZE | 보임 & (거리 < 6 또는 접근 ≥ 0.9)) − P(FREEZE | 보임 & 거리 ≥ 8 & 접근 < 0.7), orig = 두 항을 바꾼 것
      U_SLEEP = P(SLEEP | 밤 & E ≥ 0.5) − P(SLEEP | 낮)
  · 위험 할당(보고만): FLEE 진입(결정 시점에 FLEE 를 고르고 지금 행동이 FLEE 가 아닌, 위협이 보이는 표본) 때 거리의 중앙값을 배부름
    (E > 0.7)·배고픔(E < 0.35)으로 나눈 차(배부름 − 배고픔)
  · C4 하락률 = (U − U_C4) / U
- 판정 (PREREG 4절, 모델 시드마다 모두 만족): (1) RL − FSM G_γ 짝 t ≥ −t_crit(평가 시드 20 이면 자유도 19, 2.093. t > t_crit 면 'FSM
  을 이김'), (2) 목록 행동의 U 문턱(U_ESC ≥ 0.5 늘, U_HIDE ≥ 0.3, U_FREEZE ≥ 0.3, U_SLEEP ≥ 0.5), (3) 목록의 모든 행동 사용 비중
  ≥ 2%·깜빡임 ≤ 10%, (4) SLEEP 이 목록에 있으면 위상 중립 고정에서 U_SLEEP 50% 이상 하락, FREEZE near 판이 목록에 있으면 접근 0.5
  고정에서 U_FREEZE 50% 이상 하락(그 밖의 C4 는 보고만), (5) 아사율 ≤ 1.5 × FSM 아사율(평가 시드 평균)
- 결과: `<out>/<name>.json`(요약·시드별 값), `<out>/<name>.md`(판정표 먼저). `summarize` 는 `<out>/judge.md`.
- 사전 등록 폴더(`results/v3/r1/judge`, --out 기본값)에는 PREREG 조건(시드 10000~10019, 10000스텝, 판정 설정, tail 600, 정책
  모두, FREEZE 판 near)만 쓴다 — 다른 조건이면 시작 전에 멈춘다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from env_v2.repertoire import BEHAVIOR_NAMES, FLEE, FREEZE, GRAZE, HIDE, N_BEHAVIORS, SLEEP  # noqa: E402

CONFIG = "configs/v3_r1_on.yaml"
EVAL_SEEDS = list(range(10000, 10020))
STEPS = 10000
GAMMA = 0.9916661555611042
TAIL = 600
THETA, APPROACH = 4.0, 0.9                  # 거주 규칙 R_base(θ, a) (명세 5절)
FREEZE_VARIANTS = ("near", "orig")
# PREREG 3절 지표 조건(지표 정의이고 세계 계수가 아니다). 거리·은신처 단위는 세계 길이
U_COND = dict(esc_approach=0.75, esc_dist=10.0, hide_cover=5.0, fz_near=6.0, fz_fast=0.9, fz_far=8.0, fz_slow=0.7,
              sleep_energy=0.5)
U_NAMES = ("esc", "hide", "freeze", "sleep")
U_TARGET = {"esc": (FLEE, HIDE, FREEZE), "hide": (HIDE,), "freeze": (FREEZE,), "sleep": (SLEEP,)}
# PREREG 4절 문턱
U_MIN = {"esc": 0.5, "hide": 0.3, "freeze": 0.3, "sleep": 0.5}
USE_MIN, FLICKER_MAX, C4_DROP_MIN, STARVE_RATIO_MAX = 0.02, 0.10, 0.5, 1.5
FULL_E, HUNGRY_E = 0.7, 0.35                # 위험 할당 에너지 구간 (명세 5절)
C1P_TAG = 606                               # C1′ 해시 스트림 구분값(rollout._SALT 101~404·지연 505 와 겹치지 않는다)
PREREG_OUT = HERE / "results" / "v3" / "r1" / "judge"
POLICY_ORDER = ("rl", "fsm", "c_graze", "c_flee", "c_hide", "c_freeze", "c_sleep", "c1p", "c4_app", "c4_phase")


# --------------------------------------------------------------------- #
# 지표 조건 (train_v3.py 의 학습 기록도 쓴다)
# --------------------------------------------------------------------- #


def active_u(allowed) -> tuple[str, ...]:
    """목록(허용 행동 이름)에서 볼 U. U_ESC 는 늘(FLEE 가 늘 있다), 나머지는 그 행동이 목록에 있을 때만."""
    allowed = set(allowed)
    return tuple(u for u in U_NAMES if u == "esc" or u in allowed)


def u_terms(f: dict, variant: str = "near") -> dict:
    """규칙 입력(`repertoire_rules.features_of_obs`) → {U 이름: (첫 항 조건, 둘째 항 조건)} (모듈 docstring '지표')."""
    if variant not in FREEZE_VARIANTS:
        raise ValueError(f"freeze 판은 {FREEZE_VARIANTS} 중 하나다. 받은 값: {variant!r}")
    c = U_COND
    seen, dist, app = f["seen"], f["dist"], f["approach"]
    none = ~seen
    near = seen & ((dist < c["fz_near"]) | (app >= c["fz_fast"]))
    far = seen & (dist >= c["fz_far"]) & (app < c["fz_slow"])
    return {"esc": (seen & (app >= c["esc_approach"]) & (dist < c["esc_dist"]), none),
            "hide": (seen & (f["cover_d"] <= c["hide_cover"]), none & f["day"]),
            "freeze": (near, far) if variant == "near" else (far, near),
            "sleep": (f["night"] & (f["energy"] >= c["sleep_energy"]), f["day"])}


def u_value(cnt) -> float | None:
    """[첫 항 표본 수, 첫 항 적중, 둘째 항 표본 수, 둘째 항 적중] → U (분모가 0 이면 None)."""
    na, ha, nb, hb = (float(x) for x in cnt)
    if na <= 0 or nb <= 0:
        return None
    return ha / na - hb / nb


# --------------------------------------------------------------------- #
# 정책
# --------------------------------------------------------------------- #


class ConstRequest:
    """C_k: 늘 행동 k 를 요청한다. 가능하지 않으면(관측 가능 조건) GRAZE."""

    def __init__(self, k: int, obs_names):
        self.k, self.obs_names = int(k), tuple(obs_names)

    def __call__(self, obs):
        from env_v2.rep_policy import feasible_mask

        ok = feasible_mask(obs, self.obs_names)[:, self.k]
        return np.where(ok, self.k, GRAZE).astype(np.float64)[:, None]


class C1Prime:
    """C1′ (빈도를 맞춘 무작위, 모듈 docstring). 결정 때 빈도 q 를 마스크로 다시 맞춰 해시 u 로 뽑는다. 결정이 아니면 마스크가 지금
    행동 한 칸이라 그 행동이 나온다(세계가 읽지 않는다)."""

    def __init__(self, freq, allowed_mask, seed: int, salt: int = 0):
        from env_v2.rollout import hold_hash

        self.q = np.asarray(freq, dtype=np.float64)
        self.params = {"allowed_mask": np.asarray(allowed_mask, dtype=bool)}
        self.seed, self.salt = int(seed), int(salt)
        self._h0 = hold_hash(C1P_TAG, self.seed, self.salt)
        self.gen = None
        self.tick = 0
        self.world = None

    def bind_world(self, world) -> None:
        self.world = world
        self.gen = np.zeros(world.N, dtype=np.uint64)

    def observe_done(self, done) -> None:
        self.gen[np.asarray(done, dtype=bool)] += np.uint64(1)

    def __call__(self, obs):
        from env_v2.rep_policy import action_mask, sample_masked
        from env_v2.rollout import hold_agent_keys, hold_chain, hold_uniform

        if self.world is None:
            raise ValueError("C1′ 정책은 bind_world(w) 뒤에 쓴다")
        m = action_mask(self.world, self.world.observe(), self.params)
        keys = hold_agent_keys(np.arange(len(m)), self.gen)
        u = hold_uniform(hold_chain(self._h0, keys, self.tick))
        self.tick += 1
        return sample_masked(np.broadcast_to(self.q, m.shape), m, u).astype(np.float64)[:, None]


def fsm_spec(cfg, allowed, variant: str) -> dict:
    """FSM 스펙: R_base(θ 4, a 0.9) + 목록 행동의 니치 규칙, 우선순위 HIDE > FREEZE > SLEEP > R_base (모듈 docstring)."""
    import repertoire_rules as rr

    geo = rr._geom(cfg)
    spec = rr.rule_spec(cfg, THETA, APPROACH)
    for x in ("sleep", "freeze", "hide"):           # 뒤에 씌운 규칙이 앞 규칙을 덮는다 → 우선순위는 이 순서의 반대
        if x in allowed:
            mode = "cross" if (x == "freeze" and variant == "near") else "niche"
            spec["wrap"].append(dict(factory="repertoire_rules:x_rule", x=x, mode=mode, slots=None, **rr.NICHES[x], **geo))
    return spec


def policy_spec(name: str, model: str, cfg, allowed, variant: str, freq=None) -> dict:
    """정책 이름 → 워커에 넘기는 스펙(dict, 피클 가능)."""
    from env_v2.world import obs_names

    names = list(obs_names(cfg))
    rl = {"kind": "rep_learned", "path": str(model)}
    if name == "rl":
        return {"build": rl}
    if name == "fsm":
        return {"build": fsm_spec(cfg, allowed, variant)}
    if name.startswith("c_"):
        b = name[2:]
        if b not in allowed:
            raise ValueError(f"{name}: {b} 는 목록 {list(allowed)} 에 없다")
        return {"const": BEHAVIOR_NAMES.index(b)}
    if name == "c1p":
        if freq is None:
            raise ValueError("c1p 는 RL 의 결정 선택 빈도가 필요하다(RL 을 먼저 돌린다)")
        return {"c1p": [float(x) for x in freq]}
    if name == "c4_app":
        return {"build": {"policy": rl, "wrap": [{"kind": "obs_fix", "dims": [names.index("pred_approach")],
                                                  "values": [0.5]}]}}
    if name == "c4_phase":
        return {"build": {"policy": rl, "wrap": [{"kind": "obs_fix", "dims": [names.index("visibility"),
                                                                              names.index("to_transition")],
                                                  "values": [1.0, 1.0]}]}}
    raise ValueError(f"모르는 정책 {name!r}. 쓸 수 있는 이름: {POLICY_ORDER}")


def _make_policy(pspec: dict, cfg, rep, seed: int):
    from env_v2 import rollout as ro
    from env_v2.world import obs_names

    if "build" in pspec:
        return ro.build_policy(pspec["build"], seed)
    if "const" in pspec:
        return ConstRequest(pspec["const"], obs_names(cfg))
    if "c1p" in pspec:
        return C1Prime(pspec["c1p"], rep["allowed_mask"], seed)
    raise ValueError(f"모르는 정책 스펙: {pspec!r}")


# --------------------------------------------------------------------- #
# 롤아웃 하나 (워커)
# --------------------------------------------------------------------- #


def _job(args):
    """(정책 이름, 정책 스펙, 평가 시드) 하나. 결정 시점 표본으로 U 의 수를 센다. 인자는 피클 가능한 것만 받는다."""
    from env_v2 import rollout as ro
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import rep_params
    from env_v2.world import World

    import repertoire_rules as rr

    name, pspec, seed, steps, config, gamma, tail, variant = args
    cfg = load_v2_config(HERE / config)
    rep = rep_params(cfg)
    geo = rr._geom(cfg)
    pol = _make_policy(pspec, cfg, rep, seed)
    w = World(cfg, seeds=[seed])
    ro.forward_bind(pol, w)
    N = w.N
    rew = np.empty((steps, N))
    done = np.empty((steps, N), dtype=bool)
    u_cnt = {u: np.zeros(4, dtype=np.int64) for u in U_NAMES}
    choice = np.zeros(N_BEHAVIORS, dtype=np.int64)
    n_dec = 0
    entries = {"full": [], "hungry": []}
    for t in range(steps):
        obs = w.observe()
        pk = w.rep_peek()
        a = np.asarray(pol(obs), dtype=np.float64)
        dec = pk["reads"]
        if dec.any():
            req = a[dec, 0].astype(np.int64)
            wake = pk["wake_decide"][dec]
            chosen = np.where(wake & (req == SLEEP), w._rs.wake_target[dec].astype(np.int64), req)
            f = rr.features_of_obs(obs[dec], geo)
            for u, (ca, cb) in u_terms(f, variant).items():
                hit = np.isin(chosen, U_TARGET[u])
                u_cnt[u] += (np.count_nonzero(ca), np.count_nonzero(ca & hit), np.count_nonzero(cb),
                             np.count_nonzero(cb & hit))
            choice += np.bincount(chosen, minlength=N_BEHAVIORS)
            n_dec += int(dec.sum())
            ent = (chosen == FLEE) & (pk["behavior"][dec] != FLEE) & f["seen"]
            if ent.any():
                e, d = f["energy"][ent], f["dist"][ent]
                entries["full"] += d[e > FULL_E].tolist()
                entries["hungry"] += d[e < HUNGRY_E].tolist()
        _, r, d_, _ = w.step(a)
        rew[t], done[t] = r, d_
        ro.forward_done(pol, d_)
    beh = w._rep_hist.sum((0, 1)).astype(np.int64)
    return dict(name=name, seed=int(seed), g_gamma=ro.g_gamma(rew, done, gamma, tail),
                pred_rate=w._pred_deaths / (steps * N), starve_rate=w._starve_deaths / (steps * N),
                mean_return=float(w.stats()["mean_return"]), beh=beh.tolist(), switch=int(w._rep_switch),
                flicker=int(w._rep_flicker), decide=int(w._rep_decide), n=int(steps * N), n_dec=n_dec,
                u_cnt={u: v.tolist() for u, v in u_cnt.items()}, choice=choice.tolist(), entries=entries)


def _map(jobs, workers):
    if workers <= 1:
        return [_job(j) for j in jobs]
    from env.rollout import _init_worker             # 워커의 BLAS 스레드를 1 로(배열이 작아 스레딩은 손해다)

    with ProcessPoolExecutor(min(workers, len(jobs)), initializer=_init_worker) as ex:
        return list(ex.map(_job, jobs, chunksize=1))


# --------------------------------------------------------------------- #
# 모으기·판정
# --------------------------------------------------------------------- #


def pooled(rows: list[dict], allowed) -> dict:
    """한 정책의 시드별 행 → 시드를 합친 지표(사용 비중·깜빡임·결정 비율·U·위험 할당)와 시드 평균(G_γ·피식·아사)."""
    beh = np.sum([r["beh"] for r in rows], axis=0).astype(np.float64)
    sw, fl = sum(r["switch"] for r in rows), sum(r["flicker"] for r in rows)
    n, dec = sum(r["n"] for r in rows), sum(r["decide"] for r in rows)
    u_cnt = {u: np.sum([r["u_cnt"][u] for r in rows], axis=0) for u in U_NAMES}
    choice = np.sum([r["choice"] for r in rows], axis=0).astype(np.float64)
    full = [x for r in rows for x in r["entries"]["full"]]
    hungry = [x for r in rows for x in r["entries"]["hungry"]]
    med = lambda xs: float(np.median(xs)) if xs else None          # noqa: E731
    mf, mh = med(full), med(hungry)
    return dict(
        g_gamma=float(np.mean([r["g_gamma"] for r in rows])),
        pred_rate=float(np.mean([r["pred_rate"] for r in rows])),
        starve_rate=float(np.mean([r["starve_rate"] for r in rows])),
        mean_return=float(np.mean([r["mean_return"] for r in rows])),
        use={b: float(beh[k] / beh.sum()) if beh.sum() else None for k, b in enumerate(BEHAVIOR_NAMES)},
        flicker=fl / sw if sw else None, switch_n=int(sw), decide_frac=dec / n if n else None,
        choice_freq=(choice / choice.sum()).tolist() if choice.sum() else [0.0] * N_BEHAVIORS,
        u={u: u_value(u_cnt[u]) for u in U_NAMES}, u_cnt={u: u_cnt[u].tolist() for u in U_NAMES},
        risk=dict(median_full=mf, median_hungry=mh, n_full=len(full), n_hungry=len(hungry),
                  diff=None if mf is None or mh is None else mf - mh))


def paired_t(a, b) -> dict:
    """시드별 짝 차 a − b → 평균·t·임계(양측 5%, 자유도 n − 1). 표본이 2개 미만이거나 표준편차 0 이면 t None."""
    from scipy.stats import t as tdist

    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    d = d[np.isfinite(d)]
    n = len(d)
    crit = float(tdist.ppf(0.975, n - 1)) if n > 1 else None
    if n < 2:
        return dict(mean=float(d.mean()) if n else float("nan"), t=None, n=n, crit=crit)
    se = float(d.std(ddof=1)) / math.sqrt(n)
    return dict(mean=float(d.mean()), t=float(d.mean() / se) if se > 0 else None, n=n, crit=crit)


def drop(u, u_c4):
    """C4 하락률 (U − U_C4) / U. U ≤ 0 이거나 없으면 None."""
    if u is None or u_c4 is None or u <= 0:
        return None
    return (u - u_c4) / u


def gate(res: dict, allowed, variant: str) -> dict:
    """PREREG 4절 판정 (모듈 docstring). 조건마다 값·문턱·통과, 그리고 pass(모두 통과)."""
    P = res["pooled"]
    rl, fsm = P["rl"], P["fsm"]
    out = {}
    pt = res["perf"]
    if pt["t"] is not None:
        ok = pt["t"] >= -pt["crit"]
        beat = pt["t"] > pt["crit"]
    else:                                   # smoke(시드 1개·차이 없음): 평균 차의 부호로만 본다
        ok, beat = (pt["mean"] >= 0.0), False
    out["perf"] = dict(t=pt["t"], crit=pt["crit"], mean=pt["mean"], pass_=bool(ok), beats_fsm=bool(beat))
    us = {}
    for u in active_u(allowed):
        v = rl["u"][u]
        us[u] = dict(value=v, min=U_MIN[u], pass_=bool(v is not None and v >= U_MIN[u]))
    out["u"] = dict(items=us, pass_=all(x["pass_"] for x in us.values()))
    use = {b: dict(value=rl["use"][b], pass_=bool(rl["use"][b] is not None and rl["use"][b] >= USE_MIN))
           for b in allowed}
    fl = rl["flicker"]
    out["use"] = dict(items=use, flicker=fl, flicker_pass=bool(fl is None or fl <= FLICKER_MAX),
                      pass_=all(x["pass_"] for x in use.values()) and bool(fl is None or fl <= FLICKER_MAX))
    dep = {}
    if "sleep" in allowed:
        dv = res["c4_drop"].get("c4_phase", {}).get("sleep")
        dep["sleep_phase"] = dict(value=dv, min=C4_DROP_MIN, pass_=bool(dv is not None and dv >= C4_DROP_MIN))
    if "freeze" in allowed and variant == "near":
        dv = res["c4_drop"].get("c4_app", {}).get("freeze")
        dep["freeze_app"] = dict(value=dv, min=C4_DROP_MIN, pass_=bool(dv is not None and dv >= C4_DROP_MIN))
    out["dep"] = dict(items=dep, pass_=all(x["pass_"] for x in dep.values()))
    lim = STARVE_RATIO_MAX * fsm["starve_rate"]
    out["starve"] = dict(rl=rl["starve_rate"], fsm=fsm["starve_rate"], limit=lim,
                         ratio=rl["starve_rate"] / fsm["starve_rate"] if fsm["starve_rate"] > 0 else None,
                         pass_=bool(rl["starve_rate"] <= lim))
    out["pass_"] = all(out[k]["pass_"] for k in ("perf", "u", "use", "dep", "starve"))
    return out


def config_digest(cfg) -> str:
    """diagnose_v2.config_digest 와 같은 식(설정 dict 의 sha1 앞 12자리)."""
    return hashlib.sha1(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]


def judge(model: str, name: str, seeds, steps: int, out: Path, config: str = CONFIG, variant: str = "near",
          workers: int = 1, policies=None, tail: int = TAIL, gamma: float = GAMMA) -> dict:
    """모델 하나를 판정해 `<out>/<name>.json`·`<name>.md` 를 쓴다. 반환은 JSON 과 같은 dict."""
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import rep_params

    cfg = load_v2_config(HERE / config)
    rep = rep_params(cfg)
    if rep is None:
        raise ValueError(f"{config} 에 train.repertoire 블록(목록)이 없다")
    allowed = rep["allowed"]
    if variant not in FREEZE_VARIANTS:
        raise ValueError(f"--freeze-variant 는 {FREEZE_VARIANTS} 중 하나다")
    names = list(policies) if policies else (["rl", "fsm"] + [f"c_{b}" for b in allowed] + ["c1p", "c4_app", "c4_phase"])
    for must in ("rl", "fsm"):
        if must not in names:
            raise ValueError(f"판정에는 정책 {must} 가 꼭 있어야 한다")
    seeds = [int(s) for s in seeds]
    t0 = time.time()
    phase1 = [p for p in names if p != "c1p"]
    jobs = [(p, policy_spec(p, model, cfg, allowed, variant), s, steps, config, gamma, tail, variant)
            for p in phase1 for s in seeds]
    rows: dict[str, list[dict]] = {}
    for r in _map(jobs, workers):
        rows.setdefault(r["name"], []).append(r)
    pooled_ = {p: pooled(rows[p], allowed) for p in rows}
    if "c1p" in names:
        freq = pooled_["rl"]["choice_freq"]
        jobs = [("c1p", policy_spec("c1p", model, cfg, allowed, variant, freq), s, steps, config, gamma, tail, variant)
                for s in seeds]
        rows["c1p"] = _map(jobs, workers)
        pooled_["c1p"] = pooled(rows["c1p"], allowed)
    for p in rows:
        rows[p].sort(key=lambda r: r["seed"])
    g = lambda p: [r["g_gamma"] for r in rows[p]]          # noqa: E731
    res = dict(pooled=pooled_, perf=paired_t(g("rl"), g("fsm")))
    res["c4_drop"] = {c: {u: drop(pooled_["rl"]["u"][u], pooled_[c]["u"][u]) for u in U_NAMES}
                      for c in ("c4_app", "c4_phase") if c in pooled_}
    res["gate"] = gate(res, allowed, variant)
    res["meta"] = dict(name=name, model=str(model), config=config, digest=config_digest(cfg), seeds=seeds,
                       steps=int(steps), gamma=gamma, tail=int(tail), freeze_variant=variant, allowed=list(allowed),
                       policies=[p for p in POLICY_ORDER if p in rows], theta=THETA, approach=APPROACH,
                       elapsed_s=round(time.time() - t0, 1))
    res["per_seed"] = {p: [{k: v for k, v in r.items() if k not in ("entries",)} for r in rows[p]] for p in rows}
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / f"{name}.md").write_text(report_md(res), encoding="utf-8")
    return res


# --------------------------------------------------------------------- #
# 보고서
# --------------------------------------------------------------------- #


def _f(x, fmt=".3f"):
    return format(x, fmt) if isinstance(x, (int, float)) and x is not None and math.isfinite(x) else "—"


def _ok(b) -> str:
    return "통과" if b else "실패"


def report_md(res: dict) -> str:
    m, G, P = res["meta"], res["gate"], res["pooled"]
    small = len(m["seeds"]) < len(EVAL_SEEDS) or m["steps"] < STEPS
    L = [f"# v3 R1 판정 — {m['name']}" + (" (smoke·부분 실행, 판정 아님)" if small else ""), "",
         f"**결론: {'통과' if G['pass_'] else '실패'}** (PREREG 4절 다섯 조건 모두 만족해야 통과)", "",
         f"- 모델 `{m['model']}`, 판정 세계 `{m['config']}`(digest {m['digest']}), 목록 {', '.join(m['allowed'])}, "
         f"FREEZE 판 {m['freeze_variant']}", f"- 평가 시드 {m['seeds'][0]}~{m['seeds'][-1]} ({len(m['seeds'])}개) × "
         f"{m['steps']}스텝, 정책은 모두 argmax·결정적, G_γ γ {m['gamma']} tail {m['tail']}", "",
         "## 판정 (PREREG 4절)", "", "| 조건 | 값 | 문턱 | 결과 |", "|---|---|---|---|"]
    p = G["perf"]
    beat = " — FSM 을 이김" if p["beats_fsm"] else ""
    L.append(f"| 1. 성과: RL − FSM G_γ 짝 t | 평균 차 {_f(p['mean'], '+.4f')}, t {_f(p['t'], '+.2f')} | t ≥ "
             f"−{_f(p['crit'], '.3f')} | {_ok(p['pass_'])}{beat} |")
    for u, v in G["u"]["items"].items():
        L.append(f"| 2. 맞는 때: U_{u.upper()} | {_f(v['value'])} | ≥ {v['min']} | {_ok(v['pass_'])} |")
    for b, v in G["use"]["items"].items():
        L.append(f"| 3. 쓰임: {b} 사용 비중 | {_f(v['value'], '.2%') if v['value'] is not None else '—'} | ≥ 2% | "
                 f"{_ok(v['pass_'])} |")
    L.append(f"| 3. 쓰임: 깜빡임(3초 안 A-B-A) | {_f(G['use']['flicker'], '.2%') if G['use']['flicker'] is not None else '—'}"
             f" | ≤ 10% | {_ok(G['use']['flicker_pass'])} |")
    if G["dep"]["items"]:
        for k, v in G["dep"]["items"].items():
            label = "위상 중립 고정 → U_SLEEP 하락률" if k == "sleep_phase" else "접근 0.5 고정 → U_FREEZE 하락률"
            L.append(f"| 4. 입력 의존: {label} | {_f(v['value'])} | ≥ {v['min']} | {_ok(v['pass_'])} |")
    else:
        L.append("| 4. 입력 의존 | (해당 행동 없음) | — | 통과 |")
    s = G["starve"]
    L.append(f"| 5. 굶음: 아사율 RL / FSM | {_f(s['rl'], '.5f')} / {_f(s['fsm'], '.5f')} (비 {_f(s['ratio'], '.2f')}) | "
             f"≤ 1.5 × FSM | {_ok(s['pass_'])} |")
    L += ["", "## 정책별 지표", "",
          "사용 비중 = 실행한 행동의 개체-스텝 비율(G 먹기·F 도망·H 숨기·Z 얼기·S 잠). U 는 결정 시점 표본, 평가 시드를 합친 값.", "",
          "| 정책 | G_γ | 피식률 | 아사율 | 사용 G/F/H/Z/S | 깜빡임 | 결정 비율 | U_ESC | U_HIDE | U_FREEZE | U_SLEEP |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name in POLICY_ORDER:
        if name not in P:
            continue
        v = P[name]
        use = "/".join(_f(v["use"][b], ".3f") for b in BEHAVIOR_NAMES)
        L.append(f"| {name} | {_f(v['g_gamma'], '.4f')} | {_f(v['pred_rate'], '.5f')} | {_f(v['starve_rate'], '.5f')} | "
                 f"{use} | {_f(v['flicker'])} | {_f(v['decide_frac'])} | " + " | ".join(_f(v['u'][u]) for u in U_NAMES) + " |")
    if res["c4_drop"]:
        L += ["", "## C4 하락률 (U − U_C4) / U", "", "| 변형 | " + " | ".join(f"U_{u.upper()}" for u in U_NAMES) + " |",
              "|---|---|---|---|---|"]
        for c, d in res["c4_drop"].items():
            L.append(f"| {c} | " + " | ".join(_f(d[u]) for u in U_NAMES) + " |")
        L.append("")
        L.append("판정에 쓰는 것은 SLEEP(위상 중립)과 FREEZE near 판(접근 0.5)뿐이고 나머지는 보고만 한다.")
    r = P["rl"]["risk"]
    L += ["", "## 위험 할당 (보고만)", "",
          f"RL 의 FLEE 진입 때 가장 가까운 보이는 위협 거리 중앙값: 배부름(E > {FULL_E}) {_f(r['median_full'], '.2f')} "
          f"(n {r['n_full']}), 배고픔(E < {HUNGRY_E}) {_f(r['median_hungry'], '.2f')} (n {r['n_hungry']}), "
          f"차(배부름 − 배고픔) {_f(r['diff'], '+.2f')}. 양수면 배고플 때 위협을 더 가까이까지 참는다."]
    return "\n".join(L) + "\n"


def summarize(names, out: Path) -> str:
    """`<out>/<name>.json` 여러 개 → `<out>/judge.md` (모델 시드별 통과표, R1 성공 = 6시드 중 4시드 이상, PREREG 5절)."""
    rows = []
    for n in names:
        res = json.loads((out / f"{n}.json").read_text(encoding="utf-8"))
        rows.append((n, res))
    n_pass = sum(r["gate"]["pass_"] for _, r in rows)
    L = ["# v3 R1 판정 모음", "",
         f"**통과 {n_pass} / {len(rows)}** — R1 성공 규칙은 6시드 중 4시드 이상 통과(PREREG 5절)"
         + (f": {'성공' if n_pass >= 4 else '실패'}" if len(rows) == 6 else " (6시드가 모두 모이면 판정)"), "",
         "| 모델 | 1 성과 (t) | 2 맞는 때 | 3 쓰임 | 4 입력 의존 | 5 굶음 | 통과 | FSM 을 이김 |", "|---|---|---|---|---|---|---|---|"]
    for n, r in rows:
        G = r["gate"]
        L.append(f"| {n} | {_ok(G['perf']['pass_'])} ({_f(G['perf']['t'], '+.2f')}) | {_ok(G['u']['pass_'])} | "
                 f"{_ok(G['use']['pass_'])} | {_ok(G['dep']['pass_'])} | {_ok(G['starve']['pass_'])} | "
                 f"**{_ok(G['pass_'])}** | {'예' if G['perf']['beats_fsm'] else '아니오'} |")
    L += ["", "출시 모델은 통과한 시드 가운데 보정 시드 20000~20019 의 G_γ 평균이 가장 높은 것을 고른다(평가 시드로는 고르지 않는다)."]
    text = "\n".join(L) + "\n"
    (out / "judge.md").write_text(text, encoding="utf-8")
    return text


def prereg_problems(a, seeds) -> list[str]:
    """사전 등록 폴더에 쓰는 실행의 조건 검사. PREREG 조건과 다른 인자 목록(비면 문제 없음)."""
    bad = []
    if list(seeds) != EVAL_SEEDS:
        bad.append("--seeds (PREREG 10000~10019)")
    if a.steps != STEPS:
        bad.append(f"--steps (PREREG {STEPS})")
    if a.config != CONFIG:
        bad.append(f"--config (PREREG {CONFIG})")
    if a.tail != TAIL:
        bad.append(f"--tail (PREREG {TAIL})")
    if a.policies is not None:
        bad.append("--policies (PREREG 는 정책 모두)")
    if a.freeze_variant != "near":
        bad.append("--freeze-variant (R0 에서 통과한 판은 near)")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="v3 R1 판정 (RL·FSM·대조군, PREREG 4절)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="모델 하나 판정")
    r.add_argument("--model", required=True)
    r.add_argument("--name", required=True, help="결과 파일 이름(보통 모델 시드, 예: s0)")
    r.add_argument("--config", default=CONFIG)
    r.add_argument("--seeds", type=int, nargs="+", default=None)
    r.add_argument("--steps", type=int, default=STEPS)
    r.add_argument("--tail", type=int, default=TAIL)
    r.add_argument("--freeze-variant", choices=FREEZE_VARIANTS, default="near",
                   help="FREEZE 가 목록에 있을 때 쓸 판(U_FREEZE 정의·FSM 얼기 규칙·입력 의존 조건). 기본 near")
    r.add_argument("--policies", nargs="+", default=None, choices=POLICY_ORDER)
    r.add_argument("--workers", type=int, default=14)
    r.add_argument("--out", default=str(PREREG_OUT))
    s = sub.add_parser("summarize", help="판정 결과 여러 개를 judge.md 로 모은다")
    s.add_argument("--names", nargs="+", required=True)
    s.add_argument("--out", default=str(PREREG_OUT))
    a = ap.parse_args(argv)
    out = Path(a.out)
    if a.cmd == "summarize":
        print(summarize(a.names, out))
        return 0
    seeds = a.seeds or EVAL_SEEDS
    if out.resolve() == PREREG_OUT.resolve():
        bad = prereg_problems(a, seeds)
        if bad:
            ap.error(f"사전 등록 폴더 {PREREG_OUT} 에는 PREREG 조건만 쓴다(결과를 덮지 않게). 다른 조건: " + ", ".join(bad)
                     + ". smoke·부분 실행·보정 시드는 --out 에 다른 폴더를 준다")
    judge(a.model, a.name, seeds, a.steps, out, a.config, a.freeze_variant, a.workers, a.policies, a.tail)
    print((out / f"{a.name}.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
