"""R9 몸 움직임 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_TURN_EFFORT_DESIGN.md 7-3 M-1~M-16).

M-1 은 손대기 전 HEAD(1b545095 의 R9 파이썬) 에서 잰 옛 설정 셋(`v3_r9.yaml`·`v3_r9_judge.yaml`·`v3_r9_fauna.yaml`) 의 궤적
sha256 기준값이다(특성 문서 B5 꼴). F-1 은 S′ 만 지키므로 동물 세계 기준이 따로 필요하다. 새 몸 규칙은 `body_common.motion` 이
있을 때만 켜지므로 고친 뒤에도 셋 모두 비트까지 같아야 한다.
시드: 스모크·속도 범위 44180~44199 만 쓴다(동물 설계 7-3 과 같음).
"""

import env.torch_init  # noqa: F401  ← torch 보다 먼저

import hashlib
import json

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import r9_body as B
from env_v2 import r9_brains as BR
from env_v2 import r9_life as L
from env_v2 import r9_vec_env as V
from env_v2.r9_world import R9World

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"
FCFG = ROOT / "configs" / "v3_r9_fauna.yaml"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")

# 손대기 전 HEAD 1b545095 기준값 (이 파일의 `old_golden()` 을 그 HEAD 에서 돌려 잼, 2026-11-13)
GOLDEN = {
    "sp_random": "98ee6d153e298eb906260379c4365aa3e585378073813163b56ab31a1bade301",
    "sp_rules": "7f409fc237b5e6b6c3cd522f40b51142c00c9dfd25066fdd9fadf287dc44362d",
    "sp_rules_deaths": [[0, 9, 0, 6], [0, 0, 0, 0], [0, 2, 0, 0]],
    "sp_vec_wolf": "e811b506da3408b4cccd21daf89a162570ef65d3ad103b513c32d3dbb73fee40",
    "sp_hash": {"io_hash": "0x0fa76480fe9465e0",
                "body_hash": {"deer": "0x0d04b5447e42a2c0", "wolf": "0x6ce9605c7a90224a", "boar": "0x8af5915146034953"},
                "body_table_hash": "0xf6e81fcbe4e7c24d"},
    "judge_rules": "131cc4a3bdbffa39ac42ba6f563fc6893f0f750c0fc0547799ee5133968f8ce3",
    "judge_L1_rules": "634325dbab98619f255f8f487d1f1d087f341847158251ce6d57b356fcf1f184",
    "judge_L1_deaths": [[0, 5, 0, 0], [0, 0, 0, 0], [0, 1, 0, 0]],
    "judge_hash": {"io_hash": "0x0fa76480fe9465e0",
                   "body_hash": {"deer": "0x0d04b5447e42a2c0", "wolf": "0x6ce9605c7a90224a", "boar": "0x8af5915146034953"},
                   "body_table_hash": "0xf6e81fcbe4e7c24d"},
    "fauna_random": "18281f0c299160ce0986789210c59075a4f75398ee45ee6c44a3745c97a7b424",
    "fauna_rules": "93c534dfe3ee6d7844b5f6f3c4dea84eed8eea7bde2693792c20848917754646",
    "fauna_rules_deaths": [[0, 8, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
    "fauna_rules_gore": 11,
    "fauna_rules_stoch": "34cfc4b58b6b9110a131a0db680babfc6721917e4a5d6a9b672a6c82418f3e8c",
    "fauna_vec_leopard": "e766d31336f3e71297c73845f7a417c2530349ab1f45e7c65c627dd2a3b26f6a",
    "fauna_hash": {"io_hash": "0x0fa76480fe9465e0",
                   "body_hash": {"deer": "0x2ffa857d6bb1b4b4", "wolf": "0x69532181ee44398b", "boar": "0xd68f2e620798ada3",
                                 "buffalo": "0x44e493d8cc7b39bf", "leopard": "0xc90ea238572238e3", "fox": "0xf8af612d4db1993b"},
                   "body_table_hash": "0x10021edf18997ee3"},
}

STATE = ("pos", "head", "vel", "disp", "E", "R", "stam", "stam_lock", "hp", "alive", "uid", "kin_id", "next_birth", "mating",
         "bite_cd", "gore_cd", "knock_left", "carc_ok", "carc_meat", "carc_places", "grass", "root", "mem")


def _upd(h, *xs):
    for x in xs:
        h.update(np.ascontiguousarray(np.asarray(x)).tobytes())


def _world_hash(w, h):
    for n in STATE:
        _upd(h, getattr(w, n))
    for k, v in sorted(w.stats_snapshot().items()):
        h.update(k.encode())
        _upd(h, v)


def _rules(w, cfg, stochastic=False):
    for k in range(w.K):
        for s in range(w.NS):
            n = V.RULE_OF[s]
            w.set_controller(k, s, BR.Controller(BR.make_rule(n, cfg, s), stochastic, n))


def _random_scene(cfg, seeds, n_dec, seed):
    w = R9World(cfg, seeds)
    rng = np.random.default_rng(seed)
    h = hashlib.sha256()
    _upd(h, w.obs())
    for _ in range(n_dec):
        o, r, d, info = w.step(rng.integers(0, B.N_ACTIONS, (w.K, w.S)))
        _upd(h, o, r, d, info["dead_cause"], info["killer"], info["births"], info["respawned"])
    _world_hash(w, h)
    return h.hexdigest()


def _rule_scene(cfg, seeds, n_dec, stochastic=False):
    w = R9World(cfg, seeds, record=True)
    _rules(w, cfg, stochastic)
    h = hashlib.sha256()
    _upd(h, w.obs())
    for _ in range(n_dec):
        a = w.decide()
        o, r, d, info = w.step(a)
        _upd(h, a, o, r, d, info["dead_cause"], info["killer"], info["births"], info["newborn"])
    w.flush_hunts()
    _world_hash(w, h)
    ls = L.life_stats(w.life)
    for k in ("opportunities", "paired", "births", "blocked", "failed", "cancelled"):
        _upd(h, ls[k])
    h.update(json.dumps({k: v for k, v in w.events.items()}, sort_keys=True, default=str).encode())
    return h.hexdigest(), w


def _vec_scene(cfg, sp, seeds, n_dec, seed):
    v = V.R9VecEnv(cfg, sp, model_seed=0, round_=0, seeds=seeds, num_worlds=4, reset_steps=20, shards=1, online_stats=False)
    try:
        h = hashlib.sha256()
        _upd(h, v.reset())
        r_ = np.random.default_rng(seed)
        for _ in range(n_dec):
            v.step_async(r_.integers(0, B.N_ACTIONS, v.num_envs))
            o, r, d, infos = v.step_wait()
            _upd(h, o, r, d)
        h.update(json.dumps(v.history, sort_keys=True, default=str).encode())
        h.update(json.dumps(v.seed_history).encode())
        return h.hexdigest()
    finally:
        v.close()


def _hashes(cfg) -> dict:
    names = B.species_of(cfg)
    return {"io_hash": B.hash_hex(B.io_hash()),
            "body_hash": {n: B.hash_hex(B.body_hash(cfg, n)) for n in names},
            "body_table_hash": B.hash_hex(B.body_table_hash(cfg))}


def old_golden(cfg: dict, jcfg: dict, fcfg: dict) -> dict:
    """The old-config scenes (same order, seeds and hashing at HEAD and after the change)."""
    out = {}
    # v3_r9.yaml (S′ 학습 세계)
    out["sp_random"] = _random_scene(cfg, [44180, 44181], 120, 44182)
    out["sp_rules"], w = _rule_scene(cfg, [44183, 44184], 300)
    out["sp_rules_deaths"] = w.st["deaths"].sum(0).tolist()
    out["sp_vec_wolf"] = _vec_scene(cfg, "wolf", range(44185, 44195), 30, 44195)
    out["sp_hash"] = _hashes(cfg)
    # v3_r9_judge.yaml (판정 세계 그대로 + L1)
    out["judge_rules"], w = _rule_scene(jcfg, [44186], 60)
    jc = B.override(jcfg, jcfg["judge"]["variants"]["L1"])
    out["judge_L1_rules"], w = _rule_scene(jc, [44187, 44188], 500)
    out["judge_L1_deaths"] = w.st["deaths"].sum(0).tolist()
    out["judge_hash"] = _hashes(jcfg)
    # v3_r9_fauna.yaml (동물 세계 6 종)
    out["fauna_random"] = _random_scene(fcfg, [44189, 44190], 120, 44191)
    out["fauna_rules"], w = _rule_scene(fcfg, [44192, 44193], 300)
    out["fauna_rules_deaths"] = w.st["deaths"].sum(0).tolist()
    out["fauna_rules_gore"] = int(w.st["gore"].sum())
    out["fauna_rules_stoch"], w = _rule_scene(fcfg, [44194], 200, stochastic=True)
    out["fauna_vec_leopard"] = _vec_scene(fcfg, "leopard", range(44180, 44199), 30, 44199)
    out["fauna_hash"] = _hashes(fcfg)
    return out


def test_m1_old_configs_bit_identical():
    """M-1: 옛 설정 셋의 궤적·해시가 손대기 전 HEAD 와 비트까지 같다 (motion 블록이 없으면 새 줄을 안 탄다)."""
    got = old_golden(B.load_r9_config(CFG), B.load_r9_config(JCFG), B.load_r9_config(FCFG))
    assert GOLDEN, "기준값 없음"
    for k, v in GOLDEN.items():
        assert got[k] == v, f"{k}: {got[k]} != {v}"


# =========================================================================== 고친 뒤 (M-2 ~ M-14, M2 전용 M-7·M-8·M-15·M-16 은 M2 결정 뒤)

import copy  # noqa: E402
import math  # noqa: E402

from env_v2.r9_world import EPS, _len2, _shelter_edge  # noqa: E402

MCFG = ROOT / "configs" / "v3_r9_fauna_motion.yaml"
JMCFG = ROOT / "configs" / "v3_r9_judge_motion.yaml"
DE, WO, BO, BU, LE, FX = range(6)
NONE6 = dict(deer=0, wolf=0, boar=0, buffalo=0, leopard=0, fox=0)
# 부록 A (사용자 결정 2026-11-13: 늑대 옆 가속 7.0) — 설정 파일이 이 값을 그대로 싣는지 본다
APPENDIX_A = {"deer": (130, 9.0), "wolf": (140, 7.0), "boar": (125, 7.0), "buffalo": (90, 5.0), "leopard": (135, 11.0),
              "fox": (185, 10.0)}
# 설계 3-2 참고 리터럴 (이 PC 파이썬 math 로 셈한 cos Δb · sin Δb)
TURN_CS = {"deer": (0.9545876322477319, 0.29793028103848196), "wolf": (0.9473966425143293, 0.3200618717569716),
           "boar": (0.9579895123154889, 0.28680323271109026), "buffalo": (0.9781476007338057, 0.20791169081775934),
           "leopard": (0.9510565162951535, 0.3090169943749474), "fox": (0.9087511289735642, 0.4173384544818179)}


@pytest.fixture(scope="module")
def fcfg():
    return B.load_r9_config(FCFG)


@pytest.fixture(scope="module")
def mcfg():
    return B.load_r9_config(MCFG)


@pytest.fixture(scope="module")
def jmcfg():
    return B.load_r9_config(JMCFG)


def same_bits(a, b) -> bool:
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def raw(cfg: dict) -> dict:
    return copy.deepcopy({k: v for k, v in cfg.items() if k != "_path"})


class Probe(R9World):
    """Records each `_move` (before / after) for the per-step body checks."""

    def _move(self):
        pre = dict(vel=self.vel.copy(), head=self.head.copy(), alive=self.alive.copy(), act=self.act.copy(),
                   dir_cmd=self.dir_cmd.copy(), lock=self.stam_lock.copy(), E=self.E.copy(), hp=self.hp.copy(),
                   spd=self.spd_scale.copy())
        super()._move()
        self.trace.append(dict(pre=pre, vel=self.vel.copy(), head=self.head.copy(), vfree=self._vel_free.copy(),
                               wall=self._wall.copy(), tspeed=self._tspeed.copy(), contact=self._contact.copy(),
                               knocked=self._knocked.copy(), pushed=self._pushed.copy()))


def probe(cfg, seeds, **kw) -> Probe:
    w = Probe.__new__(Probe)
    w.trace = []
    R9World.__init__(w, cfg, list(seeds), **kw)
    return w


def v0_standing(v):
    """The design's standing rule: |v|² ≤ EPS² → 0 (3-1)."""
    return np.where((_len2(v) > EPS * EPS)[..., None], v, 0.0)


def theta_cos(w, v0):
    """cos θ per slot from the body table — θ = min(Δb, asin(a_lat/|v0|)), written apart from the world's `_turn_limit`."""
    b = w.body
    sp = w.slot_sp.astype(np.int64)
    s0 = np.sqrt(_len2(v0_standing(v0)))
    cb, sb_, au = b.turn_c[sp], b.turn_s[sp], b.lat_u[sp]
    fast = s0 * sb_ > au
    r = au / np.where(fast, s0, 1.0)
    return np.where(fast, np.sqrt(np.maximum(1.0 - r * r, 0.0)), cb), fast


def rules(w, cfg, stochastic=False, only=None):
    for k in range(w.K):
        for s in range(w.NS):
            n = V.RULE_OF[s] if only is None or s not in only else only[s]
            w.set_controller(k, s, BR.Controller(BR.make_rule(n, cfg, s), stochastic, n))


def mixed_step(w, rng, i):
    """Decision i: rule brains on even i, random actions on odd i; every third odd decision is all RUN (fast turns)."""
    if i % 2 == 0:
        a = w.decide()
    elif i % 6 == 1:
        a = rng.integers(B.RUN_FIRST, B.RUN_LAST + 1, (w.K, w.S))
    else:
        a = rng.integers(0, B.N_ACTIONS, (w.K, w.S))
    return w.step(a)


def slot(w, s, i=0) -> int:
    return int(w.sp_lo[s]) + i


def fworld(cfg, counts: dict, shelters=((57.0, 57.0, 2.0),), seeds=(44190,)):
    c = dict(NONE6)
    c.update(counts)
    names = B.species_of(cfg)
    p = {"counts": {n: [int(c[n]), int(c[n])] for n in names}, "world": {"shelters": {"fixed": [list(s) for s in shelters]}}}
    return R9World(B.override(cfg, p), list(seeds))


def place(w, k, s, pos, head=(1.0, 0.0), vel=(0.0, 0.0), E=0.6):
    h = np.asarray(head, dtype=np.float64)
    w.pos[k, s] = pos
    w.head[k, s] = h / np.sqrt((h * h).sum())
    w.vel[k, s] = vel
    w.disp[k, s] = 0.0
    w.hp[k, s] = 1.0
    w.stam[k, s] = 1.0
    w.stam_lock[k, s] = False
    w.g_size[k, s] = 1.0
    w.g_speed[k, s] = 1.0
    w.E[k, s] = E
    w.R[k, s] = 0.5
    w.bite_cd[k, s] = 0
    w.knock_left[k, s] = 0
    w.act[k, s] = B.WATCH
    w.born[k, s] = float(w.t[k]) - 2.0 * float(w.sb["maturity"][k, s])
    w.next_birth[k, s] = 1e9


def settle(w):
    w.mem[:] = 0.0
    w.grass[:] = 0.0
    w.root[:] = 0.0
    w._derive()
    w._jsh1, w._edge1 = _shelter_edge(w.pos, w.cov_c, w.cov_r, w.cov_ok)
    w.refresh()


# --------------------------------------------------------------------------- M-2

def test_m2_no_trig_inside_a_step(mcfg, jmcfg, monkeypatch):
    """M-2: 스텝 안 삼각함수 없음 (test_06 꼴) — cos/sin Δb 는 `load_body` 에서만 (세계를 만든 뒤에 막는다)."""
    w = R9World(mcfg, [44180, 44181])
    rules(w, mcfg)
    jc = B.override(jmcfg, jmcfg["judge"]["variants"]["L1"])
    j = R9World(jc, [44182])
    rules(j, jc)

    def boom(*a, **k):
        raise AssertionError("trig call inside a step (3-9, TURN_EFFORT 3-1)")
    for mod, names in ((np, ("sin", "cos", "tan", "arcsin", "arccos", "arctan", "arctan2", "radians", "degrees", "deg2rad",
                             "rad2deg", "sinh", "cosh", "tanh")),
                       (math, ("sin", "cos", "tan", "asin", "acos", "atan", "atan2", "radians", "degrees"))):
        for n in names:
            monkeypatch.setattr(mod, n, boom)
    rng = np.random.default_rng(44183)
    for i in range(40):
        mixed_step(w, rng, i)
    for i in range(20):
        mixed_step(j, rng, i)
    w.reinit(1, 44184)
    w.E[:, :5] = -1.0
    w.R[:, :5] = 0.0
    w.step(rng.integers(0, B.N_ACTIONS, (w.K, w.S)))         # respawn path too
    w.decide()
    assert int(w.st["turn_clip"].sum()) > 0 and int(j.st["turn_clip"].sum()) > 0


# --------------------------------------------------------------------------- M-3 · M-4 · M-5

def _check_trace(w, cfg, out):
    b = w.body
    sp_of = w.slot_sp.astype(np.int64)
    acc = b.accel[sp_of]
    for tr in w.trace:
        pre = tr["pre"]
        al = pre["alive"]
        nowall = ~tr["wall"].any(-1)
        h0, h1 = pre["head"], tr["head"]
        v0, v1 = pre["vel"], tr["vel"]
        cl, fast = theta_cos(w, v0)
        hc = (h0 * h1).sum(-1)
        m = al & nowall
        # M-3 한 스텝 머리 회전 ≤ θ (벽에 닿지 않은 산 몸 모두)
        assert (hc[m] >= cl[m] - 1e-12).all(), float((hc[m] - cl[m]).min())
        # M-4 뒤집힘 없음: 움직이던 몸은 v1·h0 ≥ 0, 아직 움직이면 > 0
        mv = m & (_len2(v0) > EPS * EPS)
        dot = (v1 * h0).sum(-1)
        assert (dot[mv] >= 0.0).all()
        assert (dot[mv & (_len2(v1) > EPS * EPS)] > 0.0).all()
        # M-5 |Δv| ≤ accel (자르기는 서 있음 규칙을 거친 v0 기준), 속력 집합·벽 미끄럼·접촉 (test_19 꼴)
        dv = np.sqrt(_len2(tr["vfree"] - v0_standing(v0)))
        assert (dv[al] <= np.broadcast_to(acc, dv.shape)[al] + 1e-12).all()
        mlt = pre["spd"] * (0.5 + 0.5 * pre["hp"]) * np.where(pre["E"] < b.weak_e[sp_of], b.weak_speed[sp_of], 1.0)
        walk = b.walk_speed[sp_of] * mlt
        run = b.run_speed[sp_of] * w._rmult * mlt
        ts = tr["tspeed"]
        ok = (ts == 0.0) | np.isclose(ts, walk, rtol=1e-12, atol=0) | np.isclose(ts, run, rtol=1e-12, atol=0)
        assert ok[al].all()
        vf = np.sqrt(_len2(tr["vfree"]))
        assert (vf[al] <= np.maximum(np.sqrt(_len2(v0)), ts)[al] + 1e-12).all()
        wl = tr["wall"]
        assert np.array_equal(np.where(wl, 0.0, v1 - tr["vfree"])[al], np.zeros_like(v1)[al])
        cn = np.sqrt(_len2(tr["contact"]))
        assert (cn[al & ~tr["knocked"] & ~tr["pushed"]] <= 1e-12).all()
        assert (cn[al & tr["knocked"] & ~tr["pushed"]] <= cfg["body_common"]["counter"]["knock_step"] + 1e-12).all()
        # 셈: 자른 스텝 (빠름 → 미끄럼 한계 / 느림 → 몸 한계), 벽 스텝
        cmd = al & (B.action_dir_index(pre["act"]) >= 0)
        cut = cmd & ((pre["dir_cmd"] * h0).sum(-1) < cl)
        out["cut_fast"] += int((cut & fast).sum())
        out["cut_slow"] += int((cut & ~fast).sum())
        out["wall"] += int((al & ~nowall).sum())
        out["steps"] += int(m.sum())
    w.trace.clear()


@pytest.mark.parametrize("which", ["fauna_motion", "judge_motion_L1"])
def test_m3_m4_m5_turn_limit_no_flip_accel(mcfg, jmcfg, which):
    """M-3 머리 회전 ≤ θ (h0·h1 ≥ cl − 1e-12, 벽 제외) · M-4 뒤집힘 없음 · M-5 |Δv| ≤ accel 과 test_19 단언이 motion 설정에서도 성립."""
    if which == "fauna_motion":
        cfg, seeds, n = mcfg, [44185, 44186, 44187], 240
    else:
        cfg, seeds, n = B.override(jmcfg, jmcfg["judge"]["variants"]["L1"]), [44188], 300
    w = probe(cfg, seeds, record=True)
    rules(w, cfg)
    rng = np.random.default_rng(44189)
    out = dict(cut_fast=0, cut_slow=0, wall=0, steps=0)
    for i in range(n):
        mixed_step(w, rng, i)
        _check_trace(w, cfg, out)
    assert out["cut_fast"] > 0 and out["cut_slow"] > 0, out          # both limits really cut commands
    assert out["wall"] > 0, out                                       # the wall exception was met (and left out)
    assert int(w.st["turn_over"].sum()) == 0
    assert int(w.st["turn_clip"].sum()) == out["cut_fast"] + out["cut_slow"]
    assert (w.st["wall_hit_steps"] <= w.st["move_steps"]).all() and int(w.st["wall_hit_steps"].sum()) > 0


def test_m4_old_body_does_flip(fcfg):
    """M-4 의 대조: 옛 몸(같은 장면·같은 두뇌)에서는 한 스텝 90° 넘게 도는 일과 속도가 0 을 지나 뒤집히는 일이 있다."""
    w = probe(fcfg, [44185, 44186, 44187], record=True)
    rules(w, fcfg)
    rng = np.random.default_rng(44189)
    flips = big = 0
    for i in range(120):
        mixed_step(w, rng, i)
        for tr in w.trace:
            al = tr["pre"]["alive"] & ~tr["wall"].any(-1)
            mv = al & (_len2(tr["pre"]["vel"]) > EPS * EPS)
            flips += int((mv & ((tr["vel"] * tr["pre"]["head"]).sum(-1) < 0.0)).sum())
            big += int((al & ((tr["pre"]["head"] * tr["head"]).sum(-1) < 0.0)).sum())
        w.trace.clear()
    assert flips > 0 and big > 0
    assert "turn_over" not in w.st and "move_steps" not in w.st     # no motion block → the old stats key set


# --------------------------------------------------------------------------- M-6

def _tie_scene(mcfg, speed):
    """Two deer far apart, head +x, standing (speed 0) or walking straight; both get the exactly-behind command WALK_180."""
    w = fworld(mcfg, dict(deer=2), seeds=(44191,))
    a, b = slot(w, DE), slot(w, DE, 1)
    place(w, 0, a, (20.0, 30.0), (1.0, 0.0), (speed, 0.0))
    place(w, 0, b, (40.0, 30.0), (1.0, 0.0), (speed, 0.0))
    settle(w)
    act = np.full((w.K, w.S), B.WATCH, dtype=np.int64)
    act[0, [a, b]] = B.WALK_FIRST + 4
    heads = []
    for _ in range(2):                                             # two decisions = four steps
        w.step(act)
        heads.append(w.head[0, [a, b]].copy())
    return w, (a, b), heads


@pytest.mark.parametrize("speed", [0.0, 0.24])
def test_m6_exactly_behind_turns_by_uid_parity(mcfg, speed):
    """M-6: 곧게 가던(또는 서 있던) 몸에 정확히 뒤(DIR8[4]) 명령 → uid 짝수는 왼쪽(반시계), 홀수는 오른쪽. 두 번 돌려 같음."""
    w, (a, b), heads = _tie_scene(mcfg, speed)
    ua, ub = int(w.uid[0, a]), int(w.uid[0, b])
    assert (ua & 1) != (ub & 1)                                    # one even, one odd body
    side = {a: 1.0 if (ua & 1) == 0 else -1.0, b: 1.0 if (ub & 1) == 0 else -1.0}
    for h in heads:
        for i, s in enumerate((a, b)):
            assert np.sign(h[i][1]) == side[s], (s, h[i])            # the same side every step (cross ≠ 0 after the first)
    if speed == 0.0:                                               # standing: the first step turns exactly Δb (body limit)
        w2 = fworld(mcfg, dict(deer=2), seeds=(44191,))
        for s in (a, b):
            place(w2, 0, s, (20.0 if s == a else 40.0, 30.0), (1.0, 0.0))
        settle(w2)
        w2.act[0, [a, b]] = B.WALK_FIRST + 4
        w2.dir_cmd[0, [a, b]] = B.rotate(w2.head[0, [a, b]], B.DIR8[4])
        w2._phys()
        c, s_ = TURN_CS["deer"]
        for s in (a, b):
            assert np.allclose(w2.head[0, s], (c, side[s] * s_), rtol=0, atol=1e-12), w2.head[0, s]
    w3, _, heads3 = _tie_scene(mcfg, speed)
    assert all(same_bits(x, y) for x, y in zip(heads, heads3))


# --------------------------------------------------------------------------- M-9 · effort 거부

def test_m9_config_checks(fcfg, mcfg):
    """M-9: 깃발 bool(문자열 거부), 켜진 규칙 키 필수(모든 종)·꺼진 규칙 키 금지, 블록 없으면 키 금지, 6-1 범위 밖은 ValueError."""
    base = raw(mcfg)
    B.check_r9_config(copy.deepcopy(base))                         # the round-1 config itself passes

    def bad(mut, match=None):
        c = copy.deepcopy(base)
        mut(c)
        with pytest.raises(ValueError, match=match):
            B.check_r9_config(c)

    def mo(c):
        return c["body_common"]["motion"]

    bad(lambda c: mo(c).__setitem__("turn", "true"), "true\\|false")
    bad(lambda c: mo(c).__setitem__("effort", "false"), "true\\|false")
    bad(lambda c: mo(c).__setitem__("turn", 1), "true\\|false")
    bad(lambda c: mo(c).pop("effort"), "misses")
    bad(lambda c: mo(c).pop("turn"), "misses")
    bad(lambda c: mo(c).__setitem__("turns", True), "unknown")
    bad(lambda c: c["body_common"].__setitem__("motion", [True, False]), "mapping")
    bad(lambda c: c["species"]["fox"].pop("turn_dps"), "misses motion keys")
    bad(lambda c: c["species"]["buffalo"].pop("lat_accel_mps2"), "misses motion keys")
    bad(lambda c: mo(c).__setitem__("fit", 0.67), "M2 keys")              # effort false → M2 keys absent
    bad(lambda c: c["species"]["deer"].__setitem__("walk_w_kg", 12.307), "M2 keys")
    bad(lambda c: c["species"]["deer"].__setitem__("turn_dps", 340), "\\(0, 45\\)")   # 340 × 2/15 = 45.3°
    bad(lambda c: c["species"]["deer"].__setitem__("turn_dps", 0), "\\(0, 45\\)")
    bad(lambda c: c["species"]["deer"].__setitem__("turn_dps", -10), "\\(0, 45\\)")
    bad(lambda c: c["species"]["deer"].__setitem__("turn_dps", "130"), "numbers")
    bad(lambda c: c["species"]["wolf"].__setitem__("lat_accel_mps2", 0.0), "> 0")
    bad(lambda c: c["species"]["wolf"].__setitem__("lat_accel_mps2", True), "numbers")
    bad(lambda c: mo(c).__setitem__("turn", False), "turn keys must be absent")
    # no block: no motion key in any species
    f = raw(fcfg)
    f["species"]["leopard"]["turn_dps"] = 135
    with pytest.raises(ValueError, match="body_common.motion is missing"):
        B.check_r9_config(f)
    # turn false · effort false without species keys is accepted (M-13 배관)
    c = copy.deepcopy(base)
    mo(c)["turn"] = False
    for n in B.species_of(c):
        for k in B.MOTION_TURN_SPECIES_KEYS:
            c["species"][n].pop(k)
    B.check_r9_config(c)
    # the inherited config carries the appendix-A values (사용자 결정: 늑대 7.0)
    for n, (dps, lat) in APPENDIX_A.items():
        assert float(mcfg["species"][n]["turn_dps"]) == dps and float(mcfg["species"][n]["lat_accel_mps2"]) == lat, n
    assert mcfg["body_common"]["motion"] == {"turn": True, "effort": False}


def test_m9_effort_true_is_refused(mcfg):
    """사용자 결정(2026-11-13): 첫 바퀴는 M1 만 — effort: true 는 M2 가 아직 없다는 ValueError (M2 키가 있어도 없어도)."""
    for extra in ({}, {"eta_up": 0.25, "eta_down": 1.2, "fit": 0.67, "kappa": 0.5}):
        c = raw(mcfg)
        c["body_common"]["motion"]["effort"] = True
        c["body_common"]["motion"].update(extra)
        with pytest.raises(ValueError, match="M2"):
            B.check_r9_config(c)
    with pytest.raises(ValueError, match="M2"):
        B.override(mcfg, {"body_common": {"motion": {"effort": True}}})


# --------------------------------------------------------------------------- M-10

def test_m10_hashes(fcfg, mcfg, jmcfg):
    """M-10: motion 설정은 몸 해시·몸 표 해시가 모든 종에서 바뀌고 입출력 해시는 같다. 옛 설정 해시는 M-1 기준값 그대로."""
    names = B.species_of(mcfg)
    assert names == B.species_of(fcfg) and len(names) == 6
    for n in names:
        assert B.body_hash(mcfg, n) != B.body_hash(fcfg, n), n
    assert B.body_table_hash(mcfg) != B.body_table_hash(fcfg)
    jcfg = B.load_r9_config(JCFG)
    for n in B.species_of(jmcfg):
        assert B.body_hash(jmcfg, n) != B.body_hash(jcfg, n), n
    assert B.hash_hex(B.io_hash()) == GOLDEN["sp_hash"]["io_hash"]
    for c, key in ((B.load_r9_config(CFG), "sp_hash"), (jcfg, "judge_hash"), (fcfg, "fauna_hash")):
        assert _hashes(c) == GOLDEN[key], key
    # the body table: turn fields only with the block, values = the design literals (3-2)
    b = B.load_body(mcfg)
    assert b.motion and b.motion_turn and not b.motion_effort
    for i, n in enumerate(b.names):
        assert (float(b.turn_c[i]), float(b.turn_s[i])) == TURN_CS[n], n
        assert float(b.lat_u[i]) == APPENDIX_A[n][1] / 112.5
    sb = B.expand_body(b, np.arange(6))
    assert all(f in sb for f in B.SLOT_MOTION_FIELDS)
    sb0 = B.expand_body(B.load_body(fcfg), np.arange(6))
    assert not any(f in sb0 for f in B.SLOT_MOTION_FIELDS)


# --------------------------------------------------------------------------- M-11

def _random_brain(tmp_path, cfg, sp, name):
    rng = np.random.default_rng(44190 + B.SPECIES_INDEX[sp])
    w = {k: (0.1 * rng.standard_normal(BR.NPZ_SHAPES[k])).astype(np.float32) for k in BR.NPZ_WEIGHT_KEYS}
    p = tmp_path / name
    BR.save_brain(p, w, BR.brain_meta(cfg, sp, "T", 0, 0, None))
    return p, w


def test_m11_rebody_and_rule_brains(tmp_path, fcfg, mcfg):
    """M-11: 동물 세계 npz 는 motion 세계에서 거부되고 rebody 뒤에 실린다(F-9 꼴, 메타 init_from). 규칙 두뇌 모두(ALL_RULE_NAMES)가
    motion 세계에서 돌고, 행동 가지(먹기·걷기·뛰기·숨기·살피기)가 모두 한 번 이상 나오며, 걷기·뛰기는 회전 한계를 지난다."""
    brains = {}
    for sp in ("deer", "wolf", "leopard"):
        src, wts = _random_brain(tmp_path, fcfg, sp, f"{sp}_fauna.npz")
        BR.load_brain(src, fcfg, sp)
        with pytest.raises(BR.BrainContractError):
            BR.load_brain(src, mcfg, sp)                                     # another body: refused without rebody
        meta = BR.rebody_brain(src, mcfg, sp, tmp_path / f"{sp}_motion.npz")
        assert meta["init_from"]["body_hash"] == B.hash_hex(B.body_hash(fcfg, sp))
        assert meta["body_hash"] == B.hash_hex(B.body_hash(mcfg, sp)) and meta["init_from"]["species"] == sp
        b = BR.load_brain(tmp_path / f"{sp}_motion.npz", mcfg, sp)
        assert all(same_bits(b.weights[k], wts[k]) for k in BR.NPZ_WEIGHT_KEYS)
        brains[B.SPECIES_INDEX[sp]] = b
    # the rebodied brains drive their species in the motion world
    w = R9World(mcfg, [44192, 44193])
    rules(w, mcfg)
    for k in range(w.K):
        for s, br in brains.items():
            w.set_controller(k, s, BR.Controller(br, k == 1, "rebody"))
    for _ in range(40):
        w.step(w.decide())
    assert int(w.st["turn_over"].sum()) == 0 and int(w.st["turn_clip"].sum()) > 0
    # every rule brain runs in the motion world (every species present)
    groups = {}
    counts = np.array([[24, 3, 8, 4, 2, 3]], dtype=np.int64)
    for name in BR.ALL_RULE_NAMES:
        own = BR.RULE_SPECIES[name]
        for s in ((DE, BO) if own is None else (own,)):
            w = R9World(mcfg, [44194], counts=counts)
            rules(w, mcfg, only={s: name})
            seen = set()
            for _ in range(150):
                a = w.decide()
                m = w.alive & (w.sp == s)
                seen |= {B.ACTION_NAMES[int(x)].split("_")[0] for x in a[m]}
                w.step(a)
            assert int(w.st["turn_over"].sum()) == 0, name
            if seen & {"WALK", "RUN"}:
                assert int(w.st["turn_clip"][:, s].sum()) > 0, name      # its moves went through the turn limit
            groups[(name, s)] = seen
    allg = set().union(*groups.values())
    assert allg >= {"EAT", "WALK", "RUN", "SHELTER", "WATCH"}, groups
    assert all(groups[(V.RULE_OF[s], s)] & {"WALK", "RUN"} for s in range(6)), groups   # the six species rules move


# --------------------------------------------------------------------------- M-12

def test_m12_gathered_equals_full_table(mcfg):
    """M-12: 두 길 같음(물기 모은 길 = 전체 표 길, 시험 22b 꼴)을 motion 설정으로 — 상태·사건 목록 비트 같음, 물기가 실제로 일어남."""
    seeds = [44195, 44196]
    ws = []
    for full in (False, True):
        w = R9World(mcfg, seeds, record=True, pairs_full=full)
        rules(w, mcfg)
        for s in (WO, LE, FX):                                 # hungry biters
            m = slice(slot(w, s), int(w.sp_hi[s]))
            w.E[:, m] = np.where(w.alive[:, m], 0.5, w.E[:, m])
        w.refresh()
        ws.append(w)
    g, f = ws
    for _ in range(250):
        ag, af_ = g.decide(), f.decide()
        assert same_bits(ag, af_)
        og, rg, _, _ = g.step(ag)
        of, rf, _, _ = f.step(af_)
        assert same_bits(og, of) and same_bits(rg, rf)
    g.flush_hunts()
    f.flush_hunts()
    for nme in ("pos", "vel", "head", "hp", "E", "R", "alive", "uid", "bite_cd", "knock_left"):
        assert same_bits(getattr(g, nme), getattr(f, nme)), nme
    for ev in ("bites", "deaths", "hunts", "respawns", "births", "gores"):
        assert g.events[ev] == f.events[ev], ev
    for k, v in g.stats_snapshot().items():
        assert same_bits(v, f.st[k]), k
    assert len(g.events["bites"]) >= 3 and int(g.st["turn_clip"].sum()) > 0


# --------------------------------------------------------------------------- M-13

def test_m13_block_with_both_rules_off_is_bit_identical(fcfg):
    """M-13: 블록은 있고 turn·effort 모두 false → 궤적이 블록 없는 세계와 비트 같고 몸 해시만 다르다 (배관 확인)."""
    off = B.override(fcfg, {"body_common": {"motion": {"turn": False, "effort": False}}})
    assert B.load_body(off).motion and not B.load_body(off).motion_turn
    for n in B.species_of(fcfg):
        assert B.body_hash(off, n) != B.body_hash(fcfg, n)
    res = []
    for c in (fcfg, off):
        w = R9World(c, [44197, 44198], record=True)
        rules(w, c)
        rng = np.random.default_rng(44199)
        h = hashlib.sha256()
        for i in range(200):
            a = w.decide() if i % 2 == 0 else rng.integers(0, B.N_ACTIONS, (w.K, w.S))
            o, r, d, info = w.step(a)
            _upd(h, a, o, r, d, info["dead_cause"], info["births"], info["respawned"])
        for n in STATE:
            _upd(h, getattr(w, n))
        res.append((h.hexdigest(), w))
    assert res[0][0] == res[1][0]
    a, b = res[0][1].st, res[1][1].st
    assert set(b) - set(a) == {"move_steps", "wall_hit_steps", "turn_clip", "turn_over"}
    for k in a:
        assert same_bits(a[k], b[k]), k
    assert int(b["turn_clip"].sum()) == 0 and int(b["move_steps"].sum()) > 0


# --------------------------------------------------------------------------- M-14

@pytest.mark.parametrize("act0,vel", [(B.WALK_FIRST, (0.0, 0.0)), (B.RUN_FIRST + 3, (0.0, 0.0)), (B.RUN_FIRST, (0.3, 0.0))])
def test_m14_zero_direction_is_not_clipped(mcfg, act0, vel):
    """M-14: WALK/RUN 인데 dir_cmd 가 0 이면 자르기가 걸리지 않는다 — 서 있던 몸은 움직이지 않고, 움직이던 몸은 곧게 줄어든다
    (|d|² > EPS² 조건이 없으면 자르기가 '없던 방향'을 만들어 몸을 움직인다). 대조: 같은 몸에 진짜 방향이면 잘린다."""
    for d, want in (((0.0, 0.0), 0), ((0.0, 1.0), 1)):
        w = fworld(mcfg, dict(deer=1), seeds=(44199,))
        s = slot(w, DE)
        place(w, 0, s, (30.0, 30.0), (1.0, 0.0), vel)
        settle(w)
        w.act[0, s] = act0
        w.dir_cmd[0, s] = d
        p0, h0 = w.pos[0, s].copy(), w.head[0, s].copy()
        w._phys()
        assert int(w.st["turn_clip"].sum()) == want, d
        if want:
            continue
        assert same_bits(w.head[0, s], h0)
        if vel == (0.0, 0.0):
            assert same_bits(w.pos[0, s], p0) and float(_len2(w.vel[0, s])) == 0.0
        else:
            assert w.vel[0, s][1] == 0.0 and 0.0 <= w.vel[0, s][0] < vel[0]       # slows straight, no new direction
