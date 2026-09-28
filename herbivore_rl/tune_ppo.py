"""§6.4 PPO 하이퍼파라미터 튜닝.

    python tune_ppo.py --trials 40

탐색 대상은 **`learning_rate`, `gamma`, `ent_coef`, `clip_range`, `n_epochs` 다섯 개뿐**이다.
§6.4·§12: `net_arch` 와 `activation_fn` 은 탐색 금지 — §9.3의 C++ 추론 함수와 §8.1 export가
7-64-64-4 / tanh 에 의존한다. `train.make_model()` 이 이를 강제한다.

목표 함수는 §5.2 튜닝과 **같다**: 같은 시드 20개에서 잰 `mean_return` (§0, §7.2).

## 왜 필요했나

기본값(§6.3)으로 10M을 돌린 결과 `train/std` 가 1.08 → 4.74로 폭주했다. `ent_coef=0.01`
의 엔트로피 보너스가 가우시안 표준편차를 계속 키웠고, `clamp(-3,3) → sigmoid` 를 지나며
행동이 0/1로 포화돼 성능이 모방 초기화 대비 −1.2%로 떨어졌다 (1M 시점엔 +6.4%였다).
`ent_coef` 가 바로 이 탐색 대상 안에 있다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import optuna
import yaml
from stable_baselines3 import PPO

from env.config import load_config
from env.rollout import run_policy
from env.vec_env import make_vec_env
from train import CKPT, PPO_KWARGS, make_model
from tune_utility import tuning_seeds

PPO_DEFAULTS = {k: v for k, v in PPO_KWARGS.items() if k != "policy_kwargs"}

ROOT = Path(__file__).resolve().parent
BEST_PATH = ROOT / "configs" / "ppo_best.yaml"

# §6.4 탐색 대상. 이 다섯 개 외에는 건드리지 않는다.
SEARCH = {
    "learning_rate": ("float_log", 1e-5, 1e-3),
    "gamma": ("float", 0.990, 0.9995),
    "ent_coef": ("float_log", 1e-6, 2e-2),
    "clip_range": ("float", 0.10, 0.40),
    "n_epochs": ("int", 3, 20),
}
FORBIDDEN = {"net_arch", "activation_fn", "policy_kwargs"}


def suggest(trial: optuna.Trial) -> dict:
    out = {}
    for name, spec in SEARCH.items():
        kind, lo, hi = spec
        if kind == "float_log":
            out[name] = trial.suggest_float(name, lo, hi, log=True)
        elif kind == "float":
            out[name] = trial.suggest_float(name, lo, hi)
        else:
            out[name] = trial.suggest_int(name, lo, hi)
    assert not (FORBIDDEN & set(out)), "§6.4 탐색 금지 항목이 들어갔다"
    return out


def train_once(cfg, params: dict, steps: int, warmstart: Path, tmp: Path):
    """§6.1 가중치에서 시작해 `steps` 만큼 학습하고 체크포인트 경로를 돌려준다."""
    venv = make_vec_env(cfg)
    model = make_model(venv, tensorboard_log=None, **params)
    if warmstart.exists():
        donor = PPO.load(warmstart, device="cpu")
        model.policy.load_state_dict(donor.policy.state_dict())
    model.learn(total_timesteps=steps, progress_bar=False)
    model.save(tmp)
    final_std = float(model.policy.log_std.exp().mean())
    venv.close()
    return tmp, final_std


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="§6.4 PPO 하이퍼파라미터 튜닝")
    p.add_argument("--trials", type=int, default=40)
    p.add_argument("--train-steps", type=int, default=2_000_000,
                   help="trial당 학습 스텝. 본 학습(10M)보다 짧게 잡아 탐색을 돌린다")
    p.add_argument("--eval-steps", type=int, default=3000)
    p.add_argument("--warmstart", default=str(CKPT / "warmstart.zip"))
    p.add_argument("--study", default="ppo_v1")
    p.add_argument("--storage", default=str(ROOT / "optuna_ppo.db"))
    p.add_argument("--config", default=None)
    p.add_argument("--out", default=str(BEST_PATH))
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    seeds = tuning_seeds(cfg)
    warmstart = Path(args.warmstart)
    tmp = CKPT / "_tune_tmp.zip"
    tmp.parent.mkdir(parents=True, exist_ok=True)

    print(f"trial {args.trials} × 학습 {args.train_steps:,} 스텝 × 평가 시드 {len(seeds)}개")
    print(f"탐색 대상: {list(SEARCH)}")
    print(f"탐색 금지: {sorted(FORBIDDEN)}  (§6.4 — C++ 추론 함수가 의존한다)")

    _, ws_mean = run_policy(cfg, {"kind": "learned", "model": str(warmstart)},
                            seeds, args.eval_steps)
    baseline = ws_mean["mean_return"]
    print(f"모방 초기화 기준선 = {baseline:.2f}  → §6.6 목표 {baseline * 1.2:.2f}\n")

    def objective(trial: optuna.Trial) -> float:
        params = suggest(trial)
        ckpt, std = train_once(cfg, params, args.train_steps, warmstart, tmp)
        _, m = run_policy(cfg, {"kind": "learned", "model": str(ckpt)}, seeds, args.eval_steps)
        trial.set_user_attr("policy_std", std)
        for k, v in m.items():
            trial.set_user_attr(k, v)
        print(f"  trial {trial.number:3d} ret={m['mean_return']:7.2f} "
              f"({m['mean_return']/baseline - 1:+6.1%})  std={std:5.2f}  "
              f"ent={params['ent_coef']:.2e} lr={params['learning_rate']:.2e} "
              f"γ={params['gamma']:.4f} clip={params['clip_range']:.2f} "
              f"ep={params['n_epochs']}", flush=True)
        return m["mean_return"]

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        study_name=args.study, storage=f"sqlite:///{args.storage}",
        direction="maximize", load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=0),
    )
    if not study.trials:
        # §6.3 기본값을 1번 trial로. 탐색이 이보다 나쁠 수 없게 하고, 동시에
        # 기본값의 std 폭주를 같은 조건에서 기록해 둔다.
        study.enqueue_trial({k: PPO_DEFAULTS[k] for k in SEARCH})
    done = sum(t.state != optuna.trial.TrialState.WAITING for t in study.trials)
    study.optimize(objective, n_trials=max(0, args.trials - done))

    best = study.best_trial
    doc = {
        "_generated": {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "by": "tune_ppo.py (§6.4)",
            "python": platform.python_version(),
            "optuna": optuna.__version__,
            "note": "자동 생성. 손으로 고치지 말고 tune_ppo.py를 다시 돌려라.",
        },
        "params": {k: (int(v) if k == "n_epochs" else float(v))
                   for k, v in best.params.items()},
        "not_searched": {
            "net_arch": [64, 64],
            "activation_fn": "Tanh",
            "reason": "§6.4·§12 탐색 금지. §9.3 C++ RunPolicy와 §8.1 export가 의존한다.",
        },
        "objective": {
            "metric": "mean_return",
            "value": float(best.value),
            "warmstart_baseline": float(baseline),
            "ratio_vs_warmstart": float(best.value / baseline),
            "policy_std_at_end": float(best.user_attrs.get("policy_std", float("nan"))),
        },
        "conditions": {
            "seeds": list(seeds),
            "train_steps": args.train_steps,
            "eval_steps": args.eval_steps,
            "trials": len(study.trials),
            "best_trial": best.number,
        },
        "stats_at_best": {k: float(v) for k, v in best.user_attrs.items()},
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)

    print(f"\n최적: " + "  ".join(f"{k}={v}" for k, v in best.params.items()))
    print(f"mean_return {best.value:.2f} (모방 대비 {best.value/baseline - 1:+.1%}) "
          f"| policy_std {doc['objective']['policy_std_at_end']:.2f}")
    print(f"저장: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
