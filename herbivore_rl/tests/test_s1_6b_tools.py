"""1-6b 도구 — 학습 실패 대응 비교(results/v2/s1_6b/PREREG.md)에 쓰는 학습 옵션·집계 일반화·비교 집계.

- train_v2 `--ent-coef`·`--init-bias`: 학습 설정만 바뀌고(세계 설정·config_digest 그대로) 메타 JSON 에 값과 출처가
  남는다. 옵션이 없으면 기존과 같다. 팔 정의(_stage1_6b_compare.ARMS)가 실제 학습 메타와 맞는다.
- `_stage1_6_v2_2.py --prefix·--sdir·--seeds`: 실행 이름·폴더만 바뀐다(기본값 = 1-6 이름).
- `_stage1_6b_compare.py`: 부트스트랩 차, 선택 규칙(사전 등록 순서), 학습 기록 요약, precheck·checktrain, 합성 결과로
  compare 전 과정.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from env.config import ROOT
from env_v2.config import load_v2_config

sys.path.insert(0, str(ROOT / "results" / "v2"))

import _stage1_6_v2_2 as J  # noqa: E402
import _stage1_6b_compare as C  # noqa: E402

V2_1 = ROOT / "configs" / "v2_1.yaml"
V2_2 = ROOT / "configs" / "v2_2.yaml"
NAMES6 = ("forage", "cohesion", "flee_dist", "cover", "speed", "vigilance")
ACT_VIG = 5
TINY = {"version": "2.2", "overrides": {"rand": {"pred_speed_mult": [0.6, 0.95]}},
        "train": {"num_worlds": 1, "reset_interval": 4000, "rollout_world_steps": 8,
                  "init_action_bias": {"vigilance": -0.84}}}

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _tuned():
    return yaml.safe_load((ROOT / "configs" / "ppo_best.yaml").read_text(encoding="utf-8"))["params"]


# --------------------------------------------------------------------- #
# 1) train_v2 --ent-coef · --init-bias
# --------------------------------------------------------------------- #


def test_world_config_digest_is_unchanged():
    """세계 설정은 바꾸지 않는다: configs/v2_2.yaml 의 config_digest 는 Gate E2 V0_d0_95 그대로다."""
    from diagnose_v2 import config_digest

    assert config_digest(load_v2_config(V2_2)) == J.DIGEST == "efc8f775f1e1"


def test_parse_init_bias_format():
    from train_v2 import parse_init_bias

    assert parse_init_bias(None) == {} and parse_init_bias([]) == {}
    assert parse_init_bias(["vigilance=0"]) == {"vigilance": 0.0}
    assert parse_init_bias(["speed=-0.5", "vigilance=1e-1"]) == {"speed": -0.5, "vigilance": 0.1}
    for bad in (["vigilance"], ["=1"], ["vigilance="], ["vigilance=x"], ["vigilance=nan"], ["vigilance=inf"],
                ["vigilance=0", "vigilance=1"]):
        with pytest.raises(SystemExit):
            parse_init_bias(bad)


def test_resolve_init_bias_merges_cli_over_config():
    from train_v2 import resolve_init_bias

    cfg2 = load_v2_config(V2_2)
    assert resolve_init_bias(cfg2, NAMES6, {}) == ({"vigilance": -0.84}, {"vigilance": "config"})   # 기존과 같다
    assert resolve_init_bias(cfg2, NAMES6, None) == ({"vigilance": -0.84}, {"vigilance": "config"})
    assert resolve_init_bias(cfg2, NAMES6, {"vigilance": 0.0}) == ({"vigilance": 0.0}, {"vigilance": "cli"})
    assert resolve_init_bias(cfg2, NAMES6, {"speed": 0.3}) == ({"vigilance": -0.84, "speed": 0.3},
                                                               {"vigilance": "config", "speed": "cli"})
    assert resolve_init_bias(load_v2_config(V2_1), NAMES6[:5], {}) == ({}, {})
    with pytest.raises(SystemExit):
        resolve_init_bias(cfg2, NAMES6, {"vigilence": 0.0})                    # 오타
    with pytest.raises(SystemExit):
        resolve_init_bias(load_v2_config(V2_1), NAMES6[:5], {"vigilance": 0.0})  # vigilance 가 없는 세계


def test_resolve_ent_coef_sources():
    from train import PPO_KWARGS
    from train_v2 import resolve_ent_coef

    tuned = {"ent_coef": 0.0008971496690499397, "gamma": 0.99}
    t, e, src = resolve_ent_coef(tuned, None)
    assert (e, src) == (0.0008971496690499397, "ppo_config") and t == tuned
    t, e, src = resolve_ent_coef(tuned, 3e-3)
    assert (e, src) == (0.003, "cli") and t == {"ent_coef": 0.003, "gamma": 0.99}
    assert tuned["ent_coef"] == 0.0008971496690499397                       # 원본은 그대로
    assert resolve_ent_coef({}, None)[1:] == (PPO_KWARGS["ent_coef"], "PPO_KWARGS")
    assert resolve_ent_coef(tuned, 0.0)[1:] == (0.0, "cli")
    for bad in (-1e-3, float("nan"), float("inf")):
        with pytest.raises(SystemExit):
            resolve_ent_coef(tuned, bad)


def test_train_options_need_run_name_and_exclude_init(tmp_path):
    """기본 이름의 체크포인트를 덮지 않게 --run-name/--out 이 필요하고, --init-bias 는 --init 과 못 쓴다(학습 전에 멈춤)."""
    import train_v2

    with pytest.raises(SystemExit):
        train_v2.main(["--steps", "1", "--ent-coef", "3e-3"])
    with pytest.raises(SystemExit):
        train_v2.main(["--steps", "1", "--init-bias", "vigilance=0"])
    with pytest.raises(SystemExit):
        train_v2.main(["--steps", "1", "--init-bias", "vigilance=0", "--run-name", "x",
                       "--init", str(tmp_path / "donor.zip")])
    assert not list((ROOT / "ckpt" / "v2").glob("x.*"))


@pytest.fixture(scope="module")
def tiny_runs(tmp_path_factory):
    """v2_2.yaml 의 기능 블록 그대로, 세계 1개 × 롤아웃 8스텝 1회 학습: 옵션 없음 / 팔 A / 팔 B."""
    import train_v2

    d = tmp_path_factory.mktemp("s16b_train")
    raw = yaml.safe_load(V2_2.read_text(encoding="utf-8"))
    cfg_path = d / "tiny_v2_2.yaml"
    cfg_path.write_text(yaml.safe_dump(dict(TINY, features=raw["features"]), allow_unicode=True), encoding="utf-8")
    runs = {}
    for key, extra in (("default", []), ("a", C.ARMS["a"]["train_args"]), ("b", C.ARMS["b"]["train_args"])):
        out = d / f"{key}.zip"
        assert train_v2.main(["--steps", "1", "--seed", "0", "--config", str(cfg_path), "--out", str(out),
                              "--tb", str(d / "tb"), "--threads", "1", *extra]) == 0
        runs[key] = (out, json.loads(out.with_suffix(".json").read_text(encoding="utf-8")))
    return cfg_path, runs


def test_train_without_options_is_unchanged(tiny_runs):
    from diagnose_v2 import config_digest

    cfg_path, runs = tiny_runs
    out, m = runs["default"]
    tuned = _tuned()
    assert m["ent_coef"] == pytest.approx(float(tuned["ent_coef"]), abs=0) and m["ent_coef_source"] == "ppo_config"
    assert m["ppo"]["ent_coef"] == m["ent_coef"]
    assert m["init_action_bias"] == {"vigilance": -0.84} and m["init_action_bias_source"] == {"vigilance": "config"}
    assert m["init_policy"]["vigilance"]["vig_prob"] == pytest.approx(0.2005, abs=0.01)
    assert m["config_digest"] == config_digest(load_v2_config(cfg_path))
    assert "--ent-coef" not in m["command"] and "--init-bias" not in m["command"]


@pytest.mark.parametrize("arm", ["a", "b"])
def test_train_arm_options_are_recorded_and_match_arm_definition(tiny_runs, arm):
    """팔 A(--ent-coef 3e-3)·B(--init-bias vigilance=0)의 학습 메타가 비교 집계의 팔 정의(ARMS)와 같고, 다른 튜닝값·
    설정 지문은 옵션 없는 학습과 같다. 모델 zip 의 ent_coef 도 같은 값이다."""
    from stable_baselines3 import PPO

    _, runs = tiny_runs
    out, m = runs[arm]
    base = runs["default"][1]
    A = C.ARMS[arm]
    for k in ("ent_coef", "ent_coef_source", "init_action_bias", "init_action_bias_source"):
        assert m[k] == A[k], k
    assert PPO.load(out, device="cpu").ent_coef == A["ent_coef"]
    for k in ("learning_rate", "clip_range", "n_epochs", "gamma", "gae_lambda"):
        assert m["ppo"][k] == base["ppo"][k], k
    assert m["config_digest"] == base["config_digest"] and m["v2"] == base["v2"]
    ip = m["init_policy"]
    assert ip["action_bias"][ACT_VIG] == pytest.approx(A["init_action_bias"]["vigilance"], abs=1e-6)
    assert ip["log_std"][ACT_VIG] == 0.0 and ip["action_bias"][4] == 0.0
    want = 0.5 * math.erfc(-A["init_action_bias"]["vigilance"] / math.sqrt(2.0))      # P(N(b, 1) > 0)
    assert ip["vigilance"]["vig_prob"] == pytest.approx(want, abs=0.01)
    assert " ".join(A["train_args"]) in m["command"]


# --------------------------------------------------------------------- #
# 2) _stage1_6_v2_2.py --prefix · --sdir · --seeds
# --------------------------------------------------------------------- #


def test_judge_names_default_to_1_6_and_follow_prefix(tmp_path):
    a = argparse.Namespace(prefix="v2_2", sdir="s1_6", res=str(tmp_path))
    assert J.run_of(a, 3) == "v2_2_s3" and J.sdir_of(a) == tmp_path / "s1_6"
    b = argparse.Namespace(prefix="v2_2b", sdir="s1_6b", res=str(tmp_path))
    assert J.run_of(b, 7) == "v2_2b_s7" and J.sdir_of(b) == tmp_path / "s1_6b"
    with pytest.raises(SystemExit) as e:
        J.main(["judge", "--prefix", "v2_2x", "--sdir", "s1_6b", "--seeds", "5", "6", "--res", str(tmp_path)])
    assert "diag_v2_2x_s5" in str(e.value)
    with pytest.raises(SystemExit) as e:
        J.main(["b67", "--prefix", "v2_2x", "--sdir", "s1_6b", "--seed", "5", "--ckpt", str(tmp_path)])
    assert "v2_2x_s5.zip" in str(e.value)
    for bad in (["judge", "--prefix", "../x"], ["judge", "--sdir", "a/b"], ["judge", "--seeds", "1", "1"]):
        with pytest.raises(SystemExit):
            J.main(bad + ["--res", str(tmp_path)])


# --------------------------------------------------------------------- #
# 3) _stage1_6b_compare.py
# --------------------------------------------------------------------- #


def test_arms_follow_configs():
    assert C.ARMS["a"]["init_action_bias"] == load_v2_config(V2_2).v2["train"]["init_action_bias"]
    assert C.ARMS["b"]["ent_coef"] == float(_tuned()["ent_coef"]) == C.TUNED_ENT_COEF
    assert C.ARMS["a"]["ent_coef"] == float("3e-3")
    assert set(C.COMPARE_SEEDS).isdisjoint(C.JUDGE_SEEDS) and set(J.SEEDS).isdisjoint(C.JUDGE_SEEDS)


def test_boot_diff_stat_matches_mean_version_and_is_antisymmetric():
    from diagnose_v2 import iqm, stratified_bootstrap_diff

    rng = np.random.default_rng(3)
    A, B = rng.normal(1.0, 0.5, (3, 20)), rng.normal(0.8, 0.5, (3, 20))
    m1, m2 = C.boot_diff_stat(A, B, stat=np.mean), stratified_bootstrap_diff(A, B)
    for k in ("point", "lo", "hi"):
        assert m1[k] == pytest.approx(m2[k], abs=1e-12)
    d1 = C.boot_diff_stat(A, B)
    assert d1["point"] == pytest.approx(iqm(A) - iqm(B), abs=1e-12) and d1["lo"] < d1["point"] < d1["hi"]
    assert d1 == C.boot_diff_stat(A, B) and d1["runs"] == [3, 3] and d1["strata"] == 20     # 난수 시드 고정
    same = C.boot_diff_stat(A, A)                    # 같은 행렬이어도 팔마다 따로 뽑아 폭이 있고 0 을 포함한다
    assert same["point"] == 0.0 and same["lo"] < 0 < same["hi"]
    with pytest.raises(ValueError):
        C.boot_diff_stat(A, B[:, :10])


def _s(lf=False, col=False, b1=0, b3=0, b2=0):
    return {"learning_failure": lf, "collapse": col, "n_pass": {"B1": b1, "B2": b2, "B3": b3}}


@pytest.mark.parametrize("summ, g, want, by", [
    ({"a": _s(lf=True), "b": _s(lf=True)}, (1.0, 2.0), None, None),               # 둘 다 학습 실패 → 멈춤
    ({"a": _s(col=True), "b": _s(col=True)}, (1.0, 2.0), None, None),             # 둘 다 붕괴 → 멈춤
    ({"a": _s(lf=True), "b": _s(col=True)}, (1.0, 2.0), None, None),              # 실패 + 붕괴 → 멈춤
    ({"a": _s(lf=True), "b": _s()}, (1.0, 2.0), "b", None),                       # 하나만 남음
    ({"a": _s(), "b": _s(col=True, b1=3, b3=3)}, (-2.0, -1.0), "a", None),       # 붕괴 팔은 G 가 높아도 빠짐
    ({"a": _s(b1=0), "b": _s(b1=3)}, (0.1, 0.5), "a", "g_gamma_iqm"),             # CI 가 0 을 빼면 G_γ 가 우선
    ({"a": _s(b1=3), "b": _s()}, (-0.5, -0.1), "b", "g_gamma_iqm"),
    ({"a": _s(b1=1, b3=0), "b": _s(b1=1, b3=2)}, (-0.2, 0.3), "b", "b1_b3_pass_count"),
    ({"a": _s(b1=2, b3=1, b2=0), "b": _s(b1=1, b3=1, b2=3)}, (-0.2, 0.3), "a", "b1_b3_pass_count"),  # B2 는 안 셈
    ({"a": _s(b1=1, b3=1), "b": _s(b1=2, b3=0)}, (-0.2, 0.3), "a", "tie"),         # 같으면 팔 A
])
def test_select_arm_follows_prereg_order(summ, g, want, by):
    sel = C.select_arm(summ, {"point": sum(g) / 2, "lo": g[0], "hi": g[1]})
    assert sel["arm"] == want and sel["decided_by"] == by and sel["stop"] == (want is None)
    if want:
        assert sel["prefix"] == C.ARMS[want]["prefix"] and sel["judge_seeds"] == [5, 6, 7, 8, 9]
        assert sel["train_args"] == C.ARMS[want]["train_args"]


def _vig_series(points):
    return {"vig/frac": points, "act/speed_std": [(st, 0.3 - 1e-8 * st) for st, _ in points]}


def test_tb_summary_reads_first_rollout_at_or_after_5m():
    steps = [32768 * k for k in range(1, 612)]
    vig = [(st, 0.2 if st < 1_000_000 else (0.03 if st < 4_000_000 else 0.009)) for st in steps]
    t = C.tb_summary(_vig_series(vig), C.COLLAPSE_STEP)
    assert t["vig_frac_5m_step"] == 5_013_504 and t["vig_frac_5m"] == 0.009
    assert t["first_below_5pct"] == 1_015_808 and t["first_below_1pct"] == 4_030_464
    assert t["vig_frac"]["1M"] == 0.03 and t["last_step"] == steps[-1]
    assert t["speed_std"]["init"] == pytest.approx(0.3 - 1e-8 * 32768) and not t["speed_std_below_10pct"]
    with pytest.raises(SystemExit):
        C.tb_summary(_vig_series(vig[:100]), C.COLLAPSE_STEP)                  # 5M 에 못 미친 기록
    with pytest.raises(SystemExit):
        C.tb_summary({"act/speed_std": [(1, 1.0)]}, C.COLLAPSE_STEP)


def test_tb_dir_takes_exactly_one_run_directory(tmp_path):
    (tmp_path / "v2_2a_s1_1").mkdir()
    (tmp_path / "v2_2a_s10_1").mkdir()
    (tmp_path / "v2_2a_s1_x").mkdir()
    assert C.tb_dir(tmp_path, "v2_2a_s1").name == "v2_2a_s1_1"
    (tmp_path / "v2_2a_s1_2").mkdir()
    with pytest.raises(SystemExit):
        C.tb_dir(tmp_path, "v2_2a_s1")
    with pytest.raises(SystemExit):
        C.tb_dir(tmp_path, "v2_2b_s0")


def _dirs(tmp_path):
    d = {k: tmp_path / k for k in ("res", "ckpt", "tb", "cache")}
    for p in d.values():
        p.mkdir(exist_ok=True)
    return d, sum((["--" + k, str(p)] for k, p in d.items()), [])


def test_precheck_seed_sets_selection_and_existing_outputs(tmp_path):
    d, paths = _dirs(tmp_path)
    assert C.main(["precheck", "--arms", "a", "b", "--seeds", "0", "1", "2", *paths]) == 0
    with pytest.raises(SystemExit):
        C.main(["precheck", "--arms", "a", "--seeds", "0", "1", "2", *paths])          # 비교는 두 팔 모두
    with pytest.raises(SystemExit):
        C.main(["precheck", "--arms", "a", "b", "--seeds", "3", "4", *paths])          # 사전 등록 밖 시드
    with pytest.raises(SystemExit):
        C.main(["precheck", "--arms", "b", "--seeds", "5", "6", "7", "8", "9", *paths])  # compare.json 전
    (d["res"] / "s1_6b").mkdir()
    (d["res"] / "s1_6b" / "compare.json").write_text(json.dumps({"selection": {"arm": "b"}}), encoding="utf-8")
    with pytest.raises(SystemExit):
        C.main(["precheck", "--arms", "a", "--seeds", "5", "6", "7", "8", "9", *paths])  # 고르지 않은 팔
    assert C.main(["precheck", "--arms", "b", "--seeds", "5", "6", "7", "8", "9", *paths]) == 0
    for p in (d["ckpt"] / "v2_2b_s7.json", d["tb"] / "v2_2b_s9_1", d["res"] / "diag_v2_2b",
              d["cache"] / "v2_2b_s5_stoch"):
        p.mkdir() if not p.suffix else p.write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit):
            C.main(["precheck", "--arms", "b", "--seeds", "5", "6", "7", "8", "9", *paths])
        (p.rmdir() if p.is_dir() else p.unlink())
    (d["res"] / "s1_6b" / "compare.json").write_text(json.dumps({"selection": {"arm": None}}), encoding="utf-8")
    with pytest.raises(SystemExit):
        C.main(["precheck", "--arms", "b", "--seeds", "5", "6", "7", "8", "9", *paths])  # 후보 없음 → 멈춤


def _train_meta(arm, seed):
    A, t = C.ARMS[arm], _tuned()
    return {"seed": seed, "init": None, "steps": C.TRAIN_STEPS, "actual_timesteps": 20_021_248,
            "gamma": J.GAMMA, "gamma_source": "cli", "ent_coef": A["ent_coef"], "ent_coef_source": A["ent_coef_source"],
            "init_action_bias": A["init_action_bias"], "init_action_bias_source": A["init_action_bias_source"],
            "config_digest": J.DIGEST, "v2": {"version": "2.2"},
            "ppo": {"learning_rate": float(t["learning_rate"]), "clip_range": float(t["clip_range"]),
                    "n_epochs": float(t["n_epochs"]), "ent_coef": A["ent_coef"]},
            "init_policy": {"vigilance": {"vig_prob": 0.2, "mu_mean": -0.84}, "speed": {"gait_prob": {"walk": 0.51}}}}


def test_checktrain_compares_meta_with_arm_definition(tmp_path, capsys):
    ck = tmp_path / "ckpt"
    ck.mkdir()
    for arm in C.ARMS:
        for s in (0, 1, 2):
            run = C.run_name(arm, s)
            (ck / f"{run}.json").write_text(json.dumps(_train_meta(arm, s)), encoding="utf-8")
            (ck / f"{run}.zip").write_bytes(b"")
            (ck / f"{run}_10m.zip").write_bytes(b"")
    assert C.main(["checktrain", "--ckpt", str(ck)]) == 0
    for k, v in (("ent_coef", 3e-3), ("init_action_bias", {"vigilance": -0.84}), ("config_digest", "x"),
                 ("steps", 1_000_000), ("gamma", 0.998), ("init", "donor.zip")):
        m = _train_meta("b", 1)
        m[k] = v
        (ck / "v2_2b_s1.json").write_text(json.dumps(m), encoding="utf-8")
        with pytest.raises(SystemExit):
            C.main(["checktrain", "--ckpt", str(ck)])
    (ck / "v2_2b_s1.json").write_text(json.dumps(_train_meta("b", 1)), encoding="utf-8")
    (ck / "v2_2a_s2_10m.zip").unlink()
    with pytest.raises(SystemExit):
        C.main(["checktrain", "--ckpt", str(ck)])
    assert C.main(["checktrain", "--ckpt", str(ck), "--arms", "b"]) == 0
    capsys.readouterr()
    assert C.main(["armargs", "--arm", "b"]) == 0 and capsys.readouterr().out.strip() == "--init-bias vigilance=0"


# ---- 합성 진단 결과로 compare 전 과정 ----

EVAL = [10000, 10001, 10002, 10003, 10004, 10005]


def _rows(rng, g, **cols):
    out = []
    for i, s in enumerate(EVAL):
        r = {"seed": s, "g_gamma": float(g + rng.normal(0, 0.05)), "starve_rate": 0.0005, "predation_rate": 0.001,
             "survival": 500.0, "repro": 10.0}
        r.update({k: (v[i] if isinstance(v, list) else v) for k, v in cols.items()})
        out.append(r)
    return out


def _write_arm(res, arm, spec, rng):
    """spec[s] = dict(g, seg, b1, b3, vig, vig5) — 학습 시드마다 결정 모드 C0·C2-seg 값과 학습 기록의 5M vig/frac."""
    tb = {}
    for s, x in spec.items():
        run = C.run_name(arm, s)
        meta = {"config_digest": J.DIGEST, "eval_seeds": EVAL, "eval_steps": 5000, "tail": 600, "gamma": J.GAMMA,
                "head": 0, "model_sha1": f"sha-{run}"}
        c0 = _rows(np.random.default_rng(1000 + s), x["g"], b1=x["b1"], b2=0.2, b3_truth=x["b3"], vig_frac=x["vig"])
        seg = _rows(np.random.default_rng(99), x["seg"], b1=0.0, b2=0.0, b3_truth=0.7, vig_frac=0.16)
        c2 = _rows(np.random.default_rng(98), 1.48, b1=0.0, b2=0.0, b3_truth=0.0, vig_frac=0.0)
        dd = res / f"diag_{run}"
        dd.mkdir(parents=True)
        (dd / "ablate.json").write_text(json.dumps({"meta": meta, "per_seed": {"C0": c0}}), encoding="utf-8")
        (dd / "c2seg_e2.json").write_text(json.dumps({
            "meta": meta, "best": J.E2_SEG["table"], "bins": J.E2_SEG["bins"], "dims": J.E2_SEG["dims"],
            "base_action": J.E2_C2, "per_seed": {"C2-seg": seg, "C0": c0, "C2": c2}}), encoding="utf-8")
        st = res / f"diag_{run}_stoch"
        st.mkdir()
        (st / "ablate.json").write_text(json.dumps({"meta": dict(meta, act_mode="stochastic"), "per_seed": {
            "C0": _rows(rng, x["g"] + 0.5, b1=0.4, b2=0.1, b3_truth=0.1, vig_frac=0.05)}}), encoding="utf-8")
        steps = [32768 * k for k in range(1, 200)]
        tb[f"{run}_1"] = {"vig/frac": [(st_, 0.2 if st_ < 2_000_000 else x["vig5"]) for st_ in steps]}
    return tb


def _compare(tmp_path, monkeypatch, spec_a, spec_b):
    d, paths = _dirs(tmp_path)
    rng = np.random.default_rng(0)
    tb = {**_write_arm(d["res"], "a", spec_a, rng), **_write_arm(d["res"], "b", spec_b, rng)}
    monkeypatch.setattr(C, "tb_dir", lambda root, run: Path(root) / f"{run}_1")
    monkeypatch.setattr(C, "tb_scalars", lambda p: tb[Path(p).name])
    assert C.main(["compare", "--smoke", *paths]) == 0
    out = json.loads((d["res"] / "s1_6b" / "compare.json").read_text(encoding="utf-8"))
    with pytest.raises(SystemExit):
        C.main(["compare", "--smoke", *paths])                                  # 덮지 않는다
    return d, paths, out


def _spec(g, seg=1.95, b1=0.35, b3=0.25, vig=0.05, vig5=0.03, seeds=(0, 1, 2)):
    return {s: dict(g=g, seg=seg, b1=b1, b3=b3, vig=vig, vig5=vig5) for s in seeds}


def test_compare_selects_the_arm_without_learning_failure(tmp_path, monkeypatch, capsys):
    d, paths, out = _compare(tmp_path, monkeypatch, _spec(2.0), _spec(0.5))
    A, B = out["arms"]["a"], out["arms"]["b"]
    assert not A["learning_failure"] and B["learning_failure"]
    assert B["learning_failure_delta"]["delta_seg_minus_c0"]["lo"] > 0
    assert not A["collapse"] and not B["collapse"]
    assert A["n_pass"] == {"B1": 3, "B2": 3, "B3": 3}
    assert A["per_seed"]["0"]["tb"]["vig_frac_5m"] == 0.03
    assert out["selection"]["arm"] == "a" and out["selection"]["candidates_after_1"] == ["a"]
    assert out["condition"]["n_eval_seeds"] == len(EVAL) and out["smoke"]
    capsys.readouterr()
    assert C.main(["selected", "--res", str(d["res"])]) == 0 and capsys.readouterr().out.strip() == "a"


def test_compare_collapse_signals_and_stop(tmp_path, monkeypatch, capsys):
    sa = _spec(2.0)
    sa[1]["vig"] = 0.0                     # 결정 모드 경계 0 → 붕괴 신호
    sb = _spec(2.0)
    sb[2]["vig5"] = 0.0099                 # 5M vig/frac < 1% → 붕괴 신호
    d, paths, out = _compare(tmp_path, monkeypatch, sa, sb)
    assert out["arms"]["a"]["collapse_seeds"] == [1] and out["arms"]["b"]["collapse_seeds"] == [2]
    assert out["arms"]["a"]["per_seed"]["1"]["collapse"] == {"vig_frac_5m_below_1pct": False,
                                                             "det_vig_frac_zero": True, "signal": True}
    assert out["selection"]["arm"] is None and out["selection"]["stop"]
    capsys.readouterr()
    assert C.main(["selected", "--res", str(d["res"])]) == 0 and capsys.readouterr().out.strip() == ""


def test_compare_ties_on_g_gamma_go_to_b1_b3_counts(tmp_path, monkeypatch):
    sb = _spec(2.0, b1=0.1)
    sb[0]["b1"] = 0.31
    d, paths, out = _compare(tmp_path, monkeypatch, _spec(2.0, b1=0.1, b3=0.1), sb)
    gd = out["g_gamma_iqm_diff_a_minus_b"]
    assert gd["lo"] <= 0 <= gd["hi"]
    assert out["selection"]["b1_b3_pass_count"] == {"a": 0, "b": 4}
    assert out["selection"]["arm"] == "b" and out["selection"]["decided_by"] == "b1_b3_pass_count"
