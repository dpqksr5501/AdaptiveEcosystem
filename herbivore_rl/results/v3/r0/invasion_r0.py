"""v3 R0 행동별 통과 시험 — 손 규칙 소수 침입 (명세 `Docs/RL_Policy/RL_V3_R0_SPEC.md` 4절, 사전 등록 `PREREG.md`).

    # herbivore_rl/ 에서
    python results/v3/r0/invasion_r0.py search --workers 14      # 1) 거주 규칙 문턱 탐색(사전 등록 폴더에 한 번, 캐시)
    python results/v3/r0/invasion_r0.py run --workers 14         # 2) 침입 시험(탐색 캐시의 (θ, a))
    # smoke: 시드 2개 · 300스텝 · 문턱 고정(탐색 생략) · 칸·행동 일부. 사전 등록 폴더가 아닌 --out 이 꼭 필요하다
    python results/v3/r0/invasion_r0.py run --seeds 12000 12001 --steps 300 --theta 8 --approach 0.75 \
        --cells ps0.3_pl_T600 --out <임시 폴더> --workers 2
    # 보정 회차(PREREG 4절): 고정한 (θ, a) 를 그대로 주고 회차 폴더·보정 설정에 쓴다
    python results/v3/r0/invasion_r0.py run --theta <θ> --approach <a> --config <보정 설정> --out results/v3/r0/cal1

- 사전 등록 폴더(이 파일의 폴더, --out 기본값)에는 PREREG 조건(시드 12000~12039, 3000스텝, 칸 8개, 격자, 판정 설정, 행동
  셋 모두, FLEE 확인 포함)만 쓴다 — 다른 조건이면 시작 전에 멈춘다(smoke·부분 실행이 사전 등록 결과를 덮지 않게). 그 폴더에서
  --theta/--approach 를 주면 탐색 캐시의 값과 같아야 한다.
- 탐색 캐시 `<out>/search.json` 은 조건(설정 요약·시드·스텝·격자·칸)이 같을 때만 쓴다. 조건이 다른 캐시가 있으면 --force 없이는
  멈춘다(PREREG 2절 '한 번 하고 결과를 고정한다' — 조용히 다시 재서 덮지 않는다).
- 세계: 판정 설정 `configs/v3_r0_on.yaml` 에 관측 obs_extra 만 켠다(손 규칙이 접근 속력을 읽는다. 세계 동역학은 같다).
  칸 8개 = 잠행형 비율 p_stalk {0.3, 0.7}(threats.stalk_frac = [p, p]) × 플레이어 {있음, 없음}(threats.player_frac 1·0) ×
  하루 길이 {600, 1800}(daynight.periods). 탐색 시드 12000~12039 × 3000스텝, 칸마다 같은 시드.
- 거주 규칙: R_base(θ, a)(`repertoire_rules.base_rule`, X 없음, 낮밤 같은 문턱). `search` 가 격자 θ {4, 6, 8, 10, 12} ×
  a {0.6, 0.75, 0.9} 에서 128마리 모두 R_base 일 때의 개체-스텝당 보상을 칸 8개·시드 평균으로 재고 가장 큰 (θ, a)를 고른다
  (같으면 작은 θ, 큰 a).
- 침입: 슬롯 0~15 만 같은 R_base 위에 행동 X 규칙(`repertoire_rules.x_rule`)을 더한다. X ∈ {FREEZE, HIDE, SLEEP} ×
  모드 {niche 니치에서 X, out 니치 밖에서 X, cross 대안의 니치에서 X}. 보고만: x = graze(바탕 규칙이 FLEE 를 고를 때 대신
  먹기 — FLEE 확인).
- 통계: 시드마다 침입 16마리 − 거주 112마리의 개체-스텝당 보상·피식·아사 차, 짝 t(시드 수 − 1 자유도, 40시드 임계 2.023).
  보고만:
  · X 사용 비율(침입·거주), 희석 보정 효과 = 보상 차 / 침입 X 사용 비율(X 를 쓴 개체-스텝당), MDE80 = (2.023 + 0.851)·표준오차
    (짝 t 로 80% 검정력이 나는 최소 차)
  · 보상 이중차 = 침입 차 − 같은 칸·시드를 X 없이 돌린 바탕 실행의 슬롯 0~15 − 나머지 차(슬롯 배치 운을 뺀다)와 그것으로 낸
    판정(강건성 확인)
  · 사건 조건 지표: 개체가 X 규칙의 조건(슬롯 제한 없이 같은 조건)에 들어선 순간부터 EVENT_K 스텝 동안의 보상 합·피식·아사를
    침입(X 를 쓴다)과 거주(바탕 규칙을 쓴다)로 나눠 평균하고 시드별 차의 짝 t 를 낸다(사용률이 낮아 희석된 차를 보완한다).
    창이 열려 있는 동안 새로 들어선 순간은 세지 않고, 끝 EVENT_K 스텝 안에 들어선 순간은 세지 않는다
  · 깜빡임(전환 중 3초 안 A-B-A 되돌림 비율)과 초당 전환 수, 침입·거주별(`World.rep_slot_counts`)
- 판정(PREREG 3절, 행동마다 셋 모두): (1) niche — 칸 8개 중 5칸 이상 보상 차 > 0, t < −2.023 인 칸 0.
  (2) out — 5칸 이상 t < −2.023. (3) cross — 5칸 이상 t < −2.023. (1)·(2)는 통과하고 (3)만 실패했는데 교차 칸의 침입 X 사용
  비율 평균이 LOW_USE 미만이면 '판정 불능(검정력 부족)'으로 적는다(통과는 아니다. R1 포함은 사람이 정한다, PREREG 변경 기록).
결과: `<out>/invasion.json`(요약·시드별 값), `<out>/invasion.md`(판정표 먼저), `<out>/gate.json`.
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

SEEDS = list(range(12000, 12040))
STEPS = 3000
FOCAL = list(range(16))
T_CRIT = 2.023                       # 짝 t, 자유도 39 (양측 5%)
T_POWER80 = 0.851                    # t 자유도 39 의 80% 분위수 (MDE80 = (T_CRIT + T_POWER80)·표준오차, 보고만)
GRID_THETA = (4.0, 6.0, 8.0, 10.0, 12.0)
GRID_APPROACH = (0.6, 0.75, 0.9)
CONFIG = "configs/v3_r0_on.yaml"
CELLS = {f"ps{p}_{'pl' if pl else 'np'}_T{T}": (p, pl, T)
         for p in (0.3, 0.7) for pl in (True, False) for T in (600, 1800)}
BEHAVIORS = ("freeze", "hide", "sleep")
MODES = ("niche", "out", "cross")
GATE_MIN_CELLS = 5                   # 칸 8개 중
EVENT_K = 60                         # 사건 조건 지표의 창(스텝, 8초 — SLEEP 최소 66 의 대부분·HIDE 이동 최대 40 을 덮는다)
LOW_USE = 0.05                       # (3) 실패를 '판정 불능(검정력 부족)'으로 적는 교차 칸 침입 X 사용 비율 문턱(보고 분류)
PREREG_OUT = HERE.parent             # 사전 등록 결과 폴더


def cell_cfg(cell: str, config: str = CONFIG):
    """칸의 설정: 판정 설정 + obs_extra + 칸 덮기(p_stalk 고정, 플레이어 있음·없음, 하루 길이 하나)."""
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


def _job(args):
    """롤아웃 하나. x 가 None 이면 128마리 모두 R_base(탐색·바탕), 아니면 슬롯 0~15 만 X 규칙(침입)."""
    from env_v2 import rollout as ro
    from env_v2.world import World

    import repertoire_rules as rr

    cell, theta, approach, x, mode, seed, steps, config = args
    cfg = cell_cfg(cell, config)
    spec = rr.rule_spec(cfg, theta, approach, x=x, mode=mode, slots=FOCAL if x is not None else None)
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
    xid = rr.BEHAVIOR_IDS[x] if x is not None else -1
    if x is not None:
        # 사건 조건 지표: X 규칙의 조건(슬롯 제한 없이)에 들어선 순간부터 EVENT_K 스텝 창
        base_rule = rr.BaseRule(None, spec["wrap"][0])
        cond_rule = rr.XRule(None, dict(spec["wrap"][1], slots=None))
        cond_prev = np.zeros(N, dtype=bool)
        win = np.full(N, -1, dtype=np.int64)
        win_rew = np.zeros(N)
        ev = np.zeros((2, 4))                       # [침입, 거주] × [창 수, 보상 합, 피식, 아사]
    for t in range(steps):
        obs = w.observe()
        if x is not None:
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
            op = win > 0
            win_rew[op] += rew[op]
            win[op] -= 1
            closed = op & (done | (win == 0))
            for k, gm in enumerate((foc, ~foc)):
                cm = closed & gm
                ev[k] += (np.count_nonzero(cm), win_rew[cm].sum(), np.count_nonzero(cm & c), np.count_nonzero(cm & s))
            win[closed] = -1
            cond_prev = cond_prev & ~done             # 새 개체는 조건 밖에서 시작한다
    sums = (("rew", rew_s), ("pred", pred_s), ("starve", starve_s))
    diff = {k: float(v[foc].mean() / steps - v[~foc].mean() / steps) for k, v in sums}
    sc = w.rep_slot_counts()
    flick = dict(sw_f=int(sc["switch"][foc].sum()), sw_r=int(sc["switch"][~foc].sum()),
                 fl_f=int(sc["flicker"][foc].sum()), fl_r=int(sc["flicker"][~foc].sum()))
    if x is None:
        # 탐색·바탕: 128마리 평균. 같은 세계의 슬롯 0~15 − 나머지 차(배치 운, 이중차 기준)도 함께 낸다
        out = {k: float(v.mean() / steps) for k, v in sums}
        out.update({k + "_fr": v for k, v in diff.items()})
    else:
        out = dict(diff)
        out["use_focal"] = float(use_s[foc].mean() / steps)
        out["use_res"] = float(use_s[~foc].mean() / steps)
        nan = float("nan")
        for k, sfx in ((0, "f"), (1, "r")):
            n = ev[k, 0]
            out[f"ev_n_{sfx}"] = int(n)
            out[f"ev_rew_{sfx}"] = float(ev[k, 1] / n) if n else nan
            out[f"ev_pred_{sfx}"] = float(ev[k, 2] / n) if n else nan
            out[f"ev_starve_{sfx}"] = float(ev[k, 3] / n) if n else nan
    out.update(flick)
    return cell, theta, approach, x, mode, seed, out


def paired(d) -> dict:
    """시드별 차 → 평균·짝 t·MDE80(보고만). nan(그 시드에 표본 없음)은 뺀다. 표준편차 0 이거나 2개 미만이면 t None."""
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
    from env.rollout import _init_worker            # 워커의 BLAS 스레드를 1 로(배열이 작아 스레딩은 손해다)

    with ProcessPoolExecutor(min(workers, len(jobs)), initializer=_init_worker) as ex:
        return list(ex.map(_job, jobs, chunksize=1))


class StaleCache(RuntimeError):
    """조건이 다른 탐색 캐시가 이미 있다(--force 없이 덮지 않는다)."""


def search_meta(seeds, steps, config=CONFIG, grid_theta=GRID_THETA, grid_approach=GRID_APPROACH, cells=None) -> dict:
    cells = list(cells or CELLS)
    return dict(config=config, digest={c: config_digest(cell_cfg(c, config)) for c in cells}, seeds=list(seeds),
                steps=int(steps), grid_theta=list(grid_theta), grid_approach=list(grid_approach), cells=cells)


def search(seeds, steps, workers, out: Path, config: str = CONFIG, grid_theta=GRID_THETA,
           grid_approach=GRID_APPROACH, cells=None, force=False) -> dict:
    """거주 규칙 문턱 탐색 (PREREG 2절). 같은 조건의 캐시가 있으면 다시 돌리지 않는다. 조건이 다른 캐시가 있으면
    `force` 없이는 StaleCache 로 멈춘다(사전 등록 탐색은 한 번 하고 고정한다)."""
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
    jobs = [(c, th, a, None, None, s, steps, config) for th in grid_theta for a in grid_approach for c in cells
            for s in seeds]
    per = {}
    for c, th, a, _, _, s, o in _map(jobs, workers):
        per.setdefault(f"{th:g}|{a:g}", {}).setdefault(c, {})[str(s)] = o
    table = {}
    for key, by_cell in per.items():
        # 시드마다 칸 평균 → 시드 평균
        rew = np.mean([[by_cell[c][str(s)]["rew"] for c in cells] for s in seeds], axis=1)
        table[key] = dict(rew=float(rew.mean()), pred=float(np.mean([[by_cell[c][str(s)]["pred"] for c in cells]
                                                                     for s in seeds])),
                          starve=float(np.mean([[by_cell[c][str(s)]["starve"] for c in cells] for s in seeds])))
    order = sorted(table, key=lambda k: (-table[k]["rew"], float(k.split("|")[0]), -float(k.split("|")[1])))
    th, a = (float(x) for x in order[0].split("|"))
    res = dict(meta=meta, best=dict(theta=th, approach=a), table=table, per_seed=per)
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def gate(summary: dict, cells, key: str = "rew") -> dict:
    """행동별 판정 (PREREG 3절). summary[f"{x}|{mode}|{cell}"][key] = paired(...). key = "rew"(판정) 또는
    "rew_did"(이중차 — 강건성 확인, 보고만). verdict: 통과 / 실패 / 판정 불능(검정력 부족 — (1)·(2) 통과, (3)만 실패,
    교차 칸 침입 X 사용 비율 평균 < LOW_USE)."""
    out = {}
    for x in BEHAVIORS:
        def col(mode):
            return [summary.get(f"{x}|{mode}|{c}") for c in cells]
        nich, outs, cross = col("niche"), col("out"), col("cross")
        if any(v is None for v in nich + outs + cross):
            out[x] = dict(complete=False)
            continue
        sig_neg = lambda v: v[key]["t"] is not None and v[key]["t"] < -T_CRIT     # noqa: E731
        n_pos = sum(v[key]["mean"] > 0 for v in nich)
        n_neg1 = sum(sig_neg(v) for v in nich)
        n_neg2 = sum(sig_neg(v) for v in outs)
        n_neg3 = sum(sig_neg(v) for v in cross)
        c1 = n_pos >= GATE_MIN_CELLS and n_neg1 == 0
        c2 = n_neg2 >= GATE_MIN_CELLS
        c3 = n_neg3 >= GATE_MIN_CELLS
        cross_use = float(np.mean([v["use_focal"] for v in cross]))
        low = bool(c1 and c2 and not c3 and cross_use < LOW_USE)
        verdict = "pass" if (c1 and c2 and c3) else ("low_power" if low else "fail")
        out[x] = dict(complete=True, niche_pos=int(n_pos), niche_sig_neg=int(n_neg1), out_sig_neg=int(n_neg2),
                      cross_sig_neg=int(n_neg3), c1=bool(c1), c2=bool(c2), c3=bool(c3), pass_=bool(c1 and c2 and c3),
                      cross_use_focal=cross_use, verdict=verdict)
    return out


def run(seeds, steps, workers, out: Path, theta: float, approach: float, config: str = CONFIG, cells=None,
        behaviors=BEHAVIORS, flee_check=True) -> dict:
    from env_v2.config import load_v2_config

    cells = list(cells or CELLS)
    cfg0 = load_v2_config(ROOT / config)
    per_sec, n_agents = 60.0 / float(cfg0.policy_interval), int(cfg0.N)
    variants = [(x, m) for x in behaviors for m in MODES] + ([("graze", "niche")] if flee_check else [])
    # 바탕 실행(X 없음)도 같은 칸·시드로 돌린다 — 보고만 하는 이중차(침입 차 − 같은 슬롯의 바탕 차)용
    variants.append((None, "base"))
    jobs = [(c, theta, approach, x, m, s, steps, config) for x, m in variants for c in cells for s in seeds]
    t0 = time.time()
    per = {}
    for c, _, _, x, m, s, o in _map(jobs, workers):
        per.setdefault(f"{x or 'base'}|{m}|{c}", {})[str(s)] = o
    base = {c: per.pop(f"base|base|{c}") for c in cells}
    summary = {}
    ss = [str(s) for s in seeds]
    for key, by_seed in per.items():
        c = key.split("|")[2]
        v = summary[key] = {k: paired([by_seed[s][k] for s in ss]) for k in ("rew", "pred", "starve")}
        v["rew_did"] = paired([by_seed[s]["rew"] - base[c][s]["rew_fr"] for s in ss])
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
    per["base"] = base
    g = gate(summary, cells)
    g_did = gate(summary, cells, key="rew_did")
    meta = dict(config=config, seeds=list(seeds), steps=int(steps), theta=theta, approach=approach, cells=cells,
                behaviors=list(behaviors), t_crit=T_CRIT, event_k=EVENT_K, low_use=LOW_USE,
                elapsed_s=round(time.time() - t0, 1), digest={c: config_digest(cell_cfg(c, config)) for c in cells})
    res = dict(meta=meta, gate=g, gate_did=g_did, summary=summary, per_seed=per)
    out.mkdir(parents=True, exist_ok=True)
    (out / "invasion.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (out / "gate.json").write_text(json.dumps(dict(meta=meta, gate=g, gate_did_report_only=g_did), indent=1),
                                   encoding="utf-8")
    (out / "invasion.md").write_text(report_md(res), encoding="utf-8")
    return res


_VERDICT = {"pass": "통과", "fail": "실패", "low_power": "판정 불능(검정력 부족)"}


def report_md(res: dict) -> str:
    m, g, s = res["meta"], res["gate"], res["summary"]
    gd = res.get("gate_did", {})
    small = len(m["seeds"]) < 40 or m["steps"] < 3000
    L = ["# v3 R0 행동별 통과 시험 (손 규칙 소수 침입)" + (" — smoke, 판정 아님" if small else ""), "",
         f"설정 {m['config']} + obs_extra, 시드 {m['seeds'][0]}~{m['seeds'][-1]} ({len(m['seeds'])}개) × {m['steps']}스텝,"
         f" 거주 규칙 R_base(θ {m['theta']:g}, a {m['approach']:g}). 값 = 침입 16 − 거주 112, 개체-스텝당. 짝 t 임계"
         f" {m['t_crit']}.", "", "## 판정 (PREREG 3절)", "",
         "| 행동 | (1) 니치 양수 칸 / 유의 음수 칸 | (2) 니치 밖 유의 음수 칸 | (3) 교차 유의 음수 칸 | 교차 X 사용(침입) | 판정 |"
         " 이중차 판정(보고만) |",
         "|---|---|---|---|---|---|---|"]
    for x in BEHAVIORS:
        v = g.get(x, {})
        if not v.get("complete"):
            L.append(f"| {x} | — | — | — | — | (칸 부족) | — |")
            continue
        vd = gd.get(x, {})
        L.append(f"| {x} | {v['niche_pos']} / {v['niche_sig_neg']} {'○' if v['c1'] else '×'} | "
                 f"{v['out_sig_neg']} {'○' if v['c2'] else '×'} | {v['cross_sig_neg']} {'○' if v['c3'] else '×'} | "
                 f"{v['cross_use_focal']:.3f} | {_VERDICT[v['verdict']]} | {_VERDICT.get(vd.get('verdict'), '—')} |")
    L += ["", f"판정 불능 = (1)·(2) 통과, (3)만 실패, 교차 칸 침입 X 사용 비율 평균 < {m['low_use']} (통과가 아니다. R1 포함은 사람이"
          " 정한다). 이중차 판정은 같은 규칙을 보상 이중차로 잰 강건성 확인이다.",
          "", "## 칸별 값", "",
          "이중차(보고만) = 침입 차 − 같은 시드·칸에서 X 없이 돌린 슬롯 0~15 − 나머지 차(배치 운을 뺀다). 판정은 PREREG 대로 침입 차다."
          f" 사건 조건 = X 규칙의 조건에 들어선 순간부터 {m['event_k']}스텝 창의 보상 합·피식 비율, 침입 − 거주(창 수 침입·거주)."
          " MDE80 = 80% 검정력 최소 차. 희석 보정 = 보상 차 / 침입 X 사용 비율.",
          "", "| 행동 | 모드 | 칸 | 보상 (t) | MDE80 | 희석 보정 | 보상 이중차 (t) | 피식 (t) | 아사 (t) | X 사용 침입·거주 |"
          " 사건 조건 보상 (t) | 사건 조건 피식 (t) | 창 수 | 깜빡임 침입·거주 | 초당 전환 침입·거주 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]

    def f(x, nd=5):
        if x["n"] == 0 or not math.isfinite(x["mean"]):
            return "—"
        return f"{x['mean']:+.{nd}f} ({x['t']:+.2f})" if x["t"] is not None else f"{x['mean']:+.{nd}f}"

    def num(x, fmt):
        return format(x, fmt) if x is not None and math.isfinite(x) else "—"
    for key in sorted(s):
        x, mode, c = key.split("|")
        v = s[key]
        L.append(f"| {x} | {mode} | {c} | {f(v['rew'])} | {num(v['rew']['mde80'], '.5f')} | "
                 f"{num(v['rew_per_use'], '+.4f')} | {f(v['rew_did'])} | {f(v['pred'])} | {f(v['starve'])} | "
                 f"{v['use_focal']:.3f} · {v['use_res']:.3f} | {f(v['ev_rew'], 3)} | {f(v['ev_pred'], 4)} | "
                 f"{v['ev_n_f']} · {v['ev_n_r']} | {num(v['flicker_f'], '.3f')} · {num(v['flicker_r'], '.3f')} | "
                 f"{v['switch_per_sec_f']:.3f} · {v['switch_per_sec_r']:.3f} |")
    return "\n".join(L) + "\n"


def prereg_problems(a, seeds) -> list[str]:
    """사전 등록 폴더에 쓰는 실행의 조건 검사. PREREG 조건과 다른 인자 목록(비면 문제 없음)."""
    bad = []
    if list(seeds) != SEEDS:
        bad.append("--seeds (PREREG 12000~12039)")
    if a.steps != STEPS:
        bad.append(f"--steps (PREREG {STEPS})")
    if a.cells is not None and sorted(a.cells) != sorted(CELLS):
        bad.append("--cells (PREREG 칸 8개 모두)")
    if list(a.grid_theta) != list(GRID_THETA) or list(a.grid_approach) != list(GRID_APPROACH):
        bad.append("--grid-theta/--grid-approach (PREREG 격자)")
    if a.config != CONFIG:
        bad.append(f"--config (PREREG {CONFIG})")
    if a.cmd == "run" and sorted(a.behaviors) != sorted(BEHAVIORS):
        bad.append("--behaviors (PREREG 셋 모두)")
    if a.cmd == "run" and a.no_flee_check:
        bad.append("--no-flee-check (PREREG 는 FLEE 확인을 보고한다)")
    if a.theta is not None:
        path = Path(a.out) / "search.json"
        best = json.loads(path.read_text(encoding="utf-8"))["best"] if path.exists() else None
        if best is None or (best["theta"], best["approach"]) != (a.theta, a.approach):
            bad.append(f"--theta/--approach (사전 등록 폴더에서는 탐색 캐시의 값과 같아야 한다: {best})")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="v3 R0 행동별 통과 시험(손 규칙 소수 침입)")
    ap.add_argument("cmd", choices=("search", "run"))
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--out", default=str(PREREG_OUT), help="결과 폴더. 기본값은 사전 등록 폴더(PREREG 조건만 받는다)")
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--seeds", type=int, nargs="+", default=None)
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--cells", nargs="+", default=None, choices=sorted(CELLS))
    ap.add_argument("--behaviors", nargs="+", default=list(BEHAVIORS), choices=BEHAVIORS)
    ap.add_argument("--theta", type=float, default=None, help="거주 규칙 θ (주면 탐색을 돌리지 않는다)")
    ap.add_argument("--approach", type=float, default=None, help="거주 규칙 a (--theta 와 함께)")
    ap.add_argument("--grid-theta", type=float, nargs="+", default=list(GRID_THETA))
    ap.add_argument("--grid-approach", type=float, nargs="+", default=list(GRID_APPROACH))
    ap.add_argument("--force", action="store_true", help="조건이 다른 탐색 캐시가 있어도 다시 재서 덮는다")
    ap.add_argument("--no-flee-check", action="store_true")
    a = ap.parse_args(argv)
    if (a.theta is None) != (a.approach is None):
        ap.error("--theta 와 --approach 는 함께 준다")
    out = Path(a.out)
    seeds = a.seeds or SEEDS
    if out.resolve() == PREREG_OUT.resolve():
        bad = prereg_problems(a, seeds)
        if bad:
            ap.error("사전 등록 폴더 " + str(PREREG_OUT) + " 에는 PREREG 조건만 쓴다(결과를 덮지 않게). 다른 조건: "
                     + ", ".join(bad) + ". smoke·부분 실행은 --out 에 다른 폴더를 준다")
    try:
        if a.cmd == "search":
            res = search(seeds, a.steps, a.workers, out, a.config, a.grid_theta, a.grid_approach, a.cells, a.force)
            print(json.dumps(res["best"]), flush=True)
            return 0
        if a.theta is None:
            res = search(seeds, a.steps, a.workers, out, a.config, a.grid_theta, a.grid_approach, a.cells, a.force)
            th, ap_ = res["best"]["theta"], res["best"]["approach"]
        else:
            th, ap_ = a.theta, a.approach
    except StaleCache as e:
        ap.error(str(e))
    run(seeds, a.steps, a.workers, out, th, ap_, a.config, a.cells, a.behaviors, not a.no_flee_check)
    print((out / "invasion.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
