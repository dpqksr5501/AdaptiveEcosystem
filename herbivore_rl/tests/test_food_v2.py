"""V2 0-6 — v2.0b 먹이 2층 food_v (계획서 4.9.1, 4.8 새 단위 테스트).

훼손이 (1 − F/V) 에 비례, 휴식 회복 반감기, 하한, 불변식 0 ≤ F ≤ V ≤ cap0, 지역 비율 ΣF/Σcap0,
cap0 = 0 셀, 가드를 단 조밀 참조(C++ 모양) = 희소 구현, 결정성, 끈 상태 = v1, 끔 값(α 0·초기 V = cap0)
= v2.0, 난수는 food_v 스트림에서만, v2.0b 기본 실행 이름.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import pickle

import numpy as np
import pytest

from env.config import ROOT, load_config
from env.world import World as WorldV1
from env_v2.config import load_v2_config
from env_v2.features import feature_stream
from env_v2.vec_env import MultiWorldVecEnv
from env_v2.world import ACT_DIM, FOOD_V_FLOOR_TOL, World
from policies.registry import make_policy

V2_0B = ROOT / "configs" / "v2_0b.yaml"


@pytest.fixture(scope="module")
def cfg_b():
    return load_v2_config(V2_0B)


def _fv(cfg, enabled=True, **kw):
    """v2_0b.yaml 의 food_v 블록에서 계수 일부만 바꾼 설정."""
    block = dict(cfg.v2["features"]["food_v"], enabled=enabled, **kw)
    return cfg.replace(v2=dict(cfg.v2, features={"food_v": block}))


def _invariants(w):
    F, V, c = w.food, w.food_v, w.food_cap
    assert (F >= 0.0).all() and (F <= V).all() and (V <= c).all()
    assert (V >= w._fv["floor"] * c).all()
    assert (V[c == 0.0] == 0.0).all() and (F[c == 0.0] == 0.0).all()


def _isolate(w):
    """재생·회복을 멈춰 7a~7c(훼손·하한·F ≤ V)만 보이게 한다."""
    w.regen_field = np.zeros_like(w.regen_field)
    w.food_v_rho = 0.0


def _rich_cells(w, n):
    return np.flatnonzero(w.food_cap.reshape(-1) > 0.5)[:n]


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


def test_v2_0b_config_is_v2_plus_food_v(cfg_b):
    """v2_0b.yaml = v2.yaml + food_v. 학습 설정·v1 키는 같고, v2.yaml 은 여전히 모두 끈 v2.0 기록이다."""
    v20 = load_v2_config()
    assert cfg_b.v2["version"] == "2.0b"
    assert cfg_b.v2["train"] == v20.v2["train"]
    assert World(cfg_b, seeds=[0]).features.active == ("food_v",)
    assert World(v20, seeds=[0]).features.active == ()
    for k, v in load_config().to_dict().items():
        assert getattr(cfg_b, k) == v, k
    assert set(cfg_b.v2["features"]["food_v"]) == {
        "enabled", "alpha", "floor", "recovery_half_lives", "init_frac"}


@pytest.mark.parametrize("kw", [
    {"alpha": -0.1}, {"alpha": True}, {"alpha": float("nan")},
    {"floor": 1.5}, {"floor": -0.1},
    {"recovery_half_lives": []}, {"recovery_half_lives": 700}, {"recovery_half_lives": [300, 0]},
    {"recovery_half_lives": [float("inf")]},
    {"init_frac": [0.05, 1.0]},                 # 하가 하한(floor 0.1) 아래
    {"init_frac": [0.9, 0.3]}, {"init_frac": [0.3, 1.2]}, {"init_frac": [0.3]}, {"init_frac": 0.3},
])
def test_bad_params_fail_at_world_creation(cfg_b, kw):
    with pytest.raises(ValueError):
        World(_fv(cfg_b, **kw), seeds=[0])


def test_missing_param_fails_at_load(tmp_path):
    text = V2_0B.read_text(encoding="utf-8").replace("    init_frac: [0.3, 1.0]\n", "")
    p = tmp_path / "v2_0b.yaml"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="init_frac"):
        load_v2_config(p)


def test_default_run_name_follows_config_version(cfg_b):
    """--run-name 없이 학습해도 v2.0b 체크포인트가 v2.0 이름(v2_0_s0_20m)을 덮지 않는다."""
    from train_v2 import default_run_name
    assert default_run_name(load_v2_config(), 0, 20_000_000) == "v2_0_s0_20m"      # v2.0 은 예전 이름 그대로
    assert default_run_name(cfg_b, 0, 20_000_000) == "v2_0b_s0_20m"
    no_ver = cfg_b.replace(v2={k: v for k, v in cfg_b.v2.items() if k != "version"})
    assert default_run_name(no_ver, 2, 10_000_000) == "v2_0_s2_10m"                 # version 은 선택 키


# --------------------------------------------------------------------- #
# 훼손 · 하한 · 회복
# --------------------------------------------------------------------- #


def test_damage_is_proportional_to_depletion(cfg_b):
    """V −= α·taken·(1 − F/V), F 는 섭취 직후 값. 같은 섭취량이면 이미 뜯긴 셀이 더 깎인다."""
    w = World(_fv(cfg_b, alpha=0.5), seeds=[636])
    _isolate(w)
    k = _rich_cells(w, 4)
    c = w.food_cap.reshape(-1)[k]
    V0 = 0.8 * c
    F0 = V0 * np.array([0.9, 0.6, 0.3, 0.0])          # 섭취 직후 F/V
    w.food_v.reshape(-1)[k] = V0
    w.food.reshape(-1)[k] = F0
    taken = np.zeros(w.gw * w.gw)
    taken[k] = 0.05
    w._fv_taken = taken
    V_before = w.food_v.copy()
    w._food_v_step()

    dV = V_before.reshape(-1) - w.food_v.reshape(-1)
    np.testing.assert_allclose(dV[k], 0.5 * 0.05 * (1.0 - F0 / V0), rtol=1e-12)
    np.testing.assert_allclose(dV[k] / (1.0 - F0 / V0), 0.5 * 0.05, rtol=1e-12)
    assert np.all(np.diff(dV[k]) > 0)                  # 덜 남은 셀일수록 많이 깎인다
    rest = np.ones(w.gw * w.gw, dtype=bool)
    rest[k] = False
    assert (dV[rest] == 0.0).all()                     # 안 먹힌 셀은 그대로 (회복을 멈춘 상태)


def test_floor_and_f_cap_after_damage(cfg_b):
    """하한 V ≥ floor·cap0 (7b), α > 1 이면 V 가 F 아래로 내려갈 수 있어 F ← min(F, V) (7c)."""
    w = World(_fv(cfg_b, alpha=3.0, floor=0.1), seeds=[636])
    _isolate(w)
    k = _rich_cells(w, 3)
    c = w.food_cap.reshape(-1)[k]
    # 셀별 (섭취 전 V, 섭취 직후 F, taken) — 섭취 전 F = F + taken ≤ V
    V0 = np.array([0.2, 0.11, 0.6]) * c
    F0 = np.array([0.15, 0.0, 0.3]) * c
    tk = np.array([0.05, 0.05, 0.3]) * c
    w.food_v.reshape(-1)[k] = V0
    w.food.reshape(-1)[k] = F0
    taken = np.zeros(w.gw * w.gw)
    taken[k] = tk
    w._fv_taken = taken
    w._food_v_step()
    V, F = w.food_v.reshape(-1)[k], w.food.reshape(-1)[k]
    # 0: 깎임 3·0.05·0.25 = 0.0375·c → V 0.1625·c. 하한 위, F 0.15·c 보다 크다 — 그대로
    np.testing.assert_allclose(V[0], 0.1625 * c[0], rtol=1e-12)
    assert F[0] == F0[0]
    # 1: 깎임 3·0.05·1 = 0.15·c → 음수 → 하한 0.1·c 에 정확히 붙는다 (회복을 멈춘 상태)
    assert V[1] == 0.1 * c[1] and F[1] == 0.0
    # 2: 깎임 3·0.3·0.5 = 0.45·c → V 0.15·c 가 F 0.3·c 아래 → F 가 V 로 잘린다 (α > 1 에서만)
    np.testing.assert_allclose(V[2], 0.15 * c[2], rtol=1e-12)
    assert F[2] == V[2]


@pytest.mark.parametrize("h", [300, 700])
def test_recovery_half_life_matches_config(cfg_b, h):
    """섭식이 없으면 cap0 − V 가 h 스텝마다 절반이 된다 (ρ = 1 − 2^(−1/h)). 실제 step() 경로로 본다."""
    cfg = _fv(cfg_b, recovery_half_lives=[h], init_frac=[0.3, 0.3]).replace(food_eat_rate=0.0)
    w = World(cfg, seeds=[636])
    assert w.food_v_half_life == h and w.food_v_rho == pytest.approx(1.0 - 2.0 ** (-1.0 / h), rel=1e-15)
    pos = w.food_cap > 0
    gap0 = (w.food_cap - w.food_v)[pos]
    act = np.full((w.N, ACT_DIM), 0.5)
    for t in range(1, 2 * h + 1):
        w.step(act)
        assert (w._fv_taken == 0.0).all()
        if t in (h, 2 * h):
            ratio = (w.food_cap - w.food_v)[pos] / gap0
            np.testing.assert_allclose(ratio, 0.5 ** (t // h), rtol=1e-9)
    _invariants(w)
    assert (w.food_cells()["last_eat"] == -1).all() and (w.food_cells()["eaten"] == 0.0).all()


def test_no_damage_and_full_init_is_v2_0(cfg_b):
    """규칙 5 의 '끔' 값: α = 0 이고 V 초기값이 cap0(init_frac [1, 1])면 V ≡ cap0 라 v2.0(= v1)과 비트 동일."""
    on = World(_fv(cfg_b, alpha=0.0, init_frac=[1.0, 1.0]), seeds=[636])
    v1 = WorldV1(load_config(), seeds=[636])
    p_on, p_v1 = make_policy({"kind": "utility"}), make_policy({"kind": "utility"})
    for _ in range(300):
        o_on, o_v1 = on.observe(), v1.observe()
        np.testing.assert_array_equal(o_on, o_v1)
        on.step(p_on(o_on))
        v1.step(p_v1(o_v1))
    np.testing.assert_array_equal(on.food, v1.food)
    np.testing.assert_array_equal(on.food_v, on.food_cap)
    assert on.stats() == v1.stats()
    assert on.food_cells()["eaten"].sum() > 0          # 먹기는 했다 — 훼손 경로를 실제로 탔다


# --------------------------------------------------------------------- #
# 불변식 · 통계
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("seed, spec, kw", [
    (636, {"kind": "utility"}, {}),
    (0, {"kind": "random", "seed": 2}, {}),
    (10000, {"kind": "fixed", "action": [1.0, 0.8, 0.4, 0.0]}, {"alpha": 2.0, "recovery_half_lives": [20]}),
])
def test_invariants_hold_over_long_rollout(cfg_b, seed, spec, kw):
    """매 스텝 0 ≤ F ≤ V ≤ cap0, V ≥ floor·cap0, cap0 = 0 셀은 F = V = 0. 나눗셈 경고도 없다."""
    w = World(_fv(cfg_b, **kw), seeds=[seed])
    p = make_policy(spec)
    _invariants(w)
    with np.errstate(divide="raise", invalid="raise"):
        for _ in range(2000):
            w.step(p(w.observe()))
            _invariants(w)
    s = w.food_stats()
    assert 0.0 < s["v_ratio"] < 1.0 and s["eaten"] > 0.0


def test_food_stats_definitions(cfg_b):
    """지역 비율 = ΣF/Σcap0 (cap0 > 0 셀), 절반은 셀 중심 x < size/2. 전체는 두 절반의 cap0 가중 평균이다."""
    w = World(cfg_b, seeds=[636])
    p = make_policy({"kind": "utility"})
    for _ in range(400):
        w.step(p(w.observe()))
    s, cells = w.food_stats(), w.food_cells()
    c, F, V = cells["food_cap"], cells["food"], cells["food_v"]
    left = cells["left"]
    np.testing.assert_array_equal(left, w._cell_x < w.size / 2)
    pos = c > 0
    floor = w._fv["floor"]
    for sfx, m in (("", pos), ("_left", pos & left), ("_right", pos & ~left)):
        assert s["f_ratio" + sfx] == pytest.approx(F[m].sum() / c[m].sum(), rel=1e-12)
        assert s["v_ratio" + sfx] == pytest.approx(V[m].sum() / c[m].sum(), rel=1e-12)
        assert s["v_cell_mean" + sfx] == pytest.approx((V[m] / c[m]).mean(), rel=1e-12)
        assert s["floor_frac" + sfx] == pytest.approx(
            (V[m] / c[m] <= floor + FOOD_V_FLOOR_TOL).mean(), rel=1e-12)
        assert s["eaten" + sfx] == pytest.approx(cells["eaten"][m].sum(), rel=1e-12)
    cl, cr = c[pos & left].sum(), c[pos & ~left].sum()
    assert s["f_ratio"] == pytest.approx((s["f_ratio_left"] * cl + s["f_ratio_right"] * cr) / (cl + cr))
    assert s["half_life"] == w.food_v_half_life and s["rho"] == w.food_v_rho
    assert (s["init_left"], s["init_right"]) == w.food_v_init

    # 끈 세계: V = cap0 로 보고, 하한·기록이 없는 열은 nan
    off = World(_fv(cfg_b, enabled=False), seeds=[636])
    so = off.food_stats()
    assert so["v_ratio"] == 1.0 and so["v_cell_mean_left"] == 1.0
    assert all(np.isnan(so[k]) for k in ("floor_frac", "eaten", "half_life", "rho", "init_left"))
    assert so["f_ratio"] == pytest.approx(off.food[pos].sum() / off.food_cap[pos].sum())
    assert off.food_cells()["eaten"] is None


def test_bookkeeping_eaten_and_last_eat(cfg_b):
    """eaten = reset 뒤 셀별 섭취량 합, last_eat = 마지막으로 뜯긴 스텝의 self.t."""
    w = World(cfg_b, seeds=[3])
    p = make_policy({"kind": "utility"})
    acc = np.zeros(w.gw * w.gw)
    last = np.full(w.gw * w.gw, -1)
    for _ in range(150):
        w.step(p(w.observe()))
        acc += w._fv_taken
        last[w._fv_taken > 0] = w.t
    cells = w.food_cells()
    np.testing.assert_array_equal(cells["eaten"].reshape(-1), acc)
    np.testing.assert_array_equal(cells["last_eat"].reshape(-1), last)
    assert (last > 0).any()


def test_cap0_zero_cells_are_safe(cfg_b):
    """cap0 = 0 셀은 F = V = 0 이고 0 나눗셈이 없다. 절반 전체가 cap0 = 0 이면 그 절반의 통계는 nan."""
    w = World(cfg_b, seeds=[636])
    assert (w.food_cap == 0).any()
    w.food_cap[w._left_half()] = 0.0                   # 왼쪽 절반을 맨땅으로 만들고 다시 시작한다
    w.food[...] = w.food_cap
    w._food_v_reset()
    p = make_policy({"kind": "utility"})
    with np.errstate(divide="raise", invalid="raise"):
        for _ in range(200):
            w.step(p(w.observe()))
            _invariants(w)
        s = w.food_stats()
    assert all(np.isnan(s[k + "_left"]) for k in ("v_ratio", "f_ratio", "v_cell_mean", "floor_frac", "eaten"))
    assert np.isfinite(s["v_ratio"]) and s["v_ratio"] == pytest.approx(s["v_ratio_right"])


def _dense_reference(w, guard):
    """`_food_v_step` 7a~7e 를 모든 셀에 조밀하게 계산한 참조(C++ 이식 모양). 스텝 전 상태에서 부른다."""
    F, V, tk = w.food.reshape(-1).copy(), w.food_v.reshape(-1).copy(), w._fv_taken
    with np.errstate(divide="ignore", invalid="ignore"):
        nv = np.maximum(V - w._fv["alpha"] * tk * (1.0 - F / V), w._fv_floor.reshape(-1))
    nf = np.minimum(F, nv)
    if guard:                                          # if (Taken > 0) — 안 먹힌 셀은 7a~7c 를 건너뛴다
        nv, nf = np.where(tk > 0.0, nv, V), np.where(tk > 0.0, nf, F)
    F = np.minimum(nf + w.regen_field.reshape(-1) * (nv - nf), nv)
    V = nv + w.food_v_rho * (w.food_cap.reshape(-1) - nv)
    return F, V


def test_dense_guarded_reference_matches_sparse(cfg_b):
    """C++ 이식 참조: 조밀 계산에 `taken > 0` 가드를 달면 희소 구현(먹힌 셀만)과 비트 단위로 같다.
    가드가 없으면 cap0 = 0 셀(V = F = 0)에서 0·(1 − 0/0) = NaN 이 난다 — 가드는 최적화가 아니라 필수다."""
    seen = dict(steps=0, mismatch=0, nan=0)

    class Probe(World):
        def _food_v_step(self):
            ref, raw = _dense_reference(self, True), _dense_reference(self, False)
            super()._food_v_step()
            seen["steps"] += 1
            seen["mismatch"] += int((ref[0] != self.food.reshape(-1)).sum()
                                    + (ref[1] != self.food_v.reshape(-1)).sum())
            seen["nan"] += int(np.isnan(raw[0]).sum() + np.isnan(raw[1]).sum())

    w = Probe(cfg_b, seeds=[636])
    assert (w.food_cap == 0).any()
    p = make_policy({"kind": "utility"})
    for _ in range(500):
        w.step(p(w.observe()))
    assert seen["steps"] == 500 and seen["mismatch"] == 0
    assert seen["nan"] > 0


# --------------------------------------------------------------------- #
# 결정성 · v1 동일 · 세계 변화 · 난수
# --------------------------------------------------------------------- #


def _run(cfg, seed, steps=300, spec=None):
    w = World(cfg, seeds=[seed])
    p = make_policy(spec or {"kind": "utility"})
    for _ in range(steps):
        w.step(p(w.observe()))
    return w


def test_same_seed_is_deterministic(cfg_b):
    a, b = _run(cfg_b, 77), _run(cfg_b, 77)
    np.testing.assert_array_equal(a.food, b.food)
    np.testing.assert_array_equal(a.food_v, b.food_v)
    np.testing.assert_array_equal(a.pos, b.pos)
    assert a.stats() == b.stats()
    sa, sb = a.food_stats(), b.food_stats()
    assert sa.keys() == sb.keys() and all(sa[k] == sb[k] for k in sa)


@pytest.mark.parametrize("seed", [0, 636, 10000])
def test_food_v_off_is_v1_bitwise(cfg_b, seed):
    """v2_0b 블록을 그대로 두고 enabled 만 끄면 v1 과 비트 단위로 같다 (food_v 코드 경로를 타지 않는다)."""
    off = World(_fv(cfg_b, enabled=False), seeds=[seed])
    assert off._fv is None and not hasattr(off, "food_v")
    v1 = WorldV1(load_config(), seeds=[seed])
    p_off, p_v1 = make_policy({"kind": "random", "seed": 5}), make_policy({"kind": "random", "seed": 5})
    for _ in range(300):
        o_off, o_v1 = off.observe(), v1.observe()
        np.testing.assert_array_equal(o_off, o_v1)
        off.step(p_off(o_off))
        v1.step(p_v1(o_v1))
    np.testing.assert_array_equal(off.food, v1.food)
    np.testing.assert_array_equal(off.pos, v1.pos)
    assert off.stats() == v1.stats()
    assert not off._feature_rngs                       # 꺼진 기능은 스트림도 만들지 않는다


def test_food_v_on_changes_the_world(cfg_b):
    """켜면 먹이와 개체 궤적이 실제로 달라진다 (켜도 아무 일 없는 실험을 막는다)."""
    on, off = World(cfg_b, seeds=[636]), World(_fv(cfg_b, enabled=False), seeds=[636])
    assert not np.array_equal(on.food, off.food)       # reset 부터 F = min(cap0, V) 가 다르다
    p1, p2 = make_policy({"kind": "utility"}), make_policy({"kind": "utility"})
    for _ in range(300):
        on.step(p1(on.observe()))
        off.step(p2(off.observe()))
    assert not np.array_equal(on.pos, off.pos)
    assert on.stats() != off.stats()
    assert on.food_stats()["v_ratio"] < 1.0 - 1e-3     # 훼손이 V 를 실제로 깎았다


@pytest.mark.parametrize("seed", [0, 5, 636, 10000])
def test_reset_draws_come_from_food_v_stream_only(cfg_b, seed):
    """반감기 고르기 u, 왼쪽·오른쪽 V 초기 비율을 food_v 스트림 part 0 에서 이 순서로 뽑는다.
    v1 스트림은 소비하지 않고, 목록 길이가 달라도 스트림 소비(3개)가 같다."""
    hl = cfg_b.v2["features"]["food_v"]["recovery_half_lives"]
    lo, hi = cfg_b.v2["features"]["food_v"]["init_frac"]
    g = feature_stream(seed, "food_v", 0)
    u = g.random()
    fl, fr = g.uniform(lo, hi, 2)
    w = World(cfg_b, seeds=[seed])
    assert w.food_v_half_life == hl[int(u * len(hl))]
    assert w.food_v_init == (fl, fr)
    left = w._left_half()
    np.testing.assert_array_equal(w.food_v, w.food_cap * np.where(left, fl, fr))
    assert set(w._feature_rngs) == {("food_v", 0)}
    np.testing.assert_array_equal(w.feature_rng("food_v").random(4), g.random(4))  # 정확히 3개 소비

    off = World(_fv(cfg_b, enabled=False), seeds=[seed])
    assert w.rng.bit_generator.state == off.rng.bit_generator.state    # v1 스트림 위치가 같다

    one = World(_fv(cfg_b, recovery_half_lives=[693]), seeds=[seed])
    assert one.food_v_half_life == 693 and one.food_v_init == w.food_v_init   # 목록 하나여도 같은 소비


def test_half_life_choices_cover_the_list(cfg_b):
    hl = cfg_b.v2["features"]["food_v"]["recovery_half_lives"]
    got = {World(cfg_b, seeds=[s]).food_v_half_life for s in range(40)}
    assert got == {float(h) for h in hl}


def test_multiworld_redraws_on_world_renewal(cfg_b):
    """VecEnv 세계마다 자기 시드에서 뽑고, 세계를 새로 뽑으면 V 초기값도 새 시드에서 다시 뽑는다."""
    venv = MultiWorldVecEnv(cfg_b, num_worlds=2, reset_interval=10, meta_seed=0)
    for w in venv.worlds:
        ref = World(cfg_b, seeds=[w.seed])
        assert w.food_v_init == ref.food_v_init and w.food_v_half_life == ref.food_v_half_life
    for _ in range(12):
        venv.step(np.zeros((venv.num_envs, ACT_DIM), dtype=np.float32))
    for w in venv.worlds:
        assert w.food_v_init == World(cfg_b, seeds=[w.seed]).food_v_init
        _invariants(w)


def test_world_with_food_v_pickles_and_deepcopies(cfg_b):
    w = _run(cfg_b, 3, steps=20)
    clones = [pickle.loads(pickle.dumps(w)), copy.deepcopy(w)]
    act = np.full((w.N, ACT_DIM), 0.5)
    for _ in range(30):
        w.step(act)
        for c in clones:
            c.step(act)
    for c in clones:
        np.testing.assert_array_equal(c.food, w.food)
        np.testing.assert_array_equal(c.food_v, w.food_v)
        np.testing.assert_array_equal(c.food_cells()["eaten"], w.food_cells()["eaten"])
        assert c.stats() == w.stats()
        assert c.food_stats() == w.food_stats()


# --------------------------------------------------------------------- #
# speed + food_v 함께 (configs/v2_1_0b.yaml — Gate F R10 고정 정책 확인 전용, 학습 금지)
# --------------------------------------------------------------------- #

V2_1 = ROOT / "configs" / "v2_1.yaml"
V2_1_0B = ROOT / "configs" / "v2_1_0b.yaml"
SPEED = 4                                   # 행동 열 4 = speed (v2.1)


def test_v2_1_0b_config_is_v2_1_plus_food_v(cfg_b):
    """v2_1_0b.yaml = v2_1.yaml + v2_0b.yaml 의 food_v 블록. speed·train·v1 키(덮은 포식자 속도 범위 포함)는 v2.1 과
    같고, food_v 는 키가 같고 α·h 만 R10 R1 후보 값(α 0.03, h 693)이다."""
    c21, c = load_v2_config(V2_1), load_v2_config(V2_1_0B)
    assert c.v2["version"] == "2.1_0b"
    assert c.v2["features"]["speed"] == c21.v2["features"]["speed"] and c.v2["train"] == c21.v2["train"]
    d21, d = c21.to_dict(), c.to_dict()
    assert {k for k in d21.keys() | d.keys() if d21.get(k) != d.get(k)} == {"v2"}
    fv, fb = c.v2["features"]["food_v"], cfg_b.v2["features"]["food_v"]
    same = set(fb) - {"alpha", "recovery_half_lives"}
    assert set(fv) == set(fb) and {k: fv[k] for k in same} == {k: fb[k] for k in same}
    assert fv["alpha"] == 0.03 and fv["floor"] == 0.1 and fv["recovery_half_lives"] == [693]
    w = World(c, seeds=[0])
    assert w.features.active == ("food_v", "speed") and w.act_dim == 5 and w.obs_dim == 7
    assert w.food_v_half_life == 693


@pytest.mark.parametrize("seed", [20001, 636])
def test_speed_and_food_v_coexist(seed):
    """speed 와 food_v 를 함께 켠 첫 설정. 보행 섭식 배수가 섭취량(taken)을 정하고 food_v 훼손·재생·회복이 그
    taken 을 쓴다. 수백 스텝 동안 매 스텝 0 ≤ F ≤ V ≤ cap0, V ≥ floor·cap0 이고 나눗셈 경고가 없다.
    실제 보행이 모두 뛰기인 스텝(섭식 배수 0)은 어느 셀도 뜯기지 않아 V 가 휴식 회복만 하고, 모두 서면 다시 먹는다.
    (명령이 뛰기여도 갈 방향이 없는 개체는 정지로 쳐서 먹으므로 실제 보행 `w.gait` 로 고른다)"""
    w = World(load_v2_config(V2_1_0B), seeds=[seed])
    rng = np.random.default_rng(seed)
    _invariants(w)
    with np.errstate(divide="raise", invalid="raise"):
        for _ in range(400):
            w.step(rng.random((w.N, 5)))
            _invariants(w)
        g = w.gait_stats()
        assert min(g["stop_frac"], g["walk_frac"], g["run_frac"]) > 0.1      # 세 보행이 모두 나왔다
        assert w.food_stats()["v_ratio"] < 1.0 and w.food_cells()["eaten"].sum() > 0.0
        run = rng.random((w.N, 5))
        run[:, SPEED] = 1.0
        all_run = 0
        for _ in range(50):
            e0, v0 = w._fv_eaten.copy(), w.food_v.copy()
            w.step(run)
            _invariants(w)
            if (w.gait == 2).all():
                all_run += 1
                assert not w._fv_taken.any()                                  # 뛰는 개체는 먹지 않는다
                np.testing.assert_array_equal(w._fv_eaten, e0)
                assert (w.food_v >= v0).all()                                 # 훼손 없이 휴식 회복만
        assert all_run >= 10                                                  # 그런 스텝이 실제로 있었다
        stop = run.copy()
        stop[:, SPEED] = 0.0
        e0 = w._fv_eaten.sum()
        for _ in range(50):
            w.step(stop)
            _invariants(w)
        assert (w.gait == 0).all() and w._fv_eaten.sum() > e0


def test_v2_1_0b_with_off_values_is_v2_1_bitwise():
    """α 0 이고 V 초기값이 cap0 면 V ≡ cap0 라 v2_1_0b 세계는 v2.1 세계와 비트 단위로 같다(food_v 가 speed 경로를
    바꾸지 않는다. v2.0 쪽은 test_no_damage_and_full_init_is_v2_0)."""
    c = load_v2_config(V2_1_0B)
    blk = dict(c.v2["features"]["food_v"], alpha=0.0, init_frac=[1.0, 1.0])
    on = World(c.replace(v2=dict(c.v2, features=dict(c.v2["features"], food_v=blk))), seeds=[636])
    ref = World(load_v2_config(V2_1), seeds=[636])
    rng = np.random.default_rng(1)
    for _ in range(300):
        np.testing.assert_array_equal(on.observe(), ref.observe())
        act = rng.random((on.N, 5))
        on.step(act)
        ref.step(act)
    np.testing.assert_array_equal(on.food, ref.food)
    np.testing.assert_array_equal(on.pos, ref.pos)
    np.testing.assert_array_equal(on.food_v, on.food_cap)
    assert on.stats() == ref.stats()
    assert on.gait_stats() == pytest.approx(ref.gait_stats(), nan_ok=True)
    assert on.food_cells()["eaten"].sum() > 0          # 먹기는 했다 — 훼손 경로를 실제로 탔다
