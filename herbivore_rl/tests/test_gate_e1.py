"""V2 1-2 Gate E1 도구 (`gate_e1.py`) — 팔 설정(대사 계수), 판정 규칙, 회차 선택, 보정 규칙 (results/v2/e1/PREREG.md).

시도 E1(회차 R*, 포식자 ×0.8~1.2)과 E1-b(회차 B*, 포식자 ×0.6~0.95, 10-02 사전 등록 변경)의 분리도 본다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import json
import math

import numpy as np
import pytest
import yaml

import gate_e1 as G
from env.config import ROOT, load_config
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
    """R 3.625 = 계획서 4.4 제안값 (c_rest 0.5, c_move 3.125) 과 비트 단위로 같다 (E1·E1-b B0 의 제안 팔)."""
    assert G.metabolism(G.PROPOSAL_R) == (0.5, 3.125)
    sp = _speed_params(load_v2_config(G.OUT / "configs" / "B0_r3_625_ew0_5.yaml").v2["features"]["speed"])
    assert (sp["c_rest"], sp["c_move"]) == G.metabolism(G.PROPOSAL_R)


def test_v2_1_has_gate_e1b_selected_coefficients():
    """Gate E1-b PASS(10-02, B1 r2_5_ew0_5) 뒤 configs/v2_1.yaml = 고른 팔의 계수(PREREG 5절): c_rest·c_move =
    metabolism(2.5) 의 float64 값, gait_eat 는 [1.0, 0.5, 0.0] 그대로. 판정표 judge_e1b.json 의 최종 팔과 같고, 설정은
    그 팔 설정 파일·run.json 의 config_digest 와 같다."""
    from diagnose_v2 import config_digest
    with open(ROOT / "configs" / "v2_1.yaml", encoding="utf-8") as f:
        sp = yaml.safe_load(f)["features"]["speed"]
    assert (sp["c_rest"], sp["c_move"]) == G.metabolism(2.5) == (15.0 / 21.0, 37.5 / 21.0)
    assert sp["gait_eat"] == [G.EAT_STOP, G.R0_WALK_EAT, G.EAT_RUN]
    final = json.loads((G.OUT / "judge_e1b.json").read_text(encoding="utf-8"))["final"]
    assert (final["verdict"], final["round"], final["arm"]) == ("PASS", "B1", "r2_5_ew0_5")
    assert (final["run_mult"], final["walk_eat"]) == (2.5, 0.5)
    assert (final["c_rest"], final["c_move"]) == (sp["c_rest"], sp["c_move"])
    rec = json.loads((G.OUT / "B1" / "r2_5_ew0_5" / "run.json").read_text(encoding="utf-8"))
    digest = config_digest(load_v2_config(G.BASE_CONFIG))
    assert digest == config_digest(load_v2_config(G.OUT / "configs" / "B1_r2_5_ew0_5.yaml")) == rec["config_digest"]


@pytest.mark.parametrize("r", [1.0, 0.5, 6.3])
def test_metabolism_rejects_out_of_range(r):
    with pytest.raises(ValueError):
        G.metabolism(r)


def test_arm_config_changes_only_speed_coefficients(tmp_path):
    """생성 설정 = configs/v2_1.yaml 에서 c_rest·c_move·gait_eat 만 다르다. 읽히고 drain_mult 가 맞다.
    포식자 속도(rand)는 v2_1.yaml 의 E1-b 값 그대로다."""
    p = G.write_arm_config("B0", 6.0, 0.75, tmp_path)
    assert p.name == "B0_r6_ew0_75.yaml"
    a, b = load_v2_config(p), load_v2_config(ROOT / "configs" / "v2_1.yaml")
    assert a.rand == b.rand and a.rand["pred_speed_mult"] == list(G.ATTEMPTS["E1-b"]["pred_speed_mult"])
    da, db = copy.deepcopy(a.to_dict()), copy.deepcopy(b.to_dict())
    sa, sb = da["v2"]["features"]["speed"], db["v2"]["features"]["speed"]
    for k in ("c_rest", "c_move", "gait_eat"):
        sa.pop(k), sb.pop(k)
    assert da == db
    sp = _speed_params(a.v2["features"]["speed"])
    assert sp["eat"].tolist() == [1.0, 0.75, 0.0]
    assert sp["drain_mult"][2] == pytest.approx(6.0)
    assert a.v2["version"] == "2.1"


def test_attempts_and_round_names():
    """E1(R*)과 E1-b(B*)는 회차 이름이 겹치지 않고 시도마다 회차 0 + 보정 2회다. 시도의 포식자 속도는 v1 값과
    지금 configs/v2_1.yaml 값이다. E1 판정표 파일 이름은 그대로(judge)다."""
    assert G.ROUNDS == ("R0", "R1", "R2", "B0", "B1", "B2")
    assert [G.attempt_of(r) for r in G.ROUNDS] == ["E1"] * 3 + ["E1-b"] * 3
    with pytest.raises(ValueError):
        G.attempt_of("C0")
    assert all(len(a["rounds"]) == G.MAX_ROUNDS == 3 for a in G.ATTEMPTS.values())
    assert list(G.ATTEMPTS["E1"]["pred_speed_mult"]) == load_config().rand["pred_speed_mult"] == [0.8, 1.2]
    assert list(G.ATTEMPTS["E1-b"]["pred_speed_mult"]) == load_v2_config(G.BASE_CONFIG).rand["pred_speed_mult"]
    assert list(G.ATTEMPTS["E1-b"]["pred_speed_mult"]) == [0.6, 0.95]
    assert G.ATTEMPTS["E1"]["judge_stem"] == "judge" and G.ATTEMPTS["E1-b"]["judge_stem"] == "judge_e1b"
    assert set(G.ROUND_LABEL) == set(G.ROUNDS)


def test_write_arm_config_guards(tmp_path):
    """지금 v2_1.yaml(E1-b 포식자 속도)로는 E1 회차(R*) 설정을 만들지 않는다. 옛 바탕(overrides {})을 주면 E1 R0
    제안 팔과 같은 설정(run.json 에 기록된 config_digest)이 나온다. 이미 있는 팔 설정은 같은 내용이면 그대로 두고,
    다르면 덮지 않는다. E1-b 제안 팔은 B0 run.json 에 기록된 설정과 같다(바탕 v2_1.yaml 의 계수가 E1-b 통과 뒤 바뀌어도
    팔 설정은 speed 계수를 덮어써서 같다)."""
    from diagnose_v2 import config_digest
    with pytest.raises(ValueError, match="E1"):
        G.write_arm_config("R0", G.PROPOSAL_R, 0.5, tmp_path)
    assert not (tmp_path / "configs").exists()
    raw = yaml.safe_load(G.BASE_CONFIG.read_text(encoding="utf-8"))
    raw["overrides"] = {}
    old = tmp_path / "v2_1_before_e1b.yaml"
    old.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    r0 = G.write_arm_config("R0", G.PROPOSAL_R, 0.5, tmp_path, base=old)
    rec = json.loads((G.OUT / "R0" / "r3_625_ew0_5" / "run.json").read_text(encoding="utf-8"))
    assert config_digest(load_v2_config(r0)) == rec["config_digest"]
    with pytest.raises(ValueError, match="E1-b"):
        G.write_arm_config("B0", G.PROPOSAL_R, 0.5, tmp_path, base=old)       # E1-b 회차에 v1 포식자 속도
    b0 = G.write_arm_config("B0", G.PROPOSAL_R, 0.5, tmp_path)
    rec = json.loads((G.OUT / "B0" / "r3_625_ew0_5" / "run.json").read_text(encoding="utf-8"))
    assert config_digest(load_v2_config(b0)) == rec["config_digest"]
    text = b0.read_text(encoding="utf-8")
    assert text == (G.OUT / "configs" / "B0_r3_625_ew0_5.yaml").read_text(encoding="utf-8")
    assert "rand.pred_speed_mult = [0.6, 0.95]" in text
    assert G.write_arm_config("B0", G.PROPOSAL_R, 0.5, tmp_path) == b0 and b0.read_text(encoding="utf-8") == text
    b0.write_text(text + "# 손으로 고침\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        G.write_arm_config("B0", G.PROPOSAL_R, 0.5, tmp_path)
    assert b0.read_text(encoding="utf-8").endswith("# 손으로 고침\n")
    with pytest.raises(SystemExit):                                           # 명령줄도 같은 이유로 멈춘다
        G.main(["configs", "--round", "R1", "--run-mult", "2", "--walk-eat", "0.5", "--out", str(tmp_path)])
    assert not (tmp_path / "configs" / "R1_r2_ew0_5.yaml").exists()


def test_run_and_judge_refuse_config_of_other_attempt(tmp_path):
    """회차 이름과 설정의 포식자 속도가 다른 시도면 돌리지도 판정하지도 않는다(결과 디렉터리를 만들지 않는다)."""
    b0 = G.write_arm_config("B0", G.PROPOSAL_R, 0.5, tmp_path)
    fake = b0.with_name("R0_r3_625_ew0_5.yaml")
    fake.write_text(b0.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(SystemExit, match="E1"):
        G.main(["run", "--round", "R0", "--arm", "r3_625_ew0_5", "--out", str(tmp_path), "--smoke"])
    assert not (tmp_path / "R0").exists()
    with pytest.raises(ValueError, match="E1"):
        G.load_round("R0", tmp_path)


def test_existing_e1_results_unchanged():
    """기록된 E1 팔 설정 6개(results/v2/e1/configs/R*.yaml)는 v1 포식자 속도이고, 판정표 judge.md 는 지금 코드로
    다시 만들어도 한 글자도 같다(E1 결과를 덮거나 바꾸지 않는다. E1-b 는 judge_e1b.* 에 따로 쓴다)."""
    cfgs = sorted((G.OUT / "configs").glob("R*.yaml"))
    assert len(cfgs) == 6
    for c in cfgs:
        G.check_attempt_world(c.stem.split("_")[0], load_v2_config(c))
    data, L = G.judge_attempt("E1")
    assert "\n".join(L) + "\n" == (G.OUT / "judge.md").read_text(encoding="utf-8")
    assert data["final"]["verdict"] == "FAIL" and data["final"]["round"] == "R1"
    assert list(data["rounds"]) == ["R0", "R1"]


def test_existing_e1b_results_unchanged():
    """기록된 E1-b 팔 설정 6개(B0·B1)는 E1-b 포식자 속도이고, 판정표 judge_e1b.md 는 지금 코드로 다시 만들어도 한 글자도
    같다. B1 에서 r2_5_ew0_5 가 통과해 B2 는 돌리지 않았다(PREREG 3.5)."""
    cfgs = sorted((G.OUT / "configs").glob("B*.yaml"))
    assert [c.stem.split("_")[0] for c in cfgs] == ["B0"] * 3 + ["B1"] * 3
    for c in cfgs:
        G.check_attempt_world(c.stem.split("_")[0], load_v2_config(c))
    data, L = G.judge_attempt("E1-b")
    assert "\n".join(L) + "\n" == (G.OUT / "judge_e1b.md").read_text(encoding="utf-8")
    assert list(data["rounds"]) == ["B0", "B1"]
    assert data["rounds"]["B0"]["selected"] is None and data["rounds"]["B0"]["next"]["action"] == "calibrate"
    assert data["rounds"]["B0"]["next"]["run_mults"] == list(G.COMMON_ONLY_RUN_MULTS)
    assert data["rounds"]["B1"]["selected"] == "r2_5_ew0_5" and data["final"]["verdict"] == "PASS"


def test_judge_attempt_e1b_reads_only_b_rounds(tmp_path):
    """E1-b 판정표는 B* 회차만 읽어 judge_e1b.* 에 쓴다. 같은 디렉터리의 E1 판정표(judge.md)는 건드리지 않는다."""
    G.write_arm_config("B0", G.PROPOSAL_R, 0.5, tmp_path)
    d = tmp_path / "B0" / "r3_625_ew0_5"
    d.mkdir(parents=True)
    c2, seg, fixed = _toy_arm()
    for stem, obj in [("constsearch", c2), ("constsearch_seg", seg)] + [(f"fixed_{n}", v) for n, v in fixed.items()]:
        (d / f"{stem}.json").write_text(json.dumps(obj, default=lambda o: o.item()), encoding="utf-8")   # numpy 값
    (tmp_path / "judge.md").write_text("E1 그대로\n", encoding="utf-8")
    assert G.main(["judge", "--attempt", "E1-b", "--out", str(tmp_path)]) == 0
    md = (tmp_path / "judge_e1b.md").read_text(encoding="utf-8")
    assert md.startswith("# Gate E1-b 판정표") and "## B0 제안값·배수 훑기 (E1-b)" in md and "**PASS**" in md
    data = json.loads((tmp_path / "judge_e1b.json").read_text(encoding="utf-8"))
    assert data["attempt"] == "E1-b" and data["pred_speed_mult"] == [0.6, 0.95]
    assert data["final"]["verdict"] == "PASS" and data["final"]["round"] == "B0"
    assert data["final"]["arm"] == "r3_625_ew0_5" and data["final"]["attempt"] == "E1-b"
    assert (tmp_path / "judge.md").read_text(encoding="utf-8") == "E1 그대로\n"
    assert not (tmp_path / "judge.json").exists()
    with pytest.raises(SystemExit):                                           # 시도를 꼭 고른다
        G.main(["judge", "--out", str(tmp_path)])


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
    h = [_round(r, {"a": _arm(G.PROPOSAL_R, walk=0.1)}) for r in G.ATTEMPTS["E1"]["rounds"]]
    assert G.next_round(h)["action"] == "stop"


def test_next_round_budget_and_repeat_are_per_attempt():
    """E1-b 는 새 시도다: 보정 예산(B1·B2)과 반복 회차 멈춤을 E1 회차와 섞지 않는다(PREREG 변경 기록 E1-b).
    judge 는 시도마다 그 시도의 회차만 history 로 넘긴다."""
    def common_only(r):
        return _arm(r, seg_g=(1.0, 1.1))
    b0 = _round("B0", {"a": common_only(G.PROPOSAL_R)})
    n = G.next_round([b0])                 # E1 R1 과 같은 계수지만 E1-b 안에서는 처음이라 돌린다
    assert n["action"] == "calibrate" and n["run_mults"] == list(G.COMMON_ONLY_RUN_MULTS) and n["walk_eat"] == 0.5
    b1 = _round("B1", {k: common_only(r) for k, r in zip("abc", G.COMMON_ONLY_RUN_MULTS)})
    assert G.next_round([b0, b1])["action"] == "stop"          # E1-b 안에서 같은 계수 반복 → 멈춤
    h = [_round(r, {"a": _arm(G.PROPOSAL_R, walk=0.1)}) for r in G.ATTEMPTS["E1-b"]["rounds"]]
    assert G.next_round(h[:1])["action"] == G.next_round(h[:2])["action"] == "calibrate"
    assert G.next_round(h)["action"] == "stop"                 # B2 뒤에는 멈춤


def test_closest_arm_counts_passed_criteria():
    arms = {"a": _arm(2.0, walk=0.1, starve=0.5), "b": _arm(6.0, walk=0.1), "c": _arm(G.PROPOSAL_R, walk=0.1,
                                                                                         starve=0.5)}
    assert G.closest_arm(arms) == "b"
    arms["b"] = _arm(6.0, walk=0.1, starve=0.5)
    assert G.closest_arm(arms) == "c"          # 같으면 제안 배수
