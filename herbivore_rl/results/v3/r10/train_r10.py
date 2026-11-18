"""R10 한 종 학습 묶음 (0 단계 사양 2 절, R9 train_r9 꼴을 줄임).

    python -X utf8 results/v3/r10/train_r10.py --species deer --decisions 2000000 --out ckpt/r10/small [--init <zip>] [--brains wolf=<npz> ...]

- PPO(SB3) + 감각 마스크 정책(r10.policy) · 망 206 → 128 → 128 → 24 tanh · γ 0.99.
- 판: <out>/<종>_<결정>.zip (SB3, 옵티마이저 포함) · .npz (numpy 가중치 + meta_json: 계약 해시·카드 sha·배운 범위·맵 범위·규칙).
- 상대: --brains 종=npz 가 없으면 공통 규칙 두뇌. 이름 모를 동물은 늘 규칙 두뇌.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from r10 import contract as C  # noqa: E402
from r10 import mapgen as G  # noqa: E402
from r10 import policy as P  # noqa: E402
from r10 import species as S  # noqa: E402
from r10 import world as W  # noqa: E402
from r10.vec_env import R10VecEnv  # noqa: E402


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip() or "?"
    except Exception:  # noqa: BLE001
        return "?"


def load_brain(path: str) -> dict:
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z["meta_json"][()]))
        if meta.get("io_hash") != C.io_hash():
            raise ValueError(f"{path}: io_hash {meta.get('io_hash')} != contract {C.io_hash()}")
        return {k: np.array(z[k]) for k in ("W0", "B0", "W1", "B1", "W2", "B2")}


def save_brain(path: Path, weights: dict, meta: dict) -> None:
    arrays = dict(weights)
    arrays["meta_json"] = np.array(json.dumps(meta, sort_keys=True, ensure_ascii=True))
    with open(path, "wb") as fh:
        np.savez(fh, **arrays)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--species", required=True)
    ap.add_argument("--cards", default=str(S.SPECIES_DIR), help="종 카드 폴더")
    ap.add_argument("--only", nargs="*", default=None, help="이 종들만 세계에 (기본 카드 폴더 전부)")
    ap.add_argument("--decisions", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--init", default=None)
    ap.add_argument("--brains", nargs="*", default=[], help="종=npz (상대 고정 두뇌)")
    ap.add_argument("--worlds", type=int, default=8)
    ap.add_argument("--learner-cap", type=int, default=8)
    ap.add_argument("--n-steps", type=int, default=64)
    ap.add_argument("--batch-size", type=int, default=2048)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--snapshot-every", type=int, default=1_000_000)
    ap.add_argument("--wall-hours", type=float, default=24.0)
    ap.add_argument("--flat", action="store_true", help="작은 확인: 평평하고 물 없는 맵만")
    a = ap.parse_args(argv)

    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback

    torch.set_num_threads(1)
    cards = S.load_all(a.cards)
    if a.only:
        cards = {k: v for k, v in cards.items() if k in set(a.only) | {a.species}}
    brains = {}
    for spec in a.brains:
        sid, _, path = spec.partition("=")
        brains[sid] = load_brain(path)
    overrides = {"shape": "flat", "water": "none"} if a.flat else None
    env = R10VecEnv(a.species, cards, n_worlds=a.worlds, learner_cap=a.learner_cap, brains=brains, seed=a.seed,
                    map_overrides=overrides)
    policy_cls = P.make_sb3_policy()
    if a.init:
        model = PPO.load(a.init, env=env, device="cpu", custom_objects={"policy_class": policy_cls, "learning_rate": a.lr})
    else:
        model = PPO(policy_cls, env, n_steps=a.n_steps, batch_size=a.batch_size, learning_rate=a.lr, gamma=a.gamma,
                    gae_lambda=0.95, ent_coef=0.01, clip_range=0.2, n_epochs=4, seed=a.seed, device="cpu", verbose=0,
                    policy_kwargs=dict(net_arch=dict(pi=list(C.NET["hidden"]), vf=list(C.NET["hidden"])), activation_fn=torch.nn.Tanh))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    card = cards[a.species]
    meta_base = {"format": "r10-brain", "version": 1, "species": a.species, "io_hash": C.io_hash(), "card_sha": sha(card),
                 "trained_range": S.trained_range(card), "map_ranges_sha": sha(G.RANGES), "rules": dataclasses.asdict(W.Rules()),
                 "world_species": sorted(cards), "opponent_brains": sorted(brains), "flat": a.flat, "git": git_sha(), "seed": a.seed}
    log = (out / f"{a.species}.log.jsonl").open("a", encoding="utf-8")
    t0 = time.time()

    def snapshot(tag):
        w = P.extract_sb3(model)
        stem = out / f"{a.species}_{tag}"
        model.save(str(stem) + ".zip")
        save_brain(Path(str(stem) + ".npz"), w, dict(meta_base, decisions=int(model.num_timesteps)))
        return stem

    class Cb(BaseCallback):
        def __init__(self):
            super().__init__()
            self.next_snap = a.snapshot_every
            self.rets = []

        def _on_step(self):
            for info in self.locals.get("infos", []):
                if "episode" in info:
                    self.rets.append(info["episode"]["r"])
            if self.num_timesteps >= self.next_snap:
                self.next_snap += a.snapshot_every
                snapshot(self.num_timesteps)
            return (time.time() - t0) < a.wall_hours * 3600

        def _on_rollout_end(self):
            w = env.world
            row = {"t": self.num_timesteps, "wall_s": round(time.time() - t0, 1),
                   "dps": round(self.num_timesteps / max(time.time() - t0, 1e-6), 1),
                   "ep_ret": round(float(np.mean(self.rets[-200:])), 3) if self.rets else None,
                   "E": round(float(w.E[env.learner_slots][w.alive[env.learner_slots]].mean()), 3) if w.alive[env.learner_slots].any() else None,
                   "deaths": dict(__import__("collections").Counter(d[4] for d in w.events["deaths"]))}
            log.write(json.dumps(row) + "\n")
            log.flush()
            print(json.dumps(row), flush=True)

    model.learn(total_timesteps=a.decisions, callback=Cb(), reset_num_timesteps=a.init is None, progress_bar=False)
    stem = snapshot(model.num_timesteps)
    print(f"끝: {stem}.zip / .npz · {model.num_timesteps:,} 결정 · {time.time() - t0:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
