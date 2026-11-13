"""R9 몸 움직임 모양 재기 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_TURN_EFFORT_DESIGN.md 7-1 마지막 줄 · 8-2 · 8-3 잣대).
세계를 바꾸지 않고 읽기만 한다 — 보고용이고, 어떤 숫자도 보상·판정·합격선이 아니다(8 절: 값을 이 숫자에 맞춰 고르지 않는다).

    python -X utf8 results/v3/r9/motion_shape.py --config configs/v3_r9_judge.yaml        --variant L1 --seeds 44180 44183 --steps 3000
    python -X utf8 results/v3/r9/motion_shape.py --config configs/v3_r9_judge_motion.yaml --variant L1 --seeds 44180 44183 --steps 3000
    python -X utf8 results/v3/r9/motion_shape.py --config configs/v3_r9_fauna_motion.yaml --seeds 44180 44187 --steps 6000 \\
        --brain wolf=<npz> --brain deer=RULE_DEER --out <scratch>/shape.json

옛 스크래치 도구 셋(SP/r9/turn_design/motion_measure.py · SP/r9/turn_review/body_wiggle.py · SP/r9/demo/turn_stats.py)을 합쳤다. 그 도구들은
demo 스냅숏(b3b8e668) + 바꿔치기 `_move` 였다. 이 도구는 저장소의 r9_world 를 그대로 싣는다 — motion 블록이 있는 설정이면 M1 이 켜진 세계,
없으면 옛 몸이다. 두 판을 따로 돌려 JSON 을 견준다(같은 시드·같은 두뇌).

두뇌 (--brain 종=값, 여러 번): 값이 ALL_RULE_NAMES 의 이름이면 규칙 두뇌, 아니면 npz 경로(이 설정의 몸 해시로 `load_brain` — 다른 몸의 두뇌는
rebody_r9.py 로 옮기거나 --no-body-check 로 가중치만 실음 = '학습 0 첫 반응'). 주지 않은 종은 그 종의 규칙 두뇌(RULE_OF).
시드: 판정 잠금 범위(44800~44999 · 46900~46999)는 거부한다. 시드 하나 = 세계 하나(K = 시드 수), 시드별 값을 함께 적는다.

잣대 (8-3, 종마다 · 시드마다):
  몸 기준 (스텝마다, 산 몸)
    turn_over        벽 아닌 스텝에서 머리가 θ 넘게 돈 몸-스텝 (motion 세계 st, 0 이어야 함; 옛 몸은 θ 가 없어 None)
    over90_steps     벽 아닌 스텝에서 한 스텝에 90° 넘게 돈 몸-스텝 · flip_steps 움직이던 몸의 속도가 머리 반대로 뒤집힌 몸-스텝
    wall_share       움직인 스텝(자기 속도 > EPS) 가운데 벽에 닿은 몫 · wall_turn 벽 스텝 머리 회전 분포(도) · wall_over_theta
  몸 기준 (결정마다, 같은 개체끼리 — body_wiggle 꼴. 걸음 띠: 속력 < 0.3 걷기 = 서기, < (걷기+뛰기)/2 = 걷기, 그 위 = 뛰기)
    body_turn_per_decision 실제 머리 회전 크기(걷기·뛰기 따로 가운데·상위 10%), share_turn_gt20, body_alt_share(실제 회전 부호 번갈이,
    |각| > 3° 만), left_share, gait_band_switch_share, starts_per_min(서기 띠 → 움직임 띠, 몸-분당)
  명령 기준 (turn_stats 꼴, 참고): action_share · stand_share(먹기+숨기+살피기) · dir_share_of_moves · zigzag_share(명령 부호 번갈이) ·
    head_turn_deg_per_s(이어 움직일 때 결정 사이 머리 돌림 ÷ 0.27 초) · action_change_share · run_streak(뛰기 명령이 이어진 결정 수)
  생태: alive_steps · 죽음(굶음·물림·반격)과 1,000 몸-스텝당 · 새로 남(newborns) · 잡은 수(kills_made, 물기 사건) ·
    엄격한 사냥 성공률(r9_eval_core.strict_stats 와 같은 차례: n_close > 4 인 다가감 구간 가운데 절반 넘게 걷기·뛰기인 것을 같은 몸끼리
    묶어 시도, 안에 죽임이 있으면 성공, 구간 밖이어도 걷기·뛰기 중 죽임은 시도 1·성공 1 — 사체로 가는 중 바꿔 적기는 없음, demo 셈과 같음)
결과: --out JSON (없으면 화면만). 화면에는 종별 한 줄 요약.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저 (r9_vec_env 가 torch 를 싣는다 — OpenMP 두 벌)
import numpy as np  # noqa: E402

from env_v2 import r9_body as B  # noqa: E402
from env_v2 import r9_brains as BR  # noqa: E402
from env_v2 import r9_vec_env as V  # noqa: E402
from env_v2 import r9_world as W  # noqa: E402
from env_v2.r9_world import EPS, R9World, _len2  # noqa: E402

DEC_S = B.DECISION_STEPS * B.STEP_S                 # 0.2667 초
KIND_NAMES = ("eat", "walk", "run", "shelter", "watch")
WALL_BINS = (0.0, 5.0, 15.0, 30.0, 45.0, 90.0, 180.0001)


def _abs(p) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def _kind(a: np.ndarray) -> np.ndarray:
    return np.where(a == B.EAT, 0, np.where((a >= B.WALK_FIRST) & (a <= B.WALK_LAST), 1,
                    np.where((a >= B.RUN_FIRST) & (a <= B.RUN_LAST), 2, np.where(a == B.SHELTER, 3, 4))))


def _sdeg(h0: np.ndarray, h1: np.ndarray) -> np.ndarray:
    """Signed head turn h0 → h1 in degrees (+ = left / ccw). Tool side only (the world never calls trig inside a step)."""
    c = h0[..., 0] * h1[..., 1] - h0[..., 1] * h1[..., 0]
    d = h0[..., 0] * h1[..., 0] + h0[..., 1] * h1[..., 1]
    return np.degrees(np.arctan2(c, d))


class ShapeWorld(R9World):
    """R9World + per-step body counters taken right after `_move` (reads only — the step is the parent's, bit for bit)."""

    def _move(self):
        h0 = self.head.copy()
        v0 = self.vel.copy()
        al = self.alive.copy()
        super()._move()
        a = self._shape
        wall = self._wall.any(-1)
        moving = al & (_len2(self._vel_free) > EPS * EPS)
        hit = moving & wall
        nowall = al & ~wall
        dot = (h0 * self.head).sum(-1)
        ang = np.abs(_sdeg(h0, self.head))
        over90 = nowall & (dot < 0.0)
        flip = nowall & (_len2(v0) > EPS * EPS) & ((self.vel * h0).sum(-1) < 0.0)
        if self._motion_turn:
            cl = _theta_cos(self, v0)
            wover = hit & (dot < cl - 1e-12)
        for s in range(self.NS):
            m = slice(int(self.sp_lo[s]), int(self.sp_hi[s]))
            a["alive_steps"][:, s] += al[:, m].sum(1)
            a["move_steps"][:, s] += moving[:, m].sum(1)
            a["wall_steps"][:, s] += hit[:, m].sum(1)
            a["over90_steps"][:, s] += over90[:, m].sum(1)
            a["flip_steps"][:, s] += flip[:, m].sum(1)
            for k in range(self.K):
                hk = hit[k, m]
                if hk.any():
                    x = ang[k, m][hk]
                    a["wall_turn_hist"][k, s] += np.histogram(x, bins=WALL_BINS)[0]
                    a["wall_turn_sum"][k, s] += float(x.sum())
            if self._motion_turn:
                a["wall_over_theta"][:, s] += wover[:, m].sum(1)


def _theta_cos(w, v0: np.ndarray) -> np.ndarray:
    """cos θ per slot (design 3-1), from the body table — the same rule as `_turn_limit`, written apart for the tool."""
    b = w.body
    sp = w.slot_sp.astype(np.int64)
    v = np.where((_len2(v0) > EPS * EPS)[..., None], v0, 0.0)
    s0 = np.sqrt(_len2(v))
    cb, sb_, au = b.turn_c[sp], b.turn_s[sp], b.lat_u[sp]
    fast = s0 * sb_ > au
    r = au / np.where(fast, s0, 1.0)
    return np.where(fast, np.sqrt(np.maximum(1.0 - r * r, 0.0)), cb)


def make_world(cfg: dict, seeds: list[int], counts) -> ShapeWorld:
    cnt = None if counts is None else np.tile(np.asarray(counts, dtype=np.int64), (len(seeds), 1))
    w = ShapeWorld(cfg, seeds, counts=cnt, record=True)
    K, NS = w.K, w.NS
    z = lambda *sh, dt=np.int64: np.zeros(sh, dtype=dt)  # noqa: E731
    w._shape = dict(alive_steps=z(K, NS), move_steps=z(K, NS), wall_steps=z(K, NS), over90_steps=z(K, NS), flip_steps=z(K, NS),
                    wall_turn_hist=z(K, NS, len(WALL_BINS) - 1), wall_turn_sum=z(K, NS, dt=np.float64), wall_over_theta=z(K, NS))
    return w


def load_controllers(cfg: dict, items: list[str], body_check: bool, stochastic: bool) -> tuple[dict, dict]:
    names = B.species_of(cfg)
    spec = {}
    for it in items:
        if "=" not in it:
            raise SystemExit(f"--brain needs <species>=<rule name | npz>: {it!r}")
        n, v = it.split("=", 1)
        if n not in names:
            raise SystemExit(f"--brain {n!r}: not a species of this config {names}")
        spec[n] = v
    ctr, lab = {}, {}
    for s, n in enumerate(names):
        v = spec.get(n, V.RULE_OF[s])
        if v in BR.ALL_RULE_NAMES:
            ctr[s] = BR.Controller(BR.make_rule(v, cfg, s), bool(stochastic), f"rule:{v}")
            lab[n] = f"rule:{v}"
            continue
        p = _abs(v)
        if body_check:
            br = BR.load_brain(p, cfg, s)
        else:
            with np.load(p, allow_pickle=False) as z:
                wts = {k: np.array(z[k]) for k in BR.NPZ_WEIGHT_KEYS}
                meta = json.loads(str(z["meta_json"][()]))
            if meta.get("species") != n:
                raise SystemExit(f"{p}: species {meta.get('species')!r} != {n!r}")
            br = BR.MlpBrain(name=f"raw:{p.name}", kind="mlp", species=s, n_state=0, weights=wts, meta=meta)
        ctr[s] = BR.Controller(br, bool(stochastic), f"mlp:{p.name}")
        lab[n] = f"mlp:{p.name}" + ("" if body_check else " (몸 해시 검사 끔)")
    return ctr, lab


class DecisionShape:
    """Per decision, per slot — the same individual (uid) as the previous decision. Vectorised over (K, S)."""

    def __init__(self, w):
        K, S, NS = w.K, w.S, w.NS
        self.ssp = w.slot_sp.astype(np.int64)
        self.p_uid = np.full((K, S), -1, dtype=np.int64)
        self.p_act = np.full((K, S), B.WATCH, dtype=np.int64)
        self.p_head = np.zeros((K, S, 2))
        self.p_sign = np.zeros((K, S), dtype=np.int64)        # last command turn sign (turn_stats)
        self.p_band = np.zeros((K, S), dtype=np.int64)
        self.p_bsign = np.zeros((K, S), dtype=np.int64)       # last real body turn sign (body_wiggle)
        self.p_rl = np.zeros((K, S), dtype=np.int64)
        z = lambda *sh: np.zeros(sh, dtype=np.int64)  # noqa: E731
        self.c = dict(kind=z(K, NS, 5), dirs=z(K, NS, 8), sw_n=z(K, NS), sw=z(K, NS), zz_n=z(K, NS), zz=z(K, NS), body_dec=z(K, NS),
                      n_pair=z(K, NS), big20=z(K, NS), alt_n=z(K, NS), alt=z(K, NS), walk_alt_n=z(K, NS), walk_alt=z(K, NS),
                      left=z(K, NS), right=z(K, NS), band_n=z(K, NS), band_sw=z(K, NS), starts=z(K, NS), clip_cmd=z(K, NS))
        self.lists = {s: dict(turn_dps=[], walk_abs=[], run_abs=[], run_len=[]) for s in range(NS)}
        self.acts: dict = {}                                  # (k, biter uid) → {t after the decision: action}
        self.uid_sp: dict = {}                                # (k, uid) → species (biters)
        self._biters = set(int(x) for x in w._biters)

    def _sum(self, key, mask):
        for s in range(self.c[key].shape[1]):
            self.c[key][:, s] += (mask & (self.ssp == s)[None, :]).sum(1)

    def on_decision(self, w, a: np.ndarray) -> None:
        al = w.alive
        U = w.uid
        H = w.head
        same = al & (U == self.p_uid)
        kind = _kind(a)
        j = B.action_dir_index(a)
        mv = al & (j >= 0)
        sign = np.where((j >= 1) & (j <= 3), 1, np.where(j >= 5, -1, 0))
        ki, si = np.nonzero(al)
        np.add.at(self.c["kind"], (ki, self.ssp[si], kind[ki, si]), 1)
        ki, si = np.nonzero(mv)
        np.add.at(self.c["dirs"], (ki, self.ssp[si], j[ki, si]), 1)
        self._sum("body_dec", al)
        self._sum("sw_n", same)
        self._sum("sw", same & (a != self.p_act))
        pmove = same & (B.action_dir_index(self.p_act) >= 0)
        zz = mv & pmove & (sign != 0) & (self.p_sign != 0)
        self._sum("zz_n", zz)
        self._sum("zz", zz & (sign != self.p_sign))
        cont = mv & pmove
        deg = np.abs(_sdeg(self.p_head, H))
        run = al & (kind == 2)
        ended = same & ~run & (self.p_rl > 0)
        sb = w.sb
        spd = np.sqrt(_len2(w.vel))
        ws, rs = sb["walk_speed"], sb["run_speed"]
        band = np.where(spd < 0.3 * ws, 0, np.where(spd < 0.5 * (ws + rs), 1, 2))
        both = same & (self.p_band >= 1) & (band >= 1)
        sang = _sdeg(self.p_head, H)
        turn = both & (np.abs(sang) > 3.0)
        cs = np.where(sang > 0.0, 1, -1)
        alt = turn & (self.p_bsign != 0)
        self._sum("n_pair", both)
        self._sum("big20", both & (np.abs(sang) > 20.0))
        self._sum("left", turn & (cs > 0))
        self._sum("right", turn & (cs < 0))
        self._sum("alt_n", alt)
        self._sum("alt", alt & (cs != self.p_bsign))
        walt = alt & (band == 1) & (self.p_band == 1)
        self._sum("walk_alt_n", walt)
        self._sum("walk_alt", walt & (cs != self.p_bsign))
        self._sum("band_n", same)
        self._sum("band_sw", same & (band != self.p_band))
        self._sum("starts", same & (self.p_band == 0) & (band >= 1))
        for s in range(w.NS):
            m = (self.ssp == s)[None, :]
            L = self.lists[s]
            L["turn_dps"].append(deg[cont & m] / DEC_S)
            L["walk_abs"].append(np.abs(sang[both & (band == 1) & m]))
            L["run_abs"].append(np.abs(sang[both & (band == 2) & m]))
            L["run_len"].append(self.p_rl[ended & m])
        # biter actions for the strict hunt count (key = t after this decision, the hunt tracker's clock)
        t_after = w.t + w.D
        for k, s in zip(*np.nonzero(al)):
            if int(s) in self._biters:
                key = (int(k), int(U[k, s]))
                self.acts.setdefault(key, {})[int(t_after[k])] = int(a[k, s])
                self.uid_sp[key] = int(self.ssp[s])
        # carry to the next decision
        self.p_sign = np.where(mv, sign, np.where(same, self.p_sign, 0))
        self.p_bsign = np.where(turn, cs, np.where(both, self.p_bsign, 0))
        self.p_rl = np.where(same, np.where(run, self.p_rl + 1, 0), run.astype(np.int64))
        self.p_uid = np.where(al, U, -1)
        self.p_act = a.copy()
        self.p_head = H.copy()
        self.p_band = band

    def after_step(self, w) -> None:
        """Biters born inside the decision get their species too (kills attribution)."""
        for k, s in zip(*np.nonzero(w.alive)):
            if int(s) in self._biters:
                self.uid_sp.setdefault((int(k), int(w.uid[k, s])), int(self.ssp[s]))


def strict_hunts(w, ds: DecisionShape) -> dict:
    """Strict hunt success per biter species and world (r9_eval_core.strict_stats order, demo test_demo.strict_stats acts)."""
    K, NS = w.K, w.NS
    att = np.zeros((K, NS), dtype=np.int64)
    suc = np.zeros((K, NS), dtype=np.int64)
    inc = np.zeros((K, NS), dtype=np.int64)
    by: dict = {}
    for h in w.events["hunts"]:
        if int(h["n_close"]) <= W.HUNT_MIN_DECISIONS:
            continue
        key = (int(h["k"]), int(h["wolf_uid"]))
        aa = ds.acts.get(key, {})
        v = [aa[t] for t in range(int(h["t0"]) + 2, int(h["t1"]) + 1, 2) if t in aa]
        if v and sum(1 for x in v if B.WALK_FIRST <= x <= B.RUN_LAST) > 0.5 * len(v):
            by.setdefault(key, []).append([int(h["t0"]), int(h["t1"])])
    eps = {}
    for key, iv in by.items():
        iv.sort()
        mm: list = []
        for a_, b_ in iv:
            if mm and a_ <= mm[-1][1]:
                mm[-1][1] = max(mm[-1][1], b_)
            else:
                mm.append([a_, b_])
        eps[key] = mm
        sp = ds.uid_sp.get(key)
        if sp is not None:
            att[key[0], sp] += len(mm)
    hit = set()
    kills = np.zeros((K, NS), dtype=np.int64)
    for e in w.events["bites"]:
        if e["outcome"] != "kill":
            continue
        k = int(e["k"])
        key = (k, int(e["wolf_uid"]))
        sp = ds.uid_sp.get(key)
        if sp is None:
            continue
        kills[k, sp] += 1
        found = None
        for i, (a_, b_) in enumerate(eps.get(key, [])):
            if a_ <= int(e["t"]) <= b_:
                found = i
                break
        if found is not None:
            if (key, found) not in hit:
                hit.add((key, found))
                suc[k, sp] += 1
            continue
        aa = ds.acts.get(key, {})
        act = next((aa[t] for t in (int(e["t"]) + 1, int(e["t"]) + 2) if t in aa), -1)
        if B.WALK_FIRST <= act <= B.RUN_LAST:
            att[k, sp] += 1
            suc[k, sp] += 1
        else:
            inc[k, sp] += 1
    return dict(attempts=att, successes=suc, incidental=inc, kills=kills)


def _q(x: np.ndarray, p: float):
    return None if x.size == 0 else round(float(np.percentile(x, p)), 2)


def _r(x, n=4):
    return None if x is None else round(float(x), n)


def _share(num, den):
    return None if den <= 0 else round(float(num) / float(den), 4)


def summarize(w, ds: DecisionShape, hs: dict, seeds: list[int]) -> dict:
    st = w.st
    sh = w._shape
    out = {}
    c = ds.c
    for s, n in enumerate(w.names):
        L = {k: (np.concatenate(v) if v else np.zeros(0)) for k, v in ds.lists[s].items()}
        alive = sh["alive_steps"][:, s]
        dth = st["deaths"][:, s]
        per = lambda arr: [int(x) for x in arr]  # noqa: E731
        per_r = lambda num, den: [_share(a_, b_) for a_, b_ in zip(num, den)]  # noqa: E731
        k_tot = c["kind"][:, s].sum(0)
        nk = max(int(k_tot.sum()), 1)
        d8 = c["dirs"][:, s].sum(0)
        nd = max(int(d8.sum()), 1)
        mins = c["body_dec"][:, s] * DEC_S / 60.0
        o = dict(
            alive_steps=int(alive.sum()),
            # 몸 기준 — 스텝
            turn_over=int(st["turn_over"][:, s].sum()) if "turn_over" in st else None,
            turn_clip=int(st["turn_clip"][:, s].sum()) if "turn_clip" in st else None,
            over90_steps=int(sh["over90_steps"][:, s].sum()),
            flip_steps=int(sh["flip_steps"][:, s].sum()),
            move_steps=int(sh["move_steps"][:, s].sum()),
            wall_steps=int(sh["wall_steps"][:, s].sum()),
            wall_share=_share(sh["wall_steps"][:, s].sum(), sh["move_steps"][:, s].sum()),
            wall_turn=dict(bins_deg=list(WALL_BINS[:-1]), hist=per(sh["wall_turn_hist"][:, s].sum(0)),
                           mean=_share(sh["wall_turn_sum"][:, s].sum(), sh["wall_steps"][:, s].sum())),
            wall_over_theta=int(sh["wall_over_theta"][:, s].sum()) if w._motion_turn else None,
            # 몸 기준 — 결정
            body_turn_per_decision=dict(walk_median=_q(L["walk_abs"], 50), walk_p90=_q(L["walk_abs"], 90),
                                        run_median=_q(L["run_abs"], 50), run_p90=_q(L["run_abs"], 90)),
            share_turn_gt20=_share(c["big20"][:, s].sum(), c["n_pair"][:, s].sum()),
            body_alt_share=_share(c["alt"][:, s].sum(), c["alt_n"][:, s].sum()),
            walk_body_alt_share=_share(c["walk_alt"][:, s].sum(), c["walk_alt_n"][:, s].sum()),
            left_share=_share(c["left"][:, s].sum(), c["left"][:, s].sum() + c["right"][:, s].sum()),
            gait_band_switch_share=_share(c["band_sw"][:, s].sum(), c["band_n"][:, s].sum()),
            starts_per_min=_share(c["starts"][:, s].sum(), mins.sum()),
            # 명령 기준 (참고)
            decisions=int(k_tot.sum()),
            action_share={nm: round(float(k_tot[i]) / nk, 4) for i, nm in enumerate(KIND_NAMES)},
            stand_share=round(float(k_tot[0] + k_tot[3] + k_tot[4]) / nk, 4),
            dir_share_of_moves=dict(straight=round(float(d8[0]) / nd, 4), turn45=round(float(d8[1] + d8[7]) / nd, 4),
                                    turn90=round(float(d8[2] + d8[6]) / nd, 4), turn135=round(float(d8[3] + d8[5]) / nd, 4),
                                    uturn180=round(float(d8[4]) / nd, 4)),
            zigzag_share=_share(c["zz"][:, s].sum(), c["zz_n"][:, s].sum()),
            head_turn_deg_per_s=dict(median=_q(L["turn_dps"], 50), mean=None if L["turn_dps"].size == 0 else _r(L["turn_dps"].mean(), 2)),
            action_change_share=_share(c["sw"][:, s].sum(), c["sw_n"][:, s].sum()),
            run_streak_decisions=dict(median=_q(L["run_len"], 50), mean=None if L["run_len"].size == 0 else _r(L["run_len"].mean(), 2),
                                      n=int(L["run_len"].size)),
            # 생태
            starved=int(dth[:, W.CAUSE_STARVE].sum()), caught=int(dth[:, W.CAUSE_BITE].sum()), counter_deaths=int(dth[:, W.CAUSE_COUNTER].sum()),
            starved_1k=_share(1000.0 * dth[:, W.CAUSE_STARVE].sum(), alive.sum()),
            caught_1k=_share(1000.0 * dth[:, W.CAUSE_BITE].sum(), alive.sum()),
            newborns=int(st["newborns"][:, s].sum()), birth_credits=int(st["birth_credits"][:, s].sum()),
            kills_made=int(hs["kills"][:, s].sum()),
            end_alive=int(w.alive[:, int(w.sp_lo[s]):int(w.sp_hi[s])].sum()),
        )
        if bool(w.body.can_bite[s]):
            o["strict_hunt"] = dict(attempts=int(hs["attempts"][:, s].sum()), successes=int(hs["successes"][:, s].sum()),
                                    rate=_share(hs["successes"][:, s].sum(), hs["attempts"][:, s].sum()),
                                    incidental=int(hs["incidental"][:, s].sum()))
        o["per_seed"] = dict(
            seed=list(seeds),
            turn_over=per(st["turn_over"][:, s]) if "turn_over" in st else None,
            over90_steps=per(sh["over90_steps"][:, s]),
            wall_share=per_r(sh["wall_steps"][:, s], sh["move_steps"][:, s]),
            body_alt_share=per_r(c["alt"][:, s], c["alt_n"][:, s]),
            zigzag_share=per_r(c["zz"][:, s], c["zz_n"][:, s]),
            starts_per_min=[_share(a_, b_) for a_, b_ in zip(c["starts"][:, s], mins)],
            stand_share=per_r(c["kind"][:, s, 0] + c["kind"][:, s, 3] + c["kind"][:, s, 4], c["kind"][:, s].sum(1)),
            starved=per(dth[:, W.CAUSE_STARVE]), caught=per(dth[:, W.CAUSE_BITE]), newborns=per(st["newborns"][:, s]),
            alive_steps=per(alive), kills_made=per(hs["kills"][:, s]),
            strict_rate=per_r(hs["successes"][:, s], hs["attempts"][:, s]) if bool(w.body.can_bite[s]) else None,
            end_alive=per(w.alive[:, int(w.sp_lo[s]):int(w.sp_hi[s])].sum(1)),
        )
        out[n] = o
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, help="R9 설정 (herbivore_rl 기준 상대 경로 또는 절대 경로)")
    ap.add_argument("--variant", default=None, help="판정 설정의 judge.variants 이름 (예: L1)")
    ap.add_argument("--brain", action="append", default=[], help="<종>=<규칙 이름 | npz> (여러 번)")
    ap.add_argument("--no-body-check", action="store_true", help="npz 를 몸 해시 검사 없이 가중치만 싣는다 (학습 0 첫 반응)")
    ap.add_argument("--stochastic", action="store_true")
    ap.add_argument("--seeds", type=int, nargs=2, default=[44180, 44183], metavar=("LO", "HI"), help="양 끝 포함")
    ap.add_argument("--steps", type=int, default=3000, help="세계 스텝 (결정 = 스텝 / 2)")
    ap.add_argument("--counts", type=int, nargs="+", default=None, help="종마다 시작 수 (-1 = 시드로 뽑음; 학습 세계만)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    cfg = B.load_r9_config(_abs(a.config))
    if a.variant:
        cfg = B.override(cfg, cfg["judge"]["variants"][a.variant])
    seeds = list(range(a.seeds[0], a.seeds[1] + 1))
    V.check_train_seeds(seeds)
    if a.counts is not None and len(a.counts) != len(B.species_of(cfg)):
        raise SystemExit(f"--counts needs {len(B.species_of(cfg))} numbers ({B.species_of(cfg)})")
    ctr, lab = load_controllers(cfg, a.brain, not a.no_body_check, a.stochastic)
    w = make_world(cfg, seeds, a.counts)
    for k in range(w.K):
        for s, c_ in ctr.items():
            if int(w.caps[s]) > 0:
                w.set_controller(k, s, c_)
    ds = DecisionShape(w)
    t0 = time.time()
    for _ in range(a.steps // w.D):
        act = w.decide()
        ds.on_decision(w, act)
        w.step(act)
        ds.after_step(w)
    w.flush_hunts()
    hs = strict_hunts(w, ds)
    res = dict(label=a.label, config=str(a.config), variant=a.variant, seeds=seeds, steps=a.steps, wall_s=round(time.time() - t0, 1),
               brains=lab, stochastic=bool(a.stochastic),
               motion=dict(on=bool(w.body.motion), turn=bool(w.body.motion_turn), effort=bool(w.body.motion_effort)),
               body_hash={n: B.hash_hex(B.body_hash(cfg, n)) for n in w.names},
               species=summarize(w, ds, hs, seeds))
    for n, o in res["species"].items():
        sh_ = o.get("strict_hunt")
        print(f"{n:8s} over90 {o['over90_steps']:6d} turn_over {o['turn_over']} wall {o['wall_share']} "
              f"turn°/s {o['head_turn_deg_per_s']['mean']} zigzag {o['zigzag_share']} body_alt {o['body_alt_share']} "
              f"starts/min {o['starts_per_min']} run_streak {o['run_streak_decisions']['median']}/{o['run_streak_decisions']['mean']} "
              f"stand {o['stand_share']} starve {o['starved']} caught {o['caught']} born {o['newborns']} kills {o['kills_made']}"
              + (f" strict {sh_['successes']}/{sh_['attempts']}={sh_['rate']}" if sh_ else ""), flush=True)
    print(f"{res['wall_s']} s · motion {res['motion']} · brains {lab}", flush=True)
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print("wrote", p, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
