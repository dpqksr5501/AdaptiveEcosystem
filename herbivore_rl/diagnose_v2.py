"""V2 진단 도구 — "정책이 정말 상황을 보고 움직이나"를 대조군으로 잰다 (계획서 0-3, 5.0, 6.1·6.3).

    python diagnose_v2.py ablate --model ckpt/final.zip          # C0, C1, C3-k, C1′ (+ Utility 참고)
    python diagnose_v2.py constsearch --model ckpt/final.zip      # C2: Optuna 최적 상수
    python diagnose_v2.py constsearch --model ckpt/final.zip --const-action 0.421 0.866 0.105 0.004
    python diagnose_v2.py constsearch --model ckpt/final.zip --seg-bins 2:0.5 4:0.5 --seg-dims forage
    python diagnose_v2.py permute --model ckpt/final.zip          # C4-j: 관측 j 고정·순열
    python diagnose_v2.py curves --model ckpt/final.zip           # 반응 곡선
    python diagnose_v2.py r2 --model ckpt/final.zip               # 행동 차원별 선형 R²
    python diagnose_v2.py report --name final                     # 결과 JSON → report.md
    python diagnose_v2.py report --dirs v2_0_s0 v2_0_s1 v2_0_s2 --name v2_0   # 학습 시드 IQM·CI

정책은 `--model`(학습 zip) 또는 `--policy utility|fixed|random` 으로 준다. 산출물은
`results/v2/diag_<이름>/` 아래 JSON + MD 다. 이름은 `--name`, 없으면 모델 파일 이름이고, 설정 version 이
2.0 이 아니면 `_v<version>` 을 붙인다(`final` + configs/v2_0b.yaml → `diag_final_v2_0b`). 같은 모델을 다른
설정으로 진단해도 v2.0 결과 디렉터리를 덮지 않는다.

판정 규칙 (6.1):
- 판정 양은 G_γ(PPO 가 최대화하는 할인 리턴-투-고 평균)와 결과·행동 지표다. mean_return 은 보고만 한다.
- 평가 시드 10000~10019 × 5000스텝, deterministic, 시드를 짝지은 t검정 (자유도 19, |t|>2.093).
- 학습 시드가 여럿이면 IQM 과 층화 부트스트랩 95% CI 를 함께 낸다 (`report --dirs`).
- 평균 행동(C1)·평균 관측(C4)은 학습 시드 0~19 × 3000스텝에서 잰다. 평가 시드를 엿보지 않는다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저 (학습 정책을 이 프로세스에서도 싣는다)

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from env_v2.config import load_v2_config
from env_v2.rollout import (
    ROW_COLUMNS,
    build_policy,
    load_gamma,
    make_executor,
    model_gamma,
    n_segments,
    public_row,
    run_specs,
    tail_steps,
)
from env_v2.world import ACT_DIM, OBS_DIM, OBS_RECENT_PREDATION
from evaluate import T_CRIT, welch_paired

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "v2"
# 관측 표본 캐시(수 MB). results/ 는 커밋 대상이라 .gitignore 가 무시하는 runs/ 아래에 둔다.
CACHE = ROOT / "runs" / "v2_diag"

ACT_NAMES = ["forage", "cohesion", "flee_dist", "cover"]
OBS_NAMES = ["food_density", "pred_count", "pred_dist", "kin_count", "energy",
             "recent_predation", "cover_dist"]

# 보정(평균 행동·평균 관측·표본) 조건. smart_check.py 와 같다.
CALIB_SEEDS = range(0, 20)
CALIB_STEPS = 3000
RECORD_EVERY = 30
# C2 탐색 조건 (계획서 2.1 의 Optuna 112회와 같다).
SEARCH_SEEDS = range(0, 8)
SEARCH_STEPS = 3000
RESCORE_SEEDS = range(100, 120)
RESCORE_STEPS = 3000
TRIALS = 112
BATCH = 7
TOP_K = 5
# v1 환경에서 학습 전에 찾았던 최고 상수. smart_check.py 가 탐색 시작점으로 넣었다.
V1_PRETRAIN_BEST = [0.39, 0.99, 0.92, 0.15]

# 결과 지표(+G_γ). 짝지은 t검정을 붙인다.
OUTCOME = ["mean_return", "g_gamma", "survival", "repro", "predation_rate", "starve_rate"]
# 행동 지표. 우열이 아니라 기술이다.
BEHAVIOR = ["cohesion_mean", "flee_dist_mean", "flee_dist_std", "cover_frac", "react_pred",
            "react_hunger", "starve_share"]
COL_LABEL = {
    "mean_return": "리턴", "g_gamma": "G_γ", "survival": "수명", "repro": "번식",
    "predation_rate": "피식률", "starve_rate": "아사율", "starve_share": "아사 비중",
}
COL_FMT = {
    "mean_return": ".2f", "g_gamma": ".3f", "survival": ".1f", "repro": ".2f",
    "predation_rate": ".5f", "starve_rate": ".5f", "starve_share": ".3f",
}
CTRL_LABEL = {
    "C0": "C0 학습 정책", "C1": "C1 평균 행동 고정", "C1'": "C1′ 행동 순열",
    "C2": "C2 최적 상수", "C2-seg": "C2-seg 구간별 상수", "Utility": "Utility (참고)",
}


# --------------------------------------------------------------------- #
# 통계 (numpy 만 쓴다)
# --------------------------------------------------------------------- #


def paired(a, b) -> dict:
    """평가 시드를 짝지은 t검정. evaluate.welch_paired 를 그대로 쓴다."""
    a, b = np.asarray(_floats(a)), np.asarray(_floats(b))
    md, sd, se, t = welch_paired(a, b)
    t = float(t)
    return {"diff": float(md), "sd": float(sd), "t": t,
            "sig": bool(math.isfinite(t) and abs(t) > T_CRIT)}


def iqm(x) -> float:
    """사분위 평균: 정렬해서 아래·위 25%(int(0.25n)개씩)를 버린 평균. scipy trim_mean(0.25)와 같다."""
    x = np.sort(np.asarray(x, dtype=np.float64).ravel())
    x = x[np.isfinite(x)]
    n = len(x)
    if n == 0:
        return float("nan")
    k = int(0.25 * n)
    return float(x[k:n - k].mean())


def stratified_bootstrap_ci(scores, stat=iqm, reps: int = 2000, alpha: float = 0.05,
                            seed: int = 0) -> dict:
    """층화 부트스트랩 퍼센타일 CI. `scores` 는 (R 학습 시드, T 층) 이다. 층은 평가 시드다.

    층마다 학습 시드 R 개를 복원추출한다(rliable StratifiedBootstrap 과 같은 방식). 1차원이면 층 하나다.
    학습 시드가 하나면 재표본이 모두 같아 CI 폭이 0 이다 — 그 경우 결론을 내지 않는다(6.1).
    """
    S = np.asarray(scores, dtype=np.float64)
    if S.ndim == 1:
        S = S[:, None]
    R, T = S.shape
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, R, size=(reps, R, T))
    boot = S[idx, np.arange(T)[None, None, :]]
    vals = np.array([stat(b) for b in boot])
    lo, hi = np.nanpercentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"point": float(stat(S)), "lo": float(lo), "hi": float(hi), "runs": R, "strata": T}


def linear_r2(obs: np.ndarray, act: np.ndarray) -> np.ndarray:
    """행동 차원마다 관측의 선형 회귀(절편 포함)로 설명되는 분산 비율. train_v2.linear_r2 와 같은 정의다."""
    obs = np.asarray(obs, dtype=np.float64)
    act = np.asarray(act, dtype=np.float64)
    X = np.c_[obs, np.ones(len(obs))]
    coef, *_ = np.linalg.lstsq(X, act, rcond=None)
    res = act - X @ coef
    var = act.var(0)
    return np.where(var > 1e-12, 1.0 - res.var(0) / np.maximum(var, 1e-12), np.nan)


def _floats(v) -> list[float]:
    return [float("nan") if x is None else float(x) for x in v]


def nanmean(v) -> float:
    v = np.asarray(_floats(v))
    v = v[np.isfinite(v)]
    return float(v.mean()) if len(v) else float("nan")


# --------------------------------------------------------------------- #
# 반응 곡선
# --------------------------------------------------------------------- #


def value_bins(x: np.ndarray, n_bins: int = 10, mass: float = 0.05) -> list[tuple[float, float, np.ndarray]]:
    """관측 한 열을 분위수 구간으로 나눈다. (하한, 상한, 마스크) 목록.

    최솟값·최댓값에 표본이 `mass` 이상 몰려 있으면(예: 포식자 안 보임 = pred_dist 1) 그 점을 따로 둔다.
    나머지는 분위수 경계로 나누고, 같은 경계는 합친다.
    """
    x = np.asarray(x, dtype=np.float64)
    rest = np.ones(len(x), dtype=bool)
    out = []
    for v in sorted({float(x.min()), float(x.max())}):
        m = x == v
        if m.mean() >= mass:
            out.append((v, v, m))
            rest &= ~m
    if rest.any():
        edges = np.unique(np.quantile(x[rest], np.linspace(0.0, 1.0, n_bins + 1)))
        if len(edges) == 1:
            out.append((float(edges[0]), float(edges[0]), rest))
        else:
            k = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, len(edges) - 2)
            for b in range(len(edges) - 1):
                m = rest & (k == b)
                if m.any():
                    out.append((float(edges[b]), float(edges[b + 1]), m))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def conditional_curve(x: np.ndarray, act: np.ndarray, n_bins: int = 10) -> list[dict]:
    """관측 구간마다 실제 표본의 조건부 평균 행동 (smart_check react 와 같은 방식, 개입 아님)."""
    act = np.asarray(act, dtype=np.float64)
    return [{"lo": lo, "hi": hi, "n": int(m.sum()), "x_mean": float(np.asarray(x)[m].mean()),
             "act": act[m].mean(0).tolist()} for lo, hi, m in value_bins(x, n_bins)]


def batched(policy, obs: np.ndarray, chunk: int = 8192) -> np.ndarray:
    return np.concatenate([np.asarray(policy(obs[i:i + chunk]), dtype=np.float64)
                           for i in range(0, len(obs), chunk)])


def intervention_curve(policy, obs: np.ndarray, j: int, grid) -> list[dict]:
    """관측 j 를 격자값으로 바꿔 넣고(나머지는 실제 표본) 평균 행동을 낸다 (부분 의존, 개입 검사)."""
    out = []
    for v in grid:
        o = np.array(obs, dtype=np.float32)
        o[:, j] = v
        out.append({"x": float(v), "act": batched(policy, o).mean(0).tolist()})
    return out


def quantile_grid(x: np.ndarray, qs=None) -> list[float]:
    qs = np.linspace(0.0, 1.0, 11) if qs is None else qs
    return [float(v) for v in np.unique(np.quantile(np.asarray(x, dtype=np.float64), qs))]


def react_conditions(obs: np.ndarray) -> dict[str, np.ndarray]:
    """smart_check.py 의 상황 구분 그대로. 실제 표본을 조건으로 나눈다."""
    o = obs
    q5 = o[:, 5]
    return {
        "포식자 보임 (dist<1)": o[:, 2] < 1.0,
        "포식자 안 보임": o[:, 2] >= 1.0,
        "포식자 가까움 (dist<0.4)": o[:, 2] < 0.4,
        "포식자 멂 (0.7~1)": (o[:, 2] >= 0.7) & (o[:, 2] < 1.0),
        "배고픔 (energy<0.3)": o[:, 4] < 0.3,
        "배부름 (energy>0.7)": o[:, 4] > 0.7,
        "위험 높음 (pred_ema 상위 20%)": q5 >= np.quantile(q5, 0.8),
        "위험 낮음 (pred_ema 하위 20%)": q5 <= np.quantile(q5, 0.2),
        "은신처 가까움 (cover<0.2)": o[:, 6] < 0.2,
        "은신처 멂 (cover>0.8)": o[:, 6] > 0.8,
        "먹이 많음 (food>0.6)": o[:, 0] > 0.6,
        "먹이 적음 (food<0.2)": o[:, 0] < 0.2,
        "동료 많음 (kin>0.5)": o[:, 3] > 0.5,
        "동료 적음 (kin<0.1)": o[:, 3] < 0.1,
    }


def react_table(obs: np.ndarray, acts: dict[str, np.ndarray], min_n: int = 50) -> dict:
    out = {}
    for name, m in react_conditions(obs).items():
        if m.sum() < min_n:
            continue
        out[name] = {"n": int(m.sum()), **{k: np.asarray(a)[m].mean(0).tolist() for k, a in acts.items()}}
    return out


# --------------------------------------------------------------------- #
# 대조군 스펙
# --------------------------------------------------------------------- #


def wrap(base: dict, *wrappers: dict) -> dict:
    return {"policy": base, "wrap": list(wrappers)}


def control_specs(base: dict, mean_action) -> dict[str, dict]:
    """C0, C1, C3-k, C1′. C1 은 학습 정책을 부르지 않는 상수 정책이다 (smart_check frozen_all 과 같다)."""
    mean = [float(x) for x in mean_action]
    specs = {"C0": base, "C1": {"kind": "fixed", "action": mean}}
    for k, name in enumerate(ACT_NAMES):
        specs[f"C3-{name}"] = wrap(base, {"kind": "act_fix", "dims": [k], "values": mean})
    specs["C1'"] = wrap(base, {"kind": "act_permute", "salt": 0})
    return specs


def obs_control_specs(base: dict, obs_mean, dims, modes) -> tuple[dict[str, dict], list[str]]:
    """C4-j. fix 는 학습 시드 평균 관측으로 고정, perm 은 같은 스텝 개체끼리 섞는다."""
    specs, notes = {}, []
    for j in dims:
        if "fix" in modes:
            specs[f"C4-{OBS_NAMES[j]}-fix"] = wrap(
                base, {"kind": "obs_fix", "dims": [j], "values": [float(obs_mean[j])]})
        if "perm" in modes:
            if j == OBS_RECENT_PREDATION:
                notes.append(f"C4-{OBS_NAMES[j]}-perm 생략: 관측 {j} 는 모든 개체가 같은 전역 값이라 "
                             "개체끼리 섞어도 바뀌지 않는다. 고정(fix)만 의미가 있다.")
                continue
            specs[f"C4-{OBS_NAMES[j]}-perm"] = wrap(base, {"kind": "obs_permute", "dims": [j], "salt": 0})
    return specs, notes


def seg_spec(base_action, bins, dims, table) -> dict:
    """C2-seg: 바탕은 C2 상수, 구간마다 `dims` 만 따로 상수."""
    return wrap({"kind": "fixed", "action": [float(x) for x in base_action]},
                {"kind": "seg_const", "bins": bins, "dims": list(dims),
                 "table": [float(x) for x in np.ravel(table)]})


def seg_labels(bins) -> list[str]:
    """구간 id 순서(segment_ids 의 혼합 기수, 앞 열이 큰 자리)대로 사람이 읽는 이름."""
    labels = [""]
    for j, thr in bins:
        name = OBS_NAMES[int(j)]
        edges = [-math.inf] + [float(t) for t in thr] + [math.inf]
        parts = []
        for k in range(len(edges) - 1):
            lo, hi = edges[k], edges[k + 1]
            if lo == -math.inf:
                parts.append(f"{name}<{hi:g}")
            elif hi == math.inf:
                parts.append(f"{name}≥{lo:g}")
            else:
                parts.append(f"{lo:g}≤{name}<{hi:g}")
        labels = [f"{a} & {b}" if a else b for a in labels for b in parts]
    return labels


def parse_bins(tokens) -> list[list]:
    """"2:0.5" 또는 "pred_dist:0.25,0.5" → [[2, [0.5]], ...]."""
    out = []
    for tok in tokens or []:
        j, _, ts = tok.partition(":")
        j = OBS_NAMES.index(j) if j in OBS_NAMES else int(j)
        thr = sorted(float(x) for x in ts.split(",") if x)
        if not thr:
            raise SystemExit(f"--seg-bins {tok!r}: 문턱이 없다 (예: 2:0.5)")
        out.append([j, thr])
    return out


def parse_dims(tokens, names) -> list[int]:
    return [names.index(t) if t in names else int(t) for t in tokens]


def parse_seeds(tokens) -> list[int]:
    """"10000:10020"(끝 제외) 또는 정수 나열."""
    out = []
    for tok in tokens:
        if ":" in str(tok):
            a, b = str(tok).split(":")
            out.extend(range(int(a), int(b)))
        else:
            out.append(int(tok))
    return out


# --------------------------------------------------------------------- #
# 보정: 학습 시드에서 평균 행동·평균 관측·표본
# --------------------------------------------------------------------- #


def calib_from_rows(rows: list[dict]) -> dict:
    """시드별 원시 합계 → 평균 행동·표준편차·평균 관측, 표본. 합산 순서는 smart_check 와 같다(시드순)."""
    rows = sorted(rows, key=lambda r: r["seed"])
    n = sum(r["_act_n"] for r in rows)
    mean = sum(r["_act_sum"] for r in rows) / n
    std = np.sqrt(np.maximum(sum(r["_act_sq"] for r in rows) / n - mean ** 2, 0.0))
    obs_mean = sum(r["_obs_sum"] for r in rows) / n
    obs = np.concatenate([r["_obs"] for r in rows]) if "_obs" in rows[0] else np.empty((0, OBS_DIM))
    act = np.concatenate([r["_act"] for r in rows]) if "_act" in rows[0] else np.empty((0, ACT_DIM))
    return {"mean_action": mean, "std_action": std, "obs_mean": obs_mean, "obs": obs, "act": act,
            "n": int(n)}


def calib_summary(cal: dict) -> dict:
    obs = cal["obs"]
    return {
        "seeds": cal.get("seeds"), "steps": cal.get("steps"), "record_every": cal.get("record_every"),
        "mean_action": dict(zip(ACT_NAMES, np.asarray(cal["mean_action"]).tolist())),
        "std_action": dict(zip(ACT_NAMES, np.asarray(cal["std_action"]).tolist())),
        "obs_mean": dict(zip(OBS_NAMES, np.asarray(cal["obs_mean"]).tolist())),
        "obs_quantiles_5_50_95": {OBS_NAMES[j]: np.quantile(obs[:, j], [0.05, 0.5, 0.95]).tolist()
                                  for j in range(OBS_DIM)} if len(obs) else None,
        "samples": int(len(obs)),
    }


# --------------------------------------------------------------------- #
# 실행 문맥
# --------------------------------------------------------------------- #


class Ctx:
    """명령 하나의 설정과 워커 풀."""

    def __init__(self, args):
        self.args = args
        self.cfg = load_v2_config(args.config)
        self.spec = base_spec(args)
        self.name = args.name or default_name(args, self.cfg)
        self.out = RESULTS / f"diag_{self.name}"
        # 계획서 6.1: G_γ 의 γ 는 그 정책의 학습 γ 다. 모델이 있으면 모델 γ 를 기본으로 쓴다.
        mg = model_gamma(args.model) if args.model else None
        if args.gamma is not None:
            self.gamma = float(args.gamma)
        elif mg is not None:
            self.gamma = float(mg)
        else:
            self.gamma = load_gamma()
        self.tail = int(args.tail) if args.tail is not None else tail_steps(self.gamma)
        lo, hi = self.cfg.eval_seeds
        self.eval_seeds = parse_seeds(args.eval_seeds) if args.eval_seeds else list(range(lo, hi))
        self.eval_steps = int(args.eval_steps)
        self.calib_seeds = parse_seeds(args.calib_seeds) if args.calib_seeds else list(CALIB_SEEDS)
        self.calib_steps = int(args.calib_steps)
        self.ex = None
        if mg is not None and abs(mg - self.gamma) > 1e-12:
            print(f"경고: 모델 학습 γ={mg} 와 다른 γ={self.gamma} 로 G_γ 를 잰다 (--gamma 지정).")
        self.model_sha1 = model_fingerprint(args.model) if args.model else None
        check_disjoint("보정 시드", self.calib_seeds, self.eval_seeds, args)

    def need_spec(self) -> dict:
        if self.spec is None:
            raise SystemExit("정책이 없다: --model <zip> 또는 --policy utility|fixed|random")
        return self.spec

    def run(self, specs, seeds, steps, record_every: int = 0):
        return run_specs(self.cfg, specs, seeds, steps, workers=self.args.workers, gamma=self.gamma,
                         tail=self.tail, record_every=record_every, executor=self.ex)

    def meta(self, **kw) -> dict:
        return {
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "command": "python diagnose_v2.py " + " ".join(sys.argv[1:]),
            "python": platform.python_version(),
            "name": self.name, "spec": self.spec,
            "eval_seeds": self.eval_seeds, "eval_steps": self.eval_steps,
            "gamma": self.gamma, "tail": self.tail, "model_sha1": self.model_sha1,
            "config_version": (getattr(self.cfg, "v2", None) or {}).get("version"),
            "config_digest": config_digest(self.cfg),
            **kw,
        }


def base_spec(args) -> dict | None:
    if args.model:
        return {"kind": "learned", "model": str(Path(args.model).resolve())}
    if args.policy == "utility":
        return {"kind": "utility"}
    if args.policy == "random":
        return {"kind": "random", "seed": 0}
    if args.policy == "fixed":
        if not args.action or len(args.action) != ACT_DIM:
            raise SystemExit("--policy fixed 는 --action 값 4개가 필요하다")
        return {"kind": "fixed", "action": [float(x) for x in args.action]}
    return None


def default_name(args, cfg=None) -> str:
    """모델 파일 이름(없으면 정책 종류). 설정 version 이 2.0 이 아니면 `_v2_0b` 처럼 붙인다 — v2.0 경로는 그대로다."""
    name = Path(args.model).stem if args.model else (args.policy or "report")
    ver = str((getattr(cfg, "v2", None) or {}).get("version") or "2.0")
    return name if ver == "2.0" else f"{name}_v{ver.replace('.', '_')}"


def model_fingerprint(path) -> str | None:
    """모델 파일 내용의 sha1 앞 12자리. 같은 이름으로 다시 학습하면 캐시·이전 결과를 쓰지 않게 한다."""
    p = Path(path)
    if not p.exists():
        return None
    return hashlib.sha1(p.read_bytes()).hexdigest()[:12]


def check_disjoint(what: str, seeds, eval_seeds, args) -> None:
    """계획서 5.0: 보정·탐색 시드는 평가 시드와 겹치면 안 된다. --allow-seed-overlap 으로만 푼다."""
    overlap = sorted(set(int(s) for s in seeds) & set(int(s) for s in eval_seeds))
    if overlap and not getattr(args, "allow_seed_overlap", False):
        raise SystemExit(f"{what}가 평가 시드와 겹친다: {overlap[:5]}{'…' if len(overlap) > 5 else ''} "
                         f"(일부러라면 --allow-seed-overlap)")


def config_digest(cfg) -> str:
    return hashlib.sha1(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]


def get_calib(ctx: Ctx) -> dict:
    """보정 롤아웃(학습 시드 × 3000)을 돌리거나 캐시에서 읽는다. 요약은 calib.json 으로 남긴다."""
    spec = ctx.need_spec()
    meta = {"spec": spec, "seeds": ctx.calib_seeds, "steps": ctx.calib_steps,
            "record_every": RECORD_EVERY, "config_digest": config_digest(ctx.cfg),
            "model_sha1": ctx.model_sha1}
    path = CACHE / ctx.name / "calib.npz"
    if path.exists() and not ctx.args.recalib:
        with np.load(path, allow_pickle=False) as z:
            if json.loads(str(z["meta"])) == meta:
                cal = {k: z[k] for k in ("mean_action", "std_action", "obs_mean", "obs", "act")}
                cal.update(n=int(z["n"]), seeds=ctx.calib_seeds, steps=ctx.calib_steps,
                           record_every=RECORD_EVERY)
                print(f"[보정] 캐시 사용 {path}")
                return cal
    t0 = time.time()
    rows = ctx.run({"C0": spec}, ctx.calib_seeds, ctx.calib_steps, record_every=RECORD_EVERY)["C0"]
    cal = calib_from_rows(rows)
    cal.update(seeds=ctx.calib_seeds, steps=ctx.calib_steps, record_every=RECORD_EVERY)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, meta=json.dumps(meta), n=cal["n"],
                        **{k: cal[k] for k in ("mean_action", "std_action", "obs_mean", "obs", "act")})
    save_json(ctx.out / "calib.json", {
        "meta": ctx.meta(calib_seeds=ctx.calib_seeds, calib_steps=ctx.calib_steps),
        "calib": calib_summary(cal),
        "outcome_mean_on_calib_seeds": {c: nanmean([r[c] for r in rows]) for c in ROW_COLUMNS},
    })
    print(f"[보정] 학습 시드 {ctx.calib_seeds[0]}~{ctx.calib_seeds[-1]} × {ctx.calib_steps} "
          f"({time.time() - t0:.0f}s) 평균 행동 {np.round(cal['mean_action'], 4).tolist()}", flush=True)
    return cal


# --------------------------------------------------------------------- #
# 표 만들기
# --------------------------------------------------------------------- #


def summarize(rows: list[dict]) -> dict:
    return {c: nanmean([r.get(c) for r in rows]) for c in ROW_COLUMNS}


def compare(rows: list[dict], ref: list[dict], cols=OUTCOME) -> dict:
    sa, sb = [r["seed"] for r in rows], [r["seed"] for r in ref]
    if sa != sb:
        raise ValueError(f"짝지을 시드가 다르다: {sa[:3]}... vs {sb[:3]}...")
    return {c: paired([r.get(c) for r in rows], [r.get(c) for r in ref]) for c in cols}


def control_table(res: dict[str, list[dict]], specs: dict | None = None, refs=("C0",)) -> dict:
    out = {}
    for name, rows in res.items():
        row = {"mean": summarize(rows)}
        if specs is not None and name in specs:
            row["spec"] = specs[name]
        for ref in refs:
            if ref in res and ref != name:
                row[f"vs_{ref}"] = compare(rows, res[ref])
        out[name] = row
    return out


def fmt(col: str, v) -> str:
    if v is None or not math.isfinite(float(v)):
        return "—"
    return format(float(v), COL_FMT.get(col, ".3f"))


def cell(col: str, mean, test: dict | None = None) -> str:
    s = fmt(col, mean)
    if test and test.get("t") is not None and math.isfinite(test["t"]):
        s += f" ({test['t']:+.2f}{'*' if test['sig'] else ''})"
    return s


def ctrl_label(name: str) -> str:
    if name in CTRL_LABEL:
        return CTRL_LABEL[name]
    if name.startswith("C3-"):
        return f"{name} ({name[3:]}만 평균)"
    if name.startswith("C4-") and name.endswith("-fix"):
        return f"{name} (평균 고정)"
    if name.startswith("C4-") and name.endswith("-perm"):
        return f"{name} (개체 순열)"
    return name


def tstr(test: dict) -> str:
    t = test.get("t")
    ts = "—" if t is None or not math.isfinite(t) else f"{t:+.2f}"
    return f"t={ts}, {'유의' if test.get('sig') else '유의 아님'}"


def md_table(controls: dict, cols, ref: str = "C0") -> list[str]:
    head = "| 대조군 | " + " | ".join(f"{COL_LABEL.get(c, c)}" for c in cols) + " |"
    lines = [head, "|---" * (len(cols) + 1) + "|"]
    for name, row in controls.items():
        test = row.get(f"vs_{ref}", {})
        lines.append(f"| {ctrl_label(name)} | " + " | ".join(
            cell(c, row["mean"].get(c), test.get(c)) for c in cols) + " |")
    return lines


def md_behavior(controls: dict) -> list[str]:
    head = "| 대조군 | " + " | ".join(f"`{c}`" for c in BEHAVIOR) + " |"
    lines = [head, "|---" * (len(BEHAVIOR) + 1) + "|"]
    for name, row in controls.items():
        lines.append(f"| {ctrl_label(name)} | " + " | ".join(fmt(c, row["mean"].get(c)) for c in BEHAVIOR) + " |")
    return lines


def md_meta(meta: dict, ref: str | None = "C0") -> list[str]:
    seeds = meta.get("eval_seeds") or []
    who = f"{ref} 와 " if ref else "표에 적은 비교 대상과 "
    return [
        f"- 생성: {meta.get('generated')} · `{meta.get('command')}`",
        f"- 정책: `{json.dumps(meta.get('spec'), ensure_ascii=False)}`",
        f"- 평가: 시드 {seeds[0] if seeds else '?'}~{seeds[-1] if seeds else '?'} ({len(seeds)}개) × "
        f"{meta.get('eval_steps')}스텝, deterministic",
        f"- G_γ: γ={meta.get('gamma')}, 롤아웃 끝 {meta.get('tail')}스텝(ceil(5/(1-γ)))은 평균에서 뺐다",
        f"- 괄호는 {who}짝지은 t (자유도 {max(len(seeds) - 1, 1)}), `*` 는 |t|>{T_CRIT}",
    ]


def md_ablate(d: dict) -> list[str]:
    c = d["controls"]
    cal = d["calib"]
    L = ["# 진단: ablate (C0, C1, C3-k, C1′)", ""]
    L += md_meta(d["meta"])
    L.append(f"- C1 평균 행동 (학습 시드 {cal['seeds'][0]}~{cal['seeds'][-1]} × {cal['steps']}스텝): "
             + ", ".join(f"{k} {v:.4f}" for k, v in cal["mean_action"].items()))
    L.append("- C1′ 는 같은 스텝에서 개체끼리 행동 벡터를 섞는다. 행동 분포는 C0 와 같고 상태 대응만 끊긴다.")
    L += ["", "## 결과 지표와 G_γ", ""]
    L += md_table(c, OUTCOME)
    L += ["", "## 행동 지표 (우열 아님)", ""]
    L += md_behavior(c)
    if "C1" in c and "vs_C0" in c["C1"]:
        t = c["C1"]["vs_C0"]
        r, g = t["mean_return"], t["g_gamma"]
        L += ["", "## T1 확인 (C0 vs C1)", "",
              f"- 평가 리턴: C1 − C0 = {r['diff']:+.2f} ({tstr(r)})",
              f"- G_γ: C1 − C0 = {g['diff']:+.4f} ({tstr(g)})"]
        side = "높다" if g["diff"] < 0 else "낮다"
        rel = g["diff"] / c["C0"]["mean"]["g_gamma"] if c["C0"]["mean"].get("g_gamma") else float("nan")
        if g["sig"] and not r["sig"]:
            L.append(f"- 평가 리턴으로는 차이가 없지만 G_γ 로는 C0 가 유의하게 {side} ({rel:+.1%}). "
                     "T1 은 지표(슬롯 보상률) 착시였다.")
        elif not g["sig"] and not r["sig"]:
            L.append(f"- G_γ 로도 유의한 차이가 없다 ({rel:+.1%}, 방향은 C0 가 {side}). T1 은 지표 착시만으로는 "
                     "설명되지 않는다 — 평균 행동 상수가 PPO 목적으로 재도 학습 정책에 가깝다.")
        else:
            L.append("- 평가 리턴에서 이미 차이가 난다. 표의 부호를 그대로 읽는다.")
        if "C1'" in c and "vs_C0" in c["C1'"]:
            p = c["C1'"]["vs_C0"]["g_gamma"]
            line = f"- 참고 C1′(행동 순열): G_γ 차 {p['diff']:+.4f} ({tstr(p)})."
            if c["C1'"]["mean"]["g_gamma"] < c["C1"]["mean"]["g_gamma"]:
                line += " 상태와 행동의 짝을 무작위로 끊으면 평균 상수(C1)보다도 나쁘다."
            L.append(line)
    return L


def md_const(d: dict) -> list[str]:
    tag = d["kind"]
    L = [f"# 진단: constsearch ({tag})", ""]
    L += md_meta(d["meta"], ref=None)
    s = d.get("search")
    if s:
        L.append(f"- 탐색: Optuna TPE {s['trials']}회, 목표 `{s['objective']}`, 시드 {s['search_seeds'][0]}~"
                 f"{s['search_seeds'][-1]} × {s['search_steps']}; 상위 {len(s['rescore'])}개를 시드 "
                 f"{s['rescore_seeds'][0]}~{s['rescore_seeds'][-1]} × {s['rescore_steps']} 로 재측정 → "
                 f"{s['best_trial']}")
    else:
        L.append("- 탐색 생략: `--const-action` 으로 받은 값을 그대로 평가했다")
    if tag == "C2":
        L.append("- 상수: " + ", ".join(f"{k} {v:.4f}" for k, v in zip(ACT_NAMES, d["best"])))
    else:
        L.append(f"- 바탕 C2 상수: {np.round(d['base_action'], 4).tolist()}, 구간별 행동: "
                 f"{[ACT_NAMES[k] for k in d['dims']]}")
        L += ["", "| 구간 | " + " | ".join(ACT_NAMES[k] for k in d["dims"]) + " |",
              "|---" * (len(d["dims"]) + 1) + "|"]
        for lab, row in zip(d["segments"], d["best_table"]):
            L.append(f"| {lab} | " + " | ".join(f"{v:.3f}" for v in row) + " |")
        if d.get("segment_spread") is not None:
            L.append("| 구간 간 최대−최소 | " + " | ".join(f"{v:.3f}" for v in d["segment_spread"]) + " |")
    L += ["", "## 평가 (괄호는 해당 비교 대상과 짝지은 t)", "",
          "| 정책 | " + " | ".join(COL_LABEL.get(c, c) for c in OUTCOME) + " |",
          "|---" * (len(OUTCOME) + 1) + "|"]
    for ref in [k for k in d["eval"] if k.startswith("vs_")]:
        L.append(f"| {tag} vs {ref[3:]} | "
                 + " | ".join(cell(c, d["eval"]["mean"][c], d["eval"][ref][c]) for c in OUTCOME) + " |")
    for name, m in d.get("ref_mean", {}).items():
        L.append(f"| {ctrl_label(name)} | " + " | ".join(fmt(c, m[c]) for c in OUTCOME) + " |")
    return L


def md_permute(d: dict) -> list[str]:
    L = ["# 진단: permute (C4-j 관측 고정·순열)", ""]
    L += md_meta(d["meta"])
    L.append("- fix: 학습 시드 평균 관측으로 고정. perm: 같은 스텝에서 개체끼리 그 열만 섞는다.")
    for n in d.get("notes", []):
        L.append(f"- {n}")
    L += ["", "## 결과 지표와 G_γ", ""]
    L += md_table(d["controls"], OUTCOME)
    L += ["", "## 행동 지표", ""]
    L += md_behavior(d["controls"])
    sens = d.get("offline_sensitivity")
    if sens:
        L += ["", "## 오프라인 민감도 (보정 표본에서 개입 전후 평균 |Δ행동|)", "",
              "| 대조군 | " + " | ".join(ACT_NAMES) + " |", "|---" * (ACT_DIM + 1) + "|"]
        for name, v in sens.items():
            L.append(f"| {name} | " + " | ".join(f"{x:.4f}" for x in v) + " |")
    return L


def md_r2(d: dict) -> list[str]:
    L = ["# 진단: 선형 R² (행동 차원별)", "",
         f"- 표본: 학습 시드 보정 롤아웃 {d['samples']}개 (관측 7 + 절편으로 회귀)",
         "- R² > 0.95 는 '규칙 수준'으로 적는다. 실패로 보지 않는다 (6.1-5).", "",
         "| 행동 | " + " | ".join(f"R² ({k})" for k in d["r2"]) + " | 표준편차 (C0) | 판정 |",
         "|---" * (len(d["r2"]) + 3) + "|"]
    for i, name in enumerate(ACT_NAMES):
        vals = [d["r2"][k][i] for k in d["r2"]]
        c0 = d["r2"]["C0"][i]
        verdict = "규칙 수준" if c0 is not None and c0 > 0.95 else ""
        L.append(f"| {name} | " + " | ".join("—" if v is None else f"{v:.3f}" for v in vals)
                 + f" | {d['act_std']['C0'][i]:.4f} | {verdict} |")
    return L


def md_curves(d: dict) -> list[str]:
    L = ["# 진단: 반응 곡선", "",
         "- 조건부: 실제 표본을 관측 분위수 구간으로 나눈 평균 행동 (smart_check react 와 같은 방식, 개입 아님)",
         "- 개입: 관측 j 만 격자값으로 바꿔 넣은 평균 행동 (부분 의존). 정책이 j 를 쓰는지는 이쪽으로 본다", ""]
    if d.get("react"):
        keys = [k for k in next(iter(d["react"].values())) if k != "n"]
        L += ["## 상황별 평균 행동", "",
              "| 상황 | n | " + " | ".join(f"{k} {a}" for k in keys for a in ACT_NAMES) + " |",
              "|---" * (2 + len(keys) * ACT_DIM) + "|"]
        for name, row in d["react"].items():
            L.append(f"| {name} | {row['n']} | " + " | ".join(f"{x:.3f}" for k in keys for x in row[k]) + " |")
        L.append("")
    for obs_name in OBS_NAMES:
        L += [f"## {obs_name}", "", "| 구간 | n | " + " | ".join(ACT_NAMES) + " |", "|---" * (ACT_DIM + 2) + "|"]
        for b in d["conditional"][obs_name]:
            rng = f"{b['lo']:.3f}" if b["lo"] == b["hi"] else f"{b['lo']:.3f}~{b['hi']:.3f}"
            L.append(f"| {rng} | {b['n']} | " + " | ".join(f"{x:.3f}" for x in b["act"]) + " |")
        L += ["", "| 개입값 | " + " | ".join(ACT_NAMES) + " |", "|---" * (ACT_DIM + 1) + "|"]
        for p in d["intervention"][obs_name]:
            L.append(f"| {p['x']:.3f} | " + " | ".join(f"{x:.3f}" for x in p["act"]) + " |")
        L.append("")
    return L


# --------------------------------------------------------------------- #
# 저장
# --------------------------------------------------------------------- #


def clean(o):
    """JSON 으로 쓸 수 있게 numpy 값을 풀고 nan·inf 는 null 로 쓴다."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return f if math.isfinite(f) else None
    return o


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(data), ensure_ascii=False, indent=1), encoding="utf-8")


def save(ctx: Ctx, stem: str, data: dict, lines: list[str]) -> None:
    save_json(ctx.out / f"{stem}.json", data)
    (ctx.out / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {ctx.out / (stem + '.json')}\n      {ctx.out / (stem + '.md')}")


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def reference_rows(ctx: Ctx, name: str, stem: str = "ablate") -> list[dict] | None:
    """같은 디렉터리의 이전 결과에서 대조군 행을 꺼낸다. 평가 조건이 같을 때만 쓴다."""
    d = load_json(ctx.out / f"{stem}.json")
    if not d:
        return None
    m = d["meta"]
    same = (m.get("eval_seeds") == ctx.eval_seeds and m.get("eval_steps") == ctx.eval_steps
            and m.get("gamma") == ctx.gamma and m.get("tail") == ctx.tail
            and m.get("config_digest") == config_digest(ctx.cfg)
            and m.get("model_sha1") == ctx.model_sha1
            and (ctx.spec is None or m.get("spec") == ctx.spec or stem != "ablate"))
    rows = d.get("per_seed", {}).get(name)
    return rows if same and rows else None


def print_controls(controls: dict, ref: str = "C0") -> None:
    for name, row in controls.items():
        m, t = row["mean"], row.get(f"vs_{ref}", {})
        parts = []
        for c in OUTCOME:
            s = fmt(c, m.get(c))
            if c in t and t[c]["t"] is not None and math.isfinite(t[c]["t"]):
                s += f"({t[c]['t']:+.2f})"
            parts.append(f"{c} {s}")
        print(f"  {name:24s} " + "  ".join(parts), flush=True)


# --------------------------------------------------------------------- #
# 서브커맨드
# --------------------------------------------------------------------- #


def cmd_ablate(ctx: Ctx) -> int:
    base = ctx.need_spec()
    t0 = time.time()
    cal = get_calib(ctx)
    specs = control_specs(base, cal["mean_action"])
    if ctx.args.utility and base.get("kind") != "utility":
        specs["Utility"] = {"kind": "utility"}
    res = ctx.run(specs, ctx.eval_seeds, ctx.eval_steps)
    controls = control_table(res, specs)
    data = {"meta": ctx.meta(elapsed_s=round(time.time() - t0, 1)), "calib": calib_summary(cal),
            "controls": controls, "per_seed": {k: [public_row(r) for r in v] for k, v in res.items()}}
    save(ctx, "ablate", data, md_ablate(clean(data)))
    print_controls(controls)
    return 0


def search_constants(ctx: Ctx, make_spec, names: list[str], enqueue) -> tuple[list[float], dict]:
    """상태를 안 보는 상수 탐색. smart_check constsearch 와 같은 절차(TPE, constant_liar, 7개씩 묶음)."""
    import optuna

    a = ctx.args
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    obj = a.objective
    if obj == "g_gamma" and a.search_steps <= ctx.tail:
        raise SystemExit(f"--search-steps {a.search_steps} 가 G_γ 꼬리 {ctx.tail} 이하다")

    def score(rows):
        return float(np.mean([r[obj] for r in rows]))

    search_seeds = parse_seeds(a.search_seeds) if a.search_seeds else list(SEARCH_SEEDS)
    rescore_seeds = parse_seeds(a.rescore_seeds) if a.rescore_seeds else list(RESCORE_SEEDS)
    check_disjoint("탐색 시드", search_seeds, ctx.eval_seeds, a)
    check_disjoint("재측정 시드", rescore_seeds, ctx.eval_seeds, a)
    sampler = optuna.samplers.TPESampler(seed=a.tpe_seed, constant_liar=True)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    for v in enqueue:
        study.enqueue_trial(dict(zip(names, [float(x) for x in v])))
    dist = {k: optuna.distributions.FloatDistribution(0.0, 1.0) for k in names}
    history, done, t0 = [], 0, time.time()
    while done < a.trials:
        trials = [study.ask(dist) for _ in range(min(BATCH, a.trials - done))]
        specs = {f"t{t.number}": make_spec([t.params[k] for k in names]) for t in trials}
        res = ctx.run(specs, search_seeds, a.search_steps)
        for t in trials:
            v = score(res[f"t{t.number}"])
            study.tell(t, v)
            history.append({"trial": t.number, "params": [t.params[k] for k in names], "value": v})
        done += len(trials)
        print(f"  {done}/{a.trials}  best {study.best_value:.3f} "
              f"{[round(study.best_params[k], 3) for k in names]}  ({time.time() - t0:.0f}s)", flush=True)

    # 선택 편향을 줄이려고 상위 몇 개를 다른 학습 시드로 다시 잰다
    top = sorted([t for t in study.trials if t.value is not None], key=lambda t: -t.value)[:a.top_k]
    params = {f"t{t.number}": [t.params[k] for k in names] for t in top}
    res = ctx.run({k: make_spec(v) for k, v in params.items()}, rescore_seeds, a.rescore_steps)
    scores = {k: score(v) for k, v in res.items()}
    best_key = max(scores, key=scores.get)
    print(f"  재측정 {({k: round(v, 3) for k, v in scores.items()})} → {best_key} "
          f"{np.round(params[best_key], 3).tolist()}", flush=True)
    info = {"objective": obj, "trials": a.trials, "search_seeds": search_seeds,
            "search_steps": a.search_steps, "rescore_seeds": rescore_seeds,
            "rescore_steps": a.rescore_steps, "tpe_seed": a.tpe_seed,
            "enqueued": [list(map(float, v)) for v in enqueue], "search_best": study.best_value,
            "search_best_params": [study.best_params[k] for k in names], "rescore": scores,
            "best_trial": best_key, "history": history}
    return params[best_key], info


def c2_base_action(ctx: Ctx) -> list:
    """C2-seg 의 바탕 상수 = 같은 디렉터리 constsearch.json(C2)의 best. 같은 설정에서 잰 C2 만 쓴다.

    출력 디렉터리 기본 이름은 모델 파일 이름이라, 설정만 바꿔(v2.0 → v2.0b) 같은 모델을 진단하면 다른
    설정의 C2 가 조용히 바탕이 된다. 결과 meta 에는 지금 설정이 적혀 섞인 것이 드러나지 않는다.
    """
    c2 = load_json(ctx.out / "constsearch.json")
    if not c2:
        raise SystemExit("--base-action 이 없고 같은 디렉터리에 constsearch.json(C2) 도 없다")
    if c2.get("meta", {}).get("config_digest") != config_digest(ctx.cfg):
        raise SystemExit(f"{ctx.out / 'constsearch.json'} 은 다른 설정에서 잰 C2 다 "
                         f"(config_version {c2.get('meta', {}).get('config_version')!r}) — "
                         "이 설정으로 C2 를 다시 재거나(--name 으로 디렉터리를 나눈다) --base-action 을 준다")
    return c2["best"]


def cmd_constsearch(ctx: Ctx) -> int:
    a = ctx.args
    t0 = time.time()
    bins = parse_bins(a.seg_bins)
    seg = bool(bins)
    tag = "C2-seg" if seg else "C2"
    stem = a.tag or ("constsearch_seg" if seg else "constsearch")

    if seg:
        dims = parse_dims(a.seg_dims or [], ACT_NAMES)
        if not dims:
            raise SystemExit("--seg-bins 를 쓰면 --seg-dims 로 구간별 행동을 정해야 한다")
        base_action = a.base_action if a.base_action is not None else c2_base_action(ctx)
        base_action = [float(x) for x in base_action]
        S = n_segments(bins)
        names = [f"s{s}_{ACT_NAMES[k]}" for s in range(S) for k in dims]

        def make_spec(vec):
            return seg_spec(base_action, bins, dims, vec)

        def default_enqueue():
            return [[base_action[k] for _ in range(S) for k in dims]]    # C2 자체(모든 구간이 C2 값)
    else:
        dims, base_action, S = list(range(ACT_DIM)), None, 1
        names = list(ACT_NAMES)        # smart_check 와 같은 이름 — TPE 결과가 같아진다

        def make_spec(vec):
            return {"kind": "fixed", "action": [float(x) for x in vec]}

        def default_enqueue():
            # smart_check 와 같은 순서: C1 평균 행동, v1 학습 전 최고 상수
            first = [np.asarray(get_calib(ctx)["mean_action"]).tolist()] if ctx.spec is not None else []
            return first + [V1_PRETRAIN_BEST]

    if a.const_action is not None:
        if len(a.const_action) != len(names):
            raise SystemExit(f"--const-action 은 값 {len(names)}개가 필요하다 ({names})")
        best, search = [float(x) for x in a.const_action], None
    else:
        enqueue = a.enqueue if a.enqueue is not None else default_enqueue()
        best, search = search_constants(ctx, make_spec, names, enqueue)

    specs = {tag: make_spec(best)}
    refs = {}
    for ref in ("C0", "C1", "Utility"):
        rows = reference_rows(ctx, ref)
        if rows is not None:
            refs[ref] = rows
    if "C0" not in refs and ctx.spec is not None:
        specs["C0"] = ctx.spec
    if seg:
        c2 = load_json(ctx.out / "constsearch.json")
        same_c2 = bool(c2) and [float(x) for x in c2.get("best", [])] == base_action
        c2rows = reference_rows(ctx, "C2", stem="constsearch") if same_c2 else None
        if c2rows is not None:
            refs["C2"] = c2rows
        else:
            specs["C2"] = {"kind": "fixed", "action": base_action}
    res = ctx.run(specs, ctx.eval_seeds, ctx.eval_steps)
    rows = res.pop(tag)
    refs.update(res)
    ev = {"mean": summarize(rows)}
    for ref in (["C2"] if seg else []) + ["C0", "C1", "Utility"]:
        if ref in refs:
            ev[f"vs_{ref}"] = compare(rows, refs[ref])
    data = {"meta": ctx.meta(elapsed_s=round(time.time() - t0, 1)), "kind": tag, "best": best,
            "names": names, "search": search, "eval": ev,
            "ref_mean": {k: summarize(v) for k, v in refs.items()},
            "per_seed": {tag: [public_row(r) for r in rows],
                         **{k: [public_row(r) if "_act_sum" in r else r for r in v] for k, v in refs.items()}}}
    if seg:
        data.update(bins=bins, dims=dims, base_action=base_action, segments=seg_labels(bins),
                    best_table=np.asarray(best).reshape(S, len(dims)).tolist(),
                    # 게이트 조건 "구간별 최적값이 서로 다르다"를 보는 값: 행동마다 구간 간 최대−최소
                    segment_spread=np.ptp(np.asarray(best).reshape(S, len(dims)), axis=0).tolist())
    save(ctx, stem, data, md_const(clean(data)))
    for ref in [k for k in ev if k.startswith("vs_")]:
        t = ev[ref]
        print(f"  {tag} vs {ref[3:]}: " + "  ".join(
            f"{c} {fmt(c, ev['mean'][c])}({tstr(t[c])})" for c in OUTCOME), flush=True)
    return 0


def offline_sensitivity(spec: dict, obs: np.ndarray, act0: np.ndarray, N: int) -> list[float]:
    """보정 표본에서 개입한 정책과 원래 행동 `act0` 의 차 |Δa| 평균.

    표본은 스텝마다 N 개씩 묶여 있다. 순열 래퍼가 같은 스텝 개체끼리 섞도록 N 개씩 넣는다.
    """
    p1 = build_policy(spec, 0)
    n = (len(obs) // N) * N
    a1 = np.concatenate([np.asarray(p1(obs[i:i + N]), np.float64) for i in range(0, n, N)])
    return np.abs(a1 - np.asarray(act0[:n], np.float64)).mean(0).tolist()


def cmd_permute(ctx: Ctx) -> int:
    base = ctx.need_spec()
    a = ctx.args
    t0 = time.time()
    cal = get_calib(ctx)
    dims = parse_dims(a.obs, OBS_NAMES) if a.obs else list(range(OBS_DIM))
    specs, notes = obs_control_specs(base, cal["obs_mean"], dims, a.modes)
    c0 = reference_rows(ctx, "C0")
    run = dict(specs)
    if c0 is None:
        run = {"C0": base, **specs}
    res = ctx.run(run, ctx.eval_seeds, ctx.eval_steps)
    if c0 is not None:
        res = {"C0": c0, **res}
    controls = control_table(res, run)
    N = int(ctx.cfg.N)
    p0 = build_policy(base, 0)
    n = (len(cal["obs"]) // N) * N
    act0 = np.concatenate([np.asarray(p0(cal["obs"][i:i + N]), np.float64) for i in range(0, n, N)])
    sens = {name: offline_sensitivity(sp, cal["obs"], act0, N) for name, sp in specs.items()}
    data = {"meta": ctx.meta(elapsed_s=round(time.time() - t0, 1)), "notes": notes,
            "obs_mean": dict(zip(OBS_NAMES, np.asarray(cal["obs_mean"]).tolist())),
            "controls": controls, "offline_sensitivity": sens,
            "per_seed": {k: [public_row(r) if "_act_sum" in r else r for r in v] for k, v in res.items()}}
    save(ctx, a.tag or "permute", data, md_permute(clean(data)))
    print_controls(controls)
    return 0


def reference_actions(base: dict, obs: np.ndarray) -> dict[str, np.ndarray]:
    """비교용 Utility 행동. 바탕 정책이 Utility 면 비운다."""
    if base.get("kind") == "utility":
        return {}
    return {"Utility": batched(build_policy({"kind": "utility"}), obs)}


def cmd_curves(ctx: Ctx) -> int:
    base = ctx.need_spec()
    cal = get_calib(ctx)
    obs, act = cal["obs"], np.asarray(cal["act"], dtype=np.float64)
    pol = build_policy(base, 0)
    acts = {"C0": act, **reference_actions(base, obs)}
    data = {
        "meta": ctx.meta(samples=int(len(obs)), calib_seeds=ctx.calib_seeds, calib_steps=ctx.calib_steps),
        "react": react_table(obs, acts),
        "conditional": {OBS_NAMES[j]: conditional_curve(obs[:, j], act) for j in range(OBS_DIM)},
        "intervention": {OBS_NAMES[j]: intervention_curve(pol, obs, j, quantile_grid(obs[:, j]))
                         for j in range(OBS_DIM)},
        "act_std": {k: np.asarray(v).std(0).tolist() for k, v in acts.items()},
    }
    save(ctx, "curves", data, md_curves(clean(data)))
    return 0


def cmd_r2(ctx: Ctx) -> int:
    base = ctx.need_spec()
    cal = get_calib(ctx)
    obs, act = cal["obs"], np.asarray(cal["act"], dtype=np.float64)
    acts = {"C0": act, **reference_actions(base, obs)}
    data = {"meta": ctx.meta(calib_seeds=ctx.calib_seeds, calib_steps=ctx.calib_steps),
            "samples": int(len(obs)),
            "r2": {k: linear_r2(obs, v).tolist() for k, v in acts.items()},
            "act_std": {k: np.asarray(v).std(0).tolist() for k, v in acts.items()}}
    save(ctx, "r2", data, md_r2(clean(data)))
    for k, v in data["r2"].items():
        print(f"  R² {k}: " + " ".join(f"{n} {x:.3f}" for n, x in zip(ACT_NAMES, v)))
    return 0


def aggregate(abl: list[dict], cols=OUTCOME, reps: int = 2000) -> dict:
    """학습 시드(디렉터리)별 ablate 결과 → 대조군마다 IQM 과 층화 부트스트랩 95% CI.

    점수 행렬은 (학습 시드, 평가 시드) 다. 차이는 같은 학습 시드·같은 평가 시드의 C0 와 뺀다.
    """
    seeds = [[r["seed"] for r in d["per_seed"]["C0"]] for d in abl]
    if any(s != seeds[0] for s in seeds):
        raise SystemExit("디렉터리마다 평가 시드가 다르다 — 층화할 수 없다")
    digests = [d.get("meta", {}).get("config_digest") for d in abl]
    if any(g != digests[0] for g in digests):
        raise SystemExit(f"디렉터리마다 설정이 다르다(config_digest {digests}) — 다른 세계의 결과를 묶지 않는다")
    names = [n for n in abl[0]["per_seed"] if all(n in d["per_seed"] for d in abl)]
    out = {}
    for name in names:
        out[name] = {}
        for c in cols:
            S = np.array([_floats(r[c] for r in d["per_seed"][name]) for d in abl])
            C0 = np.array([_floats(r[c] for r in d["per_seed"]["C0"]) for d in abl])
            out[name][c] = {"iqm": stratified_bootstrap_ci(S, reps=reps),
                            "diff_vs_C0": stratified_bootstrap_ci(S - C0, reps=reps)}
    return out


def md_aggregate(agg: dict, dirs: list[str]) -> list[str]:
    L = ["# 학습 시드 묶음 (IQM, 층화 부트스트랩 95% CI)", "",
         f"- 학습 시드(디렉터리): {', '.join(dirs)}",
         "- 층 = 평가 시드. 층마다 학습 시드를 복원추출한다. 차이 CI 가 0 을 넘지 않으면 `*`",
         "- 학습 시드가 하나면 CI 폭이 0 이다. 그때는 결론을 내지 않는다 (6.1-4)", "",
         "| 대조군 | " + " | ".join(f"{COL_LABEL.get(c, c)} IQM [CI] / Δ vs C0" for c in OUTCOME) + " |",
         "|---" * (len(OUTCOME) + 1) + "|"]
    for name, row in agg.items():
        cells = []
        for c in OUTCOME:
            i, d = row[c]["iqm"], row[c]["diff_vs_C0"]
            sig = d["lo"] is not None and d["hi"] is not None and (d["lo"] > 0 or d["hi"] < 0)
            s = f"{fmt(c, i['point'])} [{fmt(c, i['lo'])}, {fmt(c, i['hi'])}]"
            if name != "C0":
                s += f" / {fmt(c, d['point'])} [{fmt(c, d['lo'])}, {fmt(c, d['hi'])}]{'*' if sig else ''}"
            cells.append(s)
        L.append(f"| {ctrl_label(name)} | " + " | ".join(cells) + " |")
    return L


def resolve_dir(d: str) -> Path:
    p = Path(d)
    if p.is_dir():
        return p
    for cand in (RESULTS / f"diag_{d}", RESULTS / d):
        if cand.is_dir():
            return cand
    raise SystemExit(f"진단 디렉터리를 찾지 못했다: {d}")


def report_sections(path: Path) -> list[str]:
    """디렉터리의 결과 JSON 을 종류별로 모은다. `--tag` 로 이름을 바꾼 파일(constsearch_* 등)도 포함한다."""
    L = []
    for pattern, fn in (("ablate*.json", md_ablate), ("constsearch*.json", md_const),
                        ("permute*.json", md_permute), ("r2*.json", md_r2), ("curves*.json", md_curves)):
        for f in sorted(path.glob(pattern)):
            d = load_json(f)
            if not d:
                continue
            body = fn(d)
            body[0] += f" — `{f.name}`"
            # 보고서 안에서는 제목을 한 단계씩 내린다
            L += [("#" + line) if line.startswith("#") else line for line in body] + [""]
    return L


def cmd_report(ctx: Ctx) -> int:
    a = ctx.args
    dirs = [resolve_dir(d) for d in a.dirs] if a.dirs else [ctx.out]
    L = [f"# 진단 보고서: {ctx.name}", "",
         f"> 자동 생성: `python diagnose_v2.py {' '.join(sys.argv[1:])}` "
         f"({datetime.now(timezone.utc).isoformat(timespec='seconds')})", ""]
    data = {"dirs": [str(p) for p in dirs]}
    if len(dirs) > 1:
        abl = [load_json(p / "ablate.json") for p in dirs]
        if any(x is None for x in abl):
            raise SystemExit("모든 디렉터리에 ablate.json 이 있어야 묶을 수 있다")
        agg = aggregate(abl, reps=a.reps)
        data["aggregate"] = agg
        L += md_aggregate(agg, [p.name for p in dirs]) + [""]
    for p in dirs:
        if len(dirs) > 1:
            L += [f"# {p.name}", ""]
        L += report_sections(p)
    ctx.out.mkdir(parents=True, exist_ok=True)
    if len(dirs) > 1:
        save_json(ctx.out / "report.json", data)
    (ctx.out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"저장: {ctx.out / 'report.md'}")
    return 0


# --------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------- #


COMMANDS = {"ablate": cmd_ablate, "constsearch": cmd_constsearch, "permute": cmd_permute,
            "curves": cmd_curves, "r2": cmd_r2, "report": cmd_report}


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    g = common.add_argument_group("정책·출력")
    g.add_argument("--model", default=None, help="학습 정책 zip")
    g.add_argument("--policy", choices=["utility", "fixed", "random"], default=None)
    g.add_argument("--action", type=float, nargs=ACT_DIM, default=None, help="--policy fixed 의 행동 4개")
    g.add_argument("--name", default=None, help="results/v2/diag_<이름>. 기본은 모델 파일 이름")
    g.add_argument("--config", default=None, help="기본 configs/v2.yaml")
    g.add_argument("--workers", type=int, default=6, help="워커 프로세스 수 (기본 6)")
    g.add_argument("--gamma", type=float, default=None,
                   help="G_γ 의 γ. 기본은 모델의 학습 γ, 모델이 없으면 configs/ppo_best.yaml")
    g.add_argument("--tail", type=int, default=None, help="평균에서 뺄 끝 스텝. 기본 ceil(5/(1-γ))")
    g.add_argument("--eval-seeds", nargs="+", default=None, help="기본 10000:10020")
    g.add_argument("--eval-steps", type=int, default=5000)
    g.add_argument("--calib-seeds", nargs="+", default=None, help="기본 0:20")
    g.add_argument("--calib-steps", type=int, default=CALIB_STEPS)
    g.add_argument("--recalib", action="store_true", help="보정 캐시를 무시하고 다시 잰다")
    g.add_argument("--allow-seed-overlap", action="store_true",
                   help="보정·탐색 시드가 평가 시드와 겹쳐도 진행한다 (계획서 5.0 위반이므로 진단용)")
    g.add_argument("--tag", default=None, help="산출 파일 이름(확장자 제외)을 바꾼다")

    p = argparse.ArgumentParser(description="V2 진단 도구 (계획서 0-3)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ablate", parents=[common], help="C0, C1, C3-k, C1′ 와 G_γ")
    s.add_argument("--no-utility", dest="utility", action="store_false", help="Utility 참고 행을 뺀다")

    s = sub.add_parser("constsearch", parents=[common], help="C2 최적 상수 (또는 --seg-bins 로 C2-seg)")
    s.add_argument("--const-action", type=float, nargs="+", default=None, help="탐색을 건너뛰고 이 상수를 평가")
    s.add_argument("--objective", choices=["g_gamma", "mean_return"], default="g_gamma",
                   help="탐색 목표. 판정 양은 G_γ 다(5.0). smart_check 재현은 mean_return")
    s.add_argument("--trials", type=int, default=TRIALS)
    s.add_argument("--top-k", type=int, default=TOP_K)
    s.add_argument("--tpe-seed", type=int, default=0)
    s.add_argument("--search-seeds", nargs="+", default=None, help="기본 0:8")
    s.add_argument("--search-steps", type=int, default=SEARCH_STEPS)
    s.add_argument("--rescore-seeds", nargs="+", default=None, help="기본 100:120")
    s.add_argument("--rescore-steps", type=int, default=RESCORE_STEPS)
    s.add_argument("--enqueue", type=float, nargs="+", action="append", default=None,
                   help="탐색 시작점(여러 번). 기본: C1 평균 행동, v1 학습 전 최고 상수")
    s.add_argument("--seg-bins", nargs="+", default=None, help="C2-seg 구간. 예: 2:0.5 4:0.5")
    s.add_argument("--seg-dims", nargs="+", default=None, help="구간마다 상수를 갖는 행동 (이름 또는 번호)")
    s.add_argument("--base-action", type=float, nargs=ACT_DIM, default=None,
                   help="C2-seg 바탕 상수. 기본은 같은 디렉터리 constsearch.json 의 C2")

    s = sub.add_parser("permute", parents=[common], help="C4-j 관측 고정·순열")
    s.add_argument("--obs", nargs="+", default=None, help="관측 (이름 또는 번호). 기본 7개 전부")
    s.add_argument("--modes", nargs="+", choices=["fix", "perm"], default=["fix", "perm"])

    sub.add_parser("curves", parents=[common], help="반응 곡선 (조건부·개입)")
    sub.add_parser("r2", parents=[common], help="행동 차원별 선형 R²")

    s = sub.add_parser("report", parents=[common], help="결과 JSON → report.md")
    s.add_argument("--dirs", nargs="+", default=None, help="여러 학습 시드 진단 디렉터리 → IQM·CI")
    s.add_argument("--reps", type=int, default=2000, help="부트스트랩 반복 수")
    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:  # pragma: no cover
        pass
    args = build_parser().parse_args(argv)
    if args.cmd == "constsearch" and args.enqueue is not None:
        bad = [v for v in args.enqueue if len(v) != ACT_DIM]
        if bad and not args.seg_bins:
            raise SystemExit(f"--enqueue 는 값 {ACT_DIM}개씩이다: {bad}")
    ctx = Ctx(args)
    print(f"[{args.cmd}] {ctx.name} → {ctx.out}  (γ={ctx.gamma}, 꼬리 {ctx.tail}스텝, 워커 {args.workers})",
          flush=True)
    ctx.ex = make_executor(args.workers) if args.cmd not in ("report", "curves", "r2") else None
    try:
        return COMMANDS[args.cmd](ctx)
    finally:
        if ctx.ex is not None:
            ctx.ex.shutdown()


if __name__ == "__main__":
    sys.exit(main())
