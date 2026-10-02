"""V2 1-2 Gate E1 도구 (`gate_e1.py`) — 팔 설정(대사 계수), 판정 규칙, 회차 선택, 보정 규칙 (results/v2/e1/PREREG.md)."""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import math

import numpy as np
import pytest
import yaml

import gate_e1 as G
from env.config import ROOT
from env_v2.config import load_v2_config
from env_v2.world import _speed_params

THR = (1 / 3, 2 / 3)


# --------------------------------------------------------------------- #
# 팔 설정
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("r", [1.5, 2.0, 2.5, G.PROPOSAL_R, 4.5, 6.0])
def test_metabolism_keeps_walk_at_v1_and_sets_run(r):
    """걷기 대사 배수 1(= v1), 뛰기 R, 정지 = c_rest. world.py 의 drain_mult 식으로 확인한다."""
    c_rest, c_move = G.metabolism(r)
    speed = np.array([0.0, 0.4, 1.0])
    mult = c_rest + c_move * speed * speed
    assert mult[0] == c_rest
    assert mult[1] == pytest.approx(1.0, abs=1e-12)
    assert mult[2] == pytest.approx(r, abs=1e-12)


def test_metabolism_proposal_is_exact():
    """R 3.625 = 계획서 4.4 제안값 (c_rest 0.5, c_move 3.125) 과 비트 단위로 같다 (configs/v2_1.yaml 값)."""
    assert G.metabolism(G.PROPOSAL_R) == (0.5, 3.125)
    with open(ROOT / "configs" / "v2_1.yaml", encoding="utf-8") as f:
        sp = yaml.safe_load(f)["features"]["speed"]
    assert (sp["c_rest"], sp["c_move"]) == G.metabolism(G.PROPOSAL_R)
    assert sp["gait_eat"] == [G.EAT_STOP, G.R0_WALK_EAT, G.EAT_RUN]


@pytest.mark.parametrize("r", [1.0, 0.5, 6.3])
def test_metabolism_rejects_out_of_range(r):
    with pytest.raises(ValueError):
        G.metabolism(r)


def test_arm_config_changes_only_speed_coefficients(tmp_path):
    """생성 설정 = configs/v2_1.yaml 에서 c_rest·c_move·gait_eat 만 다르다. 읽히고 drain_mult 가 맞다."""
    p = G.write_arm_config("R0", 6.0, 0.75, tmp_path)
    assert p.name == "R0_r6_ew0_75.yaml"
    a, b = load_v2_config(p), load_v2_config(ROOT / "configs" / "v2_1.yaml")
    da, db = copy.deepcopy(a.to_dict()), copy.deepcopy(b.to_dict())
    sa, sb = da["v2"]["features"]["speed"], db["v2"]["features"]["speed"]
    for k in ("c_rest", "c_move", "gait_eat"):
        sa.pop(k), sb.pop(k)
    assert da == db
    sp = _speed_params(a.v2["features"]["speed"])
    assert sp["eat"].tolist() == [1.0, 0.75, 0.0]
    assert sp["drain_mult"][2] == pytest.approx(6.0)
    assert a.v2["version"] == "2.1"


def test_arm_names():
    assert G.arm_name(2, 0.5) == "r2_ew0_5"
    assert G.arm_name(G.PROPOSAL_R, 0.5) == "r3_625_ew0_5"
    assert G.arm_name(6.0, 0.35) == "r6_ew0_35"


def test_commands_follow_prereg(tmp_path):
    """명령 순서와 인자: C2(시작점 4개) → C2-seg(구간 2:0.5 4:0.5, speed) → 고정 보행 3종 → G_0.998."""
    cfg, d = tmp_path / "c.yaml", tmp_path / "arm"
    steps = G.commands_for(cfg, d, 6)
    assert [s for s, _ in steps] == ["constsearch", "constsearch_seg"]
    c2 = steps[0][1]
    assert c2.count("--enqueue") == 4 and "--seg-bins" not in c2 and "--trials" not in c2
    seg = steps[1][1]
    assert seg[seg.index("--seg-bins") + 1:seg.index("--seg-bins") + 3] == ["2:0.5", "4:0.5"]
    assert seg[seg.index("--seg-dims") + 1] == "speed"
    best = [0.1, 0.2, 0.3, 0.4, 0.5]
    steps = G.commands_for(cfg, d, 6, best, [0.9, 0.5, 0.5, 0.1])
    stems = [s for s, _ in steps]
    assert stems == ["constsearch", "constsearch_seg", "fixed_stop", "fixed_walk", "fixed_run", "g998/c2seg_g998"]
    run = dict(steps)["fixed_run"]
    ca = run[run.index("--const-action") + 1:]
    assert [float(x) for x in ca] == [0.1, 0.2, 0.3, 0.4, 1.0]
    g = dict(steps)["g998/c2seg_g998"]
    assert "--g998" in g and [float(x) for x in g[g.index("--base-action") + 1:g.index("--const-action")]] == best
    # 판정 실행에는 탐색·평가 조건 인자가 없다(diagnose_v2 기본값 = PREREG 2절)
    assert not any(a in sum((x for _, x in steps), []) for a in ("--trials", "--eval-steps", "--search-steps"))


# --------------------------------------------------------------------- #
# 판정
# --------------------------------------------------------------------- #


def _res(rows_key, means: dict, rows: list[dict], **extra) -> dict:
    return {"eval": {"mean": means, **extra.pop("eval_extra", {})}, "per_seed": {rows_key: rows}, **extra}


def _toy_arm(seg_g=(2.0, 2.1), c2_g=(1.0, 1.1), table=(0.9, 0.9, 0.5, 0.2), starve=0.2, hungry=0.3, walk=0.4,
             sr_walk=0.001, sr_run=0.01, n=20):
    seeds = list(range(10000, 10000 + n))
    rng = np.random.default_rng(0)
    gs = np.linspace(*seg_g, n)
    gc = np.linspace(*c2_g, n) + rng.normal(0, 0.01, n)
    best = [0.42, 0.87, 0.11, 0.0, 0.5]
    d = gs - gc
    t = d.mean() / (d.std(ddof=1) / math.sqrt(n))
    c2 = _res("C2", {"g_gamma": gc.mean(), "starve_share": 0.1, "hungry_frac": 0.2, "walk_frac": 0.9},
              [{"seed": s, "g_gamma": float(x)} for s, x in zip(seeds, gc)], best=best)
    seg = _res("C2-seg", {"g_gamma": gs.mean(), "starve_share": starve, "hungry_frac": hungry, "walk_frac": walk,
                          "walk_frac_cmd": walk},
               [{"seed": s, "g_gamma": float(x)} for s, x in zip(seeds, gs)],
               eval_extra={"vs_C2": {"g_gamma": {"diff": float(d.mean()), "t": float(t), "sig": abs(t) > 2.093}}},
               best=list(table), best_table=[[x] for x in table], base_action=best)
    fixed = {n_: _res("C2", {"starve_rate": v}, [{"seed": s, "starve_rate": v + 1e-4 * i} for i, s in enumerate(seeds)])
             for n_, v in (("stop", 0.002), ("walk", sr_walk), ("run", sr_run))}
    return c2, seg, fixed


def test_judge_pass_and_each_criterion():
    c2, seg, fixed = _toy_arm()
    j = G.judge_arm(c2, seg, fixed, None, THR)
    assert j["pass"] and j["passed"] == {"common": True, "a": True, "b": True, "c": True}
    assert j["common"]["gaits"] == [2, 2, 1, 0] and j["common"]["distinct"]
    assert j["c2"]["gait"] == 1

    j = G.judge_arm(*_toy_arm(table=(0.9, 0.8, 0.7, 0.67)), None, THR)      # 모두 뛰기 띠 → (ii) 실패
    assert not j["common"]["distinct"] and not j["passed"]["common"]
    j = G.judge_arm(*_toy_arm(seg_g=(1.0, 1.1)), None, THR)                  # 차이 없음 → (i) 실패
    assert not j["common"]["higher"]
    j = G.judge_arm(*_toy_arm(seg_g=(0.0, 0.1)), None, THR)                  # C2-seg 가 낮음 → |t| 커도 실패
    assert j["common"]["t"] < -2.093 and not j["common"]["higher"]
    for kw, crit, side in [(dict(starve=0.31), "a", "high"), (dict(starve=0.09), "a", "low"),
                           (dict(hungry=0.14), "a", "low"), (dict(walk=0.2), "b", None),
                           (dict(sr_walk=0.02), "c", None)]:
        j = G.judge_arm(*_toy_arm(**kw), None, THR)
        assert not j["passed"][crit] and not j["pass"], kw
        if side:
            assert j["a"][side]
    j = G.judge_arm(*_toy_arm(starve=0.10, hungry=0.15, walk=0.2001), None, THR)   # 경계는 포함
    assert j["passed"]["a"] and j["passed"]["b"]


def test_judge_refuses_mismatched_inputs():
    c2, seg, fixed = _toy_arm()
    bad = copy.deepcopy(c2)
    bad["per_seed"]["C2"] = bad["per_seed"]["C2"][1:]
    with pytest.raises(ValueError):
        G.judge_arm(bad, seg, fixed, None, THR)
    bad = copy.deepcopy(seg)
    bad["base_action"] = [0.0] * 5
    with pytest.raises(ValueError):
        G.judge_arm(c2, bad, fixed, None, THR)


def _arm(run_mult, walk_eat=0.5, **kw):
    return {"run_mult": run_mult, "walk_eat": walk_eat, "judge": G.judge_arm(*_toy_arm(**kw), None, THR)}


def test_select_prefers_proposal_then_t():
    arms = {"a": _arm(2.0, seg_g=(3.0, 3.1)), "b": _arm(G.PROPOSAL_R), "c": _arm(6.0, seg_g=(4.0, 4.1))}
    assert G.select_arm(arms) == "b"
    arms["b"] = _arm(G.PROPOSAL_R, walk=0.1)
    assert G.select_arm(arms) == max(("a", "c"), key=lambda k: arms[k]["judge"]["common"]["t"])
    assert G.select_arm({"x": _arm(2.0, walk=0.1)}) is None


def _round(name, arms, walk_eat=0.5, direction=None):
    r = {"round": name, "arms": arms, "incomplete": [], "walk_eat": walk_eat, "direction": direction}
    r["selected"], r["closest"] = G.select_arm(arms), G.closest_arm(arms)
    return r


def test_next_round_rules():
    # 통과
    assert G.next_round([_round("R0", {"a": _arm(G.PROPOSAL_R)})])["action"] == "pass"
    # (b) 실패 → e_walk 위로, 배수 그대로
    n = G.next_round([_round("R0", {"a": _arm(G.PROPOSAL_R, walk=0.1), "b": _arm(2.0, walk=0.1, starve=0.5)})])
    assert n["action"] == "calibrate" and n["walk_eat"] == 0.75 and n["direction"] == "up" and n["basis"] == "a"
    assert n["run_mults"] == list(G.R0_RUN_MULTS)
    # (a) 아래쪽 → 아래로
    n = G.next_round([_round("R0", {"a": _arm(G.PROPOSAL_R, starve=0.05)})])
    assert n["walk_eat"] == 0.35 and n["direction"] == "down"
    # 공통 규칙만 실패 → 배수 바꿈
    n = G.next_round([_round("R0", {"a": _arm(G.PROPOSAL_R, seg_g=(1.0, 1.1))})])
    assert n["run_mults"] == list(G.COMMON_ONLY_RUN_MULTS) and n["walk_eat"] == 0.5
    # (c) 실패 → 멈춤
    assert G.next_round([_round("R0", {"a": _arm(G.PROPOSAL_R, sr_walk=0.02)})])["action"] == "stop"
    # 방향이 바뀌면 가운데
    h = [_round("R0", {"a": _arm(G.PROPOSAL_R, walk=0.1)}),
         _round("R1", {"a": _arm(G.PROPOSAL_R, 0.75, starve=0.05)}, walk_eat=0.75, direction="up")]
    n = G.next_round(h)
    assert n["walk_eat"] == 0.625 and n["direction"] == "down"
    # 사다리 끝
    h = [_round("R0", {"a": _arm(G.PROPOSAL_R, 1.0, walk=0.1)}, walk_eat=1.0)]
    assert G.next_round(h)["action"] == "stop"
    # 이미 돌린 계수 회차를 다시 고르게 되면 멈춤 (공통 규칙만 실패가 두 번)
    arms1 = {"a": _arm(1.5, seg_g=(1.0, 1.1)), "b": _arm(2.5, seg_g=(1.0, 1.1)), "c": _arm(4.5, seg_g=(1.0, 1.1))}
    h = [_round("R0", {"a": _arm(G.PROPOSAL_R, seg_g=(1.0, 1.1))}), _round("R1", arms1)]
    assert G.next_round(h)["action"] == "stop"
    # R2 뒤에는 멈춤
    h = [_round(r, {"a": _arm(G.PROPOSAL_R, walk=0.1)}) for r in G.ROUNDS]
    assert G.next_round(h)["action"] == "stop"


def test_closest_arm_counts_passed_criteria():
    arms = {"a": _arm(2.0, walk=0.1, starve=0.5), "b": _arm(6.0, walk=0.1), "c": _arm(G.PROPOSAL_R, walk=0.1,
                                                                                         starve=0.5)}
    assert G.closest_arm(arms) == "b"
    arms["b"] = _arm(6.0, walk=0.1, starve=0.5)
    assert G.closest_arm(arms) == "c"          # 같으면 제안 배수
