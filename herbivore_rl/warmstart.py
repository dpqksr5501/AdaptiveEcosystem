"""§6.1 모방 초기화.

    python warmstart.py

튜닝된 Utility AI(§5.2)를 흉내 내도록 SB3 정책을 지도학습으로 먼저 맞춘 뒤, 그 가중치를
PPO 시작점으로 쓴다. 산출물 `ckpt/warmstart.zip`.

§6.6의 "모방 초기화 직후 대비 20% 이상 상승" 기준선이 되므로, 맞춘 직후의 성능을
`ckpt/warmstart_baseline.json`에 같이 적어 둔다. 학습이 끝난 뒤 이 숫자와 비교한다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from env.config import load_config
from env.rollout import run_policy, std_of
from env.vec_env import make_vec_env
from env.world import World
from policies.registry import make_policy
from train import CKPT, make_model
from tune_utility import tuning_seeds

ROOT = Path(__file__).resolve().parent

N_PAIRS = 50_000     # §6.1
CLIP_LO, CLIP_HI = 0.05, 0.95
EPOCHS = 20
LR = 1e-3


# --------------------------------------------------------------------- #
# 1) 데이터 수집 (§6.1-1)
# --------------------------------------------------------------------- #


def collect(cfg, policy, seeds, n_pairs=N_PAIRS, warmup=200, stride=25, per_seed=1200):
    """(관측, 행동) 쌍을 모은다. 시드 0~999 (§3.5 학습 대역).

    초기 상태만 잔뜩 모으면 정책이 본 적 없는 후반 상태를 못 배운다. 시드마다 `warmup`
    스텝 굴린 뒤 `stride` 간격으로 표본을 뜬다.
    """
    obs_buf, act_buf, got = [], [], 0
    for seed in seeds:
        w = World(cfg, seeds=[int(seed)])
        for t in range(per_seed):
            o = w.observe()
            a = policy(o)
            if t >= warmup and (t - warmup) % stride == 0:
                obs_buf.append(o.copy())
                act_buf.append(a.copy())
                got += len(o)
            w.step(a)
            if got >= n_pairs:
                break
        if got >= n_pairs:
            break
    obs = np.concatenate(obs_buf)[:n_pairs].astype(np.float32)
    act = np.concatenate(act_buf)[:n_pairs].astype(np.float64)
    return obs, act


def to_logits(act: np.ndarray) -> np.ndarray:
    """§6.1-2 — acts = clip(acts, 0.05, 0.95), logits = log(acts / (1-acts))."""
    a = np.clip(act, CLIP_LO, CLIP_HI)
    return np.log(a / (1.0 - a)).astype(np.float32)


# --------------------------------------------------------------------- #
# 2) 지도학습 (§6.1-3)
# --------------------------------------------------------------------- #


def fit(model, obs: np.ndarray, logits: np.ndarray, epochs=EPOCHS, lr=LR, batch=1024, seed=0):
    """`get_distribution(obs).distribution.mean` 이 logits를 MSE로 맞추게 한다.

    이 평균값은 `mlp_extractor.policy_net` → `action_net` 을 지난 결과다. §8.1이 내보내는
    바로 그 세 층이라, 여기서 맞춘 것이 그대로 C++로 간다. `log_std` 와 `value_net` 은
    이 손실에 기여하지 않으므로 갱신되지 않는다.
    """
    policy = model.policy
    device = policy.device
    X = torch.as_tensor(obs, device=device)
    Y = torch.as_tensor(logits, device=device)
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    g = torch.Generator(device="cpu").manual_seed(seed)
    n = len(X)
    history = []

    policy.train()
    for ep in range(epochs):
        perm = torch.randperm(n, generator=g).to(device)
        total = 0.0
        for i in range(0, n, batch):
            idx = perm[i : i + batch]
            pred = policy.get_distribution(X[idx]).distribution.mean
            loss = torch.nn.functional.mse_loss(pred, Y[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.detach().item() * len(idx)
        history.append(total / n)
        print(f"  epoch {ep + 1:2d}/{epochs}  mse={history[-1]:.5f}", flush=True)
    policy.eval()
    return history


# --------------------------------------------------------------------- #


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="§6.1 모방 초기화")
    p.add_argument("--pairs", type=int, default=N_PAIRS)
    p.add_argument("--epochs", type=int, default=EPOCHS)
    p.add_argument("--lr", type=float, default=LR)
    p.add_argument("--eval-steps", type=int, default=3000)
    p.add_argument("--out", default=str(CKPT / "warmstart.zip"))
    p.add_argument("--config", default=None)
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    seeds = tuning_seeds(cfg)          # §6.6 비교가 성립하도록 §5.2와 같은 시드
    utility = make_policy({"kind": "utility"})

    print(f"1) Utility AI로 (관측, 행동) {args.pairs:,}쌍 수집 — 시드 0~999")
    obs, act = collect(cfg, utility, np.random.default_rng(1).permutation(1000), args.pairs)
    logits = to_logits(act)
    print(f"   obs {obs.shape} {obs.dtype} | act {act.shape} "
          f"| logit 범위 [{logits.min():.3f}, {logits.max():.3f}]")

    print(f"2) SB3 정책 MSE 적합 — Adam lr={args.lr}, {args.epochs} epoch")
    venv = make_vec_env(cfg)
    model = make_model(venv, tensorboard_log=None)
    history = fit(model, obs, logits, epochs=args.epochs, lr=args.lr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save(out)
    print(f"   저장: {out}")

    print(f"3) 모방 직후 성능 측정 — §6.6 기준선 (시드 {len(seeds)}개 × {args.eval_steps} 스텝)")
    rows, mean = run_policy(cfg, {"kind": "learned", "model": str(out)},
                            seeds, args.eval_steps)
    sd = std_of(rows)
    _, util_mean = run_policy(cfg, {"kind": "utility"}, seeds, args.eval_steps)

    baseline = {
        "_generated": {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "by": "warmstart.py (§6.1)",
            "python": platform.python_version(),
            "note": "자동 생성. §6.6의 '모방 초기화 직후 대비 20% 이상 상승' 기준선이다.",
        },
        "mean_return": mean["mean_return"],
        "mean_return_std": sd["mean_return"],
        "target_20pct": mean["mean_return"] * 1.2,
        "utility_reference": util_mean["mean_return"],
        "final_mse": history[-1],
        "conditions": {"seeds": list(seeds), "steps": args.eval_steps, "pairs": len(obs)},
        "stats": mean,
    }
    bpath = out.with_name("warmstart_baseline.json")
    bpath.write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"   모방 초기화 mean_return = {mean['mean_return']:.2f} ± {sd['mean_return']:.2f}")
    print(f"   (원본 Utility AI = {util_mean['mean_return']:.2f})")
    print(f"   §6.6 목표: 10M 학습 후 {baseline['target_20pct']:.2f} 이상")
    print(f"   저장: {bpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
