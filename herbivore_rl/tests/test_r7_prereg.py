"""v3 R7 사전 등록 도구 시험 (results/v3/r7/PREREG.md — 학습 전).

- 쓰임마다 시드·길이·세계(사전 등록 2절): R7 칸 38000~38199 안이고 서로·R6 칸(37000~37199)과 겹치지 않는다. 스모크는 R7·R6 시드를 받지 않는다.
- 두뇌 → 세계 키는 마스크 판으로 정한다(판 4 = 길, 판 5 = 길 + 막음, 판 6 = 막음, 판 2 = 없음 · 'shelter_rule' = 고정 길).
- 세계 하나(_r7_world): 막음 통계 gate 를 적고, 탐침·gate 를 붙여도 세계 요약·도망 기록이 그대로다. 판 5 시작 두뇌의 반사 밖 두뇌 FLEE 0.
- 점검 (c) 의 GF·GR(합성 판), 본 학습 점검 모음(제외·멈춤), 고르기 자격(GF·GR)·순서, 고르기·판정 막기, A5 계약(판 5), 띄우기 -DryRun.
시드는 탐색 32080~32099 만 쓴다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import json
import shutil
import subprocess
import sys

import numpy as np
import pytest

from env.config import ROOT

R7 = ROOT / "results" / "v3" / "r7"
for _p in (str(R7), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CK = ROOT / "ckpt" / "v3"
HAVE_CK = all((CK / n).exists() for n in ("v3_r1_g995_s3_obs24route0.zip", "v3_r1_g995_s3_obs24route0m5.zip", "v3_r1_g995_s3_obs21zero.zip",
                                          "v3_r1_g995_s3_obs21zero_m6.zip"))
pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def E():
    import r7_eval

    return r7_eval


def test_uses_and_seed_guard(E):
    """사전 등록 2절 시드 표 그대로. 쓰임 칸은 38000~38199 안이고 고르기·점검·판정이 겹치지 않으며 R6 칸과도 겹치지 않는다."""
    assert E.USES == {"judge_n": (38000, 38099, 1800, "N"), "judge_g": (38000, 38039, 3600, "G"), "stuck": (38000, 38004, 3600, "stuck"),
                      "select": (38100, 38119, 1800, "N"), "check": (38120, 38139, 1800, "N")}
    assert E.R7_SEEDS == (38000, 38199) and E.SMOKE_SEEDS == (32080, 32099)
    sel, chk, jn, jg, st = (set(E.use_plan(u)["seeds"]) for u in ("select", "check", "judge_n", "judge_g", "stuck"))
    assert not (sel & chk) and not (sel & jn) and not (chk & jn) and jg <= jn and st <= jg
    assert all(38000 <= s <= 38199 for s in sel | chk | jn)
    lo6, hi6 = E.R6.R6_SEEDS
    assert not any(lo6 <= s <= hi6 for s in sel | chk | jn)
    assert all(not any(lo <= s <= hi for s in sel | chk | jn) for lo, hi, _, _ in E.R6.USES.values())
    p = E.use_plan("judge_n")
    assert (p["seeds"][0], p["seeds"][-1], len(p["seeds"]), p["steps"], p["world"]) == (38000, 38099, 100, 1800, "N")
    for bad in ([38000], [37000], [32000]):
        with pytest.raises(SystemExit):
            E.use_plan("smoke", bad, 30)
    with pytest.raises(SystemExit):
        E.use_plan("check", [38120], 1800)
    assert E.smoke_plan("judge_g", [32080], 30)["world"] == "G"


def test_early_rules_numbers(E):
    """점검 문턱(사전 등록 5-1): R6 5-1 그대로 + GF·GR 짝 t < +2. 고르기 자격 GF·GR 짝 t < +2. λ 0.98 · 도주 비용 0 고정."""
    assert E.EARLY == dict(pi_move=0.05, ev_min=0.0, t_hide=-2.0, t_caught_ratio=2.0, t_caught=2.0, t_gf=2.0, t_gr=2.0)
    assert E.SELECT == dict(t_gf=2.0, t_gr=2.0)
    assert E.LAM == 0.98 and E.FLIGHT_COST == 0.0 and E.CONTRACT_R7 == "0xad7bad5e1acaf071"
    assert E.GUARDS == E.R6.GUARDS and len(E.GUARDS) == 18


@pytest.mark.skipif(not HAVE_CK, reason="ckpt 는 저장소에 없다 (route_extend.py·r7_start.py 로 만든다)")
def test_resolve_model_world_keys(E):
    """두뇌의 마스크 판 → 세계 키. zip 에서 읽은 판은 PPO.load 의 판과 같다."""
    from stable_baselines3 import PPO

    want = {"route0": (24, 4, {"wild_flight.route": True}), "route0m5": (24, 5, {"wild_flight.route": True, E.GATE_KEY: False}),
            "obs21zero_m6": (21, 6, {E.GATE_KEY: False}), "obs21zero": (21, 2, {})}
    for name, (obs, mv, sets) in want.items():
        s = E.resolve_model(name)
        assert (s["obs"], s["mask"], s["sets"]) == (obs, mv, sets), name
        assert int(PPO.load(str(s["path"]), device="cpu").policy.rep_mask_version) == mv
    r = E.resolve_model("shelter_rule")
    assert r["sets"] == {"wild_flight.route_fixed": "shelter"} and r["mask"] == 2
    if E.R6_PICK.exists():
        assert E.resolve_model("r6")["sets"] == {"wild_flight.route": True}


@pytest.mark.skipif(not HAVE_CK, reason="ckpt 는 저장소에 없다")
def test_world_gate_and_probe_keep_world(E, tmp_path):
    """_r7_world: 판 5 시작 두뇌 세계에 막음 통계(gate)가 붙고 반사 밖 두뇌 FLEE 0, 판 4 세계는 None. 탐침을 붙여도 세계 요약·도망 기록이 같다.
    N 세계에서 route0m5(판 5)와 route0(판 4)의 판은 같은 시드면 세계 요약이 같다(이 시드에서 route0 이 반사 밖 FLEE 를 고르지 않는다 — r7_start 확인)."""
    info = E.prepare_info(tmp_path)
    plan = E.smoke_plan("judge_n", [32096], 200)
    m5, m4 = E.resolve_model("route0m5"), E.resolve_model("route0")
    a = E.run_items(E.make_items(info, m5, plan, probe=True), 1)
    b = E.run_items(E.make_items(info, m5, plan, probe=False), 1)
    c = E.run_items(E.make_items(info, m4, plan, probe=False), 1)
    for (_, wa), (_, wb), (_, wc) in zip(a, b, c):
        wa, wb, wc = dict(wa), dict(wb), dict(wc)
        pr = wa.pop("probe")
        for w in (wa, wb, wc):
            w.pop("wall_s")
        assert wa["gate"] == wb["gate"] and wa["gate"]["brain_flee"] == 0 and wa["gate"]["free_decisions"] > 0
        assert wc.pop("gate") is None
        assert wa == wb
        wb.pop("gate")
        assert wb == wc
        assert pr["cover_max"] == 0.0 and pr["pick_sh"] == 0
    res = dict(meta=dict(mask=5), worlds=[w for _, w in a])
    assert E.gate_pooled(res)["brain_flee"] == 0 and E.none_seed(res) == {32096: 0}
    assert E.gate_pooled(dict(worlds=[w for _, w in c])) is None


def _flight_world(seed, region, started, live, refled, route=True, trunc=0):
    """GF·GR 셈에 쓰는 칸만 있는 합성 세계 (live.flight_seed·r6_eval.route_seed 가 읽는 칸)."""
    n = {k: 0 for k in ("cover", "obstacle", "fov", "range", "switch", "stop", "held", "unchased", "caught", "starved", "truncated")}
    n["truncated"] = trunc
    f = dict(started=started, live_steps=live, flee_steps=100, reflex_steps=100, shelter_end=0, n=n, steps=dict(n), contact=dict(n))
    if route:
        f["route"] = dict(refled=refled, by_route=dict(none=dict(n={"unchased": 0})))
    return dict(seed=seed, region=region, flight=f)


def _pairs(rng, d_start=0, d_refl=0, route=True):
    """(후보, 기준) 합성 판: 시드 20 × 지역 셋. 후보 = 기준 + 지역마다 시작한 도망 d_start·다시 도망 d_refl + 양쪽 잡음(−1·0·+1). d 가 0 이면 잡음도 없다."""
    cand, cur = [], []
    for s in range(20):
        for r in ("Barren", "Forest", "Highland"):
            st, rf = int(rng.integers(900, 1100)), int(rng.integers(20, 40))
            cur.append(_flight_world(s, r, st, 500_000, rf))
            ns = int(rng.integers(-1, 2)) if d_start else 0
            nr = int(rng.integers(-1, 2)) if d_refl else 0
            cand.append(_flight_world(s, r, st + d_start + ns, 500_000, rf + d_refl + nr, route=route))
    return dict(worlds=cand), dict(worlds=cur)


def test_gf_gr_pairs(E):
    """GF = 1000 산 사슴-스텝당 시작한 도망(지역 셋 합), GR = 5 초 안 다시 도망 수(지역 셋 합). 길 기록이 없는 판(대조 '길 끔')은 GR None.
    GR 은 판정 GR(r6_eval.route_guards)과 같은 셈이다."""
    cand, cur = _pairs(np.random.default_rng(0), d_start=30, d_refl=10)
    gf, gr = E.gf_pair(cand, cur), E.gr_pair(cand, cur)
    assert gf["n"] == gr["n"] == 20 and gf["t"] > 2 and gr["t"] > 2
    per = {}
    for wa, wb in zip(cand["worlds"], cur["worlds"]):
        x = per.setdefault(wa["seed"], [0, 0, 0, 0])
        x[0] += wa["flight"]["started"]
        x[1] += wb["flight"]["started"]
        x[2] += wa["flight"]["route"]["refled"]
        x[3] += wb["flight"]["route"]["refled"]
    assert gf["diff"] == pytest.approx(np.mean([1000.0 * (a - b) / 1_500_000 for a, b, _, _ in per.values()]))
    assert gr["diff"] == pytest.approx(np.mean([c - d for _, _, c, d in per.values()]))
    g = E.R6.route_guards(cand, cur)["GR_reflee"]
    assert g["diff"] == gr["diff"] and g["t"] == gr["t"]
    same_c, same_b = _pairs(np.random.default_rng(1))
    assert E.gf_pair(same_c, same_b)["t"] == 0.0 and E.gr_pair(same_c, same_b)["t"] == 0.0
    off, base = _pairs(np.random.default_rng(2), route=False)
    assert E.gr_pair(off, base) is None


def _chk(a, b, parts_ok: dict, defect=False):
    parts = {k: dict(ok=v) for k, v in parts_ok.items()}
    c_ok = all(v for v in parts_ok.values() if v is not None)
    return dict(a=dict(ok=a), b=dict(ok=b), c=dict(ok=c_ok, parts=parts), defect=dict(hit=defect), passed=bool(a and b and c_ok and not defect))


OK = dict(hide=True, caught_ratio=True, caught=True, gf=True, gr=True)


def test_main_check_rules(E):
    """사전 등록 5-2: (c)(숨음 비율·잡힘 비율·잡힌 몫·GF·GR) 가 2M·5M 가운데 한 번이라도 걸린 시드는 제외, 결함·못 배움·(b)·모두 제외는 멈춤."""
    ok = {(f"s{s}", k): _chk(True, True, OK) for s in range(3) for k in (2, 5)}
    r = E.main_check_rules(ok, [2, 5])
    assert not r["stop"] and not r["excluded"]
    c = dict(ok)
    c[("s1", 2)] = _chk(True, True, dict(OK, gr=False))
    c[("s2", 5)] = _chk(True, True, dict(OK, gf=False))
    r = E.main_check_rules(c, [2, 5])
    assert sorted(r["excluded"]) == ["s1", "s2"] and not r["stop"]
    assert "gr" in r["excluded"]["s1"] and "gf" in r["excluded"]["s2"]
    d = dict(ok)
    d[("s0", 5)] = _chk(True, True, OK, defect=True)
    assert E.main_check_rules(d, [2, 5])["stop"]
    na = {k: _chk(k[1] == 2, True, OK) for k in ok}
    assert E.main_check_rules(na, [2, 5])["stop"]
    nb = {k: _chk(True, k[1] == 2, OK) for k in ok}
    assert any("(b)" in w for w in E.main_check_rules(nb, [2, 5])["why"])
    allc = {k: _chk(True, True, dict(OK, gf=False)) for k in ok}
    r = E.main_check_rules(allc, [2, 5])
    assert r["stop"] and len(r["excluded"]) == 3 and any("실패" in w for w in r["why"])


def test_select_rule(E, monkeypatch):
    """사전 등록 6절: GF·GR 짝 t < +2 인 모델만 자격, 그 가운데 숨음 비율(전체 합) 큰 쪽 → 잡힌 몫 → 굶은 몫 → 모델 시드. 자격 없으면 pick None."""
    good, base = _pairs(np.random.default_rng(5))
    bad_gr = _pairs(np.random.default_rng(5), d_refl=15)[0]
    bad_gf = _pairs(np.random.default_rng(5), d_start=40)[0]
    good2 = dict(worlds=list(good["worlds"]))
    # 고르기 순서 칸은 r6_eval.select_key(숨음 비율·잡힌 몫·굶은 몫 — 합성 판에는 그 칸이 없다)를 갈아 끼운다. 자격 셈(GF·GR)은 그대로 본다
    keys = {id(good): (-0.20, 0.10, 0.0, 0), id(bad_gr): (-0.30, 0.10, 0.0, 1), id(bad_gf): (-0.25, 0.10, 0.0, 2), id(good2): (-0.22, 0.10, 0.0, 3),
            id(base): (-0.10, 0.10, 0.0, -1)}
    monkeypatch.setattr(E.R6, "select_key", lambda res, seed: keys[id(res)])
    s = E.select_rule([("good", 0, good), ("bad_gr", 1, bad_gr), ("bad_gf", 2, bad_gf), ("good2", 3, good2)], base)
    ok = {r["model"]: (r["gf_ok"], r["gr_ok"]) for r in s["rows"]}
    assert ok == {"good": (True, True), "bad_gr": (True, False), "bad_gf": (False, True), "good2": (True, True)}
    assert s["eligible"] == ["good2", "good"] and s["pick"] == "good2"          # 자격 안에서 숨음 비율 큰 쪽 (bad_gr 가 가장 커도 자격 없음)
    s = E.select_rule([("bad_gr", 1, bad_gr), ("bad_gf", 2, bad_gf)], base)
    assert s["pick"] is None and s["eligible"] == []
    no_route = _pairs(np.random.default_rng(5), route=False)[0]
    keys[id(no_route)] = (-0.5, 0.1, 0.0, 4)
    assert E.select_rule([("no_route", 4, no_route)], base)["pick"] is None    # 길 기록 없는 판은 GR 자격이 없다


def test_select_and_judge_guards(E, tmp_path):
    """고르기 후보는 R7 본 학습 마지막 모델만, 점검 기록(스모크 아님·멈춤 아님·2M·5M 줄 있음)이 있어야 하고 제외 시드는 막는다. 판정은 select.txt 의 고른 모델
    ('없음' 이면 None)."""
    em = tmp_path / "early_main.json"
    with pytest.raises(SystemExit):
        E.select_guard(["ckpt/v3/v3_r7_g995_s0_20m.zip"], em)               # 기록 없음
    rows = {f"s{s}_{k}m": dict(passed=True) for s in range(3) for k in (2, 5)}
    em.write_text(json.dumps(dict(rows=rows, rules=dict(excluded={"s1": "(c) 걸림: 2M (c) gr"}, stop=False), smoke=None)), encoding="utf-8")
    E.select_guard(["ckpt/v3/v3_r7_g995_s0_20m.zip", "ckpt/v3/v3_r7_g995_s2_20m.zip"], em)
    for bad in (["ckpt/v3/v3_r7_g995_s1_20m.zip"], ["ckpt/v3/v3_r7_g995_s0_20m_5m.zip"], ["ckpt/v3/v3_r7off_g995_s0_20m.zip"],
                ["ckpt/v3/v3_r6_g995_s0_20m.zip"], ["ckpt/v3/v3_r7_g995_s3_20m.zip"]):
        with pytest.raises(SystemExit):
            E.select_guard(bad, em)
    em.write_text(json.dumps(dict(rows=rows, rules=dict(excluded={}, stop=True, why=["x"]), smoke=None)), encoding="utf-8")
    with pytest.raises(SystemExit):
        E.select_guard(["ckpt/v3/v3_r7_g995_s0_20m.zip"], em)
    em.write_text(json.dumps(dict(rows=rows, rules=dict(excluded={}, stop=False), smoke="32080-32081")), encoding="utf-8")
    with pytest.raises(SystemExit):
        E.select_guard(["ckpt/v3/v3_r7_g995_s0_20m.zip"], em)
    st = tmp_path / "select.txt"
    assert E.picked_model(st) is None
    st.write_text("| 모델 | … |\n\n고른 모델: ckpt/v3/v3_r7_g995_s2_20m.zip\n", encoding="utf-8")
    assert E.picked_model(st) == "ckpt/v3/v3_r7_g995_s2_20m.zip"
    st.write_text("고른 모델: 없음 — GF·GR 자격을 넘은 모델이 없다\n", encoding="utf-8")
    assert E.picked_model(st) is None


@pytest.mark.skipif(not HAVE_CK, reason="ckpt 는 저장소에 없다")
def test_a5_contract_mask5(E, tmp_path):
    """A5: 판 5 두뇌 파일(골든 세계 = 판 5 거울)은 계약 0xad7bad5e1acaf071·관측 24·판 5 로 통과. 판 4 두뇌는 계약이 달라 통과하지 않는다."""
    v = E.a5_check(CK / "v3_r1_g995_s3_obs24route0m5.zip", tmp_path)
    assert v["ok"] and v["contract_ok"] and v["contract_hash"] == E.CONTRACT_R7 and (v["obs_dim"], v["mask_version"]) == (24, 5)
    assert v["golden_world"] == "configs/v3_wild3_route5_mirror.yaml"
    w = E.a5_check(CK / "v3_r1_g995_s3_obs24route0.zip", tmp_path)
    assert not w["contract_ok"] and not w["ok"]


def test_prereg_doc_numbers(E):
    """사전 등록 문서가 도구의 시드·문턱·계약을 그대로 적는다(글자 확인)."""
    t = (R7 / "PREREG.md").read_text(encoding="utf-8")
    for s in ("38000~38099", "38000~38039", "38000~38004", "38100~38119", "38120~38139", "0xad7bad5e1acaf071", "+1.984", "+2.023",
              "v3_r1_g995_s3_obs24route0m5.zip", "configs/v3_r7_train.yaml", "configs/v3_r7off_train.yaml", "configs/ppo_r6_lam098.yaml"):
        assert s in t, s


@pytest.mark.skipif(shutil.which("powershell") is None, reason="powershell 없음")
def test_launch_dry_run():
    """띄우기 스크립트 -DryRun: 본 학습 3 + 대조 1 의 명령이 사전 등록 이름·설정·시작 두뇌·λ 0.98 PPO 설정을 쓰고, 점검 명령이 붙는다."""
    ps = R7 / "launch_train.ps1"
    r = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps), "-Checks", "-DryRun"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT, timeout=120)
    out = r.stdout
    done = sorted((ROOT / "ckpt" / "v3").glob("v3_r7*_g995_s*_20m.zip"))
    if done:
        # 본 학습이 끝난 뒤(10-23 밤): 같은 실행 이름의 끝 모델이 있으면 -DryRun 이어도 명령을 적기 전에 멈춘다(덮어쓰지 않는다 — 사람이 정한다)
        assert r.returncode != 0 and "[DryRun] train" not in out and "ckpt/v3/v3_r7_g995_s0_20m.zip" in r.stderr
        return
    lines = [x for x in out.splitlines() if x.startswith("[DryRun] train")]
    assert len(lines) == 4 and all("--steps 20000000" in x and "--ppo-config configs/ppo_r6_lam098.yaml" in x and "--tb runs/v3_r7" in x for x in lines)
    r7 = [x for x in lines if "configs/v3_r7_train.yaml" in x]
    assert len(r7) == 3 and all("obs24route0m5.zip" in x for x in r7)
    assert [f"--seed {s} " in x and f"--run-name v3_r7_g995_s{s}_20m" in x for s, x in enumerate(r7)] == [True, True, True]
    off = [x for x in lines if "configs/v3_r7off_train.yaml" in x]
    assert len(off) == 1 and "obs21zero_m6.zip" in off[0] and "--run-name v3_r7off_g995_s0_20m" in off[0]
    assert "early_checks.py --seeds 0 1 2 --control --at 2 5" in out
