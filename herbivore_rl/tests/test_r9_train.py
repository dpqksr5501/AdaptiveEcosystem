"""R9 학습 줄기 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 7-3·7-4·7-7·7-9·7-10, 12절 17·18·21·26·27).

17. VecEnv: 학습 종 칸 조각만 돌려준다(환경 수 = 세계 번호별 마릿수 합, 고정), 행동이 그 칸으로 간다, 엇갈린 교체, 끊김 =
    done + terminal_observation + TimeLimit.truncated, 같은 결정에 죽으면 사망이 우선(R8 test_r8.py 274~295 꼴).
18. 상대 고르기: 같은 메타 시드 = 같은 상대, 예전 판 = Uniform{⌊V/2⌋, …, V − 1}, V = 0 이면 규칙, 0 바퀴 몫, 확률 75%.
21. 고정 두뇌가 든 닫힌 고리(세계 + 모든 종 고정 두뇌, 학습·판정 세계) 1,000 스텝: 세계 묶음 K = 1·8·섞은 차례에서 비트 같다.
    늑대 묶음 VecEnv 조각 1·2·3 이 1,000 스텝 비트 같다(관측·보상·끝·끊김).
26. 이어 가기·학습률: 묶음을 시작 사본에서 다시 돌리면 가중치가 같다(새 모델도). `PPO.load(…, learning_rate=1e-4)` 뒤 기록된 학습률이
    1e-4. 첫 롤아웃 뒤 정책 쪽 가중치는 그대로, 가치 쪽은 바뀐다.
27. (세계를 붙인 판) 상대 두뇌를 규칙 ↔ 학습(확률) ↔ 학습(가장 높은 칸)으로 바꿔도 모든 ACT 갈래와 BITE 갈래의 소비가 같다.
판정 시드는 학습 코드가 거부한다(시험 25 의 학습 쪽).
시드: 시험 범위 44350~44399 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch 보다 먼저

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from env.config import ROOT
from env_v2 import r9_body as B
from env_v2 import r9_brains as BR
from env_v2 import r9_vec_env as V
from env_v2.r9_vec_env import R9VecEnv
from env_v2.r9_world import R9World

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"
TEST_SEEDS = range(44350, 44400)
D_, W_, R_ = B.DEER, B.WOLF, B.BOAR

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def cfg():
    return B.load_r9_config(CFG)


@pytest.fixture(scope="module")
def jcfg():
    return B.load_r9_config(JCFG)


def same_bits(a, b) -> bool:
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def rand_brain(cfg, sp, seed, scale=0.6) -> dict:
    """Untrained MLP weights at a trained-like scale (logits O(1), varied actions)."""
    g = np.random.default_rng(seed)
    w = {k: (g.standard_normal(BR.NPZ_SHAPES[k]) * (scale if k.startswith("W") else 0.1)).astype(np.float32)
         for k in BR.NPZ_WEIGHT_KEYS}
    return w


@pytest.fixture(scope="module")
def npz_pool(tmp_path_factory, cfg):
    """Two random MLP versions per species as npz (fixed-brain files the world loads, body hash checked)."""
    d = tmp_path_factory.mktemp("pool")
    pool = {}
    for sp, name in enumerate(B.SPECIES):
        paths = []
        for v in range(3):
            p = d / f"{name}_v{v}.npz"
            BR.save_brain(p, rand_brain(cfg, sp, 44360 + 10 * sp + v), BR.brain_meta(cfg, sp, "T", 0, v, None))
            paths.append(str(p))
        pool[name] = paths
    return pool


# --------------------------------------------------------------------------- 17


def test_17_learner_slice_counts_and_actions(cfg):
    for sp, name in enumerate(B.SPECIES):
        lc = cfg["learner_counts"][name]
        K = len(lc) + 1
        v = R9VecEnv(cfg, name, seeds=TEST_SEEDS, num_worlds=K)
        try:
            want = sum(lc[k % len(lc)] for k in range(K))
            assert v.num_envs == want
            w = v.shards[0].core.world
            ek, es = w.learner_index(sp)
            assert len(ek) == want and (w.slot_sp[es] == sp).all()
            assert [int(c) for c in w.counts[:, sp]] == [lc[k % len(lc)] for k in range(K)]
            obs = v.reset()
            assert obs.shape == (want, B.OBS_DIM) and obs.dtype == np.float32
            assert same_bits(obs, w.obs()[ek, es])
            rng = np.random.default_rng(44370)
            for _ in range(6):
                a = rng.integers(0, B.N_ACTIONS, v.num_envs)
                v.step_async(a)
                o, r, d, inf = v.step_wait()
                assert (w.act[ek, es] == a).all()                    # learner actions went to the learner slots only
                assert w.alive[ek, es].all() and v.num_envs == want  # train worlds: learner slots always alive
                assert same_bits(o, w.obs()[ek, es]) and r.shape == (want,) and len(inf) == want
            # other species decided by their fixed (rule, round 0) brains
            for s in range(3):
                for k in range(K):
                    assert (w.ctrl[k][s] is None) == (s == sp)
        finally:
            v.close()
    # 7-3: the design's learner env totals with the configured world counts
    tot = {n: sum(cfg["learner_counts"][n][k % len(cfg["learner_counts"][n])] for k in range(cfg["train"]["worlds"][n]))
           for n in B.SPECIES}
    assert tot == {"deer": 1280, "wolf": 384, "boar": 768}
    for n in B.SPECIES:
        assert (cfg["train"]["n_steps"][n] * tot[n]) % 4096 == 0


def test_17_stagger_truncation_and_death_priority(cfg):
    v = R9VecEnv(cfg, "deer", seeds=TEST_SEEDS, num_worlds=4, reset_steps=40)
    try:
        assert v.T == 20 and list(v._age) == [0, 5, 10, 15]
        v.reset()
        core = v.shards[0].core
        orig = core.step
        forced = []

        def step_kill_one(la, renews):                               # force a death in a world that is being renewed
            o, r, d, term = orig(la, renews)
            if renews:
                kl = int(renews[0][0])
                e = int(np.nonzero(core.ek == kl)[0][0])
                d = d.copy()
                d[e] = True
                forced.append((kl, e))
            return o, r, d, term

        core.step = step_kill_one
        rng = np.random.default_rng(44371)
        cut = []
        for t in range(25):
            v.step_async(rng.integers(0, B.N_ACTIONS, v.num_envs))
            o, r, d, infos = v.step_wait()
            for e, inf in enumerate(infos):
                if inf.get("TimeLimit.truncated"):
                    assert d[e] and "terminal_observation" in inf
                    cut.append((t, int(v._env_world[e])))
                elif d[e]:
                    assert "terminal_observation" in inf
            for kl, e in forced:
                assert d[e] and "TimeLimit.truncated" not in infos[e] and "terminal_observation" in infos[e]
            forced.clear()
        worlds_cut = sorted(set(cut))
        assert {k for _, k in worlds_cut} == {0, 1, 2, 3}
        assert [t for t, k in worlds_cut if k == 3][0] == 4 and [t for t, k in worlds_cut if k == 0][0] == 19
        assert len(set(v.current_seeds())) == 4 and all(44350 <= s < 44400 for h in v.seed_history for s in h)
    finally:
        v.close()


def test_17_truncated_terminal_is_pre_renew_obs(cfg):
    v = R9VecEnv(cfg, "boar", seeds=TEST_SEEDS, num_worlds=2, reset_steps=8)     # T = 4 decisions, world 1 aged 2
    try:
        v.reset()
        core = v.shards[0].core
        orig = core.renew
        pre = {}

        def renew_spy(renews):                                       # world obs just before the new seed goes in
            o = core.world.obs()[core.ek, core.es].copy()
            for kl, *_ in renews:
                pre[int(kl)] = o[core.ek == int(kl)]
            orig(renews)

        core.renew = renew_spy
        rng = np.random.default_rng(44372)
        seen = 0
        for _ in range(6):
            pre.clear()
            v.step_async(rng.integers(0, B.N_ACTIONS, v.num_envs))
            o, r, d, infos = v.step_wait()
            for k, blk in pre.items():
                envs = v._world_envs[k]
                for j, e in enumerate(envs):
                    assert d[e] and "terminal_observation" in infos[e]
                    assert same_bits(infos[e]["terminal_observation"], blk[j])            # pre-renew obs
                    seen += int(bool(infos[e].get("TimeLimit.truncated")))
                assert not same_bits(o[envs], blk)                                       # returned obs = the new world
            assert same_bits(o, core.world.obs()[core.ek, core.es])
        assert seen > 0
    finally:
        v.close()


def test_25_train_code_refuses_judge_seeds(cfg):
    with pytest.raises(ValueError, match="judge seeds"):
        R9VecEnv(cfg, "deer", seeds=range(44790, 44810), num_worlds=2)
    with pytest.raises(ValueError, match="judge seeds"):
        V.check_train_seeds([44999])
    V.check_train_seeds([43000, 44799])


# --------------------------------------------------------------------------- 18


def test_18_pick_opponent_rules():
    sh = {"current": 0.5, "past": 0.3, "rule": 0.2}
    a = [V.pick_opponent(np.random.default_rng([0, 1, 0, 0]), sh, 9, 0.5, 0.75) for _ in range(1)]
    b = [V.pick_opponent(np.random.default_rng([0, 1, 0, 0]), sh, 9, 0.5, 0.75) for _ in range(1)]
    assert a == b
    g = np.random.default_rng(44373)
    n = 60_000
    kinds, past, stoch = {}, {}, 0
    V_ = 9                                                   # versions 0..9 → past ∈ {4..8}
    for _ in range(n):
        p = V.pick_opponent(g, sh, V_ + 1, 0.5, 0.75)
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
        stoch += p["stochastic"]
        if p["kind"] == "past":
            past[p["v"]] = past.get(p["v"], 0) + 1
        if p["kind"] == "current":
            assert p["v"] == V_
    assert set(past) == set(range(V_ // 2, V_))
    for v_ in past:
        assert abs(past[v_] / kinds["past"] - 1.0 / len(past)) < 0.02
    for kd, s in sh.items():
        assert abs(kinds[kd] / n - s) < 0.01
    assert abs(stoch / n - 0.75) < 0.01
    # V = 1, 2, 3 → past sets {0}, {1}, {1, 2}
    for nv, want in ((2, {0}), (3, {1}), (4, {1, 2})):
        seen = {V.pick_opponent(g, {"past": 1.0}, nv, 0.5, 0.75)["v"] for _ in range(400)}
        assert seen == want
    # V = 0 (one version) → past share goes to the rule brain; empty pool → current and past go to rule
    assert {V.pick_opponent(g, {"past": 1.0}, 1, 0.5, 0.75)["kind"] for _ in range(50)} == {"rule"}
    assert {V.pick_opponent(g, {"current": 0.5, "past": 0.5}, 0, 0.5, 0.75)["kind"] for _ in range(50)} == {"rule"}
    # always 3 draws whatever the outcome
    g1, g2 = np.random.default_rng(5), np.random.default_rng(5)
    V.pick_opponent(g1, {"rule": 1.0}, 0, 0.5, 0.75)
    V.pick_opponent(g2, {"current": 0.5, "past": 0.5}, 7, 0.5, 0.75)
    assert g1.bit_generator.state == g2.bit_generator.state
    with pytest.raises(ValueError):
        V.pick_opponent(g, {"current": 0.5}, 3, 0.5, 0.75)


def test_18_round_shares(cfg):
    op = cfg["train"]["opponents"]
    assert V.opponent_shares(cfg, 0, D_, W_) == op["round0"] == {"rule": 1.0}
    assert V.opponent_shares(cfg, 0, W_, D_) == V.opponent_shares(cfg, 0, W_, R_) == {"rule": 0.7, "always_eat": 0.3}
    assert V.opponent_shares(cfg, 3, R_, D_) == {"current": 0.5, "past": 0.3, "rule": 0.2}
    ov = {"*": {"current": 0.4, "past": 0.4, "rule": 0.2}}                  # 9-4 처방
    assert V.opponent_shares(cfg, 3, D_, W_, ov) == ov["*"]


def test_18_vec_env_same_meta_seed_same_opponents(cfg, npz_pool):
    pool = {n: npz_pool[n] for n in ("wolf", "boar")}
    hs = []
    for ms in (0, 0, 1):
        v = R9VecEnv(cfg, "deer", model_seed=ms, round_=2, pool=pool, seeds=TEST_SEEDS, num_worlds=6, reset_steps=10)
        try:
            v.reset()
            rng = np.random.default_rng(44374)
            for _ in range(12):
                v.step_async(rng.integers(0, B.N_ACTIONS, v.num_envs))
                v.step_wait()
            hs.append(json.dumps(v.history, sort_keys=True))
            w = v.shards[0].core.world
            labels = {(k, s): w.ctrl[k][s].label for k in range(v.K) for s in (W_, R_)}
            kinds = {o["kind"] for h in v.history for o in h["opponents"].values()}
            assert kinds <= {"current", "past", "rule"}
            for k in range(v.K):
                last = [h for h in v.history if h["k"] == k][-1]
                for s in (W_, R_):
                    assert labels[(k, s)] == last["opponents"][B.SPECIES[s]]["label"]
                    assert w.ctrl[k][s].stochastic == last["opponents"][B.SPECIES[s]]["stochastic"]
        finally:
            v.close()
    assert hs[0] == hs[1] and hs[0] != hs[2]
    # segment re-seed (10절 '묶음 안 판 번호'): same segment → same stream
    a = R9VecEnv(cfg, "deer", round_=2, pool=pool, seeds=TEST_SEEDS, num_worlds=2)
    b = R9VecEnv(cfg, "deer", round_=2, pool=pool, seeds=TEST_SEEDS, num_worlds=2)
    try:
        a.set_segment(3)
        b.set_segment(3)
        assert a._meta.random() == b._meta.random()
    finally:
        a.close()
        b.close()


# --------------------------------------------------------------------------- 21


def _ctrl_mix(cfg, pool, k):
    """Per-world fixed brains for every species (mix of MLP stochastic / greedy and rules)."""
    out = {}
    for sp, name in enumerate(B.SPECIES):
        c = (k + sp) % 3
        if c == 0:
            out[sp] = BR.Controller(BR.load_brain(Path(pool[name][k % 3]), cfg, sp), True, "mlp-s")
        elif c == 1:
            out[sp] = BR.Controller(BR.load_brain(Path(pool[name][(k + 1) % 3]), cfg, sp), False, "mlp-g")
        else:
            out[sp] = BR.Controller(BR.make_rule(V.RULE_OF[sp], cfg), False, "rule")
    return out


def _closed_loop(cfg, pool, seeds, ks, decisions):
    """World with fixed brains for every species; returns {seed: (obs, rew, pos, alive, E) per checkpoint}."""
    w = R9World(cfg, seeds)
    for i, k in enumerate(ks):
        for sp, c in _ctrl_mix(cfg, pool, k).items():
            w.set_controller(i, sp, c)
    out = {s: [] for s in seeds}
    for t in range(decisions):
        obs, rew, done, info = w.step(w.decide())
        if t % 50 == 49 or t == decisions - 1:
            for i, s in enumerate(seeds):
                out[s].append((obs[i].copy(), rew[i].copy(), w.pos[i].copy(), w.alive[i].copy(), w.E[i].copy(), w.uid[i].copy()))
    return out


def _cmp(a, b):
    assert len(a) == len(b)
    for x, y in zip(a, b):
        for u, v_ in zip(x, y):
            assert same_bits(u, v_)


def test_21_closed_loop_fixed_brains_batch_independent(cfg, npz_pool):
    seeds = list(range(44380, 44388))
    ks = list(range(8))
    full = _closed_loop(cfg, npz_pool, seeds, ks, 500)                    # 1,000 steps
    for i in (0, 5):
        one = _closed_loop(cfg, npz_pool, [seeds[i]], [ks[i]], 500)
        _cmp(full[seeds[i]], one[seeds[i]])
    perm = [3, 7, 0, 5, 1, 6, 2, 4]
    mixed = _closed_loop(cfg, npz_pool, [seeds[j] for j in perm], [ks[j] for j in perm], 500)
    for s in seeds:
        _cmp(full[s], mixed[s])
    assert any(int(full[s][-1][5].max()) > int(full[s][0][5].max()) for s in seeds)   # respawns happened (new uids)


def test_21_judge_closed_loop_batch_independent(jcfg, npz_pool):
    seeds = [44390, 44391]
    both = _closed_loop(jcfg, npz_pool, seeds, [0, 1], 500)
    one = _closed_loop(jcfg, npz_pool, [seeds[1]], [1], 500)
    _cmp(both[seeds[1]], one[seeds[1]])
    rev = _closed_loop(jcfg, npz_pool, seeds[::-1], [1, 0], 500)
    _cmp(both[seeds[0]], rev[seeds[0]])


def test_21_wolf_shards_bit_identical(cfg, npz_pool):
    pool = {n: npz_pool[n] for n in ("deer", "boar")}
    res = {}
    for n_sh in (1, 2, 3):
        v = R9VecEnv(cfg, "wolf", model_seed=0, round_=1, pool=pool, seeds=TEST_SEEDS, num_worlds=6, reset_steps=300,
                     shards=n_sh)
        try:
            assert len(v.shards) == n_sh
            out = [v.reset()]
            rng = np.random.default_rng(44375)
            for _ in range(500):                                          # 1,000 steps, renews every 150 decisions
                v.step_async(rng.integers(0, B.N_ACTIONS, v.num_envs))
                o, r, d, inf = v.step_wait()
                out += [o, r, d, np.array([bool(i.get("TimeLimit.truncated")) for i in inf]),
                        np.stack([i.get("terminal_observation", np.zeros(B.OBS_DIM, np.float32)) for i in inf])]
            st = v.stats_snapshot()
            out += [st["deaths"], st["actions"], st["bites"]]
            res[n_sh] = (out, json.dumps(v.history, sort_keys=True), v.num_resets)
        finally:
            v.close()
    for n_sh in (2, 3):
        assert res[n_sh][1] == res[1][1] and res[n_sh][2] == res[1][2] > 0
        assert len(res[n_sh][0]) == len(res[1][0])
        for a, b in zip(res[1][0], res[n_sh][0]):
            assert same_bits(a, b)


# --------------------------------------------------------------------------- 27 (world side, MLP included)


def test_27_brain_kind_swap_keeps_streams(cfg, npz_pool):
    worlds = []
    for kind in ("rule", "mlp-s", "mlp-g"):
        w = R9World(cfg, [44392, 44393])
        for k in range(w.K):
            w.set_controller(k, D_, BR.Controller(BR.make_rule("RULE_DEER", cfg), False, "rule"))
            w.set_controller(k, R_, BR.Controller(BR.load_brain(Path(npz_pool["boar"][0]), cfg, R_), True, "mlp"))
            if kind == "rule":
                c = BR.Controller(BR.make_rule("RULE_WOLF", cfg), False, "rule")
            else:
                c = BR.Controller(BR.load_brain(Path(npz_pool["wolf"][1]), cfg, W_), kind == "mlp-s", kind)
            w.set_controller(k, W_, c)
        worlds.append(w)
    for _ in range(40):
        for w in worlds:
            w.step(w.decide())
        a = worlds[0]
        for b in worlds[1:]:
            for k in range(a.K):
                for s in range(3):
                    assert a.rng_act[k][s].bit_generator.state == b.rng_act[k][s].bit_generator.state
                assert a.rng_bite[k].bit_generator.state == b.rng_bite[k].bit_generator.state
    assert not np.array_equal(worlds[0].pos, worlds[1].pos) and not np.array_equal(worlds[1].pos, worlds[2].pos)


# --------------------------------------------------------------------------- 26


def _train_mod():
    import importlib.util
    import sys
    if "r9_train_mod" not in sys.modules:
        spec = importlib.util.spec_from_file_location("r9_train_mod", ROOT / "results" / "v3" / "r9" / "train_r9.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["r9_train_mod"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["r9_train_mod"]


def _train(tmp, run, *extra):
    train_r9 = _train_mod()
    argv = ["--species", "deer", "--branch", "A", "--wall-hours", "0.2", "--run-name", run, "--seeds", "44350", "44400",
            "--num-worlds", "1", "--out", str(tmp / "ckpt"), "--log-dir", str(tmp / "logs"), "--log-first", "256",
            "--log-every", "512", "--snapshot-every", "100000000"] + list(extra)
    rc = train_r9.main(argv)
    assert rc == 0
    return json.loads((tmp / "ckpt" / "A" / f"{run}.json").read_text(encoding="utf-8"))


def _params(zip_path):
    from stable_baselines3 import PPO
    m = PPO.load(str(zip_path), device="cpu")
    return {k: v.detach().clone() for k, v in m.policy.state_dict().items()}


@pytest.fixture(scope="module")
def r0_zip(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("r0")
    m = _train(tmp, "t26_r0", "--round", "0", "--decisions", "1024", "--n-steps", "32", "--batch-size", "256")
    assert m["learning_rate"] == 3e-4 and m["timesteps"] == 1024 and m["num_envs"] == 16
    return tmp / "ckpt" / "A" / Path(m["snapshots"][-1]["zip"]).name, m


def test_26_new_bundle_rerun_same(tmp_path, r0_zip):
    m = _train(tmp_path, "t26_r0b", "--round", "0", "--decisions", "1024", "--n-steps", "32", "--batch-size", "256")
    a = _params(r0_zip[0])
    b = _params(tmp_path / "ckpt" / "A" / Path(m["snapshots"][-1]["zip"]).name)
    assert a.keys() == b.keys() and all(torch.equal(a[k], b[k]) for k in a)


def test_26_continue_lr_value_only_and_rerun(tmp_path, r0_zip):
    init, _ = r0_zip
    pol_keys = [k for k in _params(init) if k.startswith(("mlp_extractor.policy_net", "action_net"))]
    val_keys = [k for k in _params(init) if k.startswith(("mlp_extractor.value_net", "value_net"))]
    assert pol_keys and val_keys
    # (가) one rollout (16 envs × 32 = 512) with the policy frozen → policy weights unchanged, value weights changed
    m1 = _train(tmp_path / "a", "t26_r1a", "--round", "1", "--decisions", "512", "--init", str(init))
    assert m1["value_only_first"] is True and m1["timesteps"] == 512
    p0, p1 = _params(init), _params(tmp_path / "a" / "ckpt" / "A" / Path(m1["snapshots"][-1]["zip"]).name)
    assert all(torch.equal(p0[k], p1[k]) for k in pol_keys)
    assert any(not torch.equal(p0[k], p1[k]) for k in val_keys)
    # (나) learning rate after load = 1e-4 (model, optimizer groups, logger rows)
    assert m1["learning_rate"] == 1e-4 and m1["optimizer_lr"] == [1e-4]
    rows = [json.loads(x) for x in (tmp_path / "a" / "logs" / "t26_r1a.log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows and all(r_.get("learning_rate", 1e-4) == 1e-4 for r_ in rows) and any("learning_rate" in r_ for r_ in rows)
    # (다) after the first rollout the policy learns again; a re-run from the same start copy gives the same weights
    m2 = _train(tmp_path / "b", "t26_r1b", "--round", "1", "--decisions", "1536", "--init", str(init))
    m3 = _train(tmp_path / "c", "t26_r1c", "--round", "1", "--decisions", "1536", "--init", str(init))
    assert m2["lr_seen"] == [1e-4] and m2["timesteps"] == 1536
    q2 = _params(tmp_path / "b" / "ckpt" / "A" / Path(m2["snapshots"][-1]["zip"]).name)
    q3 = _params(tmp_path / "c" / "ckpt" / "A" / Path(m3["snapshots"][-1]["zip"]).name)
    assert all(torch.equal(q2[k], q3[k]) for k in q2)
    assert any(not torch.equal(p0[k], q2[k]) for k in pol_keys)
    with np.load(tmp_path / "b" / "ckpt" / "A" / Path(m2["snapshots"][-1]["npz"]).name, allow_pickle=False) as z2, \
            np.load(tmp_path / "c" / "ckpt" / "A" / Path(m3["snapshots"][-1]["npz"]).name, allow_pickle=False) as z3:
        for k in BR.NPZ_WEIGHT_KEYS:
            assert same_bits(z2[k], z3[k])
    # the exported npz is a valid fixed brain for the world (body hash of this config)
    br = BR.load_brain(tmp_path / "b" / "ckpt" / "A" / Path(m2["snapshots"][-1]["npz"]).name, B.load_r9_config(CFG), "deer")
    assert br.meta["round"] == 1 and br.meta["decisions"] == 1536


def test_transient_failures_are_cut_and_rerun(tmp_path):
    """Fix 단계 검토 low: memory / lost shard worker → end record stop='cut' → the league re-runs it (bounded by --max-attempts);
    NaN and other errors stay 'error' → the league stops. (league.finished on stub end records; is_transient on exceptions.)"""
    import sys as _sys
    d = ROOT / "results" / "v3" / "r9"
    if str(d) not in _sys.path:
        _sys.path.insert(0, str(d))
    import league_r9 as LG
    import train_r9 as TR

    assert TR.is_transient(MemoryError()) and TR.is_transient(V.ShardWorkerLost("lost"))
    try:
        try:
            raise EOFError("pipe")
        except EOFError as e:
            raise RuntimeError("wrapped") from e
    except RuntimeError as e:
        assert TR.is_transient(e)
    assert not TR.is_transient(RuntimeError("shard worker error:\nValueError: bad")) and not TR.is_transient(ValueError("nan"))
    lg = LG.League.__new__(LG.League)
    lg.out = tmp_path
    spec = dict(branch="A", run="r0_deer_A", species="deer", round=0)
    (tmp_path / "A").mkdir()
    mp = tmp_path / "A" / "r0_deer_A.json"
    assert lg.finished(spec) is None
    for stop, want in (("cut", "cut"), ("error", "failed"), ("nan", "failed")):
        mp.write_text(json.dumps(dict(stop=stop, snapshots=[])), encoding="utf-8")
        assert lg.finished(spec) == want, stop
