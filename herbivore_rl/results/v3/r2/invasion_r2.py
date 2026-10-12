"""v3 R2 장치별 관문 — 손 규칙 소수 침입·무리 확인·역침입 (명세 `Docs/RL_Policy/RL_V3_R2_SPEC.md` 0·4절, 사전 등록 `PREREG.md`).
`results/v3/r0/invasion_r0.py` 의 사본에서 출발했다(통계·판정 규칙은 R0 와 같다).

    # herbivore_rl/ 에서 — 사전 등록 폴더(results/v3/r2/<world>/)는 PREREG 조건(시드 12160~12199 × 3000, 칸 8개, 격자, 설정)만 받는다
    python results/v3/r2/invasion_r2.py search --world w7 --workers 14     # 1) 거주 규칙 문턱 탐색(세계마다 한 번, 캐시)
    python results/v3/r2/invasion_r2.py run --world w7 --workers 14        # 2) 침입 시험(탐색 캐시의 (θ, a)) → invasion.*, gate.json
    python results/v3/r2/invasion_r2.py pop --world w7 --workers 14        # 3) 무리 확인·역침입 → pop.json·pop.md, gate.json 에 H1
    # smoke: 다른 시드·짧은 스텝·칸 일부·문턱 고정. 사전 등록 폴더가 아닌 --out 이 꼭 필요하다
    python results/v3/r2/invasion_r2.py run --world w8 --seeds 31000 31001 --steps 200 --theta 4 --approach 0.9 \
        --cells ps0.3_pl_T600 --out <임시 폴더> --workers 2
    # 2단계 R2 세계(관문 뒤에 configs/v3_r2_on.yaml 을 만든 다음): --passed 에 통과한 장치의 규칙을 준다
    python results/v3/r2/invasion_r2.py run --world wr2 --passed stare look --workers 14     # 회귀(사전 등록 7절, (1) 기준)

세계 (`--world`, 사전 등록 1·7절): w7 = configs/v3_r2_w7_on.yaml(M7 만), w8 = configs/v3_r2_w8_on.yaml(M8 만), wr2 =
configs/v3_r2_on.yaml(v3_r1_on + 통과한 장치, 관문 뒤에 만든다). 칸 8개·덮기·통계·판정은 R0 와 같다(`invasion_r0.py` docstring).
- search: 128마리 모두 R_base(θ, a) 격자 탐색, 세계마다 한 번(`<out>/search.json`, 조건이 다른 캐시는 --force 없이 덮지 않는다).
- run: w7·w8 — 관문 X(w7 stare, w8 look)의 niche·out·cross (판정, 사전 등록 3절) + 보고만 하는 보조 규칙(5절: w7 stare_still·
  stare_far·stare_chase, w8 look_hide·look_flee — `--no-aux` 로 뺀다). 슬롯 0~15 만 X 를 덮는다(침입 16 − 거주 112).
  wr2 — 회귀(7절): 통과한 니치(--passed 의 stare·look) + R0 HIDE 니치 + R0 '가까운 위협 앞 얼기'(freeze cross)를 (1) 기준
  (5칸 이상 양수 & 유의 음수 0)으로 잰다.
- pop (4·7절): 무리 전체 — 같은 칸·시드에서 128마리 모두 'R_base + X 니치' 대 모두 R_base(칸별 시드 짝 t, 8칸 평균, 유의 양수·
  음수 칸 수), 역침입 — 슬롯 0~15 는 R_base, 나머지 112마리는 R_base + X('R_base − (R_base + X)' 의 짝 t). 함께 적는 것:
  위협 유형별 피식률·아사율, 보이는 지표(stare_stats·alarm_stats 를 1000 개체-스텝당), 장치를 끈 세계(v3_r1_on)의 모두 R_base
  대비 차(w7: 표적 잠금이 R_base 에게 주는 효과, w8: E7 이 R_base 에게 주는 효과 — 사전 등록 2·5절). wr2 는 모두 R_base·
  모두 R_base + 통과 규칙·모두 FSM_R2·모두 늘 먹기와 통과 규칙의 역침입이다(7절).
- H1 '조건부 통과'(사전 등록 4절, 사람 확인 10-12): gate.json 의 (1)·(2) 통과 & (3) 실패 또는 판정 불능이고, 무리 확인의 유의
  음수 칸 0 & 8칸 평균 > 0 이고, 역침입에서 R_base 가 유의하게 이기는(t > 2.023) 칸 0 이면 조건부 통과. pop 이 gate.json 에 적는다.
사전 등록 폴더(`results/v3/r2/<world>/`, --out 기본값)에 쓰는 실행은 PREREG 조건(시드 12160~12199, 3000스텝, 칸 8개 모두, 격자,
세계의 설정, run 은 관문 모드 셋 모두와 보조 규칙 — --no-aux 를 받지 않는다, --passed 는 wr2 만)만 받고, --theta/--approach 를
주면 탐색 캐시의 값과 같아야 하며, run·pop 은 탐색 캐시의 설정 digest 가 지금 설정과 같아야 한다(설정을 바꾼 뒤 옛 탐색 값으로
판정하지 않게). 결과는 한 번 쓴다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

SEEDS = list(range(12160, 12200))     # 판정 시드(사람 확인 H2 10-12)
STEPS = 3000
FOCAL = list(range(16))
T_CRIT = 2.023                        # 짝 t, 자유도 39 (양측 5%)
T_POWER80 = 0.851
GRID_THETA = (4.0, 6.0, 8.0, 10.0, 12.0)
GRID_APPROACH = (0.6, 0.75, 0.9)
WORLDS = {
    "w7": dict(config="configs/v3_r2_w7_on.yaml", gate="stare", aux=("stare_still", "stare_far", "stare_chase")),
    "w8": dict(config="configs/v3_r2_w8_on.yaml", gate="look", aux=("look_hide", "look_flee")),
    "wr2": dict(config="configs/v3_r2_on.yaml", gate=None, aux=()),
}
OFF_CONFIG = "configs/v3_r1_on.yaml"  # 장치를 끈 바탕 세계(무리 확인의 '장치 켬 − 끔')
CELLS = {f"ps{p}_{'pl' if pl else 'np'}_T{T}": (p, pl, T)
         for p in (0.3, 0.7) for pl in (True, False) for T in (600, 1800)}
MODES = ("niche", "out", "cross")
GATE_MIN_CELLS = 5
EVENT_K = 60
LOW_USE = 0.05
PREREG_DIR = HERE.parent
CATCH_COLS = ("catch_rate_chaser", "catch_rate_ranged", "catch_rate_stalker", "catch_rate_player")
NICHE_NEAR_STARE = 4.0                # G7 니치의 아래 거리(repertoire_rules.NICHES['stare']['near']) — θ 가 이보다 크면 report 에 적는다


def cell_cfg(cell: str, config: str):
    """칸의 설정: 세계 설정 + obs_extra + 칸 덮기(p_stalk 고정, 플레이어 있음·없음, 하루 길이 하나). R0 와 같다."""
    from env_v2.config import load_v2_config

    import repertoire_rules as rr

    p, player, T = CELLS[cell]
    cfg = rr.with_obs_extra(load_v2_config(ROOT / config))
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    f["threats"] = dict(f["threats"], stalk_frac=[p, p], player_frac=1.0 if player else 0.0)
    f["daynight"] = dict(f["daynight"], periods=[T])
    return cfg.replace(v2=dict(cfg.v2, features=f))


def config_digest(cfg) -> str:
    """diagnose_v2.config_digest 와 같은 식(torch 를 싣지 않으려고 여기 다시 적는다)."""
    return hashlib.sha1(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]


def _spec(cfg, theta: float, approach: float, variant: tuple) -> tuple[dict, list | None]:
    """변형 → (정책 스펙, 사건 조건 규칙 래퍼(침입만, 아니면 None)).
    ("base",) 모두 R_base · ("inv", x, mode) 슬롯 0~15 만 X · ("pop", xs) 모두 R_base + xs 니치 · ("rev", xs) 슬롯 16~ 만 xs 니치 ·
    ("fsm", xs) 모두 FSM_R2(xs 의 줄만) · ("graze",) 모두 늘 먹기."""
    import repertoire_rules as rr

    kind = variant[0]
    if kind == "graze":
        return {"kind": "fixed", "action": [0.0]}, None
    if kind == "fsm":
        xs = variant[1]
        return rr.fsm_r2_spec(cfg, stare="stare" in xs, look="look" in xs), None
    spec = rr.rule_spec(cfg, theta, approach)
    if kind == "inv":
        w = rr.x_wrap(cfg, variant[1], variant[2], FOCAL)
        spec["wrap"].append(w)
        return spec, dict(w, slots=None)
    if kind in ("pop", "rev"):
        slots = None if kind == "pop" else list(range(len(FOCAL), int(cfg.N)))
        for x in variant[1]:
            spec["wrap"].append(rr.x_wrap(cfg, x, "niche", slots))
    return spec, None


def _job(args):
    """롤아웃 하나. 반환: 슬롯 0~15(focal) − 나머지 차, 128마리 평균, X 사용, 사건 조건 지표(침입), 깜빡임, 위협 유형별 포획률,
    보이는 지표(stare_stats·alarm_stats)."""
    from env_v2 import rollout as ro
    from env_v2.world import World

    import repertoire_rules as rr

    cell, theta, approach, variant, seed, steps, config = args
    cfg = cell_cfg(cell, config)
    spec, cond_w = _spec(cfg, theta, approach, variant)
    pol = ro.build_policy(spec, seed)

    class W(World):
        def _accumulate(self, a, rew, repro, caught, starved, done):
            self.last = (caught.copy(), starved.copy())
            super()._accumulate(a, rew, repro, caught, starved, done)

    w = W(cfg, seeds=[seed])
    N = w.N
    foc = np.zeros(N, dtype=bool)
    foc[FOCAL] = True
    rew_s, pred_s, starve_s, use_s = np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N)
    x = variant[1] if variant[0] == "inv" else None
    xid = rr.BEHAVIOR_IDS[x] if x is not None else -1
    if cond_w is not None:
        base_rule = rr.BaseRule(None, spec["wrap"][0])
        cond_rule = rr.XRule(None, cond_w)
        cond_prev = np.zeros(N, dtype=bool)
        win = np.full(N, -1, dtype=np.int64)
        win_rew = np.zeros(N)
        ev = np.zeros((2, 4))
    for t in range(steps):
        obs = w.observe()
        if cond_w is not None:
            cond = cond_rule.mask(obs, base_rule.decide(obs))
            onset = cond & ~cond_prev & (win < 0) & (t <= steps - EVENT_K)
            win[onset] = EVENT_K
            win_rew[onset] = 0.0
            cond_prev = cond
        _, rew, done, _ = w.step(pol(obs))
        if hasattr(pol, "observe_done"):
            pol.observe_done(done)
        c, s = w.last
        rew_s += rew
        pred_s += c
        starve_s += s
        if x is not None:
            use_s += w.behavior == xid
        if cond_w is not None:
            op = win > 0
            win_rew[op] += rew[op]
            win[op] -= 1
            closed = op & (done | (win == 0))
            for k, gm in enumerate((foc, ~foc)):
                cm = closed & gm
                ev[k] += (np.count_nonzero(cm), win_rew[cm].sum(), np.count_nonzero(cm & c), np.count_nonzero(cm & s))
            win[closed] = -1
            cond_prev = cond_prev & ~done
    sums = (("rew", rew_s), ("pred", pred_s), ("starve", starve_s))
    out = {k: float(v[foc].mean() / steps - v[~foc].mean() / steps) for k, v in sums}
    out.update({k + "_all": float(v.mean() / steps) for k, v in sums})
    sc = w.rep_slot_counts()
    out.update(sw_f=int(sc["switch"][foc].sum()), sw_r=int(sc["switch"][~foc].sum()),
               fl_f=int(sc["flicker"][foc].sum()), fl_r=int(sc["flicker"][~foc].sum()))
    if x is not None:
        out["use_focal"] = float(use_s[foc].mean() / steps)
        out["use_res"] = float(use_s[~foc].mean() / steps)
        nan = float("nan")
        for k, sfx in ((0, "f"), (1, "r")):
            n = ev[k, 0]
            out[f"ev_n_{sfx}"] = int(n)
            out[f"ev_rew_{sfx}"] = float(ev[k, 1] / n) if n else nan
            out[f"ev_pred_{sfx}"] = float(ev[k, 2] / n) if n else nan
            out[f"ev_starve_{sfx}"] = float(ev[k, 3] / n) if n else nan
    ts = w.threats_stats()
    out.update({k: float(ts[k]) for k in CATCH_COLS})
    rs = w.repertoire_stats()
    out["use_graze_all"] = float(rs["use_graze"])
    if w._sd is not None:
        out["stare"] = {k: (None if isinstance(v, float) and v != v else v) for k, v in w.stare_stats().items()}
    if w._al is not None:
        out["alarm"] = {k: (None if isinstance(v, float) and v != v else v) for k, v in w.alarm_stats().items()}
    return cell, theta, approach, variant, seed, out


def paired(d) -> dict:
    """시드별 차 → 평균·짝 t·MDE80. nan 은 뺀다. 표준편차 0 이거나 2개 미만이면 t None (R0 와 같다)."""
    d = np.asarray(d, dtype=np.float64)
    d = d[np.isfinite(d)]
    n = len(d)
    if n == 0:
        return dict(mean=float("nan"), t=None, n=0, mde80=None)
    sd = float(d.std(ddof=1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else 0.0
    return dict(mean=float(d.mean()), t=float(d.mean() / se) if se > 0 else None, n=n,
                mde80=float((T_CRIT + T_POWER80) * se) if se > 0 else None)


def _map(jobs, workers):
    if workers <= 1:
        return [_job(j) for j in jobs]
    from env.rollout import _init_worker

    with ProcessPoolExecutor(min(workers, len(jobs)), initializer=_init_worker) as ex:
        return list(ex.map(_job, jobs, chunksize=1))


class StaleCache(RuntimeError):
    """조건이 다른 탐색 캐시가 이미 있다(--force 없이 덮지 않는다)."""


def search_meta(seeds, steps, config, grid_theta=GRID_THETA, grid_approach=GRID_APPROACH, cells=None) -> dict:
    cells = list(cells or CELLS)
    return dict(config=config, digest={c: config_digest(cell_cfg(c, config)) for c in cells}, seeds=list(seeds),
                steps=int(steps), grid_theta=list(grid_theta), grid_approach=list(grid_approach), cells=cells)


def search(seeds, steps, workers, out: Path, config: str, grid_theta=GRID_THETA, grid_approach=GRID_APPROACH,
           cells=None, force=False) -> dict:
    """거주 규칙 문턱 탐색 (사전 등록 2절, R0 와 같은 규칙). 세계마다 한 번 하고 고정한다."""
    cells = list(cells or CELLS)
    meta = search_meta(seeds, steps, config, grid_theta, grid_approach, cells)
    path = out / "search.json"
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("meta") == meta and not force:
            return old
        if old.get("meta") != meta and not force:
            diff = sorted(k for k in meta if old.get("meta", {}).get(k) != meta[k])
            raise StaleCache(f"{path} 에 조건이 다른 탐색 캐시가 있다(다른 항목: {diff}). 사전 등록 탐색은 한 번 하고 고정한다 — "
                             "고정한 값으로 시험하려면 --theta/--approach 를 주고, 정말 다시 재려면 --force, 아니면 --out 에 "
                             "다른 폴더를 준다")
    jobs = [(c, th, a, ("base",), s, steps, config) for th in grid_theta for a in grid_approach for c in cells
            for s in seeds]
    per = {}
    for c, th, a, _, s, o in _map(jobs, workers):
        per.setdefault(f"{th:g}|{a:g}", {}).setdefault(c, {})[str(s)] = {k: o[k] for k in ("rew_all", "pred_all",
                                                                                           "starve_all", "rew")}
    table = {}
    for key, by_cell in per.items():
        def m(k):
            return float(np.mean([[by_cell[c][str(s)][k] for c in cells] for s in seeds]))
        table[key] = dict(rew=m("rew_all"), pred=m("pred_all"), starve=m("starve_all"))
    order = sorted(table, key=lambda k: (-table[k]["rew"], float(k.split("|")[0]), -float(k.split("|")[1])))
    th, a = (float(x) for x in order[0].split("|"))
    res = dict(meta=meta, best=dict(theta=th, approach=a), table=table, per_seed=per)
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def _sig_neg(v, key="rew"):
    return v[key]["t"] is not None and v[key]["t"] < -T_CRIT


def gate(summary: dict, cells, x: str, key: str = "rew") -> dict:
    """관문 X 의 판정 (사전 등록 3절, R0 와 같다). summary[f"{x}|{mode}|{cell}"][key] = paired(...)."""
    def col(mode):
        return [summary.get(f"{x}|{mode}|{c}") for c in cells]
    nich, outs, cross = col("niche"), col("out"), col("cross")
    if any(v is None for v in nich + outs + cross):
        return dict(complete=False)
    n_pos = sum(v[key]["mean"] > 0 for v in nich)
    n_neg1 = sum(_sig_neg(v, key) for v in nich)
    n_neg2 = sum(_sig_neg(v, key) for v in outs)
    n_neg3 = sum(_sig_neg(v, key) for v in cross)
    c1 = n_pos >= GATE_MIN_CELLS and n_neg1 == 0
    c2 = n_neg2 >= GATE_MIN_CELLS
    c3 = n_neg3 >= GATE_MIN_CELLS
    cross_use = float(np.mean([v["use_focal"] for v in cross]))
    low = bool(c1 and c2 and not c3 and cross_use < LOW_USE)
    verdict = "pass" if (c1 and c2 and c3) else ("low_power" if low else "fail")
    return dict(complete=True, niche_pos=int(n_pos), niche_sig_neg=int(n_neg1), out_sig_neg=int(n_neg2),
                cross_sig_neg=int(n_neg3), c1=bool(c1), c2=bool(c2), c3=bool(c3), pass_=bool(c1 and c2 and c3),
                cross_use_focal=cross_use, verdict=verdict)


def regress(summary: dict, cells, x: str, mode: str, key: str = "rew") -> dict:
    """wr2 회귀 (사전 등록 7절): (1) 기준 — 5칸 이상 양수 & 유의 음수 0."""
    vs = [summary.get(f"{x}|{mode}|{c}") for c in cells]
    if any(v is None for v in vs):
        return dict(complete=False)
    n_pos = sum(v[key]["mean"] > 0 for v in vs)
    n_neg = sum(_sig_neg(v, key) for v in vs)
    return dict(complete=True, pos=int(n_pos), sig_neg=int(n_neg), ok=bool(n_pos >= GATE_MIN_CELLS and n_neg == 0))


def _summarize(per: dict, base: dict, ss: list, steps: int, n_agents: int, per_sec: float) -> dict:
    summary = {}
    for key, by_seed in per.items():
        c = key.split("|")[2]
        v = summary[key] = {k: paired([by_seed[s][k] for s in ss]) for k in ("rew", "pred", "starve")}
        v["rew_did"] = paired([by_seed[s]["rew"] - base[c][s]["rew"] for s in ss])
        v["use_focal"] = float(np.mean([by_seed[s]["use_focal"] for s in ss]))
        v["use_res"] = float(np.mean([by_seed[s]["use_res"] for s in ss]))
        v["rew_per_use"] = v["rew"]["mean"] / v["use_focal"] if v["use_focal"] > 0 else float("nan")
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


def run(world: str, seeds, steps, workers, out: Path, theta: float, approach: float, config: str | None = None,
        cells=None, aux=True, passed=()) -> dict:
    """침입 시험(w7·w8: 관문 X 셋 + 보조 규칙) 또는 회귀(wr2: 통과 니치 + R0 HIDE·가까운 얼기)."""
    from env_v2.config import load_v2_config

    wd = WORLDS[world]
    config = config or wd["config"]
    cells = list(cells or CELLS)
    cfg0 = load_v2_config(ROOT / config)
    per_sec, n_agents = 60.0 / float(cfg0.policy_interval), int(cfg0.N)
    if world == "wr2":
        variants = [(x, "niche") for x in passed] + [("hide", "niche"), ("freeze", "cross")]
    else:
        variants = [(wd["gate"], m) for m in MODES] + ([(x, "niche") for x in wd["aux"]] if aux else [])
    jobs = [(c, theta, approach, ("inv", x, m), s, steps, config) for x, m in variants for c in cells for s in seeds]
    jobs += [(c, theta, approach, ("base",), s, steps, config) for c in cells for s in seeds]
    t0 = time.time()
    per, base = {}, {}
    for c, _, _, var, s, o in _map(jobs, workers):
        if var[0] == "base":
            base.setdefault(c, {})[str(s)] = o
        else:
            per.setdefault(f"{var[1]}|{var[2]}|{c}", {})[str(s)] = o
    ss = [str(s) for s in seeds]
    summary = _summarize(per, base, ss, steps, n_agents, per_sec)
    if world == "wr2":
        g = {f"{x}|{m}": regress(summary, cells, x, m) for x, m in variants}
        g_did = {f"{x}|{m}": regress(summary, cells, x, m, key="rew_did") for x, m in variants}
    else:
        g = {wd["gate"]: gate(summary, cells, wd["gate"])}
        g_did = {wd["gate"]: gate(summary, cells, wd["gate"], key="rew_did")}
        if wd["gate"] == "look" and aux:      # 보고만: 같은 니치에서 FREEZE 실행 차 − FLEE 실행 차의 짝 대비(5절)
            for c in cells:
                a, b = per.get(f"look|niche|{c}"), per.get(f"look_flee|niche|{c}")
                if a and b:
                    summary[f"look_minus_flee|niche|{c}"] = dict(contrast=paired([a[s]["rew"] - b[s]["rew"] for s in ss]))
    meta = dict(world=world, config=config, seeds=list(seeds), steps=int(steps), theta=theta, approach=approach,
                cells=cells, variants=[list(v) for v in variants], t_crit=T_CRIT, event_k=EVENT_K, low_use=LOW_USE,
                elapsed_s=round(time.time() - t0, 1), digest={c: config_digest(cell_cfg(c, config)) for c in cells})
    res = dict(meta=meta, gate=g, gate_did=g_did, summary=summary, per_seed=dict(per, base=base))
    out.mkdir(parents=True, exist_ok=True)
    (out / "invasion.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (out / "gate.json").write_text(json.dumps(dict(meta=meta, gate=g, gate_did_report_only=g_did), indent=1),
                                   encoding="utf-8")
    (out / "invasion.md").write_text(report_md(res), encoding="utf-8")
    return res


def h1_verdict(gx: dict, popx: dict) -> dict:
    """H1 '조건부 통과' (사전 등록 4절, 사람 확인 10-12). gx = gate(...) 한 행, popx = pop 요약의 그 X 행."""
    if not gx.get("complete") or popx is None:
        return dict(complete=False)
    cond = bool(gx["c1"] and gx["c2"] and gx["verdict"] in ("fail", "low_power") and popx["sig_neg"] == 0
                and popx["mean8"] > 0 and popx["rev_rbase_wins"] == 0)
    verdict = "pass" if gx["verdict"] == "pass" else ("conditional_pass" if cond else gx["verdict"])
    return dict(complete=True, gate_verdict=gx["verdict"], pop_sig_neg=popx["sig_neg"], pop_mean8=popx["mean8"],
                rev_rbase_wins=popx["rev_rbase_wins"], conditional=cond, verdict=verdict)


def pop(world: str, seeds, steps, workers, out: Path, theta: float, approach: float, config: str | None = None,
        cells=None, passed=()) -> dict:
    """무리 확인·역침입 (사전 등록 4·7절, 모듈 docstring). 판정이 아니다(H1 근거로 보고한다)."""
    wd = WORLDS[world]
    config = config or wd["config"]
    cells = list(cells or CELLS)
    xs = tuple(passed) if world == "wr2" else (wd["gate"],)
    variants = {"base": ("base",), "pop": ("pop", xs), "rev": ("rev", xs)}
    if world == "wr2":
        variants.update(fsm=("fsm", xs), graze=("graze",))
    jobs, names = [], []
    for name, v in variants.items():
        for c in cells:
            for s in seeds:
                jobs.append((c, theta, approach, v, s, steps, config))
                names.append(name)
    for c in cells:                 # 장치를 끈 세계의 모두 R_base (장치 켬 − 끔, 사전 등록 2·5절)
        for s in seeds:
            jobs.append((c, theta, approach, ("base",), s, steps, OFF_CONFIG))
            names.append("base_off")
    t0 = time.time()
    raw = {}
    for name, (c, _, _, _, s, o) in zip(names, _map(jobs, workers)):
        raw.setdefault(name, {}).setdefault(c, {})[str(s)] = o
    ss = [str(s) for s in seeds]
    summ = {}
    for name in raw:
        if name == "base":
            continue
        rows = {}
        for c in cells:
            if name == "rev":       # 역침입: 슬롯 0~15(R_base) − 나머지(R_base + X)
                v = paired([raw[name][c][s]["rew"] for s in ss])
            elif name == "base_off":    # 장치 켬 − 끔: 모두 R_base 의 이 세계 − 장치를 끈 세계(v3_r1_on)
                v = paired([raw["base"][c][s]["rew_all"] - raw[name][c][s]["rew_all"] for s in ss])
            else:                   # 무리: 128마리 개체-스텝당 보상, 그 변형 − 모두 R_base
                v = paired([raw[name][c][s]["rew_all"] - raw["base"][c][s]["rew_all"] for s in ss])
            v["pred_all"] = float(np.mean([raw[name][c][s]["pred_all"] for s in ss]))
            v["starve_all"] = float(np.mean([raw[name][c][s]["starve_all"] for s in ss]))
            for k in CATCH_COLS:
                v[k] = float(np.mean([raw[name][c][s][k] for s in ss]))
            rows[c] = v
        ts = [rows[c]["t"] for c in cells]
        summ[name] = dict(cells=rows, mean8=float(np.mean([rows[c]["mean"] for c in cells])),
                          sig_pos=int(sum(t is not None and t > T_CRIT for t in ts)),
                          sig_neg=int(sum(t is not None and t < -T_CRIT for t in ts)))
    summ["rev"]["rbase_wins"] = summ["rev"]["sig_pos"]
    base_rows = {c: dict(rew_all=float(np.mean([raw["base"][c][s]["rew_all"] for s in ss])),
                         pred_all=float(np.mean([raw["base"][c][s]["pred_all"] for s in ss])),
                         starve_all=float(np.mean([raw["base"][c][s]["starve_all"] for s in ss])),
                         **{k: float(np.mean([raw["base"][c][s][k] for s in ss])) for k in CATCH_COLS}) for c in cells}
    visible = {}
    for name in raw:
        for key in ("stare", "alarm"):
            vals = [raw[name][c][s].get(key) for c in cells for s in ss]
            vals = [v for v in vals if v]
            if vals:
                agg = {}
                for k in vals[0]:
                    xs_ = [v[k] for v in vals if v[k] is not None]
                    agg[k] = float(np.mean(xs_)) if xs_ else None
                n_as = int(steps) * 128
                for k in [k for k in agg if k.endswith("_n") or k.startswith("emit_") or k == "cry_n"]:
                    if agg[k] is not None:
                        agg[k + "_per1000"] = agg[k] / n_as * 1000.0
                visible.setdefault(name, {})[key] = agg
    popx = dict(sig_neg=summ["pop"]["sig_neg"], mean8=summ["pop"]["mean8"], rev_rbase_wins=summ["rev"]["rbase_wins"])
    meta = dict(world=world, config=config, off_config=OFF_CONFIG, seeds=list(seeds), steps=int(steps), theta=theta,
                approach=approach, cells=cells, xs=list(xs), t_crit=T_CRIT, elapsed_s=round(time.time() - t0, 1),
                digest={c: config_digest(cell_cfg(c, config)) for c in cells})
    res = dict(meta=meta, summary=summ, base=base_rows, visible=visible, h1_input=popx)
    gpath = out / "gate.json"
    if world != "wr2" and gpath.exists():
        gj = json.loads(gpath.read_text(encoding="utf-8"))
        gm = gj.get("meta", {})
        same = all(gm.get(k) == meta[k] for k in ("config", "seeds", "steps", "theta", "approach", "cells"))
        if same:
            res["h1"] = h1_verdict(gj["gate"][wd["gate"]], popx)
            gj["h1"] = res["h1"]
            gj["pop_meta"] = meta
            gpath.write_text(json.dumps(gj, indent=1), encoding="utf-8")
        else:
            res["h1"] = dict(complete=False, reason="gate.json 의 조건(설정·시드·스텝·문턱·칸)이 이 무리 확인과 다르다")
    out.mkdir(parents=True, exist_ok=True)
    res["per_seed"] = raw
    (out / "pop.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (out / "pop.md").write_text(pop_md(res), encoding="utf-8")
    return res


_VERDICT = {"pass": "통과", "fail": "실패", "low_power": "판정 불능(검정력 부족)", "conditional_pass": "조건부 통과"}


def _f(x, nd=5):
    if x["n"] == 0 or not math.isfinite(x["mean"]):
        return "—"
    return f"{x['mean']:+.{nd}f} ({x['t']:+.2f})" if x["t"] is not None else f"{x['mean']:+.{nd}f}"


def _num(x, fmt):
    return format(x, fmt) if x is not None and isinstance(x, (int, float)) and math.isfinite(x) else "—"


def report_md(res: dict) -> str:
    m, g, s = res["meta"], res["gate"], res["summary"]
    gd = res.get("gate_did", {})
    small = len(m["seeds"]) < 40 or m["steps"] < 3000
    L = [f"# v3 R2 관문 {m['world']} (손 규칙 소수 침입)" + (" — smoke, 판정 아님" if small else ""), "",
         f"설정 {m['config']} + obs_extra, 시드 {m['seeds'][0]}~{m['seeds'][-1]} ({len(m['seeds'])}개) × {m['steps']}스텝,"
         f" 거주 규칙 R_base(θ {m['theta']:g}, a {m['approach']:g}). 값 = 침입 16 − 거주 112, 개체-스텝당. 짝 t 임계"
         f" {m['t_crit']}.", ""]
    if m["world"] == "wr2":
        L += ["## 회귀 (사전 등록 7절, (1) 기준: 5칸 이상 양수 & 유의 음수 0)", "", "| 규칙 | 양수 칸 | 유의 음수 칸 | 유지 |"
              " 이중차(보고만) |", "|---|---|---|---|---|"]
        for k, v in g.items():
            if not v.get("complete"):
                L.append(f"| {k} | — | — | (칸 부족) | — |")
                continue
            vd = gd.get(k, {})
            L.append(f"| {k} | {v['pos']} | {v['sig_neg']} | {'○' if v['ok'] else '×'} | {'○' if vd.get('ok') else '×'} |")
    else:
        L += ["## 판정 (사전 등록 3절)", "",
              "| X | (1) 니치 양수 칸 / 유의 음수 칸 | (2) 니치 밖 유의 음수 칸 | (3) 교차 유의 음수 칸 | 교차 X 사용(침입) | 판정 |"
              " 이중차 판정(보고만) |", "|---|---|---|---|---|---|---|"]
        for x, v in g.items():
            if not v.get("complete"):
                L.append(f"| {x} | — | — | — | — | (칸 부족) | — |")
                continue
            vd = gd.get(x, {})
            L.append(f"| {x} | {v['niche_pos']} / {v['niche_sig_neg']} {'○' if v['c1'] else '×'} | "
                     f"{v['out_sig_neg']} {'○' if v['c2'] else '×'} | {v['cross_sig_neg']} {'○' if v['c3'] else '×'} | "
                     f"{v['cross_use_focal']:.3f} | {_VERDICT[v['verdict']]} | {_VERDICT.get(vd.get('verdict'), '—')} |")
        L += ["", "H1 '조건부 통과'는 `pop` 이 무리 확인·역침입을 잰 뒤 gate.json 에 적는다(사전 등록 4절)."]
        if m["world"] == "w7" and m["theta"] > NICHE_NEAR_STARE:
            L += ["", f"주의: 거주 θ {m['theta']:g} > {NICHE_NEAR_STARE:g} 라 G7 니치(4 < 거리 ≤ 10)·교차(거리 ≥ 8)의 일부 스텝에서 "
                  "바탕 요청이 FLEE 다. 규칙은 바탕과 무관하게 조건만 본다(사전 등록 변경 기록 10-12 (2)) — 그 스텝의 X 는 'FLEE "
                  "대신 FREEZE'라서 니치 가설을 'GRAZE 대신 노려보기'로만 읽지 않는다."]
    L += ["", "## 칸별 값", "",
          "이중차(보고만) = 침입 차 − 같은 시드·칸에서 X 없이 돌린 슬롯 0~15 − 나머지 차. 사건 조건 = X 규칙의 조건에 들어선 순간부터"
          f" {m['event_k']}스텝 창, 침입 − 거주(창 수 침입·거주). 보조 규칙(stare_*·look_*)은 보고만이다.", "",
          "| X | 모드 | 칸 | 보상 (t) | MDE80 | 희석 보정 | 보상 이중차 (t) | 피식 (t) | 아사 (t) | X 사용 침입·거주 |"
          " 사건 조건 보상 (t) | 사건 조건 피식 (t) | 창 수 | 깜빡임 침입·거주 | 초당 전환 침입·거주 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(s):
        x, mode, c = key.split("|")
        v = s[key]
        if "contrast" in v:
            continue
        L.append(f"| {x} | {mode} | {c} | {_f(v['rew'])} | {_num(v['rew']['mde80'], '.5f')} | "
                 f"{_num(v['rew_per_use'], '+.4f')} | {_f(v['rew_did'])} | {_f(v['pred'])} | {_f(v['starve'])} | "
                 f"{v['use_focal']:.3f} · {v['use_res']:.3f} | {_f(v['ev_rew'], 3)} | {_f(v['ev_pred'], 4)} | "
                 f"{v['ev_n_f']} · {v['ev_n_r']} | {_num(v['flicker_f'], '.3f')} · {_num(v['flicker_r'], '.3f')} | "
                 f"{v['switch_per_sec_f']:.3f} · {v['switch_per_sec_r']:.3f} |")
    cons = [(k, v) for k, v in s.items() if "contrast" in v]
    if cons:
        L += ["", "보고만(5절): 같은 니치에서 FREEZE 실행 차 − FLEE 실행 차(look − look_flee)의 짝 대비", "",
              "| 칸 | 대비 (t) |", "|---|---|"] + [f"| {k.split('|')[2]} | {_f(v['contrast'])} |" for k, v in sorted(cons)]
    return "\n".join(L) + "\n"


def pop_md(res: dict) -> str:
    m, s = res["meta"], res["summary"]
    small = len(m["seeds"]) < 40 or m["steps"] < 3000
    L = [f"# v3 R2 무리 확인·역침입 {m['world']}" + (" — smoke, 판정 아님" if small else ""), "",
         f"설정 {m['config']}, 시드 {m['seeds'][0]}~{m['seeds'][-1]} ({len(m['seeds'])}개) × {m['steps']}스텝, R_base(θ "
         f"{m['theta']:g}, a {m['approach']:g}), X = {m['xs']}. 무리 = 128마리 개체-스텝당 보상의 (변형 − 모두 R_base) 시드 짝 t,"
         " 역침입 = 슬롯 0~15(R_base) − 나머지(R_base + X). 보고만 한다(H1 근거).", ""]
    if res.get("h1"):
        h = res["h1"]
        L += ["## H1 (사전 등록 4절)", ""]
        if h.get("complete"):
            L.append(f"- 관문 판정 {_VERDICT[h['gate_verdict']]} → **{_VERDICT[h['verdict']]}** (무리 유의 음수 칸 "
                     f"{h['pop_sig_neg']}, 8칸 평균 {h['pop_mean8']:+.5f}, 역침입에서 R_base 가 유의하게 이긴 칸 "
                     f"{h['rev_rbase_wins']})")
        else:
            L.append(f"- 계산하지 않음: {h.get('reason', 'gate.json 이 없다')}")
        L.append("")
    L += ["변형: pop = 모두 R_base + X − 모두 R_base, rev = 역침입, base_off = 모두 R_base 의 장치 켬 − 끔(v3_r1_on), wr2 의 fsm·graze ="
          " 모두 FSM_R2·모두 늘 먹기 − 모두 R_base.", "",
          "| 변형 | 칸 평균 | 유의 양수 칸 | 유의 음수 칸 | " + " | ".join(m["cells"]) + " |",
          "|---" * (4 + len(m["cells"])) + "|"]
    for name, v in s.items():
        L.append(f"| {name} | {v['mean8']:+.5f} | {v['sig_pos']} | {v['sig_neg']} | "
                 + " | ".join(_f(v["cells"][c]) for c in m["cells"]) + " |")
    L += ["", "위협 유형별 포획률(개체-스텝당, 칸·시드 평균)·아사율:", "",
          "| 변형 | 근접 추격 | 원거리 | 잠행 | 플레이어 | 아사 |", "|---|---|---|---|---|---|"]
    rows = dict(base=res["base"], **{k: v["cells"] for k, v in s.items()})
    for name, cells in rows.items():
        vals = [np.mean([cells[c][k] for c in m["cells"]]) for k in CATCH_COLS + ("starve_all",)]
        L.append(f"| {name} | " + " | ".join(f"{x:.5f}" for x in vals) + " |")
    if res.get("visible"):
        L += ["", "보이는 지표(사전 등록 5절, 칸·시드 평균, *_per1000 = 1000 개체-스텝당):", ""]
        for name, d in res["visible"].items():
            for key, agg in d.items():
                L.append(f"- {name} · {key}: " + ", ".join(f"{k} {_num(v, '.4g')}" for k, v in agg.items()))
    return "\n".join(L) + "\n"


def prereg_problems(a, seeds, world: str) -> list[str]:
    """사전 등록 폴더에 쓰는 실행의 조건 검사(R0 와 같은 꼴 + 설정 digest)."""
    wd = WORLDS[world]
    bad = []
    if list(seeds) != SEEDS:
        bad.append("--seeds (PREREG 12160~12199)")
    if a.steps != STEPS:
        bad.append(f"--steps (PREREG {STEPS})")
    if a.cells is not None and sorted(a.cells) != sorted(CELLS):
        bad.append("--cells (PREREG 칸 8개 모두)")
    if list(a.grid_theta) != list(GRID_THETA) or list(a.grid_approach) != list(GRID_APPROACH):
        bad.append("--grid-theta/--grid-approach (PREREG 격자)")
    if a.config is not None and a.config != wd["config"]:
        bad.append(f"--config (PREREG {wd['config']})")
    if world == "wr2" and a.cmd in ("run", "pop") and not a.passed:
        bad.append("--passed (wr2 는 관문을 통과한 장치의 규칙을 준다)")
    if world != "wr2" and a.cmd == "run" and a.no_aux:
        bad.append("--no-aux (PREREG 5절 보조 규칙은 보고한다)")
    if world != "wr2" and a.passed:
        bad.append("--passed (w7·w8 은 관문 X 하나만 잰다 — --passed 는 wr2 전용)")
    path = Path(a.out) / "search.json"
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if a.theta is not None:
        best = cache["best"] if cache else None
        if best is None or (best["theta"], best["approach"]) != (a.theta, a.approach):
            bad.append(f"--theta/--approach (사전 등록 폴더에서는 탐색 캐시의 값과 같아야 한다: {best})")
    if a.cmd in ("run", "pop") and cache is not None:
        cfgp = a.config or wd["config"]
        if (ROOT / cfgp).exists():
            now = {c: config_digest(cell_cfg(c, cfgp)) for c in CELLS}
            if cache.get("meta", {}).get("digest") != now:
                bad.append("설정 digest (탐색 캐시를 만든 뒤 설정이 바뀌었다 — 옛 탐색 값으로 판정하지 않는다)")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="v3 R2 장치별 관문(손 규칙 소수 침입·무리 확인·역침입)")
    ap.add_argument("cmd", choices=("search", "run", "pop"))
    ap.add_argument("--world", required=True, choices=sorted(WORLDS))
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--out", default=None, help="결과 폴더. 기본값은 사전 등록 폴더 results/v3/r2/<world>/ (PREREG 조건만 받는다)")
    ap.add_argument("--config", default=None, help="세계 설정(기본: 그 세계의 설정)")
    ap.add_argument("--seeds", type=int, nargs="+", default=None)
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--cells", nargs="+", default=None, choices=sorted(CELLS))
    ap.add_argument("--theta", type=float, default=None, help="거주 규칙 θ (주면 탐색을 돌리지 않는다)")
    ap.add_argument("--approach", type=float, default=None, help="거주 규칙 a (--theta 와 함께)")
    ap.add_argument("--grid-theta", type=float, nargs="+", default=list(GRID_THETA))
    ap.add_argument("--grid-approach", type=float, nargs="+", default=list(GRID_APPROACH))
    ap.add_argument("--force", action="store_true", help="조건이 다른 탐색 캐시가 있어도 다시 재서 덮는다")
    ap.add_argument("--no-aux", action="store_true", help="보고만 하는 보조 규칙(사전 등록 5절)을 빼고 잰다")
    ap.add_argument("--passed", nargs="*", default=[], choices=("stare", "look"),
                    help="wr2: 관문을 통과한 장치의 규칙(사전 등록 7절)")
    a = ap.parse_args(argv)
    if (a.theta is None) != (a.approach is None):
        ap.error("--theta 와 --approach 는 함께 준다")
    prereg_out = PREREG_DIR / a.world
    out = Path(a.out) if a.out else prereg_out
    a.out = str(out)
    seeds = a.seeds or SEEDS
    config = a.config or WORLDS[a.world]["config"]
    if not (ROOT / config).exists():
        ap.error(f"설정 {config} 이 없다(wr2 의 configs/v3_r2_on.yaml 은 관문을 통과한 장치로 만든 뒤에 쓴다)")
    if out.resolve() == prereg_out.resolve():
        bad = prereg_problems(a, seeds, a.world)
        if bad:
            ap.error("사전 등록 폴더 " + str(prereg_out) + " 에는 PREREG 조건만 쓴다(결과를 덮지 않게). 다른 조건: "
                     + ", ".join(bad) + ". smoke·부분 실행은 --out 에 다른 폴더를 준다")
    try:
        if a.cmd == "search" or a.theta is None:
            res = search(seeds, a.steps, a.workers, out, config, a.grid_theta, a.grid_approach, a.cells, a.force)
            if a.cmd == "search":
                print(json.dumps(res["best"]), flush=True)
                return 0
            th, ap_ = res["best"]["theta"], res["best"]["approach"]
        else:
            th, ap_ = a.theta, a.approach
    except StaleCache as e:
        ap.error(str(e))
    if a.cmd == "run":
        run(a.world, seeds, a.steps, a.workers, out, th, ap_, config, a.cells, not a.no_aux, tuple(a.passed))
        print((out / "invasion.md").read_text(encoding="utf-8"))
    else:
        pop(a.world, seeds, a.steps, a.workers, out, th, ap_, config, a.cells, tuple(a.passed))
        print((out / "pop.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
