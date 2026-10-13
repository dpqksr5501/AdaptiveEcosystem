"""v3 R1 모방 초기화 — FSM 손 규칙을 흉내 내도록 RepertoirePolicy 를 지도학습으로 먼저 맞춘다 (results/v3/r1/PREREG.md 변경 기록
10-07 '대응: 모방 초기화', 계획서 #10 '모방 초기화는 학습 실패 대응 (d)').

    python warmstart_v3.py collect                     # 교사 자료 모으기(한 번, 모델 시드와 무관)
    python warmstart_v3.py fit --seeds 0 1 2 3 4 5     # 모델 시드마다 맞추기 → ckpt/v3/ws/<이름>_s<시드>.pt(.zip)

교사 둘 = R_base(θ 4, a 0.9 — 먹다가 가까우면 도망, 무리 전체 성과가 가장 높은 손 규칙)와 FSM(eval_v3.fsm_spec: R_base + 목록
행동의 니치 규칙, 숨기 > 얼기 > R_base, 얼기는 가까운 위협 판 — 이 우선순위에서는 도망을 고르지 않는다). 어느 쪽이 나은지는
정하지 않고 '이 상황의 후보 행동'만 알려 주려고 둘을 섞는다. 학습 세계 설정(configs/v3_r1.yaml)에서 학습 세계 시드 풀
(cfg.train_seeds)의 세계를 고정 난수(COLLECT_TAG)로 골라, 짝수 번째 세계는 R_base, 홀수 번째는 FSM 이 움직이게 돌린다(세계에는
그 교사의 요청을 그대로 넣는다 — 판정 롤아웃과 같은 궤적). 표본마다 두 교사의 선택을 모두 적는다.

정책 표본 = 결정 시점(rep_peek 의 reads)이고 마스크가 두 칸 이상이며 두 교사 요청이 모두 마스크 안인 개체-스텝. 목표 분포는
(1 − s)/2·onehot(R_base) + (1 − s)/2·onehot(FSM) + s·m/|m| (s = SMOOTH) — 두 교사가 같으면 그 행동이 1 − s + s/|m|. 손실은
마스크 로그 확률(ε 제외 π)의 교차 엔트로피다.
가치 표본 = 모든 개체-스텝 중 VALUE_EVERY 마다 하나, 목표 = 학습 γ(0.995)의 할인 수익(사망·리스폰에서 끊는다). 롤아웃 끝의
꼬리는 잘라 버린다(마지막 VALUE_DROP 스텝 — 0.995^1000 ≈ 0.0067). 가치망을 같이 맞춰야 PPO 첫 갱신의 이점이 잡음이 되지 않는다.

맞춘 정책은 train_v3.py --warmstart <.pt> 가 PPO 시작 가중치로 싣는다. .zip 은 같은 가중치의 SB3 모델이라 eval_v3 로 바로 잴 수
있다(맞춘 직후의 성능 기록용).

v3 R2 (명세 RL_V3_R2_SPEC.md 10절 6단계 — R1 과 같은 조리법, 목표 0.45·R_base + 0.45·FSM_R2 + 0.1·마스크 균등):

    python warmstart_v3.py collect --config configs/v3_r2.yaml --teacher2 fsm_r2 --out-dir ckpt/v3/ws_r2
    python warmstart_v3.py fit --config configs/v3_r2.yaml --out-dir ckpt/v3/ws_r2 --name v3_r2_ws --seeds 0 1 2 3 4 5

- `--teacher2` 가 둘째 교사를 고른다: fsm(R1 그대로 — eval_v3.fsm_spec near 판) 또는 fsm_r2(eval_v3.fsm_r2_policy_spec =
  repertoire_rules.fsm_r2_spec, 켠 장치의 줄). 기본은 설정을 보고 정한다: 경보(또는 재현 설정의 노려보기)를 켠 R2 세계면 fsm_r2,
  아니면 fsm(R1 재현). `--out-dir` 기본도 R2 세계면 ckpt/v3/ws_r2(R1 의 ckpt/v3/ws 를 덮지 않는다), fit `--name` 기본은
  v<version>_ws 다. 두 교사 모두 R_base(θ 4, a 0.9)를 쓴다(사람 결정 10-12 밤 — 교사·판정 대조는 R1 과 같은 (4, 0.9)). 교사 세계
  시드는 R1 과 같은 규칙(학습 시드 풀에서 고정 난수 808)이다.
- R2 세계(v3_r1 + 경보, 사람 결정 10-13 — 노려보기는 뺐다)의 FSM_R2 교사 = R_base(4, 0.9) + look + R0 HIDE 니치 + R0 가까운 위협
  얼기(우선순위 HIDE > 가까운 얼기 > look > R_base, stare 줄 없음). 10-12 에 모은 자료·가중치는 노려보기를 함께 켠 세계에서
  stare 줄이 든 FSM_R2 로 모은 것이라 R2 학습에 쓰지 않는다 — 10-13 에 ckpt/v3/ws_r2_both 로 옮겼고, 기본 폴더에는 다시 모은다
  (아래 '출처 확인').
- fsm_r2 교사의 FREEZE 는 어느 줄에서 왔는지 표본마다 적는다(`p_src2`: 0 = FREEZE 아님, 1 = 가까운 위협 얼기(freeze cross),
  2 = stare 띠, 3 = stare 유지 줄만, 4 = look — 우선순위 가까운 판 > stare > look 그대로). R2 세계에는 stare 줄이 없어 2·3 은 늘 0 이다
  (자료 꼴은 그대로 둔다). 교사 수(`counts_fsm`, `freeze_src_fsm`, 세계를 움직인 교사별 `counts_by_driver`)와 맞춘 뒤 보류 표본의
  줄별 평균 π(FREEZE)(`recall_src`)를 보고한다. R1 자료(p_src2 없음)는 그대로 읽는다.
- `--out-dir` 가 교사 자료(`<out-dir>/teacher_mix.npz`, 기본 --data)와 맞춘 가중치(`<out-dir>/<name>_s<시드>.pt·.zip·.json`)의
  폴더다. 기본은 R1 의 ckpt/v3/ws.

출처 확인 (10-13 검토 — 옛 R2 자료를 조용히 다시 쓰지 않게):
- collect 는 곁 파일 teacher_mix.json 에, fit 은 <name>_s<시드>.json 에 이 설정의 `world_digest`(세계 동역학 + 허용 목록, `world_digest`
  docstring)와 전체 `config_digest` 를 적는다. fit 은 자료의 world_digest 가 이 설정과 다르면 멈추고, train_v3.py --warmstart 는
  가중치의 world_digest 가 학습 설정과 다르면 멈춘다(`check_source`).
- world_digest 가 없는 자료·가중치(10-13 전 판)는 R1 세계면 알리고 쓰고(R1 재현), 경보를 켠 R2 세계면 멈춘다 — 10-13 전의 R2
  자료·가중치는 모두 두 장치 세계의 것이다(10-13 에 ckpt/v3/ws_r2 → ckpt/v3/ws_r2_both 로 옮겼다). 그 실행의 재현이면
  fit --allow-legacy(train_v3 는 --allow-legacy-warmstart).
- collect 는 있는 teacher_mix.npz·.json 을, fit 은 있는 <name>_s<시드>.pt·.zip·.json 을 덮지 않는다(덮으려면 --force). ckpt/ 는
  저장소 밖(.gitignore)이라 덮으면 되살릴 수 없다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch as th

from env_v2.config import load_v2_config
from env_v2.rep_policy import N_BEHAVIORS, action_mask, policy_obs, rep_params
from env_v2.vec_env import MultiWorldVecEnv

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "ckpt" / "v3" / "ws"
OUT_R2 = ROOT / "ckpt" / "v3" / "ws_r2"     # v3 R2 세계(v3_r1 + 경보)의 기본 폴더
CONFIG = ROOT / "configs" / "v3_r1.yaml"
COLLECT_TAG = 808          # 교사 세계 고르기 난수 스트림(지연 505·C1′ 606·f_dec 707 과 겹치지 않는다)
N_WORLDS = 24              # 교사 세계 수
STEPS = 3000               # 세계마다 스텝
SMOOTH = 0.1               # 목표 분포의 균등 혼합
VALUE_EVERY = 4            # 가치 표본: 개체-스텝 4개 중 하나
VALUE_DROP = 1000          # 가치 목표에서 버리는 롤아웃 끝 스텝 수
EPOCHS = 12
BATCH = 4096
LR = 1e-3
VALUE_COEF = 0.5
GAMMA_TRAIN = 0.995        # S1-a 학습 γ


TEACHERS2 = ("fsm", "fsm_r2")
# fsm_r2 교사 FREEZE 의 출처(p_src2 값 → 이름, 모듈 docstring 'v3 R2')
SRC_NAMES = {1: "near", 2: "stare_band", 3: "stare_hold", 4: "look"}


class FreezeSource:
    """FSM_R2 의 FREEZE 가 어느 줄에서 왔는지(SRC_NAMES). 줄마다 손 규칙 마스크(repertoire_rules.XRule.mask, x_wrap 스펙)를 다시
    재고 FSM_R2 우선순위(가까운 위협 얼기 > stare > look)대로 고른다. stare 띠/유지 줄은 같은 스펙에서 beh_freeze 칸을 뺀 판으로
    가른다(eval_v3.XTerms 와 같은 방식). stare 줄은 FSM_R2 와 같이 노려보기를 켠 재현 설정에서만 본다 — R2 세계에서는 출처가
    가까운 판·look 뿐이다. 상태가 없다."""

    def __init__(self, cfg):
        import repertoire_rules as rr
        from eval_v3 import XTerms

        geo = rr._geom(cfg)
        self.near = rr.XRule(None, rr.x_wrap(cfg, "freeze", "cross", geo=geo))
        self.xt = XTerms(cfg)

    def __call__(self, obs, base_req, req2) -> np.ndarray:
        """관측·R_base 요청·FSM_R2 요청 → (n,) int8 출처(0 = FREEZE 아님)."""
        from env_v2.repertoire import FREEZE

        x = self.xt(obs)
        near = self.near.mask(obs, base_req)
        none = np.zeros(len(obs), dtype=bool)
        band = x["stare_band"][0] if "stare_band" in x else none        # 노려보기 재현 설정에서만(eval_v3.XTerms)
        stare = x["stare"][0] if "stare" in x else none
        look = x["look"][0] if "look" in x else none
        src = np.select([near, band, stare, look], [1, 2, 3, 4], default=0).astype(np.int8)
        return np.where(req2 == FREEZE, src, 0).astype(np.int8)


def teacher2_spec(cfg, allowed, teacher2: str) -> dict:
    """둘째 교사의 정책 스펙: fsm(R1 FSM, eval_v3.fsm_spec near 판) 또는 fsm_r2(eval_v3.fsm_r2_policy_spec)."""
    from eval_v3 import fsm_r2_policy_spec, fsm_spec

    if teacher2 not in TEACHERS2:
        raise ValueError(f"--teacher2 는 {TEACHERS2} 중 하나다. 받은 값: {teacher2!r}")
    return fsm_spec(cfg, allowed, "near") if teacher2 == "fsm" else fsm_r2_policy_spec(cfg, allowed)


def is_r2_world(cfg) -> bool:
    """경보(alarm)나 노려보기(stare_down, 재현 설정)를 켠 v3 R2 세계인가(eval_v3.has_r2_world). --teacher2·--out-dir·--name 기본값이
    쓴다. R2 세계(v3_r2 = v3_r1 + 경보)는 참이다."""
    from eval_v3 import has_r2_world

    return any(has_r2_world(cfg))


def default_teacher2(cfg) -> str:
    """--teacher2 기본값: R2 세계면 fsm_r2, 아니면 fsm(R1 재현). R2 세계에 R1 FSM 교사(look 줄 없음)를 조용히 쓰지 않게."""
    return "fsm_r2" if is_r2_world(cfg) else "fsm"


def default_out_dir(cfg) -> Path:
    """--out-dir 기본값: R2 세계면 ckpt/v3/ws_r2, 아니면 R1 의 ckpt/v3/ws (R1 교사 자료·가중치를 덮지 않게)."""
    return OUT_R2 if is_r2_world(cfg) else OUT


def default_name(cfg) -> str:
    """fit --name 기본값: v<설정 version>_ws (v3_r1 → v3_r1_ws, v3_r2 → v3_r2_ws — train_v3.default_run_name 과 같은 version 조각)."""
    return f"v{str(cfg.v2.get('version') or '3').replace('.', '_')}_ws"


def world_digest(cfg) -> str:
    """교사 자료·맞춘 가중치의 출처 표시(모듈 docstring '출처 확인'): 설정 dict 에서 version 과 train 블록을 빼고
    train.repertoire.allowed 만 다시 넣은 dict 의 sha1 앞 12자리(eval_v3.config_digest 와 같은 식). 교사 자료(관측·마스크·교사 요청)와
    맞춘 가중치의 뜻은 세계 동역학과 허용 목록으로 정해지고, train 블록의 다른 값(ε·f_dec·ent_coef_base·롤아웃 길이)은 PPO 학습만
    바꾼다 — 그래서 조기 중단 대응(ε 0.05 → 0.1, 판정 사전 등록 results/v3/r2/judge/PREREG.md 2절 '같은 모방 초기화에서 다시
    학습')도 같은 가중치를 받는다. 학습 세계(v3_r2)와 판정 세계(v3_r2_on)는 낮 고정 비율이 달라 값이 다르다."""
    d = cfg.to_dict()
    v2 = dict(d.get("v2") or {})
    v2.pop("version", None)
    train = v2.pop("train", None) or {}
    d = dict(d, v2=v2, allowed=list((train.get("repertoire") or {}).get("allowed") or []))
    return hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:12]


def check_source(cfg, sidecar, what: str, allow_legacy: bool = False) -> str | None:
    """`what`(교사 자료·모방 초기화 가중치)의 출처 확인(모듈 docstring '출처 확인'). 곁 파일 `sidecar`(자료는 teacher_mix.json, 가중치는
    <name>_s<시드>.json)의 world_digest 가 이 설정의 값과 다르면 멈춘다. world_digest 가 없으면(곁 파일이 없거나 10-13 전 판)
    R1 세계는 알리고 쓰고, 경보를 켠 R2 세계는 `allow_legacy` 가 아니면 멈춘다. 반환: 곁 파일의 world_digest(옛 판이면 None)."""
    sidecar = Path(sidecar)
    want = world_digest(cfg)
    st = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else None
    got = (st or {}).get("world_digest")
    if got is None:
        msg = (f"{what}에 출처 표시(world_digest)가 없다({sidecar}" + ("" if st is not None else " 없음")
               + ") — 10-13 전 판이다")
        if is_r2_world(cfg) and not allow_legacy:
            raise SystemExit(msg + ". 10-13 전의 R2 자료·가중치는 노려보기·경보 두 장치 세계에서 stare 줄이 든 FSM_R2 로 만든 "
                             "것이라(ckpt/v3/ws_r2_both) 이 세계에 쓰지 않는다. 이 설정으로 다시 만든다(그 실행의 재현이면 "
                             "fit --allow-legacy, train_v3 --allow-legacy-warmstart)")
        print("주의: " + msg + " — 그대로 쓴다(" + ("재현용으로 허용함" if is_r2_world(cfg) else "R1 재현") + ")", flush=True)
        return None
    if got != want:
        raise SystemExit(f"{what}는 다른 세계에서 만든 것이다(world_digest {got}, 이 설정 {want}, {sidecar}) — 이 설정으로 다시 "
                         f"만든다")
    return got


def collect(cfg, n_worlds: int = N_WORLDS, steps: int = STEPS, teacher2: str | None = None) -> dict:
    """교사 자료 모으기(모듈 docstring). `teacher2` 가 None 이면 `default_teacher2`(R2 세계면 fsm_r2, 아니면 fsm)."""
    import env_v2.rollout as ro
    from env_v2.world import World
    from eval_v3 import fsm_spec

    if teacher2 is None:
        teacher2 = default_teacher2(cfg)
    rep = rep_params(cfg)
    lo, hi = cfg.train_seeds
    seeds = np.random.default_rng([COLLECT_TAG]).choice(np.arange(lo, hi), size=n_worlds, replace=False).tolist()
    P_obs, P_mask, P_act, P_act2, V_obs, V_ret = [], [], [], [], [], []
    P_src = []
    src_of = FreezeSource(cfg) if teacher2 == "fsm_r2" else None
    stats = dict(decisions=0, multi=0, teacher_invalid=0, counts_rbase=[0] * N_BEHAVIORS, counts_fsm=[0] * N_BEHAVIORS,
                 agree=0)
    if src_of is not None:
        stats.update(freeze_src_fsm={v: 0 for v in SRC_NAMES.values()}, counts_by_driver={})
    spec2 = teacher2_spec(cfg, rep["allowed"], teacher2)
    for i, s in enumerate(seeds):
        w = World(cfg, seeds=[int(s)])
        rbase = ro.build_policy(fsm_spec(cfg, ("graze", "flee"), "near"), int(s))
        fsm = ro.build_policy(spec2, int(s))
        teacher = rbase if i % 2 == 0 else fsm
        N = w.N
        obs_t = np.empty((steps, N, w.obs_dim), dtype=np.float32)
        mask_t = np.empty((steps, N, N_BEHAVIORS), dtype=bool)
        rew = np.empty((steps, N), dtype=np.float64)
        done = np.empty((steps, N), dtype=bool)
        for t in range(steps):
            obs = w.observe()
            m = action_mask(w, obs, rep)
            a_rb = np.asarray(rbase(obs), dtype=np.float64)
            a_fs = np.asarray(fsm(obs), dtype=np.float64)
            a = a_rb if teacher is rbase else a_fs
            req, req2 = a_rb[:, 0].astype(np.int64), a_fs[:, 0].astype(np.int64)
            reads = np.asarray(w.rep_peek()["reads"], dtype=bool)
            valid = m[np.arange(N), req] & m[np.arange(N), req2]
            multi = reads & (m.sum(1) >= 2)
            stats["decisions"] += int(reads.sum())
            stats["multi"] += int(multi.sum())
            stats["teacher_invalid"] += int((reads & ~valid).sum())
            keep = multi & valid
            if keep.any():
                P_obs.append(obs[keep].astype(np.float32))
                P_mask.append(m[keep])
                P_act.append(req[keep])
                P_act2.append(req2[keep])
                for b in req[keep]:
                    stats["counts_rbase"][int(b)] += 1
                for b in req2[keep]:
                    stats["counts_fsm"][int(b)] += 1
                stats["agree"] += int((req[keep] == req2[keep]).sum())
                if src_of is not None:
                    src = src_of(obs[keep], req[keep], req2[keep])
                    P_src.append(src)
                    for k, v in SRC_NAMES.items():
                        stats["freeze_src_fsm"][v] += int(np.count_nonzero(src == k))
                    drv = "rbase" if teacher is rbase else teacher2
                    cb = stats["counts_by_driver"].setdefault(drv, dict(rbase=[0] * N_BEHAVIORS, fsm=[0] * N_BEHAVIORS))
                    cb["rbase"] = (np.asarray(cb["rbase"]) + np.bincount(req[keep], minlength=N_BEHAVIORS)).tolist()
                    cb["fsm"] = (np.asarray(cb["fsm"]) + np.bincount(req2[keep], minlength=N_BEHAVIORS)).tolist()
            obs_t[t], mask_t[t] = obs, m
            _, r, d, _ = w.step(a)
            rew[t], done[t] = r, d
            for pol in (rbase, fsm):
                hook = getattr(pol, "observe_done", None)
                if hook is not None:
                    hook(d)
        ret = np.zeros((steps, N))
        g = np.zeros(N)
        for t in range(steps - 1, -1, -1):
            g = rew[t] + GAMMA_TRAIN * g * (~done[t])
            ret[t] = g
        use = steps - VALUE_DROP
        idx = np.arange(use * N)[::VALUE_EVERY]
        ot = obs_t[:use].reshape(-1, w.obs_dim)[idx]
        mt = mask_t[:use].reshape(-1, N_BEHAVIORS)[idx]
        V_obs.append(policy_obs(ot, mt))
        V_ret.append(ret[:use].reshape(-1)[idx].astype(np.float32))
        print(f"  세계 {s}: 결정 표본 누적 {sum(len(x) for x in P_act):,}", flush=True)
    data = dict(p_obs=policy_obs(np.concatenate(P_obs), np.concatenate(P_mask)), p_act=np.concatenate(P_act),
                p_act2=np.concatenate(P_act2),
                v_obs=np.concatenate(V_obs), v_ret=np.concatenate(V_ret))
    if src_of is not None:
        data["p_src2"] = np.concatenate(P_src)
    stats.update(seeds=seeds, steps=steps, n_policy=int(len(data["p_act"])), n_value=int(len(data["v_ret"])),
                 v_ret_mean=float(data["v_ret"].mean()), v_ret_std=float(data["v_ret"].std()))
    if src_of is not None:              # R1 자료의 통계 키는 그대로 둔다
        stats.update(teacher2=teacher2, obs_dim=int(data["p_obs"].shape[1] - N_BEHAVIORS))
    return dict(data=data, stats=stats)


def fit(cfg, data: dict, seed: int, epochs: int = EPOCHS, smooth: float = SMOOTH, ppo_config: str | None = None):
    """모델 시드 하나: train_v3 와 같은 PPO 모델을 만들고 정책·가치망을 교사 자료에 맞춘다. 반환 (model, 보고 dict)."""
    from train import load_tuned
    from train_v2 import apply_lr_schedule, resolve_gamma
    from train_v3 import S1A_GAMMA, make_model_rep

    th.manual_seed(seed)
    rep = rep_params(cfg)
    venv = MultiWorldVecEnv(cfg, num_worlds=1, meta_seed=seed)
    if data["p_obs"].shape[1] != venv.obs_dim + N_BEHAVIORS:
        raise ValueError(f"교사 자료의 정책 입력 {data['p_obs'].shape[1]}칸이 이 설정의 [관측 {venv.obs_dim} | 마스크 "
                         f"{N_BEHAVIORS}] 와 다르다 — 같은 설정으로 모은 자료를 쓴다(--data)")
    tuned, _, _ = resolve_gamma(load_tuned(ppo_config or str(ROOT / "configs" / "ppo_best.yaml")), S1A_GAMMA)
    tuned, _ = apply_lr_schedule(tuned, "constant")
    rollout_world_steps = int(cfg.v2["train"].get("rollout_world_steps", 256))
    model = make_model_rep(venv, rep, None, n_steps=max(1, rollout_world_steps // venv.K), seed=seed, **tuned)
    pol = model.policy
    pol.set_training_mode(True)
    opt = th.optim.Adam(pol.parameters(), lr=LR)
    rng = np.random.default_rng([seed, COLLECT_TAG])
    p_obs, p_act, p_act2, v_obs, v_ret = data["p_obs"], data["p_act"], data["p_act2"], data["v_obs"], data["v_ret"]
    p_src = data.get("p_src2")
    n_p, n_v = len(p_act), len(v_ret)
    hold_p = rng.random(n_p) < 0.1
    tr_p, te_p = np.flatnonzero(~hold_p), np.flatnonzero(hold_p)
    steps_per_epoch = math.ceil(len(tr_p) / BATCH)
    hist = []
    for ep in range(epochs):
        perm_p = rng.permutation(tr_p)
        perm_v = rng.integers(0, n_v, size=steps_per_epoch * BATCH)
        ce_sum = v_sum = 0.0
        for k in range(steps_per_epoch):
            bi = perm_p[k * BATCH:(k + 1) * BATCH]
            o = th.as_tensor(p_obs[bi])
            m = o[:, -N_BEHAVIORS:] > 0.5
            oh1 = th.nn.functional.one_hot(th.as_tensor(p_act[bi]), N_BEHAVIORS).float()
            oh2 = th.nn.functional.one_hot(th.as_tensor(p_act2[bi]), N_BEHAVIORS).float()
            uni = m.float() / m.float().sum(1, keepdim=True)
            tgt = (1.0 - smooth) * 0.5 * (oh1 + oh2) + smooth * uni
            d = pol.get_distribution(o)
            logp = th.where(m, d.log_pi, th.zeros_like(d.log_pi))
            ce = -(tgt * logp).sum(1).mean()
            vi = perm_v[k * BATCH:(k + 1) * BATCH]
            vo = th.as_tensor(v_obs[vi])
            pol._set_mask(vo)
            vpred = pol.predict_values(vo).squeeze(1)
            vl = th.nn.functional.mse_loss(vpred, th.as_tensor(v_ret[vi]))
            loss = ce + VALUE_COEF * vl
            opt.zero_grad()
            loss.backward()
            th.nn.utils.clip_grad_norm_(pol.parameters(), 0.5)
            opt.step()
            ce_sum += float(ce)
            v_sum += float(vl)
        acc = held_out_report(pol, p_obs[te_p], p_act[te_p], p_act2[te_p], None if p_src is None else p_src[te_p])
        hist.append(dict(epoch=ep + 1, ce=ce_sum / steps_per_epoch, v_mse=v_sum / steps_per_epoch, **acc))
        print(f"  [s{seed}] 에폭 {ep + 1}: CE {hist[-1]['ce']:.4f}, 가치 MSE {hist[-1]['v_mse']:.4f}, 보류 정확도 "
              f"{acc['acc']:.4f}(두 교사 행동의 π 합), 행동별 평균 π {acc['recall']}"
              + (f", FREEZE 출처별 평균 π(FREEZE)·표본 {acc['recall_src']}" if "recall_src" in acc else ""), flush=True)
    pol.set_training_mode(False)
    return model, dict(seed=seed, history=hist, n_policy=n_p, n_value=n_v, smooth=smooth, epochs=epochs)


def held_out_report(pol, obs, act, act2, src=None) -> dict:
    """보류 표본: 행동별 평균 π(그 행동을 교사 하나라도 골랐을 때)와 두 교사 행동의 평균 π 합. `src`(fsm_r2 교사의 FREEZE 출처,
    모듈 docstring 'v3 R2')를 주면 출처별 [평균 π(FREEZE), 표본 수](`recall_src`)도 낸다."""
    with th.no_grad():
        d = pol.get_distribution(th.as_tensor(obs))
        pi = d.probs_masked().cpu().numpy()
    rec = {}
    for b in range(N_BEHAVIORS):
        sel = (act == b) | (act2 == b)
        if sel.any():
            rec[int(b)] = round(float(pi[sel, b].mean()), 3)
    i = np.arange(len(act))
    both = np.where(act == act2, pi[i, act], pi[i, act] + pi[i, act2])
    out = dict(acc=float(both.mean()), recall=rec)
    if src is not None:
        from env_v2.repertoire import FREEZE

        out["recall_src"] = {v: [round(float(pi[src == k, FREEZE].mean()), 3) if (src == k).any() else None,
                                 int(np.count_nonzero(src == k))] for k, v in SRC_NAMES.items()}
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("collect", "fit"):
        print(__doc__)
        return 2
    cmd = argv.pop(0)
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--out-dir", default=None,
                    help="교사 자료·맞춘 가중치 폴더(기본: R2 세계면 ckpt/v3/ws_r2, 아니면 R1 의 ckpt/v3/ws)")
    ap.add_argument("--data", default=None, help="교사 자료 .npz (기본 <out-dir>/teacher_mix.npz)")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--force", action="store_true",
                    help="있는 산출(collect: teacher_mix.npz·.json, fit: <name>_s<시드>.pt·.zip·.json)을 덮는다. 기본은 멈춘다")
    if cmd == "collect":
        ap.add_argument("--worlds", type=int, default=N_WORLDS)
        ap.add_argument("--steps", type=int, default=STEPS)
        ap.add_argument("--teacher2", choices=TEACHERS2, default=None,
                        help="둘째 교사: fsm(R1 FSM) 또는 fsm_r2(v3 R2 FSM_R2). 기본: R2 세계면 fsm_r2, 아니면 fsm(R1 재현)")
    else:
        ap.add_argument("--seeds", type=int, nargs="+", required=True)
        ap.add_argument("--epochs", type=int, default=EPOCHS)
        ap.add_argument("--smooth", type=float, default=SMOOTH)
        ap.add_argument("--name", default=None, help="가중치 이름(기본 v<설정 version>_ws: v3_r1_ws, v3_r2_ws)")
        ap.add_argument("--allow-legacy", action="store_true",
                        help="출처 표시가 없는 10-13 전 자료를 R2 세계에서도 쓴다(두 장치 실행의 재현용, 모듈 docstring '출처 확인')")
    a = ap.parse_args(argv)
    th.set_num_threads(a.threads)
    cfg = load_v2_config(a.config)
    out_dir = Path(a.out_dir) if a.out_dir is not None else default_out_dir(cfg)
    if cmd == "collect" and a.teacher2 is None:
        a.teacher2 = default_teacher2(cfg)
    if cmd == "collect" and a.teacher2 == "fsm" and is_r2_world(cfg):
        print("주의: R2 세계(경보)에 R1 FSM 교사(look 줄 없음)를 쓴다 — --teacher2 fsm 을 직접 준 경우만", flush=True)
    if cmd == "fit" and a.name is None:
        a.name = default_name(cfg)
    if a.data is None:
        a.data = str(out_dir / "teacher_mix.npz")
    from eval_v3 import config_digest

    t0 = time.time()
    if cmd == "collect":
        old = [p for p in (Path(a.data), Path(a.data).with_suffix(".json")) if p.exists()]
        if old and not a.force:
            raise SystemExit(f"이미 있는 교사 자료를 덮지 않는다: {', '.join(map(str, old))} — 옮기거나(앞선 실행 기록) --force")
        res = collect(cfg, a.worlds, a.steps, a.teacher2)
        Path(a.data).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(a.data, **res["data"])
        st = dict(res["stats"], config=str(a.config), world_digest=world_digest(cfg), config_digest=config_digest(cfg),
                  generated=datetime.now(timezone.utc).isoformat(timespec="seconds"), elapsed_s=round(time.time() - t0, 1))
        Path(a.data).with_suffix(".json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(st, ensure_ascii=False))
        return 0
    old = [p for s in a.seeds for ext in (".pt", ".zip", ".json") if (p := out_dir / f"{a.name}_s{s}{ext}").exists()]
    if old and not a.force:
        raise SystemExit(f"이미 있는 가중치를 덮지 않는다: {', '.join(map(str, old))} — 옮기거나(앞선 실행 기록) --force")
    if not Path(a.data).exists():
        raise SystemExit(f"교사 자료 {a.data} 가 없다 — 먼저 같은 설정으로 collect 한다")
    src = check_source(cfg, Path(a.data).with_suffix(".json"), "교사 자료", a.allow_legacy)
    z = np.load(a.data)
    data = {k: z[k] for k in z.files}
    out_dir.mkdir(parents=True, exist_ok=True)
    for s in a.seeds:
        model, rep = fit(cfg, data, s, a.epochs, a.smooth)
        base = out_dir / f"{a.name}_s{s}"
        th.save({"policy": model.policy.state_dict()}, base.with_suffix(".pt"))
        model.save(base.with_suffix(".zip"))
        rep.update(config=str(a.config), data=str(a.data), world_digest=world_digest(cfg), config_digest=config_digest(cfg),
                   data_world_digest=src, elapsed_s=round(time.time() - t0, 1),
                   generated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   mask_version=int(model.policy.rep_mask_version), obs_names=list(model.policy.rep_obs_names))
        base.with_suffix(".json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"저장: {base}.pt / .zip", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
