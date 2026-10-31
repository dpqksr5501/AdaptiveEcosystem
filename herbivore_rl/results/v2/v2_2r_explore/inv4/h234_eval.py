"""갈림 4 조사 H2·H3/H4 — 학습 시드를 늘린 T0·T1 과 대조 팔 T1-d0 의 평가 (inv4/MEMO.md 1절 H2·H3/H4 행).

    cd herbivore_rl
    python results/v2/v2_2r_explore/inv4/h234_eval.py run --budget 480     # 잡을 돌려 h234_rows.jsonl 에 쌓는다(이어 돌리기)
    python results/v2/v2_2r_explore/inv4/h234_eval.py summarize            # h234_eval.json 을 만든다

평가 조건은 probe_v2 eval 의 C0 와 같다: 각 팔의 설정 세계, 탐색 시드 12000~12039 × 5000스텝, γ 학습값, 두 모드
(결정 = {"kind":"learned"}, K24 = mode hold·hold_k 24), env_v2.rollout._run_one 페이로드(tail 없음, head 0).
- 새로 재는 모델: T0 s23~25 (configs/v2_1.yaml), T1 s23~25 (configs/v2_2r_t1.yaml), T1-d0 s20~22 (configs/v2_2r_t1d0.yaml)
- T0·T1 s20~22 는 eval_p1.json 의 행을 그대로 쓴다. 조건(cond 의 시드·스텝·γ·K)과 모델 sha1 이 같은지 확인하고,
  잡 4개(T0·T1 s20, 시드 12000, 두 모드)를 다시 돌려 공개 열이 같은지 본다(repro).
- `run` 은 `--budget` 초가 지나면 새 잡을 넣지 않고 돌던 잡만 끝낸다. 다시 부르면 남은 잡만 돈다.

판정 규칙(MEMO 1절 그대로):
- 출시 모드: probe_v2.choose_modes 규칙(팔의 모델 평균 시계열, K24 − 결정 짝 t > 2.023 이면 높은 쪽, 아니면 B1 ≥ 0.3
  크기 통과 수, 같으면 결정). T1-d0 는 사용 지표가 없는 팔(T1 과 같은 규칙)이라 키를 T1 꼴로 바꿔 같은 함수에 넣는다.
- H2: 출시 모드에서 모델 평균 G_γ(모델마다 탐색 시드 40개 평균) T1(6) − T0(6) 의 Welch t, |t| > 2.23 이면 유의.
- H3/H4: T1-d0(3) − T0(6), T1-d0(3) − T1(6) 모델 평균 차. T1-d0 − T0 > −0.15 면 H3, T1-d0 − T1 < +0.15 면 H4.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]          # herbivore_rl
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch보다 먼저

import argparse  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import numpy as np  # noqa: E402

OUT = Path(__file__).resolve().parent
EXPLORE = OUT.parent
ROWS = OUT / "h234_rows.jsonl"
SUMMARY = OUT / "h234_eval.json"
P1 = EXPLORE / "eval_p1.json"
JUDGE = EXPLORE / "judge.json"
CKPT = ROOT / "ckpt" / "v2"
STEPS = 5000
GAMMA = 0.9916661555611042
HOLD_K = 24
WELCH_CRIT = 2.23                  # MEMO 1절 H2 (자유도 ≈ 10)
H34_MARGIN = 0.15                  # MEMO 1절 H3/H4
MODE_NAMES = ("det", "hold")
ARMS = {
    "T0": {"config": "configs/v2_1.yaml", "run": "v2_2r_t0", "seeds": (20, 21, 22, 23, 24, 25), "p1": (20, 21, 22)},
    "T1": {"config": "configs/v2_2r_t1.yaml", "run": "v2_2r_t1", "seeds": (20, 21, 22, 23, 24, 25), "p1": (20, 21, 22)},
    "T1d0": {"config": "configs/v2_2r_t1d0.yaml", "run": "v2_2r_t1d0", "seeds": (20, 21, 22), "p1": ()},
}
REPRO = [("T0", 20, "det"), ("T0", 20, "hold"), ("T1", 20, "det"), ("T1", 20, "hold")]
REPRO_SEED = 12000
AUX_COLS = ("g_gamma", "b1", "b2", "starve_rate", "predation_rate", "survival", "stop_frac", "walk_frac", "run_frac")
PROBE_COLS = ("p_stop", "speed_std", "p_stop_win", "p_stop_calm", "frac_win", "frac_seen")


def model_path(arm: str, seed: int) -> Path:
    return CKPT / f"{ARMS[arm]['run']}_s{seed}.zip"


def key_of(arm: str, seed: int, mode: str) -> str:
    return f"{arm}_s{seed}|C0|{mode}"


def spec_of(arm: str, seed: int, mode: str) -> dict:
    from probe_v2 import MODES

    return {"kind": "learned", "model": str(model_path(arm, seed).resolve()), **MODES[mode]}


def read_rows() -> list[dict]:
    if not ROWS.exists():
        return []
    return [json.loads(ln) for ln in ROWS.read_text(encoding="utf-8").splitlines() if ln.strip()]


def fingerprints() -> dict[str, str]:
    from diagnose_v2 import model_fingerprint

    return {f"{arm}_s{s}": model_fingerprint(model_path(arm, s)) for arm, a in ARMS.items() for s in a["seeds"]}


def job_list() -> list[dict]:
    from diagnose_v2 import EXPLORE_SEEDS

    jobs = []
    for arm, a in ARMS.items():
        for s in a["seeds"]:
            if s in a["p1"]:
                continue
            for m in MODE_NAMES:
                for sd in EXPLORE_SEEDS:
                    jobs.append({"key": key_of(arm, s, m), "arm": arm, "model": f"{arm}_s{s}", "seed": int(sd),
                                 "spec": spec_of(arm, s, m)})
    for arm, s, m in REPRO:
        jobs.append({"key": "repro:" + key_of(arm, s, m), "arm": arm, "model": f"{arm}_s{s}", "seed": REPRO_SEED,
                     "spec": spec_of(arm, s, m)})
    return jobs


# --------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------- #


def cmd_run(args) -> int:
    from concurrent.futures import FIRST_COMPLETED, wait

    from env_v2.config import load_v2_config
    from env_v2.rollout import _run_one, make_executor, public_row

    sha = fingerprints()
    cfgs = {arm: load_v2_config(ROOT / a["config"]).to_dict() for arm, a in ARMS.items()}
    have = {(r["key"], r["seed"]) for r in read_rows()
            if r.get("steps") == STEPS and r.get("gamma") == GAMMA and r.get("sha1") == sha[r["model"]]}
    todo = [j for j in job_list() if (j["key"], j["seed"]) not in have]
    # repro 잡을 먼저 돌린다(재사용 확인이 가장 먼저 필요하다)
    todo.sort(key=lambda j: not j["key"].startswith("repro:"))
    print(f"잡 {len(todo)}개 남음 (이미 {len(have)}개), 워커 {args.workers}, 예산 {args.budget}s", flush=True)
    if not todo:
        return 0
    ex = make_executor(args.workers)
    t0 = time.time()
    n_done = 0
    inflight = {}
    it = iter(todo)
    try:
        with open(ROWS, "a", encoding="utf-8") as f:
            while True:
                while len(inflight) < max(args.workers, 1) and time.time() - t0 < args.budget:
                    j = next(it, None)
                    if j is None:
                        break
                    payload = (cfgs[j["arm"]], j["spec"], j["seed"], STEPS, GAMMA, None, 0, 0)
                    fut = ex.submit(_run_one, payload) if ex is not None else None
                    if fut is None:                 # 워커 1 이하: 같은 프로세스에서
                        from concurrent.futures import Future
                        fut = Future()
                        fut.set_result(_run_one(payload))
                    inflight[fut] = j
                if not inflight:
                    break
                fin, _ = wait(list(inflight), return_when=FIRST_COMPLETED)
                for fut in fin:
                    j = inflight.pop(fut)
                    row = public_row(fut.result())
                    f.write(json.dumps({"key": j["key"], "seed": j["seed"], "model": j["model"],
                                        "sha1": sha[j["model"]], "steps": STEPS, "gamma": GAMMA, "spec": j["spec"],
                                        "row": row}, ensure_ascii=False, allow_nan=True) + "\n")
                    f.flush()
                    n_done += 1
                    if n_done % 16 == 0:
                        el = time.time() - t0
                        print(f"  {n_done} 끝 ({el:.0f}s, 잡당 {el / n_done:.1f}s)", flush=True)
    finally:
        if ex is not None:
            ex.shutdown()
    left = len(todo) - n_done
    print(f"이번 호출 {n_done}개 ({time.time() - t0:.0f}s), 남은 잡 {left}개", flush=True)
    return 0


# --------------------------------------------------------------------- #
# 통계
# --------------------------------------------------------------------- #


def welch(a, b) -> dict:
    """Welch t (a − b). 모델마다 한 값. 자유도는 Welch–Satterthwaite, 정확 순열 p(양측, 평균 차)도 붙인다."""
    from scipy import stats

    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    na, nb = len(a), len(b)
    va, vb = a.var(ddof=1), b.var(ddof=1)
    se2 = va / na + vb / nb
    diff = float(a.mean() - b.mean())
    t = diff / math.sqrt(se2) if se2 > 0 else float("nan")
    df = se2 ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)) if se2 > 0 else float("nan")
    allv = np.concatenate([a, b])
    obs = abs(diff)
    cnt = tot = 0
    for idx in itertools.combinations(range(na + nb), na):
        m = np.zeros(na + nb, dtype=bool)
        m[list(idx)] = True
        cnt += abs(allv[m].mean() - allv[~m].mean()) >= obs - 1e-12
        tot += 1
    return {"diff": diff, "t": float(t), "df": float(df),
            "crit_df": float(stats.t.ppf(0.975, df)) if math.isfinite(df) else float("nan"),
            "sig_memo": bool(math.isfinite(t) and abs(t) > WELCH_CRIT), "perm_p": cnt / tot,
            "full_split": bool(a.max() < b.min() or a.min() > b.max()), "n": [na, nb]}


def _col(rows, key):
    return np.array([r.get(key, float("nan")) for r in sorted(rows, key=lambda r: r["seed"])], dtype=np.float64)


# --------------------------------------------------------------------- #
# summarize
# --------------------------------------------------------------------- #


def same_row(a: dict, b: dict) -> bool:
    if set(a) != set(b):
        return False
    for k in a:
        x, y = a[k], b[k]
        if isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y):
            continue
        if x != y:
            return False
    return True


def read_probe(arm: str, seed: int) -> list[dict]:
    p = model_path(arm, seed).with_suffix(".probe.jsonl")
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def cmd_summarize(args) -> int:
    from diagnose_v2 import EXPLORE_SEEDS
    from probe_v2 import arm_series, choose_modes

    seeds = list(EXPLORE_SEEDS)
    sha = fingerprints()
    p1 = json.loads(P1.read_text(encoding="utf-8"))
    judge = json.loads(JUDGE.read_text(encoding="utf-8"))

    # 1) eval_p1 재사용 확인
    c = p1["cond"]
    reuse = {"cond_seeds": c["seeds"] == seeds, "cond_steps": c["steps"] == STEPS, "cond_gamma": c["gamma"] == GAMMA,
             "cond_hold_k": c["hold_k"] == HOLD_K, "keys": {}}
    rows: dict[str, list[dict]] = {}
    source: dict[str, str] = {}
    for arm, a in ARMS.items():
        for s in a["p1"]:
            for m in MODE_NAMES:
                k = key_of(arm, s, m)
                rr = p1["rows"][k]
                reuse["keys"][k] = {"n": len(rr), "seeds": [r["seed"] for r in rr] == seeds,
                                    "sha1": p1["sha1"].get(k) == sha[f"{arm}_s{s}"]}
                rows[k] = rr
                source[k] = "eval_p1.json"
    new = {}
    repro = {}
    for r in read_rows():
        if r["steps"] != STEPS or r["gamma"] != GAMMA or r["sha1"] != sha[r["model"]]:
            continue
        if r["key"].startswith("repro:"):
            k = r["key"][len("repro:"):]
            ref = next(x for x in p1["rows"][k] if x["seed"] == r["seed"])
            repro[k] = {"seed": r["seed"], "same_public_row": same_row(r["row"], ref),
                        "g_gamma": r["row"]["g_gamma"], "g_gamma_p1": ref["g_gamma"]}
            continue
        new.setdefault(r["key"], {})[r["seed"]] = r["row"]
    missing = []
    for arm, a in ARMS.items():
        for s in a["seeds"]:
            if s in a["p1"]:
                continue
            for m in MODE_NAMES:
                k = key_of(arm, s, m)
                got = new.get(k, {})
                if sorted(got) != seeds:
                    missing.append(f"{k} ({len(got)}/40)")
                    continue
                rows[k] = [got[sd] for sd in seeds]
                source[k] = "h234_rows.jsonl"
    reuse["repro"] = repro
    reuse["ok"] = (all(v for kk, v in reuse.items() if kk.startswith("cond_"))
                   and all(all(v2 for kk2, v2 in v.items() if kk2 != "n") and v["n"] == 40
                           for v in reuse["keys"].values())
                   and len(repro) == len(REPRO) and all(v["same_public_row"] for v in repro.values()))
    if missing:
        print("아직 없는 잡:", ", ".join(missing))
        if not args.partial:
            return 1
    d = {"rows": rows}

    # 2) 출시 모드
    def sub(arms_seeds: dict[str, tuple], rename: dict[str, str] | None = None) -> dict:
        out = {}
        for arm, ss in arms_seeds.items():
            for s in ss:
                for m in MODE_NAMES:
                    k = key_of(arm, s, m)
                    if k in rows:
                        out[key_of((rename or {}).get(arm, arm), s, m)] = rows[k]
        return {"rows": out}

    def strip(mres: dict) -> dict:
        return {"mode": mres["mode"], "why": mres["why"], "hold_minus_det": mres["hold_minus_det"],
                "passes": mres["passes"], "g": mres["g"]}

    m6 = choose_modes(sub({"T0": ARMS["T0"]["seeds"], "T1": ARMS["T1"]["seeds"]}))
    m3 = choose_modes(sub({"T0": (20, 21, 22), "T1": (20, 21, 22)}))
    mnew = choose_modes(sub({"T0": (23, 24, 25), "T1": (23, 24, 25)}))
    md0 = choose_modes(sub({"T1d0": ARMS["T1d0"]["seeds"]}, rename={"T1d0": "T1"}))["T1"]
    modes = {
        "T0": {**strip(m6["T0"]), "n_models": 6},
        "T1": {**strip(m6["T1"]), "n_models": 6},
        "T1d0": {**strip(md0), "n_models": 3},
        "three_model_20_22": {a: strip(m3[a]) for a in ("T0", "T1")},
        "three_model_23_25": {a: strip(mnew[a]) for a in ("T0", "T1")},
        "judge_json": {a: judge["modes"][a]["mode"] for a in ("T0", "T1")},
    }
    modes["six_equals_three"] = {a: m6[a]["mode"] == m3[a]["mode"] for a in ("T0", "T1")}
    launch = {a: modes[a]["mode"] for a in ARMS}

    # 3) 모델별 값
    def per_model(arm, mode, col="g_gamma", ss=None):
        ss = ss or ARMS[arm]["seeds"]
        return {s: float(np.nanmean(_col(rows[key_of(arm, s, mode)], col))) for s in ss}

    pm = {arm: {m: {col: per_model(arm, m, col) for col in AUX_COLS} for m in MODE_NAMES} for arm in ARMS}

    def g_list(arm, mode, ss=None):
        v = per_model(arm, mode, "g_gamma", ss)
        return [v[s] for s in sorted(v)]

    # 4) H2
    def cmp(arm_a, arm_b, ma, mb, sa=None, sb=None):
        r = welch(g_list(arm_a, ma, sa), g_list(arm_b, mb, sb))
        r["modes"] = [ma, mb]
        return r

    h2 = {"launch": cmp("T1", "T0", launch["T1"], launch["T0"]),
          "det": cmp("T1", "T0", "det", "det"), "hold": cmp("T1", "T0", "hold", "hold"),
          "s23_25": {"launch": cmp("T1", "T0", launch["T1"], launch["T0"], (23, 24, 25), (23, 24, 25)),
                     "det": cmp("T1", "T0", "det", "det", (23, 24, 25), (23, 24, 25)),
                     "hold": cmp("T1", "T0", "hold", "hold", (23, 24, 25), (23, 24, 25))},
          "s20_22": {"launch": cmp("T1", "T0", launch["T1"], launch["T0"], (20, 21, 22), (20, 21, 22)),
                     "det": cmp("T1", "T0", "det", "det", (20, 21, 22), (20, 21, 22)),
                     "hold": cmp("T1", "T0", "hold", "hold", (20, 21, 22), (20, 21, 22))}}
    h2["verdict"] = ("H2 버림: 출시 모드 T1 − T0 가 유의(|t| > 2.23)" if h2["launch"]["sig_memo"]
                     else "H2 를 버리지 못함: 출시 모드 T1 − T0 가 유의하지 않음(|t| ≤ 2.23)")

    # 5) H3/H4
    def h34(md0_, mt0, mt1):
        a = cmp("T1d0", "T0", md0_, mt0)
        b = cmp("T1d0", "T1", md0_, mt1)
        h3, h4 = a["diff"] > -H34_MARGIN, b["diff"] < H34_MARGIN
        v = ("H3·H4 둘 다" if h3 and h4 else "H3" if h3 else "H4" if h4 else "판정 없음")
        return {"d0_minus_T0": a, "d0_minus_T1": b, "H3": bool(h3), "H4": bool(h4), "verdict": v}

    h34r = {"launch": h34(launch["T1d0"], launch["T0"], launch["T1"]),
            "det": h34("det", "det", "det"), "hold": h34("hold", "hold", "hold")}

    # 6) 팔별 보조 지표 (모델 평균 시계열의 평균, probe_v2.judge 와 같은 식)
    arm_aux = {arm: {m: {col: float(np.nanmean(arm_series(d, arm, "C0", m, col))) for col in AUX_COLS}
                     for m in MODE_NAMES} for arm in ARMS}

    # 7) 학습 중 탐침 궤적
    probe = {}
    for arm, a in ARMS.items():
        per = {s: read_probe(arm, s) for s in a["seeds"]}
        n = min(len(v) for v in per.values())
        ts = [per[a["seeds"][0]][i]["timesteps"] for i in range(n)]
        cols = {}
        for col in PROBE_COLS:
            mat = [[(per[s][i].get(col) if per[s][i].get(col) is not None else float("nan")) for i in range(n)]
                   for s in a["seeds"]]
            if all(all(isinstance(x, float) and math.isnan(x) for x in r_) for r_ in mat):
                continue
            mat = np.array(mat, dtype=np.float64)
            cols[col] = {"mean": [float(x) for x in np.nanmean(mat, axis=0)],
                         "per_seed": {str(s): [float(x) for x in mat[j]] for j, s in enumerate(a["seeds"])}}
        probe[arm] = {"timesteps": ts, "cols": cols}
    probe_cmp = {}
    for (aa, bb) in (("T1", "T0"), ("T1d0", "T0"), ("T1d0", "T1")):
        probe_cmp[f"{aa}-{bb}"] = {}
        for col in ("p_stop", "speed_std"):
            ra, rb = probe[aa]["cols"][col]["per_seed"], probe[bb]["cols"][col]["per_seed"]
            n = min(len(probe[aa]["timesteps"]), len(probe[bb]["timesteps"]))
            ser = []
            for i in range(n):
                w = welch([v[i] for v in ra.values()], [v[i] for v in rb.values()])
                ser.append({"timesteps": probe[aa]["timesteps"][i], "diff": w["diff"], "t": w["t"], "df": w["df"],
                            "crit_df": w["crit_df"], "full_split": w["full_split"]})
            first_sig = next((s_["timesteps"] for s_ in ser if abs(s_["t"]) > s_["crit_df"]), None)
            stay = None
            for i in range(len(ser)):
                if all(abs(x["t"]) > x["crit_df"] and np.sign(x["diff"]) == np.sign(ser[-1]["diff"])
                       for x in ser[i:]):
                    stay = ser[i]["timesteps"]
                    break
            first_split = next((s_["timesteps"] for s_ in ser if s_["full_split"]), None)
            probe_cmp[f"{aa}-{bb}"][col] = {"series": ser, "first_sig": first_sig, "sig_from_on": stay,
                                            "first_full_split": first_split}

    res = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "cond": {"seeds": seeds, "steps": STEPS, "gamma": GAMMA, "hold_k": HOLD_K, "kind": "C0",
                    "welch_crit": WELCH_CRIT, "h34_margin": H34_MARGIN,
                    "configs": {a: ARMS[a]["config"] for a in ARMS}},
           "partial": bool(missing), "missing": missing,
           "p1_reuse": reuse, "sha1": sha, "source": source,
           "modes": modes, "launch": launch,
           "per_model": {arm: {m: {col: {str(s): v for s, v in pm[arm][m][col].items()} for col in AUX_COLS}
                               for m in MODE_NAMES} for arm in ARMS},
           "arm_aux": arm_aux, "H2": h2, "H3H4": h34r,
           "probe": probe, "probe_cmp": probe_cmp,
           "rows": rows}
    SUMMARY.write_text(json.dumps(res, ensure_ascii=False, indent=1, allow_nan=True), encoding="utf-8")
    print_summary(res)
    return 0


def _f(x, nd=3):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.{nd}f}"


def print_summary(res: dict) -> None:
    r = res["p1_reuse"]
    print(f"eval_p1 재사용 ok={r['ok']}  repro={ {k: v['same_public_row'] for k, v in r['repro'].items()} }")
    for a in ("T0", "T1", "T1d0"):
        m = res["modes"][a]
        print(f"모드 {a}({m['n_models']}): {m['mode']} ({m['why']}) 결정 {m['g']['det']:.3f} K24 {m['g']['hold']:.3f} "
              f"K24−결정 {_f(m['hold_minus_det']['diff'])} (t {_f(m['hold_minus_det']['t'], 2)}) 통과 {m['passes']}")
    for tag in ("three_model_20_22", "three_model_23_25"):
        for a, m in res["modes"][tag].items():
            print(f"  {tag} {a}: {m['mode']} ({m['why']}) 결정 {m['g']['det']:.3f} K24 {m['g']['hold']:.3f} "
                  f"t {_f(m['hold_minus_det']['t'], 2)} 통과 {m['passes']}")
    print(f"  6 = 3 모델 모드: {res['modes']['six_equals_three']}, judge.json {res['modes']['judge_json']}")
    for arm, pm in res["per_model"].items():
        for m in MODE_NAMES:
            print(f"  {arm} {m} G_γ " + " ".join(f"s{s} {v:.3f}" for s, v in pm[m]["g_gamma"].items()))

    def w(x):
        return (f"{_f(x['diff'])} (t {_f(x['t'], 2)}, df {x['df']:.1f}, crit {x['crit_df']:.2f}, perm p "
                f"{x['perm_p']:.4f}, 분리 {x['full_split']}, 모드 {x['modes']})")
    h2 = res["H2"]
    print("H2:", h2["verdict"])
    for k in ("launch", "det", "hold"):
        print(f"  6v6 {k}: {w(h2[k])}")
    for g in ("s23_25", "s20_22"):
        for k in ("launch", "det", "hold"):
            print(f"  {g} {k}: {w(h2[g][k])}")
    for k, v in res["H3H4"].items():
        print(f"H3/H4 {k}: {v['verdict']}  d0−T0 {w(v['d0_minus_T0'])}")
        print(f"            d0−T1 {w(v['d0_minus_T1'])}")
    for arm, mm in res["arm_aux"].items():
        for m, v in mm.items():
            print(f"  aux {arm} {m}: " + " ".join(f"{c} {v[c]:.5g}" for c in AUX_COLS))
    for k, v in res["probe_cmp"].items():
        for col, x in v.items():
            print(f"  탐침 {k} {col}: 처음 유의 {x['first_sig']}, 끝까지 유의 {x['sig_from_on']}, 처음 분리 "
                  f"{x['first_full_split']}; " + " ".join(f"{s['timesteps'] / 1e6:.0f}M {s['diff']:+.3f}({s['t']:+.1f})"
                                                        for s in x["series"]))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--budget", type=float, default=480.0, help="이 초가 지나면 새 잡을 넣지 않는다")
    s = sub.add_parser("summarize")
    s.add_argument("--partial", action="store_true", help="없는 잡이 있어도 있는 것만으로 요약(점검용)")
    args = p.parse_args(argv)
    return {"run": cmd_run, "summarize": cmd_summarize}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
