"""v3 현실성 1단계 — 재학습 없이 지금 두뇌를 새 규칙 세계에 얹어 본 측정 (사전 기록 `PREREG.md`).

    # herbivore_rl/ 에서
    python results/v3/real1/eval_real1.py run --workers 14            # 본 측정 → results/v3/real1/real1.json, tables.md
    python results/v3/real1/eval_real1.py run --long --workers 14     # 긴 판 확인 → real1_long.json, tables_long.md
    python results/v3/real1/eval_real1.py smoke                       # 탐색 시드 32000 × 200스텝, 저장하지 않는다
    python results/v3/real1/eval_real1.py verify                      # Spy 가 궤적을 바꾸지 않는지(탐색 시드 32000~32001)

판정이 아니라 측정이다. 환경 코드(env_v2/*)는 바꾸지 않는다. 세계 안을 엿보는 것은 `Spy`(World 를 상속해 `_threat_motion`·
`_step_predators_v3` 을 감싼다 — 기록만 하고 상태·난수를 바꾸지 않는다)뿐이다.

- 정책: rl = 출시 두뇌 R1b s3(`ckpt/v3/v3_r1_g995_s3_20m.zip`, argmax, 마스크 판 2), rbase = 손 규칙 R_base(θ 4, a 0.9)
  (eval_v3.fsm_spec(cfg, ('graze','flee'), 'near') 그대로).
- 세계(VARIANTS): base = configs/v3_r1_on.yaml, 규칙 하나씩 켠 판(vision·hearing·shelter(c+e)·night), shelter 를 둘로 가른 판
  (shelter_c = 은신처 안전만, cover_food_e = 은신처 먹이 부족만 — v3_real1_shelter_on.yaml 의 다른 블록을 메모리에서 끈다), all =
  configs/v3_real1_on.yaml. train_ref = configs/v3_r1.yaml(R1b 를 학습한 설정, 낮 고정 세계 20%)은 관측 범위 기준으로만 rl 을 돌린다.
- 시드: 보정 20000~20019 × 3000스텝(본 측정), 긴 판 20000~20007 × 10000스텝(같은 세계 모두). 판정 시드는 쓰지 않는다.
- 지표 정의는 PREREG.md 2절. 시간: 1스텝 = 2/15 s, 3 s = 22스텝(World 의 깜빡임 창과 같다).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
OUT_DIR = HERE.parent
ROOT = HERE.parents[3]                       # herbivore_rl
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

MODEL = "ckpt/v3/v3_r1_g995_s3_20m.zip"
SEEDS = list(range(20000, 20020))
STEPS = 3000
LONG_SEEDS = list(range(20000, 20008))
LONG_STEPS = 10000
LONG_VARIANTS = ("base", "vision", "hearing", "shelter", "shelter_c", "cover_food_e", "night", "all")
SMOKE_SEEDS = [32000]
FORBIDDEN = [range(10000, 10020), range(10200, 10220), range(12160, 12200), range(14000, 14040)]
ALLOWED = [range(20000, 20020), range(32000, 32100)]

VARIANTS = {
    "base": ("configs/v3_r1_on.yaml", None),
    "vision": ("configs/v3_real1_vision_on.yaml", None),
    "hearing": ("configs/v3_real1_hearing_on.yaml", None),
    "shelter": ("configs/v3_real1_shelter_on.yaml", None),
    "shelter_c": ("configs/v3_real1_shelter_on.yaml", ("realism_cover_food",)),
    "cover_food_e": ("configs/v3_real1_shelter_on.yaml", ("realism_shelter",)),
    "night": ("configs/v3_real1_night_on.yaml", None),
    "all": ("configs/v3_real1_on.yaml", None),
    "train_ref": ("configs/v3_r1.yaml", None),
}
VARIANT_ORDER = ("base", "vision", "hearing", "shelter", "shelter_c", "cover_food_e", "night", "all")
POLICIES = ("rl", "rbase")
REF_VARIANTS = ("base", "train_ref")         # 관측 범위 기준(rl 만)

GAMMA = 0.9916661555611042                   # eval_v3.GAMMA
TAIL = 600                                   # eval_v3.TAIL
WIN = 22                                     # 3 s (World._rep_flicker_w 와 같은 22스텝)
WIN60 = 60                                   # 앞 측정의 '60스텝 안 잡힘'(8 s)
PURSUE_R = 10.0                              # '쫓는 위협이 10 안'
SETTLE_R = 8.0                               # 잠드는 순간 사슴 근처 판정(realism_night.settle_r 과 같다)
COS_FRONT = math.cos(math.radians(60.0))     # 앞쪽 120° (학습 세계의 위협 시야)
COS_REAR = math.cos(math.radians(150.0))     # 바로 뒤 60° (300° 세계의 사각)
NB = 1000                                    # 관측 히스토그램 칸(0.001)
NB_FLAG = 100                                # 범위·지지 판정 칸(0.01)
EPS_RANGE = 1e-6
J1_TOL = 1e-4
FLEE_LEN_BINS = (0, 8, 9, 16, 23, 46, 91, 10 ** 9)   # 칸 [a, b): <8, 8, 9~15, 16~22, 23~45, 46~90, 91+
COND_NAMES = ("pred_dist|seen", "pred_approach|seen", "food_density|in_cover", "threat_recency|unseen")


def _check_seeds(seeds) -> None:
    for s in seeds:
        if any(s in r for r in FORBIDDEN):
            raise SystemExit(f"판정 시드 {s} 는 쓰지 않는다")
        if not any(s in r for r in ALLOWED):
            raise SystemExit(f"시드 {s} 는 보정 20000~20019·탐색 32000~32099 밖이다")


def load_variant(name: str):
    from env_v2.config import load_v2_config

    path, off = VARIANTS[name]
    cfg = load_v2_config(ROOT / path)
    if off:
        f = {k: dict(v) for k, v in cfg.v2["features"].items()}
        for b in off:
            f[b] = dict(f[b], enabled=False)
        cfg = cfg.replace(v2=dict(cfg.v2, features=f))
    return cfg


def _spy_class():
    from env_v2.steering import EPS
    from env_v2.world import PM_CHARGE, PT_STALKER, ST_POUNCE, World

    class Spy(World):
        """기록만 하는 World. `_threat_motion` 에 들어오는 이동 방향(표적이 있으면 표적 쪽 단위 벡터)으로 표적 번호를 되찾고,
        `_step_predators_v3` 앞뒤로 포획 위치의 은신처 여부·포식자 이동 뒤 기하를 남긴다. 상태·난수를 바꾸지 않는다."""

        def _spy_init(self):
            self.spy_prev_tgt = np.full(self.M, -1, dtype=np.int64)
            self.spy_tgt = np.full(self.M, -1, dtype=np.int64)
            self.spy_fail = 0
            self.spy = None

        def _threat_motion(self, move, speed, wander, has_target, d_t, exh0, rest0):
            M = self.M
            tgt = np.full(M, -1, dtype=np.int64)
            idx = np.flatnonzero(has_target)
            if len(idx):
                v = self.pos[None, :, :] - self.pred_pos[idx][:, None, :]
                d = np.sqrt((v * v).sum(2))
                cs = (v * move[idx][:, None, :]).sum(2) / np.maximum(d, EPS)
                dd = np.where(cs > 1.0 - 1e-9, d, np.inf)
                k = dd.argmin(1)
                ok = np.isfinite(dd[np.arange(len(idx)), k])
                self.spy_fail += int(np.count_nonzero(~ok))
                tgt[idx] = np.where(ok, k, cs.argmax(1))
            out = super()._threat_motion(move, speed, wander, has_target, d_t, exh0, rest0)
            # 표적이 안 보여도 곧장 이어 가는 돌진(잠행형 돌진·플레이어 돌진)은 지난 표적을 쫓는 중으로 둔다
            carry = ~has_target & (((self.pred_type == PT_STALKER) & (self.stalk_state == ST_POUNCE))
                                   | (self.pred_is_player & (self.player_mode == PM_CHARGE)))
            tgt = np.where(carry, self.spy_prev_tgt, tgt)
            self.spy_tgt = tgt
            return out

        def _step_predators_v3(self):
            in_cov = self._in_cover(self.pos)
            self.spy_tgt = np.full(self.M, -1, dtype=np.int64)
            caught = super()._step_predators_v3()
            N, M = self.N, self.M
            awake = ~self.pred_asleep if self._ps is not None else np.ones(M, dtype=bool)
            ex = self.pred_pos[:, 0][None, :] - self.pos[:, 0:1]          # (N, M) 사슴 → 위협
            ey = self.pred_pos[:, 1][None, :] - self.pos[:, 1:2]
            pd = np.sqrt(ex * ex + ey * ey)
            cosang = (ex * self.head[:, 0:1] + ey * self.head[:, 1:2]) / np.maximum(pd, EPS)
            cls = np.where(cosang >= COS_FRONT, 0, np.where(cosang >= COS_REAR, 1, 2)).astype(np.int8)
            pa = np.where(awake[None, :], pd, np.inf)
            j = pa.argmin(1)
            ar = np.arange(N)
            near_d = pa[ar, j]
            near_cls = np.where(np.isfinite(near_d), cls[ar, j], -1).astype(np.int8)
            purs_d = np.full(N, np.inf)
            purs_cls = np.full(N, -1, dtype=np.int8)
            purs_kind = np.full(N, -1, dtype=np.int8)
            # 위협 종류(eval_v3.R2_KINDS 와 같은 번호): 0 근접 추격, 1 원거리, 2 잠행, 3 플레이어
            kind = np.where(self.pred_is_player, 3, np.where(self.pred_type == PT_STALKER, 2,
                                                             np.where(self.pred_ranged, 1, 0)))
            for tg in (self.spy_tgt, self.spy_prev_tgt):            # 이번 스텝 또는 지난 스텝에 이 사슴을 쫓은 위협
                for m in np.flatnonzero((tg >= 0) & awake):
                    i = tg[m]
                    if pd[i, m] < purs_d[i]:
                        purs_d[i] = pd[i, m]
                        purs_cls[i] = cls[i, m]
                        purs_kind[i] = kind[m]
            self.spy = dict(caught=caught.copy(), in_cov=in_cov, near_d=near_d, near_cls=near_cls, purs_d=purs_d,
                            purs_cls=purs_cls, purs_kind=purs_kind)
            self.spy_prev_tgt = self.spy_tgt.copy()
            return caught

    return Spy


def make_policy(pname: str, cfg, seed: int):
    from env_v2 import rollout as ro

    import eval_v3 as ev

    if pname == "rl":
        return ro.build_policy({"kind": "rep_learned", "path": str(ROOT / MODEL)}, seed)
    if pname == "rbase":
        return ro.build_policy(ev.fsm_spec(cfg, ("graze", "flee"), "near"), seed)
    raise ValueError(pname)


def _hist(x: np.ndarray, nb: int = NB) -> np.ndarray:
    """(n, F) 값 [0, 1] → (F, nb) 칸 수. 칸 = floor(x·nb), 1.0 은 마지막 칸."""
    n, F = x.shape
    b = np.clip(np.floor(x.astype(np.float64) * nb).astype(np.int64), 0, nb - 1)
    return np.bincount((b + np.arange(F)[None, :] * nb).ravel(), minlength=F * nb).reshape(F, nb)


def _hist1(x: np.ndarray, nb: int = NB) -> np.ndarray:
    b = np.clip(np.floor(np.asarray(x, dtype=np.float64) * nb).astype(np.int64), 0, nb - 1)
    return np.bincount(b, minlength=nb)


def job(args):
    from env_v2 import rollout as ro
    from env_v2.rep_policy import rep_params
    from env_v2.repertoire import FLEE, N_BEHAVIORS, SLEEP

    import eval_v3 as ev
    import repertoire_rules as rr

    variant, pname, seed, steps = args
    t0 = time.time()
    cfg = load_variant(variant)
    rep_params(cfg)
    geo = rr._geom(cfg)
    Spy = _spy_class()
    w = Spy(cfg, seeds=[seed])
    w._spy_init()
    pol = make_policy(pname, cfg, seed)
    ro.forward_bind(pol, w)
    N, T, F = w.N, steps, w.obs_dim
    names = list(w.obs_names)
    c_pc, c_pd, c_app = names.index("pred_count"), names.index("pred_dist"), names.index("pred_approach")
    c_food, c_cov, c_rec = names.index("food_density"), names.index("cover_dist"), names.index("threat_recency")
    rew = np.empty((T, N))
    done = np.zeros((T, N), dtype=bool)
    beh = np.zeros((T, N), dtype=np.int8)
    caught = np.zeros((T, N), dtype=bool)
    in_cov = np.zeros((T, N), dtype=bool)
    near_d = np.full((T, N), np.inf, dtype=np.float32)
    near_cls = np.full((T, N), -1, dtype=np.int8)
    purs_d = np.full((T, N), np.inf, dtype=np.float32)
    purs_cls = np.full((T, N), -1, dtype=np.int8)
    purs_kind = np.full((T, N), -1, dtype=np.int8)
    seen_dec = np.zeros((T, N), dtype=bool)
    u_cnt = {u: np.zeros(4, dtype=np.int64) for u in ev.u_names("r1b")}
    choice = np.zeros(N_BEHAVIORS, dtype=np.int64)
    n_dec = 0
    h_all = np.zeros((F, NB), dtype=np.int64)
    h_dec = np.zeros((F, NB), dtype=np.int64)
    h_cond = np.zeros((len(COND_NAMES), NB), dtype=np.int64)
    mn_all, mx_all = np.full(F, np.inf), np.full(F, -np.inf)
    mn_dec, mx_dec = np.full(F, np.inf), np.full(F, -np.inf)
    out01 = 0
    j1 = np.zeros(3, dtype=np.int64)            # [보이는 표본, 위반, 위반 중 최대 초과 × 1e6]
    j1_max = 0.0
    sleep_on = np.zeros(2, dtype=np.int64)      # [잠든 늑대-사건, 그중 실거리 8 안에 사슴]
    has_ps = w._ps is not None
    for t in range(T):
        obs = w.observe()
        pk = w.rep_peek()
        g = w._g
        seen_dec[t] = g["pred_count"] > 0
        h_all += _hist(obs)
        mn_all = np.minimum(mn_all, obs.min(0))
        mx_all = np.maximum(mx_all, obs.max(0))
        out01 += int(np.count_nonzero((obs < 0.0) | (obs > 1.0)))
        seen = obs[:, c_pc] > 0.0
        if seen.any():
            h_cond[0] += _hist1(obs[seen, c_pd])
            h_cond[1] += _hist1(obs[seen, c_app])
            # J1 학습 결합 범위: 보이는 위협의 실거리 ≤ 지금 탐지 반경(see_r × visibility × 행동 배수)
            lim = (w._see_pred * w._rep_see)[seen] / cfg.see_r
            exc = obs[seen, c_pd].astype(np.float64) - lim
            bad = exc > J1_TOL
            j1[0] += int(seen.sum())
            j1[1] += int(bad.sum())
            if bad.any():
                j1_max = max(j1_max, float(exc.max()))
        inc = obs[:, c_cov] <= 0.0
        if inc.any():
            h_cond[2] += _hist1(obs[inc, c_food])
        if (~seen).any():
            h_cond[3] += _hist1(obs[~seen, c_rec])
        a = np.asarray(pol(obs), dtype=np.float64)
        dec = pk["reads"]
        if dec.any():
            od = obs[dec]
            h_dec += _hist(od)
            mn_dec = np.minimum(mn_dec, od.min(0))
            mx_dec = np.maximum(mx_dec, od.max(0))
            req = a[dec, 0].astype(np.int64)
            wake = pk["wake_decide"][dec]
            chosen = np.where(wake & (req == SLEEP), w._rs.wake_target[dec].astype(np.int64), req)
            f = rr.features_of_obs(od, geo)
            for u, (ca, cb) in ev.u_terms(f, "near", "r1b").items():
                hit = np.isin(chosen, ev.U_TARGET[u])
                u_cnt[u] += (np.count_nonzero(ca), np.count_nonzero(ca & hit), np.count_nonzero(cb),
                             np.count_nonzero(cb & hit))
            choice += np.bincount(chosen, minlength=N_BEHAVIORS)
            n_dec += int(dec.sum())
        asleep0 = w.pred_asleep.copy() if has_ps else None
        _, r, d_, _ = w.step(a)
        ro.forward_done(pol, d_)
        rew[t], done[t] = r, d_
        beh[t] = w.behavior
        sp = w.spy
        caught[t], in_cov[t] = sp["caught"], sp["in_cov"]
        near_d[t], near_cls[t], purs_d[t], purs_cls[t] = sp["near_d"], sp["near_cls"], sp["purs_d"], sp["purs_cls"]
        purs_kind[t] = sp["purs_kind"]
        if has_ps:
            fell = np.flatnonzero(~asleep0 & w.pred_asleep)
            if len(fell):
                dx = w.pos[:, 0][None, :] - w.pred_pos[fell, 0][:, None]
                dy = w.pos[:, 1][None, :] - w.pred_pos[fell, 1][:, None]
                dmin = np.sqrt(dx * dx + dy * dy).min(1)
                sleep_on += (len(fell), int(np.count_nonzero(dmin <= SETTLE_R)))
    bouts = flee_bouts(beh, done, caught, purs_d, purs_cls, near_d, near_cls, seen_dec, FLEE, purs_kind, in_cov)
    bh = w._rep_hist.sum((0, 1)).astype(np.int64)
    out = dict(variant=variant, policy=pname, seed=int(seed), steps=int(T), n=int(T * N),
               g_gamma=ro.g_gamma(rew, done, GAMMA, TAIL),
               pred_rate=w._pred_deaths / (T * N), starve_rate=w._starve_deaths / (T * N),
               beh=bh.tolist(), switch=int(w._rep_switch), flicker=int(w._rep_flicker), n_dec=n_dec,
               choice=choice.tolist(), u_cnt={u: v.tolist() for u, v in u_cnt.items()},
               catch_n=int(caught.sum()), catch_in_cover=int((caught & in_cov).sum()),
               in_cover_frac=float(in_cov.mean()), spy_fail=int(w.spy_fail), sleep_on=sleep_on.tolist(),
               bouts=bouts,
               obs=dict(h_all=h_all.tolist(), h_dec=h_dec.tolist(), h_cond=h_cond.tolist(), mn_all=mn_all.tolist(),
                        mx_all=mx_all.tolist(), mn_dec=mn_dec.tolist(), mx_dec=mx_dec.tolist(), out01=out01,
                        j1=[int(j1[0]), int(j1[1])], j1_max=j1_max))
    ds = w.daynight_stats()
    out.update(pred_rate_night=ds.get("pred_rate_night"), pred_rate_day=ds.get("pred_rate_day"))
    if has_ps:
        out["pred_asleep_mean"] = w.pred_sleep_stats()["pred_asleep_mean"]
    if w._rz:
        out["realism"] = {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
                          for k, v in w.realism_stats().items()}
    out["sec"] = time.time() - t0
    return out


def flee_bouts(beh, done, caught, purs_d, purs_cls, near_d, near_cls, seen_dec, FLEE, purs_kind=None, in_cov=None) -> dict:
    """도주 묶음(PREREG 2절). 묶음 = 한 개체(슬롯 + 세대)의 FLEE 연속 스텝. 끝 = 바뀜(살아서 FLEE 가 아닌 행동으로) 또는
    죽음(FLEE 중 잡힘·굶음). 실행이 끝날 때 FLEE 중이면 길이에서 뺀다(잘림)."""
    T, N = beh.shape
    Fm = beh == FLEE
    ok_prev = np.zeros((T, N), dtype=bool)
    ok_prev[1:] = ~done[:-1]                     # t 의 개체가 t−1 의 개체와 같다
    cont = np.zeros((T, N), dtype=bool)
    cont[1:] = Fm[:-1] & ok_prev[1:]             # t−1 에 같은 개체가 FLEE 중이었다
    start = Fm & ~cont
    sw_end = cont & ~Fm                          # t 에 처음으로 FLEE 가 아니다(바뀜)
    death_end = Fm & done
    lengths, len_sw, len_death = [], [], []
    ends = []                                    # (t, i) 바뀜 끝
    censored = 0
    for i in range(N):
        s_list = np.flatnonzero(start[:, i])
        e_sw = np.flatnonzero(sw_end[:, i])
        e_dt = np.flatnonzero(death_end[:, i])
        ev = sorted([(t, 0) for t in e_sw] + [(t, 1) for t in e_dt])
        k = 0
        for s in s_list:
            while k < len(ev) and ev[k][0] < s:
                k += 1
            if k >= len(ev):
                censored += 1
                continue
            t, kind = ev[k]
            k += 1
            if kind == 0:
                L = t - s
                len_sw.append(L)
                ends.append((t, i))
            else:
                L = t - s + 1
                len_death.append(L)
            lengths.append(L)
    n_end = len(ends)
    pursued = refle = caught_w = stopgo = caught60 = 0
    after = np.zeros(8, dtype=np.int64)
    d_all, d_purs = [], []
    cls_purs = np.zeros(3, dtype=np.int64)
    seen_purs = 0
    cls_near = np.zeros(3, dtype=np.int64)
    quick_reflee_all = 0
    # 쫓김 끝의 자세한 칸: 바꾼 행동 × [끝 수, 멈춤-재도주], 쫓는 위협 종류 × [끝 수, 멈춤-재도주],
    # 결정 때 보임 [안 보임, 보임] × [끝 수, 멈춤-재도주], 끝 위치 [은신처 밖, 안] × [끝 수, 멈춤-재도주]
    p_after = np.zeros((8, 2), dtype=np.int64)
    p_kind = np.zeros((4, 2), dtype=np.int64)
    p_seen = np.zeros((2, 2), dtype=np.int64)
    p_cov = np.zeros((2, 2), dtype=np.int64)
    for t, i in ends:
        after[beh[t, i]] += 1
        nd = float(near_d[t, i])
        d_all.append(nd if math.isfinite(nd) else 1e9)
        if near_cls[t, i] >= 0:
            cls_near[near_cls[t, i]] += 1
        p = float(purs_d[t, i]) <= PURSUE_R
        # 3 s 안 다시 도주 / 잡힘 (같은 개체만)
        rf = cw = c60 = False
        for k in range(t, min(t + WIN60, T - 1) + 1):
            if k > t and done[k - 1, i]:
                break
            if k > t and k - t <= WIN and Fm[k, i]:
                rf = True
            if caught[k, i]:
                if k - t <= WIN:
                    cw = True
                c60 = True
                break
        quick_reflee_all += int(rf)
        if p:
            pursued += 1
            d_purs.append(float(purs_d[t, i]))
            if purs_cls[t, i] >= 0:
                cls_purs[purs_cls[t, i]] += 1
            seen_purs += int(seen_dec[t, i])
            refle += int(rf)
            caught_w += int(cw and not rf)
            stopgo += int(rf or cw)
            caught60 += int(c60)
            sg = int(rf or cw)
            p_after[beh[t, i]] += (1, sg)
            p_seen[int(seen_dec[t, i])] += (1, sg)
            if purs_kind is not None and purs_kind[t, i] >= 0:
                p_kind[purs_kind[t, i]] += (1, sg)
            if in_cov is not None:
                p_cov[int(in_cov[t, i])] += (1, sg)
    return dict(lengths=lengths, len_sw=len_sw, len_death=len_death, censored=censored, n_end=n_end,
                n_death_end=len(len_death), pursued=pursued, reflee=refle, caught_w=caught_w, stopgo=stopgo,
                caught60=caught60, quick_reflee_all=quick_reflee_all, after=after.tolist(),
                d_all=[round(x, 3) for x in d_all], d_purs=[round(x, 3) for x in d_purs],
                cls_purs=cls_purs.tolist(), seen_purs=seen_purs, cls_near=cls_near.tolist(),
                p_after=p_after.tolist(), p_kind=p_kind.tolist(), p_seen=p_seen.tolist(), p_cov=p_cov.tolist())


# --------------------------------------------------------------------- #
# 모으기
# --------------------------------------------------------------------- #


def _pct(xs, qs=(10, 25, 50, 75, 90)):
    if not xs:
        return {f"p{q}": None for q in qs}
    a = np.asarray(xs, dtype=np.float64)
    return {f"p{q}": float(np.percentile(a, q)) for q in qs}


def _paired(a, b):
    """같은 시드 짝 차 a − b 의 평균·t (자유도 n − 1)."""
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    n = len(d)
    if n < 2:
        return dict(diff=float(d.mean()) if n else None, t=None)
    sd = d.std(ddof=1)
    return dict(diff=float(d.mean()), t=float(d.mean() / (sd / math.sqrt(n))) if sd > 0 else None)


def _ratio(x, y):
    return float(x) / float(y) if y else None


def summarize_cell(rows: list[dict]) -> dict:
    from env_v2.repertoire import BEHAVIOR_NAMES

    import eval_v3 as ev

    rows = sorted(rows, key=lambda r: r["seed"])
    beh = np.sum([r["beh"] for r in rows], axis=0).astype(np.float64)
    sw, fl = sum(r["switch"] for r in rows), sum(r["flicker"] for r in rows)
    n = sum(r["n"] for r in rows)
    ucnt = {u: np.sum([r["u_cnt"][u] for r in rows], axis=0) for u in rows[0]["u_cnt"]}
    B = [r["bouts"] for r in rows]
    lengths = [x for b in B for x in b["lengths"]]
    s = lambda k: sum(b[k] for b in B)            # noqa: E731
    n_end, pursued, stopgo = s("n_end"), s("pursued"), s("stopgo")
    cls_purs = np.sum([b["cls_purs"] for b in B], axis=0)
    cls_near = np.sum([b["cls_near"] for b in B], axis=0)
    after = np.sum([b["after"] for b in B], axis=0)
    d_all = [x for b in B for x in b["d_all"]]
    d_purs = [x for b in B for x in b["d_purs"]]
    hist = np.histogram(lengths, bins=FLEE_LEN_BINS)[0] if lengths else np.zeros(len(FLEE_LEN_BINS) - 1)
    catch_n, catch_cov = sum(r["catch_n"] for r in rows), sum(r["catch_in_cover"] for r in rows)
    sleep_on = np.sum([r["sleep_on"] for r in rows], axis=0)
    out = dict(
        seeds=[r["seed"] for r in rows], steps=rows[0]["steps"],
        g_gamma=float(np.mean([r["g_gamma"] for r in rows])),
        pred_rate=float(np.mean([r["pred_rate"] for r in rows])),
        starve_rate=float(np.mean([r["starve_rate"] for r in rows])),
        death_rate=float(np.mean([r["pred_rate"] + r["starve_rate"] for r in rows])),
        pred_rate_night=float(np.nanmean([np.nan if r["pred_rate_night"] is None else r["pred_rate_night"] for r in rows])),
        pred_rate_day=float(np.nanmean([np.nan if r["pred_rate_day"] is None else r["pred_rate_day"] for r in rows])),
        use={b: float(beh[k] / beh.sum()) for k, b in enumerate(BEHAVIOR_NAMES)},
        flicker=_ratio(fl, sw),
        u={u: ev.u_value(ucnt[u]) for u in ucnt}, u_cnt={u: ucnt[u].tolist() for u in ucnt},
        flee=dict(n_bouts=len(lengths), censored=s("censored"), mean_len=float(np.mean(lengths)) if lengths else None,
                  len_pct=_pct(lengths), len_hist=dict(zip(["<8", "8", "9-15", "16-22", "23-45", "46-90", "91+"],
                                                           [int(x) for x in hist])),
                  n_end=n_end, n_death_end=s("n_death_end"),
                  bouts_per_1k=1000.0 * len(lengths) / n,
                  pursued_end_frac=_ratio(pursued, n_end),
                  stop_go_rate=_ratio(stopgo, n_end),
                  stop_go_given_pursued=_ratio(stopgo, pursued),
                  reflee_given_pursued=_ratio(s("reflee"), pursued),
                  caught3s_given_pursued=_ratio(s("caught_w"), pursued),
                  caught60_given_pursued=_ratio(s("caught60"), pursued),
                  stop_go_per_1k=1000.0 * stopgo / n,
                  quick_reflee_all=_ratio(s("quick_reflee_all"), n_end),
                  after={b: _ratio(after[k], n_end) for k, b in enumerate(BEHAVIOR_NAMES)},
                  end_dist=dict(**_pct(d_all), lt4=_ratio(sum(x < 4 for x in d_all), len(d_all)),
                                lt10=_ratio(sum(x < 10 for x in d_all), len(d_all)),
                                gt20=_ratio(sum(x > 20 for x in d_all), len(d_all))),
                  purs_dist=_pct(d_purs),
                  purs_dir={k: _ratio(cls_purs[i], cls_purs.sum()) for i, k in enumerate(("front120", "side", "rear60"))},
                  purs_seen_at_decision=_ratio(s("seen_purs"), pursued),
                  near_dir={k: _ratio(cls_near[i], cls_near.sum()) for i, k in enumerate(("front120", "side", "rear60"))},
                  len_sw_pct=_pct([x for b in B for x in b["len_sw"]]),
                  pursued_detail=_pursued_detail(B, BEHAVIOR_NAMES)),
        catch=dict(n=int(catch_n), in_cover=int(catch_cov), in_cover_share=_ratio(catch_cov, catch_n),
                   in_cover_per_1k=1000.0 * catch_cov / n),
        in_cover_frac=float(np.mean([r["in_cover_frac"] for r in rows])),
        sleep_onset=dict(n=int(sleep_on[0]), deer_within_8=int(sleep_on[1]), frac=_ratio(sleep_on[1], sleep_on[0])),
        pred_asleep_mean=float(np.mean([r.get("pred_asleep_mean", np.nan) for r in rows])),
        spy_fail=int(sum(r["spy_fail"] for r in rows)),
        per_seed={k: [r[k] for r in rows] for k in ("g_gamma", "pred_rate", "starve_rate")},
    )
    out["per_seed"]["death_rate"] = [r["pred_rate"] + r["starve_rate"] for r in rows]
    out["per_seed"]["stop_go_given_pursued"] = [_ratio(r["bouts"]["stopgo"], r["bouts"]["pursued"]) for r in rows]
    out["per_seed"]["pursued_end_frac"] = [_ratio(r["bouts"]["pursued"], r["bouts"]["n_end"]) for r in rows]
    # 1000 개체-스텝당 수(보고만, 사후 — PREREG 변경 기록): 도주 묶음, 쫓김 끝, 멈춤-재도주, 쫓김 끝 중 결정 때 안 보임, GRAZE 로 바꿈
    k1 = lambda r, x: 1000.0 * x / r["n"]          # noqa: E731
    out["per_seed"]["bouts_per_1k"] = [k1(r, len(r["bouts"]["lengths"])) for r in rows]
    out["per_seed"]["pursued_per_1k"] = [k1(r, r["bouts"]["pursued"]) for r in rows]
    out["per_seed"]["stop_go_per_1k"] = [k1(r, r["bouts"]["stopgo"]) for r in rows]
    out["per_seed"]["unseen_stop_per_1k"] = [k1(r, r["bouts"]["p_seen"][0][0]) for r in rows]
    out["per_seed"]["graze_stop_per_1k"] = [k1(r, r["bouts"]["p_after"][0][0]) for r in rows]
    out["flee"]["per_1k"] = {k: float(np.mean(out["per_seed"][k])) for k in
                             ("bouts_per_1k", "pursued_per_1k", "stop_go_per_1k", "unseen_stop_per_1k", "graze_stop_per_1k")}
    if "realism" in rows[0]:
        keys = rows[0]["realism"].keys()
        out["realism"] = {}
        for k in keys:
            vals = [r["realism"][k] for r in rows if r["realism"][k] is not None]
            if not vals:
                out["realism"][k] = None
            elif k.endswith("_n"):
                out["realism"][k] = float(np.sum(vals))
            else:
                out["realism"][k] = float(np.mean(vals))
    return out


def _pursued_detail(B, behavior_names) -> dict:
    """쫓김 끝을 바꾼 행동·쫓는 위협 종류·결정 때 보임·끝 위치(은신처)로 나눈 [끝 수, 멈춤-재도주 비율]."""
    out = {}
    for key, labels in (("p_after", behavior_names), ("p_kind", ("chaser", "ranged", "stalker", "player")),
                        ("p_seen", ("unseen", "seen")), ("p_cov", ("open", "in_cover"))):
        if key not in B[0]:
            continue
        a = np.sum([b[key] for b in B], axis=0)
        tot = a[:, 0].sum()
        out[key[2:]] = {lab: dict(n=int(a[i, 0]), share=_ratio(a[i, 0], tot), stop_go=_ratio(a[i, 1], a[i, 0]))
                        for i, lab in enumerate(labels) if i < len(a)}
    return out


def _obs_pool(rows):
    o = [r["obs"] for r in rows]
    return dict(h_all=np.sum([x["h_all"] for x in o], axis=0), h_dec=np.sum([x["h_dec"] for x in o], axis=0),
                h_cond=np.sum([x["h_cond"] for x in o], axis=0),
                mn_all=np.min([x["mn_all"] for x in o], axis=0), mx_all=np.max([x["mx_all"] for x in o], axis=0),
                mn_dec=np.min([x["mn_dec"] for x in o], axis=0), mx_dec=np.max([x["mx_dec"] for x in o], axis=0),
                out01=int(sum(x["out01"] for x in o)), j1=np.sum([x["j1"] for x in o], axis=0),
                j1_max=float(max(x["j1_max"] for x in o)))


def _hpct(h, qs=(1, 5, 50, 95, 99)):
    c = np.cumsum(h)
    tot = c[-1]
    if tot == 0:
        return {f"p{q}": None for q in qs}
    return {f"p{q}": float((np.searchsorted(c, q / 100.0 * tot) + 0.5) / len(h)) for q in qs}


def _coarse(h):
    return np.asarray(h).reshape(NB_FLAG, NB // NB_FLAG).sum(1)


def obs_check(var: dict, ref: dict, names) -> dict:
    """PREREG 3절: 범위 밖(OUT)·지지 밖(SUPPORT)·분포 이동(SHIFT, 보고만)·결합 범위 J1."""
    feats = {}
    for k, nm in enumerate(names):
        one = {}
        # 범위(min·max)는 기준의 모든 개체-스텝으로 본다(결정 표본은 그 부분집합). 분포(지지·전변동·백분위)는 같은 종류끼리
        # 비교한다: 모든 개체-스텝은 기준의 모든 개체-스텝과, 결정 표본은 기준의 결정 표본과
        for part, (h, mn, mx), rh in (("all", (var["h_all"][k], var["mn_all"][k], var["mx_all"][k]), ref["h_all"][k]),
                                      ("dec", (var["h_dec"][k], var["mn_dec"][k], var["mx_dec"][k]), ref["h_dec"][k])):
            rf_c = _coarse(rh)
            rf_p = rf_c / max(rf_c.sum(), 1)
            h = np.asarray(h)
            tot = h.sum()
            lo, hi = ref["mn_all"][k], ref["mx_all"][k]
            # 범위 밖 몫: 기준 최솟값·최댓값을 넘는 칸의 표본(칸 단위라 경계 칸은 정확한 min·max 로 따로 본다)
            edges = np.arange(NB) / NB
            below = (edges + 1.0 / NB <= lo - EPS_RANGE)
            above = (edges >= hi + EPS_RANGE)
            out_share = float(h[below | above].sum() / tot) if tot else None
            vc = _coarse(h)
            vp = vc / vc.sum() if vc.sum() else vc
            sup = float(vp[rf_c == 0].sum()) if vc.sum() else None
            tv = float(0.5 * np.abs(vp - rf_p).sum()) if vc.sum() else None
            one[part] = dict(min=float(mn), max=float(mx), ref_min=float(lo), ref_max=float(hi),
                             out_min=bool(mn < lo - EPS_RANGE), out_max=bool(mx > hi + EPS_RANGE),
                             out_share=out_share, support_out=sup, tv=tv, pct=_hpct(h), ref_pct=_hpct(rh))
        a = one["all"]
        d = one["dec"]
        one["flag_out"] = bool(a["out_min"] or a["out_max"] or d["out_min"] or d["out_max"])
        one["flag_support"] = bool((a["support_out"] or 0) > 1e-3 or (d["support_out"] or 0) > 1e-3)
        one["flag_shift"] = bool((a["tv"] or 0) > 0.05 or (d["tv"] or 0) > 0.05)
        feats[nm] = one
    cond = {}
    for k, nm in enumerate(COND_NAMES):
        hv, hr = np.asarray(var["h_cond"][k]), np.asarray(ref["h_cond"][k])
        vc, rc = _coarse(hv), _coarse(hr)
        cond[nm] = dict(n=int(hv.sum()), ref_n=int(hr.sum()), pct=_hpct(hv), ref_pct=_hpct(hr),
                        tv=float(0.5 * np.abs(vc / max(vc.sum(), 1) - rc / max(rc.sum(), 1)).sum()) if vc.sum() else None,
                        support_out=float((vc / vc.sum())[rc == 0].sum()) if vc.sum() else None)
    return dict(features=feats, cond=cond, out01=var["out01"], j1=dict(seen=int(var["j1"][0]), viol=int(var["j1"][1]),
                                                                        max_excess=var["j1_max"]),
                flags=dict(out=[nm for nm in names if feats[nm]["flag_out"]],
                           support=[nm for nm in names if feats[nm]["flag_support"]],
                           shift=[nm for nm in names if feats[nm]["flag_shift"]]))


def aggregate(results: list[dict], names) -> dict:
    cells = {}
    for r in results:
        cells.setdefault((r["variant"], r["policy"]), []).append(r)
    summ = {f"{v}|{p}": summarize_cell(rows) for (v, p), rows in cells.items()}
    # 짝 비교: 같은 정책의 base 대비(시드 짝), 같은 세계의 rl − rbase
    for key, c in summ.items():
        v, p = key.split("|")
        base = summ.get(f"base|{p}")
        if base is not None and v != "base" and base["seeds"] == c["seeds"]:
            c["vs_base"] = {k: _paired(c["per_seed"][k], base["per_seed"][k])
                            for k in ("g_gamma", "pred_rate", "starve_rate", "death_rate")}
            c["vs_base"]["rel"] = {k: (c[k] / base[k] - 1.0) if base[k] else None
                                   for k in ("pred_rate", "starve_rate", "death_rate")}
            for k in ("stop_go_given_pursued", "pursued_end_frac", "bouts_per_1k", "pursued_per_1k", "stop_go_per_1k",
                      "unseen_stop_per_1k", "graze_stop_per_1k"):
                a, b = c["per_seed"][k], base["per_seed"][k]
                ok = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
                c["vs_base"][k] = _paired([x for x, _ in ok], [y for _, y in ok])
        if p == "rl":
            rb = summ.get(f"{v}|rbase")
            if rb is not None and rb["seeds"] == c["seeds"]:
                c["vs_rbase"] = {k: _paired(c["per_seed"][k], rb["per_seed"][k]) for k in ("g_gamma", "death_rate")}
    obs = {}
    ref_rows = [r for r in results if r["policy"] == "rl" and r["variant"] in REF_VARIANTS]
    if ref_rows:
        ref = _obs_pool(ref_rows)
        for (v, p), rows in cells.items():
            if p == "rl" and v != "train_ref":
                obs[v] = obs_check(_obs_pool(rows), ref, names)
        obs["_ref"] = dict(variants=list(REF_VARIANTS), n=int(ref["h_all"][0].sum()), j1=ref["j1"].tolist(),
                           out01=ref["out01"])
        # 같은 학습 세계 표본끼리의 '거짓 경보' 눈금(보고만): base 를 train_ref 하나만으로, train_ref 를 base 하나만으로 잰다
        b_rows = [r for r in ref_rows if r["variant"] == "base"]
        t_rows = [r for r in ref_rows if r["variant"] == "train_ref"]
        if b_rows and t_rows:
            obs["_null"] = {"base_vs_train_ref": obs_check(_obs_pool(b_rows), _obs_pool(t_rows), names),
                            "train_ref_vs_base": obs_check(_obs_pool(t_rows), _obs_pool(b_rows), names)}
    hist = {}
    for (v, p), rows in cells.items():
        if p == "rl":
            o = _obs_pool(rows)
            hist[v] = {k: (x.tolist() if isinstance(x, np.ndarray) else x) for k, x in o.items()}
    return dict(summary=summ, obs=obs, _hist=hist)


# --------------------------------------------------------------------- #
# 표
# --------------------------------------------------------------------- #


def _f(x, nd=4):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def _pc(x, nd=1):
    return "—" if x is None else f"{100 * x:.{nd}f}%"


def _t(d):
    if d is None or d.get("t") is None:
        return "—"
    return f"{d['t']:+.2f}"


def tables(agg: dict, title: str) -> str:
    S = agg["summary"]
    L = [f"# {title}", "", "자동 생성 표(`eval_real1.py`). 정의는 `PREREG.md`.", ""]
    for p in POLICIES:
        L += [f"## {p} — 생존·성과", "",
              "| 세계 | 피식률 | Δ피식 (t) | 아사율 | Δ아사 (t) | 합 사망 Δ (t) | G_γ | ΔG_γ (t) | GRAZE/FLEE/HIDE/FREEZE | 깜빡임 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for v in VARIANT_ORDER:
            c = S.get(f"{v}|{p}")
            if c is None:
                continue
            vb = c.get("vs_base")
            u = c["use"]
            use = "/".join(_pc(u[b], 1) for b in ("graze", "flee", "hide", "freeze"))
            if vb:
                rel = vb["rel"]
                dp = f"{_pc(rel['pred_rate'], 0)} ({_t(vb['pred_rate'])})"
                dsv = f"{_pc(rel['starve_rate'], 0)} ({_t(vb['starve_rate'])})"
                dd = f"{_pc(rel['death_rate'], 0)} ({_t(vb['death_rate'])})"
                dg = f"{vb['g_gamma']['diff']:+.3f} ({_t(vb['g_gamma'])})"
            else:
                dp = dsv = dd = dg = "기준"
            L.append(f"| {v} | {_f(c['pred_rate'], 6)} | {dp} | {_f(c['starve_rate'], 6)} | {dsv} | {dd} | "
                     f"{_f(c['g_gamma'], 3)} | {dg} | {use} | {_f(c['flicker'], 2)} |")
        L += ["", f"## {p} — 도주 묶음·멈췄다 다시 뛰기", "",
              "| 세계 | 묶음 수 | 길이 p25/p50/p75/p90 (스텝) | 끝 중 쫓김 | 멈춤-재도주 비율 | 쫓김 끝 중 멈춤-재도주 | ↳ 3초 안 다시 도주 | ↳ 3초 안 잡힘 | 쫓김 끝 60스텝 안 잡힘 | 끝 거리 p25/p50/p75 | 쫓는 위협 방향 앞/옆/뒤 | 결정 때 보였나 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for v in VARIANT_ORDER:
            c = S.get(f"{v}|{p}")
            if c is None:
                continue
            fl = c["flee"]
            lp, ed, pdr = fl["len_pct"], fl["end_dist"], fl["purs_dir"]
            L.append(f"| {v} | {fl['n_bouts']} | {_f(lp['p25'], 0)}/{_f(lp['p50'], 0)}/{_f(lp['p75'], 0)}/{_f(lp['p90'], 0)} | "
                     f"{_pc(fl['pursued_end_frac'])} | {_pc(fl['stop_go_rate'])} | {_pc(fl['stop_go_given_pursued'])} | "
                     f"{_pc(fl['reflee_given_pursued'])} | {_pc(fl['caught3s_given_pursued'])} | "
                     f"{_pc(fl['caught60_given_pursued'])} | {_f(ed['p25'], 1)}/{_f(ed['p50'], 1)}/{_f(ed['p75'], 1)} | "
                     f"{_pc(pdr['front120'], 0)}/{_pc(pdr['side'], 0)}/{_pc(pdr['rear60'], 0)} | "
                     f"{_pc(fl['purs_seen_at_decision'], 0)} |")
        L += ["", f"## {p} — 쫓김 끝 자세히 (몫 · 그중 멈춤-재도주)", "",
              "| 세계 | 바꾼 행동 GRAZE | HIDE | FREEZE | 결정 때 안 보임 | 보임 | 끝 위치 은신처 안 | 쫓는 위협 추격/원거리/잠행/플레이어 |",
              "|---|---|---|---|---|---|---|---|"]
        for v in VARIANT_ORDER:
            c = S.get(f"{v}|{p}")
            if c is None or "pursued_detail" not in c["flee"]:
                continue
            pdt = c["flee"]["pursued_detail"]
            cell = lambda x: f"{_pc(x['share'], 0)} · {_pc(x['stop_go'], 0)}"      # noqa: E731
            kd = pdt["kind"]
            L.append(f"| {v} | {cell(pdt['after']['graze'])} | {cell(pdt['after']['hide'])} | {cell(pdt['after']['freeze'])} | "
                     f"{cell(pdt['seen']['unseen'])} | {cell(pdt['seen']['seen'])} | {cell(pdt['cov']['in_cover'])} | "
                     + "/".join(_pc(kd[k]['share'], 0) for k in ("chaser", "ranged", "stalker", "player")) + " |")
        L += ["", f"## {p} — 1000 개체-스텝당 수 (보고만, 사후) — 값 (base 대비 t)", "",
              "| 세계 | 도주 묶음 | 쫓김 끝 | 멈춤-재도주 | 쫓김 끝 & 결정 때 안 보임 | 쫓김 끝 & GRAZE 로 바꿈 |", "|---|---|---|---|---|---|"]
        for v in VARIANT_ORDER:
            c = S.get(f"{v}|{p}")
            if c is None or "per_1k" not in c["flee"]:
                continue
            pk = c["flee"]["per_1k"]
            vb = c.get("vs_base") or {}
            L.append(f"| {v} | " + " | ".join(f"{pk[k]:.3f} ({_t(vb.get(k))})" for k in
                                             ("bouts_per_1k", "pursued_per_1k", "stop_go_per_1k", "unseen_stop_per_1k",
                                              "graze_stop_per_1k")) + " |")
        L += ["", f"## {p} — 길이 분포(묶음 수)·은신처 안 포획·U", "",
              "| 세계 | <8 | 8 | 9-15 | 16-22 | 23-45 | 46-90 | 91+ | 포획 수 | 은신처 안 포획 | 은신처 안 시간 | U_ESC | U_HIDE′ | U_FREEZE′ |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for v in VARIANT_ORDER:
            c = S.get(f"{v}|{p}")
            if c is None:
                continue
            hh = c["flee"]["len_hist"]
            u = c["u"]
            L.append(f"| {v} | " + " | ".join(str(hh[k]) for k in hh) +
                     f" | {c['catch']['n']} | {c['catch']['in_cover']} ({_pc(c['catch']['in_cover_share'])}) | "
                     f"{_pc(c['in_cover_frac'])} | {_f(u['esc'], 3)} | {_f(u['hide'], 3)} | {_f(u['freeze'], 3)} |")
        L.append("")
    O = agg.get("obs") or {}
    if O:
        L += ["## rl — 관측 범위 (기준: rl 의 base ∪ train_ref, 모든 개체-스텝)", "",
              f"기준 표본 {O['_ref']['n']} 개체-스텝. OUT = 기준 최솟값·최댓값 밖 값이 있음, SUPPORT = 기준에 표본이 없는 0.01 칸에 "
              "0.1% 넘게, SHIFT(보고만) = 전변동 거리 > 0.05. J1 = 보이는 위협의 pred_dist > visibility × 행동 배수.", "",
              "| 세계 | OUT | SUPPORT | SHIFT | J1 위반 / 보임 표본 | [0,1] 밖 |", "|---|---|---|---|---|---|"]
        for v in VARIANT_ORDER:
            o = O.get(v)
            if o is None:
                continue
            fg = o["flags"]
            L.append(f"| {v} | {', '.join(fg['out']) or '없음'} | {', '.join(fg['support']) or '없음'} | "
                     f"{', '.join(fg['shift']) or '없음'} | {o['j1']['viol']} / {o['j1']['seen']} | {o['out01']} |")
        for nm, o in (O.get("_null") or {}).items():
            fg = o["flags"]
            L.append(f"| (눈금) {nm} | {', '.join(fg['out']) or '없음'} | {', '.join(fg['support']) or '없음'} | "
                     f"{', '.join(fg['shift']) or '없음'} | {o['j1']['viol']} / {o['j1']['seen']} | {o['out01']} |")
        L += ["", "### 특성별 (all 세계, 결정 표본) — min/max·p1/p50/p99 대 기준, 전변동 거리", "",
              "| 특성 | min (기준) | max (기준) | p1 | p50 | p99 | 기준 p1/p50/p99 | TV 결정 | TV 전체 |", "|---|---|---|---|---|---|---|---|---|"]
        o = O.get("all")
        if o:
            for nm, x in o["features"].items():
                d, a = x["dec"], x["all"]
                rp = d["ref_pct"]
                L.append(f"| {nm} | {_f(d['min'], 3)} ({_f(d['ref_min'], 3)}) | {_f(d['max'], 3)} ({_f(d['ref_max'], 3)}) | "
                         f"{_f(d['pct']['p1'], 3)} | {_f(d['pct']['p50'], 3)} | {_f(d['pct']['p99'], 3)} | "
                         f"{_f(rp['p1'], 3)}/{_f(rp['p50'], 3)}/{_f(rp['p99'], 3)} | {_f(d['tv'], 3)} | {_f(a['tv'], 3)} |")
        L += ["", "### 조건부 분포 (모든 개체-스텝) — p5/p50/p95 대 기준, 전변동 거리", "",
              "| 세계 | " + " | ".join(COND_NAMES) + " |", "|---|" + "---|" * len(COND_NAMES)]
        for v in VARIANT_ORDER:
            o = O.get(v)
            if o is None:
                continue
            cells = []
            for nm in COND_NAMES:
                cc = o["cond"][nm]
                p_ = cc["pct"]
                cells.append(f"{_f(p_['p5'], 2)}/{_f(p_['p50'], 2)}/{_f(p_['p95'], 2)} (TV {_f(cc['tv'], 3)})")
            L.append(f"| {v} | " + " | ".join(cells) + " |")
        rc = O.get("base")
        if rc:
            L += ["", "기준(base ∪ train_ref)의 조건부 p5/p50/p95: " + "; ".join(
                f"{nm} {_f(rc['cond'][nm]['ref_pct']['p5'], 2)}/{_f(rc['cond'][nm]['ref_pct']['p50'], 2)}/"
                f"{_f(rc['cond'][nm]['ref_pct']['p95'], 2)}" for nm in COND_NAMES)]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------- #


def _map(jobs, workers):
    from env.rollout import _init_worker

    if workers <= 1:
        return [job(j) for j in jobs]
    with ProcessPoolExecutor(min(workers, len(jobs)), initializer=_init_worker) as ex:
        return list(ex.map(job, jobs, chunksize=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "smoke", "tables", "verify"))
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--long", action="store_true")
    a = ap.parse_args()
    import os

    os.chdir(ROOT)
    from env_v2.world import obs_names

    names = list(obs_names(load_variant("base")))
    if a.cmd == "verify":
        _check_seeds([32000, 32001])
        print(verify([32000, 32001], 600))
        return
    if a.cmd == "smoke":
        _check_seeds(SMOKE_SEEDS)
        jobs = [(v, p, s, 200) for v in ("base", "all") for p in POLICIES for s in SMOKE_SEEDS]
        res = _map(jobs, a.workers)
        agg = aggregate(res + [dict(r, variant="train_ref") for r in res if r["variant"] == "base" and r["policy"] == "rl"],
                        names)
        print(tables(agg, "smoke"))
        print({r["variant"] + "|" + r["policy"]: round(r["sec"], 1) for r in res})
        return
    tag = "real1_long" if a.long else "real1"
    if a.cmd == "tables":
        agg = json.loads((OUT_DIR / f"{tag}.json").read_text(encoding="utf-8"))
        (OUT_DIR / f"tables{'_long' if a.long else ''}.md").write_text(tables(agg, tag), encoding="utf-8")
        return
    seeds, steps = (LONG_SEEDS, LONG_STEPS) if a.long else (SEEDS, STEPS)
    _check_seeds(seeds)
    variants = LONG_VARIANTS if a.long else VARIANT_ORDER
    jobs = [(v, p, s, steps) for v in variants for p in POLICIES for s in seeds]
    jobs += [("train_ref", "rl", s, steps) for s in seeds]
    t0 = time.time()
    res = _map(jobs, a.workers)
    agg = aggregate(res, names)
    agg["meta"] = dict(model=MODEL, seeds=seeds, steps=steps, variants={v: VARIANTS[v] for v in list(variants) + ["train_ref"]},
                       policies=list(POLICIES), gamma=GAMMA, tail=TAIL, win_steps=WIN, pursue_r=PURSUE_R,
                       wall_sec=time.time() - t0, obs_names=names)
    drop = ("lengths", "len_sw", "len_death", "d_all", "d_purs")
    agg["raw"] = [dict({k: v for k, v in r.items() if k not in ("obs", "bouts")},
                       bouts={k: v for k, v in r["bouts"].items() if k not in drop}) for r in res]
    hist = agg.pop("_hist")
    (OUT_DIR / f"{tag}_obs_hist.json").write_text(json.dumps(dict(names=names, nb=NB, cond=list(COND_NAMES), hist=hist),
                                                             default=_json_default), encoding="utf-8")
    (OUT_DIR / f"{tag}.json").write_text(json.dumps(agg, ensure_ascii=False, indent=1, default=_json_default),
                                         encoding="utf-8")
    (OUT_DIR / f"tables{'_long' if a.long else ''}.md").write_text(tables(agg, tag), encoding="utf-8")
    print(f"wrote {tag}.json in {time.time() - t0:.0f}s")


def verify(seeds, steps) -> dict:
    """Spy(기록만)가 궤적을 바꾸지 않는지: 같은 시드·정책으로 World 와 Spy 를 나란히 돌려 스텝마다 보상·죽음·위치·포식자 위치·
    행동이 비트 단위로 같은지 본다(base·all × rl·rbase)."""
    from env_v2 import rollout as ro
    from env_v2.world import World

    out = {}
    Spy = _spy_class()
    for v in ("base", "all"):
        cfg = load_variant(v)
        for p in POLICIES:
            for s in seeds:
                ws = []
                for cls in (World, Spy):
                    w = cls(cfg, seeds=[s])
                    if cls is Spy:
                        w._spy_init()
                    pol = make_policy(p, cfg, s)
                    ro.forward_bind(pol, w)
                    ws.append((w, pol))
                same = True
                for t in range(steps):
                    acts = []
                    for w, pol in ws:
                        obs = w.observe()
                        w.rep_peek()
                        acts.append(np.asarray(pol(obs), dtype=np.float64))
                    res = []
                    for (w, pol), a_ in zip(ws, acts):
                        _, r, d_, _ = w.step(a_)
                        ro.forward_done(pol, d_)
                        res.append((r.copy(), d_.copy(), w.pos.copy(), w.pred_pos.copy(), w.behavior.copy()))
                    same &= all(np.array_equal(x, y) for x, y in zip(res[0], res[1]))
                    same &= np.array_equal(acts[0], acts[1])
                    if not same:
                        break
                out[f"{v}|{p}|{s}"] = dict(same=bool(same), steps=t + 1, spy_fail=int(ws[1][0].spy_fail))
    return out


def _json_default(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    raise TypeError(type(x))


if __name__ == "__main__":
    main()
