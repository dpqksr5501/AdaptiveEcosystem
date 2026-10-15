"""v3 R3 관문 도구 (사전 등록 results/v3/r3/PREREG.md 16절): R3 니치 규칙(repertoire_rules R3 묶음)·교사 FSM_R3·관문 도구
results/v3/r3/invasion_r3.py·결정적 확인표 chase_r3.py·eval_v3 --u-def r3·train_v3 R3_EARLY_PI·measure-pi r3·H13 출처 표시·warmstart_v3
R3 기본값·공통 도구 r3_tools.

시드: 도구 점검 범위 33080~33099 만 쓴다(사전 등록 2절). 관문 판정 15000~15039·최종 판정 10300~10319 는 거부되는지만 본다(돌리지 않는다).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import importlib.util
import json
import subprocess
import sys

import numpy as np
import pytest

import r3_tools as rt
import repertoire_rules as rr
from env.config import ROOT
from env_v2 import rep_policy as rp
from env_v2 import repertoire as rep
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.world import World, obs_names

R3_ON = ROOT / "configs" / "v3_r3_on.yaml"
R3 = ROOT / "configs" / "v3_r3.yaml"
R1B = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
GATE_PY = ROOT / "results" / "v3" / "r3"
G, F, H, Z, S = rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP
OLD_RULES_COMMIT = "f6e8b6e"            # R3 규칙을 더하기 전 커밋 — R0·R2 규칙의 스펙·결과가 그대로인지 견준다

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size", "ignore::RuntimeWarning")


@pytest.fixture(scope="module")
def c3():
    return load_v2_config(R3_ON)


def _inv():
    if str(GATE_PY) not in sys.path:
        sys.path.insert(0, str(GATE_PY))
    import invasion_r3

    return invasion_r3


def _obs(cfg, rows):
    """R3 규칙 관측 행: s(감지)·d·a·c·E·vis·rec(threat_recency)·F(지금 FLEE)."""
    names = list(obs_names(cfg))
    o = np.zeros((len(rows), len(names)), dtype=np.float32)
    for i, r in enumerate(rows):
        o[i, names.index("pred_count")] = 1.0 / 8.0 if r.get("s") else 0.0
        o[i, names.index("pred_dist")] = r.get("d", 20.0) / cfg.see_r if r.get("s") else 1.0
        o[i, names.index("pred_approach")] = r.get("a", 0.5)
        o[i, names.index("cover_dist")] = r.get("c", 20.0) / cfg.obs_cover_norm
        o[i, names.index("energy")] = r.get("E", 0.6)
        o[i, names.index("visibility")] = r.get("vis", 1.0)
        o[i, names.index("threat_recency")] = 1.0 if r.get("s") else r.get("rec", 0.0)
        o[i, names.index("beh_flee")] = 1.0 if r.get("F") else 0.0
        o[i, names.index("beh_graze")] = 0.0 if r.get("F") else 1.0
    return o


def _cond(cfg, x, mode, rows, cal=0, theta=4.0, approach=0.9, base=None):
    spec = rr.r3_wrap(cfg, x, mode, theta=theta, approach=approach, cal=cal, sleep=x in rr.R3_SLEEP_X)
    o = _obs(cfg, rows)
    f = rr.features_of_obs(o, spec)
    b = np.full(len(rows), G) if base is None else np.asarray(base)
    return rr.r3_cond(x, mode, f, spec["niche"], theta, approach, b)


# --------------------------------------------------------------------- #
# 규칙 (repertoire_rules R3 묶음)
# --------------------------------------------------------------------- #


def test_r3_constants_match_contract(c3):
    """관측 계약 값은 마스크와 같다. 관문 표·FSM 줄·U 이름은 r3_tools 와 같다. 사전 등록 5-1 표의 문턱 몇 개."""
    assert rr.R3_RECENCY == rp.THREAT_RECENCY_OBS
    assert rr.R3_HIDE_C == pytest.approx(rp.HIDE_COVER_OBS * c3.obs_cover_norm)
    assert rt.FSM_GATES == rr.FSM_R3_LINES and rt.U_GATES == rr.R3_U_GATE
    assert set(rr.R3_X) == {"keep", "keep_hide", "run", "leave", "crouch", "shelter_all", "camp", "early", "sleep_r3", "camp_sleep"}
    assert rr.R3_NICHES["keep"] == dict(app=0.6, d=10.0, x_app=0.5, x_d=8.0)
    assert rr.R3_CAL1 == {"keep": dict(app=0.75, d=8.0), "keep_hide": dict(app=0.75, d=8.0), "run": dict(c=4.0),
                          "leave": dict(e=0.2), "early": dict(d_hi=7.0, app=0.62)}
    assert rr.r3_allowed(c3) == ("graze", "flee", "hide") and rr.r3_allowed(c3, sleep=True) == ("graze", "flee", "hide", "sleep")
    with pytest.raises(ValueError, match="보정 1 이 없다"):
        rr.r3_params("crouch", 1)
    with pytest.raises(ValueError, match="niche 모드만"):
        rr.r3_wrap(c3, "camp", "out")
    with pytest.raises(ValueError, match="θ·a"):
        rr.r3_wrap(c3, "early", "niche")
    with pytest.raises(ValueError, match="묶음 B"):
        rr.r3_wrap(c3, "sleep_r3", "niche")


CASES = [
    # (규칙, 모드, 관측, 기대, 보정). 관측은 float32 이고 규칙은 float64 로 바꾼 뒤 × 20 한다(R0·R2 규칙과 같다) — 경계 값이 float32 로 딱
    # 떨어지지 않는 문턱(6·8·4·0.7·0.9·0.35 등)은 경계 바로 안팎(±0.01, ±0.005)으로 본다. 딱 떨어지는 경계(10·15·0.5·0)는 그대로 본다
    ("keep", "niche", dict(F=1, s=1, a=0.605, d=9.99, c=1), True, 0),
    ("keep", "niche", dict(F=1, s=1, a=0.595, d=9.9, c=1), False, 0),
    ("keep", "niche", dict(F=1, s=1, a=0.65, d=10.0, c=1), False, 0),
    ("keep", "niche", dict(F=1, s=1, a=0.65, d=5.0, c=0), False, 0),
    ("keep", "niche", dict(F=0, s=1, a=0.95, d=5.0, c=1), False, 0),
    ("keep", "niche", dict(F=1, s=1, a=0.7, d=9.0, c=1), False, 1),
    ("keep", "niche", dict(F=1, s=1, a=0.755, d=7.99, c=1), True, 1),
    ("keep", "out", dict(rec=0.205, c=1), True, 0),
    ("keep", "out", dict(rec=0.195, c=1), False, 0),
    ("keep", "out", dict(s=1, c=1), False, 0),
    ("keep", "cross", dict(F=1, s=1, a=0.49, d=8.01, c=1), True, 0),
    ("keep", "cross", dict(F=1, s=1, a=0.5, d=8.01, c=1), False, 0),
    ("keep", "cross", dict(F=1, s=1, a=0.3, d=7.99, c=1), False, 0),
    ("run", "niche", dict(s=1, c=5.99, d=6.01), True, 0),
    ("run", "niche", dict(s=1, c=6.01, d=6.01), False, 0),
    ("run", "niche", dict(s=1, c=5.99, d=5.99), False, 0),
    ("run", "niche", dict(s=1, c=0.0, d=9.0), False, 0),
    ("run", "niche", dict(s=1, c=4.01, d=9.0), False, 1),
    ("run", "niche", dict(s=1, c=3.99, d=9.0), True, 1),
    ("run", "out", dict(rec=0.5, c=14.99), True, 0),
    ("run", "out", dict(rec=0.5, c=15.0), False, 0),
    ("leave", "niche", dict(c=0, rec=0.5, E=0.34), True, 0),
    ("leave", "niche", dict(c=0, s=1, d=10.0, E=0.34), True, 0),
    ("leave", "niche", dict(c=0, s=1, d=9.99, E=0.34), False, 0),
    ("leave", "niche", dict(c=0, rec=0.5, E=0.355), False, 0),
    ("leave", "niche", dict(c=0, rec=0.1, E=0.1), False, 0),
    ("leave", "niche", dict(c=0, rec=0.5, E=0.25), False, 1),
    ("leave", "niche", dict(c=0, rec=0.5, E=0.19), True, 1),
    ("leave", "out", dict(c=0, s=1, d=5.99, E=0.9), True, 0),
    ("leave", "out", dict(c=0, s=1, d=6.01, E=0.1), False, 0),
    ("leave", "cross", dict(c=0, rec=0.5, E=0.71), True, 0),
    ("leave", "cross", dict(c=0, rec=0.5, E=0.695), False, 0),
    ("leave", "cross", dict(c=0, s=1, d=12.0, E=0.9), False, 0),
    ("crouch", "niche", dict(c=0, s=1, d=5.99), True, 0),
    ("crouch", "niche", dict(c=0, s=1, d=6.01), False, 0),
    ("crouch", "niche", dict(c=1, s=1, d=3.0), False, 0),
    ("crouch", "out", dict(c=0, rec=0.5, E=0.695), True, 0),
    ("crouch", "out", dict(c=0, rec=0.5, E=0.71), False, 0),
    ("crouch", "cross", dict(c=0, s=1, d=8.01, a=0.69), True, 0),
    ("crouch", "cross", dict(c=0, s=1, d=8.01, a=0.705), False, 0),
    ("shelter_all", "niche", dict(rec=0.3, c=14.99), True, 0),
    ("shelter_all", "niche", dict(rec=0.3, c=15.0), False, 0),
    ("shelter_all", "niche", dict(rec=0.1, c=3.0), False, 0),
    ("camp", "niche", dict(c=0, rec=0.3), True, 0),
    ("camp", "niche", dict(c=0, rec=0.1), False, 0),
    ("early", "niche", dict(s=1, d=4.01, a=0.605, c=1), True, 0),
    ("early", "niche", dict(s=1, d=3.99, a=0.65, c=1), False, 0),
    ("early", "niche", dict(s=1, d=8.01, a=0.7, c=1), False, 0),
    ("early", "niche", dict(s=1, d=6.0, a=0.905, c=1), False, 0),
    ("early", "niche", dict(F=1, s=1, d=6.0, a=0.7, c=1), False, 0),
    ("early", "niche", dict(s=1, d=7.01, a=0.7, c=1), False, 1),
    ("early", "niche", dict(s=1, d=6.9, a=0.625, c=1), True, 1),
    ("early", "niche", dict(s=1, d=6.9, a=0.615, c=1), False, 1),
    ("early", "out", dict(s=1, d=12.01, a=0.54, c=1), True, 0),
    ("early", "out", dict(s=1, d=11.99, a=0.54, c=1), False, 0),
    ("early", "cross", dict(s=1, d=5.0, a=0.54, c=1), True, 0),
    ("early", "cross", dict(s=1, d=5.0, a=0.555, c=1), False, 0),
    ("early", "cross", dict(s=1, d=7.5, a=0.5, c=1), True, 0),
    ("early", "cross", dict(s=1, d=7.5, a=0.5, c=1), True, 1),      # 보정 1 은 니치만 좁힌다 — 교차(θ < d < 8)는 그대로(9-1)
    ("early", "cross", dict(s=1, d=8.01, a=0.5, c=1), False, 1),
    ("sleep_r3", "niche", dict(vis=0.6, c=0, E=0.5), True, 0),
    ("sleep_r3", "niche", dict(vis=0.6, c=0, E=0.5, rec=0.3), False, 0),
    ("sleep_r3", "niche", dict(vis=0.61, c=0, E=0.5), False, 0),
    ("sleep_r3", "out", dict(vis=0.9, c=5), True, 0),
    ("sleep_r3", "out", dict(vis=0.89, c=5), False, 0),
    ("sleep_r3", "cross", dict(vis=0.5, c=5, E=0.6), True, 0),
    ("sleep_r3", "cross", dict(vis=0.5, c=0, E=0.6), False, 0),
]


@pytest.mark.parametrize("x, mode, row, want, cal", CASES)
def test_r3_niche_conditions(c3, x, mode, row, want, cal):
    """사전 등록 5-1 니치 표의 경계 (θ 4, a* 0.9)."""
    assert bool(_cond(c3, x, mode, [row], cal=cal)[0]) is want


def test_run_cross_needs_base_flee(c3):
    rows = [dict(s=1, c=10.01, d=9.0), dict(s=1, c=10.01, d=9.0), dict(s=1, c=10.0, d=9.0), dict(s=1, c=15.0, d=9.0)]
    np.testing.assert_array_equal(_cond(c3, "run", "cross", rows, base=[F, G, F, F]), [True, False, False, False])


def test_r3_rule_actions_slots_and_feasibility(c3):
    """R3Rule: 슬롯 제한, 개체마다 다른 행동(keep_hide·camp_sleep), 고를 수 있는 자리 거르기(허용 ∧ 가능 — 학습 마스크와 같은 함수)."""
    rows = [dict(F=1, s=1, a=0.7, d=8.0, c=5.0), dict(F=1, s=1, a=0.7, d=8.0, c=16.0), dict(F=1, s=1, a=0.7, d=8.0, c=5.0)]
    o = _obs(c3, rows)
    w = rr.r3_wrap(c3, "keep_hide", "niche", slots=[0, 1])
    m, act = rr.R3Rule(None, w).target(o, np.full(3, G))
    np.testing.assert_array_equal(m, [True, True, False])                 # 슬롯 2 는 침입이 아니다
    np.testing.assert_array_equal(act[:2], [H, F])                        # c < 15 면 HIDE, 아니면 FLEE
    # camp_sleep(묶음 B): K 면 HIDE, ¬K 면 SLEEP(판 4 — SLEEP 가능 = ¬K)
    o2 = _obs(c3, [dict(c=0, rec=0.5), dict(c=0, rec=0.0), dict(c=3, rec=0.0)])
    m2, a2 = rr.R3Rule(None, rr.r3_wrap(c3, "camp_sleep", "niche", sleep=True)).target(o2, np.full(3, G))
    np.testing.assert_array_equal(m2, [True, True, False])
    np.testing.assert_array_equal(a2[:2], [H, S])
    # 거르기: 허용 목록에 hide 가 없으면 HIDE 규칙은 덮지 않는다. 가능 칸은 rep_policy.feasible_mask 그대로(판 4 만 SLEEP 을 바꾼다)
    w3 = dict(rr.r3_wrap(c3, "shelter_all", "niche"), allowed=["graze", "flee"])
    o3 = _obs(c3, [dict(rec=0.5, c=3.0), dict(s=1, d=5.0, c=0.0)])
    assert not rr.R3Rule(None, w3).target(o3, np.full(2, G))[0].any()
    assert rr.R3Rule(None, rr.r3_wrap(c3, "shelter_all", "niche")).target(o3, np.full(2, G))[0].all()
    rng = np.random.default_rng(33080)
    ro_ = _obs(c3, [dict(s=bool(rng.random() < 0.4), d=float(rng.uniform(0, 20)), a=float(rng.random()),
                          c=float(rng.choice([0.0, rng.uniform(0, 20)])), rec=float(rng.random()), F=bool(rng.random() < 0.3))
                    for _ in range(400)])
    fa = rr.r3_feasible(ro_, rr.r3_wrap(c3, "camp", "niche"))
    want = rp.feasible_mask(ro_, obs_names(c3)) & rp.allowed_mask_of(("graze", "flee", "hide"))[None, :]
    np.testing.assert_array_equal(fa, want)
    fb = rr.r3_feasible(ro_, rr.r3_wrap(c3, "camp", "niche", sleep=True))
    kk = rr.r3_known(rr.features_of_obs(ro_, rr.r3_geo(c3)))
    np.testing.assert_array_equal(fb[:, S], ~kk)
    np.testing.assert_array_equal(fb[:, :S], want[:, :S])
    assert not fb[:, Z].any()
    # __call__: 덮은 개체만 바뀌고 나머지는 바탕 요청 그대로
    a = rr.R3Rule(lambda _o: np.full((3, 1), float(G)), w)(o)
    np.testing.assert_array_equal(a[:, 0], [H, F, G])


def test_fsm_r3_lines(c3):
    """FSM_R3 줄 순서(12-1)와 줄 켜고 끄기, 허용 ∧ 가능 밖은 GRAZE, 얼기·잠은 내지 않는다(잠 줄을 켜지 않으면)."""
    rows = [dict(c=0, s=1, d=3.0, a=0.95),            # 0 줄 1 웅크림 (줄 4 는 은신처 밖만)
            dict(c=0, rec=0.5, E=0.8),                 # 1 줄 2 배부르면 숨어 있기
            dict(c=0, rec=0.5, E=0.2),                 # 2 배고픔 → GRAZE (G3)
            dict(c=5.0, s=1, d=7.0, a=0.95),           # 3 줄 3 은신처로 (줄 4 보다 먼저)
            dict(c=9.0, s=1, d=3.0, a=0.5),            # 4 줄 4 R_base
            dict(F=1, c=9.0, s=1, d=8.0, a=0.7),       # 5 줄 5 끝까지 도망
            dict(c=9.0, s=1, d=6.0, a=0.65),           # 6 줄 6 미리 떠나기
            dict(c=9.0, s=1, d=15.0, a=0.3),           # 7 그 밖 GRAZE
            dict(vis=0.5, c=0, E=0.8)]                 # 8 밤 은신처 ¬K (잠 줄을 켜야 SLEEP)
    o = _obs(c3, rows)

    def dec(**kw):
        return rr.FsmR3(None, rr.fsm_r3_spec(c3, 4.0, 0.9, **kw)["wrap"][0]).decide(o)
    np.testing.assert_array_equal(dec(), [H, H, G, H, F, F, F, G, G])
    np.testing.assert_array_equal(dec(lines=()), [G, G, G, F, F, G, G, G, G])
    np.testing.assert_array_equal(dec(lines=("run", "keep")), [G, G, G, H, F, F, G, G, G])
    np.testing.assert_array_equal(dec(sleep=True)[8], S)
    np.testing.assert_array_equal(dec(lines=("run",), cal=("run",))[3], F)      # 보정 1: c ≤ 4 — c 5 는 줄 4 로
    with pytest.raises(ValueError, match="보정 1"):
        rr.fsm_r3_spec(c3, 4.0, 0.9, lines=("run",), cal=("keep",))
    sp = rr.fsm_r3_spec(c3, 4.0, 0.9)
    sp["wrap"][0]["allowed"] = ["graze", "flee"]                               # 허용 밖(HIDE)은 GRAZE
    d2 = rr.FsmR3(None, sp["wrap"][0]).decide(o)
    assert not (d2 == H).any() and d2[4] == F


def test_fsm_r3_and_rules_in_r3_runs(c3):
    """R3 판정 세계에서 FSM_R3·R3 규칙은 FREEZE·SLEEP 을 내지 않고, FSM_R3 는 도망을 지우지 않는다(8절 제약의 꼴)."""
    specs = {"fsm": rr.fsm_r3_spec(c3, 4.0, 0.9), "inv": rr.r3_rule_spec(c3, 4.0, 0.9, x="keep", slots=range(16)),
             "camp": rr.r3_rule_spec(c3, 4.0, 0.9, resident="camp", x="leave")}
    for name, sp in specs.items():
        w = World(rr.with_obs_extra(c3), seeds=[33080])
        pol = ro.build_policy(sp, 0)
        for _ in range(250):
            a = np.asarray(pol(w.observe()), dtype=np.float64)
            assert not np.isin(a[:, 0], (Z, S)).any(), name
            w.step(a)
        h = w._rep_hist.sum((0, 1))
        assert h[Z] == 0 and h[S] == 0
        if name == "fsm":
            assert h[F] > 0 and h[H] > 0


def test_r3_u_terms_and_probs(c3):
    """U 정의(15-3): U_KEEP·U_EARLY 의 둘째 항에서 G2 니치를 뺀다. 적중 묶음과 확률 합."""
    rows = [dict(F=1, s=1, a=0.3, d=9.0, c=5.0),        # G1 C 이자 G2 N → U_KEEP 둘째 항에서 빠진다
            dict(F=1, s=1, a=0.3, d=9.0, c=12.0),       # G1 C 만
            dict(s=1, d=6.0, a=0.5, c=5.0)]             # G6 C 이자 G2 N
    f = rr.features_of_obs(_obs(c3, rows), rr.r3_geo(c3))
    t = rr.r3_u_terms(f, 4.0, 0.9)
    np.testing.assert_array_equal(t["keep"][1], [False, True, False])
    np.testing.assert_array_equal(t["run"][0], [True, False, True])
    assert not t["early"][1].any()
    np.testing.assert_array_equal(rr.r3_u_hit("keep", np.array([H, H, F]), f), [True, True, True])
    f_in = rr.features_of_obs(_obs(c3, [dict(c=0, s=1, d=3.0)]), rr.r3_geo(c3))
    assert not rr.r3_u_hit("keep", np.array([H]), f_in)[0] and rr.r3_u_hit("hide", np.array([H]), f_in)[0]
    pi = np.array([[0.2, 0.3, 0.4, 0.0, 0.1]] * 3)
    np.testing.assert_allclose(rr.r3_u_prob("esc", pi, f), 0.7)
    np.testing.assert_allclose(rr.r3_u_prob("leave", pi, f), 0.2)
    assert tuple(t) == rr.R3_U
    # 보정 1 을 쓴 G6: U_EARLY 의 첫 항(니치)만 좁아지고 둘째 항(교차 θ < d < 8)은 그대로다
    f2 = rr.features_of_obs(_obs(c3, [dict(s=1, d=7.5, a=0.5, c=12.0), dict(s=1, d=7.5, a=0.7, c=12.0)]), rr.r3_geo(c3))
    t0, t1 = rr.r3_u_terms(f2, 4.0, 0.9), rr.r3_u_terms(f2, 4.0, 0.9, cal=("early",))
    np.testing.assert_array_equal(t0["early"][1], [True, False])
    np.testing.assert_array_equal(t1["early"][1], [True, False])
    np.testing.assert_array_equal(t0["early"][0], [False, True])
    np.testing.assert_array_equal(t1["early"][0], [False, False])


def test_r3_niche_overlaps(c3):
    """니치 겹침 표(8절): 반대 행동을 요구하는 겹침이 없다 — G3 교차 ∩ G4a(니치·밖·교차) 없음, G6 ∩ G1 없음, G5 ∩ 다른 관문(니치·교차) 없음,
    G3 니치 ∩ G4a 니치 없음."""
    rng = np.random.default_rng(33081)
    rows = []
    for _ in range(6000):
        s = bool(rng.random() < 0.5)
        rows.append(dict(s=s, d=float(rng.choice([rng.uniform(0, 14), 6.0, 8.0, 10.0])), a=float(rng.random()),
                         c=float(rng.choice([0.0, rng.uniform(0, 16)])), E=float(rng.random()), F=bool(rng.random() < 0.5),
                         rec=float(rng.choice([0.0, 0.1, 0.5])), vis=float(rng.choice([0.5, 0.75, 1.0]))))
    o = _obs(c3, rows)
    spec = rr.r3_geo(c3)
    f = rr.features_of_obs(o, spec)
    P = {x: rr.r3_params(x) for x in rr.R3_NICHES}
    b = np.full(len(rows), F)

    def C(x, m):
        return rr.r3_cond(x, m, f, P[x], 4.0, 0.9, b)
    assert not (C("leave", "cross") & (C("crouch", "niche") | C("crouch", "out") | C("crouch", "cross"))).any()
    assert not ((C("early", "niche") | C("early", "cross")) & (C("keep", "niche") | C("keep", "cross"))).any()
    g5 = C("sleep_r3", "niche") | C("sleep_r3", "cross")
    for x in ("keep", "run", "leave", "crouch", "early"):
        assert not (g5 & (C(x, "niche") | C(x, "cross"))).any(), x
    assert not (C("leave", "niche") & C("crouch", "niche")).any()


def _old_rules():
    """R3 규칙 전 커밋의 repertoire_rules (git show). git 이 없으면 시험을 건너뛴다."""
    try:
        src = subprocess.run(["git", "show", f"{OLD_RULES_COMMIT}:herbivore_rl/repertoire_rules.py"], cwd=ROOT,
                             capture_output=True, check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git 으로 옛 repertoire_rules 를 읽을 수 없다")
    spec = importlib.util.spec_from_loader("rr_old", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(src, "rr_old.py", "exec"), mod.__dict__)
    return mod


@pytest.mark.parametrize("cfg_name", ["v3_r0_on", "v3_r1_on", "v3_r2_on", "v3_r2_w7_on", "v3_r2_w8_on", "v3_r3_on"])
def test_old_rules_specs_and_masks_unchanged(cfg_name):
    """R0·R2 규칙의 스펙과 결과는 그대로다(사전 등록 16-1): 바꾸기 전 커밋의 모듈과 스펙 dict 가 같고, 실제 세계 관측에서 규칙 마스크·
    요청이 같다."""
    old = _old_rules()
    cfg = rr.with_obs_extra(load_v2_config(ROOT / "configs" / f"{cfg_name}.yaml"))
    alarm = "alarm_heard" in obs_names(cfg)
    stare = bool((cfg.v2["features"].get("stare_down") or {}).get("enabled"))
    xs = [x for x in rr.NICHES if (x not in rr.ALARM_X or alarm)]
    assert rr.rule_spec(cfg, 4.0, 0.9) == old.rule_spec(cfg, 4.0, 0.9)
    for x in xs:
        for m in (("niche",) if x in rr.AUX_X else rr.X_MODES):
            assert rr.rule_spec(cfg, 6.0, 0.75, x=x, mode=m, slots=range(16)) == old.rule_spec(cfg, 6.0, 0.75, x=x, mode=m,
                                                                                               slots=range(16)), (x, m)
    if alarm:
        assert rr.fsm_r2_spec(cfg, stare=stare) == old.fsm_r2_spec(cfg, stare=stare)
    w = World(cfg, seeds=[33082])
    pol = ro.build_policy(rr.rule_spec(cfg, 4.0, 0.9), 0)
    for t in range(120):
        o = w.observe()
        base = np.asarray(pol(o))[:, 0].astype(np.int64)
        assert (rr.BaseRule(None, rr.rule_spec(cfg, 4.0, 0.9)["wrap"][0]).decide(o)
                == old.BaseRule(None, old.rule_spec(cfg, 4.0, 0.9)["wrap"][0]).decide(o)).all()
        if t % 10 == 0:
            for x in xs:
                for m in (("niche",) if x in rr.AUX_X else rr.X_MODES):
                    sp = rr.x_wrap(cfg, x, m)
                    np.testing.assert_array_equal(rr.XRule(None, sp).mask(o, base), old.XRule(None, old.x_wrap(cfg, x, m)).mask(o, base))
                    fn, fo = rr.features_of_obs(o, sp), old.features_of_obs(o, old.x_wrap(cfg, x, m))
                    assert set(fn) == set(fo)                     # R3 칸(recency·flee_now)은 R3 래퍼 스펙에만 생긴다
        w.step(base.astype(np.float64)[:, None])


# --------------------------------------------------------------------- #
# r3_tools
# --------------------------------------------------------------------- #


def test_seed_problems_and_draft(tmp_path):
    assert rt.seed_problems([20000, 32050, 33099]) == []
    assert len(rt.seed_problems([10000, 10219, 12170, 14000, 31000])) == 5
    assert rt.seed_problems([15000]) and rt.seed_problems([15000], gate=True) == []
    assert rt.seed_problems([10300]) and rt.seed_problems([10319], final=True) == []
    assert rt.seed_problems([15000], final=True) and rt.seed_problems([10300], gate=True)
    assert rt.seed_problems([40000])
    import eval_v3 as ev

    p = tmp_path / "PREREG.md"
    for title, want in (("# v3 R3 관문 사전 등록 (초안) — 얼기 없는 세계", True), ("# v3 R3 관문 사전 등록 (확정 10-20)", False)):
        p.write_text(title + "\n\n본문의 초안은 보지 않는다\n", encoding="utf-8")
        assert rt.prereg_draft(p) is want and ev.prereg_draft(p) is want
    assert rt.prereg_draft(tmp_path / "없음.md")
    assert rt.prereg_draft(GATE_PY / "PREREG.md")                 # 지금 관문 사전 등록은 초안이다 — 사전 등록 폴더 실행을 받지 않는다


def test_is_r3_world():
    for name, want in (("v3_r3_on", True), ("v3_r3", True), ("v3_r1_on", False), ("v3_r2_on", False), ("v3_real1_on", False),
                       ("v3_real1_night_on", False)):
        cfg = load_v2_config(ROOT / "configs" / f"{name}.yaml")
        assert rt.is_r3_world(cfg) is want, name
        assert World(cfg, seeds=[33083])._r3 is want, name


def test_setup_from_final():
    """9-2 표: 줄 = 통과·조건부 통과, 판정 U = 완전 통과만, P3 = G1 통과·조건부, HIDE 하한 = G2·G4a 가운데 하나, SLEEP = G5 통과 & G0b-S 손해 확인."""
    search = {"best": {"theta": 6.0, "approach": 0.75}}
    final = {"gates": {"keep": {"verdict": "conditional_pass", "cal": 1}, "run": {"verdict": "fail", "cal": 0},
                       "leave": {"verdict": "pass", "cal": 1}, "crouch": {"verdict": "insufficient"},
                       "early": {"verdict": "pass"}, "shelter_all": {"verdict": "exploit_loss"},
                       "sleep_r3": {"verdict": "pass"}, "camp_sleep": {"verdict": "exploit_risk"}}}
    s = rt.setup_from_final(final, search)
    assert s["complete"] and (s["theta"], s["approach"]) == (6.0, 0.75)
    assert s["lines"] == ("leave", "keep", "early") and s["cal"] == ("leave", "keep")
    assert s["u_judged"] == ("esc", "leave", "early") and set(s["u_report"]) == {"keep", "run", "hide"}
    assert s["p3"] and not s["hide_floor"] and not s["sleep"]
    final["gates"]["camp_sleep"]["verdict"] = "exploit_loss"
    final["gates"]["crouch"]["verdict"] = "conditional_pass"
    s2 = rt.setup_from_final(final, search)
    assert s2["sleep"] and s2["hide_floor"]
    assert not rt.setup_from_final(final, None)["complete"]
    e = rt.setup_from_final(None, None)
    assert not e["complete"] and e["theta"] is None and e["u_judged"] == ("esc",)


def test_pursuit_tracker_matches_eval_pre(c3):
    """포기율 A 의 쫓는 위협(15-2): r3_tools 추적과 eval_pre 의 Spy 가 매 스텝 같은 표적·같은 기회를 낸다(같은 세계·정책)."""
    ep = _inv().eval_pre()
    Spy = ep._spy_class()
    ws = Spy(c3, seeds=[33084])
    ws._spy_init()
    wp = rt.pursuit_world_class()(c3, seeds=[33084])
    spec = rr.rule_spec(c3, 4.0, 0.9)
    pa, pb = ro.build_policy(spec, 0), ro.build_policy(spec, 0)
    tp1 = np.full(ws.M, -1)
    tp2 = np.full(ws.M, -1)
    n_opp = 0
    for _ in range(400):
        oa, ob = ws.observe(), wp.observe()
        np.testing.assert_array_equal(oa, ob)
        purs = np.full(ws.N, np.inf)
        awake = ~ws.pred_asleep
        for tg in (tp1, tp2):
            ms = np.flatnonzero((tg >= 0) & awake)
            if len(ms):
                np.minimum.at(purs, tg[ms], np.sqrt(((ws.pred_pos[ms] - ws.pos[tg[ms]]) ** 2).sum(1)))
        np.testing.assert_array_equal(purs, wp.pursuer_dist())
        pk = wp.rep_peek()
        opp = rt.opportunities(wp, pk)
        want = pk["reads"] & (pk["behavior"] == F) & (purs < rt.PURSUE_R) & ~ws._in_cover(ws.pos)
        np.testing.assert_array_equal(opp, want)
        n_opp += int(opp.sum())
        a = np.asarray(pa(oa))
        ws.step(a)
        wp.step(np.asarray(pb(ob)))
        tp2, tp1 = tp1, ws.spy["tgt"].copy()
        np.testing.assert_array_equal(tp1, wp.tp1)
    assert n_opp > 0
    with pytest.raises(ValueError, match="pred_target"):
        rt.pursuit_world_class()(load_v2_config(ROOT / "configs" / "v3_r1_on.yaml"), seeds=[33084])


# --------------------------------------------------------------------- #
# 관문 도구 invasion_r3
# --------------------------------------------------------------------- #


def test_cells_keep_layout_and_digests(c3):
    """칸 덮기는 세계 배치를 바꾸지 않는다(3절). 설정 digest 는 사전 등록 1절 값이다(10-15 작업 트리). world_digest 식은 warmstart_v3 와 같다."""
    import warmstart_v3 as ws

    inv = _inv()
    lay = inv.layout_check([33085, 33086])
    assert set(lay) == {"33085", "33086"} and lay["33085"] != lay["33086"]
    base = inv.cell_cfg("ps0.3_pl_T600")
    for c in inv.CELLS:
        cc = inv.cell_cfg(c)
        assert cc.rand == base.rand and cc.v2["train"] == base.v2["train"]
        diff = {k for k in cc.v2["features"] if cc.v2["features"][k] != base.v2["features"][k]}
        assert diff <= {"threats", "daynight"}
        assert inv.cell_cfg(c, bundle="b").v2["train"]["repertoire"]["allowed"] == ["graze", "flee", "hide", "sleep"]
    for p in (R3_ON, R3):
        cfg = load_v2_config(p)
        assert inv.world_digest(cfg) == ws.world_digest(cfg)
    assert inv.prereg_digests() == inv.PREREG_DIGEST
    assert inv.PREREG_DIGEST["config"] in (GATE_PY / "PREREG.md").read_text(encoding="utf-8")
    assert inv.PREREG_DIGEST["world"] in (GATE_PY / "PREREG.md").read_text(encoding="utf-8")


def _row(mean, t, chg=500, cov=0.1):
    return {"rew": dict(mean=mean, t=t, n=40, mde80=0.001), "chg_f": chg, "cov_f": cov}


def _summ(x, niche, out, cross):
    s = {}
    for mode, vals in (("niche", niche), ("out", out), ("cross", cross)):
        for i, v in enumerate(vals):
            s[f"{x}|{mode}|c{i}"] = _row(*v)
    return s


def test_gate_verdicts_and_h1():
    inv = _inv()
    cells = [f"c{i}" for i in range(8)]
    good_n = [(0.001, 1.0)] * 5 + [(-0.001, -1.0)] * 3
    neg = [(-0.002, -3.0)] * 5 + [(0.0, 0.0)] * 3
    v = inv.gate_verdict(_summ("keep", good_n, neg, neg), cells, "keep")
    assert v["verdict"] == "pass" and v["c1"] and v["c2"] and v["c3"]
    v = inv.gate_verdict(_summ("keep", [(0.001, 1.0)] * 4 + [(-0.001, -1.0)] * 4, neg, neg), cells, "keep")
    assert v["verdict"] == "fail" and not v["c1"] and v["cal_eligible"]
    assert not inv.gate_verdict(_summ("crouch", [(0.001, 1.0)] * 4 + [(-0.001, -1.0)] * 4, neg, neg), cells, "crouch")["cal_eligible"]
    weak = [(0.0, 0.0)] * 8
    s = _summ("keep", good_n, neg, weak)
    for i in range(8):
        s[f"keep|cross|c{i}"]["cov_f"] = 0.01
    assert inv.gate_verdict(s, cells, "keep")["verdict"] == "low_power"
    s = _summ("keep", good_n, neg, weak)
    assert inv.gate_verdict(s, cells, "keep")["verdict"] == "fail"
    v = inv.gate_verdict(_summ("keep", good_n, weak, neg), cells, "keep")
    assert v["verdict"] == "fail" and v["human"] and not v["cal_eligible"]          # (2) 실패 → 사람이 본다
    # (1)·(2) 가 함께 떨어지면 보정하지 않고 사람이 본다(9-1 — 보정은 니치 밖 판을 바꾸지 못한다)
    v = inv.gate_verdict(_summ("keep", [(0.001, 1.0)] * 4 + [(-0.001, -1.0)] * 4, weak, neg), cells, "keep")
    assert v["verdict"] == "fail" and not v["c1"] and not v["c2"] and v["human"] and not v["cal_eligible"]
    s = _summ("keep", good_n, neg, neg)
    for i in range(4):
        s[f"keep|niche|c{i}"]["chg_f"] = 399
    assert inv.gate_verdict(s, cells, "keep")["verdict"] == "insufficient"
    s = _summ("keep", good_n, neg, neg)
    for i in range(4):
        s[f"keep|out|c{i}"]["chg_f"] = 10
    v = inv.gate_verdict(s, cells, "keep")
    assert v["verdict"] == "out_insufficient" and v["human"]
    s = _summ("keep", good_n, neg, neg)
    for i in range(4):
        s[f"keep|cross|c{i}"]["chg_f"] = 10
    v = inv.gate_verdict(s, cells, "keep")
    assert v["verdict"] == "cross_insufficient"
    h = inv.h1_verdict(v, dict(sig_neg=0, mean8=0.0001, rev_res_wins=0))
    assert h["verdict"] == "conditional_pass"
    assert inv.h1_verdict(v, dict(sig_neg=1, mean8=0.0001, rev_res_wins=0))["verdict"] == "cross_insufficient"
    assert inv.h1_verdict(v, dict(sig_neg=0, mean8=-0.0001, rev_res_wins=0))["verdict"] == "cross_insufficient"
    assert inv.h1_verdict(v, dict(sig_neg=0, mean8=0.0001, rev_res_wins=1))["verdict"] == "cross_insufficient"
    pv = inv.gate_verdict(_summ("keep", good_n, neg, neg), cells, "keep")
    assert inv.h1_verdict(pv, dict(sig_neg=3, mean8=-1, rev_res_wins=4))["verdict"] == "pass"
    ex = {f"camp|niche|c{i}": _row(-0.002, -3.0 if i < 5 else 0.0) for i in range(8)}
    assert inv.exploit_verdict(ex, cells, "camp")["verdict"] == "exploit_loss"
    ex["camp|niche|c0"] = _row(-0.001, -1.0)
    assert inv.exploit_verdict(ex, cells, "camp")["verdict"] == "exploit_risk"
    variants, skipped = inv.gate_list("a", list(inv.BUNDLE["a"]), 0.6)
    assert "early" in skipped and ("early", "niche") not in variants and ("keep_hide", "niche") in variants
    assert ("keep_hide", "out") not in variants and ("camp", "niche") in variants and ("camp", "out") not in variants


def _ns(**kw):
    inv = _inv()
    d = dict(cmd="run", bundle="a", seeds=None, steps=inv.STEPS, cells=None, grid_theta=list(inv.GRID_THETA),
             grid_approach=list(inv.GRID_APPROACH), config=inv.CONFIG, force=False, gates=None, no_t0=False, cal=0, cal_gates=[],
             x=[], stage2=False, passed=[], theta=None, approach=None)
    d.update(kw)
    return argparse.Namespace(**d)


def test_prereg_folder_guard(tmp_path, monkeypatch):
    """16-2: 초안 제목·시드·스텝·칸·격자·설정·digest·--force·관문 일부·T0 뺌·이미 있는 결과·탐색 캐시·보정 조건·pop 조건을 각각 거부한다."""
    inv = _inv()
    gate, gate_b = tmp_path / "gate", tmp_path / "gate_b"
    gate.mkdir()
    monkeypatch.setattr(inv, "GATE_DIR", gate)
    monkeypatch.setattr(inv, "GATE_B_DIR", gate_b)
    monkeypatch.setattr(inv, "OUT_DIR", {"a": gate, "b": gate_b})
    pr = tmp_path / "PREREG.md"
    pr.write_text("# v3 R3 관문 사전 등록 (초안)\n", encoding="utf-8")
    monkeypatch.setattr(inv, "PREREG", pr)
    S, Gs = inv.SEARCH_SEEDS, inv.GATE_SEEDS
    bad = inv.prereg_problems(_ns(cmd="search"), S, gate)
    assert len(bad) == 1 and "초안" in bad[0]
    pr.write_text("# v3 R3 관문 사전 등록 (확정 10-20)\n", encoding="utf-8")
    assert inv.prereg_problems(_ns(cmd="search"), S, gate) == []
    assert any("--seeds" in b for b in inv.prereg_problems(_ns(cmd="search"), Gs, gate))
    for kw, key in ((dict(steps=200), "--steps"), (dict(cells=["ps0.3_pl_T600"]), "--cells"), (dict(grid_theta=[4.0]), "격자"),
                    (dict(config="configs/v3_r1_on.yaml"), "--config"), (dict(force=True), "--force"),
                    (dict(bundle="b"), "--bundle")):
        assert any(key in b for b in inv.prereg_problems(_ns(cmd="search", **kw), S, gate)), key
    monkeypatch.setattr(inv, "PREREG_DIGEST", dict(config="000000000000", world="000000000000"))
    assert any("digest" in b for b in inv.prereg_problems(_ns(cmd="search"), S, gate))
    monkeypatch.setattr(inv, "PREREG_DIGEST", inv.prereg_digests())
    # run: 탐색 캐시가 있어야 하고 조건·digest·문턱이 같아야 한다
    bad = inv.prereg_problems(_ns(), Gs, gate)
    assert any("search.json" in b for b in bad) and len(bad) == 1
    meta = inv.search_meta(S, inv.STEPS)
    (gate / "search.json").write_text(json.dumps(dict(meta=meta, best=dict(theta=4.0, approach=0.9))), encoding="utf-8")
    assert inv.prereg_problems(_ns(), Gs, gate) == []
    assert any("--seeds" in b for b in inv.prereg_problems(_ns(), S, gate))
    assert any("--gates" in b for b in inv.prereg_problems(_ns(gates=["keep"]), Gs, gate))
    assert any("--no-t0" in b for b in inv.prereg_problems(_ns(no_t0=True), Gs, gate))
    assert any("--theta" in b for b in inv.prereg_problems(_ns(theta=6.0, approach=0.9), Gs, gate))
    assert inv.prereg_problems(_ns(theta=4.0, approach=0.9), Gs, gate) == []
    bad_meta = dict(meta, digest={c: "x" for c in meta["digest"]})
    (gate / "search.json").write_text(json.dumps(dict(meta=bad_meta, best=dict(theta=4.0, approach=0.9))), encoding="utf-8")
    assert any("탐색 캐시를 만든 뒤" in b for b in inv.prereg_problems(_ns(), Gs, gate))
    (gate / "search.json").write_text(json.dumps(dict(meta=meta, best=dict(theta=4.0, approach=0.9))), encoding="utf-8")
    (gate / "invasion.json").write_text("{}", encoding="utf-8")
    assert any("한 번 쓴다" in b for b in inv.prereg_problems(_ns(), Gs, gate))
    (gate / "invasion.json").unlink()
    # 보정: 첫 판정 gate.json 의 보정 대상만, gate/cal1/<관문>/ 에
    cal_out = gate / "cal1" / "keep"
    assert any("gate.json" in b for b in inv.prereg_problems(_ns(cal=1, cal_gates=["keep"], gates=["keep"]), Gs, cal_out))
    (gate / "gate.json").write_text(json.dumps(dict(gate={"keep": dict(cal_eligible=True, verdict="fail", complete=True,
                                                                         c1=False, c2=True),
                                                          "run": dict(cal_eligible=False, verdict="pass")})), encoding="utf-8")
    assert inv.prereg_problems(_ns(cal=1, cal_gates=["keep"], gates=["keep"]), Gs, cal_out) == []
    assert any("보정 대상" in b for b in inv.prereg_problems(_ns(cal=1, cal_gates=["run"], gates=["run"]), Gs, gate / "cal1" / "run"))
    assert any("--out" in b for b in inv.prereg_problems(_ns(cal=1, cal_gates=["keep"], gates=["keep"]), Gs, gate / "cal1" / "x"))
    assert any("--cal" in b for b in inv.prereg_problems(_ns(cal=2, cal_gates=["keep"], gates=["keep"]), Gs, gate / "cal2" / "keep"))
    # pop: 조건부 통과를 따질 관문만, gate.json 과 같은 조건(아니면 H1 을 못 적고 pop.json 만 한 번 쓰인다), 맞는 폴더
    assert any("--x run" in b for b in inv.prereg_problems(_ns(cmd="pop", x=["run"]), Gs, gate))
    run_meta = dict(bundle="a", config=inv.CONFIG, seeds=list(Gs), steps=inv.STEPS, theta=4.0, approach=0.9,
                    cells=list(inv.CELLS), cal=[])
    gj = dict(meta=run_meta, gate={"keep": dict(complete=True, c1=True, c2=True, verdict="low_power", cal_eligible=False)})
    (gate / "gate.json").write_text(json.dumps(gj), encoding="utf-8")
    assert inv.prereg_problems(_ns(cmd="pop", x=["keep"]), Gs, gate) == []
    (gate / "gate.json").write_text(json.dumps(dict(gj, meta=dict(run_meta, steps=200))), encoding="utf-8")
    assert any("조건과 다르다" in b for b in inv.prereg_problems(_ns(cmd="pop", x=["keep"]), Gs, gate))
    (gate / "gate.json").write_text(json.dumps(gj), encoding="utf-8")
    (gate / "cal1" / "keep").mkdir(parents=True, exist_ok=True)
    (cal_out / "gate.json").write_text(json.dumps(dict(gj, meta=dict(run_meta, cal=["keep"]))), encoding="utf-8")
    assert any("--out" in b for b in inv.prereg_problems(_ns(cmd="pop", x=["keep"]), Gs, cal_out))         # 보정 회차가 아닌데 cal1/
    assert any("보정 대상" in b for b in inv.prereg_problems(_ns(cmd="pop", x=["keep"], cal=1, cal_gates=["keep"]), Gs, cal_out))
    assert any("--out" in b for b in inv.prereg_problems(_ns(cmd="pop", x=["keep"], cal=1, cal_gates=["keep"]), Gs, gate))
    # 2단계 무리 확인: gate/ 에서, 최종표(final.json)의 통과·조건부 통과 니치 그대로
    st2 = _ns(cmd="pop", stage2=True, passed=["keep"])
    assert any("final.json" in b for b in inv.prereg_problems(st2, Gs, gate))
    (gate / "final.json").write_text(json.dumps(dict(gates={"keep": dict(verdict="conditional_pass", cal=0),
                                                            "run": dict(verdict="fail", cal=0)})), encoding="utf-8")
    assert inv.prereg_problems(st2, Gs, gate) == []
    assert any("--passed" in b for b in inv.prereg_problems(_ns(cmd="pop", stage2=True, passed=["keep", "run"]), Gs, gate))
    assert any("--out" in b for b in inv.prereg_problems(st2, Gs, gate_b))
    assert any("t0" in b for b in inv.prereg_problems(_ns(cmd="t0"), Gs, gate))
    assert inv.prereg_folder(gate / "cal1" / "keep") == "a" and inv.prereg_folder(tmp_path / "x") is None


def test_main_refuses_judge_seeds_and_draft(tmp_path, capsys, monkeypatch):
    """사전 등록 폴더(기본 --out)는 사전 등록 제목이 '초안'이면 거부한다. 폴더 밖 실행은 관문·최종 판정 시드와 쓰지 않는 시드를 거부한다.
    아무것도 쓰지 않는다. 초안 거부는 임시 초안 파일과 임시 사전 등록 폴더로 본다 — 진짜 PREREG.md 에서 '초안'을 지운 뒤에도 이 시험이
    사전 등록 거주 탐색(33000~33039, 진짜 gate/)을 시작하지 않게 한다(리드 결정 10-15, PREREG 변경 기록 10-15 (5))."""
    inv = _inv()
    pr = tmp_path / "PREREG.md"
    pr.write_text("# v3 R3 관문 사전 등록 (초안)\n", encoding="utf-8")
    gate, gate_b = tmp_path / "gate", tmp_path / "gate_b"
    monkeypatch.setattr(inv, "PREREG", pr)
    monkeypatch.setattr(inv, "GATE_DIR", gate)
    monkeypatch.setattr(inv, "GATE_B_DIR", gate_b)
    monkeypatch.setattr(inv, "OUT_DIR", {"a": gate, "b": gate_b})
    with pytest.raises(SystemExit):
        inv.main(["search"])
    assert "초안" in capsys.readouterr().err
    assert not gate.exists()
    for seeds in (["15000"], ["10300"], ["10000"], ["12170"]):
        with pytest.raises(SystemExit):
            inv.main(["run", "--seeds", *seeds, "--steps", "10", "--theta", "4", "--approach", "0.9", "--out", str(tmp_path / "x")])
        assert "판정 시드" in capsys.readouterr().err
    assert not (tmp_path / "x").exists() and not (GATE_PY / "gate").exists()


def test_invasion_run_smoke(tmp_path):
    """침입 시험 smoke(도구 점검 시드): 판정표가 먼저인 보고서, 바뀐 결정 ≤ 침입 결정, 덮은 스텝 몫 ∈ [0, 1], 모두 거주 팔은 바뀐 결정 0,
    보고 지표가 침입·거주로 나뉜다. full(Spy 보고 지표)과 light 잡의 판정 값이 같다(Spy 는 궤적을 바꾸지 않는다)."""
    inv = _inv()
    res = inv.run([33087, 33088], 120, 1, tmp_path, 4.0, 0.9, cells=["ps0.7_pl_T600"], gates=["keep", "leave", "camp", "keep_hide"],
                  t0=False)
    md = (tmp_path / "invasion.md").read_text(encoding="utf-8")
    assert md.index("## 판정") < md.index("## 칸별 값") and "smoke" in md.splitlines()[0]
    assert set(res["gate"]) == {"keep", "leave", "camp", "keep_hide"}
    assert res["gate"]["camp"]["kind"] == "exploit" and res["gate"]["keep_hide"]["verdict"] == "report"
    for k, v in res["summary"].items():
        assert 0 <= v["chg_f"] <= v["dec_f"] and 0.0 <= v["cov_f"] <= 1.0, k
    assert set(res["per_seed"]["base"]) == {"rbase", "camp"}
    for r_ in ("rbase", "camp"):
        for o in res["per_seed"]["base"][r_]["ps0.7_pl_T600"].values():
            assert o["chg_f"] == 0 and o["chg_r"] == 0
    assert "g1h" in res["extra"] and set(res["report"]) >= {"keep|niche", "base_rbase", "base_camp"}
    assert set(res["report"]["keep|niche"]) >= {"f", "r", "wolf_catch_per_min"}
    assert json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))["meta"]["layout"]
    args = ("ps0.3_np_T1800", 4.0, 0.9, ("inv", "run", "niche", ()), 33089, 150, inv.CONFIG, "a")
    a, b = inv._job(args + (False,))[-1], inv._job(args + (True,))[-1]
    for k in ("rew", "pred", "starve", "rew_all", "chg_f", "dec_f", "cov_f", "ev_n_f", "use_focal", "sw_f", "fl_f"):
        assert a[k] == b[k], k
    assert "rep" in b and "rep" not in a
    dump = lambda d: json.dumps(d, sort_keys=True, default=str)                     # noqa: E731 (nan 도 같은 글자로)
    assert dump(inv._job(args + (True,))[-1]) == dump(b)                            # 같은 잡을 다시 돌리면 비트까지 같다


def test_search_cache_pop_and_report(tmp_path, monkeypatch):
    """탐색 캐시(같은 조건이면 다시 쓰고, 다르면 StaleCache), 무리 확인·역침입과 H1 기록, 최종 관문표(보정·H1 반영)."""
    inv = _inv()
    cells = ["ps0.3_np_T600"]
    r1 = inv.search([33090], 60, 1, tmp_path, cells=cells, grid_theta=(4.0,), grid_approach=(0.9, 0.75))
    assert r1["best"]["theta"] == 4.0 and set(r1["table"]) == {"4|0.9", "4|0.75"}
    assert inv.search([33090], 60, 1, tmp_path, cells=cells, grid_theta=(4.0,), grid_approach=(0.9, 0.75)) == r1
    with pytest.raises(inv.StaleCache):
        inv.search([33091], 60, 1, tmp_path, cells=cells, grid_theta=(4.0,), grid_approach=(0.9, 0.75))
    # gate.json 을 같은 조건으로 만든 뒤 pop 이 H1 을 적는다
    run_meta = dict(bundle="a", config=inv.CONFIG, seeds=[33090, 33091], steps=60, theta=4.0, approach=0.9, cells=cells, cal=[])
    gx = dict(complete=True, kind="judged", c1=True, c2=True, c3=False, verdict="low_power", cal_eligible=False)
    (tmp_path / "gate.json").write_text(json.dumps(dict(meta=run_meta, gate={"keep": gx})), encoding="utf-8")
    pres = inv.pop([33090, 33091], 60, 1, tmp_path, 4.0, 0.9, cells=cells, xs=["keep"])
    assert set(pres["summary"]) == {"pop|keep", "rev|keep"} and pres["h1"]["keep"]["complete"]
    assert json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))["h1"]["keep"]["gate_verdict"] == "low_power"
    st2 = inv.pop([33090, 33091], 60, 1, tmp_path, 4.0, 0.9, cells=cells, stage2=True, passed=["keep", "crouch", "leave"])
    assert set(st2["summary"]) == {"pop", "rev", "fsm", "graze"} and (tmp_path / "pop_stage2.md").exists()
    # 최종 관문표
    gd, gbd = tmp_path / "g", tmp_path / "gb"
    (gd / "cal1" / "run").mkdir(parents=True)
    (gd / "search.json").write_text(json.dumps(dict(best=dict(theta=4.0, approach=0.9))), encoding="utf-8")
    gate = {"keep": dict(gx), "run": dict(complete=True, verdict="fail", cal_eligible=True, c1=False),
            "crouch": dict(verdict="pass"), "camp": dict(kind="exploit", verdict="exploit_loss"), "keep_hide": dict(verdict="report"),
            "early": dict(complete=True, verdict="fail", c1=True, c2=False, cal_eligible=False, human=True)}
    (gd / "gate.json").write_text(json.dumps(dict(gate=gate, h1={"keep": dict(complete=True, verdict="conditional_pass")})),
                                  encoding="utf-8")
    (gd / "cal1" / "run" / "gate.json").write_text(json.dumps(dict(gate={"run": dict(verdict="pass")})), encoding="utf-8")
    out_md = tmp_path / "report_gate.md"
    r = inv.report(gd, gbd, out_md)
    fv = {x: v["verdict"] for x, v in r["final"]["gates"].items()}
    assert fv == {"keep": "conditional_pass", "run": "pass", "crouch": "pass", "camp": "exploit_loss", "keep_hide": "report",
                  "early": "fail"}
    assert r["final"]["gates"]["run"]["cal"] == 1
    assert r["final"]["gates"]["early"]["human"] and not r["final"]["gates"]["run"]["human"]
    stop = [ln for ln in r["md"].splitlines() if ln.startswith("- **멈춤**")]
    assert len(stop) == 1 and "early" in stop[0] and "run" not in stop[0]             # (2) 실패도 멈추고 사람이 본다
    s = rt.gate_setup(gd)
    assert s["complete"] and s["lines"] == ("crouch", "run", "keep") and s["cal"] == ("run",) and s["p3"]
    assert s["u_judged"] == ("esc", "run", "hide")
    md = out_md.read_text(encoding="utf-8")
    assert md.index("## 관문표") < md.index("## 학습과 판정에 쓰이는 방식")


def test_t0_chase_smoke():
    inv = _inv()
    t = inv.t0_chase([33092], 120, 1, 4.0, 0.9, cells=["ps0.7_np_T600"])
    assert set(t) >= {"t0", "pounce", "charge", "chase", "a_out"}
    assert set(t["t0"]) >= {"per_seed", "snow_minus_normal", "rough_minus_normal", "deer_share"}
    md = inv.t0_md(t, {})
    assert "T0" in md and "확인표" in md


# --------------------------------------------------------------------- #
# 결정적 확인표 chase_r3
# --------------------------------------------------------------------- #


def test_chase_r3_deterministic_and_saved_table():
    """16-3 확인표: 같은 시행은 결정적이다. 저장한 chase_r3.json 은 지금 코드로 다시 잰 값과 같다(몇 칸). 멈추면 추격형에게 잡히고, 덤불에 닿으면
    산다(보통 땅), 늑대는 원 안에 들어가지 않는다."""
    if str(GATE_PY) not in sys.path:
        sys.path.insert(0, str(GATE_PY))
    import chase_r3 as cr

    saved = json.loads((GATE_PY / "chase_r3.json").read_text(encoding="utf-8"))
    assert saved["meta"]["repeat_identical"] and saved["meta"]["seeds"] == list(cr.SEEDS)
    assert all(33080 <= s <= 33099 for s in cr.SEEDS)
    for key in ("chaser|normal|flee|5", "chaser|normal|stop8|5", "chaser|normal|hide3|5", "stalker|snow|hide6|5"):
        wolf, terr, dk, d0 = key.split("|")
        deer = next(d for d in cr.DEER if cr.deer_key(d) == dk)
        runs = [cr.chase(wolf, terr, float(d0), deer, s) for s in cr.SEEDS]
        assert runs == saved["table"][key]["runs"], key
        assert runs == [cr.chase(wolf, terr, float(d0), deer, s) for s in cr.SEEDS]
    T = saved["table"]
    assert all(T[f"chaser|normal|stop{k}|{d:g}"]["caught"] == 4 for k in (4, 8, 16) for d in cr.D0S)
    assert all(T[f"chaser|normal|flee|{d:g}"]["caught"] == 0 for d in cr.D0S)
    assert all(T[f"chaser|normal|hide{c:g}|{d:g}"]["caught"] == 0 for c in (3.0, 6.0, 10.0) for d in cr.D0S)
    assert sum(r["inside_steps"] for v in T.values() for r in v["runs"]) == 0
    assert all(not (r["caught"] and r["reach_t"] is not None and r["caught_t"] > r["reach_t"]) for v in T.values() for r in v["runs"])
    assert saved["meta"]["digests"]["configs/v3_r3_on.yaml"] == _inv().PREREG_DIGEST


# --------------------------------------------------------------------- #
# eval_v3 --u-def r3
# --------------------------------------------------------------------- #


def _res_for_gate(a_rl, a_lf, opp=400, flee=0.02, hide=0.02, freeze=0.0, u=0.5, n=500):
    import eval_v3 as ev
    import repertoire_rules as rr_

    seeds = list(range(20))
    pol = dict(u={k: u for k in rr_.R3_U}, u_cnt={k: [n, n // 2, n, 0] for k in rr_.R3_U}, starve_rate=0.001, flicker=0.3,
               use=dict(graze=0.9, flee=flee, hide=hide, freeze=freeze, sleep=0.0))
    res = dict(perf=dict(t=1.0, crit=2.093, mean=0.1), pooled={"rl": pol, "fsm_r3": dict(pol, starve_rate=0.001)},
               a3={"rl": dict(seeds=seeds, A=list(a_rl), opp=[opp] * 20), "rlf": dict(seeds=seeds, A=list(a_lf), opp=[opp] * 20)})
    return ev, res


def test_gate_r3_logic(monkeypatch):
    """P3·P4·P5 의 상태(판정·보고만·판정 불가·미정)와 멈춤(FREEZE 사용)."""
    rng = np.random.default_rng(33093)
    a_lf = list(0.08 + 0.01 * rng.standard_normal(20))
    a_good = [x - 0.04 + 0.005 * rng.standard_normal() for x in a_lf]
    full = dict(theta=4.0, approach=0.9, lines=["keep", "run"], cal=[], sleep=False, u_judged=["esc", "keep"], u_report=[],
                p3=True, hide_floor=True, gate_complete=True, explicit=False)
    ev, res = _res_for_gate(a_good, a_lf)
    res["r3_setup"] = full
    monkeypatch.setitem(ev.R3_JUDGE, "u_min_esc", 0.23)
    monkeypatch.setitem(ev.R3_JUDGE, "a_ref", dict(rlf=0.08, fsm_r3=0.04))
    g = ev._gate_r3(res, ("graze", "flee", "hide"), res["pooled"]["rl"], res["pooled"]["fsm_r3"])
    assert g["p3"]["status"] == "judged" and g["p3"]["pass_"] and g["pass_"] and not g["pending"]
    assert g["u"]["items"]["keep"]["status"] == "judged" and g["u"]["items"]["run"]["status"] == "report"
    ev, res = _res_for_gate(a_lf, a_lf)
    res["r3_setup"] = full
    g = ev._gate_r3(res, ("graze", "flee", "hide"), res["pooled"]["rl"], res["pooled"]["fsm_r3"])
    assert g["p3"]["status"] == "judged" and not g["p3"]["pass_"] and not g["pass_"]
    ev, res = _res_for_gate(a_good, a_lf, opp=200)
    res["r3_setup"] = full
    assert ev._gate_r3(res, (), res["pooled"]["rl"], res["pooled"]["fsm_r3"])["p3"]["status"] == "insufficient"
    monkeypatch.setitem(ev.R3_JUDGE, "a_ref", dict(rlf=0.08, fsm_r3=0.07))
    ev, res = _res_for_gate(a_good, a_lf)
    res["r3_setup"] = full
    assert ev._gate_r3(res, (), res["pooled"]["rl"], res["pooled"]["fsm_r3"])["p3"]["status"] == "report"
    ev, res = _res_for_gate(a_good, a_lf, freeze=0.001, n=100)
    res["r3_setup"] = full
    g = ev._gate_r3(res, (), res["pooled"]["rl"], res["pooled"]["fsm_r3"])
    assert g["halt"] and not g["pass_"] and g["u"]["items"]["esc"]["status"] == "insufficient"
    monkeypatch.setitem(ev.R3_JUDGE, "u_min_esc", None)
    ev, res = _res_for_gate(a_good, a_lf)
    res["r3_setup"] = dict(full, gate_complete=False, u_judged=None, p3=None, hide_floor=None)
    g = ev._gate_r3(res, (), res["pooled"]["rl"], res["pooled"]["fsm_r3"])
    assert g["pending"] and not g["pass_"] and g["p3"]["status"] == "pending"


@pytest.fixture(scope="module")
def judged_r3(tmp_path_factory):
    if not R1B.exists():
        pytest.skip("R1b 모델 없음")
    import eval_v3 as ev

    out = tmp_path_factory.mktemp("judge_r3")
    r3s = ev.r3_setup(4.0, 0.9)
    res = ev.judge(str(R1B), "smoke", [33094], 150, out, config=ev.CONFIG_R3, tail=50, workers=1, udef="r3", r3=r3s)
    return ev, res, out


def test_eval_r3_smoke(judged_r3):
    """r3 판정 smoke(R1b 를 'RL' 자리에 얹어): 정책 모두, U 여섯, 포기율 A 와 반사실, 판정은 미정(관문 결과·문턱 없음), 얼기 없음."""
    ev, res, out = judged_r3
    P = res["pooled"]
    assert set(P) == set(ev.R3_POLICIES)
    for name, v in P.items():
        assert set(v["u"]) == set(rr.R3_U), name
        assert "a3" in v and set(v["visible"]) >= {"threats", "r3", "realism"}, name
    assert P["rl"]["g_gamma"] == P["rlf"]["g_gamma"] and P["rl"]["a3"] == P["rlf"]["a3"]      # 같은 모델·같은 세계
    assert P["rl"]["use"]["freeze"] == 0.0 and P["fsm_r3"]["use"]["freeze"] == 0.0
    assert P["r1b"]["a3"]["freeze_abandon"] and not P["rl"]["a3"]["freeze_abandon"]
    if P["rl"]["a3"]["n_opp"]:
        assert P["rl"]["a3"]["cf"]["rlf"]["same"] == 1.0                                     # R1b−F 반사실 = RL 자신
    G_ = res["gate"]
    assert G_["pending"] and not G_["pass_"] and not G_["halt"]
    assert G_["perf"]["ref"] == "fsm_r3" and G_["starve"]["fsm"] == P["fsm_r3"]["starve_rate"]
    assert res["meta"]["u_def"] == "r3" and not res["meta"]["prereg"] and res["meta"]["r3"]["explicit"]
    md = (out / "smoke.md").read_text(encoding="utf-8")
    assert "v3 R3 판정" in md and "포기율 A" in md and md.index("## 판정") < md.index("## 정책별 지표")
    assert "v3 R3 판정 모음" in ev.summarize(["smoke"], out, "r3")
    # 니치 π 측정: 판정 롤아웃과 같은 궤적(argmax) — 결정 표본 수가 eval 의 rl 과 같다. 난수 없음
    import train_v3

    cfg = load_v2_config(R3_ON)
    mp = train_v3.measure_pi(cfg, str(R1B), seeds=[33094], steps=150, r3=res["meta"]["r3"])
    assert mp["u_def"] == "r3" and mp["n_dec"] == res["per_seed"]["rl"][0]["n_dec"]
    assert set(mp["early_stop_pi"]) == set(train_v3.R3_EARLY_PI) and mp["early_stop_pending"]
    assert not mp["freeze_or_sleep_open"] and mp["pooled"]["pi_freeze_max"] == 0.0
    assert mp == train_v3.measure_pi(cfg, str(R1B), seeds=[33094], steps=150, r3=res["meta"]["r3"])


def test_eval_r3_guards(judged_r3, tmp_path, capsys):
    """판정 폴더 보호와 시드: 기본 --out(판정 폴더)은 거부, 폴더 밖은 관문·최종 판정 시드를 거부, r3 는 R3 세계에서만."""
    ev, res, out = judged_r3
    model = str(R1B)
    with pytest.raises(SystemExit):
        ev.main(["run", "--u-def", "r3", "--model", model, "--name", "x"])
    for seeds in ("10300", "15000", "10000"):
        with pytest.raises(SystemExit):
            ev.main(["run", "--u-def", "r3", "--model", model, "--name", "x", "--seeds", seeds, "--steps", "10", "--out", str(tmp_path)])
    with pytest.raises(SystemExit):
        ev.main(["run", "--model", model, "--name", "x", "--theta", "4", "--seeds", "20000", "--out", str(tmp_path)])
    capsys.readouterr()
    assert not (ev.PREREG_OUT_R3 / "x.json").exists() and not (tmp_path / "x.json").exists()
    with pytest.raises(ValueError, match="R3 세계"):
        ev.judge(model, "x", [33095], 10, tmp_path, config=ev.CONFIG, udef="r3", workers=1)
    a = argparse.Namespace(steps=ev.STEPS, config=ev.CONFIG_R3, tail=ev.TAIL, policies=None, u_def="r3", theta=None, approach=None,
                           fsm_r3_lines=None, r3_cal=None)
    bad = ev.prereg_problems_r3(a, ev.EVAL_SEEDS_R3)
    assert any("관문 결과" in b for b in bad) and any("U_ESC 문턱 미정" in b for b in bad)
    assert any("판정 사전 등록" in b for b in bad)
    a2 = argparse.Namespace(steps=3000, config=ev.CONFIG, tail=100, policies=["rl"], u_def="r2", theta=4.0, approach=None,
                            fsm_r3_lines=None, r3_cal=None)
    assert len(ev.prereg_problems_r3(a2, [20000])) >= 9
    assert ev.EVAL_SEEDS_R3 == list(range(10300, 10320)) and ev.R3_JUDGE["u_min_esc"] is None and ev.R3_JUDGE["a_ref"] is None


def test_reserved_r3_seeds_refused_by_other_paths(tmp_path, capsys):
    """R3 관문·최종 판정 시드는 다른 지표 정의(r1·r2)의 eval_v3 실행과 train_v3 measure-fdec 도 받지 않는다(2절). 아무것도 돌리지 않는다."""
    import eval_v3 as ev
    import train_v3

    for udef, seed in (("r1", "10300"), ("r2", "15000"), ("r1b", "10319"), ("r1", "15039")):
        with pytest.raises(SystemExit):
            ev.main(["run", "--u-def", udef, "--model", str(tmp_path / "없음.zip"), "--name", "x", "--seeds", seed, "--steps", "10",
                     "--out", str(tmp_path)])
        assert "R3 관문·최종 판정 시드" in capsys.readouterr().err
    for seed in ("15000", "10300"):
        with pytest.raises(SystemExit, match="판정 시드"):
            train_v3.main(["measure-fdec", "--config", str(R3), "--seeds", seed, "--steps", "10"])
    assert not (tmp_path / "x.json").exists()


def test_policy_specs_r3(c3):
    import eval_v3 as ev

    r3s = ev.r3_setup(6.0, 0.75, ["run", "keep"], ["run"])
    assert r3s["explicit"] and r3s["lines"] == ["run", "keep"] and r3s["cal"] == ["run"]
    allowed = ("graze", "flee", "hide")
    assert ev.policy_spec("fsm_r3", "x.zip", c3, allowed, "near", r3=r3s)["build"] == rr.fsm_r3_spec(
        c3, 6.0, 0.75, lines=["run", "keep"], cal=["run"])
    assert ev.policy_spec("rbase", "x.zip", c3, allowed, "near", r3=r3s)["build"] == rr.rule_spec(c3, 6.0, 0.75)
    assert ev.policy_spec("rbase", "x.zip", c3, allowed, "near")["build"] == ev.fsm_spec(c3, ("graze", "flee"), "near")
    assert ev.policy_spec("r1b", "x.zip", c3, allowed, "near")["world"] == "freeze"
    assert ev.r3_freeze_world(c3).v2["train"]["repertoire"]["allowed"] == ["graze", "flee", "hide", "freeze"]
    with pytest.raises(ValueError, match="r3_setup"):
        ev.policy_spec("fsm_r3", "x.zip", c3, allowed, "near")
    d = ev.r3_setup()
    assert not d["gate_complete"] and (d["theta"], d["approach"]) == (4.0, 0.9) and tuple(d["lines"]) == rr.FSM_R3_LINES
    assert ev.ref_fsm("r3") == "fsm_r3" and ev.ref_fsm("r2") == "fsm_r2"


# --------------------------------------------------------------------- #
# train_v3 (R3_EARLY_PI, r3 니치 π, H13 출처 표시) · warmstart_v3 R3 기본값
# --------------------------------------------------------------------- #


def test_niche_probs_r3_and_early_split(c3):
    import train_v3

    o = _obs(c3, [dict(F=1, s=1, a=0.7, d=8.0, c=9.0), dict(c=0, s=1, d=3.0), dict(s=1, d=6.0, a=0.65, c=9.0)])
    pi = np.tile([0.4, 0.3, 0.3, 0.0, 0.0], (3, 1))
    r3s = dict(theta=4.0, approach=0.9, cal=())
    out = train_v3.niche_probs(pi, o, rr.r3_geo(c3), ("graze", "flee", "hide"), "near", "r3", r3=r3s)
    assert set(out) == {f"{p}_{u}_{k}" for p in ("pi", "n") for u in rr.R3_U for k in ("niche", "base")} | {"pi_freeze_max",
                                                                                                         "pi_sleep_max"}
    assert out["pi_keep_niche"] == pytest.approx(0.6) and out["pi_hide_niche"] == pytest.approx(0.3)
    assert out["pi_early_niche"] == pytest.approx(0.6) and out["pi_freeze_max"] == 0.0
    with pytest.raises(ValueError, match="r3_geo"):
        train_v3.niche_probs(pi, o, rr._geom(c3), (), "near", "r3", r3=r3s)
    assert train_v3.R3_EARLY_PI == {"keep": "pi_keep_niche", "run": "pi_run_niche", "crouch": "pi_hide_niche",
                                    "early": "pi_early_niche"}
    use, rep_ = train_v3.r3_early_split(dict(gate_complete=True, p3=False, lines=["run", "crouch", "keep"]))
    assert use == ("run", "crouch") and rep_ == ("keep", "early")
    assert train_v3.r3_early_split(dict(gate_complete=False)) == (tuple(train_v3.R3_EARLY_PI), ())
    assert train_v3.auto_udef(obs_names(c3), c3) == "r3" and train_v3.auto_udef(obs_names(c3)) == "r1"
    assert train_v3.default_run_name(load_v2_config(R3), 0, 20_000_000, 0.995, "r1b") == "v3_r3r1b_g995_s0_20m"


def test_init_from_model(tmp_path):
    """H13 대응 1회(13-5): R1b 가중치를 R3 설정 모델에 strict 로 싣고 출처를 남긴다. 출처 글·파일·관측이 맞지 않으면 멈춘다."""
    if not R1B.exists():
        pytest.skip("R1b 모델 없음")
    import torch
    from stable_baselines3 import PPO

    import train_v3
    from env_v2.vec_env import MultiWorldVecEnv

    cfg = load_v2_config(R3)
    venv = MultiWorldVecEnv(cfg, num_worlds=1, meta_seed=0)
    model = train_v3.make_model_rep(venv, rp.rep_params(cfg), None, seed=0)
    rec = train_v3.init_from_model(model, R1B, "R1b s3, R1 세계, 목록 graze·flee·hide·freeze")
    assert rec["model_allowed"] == ["graze", "flee", "hide", "freeze"] and rec["allowed"] == ["graze", "flee", "hide"]
    assert len(rec["sha1"]) == 12 and rec["mask_version"] == 2
    src = PPO.load(str(R1B), device="cpu").policy.state_dict()
    for k, v in model.policy.state_dict().items():
        assert torch.equal(v, src[k]), k
    with pytest.raises(SystemExit, match="init-source"):
        train_v3.init_from_model(model, R1B, "  ")
    with pytest.raises(SystemExit, match="없다"):
        train_v3.init_from_model(model, tmp_path / "x.zip", "출처")
    (tmp_path / "bad.zip").write_bytes(b"not a zip")
    with pytest.raises(SystemExit, match="RepertoirePolicy"):
        train_v3.init_from_model(model, tmp_path / "bad.zip", "출처")
    with pytest.raises(SystemExit, match="함께"):
        train_v3.main(["--config", str(R3), "--init-from-model", str(R1B), "--init-source", "x", "--warmstart", "w.pt",
                       "--out", str(tmp_path / "m.zip")])
    with pytest.raises(SystemExit, match="init-from-model"):
        train_v3.main(["--config", str(R3), "--init-source", "x", "--out", str(tmp_path / "m.zip")])
    assert not (tmp_path / "m.zip").exists()


def test_warmstart_r3_defaults_and_collect(tmp_path, monkeypatch):
    """R3 세계의 모방 초기화 기본값(교사 fsm_r3, ckpt/v3/ws_r3, v3_r3_ws)과 교사 자료: 두 교사 요청은 늘 마스크 안이고 FREEZE 가 없다.
    관문 결과 없이 문턱을 주지 않으면 collect 가 멈춘다."""
    import eval_v3 as ev
    import warmstart_v3 as ws

    cfg = load_v2_config(R3)
    assert ws.default_teacher2(cfg) == "fsm_r3" and ws.default_out_dir(cfg) == ws.OUT_R3 and ws.default_name(cfg) == "v3_r3_ws"
    assert ws.default_teacher2(load_v2_config(ROOT / "configs" / "v3_r2.yaml")) == "fsm_r2"
    assert ws.default_teacher2(load_v2_config(ROOT / "configs" / "v3_r1.yaml")) == "fsm"
    r3s = ev.r3_setup(4.0, 0.9)
    assert ws.teacher2_spec(cfg, ("graze", "flee", "hide"), "fsm_r3", r3s) == rr.fsm_r3_spec(cfg, 4.0, 0.9)
    monkeypatch.setattr(ws, "VALUE_DROP", 50)
    res = ws.collect(cfg, n_worlds=2, steps=150, r3=r3s)
    st = res["stats"]
    assert st["teacher2"] == "fsm_r3" and st["teacher_invalid"] == 0 and st["freeze_teacher"] == 0 and st["freeze_mask"] == 0
    assert st["r3"]["theta"] == 4.0 and st["counts_fsm"][rep.HIDE] >= 0 and st["obs_dim"] == 18
    assert not np.isin(res["data"]["p_act2"], (Z, S)).any() and not np.isin(res["data"]["p_act"], (Z, S)).any()
    data = tmp_path / "tm.npz"
    with pytest.raises(SystemExit, match="관문 결과"):
        ws.main(["collect", "--config", str(R3), "--data", str(data), "--worlds", "1", "--steps", "10"])
    assert not data.exists()


@pytest.mark.parametrize("cfg_name", ["v3_r1_on", "v3_r2_on", "v3_real1_on", "v3_real1_night_on", "v3_r3_on", "v3_r3"])
def test_tool_worlds_keep_dynamics(cfg_name):
    """도구의 World 하위 클래스(포기율 A 의 쫓는 위협 추적 r3_tools.pursuit_world_class, 관문 잡의 기록 훅·eval_pre Spy)는 기록만 한다 —
    지금 설정들의 궤적(관측·보상·사망·위치)이 보통 World 와 비트까지 같다."""
    cfg = rr.with_obs_extra(load_v2_config(ROOT / "configs" / f"{cfg_name}.yaml"))
    worlds = [World(cfg, seeds=[33097])]
    if rt.is_r3_world(cfg) or World(cfg, seeds=[33097])._rz:
        worlds.append(rt.pursuit_world_class()(cfg, seeds=[33097]))
        Spy = _inv().eval_pre()._spy_class()
        ws = Spy(cfg, seeds=[33097])
        ws._spy_init()
        worlds.append(ws)
    spec = rr.rule_spec(cfg, 4.0, 0.9)
    pols = [ro.build_policy(spec, 0) for _ in worlds]
    for _ in range(200):
        outs = []
        for w, p in zip(worlds, pols):
            o = w.observe()
            outs.append((o, w.step(np.asarray(p(o), dtype=np.float64))))
        for o, (o2, r, d, _) in outs[1:]:
            np.testing.assert_array_equal(o, outs[0][0])
            np.testing.assert_array_equal(r, outs[0][1][1])
            np.testing.assert_array_equal(d, outs[0][1][2])
        for w in worlds[1:]:
            np.testing.assert_array_equal(w.pos, worlds[0].pos)
            np.testing.assert_array_equal(w.pred_pos, worlds[0].pred_pos)
