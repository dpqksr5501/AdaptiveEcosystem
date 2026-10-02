"""0-7 도구 보강의 단위 테스트 (계획서 0-7, 4.7 γ 선택 규칙, 6.1-4·6.1-7, #27·#29).

- train_v2 --gamma: γ 만 바뀌고 메타 JSON·모델에 실제 γ 가 남는다
- 확률 모드: 학습 분포 표본, 평가 시드로 재현, 평균이 결정 모드와 다르다, 잡음 0 이면 결정 모드와 같다
- 앞 제외(head): G_γ 평균에서 앞부분을 뺀다. 기본 0 은 예전과 같다
- 캐시 키·기본 이름·이전 결과 재사용 조건이 모드·앞 제외를 구분한다
- γ 선택(gammasel)·모드 비교(modecmp) 계산이 results/v2/g07/PREREG.md 의 절차와 같다

학습은 1회(롤아웃 한 번)만 돌린다. 나머지는 손으로 셀 수 있는 작은 예와 합성 결과 JSON 이다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import json
import math

import numpy as np
import pytest

import diagnose_v2 as dg
from env_v2 import features as F
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.world import World
from policies.registry import make_policy

TINY_V2 = """version: "2.0"
overrides: {}
features: {}
train:
  num_worlds: 1
  reset_interval: 4000
  rollout_world_steps: 8
"""

# 작은 롤아웃(1,024)에 v1 batch_size 4096 을 그대로 써서 SB3 가 내는 경고. 테스트 크기 탓이라 끈다.
pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")

# 행동 평균(자르기 전)과 log_std. 3.5 는 [-3, 3] 밖이라 자르기를 함께 본다.
BIAS = [2.0, -1.0, 0.5, 3.5]
LOG_STD = [-0.5, 0.0, 0.3, 0.0]


# --------------------------------------------------------------------- #
# 공용: 작은 PPO 모델
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def tiny_model(tmp_path_factory):
    """무작위 초기화 PPO 에 행동 평균 편향과 log_std 를 박아 저장한다. action_net 가중치는 SB3 기본
    (직교 초기화, gain 0.01)이라 μ ≈ BIAS 다."""
    import torch as th
    from env_v2.vec_env import MultiWorldVecEnv
    from train import make_model

    d = tmp_path_factory.mktemp("tiny_model")
    cfg = load_v2_config()
    venv = MultiWorldVecEnv(cfg, num_worlds=1)
    model = make_model(venv, tensorboard_log=None, n_steps=8, seed=0)
    with th.no_grad():
        model.policy.action_net.bias.copy_(th.tensor(BIAS))
        model.policy.log_std.copy_(th.tensor(LOG_STD))
    path = d / "m.zip"
    model.save(path)
    return path


def _obs(n=128, seed=0):
    return np.random.default_rng(seed).random((n, 7)).astype(np.float32)


# --------------------------------------------------------------------- #
# 1) train_v2 --gamma
# --------------------------------------------------------------------- #


def test_train_gamma_cli_is_recorded_and_only_gamma_changes(tmp_path):
    """--gamma 0.998 로 1회 학습: 메타 JSON 의 gamma·gamma_source, 모델 zip 의 γ 가 0.998 이고 다른 튜닝값은 그대로."""
    import yaml
    import train_v2

    cfg = tmp_path / "tiny.yaml"
    cfg.write_text(TINY_V2, encoding="utf-8")
    out = tmp_path / "g998.zip"
    assert train_v2.main(["--steps", "1", "--seed", "0", "--gamma", "0.998", "--config", str(cfg),
                          "--out", str(out), "--tb", str(tmp_path / "tb"), "--threads", "1"]) == 0
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["gamma"] == 0.998 and meta["gamma_source"] == "cli"
    assert meta["ppo"]["gamma"] == 0.998
    assert ro.model_gamma(out) == 0.998
    tuned = yaml.safe_load((train_v2.ROOT / "configs" / "ppo_best.yaml").read_text(encoding="utf-8"))["params"]
    for k in ("learning_rate", "ent_coef", "clip_range", "n_epochs"):
        assert meta["ppo"][k] == pytest.approx(float(tuned[k])), k
    assert "--gamma 0.998" in meta["command"]


def test_resolve_gamma_sources_and_run_name():
    from train import PPO_KWARGS
    from train_v2 import default_run_name, gamma_tag, resolve_gamma

    tuned = {"gamma": 0.9916661555611042, "learning_rate": 1e-4}
    t, g, src = resolve_gamma(tuned, None)
    assert (g, src) == (0.9916661555611042, "ppo_config") and t == tuned
    t, g, src = resolve_gamma(tuned, 0.995)
    assert (g, src) == (0.995, "cli") and t == {"gamma": 0.995, "learning_rate": 1e-4}
    assert tuned["gamma"] == 0.9916661555611042                      # 원본은 그대로
    assert resolve_gamma({}, None)[1:] == (PPO_KWARGS["gamma"], "PPO_KWARGS")
    for bad in (0.0, 1.0, 1.5, -0.1):
        with pytest.raises(SystemExit):
            resolve_gamma(tuned, bad)
    cfg = load_v2_config()
    assert default_run_name(cfg, 0, 20_000_000) == "v2_0_s0_20m"                 # --gamma 없으면 예전 이름
    assert default_run_name(cfg, 1, 20_000_000, 0.998) == "v2_0_g998_s1_20m"
    assert gamma_tag(0.995) == "g995" and gamma_tag(0.9916661555611042) == "g991666"


# --------------------------------------------------------------------- #
# 2) 확률 모드
# --------------------------------------------------------------------- #


def test_stochastic_mode_is_reproducible_per_seed(tiny_model):
    spec = {"kind": "learned", "model": str(tiny_model), "mode": "stochastic"}
    obs = [_obs(seed=k) for k in range(3)]
    a1 = ro.build_policy(spec, 10000)(obs[0])
    p1, p2, p3 = ro.build_policy(spec, 10000), ro.build_policy(spec, 10000), ro.build_policy(spec, 10001)
    s1 = np.stack([p1(o) for o in obs])
    s2 = np.stack([p2(o) for o in obs])
    s3 = np.stack([p3(o) for o in obs])
    np.testing.assert_array_equal(s1, s2)                       # 같은 평가 시드 → 같은 행동열
    np.testing.assert_array_equal(s1[0], a1)
    assert not np.array_equal(s1, s3)                           # 시드가 다르면 다른 잡음
    assert ((s1 >= 0) & (s1 <= 1)).all()
    # 래퍼 스펙 안에서도 바탕 정책이 같은 스트림을 받는다
    wrapped = {"policy": spec, "wrap": [{"kind": "act_fix", "dims": [1], "values": [0, 0.5, 0, 0]}]}
    w = ro.build_policy(wrapped, 10000)(obs[0])
    np.testing.assert_array_equal(w[:, [0, 2, 3]], s1[0][:, [0, 2, 3]])
    assert (w[:, 1] == 0.5).all()


def test_stochastic_mean_differs_from_deterministic_and_zero_noise_equals_it(tiny_model):
    det = ro.build_policy({"kind": "learned", "model": str(tiny_model)}, 0)
    sto = ro.build_policy({"kind": "learned", "model": str(tiny_model), "mode": "stochastic"}, 7)
    assert isinstance(sto, ro.StochasticLearned)
    obs = _obs()
    a_det = det(obs)
    mu, std = sto.distribution(obs)
    np.testing.assert_allclose(std, np.broadcast_to(np.exp(LOG_STD), std.shape), rtol=1e-6)
    np.testing.assert_allclose(mu, np.broadcast_to(BIAS, mu.shape), atol=0.1)
    # 결정 모드 = sigmoid(clip(μ)). 확률 모드의 잡음을 0 으로 두면 같다 (자르기 포함, BIAS[3]=3.5)
    zero = ro.StochasticLearned(sto.model, 7)
    zero.rng = type("Z", (), {"standard_normal": staticmethod(lambda shape: np.zeros(shape))})()
    np.testing.assert_allclose(zero(obs), a_det, atol=1e-6)
    np.testing.assert_allclose(a_det[:, 3], 1 / (1 + np.exp(-3.0)), atol=1e-6)
    # 표본 평균은 결정 모드와 다르다: sigmoid 가 휘고 [-3,3] 에서 잘리므로 E[σ(μ+sε)] ≠ σ(μ)
    m = np.mean([sto(obs) for _ in range(300)], axis=0).mean(0)
    d = a_det.mean(0)
    assert m[0] < d[0] - 0.008           # μ=2: 위로 볼록한 쪽이라 평균이 내려간다
    assert m[1] > d[1] + 0.01            # μ=-1: 아래로 볼록한 쪽이라 올라간다
    assert m[3] < d[3] - 0.01            # μ=3.5 → 결정은 σ(3), 표본은 σ(3) 아래로만 퍼진다
    # 원시 표본의 분포는 N(μ, exp(log_std)) 를 [-3,3] 로 자른 것이다 (자르기가 드문 차원 0·1 에서 확인)
    rng = ro._perm_rng("act_sample", 7, 0)
    eps = rng.standard_normal((128, 4))
    raw = np.clip(mu + std * eps, -3, 3)
    np.testing.assert_allclose(ro.build_policy({"kind": "learned", "model": str(tiny_model),
                                                "mode": "stochastic"}, 7)(obs), 1 / (1 + np.exp(-raw)),
                               atol=1e-12)


def test_stochastic_rollout_is_reproducible(tiny_model):
    cfg = load_v2_config()
    spec = {"kind": "learned", "model": str(tiny_model), "mode": "stochastic"}
    r1 = ro.rollout(cfg, ro.build_policy(spec, 10000), 10000, 15, tail=0)
    r2 = ro.rollout(cfg, ro.build_policy(spec, 10000), 10000, 15, tail=0)
    rd = ro.rollout(cfg, ro.build_policy({"kind": "learned", "model": str(tiny_model)}, 10000), 10000, 15, tail=0)
    assert ro.public_row(r1) == ro.public_row(r2)
    np.testing.assert_array_equal(r1["_act_sum"], r2["_act_sum"])
    assert not np.array_equal(r1["_act_sum"], rd["_act_sum"])


def test_action_mode_parsing():
    assert ro.action_mode({"kind": "learned", "model": "m"}) == "deterministic"
    assert ro.action_mode({"policy": {"kind": "learned", "model": "m", "mode": "stochastic"}, "wrap": []}) \
        == "stochastic"
    with pytest.raises(ValueError):
        ro.action_mode({"kind": "learned", "model": "m", "mode": "sample"})
    with pytest.raises(ValueError, match="학습 정책"):
        ro.build_policy({"kind": "utility", "mode": "stochastic"}, 0)


@pytest.mark.parametrize("seed", [0, 5, 636, 10000])
def test_act_sample_stream_is_distinct(seed):
    """확률 모드 잡음 스트림 [seed, 303, salt] 은 v1 세계·기능·순열 대조군 스트림과 다르다."""
    def head(g):
        return g.integers(0, 2**63 - 1, size=4)
    heads = {("v1",): head(np.random.default_rng(seed))}
    for name in F.FEATURE_IDS:
        for part in (0, 1):
            heads[(name, part)] = head(F.feature_stream(seed, name, part))
    for kind in ("act_permute", "obs_permute", "act_sample"):
        for salt in (0, 1, 2):
            heads[(kind, salt)] = head(ro._perm_rng(kind, seed, salt))
    blobs = {k: v.tobytes() for k, v in heads.items()}
    assert len(set(blobs.values())) == len(blobs)
    assert ro._SALT["act_sample"] not in (0, F.STREAM_DOMAIN, ro._SALT["act_permute"], ro._SALT["obs_permute"])


# --------------------------------------------------------------------- #
# 3) 앞 제외 (head)
# --------------------------------------------------------------------- #


def test_g_gamma_head_excludes_front_only_from_the_mean():
    """γ=0.5. 리턴-투-고는 롤아웃 전체로 계산하고 앞 head·끝 tail 스텝만 평균에서 뺀다."""
    rew = np.array([[1.0, 0.0], [2.0, 0.0], [3.0, 4.0], [1.0, 1.0]])
    done = np.array([[0, 0], [1, 0], [0, 0], [0, 0]], dtype=bool)
    G = ro.discounted_return_to_go(rew, done, 0.5)
    assert ro.g_gamma(rew, done, 0.5, tail=1) == ro.g_gamma(rew, done, 0.5, tail=1, head=0)   # 기본 0 = 예전
    assert ro.g_gamma(rew, done, 0.5, tail=1, head=1) == pytest.approx(G[1:3].mean())
    assert ro.g_gamma(rew, done, 0.5, tail=0, head=2) == pytest.approx(G[2:].mean())
    assert G[1, 1] == pytest.approx(0.0 + 0.5 * (4.0 + 0.5 * 1.0))     # 앞을 빼도 뒤 보상은 그대로 들어간다
    assert math.isnan(ro.g_gamma(rew, done, 0.5, tail=2, head=2))     # 남는 스텝이 없다
    with pytest.raises(ValueError):
        ro.g_gamma(rew, done, 0.5, tail=0, head=-1)


def test_rollout_head_changes_only_g_gamma():
    cfg = load_v2_config()
    spec = {"kind": "fixed", "action": [0.3, 0.8, 0.4, 0.1]}
    r0 = ro.rollout(cfg, ro.build_policy(spec, 0), 10000, 30, tail=5)
    r1 = ro.rollout(cfg, ro.build_policy(spec, 0), 10000, 30, tail=5, head=10)
    w, pol, rew, done = World(cfg, seeds=[10000]), make_policy(spec), [], []
    for _ in range(30):
        _, rr, dd, _ = w.step(pol(w.observe()))
        rew.append(rr)
        done.append(dd)
    g = ro.load_gamma()
    assert r1["g_gamma"] == pytest.approx(ro.g_gamma(np.array(rew), np.array(done), g, 5, 10))
    assert r0["g_gamma"] == pytest.approx(ro.g_gamma(np.array(rew), np.array(done), g, 5))
    assert r0["g_gamma"] != r1["g_gamma"]
    for c in ro.STAT_COLUMNS:
        assert r0[c] == r1[c] or (math.isnan(r0[c]) and math.isnan(r1[c])), c
    # 워커 경로(run_specs → _run_one)도 head 를 넘긴다
    res = ro.run_specs(cfg, {"x": spec}, [10000], 30, workers=1, tail=5, head=10)
    assert res["x"][0]["g_gamma"] == pytest.approx(r1["g_gamma"])


def test_g998_preset_and_defaults(tiny_model):
    P = dg.build_parser()
    ctx = dg.Ctx(P.parse_args(["ablate", "--model", str(tiny_model)]))
    assert (ctx.gamma, ctx.eval_steps, ctx.head, ctx.act_mode) == (pytest.approx(ro.model_gamma(tiny_model)),
                                                                   5000, 0, "deterministic")
    ctx = dg.Ctx(P.parse_args(["ablate", "--model", str(tiny_model), "--g998"]))
    assert (ctx.gamma, ctx.eval_steps, ctx.head, ctx.tail) == (0.998, 10000, 500, 2500)
    assert ctx.name.endswith("_g998")
    dg.Ctx(P.parse_args(["ablate", "--model", str(tiny_model), "--g998", "--eval-steps", "10000"]))   # 같은 값은 받는다
    for extra in (["--eval-steps", "5000"], ["--gamma", "0.995"], ["--head", "0"], ["--tail", "600"]):
        with pytest.raises(SystemExit):
            dg.Ctx(P.parse_args(["ablate", "--model", str(tiny_model), "--g998", *extra]))
    m = dg.md_meta({"eval_seeds": [10000, 10019], "eval_steps": 5000, "gamma": 0.99, "tail": 500})
    assert m[3] == "- G_γ: γ=0.99, 롤아웃 끝 500스텝(ceil(5/(1-γ)))은 평균에서 뺐다"               # 예전 문구 그대로
    assert m[2].endswith("deterministic")
    m = dg.md_meta({"eval_seeds": [10000], "eval_steps": 10000, "gamma": 0.998, "tail": 2500, "head": 500,
                    "act_mode": "stochastic"})
    assert "앞 500스텝" in m[3] and "stochastic" in m[2]


# --------------------------------------------------------------------- #
# 4) 캐시 키와 이름
# --------------------------------------------------------------------- #


def test_cache_key_and_name_separate_modes(tiny_model, tmp_path):
    P = dg.build_parser()
    det = dg.Ctx(P.parse_args(["ablate", "--model", str(tiny_model), "--out", str(tmp_path)]))
    sto = dg.Ctx(P.parse_args(["ablate", "--model", str(tiny_model), "--out", str(tmp_path),
                               "--act-mode", "stochastic"]))
    pd, md = dg.calib_cache_key(det)
    ps, ms = dg.calib_cache_key(sto)
    assert pd.name == "calib.npz" and ps.name == "calib_stochastic.npz"
    # 결정 모드 키는 예전 형식 그대로다 (기존 캐시를 그대로 쓴다)
    assert set(md) == {"spec", "seeds", "steps", "record_every", "config_digest", "model_sha1"}
    assert md["spec"] == {"kind": "learned", "model": str(tiny_model.resolve())}
    assert ms["act_mode"] == "stochastic" and ms["spec"]["mode"] == "stochastic" and md != ms
    assert det.name == "m" and sto.name == "m_stoch"
    named = dg.Ctx(P.parse_args(["ablate", "--model", str(tiny_model), "--name", "same", "--act-mode", "stochastic"]))
    assert dg.calib_cache_key(named)[0].name == "calib_stochastic.npz"   # 같은 --name 이어도 파일이 갈린다
    with pytest.raises(SystemExit):
        dg.Ctx(P.parse_args(["ablate", "--policy", "utility", "--act-mode", "stochastic"]))


def test_reference_rows_require_same_mode_and_head(tiny_model, tmp_path):
    """constsearch·permute 가 이전 ablate 의 C0 행을 재사용하는 조건에 모드와 앞 제외가 들어간다."""
    P = dg.build_parser()
    base = ["ablate", "--model", str(tiny_model), "--out", str(tmp_path)]
    det = dg.Ctx(P.parse_args(base))
    rows = [{"seed": s, "g_gamma": 1.0} for s in det.eval_seeds]
    dg.save_json(tmp_path / "ablate.json", {"meta": det.meta(), "per_seed": {"C0": rows}})
    assert dg.reference_rows(det, "C0") == rows
    assert dg.reference_rows(dg.Ctx(P.parse_args(base + ["--act-mode", "stochastic"])), "C0") is None
    assert dg.reference_rows(dg.Ctx(P.parse_args(base + ["--head", "100"])), "C0") is None
    # 예전 JSON(head·act_mode 키 없음)은 결정 모드·앞 제외 0 으로 본다
    old = {k: v for k, v in det.meta().items() if k not in ("head", "act_mode", "model_gamma")}
    dg.save_json(tmp_path / "ablate.json", {"meta": old, "per_seed": {"C0": rows}})
    assert dg.reference_rows(det, "C0") == rows


# --------------------------------------------------------------------- #
# 5) γ 선택·모드 비교 계산 (합성 결과)
# --------------------------------------------------------------------- #

EVAL = list(range(10000, 10020))


def _fake(gamma, run, g, *, act_mode="deterministic", c1=None, cond=None, sha=None, extra=None):
    """ablate.json 모양의 합성 결과. g 는 평가 시드 20개의 G 값."""
    meta = {"eval_seeds": EVAL, "eval_steps": 10000, "gamma": 0.998, "tail": 2500, "head": 500,
            "act_mode": act_mode, "config_digest": "cfg", "config_version": "2.0", "model_gamma": gamma,
            "model_sha1": sha or f"{gamma}-{run}", "spec": {"kind": "learned", "model": f"none/{gamma}_{run}.zip"}}
    meta.update(cond or {})
    def rows(vals):
        out = []
        for s, v in zip(EVAL, vals):
            r = {"seed": s, "g_gamma": float(v), "survival": 400.0 + v, "starve_rate": 1e-4,
                 "predation_rate": 1e-3 - 1e-5 * v, "mean_return": 30.0 + v}
            for c in dg.BEHAVIOR + ["repro"]:
                r[c] = 0.5
            r.update((extra or {}))
            out.append(r)
        return out
    per = {"C0": rows(g)}
    if c1 is not None:
        per["C1"] = rows(c1)
    return {"meta": meta, "per_seed": per, "_dir": f"fake/{gamma}_{run}"}


def _arms(means, noise=0.05, seed=0, spread=None):
    rng = np.random.default_rng(seed)
    ds = []
    for g, mu in means.items():
        for run in (0, 1):
            off = 0.0 if spread is None else spread.get(g, 0.0) * (1 if run == 0 else -1)
            ds.append(_fake(g, run, mu + off + noise * rng.standard_normal(20)))
    return ds


def test_gamma_select_picks_best_when_others_clearly_lower():
    ds = _arms({0.9916661555611042: 10.0, 0.995: 10.5, 0.998: 12.0})
    r = dg.gamma_select(ds, reps=500)
    assert r["best"] == 0.998 and r["selected"] == 0.998
    small = [a for a in r["arms"] if a["gamma"] != 0.998]
    assert all(a["test"]["sig"] and not a["test"]["eligible"] for a in small)
    a0 = r["arms"][0]
    assert a0["test"]["diff"] == pytest.approx(a0["mean"]["g_gamma"] - r["arms"][2]["mean"]["g_gamma"])
    assert a0["test"]["t"] < -2.093 and a0["test"]["ci"]["hi"] < 0


def test_gamma_select_picks_smallest_not_different():
    """최고값과 차이가 잡음 안이면 가장 작은 γ."""
    ds = _arms({0.9916661555611042: 10.0, 0.995: 10.02, 0.998: 10.03}, noise=0.5)
    r = dg.gamma_select(ds, reps=500)
    assert r["selected"] == 0.9916661555611042
    assert all(a["test"]["eligible"] for a in r["arms"])


def test_gamma_select_ties_and_layer_disagreement():
    # 평균이 같으면 작은 γ 가 최고값이다
    ds = _arms({0.995: 10.0, 0.998: 10.0}, noise=0.0)
    assert dg.gamma_select(ds, reps=200)["best"] == 0.995
    # 학습 시드 평균은 늘 1 낮지만(t 유의) 학습 시드 둘이 ±10 으로 갈려 CI 가 0 을 포함 → 자격 있음
    rng = np.random.default_rng(3)
    alt = np.where(np.arange(20) % 2 == 0, 10.0, -10.0)
    best = rng.standard_normal(20)
    ds = [_fake(0.995, 0, best - 1 + alt + 0.01 * rng.standard_normal(20)),
          _fake(0.995, 1, best - 1 - alt + 0.01 * rng.standard_normal(20)),
          _fake(0.998, 0, best), _fake(0.998, 1, best)]
    r = dg.gamma_select(ds, reps=2000)
    t = r["arms"][0]["test"]
    assert t["sig_t"] and not t["ci_excludes_0"] and t["layers_disagree"]
    assert t["eligible"] and r["selected"] == 0.995


def test_gamma_select_refuses_wrong_conditions():
    ok = _arms({0.995: 10.0, 0.998: 10.0})
    dg.gamma_select(ok, reps=50)
    bad_cases = [
        ok[:3],                                                             # 학습 시드 수가 팔마다 다르다
        [ok[0], ok[2]],                                                     # 팔마다 1개
        ok[:2],                                                             # γ 하나
        ok + [dict(ok[0])],                                                 # 같은 모델 두 번
    ]
    for cond in ({"gamma": 0.995}, {"eval_steps": 5000}, {"head": 0}, {"act_mode": "stochastic"},
                 {"config_digest": "other"}, {"eval_seeds": list(range(10000, 10010))},
                 {"config_version": "2.0b"}):
        bad_cases.append(ok[:3] + [_fake(0.998, 1, np.zeros(20), cond=cond)])
    for ds in bad_cases:
        with pytest.raises(SystemExit):
            dg.gamma_select(ds, reps=50)


def test_gamma_select_refuses_different_train_seed_sets(monkeypatch):
    """PREREG 1절: 세 팔 모두 학습 시드 0·1. 학습 메타로 시드를 알면 팔마다 같은 묶음이어야 한다."""
    ds = _arms({0.995: 10.0, 0.998: 10.0})
    seeds = {"0.995-0": 0, "0.995-1": 1, "0.998-0": 0, "0.998-1": 1}
    monkeypatch.setattr(dg, "train_seed_of", lambda d: seeds[d["meta"]["model_sha1"]])
    assert dg.gamma_select(ds, reps=50)["arms"][0]["train_seeds"] == [0, 1]
    seeds["0.998-1"] = 2                                                   # 한 팔만 s1 대신 s2
    with pytest.raises(SystemExit, match="학습 시드 묶음"):
        dg.gamma_select(ds, reps=50)


def _etrain(gamma, run, g, **kw):
    """PREREG Etrain 조건(학습 γ, 5000스텝, 앞 제외 0, 끝 ceil(5/(1−γ)))의 합성 결과."""
    cond = {"gamma": gamma, "tail": ro.tail_steps(gamma), "eval_steps": 5000, "head": 0}
    cond.update(kw.pop("cond", {}))
    return _fake(gamma, run, g, cond=cond, **kw)


def test_train_gamma_table_accepts_only_etrain():
    rng = np.random.default_rng(0)
    ok = [_etrain(g, r, 3 + rng.standard_normal(20)) for g in (0.9916661555611042, 0.995, 0.998) for r in (0, 1)]
    rows = dg.train_gamma_table(ok)
    assert [r["tail"] for r in rows] == [600, 1000, 2500]
    for bad in ({"head": 500}, {"eval_steps": 10000}, {"tail": 600}, {"gamma": 0.995}, {"act_mode": "stochastic"},
                {"config_version": "2.0b"}):
        with pytest.raises(SystemExit):
            dg.train_gamma_table(ok[:5] + [_etrain(0.998, 1, np.zeros(20), cond=bad)])


def test_mode_compare_etrain_with_per_arm_gamma():
    """Etrain 은 팔마다 G 의 γ·꼬리가 학습 γ 라 다르다. 그래도 비교되어야 하고(PREREG 6절 modecmp_etrain),
    E998 결과와 섞이거나 짝끼리 조건이 다르면 거부한다."""
    rng = np.random.default_rng(2)
    det, sto = [], []
    for g in (0.9916661555611042, 0.995, 0.998):
        for run in (0, 1):
            base = 3 + rng.standard_normal(20)
            det.append(_etrain(g, run, base))
            sto.append(_etrain(g, run, base + 0.01 * rng.standard_normal(20), act_mode="stochastic"))
    r = dg.mode_compare(det, sto, reps=200)
    assert r["condition"]["gamma"] is None and r["condition"]["tail"] is None
    assert [(gr["g_eval_gamma"], gr["tail"]) for gr in r["groups"]] == [
        (0.9916661555611042, 600), (0.995, 1000), (0.998, 2500)]
    md = "\n".join(dg.md_modecmp(dg.clean(r)))
    assert "팔마다 그 팔의 학습 γ" in md and "끝 1000스텝" in md
    # E998 모양(모두 0.998)은 예전처럼 조건 하나로 적는다
    e998 = dg.mode_compare([_fake(0.995, 0, np.ones(20)), _fake(0.995, 1, np.ones(20))],
                           [_fake(0.995, 0, np.ones(20), act_mode="stochastic"),
                            _fake(0.995, 1, np.ones(20), act_mode="stochastic")], reps=50)
    assert e998["condition"]["gamma"] == 0.998 and e998["condition"]["tail"] == 2500
    # 한 팔만 학습 γ 가 아닌 γ 로 잰 결과(E998 과 Etrain 을 섞음)
    mixed = det[:2] + [_etrain(0.995, r, np.ones(20), cond={"gamma": 0.998, "tail": 2500}) for r in (0, 1)]
    mixed_s = sto[:2] + [_etrain(0.995, r, np.ones(20), act_mode="stochastic",
                                 cond={"gamma": 0.998, "tail": 2500}) for r in (0, 1)]
    with pytest.raises(SystemExit, match="섞지 않는다"):
        dg.mode_compare(mixed, mixed_s, reps=50)
    # 같은 모델의 두 모드가 다른 꼬리로 잰 결과
    with pytest.raises(SystemExit):
        dg.mode_compare(det, sto[:-1] + [_etrain(0.998, 1, np.ones(20), act_mode="stochastic",
                                                 cond={"tail": 3000})], reps=50)


def test_modecmp_command_on_etrain_dirs(tmp_path):
    """PREREG 6절의 modecmp_etrain 명령 모양 그대로(팔마다 γ 가 다른 디렉터리) 보고서가 나온다."""
    rng = np.random.default_rng(4)
    det, sto = [], []
    for g in (0.9916661555611042, 0.998):
        for run in (0, 1):
            base = 3 + rng.standard_normal(20)
            for mode, lst in (("deterministic", det), ("stochastic", sto)):
                d = _etrain(g, run, base, act_mode=mode)
                p = tmp_path / f"{g}_{run}_{mode}"
                d.pop("_dir")
                dg.save_json(p / "ablate.json", d)
                lst.append(str(p))
    out = tmp_path / "g07"
    assert dg.main(["modecmp", "--out", str(out), "--tag", "modecmp_etrain", "--det", *det, "--stoch", *sto,
                    "--reps", "100"]) == 0
    assert "#29 신호" in (out / "modecmp_etrain.md").read_text(encoding="utf-8")


def test_bootstrap_diff_t_pvalue_holm_by_hand():
    A = np.tile(np.arange(5.0), (2, 1))
    ci = dg.stratified_bootstrap_diff(A + 0.5, A, reps=200)
    assert ci["point"] == pytest.approx(0.5) and ci["lo"] == pytest.approx(0.5) and ci["hi"] == pytest.approx(0.5)
    ci = dg.stratified_bootstrap_diff(np.array([[0.0] * 5, [2.0] * 5]), np.ones((2, 5)), reps=500)
    assert ci["lo"] < 0 < ci["hi"] and ci["point"] == pytest.approx(0.0)
    assert dg.t_pvalue(2.093024054408263, 19) == pytest.approx(0.05, abs=1e-9)
    assert dg.t_pvalue(0.0, 19) == pytest.approx(1.0)
    assert dg.t_pvalue(-2.093024054408263, 19) == pytest.approx(0.05, abs=1e-9)
    assert math.isnan(dg.t_pvalue(float("nan"), 19))
    np.testing.assert_allclose(dg.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])
    out = dg.holm([0.02, float("nan")])
    assert out[0] == pytest.approx(0.02) and math.isnan(out[1])


def test_t_pvalue_matches_scipy():
    st = pytest.importorskip("scipy.stats")
    for df in (1, 2, 5, 19, 39):
        for t in (0.1, 0.7, 1.5, 2.093, 3.0, 6.0, 15.0):
            assert dg.t_pvalue(t, df) == pytest.approx(2 * st.t.sf(t, df), rel=1e-9, abs=1e-15)


def test_mode_compare_pairs_by_model_and_flags_trigger():
    rng = np.random.default_rng(1)
    det, sto = [], []
    for g in (0.995, 0.998):
        for run in (0, 1):
            base = 10 + rng.standard_normal(20)
            det.append(_fake(g, run, base))
            # 0.998 은 G 가 1 오른다(작은 잡음, t 가 정의되게). 0.995 는 두 모드가 똑같다
            shift = 1.0 + 0.01 * rng.standard_normal(20) if g == 0.998 else 0.0
            sto.append(_fake(g, run, base + shift, act_mode="stochastic", sha=f"{g}-{run}"))
    r = dg.mode_compare(det, sto[::-1], reps=500)              # 순서가 달라도 model_sha1 로 짝짓는다
    by = {gr["gamma"]: gr for gr in r["groups"]}
    assert by[0.998]["cols"]["g_gamma"]["diff"] == pytest.approx(1.0, abs=0.01)
    assert by[0.998]["cols"]["g_gamma"]["verdict"] and by[0.998]["trigger"]
    assert by[0.998]["cols"]["survival"]["verdict"]           # 합성 수명 = 400 + G 라 함께 움직인다
    assert not by[0.995]["cols"]["g_gamma"]["verdict"]
    assert "p_holm" in by[0.995]["cols"]["starve_rate"] and "verdict" not in by[0.995]["cols"]["repro"]
    one = dg.mode_compare(det[:1], sto[:1], reps=50)
    assert one["groups"][0]["trigger"] is None                # 학습 시드 하나로는 판정하지 않는다
    with pytest.raises(SystemExit):
        dg.mode_compare(det, sto[:-1], reps=50)               # 짝이 없는 결정 모드 결과
    with pytest.raises(SystemExit):
        dg.mode_compare(det, det, reps=50)                    # --stoch 에 결정 모드


def test_gammasel_and_modecmp_commands_write_reports(tmp_path):
    ds = _arms({0.9916661555611042: 10.0, 0.995: 10.5, 0.998: 12.0})
    dirs = []
    for d in ds:
        d = dict(d)
        d["per_seed"] = {**d["per_seed"], "C1": d["per_seed"]["C0"]}
        p = tmp_path / d.pop("_dir").replace("/", "_")
        dg.save_json(p / "ablate.json", d)
        dirs.append(str(p))
    out = tmp_path / "sel"
    assert dg.main(["gammasel", "--dirs", *dirs, "--out", str(out), "--reps", "200"]) == 0
    res = json.loads((out / "gammasel.json").read_text(encoding="utf-8"))
    assert res["selected"] == 0.998
    md = (out / "gammasel.md").read_text(encoding="utf-8")
    assert "**선택**" in md and "C0 − C1" in md
    sto = []
    for p in dirs:
        d = json.loads((tmp_path / p / "ablate.json").read_text(encoding="utf-8"))
        d["meta"]["act_mode"] = "stochastic"
        q = tmp_path / (p + "_stoch")
        dg.save_json(q / "ablate.json", d)
        sto.append(str(q))
    out = tmp_path / "mode"
    assert dg.main(["modecmp", "--det", *dirs, "--stoch", *sto, "--out", str(out), "--reps", "100"]) == 0
    assert "#29 신호" in (out / "modecmp.md").read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        dg.main(["gammasel", "--dirs", *dirs])                     # 출력 위치가 없다
