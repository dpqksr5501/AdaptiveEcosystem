"""도망길 오라클(상한)과 '배울 수 있나' (10-21 '도망 방향을 두뇌가 고름' 2단계 — 설계 Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 9-3·9-4절, 학습 전, 보고만).

RUN 판(N 세계, wild_flight.route_fixed 'run', 끝 규칙 지금·quiet_end 15)을 돌리다가 도주 시작을 골라(세계마다 몫만큼 — 판 길이에 고르게 뽑은 시각마다 그
시각 뒤 첫 도주 시작 스텝의 시작 가운데 하나), 그 순간의 세계를 복제(deepcopy)해 그 사슴에게만 길 넷을
강제(World.route_redecide — 가능하지 않으면 RUN)하고 복제 뒤 난수 흐름 3 개로 그 도망이 끝날 때까지(최대 300 스텝) 돌린다. 값 = 쫓긴 시간(시작부터 늑대가
이 사슴을 마지막으로 표적으로 둔 순간까지의 초 — 관문 1차 P1·route_rules.py P1 과 같은 잣대, MEASURE), 잡힘·굶음·안 끝남은 가장 나쁜 값 = 300 스텝.
길마다 흐름 평균, 가장 짧은 길 = '정답'. 9-4 판단표의 첫 두 줄(이득 없음·배울 수 있나)도 이 잣대다 — 도망 길이(끝까지의 초)는 보조 표로만 적는다.
  낙관 편향 빼기: '가짜 오라클' = 팔 넷 모두 RUN(팔 a 는 진짜 길 a 와 같은 난수 흐름 3a..3a+2 — 팔 0 은 진짜 RUN 그대로)의 같은 셈 이득. 진짜 − 가짜.
  두뇌 길(RUN·COVER·SHELTER, 셋)과 측정 전용 OPEN 까지 넷 모두 적는다. 판단은 두뇌 길 셋.
  배울 수 있나: 시작 때 망이 볼 수 있는 값(cover_reach·shelter_reach(단계 4 관측 22·23 의 값)·escape_room·pred_dist·pred_approach·obstacle_near·threat_hidden·
    visibility)으로 정답(그때 가능한 두뇌 길 가운데 가장 짧은 것)을 깊이 3 결정 나무에 맞춘다(시드 34960~34989), 34990~34999 에서 '늘 RUN' 대비 손해(regret)를
    30 % 넘게 줄이면 통과. sklearn 이 없으면 같은 기준(지니)의 작은 구현을 쓴다.

    # herbivore_rl/ 에서 (PYTHONUTF8=1)
    python results/v3/route/oracle.py run --out <폴더> [--workers 14]        # oracle_raw.json → report
    python results/v3/route/oracle.py run --out <폴더> --smoke                # 시드 3 · 300 스텝 · 워커 ≤ 4 (도구 확인)
    python results/v3/route/oracle.py report --out <폴더>                     # oracle.json·oracle.md (route_rules.py report 가 9-4 판단표에 넣는다)
    python results/v3/route/oracle.py run --out <폴더> --world-set features.obstacles.foliage.enabled=true   # 세계 덮기 (route_rules.py 와 같은 뜻)
세계·두뇌·워커는 route_rules.py 와 같다(<out>/world — 스냅숏 변환, 도주 밖 obs21zero argmax, 워커 풀 env_v2.rollout.make_executor).
세계 덮기 --world-set 키=값(여러 번 — route_rules.apply_world_set): 모든 세계에 같게 건다(RUN 판·길 넷·가짜 RUN 이 모두 그 세계의 복제라 비교 기준 RUN 도
같은 덮기). oracle_raw.json·oracle.json meta 에 남고, route_rules.py report 는 규칙 측정과 덮기가 다른 오라클을 판단표에 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

import route_rules as rr  # noqa: E402  (sys.path·torch 순서는 이 모듈이 맞춘다)

import numpy as np  # noqa: E402

ad, lv, re_ = rr.ad, rr.lv, rr.re_

SEEDS = (34960, 34999)
FIT, TEST = (34960, 34989), (34990, 34999)
PER_REGION = 300                    # 지역·끝 규칙마다 도주 시작 수 (세계마다 ceil(PER_REGION / 시드 수))
STREAMS = 3                         # 길마다 복제 뒤 난수 흐름
MAX_STEPS = 300                     # 한 복제 롤아웃 최대 스텝 (40 초) — 잡힘·굶음·안 끝남은 이 값
MAIN_STEPS = 1800                   # RUN 판 길이 (몫을 채우면 일찍 멈춘다)
SMOKE = dict(seeds=3, steps=300, workers=4, quota=2, max_steps=60)
ORACLE_TAG = 0x4F5243               # "ORC"
ROUTE_KO = dict(run="RUN", cover="COVER", shelter="SHELTER", open="OPEN")
OBS_FEATS = ("escape_room", "pred_dist", "pred_approach", "obstacle_near", "threat_hidden", "visibility")
FEATS = ("cover_reach", "shelter_reach") + OBS_FEATS
BRAIN = (0, 1, 2)                   # 두뇌 길 번호 (ROUTE_RUN·ROUTE_COVER·ROUTE_SHELTER)
NO_GAIN_S = -0.5                    # 9-4 첫 줄: 오라클(잡음 뺀 값) − RUN > −0.5 초 (모든 지역, 두 끝 규칙)이면 학습하지 않음
REGRET_CUT = 0.3                    # 배울 수 있나: '늘 RUN' 대비 손해를 30 % 넘게 줄인다
MEASURE = "contact"                 # 판단 잣대: 쫓긴 시간 (route_rules P1·관문 1차와 같다). 보조 = "len" (도망 길이)
STEP_S = rr.STEP_S


# --------------------------------------------------------------------- #
# 워커 (세계 하나 — RUN 판 + 고른 시작마다 복제 롤아웃)
# --------------------------------------------------------------------- #

def reseed(wc, key: list) -> None:
    """복제 세계의 난수 흐름을 바꾼다 (v1 스트림·기능 스트림 — 열쇠 key + 기능 순번)."""
    wc.rng = np.random.default_rng(list(key))
    for j, k in enumerate(sorted(wc._feature_rngs)):
        wc._feature_rngs[k] = np.random.default_rng(list(key) + [j + 1])


def rollout_one(w, pol, i: int, route: int, key: list, max_steps: int, L0: int) -> dict:
    """세계 w 를 복제해 사슴 i 의 길을 route 로 다시 고르고 그 도망이 닫힐 때까지 돈다 → dict(len 스텝(시작부터), contact 스텝, cause, closed, n)."""
    from env_v2 import rollout as ro
    from env_v2.world import FLIGHT_CAUSES

    wc = copy.deepcopy(w)
    reseed(wc, key)
    got = wc.route_redecide(i, route)
    ro.forward_bind(pol, wc)
    c0 = int(wc._fl_closed[i])
    n = 0
    while n < max_steps:
        wc.step(np.asarray(pol(wc.observe()), dtype=np.float64))
        n += 1
        if int(wc._fl_closed[i]) > c0:
            break
    if int(wc._fl_closed[i]) > c0:
        cause = FLIGHT_CAUSES[int(wc._fl_last_cause[i])]
        return dict(len=int(wc._fl_last_len[i]) - L0, contact=max(int(wc._fl_last_contact[i]) - L0, 0), cause=cause, closed=True, n=n, got=int(got))
    return dict(len=n, contact=n, cause="open", closed=False, n=n, got=int(got))


def pick_times(seed: int, reg_i: int, qe: int, steps: int, quota: int) -> list[int]:
    """세계 하나에서 시작을 고를 시각 quota 개 — [0, steps) 에서 겹치지 않게 고르게 뽑는다(세계 난수 밖, 판 고르기 전용 흐름). 시각마다 그 시각 이후 첫 도주
    시작 스텝의 시작 가운데 하나를 고른다(사슴 128 이면 스텝마다 시작이 잦아 몫을 판 앞쪽에서 다 채우지 않게)."""
    g = np.random.default_rng([ORACLE_TAG, 1, int(seed), int(reg_i), int(qe)])
    return sorted(int(t) for t in g.choice(int(steps), size=min(int(quota), int(steps)), replace=False))


def _oracle_world(job: dict) -> dict:
    """세계 하나: RUN 판(route_fixed 'run')을 돌리며 고를 시각(pick_times)마다 도주 시작 하나를 골라 길 넷 × 흐름 + 가짜 RUN 팔 셋 × 흐름을 돌린다."""
    from env.config import Config
    from env_v2 import rollout as ro
    from env_v2.world import ROUTE_COVER, ROUTE_NAMES, ROUTE_RUN, ROUTE_SHELTER, ROUTE_SHELTER_REACH_U, World

    t0 = time.perf_counter()
    seed, qe, reg_i = int(job["seed"]), int(job["quiet_end"]), int(job["region_index"])
    w = World(Config(job["cfg"]), seeds=[seed])
    ad.apply_snapshot_food(w, job["snap_food"])
    w.track_flight = True
    pol = ro.build_policy({"kind": "rep_learned", "path": str(job["model"])}, seed)
    ro.forward_bind(pol, w)
    fi = [w.obs_names.index(k) for k in OBS_FEATS]
    S, ms, quota = int(job["streams"]), int(job["max_steps"]), int(job["quota"])
    due = pick_times(seed, reg_i, qe, int(job["steps"]), quota)
    pick = np.random.default_rng([ORACLE_TAG, 2, seed, reg_i, qe])
    recs, main_n, roll_n = [], 0, 0
    for t in range(int(job["steps"])):
        if not due:
            break
        w.step(np.asarray(pol(w.observe()), dtype=np.float64))
        main_n += 1
        cand = np.flatnonzero(w.route_onset & w.alive)
        took = False
        while due and due[0] <= t and len(cand):
            due.pop(0)
            k = int(pick.integers(len(cand)))
            i = int(cand[k])
            cand = np.delete(cand, k)
            uid = len(recs)
            ok = w.route_cand_ok[i].tolist()
            obs = w._obs[i]
            feats = dict(cover_reach=float(w.route_cover_h[i]) if ok[ROUTE_COVER] else 0.0,
                         shelter_reach=float(np.clip(w.route_shelter_mu[i] / ROUTE_SHELTER_REACH_U, 0.0, 1.0)) if ok[ROUTE_SHELTER] else 0.0,
                         **{k: float(obs[j]) for k, j in zip(OBS_FEATS, fi)})
            L0 = int(w._fl_len[i])
            arms = {}
            for r in range(len(ROUTE_NAMES)):
                arms[f"real{r}"] = [rollout_one(w, pol, i, r, [ORACLE_TAG, seed, reg_i, qe, uid, 3 * r + s], ms, L0) for s in range(S)]
            for a in range(1, len(ROUTE_NAMES)):
                arms[f"fake{a}"] = [rollout_one(w, pol, i, ROUTE_RUN, [ORACLE_TAG, seed, reg_i, qe, uid, 3 * a + s], ms, L0) for s in range(S)]
            roll_n += sum(x["n"] for v in arms.values() for x in v)
            recs.append(dict(t=int(w.t), deer=i, ok=ok, feats=feats, L0=L0, arms=arms))
            took = True
        if took:
            ro.forward_bind(pol, w)
    return dict(seed=seed, region=job["region"], quiet_end=qe, onsets=recs, main_steps=main_n, roll_steps=roll_n,
                wall_s=round(time.perf_counter() - t0, 2))


# --------------------------------------------------------------------- #
# 분석
# --------------------------------------------------------------------- #

def value(x: dict, cap: int, key: str = MEASURE) -> float:
    """롤아웃 하나의 값(스텝): 살아 닫힌 도망이면 시작부터 끝까지(또는 쫓긴) 스텝, 잡힘·굶음·안 끝남이면 cap."""
    if not x["closed"] or x["cause"] in ("caught", "starved"):
        return float(cap)
    return float(x[key])


def onset_table(recs: list, cap: int, key: str = MEASURE) -> dict:
    """도주 시작 목록 → 배열: real (K, 4)·fake (K, 4)(팔 0 = real 0) 흐름 평균(초), ok (K, 4), X (K, 8), seed (K,)."""
    K = len(recs)
    real, fake = np.zeros((K, 4)), np.zeros((K, 4))
    for k, r in enumerate(recs):
        for a in range(4):
            real[k, a] = np.mean([value(x, cap, key) for x in r["arms"][f"real{a}"]]) * STEP_S
        fake[k, 0] = real[k, 0]
        for a in range(1, 4):
            fake[k, a] = np.mean([value(x, cap, key) for x in r["arms"][f"fake{a}"]]) * STEP_S
    ok = np.array([r["ok"] for r in recs], dtype=bool).reshape(K, 4)
    X = np.array([[r["feats"][f] for f in FEATS] for r in recs], dtype=np.float64).reshape(K, len(FEATS))
    seed = np.array([r["seed"] for r in recs], dtype=np.int64)
    return dict(real=real, fake=fake, ok=ok, X=X, seed=seed)


def tstat(d: np.ndarray) -> dict:
    n = len(d)
    if n < 2:
        return dict(mean=float(d.mean()) if n else float("nan"), se=float("nan"), t=float("nan"), n=n)
    m, se = float(d.mean()), float(d.std(ddof=1) / math.sqrt(n))
    return dict(mean=m, se=se, t=m / se if se > 0 else (0.0 if m == 0 else math.copysign(math.inf, m)), n=n)


def oracle_gain(tb: dict) -> dict:
    """오라클 이득(초, 음수 = 짧아짐): 두뇌 길 셋·넷(OPEN 포함) — 진짜, 가짜(같은 팔 수), 잡음 뺀 값, 길마다 RUN 대비(전체·가능할 때만)."""
    real, fake, ok = tb["real"], tb["fake"], tb["ok"]
    out = dict(n=len(real), run_s=float(real[:, 0].mean()) if len(real) else float("nan"))
    for nm, cols in (("brain", list(BRAIN)), ("all4", [0, 1, 2, 3])):
        g = real[:, cols].min(1) - real[:, 0]
        f = fake[:, cols].min(1) - fake[:, 0]
        gf = np.where(ok[:, cols], real[:, cols], np.inf).min(1) - real[:, 0]
        out[nm] = dict(gain=tstat(g), fake=tstat(f), corrected=float(g.mean() - f.mean()) if len(g) else float("nan"), feasible_gain=tstat(gf))
    out["route"] = {}
    for r, name in enumerate(("run", "cover", "shelter", "open")):
        if r == 0:
            continue
        d = real[:, r] - real[:, 0]
        out["route"][name] = dict(all=tstat(d), feasible=tstat(d[ok[:, r]]), feasible_share=float(ok[:, r].mean()) if len(ok) else float("nan"))
    best = np.where(ok[:, list(BRAIN)], real[:, list(BRAIN)], np.inf).argmin(1) if len(real) else np.zeros(0, dtype=int)
    out["label_share"] = {name: float((best == r).mean()) if len(best) else float("nan") for r, name in enumerate(("run", "cover", "shelter"))}
    return out


def _gini_tree(X: np.ndarray, y: np.ndarray, depth: int, classes: np.ndarray):
    """sklearn 이 없을 때의 작은 결정 나무 (지니, 깊이 depth, 문턱 = 이웃 값의 가운데, 같은 이득이면 앞 특징·작은 문턱)."""
    def leaf(yy):
        cnt = np.array([(yy == c).sum() for c in classes])
        return ("leaf", int(classes[int(cnt.argmax())]))

    def gini(yy):
        if not len(yy):
            return 0.0
        p = np.array([(yy == c).mean() for c in classes])
        return 1.0 - float((p * p).sum())

    def grow(idx, d):
        yy = y[idx]
        if d == 0 or len(np.unique(yy)) <= 1 or len(idx) < 2:
            return leaf(yy)
        base, best = gini(yy) * len(idx), None
        for f in range(X.shape[1]):
            v = np.unique(X[idx, f])
            for th in (v[:-1] + v[1:]) / 2.0:
                L = idx[X[idx, f] <= th]
                R = idx[X[idx, f] > th]
                cost = gini(y[L]) * len(L) + gini(y[R]) * len(R)
                if cost < base - 1e-12 and (best is None or cost < best[0] - 1e-12):
                    best = (cost, f, float(th), L, R)
        if best is None:
            return leaf(yy)
        return ("split", best[1], best[2], grow(best[3], d - 1), grow(best[4], d - 1))

    root = grow(np.arange(len(y)), depth)

    def predict(Z):
        out = np.empty(len(Z), dtype=np.int64)
        for k, z in enumerate(Z):
            n = root
            while n[0] == "split":
                n = n[3] if z[n[1]] <= n[2] else n[4]
            out[k] = n[1]
        return out

    return predict, root


def fit_tree(X: np.ndarray, y: np.ndarray, depth: int = 3):
    """깊이 3 결정 나무 → (예측 함수, 설명 글). sklearn 이 있으면 DecisionTreeClassifier(random_state 0)."""
    try:
        from sklearn.tree import DecisionTreeClassifier, export_text
    except ImportError:
        pred, root = _gini_tree(X, y, depth, np.unique(y))
        return pred, f"작은 구현 {root!r}"
    clf = DecisionTreeClassifier(max_depth=depth, random_state=0).fit(X, y)
    return clf.predict, export_text(clf, feature_names=list(FEATS))


def learnability(tb: dict, fit_seeds, test_seeds) -> dict:
    """배울 수 있나 (9-3): 정답 = 그때 가능한 두뇌 길 가운데 흐름 평균이 가장 짧은 것(같으면 RUN·COVER·SHELTER 순). 맞춤 시드에서 깊이 3 나무, 확인 시드에서
    regret = 고른 길(가능하지 않으면 RUN) − 정답, '늘 RUN' regret 과 견준 줄어든 몫 > 0.3 이면 통과. 확인 표본이나 RUN 손해가 없으면 판단 없음(None)."""
    real, ok, X, seed = tb["real"], tb["ok"], tb["X"], tb["seed"]
    cols = list(BRAIN)
    y = np.where(ok[:, cols], real[:, cols], np.inf).argmin(1)
    fit = (seed >= fit_seeds[0]) & (seed <= fit_seeds[1])
    tst = (seed >= test_seeds[0]) & (seed <= test_seeds[1])
    out = dict(n_fit=int(fit.sum()), n_test=int(tst.sum()), label_fit={nm: int((y[fit] == r).sum()) for r, nm in enumerate(("run", "cover", "shelter"))})
    if fit.sum() < 2 or tst.sum() < 1:
        return dict(out, passed=None, why="맞춤·확인 표본이 모자란다")
    if len(np.unique(y[fit])) == 1:
        pred = np.full(int(tst.sum()), int(y[fit][0]))
        tree = f"한 길뿐 ({('run', 'cover', 'shelter')[int(y[fit][0])]})"
    else:
        fn, tree = fit_tree(X[fit], y[fit])
        pred = np.asarray(fn(X[tst]), dtype=np.int64)
    Rt, Ot = real[tst][:, cols], ok[tst][:, cols]
    ar = np.arange(int(tst.sum()))
    pred = np.where(Ot[ar, pred], pred, 0)
    best = np.where(Ot, Rt, np.inf).min(1)
    reg_run = float((Rt[:, 0] - best).mean())
    reg_tree = float((Rt[ar, pred] - best).mean())
    red = (reg_run - reg_tree) / reg_run if reg_run > 0 else float("nan")
    passed = None if not reg_run > 0 else bool(red > REGRET_CUT)
    return dict(out, regret_run_s=reg_run, regret_tree_s=reg_tree, reduction=red, passed=passed, tree=tree,
                why=("RUN 손해 없음 — 배울 것이 없다" if passed is None else f"손해 {reg_run:.2f} → {reg_tree:.2f} 초 (줄어든 몫 {red * 100:.0f}%)"))


def summarize(raw: dict) -> dict:
    """oracle_raw.json → 지역·끝 규칙마다 오라클 이득, 끝 규칙마다 배울 수 있나, 9-4 첫 두 줄 판단 — 모두 쫓긴 시간(MEASURE, route_rules P1 과 같은 잣대).
    gain_len = 같은 셈을 도망 길이로 (보조, 판단에 쓰지 않는다). 잴 값이 없으면 no_gain None (판단하지 않음)."""
    cap = int(raw["max_steps"])
    rows = [dict(o, seed=w["seed"], region=w["region"], quiet_end=w["quiet_end"]) for w in raw["worlds"] for o in w["onsets"]]
    regions = sorted({w["region"] for w in raw["worlds"]})
    qes = sorted({int(w["quiet_end"]) for w in raw["worlds"]})
    out = dict(max_steps=cap, streams=raw["streams"], regions=regions, quiet_ends=qes, measure=MEASURE, gain={}, gain_len={}, learn={})
    for qe in qes:
        sub = [r for r in rows if r["quiet_end"] == qe]
        for reg in regions + [None]:
            rs = [r for r in sub if reg is None or r["region"] == reg]
            key = f"q{qe}:{reg or 'all'}"
            out["gain"][key] = oracle_gain(onset_table(rs, cap, MEASURE))
            out["gain_len"][key] = oracle_gain(onset_table(rs, cap, "len"))
        out["learn"][f"q{qe}"] = learnability(onset_table(sub, cap, MEASURE), raw["fit_seeds"], raw["test_seeds"])
    reg_keys = [k for k in out["gain"] if not k.endswith(":all")]
    corr = {k: out["gain"][k]["brain"]["corrected"] for k in reg_keys}
    vals = [v for v in corr.values() if v == v]
    no_gain = None if not vals else all(v > NO_GAIN_S for v in vals)
    gained_q = sorted({int(k.split(":")[0][1:]) for k, v in corr.items() if v == v and v <= NO_GAIN_S})
    known = [out["learn"][f"q{q}"]["passed"] for q in gained_q if out["learn"][f"q{q}"]["passed"] is not None]
    learnable = None if not known else all(known)          # 이득이 있는 끝 규칙에서 판단할 수 있는 것만 (확인 표본에 RUN 손해가 없으면 뺀다)
    out["decision"] = dict(
        no_gain=no_gain, learnable=learnable,
        no_gain_why="; ".join(f"{k} {v:+.2f} 초" for k, v in corr.items()),
        learnable_why="; ".join(f"q{q}: {out['learn'][f'q{q}']['why']}" for q in qes))
    return out


def fmt(s: dict, meta: dict) -> str:
    L = [f"# 도망길 오라클과 '배울 수 있나' (설계 9-3절 — 보고만){' — 연기 시험' if meta.get('smoke') else ''}", "",
         f"- 시드 {meta.get('seeds')}, 흐름 {s['streams']}, 롤아웃 최대 {s['max_steps']} 스텝 (잡힘·굶음·안 끝남 = 이 값), 워커 {meta.get('workers')}, "
         f"시간 {meta.get('wall_s')} 초, 세계-스텝 {meta.get('world_steps')}, 세계 덮기 {rr.world_set_text(meta.get('world_set') or {})}",
         "- 값 = 쫓긴 시간 — 도주 시작부터 늑대가 이 사슴을 마지막으로 표적으로 둔 순간까지의 초 (흐름 평균, 관문 1차 P1·route_rules.py P1 과 같은 잣대 — "
         "9-4 판단은 모두 이 값). 이득 = 가장 짧은 길 − RUN (음수 = 짧아짐). 잡음 뺀 값 = 진짜 이득 − 가짜(모두 RUN, 난수만 다름) 이득",
         "", "## 오라클 이득 (두뇌 길 셋 — RUN·COVER·SHELTER, 괄호 = OPEN 까지 넷)", "",
         "| 끝 규칙·지역 | 시작 수 | RUN 초 | 진짜 이득 | 가짜 이득 | 잡음 뺀 값 | 가능할 때만 이득 | COVER − RUN (가능할 때, t) | SHELTER − RUN (가능할 때, t) | OPEN − RUN (t) | 가능 몫 COVER·SHELTER | 정답 몫 RUN·COVER·SHELTER |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, g in s["gain"].items():
        b, a4 = g["brain"], g["all4"]
        rt = g["route"]
        ls = g["label_share"]
        L.append(f"| {k} | {g['n']} | {g['run_s']:.2f} | {b['gain']['mean']:+.2f} ({a4['gain']['mean']:+.2f}) | {b['fake']['mean']:+.2f} ({a4['fake']['mean']:+.2f}) | "
                 f"**{b['corrected']:+.2f}** ({a4['corrected']:+.2f}) | {b['feasible_gain']['mean']:+.2f} | "
                 f"{rt['cover']['feasible']['mean']:+.2f} ({rt['cover']['feasible']['t']:+.1f}) | {rt['shelter']['feasible']['mean']:+.2f} ({rt['shelter']['feasible']['t']:+.1f}) | "
                 f"{rt['open']['all']['mean']:+.2f} ({rt['open']['all']['t']:+.1f}) | {rt['cover']['feasible_share'] * 100:.0f}% · {rt['shelter']['feasible_share'] * 100:.0f}% | "
                 f"{ls['run'] * 100:.0f}·{ls['cover'] * 100:.0f}·{ls['shelter'] * 100:.0f}% |")
    L += ["", "### 도망 길이(시작부터 도망이 끝날 때까지의 초)로 잰 같은 표 (보조 — 판단에 쓰지 않는다, 잡음 뺀 값만)", "",
          "| 끝 규칙·지역 | 진짜 이득 | 가짜 이득 | 잡음 뺀 값 |", "|---|---|---|---|"]
    for k, g in s["gain_len"].items():
        L.append(f"| {k} | {g['brain']['gain']['mean']:+.2f} | {g['brain']['fake']['mean']:+.2f} | {g['brain']['corrected']:+.2f} |")
    L += ["", "## 배울 수 있나 (깊이 3 나무, 맞춤 → 확인 시드, 정답·손해 = 쫓긴 시간)", "", "| 끝 규칙 | 맞춤·확인 수 | 맞춤 정답 RUN·COVER·SHELTER | '늘 RUN' 손해 초 | 나무 손해 초 | 줄어든 몫 | 통과 |", "|---|---|---|---|---|---|---|"]
    for q, l in s["learn"].items():
        lf = l["label_fit"]
        L.append(f"| {q} | {l['n_fit']}·{l['n_test']} | {lf['run']}·{lf['cover']}·{lf['shelter']} | {l.get('regret_run_s', float('nan')):.2f} | "
                 f"{l.get('regret_tree_s', float('nan')):.2f} | {l.get('reduction', float('nan')) * 100:.0f}% | "
                 f"{'—' if l['passed'] is None else ('예' if l['passed'] else '아니오')} ({l['why']}) |")
    d = s["decision"]
    ng = "— (잴 값 없음)" if d["no_gain"] is None else ("예 — 학습하지 않음" if d["no_gain"] else "아니오")
    L += ["", "## 9-4 첫 두 줄 (쫓긴 시간)", "",
          f"- 오라클(잡음 뺀 값) − RUN > {NO_GAIN_S} 초 (모든 지역, 두 끝 규칙): **{ng}** ({d['no_gain_why']})",
          f"- 배울 수 있나: **{'—' if d['learnable'] is None else ('통과' if d['learnable'] else '실패 — 관측을 고친 뒤 다시 잼')}** ({d['learnable_why']})", ""]
    return "\n".join(L)


# --------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------- #

def cmd_run(a) -> int:
    from env_v2 import rollout as ro

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    info = rr.prepare_info(out, Path(a.snapshot))
    model = Path(a.model) if a.model else Path(info["start"]["zip"])
    seeds = rr.seeds_of(rr.lv.seed_range(a.seeds) if a.seeds else SEEDS)
    steps, W, ms, streams = MAIN_STEPS, int(a.workers), int(a.max_steps), int(a.streams)
    fit, test = FIT, TEST
    if a.smoke:
        seeds, steps, W, ms = seeds[: SMOKE["seeds"]], SMOKE["steps"], min(W, SMOKE["workers"]), SMOKE["max_steps"]
        fit, test = (seeds[0], seeds[-2]), (seeds[-1], seeds[-1])
    quota = SMOKE["quota"] if a.smoke else int(math.ceil(int(a.per_region) / len(seeds)))
    qes = [int(x) for x in a.quiet_ends.split(",")]
    wset = rr.parse_world_set(a.world_set)
    jobs = []
    for qe in qes:
        sets = dict(lv.NOSAT["sets"], **{"wild_flight.route_fixed": "run"})
        if qe > 0:
            sets["wild_flight.quiet_end"] = qe
        for j in ad.make_jobs(info, model, seeds, steps, False, dict(name=f"oracle_q{qe}", sets=sets)):
            rr.apply_world_set(j["cfg"], wset)                  # 세계 덮기 (없으면 그대로)
            j.update(quiet_end=qe, region_index=int(info["regions"][j["region"]]["region_index"]), quota=quota, streams=streams, max_steps=ms)
            jobs.append(j)
    print(f"도망길 오라클 → {out}: 세계 {len(jobs)} (시드 {seeds[0]}~{seeds[-1]} × 지역 {len(info['regions'])} × 끝 규칙 {qes}), 세계마다 시작 {quota}, "
          f"흐름 {streams}, 롤아웃 최대 {ms} 스텝, 워커 {W}, 세계 덮기 {rr.world_set_text(wset)}{', 연기 시험' if a.smoke else ''}", flush=True)
    t0 = time.perf_counter()
    ex = ro.make_executor(min(W, len(jobs)))
    worlds = []
    if ex is None:
        worlds = [_oracle_world(j) for j in jobs]
    else:
        from concurrent.futures import as_completed

        with ex:
            futs = [ex.submit(_oracle_world, j) for j in jobs]
            for k, f in enumerate(as_completed(futs), 1):
                worlds.append(f.result())
                if k % 10 == 0 or k == len(futs):
                    print(f"  세계 {k}/{len(futs)} ({time.perf_counter() - t0:.0f} 초)", flush=True)
    worlds.sort(key=lambda w: (w["quiet_end"], w["seed"], w["region"]))
    wall = time.perf_counter() - t0
    ws = sum(w["main_steps"] + w["roll_steps"] for w in worlds)
    raw = dict(made=datetime.now().isoformat(), snapshot=str(a.snapshot), model=lv.path_text(model), seeds=[seeds[0], seeds[-1]], fit_seeds=list(fit),
               test_seeds=list(test), quiet_ends=qes, quota=quota, streams=streams, max_steps=ms, main_steps=steps, workers=W,
               smoke=bool(a.smoke), wall_s=round(wall, 1), world_steps=ws, sec_per_world_step=float(sum(w["wall_s"] for w in worlds)) / max(ws, 1),
               world_set=lv.jsonable(wset), world_set_args=list(a.world_set or []), worlds=worlds)
    lv.atomic_write_json(out / "oracle_raw.json", lv.jsonable(raw), indent=None)
    print(f"  {wall:.0f} 초, 세계-스텝 {ws} (세계-스텝당 {raw['sec_per_world_step'] * 1000:.2f} ms) → oracle_raw.json", flush=True)
    return cmd_report(a)


def cmd_report(a) -> int:
    out = Path(a.out)
    raw = json.loads((out / "oracle_raw.json").read_text(encoding="utf-8"))
    s = summarize(raw)
    meta = {k: raw[k] for k in ("seeds", "workers", "wall_s", "world_steps", "smoke", "quota", "sec_per_world_step")}
    meta["world_set"] = raw.get("world_set", {})                  # 세계 덮기 (옛 판은 없음 = 덮기 없음)
    lv.atomic_write_json(out / "oracle.json", lv.jsonable(dict(meta=meta, **s)))
    text = fmt(s, meta)
    (out / "oracle.md").write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    print(f"-> {out / 'oracle.json'}, {out / 'oracle.md'} (9-4 판단표: route_rules.py report --out {out})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--snapshot", default=str(rr.SNAPSHOT))
    r.add_argument("--model", default=None)
    r.add_argument("--seeds", default=None, help=f"기본 {SEEDS[0]}-{SEEDS[1]}")
    r.add_argument("--per-region", type=int, default=PER_REGION)
    r.add_argument("--streams", type=int, default=STREAMS)
    r.add_argument("--max-steps", type=int, default=MAX_STEPS)
    r.add_argument("--quiet-ends", default="0,15")
    r.add_argument("--workers", type=int, default=14)
    r.add_argument("--smoke", action="store_true", help=f"시드 {SMOKE['seeds']} · {SMOKE['steps']} 스텝 · 워커 ≤ {SMOKE['workers']} · 세계마다 시작 {SMOKE['quota']}")
    r.add_argument("--world-set", action="append", default=[], metavar="키=값", help="세계 덮기 (여러 번 — route_rules.py 와 같다)")
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
