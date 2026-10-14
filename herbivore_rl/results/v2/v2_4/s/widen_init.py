"""v2.4s 대응 1회의 시작 가중치 만들기 (`PREREG.md` 2절: v2.1 출시 모델 가중치로 시작, 새 관측 두 칸은 0).

    # herbivore_rl/ 에서
    python results/v2/v2_4/s/widen_init.py

1) configs/v2_4s.yaml 세계로 train_v2 를 1 스텝 돌려 관측 9·행동 5 모양의 PPO zip 을 만든다(같은 망 구조·튜닝값).
2) 그 zip 의 정책 state_dict 에 s1a_g_s58(관측 7) 값을 넣는다. 첫 층(정책망·가치망)의 가중치는 앞 7열을 복사하고
   visibility·to_transition 두 열은 0 이다. 나머지 텐서는 모양이 같아 그대로 복사한다. 그래서 처음에는 v2.1 출시 모델과
   같은 행동·가치를 낸다(아래에서 확인한다).
3) ckpt/v2/v2_4s_init_from_s1a_g_s58.zip 으로 저장한다. 학습은 train_v2.py --init 이 이 zip 의 정책 가중치를 옮겨 온다.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: F401,E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

SRC = ROOT / "ckpt" / "v2" / "s1a_g_s58.zip"
DST = ROOT / "ckpt" / "v2" / "v2_4s_init_from_s1a_g_s58.zip"


def main() -> int:
    from stable_baselines3 import PPO

    with tempfile.TemporaryDirectory() as td:
        shell = Path(td) / "shell.zip"
        cmd = [sys.executable, "train_v2.py", "--config", "configs/v2_4s.yaml", "--steps", "1", "--seed", "0",
               "--gamma", "0.995", "--out", str(shell), "--tb", str(Path(td) / "tb"), "--threads", "1"]
        subprocess.run(cmd, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        tgt = PPO.load(shell, device="cpu")
    src = PPO.load(SRC, device="cpu")
    sd_t, sd_s = tgt.policy.state_dict(), src.policy.state_dict()
    out, widened = {}, []
    for k, v in sd_t.items():
        s = sd_s[k]
        if v.shape == s.shape:
            out[k] = s.clone()
        elif v.dim() == 2 and v.shape[0] == s.shape[0] and v.shape[1] == s.shape[1] + 2:
            w = torch.zeros_like(v)
            w[:, : s.shape[1]] = s
            out[k] = w
            widened.append(k)
        else:
            raise SystemExit(f"모양이 맞지 않는다: {k} {tuple(v.shape)} vs {tuple(s.shape)}")
    tgt.policy.load_state_dict(out)
    # 확인: 관측 앞 7칸이 같으면 새 모델의 평균 행동·가치가 v2.1 모델과 같다(새 두 칸 값과 무관)
    rng = np.random.default_rng(0)
    o7 = rng.random((256, 7)).astype(np.float32)
    o9 = np.concatenate([o7, rng.random((256, 2)).astype(np.float32)], 1)
    with torch.no_grad():
        a7 = src.policy.get_distribution(torch.as_tensor(o7)).distribution.mean.numpy()
        a9 = tgt.policy.get_distribution(torch.as_tensor(o9)).distribution.mean.numpy()
        v7 = src.policy.predict_values(torch.as_tensor(o7)).numpy()
        v9 = tgt.policy.predict_values(torch.as_tensor(o9)).numpy()
    da, dv = float(np.abs(a7 - a9).max()), float(np.abs(v7 - v9).max())
    assert da < 1e-5 and dv < 1e-5, (da, dv)
    tgt.save(DST)
    print(f"넓힌 텐서 {widened}, 행동 차 {da:.2e}, 가치 차 {dv:.2e} → {DST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
