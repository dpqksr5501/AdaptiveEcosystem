"""R6 판정 뒤 진단 — 반사 밖 두뇌 FLEE 를 막으면 지킴 GF·GR 이 돌아오나 (보고만: 판정 결론 '기각'은 그대로다, 재학습 없음).

사람 결정(10-23 '짧게 진단 후 R7'): 설계 원칙은 반사(도주 반사 거리 wild_flight)가 '언제' 도망칠지, 두뇌가 '어디로'(RUN·SHELTER)를 정하는 것이다.
R6 두뇌는 늑대가 쫓지 않는데도 반사 밖에서 스스로 FLEE 를 골라 짧게 뛰었다(judge_notes — 판정 N 시드당 약 361 번). 그 선택만 막은 채 같은 꼴의 세계를
돌려, GF·GR 이 route0 수준으로 돌아오면 R7(반사 밖 두뇌 FLEE 막기)로 가고, 은신처 들락날락 때문에 GR 이 남으면 멈추고 사람에게 묻는다.

    # herbivore_rl/ 에서
    PYTHONUTF8=1 python results/v3/r6/diag/diag.py                 # → diag/diag.md · diag/diag.json (판 파일은 diag/runs/ — git 밖)
    PYTHONUTF8=1 python results/v3/r6/diag/diag.py --smoke 32080-32081 --smoke-steps 300 --out-dir <임시>     # 도구 확인 (쓰지 않는다)

세계: r6_eval.py 의 N 세계 그대로(스냅숏 거울 G + 늑대 포만 끔, 1800 스텝 — 판정 N 과 같은 길이·설정), 점검 시드 37120~37139 × 지역 셋
(r6_eval.use_plan('check') — 조기 점검 기준 판 runs/early_base.json 과 같은 세계). 판정 시드 37000~37099 · 고르기 시드 37100~37119 는 쓰지 않는다.

두뇌 넷 (모두 argmax. 막기는 이 스크립트의 정책 껍질 안에서만 한다 — env_v2·r6_eval·두뇌 파일·기본 동작은 그대로):
  route0     지금 두뇌(관측 24, 길은 늘 RUN — r6_eval ROUTE0)
  r6         R6 고른 두뇌 ckpt/v3/v3_r6_g995_s1_20m.zip 그대로
  r6_block   같은 두뇌 + 반사 밖 FLEE 막음: 결정 스텝(rep_peek reads)이고 덮기(도주 반사 WF_PANIC · 웅크림 WF_SHELTER)가 아닌 사슴의 마스크에서 FLEE 칸을
             끈다. 마스크는 망 입력이 아니다(RepObsSlice — 앞 관측 칸만 망에 들어간다). 그래서 막기 = 같은 로짓에서 FLEE 를 뺀 argmax(선택 키와 같은 값)다.
             덮기 중 행(판 4 — RUN·SHELTER 칸)은 그대로라 반사 도주와 길 고르기는 바뀌지 않는다. GRAZE 는 늘 열려 있어 빈 행이 없다.
  rule       측정용 '늘 SHELTER' 손 규칙(r6_eval 'shelter_rule' — 관측 21 두뇌 + wild_flight.route_fixed shelter, 보고만)

칸 (시드마다 지역 셋 합, 짝 t 는 route0 대비 같은 시드 — 시드 20 이면 문턱 t_crit(19) = 2.093, 판정과 같은 셈 함수):
  숨음 비율(lv.hide_pair 'hide' — P1), 잡힘 비율(쫓긴 도망 가운데 잡힘 — 'caught', GH), 잡힌 몫(사슴 가운데 — GN), GF(1000 산 사슴-스텝당 시작한 도망 —
  lv.flight_rate_pair 'starts'), GR(살아 끝난 도망 뒤 5 초(38 스텝) 안 다시 시작한 도망 — r6_eval.route_guards), 반사 밖 두뇌 FLEE 도망 수(도망 길 none —
  judge_notes 와 같은 셈: 반사 스텝이 하나도 없는 도망).

GR 나누기 (세계의 도망 기록 _fl_update · _fl_close 를 감싸 센다 — 통계 전용이라 세계·궤적은 그대로다. 감싼 셈의 다시 도망 수·시작 수가 세계의 refled ·
started 와 다르면 멈춘다). 다시 시작한 도망 하나를 아래 차례로 칸 하나에 넣는다:
  (다) 두뇌 스스로 뛰기 — 새 도망의 첫 FLEE 스텝이 반사(실행한 덮기 WF_PANIC)가 아니다(두뇌가 고른 FLEE 로 시작했다)
  (가) 은신처 들락날락 — 반사로 시작했고 지난 도망이 은신처로 끝났다(끝 까닭 cover 이거나, 마지막 FLEE 스텝 끝 위치가 은신처 원 안)
  (나) 그 밖 — 반사로 시작했고 지난 도망이 그 밖의 까닭으로 끝났다
  GF 도 같은 셈으로 나눈다: 두뇌 시작 · 반사 시작((가) 다시 도망 · (나) 다시 도망 · 5 초 밖 새 도망).

판단 규칙 (실행 전에 적음 — 보고만, 판정을 바꾸지 않는다):
  GO  — r6_block 의 GF·GR 짝 t 가 모두 문턱 미만이고, 숨음 비율 이득이 남고(차이 > 0, 짝 t ≥ 문턱), 잡힘 비율·잡힌 몫 짝 t 가 문턱 미만.
  ASK — 그 밖 모두. GR(또는 GF) 짝 t 가 문턱 이상일 때 GR 초과분(r6_block − route0, 시드 평균)의 절반 이상이 (가) 면 '은신처 들락날락'이 주된 원인으로 적는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve()
R6_DIR = HERE.parents[1]
for _p in (R6_DIR, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import r6_eval as R  # noqa: E402  (경로·torch 준비를 먼저 한다)
import numpy as np  # noqa: E402

lv, re_ = R.lv, R.re_
OUT = HERE.parent / "runs"                          # 판 파일 (git 밖 — herbivore_rl/.gitignore runs/)
MD, JS = HERE.parent / "diag.md", HERE.parent / "diag.json"
R6_MODEL = "ckpt/v3/v3_r6_g995_s1_20m.zip"
MODELS = (("route0", "route0", False), ("r6", R6_MODEL, False), ("r6_block", R6_MODEL, True), ("rule", "shelter_rule", False))
LABEL = {"route0": "route0 (지금 두뇌)", "r6": "R6 s1 그대로", "r6_block": "R6 s1 + 반사 밖 FLEE 막음", "rule": "'늘 SHELTER' 규칙 (측정용)"}
CATS = ("ga", "na", "da")
CAT_KO = {"ga": "(가) 은신처 들락날락", "na": "(나) 그 밖 끝 까닭 뒤", "da": "(다) 두뇌 스스로 뛰기"}


# --------------------------------------------------------------------- #
# 세계 기록 감싸기 (통계 전용)
# --------------------------------------------------------------------- #

class _Tracker:
    """세계 하나의 도망 기록(_fl_update · _fl_close)을 감싸 시작한 도망을 두뇌 시작·반사 시작으로, 다시 시작한 도망(GR)을 지난 도망의 끝 까닭·끝 위치
    (은신처 원 안)·길과 새 도망의 시작 종류로 센다. 원래 함수에 같은 인자를 그대로 넘기고 세계 칸을 쓰지 않는다(읽기만)."""

    def __init__(self, w):
        from env_v2.world import FLIGHT_CAUSES, FLIGHT_REFLEE_STEPS, ROUTE_NAMES

        if not getattr(w, "_route_on", False) or not w.track_flight:
            raise ValueError("진단은 길 기록이 있는 세계(wild_flight.route · route_fixed)에서 track_flight 를 켠 뒤에만 쓴다")
        N = w.N
        self.w = w
        self.causes, self.routes, self.reflee = FLIGHT_CAUSES, ROUTE_NAMES + ("none",), int(FLIGHT_REFLEE_STEPS)
        self.last_cause = np.full(N, -1, dtype=np.int64)
        self.last_circle = np.zeros(N, dtype=bool)
        self.last_route = np.full(N, -1, dtype=np.int64)
        self.starts = Counter()
        self.cells = Counter()
        self.gap = np.zeros(self.reflee + 1, dtype=np.int64)
        self.refled = 0
        self.ref0, self.st0 = int(w._flr_refled), int(w._fl_started)
        oc, ou = w._fl_close, w._fl_update          # 묶인 메서드 (원래 셈)

        def close(m, cause):
            m = np.asarray(m, dtype=bool)
            if m.any():
                rs_ = w._fl_rsteps[m]
                self.last_route[m] = np.where(rs_.sum(1) > 0, rs_.argmax(1), len(ROUTE_NAMES))
                self.last_cause[m] = np.asarray(cause)[m]
                self.last_circle[m] = w._fl_end_cov[m]
            return oc(m, cause)

        def update(flee, reflex, done, caught, live, in_cov, **kw):
            L0 = w._fl_len.copy()
            last0 = w._fl_last_t.copy()
            r0, s0 = int(w._flr_refled), int(w._fl_started)
            alive0 = np.asarray(live, dtype=bool) | np.asarray(done, dtype=bool)
            ex = np.asarray(flee, dtype=bool) & alive0
            rf = np.asarray(reflex, dtype=bool)
            new = ex & (L0 == 0)
            gap = (w.t - 1) - last0
            ref = new & (gap <= self.reflee)
            idx = np.flatnonzero(ref)
            prev = (self.last_cause[idx].copy(), self.last_circle[idx].copy(), self.last_route[idx].copy())
            out = ou(flee, reflex, done, caught, live, in_cov, **kw)
            if int(w._flr_refled) - r0 != len(idx) or int(w._fl_started) - s0 != int(new.sum()):
                raise RuntimeError(f"감싼 셈이 세계 기록과 다르다 (스텝 {w.t}: 다시 도망 {len(idx)} 대 {int(w._flr_refled) - r0}, "
                                   f"시작 {int(new.sum())} 대 {int(w._fl_started) - s0})")
            self.starts["brain"] += int(np.count_nonzero(new & ~rf))
            self.starts["reflex"] += int(np.count_nonzero(new & rf))
            ic = np.asarray(in_cov, dtype=bool)
            for j, i in enumerate(idx):
                c, cc, rr = int(prev[0][j]), bool(prev[1][j]), int(prev[2][j])
                key = "|".join(("reflex" if rf[i] else "brain", self.causes[c] if c >= 0 else "?", "1" if cc else "0",
                                self.routes[rr] if rr >= 0 else "?", "1" if ic[i] else "0"))
                self.cells[key] += 1
                self.gap[int(gap[i])] += 1
            self.refled += len(idx)
            return out

        w._fl_close = close
        w._fl_update = update

    def result(self) -> dict:
        w = self.w
        return dict(starts=dict(self.starts), cells=dict(self.cells), gap=self.gap.tolist(), refled=int(self.refled),
                    world_refled=int(w._flr_refled) - self.ref0, world_started=int(w._fl_started) - self.st0)


class _DiagPolicy:
    """rep_learned(RepLearned) 바깥 껍질: 행동은 바탕과 같은 마스크 로짓 argmax. block 이면 반사 밖 결정 행(rep_peek reads ∧ 덮기 아님)의 FLEE 칸만 끈다.
    결정 셈(반사 밖 결정 수 · 그 가운데 argmax 가 FLEE 인 수 · 막아서 대신 고른 행동)과 세계 도망 기록 감싸기(_Tracker)를 함께 한다."""

    def __init__(self, base, block: bool):
        self.base, self.block = base, bool(block)
        self.world = None
        self.tracker = None
        self.dec = Counter()

    def __getattr__(self, name):
        if name in ("base", "block", "world", "tracker", "dec"):
            raise AttributeError(name)
        return getattr(self.base, name)

    def bind_world(self, w) -> None:
        self.base.bind_world(w)
        self.world = w
        self.tracker = _Tracker(w)

    def __call__(self, obs):
        from env_v2.rep_policy import action_mask, policy_obs, rep_argmax
        from env_v2.repertoire import BEHAVIOR_NAMES, FLEE
        from env_v2.world import WF_PANIC, WF_SHELTER

        w, base = self.world, self.base
        pk = w.rep_peek()                                           # 순수 (세계·난수 그대로)
        m = action_mask(pk, w.observe(), base.params, obs_names=w.obs_names)    # RepLearned.mask() 와 같은 값
        pol = base.model.policy
        a = rep_argmax(pol, policy_obs(obs, m))
        live = np.ones(w.N, dtype=bool) if w.alive is None else np.asarray(w.alive, dtype=bool)
        over = ((w.wf_mode == WF_PANIC) | (w.wf_mode == WF_SHELTER)) & live
        free = np.asarray(pk["reads"], dtype=bool) & ~over & live
        ch = free & (a == FLEE)
        self.dec["free"] += int(free.sum())
        self.dec["free_flee"] += int(ch.sum())
        if self.block and ch.any():
            m = m.copy()
            m[free, FLEE] = False
            a2 = rep_argmax(pol, policy_obs(np.asarray(obs)[ch], m[ch]))
            a = a.copy()
            a[ch] = a2
            self.dec["blocked"] += int(ch.sum())
            for v in a2.tolist():
                self.dec[f"repl_{BEHAVIOR_NAMES[int(v)]}"] += 1
        base.last_mask = m
        return a.astype(np.float64)[:, None]

    def result(self) -> dict:
        return dict(dec=dict(self.dec), **self.tracker.result())


def _diag_world(job: dict, block: bool) -> dict:
    """세계 하나: live._world_multi 그대로(r6_eval 의 판과 같은 요약) + 'diag' 칸 (결정 셈·시작 종류·다시 도망 칸)."""
    from env_v2 import rollout as ro

    holder: dict = {}
    orig = ro.build_policy

    def build(spec, seed=0):
        p = _DiagPolicy(orig(spec, seed), block)
        holder["p"] = p
        return p

    ro.build_policy = build
    try:
        out = lv._world_multi(job)
    finally:
        ro.build_policy = orig
    out["diag"] = holder["p"].result()
    return out


def _diag_job(item):
    tag, job, block = item
    return tag, _diag_world(job, block)


# --------------------------------------------------------------------- #
# 돌리기
# --------------------------------------------------------------------- #

def tool_sha() -> str:
    return hashlib.sha256(HERE.read_bytes()).hexdigest()[:16]


def run_model(info: dict, name: str, text: str, block: bool, plan: dict, workers: int, out_dir: Path) -> dict:
    """두뇌 하나 → {meta, worlds} (같은 조건의 판 파일이 있으면 다시 쓴다)."""
    from concurrent.futures import as_completed

    from env_v2 import rollout as ro

    import diag as D                          # 워커가 이름으로 불러올 수 있게 (__main__ 이 아닌 모듈의 함수)

    spec = R.resolve_model(text)
    want = dict(use=plan["use"], seeds=plan["seeds"], steps=plan["steps"], model=text,
                model_sha1=hashlib.sha1(Path(spec["path"]).read_bytes()).hexdigest()[:12], sets=spec["sets"], block=bool(block),
                code=R.code_tags(), diag_tool=tool_sha())
    path = Path(out_dir) / f"{name}.json"
    if path.exists():
        old = R.load(path)
        if all((old.get("meta") or {}).get(k) == v for k, v in want.items()):
            print(f"  {name}: 같은 조건의 판이 있다 — 다시 쓴다 ({lv.path_text(path)})", flush=True)
            return old
    items = [(tag, job, bool(block)) for _, tag, job in R.make_items(info, spec, plan, False, 0.0, tag=name)]
    print(f"  {name}: {text}{' + 반사 밖 FLEE 막음' if block else ''} · {plan['use']} 시드 {plan['seeds'][0]}~{plan['seeds'][-1]} × 지역 "
          f"{len(info['regions'])} × {plan['steps']} 스텝 ({len(items)} 세계)", flush=True)
    t0 = time.perf_counter()
    rows = [None] * len(items)
    ex = ro.make_executor(min(int(workers), len(items)))
    if ex is None:
        for k, it in enumerate(items):
            rows[k] = D._diag_job(it)
    else:
        with ex:
            futs = {ex.submit(D._diag_job, it): k for k, it in enumerate(items)}
            for n, f in enumerate(as_completed(futs), 1):
                rows[futs[f]] = f.result()
                if n % 30 == 0 or n == len(items):
                    print(f"    {name} {n}/{len(items)} ({time.perf_counter() - t0:.0f} 초)", flush=True)
    res = dict(meta=dict(want, name=name, obs=spec["obs"], model_path=lv.path_text(spec["path"]), snapshot=R.SNAPSHOT.name,
                         wall_s=round(time.perf_counter() - t0, 1), workers=int(workers)),
               worlds=[r for _, r in rows])
    R.save(res, path)
    return res


# --------------------------------------------------------------------- #
# 셈
# --------------------------------------------------------------------- #

def check_world(w: dict) -> None:
    """감싼 셈 = 세계 기록 (시작 · 다시 도망) — 다르면 멈춘다."""
    d, f = w["diag"], lv.flight_of(w)
    st = sum(d["starts"].values())
    if not (st == d["world_started"] == int(f["started"]) and d["refled"] == d["world_refled"] == int(f["route"]["refled"])
            and sum(d["cells"].values()) == d["refled"] == sum(d["gap"])):
        raise RuntimeError(f"세계 (시드 {w['seed']}, {w['region']}) 의 감싼 셈이 도망 기록과 다르다: {d['starts']} {d['refled']} 대 "
                           f"{f['started']} {f['route']['refled']}")


def cat_of(key: str) -> str:
    kind, cause, circle, _route, _nc = key.split("|")
    if kind == "brain":
        return "da"
    return "ga" if (cause == "cover" or circle == "1") else "na"


def seed_parts(res: dict) -> dict:
    """시드 → 지역 셋 합: live(산 사슴-스텝), started, brain·reflex 시작, 다시 도망 칸(ga·na·da · ga_cover), none 길 도망, 결정 셈."""
    out: dict = {}
    for w in res["worlds"]:
        check_world(w)
        d, f = w["diag"], lv.flight_of(w)
        a = out.setdefault(int(w["seed"]), Counter())
        a["live"] += int(f["live_steps"])
        a["started"] += int(f["started"])
        a["brain"] += int(d["starts"].get("brain", 0))
        a["reflex"] += int(d["starts"].get("reflex", 0))
        a["refled"] += int(d["refled"])
        a["none"] += sum(int(v) for v in (f["route"]["by_route"].get("none") or {}).get("n", {}).values())
        a["flee_steps"] += int(f["flee_steps"])
        a["reflex_steps"] += int(f["reflex_steps"])
        for k, v in d["cells"].items():
            c = cat_of(k)
            a[c] += int(v)
            if c == "ga" and k.split("|")[1] == "cover":
                a["ga_cover"] += int(v)
            if c == "na" and k.split("|")[3] == "none":
                a["na_after_none"] += int(v)
        for k, v in d["dec"].items():
            a["dec_" + k] += int(v)
    return out


def paired_of(a: dict, b: dict, fn) -> dict:
    return re_.paired({s: float(fn(v)) for s, v in a.items()}, {s: float(fn(v)) for s, v in b.items()})


def pooled_cells(res: dict) -> Counter:
    c = Counter()
    for w in res["worlds"]:
        c.update({k: int(v) for k, v in w["diag"]["cells"].items()})
    return c


def compare_early_base(res: dict, path: Path) -> dict:
    """route0 다시 돌린 판 = 조기 점검 기준 판(runs/early_base.json, 탐침 — 궤적은 같다)인지: 세계마다 시작·다시 도망·쫓긴·숨음·잡힘·굶음·산."""
    if not path.exists():
        return dict(ok=None, why=f"{lv.path_text(path)} 이 없다")
    old = {(int(w["seed"]), w["region"]): w for w in R.load(path)["worlds"]}

    def key(w):
        f = w["flight"]
        return (int(f["started"]), int(f["route"]["refled"]), int(f["hide"]["chased"]), int(f["hide"]["hidden"]), int(w["caught"]),
                int(w["starved"]), int(w["alive"]))

    bad = []
    for w in res["worlds"]:
        k = (int(w["seed"]), w["region"])
        if k not in old or key(old[k]) != key(w):
            bad.append(k)
    return dict(ok=not bad and len(old) == len(res["worlds"]), worlds=len(res["worlds"]), bad=bad[:10])


def analyse(runs: dict, plan: dict) -> dict:
    """모델마다 칸 · route0 대비 짝 · GR/GF 나누기 · 판단."""
    base = runs["route0"]
    parts = {k: seed_parts(v) for k, v in runs.items()}
    seeds = sorted(parts["route0"])
    n = len(seeds)
    T = lv.t_crit(n - 1) if n >= 2 else float("nan")
    out: dict = dict(n=n, t_crit=T, seeds=[seeds[0], seeds[-1]], use=plan["use"], steps=plan["steps"], models={})
    for name, res in runs.items():
        p = parts[name]
        S = len(p)
        f, q = lv.flight_pooled(res), re_.pooled(res)
        row: dict = dict(
            label=LABEL[name],
            hide=lv.hide_pair(res, base, "hide"), caught_ratio=lv.hide_pair(res, base, "caught"),
            caught=re_.paired(re_.per_seed(res, "caught"), re_.per_seed(base, "caught")),
            starved=re_.paired(re_.per_seed(res, "starved"), re_.per_seed(base, "starved")),
            shelter=re_.paired(re_.per_seed(res, "shelter"), re_.per_seed(base, "shelter")),
            GF=lv.flight_rate_pair(res, base, "starts"), GV=lv.flight_rate_pair(res, base, "flee"), GC=lv.flight_rate_pair(res, base, "unsafe"),
            none=paired_of(p, parts["route0"], lambda x: x["none"]), brain_starts=paired_of(p, parts["route0"], lambda x: x["brain"]),
            pooled=dict(hide_share=f["hide_share"], chased=f["chased"], caught_share_chased=f["caught_share_chased"], started=f["started"],
                        caught=q["caught"], starved=q["starved"], alive=q["alive"], shelter=q["shelter"], beh=q["beh"],
                        self_flee_share=f["self_flee_share"]),
            dec={k[4:]: v / S for k, v in sum((Counter({kk: vv for kk, vv in x.items() if kk.startswith("dec_")}) for x in p.values()),
                                               Counter()).items()},
        )
        g = R.route_guards(res, base)
        row["GR"], row["GTr"] = g["GR_reflee"], g["GTr_truncated"]
        # GR 나누기 (시드당 수) 와 route0 대비 짝
        row["gr_cat"] = {c: paired_of(p, parts["route0"], lambda x, c=c: x[c]) for c in CATS + ("ga_cover", "na_after_none")}
        # GF 나누기 (1000 산 사슴-스텝당)
        rate = lambda k: (lambda x: 1000.0 * x[k] / x["live"] if x["live"] else 0.0)  # noqa: E731
        fresh = lambda x: 1000.0 * (x["reflex"] - x["ga"] - x["na"]) / x["live"] if x["live"] else 0.0  # noqa: E731
        row["gf_cat"] = dict(brain=paired_of(p, parts["route0"], rate("brain")), reflex_ga=paired_of(p, parts["route0"], rate("ga")),
                             reflex_na=paired_of(p, parts["route0"], rate("na")), reflex_fresh=paired_of(p, parts["route0"], fresh))
        cells = pooled_cells(res)
        sub_na, sub_ga, sub_ga_new = Counter(), Counter(), Counter()
        for k, v in cells.items():
            kind, cause, circle, route, nc = k.split("|")
            c = cat_of(k)
            if c == "na":
                sub_na[f"{cause} · 길 {route}"] += v
            elif c == "ga":
                sub_ga[f"{'cover' if cause == 'cover' else cause + ' (원 안)'} · 길 {route}"] += v
                sub_ga_new["새 도망 첫 스텝 끝 원 안" if nc == "1" else "원 밖"] += v
        gap = np.sum([w["diag"]["gap"] for w in res["worlds"]], 0)
        row["sub"] = dict(na={k: v / S for k, v in sub_na.most_common()}, ga={k: v / S for k, v in sub_ga.most_common()},
                          ga_new={k: v / S for k, v in sub_ga_new.items()},
                          gap_mean_s=float((gap * np.arange(len(gap))).sum() / gap.sum() * lv.STEP_S) if gap.sum() else float("nan"))
        out["models"][name] = row
    # 판단 (모듈 docstring — 실행 전에 적은 규칙)
    b = out["models"]["r6_block"]
    ok = lambda q: bool(q["n"] >= 2 and math.isfinite(q["t"]))  # noqa: E731
    gf_ok = ok(b["GF"]) and b["GF"]["t"] < T
    gr_ok = ok(b["GR"]) and b["GR"]["t"] < T
    hide_ok = ok(b["hide"]) and b["hide"]["diff"] > 0 and b["hide"]["t"] >= T
    gh_ok = ok(b["caught_ratio"]) and b["caught_ratio"]["t"] < T
    gn_ok = ok(b["caught"]) and b["caught"]["t"] < T
    ex = {c: b["gr_cat"][c]["diff"] for c in CATS}
    ex_tot = b["GR"]["diff"]
    main = max(CATS, key=lambda c: ex[c])
    ga_main = bool(ex_tot > 0 and ex["ga"] >= 0.5 * ex_tot)
    if gf_ok and gr_ok and hide_ok and gh_ok and gn_ok:
        decision, why = "GO", "막은 뒤 GF·GR 짝 t 가 모두 문턱 미만이고 숨음 비율 이득이 남는다(잡힘 비율·잡힌 몫도 문턱 미만)"
    elif not (gf_ok and gr_ok) and ga_main:
        decision, why = "ASK", "막은 뒤에도 GF 또는 GR 이 문턱 이상이고, GR 초과분의 절반 이상이 (가) 은신처 들락날락이다"
    else:
        bad = [k for k, v in (("GF", gf_ok), ("GR", gr_ok), ("숨음 비율 이득", hide_ok), ("잡힘 비율", gh_ok), ("잡힌 몫", gn_ok)) if not v]
        decision, why = "ASK", "애매함 — 걸린 칸: " + ", ".join(bad) + (f" (GR 초과분의 가장 큰 몫: {CAT_KO[main]})" if ex_tot > 0 else
                                                                         " (GR 은 route0 보다 많지 않다)")
    out["decision"] = dict(decision=decision, why=why, gf_ok=gf_ok, gr_ok=gr_ok, hide_ok=hide_ok, gh_ok=gh_ok, gn_ok=gn_ok,
                           gr_excess=ex_tot, gr_excess_by=ex, ga_main=ga_main, main=main)
    # 막기 효과 (r6_block − r6, 보고만)
    out["block_vs_r6"] = dict(hide=lv.hide_pair(runs["r6_block"], runs["r6"], "hide"), caught_ratio=lv.hide_pair(runs["r6_block"], runs["r6"], "caught"),
                              GF=lv.flight_rate_pair(runs["r6_block"], runs["r6"], "starts"), GR=R.route_guards(runs["r6_block"], runs["r6"])["GR_reflee"])
    return out


# --------------------------------------------------------------------- #
# 글
# --------------------------------------------------------------------- #

def _t(q) -> str:
    return lv.tfmt(q["t"])


def _cell(q: dict, kind: str, base: bool) -> str:
    """kind: 'pct'(몫 → %, 차이 %p) · 'num'(소수 4) · 'cnt'(소수 1)."""
    if kind == "pct":
        v = f"{q['a'] * 100:.2f}%"
        d = f"{q['diff'] * 100:+.2f}%p"
    elif kind == "num":
        v, d = f"{q['a']:.4f}", f"{q['diff']:+.4f}"
    else:
        v, d = f"{q['a']:.1f}", f"{q['diff']:+.1f}"
    return v if base else f"{v} ({d}, t {_t(q)})"


def fmt(an: dict, meta: dict) -> str:
    M = an["models"]
    T = an["t_crit"]
    order = [k for k, _, _ in MODELS]
    d = an["decision"]
    b = M["r6_block"]
    L = ["# R6 판정 뒤 진단 — 반사 밖 두뇌 FLEE 막기 (보고만)", "",
         "**판정 뒤 진단, 보고만이다. R6 판정 결론(기각)은 그대로다.** 재학습 없이 R6 고른 두뇌에서 '반사 밖 두뇌의 FLEE 선택'만 평가 때 막아 보았다.", "",
         "## 결론 먼저", ""]
    L += conclusion_lines(an)
    L += ["", "## 어떻게 쟀나", "",
          f"- 세계: `r6_eval.py` 의 N 세계(스냅숏 거울 + 늑대 포만 끔, {an['steps']} 스텝 — 판정 N 과 같은 길이·설정), 점검 시드 {an['seeds'][0]}~{an['seeds'][1]} × "
          f"지역 셋({an['n']} 시드 × 3 = {an['n'] * 3} 세계). 판정 시드 37000~37099 · 고르기 시드 37100~37119 는 쓰지 않았다.",
          "- 막기: 결정 스텝이고 덮기(도주 반사 · 웅크림)가 아닌 사슴의 마스크에서 FLEE 칸만 껐다. 마스크는 망 입력이 아니라서 같은 로짓에서 FLEE 를 뺀 argmax 다. "
          "반사 도주 중 길 고르기(RUN·SHELTER)는 그대로다. 막기는 `diag.py` 의 정책 껍질 안에서만 했다(기본 동작 · 기존 파일 그대로).",
          "- 짝 t: 같은 시드의 route0 과의 차이(시드마다 지역 셋 합) — 판정과 같은 셈 함수(`lv.hide_pair` · `lv.flight_rate_pair` · `r6_eval.route_guards`). "
          f"시드 {an['n']} 이면 문턱 t_crit({an['n'] - 1}) = {T:.3f}.",
          "- GR 나누기: 세계의 도망 기록을 감싸 다시 시작한 도망마다 (다) 새 도망이 두뇌 FLEE 로 시작 → (가) 반사로 시작했고 지난 도망이 은신처로 끝남"
          "(끝 까닭 cover 이거나 끝 위치가 은신처 원 안) → (나) 그 밖, 차례로 하나에 넣었다. 감싼 셈의 합은 세계 기록(refled · started)과 세계마다 같았다.",
          f"- 확인: route0 을 다시 돌린 판이 조기 점검 기준 판(`runs/early_base.json`)과 세계마다 같은가 — {meta.get('early_base')}.", "",
          "## 1. 견줌 (시드 평균, 괄호 = route0 대비 차이 · 짝 t)", "",
          "| 칸 | " + " | ".join(M[k]["label"] for k in order) + " |", "|---|" + "---|" * len(order)]
    rows = (("숨음 비율 (쫓긴 도망 가운데 숨어 10 초 안 안 잡힘)", "hide", "pct"), ("잡힘 비율 (쫓긴 도망 가운데)", "caught_ratio", "pct"),
            ("잡힌 몫 (사슴 가운데)", "caught", "pct"), ("GF (도망 시작 / 1000 산 사슴-스텝)", "GF", "num"),
            ("GR (5 초 안 다시 도망, 시드당)", "GR", "cnt"), ("반사 밖 두뇌 FLEE 도망 (길 none, 시드당)", "none", "cnt"),
            ("두뇌 FLEE 로 시작한 도망 (시드당)", "brain_starts", "cnt"))
    for title, key, kind in rows:
        L.append(f"| {title} | " + " | ".join(_cell(M[k][key], kind, k == "route0") for k in order) + " |")
    L += ["", f"- 판정 문턱 {T:.3f} (시드 {an['n']}). GF·GR 은 짝 t 가 +{T:.3f} 미만이어야 지킴 통과, 숨음 비율은 +{T:.3f} 이상이어야 1차 통과 꼴이다.",
          f"- 막기 효과(r6_block − r6 짝): 숨음 비율 {an['block_vs_r6']['hide']['diff'] * 100:+.2f}%p (t {_t(an['block_vs_r6']['hide'])}) · 잡힘 비율 "
          f"{an['block_vs_r6']['caught_ratio']['diff'] * 100:+.2f}%p (t {_t(an['block_vs_r6']['caught_ratio'])}) · GF {an['block_vs_r6']['GF']['diff']:+.4f} "
          f"(t {_t(an['block_vs_r6']['GF'])}) · GR {an['block_vs_r6']['GR']['diff']:+.1f} (t {_t(an['block_vs_r6']['GR'])})", "",
          "## 2. GR 나누기 (시드당 다시 도망 수, 괄호 = route0 대비 차이 · 짝 t)", "",
          "| 칸 | " + " | ".join(M[k]["label"] for k in order) + " |", "|---|" + "---|" * len(order)]
    L.append("| GR 전체 | " + " | ".join(_cell(M[k]["GR"], "cnt", k == "route0") for k in order) + " |")
    for c in CATS:
        L.append(f"| {CAT_KO[c]} | " + " | ".join(_cell(M[k]["gr_cat"][c], "cnt", k == "route0") for k in order) + " |")
    L.append("| └ (가) 가운데 지난 끝 까닭 cover | " + " | ".join(_cell(M[k]["gr_cat"]["ga_cover"], "cnt", k == "route0") for k in order) + " |")
    L.append("| └ (나) 가운데 지난 도망이 두뇌 FLEE 도망(길 none) | " + " | ".join(_cell(M[k]["gr_cat"]["na_after_none"], "cnt", k == "route0")
                                                              for k in order) + " |")
    L.append("| 다시 도망 사이 평균 틈 (초) | " + " | ".join(f"{M[k]['sub']['gap_mean_s']:.2f}" for k in order) + " |")
    ex, tot = d["gr_excess_by"], d["gr_excess"]
    L += ["", f"- R6 s1 + 막음의 GR 초과분(route0 대비 시드 평균) {tot:+.1f} = " + " + ".join(f"{CAT_KO[c]} {ex[c]:+.1f}" for c in CATS)
          + (f" — (가) 몫 {ex['ga'] / tot * 100:.0f}%" if tot > 0 else ""),
          f"- R6 s1 그대로의 GR 초과분 {M['r6']['GR']['diff']:+.1f} = " + " + ".join(f"{CAT_KO[c]} {M['r6']['gr_cat'][c]['diff']:+.1f}" for c in CATS), ""]
    L += ["## 3. GF 나누기 (1000 산 사슴-스텝당 시작한 도망, 괄호 = route0 대비 차이 · 짝 t)", "",
          "| 칸 | " + " | ".join(M[k]["label"] for k in order) + " |", "|---|" + "---|" * len(order)]
    L.append("| GF 전체 | " + " | ".join(_cell(M[k]["GF"], "num", k == "route0") for k in order) + " |")
    for key, title in (("brain", "두뇌 FLEE 로 시작"), ("reflex_ga", "반사 시작 · (가) 다시 도망"), ("reflex_na", "반사 시작 · (나) 다시 도망"),
                       ("reflex_fresh", "반사 시작 · 5 초 밖 새 도망")):
        L.append(f"| {title} | " + " | ".join(_cell(M[k]["gf_cat"][key], "num", k == "route0") for k in order) + " |")
    L += ["", "## 4. 다시 도망 속살 (시드당, 판 전체 합 ÷ 시드)", ""]
    for k in order:
        s = M[k]["sub"]
        ga = " · ".join(f"{x} {v:.1f}" for x, v in list(s["ga"].items())[:5]) or "없음"
        na = " · ".join(f"{x} {v:.1f}" for x, v in list(s["na"].items())[:6]) or "없음"
        gn = " · ".join(f"{x} {v:.1f}" for x, v in s["ga_new"].items()) or "없음"
        L += [f"- {M[k]['label']}", f"  - (가) 지난 도망 끝 까닭 · 길: {ga}", f"  - (가) 새 도망 시작 위치: {gn}", f"  - (나) 지난 도망 끝 까닭 · 길: {na}"]
    L += ["", "## 5. 보고만 (그 밖의 칸)", "",
          "| 칸 | " + " | ".join(M[k]["label"] for k in order) + " |", "|---|" + "---|" * len(order)]
    for title, key, kind in (("굶은 몫", "starved", "pct"), ("은신처 안 몫 (산 사슴-스텝)", "shelter", "pct"), ("GV 실행 FLEE 몫", "GV", "pct"),
                             ("GC 위험하게 끝난 도망 몫", "GC", "pct"), ("GTr 잘린 도망 (시드당)", "GTr", "cnt")):
        L.append(f"| {title} | " + " | ".join(_cell(M[k][key], kind, k == "route0") for k in order) + " |")
    L.append("| 행동 몫 먹기 · 도망 · 숨기 (판 합) | " + " | ".join(
        f"{M[k]['pooled']['beh']['graze'] * 100:.1f}% · {M[k]['pooled']['beh']['flee'] * 100:.1f}% · {M[k]['pooled']['beh']['hide'] * 100:.1f}%" for k in order) + " |")
    L.append("| 반사 밖 결정 사슴-스텝 (시드당) · 그 가운데 argmax FLEE | " + " | ".join(
        f"{M[k]['dec'].get('free', 0):.0f} · {M[k]['dec'].get('free_flee', 0):.1f}" for k in order) + " |")
    rb = {x[5:]: v for x, v in b["dec"].items() if x.startswith("repl_")}
    L += ["", f"- 막음 판에서 막힌 선택 시드당 {b['dec'].get('blocked', 0):.1f} 번, 대신 고른 행동: " + (" · ".join(f"{x} {v:.1f}" for x, v in rb.items()) or "없음"),
          "", "## 6. 판단 (실행 전에 `diag.py` 머리에 적은 규칙)", "",
          f"- **{d['decision']}** — {d['why']}.",
          f"- GF 짝 t {_t(b['GF'])} ({'문턱 미만' if d['gf_ok'] else '문턱 이상'}) · GR 짝 t {_t(b['GR'])} ({'문턱 미만' if d['gr_ok'] else '문턱 이상'}) · "
          f"숨음 비율 {b['hide']['diff'] * 100:+.2f}%p t {_t(b['hide'])} ({'이득 남음' if d['hide_ok'] else '이득 문턱 미달'}) · 잡힘 비율 t {_t(b['caught_ratio'])} · "
          f"잡힌 몫 t {_t(b['caught'])}.",
          "- 판정 결론(기각)은 바꾸지 않는다. R7 로 가려면 새 사전 등록과 새 시드가 필요하다(이 진단의 점검 시드는 이미 썼다).", "",
          f"- 판 파일: `results/v3/r6/diag/runs/` (git 밖). 도구 `diag.py` sha256 앞 16 `{meta.get('tool')}`. 걸린 시간 {meta.get('wall')}."]
    return "\n".join(L) + "\n"


def conclusion_lines(an: dict) -> list[str]:
    M, d, T = an["models"], an["decision"], an["t_crit"]
    b, r, z = M["r6_block"], M["r6"], M["route0"]
    ex = d["gr_excess_by"]
    L = [f"- **판단: {d['decision']}** — {d['why']}."]
    if d["decision"] == "GO":
        L.append("- 쉽게 말해: 늑대가 쫓지 않는데 두뇌가 스스로 툭툭 뛰던 것만 막으면, 도망을 너무 자주 시작하던 것(GF)과 끝나자마자 또 뛰던 것(GR)이 지금 두뇌 "
                 "수준으로 돌아오고, 은신처에 숨는 비율 이득은 그대로 남는다.")
    L += [f"- R6 두뇌에서 반사 밖 FLEE 만 막자: 숨음 비율 {b['hide']['a'] * 100:.1f}% (route0 {z['hide']['a'] * 100:.1f}%, R6 그대로 {r['hide']['a'] * 100:.1f}%), "
         f"도망 시작 GF {b['GF']['a']:.3f} (route0 {z['GF']['a']:.3f}, R6 그대로 {r['GF']['a']:.3f} — 짝 t {_t(b['GF'])}), "
         f"5 초 안 다시 도망 GR 시드당 {b['GR']['a']:.0f} 번 (route0 {z['GR']['a']:.0f}, R6 그대로 {r['GR']['a']:.0f} — 짝 t {_t(b['GR'])}). 문턱은 {T:.3f}.",
         f"- 잡힘: 쫓긴 도망 가운데 잡힘 {b['caught_ratio']['a'] * 100:.1f}% (route0 {z['caught_ratio']['a'] * 100:.1f}%, t {_t(b['caught_ratio'])}), "
         f"사슴 가운데 잡힌 몫 {b['caught']['a'] * 100:.1f}% (route0 {z['caught']['a'] * 100:.1f}%, t {_t(b['caught'])}).",
         (f"- 남은 GR 초과분(route0 대비) 시드당 {d['gr_excess']:+.1f} 번의 원인: (가) 은신처로 끝난 도망 뒤 다시 도망 {ex['ga']:+.1f} · (나) 그 밖 끝 까닭 뒤 "
          f"{ex['na']:+.1f} · (다) 두뇌 스스로 뛰기 {ex['da']:+.1f}." if d["gr_excess"] > 0 else
          f"- GR 초과분이 없다(route0 대비 시드당 {d['gr_excess']:+.1f} 번 — (가) {ex['ga']:+.1f} · (나) {ex['na']:+.1f} · (다) {ex['da']:+.1f}).")]
    # 주의 (보고만 — 판단 규칙과 무관한 글)
    u = M["rule"]
    rb = {x[5:]: v for x, v in b["dec"].items() if x.startswith("repl_")}
    L += ["", "주의 (판정이 아니다):",
          "- 평가 때만 막은 값이다(재학습 없음). R7 은 이 막기를 마스크로 넣고 다시 배우므로 값이 달라질 수 있다 — 새 사전 등록 · 새 시드로 다시 판정해야 한다.",
          f"- 점검 시드 {an['seeds'][0]}~{an['seeds'][1]}(조기 점검에서 이미 쓴 시드 {an['n']} 개)로 본 값이다. 판정 · 고르기 시드는 쓰지 않았다.",
          f"- 은신처 들락날락((가))은 지금 두뇌에서도 GR 의 대부분이다(route0 시드당 {z['gr_cat']['ga']['a']:.0f} / {z['GR']['a']:.0f}). 막은 R6 의 (가)는 route0 와 "
          f"비슷하다({ex['ga']:+.1f}, t {_t(b['gr_cat']['ga'])}). '늘 SHELTER' 규칙은 (가)가 크게 늘어(+{u['gr_cat']['ga']['diff']:.1f}, "
          f"t {_t(u['gr_cat']['ga'])}) GR 이 걸린다(t {_t(u['GR'])}).",
          f"- 막힌 선택은 시드당 {b['dec'].get('blocked', 0):.0f} 번이고 대신 " + " · ".join(f"{x} {v:.0f}" for x, v in sorted(rb.items(), key=lambda kv: -kv[1]))
          + f" 번을 골랐다. 은신처 안 몫(산 사슴-스텝)은 route0 {z['shelter']['a'] * 100:.1f}% → {b['shelter']['a'] * 100:.1f}% (R6 그대로 "
          f"{r['shelter']['a'] * 100:.1f}%) — 보고만."]
    return L


# --------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--workers", type=int, default=lv.default_workers())
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--smoke", default=None, help="도구 확인: 스모크 시드(32080~32099 안) — diag.md·diag.json 을 쓰지 않는다")
    ap.add_argument("--smoke-steps", type=int, default=300)
    a = ap.parse_args(argv)
    plan = R.smoke_plan("check", R.parse_seeds(a.smoke), a.smoke_steps) if a.smoke else R.use_plan("check")
    if not a.smoke and plan["seeds"] != list(range(37120, 37140)):
        raise SystemExit("진단은 점검 시드 37120~37139 만 쓴다")
    info = R.prepare_info()                         # runs/world (스냅숏 변환 — r6_eval 판과 같은 세계)
    t0 = time.perf_counter()
    runs = {name: run_model(info, name, text, block, plan, a.workers, a.out_dir) for name, text, block in MODELS}
    eb = compare_early_base(runs["route0"], R.OUT / "early_base.json") if not a.smoke else dict(ok=None, why="스모크")
    an = analyse(runs, plan)
    wall = sum(float(r["meta"].get("wall_s", 0.0)) for r in runs.values())
    eb_txt = ("같음 (60 세계 모두 시작·다시 도망·쫓긴·숨음·잡힘·굶음·산이 같다)" if eb.get("ok") else
              (f"다름 {eb.get('bad')}" if eb.get("ok") is False else f"보지 않음 ({eb.get('why')})"))
    meta = dict(tool=tool_sha(), wall=f"판 넷 합 {wall / 60:.1f} 분 (워커 {a.workers})", early_base=eb_txt,
                runs={k: dict(name=v["meta"]["name"], model=v["meta"]["model"], model_sha1=v["meta"]["model_sha1"], block=v["meta"]["block"],
                              sets=v["meta"]["sets"], wall_s=v["meta"]["wall_s"], code=v["meta"]["code"]) for k, v in runs.items()})
    text = fmt(an, meta)
    print(text)
    if eb.get("ok") is False:
        raise SystemExit(f"route0 다시 돌린 판이 조기 점검 기준 판과 다르다: {eb}")
    if not a.smoke:
        MD.write_text(text, encoding="utf-8")
        JS.write_text(json.dumps(lv.jsonable(dict(meta=meta, analysis=an)), ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
        print(f"→ {lv.path_text(MD)} · {lv.path_text(JS)} ({(time.perf_counter() - t0) / 60:.1f} 분)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
