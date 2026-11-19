"""R10 세계·감각 시험 (0 단계 사양 5·7·10 절): 몸 물리(경사·물·날기·덮치기), 몸으로 정하는 물기, 감각 회전 불변·종 수 불변·결정성."""

import copy
import math

import numpy as np
import pytest

from r10 import contract as C
from r10 import mapgen as G
from r10 import senses as O
from r10 import species as S
from r10 import terrain as T
from r10 import world as W


def card(kind="ground", mass=50.0, kill=0.0, **body):
    c = S.random_card(np.random.default_rng(0), 0)
    c["id"] = f"t_{kind}_{mass}"
    m = c["medium"]
    m.update(ground=kind in ("ground", "air", "amph"), swim=kind in ("fish", "amph"), fly=kind == "air",
             needs_water=kind == "fish", wade_depth_m=0.3, swim_depth_frac=0.5 if kind in ("fish", "amph") else None,
             cruise_height_m=10.0 if kind == "air" else None, ceiling_m=30.0 if kind == "air" else None,
             takeoff_s=0.6 if kind == "air" else None)
    b = c["body"]
    b.update(mass_kg=mass, radius_m=0.3, walk_mps=1.0, run_mps=4.0, accel_mps2=20.0, turn_dps=720.0, lat_accel_mps2=40.0,
             max_slope_deg=35.0, step_m=0.2, swim_mps=1.0 if kind in ("fish", "amph") else None,
             swim_fast_mps=2.0 if kind in ("fish", "amph") else None, fly_mps=4.0 if kind == "air" else None,
             cruise_mps=8.0 if kind == "air" else None, dive_mps=15.0 if kind == "air" else None,
             burst_mps=None, burst_s=None, burst_exhaust_mps=None, burst_exhaust_s=None)
    b.update(body)
    c["diet"] = {k: 0.0 for k in S.DIET_KEYS}
    c["diet"].update(grass=1.0) if kill == 0 else c["diet"].update(meat=1.0, carrion=1.0)
    c["combat"].update(kill_mass_ratio=kill, reach_m=0.5, attack_cd_s=1.0, defense=0.0)
    c["metabolism"].update(swim_cost=2.0 if kind in ("fish", "amph") else None, fly_cost=3.0 if kind == "air" else None)
    c["randomize"] = {"frac": 0.0, "keys": []}
    assert not S.validate(c), S.validate(c)
    return c


def world_of(m, cards, slots=8, seed=0):
    ros = W.Roster([(c, 0, 1) for c in cards])
    w = W.World([m], [ros], slots=slots, seed=seed, train=False, jitter=False)
    return w


def put(w, i, x, y, heading=0.0, z=None, airborne=False):
    w._spawn(i)                                   # 살리고 기본값
    w.x[i], w.y[i] = x, y
    w.hx[i], w.hy[i] = math.cos(heading), math.sin(heading)
    w.speed[i] = 0.0
    w.airborne[i] = airborne
    c = w.cidx(np.array([0]), np.array([x]), np.array([y]))
    sw = w.p["needs_water"][i] or (w.p["swim"][i] and w.depth_at(c)[0] > w.p["wade_depth_m"][i])
    w.swimming[i] = bool(sw)
    if z is not None:
        w.z[i] = z
    elif sw:
        bed, surf = w.g_bed[c][0], w.surface_at(c)[0]
        w.z[i] = (bed + surf) / 2
    else:
        w.z[i] = 0.0
    w.E[i] = 0.9


def run(w, acts: dict, n=10):
    for _ in range(n):
        a = np.full(w.N, C.A_WATCH)
        for i, v in acts.items():
            a[i] = v
        w.step(a)


EAST_FAST = C.A_FAST0          # 머리 방향(j = 0)으로 빠르게


def test_steep_slope_blocks_low_step_body():
    m = T.blank_map(30, 10)
    m.ground_z[:, 15:] = 1.5                      # 1.5 m 턱
    w = world_of(m, [card(step_m=0.2), card(step_m=2.0)])
    put(w, 0, 10.5, 5.5)
    put(w, 1, 10.5, 4.5)
    run(w, {0: EAST_FAST, 1: EAST_FAST}, 12)
    assert w.x[0] < 15.0 and w.x[1] > 15.0


def test_water_depth_wade_swim_and_fish():
    m = T.blank_map(30, 10)
    m.water_sys[:, 15:] = 1
    m.water_bed_z[:, 15:] = -1.0
    m.ground_z[:, 15:] = -1.0
    m.water_surf0_z[:, 15:] = 0.0                 # 깊이 1 m
    w = world_of(m, [card("ground"), card("amph"), card("fish")])
    put(w, 0, 10.5, 2.5)
    put(w, 1, 10.5, 5.5)
    put(w, 2, 20.5, 8.5, heading=math.pi)          # 물고기는 서쪽(뭍)으로
    run(w, {0: EAST_FAST, 1: EAST_FAST, 2: EAST_FAST}, 15)
    assert w.x[0] < 15.0                           # 걷기 깊이 0.3 < 1 m: 못 들어감
    assert w.x[1] > 15.0 and w.swimming[1]         # 헤엄 몸: 들어가 헤엄
    assert w.x[2] >= 15.0 and w.alive[2]           # 물고기: 뭍으로 못 나감


def test_takeoff_canopy_and_no_landing_on_water():
    m = T.blank_map(30, 10)
    m.canopy[:, :5] = 1
    m.water_sys[:, 20:] = 1
    m.water_bed_z[:, 20:] = -1.0
    m.ground_z[:, 20:] = -1.0
    m.water_surf0_z[:, 20:] = 0.0
    w = world_of(m, [card("air"), card("air")])
    put(w, 0, 2.5, 5.5)
    put(w, 1, 10.5, 5.5)
    run(w, {0: C.A_UP, 1: C.A_UP}, 6)
    assert not w.airborne[0] and w.airborne[1] and w.z[1] > 1.0
    # 물 위로 날아가 내리기: 물 위에서는 내려앉지 못하고 맴돈다
    w.x[1] = 25.5
    run(w, {1: C.A_DOWN}, 40)
    assert w.airborne[1] and w.z[1] == pytest.approx(w.rules.hover_m)
    w.x[1] = 12.5
    run(w, {1: C.A_DOWN}, 20)
    assert not w.airborne[1] and w.z[1] == 0.0


def test_bite_by_mass_ratio_not_by_name():
    m = T.blank_map(40, 20)
    hunter = card("ground", 60.0, kill=1.6)
    small, big = card("ground", 30.0), card("ground", 450.0)
    w = world_of(m, [hunter, small, big, hunter])
    put(w, 0, 10.0, 5.0)
    put(w, 1, 11.0, 5.0)
    put(w, 3, 10.0, 15.0)
    put(w, 2, 11.0, 15.0)
    w.E[:] = 0.9
    run(w, {0: EAST_FAST, 3: EAST_FAST}, 3)
    assert not w.alive[1] or w.hp[1] < 1.0          # 30 kg ≤ 60 × 1.6: 물림
    assert w.alive[2] and w.hp[2] == 1.0            # 450 kg > 96: 못 묾
    assert any(d[4] == "bitten" for d in w.events["deaths"]) or w.hp[1] < 1.0


def test_no_bite_across_medium_or_same_species():
    m = T.blank_map(30, 10)
    m.water_sys[:, 15:] = 1
    m.water_bed_z[:, 15:] = -1.0
    m.ground_z[:, 15:] = -1.0
    m.water_surf0_z[:, 15:] = 0.0
    hunter = card("ground", 60.0, kill=2.0)
    w = world_of(m, [hunter, card("fish", 1.0)])
    put(w, 0, 14.6, 5.0)
    put(w, 1, 15.4, 5.0)
    w.slot_same = None
    run(w, {0: EAST_FAST}, 3)
    assert w.alive[1] and w.hp[1] == 1.0
    w2 = world_of(T.blank_map(30, 10), [hunter])
    w2.cap[0][0] = 2
    put(w2, 0, 10.0, 5.0)
    w2.sp[1] = 0
    put(w2, 1, 10.8, 5.0)
    run(w2, {0: EAST_FAST}, 3)
    assert w2.alive[1] and w2.hp[1] == 1.0


def _world_on(m, seed=3):
    rng = np.random.default_rng(seed)
    cards = [card("ground", 50.0), card("ground", 60.0, kill=1.6), card("amph", 1.0), card("air", 5.0), card("fish", 0.5)]
    w = world_of(m, cards, slots=10, seed=seed)
    k = 0
    W_, H_ = m.size_m
    for i in range(5):
        for _ in range(200):
            x, y = rng.uniform(1, W_ - 1), rng.uniform(1, H_ - 1)
            if w._place_ok(np.array([i]), np.array([x]), np.array([y]))[0]:
                put(w, i, x, y, heading=rng.uniform(0, 2 * math.pi))
                break
    return w


def test_observation_rotation_invariant():
    m = G.make_map(50003, overrides={"water": "river", "shape": "hills", "w": 70, "h": 70})
    w = _world_on(m)
    o = O.observe(w)
    for k in (1, 2, 3):
        r = T.rotate90(m, k)
        w2 = world_of(r, [c for c in w.base_cards[0]], slots=10, seed=3)
        for i in range(w.N):
            if not w.alive[i]:
                continue
            x, y = T.rotate_xy(w.x[i], w.y[i], k, *m.size_m)
            hx, hy = T.rotate_vec(w.hx[i], w.hy[i], k)
            put(w2, i, float(x), float(y), heading=math.atan2(float(hy), float(hx)), z=w.z[i], airborne=bool(w.airborne[i]))
            w2.swimming[i] = w.swimming[i]
            for a in ("E", "R", "stam", "hp", "age_days", "speed", "breath"):
                getattr(w2, a)[i] = getattr(w, a)[i]
            w2.sex[i] = w.sex[i]
            w2.vx[i], w2.vy[i] = T.rotate_vec(w.vx[i], w.vy[i], k)
        w2.weather[:] = w.weather
        w2.t = w.t
        o2 = O.observe(w2)
        assert o2.shape == o.shape
        assert np.allclose(o, o2, atol=1e-4), (k, np.argwhere(~np.isclose(o, o2, atol=1e-4))[:10])


def test_obs_size_independent_of_species_count():
    m = T.blank_map(40, 40)
    for n in (1, 3, 16):
        cards = [S.random_card(np.random.default_rng(n * 100 + i), i) for i in range(n)]
        w = W.World([m], [W.Roster([(c, 1, 1) for c in cards])], slots=16, seed=1, train=False, jitter=False)
        assert O.observe(w).shape == (16, C.OBS_DIM)


def test_deterministic_trajectories():
    def go():
        rng = np.random.default_rng(11)
        maps = [G.make_map(50000 + k) for k in range(2)]
        ros = [W.Roster([(S.random_card(np.random.default_rng(100 + s), s), 3, 4) for s in range(4)]) for _ in maps]
        w = W.World(maps, ros, slots=16, seed=5)
        out = []
        for _ in range(30):
            a = np.array([rng.choice(np.nonzero(w.amask[i])[0]) for i in range(w.N)])
            w.step(a)
            out.append(O.observe(w).copy())
        return np.stack(out), w.x.copy(), list(w.events["deaths"])
    a, b = go(), go()
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]) and a[2] == b[2]


def test_dead_slots_zero_and_masks_applied():
    m = T.blank_map(40, 40)
    w = world_of(m, [card("ground"), card("fish")])
    put(w, 0, 10.0, 10.0)
    o = O.observe(w)
    assert not o[1].any()                          # 물 없는 맵: 물고기 자리 없음 → 빈 칸
    idx = {n: i for i, n in enumerate(C.OBS_NAMES)}
    assert o[0, idx["air_height"]] == 0 and o[0, idx["breath"]] == 0
    assert not o[0, C.SLICES["spare"][0]:C.SLICES["spare"][1]].any()


POUNCE = dict(burst_mps=13.5, burst_s=1.6, burst_exhaust_mps=1.8, burst_exhaust_s=4.0)


def test_burst_fast_then_exhaust_then_ready():
    """덮치기: burst_s 동안 run 보다 빠르게, 뒤에 지침(속력 상한), 지침이 끝나면 다시 준비. 마스크·감각도 그 상태를 따른다."""
    from r10 import policy as P
    m = T.blank_map(80, 10)
    w = world_of(m, [card(**POUNCE), card()])
    put(w, 0, 5.0, 3.0)
    put(w, 1, 5.0, 7.0)
    idx = {n: i for i, n in enumerate(C.OBS_NAMES)}
    o = O.observe(w)
    assert o[0, idx["burst_ready"]] == 1.0 and o[1, idx["burst_ready"]] == 0.0
    mk = P.mask_from_obs(o)
    assert mk[0, C.A_BURST] and not mk[1, C.A_BURST]                 # 덮치기 없는 몸은 못 고름
    assert not w.amask[1, C.A_BURST]
    run(w, {0: C.A_BURST, 1: EAST_FAST}, 6)                           # 12 걸음 = 1.6 s
    assert w.x[0] - 5.0 > 1.6 * 4.0 * 2.0                             # 같은 시간 뛰기(4 m/s)의 두 배 넘게
    assert w.burst_left[0] == 0.0 and w.exhaust_left[0] == pytest.approx(4.0)
    o = O.observe(w)
    assert o[0, idx["burst_ready"]] == 0.0 and o[0, idx["burst_phase"]] < 0
    assert not P.mask_from_obs(o)[0, C.A_BURST]                       # 지친 중에는 막힘
    run(w, {0: EAST_FAST}, 5)
    assert w.speed[0] <= 1.8 + 1e-6                                   # 지친 중: 뛰어도 상한
    run(w, {0: EAST_FAST}, 10)                                         # 4 s 지나면
    assert w.exhaust_left[0] == 0.0 and w.burst_ready()[0]
    assert O.observe(w)[0, idx["burst_ready"]] == 1.0


def test_burst_bite_ends_burst():
    """덮쳐 물면 덮치기가 끝나고 지침으로 (언리얼 Native: 잡으면 Exhaust)."""
    m = T.blank_map(60, 10)
    hunter = card("ground", 40.0, kill=1.6, **POUNCE)
    prey = card("ground", 30.0)
    w = world_of(m, [hunter, prey])
    put(w, 0, 5.0, 5.0)
    put(w, 1, 12.0, 5.0)
    run(w, {0: C.A_BURST}, 1)
    assert w.burst_left[0] > 0 or w.exhaust_left[0] > 0
    run(w, {0: C.A_BURST}, 5)
    assert any(b[2] == w.uid[0] for b in w.events["bites"])
    assert w.burst_left[0] == 0.0 and w.exhaust_left[0] > 0.0


def test_carcass_shows_in_food_direction():
    """고기를 먹는 몸은 먹이 감각 반경 안 사체를 그 방향 '먹이' 칸으로 느낀다 (풀 먹는 몸은 못 느낌)."""
    m = T.blank_map(60, 20)
    hunter = card("ground", 40.0, kill=1.6)
    hunter["diet"] = {k: 0.0 for k in S.DIET_KEYS} | {"meat": 1.0, "carrion": 1.0}
    grazer = card("ground", 30.0)
    w = world_of(m, [hunter, grazer])
    put(w, 0, 10.0, 10.0)
    put(w, 1, 30.0, 10.0)
    w.hx[:], w.hy[:] = 1.0, 0.0
    lo = C.SLICES["dir"][0]
    f0 = lambda o, i, j: o[i, lo + j * len(C.DIR_FIELDS) + 5]
    o = O.observe(w)
    base0, base_left = f0(o, 0, 0), f0(o, 0, 2)
    ci = 0
    w.carcass["wk"][ci], w.carcass["x"][ci], w.carcass["y"][ci] = 0, 15.0, 10.0
    w.carcass["meat"][ci], w.carcass["kin"][ci] = 20.0, 1
    o = O.observe(w)
    assert f0(o, 0, 0) > base0 + 0.5          # 앞(0°)
    assert abs(f0(o, 0, 2) - base_left) < 1e-9  # 왼쪽(90°) 그대로
    w.carcass["x"][ci], w.carcass["y"][ci] = 10.0, 15.0
    o = O.observe(w)
    assert f0(o, 0, 2) > base_left + 0.5      # 왼쪽
    assert abs(f0(o, 1, 4) - f0(O.observe(w), 1, 4)) < 1e-9
