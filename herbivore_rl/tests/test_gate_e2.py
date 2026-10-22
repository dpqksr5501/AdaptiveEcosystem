"""V2 1-5 Gate E2 도구 (`gate_e2.py`) — 후보 설정(감쇠·보정 계수), 구간 정의(관측 7 의 [θ, 1]), 명령 구성, 판정 규칙
(E2a A·B 갈래, E2b, #18), 후보 선택, 보정 규칙 (results/v2/e2/PREREG.md).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import json
import math

import numpy as np
import pytest
import yaml

import gate_e2 as G
from env.config import ROOT
from env_v2.config import load_v2_config
from env_v2.rollout import segment_ids
from env_v2.world import RECENT_THREAT, World

V2_2 = ROOT / "configs" / "v2_2.yaml"


# --------------------------------------------------------------------- #
# 후보·설정
# --------------------------------------------------------------------- #


def test_candidates_theta_and_windows():
    """감쇠 후보 {0.9, 0.95, 0.975}(반감기 6.6/13.5/27.4스텝), θ 0.5 = world.RECENT_THREAT. θ 에서 놓친 뒤 최근 위협에
    머무는 스텝 수 K = 6/13/27 (decay^K ≥ θ > decay^(K+1))."""
    assert G.DECAYS == (0.9, 0.95, 0.975) and G.PROPOSAL_DECAY in G.DECAYS
    assert G.THETA == RECENT_THREAT == 0.5
    assert [G.window_steps(d) for d in G.DECAYS] == [6, 13, 27]
    for d in G.DECAYS:
        k = G.window_steps(d)
        assert d ** k >= G.THETA > d ** (k + 1)
        assert np.float32(d ** k) != np.float32(G.THETA)           # 같음 경계가 없다(digitize ≥ 와 world > 가 같다)
    assert [G.cand_name(d) for d in G.DECAYS] == ["d0_9", "d0_95", "d0_975"]
    assert G.decay_of("d0_975") == 0.975
    with pytest.raises(ValueError):
        G.decay_of("d0_5")


def test_round_config_changes_only_vigilance_coefficients(tmp_path):
    """회차·후보 설정 = configs/v2_2.yaml 에서 vigilance 의 decay·eat_mult·threat_flee 만 다르다."""
    base = load_v2_config(V2_2).to_dict()
    for rnd, eat in (("V0", 0.0), ("V1", 0.5)):
        for d in G.DECAYS:
            for tf in (0.0, G.THREAT_FLEE_VARIANT):
                p = G.write_config(rnd, d, tmp_path, tf)
                assert p == G.config_path(rnd, d, tmp_path, tf)
                c = copy.deepcopy(load_v2_config(p).to_dict())
                vg = c["v2"]["features"]["vigilance"]
                assert (vg["decay"], vg["eat_mult"], vg["threat_flee"]) == (d, eat, tf)
                for k in ("decay", "eat_mult", "threat_flee"):
                    vg[k] = base["v2"]["features"]["vigilance"][k]
                assert c == base
    assert G.config_path("V0", 0.95, tmp_path, 1.0).name == "V0_d0_95_tf1.yaml"
    with pytest.raises(NotImplementedError):                    # V2 의 반경 배수는 아직 구현하지 않았다
        G.write_config("V2", 0.95, tmp_path)
    with pytest.raises(ValueError):
        G.write_config("V0", 0.8, tmp_path)


def test_write_config_does_not_overwrite(tmp_path):
    p = G.write_config("V0", 0.9, tmp_path)
    assert G.write_config("V0", 0.9, tmp_path) == p              # 같은 내용이면 그대로
    p.write_text(p.read_text(encoding="utf-8") + "\n# 손으로 고침\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        G.write_config("V0", 0.9, tmp_path)


def test_e1b_c2_start_matches_judge():
    """C2 시작점의 E1-b C2 = results/v2/e1/judge_e1b.json 의 최종 C2 (float64 그대로)."""
    final = json.loads((ROOT / "results" / "v2" / "e1" / "judge_e1b.json").read_text(encoding="utf-8"))["final"]
    assert list(G.E1B_C2) == final["c2"]
    assert all(len(v) == G.ACT_DIM for v in G.C2_ENQUEUE)
    assert all(v[G.A_VIG] == G.VIG_OFF_START < 0.5 for v in G.C2_ENQUEUE)


# --------------------------------------------------------------------- #
# 구간: 관측 7 의 [θ, 1] = {평시, 최근 위협·안 보임, 포식자 보임}
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("decay", G.DECAYS)
def test_segments_match_seen_recent_calm(decay, tmp_path):
    """C2-seg 구간(관측 7 문턱 [θ, 1])이 계획서 1-5 구간과 같다: 2 ⇔ 포식자 보임(관측 1 > 0), 1 ⇔ 안 보임 &
    threat_recency > θ, 0 ⇔ 그 밖. 경계를 섞는 상수로 리스폰을 포함해 1500스텝 본다."""
    from diagnose_v2 import parse_bins
    cfg = load_v2_config(G.write_config("V0", decay, tmp_path))
    w = World(cfg, seeds=[10000])
    bins = parse_bins([G.SEG_BIN], list(w.obs_names))
    assert bins == [[7, [0.5, 1.0]]]
    n = {0: 0, 1: 0, 2: 0}
    for t in range(1500):
        o = w.observe()
        s = segment_ids(o, bins)
        seen = o[:, 1] > 0
        assert ((o[:, 7] >= 1.0) == seen).all()
        recent = ~seen & (w.threat > G.THETA)
        np.testing.assert_array_equal(s, np.where(seen, 2, recent.astype(int)))
        for k in n:
            n[k] += int((s == k).sum())
        a = np.tile([0.4, 0.8, 0.4, 0.1, 0.9, 0.0], (w.N, 1))
        a[:, 5] = (np.arange(w.N) + t) % 4 == 0
        w.step(a)
    assert min(n.values()) > 0


def test_constants_do_not_depend_on_decay(tmp_path):
    """상수 정책의 세계(G_γ·결과)는 감쇠와 무관하다(감쇠는 관측 7 과 통계만 바꾼다, threat_flee 0). 그래서 C2 는 회차마다
    한 번 찾는다(PREREG 2절)."""
    from env_v2 import rollout as ro
    rows = []
    for d in G.DECAYS:
        cfg = load_v2_config(G.write_config("V0", d, tmp_path))
        pol = ro.build_policy({"kind": "fixed", "action": [0.97, 0.78, 0.22, 0.03, 0.49, 0.25]})
        rows.append(ro.rollout(cfg, pol, 10001, 900))
    for r in rows[1:]:
        for c in ("g_gamma", "mean_return", "survival", "predation_rate", "starve_rate", "walk_frac", "b1", "b2"):
            assert r[c] == rows[0][c] or (math.isnan(r[c]) and math.isnan(rows[0][c])), c
    assert rows[0]["seg_recent_frac"] < rows[2]["seg_recent_frac"]  # 통계의 '최근 위협'은 감쇠를 따른다


# --------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------- #


def _arg(a, flag, n):
    i = a.index(flag)
    return a[i + 1:i + 1 + n]


def test_c2_commands_follow_prereg(tmp_path):
    steps = G.c2_commands(tmp_path / "c.yaml", tmp_path / "c2", 18)
    assert [s for s, _ in steps] == ["constsearch"]
    a = steps[0][1]
    assert a.count("--enqueue") == 3 and "--seg-bins" not in a and "--trials" not in a
    i = a.index("--enqueue")
    assert [float(x) for x in a[i + 1:i + 7]] == list(G.E1B_C2) + [0.25]


def test_cand_commands_follow_prereg(tmp_path):
    cfg, tf, d = tmp_path / "c.yaml", tmp_path / "c_tf1.yaml", tmp_path / "d"
    assert G.cand_commands(cfg, tf, d, 6) == []
    c2 = [0.9, 0.8, 0.2, 0.05, 0.45, 0.2]
    steps = G.cand_commands(cfg, tf, d, 6, c2)
    stems = [s for s, _ in steps]
    assert stems == ["a_forbid", "a_allow", "b_forbid", "e2b_vig", "e2b_run", "tf/e2b_run18", "g998/a_forbid",
                     "g998/e2b_vig", "g998/e2b_run"]
    S = dict(steps)
    assert [float(x) for x in _arg(S["a_forbid"], "--const-action", 6)] == c2[:5] + [0.0]
    for stem, dims in (("a_allow", ["vigilance"]), ("b_forbid", ["speed"])):
        a = S[stem]
        assert _arg(a, "--seg-bins", 1) == ["threat_recency:0.5,1"]
        assert a[a.index("--seg-dims") + 1:a.index("--base-action")] == dims
        assert "--const-action" not in a and "--enqueue" not in a       # 탐색 (C2 자체 시작점 = 도구 기본값)
    assert [float(x) for x in _arg(S["a_allow"], "--base-action", 6)] == c2
    assert [float(x) for x in _arg(S["b_forbid"], "--base-action", 6)] == c2[:5] + [0.0]
    for arm, s1 in (("vig", [0.45, 1.0]), ("run", [1.0, 0.0])):
        a = S[f"e2b_{arm}"]
        assert [float(x) for x in _arg(a, "--base-action", 6)] == [0.9, 0.8, 1.0, 0.05, 0.45, 0.0]
        assert [float(x) for x in _arg(a, "--const-action", 6)] == [0.45, 0.0, *s1, 1.0, 0.0]
    r18 = S["tf/e2b_run18"]
    assert _arg(r18, "--config", 1) == [G.rel(tf)] and _arg(r18, "--out", 1) == [G.rel(d / "tf")]
    assert _arg(r18, "--const-action", 6) == _arg(S["e2b_run"], "--const-action", 6)
    assert all(_arg(a, "--config", 1) == [G.rel(cfg)] for s, a in steps if not s.startswith("tf/"))
    assert all("--g998" in a and _arg(a, "--out", 1) == [G.rel(d / "g998")] for s, a in steps if s.startswith("g998/"))

    bf, ba, aa = [0.1, 0.5, 0.9], [0.1, 0.0, 0.5, 0.9, 0.9, 0.0], [0.1, 0.9, 0.2]
    steps = G.cand_commands(cfg, tf, d, 6, c2, aa, bf, ba)
    S = dict(steps)
    assert [s for s, _ in steps] == ["a_forbid", "a_allow", "b_forbid", "b_allow", "e2b_vig", "e2b_run",
                                     "tf/e2b_run18", "e2b_tab_vig", "e2b_tab_run", "g998/a_forbid", "g998/a_allow",
                                     "g998/b_forbid", "g998/b_allow", "g998/e2b_vig", "g998/e2b_run"]
    b = S["b_allow"]
    assert b[b.index("--seg-dims") + 1:b.index("--base-action")] == ["speed", "vigilance"]
    i = b.index("--enqueue")
    assert [float(x) for x in b[i + 1:i + 7]] == [0.45, 0.2] * 3                     # C2 자체
    j = b.index("--enqueue", i + 1)
    assert [float(x) for x in b[j + 1:j + 7]] == [0.1, 0.2, 0.5, 0.2, 0.9, 0.2]     # B-금지 최적 + C2 경계값
    assert [float(x) for x in _arg(S["e2b_tab_vig"], "--const-action", 6)] == [0.1, 0.0, 0.5, 1.0, 0.9, 0.0]
    assert [float(x) for x in _arg(S["e2b_tab_run"], "--const-action", 6)] == [0.1, 0.0, 1.0, 0.0, 0.9, 0.0]
    assert [float(x) for x in _arg(S["g998/a_allow"], "--const-action", 3)] == aa
    assert [float(x) for x in _arg(S["g998/b_allow"], "--const-action", 6)] == ba
    # 판정 실행에는 탐색·평가 조건 인자가 없다(diagnose_v2 기본값 = PREREG 2절)
    assert not any(a in sum((x for _, x in steps), []) for a in ("--trials", "--eval-steps", "--search-steps",
                                                                 "--eval-seeds"))
    smoke = G.cand_commands(cfg, tf, d, 6, c2, smoke=True)
    assert "--trials" in dict(smoke)["a_allow"] and "--eval-steps" in dict(smoke)["e2b_vig"]


def test_e2b_tables_differ_only_in_recent_segment():
    c2 = [0.9, 0.8, 0.2, 0.05, 0.45, 0.2]
    v, r = G.e2b_table(c2, "vig"), G.e2b_table(c2, "run")
    assert v[:2] == r[:2] and v[4:] == r[4:] and v[2:4] != r[2:4]
    assert v[3] > 0.5 >= r[3] and r[2] >= 2 / 3 and v[4] >= 2 / 3 and v[0] == c2[4]
    with pytest.raises(ValueError):
        G.e2b_table(c2, "stop")
    with pytest.raises(ValueError):
        G.tab_table([0.1, 0.2], "vig")


# --------------------------------------------------------------------- #
# 판정
# --------------------------------------------------------------------- #

NAMES = ["forage", "cohesion", "flee_dist", "cover", "speed", "vigilance"]
SEEDS = list(range(10000, 10020))


def _rows(g, pred=None, **cols):
    rng = np.random.default_rng(int(abs(g[0]) * 1000) % 7)
    gs = np.linspace(*g, len(SEEDS))
    ps = np.full(len(SEEDS), 0.002) if pred is None else np.linspace(*pred, len(SEEDS)) + rng.normal(0, 1e-6, 20)
    return [{"seed": s, "g_gamma": float(x), "predation_rate": float(p), "survival": 400.0, "repro": 15.0,
             "starve_rate": 0.0004, "mean_return": 100.0, **cols} for s, x, p in zip(SEEDS, gs, ps)]


def _res(kind, rows, best, vig_frac=0.1, dims=None, table=None, base=None):
    means = {c: float(np.mean([r[c] for r in rows])) for c in G.OUTCOME_COLS}
    means["vig_frac"] = vig_frac
    d = {"kind": kind, "best": best, "meta": {"act_names": NAMES}, "eval": {"mean": means},
         "per_seed": {kind: rows}}
    if kind == "C2-seg":
        d.update(dims=dims, best_table=table, base_action=base)
    return d


C2 = [0.9, 0.8, 0.2, 0.05, 0.45, 0.2]


def _a_pair(allow_g=(2.0, 2.2), vig=(0.1, 0.9, 0.2), vig_frac=0.1):
    forbid = _res("C2", _rows((1.0, 1.1)), C2[:5] + [0.0], vig_frac=0.0)
    allow = _res("C2-seg", _rows(allow_g), list(vig), vig_frac=vig_frac, dims=[5], table=[[v] for v in vig],
                 base=C2)
    return allow, forbid


def test_judge_e2a_pass_and_each_criterion():
    a = G.judge_e2a(*_a_pair(), 0.5)
    assert a["pass"] and a["higher"] and a["distinct"] and a["frac_ok"]
    assert a["states"] == [False, True, False] and a["speed"] == [0.45] * 3 and a["forbid_speed"] == [0.45] * 3
    assert not G.judge_e2a(*_a_pair(allow_g=(1.0, 1.1)), 0.5)["higher"]          # 차이 없음
    lo = G.judge_e2a(*_a_pair(allow_g=(0.0, 0.1)), 0.5)                           # 낮음: |t| 커도 실패
    assert lo["t"] < -2.093 and not lo["pass"]
    assert not G.judge_e2a(*_a_pair(vig=(0.1, 0.2, 0.3)), 0.5)["distinct"]        # 경계를 안 쓴다
    assert not G.judge_e2a(*_a_pair(vig=(0.9, 0.6, 0.51)), 0.5)["distinct"]       # 모두 경계
    assert not G.judge_e2a(*_a_pair(vig=(0.1, 0.5, 0.2)), 0.5)["distinct"]        # 0.5 는 경계가 아니다(> 문턱)
    over = G.judge_e2a(*_a_pair(vig_frac=0.51), 0.5)
    assert not over["frac_ok"] and over["over"] and not over["pass"]
    assert not G.judge_e2a(*_a_pair(vig_frac=0.009), 0.5)["frac_ok"]
    assert G.judge_e2a(*_a_pair(vig_frac=0.5), 0.5)["frac_ok"] and G.judge_e2a(*_a_pair(vig_frac=0.01), 0.5)["frac_ok"]


def test_judge_e2a_g998_only_and_mismatch():
    allow, forbid = _a_pair(allow_g=(1.0, 1.1))
    g_allow, g_forbid = _a_pair(allow_g=(3.0, 3.3))
    a = G.judge_e2a(allow, forbid, 0.5, g_allow, g_forbid)
    assert not a["higher"] and a["g998"]["higher"] and a["g998_only"]
    a = G.judge_e2a(*_a_pair(), 0.5, g_allow, g_forbid)
    assert a["pass"] and not a["g998_only"]
    bad = copy.deepcopy(forbid)
    bad["per_seed"]["C2"] = bad["per_seed"]["C2"][1:]
    with pytest.raises(ValueError):
        G.judge_e2a(allow, bad, 0.5)


def test_judge_b_branch_reads_speed_and_vigilance_tables():
    forbid = _res("C2-seg", _rows((1.0, 1.1)), [0.45, 0.45, 0.9], vig_frac=0.0, dims=[4],
                  table=[[0.45], [0.45], [0.9]], base=C2[:5] + [0.0])
    tab = [[0.45, 0.1], [0.2, 0.9], [0.9, 0.1]]
    allow = _res("C2-seg", _rows((2.0, 2.2)), sum(tab, []), dims=[4, 5], table=tab, base=C2)
    b = G.judge_e2a(allow, forbid, 0.5)
    assert b["pass"] and b["vig"] == [0.1, 0.9, 0.1] and b["speed"] == [0.45, 0.2, 0.9]
    assert b["forbid_speed"] == [0.45, 0.45, 0.9]


def _e2b(vg=(2.0, 2.2), vp=(0.0015, 0.0016)):
    vig = _res("C2-seg", _rows(vg, vp), [], dims=[4, 5], table=[], base=[])
    run = _res("C2-seg", _rows((1.0, 1.1), (0.0020, 0.0021)), [], dims=[4, 5], table=[], base=[])
    return vig, run


def test_judge_e2b_needs_g_and_predation():
    e = G.judge_e2b(*_e2b())
    assert e["pass"] and e["g_win"] and e["pred_win"]
    assert not G.judge_e2b(*_e2b(vg=(1.0, 1.1)))["pass"]                          # G_γ 같음
    assert not G.judge_e2b(*_e2b(vp=(0.0020, 0.0021)))["pass"]                    # 피식률 같음
    e = G.judge_e2b(*_e2b(vp=(0.0025, 0.0026)))                                   # 피식률이 높다
    assert not e["pred_win"] and e["pred"]["t"] > 2.093


def test_judge_t18_big_win():
    vig, run = _e2b()
    r18 = _res("C2-seg", _rows((3.0, 3.3), (0.001, 0.0011)), [], dims=[4, 5], table=[], base=[])
    t = G.judge_t18(vig, run, r18)
    assert t["big_win"] and t["vs_vig"]["g_gamma"]["diff"] > 0
    assert not G.judge_t18(vig, run, vig)["big_win"]


def _cand(a_pass, b_pass=False, t=3.0, g998_only=False, over=False):
    return {"A": {"pass": a_pass, "t": t, "g998_only": g998_only, "over": over},
            "B": {"pass": b_pass, "t": t, "g998_only": False, "over": False}}


def test_select_prefers_proposal_then_t():
    c = {"d0_9": _cand(True, t=5.0), "d0_95": _cand(True, t=2.5), "d0_975": _cand(False)}
    assert G.select(c, "A") == "d0_95"
    c["d0_95"] = _cand(False, b_pass=True)
    assert G.select(c, "A") == "d0_9" and G.select(c, "B") == "d0_95"
    assert G.select({k: _cand(False) for k in c}, "A") is None


def _round(rnd, cands, sel_a=None, sel_b=None):
    return {"round": rnd, "cands": cands, "selected_A": sel_a, "selected_B": sel_b}


def test_next_round_rules():
    fail = {k: _cand(False) for k in ("d0_9", "d0_95", "d0_975")}
    assert G.next_round([_round("V0", fail, "d0_95")])["action"] == "pass"
    nx = G.next_round([_round("V0", fail)])
    assert nx["action"] == "calibrate" and nx["round"] == "V1" and "0.5" in nx["reason"]
    nx = G.next_round([_round("V0", fail), _round("V1", fail)])
    assert nx["action"] == "calibrate" and nx["round"] == "V2" and "구현" in nx["reason"]
    assert G.next_round([_round("V0", fail), _round("V1", fail), _round("V2", fail)])["action"] == "stop"
    g9 = dict(fail, d0_9=_cand(False, g998_only=True))
    assert G.next_round([_round("V0", g9)])["action"] == "stop"                    # 0.998 갈래
    nx = G.next_round([_round("V0", dict(fail, d0_975=_cand(False, b_pass=True)), sel_b="d0_975")])
    assert nx["action"] == "stop" and "B 갈래" in nx["reason"]                      # B 만 통과 → 사람 결정
    over = dict(fail, d0_95=_cand(False, over=True))
    assert G.next_round([_round("V0", over)])["action"] == "stop"                  # 과반 → 반대 방향 보정 안 함


# --------------------------------------------------------------------- #
# 기록된 판정 (10-03 V0)
# --------------------------------------------------------------------- #


def test_v2_2_has_gate_e2_selected_coefficients():
    """Gate E2 PASS(10-03, V0 d0_95, PREREG 5절) 뒤 configs/v2_2.yaml 의 vigilance 계수 = 고른 후보·회차의 값이고,
    그 설정은 고른 후보 설정·run.json 의 config_digest 와 같다. 판정표 judge_e2.json 의 최종 판정과 맞는다."""
    from diagnose_v2 import config_digest
    final = json.loads((G.OUT / "judge_e2.json").read_text(encoding="utf-8"))["final"]
    assert (final["E2a"], final["E2b"], final["round"], final["cand"]) == ("PASS", "PASS", "V0", "d0_95")
    with open(V2_2, encoding="utf-8") as f:
        vg = yaml.safe_load(f)["features"]["vigilance"]
    assert (vg["decay"], vg["eat_mult"], vg["threat_flee"]) == (final["decay"], final["eat_mult"], 0.0)
    assert final["theta"] == G.THETA == RECENT_THREAT and final["view_r_mult"] == 1.0
    rec = json.loads((G.OUT / "V0" / "d0_95" / "run.json").read_text(encoding="utf-8"))
    digest = config_digest(load_v2_config(V2_2))
    assert digest == config_digest(load_v2_config(G.config_path("V0", 0.95))) == rec["config_digest"][""]
    c2 = json.loads((G.OUT / "V0" / "c2" / "constsearch.json").read_text(encoding="utf-8"))
    assert c2["best"] == final["c2"] and c2["meta"]["config_digest"] == digest
