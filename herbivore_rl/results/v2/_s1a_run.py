"""S1-a 학습 세계 균형 추출·세계 순서 원인 확인 실행기 (`results/v2/s1a/PREREG.md`, 학습 전 작성).

    # herbivore_rl/ 에서
    python results/v2/_s1a_run.py train --concurrency 16     # 72개 학습(이미 있는 모델은 건너뜀)
    python results/v2/_s1a_run.py eval                       # 평가 시드 10000~10019 × 5000스텝, 결정 모드(판정)
    python results/v2/_s1a_run.py judge                      # P1·P2, 레시피, 2차 → s1a/judge.json·judge.md
    python results/v2/_s1a_run.py select                     # 고른 레시피 팔의 출시 모델(탐색 시드, 두 모드)

팔·시드·판정 규칙은 PREREG 그대로다. 모든 팔을 configs/v2_1.yaml 세계에서 잰다. 나쁨(1차) = G_γ(결정, 평가 시드 평균) ≤ 0.482.
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

OUT = ROOT / "results" / "v2" / "s1a"
CKPT = ROOT / "ckpt" / "v2"
GAMMA = 0.9916661555611042
EVAL_SEEDS = list(range(10000, 10020))
C2_G, C2_STARVE = 1.4820, 0.0004271875           # 평가 시드 C2 (E1-b/E2 C2 상수), PREREG 2절
C2_STARVE_EXPLORE = 0.000454
BAD_G = C2_G - 1.0                                 # 0.482

HW_WORLDS = {24: (80, 81, 82), 30: (83, 84, 85), 31: (86, 87, 88), 33: (89, 90, 91)}
GW_WORLDS = {32: (92, 93, 94), 20: (95, 96, 97), 22: (98, 99, 100), 25: (101, 102, 103)}


def jobs() -> list[dict]:
    out = []
    for s in range(50, 74):
        out.append({"arm": "B", "name": f"s1a_b_s{s}", "config": "configs/v2_1.yaml", "seed": s, "world_seed": s})
        out.append({"arm": "W", "name": f"s1a_w_s{s}", "config": "configs/v2_1_bal.yaml", "seed": s, "world_seed": s})
    for arm, table in (("HW", HW_WORLDS), ("GW", GW_WORLDS)):
        for ws, seeds in table.items():
            for s in seeds:
                out.append({"arm": arm, "name": f"s1a_{arm.lower()}_s{s}", "config": "configs/v2_1.yaml", "seed": s,
                            "world_seed": ws})
    return out


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


# --------------------------------------------------------------------- #
# train
# --------------------------------------------------------------------- #


def cmd_train(a) -> int:
    logs = OUT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    todo = [j for j in jobs() if not (CKPT / f"{j['name']}.zip").exists()]
    # B·W 를 같은 시드끼리 먼저, 그다음 HW·GW (같은 시간대에 비교 팔이 함께 돌게)
    todo.sort(key=lambda j: (j["arm"] in ("HW", "GW"), j["seed"], j["arm"]))
    print(f"학습할 것 {len(todo)}개 (동시 {a.concurrency})", flush=True)
    running: list[tuple[dict, subprocess.Popen, object]] = []
    status = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "runs": {}}
    t0 = time.time()
    while todo or running:
        while todo and len(running) < a.concurrency:
            j = todo.pop(0)
            cmd = [sys.executable, "train_v2.py", "--config", j["config"], "--steps", "20000000", "--seed", str(j["seed"]),
                   "--world-seed", str(j["world_seed"]), "--run-name", j["name"], "--save-at", "10000000",
                   "--probe-every", "1000000", "--threads", "1"]
            log = open(logs / f"train_{j['name']}.log", "w", encoding="utf-8")
            running.append((j, subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT), log))
            status["runs"][j["name"]] = {"arm": j["arm"], "cmd": " ".join(cmd[1:]), "returncode": None}
        time.sleep(a.poll)
        still = []
        for j, p, log in running:
            rc = p.poll()
            if rc is None:
                still.append((j, p, log))
                continue
            log.close()
            status["runs"][j["name"]]["returncode"] = rc
            done = sum(1 for r in status["runs"].values() if r["returncode"] is not None)
            print(f"[{(time.time() - t0) / 60:5.1f}분] 끝 {j['name']} (rc {rc}) — {done}/{len(status['runs'])}, 남은 {len(todo)}",
                  flush=True)
        running = still
        save_json(OUT / "train_status.json", status)
    status["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_json(OUT / "train_status.json", status)
    bad = [n for n, r in status["runs"].items() if r["returncode"] != 0]
    print("학습 끝" + (f" — 실패: {bad}" if bad else ""), flush=True)
    return 1 if bad else 0


# --------------------------------------------------------------------- #
# eval
# --------------------------------------------------------------------- #


def _spec(name: str, mode: str = "det") -> dict:
    s = {"kind": "learned", "model": str((CKPT / f"{name}.zip").resolve())}
    if mode == "hold":
        s.update(mode="hold", hold_k=24)
    return s


def _rows(res):
    from env_v2.rollout import public_row

    return [public_row(r) for r in res]


def cmd_eval(a) -> int:
    from diagnose_v2 import model_fingerprint
    from env_v2.config import load_v2_config
    from env_v2.rollout import make_executor, run_specs

    cfg = load_v2_config(ROOT / "configs" / "v2_1.yaml")
    path = OUT / "eval.json"
    d = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"rows": {}, "sha1": {}}
    todo = []
    for j in jobs():
        z = CKPT / f"{j['name']}.zip"
        if not z.exists():
            continue
        sha = model_fingerprint(z)
        if d["rows"].get(j["name"]) and d["sha1"].get(j["name"]) == sha:
            continue
        todo.append((j["name"], sha))
    print(f"평가할 모델 {len(todo)}개", flush=True)
    ex = make_executor(a.workers)
    try:
        for i in range(0, len(todo), 8):
            chunk = todo[i:i + 8]
            res = run_specs(cfg, {n: _spec(n) for n, _ in chunk}, EVAL_SEEDS, 5000, gamma=GAMMA, executor=ex)
            for n, sha in chunk:
                d["rows"][n] = _rows(res[n])
                d["sha1"][n] = sha
            d["meta"] = {"config": "configs/v2_1.yaml", "eval_seeds": [EVAL_SEEDS[0], EVAL_SEEDS[-1]], "steps": 5000,
                         "gamma": GAMMA, "mode": "deterministic"}
            save_json(path, d)
            print(f"  {i + len(chunk)}/{len(todo)}", flush=True)
    finally:
        if ex is not None:
            ex.shutdown()
    return 0


# --------------------------------------------------------------------- #
# judge
# --------------------------------------------------------------------- #


def _mean(rows, key):
    return float(np.mean([r[key] for r in rows]))


def world_mix(meta_seed: int, config: str) -> float:
    """학습 중 본 세계의 시간 가중 먹이 재생 배수 평균 (세계 고르기만 흉내 낸다, s1a_diag/world_mix.py 와 같은 규칙)."""
    from env_v2.config import load_v2_config
    from env_v2.vec_env import MultiWorldVecEnv, world_sampling_params
    from env_v2.world import world_params

    cfg = load_v2_config(ROOT / config)
    v = MultiWorldVecEnv.__new__(MultiWorldVecEnv)
    v.K, v.T = 8, 4000
    v.pool = np.arange(1000)
    v._meta = np.random.default_rng(meta_seed)
    v._ws = world_sampling_params((cfg.v2.get("train") or {}).get("world_sampling"))
    fr = {s: world_params(cfg, s)["food_regen_mult"] for s in range(1000)}
    if v._ws:
        keys = v._ws["keys"]
        feats = np.array([[world_params(cfg, s)[k] for k in keys] for s in range(1000)])
        mu, sd = feats.mean(0), feats.std(0)
        v._ws_z = dict(zip(range(1000), (feats - mu) / sd))
        v._ws_sum, v._ws_n, v.ws_picked = np.zeros(len(keys)), 0, []

    class W:
        pass
    v.worlds = []
    for _ in range(8):
        w = W()
        w.seed = v._pick_seed(exclude=[x.seed for x in v.worlds])
        v.worlds.append(w)
    age = np.array([(k * 4000) // 8 for k in range(8)])
    acc, n = 0.0, 0
    for _ in range(20021248 // 1024):
        for k, w in enumerate(v.worlds):
            acc += fr[w.seed]
            n += 1
            age[k] += 1
            if age[k] >= 4000:
                w.seed = v._pick_seed(exclude=[x.seed for i, x in enumerate(v.worlds) if i != k])
                age[k] = 0
    return acc / n


def _cp(k, n, alpha=0.05):
    from scipy.stats import beta

    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return [lo, hi]


def cmd_judge(a) -> int:
    from scipy.stats import fisher_exact, mannwhitneyu

    d = json.loads((OUT / "eval.json").read_text(encoding="utf-8"))
    models = {}
    for j in jobs():
        rows = d["rows"].get(j["name"])
        if not rows:
            continue
        g, st = _mean(rows, "g_gamma"), _mean(rows, "starve_rate")
        models[j["name"]] = {"arm": j["arm"], "seed": j["seed"], "world_seed": j["world_seed"], "g": g, "starve": st,
                             "predation": _mean(rows, "predation_rate"), "b1": _mean(rows, "b1"),
                             "bad": bool(g <= BAD_G), "bad2": bool(g <= BAD_G and st >= 2 * C2_STARVE),
                             "world_fr": world_mix(j["world_seed"], j["config"])}
    arms = {}
    for arm in ("B", "W", "HW", "GW"):
        ms = [m for m in models.values() if m["arm"] == arm]
        k = sum(m["bad"] for m in ms)
        arms[arm] = {"n": len(ms), "bad": k, "bad2": sum(m["bad2"] for m in ms), "rate": k / len(ms) if ms else None,
                     "cp95": _cp(k, len(ms)) if ms else None,
                     "g_median": float(np.median([m["g"] for m in ms])) if ms else None,
                     "g_q": [float(np.percentile([m["g"] for m in ms], q)) for q in (25, 75)] if ms else None}

    def fisher(x, y, key="bad"):
        nx, ny = arms[x]["n"], arms[y]["n"]
        kx, ky = arms[x][key], arms[y][key]
        return float(fisher_exact([[kx, nx - kx], [ky, ny - ky]], alternative="greater")[1])

    res = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bad_threshold_g": BAD_G,
           "arms": arms, "models": models}
    res["P1"] = {"test": "Fisher 단측, 나쁨 B > W", "p": fisher("B", "W"), "p_bad2": fisher("B", "W", "bad2")}
    res["P1"]["sig"] = res["P1"]["p"] < 0.05
    res["P2"] = {"test": "Fisher 단측, 나쁨 HW > GW", "p": fisher("HW", "GW"), "p_bad2": fisher("HW", "GW", "bad2")}
    res["P2"]["sig"] = res["P2"]["p"] < 0.05
    gb = [m["g"] for m in models.values() if m["arm"] == "B" and not m["bad"]]
    gw = [m["g"] for m in models.values() if m["arm"] == "W" and not m["bad"]]
    harm = None
    if len(gb) >= 2 and len(gw) >= 2:
        u = mannwhitneyu(gw, gb, alternative="two-sided")
        harm = {"W_not_bad_median": float(np.median(gw)), "B_not_bad_median": float(np.median(gb)), "p": float(u.pvalue),
                "W_lower_sig": bool(u.pvalue < 0.05 and np.median(gw) < np.median(gb))}
    res["harm_check"] = harm
    use_w = arms["W"]["bad"] <= arms["B"]["bad"] and not (harm and harm["W_lower_sig"])
    res["recipe"] = "W" if use_w else "B"
    res["claim"] = ("균형 추출이 굶는 갈래를 줄인다(P1 유의)" if res["P1"]["sig"]
                    else "줄인다는 근거가 없다(P1 유의하지 않음, 방향만 기술)")
    chosen = arms[res["recipe"]]
    res["second_round_needed"] = bool(chosen["rate"] is not None and chosen["rate"] >= 0.25)
    # 기술: 먹이 재생 평균과 나쁨
    fr_bad = [m["world_fr"] for m in models.values() if m["bad"]]
    fr_ok = [m["world_fr"] for m in models.values() if not m["bad"]]
    res["world_fr"] = {"bad": [min(fr_bad), max(fr_bad)] if fr_bad else None,
                       "not_bad": [min(fr_ok), max(fr_ok)] if fr_ok else None}
    save_json(OUT / "judge.json", res)
    (OUT / "judge.md").write_text(render(res), encoding="utf-8")
    print(render(res))
    return 0


def render(res) -> str:
    A = res["arms"]
    L = ["# S1-a 판정 (PREREG 그대로)", "", f"- 생성 {res['generated']}. 나쁨(1차) = G_γ(결정, 평가 시드) ≤ {res['bad_threshold_g']:.3f}.",
         "", "| 팔 | 모델 | 나쁨 (1차) | 나쁨 (2차) | 실패율 [CP95] | G_γ 중앙값 [사분위] |", "|---|---|---|---|---|---|"]
    for arm in ("B", "W", "HW", "GW"):
        x = A[arm]
        if not x["n"]:
            L.append(f"| {arm} | 0 | — | — | — | — |")
            continue
        L.append(f"| {arm} | {x['n']} | {x['bad']} | {x['bad2']} | {x['rate']:.2f} [{x['cp95'][0]:.2f}, {x['cp95'][1]:.2f}] | "
                 f"{x['g_median']:.3f} [{x['g_q'][0]:.3f}, {x['g_q'][1]:.3f}] |")
    L += ["", f"- **P1 (대응)** {res['P1']['test']}: p {res['P1']['p']:.4f} → {'유의' if res['P1']['sig'] else '유의하지 않음'}"
          f" (2차 정의 p {res['P1']['p_bad2']:.4f})",
          f"- **P2 (원인)** {res['P2']['test']}: p {res['P2']['p']:.4f} → {'유의' if res['P2']['sig'] else '유의하지 않음'}"
          f" (2차 정의 p {res['P2']['p_bad2']:.4f})",
          f"- 해 점검(나쁘지 않은 모델 G_γ, W 대 B): {res['harm_check']}",
          f"- **주장**: {res['claim']}",
          f"- **레시피**: {res['recipe']} · 2차 대응 필요: {res['second_round_needed']}",
          f"- 학습 세계 먹이 재생 평균(기술): 나쁨 {res['world_fr']['bad']}, 나쁨 아님 {res['world_fr']['not_bad']}"]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------- #
# select (출시 모델, PREREG 4절)
# --------------------------------------------------------------------- #


def cmd_select(a) -> int:
    import probe_v2 as P
    from diagnose_v2 import EXPLORE_SEEDS
    from env_v2.config import load_v2_config
    from env_v2.rollout import make_executor, run_specs

    res = json.loads((OUT / "judge.json").read_text(encoding="utf-8"))
    arm = res["recipe"]
    names = sorted(n for n, m in res["models"].items() if m["arm"] == arm)
    cfg = load_v2_config(ROOT / "configs" / "v2_1.yaml")
    path = OUT / "select_eval.json"
    d = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"rows": {}}
    ex = make_executor(a.workers)
    try:
        for n in names:
            for m in ("det", "hold"):
                key = f"{n}|{m}"
                if key in d["rows"]:
                    continue
                d["rows"][key] = _rows(run_specs(cfg, {key: _spec(n, m)}, list(EXPLORE_SEEDS), 5000, gamma=GAMMA,
                                                 executor=ex)[key])
                save_json(path, d)
            print(f"  {n}", flush=True)
    finally:
        if ex is not None:
            ex.shutdown()
    # 모드 (R1·S1-c): 팔 모델 평균 시계열의 K24 − 결정 짝 t, 유의하지 않으면 결정
    g = {m: np.mean([[r["g_gamma"] for r in sorted(d["rows"][f"{n}|{m}"], key=lambda r: r["seed"])] for n in names], 0)
         for m in ("det", "hold")}
    t = P._paired_t(g["hold"], g["det"])
    mode = ("hold" if t["diff"] > 0 else "det") if t["sig"] else "det"
    cand = []
    for n in names:
        rows = d["rows"][f"{n}|{mode}"]
        cand.append({"name": n, "g": _mean(rows, "g_gamma"), "starve": _mean(rows, "starve_rate"), "b1": _mean(rows, "b1")})
    ok = [c for c in cand if c["starve"] <= 1.5 * C2_STARVE_EXPLORE and c["b1"] >= 0.3]
    rule = "아사율 ≤ 1.5 × C2_탐색, B1 ≥ 0.3"
    if not ok:
        ok = [c for c in cand if c["starve"] <= 1.5 * C2_STARVE_EXPLORE]
        rule = "B1 조건을 뺌(PREREG 4절)"
    pick = max(ok, key=lambda c: (c["g"], -int(c["name"].rsplit("s", 1)[1]))) if ok else None
    out = {"arm": arm, "mode": mode, "mode_t": t, "rule": rule, "candidates": cand, "pick": pick,
           "pick_eval_seeds": res["models"].get(pick["name"]) if pick else None,
           "fallback": None if pick else "v2_1c_s34 유지"}
    save_json(OUT / "select.json", out)
    print(json.dumps({k: out[k] for k in ("arm", "mode", "rule", "pick", "fallback")}, ensure_ascii=False, indent=1))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--concurrency", type=int, default=16)
    t.add_argument("--poll", type=float, default=30.0)
    e = sub.add_parser("eval")
    e.add_argument("--workers", type=int, default=16)
    sub.add_parser("judge")
    s = sub.add_parser("select")
    s.add_argument("--workers", type=int, default=16)
    a = p.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    return {"train": cmd_train, "eval": cmd_eval, "judge": cmd_judge, "select": cmd_select}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
