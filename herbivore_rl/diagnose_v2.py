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
    python diagnose_v2.py ablate --model ckpt/final.zip --g998                # γ=0.998 보고 평가 (6.1-4)
    python diagnose_v2.py ablate --model ckpt/final.zip --act-mode stochastic # 확률 모드 (6.1-7)
    python diagnose_v2.py ablate --model ckpt/final.zip --act-mode hold --hold-k 24   # 유지 표본 모드 (R1)
    python diagnose_v2.py gammasel --dirs <γ 후보별 --g998 ablate 디렉터리들>   # 4.7 γ 선택 규칙
    python diagnose_v2.py modecmp --det <결정 모드 디렉터리들> --stoch <확률 모드 디렉터리들>  # #29
    python diagnose_v2.py modecmp --det <결정 모드 디렉터리들> --hold <유지 표본 모드 디렉터리들>  # R1

정책은 `--model`(학습 zip) 또는 `--policy utility|fixed|random` 으로 준다. 산출물은
`results/v2/diag_<이름>/` 아래 JSON + MD 다(`--out` 으로 디렉터리를 직접 정할 수 있다). 이름은 `--name`, 없으면
모델 파일 이름이고, 설정 version 이 2.0 이 아니면 `_v<version>` 을 붙인다(`final` + configs/v2_0b.yaml →
`diag_final_v2_0b`). 같은 모델을 다른 설정으로 진단해도 v2.0 결과 디렉터리를 덮지 않는다. 기본 이름에는
`--g998` 이면 `_g998`, 확률 모드면 `_stoch`, 유지 표본 모드면 `_hold<K>` 도 붙는다.

판정 규칙 (6.1):
- 판정 양은 G_γ(PPO 가 최대화하는 할인 리턴-투-고 평균)와 결과·행동 지표다. mean_return 은 보고만 한다.
- 평가 시드 10000~10019 × 5000스텝, deterministic, 시드를 짝지은 t검정 (자유도 19, |t|>2.093).
- 학습 시드가 여럿이면 IQM 과 층화 부트스트랩 95% CI 를 함께 낸다 (`report --dirs`).
- 평균 행동(C1)·평균 관측(C4)은 학습 시드 0~19 × 3000스텝에서 잰다. 평가 시드를 엿보지 않는다.
- γ = 0.998 로 보고하는 평가는 10000스텝이고 G_γ 평균에서 앞 500스텝(리셋 과도기)을 뺀다 (6.1-4). `--g998` 이
  γ·스텝·앞 제외를 한 번에 정한다. 앞 제외만 따로 쓰려면 `--head` (기본 0 = 예전과 같은 출력).
- 행동 모드 (6.1-7): 기본은 결정 모드(평균 행동, 언리얼 배포와 같음)다. `--act-mode stochastic` 은 학습 분포
  (평균 + exp(log_std) 잡음 → [-3,3] 자르기 → sigmoid)에서 뽑는다. 잡음은 평가 시드에서 유도한 전용 스트림이라
  재현된다(env_v2/rollout.py StochasticLearned). 사전 등록 판정은 결정 모드로 한다.
  `--act-mode hold --hold-k K` 는 유지 표본 모드다(수정 제안서 3.1 (가) R1 출시 모드): 조향 4열은 평균, 보행·경계 열만
  개체별 잡음을 K 스텝 유지해 뽑는다(env_v2/rollout.py HoldLearned, 해시·위상 표본기). 캐시·이름·meta 에 K 가 들어간다.
- 행동 수는 설정을 따른다(`env_v2.world.action_names`: v2.0 4개, speed 를 켠 v2.1 은 5개 — idx 4 = speed).
  C1·C3-k·C1′·C2·C2-seg·`--action`·`--const-action`·`--base-action` 의 길이가 모두 그 수다. 예:
      python diagnose_v2.py constsearch --config configs/v2_1.yaml --policy fixed --action 0.4 0.8 0.4 0.1 0.5 \
          --seg-bins 2:0.5 4:0.5 --seg-dims speed --base-action 0.4 0.8 0.4 0.1 0.5     # Gate E1 꼴 C2-seg
  Utility 는 v1 행동 4개만 내므로 speed 세계에서는 참고 행에서 뺀다(Utility v2 는 아직 없다, 계획서 4.8).
  speed 세계의 결과에는 보행 지표(`World.gait_stats`: 보행 비율, energy<0.5 비율, B1·B2·B8)가 함께 남는다.
- 관측 수도 설정을 따른다(`env_v2.world.obs_names`: v2.0·v2.1 7개, vigilance 를 켠 v2.2 는 8개 — idx 7 =
  threat_recency). v2.2 의 행동은 6개(idx 5 = vigilance)다. C4(`permute --obs threat_recency`), `--seg-bins`
  (`threat_recency:0.5` 처럼 이름도 된다), 반응 곡선·R² 가 관측 8개를 다룬다. vigilance 세계의 결과에는 경계 지표
  (`World.vigil_stats`: 경계 비율, 구간별 P(경계), B3·B4·B5·B5′, b8_vig, 360° 시야의 동족·포식자 수)가 함께 남는다.
  경계 지속(다음 관측 360°)이 시야를 합친 B3·B4·B5′ 를 정책과 무관하게 치우치게 하므로, 결정 관측이 기본 FOV 인
  개체만 센 `*_narrow` 와 시야와 무관한 기준 구간 `*_truth` 를 함께 낸다(정의와 주의는 `World.vigil_stats`).
      python diagnose_v2.py ablate --config configs/v2_2.yaml --model ckpt/v2/v2_2_s0.zip
      python diagnose_v2.py permute --config configs/v2_2.yaml --model ckpt/v2/v2_2_s0.zip --obs threat_recency
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
    ACTION_MODES,
    ROW_COLUMNS,
    build_policy,
    hold_k_of,
    load_gamma,
    make_executor,
    model_gamma,
    n_segments,
    public_row,
    run_specs,
    tail_steps,
)
from env_v2.rollout import GAIT_COLUMNS, VIGIL_COLUMNS, adapt_spec
from env_v2.world import (ACT_DIM, ACT_NAMES_V1, OBS_NAMES_V1, OBS_RECENT_PREDATION, action_names,
                          obs_names as world_obs_names)
from evaluate import T_CRIT, welch_paired

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "v2"
# 관측 표본 캐시(수 MB). results/ 는 커밋 대상이라 .gitignore 가 무시하는 runs/ 아래에 둔다.
CACHE = ROOT / "runs" / "v2_diag"

ACT_NAMES = list(ACT_NAMES_V1)   # v1 행동 4개. 진단하는 세계의 행동 이름은 Ctx.act_names (결과 meta "act_names")
# v1 관측 7개 (env_v2.world.OBS_NAMES_V1 과 같다). 진단하는 세계의 관측 이름은 Ctx.obs_names (결과 meta "obs_names")
OBS_NAMES = list(OBS_NAMES_V1)

# 보정(평균 행동·평균 관측·표본) 조건. smart_check.py 와 같다.
CALIB_SEEDS = range(0, 20)
CALIB_STEPS = 3000
RECORD_EVERY = 30
# C2 탐색 조건 (계획서 2.1 의 Optuna 112회와 같다).
SEARCH_SEEDS = range(0, 8)
SEARCH_STEPS = 3000
RESCORE_SEEDS = range(100, 120)      # C2 상수 탐색의 재채점에만 쓴다
RESCORE_STEPS = 3000
# 탐색 층 판정 시드 (10-03 R6). 학습 시드 풀 0~999 와 평가 시드 10000~10019 밖이다. 출시 모드 선택(R1)과 탐색 배치의
# 팔 비교가 이 시드로 한다. RESCORE_SEEDS(100~119)는 상수 탐색 전용으로 그대로 둔다.
EXPLORE_SEEDS = range(12000, 12040)
TRIALS = 112
BATCH = 7
TOP_K = 5
# v1 환경에서 학습 전에 찾았던 최고 상수. smart_check.py 가 탐색 시작점으로 넣었다.
V1_PRETRAIN_BEST = [0.39, 0.99, 0.92, 0.15]
# v1 에 없는 행동의 탐색 시작값. speed 0.5 = 걷기 구간(1/3~2/3) 가운데 — 걷기 대사가 v1 대사와 같다(계획서 4.4).
# vigilance 0.25 = 경계 아님 구간(0~0.5) 가운데 — 상수 경계(모두 늘 경계)는 섭식 0 이라 굶는다.
PRETRAIN_EXTRA = {"speed": 0.5, "vigilance": 0.25}
# 평가 길이 기본값 (6.1-4)
EVAL_STEPS = 5000
# γ = 0.998 보고 평가 (6.1-4, #27). `--g998` 이 이 세 값을 한 번에 정한다. 꼬리는 ceil(5/(1-0.998)) = 2500.
G998 = {"gamma": 0.998, "eval_steps": 10000, "head": 500}

# 결과 지표(+G_γ). 짝지은 t검정을 붙인다.
OUTCOME = ["mean_return", "g_gamma", "survival", "repro", "predation_rate", "starve_rate"]
# 행동 지표. 우열이 아니라 기술이다.
BEHAVIOR = ["cohesion_mean", "flee_dist_mean", "flee_dist_std", "cover_frac", "react_pred",
            "react_hunger", "starve_share"]
# 보행 지표(speed 를 켠 세계만, World.gait_stats). 우열이 아니라 기술이다. 표에는 이 열만 낸다(나머지는 JSON).
GAIT_SHOW = ["walk_frac", "stop_frac", "run_frac", "stall_frac", "hungry_frac", "b1", "b2", "b8"]
# 경계 지표(vigilance 를 켠 세계만, World.vigil_stats). 우열이 아니라 기술이다. 표에는 이 열만 낸다(나머지는 JSON).
# 시야를 합친 b3·b4·b5p_pred 는 경계 지속(360°) 때문에 치우친다 — 옆에 *_narrow·*_truth 를 둔다(World.vigil_stats).
VIGIL_SHOW = ["vig_frac", "p_vig_seen", "p_vig_recent", "p_vig_calm", "b3", "b3_narrow", "b3_truth", "b4", "b4_narrow",
              "b5", "b5p_pred", "b5p_pred_narrow", "b5p_truth", "b5p_ema", "b8_vig", "obs_wide_frac"]
COL_LABEL = {
    "mean_return": "리턴", "g_gamma": "G_γ", "survival": "수명", "repro": "번식",
    "predation_rate": "피식률", "starve_rate": "아사율", "starve_share": "아사 비중",
    "walk_frac": "걷기", "stop_frac": "정지", "run_frac": "뛰기", "stall_frac": "방향 없음 정지",
    "hungry_frac": "energy<0.5", "b1": "B1", "b2": "B2", "b8": "B8 (/초)",
    "vig_frac": "경계", "p_vig_seen": "P(경계|보임)", "p_vig_recent": "P(경계|최근 위협)", "p_vig_calm": "P(경계|평시)",
    "b3": "B3 (시야 합침)", "b3_narrow": "B3 (120° 결정)", "b3_truth": "B3 (반경 기준)",
    "b4": "B4 (시야 합침)", "b4_narrow": "B4 (120° 결정)", "b5": "B5 (관측적)",
    "b5p_pred": "B5′ 포식자 (관측, 360° 포함)", "b5p_pred_narrow": "B5′ 포식자 (120° 결정)",
    "b5p_truth": "B5′ 포식자 (반경 기준)", "b5p_ema": "B5′ 피식 EMA",
    "b8_vig": "경계 전환 (/초)", "obs_wide_frac": "360° 관측",
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
        # v2.2 (관측 8개): 결정 때 구간 (World.vigil_stats 와 같은 문턱 0.5)
        **({"최근 위협·안 보임 (threat>0.5, dist=1)": (o[:, 7] > 0.5) & (o[:, 2] >= 1.0),
            "위협 없음 (threat≤0.5)": o[:, 7] <= 0.5} if o.shape[1] > 7 else {}),
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


def check_names(names, n: int) -> list[str]:
    """행동 이름 목록. 주지 않으면 v1 4개이고, 그때 길이가 4 가 아니면 멈춘다(이름을 지어내지 않는다)."""
    names = list(ACT_NAMES if names is None else names)
    if len(names) != n:
        raise ValueError(f"행동 {n}개인데 이름이 {len(names)}개다: {names}")
    return names


def control_specs(base: dict, mean_action, names=None) -> dict[str, dict]:
    """C0, C1, C3-k, C1′. C1 은 학습 정책을 부르지 않는 상수 정책이다 (smart_check frozen_all 과 같다).

    C3-k 는 행동마다 하나다(speed 세계는 C3-speed 까지 5개). `names` 를 주지 않으면 v1 4개다."""
    mean = [float(x) for x in mean_action]
    specs = {"C0": base, "C1": {"kind": "fixed", "action": mean}}
    for k, name in enumerate(check_names(names, len(mean))):
        specs[f"C3-{name}"] = wrap(base, {"kind": "act_fix", "dims": [k], "values": mean})
    specs["C1'"] = wrap(base, {"kind": "act_permute", "salt": 0})
    return specs


def obs_control_specs(base: dict, obs_mean, dims, modes, names=None) -> tuple[dict[str, dict], list[str]]:
    """C4-j. fix 는 학습 시드 평균 관측으로 고정, perm 은 같은 스텝 개체끼리 섞는다.

    `names` 는 세계의 관측 이름(없으면 v1 7개). v2.2 의 threat_recency(7)는 개체별 값이라 순열도 의미가 있다."""
    names = list(OBS_NAMES if names is None else names)
    specs, notes = {}, []
    for j in dims:
        if "fix" in modes:
            specs[f"C4-{names[j]}-fix"] = wrap(
                base, {"kind": "obs_fix", "dims": [j], "values": [float(obs_mean[j])]})
        if "perm" in modes:
            if j == OBS_RECENT_PREDATION:
                notes.append(f"C4-{names[j]}-perm 생략: 관측 {j} 는 모든 개체가 같은 전역 값이라 "
                             "개체끼리 섞어도 바뀌지 않는다. 고정(fix)만 의미가 있다.")
                continue
            specs[f"C4-{names[j]}-perm"] = wrap(base, {"kind": "obs_permute", "dims": [j], "salt": 0})
    return specs, notes


def seg_spec(base_action, bins, dims, table) -> dict:
    """C2-seg: 바탕은 C2 상수, 구간마다 `dims` 만 따로 상수."""
    return wrap({"kind": "fixed", "action": [float(x) for x in base_action]},
                {"kind": "seg_const", "bins": bins, "dims": list(dims),
                 "table": [float(x) for x in np.ravel(table)]})


def seg_labels(bins, names=None) -> list[str]:
    """구간 id 순서(segment_ids 의 혼합 기수, 앞 열이 큰 자리)대로 사람이 읽는 이름. `names` 는 관측 이름."""
    names = list(OBS_NAMES if names is None else names)
    labels = [""]
    for j, thr in bins:
        name = names[int(j)]
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


def parse_bins(tokens, names=None) -> list[list]:
    """"2:0.5" 또는 "pred_dist:0.25,0.5" → [[2, [0.5]], ...]. `names` 는 세계의 관측 이름(없으면 v1 7개)."""
    names = list(OBS_NAMES if names is None else names)
    out = []
    for tok in tokens or []:
        j, _, ts = tok.partition(":")
        j = names.index(j) if j in names else int(j)
        if not 0 <= j < len(names):
            raise SystemExit(f"--seg-bins {tok!r}: 관측 {j} 는 이 설정의 관측 {names} 밖이다")
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
    obs = (np.concatenate([r["_obs"] for r in rows]) if "_obs" in rows[0]
           else np.empty((0, len(rows[0]["_obs_sum"]))))
    act = np.concatenate([r["_act"] for r in rows]) if "_act" in rows[0] else np.empty((0, len(mean)))
    return {"mean_action": mean, "std_action": std, "obs_mean": obs_mean, "obs": obs, "act": act,
            "n": int(n)}


def calib_summary(cal: dict, names=None, obs_names=None) -> dict:
    obs = cal["obs"]
    names = check_names(names, len(np.ravel(cal["mean_action"])))
    obs_names = list(OBS_NAMES if obs_names is None else obs_names)
    if len(obs_names) != len(np.ravel(cal["obs_mean"])):
        raise ValueError(f"관측 {len(np.ravel(cal['obs_mean']))}개인데 이름이 {len(obs_names)}개다: {obs_names}")
    return {
        "seeds": cal.get("seeds"), "steps": cal.get("steps"), "record_every": cal.get("record_every"),
        "mean_action": dict(zip(names, np.asarray(cal["mean_action"]).tolist())),
        "std_action": dict(zip(names, np.asarray(cal["std_action"]).tolist())),
        "obs_mean": dict(zip(obs_names, np.asarray(cal["obs_mean"]).tolist())),
        "obs_quantiles_5_50_95": {obs_names[j]: np.quantile(obs[:, j], [0.05, 0.5, 0.95]).tolist()
                                  for j in range(len(obs_names))} if len(obs) else None,
        "samples": int(len(obs)),
    }


# --------------------------------------------------------------------- #
# 실행 문맥
# --------------------------------------------------------------------- #


class Ctx:
    """명령 하나의 설정과 워커 풀."""

    def __init__(self, args):
        self.args = args
        apply_g998(args)
        self.act_mode = getattr(args, "act_mode", None) or "deterministic"
        self.hold_k = hold_k_arg(args)          # 유지 표본 모드의 K (다른 모드는 None)
        self.cfg = load_v2_config(args.config)
        # 이 설정의 세계가 받는 행동 (v2.0 4개, speed 를 켠 v2.1 5개). 대조군·상수의 길이가 이 수다
        self.act_names = list(action_names(self.cfg))
        self.act_dim = len(self.act_names)
        # 이 설정의 세계가 내는 관측 (v2.0·v2.1 7개, vigilance 를 켠 v2.2 8개). C4·구간·반응 곡선의 관측 번호다
        self.obs_names = list(world_obs_names(self.cfg))
        self.obs_dim = len(self.obs_names)
        self.spec = base_spec(args, self.act_names)
        self.name = args.name or default_name(args, self.cfg)
        out = getattr(args, "out", None)
        self.out = Path(out) if out else RESULTS / f"diag_{self.name}"
        # 계획서 6.1: G_γ 의 γ 는 그 정책의 학습 γ 다. 모델이 있으면 모델 γ 를 기본으로 쓴다.
        mg = model_gamma(args.model) if args.model else None
        self.model_gamma = mg
        if args.gamma is not None:
            self.gamma = float(args.gamma)
        elif mg is not None:
            self.gamma = float(mg)
        else:
            self.gamma = load_gamma()
        self.tail = int(args.tail) if args.tail is not None else tail_steps(self.gamma)
        self.head = int(args.head) if getattr(args, "head", None) is not None else 0
        if self.head < 0:
            raise SystemExit(f"--head {self.head} 는 0 이상이어야 한다")
        lo, hi = self.cfg.eval_seeds
        self.eval_seeds = parse_seeds(args.eval_seeds) if args.eval_seeds else list(range(lo, hi))
        self.eval_steps = int(args.eval_steps) if args.eval_steps is not None else EVAL_STEPS
        if (self.eval_steps <= self.head + self.tail
                and getattr(args, "cmd", None) not in ("report", "gammasel", "modecmp")):
            print(f"경고: 평가 {self.eval_steps}스텝이 앞 {self.head} + 꼬리 {self.tail} 이하라 G_γ 가 nan 이 된다.")
        self.calib_seeds = parse_seeds(args.calib_seeds) if args.calib_seeds else list(CALIB_SEEDS)
        self.calib_steps = int(args.calib_steps)
        self.ex = None
        if mg is not None and abs(mg - self.gamma) > 1e-12:
            print(f"경고: 모델 학습 γ={mg} 와 다른 γ={self.gamma} 로 G_γ 를 잰다 (--gamma 또는 --g998).")
        self.model_sha1 = model_fingerprint(args.model) if args.model else None
        check_disjoint("보정 시드", self.calib_seeds, self.eval_seeds, args)

    def need_spec(self) -> dict:
        if self.spec is None:
            raise SystemExit("정책이 없다: --model <zip> 또는 --policy utility|fixed|random")
        return self.spec

    def run(self, specs, seeds, steps, record_every: int = 0):
        return run_specs(self.cfg, specs, seeds, steps, workers=self.args.workers, gamma=self.gamma,
                         tail=self.tail, record_every=record_every, executor=self.ex, head=self.head)

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
            # 0-7 에서 더한 키. 예전 JSON 에는 없다 — 읽을 때 없으면 head 0, 결정 모드로 본다.
            "head": self.head, "act_mode": self.act_mode, "model_gamma": self.model_gamma,
            # 1-1 에서 더한 키. 예전 JSON 에는 없다 — 읽을 때 없으면 v1 행동 4개로 본다(act_names_of).
            "act_names": self.act_names,
            # 1-4 에서 더한 키. 예전 JSON 에는 없다 — 읽을 때 없으면 v1 관측 7개로 본다(obs_names_of).
            "obs_names": self.obs_names,
            # R1(10-03)에서 더한 키. 유지 표본 모드에만 있다 — 없으면 None(결정·확률 모드)으로 본다.
            **({"hold_k": self.hold_k} if self.hold_k is not None else {}),
            **kw,
        }


def apply_g998(args) -> None:
    """`--g998` (6.1-4 γ=0.998 보고 평가): γ 0.998, 10000스텝, 앞 500스텝 제외를 채운다.

    같은 옵션을 다른 값으로 함께 주면 사전 등록 조건이 깨지므로 거부한다. 같은 값은 받는다.
    """
    if not getattr(args, "g998", False):
        return
    for key, want in G998.items():
        got = getattr(args, key, None)
        if got is not None and float(got) != float(want):
            raise SystemExit(f"--g998 은 --{key.replace('_', '-')} {want} 로 고정한다 (받은 값 {got})")
        setattr(args, key, want)
    tail = tail_steps(G998["gamma"])
    if getattr(args, "tail", None) is not None and int(args.tail) != tail:
        raise SystemExit(f"--g998 은 꼬리를 ceil(5/(1-γ)) = {tail} 로 둔다 (받은 값 {args.tail})")


def hold_k_arg(args) -> int | None:
    """`--act-mode hold` 의 `--hold-k`. hold 면 꼭 있어야 하고(양의 정수), 다른 모드에 주면 잘못 쓴 것으로 보고 멈춘다."""
    mode = getattr(args, "act_mode", None) or "deterministic"
    k = getattr(args, "hold_k", None)
    if mode != "hold":
        if k is not None:
            raise SystemExit(f"--hold-k 는 --act-mode hold 에만 쓴다 (받은 모드 {mode})")
        return None
    if k is None:
        raise SystemExit("--act-mode hold 는 --hold-k K(양의 정수, 수정 제안서 R1 은 24)가 필요하다")
    if int(k) < 1:
        raise SystemExit(f"--hold-k 는 양의 정수여야 한다 (받은 값 {k})")
    return int(k)


def mode_tag(mode: str, hold_k: int | None = None) -> str | None:
    """이름·캐시 파일에 붙일 모드 표시. 결정 모드는 None(예전 이름 그대로), 확률 모드 stochastic, 유지 표본 모드 hold<K>."""
    if mode == "deterministic":
        return None
    return f"hold{int(hold_k)}" if mode == "hold" else mode


def base_spec(args, names=None) -> dict | None:
    """명령줄 → 바탕 정책 스펙. `names` 는 세계의 행동 이름(없으면 v1 4개)이고 fixed·random·utility 의 길이를 정한다."""
    names = list(ACT_NAMES if names is None else names)
    mode = getattr(args, "act_mode", None) or "deterministic"
    if mode not in ACTION_MODES:
        raise SystemExit(f"--act-mode {mode!r}: {ACTION_MODES} 중 하나")
    if mode == "stochastic":
        if not args.model:
            raise SystemExit("--act-mode stochastic 은 학습 정책(--model)에만 쓴다 — 상수·Utility 에는 분포가 없다")
        # 결정 모드 스펙은 예전과 같게 둔다(키를 더하지 않는다). 그래야 예전 캐시·결과와 그대로 비교된다.
        return {"kind": "learned", "model": str(Path(args.model).resolve()), "mode": "stochastic"}
    if mode == "hold":
        if not args.model:
            raise SystemExit("--act-mode hold 는 학습 정책(--model)에만 쓴다 — 상수·Utility 에는 분포가 없다")
        spec = {"kind": "learned", "model": str(Path(args.model).resolve()), "mode": "hold",
                "hold_k": hold_k_arg(args)}
        hold_k_of(spec)                       # rollout 과 같은 검사
        return spec
    if args.model:
        return {"kind": "learned", "model": str(Path(args.model).resolve())}
    if args.policy == "utility":
        if len(names) != ACT_DIM:
            raise SystemExit(f"Utility 는 v1 행동 4개만 낸다. 이 설정은 행동 {len(names)}개 {names} 다 "
                             "(Utility v2 는 아직 없다, 계획서 4.8)")
        return {"kind": "utility"}
    if args.policy == "random":
        return adapt_spec({"kind": "random", "seed": 0}, len(names))
    if args.policy == "fixed":
        if not args.action or len(args.action) != len(names):
            raise SystemExit(f"--policy fixed 는 --action 값 {len(names)}개가 필요하다 ({names})")
        return {"kind": "fixed", "action": [float(x) for x in args.action]}
    return None


def default_name(args, cfg=None) -> str:
    """모델 파일 이름(없으면 정책 종류). 설정 version 이 2.0 이 아니면 `_v2_0b` 처럼 붙인다 — v2.0 경로는 그대로다.

    `--g998` 이면 `_g998`, 확률 모드면 `_stoch`, 유지 표본 모드면 `_hold<K>` 를 더 붙인다. 기본 조건(결정 모드,
    5000스텝)의 이름은 그대로라 새 조건으로 돌려도 예전 결과 디렉터리를 덮지 않는다.
    """
    name = Path(args.model).stem if args.model else (args.policy or "report")
    ver = str((getattr(cfg, "v2", None) or {}).get("version") or "2.0")
    if ver != "2.0":
        name = f"{name}_v{ver.replace('.', '_')}"
    if getattr(args, "g998", False):
        name += "_g998"
    mode = getattr(args, "act_mode", None) or "deterministic"
    if mode == "stochastic":
        name += "_stoch"
    elif mode == "hold":
        name += f"_{mode_tag(mode, hold_k_arg(args))}"
    return name


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


def calib_cache_key(ctx: Ctx) -> tuple[Path, dict]:
    """보정 캐시의 (파일, 메타). 메타가 같아야 캐시를 쓴다.

    결정 모드는 예전과 같은 파일·메타다(기존 캐시를 그대로 쓴다). 확률 모드는 파일 이름과 메타에 모드를 넣어
    같은 `--name` 으로 돌려도 결정 모드 캐시를 읽거나 덮지 않는다(스펙에도 "mode" 가 들어 있다). 유지 표본 모드는
    파일 이름에 K 까지 넣는다(`calib_hold24.npz`, 메타·스펙에도 hold_k) — K 가 다르면 서로 읽거나 덮지 않는다.
    """
    spec = ctx.need_spec()
    meta = {"spec": spec, "seeds": ctx.calib_seeds, "steps": ctx.calib_steps,
            "record_every": RECORD_EVERY, "config_digest": config_digest(ctx.cfg),
            "model_sha1": ctx.model_sha1}
    fname = "calib.npz"
    if ctx.act_mode != "deterministic":
        meta["act_mode"] = ctx.act_mode
        fname = f"calib_{mode_tag(ctx.act_mode, ctx.hold_k)}.npz"
        if ctx.hold_k is not None:
            meta["hold_k"] = ctx.hold_k
    return CACHE / ctx.name / fname, meta


def get_calib(ctx: Ctx) -> dict:
    """보정 롤아웃(학습 시드 × 3000)을 돌리거나 캐시에서 읽는다. 요약은 calib.json 으로 남긴다."""
    spec = ctx.need_spec()
    path, meta = calib_cache_key(ctx)
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
        "calib": calib_summary(cal, ctx.act_names, ctx.obs_names),
        "outcome_mean_on_calib_seeds": summarize(rows),
    })
    print(f"[보정] 학습 시드 {ctx.calib_seeds[0]}~{ctx.calib_seeds[-1]} × {ctx.calib_steps} "
          f"({time.time() - t0:.0f}s) 평균 행동 {np.round(cal['mean_action'], 4).tolist()}", flush=True)
    return cal


# --------------------------------------------------------------------- #
# 표 만들기
# --------------------------------------------------------------------- #


def summarize(rows: list[dict]) -> dict:
    """시드 평균. speed 세계의 행이면 보행 지표 열(GAIT_COLUMNS), vigilance 세계의 행이면 경계 지표 열
    (VIGIL_COLUMNS)도 평균한다(v2.0 행은 예전과 같은 열)."""
    extra = [c for c in GAIT_COLUMNS + VIGIL_COLUMNS if c in rows[0]] if rows else []
    return {c: nanmean([r.get(c) for r in rows]) for c in ROW_COLUMNS + extra}


def act_names_of(d: dict) -> list[str]:
    """결과 JSON 의 행동 이름. 1-1 전 결과(meta 에 act_names 가 없다)는 v1 4개다."""
    return list((d.get("meta") or {}).get("act_names") or ACT_NAMES)


def obs_names_of(d: dict) -> list[str]:
    """결과 JSON 의 관측 이름. 1-4 전 결과(meta 에 obs_names 가 없다)는 v1 7개다."""
    return list((d.get("meta") or {}).get("obs_names") or OBS_NAMES)


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
    return lines + md_gait(controls) + md_vigil(controls)


def md_gait(controls: dict) -> list[str]:
    """speed 세계의 보행 지표 표 (World.gait_stats). v2.0 결과는 열이 없어 빈 목록이다."""
    rows = {k: v for k, v in controls.items() if "walk_frac" in v.get("mean", {})}
    if not rows:
        return []
    L = ["", "### 보행 지표 (speed, 우열 아님. B1·B2 는 명령 보행, 비율은 실제 보행)", "",
         "| 대조군 | " + " | ".join(COL_LABEL.get(c, c) for c in GAIT_SHOW) + " |",
         "|---" * (len(GAIT_SHOW) + 1) + "|"]
    for name, row in rows.items():
        L.append(f"| {ctrl_label(name)} | " + " | ".join(fmt(c, row["mean"].get(c)) for c in GAIT_SHOW) + " |")
    return L


def md_vigil(controls: dict) -> list[str]:
    """vigilance 세계의 경계 지표 표 (World.vigil_stats). 열이 없는 결과는 빈 목록이다."""
    rows = {k: v for k, v in controls.items() if "vig_frac" in v.get("mean", {})}
    if not rows:
        return []
    L = ["", "### 경계 지표 (vigilance, 우열 아님. 구간은 결정 때: 최근 위협 = 안 보임 & threat_recency > 0.5. "
         "B4 = 이동 도주 중 다음 스텝에 놓친 비율. 360° 관측 = 직전 스텝에 경계해 넓은 시야로 본 관측의 비율)", "",
         "시야 합침 열은 경계 지속(다음 관측 360°) 때문에 정책과 무관하게 치우친다(B5′ +, B3 −, B4 +). "
         "120° 결정 = 결정 관측이 기본 FOV 인 개체만(B4 는 결정·다음 관측 모두 120° — v1 기준선 59.1% 와 비교하는 값). "
         "반경 기준 = 결정 위치에서 see_r 안 포식자 유무(FOV 무시)와 그 흔적(threat_recency 와 같은 decay)으로 나눈 구간. "
         "B5 는 관측적 기울기라 역인과(경계 섭식 0)로 − 쪽에 치우친다 — 판정은 C4-energy 대비 차로 한다. "
         "1차 정의는 1-6 사전 등록", "",
         "| 대조군 | " + " | ".join(COL_LABEL.get(c, c) for c in VIGIL_SHOW) + " |",
         "|---" * (len(VIGIL_SHOW) + 1) + "|"]
    for name, row in rows.items():
        L.append(f"| {ctrl_label(name)} | " + " | ".join(fmt(c, row["mean"].get(c)) for c in VIGIL_SHOW) + " |")
    return L


def md_meta(meta: dict, ref: str | None = "C0") -> list[str]:
    seeds = meta.get("eval_seeds") or []
    who = f"{ref} 와 " if ref else "표에 적은 비교 대상과 "
    head = int(meta.get("head") or 0)
    mode = meta.get("act_mode") or "deterministic"
    mode_s = ("deterministic" if mode == "deterministic" else
              f"hold K={meta.get('hold_k')} (조향 평균, 보행·경계 열만 개체별 잡음을 K스텝 유지한 표본, 해시·위상 표본기)"
              if mode == "hold" else
              f"{mode} (학습 분포 표본, 잡음 스트림 [평가 시드, 303, 0])")
    g_line = (f"- G_γ: γ={meta.get('gamma')}, 롤아웃 끝 {meta.get('tail')}스텝(ceil(5/(1-γ)))은 평균에서 뺐다"
              if head == 0 else
              f"- G_γ: γ={meta.get('gamma')}, 롤아웃 앞 {head}스텝(리셋 과도기)과 끝 {meta.get('tail')}스텝"
              f"(ceil(5/(1-γ)))은 평균에서 뺐다")
    return [
        f"- 생성: {meta.get('generated')} · `{meta.get('command')}`",
        f"- 정책: `{json.dumps(meta.get('spec'), ensure_ascii=False)}`",
        f"- 평가: 시드 {seeds[0] if seeds else '?'}~{seeds[-1] if seeds else '?'} ({len(seeds)}개) × "
        f"{meta.get('eval_steps')}스텝, {mode_s}",
        g_line,
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
    names = act_names_of(d)
    if tag == "C2":
        L.append("- 상수: " + ", ".join(f"{k} {v:.4f}" for k, v in zip(names, d["best"])))
    else:
        L.append(f"- 바탕 C2 상수: {np.round(d['base_action'], 4).tolist()}, 구간별 행동: "
                 f"{[names[k] for k in d['dims']]}")
        L += ["", "| 구간 | " + " | ".join(names[k] for k in d["dims"]) + " |",
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
    rows = {tag: {"mean": d["eval"]["mean"]}, **{k: {"mean": m} for k, m in d.get("ref_mean", {}).items()}}
    L += md_gait(rows) + md_vigil(rows)
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
        names = act_names_of(d)
        L += ["", "## 오프라인 민감도 (보정 표본에서 개입 전후 평균 |Δ행동|)", "",
              "| 대조군 | " + " | ".join(names) + " |", "|---" * (len(names) + 1) + "|"]
        for name, v in sens.items():
            L.append(f"| {name} | " + " | ".join(f"{x:.4f}" for x in v) + " |")
    return L


def md_r2(d: dict) -> list[str]:
    L = ["# 진단: 선형 R² (행동 차원별)", "",
         f"- 표본: 학습 시드 보정 롤아웃 {d['samples']}개 (관측 {len(obs_names_of(d))} + 절편으로 회귀)",
         "- R² > 0.95 는 '규칙 수준'으로 적는다. 실패로 보지 않는다 (6.1-5).", "",
         "| 행동 | " + " | ".join(f"R² ({k})" for k in d["r2"]) + " | 표준편차 (C0) | 판정 |",
         "|---" * (len(d["r2"]) + 3) + "|"]
    for i, name in enumerate(act_names_of(d)):
        vals = [d["r2"][k][i] for k in d["r2"]]
        c0 = d["r2"]["C0"][i]
        verdict = "규칙 수준" if c0 is not None and c0 > 0.95 else ""
        L.append(f"| {name} | " + " | ".join("—" if v is None else f"{v:.3f}" for v in vals)
                 + f" | {d['act_std']['C0'][i]:.4f} | {verdict} |")
    return L


def md_curves(d: dict) -> list[str]:
    names = act_names_of(d)
    L = ["# 진단: 반응 곡선", "",
         "- 조건부: 실제 표본을 관측 분위수 구간으로 나눈 평균 행동 (smart_check react 와 같은 방식, 개입 아님)",
         "- 개입: 관측 j 만 격자값으로 바꿔 넣은 평균 행동 (부분 의존). 정책이 j 를 쓰는지는 이쪽으로 본다", ""]
    if d.get("react"):
        keys = [k for k in next(iter(d["react"].values())) if k != "n"]
        L += ["## 상황별 평균 행동", "",
              "| 상황 | n | " + " | ".join(f"{k} {a}" for k in keys for a in names) + " |",
              "|---" * (2 + len(keys) * len(names)) + "|"]
        for name, row in d["react"].items():
            L.append(f"| {name} | {row['n']} | " + " | ".join(f"{x:.3f}" for k in keys for x in row[k]) + " |")
        L.append("")
    for obs_name in d["conditional"]:          # 결과의 관측 순서 (v2.2 는 threat_recency 까지 8개)
        L += [f"## {obs_name}", "", "| 구간 | n | " + " | ".join(names) + " |", "|---" * (len(names) + 2) + "|"]
        for b in d["conditional"][obs_name]:
            rng = f"{b['lo']:.3f}" if b["lo"] == b["hi"] else f"{b['lo']:.3f}~{b['hi']:.3f}"
            L.append(f"| {rng} | {b['n']} | " + " | ".join(f"{x:.3f}" for x in b["act"]) + " |")
        L += ["", "| 개입값 | " + " | ".join(names) + " |", "|---" * (len(names) + 1) + "|"]
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
            # 0-7 에서 더한 조건. 예전 JSON 은 키가 없으므로 앞 제외 0, 결정 모드로 본다.
            and int(m.get("head") or 0) == ctx.head
            and (m.get("act_mode") or "deterministic") == ctx.act_mode
            and m.get("hold_k") == ctx.hold_k                  # R1 에서 더한 조건. 예전 JSON 은 None
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
    specs = control_specs(base, cal["mean_action"], ctx.act_names)
    if ctx.args.utility and base.get("kind") != "utility":
        if ctx.act_dim == ACT_DIM:
            specs["Utility"] = {"kind": "utility"}
        else:
            print(f"  Utility 참고 행 생략: Utility 는 행동 4개만 낸다(이 세계 {ctx.act_dim}개, Utility v2 없음)")
    res = ctx.run(specs, ctx.eval_seeds, ctx.eval_steps)
    controls = control_table(res, specs)
    data = {"meta": ctx.meta(elapsed_s=round(time.time() - t0, 1)),
            "calib": calib_summary(cal, ctx.act_names, ctx.obs_names),
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
    bins = parse_bins(a.seg_bins, ctx.obs_names)
    seg = bool(bins)
    tag = "C2-seg" if seg else "C2"
    stem = a.tag or ("constsearch_seg" if seg else "constsearch")

    act_names = ctx.act_names
    if seg:
        dims = parse_dims(a.seg_dims or [], act_names)
        if not dims:
            raise SystemExit("--seg-bins 를 쓰면 --seg-dims 로 구간별 행동을 정해야 한다")
        bad = [k for k in dims if not 0 <= k < ctx.act_dim]
        if bad:
            raise SystemExit(f"--seg-dims {bad} 는 이 설정의 행동 {act_names} 밖이다")
        base_action = a.base_action if a.base_action is not None else c2_base_action(ctx)
        base_action = [float(x) for x in base_action]
        if len(base_action) != ctx.act_dim:
            raise SystemExit(f"C2-seg 바탕 상수는 값 {ctx.act_dim}개다 ({act_names}). 받은 값: {base_action}")
        S = n_segments(bins)
        names = [f"s{s}_{act_names[k]}" for s in range(S) for k in dims]

        def make_spec(vec):
            return seg_spec(base_action, bins, dims, vec)

        def default_enqueue():
            return [[base_action[k] for _ in range(S) for k in dims]]    # C2 자체(모든 구간이 C2 값)
    else:
        dims, base_action, S = list(range(ctx.act_dim)), None, 1
        names = list(act_names)        # v2.0 은 smart_check 와 같은 이름 — TPE 결과가 같아진다

        def make_spec(vec):
            return {"kind": "fixed", "action": [float(x) for x in vec]}

        def default_enqueue():
            # smart_check 와 같은 순서: C1 평균 행동, v1 학습 전 최고 상수(v1 에 없는 행동은 PRETRAIN_EXTRA)
            first = [np.asarray(get_calib(ctx)["mean_action"]).tolist()] if ctx.spec is not None else []
            return first + [V1_PRETRAIN_BEST + [PRETRAIN_EXTRA[k] for k in act_names[ACT_DIM:]]]

    if a.const_action is not None:
        if len(a.const_action) != len(names):
            raise SystemExit(f"--const-action 은 값 {len(names)}개가 필요하다 ({names})")
        best, search = [float(x) for x in a.const_action], None
    else:
        if a.enqueue is not None and not seg:
            bad = [v for v in a.enqueue if len(v) != len(names)]
            if bad:
                raise SystemExit(f"--enqueue 는 값 {len(names)}개씩이다 ({names}): {bad}")
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
        data.update(bins=bins, dims=dims, base_action=base_action, segments=seg_labels(bins, ctx.obs_names),
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
    dims = parse_dims(a.obs, ctx.obs_names) if a.obs else list(range(ctx.obs_dim))
    bad = [j for j in dims if not 0 <= j < ctx.obs_dim]
    if bad:
        raise SystemExit(f"--obs {bad} 는 이 설정의 관측 {ctx.obs_names} 밖이다")
    specs, notes = obs_control_specs(base, cal["obs_mean"], dims, a.modes, ctx.obs_names)
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
            "obs_mean": dict(zip(ctx.obs_names, np.asarray(cal["obs_mean"]).tolist())),
            "controls": controls, "offline_sensitivity": sens,
            "per_seed": {k: [public_row(r) if "_act_sum" in r else r for r in v] for k, v in res.items()}}
    save(ctx, a.tag or "permute", data, md_permute(clean(data)))
    print_controls(controls)
    return 0


def reference_actions(base: dict, obs: np.ndarray, act_dim: int = ACT_DIM) -> dict[str, np.ndarray]:
    """비교용 Utility 행동. 바탕 정책이 Utility 이거나 세계의 행동이 4개가 아니면(Utility v2 없음) 비운다."""
    if base.get("kind") == "utility" or act_dim != ACT_DIM:
        return {}
    return {"Utility": batched(build_policy({"kind": "utility"}), obs)}


def cmd_curves(ctx: Ctx) -> int:
    base = ctx.need_spec()
    cal = get_calib(ctx)
    obs, act = cal["obs"], np.asarray(cal["act"], dtype=np.float64)
    pol = build_policy(base, 0)
    acts = {"C0": act, **reference_actions(base, obs, ctx.act_dim)}
    data = {
        "meta": ctx.meta(samples=int(len(obs)), calib_seeds=ctx.calib_seeds, calib_steps=ctx.calib_steps),
        "react": react_table(obs, acts),
        "conditional": {ctx.obs_names[j]: conditional_curve(obs[:, j], act) for j in range(ctx.obs_dim)},
        "intervention": {ctx.obs_names[j]: intervention_curve(pol, obs, j, quantile_grid(obs[:, j]))
                         for j in range(ctx.obs_dim)},
        "act_std": {k: np.asarray(v).std(0).tolist() for k, v in acts.items()},
    }
    save(ctx, "curves", data, md_curves(clean(data)))
    return 0


def cmd_r2(ctx: Ctx) -> int:
    base = ctx.need_spec()
    cal = get_calib(ctx)
    obs, act = cal["obs"], np.asarray(cal["act"], dtype=np.float64)
    acts = {"C0": act, **reference_actions(base, obs, ctx.act_dim)}
    data = {"meta": ctx.meta(calib_seeds=ctx.calib_seeds, calib_steps=ctx.calib_steps),
            "samples": int(len(obs)),
            "r2": {k: linear_r2(obs, v).tolist() for k, v in acts.items()},
            "act_std": {k: np.asarray(v).std(0).tolist() for k, v in acts.items()}}
    save(ctx, "r2", data, md_r2(clean(data)))
    for k, v in data["r2"].items():
        print(f"  R² {k}: " + " ".join(f"{n} {x:.3f}" for n, x in zip(ctx.act_names, v)))
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
# 0-7: γ 선택 규칙 (4.7) · 행동 모드 비교 (#29)
# 절차는 결과를 보기 전에 results/v2/g07/PREREG.md 에 적었다. 아래 계산은 그 문서를 그대로 옮긴 것이다.
# --------------------------------------------------------------------- #

ALPHA = 0.05
# 4.7: γ 후보마다 G_0.998 과 함께 재는 결과 지표. 선택에는 쓰지 않고 보고한다(2차, Holm).
GSEL_SECONDARY = ["survival", "starve_rate", "predation_rate"]
# #29: 두 모드 차이를 볼 결과 지표 묶음(Holm, m=3). G_γ 는 따로 본다.
MODE_OUTCOME = ["survival", "starve_rate", "predation_rate"]
MODE_COLS = ["g_gamma", "mean_return", "survival", "repro", "predation_rate", "starve_rate"] + BEHAVIOR
# gammasel 이 받는 평가 조건: --g998, 결정 모드 (6.1-4, 6.1-7)
# 평가 시드는 계획서 6.1-4 의 10000~10019 (자유도 19 라 |t|>2.093 이 맞다).
GSEL_REQUIRE = {"gamma": G998["gamma"], "eval_steps": G998["eval_steps"], "head": G998["head"],
                "tail": tail_steps(G998["gamma"]), "act_mode": "deterministic",
                "eval_seeds": list(range(10000, 10020)), "config_version": "2.0"}
# G_γtrain 표가 받는 평가 조건(PREREG 2절 Etrain). 꼬리는 팔마다 ceil(5/(1−γ_train)) 이라 따로 본다.
ETRAIN_REQUIRE = {"eval_steps": EVAL_STEPS, "head": 0, "act_mode": "deterministic",
                  "eval_seeds": list(range(10000, 10020)), "config_version": "2.0"}


def fmean(x) -> float:
    """유한한 값만의 평균(없으면 nan). 행렬이면 전체 평균."""
    x = np.asarray(x, dtype=np.float64).ravel()
    x = x[np.isfinite(x)]
    return float(x.mean()) if len(x) else float("nan")


def col_means(M) -> np.ndarray:
    """(R, T) → 열(평가 시드)마다 유한한 값의 평균 (T,). 학습 시드 평균을 평가 시드별로 낸다."""
    M = np.asarray(M, dtype=np.float64)
    return np.array([fmean(M[:, t]) for t in range(M.shape[1])])


def _betacf(a: float, b: float, x: float) -> float:
    """정규화 불완전 베타의 연분수(Lentz 방법). t 분포 p 값에만 쓴다."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                   -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < 1e-15:
            break
    return h


def t_pvalue(t, df: int) -> float:
    """스튜던트 t 의 양측 p 값 (numpy·math 만). p = I_{df/(df+t²)}(df/2, 1/2)."""
    if t is None or not math.isfinite(float(t)) or df < 1:
        return float("nan")
    t = float(t)
    x = df / (df + t * t)
    a, b = df / 2.0, 0.5
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return min(1.0, math.exp(lbt) * _betacf(a, b, x) / a)
    return min(1.0, 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b)


def holm(pvals) -> list[float]:
    """Holm 보정 p 값(입력 순서 그대로). nan 은 nan 으로 두고 검정 수 m 에서 뺀다."""
    p = [float(v) if v is not None else float("nan") for v in pvals]
    idx = sorted((i for i, v in enumerate(p) if math.isfinite(v)), key=lambda i: p[i])
    m, run = len(idx), 0.0
    out = [float("nan")] * len(p)
    for k, i in enumerate(idx):
        run = max(run, min(1.0, (m - k) * p[i]))
        out[i] = run
    return out


def stratified_bootstrap_diff(A, B, reps: int = 2000, alpha: float = ALPHA, seed: int = 0) -> dict:
    """서로 다른 두 팔(학습 실행 묶음)의 평균 차 A − B 의 층화 부트스트랩 퍼센타일 CI.

    A 는 (Ra 학습 시드, T 층), B 는 (Rb, T) 이고 층은 평가 시드다. 층마다 팔마다 학습 시드를 **따로**
    복원추출한다 — 팔끼리 학습 시드 번호를 짝짓지 않는다(같은 시드 번호라도 γ 가 다르면 다른 학습이다).
    """
    A, B = np.asarray(A, dtype=np.float64), np.asarray(B, dtype=np.float64)
    if A.ndim == 1:
        A = A[:, None]
    if B.ndim == 1:
        B = B[:, None]
    if A.shape[1] != B.shape[1]:
        raise ValueError(f"층 수가 다르다: {A.shape} vs {B.shape}")
    T = A.shape[1]
    rng = np.random.default_rng(seed)
    cols = np.arange(T)[None, None, :]
    ia = rng.integers(0, A.shape[0], size=(reps, A.shape[0], T))
    ib = rng.integers(0, B.shape[0], size=(reps, B.shape[0], T))
    diff = A[ia, cols].mean(axis=(1, 2)) - B[ib, cols].mean(axis=(1, 2))
    lo, hi = np.nanpercentile(diff, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"point": float(A.mean() - B.mean()), "lo": float(lo), "hi": float(hi),
            "runs": [int(A.shape[0]), int(B.shape[0])], "strata": int(T)}


def excludes_zero(ci: dict | None) -> bool:
    return bool(ci) and ci.get("lo") is not None and ci.get("hi") is not None and (ci["lo"] > 0 or ci["hi"] < 0)


def load_result(d: str, stem: str = "ablate") -> dict:
    """진단 디렉터리의 결과 JSON. 어디서 읽었는지 `_dir` 에 남긴다."""
    p = resolve_dir(d) / f"{stem}.json"
    data = load_json(p)
    if not data:
        raise SystemExit(f"{p} 가 없다")
    data["_dir"] = str(p.parent)
    return data


def _model_of(d: dict) -> str | None:
    spec = d["meta"].get("spec") or {}
    return spec.get("policy", spec).get("model")


def arm_gamma(d: dict) -> float:
    """그 결과를 낸 모델의 학습 γ. 메타의 model_gamma, 없으면 모델 zip 에서 읽는다."""
    g = d["meta"].get("model_gamma")
    if g is None and _model_of(d):
        g = model_gamma(_model_of(d))
    if g is None:
        raise SystemExit(f"{d.get('_dir')}: 모델 학습 γ 를 알 수 없다")
    return float(g)


def train_seed_of(d: dict) -> int | None:
    """모델 옆 학습 메타(ckpt/v2/<run>.json)의 seed. 없으면 None."""
    m = _model_of(d)
    if not m:
        return None
    try:
        return int(json.loads(Path(m).with_suffix(".json").read_text(encoding="utf-8"))["seed"])
    except (OSError, KeyError, TypeError, ValueError):
        return None


def _cond(m: dict, key: str):
    if key == "head":
        return int(m.get("head") or 0)
    if key == "act_mode":
        return m.get("act_mode") or "deterministic"
    return m.get(key)


def check_same_eval(ds: list[dict], require: dict | None = None,
                    keys=("eval_seeds", "eval_steps", "gamma", "tail", "head", "config_digest")) -> None:
    """결과들의 평가 조건이 모두 같은지 본다(시드·스텝·γ·꼬리·앞 제외·설정). `require` 값과도 맞아야 한다."""
    ref = ds[0]["meta"]
    for d in ds:
        m = d["meta"]
        for k in keys:
            if _cond(m, k) != _cond(ref, k):
                raise SystemExit(f"{d.get('_dir')}: {k} 가 {ds[0].get('_dir')} 와 다르다 "
                                 f"({_cond(m, k)!r} vs {_cond(ref, k)!r})")
        if [r["seed"] for r in d["per_seed"]["C0"]] != list(m["eval_seeds"]):
            raise SystemExit(f"{d.get('_dir')}: C0 행의 시드가 eval_seeds 와 다르다")
        for k, want in (require or {}).items():
            got = _cond(m, k)
            ok = (got is not None and abs(float(got) - float(want)) < 1e-12) if k == "gamma" else got == want
            if not ok:
                raise SystemExit(f"{d.get('_dir')}: {k}={got!r} 인데 이 비교는 {want!r} 에서 잰 결과만 받는다")


def score_matrix(ds: list[dict], col: str, ctrl: str = "C0") -> np.ndarray:
    """(학습 시드 R, 평가 시드 T) 점수 행렬."""
    return np.array([_floats(r.get(col) for r in d["per_seed"][ctrl]) for d in ds], dtype=np.float64)


def group_by_gamma(ds: list[dict]) -> dict[float, list[dict]]:
    groups: dict[float, list[dict]] = {}
    for d in ds:
        groups.setdefault(arm_gamma(d), []).append(d)
    return dict(sorted(groups.items()))


def gfmt(g: float) -> str:
    return format(float(g), ".6g")


def _check_unique_models(ds: list[dict]) -> None:
    sha = [d["meta"].get("model_sha1") for d in ds]
    dup = sorted({s for s in sha if s is not None and sha.count(s) > 1})
    if dup:
        raise SystemExit(f"같은 모델이 두 번 들어왔다 (model_sha1 {dup})")


def gamma_select(ds: list[dict], reps: int = 2000, seed: int = 0,
                 require: dict | None = GSEL_REQUIRE) -> dict:
    """4.7 γ 선택 규칙 (사전 등록: results/v2/g07/PREREG.md).

    - 점수: 결정 모드, γ=0.998, 10000스텝, 앞 500·끝 2500스텝 제외한 C0 의 G_0.998.
    - 최고값 γ*: 팔 평균(학습 시드 R × 평가 시드 T 의 평균)이 가장 큰 γ. 같으면 작은 γ.
    - 후보 γ 가 γ* 와 '유의하게 다르다' = 두 층이 모두 다르다고 할 때:
      (1) 평가 시드마다 학습 시드 평균을 내 짝지은 t (자유도 T−1) |t| > 2.093, 그리고
      (2) 층화 부트스트랩(층 = 평가 시드, 팔마다 학습 시드 복원추출) 95% CI 가 0 을 포함하지 않는다.
    - 선택: γ* 와 유의하게 다르지 않은 γ 중 가장 작은 값. γ* 자신은 늘 자격이 있다.
    """
    if require:
        check_same_eval(ds, require)
    else:
        check_same_eval(ds)
    _check_unique_models(ds)
    groups = group_by_gamma(ds)
    if len(groups) < 2:
        raise SystemExit(f"γ 후보가 둘 이상이어야 한다 (받은 γ: {[gfmt(g) for g in groups]})")
    Rs = {g: len(v) for g, v in groups.items()}
    if min(Rs.values()) < 2:
        raise SystemExit(f"학습 시드 하나로는 결론 내지 않는다 (6.1-4). 팔마다 2개 이상: {Rs}")
    if len(set(Rs.values())) != 1:
        raise SystemExit(f"팔마다 학습 시드 수가 같아야 한다: {Rs}")
    # PREREG 1절: 세 팔 모두 같은 학습 시드(0, 1). 학습 메타로 시드를 알 수 있으면 팔마다 같은 묶음인지 본다
    # (예: 한 팔만 s1 대신 s2 를 넣는 것을 막는다).
    tseeds = {g: sorted(train_seed_of(d) for d in v) if all(train_seed_of(d) is not None for d in v) else None
              for g, v in groups.items()}
    known = {g: s for g, s in tseeds.items() if s is not None}
    if len({tuple(s) for s in known.values()}) > 1:
        raise SystemExit(f"팔마다 학습 시드 묶음이 같아야 한다: {known}")
    T = len(ds[0]["meta"]["eval_seeds"])
    G = {g: score_matrix(v, "g_gamma") for g, v in groups.items()}
    for g, M in G.items():
        if not np.isfinite(M).all():
            raise SystemExit(f"γ {gfmt(g)} 팔의 G 에 nan 이 있다 — 평가가 앞 제외 + 꼬리보다 짧다")
    means = {g: float(M.mean()) for g, M in G.items()}
    best = sorted(groups, key=lambda g: (-means[g], g))[0]

    arms = []
    for g, v in groups.items():
        row = {
            "gamma": g, "R": len(v), "dirs": [d.get("_dir") for d in v],
            "train_seeds": [train_seed_of(d) for d in v],
            "model_sha1": [d["meta"].get("model_sha1") for d in v],
            "mean": {c: fmean(score_matrix(v, c)) for c in ["g_gamma"] + GSEL_SECONDARY + ["mean_return"]},
            "per_run_mean": {c: [fmean(x) for x in score_matrix(v, c)] for c in ["g_gamma"] + GSEL_SECONDARY},
            "g_iqm": iqm(G[g]),
            "g_ci": stratified_bootstrap_ci(G[g], stat=fmean, reps=reps, seed=seed),
            "is_best": g == best,
        }
        if g == best:
            row["test"] = {"diff": 0.0, "t": None, "sig_t": False, "ci": None, "ci_excludes_0": False,
                           "sig": False, "eligible": True, "layers_disagree": False}
        else:
            t = paired(G[g].mean(0), G[best].mean(0))
            ci = stratified_bootstrap_diff(G[g], G[best], reps=reps, seed=seed)
            excl = excludes_zero(ci)
            sig = bool(t["sig"] and excl)
            row["test"] = {"diff": t["diff"], "sd": t["sd"], "t": t["t"], "sig_t": t["sig"], "ci": ci,
                           "ci_excludes_0": excl, "sig": sig, "eligible": not sig,
                           "layers_disagree": bool(t["sig"]) != excl}
        if all("C1" in d["per_seed"] for d in v):          # 참고: 같은 평가에서 C0 − C1 (상태 의존 이득)
            D = G[g] - score_matrix(v, "g_gamma", "C1")
            tc = paired(G[g].mean(0), score_matrix(v, "g_gamma", "C1").mean(0))
            row["c0_minus_c1"] = {"diff": tc["diff"], "t": tc["t"], "sig_t": tc["sig"],
                                  "ci": stratified_bootstrap_ci(D, stat=fmean, reps=reps, seed=seed)}
        arms.append(row)
    selected = min(r["gamma"] for r in arms if r["test"]["eligible"])

    # 2차: 선택 γ 와 다른 팔의 결과 지표 차 (짝지은 t, 비교마다 Holm m=3). 선택에는 쓰지 않는다.
    sel = groups[selected]
    secondary = []
    for g, v in groups.items():
        if g == selected:
            continue
        tests = {c: paired(col_means(score_matrix(v, c)), col_means(score_matrix(sel, c))) for c in GSEL_SECONDARY}
        ps = [t_pvalue(tests[c]["t"], T - 1) for c in GSEL_SECONDARY]
        ph = holm(ps)
        secondary.append({"gamma": g, "vs": selected, **{c: {**tests[c], "p": p, "p_holm": q,
                                                             "sig_holm": bool(math.isfinite(q) and q < ALPHA)}
                                                          for c, p, q in zip(GSEL_SECONDARY, ps, ph)}})
    return {"rule": "4.7 (PREREG.md): 최고값 γ* 와 유의하게 다르지 않은(짝지은 t |t|>2.093 이고 층화 부트스트랩 "
                    "95% CI 가 0 을 빼는 경우만 '다르다') 가장 작은 γ",
            "condition": {k: _cond(ds[0]["meta"], k) for k in ("gamma", "eval_steps", "head", "tail", "act_mode")},
            "eval_seeds": ds[0]["meta"]["eval_seeds"], "config_digest": ds[0]["meta"].get("config_digest"),
            "t_crit": T_CRIT, "df": T - 1, "reps": reps, "boot_seed": seed,
            "arms": arms, "best": best, "selected": selected, "secondary": secondary}


def train_gamma_table(ds: list[dict]) -> list[dict]:
    """각 팔의 학습 γ 로 잰 G_γtrain (표준 평가). 팔끼리 비교하지 않는다 — γ 가 달라 크기가 다르다(6.1-1).

    받는 결과는 PREREG 의 Etrain 뿐이다: 결정 모드, 평가 시드 10000~10019 × 5000스텝, 앞 제외 0,
    끝 ceil(5/(1−γ_train)), v2.0 세계.
    """
    check_same_eval(ds, ETRAIN_REQUIRE, keys=("eval_seeds", "eval_steps", "head", "config_digest"))
    out = []
    for g, v in group_by_gamma(ds).items():
        for d in v:
            if abs(float(d["meta"]["gamma"]) - g) > 1e-12:
                raise SystemExit(f"{d.get('_dir')}: G 의 γ {d['meta']['gamma']} 가 모델 학습 γ {g} 와 다르다")
            if _cond(d["meta"], "tail") != tail_steps(g):
                raise SystemExit(f"{d.get('_dir')}: 꼬리 {_cond(d['meta'], 'tail')} 가 ceil(5/(1−γ)) = "
                                 f"{tail_steps(g)} 가 아니다")
        M = score_matrix(v, "g_gamma")
        row = {"gamma": g, "R": len(v), "tail": v[0]["meta"].get("tail"), "train_seeds": [train_seed_of(d) for d in v],
               "g_mean": fmean(M), "g_per_run": [fmean(x) for x in M], "g_iqm": iqm(M)}
        if all("C1" in d["per_seed"] for d in v):
            C1 = score_matrix(v, "g_gamma", "C1")
            tc = paired(M.mean(0), C1.mean(0))
            row["c0_minus_c1"] = {"diff": tc["diff"], "t": tc["t"], "sig_t": tc["sig"],
                                  "ci": stratified_bootstrap_ci(M - C1, stat=fmean, seed=0)}
        out.append(row)
    return out


def mode_compare(det: list[dict], stoch: list[dict], reps: int = 2000, seed: int = 0) -> dict:
    """#29 결정 ↔ 확률 모드 (사전 등록: results/v2/g07/PREREG.md). 같은 모델·같은 평가 시드끼리 짝짓는다.

    γ 팔마다 차이 D = 확률 − 결정 (학습 시드 R × 평가 시드 T). 짝지은 t 는 평가 시드마다 학습 시드 평균을
    낸 T 쌍으로, CI 는 D 를 층화 부트스트랩(층 = 평가 시드, 학습 시드 복원추출, 평균)으로 낸다.
    - G_γ: |t| > 2.093 이고 CI 가 0 을 빼면 유의.
    - 결과 지표 3개(수명·아사율·피식률): Holm 보정 p < 0.05 이고 CI 가 0 을 빼면 유의.
    - 그 밖(리턴·번식·행동 지표)은 차이와 t·CI 만 적는다(우열이 아니다).
    `trigger` = G_γ 또는 결과 지표 하나라도 유의 (계획서 6.1-7 / #29 의 '차이가 유의하면').
    학습 시드가 하나뿐인 팔은 판정하지 않는다(verdict·trigger = None, 6.1-4).

    평가 시드·스텝·앞 제외·설정은 모든 결과가 같아야 한다. G 의 γ·꼬리는 E998 이면 모두 0.998·2500 이지만
    Etrain 이면 팔마다 그 팔의 학습 γ 라 다르다. 그래서 γ·꼬리는 짝(같은 모델의 두 모드)과 팔 안에서 같은지
    보고, 팔끼리 다르면 모든 결과가 자기 학습 γ 로 잰 것(Etrain)인지 본다 — E998 과 Etrain 을 섞지 않는다.

    둘째 목록은 유지 표본 모드(R1, `--act-mode hold`)여도 된다. 그때 Δ = 유지 표본 − 결정이고 모든 결과의 K 가
    같아야 한다. 둘째 모드는 결과의 "mode2"·"hold_k" 에 남는다(열 키 "stoch" 는 둘째 모드 값이다).
    """
    for d in det:
        if _cond(d["meta"], "act_mode") != "deterministic":
            raise SystemExit(f"{d.get('_dir')}: --det 에 결정 모드가 아닌 결과가 있다")
    mode2 = {_cond(d["meta"], "act_mode") for d in stoch}
    if not mode2 <= {"stochastic", "hold"} or len(mode2) != 1:
        raise SystemExit(f"--stoch 에 확률 모드가 아닌 결과가 있다(또는 확률·유지 표본 모드가 섞였다): {sorted(mode2)}")
    mode2 = mode2.pop()
    hold_ks = {d["meta"].get("hold_k") for d in stoch}
    if len(hold_ks) != 1:
        raise SystemExit(f"--hold 결과마다 K 가 다르다: {sorted(map(str, hold_ks))}")
    hold_k = hold_ks.pop()
    check_same_eval(det + stoch, keys=("eval_seeds", "eval_steps", "head", "config_digest"))
    if len({float(d["meta"]["gamma"]) for d in det + stoch}) > 1:
        for d in det + stoch:
            if abs(float(d["meta"]["gamma"]) - arm_gamma(d)) > 1e-12:
                raise SystemExit(f"{d.get('_dir')}: G 의 γ 가 결과마다 다른데 이 결과는 학습 γ {arm_gamma(d)} 가 "
                                 f"아니라 γ {d['meta']['gamma']} 로 쟀다 (E998 과 Etrain 을 섞지 않는다)")
    _check_unique_models(det)
    _check_unique_models(stoch)
    by_sha = {d["meta"].get("model_sha1"): d for d in det}
    pairs = []
    for s in stoch:
        k = s["meta"].get("model_sha1")
        if k is None or k not in by_sha:
            raise SystemExit(f"{s.get('_dir')}: 같은 모델(model_sha1 {k})의 결정 모드 결과가 없다")
        pairs.append((by_sha.pop(k), s))
    if by_sha:
        raise SystemExit(f"확률 모드 짝이 없는 결정 모드 결과: {[d.get('_dir') for d in by_sha.values()]}")
    T = len(det[0]["meta"]["eval_seeds"])
    groups: dict[float, list] = {}
    for dd, ss in pairs:
        check_same_eval([dd, ss])                       # 짝: γ·꼬리까지 모두 같다
        groups.setdefault(arm_gamma(dd), []).append((dd, ss))
    out = []
    for g, prs in sorted(groups.items()):
        dl, sl = [p[0] for p in prs], [p[1] for p in prs]
        check_same_eval(dl + sl)                        # 팔 안: γ·꼬리까지 모두 같다
        cols = {}
        for c in MODE_COLS:
            Dm, Sm = score_matrix(dl, c), score_matrix(sl, c)
            t = paired(col_means(Sm), col_means(Dm))
            ci = stratified_bootstrap_ci(Sm - Dm, stat=fmean, reps=reps, seed=seed)
            cols[c] = {"det": fmean(Dm), "stoch": fmean(Sm), **t, "p": t_pvalue(t["t"], T - 1), "ci": ci,
                       "ci_excludes_0": excludes_zero(ci)}
        enough = len(prs) >= 2
        g_row = cols["g_gamma"]
        g_row["verdict"] = bool(g_row["sig"] and g_row["ci_excludes_0"]) if enough else None
        for c, q in zip(MODE_OUTCOME, holm([cols[c]["p"] for c in MODE_OUTCOME])):
            cols[c]["p_holm"] = q
            cols[c]["verdict"] = (bool(math.isfinite(q) and q < ALPHA and cols[c]["ci_excludes_0"])
                                  if enough else None)
        trigger = (bool(g_row["verdict"] or any(cols[c]["verdict"] for c in MODE_OUTCOME))
                   if enough else None)
        out.append({"gamma": g, "R": len(prs), "train_seeds": [train_seed_of(d) for d in dl],
                    "g_eval_gamma": float(dl[0]["meta"]["gamma"]), "tail": dl[0]["meta"].get("tail"),
                    "dirs_det": [d.get("_dir") for d in dl], "dirs_stoch": [d.get("_dir") for d in sl],
                    "cols": cols, "trigger": trigger})
    m = det[0]["meta"]
    cond = {k: _cond(m, k) for k in ("gamma", "eval_steps", "head", "tail")}
    for k in ("gamma", "tail"):                          # Etrain: 팔마다 다르다 → None (팔별 값은 groups 에)
        if len({_cond(d["meta"], k) for d in det + stoch}) > 1:
            cond[k] = None
    res = {"condition": cond,
           "eval_seeds": m["eval_seeds"], "t_crit": T_CRIT, "df": T - 1, "reps": reps, "boot_seed": seed,
           "groups": out}
    if mode2 != "stochastic":                            # 확률 모드 결과는 예전 키 그대로
        res.update(mode2=mode2, hold_k=hold_k)
    return res


def _ci_s(col: str, ci: dict | None) -> str:
    if not ci:
        return "—"
    return f"[{fmt(col, ci.get('lo'))}, {fmt(col, ci.get('hi'))}]"


def _t_s(t) -> str:
    return "—" if t is None or not math.isfinite(float(t)) else f"{float(t):+.2f}"


def _n(v, spec: str) -> str:
    """숫자 하나. None·nan 은 —."""
    return "—" if v is None or not math.isfinite(float(v)) else format(float(v), spec)


def md_gammasel(d: dict, train: list[dict] | None = None) -> list[str]:
    c = d["condition"]
    L = ["# 0-7 γ 선택 (계획서 4.7, 사전 등록 results/v2/g07/PREREG.md)", "",
         f"- 평가: 시드 {d['eval_seeds'][0]}~{d['eval_seeds'][-1]} ({len(d['eval_seeds'])}개) × {c['eval_steps']}스텝, "
         f"{c['act_mode']}, G 는 γ={c['gamma']} · 앞 {c['head']}스텝과 끝 {c['tail']}스텝 제외",
         f"- 규칙: {d['rule']}",
         f"- 짝지은 t: 평가 시드마다 학습 시드 평균, 자유도 {d['df']}, |t|>{d['t_crit']}. "
         f"CI: 층화 부트스트랩 {d['reps']}회(시드 {d['boot_seed']}), 팔마다 학습 시드를 따로 복원추출",
         "", "## 판정표 (G_0.998, 결정 모드)", "",
         "| γ | 학습 시드 | G_0.998 평균 [95% CI] | 학습 시드별 | IQM | Δ vs 최고 | t | Δ 95% CI | 유의 | 자격 | 선택 |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in d["arms"]:
        t = a["test"]
        seeds = ",".join("?" if s is None else str(s) for s in a["train_seeds"])
        per = ", ".join(_n(x, ".3f") for x in a["per_run_mean"]["g_gamma"])
        sig = "—" if a["is_best"] else ("유의" + (" (층 불일치)" if t["layers_disagree"] else "") if t["sig"] else
                                        "유의 아님" + (" (층 불일치)" if t["layers_disagree"] else ""))
        L.append(f"| {gfmt(a['gamma'])}{' (최고)' if a['is_best'] else ''} | {seeds} | {_n(a['mean']['g_gamma'], '.4f')} {_ci_s('g_gamma', a['g_ci'])} | "
                 f"{per} | {_n(a['g_iqm'], '.4f')} | {_n(t['diff'], '+.4f')} | {_t_s(t['t'])} | {_ci_s('g_gamma', t['ci'])} | "
                 f"{sig} | {'O' if t['eligible'] else 'X'} | {'**선택**' if a['gamma'] == d['selected'] else ''} |")
    L += ["", f"- 최고값 γ* = {gfmt(d['best'])}, 선택 γ = **{gfmt(d['selected'])}**",
          "- '층 불일치'는 t 와 CI 중 하나만 다르다고 한 경우다. 규칙상 '유의하게 다르지 않다'로 친다.", "",
          "## 결과 지표 (같은 평가, 선택에는 쓰지 않음)", "",
          "| γ | " + " | ".join(COL_LABEL.get(x, x) for x in GSEL_SECONDARY + ["mean_return"]) + " |",
          "|---" * (len(GSEL_SECONDARY) + 2) + "|"]
    for a in d["arms"]:
        L.append(f"| {gfmt(a['gamma'])} | " + " | ".join(fmt(x, a["mean"][x]) for x in GSEL_SECONDARY + ["mean_return"])
                 + " |")
    if d["secondary"]:
        L += ["", f"### 선택 γ {gfmt(d['selected'])} 와의 차 (짝지은 t, 비교마다 Holm m={len(GSEL_SECONDARY)})", "",
              "| γ | " + " | ".join(f"{COL_LABEL.get(x, x)} Δ (t, p_Holm)" for x in GSEL_SECONDARY) + " |",
              "|---" * (len(GSEL_SECONDARY) + 1) + "|"]
        for s in d["secondary"]:
            L.append(f"| {gfmt(s['gamma'])} | " + " | ".join(
                f"{fmt(x, s[x]['diff'])} ({_t_s(s[x]['t'])}, {_n(s[x]['p_holm'], '.3f')}{'*' if s[x]['sig_holm'] else ''})"
                for x in GSEL_SECONDARY) + " |")
    if all("c0_minus_c1" in a for a in d["arms"]):
        L += ["", "## 참고: 같은 평가에서 C0 − C1 (G_0.998)", "", "| γ | Δ | t | 95% CI |", "|---|---|---|---|"]
        for a in d["arms"]:
            x = a["c0_minus_c1"]
            L.append(f"| {gfmt(a['gamma'])} | {_n(x['diff'], '+.4f')} | {_t_s(x['t'])}{'*' if x['sig_t'] else ''} | "
                     f"{_ci_s('g_gamma', x['ci'])} |")
    if train:
        L += ["", "## 참고: 학습 γ 로 잰 G_γtrain (표준 평가, 팔끼리 비교하지 않음)", "",
              "| γ_train | 꼬리 | G_γtrain 평균 | 학습 시드별 | C0 − C1 (t) |", "|---|---|---|---|---|"]
        for r in train:
            cc = r.get("c0_minus_c1")
            L.append(f"| {gfmt(r['gamma'])} | {r['tail']} | {_n(r['g_mean'], '.4f')} | "
                     + ", ".join(_n(x, ".3f") for x in r["g_per_run"]) + " | "
                     + (f"{_n(cc['diff'], '+.4f')} ({_t_s(cc['t'])}{'*' if cc['sig_t'] else ''})" if cc else "—") + " |")
    return L


def md_modecmp(d: dict) -> list[str]:
    c = d["condition"]
    g_s = (f"G 는 γ={c['gamma']} · 앞 {c['head']}·끝 {c['tail']}스텝 제외" if c.get("gamma") is not None else
           f"G 는 팔마다 그 팔의 학습 γ(γ_train) · 앞 {c['head']}스텝과 끝 ceil(5/(1−γ))스텝 제외(팔별 값은 각 절 제목)")
    hold = d.get("mode2") == "hold"
    m2 = f"유지 표본 K{d.get('hold_k')}" if hold else "확률"
    title = (f"# 결정 ↔ 유지 표본 모드 K={d.get('hold_k')} (수정 제안서 3.1 (가) R1, 비교 절차는 #29 modecmp 그대로)"
             if hold else "# 0-7 결정 ↔ 확률 모드 (계획서 6.1-7, #29, 사전 등록 results/v2/g07/PREREG.md)")
    L = [title, "",
         f"- 평가: 시드 {d['eval_seeds'][0]}~{d['eval_seeds'][-1]} × {c['eval_steps']}스텝, {g_s}",
         f"- Δ = {m2} − 결정 (같은 모델·같은 평가 시드). t 는 평가 시드마다 학습 시드 평균(자유도 {d['df']}), CI 는 "
         f"층화 부트스트랩 {d['reps']}회",
         f"- 유의: G_γ 는 |t|>{d['t_crit']} 이고 CI 가 0 을 뺀다. 결과 지표 3개는 Holm p<0.05 이고 CI 가 0 을 뺀다. "
         "나머지는 기술만 한다"]
    if d["df"] != 19:
        L.append(f"- 주의: 자유도 {d['df']}. 2.093 은 자유도 19(평가 시드 20개)의 값이다 — 사전 등록 평가가 아니다")
    L.append("")
    for gr in d["groups"]:
        sig = "결론 없음 (학습 시드 1개)" if gr["trigger"] is None else ("**있음**" if gr["trigger"] else "없음")
        ev = (f", G 의 γ {gfmt(gr['g_eval_gamma'])} · 끝 {gr['tail']}스텝" if "g_eval_gamma" in gr else "")
        L += [f"## γ_train {gfmt(gr['gamma'])} (학습 시드 {gr['train_seeds']}{ev}) — "
              f"{'모드 차 신호' if hold else '#29 신호'}: {sig}", "",
              f"| 지표 | 결정 | {m2} | Δ | t | 95% CI | 판정 |", "|---|---|---|---|---|---|---|"]
        for col, r in gr["cols"].items():
            if "verdict" in r and r["verdict"] is None:
                v = "결론 없음"
            elif "verdict" in r:
                v = "유의" if r["verdict"] else "유의 아님"
                if "p_holm" in r:
                    v += f" (p_Holm {_n(r['p_holm'], '.3f')})"
            else:
                v = "기술"
            L.append(f"| {COL_LABEL.get(col, col)} | {fmt(col, r['det'])} | {fmt(col, r['stoch'])} | "
                     f"{fmt(col, r['diff'])} | {_t_s(r['t'])} | {_ci_s(col, r['ci'])} | {v} |")
        L.append("")
    return L


def _out_required(ctx: Ctx) -> None:
    if not ctx.args.out and not ctx.args.name:
        raise SystemExit(f"{ctx.args.cmd}: 출력 위치를 --out 이나 --name 으로 준다")


def cmd_gammasel(ctx: Ctx) -> int:
    a = ctx.args
    _out_required(ctx)
    ds = [load_result(x) for x in a.dirs]
    data = gamma_select(ds, reps=a.reps, seed=a.boot_seed)
    train = train_gamma_table([load_result(x) for x in a.train_dirs]) if a.train_dirs else None
    if train is not None:
        data["train_gamma"] = train
    data["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["command"] = "python diagnose_v2.py " + " ".join(sys.argv[1:])
    save(ctx, a.tag or "gammasel", data, md_gammasel(clean(data), clean(train) if train else None))
    print(f"  최고 γ* {gfmt(data['best'])} → 선택 γ {gfmt(data['selected'])}")
    return 0


def cmd_modecmp(ctx: Ctx) -> int:
    a = ctx.args
    _out_required(ctx)
    data = mode_compare([load_result(x) for x in a.det], [load_result(x) for x in a.stoch],
                        reps=a.reps, seed=a.boot_seed)
    data["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["command"] = "python diagnose_v2.py " + " ".join(sys.argv[1:])
    save(ctx, a.tag or "modecmp", data, md_modecmp(clean(data)))
    what = f"결정 ↔ 유지 표본 K{data['hold_k']} 차 신호" if data.get("mode2") == "hold" else "#29 신호"
    for gr in data["groups"]:
        sig = "결론 없음" if gr["trigger"] is None else ("있음" if gr["trigger"] else "없음")
        print(f"  γ {gfmt(gr['gamma'])}: {what} {sig}")
    return 0


# --------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------- #


COMMANDS = {"ablate": cmd_ablate, "constsearch": cmd_constsearch, "permute": cmd_permute,
            "curves": cmd_curves, "r2": cmd_r2, "report": cmd_report,
            "gammasel": cmd_gammasel, "modecmp": cmd_modecmp}
# 롤아웃을 돌리지 않아 워커 풀이 필요 없는 명령
NO_POOL = ("report", "curves", "r2", "gammasel", "modecmp")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    g = common.add_argument_group("정책·출력")
    g.add_argument("--model", default=None, help="학습 정책 zip")
    g.add_argument("--policy", choices=["utility", "fixed", "random"], default=None)
    g.add_argument("--action", type=float, nargs="+", default=None,
                   help="--policy fixed 의 행동. 설정의 행동 수만큼(v2.0 4개, speed 를 켠 v2.1 5개, v2.2 6개)")
    g.add_argument("--name", default=None, help="results/v2/diag_<이름>. 기본은 모델 파일 이름")
    g.add_argument("--out", default=None, help="출력 디렉터리를 직접 정한다. 기본 results/v2/diag_<이름>")
    g.add_argument("--config", default=None, help="기본 configs/v2.yaml")
    g.add_argument("--workers", type=int, default=6, help="워커 프로세스 수 (기본 6)")
    g.add_argument("--gamma", type=float, default=None,
                   help="G_γ 의 γ. 기본은 모델의 학습 γ, 모델이 없으면 configs/ppo_best.yaml")
    g.add_argument("--tail", type=int, default=None, help="평균에서 뺄 끝 스텝. 기본 ceil(5/(1-γ))")
    g.add_argument("--eval-seeds", nargs="+", default=None, help="기본 10000:10020")
    g.add_argument("--eval-steps", type=int, default=None, help=f"기본 {EVAL_STEPS} (--g998 이면 {G998['eval_steps']})")
    g.add_argument("--head", type=int, default=None,
                   help="G_γ 평균에서 뺄 앞 스텝(리셋 과도기, 6.1-4). 기본 0 = 예전과 같은 출력 "
                        f"(--g998 이면 {G998['head']})")
    g.add_argument("--g998", action="store_true",
                   help=f"γ=0.998 보고 평가(6.1-4): --gamma {G998['gamma']} --eval-steps {G998['eval_steps']} "
                        f"--head {G998['head']} 를 한 번에 정한다. 기본 이름에 _g998")
    g.add_argument("--act-mode", choices=list(ACTION_MODES), default="deterministic",
                   help="행동 모드(6.1-7). deterministic = 평균 행동(기본, 언리얼과 같음), stochastic = 학습 "
                        "분포에서 표본(평가 시드에서 유도한 잡음, 재현됨). 기본 이름에 _stoch. hold = 유지 표본 모드"
                        "(R1 출시 모드: 조향 평균, 보행·경계 열만 잡음을 --hold-k 스텝 유지). 기본 이름에 _hold<K>")
    g.add_argument("--hold-k", type=int, default=None,
                   help="--act-mode hold 의 유지 길이 K(스텝, 양의 정수). hold 에서는 꼭 준다(수정 제안서 R1 은 24)")
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
    s.add_argument("--base-action", type=float, nargs="+", default=None,
                   help="C2-seg 바탕 상수(설정의 행동 수만큼). 기본은 같은 디렉터리 constsearch.json 의 C2")

    s = sub.add_parser("permute", parents=[common], help="C4-j 관측 고정·순열")
    s.add_argument("--obs", nargs="+", default=None,
                   help="관측 (이름 또는 번호). 기본 설정의 관측 전부(v2.0·v2.1 7개, v2.2 8개)")
    s.add_argument("--modes", nargs="+", choices=["fix", "perm"], default=["fix", "perm"])

    sub.add_parser("curves", parents=[common], help="반응 곡선 (조건부·개입)")
    sub.add_parser("r2", parents=[common], help="행동 차원별 선형 R²")

    s = sub.add_parser("report", parents=[common], help="결과 JSON → report.md")
    s.add_argument("--dirs", nargs="+", default=None, help="여러 학습 시드 진단 디렉터리 → IQM·CI")
    s.add_argument("--reps", type=int, default=2000, help="부트스트랩 반복 수")

    s = sub.add_parser("gammasel", parents=[common],
                       help="4.7 γ 선택 규칙 (사전 등록 results/v2/g07/PREREG.md)")
    s.add_argument("--dirs", nargs="+", required=True,
                   help="γ 후보 × 학습 시드의 --g998 결정 모드 ablate 디렉터리. 모델 학습 γ 로 팔을 나눈다")
    s.add_argument("--train-dirs", nargs="+", default=None,
                   help="참고: 같은 모델들의 학습 γ 표준 평가 ablate 디렉터리 (G_γtrain 표)")
    s.add_argument("--reps", type=int, default=2000, help="부트스트랩 반복 수")
    s.add_argument("--boot-seed", type=int, default=0, help="부트스트랩 난수 시드")

    s = sub.add_parser("modecmp", parents=[common], help="#29 결정 ↔ 확률 모드 비교 (R1 결정 ↔ 유지 표본 모드)")
    s.add_argument("--det", nargs="+", required=True, help="결정 모드 ablate 디렉터리")
    s.add_argument("--stoch", "--hold", dest="stoch", nargs="+", required=True,
                   help="같은 모델·같은 평가 조건의 확률 모드 디렉터리. 유지 표본 모드(K 하나) 디렉터리도 된다(--hold)")
    s.add_argument("--reps", type=int, default=2000, help="부트스트랩 반복 수")
    s.add_argument("--boot-seed", type=int, default=0, help="부트스트랩 난수 시드")
    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:  # pragma: no cover
        pass
    args = build_parser().parse_args(argv)
    ctx = Ctx(args)            # 행동 수는 설정에서 읽는다. --enqueue 길이는 constsearch 가 검사한다
    head = f", 앞 {ctx.head}스텝" if ctx.head else ""
    mode = f", {ctx.act_mode}" if ctx.act_mode != "deterministic" else ""
    if ctx.hold_k is not None:
        mode += f" K={ctx.hold_k}"
    print(f"[{args.cmd}] {ctx.name} → {ctx.out}  (γ={ctx.gamma}, 꼬리 {ctx.tail}스텝{head}{mode}, "
          f"워커 {args.workers})", flush=True)
    ctx.ex = make_executor(args.workers) if args.cmd not in NO_POOL else None
    try:
        return COMMANDS[args.cmd](ctx)
    finally:
        if ctx.ex is not None:
            ctx.ex.shutdown()


if __name__ == "__main__":
    sys.exit(main())
