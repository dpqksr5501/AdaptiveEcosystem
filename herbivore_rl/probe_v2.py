"""v2.2r 탐색 배치 — 학습 가능성 탐침 (10-03 R2·R6·R7·R8, 수정 제안서 3.2·3.8, 5절 #5·#7).

    python probe_v2.py train            # 팔 4개 × 학습 시드를 동시에 20M 학습, 2M·5M 조기 중단 감시
    python probe_v2.py eval             # 탐색 시드 12000~12039 에서 두 모드(결정·K24 유지)·대조군·기준선 평가
    python probe_v2.py judge            # 선택 규칙 (i)~(iv)·미리 정한 갈림 1~7 → judge.md·judge.json

탐색층이다(R7): 평가 시드 10000~10019 는 쓰지 않고 결과를 주장에 쓰지 않는다. 규칙·팔·예산은 학습 전에 적은 탐색
메모 `results/v2/v2_2r_explore/MEMO.md` 그대로다. 결과는 같은 폴더에 남는다.

팔 (MEMO 2절, 수정 제안서 3.8 표):
- T0  configs/v2_1.yaml     v2.1 을 새 학습 시드로 재학습 (기준)
- T1  configs/v2_2r_t1.yaml v2.1 + 관측 8(threat_recency), 경계 행동 열 없음 (L 의 대조군)
- L   configs/v2_2r_l.yaml  T1 + 반사 돌아보기 (1순위)
- W   configs/v2_2r_w.yaml  v2.2 + 창 경계(L 형 계수), 시작 편향 0 (보조 팔 W′)
- CM  configs/v2_2r_cm.yaml Categorical(4){정지, 걷기, 뛰기, look} + 창 밖 look 마스크, W′ 세계 (갈림 3, MEMO 9절)
      python probe_v2.py train --arms CM

학습 중 탐침 기록은 `train_v2.py --probe-every 1000000` 의 `<체크포인트>.probe.jsonl` 이다. 조기 중단(MEMO 3절):
L 은 b3_l_prob, W 는 p_vig_win 이 2M 또는 5M 기록에서 시드 절반 이상(올림) 0.01 미만이면 그 팔의 남은 학습을 멈춘다.

평가 기준선 (학습 없음):
- C2   E2 C2 상수(앞 5열)를 T1 세계에서. T0·T1·L 세계에서 상수의 동역학이 같다(관측만 다르다)
- C2W  C2 + 경계 1 을 W 세계에서 (C2_W′ = 'C2 + 창 경계 상수', C2-seg-L 근사와 같은 정책)
- OVL  v2.1 원 모델(ckpt/v2/v2_1_s0~2) + 창 규칙(창 안이면 speed 정지 → L 반사)을 L 세계에서, 결정 모드
- V21  v2.1 원 모델 그대로 L 세계에서, 결정 모드 (OVL − V21 = 덧씌우기 이득, 갈림 5 (a))
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "v2" / "v2_2r_explore"
CKPT = ROOT / "ckpt" / "v2"

STEPS = 20_000_000
PROBE_EVERY = 1_000_000
EARLY_AT = (2_000_000, 5_000_000)
EARLY_BELOW = 0.01
EVAL_STEPS = 5000
GAMMA = 0.9916661555611042
HOLD_K = 24
T_CRIT = 2.023                     # 탐색 시드 40개 짝 t, 자유도 39 (수정 제안서 표기)

ARMS = {
    "T0": {"config": "configs/v2_1.yaml", "seeds": [20, 21, 22], "use": None},
    "T1": {"config": "configs/v2_2r_t1.yaml", "seeds": [20, 21, 22], "use": None},
    "L": {"config": "configs/v2_2r_l.yaml", "seeds": [20, 21, 22],
          "use": {"probe": "b3_l_prob", "eval": "b3_l", "min": 0.1}},
    "W": {"config": "configs/v2_2r_w.yaml", "seeds": [20, 21],
          "use": {"probe": "p_vig_win", "eval": "p_vig_win", "min": 0.05}, "w_type": True},
    # 갈림 3 (MEMO 9절): W′ 와 같은 기준. 탐침 p_vig_win = 창 안 P(look)
    "CM": {"config": "configs/v2_2r_cm.yaml", "seeds": [20, 21, 22],
           "use": {"probe": "p_vig_win", "eval": "p_vig_win", "min": 0.05}, "w_type": True},
}
# E2 최적 상수 C2 (results/v2/e2/V0/c2/constsearch.json best, 6열). T1·L 세계는 앞 5열을 쓴다
C2_FILE = ROOT / "results" / "v2" / "e2" / "V0" / "c2" / "constsearch.json"
V21_MODELS = [CKPT / f"v2_1_s{i}.zip" for i in range(3)]
MODES = {"det": {}, "hold": {"mode": "hold", "hold_k": HOLD_K}}


def run_name(arm: str, seed: int) -> str:
    return f"v2_2r_{arm.lower()}_s{seed}"


def model_path(arm: str, seed: int) -> Path:
    return CKPT / f"{run_name(arm, seed)}.zip"


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, allow_nan=True), encoding="utf-8")


def read_probe(arm: str, seed: int) -> list[dict]:
    p = model_path(arm, seed).with_suffix(".probe.jsonl")
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def probe_at(rows: list[dict], at: int) -> dict | None:
    """`at` 스텝 이후 첫 기록 (롤아웃 끝마다 재므로 실제 스텝은 at 보다 조금 크다)."""
    for r in rows:
        if r["timesteps"] >= at:
            return r
    return None


# --------------------------------------------------------------------- #
# 평가 래퍼 (rollout make_wrapper 의 factory, "probe_v2:obs_take" 꼴)
# --------------------------------------------------------------------- #


class _Wrap:
    def observe_done(self, done):
        f = getattr(self.base, "observe_done", None)
        if f is not None:
            f(done)


class ObsTake(_Wrap):
    """관측 열 `dims` 만 바탕 정책에 넣는다 (관측 7 모델을 관측 8 세계에서 돌린다)."""

    def __init__(self, base, spec):
        self.base, self.dims = base, list(spec["dims"])

    def __call__(self, obs):
        return self.base(np.asarray(obs)[:, self.dims])


class WindowStop(_Wrap):
    """창 안(관측 1 = 0 & 관측 `tr_col` > theta) 개체의 speed 열을 정지 값 0 으로 덮는다 — 규칙 덧씌우기 기준선 OVL.
    L 세계에서는 정지 + 창 안이라 반사 돌아보기가 돈다(수정 제안서 부록 D.1 의 L 형 덧씌우기와 같은 동역학)."""

    def __init__(self, base, spec):
        self.base = base
        self.col, self.tr, self.theta = int(spec["speed_col"]), int(spec["tr_col"]), float(spec["theta"])

    def __call__(self, obs):
        a = np.array(self.base(obs), dtype=np.float64)
        o = np.asarray(obs)
        win = (o[:, 1] <= 0.0) & (o[:, self.tr] > self.theta)
        a[win, self.col] = 0.0
        return a


def obs_take(base, spec, seed):
    return ObsTake(base, spec)


def window_stop(base, spec, seed):
    return WindowStop(base, spec)


# --------------------------------------------------------------------- #
# train
# --------------------------------------------------------------------- #


def cmd_train(args) -> int:
    logs = OUT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    jobs = {}
    arms = args.arms or list(ARMS)
    for arm, a in ARMS.items():
        if arm not in arms:
            continue
        for s in a["seeds"]:
            name = run_name(arm, s)
            if model_path(arm, s).exists() and not args.force:
                print(f"{name}: 이미 있다 — 건너뛴다 (--force 로 다시)")
                continue
            cmd = [sys.executable, "train_v2.py", "--config", a["config"], "--steps", str(args.steps),
                   "--seed", str(s), "--run-name", name, "--probe-every", str(PROBE_EVERY),
                   "--threads", str(args.threads)]
            log = open(logs / f"train_{name}.log", "w", encoding="utf-8")
            jobs[(arm, s)] = {"proc": subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT),
                              "log": log, "cmd": " ".join(cmd[1:])}
            print(f"시작 {name}: {' '.join(cmd[1:])}", flush=True)
    # 배치마다 상태 파일을 따로 둔다(동시에 도는 배치가 서로 덮지 않게). judge 는 train_status*.json 을 모두 읽는다
    sp = OUT / ("train_status.json" if args.arms is None else f"train_status_{'_'.join(arms)}.json")
    status = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "steps": args.steps,
              "arms": arms, "early_stop": {}, "runs": {}}
    checked = {arm: set() for arm in ARMS}
    while jobs and any(j["proc"].poll() is None for j in jobs.values()):
        time.sleep(args.poll)
        for arm, a in ARMS.items():
            use = a["use"]
            if use is None or arm in status["early_stop"] or arm not in arms:
                continue
            seeds = a["seeds"]
            for at in EARLY_AT:
                if at in checked[arm] or at > args.steps:
                    continue
                rows = {s: probe_at(read_probe(arm, s), at) for s in seeds}
                if any(r is None for r in rows.values()):
                    continue                    # 아직 그 시점까지 오지 않은 시드가 있다
                checked[arm].add(at)
                vals = {s: r.get(use["probe"]) for s, r in rows.items()}
                low = [s for s, v in vals.items() if v is None or v < EARLY_BELOW]
                print(f"[{arm} {at / 1e6:g}M] {use['probe']} = "
                      + ", ".join(f"s{s} {v if v is None else round(v, 4)}" for s, v in vals.items()), flush=True)
                if len(low) >= math.ceil(len(seeds) / 2):
                    status["early_stop"][arm] = {"at": at, "values": vals, "low_seeds": low}
                    for s in seeds:
                        j = jobs.get((arm, s))
                        if j is not None and j["proc"].poll() is None:
                            j["proc"].terminate()
                    print(f"[{arm}] 조기 중단: {at / 1e6:g}M 에서 {len(low)}/{len(seeds)} 시드가 {EARLY_BELOW} 미만",
                          flush=True)
                    break
        for (arm, s), j in jobs.items():
            status["runs"][run_name(arm, s)] = {"returncode": j["proc"].poll(), "cmd": j["cmd"]}
        save_json(sp, status)
    for (arm, s), j in jobs.items():
        j["proc"].wait()
        j["log"].close()
        status["runs"][run_name(arm, s)] = {"returncode": j["proc"].returncode, "cmd": j["cmd"],
                                            "model": rel(model_path(arm, s)) if model_path(arm, s).exists() else None}
    status["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_json(sp, status)
    bad = [n for n, r in status["runs"].items() if r["returncode"] not in (0, None)
           and not any(n.startswith(f"v2_2r_{arm.lower()}_") for arm in status["early_stop"])]
    print("학습 끝" + (f" — 실패: {bad}" if bad else ""), flush=True)
    return 1 if bad else 0


# --------------------------------------------------------------------- #
# eval
# --------------------------------------------------------------------- #


def _rows(res) -> list[dict]:
    from env_v2.rollout import public_row

    return [public_row(r) for r in res]


def _learned(path: Path, mode: str) -> dict:
    return {"kind": "learned", "model": str(Path(path).resolve()), **MODES[mode]}


def _paired_t(a, b) -> dict:
    """짝 t (a − b). 시드마다 한 값."""
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    n = len(d)
    sd = float(d.std(ddof=1)) if n > 1 else float("nan")
    t = float(d.mean() / (sd / math.sqrt(n))) if n > 1 and sd > 0 else float("nan")
    return {"diff": float(d.mean()), "sd": sd, "t": t, "sig": bool(math.isfinite(t) and abs(t) > T_CRIT)}


def trained_models() -> dict[str, list[tuple[int, Path]]]:
    out = {}
    for arm, a in ARMS.items():
        got = [(s, model_path(arm, s)) for s in a["seeds"] if model_path(arm, s).exists()]
        if got:
            out[arm] = got
    return out


def cmd_eval(args) -> int:
    """평가는 잡(스펙 키)마다 저장하고, 다시 부르면 없는 잡만 돈다. 조건(시드·스텝·γ·K·C2·v2.1 모델)이 다르거나
    모델 파일이 바뀌면(sha1) 그 잡을 다시 잰다. 그래서 CM 처럼 뒤에 학습한 팔은 그 팔만 더 잰다."""
    from diagnose_v2 import EXPLORE_SEEDS, model_fingerprint
    from env_v2.config import load_v2_config
    from env_v2.rollout import make_executor, run_specs
    from env_v2.world import OBS_THREAT_RECENCY

    seeds = list(EXPLORE_SEEDS)
    steps = args.steps
    cfgs = {arm: load_v2_config(ROOT / a["config"]) for arm, a in ARMS.items()}
    c2 = json.loads(C2_FILE.read_text(encoding="utf-8"))["best"]
    models = trained_models()
    sha = {f"{arm}_s{s}": model_fingerprint(p) for arm, ms in models.items() for s, p in ms}
    cond = {"seeds": seeds, "steps": steps, "gamma": GAMMA, "hold_k": HOLD_K, "c2": c2,
            "v21_models": {p.name: model_fingerprint(p) for p in V21_MODELS}}

    def load(path):
        if path.exists() and not args.force:
            d = json.loads(path.read_text(encoding="utf-8"))
            if d.get("cond") == cond:
                return d
        return {"cond": cond, "rows": {}, "sha1": {}, "mean_energy": {}}

    def fresh(d, key, model_key=None):
        return key in d["rows"] and (model_key is None or d["sha1"].get(key) == sha.get(model_key))

    def run(d, cfg, specs, model_key=None):
        todo = {k: v for k, v in specs.items() if not fresh(d, k, model_key)}
        if not todo:
            return
        for k, rows in run_specs(cfg, todo, seeds, steps, gamma=GAMMA, executor=ex).items():
            d["rows"][k] = _rows(rows)
            if model_key is not None:
                d["sha1"][k] = sha[model_key]
            if "|C0|" in k:       # C4-energy 고정값 = 그 모델·모드 C0 롤아웃의 평균 관측 4 (diagnose_v2 C4-j 와 같은 규칙)
                d["mean_energy"][k] = float(sum(r["_obs_sum"][4] for r in rows) / sum(r["_act_n"] for r in rows))

    p1, p2 = OUT / "eval_p1.json", OUT / "eval_p2.json"
    ex = make_executor(args.workers)
    try:
        d1 = load(p1)
        t0 = time.time()
        for arm, ms in models.items():
            for s, p in ms:
                run(d1, cfgs[arm], {f"{arm}_s{s}|C0|{m}": _learned(p, m) for m in MODES}, f"{arm}_s{s}")
            save_json(p1, d1)
            print(f"  {arm} C0 두 모드 ({time.time() - t0:.0f}s)", flush=True)
        base = {"C2": (cfgs["T1"], {"kind": "fixed", "action": list(c2[:5])}),
                "C2W": (cfgs["W"], {"kind": "fixed", "action": list(c2[:5]) + [1.0]})}
        take = {"factory": "probe_v2:obs_take", "dims": list(range(7))}
        stop = {"factory": "probe_v2:window_stop", "speed_col": 4, "tr_col": OBS_THREAT_RECENCY,
                "theta": cfgs["L"].v2["features"]["vigil_window"]["theta"]}
        for i, p in enumerate(V21_MODELS):
            base[f"V21_s{i}"] = (cfgs["L"], {"policy": _learned(p, "det"), "wrap": [take]})
            base[f"OVL_s{i}"] = (cfgs["L"], {"policy": _learned(p, "det"), "wrap": [take, stop]})
        for k, (cfg, spec) in base.items():
            run(d1, cfg, {k: spec})
        save_json(p1, d1)
        print(f"  기준선 ({time.time() - t0:.0f}s)", flush=True)

        modes = choose_modes(d1)
        d2 = load(p2)
        for arm in [x for x, a in ARMS.items() if a["use"] is not None]:
            if arm not in models:
                continue
            m = modes[arm]["mode"]
            for s, p in models[arm]:
                specs = {f"{arm}_s{s}|C1p|{m}": {"policy": _learned(p, m),
                                                "wrap": [{"kind": "act_permute", "salt": 0}]}}
                if ARMS[arm].get("w_type"):
                    e = d1["mean_energy"][f"{arm}_s{s}|C0|{m}"]
                    specs[f"{arm}_s{s}|C4e|{m}"] = {"policy": _learned(p, m),
                                                    "wrap": [{"kind": "obs_fix", "dims": [4], "values": [e]}]}
                run(d2, cfgs[arm], specs, f"{arm}_s{s}")
            save_json(p2, d2)
            print(f"  {arm} C1′·C4 ({time.time() - t0:.0f}s)", flush=True)
    finally:
        if ex is not None:
            ex.shutdown()
    return 0


# --------------------------------------------------------------------- #
# judge
# --------------------------------------------------------------------- #


def _col(rows, key):
    return np.array([r.get(key, float("nan")) for r in sorted(rows, key=lambda r: r["seed"])], dtype=np.float64)


def arm_series(d: dict, arm: str, kind: str, mode: str, key: str = "g_gamma"):
    """팔의 시드 평균(모델 평균) 시계열 — 탐색 시드마다 한 값. 모델 키는 `{arm}_s{seed}|{kind}|{mode}`."""
    ks = [k for k in d["rows"] if k.startswith(f"{arm}_s") and k.endswith(f"|{kind}|{mode}")]
    if not ks:
        return None
    return np.mean([_col(d["rows"][k], key) for k in ks], axis=0)


def base_series(d: dict, prefix: str, key: str = "g_gamma"):
    ks = [k for k in d["rows"] if k == prefix or k.startswith(prefix + "_s")]
    return np.mean([_col(d["rows"][k], key) for k in ks], axis=0)


MODE_TIE_RULES = ("passes", "det")


def choose_modes(d1: dict, tie: str = "passes") -> dict:
    """팔마다 출시 모드 (R1, 수정 제안서 3.1 (가) 3): 팔 평균 G_γ 가 유의하게 높은 모드. 유의하지 않을 때는 `tie` 로 정한다.

    - tie="passes" (v2.2r 탐색 메모 5절, 학습 전 규칙 — 이 배치의 판정은 이것으로 재현한다): 크기 통과(새 결정 사용
      지표 ≥ 기준, B1 ≥ 0.3) 수가 많은 모드, 같으면 결정.
    - tie="det" (10-03 결정 S1-c, 다음 버전부터): 결정 모드. 크기 통과 수 단계를 뺀다(3모델 K24 ↔ 6모델 결정으로
      뒤집힌 T0 사례, `results/v2/stage1_close.md` 8절). 크기 통과 수는 기록만 한다.
    """
    if tie not in MODE_TIE_RULES:
        raise ValueError(f"tie 는 {MODE_TIE_RULES} 중 하나다: {tie!r}")
    out = {}
    for arm, a in ARMS.items():
        g = {m: arm_series(d1, arm, "C0", m) for m in MODES}
        if g["det"] is None:
            continue
        t = _paired_t(g["hold"], g["det"])
        passes = {}
        for m in MODES:
            n = int(np.nanmean(arm_series(d1, arm, "C0", m, "b1")) >= 0.3)
            if a["use"] is not None:
                n += int(np.nanmean(arm_series(d1, arm, "C0", m, a["use"]["eval"])) >= a["use"]["min"])
            passes[m] = n
        if t["sig"]:
            mode, why = ("hold" if t["diff"] > 0 else "det"), "G_γ 유의"
        elif tie == "passes" and passes["hold"] != passes["det"]:
            mode, why = max(passes, key=passes.get), "크기 통과 수"
        else:
            mode, why = "det", ("같음 → 결정" if tie == "passes" else "유의하지 않음 → 결정 (S1-c)")
        out[arm] = {"mode": mode, "why": why, "hold_minus_det": t, "passes": passes,
                    "g": {m: float(g[m].mean()) for m in MODES}}
    return out


def cmd_judge(args) -> int:
    d1 = json.loads((OUT / "eval_p1.json").read_text(encoding="utf-8"))
    p2 = OUT / "eval_p2.json"
    d2 = json.loads(p2.read_text(encoding="utf-8")) if p2.exists() else {"rows": {}}
    st = {"early_stop": {}}
    for f in sorted(OUT.glob("train_status*.json")):
        st["early_stop"].update(json.loads(f.read_text(encoding="utf-8")).get("early_stop", {}))
    modes = choose_modes(d1)
    c2, c2w = base_series(d1, "C2"), base_series(d1, "C2W")
    ovl, v21 = base_series(d1, "OVL"), base_series(d1, "V21")
    c2_starve = float(base_series(d1, "C2", "starve_rate").mean())
    res = {"early_stop": st["early_stop"], "modes": modes,
           "baselines": {"C2": float(c2.mean()), "C2W": float(c2w.mean()), "OVL": float(ovl.mean()),
                         "V21": float(v21.mean()), "OVL_minus_V21": _paired_t(ovl, v21),
                         "C2_starve_rate": c2_starve},
           "arms": {}}
    for arm, a in ARMS.items():
        if arm not in modes:
            res["arms"][arm] = {"trained": False, "early_stop": st["early_stop"].get(arm)}
            continue
        m = modes[arm]["mode"]
        g = arm_series(d1, arm, "C0", m)
        r = {"trained": True, "mode": m, "g": float(g.mean()),
             "per_model": {k.split("|")[0]: float(_col(v, "g_gamma").mean())
                           for k, v in d1["rows"].items() if k.startswith(f"{arm}_s") and k.endswith(f"|C0|{m}")},
             "b1": float(np.nanmean(arm_series(d1, arm, "C0", m, "b1"))),
             "b2": float(np.nanmean(arm_series(d1, arm, "C0", m, "b2"))),
             "starve_rate": float(np.nanmean(arm_series(d1, arm, "C0", m, "starve_rate"))),
             "vs_C2": _paired_t(g, c2), "vs_OVL": float(g.mean() - ovl.mean())}
        checks = {}
        if a["use"] is not None:
            u = a["use"]
            pr = {at: [((probe_at(read_probe(arm, s), at) or {}).get(u["probe"])) for s in a["seeds"]]
                  for at in EARLY_AT}
            pm = {at: (float(np.mean(v)) if all(x is not None for x in v) else None) for at, v in pr.items()}
            ev = float(np.nanmean(arm_series(d1, arm, "C0", m, u["eval"])))
            r["use"] = {"metric": u, "probe": {f"{at / 1e6:g}M": pm[at] for at in EARLY_AT}, "eval_20M": ev,
                        "probe_per_seed": {f"{at / 1e6:g}M": pr[at] for at in EARLY_AT}}
            checks["i"] = all(v is not None and v >= u["min"] for v in pm.values()) and ev >= u["min"]
            c1p = arm_series(d2, arm, "C1p", m)
            r["vs_C1p"] = _paired_t(g, c1p) if c1p is not None else None
            checks["ii_a"] = (r["vs_C2"]["diff"] > 0 and r["vs_C2"]["t"] > T_CRIT and r["vs_C1p"] is not None
                              and r["vs_C1p"]["diff"] > 0 and r["vs_C1p"]["t"] > T_CRIT)
            checks["ii_b"] = r["g"] >= float(ovl.mean()) - 0.3
            checks["iii"] = r["starve_rate"] <= 1.5 * c2_starve
            checks["iv"] = r["b1"] >= 0.3
            if a.get("w_type"):
                r["vs_C2W"] = _paired_t(g, c2w)
                c4 = arm_series(d2, arm, "C4e", m, "p_vig_win")
                c0v = arm_series(d1, arm, "C0", m, "p_vig_win")
                r["c4_energy_p_vig_win"] = _paired_t(c4, c0v) if c4 is not None else None
                checks["ii_c"] = (r["vs_C2W"]["diff"] > 0 and r["vs_C2W"]["t"] > T_CRIT
                                  and r["c4_energy_p_vig_win"] is not None
                                  and r["c4_energy_p_vig_win"]["t"] < -T_CRIT)
            r["pass"] = all(checks.values())
        r["checks"] = checks
        res["arms"][arm] = r
    # 갈림 4: T1 이 T0 보다 0.3 이상 낮고 3 대 3 완전 분리
    t0a, t1a = res["arms"].get("T0", {}), res["arms"].get("T1", {})
    sep = None
    if t0a.get("trained") and t1a.get("trained"):
        sep = {"T1_minus_T0": t1a["g"] - t0a["g"],
               "full_split": max(t1a["per_model"].values()) < min(t0a["per_model"].values())}
        sep["flag"] = sep["T1_minus_T0"] <= -0.3 and sep["full_split"]
    res["t1_vs_t0"] = sep
    ok = {arm: res["arms"].get(arm, {}).get("pass", False) for arm in ("L", "W", "CM")}
    ovl_sig = res["baselines"]["OVL_minus_V21"]
    if ok["L"]:
        branch = "1: L 통과 → L 로 확인층"
    elif ok["W"]:
        branch = "2: L 실패·W′ 통과 → W′ 로 확인층"
    elif sep is not None and sep["flag"]:
        branch = "4: T1 이 T0 보다 0.3 이상 낮고 완전 분리 → 하루 조사 상자, 그다음 대체안"
    elif not res["arms"].get("CM", {}).get("trained"):
        branch = "3: L·W′ 실패 → CM 1회"
    elif ok["CM"]:
        branch = "3: L·W′ 실패, CM 통과 → CM 으로 확인층"
    elif ovl_sig["diff"] > 0 and ovl_sig["t"] > T_CRIT:
        branch = "5 (a): CM 도 실패, OVL − V21 유의 → 규칙 장면(v2.1 + 창 규칙), v2.1 을 시드 30~34 로 확인"
    else:
        branch = "5 (b): CM 도 실패, OVL − V21 유의하지 않음 → v2.1 확인 후 1단계를 'S1만'으로 닫는다"
    res["branch"] = branch
    res["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_json(OUT / "judge.json", res)
    (OUT / "judge.md").write_text(render(res), encoding="utf-8")
    print(render(res))
    return 0


def _f(x, nd=3):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.{nd}f}" if isinstance(x, float) \
        else str(x)


def render(res: dict) -> str:
    b = res["baselines"]
    L = [f"# v2.2r 탐색 배치 판정 (탐색층 — 주장에 쓰지 않는다)", "",
         f"- 생성: {res['generated']}, 규칙: `MEMO.md`, 원본: `judge.json`·`eval_p1.json`·`eval_p2.json`",
         f"- **갈림: {res['branch']}**", "",
         "| 팔 | 모드 | G_γ | − C2 (t) | − C1′ (t) | − OVL | 사용 2M / 5M / 20M | B1 | 아사율 | (i) (ii-a) (ii-b) (ii-c) (iii) (iv) | 통과 |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm, r in res["arms"].items():
        if not r.get("trained"):
            L.append(f"| {arm} | — | 학습 없음 (조기 중단 {r.get('early_stop')}) | | | | | | | | 아니오 |")
            continue
        u = r.get("use")
        use = (f"{_f(u['probe']['2M'])} / {_f(u['probe']['5M'])} / {_f(u['eval_20M'])}" if u else "—")
        ck = " ".join(f"{k}:{'O' if v else 'X'}" for k, v in r["checks"].items()) or "—"
        c1p = r.get("vs_C1p")
        L.append(f"| {arm} | {r['mode']} | {r['g']:.3f} | {_f(r['vs_C2']['diff'])} ({_f(r['vs_C2']['t'], 2)}) | "
                 + (f"{_f(c1p['diff'])} ({_f(c1p['t'], 2)})" if c1p else "—")
                 + f" | {_f(r['vs_OVL'])} | {use} | {r['b1']:.3f} | {r['starve_rate']:.5f} | {ck} | "
                 + ("예" if r.get("pass") else ("아니오" if "pass" in r else "—")) + " |")
    L += ["", f"- 기준선 G_γ: C2 {b['C2']:.3f}, C2_W′ {b['C2W']:.3f}, OVL {b['OVL']:.3f}, V21 {b['V21']:.3f} "
          f"(OVL − V21 {_f(b['OVL_minus_V21']['diff'])}, t {_f(b['OVL_minus_V21']['t'], 2)}), C2 아사율 "
          f"{b['C2_starve_rate']:.5f}", ""]
    L.append("**모드 선택 (R1)**")
    for arm, m in res["modes"].items():
        L.append(f"- {arm}: {m['mode']} ({m['why']}) — 결정 {m['g']['det']:.3f}, K24 {m['g']['hold']:.3f}, "
                 f"K24 − 결정 {_f(m['hold_minus_det']['diff'])} (t {_f(m['hold_minus_det']['t'], 2)}), "
                 f"크기 통과 {m['passes']}")
    if res.get("t1_vs_t0"):
        s = res["t1_vs_t0"]
        L += ["", f"- T1 − T0 {_f(s['T1_minus_T0'])}, 완전 분리 {s['full_split']} → 갈림 4 신호 {s['flag']}"]
    for arm in ("L", "W", "CM"):
        r = res["arms"].get(arm, {})
        if r.get("trained") and r.get("use"):
            L.append(f"- {arm} 시드별 탐침 {r['use']['probe_per_seed']}, 모델별 G_γ {r['per_model']}")
    for arm in ("W", "CM"):
        r = res["arms"].get(arm, {})
        if r.get("c4_energy_p_vig_win"):
            c = r["c4_energy_p_vig_win"]
            L.append(f"- {arm} C4-energy 고정 − C0 의 창 안 경계 비율 {_f(c['diff'])} (t {_f(c['t'], 2)}), "
                     f"C0 − C2_W′ {_f(r['vs_C2W']['diff'])} (t {_f(r['vs_C2W']['t'], 2)})")
    if res["early_stop"]:
        L.append(f"- 조기 중단: {res['early_stop']}")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--steps", type=int, default=STEPS)
    t.add_argument("--threads", type=int, default=1)
    t.add_argument("--poll", type=float, default=30.0)
    t.add_argument("--force", action="store_true")
    t.add_argument("--arms", nargs="+", choices=list(ARMS), default=None, help="학습할 팔 (기본 전부)")
    e = sub.add_parser("eval")
    e.add_argument("--steps", type=int, default=EVAL_STEPS)
    e.add_argument("--workers", type=int, default=16)
    e.add_argument("--force", action="store_true")
    sub.add_parser("judge")
    args = p.parse_args(argv)
    return {"train": cmd_train, "eval": cmd_eval, "judge": cmd_judge}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
