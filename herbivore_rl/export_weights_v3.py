"""v3 행동 고르기 정책 가중치·골든 내보내기 (계획서 `Docs/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md` 4-5 e1·e2 첫 조각).

    # herbivore_rl/ 에서. R1b 출시 모델(s3)을 언리얼 모듈 폴더에 바로 쓴다
    python export_weights_v3.py
    # 다른 모델·세계 (R2 출시 모델이 정해지면: 관측 19·마스크 판 3 — 같은 코드로 나온다)
    python export_weights_v3.py --model ckpt/v3/<모델>.zip --config configs/v3_r2_on.yaml
    # 시험용 다른 폴더
    python export_weights_v3.py --out <폴더>

v1 `export_weights.py`(7-64-64-4, sigmoid 출력)는 그대로 둔다. 이 스크립트는 v3 RepertoirePolicy(`env_v2/rep_policy.py`)만 받는다.

배포 경로 (확인한 것, `env_v2/rollout.py` RepLearned → `rep_policy.rep_argmax`):
  - 정책 입력 = [세계 관측 obs_dim | 마스크 5칸] (`policy_obs`). 마스크 = 허용 ∧ 가능 ∧ 결정 (`action_mask`)
  - 망 입력은 앞 obs_dim 칸뿐이다(`RepObsSlice`, 특징 추출기 공유). 마스크 칸은 망에 들어가지 않고 막기에만 쓴다(> 0.5)
  - 로짓 = action_net(tanh(policy_net.2(tanh(policy_net.0(obs))))) — obs_dim → 64 → 64 → 5, tanh (train.PPO_KWARGS)
  - 막힌 칸 로짓 = MASK_LOGIT(−1e9), 선택 = argmax, 동점이면 낮은 번호 (`MaskedEpsCategorical.mode`). ε 는 학습에만 쓴다
  - 가치망·ε·엔트로피 배율은 내보내지 않는다

산출물 (네임스페이스 `EcoPolicyV3` — v1 전역 배열과 한 번역 단위에 들어가도 겹치지 않는다):
  PolicyWeightsV3.h        가중치(float, (out, in) 순서), 차원, 마스크 판·문턱, 관측·행동 이름, 허용 칸, 모델·설정 지문,
                           계약 해시(`contract_hash`)
  PolicyGoldenVectorsV3.h  골든 다섯 묶음 (아래)

골든 (C++ `Tests/EcoPolicyV3InferenceTest.cpp`, 파이썬 `tests/test_export_v3.py` 가 읽는다):
  1. 본 묶음: 판정 세계(--config)의 보정 시드(--seeds) 롤아웃을 모델 자신의 argmax 로 돌려 뽑은 결정 시점(다중 칸 마스크는
     고른 행동별로, 한 칸 마스크와 비결정 개체는 조금) + 실제 관측에 합성 마스크(한 칸만 허용 5, 한 칸만 막기 5, 모두 허용 1)를
     씌운 사례. 관측 + 마스크 → 로짓 5(torch float32, 배포와 같은 값) + 마스크 argmax. 허용 칸의 1·2위 로짓 차가
     NEAR_TIE_GAP(1e-4) 보다 작은 사례는 float32·float64 에서 argmax 가 갈릴 수 있어 본 묶음에서 빼고 뺀 수를 헤더에 적는다
  2. 근접 동점 묶음: 롤아웃에서 나온 근접 동점 + 두 실제 관측 사이 선분을 이분해 1·2위가 거의 같은 점(합성). 로짓 허용 오차는
     같고, 행동은 '파이썬 최대 로짓에서 NEAR_TIE_GAP 안의 허용 칸' 중 하나면 된다
  3. 동점 규칙 묶음: 로짓을 직접 준 사례(정확한 동점, 빈 마스크, −0/+0). torch argmax 가 낸 값과 같아야 한다
  4. 마스크 문턱 묶음(이 모델의 관측 칸): pred_count·threat_recency·cover_dist(·alarm_heard)를 문턱 바로 위·아래로 둔 관측 →
     `feasible_mask`. 파이썬 비교는 float32 칸과 문턱(NumPy 2 에서 float32 로 내려간다)이고 C++ 도 float 비교라 정확히 같다
  5. 마스크 판 3 묶음: 경보 세계(--alarm-config, 관측 19 = 18 + alarm_heard) 관측 이름으로 같은 문턱 격자 → `feasible_mask`.
     R2 모델이 아직 없어도 판 3 마스크 코드를 시험한다(C++ 은 '경보 0 이면 판 3 = 판 2' 도 본다)

결정성: 헤더에는 시각·절대 경로를 적지 않는다. 같은 모델·설정·코드면 바이트 단위로 같은 헤더가 나온다(tests/test_export_v3.py).
torch 는 스레드 1 로 돈다(`env.torch_init`, main 안에서도 다시 고정한다).

두뇌 파일 (10-18, 실행 중 가중치 로더 — 언리얼 `AI/Policy/EcoV3Brain.h`, 계획서 RL_SEASON_RETRAIN_PLAN.md 4.4.2):

    # 헤더는 쓰지 않고 두뇌 파일 하나만 쓴다 (빌드 없이 Play 중에 eco.V3Brain.Load 로 바꿔 끼운다)
    python export_weights_v3.py --model ckpt/v3/v3_r4_g995_s0_20m.zip --brain-file ../AdaptiveEcosystem/EcoBrains/v3_r4_g995_s0_20m.json

  JSON 하나(`BRAIN_FORMAT` 판 `BRAIN_FORMAT_VERSION`): 계약(관측 이름·행동 이름·망 모양·마스크 판·문턱 — `contract_dict` 그대로)과 계약 해시,
  허용 칸, 세 층 가중치(float32 리틀 엔디언 바이트를 base64 로 — 십진 반올림이 없다), 그 바이트의 sha256, 모델 zip 경로·sha256,
  학습 세계(모델 옆 학습 기록의 설정·지문 + 사람이 읽을 이름), 자체 확인 골든(관측 + 마스크 → torch 원 로짓 5 + 마스크 argmax).
  골든은 언리얼과 같은 세계(`BRAIN_GOLDEN_CONFIG`) 한 시드를 모델 자신의 argmax 로 돌려 고른 결정 시점(행동별)과 균등 난수 관측이다.
  허용 칸 1·2위 로짓 차가 NEAR_TIE_GAP 보다 작은 사례는 넣지 않는다(float32 순서 차이로 argmax 가 갈릴 수 있다).
  언리얼 로더는 버전·차원·이름·마스크·문턱·모양·NaN·sha256 을 보고, 골든을 C++ 순전파(EcoPolicyV3Inference.h)로 다시 돌려
  로짓이 허용 오차 안이고 행동이 같아야 받는다. 시각·절대 경로를 적지 않아 같은 모델이면 바이트 단위로 같은 파일이 나온다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch as th

ROOT = Path(__file__).resolve().parent
UE_POLICY_DIR = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
DEFAULT_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"     # R1b 출시 모델 (모델 시드 3)
DEFAULT_CONFIG = ROOT / "configs" / "v3_r1_on.yaml"               # R1 판정 세계
ALARM_CONFIG = ROOT / "configs" / "v3_r2_on.yaml"                 # 경보 세계 (관측 19, 마스크 판 3)
HEADERS = ("PolicyWeightsV3.h", "PolicyGoldenVectorsV3.h")

GOLDEN_SEEDS = (20000, 20001, 20002)     # 보정 시드 (조기 중단 점검과 같은 세 시드, 평가 시드 10000~ 와 겹치지 않는다)
GOLDEN_STEPS = 3000
HIDDEN = 64                              # train.PPO_KWARGS net_arch [64, 64] (make_model 이 바꾸지 못하게 막는다)
NEAR_TIE_GAP = 1e-4                      # 허용 칸 1·2위 로짓 차가 이보다 작으면 근접 동점
LOGIT_TOL = 1e-4                         # C++ 로짓 허용 오차 (헤더에 적어 시험이 읽는다)
PER_ACTION = 24                          # 시드마다 다중 칸 결정 시점을 고른 행동별로 최대 이만큼
N_SINGLE = 8                             # 시드마다 한 칸 마스크 결정 시점
N_NONDEC_PER_BEH = 2                     # 시드마다 비결정 개체(지금 행동 한 칸)를 지금 행동별로
SINGLE_STRIDE = 50                       # 한 칸·비결정 후보는 이 간격의 스텝에서만 모은다(메모리)
N_EDGE_PER_ACTION = 2                    # 합성 마스크를 씌울 실제 관측 (행동별)
NEAR_TIE_TARGET = 8                      # 근접 동점 묶음 크기 (롤아웃에서 나온 것 + 이분 합성)
SELECT_SEED = 3                          # 표본 고르기 난수 (결정적)

KIND_DECIDE, KIND_NONDEC, KIND_SYNTH = 0, 1, 2          # 본 묶음 사례 종류
NT_ROLLOUT, NT_BISECT = 0, 1                            # 근접 동점 사례 종류

# 두뇌 파일 (모듈 docstring '두뇌 파일')
BRAIN_FORMAT = "eco_v3_brain"
BRAIN_FORMAT_VERSION = 1
BRAIN_GOLDEN_CONFIG = ROOT / "configs" / "v3_wild3_mirror.yaml"   # 언리얼 통합 레벨과 같은 세계 (나무 + 지역 날씨, 관측 18)
BRAIN_GOLDEN_SEED = 32099              # 파이썬 탐색 시드 칸(32000~32099)의 끝 — 학습·판정·고르기에 쓰지 않는다
BRAIN_GOLDEN_STEPS = 600
BRAIN_PER_ACTION = 6                   # 다중 칸 결정 시점을 고른 행동별로 많아야 이만큼
BRAIN_N_SINGLE = 2                     # 한 칸 마스크 결정 시점
BRAIN_N_RANDOM = 6                     # 균등 난수 관측 (마스크 = 모델 허용 칸)
BRAIN_LAYERS = (("W0", "B0", "mlp_extractor.policy_net.0"), ("W1", "B1", "mlp_extractor.policy_net.2"),
                ("W2", "B2", "action_net"))


# --------------------------------------------------------------------- #
# 모델·망
# --------------------------------------------------------------------- #


def load_model(path: Path):
    from stable_baselines3 import PPO

    from env_v2.rep_policy import is_rep_model

    model = PPO.load(str(path), device="cpu")
    if not is_rep_model(model):
        raise SystemExit(f"{path} 는 RepertoirePolicy(v3) 모델이 아니다 — v1 은 export_weights.py 를 쓴다")
    return model


def extract(model) -> dict[str, np.ndarray]:
    """배포에 쓰는 세 층만. torch Linear.weight 는 (out, in) 이다. 모양이 계약(obs_dim → 64 → 64 → 5)과 다르면 멈춘다."""
    from env_v2.repertoire import N_BEHAVIORS

    pol = model.policy
    net = pol.mlp_extractor.policy_net
    if not (len(net) == 4 and isinstance(net[1], th.nn.Tanh) and isinstance(net[3], th.nn.Tanh)):
        raise SystemExit(f"policy_net 이 Linear-Tanh-Linear-Tanh 가 아니다: {net}")
    if not pol.share_features_extractor:
        raise SystemExit("특징 추출기를 공유하지 않는 모델이다(RepObsSlice 가 정책·가치 공통이어야 한다)")
    d = int(pol.rep_obs_dim)
    layers = [("0", net[0], (HIDDEN, d)), ("1", net[2], (HIDDEN, HIDDEN)), ("2", pol.action_net, (N_BEHAVIORS, HIDDEN))]
    out = {}
    for tag, lin, want in layers:
        w = lin.weight.detach().cpu().numpy().astype(np.float32)
        b = lin.bias.detach().cpu().numpy().astype(np.float32)
        if w.shape != want or b.shape != (want[0],):
            raise SystemExit(f"W{tag} 모양 {w.shape} 이 {want} 와 다르다 — v3 망 계약(obs_dim → 64 → 64 → 5)이 바뀌었다")
        out[f"W{tag}"], out[f"B{tag}"] = w, b
    return out


def forward_np(obs: np.ndarray, w: dict, dtype=np.float32) -> np.ndarray:
    """NumPy 순전파 (C++ ComputeLogits 와 같은 식): 로짓 = W2·tanh(W1·tanh(W0·obs + B0) + B1) + B2. 관측은 앞 obs_dim 칸만."""
    d = w["W0"].shape[1]
    x = np.asarray(obs)[:, :d].astype(dtype)
    h1 = np.tanh(x @ w["W0"].T.astype(dtype) + w["B0"].astype(dtype))
    h2 = np.tanh(h1 @ w["W1"].T.astype(dtype) + w["B1"].astype(dtype))
    return h2 @ w["W2"].T.astype(dtype) + w["B2"].astype(dtype)


def masked_argmax(logits: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """막힌 칸을 MASK_LOGIT 으로 바꾼 로짓의 argmax (동점이면 낮은 번호 — np.argmax·torch.argmax 와 같다)."""
    from env_v2.rep_policy import MASK_LOGIT

    lg = np.asarray(logits)
    return np.argmax(np.where(np.asarray(mask, dtype=bool), lg, lg.dtype.type(MASK_LOGIT)), axis=1).astype(np.int64)


def top_gap(logits: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """허용 칸 1·2위 로짓 차 (n,). 허용 칸이 하나 이하면 inf (동점이 생길 수 없다)."""
    lg = np.where(np.asarray(mask, dtype=bool), np.asarray(logits, dtype=np.float64), -np.inf)
    s = np.sort(lg, axis=1)
    with np.errstate(invalid="ignore"):
        g = s[:, -1] - s[:, -2]
    return np.where(np.asarray(mask, dtype=bool).sum(1) >= 2, g, np.inf)


def torch_logits(policy, pobs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """정책 입력 (n, obs_dim + 5) → (원 로짓 (n, 5) float32, 배포 argmax (n,)). get_distribution 과 같은 길로 계산하고,
    막은 로짓이 분포의 logits_m 과, argmax 가 `rep_argmax`(= predict(deterministic=True))와 같은지 확인한다."""
    from stable_baselines3.common.policies import BaseModel

    from env_v2.rep_policy import MASK_LOGIT, rep_argmax

    policy.set_training_mode(False)
    obs_t, _ = policy.obs_to_tensor(np.asarray(pobs, dtype=np.float32))
    with th.no_grad():
        feats = BaseModel.extract_features(policy, obs_t, policy.pi_features_extractor)
        raw = policy.action_net(policy.mlp_extractor.forward_actor(feats))
        dist = policy.get_distribution(obs_t)
        mask = obs_t[:, policy.rep_obs_dim:] > 0.5
        if not th.equal(th.where(mask, raw, th.full_like(raw, MASK_LOGIT)), dist.logits_m):
            raise SystemExit("원 로짓을 막은 값이 분포의 logits_m 과 다르다 — 배포 경로를 다시 확인하라")
    raw_np = raw.cpu().numpy().astype(np.float32)
    act = rep_argmax(policy, pobs)
    if not np.array_equal(act, masked_argmax(raw_np, mask.cpu().numpy())):
        raise SystemExit("rep_argmax 가 막은 로짓의 argmax 와 다르다")
    return raw_np, act


# --------------------------------------------------------------------- #
# 계약 해시·지문
# --------------------------------------------------------------------- #


def contract_dict(obs_names, mask_version: int) -> dict:
    """정책 입출력 계약 (관측 순서, 행동 순서, 망 모양, 마스크 판·문턱, 선택 규칙). 가중치는 넣지 않는다(모델 지문이 따로 있다).
    이 dict 가 바뀌면 `contract_hash` 가 바뀌고, C++ `EcoPolicyV3Inference.h` 의 알려진 해시 static_assert 가 걸린다."""
    from env_v2.rep_policy import ALARM_MASK_OBS, HIDE_COVER_OBS, MASK_LOGIT, MASK_VERSION_ALARM, THREAT_RECENCY_OBS
    from env_v2.repertoire import BEHAVIOR_NAMES

    return {
        "contract": "eco_policy_v3_io",
        "obs_names": list(obs_names),
        "behaviors": list(BEHAVIOR_NAMES),
        "net": {"hidden": [HIDDEN, HIDDEN], "activation": "tanh", "head": "logits", "net_sees_mask": False},
        "mask": {"version": int(mask_version), "threat_recency_obs": THREAT_RECENCY_OBS, "hide_cover_obs": HIDE_COVER_OBS,
                 "alarm_mask_obs": ALARM_MASK_OBS if int(mask_version) == MASK_VERSION_ALARM else None,
                 "mask_logit": MASK_LOGIT, "bit": "> 0.5"},
        "select": "argmax_masked_lowest_index",
    }


def contract_hash(obs_names, mask_version: int) -> int:
    """`contract_dict` 의 정규 JSON(키 정렬, 공백 없음) sha256 앞 16자리 → uint64."""
    s = json.dumps(contract_dict(obs_names, mask_version), sort_keys=True, separators=(",", ":"))
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], 16)


def config_digest(cfg) -> str:
    """eval_v3.config_digest·diagnose_v2.config_digest 와 같은 식(설정 dict 의 sha1 앞 12자리)."""
    return hashlib.sha1(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path: Path) -> str:
    """헤더에 적는 경로: herbivore_rl/ 기준 상대 경로(밖이면 파일 이름만). 절대 경로를 적지 않아야 결정적이다."""
    p = Path(path).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.name


def train_meta(model_path: Path) -> dict:
    """모델 옆 학습 기록 json(train_v3.py 가 쓴다)의 설정·지문. 없으면 unknown."""
    side = Path(model_path).with_suffix(".json")
    if side.exists():
        d = json.loads(side.read_text(encoding="utf-8"))
        return {"config": str(d.get("config", "unknown")), "config_digest": str(d.get("config_digest", "unknown"))}
    return {"config": "unknown", "config_digest": "unknown"}


# --------------------------------------------------------------------- #
# 골든 모으기
# --------------------------------------------------------------------- #


def collect_rollout(model, cfg, seed: int, steps: int) -> dict:
    """판정 세계 시드 하나를 모델 자신의 argmax(RepLearned, 배포·판정 모드)로 돌린다. 다중 칸 마스크 결정 시점은 모든 스텝에서,
    한 칸 마스크 결정 시점과 비결정 개체는 SINGLE_STRIDE 스텝마다 모은다. 마스크는 RepLearned 가 실제로 쓴 것이다."""
    from env_v2.rep_policy import action_mask
    from env_v2.rollout import RepLearned
    from env_v2.world import World

    w = World(cfg, seeds=[seed])
    pol = RepLearned(model)
    pol.bind_world(w)
    keep = {k: [] for k in ("obs", "mask", "act", "reads", "wake", "beh", "step", "agent")}
    for t in range(steps):
        obs = w.observe()
        pk = w.rep_peek()                       # 순수 함수 — 부르든 부르지 않든 궤적이 같다(tests/test_rep_policy_v3.py)
        a = pol(obs)
        m = pol.last_mask
        if not np.array_equal(m, action_mask(pk, obs, pol.params, obs_names=w.obs_names)):
            raise SystemExit(f"시드 {seed} 스텝 {t}: RepLearned 마스크가 action_mask(미리 보기) 와 다르다")
        reads = np.asarray(pk["reads"], dtype=bool)
        sel = reads & (m.sum(1) > 1)
        if t % SINGLE_STRIDE == 0:
            sel = np.ones_like(sel)
        idx = np.flatnonzero(sel)
        keep["obs"].append(np.asarray(obs, dtype=np.float32)[idx])
        keep["mask"].append(m[idx])
        keep["act"].append(a[idx, 0].astype(np.int64))
        keep["reads"].append(reads[idx])
        keep["wake"].append(np.asarray(pk["wake_decide"], dtype=bool)[idx])
        keep["beh"].append(np.asarray(pk["behavior"], dtype=np.int64)[idx])
        keep["step"].append(np.full(len(idx), t, dtype=np.int64))
        keep["agent"].append(idx.astype(np.int64))
        w.step(a)
    out = {k: np.concatenate(v) for k, v in keep.items()}
    out["seed"] = np.full(len(out["obs"]), seed, dtype=np.int64)
    out["obs_names"] = tuple(w.obs_names)
    return out


def _pick(rng, idx: np.ndarray, n: int) -> np.ndarray:
    idx = np.asarray(idx, dtype=np.int64)
    if len(idx) <= n:
        return idx
    return np.sort(rng.choice(idx, size=n, replace=False))


def _bisect_tie(a: np.ndarray, b: np.ndarray, mask: np.ndarray, w: dict) -> np.ndarray:
    """같은 마스크에서 argmax 가 다른 두 관측 사이 선분을 float64 순전파로 이분해, 바뀌는 자리의 관측(float32)을 낸다."""
    fa = masked_argmax(forward_np(a[None], w, np.float64), mask[None])[0]
    lo, hi = 0.0, 1.0
    a64, b64 = a.astype(np.float64), b.astype(np.float64)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        x = (1.0 - mid) * a64 + mid * b64
        if masked_argmax(forward_np(x[None], w, np.float64), mask[None])[0] == fa:
            lo = mid
        else:
            hi = mid
    return ((1.0 - hi) * a64 + hi * b64).astype(np.float32)


def _synthetic_masks() -> list[np.ndarray]:
    """한 칸만 허용 5개, 한 칸만 막기 5개, 모두 허용 1개 (SLEEP 칸 포함 — 망은 마스크를 보지 않으므로 로짓은 같다)."""
    from env_v2.repertoire import N_BEHAVIORS

    eye = np.eye(N_BEHAVIORS, dtype=bool)
    return [eye[j] for j in range(N_BEHAVIORS)] + [~eye[j] for j in range(N_BEHAVIORS)] + [np.ones(N_BEHAVIORS, bool)]


def tie_cases() -> tuple[np.ndarray, np.ndarray]:
    """동점 규칙 묶음 (로짓 직접). 기대값은 torch MaskedEpsCategorical.mode 가 낸다."""
    nz = -0.0
    rows = [
        ([0.0, 0.0, 0.0, 0.0, 0.0], [1, 1, 1, 1, 1]),       # 모두 같음 → 0
        ([1.0, 3.0, 3.0, 0.0, 0.0], [1, 1, 1, 1, 1]),       # 1·2 동점 → 1
        ([1.0, 3.0, 3.0, 0.0, 0.0], [1, 0, 1, 1, 1]),       # 1 막힘 → 2
        ([5.0, 5.0, 5.0, 5.0, 5.0], [0, 0, 0, 1, 1]),       # 3·4 동점 → 3
        ([0.0, 0.0, 0.0, 0.0, 7.0], [1, 1, 1, 1, 0]),       # 큰 값이 막힘, 나머지 동점 → 0
        ([-2.0, -1.0, -1.0, -1.0, -3.0], [1, 1, 0, 1, 0]),  # 음수 동점 → 1
        ([2.0, 1.0, 0.0, -1.0, -2.0], [0, 1, 1, 1, 1]),     # 최댓값이 막힘 → 1
        ([-1.0, nz, 0.0, -1.0, -1.0], [1, 1, 1, 1, 1]),     # −0 과 +0 은 같다 → 1
        ([0.25, 0.5, 0.5, 0.5, 0.5], [1, 0, 0, 0, 0]),      # 한 칸만 허용 → 0
        ([0.25, 0.5, 0.5, 0.5, 9.0], [0, 0, 0, 0, 1]),      # 한 칸만 허용(SLEEP) → 4
        ([3.0, 1.0, 2.0, 0.0, 0.0], [0, 0, 0, 0, 0]),       # 빈 마스크(설계상 없다): 모두 MASK_LOGIT → 0
    ]
    lg = np.array([r[0] for r in rows], dtype=np.float32)
    mk = np.array([r[1] for r in rows], dtype=bool)
    return lg, mk


def tie_expected(logits: np.ndarray, mask: np.ndarray) -> np.ndarray:
    from env_v2.rep_policy import MaskedEpsCategorical
    from env_v2.repertoire import N_BEHAVIORS

    d = MaskedEpsCategorical(N_BEHAVIORS, 0.0, 1.0).proba_distribution(th.as_tensor(logits), th.as_tensor(mask))
    return d.mode().cpu().numpy().astype(np.int64)


def mask_edge_grid(base: np.ndarray, names) -> np.ndarray:
    """가능 조건이 읽는 칸을 문턱 바로 위·아래로 두는 격자 (나머지 칸은 base). 문턱 값은 float32 로 둔다(관측이 float32 다)."""
    from env_v2.rep_policy import ALARM_MASK_OBS, HIDE_COVER_OBS, REP_ALARM_COL, THREAT_RECENCY_OBS

    names = list(names)
    f32 = np.float32
    below = lambda x: np.nextafter(f32(x), f32(0.0))     # noqa: E731
    pc = [f32(0.0), f32(0.125)]
    tr = [f32(0.0), below(THREAT_RECENCY_OBS), f32(THREAT_RECENCY_OBS), f32(1.0)]
    cv = [f32(0.0), below(HIDE_COVER_OBS), f32(HIDE_COVER_OBS), f32(1.0)]
    al = [None]
    if REP_ALARM_COL in names:
        tr = tr[:3]
        cv = cv[1:3]
        al = [f32(0.0), below(ALARM_MASK_OBS), f32(ALARM_MASK_OBS), f32(1.0)]
    rows = []
    for p in pc:
        for r in tr:
            for c in cv:
                for a in al:
                    o = np.array(base, dtype=np.float32, copy=True)
                    o[names.index("pred_count")] = p
                    o[names.index("threat_recency")] = r
                    o[names.index("cover_dist")] = c
                    if a is not None:
                        o[names.index(REP_ALARM_COL)] = a
                    rows.append(o)
    return np.stack(rows)


def build_golden(model, w: dict, cfg, alarm_names, seeds, steps: int) -> dict:
    """골든 다섯 묶음과 통계 (모듈 docstring)."""
    from env_v2.rep_policy import feasible_mask, policy_obs

    pol = model.policy
    names = tuple(pol.rep_obs_names)
    rng = np.random.default_rng(SELECT_SEED)

    pools = [collect_rollout(model, cfg, s, steps) for s in seeds]
    stats = {"seeds": [int(s) for s in seeds], "steps": int(steps), "pool_multi": 0, "pool_multi_near_tie": 0,
             "pool_single": 0, "pool_nondec": 0, "synth_near_tie": 0}
    main, near = [], []
    for p in pools:
        if p["obs_names"] != names:
            raise SystemExit(f"판정 세계 관측 {list(p['obs_names'])} 이 모델 관측 {list(names)} 과 다르다")
        raw, act = torch_logits(pol, policy_obs(p["obs"], p["mask"]))
        if not np.array_equal(act, p["act"]):
            bad = np.flatnonzero(act != p["act"])
            gaps = top_gap(raw[bad], p["mask"][bad])
            if np.any(gaps >= NEAR_TIE_GAP):
                raise SystemExit(f"롤아웃 행동과 다시 계산한 argmax 가 근접 동점이 아닌 곳에서 다르다: {bad[:5].tolist()}")
        gap = top_gap(raw, p["mask"])
        multi = p["reads"] & (p["mask"].sum(1) > 1)
        single = p["reads"] & ~multi
        nondec = ~p["reads"]
        tie = multi & (gap < NEAR_TIE_GAP)
        stats["pool_multi"] += int(multi.sum())
        stats["pool_multi_near_tie"] += int(tie.sum())
        stats["pool_single"] += int(single.sum())
        stats["pool_nondec"] += int(nondec.sum())
        for i in np.flatnonzero(tie):
            near.append(dict(obs=p["obs"][i], mask=p["mask"][i], kind=NT_ROLLOUT,
                             src=(int(p["seed"][i]), int(p["step"][i]), int(p["agent"][i]))))
        picks = []
        for a in range(len(p["mask"][0])):
            picks.append((KIND_DECIDE, _pick(rng, np.flatnonzero(multi & ~tie & (act == a)), PER_ACTION)))
        picks.append((KIND_DECIDE, _pick(rng, np.flatnonzero(single), N_SINGLE)))
        for b in range(len(p["mask"][0])):
            picks.append((KIND_NONDEC, _pick(rng, np.flatnonzero(nondec & (p["beh"] == b)), N_NONDEC_PER_BEH)))
        for kind, idx in picks:
            for i in idx:
                main.append(dict(obs=p["obs"][i], mask=p["mask"][i], kind=kind, reads=bool(p["reads"][i]),
                                 wake=bool(p["wake"][i]), beh=int(p["beh"][i]), act_rollout=int(p["act"][i]),
                                 src=(int(p["seed"][i]), int(p["step"][i]), int(p["agent"][i]))))

    # 합성 마스크: 다중 칸 결정 시점에서 고른 행동별로 앞의 몇 개 관측
    real = [r for r in main if r["kind"] == KIND_DECIDE and r["mask"].sum() > 1]
    base_rows = []
    for a in range(5):
        base_rows += [r for r in real if r["act_rollout"] == a][:N_EDGE_PER_ACTION]
    synth = []
    for r in base_rows:
        for m in _synthetic_masks():
            synth.append(dict(obs=r["obs"], mask=m, kind=KIND_SYNTH, reads=False, wake=False, beh=-1, act_rollout=-1,
                              src=r["src"]))
    if synth:
        s_raw, _ = torch_logits(pol, policy_obs(np.stack([r["obs"] for r in synth]), np.stack([r["mask"] for r in synth])))
        s_gap = top_gap(s_raw, np.stack([r["mask"] for r in synth]))
        stats["synth_near_tie"] = int((s_gap < NEAR_TIE_GAP).sum())
        synth = [r for r, g in zip(synth, s_gap) if g >= NEAR_TIE_GAP]
    main += synth

    obs = np.stack([r["obs"] for r in main])
    mask = np.stack([r["mask"] for r in main])
    logits, act = torch_logits(pol, policy_obs(obs, mask))
    gap = top_gap(logits, mask)
    if np.any(gap < NEAR_TIE_GAP):
        raise SystemExit("본 묶음에 근접 동점이 남았다")
    roll = np.array([r["act_rollout"] for r in main])
    is_roll = np.array([r["kind"] != KIND_SYNTH for r in main])
    if not np.array_equal(act[is_roll], roll[is_roll]):
        raise SystemExit("본 묶음 롤아웃 사례의 argmax 가 롤아웃 행동과 다르다")

    # 근접 동점: 롤아웃에서 나온 것 + 이분 합성 (같은 마스크·다른 행동인 본 묶음 실제 관측 쌍)
    n_need = max(NEAR_TIE_TARGET - len(near), 4)
    real_idx = [k for k, r in enumerate(main) if r["kind"] == KIND_DECIDE and r["mask"].sum() > 1]
    made = 0
    for x, i in enumerate(real_idx):
        if made >= n_need:
            break
        for j in real_idx[x + 1:]:
            if np.array_equal(mask[i], mask[j]) and act[i] != act[j] and main[i]["src"][0] == main[j]["src"][0]:
                o = _bisect_tie(obs[i], obs[j], mask[i], w)
                g_raw, _ = torch_logits(pol, policy_obs(o[None], mask[i][None]))
                if top_gap(g_raw, mask[i][None])[0] < NEAR_TIE_GAP:
                    near.append(dict(obs=o, mask=mask[i].copy(), kind=NT_BISECT, src=(-1, -1, -1)))
                    made += 1
                break
    if not near:
        raise SystemExit("근접 동점 사례를 만들지 못했다")
    n_obs = np.stack([r["obs"] for r in near])
    n_mask = np.stack([r["mask"] for r in near])
    n_logits, n_act = torch_logits(pol, policy_obs(n_obs, n_mask))
    n_gap = top_gap(n_logits, n_mask)

    t_logits, t_mask = tie_cases()
    t_act = tie_expected(t_logits, t_mask)

    e_obs = mask_edge_grid(obs[0], names)
    e_feas = feasible_mask(e_obs, names)
    a_base = np.zeros(len(alarm_names), dtype=np.float32)
    for k, n in enumerate(alarm_names):
        if n in names:
            a_base[k] = obs[0][names.index(n)]
    a_obs = mask_edge_grid(a_base, alarm_names)
    a_feas = feasible_mask(a_obs, alarm_names)

    # 파이썬 쪽 오차 (NumPy 재구현 vs torch) — 본 묶음 + 근접 동점
    all_obs = np.concatenate([obs, n_obs])
    all_ref = np.concatenate([logits, n_logits])
    stats["err_np32"] = float(np.abs(forward_np(all_obs, w, np.float32) - all_ref).max())
    stats["err_np64"] = float(np.abs(forward_np(all_obs, w, np.float64) - all_ref).max())
    stats["main_min_gap"] = float(gap[np.isfinite(gap)].min())
    stats["near_max_gap"] = float(n_gap.max())

    return dict(
        names=names, alarm_names=tuple(alarm_names), stats=stats,
        main=dict(obs=obs, mask=mask, logits=logits, act=act, kind=np.array([r["kind"] for r in main]),
                  feas=feasible_mask(obs, names), reads=np.array([r["reads"] for r in main]),
                  wake=np.array([r["wake"] for r in main]), beh=np.array([r["beh"] for r in main]),
                  src=np.array([r["src"] for r in main])),
        near=dict(obs=n_obs, mask=n_mask, logits=n_logits, act=n_act, kind=np.array([r["kind"] for r in near]),
                  src=np.array([r["src"] for r in near]), gap=n_gap),
        tie=dict(logits=t_logits, mask=t_mask, act=t_act),
        edge=dict(obs=e_obs, feas=e_feas),
        alarm=dict(obs=a_obs, feas=a_feas),
    )


# --------------------------------------------------------------------- #
# 헤더 쓰기
# --------------------------------------------------------------------- #


def f32_lit(x) -> str:
    """float32 값을 다시 읽으면 같은 float32 가 되는 가장 짧은 십진 표기 + f."""
    return np.format_float_scientific(np.float32(x), unique=True, exp_digits=2) + "f"


def c_array(ctype: str, name: str, arr, per_line: int, fmt, comment: str = "") -> str:
    flat = np.asarray(arr).reshape(-1)
    if flat.size == 0:
        raise SystemExit(f"{name} 가 비었다 — C++ 배열은 크기 0 일 수 없다")
    head = f"\tinline constexpr {ctype} {name}[{flat.size}] = {{" + (f"   // {comment}" if comment else "")
    lines = [head]
    for i in range(0, flat.size, per_line):
        chunk = ", ".join(fmt(v) for v in flat[i:i + per_line])
        lines.append("\t\t" + chunk + ("," if i + per_line < flat.size else ""))
    lines.append("\t};")
    return "\n".join(lines)


def _u8(v) -> str:
    return "1" if bool(v) else "0"


def _i32(v) -> str:
    return str(int(v))


def _names(xs) -> str:
    return ", ".join(f'"{x}"' for x in xs)


def obs_index(names, col: str) -> int:
    return list(names).index(col) if col in names else -1


def write_weights_header(path: Path, w: dict, meta: dict) -> None:
    """PolicyWeightsV3.h — 가중치와 계약 상수. 주석은 모델·설정에서 자동으로 채운다(손으로 적지 않는다)."""
    from env_v2.rep_policy import (ALARM_MASK_OBS, HIDE_COVER_OBS, MASK_LOGIT, REP_ALARM_COL, THREAT_RECENCY_OBS)
    from env_v2.repertoire import BEHAVIOR_NAMES, N_BEHAVIORS

    names = meta["obs_names"]
    d = len(names)
    obs_list = "\n".join(f"//   {k:2d} {n}" for k, n in enumerate(names))
    body = f"""// 자동 생성. 수정 금지.
// 생성: herbivore_rl/export_weights_v3.py — v3 행동 고르기 정책(RepertoirePolicy) 가중치
// model:        {meta["model"]}  (sha256 {meta["model_sha256"]})
// train config: {meta["train_config"]}  (config_digest {meta["train_digest"]})
// layers:       {d}-{HIDDEN}-{HIDDEN}-{N_BEHAVIORS}  (obs[0:{d}] -> Linear -> tanh -> Linear -> tanh -> Linear -> 로짓 {N_BEHAVIORS})
// mask:         정책 입력 [관측 {d} | 마스크 {N_BEHAVIORS}] 의 마스크 칸은 망에 들어가지 않는다.
//               막힌 칸 로짓 = {MASK_LOGIT:g} -> argmax, 동점이면 낮은 번호. 배포에는 ε 가 없다
// mask version: {meta["mask_version"]}  (rep_allowed: {" ".join(meta["allowed"])})
// contract:     0x{meta["contract_hash"]:016x}  (export_weights_v3.contract_hash — 관측 순서·행동 순서·망 모양·마스크 판·문턱·선택 규칙)
// obs:
{obs_list}
//
// 사용: EcoPolicyV3Inference.h (RunPolicyV3, ComputeFeasibleMask, ComposeActionMask)
#pragma once

#include <cstdint>

namespace EcoPolicyV3
{{
	inline constexpr std::int32_t kObsDim = {d};
	inline constexpr std::int32_t kHiddenDim = {HIDDEN};
	inline constexpr std::int32_t kNumBehaviors = {N_BEHAVIORS};
	inline constexpr std::int32_t kMaskVersion = {meta["mask_version"]};
	inline constexpr std::uint64_t kContractHash = 0x{meta["contract_hash"]:016x}ULL;
	inline constexpr std::uint64_t kModelDigest = 0x{meta["model_sha256"][:16]}ULL;   // 모델 zip sha256 앞 16자리
	inline constexpr const char* kModelName = "{Path(meta["model"]).stem}";

	inline constexpr const char* kObsNames[kObsDim] = {{{_names(names)}}};
	inline constexpr const char* kBehaviorNames[kNumBehaviors] = {{{_names(BEHAVIOR_NAMES)}}};
	// 허용 칸 (모델의 rep_allowed, 계약 순서)
	inline constexpr std::uint8_t kAllowedMask[kNumBehaviors] = {{{", ".join(_u8(b in meta["allowed"]) for b in BEHAVIOR_NAMES)}}};

	// 마스크 '가능' 조건이 읽는 관측 칸 (이름으로 찾은 번호, -1 = 없음 — 판 2)
	inline constexpr std::int32_t kObsPredCount = {obs_index(names, "pred_count")};
	inline constexpr std::int32_t kObsThreatRecency = {obs_index(names, "threat_recency")};
	inline constexpr std::int32_t kObsCoverDist = {obs_index(names, "cover_dist")};
	inline constexpr std::int32_t kObsAlarmHeard = {obs_index(names, REP_ALARM_COL)};
	// 마스크 문턱 (env_v2/rep_policy.py 관측 계약 값)과 막힌 칸 로짓
	inline constexpr float kThreatRecencyObs = {f32_lit(THREAT_RECENCY_OBS)};
	inline constexpr float kHideCoverObs = {f32_lit(HIDE_COVER_OBS)};
	inline constexpr float kAlarmMaskObs = {f32_lit(ALARM_MASK_OBS)};
	inline constexpr float kMaskLogit = {f32_lit(MASK_LOGIT)};

{c_array("float", "kW0", w["W0"], 8, f32_lit, comment=f"mlp_extractor.policy_net.0 (out,in): kW0[j*{d} + i]")}

{c_array("float", "kB0", w["B0"], 8, f32_lit)}

{c_array("float", "kW1", w["W1"], 8, f32_lit, comment=f"mlp_extractor.policy_net.2: kW1[j*{HIDDEN} + i]")}

{c_array("float", "kB1", w["B1"], 8, f32_lit)}

{c_array("float", "kW2", w["W2"], 8, f32_lit, comment=f"action_net: kW2[j*{HIDDEN} + i]")}

{c_array("float", "kB2", w["B2"], 8, f32_lit)}
}}
"""
    Path(path).write_text(body, encoding="utf-8", newline="\n")


def write_golden_header(path: Path, g: dict, meta: dict) -> None:
    """PolicyGoldenVectorsV3.h — 골든 다섯 묶음 (모듈 docstring)."""
    from env_v2.rep_policy import REP_ALARM_COL

    s, M, N, T, E, A = g["stats"], g["main"], g["near"], g["tie"], g["edge"], g["alarm"]
    d, da = len(g["names"]), len(g["alarm_names"])
    kinds = np.bincount(M["kind"], minlength=3)
    acts = np.bincount(M["act"][M["kind"] != KIND_SYNTH], minlength=5)
    from_builtin = [list(g["names"]).index(n) if n in g["names"] else -1 for n in g["alarm_names"]]
    body = f"""// 자동 생성. 수정 금지.
// 생성: herbivore_rl/export_weights_v3.py — v3 정책 골든 (순전파·마스크·argmax)
// model:   {meta["model"]}  (sha256 {meta["model_sha256"]})
// world:   {meta["world_config"]}  (config_digest {meta["world_digest"]}), 시드 {" ".join(map(str, s["seeds"]))} x {s["steps"]}스텝,
//          모델 자신의 argmax (env_v2/rollout.py RepLearned)
//
// 1. 본 묶음 kCount = {len(M["obs"])}: 롤아웃 결정 시점 {kinds[KIND_DECIDE]}, 롤아웃 비결정 {kinds[KIND_NONDEC]}, \
합성 마스크 {kinds[KIND_SYNTH]}
//    롤아웃 사례의 argmax: GRAZE {acts[0]}, FLEE {acts[1]}, HIDE {acts[2]}, FREEZE {acts[3]}, SLEEP {acts[4]}
//    기대: 원 로짓 5 (torch float32, 배포와 같은 값) + 마스크 argmax (동점이면 낮은 번호)
//    근접 동점 제외 (허용 칸 1·2위 로짓 차 < {NEAR_TIE_GAP:g}): 롤아웃 다중 칸 결정 시점 후보 {s["pool_multi"]} 중 \
{s["pool_multi_near_tie"]}, 합성 마스크 {s["synth_near_tie"]}
//    본 묶음의 가장 작은 1·2위 차 = {s["main_min_gap"]:.3e}
//    후보 수: 다중 칸 결정 {s["pool_multi"]} (모든 스텝), 한 칸 결정 {s["pool_single"]}·비결정 {s["pool_nondec"]} \
({SINGLE_STRIDE}스텝 간격)
// 2. 근접 동점 묶음 kNearTieCount = {len(N["obs"])} (롤아웃 {int((N["kind"] == NT_ROLLOUT).sum())}, 이분 합성 \
{int((N["kind"] == NT_BISECT).sum())}), 가장 큰 1·2위 차 {s["near_max_gap"]:.3e}
//    허용: 로짓 |C++ - Python| <= kLogitTolerance, 행동은 파이썬 최대 로짓에서 kNearTieGap 안의 허용 칸 중 하나
// 3. 동점 규칙 묶음 kTieCount = {len(T["logits"])}: 로짓 직접 -> torch MaskedEpsCategorical.mode
// 4. 마스크 문턱 묶음 kMaskEdgeCount = {len(E["obs"])}: 이 모델 관측 {d}칸, 문턱 바로 위·아래 -> feasible_mask (정확히 같아야 한다)
// 5. 마스크 판 3 묶음 kAlarmCount = {len(A["obs"])}: {meta["alarm_config"]} 관측 {da}칸 -> feasible_mask
//
// 파이썬 쪽 오차 (본 + 근접 동점, NumPy 재구현 vs torch): float32 {s["err_np32"]:.3e}, float64 {s["err_np64"]:.3e}
// 허용: 로짓 max |C++ - Python| <= {LOGIT_TOL:g}, 본 묶음 argmax 는 정확히 같다
#pragma once

#include <cstdint>

#include "PolicyWeightsV3.h"

namespace EcoPolicyV3::Golden
{{
	inline constexpr float kLogitTolerance = {f32_lit(LOGIT_TOL)};
	inline constexpr float kNearTieGap = {f32_lit(NEAR_TIE_GAP)};
	// 본 묶음 사례 종류
	inline constexpr std::uint8_t kKindDecide = {KIND_DECIDE};       // 롤아웃 결정 시점 (마스크 = 허용 ∧ 가능 ∧ 결정)
	inline constexpr std::uint8_t kKindNonDecide = {KIND_NONDEC};    // 롤아웃 비결정 개체 (마스크 = 지금 행동 한 칸)
	inline constexpr std::uint8_t kKindSynthetic = {KIND_SYNTH};     // 실제 관측 + 합성 마스크

	// ---- 1. 본 묶음 ----
	inline constexpr std::int32_t kCount = {len(M["obs"])};
{c_array("float", "kObs", M["obs"], d, f32_lit, comment=f"[n*{d} + i]")}
{c_array("std::uint8_t", "kMask", M["mask"], 5, _u8, comment="[n*5 + j] 정책 입력 마스크")}
{c_array("float", "kLogits", M["logits"], 5, f32_lit, comment="[n*5 + j] 원 로짓 (막기 전)")}
{c_array("std::int32_t", "kAction", M["act"], 16, _i32, comment="[n] 마스크 argmax")}
{c_array("std::uint8_t", "kKind", M["kind"], 32, _i32, comment="[n] kKind*")}
{c_array("std::uint8_t", "kFeasible", M["feas"], 5, _u8, comment="[n*5 + j] feasible_mask(관측)")}
{c_array("std::uint8_t", "kReads", M["reads"], 32, _u8, comment="[n] 요청을 읽는가 (rep_peek reads, 합성은 0)")}
{c_array("std::uint8_t", "kWakeDecide", M["wake"], 32, _u8, comment="[n] 기상 결정 (rep_peek wake_decide)")}
{c_array("std::int32_t", "kBehavior", M["beh"], 16, _i32, comment="[n] 지금 행동 (합성은 -1)")}
{c_array("std::int32_t", "kSource", M["src"], 3, _i32, comment="[n*3] 시드, 스텝, 개체 (합성은 바탕 관측)")}

	// ---- 2. 근접 동점 묶음 ----
	inline constexpr std::int32_t kNearTieCount = {len(N["obs"])};
{c_array("float", "kNearTieObs", N["obs"], d, f32_lit, comment=f"[n*{d} + i]")}
{c_array("std::uint8_t", "kNearTieMask", N["mask"], 5, _u8)}
{c_array("float", "kNearTieLogits", N["logits"], 5, f32_lit)}
{c_array("std::int32_t", "kNearTieAction", N["act"], 16, _i32, comment="[n] torch argmax (참고 — 시험은 근접 동점 칸 중 하나면 된다)")}
{c_array("std::uint8_t", "kNearTieKind", N["kind"], 32, _i32, comment=f"[n] {NT_ROLLOUT} 롤아웃, {NT_BISECT} 이분 합성")}
{c_array("std::int32_t", "kNearTieSource", N["src"], 3, _i32, comment="[n*3] 시드, 스텝, 개체 (합성은 -1)")}

	// ---- 3. 동점 규칙 묶음 (로짓 직접) ----
	inline constexpr std::int32_t kTieCount = {len(T["logits"])};
{c_array("float", "kTieLogits", T["logits"], 5, f32_lit)}
{c_array("std::uint8_t", "kTieMask", T["mask"], 5, _u8)}
{c_array("std::int32_t", "kTieAction", T["act"], 16, _i32)}

	// ---- 4. 마스크 문턱 묶음 (이 모델 관측) ----
	inline constexpr std::int32_t kMaskEdgeCount = {len(E["obs"])};
{c_array("float", "kMaskEdgeObs", E["obs"], d, f32_lit, comment=f"[n*{d} + i]")}
{c_array("std::uint8_t", "kMaskEdgeFeasible", E["feas"], 5, _u8)}

	// ---- 5. 마스크 판 3 묶음 (경보 세계 관측 이름) ----
	inline constexpr std::int32_t kAlarmObsDim = {da};
	inline constexpr std::int32_t kAlarmPredCount = {obs_index(g["alarm_names"], "pred_count")};
	inline constexpr std::int32_t kAlarmThreatRecency = {obs_index(g["alarm_names"], "threat_recency")};
	inline constexpr std::int32_t kAlarmCoverDist = {obs_index(g["alarm_names"], "cover_dist")};
	inline constexpr std::int32_t kAlarmHeard = {obs_index(g["alarm_names"], REP_ALARM_COL)};
	inline constexpr std::uint64_t kAlarmContractHash = 0x{meta["alarm_contract_hash"]:016x}ULL;
{c_array("std::int32_t", "kAlarmFromBuiltin", from_builtin, 19, _i32, comment="[i] 같은 이름의 이 모델 관측 칸 (-1 = 없음)")}
	inline constexpr std::int32_t kAlarmCount = {len(A["obs"])};
{c_array("float", "kAlarmObs", A["obs"], da, f32_lit, comment=f"[n*{da} + i]")}
{c_array("std::uint8_t", "kAlarmFeasible", A["feas"], 5, _u8)}
}}
"""
    Path(path).write_text(body, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------- #
# 두뇌 파일 (실행 중 가중치 로더)
# --------------------------------------------------------------------- #


def weights_bytes(w: dict) -> bytes:
    """세 층 가중치를 언리얼 로더와 같은 순서(W0, B0, W1, B1, W2, B2)·float32 리틀 엔디언으로 이은 바이트. sha256 은 이 바이트에 건다."""
    return b"".join(np.ascontiguousarray(w[k], dtype="<f4").tobytes() for wk, bk, _ in BRAIN_LAYERS for k in (wk, bk))


def _f32(x) -> float:
    """float32 값을 그대로 담은 파이썬 float (json 이 적는 십진을 double 로 읽어 float 로 내리면 같은 float32 다)."""
    return float(np.float32(x))


def brain_golden(model, w: dict, cfg, seed: int = BRAIN_GOLDEN_SEED, steps: int = BRAIN_GOLDEN_STEPS) -> dict:
    """두뇌 파일 자체 확인 골든: 세계 한 시드를 모델 자신의 argmax 로 돌려 다중 칸 결정 시점(고른 행동별)·한 칸 결정 시점을 고르고,
    균등 난수 관측(마스크 = 모델 허용 칸)을 더한다. 근접 동점(허용 칸 1·2위 차 < NEAR_TIE_GAP)은 뺀다. 기대값은 torch 원 로짓·배포 argmax."""
    from env_v2.rep_policy import policy_obs
    from env_v2.repertoire import BEHAVIOR_NAMES

    pol = model.policy
    names = tuple(pol.rep_obs_names)
    p = collect_rollout(model, cfg, seed, steps)
    if p["obs_names"] != names:
        raise SystemExit(f"골든 세계 관측 {list(p['obs_names'])} 이 모델 관측 {list(names)} 과 다르다")
    raw, act = torch_logits(pol, policy_obs(p["obs"], p["mask"]))
    gap = top_gap(raw, p["mask"])
    nm = p["mask"].sum(1)
    multi = p["reads"] & (nm > 1) & (gap >= NEAR_TIE_GAP)
    single = p["reads"] & (nm == 1)
    rng = np.random.default_rng(SELECT_SEED)
    picks, kinds = [], []
    for a in range(len(BEHAVIOR_NAMES)):
        idx = _pick(rng, np.flatnonzero(multi & (act == a)), BRAIN_PER_ACTION)
        picks += idx.tolist()
        kinds += ["rollout"] * len(idx)
    idx = _pick(rng, np.flatnonzero(single), BRAIN_N_SINGLE)
    picks += idx.tolist()
    kinds += ["single"] * len(idx)
    obs = [p["obs"][i] for i in picks]
    mask = [p["mask"][i] for i in picks]
    src = [(int(p["seed"][i]), int(p["step"][i]), int(p["agent"][i])) for i in picks]

    allowed = np.array([b in tuple(pol.rep_allowed) for b in BEHAVIOR_NAMES], dtype=bool)
    srng = np.random.default_rng(SELECT_SEED + 1)
    cand = srng.random((BRAIN_N_RANDOM * 4, len(names)), dtype=np.float32)
    cmask = np.tile(allowed, (len(cand), 1))
    c_raw, _ = torch_logits(pol, policy_obs(cand, cmask))
    keep = np.flatnonzero(top_gap(c_raw, cmask) >= NEAR_TIE_GAP)[:BRAIN_N_RANDOM]
    for i in keep:
        obs.append(cand[i])
        mask.append(cmask[i])
        kinds.append("random")
        src.append((-1, -1, int(i)))

    obs = np.stack(obs).astype(np.float32)
    mask = np.stack(mask).astype(bool)
    logits, act = torch_logits(pol, policy_obs(obs, mask))
    if np.any(top_gap(logits, mask) < NEAR_TIE_GAP):
        raise SystemExit("두뇌 골든에 근접 동점이 남았다")
    err = float(np.abs(forward_np(obs, w, np.float32) - logits).max())
    return dict(obs=obs, mask=mask, logits=logits, act=act, kind=kinds, src=src, err_np32=err,
                pool=dict(multi=int(multi.sum()), single=int(single.sum()), near_tie=int((p["reads"] & (nm > 1) & (gap < NEAR_TIE_GAP)).sum())))


def brain_dict(model, model_path: Path, golden_config: Path, seed: int = BRAIN_GOLDEN_SEED, steps: int = BRAIN_GOLDEN_STEPS,
               world_label: str | None = None) -> dict:
    """두뇌 파일 내용 (dict, 키 순서 고정). 모듈 docstring '두뇌 파일'."""
    import base64

    from env_v2.config import load_v2_config
    from env_v2.rep_policy import ALARM_MASK_OBS, HIDE_COVER_OBS, MASK_LOGIT, THREAT_RECENCY_OBS, check_mask_version
    from env_v2.repertoire import BEHAVIOR_NAMES

    pol = model.policy
    names = tuple(pol.rep_obs_names)
    mver = int(getattr(pol, "rep_mask_version", 1))
    check_mask_version(mver, names)
    w = extract(model)
    cfg = load_v2_config(Path(golden_config))
    g = brain_golden(model, w, cfg, seed, steps)
    tm = train_meta(model_path)
    allowed = tuple(pol.rep_allowed)
    wsha = hashlib.sha256(weights_bytes(w)).hexdigest()
    layers = []
    for wk, bk, tag in BRAIN_LAYERS:
        out_dim, in_dim = w[wk].shape
        layers.append({"name": tag, "weight": wk, "bias": bk, "out": int(out_dim), "in": int(in_dim),
                       "w_f32le_b64": base64.b64encode(np.ascontiguousarray(w[wk], dtype="<f4").tobytes()).decode("ascii"),
                       "b_f32le_b64": base64.b64encode(np.ascontiguousarray(w[bk], dtype="<f4").tobytes()).decode("ascii")})
    cases = []
    for k in range(len(g["obs"])):
        cases.append({"kind": g["kind"][k], "src": list(g["src"][k]), "obs": [_f32(v) for v in g["obs"][k]],
                      "mask": [int(b) for b in g["mask"][k]], "logits": [_f32(v) for v in g["logits"][k]], "action": int(g["act"][k])})
    name = Path(model_path).stem
    return {
        "format": BRAIN_FORMAT,
        "format_version": BRAIN_FORMAT_VERSION,
        "id": f"{name}@{wsha[:8]}",
        "contract": contract_dict(names, mver),
        "contract_hash": f"0x{contract_hash(names, mver):016x}",
        "obs_dim": len(names),
        "hidden": HIDDEN,
        "num_behaviors": len(BEHAVIOR_NAMES),
        "obs_names": list(names),
        "behaviors": list(BEHAVIOR_NAMES),
        "mask_version": mver,
        "allowed": list(allowed),
        "allowed_mask": [int(b in allowed) for b in BEHAVIOR_NAMES],
        "thresholds": {"threat_recency_obs": _f32(THREAT_RECENCY_OBS), "hide_cover_obs": _f32(HIDE_COVER_OBS),
                       "alarm_mask_obs": _f32(ALARM_MASK_OBS), "mask_logit": _f32(MASK_LOGIT)},
        "layers": layers,
        "weights_sha256": wsha,
        "model": {"name": name, "path": rel(model_path), "sha256": file_sha256(model_path)},
        "train": {"config": tm["config"], "config_digest": tm["config_digest"],
                  "world": world_label if world_label else Path(tm["config"]).stem},
        "golden": {"world_config": rel(golden_config), "world_digest": config_digest(cfg), "seed": int(seed), "steps": int(steps),
                   "logit_tolerance": _f32(LOGIT_TOL), "near_tie_gap": _f32(NEAR_TIE_GAP), "count": len(cases),
                   "pool": g["pool"], "err_np32": g["err_np32"], "cases": cases},
        "exporter": "herbivore_rl/export_weights_v3.py --brain-file",
    }


def write_brain_file(path: Path, d: dict) -> None:
    """두뇌 파일 쓰기 (UTF-8, LF, 키 순서 그대로 — 같은 모델이면 바이트 단위로 같다)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def export_brain_file(model_path: Path, out_file: Path, golden_config: Path = BRAIN_GOLDEN_CONFIG, seed: int = BRAIN_GOLDEN_SEED,
                      steps: int = BRAIN_GOLDEN_STEPS, world_label: str | None = None) -> dict:
    """두뇌 파일 하나를 쓴다 (헤더는 쓰지 않는다). 반환: 파일 dict."""
    model_path = Path(model_path)
    if not model_path.exists():
        raise SystemExit(f"{model_path} 없음")
    prev_threads = th.get_num_threads()
    th.set_num_threads(1)
    try:
        model = load_model(model_path)
        d = brain_dict(model, model_path, Path(golden_config), seed, steps, world_label)
    finally:
        th.set_num_threads(prev_threads)
    write_brain_file(Path(out_file), d)
    return d


# --------------------------------------------------------------------- #


def export(model_path: Path, config: Path, alarm_config: Path, out: Path, seeds=GOLDEN_SEEDS,
           steps: int = GOLDEN_STEPS) -> dict:
    """두 헤더를 `out` 에 쓴다. 반환: 메타·통계 (main 이 찍는다)."""
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import check_mask_version, mask_version_of
    from env_v2.world import obs_names

    model_path, config, alarm_config, out = Path(model_path), Path(config), Path(alarm_config), Path(out)
    if not model_path.exists():
        raise SystemExit(f"{model_path} 없음")
    prev_threads = th.get_num_threads()
    th.set_num_threads(1)
    try:
        model = load_model(model_path)
        pol = model.policy
        names = tuple(pol.rep_obs_names)
        mver = int(getattr(pol, "rep_mask_version", 1))
        check_mask_version(mver, names)
        cfg = load_v2_config(config)
        alarm_names = tuple(obs_names(load_v2_config(alarm_config)))
        if mask_version_of(alarm_names) != 3:
            raise SystemExit(f"{alarm_config} 는 관측에 alarm_heard 가 있는 경보 세계여야 한다")
        w = extract(model)
        g = build_golden(model, w, cfg, alarm_names, seeds, steps)
    finally:
        th.set_num_threads(prev_threads)

    tm = train_meta(model_path)
    meta = dict(model=rel(model_path), model_sha256=file_sha256(model_path), train_config=tm["config"],
                train_digest=tm["config_digest"], world_config=rel(config), world_digest=config_digest(cfg),
                alarm_config=rel(alarm_config), obs_names=names, mask_version=mver, allowed=tuple(pol.rep_allowed),
                contract_hash=contract_hash(names, mver), alarm_contract_hash=contract_hash(alarm_names, 3))
    out.mkdir(parents=True, exist_ok=True)
    write_weights_header(out / HEADERS[0], w, meta)
    write_golden_header(out / HEADERS[1], g, meta)
    return dict(meta=meta, stats=g["stats"], weights=w, golden=g,
                counts=dict(main=len(g["main"]["obs"]), near=len(g["near"]["obs"]), tie=len(g["tie"]["logits"]),
                            edge=len(g["edge"]["obs"]), alarm=len(g["alarm"]["obs"])))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="v3 행동 고르기 정책 가중치·골든 내보내기")
    p.add_argument("--model", default=str(DEFAULT_MODEL))
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="골든 롤아웃 세계 (모델 관측과 같아야 한다)")
    p.add_argument("--alarm-config", default=str(ALARM_CONFIG), help="마스크 판 3 골든의 관측 이름을 줄 경보 세계")
    p.add_argument("--seeds", type=int, nargs="+", default=list(GOLDEN_SEEDS))
    p.add_argument("--steps", type=int, default=GOLDEN_STEPS)
    p.add_argument("--out", default=str(UE_POLICY_DIR), help="헤더를 쓸 폴더 (기본: 언리얼 모듈 AI/Policy)")
    p.add_argument("--brain-file", default=None,
                   help="주면 헤더 대신 실행 중 가중치 로더의 두뇌 파일(JSON) 하나만 쓴다 (모듈 docstring '두뇌 파일')")
    p.add_argument("--golden-config", default=str(BRAIN_GOLDEN_CONFIG), help="두뇌 파일 골든 세계 (모델 관측과 같아야 한다)")
    p.add_argument("--golden-seed", type=int, default=BRAIN_GOLDEN_SEED)
    p.add_argument("--golden-steps", type=int, default=BRAIN_GOLDEN_STEPS)
    p.add_argument("--world-label", default=None, help="두뇌 파일 train.world (사람이 읽을 학습 세계 이름, 기본: 학습 설정 파일 이름)")
    args = p.parse_args(argv)

    if args.brain_file:
        d = export_brain_file(Path(args.model), Path(args.brain_file), Path(args.golden_config), args.golden_seed, args.golden_steps,
                              args.world_label)
        g = d["golden"]
        print(f"두뇌: {d['id']}  관측 {d['obs_dim']}  마스크 판 {d['mask_version']}  허용 {' '.join(d['allowed'])}  계약 {d['contract_hash']}")
        print(f"가중치 sha256 {d['weights_sha256']}  모델 sha256 {d['model']['sha256'][:16]}  학습 {d['train']['config']} ({d['train']['world']})")
        print(f"골든 {g['count']} (세계 {g['world_config']} 시드 {g['seed']} × {g['steps']}, NumPy 오차 {g['err_np32']:.3e})")
        print(f"생성: {args.brain_file}")
        return 0

    r = export(Path(args.model), Path(args.config), Path(args.alarm_config), Path(args.out), args.seeds, args.steps)
    m, s, c = r["meta"], r["stats"], r["counts"]
    print(f"모델: {m['model']}  sha256 {m['model_sha256'][:16]}  관측 {len(m['obs_names'])}  마스크 판 {m['mask_version']}")
    print(f"계약 해시: 0x{m['contract_hash']:016x}  (경보 세계 0x{m['alarm_contract_hash']:016x})")
    print(f"골든: 본 {c['main']}  근접 동점 {c['near']}  동점 규칙 {c['tie']}  마스크 문턱 {c['edge']}  판 3 {c['alarm']}")
    print(f"근접 동점 제외: 다중 칸 결정 후보 {s['pool_multi']} 중 {s['pool_multi_near_tie']}, 합성 마스크 {s['synth_near_tie']}")
    print(f"NumPy vs torch 최대 로짓 오차: float32 {s['err_np32']:.3e}, float64 {s['err_np64']:.3e}")
    print(f"생성: {Path(args.out) / HEADERS[0]}\n      {Path(args.out) / HEADERS[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
