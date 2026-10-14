"""v3 R3 재학습 전 측정 — 지금 두뇌(R1b s3)를 얼기만 막아(R1b−F) R3 세계에 얹어 본다. 손 규칙·상수 대조와 규칙 하나씩 뺀 세계도 잰다.
명세 `Docs/RL_Policy/RL_V3_R3_SPEC.md` 4-8 '재학습 전 측정', 4-9 '잴 것', 7-2 세계 점검 T0·사용자 추격 모형 확인표, 10절 포기율 A.
사전 기록 `PREREG.md`(같은 폴더).

    # herbivore_rl/ 에서
    python results/v3/r3/pre/eval_pre.py run --workers 16     # 본 측정 → pre.json(요약), pre_raw.json(시드별), pre_obs_hist.json, tables.md
    python results/v3/r3/pre/eval_pre.py tables               # pre.json·pre_raw.json 에서 tables.md 만 다시 쓴다
    python results/v3/r3/pre/eval_pre.py smoke                # 탐색 시드 32000 × 200스텝, 저장하지 않는다
    python results/v3/r3/pre/eval_pre.py verify               # Spy 가 궤적을 바꾸지 않는지(탐색 시드 32000~32001)

판정이 아니라 측정이다. 학습하지 않고 환경 코드(env_v2/*)도 바꾸지 않는다. 세계 안을 엿보는 것은 `Spy`(World 를 상속해
`_step_predators_v3`·`_threat_motion`·`_threat_after` 를 감싼다 — 기록만 하고 상태·난수를 바꾸지 않는다)뿐이다.
1단계 측정 도구 `results/v3/real1/eval_real1.py` 에서 도주 묶음·관측 범위 코드를 옮겨 왔고, R3 지표(포기율 A, T0, 확인표, 은신처
몰림·먹이, 늑대 둘레 미끄러짐, 밤 활동)를 더했다.

- 정책: rlf = R1b s3(`ckpt/v3/v3_r1_g995_s3_20m.zip`, argmax, 마스크 판 2)에서 허용 목록의 FREEZE 만 뺀 것(R1b−F, 명세 5-4),
  rl = R1b s3 그대로(얼기 씀 — 허용 목록에 freeze 를 넣은 사본 세계에서만), rbase = R_base(θ 4, a 0.9)(`eval_v3.fsm_spec(cfg,
  ('graze','flee'), 'near')`), c_graze·c_flee·c_hide = 늘 그 행동 요청(가능하지 않으면 GRAZE, `eval_v3.ConstRequest`).
- 세계(VARIANTS): r3 = configs/v3_r3_on.yaml(R3 판정 세계), no_chase·no_wall·no_terrain = 추격 고정·늑대 은신처 진입 금지·지형 하나씩
  메모리에서 끈 판, r3_fz = r3 에 허용 목록 freeze 를 더한 사본(세계 동역학은 r3 와 같다 — 원래 R1b 보고용), base = configs/v3_r1_on.yaml
  (R1b 판정 세계), night = configs/v3_real1_night_on.yaml(R1 세계 + 늑대 밤잠 점진화 — H1 로 R3 전에 게임에 들어가는 세계),
  train_ref = configs/v3_r1.yaml(R1b 학습 설정 — 관측 범위 기준으로만).
- 시드: 보정 20000~20019 × 3000스텝. 도구 점검은 탐색 32000~32001. 판정 시드는 쓰지 않는다(시작 전에 막는다).
- 시간: 1스텝 = 2/15 s, 3 s = 22스텝, 1분 = 450스텝.
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
ROOT = HERE.parents[4]                       # herbivore_rl
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

MODEL = "ckpt/v3/v3_r1_g995_s3_20m.zip"
SEEDS = list(range(20000, 20020))
STEPS = 3000
SMOKE_SEEDS = [32000]
VERIFY_SEEDS = [32000, 32001]
# 판정·예약 시드(명세 11절 '쓰지 않음', R3 관문·최종 판정 15000~15039·10300~10319 포함)
FORBIDDEN = [range(10000, 10020), range(10100, 10120), range(10200, 10220), range(10300, 10320), range(12000, 12240),
             range(14000, 14040), range(15000, 15040), range(30000, 30024), range(31000, 31306), range(41000, 41040),
             range(42000, 42010)]
ALLOWED = [range(20000, 20020), range(32000, 32100), range(33000, 33100)]

R3_ON = "configs/v3_r3_on.yaml"
VARIANTS = {
    "r3": (R3_ON, None),
    "no_chase": (R3_ON, {"features": {"realism_chase": {"enabled": False}}}),
    "no_wall": (R3_ON, {"features": {"realism_shelter": {"block_predators": False}}}),
    "no_terrain": (R3_ON, {"features": {"realism_terrain": {"enabled": False}}}),
    "r3_fz": (R3_ON, {"allowed": ["graze", "flee", "hide", "freeze"]}),
    "base": ("configs/v3_r1_on.yaml", None),
    "night": ("configs/v3_real1_night_on.yaml", None),
    "train_ref": ("configs/v3_r1.yaml", None),
}
R3_FAMILY = ("r3", "no_chase", "no_wall", "no_terrain")
R3_POLICIES = ("rlf", "rbase", "c_graze", "c_flee", "c_hide")
EXTRA_CELLS = (("r3_fz", "rl"), ("base", "rl"), ("base", "rlf"), ("night", "rl"), ("night", "rlf"), ("train_ref", "rl"))
CELLS = tuple((v, p) for v in R3_FAMILY for p in R3_POLICIES) + EXTRA_CELLS
REF_VARIANTS = ("base", "train_ref")         # 관측 범위 기준(rl 만)
OBS_POLICIES = ("rl", "rlf")                 # 관측 히스토그램을 모으는 정책

GAMMA = 0.9916661555611042                   # eval_v3.GAMMA
TAIL = 600                                   # eval_v3.TAIL
WIN = 22                                     # 3 s
WIN60 = 60
MINUTE = 450                                 # 1분 = 450스텝
PURSUE_R = 10.0                              # '쫓는 위협이 실거리 10 안'(명세 3-1 '안전', 10절 A)
SETTLE_R = 8.0
COS_FRONT = math.cos(math.radians(60.0))
COS_REAR = math.cos(math.radians(150.0))
NB = 1000
NB_FLAG = 100
EPS_RANGE = 1e-6
J1_TOL = 1e-4
FLEE_LEN_BINS = (0, 8, 9, 16, 23, 46, 91, 10 ** 9)
COND_NAMES = ("pred_dist|seen", "pred_approach|seen", "food_density|in_cover", "threat_recency|unseen")
RIM_TOL = 1e-3                               # 늑대가 은신처 원 둘레에 붙어 있음: 0 ≤ (중심 거리 − r) < RIM_TOL (밀어낸 자리는 r + 1e-6)
STILL_TOL = 1e-3                             # 이번 스텝 이동 < 이 값이면 '제자리'
RUN_BINS = (1, 2, 3, 6, 11, 31, 10 ** 9)     # 끼임 연속 스텝 칸 [a, b): 1, 2, 3~5, 6~10, 11~30, 31+
FOOD_EVERY = 10                              # 은신처 먹이 채움 표본 간격(스텝)
LAT_MAX = 60                                 # 쫓김 시작 → 첫 반응 스텝 히스토그램 끝 칸(60+)
# 명세 7-2 관문 니치 초안(보고만): G1 도주 중 & s & a ≥ 0.6 & d < 10 & c > 0 (교차 a < 0.5 & d ≥ 8), G2 s & 0 < c ≤ 6 & d ≥ 6
# (교차 c > 12), G3 c = 0 & K & (¬s ∨ d ≥ 10) & E < 0.35 (교차 E > 0.7)
G_COND = dict(g1_app=0.6, g1_d=10.0, g1x_app=0.5, g1x_d=8.0, g2_c=6.0, g2_d=6.0, g2x_c=12.0, g3_d=10.0, g3_e=0.35, g3x_e=0.7,
              recency=0.2)

# 확인표 칸
TERR_LABELS = ("normal", "snow", "rough", "none")          # none = 지형이 없는 세계
POUNCE_CATS = ("flee_run", "flee_startle", "hide_go", "freeze", "graze_seen", "graze_unseen", "other")
POUNCE_OUT = ("hit", "hit_other", "miss", "censored")
DIST_BINS = (0.0, 2.0, 4.0, 10 ** 9)                       # 돌진 시작 거리 칸 [0, 2), [2, 4), 4+ (돌진 판정은 체감 거리 ≤ 6)
DIST_LABELS = ("<2", "2-4", "4+")
FOLLOW_LABELS = ("fresh", "follow")                         # 새 사냥 / 이어 사냥(직전 3초 안에 잡은 위협)
CHASE_CATS = ("none", "stop_graze", "freeze", "hide", "kept")
CHASE_OUT = ("caught", "cover", "far", "starved", "censored")
KINDS = ("chaser", "ranged", "stalker", "player")
PHASES = ("day", "twilight", "night")


def _check_seeds(seeds) -> None:
    for s in seeds:
        if any(s in r for r in FORBIDDEN):
            raise SystemExit(f"판정·예약 시드 {s} 는 쓰지 않는다")
        if not any(s in r for r in ALLOWED):
            raise SystemExit(f"시드 {s} 는 보정 20000~20019·탐색 32000~32099·33000~33099 밖이다")


def load_variant(name: str):
    from env_v2.config import load_v2_config

    path, mod = VARIANTS[name]
    cfg = load_v2_config(ROOT / path)
    if mod:
        v2 = dict(cfg.v2)
        if "features" in mod:
            f = {k: dict(v) for k, v in v2["features"].items()}
            for b, kv in mod["features"].items():
                f[b] = dict(f[b], **kv)
            v2["features"] = f
        if "allowed" in mod:
            tr = dict(v2["train"])
            rp = dict(tr["repertoire"])
            rp["allowed"] = list(mod["allowed"])
            tr["repertoire"] = rp
            v2["train"] = tr
        cfg = cfg.replace(v2=v2)
    return cfg


_SPY = None


def _spy_class():
    global _SPY
    if _SPY is None:
        _SPY = _make_spy()
    return _SPY


def _make_spy():
    from env_v2.steering import EPS
    from env_v2.world import PM_CHARGE, PM_STALK, PT_STALKER, ST_POUNCE, ST_ROAM, World

    class Spy(World):
        """기록만 하는 World. `_step_predators_v3` 앞에서 이번 스텝 실행 행동·보행·초식 이동 뒤 위치를, `_threat_motion` 앞뒤에서
        잠행형·플레이어 상태 전이(돌진 시작)를, `_threat_after` 에서 위협별 포획(got)을 남긴다. 표적은 세계 훅 `pred_target`(현실성·R3
        세계)을 쓰고, 훅이 없는 세계(base·train_ref)는 1단계처럼 이동 방향(표적 쪽 단위 벡터)으로 되찾는다. 상태·난수를 바꾸지 않는다."""

        def _spy_init(self):
            self.spy_prev_tgt = np.full(self.M, -1, dtype=np.int64)
            self.spy_tgt = np.full(self.M, -1, dtype=np.int64)
            self.spy_fail = 0
            self.spy = None
            self.spy_motion = None
            self.spy_got = np.zeros(self.M, dtype=bool)

        def _threat_motion(self, move, speed, wander, has_target, d_t, exh0, rest0):
            M = self.M
            tgt_dir = None
            if not (self._rz or self._r3):
                tgt_dir = np.full(M, -1, dtype=np.int64)
                idx = np.flatnonzero(has_target)
                if len(idx):
                    v = self.pos[None, :, :] - self.pred_pos[idx][:, None, :]
                    d = np.sqrt((v * v).sum(2))
                    cs = (v * move[idx][:, None, :]).sum(2) / np.maximum(d, EPS)
                    dd = np.where(cs > 1.0 - 1e-9, d, np.inf)
                    k = dd.argmin(1)
                    ok = np.isfinite(dd[np.arange(len(idx)), k])
                    self.spy_fail += int(np.count_nonzero(~ok))
                    tgt_dir[idx] = np.where(ok, k, cs.argmax(1))
            st0, pm0 = self.stalk_state.copy(), self.player_mode.copy()
            out = super()._threat_motion(move, speed, wander, has_target, d_t, exh0, rest0)
            st1, pm1 = self.stalk_state.copy(), self.player_mode.copy()
            stalker = self.pred_type == PT_STALKER
            self.spy_motion = dict(has_target=has_target.copy(), tgt_dir=tgt_dir, st1=st1, pm1=pm1,
                                   pounce_start=stalker & (st0 == ST_ROAM) & (st1 == ST_POUNCE),
                                   charge_start=self.pred_is_player & (pm0 == PM_STALK) & (pm1 == PM_CHARGE))
            return out

        def _threat_after(self, got, ts):
            self.spy_got = np.asarray(got, dtype=bool).copy()
            return super()._threat_after(got, ts)

        def _step_predators_v3(self):
            pre = dict(beh=self._rs.behavior.astype(np.int8).copy(), gait=np.asarray(self.gait).astype(np.int8).copy(),
                       pos=self.pos.copy(), in_cov=self._in_cover(self.pos))
            self.spy_motion = None
            self.spy_got = np.zeros(self.M, dtype=bool)
            caught = super()._step_predators_v3()
            N, M = self.N, self.M
            mo = self.spy_motion
            if mo is None:                                   # 위협이 없는 세계(여기서는 없다)
                tgt = np.full(M, -1, dtype=np.int64)
                carry_m = np.zeros(M, dtype=bool)
            else:
                tgt = (self.pred_target.copy() if mo["tgt_dir"] is None else mo["tgt_dir"].copy())
                stalker = self.pred_type == PT_STALKER
                # 표적이 안 보여도 곧장 이어 가는 돌진(잠행형 돌진·플레이어 돌진)은 지난 표적을 쫓는 중으로 둔다(1단계와 같다)
                carry_m = ~mo["has_target"] & ((stalker & (mo["st1"] == ST_POUNCE))
                                               | (self.pred_is_player & (mo["pm1"] == PM_CHARGE)))
                tgt = np.where(carry_m, self.spy_prev_tgt, tgt)
            self.spy_tgt = tgt
            awake = ~self.pred_asleep if self._ps is not None else np.ones(M, dtype=bool)
            ex = self.pred_pos[:, 0][None, :] - self.pos[:, 0:1]          # (N, M) 사슴 → 위협 (포식자 이동 뒤)
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
            kind = np.where(self.pred_is_player, 3, np.where(self.pred_type == PT_STALKER, 2,
                                                             np.where(self.pred_ranged, 1, 0)))
            for tg in (self.spy_tgt, self.spy_prev_tgt):            # 이번 스텝 또는 지난 스텝에 이 사슴을 쫓은 깨어 있는 위협
                for m in np.flatnonzero((tg >= 0) & awake):
                    i = tg[m]
                    if pd[i, m] < purs_d[i]:
                        purs_d[i] = pd[i, m]
                        purs_cls[i] = cls[i, m]
                        purs_kind[i] = kind[m]
            self.spy = dict(caught=caught.copy(), pre=pre, near_d=near_d, near_cls=near_cls, purs_d=purs_d,
                            purs_cls=purs_cls, purs_kind=purs_kind, tgt=tgt.copy(), got=self.spy_got.copy(),
                            pounce_start=(mo["pounce_start"].copy() if mo else np.zeros(M, dtype=bool)),
                            charge_start=(mo["charge_start"].copy() if mo else np.zeros(M, dtype=bool)),
                            kind=kind)
            self.spy_prev_tgt = self.spy_tgt.copy()
            return caught

    return Spy


class FreezeOff:
    """R1b−F: R1b 를 그대로 싣고(`rep_learned`, 허용 = 모델 ∩ 세계) 허용 목록에서 FREEZE 만 뺀다(명세 5-4). R3 세계에서는 rep_learned 의
    허용이 이미 graze·flee·hide 라 그대로이고, freeze 가 든 세계(base·night)에서는 여기서 막는다. 망과 가능·결정 마스크는 그대로다."""

    def __init__(self, base):
        self.base = base
        self.model = base.model

    def bind_world(self, world) -> None:
        from env_v2.rep_policy import allowed_mask_of

        self.base.bind_world(world)
        names = tuple(b for b in self.base.allowed if b != "freeze")
        self.base.allowed = names
        self.base.params = {"allowed_mask": allowed_mask_of(names)}
        self.allowed = names

    def __call__(self, obs):
        return self.base(obs)


def make_policy(pname: str, cfg, seed: int):
    from env_v2 import rollout as ro
    from env_v2.repertoire import BEHAVIOR_NAMES
    from env_v2.world import obs_names

    import eval_v3 as ev

    if pname == "rl":
        return ro.build_policy({"kind": "rep_learned", "path": str(ROOT / MODEL)}, seed)
    if pname == "rlf":
        return FreezeOff(ro.build_policy({"kind": "rep_learned", "path": str(ROOT / MODEL)}, seed))
    if pname == "rbase":
        return ro.build_policy(ev.fsm_spec(cfg, ("graze", "flee"), "near"), seed)
    if pname.startswith("c_"):
        return ev.ConstRequest(BEHAVIOR_NAMES.index(pname[2:]), obs_names(cfg))
    raise ValueError(pname)


def _hist(x: np.ndarray, nb: int = NB) -> np.ndarray:
    n, F = x.shape
    b = np.clip(np.floor(x.astype(np.float64) * nb).astype(np.int64), 0, nb - 1)
    return np.bincount((b + np.arange(F)[None, :] * nb).ravel(), minlength=F * nb).reshape(F, nb)


def _hist1(x: np.ndarray, nb: int = NB) -> np.ndarray:
    b = np.clip(np.floor(np.asarray(x, dtype=np.float64) * nb).astype(np.int64), 0, nb - 1)
    return np.bincount(b, minlength=nb)


def _phase(d: float) -> int:
    from env_v2.world import DN_EDGES, DN_TOL

    if d <= DN_EDGES[0] + DN_TOL:
        return 0
    if d >= DN_EDGES[1] - DN_TOL:
        return 2
    return 1


def job(args):
    from env_v2 import rollout as ro
    from env_v2.rep_policy import action_mask, allowed_mask_of, feasible_mask, policy_obs, rep_argmax, rep_params
    from env_v2.repertoire import FLEE, FREEZE, GRAZE, HIDE, N_BEHAVIORS, SLEEP
    from env_v2.world import GAIT_STOP, PM_CHARGE, PM_REST, PT_STALKER, ST_POUNCE, world_params

    import eval_v3 as ev
    import repertoire_rules as rr

    variant, pname, seed, steps = args
    t0 = time.time()
    cfg = load_variant(variant)
    rp = rep_params(cfg)
    geo = rr._geom(cfg)
    Spy = _spy_class()
    w = Spy(cfg, seeds=[seed])
    w._spy_init()
    pol = make_policy(pname, cfg, seed)
    ro.forward_bind(pol, w)
    N, M, T, F = w.N, w.M, steps, w.obs_dim
    names = list(w.obs_names)
    ci = {c: names.index(c) for c in ("pred_count", "pred_dist", "pred_approach", "food_density", "cover_dist",
                                      "threat_recency", "energy", "beh_flee")}
    see_r, cov_norm = float(cfg.see_r), float(cfg.obs_cover_norm)
    allowed_w = tuple(rp["allowed"])
    has_terr = w._zt is not None
    has_ps = w._ps is not None
    is_player = w.pred_is_player.copy()
    wolf = ~is_player
    stalker = w.pred_type == PT_STALKER
    K = len(w.cov_r)
    # 원래 R1b(얼기 씀)의 허용 — R1b−F 의 '얼던 자리' 반사실(같은 상태에서 FREEZE 를 열었으면 무엇을 골랐나)
    cf_pol = None
    if pname == "rlf":
        mp = pol.model.policy
        cf_pol = (mp, {"allowed_mask": mp.rep_allowed_mask})

    # (T, N) 기록
    rew = np.empty((T, N))
    done = np.zeros((T, N), dtype=bool)
    caught = np.zeros((T, N), dtype=bool)
    beh = np.zeros((T, N), dtype=np.int8)
    in_cov = np.zeros((T, N), dtype=bool)
    near_d = np.full((T, N), np.inf, dtype=np.float32)
    near_cls = np.full((T, N), -1, dtype=np.int8)
    purs_d = np.full((T, N), np.inf, dtype=np.float32)
    purs_cls = np.full((T, N), -1, dtype=np.int8)
    purs_kind = np.full((T, N), -1, dtype=np.int8)
    seen_dec = np.zeros((T, N), dtype=bool)
    terr = np.full((T, N), 3, dtype=np.int8)            # 3 = 지형 없는 세계

    # 결정 시점 누적
    u_cnt = {u: np.zeros(4, dtype=np.int64) for u in ("esc3", "esc4", "hide")}
    g_cnt = {g: np.zeros(4, dtype=np.int64) for g in ("keep", "run", "leave")}
    choice = np.zeros(N_BEHAVIORS, dtype=np.int64)
    n_dec = 0
    a_opp = np.zeros((4, N_BEHAVIORS), dtype=np.int64)   # 포기율 A 기회: [땅] × 고른 행동
    opp_ev = []                                          # 기회 사건 (스텝, 개체, 고른 행동, 땅) — 고른 행동별 뒤 잡힘(변경 기록 10-15)
    a_cf = np.zeros((N_BEHAVIORS, N_BEHAVIORS), dtype=np.int64)  # 기회에서 [R1b 반사실 선택] × [고른 행동]
    cf_mat = np.zeros((2, N_BEHAVIORS, N_BEHAVIORS), dtype=np.int64)   # 모든 결정: [감지 0/1] × 반사실 × 고른 것
    flee_open_unseen = np.zeros(2, dtype=np.int64)       # [감지 없는 결정, 그중 FLEE 가능]
    cov_k = np.zeros(2, dtype=np.int64)                  # [은신처 안 개체-스텝(관측), 그중 '위협을 안다' K]
    h_all = np.zeros((F, NB), dtype=np.int64) if pname in OBS_POLICIES else None
    h_dec = np.zeros((F, NB), dtype=np.int64) if pname in OBS_POLICIES else None
    h_cond = np.zeros((len(COND_NAMES), NB), dtype=np.int64)
    mn_all, mx_all = np.full(F, np.inf), np.full(F, -np.inf)
    mn_dec, mx_dec = np.full(F, np.inf), np.full(F, -np.inf)
    out01 = 0
    j1 = np.zeros(2, dtype=np.int64)
    j1_max = 0.0
    # 스텝 뒤 누적
    sleep_on = np.zeros(2, dtype=np.int64)
    night = dict(deer=np.zeros(3), beh=np.zeros((3, N_BEHAVIORS)), catch=np.zeros(3), starve=np.zeros(3), cover=np.zeros(3),
                 wolf=np.zeros(3), wolf_awake=np.zeros(3), wolf_hunt=np.zeros(3), wolf_catch=np.zeros(3), steps=np.zeros(3))
    others_hist = np.zeros(N, dtype=np.int64)            # 은신처 안 개체-스텝의 '같은 원 안 다른 사슴 수'
    occ_max_sum, occ_max = 0.0, 0
    food_fill = np.zeros(4)                              # [은신처 셀 먹이 합, 용량 합, 밖 먹이 합, 밖 용량 합] (표본 합)
    cover_cells = getattr(w, "cover_food_cell", w.cover_cell)
    rim = np.zeros((2, 3), dtype=np.int64)               # [늑대, 플레이어] × [깨어 있는 위협-스텝, 둘레에 붙음, 원 안(막는 세계 0)]
    stuck_run = np.zeros(M, dtype=np.int64)
    stuck_hist = np.zeros((2, len(RUN_BINS) - 1), dtype=np.int64)
    stuck_max = np.zeros(2, dtype=np.int64)
    wolf_catch = 0
    player_catch = 0
    # [이어 사냥 0/1, 칸, 땅, 시작 거리 칸, 결과]
    pshape = (2, len(POUNCE_CATS), 4, len(DIST_BINS) - 1, len(POUNCE_OUT))
    pounce = np.zeros(pshape, dtype=np.int64)
    charge = np.zeros(pshape, dtype=np.int64)
    last_catch = np.full(M, -(10 ** 9), dtype=np.int64)  # 위협마다 마지막으로 잡은 스텝
    pounce_tdead = np.zeros(2, dtype=np.int64)           # [돌진, 플레이어 돌진] 중 표적이 다른 까닭으로 먼저 죽은 수
    active = {}                                          # 위협 m → (종류 0 돌진 / 1 플레이어 돌진, 표적, 세대, 칸, 땅)
    gen = np.zeros(N, dtype=np.int64)
    tp1 = np.full(M, -1, dtype=np.int64)                 # 지난 포식자 스텝의 표적
    tp2 = np.full(M, -1, dtype=np.int64)                 # 그 전 스텝
    rim_sel = w._zw_sel.copy() if w._zw else np.ones(M, dtype=bool)

    def rim_edge(q):
        if not K:
            return np.full(len(q), np.inf)
        dx = q[:, 0:1] - w.cov_c[:, 0][None, :]
        dy = q[:, 1:2] - w.cov_c[:, 1][None, :]
        return (np.sqrt(dx * dx + dy * dy) - w.cov_r[None, :]).min(1)

    for t in range(T):
        obs = w.observe()
        pk = w.rep_peek()
        g = w._g
        seen_dec[t] = g["pred_count"] > 0
        if h_all is not None:
            h_all += _hist(obs)
            mn_all = np.minimum(mn_all, obs.min(0))
            mx_all = np.maximum(mx_all, obs.max(0))
            out01 += int(np.count_nonzero((obs < 0.0) | (obs > 1.0)))
            seen = obs[:, ci["pred_count"]] > 0.0
            if seen.any():
                h_cond[0] += _hist1(obs[seen, ci["pred_dist"]])
                h_cond[1] += _hist1(obs[seen, ci["pred_approach"]])
                lim = (w._see_pred * w._rep_see)[seen] / cfg.see_r
                exc = obs[seen, ci["pred_dist"]].astype(np.float64) - lim
                bad = exc > J1_TOL
                j1 += (int(seen.sum()), int(bad.sum()))
                if bad.any():
                    j1_max = max(j1_max, float(exc.max()))
            inc_o = obs[:, ci["cover_dist"]] <= 0.0
            if inc_o.any():
                h_cond[2] += _hist1(obs[inc_o, ci["food_density"]])
            if (~seen).any():
                h_cond[3] += _hist1(obs[~seen, ci["threat_recency"]])
        inc_o = obs[:, ci["cover_dist"]] <= 0.0
        kk = (obs[:, ci["pred_count"]] > 0.0) | (obs[:, ci["threat_recency"]] >= G_COND["recency"])
        cov_k += (int(inc_o.sum()), int((inc_o & kk).sum()))
        # 결정 시점의 쫓김: 지난 두 포식자 스텝에 이 사슴을 표적으로 삼았고 지금 깨어 있는 위협의 실거리(지금 위치)
        awake_now = ~w.pred_asleep if has_ps else np.ones(M, dtype=bool)
        purs_now = np.full(N, np.inf)
        for tg in (tp1, tp2):
            ms = np.flatnonzero((tg >= 0) & awake_now)
            if len(ms):
                dd = np.sqrt(((w.pred_pos[ms] - w.pos[tg[ms]]) ** 2).sum(1))
                np.minimum.at(purs_now, tg[ms], dd)
        in_cov_now = w._in_cover(w.pos)
        terr_now = w._rz_terrain_of(w.pos).astype(np.int64) if has_terr else np.full(N, 3, dtype=np.int64)
        dark0 = float(w.dark) if w._dn is not None else 0.0
        a = np.asarray(pol(obs), dtype=np.float64)
        dec = pk["reads"]
        if dec.any():
            od = obs[dec]
            if h_dec is not None:
                h_dec += _hist(od)
                mn_dec = np.minimum(mn_dec, od.min(0))
                mx_dec = np.maximum(mx_dec, od.max(0))
            req = a[dec, 0].astype(np.int64)
            wake = pk["wake_decide"][dec]
            chosen = np.where(wake & (req == SLEEP), w._rs.wake_target[dec].astype(np.int64), req)
            f = rr.features_of_obs(od, geo)
            for u, (ca, cb) in ev.u_terms(f, "near", "r1b").items():
                if u == "esc":
                    for key, tg in (("esc3", (FLEE, HIDE)), ("esc4", (FLEE, HIDE, FREEZE))):
                        hit = np.isin(chosen, tg)
                        u_cnt[key] += (np.count_nonzero(ca), np.count_nonzero(ca & hit), np.count_nonzero(cb),
                                       np.count_nonzero(cb & hit))
                elif u == "hide":
                    hit = chosen == HIDE
                    u_cnt["hide"] += (np.count_nonzero(ca), np.count_nonzero(ca & hit), np.count_nonzero(cb),
                                      np.count_nonzero(cb & hit))
            # 관문 니치 초안(보고만): U_KEEP·U_RUN·U_LEAVE (명세 10절 '새 니치 U')
            s_, d_, ap_, c_ = f["seen"], f["dist"], f["approach"], f["cover_d"]
            e_ = od[:, ci["energy"]]
            fleeing = od[:, ci["beh_flee"]] > 0.5
            kn = s_ | (od[:, ci["threat_recency"]] >= G_COND["recency"])
            keep = (chosen == FLEE) | ((chosen == HIDE) & (c_ > 0.0))
            gc = G_COND
            for key, (na, nb_, hit) in (
                    ("keep", (fleeing & s_ & (ap_ >= gc["g1_app"]) & (d_ < gc["g1_d"]) & (c_ > 0.0),
                              fleeing & s_ & (ap_ < gc["g1x_app"]) & (d_ >= gc["g1x_d"]), keep)),
                    ("run", (s_ & (c_ > 0.0) & (c_ <= gc["g2_c"]) & (d_ >= gc["g2_d"]), s_ & (c_ > gc["g2x_c"]),
                             chosen == HIDE)),
                    ("leave", ((c_ <= 0.0) & kn & (~s_ | (d_ >= gc["g3_d"])) & (e_ < gc["g3_e"]),
                               (c_ <= 0.0) & kn & (~s_ | (d_ >= gc["g3_d"])) & (e_ > gc["g3x_e"]), chosen == GRAZE))):
                g_cnt[key] += (np.count_nonzero(na), np.count_nonzero(na & hit), np.count_nonzero(nb_),
                               np.count_nonzero(nb_ & hit))
            choice += np.bincount(chosen, minlength=N_BEHAVIORS)
            n_dec += int(dec.sum())
            sd = f["seen"]
            fm = feasible_mask(od, names)
            flee_open_unseen += (int((~sd).sum()), int((~sd & fm[:, FLEE]).sum()))
            # 포기율 A 기회: 지금 행동 FLEE & 쫓는 위협 실거리 < 10 & 은신처 밖 (명세 10절)
            idx = np.flatnonzero(dec)
            opp = (pk["behavior"][idx] == FLEE) & (purs_now[idx] < PURSUE_R) & ~in_cov_now[idx]
            if opp.any():
                np.add.at(a_opp, (terr_now[idx][opp], chosen[opp]), 1)
                opp_ev.extend(zip([t] * int(opp.sum()), idx[opp].tolist(), chosen[opp].tolist(), terr_now[idx][opp].tolist()))
            if cf_pol is not None:
                mp, prm = cf_pol
                mfull = action_mask(pk, obs, prm, obs_names=names)[dec]
                cf = rep_argmax(mp, policy_obs(od, mfull))
                np.add.at(cf_mat, (sd.astype(np.int64), cf, chosen), 1)
                if opp.any():
                    np.add.at(a_cf, (cf[opp], chosen[opp]), 1)
        asleep0 = w.pred_asleep.copy() if has_ps else None
        pp0 = w.pred_pos.copy()
        _, r, d_, _ = w.step(a)
        ro.forward_done(pol, d_)
        rew[t], done[t] = r, d_
        beh[t] = w.behavior
        sp = w.spy
        pre = sp["pre"]
        caught[t], in_cov[t] = sp["caught"], pre["in_cov"]
        near_d[t], near_cls[t], purs_d[t], purs_cls[t] = sp["near_d"], sp["near_cls"], sp["purs_d"], sp["purs_cls"]
        purs_kind[t] = sp["purs_kind"]
        if has_terr:
            terr[t] = w._rz_terrain_of(pre["pos"])
        got = sp["got"]
        wolf_catch += int(np.count_nonzero(got & wolf))
        player_catch += int(np.count_nonzero(got & is_player))
        # 밤 활동
        ph = _phase(dark0)
        awake = ~w.pred_asleep if has_ps else np.ones(M, dtype=bool)
        tgt = sp["tgt"]
        night["steps"][ph] += 1
        night["deer"][ph] += N
        night["beh"][ph] += np.bincount(pre["beh"].astype(np.int64), minlength=N_BEHAVIORS)
        night["catch"][ph] += float(sp["caught"].sum())
        night["starve"][ph] += float((d_ & ~sp["caught"]).sum())
        night["cover"][ph] += float(pre["in_cov"].sum())
        night["wolf"][ph] += float(wolf.sum())
        night["wolf_awake"][ph] += float((wolf & awake).sum())
        night["wolf_hunt"][ph] += float((wolf & awake & (tgt >= 0)).sum())
        night["wolf_catch"][ph] += float((got & wolf).sum())
        if has_ps:
            fell = np.flatnonzero(~asleep0 & w.pred_asleep)
            if len(fell):
                dx = w.pos[:, 0][None, :] - w.pred_pos[fell, 0][:, None]
                dy = w.pos[:, 1][None, :] - w.pred_pos[fell, 1][:, None]
                dmin = np.sqrt(dx * dx + dy * dy).min(1)
                sleep_on += (len(fell), int(np.count_nonzero(dmin <= SETTLE_R)))
        # 은신처 몰림: 은신처 안 사슴마다 '가장 깊이 든 원'의 다른 사슴 수
        if K and pre["in_cov"].any():
            p_in = pre["pos"][pre["in_cov"]]
            dx = p_in[:, 0:1] - w.cov_c[:, 0][None, :]
            dy = p_in[:, 1:2] - w.cov_c[:, 1][None, :]
            k_of = (np.sqrt(dx * dx + dy * dy) - w.cov_r[None, :]).argmin(1)
            cnt = np.bincount(k_of, minlength=K)
            others_hist += np.bincount(cnt[k_of] - 1, minlength=N)[:N]
            occ_max = max(occ_max, int(cnt.max()))
            occ_max_sum += float(cnt.max())
        if t % FOOD_EVERY == 0:
            cap = w.food_cap
            food_fill += (float(w.food[cover_cells].sum()), float(cap[cover_cells].sum()),
                          float(w.food[~cover_cells].sum()), float(cap[~cover_cells].sum()))
        # 늑대 둘레 미끄러짐·끼임
        edge = rim_edge(w.pred_pos)
        rest = is_player & (w.player_mode == PM_REST)
        mv = np.sqrt((w.pred_vel * w.pred_vel).sum(1))
        on_rim = (edge >= 0.0) & (edge < RIM_TOL)
        inside = edge < 0.0
        for kix, sel in ((0, wolf), (1, is_player)):
            aw = sel & awake & ~rest
            rim[kix] += (int(aw.sum()), int((aw & on_rim).sum()), int((aw & inside & rim_sel).sum()))
        stuck = awake & ~rest & on_rim & (mv < STILL_TOL)
        for m in range(M):
            if stuck[m]:
                stuck_run[m] += 1
            elif stuck_run[m] > 0:
                kix = int(is_player[m])
                stuck_hist[kix, np.searchsorted(RUN_BINS, stuck_run[m], side="right") - 1] += 1
                stuck_max[kix] = max(stuck_max[kix], stuck_run[m])
                stuck_run[m] = 0
        # 사용자 추격 모형 확인표: 잠행형 돌진·플레이어 돌진의 시작과 결과
        for kind_ix, starts in ((0, sp["pounce_start"]), (1, sp["charge_start"])):
            for m in np.flatnonzero(starts):
                i = int(tgt[m])
                if i < 0:
                    continue
                b0, g0 = int(pre["beh"][i]), int(pre["gait"][i])
                if b0 == FLEE:
                    cat = "flee_startle" if g0 == GAIT_STOP else "flee_run"
                elif b0 == HIDE:
                    cat = "hide_go"
                elif b0 == FREEZE:
                    cat = "freeze"
                elif b0 == GRAZE:
                    cat = "graze_seen" if seen_dec[t, i] else "graze_unseen"
                else:
                    cat = "other"
                tr = int(w._rz_terrain_of(pre["pos"][i:i + 1])[0]) if has_terr else 3
                # 이어 사냥(변경 기록 10-15): 그 위협이 직전 22스텝(3초) 안에 사슴을 잡았다 — 무리 안에서 먹이 쿨다운이 끝나자마자 옆 사슴에게
                # 돌진. 시작 거리 = 돌진을 시작한 포식자 스텝의 실거리(초식 이동 뒤 사슴, 포식자 이동 전 위협 — 돌진 판정과 같은 때)
                fol = int(t - last_catch[m] <= WIN)
                dist0 = float(np.hypot(*(pre["pos"][i] - pp0[m])))
                db = int(np.searchsorted(DIST_BINS, dist0, side="right") - 1)
                key = (fol, POUNCE_CATS.index(cat), tr, min(max(db, 0), len(DIST_BINS) - 2))
                if int(m) in active:                     # 잠들어 처음 상태로 돌아간 뒤 같은 스텝에 다시 돌진(드묾): 앞 돌진은 놓침
                    k0, _, _, key0, _ = active[int(m)]
                    (pounce if k0 == 0 else charge)[key0 + (2,)] += 1
                active[int(m)] = [kind_ix, i, int(gen[i]), key, False]
        for m in list(active):
            kind_ix, i, gi, key, tdead = active[m]
            tab = pounce if kind_ix == 0 else charge
            on = (w.stalk_state[m] == ST_POUNCE) if kind_ix == 0 else (w.player_mode[m] == PM_CHARGE)
            same = gen[i] == gi
            if got[m]:
                tab[key + (0 if (same and sp["caught"][i]) else 1,)] += 1
                if tdead:
                    pounce_tdead[kind_ix] += 1
                del active[m]
            elif not on:
                tab[key + (2,)] += 1
                if tdead:
                    pounce_tdead[kind_ix] += 1
                del active[m]
            elif same and d_[i]:
                active[m][4] = True
        last_catch[got] = t
        gen[d_] += 1
        tp2, tp1 = tp1, tgt.copy()
    for m in list(active):                                # 실행 끝에 진행 중인 돌진
        kind_ix, i, gi, key, tdead = active[m]
        (pounce if kind_ix == 0 else charge)[key + (3,)] += 1
    for m in range(M):
        if stuck_run[m] > 0:
            kix = int(is_player[m])
            stuck_hist[kix, np.searchsorted(RUN_BINS, stuck_run[m], side="right") - 1] += 1
            stuck_max[kix] = max(stuck_max[kix], stuck_run[m])

    bouts = flee_bouts(beh, done, caught, purs_d, purs_cls, near_d, near_cls, seen_dec, FLEE, purs_kind, in_cov, terr)
    a_out = opp_outcomes(opp_ev, caught, done)
    chase = chase_episodes(purs_d, purs_kind, beh, done, caught, in_cov, terr)
    cross = cover_crossings(in_cov, done)
    bh = w._rep_hist.sum((0, 1)).astype(np.int64)
    wp = world_params(cfg, seed)
    out = dict(variant=variant, policy=pname, seed=int(seed), steps=int(T), n=int(T * N),
               g_gamma=ro.g_gamma(rew, done, GAMMA, TAIL),
               pred_rate=w._pred_deaths / (T * N), starve_rate=w._starve_deaths / (T * N),
               beh=bh.tolist(), switch=int(w._rep_switch), flicker=int(w._rep_flicker), n_dec=n_dec,
               choice=choice.tolist(), u_cnt={u: v.tolist() for u, v in u_cnt.items()},
               g_cnt={k: v.tolist() for k, v in g_cnt.items()},
               a_opp=a_opp.tolist(), a_out=a_out.tolist(), a_cf=a_cf.tolist(), cf_mat=cf_mat.tolist(), has_cf=cf_pol is not None,
               flee_open_unseen=flee_open_unseen.tolist(), cov_k=cov_k.tolist(),
               catch_n=int(caught.sum()), catch_in_cover=int((caught & in_cov).sum()),
               in_cover_frac=float(in_cov.mean()), spy_fail=int(w.spy_fail), sleep_on=sleep_on.tolist(),
               night={k: v.tolist() for k, v in night.items()},
               others_hist=others_hist.tolist(), occ_max=int(occ_max), occ_max_mean=occ_max_sum / T,
               food_fill=food_fill.tolist(), rim=rim.tolist(), stuck_hist=stuck_hist.tolist(), stuck_max=stuck_max.tolist(),
               wolf_catch=wolf_catch, player_catch=player_catch, n_wolf=int(wolf.sum()), n_player=int(is_player.sum()),
               n_stalker=int(stalker.sum()), pounce=pounce.tolist(), charge=charge.tolist(),
               pounce_tdead=pounce_tdead.tolist(), bouts=bouts, chase=chase, cross=cross,
               world=dict(size=float(w.size), M=int(M), cover_frac_target=float(w.cover_frac_target),
                          cover_frac_actual=float(w.cover_frac_actual), n_cover=int(K),
                          pred_speed_mult=float(wp["pred_speed_mult"]), ranged_frac=float(wp["ranged_frac"]),
                          food_regen_mult=float(wp["food_regen_mult"])),
               allowed=list(getattr(pol, "allowed", allowed_w)))
    if h_all is not None:
        out["obs"] = dict(h_all=h_all.tolist(), h_dec=h_dec.tolist(), h_cond=h_cond.tolist(), mn_all=mn_all.tolist(),
                          mx_all=mx_all.tolist(), mn_dec=mn_dec.tolist(), mx_dec=mx_dec.tolist(), out01=out01,
                          j1=[int(j1[0]), int(j1[1])], j1_max=j1_max)
    ds = w.daynight_stats()
    out.update(pred_rate_night=ds.get("pred_rate_night"), pred_rate_day=ds.get("pred_rate_day"))
    if has_ps:
        out["pred_asleep_mean"] = w.pred_sleep_stats()["pred_asleep_mean"]
    if w._rz:
        out["realism"] = {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
                          for k, v in w.realism_stats().items()}
    if w._r3:
        out["r3"] = {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in w.r3_stats().items()}
        if w._zw:
            out["r3"]["blocking_n"] = int(w._zw_sel.sum())
    out["sec"] = time.time() - t0
    return out


def flee_bouts(beh, done, caught, purs_d, purs_cls, near_d, near_cls, seen_dec, FLEE, purs_kind=None, in_cov=None,
               terr=None) -> dict:
    """도주 묶음(1단계 PREREG 2절과 같은 정의). 묶음 = 한 개체(슬롯 + 세대)의 FLEE 연속 스텝. 끝 = 바뀜(살아서 FLEE 가 아닌 행동으로)
    또는 죽음(FLEE 중 잡힘·굶음). 실행이 끝날 때 FLEE 중이면 길이에서 뺀다(잘림). R3 판: 쫓김 끝을 끝 위치의 땅으로도 나눈다."""
    T, N = beh.shape
    Fm = beh == FLEE
    ok_prev = np.zeros((T, N), dtype=bool)
    ok_prev[1:] = ~done[:-1]
    cont = np.zeros((T, N), dtype=bool)
    cont[1:] = Fm[:-1] & ok_prev[1:]
    start = Fm & ~cont
    sw_end = cont & ~Fm
    death_end = Fm & done
    lengths, len_sw, len_death = [], [], []
    ends = []
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
    p_after = np.zeros((8, 2), dtype=np.int64)
    p_kind = np.zeros((4, 2), dtype=np.int64)
    p_seen = np.zeros((2, 2), dtype=np.int64)
    p_cov = np.zeros((2, 2), dtype=np.int64)
    p_terr = np.zeros((4, 3), dtype=np.int64)           # 쫓김 끝의 땅 × [끝 수, 멈춤-재도주, 3초 안 잡힘(다시 뛰기 전)]
    for t, i in ends:
        after[beh[t, i]] += 1
        nd = float(near_d[t, i])
        d_all.append(nd if math.isfinite(nd) else 1e9)
        if near_cls[t, i] >= 0:
            cls_near[near_cls[t, i]] += 1
        p = float(purs_d[t, i]) <= PURSUE_R
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
            if terr is not None:
                p_terr[int(terr[t, i])] += (1, sg, int(cw and not rf))
    return dict(lengths=lengths, len_sw=len_sw, len_death=len_death, censored=censored, n_end=n_end,
                n_death_end=len(len_death), pursued=pursued, reflee=refle, caught_w=caught_w, stopgo=stopgo,
                caught60=caught60, quick_reflee_all=quick_reflee_all, after=after.tolist(),
                d_all=[round(x, 3) for x in d_all], d_purs=[round(x, 3) for x in d_purs],
                cls_purs=cls_purs.tolist(), seen_purs=seen_purs, cls_near=cls_near.tolist(),
                p_after=p_after.tolist(), p_kind=p_kind.tolist(), p_seen=p_seen.tolist(), p_cov=p_cov.tolist(),
                p_terr=p_terr.tolist())


def chase_episodes(purs_d, purs_kind, beh, done, caught, in_cov, terr) -> dict:
    """쫓김 묶음(사용자 추격 모형 확인표 4번째 줄, PREREG 2절). 시작 = 쫓는 위협(이번·지난 포식자 스텝에 이 사슴을 표적으로 삼은 깨어
    있는 위협)이 실거리 10 안에 들어온 스텝(같은 개체가 직전 22스텝 동안 쫓기지 않았고 은신처 밖). 끝 = 잡힘, 굶음, 은신처 원 안(안전),
    22스텝 이어서 쫓기지 않음(안전), 실행 끝(잘림). 행동 칸(쫓기는 스텝과 잡힌 스텝의 실행 행동만 본다): 반응(FLEE·HIDE·FREEZE) 없음,
    반응 뒤 GRAZE(먹으러 멈춤), 얼기, 숨기, 도주만."""
    from env_v2.repertoire import FLEE, FREEZE, GRAZE, HIDE, SLEEP

    T, N = beh.shape
    P = purs_d < PURSUE_R
    tab = np.zeros((4, len(CHASE_CATS), 4, len(CHASE_OUT)), dtype=np.int64)   # [위협 종류, 행동 칸, 땅, 결과]
    tlen = np.zeros((4, len(CHASE_CATS), 2), dtype=np.int64)                   # [종류, 칸] × [끝난 묶음 수, 길이 합(스텝)]
    lat = np.zeros((4, 4, LAT_MAX + 2), dtype=np.int64)                         # [종류, 땅, 첫 반응까지 스텝(0..60, 60+, 없음)]
    react = (FLEE, HIDE, FREEZE)
    for i in range(N):
        last_p = -(10 ** 9)
        ep = None
        for t in range(T):
            if t > 0 and done[t - 1, i]:          # 새 개체
                last_p = -(10 ** 9)
                ep = None
            if ep is None:
                if P[t, i] and t - last_p > WIN and not in_cov[t, i] and purs_kind[t, i] >= 0:
                    ep = dict(s=t, kind=int(purs_kind[t, i]), terr=int(terr[t, i]), react=-1, graze=False, hide=False,
                              freeze=False)
                else:
                    if P[t, i]:
                        last_p = t
                    continue
            b = int(beh[t, i])
            # 행동 칸은 쫓기는 스텝(쫓는 위협이 10 안)과 잡힌 스텝만으로 정한다(변경 기록 10-15: 안전 확인 창 22스텝 동안의 먹기를
            # '멈춤'으로 세지 않는다)
            if P[t, i] or caught[t, i]:
                if b in react and ep["react"] < 0:
                    ep["react"] = t
                if ep["react"] >= 0 and b in (GRAZE, SLEEP):
                    ep["graze"] = True
                ep["hide"] |= b == HIDE
                ep["freeze"] |= b == FREEZE
            res = None
            if caught[t, i]:
                res = "caught"
            elif done[t, i]:
                res = "starved"
            elif in_cov[t, i]:
                res = "cover"
            elif P[t, i]:
                last_p = t
            elif t - max(last_p, ep["s"]) >= WIN:
                res = "far"
            if res is None and t == T - 1:
                res = "censored"
            if res is not None:
                cat = ("none" if ep["react"] < 0 else "stop_graze" if ep["graze"] else "freeze" if ep["freeze"]
                       else "hide" if ep["hide"] else "kept")
                tab[ep["kind"], CHASE_CATS.index(cat), ep["terr"], CHASE_OUT.index(res)] += 1
                lt = LAT_MAX + 1 if ep["react"] < 0 else min(ep["react"] - ep["s"], LAT_MAX)
                lat[ep["kind"], ep["terr"], lt] += 1
                if res != "censored":
                    tlen[ep["kind"], CHASE_CATS.index(cat)] += (1, t - ep["s"] + 1)
                if P[t, i]:
                    last_p = t
                ep = None
    return dict(tab=tab.tolist(), lat=lat.tolist(), tlen=tlen.tolist())


def opp_outcomes(ev, caught, done) -> np.ndarray:
    """포기율 A 기회마다 고른 행동별로 그 뒤 잡혔나(변경 기록 10-15, 보고만): [땅 4, 고른 행동 5, (기회 수, 3초(22스텝) 안 잡힘, 8초(60스텝)
    안 잡힘)]. 결정한 스텝부터 센다(그 스텝의 포획 포함). 같은 개체만(그 사이 죽어 리스폰하면 멈춘다). 실행 끝까지 60스텝이 남지 않은
    기회는 뺀다(잘림)."""
    T = caught.shape[0]
    out = np.zeros((4, 5, 3), dtype=np.int64)
    for t, i, ch, tr in ev:
        if t + WIN60 >= T:
            continue
        c22 = c60 = False
        for k in range(t, t + WIN60):
            if k > t and done[k - 1, i]:
                break
            if caught[k, i]:
                c60 = True
                c22 = k - t < WIN
                break
        out[tr, ch] += (1, int(c22), int(c60))
    return out


def cover_crossings(in_cov, done) -> dict:
    """은신처 원 경계 넘나듦(같은 개체): 들고 남 수와 그중 3초(22스텝) 안에 되돌아온 수."""
    T, N = in_cov.shape
    ok = np.zeros((T, N), dtype=bool)
    ok[1:] = ~done[:-1]
    ch = ok & (in_cov != np.roll(in_cov, 1, axis=0))
    ch[0] = False
    n = int(ch.sum())
    quick = 0
    for i in range(N):
        ts = np.flatnonzero(ch[:, i])
        for a, b in zip(ts[:-1], ts[1:]):
            if b - a <= WIN and not done[a:b, i].any():
                quick += 1
    return dict(n=n, quick=quick)


# --------------------------------------------------------------------- #
# 모으기
# --------------------------------------------------------------------- #


def _pct(xs, qs=(10, 25, 50, 75, 90)):
    if not len(xs):
        return {f"p{q}": None for q in qs}
    a = np.asarray(xs, dtype=np.float64)
    return {f"p{q}": float(np.percentile(a, q)) for q in qs}


def _paired(a, b):
    ok = [(x, y) for x, y in zip(a, b) if x is not None and y is not None and math.isfinite(x) and math.isfinite(y)]
    d = np.asarray([x - y for x, y in ok], dtype=np.float64)
    n = len(d)
    if n < 2:
        return dict(diff=float(d.mean()) if n else None, t=None, n=n)
    sd = d.std(ddof=1)
    return dict(diff=float(d.mean()), t=float(d.mean() / (sd / math.sqrt(n))) if sd > 0 else None, n=n)


def _ratio(x, y):
    return float(x) / float(y) if y else None


def _nanmean(xs):
    v = [x for x in xs if x is not None and math.isfinite(x)]
    return float(np.mean(v)) if v else None


def summarize_cell(rows: list[dict]) -> dict:
    from env_v2.repertoire import BEHAVIOR_NAMES

    import eval_v3 as ev

    rows = sorted(rows, key=lambda r: r["seed"])
    nb = len(BEHAVIOR_NAMES)
    beh = np.sum([r["beh"] for r in rows], axis=0).astype(np.float64)
    sw, fl = sum(r["switch"] for r in rows), sum(r["flicker"] for r in rows)
    n = sum(r["n"] for r in rows)
    B = [r["bouts"] for r in rows]
    lengths = [x for b in B for x in b["lengths"]]
    s = lambda k: sum(b[k] for b in B)            # noqa: E731
    n_end, pursued, stopgo = s("n_end"), s("pursued"), s("stopgo")
    hist = np.histogram(lengths, bins=FLEE_LEN_BINS)[0] if lengths else np.zeros(len(FLEE_LEN_BINS) - 1)
    out = dict(seeds=[r["seed"] for r in rows], steps=rows[0]["steps"], allowed=rows[0]["allowed"],
               g_gamma=float(np.mean([r["g_gamma"] for r in rows])),
               pred_rate=float(np.mean([r["pred_rate"] for r in rows])),
               starve_rate=float(np.mean([r["starve_rate"] for r in rows])),
               death_rate=float(np.mean([r["pred_rate"] + r["starve_rate"] for r in rows])),
               use={b: float(beh[k] / beh.sum()) for k, b in enumerate(BEHAVIOR_NAMES)},
               flicker=_ratio(fl, sw), decide_frac=_ratio(sum(r["n_dec"] for r in rows), n),
               choice={b: _ratio(np.sum([r["choice"][k] for r in rows]), sum(r["n_dec"] for r in rows))
                       for k, b in enumerate(BEHAVIOR_NAMES)})
    ucnt = {u: np.sum([r["u_cnt"][u] for r in rows], axis=0) for u in rows[0]["u_cnt"]}
    gcnt = {u: np.sum([r["g_cnt"][u] for r in rows], axis=0) for u in rows[0]["g_cnt"]}
    out["u"] = {u: ev.u_value(c) for u, c in ucnt.items()}
    out["g_u"] = {u: ev.u_value(c) for u, c in gcnt.items()}
    out["g_cnt"] = {u: c.tolist() for u, c in gcnt.items()}
    out["g_p"] = {u: dict(niche=_ratio(c[1], c[0]), cross=_ratio(c[3], c[2]), n_niche=int(c[0]), n_cross=int(c[2]))
                  for u, c in gcnt.items()}
    # 포기율 A (명세 10절): 기회 = 결정 시점 FLEE 중 & 쫓는 위협 실거리 < 10 & 은신처 밖. 포기 = GRAZE·SLEEP(원래 R1b 는 FREEZE 도)
    fz_on = "freeze" in rows[0]["allowed"]
    ab_cols = [BEHAVIOR_NAMES.index("graze"), BEHAVIOR_NAMES.index("sleep")] + ([BEHAVIOR_NAMES.index("freeze")] if fz_on
                                                                                   else [])
    A_seed = []
    opp_all = np.zeros((4, nb), dtype=np.int64)
    for r in rows:
        ao = np.asarray(r["a_opp"])
        opp_all += ao
        tot = ao.sum()
        A_seed.append(float(ao[:, ab_cols].sum() / tot) if tot else None)
    tot = opp_all.sum()
    out["A"] = dict(per_seed=A_seed, mean=_nanmean(A_seed), pooled=_ratio(opp_all[:, ab_cols].sum(), tot), n_opp=int(tot),
                    opp_per_1k=1000.0 * tot / n,
                    choice={b: _ratio(opp_all[:, k].sum(), tot) for k, b in enumerate(BEHAVIOR_NAMES)},
                    by_terr={TERR_LABELS[q]: dict(n=int(opp_all[q].sum()), A=_ratio(opp_all[q, ab_cols].sum(), opp_all[q].sum()))
                             for q in range(4) if opp_all[q].sum()})
    if rows[0]["has_cf"]:
        cf = np.sum([r["a_cf"] for r in rows], axis=0)
        cfm = np.sum([r["cf_mat"] for r in rows], axis=0)        # [감지, 반사실, 고른 것]
        fz = BEHAVIOR_NAMES.index("freeze")
        # 같은 기회에서 원래 R1b(얼기 씀)가 골랐을 것의 A (FREEZE 도 포기)
        ab_r1b = [BEHAVIOR_NAMES.index("graze"), BEHAVIOR_NAMES.index("sleep"), fz]
        cf_seed = []
        for r in rows:
            c = np.asarray(r["a_cf"])
            t_ = c.sum()
            cf_seed.append(float(c[ab_r1b, :].sum() / t_) if t_ else None)
        out["A"]["cf_r1b"] = dict(per_seed=cf_seed, mean=_nanmean(cf_seed), pooled=_ratio(cf[ab_r1b, :].sum(), cf.sum()),
                                  choice={b: _ratio(cf[k, :].sum(), cf.sum()) for k, b in enumerate(BEHAVIOR_NAMES)},
                                  at_freeze={b: _ratio(cf[fz, k], cf[fz, :].sum()) for k, b in enumerate(BEHAVIOR_NAMES)},
                                  n_freeze=int(cf[fz, :].sum()))
        allm = cfm.sum(0)
        out["cf"] = dict(n_dec=int(allm.sum()), freeze_share=_ratio(allm[fz, :].sum(), allm.sum()),
                         at_freeze={b: _ratio(allm[fz, k], allm[fz, :].sum()) for k, b in enumerate(BEHAVIOR_NAMES)},
                         at_freeze_seen={b: _ratio(cfm[1, fz, k], cfm[1, fz, :].sum()) for k, b in enumerate(BEHAVIOR_NAMES)},
                         at_freeze_unseen={b: _ratio(cfm[0, fz, k], cfm[0, fz, :].sum()) for k, b in enumerate(BEHAVIOR_NAMES)},
                         same_elsewhere=_ratio(np.trace(allm) - allm[fz, fz], allm.sum() - allm[fz, :].sum()),
                         n_freeze=int(allm[fz, :].sum()), n_freeze_seen=int(cfm[1, fz, :].sum()))
    fo = np.sum([r["flee_open_unseen"] for r in rows], axis=0)
    ck = np.sum([r["cov_k"] for r in rows], axis=0)
    out["flee_open_unseen"] = _ratio(fo[1], fo[0])
    out["cover_k_share"] = _ratio(ck[1], ck[0])
    # 도주 묶음 (1단계와 같은 꼴)
    cls_purs = np.sum([b["cls_purs"] for b in B], axis=0)
    after = np.sum([b["after"] for b in B], axis=0)
    d_all = [x for b in B for x in b["d_all"]]
    pt = np.sum([b["p_terr"] for b in B], axis=0)
    out["flee"] = dict(n_bouts=len(lengths), censored=s("censored"), mean_len=float(np.mean(lengths)) if lengths else None,
                       len_pct=_pct(lengths),
                       len_hist=dict(zip(["<8", "8", "9-15", "16-22", "23-45", "46-90", "91+"], [int(x) for x in hist])),
                       n_end=n_end, n_death_end=s("n_death_end"), bouts_per_1k=1000.0 * len(lengths) / n,
                       pursued_end_frac=_ratio(pursued, n_end), stop_go_given_pursued=_ratio(stopgo, pursued),
                       reflee_given_pursued=_ratio(s("reflee"), pursued), caught3s_given_pursued=_ratio(s("caught_w"), pursued),
                       caught60_given_pursued=_ratio(s("caught60"), pursued), pursued_per_1k=1000.0 * pursued / n,
                       after={b: _ratio(after[k], n_end) for k, b in enumerate(BEHAVIOR_NAMES)},
                       end_dist=_pct(d_all),
                       purs_dir={k: _ratio(cls_purs[i], cls_purs.sum()) for i, k in enumerate(("front120", "side", "rear60"))},
                       purs_seen_at_decision=_ratio(s("seen_purs"), pursued),
                       by_terr={TERR_LABELS[q]: dict(n=int(pt[q, 0]), stop_go=_ratio(pt[q, 1], pt[q, 0]),
                                                     caught3s=_ratio(pt[q, 2], pt[q, 0])) for q in range(4) if pt[q, 0]})
    # 포획·은신처
    catch_n, catch_cov = sum(r["catch_n"] for r in rows), sum(r["catch_in_cover"] for r in rows)
    oh = np.sum([r["others_hist"] for r in rows], axis=0).astype(np.float64)
    ks = np.arange(len(oh))
    ff = np.sum([r["food_fill"] for r in rows], axis=0)
    cr = [r["cross"] for r in rows]
    cfrac = [r["world"]["cover_frac_actual"] for r in rows]
    crowd = [r["in_cover_frac"] / r["world"]["cover_frac_actual"] if r["world"]["cover_frac_actual"] > 0 else None
             for r in rows]
    out["catch"] = dict(n=int(catch_n), in_cover=int(catch_cov), in_cover_share=_ratio(catch_cov, catch_n))
    out["shelter"] = dict(in_cover_frac=float(np.mean([r["in_cover_frac"] for r in rows])),
                          cover_frac_actual=float(np.mean(cfrac)), crowd_index=_nanmean(crowd),
                          others_mean=float((oh * ks).sum() / oh.sum()) if oh.sum() else None,
                          others_p50=_hpct_int(oh, 50), others_p90=_hpct_int(oh, 90),
                          others_ge5=_ratio(oh[5:].sum(), oh.sum()), occ_max=int(max(r["occ_max"] for r in rows)),
                          occ_max_mean=float(np.mean([r["occ_max_mean"] for r in rows])),
                          cover_k_share=out["cover_k_share"],
                          cross_per_min=float(sum(c["n"] for c in cr)) / (n / MINUTE),
                          cross_quick=_ratio(sum(c["quick"] for c in cr), sum(c["n"] for c in cr)),
                          food_fill_cover=_ratio(ff[0], ff[1]), food_fill_out=_ratio(ff[2], ff[3]))
    # 늑대
    rim = np.sum([r["rim"] for r in rows], axis=0)
    sh = np.sum([r["stuck_hist"] for r in rows], axis=0)
    wolf_min = [r["wolf_catch"] / (r["n_wolf"] * r["steps"] / MINUTE) if r["n_wolf"] else None for r in rows]
    out["wolf"] = dict(catch_per_wolf_min=_nanmean(wolf_min), per_seed_catch_per_wolf_min=wolf_min,
                       rim_share_wolf=_ratio(rim[0, 1], rim[0, 0]), rim_share_player=_ratio(rim[1, 1], rim[1, 0]),
                       inside_blocking=int(rim[:, 2].sum()),
                       stuck_hist_wolf=sh[0].tolist(), stuck_hist_player=sh[1].tolist(),
                       stuck_max_wolf=int(max(r["stuck_max"][0] for r in rows)),
                       stuck_max_player=int(max(r["stuck_max"][1] for r in rows)),
                       player_catch_per_min=_nanmean([r["player_catch"] / (r["n_player"] * r["steps"] / MINUTE)
                                                      for r in rows if r["n_player"]]))
    # 밤 활동
    nt = {k: np.sum([r["night"][k] for r in rows], axis=0) for k in rows[0]["night"]}
    out["night"] = {PHASES[p]: dict(frac_steps=_ratio(nt["steps"][p], nt["steps"].sum()),
                                    pred_per_1k=_ratio(1000.0 * nt["catch"][p], nt["deer"][p]),
                                    starve_per_1k=_ratio(1000.0 * nt["starve"][p], nt["deer"][p]),
                                    use={b: _ratio(nt["beh"][p][k], nt["beh"][p].sum()) for k, b in enumerate(BEHAVIOR_NAMES)},
                                    cover=_ratio(nt["cover"][p], nt["deer"][p]),
                                    wolf_awake=_ratio(nt["wolf_awake"][p], nt["wolf"][p]),
                                    wolf_hunt=_ratio(nt["wolf_hunt"][p], nt["wolf"][p]),
                                    wolf_catch_per_min=_ratio(nt["wolf_catch"][p] * MINUTE, nt["wolf"][p]))
                    for p in range(3)}
    so = np.sum([r["sleep_on"] for r in rows], axis=0)
    out["sleep_onset"] = dict(n=int(so[0]), deer_within_8=int(so[1]), frac=_ratio(so[1], so[0]))
    out["pred_asleep_mean"] = _nanmean([r.get("pred_asleep_mean") for r in rows])
    out["pred_rate_night"] = _nanmean([r["pred_rate_night"] for r in rows])
    out["pred_rate_day"] = _nanmean([r["pred_rate_day"] for r in rows])
    # 확인표
    pc = np.sum([r["pounce"] for r in rows], axis=0)
    ch = np.sum([r["charge"] for r in rows], axis=0)
    out["pounce"] = _pounce_table(pc)
    out["charge"] = _pounce_table(ch)
    out["pounce_tdead"] = np.sum([r["pounce_tdead"] for r in rows], axis=0).tolist()
    ct = np.sum([r["chase"]["tab"] for r in rows], axis=0)
    lt = np.sum([r["chase"]["lat"] for r in rows], axis=0)
    tl = np.sum([r["chase"]["tlen"] for r in rows], axis=0)
    out["chase"] = _chase_table(ct, lt, tl)
    # 기회에서 고른 행동별 뒤 잡힘(보고만): 모아서, 그리고 시드마다 'GRAZE − FLEE' 3초 안 잡힘 차(두 칸 모두 기회 5개 이상인 시드)
    ao = np.sum([r["a_out"] for r in rows], axis=0)          # [땅, 행동, 3]
    aa = ao.sum(0)
    out["A_out"] = {b: dict(n=int(aa[k, 0]), caught3s=_ratio(aa[k, 1], aa[k, 0]), caught8s=_ratio(aa[k, 2], aa[k, 0]))
                    for k, b in enumerate(BEHAVIOR_NAMES) if aa[k, 0]}
    out["A_out_terr"] = {TERR_LABELS[q]: {b: dict(n=int(ao[q, k, 0]), caught3s=_ratio(ao[q, k, 1], ao[q, k, 0]))
                                         for k, b in enumerate(BEHAVIOR_NAMES) if ao[q, k, 0]} for q in range(4) if ao[q, :, 0].sum()}
    g_, f_ = BEHAVIOR_NAMES.index("graze"), BEHAVIOR_NAMES.index("flee")
    gd, fd = [], []
    for r in rows:
        x = np.asarray(r["a_out"]).sum(0)
        ok = x[g_, 0] >= 5 and x[f_, 0] >= 5
        gd.append(x[g_, 1] / x[g_, 0] if ok else None)
        fd.append(x[f_, 1] / x[f_, 0] if ok else None)
    out["A_out_graze_minus_flee"] = _paired(gd, fd)
    # T0 (R3 지형 통계, 시드마다)
    if rows[0].get("r3") and rows[0]["r3"].get("deer_n_normal") is not None:
        out["t0"] = _t0(rows)
    # realism·r3 열 모으기
    for key in ("realism", "r3"):
        if key in rows[0]:
            agg = {}
            for k in rows[0][key]:
                vals = [r[key][k] for r in rows if r[key].get(k) is not None]
                if not vals:
                    agg[k] = None
                elif k.endswith("_n"):
                    agg[k] = float(np.sum(vals))
                else:
                    agg[k] = float(np.mean(vals))
            out[key] = agg
    if "r3" in rows[0] and rows[0]["r3"].get("wall_push_n") is not None:
        blk = sum(r["r3"].get("blocking_n", 0) * r["steps"] for r in rows)
        out["wall"] = dict(push_share=_ratio(out["r3"]["wall_push_n"], blk), slide_share=_ratio(out["r3"]["wall_slide_n"], blk),
                           dead_share=_ratio(out["r3"]["wall_stuck_n"], blk), giveup_n=out["r3"]["wall_giveup_n"],
                           inside_n=out["r3"]["wall_inside_n"], reset_n=out["r3"]["wall_reset_n"],
                           blocking_steps=blk)
        hi = [r for r in rows if r["world"]["cover_frac_target"] >= 0.25]
        if hi:
            bh_ = sum(r["r3"].get("blocking_n", 0) * r["steps"] for r in hi)
            out["wall"]["high_cover"] = dict(n_seeds=len(hi), push_share=_ratio(sum(r["r3"]["wall_push_n"] for r in hi), bh_),
                                             dead_share=_ratio(sum(r["r3"]["wall_stuck_n"] for r in hi), bh_))
    if "r3" in rows[0] and rows[0]["r3"].get("chase_held_n") is not None:
        thr = sum(r["world"]["M"] * r["steps"] for r in rows)
        rr_ = out["r3"]
        rel = {k: rr_[f"chase_rel_{k}_n"] for k in ("cover", "lost", "state", "catch", "dead")}
        out["chase_lock"] = dict(held_share=_ratio(rr_["chase_held_n"], thr), locks=rr_["chase_lock_n"],
                                 release=rel, release_share={k: _ratio(v, sum(rel.values())) for k, v in rel.items()},
                                 own_catch_share=_ratio(rr_["chase_catch_own_n"], rr_["chase_rel_catch_n"]),
                                 rel_cover_per_wolf_min=_ratio(rr_["chase_rel_cover_n"],
                                                               sum(r["world"]["M"] * r["steps"] / MINUTE for r in rows)))
    out["world"] = {k: [r["world"][k] for r in rows] for k in rows[0]["world"]}
    ps = out["per_seed"] = {k: [r[k] for r in rows] for k in ("g_gamma", "pred_rate", "starve_rate")}
    ps["death_rate"] = [r["pred_rate"] + r["starve_rate"] for r in rows]
    ps["A"] = A_seed
    ps["wolf_catch_min"] = wolf_min
    ps["in_cover_frac"] = [r["in_cover_frac"] for r in rows]
    ps["bouts_per_1k"] = [1000.0 * len(r["bouts"]["lengths"]) / r["n"] for r in rows]
    ps["flee_use"] = [r["beh"][1] / max(sum(r["beh"]), 1) for r in rows]
    if "cf_r1b" in out["A"]:
        ps["A_cf_r1b"] = out["A"]["cf_r1b"]["per_seed"]
    return out


def _hpct_int(h, q):
    c = np.cumsum(h)
    if not c[-1]:
        return None
    return int(np.searchsorted(c, q / 100.0 * c[-1]))


def _pounce_cells(pc) -> dict:
    """[칸, 땅, 거리, 결과] → 칸마다·칸 × 땅·거리마다 {n(끝난 돌진), hit(그 표적을 잡음 몫), any(어느 사슴이든 잡음 몫)}. 잘린 돌진은 n 에서 뺀다."""
    out = {}
    tot = pc[..., :3].sum()
    for ci, cat in enumerate(POUNCE_CATS):
        row = pc[ci]                                  # [땅, 거리, 결과]
        n = row[..., :3].sum()
        if not n:
            continue
        cell = dict(n=int(n), share=_ratio(n, tot), hit=_ratio(row[..., 0].sum(), n), any=_ratio(row[..., :2].sum(), n),
                    by_terr={}, by_dist={})
        for q in range(4):
            nq = row[q, :, :3].sum()
            if nq:
                cell["by_terr"][TERR_LABELS[q]] = dict(n=int(nq), hit=_ratio(row[q, :, 0].sum(), nq))
        for k, lab in enumerate(DIST_LABELS):
            nk = row[:, k, :3].sum()
            if nk:
                cell["by_dist"][lab] = dict(n=int(nk), hit=_ratio(row[:, k, 0].sum(), nk))
        out[cat] = cell
    allr = pc.sum(0)                                  # [땅, 거리, 결과]
    out["_all"] = dict(n=int(tot), hit=_ratio(allr[..., 0].sum(), tot),
                       by_terr={TERR_LABELS[q]: dict(n=int(allr[q, :, :3].sum()), hit=_ratio(allr[q, :, 0].sum(), allr[q, :, :3].sum()))
                                for q in range(4) if allr[q, :, :3].sum()},
                       by_dist={lab: dict(n=int(allr[:, k, :3].sum()), hit=_ratio(allr[:, k, 0].sum(), allr[:, k, :3].sum()))
                                for k, lab in enumerate(DIST_LABELS) if allr[:, k, :3].sum()})
    return out


def _pounce_table(pc) -> dict:
    """[이어 사냥, 칸, 땅, 거리, 결과] → 모두 합친 칸(이전 꼴)과 새 사냥·이어 사냥으로 나눈 칸."""
    pc = np.asarray(pc)
    out = _pounce_cells(pc.sum(0))
    tot = pc[..., :3].sum()
    out["_follow"] = {lab: dict(_pounce_cells(pc[f]), share=_ratio(pc[f][..., :3].sum(), tot))
                      for f, lab in enumerate(FOLLOW_LABELS)}
    return out


def _chase_table(ct, lt, tl=None) -> dict:
    """[종류, 행동 칸, 땅, 결과] → 추격형(근접 + 원거리)과 종류별: 칸마다 n·몫·안전에 닿기 전 잡힘(잡힘 ÷ (잡힘 + 은신처 + 멀어짐))."""
    out = {}
    for name, ks in (("chaser_all", (0, 1)), ("chaser", (0,)), ("ranged", (1,)), ("stalker", (2,)), ("player", (3,)),
                     ("all", (0, 1, 2, 3))):
        t = ct[list(ks)].sum(0)                     # [칸, 땅, 결과]
        ended = t[..., :3].sum()
        cell = dict(n=int(t.sum()), n_ended=int(ended),
                    caught=_ratio(t[..., 0].sum(), ended), cover=_ratio(t[..., 1].sum(), ended),
                    far=_ratio(t[..., 2].sum(), ended), cats={}, by_terr={})
        for ci, cat in enumerate(CHASE_CATS):
            e = t[ci, :, :3].sum()
            if e:
                cell["cats"][cat] = dict(n=int(e), share=_ratio(e, ended), caught=_ratio(t[ci, :, 0].sum(), e),
                                         cover=_ratio(t[ci, :, 1].sum(), e))
                if tl is not None:
                    z = tl[list(ks)].sum(0)[ci]
                    cell["cats"][cat]["mean_len"] = _ratio(z[1], z[0])
        L = lt[list(ks)].sum(0)                      # [땅, 지연]
        for q in range(4):
            e = t[:, q, :3].sum()
            if not e:
                continue
            lat = L[q]
            vals = np.repeat(np.arange(LAT_MAX + 1), lat[:LAT_MAX + 1])
            cell["by_terr"][TERR_LABELS[q]] = dict(
                n=int(e), caught=_ratio(t[:, q, 0].sum(), e),
                cats={cat: dict(n=int(t[ci, q, :3].sum()), caught=_ratio(t[ci, q, 0].sum(), t[ci, q, :3].sum()))
                      for ci, cat in enumerate(CHASE_CATS) if t[ci, q, :3].sum()},
                latency_p50=float(np.median(vals)) if len(vals) else None,
                latency_mean=float(vals.mean()) if len(vals) else None, no_react=_ratio(lat[LAT_MAX + 1], lat.sum()))
        out[name] = cell
    return out


def _t0(rows) -> dict:
    """세계 점검 T0 (명세 7-2): 땅별 개체-스텝당 잡힘. 시드마다 눈 − 보통, 거친 땅 − 보통(그 땅이 있는 시드만, 짝 t)."""
    per = []
    for r in rows:
        z = r["r3"]
        rate = {t: (z[f"catch_{t}_n"] / z[f"deer_n_{t}"] if z[f"deer_n_{t}"] else None) for t in ("normal", "snow", "rough")}
        per.append(dict(seed=r["seed"], rate=rate, deer={t: z[f"deer_n_{t}"] for t in ("normal", "snow", "rough")},
                        catch={t: z[f"catch_{t}_n"] for t in ("normal", "snow", "rough")},
                        snow_frac=z["snow_frac_actual"], rough_frac=z["rough_frac_actual"]))
    out = dict(per_seed=per)
    tot_deer = {t: sum(p["deer"][t] for p in per) for t in ("normal", "snow", "rough")}
    tot_catch = {t: sum(p["catch"][t] for p in per) for t in ("normal", "snow", "rough")}
    all_deer, all_catch = sum(tot_deer.values()), sum(tot_catch.values())
    out["pooled_per_1k"] = {t: _ratio(1000.0 * tot_catch[t], tot_deer[t]) for t in tot_deer}
    out["deer_share"] = {t: _ratio(tot_deer[t], all_deer) for t in tot_deer}
    out["catch_share"] = {t: _ratio(tot_catch[t], all_catch) for t in tot_catch}
    for t in ("snow", "rough"):
        a = [p["rate"][t] * 1000.0 if p["rate"][t] is not None else None for p in per]
        b = [p["rate"]["normal"] * 1000.0 if p["rate"][t] is not None and p["rate"]["normal"] is not None else None for p in per]
        out[f"{t}_minus_normal"] = _paired(a, b)
        out[f"{t}_seeds"] = sum(x is not None for x in a)
        # 표본이 작은 시드(그 땅 사슴-스텝 < 2% 몫)를 뺀 판(보고만)
        a2 = [x if x is not None and p["deer"][t] >= 0.02 * sum(p["deer"].values()) else None for x, p in zip(a, per)]
        out[f"{t}_minus_normal_ge2pct"] = _paired(a2, b)
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
    """1단계 PREREG 3절과 같다: 범위 밖(OUT)·지지 밖(SUPPORT)·분포 이동(SHIFT, 보고만)·결합 범위 J1."""
    feats = {}
    for k, nm in enumerate(names):
        one = {}
        for part, (h, mn, mx), rh in (("all", (var["h_all"][k], var["mn_all"][k], var["mx_all"][k]), ref["h_all"][k]),
                                      ("dec", (var["h_dec"][k], var["mn_dec"][k], var["mx_dec"][k]), ref["h_dec"][k])):
            rf_c = _coarse(rh)
            rf_p = rf_c / max(rf_c.sum(), 1)
            h = np.asarray(h)
            tot = h.sum()
            lo, hi = ref["mn_all"][k], ref["mx_all"][k]
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
        a, d = one["all"], one["dec"]
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
    return dict(features=feats, cond=cond, out01=var["out01"],
                j1=dict(seen=int(var["j1"][0]), viol=int(var["j1"][1]), max_excess=var["j1_max"]),
                flags=dict(out=[nm for nm in names if feats[nm]["flag_out"]],
                           support=[nm for nm in names if feats[nm]["flag_support"]],
                           shift=[nm for nm in names if feats[nm]["flag_shift"]]))


PAIR_KEYS = ("g_gamma", "pred_rate", "starve_rate", "death_rate", "A", "wolf_catch_min", "in_cover_frac", "bouts_per_1k")


def aggregate(results: list[dict], names) -> dict:
    cells = {}
    for r in results:
        cells.setdefault((r["variant"], r["policy"]), []).append(r)
    summ = {f"{v}|{p}": summarize_cell(rows) for (v, p), rows in cells.items()}
    comp = {}

    def pair(a_key, b_key, label):
        a, b = summ.get(a_key), summ.get(b_key)
        if a is None or b is None or a["seeds"] != b["seeds"]:
            return
        c = {k: _paired(a["per_seed"][k], b["per_seed"][k]) for k in PAIR_KEYS}
        c["rel"] = {k: (a[k] / b[k] - 1.0) if b[k] else None for k in ("pred_rate", "starve_rate", "death_rate")}
        comp[label] = dict(a=a_key, b=b_key, **c)

    # 규칙 하나씩 뺀 세계 − R3 세계(같은 정책)
    for p in R3_POLICIES:
        for v in R3_FAMILY[1:]:
            pair(f"{v}|{p}", f"r3|{p}", f"{v}-r3|{p}")
    # 같은 세계의 정책 − R1b−F
    for v in R3_FAMILY:
        for p in R3_POLICIES[1:]:
            pair(f"{v}|{p}", f"{v}|rlf", f"{v}|{p}-rlf")
    pair("r3_fz|rl", "r3|rlf", "r3|rl-rlf")
    pair("base|rlf", "base|rl", "base|rlf-rl")
    pair("night|rlf", "night|rl", "night|rlf-rl")
    pair("r3|rlf", "base|rl", "r3rlf-base_rl")             # R3 세계의 R1b−F − R1 세계의 R1b (학습 신호: 피식 크기)
    pair("night|rl", "base|rl", "night-base|rl")
    # A: 같은 상태에서 원래 R1b 가 골랐을 것(반사실) 대 R1b−F
    for v in R3_FAMILY + ("base", "night"):
        c = summ.get(f"{v}|rlf")
        if c is not None and "A_cf_r1b" in c["per_seed"]:
            comp[f"{v}|rlf_A-cf"] = dict(A=_paired(c["per_seed"]["A"], c["per_seed"]["A_cf_r1b"]))
    obs = {}
    ref_rows = [r for r in results if r["policy"] == "rl" and r["variant"] in REF_VARIANTS and "obs" in r]
    if ref_rows:
        ref = _obs_pool(ref_rows)
        for (v, p), rows in cells.items():
            if p in OBS_POLICIES and v != "train_ref" and "obs" in rows[0]:
                obs[f"{v}|{p}"] = obs_check(_obs_pool(rows), ref, names)
        obs["_ref"] = dict(variants=list(REF_VARIANTS), n=int(ref["h_all"][0].sum()), j1=ref["j1"].tolist(),
                           out01=ref["out01"])
        b_rows = [r for r in ref_rows if r["variant"] == "base"]
        t_rows = [r for r in ref_rows if r["variant"] == "train_ref"]
        if b_rows and t_rows:
            obs["_null"] = {"base_vs_train_ref": obs_check(_obs_pool(b_rows), _obs_pool(t_rows), names),
                            "train_ref_vs_base": obs_check(_obs_pool(t_rows), _obs_pool(b_rows), names)}
    hist = {}
    for (v, p), rows in cells.items():
        if p in OBS_POLICIES and "obs" in rows[0]:
            o = _obs_pool(rows)
            hist[f"{v}|{p}"] = {k: (x.tolist() if isinstance(x, np.ndarray) else x) for k, x in o.items()}
    return dict(summary=summ, compare=comp, obs=obs, _hist=hist)


# --------------------------------------------------------------------- #
# 표
# --------------------------------------------------------------------- #

VNAME = {"r3": "R3 세계", "no_chase": "추격 고정 뺌", "no_wall": "진입 금지 뺌", "no_terrain": "지형 뺌",
         "r3_fz": "R3 세계(얼기 허용 사본)", "base": "R1 판정 세계", "night": "R1 세계 + 밤잠", "train_ref": "R1b 학습 세계"}
PNAME = {"rlf": "R1b−F", "rl": "R1b(얼기 씀)", "rbase": "R_base", "c_graze": "늘 먹기", "c_flee": "늘 도망", "c_hide": "늘 숨기"}


def _f(x, nd=3):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def _pc(x, nd=1):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{100 * x:.{nd}f}%"


def _t(d):
    if d is None or d.get("t") is None:
        return "—"
    return f"{d['t']:+.2f}"


def _dt(d, nd=3, scale=1.0):
    if d is None or d.get("diff") is None:
        return "—"
    return f"{scale * d['diff']:+.{nd}f} ({_t(d)})"


def _cell_name(key):
    v, p = key.split("|")
    return f"{VNAME.get(v, v)} · {PNAME.get(p, p)}"


def tables(agg: dict, title: str) -> str:
    S, C = agg["summary"], agg.get("compare", {})
    meta = agg.get("meta", {})
    L = [f"# {title}", "", "자동 생성 표(`eval_pre.py`). 정의는 `PREREG.md`. 보정 시드 "
         f"{meta.get('seeds', ['?'])[0]}~{meta.get('seeds', ['?'])[-1]} × {meta.get('steps', '?')}스텝, 세계당 사슴 128마리.", "",
         "정책: R1b−F = R1b s3 에서 FREEZE 만 막음, R1b(얼기 씀) = 원래 R1b, R_base = (θ 4, a 0.9), 늘 먹기·늘 도망·늘 숨기 = 상수 대조. "
         "세계: R3 세계 = configs/v3_r3_on.yaml, '…뺌' = 그 규칙만 끈 R3 세계.", ""]
    order_main = [f"{v}|{p}" for v in R3_FAMILY for p in R3_POLICIES]
    order_extra = [f"{v}|{p}" for v, p in EXTRA_CELLS if v != "train_ref"]
    # 1. 생존·성과
    L += ["## 1. 생존·성과", "",
          "| 세계 · 정책 | 피식 /1000 | 아사 /1000 | 합 사망 /1000 | G_γ | 사용 GRAZE/FLEE/HIDE/FREEZE | 깜빡임 | 결정 비율 | 늑대 1마리 분당 포획 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None:
            continue
        u = c["use"]
        L.append(f"| {_cell_name(key)} | {_f(1000 * c['pred_rate'], 3)} | {_f(1000 * c['starve_rate'], 3)} | "
                 f"{_f(1000 * c['death_rate'], 3)} | {_f(c['g_gamma'], 3)} | "
                 + "/".join(_pc(u[b], 1) for b in ("graze", "flee", "hide", "freeze"))
                 + f" | {_f(c['flicker'], 2)} | {_pc(c['decide_frac'])} | {_f(c['wolf']['catch_per_wolf_min'], 3)} |")
    # 2. 규칙 하나씩 뺀 효과
    L += ["", "## 2. 규칙 하나씩 뺀 효과 (뺀 세계 − R3 세계, 같은 정책, 시드 짝 차와 t, 자유도 19)", "",
          "| 비교 | Δ피식 /1000 (t) | Δ아사 /1000 (t) | Δ합 사망 /1000 (t) | ΔG_γ (t) | Δ포기율 A (t) | Δ늑대 분당 포획 (t) | Δ은신처 안 시간 (t) |",
          "|---|---|---|---|---|---|---|---|"]
    for p in R3_POLICIES:
        for v in R3_FAMILY[1:]:
            c = C.get(f"{v}-r3|{p}")
            if c is None:
                continue
            L.append(f"| {VNAME[v]} · {PNAME[p]} | {_dt(c['pred_rate'], 3, 1000)} | {_dt(c['starve_rate'], 3, 1000)} | "
                     f"{_dt(c['death_rate'], 3, 1000)} | {_dt(c['g_gamma'])} | {_dt(c['A'])} | {_dt(c['wolf_catch_min'])} | "
                     f"{_dt(c['in_cover_frac'])} |")
    L += ["", "### 같은 세계의 정책 − R1b−F", "",
          "| 비교 | Δ피식 /1000 (t) | Δ아사 /1000 (t) | Δ합 사망 /1000 (t) | ΔG_γ (t) |", "|---|---|---|---|---|"]
    for v in R3_FAMILY:
        for p in R3_POLICIES[1:]:
            c = C.get(f"{v}|{p}-rlf")
            if c is None:
                continue
            L.append(f"| {VNAME[v]} · {PNAME[p]} − R1b−F | {_dt(c['pred_rate'], 3, 1000)} | {_dt(c['starve_rate'], 3, 1000)} | "
                     f"{_dt(c['death_rate'], 3, 1000)} | {_dt(c['g_gamma'])} |")
    # 3. R1b−F 대 R1b
    L += ["", "## 3. 얼기를 막은 R1b(R1b−F) 대 원래 R1b — H13 시작점·H21 자료", "",
          "| 비교 | Δ피식 /1000 (t) | Δ아사 /1000 (t) | Δ합 사망 /1000 (t) | ΔG_γ (t) | 상대 피식 | 상대 아사 |",
          "|---|---|---|---|---|---|---|"]
    for lab, text in (("r3|rl-rlf", "R3 세계: R1b − R1b−F"), ("base|rlf-rl", "R1 판정 세계: R1b−F − R1b"),
                      ("night|rlf-rl", "R1 세계 + 밤잠: R1b−F − R1b"), ("r3rlf-base_rl", "R3 세계 R1b−F − R1 판정 세계 R1b"),
                      ("night-base|rl", "R1 세계 + 밤잠 − R1 판정 세계 (R1b)")):
        c = C.get(lab)
        if c is None:
            continue
        rel = c["rel"]
        L.append(f"| {text} | {_dt(c['pred_rate'], 3, 1000)} | {_dt(c['starve_rate'], 3, 1000)} | {_dt(c['death_rate'], 3, 1000)} | "
                 f"{_dt(c['g_gamma'])} | {_pc(rel['pred_rate'], 0)} | {_pc(rel['starve_rate'], 0)} |")
    L += ["", "### R1b 가 얼었을 자리에서 R1b−F 가 고른 것 (같은 상태의 반사실: FREEZE 를 열었으면 R1b 가 FREEZE 를 고른 결정)", "",
          "| 세계 | 결정 수 | R1b 가 FREEZE 를 골랐을 몫 | → GRAZE | → FLEE | → HIDE | 감지 중 → GRAZE/FLEE/HIDE | 감지 없음 → GRAZE/FLEE/HIDE | 나머지 결정 같음 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for v in R3_FAMILY + ("base", "night"):
        c = S.get(f"{v}|rlf")
        if c is None or "cf" not in c:
            continue
        cf = c["cf"]
        az, s1, s0 = cf["at_freeze"], cf["at_freeze_seen"], cf["at_freeze_unseen"]
        L.append(f"| {VNAME[v]} | {cf['n_dec']} | {_pc(cf['freeze_share'])} | {_pc(az['graze'])} | {_pc(az['flee'])} | "
                 f"{_pc(az['hide'])} | {'/'.join(_pc(s1[b], 0) for b in ('graze', 'flee', 'hide'))} | "
                 f"{'/'.join(_pc(s0[b], 0) for b in ('graze', 'flee', 'hide'))} | {_pc(cf['same_elsewhere'], 2)} |")
    # 4. 포기율 A
    L += ["", "## 4. 쫓기는 동안 도주 포기율 A (명세 10절 정의)", "",
          "기회 = 결정 시점에 FLEE 중 & 쫓는 위협(지난 두 포식자 스텝에 이 사슴을 표적으로 삼은 깨어 있는 위협)이 실거리 10 안 & 은신처 밖. "
          "포기 = GRAZE(·SLEEP)로 바꿈(원래 R1b 는 FREEZE 도). A 는 시드 평균, '모아서'는 시드를 합친 값.", "",
          "| 세계 · 정책 | 기회 수 | 기회 /1000 | A (시드 평균) | A (모아서) | 기회에서 고른 GRAZE/FLEE/HIDE/FREEZE | 보통/눈/거친 땅 A (기회 수) | 같은 기회에서 원래 R1b 의 A |",
          "|---|---|---|---|---|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None:
            continue
        A = c["A"]
        bt = A["by_terr"]
        terr = "/".join(f"{_pc(bt[t]['A'], 0)} ({bt[t]['n']})" if t in bt else "—" for t in ("normal", "snow", "rough"))
        cfa = A.get("cf_r1b")
        L.append(f"| {_cell_name(key)} | {A['n_opp']} | {_f(A['opp_per_1k'], 3)} | {_pc(A['mean'])} | {_pc(A['pooled'])} | "
                 + "/".join(_pc(A['choice'][b], 0) for b in ("graze", "flee", "hide", "freeze"))
                 + f" | {terr} | {_pc(cfa['mean']) if cfa else '—'} |")
    lines = []
    for v in R3_FAMILY + ("base", "night"):
        c = C.get(f"{v}|rlf_A-cf")
        if c:
            lines.append(f"{VNAME[v]} {_dt(c['A'])}")
    if lines:
        L += ["", "R1b−F 의 A − 같은 기회에서 원래 R1b 의 A (시드 짝 차, t): " + "; ".join(lines) + "."]
    L += ["", "### 기회에서 고른 행동별로 그 뒤 잡힌 몫 (보고만, 변경 기록 10-15)", "",
          "같은 기회(쫓기며 도주 중인 결정)에서 계속 도망(FLEE)·먹기(GRAZE)·숨으러 감(HIDE)을 고른 뒤 3초(22스텝)·8초(60스텝) 안에 잡힌 몫. "
          "관찰 비교라 상태가 섞여 있다(먹기를 고른 때는 대개 위협이 멀어지거나 느려진 때다) — 인과가 아니다. 인과 비교는 관문 G1(침입)이 한다. "
          "'GRAZE − FLEE' 는 두 칸 모두 기회 5개 이상인 시드의 3초 안 잡힘 짝 차.", "",
          "| 세계 · 정책 | FLEE 3초/8초 (기회) | GRAZE 3초/8초 (기회) | HIDE 3초/8초 (기회) | FREEZE 3초/8초 (기회) | GRAZE − FLEE 3초 (t, 시드) | 눈에서 FLEE / GRAZE 3초 |",
          "|---|---|---|---|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None or not c.get("A_out"):
            continue
        ao = c["A_out"]

        def oc(b):
            x = ao.get(b)
            return f"{_pc(x['caught3s'], 0)}/{_pc(x['caught8s'], 0)} ({x['n']})" if x else "—"
        sn = c.get("A_out_terr", {}).get("snow", {})
        snow = "/".join(f"{_pc(sn[b]['caught3s'], 0)} ({sn[b]['n']})" if b in sn else "—" for b in ("flee", "graze"))
        gm = c["A_out_graze_minus_flee"]
        L.append(f"| {_cell_name(key)} | {oc('flee')} | {oc('graze')} | {oc('hide')} | {oc('freeze')} | "
                 f"{_dt(gm)}, {gm.get('n')} | {snow} |")
    L += ["", "### 관문 니치 초안의 선택 확률 (보고만, 명세 7-2·10절 U_KEEP·U_RUN·U_LEAVE)", "",
          "| 세계 · 정책 | G1 계속 도망 P(니치) / P(교차) (표본) | U_KEEP | G2 숨으러 감 P(니치)/P(교차) | U_RUN | G3 먹으러 나감 P(니치)/P(교차) | U_LEAVE | U_ESC(FLEE∪HIDE) | U_HIDE′ |",
          "|---|---|---|---|---|---|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None:
            continue
        gp, gu = c["g_p"], c["g_u"]

        def gcell(k):
            x = gp[k]
            return f"{_pc(x['niche'], 0)} / {_pc(x['cross'], 0)} ({x['n_niche']}/{x['n_cross']})"
        L.append(f"| {_cell_name(key)} | {gcell('keep')} | {_f(gu['keep'])} | {gcell('run')} | {_f(gu['run'])} | "
                 f"{gcell('leave')} | {_f(gu['leave'])} | {_f(c['u']['esc3'])} | {_f(c['u']['hide'])} |")
    # 5. 도주 묶음
    L += ["", "## 5. 도주 묶음 (1단계와 같은 정의, 보고만)", "",
          "| 세계 · 정책 | 묶음 /1000 | 길이 p25/p50/p75/p90 | <8 / 8 / 9-15 / 16-22 / 23-45 / 46-90 / 91+ | 끝 중 쫓김 | 쫓김 끝 /1000 | 쫓김 끝 중 멈춤-재도주 | ↳ 3초 안 잡힘 | 쫓김 끝 뒤 바꾼 행동 GRAZE/HIDE/FREEZE | 쫓김 끝 3초 안 잡힘 보통/눈/거친 땅 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None:
            continue
        fl = c["flee"]
        lp = fl["len_pct"]
        hh = fl["len_hist"]
        bt = fl["by_terr"]
        terr = "/".join(f"{_pc(bt[t]['caught3s'], 0)} ({bt[t]['n']})" if t in bt else "—" for t in ("normal", "snow", "rough"))
        L.append(f"| {_cell_name(key)} | {_f(fl['bouts_per_1k'], 2)} | {_f(lp['p25'], 0)}/{_f(lp['p50'], 0)}/{_f(lp['p75'], 0)}/"
                 f"{_f(lp['p90'], 0)} | {' / '.join(str(hh[k]) for k in hh)} | {_pc(fl['pursued_end_frac'])} | "
                 f"{_f(fl['pursued_per_1k'], 3)} | {_pc(fl['stop_go_given_pursued'])} | {_pc(fl['caught3s_given_pursued'])} | "
                 f"{'/'.join(_pc(fl['after'][b], 0) for b in ('graze', 'hide', 'freeze'))} | {terr} |")
    # 6. T0
    L += ["", "## 6. 세계 점검 T0 — 땅별 개체-스텝당 잡힘 (명세 7-2)", "",
          "잡힘은 잡힌 순간(초식 이동 뒤) 사슴 위치의 땅, 분모는 이동 전 위치의 땅별 사슴-스텝. 짝 차는 그 땅이 있는 시드만이다.", "",
          "| 세계 · 정책 | 사슴-스텝 몫 보통/눈/거친 땅 | 잡힘 몫 보통/눈/거친 땅 | 잡힘 /1000 보통/눈/거친 땅 (모아서) | 눈 − 보통 /1000 (t, 시드 수) | 거친 땅 − 보통 /1000 (t, 시드 수) | 눈 − 보통, 눈 몫 ≥ 2% 시드만 |",
          "|---|---|---|---|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None or "t0" not in c:
            continue
        t0 = c["t0"]
        tt = ("normal", "snow", "rough")
        L.append(f"| {_cell_name(key)} | {'/'.join(_pc(t0['deer_share'][t]) for t in tt)} | "
                 f"{'/'.join(_pc(t0['catch_share'][t]) for t in tt)} | {'/'.join(_f(t0['pooled_per_1k'][t], 3) for t in tt)} | "
                 f"{_dt(t0['snow_minus_normal'])}, {t0['snow_seeds']} | {_dt(t0['rough_minus_normal'])}, {t0['rough_seeds']} | "
                 f"{_dt(t0['snow_minus_normal_ge2pct'])}, {t0['snow_minus_normal_ge2pct']['n']} |")
    # 7. 확인표
    L += ["", "## 7. 사용자 추격 모형 확인표 (명세 7-2, 보고만)", "",
          "### 7-1. 잠행형 돌진 — 돌진 시작 때 표적 사슴의 상태별로 그 돌진이 그 사슴을 잡은 몫", "",
          "칸: 이미 도주 중(뛰는 중), 놀람 정지(FLEE 첫 3스텝 서 있음), 숨으러 가는 중, 얼기, 감지하고 먹는 중, 못 감지하고 먹는 중. "
          "감지 = 그 스텝 결정 관측의 pred_count > 0. 괄호는 끝난 돌진 수. "
          "**이어 사냥** = 그 잠행형이 직전 3초(22스텝) 안에 다른 사슴을 잡은 돌진(무리 안에서 먹이 쿨다운 5스텝이 끝나자마자 옆 사슴에게 돌진). "
          "**새 사냥** = 그 밖. 사용자 추격 모형('몰래 다가가 돌진')에 맞는 것은 새 사냥 줄이다(변경 기록 10-15).", "",
          "| 세계 · 정책 | 모든 돌진 | 이어 사냥 몫 | 새 사냥 모두 | " + " | ".join(f"새 사냥 {c}" for c in POUNCE_CATS[:6]) + " | 이어 사냥 모두 |",
          "|---|---|---|---|" + "---|" * 7]

    def pcell(x):
        return f"{_pc(x['hit'], 0)} ({x['n']})" if x else "—"
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None:
            continue
        pt = c["pounce"]
        fr, fo = pt["_follow"]["fresh"], pt["_follow"]["follow"]
        L.append(f"| {_cell_name(key)} | {pcell(pt['_all'])} | {_pc(fo['share'], 0)} | {pcell(fr['_all'])} | "
                 + " | ".join(pcell(fr.get(cat)) for cat in POUNCE_CATS[:6]) + f" | {pcell(fo['_all'])} |")
    L += ["", "#### 새 사냥의 시작 거리별 (실거리 <2 / 2-4 / 4+) — 그 표적을 잡은 몫 (돌진 수)", "",
          "| 세계 · 정책 | 칸 | <2 | 2-4 | 4+ |", "|---|---|---|---|---|"]
    for key in ("r3|rlf", "r3|rbase", "r3|c_graze", "r3|c_flee", "r3_fz|rl", "no_chase|rlf", "no_wall|rlf", "no_terrain|rlf"):
        c = S.get(key)
        if c is None:
            continue
        fr = c["pounce"]["_follow"]["fresh"]
        for cat in ("_all",) + POUNCE_CATS[:6]:
            x = fr.get(cat)
            if not x:
                continue
            bd = x["by_dist"]
            L.append(f"| {_cell_name(key)} | {cat} | " + " | ".join(pcell(bd.get(lab)) for lab in DIST_LABELS) + " |")
    L += ["", "#### 땅별 (새 사냥) — 칸마다 보통 / 눈 / 거친 땅", "",
          "| 세계 · 정책 | 칸 | 보통 | 눈 | 거친 땅 |", "|---|---|---|---|---|"]
    for key in ("r3|rlf", "r3|rbase", "r3|c_graze", "no_chase|rlf", "no_wall|rlf"):
        c = S.get(key)
        if c is None:
            continue
        fr = c["pounce"]["_follow"]["fresh"]
        for cat in ("_all",) + POUNCE_CATS[:6]:
            x = fr.get(cat)
            if not x:
                continue
            bt = x["by_terr"]
            L.append(f"| {_cell_name(key)} | {cat} | " + " | ".join(
                f"{_pc(bt[t]['hit'], 0)} ({bt[t]['n']})" if t in bt else "—" for t in ("normal", "snow", "rough")) + " |")
    L += ["", "### 7-2. 플레이어 대역 돌진 — 같은 칸 (보고만)", "",
          "| 세계 · 정책 | 모든 돌진 | " + " | ".join(POUNCE_CATS[:6]) + " |", "|---|---|" + "---|" * 6]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None:
            continue
        pt = c["charge"]
        if not pt["_all"]["n"]:
            continue
        cells = []
        for cat in POUNCE_CATS[:6]:
            x = pt.get(cat)
            cells.append(f"{_pc(x['hit'], 0)} ({x['n']})" if x else "—")
        L.append(f"| {_cell_name(key)} | {_pc(pt['_all']['hit'], 0)} ({pt['_all']['n']}) | " + " | ".join(cells) + " |")
    L += ["", "### 7-3. 추격형(근접 + 원거리)에게 쫓김이 시작된 사슴 — 안전에 닿기 전 잡힌 몫", "",
          "쫓김 = 쫓는 추격형이 실거리 10 안. 안전 = 은신처 원 안, 또는 22스텝 이어서 쫓기지 않음. 행동 칸(쫓기는 스텝과 잡힌 스텝의 행동만 본다, "
          "변경 기록 10-15): 반응 없음(FLEE·HIDE·FREEZE 없이 끝), 먹으러 멈춤(반응 뒤 쫓기는 중에 GRAZE), 얼기, 숨기(HIDE), 끝까지 도주(FLEE 만). "
          "칸마다 잡힌 몫 (끝난 쫓김 수, 평균 길이 스텝). **읽는 법 주의**: 칸은 묶음이 끝난 뒤에 정해지므로 길이에 치우친다 — 빨리 잡힌 묶음은 멈출 "
          "틈 없이 '끝까지 도주'로 남고, 오래 산 묶음일수록 '먹으러 멈춤'이 될 기회가 많다. '멈추면 잡히나'는 4절의 '고른 행동별 뒤 잡힘'과 관문 G1 로 본다.", "",
          "| 세계 · 정책 | 쫓김 수 | 잡힘 / 은신처 / 멀어짐 | 반응 없음 | 먹으러 멈춤 | 얼기 | 숨기 | 끝까지 도주 | 첫 반응까지 스텝 중앙값 보통/눈/거친 땅 | 잡힘 보통/눈/거친 땅 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None:
            continue
        ch = c["chase"]["chaser_all"]
        cats = []
        for cat in CHASE_CATS:
            x = ch["cats"].get(cat)
            cats.append(f"{_pc(x['caught'], 0)} ({x['n']}, {_f(x.get('mean_len'), 0)})" if x else "—")
        bt = ch["by_terr"]
        lat = "/".join(_f(bt[t]["latency_p50"], 0) if t in bt else "—" for t in ("normal", "snow", "rough"))
        cg = "/".join(f"{_pc(bt[t]['caught'], 0)} ({bt[t]['n']})" if t in bt else "—" for t in ("normal", "snow", "rough"))
        L.append(f"| {_cell_name(key)} | {ch['n_ended']} | {_pc(ch['caught'], 0)} / {_pc(ch['cover'], 0)} / {_pc(ch['far'], 0)} | "
                 + " | ".join(cats) + f" | {lat} | {cg} |")
    # 8. 은신처
    L += ["", "## 8. 은신처 — 시간·몰림·먹이·경계", "",
          "몰림 지수 = 은신처 안 시간 ÷ 은신처 넓이 몫(1 이면 고르게 퍼짐). '같은 원 다른 사슴' = 은신처 안 사슴-스텝마다 가장 깊이 든 원 안의 다른 사슴 수. "
          "먹이 채움 = 셀 먹이 합 ÷ 용량 합(10스텝마다). 면역 접촉 = 잡힐 거리인데 은신처 안이라 빠진 사슴-스텝.", "",
          "| 세계 · 정책 | 은신처 안 시간 | 은신처 넓이 | 몰림 지수 | 같은 원 다른 사슴 평균/p50/p90 | 5마리 이상과 함께 | 한 원 최대 | 먹이 채움 안/밖 | 섭취 중 은신처 몫 | 은신처 배수 f | 은신처 안 & 위협을 앎 | 넘나듦 /개체-분 | 3초 안 되돌아옴 | 면역 접촉 /1000 | 은신처 안 포획 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None:
            continue
        sh = c["shelter"]
        rz = c.get("realism") or {}
        r3 = c.get("r3") or {}
        n = len(c["seeds"]) * c["steps"] * 128
        imm = (1000.0 * rz["safe_saved_n"] / n) if rz.get("safe_saved_n") is not None else None
        L.append(f"| {_cell_name(key)} | {_pc(sh['in_cover_frac'])} | {_pc(sh['cover_frac_actual'])} | {_f(sh['crowd_index'], 2)} | "
                 f"{_f(sh['others_mean'], 1)}/{sh['others_p50']}/{sh['others_p90']} | {_pc(sh['others_ge5'])} | {sh['occ_max']} | "
                 f"{_pc(sh['food_fill_cover'], 0)}/{_pc(sh['food_fill_out'], 0)} | {_pc(rz.get('cover_intake_share'))} | "
                 f"{_f(r3.get('cover_food_cap'), 3)} | {_pc(sh['cover_k_share'])} | {_f(sh['cross_per_min'], 3)} | "
                 f"{_pc(sh['cross_quick'])} | {_f(imm, 3)} | {c['catch']['in_cover']} |")
    # 9. 늑대
    L += ["", "## 9. 늑대 — 은신처 둘레 미끄러짐·끼임·포획·추격 고정", "",
          "둘레에 붙음 = 깨어 있는 위협-스텝 중 은신처 원 둘레 바로 밖(0 ≤ 중심 거리 − r < 0.001). 끼임 = 둘레에 붙은 채 이번 스텝 이동 < 0.001. "
          "밀어냄·접선·막다른 곳 = 세계 통계 r3_stats(막는 위협-스텝 대비). 원 안 = 스텝 끝 원 안에 있는 막는 위협-스텝(늘 0 이어야 한다).", "",
          "| 세계 · 정책 | 늑대 분당 포획 | 둘레에 붙음 늑대/플레이어 | 밀어냄 | 접선 | 막다른 곳 | 플레이어 포기 | 원 안 | 끼임 연속 1/2/3-5/6-10/11-30/31+ (늑대) | 가장 긴 끼임 늑대/플레이어 | 은신처 25% 이상 세계 밀어냄/막다른 곳 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None:
            continue
        wl = c["wolf"]
        wa = c.get("wall")
        hc = (wa or {}).get("high_cover")
        L.append(f"| {_cell_name(key)} | {_f(wl['catch_per_wolf_min'], 3)} | {_pc(wl['rim_share_wolf'])}/{_pc(wl['rim_share_player'])} | "
                 f"{_pc(wa['push_share'], 2) if wa else '—'} | {_pc(wa['slide_share'], 3) if wa else '—'} | "
                 f"{_pc(wa['dead_share'], 3) if wa else '—'} | {_f(wa['giveup_n'], 0) if wa else '—'} | "
                 f"{wl['inside_blocking'] if wa else '—'} | {'/'.join(str(x) for x in wl['stuck_hist_wolf'])} | "
                 f"{wl['stuck_max_wolf']}/{wl['stuck_max_player']} | "
                 f"{(_pc(hc['push_share'], 2) + '/' + _pc(hc['dead_share'], 3) + ' (' + str(hc['n_seeds']) + '세계)') if hc else '—'} |")
    L += ["", "### 추격 고정 (f)", "",
          "| 세계 · 정책 | 고정을 쥔 위협-스텝 몫 | 새 고정 수 | 놓은 까닭 은신처/시야 밖/상태/잡음/죽음 | 잡음 중 고정한 표적 | 은신처로 표적을 잃음 /늑대-분 |",
          "|---|---|---|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None or "chase_lock" not in c:
            continue
        ck = c["chase_lock"]
        rs = ck["release_share"]
        L.append(f"| {_cell_name(key)} | {_pc(ck['held_share'])} | {_f(ck['locks'], 0)} | "
                 + "/".join(_pc(rs[k], 0) for k in ("cover", "lost", "state", "catch", "dead"))
                 + f" | {_pc(ck['own_catch_share'])} | {_f(ck['rel_cover_per_wolf_min'], 3)} |")
    # 10. 밤
    L += ["", "## 10. 밤 활동 (위상: 낮 d ≤ 0.2, 박명, 밤 d ≥ 0.8 — 결정 때 어둠)", "",
          "| 세계 · 정책 | 위상 | 스텝 몫 | 피식 /1000 | 아사 /1000 | 사슴 GRAZE/FLEE/HIDE/FREEZE | 은신처 안 | 늑대 깨어 있음 | 늑대 사냥 중 | 늑대 분당 포획 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for key in ("r3|rlf", "r3|rbase", "r3|c_graze", "r3_fz|rl", "no_chase|rlf", "no_wall|rlf", "no_terrain|rlf", "base|rl",
                "night|rl", "night|rlf"):
        c = S.get(key)
        if c is None:
            continue
        for ph in PHASES:
            x = c["night"][ph]
            L.append(f"| {_cell_name(key)} | {ph} | {_pc(x['frac_steps'])} | {_f(x['pred_per_1k'], 3)} | {_f(x['starve_per_1k'], 3)} | "
                     + "/".join(_pc(x['use'][b], 0) for b in ("graze", "flee", "hide", "freeze"))
                     + f" | {_pc(x['cover'])} | {_pc(x['wolf_awake'])} | {_pc(x['wolf_hunt'])} | {_f(x['wolf_catch_per_min'], 3)} |")
    L += ["", "| 세계 · 정책 | 늑대가 잠드는 순간 8 안에 사슴 | 늑대 잠든 비율 평균 |", "|---|---|---|"]
    for key in order_main + order_extra:
        c = S.get(key)
        if c is None:
            continue
        so = c["sleep_onset"]
        L.append(f"| {_cell_name(key)} | {so['deer_within_8']}/{so['n']} ({_pc(so['frac'])}) | {_f(c['pred_asleep_mean'], 3)} |")
    # 11. 관측
    O = agg.get("obs") or {}
    if O:
        L += ["", "## 11. 관측 범위 (기준: 원래 R1b 의 R1 판정 세계 ∪ R1b 학습 세계, 모든 개체-스텝)", "",
              f"기준 표본 {O['_ref']['n']} 개체-스텝. OUT = 기준 최솟값·최댓값 밖 값이 있음, SUPPORT = 기준에 표본이 없는 0.01 칸에 0.1% 넘게, "
              "SHIFT(보고만) = 전변동 거리 > 0.05. J1 = 감지된 위협의 pred_dist > 그 사슴의 지금 시야 반경(청각 자르기를 푼 R3 세계에서는 "
              "들은 위협이 시야 밖에 있을 수 있어 위반이 나오는 것이 정상이다, 명세 5-1).", "",
              "| 세계 · 정책 | OUT | SUPPORT | SHIFT | J1 위반 / 감지 표본 | [0,1] 밖 |", "|---|---|---|---|---|---|"]
        for key in order_main + order_extra:
            o = O.get(key)
            if o is None:
                continue
            fg = o["flags"]
            L.append(f"| {_cell_name(key)} | {', '.join(fg['out']) or '없음'} | {', '.join(fg['support']) or '없음'} | "
                     f"{', '.join(fg['shift']) or '없음'} | {o['j1']['viol']} / {o['j1']['seen']} | {o['out01']} |")
        for nm, o in (O.get("_null") or {}).items():
            fg = o["flags"]
            L.append(f"| (눈금) {nm} | {', '.join(fg['out']) or '없음'} | {', '.join(fg['support']) or '없음'} | "
                     f"{', '.join(fg['shift']) or '없음'} | {o['j1']['viol']} / {o['j1']['seen']} | {o['out01']} |")
        o = O.get("r3|rlf")
        if o:
            L += ["", "### 특성별 (R3 세계 · R1b−F, 결정 표본) — min/max·p1/p50/p99 대 기준, 전변동 거리", "",
                  "| 특성 | min (기준) | max (기준) | p1 | p50 | p99 | 기준 p1/p50/p99 | TV 결정 | TV 전체 | 범위 밖 몫(전체) |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
            for nm, x in o["features"].items():
                d, a = x["dec"], x["all"]
                rp = d["ref_pct"]
                L.append(f"| {nm} | {_f(d['min'])} ({_f(d['ref_min'])}) | {_f(d['max'])} ({_f(d['ref_max'])}) | "
                         f"{_f(d['pct']['p1'])} | {_f(d['pct']['p50'])} | {_f(d['pct']['p99'])} | "
                         f"{_f(rp['p1'])}/{_f(rp['p50'])}/{_f(rp['p99'])} | {_f(d['tv'])} | {_f(a['tv'])} | "
                         f"{_pc(a['out_share'], 3)} |")
        L += ["", "### 조건부 분포 (모든 개체-스텝) — p5/p50/p95 (전변동 거리)", "",
              "| 세계 · 정책 | " + " | ".join(COND_NAMES) + " |", "|---|" + "---|" * len(COND_NAMES)]
        for key in order_main + order_extra:
            o = O.get(key)
            if o is None:
                continue
            cells = []
            for nm in COND_NAMES:
                cc = o["cond"][nm]
                p_ = cc["pct"]
                cells.append(f"{_f(p_['p5'], 2)}/{_f(p_['p50'], 2)}/{_f(p_['p95'], 2)} (TV {_f(cc['tv'])})")
            L.append(f"| {_cell_name(key)} | " + " | ".join(cells) + " |")
        rc = O.get("base|rl")
        if rc:
            L += ["", "기준의 조건부 p5/p50/p95: " + "; ".join(
                f"{nm} {_f(rc['cond'][nm]['ref_pct']['p5'], 2)}/{_f(rc['cond'][nm]['ref_pct']['p50'], 2)}/"
                f"{_f(rc['cond'][nm]['ref_pct']['p95'], 2)}" for nm in COND_NAMES)]
    # 12. 세계 묘사
    c = S.get("r3|rlf")
    if c:
        wd = c["world"]
        t0 = c.get("t0", {}).get("per_seed", [])
        L += ["", "## 12. 시드별 세계 (R3 세계)", "",
              "| 시드 | 맵 한 변 | 위협 수 | 늑대 속력 배수 | 은신처 넓이 | 은신처 원 수 | 눈 넓이 | 거친 땅 넓이 | 은신처 배수 f |", "|---|---|---|---|---|---|---|---|---|"]
        rows = sorted([r for r in agg.get("raw", []) if r["variant"] == "r3" and r["policy"] == "rlf"], key=lambda r: r["seed"])
        for k, s in enumerate(c["seeds"]):
            tz = t0[k] if k < len(t0) else {}
            cap = rows[k]["r3"]["cover_food_cap"] if k < len(rows) else None
            L.append(f"| {s} | {_f(wd['size'][k], 0)} | {wd['M'][k]} | {_f(wd['pred_speed_mult'][k], 2)} | "
                     f"{_pc(wd['cover_frac_actual'][k])} | {wd['n_cover'][k]} | {_pc(tz.get('snow_frac'))} | "
                     f"{_pc(tz.get('rough_frac'))} | {_f(cap, 3)} |")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------- #


def _map(jobs, workers):
    from env.rollout import _init_worker

    if workers <= 1:
        return [job(j) for j in jobs]
    with ProcessPoolExecutor(min(workers, len(jobs)), initializer=_init_worker) as ex:
        return list(ex.map(job, jobs, chunksize=1))


def verify(seeds, steps) -> dict:
    """Spy(기록만)가 궤적을 바꾸지 않는지: 같은 시드·정책으로 World 와 Spy 를 나란히 돌려 스텝마다 보상·죽음·위치·포식자 위치·행동·
    추격 고정 표적이 비트 단위로 같은지 본다."""
    from env_v2 import rollout as ro
    from env_v2.world import World

    out = {}
    Spy = _spy_class()
    for v, p in (("r3", "rlf"), ("r3", "rbase"), ("no_wall", "rlf"), ("no_chase", "rlf"), ("base", "rl"), ("r3_fz", "rl")):
        cfg = load_variant(v)
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
                    extra = (w.chase_tgt.copy(),) if w._zc is not None else ()
                    res.append((r.copy(), d_.copy(), w.pos.copy(), w.pred_pos.copy(), w.behavior.copy()) + extra)
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
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    raise TypeError(type(x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "smoke", "tables", "verify"))
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    import os

    os.chdir(ROOT)
    from env_v2.world import obs_names

    names = list(obs_names(load_variant("r3")))
    if a.cmd == "verify":
        _check_seeds(VERIFY_SEEDS)
        print(json.dumps(verify(VERIFY_SEEDS, 600), indent=1))
        return
    if a.cmd == "smoke":
        _check_seeds(SMOKE_SEEDS)
        jobs = [(v, p, s, 200) for v, p in CELLS for s in SMOKE_SEEDS]
        res = _map(jobs, a.workers)
        agg = aggregate(res, names)
        agg["meta"] = dict(seeds=SMOKE_SEEDS, steps=200)
        agg["raw"] = [dict({k: v for k, v in r.items() if k not in ("obs", "bouts")}) for r in res]
        print(tables(agg, "smoke"))
        print({r["variant"] + "|" + r["policy"]: round(r["sec"], 1) for r in res})
        return
    if a.cmd == "tables":
        agg = json.loads((OUT_DIR / "pre.json").read_text(encoding="utf-8"))
        agg["raw"] = json.loads((OUT_DIR / "pre_raw.json").read_text(encoding="utf-8"))
        (OUT_DIR / "tables.md").write_text(tables(agg, "R3 재학습 전 측정"), encoding="utf-8")
        return
    _check_seeds(SEEDS)
    jobs = [(v, p, s, STEPS) for v, p in CELLS for s in SEEDS]
    t0 = time.time()
    res = _map(jobs, a.workers)
    agg = aggregate(res, names)
    agg["meta"] = dict(model=MODEL, seeds=SEEDS, steps=STEPS, variants={v: VARIANTS[v] for v in VARIANTS},
                       cells=[list(c) for c in CELLS], gamma=GAMMA, tail=TAIL, win_steps=WIN, pursue_r=PURSUE_R,
                       wall_sec=time.time() - t0, obs_names=names, spy_fail=int(sum(r["spy_fail"] for r in res)))
    drop = ("lengths", "len_sw", "len_death", "d_all", "d_purs")
    agg["raw"] = [dict({k: v for k, v in r.items() if k not in ("obs", "bouts")},
                       bouts={k: v for k, v in r["bouts"].items() if k not in drop}) for r in res]
    hist = agg.pop("_hist")
    (OUT_DIR / "pre_obs_hist.json").write_text(json.dumps(dict(names=names, nb=NB, cond=list(COND_NAMES), hist=hist),
                                                          default=_json_default), encoding="utf-8")
    # 요약·짝 비교·관측 점검은 읽기 쉽게(pre.json), 시드별 원자료는 촘촘하게(pre_raw.json) 쓴다
    (OUT_DIR / "pre.json").write_text(json.dumps({k: v for k, v in agg.items() if k != "raw"}, ensure_ascii=False, indent=1,
                                                 default=_json_default), encoding="utf-8")
    (OUT_DIR / "pre_raw.json").write_text(json.dumps(agg["raw"], ensure_ascii=False, separators=(",", ":"),
                                                     default=_json_default), encoding="utf-8")
    (OUT_DIR / "tables.md").write_text(tables(agg, "R3 재학습 전 측정"), encoding="utf-8")
    print(f"wrote pre.json in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
