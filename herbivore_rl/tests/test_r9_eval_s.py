"""R9 S′ 평가·관문 정의와 밤 창 시험 (2026-11-12 등록 — 설계 8-2·8-4·9-1, results/v3/r9/STATUS.md 0·2·5절).

- strict 사냥: 손 구간·죽임으로 거르기 → 묶기 → 성공·우연, 세계에서 Recorder 고리 셈 = 스크래치 꼴(결정 사전) 셈, 사체 칸 쪽 걷기·뛰기 = 사체로 가는 중.
- C0-5 먹은 양 몫·d 점수·동점 0.01 표 차례, C0-7 max 점수·동점 0.05·L0 짝 비교·0.012 등록 조건, C0-6 보고, C0-1 멈추고 묻기, C0-2 한 번만,
  C0-10 늑대 셋 조건과 음성 대조 셋, γ 고르기.
- 밤 창 (22:00-09:00, 자정 넘김), 언리얼·메모리 조건, 리그 precheck, 밤 실행기 단계 판단·YAML 옮겨 적기·dry-run (띄우지 않음).
시드: 44350~44399 만 (10절).
"""

import datetime as dt
import json
import math
import sys

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import r9_body as B
from env_v2 import r9_world as W
from env_v2.r9_world import R9World

EVAL_DIR = ROOT / "results" / "v3" / "r9"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import eval_r9 as EV  # noqa: E402
import league_r9 as LG  # noqa: E402
import r9_eval_core as C  # noqa: E402
import run_night as NR  # noqa: E402

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"
D_, W_, R_ = B.DEER, B.WOLF, B.BOAR


@pytest.fixture(scope="module")
def cfg():
    return B.load_r9_config(CFG)


@pytest.fixture(scope="module")
def jcfg():
    return B.load_r9_config(JCFG)


def _h(k, wuid, tuid, t0, t1, n=6, hunting=True, end="gap"):
    return dict(k=k, wolf_uid=wuid, target_uid=tuid, target_sp=D_, t0=t0, t1=t1, n_close=n, ran=False, end=end, hunting=hunting)


def _kill(k, wuid, puid, t, rel, act=None):
    return dict(k=k, wolf_uid=wuid, prey_uid=puid, t=t, prey_sp=D_, wolf_act=B.WALK_FIRST if act is None else act, wolf_rel=rel,
                prey_af=1.0, juv_share=0.0)


# --------------------------------------------------------------------------- #
# strict 사냥 (8-2)
# --------------------------------------------------------------------------- #

def test_strict_hand_filter_merge_success_incidental():
    """거르기 → 묶기: 같은 늑대의 겹친 사냥 구간은 하나, 사냥 아닌 구간(사체로 가는 중이 절반 넘음)은 빠짐, 짧은 구간(n_close ≤ 4)도 빠짐.
    구간 안 죽임 = 그 묶음 성공(한 번), 구간 밖 걷기·뛰기 중 죽임 = 시도 1·성공 1, 구간 밖 서기·사체로 가는 중 죽임 = 우연."""
    hunts = [_h(0, 9, 1, 10, 40), _h(0, 9, 2, 30, 60), _h(0, 9, 3, 100, 130), _h(0, 9, 4, 200, 230, hunting=False),
             _h(0, 9, 5, 300, 330, n=4), _h(0, 7, 6, 10, 40), _h(1, 9, 1, 10, 40)]
    kills = [_kill(0, 9, 2, 50, 1), _kill(0, 9, 1, 55, 1),          # 둘 다 첫 묶음 [10, 60] 안 → 성공 1, 안 죽임 2
             _kill(0, 9, 4, 210, 2),                                # 사냥 아닌 구간 안이지만 사체로 가는 중 → 우연
             _kill(0, 9, 7, 500, 1),                                # 구간 밖 걷기 → 시도 1·성공 1
             _kill(0, 9, 8, 600, 0),                                # 구간 밖 서기 → 우연
             _kill(1, 9, 1, 40, 0)]                                 # 세계 1 구간 끝 (포함) → 성공
    s = C.strict_stats(hunts, kills, 2)
    assert s["attempts"].tolist() == [4, 1]                         # 세계 0: 묶음 [10,60] · [100,130] · 늑대 7 [10,40] + 구간 밖 1
    assert s["successes"].tolist() == [2, 1] and s["kills_inside"].tolist() == [2, 1]
    assert s["kills_outside_move"].tolist() == [1, 0] and s["incidental"].tolist() == [2, 0]
    assert s["hunt_kills"].tolist() == [3, 1] and s["segments_not_hunting"].tolist() == [1, 0]
    rec = dict(K=2, hunts=hunts, kills=kills, st=dict(alive_steps=np.array([[0, 900, 0], [0, 1800, 0]])), att=np.zeros((2, 2)))
    j = C.j3_metrics(rec)
    assert j["hunt_def"] == "strict" and j["success_rate"] == pytest.approx(3 / 5) and j["attempts"] == 5
    assert j["kappa_hunt"] == pytest.approx(4 / 3) and j["kappa_incidental"] == pytest.approx(2 / 3)
    assert j["ok"]["success"] is False and j["insufficient"].get("success")          # 최소 표본 strict 시도 100


def test_strict_counting_equals_scratch_dict_form(cfg):
    """세계에서: Recorder 의 결정 고리 셈(hunting·wolf_rel) = 스크래치 꼴(늑대-uid 별 결정 사전, '결정 시각 + D' 키, measure_s R3 바꿔 적기) 셈.
    사체로 가는 중 = 걷기·뛰기 방향이 그 결정 관측 food_dir 가장 큰 칸(> 0)과 같음 — 관측과 고른 행동만."""
    c = B.override(cfg, EV.EVAL_FACING)
    acts, carc = {}, [0]

    def probe(w, rec, a, c0):
        lo, hi = int(w.sp_lo[W_]), int(w.sp_hi[W_])
        o = w.obs()
        for k, s in zip(*np.nonzero(w.alive[:, lo:hi])):
            act = int(a[k, lo + s])
            if B.WALK_FIRST <= act <= B.RUN_LAST:
                fd = o[k, lo + s, B.SL_FOOD_DIR]
                if fd.max() > 0.0 and int(np.argmax(fd)) == int(B.action_dir_index(act)):
                    act = B.EAT
                    carc[0] += 1
            acts.setdefault((c0 + int(k), int(w.uid[k, lo + s])), {})[int(w.t[k]) + w.D] = act
    for wolf in ("RULE_WOLF", "RANDOM"):
        acts.clear()
        carc[0] = 0
        rec = C.run(c, [44350, 44351], 700, EV.spec_fn(c, {D_: "RULE_DEER", W_: wolf, R_: "ALWAYS_EAT"}, {}), scenes=False, on_decision=probe)
        seg = [h for h in rec["hunts"] if int(h["n_close"]) > W.HUNT_MIN_DECISIONS]
        assert seg, wolf
        for h in seg:
            aa = acts.get((int(h["k"]), int(h["wolf_uid"])), {})
            v = [aa[t] for t in range(int(h["t0"]) + 2, int(h["t1"]) + 1, 2) if t in aa]
            mv = sum(1 for x in v if B.WALK_FIRST <= x <= B.RUN_LAST)
            assert (h["hunt_dec"], h["hunt_move"]) == (len(v), mv) and h["hunting"] == (bool(v) and mv > 0.5 * len(v))
        for e in rec["kills"]:
            aa = acts.get((int(e["k"]), int(e["wolf_uid"])), {})
            ra = next((aa[t] for t in (int(e["t"]) + 1, int(e["t"]) + 2) if t in aa), None)
            assert ra is not None and (e["wolf_rel"] == 1) == (B.WALK_FIRST <= ra <= B.RUN_LAST)
        assert int(rec["wolf_dec"][:, 2].sum()) == carc[0]


def test_nohunt_wolves_never_hunt(cfg):
    """음성 대조: 사체 쪽 걷기·뛰기만 하는 늑대(NOHUNT·NOHUNT_RUN)는 '사냥 구간'도 사냥 죽임도 없다(물린 먹잇감은 우연 죽임)."""
    c = B.override(cfg, EV.EVAL_FACING)
    for wolf in ("NOHUNT", "NOHUNT_RUN"):
        rec = C.run(c, [44352, 44353], 900, EV.spec_fn(c, {D_: "ALWAYS_EAT", W_: wolf, R_: "ALWAYS_EAT"}, {}), scenes=False)
        s = C.strict_stats(rec["hunts"], rec["kills"], int(rec["K"]))
        assert s["hunt_kills"].sum() == 0
        assert all(int(e["wolf_rel"]) != 1 for e in rec["kills"])


# --------------------------------------------------------------------------- #
# C0-5 · C0-7 · C0-6 · C0-1 · C0-2 고르는 규칙
# --------------------------------------------------------------------------- #

def test_c05_units_score_and_tie(cfg):
    """먹은 양 = 에너지 ÷ 몸 단위당 E. 멧돼지 에너지 풀 0.1·땅속 0.55·고기 0.35 → 단위 몫 풀 0.330·땅속 0.605·고기 0.064 [계산]."""
    ee = np.zeros((3, 3))
    ee[D_, B.GRASS] = 5.0
    ee[R_] = [0.10, 0.55, 0.35]
    u = EV.c05_units(ee, cfg)
    g, r, m = 0.10 / 0.05, 0.55 / 0.15, 0.35 / 0.9
    tot = g + r + m
    assert u["root_share"] == pytest.approx(r / tot) and u["units"]["boar"]["meat"] == pytest.approx(m / tot)
    pk = (g / tot) / math.sqrt((g / tot) ** 2 + (r / tot) ** 2 + (m / tot) ** 2)
    assert u["pianka"] == pytest.approx(pk) and u["ok"] is (0.5 <= r / tot <= 0.8 and 0.2 <= pk <= 0.5)
    assert u["score"] == pytest.approx(max(abs(r / tot - 0.65), abs(pk - 0.35)))
    # 고르기: d 가장 작은 것, 0.01 안은 표 차례 (1 → 0.5 → 2 → 0.25 → 4)
    cands = [1.0, 0.5, 2.0, 0.25, 4.0]
    t = [dict(value=1.0, ok=True, score=0.060), dict(value=0.5, ok=True, score=0.052), dict(value=2.0, ok=True, score=0.045),
         dict(value=0.25, ok=False, score=0.0), dict(value=4.0, ok=True, score=0.20)]
    assert EV.pick_by_rule(t, cands, 0.01)["value"] == 0.5          # 0.045 와 0.052 는 0.01 안 → 표 차례 앞(0.5)
    t[1]["score"] = 0.058
    assert EV.pick_by_rule(t, cands, 0.01)["value"] == 2.0
    assert EV.pick_by_rule([dict(value=1.0, ok=False, score=0.0)], cands, 0.01) is None
    assert EV.C0_SPEC["C0-5"]["tie"] == 0.01 and EV.C0_SPEC["C0-5"]["cands"] == cands


def test_c07_score_tie_l0_and_registration(monkeypatch):
    """C0-7: 점수 = max(|log 사슴비|, |log 멧돼지비|) (스크래치 3-5: 0.002 0.72/1.35 → 0.30, 0.0025 0.94/1.34 → 0.29 → 0.05 안 → 0.002),
    L0 짝 변화 = ΣL0 끝 ÷ Σ켬 끝 − 1, 0.012 가 띠를 통과하면 고르지 않고 묻는다(등록 조건)."""
    sc = lambda a, b: max(abs(math.log(a)), abs(math.log(b)))  # noqa: E731
    cands = EV.C0_SPEC["C0-7"]["cands"]
    t = [dict(value=0.002, ok=True, score=sc(0.72, 1.35)), dict(value=0.0025, ok=True, score=sc(0.94, 1.34))]
    assert EV.pick_by_rule(t, cands, 0.05)["value"] == 0.002
    t = [dict(value=0.002, ok=True, score=sc(0.75, 1.22)), dict(value=0.0025, ok=True, score=sc(0.96, 1.18))]
    assert EV.pick_by_rule(t, cands, 0.05)["value"] == 0.0025       # 0.29 대 0.17 (탐색 10 세계) → 0.0025
    ch = C.l0_change([[10, 0, 4], [10, 0, 6]], [[11, 0, 5], [10, 0, 7]])
    assert ch["deer"] == pytest.approx(0.05) and ch["boar"] == pytest.approx(0.2) and math.isnan(ch["wolf"])
    with pytest.raises(ValueError):
        C.l0_change([[1, 1, 1]], [[1, 1, 1], [1, 1, 1]])
    # pick_gate: 후보 통과 + 0.012 띠 안 → ask_user
    calls = []

    def fake_m(ctx, v, **kw):
        calls.append(v)
        return dict(value=v, ok=v == 0.002, score=0.1, band_ok=True, end_ratio=dict(deer=1.0, boar=1.0))
    monkeypatch.setitem(EV.MEASURE, "C0-7", fake_m)
    monkeypatch.setattr(EV, "m_c07_controls", lambda ctx: dict(neg=dict(band_ok=True), neg_fails_band=False, report=dict(ok=True)))
    ctx = EV.GateCtx(None, None, [], [], 0, 0, 0, None, verbose=False)
    r = EV.pick_gate("C0-7", ctx, {})
    assert r["status"] == "ask_user" and r["value"] is None and "등록 조건" in r["note"] and calls == cands
    monkeypatch.setattr(EV, "m_c07_controls", lambda ctx: dict(neg=dict(band_ok=False), neg_fails_band=True, report=dict(ok=True)))
    r = EV.pick_gate("C0-7", ctx, {})
    assert r["status"] == "pass" and r["value"] == 0.002


def test_c06_report_and_report_gates(monkeypatch):
    """C0-6 보고: 서서 먹은 몫·헛 EAT 몫 = 산 스텝 기준, 먹이 활동 몫 = 결정 기준. 보고 관문(C0-6·C0-4)은 고르지도 멈추지도 않는다."""
    K = 1
    st = dict(alive_steps=np.array([[100, 0, 50]]), decisions=np.array([[50, 0, 25]]), actions=np.zeros((K, 3, B.N_ACTIONS)),
              in_shelter_steps=np.zeros((K, 3)), run_steps=np.zeros((K, 3)), eaten_e=np.zeros((K, 3, 3)), deaths=np.zeros((K, 3, 4)),
              birth_credits=np.zeros((K, 3)), near_ties=np.zeros((K, 3)))
    st["actions"][0, D_, B.EAT] = 20
    st["actions"][0, D_, B.WATCH] = 5
    st["actions"][0, D_, B.WALK_FIRST] = 25
    eh = np.zeros((K, 3, 101))
    eh[0, D_, 30] = 10
    rec = dict(K=K, st=st, ehist=eh, elig=np.zeros((K, 3)), eat_steps=np.array([[[100, 30, 10], [0, 0, 0], [50, 20, 1]]]),
               forage_dec=np.array([[[50, 40], [0, 0], [25, 10]]]))
    r = EV.c06_report(rec)
    assert r["deer"]["eat_dec_share"] == pytest.approx(0.4) and r["deer"]["stand_eat_share"] == pytest.approx(0.3)
    assert r["deer"]["null_eat_share"] == pytest.approx(0.1) and r["deer"]["forage_share"] == pytest.approx(0.8)
    assert r["deer"]["rest_share"] == pytest.approx(0.1) and r["deer"]["E_median"] == pytest.approx(0.3) and r["old_band"]["deer"]
    for g in ("C0-6", "C0-4"):
        monkeypatch.setitem(EV.MEASURE, g, lambda ctx, v=None: dict(ok=True, value=None))
        r = EV.pick_gate(g, EV.GateCtx(None, None, [], [], 0, 0, 0, None, verbose=False), {})
        assert r["status"] == "report" and EV.C0_SPEC[g]["kind"] == "report" and "path" not in EV.C0_SPEC[g]


def test_c01_check_asks_and_c02_fix_once(monkeypatch):
    ctx = EV.GateCtx(None, None, [], [], 0, 0, 0, None, verbose=False)
    monkeypatch.setitem(EV.MEASURE, "C0-1", lambda ctx, v=None: dict(ok=False, ratio=0.74, diff_ci=[-0.1, 0.02]))
    r = EV.pick_gate("C0-1", ctx, {})
    assert r["status"] == "ask_user" and "멈추고" in r["note"]
    monkeypatch.setitem(EV.MEASURE, "C0-1", lambda ctx, v=None: dict(ok=True, ratio=0.47, diff_ci=[-0.4, -0.1]))
    assert EV.pick_gate("C0-1", ctx, {})["status"] == "pass"
    seen = []

    def m2(ctx, v):
        seen.append(v)
        sr = 0.55 if v == [0.90, 1.05] else 0.52
        return dict(value=v, ok=0.1 <= sr <= 0.5, success_rate=sr, direction="high" if sr > 0.5 else None)
    monkeypatch.setitem(EV.MEASURE, "C0-2", m2)
    ct = B.load_r9_config(CFG)
    ctx2 = EV.GateCtx(ct, None, [], [], 0, 0, 0, None, verbose=False)
    r = EV.pick_gate("C0-2", ctx2, {})
    assert seen == [[0.90, 1.05], [0.85, 1.00]] and r["status"] == "ask_user" and r["fixed"]          # 한 번만, 그래도 밖 → 묻기
    st = dict(values={}, fixed={})
    r = dict(gate="C0-2", kind="direction", status="fixed_pass", value=[0.85, 1.00], fixed=True, tried=[])
    EV._apply(st, "C0-2", r)
    assert st["values"]["C0-2"] == [0.85, 1.00] and st["fixed"]["C0-2"]


def test_c0_10_wolf_verdict_controls_and_choice():
    """늑대 셋 조건: 보상 − RANDOM·− 늘 살피기 (세계 짝 95% 아래 끝 > 0) ∧ 성공률 ≥ 0.5 × 규칙 ∧ 사냥 죽임 κ ≥ 0.5 × 규칙.
    스모크 꼴 값: 규칙 0.49·0.32, 무작위 0.08, 사체 쪽 걷기 κ 0 → 무작위·청소부 모두 떨어진다 (등록 조건)."""
    rng = np.random.default_rng(44354)

    def side(base, sr, kh):
        return dict(rew_1k_world=(base + rng.normal(0, 0.05, 20)).tolist(), success_rate=sr, kappa_hunt=kh)
    rule, rnd, wat = side(5.0, 0.49, 0.32), side(-2.0, 0.08, 1.0), side(1.0, float("nan"), 0.0)
    nohunt, learned = side(5.3, float("nan"), 0.0), side(4.0, 0.40, 0.25)
    v = EV.c010_wolf_verdict(learned, rule, rnd, wat)
    assert v["a_reward"] and v["b_success"] and v["c_kappa"] and v["ok"]
    assert not EV.c010_wolf_verdict(rnd, rule, rnd, wat)["ok"]                         # RANDOM − RANDOM = 0
    vn = EV.c010_wolf_verdict(nohunt, rule, rnd, wat)
    assert vn["a_reward"] and not vn["b_success"] and not vn["c_kappa"] and not vn["ok"]   # 보상만으로는 청소부를 못 거른다
    weak = side(4.0, 0.20, 0.10)
    assert not EV.c010_wolf_verdict(weak, rule, rnd, wat)["ok"]                         # 0.20 < 0.245
    good = dict(deer=dict(ok=True), boar=dict(ok=True), wolf=dict(ok=True, registration_ok=True))
    badw = dict(deer=dict(ok=True), boar=dict(ok=True), wolf=dict(ok=False, registration_ok=True))
    badp = dict(deer=dict(ok=False), boar=dict(ok=True), wolf=dict(ok=True, registration_ok=True))
    assert EV.c010_choose({"0.997": good, "0.99": good}) == dict(gamma=0.997, action="pass")
    assert EV.c010_choose({"0.997": badw, "0.99": good}) == dict(gamma=0.99, action="pass")
    assert EV.c010_choose({"0.997": badp, "0.99": badp})["action"] == "enable_F_and_rerun_both"
    assert EV.c010_choose({"0.997": badw, "0.99": badw})["action"] == "wolf_round0_first10M_always_eat_100"
    reg = dict(good, wolf=dict(ok=True, registration_ok=False))
    assert EV.c010_choose({"0.997": reg, "0.99": good})["action"] == "ask_user"


def test_c0_10_plan_and_commands():
    """먹이 넷(γ 둘 × 사슴 20M·멧돼지 10M) → 늑대 둘(10M, 조각 3), --round 0 · --model-seed 0 · 갈래 C0_10_g*, F 판은 _F·--fallback-f.
    벽시계 상한 = 2 × 결정 ÷ 속도 (0.1 h 올림), 밤 창 어림 = 결정 ÷ 속도 × 1.1."""
    sp = dict(deer=5000.0, boar=2000.0, wolf=2000.0)
    plan = EV.c010_plan(speeds=sp)
    assert [(p["stage"], p["species"], p["gamma"]) for p in plan] == [("prey", "deer", 0.997), ("prey", "boar", 0.997), ("prey", "deer", 0.99),
                                                                      ("prey", "boar", 0.99), ("wolf", "wolf", 0.997), ("wolf", "wolf", 0.99)]
    d = plan[0]
    assert d["decisions"] == 20_000_000 and d["est_s"] == pytest.approx(20e6 / 5000 * 1.1) and d["wall_hours"] == pytest.approx(2.3)
    assert "--round" in d["args"] and d["args"][d["args"].index("--round") + 1] == "0" and "--fallback-f" not in d["args"]
    assert plan[4]["procs"] == 3 and "--shards" in plan[4]["args"]
    pf = EV.c010_plan(speeds=sp, fallback_f=True)
    assert all(p["branch"].endswith("_F") and "--fallback-f" in p["args"] for p in pf)
    assert len(EV.c010_commands(speeds=sp)) == 8
    s0, src = EV.registered_speeds(str(ROOT / "results" / "v3" / "r9" / "nonexistent.json"))
    assert s0["deer"] == pytest.approx(11_900 / 2.3) and "어림" in src


def test_c0_state_checks_gamma(tmp_path, cfg, jcfg):
    """C0-10 γ 를 C0_STATE 에 적으면 judge·mixed·check·리그가 YAML 의 train.ppo.gamma 와 견준다."""
    sp = tmp_path / "C0_STATE.json"
    sp.write_text(json.dumps(dict(values={"C0-10": float(cfg["train"]["ppo"]["gamma"])}, f_enabled=False)), encoding="utf-8")
    assert EV.check_c0_state(cfg, jcfg, "t", sp) is not None
    sp.write_text(json.dumps(dict(values={"C0-10": 0.5}, f_enabled=False)), encoding="utf-8")
    with pytest.raises(SystemExit, match="C0-10"):
        EV.check_c0_state(cfg, jcfg, "t", sp)


def test_judge_verdict_l0_main_criterion_and_sentence():
    def batch(end, coexist=0.8):
        return dict(population=dict(coexist_share=coexist, end_worlds=end, block_share=0.5, rule_backed_block=True),
                    j3=dict(J3=True, ok={}, insufficient={}), anomaly=dict(J4=[]))
    out = dict(batches={"L_A": batch([[10, 2, 5], [10, 2, 5]])}, long={}, variants={})
    v = EV.judge_verdict(out, {})
    assert v["branches"]["A"]["rule_backed"] is None and v["branches"]["A"]["rule_backed_block"] is True
    out["variants"]["L0"] = {"L_A": batch([[11, 2, 5], [10, 2, 5]])}
    v = EV.judge_verdict(out, {})
    assert v["branches"]["A"]["rule_backed"] is False and v["branches"]["A"]["l0_change"]["deer"] == pytest.approx(0.05)
    out["variants"]["L0"] = {"L_A": batch([[10, 2, 7], [10, 2, 6]])}
    v = EV.judge_verdict(out, {})
    assert v["branches"]["A"]["rule_backed"] is True
    s = EV.sentence(True, True, True, True, dict(verdict=v))
    assert "상한이 받쳤다" in s and "boar" in s
    assert "L0 짝 판이 없어" in EV.sentence(True, True, True, None, None)


def test_shield_time_shift_baseline(jcfg):
    """방패 우연 기준 = 같은 세계 450 스텝 전 성체 멧돼지 자리: 450 스텝 전에는 기준을 세지 않고 그 뒤에만 센다."""
    fn = EV.spec_fn(jcfg, EV.rule_specs(), {})
    r = C.run(jcfg, [44355], 440, fn, scenes=True)
    assert r["an_shield"][:, 2].sum() == 0 and r["an_shield"][:, 0].sum() > 0
    r = C.run(jcfg, [44355], 1000, fn, scenes=True)
    sh = r["an_shield"].sum(0)
    assert sh[2] > 0 and sh[2] < sh[0]
    a = C.anomaly_metrics(r)
    assert math.isnan(a["shield"]) or a["shield"] == pytest.approx((sh[1] / sh[0]) / (sh[3] / sh[2]))


# --------------------------------------------------------------------------- #
# 밤 창 (STATUS 5절) · 리그 · 밤 실행기
# --------------------------------------------------------------------------- #

T = lambda h, m=0, d=12: dt.datetime(2026, 11, d, h, m)  # noqa: E731


def test_window_parse_wrap_and_fit():
    win = LG.parse_window("22:00-09:00")
    assert win == (22 * 60, 9 * 60) and LG.window_length_s(win) == 11 * 3600
    assert LG.current_window(T(23, 30), win) == (T(22), T(9, 0, 13))
    assert LG.current_window(T(3), win) == (T(22, 0, 11), T(9))
    assert LG.current_window(T(9, 0), win) is None and LG.current_window(T(15), win) is None
    assert LG.next_window_start(T(15), win) == T(22) and LG.next_window_start(T(23), win) == T(22, 0, 13)
    assert LG.window_check(T(23), win, 4 * 3600)[0]
    ok, why = LG.window_check(T(5, 30), win, 4 * 3600)                  # 05:30 + 4 h > 09:00 → 다음 창
    assert not ok and "창 끝 09:00" in why and "11-12 22:00" in why
    assert LG.window_check(T(5, 0), win, 4 * 3600)[0]                   # 정확히 09:00 에 끝 = 들어감
    assert not LG.window_check(T(12), win, 60)[0]
    assert LG.window_check(T(22, 10), win, 12 * 3600)[0] and not LG.window_check(T(23, 0), win, 12 * 3600)[0]   # 창보다 긴 묶음: 창 시작 30 분 안만
    day = LG.parse_window("09:00-18:00")
    assert LG.current_window(T(12), day) == (T(9), T(18)) and LG.current_window(T(20), day) is None
    for bad in ("22:00", "25:00-09:00", "22:00-22:00", "a-b", "22:60-09:00", "22:00-09:-1", "24:00-09:00", "22:00:00-09:00"):
        with pytest.raises(ValueError):
            LG.parse_window(bad)


def test_launch_gate_unreal_memory():
    win = LG.parse_window("22:00-09:00")
    GB = LG.GB
    assert LG.launch_gate(T(23), win, 3600, [], 20 * GB, 4, 0.5) is None
    assert "언리얼" in LG.launch_gate(T(23), win, 3600, ["UnrealEditor.exe(31832)"], 20 * GB, 4, 0.5)
    assert "커밋 메모리" in LG.launch_gate(T(23), win, 3600, [], 8 * GB, 4, 0.5)          # 1.5 × 0.5 × 4 + 6 = 9 GB
    assert LG.launch_gate(T(23), win, 3600, [], int(9.01 * GB), 4, 0.5) is None
    assert "밤 창 밖" in LG.launch_gate(T(12), win, 3600, [], 20 * GB, 4, 0.5)
    assert LG.launch_gate(T(12), None, 3600, [], 20 * GB, 4, 0.5) is None                 # 점검 --check-anytime
    assert "livecodingconsole" in LG.UNREAL_NAMES and "msbuild" in LG.UNREAL_NAMES


def test_league_precheck_and_estimate(tmp_path, monkeypatch):
    """리그 묶음 시작 조건: 어림 = 등록 결정 ÷ 등록 속도 × 1.1 (speed_dps), 없으면 벽시계 상한 / 2. 시계·프로세스·메모리를 가짜로."""
    dj = tmp_path / "dec.json"
    dj.write_text(json.dumps({"round0": dict(deer=10_000_000, boar=1, wolf=1), "later": dict(deer=1, boar=1, wolf=1),
                              "speed_dps": {"round0": dict(deer=1000.0, boar=1.0, wolf=1.0), "later": dict(deer=1.0, boar=1.0, wolf=1.0)}}),
                  encoding="utf-8")
    monkeypatch.setattr(EV, "OUT_CALIB", tmp_path / "calib")
    args = LG.build_parser().parse_args(["--decisions-json", str(dj), "--state", str(tmp_path / "st.json"), "--out", str(tmp_path),
                                         "--log-dir", str(tmp_path / "logs")])
    lg = LG.League(args)
    spec = dict(round=0, species="deer", decisions=10_000_000, wall_hours=7.0)
    assert lg.est_seconds(spec) == pytest.approx(10_000_000 / 1000.0 * 1.1)
    lg.speeds = None
    assert lg.est_seconds(spec) == pytest.approx(3.5 * 3600)
    lg.clock = lambda: T(6)
    lg._unreal = lambda: []
    lg._free = lambda: 30 * LG.GB
    assert "창 끝" in lg.precheck(1, lg.est_seconds(spec))                   # 06:00 + 3.5 h > 09:00
    lg.clock = lambda: T(22, 30)
    assert lg.precheck(1, lg.est_seconds(spec)) is None
    lg._unreal = lambda: ["ShaderCompileWorker.exe(1)"]
    assert "언리얼" in lg.precheck(1, lg.est_seconds(spec))
    lg.note_wait("시험 기다림")
    assert json.loads((tmp_path / "st.json").read_text(encoding="utf-8"))["waiting"]["reason"] == "시험 기다림"
    assert "리그 기다림: 시험 기다림" in (tmp_path / "logs" / "progress.md").read_text(encoding="utf-8")


def test_night_after_choice_and_yaml(tmp_path):
    st = dict(attempt="base")
    assert NR.after_choice(dict(gamma=0.997, action="pass"), st, {})[0] == "league"
    assert NR.after_choice(dict(gamma=None, action="enable_F_and_rerun_both"), st, {})[0] == "train"
    nxt, why = NR.after_choice(dict(gamma=None, action="enable_F_and_rerun_both"), st, dict(f_enabled=True))
    assert nxt == "stopped" and "C0-11" in why                              # F 는 한 번만 (C0-11 에서 이미 걸었으면 멈춤)
    assert NR.after_choice(dict(gamma=None, action="enable_F_and_rerun_both"), dict(attempt="F"), {})[0] == "stopped"
    assert NR.after_choice(dict(gamma=0.99, action="wolf_round0_first10M_always_eat_100"), st, {})[0] == "stopped"
    assert NR.after_choice(dict(gamma=None, action="ask_user", why="x"), st, {})[0] == "stopped"
    txt = CFG.read_text(encoding="utf-8")
    new = NR.set_yaml_values(txt, gamma=0.99, fallback_f=True)
    p = tmp_path / "v3_r9.yaml"
    p.write_text(new, encoding="utf-8")
    c = B.load_r9_config(p)
    assert c["train"]["ppo"]["gamma"] == 0.99 and c["reward"]["fallback_f"]["enabled"] is True
    assert sum(1 for a, b in zip(txt.split("\n"), new.split("\n")) if a != b) == 2 and len(txt.split("\n")) == len(new.split("\n"))
    assert NR.set_yaml_values(txt, gamma=0.997, fallback_f=False).split("\n") == txt.split("\n")


def test_night_dry_run_and_resume(tmp_path, capsys):
    """dry-run 은 계획만 찍고(띄우지 않음, 상태 파일 안 씀). 끝 기록(stop target·snapshots)이 있는 묶음은 '끝남', stop cut 은 다시 돌 것."""
    stp = tmp_path / "night.json"
    base = ["--state", str(stp), "--c010-out", str(tmp_path / "c010"), "--calib-dir", str(tmp_path / "calib"), "--log-dir", str(tmp_path / "logs"),
            "--decisions-json", str(tmp_path / "none.json")]
    assert NR.main(base + ["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "r9_c010_g0997_deer" in out and "r9_c010_g099_wolf" in out and "밤 창 22:00-09:00" in out and "league_r9.py" in out
    assert "보정 관문 상태" in out and not stp.exists() and not (tmp_path / "logs").exists()
    nr = NR.Night(NR.build_parser().parse_args(base + ["--dry-run"]))
    plan = nr.plan()
    s0 = plan[0]
    bdir = tmp_path / "c010" / s0["branch"]
    bdir.mkdir(parents=True)
    npz = bdir / "deer_r0_20000000.npz"
    npz.write_bytes(b"x")
    (bdir / f"{s0['run']}.json").write_text(json.dumps(dict(stop="target", snapshots=[dict(npz=str(npz), decisions=20_000_000)])), encoding="utf-8")
    assert nr.finished(s0) == "done" and nr.brain_paths(0.997) == {"-:deer": str(npz)}
    (bdir / f"{s0['run']}.json").write_text(json.dumps(dict(stop="cut", snapshots=[])), encoding="utf-8")
    assert nr.finished(s0) == "cut"
    (bdir / f"{s0['run']}.json").write_text(json.dumps(dict(stop="error", snapshots=[])), encoding="utf-8")
    assert nr.finished(s0) == "failed"
    nr.clock = lambda: T(12)
    nr._unreal = lambda: []
    nr._free = lambda: 30 * LG.GB
    assert "밤 창 밖" in nr.gate(4, 3600)
    assert nr.gate(2, 0.0, window=False) is None                           # 잼은 학습이 아니라 창과 무관
    assert nr.gates_confirmed() is not None and nr.decisions_registered() is not None
    (tmp_path / "calib").mkdir()
    (tmp_path / "calib" / "C0_STATE.json").write_text(json.dumps(dict(values={}, history=[dict(phase="confirm", status="confirmed")])),
                                                     encoding="utf-8")
    assert nr.gates_confirmed() is None


# --------------------------------------------------------------------------- #
# S′ 검토 고침 (11-12): 확인 단계 되돌림, 시드 범위, 도망 정의, 밤 실행기 멈춤·이어 감·C0 값 확인·--config
# --------------------------------------------------------------------------- #

def test_confirm_mixed_fail_does_not_store_unmeasured_value(tmp_path, monkeypatch):
    """확인 단계에서 고칠 수 있는 관문(C0-7)과 고칠 수 없는 관문(C0-1)이 함께 떨어지면 값·고침 표시를 바꾸지 않고 제안만 남긴다."""
    def mk(ok):
        return lambda ctx, v=None: dict(value=v, ok=ok, j2_primary="short", ok_with_F=ok, direction=None)
    for g in list(EV.MEASURE):
        monkeypatch.setitem(EV.MEASURE, g, mk(True))
    monkeypatch.setitem(EV.MEASURE, "C0-7", mk(False))
    monkeypatch.setitem(EV.MEASURE, "C0-1", mk(False))
    st = dict(values={"C0-5": 1.0, "C0-7": 0.002, "C0-2": [0.9, 1.05], "C0-3": 0.25}, fixed={}, f_enabled=False, j2_primary="short", history=[])
    sp = tmp_path / "C0_STATE.json"
    sp.write_text(json.dumps(st), encoding="utf-8")
    rc = EV.main(["calibrate", "--phase", "confirm", "--state", str(sp), "--out", str(tmp_path), "--seeds-train", "44380", "44381",
                  "--seeds-judge", "44382", "44383"])
    s2 = json.loads(sp.read_text(encoding="utf-8"))
    assert rc == 2 and s2["history"][-1]["status"] == "ask_user"
    assert s2["values"]["C0-7"] == 0.002 and not s2["fixed"].get("C0-7")
    assert s2["proposed"][-1]["proposed"]["C0-7"] != 0.002 and set(s2["proposed"][-1]["fails"]) == {"C0-7", "C0-1"}
    monkeypatch.setitem(EV.MEASURE, "C0-1", mk(True))                    # 고칠 수 있는 관문만 떨어지면 한 번 고치고 다시 잰다
    sp.write_text(json.dumps(st), encoding="utf-8")
    EV.main(["calibrate", "--phase", "confirm", "--state", str(sp), "--out", str(tmp_path), "--seeds-train", "44380", "44381",
             "--seeds-judge", "44382", "44383"])
    s3 = json.loads(sp.read_text(encoding="utf-8"))
    assert s3["values"]["C0-7"] != 0.002 and s3["fixed"]["C0-7"]


def test_calib_seed_ranges_and_dev_defaults(capsys):
    """보정 관문은 점검 44200~44299·학습 풀 43000~43999·판정 시드를 거부한다. leak·scenes·anomaly 기본은 스모크 44180~44199, 고르기 시드면 경고."""
    for bad in ([44200, 44201], [43000], [44850]):
        with pytest.raises(C.JudgeSeedError):
            C.assert_calib_seeds(bad, "t")
    C.assert_calib_seeds([44000, 44049, 44100, 44179, 44180, 44199, 44350, 44399], "t")
    p = EV.build_parser()
    for nm in ("leak", "scenes", "anomaly"):
        assert p.parse_args([nm]).seeds == list(C.SEED_RANGES["smoke"])
    assert C.warn_calib_seeds([44000, 44001], "t") and "경고" in capsys.readouterr().out
    assert not C.warn_calib_seeds([44180, 44199], "t")


def test_flee_is_run_only():
    """S′: SHELTER 는 제자리 서기 — 8-3 장면 지표·학습 기록의 도망은 뛰기만."""
    assert B.SHELTER not in C.FLEE_ACTIONS and set(C.FLEE_ACTIONS) == set(range(B.RUN_FIRST, B.RUN_LAST + 1))


def test_c0_state_skip_gates_and_f(tmp_path, cfg, jcfg):
    sp = tmp_path / "C0_STATE.json"
    sp.write_text(json.dumps(dict(values={"C0-10": 0.5}, f_enabled=True)), encoding="utf-8")
    with pytest.raises(SystemExit):
        EV.check_c0_state(cfg, jcfg, "t", sp)
    assert EV.check_c0_state(cfg, jcfg, "t", sp, skip_gates=("C0-10",), skip_f=True) is not None


def _night(tmp_path, *extra):
    base = ["--state", str(tmp_path / "night.json"), "--c010-out", str(tmp_path / "c010"), "--calib-dir", str(tmp_path / "calib"),
            "--log-dir", str(tmp_path / "logs"), "--decisions-json", str(tmp_path / "dec.json"), "--poll", "0"]
    nr = NR.Night(NR.build_parser().parse_args(base + list(extra)))
    nr.clock = lambda: T(12)                                              # 창 밖 — 학습은 띄워지지 않는다
    nr._unreal = lambda: []
    nr._free = lambda: 30 * LG.GB
    return nr


def test_night_stop_kinds_and_resume(tmp_path, cfg):
    """띄우기 전 조건 멈춤은 단계를 바꾸지 않고, 조건을 맞추면 다시 띄울 때 학습 단계로 간다(학습은 가짜 — 띄우지 않는다).
    일시 멈춤은 앞 단계부터, 사람 확인 멈춤은 --resume-from 이 있어야 이어 간다."""
    nr = _night(tmp_path)
    assert nr.run() == 2
    st = json.loads((tmp_path / "night.json").read_text(encoding="utf-8"))
    assert st["phase"] == "train" and st["stop_kind"] == "precondition" and "보정 관문 상태" in st["note"]
    (tmp_path / "calib").mkdir(exist_ok=True)
    (tmp_path / "calib" / "C0_STATE.json").write_text(json.dumps(dict(values={"C0-5": 9.0}, f_enabled=False,
                                                                      history=[dict(phase="confirm", status="confirmed")])), encoding="utf-8")
    (tmp_path / "dec.json").write_text(json.dumps({"speed_dps": {"round0": dict(deer=5000.0, boar=2000.0, wolf=2000.0)}}), encoding="utf-8")
    nr = _night(tmp_path)
    assert nr.run() == 2                                                  # C0-5 9.0 이 YAML 에 없음 → 학습 안 띄움
    st = json.loads((tmp_path / "night.json").read_text(encoding="utf-8"))
    assert st["phase"] == "train" and "C0-5" in st["note"]
    (tmp_path / "calib" / "C0_STATE.json").write_text(json.dumps(dict(values={"C0-5": float(cfg["food"]["root"]["regen_q"])},
                                                                      f_enabled=False, history=[dict(phase="confirm", status="confirmed")])),
                                                      encoding="utf-8")
    nr = _night(tmp_path)
    assert nr.prechecks() is None
    seen = []

    def fake_train():
        seen.append("train")
        nr.stop("잼 rc 1 (가짜)", kind="transient")
        return False
    nr.train = fake_train
    assert nr.run() == 2 and seen == ["train"]
    st = json.loads((tmp_path / "night.json").read_text(encoding="utf-8"))
    assert st["phase"] == "stopped" and st["stop_kind"] == "transient" and st["phase_before"] == "train"
    nr = _night(tmp_path)
    assert nr.resume() is None and nr.state["phase"] == "train"         # 일시 멈춤 → 앞 단계부터
    nr.state["runs"] = {"r9_c010_g0997_deer": dict(status="running", attempts=3)}
    nr.stop("NaN (가짜)")
    nr = _night(tmp_path)
    why = nr.resume()
    assert why and "--resume-from" in why and nr.state["phase"] == "stopped"
    nr = _night(tmp_path, "--resume-from", "train")
    assert nr.resume() is None and nr.state["phase"] == "train" and nr.state["runs"]["r9_c010_g0997_deer"]["attempts"] == 0


def test_night_passes_config_everywhere(tmp_path):
    nr = _night(tmp_path, "--config", "configs/v3_r9.yaml")
    for s in nr.plan():
        assert s["args"][s["args"].index("--config") + 1] == "configs/v3_r9.yaml"
    la = nr.league_args()
    assert la[la.index("--config") + 1] == "configs/v3_r9.yaml"
