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
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
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


def collect(cfg, n_worlds: int = N_WORLDS, steps: int = STEPS) -> dict:
    import env_v2.rollout as ro
    from env_v2.world import World
    from eval_v3 import fsm_spec

    rep = rep_params(cfg)
    lo, hi = cfg.train_seeds
    seeds = np.random.default_rng([COLLECT_TAG]).choice(np.arange(lo, hi), size=n_worlds, replace=False).tolist()
    P_obs, P_mask, P_act, P_act2, V_obs, V_ret = [], [], [], [], [], []
    stats = dict(decisions=0, multi=0, teacher_invalid=0, counts_rbase=[0] * N_BEHAVIORS, counts_fsm=[0] * N_BEHAVIORS,
                 agree=0)
    for i, s in enumerate(seeds):
        w = World(cfg, seeds=[int(s)])
        rbase = ro.build_policy(fsm_spec(cfg, ("graze", "flee"), "near"), int(s))
        fsm = ro.build_policy(fsm_spec(cfg, rep["allowed"], "near"), int(s))
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
    stats.update(seeds=seeds, steps=steps, n_policy=int(len(data["p_act"])), n_value=int(len(data["v_ret"])),
                 v_ret_mean=float(data["v_ret"].mean()), v_ret_std=float(data["v_ret"].std()))
    return dict(data=data, stats=stats)


def fit(cfg, data: dict, seed: int, epochs: int = EPOCHS, smooth: float = SMOOTH, ppo_config: str | None = None):
    """모델 시드 하나: train_v3 와 같은 PPO 모델을 만들고 정책·가치망을 교사 자료에 맞춘다. 반환 (model, 보고 dict)."""
    from train import load_tuned
    from train_v2 import apply_lr_schedule, resolve_gamma
    from train_v3 import S1A_GAMMA, make_model_rep

    th.manual_seed(seed)
    rep = rep_params(cfg)
    venv = MultiWorldVecEnv(cfg, num_worlds=1, meta_seed=seed)
    tuned, _, _ = resolve_gamma(load_tuned(ppo_config or str(ROOT / "configs" / "ppo_best.yaml")), S1A_GAMMA)
    tuned, _ = apply_lr_schedule(tuned, "constant")
    rollout_world_steps = int(cfg.v2["train"].get("rollout_world_steps", 256))
    model = make_model_rep(venv, rep, None, n_steps=max(1, rollout_world_steps // venv.K), seed=seed, **tuned)
    pol = model.policy
    pol.set_training_mode(True)
    opt = th.optim.Adam(pol.parameters(), lr=LR)
    rng = np.random.default_rng([seed, COLLECT_TAG])
    p_obs, p_act, p_act2, v_obs, v_ret = data["p_obs"], data["p_act"], data["p_act2"], data["v_obs"], data["v_ret"]
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
        acc = held_out_report(pol, p_obs[te_p], p_act[te_p], p_act2[te_p])
        hist.append(dict(epoch=ep + 1, ce=ce_sum / steps_per_epoch, v_mse=v_sum / steps_per_epoch, **acc))
        print(f"  [s{seed}] 에폭 {ep + 1}: CE {hist[-1]['ce']:.4f}, 가치 MSE {hist[-1]['v_mse']:.4f}, 보류 정확도 "
              f"{acc['acc']:.4f}(두 교사 행동의 π 합), 행동별 평균 π {acc['recall']}", flush=True)
    pol.set_training_mode(False)
    return model, dict(seed=seed, history=hist, n_policy=n_p, n_value=n_v, smooth=smooth, epochs=epochs)


def held_out_report(pol, obs, act, act2) -> dict:
    """보류 표본: 행동별 평균 π(그 행동을 교사 하나라도 골랐을 때)와 두 교사 행동의 평균 π 합."""
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
    return dict(acc=float(both.mean()), recall=rec)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("collect", "fit"):
        print(__doc__)
        return 2
    cmd = argv.pop(0)
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--data", default=str(OUT / "teacher_mix.npz"))
    ap.add_argument("--threads", type=int, default=4)
    if cmd == "collect":
        ap.add_argument("--worlds", type=int, default=N_WORLDS)
        ap.add_argument("--steps", type=int, default=STEPS)
    else:
        ap.add_argument("--seeds", type=int, nargs="+", required=True)
        ap.add_argument("--epochs", type=int, default=EPOCHS)
        ap.add_argument("--smooth", type=float, default=SMOOTH)
        ap.add_argument("--name", default="v3_r1_ws")
    a = ap.parse_args(argv)
    th.set_num_threads(a.threads)
    cfg = load_v2_config(a.config)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if cmd == "collect":
        res = collect(cfg, a.worlds, a.steps)
        np.savez_compressed(a.data, **res["data"])
        st = dict(res["stats"], config=str(a.config), generated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  elapsed_s=round(time.time() - t0, 1))
        Path(a.data).with_suffix(".json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(st, ensure_ascii=False))
        return 0
    z = np.load(a.data)
    data = {k: z[k] for k in z.files}
    for s in a.seeds:
        model, rep = fit(cfg, data, s, a.epochs, a.smooth)
        base = OUT / f"{a.name}_s{s}"
        th.save({"policy": model.policy.state_dict()}, base.with_suffix(".pt"))
        model.save(base.with_suffix(".zip"))
        rep.update(config=str(a.config), data=str(a.data), elapsed_s=round(time.time() - t0, 1),
                   generated=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        base.with_suffix(".json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"저장: {base}.pt / .zip", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
