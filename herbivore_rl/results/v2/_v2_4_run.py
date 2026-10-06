"""v2.4 낮밤 탐침·γ 재비교·짧은 확인 실행기 (`results/v2/v2_4/PREREG.md`, `MEMO.md`, `confirm/PREREG.md`, 학습 전 작성).

    # herbivore_rl/ 에서
    python results/v2/_v2_4_run.py train --stage probe --concurrency 6     # v2.4 × γ{0.995, 0.998} × 시드 20~22
    python results/v2/_v2_4_run.py g27                                     # #27 γ 재비교(G_0.998, 탐색 시드)
    python results/v2/_v2_4_run.py eval --stage probe                      # 탐침 평가(탐색 시드, 두 모드, 대조군)
    python results/v2/_v2_4_run.py garm                                    # (iv) 기준: S1-a G 팔 24모델(결정, 낮 구간 B1)
    python results/v2/_v2_4_run.py judge --stage probe                     # 탐침 판정 → v2_4/probe/judge.json·md
    python results/v2/_v2_4_run.py train --stage resp                      # 탐침 실패 때 대응 1회(시작 상태 유도)
    python results/v2/_v2_4_run.py train --stage confirm                   # 짧은 확인 시드 40~42
    python results/v2/_v2_4_run.py eval --stage confirm                    # 평가 시드(판정)·탐색 시드(출시 선택)
    python results/v2/_v2_4_run.py judge --stage confirm                   # 짧은 확인 판정과 출시 모델

판정 G_γ 는 γ 0.9916661555611042(끝 600스텝 제외), 세계는 configs/v2_4_on.yaml(낮 고정 세계 없음). 학습 γ 는 S1-a
레시피 0.995 와 #27 후보 0.998 이다. 규칙은 사전 등록 문서 그대로다.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

OUT = ROOT / "results" / "v2" / "v2_4"
C2DIR = OUT / "c2"              # v2.4 판정 세계에서 찾은 C2·C2-seg 상수(변형 세계에서도 이 상수를 그 세계로 잰다)
# 변형(--variant): base = v2.4, b = v2.4b(휴식 할인 은신처 안만, MEMO 변경 기록 10-06 19:00). 출력·상태·이름이 따로다
PREFIX, TRAIN_CFG, ON_CFG = "v2_4", "configs/v2_4.yaml", "configs/v2_4_on.yaml"
CONFIRM_SEEDS = (40, 41, 42)


def set_variant(v: str) -> None:
    global OUT, PREFIX, TRAIN_CFG, ON_CFG, C2DIR, CONFIRM_SEEDS
    if v == "s":        # v2.4s 포식자 밤잠(10-07 사용자 결정 A안, results/v2/v2_4/s/PREREG.md). C2 는 v2.4s 세계에서 새로 찾는다
        OUT = ROOT / "results" / "v2" / "v2_4" / "s"
        PREFIX, TRAIN_CFG, ON_CFG = "v2_4s", "configs/v2_4s.yaml", "configs/v2_4s_on.yaml"
        C2DIR = OUT / "c2"
        CONFIRM_SEEDS = (43, 44, 45)
    if v in ("b", "s"):
        if v == "b":
            OUT = ROOT / "results" / "v2" / "v2_4" / "b"
            PREFIX, TRAIN_CFG, ON_CFG = "v2_4b", "configs/v2_4b.yaml", "configs/v2_4b_on.yaml"
        st = load_json(OUT / "state.json", {})
        if "gamma_sel" not in st:          # #27 은 v2.4 에서 정했다(γ 0.995)
            st["gamma_sel"] = "995"
            save_json(OUT / "state.json", st)
CKPT = ROOT / "ckpt" / "v2"
GAMMA = 0.9916661555611042
EXPLORE_SEEDS = list(range(12000, 12040))
EVAL_SEEDS = list(range(10000, 10020))
T_CRIT_40, T_CRIT_20 = 2.023, 2.093
GAMMAS = {"995": 0.995, "998": 0.998}
G998 = dict(gamma=0.998, steps=10000, head=500, tail=2500)
FIX_MODEL = "s1a_g_s58"
MODES = {"det": {}, "hold": {"mode": "hold", "hold_k": 24}}


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def load_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def state() -> dict:
    """사전 등록이 정한 값(γ_sel, 모드, 최종 설정)을 담은 상태 파일. 판정 단계가 채운다."""
    return load_json(OUT / "state.json", {})


def final_config(stage: str) -> str:
    st = state()
    if stage == "resp":
        return "configs/v2_4_ind.yaml"
    return st.get("confirm_config", TRAIN_CFG) if stage == "confirm" else TRAIN_CFG


def jobs(stage: str) -> list[dict]:
    if stage == "probe":
        gs = list(GAMMAS) if PREFIX == "v2_4" else [state().get("gamma_sel", "995")]
        return [{"stage": "probe", "g": g, "seed": s, "name": f"{PREFIX}p_g{g}_s{s}", "config": TRAIN_CFG,
                 "save_at": ["2000000", "5000000", "10000000"]} for s in (20, 21, 22) for g in gs]
    g = state().get("gamma_sel")
    if g is None:
        raise SystemExit("state.json 에 gamma_sel 이 없다 — g27 판정 뒤에 돌린다")
    if stage == "resp":
        if PREFIX == "v2_4s":   # v2.4s 대응: v2.1 출시 모델 가중치로 시작(s/PREREG.md 2절, s/widen_init.py)
            return [{"stage": "resp", "g": g, "seed": s, "name": f"{PREFIX}r_g{g}_s{s}", "config": TRAIN_CFG,
                     "save_at": ["2000000", "5000000", "10000000"],
                     "extra": ["--init", "ckpt/v2/v2_4s_init_from_s1a_g_s58.zip"]} for s in (20, 21, 22)]
        return [{"stage": "resp", "g": g, "seed": s, "name": f"{PREFIX}r_g{g}_s{s}", "config": final_config("resp"),
                 "save_at": ["2000000", "5000000", "10000000"]} for s in (20, 21, 22)]
    if stage == "confirm":
        return [{"stage": "confirm", "g": g, "seed": s, "name": f"{PREFIX}c_g{g}_s{s}", "config": final_config("confirm"),
                 "save_at": ["5000000", "10000000"]} for s in CONFIRM_SEEDS]
    if stage == "diag":
        return [{"stage": "diag", "g": g, "seed": s, "name": f"v2_4d_rest0_s{s}",
                 "config": "results/v2/v2_4/diag/v2_4_rest0.yaml", "save_at": ["5000000", "10000000"]}
                for s in (20, 21, 22)]
    raise SystemExit(f"모르는 단계 {stage}")


# --------------------------------------------------------------------- #
# train
# --------------------------------------------------------------------- #


def cmd_train(a) -> int:
    logs = OUT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    pool = jobs(a.stage)
    todo = [j for j in pool if not (CKPT / f"{j['name']}.zip").exists()]
    print(f"학습할 것 {len(todo)}개 (동시 {a.concurrency})", flush=True)
    status_path = OUT / f"train_status_{a.stage}.json"
    status = load_json(status_path, {"runs": {}})
    status["started"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    running, t0 = [], time.time()
    while todo or running:
        while todo and len(running) < a.concurrency:
            j = todo.pop(0)
            cmd = [sys.executable, "train_v2.py", "--config", j["config"], "--steps", "20000000", "--seed", str(j["seed"]),
                   "--gamma", repr(GAMMAS[j["g"]]), "--run-name", j["name"], "--save-at", *j["save_at"],
                   "--probe-every", "1000000", "--threads", "1", *j.get("extra", [])]
            log = open(logs / f"train_{j['name']}.log", "w", encoding="utf-8")
            running.append((j, subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT), log))
            status["runs"][j["name"]] = {"stage": j["stage"], "cmd": " ".join(cmd[1:]), "returncode": None}
        time.sleep(a.poll)
        still = []
        for j, p, log in running:
            rc = p.poll()
            if rc is None:
                still.append((j, p, log))
                continue
            log.close()
            status["runs"][j["name"]]["returncode"] = rc
            print(f"[{(time.time() - t0) / 60:5.1f}분] 끝 {j['name']} (rc {rc}), 남은 {len(todo)}", flush=True)
        running = still
        save_json(status_path, status)
    status["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_json(status_path, status)
    bad = [n for n, r in status["runs"].items() if r["returncode"] != 0]
    print("학습 끝" + (f" — 실패: {bad}" if bad else ""), flush=True)
    return 1 if bad else 0


# --------------------------------------------------------------------- #
# 정책 스펙
# --------------------------------------------------------------------- #


def learned(name: str, mode: str = "det") -> dict:
    return {"kind": "learned", "model": str((CKPT / f"{name}.zip").resolve()), **MODES[mode]}


def cond_specs(name: str, mode: str, cfg) -> dict:
    """모델 하나의 대조 조건: C0, C4-phase(관측 두 칸 1·1), C1′(같은 스텝 개체끼리 행동 순열), C4-energy 밤 구간판
    (밤 구간 개체의 energy 관측을 ENERGY_FIX 로 둔다 — 고정 정책 s1a_g_s58 의 v2.4 판정 세계 밤 구간 energy 관측 평균
    0.540(보정 시드 20000~20004 × 5000스텝, 10-06 사전 측정). MEMO 2절)."""
    import daynight_v2 as dnv

    c0 = learned(name, mode)
    return {"C0": c0, "C4phase": dnv.c4_phase(c0, cfg),
            "C1p": dnv.add_wrap(c0, {"kind": "act_permute"}),
            "C4en": dnv.add_wrap(c0, dnv.rule_wrap(cfg, factory="night_energy_fix", value=ENERGY_FIX))}


ENERGY_FIX = 0.54


def _sha(name):
    from diagnose_v2 import model_fingerprint

    return model_fingerprint(CKPT / f"{name}.zip")


def run_conds(cfg, todo: list[tuple[str, dict]], seeds, steps, path: Path, workers: int, *, gamma=GAMMA, tail=None,
              head=0, chunk=6) -> dict:
    """(키, 스펙) 목록을 돌려 path 에 키별 행을 쌓는다(이미 있는 키는 건너뛴다)."""
    from diagnose_v2 import clean
    from env_v2.rollout import make_executor, public_row, run_specs

    d = load_json(path, {"rows": {}})
    todo = [(k, s) for k, s in todo if k not in d["rows"]]
    print(f"{path.name}: 돌릴 조건 {len(todo)}개", flush=True)
    ex = make_executor(workers)
    try:
        for i in range(0, len(todo), chunk):
            part = dict(todo[i:i + chunk])
            res = run_specs(cfg, part, seeds, steps, gamma=gamma, tail=tail, head=head, executor=ex)
            for k in part:
                d["rows"][k] = [clean(public_row(r)) for r in res[k]]
            d["meta"] = dict(seeds=[seeds[0], seeds[-1]], steps=steps, gamma=gamma, tail=tail, head=head)
            save_json(path, d)
            print(f"  {min(i + chunk, len(todo))}/{len(todo)}", flush=True)
    finally:
        if ex is not None:
            ex.shutdown()
    return d


def on_cfg():
    from env_v2.config import load_v2_config

    return load_v2_config(ROOT / state().get("on_config", ON_CFG))


def models(stage: str) -> list[str]:
    st = state()
    if stage == "probe":
        g = st.get("gamma_sel")
        gs = [g] if g else list(GAMMAS)
        return [f"{PREFIX}p_g{g}_s{s}" for g in gs for s in (20, 21, 22) if (CKPT / f"{PREFIX}p_g{g}_s{s}.zip").exists()]
    return [j["name"] for j in jobs(stage) if (CKPT / f"{j['name']}.zip").exists()]


# --------------------------------------------------------------------- #
# #27 γ 재비교
# --------------------------------------------------------------------- #


def cmd_g27(a) -> int:
    cfg = on_cfg()
    names = [f"v2_4p_g{g}_s{s}" for g in GAMMAS for s in (20, 21, 22)]
    missing = [n for n in names if not (CKPT / f"{n}.zip").exists()]
    if missing:
        raise SystemExit(f"모델이 없다: {missing}")
    path = OUT / "g27" / "rows.json"
    run_conds(cfg, [(n, learned(n, "det")) for n in names], EXPLORE_SEEDS, G998["steps"], path, a.workers,
              gamma=G998["gamma"], tail=G998["tail"], head=G998["head"])
    d = load_json(path)
    per = {g: np.array([[r["g_gamma"] for r in d["rows"][f"v2_4p_g{g}_s{s}"]] for s in (20, 21, 22)]) for g in GAMMAS}
    arm = {g: v.mean(0) for g, v in per.items()}                     # 탐색 시드별 팔 평균
    best = max(arm, key=lambda g: arm[g].mean())
    rng = np.random.default_rng(0)
    out = {"arms": {g: dict(mean=float(v.mean()), per_model=[float(x) for x in per[g].mean(1)]) for g, v in arm.items()},
           "best": best, "compare": {}}
    for g in GAMMAS:
        if g == best:
            continue
        dlt = arm[best] - arm[g]
        sd = float(dlt.std(ddof=1))
        t = float(dlt.mean() / (sd / math.sqrt(len(dlt))))
        boots = []
        for _ in range(2000):
            si = rng.integers(0, len(EXPLORE_SEEDS), len(EXPLORE_SEEDS))
            mb = per[best][rng.integers(0, 3, 3)][:, si].mean()
            mg = per[g][rng.integers(0, 3, 3)][:, si].mean()
            boots.append(mb - mg)
        ci = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
        sig = abs(t) > T_CRIT_40 and (ci[0] > 0 or ci[1] < 0)
        out["compare"][g] = dict(diff=float(dlt.mean()), t=t, ci95=ci, sig_both=bool(sig))
    # 고른 γ: 최고값과 유의하게 다르지 않은(두 층 모두 유의해야 '다름') 가장 작은 γ
    ok = [g for g in GAMMAS if g == best or not out["compare"][g]["sig_both"]]
    sel = min(ok, key=lambda g: GAMMAS[g])
    out["gamma_sel"] = sel
    out["rule"] = ("G_0.998(탐색 시드 40 × 10000스텝, 앞 500·끝 2500 제외, 결정)이 최고 팔과 유의하게 다르지 않은 가장 작은 γ. "
                   "'다름' = 짝 t |t| > 2.023 이고 층화 부트스트랩 95% CI 가 0 을 뺀다(둘 다)")
    save_json(OUT / "g27" / "judge.json", out)
    st = state()
    st["gamma_sel"] = sel
    save_json(OUT / "state.json", st)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


# --------------------------------------------------------------------- #
# 탐침·확인 평가
# --------------------------------------------------------------------- #


def cmd_eval(a) -> int:
    cfg = on_cfg()
    st = state()
    if a.stage == "probe":
        names = models("probe") if st.get("gamma_sel") else [f"v2_4p_g{g}_s{s}" for g in GAMMAS for s in (20, 21, 22)]
        todo = []
        for n in names:
            sha = _sha(n)[:12]
            for mode in MODES:
                for c, spec in cond_specs(n, mode, cfg).items():
                    todo.append((f"{n}|{sha}|{mode}|{c}", spec))
        run_conds(cfg, todo, EXPLORE_SEEDS, 5000, OUT / "probe" / "rows.json", a.workers)
        arm_level(cfg, EXPLORE_SEEDS, OUT / "probe" / "arm_rows.json", a.workers)
    elif a.stage in ("resp", "confirm_explore", "diag"):
        stage = {"resp": "resp", "diag": "diag"}.get(a.stage, "confirm")
        todo = []
        for n in models(stage):
            sha = _sha(n)[:12]
            mode_list = list(MODES) if stage == "resp" else [st["mode"]]           # diag 는 고른 모드만
            for mode in mode_list:
                for c, spec in cond_specs(n, mode, cfg).items():
                    todo.append((f"{n}|{sha}|{mode}|{c}", spec))
        run_conds(cfg, todo, EXPLORE_SEEDS, 5000, OUT / "probe" / "rows.json", a.workers)
    elif a.stage == "confirm":
        mode = st["mode"]
        todo = []
        for n in models("confirm"):
            sha = _sha(n)[:12]
            for c, spec in cond_specs(n, mode, cfg).items():
                todo.append((f"{n}|{sha}|{mode}|{c}", spec))
        run_conds(cfg, todo, EVAL_SEEDS, 5000, OUT / "confirm" / "rows.json", a.workers)
        arm_level(cfg, EVAL_SEEDS, OUT / "confirm" / "arm_rows.json", a.workers)
    return 0


def arm_level(cfg, seeds, path: Path, workers: int) -> None:
    """팔 단위 조건: C2(v2.4 세계 최적 상수), C2-seg 위상판, 덧씌우기 기준선(s1a_g_s58 결정 + 밤 규칙)."""
    import daynight_v2 as dnv

    todo = []
    c2 = load_json(C2DIR / "constsearch.json")
    if c2:
        todo.append(("C2", {"kind": "fixed", "action": c2["best"]}))
    seg = load_json(C2DIR / "constsearch_seg.json")
    if seg:
        todo.append(("C2seg", {"policy": {"kind": "fixed", "action": seg["base_action"]},
                               "wrap": [{"kind": "seg_const", "bins": seg["bins"], "dims": seg["dims"],
                                         "table": [x for row in seg["best_table"] for x in row]}]}))
    fix = dnv.take7(learned(FIX_MODEL, "det"))
    todo.append(("FIX", fix))
    todo.append(("OVL", dnv.add_wrap(fix, dnv.rule_wrap(cfg))))
    run_conds(cfg, todo, seeds, 5000, path, workers)


def cmd_garm(a) -> int:
    """(iv) 기준: S1-a G 팔(학습 γ 0.995 v2.1) 24모델을 v2.4 판정 세계·탐색 시드·결정 모드로 잰다(관측 앞 7칸)."""
    import daynight_v2 as dnv

    cfg = on_cfg()
    todo = [(f"s1a_g_s{s}", dnv.take7(learned(f"s1a_g_s{s}", "det"))) for s in range(50, 74)]
    run_conds(cfg, todo, EXPLORE_SEEDS, 5000, OUT / "ref_garm" / "rows.json", a.workers)
    return 0


# --------------------------------------------------------------------- #
# 판정
# --------------------------------------------------------------------- #


def _paired(a, b, crit) -> dict:
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    d = d[np.isfinite(d)]
    n = len(d)
    sd = float(d.std(ddof=1)) if n > 1 else float("nan")
    t = float(d.mean() / (sd / math.sqrt(n))) if n > 1 and sd > 0 else float("nan")
    return dict(diff=float(d.mean()) if n else float("nan"), t=t, n=n, sig=bool(math.isfinite(t) and abs(t) > crit))


def _series(rows, key):
    return np.array([r.get(key, float("nan")) for r in sorted(rows, key=lambda r: r["seed"])], dtype=np.float64)


def model_table(d: dict, names, mode) -> dict:
    """모델별 조건별 시드 계열. {name: {cond: {key: array}}}"""
    out = {}
    for k, rows in d["rows"].items():
        n, _, m, c = k.split("|")
        if n in names and m == mode:
            out.setdefault(n, {})[c] = rows
    return out


KEYS = ("g_gamma", "starve_rate", "predation_rate", "n1", "n5p", "b1_day", "b1_night", "b2_day", "survival", "repro",
        "p_rest_cover_night", "p_rest_cover_day", "p_eat_night_hungry", "p_eat_night_full", "p_stop_night", "p_stop_day")


def arm_series(tab: dict, cond: str, key: str) -> np.ndarray:
    """팔 평균 시드 계열(모델 평균)."""
    return np.nanmean([_series(tab[n][cond], key) for n in tab], axis=0)


def n5p_rel(tab_n: dict) -> np.ndarray:
    """N5′ 1차 정의(MEMO): 시드별 N5′(C0) − N5′(C1′)."""
    return _series(tab_n["C0"], "n5p") - _series(tab_n["C1p"], "n5p")


def choose_mode(d, names) -> dict:
    g = {m: arm_series(model_table(d, names, m), "C0", "g_gamma") for m in MODES}
    t = _paired(g["hold"], g["det"], T_CRIT_40)
    mode = ("hold" if t["diff"] > 0 else "det") if t["sig"] else "det"
    return dict(mode=mode, hold_minus_det=t)


def judge_probe(a, stage: str = "probe") -> dict:
    """탐침 판정(MEMO 3절). stage = probe(탐침 팔), resp(대응 팔, 같은 규칙), diag(진단 팔, 기술 — 결정 모드만 잰다)."""
    from scipy.stats import mannwhitneyu

    st = state()
    d = load_json(OUT / "probe" / "rows.json")
    arm = load_json(OUT / "probe" / "arm_rows.json")
    names = models(stage)
    mc = choose_mode(d, names) if stage != "diag" else dict(mode="det", hold_minus_det=None)
    mode = mc["mode"]
    tab = model_table(d, names, mode)
    res = dict(stage=stage, models=names, gamma_sel=st.get("gamma_sel"), mode=mc, checks={}, report={})
    ck, rp = res["checks"], res["report"]
    c0 = {k: arm_series(tab, "C0", k) for k in KEYS}
    c4 = {k: arm_series(tab, "C4phase", k) for k in KEYS}
    n5r = np.nanmean([n5p_rel(tab[n]) for n in names], axis=0)
    n5r_c4 = np.nanmean([_series(tab[n]["C4phase"], "n5p") - _series(tab[n]["C1p"], "n5p") for n in names], axis=0)
    i_n1 = _paired(c0["n1"], c4["n1"], T_CRIT_40)
    i_n5 = _paired(n5r, n5r_c4, T_CRIT_40)
    i_g = _paired(c0["g_gamma"], c4["g_gamma"], T_CRIT_40)
    routes = dict(n1=i_n1["diff"] >= 0.05 and i_n1["t"] > T_CRIT_40,
                  n5p=i_n5["diff"] >= 0.05 and i_n5["t"] > T_CRIT_40,
                  g=i_g["diff"] >= 0.05 and i_g["t"] > T_CRIT_40)
    ck["i"] = dict(pass_=bool(any(routes.values())), routes=routes, d_n1=i_n1, d_n5p_rel=i_n5, d_g=i_g)
    c2 = _series(arm["rows"]["C2"], "g_gamma")
    c1p = arm_series(tab, "C1p", "g_gamma")
    vs_c2, vs_c1p = _paired(c0["g_gamma"], c2, T_CRIT_40), _paired(c0["g_gamma"], c1p, T_CRIT_40)
    ck["ii"] = dict(pass_=bool(vs_c2["diff"] > 0 and vs_c2["t"] > T_CRIT_40 and vs_c1p["diff"] > 0
                               and vs_c1p["t"] > T_CRIT_40), vs_C2=vs_c2, vs_C1p=vs_c1p)
    c2_st = float(np.mean(_series(arm["rows"]["C2"], "starve_rate")))
    st_c0 = float(np.nanmean(c0["starve_rate"]))
    ck["iii"] = dict(pass_=bool(st_c0 <= 1.5 * c2_st), starve=st_c0, c2_starve=c2_st, cap=1.5 * c2_st)
    gref = load_json(OUT / "ref_garm" / "rows.json")
    b1_ref = [float(np.nanmean(_series(r, "b1_day"))) for r in gref["rows"].values()]
    b1_probe = [float(np.nanmean(_series(tab[n]["C0"], "b1_day"))) for n in names]
    mw = mannwhitneyu(b1_probe, b1_ref, alternative="less")
    ck["iv"] = dict(pass_=bool(mw.pvalue >= 0.05), p=float(mw.pvalue), b1_probe=b1_probe,
                    b1_ref_median=float(np.median(b1_ref)), n_ge_03=int(sum(x >= 0.3 for x in b1_probe)))
    res["pass"] = bool(all(c["pass_"] for c in ck.values()))
    for k in ("n1", "n5p", "g_gamma", "starve_rate", "predation_rate", "b1_day", "b1_night", "b2_day", "survival"):
        rp[k] = dict(C0=float(np.nanmean(c0[k])), C4phase=float(np.nanmean(c4[k])),
                     C1p=float(np.nanmean(arm_series(tab, "C1p", k))))
    rp["n5p_rel"] = float(np.nanmean(n5r))
    rp["per_model"] = {n: dict(g=float(np.nanmean(_series(tab[n]["C0"], "g_gamma"))),
                               n1=float(np.nanmean(_series(tab[n]["C0"], "n1"))),
                               n5p_rel=float(np.nanmean(n5p_rel(tab[n]))),
                               starve=float(np.nanmean(_series(tab[n]["C0"], "starve_rate"))),
                               b1_day=float(np.nanmean(_series(tab[n]["C0"], "b1_day")))) for n in names}
    for k in ("C2", "C2seg", "FIX", "OVL"):
        if k in arm["rows"]:
            rp[f"arm_{k}"] = {kk: float(np.nanmean(_series(arm["rows"][k], kk))) for kk in ("g_gamma", "n1", "n5p",
                                                                                         "starve_rate", "predation_rate")}
    en = arm_series(tab, "C4en", "n5p") - arm_series(tab, "C1p", "n5p")
    rp["c4_energy_night_n5p_rel"] = float(np.nanmean(en))
    return res


def _boot_ci(per_model: np.ndarray, reps=2000, seed=0):
    """모델 × 시드 배열의 평균에 대한 층화 부트스트랩 95% CI (모델·시드 재표집)."""
    rng = np.random.default_rng(seed)
    m, s = per_model.shape
    b = [per_model[rng.integers(0, m, m)][:, rng.integers(0, s, s)].mean() for _ in range(reps)]
    return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def judge_confirm(a) -> dict:
    """짧은 확인 판정 (confirm/PREREG.md). 1차 N1·N5′(C1′ 대비) — 3시드 중 2시드 이상 크기 기준."""
    st = state()
    d = load_json(OUT / "confirm" / "rows.json")
    arm = load_json(OUT / "confirm" / "arm_rows.json")
    names = models("confirm")
    mode = st["mode"]
    tab = model_table(d, names, mode)
    res = dict(stage="confirm", models=names, gamma_sel=st.get("gamma_sel"), mode=mode, primary={}, report={})
    n1 = {n: float(np.nanmean(_series(tab[n]["C0"], "n1"))) for n in names}
    n5 = {n: float(np.nanmean(n5p_rel(tab[n]))) for n in names}
    res["primary"]["N1"] = dict(per_model=n1, n_pass=sum(v >= 0.15 for v in n1.values()), need=2, crit=0.15)
    res["primary"]["N1"]["pass_"] = res["primary"]["N1"]["n_pass"] >= 2
    res["primary"]["N5p"] = dict(per_model=n5, n_pass=sum(v >= 0.1 for v in n5.values()), need=2, crit=0.1)
    res["primary"]["N5p"]["pass_"] = res["primary"]["N5p"]["n_pass"] >= 2
    rp = res["report"]
    rp["input_dep"] = {n: dict(n1_c4phase=float(np.nanmean(_series(tab[n]["C4phase"], "n1"))),
                               n5p_rel_c4energy=float(np.nanmean(_series(tab[n]["C4en"], "n5p")
                                                                  - _series(tab[n]["C1p"], "n5p"))))
                       for n in names}
    g0 = np.array([_series(tab[n]["C0"], "g_gamma") for n in names])
    c0 = g0.mean(0)
    for k in ("C2", "C2seg", "FIX", "OVL"):
        if k in arm["rows"]:
            ck = _series(arm["rows"][k], "g_gamma")
            rp[f"vs_{k}"] = dict(**_paired(c0, ck, T_CRIT_20), ci95=_boot_ci(g0 - ck[None, :]))
    rp["vs_C1p"] = _paired(c0, arm_series(tab, "C1p", "g_gamma"), T_CRIT_20)
    if "C2seg" in arm["rows"]:
        v = rp["vs_C2seg"]
        rp["learning_failure"] = bool(v["diff"] < 0 and v["t"] < -T_CRIT_20 and v["ci95"][1] < 0)
    c2g = float(np.mean(_series(arm["rows"]["C2"], "g_gamma"))) if "C2" in arm["rows"] else float("nan")
    per = {n: dict(g=float(np.nanmean(_series(tab[n]["C0"], "g_gamma"))),
                   starve=float(np.nanmean(_series(tab[n]["C0"], "starve_rate"))),
                   pred=float(np.nanmean(_series(tab[n]["C0"], "predation_rate"))),
                   b1_day=float(np.nanmean(_series(tab[n]["C0"], "b1_day"))),
                   survival=float(np.nanmean(_series(tab[n]["C0"], "survival")))) for n in names}
    rp["per_model"] = per
    rp["c2_g"] = c2g
    rp["bad"] = [n for n in names if per[n]["g"] <= c2g - 1.0]
    return res


def select_release() -> dict:
    """MEMO 5절 출시 규칙: 후보 = 최종 레시피 모델(탐침 + 짧은 확인), 탐색 시드·고른 모드."""
    st = state()
    mode = st["mode"]
    d = load_json(OUT / "probe" / "rows.json")
    arm = load_json(OUT / "probe" / "arm_rows.json")
    pool = (models("resp") if st.get("resp_used") else models("probe")) + models("confirm")
    tab = model_table(d, pool, mode)
    missing = [n for n in pool if n not in tab]
    if missing:
        raise SystemExit(f"탐색 시드 평가가 없는 후보: {missing} — eval --stage confirm_explore 를 먼저 돌린다")
    c2 = arm["rows"]["C2"]
    cap = 1.5 * float(np.mean(_series(c2, "starve_rate")))
    c2g = float(np.mean(_series(c2, "g_gamma")))
    cand = []
    for n in pool:
        t = tab[n]
        cand.append(dict(name=n, g=float(np.nanmean(_series(t["C0"], "g_gamma"))),
                         starve=float(np.nanmean(_series(t["C0"], "starve_rate"))),
                         n1=float(np.nanmean(_series(t["C0"], "n1"))), n5p_rel=float(np.nanmean(n5p_rel(t))),
                         b1_day=float(np.nanmean(_series(t["C0"], "b1_day"))), seed=int(n.rsplit("_s", 1)[1])))
    rules = [("starve", lambda c: c["starve"] <= cap), ("n1", lambda c: c["n1"] >= 0.15),
             ("n5p", lambda c: c["n5p_rel"] >= 0.1), ("b1", lambda c: c["b1_day"] >= 0.3)]
    pick, dropped = None, []
    drop_order = ("b1", "n5p", "n1")              # MEMO 5절: B1 → N5′ → N1 순서로 조건을 뺀다
    for k in range(len(drop_order) + 1):
        gone = drop_order[:k]
        ok = [c for c in cand if all(f(c) for r, f in rules if r not in gone)]
        if ok:
            pick = max(ok, key=lambda c: (c["g"], -c["seed"]))
            dropped = list(gone)
            break
    flag = None
    if pick is None:
        ok = [c for c in cand if c["g"] > c2g - 1.0]
        pick = max(ok, key=lambda c: (c["g"], -c["seed"])) if ok else None
        flag = "자격 없음"
    return dict(mode=mode, starve_cap=cap, c2_g=c2g, candidates=cand, pick=pick, dropped=dropped, flag=flag)


def cmd_judge(a) -> int:
    if a.stage == "confirm":
        res = judge_confirm(a)
        res["release"] = select_release()
        res["created"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_json(OUT / "confirm" / "judge.json", res)
        print(json.dumps({k: res[k] for k in ("primary", "release")}, ensure_ascii=False, indent=1, default=str))
        return 0
    if a.stage in ("probe", "resp", "diag"):
        res = judge_probe(a, a.stage)
        res["created"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_json(OUT / "probe" / ("judge.json" if a.stage == "probe" else f"judge_{a.stage}.json"), res)
        st = state()
        if a.stage == "probe":
            st["mode"] = res["mode"]["mode"]
            st["probe_pass"] = res["pass"]
        elif a.stage == "resp":
            st["resp_mode"] = res["mode"]["mode"]
            st["resp_pass"] = res["pass"]
        save_json(OUT / "state.json", st)
        print(json.dumps({k: res[k] for k in ("pass", "mode", "checks")}, ensure_ascii=False, indent=1, default=str))
    else:
        raise SystemExit("confirm 판정은 confirm/PREREG.md 를 쓴 뒤 이 파일에 더한다")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--stage", choices=["probe", "resp", "confirm", "diag"], required=True)
    t.add_argument("--concurrency", type=int, default=6)
    t.add_argument("--poll", type=float, default=30.0)
    t.set_defaults(fn=cmd_train)
    g = sub.add_parser("g27")
    g.add_argument("--workers", type=int, default=16)
    g.set_defaults(fn=cmd_g27)
    e = sub.add_parser("eval")
    e.add_argument("--stage", choices=["probe", "resp", "confirm", "confirm_explore", "diag"], required=True)
    e.add_argument("--workers", type=int, default=16)
    e.set_defaults(fn=cmd_eval)
    r = sub.add_parser("garm")
    r.add_argument("--workers", type=int, default=16)
    r.set_defaults(fn=cmd_garm)
    j = sub.add_parser("judge")
    j.add_argument("--stage", choices=["probe", "resp", "diag", "confirm"], required=True)
    j.set_defaults(fn=cmd_judge)
    ap.add_argument("--variant", choices=["base", "b", "s"], default="base")
    a = ap.parse_args(argv)
    set_variant(a.variant)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
