"""v3 R2 학습 준비 (명세 Docs/RL_Policy/RL_V3_R2_SPEC.md 10절 5~7단계).

학습 설정 configs/v3_r2.yaml(= v3_r1 + stare_down·alarm 두 블록 + version 3.r2, 판정 세계 v3_r2_on 과는 낮 고정 비율만 다르다 —
f_dec·ent_coef_base 는 다시 잰 값, 범주 엔트로피 계수 0.01), 관측 19·마스크 판 3 학습(train_v3, 학습 기록의 stare·look 니치 π),
U_STARE·U_LOOK 조건(eval_v3.XTerms = 손 규칙 XRule.mask 그대로), FSM_R2 정책, r2 판정 smoke(보고 지표·같은 순간 불일치·사전 등록
폴더 거부), 모방 초기화의 둘째 교사 fsm_r2(FREEZE 출처). 보호 파일(env_v2/*, repertoire_rules.py, 관문 도구, 판정·관문 설정)은
읽기만 한다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import json
import math

import numpy as np
import pytest
import yaml

import repertoire_rules as rr
from env.config import ROOT
from env_v2 import rep_policy as rp
from env_v2 import repertoire as rep
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.world import World, obs_names

V3R1 = ROOT / "configs" / "v3_r1.yaml"
V3R1_ON = ROOT / "configs" / "v3_r1_on.yaml"
V3R2 = ROOT / "configs" / "v3_r2.yaml"
V3R2_ON = ROOT / "configs" / "v3_r2_on.yaml"
G, F, H, Z, S = rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP
REMEASURED = ("f_dec", "ent_coef_base")        # R2 학습 전에 다시 잰 값(판정 설정에는 리드가 옮겨 적는다)

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def c2():
    return load_v2_config(V3R2)


@pytest.fixture(scope="module")
def c2_on():
    return load_v2_config(V3R2_ON)


def _ev():
    import eval_v3

    return eval_v3


def _obs(cfg, rows):
    """규칙 관측 행(test_r2_mechanics._rule_obs 와 같은 꼴 + beh_freeze·visibility·energy)."""
    names = list(obs_names(cfg))
    o = np.zeros((len(rows), len(names)), dtype=np.float32)
    for i, r in enumerate(rows):
        o[i, names.index("pred_count")] = r.get("pc", 0) / 8.0
        o[i, names.index("pred_dist")] = r.get("dist", 20.0) / cfg.see_r
        o[i, names.index("pred_approach")] = r.get("app", 0.5)
        o[i, names.index("cover_dist")] = r.get("cover", 20.0) / cfg.obs_cover_norm
        o[i, names.index("energy")] = r.get("energy", 0.8)
        o[i, names.index("visibility")] = r.get("vis", 1.0)
        o[i, names.index("beh_freeze")] = 1.0 if r.get("freeze_now") else 0.0
        o[i, names.index("beh_graze")] = 0.0 if r.get("freeze_now") else 1.0
        if "alarm_heard" in names:
            o[i, names.index("alarm_heard")] = r.get("alarm", 0.0)
            o[i, names.index("threat_recency")] = r.get("rec", 0.0)
    return o


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


def test_r2_train_config_is_r1_plus_two_blocks():
    """v3_r2 = v3_r1 + stare_down·alarm(판정 세계와 같은 값) + version 3.r2. train 블록은 목록·ε·시작 확률이 R1 그대로이고 f_dec·
    ent_coef_base 만 다시 쟀다(범주 엔트로피 계수 = ent_coef_base ÷ f_dec = 0.01, R1 조리법)."""
    a = yaml.safe_load(V3R2.read_text(encoding="utf-8"))
    b = yaml.safe_load(V3R1.read_text(encoding="utf-8"))
    on = yaml.safe_load(V3R2_ON.read_text(encoding="utf-8"))
    assert a["version"] == "3.r2" and b["version"] == "3.r1"
    assert {k: v for k, v in a["features"].items() if k not in ("stare_down", "alarm")} == b["features"]
    assert a["features"]["stare_down"] == on["features"]["stare_down"] and a["features"]["alarm"] == on["features"]["alarm"]
    assert a["overrides"] == b["overrides"]
    ta, tb = dict(a["train"]), dict(b["train"])
    ra, rb = dict(ta.pop("repertoire")), dict(tb.pop("repertoire"))
    assert ta == tb
    assert {k: v for k, v in ra.items() if k not in REMEASURED} == {k: v for k, v in rb.items() if k not in REMEASURED}
    assert ra["allowed"] == ["graze", "flee", "hide", "freeze"]             # SLEEP 은 그대로 빠진다
    assert abs(ra["ent_coef_base"] / ra["f_dec"] - 0.01) < 1e-9 and 0.0 < ra["f_dec"] <= 1.0
    p = rp.rep_params(load_v2_config(V3R2))
    assert p["cat_ent_coef"] == pytest.approx(0.01, rel=1e-9)


def test_r2_train_and_judge_worlds_differ_only_in_fixed_day():
    """학습·판정 세계는 낮 고정 비율(0.2 ↔ 0)만 다르다. 다시 잰 f_dec·ent_coef_base 는 판정 설정에 옮겨 적기 전에는 다를 수 있다
    (판정 도구는 목록만 읽는다)."""
    a = yaml.safe_load(V3R2.read_text(encoding="utf-8"))
    b = yaml.safe_load(V3R2_ON.read_text(encoding="utf-8"))
    assert a["features"]["daynight"].pop("fixed_day_frac") == 0.2
    assert b["features"]["daynight"].pop("fixed_day_frac") == 0.0
    for d in (a, b):
        for k in REMEASURED:
            d["train"]["repertoire"].pop(k)
    assert a == b


def test_r2_train_world_obs_and_mask_version(c2):
    w = World(c2, seeds=[0])
    assert w.obs_dim == 19 and w.obs_names[-1] == "alarm_heard"
    assert rp.mask_version_of(w.obs_names) == rp.MASK_VERSION_ALARM == 3


# --------------------------------------------------------------------- #
# U_STARE·U_LOOK 조건, FSM_R2
# --------------------------------------------------------------------- #


def test_xterms_are_rule_masks(c2_on):
    """XTerms = repertoire_rules.XRule.mask(x_wrap 스펙) 그대로. stare 니치는 유지 줄 포함, stare_band 는 유지 줄 없음(교차는 같다)."""
    ev = _ev()
    rows = [dict(pc=1, dist=8.0, app=0.65),                     # 0 stare 띠
            dict(pc=1, dist=7.0, app=0.5, freeze_now=True),     # 1 유지 줄(멈춘 대치)
            dict(pc=1, dist=7.0, app=0.5),                      # 2 FREEZE 가 아니면 유지 줄이 아니다
            dict(pc=1, dist=9.0, app=0.5),                      # 3 stare 교차(거리 ≥ 8 & 접근 < 0.6)
            dict(pc=1, dist=3.0, app=0.65),                     # 4 너무 가깝다(4 이하)
            dict(alarm=0.5),                                    # 5 look 니치(안 보임, 강한 경보, 개활지)
            dict(alarm=0.5, cover=3.0),                         # 6 은신처 가까움 → look 니치 아님
            dict(alarm=0.3),                                    # 7 look 교차(약한 경보)
            dict(),                                             # 8 아무것도 아님
            dict(pc=1, dist=9.0, app=0.5, freeze_now=True)]     # 9 유지 줄과 교차가 겹친다(사전 등록 정의 그대로)
    o = _obs(c2_on, rows)
    t = ev.XTerms(c2_on)(o)
    assert set(t) == {"stare", "stare_band", "look"}
    np.testing.assert_array_equal(t["stare"][0], [1, 1, 0, 0, 0, 0, 0, 0, 0, 1])
    np.testing.assert_array_equal(t["stare_band"][0], [1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    np.testing.assert_array_equal(t["stare"][1], [0, 0, 0, 1, 0, 0, 0, 0, 0, 1])
    np.testing.assert_array_equal(t["stare_band"][1], t["stare"][1])
    assert not (t["stare_band"][0] & t["stare_band"][1]).any()            # 띠만의 니치는 교차와 겹치지 않는다
    np.testing.assert_array_equal(t["look"][0], [0, 0, 0, 0, 0, 1, 0, 0, 0, 0])
    np.testing.assert_array_equal(t["look"][1], [0, 0, 0, 0, 0, 0, 0, 1, 0, 0])
    g = np.full(len(o), G)
    for x in ("stare", "look"):
        for i, mode in enumerate(("niche", "cross")):
            np.testing.assert_array_equal(t[x][i], rr.XRule(None, rr.x_wrap(c2_on, x, mode)).mask(o, g))
    assert "look" not in ev.XTerms(load_v2_config(V3R1_ON)).rules         # 경보 칸이 없으면 look 을 내지 않는다


def test_u_terms_r2_and_active_u(c2_on):
    ev = _ev()
    o = _obs(c2_on, [dict(pc=1, dist=3.0, app=0.95, cover=0.0), dict(pc=1, dist=9.0, app=0.5), dict(alarm=0.5)])
    f = rr.features_of_obs(o, rr._geom(c2_on))
    t2, t1b = ev.u_terms(f, "near", "r2"), ev.u_terms(f, "near", "r1b")
    assert set(t2) == set(t1b)
    for k in t2:
        np.testing.assert_array_equal(t2[k][0], t1b[k][0])
        np.testing.assert_array_equal(t2[k][1], t1b[k][1])
    allowed = ("graze", "flee", "hide", "freeze")
    # 판정 U 는 U_STARE·U_LOOK_OPEN(FREEZE 가 열린 결정만 센 look). 글자 그대로의 U_LOOK·U_STARE_BAND 는 보고만
    assert ev.active_u(allowed, "r2") == ("esc", "hide", "freeze", "stare", "look_open")
    assert ev.active_u(allowed) == ("esc", "hide", "freeze")                # r1 그대로
    assert ev.active_u(("graze", "flee", "hide"), "r2") == ("esc", "hide")
    assert ev.u_names("r2") == ev.U_NAMES + ("stare", "look", "look_open", "stare_band") and ev.u_names("r1b") == ev.U_NAMES
    assert set(ev.U_MIN_BY["r2"]) == {"esc", "hide", "freeze", "sleep", "stare", "look_open"}
    assert ev.R2_ALARM == rr.NICHES["look"]["alarm"] == rp.ALARM_MASK_OBS
    assert ev.REF_FSM == {"r1": "fsm", "r1b": "fsm", "r2": "fsm_r2"}


def test_fsm_r2_policy(c2_on):
    """fsm_r2 = repertoire_rules.fsm_r2_spec(켠 장치의 줄). 장치가 없는 세계(v3_r1_on)에서는 R1 FSM(near)과 같은 결정이다."""
    ev = _ev()
    allowed = ("graze", "flee", "hide", "freeze")
    assert ev.has_r2_world(c2_on) == (True, True)
    spec = ev.policy_spec("fsm_r2", "unused.zip", c2_on, allowed, "near")["build"]
    assert spec == rr.fsm_r2_spec(c2_on, allowed)
    rows = [dict(pc=1, dist=8.0, app=0.65, cover=3.0), dict(pc=1, dist=8.0, app=0.65), dict(pc=1, dist=3.0),
            dict(alarm=0.5), dict(pc=1, dist=8.0, app=0.95), dict(pc=1, dist=8.0, app=0.5, freeze_now=True), dict()]
    out = ro.build_policy(spec, 0)(_obs(c2_on, rows))[:, 0].astype(int).tolist()
    assert out == [H, Z, Z, Z, Z, Z, G]
    c1 = load_v2_config(V3R1_ON)
    assert ev.has_r2_world(c1) == (False, False)
    rng = np.random.default_rng(0)
    o1 = World(c1, seeds=[10001]).observe()
    o1 = np.concatenate([o1, rng.random((64, o1.shape[1])).astype(np.float32)])
    a = ro.build_policy(ev.fsm_r2_policy_spec(c1, allowed), 0)(o1)
    b = ro.build_policy(ev.fsm_spec(c1, allowed, "near"), 0)(o1)
    np.testing.assert_array_equal(a, b)


# --------------------------------------------------------------------- #
# 학습·판정·모방 초기화 smoke
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def trained_r2(tmp_path_factory):
    """train_v3 를 R2 학습 세계에서 롤아웃 한 번(32,768 스텝) 돌린다."""
    import train_v3

    d = tmp_path_factory.mktemp("v3_r2_train")
    out = d / "smoke_r2.zip"
    assert train_v3.main(["--config", str(V3R2), "--steps", "20000", "--seed", "0", "--out", str(out),
                          "--tb", str(d / "tb"), "--every", "16384"]) == 0
    return out, json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))


def test_train_v3_r2_smoke(trained_r2):
    from stable_baselines3 import PPO

    out, meta = trained_r2
    assert meta["u_def"] == "r2" and meta["mask_version"] == 3 and meta["obs_names"][-1] == "alarm_heard"
    assert meta["cat_ent_coef"] == pytest.approx(0.01, rel=1e-9) and meta["gamma"] == 0.995
    assert PPO.load(out, device="cpu").policy.rep_mask_version == 3
    r = meta["log_history"][-1]
    for k in ("pi_flee_niche", "pi_hide_niche", "pi_freeze_niche", "pi_stare_niche", "pi_stare_base", "pi_look_niche",
              "pi_look_base", "pi_stare_band_niche", "n_stare_niche", "n_look_niche", "pi_look_open_niche",
              "pi_look_open_base", "n_look_open_base"):
        assert k in r, k
    assert r["use_sleep"] == 0.0


def test_niche_probs_r1_keys_unchanged(c2_on):
    """r1 정의(xterms 없음)의 학습 기록 칸은 R2 전과 같다. r2 는 stare·look 칸을 더한다."""
    import train_v3

    ev = _ev()
    o = _obs(c2_on, [dict(pc=1, dist=8.0, app=0.65), dict(alarm=0.5), dict(pc=1, dist=9.0, app=0.5), dict(alarm=0.3)])
    pi = np.tile([0.4, 0.2, 0.2, 0.2, 0.0], (len(o), 1))
    geo, allowed = rr._geom(c2_on), ("graze", "flee", "hide", "freeze")
    r1 = train_v3.niche_probs(pi, o, geo, allowed, "near")
    assert set(r1) == {f"pi_{x}_{s}" for x in ("flee", "hide", "freeze", "esc") for s in ("niche", "base")}
    r2 = train_v3.niche_probs(pi, o, geo, allowed, "near", "r2", ev.XTerms(c2_on))
    assert r2["pi_stare_niche"] == pytest.approx(0.2) and r2["n_stare_niche"] == 1 and r2["n_look_niche"] == 1
    assert r2["n_stare_base"] == 1 and r2["n_look_base"] == 1


def test_eval_r2_smoke_and_guards(trained_r2, tmp_path, c2_on):
    ev = _ev()
    out, _ = trained_r2
    res = ev.judge(str(out), "smoke", [20000, 20001], 150, tmp_path, config=ev.CONFIG_R2, tail=50, workers=1, udef="r2")
    P = res["pooled"]
    assert set(P) == set(ev.R2_POLICIES)
    for name, v in P.items():
        assert math.isfinite(v["g_gamma"]), name
        assert set(v["u"]) == set(ev.U_NAMES_R2), name
        assert set(v["visible"]) >= {"stare", "alarm", "threats", "non_graze"}, name
        assert v["r2"]["kind_miss"] == 0, name                       # 다시 계산한 가장 가까운 위협 = 관측
        assert set(v["r2"]["by_kind"]) == set(ev.R2_KINDS)
    # 같은 순간 불일치: 손 규칙은 자기 자신과 늘 같다
    assert P["fsm_r2"]["r2"]["disagree"]["fsm_r2"] in (0.0, None) and P["rbase"]["r2"]["disagree"]["rbase"] in (0.0, None)
    # U_LOOK_OPEN: look 조건 & FREEZE 열림. 닫힌 칸은 고를 수 없으니 늘 U_LOOK_OPEN ≤ U_LOOK, 늘 얼기는 열린 결정에서 늘 FREEZE 라
    # U_LOOK_OPEN 이 정확히 0 이다(글자 그대로의 U_LOOK 은 교차의 마스크만으로 커진다 — 판정 사전 등록 3절)
    for name, v in P.items():
        c = v["u_cnt"]
        assert c["look_open"][0] <= c["look"][0] and c["look_open"][2] <= c["look"][2], name
        assert c["look_open"][1] == c["look"][1] and c["look_open"][3] == c["look"][3], name    # FREEZE 는 열렸을 때만 나온다
        if v["u"]["look_open"] is not None and v["u"]["look"] is not None:
            assert v["u"]["look_open"] <= v["u"]["look"] + 1e-12, name
        # 홉별 반응: 안 보이는 결정 표본 = 홉 칸의 합 + 뺀 표본(관측에 경보가 있는데 훅이 없음)
        hm = v["r2"]["hop_miss"]
        assert sum(b["n"] for b in v["r2"]["by_hop"].values()) + hm["dropped"] == c["esc"][2], name
        assert hm["dropped"] <= hm["n"]
    cf = P["c_freeze"]["u_cnt"]["look_open"]
    assert cf[1] == cf[0] and cf[3] == cf[2]
    assert set(P) >= {"c_flee", "c_hide", "c_freeze", "rbase_wr2"}
    assert res["perf_rbase_wr2"] is not None and res["meta"]["approach_wr2"] == ev.APPROACH_WR2
    G_ = res["gate"]
    assert set(G_["u"]["items"]) == {"esc", "hide", "freeze", "stare", "look_open"} and G_["dep"]["items"] == {}
    assert G_["perf"]["ref"] == "fsm_r2" and G_["starve"]["fsm"] == P["fsm_r2"]["starve_rate"]
    assert G_["pending"] == any(v is None for k, v in ev.U_MIN_BY["r2"].items() if k != "sleep")
    assert res["meta"]["u_def"] == "r2" and res["meta"]["ref_fsm"] == "fsm_r2" and not res["meta"]["prereg"]
    md = (tmp_path / "smoke.md").read_text(encoding="utf-8")
    assert "v3 R2 판정" in md and "같은 순간 불일치" in md and "홉별 반응" in md
    assert "v3 R2 판정 모음" in ev.summarize(["smoke"], tmp_path)
    assert "v3 R2 판정 모음" in ev.summarize(["smoke"], tmp_path, "r2")
    with pytest.raises(ValueError, match="지표 정의"):                    # R2 결과를 r1 로 모으지 않는다
        ev.summarize(["smoke"], tmp_path, "r1")
    (tmp_path / "done.flag").write_text("", encoding="utf-8")               # 닫힌 폴더: 같은 내용이면 그대로, 바뀌면 멈춘다
    ev.summarize(["smoke"], tmp_path, "r2")
    (tmp_path / "judge.md").write_text("old\n", encoding="utf-8")
    with pytest.raises(ValueError, match="닫힌"):
        ev.summarize(["smoke"], tmp_path, "r2")
    assert (tmp_path / "judge.md").read_text(encoding="utf-8") == "old\n"
    # 니치 π 측정(조기 중단 점검): 판정 롤아웃과 같은 궤적(argmax) — 결정 표본 수가 eval 의 rl 과 같다
    import train_v3

    mp = train_v3.measure_pi(c2_on, str(out), seeds=[20000], steps=150)
    rl0 = [r for r in res["per_seed"]["rl"] if r["seed"] == 20000][0]
    assert mp["u_def"] == "r2" and mp["n_dec"] == rl0["n_dec"]
    for k in ("pi_flee_niche", "pi_hide_niche", "pi_freeze_niche", "pi_stare_niche", "pi_look_niche", "pi_look_open_base",
              "pi_stare_band_niche"):
        assert k in mp["pooled"], k
    assert mp == train_v3.measure_pi(c2_on, str(out), seeds=[20000], steps=150)       # 난수 없음
    # r2 는 R2 세계(노려보기·경보)에서만, 기준 손 규칙(fsm_r2)이 꼭 있어야 한다
    with pytest.raises(ValueError, match="R2 세계"):
        ev.judge(str(out), "x", [20000], 10, tmp_path, config=ev.CONFIG, udef="r2", workers=1)
    with pytest.raises(ValueError, match="fsm_r2"):
        ev.judge(str(out), "x", [20000], 10, tmp_path, config=ev.CONFIG_R2, udef="r2", workers=1, policies=["rl", "fsm"])
    # 사전 등록 폴더: --u-def r2 의 기본 --out 은 R2 판정 폴더이고 다른 조건이면 시작 전에 멈춘다. R1 폴더는 r2 를 받지 않는다
    with pytest.raises(SystemExit):
        ev.main(["run", "--u-def", "r2", "--model", str(out), "--name", "x", "--seeds", "10200", "--steps", "10"])
    with pytest.raises(SystemExit):
        ev.main(["run", "--u-def", "r2", "--model", str(out), "--name", "x", "--out", str(ev.PREREG_OUT)])
    assert not (ev.PREREG_OUT_R2 / "x.json").exists() and not (ev.PREREG_OUT / "x.json").exists()


def test_prereg_r2_conditions():
    """R2 판정 폴더 조건(모듈 docstring): 시드 10200~10219 × 10000, v3_r2_on, tail 600, 정책 모두, near, r2, 문턱 확정, PREREG.md."""
    import argparse

    ev = _ev()
    a = argparse.Namespace(steps=ev.STEPS, config=ev.CONFIG_R2, tail=ev.TAIL, policies=None, freeze_variant="near", u_def="r2")
    bad = ev.prereg_problems_r2(a, ev.EVAL_SEEDS_R2)
    pending = any(ev.U_MIN_BY["r2"][u] is None for u in ("esc", "hide", "freeze", "stare", "look_open"))
    pr = ev.PREREG_OUT_R2 / "PREREG.md"
    draft = pr.exists() and ev.prereg_draft(pr)
    assert any("문턱 미정" in b for b in bad) == pending
    assert any("이 없다" in b for b in bad) == (not pr.exists())
    assert any("초안" in b for b in bad) == draft                          # 초안이면 판정 폴더 실행을 받지 않는다
    assert len(bad) == int(pending) + int(not pr.exists()) + int(draft)
    assert ev.EVAL_SEEDS_R2 == list(range(10200, 10220)) and ev.CONFIG_R2 == "configs/v3_r2_on.yaml"
    a2 = argparse.Namespace(steps=3000, config=ev.CONFIG, tail=100, policies=["rl"], freeze_variant="orig", u_def="r1b")
    assert len(ev.prereg_problems_r2(a2, [20000])) >= 7


@pytest.mark.filterwarnings("ignore::RuntimeWarning", "ignore:Converting a tensor")
def test_warmstart_teacher2(c2, monkeypatch):
    """둘째 교사: 기본 fsm(R1 그대로 — 자료·통계 키가 R1 과 같다), fsm_r2 는 FSM_R2 이고 FREEZE 마다 출처(가까운 판·stare 띠·유지
    줄·look)를 적는다. 출처 수의 합 = FSM_R2 의 FREEZE 수."""
    import warmstart_v3 as ws

    r1 = ws.collect(load_v2_config(V3R1), n_worlds=2, steps=120)
    assert "p_src2" not in r1["data"] and "teacher2" not in r1["stats"] and "freeze_src_fsm" not in r1["stats"]
    res = ws.collect(c2, n_worlds=2, steps=200, teacher2="fsm_r2")
    st, d = res["stats"], res["data"]
    assert st["teacher2"] == "fsm_r2" and st["obs_dim"] == 19 and st["teacher_invalid"] == 0
    assert d["p_src2"].shape == d["p_act2"].shape and d["p_obs"].shape[1] == 19 + rep.N_BEHAVIORS
    assert sum(st["freeze_src_fsm"].values()) == st["counts_fsm"][Z] == int(np.count_nonzero(d["p_act2"] == Z))
    assert np.all((d["p_src2"] > 0) == (d["p_act2"] == Z))
    assert ws.teacher2_spec(c2, ("graze", "flee", "hide", "freeze"), "fsm_r2") == rr.fsm_r2_spec(c2)
    with pytest.raises(ValueError, match="teacher2"):
        ws.teacher2_spec(c2, ("graze", "flee"), "rbase")
    # 맞추기: 자료가 다른 설정(관측 18)이면 멈춘다. 같은 설정이면 판 3 모델이고 출처별 보류 π 를 낸다
    with pytest.raises(ValueError, match="관측"):
        ws.fit(load_v2_config(V3R1), d, 0, epochs=1)
    monkeypatch.setattr(ws, "VALUE_DROP", 50)
    res = ws.collect(c2, n_worlds=2, steps=200, teacher2="fsm_r2")
    model, fr = ws.fit(c2, res["data"], 0, epochs=1)
    assert model.policy.rep_mask_version == 3
    assert set(fr["history"][-1]["recall_src"]) == set(ws.SRC_NAMES.values())


def test_prereg_draft_title(tmp_path):
    ev = _ev()
    p = tmp_path / "PREREG.md"
    p.write_text("# v3 R2 판정 사전 등록 (초안 — 학습 기록을 보기 전에 리드가 확정)\n\n본문의 초안은 보지 않는다\n", encoding="utf-8")
    assert ev.prereg_draft(p)
    p.write_text("# v3 R2 판정 사전 등록 (확정 10-13)\n\n변경 기록: 초안을 확정했다\n", encoding="utf-8")
    assert not ev.prereg_draft(p)


def test_look_open_terms_and_rbase_wr2(c2_on):
    """U_LOOK_OPEN 조건 = look 조건 & 마스크의 FREEZE 칸. rbase_wr2 = R_base(θ 4, a 0.6)(합친 세계 거주 탐색값)."""
    ev = _ev()
    o = _obs(c2_on, [dict(alarm=0.5), dict(alarm=0.3, rec=0.5), dict(alarm=0.3), dict()])
    look = ev.XTerms(c2_on)(o)["look"]
    m = rp.feasible_mask(o, obs_names(c2_on))                  # 판 3: 경보 ≥ 0.4 이거나 threat_recency ≥ 0.2 면 FREEZE 열림
    np.testing.assert_array_equal(m[:, Z], [1, 1, 0, 0])
    a, b = ev.look_open_terms(look, m)
    np.testing.assert_array_equal(look[0], [1, 0, 0, 0])
    np.testing.assert_array_equal(look[1], [0, 1, 1, 0])
    np.testing.assert_array_equal(a, [1, 0, 0, 0])
    np.testing.assert_array_equal(b, [0, 1, 0, 0])            # 교차 중 FREEZE 가 닫힌 결정은 빠진다
    allowed = ("graze", "flee", "hide", "freeze")
    assert ev.policy_spec("rbase_wr2", "unused.zip", c2_on, allowed, "near")["build"] == rr.rule_spec(c2_on, 4.0, 0.6)
    assert (ev.THETA, ev.APPROACH) == (4.0, 0.9) and (ev.THETA_WR2, ev.APPROACH_WR2) == (4.0, 0.6)
    s = ROOT / "results" / "v3" / "r2" / "wr2" / "search.json"
    if s.exists():
        best = json.loads(s.read_text(encoding="utf-8"))["best"]
        assert (best["theta"], best["approach"]) == (ev.THETA_WR2, ev.APPROACH_WR2)
    assert "rbase_wr2" in ev.R2_POLICIES and {"c_flee", "c_hide", "c_freeze"} <= set(ev.R2_POLICIES)


def test_warmstart_defaults(c2):
    """--teacher2·--out-dir·--name 기본: R2 세계면 fsm_r2·ckpt/v3/ws_r2·v3_r2_ws, R1 세계면 fsm·ckpt/v3/ws·v3_r1_ws(R1 재현)."""
    import warmstart_v3 as ws

    c1 = load_v2_config(V3R1)
    assert ws.default_teacher2(c2) == "fsm_r2" and ws.default_teacher2(c1) == "fsm"
    assert ws.default_out_dir(c2) == ws.OUT_R2 and ws.default_out_dir(c1) == ws.OUT
    assert ws.default_name(c2) == "v3_r2_ws" and ws.default_name(c1) == "v3_r1_ws"
