"""갈림 4 조사 H1 — T1 세계(configs/v2_2r_t1.yaml)와 v2.1 세계(configs/v2_1.yaml)의 코드·세계 동일성.

조사 메모 `inv4/MEMO.md` 1절 H1 행: 같은 행동열을 넣고 관측 앞 7열·보상·사망·리스폰·stats 를 비교한다.
판정(학습 전에 정함): 한 비트라도 다르면 H1 성립(원인 확정 전까지 다른 시험 해석 보류).

herbivore_rl 폴더에서 돌린다. 코어 코드는 고치지 않고 읽기만 한다. 결과는 이 폴더에만 쓴다.
    python results/v2/v2_2r_explore/inv4/h1_identity.py pairs   # 같은 행동열 2000스텝 → h1_pairs.json
    python results/v2/v2_2r_explore/inv4/h1_identity.py train   # 학습 쪽 차이 → h1_train.json
    python results/v2/v2_2r_explore/inv4/h1_identity.py repro   # eval_p1 의 T0 행을 T1 세계에서 재현 → h1_repro.json

pairs: 시드 12000~12004(탐색)·0~2(학습 풀) 마다 World(v2.1)와 World(T1)를 따로 만들고 행동 하나를 두 세계에 똑같이
넣는다. 행동을 정하는 쪽(드라이버):
  uniform   균등 난수 5열 (default_rng([시드, 7101]))
  c2        E2 C2 상수 앞 5열 (results/v2/e2/V0/c2/constsearch.json best)
  t0_det    T0 모델 s20 결정 모드. v2.1 세계 관측(7열)으로 행동을 정한다 (과제 (c))
  t0_hold   T0 모델 s20 K24 유지 표본 모드(출시 모드). v2.1 세계 관측, 리스폰 훅은 v2.1 세계의 사망 (추가)
  t1_det    T1 모델 s20 결정 모드. T1 세계 관측(8열)으로 행동을 정한다 (추가 — T1 정책이 가는 상태 분포)
  t1_hold   T1 모델 s20 K24 유지 표본 모드. T1 세계 관측, 리스폰 훅은 T1 세계의 사망 (추가)
비교(비트 단위, dtype·모양 포함): reset 직후 세계 배치와 첫 관측, 스텝마다 관측 앞 7열(float32)·보상·done·
terminal_obs 앞 7열·스텝 뒤(리스폰 뒤) pos·head·energy·food·repro_cd·포식자 상태·pred_ema·보행·적용 속도·세계 난수
상태·기하(_g) 전부, 끝의 stats()·gait_stats() 모든 키.

train: 두 설정의 train·overrides·speed 블록과 합친 v1 키, 메타 JSON 의 PPO 값, MultiWorldVecEnv 세계 시드 순서
(meta_seed 같을 때, 학습 길이만큼 _renew 를 흉내 내어 seed_history 비교), 같은 PPO 시드의 초기 정책 가중치.

repro: eval_p1.json 의 'T0_s*|C0|det·hold' 행(v2.1 세계에서 잰 값)을 T1 세계에서 관측 앞 7열만 넣어(probe_v2:obs_take)
다시 재고 모든 공통 열을 비교한다. 세계가 같으면 G_γ 까지 그대로 나와야 한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                     # herbivore_rl
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import numpy as np  # noqa: E402

CFG_T0 = ROOT / "configs" / "v2_1.yaml"
CFG_T1 = ROOT / "configs" / "v2_2r_t1.yaml"
CKPT = ROOT / "ckpt" / "v2"
C2_FILE = ROOT / "results" / "v2" / "e2" / "V0" / "c2" / "constsearch.json"
EVAL_P1 = ROOT / "results" / "v2" / "v2_2r_explore" / "eval_p1.json"
GAMMA = 0.9916661555611042
HOLD_K = 24
PAIR_SEEDS = [12000, 12001, 12002, 12003, 12004, 0, 1, 2]
PAIR_STEPS = 2000
DRIVERS = ["uniform", "c2", "t0_det", "t0_hold", "t1_det", "t1_hold"]
UNIFORM_SALT = 7101
CONTROL_STEP = 100
WORKERS = 4
TRAIN_SEEDS = [20, 21, 22]


def model_path(arm: str, s: int) -> Path:
    return CKPT / f"v2_2r_{arm}_s{s}.zip"


def save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, allow_nan=True), encoding="utf-8")


# --------------------------------------------------------------------- #
# 비트 단위 비교
# --------------------------------------------------------------------- #


def _scalar(v):
    """JSON 에 남길 값 하나(정수·실수·bool). 실수는 repr 로 되살릴 수 있는 float 다."""
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    return float(v)


def bit_diff(x, y):
    """x, y 를 비트 단위로 비교한다. 같으면 None, 다르면 차이 설명 dict.

    dtype·모양이 다르면 그것만 적는다. 같으면 바이트를 원소별로 비교해 다른 원소 수와 첫 위치·값을 적는다
    (NaN 도 비트로 비교하고, 0.0 과 −0.0 은 다르다고 본다).
    """
    x = np.ascontiguousarray(np.asarray(x))
    y = np.ascontiguousarray(np.asarray(y))
    if x.dtype != y.dtype or x.shape != y.shape:
        return {"kind": "dtype/shape", "a": f"{x.dtype}{list(x.shape)}", "b": f"{y.dtype}{list(y.shape)}"}
    if x.tobytes() == y.tobytes():
        return None
    xb = x.reshape(-1).view(np.uint8).reshape(x.size, x.dtype.itemsize)
    yb = y.reshape(-1).view(np.uint8).reshape(y.size, y.dtype.itemsize)
    bad = np.flatnonzero((xb != yb).any(1))
    i = int(bad[0])
    return {"kind": "value", "n_diff": int(bad.size), "index": [int(j) for j in np.unravel_index(i, x.shape)],
            "a": _scalar(x.reshape(-1)[i]), "b": _scalar(y.reshape(-1)[i])}


def dict_diff(a: dict, b: dict) -> dict:
    """두 dict(stats 등)의 키·값 비트 비교. {키: 차이}. 같으면 빈 dict."""
    out = {}
    for k in sorted(set(a) | set(b)):
        if k not in a or k not in b:
            out[k] = {"kind": "missing", "a": k in a, "b": k in b}
            continue
        d = bit_diff(np.float64(a[k]), np.float64(b[k]))
        if d is not None:
            out[k] = d
    return out


class DiffLog:
    """키별 첫 차이 스텝·차이 난 스텝 수."""

    def __init__(self):
        self.first: dict[str, dict] = {}
        self.count: dict[str, int] = {}
        self.checked: set[str] = set()

    def check(self, key: str, step: int, x, y) -> None:
        self.checked.add(key)
        d = bit_diff(x, y)
        if d is None:
            return
        self.count[key] = self.count.get(key, 0) + 1
        if key not in self.first:
            self.first[key] = {"step": step, **d}

    def first_overall(self):
        if not self.first:
            return None
        k = min(self.first, key=lambda k: (self.first[k]["step"], k))
        return {"key": k, **self.first[k]}


# --------------------------------------------------------------------- #
# pairs: 같은 행동열을 두 세계에
# --------------------------------------------------------------------- #

RESET_SCALARS = ("seed", "size", "M", "pred_speed_mult", "ranged_frac", "cover_frac_target", "food_regen_mult",
                 "cover_frac_actual", "gw", "N", "t", "pred_ema")
RESET_ARRAYS = ("food_cap", "food", "cov_c", "cov_r", "cover_cell", "regen_field", "pos", "head", "energy",
                "repro_cd", "pred_pos", "pred_head", "pred_ranged", "pred_speed", "pred_catch_r", "pred_cd")
STEP_ARRAYS = ("pos", "head", "energy", "food", "repro_cd", "pred_pos", "pred_head", "pred_cd", "gait", "gait_cmd",
               "vel")


def _rng_state(w) -> str:
    return json.dumps(w.rng.bit_generator.state, sort_keys=True)


def _driver(name: str, seed: int, n: int, act_dim: int):
    """드라이버 → (행동 함수 f(obs0, obs1), 리스폰 훅을 받을 세계 번호 0·1·None, 정책 객체)."""
    from env_v2.rollout import build_policy

    if name == "uniform":
        rng = np.random.default_rng([int(seed), UNIFORM_SALT])
        return (lambda o0, o1: rng.random((n, act_dim))), None, None
    if name == "c2":
        c2 = np.asarray(json.loads(C2_FILE.read_text(encoding="utf-8"))["best"][:act_dim], dtype=np.float64)
        return (lambda o0, o1: np.tile(c2, (n, 1))), None, None
    arm, mode = name.split("_")
    spec = {"kind": "learned", "model": str(model_path(arm, 20))}
    if mode == "hold":
        spec.update(mode="hold", hold_k=HOLD_K)
    pol = build_policy(spec, seed)
    if arm == "t0":
        return (lambda o0, o1: pol(o0)), (0 if mode == "hold" else None), pol
    return (lambda o0, o1: pol(o1)), (1 if mode == "hold" else None), pol


def run_pair(job) -> dict:
    """시드 하나 × 드라이버 하나. 두 세계에 같은 행동을 넣고 차이를 모은다.

    job = (시드, 드라이버, 스텝 수, 교란 스텝). 교란 스텝이 None 이 아니면 음성 대조다: 그 스텝(1부터)에 T1 세계에 넣는
    행동 [0, 0] 하나만 한 ulp(np.nextafter) 바꾼다. 비교가 이 크기의 차이를 잡는지 본다(판정에는 쓰지 않는다).
    """
    seed, driver, steps, perturb = job
    from env_v2.config import load_v2_config
    from env_v2.rollout import g_gamma
    from env_v2.world import World

    t_start = time.time()
    w0 = World(load_v2_config(CFG_T0), seeds=[seed])
    w1 = World(load_v2_config(CFG_T1), seeds=[seed])
    N = w0.N
    log = DiffLog()
    shape = {"obs_dim": [w0.obs_dim, w1.obs_dim], "act_dim": [w0.act_dim, w1.act_dim],
             "act_names": [list(w0.act_names), list(w1.act_names)], "obs_names_1": list(w1.obs_names)}

    # reset 직후 세계 배치와 첫 관측
    for k in RESET_SCALARS:
        log.check(f"reset.{k}", 0, getattr(w0, k), getattr(w1, k))
    for k in RESET_ARRAYS:
        log.check(f"reset.{k}", 0, getattr(w0, k), getattr(w1, k))
    log.check("reset.obs7", 0, w0.observe(), np.ascontiguousarray(w1.observe()[:, :7]))
    log.check("reset.rng_state", 0, np.frombuffer(_rng_state(w0).encode(), np.uint8),
              np.frombuffer(_rng_state(w1).encode(), np.uint8))
    for k in w0._g:
        log.check(f"reset.geom.{k}", 0, w0._g[k], w1._g[k])

    act, hook_world, pol = _driver(driver, seed, N, w0.act_dim)
    rew = np.empty((2, steps, N))
    done = np.empty((2, steps, N), dtype=bool)
    o1_col7 = np.empty((steps, N), dtype=np.float32)       # 결정 때 T1 관측 7 (threat_recency) — 시험이 비지 않았나
    win = np.empty((steps, N), dtype=bool)                   # 결정 때 창 (안 보임 & threat_recency > 0.5)
    for t in range(steps):
        o0, o1 = w0.observe(), w1.observe()
        o1_col7[t] = o1[:, 7]
        win[t] = (o1[:, 1] <= 0.0) & (o1[:, 7] > 0.5)
        a = np.asarray(act(o0, o1), dtype=np.float64)
        a1 = a.copy()
        if perturb is not None and t + 1 == perturb:
            a1[0, 0] = np.nextafter(a1[0, 0], 2.0)
        obs0, r0, d0, term0 = w0.step(a.copy())
        obs1, r1, d1, term1 = w1.step(a1)
        if hook_world is not None:
            pol.observe_done(d0 if hook_world == 0 else d1)
        step = t + 1
        rew[0, t], rew[1, t], done[0, t], done[1, t] = r0, r1, d0, d1
        log.check("obs7", step, obs0, np.ascontiguousarray(obs1[:, :7]))
        log.check("reward", step, r0, r1)
        log.check("done", step, d0, d1)
        log.check("terminal_obs7", step, term0, np.ascontiguousarray(term1[:, :7]))
        for k in STEP_ARRAYS:
            log.check(k, step, getattr(w0, k), getattr(w1, k))
        log.check("pred_ema", step, np.float64(w0.pred_ema), np.float64(w1.pred_ema))
        log.check("t", step, np.int64(w0.t), np.int64(w1.t))
        log.check("rng_state", step, np.frombuffer(_rng_state(w0).encode(), np.uint8),
                  np.frombuffer(_rng_state(w1).encode(), np.uint8))
        for k in w0._g:
            log.check(f"geom.{k}", step, w0._g[k], w1._g[k])

    s0, s1 = w0.stats(), w1.stats()
    g0, g1 = w0.gait_stats(), w1.gait_stats()
    stats_diff, gait_diff = dict_diff(s0, s1), dict_diff(g0, g1)
    col7 = o1_col7.astype(np.float64)
    ws1, vs1 = w1.window_stats(), w1.vigil_stats()
    return {
        "seed": seed, "driver": driver, "steps": steps, "perturb_step": perturb, "shape": shape,
        "identical": not log.first and not stats_diff and not gait_diff,
        "first_diff": log.first_overall(),
        "diff_keys": {k: {"n_steps": log.count[k], **log.first[k]} for k in sorted(log.first)},
        "keys_checked": sorted(log.checked),
        "stats_diff": stats_diff, "gait_stats_diff": gait_diff,
        "stats_keys": sorted(s0), "gait_stats_keys": sorted(g0),
        "g_gamma": [g_gamma(rew[0], done[0], GAMMA), g_gamma(rew[1], done[1], GAMMA)],
        "stats_v21": {k: _scalar(v) for k, v in s0.items()},
        "gait_stats_v21": {k: _scalar(v) for k, v in g0.items()},
        # 시험이 비지 않았다는 근거(같은 행동열이 사망·리스폰·번식·보행 전환·기억 관측을 실제로 지났다)
        "coverage": {
            "deaths": int(done[0].sum()), "pred_deaths": int(w0._pred_deaths), "starve_deaths": int(w0._starve_deaths),
            "repro": int(w0._repro_total),
            "stop_frac": g0["stop_frac"], "walk_frac": g0["walk_frac"], "run_frac": g0["run_frac"],
            "tr_pos_frac": float((col7 > 0).mean()), "tr_mid_frac": float(((col7 > 0) & (col7 < 1)).mean()),
            "tr_one_frac": float((col7 == 1).mean()), "tr_mean": float(col7.mean()),
            "win_frac_obs": float(win.mean()), "win_frac_world": ws1["win_frac"],
            "threat_mean_world": vs1["threat_mean"],
        },
        "elapsed_s": round(time.time() - t_start, 1),
    }


def cmd_pairs(args) -> int:
    from env.rollout import _init_worker

    jobs = [(s, d, args.steps, None) for d in args.drivers for s in PAIR_SEEDS]
    # 음성 대조: uniform·t0_det 드라이버, 시드 12000·0, 100 스텝에 T1 쪽 행동 한 칸을 한 ulp 바꾼다
    controls = [(s, d, args.steps, CONTROL_STEP) for d in ("uniform", "t0_det") for s in (12000, 0)]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker) as ex:
        res = list(ex.map(run_pair, jobs + controls))
    res, ctrl = res[:len(jobs)], res[len(jobs):]
    out = {
        "meta": {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "command": " ".join(sys.argv), "configs": [str(CFG_T0.relative_to(ROOT)), str(CFG_T1.relative_to(ROOT))],
                 "seeds": PAIR_SEEDS, "steps": args.steps, "drivers": args.drivers, "gamma": GAMMA,
                 "hold_k": HOLD_K, "uniform_salt": UNIFORM_SALT, "elapsed_s": round(time.time() - t0, 1),
                 "models": {a: str(model_path(a, 20).relative_to(ROOT)) for a in ("t0", "t1")}},
        "all_identical": all(r["identical"] for r in res),
        "n_jobs": len(res), "n_identical": sum(r["identical"] for r in res),
        "jobs": res,
        "controls": [{k: c[k] for k in ("seed", "driver", "perturb_step", "identical", "first_diff")}
                     | {"n_diff_keys": len(c["diff_keys"]), "g_gamma": c["g_gamma"]} for c in ctrl],
    }
    save_json(HERE / "h1_pairs.json", out)
    for r in res:
        c = r["coverage"]
        fd = r["first_diff"]
        print(f"{r['driver']:8s} s{r['seed']:<5d} 같음={r['identical']}  G_γ {r['g_gamma'][0]:+.6f} / {r['g_gamma'][1]:+.6f}"
              f"  사망 {c['deaths']} (피식 {c['pred_deaths']}, 아사 {c['starve_deaths']}) 번식 {c['repro']}"
              f"  tr>0 {c['tr_pos_frac']:.3f} 창 {c['win_frac_obs']:.3f}"
              + (f"  첫 차이 {fd}" if fd else ""), flush=True)
    print(f"전체 같음: {out['all_identical']} ({out['n_identical']}/{out['n_jobs']}), {out['meta']['elapsed_s']}s")
    for c in out["controls"]:
        print(f"음성 대조 {c['driver']} s{c['seed']} 교란 {c['perturb_step']}: 같음={c['identical']}, 첫 차이 {c['first_diff']}")
    return 0


# --------------------------------------------------------------------- #
# train: 학습 쪽 차이
# --------------------------------------------------------------------- #

META_KEYS = ("steps", "actual_timesteps", "seed", "gamma", "gamma_source", "ent_coef", "ent_coef_source", "ppo_config",
             "ppo", "num_worlds", "reset_interval", "worlds_seen", "world_resets", "init", "act_names", "obs_names",
             "init_action_bias", "init_action_bias_source", "probe_every", "config_digest", "command")


def _simulate_renewals(venv, vec_steps: int) -> None:
    """MultiWorldVecEnv.step_wait 의 세계 갱신 순서만 흉내 낸다(세계 스텝은 돌리지 않는다).

    세계 시드 선택은 VecEnv 의 meta 난수와 동시에 도는 세계의 시드만 쓰고 세계 상태를 읽지 않으므로, 스텝을 건너뛰어도
    seed_history 가 학습 때와 같다. SB3 learn 시작의 reset() 은 막 만든 세계라 다시 뽑지 않고 나이만 엇갈리게 둔다.
    """
    venv.reset()
    for _ in range(vec_steps):
        for k in range(venv.K):
            venv._age[k] += 1
            if venv._age[k] >= venv.T:
                venv._renew(k)
                venv.num_resets += 1


def _init_weights(cfg_path: Path, seed: int, tuned: dict):
    """train_v2.main 과 같은 순서로 VecEnv·PPO 를 만들고(학습 없음) 초기 정책 가중치를 돌려준다."""
    from env_v2.config import load_v2_config
    from env_v2.vec_env import MultiWorldVecEnv
    from train import make_model

    cfg = load_v2_config(cfg_path)
    venv = MultiWorldVecEnv(cfg, meta_seed=seed)
    n_steps = max(1, int(cfg.v2["train"].get("rollout_world_steps", 256)) // venv.K)
    model = make_model(venv, tensorboard_log=None, n_steps=n_steps, seed=seed, **tuned)
    return {k: v.detach().cpu().numpy().copy() for k, v in model.policy.state_dict().items()}


def cmd_train(args) -> int:
    import yaml

    from env_v2.config import load_v2_config
    from env_v2.vec_env import MultiWorldVecEnv
    from train import load_tuned

    out: dict = {"meta": {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "command": " ".join(sys.argv)}}
    raw = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in (CFG_T0, CFG_T1)]
    cfg = [load_v2_config(p) for p in (CFG_T0, CFG_T1)]
    d = [c.to_dict() for c in cfg]
    v1_keys = sorted((set(d[0]) | set(d[1])) - {"v2"})
    out["config"] = {
        "train_block": [raw[0].get("train"), raw[1].get("train")],
        "train_equal": raw[0].get("train") == raw[1].get("train"),
        "overrides": [raw[0].get("overrides"), raw[1].get("overrides")],
        "overrides_equal": raw[0].get("overrides") == raw[1].get("overrides"),
        "speed_block": [raw[0]["features"].get("speed"), raw[1]["features"].get("speed")],
        "speed_equal": raw[0]["features"].get("speed") == raw[1]["features"].get("speed"),
        "features": [sorted(raw[0]["features"]), sorted(raw[1]["features"])],
        "t1_only_features": {k: raw[1]["features"][k] for k in raw[1]["features"] if k not in raw[0]["features"]},
        "merged_v1_keys_differ": [k for k in v1_keys if d[0].get(k) != d[1].get(k)],
        "merged_v1_n_keys": len(v1_keys),
        "version": [raw[0].get("version"), raw[1].get("version")],
    }

    metas = {}
    for s in TRAIN_SEEDS:
        m = [json.loads((CKPT / f"v2_2r_{a}_s{s}.json").read_text(encoding="utf-8")) for a in ("t0", "t1")]
        metas[s] = {"has_seed_history": ["seed_history" in x for x in m],
                    "fields": {k: {"t0": m[0].get(k), "t1": m[1].get(k), "equal": m[0].get(k) == m[1].get(k)}
                               for k in META_KEYS},
                    "init_policy": [m[0].get("init_policy"), m[1].get("init_policy")]}
    out["meta_json"] = metas

    seeds = {}
    for s in TRAIN_SEEDS:
        m0 = metas[s]["fields"]
        vec_steps = int(m0["actual_timesteps"]["t0"]) // (int(m0["num_worlds"]["t0"]) * 128)
        v = [MultiWorldVecEnv(c, meta_seed=s) for c in cfg]
        start = [x.current_seeds() for x in v]
        for x in v:
            _simulate_renewals(x, vec_steps)
        seeds[s] = {"vec_steps": vec_steps, "start_seeds": start, "start_equal": start[0] == start[1],
                    "seed_history_equal": v[0].seed_history == v[1].seed_history,
                    "seed_history_t0": v[0].seed_history,
                    "worlds_seen": [sum(len(h) for h in x.seed_history) for x in v],
                    "world_resets": [x.num_resets for x in v],
                    "meta_worlds_seen": [m0["worlds_seen"]["t0"], m0["worlds_seen"]["t1"]],
                    "meta_world_resets": [m0["world_resets"]["t0"], m0["world_resets"]["t1"]],
                    "final_seeds_equal": v[0].current_seeds() == v[1].current_seeds()}
    out["vec_env_seeds"] = seeds

    tuned = load_tuned(ROOT / "configs" / "ppo_best.yaml")
    init = {}
    for s in TRAIN_SEEDS:
        a, b = _init_weights(CFG_T0, s, tuned), _init_weights(CFG_T1, s, tuned)
        rows = {}
        for k in a:
            same_shape = a[k].shape == b[k].shape
            rows[k] = {"shape": [list(a[k].shape), list(b[k].shape)],
                       "equal": bool(same_shape and a[k].tobytes() == b[k].tobytes())}
            if not same_shape and a[k].ndim == 2 and a[k].shape[0] == b[k].shape[0]:
                c = min(a[k].shape[1], b[k].shape[1])
                rows[k]["first_cols_equal"] = bool(np.array_equal(a[k][:, :c], b[k][:, :c]))
            if same_shape and not rows[k]["equal"]:
                rows[k]["max_abs_diff"] = float(np.abs(a[k].astype(np.float64) - b[k].astype(np.float64)).max())
        init[s] = rows
    out["init_weights"] = init
    save_json(HERE / "h1_train.json", out)

    c = out["config"]
    print(f"train 블록 같음 {c['train_equal']}, overrides 같음 {c['overrides_equal']}, speed 같음 {c['speed_equal']}, "
          f"합친 v1 키 중 다른 키 {c['merged_v1_keys_differ']}, T1 에만 있는 기능 {sorted(c['t1_only_features'])}")
    for s in TRAIN_SEEDS:
        diff = [k for k, f in metas[s]["fields"].items() if not f["equal"]]
        print(f"s{s} 메타 다른 키: {diff}")
        x = seeds[s]
        print(f"s{s} 세계 시드: 시작 같음 {x['start_equal']}, seed_history 같음 {x['seed_history_equal']}, "
              f"본 세계 {x['worlds_seen']} (메타 {x['meta_worlds_seen']}), 리셋 {x['world_resets']} (메타 {x['meta_world_resets']})")
        print(f"s{s} 초기 가중치: " + ", ".join(f"{k} {v['shape'][0]}/{v['shape'][1]} 같음={v['equal']}"
                                           + (f" 앞열같음={v['first_cols_equal']}" if 'first_cols_equal' in v else "")
                                           for k, v in init[s].items()))
    return 0


# --------------------------------------------------------------------- #
# repro: eval_p1 T0 행을 T1 세계에서
# --------------------------------------------------------------------- #


def _same(a, b) -> bool:
    """JSON 에서 읽은 값과 새로 잰 값. 실수는 repr 왕복이 정확하므로 == 로 보고, 둘 다 NaN 이면 같다고 본다."""
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def cmd_repro(args) -> int:
    from diagnose_v2 import EXPLORE_SEEDS
    from env_v2.config import load_v2_config
    from env_v2.rollout import make_executor, public_row, run_specs

    d1 = json.loads(EVAL_P1.read_text(encoding="utf-8"))
    steps = int(d1["cond"]["steps"])
    seeds_all = list(EXPLORE_SEEDS)
    assert d1["cond"]["seeds"] == seeds_all
    cfg1 = load_v2_config(CFG_T1)
    take = {"factory": "probe_v2:obs_take", "dims": list(range(7))}
    plan = {}
    for s in args.models:
        n = len(seeds_all) if s == 20 else args.n_other
        for m in ("det", "hold"):
            mode = {} if m == "det" else {"mode": "hold", "hold_k": HOLD_K}
            spec = {"policy": {"kind": "learned", "model": str(model_path("t0", s).resolve()), **mode}, "wrap": [take]}
            plan[f"T0_s{s}|C0|{m}"] = (spec, seeds_all[:n])
    res = {}
    t0 = time.time()
    ex = make_executor(args.workers)
    try:
        by_seeds: dict[tuple, dict] = {}
        for k, (spec, ss) in plan.items():
            by_seeds.setdefault(tuple(ss), {})[k] = spec
        for ss, specs in by_seeds.items():
            for k, rows in run_specs(cfg1, specs, list(ss), steps, gamma=GAMMA, executor=ex).items():
                res[k] = [public_row(r) for r in rows]
            print(f"  시드 {len(ss)}개 {list(specs)} ({time.time() - t0:.0f}s)", flush=True)
    finally:
        if ex is not None:
            ex.shutdown()

    report = {}
    for k, rows in res.items():
        orig = {r["seed"]: r for r in d1["rows"][k]}
        n_eq, first, n_cols = 0, None, None
        for r in rows:
            o = orig[r["seed"]]
            common = sorted(set(o) & set(r))
            n_cols = len(common)
            bad = [c for c in common if not _same(o[c], r[c])]
            if not bad:
                n_eq += 1
            elif first is None:
                first = {"seed": r["seed"], "key": bad[0], "eval_p1": o[bad[0]], "t1_world": r[bad[0]], "n_keys": len(bad)}
        gg_new = [r["g_gamma"] for r in rows]
        gg_old = [orig[r["seed"]]["g_gamma"] for r in rows]
        report[k] = {"n_seeds": len(rows), "n_rows_identical": n_eq, "n_common_cols": n_cols, "first_diff": first,
                     "g_gamma_mean_t1_world": float(np.mean(gg_new)), "g_gamma_mean_eval_p1": float(np.mean(gg_old)),
                     "t1_only_cols": sorted(set(rows[0]) - set(d1["rows"][k][0]))}
    out = {"meta": {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "command": " ".join(sys.argv),
                    "config": str(CFG_T1.relative_to(ROOT)), "steps": steps, "gamma": GAMMA, "hold_k": HOLD_K,
                    "wrap": take, "elapsed_s": round(time.time() - t0, 1)},
           "all_identical": all(v["n_rows_identical"] == v["n_seeds"] for v in report.values()),
           "report": report, "rows": res}
    save_json(HERE / "h1_repro.json", out)
    for k, v in report.items():
        print(f"{k}: 같은 행 {v['n_rows_identical']}/{v['n_seeds']} (공통 열 {v['n_common_cols']}), "
              f"G_γ 평균 T1 세계 {v['g_gamma_mean_t1_world']:.6f} / eval_p1 {v['g_gamma_mean_eval_p1']:.6f}"
              + (f", 첫 차이 {v['first_diff']}" if v["first_diff"] else ""))
    print(f"전체 같음: {out['all_identical']}, {out['meta']['elapsed_s']}s")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="갈림 4 조사 H1 — T1 세계와 v2.1 세계의 동일성")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("pairs")
    a.add_argument("--steps", type=int, default=PAIR_STEPS)
    a.add_argument("--drivers", nargs="+", default=DRIVERS, choices=DRIVERS)
    a.add_argument("--workers", type=int, default=WORKERS)
    sub.add_parser("train")
    r = sub.add_parser("repro")
    r.add_argument("--models", type=int, nargs="+", default=TRAIN_SEEDS)
    r.add_argument("--n-other", type=int, default=10, help="s20 밖 모델은 탐색 시드 앞 n 개만 잰다")
    r.add_argument("--workers", type=int, default=WORKERS)
    args = p.parse_args(argv)
    if max(getattr(args, "workers", 1), 1) > WORKERS:
        raise SystemExit(f"워커는 최대 {WORKERS}개다(다른 학습·진단이 돌고 있다)")
    return {"pairs": cmd_pairs, "train": cmd_train, "repro": cmd_repro}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
