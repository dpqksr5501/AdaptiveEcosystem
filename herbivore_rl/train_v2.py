"""V2 PPO 학습 (계획서 4.7).

    python train_v2.py --steps 20000000 --seed 0 --run-name v2_0_s0 --save-at 10000000
    python train_v2.py --steps 20000000 --seed 0 --gamma 0.998 --run-name g07_g998_s0   # γ 비교(0-7)

v1 train.py 와 다른 점:
- 독립 세계 K 개를 묶은 MultiWorldVecEnv 로 학습한다 (env_v2/vec_env.py). 세계는 주기적으로 바뀐다
- 무작위 초기화가 기본이다. v1 은 Utility 모방에서 시작해 그 근처에 머물렀다 (계획서 T3)
- 롤아웃 배치를 v1 과 같게(32,768) 두려고 세계당 n_steps = 256 / K 로 줄인다
- 행동 차원별 평균·표준편차·log_std, 선형 R², 월드 상태를 기록하고, 실행 명령과 설정을 함께 저장한다

PPO 구조(O-64-64-A, tanh)와 기본 하이퍼파라미터는 v1 의 `train.PPO_KWARGS` / `make_model` 을 그대로 쓴다.
입력 O 는 설정의 관측 수(`env_v2.world.obs_dim`: v2.0·v2.1 7, vigilance 를 켠 v2.2 8), 출력 A 는 행동 수
(`env_v2.world.action_dim`: v2.0 4, speed 를 켠 v2.1 5, v2.2 6)다. 두 크기는 VecEnv 의 관측·행동 공간이 정한다.
`--gamma` 는 할인율 γ 하나만 바꾼다(계획서 4.7 γ 비교). 나머지 튜닝값은 `--ppo-config` 그대로이고, 실제로 쓴
γ 와 그 출처는 메타 JSON 의 `gamma`·`gamma_source` 에 남는다.

시작 분포 (계획서 4.7 초기화): 무작위 초기화의 마지막 층(action_net)은 SB3 기본값 — 직교 초기화 gain 0.01,
편향 0, log_std 0 — 이라 speed 평균 ≈ 0 → sigmoid 0.5 이고, 걷기 확률은 P(|ε| < ln 2) ≈ 51% 다(계획서의
"speed 0, 걷기 약 51%"). 학습 전에 실제 정책으로 이 분포를 재서 출력하고 메타 JSON `init_policy` 에 남긴다.
설정 `train.init_action_bias: {행동 이름: 값}` 이 있으면 무작위 초기화 직후 그 행동의 편향만 바꾼다(`--init` 이면
쓰지 않는다). 없으면 기존과 같다. v2.2(`configs/v2_2.yaml`)는 vigilance −0.84 다: log_std 0 에서
P(경계) = P(N(−0.84, 1) > logit(0.5) = 0) ≈ 20% (계획서 4.7 "vigilance −0.84, 경계 확률 약 20%").

학습 설정만 바꾸는 명령줄 옵션 (10-03 결정, 1-6 학습 실패 대응 비교 `results/v2/s1_6b/PREREG.md`). 세계 설정 파일과
그 config_digest 는 그대로 두고 학습 쪽 값만 덮는다. 둘 다 주지 않으면 기존과 같다.
- `--ent-coef X`: 엔트로피 계수만 덮는다(`--gamma` 와 같은 방식). 메타 JSON `ent_coef`·`ent_coef_source`.
      python train_v2.py --config configs/v2_2.yaml --seed 0 --run-name v2_2a_s0 --ent-coef 3e-3
- `--init-bias 이름=값 ...`: 설정 `train.init_action_bias` 위에 행동별 시작 편향을 덮는다(적지 않은 행동은 설정 값).
  메타 JSON `init_action_bias`(실제로 넣은 값)·`init_action_bias_source`(행동마다 config|cli).
      python train_v2.py --config configs/v2_2.yaml --seed 0 --run-name v2_2b_s0 --init-bias vigilance=0
  두 옵션은 기본 이름(`v2_2_s0_20m` 등)의 체크포인트를 덮지 않도록 `--run-name` 이나 `--out` 과 함께 써야 한다.
  `--init` 과 `--init-bias` 는 함께 쓸 수 없다(옮겨 온 가중치에는 편향을 넣지 않는다).
메타 JSON 에는 설정의 `config_digest`(diagnose_v2.config_digest 와 같은 값)도 남긴다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from stable_baselines3.common.callbacks import BaseCallback

from env_v2.config import load_v2_config
from env_v2.vec_env import MultiWorldVecEnv, sigmoid
from env_v2.world import ACT_NAMES_V1, ACT_SPEED, GAIT_RUN, GAIT_STOP, GAIT_WALK
from train import load_tuned, make_model

ROOT = Path(__file__).resolve().parent
CKPT = ROOT / "ckpt" / "v2"
ACT_NAMES = list(ACT_NAMES_V1)      # v1 행동 4개. 학습하는 세계의 행동 이름은 venv.act_names


def linear_r2(obs: np.ndarray, act: np.ndarray) -> np.ndarray:
    """행동 차원마다 관측의 선형 회귀로 설명되는 분산 비율. 1에 가까우면 '선형 규칙 수준'이다."""
    X = np.c_[obs, np.ones(len(obs))]
    coef, *_ = np.linalg.lstsq(X, act, rcond=None)
    res = act - X @ coef
    var = act.var(0)
    return np.where(var > 0, 1.0 - res.var(0) / np.maximum(var, 1e-12), np.nan)


def gait_of(a_speed: np.ndarray, thresholds) -> np.ndarray:
    """[0,1] speed 행동 → 명령 보행 (0 정지, 1 걷기, 2 뛰기). env_v2/world.py `_gait_step` 1a) 와 같은 식이다."""
    t_walk, t_run = thresholds
    return (np.asarray(a_speed) >= t_walk).astype(np.int8) + (np.asarray(a_speed) >= t_run)


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _side(t):
    """P(자른 표본 sigmoid ≥ t) 를 계산하는 함수 (m, s) → 확률."""
    if t <= 0.0:
        return lambda m, s: 1.0
    if t >= 1.0:
        return lambda m, s: 0.0
    x = math.log(t / (1.0 - t))
    if x <= -3.0:
        return lambda m, s: 1.0
    if x > 3.0:
        return lambda m, s: 0.0
    return lambda m, s: 1.0 - _phi((x - m) / s)


def gait_probs(mu, std, thresholds) -> np.ndarray:
    """speed 차원 가우시안 N(μ, std²) 표본의 명령 보행 확률 [정지, 걷기, 뛰기] (개체마다, (n, 3)).

    학습 롤아웃과 같은 경로다: 표본 → [-3, 3] 자르기 → sigmoid → 문턱. sigmoid 가 단조라 a ≥ t ⇔ raw ≥ logit(t)
    이고, 자르기는 raw 를 [-3, 3] 안으로 옮길 뿐 문턱의 어느 쪽인지는 logit(t) 가 (-3, 3) 안이면 바꾸지 않는다.
    logit(t) 가 그 밖이면 자른 값 ±3 이 그 문턱을 넘는지로 정해진다(그 상태 확률은 0 또는 1).
    """
    ge_walk, ge_run = (_side(t) for t in thresholds)
    out = np.empty((np.size(mu), 3))
    for i, (m, s) in enumerate(zip(np.ravel(mu), np.ravel(std))):
        pw, pr = ge_walk(float(m), float(s)), ge_run(float(m), float(s))
        out[i] = (1.0 - pw, pw - pr, pr)
    return out


def vig_probs(mu, std, threshold: float) -> np.ndarray:
    """vigilance 차원 가우시안 N(μ, std²) 표본이 경계(sigmoid(자른 표본) > threshold)일 확률 (개체마다, (n,)).

    `gait_probs` 와 같은 경로다(표본 → [-3, 3] 자르기 → sigmoid → 문턱). 표본이 연속이라 > 와 ≥ 의 차이는 없다.
    threshold 0.5·std 1 이면 1 − Φ(−μ) — μ = −0.84 에서 약 0.20.
    """
    ge = _side(threshold)
    return np.array([ge(float(m), float(s)) for m, s in zip(np.ravel(mu), np.ravel(std))])


def init_action_bias(cfg, act_names) -> dict[str, float]:
    """설정 `train.init_action_bias` → {행동 이름: 편향}. 없으면 빈 dict(SB3 기본 편향 0 그대로, 기존과 같다).

    모르는 행동 이름(이 세계에 없는 행동, 오타)과 유한한 숫자가 아닌 값은 읽을 때 멈춘다.
    """
    raw = (cfg.v2.get("train") or {}).get("init_action_bias")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SystemExit(f"train.init_action_bias 는 {{행동 이름: 편향}} 이어야 한다. 받은 값: {raw!r}")
    out = {}
    for k, v in raw.items():
        if k not in act_names:
            raise SystemExit(f"train.init_action_bias 의 '{k}' 는 이 설정의 행동 {list(act_names)} 이 아니다")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise SystemExit(f"train.init_action_bias.{k} 는 유한한 숫자여야 한다. 받은 값: {v!r}")
        out[str(k)] = float(v)
    return out


def parse_init_bias(tokens) -> dict[str, float]:
    """`--init-bias 이름=값 ...` → {이름: 값}. 형식(이름=유한한 숫자, 이름 중복 없음)만 본다. 행동 이름이 이 세계에
    있는지는 `resolve_init_bias` 가 본다. 없거나 비면 빈 dict(기존과 같다)."""
    out: dict[str, float] = {}
    for tok in tokens or []:
        name, sep, val = str(tok).partition("=")
        name = name.strip()
        if not sep or not name:
            raise SystemExit(f"--init-bias 는 이름=값 꼴이다 (예: vigilance=0). 받은 값: {tok!r}")
        try:
            v = float(val)
        except ValueError:
            raise SystemExit(f"--init-bias {name} 의 값은 숫자여야 한다. 받은 값: {val!r}") from None
        if not math.isfinite(v):
            raise SystemExit(f"--init-bias {name} 의 값은 유한한 숫자여야 한다. 받은 값: {val!r}")
        if name in out:
            raise SystemExit(f"--init-bias 에 '{name}' 이 두 번 있다")
        out[name] = v
    return out


def resolve_init_bias(cfg, act_names, cli: dict[str, float] | None) -> tuple[dict[str, float], dict[str, str]]:
    """설정 `train.init_action_bias` 위에 명령줄 `--init-bias` 를 덮는다. (넣을 편향, 행동마다 출처 config|cli).

    명령줄의 모르는 행동 이름(이 세계에 없는 행동, 오타)은 멈춘다. `cli` 가 비면 `init_action_bias(cfg, …)` 그대로다.
    """
    bias = init_action_bias(cfg, act_names)
    source = {k: "config" for k in bias}
    for k, v in (cli or {}).items():
        if k not in act_names:
            raise SystemExit(f"--init-bias 의 '{k}' 는 이 설정의 행동 {list(act_names)} 이 아니다")
        bias[k] = float(v)
        source[k] = "cli"
    return bias, source


def resolve_ent_coef(tuned: dict, ent_coef: float | None) -> tuple[dict, float, str]:
    """튜닝값에 `--ent-coef` 를 덮는다. (새 튜닝값, 쓸 ent_coef, 출처). 다른 키는 건드리지 않는다.

    출처는 "cli"(--ent-coef), "ppo_config"(--ppo-config 의 params.ent_coef), "PPO_KWARGS"(튜닝 파일이 없을 때
    v1 기본값) 중 하나다(`resolve_gamma` 와 같은 규칙).
    """
    from train import PPO_KWARGS

    out = dict(tuned)
    if ent_coef is not None:
        e = float(ent_coef)
        if not (math.isfinite(e) and e >= 0.0):
            raise SystemExit(f"--ent-coef {ent_coef} 는 0 이상의 유한한 숫자여야 한다")
        out["ent_coef"] = e
        return out, e, "cli"
    if "ent_coef" in out:
        return out, float(out["ent_coef"]), "ppo_config"
    return out, float(PPO_KWARGS["ent_coef"]), "PPO_KWARGS"


def apply_action_bias(model, act_names, bias: dict[str, float]) -> None:
    """정책 마지막 층(action_net)의 편향 가운데 `bias` 에 적힌 행동만 바꾼다. 가중치·log_std·다른 편향은 그대로다."""
    import torch as th

    names = list(act_names)
    with th.no_grad():
        for k, v in bias.items():
            model.policy.action_net.bias[names.index(k)] = float(v)


def init_policy_report(model, venv) -> dict:
    """학습 전 정책의 시작 분포 (계획서 4.7 초기화 확인). 마지막 층 편향·log_std, 그리고 speed 가 있으면 지금
    세계들의 관측에서 잰 평균 μ 와 명령 보행 확률(가우시안 표본 → 자르기 → sigmoid → 문턱)을, vigilance 가 있으면
    같은 방식의 경계 확률을 낸다.

    관측은 `World.observe()` 로만 읽는다 — 세계를 바꾸지 않고 난수를 쓰지 않아 학습 결과에 영향이 없다.
    """
    import torch as th

    names = list(venv.act_names)
    pol = model.policy
    rep = {"act_names": names,
           "action_bias": pol.action_net.bias.detach().cpu().numpy().astype(float).tolist(),
           "log_std": pol.log_std.detach().cpu().numpy().astype(float).tolist()}
    if "speed" in names or "vigilance" in names:
        obs = np.concatenate([w.observe() for w in venv.worlds])
        with th.no_grad():
            d = pol.get_distribution(pol.obs_to_tensor(obs)[0]).distribution
            mu_all = d.mean.cpu().numpy().astype(np.float64)
            std_all = d.stddev.cpu().numpy().astype(np.float64)
    if "speed" in names:
        mu, std = mu_all[:, ACT_SPEED], std_all[:, ACT_SPEED]
        p = gait_probs(mu, std, venv.worlds[0]._sp["thresholds"]).mean(0)
        rep["speed"] = {"mu_mean": float(mu.mean()), "mu_absmax": float(np.abs(mu).max()),
                        "std": float(std.mean()), "gait_prob": dict(zip(("stop", "walk", "run"), p.tolist()))}
    if "vigilance" in names:
        i = names.index("vigilance")
        mu, std = mu_all[:, i], std_all[:, i]
        p = float(vig_probs(mu, std, venv.worlds[0]._vg["threshold"]).mean())
        # mu_spread: 개체끼리 μ 가 편향에서 얼마나 벌어졌나(action_net 가중치 gain 0.01 이라 작다)
        rep["vigilance"] = {"mu_mean": float(mu.mean()), "mu_spread": float(np.abs(mu - mu.mean()).max()),
                            "std": float(std.mean()), "vig_prob": p}
    return rep


class BehaviorLogCallbackV2(BaseCallback):
    """롤아웃마다 행동 분포·정책 분산·월드 상태를, `r2_every` 스텝마다 선형 R² 를 기록한다.

    행동 이름은 학습 VecEnv 의 `act_names` 다(speed 를 켜면 5개, vigilance 까지 6개). speed 가 있으면 롤아웃
    표본(학습 분포)의 명령 보행 비율(gait/stop·walk·run)을, vigilance 가 있으면 경계 비율(vig/frac, 4.7 탐색 붕괴
    감시 '5M 시점 경계 비율 1% 미만')을 남긴다. 둘 다 행동 문턱으로만 센 값이다(gait 는 명령 보행이라 경계가 speed
    보다 우선인 것을 반영하지 않는다).
    """

    def __init__(self, r2_every: int = 1_000_000, save_at: list[int] | None = None,
                 save_prefix: Path | None = None):
        super().__init__()
        self.r2_every = r2_every
        self._next_r2 = r2_every
        self.save_at = sorted(save_at or [])
        self.save_prefix = save_prefix
        self.r2_history: list[dict] = []

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        buf = self.model.rollout_buffer
        names = list(self.training_env.act_names)
        raw = buf.actions.reshape(-1, len(names))
        a = sigmoid(np.clip(raw, -3.0, 3.0))
        for i, name in enumerate(names):
            self.logger.record(f"act/{name}_mean", float(a[:, i].mean()))
            self.logger.record(f"act/{name}_std", float(a[:, i].std()))
        log_std = self.model.policy.log_std.detach().cpu().numpy()
        for i, name in enumerate(names):
            self.logger.record(f"policy/{name}_log_std", float(log_std[i]))
        if "speed" in names:
            g = np.bincount(gait_of(a[:, ACT_SPEED], self.training_env.worlds[0]._sp["thresholds"]),
                            minlength=3) / max(len(a), 1)
            for k, name in ((GAIT_STOP, "stop"), (GAIT_WALK, "walk"), (GAIT_RUN, "run")):
                self.logger.record(f"gait/{name}", float(g[k]))
        if "vigilance" in names:
            th = self.training_env.worlds[0]._vg["threshold"]
            self.logger.record("vig/frac", float((a[:, names.index("vigilance")] > th).mean()))
        self.logger.record("rollout/reward_per_step", float(buf.rewards.mean()))

        env = self.training_env
        worlds = env.worlds
        self.logger.record("world/mean_energy", float(np.mean([w.energy.mean() for w in worlds])))
        self.logger.record("world/in_cover_frac", float(np.mean([w._g["in_cover"].mean() for w in worlds])))
        self.logger.record("world/kill_ema", float(np.mean([w.pred_ema for w in worlds])))
        self.logger.record("world/resets", float(env.num_resets))

        if self.num_timesteps >= self._next_r2:
            # 버퍼의 행동은 정책 분포에서 뽑은 값이라 잡음이 섞여 R² 가 낮게 나온다. 정책 평균(결정적
            # 행동)으로 잰다 — 진단 도구(diagnose_v2.py)와 같은 기준이다.
            obs = buf.observations.reshape(-1, self.training_env.obs_dim)
            det, _ = self.model.predict(obs, deterministic=True)
            r2 = linear_r2(obs.astype(np.float64), sigmoid(np.clip(det, -3.0, 3.0)))
            row = {"timesteps": int(self.num_timesteps)}
            for i, name in enumerate(names):
                self.logger.record(f"r2/{name}", float(r2[i]))
                row[name] = float(r2[i])
            self.r2_history.append(row)
            self._next_r2 += self.r2_every

        while self.save_at and self.num_timesteps >= self.save_at[0]:
            at = self.save_at.pop(0)
            if self.save_prefix is not None:
                path = self.save_prefix.with_name(f"{self.save_prefix.stem}_{at / 1e6:g}m.zip")
                self.model.save(path)
                print(f"  중간 저장 {at:,} → {path.name} (실제 {self.num_timesteps:,})", flush=True)


def gamma_tag(gamma: float) -> str:
    """γ → 이름 조각. 0.998 → g998, 0.995 → g995, 0.9916661555611042 → g991666 (유효숫자 6자리)."""
    return "g" + format(float(gamma), ".6g").replace("0.", "", 1).replace(".", "p")


def default_run_name(cfg, seed: int, steps: int, gamma: float | None = None) -> str:
    """--run-name 이 없을 때의 실행 이름. 설정 version 을 넣어 버전마다 체크포인트·TensorBoard 이름이 갈린다
    (v2.0 → v2_0_s0_20m 그대로, v2.0b → v2_0b_s0_20m). version 은 선택 키라 없으면 2.0 으로 본다.
    `--gamma` 를 주면 그 값이 튜닝값과 같아도 γ 조각을 넣는다(v2_0_g998_s0_20m) — γ 를 바꾼 실행이 기본
    이름의 체크포인트를 덮지 않는다."""
    ver = str(cfg.v2.get("version") or "2.0").replace(".", "_")
    g = f"_{gamma_tag(gamma)}" if gamma is not None else ""
    return f"v{ver}{g}_s{seed}_{steps // 1_000_000}m"


def resolve_gamma(tuned: dict, gamma: float | None) -> tuple[dict, float, str]:
    """튜닝값에 `--gamma` 를 덮는다. (새 튜닝값, 쓸 γ, 출처). 다른 키는 건드리지 않는다.

    출처는 "cli"(--gamma), "ppo_config"(--ppo-config 의 params.gamma), "PPO_KWARGS"(튜닝 파일이 없을 때
    v1 기본값) 중 하나다.
    """
    from train import PPO_KWARGS

    out = dict(tuned)
    if gamma is not None:
        g = float(gamma)
        if not 0.0 < g < 1.0:
            raise SystemExit(f"--gamma {gamma} 는 0 과 1 사이여야 한다")
        out["gamma"] = g
        return out, g, "cli"
    if "gamma" in out:
        return out, float(out["gamma"]), "ppo_config"
    return out, float(PPO_KWARGS["gamma"]), "PPO_KWARGS"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="V2 PPO 학습 (다중 세계)")
    p.add_argument("--steps", type=int, default=20_000_000)
    p.add_argument("--seed", type=int, default=0, help="PPO 시드이자 세계 선택 시드(meta_seed)")
    p.add_argument("--run-name", default=None, help="기본 v<설정 version>_s<seed>_<M>m (예: v2_0b_s0_20m)")
    p.add_argument("--out", default=None, help="기본 ckpt/v2/<run-name>.zip")
    p.add_argument("--config", default=None, help="기본 configs/v2.yaml")
    p.add_argument("--ppo-config", default=str(ROOT / "configs" / "ppo_best.yaml"))
    p.add_argument("--gamma", type=float, default=None,
                   help="할인율 γ 만 덮는다(0-7 γ 비교). 기본은 --ppo-config 의 params.gamma. "
                        "다른 하이퍼파라미터는 그대로다")
    p.add_argument("--ent-coef", type=float, default=None,
                   help="엔트로피 계수만 덮는다(1-6 학습 실패 대응 비교). 기본은 --ppo-config 의 params.ent_coef. "
                        "다른 하이퍼파라미터는 그대로다. --run-name 이나 --out 과 함께 쓴다")
    p.add_argument("--init-bias", nargs="+", default=None, metavar="이름=값",
                   help="마지막 층 시작 편향을 행동별로 덮는다(예: vigilance=0). 적지 않은 행동은 설정 "
                        "train.init_action_bias 그대로. --run-name 이나 --out 과 함께 쓰고, --init 과는 못 쓴다")
    p.add_argument("--init", default=None, help="가중치를 옮겨 올 체크포인트. 기본은 무작위 초기화")
    p.add_argument("--num-worlds", type=int, default=None)
    p.add_argument("--reset-interval", type=int, default=None)
    p.add_argument("--save-at", type=int, nargs="*", default=[], help="중간 저장 시점(timestep)")
    p.add_argument("--threads", type=int, default=4, help="torch 스레드 수 (병렬 실행 시 줄인다)")
    p.add_argument("--tb", default=str(ROOT / "runs" / "v2"))
    args = p.parse_args(argv)
    cli_bias = parse_init_bias(args.init_bias)
    if (args.ent_coef is not None or cli_bias) and not (args.run_name or args.out):
        raise SystemExit("--ent-coef·--init-bias 는 --run-name 이나 --out 과 함께 쓴다 (기본 이름의 체크포인트를 덮지 않게)")
    if cli_bias and args.init:
        raise SystemExit("--init-bias 는 --init 과 함께 쓸 수 없다 (옮겨 온 가중치에는 편향을 넣지 않는다)")

    torch.set_num_threads(args.threads)
    cfg = load_v2_config(args.config)
    from diagnose_v2 import config_digest       # 진단 결과 meta 와 같은 식(설정 dict 의 sha1 앞 12자리)
    digest = config_digest(cfg)
    venv = MultiWorldVecEnv(cfg, num_worlds=args.num_worlds, reset_interval=args.reset_interval,
                            meta_seed=args.seed)
    rollout_world_steps = int(cfg.v2["train"].get("rollout_world_steps", 256))
    n_steps = max(1, rollout_world_steps // venv.K)

    tuned, gamma, gamma_source = resolve_gamma(load_tuned(args.ppo_config), args.gamma)
    if gamma_source == "cli":
        print(f"γ = {gamma} (--gamma, 다른 튜닝값은 그대로)")
    tuned, ent_coef, ent_coef_source = resolve_ent_coef(tuned, args.ent_coef)
    if ent_coef_source == "cli":
        print(f"ent_coef = {ent_coef} (--ent-coef, 다른 튜닝값은 그대로)")
    run = args.run_name or default_run_name(cfg, args.seed, args.steps, args.gamma)
    out = Path(args.out) if args.out else CKPT / f"{run}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    model = make_model(venv, tensorboard_log=args.tb, n_steps=n_steps, seed=args.seed, **tuned)
    # γ 는 GAE·truncation 부트스트랩이 쓰는 롤아웃 버퍼에도 들어가야 한다 (SB3 _setup_model)
    if float(model.gamma) != gamma or float(model.rollout_buffer.gamma) != gamma:
        raise RuntimeError(f"모델 γ {model.gamma} (버퍼 {model.rollout_buffer.gamma}) 가 지정한 γ {gamma} 와 다르다")
    if float(model.ent_coef) != ent_coef:
        raise RuntimeError(f"모델 ent_coef {model.ent_coef} 가 지정한 값 {ent_coef} 와 다르다")
    if args.init:
        from stable_baselines3 import PPO
        donor = PPO.load(args.init, device="cpu")
        model.policy.load_state_dict(donor.policy.state_dict())
        print(f"가중치 이식: {args.init}")
    else:
        print("무작위 초기화로 시작 (계획서 4.7)")
    bias, bias_source = resolve_init_bias(cfg, venv.act_names, cli_bias)
    if bias and not args.init:
        apply_action_bias(model, venv.act_names, bias)
        print("마지막 층 편향 (train.init_action_bias" + (" + --init-bias" if cli_bias else "") + "): "
              + ", ".join(f"{k} {v:+g} ({bias_source[k]})" for k, v in bias.items()))
    elif bias:
        print(f"train.init_action_bias {bias} 는 --init 이라 쓰지 않는다 (옮겨 온 가중치 그대로)")
    init_rep = init_policy_report(model, venv)
    if "speed" in init_rep:
        sp, i = init_rep["speed"], ACT_SPEED
        gp = sp["gait_prob"]
        print(f"시작 분포 speed: 편향 {init_rep['action_bias'][i]:+.4f}, log_std {init_rep['log_std'][i]:+.3f}, "
              f"평균 μ {sp['mu_mean']:+.4f} → 정지 {gp['stop']:.3f} · 걷기 {gp['walk']:.3f} · 뛰기 {gp['run']:.3f} "
              "(계획서 4.7: 편향 0, 걷기 약 51%)", flush=True)
    if "vigilance" in init_rep:
        vp, i = init_rep["vigilance"], venv.act_names.index("vigilance")
        ref = ("--init-bias 로 덮음" if bias_source.get("vigilance") == "cli"
               else "계획서 4.7: 편향 −0.84, 경계 약 20%")
        print(f"시작 분포 vigilance: 편향 {init_rep['action_bias'][i]:+.4f}, log_std {init_rep['log_std'][i]:+.3f}, "
              f"평균 μ {vp['mu_mean']:+.4f} → 경계 {vp['vig_prob']:.3f} ({ref})", flush=True)

    print(f"{args.steps:,} 스텝 — 세계 {venv.K}개 × {venv.N}슬롯 = num_envs {venv.num_envs}, "
          f"세계당 n_steps {n_steps} (배치 {n_steps * venv.num_envs:,}), 리셋 {venv.T}스텝마다, "
          f"관측 {venv.obs_dim}개, 행동 {venv.act_dim}개 {list(venv.act_names)}", flush=True)
    cb = BehaviorLogCallbackV2(save_at=args.save_at, save_prefix=out)
    t0 = time.time()
    model.learn(total_timesteps=args.steps, callback=cb, tb_log_name=run,
                reset_num_timesteps=True, progress_bar=False)
    elapsed = time.time() - t0
    model.save(out)
    print(f"저장: {out}  ({elapsed / 60:.1f}분)")

    meta = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # main(argv) 로 부르면(테스트) sys.argv 가 아니라 받은 인자를 적는다
        "command": " ".join([Path(sys.executable).name, Path(__file__).name]
                            + (sys.argv[1:] if argv is None else [str(a) for a in argv])),
        "python": platform.python_version(),
        "steps": args.steps,
        "actual_timesteps": int(model.num_timesteps),
        "seed": args.seed,
        "elapsed_min": round(elapsed / 60, 2),
        # 실제 학습 γ(모델에 들어간 값). 출처: cli(--gamma) / ppo_config / PPO_KWARGS
        "gamma": float(model.gamma),
        "gamma_source": gamma_source,
        # 실제 엔트로피 계수(모델에 들어간 값). 출처: cli(--ent-coef) / ppo_config / PPO_KWARGS
        "ent_coef": float(model.ent_coef),
        "ent_coef_source": ent_coef_source,
        # 설정 전체(v1 기본 + v2 파일)의 지문. diagnose_v2 결과 meta 의 config_digest 와 같은 값이다
        "config_digest": digest,
        "ppo_config": args.ppo_config,
        "ppo": {k: (float(v) if isinstance(v, (int, float)) else str(v)) for k, v in {
            "n_steps": n_steps, "batch_size": model.batch_size, "n_epochs": model.n_epochs,
            "gamma": model.gamma, "gae_lambda": model.gae_lambda, "ent_coef": model.ent_coef,
            "learning_rate": tuned.get("learning_rate", "default"), "clip_range": tuned.get("clip_range", "default"),
        }.items()},
        "v2": cfg.v2,
        "num_worlds": venv.K, "reset_interval": venv.T,
        "worlds_seen": sum(len(h) for h in venv.seed_history),
        "world_resets": venv.num_resets,
        "r2_history": cb.r2_history,
        "init": args.init,
        # 학습 전 정책의 시작 분포(마지막 층 편향·log_std, speed 명령 보행 확률). 계획서 4.7 초기화 확인용
        "act_names": list(venv.act_names),
        "obs_names": list(venv.obs_names),
        # train.init_action_bias(+ --init-bias)로 바꾼 편향(--init 이면 쓰지 않아 빈 dict)과 행동마다 출처 config|cli
        "init_action_bias": bias if not args.init else {},
        "init_action_bias_source": bias_source if not args.init else {},
        "init_policy": init_rep,
    }
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"config_digest {meta['config_digest']}, ent_coef {meta['ent_coef']} ({ent_coef_source})")
    print(f"학습한 세계 수: {meta['worlds_seen']} (시간 초과 리셋 {venv.num_resets}회)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
