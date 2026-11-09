"""v3 R1 행동 고르기 PPO 학습 (명세 `Docs/RL_Policy/RL_V3_R1_SPEC.md` 3·4절, 사전 등록 `results/v3/r1/PREREG.md`).

    # herbivore_rl/ 에서. 본 학습: 모델 시드 0~5 × 20M (체크포인트 1M 마다, 학습 기록 1M 마다)
    python train_v3.py --config configs/v3_r1.yaml --seed 0 --steps 20000000
    # 학습 전 결정 비율 f_dec 측정(보정 시드 20000~20002 × 3000스텝, 시작 정책) → yaml train.repertoire.f_dec 에 적는다
    python train_v3.py measure-fdec --config configs/v3_r1.yaml
    # v3 R2 (명세 RL_V3_R2_SPEC.md 10절 6단계): R2 세계 = v3_r1 + 경보(관측 19·마스크 판 3 — 노려보기는 사람 결정 10-13 으로 뺐다),
    # 모방 초기화(warmstart_v3.py --teacher2 fsm_r2)
    # (가중치 곁 파일의 world_digest 가 이 설정과 다르거나, R2 세계에서 출처 표시가 없는 10-13 전 가중치면 시작 전에 멈춘다)
    python train_v3.py --config configs/v3_r2.yaml --seed 0 --steps 20000000 --warmstart ckpt/v3/ws_r2/v3_r2_ws_s0.pt
    # 조기 중단 π 점검(판정 사전 등록 results/v3/r2/judge/PREREG.md 2절): 체크포인트의 니치 π 를 보정 시드 20000~20002 × 3000 에서
    python train_v3.py measure-pi --config configs/v3_r2_on.yaml --model ckpt/v3/v3_r2_g995_s0_20m_2m.zip \
        --out results/v3/r2/early/s0_2m_pi.json

학습 (train_v2.py 의 S1-a 조리법 그대로):
- 독립 세계 K 개를 묶은 MultiWorldVecEnv 의 이산 행동 경로(`train.repertoire` 블록이 켠다, env_v2/vec_env.py): 행동 Discrete(5),
  관측 [세계 관측 18 | 마스크 5]. 세계 8개·교체 5000·rollout_world_steps 256 은 설정 train 블록, 학습 세계 시드 풀은 v2 와 같다
  (cfg.train_seeds, 세계 선택 시드 = 모델 시드)
- 정책 RepertoirePolicy(env_v2/rep_policy.py): 18 → 64 → 64 → 로짓 5, 가치망 64·64, tanh(v3 R2 경보 세계는 관측 19 → 64 → 64 → 5,
  마스크 판 3 — 판은 관측 이름으로 정해 모델에 저장한다, `mask_version_of`). 시작 로짓 편향 log(init_probs),
  학습 분포 π′ = (1 − ε)·π + ε·U(m), 엔트로피 계수(범주) = ent_coef_base ÷ f_dec
- PPO 값: γ 0.995 (S1-a·v2.4s 학습 명령의 --gamma 0.995), 나머지는 --ppo-config(configs/ppo_best.yaml: learning_rate·clip_range·
  n_epochs·ent_coef)와 train.PPO_KWARGS(batch_size 4096·gae_lambda 0.95) — v2.4s 학습(v2_4sp_g995_s20 메타 JSON)과 같다.
  ent_coef 는 튜닝값 그대로 두고 분포의 엔트로피 배율 ent_scale = cat_ent_coef / ent_coef 로 범주 계수를 맞춘다(cm.py 와 같은 방식)
- 체크포인트: 1M 마다 `<out>_<k>m.zip`, 끝에 `<out>.zip` 과 메타 `<out>.json`
- 학습 기록(1M 마다, `<out>.log.jsonl`·메타 `log_history`·TensorBoard `rep/*`, 명세 4절):
    · use_<행동>: 실행한 행동의 개체-스텝 비중(지난 기록 뒤 구간), decide_frac: 요청을 읽은 개체-스텝 비율
    · ent_dec: 결정 시점 표본의 π 엔트로피 평균(ε 제외, 배율 없음 — 마지막 롤아웃), ent_dec_multi: 그중 마스크가 두 칸 이상인 표본
    · starve_rate·pred_rate: 개체-스텝당 아사·피식 수(구간)
    · pi_<x>_niche·pi_<x>_base: 목록의 행동 x(GRAZE 제외)의 결정 시점 π(x)(ε 제외) 평균 — 니치(PREREG U_x 의 첫 항 조건, FLEE 는
      U_ESC 조건)와 둘째 항 조건. pi_esc_niche·pi_esc_base 는 FLEE ∪ HIDE ∪ FREEZE 확률의 합. 조기 중단(PREREG 6절)의 '니치에서 π
      확률'이 pi_<x>_niche 다. FREEZE 는 --freeze-variant 판(기본 near, R0 에서 통과한 판)의 조건을 쓴다(eval_v3.u_terms)
    · 지표 정의(--u-def, 기본 auto = 관측에 alarm_heard 가 있는 세계(마스크 판 3, v3 R2)면 r2, 아니면 r1 — R1 학습 기록은 그대로다).
      r2 는 eval_v3 판정과 같은 정의다: HIDE·FREEZE 니치는 R1b 의 U_HIDE′·U_FREEZE′ 조건이고, FREEZE 가 목록에 있으면 보고만 하는
      칸 pi_look_niche·pi_look_base(FREEZE 확률, look 니치와 교차 — eval_v3.XTerms, 손 규칙 repertoire_rules.NICHES 그대로)와
      pi_look_open_*(look 니치·교차 중 FREEZE 가 열린 표본), 표본 수 n_<x>_niche·n_<x>_base 를 더한다. stare 칸(pi_stare_*,
      pi_stare_band_*)은 노려보기(stare_down)를 켠 재현 설정에서만 생긴다 — R2 세계에는 없다(사람 결정 10-13).
      R2 조기 중단(판정 사전 등록 results/v3/r2/judge/PREREG.md 2절)은 R1 사전 등록 6절 꼴 그대로 FLEE·HIDE·FREEZE 니치 π
      (R2_EARLY_PI = pi_flee_niche·pi_hide_niche·pi_freeze_niche)와 5M 의 U_ESC·U_FREEZE′(eval_v3 run)를 본다. look 칸은 보고만
      (R2_REPORT_PI, 사람 결정 10-12 밤 — 경보 반응은 판정에서 뺐다). 같은 칸을 `measure-pi` 가 보정 시드에서 잰 값으로 보고,
      학습 기록은 함께 적기만 한다
- 리스폰 니치 유도는 쓰지 않는다.

니치 π 측정 (`measure-pi`, 조기 중단 점검 — R1 사전 등록 1절 '보정 시드 20000~20002 × 3000스텝, 체크포인트'): 저장한 모델(.zip)을
설정 세계(보정 시드를 하나씩 `World(cfg, seeds=[s])`)에서 argmax(판정 롤아웃 `rep_learned` 과 같은 궤적, 난수 없음)로 돌리며 결정
시점 표본의 π(ε 제외, 마스크 적용)를 모아, 학습 기록과 같은 `niche_probs` 칸(시드 합침과 시드별)을 낸다.

f_dec 측정 (`measure-fdec`): 학습과 같은 방식으로 만든 시작 정책(모델 시드 0 의 무작위 가중치 + 시작 로짓 편향)을 학습 설정 세계
(보정 시드 20000~20002 를 하나씩 `World(cfg, seeds=[s])`)에서 ε 혼합 분포 π′ 의 표본으로 3000스텝 돌리고, 요청을 읽은 개체-스텝
비율(`World.rep_peek` 의 reads, `World.repertoire_stats` decide_frac 과 같은 값)을 낸다. 표본 잡음은 [시드, 707] 스트림이다.

v3 R3 (관문 사전 등록 results/v3/r3/PREREG.md 13·14절):

    # 본 학습 — 모방 초기화(warmstart_v3.py, ckpt/v3/ws_r3)에서
    python train_v3.py --config configs/v3_r3.yaml --seed 0 --steps 20000000 --warmstart ckpt/v3/ws_r3/v3_r3_ws_s0.pt
    # 조기 중단 대응 1회(H13, 13-5): R1b s3 가중치에서 다시 시작 — 출처를 밝혀 싣는다. 실행 이름 기본 v3_r3r1b_g995_s<s>_20m
    python train_v3.py --config configs/v3_r3.yaml --seed 0 --steps 20000000 --init-from-model ckpt/v3/v3_r1_g995_s3_20m.zip \
        --init-source "R1b s3, R1 세계, 목록 graze·flee·hide·freeze"
    # 조기 중단 니치 π (14절, R3_EARLY_PI): 보정 시드 20000~20002 × 3000, 판정 세계
    python train_v3.py measure-pi --config configs/v3_r3_on.yaml --model ckpt/v3/v3_r3_g995_s0_20m_2m.zip --out results/v3/r3/early/s0_2m_pi.json

v3 R4 (사전 등록 results/v3/r4/PREREG.md — 언리얼과 같은 날씨 + 나무 세계, 학습 보충·지역 섞기 configs/v3_r4_train.yaml):

    python train_v3.py measure-fdec --config configs/v3_r4_train.yaml --seeds 32000 32001 32002     # 지역 셋 × 시드 셋 (train.region_mix)
    python train_v3.py --config configs/v3_r4_train.yaml --seed 0 --steps 20000000 --init-from-model ckpt/v3/v3_r1_g995_s3_20m.zip \
        --init-source "R1b s3 (게임 두뇌), R1 세계, 목록 graze·flee·hide·freeze — R4 설정이 얼기를 막아 R1b-F 로 시작" --run-name v3_r4_g995_s0_20m

- 설정에 train.region_mix 가 있으면 measure-fdec 는 시드마다 지역 모두를 한 번씩 돌리고(시드별 줄에 region), 학습 메타에 region_history·seed_history 를 남긴다.
- 학습 기록·measure-pi 의 니치 정의 r3(R3 세계면 auto): R3 판정 U 와 같은 조건(`repertoire_rules.r3_u_terms`)에서 같은 묶음의 확률 합
  (`r3_u_prob`) — pi_<u>_niche·pi_<u>_base·n_<u>_*, u ∈ esc·keep·run·leave·hide(U_HIDE′)·early. 손 규칙 문턱(거주 θ·a*, 보정 1 을 쓴 니치)은
  관문 결과(`eval_v3.r3_setup`)에서 오고, 없으면 재학습 전 측정 값이다(그때는 기록에 그렇게 적는다). 허용 목록 점검(14절 '즉시 멈춤')을 위해
  결정 표본의 π(FREEZE)·π(SLEEP) 최댓값(pi_freeze_max·pi_sleep_max)도 적는다 — 마스크가 막으므로 늘 0 이어야 한다.
- 조기 중단 칸(R3_EARLY_PI, 14절): G1 π(FLEE ∪ 은신처 밖 HIDE)(P3 가 판정 조건일 때만), G2·G4a π(HIDE), G6 π(FLEE ∪ 은신처 밖 HIDE).
  measure-pi 는 관문 결과로 판정에 쓰는 니치(통과·조건부 통과 — 9-2 표)의 칸만 `early_stop_pi` 에, 나머지는 `report_only_pi` 에 적는다.
- `--init-from-model <zip> --init-source "<출처>"`(13-5 대응 1회): 그 SB3 모델(RepertoirePolicy)의 정책·가치망 state_dict 만 이 설정으로
  만든 모델에 strict 로 싣는다(구조·ε·엔트로피·허용 목록은 이 설정 값 — R1b 의 FREEZE 로짓은 남지만 마스크가 늘 막는다). 관측 이름·마스크
  판이 다르면 멈춘다. 출처 글은 비울 수 없고, 곁 파일 `<out>.init.json`(학습 전에 쓴다)과 학습 메타 `init_from_model` 에 경로·sha1·출처·
  원래 목록을 남긴다. --warmstart 와 함께 쓰지 않는다.

v3 R7 (10-23 사람 결정 '짧게 진단 후 R7' — 반사 밖 두뇌 FLEE 막음, 마스크 판 5·6, 설계 Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 17절,
설정 생성기 results/v3/r7/make_r7_configs.py, 시작 두뇌 results/v3/r7/r7_start.py):

    python train_v3.py measure-fdec --config configs/v3_r7_train.yaml --seeds 32000 32001 32002
    python train_v3.py --config configs/v3_r7_train.yaml --ppo-config configs/ppo_r6_lam098.yaml --seed 0 --steps 20000000 \
        --init-from-model ckpt/v3/v3_r1_g995_s3_obs24route0m5.zip --init-source "<출처>" --run-name v3_r7_g995_s0_20m

- 모델의 마스크 판은 관측 이름과 세계 키 wild_flight.brain_flee_outside_reflex 로 정한다(`rep_policy.world_mask_version` — 판 5 = 두뇌 길 + 막기,
  판 6 = 대조 '길 끔' + 막기). 막는 세계는 학습 기록·measure-fdec 에 덮기 밖 결정 수 gate_free 와 그 가운데 두뇌가 낸 FLEE 수 gate_flee(마스크 안
  표본이라 늘 0)를 더 적는다.
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
from env_v2.rep_policy import (MASK_VERSION_ALARM, ROUTE_MASK_VERSIONS, ROUTE_PANIC_COL, ROUTE_SLOT_SHELTER, RepertoirePolicy, action_mask,
                               flee_gated, mask_version_of, policy_obs, rep_distribution, rep_params, sample_masked, world_mask_version)
from env_v2.repertoire import BEHAVIOR_NAMES, FLEE, FREEZE, HIDE, N_BEHAVIORS, SLEEP
from env_v2.vec_env import MultiWorldVecEnv
from train import PPO_KWARGS, load_tuned
from train_v2 import apply_lr_schedule, gamma_tag, resolve_gamma

ROOT = Path(__file__).resolve().parent
CKPT = ROOT / "ckpt" / "v3"
DEFAULT_CONFIG = ROOT / "configs" / "v3_r1.yaml"
S1A_GAMMA = 0.995                   # S1-a 조리법·v2.4s 학습의 --gamma
EVERY = 1_000_000                   # 체크포인트·학습 기록 간격 (명세 4절)
FDEC_SEEDS = (20000, 20001, 20002)  # f_dec 측정 보정 시드 (명세 3절)
FDEC_STEPS = 3000
FDEC_TAG = 707                      # f_dec 측정 표본 잡음 스트림 구분값(rollout._SALT·지연 505·C1′ 606 과 겹치지 않는다)
# v3 R2 조기 중단(판정 사전 등록 results/v3/r2/judge/PREREG.md 2절)이 보는 니치 π 칸 — R1 사전 등록 6절 꼴(FLEE 는 U_ESC 니치,
# HIDE·FREEZE 는 R1b 의 U_HIDE′·U_FREEZE′ 니치). 보고만 하는 칸은 경보 반응(look)과 재현 설정의 노려보기(stare)다
R2_EARLY_PI = ("pi_flee_niche", "pi_hide_niche", "pi_freeze_niche")
R2_REPORT_PI = ("pi_look_niche", "pi_look_open_niche", "pi_stare_niche", "pi_stare_band_niche")
# v3 R3 조기 중단(관문 사전 등록 14절)이 보는 니치 π 칸: 관문 → 칸. G3(leave)의 GRAZE 는 넣지 않는다(실패 모습이 '눌러앉기'라 π 가 0 으로
# 무너지는 꼴이 아니다). 어느 칸을 판정에 쓰는지는 관문 결과가 정한다(`r3_early_split`)
R3_EARLY_PI = {"keep": "pi_keep_niche", "run": "pi_run_niche", "crouch": "pi_hide_niche", "early": "pi_early_niche"}


def make_model_rep(venv: MultiWorldVecEnv, rep: dict, tensorboard_log: str | None, **overrides):
    """RepertoirePolicy 로 PPO 를 만든다. `train.make_model` 과 같은 PPO_KWARGS·튜닝값·구조(64-64 tanh)를 쓰고 정책 클래스와
    R1 인자만 더한다. 범주 엔트로피 배율 = cat_ent_coef / ent_coef (모듈 docstring)."""
    from stable_baselines3 import PPO

    bad = {"policy_kwargs", "net_arch", "activation_fn"} & set(overrides)
    if bad:
        raise ValueError(f"탐색 금지 항목이다(구조는 PPO_KWARGS 고정): {sorted(bad)}")
    if venv.rep is None:
        raise ValueError("이산 행동 경로 VecEnv(train.repertoire 블록이 있는 repertoire 세계)가 필요하다")
    kw = dict(PPO_KWARGS)
    kw.update(overrides)
    ent = float(kw["ent_coef"])
    if ent <= 0.0:
        raise ValueError("ent_coef > 0 이어야 한다(범주 엔트로피 계수를 배율로 넣는다)")
    kw["policy_kwargs"] = dict(PPO_KWARGS["policy_kwargs"], rep_allowed=list(rep["allowed"]), rep_epsilon=rep["epsilon"],
                               rep_ent_scale=rep["cat_ent_coef"] / ent, rep_init_logits=rep["init_logits"],
                               rep_obs_names=list(venv.obs_names),
                               # 경보 세계(v3 R2 M8)는 판 3, 두뇌 길은 판 4, 10-23 반사 밖 FLEE 막음은 판 5·6(세계 키 — world_mask_version)
                               rep_mask_version=world_mask_version(venv.worlds[0]))
    return PPO(RepertoirePolicy, venv, tensorboard_log=tensorboard_log, device="cpu", **kw)


def default_run_name(cfg, seed: int, steps: int, gamma: float, tag: str = "") -> str:
    """--run-name 이 없을 때의 실행 이름 v<version><tag>_<γ 조각>_s<seed>_<M>m (예: v3_r1_g995_s0_20m, H13 대응 v3_r3r1b_g995_s0_20m)."""
    ver = str(cfg.v2.get("version") or "3").replace(".", "_")
    m = steps / 1_000_000
    return f"v{ver}{tag}_{gamma_tag(gamma)}_s{seed}_{m:g}m"


def auto_udef(obs_names, cfg=None) -> str:
    """--u-def auto: R3 세계(`r3_tools.is_r3_world`, 설정을 주었을 때)면 r3, 관측에 alarm_heard 가 있는 세계(마스크 판 3, v3 R2)면 r2,
    아니면 r1."""
    if cfg is not None:
        import r3_tools as rt

        if rt.is_r3_world(cfg):
            return "r3"
    return "r2" if mask_version_of(obs_names) == MASK_VERSION_ALARM else "r1"


def r3_early_split(setup: dict) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(조기 중단에 쓰는 R3 관문, 보고만 하는 관문) — 14절: 판정에 쓰는 니치(통과·조건부 통과 = FSM_R3 줄)만, G1 은 P3 가 판정 조건일 때만.
    관문 결과가 없으면(관문 전) 넷 모두를 쓰는 칸으로 두고 `setup['gate_complete']` 로 미정임을 알린다."""
    if not setup.get("gate_complete"):
        return tuple(R3_EARLY_PI), ()
    use = tuple(g for g in R3_EARLY_PI if (g == "keep" and setup["p3"]) or (g != "keep" and g in setup["lines"]))
    return use, tuple(g for g in R3_EARLY_PI if g not in use)


def niche_probs(pi: np.ndarray, obs: np.ndarray, geo: dict, allowed, variant: str, udef: str = "r1",
                xterms=None, mask=None, r3: dict | None = None) -> dict:
    """결정 시점 표본의 π (n,5)(ε 제외)·관측 → 니치별 평균 π (모듈 docstring '학습 기록'). 표본이 없으면 None.
    `udef` 는 eval_v3 의 지표 정의 묶음, `xterms` 는 eval_v3.XTerms(v3 R2 stare·look 니치, r2 에서만 준다). `mask`(표본의 (n,5)
    마스크)를 주면 look_open(look 조건 & FREEZE 열림, eval_v3.look_open_terms) 칸도 낸다. r3 는 R3 판정 U 의 조건과 묶음(모듈
    docstring 'v3 R3') — `geo` 는 `repertoire_rules.r3_geo`, `r3` 는 eval_v3.r3_setup(θ·a*·보정 1)이어야 한다."""
    import repertoire_rules as rr

    def mean(x, m):
        return float(x[m].mean()) if m.any() else None
    if udef == "r3":
        if r3 is None or "threat_recency" not in geo["cols"]:
            raise ValueError("r3 니치 π 는 R3 스펙 관측 칸(repertoire_rules.r3_geo)과 판정 설정(eval_v3.r3_setup)이 필요하다")
        f = rr.features_of_obs(obs, geo)
        out = {}
        for u, (a, b) in rr.r3_u_terms(f, r3["theta"], r3["approach"], r3.get("cal", ())).items():
            x = rr.r3_u_prob(u, pi, f)
            out[f"pi_{u}_niche"], out[f"pi_{u}_base"] = mean(x, a), mean(x, b)
            out[f"n_{u}_niche"], out[f"n_{u}_base"] = int(a.sum()), int(b.sum())
        out["pi_freeze_max"] = float(pi[:, FREEZE].max()) if len(pi) else None
        out["pi_sleep_max"] = float(pi[:, SLEEP].max()) if len(pi) else None
        return out
    from eval_v3 import u_terms

    terms = u_terms(rr.features_of_obs(obs, geo), variant, udef)
    out = {}
    for name, x in (("flee", FLEE), ("hide", HIDE), ("freeze", FREEZE), ("sleep", SLEEP)):
        if name not in allowed:
            continue
        a, b = terms["esc" if name == "flee" else name]
        out[f"pi_{name}_niche"], out[f"pi_{name}_base"] = mean(pi[:, x], a), mean(pi[:, x], b)
    esc = pi[:, [FLEE, HIDE, FREEZE]].sum(1)
    a, b = terms["esc"]
    out["pi_esc_niche"], out["pi_esc_base"] = mean(esc, a), mean(esc, b)
    if xterms is not None and "freeze" in allowed:     # v3 R2: FREEZE 의 stare·look 니치(와 교차)
        xt = xterms(obs)
        if mask is not None and "look" in xt:
            from eval_v3 import look_open_terms

            xt["look_open"] = look_open_terms(xt["look"], mask)
        for name, (a, b) in xt.items():
            out[f"pi_{name}_niche"], out[f"pi_{name}_base"] = mean(pi[:, FREEZE], a), mean(pi[:, FREEZE], b)
            out[f"n_{name}_niche"], out[f"n_{name}_base"] = int(a.sum()), int(b.sum())
    return out


class RepLogCallback(BaseCallback):
    """1M 마다 체크포인트와 학습 기록(모듈 docstring). 스텝마다 VecEnv 의 `last_reads`(방금 스텝에서 요청을 읽은 개체)를 롤아웃
    버퍼 순서대로 모아, 기록 때 마지막 롤아웃의 결정 시점 표본으로 엔트로피·니치 확률을 잰다. 정책 분포만 읽어 학습에는 영향이
    없다(난수를 쓰지 않는다)."""

    def __init__(self, every: int, save_prefix: Path | None, log_path: Path | None, geo: dict, allowed,
                 variant: str = "near", udef: str = "r1", xterms=None, r3: dict | None = None):
        super().__init__()
        self.every = int(every)
        self._next_log = self.every
        self._next_save = self.every
        self.save_prefix, self.log_path = save_prefix, log_path
        self.geo, self.allowed, self.variant = geo, tuple(allowed), variant
        self.udef, self.xterms, self.r3 = udef, xterms, r3
        self.history: list[dict] = []
        self.saved: list[str] = []
        self._reads: list[np.ndarray] = []
        self._prev = None
        if log_path is not None:
            log_path.write_text("", encoding="utf-8")

    def _on_training_start(self) -> None:
        self._prev = self._snapshot()

    def _snapshot(self) -> dict:
        c = self.training_env.rep_counts
        return {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in c.items()}

    def _on_rollout_start(self) -> None:
        self._reads = []

    def _on_step(self) -> bool:
        self._reads.append(self.training_env.last_reads.copy())
        return True

    def _on_rollout_end(self) -> None:
        if self.num_timesteps >= self._next_log:
            self._log()
            while self._next_log <= self.num_timesteps:
                self._next_log += self.every
        while self.save_prefix is not None and self.num_timesteps >= self._next_save:
            path = self.save_prefix.with_name(f"{self.save_prefix.stem}_{self._next_save / 1e6:g}m.zip")
            self.model.save(path)
            self.saved.append(path.name)
            print(f"  체크포인트 {self._next_save:,} → {path.name} (실제 {self.num_timesteps:,})", flush=True)
            self._next_save += self.every

    def row(self) -> dict:
        """지금 기록 한 행(구간 수는 지난 기록 뒤부터)."""
        venv = self.training_env
        cur = self._snapshot()
        d = {k: cur[k] - self._prev[k] for k in cur}
        self._prev = cur
        n = max(int(d["agent_steps"]), 1)
        beh = np.asarray(d["beh"], dtype=np.float64)
        row = {"timesteps": int(self.num_timesteps)}
        row.update({f"use_{b}": float(beh[k] / max(beh.sum(), 1.0)) for k, b in enumerate(BEHAVIOR_NAMES)})
        row.update(decide_frac=d["decide"] / n, starve_rate=d["starved"] / n, pred_rate=d["caught"] / n)
        buf = self.model.rollout_buffer
        obs = buf.observations.reshape(buf.buffer_size, buf.n_envs, -1)
        reads = np.asarray(self._reads[-buf.buffer_size:])
        if reads.shape == obs.shape[:2] and reads.any():
            pobs = obs[reads]
            pi, _, ent = rep_distribution(self.model.policy, pobs)
            multi = pobs[:, venv.obs_dim:].sum(1) >= 2
            row.update(ent_dec=float(ent.mean()), ent_dec_multi=float(ent[multi].mean()) if multi.any() else None,
                       n_dec_samples=int(len(pobs)))
            row.update(niche_probs(pi, pobs[:, :venv.obs_dim], self.geo, self.allowed, self.variant, self.udef,
                                   self.xterms, pobs[:, venv.obs_dim:] > 0.5, self.r3))
            if ROUTE_PANIC_COL in venv.obs_names:
                # 10-22 두뇌 길(마스크 판 4): 결정 표본 가운데 도주 길 결정, 그 가운데 SHELTER 가 열린(두 칸) 결정의 π(SHELTER) 평균(ε 제외 — 시작 0.119)
                rt = pobs[:, list(venv.obs_names).index(ROUTE_PANIC_COL)] > 0.5
                two = rt & (pobs[:, venv.obs_dim + ROUTE_SLOT_SHELTER] > 0.5)
                row.update(n_route_dec=int(rt.sum()), n_route_choice=int(two.sum()),
                           pi_shelter_route=float(pi[two, ROUTE_SLOT_SHELTER].mean()) if two.any() else None)
        if "gate_flee" in d:
            # 10-23 반사 밖 두뇌 FLEE 막음(마스크 판 5·6): 구간의 덮기 밖 결정 수와 그 가운데 두뇌가 낸 FLEE 수(마스크 안 표본이라 늘 0)
            row.update(gate_free=int(d["gate_free"]), gate_flee=int(d["gate_flee"]))
        return row

    def _log(self) -> None:
        row = self.row()
        self.history.append(row)
        for k, v in row.items():
            if k != "timesteps" and isinstance(v, float):
                self.logger.record(f"rep/{k}", v)
        if self.log_path is not None:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        use = " ".join(f"{c}{row[f'use_{b}']:.3f}" for c, b in zip("GFHZS", BEHAVIOR_NAMES))   # 먹기·도망·숨기·얼기·잠
        print(f"  [{row['timesteps']:,}] 사용 {use} · 결정 {row['decide_frac']:.3f} · 결정 엔트로피 "
              f"{row.get('ent_dec', float('nan')):.3f} · 아사 {row['starve_rate']:.2e} · 피식 {row['pred_rate']:.2e}"
              + (f" · 길 결정 {row['n_route_dec']} (두 칸 {row['n_route_choice']}, π SHELTER "
                 + (f"{row['pi_shelter_route']:.3f}" if row["pi_shelter_route"] is not None else "—") + ")" if "n_route_dec" in row else "")
              + (f" · 반사 밖 두뇌 FLEE {row['gate_flee']} / 덮기 밖 결정 {row['gate_free']:,}" if "gate_flee" in row else ""),
              flush=True)


def init_policy_report(model, venv: MultiWorldVecEnv) -> dict:
    """학습 전 정책의 시작 분포: 로짓 편향과 지금 세계들 관측의 결정 시점 평균 π(ε 제외, 마스크 적용). 세계를 바꾸지 않는다."""
    pobs = np.concatenate([np.concatenate([w.observe(), venv.current_masks()[k * venv.N:(k + 1) * venv.N]
                                           .astype(np.float32)], 1) for k, w in enumerate(venv.worlds)])
    pi, pi_eps, ent = rep_distribution(model.policy, pobs)
    dec = venv._reads.copy()
    out = {"action_bias": model.policy.action_net.bias.detach().cpu().numpy().astype(float).tolist(),
           "n_dec": int(dec.sum())}
    if dec.any():
        out.update(pi_dec=pi[dec].mean(0).tolist(), pi_eps_dec=pi_eps[dec].mean(0).tolist(),
                   ent_dec=float(ent[dec].mean()))
    return out


def measure_fdec(cfg, seeds=FDEC_SEEDS, steps: int = FDEC_STEPS, model_seed: int = 0) -> dict:
    """시작 정책으로 결정 비율 f_dec 를 잰다(모듈 docstring 'f_dec 측정'). 반환: f_dec(요청을 읽은 개체-스텝 비율), 시드별 값,
    결정 시점 중 마스크가 두 칸 이상인 비율, World.repertoire_stats decide_frac(같은 값이어야 한다 — 마스크 판 4 세계도 덮기 스텝을 빼고 길 결정을
    더한 같은 셈이다)."""
    from env_v2.vec_env import region_configs, region_mix_params
    from env_v2.world import World

    rep = rep_params(cfg)
    if rep is None:
        raise SystemExit("설정에 train.repertoire 블록이 없다")
    venv = MultiWorldVecEnv(cfg, num_worlds=1, meta_seed=model_seed)       # 정책 공간·초기화용(학습과 같은 seed)
    model = make_model_rep(venv, rep, None, seed=model_seed)
    pol = model.policy
    pol.set_training_mode(False)
    # v3 R4 지역 섞기(train.region_mix, env_v2/vec_env.py): 시드마다 지역 모두를 한 번씩(같은 표본 잡음 스트림). 블록이 없으면 설정 그대로 한 번 — 지금과 같다
    rm = region_mix_params(cfg.v2.get("train", {}).get("region_mix"), cfg)
    cfgs = [(None, cfg)] if rm is None else list(region_configs(cfg, rm).items())
    per = []
    reads_n = multi_n = total = 0
    route_n = route_two = 0             # 10-22 두뇌 길(마스크 판 4·5)만: 도주 길 결정, 그 가운데 SHELTER 가 열린 결정
    gate_free = gate_flee = 0           # 10-23 반사 밖 FLEE 막음(판 5·6)만: 덮기 밖 결정, 그 가운데 두뇌가 낸 FLEE(마스크 안 표본이라 늘 0)
    for s in seeds:
        for region, c in cfgs:
            w = World(c, seeds=[int(s)])
            rng = np.random.default_rng([int(s), FDEC_TAG])
            r_s = 0
            for _ in range(steps):
                obs = w.observe()
                pk = w.rep_peek()
                m = action_mask(pk, obs, rep, obs_names=w.obs_names)
                _, pi_eps, _ = rep_distribution(pol, policy_obs(obs, m))
                a = sample_masked(pi_eps, m, rng.random(w.N))
                r_s += int(pk["reads"].sum())
                multi_n += int((m[pk["reads"]].sum(1) >= 2).sum())
                if "route_decide" in pk:
                    route_n += int(pk["route_decide"].sum())
                    route_two += int((pk["route_decide"] & m[:, ROUTE_SLOT_SHELTER]).sum())
                w.step(a.astype(np.float64)[:, None])
            n = steps * w.N
            row = dict(seed=int(s), f_dec=r_s / n, decide_frac_world=w.repertoire_stats()["decide_frac"])
            if w._fb:
                g = w.flee_gate_stats()
                row.update(gate_free=g["free_decisions"], gate_flee=g["brain_flee"])
                gate_free += g["free_decisions"]
                gate_flee += g["brain_flee"]
            if region is not None:
                row["region"] = region
            per.append(row)
            reads_n += r_s
            total += n
    out = dict(f_dec=reads_n / total, per_seed=per, multi_frac=multi_n / max(reads_n, 1), seeds=[int(s) for s in seeds],
               steps=int(steps), model_seed=int(model_seed), allowed=list(rep["allowed"]))
    mver = world_mask_version(venv.worlds[0])
    out["mask_version"] = int(mver)
    if mver in ROUTE_MASK_VERSIONS:
        out.update(route_decisions=route_n, route_choice=route_two, route_dec_frac=route_n / total)
    if flee_gated(mver):
        out.update(gate_free=gate_free, gate_flee=gate_flee)
    return out


def measure_pi(cfg, model_path, seeds=FDEC_SEEDS, steps: int = FDEC_STEPS, udef: str = "auto",
               variant: str = "near", r3: dict | None = None) -> dict:
    """저장한 모델의 결정 시점 니치 π(ε 제외)를 보정 시드에서 잰다(모듈 docstring '니치 π 측정'). 세계는 모델의 argmax 로 돌린다
    (판정 롤아웃과 같은 궤적, 난수 없음). 반환: 시드 합친 `niche_probs` 칸(`pooled`)과 시드별 칸, 결정 표본 수. r3 는 `r3`(주지 않으면
    eval_v3.r3_setup — 관문 결과)의 손 규칙 문턱을 쓰고, 조기 중단 칸을 관문 결과대로 나눈다(`r3_early_split`)."""
    from stable_baselines3 import PPO

    import repertoire_rules as rr
    from env_v2.rep_policy import check_mask_version, rep_argmax
    from env_v2.world import World

    from env_v2.rep_policy import allowed_mask_of, effective_allowed

    model = PPO.load(str(model_path), device="cpu")
    pol = model.policy
    pol.set_training_mode(False)
    # 허용 = 모델 목록 ∩ 설정 목록(판정 롤아웃 rep_learned 와 같다 — v3 R3 세계에서는 R1b 의 FREEZE 가 막힌다)
    allowed = effective_allowed(pol.rep_allowed, cfg)
    params = {"allowed_mask": allowed_mask_of(allowed)}
    if udef == "auto":
        udef = auto_udef(tuple(pol.rep_obs_names), cfg)
    if udef == "r3" and r3 is None:
        from eval_v3 import r3_setup

        r3 = r3_setup()
    geo = rr.r3_geo(cfg) if udef == "r3" else rr._geom(cfg)
    xterms = None
    per, P, O, M = [], [], [], []
    for s in seeds:
        w = World(cfg, seeds=[int(s)])
        check_mask_version(getattr(pol, "rep_mask_version", 1), w.obs_names, w.brain_flee_outside_reflex)
        if tuple(w.obs_names) != tuple(pol.rep_obs_names):
            raise ValueError(f"모델의 관측 {list(pol.rep_obs_names)} 이 세계의 관측 {list(w.obs_names)} 과 다르다")
        if udef == "auto":
            udef = auto_udef(w.obs_names)
        if udef == "r2" and xterms is None:
            from eval_v3 import XTerms

            xterms = XTerms(cfg)
        ps, os_, ms = [], [], []
        for _ in range(steps):
            obs = w.observe()
            pk = w.rep_peek()
            m = action_mask(pk, obs, params, obs_names=w.obs_names)
            pobs = policy_obs(obs, m)
            dec = np.asarray(pk["reads"], dtype=bool)
            if dec.any():
                pi, _, _ = rep_distribution(pol, pobs[dec])
                ps.append(pi)
                os_.append(obs[dec])
                ms.append(m[dec])
            w.step(rep_argmax(pol, pobs).astype(np.float64)[:, None])
        ps, os_, ms = np.concatenate(ps), np.concatenate(os_), np.concatenate(ms)
        per.append(dict(seed=int(s), n_dec=int(len(ps)),
                        **niche_probs(ps, os_, geo, allowed, variant, udef, xterms, ms, r3)))
        P.append(ps)
        O.append(os_)
        M.append(ms)
    P, O, M = np.concatenate(P), np.concatenate(O), np.concatenate(M)
    pooled = niche_probs(P, O, geo, allowed, variant, udef, xterms, M, r3)
    out = dict(model=str(model_path), seeds=[int(s) for s in seeds], steps=int(steps), u_def=udef, freeze_variant=variant,
               allowed=list(allowed), n_dec=int(len(P)), pooled=pooled, per_seed=per)
    if udef == "r2":                # 조기 중단 칸과 보고만 칸을 따로 적는다(R2_EARLY_PI 주석)
        out["early_stop_pi"] = {k: pooled.get(k) for k in R2_EARLY_PI}
        out["report_only_pi"] = {k: pooled[k] for k in R2_REPORT_PI if k in pooled}
    if udef == "r3":                # 관문 결과로 나눈 조기 중단 칸(14절), 허용 목록 점검(즉시 멈춤)
        use, rep_ = r3_early_split(r3)
        out["r3"] = r3
        out["early_stop_pi"] = {g: pooled.get(R3_EARLY_PI[g]) for g in use}
        out["report_only_pi"] = {g: pooled.get(R3_EARLY_PI[g]) for g in rep_}
        out["early_stop_pending"] = not r3.get("gate_complete")
        out["freeze_or_sleep_open"] = bool((pooled.get("pi_freeze_max") or 0.0) > 0.0
                                           or (not r3.get("sleep") and (pooled.get("pi_sleep_max") or 0.0) > 0.0))
    return out


def init_from_model(model, path, source: str) -> dict:
    """H13 대응 1회(모듈 docstring 'v3 R3'): SB3 모델 `path` 의 정책·가치망 state_dict 를 `model` 에 strict 로 싣고 출처 기록을 돌려준다.
    출처 글이 비었거나, RepertoirePolicy 모델이 아니거나, 관측 이름·마스크 판이 다르면 멈춘다(출처 확인을 조용히 건너뛰지 않는다)."""
    import hashlib

    from stable_baselines3 import PPO

    from env_v2.rep_policy import is_rep_file

    if not str(source or "").strip():
        raise SystemExit("--init-source 는 비울 수 없다(어느 학습·세계·목록의 가중치인지 적는다, 13-5)")
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"--init-from-model {p} 가 없다")
    if not is_rep_file(p):
        raise SystemExit(f"--init-from-model {p} 는 행동 고르기 정책(RepertoirePolicy) 모델이 아니다")
    src = PPO.load(str(p), device="cpu").policy
    dst = model.policy
    if tuple(src.rep_obs_names) != tuple(dst.rep_obs_names):
        raise SystemExit(f"실을 모델의 관측 {list(src.rep_obs_names)} 이 이 설정의 관측 {list(dst.rep_obs_names)} 과 다르다")
    if int(getattr(src, "rep_mask_version", 1)) != int(dst.rep_mask_version):
        raise SystemExit(f"실을 모델의 마스크 판 {getattr(src, 'rep_mask_version', 1)} 이 이 설정의 판 {dst.rep_mask_version} 과 다르다")
    dst.load_state_dict(src.state_dict(), strict=True)
    return dict(path=str(p), sha1=hashlib.sha1(p.read_bytes()).hexdigest()[:12], source=str(source).strip(),
                model_allowed=list(src.rep_allowed), allowed=list(dst.rep_allowed), mask_version=int(dst.rep_mask_version),
                obs_names=list(dst.rep_obs_names))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = "train"
    if argv and argv[0] in ("train", "measure-fdec", "measure-pi"):
        cmd = argv.pop(0)
    p = argparse.ArgumentParser(description="v3 R1 행동 고르기 PPO 학습 (다중 세계, 이산 행동)")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--threads", type=int, default=1, help="torch 스레드 수 (S1-a·v2.4s 학습은 1)")
    if cmd == "measure-fdec":
        p.add_argument("--seeds", type=int, nargs="+", default=list(FDEC_SEEDS))
        p.add_argument("--steps", type=int, default=FDEC_STEPS)
        p.add_argument("--model-seed", type=int, default=0)
        args = p.parse_args(argv)
        import r3_tools as rt

        hit = [s for s in args.seeds if s in rt.GATE_JUDGE or s in rt.FINAL_JUDGE]
        if hit:
            raise SystemExit(f"measure-fdec 는 R3 관문·최종 판정 시드 {hit} 를 쓰지 않는다(보정 시드 20000~20002)")
        torch.set_num_threads(args.threads)
        t0 = time.time()
        res = measure_fdec(load_v2_config(args.config), args.seeds, args.steps, args.model_seed)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        print(f"f_dec = {res['f_dec']:.6f} (보정 시드 {res['seeds']} × {res['steps']}스텝, 목록 {res['allowed']}, "
              f"{time.time() - t0:.0f}초) → yaml train.repertoire.f_dec 에 적는다")
        return 0
    if cmd == "measure-pi":
        p.add_argument("--model", required=True, help="저장한 모델 .zip (체크포인트 또는 모방 초기화 직후)")
        p.add_argument("--seeds", type=int, nargs="+", default=list(FDEC_SEEDS))
        p.add_argument("--steps", type=int, default=FDEC_STEPS)
        p.add_argument("--u-def", choices=("auto", "r1", "r1b", "r2", "r3"), default="auto")
        p.add_argument("--freeze-variant", choices=("near", "orig"), default="near")
        p.add_argument("--out", default=None, help="결과 JSON 경로(없으면 화면에만)")
        args = p.parse_args(argv)
        torch.set_num_threads(args.threads)
        t0 = time.time()
        import r3_tools as rt

        bad = rt.seed_problems(args.seeds)
        if bad:
            raise SystemExit("measure-pi 는 관문·최종 판정 시드를 쓰지 않는다: " + ", ".join(bad))
        res = measure_pi(load_v2_config(args.config), args.model, args.seeds, args.steps, args.u_def, args.freeze_variant)
        res.update(config=str(args.config), elapsed_s=round(time.time() - t0, 1),
                   generated=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        text = json.dumps(res, ensure_ascii=False, indent=1)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
        pooled = res["pooled"]
        print(text if not args.out else f"저장: {args.out}")
        print("니치 π(ε 제외, 보정 시드 합침): " + " · ".join(
            f"{k[3:-6]} {pooled[k]:.4f}" for k in pooled if k.startswith("pi_") and k.endswith("_niche")
            and pooled[k] is not None), flush=True)
        if res.get("u_def") == "r3":
            print("R3 조기 중단 칸(관문 사전 등록 14절" + (", 관문 전 — 미정" if res["early_stop_pending"] else "") + "): "
                  + (" · ".join(f"{g} {v:.4f}" if v is not None else f"{g} —" for g, v in res["early_stop_pi"].items()) or "—")
                  + " / 보고만: " + (" · ".join(f"{g} {v:.4f}" for g, v in res["report_only_pi"].items() if v is not None) or "—")
                  + (" / 허용 목록 결함: FREEZE·SLEEP 확률이 0 이 아니다 — 학습을 멈추고 고친다" if res["freeze_or_sleep_open"] else ""),
                  flush=True)
        elif "early_stop_pi" in res:
            print("R2 조기 중단 칸(판정 사전 등록 2절): " + " · ".join(
                f"{k[3:-6]} {v:.4f}" if v is not None else f"{k[3:-6]} —" for k, v in res["early_stop_pi"].items())
                + " / 보고만: " + (" · ".join(f"{k[3:-6]} {v:.4f}" for k, v in res["report_only_pi"].items() if v is not None)
                                  or "—"), flush=True)
        return 0
    p.add_argument("--steps", type=int, default=20_000_000)
    p.add_argument("--seed", type=int, default=0, help="모델(PPO) 시드이자 세계 선택 시드(meta_seed)")
    p.add_argument("--run-name", default=None, help="기본 v<설정 version>_<γ>_s<seed>_<M>m (예: v3_r1_g995_s0_20m)")
    p.add_argument("--out", default=None, help="기본 ckpt/v3/<run-name>.zip")
    p.add_argument("--ppo-config", default=str(ROOT / "configs" / "ppo_best.yaml"))
    p.add_argument("--gamma", type=float, default=None, help=f"할인율 γ. 기본 {S1A_GAMMA}(S1-a 조리법)")
    p.add_argument("--every", type=int, default=EVERY, help="체크포인트·학습 기록 간격(스텝). 기본 1M")
    p.add_argument("--freeze-variant", choices=("near", "orig"), default="near",
                   help="학습 기록의 FREEZE 니치 조건 판(eval_v3.u_terms). FREEZE 가 목록에 없으면 쓰이지 않는다")
    p.add_argument("--u-def", choices=("auto", "r1", "r1b", "r2"), default="auto",
                   help="학습 기록의 니치 정의(eval_v3 지표 묶음). auto = 경보 세계(마스크 판 3)면 r2, 아니면 r1")
    p.add_argument("--tb", default=str(ROOT / "runs" / "v3"))
    p.add_argument("--warmstart", default=None,
                   help="모방 초기화 가중치(warmstart_v3.py fit 의 .pt). 주면 PPO 시작 정책·가치망을 이것으로 바꾼다. 곁 파일 "
                        "<.pt 이름>.json 의 world_digest 가 이 설정과 다르면 멈춘다(warmstart_v3.check_source)")
    p.add_argument("--allow-legacy-warmstart", action="store_true",
                   help="출처 표시(world_digest)가 없는 10-13 전 가중치를 R2 세계에서도 싣는다(두 장치 실행의 재현용)")
    p.add_argument("--init-from-model", default=None,
                   help="v3 R3 대응 1회(H13): 이 SB3 모델(.zip)의 정책·가치망을 strict 로 싣고 시작한다(--init-source 가 꼭 필요하다)")
    p.add_argument("--init-source", default=None, help="--init-from-model 의 출처(어느 학습·세계·목록인지). 곁 파일·학습 메타에 남는다")
    p.add_argument("--init-tag", default="r1b", help="--init-from-model 이고 --run-name 이 없을 때 실행 이름에 붙는 조각(기본 r1b)")
    args = p.parse_args(argv)
    if args.init_from_model and args.warmstart:
        raise SystemExit("--init-from-model 과 --warmstart 는 함께 쓰지 않는다(시작 가중치는 하나다)")
    if args.init_source and not args.init_from_model:
        raise SystemExit("--init-source 는 --init-from-model 과 함께 준다")

    torch.set_num_threads(args.threads)
    cfg = load_v2_config(args.config)
    rep = rep_params(cfg)
    if rep is None:
        raise SystemExit(f"{args.config} 에 train.repertoire 블록이 없다(이산 행동 학습 설정이 아니다)")
    ws_digest = None
    if args.warmstart:
        # 출처 확인(warmstart_v3 모듈 docstring '출처 확인'): 다른 세계에서 맞춘 가중치나, R2 세계에서 10-13 전(두 장치 세계) 가중치를
        # 조용히 싣지 않는다. 학습을 만들기 전에 멈춘다
        from warmstart_v3 import check_source

        if not Path(args.warmstart).exists():
            raise SystemExit(f"모방 초기화 가중치 {args.warmstart} 가 없다")
        ws_digest = check_source(cfg, Path(args.warmstart).with_suffix(".json"), "모방 초기화 가중치",
                                 args.allow_legacy_warmstart)
    from diagnose_v2 import config_digest       # 진단 결과 meta 와 같은 식(설정 dict 의 sha1 앞 12자리)

    import repertoire_rules as rr

    digest = config_digest(cfg)
    venv = MultiWorldVecEnv(cfg, meta_seed=args.seed)
    rollout_world_steps = int(cfg.v2["train"].get("rollout_world_steps", 256))
    n_steps = max(1, rollout_world_steps // venv.K)
    tuned, gamma, gamma_source = resolve_gamma(load_tuned(args.ppo_config),
                                               args.gamma if args.gamma is not None else S1A_GAMMA)
    gamma_source = "cli" if args.gamma is not None else "s1a"
    tuned, lr_schedule = apply_lr_schedule(tuned, "constant")
    run = args.run_name or default_run_name(cfg, args.seed, args.steps, gamma, args.init_tag if args.init_from_model else "")
    out = Path(args.out) if args.out else CKPT / f"{run}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    model = make_model_rep(venv, rep, tensorboard_log=args.tb, n_steps=n_steps, seed=args.seed, **tuned)
    if float(model.gamma) != gamma or float(model.rollout_buffer.gamma) != gamma:
        raise RuntimeError(f"모델 γ {model.gamma} (버퍼 {model.rollout_buffer.gamma}) 가 지정한 γ {gamma} 와 다르다")
    if args.warmstart:
        # 모방 초기화(results/v3/r1/PREREG.md 변경 기록 10-07 '대응: 모방 초기화'): 정책·가치망 가중치만 바꾼다. 구조·분포 인자
        # (ε, 엔트로피 배율, 허용 목록)는 이 설정의 값 그대로다 — 가중치 파일에는 state_dict 만 있다
        state = torch.load(args.warmstart, map_location="cpu")["policy"]
        model.policy.load_state_dict(state, strict=True)
        print(f"모방 초기화 가중치: {args.warmstart}", flush=True)
    init_rec = None
    if args.init_from_model:
        # v3 R3 대응 1회(H13, 관문 사전 등록 13-5): 출처를 밝혀 싣고, 학습 전에 곁 파일을 남긴다
        init_rec = init_from_model(model, args.init_from_model, args.init_source)
        init_rec.update(config=str(args.config), config_digest=digest, run=run,
                        generated=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        out.with_suffix(".init.json").write_text(json.dumps(init_rec, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"시작 가중치(출처: {init_rec['source']}): {args.init_from_model} (sha1 {init_rec['sha1']}, 원래 목록 "
              f"{init_rec['model_allowed']} → 이 설정의 목록 {init_rec['allowed']})", flush=True)
    ent_scale = float(model.policy.rep_ent_scale)
    cat_ent = float(model.ent_coef) * ent_scale
    if not math.isclose(cat_ent, rep["cat_ent_coef"], rel_tol=1e-12):
        raise RuntimeError(f"범주 엔트로피 계수 {cat_ent} 가 설정 값 {rep['cat_ent_coef']} 와 다르다")
    init_rep = init_policy_report(model, venv)
    print(f"행동 고르기 학습: 목록 {list(rep['allowed'])}, ε {rep['epsilon']}, 시작 확률 {rep['init_probs']}, "
          f"엔트로피 기준 {rep['ent_coef_base']} ÷ f_dec {rep['f_dec']} = {rep['cat_ent_coef']:.6g} "
          f"(PPO ent_coef {model.ent_coef} × 배율 {ent_scale:.6g})", flush=True)
    if "pi_dec" in init_rep:
        print("시작 분포(결정 시점 평균 π, 마스크 적용): "
              + " · ".join(f"{b} {x:.3f}" for b, x in zip(BEHAVIOR_NAMES, init_rep["pi_dec"])), flush=True)
    print(f"{args.steps:,} 스텝 — 세계 {venv.K}개 × {venv.N}슬롯 = num_envs {venv.num_envs}, 세계당 n_steps {n_steps} "
          f"(배치 {n_steps * venv.num_envs:,}), 교체 {venv.T}스텝마다, γ {gamma} ({gamma_source}), "
          f"관측 {venv.obs_dim} + 마스크 {N_BEHAVIORS}(마스크 판 {model.policy.rep_mask_version}), 행동 Discrete({N_BEHAVIORS})",
          flush=True)
    udef = auto_udef(venv.obs_names, cfg) if args.u_def == "auto" else args.u_def
    xterms = None
    if udef == "r2":
        from eval_v3 import XTerms

        xterms = XTerms(cfg)
    r3s = None
    if udef == "r3":
        from eval_v3 import r3_setup

        r3s = r3_setup()
    print(f"학습 기록 니치 정의: {udef}" + (f" (+ {', '.join(xterms.rules)} 니치)" if xterms is not None else "")
          + (f" (θ {r3s['theta']:g}, a* {r3s['approach']:g}, 보정 1 {r3s['cal'] or '없음'}, 관문 결과 "
             f"{'있음' if r3s['gate_complete'] else '없음 — 재학습 전 측정 값'})" if r3s is not None else ""), flush=True)
    cb = RepLogCallback(args.every, out, out.with_suffix(".log.jsonl"), rr.r3_geo(cfg) if udef == "r3" else rr._geom(cfg),
                        rep["allowed"], args.freeze_variant, udef, xterms, r3s)
    t0 = time.time()
    model.learn(total_timesteps=args.steps, callback=cb, tb_log_name=run, reset_num_timesteps=True, progress_bar=False)
    elapsed = time.time() - t0
    model.save(out)
    print(f"저장: {out}  ({elapsed / 60:.1f}분, {model.num_timesteps / max(elapsed, 1e-9):,.0f} 스텝/초)")

    meta = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": " ".join([Path(sys.executable).name, Path(__file__).name, cmd] + [str(a) for a in argv]),
        "python": platform.python_version(),
        "steps": args.steps, "actual_timesteps": int(model.num_timesteps), "seed": args.seed,
        "elapsed_min": round(elapsed / 60, 2), "steps_per_sec": round(model.num_timesteps / max(elapsed, 1e-9), 1),
        "gamma": float(model.gamma), "gamma_source": gamma_source, "ent_coef": float(model.ent_coef),
        "rep_ent_scale": ent_scale, "cat_ent_coef": cat_ent, "config_digest": digest, "config": str(args.config),
        "ppo_config": args.ppo_config,
        "ppo": {k: (float(v) if isinstance(v, (int, float)) else str(v)) for k, v in {
            "n_steps": n_steps, "batch_size": model.batch_size, "n_epochs": model.n_epochs, "gamma": model.gamma,
            "gae_lambda": model.gae_lambda, "ent_coef": model.ent_coef,
            "learning_rate": tuned.get("learning_rate", "default"), "clip_range": tuned.get("clip_range", "default"),
            "lr_schedule": lr_schedule}.items()},
        "repertoire": {k: (v.tolist() if isinstance(v, np.ndarray) else (list(v) if isinstance(v, tuple) else v))
                       for k, v in rep.items()},
        "v2": cfg.v2, "num_worlds": venv.K, "reset_interval": venv.T,
        "worlds_seen": sum(len(h) for h in venv.seed_history), "world_resets": venv.num_resets,
        "obs_names": list(venv.obs_names), "behavior_names": list(BEHAVIOR_NAMES), "freeze_variant": args.freeze_variant,
        "u_def": udef, "mask_version": int(model.policy.rep_mask_version),
        "init_policy": init_rep, "checkpoints": cb.saved, "log_history": cb.history, "warmstart": args.warmstart,
        "warmstart_world_digest": ws_digest, "init_from_model": init_rec, "r3_setup": r3s,
    }
    if venv.region_history is not None:     # v3 R4 지역 섞기: 세계마다 고른 지역 차례(seed_history 와 같은 순서)
        meta["region_history"] = venv.region_history
        meta["seed_history"] = venv.seed_history
    if getattr(venv, "forest_history", None) is not None:     # v3 R5 무작위 숲 섞기: 세계마다 꼴('unreal' / 'rand u=… brush=… n=…')
        meta["forest_history"] = venv.forest_history
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"config_digest {digest}, 체크포인트 {len(cb.saved)}개, 학습한 세계 수 {meta['worlds_seen']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
