"""v3 R1 — 행동 고르기 학습 파이프라인 (명세 Docs/RL_Policy/RL_V3_R1_SPEC.md, 사전 등록 results/v3/r1/PREREG.md).

결정 미리 보기(`World.rep_peek`)의 순수성·비트 동일·실제 결정과의 일치, 마스크(허용 ∧ 가능 ∧ 결정), 설정 블록 검사, ε 혼합
범주 분포(합 1·막힌 칸 0·한 칸 마스크 log π = 0·엔트로피 0·argmax 동점), 정책(마스크 칸은 망에 안 들어감·시작 편향·저장/싣기),
이산 VecEnv(모양·마스크 밖 행동 거부·끊긴 슬롯 terminal 관측의 마스크·블록 없는 repertoire 세계 거부·연속 세계 그대로),
롤아웃 세계 연결 훅과 rep_learned, 학습·f_dec 측정·판정 도구 smoke.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import json
import math

import numpy as np
import pytest
import torch as th
import yaml

import repertoire_rules as rr
from env.config import ROOT
from env_v2 import rep_policy as rp
from env_v2 import repertoire as rep
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.vec_env import MultiWorldVecEnv, sigmoid
from env_v2.world import World, obs_names

V3R1 = ROOT / "configs" / "v3_r1.yaml"
V3R1_ON = ROOT / "configs" / "v3_r1_on.yaml"
V3R0 = ROOT / "configs" / "v3_r0.yaml"
V3R0_ON = ROOT / "configs" / "v3_r0_on.yaml"
V2_4S = ROOT / "configs" / "v2_4s.yaml"
G, F, H, Z, S = rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def cfg():
    return load_v2_config(V3R1)


@pytest.fixture(scope="module")
def cfg_on():
    return load_v2_config(V3R1_ON)


@pytest.fixture(scope="module")
def params(cfg):
    return rp.rep_params(cfg)


def _train(cfg, **kw):
    t = dict(cfg.v2["train"])
    t["repertoire"] = dict(t["repertoire"], **kw)
    return cfg.replace(v2=dict(cfg.v2, train=t))


def _feat(cfg, name, **kw):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    f[name] = dict(f[name], **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _state(w):
    return {k: np.array(v, copy=True) for k, v in vars(w._rs).items()}


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("r1, r0", [(V3R1, V3R0), (V3R1_ON, V3R0_ON)], ids=["train", "on"])
def test_r1_configs_are_r0_plus_three_changes(r1, r0):
    """v3_r1(_on) = v3_r0(_on) + version 3.r1·cover_mult_crouch 4.0·obs_extra true·train.repertoire 블록. 그 밖은 그대로."""
    a = yaml.safe_load(r1.read_text(encoding="utf-8"))
    b = yaml.safe_load(r0.read_text(encoding="utf-8"))
    assert a["version"] == "3.r1" and b["version"] == "3.r0"
    ra, rb = dict(a["features"]["repertoire"]), dict(b["features"]["repertoire"])
    assert ra.pop("cover_mult_crouch") == 4.0 and rb.pop("cover_mult_crouch") == 2.5
    assert ra.pop("obs_extra") is True and rb.pop("obs_extra") is False
    assert ra == rb
    assert {k: v for k, v in a["features"].items() if k != "repertoire"} == \
        {k: v for k, v in b["features"].items() if k != "repertoire"}
    t = dict(a["train"])
    blk = t.pop("repertoire")
    assert t == b["train"] and a["overrides"] == b["overrides"]
    assert blk["allowed"] == ["graze", "flee", "hide", "freeze"] and blk["epsilon"] == 0.05      # R0 결과(SLEEP 제외)
    assert blk["init_probs"] == [0.4, 0.15, 0.15, 0.15, 0.15]
    assert blk["ent_coef_base"] == 0.0008971496690499397                     # v2.4s 학습 ent_coef (ppo_best.yaml)
    assert 0.0 < blk["f_dec"] <= 1.0
    w = World(load_v2_config(r1), seeds=[0])
    assert w.obs_dim == 18 and w.act_names == ("behavior",)


def test_train_and_judge_worlds_differ_only_in_fixed_day():
    a = yaml.safe_load(V3R1.read_text(encoding="utf-8"))
    b = yaml.safe_load(V3R1_ON.read_text(encoding="utf-8"))
    assert a["features"]["daynight"].pop("fixed_day_frac") == 0.2
    assert b["features"]["daynight"].pop("fixed_day_frac") == 0.0
    assert a == b


@pytest.mark.parametrize("kw, match", [
    (dict(allowed=["graze", "hide"]), "flee"),
    (dict(allowed=["graze", "flee", "run"]), "allowed"),
    (dict(allowed=["graze", "flee", "flee"]), "allowed"),
    (dict(epsilon=1.0), "epsilon"),
    (dict(epsilon=-0.1), "epsilon"),
    (dict(epsilon=True), "epsilon"),
    (dict(init_probs=[0.4, 0.2, 0.2, 0.2]), "init_probs"),
    (dict(init_probs=[0.4, 0.2, 0.2, 0.2, 0.0]), "init_probs"),
    (dict(ent_coef_base=-1e-3), "ent_coef_base"),
    (dict(f_dec=0.0), "f_dec"),
    (dict(f_dec=1.5), "f_dec"),
])
def test_rep_params_are_checked(cfg, kw, match):
    with pytest.raises(ValueError, match=match):
        rp.rep_params(_train(cfg, **kw))


def test_rep_params_keys_and_world(cfg, params):
    t = dict(cfg.v2["train"])
    blk = dict(t["repertoire"])
    del blk["f_dec"]
    with pytest.raises(ValueError, match="키"):
        rp.rep_params(cfg.replace(v2=dict(cfg.v2, train=dict(t, repertoire=blk))))
    with pytest.raises(ValueError, match="키"):
        rp.rep_params(cfg.replace(v2=dict(cfg.v2, train=dict(t, repertoire=dict(t["repertoire"], extra=1)))))
    with pytest.raises(ValueError, match="obs_extra"):
        rp.rep_params(_feat(cfg, "repertoire", obs_extra=False))
    with pytest.raises(ValueError, match="repertoire"):
        rp.rep_params(_feat(cfg, "repertoire", enabled=False))
    assert rp.rep_params(load_v2_config(V3R0)) is None                       # 블록이 없으면 None
    assert params["allowed"] == ("graze", "flee", "hide", "freeze")
    np.testing.assert_array_equal(params["allowed_mask"], [True, True, True, True, False])
    np.testing.assert_allclose(np.exp(params["init_logits"]), [0.4, 0.15, 0.15, 0.15, 0.15])
    assert params["cat_ent_coef"] == params["ent_coef_base"] / params["f_dec"]


# --------------------------------------------------------------------- #
# rep_peek — 순수 함수
# --------------------------------------------------------------------- #


class _Capture(World):
    """`_rep_step` 의 실제 결정 결과(decide)를 남기는 World."""

    def _rep_step(self, a):
        v, out = super()._rep_step(a)
        self.last_decide = out["decide"].copy()
        return v, out


def _requests(rng, n):
    return rng.integers(0, rep.N_BEHAVIORS, (n, 1)).astype(np.float64)


@pytest.mark.parametrize("seed", [20000, 12003])
def test_peek_is_pure_and_bit_identical(cfg, seed):
    """peek 을 스텝마다(여러 번) 부른 세계와 한 번도 부르지 않은 세계의 궤적이 비트 단위로 같다(관측·보상·사망·위치·행동 상태·
    통계·난수 상태). peek 의 reads 는 다음 스텝의 실제 결정과 같고, wake_decide 는 그중 이번 스텝에 깨는 개체다."""
    wa, wb = _Capture(cfg, seeds=[seed]), World(cfg, seeds=[seed])
    assert wa._th is not None and wa._rp is not None
    ra, rb = np.random.default_rng(7), np.random.default_rng(7)
    n_wake = n_dec = 0
    for t in range(400):
        st = _state(wa)
        rng_state = wa.rng.bit_generator.state
        feat = {k: g.bit_generator.state for k, g in wa._feature_rngs.items()}
        pk = wa.rep_peek()
        pk2 = wa.rep_peek()
        for k in pk:
            np.testing.assert_array_equal(pk[k], pk2[k])
        for k, v in _state(wa).items():                                     # 행동 상태를 바꾸지 않는다
            np.testing.assert_array_equal(v, st[k], err_msg=k)
        assert wa.rng.bit_generator.state == rng_state
        assert {k: g.bit_generator.state for k, g in wa._feature_rngs.items()} == feat
        woke = wa._rs.waking & (wa._rs.wake_left <= 0)
        oa, ob = wa.observe(), wb.observe()
        np.testing.assert_array_equal(oa, ob)
        res_a, res_b = wa.step(_requests(ra, wa.N)), wb.step(_requests(rb, wb.N))
        for x, y in zip(res_a, res_b):
            np.testing.assert_array_equal(x, y)
        np.testing.assert_array_equal(pk["reads"], wa.last_decide)          # 미리 본 결정 = 실제 결정
        np.testing.assert_array_equal(pk["wake_decide"], wa.last_decide & woke)
        n_wake += int(pk["wake_decide"].sum())
        n_dec += int(pk["reads"].sum())
    for k, v in _state(wa).items():
        np.testing.assert_array_equal(v, getattr(wb._rs, k), err_msg=k)
    for k in ("pos", "head", "energy", "pred_pos", "food", "behavior", "beh_phase", "beh_steps", "beh_seq"):
        np.testing.assert_array_equal(getattr(wa, k), getattr(wb, k), err_msg=k)
    assert wa.repertoire_stats() == wb.repertoire_stats() or all(
        (x == y) or (math.isnan(x) and math.isnan(y)) for x, y in zip(wa.repertoire_stats().values(),
                                                                       wb.repertoire_stats().values()))
    assert n_dec > 0 and n_wake > 0                                          # 기상 결정까지 실제로 지나갔다


def test_peek_only_on_repertoire_world():
    with pytest.raises(ValueError, match="repertoire"):
        World(load_v2_config(V2_4S), seeds=[0]).rep_peek()


# --------------------------------------------------------------------- #
# 마스크
# --------------------------------------------------------------------- #


def _obs_rows(cfg, rows):
    """관측 행(이름으로 채운다). rows: dict 목록 {pc, recency, cover}."""
    names = list(obs_names(cfg))
    o = np.zeros((len(rows), len(names)), dtype=np.float32)
    for i, r in enumerate(rows):
        o[i, names.index("pred_count")] = r.get("pc", 0) / 8.0
        o[i, names.index("threat_recency")] = r.get("recency", 0.0)
        o[i, names.index("cover_dist")] = r.get("cover", 1.0)
    return o, names


def test_feasible_mask(cfg):
    o, names = _obs_rows(cfg, [dict(), dict(pc=1), dict(recency=0.3), dict(cover=0.74), dict(cover=0.75),
                               dict(cover=0.0), dict(recency=0.19), dict(recency=rp.THREAT_RECENCY_OBS),
                               dict(pc=1, cover=0.74), dict(recency=0.3, cover=0.0), dict(recency=0.1, cover=0.0)])
    f = rp.feasible_mask(o, names)
    np.testing.assert_array_equal(f[:, G], True)
    np.testing.assert_array_equal(f[:, S], True)
    # 위협을 안다 = 보임 또는 threat_recency ≥ 0.2 (곱 감쇠의 꼬리 0 < r < 0.2 는 모른다)
    np.testing.assert_array_equal(f[:, F], [False, True, True, False, False, False, False, True, True, True, False])
    np.testing.assert_array_equal(f[:, Z], f[:, F])
    # HIDE 는 위협을 알고 은신처가 가까울 때만
    np.testing.assert_array_equal(f[:, H], [False, False, False, False, False, False, False, False, True, True, False])
    with pytest.raises(ValueError, match="threat_recency"):
        rp.feasible_mask(o[:, :9], names[:9])


def test_action_mask_rules(cfg, params):
    o, names = _obs_rows(cfg, [dict(pc=1, cover=0.1)] * 4 + [dict()] + [dict(pc=1, cover=0.1)])
    pk = dict(reads=np.array([True, False, True, True, True, False]),
              wake_decide=np.array([False, False, True, False, False, False]),
              behavior=np.array([G, F, S, S, G, Z]))
    every = dict(allowed_mask=np.ones(5, dtype=bool))
    m = rp.action_mask(pk, o, every, obs_names=names)
    np.testing.assert_array_equal(m[0], [1, 1, 1, 1, 1])                   # 결정·위협·은신처: 모두 가능
    np.testing.assert_array_equal(m[1], [0, 1, 0, 0, 0])                   # 잠김: 지금 행동 한 칸
    np.testing.assert_array_equal(m[2], [1, 1, 1, 1, 0])                   # 기상 결정: SLEEP 막음
    np.testing.assert_array_equal(m[3], [1, 1, 1, 1, 1])                   # 기상 결정이 아닌 SLEEP 개체의 결정
    np.testing.assert_array_equal(m[4], [1, 0, 0, 0, 1])                   # 위협·은신처 없음: FLEE·FREEZE·HIDE 불가
    np.testing.assert_array_equal(m[5], [0, 0, 0, 1, 0])                   # 잠김: 허용 밖이어도 지금 행동
    m = rp.action_mask(pk, o, params, obs_names=names)
    np.testing.assert_array_equal(m[0], [1, 1, 1, 1, 0])                   # 허용 밖(SLEEP)은 늘 0
    m3 = rp.action_mask(pk, o, dict(allowed_mask=rp.allowed_mask_of(["graze", "flee", "hide"])), obs_names=names)
    np.testing.assert_array_equal(m3[0], [1, 1, 1, 0, 0])
    m = rp.action_mask(pk, o, params, obs_names=names)
    np.testing.assert_array_equal(m[4], [1, 0, 0, 0, 0])
    assert m.any(1).all()
    with pytest.raises(ValueError, match="빈 마스크"):
        rp.action_mask(pk, o, dict(allowed_mask=np.zeros(5, dtype=bool)), obs_names=names)
    with pytest.raises(ValueError, match="obs_names"):
        rp.action_mask(pk, o, params)


def test_world_mask_at_reset_and_over_time(cfg, params):
    """reset 직후는 모두 GRAZE 잠금이라 결정이 아닌 개체는 GRAZE 한 칸이다. 시간이 지나도 결정이 아닌 행은 늘 지금 행동 한 칸이고
    결정 행은 허용 ∧ 가능이다. 마스크는 비지 않는다."""
    w = World(cfg, seeds=[20001])
    rng = np.random.default_rng(3)
    for t in range(200):
        obs = w.observe()
        pk = w.rep_peek()
        m = rp.action_mask(w, obs, params)
        one = np.zeros_like(m)
        one[np.arange(w.N), w._rs.behavior.astype(int)] = True
        np.testing.assert_array_equal(m[~pk["reads"]], one[~pk["reads"]])
        if t == 0:
            assert (w._rs.behavior == G).all()
        dec = pk["reads"]
        np.testing.assert_array_equal(m[dec], (params["allowed_mask"] & rp.feasible_mask(obs, w.obs_names))[dec]
                                      & ~(pk["wake_decide"][dec, None] & (np.arange(5) == S)))
        assert m.any(1).all() and not m[:, S][dec].any()
        a = rp.sample_masked(np.full(m.shape, 0.2), m, rng.random(w.N))
        assert m[np.arange(w.N), a].all()
        w.step(a.astype(np.float64)[:, None])


def test_sample_masked_never_picks_blocked():
    m = np.array([[1, 0, 1, 0, 0], [0, 0, 0, 0, 1], [1, 1, 1, 0, 0]], dtype=bool)
    p = np.array([[0.5, 0.5, 0.0, 0.0, 0.0], [0.2] * 5, [0.0, 0.0, 0.0, 0.5, 0.5]])
    for u in (1e-12, 0.3, 0.5, 0.7, 1.0 - 1e-16):
        c = rp.sample_masked(p, m, np.full(3, u))
        assert m[np.arange(3), c].all()
    np.testing.assert_array_equal(rp.sample_masked(p, m, np.array([0.99, 0.5, 0.5])), [0, 4, 1])


# --------------------------------------------------------------------- #
# 분포
# --------------------------------------------------------------------- #


def _dist(logits, mask, eps=0.05, scale=1.0):
    d = rp.MaskedEpsCategorical(5, eps, scale)
    return d.proba_distribution(th.as_tensor(logits, dtype=th.float32), th.as_tensor(mask, dtype=th.bool))


def test_distribution_probs_and_eps_mix():
    logits = np.array([[0.0, 1.0, 2.0, 3.0, 4.0], [0.5, -0.5, 0.0, 9.0, 1.0], [1.0, 2.0, 3.0, 4.0, 5.0]])
    mask = np.array([[1, 1, 1, 1, 1], [1, 1, 0, 0, 1], [0, 0, 1, 0, 0]], dtype=bool)
    d = _dist(logits, mask)
    pe = d.probs_eps.numpy().astype(np.float64)
    np.testing.assert_allclose(pe.sum(1), 1.0, atol=1e-6)
    assert (pe[~mask] == 0.0).all() and (d.probs_masked().numpy()[~mask] == 0.0).all()     # 막힌 칸은 정확히 0
    for i in range(2):
        z = np.where(mask[i], logits[i], -np.inf)
        pi = np.exp(z - z.max())
        pi /= pi.sum()
        want = 0.95 * pi + 0.05 * mask[i] / mask[i].sum()
        np.testing.assert_allclose(pe[i], want, rtol=1e-5)
        for a in np.flatnonzero(mask[i]):
            lp = float(d.log_prob(th.tensor([a, a, 2]))[i])
            assert lp == pytest.approx(math.log(want[a]), rel=1e-5)
    lp = d.log_prob(th.tensor([0, 0, 2]))
    assert float(lp[2]) == 0.0                                             # 한 칸 마스크: log π′ = 0 정확히
    ent = d.raw_entropy()
    assert float(ent[2]) == 0.0 and float(d.entropy()[2]) == 0.0
    assert float(ent[0]) > 0.0
    with th.no_grad():
        s = th.stack([d.sample() for _ in range(2000)])
    assert mask[np.arange(3)[None, :].repeat(2000, 0), s.numpy()].all()     # 막힌 칸은 뽑히지 않는다


def test_distribution_entropy_scale_mode_and_grad():
    logits = th.tensor([[1.0, 1.0, 1.0, 1.0, 1.0], [0.3, 2.0, 2.0, 2.0, 0.0], [5.0, 0.0, 0.0, 0.0, 0.0]],
                       requires_grad=True)
    mask = th.tensor([[1, 1, 1, 0, 0], [0, 1, 1, 1, 1], [0, 1, 1, 0, 0]], dtype=th.bool)
    d = rp.MaskedEpsCategorical(5, 0.05, 3.0).proba_distribution(logits, mask)
    np.testing.assert_array_equal(d.mode().numpy(), [0, 1, 1])             # 동점이면 낮은 번호, 막힌 큰 로짓은 무시
    np.testing.assert_allclose(d.entropy().detach().numpy(), 3.0 * d.raw_entropy().detach().numpy())
    assert float(d.raw_entropy().detach()[0]) == pytest.approx(math.log(3.0), rel=1e-6)   # ε 제외 엔트로피
    (d.log_prob(th.tensor([1, 2, 1])).sum() + d.entropy().sum()).backward()
    assert th.isfinite(logits.grad).all()
    assert (logits.grad[~mask] == 0.0).all()                               # 막힌 칸에는 기울기가 없다
    d0 = rp.MaskedEpsCategorical(5, 0.0, 1.0).proba_distribution(logits.detach(), mask)
    np.testing.assert_allclose(d0.probs_eps.numpy(), d0.probs_masked().numpy())            # ε = 0 이면 π′ = π
    one = rp.MaskedEpsCategorical(5, 0.0, 1.0).proba_distribution(logits.detach(), th.eye(5, dtype=th.bool)[[3, 3, 3]])
    assert (one.log_prob(th.tensor([3, 3, 3])) == 0.0).all() and (one.entropy() == 0.0).all()


# --------------------------------------------------------------------- #
# 정책·VecEnv
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def venv(cfg):
    v = MultiWorldVecEnv(cfg, num_worlds=2, seeds=range(100, 120), meta_seed=0)
    yield v
    v.close()


@pytest.fixture(scope="module")
def model(venv, params):
    import train_v3

    return train_v3.make_model_rep(venv, params, None, n_steps=8, seed=0, batch_size=512)


def test_vec_env_spaces_and_masks(venv):
    from gymnasium.spaces import Discrete

    assert venv.rep is not None and venv.obs_dim == 18 and venv.policy_obs_dim == 23
    assert venv.observation_space.shape == (23,) and venv.action_space == Discrete(5)
    o = venv.reset()
    assert o.shape == (venv.num_envs, 23) and o.dtype == np.float32
    m = o[:, 18:]
    assert set(np.unique(m)) <= {0.0, 1.0} and (m.sum(1) >= 1).all()
    np.testing.assert_array_equal(m.astype(bool), venv.current_masks())
    np.testing.assert_array_equal(o[:, :18], np.concatenate([w.observe() for w in venv.worlds]))


def test_vec_env_rejects_bad_actions(cfg):
    v = MultiWorldVecEnv(cfg, num_worlds=1, seeds=range(100, 110), meta_seed=1)
    v.reset()
    m = v.current_masks()
    bad = np.argmin(m, axis=1)                                             # 막힌 칸(잠금 개체는 지금 행동 빼고 모두 막힘)
    with pytest.raises(ValueError, match="마스크"):
        v.step(bad)
    with pytest.raises(ValueError, match="정수"):
        v.step(np.full(v.num_envs, 0.5))
    with pytest.raises(ValueError, match="정수"):
        v.step(np.full(v.num_envs, 5))


def test_policy_ignores_mask_columns_and_predicts_masked_argmax(venv, model, params):
    pol = model.policy
    assert isinstance(pol, rp.RepertoirePolicy) and pol.rep_obs_dim == 18
    np.testing.assert_allclose(pol.action_net.bias.detach().numpy(), params["init_logits"], rtol=1e-6)
    o = venv.reset()
    o2 = o.copy()
    o2[:, 18:] = 1.0                                                       # 마스크만 바꾼다
    with th.no_grad():
        t1, t2 = th.as_tensor(o), th.as_tensor(o2)
        f1, f2 = pol.extract_features(t1), pol.extract_features(t2)
        th.testing.assert_close(f1, f2)
        th.testing.assert_close(pol.predict_values(t1), pol.predict_values(t2))
        logits = pol.action_net(pol.mlp_extractor.forward_actor(f1)).numpy()
    det, _ = model.predict(o, deterministic=True)
    want = np.argmax(np.where(o[:, 18:] > 0.5, logits, -np.inf), axis=1)
    np.testing.assert_array_equal(det, want)
    np.testing.assert_array_equal(det, rp.rep_argmax(pol, o))
    assert o[np.arange(len(o)), 18 + det].all()                            # 마스크 안
    pi, pe, ent = rp.rep_distribution(pol, o)
    dec = o[:, 18:].sum(1) > 1
    assert dec.any()
    p0 = np.array(params["init_probs"]) * o[dec, 18:]                      # 가중치 gain 0.01 → 시작 확률(마스크로 다시 맞춤)
    np.testing.assert_allclose(pi[dec], p0 / p0.sum(1, keepdims=True), atol=0.05)
    assert (ent[~dec] == 0.0).all()


def test_ppo_rollout_uses_masks_and_logs(venv, model):
    """짧은 학습: 표본은 마스크 안이고(세계가 받는다), 결정이 아닌 표본의 log prob 은 0 이다."""
    model.learn(total_timesteps=venv.num_envs * 8)
    buf = model.rollout_buffer
    obs = buf.observations.reshape(-1, 23)
    act = buf.actions.reshape(-1).astype(int)
    assert obs[np.arange(len(obs)), 18 + act].all()
    one = obs[:, 18:].sum(1) == 1
    np.testing.assert_array_equal(buf.log_probs.reshape(-1)[one], 0.0)
    c = venv.rep_counts
    assert c["agent_steps"] >= venv.num_envs * 8 and c["beh"].sum() == c["agent_steps"]
    assert 0 < c["decide"] < c["agent_steps"]


def test_truncated_terminal_obs_carry_mask(cfg):
    v = MultiWorldVecEnv(cfg, num_worlds=2, reset_interval=6, seeds=range(100, 120), meta_seed=2)
    o = v.reset()
    seen = 0
    for _ in range(7):
        a = np.array([np.flatnonzero(r)[0] for r in o[:, 18:] > 0.5])
        o, r, d, infos = v.step(a)
        assert o.shape == (v.num_envs, 23)
        for i in np.flatnonzero(d):
            term = infos[i]["terminal_observation"]
            assert term.shape == (23,) and term.dtype == np.float32
            assert set(np.unique(term[18:])) <= {0.0, 1.0} and term[18:].sum() >= 1
            seen += bool(infos[i].get("TimeLimit.truncated"))
    assert seen > 0 and v.num_resets >= 2


def test_vec_env_refuses_repertoire_without_block(cfg):
    t = {k: v for k, v in cfg.v2["train"].items() if k != "repertoire"}
    with pytest.raises(ValueError, match="R1"):
        MultiWorldVecEnv(cfg.replace(v2=dict(cfg.v2, train=t)), seeds=range(100, 110), meta_seed=0)
    with pytest.raises(ValueError, match="R1"):
        MultiWorldVecEnv(load_v2_config(V3R0), seeds=range(100, 110), meta_seed=0)


def test_continuous_vec_env_matches_direct_worlds():
    """repertoire 가 없는 세계(v2.4s)의 VecEnv 는 지금과 같다: 같은 시드의 World 를 직접 sigmoid 행동으로 돌린 값과 같고
    마스크 칸이 없다."""
    c = load_v2_config(V2_4S)
    v = MultiWorldVecEnv(c, num_worlds=2, reset_interval=5000, seeds=range(100, 120), meta_seed=4)
    assert v.rep is None and v.observation_space.shape == (9,) and v.action_space.shape == (5,)
    ref = [World(c, seeds=[h[0]]) for h in v.seed_history]
    o = v.reset()
    rng = np.random.default_rng(0)
    for t in range(40):
        np.testing.assert_array_equal(o, np.concatenate([w.observe() for w in ref]))
        raw = rng.uniform(-3, 3, (v.num_envs, 5)).astype(np.float32)
        o, r, d, _ = v.step(raw)
        for k, w in enumerate(ref):
            _, rr_, dd, _ = w.step(sigmoid(raw[k * w.N:(k + 1) * w.N].astype(np.float64)))
            np.testing.assert_array_equal(r[k * w.N:(k + 1) * w.N], rr_)
            np.testing.assert_array_equal(d[k * w.N:(k + 1) * w.N], dd)


def test_model_save_load_roundtrip(tmp_path, venv, model):
    from stable_baselines3 import PPO

    path = tmp_path / "rep.zip"
    model.save(path)
    assert rp.is_rep_file(path) and not rp.is_rep_file(ROOT / "ckpt" / "missing.zip")
    m2 = PPO.load(path, device="cpu")
    assert rp.is_rep_model(m2) and m2.policy.rep_allowed == ("graze", "flee", "hide", "freeze")
    o = venv.reset()
    np.testing.assert_array_equal(m2.predict(o, deterministic=True)[0], model.predict(o, deterministic=True)[0])


# --------------------------------------------------------------------- #
# 롤아웃: 세계 연결 훅·rep_learned
# --------------------------------------------------------------------- #


class _Bound:
    def __init__(self):
        self.worlds, self.dones = [], 0

    def bind_world(self, w):
        self.worlds.append(w)

    def observe_done(self, d):
        self.dones += 1

    def __call__(self, obs):
        return np.zeros((len(obs), 1))


def test_bind_world_is_forwarded_through_wrappers(cfg):
    base = _Bound()
    spec_wraps = [{"kind": "obs_fix", "dims": [0], "values": [0.5]}, {"kind": "act_fix", "dims": [], "values": [0.0]},
                  {"kind": "obs_permute", "dims": [1]}, {"kind": "act_permute"},
                  {"factory": "repertoire_rules:base_rule", "theta": 4.0, "approach": 0.9, **rr._geom(cfg)}]
    pol = base
    for w in spec_wraps:
        pol = ro.make_wrapper(w, pol, 0)
    world = World(cfg, seeds=[20000])
    ro.forward_bind(pol, world)
    ro.forward_done(pol, np.zeros(world.N, dtype=bool))
    assert base.worlds == [world] and base.dones == 1
    ro.forward_bind(object(), world)                                       # 훅이 없으면 아무 일도 없다


@pytest.fixture(scope="module")
def model_path(tmp_path_factory, model):
    p = tmp_path_factory.mktemp("rep_model") / "rep.zip"
    model.save(p)
    return p


def test_rep_learned_rollout_and_obs_fix_keeps_mask(cfg_on, model_path):
    spec = {"kind": "rep_learned", "path": str(model_path)}
    pol = ro.build_policy(spec, 10000)
    with pytest.raises(ValueError, match="bind_world"):
        pol(np.zeros((128, 18), dtype=np.float32))
    r = ro.rollout(cfg_on, ro.build_policy(spec, 10000), 10000, 120, tail=20)
    assert math.isfinite(r["g_gamma"]) and set(ro.REPERTOIRE_COLUMNS) <= set(r)
    # 망 입력만 고친 C4 변형도 마스크는 참 상태로 만든다: 같은 세계에서 두 정책의 마스크가 같다
    names = list(obs_names(cfg_on))
    fixed = ro.build_policy({"policy": spec, "wrap": [{"kind": "obs_fix", "dims": [names.index("pred_count"),
                                                                                  names.index("cover_dist")],
                                                       "values": [0.0, 1.0]}]}, 10000)
    plain = ro.build_policy(spec, 10000)
    w = World(cfg_on, seeds=[10003])
    ro.forward_bind(fixed, w)
    ro.forward_bind(plain, w)
    for _ in range(60):
        obs = w.observe()
        a = fixed(obs)
        b = plain(obs)
        inner = fixed.base
        np.testing.assert_array_equal(inner.last_mask, plain.last_mask)
        assert plain.last_mask[np.arange(w.N), b[:, 0].astype(int)].all()
        assert inner.last_mask[np.arange(w.N), a[:, 0].astype(int)].all()
        w.step(b)


def test_rep_learned_checks_world(model_path):
    pol = ro.build_policy({"kind": "rep_learned", "path": str(model_path)}, 0)
    with pytest.raises(ValueError, match="관측"):
        pol.bind_world(World(load_v2_config(V3R0_ON), seeds=[0]))          # obs_extra 가 없는 세계
    with pytest.raises(ValueError, match="argmax"):
        ro.build_policy({"kind": "rep_learned", "path": str(model_path), "mode": "stochastic"}, 0)


# --------------------------------------------------------------------- #
# 학습·f_dec·판정 도구
# --------------------------------------------------------------------- #


def test_measure_fdec_smoke(cfg):
    import train_v3

    res = train_v3.measure_fdec(cfg, seeds=[20000], steps=40)
    assert 0.0 < res["f_dec"] <= 1.0 and res["allowed"] == ["graze", "flee", "hide", "freeze"]
    assert res["per_seed"][0]["f_dec"] == res["per_seed"][0]["decide_frac_world"]


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    """train_v3 를 롤아웃 한 번(32,768 스텝) 돌린다: 저장·메타·학습 기록·체크포인트."""
    import train_v3

    d = tmp_path_factory.mktemp("v3_train")
    out = d / "smoke.zip"
    assert train_v3.main(["--config", str(V3R1), "--steps", "20000", "--seed", "0", "--out", str(out),
                          "--tb", str(d / "tb"), "--every", "16384"]) == 0
    return out, json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))


def test_train_v3_smoke(trained):
    out, meta = trained
    assert out.exists() and rp.is_rep_file(out)
    assert meta["gamma"] == 0.995 and meta["gamma_source"] == "s1a"
    assert meta["ent_coef"] == 0.0008971496690499397
    assert meta["cat_ent_coef"] == pytest.approx(meta["repertoire"]["ent_coef_base"] / meta["repertoire"]["f_dec"])
    assert meta["ppo"]["batch_size"] == 4096 and meta["ppo"]["n_steps"] == 32 and meta["ppo"]["n_epochs"] == 15
    assert meta["num_worlds"] == 8 and meta["reset_interval"] == 5000
    rows = [json.loads(x) for x in out.with_suffix(".log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows and rows == meta["log_history"]
    r = rows[-1]
    for k in ("use_graze", "use_flee", "use_hide", "decide_frac", "ent_dec", "starve_rate", "pred_rate",
              "pi_flee_niche", "pi_hide_niche", "pi_freeze_niche", "pi_freeze_base", "pi_esc_niche"):
        assert k in r, k
    assert r["use_sleep"] == 0.0 and "pi_sleep_niche" not in r               # 목록 밖 행동(SLEEP)은 쓰이지 않는다
    assert meta["freeze_variant"] == "near"
    assert meta["checkpoints"] and (out.parent / meta["checkpoints"][0]).exists()


def _eval_module():
    import eval_v3

    return eval_v3


def test_eval_u_terms_and_fsm_priority(cfg_on):
    ev = _eval_module()
    names = list(obs_names(cfg_on))
    geo = rr._geom(cfg_on)

    def row(pc=0, dist=20.0, app=0.5, cover=20.0, energy=0.8, vis=1.0):
        o = np.zeros(len(names), dtype=np.float32)
        o[names.index("pred_count")] = pc / 8.0
        o[names.index("pred_dist")] = dist / cfg_on.see_r
        o[names.index("pred_approach")] = app
        o[names.index("cover_dist")] = cover / cfg_on.obs_cover_norm
        o[names.index("energy")] = energy
        o[names.index("visibility")] = vis
        return o
    o = np.stack([row(), row(pc=1, dist=8.0, app=0.8), row(pc=1, dist=12.0, app=0.5, cover=3.0),
                  row(pc=1, dist=5.0), row(vis=0.5, energy=0.6), row(pc=1, dist=9.0, app=0.6)])
    f = rr.features_of_obs(o, geo)
    t = ev.u_terms(f, "near")
    np.testing.assert_array_equal(t["esc"][0], [0, 1, 0, 0, 0, 0])
    np.testing.assert_array_equal(t["esc"][1], [1, 0, 0, 0, 1, 0])
    np.testing.assert_array_equal(t["hide"][0], [0, 0, 1, 0, 0, 0])
    np.testing.assert_array_equal(t["hide"][1], [1, 0, 0, 0, 0, 0])
    np.testing.assert_array_equal(t["freeze"][0], [0, 0, 0, 1, 0, 0])
    np.testing.assert_array_equal(t["freeze"][1], [0, 0, 1, 0, 0, 1])
    to = ev.u_terms(f, "orig")
    np.testing.assert_array_equal(to["freeze"][0], t["freeze"][1])
    np.testing.assert_array_equal(t["sleep"][0], [0, 0, 0, 0, 1, 0])
    assert ev.u_value([10, 6, 20, 2]) == pytest.approx(0.5) and ev.u_value([0, 0, 5, 1]) is None
    assert ev.active_u(("graze", "flee", "hide")) == ("esc", "hide")
    assert ev.active_u(("graze", "flee", "hide", "freeze")) == ("esc", "hide", "freeze")
    # FSM: R_base(θ 4, a 0.9) + 니치 규칙, 우선순위 HIDE > FREEZE > SLEEP > R_base
    o2 = np.stack([row(pc=1, dist=3.0, cover=3.0), row(pc=1, dist=3.0), row(pc=1, dist=10.0),
                   row(vis=0.5, energy=0.8, cover=0.0), row(pc=1, dist=3.0, vis=0.5, energy=0.8, cover=0.0)])
    allowed = ("graze", "flee", "hide", "freeze", "sleep")
    near = ro.build_policy(ev.fsm_spec(cfg_on, allowed, "near"), 0)(o2)[:, 0].astype(int).tolist()
    assert near == [H, Z, G, S, H]
    orig = ro.build_policy(ev.fsm_spec(cfg_on, allowed, "orig"), 0)(o2)[:, 0].astype(int).tolist()
    assert orig == [H, F, Z, S, H]
    only = ro.build_policy(ev.fsm_spec(cfg_on, ("graze", "flee"), "near"), 0)(o2)[:, 0].astype(int).tolist()
    assert only == [F, F, G, G, F]
    final = ro.build_policy(ev.fsm_spec(cfg_on, ("graze", "flee", "hide", "freeze"), "near"), 0)(o2)
    assert final[:, 0].astype(int).tolist() == [H, Z, G, G, H]              # R1 목록: HIDE > FREEZE(가까운 위협) > R_base
    c = ev.ConstRequest(H, names)(o2)[:, 0].astype(int).tolist()
    assert c == [H, G, G, G, H]                     # 은신처가 멀거나(관측 ≥ 0.75) 위협을 모르면(행 3) GRAZE


def test_eval_c1prime_is_masked_and_deterministic(cfg_on, params):
    ev = _eval_module()
    outs = []
    for _ in range(2):
        w = World(cfg_on, seeds=[10001])
        pol = ev.C1Prime([0.5, 0.3, 0.2, 0.0, 0.0], params["allowed_mask"], 10001)
        ro.forward_bind(pol, w)
        seq = []
        for _ in range(80):
            m = rp.action_mask(w, w.observe(), params)
            a = pol(w.observe())
            assert m[np.arange(w.N), a[:, 0].astype(int)].all()
            seq.append(a[:, 0].copy())
            _, _, d, _ = w.step(a)
            ro.forward_done(pol, d)
        outs.append(np.stack(seq))
    np.testing.assert_array_equal(outs[0], outs[1])


def test_eval_gate_logic():
    ev = _eval_module()

    def pol(starve, u, use, flicker=0.05):
        return dict(starve_rate=starve, u=u, use=use, flicker=flicker)
    use = dict(graze=0.8, flee=0.1, hide=0.1, freeze=0.0, sleep=0.0)
    res = dict(pooled=dict(rl=pol(0.001, dict(esc=0.6, hide=0.35, freeze=None, sleep=None), use),
                           fsm=pol(0.001, {}, use)),
               perf=dict(mean=0.1, t=1.0, n=20, crit=2.093), c4_drop={})
    g = ev.gate(res, ("graze", "flee", "hide"), "near")
    assert g["pass_"] and not g["perf"]["beats_fsm"]
    res["perf"]["t"] = -2.2
    assert not ev.gate(res, ("graze", "flee", "hide"), "near")["perf"]["pass_"]
    res["perf"]["t"] = 2.5
    g = ev.gate(res, ("graze", "flee", "hide"), "near")
    assert g["perf"]["beats_fsm"] and g["pass_"]
    res["pooled"]["rl"]["starve_rate"] = 0.0016                              # 1.5 × FSM 초과
    assert not ev.gate(res, ("graze", "flee", "hide"), "near")["starve"]["pass_"]
    res["pooled"]["rl"]["starve_rate"] = 0.001
    res["pooled"]["rl"]["use"] = dict(use, hide=0.01)
    assert not ev.gate(res, ("graze", "flee", "hide"), "near")["use"]["pass_"]
    res["pooled"]["rl"]["use"] = use
    res["pooled"]["rl"]["u"]["hide"] = 0.29
    assert not ev.gate(res, ("graze", "flee", "hide"), "near")["u"]["pass_"]
    res["pooled"]["rl"]["u"].update(hide=0.4, sleep=0.6)
    res["c4_drop"] = {"c4_phase": dict(sleep=0.4)}
    g = ev.gate(res, ("graze", "flee", "hide", "sleep"), "near")
    assert not g["dep"]["pass_"] and set(g["dep"]["items"]) == {"sleep_phase"}
    assert ev.drop(0.5, 0.2) == pytest.approx(0.6) and ev.drop(0.0, 0.1) is None


def test_eval_smoke_and_prereg_guard(trained, tmp_path):
    ev = _eval_module()
    out, _ = trained
    res = ev.judge(str(out), "smoke", [10000, 10001], 300, tmp_path, tail=100, workers=1)
    assert (tmp_path / "smoke.json").exists() and (tmp_path / "smoke.md").exists()
    P = res["pooled"]
    assert set(P) == {"rl", "fsm", "c_graze", "c_flee", "c_hide", "c_freeze", "c1p", "c4_app", "c4_phase"}
    for name, v in P.items():
        assert math.isfinite(v["g_gamma"]), name
        assert v["use"]["sleep"] == 0.0, name
    assert P["c_graze"]["use"]["graze"] == 1.0 and P["c_freeze"]["use"]["freeze"] > 0.0
    assert set(res["gate"]) == {"perf", "u", "use", "dep", "starve", "pass_"}
    assert res["meta"]["freeze_variant"] == "near"                          # 기본은 '가까운 위협 앞 얼기' 판
    assert set(res["gate"]["u"]["items"]) == {"esc", "hide", "freeze"}
    assert set(res["gate"]["dep"]["items"]) == {"freeze_app"}
    assert "smoke" in (tmp_path / "smoke.md").read_text(encoding="utf-8")
    text = ev.summarize(["smoke"], tmp_path)
    assert "통과" in text and (tmp_path / "judge.md").exists()
    with pytest.raises(SystemExit):
        ev.main(["run", "--model", str(out), "--name", "x", "--seeds", "10000", "--steps", "10"])
    assert not (ev.PREREG_OUT / "x.json").exists()


def test_replay_frames_carry_animation_state(cfg_on, model_path, tmp_path):
    """명세 6절: repertoire 세계의 리플레이 프레임에 behavior·phase·steps_in·seq 넷이 있다. rep_learned 도 리플레이에서 돈다."""
    import replay_v2 as R

    run = R.run_policy(cfg_on, {"kind": "rep_learned", "path": str(model_path)}, 10002, 20, 5, label="R1")
    f = run.frames[-1]
    for k in ("beh", "beh_phase", "beh_steps", "beh_seq"):
        assert f[k].shape == (cfg_on.N,), k
    w2 = World(load_v2_config(V2_4S), seeds=[0])
    w2.step(np.tile([0.97099, 0.78494, 0.21823, 0.03359, 0.49137], (w2.N, 1)))
    assert "beh_steps" not in R._applied(w2, None)
