"""R9 세계 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 12절, 세계 env_v2/r9_world.py).

12절 번호 그대로: 1 결정성·묶음 무관 · 2 관측 함수가 종 번호를 안 읽음 · 3 종 바꿔치기(관계 보존) · 4 보상식 · 5 행동 19 칸 × 3 종 ·
6 스텝 안 삼각함수 없음(표 부분은 test_r9_body.py) · 7 차례 합 = 명시 고리 · 8 물기·반격 · 9 사체 · 10 지구력·상처·약함 · 11 은신처 ·
12 다시 남 · 19 속력 집합·접촉 변위 · 20 R8 과 풀 생성·재생·셀 수요 나누기 비트 같음 · 22 산 개체 모으기 = (K, S, S) · 23 장부.
S′ (2026-11-12) 로 뜻을 바꾼 시험: 02b (관측 입력에 act·eat_min·fd_fast, 115 칸) · 05 (EAT·SHELTER = 제자리 서기) · 20 (풀 생성기 비교는
학습 세계 풀 맞춤을 끄고) · 23 (고기 장부: 늑대가 관측으로 사체에 가서 먹음). S′ 전용 시험은 tests/test_r9_s_world.py.
시드: 44350~44399 만 쓴다(10절). 장면 시험은 장면 꼴(배치·머리·속도)을 손으로 놓고 `refresh()` 한다.
"""

import copy
import dataclasses
import inspect
import math

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import r8_world as RW8
from env_v2 import r9_body as B
from env_v2 import r9_life as L
from env_v2 import r9_world as RW
from env_v2.r9_world import R9World

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"
R8CFG = ROOT / "configs" / "v3_r8_pilot.yaml"
SEEDS = [44350, 44351, 44352, 44353]
D_, W_, R_ = B.DEER, B.WOLF, B.BOAR


@pytest.fixture(scope="module")
def cfg():
    return B.load_r9_config(CFG)


@pytest.fixture(scope="module")
def jcfg():
    return B.load_r9_config(JCFG)


def rand_act(rng, w):
    return rng.integers(0, B.N_ACTIONS, (w.K, w.S))


def same_bits(a, b) -> bool:
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


# --------------------------------------------------------------------------- 장면 도구


def scene(cfg, counts, shelters=((55.0, 55.0, 4.0),), K=1, seed=44360, patch=None):
    """K worlds with fixed shelters and counts; everybody stopped, adult, standard genome (1, 1), full stamina/HP, no breeding
    (next_birth far), no grid food. Place individuals with `put`, then call w.refresh()."""
    p = {"world": {"shelters": {"fixed": [list(s) for s in shelters]}}}
    if patch:
        p = B._deep_merge(p, patch)
    c = B.override(cfg, p)
    w = R9World(c, [seed + i for i in range(K)], counts=np.tile(np.asarray(counts, dtype=np.int64), (K, 1)))
    a = w.alive
    w.vel[:] = 0.0
    w.disp[:] = 0.0
    w.g_size[a] = 1.0
    w.g_speed[a] = 1.0
    w.hp[:] = 1.0
    w.stam[:] = 1.0
    w.stam_lock[:] = False
    w.E[a] = 0.6
    w.R[a] = 0.5
    w.born[:] = -3.0 * w.sb["maturity"]
    w.next_birth[:] = 1e9
    w.grass[:] = 0.0
    w.root[:] = 0.0
    w.grass_cap[:] = 0.0
    w.root_cap[:] = 0.0
    w.mem[:] = 0.0
    w.refresh()
    return w


def put(w, s, xy, head=(1.0, 0.0), vel=(0.0, 0.0), k=0):
    h = np.asarray(head, dtype=np.float64)
    w.pos[k, s] = xy
    w.head[k, s] = h / np.sqrt((h * h).sum())
    w.vel[k, s] = vel


def acts(w, default=B.WATCH, **by_slot):
    a = np.full((w.K, w.S), default, dtype=np.int64)
    for s, v in by_slot.items():
        a[:, int(s[1:])] = v
    return a


def lo(w, sp):
    return int(w.sp_lo[sp])


# --------------------------------------------------------------------------- 1


def test_01_determinism_and_batch_independence(cfg, jcfg):
    a = R9World(cfg, SEEDS)
    b = R9World(cfg, SEEDS)
    c = R9World(cfg, [SEEDS[2]])
    d = R9World(cfg, SEEDS[::-1])
    assert same_bits(a.obs(), b.obs()) and same_bits(a.obs()[2:3], c.obs()) and same_bits(a.obs()[::-1], d.obs())
    rng = np.random.default_rng(44350)
    for _ in range(150):
        act = rand_act(rng, a)
        oa, ra, da, ia = a.step(act)
        ob, rb, db, _ = b.step(act)
        oc, rc, dc, _ = c.step(act[2:3])
        od, rd, dd, _ = d.step(act[::-1])
        assert same_bits(oa, ob) and same_bits(ra, rb) and same_bits(da, db)
        assert same_bits(oa[2:3], oc) and same_bits(ra[2:3], rc) and same_bits(da[2:3], dc)
        assert same_bits(oa[::-1], od) and same_bits(ra[::-1], rd)
    for n in ("pos", "vel", "E", "R", "hp", "stam", "grass", "root", "mem", "carc_meat", "uid"):
        assert same_bits(getattr(a, n), getattr(b, n)), n
        assert same_bits(getattr(a, n)[2:3], getattr(c, n)), n
        assert same_bits(getattr(a, n)[::-1], getattr(d, n)), n
    assert a.st["deaths"].sum() > 0                       # the run is not empty (deaths and respawns happened)
    # judge world (births by r9_life, no respawn): same rule
    ja = R9World(jcfg, [44354, 44355])
    jb = R9World(jcfg, [44355])
    rng = np.random.default_rng(44351)
    for _ in range(40):
        act = rand_act(rng, ja)
        oa, ra, _, _ = ja.step(act)
        ob, rb, _, _ = jb.step(act[1:2])
        assert same_bits(oa[1:2], ob) and same_bits(ra[1:2], rb)
    assert same_bits(ja.pos[1:2], jb.pos) and same_bits(ja.mem[1:2], jb.mem)


# --------------------------------------------------------------------------- 2


FORBID = {"sp", "slot_sp", "carc_sp", "body", "rules", "life", "sp_lo", "sp_hi", "caps", "counts", "_biters", "_bite_mat",
          "_diet_rank", "_first_grid", "_meat_only", "carc_uid", "carc_killer"}


class Guarded(R9World):
    """Raises if perception or the observation builder reads a species label (12절 시험 2)."""
    _guard = False

    def __getattribute__(self, name):
        if name in FORBID and object.__getattribute__(self, "_guard"):
            raise AssertionError(f"perception/observation read hidden '{name}'")
        return object.__getattribute__(self, name)

    def _perceive(self, update_mem):
        object.__setattr__(self, "_guard", True)
        try:
            return super()._perceive(update_mem)
        finally:
            object.__setattr__(self, "_guard", False)

    def _observe(self):
        object.__setattr__(self, "_guard", True)
        try:
            return super()._observe()
        finally:
            object.__setattr__(self, "_guard", False)


def test_02_obs_function_never_reads_species(cfg, jcfg):
    fields = set(RW.ObsInputs._fields)
    assert not fields & {"sp", "slot_sp", "carc_sp", "body", "species", "kind"}
    assert list(inspect.signature(RW.build_obs).parameters) == ["inp"]
    for c, seeds in ((cfg, SEEDS[:2]), (jcfg, [44356])):
        g = Guarded(c, seeds)
        p = R9World(c, seeds)
        object.__setattr__(g, "_guard", True)
        with pytest.raises(AssertionError):
            _ = g.sp
        object.__setattr__(g, "_guard", False)
        rng = np.random.default_rng(44352)
        for _ in range(40):
            act = rand_act(rng, g)
            og, rg, _, _ = g.step(act)
            op, rp, _, _ = p.step(act)
            assert same_bits(og, op) and same_bits(rg, rp)
        g.reinit(0, 44357)
        p.reinit(0, 44357)
        assert same_bits(g.obs(), p.obs())


def test_02b_obs_reads_only_the_observers_body_row(cfg, jcfg):
    """Fix 단계 검토 low: build_obs gets the per-slot body arrays `sb` of every slot, so tests 2·3 could not catch an observation
    that reads another individual's body value (e.g. mass_kg = a species label). Here, for each observer i, every OTHER slot's
    `sb` row is replaced by the row of a slot of another species (size_obs·disp·head·kin_id untouched) — observer i's 115
    columns must stay bit-identical. So only the observer's own body row (diet, e_per_unit, food refs) reaches its observation."""
    for c, seeds in ((cfg, [44358]), (jcfg, [44359])):
        w = R9World(c, seeds)
        rng = np.random.default_rng(44362)
        for _ in range(6):
            w.step(rand_act(rng, w))
        base = dict(w.sb)
        donors = [lo(w, sp) for sp in range(3)]
        w._derive()                                    # size_obs·af·mature from the true body rows (not from the swapped ones)

        def obs_with(sb):
            inp = RW.ObsInputs(t=w.t, pc=w._pc, pos=w.pos, head=w.head, disp=w.disp, alive=w.alive, kin_id=w.kin_id, sb=sb, E=w.E,
                               R=w.R, stam=w.stam, hp=w.hp, size_obs=w.size_obs, af=w.af, next_birth=w.next_birth, mating=w.mating,
                               sex=w.sex, mature=w.mature, uid=w.uid, parent_a=w.parent_a, parent_b=w.parent_b,
                               check_related=w.judge, size=w.size, cell=w.cell, grass=w.grass, root=w.root, cov_c=w.cov_c,
                               cov_r=w.cov_r, cov_ok=w.cov_ok, mem=w.mem, act=w.act, eat_min=w._eat_min,
                               fd_fast=w.food_dir_fast)
            return RW.build_obs(inp)[0]

        assert same_bits(obs_with(base), w.obs())
        for sp in range(3):
            i = lo(w, sp)
            if not w.alive[0, i]:
                continue
            obs0 = obs_with(base)[0, i].copy()
            for d in donors:
                if int(w.slot_sp[d]) == sp:
                    continue
                sb2 = {}
                for key, a in base.items():
                    if not (isinstance(a, np.ndarray) and a.shape[:2] == (w.K, w.S)):
                        sb2[key] = a
                        continue
                    b = a.copy()
                    others = np.arange(w.S) != i
                    b[0, others] = a[0, d]
                    sb2[key] = b
                assert same_bits(obs0, obs_with(sb2)[0, i]), (sp, d)



def _perm_body(body: B.Body, pinv: np.ndarray) -> B.Body:
    """Body table relabelled: new species number n holds the values of old species pinv[n]."""
    ch = {}
    for f in dataclasses.fields(body):
        v = getattr(body, f.name)
        if isinstance(v, np.ndarray) and v.shape[:1] == (3,):
            v = v[pinv]
            if f.name == "bites":
                v = v[:, pinv]
            ch[f.name] = v
        elif f.name == "diet_order":
            ch[f.name] = tuple(v[i] for i in pinv)
    return dataclasses.replace(body, **ch)


def _obs_now(w):
    w._perceive(update_mem=False)
    return w._observe()


def test_03_species_relabel_swaps(cfg):
    w = R9World(cfg, list(range(44358, 44366)))
    rng = np.random.default_rng(44353)
    for _ in range(60):
        w.step(rand_act(rng, w))
    o1 = _obs_now(w)
    # (가) species numbers and body table permuted together (relation preserving): same per-slot body arrays, same kin_id
    for pi in ([2, 0, 1], [1, 2, 0], [0, 2, 1]):
        pi = np.asarray(pi)
        pinv = np.argsort(pi)
        w2 = copy.deepcopy(w)
        w2.sp = pi[w.sp].astype(np.int8)
        w2.slot_sp = pi[w.slot_sp].astype(np.int8)
        w2.carc_sp = np.where(w.carc_sp >= 0, pi[np.maximum(w.carc_sp, 0)], -1).astype(np.int8)
        w2.body = _perm_body(w.body, pinv)
        w2.sb = B.expand_body(w2.body, w2.sp)
        w2.kin_perm = w.kin_perm[:, pinv]
        for f in B.SLOT_FIELDS + B.SLOT_FOOD_FIELDS:
            assert same_bits(w2.sb[f], w.sb[f]), f
        assert same_bits(w2.kin_perm[np.arange(w.K)[:, None], w2.slot_sp.astype(int)], w.kin_id)   # kin_id unchanged
        assert same_bits(_obs_now(w2), o1)
    # (나) for a deer observer: swap the species numbers (and kin ids) of a wolf and a boar it perceives, bodies untouched
    hits = 0
    for k in range(w.K):
        pc = w._pc
        valid = pc["valid"][k]
        icr = pc["ic"][k]
        for ii in np.nonzero(valid)[0]:
            i = int(icr[ii])
            if w.slot_sp[i] != D_:
                continue
            seen = icr[np.nonzero(pc["perc"][k, ii] & valid)[0]]
            wolves = [j for j in seen if w.slot_sp[j] == W_]
            boars = [j for j in seen if w.slot_sp[j] == R_]
            if wolves and boars:
                j1, j2 = int(wolves[0]), int(boars[0])
                w2 = copy.deepcopy(w)
                w2.sp[k, j1], w2.sp[k, j2] = w.sp[k, j2], w.sp[k, j1]
                w2.kin_id[k, j1], w2.kin_id[k, j2] = w.kin_id[k, j2], w.kin_id[k, j1]
                o2 = _obs_now(w2)
                deer = w.alive[k] & (w.slot_sp == D_)
                assert same_bits(o2[k][deer], o1[k][deer])
                hits += 1
                break
    assert hits >= 1
    # (다) another kin_id permutation → same observation
    for sig in ([1, 2, 0], [2, 1, 0]):
        sig = np.asarray(sig, dtype=np.int8)
        w2 = copy.deepcopy(w)
        w2.kin_perm = sig[w.kin_perm]
        w2.kin_id = sig[w.kin_id]
        w2.carc_kin = np.where(w.carc_kin >= 0, sig[np.maximum(w.carc_kin, 0)], -1).astype(np.int8)
        assert same_bits(_obs_now(w2), o1)


# --------------------------------------------------------------------------- 4


def _no_breed(monkeypatch):
    monkeypatch.setattr(RW.L, "breed_step", lambda w, life, rules: L.BreedEvents.empty(w.K, w.S))


def test_04_reward_formula(cfg, monkeypatch):
    _no_breed(monkeypatch)
    w = R9World(cfg, SEEDS[:3], counts=np.array([[20, 2, 6]] * 3))
    C = w.sb["reserve_cap"]
    rng = np.random.default_rng(44354)
    # wolves only watch (no approach → no bite); prey eat / walk / watch / shelter. Low E for some: fat is spent; high E: refilled
    w.E[:, :6] = 0.0005
    w.R[:, :6] = 0.5
    w.E[:, 6:12] = 0.95
    w.R[:, 6:12] = 0.2
    w.R[w.alive & (w.R < 0.05)] = 0.05                      # nobody starves in this part
    w.refresh()
    spent = filled = 0
    for _ in range(60):
        a = rng.choice([B.EAT, B.WALK_FIRST + 2, B.WATCH, B.SHELTER], (w.K, w.S))
        a[:, lo(w, W_):lo(w, R_)] = B.WATCH
        v0 = w.E + w.R * C
        r0 = w.R.copy()
        _, r, done, info = w.step(a)
        assert not done.any() and not info["births"].any()
        alive = w.alive
        want = 2 * 0.01 + (w.E + w.R * C) - v0
        assert np.allclose(r[alive], want[alive], atol=1e-12)
        assert (r[~alive] == 0.0).all()
        spent += int((w.R < r0 - 1e-15).sum())
        filled += int((w.R > r0 + 1e-15).sum())
    assert spent > 0 and filled > 0
    # death: −10 and the energy change up to death (all three species, starving at the first step of the decision)
    ss = [lo(w, D_), lo(w, W_), lo(w, R_)]
    for s in ss:
        w.E[:, s] = -1.0
        w.R[:, s] = 0.0
    w.refresh()
    w._derive()
    dr = w.sb["drain"] * w._gait_drain[B.G_STAND] * w.maint
    v0 = w.E + w.R * C
    _, r, done, info = w.step(np.full((w.K, w.S), B.WATCH))
    for s in ss:
        assert done[:, s].all() and (info["dead_cause"][:, s] == RW.CAUSE_STARVE).all()
        assert np.allclose(r[:, s], 0.01 + (-1.0 - dr[:, s]) - v0[:, s] - 10.0, atol=1e-12)
    # births: +10 to both parents and the −0.2 cost inside Δ (fake life events: wiring only — life owns the rule)
    t_birth = int(w.t[0])

    def fake(wd, life, rules):
        ev = L.BreedEvents.empty(wd.K, wd.S)
        if int(wd.t[0]) == t_birth:
            for s in (lo(wd, D_) + 1, lo(wd, D_) + 2):
                ev.births[:, s] = 1
                wd.E[:, s] -= 0.2
        return ev
    monkeypatch.setattr(RW.L, "breed_step", fake)
    w.E[:, 13:15] = 0.9
    w.refresh()
    v0 = w.E + w.R * C
    _, r, done, info = w.step(np.full((w.K, w.S), B.WATCH))
    for s in (lo(w, D_) + 1, lo(w, D_) + 2):
        assert (info["births"][:, s] == 1).all()
        assert np.allclose(r[:, s], 0.02 + 10.0 + (w.E + w.R * C)[:, s] - v0[:, s], atol=1e-12)
        assert ((w.E + w.R * C)[:, s] - v0[:, s] < -0.19).all()
    # 대비책 F switch (off by default): births × 2 + 8/2250 per mature E ≥ 0.7 step
    assert cfg["reward"]["fallback_f"]["enabled"] is False
    cf = B.override(cfg, {"reward": {"fallback_f": {"enabled": True}}})
    _no_breed(monkeypatch)
    wf = R9World(cf, SEEDS[:2], counts=np.array([[20, 2, 6]] * 2))
    wf.E[wf.alive] = 0.9
    wf.refresh()
    wf._derive()
    mat = wf.mature.copy()
    v0 = wf.E + wf.R * wf.sb["reserve_cap"]
    _, r, done, _ = wf.step(np.full((wf.K, wf.S), B.WATCH))
    al = wf.alive
    want = 0.02 + (wf.E + wf.R * wf.sb["reserve_cap"]) - v0 + 2 * (8.0 / 2250.0) * mat
    assert np.allclose(r[al], want[al], atol=1e-12) and mat[al].any() and (~mat[al]).any()


# --------------------------------------------------------------------------- 5


def test_05_action_semantics_all_species(cfg):
    w = scene(cfg, [6, 6, 6], shelters=((55.0, 55.0, 4.0),))
    b = w.body
    rng = np.random.default_rng(44355)
    slots = [lo(w, sp) + i for sp in range(3) for i in range(6)]
    for n, s in enumerate(slots):
        th = rng.uniform(0, 2 * math.pi)
        put(w, s, (14.0 + 2.0 * (n % 9), 18.0 + 12.0 * (n // 9)), head=(math.cos(th), math.sin(th)))
    w.E[:] = 0.8
    w.refresh()
    base = copy.deepcopy(w)

    def run(a):
        x = copy.deepcopy(base)
        p0, h0 = x.pos[0].copy(), x.head[0].copy()
        x.step(np.full((1, x.S), a))
        return x, p0, h0

    for a in range(B.N_ACTIONS):
        x, p0, h0 = run(a)
        for s in slots:
            sp = int(x.slot_sp[s])
            dp = x.pos[0, s] - p0[s]
            acc = b.accel[sp]
            j = int(B.action_dir_index(a))
            if j >= 0:
                tgt = (b.walk_speed[sp] if a <= B.WALK_LAST else b.run_speed[sp] * x.run_mult[0, sp])
                v1 = min(acc, tgt)
                v2 = min(v1 + acc, tgt)
                u = B.rotate(h0[s], B.DIR8[j])
                assert np.allclose(dp, u * (v1 + v2), atol=1e-12), (a, sp)
                assert np.allclose(x.vel[0, s], u * v2, atol=1e-12)
            elif a in (B.WATCH, B.SHELTER, B.EAT):
                # S′: WATCH · SHELTER (은신처로 자동으로 뛰지 않음) · EAT (먹이 없으면 걷지 않음) = 제자리 서기, 모든 종
                assert np.array_equal(dp, np.zeros(2)), (a, sp)
                assert x._gait[0, s] == B.G_STAND
    # EAT on food stands still (any body with that food under it)
    x = copy.deepcopy(base)
    x.grass[:] = 0.5
    x.root[:] = 0.5
    p0 = x.pos[0].copy()
    x.step(np.full((1, x.S), B.EAT))
    for s in slots:
        if b.eats[int(x.slot_sp[s]), B.GRASS]:
            assert np.array_equal(x.pos[0, s], p0[s])
    # WATCH and the stand actions are 0 — they also slow a moving body by accel per step
    x = copy.deepcopy(base)
    x.vel[0, slots] = x.head[0, slots] * 0.3
    x.refresh()
    x.step(np.full((1, x.S), B.WATCH))
    for s in slots:
        sp = int(x.slot_sp[s])
        assert np.linalg.norm(x.vel[0, s]) <= max(0.3 - 2 * b.accel[sp], 0.0) + 1e-12


# --------------------------------------------------------------------------- 6


def test_06_no_trig_inside_a_step(cfg, jcfg, monkeypatch):
    w = R9World(cfg, SEEDS[:2])
    j = R9World(jcfg, [44356])

    def boom(*a, **k):
        raise AssertionError("trig call inside a step (3-9)")
    for mod, names in ((np, ("sin", "cos", "tan", "arcsin", "arccos", "arctan", "arctan2", "radians", "degrees", "deg2rad",
                             "rad2deg", "sinh", "cosh", "tanh")),
                       (math, ("sin", "cos", "tan", "asin", "acos", "atan", "atan2", "radians", "degrees"))):
        for n in names:
            monkeypatch.setattr(mod, n, boom)
    rng = np.random.default_rng(44356)
    for _ in range(30):
        w.step(rand_act(rng, w))
        j.step(rand_act(rng, j))
    w.reinit(1, 44357)
    w.E[:, :5] = -1.0
    w.R[:, :5] = 0.0
    w.step(rand_act(rng, w))                              # respawn path too
    w.decide()


# --------------------------------------------------------------------------- 7


def test_07_sums_are_sequential(cfg):
    w = R9World(cfg, SEEDS[:2])
    rng = np.random.default_rng(44357)
    for _ in range(40):
        w.step(rand_act(rng, w))
    # seq_sum = explicit left-to-right loop (and not pairwise)
    x = rng.normal(size=(5, 300))
    loop = np.zeros(5)
    for i in range(300):
        loop = loop + x[:, i]
    assert same_bits(RW.seq_sum(x, -1), loop)
    # kin summary columns of the observation = explicit slot-order loop
    o = w.obs()
    pc = w._pc
    checked = 0
    for k in range(w.K):
        ic, valid = pc["ic"][k], pc["valid"][k]
        for ii in np.nonzero(valid)[0][::5]:
            i = int(ic[ii])
            cnt, sx, sy, nrun = 0, 0.0, 0.0, 0
            for jj in np.nonzero(valid)[0]:
                if pc["perc"][k, ii, jj] and w.kin_id[k, int(ic[jj])] == w.kin_id[k, i]:
                    dsp = w.disp[k, int(ic[jj])]
                    cnt += 1
                    sx = sx + dsp[0]
                    sy = sy + dsp[1]
                    nrun += int(math.sqrt(dsp[0] * dsp[0] + dsp[1] * dsp[1]) > 0.39)
            h = w.head[k, i]
            mx, my = (sx / cnt, sy / cnt) if cnt else (0.0, 0.0)
            want = np.array([cnt / 20.0, nrun / cnt if cnt else 0.0, (mx * h[0] + my * h[1]) / 0.6, (-mx * h[1] + my * h[0]) / 0.6])
            assert same_bits(o[k, i, B.KINSUM0:B.KIN0], np.clip(want, -1, 1).astype(np.float32))
            checked += 1
    assert checked > 10
    # grass demand split: per-cell bincount = explicit slot-order loop
    K, G = w.K, w.G
    want_ = rng.uniform(0, 0.01, (K, w.S))
    ix, iy = RW._cells(w.pos, w.cell, G)
    flat = (np.arange(K)[:, None] * G * G + iy * G + ix).reshape(-1)
    bc = np.bincount(flat, weights=want_.reshape(-1), minlength=K * G * G)
    ref = np.zeros(K * G * G)
    for e, v in zip(flat, want_.reshape(-1)):
        ref[e] = ref[e] + v
    assert same_bits(bc, ref)


# --------------------------------------------------------------------------- 8


def _bite_scene(cfg, counts=(1, 1, 1), shelters=((55.0, 55.0, 4.0),), K=1, seed=44360):
    w = scene(cfg, counts, shelters=shelters, K=K, seed=seed)
    for k in range(K):
        for s in np.nonzero(w.alive[k])[0]:
            put(w, int(s), (8.0 + 0.5 * int(s), 8.0), k=k)       # park everybody in a corner row
    return w


def test_08_bite_conditions(cfg):
    d0, w0, b0 = 0, 64, 70
    assert (lo(R9World(cfg, [44361]), D_), lo(R9World(cfg, [44361]), W_), lo(R9World(cfg, [44361]), R_)) == (d0, w0, b0)

    def deer_case(dist_after=0.7, angle_deg=0.0, wolf_vel=0.18, wolf_act=B.WALK_FIRST, g_size=1.0, shelters=((55.0, 55.0, 4.0),),
                  deer_xy=None, cd=0, ref_step=1):
        """Wolf walks +x at wolf_vel for the decision; the deer stands at dist_after from the wolf's position after step ref_step."""
        w = _bite_scene(cfg, shelters=shelters)
        put(w, w0, (30.0, 30.0), head=(1, 0), vel=(wolf_vel, 0.0))
        w.g_size[0, w0] = g_size
        w.bite_cd[0, w0] = cd
        after = np.array([30.0 + ref_step * wolf_vel, 30.0])
        th = math.radians(angle_deg)
        xy = after + dist_after * np.array([math.cos(th), math.sin(th)]) if deer_xy is None else np.asarray(deer_xy)
        put(w, d0, xy)
        w.refresh()
        _, _, done, info = w.step(acts(w, **{f"s{w0}": wolf_act}))
        return w, done[0, d0], info

    w, dead, info = deer_case()
    assert dead and info["dead_cause"][0, d0] == RW.CAUSE_BITE and info["killer"][0, d0] == w.uid[0, w0]
    assert w.bite_cd[0, w0] == 8 - 1                       # bite cooldown 8, one step of it spent in the 2nd step
    assert not deer_case(angle_deg=70.0)[1]                # outside the head cone (dot 0.34 < 0.5)
    assert deer_case(angle_deg=50.0)[1]                    # inside (dot 0.64)
    assert not deer_case(wolf_vel=0.0, wolf_act=B.WATCH)[1]    # standing wolf does not bite
    assert not deer_case(wolf_vel=0.0, wolf_act=B.SHELTER)[1]  # wolf SHELTER = stand
    assert not deer_case(cd=5)[1]                          # cooldown
    # bite distance = 1.0 × g_size × growth (measured at step 2: at step 1 the deer is 0.18 farther, out of reach)
    assert deer_case(dist_after=0.79, g_size=0.8, ref_step=2)[1] and not deer_case(dist_after=0.81, g_size=0.8, ref_step=2)[1]
    assert deer_case(dist_after=0.99, ref_step=2)[1] and not deer_case(dist_after=1.01, ref_step=2)[1]
    w = scene(cfg, [1, 1, 0])
    w.born[0, w0] = float(w.t[0])                          # newborn wolf: growth 0.75 → reach 0.75
    w.refresh()
    assert np.isclose(w.sb["bite_r"][0, w0] * w.bscale[0, w0], 0.75)
    # prey inside a shelter is not bitten: deer 0.2 inside the edge, wolf held at r + 0.5, 0.7 apart, approaching
    c, r = np.array([40.0, 30.0]), 3.0
    w = _bite_scene(cfg, shelters=((40.0, 30.0, 3.0),))
    put(w, w0, c - np.array([r + 0.5, 0.0]), head=(1, 0), vel=(0.18, 0.0))
    put(w, d0, c - np.array([r - 0.2, 0.0]))
    w.refresh()
    _, _, done, _ = w.step(acts(w, **{f"s{w0}": B.WALK_FIRST}))
    assert not done[0, d0]
    w = _bite_scene(cfg, shelters=((55.0, 55.0, 4.0),))                  # same geometry without the shelter → bitten
    put(w, w0, c - np.array([r + 0.5, 0.0]) - np.array([0.18, 0.0]), head=(1, 0), vel=(0.18, 0.0))
    put(w, d0, c - np.array([r - 0.2, 0.0]))
    w.refresh()
    _, _, done, _ = w.step(acts(w, **{f"s{w0}": B.WALK_FIRST}))
    assert done[0, d0]


class Probe(R9World):
    """Records per-step move outputs (contact displacement, knock/push masks) for the contact tests."""

    def _move(self):
        pre = dict(vel=self.vel.copy(), alive=self.alive.copy(), act=self.act.copy(), lock=self.stam_lock.copy(),
                   E=self.E.copy(), hp=self.hp.copy(), spd=self.spd_scale.copy(), knock=self.knock_left.copy())
        super()._move()
        self.trace.append(dict(pre=pre, contact=self._contact.copy(), knocked=self._knocked.copy(), pushed=self._pushed.copy(),
                               vfree=self._vel_free.copy(), vel=self.vel.copy(), wall=self._wall.copy(),
                               tspeed=self._tspeed.copy(), gait=self._gait.copy()))


def test_08_boar_counter_wound_and_wolf_order(cfg):
    w0, b0 = 64, 70
    ct = cfg["body_common"]["counter"]
    regen = 0.25 / 900

    def boar_case(boar_head=(-1.0, 0.0), juvenile=False, hp=1.0):
        c = B.override(cfg, {"world": {"shelters": {"fixed": [[55.0, 55.0, 4.0]]}}})
        w = Probe.__new__(Probe)
        w.trace = []
        R9World.__init__(w, c, [44362], counts=np.array([[1, 1, 1]]))
        a = w.alive
        w.vel[:] = 0
        w.g_size[a] = 1.0
        w.g_speed[a] = 1.0
        w.hp[:] = 1.0
        w.E[a] = 0.6
        w.born[:] = -3.0 * w.sb["maturity"]
        w.next_birth[:] = 1e9
        put(w, 0, (8.0, 8.0))
        put(w, w0, (30.0, 30.0), head=(1, 0), vel=(0.18, 0.0))
        put(w, b0, (30.18 + 0.7, 30.0), head=boar_head)
        w.hp[0, b0] = hp
        if juvenile:
            w.born[0, b0] = 0.0
        w.refresh()
        w.trace.clear()
        _, _, done, info = w.step(acts(w, **{f"s{w0}": B.WALK_FIRST}))
        return w, done, info

    # frontal adult boar with HP ≥ 0.35 → counter
    w, done, info = boar_case()
    assert not done.any()
    assert np.isclose(w.hp[0, w0], 1.0 - ct["damage"] * 1.0 * 1.0 + 2 * regen, atol=1e-12)
    assert np.isclose(w.hp[0, b0], 1.0 - ct["self_damage"] + 2 * regen, atol=1e-12)
    assert w.bite_cd[0, w0] == ct["nobite_steps"] - 1 and w.st["bites"][0, R_, RW.BITE_COUNTER] == 1
    assert np.allclose(w.knock_dir[0, w0], [-1.0, 0.0])
    # knock: 0.25 per step for 4 steps (steps 2..5), then nothing — contact displacement only
    for _ in range(3):
        w.step(acts(w))
    kn = [tr["knocked"][0, w0] for tr in w.trace]
    assert kn == [False, True, True, True, True, False, False, False]
    for tr in w.trace[1:5]:
        assert np.allclose(tr["contact"][0, w0], [-ct["knock_step"], 0.0], atol=1e-12)
    for tr in w.trace[5:]:
        assert np.allclose(tr["contact"][0, w0], 0.0, atol=1e-12)
    # from behind (wolf not in the boar's front ±75.5°) → boar HP − 0.45, no counter
    w, done, _ = boar_case(boar_head=(1.0, 0.0))
    assert not done.any() and np.isclose(w.hp[0, b0], 1.0 - 0.45 + 2 * regen, atol=1e-12) and np.isclose(w.hp[0, w0], 1.0)
    assert w.st["bites"][0, R_, RW.BITE_WOUND] == 1
    # frontal but HP < 0.35 → no counter: the 0.45 loss kills it
    w, done, info = boar_case(hp=0.34)
    assert done[0, b0] and w.st["bites"][0, R_, RW.BITE_COUNTER] == 0 and np.isclose(w.hp[0, w0], 1.0)
    # juvenile (age 0, mass ratio 0.12) from behind → dies in one bite
    w, done, info = boar_case(boar_head=(1.0, 0.0), juvenile=True)
    assert done[0, b0] and info["dead_cause"][0, b0] == RW.CAUSE_BITE
    # two wolves able to bite the same deer in the same step: the per-step shuffled order lets either win
    wins = set()
    K = 24
    w = _bite_scene(cfg, counts=(1, 2, 0), K=K, seed=44364)
    for k in range(K):
        put(w, w0, (30.0, 30.0), head=(1, 0), vel=(0.18, 0.0), k=k)
        put(w, w0 + 1, (30.36, 30.36 + 0.7), head=(0, -1), vel=(0.0, -0.18), k=k)
        put(w, 0, (30.18 + 0.18, 30.0 + 0.18 + 0.0), k=k)
    w.refresh()
    _, _, done, info = w.step(acts(w, **{f"s{w0}": B.WALK_FIRST, f"s{w0 + 1}": B.WALK_FIRST}))
    assert done[:, 0].all()
    for k in range(K):
        wins.add(int(np.nonzero(w.uid[k] == info["killer"][k, 0])[0][0]))
    assert wins == {w0, w0 + 1}


# --------------------------------------------------------------------------- 9


def test_09_carcass(cfg):
    w0 = 64
    cc = cfg["body_common"]["carcass"]
    # deer killed → carcass at its position, meat = 60 × 1 × 0.6 / 9 (adult, g_size 1), kin of the deer, then decays
    w = _bite_scene(cfg)
    put(w, w0, (30.0, 30.0), head=(1, 0), vel=(0.18, 0.0))
    put(w, 0, (30.88, 30.0))
    w.refresh()
    _, _, done, _ = w.step(acts(w, **{f"s{w0}": B.WALK_FIRST}))
    assert done[0, 0]
    c = int(np.nonzero(w.carc_ok[0])[0][0])
    m0 = 60.0 * 1.0 * cc["meat_frac"] / cc["kg_per_unit"]
    assert np.allclose(w.carc_pos[0, c], [30.88, 30.0]) and np.isclose(w.carc_meat0[0, c], m0)
    assert w.carc_kin[0, c] == w.kin_id[0, 0] and w.carc_sp[0, c] == D_
    # decay 1/1350 of the first meat per step (2 steps passed: death step and the next)
    assert np.isclose(w.carc_meat[0, c], m0 - 2 * m0 / cc["decay_steps"], atol=1e-12)

    def eat_scene(kin_sp, eaters):
        w = scene(cfg, [2, 4, 1])
        for i, s in enumerate(np.nonzero(w.alive[0])[0]):
            put(w, int(s), (6.0 + 3.0 * i, 6.0))
        p = np.array([30.0, 30.0])
        w._add_carcass(0, p, 4.0, int(w.kin_perm[0, kin_sp]), kin_sp, 999, 0)
        for s, dxy in eaters:
            put(w, s, p + np.asarray(dxy))
        w.E[w.alive] = 0.5
        w.refresh()
        e0 = w.E.copy()
        w._derive()
        dr = w.sb["drain"] * w._gait_drain[B.G_STAND] * w.maint
        w.step(np.full((1, w.S), B.EAT))
        return w, e0, dr

    wolves = [w0 + i for i in range(4)]
    w, e0, dr = eat_scene(D_, [(wolves[0], (0.3, 0)), (wolves[1], (0, 0.5)), (wolves[2], (-0.7, 0)), (wolves[3], (0, -0.9))])
    rate = cfg["species"]["wolf"]["eat_rate"]["meat"]
    for s in wolves[:3]:                                   # 3 places, nearest first
        assert np.isclose(w.E[0, s] - e0[0, s], 2 * (rate - dr[0, s]), atol=1e-12)
    assert np.isclose(w.E[0, wolves[3]] - e0[0, wolves[3]], -2 * dr[0, wolves[3]], atol=1e-12)
    # deer does not eat meat; boar does (no root/grass under it)
    b0 = 70
    w, e0, dr = eat_scene(D_, [(0, (0.3, 0)), (b0, (-0.3, 0))])
    assert w.E[0, 0] < e0[0, 0]
    br = cfg["species"]["boar"]
    assert np.isclose(w.E[0, b0] - e0[0, b0], 2 * (br["eat_rate"]["meat"] * br["e_per_unit"]["meat"] - dr[0, b0]), atol=1e-12)
    # same kin: wolves do not eat a wolf carcass, the boar does
    w, e0, dr = eat_scene(W_, [(wolves[0], (0.3, 0)), (b0, (-0.3, 0))])
    assert w.E[0, wolves[0]] < e0[0, wolves[0]] and w.E[0, b0] > e0[0, b0]
    # sensing: eye ∪ nose only — a carcass behind a wolf beyond its nose is not in food_density, within the nose it is
    for dist_, sensed in ((8.0, False), (4.0, True)):
        w = scene(cfg, [1, 1, 0])
        put(w, 0, (5.0, 5.0))
        put(w, w0, (30.0, 30.0), head=(1, 0))
        w._add_carcass(0, np.array([30.0 - dist_, 30.0]), 4.0, int(w.kin_perm[0, D_]), D_, 999, 0)
        w.refresh()
        fd = w.obs()[0, w0, B.O_FOOD_DENSITY]
        want = (4.0 / 441.0) / cfg["species"]["wolf"]["food_density_ref"] if sensed else 0.0
        assert np.isclose(fd, min(want, 1.0), atol=1e-6), (dist_, fd)
    # in front within the eye (20 units, 250°) → sensed
    w = scene(cfg, [1, 1, 0])
    put(w, 0, (5.0, 5.0))
    put(w, w0, (30.0, 30.0), head=(1, 0))
    w._add_carcass(0, np.array([45.0, 30.0]), 4.0, int(w.kin_perm[0, D_]), D_, 999, 0)
    w.refresh()
    assert w.obs()[0, w0, B.O_FOOD_DENSITY] > 0


# --------------------------------------------------------------------------- 10


def test_10_stamina_wound_weak(cfg):
    c = B.override(cfg, {"world": {"shelters": {"fixed": [[55.0, 55.0, 4.0]]}}})
    w = Probe.__new__(Probe)
    w.trace = []
    R9World.__init__(w, c, [44366], counts=np.array([[1, 1, 1]]))
    a = w.alive
    w.g_size[a] = 1.0
    w.g_speed[a] = 1.0
    w.E[a] = 0.9
    w.R[a] = 1.0
    w.born[:] = -3.0 * w.sb["maturity"]
    w.next_birth[:] = 1e9
    w.refresh()
    b = w.body
    d0 = 0
    lock_step = None
    steps = 0
    while lock_step is None and steps < 200:
        w.trace.clear()
        w.step(acts(w, default=B.WATCH, s0=B.RUN_FIRST + (4 if (steps // 20) % 2 else 0)))
        steps += 2
        if w.stam_lock[0, d0]:
            lock_step = steps
    assert lock_step is not None and abs(lock_step - b.stam_run_steps[D_]) <= 2       # 90 steps of running (± decision)
    assert w.stam[0, d0] <= 0.15 + 1e-9
    w.trace.clear()
    w.step(acts(w, default=B.WATCH, s0=B.RUN_FIRST))
    assert np.isclose(w.trace[-1]["tspeed"][0, d0], b.walk_speed[D_] * w.spd_scale[0, d0], atol=1e-12)   # locked run = walk
    assert w.trace[-1]["gait"][0, d0] == B.G_WALK
    n = 0
    while w.stam_lock[0, d0] and n < 200:
        w.step(acts(w))
        n += 2
    assert w.stam[0, d0] >= 0.55 - 1e-9 and abs(n - b.stam_recover_steps[D_]) <= 3
    # wound (HP 0.5 → × 0.75) and weak (E < 0.1 → × 0.75)
    w.hp[0, 64] = 0.5
    w.E[0, 70] = 0.05
    w.refresh()
    w.trace.clear()
    w.step(acts(w, s64=B.WALK_FIRST, s70=B.WALK_FIRST))
    t = w.trace[0]
    assert np.isclose(t["tspeed"][0, 64], b.walk_speed[W_] * 0.75 * t["pre"]["spd"][0, 64], atol=1e-12)
    assert np.isclose(t["tspeed"][0, 70], b.walk_speed[R_] * 0.75 * t["pre"]["spd"][0, 70], atol=1e-12)
    # growth: a newborn walks at g_speed × (0.8 + 0.2 × 0.75)
    w.born[0, 0] = float(w.t[0])
    w.E[0, 0] = 0.9
    w.refresh()
    w.trace.clear()
    w.step(acts(w, s0=B.WALK_FIRST))
    assert np.isclose(w.trace[0]["tspeed"][0, 0], b.walk_speed[D_] * (0.8 + 0.2 * 0.75), atol=1e-9)


# --------------------------------------------------------------------------- 11


def test_11_shelters(cfg):
    w = R9World(cfg, list(range(44367, 44375)))
    bad = []
    inside = np.zeros(3, dtype=np.int64)

    def hook(wd, dead, extra):
        _, e = RW._shelter_edge(wd.pos, wd.cov_c, wd.cov_r, wd.cov_ok)
        for s in range(3):
            m = wd.alive & (wd.slot_sp == s)
            if s == W_:
                for ci in range(wd.C):
                    d = np.sqrt(((wd.pos - wd.cov_c[:, ci][:, None, :]) ** 2).sum(-1))
                    r = (wd.cov_r[:, ci] + cfg["body_common"]["shelter_push"])[:, None]
                    if (m & wd.cov_ok[:, ci][:, None] & (d < r - 1e-9)).any():
                        bad.append(int(wd.t[0]))
            else:
                inside[s] += int((m & (e <= 0.0)).sum())
    w.step_hook = hook
    rng = np.random.default_rng(44358)
    for i in range(300):
        a = rand_act(rng, w)
        a[:, :16] = B.SHELTER
        a[:, lo(w, W_):lo(w, R_)] = np.where(rng.random((w.K, 6)) < 0.5, B.SHELTER, a[:, lo(w, W_):lo(w, R_)])
        a[:, lo(w, R_):lo(w, R_) + 4] = B.SHELTER
        w.step(a)
    assert not bad
    assert inside[D_] > 0 and inside[R_] > 0
    assert w.st["bites"].sum() > 0 or w.st["deaths"].sum() > 0


# --------------------------------------------------------------------------- 12


def test_12_respawn(cfg):
    K = 8
    w = R9World(cfg, list(range(44376, 44376 + K)), counts=np.array([[24, 1, 4]] * K))
    w._derive()
    dr = w.sb["drain"] * w._gait_drain[B.G_STAND] * w.maint
    kill = np.zeros((K, w.S), dtype=bool)
    kill[:, 2:14] = True                                    # 12 deer per world
    kill[:, lo(w, R_)] = True                               # one boar per world
    w.E = np.where(kill, 1.5 * dr, w.E)                     # alive after step 1, starves at step 2 (no one moves: all WATCH)
    w.R = np.where(kill, 0.0, w.R)
    w.mem[:] = 0.5
    # a pending pair that points at a dying deer (life must not keep it)
    lf = w.life
    lf.pair_on[0, 0] = True
    lf.pair_a[0, 0], lf.pair_b[0, 0] = 2, 20
    lf.pair_ua[0, 0], lf.pair_ub[0, 0] = w.uid[0, 2], w.uid[0, 20]
    lf.pair_due[0, 0] = 1e9
    lf.pair_sp[0, 0] = D_
    w.mating[0, [2, 20]] = True
    w.refresh()
    old_max = w.uid.max(1)
    _, r, done, info = w.step(np.full((K, w.S), B.WATCH))
    assert (done == kill).all() and (info["respawned"] == kill).all()
    assert (w.alive.sum(1) == w.counts.sum(1)).all()
    forms = w._resp_form
    nb_n = far_n = 0
    for k in range(K):
        for s in np.nonzero(kill[k])[0]:
            assert w.uid[k, s] > old_max[k]
            assert (w.mem[k, s, :] == 0).all() and (w.mem[k, :, s] == 0).all()
            sp = int(w.slot_sp[s])
            if forms[k, s] == RW.RESP_NEWBORN:
                nb_n += 1
                assert w.born[k, s] == w.t[k] - 1 and w.E[k, s] == 0.4 and w.R[k, s] == 0.0
                same = w.alive[k] & (w.slot_sp == sp) & (np.arange(w.S) != s)
                d = np.sqrt(((w.pos[k][same] - w.pos[k, s]) ** 2).sum(-1))
                assert ((d >= 1.1 - 1e-9) & (d <= 2.5 + 1e-9)).any()
            else:
                far_n += 1
                assert forms[k, s] == RW.RESP_FAR
                oth = w.alive[k] & (w.slot_sp != sp) & ~(kill[k] & (np.arange(w.S) > s))   # later respawns came after it
                d = np.sqrt(((w.pos[k][oth] - w.pos[k, s]) ** 2).sum(-1)).min()
                if sp == D_:
                    assert d >= 20.0 - 1e-9                 # few other-species individuals: a candidate always exists here
                assert w.E[k, s] == cfg["randomize"]["start_energy"]
                assert 0.0 <= w.R[k, s] <= 1.0
                assert RW._shelter_edge(w.pos[k:k + 1, s:s + 1], w.cov_c[k:k + 1], w.cov_r[k:k + 1], w.cov_ok[k:k + 1])[1][0, 0] > 0
    frac = nb_n / (nb_n + far_n)
    assert 0.08 <= frac <= 0.35, frac
    # references cleared: no live pair points at a respawned slot; the partner's mating flag is off
    on = lf.pair_on
    for k in range(K):
        for p in np.nonzero(on[k])[0]:
            assert not kill[k, lf.pair_a[k, p]] and not kill[k, lf.pair_b[k, p]]
    assert not w.mating[0, 20]
    # ID only increases
    assert (w.next_uid > w.uid.max(1)).all()


# --------------------------------------------------------------------------- 19


def test_19_speed_set_and_contact(cfg):
    c = cfg
    w = Probe.__new__(Probe)
    w.trace = []
    R9World.__init__(w, c, SEEDS[:4])
    b = w.body
    rng = np.random.default_rng(44359)
    sp_of = w.slot_sp.astype(np.int64)
    n_knock = n_push = n_wall = 0
    for i in range(250):
        w.trace.clear()
        a = rand_act(rng, w)
        if i % 3 == 0:
            a[:, lo(w, W_):lo(w, R_)] = rng.integers(B.RUN_FIRST, B.RUN_LAST + 1, (w.K, 6))
        w.step(a)
        for tr in w.trace:
            pre = tr["pre"]
            al = pre["alive"]
            m = pre["spd"] * (0.5 + 0.5 * pre["hp"]) * np.where(pre["E"] < b.weak_e[sp_of], b.weak_speed[sp_of], 1.0)
            walk = b.walk_speed[sp_of] * m
            run = b.run_speed[sp_of] * w._rmult * m
            ts = tr["tspeed"]
            ok = np.isclose(ts, 0.0, atol=0) | np.isclose(ts, walk, rtol=1e-12, atol=0) | np.isclose(ts, run, rtol=1e-12, atol=0)
            assert ok[al].all()
            runact = (pre["act"] >= B.RUN_FIRST) & (pre["act"] <= B.RUN_LAST)
            assert np.isclose(ts[al & runact & pre["lock"]], walk[al & runact & pre["lock"]], rtol=1e-12).all()
            dv = np.sqrt(((tr["vfree"] - pre["vel"]) ** 2).sum(-1))
            acc = b.accel[sp_of]
            assert (dv[al] <= np.broadcast_to(acc, dv.shape)[al] + 1e-12).all()
            vf = np.sqrt((tr["vfree"] ** 2).sum(-1))
            v0 = np.sqrt((pre["vel"] ** 2).sum(-1))
            assert (vf[al] <= np.maximum(v0, ts)[al] + 1e-12).all()
            # wall slide only removes blocked components of the free velocity
            wl = tr["wall"]
            assert np.array_equal(np.where(wl, 0.0, tr["vel"] - tr["vfree"])[al], np.zeros_like(tr["vel"])[al])
            # contact displacement exists only with a knock or a shelter push
            cn = np.sqrt((tr["contact"] ** 2).sum(-1))
            free_ = al & ~tr["knocked"] & ~tr["pushed"]
            assert (cn[free_] <= 1e-12).all()
            kn = al & tr["knocked"] & ~tr["pushed"]
            assert (cn[kn] <= cfg["body_common"]["counter"]["knock_step"] + 1e-12).all()
            n_knock += int(tr["knocked"].sum())
            n_push += int(tr["pushed"].sum())
            n_wall += int(wl.any(-1).sum())
    assert n_push > 0 and n_wall > 0
    # the scene with a guaranteed counter covers the knock path (test 8); here we only require the rule held whenever it fired
    assert n_knock >= 0


# --------------------------------------------------------------------------- 20


def test_20_grass_matches_r8(cfg):
    """Copied grass generator, regrowth and the cell demand split are bit-identical to R8World (same seed, same shelter layout)."""
    covers = [[15.0, 15.0], [45.0, 15.0], [15.0, 45.0], [45.0, 45.0]]
    n = 16
    r8c = RW8.load_r8_config(R8CFG)
    r8c = RW8.override(r8c, {"wolves": {"count": [0, 0]}, "beasts": {"count": [0, 0]}, "world": {"n_deer": n, "covers": covers, "cover_r": 6.0},
                             "food": {"regen_base": cfg["food"]["grass"]["regen_base"], "regen_mult": [1.0, 1.0],
                                      "eat_rate": cfg["species"]["deer"]["eat_rate"]["grass"]},
                             "deer": {"repro_threshold": 2.0}})
    r9c = B.override(cfg, {"world": {"shelters": {"fixed": [c + [6.0] for c in covers]}},
                           "randomize": {"grass_regen_mult": [1.0, 1.0]},
                           "food": {"train_grass_total": None}})       # S′ N 맞춤(용량 합 70)은 끄고 복사한 생성기만 비교
    seeds = [44380, 44381, 44382]
    a = RW8.R8World(r8c, seeds)
    b = R9World(r9c, seeds, counts=np.array([[n, 0, 0]] * len(seeds)))
    assert same_bits(b.cover_cell, np.broadcast_to(a.cover_cell, b.cover_cell.shape))
    assert same_bits(b.grass_cap, a.food_cap) and same_bits(b.grass, a.food) and same_bits(b.grass_regen, a.regen)
    # same deer bodies on food cells (crowded cells make demand > food), both stand and eat one step
    rng = np.random.default_rng(44360)
    for k in range(len(seeds)):
        cells = np.argwhere(a.food[k] >= 0.07)
        pick = cells[rng.choice(len(cells), 4, replace=False)]
        a.food[k][tuple(pick[:2].T)] = 0.07                   # 2 cells × 6 deer × 0.012 > 0.07: frac < 1
        xy = np.repeat((pick[:, ::-1] + 0.5) * 2.0, [6, 6, 2, 2], 0) + rng.uniform(-0.4, 0.4, (n, 2))
        a.pos[k] = xy
        b.pos[k, :n] = xy
    b.grass[:] = a.food
    E0 = rng.uniform(0.2, 0.95, (len(seeds), n))
    R0 = rng.uniform(0.0, 1.0, (len(seeds), n))
    a.E[:] = E0
    a.R[:] = R0
    b.E[:, :n] = E0
    b.R[:, :n] = R0
    b.g_size[:, :n] = 1.0
    b.g_speed[:, :n] = 1.0
    b.refresh()
    a.act[:] = RW8.EAT
    b.act[:] = B.WATCH
    b.act[:, :n] = B.EAT
    g0 = a.food.copy()
    a._phys()
    b._phys()
    assert same_bits(b.pos[:, :n], a.pos)                    # everybody stood (food ≥ eat_min under every deer)
    assert same_bits(b.grass, a.food) and same_bits(b.E[:, :n], a.E) and same_bits(b.R[:, :n], a.R)
    assert (g0 - b.grass > 0.06).any()                        # the crowded cells were emptied (demand > food → frac < 1)
    # regrowth alone (nobody eats) for many steps
    a.act[:] = RW8.WATCH
    b.act[:] = B.WATCH
    for _ in range(40):
        a._phys()
        b._phys()
        assert same_bits(b.grass, a.food)
    assert (b.grass < b.grass_cap).any()


# --------------------------------------------------------------------------- 22


def test_22_gathered_equals_full_table(cfg, jcfg):
    for c, seeds, steps in ((cfg, [44383, 44384, 44385], 60), (jcfg, [44386], 12)):
        g = R9World(c, seeds)
        f = R9World(c, seeds, pairs_full=True)
        assert same_bits(g.obs(), f.obs())
        rng = np.random.default_rng(44361)
        for _ in range(steps):
            act = rand_act(rng, g)
            og, rg, dg, _ = g.step(act)
            of, rf, df, _ = f.step(act)
            assert same_bits(og, of) and same_bits(rg, rf)
            idx, n = g.alive_index()
            for k in range(g.K):
                row = idx[k, :n[k]]
                assert (np.diff(row) > 0).all() and (idx[k, n[k]:] == -1).all()     # gathered order = slot order
        for nme in ("pos", "vel", "E", "R", "mem"):
            al = g.alive
            if nme == "mem":
                m = al[:, :, None] & al[:, None, :]
                assert same_bits(g.mem[m], f.mem[m])
            else:
                assert same_bits(getattr(g, nme), getattr(f, nme)), nme
        assert g.alive.sum() < g.K * g.S                     # empty slots exist (otherwise gathering is trivial)


def _rule_world(c, seeds, counts=None, **kw):
    BR = RW.BR
    w = R9World(c, seeds, counts=counts, record=True, **kw)
    for k in range(w.K):
        for s, n in ((D_, "RULE_DEER"), (W_, "RULE_WOLF"), (R_, "RULE_BOAR")):
            w.set_controller(k, s, BR.Controller(BR.make_rule(n, c), stochastic=False, label=n))
    return w


def test_22b_gathered_bite_and_hunts_equal_full_table(cfg, jcfg):
    """Fix 단계: `_bite` (ready biters × gathered alive slots) and `_track_hunts` (sparse eligible pairs) equal their full
    (K, nb, S) reference paths bit for bit — world state, bite/death/hunt event lists — in a train world with many wolves and in
    the L0 judge variant (64 wolf slots × 1,024 slots) with rule brains, so bites, counters, kills and segments really happen."""
    L0 = B.override(jcfg, jcfg["judge"]["variants"]["L0"])
    counts = np.array([[64, 6, 14], [48, 6, 8], [0, 6, 14]], dtype=np.int64)   # world 3: no deer — wolves bite boar
    out = []
    for c, seeds, cnt, n_dec in ((cfg, [44387, 44388, 44389], counts, 300), (L0, [44390], None, 120)):
        g = _rule_world(c, seeds, cnt)
        f = _rule_world(c, seeds, cnt, pairs_full=True)
        for w in (g, f):                                   # hungry wolves (judge wolves start full and would not hunt yet)
            ws = slice(lo(w, W_), lo(w, R_))
            w.E[:, ws] = np.where(w.alive[:, ws], 0.5, w.E[:, ws])
            w.refresh()
        for _ in range(n_dec):
            ag, af_ = g.decide(), f.decide()
            assert same_bits(ag, af_)
            og, rg, _, _ = g.step(ag)
            of, rf, _, _ = f.step(af_)
            assert same_bits(og, of) and same_bits(rg, rf)
        g.flush_hunts()
        f.flush_hunts()
        for nme in ("pos", "vel", "hp", "E", "R", "alive", "uid", "bite_cd", "knock_left"):
            assert same_bits(getattr(g, nme), getattr(f, nme)), nme
        for ev in ("bites", "deaths", "hunts", "respawns", "births"):
            assert g.events[ev] == f.events[ev], ev
        out.append(([e["outcome"] for e in g.events["bites"]], len(g.events["hunts"])))
    tr, j0 = out
    assert tr[0].count("kill") >= 3 and tr[1] >= 3, tr
    assert tr[0].count("counter") + tr[0].count("wound") >= 1, tr[0]        # boar bites happen too
    assert j0[1] >= 1 and len(j0[0]) >= 1, j0                                # the L0 run has bites and segments


def test_22c_hunt_previous_distance_follows_the_target_uid(cfg):
    """Fix 단계 (검토 low): a slot whose individual changed between decisions has no previous distance — a new individual that
    appears closer than the old one does not start an approach segment by itself; the next real approach still counts."""
    c = B.override(cfg, {"world": {"shelters": {"fixed": [[55.0, 55.0, 4.0]]}}})
    w = R9World(c, [44392], counts=np.array([[1, 1, 0]]), record=True)
    a = w.alive
    w.vel[:] = 0.0
    w.g_size[a] = 1.0
    w.g_speed[a] = 1.0
    w.E[a] = 0.6
    w.born[:] = -3.0 * w.sb["maturity"]
    w.next_birth[:] = 1e9
    w0 = lo(w, W_)
    put(w, w0, (20.0, 30.0), head=(1, 0))
    put(w, 0, (34.0, 30.0))
    w.refresh()
    w.step(acts(w))                                   # decision 1: stores the wolf → deer distance (14)
    w.step(acts(w))
    assert np.isfinite(w._h_prev[0, 0, 0]) and w._h_puid[0, 0, 0] == w.uid[0, 0]
    # the deer slot gets a new individual 5 units closer (as a train respawn inside a decision would) — nobody moved toward it
    w.uid[0, 0] = int(w.next_uid[0])
    w.next_uid[0] += 1
    put(w, 0, (29.0, 30.0))
    w.refresh()
    w.step(acts(w))
    assert not w._h_on[0, 0, 0] and w._h_close[0, 0, 0] == 0           # before the fix: (14 − 9) / 2 > 0.1 → a closing decision
    assert w._h_puid[0, 0, 0] == w.uid[0, 0]
    for _ in range(3):                                   # a real approach afterwards closes normally
        w.step(acts(w, **{f"s{w0}": B.WALK_FIRST}))
    assert w._h_on[0, 0, 0] and w._h_close[0, 0, 0] >= 2


# --------------------------------------------------------------------------- 23


class Ledger(R9World):
    def _eat(self):
        g0, r0 = self.grass.copy(), self.root.copy()
        out = super()._eat()
        for f, a0, a1 in ((B.GRASS, g0, self.grass), (B.ROOT, r0, self.root)):
            taken = (a0 - a1).reshape(self.K, -1)
            assert (taken >= -1e-15).all()
            eaten = self._gain_u[..., f]
            for k in range(self.K):
                assert np.isclose(RW.seq_sum(taken[k]), RW.seq_sum(eaten[k]), rtol=1e-12, atol=1e-15)
        self.n_eat_checks += 1
        return out


def test_23_ledgers(cfg, jcfg):
    w = Ledger.__new__(Ledger)
    w.n_eat_checks = 0
    R9World.__init__(w, cfg, [44387, 44388, 44389, 44390])
    rng = np.random.default_rng(44362)
    dead_n = resp_n = 0
    for _ in range(250):
        a = rand_act(rng, w)
        a[:, :lo(w, W_)] = np.where(rng.random((w.K, lo(w, W_))) < 0.5, B.EAT, a[:, :lo(w, W_)])
        a[:, lo(w, R_):] = np.where(rng.random((w.K, w.S - lo(w, R_))) < 0.5, B.EAT, a[:, lo(w, R_):])
        # S′: EAT 는 걷지 않으므로 고기 길을 지나가려면 늑대가 관측으로 사체에 간다 — 발밑(food_here) EAT, 느낀 사체(food_dir) 쪽 걷기
        ow = w.obs()[:, lo(w, W_):lo(w, R_)]
        fdw = ow[..., B.SL_FOOD_DIR]
        a[:, lo(w, W_):lo(w, R_)] = np.where(ow[..., B.O_FOOD_HERE] > 0, B.EAT,
                                             np.where(fdw.max(-1) > 0, B.WALK_FIRST + fdw.argmax(-1), a[:, lo(w, W_):lo(w, R_)]))
        _, _, done, info = w.step(a)
        assert (w.alive.sum(1) == w.counts.sum(1)).all()
        dead_n += int(done.sum())
        resp_n += int(info["respawned"].sum())
    assert w.n_eat_checks == 500
    st = w.st
    assert st["deaths"].sum() == st["respawns"].sum() and st["deaths"].sum() > 0
    created = st["meat_created"].sum(1)
    eaten = st["eaten_units"][:, :, B.MEAT].sum(1)
    left = np.where(w.carc_ok, w.carc_meat, 0.0).sum(1)
    assert np.allclose(created, eaten + st["meat_decayed"] + left + st["meat_overflow_lost"], atol=1e-9)
    assert (eaten > 0).any()
    # judge world: population change = births − deaths; blocked opportunities add up by reason
    j = R9World(jcfg, [44391])
    n0 = j.alive.sum()
    rng = np.random.default_rng(44363)
    for _ in range(150):
        j.step(rand_act(rng, j))
    assert j.alive.sum() - n0 == j.st["newborns"].sum() - j.st["deaths"].sum()
    ls = L.life_stats(j.life)
    assert (ls["blocked"] >= 0).all() and ls["blocked"].shape[-1] == len(L.BLOCK_NAMES)
    assert ((ls["content_block_share"] >= 0) & (ls["content_block_share"] <= 1)).all()


# --------------------------------------------------------------------------- VecEnv 계약 (9절) — 세계 쪽만


def test_learner_index_and_counts_override(cfg):
    lc = cfg["learner_counts"]["deer"]
    K = 6
    cnt = np.full((K, 3), -1)
    cnt[:, D_] = [lc[k % len(lc)] for k in range(K)]
    w = R9World(cfg, list(range(44392, 44392 + K)), counts=cnt)
    ek, es = w.learner_index(D_)
    assert len(ek) == sum(lc[k % len(lc)] for k in range(K))
    assert (np.diff(ek) >= 0).all() and all((es[ek == k] == np.arange(cnt[k, D_])).all() for k in range(K))
    assert w.alive[ek, es].all()
    for k in range(K):
        assert w.alive[k, :lo(w, W_)].sum() == cnt[k, D_]
    # other species counts come from the seed and stay in the configured ranges
    for sp, n in ((W_, "wolf"), (R_, "boar")):
        assert ((w.counts[:, sp] >= cfg["counts"][n][0]) & (w.counts[:, sp] <= cfg["counts"][n][1])).all()
    # decide(): learner flat actions land on the learner slots, other blocks default to WATCH
    la = np.full(len(ek), B.RUN_FIRST)
    a = w.decide(learner_sp=D_, learner_actions=la)
    assert (a[ek, es] == B.RUN_FIRST).all() and (a[:, lo(w, W_):] == B.WATCH).all()
    wp = w.world_params(0)
    assert wp["counts"]["deer"] == cnt[0, D_] and len(wp["shelters"]) == w.n_cov[0]


# --------------------------------------------------------------------------- 숨은 기록 (8-2·8-3·8-4 원자료)


def test_hidden_records_scripted_stalk(cfg):
    """A wolf walks straight at a standing deer from 8 units: one approach segment (walk, > 4 closing decisions) ends by the kill;
    the bite and the death are recorded with the wolf's uid."""
    c = B.override(cfg, {"world": {"shelters": {"fixed": [[55.0, 55.0, 4.0]]}}})
    w = R9World(c, [44393], counts=np.array([[1, 1, 0]]), record=True)
    a = w.alive
    w.vel[:] = 0.0
    w.g_size[a] = 1.0
    w.g_speed[a] = 1.0
    w.E[a] = 0.6
    w.born[:] = -3.0 * w.sb["maturity"]
    w.next_birth[:] = 1e9
    w0 = lo(w, W_)
    put(w, w0, (20.0, 30.0), head=(1, 0))
    put(w, 0, (28.0, 30.0))
    w.refresh()
    for _ in range(40):
        _, _, done, info = w.step(acts(w, **{f"s{w0}": B.WALK_FIRST}))
        if done[0, 0]:
            break
    assert done[0, 0] and info["dead_cause"][0, 0] == RW.CAUSE_BITE
    wuid = int(w.uid[0, w0])
    kills = [e for e in w.events["bites"] if e["outcome"] == "kill"]
    assert len(kills) == 1 and kills[0]["wolf_uid"] == wuid and kills[0]["prey_sp"] == D_
    deaths = [e for e in w.events["deaths"] if e["cause"] == "bite"]
    assert len(deaths) == 1 and deaths[0]["killer"] == wuid and deaths[0]["sp"] == D_
    segs = [e for e in w.events["hunts"] if e["wolf_uid"] == wuid]
    assert len(segs) == 1 and segs[0]["end"] == "kill" and segs[0]["n_close"] > RW.HUNT_MIN_DECISIONS and not segs[0]["ran"]
    assert segs[0]["target_sp"] == D_ and segs[0]["t0"] == w.D   # closing is measured between decisions: first at t = 2 → 4
    assert w.st["deaths"][0, D_, RW.CAUSE_BITE] == 1 and w.st["bites"][0, D_, RW.BITE_KILL] == 1


def test_decide_draws_every_stream(cfg, monkeypatch):
    """Order 0: every species' ACT stream draws (block, 19) uniforms each decision whoever decides; a fixed brain gets its species
    block obs[k, lo:hi] (dead slots included) once per world (7-10, 시험 27 의 세계 쪽). decide_block here is a stand-in with the
    contract's draw rule — the real one is the brains agent's."""
    calls = []

    def fake_decide(ctrl, obs_block, rng, state, ctx):
        rng.random((obs_block.shape[0], B.N_ACTIONS))
        calls.append((obs_block.shape, ctx["facing_f"]))
        return np.full(obs_block.shape[0], B.EAT, dtype=np.int64), np.full(obs_block.shape[0], np.inf)
    monkeypatch.setattr(RW.BR, "decide_block", fake_decide)
    a = R9World(cfg, SEEDS[:3])
    b = R9World(cfg, SEEDS[:3])
    ctrl = RW.BR.Controller(brain=RW.BR.Brain(name="stub", kind="rule"), stochastic=True, label="rule")
    for k in range(b.K):
        b.set_controller(k, W_, ctrl)
    for _ in range(5):
        xa = a.decide()
        xb = b.decide(learner_sp=D_, learner_actions=np.full((b.K, int(b.caps[D_])), B.WATCH))
        for k in range(a.K):
            for s in range(3):
                assert a.rng_act[k][s].bit_generator.state == b.rng_act[k][s].bit_generator.state
        assert (xb[:, lo(b, W_):lo(b, R_)] == B.EAT).all() and (xa[:, lo(a, W_):lo(a, R_)] == B.WATCH).all()
        a.step(xa)
        b.step(xa)                                          # same physics actions → the other streams stay in step too
        for k in range(a.K):
            assert a.rng_bite[k].bit_generator.state == b.rng_bite[k].bit_generator.state
            assert a.rng_resp[k].bit_generator.state == b.rng_resp[k].bit_generator.state
    assert len(calls) == 5 * b.K and all(shp == (int(b.caps[W_]), B.OBS_DIM) for shp, _ in calls)
    assert all(abs(f - fr) < 1e-15 for (_, f), fr in zip(calls, np.tile(b.rule_f, 5)))


def test_decide_real_brains_streams_fixed(cfg):
    """시험 27 둘째 부분의 세계 쪽: wolf brain swapped (RULE_WOLF greedy ↔ RANDOM stochastic) — every ACT stream and the BITE
    stream consume the same draws (brains: r9_brains.make_rule; the brains agent owns their tests)."""
    BR = RW.BR
    worlds = []
    for wolf_brain, stoch in (("RULE_WOLF", False), ("RANDOM", True)):
        w = R9World(cfg, SEEDS[:2])
        for k in range(w.K):
            w.set_controller(k, D_, BR.Controller(BR.make_rule("RULE_DEER", cfg), stochastic=False, label="rule"))
            w.set_controller(k, R_, BR.Controller(BR.make_rule("RULE_BOAR", cfg), stochastic=False, label="rule"))
            w.set_controller(k, W_, BR.Controller(BR.make_rule(wolf_brain, cfg), stochastic=stoch, label=wolf_brain))
        worlds.append(w)
    for _ in range(30):
        for w in worlds:
            w.step(w.decide())
        a, b = worlds
        for k in range(a.K):
            for s in range(3):
                assert a.rng_act[k][s].bit_generator.state == b.rng_act[k][s].bit_generator.state
            assert a.rng_bite[k].bit_generator.state == b.rng_bite[k].bit_generator.state
    assert not np.array_equal(worlds[0].pos, worlds[1].pos)       # the brains really differ
