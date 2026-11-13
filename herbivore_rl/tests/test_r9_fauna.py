"""R9 동물 세계 1 단계 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md 7-1 F-1~F-13).

F-1 은 손대기 전 HEAD(76950dfb 의 R9 파이썬) 에서 잰 S′ 세 종 세계 기준값이다(설계 9-1 B5). 옛 설정(`v3_r9.yaml`·`v3_r9_judge.yaml`)
으로 아홉 장면의 sha256 과 입출력·몸·몸 표 해시가 모두 같아야 한다 — 새 종·새 몸 규칙은 `body_common.fauna` 가 있을 때만 켜진다.
시드: 스모크·속도 범위 44180~44199 만 쓴다(설계 7-3).
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
from env_v2.r9_world import R9World

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")

# 손대기 전 HEAD 기준값 (SP/species/bench/golden_sprime_baseline.py, 2026-11-13 다시 돌려 설계 9-3 값과 같음을 확인)
GOLDEN = {
    "train_random19": "226d9fb484bccc24db18ed3bad5cefcb6511ddef0fca652f54dbfb5e7bc41e34",
    "train_rules400": "8ce1907953265e59ae599850e00e3c84317ee55eb89876c959c69932348c6183",
    "train_rules400_bites": [[6, 0, 0], [0, 0, 0], [2, 4, 7]],
    "train_rules400_deaths": [[0, 6, 0, 4], [0, 0, 0, 0], [0, 2, 0, 0]],
    "judge_L1_rules700": "30ae6875e878a11b17faf1c5080188380d1cb48d8d542cdc45cf9de50d1437a4",
    "judge_L1_births": [5, 2, 0],
    "vecenv_deer": "5cebf5dcbaa6971a055e5b5d163de0ab72ce48edd740ee90d9d6c1f451e18fcf",
    "vecenv_wolf": "65c1f860dc66504d2ae68f1758f7728624aa92980e65aa84bc69e6eb6179016e",
    "vecenv_boar": "f7793af1e66cbbf76d0c3f1c3a1c28f3cdff97e175e3ed29b8d3afd13c02636a",
    "io_hash": "0x0fa76480fe9465e0",
    "body_hash": {"deer": "0x0d04b5447e42a2c0", "wolf": "0x6ce9605c7a90224a", "boar": "0x8af5915146034953"},
    "body_table_hash": "0xf6e81fcbe4e7c24d",
}

STATE = ("pos", "head", "vel", "E", "R", "stam", "hp", "alive", "uid", "kin_id", "next_birth", "mating", "bite_cd",
         "carc_ok", "carc_meat", "grass", "root", "mem")
RULE3 = {0: "RULE_DEER", 1: "RULE_WOLF", 2: "RULE_BOAR"}


def _upd(h, *xs):
    for x in xs:
        h.update(np.ascontiguousarray(np.asarray(x)).tobytes())


def _world_hash(w, h):
    for n in STATE:
        _upd(h, getattr(w, n))


def sprime_golden(cfg: dict, jcfg: dict) -> dict:
    """The nine S′ scenes of the baseline script (same order, same seeds, same hashing)."""
    out = {}
    w = R9World(cfg, [44180, 44181, 44182])
    rng = np.random.default_rng(44183)
    h = hashlib.sha256()
    _upd(h, w.obs())
    for _ in range(150):
        o, r, d, info = w.step(rng.integers(0, B.N_ACTIONS, (w.K, w.S)))
        _upd(h, o, r, d, info["dead_cause"], info["births"], info["respawned"])
    _world_hash(w, h)
    for k, v in sorted(w.stats_snapshot().items()):
        _upd(h, v)
    out["train_random19"] = h.hexdigest()

    w = R9World(cfg, [44184, 44185])
    for k in range(w.K):
        for s in range(B.N_SPECIES):
            w.set_controller(k, s, BR.Controller(BR.make_rule(RULE3[s], cfg, s), True, "rule"))
    h = hashlib.sha256()
    _upd(h, w.obs())
    for _ in range(400):
        a = w.decide()
        o, r, d, info = w.step(a)
        _upd(h, a, o, r, d, info["dead_cause"], info["killer"], info["births"])
    _world_hash(w, h)
    for k, v in sorted(w.stats_snapshot().items()):
        _upd(h, v)
    out["train_rules400"] = h.hexdigest()
    out["train_rules400_bites"] = w.st["bites"].sum(0).tolist()
    out["train_rules400_deaths"] = w.st["deaths"].sum(0).tolist()

    jc = B.override(jcfg, jcfg["judge"]["variants"]["L1"])
    w = R9World(jc, [44186, 44187])
    for k in range(w.K):
        for s in range(B.N_SPECIES):
            w.set_controller(k, s, BR.Controller(BR.make_rule(RULE3[s], jc, s), False, "rule"))
    h = hashlib.sha256()
    _upd(h, w.obs())
    for _ in range(700):
        a = w.decide()
        o, r, d, info = w.step(a)
        _upd(h, a, o, r, d, info["dead_cause"], info["newborn"])
    _world_hash(w, h)
    ls = L.life_stats(w.life)
    for k in ("opportunities", "paired", "births", "blocked", "failed", "cancelled"):
        _upd(h, ls[k])
    out["judge_L1_rules700"] = h.hexdigest()
    out["judge_L1_births"] = ls["births"].sum((0, 1)).tolist()

    from env_v2.r9_vec_env import R9VecEnv
    for sp in B.SPECIES:
        v = R9VecEnv(cfg, sp, model_seed=0, round_=0, seeds=range(44188, 44199), num_worlds=4, reset_steps=20, shards=1,
                     online_stats=False)
        h = hashlib.sha256()
        _upd(h, v.reset())
        r_ = np.random.default_rng(44199)
        for _ in range(35):
            v.step_async(r_.integers(0, B.N_ACTIONS, v.num_envs))
            o, r, d, infos = v.step_wait()
            _upd(h, o, r, d)
        h.update(json.dumps(v.history, sort_keys=True, default=str).encode())
        h.update(json.dumps(v.seed_history).encode())
        v.close()
        out[f"vecenv_{sp}"] = h.hexdigest()

    out["io_hash"] = B.hash_hex(B.io_hash())
    out["body_hash"] = {n: B.hash_hex(B.body_hash(cfg, n)) for n in B.SPECIES}
    out["body_table_hash"] = B.hash_hex(B.body_table_hash(cfg))
    return out


def test_f1_sprime_bit_identical():
    """F-1: 옛 설정의 S′ 세 종 세계가 손대기 전 HEAD 와 비트까지 같다."""
    got = sprime_golden(B.load_r9_config(CFG), B.load_r9_config(JCFG))
    for k, v in GOLDEN.items():
        assert got[k] == v, f"{k}: {got[k]} != {v}"


# =========================================================================== 동물 세계 (F-2 ~ F-13)

import copy  # noqa: E402
import dataclasses  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402

from env_v2 import r9_vec_env as V  # noqa: E402
from env_v2.r9_vec_env import R9VecEnv  # noqa: E402
from env_v2.r9_world import CAUSE_BITE, _shelter_edge  # noqa: E402

FCFG = ROOT / "configs" / "v3_r9_fauna.yaml"
SRC = ROOT / "ckpt" / "r9_fauna" / "start" / "src"
DE, WO, BO, BU, LE, FX = range(6)
NONE6 = dict(deer=0, wolf=0, boar=0, buffalo=0, leopard=0, fox=0)
CORNER = [[57.0, 57.0, 2.0]]
DEMO_ZIP = {"wolf": "wolf_r0_7845120", "boar": "boar_r0_10027008"}


@pytest.fixture(scope="module")
def fcfg():
    return B.load_r9_config(FCFG)


def same_bits(a, b) -> bool:
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


class NoRespawn(R9World):
    """Scene world: no train-world respawn (a dead slot stays empty)."""

    def _respawn(self, dead):
        return np.zeros((self.K, self.S), dtype=bool)


def fworld(cfg, counts: dict, shelters=None, seeds=(44190,), record=False, cls=R9World, patch=None):
    c = dict(NONE6)
    c.update(counts)
    p = {"counts": {n: [int(v), int(v)] for n, v in c.items()}, "world": {"shelters": {"fixed": shelters or CORNER}}}
    if patch:
        p = B._deep_merge(p, patch)
    return cls(B.override(cfg, p), list(seeds), record=record)


def slot(w, s, i=0) -> int:
    return int(w.sp_lo[s]) + i


def place(w, k, s, pos, head=(1.0, 0.0), af=1.0, g=1.0, E=0.5):
    h = np.asarray(head, dtype=np.float64)
    w.pos[k, s] = pos
    w.head[k, s] = h / np.sqrt((h * h).sum())
    w.vel[k, s] = 0.0
    w.disp[k, s] = 0.0
    w.hp[k, s] = 1.0
    w.stam[k, s] = 1.0
    w.stam_lock[k, s] = False
    w.g_size[k, s] = g
    w.g_speed[k, s] = 1.0
    w.E[k, s] = E
    w.bite_cd[k, s] = 0
    w.gore_cd[k, s] = 0
    w.knock_left[k, s] = 0
    w.act[k, s] = B.WATCH
    mat = float(w.sb["maturity"][k, s])
    w.born[k, s] = float(w.t[k]) - (2.0 * mat if af >= 1.0 else af * mat)


def settle(w):
    """After placing by hand: derived values, shelter edges, fresh memory, perception and observation."""
    w.mem[:] = 0.0
    w._derive()
    w._jsh1, w._edge1 = _shelter_edge(w.pos, w.cov_c, w.cov_r, w.cov_ok)
    w._dead = np.zeros((w.K, w.S), dtype=bool)                 # per-step arrays `_phys` makes (direct rule calls in a test)
    w._dead_uid = np.zeros((w.K, w.S), dtype=np.int64)
    w._dec_kills = []
    w.refresh()


class Chase(BR.Brain):
    """CHASE: RUN toward the nearest perceived other-species body (observation only), else WATCH."""

    def decide(self, obs, u, stochastic, state, ctx):
        o = np.asarray(obs, dtype=np.float64)
        pres = o[:, B.other_col(0, "present")] > 0.5
        j = BR._dir_index(o[:, B.other_col(0, "rel_x")], o[:, B.other_col(0, "rel_y")])
        return np.where(pres, B.RUN_FIRST + j, B.WATCH).astype(np.int64), np.full(len(o), np.inf)


class Flee(BR.Brain):
    """FLEE: RUN away from the nearest perceived other (the closest open direction), else WATCH."""

    def decide(self, obs, u, stochastic, state, ctx):
        o = np.asarray(obs, dtype=np.float64)
        pres = o[:, B.other_col(0, "present")] > 0.5
        j = BR._dir_index(-o[:, B.other_col(0, "rel_x")], -o[:, B.other_col(0, "rel_y")], o[:, BR._FREE], BR.PATROL_FREE_MIN)
        return np.where(pres, B.RUN_FIRST + j, B.WATCH).astype(np.int64), np.full(len(o), np.inf)


# --------------------------------------------------------------------------- F-2 R1

def test_f2_mass_wounds_fixed_points_and_table(fcfg):
    w = fworld(fcfg, dict(deer=1, wolf=1, boar=1, buffalo=1, leopard=1, fox=1))
    sl = {s: slot(w, s) for s in range(6)}
    for s in range(6):
        place(w, 0, sl[s], (5.0 + 8.0 * s, 30.0))
    settle(w)
    b = w.body

    def bite(a, t):
        return float(b.bite_k[a]) * w._p23(0, sl[a], sl[t]) / float(b.hide[t])

    def strike(a, t):
        return float(b.strike_k[a]) * w._p23(0, sl[a], sl[t]) / float(b.hide[t])

    assert abs(bite(WO, BO) - 0.45) < 1e-12                       # S′ 고정점: 늑대 → 다 큰 멧돼지 0.45
    assert abs(strike(BO, WO) - 0.18) < 1e-12                     # S′ 고정점: 멧돼지 반격 → 늑대 0.18
    assert bite(WO, DE) >= 1.0                                    # 늑대 → 다 큰 사슴 한 번에
    # 3-2 표 (설계 F-2 의 '늑대 → 물소 0.1424' 는 설계 셈 final_numbers 의 0.1423 과 어긋난 오타 — 셈 값으로 본다)
    for (a, t, kind, v) in ((WO, BU, "bite", 0.1423), (LE, WO, "bite", 0.6962), (WO, LE, "bite", 0.5171), (FX, DE, "bite", 0.0478),
                            (BU, WO, "strike", 0.5693)):
        got = bite(a, t) if kind == "bite" else strike(a, t)
        assert abs(got - v) < 1e-4, (a, t, got, v)
    # AGE23 literal table = the formula bit for bit; age_steps other than 64 is refused
    for i in range(65):
        assert L.AGE23[i] == (0.12 + 0.88 * i / 64) ** (2.0 / 3.0)
    assert L.age_index(0.0) == 0 and L.age_index(1.0) == 64 and L.age_index(0.2) == 13
    with pytest.raises(ValueError):
        B.override(fcfg, {"body_common": {"fauna": {"age_steps": 32}}})
    # the world's bite path: wolf behind a boar → boar HP − 0.45; boar facing the wolf → counter, wolf HP − 0.18
    w = fworld(fcfg, dict(wolf=1, boar=1))
    ws, bs = slot(w, WO), slot(w, BO)
    place(w, 0, ws, (30.0, 30.0), (1.0, 0.0))
    place(w, 0, bs, (30.6, 30.0), (1.0, 0.0))
    settle(w)
    w._resolve_bite(0, ws, bs, 0.6)
    assert abs((1.0 - float(w.hp[0, bs])) - 0.45) < 1e-12 and float(w.hp[0, ws]) == 1.0
    w.hp[0, bs] = 1.0
    w.head[0, bs] = (-1.0, 0.0)
    w._resolve_bite(0, ws, bs, 0.6)
    assert abs((1.0 - float(w.hp[0, ws])) - 0.18) < 1e-12
    assert abs(float(w.hp[0, bs]) - 0.95) < 1e-12
    bp = w.st["bite_pairs"][0]
    assert bp[WO, BO, 1] == 1 and bp[WO, BO, 2] == 1


# --------------------------------------------------------------------------- F-3 R2

def _gore_case(fcfg, target, rel, vel, gait=B.G_RUN, shelters=None):
    counts = {"buffalo": 2 if target == BU else 1}
    if target != BU:
        counts[B.ALL_SPECIES[target]] = 1
    w = fworld(fcfg, counts, shelters=shelters)
    g = slot(w, BU)
    t = slot(w, BU, 1) if target == BU else slot(w, target)
    place(w, 0, g, (30.0, 30.0), (1.0, 0.0))
    place(w, 0, t, (30.0 + rel[0], 30.0 + rel[1]), (1.0, 0.0))
    settle(w)
    w._gait = np.zeros((w.K, w.S), dtype=np.int64)
    w._gait[0, g] = gait
    w.vel[0, g] = vel
    w._gore()
    return w, g, t


def test_f3_gore_conditions(fcfg):
    # full-speed RUN into a wolf in front → gore 0.5693 (g 1), knock, no-bite rest, gorer cost and rest
    w, g, t = _gore_case(fcfg, WO, (0.8, 0.0), (0.48, 0.0))
    d_full = 1.0 - float(w.hp[0, t])
    assert abs(d_full - 0.5693) < 1e-4
    assert int(w.bite_cd[0, t]) >= 30 and int(w.knock_left[0, t]) == 4
    assert int(w.gore_cd[0, g]) == 8 and abs(float(w.hp[0, g]) - 0.95) < 1e-12
    assert w.st["gore"][0, BU, WO, 0] == 1
    # half speed → half the wound
    w, g, t = _gore_case(fcfg, WO, (0.8, 0.0), (0.24, 0.0))
    assert abs((1.0 - float(w.hp[0, t])) - 0.5 * d_full) < 1e-12
    # WALK gait, outside the ±60° cone, out of reach, same species → nothing
    for args in ((WO, (0.8, 0.0), (0.48, 0.0), B.G_WALK),
                 (WO, (0.8 * 0.3420201433256687, 0.8 * 0.9396926207859084), (0.48, 0.0), B.G_RUN),
                 (WO, (1.3, 0.0), (0.48, 0.0), B.G_RUN),
                 (BU, (0.8, 0.0), (0.48, 0.0), B.G_RUN)):
        w, g, t = _gore_case(fcfg, *args)
        assert float(w.hp[0, t]) == 1.0 and int(w.st["gore"].sum()) == 0, args
    # P1: a deer inside a shelter cannot be gored by a body that cannot enter; control without the shelter
    w, g, t = _gore_case(fcfg, DE, (0.8, 0.0), (0.48, 0.0), shelters=[[32.5, 30.0, 1.8]])
    assert float(w._edge1[0, t]) <= 0.0 and bool(w.alive[0, t]) and int(w.st["gore"].sum()) == 0
    w, g, t = _gore_case(fcfg, DE, (0.8, 0.0), (0.48, 0.0))
    assert int(w.st["gore"][0, BU, DE].sum()) == 1
    # RUN action under the stamina lock moves at the walk gait → no gore (real step); control unlocked
    for locked, want in ((True, 0), (False, 1)):
        w = fworld(fcfg, dict(buffalo=1, wolf=1))
        g, t = slot(w, BU), slot(w, WO)
        place(w, 0, g, (30.0, 30.0), (1.0, 0.0))
        place(w, 0, t, (30.9, 30.0), (1.0, 0.0))
        if locked:
            w.stam[0, g] = 0.15
            w.stam_lock[0, g] = True
        settle(w)
        a = np.full((w.K, w.S), B.WATCH, dtype=np.int64)
        a[0, g] = B.RUN_FIRST
        w.step(a)
        assert int(w.st["gore"].sum()) == want, locked
    # no goring body → no gore stream (S′, and the animal world with gore off)
    w = R9World(B.load_r9_config(CFG), [44190])
    assert len(w._gorers) == 0 and all(r is None for r in w.rng_gore)
    w = fworld(fcfg, dict(buffalo=1), patch={"species": {"buffalo": {"gore": False, "gore_r": 0.0}}})
    assert len(w._gorers) == 0 and all(r is None for r in w.rng_gore)


# --------------------------------------------------------------------------- F-4 R3

def test_f4_camouflage(fcfg):
    # all camo 1 → the camo line gives the same bits as the plain line
    c1 = B.override(fcfg, {"species": {"leopard": {"camo": 1.0}}})
    wa = R9World(c1, [44191, 44192])
    wb = R9World(c1, [44191, 44192])
    assert not wa._camo_on
    wb._camo_on = True
    wb.refresh()
    assert same_bits(wa.obs(), wb.obs())
    rng = np.random.default_rng(44193)
    for _ in range(40):
        a = rng.integers(0, B.N_ACTIONS, (wa.K, wa.S))
        oa = wa.step(a)[0]
        ob = wb.step(a)[0]
        assert same_bits(oa, ob)

    # a standing leopard is seen at see_r × 0.4, a running one (|disp| ≥ 0.60) at see_r × 1
    def seen(dist, disp):
        w = fworld(fcfg, dict(deer=1, leopard=1))
        d, le = slot(w, DE), slot(w, LE)
        place(w, 0, d, (30.0, 30.0), (1.0, 0.0))
        place(w, 0, le, (30.0 + dist, 30.0), (-1.0, 0.0))
        settle(w)
        w.disp[0, le] = (disp, 0.0)
        w._perceive(update_mem=False)
        pc = w._pc
        gi = {int(pc["ic"][0, i]): i for i in np.nonzero(pc["valid"][0])[0]}
        return bool(pc["vis"][0, gi[d], gi[le]])

    assert not seen(10.0, 0.0) and seen(7.0, 0.0)           # 20 × 0.4 = 8
    assert seen(10.0, 0.6) and seen(19.0, 0.6) and not seen(21.0, 0.6)


# --------------------------------------------------------------------------- F-5 R4

def test_f5_teeth_bite_every_other_species(fcfg):
    b = B.load_body(fcfg)
    for s in range(6):
        want = np.array([t != s for t in range(6)]) if s in (WO, LE, FX) else np.zeros(6, bool)
        assert same_bits(b.bites[s], want), b.names[s]
    assert b.names == B.ALL_SPECIES[:6] and b.fauna


# --------------------------------------------------------------------------- F-6 R6 · R7

def test_f6_carcass_places_and_breeding_rest(fcfg):
    w = fworld(fcfg, dict(deer=2, wolf=1, boar=1, buffalo=1, leopard=1, fox=1))
    young = slot(w, DE, 1)
    want = {slot(w, DE): 3, slot(w, WO): 3, slot(w, BO): 3, slot(w, BU): 6, slot(w, LE): 3, slot(w, FX): 1, young: 2}
    for i, s in enumerate(want):
        place(w, 0, s, (4.0 + 6.0 * i, 20.0), af=0.0 if s == young else 1.0)
    settle(w)
    for s, n in want.items():
        assert w._carcass_places(0, s) == n, (s, n)
    # a death stores the places on its carcass
    w._dead = np.zeros((w.K, w.S), bool)
    w._dead_uid = np.zeros((w.K, w.S), np.int64)
    w.dead_cause[:] = 0
    w.killer[:] = 0
    fx = slot(w, FX)
    u = int(w.uid[0, fx])
    w._kill(0, fx, CAUSE_BITE, 0)
    w._deaths()
    c = int(np.nonzero(w.carc_ok[0] & (w.carc_uid[0] == u))[0][0])
    assert int(w.carc_places[0, c]) == 1
    # eating: places 1 → only the nearer of two eaters eats; places 2 → both
    for places, both in ((1, False), (2, True)):
        w = fworld(fcfg, dict(wolf=2, deer=1))
        a1, a2, d = slot(w, WO), slot(w, WO, 1), slot(w, DE)
        place(w, 0, a1, (30.3, 30.0))
        place(w, 0, a2, (30.0, 30.6))
        place(w, 0, d, (50.0, 50.0))
        settle(w)
        w._add_carcass(0, np.array([30.0, 30.0]), 4.0, int(w.kin_id[0, d]), DE, 999, 0, places=places)
        a = np.full((w.K, w.S), B.WATCH, dtype=np.int64)
        a[0, [a1, a2]] = B.EAT
        w.step(a)
        gu = w._gain_u[0, :, B.MEAT]
        assert gu[a1] > 0.0 and ((gu[a2] > 0.0) == both), places
    # R7: next breeding = delivery step + the species' recover
    w = fworld(fcfg, dict(buffalo=2, leopard=2))
    assert w.rules.recover_sp == (2250.0, 2250.0, 2250.0, 3375.0, 3650.0, 2250.0)
    ev = L.BreedEvents.empty(w.K, w.S)
    for sp, rec in ((BU, 3375.0), (LE, 3650.0)):
        a, b_ = slot(w, sp), slot(w, sp, 1)
        L._pay(w, ev, w.rules, 0, a, b_, 100.0, sp)
        assert float(w.next_birth[0, a]) == 100.0 + rec and float(w.next_birth[0, b_]) == 100.0 + rec
    ws = R9World(B.load_r9_config(CFG), [44190])
    assert ws.rules.recover_sp == (ws.rules.recover,) * 3


# --------------------------------------------------------------------------- F-7 no species label

def _perm_body6(body, pinv):
    ch = {}
    n = body.n
    for f in dataclasses.fields(body):
        v = getattr(body, f.name)
        if isinstance(v, np.ndarray) and v.shape[:1] == (n,):
            v = v[pinv]
            if f.name in ("bites", "c23"):
                v = v[:, pinv]
            ch[f.name] = v
        elif f.name in ("diet_order", "names"):
            ch[f.name] = tuple(v[i] for i in pinv)
    return dataclasses.replace(body, **ch)


def test_f7_no_species_label_in_observation(fcfg):
    w = R9World(fcfg, [44194, 44195])
    rng = np.random.default_rng(44196)
    for _ in range(30):
        w.step(rng.integers(0, B.N_ACTIONS, (w.K, w.S)))
    w._perceive(update_mem=False)
    o1 = w._observe()
    # species numbers of every slot changed (bodies, kin ids untouched) → the same observation for every observer
    w2 = copy.deepcopy(w)
    w2.sp = ((w.sp.astype(np.int64) + 1) % 6).astype(np.int8)
    w2.carc_sp = np.where(w.carc_sp >= 0, (w.carc_sp.astype(np.int64) + 1) % 6, -1).astype(np.int8)
    w2._perceive(update_mem=False)
    assert same_bits(w2._observe(), o1)
    # species numbers and the body table permuted together (relation preserving) → same per-slot bodies, same observation
    for pi in ([5, 0, 1, 2, 3, 4], [2, 4, 0, 5, 1, 3]):
        pi = np.asarray(pi)
        pinv = np.argsort(pi)
        w2 = copy.deepcopy(w)
        w2.sp = pi[w.sp].astype(np.int8)
        w2.slot_sp = pi[w.slot_sp].astype(np.int8)
        w2.body = _perm_body6(w.body, pinv)
        w2.sb = B.expand_body(w2.body, w2.sp)
        for f in B.SLOT_FIELDS + B.SLOT_FOOD_FIELDS + B.SLOT_FAUNA_FIELDS:
            assert same_bits(w2.sb[f], w.sb[f]), f
        w2._perceive(update_mem=False)
        assert same_bits(w2._observe(), o1)


# --------------------------------------------------------------------------- F-8 RNG

def _four_species(cfg):
    c = copy.deepcopy({k: v for k, v in cfg.items() if k != "_path"})
    for n in ("leopard", "fox"):
        for blk in (c["species"], c["world"]["slots"], c["counts"], c["learner_counts"], c["randomize"]["juvenile_frac"], c["rules"],
                    c["train"]["worlds"], c["train"]["n_steps"], c["train"]["snapshot_every"]):
            blk.pop(n, None)
    c["species"]["wolf"]["bites"] = ["deer", "boar", "buffalo"]
    c["train"]["variants"] = [v for v in c["train"]["variants"] if v["name"] != "few_wolves"]
    return B.check_r9_config(c)


def test_f8_rng_streams(fcfg):
    seeds = list(range(44180, 44186))
    ws = R9World(B.load_r9_config(CFG), seeds)
    wf = R9World(fcfg, seeds)
    for n in ("counts", "run_mult", "juv_frac"):
        assert same_bits(getattr(ws, n), getattr(wf, n)[:, :3]), n
    assert same_bits(ws.rule_f, wf.rule_f)
    assert same_bits(ws.kin_perm, wf.kin_perm[:, :3]) and (wf.kin_perm[:, 3:] == np.array([3, 4, 5])).all()
    # VecEnv: species with world.slots 0 draw no opponent meta uniforms (6 species with leopard/fox at 0 = the 4-species config)
    c0 = B.override(fcfg, {"world": {"slots": {"leopard": 0, "fox": 0}}, "counts": {"leopard": [0, 0], "fox": [0, 0]},
                           "learner_counts": {"leopard": [0], "fox": [0]}})
    c4 = _four_species(fcfg)
    hist = []
    for c in (c0, c4):
        v = R9VecEnv(c, "deer", model_seed=0, round_=0, seeds=range(44180, 44200), num_worlds=4, reset_steps=20, online_stats=False)
        rng = np.random.default_rng(44197)
        for _ in range(12):
            v.step_async(rng.integers(0, B.N_ACTIONS, v.num_envs))
            v.step_wait()
        hist.append((v.seed_history, [{n: h["opponents"][n] for n in ("wolf", "boar", "buffalo")} for h in v.history]))
        v.close()
    assert hist[0] == hist[1] and len(hist[0][1]) > 4


# --------------------------------------------------------------------------- F-9 training line (smoke)

def _train_mod():
    import importlib.util
    import sys
    if "r9_train_mod" not in sys.modules:
        spec = importlib.util.spec_from_file_location("r9_train_mod", ROOT / "results" / "v3" / "r9" / "train_r9.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["r9_train_mod"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["r9_train_mod"]


def _train(tmp_path, sp, decisions, worlds, init_sp=None, n_steps=32, batch=64):
    T = _train_mod()
    args =["--config", str(FCFG), "--species", sp, "--branch", "T", "--model-seed", "0", "--round", "0",
            "--decisions", str(decisions), "--wall-hours", "1", "--num-worlds", str(worlds), "--seeds", "44180", "44200",
            "--out", str(tmp_path), "--log-dir", str(tmp_path), "--run-name", f"f9_{sp}", "--log-first", "0",
            "--log-every", "1000000000", "--gamma", "0.99", "--n-steps", str(n_steps), "--batch-size", str(batch)]
    if init_sp:
        args += ["--init", str(SRC / f"{DEMO_ZIP[init_sp]}.zip"), "--init-species", init_sp]
    assert T.main(args) == 0
    meta = json.loads((tmp_path / "T" / f"f9_{sp}.json").read_text(encoding="utf-8"))
    assert meta["stop"] in ("target", "wall_clock") and meta["snapshots"]
    return meta


@pytest.mark.parametrize("sp,init_sp", [("buffalo", "boar"), ("leopard", "wolf"), ("fox", "wolf")])
def test_f9_train_line_smoke(tmp_path, fcfg, sp, init_sp):
    full = os.environ.get("R9_FAUNA_F9_FULL") == "1"            # 설계 F-9: 각 10만 결정·세계 12 (합 약 5 분)
    have = all((SRC / f"{z}.zip").exists() for z in DEMO_ZIP.values())
    meta = _train(tmp_path, sp, 100_000 if full else 384, 12 if full else 2, init_sp if have else None,
                  n_steps=int(fcfg["train"]["n_steps"][sp]) if full else 32, batch=4096 if full else 64)
    p = Path(meta["snapshots"][-1]["npz"])
    br = BR.load_brain(p if p.is_absolute() else ROOT / p, fcfg, sp)   # the animal world accepts it
    assert br.meta["species"] == sp
    if have:
        assert meta["init_species"] == init_sp


def test_f9_rebody(tmp_path, fcfg):
    src = SRC / "deer_r0_20013056.npz"
    if not src.exists():
        pytest.skip("demo start brains not copied (SPECIES_START.md 시작 판 복사)")
    with pytest.raises(BR.BrainContractError):
        BR.load_brain(src, fcfg, "deer")                          # another body: refused without rebody
    with pytest.raises(BR.BrainContractError):
        BR.rebody_brain(src, fcfg, "wolf", tmp_path / "x.npz")    # same species only
    with np.load(src, allow_pickle=False) as z:
        old = json.loads(str(z["meta_json"][()]))
        wts = {k: np.array(z[k]) for k in BR.NPZ_WEIGHT_KEYS}
    meta = BR.rebody_brain(src, fcfg, "deer", tmp_path / "deer_v0.npz")
    assert meta["init_from"]["body_hash"] == old["body_hash"] and meta["init_from"]["species"] == "deer"
    assert meta["body_hash"] == B.hash_hex(B.body_hash(fcfg, "deer")) != old["body_hash"]
    b = BR.load_brain(tmp_path / "deer_v0.npz", fcfg, "deer")
    for k in BR.NPZ_WEIGHT_KEYS:
        assert same_bits(b.weights[k], wts[k])


# --------------------------------------------------------------------------- F-10 body check 'can do' (not a judgement)

def test_f10_fox_cannot_kill_adult_deer_and_wolf_leopard_two_touches(fcfg):
    rows = [(d, st) for d in (1.0, 2.0, 4.0, 8.0) for st in (1.0, 0.15)]
    w = fworld(fcfg, dict(deer=1, fox=1), seeds=[44180 + i for i in range(len(rows))], record=True, cls=NoRespawn)
    d_, f_ = slot(w, DE), slot(w, FX)
    for k, (dist, st) in enumerate(rows):
        place(w, k, d_, (30.0, 30.0), (1.0, 0.0))
        place(w, k, f_, (30.0 - dist, 30.0), (1.0, 0.0))
        w.stam[k, d_] = st
        w.stam_lock[k, d_] = st <= 0.15
    settle(w)
    for k in range(w.K):
        w.set_controller(k, DE, BR.Controller(Flee(name="FLEE", kind="rule"), False, "flee"))
        w.set_controller(k, FX, BR.Controller(Chase(name="CHASE", kind="rule"), False, "chase"))
    for _ in range(450):                                          # 900 steps
        w.step(w.decide())
    assert sum(1 for e in w.events["deaths"] if e["sp"] == DE and e["cause"] == "bite") == 0
    assert len(w.events["bites"]) > 0                             # the fox did reach and bite (the check is not empty)
    # wolf 1 ↔ leopard 1 walking into each other: never a death at the first touch (hide 2.5 — two bites)
    w = fworld(fcfg, dict(wolf=1, leopard=1), seeds=list(range(44180, 44200)) * 2, record=True, cls=NoRespawn)
    a_, b_ = slot(w, WO), slot(w, LE)
    for k in range(w.K):
        dv = B.DIR8[k % 8]
        place(w, k, a_, 30.0 - 3.0 * dv, dv)
        place(w, k, b_, 30.0 + 3.0 * dv, -dv)
    settle(w)
    for k in range(w.K):
        for s in (WO, LE):
            w.set_controller(k, s, BR.Controller(Chase(name="CHASE", kind="rule"), False, "chase"))
    for _ in range(150):
        w.step(w.decide())
    hit = {}
    one_touch = 0
    for e in w.events["bites"]:
        key = (e["k"], e["prey_uid"])
        if e["outcome"] == "kill" and key not in hit:
            one_touch += 1
        hit[key] = hit.get(key, 0) + 1
    assert len(w.events["bites"]) > 0 and one_touch == 0


# --------------------------------------------------------------------------- F-11 rule brain branches

def _obs(n=1):
    return np.zeros((n, B.OBS_DIM), dtype=np.float32)


def _other(o, i, rel, appr=0.0, size=0.45, facing=0.0, j=0):
    o[i, B.other_col(j, "present")] = 1.0
    o[i, B.other_col(j, "rel_x")], o[i, B.other_col(j, "rel_y")] = rel
    o[i, B.other_col(j, "dist")] = float(np.hypot(*rel))
    o[i, B.other_col(j, "approach")] = appr
    o[i, B.other_col(j, "size")] = size
    o[i, B.other_col(j, "facing")] = facing


def _act(brain, o):
    u = np.zeros((o.shape[0], B.N_ACTIONS))
    return brain.decide(o, u, False, brain.new_state(o.shape[0]), {})[0]


def test_f11_rule_brain_branches(fcfg):
    buf = BR.make_rule("RULE_BUFFALO", fcfg, BU)
    o = _obs(5)
    o[:, B.O_ENERGY] = 1.0
    _other(o, 0, (0.1, 0.0), appr=0.5)                            # ① head-on → RUN toward (charge)
    _other(o, 1, (0.0, 0.1), appr=0.5)                            # ① from the side → WALK toward (turn)
    o[2, B.O_ENERGY] = 0.5
    o[2, B.O_FOOD_HERE] = 1.0                                     # ② hungry, food here → EAT
    o[3, B.kin_col(0, "present")] = 1.0
    o[3, B.kin_col(0, "rel_x")] = 0.5                             # ③ kin 10 units ahead > 6 → WALK toward it
    a = _act(buf, o)                                              # ④ row 4 → WATCH
    assert a.tolist() == [B.RUN_FIRST, B.WALK_FIRST + 2, B.EAT, B.WALK_FIRST, B.WATCH]
    leo = BR.make_rule("RULE_LEOPARD", fcfg, LE)
    o = _obs(8)
    o[:, B.O_ENERGY] = 1.0
    o[:, B.O_STAMINA] = 1.0
    _other(o, 0, (0.2, 0.0), appr=0.5, size=0.44)                 # ① threat, no shelter known → RUN away (j = 4)
    _other(o, 1, (0.2, 0.0), appr=0.5, size=0.44)
    o[1, B.O_IN_SHELTER] = 1.0                                    # ① inside → SHELTER
    o[2, B.O_ENERGY] = 0.5
    o[2, B.O_FOOD_HERE] = 1.0                                     # ② carcass here → EAT
    o[3, B.O_ENERGY] = 0.5
    _other(o, 3, (0.0, 0.5), size=0.3, facing=0.0)                # ③ prey 10 units, not facing → WALK toward
    o[4, B.O_ENERGY] = 0.5
    _other(o, 4, (0.0, 0.5), size=0.3, facing=0.9)                # ③ prey facing me → WATCH
    o[5, B.O_ENERGY] = 0.5
    _other(o, 5, (0.1, 0.0), size=0.3)                            # ③ prey within 4 → RUN
    o[6, B.O_STAMINA] = 0.1
    o[6, B.O_SHELTER_X] = 1.0                                     # ④ locked → WALK toward the shelter
    a = _act(leo, o)                                              # ⑤ row 7 → WATCH
    assert a.tolist() == [B.RUN_FIRST + 4, B.SHELTER, B.EAT, B.WALK_FIRST + 2, B.WATCH, B.RUN_FIRST, B.WALK_FIRST, B.WATCH]
    fox = BR.make_rule("RULE_FOX", fcfg, FX)
    o = _obs(6)
    o[:, B.O_ENERGY] = 1.0
    o[:, B.O_OWN_SIZE] = 0.24
    _other(o, 0, (0.0, -0.2), appr=0.5, size=0.5)                 # ① big and coming → RUN away (j = 2)
    _other(o, 1, (0.0, -0.2), appr=0.5, size=0.5)
    o[1, B.O_IN_SHELTER] = 1.0                                    # ① inside → SHELTER
    o[2, B.O_ENERGY] = 0.5
    _other(o, 2, (0.1, 0.0), size=0.1)                            # ② small body within 4 → RUN toward
    o[3, B.O_ENERGY] = 0.5
    o[3, B.O_FOOD_HERE] = 1.0                                     # ② seek → EAT here
    _other(o, 4, (0.0, -0.2), appr=0.5, size=0.3)                 # not bigger than 1.5 × own → no flight → ③ WATCH
    a = _act(fox, o)                                              # ③ row 5 → WATCH
    assert a.tolist() == [B.RUN_FIRST + 2, B.SHELTER, B.RUN_FIRST, B.EAT, B.WATCH, B.WATCH]


# --------------------------------------------------------------------------- F-12 P1 shelter guard

def test_f12_shelter_guard(fcfg):
    sh = [[30.0, 30.0, 5.0]]
    # a leopard inside the same shelter bites the deer inside it
    w = fworld(fcfg, dict(deer=1, leopard=1), shelters=sh)
    d, le = slot(w, DE), slot(w, LE)
    place(w, 0, d, (31.0, 30.0), (1.0, 0.0))
    place(w, 0, le, (30.2, 30.0), (1.0, 0.0))
    settle(w)
    a = np.full((w.K, w.S), B.WATCH, dtype=np.int64)
    a[0, le] = B.RUN_FIRST
    w.step(a)
    assert w.st["bite_pairs"][0, LE, DE].sum() >= 1 and w.st["bite_in_shelter"][0, LE, DE] >= 1

    # a wolf outside cannot bite a fox inside; control: the same geometry without the shelter → bite
    def wolf_on_fox(shelters):
        w = fworld(fcfg, dict(wolf=1, fox=1), shelters=shelters)
        f_, w_ = slot(w, FX), slot(w, WO)
        place(w, 0, f_, (34.8, 30.0), (1.0, 0.0))
        place(w, 0, w_, (35.6, 30.0), (-1.0, 0.0))
        settle(w)
        a = np.full((w.K, w.S), B.WATCH, dtype=np.int64)
        a[0, w_] = B.RUN_FIRST
        w.step(a)
        return int(w.st["bite_pairs"][0, WO, FX].sum())

    assert wolf_on_fox(sh) == 0 and wolf_on_fox(None) >= 1

    # a buffalo cannot gore a deer inside a shelter; control without it
    def buffalo_on_deer(shelters):
        w = fworld(fcfg, dict(buffalo=1, deer=1), shelters=shelters)
        d, g = slot(w, DE), slot(w, BU)
        place(w, 0, d, (34.8, 30.0), (1.0, 0.0))
        place(w, 0, g, (35.7, 30.0), (-1.0, 0.0))
        settle(w)
        w.vel[0, g] = (-0.3, 0.0)
        a = np.full((w.K, w.S), B.WATCH, dtype=np.int64)
        a[0, g] = B.RUN_FIRST
        w.step(a)
        return int(w.st["gore"][0, BU, DE].sum())

    assert buffalo_on_deer(sh) == 0 and buffalo_on_deer(None) >= 1


# --------------------------------------------------------------------------- F-13 variants · shards

def test_f13_variants_and_learner_slots(fcfg):
    want_env = dict(wolf=448, buffalo=384, leopard=288, fox=288)
    for sp, n_env in want_env.items():
        v = R9VecEnv(fcfg, sp, model_seed=0, round_=0, seeds=range(44180, 44200), online_stats=False)
        try:
            assert v.num_envs == n_env, (sp, v.num_envs)
            cnt = v.shards[0].core.world.counts
            for k in range(v.K):
                if sp in ("wolf", "buffalo") and k % 4 == 3:
                    j = k // 4
                    assert v.variant[k] == "buffalo_land"
                    assert cnt[k, DE] == (0, 2, 4)[j % 3]
                    if sp == "wolf":
                        assert cnt[k, BU] == (4, 6, 8)[j % 3] and cnt[k, WO] == (4, 6)[j % 2]
                    else:
                        assert cnt[k, BU] == (2, 3, 4, 6)[k % 4]          # the learner count is not overridden
                elif sp == "leopard" and k % 3 == 2:
                    assert v.variant[k] == "few_wolves" and cnt[k, WO] == (0, 1)[(k // 3) % 2]
                else:
                    assert v.variant[k] is None
            assert all("variant" in h for h in v.history)
        finally:
            v.close()
    # S′ history rows keep their keys (no 'variant')
    v = R9VecEnv(B.load_r9_config(CFG), "deer", model_seed=0, round_=0, seeds=range(44180, 44200), num_worlds=2, online_stats=False)
    assert all("variant" not in h for h in v.history)
    v.close()


def test_f13_wolf_shards_bit_identical(fcfg):
    res = {}
    for n_sh in (1, 2, 3):
        v = R9VecEnv(fcfg, "wolf", model_seed=0, round_=0, seeds=range(44180, 44200), num_worlds=6, reset_steps=60, shards=n_sh)
        try:
            assert len(v.shards) == n_sh
            out = [v.reset()]
            rng = np.random.default_rng(44198)
            for _ in range(80):
                v.step_async(rng.integers(0, B.N_ACTIONS, v.num_envs))
                o, r, d, inf = v.step_wait()
                out += [o, r, d, np.array([bool(i.get("TimeLimit.truncated")) for i in inf])]
            st = v.stats_snapshot()
            out += [st["deaths"], st["bite_pairs"], st["gore"]]
            res[n_sh] = (out, json.dumps(v.history, sort_keys=True), v.num_resets)
        finally:
            v.close()
    for n_sh in (2, 3):
        assert res[n_sh][1] == res[1][1] and res[n_sh][2] == res[1][2] > 0
        for a, b in zip(res[1][0], res[n_sh][0]):
            assert same_bits(a, b)


def test_fauna_config_checks(fcfg):
    """설정 검사: fauna 블록 없는 설정에 새 몸 칸, 쥐·까마귀, 새 종 필수 칸, 판정 세계 6 종, 동물 판정 시드."""
    raw = copy.deepcopy({k: v for k, v in B.load_r9_config(CFG).items() if k != "_path"})
    raw["species"]["deer"]["hide"] = 1.0
    with pytest.raises(ValueError):
        B.check_r9_config(raw)
    c = copy.deepcopy({k: v for k, v in fcfg.items() if k != "_path"})
    c["species"]["rat"] = copy.deepcopy(c["species"]["fox"])
    with pytest.raises(ValueError):
        B.species_of(c)
    c = copy.deepcopy({k: v for k, v in fcfg.items() if k != "_path"})
    del c["species"]["buffalo"]["hide"]
    with pytest.raises(ValueError):
        B.check_r9_config(c)
    c = copy.deepcopy({k: v for k, v in fcfg.items() if k != "_path"})
    del c["rules"]["fox"]
    with pytest.raises(ValueError):
        B.check_r9_config(c)
    jc = B.override(fcfg, {"world": {"mode": "judge"}, "food": {"quadrant_grass_total": 70.0},
                           "judge": B.load_r9_config(JCFG)["judge"]})
    with pytest.raises(NotImplementedError):
        R9World(jc, [44199])
    with pytest.raises(ValueError):
        V.check_train_seeds([46950])
