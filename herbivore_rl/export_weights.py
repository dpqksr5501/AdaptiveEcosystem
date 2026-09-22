"""§8.1 가중치 내보내기.

    python export_weights.py                     # ckpt/final.zip -> export/

SB3 정책에서 **세 층만** 가져간다 (§8.1):

    mlp_extractor.policy_net.0   Linear 7  -> 64
    mlp_extractor.policy_net.2   Linear 64 -> 64
    action_net                   Linear 64 -> 4

`value_net`, `log_std`, optimizer 상태는 버린다. 게임 런타임에는 추론만 필요하다.

산출물:
  export/PolicyWeights.h        §8.1 형식의 C 헤더. 주석은 학습 설정에서 자동 생성
  export/PolicyGoldenVectors.h  §9.8-1 검증용 100쌍. C++ 자동화 테스트가 파일 I/O 없이 읽는다
  export/verify.npz             §8.1 — 관측 100개 + sigmoid 후 출력 100개

§12: 헤더 주석을 손으로 적지 말 것. 이 스크립트가 채운다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

from env.config import load_config
from env.vec_env import sigmoid

ROOT = Path(__file__).resolve().parent
EXPORT = ROOT / "export"
N_VERIFY = 100

# 생성된 헤더는 언리얼 모듈에도 바로 들어가야 한다. 손으로 복사하면 언젠가 어긋난다.
UE_POLICY_DIR = (
    ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
)
GENERATED = ("PolicyWeights.h", "PolicyGoldenVectors.h", "UtilityParams.h")

# §3.1 관측 이름. 골든 벡터 헤더 주석에 쓴다.
OBS_NAMES = ["food_density", "predator_count", "predator_distance", "kin_count",
             "energy", "recent_predation", "cover_distance"]
ACT_NAMES = ["forage", "cohesion", "flee_dist", "cover"]


# --------------------------------------------------------------------- #
# 추출
# --------------------------------------------------------------------- #


def extract(model: PPO) -> dict[str, np.ndarray]:
    """세 층의 weight/bias를 float32 numpy로. torch의 Linear.weight는 (out, in)이다."""
    net = model.policy.mlp_extractor.policy_net
    head = model.policy.action_net
    layers = [("0", net[0]), ("1", net[2]), ("2", head)]
    shapes = [(64, 7), (64, 64), (4, 64)]

    out = {}
    for (tag, lin), want in zip(layers, shapes):
        w = lin.weight.detach().cpu().numpy().astype(np.float32)
        b = lin.bias.detach().cpu().numpy().astype(np.float32)
        if w.shape != want:
            raise SystemExit(f"W{tag} shape {w.shape} != {want} — §8.1 구조가 바뀌었다")
        out[f"W{tag}"], out[f"B{tag}"] = w, b
    return out


def forward(obs: np.ndarray, w: dict) -> np.ndarray:
    """§9.3 C++ RunPolicy 와 **같은 순서**의 numpy 순전파.

    tanh → tanh → clamp(-3,3) → sigmoid. §8.2 검증이 이 함수를 쓴다.
    """
    h1 = np.tanh(obs @ w["W0"].T + w["B0"])
    h2 = np.tanh(h1 @ w["W1"].T + w["B1"])
    raw = h2 @ w["W2"].T + w["B2"]
    return sigmoid(np.clip(raw, -3.0, 3.0))


# --------------------------------------------------------------------- #
# 헤더 생성
# --------------------------------------------------------------------- #


def c_array(name: str, arr: np.ndarray, per_line: int = 8, comment: str = "") -> str:
    flat = arr.reshape(-1)
    head = f"static const float {name}[{flat.size}] = {{"
    if comment:
        head += f"   // {comment}"
    lines = [head]
    for i in range(0, flat.size, per_line):
        chunk = ", ".join(f"{v:.8f}f" for v in flat[i : i + per_line])
        lines.append("    " + chunk + ("," if i + per_line < flat.size else ""))
    lines.append("};")
    return "\n".join(lines)


def write_weights_header(path: Path, w: dict, cfg, src: Path) -> None:
    """§8.1 형식. 주석은 학습 설정에서 자동으로 채운다 (§12)."""
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = f"""// 자동 생성. 수정 금지.
// layers:     7-64-64-4
// activation: tanh
// output:     clamp(-3,3) -> sigmoid
// obs_norm:   pred_count/{cfg.obs_pred_count_norm:g}, kin_count/{cfg.obs_kin_count_norm:g}, \
cover_dist/{cfg.obs_cover_norm:g}, see_r={cfg.see_r:g}, max_energy={cfg.max_energy:g}
// generated:  {stamp}, from {src.as_posix()}
//
// 생성: herbivore_rl/export_weights.py (§8.1)
// 사용: RunPolicy(const float Obs[7], float Out[4])  — §9.3
#pragma once

{c_array("W0", w["W0"], comment="(out,in) 순서: W0[j*7 + i]")}

{c_array("B0", w["B0"])}

{c_array("W1", w["W1"], comment="W1[j*64 + i]")}

{c_array("B1", w["B1"])}

{c_array("W2", w["W2"], comment="W2[j*64 + i]")}

{c_array("B2", w["B2"])}
"""
    path.write_text(body, encoding="utf-8")


def write_utility_header(path: Path, params: dict, src: Path) -> None:
    """§9.3 `RunUtilityPolicy` 의 상수. §5.2 튜닝 산출물에서 자동 생성한다.

    §9.7 "두 곳에 따로 적지 않는다" — 이 값을 C++에 손으로 옮기면 비교군이 갈라져
    §0의 동일 조건이 깨진다.
    """
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = "\n".join(
        f"\tstatic constexpr float {k[0].upper() + k[1:]} = {v:.8f}f;"
        for k, v in params.items()
    )
    body = f"""// 자동 생성. 수정 금지.
// §5.1 Utility AI 비교군 계수. §5.2 Optuna 튜닝 산출물에서 뽑았다.
// generated: {stamp}, from {src.as_posix()}
#pragma once

namespace EcoUtilityParams
{{
{lines}
}}
"""
    path.write_text(body, encoding="utf-8")


def write_golden_header(path: Path, obs: np.ndarray, out: np.ndarray, src: Path) -> None:
    """§9.8-1 검증용. C++ 자동화 테스트가 파일 I/O 없이 쓸 수 있게 헤더로 낸다.

    `verify.npz` 는 파이썬 전용이라 언리얼에서 읽을 수 없다. 같은 내용을 배열로 박아 둔다.
    """
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = f"""// 자동 생성. 수정 금지.
// §9.8-1 파리티 검증용 골든 벡터 {len(obs)}쌍.
// 입력:  관측 7개 — {", ".join(OBS_NAMES)}
// 기대:  행동 4개 — {", ".join(ACT_NAMES)}  (clamp(-3,3) -> sigmoid 를 거친 값)
// 허용:  max |C++ - Python| <= 1e-5
// generated: {stamp}, from {src.as_posix()}
#pragma once

static const int kGoldenCount = {len(obs)};

{c_array("kGoldenObs", obs, per_line=7, comment="[n*7 + i]")}

{c_array("kGoldenExpected", out, per_line=4, comment="[n*4 + j]")}
"""
    path.write_text(body, encoding="utf-8")


# --------------------------------------------------------------------- #


def sample_observations(n: int, seed: int = 0) -> np.ndarray:
    """§3.1 관측 공간을 덮는 표본. 경계값(0과 1)을 반드시 포함한다."""
    rng = np.random.default_rng(seed)
    corners = np.array([[0.0] * 7, [1.0] * 7, [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0],
                        [1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]], dtype=np.float32)
    rest = rng.random((n - len(corners), 7)).astype(np.float32)
    return np.concatenate([corners, rest])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="§8.1 가중치 내보내기")
    p.add_argument("--model", default=str(ROOT / "ckpt" / "final.zip"))
    p.add_argument("--out", default=str(EXPORT))
    p.add_argument("--n-verify", type=int, default=N_VERIFY)
    p.add_argument("--config", default=None)
    p.add_argument("--ue-dest", default=str(UE_POLICY_DIR),
                   help="생성된 헤더를 언리얼 모듈에도 복사한다. 빈 문자열이면 생략")
    args = p.parse_args(argv)

    src = Path(args.model)
    if not src.exists():
        raise SystemExit(f"{src} 없음. 먼저 train.py 를 돌려라 (§6.3).")
    cfg = load_config(args.config)
    model = PPO.load(src, device="cpu")
    w = extract(model)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_weights_header(out / "PolicyWeights.h", w, cfg, src)

    obs = sample_observations(args.n_verify)
    ref = sigmoid(model.predict(obs, deterministic=True)[0])   # §7.1과 같은 경로
    mine = forward(obs, w)
    err = float(np.abs(ref - mine).max())

    np.savez(out / "verify.npz", obs=obs, out=ref.astype(np.float32))
    write_golden_header(out / "PolicyGoldenVectors.h", obs, ref.astype(np.float32), src)

    from policies.utility import BEST_PATH, load_best_params

    if BEST_PATH.exists():
        write_utility_header(out / "UtilityParams.h", load_best_params(), BEST_PATH)

    dest = Path(args.ue_dest) if args.ue_dest else None
    if dest is not None and dest.is_dir():
        import shutil

        for name in GENERATED:
            shutil.copyfile(out / name, dest / name)

    print(f"모델: {src}")
    print(f"층: " + ", ".join(f"{k}{tuple(v.shape)}" for k, v in w.items()))
    print(f"생성: {out/'PolicyWeights.h'}")
    print(f"      {out/'PolicyGoldenVectors.h'}  ({len(obs)}쌍)")
    print(f"      {out/'verify.npz'}")
    if dest is not None and dest.is_dir():
        print(f"복사: {dest}  ({', '.join(GENERATED)})")
    elif dest is not None:
        print(f"경고: 언리얼 경로 없음 — {dest}")
    print(f"§8.2 numpy 순전파 vs SB3 predict 최대 오차 = {err:.3e}  "
          f"{'통과' if err <= 1e-5 else '미달'} (기준 1e-5)")
    return 0 if err <= 1e-5 else 1


if __name__ == "__main__":
    sys.exit(main())
