"""v3 R7e 사전 등록 도구 시험 (results/v3/r7e/PREREG.md — 학습 없음, 점검·고르기·판정 전).

- 쓰임마다 시드·길이·세계(사전 등록 2절): 새 점검 38220~38239 · 새 고르기 38200~38219 는 서로·판정 칸과 겹치지 않고 R7 이 이미 쓴 38100~38139 와도 겹치지 않는다.
  판정 칸은 R7 사전 등록 그대로다. run 은 판정 쓰임을 받지 않는다. 스모크는 32080~32099 만.
- 규칙 수: 점검 (c) = 사건 숨음·잡힘 비율 + 잡힌 몫 + GF + GE (문턱 R7 그대로), 고르기 자격 GF·GE, 지킴 18 칸 = R7 지킴의 GR 자리에 GE.
- 사건 단위 셈이 관문 셈(live.episode_pair·flight_rate_pair 'episodes')과 같고 손 셈과 맞는다. 사건이 없는 판·세계 코드가 다른 판은 받지 않는다.
- 점검 모음(제외·멈춤), 고르기 자격·순서, 판정 판정(GR 은 보고만, GE 는 지킴), 고르기·판정 막기, R7 두뇌 sha1 막기, 작은 실제 판으로 판정 표 꼴.
시드는 탐색 32080~32099 만 쓴다.
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import json
import shutil
import sys

import numpy as np
import pytest

from env.config import ROOT

R7E = ROOT / "results" / "v3" / "r7e"
for _p in (str(R7E), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CK = ROOT / "ckpt" / "v3"
HAVE_CK = all((CK / n).exists() for n in ("v3_r1_g995_s3_obs24route0.zip", "v3_r1_g995_s3_obs24route0m5.zip"))
HAVE_R7 = all((CK / f"{n}.zip").exists() for n in ("v3_r7_g995_s0_20m", "v3_r7_g995_s1_20m", "v3_r7_g995_s2_20m", "v3_r7off_g995_s0_20m"))
pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def E():
    import r7e_eval

    return r7e_eval


def test_uses_and_seed_guard(E):
    """사전 등록 2절 시드 표 그대로. 새 점검·고르기는 겹치지 않고 R7 이 쓴 38100~38139 와도 겹치지 않는다. 판정 칸은 R7 사전 등록과 같다."""
    assert E.USES == {"judge_n": (38000, 38099, 1800, "N"), "judge_g": (38000, 38039, 3600, "G"), "stuck": (38000, 38004, 3600, "stuck"),
                      "select": (38200, 38219, 1800, "N"), "check": (38220, 38239, 1800, "N")}
    for u in ("judge_n", "judge_g", "stuck"):
        assert E.USES[u] == E.R7.USES[u]
    assert E.R7_USED == ((E.R7.USES["select"][0], E.R7.USES["select"][1]), (E.R7.USES["check"][0], E.R7.USES["check"][1]))
    sel, chk, jn, jg, st = (set(E.use_plan(u)["seeds"]) for u in ("select", "check", "judge_n", "judge_g", "stuck"))
    assert len(sel) == len(chk) == 20 and len(jn) == 100 and len(jg) == 40 and len(st) == 5
    assert not (sel & chk) and not (sel & jn) and not (chk & jn) and jg <= jn and st <= jg
    used = {s for lo, hi in E.R7_USED for s in range(lo, hi + 1)}
    assert not ((sel | chk | jn) & used)
    lo6, hi6 = E.R6.R6_SEEDS
    assert not any(lo6 <= s <= hi6 for s in sel | chk | jn)
    for bad in ([38000], [38120], [38200], [37000], [32000]):
        with pytest.raises(SystemExit):
            E.use_plan("smoke", bad, 30)
    with pytest.raises(SystemExit):
        E.use_plan("check", [38220], 1800)
    assert E.smoke_plan("judge_g", [32080], 30)["world"] == "G"
    for u in ("judge_n", "judge_g", "stuck"):                                  # 판정 시드는 judge 명령으로만 (run 이 받지 않는다)
        with pytest.raises(SystemExit):
            E.main(["run", "--use", u, "--model", "route0", "--name", "x"])


def test_rules_numbers(E):
    """점검·고르기 문턱(사전 등록 4·5절)은 R7 그대로이되 GR → GE. 지킴 18 칸 = R7 지킴의 GR_reflee 자리에 GE_episode_starts. λ 0.98 고정."""
    assert E.EARLY == dict(pi_move=0.05, ev_min=0.0, t_hide=-2.0, t_caught_ratio=2.0, t_caught=2.0, t_gf=2.0, t_ge=2.0)
    r7 = dict(E.R7.EARLY)
    assert {k: v for k, v in E.EARLY.items() if k != "t_ge"} == {k: v for k, v in r7.items() if k != "t_gr"} and E.EARLY["t_ge"] == r7["t_gr"]
    assert E.SELECT == dict(t_gf=2.0, t_ge=2.0) and E.SELECT["t_ge"] == E.R7.SELECT["t_gr"]
    assert len(E.GUARDS) == 18 and len(set(E.GUARDS)) == 18
    assert set(E.GUARDS) == (set(E.R7.GUARDS) - {"GR_reflee"}) | {"GE_episode_starts"}
    assert E.REPORT_KEYS == ("REPORT_N_flight_hide", "REPORT_N_flight_caught", "GR_reflee")
    assert E.LAM == 0.98 and E.FLIGHT_COST == 0.0 and E.CHECK_AT == (2, 5)
    assert len(E.R7_SHA1) == 12 and all(len(v) == 12 for v in E.R7_SHA1.values())
    # 길 지킴 GT·GTr(r6_eval.route_guards)과 A5 밖의 지킴은 모두 실시간 관문(live.gate_live)의 지킴 칸이다 — 관문과 같은 셈
    assert all(k.startswith(E.lv.GUARD_PREFIXES) for k in E.GUARDS if k not in ("GT_flight_time", "GTr_truncated", "A5_export"))


# --------------------------------------------------------------------- #
# 합성 판 (사건·도망 기록 칸만 — live.flight_seed 가 읽는 칸)
# --------------------------------------------------------------------- #

def _world(seed, region, started=1000, live=500_000, ep_started=900, ep_chased=300, ep_hidden=40, ep_caught=30, hidden=50, chased=330, caught=30,
           refled=30, route=True):
    n = {k: 0 for k in ("cover", "obstacle", "fov", "range", "switch", "stop", "held", "unchased", "caught", "starved", "truncated")}
    n["caught"] = caught
    ep = {k: 0 for k in E_KEYS}
    ep.update(started=ep_started, chased=ep_chased, hidden=ep_hidden, caught=ep_caught, other=ep_started - ep_hidden - ep_caught)
    f = dict(started=started, live_steps=live, flee_steps=100, reflex_steps=100, shelter_end=0, n=n, steps=dict(n), contact=dict(n),
             hide=dict(chased=chased, hidden=hidden, watching=0, cover_then_caught=0, cover_then_starved=0), episode=ep)
    if route:
        f["route"] = dict(refled=refled, by_route=dict(none=dict(n={"unchased": 0})))
    return dict(seed=seed, region=region, flight=f)


E_KEYS = ("started", "chased", "hidden", "caught", "starved", "other", "truncated", "watching", "other_chased", "joined", "joined_cover", "joined_other",
          "window_caught", "window_starved")


def _pairs(rng, d_hid=0, d_ep=0, d_start=0, n_seeds=20):
    """(후보, 기준) 합성 판: 시드 n × 지역 셋. 후보 = 기준 + 지역마다 숨음 사건 d_hid·사건 시작 d_ep·도망 시작 d_start + 잡음(−1·0·+1, d 가 0 이면 없음)."""
    cand, cur = [], []
    for s in range(n_seeds):
        for r in ("Barren", "Forest", "Highland"):
            st, es, hd = int(rng.integers(900, 1100)), int(rng.integers(800, 900)), int(rng.integers(30, 50))
            cur.append(_world(s, r, started=st, ep_started=es, ep_hidden=hd))
            j = (lambda d: int(rng.integers(-1, 2)) if d else 0)
            cand.append(_world(s, r, started=st + d_start + j(d_start), ep_started=es + d_ep + j(d_ep), ep_hidden=hd + d_hid + j(d_hid)))
    return dict(worlds=cand), dict(worlds=cur)


def test_episode_pairs_match_gate(E):
    """사건 숨음 비율·사건 잡힘 비율 짝 = 시드마다 지역 셋 분자·분모 합의 몫(live.episode_pair — 관문 P1·GH 셈), GE = 1000 × 사건 시작 ÷ 산 사슴-스텝."""
    cand, cur = _pairs(np.random.default_rng(0), d_hid=8, d_ep=-20)
    h, c, ge = E.ep_pair(cand, cur, "hide"), E.ep_pair(cand, cur, "caught"), E.ge_pair(cand, cur)
    assert h["n"] == c["n"] == ge["n"] == 20 and h["t"] > 2 and ge["t"] < -2
    per = {}
    for wa, wb in zip(cand["worlds"], cur["worlds"]):
        x = per.setdefault(wa["seed"], np.zeros(6))
        ea, eb = wa["flight"]["episode"], wb["flight"]["episode"]
        x += [ea["hidden"], ea["chased"], eb["hidden"], eb["chased"], ea["started"] - eb["started"], 0]
    assert h["diff"] == pytest.approx(np.mean([a / b - c_ / d for a, b, c_, d, _, _ in per.values()]))
    assert ge["diff"] == pytest.approx(np.mean([1000.0 * e / 1_500_000 for *_, e, _ in per.values()]))
    q = E.lv.flight_rate_pair(cand, cur, "episodes")
    assert (q["diff"], q["t"]) == (ge["diff"], ge["t"])
    same_c, same_b = _pairs(np.random.default_rng(1))
    assert E.ep_pair(same_c, same_b, "hide")["t"] == 0.0 and E.ge_pair(same_c, same_b)["t"] == 0.0
    old = dict(worlds=[dict(w, flight={k: v for k, v in w["flight"].items() if k != "episode"}) for w in cur["worlds"]])
    with pytest.raises(ValueError):
        E.need_episode(old, "옛 판")
    E.need_episode(cur, "새 판")


def test_same_code(E):
    """견주는 판의 세계 셈 길 지문이 다르면 멈춘다(돌리는 사이 세계 코드가 바뀐 판끼리 짝을 짓지 않는다)."""
    a, b = dict(meta=dict(code=dict(world="aaa"))), dict(meta=dict(code=dict(world="aaa")))
    E.same_code(a, b, None)
    with pytest.raises(ValueError):
        E.same_code(a, dict(meta=dict(code=dict(world="bbb"))))


def _chk(a, b, parts_ok: dict, defect=False):
    parts = {k: dict(ok=v) for k, v in parts_ok.items()}
    c_ok = all(v for v in parts_ok.values() if v is not None)
    return dict(a=dict(ok=a), b=dict(ok=b), c=dict(ok=c_ok, parts=parts), defect=dict(hit=defect), passed=bool(a and b and c_ok and not defect))


OK = dict(hide=True, caught_ratio=True, caught=True, gf=True, ge=True)


def test_main_check_rules(E):
    """사전 등록 4-2: (c)(사건 숨음·잡힘 비율·잡힌 몫·GF·GE) 가 2M·5M 가운데 한 번이라도 걸린 시드는 제외, 결함·못 배움·(b)·모두 제외는 멈춤 (R7 5-2 그대로)."""
    ok = {(f"s{s}", k): _chk(True, True, OK) for s in range(3) for k in (2, 5)}
    r = E.main_check_rules(ok, [2, 5])
    assert not r["stop"] and not r["excluded"]
    c = dict(ok)
    c[("s1", 2)] = _chk(True, True, dict(OK, ge=False))
    c[("s2", 5)] = _chk(True, True, dict(OK, hide=False))
    c[("off", 5)] = _chk(True, True, dict(OK, gf=False))                    # 대조 줄은 모음에 넣지 않는다 (넣어도 시드 이름이 아니라 빠진다)
    r = E.main_check_rules(c, [2, 5])
    assert sorted(r["excluded"]) == ["s1", "s2"] and not r["stop"]
    assert "ge" in r["excluded"]["s1"] and "hide" in r["excluded"]["s2"]
    d = dict(ok)
    d[("s0", 5)] = _chk(True, True, OK, defect=True)
    assert E.main_check_rules(d, [2, 5])["stop"]
    na = {k: _chk(k[1] == 2, True, OK) for k in ok}
    assert E.main_check_rules(na, [2, 5])["stop"]
    na2 = {k: _chk(not (k[0] == "s1" and k[1] == 2), True, OK) for k in ok}   # 2M 의 (a) 만 못 넘음은 제외도 멈춤도 아니다 (R7 s1 2M 꼴)
    r = E.main_check_rules(na2, [2, 5])
    assert not r["stop"] and not r["excluded"]
    nb = {k: _chk(True, k[1] == 2, OK) for k in ok}
    assert any("(b)" in w for w in E.main_check_rules(nb, [2, 5])["why"])
    allc = {k: _chk(True, True, dict(OK, ge=False)) for k in ok}
    r = E.main_check_rules(allc, [2, 5])
    assert r["stop"] and len(r["excluded"]) == 3 and any("R7e 실패" in w for w in r["why"])


def test_select_rule(E, monkeypatch):
    """사전 등록 5절: GF·GE 짝 t < +2 인 모델만 자격, 그 가운데 사건 숨음 비율(전체 합) 큰 쪽 → 잡힌 몫 → 굶은 몫 → 모델 시드. 자격 없으면 pick None.
    GR 은 자격에 쓰지 않는다(보고만)."""
    rng = lambda: np.random.default_rng(5)  # noqa: E731
    good, base = _pairs(rng())
    bad_ge = _pairs(rng(), d_ep=40)[0]
    bad_gf = _pairs(rng(), d_start=40)[0]
    gr_only = dict(worlds=[dict(w, flight=dict(w["flight"], route=dict(w["flight"]["route"], refled=w["flight"]["route"]["refled"] + 15 + k % 3)))
                           for k, w in enumerate(good["worlds"])])      # GR 만 크게 나쁨 — 자격은 그대로 있다
    good2 = dict(worlds=list(good["worlds"]))
    keys = {id(good): (-0.20, 0.10, 0.0, 0), id(bad_ge): (-0.30, 0.10, 0.0, 1), id(bad_gf): (-0.25, 0.10, 0.0, 2), id(good2): (-0.22, 0.10, 0.0, 3),
            id(gr_only): (-0.21, 0.10, 0.0, 4), id(base): (-0.10, 0.10, 0.0, -1)}
    monkeypatch.setattr(E, "ep_select_key", lambda res, seed: keys[id(res)])
    monkeypatch.setattr(E.lv, "flight_pooled", lambda res: dict(hide_share=0.1, ep_hide_share=-keys[id(res)][0]))
    s = E.select_rule([("good", 0, good), ("bad_ge", 1, bad_ge), ("bad_gf", 2, bad_gf), ("good2", 3, good2), ("gr_only", 4, gr_only)], base)
    ok = {r["model"]: (r["gf_ok"], r["ge_ok"]) for r in s["rows"]}
    assert ok == {"good": (True, True), "bad_ge": (True, False), "bad_gf": (False, True), "good2": (True, True), "gr_only": (True, True)}
    gr = {r["model"]: r["gr"]["t"] for r in s["rows"]}
    assert gr["gr_only"] > 2                                             # GR 은 나쁘지만 보고만
    assert s["eligible"] == ["good2", "gr_only", "good"] and s["pick"] == "good2"
    s = E.select_rule([("bad_ge", 1, bad_ge), ("bad_gf", 2, bad_gf)], base)
    assert s["pick"] is None and s["eligible"] == []


def test_verdict_of(E):
    """판정: P1 이 아니면 기각, 지킴 18 칸 가운데 하나라도 ok 가 참이 아니면(없는 칸 포함) 기각. 보고만 칸(GR·도망 단위)은 보지 않는다."""
    good = {k: dict(ok=True) for k in E.GUARDS}
    rep = {k: dict(ok=None) for k in E.REPORT_KEYS}
    p1 = dict(ok=True, a=0.2, b=0.12, t=5.0, n=100, dropped=[])
    v, why, bad = E.verdict_of(dict(P1_N_hide=p1, **good, **rep), 1.984)
    assert v == "통과" and not bad
    v, _, bad = E.verdict_of(dict(P1_N_hide=p1, **good, GR_reflee=dict(ok=False, t=9.0)), 1.984)
    assert v == "통과" and not bad                                       # GR 이 나빠도 보고만
    v, why, bad = E.verdict_of(dict(P1_N_hide=p1, **dict(good, GE_episode_starts=dict(ok=False))), 1.984)
    assert v == "기각" and bad == ["GE_episode_starts"]
    g2 = dict(good)
    g2.pop("GT_flight_time")
    assert E.verdict_of(dict(P1_N_hide=p1, **g2), 1.984)[2] == ["GT_flight_time"]
    v, why, _ = E.verdict_of(dict(P1_N_hide=dict(p1, ok=False, t=1.5), **good), 1.984)
    assert v == "기각" and "1차 P1" in why


@pytest.mark.skipif(not HAVE_R7, reason="R7 본 학습 산출(ckpt)은 저장소에 없다")
def test_r7_models_and_select_guard(E, tmp_path):
    """R7 두뇌 sha1 이 R7 이 잰 것과 같다(모두). 이름만 같은 다른 파일은 받지 않는다. 고르기 막기: R7e 점검 기록(스모크 아님·점검 시드·멈춤 아님·2M·5M 줄)이
    있어야 하고 제외 시드·중간 체크포인트·대조·R6 모델은 받지 않는다. 판정은 select.txt 의 고른 모델('없음' 이면 None)."""
    for stem in E.R7_SHA1:
        E.require_r7_model(CK / f"{stem}.zip")
    fake = tmp_path / "v3_r7_g995_s0_20m.zip"
    shutil.copy(CK / "v3_r1_g995_s3_obs24route0m5.zip", fake)
    with pytest.raises(SystemExit):
        E.require_r7_model(fake)
    with pytest.raises(SystemExit):
        E.require_r7_model(CK / "v3_r1_g995_s3_obs24route0m5.zip")
    em = tmp_path / "early_main.json"
    with pytest.raises(SystemExit):
        E.select_guard(["ckpt/v3/v3_r7_g995_s0_20m.zip"], em)               # 기록 없음
    rows = {f"s{s}_{k}m": dict(passed=True) for s in range(3) for k in (2, 5)}
    chk = E.use_plan("check")["seeds"]

    def put(**kw):
        d = dict(rows=rows, rules=dict(excluded={"s1": "(c) 걸림: 2M (c) ge"}, stop=False), smoke=False, seeds=chk)
        d.update(kw)
        em.write_text(json.dumps(d), encoding="utf-8")

    put()
    E.select_guard(["ckpt/v3/v3_r7_g995_s0_20m.zip", "ckpt/v3/v3_r7_g995_s2_20m.zip"], em)
    for bad in (["ckpt/v3/v3_r7_g995_s1_20m.zip"], ["ckpt/v3/v3_r7_g995_s0_20m_5m.zip"], ["ckpt/v3/v3_r7off_g995_s0_20m.zip"],
                ["ckpt/v3/v3_r6_g995_s0_20m.zip"], ["ckpt/v3/v3_r7_g995_s3_20m.zip"]):
        with pytest.raises(SystemExit):
            E.select_guard(bad, em)
    for kw in (dict(rules=dict(excluded={}, stop=True, why=["x"])), dict(smoke=True), dict(seeds=list(range(38120, 38140))),
               dict(rows={k: v for k, v in rows.items() if k != "s0_5m"})):
        put(**kw)
        with pytest.raises(SystemExit):
            E.select_guard(["ckpt/v3/v3_r7_g995_s0_20m.zip"], em)
    st = tmp_path / "select.txt"
    assert E.picked_model(st) is None
    st.write_text("| 모델 | … |\n\n고른 모델: ckpt/v3/v3_r7_g995_s2_20m.zip\n", encoding="utf-8")
    assert E.picked_model(st) == "ckpt/v3/v3_r7_g995_s2_20m.zip"
    st.write_text("고른 모델: 없음 — GF·GE 자격을 넘은 모델이 없다\n", encoding="utf-8")
    assert E.picked_model(st) is None


@pytest.mark.skipif(not HAVE_CK, reason="ckpt 는 저장소에 없다")
def test_judge_table_shape(E, tmp_path):
    """작은 실제 판(스모크 시드 32096·32097 × 지역 셋 × 120 스텝, route0m5 대 route0)으로 judge 를 돌리면: 판정 표 = P1 + 지킴 18 칸(GE 포함, GR 없음),
    보고만 칸 = 도망 단위 숨음·잡힘 비율·GR (ok None), 셈 단위 'episode'. A5 를 주지 않으면 통과로 두지 않는다. 판정 실행기는 사건을 센다."""
    info = E.prepare_info(tmp_path)
    runs = {}
    for use in ("judge_n", "judge_g", "stuck"):
        plan = E.smoke_plan(use, [32096, 32097], 120)
        for who, m in (("candidate", "route0m5"), ("current", "route0")):
            runs[(use, who)] = E.run_model(info, m, plan, 6, name=f"t_{use}_{who}")
    N = dict(candidate=runs[("judge_n", "candidate")], current=runs[("judge_n", "current")])
    G = dict(candidate=runs[("judge_g", "candidate")], current=runs[("judge_g", "current")])
    S = dict(candidate=runs[("stuck", "candidate")], current=runs[("stuck", "current")])
    res = E.judge(N, G, S, None)
    assert list(res["criteria"]) == ["P1_N_hide", *E.GUARDS]
    assert list(res["report_criteria"]) == list(E.REPORT_KEYS) and all(v["ok"] is None for v in res["report_criteria"].values())
    assert res["unit"] == "episode" and res["criterion"] == E.lv.GATE_CRITERION
    assert res["verdict"] == "기각" and "A5_export" in res["failed"]
    ge = res["criteria"]["GE_episode_starts"]
    assert ge["diff"] == E.ge_pair(N["candidate"], N["current"])["diff"]
    p1 = res["criteria"]["P1_N_hide"]
    assert p1["diff"] == E.ep_pair(N["candidate"], N["current"], "hide")["diff"]
    assert res["report"]["gate"]["N"]["brain_flee"] == 0
    text = E.fmt_judge(res)
    assert "GE_episode_starts" in text and "| GR_reflee |" in text and "보고만" in text


def test_prereg_doc_numbers(E):
    """사전 등록 문서가 도구의 시드·문턱·두뇌 지문·커밋을 그대로 적는다(글자 확인)."""
    t = (R7E / "PREREG.md").read_text(encoding="utf-8")
    for s in ("38000~38099", "38000~38039", "38000~38004", "38200~38219", "38220~38239", "38100~38119", "38120~38139", "+1.984", "+2.023",
              "0xad7bad5e1acaf071", "4d33c18", "71e7612", "ed01894", "c65df22", "GE_episode_starts", "GR_reflee", "사람 결정 10-24"):
        assert s in t, s
    for v in E.R7_SHA1.values():
        assert v in t, v
