"""§5.2 Utility AI 튜닝.

    python tune_utility.py                # 300 trial
    python tune_utility.py --trials 50    # 짧게

목표는 `World.stats()["mean_return"]` 최대화 (§7.2). 학습 정책과 **같은 목표 함수**를
써야 하므로 롤아웃은 `env/rollout.py` 한 곳을 공유한다 (§0).

시드는 0~999에서 고른 20개를 **모든 trial에 고정**해서 쓴다. trial마다 다른 시드를 쓰면
Optuna가 정책이 아니라 시드 운을 최적화한다. 어떤 20개인지는 산출물에 적어 둔다.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import optuna
import yaml

from env.config import load_config
from env.rollout import run_policy, std_of
from policies.utility import BEST_PATH, SEARCH_SPACE, UTILITY_PARAMS

ROOT = Path(__file__).resolve().parent
SEED_POOL_RNG = 0        # 시드 20개를 뽑는 RNG. 바꾸면 튜닝을 다시 돌려야 한다.
N_SEEDS = 20
STEPS = 3000


def tuning_seeds(cfg) -> list[int]:
    """§3.5 학습 시드 대역(0~999)에서 결정적으로 20개."""
    lo, hi = cfg.train_seeds
    pool = np.arange(lo, hi)
    return sorted(
        int(s) for s in np.random.default_rng(SEED_POOL_RNG).choice(pool, N_SEEDS, replace=False)
    )


def objective_for(cfg, seeds, steps, workers):
    def objective(trial: optuna.Trial) -> float:
        params = {k: trial.suggest_float(k, *rng) for k, rng in SEARCH_SPACE.items()}
        rows, mean = run_policy(
            cfg, {"kind": "utility", "params": params}, seeds, steps, workers
        )
        for col, v in mean.items():
            trial.set_user_attr(col, v)
        trial.set_user_attr("return_std", std_of(rows)["mean_return"])
        return mean["mean_return"]

    return objective


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="§5.2 Utility AI Optuna 튜닝")
    p.add_argument("--trials", type=int, default=300)
    p.add_argument("--steps", type=int, default=STEPS)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--study", default="utility_v1")
    p.add_argument("--storage", default=str(ROOT / "optuna_utility.db"))
    p.add_argument("--config", default=None)
    p.add_argument("--out", default=str(BEST_PATH))
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    seeds = tuning_seeds(cfg)
    print(f"시드 {N_SEEDS}개 (§3.5 학습 대역): {seeds}")
    print(f"trial {args.trials} × 시드 {len(seeds)} × {args.steps} 스텝")

    # §5.3 판정용 기준선. 튜닝과 완전히 같은 조건에서 잰다.
    base_rows, base_mean = run_policy(
        cfg, {"kind": "random", "seed": 0}, seeds, args.steps, args.workers
    )
    baseline = base_mean["mean_return"]
    print(f"랜덤 기준선 mean_return = {baseline:.2f} ± {std_of(base_rows)['mean_return']:.2f}")

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        study_name=args.study,
        storage=f"sqlite:///{args.storage}",
        direction="maximize",
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=0),
    )
    # 스펙의 시작점(§5.1)을 1번 trial로 넣어 둔다. 튜닝이 이보다 나쁠 수 없게.
    if not study.trials:
        study.enqueue_trial(dict(UTILITY_PARAMS))

    # enqueue한 trial은 WAITING 상태로 study.trials에 들어간다. 아직 돌지 않았으니
    # 완료 수에서 빼야 총 trial 수가 --trials 와 맞는다.
    done = sum(t.state != optuna.trial.TrialState.WAITING for t in study.trials)
    remaining = max(0, args.trials - done)
    if done:
        print(f"기존 study에서 이어서 진행: {done} trial 완료, {remaining} 남음")

    def log(st: optuna.Study, tr: optuna.trial.FrozenTrial):
        n = len(st.trials)
        if n % 10 == 0 or n == 1:
            print(f"  trial {n:3d}/{args.trials}  best={st.best_value:7.2f} "
                  f"(x{st.best_value / baseline:.2f})  last={tr.value:7.2f}", flush=True)

    study.optimize(
        objective_for(cfg, seeds, args.steps, args.workers),
        n_trials=remaining,
        callbacks=[log],
    )

    best = study.best_trial
    ratio = best.value / baseline if baseline > 0 else float("nan")
    write_best(Path(args.out), cfg, seeds, args, study, best, baseline, ratio)

    print(f"\n최적 파라미터: " + "  ".join(f"{k}={v:.4f}" for k, v in best.params.items()))
    print(f"mean_return {best.value:.2f}  (랜덤 {baseline:.2f} 대비 x{ratio:.2f})")
    print(f"§5.3 '랜덤 대비 2배 이상' — {'통과' if ratio >= 2.0 else '미달'}")
    print(f"저장: {args.out}")
    return 0


def write_best(out: Path, cfg, seeds, args, study, best, baseline, ratio) -> None:
    """§5.3 산출물. 재현에 필요한 조건을 전부 같이 적는다 (§12 '헤더를 손으로 적지 말 것')."""
    doc = {
        "_generated": {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "by": "tune_utility.py (§5.2)",
            "python": platform.python_version(),
            "optuna": optuna.__version__,
            "note": "자동 생성. 손으로 고치지 말고 tune_utility.py를 다시 돌려라.",
        },
        "params": {k: float(v) for k, v in best.params.items()},
        "objective": {
            "metric": "mean_return",
            "value": float(best.value),
            "std_over_seeds": float(best.user_attrs.get("return_std", float("nan"))),
            "random_baseline": float(baseline),
            "ratio_vs_random": float(ratio),
            "spec_5_3_pass": bool(ratio >= 2.0),
        },
        "conditions": {
            "seeds": list(seeds),
            "seed_pool": list(cfg.train_seeds),
            "seed_pool_rng": SEED_POOL_RNG,
            "steps": args.steps,
            "trials": len(study.trials),
            "best_trial": best.number,
            "config": args.config or "configs/default.yaml",
        },
        "stats_at_best": {
            k: float(v) for k, v in best.user_attrs.items() if k != "return_std"
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


if __name__ == "__main__":
    sys.exit(main())
