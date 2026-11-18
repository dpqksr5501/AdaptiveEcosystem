"""R10 0 단계 바탕 시험 — 계약·층 지형·맵 생성기·종 카드 (사양 RL_R10_PHASE0_SPEC.md 3·4·6·7·8·10 절)."""

import copy

import numpy as np
import pytest

from r10 import contract as C
from r10 import mapgen as G
from r10 import species as S
from r10 import terrain as T


# ----------------------------------------------------------------------------- 계약

def test_contract_shape_and_slices():
    assert C.OBS_DIM == 206 and C.N_ACTIONS == 24
    assert len(set(C.OBS_NAMES)) == C.OBS_DIM and len(set(C.ACTION_NAMES)) == C.N_ACTIONS
    spans = sorted(C.SLICES.values())
    assert spans[0][0] == 0 and spans[-1][1] == C.OBS_DIM
    assert all(a[1] == b[0] for a, b in zip(spans, spans[1:]))
    assert C.SLICES["other"][1] - C.SLICES["other"][0] == C.N_OTHER * 12
    assert C.io_hash() == C.io_hash() and C.io_hash().startswith("0x")


def test_action_and_obs_masks_follow_medium():
    ground = C.action_mask({"ground": True})
    assert not ground[[C.A_UP, C.A_DOWN, C.A_DIVE, 22, 23]].any() and ground[:19].all()
    fly = C.action_mask({"ground": True, "fly": True})
    assert fly[[C.A_UP, C.A_DOWN, C.A_DIVE]].all()
    fish = C.action_mask({"swim": True, "needs_water": True})
    assert fish[[C.A_UP, C.A_DOWN]].all() and not fish[C.A_DIVE]
    om = C.obs_mask({"swim": True, "needs_water": True})
    idx = {n: i for i, n in enumerate(C.OBS_NAMES)}
    assert not om[idx["noise_dir"]] and om[idx["breath"]] and not om[idx["airborne"]]
    lo, hi = C.SLICES["spare"]
    assert not C.obs_mask({"ground": True})[lo:hi].any()


def test_log_scales():
    assert C.lg(0.0, 1.0, 25.0) == 0.0 and C.lg(25.0, 1.0, 25.0) == pytest.approx(1.0) and C.lg(1e6, 1.0, 25.0) == 1.0
    assert C.ratio(450.0, 0.05) == 1.0 and C.ratio(1.0, 1.0) == 0.0 and C.ratio(0.05, 450.0) == -1.0


# ----------------------------------------------------------------------------- 지형·생성기

def test_mapgen_deterministic_and_valid():
    for s in range(50000, 50012):
        a, b = G.make_map(s), G.make_map(s)
        for k in T.LAYERS:
            assert np.array_equal(getattr(a, k), getattr(b, k)), (s, k)
        a.check()
        assert 60 <= a.w <= 200 and 60 <= a.h <= 200
    seen = {(G.make_map(s).meta["water"]) for s in range(50000, 50040)}
    assert {"none", "river", "lake"} <= seen


def test_seed_ranges_locked():
    G.make_map(61000, "test")
    for bad, purpose in ((61000, "train"), (61500, "check"), (49999, "train"), (60000, "train")):
        with pytest.raises(ValueError):
            G.make_map(bad, purpose)


def test_water_layers_consistent():
    m = G.make_map(50003, overrides={"water": "river", "shape": "hills"})
    wet = m.water_sys > 0
    assert wet.any()
    assert np.all(m.water_bed_z[wet] <= m.ground_z[wet] + 1e-4)
    assert np.all(m.water_surf0_z[wet] > m.water_bed_z[wet])
    ys, xs = np.nonzero(wet)
    d = m.depth(xs + 0.5, ys + 0.5, 0.0)
    assert (d > 0).all()
    assert m.depth(0.5, 0.5, 0.0) >= 0.0
    assert (m.food_cap[T.FOOD_KINDS.index("aquatic")][~wet] == 0).all()


def test_map_card_roundtrip(tmp_path):
    m = G.make_map(50011)
    m.save(tmp_path / "m.npz")
    r = T.load_map(tmp_path / "m.npz")
    for k in T.LAYERS:
        assert np.array_equal(getattr(m, k), getattr(r, k))
    assert r.water == m.water and r.meta["seed"] == 50011


def test_rotation_moves_points_and_vectors_together():
    m = T.blank_map(7, 5)
    m.ground_z[1, 5] = 9.0
    m.current[1, 5] = (0.3, 0.1)
    for k in range(4):
        r = T.rotate90(m, k)
        x, y = T.rotate_xy(5.5, 1.5, k, *m.size_m)
        assert float(r.height(x, y)) == 9.0
        assert np.allclose(r.current_at(x, y), T.rotate_vec(0.3, 0.1, k))


def test_water_cycle_offset():
    wc = T.WaterCycle(amp_m=1.0, rise_s=10, high_s=10, fall_s=10, low_s=10)
    assert wc.offset(0.0) == pytest.approx(-0.5) and wc.offset(15.0) == pytest.approx(0.5) and wc.offset(35.0) == pytest.approx(-0.5)
    assert T.WaterCycle(rain_rise_m=0.4).offset(3.0, rain=0.5) == pytest.approx(0.2)


# ----------------------------------------------------------------------------- 종 카드

def test_random_cards_valid_and_body_vector_in_range():
    rng = np.random.default_rng(3)
    for i in range(200):
        c = S.random_card(rng, i)
        assert not S.validate(c)
        v = S.body_vector(c)
        assert v.shape == (17,) and v.min() >= 0.0 and v.max() <= 1.0


def test_validate_catches_bad_cards():
    good = S.random_card(np.random.default_rng(0), 0)
    for path, value, word in ((("body", "mass_kg"), -1.0, "mass_kg"), (("medium", "swim"), None, "swim"),
                              (("combat", "kill_mass_ratio"), 1.0, None)):
        c = copy.deepcopy(good)
        c[path[0]][path[1]] = value
        if path == ("combat", "kill_mass_ratio"):
            c["diet"]["meat"] = 0.0
            assert any("does not eat meat" in p for p in S.validate(c))
        else:
            assert any(word in p for p in S.validate(c))
    c = copy.deepcopy(good)
    c["medium"].update(needs_water=True, swim=False)
    assert any("needs_water" in p for p in S.validate(c))


def test_jitter_stays_in_trained_range():
    c = S.random_card(np.random.default_rng(5), 0)
    c["randomize"] = {"frac": 0.2, "keys": ["body.mass_kg", "body.run_mps"]}
    rng = np.random.default_rng(9)
    rr = S.trained_range(c)
    for _ in range(50):
        j = S.jitter(c, rng)
        for key, (lo, hi) in rr.items():
            g, _, k = key.partition(".")
            assert lo <= j[g][k] <= hi
        assert not S.validate(j)


# ----------------------------------------------------------------------------- 16 종 카드 (species/*.json)

def test_sixteen_cards_load_and_bodies():
    cards = S.load_all()
    assert len(cards) == 16
    for sid, c in cards.items():
        v = S.body_vector(c)
        assert v.min() >= 0.0 and v.max() <= 1.0, sid
        assert c["sources"], sid
    fish = [s for s, c in cards.items() if c["medium"]["needs_water"]]
    fly = [s for s, c in cards.items() if c["medium"]["fly"]]
    assert sorted(fish) == ["ariake_catfish", "common_carp", "small_fish"]
    assert sorted(fly) == ["crow", "golden_eagle"]
    assert cards["mink"]["medium"]["swim"] and cards["mink"]["medium"]["ground"]


def test_prey_pairs_follow_mass_ratio():
    """종 이름 목록 대신 몸무게 비율 하나로 언리얼 사냥 표의 핵심 짝이 나와야 한다 (사양 3 절)."""
    cards = S.load_all()
    mass = {s: c["body"]["mass_kg"] for s, c in cards.items()}

    def can(a, b, frac=1.0):
        return cards[a]["combat"]["kill_mass_ratio"] * mass[a] >= mass[b] * frac

    assert can("wolf", "deer") and not can("wolf", "buffalo") and not can("wolf", "horse")
    assert can("leopard", "boar") and can("leopard", "rat") and not can("leopard", "buffalo") and can("leopard", "buffalo", 0.2)
    assert can("fox", "rat") and can("fox", "crow") and not can("fox", "deer")
    assert can("golden_eagle", "jackrabbit") and can("golden_eagle", "rat")
    assert can("mink", "small_fish") and can("mink", "ariake_catfish") and can("mink", "rat") and not can("mink", "common_carp")
    for herb in ("deer", "buffalo", "horse", "bighorn", "jackrabbit", "rat", "common_carp"):
        assert cards[herb]["combat"]["kill_mass_ratio"] == 0.0
