"""v3 R6 사전 등록 도구 시험 (results/v3/r6/PREREG.md — 학습 전).

- 학습 설정 갈래(make_r6_configs.py): 최신이고, 바탕 configs/v3_r6_train.yaml 에서 적은 칸만 다르다. λ 0.98 PPO 설정 = ppo_best + gae_lambda.
- 쓰임마다 시드·길이·세계(사전 등록 2절), 스모크는 R6 시드를 받지 않는다.
- 탐침(조기 점검 (a)·(b))은 세계·궤적·도망 기록을 바꾸지 않는다. route0 의 π′(SHELTER) = 0.95/(1+e²) + 0.025.
- (b) 의 λ-수익 목표(lambda_returns — SB3 GAE 와 같음), 조기 점검 고르기·멈춤(pick_combo·main_check_rules), 길 지킴(GT·GTr·GR), 고르기 순서,
  고르기·판정 막기(select_guard·picked_model), 띄우기 스크립트 명령(-DryRun).
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import importlib.util
import math
import shutil
import subprocess
import sys

import numpy as np
import pytest
import yaml

from env.config import ROOT

R6 = ROOT / "results" / "v3" / "r6"
for _p in (str(R6), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gen():
    return _module("make_r6_configs", R6 / "make_r6_configs.py")


@pytest.fixture(scope="module")
def E():
    import r6_eval

    return r6_eval


def _y(p):
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def test_configs_up_to_date_and_minimal(gen):
    """갈래 다섯 + PPO 하나가 생성기와 같고, 바탕에서 적은 칸만 다르다. 바탕(c109bf0)의 지문은 그대로."""
    from diagnose_v2 import config_digest
    from env_v2.config import load_v2_config

    assert gen.main(["--check"]) == 0
    base = _y(gen.BASE)
    assert config_digest(load_v2_config(gen.BASE)) == "8e60880fa2eb"            # c109bf0 의 R6 학습 세계 (train_smoke_r6.log)
    assert base["features"]["wild_flight"]["route"] is True and base["features"]["wild_flight"]["flight_cost"] == 0.0
    for route in (True, False):
        for cost, c in gen.COSTS.items():
            p = gen.config_path(route, cost)
            d = _y(p)
            want = copy.deepcopy(base)
            want["features"]["wild_flight"]["flight_cost"] = c
            if not route:
                want["version"] = "3.r6off"
                want["features"]["wild_flight"]["route"] = False
                want["train"]["repertoire"]["f_dec"] = gen.F_DEC_OFF
                want["train"]["repertoire"]["ent_coef_base"] = round(0.01 * gen.F_DEC_OFF, 8)
            assert d == want, p.name
            rp = d["train"]["repertoire"]
            assert math.isclose(rp["ent_coef_base"] / rp["f_dec"], 0.01, rel_tol=1e-6)       # 범주 엔트로피 계수 0.01 그대로
    assert gen.config_path(True, "0") == gen.BASE
    a, b = _y(gen.PPO_BEST), _y(gen.PPO_LAM98)
    assert b["params"].pop("gae_lambda") == 0.98 and a == b


def test_ppo_lambda_reaches_model(gen):
    """train.load_tuned 가 gae_lambda 를 읽고 train_v3.make_model_rep 이 PPO_KWARGS(0.95)를 덮는다."""
    from train import PPO_KWARGS, load_tuned

    assert PPO_KWARGS["gae_lambda"] == 0.95
    assert load_tuned(gen.PPO_LAM98)["gae_lambda"] == 0.98
    assert "gae_lambda" not in load_tuned(gen.PPO_BEST)


def test_world_obs_and_mask(gen):
    """길 켬 갈래 = 관측 24·마스크 판 4, 대조 = 관측 21·판 2. 도주 비용은 보상만 바꾼다(같은 행동이면 같은 궤적)."""
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import mask_version_of
    from env_v2.world import World

    on, off = load_v2_config(gen.config_path(True, "005")), load_v2_config(gen.config_path(False, "0027"))
    w_on, w_off = World(on, seeds=[32096]), World(off, seeds=[32096])
    assert (w_on.obs_dim, mask_version_of(w_on.obs_names)) == (24, 4)
    assert (w_off.obs_dim, mask_version_of(w_off.obs_names)) == (21, 2)
    w0 = World(load_v2_config(gen.BASE), seeds=[32096])
    rng = np.random.default_rng(3)
    for _ in range(40):
        a = rng.integers(0, 3, size=(w0.N, 1)).astype(np.float64)
        o0, r0, d0, _ = w0.step(a)
        o1, r1, d1, _ = w_on.step(a)
        assert np.array_equal(o0, o1) and np.array_equal(d0, d1) and np.array_equal(w0.pos, w_on.pos)
        assert np.all(r1 <= r0 + 1e-12)


def test_uses_and_seed_guard(E):
    """사전 등록 2절 시드 표 그대로. 쓰임 칸은 37000~37199 안이고 고르기·점검·판정이 겹치지 않는다. 스모크는 R6 시드를 받지 않는다."""
    assert E.USES == {"judge_n": (37000, 37099, 1800, "N"), "judge_g": (37000, 37039, 3600, "G"), "stuck": (37000, 37004, 3600, "stuck"),
                      "select": (37100, 37119, 1800, "N"), "check": (37120, 37139, 1800, "N")}
    p = E.use_plan("judge_n")
    assert (p["seeds"][0], p["seeds"][-1], len(p["seeds"]), p["steps"], p["world"]) == (37000, 37099, 100, 1800, "N")
    sel, chk, jn = (set(E.use_plan(u)["seeds"]) for u in ("select", "check", "judge_n"))
    assert not (sel & chk) and not (sel & jn) and not (chk & jn)
    assert all(37000 <= s <= 37199 for s in sel | chk | jn)
    with pytest.raises(SystemExit):
        E.use_plan("check", [37120], 1800)
    with pytest.raises(SystemExit):
        E.use_plan("smoke", [37000, 37001], 30)
    with pytest.raises(SystemExit):
        E.use_plan("smoke", [32000], 30)                     # 학습 풀 — 스모크 칸 밖
    assert E.smoke_plan("judge_g", [32080], 30)["world"] == "G"
    assert E.parse_seeds("32080-32082,32090") == [32080, 32081, 32082, 32090]


def test_probe_keeps_world(E, tmp_path):
    """탐침을 씌운 세계 = 씌우지 않은 세계 (요약·도망 기록 모두). route0 의 학습 표본 확률 π′(SHELTER) = 0.95/(1+e²) + 0.025, 배포는 늘 RUN."""
    info = E.prepare_info(tmp_path)
    plan = E.smoke_plan("judge_n", [32096], 200)
    spec = E.resolve_model("route0")
    a = E.run_items(E.make_items(info, spec, plan, probe=True, flight_cost=0.005), 1)
    b = E.run_items(E.make_items(info, spec, plan, probe=False), 1)
    for (ta, wa), (tb, wb) in zip(a, b):
        wa = dict(wa)
        pr = wa.pop("probe")
        wa.pop("wall_s")
        wb = dict(wb)
        wb.pop("wall_s")
        assert wa == wb
        assert pr["cover_max"] == 0.0 and pr["pick_sh"] == 0
    res = dict(meta=dict(obs=24), worlds=[w for _, w in a])
    q = E.probe_pooled(res)
    assert q["two_n"] > 0 and abs(q["pe_shelter"] - (0.95 / (1.0 + math.exp(2.0)) + 0.025)) < 1e-5
    assert abs(q["pi_shelter"] - 1.0 / (1.0 + math.exp(2.0))) < 1e-5
    assert q["ev_n"] > 0 and set(q["ev"]) == {"0.95", "0.98", "1"} and all(math.isfinite(v) for v in q["ev"].values())
    r = E.early_check(res, res, 0.98)                        # 같은 판끼리: (a) 안 움직임, (c) 차이 0, (b) 는 학습 λ 칸
    assert r["a"]["ok"] is False and r["c"]["parts"]["hide"]["diff"] == 0.0 and not r["defect"]["hit"]
    assert r["b"]["ev"] == q["ev"]["0.98"] and r["b"]["ev_mc"] == q["ev"]["1"] and r["b"]["lam"] == 0.98
    with pytest.raises(ValueError):
        E.early_check(res, res, 1.0)                         # (b) 의 λ 는 학습 λ 후보만


def test_lambda_returns(E):
    """(b) 의 수익 목표: λ 1 = 몬테카를로 할인 수익(끝은 V(s_T)), λ 0 = 한 스텝 TD 목표, 죽음 스텝에서 끊는다. SB3 GAE(이점 + V)와 같다."""
    rng = np.random.default_rng(1)
    T, N, g = 30, 4, 0.9
    R, V, v_end = rng.normal(size=(T, N)), rng.normal(size=(T, N)), rng.normal(size=N)
    D = np.zeros((T, N), dtype=bool)
    D[7, 1] = D[20, 2] = True
    Vn = np.concatenate([V[1:], v_end[None]], 0)
    mc = np.zeros((T, N))
    nxt = v_end.copy()
    for t in range(T - 1, -1, -1):
        mc[t] = R[t] + g * (~D[t]) * nxt
        nxt = mc[t]
    assert np.allclose(E.lambda_returns(R, D, V, v_end, g, 1.0), mc)
    assert np.allclose(E.lambda_returns(R, D, V, v_end, g, 0.0), R + g * (~D) * Vn)
    lam = 0.95                                                # SB3 RolloutBuffer.compute_returns_and_advantage 와 같은 GAE
    adv, last = np.zeros((T, N)), np.zeros(N)
    for t in range(T - 1, -1, -1):
        delta = R[t] + g * (~D[t]) * Vn[t] - V[t]
        last = delta + g * lam * (~D[t]) * last
        adv[t] = last
    assert np.allclose(E.lambda_returns(R, D, V, v_end, g, lam), adv + V)


def test_select_and_judge_guards(E, tmp_path):
    """사전 등록 6·7절: 고르기 후보는 R6 본 학습 마지막 모델만, 본 학습 점검이 제외한 시드는 막는다. 판정은 select.txt 의 고른 모델."""
    em = tmp_path / "early_main.json"
    em.write_text('{"rules": {"excluded": {"s1": "(c) 걸림: 2M (c)"}}}', encoding="utf-8")
    E.select_guard(["ckpt/v3/v3_r6_g995_s0_20m.zip", "ckpt/v3/v3_r6_g995_s2_20m.zip"], em)
    for bad in (["ckpt/v3/v3_r6_g995_s1_20m.zip"], ["ckpt/v3/v3_r6_g995_s0_20m_5m.zip"], ["ckpt/v3/v3_r6off_g995_s0_20m.zip"]):
        with pytest.raises(SystemExit):
            E.select_guard(bad, em)
    st = tmp_path / "select.txt"
    assert E.picked_model(st) is None
    st.write_text("| 모델 | … |\n\n고른 모델: ckpt/v3/v3_r6_g995_s2_20m.zip\n", encoding="utf-8")
    assert E.picked_model(st) == "ckpt/v3/v3_r6_g995_s2_20m.zip"


def _chk(a, b, c, hide_diff, defect=False):
    return dict(a=dict(ok=a), b=dict(ok=b), c=dict(ok=c, parts=dict(hide=dict(diff=hide_diff))), defect=dict(hit=defect),
                passed=bool(a and b and c and not defect))


def test_pick_combo(E):
    """사전 등록 5-2: 통과 조합 가운데 숨음 비율 짝 차이 최대, 그와 1 %p 안이면 작은 c → λ 0.95. 멈춤 까닭 셋."""
    K = [(l, c) for l in ("95", "98") for c in ("0", "0027", "005")]
    ch = {k: _chk(True, True, True, 0.01) for k in K}
    ch[("98", "005")] = _chk(True, True, True, 0.040)
    ch[("95", "0027")] = _chk(True, True, True, 0.031)          # 0.9 %p 안 — c 가 더 작다
    ch[("98", "0")] = _chk(True, True, True, 0.020)
    r = E.pick_combo(ch)
    assert not r["stop"] and r["pick"] == ("95", "0027")
    ch[("95", "0027")] = _chk(True, True, True, 0.029)          # 1.1 %p 밖
    ch[("98", "0027")] = _chk(True, True, True, 0.0305)         # 0.95 %p 안, λ 0.98 만
    assert E.pick_combo(ch)["pick"] == ("98", "0027")
    ch2 = {k: _chk(True, True, True, 0.02) for k in K}
    assert E.pick_combo(ch2)["pick"] == ("95", "0")               # 모두 같으면 c 0 · λ 0.95
    assert "못 배움" in E.pick_combo({k: _chk(False, True, True, 0.0) for k in K})["why"]
    only_b = {k: _chk(True, False, True, 0.0) for k in K}
    assert "관측 25" in E.pick_combo(only_b)["why"]
    mixed = {k: _chk(True, True, False, 0.0) for k in K}
    r = E.pick_combo(mixed)
    assert r["stop"] and "넘은 조합이 없다" in r["why"]
    bad = dict(ch2)
    bad[("95", "0")] = _chk(True, True, True, 0.02, defect=True)
    assert "결함" in E.pick_combo(bad)["why"]


def test_main_check_rules(E):
    """사전 등록 5-3: (c) 걸린 시드는 제외, 5M 에서 모두 (a) 못 움직임 → 멈춤, 남은 시드 모두 (b) 걸림 → 멈춤, 모든 시드 제외 → 멈춤."""
    ok = {(f"s{s}", k): _chk(True, True, True, 0.01) for s in range(3) for k in (2, 5)}
    r = E.main_check_rules(ok, [2, 5])
    assert not r["stop"] and not r["excluded"]
    c = dict(ok)
    c[("s1", 2)] = _chk(True, True, False, -0.03)
    r = E.main_check_rules(c, [2, 5])
    assert list(r["excluded"]) == ["s1"] and not r["stop"]
    na = {k: _chk(k[1] == 2, True, True, 0.0) for k in ok}
    assert E.main_check_rules(na, [2, 5])["stop"]
    nb = {k: _chk(True, k[1] == 2, True, 0.0) for k in ok}
    assert any("(b)" in w for w in E.main_check_rules(nb, [2, 5])["why"])
    allc = {k: _chk(True, True, False, 0.0) for k in ok}
    assert E.main_check_rules(allc, [2, 5])["stop"]


def _world(seed, region, flee, live, trunc, refled, route=True):
    n = {c: 0 for c in ("cover", "obstacle", "fov", "range", "switch", "stop", "held", "unchased", "caught", "starved", "truncated")}
    n["truncated"] = trunc
    f = dict(started=10, live_steps=live, flee_steps=flee, reflex_steps=flee, shelter_end=0, n=n, steps=dict(n), contact=dict(n))
    if route:
        f["route"] = dict(refled=refled)
    return dict(seed=seed, region=region, flight=f)


def test_route_guards(E):
    """GT = 60 × 실행 FLEE ÷ 산 사슴-스텝, GTr = 잘린 도망 수, GR = 5 초 안 다시 도망 수 — 시드마다 지역 합, 짝 t < +t_crit."""
    rng = np.random.default_rng(0)
    cand, cur = [], []
    for s in range(20):
        for r in ("Barren", "Forest"):
            f0, t0, g0 = int(rng.integers(900, 1100)), int(rng.integers(0, 4)), int(rng.integers(5, 15))
            cur.append(_world(s, r, f0, 10000, t0, g0))
            cand.append(_world(s, r, f0 + 30, 10000, t0, g0 + int(rng.integers(0, 2))))
    g = E.route_guards(dict(worlds=cand), dict(worlds=cur))
    assert not g["GT_flight_time"]["ok"] and g["GT_flight_time"]["diff"] == pytest.approx(60.0 * 60 / 20000)
    assert g["GTr_truncated"]["ok"] and g["GTr_truncated"]["diff"] == 0.0
    assert not g["GR_reflee"]["ok"] and g["GR_reflee"]["diff"] > 0
    off = [_world(w["seed"], w["region"], 1000, 10000, 0, 0, route=False) for w in cur]
    assert E.route_guards(dict(worlds=cand), dict(worlds=off))["GR_reflee"]["ok"] is False


def test_select_key_and_seed(E):
    """고르기 순서: 숨음 비율(전체 합) 큰 쪽 → 잡힌 몫 → 굶은 몫 → 모델 시드. 실행 이름의 모델 시드."""
    assert E.model_seed_of("v3_r6_g995_s2_20m") == 2 and E.model_seed_of("route0") == 0
    rows = [((-0.20, 0.10, 0.0, 1), "s1"), ((-0.20, 0.09, 0.0, 2), "s2"), ((-0.21, 0.2, 0.0, 0), "s0")]
    assert sorted(rows)[0][1] == "s0" and sorted(rows)[1][1] == "s2"


@pytest.mark.skipif(shutil.which("powershell") is None, reason="powershell 없음")
def test_launch_dry_run():
    """띄우기 스크립트 -DryRun: 조기 점검 6 조합·본 학습 3 + 대조 1 의 명령이 사전 등록 이름·설정·시작 두뇌를 쓴다."""
    ps = R6 / "launch_train.ps1"
    out = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps), "-Phase", "combos", "-Checks", "-DryRun"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT, timeout=120).stdout
    lines = [x for x in out.splitlines() if x.startswith("[DryRun] train")]
    assert len(lines) == 6 and all("--steps 5000000" in x and "obs24route0.zip" in x and "--seed 0 " in x for x in lines)
    assert sum("configs/ppo_r6_lam098.yaml" in x for x in lines) == 3
    assert "early_checks.py combos" in out
    out = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps), "-Phase", "main", "-Lam", "98", "-Cost", "005", "-Checks",
                          "-DryRun"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT, timeout=120).stdout
    lines = [x for x in out.splitlines() if x.startswith("[DryRun] train")]
    assert len(lines) == 4 and all("--steps 20000000" in x and "configs/ppo_r6_lam098.yaml" in x for x in lines)
    assert sum("configs/v3_r6_train_c005.yaml" in x for x in lines) == 3
    assert sum("configs/v3_r6off_train_c005.yaml" in x and "obs21zero.zip" in x for x in lines) == 1
    assert "early_checks.py main --seeds 0 1 2 --control --at 2 5 --cost 005 --lam 98" in out
