"""R8 평가 — 보정 관문 C0·새는 길 시험·판정 평가·곰 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R8_LEARN_DANGER_DESIGN.md 8~10절).

`herbivore_rl/` 에서 (PYTHONUTF8=1):
    python results/v3/r8/eval_r8.py calibrate --config configs/v3_r8_pilot.yaml --seeds 41400 41449 --steps 3000   # C0-1·2·4
    python results/v3/r8/eval_r8.py leak --config configs/v3_r8_pilot.yaml --seeds 41400 41449                     # C0-3
    python results/v3/r8/eval_r8.py eval --config configs/v3_r8_pilot.yaml --models ckpt/r8/r8_p_s0.zip ... \
        --baselines random always_eat rule_blind rule_oracle --seeds 41900 41999 --steps 3000 --out results/v3/r8/eval
    python results/v3/r8/eval_r8.py bear --config configs/v3_r8_pilot.yaml --models ckpt/r8/r8_p_s0.zip ... --bears 2 \
        --seeds 41900 41999 --steps 3000 --out results/v3/r8/eval/bear

정책 (설계 8-2): random(결정마다 11 칸 균등, 세계의 평가 갈래 난수), always_eat(늘 0), rule_blind(가장 가까운 느낀 동물이 15 단위 안이고
approach > 0.1 이면 도망 — 은신처 가장자리 8 단위 안이면 SHELTER, 아니면 그 동물 반대에 가까운 뛰기 방향 가운데 free > 0.2 인 것, 아니면 먹기),
rule_oracle(같은 규칙을 느낀 늑대에게만 — 숨은 종류를 쓰는 R7e 식 손규칙), 모델 zip(결정적: 가장 높은 확률 칸).
모든 정책은 같은 시드의 같은 시작 세계에서 돈다(세계 K 개를 한 묶음으로 — 세계마다 난수 갈래가 따로라 묶음과 무관하다).

지표 (설계 8-3): 잡힘·굶음·번식 1000 사슴-스텝당, 먹은 에너지 사슴-스텝당 × 1000, 행동 몫, 은신처 안 몫, 도망 몫 차이
Δ = Σ_b w_b (F_w(b) − F_h(b)) (b = 거리 띠 [0,5)·[5,10)·[10,15), w_b = 띠의 두 표본 수 합 / 전체 — 두 쪽 표본이 다 있는 띠만), ρ = Σ w F_w / Σ w F_h,
95% 구간 = 세계 되뽑기 2000 번 백분위. 보고만: (가) 15 안 유일한 동물, (나) 동족이 뛰지 않을 때, (다) 다가옴 띠까지 맞춘 Δ, (라) 먹는 늑대 대 짐승,
도망 방향 cos, 도망 시작 거리 중앙값.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저

import numpy as np  # noqa: E402

from env_v2.r8_world import (A0, ACTION_NAMES, EAT, K_BEAR, K_BEAST, K_WOLF, N_ACTIONS, NA, N_SLOTS, OBS_DIM,  # noqa: E402
                             SHELTER, R8World, load_r8_config, override)

BOOT = 2000
BOOT_SEED = 41999
SC = {c: i for i, c in enumerate(R8World.SAMPLE_COLUMNS)}


# --------------------------------------------------------------------------- #
# 정책
# --------------------------------------------------------------------------- #

def rule_actions(obs: np.ndarray, world: R8World | None, oracle: bool) -> np.ndarray:
    """rule_blind / rule_oracle (설계 8-2). obs (K, N, 65). oracle 이면 느낀 늑대 칸만 본다(숨은 종류 — world.obs_slot_anim·kind)."""
    K, N, _ = obs.shape
    o = obs.reshape(K * N, OBS_DIM)
    slot = np.zeros(K * N, dtype=np.int64)
    pres = o[:, A0] > 0.5
    if oracle:
        ids = world.obs_slot_anim.reshape(K * N, N_SLOTS)
        kk = np.repeat(np.arange(K), N)
        kinds = np.where(ids >= 0, world.kind[kk[:, None], np.maximum(ids, 0)], 0)
        isw = kinds == K_WOLF
        pres = isw.any(1)
        slot = np.argmax(isw, 1)                         # 가장 가까운 느낀 늑대 칸
    c = A0 + slot * NA
    r = np.arange(K * N)
    rel_x, rel_y, dist, appr = o[r, c + 1], o[r, c + 2], o[r, c + 3], o[r, c + 6]
    trig = pres & (dist < 15.0 / 20.0) & (appr > 0.1)
    act = np.full(K * N, EAT, dtype=np.int64)
    near_sh = o[:, 7] < 8.0 / 20.0
    away = np.arctan2(-rel_y, -rel_x)
    cosj = np.cos(away[:, None] - np.arange(8)[None, :] * (math.pi / 4.0))
    free = o[:, 8:16] > 0.2
    score = np.where(free, cosj, cosj - 10.0)
    run = 1 + np.argmax(score, 1)
    act = np.where(trig, np.where(near_sh, SHELTER, run), act)
    return act.reshape(K, N)


class ModelPolicy:
    def __init__(self, path: str):
        from stable_baselines3 import PPO

        self.model = PPO.load(path, device="cpu")
        self.path = path

    def __call__(self, obs: np.ndarray, world: R8World) -> np.ndarray:
        K, N, _ = obs.shape
        a, _ = self.model.predict(obs.reshape(K * N, OBS_DIM), deterministic=True)
        return np.asarray(a, dtype=np.int64).reshape(K, N)


def make_policy(name: str):
    if name == "random":
        return lambda obs, w: np.stack([w.rng_pol[k].integers(0, N_ACTIONS, w.N) for k in range(w.K)])
    if name == "always_eat":
        return lambda obs, w: np.zeros((w.K, w.N), dtype=np.int64)
    if name == "rule_blind":
        return lambda obs, w: rule_actions(obs, w, oracle=False)
    if name == "rule_oracle":
        return lambda obs, w: rule_actions(obs, w, oracle=True)
    if name.endswith(".zip"):
        return ModelPolicy(str(ROOT / name) if not Path(name).is_absolute() else name)
    raise ValueError(f"모르는 정책: {name}")


def policy_label(name: str) -> str:
    return Path(name).stem if name.endswith(".zip") else name.upper()


def run_policy(cfg: dict, seeds, steps: int, policy, record: bool = True, hook=None) -> R8World:
    w = R8World(cfg, list(seeds), record_samples=record)
    w.step_hook = hook
    D = w.D
    for _ in range(int(steps) // D):
        w.step(policy(w.observe(), w))
    return w


# --------------------------------------------------------------------------- #
# 지표
# --------------------------------------------------------------------------- #

def delta_from(C: np.ndarray):
    """C (S, 2, 2) = 층 × (늑대, 짐승) × (안 도망, 도망) → (Δ, ρ, F_w, F_h, n). 두 쪽 표본이 다 있는 층만 쓴다."""
    n = C.sum(-1).astype(np.float64)
    ok = (n[:, 0] > 0) & (n[:, 1] > 0)
    F = np.divide(C[..., 1], n, out=np.zeros_like(n), where=n > 0)
    wgt = np.where(ok, n.sum(-1), 0.0)
    if wgt.sum() <= 0:
        return float("nan"), float("nan"), F[:, 0], F[:, 1], n
    wgt = wgt / wgt.sum()
    d = float((wgt * (F[:, 0] - F[:, 1])).sum())
    den = float((wgt * F[:, 1]).sum())
    rho = float((wgt * F[:, 0]).sum() / den) if den > 0 else float("inf")
    return d, rho, F[:, 0], F[:, 1], n


def boot_delta(CW: np.ndarray, B: int = BOOT, seed: int = BOOT_SEED):
    """CW (K, S, 2, 2) 세계별 수 → Δ·ρ 의 세계 되뽑기 95% 구간."""
    K = CW.shape[0]
    rng = np.random.default_rng(seed)
    ds, rs = [], []
    for _ in range(B):
        idx = rng.integers(0, K, K)
        d, r, *_ = delta_from(CW[idx].sum(0))
        ds.append(d)
        rs.append(r)
    ds, rs = np.asarray(ds), np.asarray(rs)
    ds, rs = ds[np.isfinite(ds)], rs[np.isfinite(rs)]
    q = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))] if len(x) else [float("nan")] * 2  # noqa: E731
    return q(ds), q(rs)


def samples_counts(S: np.ndarray, K: int, mask: np.ndarray, strata: np.ndarray, n_strata: int, kinds=(K_WOLF, K_BEAST)) -> np.ndarray:
    """표본 줄 → 세계별 수 (K, 층, 2, 2)."""
    CW = np.zeros((K, n_strata, 2, 2), dtype=np.int64)
    for j, kd in enumerate(kinds):
        m = mask & (S[:, SC["kind"]] == kd)
        np.add.at(CW, (S[m, SC["world"]].astype(int), strata[m].astype(int), j, S[m, SC["fled"]].astype(int)), 1)
    return CW


def summarize(w: R8World, worlds: np.ndarray | None = None, boot: bool = True) -> dict:
    st = w.st
    sel = np.arange(w.K) if worlds is None else np.asarray(worlds)
    g = {k: v[sel] for k, v in st.items()}
    ds = max(int(g["deer_steps"].sum()), 1)
    dec = max(int(g["decisions"].sum()), 1)
    act = g["actions"].sum(0)
    out = dict(
        worlds=int(len(sel)), deer_steps=ds,
        caught_wolf_1k=1000.0 * g["caught_wolf"].sum() / ds, caught_bear_1k=1000.0 * g["caught_bear"].sum() / ds,
        starved_1k=1000.0 * g["starved"].sum() / ds, repro_1k=1000.0 * g["repro"].sum() / ds,
        eaten_x1000=1000.0 * g["eaten_e"].sum() / ds, in_shelter=float(g["in_shelter"].sum()) / ds,
        act_eat=float(act[0]) / dec, act_run=float(act[1:9].sum()) / dec, act_shelter=float(act[9]) / dec, act_watch=float(act[10]) / dec,
        act_hist={ACTION_NAMES[i]: float(act[i]) / dec for i in range(N_ACTIONS)},
        flee_dir_cos=float(g["flee_dir_sum"].sum() / max(g["flee_dir_n"].sum(), 1)), flee_dir_n=int(g["flee_dir_n"].sum()),
    )
    out["caught_1k"] = out["caught_wolf_1k"] + out["caught_bear_1k"]
    # 주 Δ: 거리 띠 3 개
    CW = g["flee_cnt"][:, [K_WOLF, K_BEAST]].transpose(0, 2, 1, 3)        # (K, 띠, 종류, 도망)
    d, rho, Fw, Fh, n = delta_from(CW.sum(0))
    out.update(delta=d, rho=rho, F_wolf=Fw.tolist(), F_beast=Fh.tolist(), n_wolf=n[:, 0].astype(int).tolist(), n_beast=n[:, 1].astype(int).tolist())
    if boot:
        out["delta_ci"], out["rho_ci"] = boot_delta(CW)
    # 덧붙여 보기 (표본 줄)
    S = w.samples_array()
    if len(S):
        S = S[np.isin(S[:, SC["world"]].astype(int), sel)]
        remap = np.full(w.K, -1)
        remap[sel] = np.arange(len(sel))
        S = S.copy()
        S[:, SC["world"]] = remap[S[:, SC["world"]].astype(int)]
        Kn = len(sel)
        band = S[:, SC["band"]]
        allm = np.ones(len(S), dtype=bool)
        ex = {}
        cw = samples_counts(S, Kn, S[:, SC["n_within15"]] == 1, band, 3)
        ex["only_one"] = _dsum(cw, boot)
        cw = samples_counts(S, Kn, S[:, SC["kin_run_frac"]] <= 0.0, band, 3)
        ex["kin_still"] = _dsum(cw, boot)
        ab = np.digitize(S[:, SC["approach"]], [0.0, 0.25, 0.5])              # 다가옴 띠 4
        cw = samples_counts(S, Kn, allm, band * 4 + ab, 12)
        ex["approach_matched"] = _dsum(cw, boot)
        eat_w = (S[:, SC["kind"]] == K_WOLF) & (S[:, SC["astate"]] == 1)
        cw = samples_counts(S, Kn, eat_w | (S[:, SC["kind"]] == K_BEAST), band, 3)
        ex["eating_wolf_vs_beast"] = _dsum(cw, boot)
        hw = (S[:, SC["kind"]] == K_WOLF) & (S[:, SC["astate"]] == 0)
        cw = samples_counts(S, Kn, hw | (S[:, SC["kind"]] == K_BEAST), band, 3)
        ex["hunting_wolf_vs_beast"] = _dsum(cw, boot)
        st_m = hw & (S[:, SC["approach"]] > 0) & (S[:, SC["fled"]] == 1) & (S[:, SC["prev_fled"]] == 0)
        ex["flight_start_dist_median"] = float(np.median(S[st_m, SC["dist"]])) * 2.0 if st_m.any() else None   # m
        ex["flight_start_n"] = int(st_m.sum())
        bm = S[:, SC["kind"]] == K_BEAR
        if bm.any():
            b8 = bm & (S[:, SC["dist"]] < 8.0)
            ex["bear_flee_within8"] = float(S[b8, SC["fled"]].mean()) if b8.any() else None
            ex["bear_n_within8"] = int(b8.sum())
            w8 = (S[:, SC["kind"]] == K_WOLF) & (S[:, SC["dist"]] < 8.0)
            ex["wolf_flee_within8"] = float(S[w8, SC["fled"]].mean()) if w8.any() else None
        out["extra"] = ex
    return out


def _dsum(cw: np.ndarray, boot: bool) -> dict:
    d, rho, Fw, Fh, n = delta_from(cw.sum(0))
    r = dict(delta=d, rho=rho, n_wolf=int(n[:, 0].sum()), n_beast=int(n[:, 1].sum()))
    if boot:
        r["delta_ci"], r["rho_ci"] = boot_delta(cw, B=500)
    return r


# --------------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------------- #

def _seeds(a) -> list[int]:
    lo, hi = int(a[0]), int(a[1])
    return list(range(lo, hi + 1))


def _cfg(path: str, sets=None) -> dict:
    """설정 + `--set 블록.키=값`(YAML 값) 덮어쓰기 (보정 탐색용 — 정한 값은 설정 파일에 적는다)."""
    import yaml

    p = Path(path)
    cfg = load_r8_config(p if p.is_absolute() else ROOT / p)
    for s in sets or []:
        key, val = s.split("=", 1)
        sec, k = key.split(".", 1)
        cfg = override(cfg, {sec: {k: yaml.safe_load(val)}})
    return cfg


def _fmt(x, nd=3):
    if x is None:
        return "-"
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(_fmt(v, nd) for v in x) + "]"
    if isinstance(x, float):
        return f"{x:.{nd}f}" if math.isfinite(x) else str(x)
    return str(x)


def cmd_calibrate(args) -> int:
    cfg = _cfg(args.config, args.set)
    seeds = _seeds(args.seeds)
    res, worlds = {}, {}
    for name in ("always_eat", "rule_blind", "rule_oracle", "random"):
        t = time.time()
        w = run_policy(cfg, seeds, args.steps, make_policy(name))
        res[name] = summarize(w, boot=False)
        h2 = np.nonzero(w.H >= 2)[0]
        res[name]["eaten_x1000_h2"] = summarize(w, h2, boot=False)["eaten_x1000"]
        worlds = [w.world_params(k) for k in range(w.K)]
        print(f"{name}: 잡힘 {res[name]['caught_1k']:.3f} 굶음 {res[name]['starved_1k']:.3f} 번식 {res[name]['repro_1k']:.3f} "
              f"먹음 {res[name]['eaten_x1000']:.3f} (짐승≥2 {res[name]['eaten_x1000_h2']:.3f}) 은신 {res[name]['in_shelter']:.3f} "
              f"Δ {res[name]['delta']:.3f} ({time.time() - t:.0f}s)", flush=True)
    ae, rb, ro = res["always_eat"], res["rule_blind"], res["rule_oracle"]
    gates = {
        "C0-1": dict(ok=bool(ro["caught_1k"] <= 0.5 * ae["caught_1k"]), oracle=ro["caught_1k"], always_eat=ae["caught_1k"],
                     ratio=ro["caught_1k"] / max(ae["caught_1k"], 1e-12)),
        "C0-2": dict(ok=bool(rb["eaten_x1000_h2"] <= 0.9 * ro["eaten_x1000_h2"]), blind=rb["eaten_x1000_h2"], oracle=ro["eaten_x1000_h2"],
                     ratio=rb["eaten_x1000_h2"] / max(ro["eaten_x1000_h2"], 1e-12), worlds_h2=int(sum(1 for x in worlds if x["beasts"] >= 2))),
        "C0-4": dict(ok=bool(0.5 <= ae["caught_1k"] <= 20.0), always_eat=ae["caught_1k"]),
    }
    out = dict(config=args.config, sets=args.set, seeds=args.seeds, steps=args.steps, policies=res, gates=gates, worlds=worlds)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / f"calibrate{args.tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in gates.items():
        print(k, "통과" if v["ok"] else "못 넘음", {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items() if a != "ok"})
    return 0


def cmd_leak(args) -> int:
    """C0-3: 평상 상태(늑대 = 사냥 중·표적 없음 배회, 짐승 = 돌아다님)의 (속력, 크기, 꺾기)로 종류를 맞히는 로지스틱 AUC (세계 절반 학습·절반 시험)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    cfg = _cfg(args.config, args.set)
    seeds = _seeds(args.seeds)
    rows = []
    prev = {}

    def hook(w: R8World, dead, ck):
        if "ahead" in prev:
            turn = np.arctan2(prev["ahead"][..., 0] * w.ahead[..., 1] - prev["ahead"][..., 1] * w.ahead[..., 0],
                              (prev["ahead"] * w.ahead).sum(-1))
            wolf_n = (w.kind == K_WOLF) & (w.target < 0) & (w.eat_left == 0) & (w.tired_left == 0) & (w.pounce_left == 0) & prev["wn"]
            beast_n = (w.kind == K_BEAST) & (w.bstate == 0) & prev["bn"]
            m = wolf_n | beast_n
            if m.any():
                kk, aa = np.nonzero(m)
                spd = np.sqrt((w.adisp[kk, aa] ** 2).sum(-1)) / w.unit
                rows.append(np.stack([kk, (w.kind[kk, aa] == K_WOLF).astype(float), spd, w.asize[kk, aa], np.abs(turn[kk, aa])], 1))
        prev["ahead"] = w.ahead.copy()
        prev["wn"] = (w.kind == K_WOLF) & (w.target < 0) & (w.eat_left == 0) & (w.tired_left == 0) & (w.pounce_left == 0)
        prev["bn"] = (w.kind == K_BEAST) & (w.bstate == 0)

    w = run_policy(cfg, seeds, args.steps, make_policy("always_eat"), record=False, hook=hook)
    X = np.concatenate(rows, 0)
    half = w.K // 2
    tr, te = X[:, 0] < half, X[:, 0] >= half
    feats = X[:, 2:5]
    clf = LogisticRegression(max_iter=1000).fit(feats[tr], X[tr, 1])
    auc = float(roc_auc_score(X[te, 1], clf.predict_proba(feats[te])[:, 1]))
    single = {nm: float(roc_auc_score(X[te, 1], feats[te, j])) for j, nm in enumerate(("speed", "size", "turn"))}
    # 관측 함수 종류 바꿔치기 (설계 3-8 7)
    import copy as _c

    w2 = R8World(cfg, seeds[:8])
    for _ in range(50):
        w2.step(np.zeros((w2.K, w2.N), dtype=np.int64))
    o1 = w2._observe()
    w3 = _c.deepcopy(w2)
    swapped = 0
    for k in range(w3.K):
        wi = np.nonzero(w3.kind[k] == K_WOLF)[0]
        bi = np.nonzero(w3.kind[k] == K_BEAST)[0]
        if len(wi) and len(bi):
            w3.kind[k, wi[0]], w3.kind[k, bi[0]] = K_BEAST, K_WOLF
            swapped += 1
    o2 = w3._observe()
    swap_ok = bool(np.array_equal(o1, o2)) and swapped > 0
    ok = 0.45 <= auc <= 0.55 and swap_ok
    out = dict(config=args.config, seeds=args.seeds, steps=args.steps, n=int(len(X)), n_wolf=int(X[:, 1].sum()), auc=auc, single_auc=single,
               swap_ok=swap_ok, swapped_worlds=swapped, ok=ok,
               mean_speed=dict(wolf=float(X[X[:, 1] == 1, 2].mean()), beast=float(X[X[:, 1] == 0, 2].mean())),
               mean_size=dict(wolf=float(X[X[:, 1] == 1, 3].mean()), beast=float(X[X[:, 1] == 0, 3].mean())),
               mean_turn=dict(wolf=float(X[X[:, 1] == 1, 4].mean()), beast=float(X[X[:, 1] == 0, 4].mean())))
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "leak.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print("C0-3", "통과" if ok else "못 넘음")
    return 0


def judge(m: dict, ae: dict) -> dict:
    p1 = m["caught_1k"] <= 0.5 * ae["caught_1k"]
    p2 = (m["eaten_x1000"] >= 0.7 * ae["eaten_x1000"]) and (m["starved_1k"] <= 0.1)
    lo = m.get("delta_ci", [float("nan")])[0]
    p3 = bool(math.isfinite(lo) and lo > 0 and m["rho"] >= 1.5)
    return dict(P1=bool(p1), P2=bool(p2), P3=p3, caught_ratio=m["caught_1k"] / max(ae["caught_1k"], 1e-12),
                eaten_ratio=m["eaten_x1000"] / max(ae["eaten_x1000"], 1e-12))


def run_set(cfg, names, seeds, steps):
    res = {}
    for name in names:
        t = time.time()
        w = run_policy(cfg, seeds, steps, make_policy(name))
        lab = policy_label(name)
        res[lab] = summarize(w)
        res[lab]["source"] = name
        m = res[lab]
        print(f"{lab}: 잡힘 {m['caught_1k']:.3f} (곰 {m['caught_bear_1k']:.3f}) 굶음 {m['starved_1k']:.3f} 번식 {m['repro_1k']:.3f} "
              f"먹음 {m['eaten_x1000']:.3f} 뛰기 {m['act_run']:.3f} 은신 {m['act_shelter']:.3f} 살핌 {m['act_watch']:.3f} "
              f"Δ {m['delta']:.3f} {_fmt(m.get('delta_ci'))} ρ {m['rho']:.2f} ({time.time() - t:.0f}s)", flush=True)
    return res


def write_summary(out_dir: Path, title: str, args, res: dict, models: list[str]) -> None:
    ae = res.get("ALWAYS_EAT")
    verdict = {}
    if ae is not None:
        for mname in models:
            lab = policy_label(mname)
            verdict[lab] = judge(res[lab], ae)
    main = [policy_label(m) for m in models if not Path(m).stem.startswith("r8_h0")]
    passes = {p: sum(1 for lab in main if verdict.get(lab, {}).get(p)) for p in ("P1", "P2", "P3")}
    overall = {p: passes[p] >= 2 for p in passes} if len(main) >= 3 else None
    js = dict(title=title, args=vars(args), results=res, verdict=verdict, passes=passes, overall=overall,
              finished=time.strftime("%Y-%m-%d %H:%M:%S"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(js, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    L = [f"# {title}", "", f"- 세계 {args.seeds[0]}~{args.seeds[1]}, {args.steps} 스텝, 결정적 행동. 만든 때 {js['finished']}.", ""]
    L.append("| 정책 | 잡힘/1k | 곰/1k | 굶음/1k | 번식/1k | 먹음×1000 | 먹기 | 뛰기 | 은신처 | 살핌 | 은신처 안 | Δ | Δ 95% | ρ | ρ 95% |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for lab, m in res.items():
        L.append(f"| {lab} | {m['caught_1k']:.3f} | {m['caught_bear_1k']:.3f} | {m['starved_1k']:.3f} | {m['repro_1k']:.3f} | {m['eaten_x1000']:.3f} | "
                 f"{m['act_eat']:.3f} | {m['act_run']:.3f} | {m['act_shelter']:.3f} | {m['act_watch']:.3f} | {m['in_shelter']:.3f} | "
                 f"{m['delta']:.3f} | {_fmt(m.get('delta_ci'))} | {m['rho']:.2f} | {_fmt(m.get('rho_ci'), 2)} |")
    L.append("")
    L.append("거리 띠별 도망 몫 (늑대 / 짐승, 표본 수)")
    L.append("")
    for lab, m in res.items():
        L.append(f"- {lab}: " + "; ".join(f"[{5 * b},{5 * b + 5}) {m['F_wolf'][b]:.3f} / {m['F_beast'][b]:.3f} (n {m['n_wolf'][b]} / {m['n_beast'][b]})"
                                          for b in range(3)) + f" — 도망 방향 cos {m['flee_dir_cos']:.3f} (n {m['flee_dir_n']})")
    if verdict:
        L += ["", "판정 (설계 9-2, 기준 ALWAYS_EAT)", "", "| 두뇌 | P1 잡힘 ≤ 0.5× | P2 먹음 ≥ 0.7×·굶음 ≤ 0.1 | P3 Δ 아래 끝 > 0·ρ ≥ 1.5 | 잡힘 비 | 먹음 비 |",
              "|---|---|---|---|---|---|"]
        for lab, v in verdict.items():
            L.append(f"| {lab} | {'통과' if v['P1'] else '실패'} | {'통과' if v['P2'] else '실패'} | {'통과' if v['P3'] else '실패'} | "
                     f"{v['caught_ratio']:.3f} | {v['eaten_ratio']:.3f} |")
        if overall is not None:
            L += ["", f"시드 3 개 중 통과 수 (대조 r8_h0 제외): {passes} → " + ", ".join(f"{p} {'통과' if ok else '실패'}" for p, ok in overall.items())]
    L += ["", "덧붙여 보기 (보고만)", ""]
    for lab, m in res.items():
        ex = m.get("extra", {})
        parts = []
        for key in ("only_one", "kin_still", "approach_matched", "eating_wolf_vs_beast", "hunting_wolf_vs_beast"):
            if key in ex:
                e = ex[key]
                parts.append(f"{key} Δ {e['delta']:.3f} {_fmt(e.get('delta_ci'))} ρ {e['rho']:.2f}")
        if ex.get("flight_start_dist_median") is not None:
            parts.append(f"도망 시작 거리 중앙값 {ex['flight_start_dist_median']:.1f} m (n {ex['flight_start_n']})")
        if "bear_flee_within8" in ex:
            parts.append(f"곰 8 단위 안 도망 몫 {_fmt(ex['bear_flee_within8'])} (n {ex['bear_n_within8']}) / 늑대 {_fmt(ex.get('wolf_flee_within8'))}")
        L.append(f"- {lab}: " + "; ".join(parts))
    (out_dir / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def cmd_eval(args) -> int:
    cfg = _cfg(args.config, args.set)
    if args.bears:
        cfg = override(cfg, {"bears": {"count": int(args.bears)}})
    names = list(args.baselines) + list(args.models)
    res = run_set(cfg, names, _seeds(args.seeds), args.steps)
    title = "R8 곰 시험 (설계 10절)" if args.bears else "R8 판정 평가 (설계 8~9절)"
    write_summary(ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out), title, args, res, list(args.models))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("calibrate", "leak", "eval", "bear"):
        p = sub.add_parser(nm)
        p.add_argument("--config", default="configs/v3_r8_pilot.yaml")
        p.add_argument("--seeds", nargs=2, type=int, default=[41400, 41449] if nm in ("calibrate", "leak") else [41900, 41999])
        p.add_argument("--steps", type=int, default=3000)
        p.add_argument("--set", nargs="*", default=[], help="블록.키=값 덮어쓰기 (보정 탐색용)")
        p.add_argument("--tag", default="", help="결과 파일 이름 꼬리")
        p.add_argument("--out", default=str(HERE.parent / ("calib" if nm in ("calibrate", "leak") else ("eval/bear" if nm == "bear" else "eval"))))
        if nm in ("eval", "bear"):
            p.add_argument("--models", nargs="*", default=[])
            p.add_argument("--baselines", nargs="*", default=["random", "always_eat", "rule_blind", "rule_oracle"] if nm == "eval" else ["always_eat"])
            p.add_argument("--bears", type=int, default=2 if nm == "bear" else 0)
    args = ap.parse_args(argv)
    if args.cmd == "calibrate":
        return cmd_calibrate(args)
    if args.cmd == "leak":
        return cmd_leak(args)
    return cmd_eval(args)


if __name__ == "__main__":
    sys.exit(main())
