"""A3 H-스레드 보조: torch 스레드 수가 같은 입력의 기울기 계산을 비트 단위로 바꾸는지 본다 (학습·가중치 갱신 없음).

v2_1c_s30 정책을 싣고 고정 표본 배치(관측 4096개, 행동 4096개, 시드 고정)에서 PPO 와 같은 꼴의 손실
(−log π(a|s)·A + 0.5·(V − R)² − ent)을 한 번 역전파해 기울기를 저장한다. 프로세스 하나에서 스레드 1, 다른 하나에서 3.
실행(herbivore_rl 에서): python results/v2/s1a_diag/a3_threads_numeric.py
산출: results/v2/s1a_diag/a3_threads_numeric.json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
H = HERE.parents[2]


def child(threads: int, out: str) -> None:
    sys.path.insert(0, str(H))
    import env.torch_init  # noqa: F401
    import numpy as np
    import torch as th
    from stable_baselines3 import PPO

    th.set_num_threads(threads)
    model = PPO.load(str(H / "ckpt" / "v2" / "v2_1c_s30.zip"), device="cpu")
    pol = model.policy
    pol.set_training_mode(True)
    rng = np.random.default_rng(12345)
    B = 4096
    obs = th.as_tensor(rng.random((B, 7)), dtype=th.float32)
    act = th.as_tensor(rng.uniform(-3, 3, (B, 5)), dtype=th.float32)
    adv = th.as_tensor(rng.standard_normal(B), dtype=th.float32)
    ret = th.as_tensor(rng.standard_normal(B), dtype=th.float32)
    values, logp, ent = pol.evaluate_actions(obs, act)
    loss = -(logp * adv).mean() + 0.5 * ((values.flatten() - ret) ** 2).mean() - 0.0009 * ent.mean()
    pol.zero_grad()
    loss.backward()
    grads = {n: p.grad.detach().numpy().astype(np.float32) for n, p in pol.named_parameters() if p.grad is not None}
    np.savez(out, loss=np.float32(loss.item()), **grads)


def main() -> None:
    outs = {}
    for t in (1, 3, 1):
        pass
    files = []
    for i, t in enumerate((1, 3, 1)):
        f = HERE / f"_a3_grad_t{t}_{i}.npz"
        subprocess.run([sys.executable, __file__, "child", str(t), str(f)], check=True)
        files.append((t, f))
    import numpy as np
    loaded = [(t, dict(np.load(f))) for t, f in files]
    (t1, g1), (t3, g3), (t1b, g1b) = loaded
    res = {"batch": 4096, "model": "ckpt/v2/v2_1c_s30.zip", "tensors": {}}
    n_diff13, n_diff11 = 0, 0
    for k in g1:
        a, b, c = g1[k], g3[k], g1b[k]
        d13 = int((a.view(np.uint32) != b.view(np.uint32)).sum()) if a.shape else int(a != b)
        d11 = int((a.view(np.uint32) != c.view(np.uint32)).sum()) if a.shape else int(a != c)
        rel = float(np.abs(a - b).max() / (np.abs(a).max() + 1e-30))
        res["tensors"][k] = {"size": int(a.size), "bits_diff_t1_vs_t3": d13, "bits_diff_t1_vs_t1": d11,
                             "max_rel_diff_t1_vs_t3": rel}
        n_diff13 += d13 > 0
        n_diff11 += d11 > 0
    res["n_tensors"] = len(g1)
    res["n_tensors_differ_t1_vs_t3"] = n_diff13
    res["n_tensors_differ_t1_vs_t1"] = n_diff11
    (HERE / "a3_threads_numeric.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for _, f in files:
        f.unlink()
    print(json.dumps({k: v for k, v in res.items() if k != "tensors"}))
    for k, v in res["tensors"].items():
        print(k, v)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        child(int(sys.argv[2]), sys.argv[3])
    else:
        main()
