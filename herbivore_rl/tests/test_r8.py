"""R8 파일럿 세계 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R8_LEARN_DANGER_DESIGN.md 12절, 세계 env_v2/r8_world.py).

1. 결정성: 같은 시드·같은 행동 → 관측·보상·위치가 비트 단위로 같다. 함께 도는 세계와 무관하다(묶음 크기·순서).
2. 이름표 없음: 동물 둘의 종류만 맞바꾼 세계 사본의 관측이 비트 단위로 같다(관측 함수가 종류를 읽지 않는다).
3. 짐승은 잡지 않는다(짐승만 있는 세계 잡힘 0).
4. 스텝 끝에 늑대·짐승이 은신처 원(r + margin) 안에 없다. 은신처 안 사슴은 잡히지 않는다.
5. 보상 = 0.01 + ΔE + 10 × 번식 − 10 × 죽음, 다른 항 없음(항마다 무게 하나만 켠 세계 넷의 합 = 기본 보상). 에너지 항 = E 순변화.
6. 행동 뜻: RUN_k = 머리에서 (k − 1) × 45° 반시계로 0.6, EAT = 서거나 0.24, SHELTER = 가장 가까운 은신처 쪽 0.6, WATCH = 0.
7. 다시 난 사슴은 모든 동물에게서 20 단위 밖(후보가 있을 때).
8. 세계 무작위 값이 설정 범위 안. 곰은 기본 0. 곰을 더해도 먹이·늑대·짐승·사슴 시작이 같다(곰 갈래 따로). 대조 H0 설정은 짐승 0.
9. VecEnv: 엇갈린 교체, 끊김 terminal_observation·TimeLimit.truncated, 사망 우선.
"""

import copy
import math

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import r8_world as RW
from env_v2.r8_vec_env import R8VecEnv
from env_v2.r8_world import EAT, K_BEAST, K_WOLF, SHELTER, WATCH, R8World, load_r8_config, override

CFG = ROOT / "configs" / "v3_r8_pilot.yaml"
SEEDS = [41400, 41401, 41402, 41403]


@pytest.fixture(scope="module")
def cfg():
    return load_r8_config(CFG)


def _rand_actions(rng, w):
    return rng.integers(0, RW.N_ACTIONS, (w.K, w.N))


def test_obs_dim_and_names(cfg):
    w = R8World(cfg, SEEDS[:1])
    assert RW.OBS_DIM == 65 and len(RW.OBS_NAMES) == 65 and len(set(RW.OBS_NAMES)) == 65
    assert w.obs.shape == (1, cfg["world"]["n_deer"], 65) and w.obs.dtype == np.float32
    assert not any(("wolf" in n or "pred" in n or "threat" in n) for n in RW.OBS_NAMES)


def test_determinism_and_batch_independence(cfg):
    a = R8World(cfg, SEEDS)
    b = R8World(cfg, SEEDS)
    c = R8World(cfg, [SEEDS[2]])
    r1, r2 = np.random.default_rng(0), np.random.default_rng(0)
    for _ in range(120):
        act = _rand_actions(r1, a)
        assert np.array_equal(act, _rand_actions(r2, b))
        oa, ra, da, _ = a.step(act)
        ob, rb, db, _ = b.step(act)
        oc, rc, dc, _ = c.step(act[2:3])
        assert np.array_equal(oa, ob) and np.array_equal(ra, rb) and np.array_equal(da, db)
        assert np.array_equal(oa[2:3], oc) and np.array_equal(ra[2:3], rc) and np.array_equal(da[2:3], dc)
    assert np.array_equal(a.pos, b.pos) and np.array_equal(a.apos, b.apos) and np.array_equal(a.food, b.food)
    assert np.array_equal(a.pos[2], c.pos[0]) and np.array_equal(a.apos[2], c.apos[0])


def test_kind_swap_same_obs(cfg):
    w = R8World(cfg, list(range(41400, 41416)))
    rng = np.random.default_rng(1)
    for _ in range(60):
        w.step(_rand_actions(rng, w))
    o1 = w._observe()
    w2 = copy.deepcopy(w)
    n = 0
    for k in range(w2.K):
        wi = np.nonzero(w2.kind[k] == K_WOLF)[0]
        bi = np.nonzero(w2.kind[k] == K_BEAST)[0]
        if len(wi) and len(bi):
            w2.kind[k, wi[0]], w2.kind[k, bi[0]] = K_BEAST, K_WOLF
            n += 1
    assert n >= 5
    o2 = w2._observe()
    assert np.array_equal(o1, o2)
    # 숨은 상태(먹기·탈진·짐승 상태)까지 바꿔도 같다 — 관측은 위치·이동·머리·크기만 읽는다
    w2.eat_left[:] = 7
    w2.tired_left[:] = 3
    w2.bstate[:] = 2
    w2.stalker[:] = ~w2.stalker
    assert np.array_equal(o1, w2._observe())


def test_tired_wolf_moves_like_roaming(cfg):
    """학습 전 검토(11-05): 탈진(사냥 안 함) 늑대는 제 배회 속력으로 배회한다 — 짐승에 없는 늑대만의 속력(설계 값 0.2)은 이름표였다."""
    assert cfg["wolves"]["tired_speed"] == "roam"
    c = override(cfg, {"wolves": {"count": [4, 4]}, "beasts": {"count": [0, 0]}})
    w = R8World(c, SEEDS)
    for _ in range(5):
        w.step(np.full((w.K, w.N), WATCH))
    wolf = w.kind == K_WOLF
    w.eat_left[wolf] = 0
    w.pounce_left[wolf] = 0
    w.lock[wolf] = -1
    w.tired_left[wolf] = 20
    p0 = w.apos.copy()
    w.D = 1
    w.step(np.full((w.K, w.N), WATCH))
    sp = np.sqrt(((w.apos - p0) ** 2).sum(-1))
    rr = w.cov_r + c["animals"]["shelter_margin"]
    free = wolf & (p0 > 2).all(-1) & (p0 < w.size - 2).all(-1)
    for cc in w.cov_c:
        free &= np.sqrt(((p0 - cc) ** 2).sum(-1)) > rr + 2
    assert free.sum() >= 4
    assert np.allclose(sp[free], w.aroam[free], atol=1e-12)
    lo, hi = c["animals"]["roam_speed"]
    assert (w.aroam[wolf] >= lo * w.unit - 1e-12).all() and (w.aroam[wolf] <= hi * w.unit + 1e-12).all()
    assert (w.target[wolf] == -1).all()                # 탈진 중에는 사냥하지 않는다
    # 수로 적으면 예전 뜻(× 사슴 뛰기 속력) 그대로
    w2 = R8World(override(c, {"wolves": {"tired_speed": 0.2}}), SEEDS)
    assert not w2.tired_roam


def test_beasts_never_catch(cfg):
    c = override(cfg, {"wolves": {"count": [0, 0]}, "beasts": {"count": [6, 6]}})
    w = R8World(c, SEEDS)
    assert (w.H == 6).all() and (w.M == 0).all()
    for _ in range(500):
        w.step(np.zeros((w.K, w.N), dtype=np.int64))
    assert w.st["caught_wolf"].sum() == 0 and w.st["caught_bear"].sum() == 0
    # 짐승은 실제로 돌아다니고 사슴 곁을 지나간다(시험이 빈 세계가 아님)
    assert w.st["flee_cnt"][:, K_BEAST].sum() > 100


def test_shelter_blocks_and_protects(cfg):
    w = R8World(cfg, list(range(41400, 41408)))
    rr = w.cov_r + cfg["animals"]["shelter_margin"]
    bad = []

    def hook(wd, dead, ck):
        for c in wd.cov_c:
            d = np.sqrt(((wd.apos - c) ** 2).sum(-1))
            if (wd.present & (d < rr - 1e-9)).any():
                bad.append("animal")

    w.step_hook = hook
    rng = np.random.default_rng(2)
    caught_inside = 0
    for _ in range(400):
        act = _rand_actions(rng, w)
        act[:, :8] = SHELTER                          # 몇 마리는 늘 은신처로
        _, edge0 = w._cover_edge(w.pos)
        _, _, done, info = w.step(act)
        caught_inside += int(((info["caught_kind"] > 0) & (edge0 <= -1.5)).sum())   # 결정 첫머리에 깊이 안에 있던 사슴은 2 스텝 안에 못 나간다
    assert not bad
    assert caught_inside == 0
    assert w.st["caught_wolf"].sum() > 0              # 밖의 사슴은 잡힌다(시험이 빈 세계가 아님)


def test_reward_terms(cfg):
    base = override(cfg, {})
    names = ("alive", "energy", "repro", "death")
    runs = {}
    for nm in names + ("all",):
        rw = {k: 0.0 for k in names} if nm != "all" else dict(cfg["reward"])
        if nm != "all":
            rw[nm] = 1.0
        w = R8World(override(base, {"reward": rw}), SEEDS)
        rng = np.random.default_rng(3)
        tot = []
        for _ in range(300):
            _, r, d, _ = w.step(_rand_actions(rng, w))
            tot.append(r)
        runs[nm] = np.asarray(tot)
    rw = cfg["reward"]
    lin = rw["alive"] * runs["alive"] + rw["energy"] * runs["energy"] + rw["repro"] * runs["repro"] + rw["death"] * runs["death"]
    assert np.allclose(runs["all"], lin, atol=1e-9)
    assert set(np.unique(runs["death"])) <= {0.0, 1.0} and runs["death"].sum() > 0
    assert set(np.unique(runs["repro"])) <= {0.0, 1.0, 2.0}
    assert runs["alive"].max() == 2.0                  # 살아 있음 = 스텝마다 1 (결정 = 2 스텝)
    # 에너지 항 = E 순변화 (죽음·번식 없는 세계에서 결정 보상 = E_after − E_before)
    c = override(cfg, {"wolves": {"count": [0, 0]}, "deer": {"repro_threshold": 2.0},
                       "reward": {"alive": 0.0, "energy": 1.0, "repro": 0.0, "death": 0.0}})
    w = R8World(c, SEEDS)
    rng = np.random.default_rng(4)
    for _ in range(200):
        e0 = w.E.copy()
        _, r, d, _ = w.step(_rand_actions(rng, w))
        assert not d.any()
        assert np.allclose(r, w.E - e0, atol=1e-12)


def test_action_semantics(cfg):
    c = override(cfg, {"wolves": {"count": [0, 0]}, "beasts": {"count": [0, 0]}, "world": {"decision_steps": 1}})
    w = R8World(c, [41400])
    N = w.N
    # 무대 가운데 띠에 놓고(벽·은신처에서 멀리) 머리 방향을 고정한다
    w.pos[0] = np.stack([np.linspace(25, 35, N), np.full(N, 30.0)], 1)
    ang = np.linspace(0, 2 * math.pi, N, endpoint=False)
    w.head[0] = np.stack([np.cos(ang), np.sin(ang)], 1)
    w.E[0] = 0.5
    for k in range(1, 9):
        w2 = copy.deepcopy(w)
        h0 = w2.head[0].copy()
        p0 = w2.pos[0].copy()
        w2.step(np.full((1, N), k))
        dp = w2.pos[0] - p0
        expect = RW._rot(h0, (k - 1) * math.pi / 4) * 0.6
        assert np.allclose(dp, expect, atol=1e-12)
    w2 = copy.deepcopy(w)
    p0 = w2.pos[0].copy()
    w2.step(np.full((1, N), WATCH))
    assert np.array_equal(w2.pos[0], p0)
    w2 = copy.deepcopy(w)
    p0 = w2.pos[0].copy()
    w2.step(np.full((1, N), EAT))
    sp = np.sqrt(((w2.pos[0] - p0) ** 2).sum(1))
    assert np.all((np.abs(sp) < 1e-12) | (np.abs(sp - 0.24) < 1e-9))
    w2 = copy.deepcopy(w)
    p0 = w2.pos[0].copy()
    j, _ = w2._cover_edge(p0)
    w2.step(np.full((1, N), SHELTER))
    dp = w2.pos[0] - p0
    want = RW._norm(w2.cov_c[j] - p0) * 0.6
    assert np.allclose(dp, want, atol=1e-12)
    # 약하면 0.75 배
    w2 = copy.deepcopy(w)
    w2.E[0] = 0.05
    p0 = w2.pos[0].copy()
    w2.step(np.full((1, N), 1))
    assert np.allclose(np.sqrt(((w2.pos[0] - p0) ** 2).sum(1)), 0.45, atol=1e-9)


def test_respawn_far_from_animals(cfg):
    # 동물이 적은 세계(후보가 늘 있다): 늑대 1·짐승 2
    w = R8World(override(cfg, {"wolves": {"count": [1, 1]}, "beasts": {"count": [2, 2]}}), SEEDS)
    rng = np.random.default_rng(5)
    for _ in range(20):
        w.step(_rand_actions(rng, w))
    w.E[:, :6] = -1.0                                  # 다음 스텝에 굶어 죽는다
    w.R[:, :6] = 0.0
    _, _, done, _ = w.step(np.full((w.K, w.N), WATCH))
    assert done[:, :6].all()
    for k in range(w.K):
        ap = w.apos[k][w.present[k]]
        for i in range(6):
            d = np.sqrt(((ap - w.pos[k, i]) ** 2).sum(1)).min()
            # 한 스텝(뒤 스텝) 동안 동물이 움직였으니 20 − 동물 최대 한 걸음(1.5 × 0.6)·사슴 WATCH 0
            assert d >= 20.0 - 0.9 - 1e-9
            assert w.E[k, i] < 0.5 + 1e-9 and w.R[k, i] <= 1.0


def test_world_params_in_range(cfg):
    w = R8World(cfg, list(range(41100, 41200)))
    wl, bs, fd = cfg["wolves"], cfg["beasts"], cfg["food"]
    assert ((w.M >= wl["count"][0]) & (w.M <= wl["count"][1])).all()
    assert ((w.H >= bs["count"][0]) & (w.H <= bs["count"][1])).all()
    assert ((w.wolf_speed >= wl["speed_mult"][0]) & (w.wolf_speed <= wl["speed_mult"][1])).all()
    assert ((w.regen_mult >= fd["regen_mult"][0]) & (w.regen_mult <= fd["regen_mult"][1])).all()
    assert set(np.unique(w.M)) == set(range(wl["count"][0], wl["count"][1] + 1))
    assert set(np.unique(w.H)) == set(range(bs["count"][0], bs["count"][1] + 1))
    assert cfg["bears"]["count"] == 0 and w.nBear == 0 and not (w.kind == RW.K_BEAR).any()
    sz = w.asize[w.present]
    assert sz.min() >= cfg["animals"]["size"][0] and sz.max() <= cfg["animals"]["size"][1]
    h0 = load_r8_config(ROOT / "configs" / "v3_r8_pilot_h0.yaml")
    assert h0["beasts"]["count"] == [0, 0] and h0["wolves"] == cfg["wolves"] and h0["reward"] == cfg["reward"]


def test_bears_separate_stream(cfg):
    a = R8World(cfg, SEEDS)
    b = R8World(override(cfg, {"bears": {"count": 2}}), SEEDS)
    AW = a.AW
    assert np.array_equal(a.food, b.food) and np.array_equal(a.pos, b.pos)
    assert np.array_equal(a.apos[:, :AW], b.apos[:, :AW]) and np.array_equal(a.kind[:, :AW], b.kind[:, :AW])
    assert (b.kind[:, AW:] == RW.K_BEAR).all()
    for k in range(b.K):
        d = np.sqrt(((b.pos[k][:, None] - b.apos[k, AW:][None]) ** 2).sum(-1)).min()
        assert d >= cfg["bears"]["start_r"]


def test_vec_env_truncation_and_stagger(cfg):
    c = override(cfg, {"train": {"num_worlds": 4, "reset_steps": 40}})
    v = R8VecEnv(c, meta_seed=7)
    obs = v.reset()
    assert obs.shape == (4 * v.N, 65)
    assert list(v._age) == [0, 5, 10, 15]               # T = 20 결정, 엇갈림
    seen_trunc = []
    rng = np.random.default_rng(8)
    for t in range(25):
        v.step_async(rng.integers(0, RW.N_ACTIONS, v.num_envs))
        o, r, d, infos = v.step_wait()
        for e, inf in enumerate(infos):
            if inf.get("TimeLimit.truncated"):
                seen_trunc.append((t, e // v.N))
                assert d[e] and "terminal_observation" in inf
            elif d[e]:
                assert "terminal_observation" in inf     # 사망: 끝 관측은 있지만 truncated 아님
    worlds_cut = sorted({(t, k) for t, k in seen_trunc})
    assert {k for _, k in worlds_cut} == {0, 1, 2, 3}
    assert [t for t, k in worlds_cut if k == 3][0] == 4 and [t for t, k in worlds_cut if k == 0][0] == 19
    assert len(set(v.current_seeds())) == 4
    assert all(41100 <= s < 41400 for h in v.seed_history for s in h)
