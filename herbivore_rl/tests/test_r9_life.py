"""R9 생애 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 3-6·3-7, 12절 시험 13·14·15).

13. 번식: 자격(E·HP·성숙·쉼·세대), 도망 확인은 짝 맺을 때만(사슴 뛰기·SHELTER, 멧돼지 뛰기, 늑대 없음), 대기 중 확인(사슴·늑대 E·HP·사분면,
    멧돼지 살아 있음·사분면), 짝 거리, 성별(늑대 무관), 근친 금지(세 종), 짝 찾기 때(⌊2t/75⌋), 대기 225 스텝, 출산 거리·멧돼지 150 스텝
    기다림, 비용 −0.2·쉼 2,250 스텝. 학습 세계는 보상만·모든 쌍, 판정 세계는 새끼·대기 1 건.
14. 생애 해시: Mix/Unit, FounderAge·Rank, Sex, Founder/NaturalFounder, Inherit, 성장·CanParent 가 EcoLifeHistoryV3.h 를 엔진 없이 컴파일한
    C++(tests/cpp/life_golden_r9_main.cpp)의 골든(tests/cpp/life_golden_r9.json)과 비트 단위로 같다. 손으로 낸 골든은 쓰지 않는다.
15. 판정 세계: 출생은 가장 낮은 빈 칸, 출생 예산·콘텐츠 상한·대기 1 건이 막고 막힌 기회를 까닭별로 센다, L0 은 상한을 끈다.
    '다시 나지 않음'·'사분면 풀 용량 합이 같다'는 세계(R9World)가 필요해 세계가 덜 되어 있으면 xfail 로 둔다.

세계 없이 돌린다: 생애 함수는 r9_life.LIFE_READS 이름만 가진 가짜 세계(SimpleNamespace)를 받는다. 시드는 시험 범위 44350~44399 만 쓴다.
"""

import json
import shutil
import struct
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import r9_body as B
from env_v2 import r9_life as L

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"
GOLDEN = ROOT / "tests" / "cpp" / "life_golden_r9.json"
CPP_MAIN = ROOT / "tests" / "cpp" / "life_golden_r9_main.cpp"
UE_POLICY = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
SEED = 44350


@pytest.fixture(scope="module")
def cfg():
    return B.load_r9_config(CFG)


@pytest.fixture(scope="module")
def jcfg():
    return B.load_r9_config(JCFG)


# --------------------------------------------------------------------------- #
# fake world (LIFE_READS names only)
# --------------------------------------------------------------------------- #

class Fake:
    """Minimal world: the R9World state-table names life reads (impl_contract.md §2). One world (K = 1) unless asked."""

    def __init__(self, cfg, K=1, t=0, grass=0.05):
        self.cfg = cfg
        self.body = B.load_body(cfg)
        self.rules = L.LifeRules.from_cfg(cfg, self.body)
        caps = [int(cfg["world"]["slots"][n]) for n in B.SPECIES]
        lo = np.cumsum([0] + caps[:-1]).astype(np.int64)
        S = int(sum(caps))
        size = float(cfg["world"]["size"])
        Q = int(cfg["world"]["quadrants"])
        G = int(size / 2)
        c = (np.arange(G) + 0.5) * 2.0
        X, Y = np.meshgrid(c, c, indexing="ij")
        C = 16
        s_w, s_q = L.life_seeds(SEED)
        self.w = SimpleNamespace(
            K=K, S=S, Q=Q, mode=cfg["world"]["mode"], t=np.full(K, t, np.int64), size=size,
            alive=np.zeros((K, S), bool), dead_cause=np.zeros((K, S), np.int8), uid=np.zeros((K, S), np.int64),
            sp_lo=lo, sp_hi=lo + np.array(caps), pos=np.zeros((K, S, 2)), quad=np.zeros((K, S), np.int8), E=np.zeros((K, S)),
            hp=np.ones((K, S)), born=np.zeros((K, S)), next_birth=np.zeros((K, S)), sex=np.zeros((K, S), np.int8),
            g_speed=np.ones((K, S)), g_size=np.ones((K, S)), parent_a=np.zeros((K, S), np.int64),
            parent_b=np.zeros((K, S), np.int64), offspring=np.zeros((K, S), np.int64), generation=np.zeros((K, S), np.int32),
            act=np.full((K, S), B.WATCH, np.int64), mating=np.zeros((K, S), bool), cov_c=np.full((K, C, 2), -1e6),
            cov_r=np.zeros((K, C)), cov_ok=np.zeros((K, C), bool), grass=np.full((K, G, G), float(grass)),
            cell_quad=B.quadrant_of(np.stack([X, Y], -1), size, Q),
            s_w=np.full(K, s_w, np.uint64), s_q=np.tile(np.array(s_q, np.uint64), (K, 1)), next_uid=np.ones(K, np.int64))
        self.life = L.LifeState.alloc(K, S, self.rules)

    def add(self, sp, x, y, k=0, sex=None, E=1.0, hp=1.0, mature=True, act=B.EAT, pa=0, pb=0, gen=0, slot=None, g=(1.0, 1.0)):
        w = self.w
        lo, hi = int(w.sp_lo[sp]), int(w.sp_hi[sp])
        if slot is None:
            slot = lo + int(np.flatnonzero(~w.alive[k, lo:hi])[0])
        mat = float(self.body.maturity[sp])
        if sex is None:
            sex = B.SEX_NONE if sp == B.WOLF else B.SEX_FEMALE
        w.alive[k, slot] = True
        w.uid[k, slot] = w.next_uid[k]
        w.next_uid[k] += 1
        w.pos[k, slot] = (x, y)
        w.quad[k, slot] = B.quadrant_of(np.array([x, y]), w.size, w.Q)
        w.E[k, slot], w.hp[k, slot] = E, hp
        w.born[k, slot] = float(w.t[k]) - mat - 1.0 if mature else float(w.t[k])
        w.next_birth[k, slot] = 0.0
        w.sex[k, slot] = sex
        w.g_speed[k, slot], w.g_size[k, slot] = g
        w.parent_a[k, slot], w.parent_b[k, slot], w.generation[k, slot] = pa, pb, gen
        w.act[k, slot] = act
        return slot

    def move(self, slot, x, y, k=0):
        self.w.pos[k, slot] = (x, y)
        self.w.quad[k, slot] = B.quadrant_of(np.array([x, y]), self.w.size, self.w.Q)

    def step(self, t):
        self.w.t[:] = t
        return L.breed_step(self.w, self.life, self.rules)

    def pairs(self, k=0):
        on = np.flatnonzero(self.life.pair_on[k])
        return sorted((int(self.life.pair_a[k, p]), int(self.life.pair_b[k, p])) for p in on)

    def install(self, ev):
        """What R9World._install_newborn does for the fields life reads."""
        w = self.w
        for nb in ev.newborns:
            k, s = nb.k, nb.slot
            assert not w.alive[k, s]
            w.alive[k, s], w.uid[k, s], w.pos[k, s] = True, nb.uid, nb.pos
            w.quad[k, s] = B.quadrant_of(nb.pos, w.size, w.Q)
            w.E[k, s], w.hp[k, s], w.born[k, s], w.next_birth[k, s] = nb.energy, 1.0, nb.born, 0.0
            w.sex[k, s], w.g_speed[k, s], w.g_size[k, s] = nb.sex, nb.g_speed, nb.g_size
            w.parent_a[k, s], w.parent_b[k, s], w.generation[k, s], w.offspring[k, s] = nb.parent_a, nb.parent_b, nb.generation, 0
            w.act[k, s], w.mating[k, s] = B.WATCH, False


def _invariant(life):
    assert np.array_equal(life.opportunities, life.paired + life.blocked.sum(-1))


# --------------------------------------------------------------------------- #
# 14 — C++ golden
# --------------------------------------------------------------------------- #

def _h(s):
    return int(s, 16)


def _f(s):
    return struct.unpack("<d", struct.pack("<Q", int(s, 16)))[0]


def _b(x):
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_14_golden_hash(golden):
    """Mix / Unit (LH 16~17) — 스칼라·배열판 모두 C++ 골든과 비트 같다. Mix(0) = SplitMix64 기준값."""
    assert L.mix(0) == 0xE220A8397B1DCDAF
    for v, m, u in golden["mix"]:
        assert L.mix(_h(v)) == _h(m) and _b(L.unit(_h(v))) == _h(u)
    vs = np.array([_h(v) for v, _, _ in golden["mix"]], dtype=np.uint64)
    assert [int(x) for x in L.mix_np(vs)] == [_h(m) for _, m, _ in golden["mix"]]
    assert [_b(x) for x in L.unit_np(vs)] == [_h(u) for _, _, u in golden["mix"]]


def test_14_golden_genome(golden):
    """Founder · NaturalFounder · Inherit (LH 49~62) — 두 Inherit 씨앗 꼴(NB 73 · FAc 557)과 clamp 끝 포함."""
    for s, i, sp, sz in golden["founder"]:
        a, b = L.founder(_h(s), _h(i))
        assert (_b(a), _b(b)) == (_h(sp), _h(sz))
    for s, i, v, sp, sz in golden["natural_founder"]:
        a, b = L.natural_founder(_h(s), _h(i), _f(v))
        assert (_b(a), _b(b)) == (_h(sp), _h(sz))
    for asp, asz, bsp, bsz, s, sp, sz in golden["inherit"]:
        a, b = L.inherit(_f(asp), _f(asz), _f(bsp), _f(bsz), _h(s))
        assert (_b(a), _b(b)) == (_h(sp), _h(sz))
    assert len(golden["founder"]) > 300 and len(golden["natural_founder"]) > 500 and len(golden["inherit"]) > 300


def test_14_golden_age_rank_sex(golden):
    """FounderAge (LH 27~34, 초 값과 R9 스텝 값) · Rank (SP 177~178) · Sex (LH 35~36)."""
    for m, j, mx, s, o, c, age in golden["founder_age"]:
        assert _b(L.founder_age(_f(m), _f(j), _f(mx), _h(s), o, c)) == _h(age)
    for i, c, s, r in golden["rank"]:
        assert L.founder_rank(i, c, _h(s)) == r
    for s, i, f, sx in golden["sex"]:
        assert L.natural_sex(_h(s), _h(i), _f(f)) == sx
    # Rank 는 0..count−1 의 순열이다(층별 나이가 겹치지 않는다)
    for c in (7, 24, 64):
        assert sorted(L.founder_rank(i, c, 12345) for i in range(c)) == list(range(c))


def test_14_golden_growth_can_parent(golden):
    """AgeFraction·Growth(smoothstep/직선)·BodyScale·SpeedScale·Maintenance (LH 196~203) · CanParent 경계 (LH 204~206)."""
    for nat, mat, born, now, spd, siz, af, gr, bs, ss, mt in golden["growth"]:
        a = L.age_frac(_f(now), _f(born), _f(mat))
        g = L.growth(a, bool(nat))
        assert (_b(a), _b(g)) == (_h(af), _h(gr))
        assert _b(L.body_scale(_f(siz), g)) == _h(bs)
        assert _b(L.speed_scale(_f(spd), g)) == _h(ss)
        assert _b(L.maintenance(_f(siz), _f(spd))) == _h(mt)
    for now, born, mat, nb, e, h, spd, siz, r in golden["can_parent"]:
        assert bool(L.can_parent_core(_f(now), _f(born), _f(mat), _f(nb), _f(e), _f(h), _f(spd), _f(siz))) == bool(r)


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ 없음 — 저장된 골든 JSON 대조만 한다")
def test_14_golden_is_fresh(tmp_path, golden):
    """언리얼 모듈의 EcoLifeHistoryV3.h 를 그대로 g++ 로 엔진 없이 컴파일해 다시 낸 골든이 저장된 JSON 과 같다."""
    if not (UE_POLICY / "EcoLifeHistoryV3.h").exists():
        pytest.skip("언리얼 모듈 EcoLifeHistoryV3.h 없음")
    exe = tmp_path / ("life_golden_r9.exe" if sys.platform == "win32" else "life_golden_r9")
    build = subprocess.run(["g++", "-std=c++17", "-O2", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror", "-Wshadow",
                            "-Wno-unused-parameter", "-I", str(UE_POLICY), str(CPP_MAIN), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, f"컴파일 실패:\n{build.stderr}"
    run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == golden


def test_14_seeds_and_founders(cfg):
    """생애 씨앗(11절 #23 해석)과 시작 개체 함수의 꼴: 사슴 NaturalFounder 0.92~1.08 · 늑대·멧돼지 Founder 0.95~1.05, 성별 규칙, 첫 번식."""
    body = B.load_body(cfg)
    s_w, s_q = L.life_seeds(SEED)
    assert s_w == L.mix(SEED) and s_q == tuple(L.mix((s_w + q + 1) & L.M64) for q in range(4))
    g = np.array([L.founder_genome(body, B.DEER, s_w, s_q[0], u) for u in range(1, 400)])
    assert g.min() >= 0.92 - 1e-12 and g.max() <= 1.08 + 1e-12 and g.min() < 0.93 and g.max() > 1.07
    for sp in (B.WOLF, B.BOAR):
        g = np.array([L.founder_genome(body, sp, s_w, s_q[0], u) for u in range(1, 400)])
        assert g.min() >= 0.95 and g.max() <= 1.05
        assert L.founder_genome(body, sp, s_w, s_q[0], 7) == L.founder(s_w, 7)
    assert L.founder_genome(body, B.DEER, s_w, s_q[1], 7) == L.natural_founder(s_q[1], 7, 0.08)
    sexes = [L.founder_sex(body, B.DEER, s_w, s_q[0], u, 0) for u in range(1, 2001)]
    assert 0.55 < np.mean(np.array(sexes) == B.SEX_FEMALE) < 0.65
    assert [L.founder_sex(body, B.BOAR, s_w, s_q[0], 1, i) for i in range(4)] == [B.SEX_FEMALE, B.SEX_MALE] * 2   # FAc 333
    assert L.founder_sex(body, B.WOLF, s_w, s_q[0], 1, 0) == B.SEX_NONE
    assert L.first_birth_time(body, B.BOAR, 100.0, s_q[0], 5) == 212.5 and L.first_birth_time(body, B.WOLF, 100.0, s_q[0], 5) == 100.0
    fb = L.first_birth_time(body, B.DEER, 100.0, s_q[0], 5)
    assert fb == 100.0 + 112.5 + 450.0 * L.unit(s_q[0] ^ 5)
    # 새끼 성별: 사슴 Unit(uid ^ S_w) < 0.6 (NB 98), 멧돼지 Unit(씨앗) < 0.5 (FAc 571), 늑대 없음
    assert L.child_sex(body, B.DEER, s_w, 77, 0) == (B.SEX_FEMALE if L.unit(77 ^ s_w) < 0.6 else B.SEX_MALE)
    assert L.child_sex(body, B.BOAR, s_w, 77, 991) == (B.SEX_FEMALE if L.unit(991) < 0.5 else B.SEX_MALE)
    assert L.child_sex(body, B.WOLF, s_w, 77, 991) == B.SEX_NONE
    # Inherit 씨앗 꼴: Native(사슴·늑대) offspring 그대로, Fauna(멧돼지) Mix(offspring)
    assert L.inherit_seed(body, B.DEER, 3, 9, 2) == 3 ^ L.mix(9) ^ 2
    assert L.inherit_seed(body, B.WOLF, 3, 9, 2) == 3 ^ L.mix(9) ^ 2
    assert L.inherit_seed(body, B.BOAR, 3, 9, 2) == 3 ^ L.mix(9) ^ L.mix(2)


# --------------------------------------------------------------------------- #
# 13 — breeding (train world unless noted)
# --------------------------------------------------------------------------- #

def test_13_eligibility(cfg):
    """자격: 성숙·쉼(next_birth)·E ≥ 0.7·HP ≥ 0.7(HP 없는 몸 = 1)·세대 < 64·이번 스텝 죽지 않음."""
    f = Fake(cfg, t=1000)
    w = f.w
    d0 = f.add(B.DEER, 10, 10)
    d_young = f.add(B.DEER, 10, 11, mature=False)
    d_wait = f.add(B.DEER, 10, 12)
    w.next_birth[0, d_wait] = 1001.0
    d_e = f.add(B.DEER, 10, 13, E=0.69)
    d_hp = f.add(B.DEER, 10, 14, hp=0.2)              # 사슴은 HP 를 보지 않는다(Native 1)
    w_hp = f.add(B.WOLF, 20, 10, hp=0.69)
    w_ok = f.add(B.WOLF, 20, 11, hp=0.7)
    d_gen = f.add(B.DEER, 10, 15, gen=64)
    d_bit = f.add(B.DEER, 10, 16)
    w.dead_cause[0, d_bit] = 1
    e = L.can_parent(w, f.rules)[0]
    assert e[d0] and not e[d_young] and not e[d_wait] and not e[d_e] and e[d_hp]
    assert not e[w_hp] and e[w_ok] and not e[d_gen] and not e[d_bit]
    # 성숙 경계: t − born ≥ 성숙 (같으면 자격)
    w.born[0, d_young] = 1000.0 - 2700.0
    assert L.can_parent(w, f.rules)[0, d_young]
    w.born[0, d_young] = 1000.0 - 2699.0
    assert not L.can_parent(w, f.rules)[0, d_young]


def test_13_scan_times():
    """짝 찾기 = ⌊2t/75⌋ 가 바뀌는 스텝(평균 37.5 스텝), t = 0 도 찾는다."""
    t = np.arange(0, 400)
    s = np.flatnonzero(L.mate_scan_now(t))
    assert s[:6].tolist() == [0, 38, 75, 113, 150, 188]
    assert np.all(np.diff(s) >= 37) and np.all(np.diff(s) <= 38)


def test_13_pair_sex_distance_species(cfg):
    """짝: 사슴·멧돼지 이성, 늑대 성별 무관, 거리 ≤ mate_r(사슴·늑대 10, 멧돼지 5 — 같으면 됨)."""
    f = Fake(cfg)
    a = f.add(B.DEER, 10, 10, sex=B.SEX_FEMALE)
    b = f.add(B.DEER, 20, 10, sex=B.SEX_MALE)            # 정확히 10
    c = f.add(B.DEER, 40, 40, sex=B.SEX_FEMALE)
    d = f.add(B.DEER, 40, 50.0001, sex=B.SEX_MALE)        # 10.0001
    e1 = f.add(B.DEER, 5, 50, sex=B.SEX_FEMALE)
    e2 = f.add(B.DEER, 6, 50, sex=B.SEX_FEMALE)          # 같은 성
    w1 = f.add(B.WOLF, 50, 5)
    w2 = f.add(B.WOLF, 55, 5)                             # 둘 다 성별 없음
    b1 = f.add(B.BOAR, 30, 25, sex=B.SEX_FEMALE)
    b2 = f.add(B.BOAR, 35, 25, sex=B.SEX_MALE)            # 정확히 5
    b3 = f.add(B.BOAR, 30, 2, sex=B.SEX_FEMALE)
    b4 = f.add(B.BOAR, 35.01, 2, sex=B.SEX_MALE)
    ev = f.step(0)
    assert f.pairs() == sorted([(a, b), (w1, w2), (b1, b2)])
    assert ev.paired[0, [a, b, w1, w2, b1, b2]].all() and not ev.paired[0, [c, d, e1, e2, b3, b4]].any()
    assert f.w.mating[0, [a, b, w1, w2, b1, b2]].all() and not f.w.mating[0, [c, d, e1, e2, b3, b4]].any()
    assert ev.births.sum() == 0
    _invariant(f.life)


def test_13_flee_check_only_at_pairing(cfg):
    """도망 확인은 짝 맺을 때만: 사슴 RUN·SHELTER 면 안 맺음, 멧돼지 RUN 이면 안 맺음, 늑대 RUN 도 맺음. 맺은 뒤 사슴이 뛰어도 출산."""
    f = Fake(cfg)
    run = B.RUN_FIRST + 3
    dr = [f.add(B.DEER, 10, 10, sex=B.SEX_FEMALE, act=run), f.add(B.DEER, 11, 10, sex=B.SEX_MALE)]
    ds = [f.add(B.DEER, 30, 10, sex=B.SEX_FEMALE, act=B.SHELTER), f.add(B.DEER, 31, 10, sex=B.SEX_MALE)]
    br = [f.add(B.BOAR, 50, 10, sex=B.SEX_FEMALE, act=run), f.add(B.BOAR, 51, 10, sex=B.SEX_MALE)]
    wr = [f.add(B.WOLF, 10, 50, act=run), f.add(B.WOLF, 11, 50, act=run)]
    f.step(0)
    assert f.pairs() == [tuple(wr)]
    for s in dr + ds + br:
        f.w.act[0, s] = B.WALK_FIRST                      # 걷기·먹기·살피기는 막지 않는다
    f.step(38)
    assert f.pairs() == sorted([tuple(wr), tuple(dr), tuple(ds), tuple(br)])
    # 대기 중 사슴은 뛰어도 취소되지 않는다(3-7 '언리얼과 다르게' — RL-6); 멧돼지는 출산 때 뛰면 기다린다
    for s in dr + ds:
        f.w.act[0, s] = run
    f.step(100)
    assert tuple(dr) in f.pairs() and tuple(ds) in f.pairs()
    ev = f.step(225)                                       # 늑대는 0 에 맺어 225 에 낳는다(뛰는 중이어도)
    assert ev.births[0, wr].tolist() == [1, 1] and ev.births[0, dr + ds].sum() == 0
    ev = f.step(38 + 225)
    assert ev.births[0, dr].tolist() == [1, 1] and ev.births[0, ds].tolist() == [1, 1]
    assert ev.births[0, wr].tolist() == [0, 0]
    _invariant(f.life)


def test_13_gestation_costs_rest(cfg):
    """임신 225 스텝: 224 에는 안 낳고 225 에 낳는다. 비용 E −0.2 둘 다, 다음 번식 t + 2,250, 새끼 수 +1, 두 부모 보상 1."""
    f = Fake(cfg)
    a = f.add(B.DEER, 10, 10, sex=B.SEX_FEMALE, E=0.9)
    b = f.add(B.DEER, 12, 10, sex=B.SEX_MALE, E=0.75)
    f.step(0)
    assert f.pairs() == [(a, b)]
    ev = f.step(224)
    assert ev.births.sum() == 0 and f.pairs() == [(a, b)]
    ev = f.step(225)
    assert ev.births[0, a] == 1 and ev.births[0, b] == 1 and ev.births.sum() == 2
    np.testing.assert_allclose(f.w.E[0, [a, b]], [0.9 - 0.2, 0.75 - 0.2], rtol=0, atol=0)
    assert f.w.next_birth[0, a] == 225 + 2250 and f.w.next_birth[0, b] == 225 + 2250
    assert f.w.offspring[0, a] == 1 and f.w.offspring[0, b] == 1
    assert f.pairs() == [] and not f.w.mating[0, [a, b]].any()
    assert ev.newborns == [] and f.w.next_uid[0] == 3          # 학습 세계: 새끼 몸 없음
    assert f.life.births[0, 0, B.DEER] == 1
    # 쉼 동안 다시 맺지 않는다
    f.w.E[0, [a, b]] = 1.0
    f.step(263)
    assert f.pairs() == []


def test_13_pending_checks(cfg):
    """대기 중 확인: 사슴·늑대는 E·HP 자격을 잃으면 취소, 멧돼지는 살아 있음·사분면만(E 가 떨어져도 계속). 죽으면 취소."""
    f = Fake(cfg)
    da, db = f.add(B.DEER, 10, 10, sex=B.SEX_FEMALE), f.add(B.DEER, 11, 10, sex=B.SEX_MALE)
    wa, wb = f.add(B.WOLF, 30, 10), f.add(B.WOLF, 31, 10)
    ba, bb = f.add(B.BOAR, 50, 10, sex=B.SEX_FEMALE), f.add(B.BOAR, 51, 10, sex=B.SEX_MALE)
    ea, eb = f.add(B.DEER, 10, 40, sex=B.SEX_FEMALE), f.add(B.DEER, 11, 40, sex=B.SEX_MALE)
    f.step(0)
    assert len(f.pairs()) == 4
    f.w.E[0, da] = 0.69
    f.w.hp[0, wb] = 0.5
    f.w.E[0, ba] = 0.1
    f.w.dead_cause[0, eb] = 1                              # 이번 스텝 물려 죽음
    f.step(10)
    assert f.pairs() == [(ba, bb)]
    assert f.life.cancelled[0, 0].tolist() == [2, 1, 0]
    assert not f.w.mating[0, [da, db, wa, wb, ea, eb]].any() and f.w.mating[0, [ba, bb]].all()


def test_13_delivery_distance_and_boar_wait(cfg):
    """출산 때: 사슴·늑대는 15 단위 밖이면 낳지 않고 225 스텝 뒤 다시(대기 끝). 멧돼지는 7.5 단위 안·뛰지 않음을 150 스텝까지 기다리고, 넘으면 취소."""
    f = Fake(cfg)
    da, db = f.add(B.DEER, 10, 10, sex=B.SEX_FEMALE), f.add(B.DEER, 11, 10, sex=B.SEX_MALE)
    ba, bb = f.add(B.BOAR, 30, 30, sex=B.SEX_FEMALE), f.add(B.BOAR, 31, 30, sex=B.SEX_MALE)
    ca, cb = f.add(B.BOAR, 50, 50, sex=B.SEX_FEMALE), f.add(B.BOAR, 51, 50, sex=B.SEX_MALE)
    f.step(0)
    assert len(f.pairs()) == 3
    f.move(db, 10, 25.01)                                  # 15.0x 단위
    f.move(bb, 38.6, 30)                                   # 7.6 단위
    f.w.act[0, ca] = B.RUN_FIRST                           # 출산 때 뛰면 기다림
    ev = f.step(225)
    assert ev.births.sum() == 0
    assert f.w.next_birth[0, da] == 225 + 225 and f.w.next_birth[0, db] == 225 + 225    # NB 54 재시도
    assert f.pairs() == sorted([(ba, bb), (ca, cb)])
    assert f.life.failed[0, 0, B.DEER] == 1
    f.move(bb, 37.5, 30)                                   # 정확히 7.5 → 낳는다
    ev = f.step(225 + 100)
    assert ev.births[0, [ba, bb]].tolist() == [1, 1] and f.pairs() == [(ca, cb)]
    assert f.w.next_birth[0, ba] == 325 + 2250
    f.step(225 + 150)                                      # 기한 + 150: 아직 기다림
    assert f.pairs() == [(ca, cb)]
    f.step(225 + 151)                                      # 넘으면 취소
    assert f.pairs() == [] and f.life.cancelled[0, 0, B.BOAR] == 1


def test_13_train_all_pairs_uid_order(cfg):
    """학습 세계: 짝 찾기 때 맞는 쌍을 ID 차례로 모두 맺는다(대기 1 건 없음). 이미 대기 중인 개체는 다시 맺지 않는다."""
    f = Fake(cfg)
    sexes = [B.SEX_FEMALE, B.SEX_FEMALE, B.SEX_MALE, B.SEX_FEMALE, B.SEX_MALE, B.SEX_MALE, B.SEX_FEMALE]
    s = [f.add(B.DEER, 10 + i, 10, sex=x) for i, x in enumerate(sexes)]
    f.step(0)
    # uid 차례 탐욕: 1F–3M, 2F–5M, 4F–6M, 7F 남음
    assert f.pairs() == sorted([(s[0], s[2]), (s[1], s[4]), (s[3], s[5])])
    assert f.life.paired[0, 0, B.DEER] == 3 and f.life.opportunities[0, 0, B.DEER] == 3
    late = f.add(B.DEER, 9, 10, sex=B.SEX_MALE)
    f.step(38)
    assert (s[6], late) in f.pairs() and len(f.pairs()) == 4
    _invariant(f.life)


def test_13_incest_and_founders(jcfg, cfg):
    """근친 금지(세 종): 부모-자식·같은 부모 하나라도 둔 형제. 부모 모름(0)인 시작 개체끼리는 맺는다."""
    for sp in (B.DEER, B.WOLF, B.BOAR):
        f = Fake(jcfg)
        sx = (lambda i: B.SEX_NONE) if sp == B.WOLF else (lambda i: B.SEX_FEMALE if i % 2 == 0 else B.SEX_MALE)
        p1 = f.add(sp, 10, 10, sex=sx(0))
        p2 = f.add(sp, 11, 10, sex=sx(1))
        u1, u2 = int(f.w.uid[0, p1]), int(f.w.uid[0, p2])
        f.w.mating[0, [p1, p2]] = False
        f.w.E[0, [p1, p2]] = 0.0                            # 부모는 자격 없음 — 새끼끼리만 본다
        c1 = f.add(sp, 30, 30, sex=sx(0), pa=u1, pb=u2)    # 형제(두 부모 같음)
        f.add(sp, 31, 30, sex=sx(1), pa=u2, pb=99)         # c2: c1 과 반형제(부모 하나 같음)
        c3 = f.add(sp, 30, 31, sex=sx(1), pa=0, pb=u2)     # c2 와 반형제
        f.w.parent_a[0, c3] = int(f.w.uid[0, c1])           # c3 의 부모가 c1 → c1 과 부모-자식
        f.step(0)
        assert f.pairs() == [], sp
        _invariant(f.life)
        f2 = Fake(cfg)
        a2, b2 = f2.add(sp, 10, 10, sex=sx(0)), f2.add(sp, 11, 10, sex=sx(1))
        f2.step(0)
        assert f2.pairs() == [(a2, b2)], sp
    assert L.related(0, 0, 5, 0, 0, 6) is not None and not L.related(np.int64(0), 0, 5, 0, 0, 6)
    assert L.related(5, 0, 7, 0, 0, 5) and L.related(0, 0, 5, 5, 0, 7) and L.related(3, 4, 7, 4, 9, 8)


def test_13_batch_independent(jcfg, cfg):
    """한 세계의 생애 결과는 묶음의 다른 세계와 무관하다(시험 1 의 생애 부분): K = 3 묶음 = 세계 하나씩 돌린 것."""
    def build(c, K, ks):
        f = Fake(c, K=K)
        rng = np.random.default_rng(44365)
        for k in range(K):
            r = np.random.default_rng([44366, ks[k]])
            for sp, n in ((B.DEER, 30), (B.WOLF, 4), (B.BOAR, 8)):
                for i in range(n):
                    f.add(sp, *r.uniform(0, f.w.size * 0.5, 2), k=k, sex=(B.SEX_NONE if sp == B.WOLF else 1 + i % 2),
                          E=r.uniform(0.65, 1.0))
        f.w.grass[:] = rng.uniform(0.01, 0.1)
        return f
    for c in (cfg, jcfg):
        fb = build(c, 3, [0, 1, 2])
        singles = [build(c, 1, [k]) for k in range(3)]
        for t in range(0, 700, 1):
            for f in [fb] + singles:
                f.w.E = np.minimum(f.w.E + 0.001, 1.0)
            evb = fb.step(t)
            fb.install(evb)
            for k, f in enumerate(singles):
                ev = f.step(t)
                f.install(ev)
                assert np.array_equal(ev.births[0], evb.births[k]) and np.array_equal(ev.paired[0], evb.paired[k])
                assert [(n.slot, n.uid, n.sex, n.g_speed, n.g_size) for n in ev.newborns] == \
                       [(n.slot, n.uid, n.sex, n.g_speed, n.g_size) for n in evb.newborns if n.k == k]
        for k, f in enumerate(singles):
            for name in ("E", "next_birth", "offspring", "mating", "next_uid"):
                assert np.array_equal(getattr(f.w, name)[0], getattr(fb.w, name)[k]), name
            assert np.array_equal(f.life.paired[0], fb.life.paired[k]) and np.array_equal(f.life.blocked[0], fb.life.blocked[k])
        assert fb.life.births.sum() > 0


def test_13_slot_reset_cancels(cfg):
    """다시 남(칸 재사용): on_slot_reset 이 그 칸을 가리킨 대기를 지우고(w 를 넘기면 짝의 mating 도 바로), uid 지킴이 남은 것도 막는다."""
    f = Fake(cfg)
    a, b = f.add(B.DEER, 10, 10, sex=B.SEX_FEMALE), f.add(B.DEER, 11, 10, sex=B.SEX_MALE)
    c, d = f.add(B.DEER, 30, 10, sex=B.SEX_FEMALE), f.add(B.DEER, 31, 10, sex=B.SEX_MALE)
    f.step(0)
    assert len(f.pairs()) == 2
    L.on_slot_reset(f.life, 0, [a], w=f.w)
    assert f.pairs() == [(c, d)] and not f.w.mating[0, b] and f.w.mating[0, c]
    f.w.uid[0, d] = 999                                    # 세계가 on_slot_reset 없이 칸을 바꿨어도
    f.step(5)
    assert f.pairs() == [] and not f.w.mating[0].any()


# --------------------------------------------------------------------------- #
# 15 — judge world
# --------------------------------------------------------------------------- #

def _jpair(f, sp, x, y, sex=True):
    a = f.add(sp, x, y, sex=(B.SEX_FEMALE if sex else B.SEX_NONE))
    b = f.add(sp, x, y + 2.0, sex=(B.SEX_MALE if sex else B.SEX_NONE))
    return a, b


def test_15_newborn_fields_lowest_slot(jcfg):
    """판정 세계 출생: 가장 낮은 빈 칸(같은 스텝 앞 출생이 쓴 칸 빼고), 새 uid(늘기만), 유전 Inherit·세대·성별 해시, E 0.4·지방 0, 자리 고리."""
    f = Fake(jcfg)
    w = f.w
    for i in range(6):
        f.add(B.DEER, 100, 100 + i * 3, E=0.0)             # 칸 0~5 를 채움 (자격 없음)
    a1, b1 = _jpair(f, B.DEER, 10, 10)                     # 사분면 0, 칸 6·7
    a2, b2 = _jpair(f, B.DEER, 80, 10)                     # 사분면 1, 칸 8·9
    w.alive[0, [2, 4]] = False                             # 빈 칸 2·4
    w.dead_cause[0, 5] = 1                                 # 칸 5 는 이번 스텝 죽음 — 아직 빈 칸이 아니다
    w.offspring[0, a1] = 3
    f.step(0)
    assert f.pairs() == sorted([(a1, b1), (a2, b2)])
    u0 = int(w.next_uid[0])
    ev = f.step(225)
    assert [nb.slot for nb in ev.newborns] == [2, 4]
    nb = ev.newborns[0]
    assert nb.uid == u0 and ev.newborns[1].uid == u0 + 1 and w.next_uid[0] == u0 + 2
    assert (nb.sp, nb.parent_a, nb.parent_b, nb.generation) == (B.DEER, int(w.uid[0, a1]), int(w.uid[0, b1]), 1)
    seed = int(w.uid[0, a1]) ^ L.mix(int(w.uid[0, b1])) ^ 3
    assert (nb.g_speed, nb.g_size) == L.inherit(1.0, 1.0, 1.0, 1.0, seed)
    assert nb.sex == L.child_sex(f.body, B.DEER, int(w.s_w[0]), nb.uid, seed)
    assert (nb.energy, nb.fat, nb.born) == (0.4, 0.0, 225.0)
    np.testing.assert_array_equal(nb.pos, w.pos[0, a1] + 1.1 * B.GOLDEN8[0])
    np.testing.assert_array_equal(nb.head, B.GOLDEN8[0])
    assert w.offspring[0, a1] == 4 and w.E[0, a1] == pytest.approx(0.8, abs=0) and f.life.births[0, 0, B.DEER] == 1
    assert f.life.log[0] == (0, 225, B.DEER, 0, u0, int(w.uid[0, a1]), int(w.uid[0, b1]))
    f.install(ev)
    _invariant(f.life)


def test_15_child_spot_rules(jcfg):
    """새끼 자리: 산 개체에서 0.5 단위 안이면 다음 자리, 늑대는 은신처 원(r + 0.5) 밖, 멧돼지는 두 부모 가운데에서 0.9 + 0.15j."""
    f = Fake(jcfg)
    w = f.w
    a, b = _jpair(f, B.DEER, 20, 20)
    f.add(B.DEER, 20 + 1.1 + 0.3, 20, E=0.0)               # 자리 0 에서 0.3 → 막힘
    for i in range(30):                                    # 늑대 예산용 사슴 (사분면 2)
        f.add(B.DEER, 5 + i, 110, E=0.0)
    wa, wb = _jpair(f, B.WOLF, 30, 80, sex=False)
    w.cov_c[0, 0] = w.pos[0, wa] + 1.1 * B.GOLDEN8[0] + np.array([0.0, 0.9])   # 자리 0 이 원 r + 0.5 안
    w.cov_r[0, 0], w.cov_ok[0, 0] = 0.5, True
    ba, bb = _jpair(f, B.BOAR, 90, 90)
    f.step(0)
    ev = f.step(225)
    got = {nb.sp: nb for nb in ev.newborns}
    np.testing.assert_array_equal(got[B.DEER].pos, w.pos[0, a] + 1.3 * B.GOLDEN8[1])
    np.testing.assert_array_equal(got[B.WOLF].pos, w.pos[0, wa] + 1.3 * B.GOLDEN8[1])
    mid = (w.pos[0, ba] + w.pos[0, bb]) * 0.5
    np.testing.assert_array_equal(got[B.BOAR].pos, mid + 0.9 * B.GOLDEN8[0])
    assert got[B.WOLF].sex == B.SEX_NONE
    seed = int(w.uid[0, ba]) ^ L.mix(int(w.uid[0, bb])) ^ L.mix(0)
    assert got[B.BOAR].sex == (B.SEX_FEMALE if L.unit(seed) < 0.5 else B.SEX_MALE)
    # 8 자리가 다 막히면 출생 없음(막힘 까닭에 세지 않음 — 계약 11절 #34), 부모는 225 뒤 다시
    f2 = Fake(jcfg)
    a, b = _jpair(f2, B.DEER, 20, 20)
    for j in range(8):
        p = f2.w.pos[0, a] + (1.1 + 0.2 * j) * B.GOLDEN8[j]
        f2.add(B.DEER, p[0], p[1], E=0.0)
    f2.step(0)
    ev = f2.step(225)
    assert ev.newborns == [] and ev.births.sum() == 0 and f2.life.failed[0, 0, B.DEER] == 1
    assert f2.life.blocked.sum() == 0 and f2.w.next_birth[0, a] == 450


def test_15_one_pending_per_quadrant_species(jcfg):
    """대기 1 건: 같은 사분면·종의 둘째 쌍은 막히고(까닭 one_pending), 다른 사분면·다른 종은 따로 맺는다. 첫 쌍 = ID 차례 첫 쌍."""
    f = Fake(jcfg)
    a, b = _jpair(f, B.DEER, 10, 10)
    c, d = _jpair(f, B.DEER, 20, 30)
    e, g = _jpair(f, B.DEER, 70, 10)                       # 사분면 1
    ba, bb = _jpair(f, B.BOAR, 15, 15)                     # 같은 사분면 다른 종
    f.step(0)
    assert f.pairs() == sorted([(a, b), (e, g), (ba, bb)])
    f.step(38)                                             # 대기가 있는 동안 짝 찾기 → 막힘 셈
    assert f.life.blocked[0, 0, B.DEER, L.BLOCK_ONE_PENDING] == 1
    assert f.life.paired[0, 0, B.DEER] == 1 and f.life.paired[0, 1, B.DEER] == 1 and f.life.paired[0, 0, B.BOAR] == 1
    ev = f.step(225)
    f.install(ev)
    assert len(ev.newborns) == 3 and (c, d) in f.pairs()   # 같은 스텝 짝 찾기에서 다음 쌍
    _invariant(f.life)
    st = L.life_stats(f.life)
    assert st["content_block_share"][B.DEER] == pytest.approx(1 / (1 + 3))


def test_15_wolf_budget(jcfg):
    """늑대 예산(ESS 401~405): 사분면 늑대 + 1 ≤ 6 이고 사분면 사슴 ≥ 8 × (늑대 + 1). 멧돼지는 먹이로 세지 않는다."""
    def run(n_deer, n_wolf_extra, n_boar=0):
        f = Fake(jcfg)
        for i in range(n_deer):
            f.add(B.DEER, 2 + (i % 50), 2 + 0.7 * (i // 50), E=0.0)
        for i in range(n_boar):
            f.add(B.BOAR, 2 + i, 50, E=0.0)
        a, b = _jpair(f, B.WOLF, 40, 30, sex=False)
        for i in range(n_wolf_extra):
            f.add(B.WOLF, 10 + 3 * i, 40, E=0.0)
        f.step(0)
        ev = f.step(225)
        return f, ev
    f, ev = run(24, 0)                                     # 늑대 2 + 1 = 3, 사슴 24 ≥ 24
    assert len(ev.newborns) == 1 and ev.newborns[0].sp == B.WOLF
    f, ev = run(23, 0, n_boar=10)
    assert ev.newborns == [] and f.life.blocked[0, 0, B.WOLF, L.BLOCK_WOLF_BUDGET] == 1
    assert f.w.next_birth[0, f.w.sp_lo[B.WOLF]] == 450     # 막혀도 225 뒤 다시
    f, ev = run(48, 3)                                     # 늑대 5 + 1 = 6 ≤ 6
    assert len(ev.newborns) == 1
    f, ev = run(56, 4)                                     # 늑대 6 + 1 = 7 > 6
    assert ev.newborns == [] and f.life.blocked[0, 0, B.WOLF, L.BLOCK_WOLF_BUDGET] == 1
    _invariant(f.life)


def test_15_boar_cap_food_budget_slot_cap(jcfg):
    """멧돼지 상한 14(짝 찾기·출산 둘 다), 먹이 예산(풀 ≥ max(1, 식물 먹는 개체 + 1) × 0.42·0.35), 배열 상한 — 까닭별로 센다."""
    f = Fake(jcfg)
    for i in range(12):
        f.add(B.BOAR, 2 + 2 * i, 20, E=0.0)
    a, b = _jpair(f, B.BOAR, 40, 40)                       # 14 마리 → 짝 찾기부터 막힘
    f.step(0)
    assert f.pairs() == [] and f.life.blocked[0, 0, B.BOAR, L.BLOCK_BOAR_CAP] == 1
    f.w.alive[0, f.w.sp_lo[B.BOAR]] = False                # 13 마리 → 맺음
    f.step(38)
    assert f.pairs() == [(a, b)]
    f.add(B.BOAR, 50, 50, E=0.0)                           # 대기 중 14 마리가 됨 → 출산 때 막힘
    ev = f.step(38 + 225)
    assert ev.newborns == [] and f.life.blocked[0, 0, B.BOAR, L.BLOCK_BOAR_CAP] == 2
    _invariant(f.life)
    # 먹이 예산: 사분면 0 풀 합 = 900 셀 × g. 식물 먹는 개체(사슴 + 멧돼지) 3 → 필요 0.42 × 4 = 1.68
    for g, ok in ((1.68 / 900 * 1.0001, True), (1.68 / 900 * 0.999, False)):
        f = Fake(jcfg, grass=g)
        f.w.grass[0, 30:, :] = 1.0                         # 다른 사분면 풀은 상관없음
        a, b = _jpair(f, B.DEER, 10, 10)
        f.add(B.BOAR, 20, 20, E=0.0)
        f.step(0)
        ev = f.step(225)
        assert (len(ev.newborns) == 1) == ok
        assert f.life.blocked[0, 0, B.DEER, L.BLOCK_FOOD] == (0 if ok else 1)
    # 배열 상한: 사슴 칸이 다 차면 slot_cap
    f = Fake(jcfg)
    a, b = _jpair(f, B.DEER, 10, 10)
    n = int(f.w.sp_hi[B.DEER] - f.w.sp_lo[B.DEER]) - 2
    for i in range(n):
        f.add(B.DEER, 61 + (i % 50) * 1.1, 61 + (i // 50) * 1.1, E=0.0)
    f.w.grass[:] = 1.0
    f.step(0)
    ev = f.step(225)
    assert ev.newborns == [] and f.life.blocked[0, 0, B.DEER, L.BLOCK_SLOT_CAP] == 1
    _invariant(f.life)


def test_15_quadrant_pending_cancel(jcfg):
    """대기 중 한 부모가 짝 맺을 때 사분면을 떠나면 취소(사슴·늑대·멧돼지 모두 — 3-1)."""
    for sp in (B.DEER, B.WOLF, B.BOAR):
        f = Fake(jcfg)
        for i in range(30):
            f.add(B.DEER, 2 + i, 110, E=0.0)
        a, b = _jpair(f, sp, 55, 10, sex=(sp != B.WOLF))
        f.step(0)
        assert len(f.pairs()) == 1, sp
        f.move(b, 61, 10)                                  # 사분면 1 로
        f.step(5)
        assert f.pairs() == [], sp


def test_15_L0_limits_off(jcfg):
    """L0: 대기 1 건·늑대 예산·멧돼지 상한을 끄고 먹이 예산·자격만 남긴다 — 같은 사분면에서 여러 쌍, 사슴 없는 늑대 출산."""
    j0 = B.override(jcfg, jcfg["judge"]["variants"]["L0"])
    f = Fake(j0)
    assert not f.rules.limits_on and not f.rules.one_pending and f.life.P == f.w.S // 2 + 1
    a, b = _jpair(f, B.DEER, 10, 10)
    c, d = _jpair(f, B.DEER, 20, 30)
    wa, wb = _jpair(f, B.WOLF, 40, 40, sex=False)
    for i in range(13):
        f.add(B.BOAR, 2 + 2 * i, 50, E=0.0)
    ba, bb = _jpair(f, B.BOAR, 45, 20)                     # 15 마리여도 맺음
    f.step(0)
    assert f.pairs() == sorted([(a, b), (c, d), (wa, wb), (ba, bb)])
    ev = f.step(225)
    assert sorted(nb.sp for nb in ev.newborns) == [B.DEER, B.DEER, B.WOLF, B.BOAR]
    assert f.life.blocked.sum() == 0
    _invariant(f.life)


def test_15_judge_world_no_respawn_and_quadrant_grass():
    """세계가 필요한 부분: 판정 세계는 다시 나지 않고(죽은 칸은 빈다), 사분면 풀 용량 합(은신처 0.15 배 전)이 모두 70 이다.
    R9World 가 아직 덜 되어 있으면 xfail (세계 에이전트가 같은 때 채운다)."""
    from env_v2 import r9_world as RW

    j = B.load_r9_config(JCFG)
    try:
        world = RW.R9World(j, [SEED])
    except NotImplementedError as e:
        pytest.xfail(f"R9World 미완성: {e}")
    cq = np.asarray(world.cell_quad)
    cover = float(j["food"]["grass"]["cover_mult"])
    cap0 = np.where(np.asarray(world.cover_cell[0]), np.asarray(world.grass_cap[0]) / cover, np.asarray(world.grass_cap[0]))
    sums = [float(np.cumsum(cap0[cq == q])[-1]) for q in range(4)]
    np.testing.assert_allclose(sums, 70.0, rtol=1e-9)
    alive0 = np.asarray(world.alive).copy()
    kill = int(np.flatnonzero(alive0[0])[0])
    world.E[0, kill] = 0.0
    world.R[0, kill] = 0.0
    try:
        world.step(np.full((1, world.S), B.WATCH, np.int64))
    except NotImplementedError as e:
        pytest.xfail(f"R9World.step 미완성: {e}")
    assert not world.alive[0, kill]
