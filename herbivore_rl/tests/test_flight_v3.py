"""야생 (w3) 도망 기록과 학습 전용 도주 비용 (10-21 사용자 '도망 시간이 더 짧은 사슴이 똑똑한 걸로 기준을 잡아봐' — results/v3/live/LIVE_GATE.md 변경 기록 (3)).

- 정의(env_v2/world.py 모듈 docstring '야생 1단계' (w3) 도망 기록): 도망 = FLEE 를 실행한 스텝(도주 반사·두뇌 FLEE 모두)이 이어진 묶음. 쫓긴 시간 =
  표적이던 마지막 FLEE 스텝까지. 끝 까닭 cover·obstacle·fov·range(스스로 벗어남)·switch·stop·held·unchased·caught·starved·truncated.
  `_fl_update` 를 짜 맞춘 FLEE·표적으로 불러 하나씩 본다(시작·쫓긴 시간·끝·다음 스텝에 닫기·잘림·다시 남·잡아 먹기 시작한 늑대).
- 동역학과 무관: 같은 세계를 기록 켬·끔으로 돌리면 관측·보상·위치·난수가 비트 단위로 같다(거울 세계 = 부활 없음, 학습 세계 = 부활 있음).
  실행한 FLEE 사슴-스텝 = 끝 까닭별 스텝 합(잘림 포함) = 진단 행동 칸, 반사 스텝 = 실행한 도주 덮기, 시작 = 까닭별 수 합.
- flight_cost: 끔 값 0 은 키가 없는 세계와 비트 동일, 켜면 보상만 −flight_cost × [그 스텝 FLEE 실행] 으로 바뀐다(궤적 그대로).
- 판정 실행기(run_mirror.run_world)는 wild_flight 세계에서 기록을 켜고 메타 flight·flight_at 을 적는다.
시드는 탐색 32084~32099·학습 32000~32049 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import importlib.util

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import (FL_DROP_CAUSE, FL_DROP_COVER, FL_DROP_FOV, FL_DROP_OBSTACLE, FL_DROP_RANGE, FL_DROP_STOP, FL_DROP_SWITCH, FLIGHT_CAUSES,
                          FLIGHT_HIST_STEPS, FLIGHT_OWN, FLIGHT_UNSAFE, WF_PANIC, World)

CFG = ROOT / "configs"
OBS = CFG / "v3_wild3_obs_mirror.yaml"          # 거울 (부활 없음, 장애물·늑대 4)
TRAIN = CFG / "v3_r5_train.yaml"                # 학습 세계 (부활 있음)
R1Z = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _forest(cfg):
    """거울 세계에 숲 지역 나무 원판(results/v3/wild2/trees/tree_layout.json)을 덮는다 — 원판이 늑대 눈길을 가리는 길을 탄다."""
    r4 = _module("_r4_for_flight", ROOT / "results" / "v3" / "r4" / "r4_eval.py")
    return _with(cfg, wild_weather=dict(region="Forest"), obstacles=dict(fixed=r4.region_discs()["Forest"]))


def _run(cfg, seed, steps, track, acts_seed=7):
    """무작위 행동(먹기·도망·숨기 — 두뇌가 고른 FLEE 도 나온다)으로 돌린 궤적과 세계, 실행한 도주 덮기 사슴-스텝 수, 스텝 뒤 FLEE 인 산 사슴-스텝 수
    (부활 없는 세계는 실행한 FLEE 와 같다 — 진단 행동 칸과 같은 셈. 부활 있는 세계는 죽은 칸이 빠진다)."""
    w = World(cfg, seeds=[seed])
    w.track_flight = track
    rng = np.random.default_rng(acts_seed)
    out, pan, flee = [], 0, 0
    for _ in range(steps):
        alive0 = np.ones(w.N, dtype=bool) if w.alive is None else w.alive.copy()
        pan += int(np.count_nonzero((w.wf_mode == WF_PANIC) & alive0))
        o, r, d, _ = w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        flee += int(np.count_nonzero((w._rs.behavior == rep.FLEE) & alive0 & ~(d if w.alive is None else np.zeros(w.N, dtype=bool))))
        out.append((o.copy(), r.copy(), d.copy(), w.pos.copy(), w.pred_pos.copy(), w.energy.copy()))
        if track:
            assert not (w._fl_len[d] > 0).any()                 # FLEE 중 죽은(다시 난) 칸은 그 스텝에 닫는다
    return out, w, pan, flee


def _same(a, b):
    assert len(a) == len(b)
    for t, (x, y) in enumerate(zip(a, b)):
        for k, (u, v) in enumerate(zip(x, y)):
            assert np.array_equal(u, v), (t, k)


def _invariants(f):
    assert set(f["n"]) == set(FLIGHT_CAUSES) and f["started"] == sum(f["n"].values())
    assert f["flee_steps"] == sum(f["steps"].values()) and f["reflex_steps"] <= f["flee_steps"] <= f["live_steps"]
    assert f["own_n"] == sum(f["n"][c] for c in FLIGHT_OWN) and f["own_contact"] == sum(f["contact"][c] for c in FLIGHT_OWN)
    assert sum(f["hist"]) == f["own_n"] and f["hist_edges"] == list(FLIGHT_HIST_STEPS)
    assert all(f["steps"][c] >= f["n"][c] for c in FLIGHT_CAUSES)   # 도망 하나는 1 스텝 이상
    assert all(0 <= f["contact"][c] <= f["steps"][c] for c in FLIGHT_CAUSES)
    assert f["contact"]["unchased"] == 0 and f["shelter_end"] <= f["started"] - sum(f["n"][c] for c in FLIGHT_UNSAFE)


# --------------------------------------------------------------------- #
# 동역학과 무관 (기록 켬 = 끔, 비트 동일)
# --------------------------------------------------------------------- #


def test_tracking_is_bit_identical_mirror():
    """거울(부활 없음, 숲 원판·늑대 4): 기록 켬·끔 궤적·난수가 같고, 실행한 FLEE 사슴-스텝 = 기록 스텝 합, 반사 = 실행한 덮기 통계(_wf_mode_n)."""
    cfg = _forest(load_v2_config(OBS).replace(N=32))
    a, wa, _, _ = _run(cfg, 32084, 900, False)
    b, wb, pan, flee = _run(cfg, 32084, 900, True)
    _same(a, b)
    assert wa.rng.bit_generator.state == wb.rng.bit_generator.state
    assert {k: g.bit_generator.state for k, g in wa._feature_rngs.items()} == {k: g.bit_generator.state for k, g in wb._feature_rngs.items()}
    assert repr(wa.wild_stats()) == repr(wb.wild_stats()) and repr(wa.hunt_stats()) == repr(wb.hunt_stats())
    f = wb.flight_stats()
    _invariants(f)
    assert f["flee_steps"] == flee and f["reflex_steps"] == pan == int(wb._wf_mode_n[WF_PANIC])
    assert f["flee_steps"] > f["reflex_steps"] > 0 and f["started"] > 0 and f["own_n"] > 0     # 무작위 행동이라 두뇌가 고른 FLEE 도 센다
    with pytest.raises(ValueError, match="track_flight"):
        wa.flight_stats()


def test_tracking_is_bit_identical_respawn():
    """학습 세계(부활 있음): 기록 켬·끔 궤적이 같고, 죽음 스텝의 FLEE(리스폰이 지우기 전 사본)까지 센다."""
    cfg = load_v2_config(TRAIN).replace(N=24)
    a, _, _, _ = _run(cfg, 32001, 1500, False, acts_seed=5)
    b, w, pan, flee = _run(cfg, 32001, 1500, True, acts_seed=5)
    _same(a, b)
    f = w.flight_stats()
    _invariants(f)
    assert f["n"]["caught"] > 0                                     # FLEE 중 잡힌 사슴이 있고, 그 칸의 새 개체는 새 도망이다
    assert f["reflex_steps"] >= pan and f["flee_steps"] >= flee      # 죽음 스텝(리스폰이 지운 칸)도 센다
    assert f["live_steps"] == 24 * 1500


@pytest.mark.skipif(not R1Z.exists(), reason="관측 21 두뇌 zip 이 없다 (저장소 밖 ckpt)")
def test_runner_writes_flight_and_matches_untracked(monkeypatch):
    """판정 실행기: 메타 flight·flight_at(길이마다 끊은 기록 — 끝 길이 = flight), 실행한 FLEE = 진단 행동 칸, 같은 job 을 기록 없이 돌린 궤적과 같다."""
    rm = _module("_rm_for_flight", ROOT / "results" / "v3" / "mirror" / "run_mirror.py")
    cfg = _forest(rm.mirror_cfg(32, 38, OBS)).to_dict()
    job = dict(cfg=cfg, seed=32085, steps=300, model=str(R1Z), log_every=100, diag=True, region="Forest", flight_at=[150, 300])
    m = rm.run_world(copy.deepcopy(job))["meta"]
    assert set(m["flight_at"]) == {"150", "300"} and m["flight_at"]["300"] == m["flight"]
    assert m["flight_at"]["150"]["started"] <= m["flight"]["started"] and m["flight_at"]["150"]["live_steps"] < m["flight"]["live_steps"]
    assert m["flight"]["flee_steps"] == m["diag"]["beh_steps"][rep.FLEE] and m["flight"]["live_steps"] == m["live_steps"]
    _invariants(m["flight"])
    # 기록 끔: 실행기가 켜도 꺼진 채 (이 시험 안에서만 — monkeypatch 가 되돌린다)
    monkeypatch.setattr(World, "track_flight", property(lambda self: False, lambda self, v: None), raising=False)
    monkeypatch.setattr(World, "flight_stats", lambda self: {})
    off = rm.run_world(copy.deepcopy(job))["meta"]
    assert off["flight"] == {}
    for k in ("death_t", "death_cause", "hunt", "shelter_steps", "live_steps", "diag"):
        assert repr(m[k]) == repr(off[k]), k


# --------------------------------------------------------------------- #
# 끝 까닭 (짜 맞춘 FLEE·표적으로 _fl_update 를 직접 부른다)
# --------------------------------------------------------------------- #


def _scene(n=6):
    w = World(load_v2_config(OBS).replace(N=n), seeds=[32086])
    w.track_flight = True
    w._fl_reset()
    return w


def _tick(w, flee, tgt=None, done=(), caught=(), in_cov=(), pred=None, reflex=None, idle=()):
    """한 스텝: flee = 이번 스텝에 FLEE 를 실행한 사슴(reflex = 그 가운데 도주 반사, 없으면 모두), tgt = 이번 스텝 늑대 표적(없으면 −1), idle = 스텝 끝에
    사냥하지 않는 늑대(먹기 — 쿨다운), pred = 놓침 까닭 재료(사냥 가능 (M,), 시야 반경 안·반경과 시야각 안·원판이 가림·은신처 표적 제외 (M,N) — 없으면
    모두 사냥 가능·보임·안 가림·은신처 아님)."""
    N, M = w.N, w.M

    def mask(ix):
        m = np.zeros(N, dtype=bool)
        m[list(ix)] = True
        return m

    d = mask(done)
    w.pred_target = np.full(M, -1, dtype=np.int64) if tgt is None else np.asarray(tgt, dtype=np.int64)
    w.pred_cd = np.zeros(M, dtype=np.int64)
    w.pred_cd[list(idle)] = 30
    if getattr(w, "pred_asleep", None) is not None:
        w.pred_asleep = np.zeros(M, dtype=bool)
    if getattr(w, "pred_sat", None) is not None:
        w.pred_sat = np.zeros(M, dtype=np.int64)
    no = np.zeros((M, N), dtype=bool)
    w._fl_pred = pred if pred is not None else (np.ones(M, dtype=bool), np.ones((M, N), dtype=bool), np.ones((M, N), dtype=bool), no, no.copy())
    w._fl_update(mask(flee), mask(flee if reflex is None else reflex), d, mask(caught), np.ones(N, dtype=bool) & ~d, mask(in_cov))


def _t(M, **pairs):
    """늑대 m → 표적 (w0=사슴 0 꼴)."""
    return [pairs.get(f"w{m}", -1) for m in range(M)]


def test_end_causes_scripted():
    w = _scene()
    M, N = w.M, w.N
    no = np.zeros((M, N), dtype=bool)
    yes = np.ones((M, N), dtype=bool)
    # 0: 늑대 0 이 2 스텝 쫓다가 원판 뒤에서 놓침, 1 스텝 더 달리고 끝 → obstacle, 도망 3·쫓긴 2
    # 1: 쫓기지 않고 은신처 안에서 끝 → unchased (은신처에서 끝 1), 2 스텝
    # 2: 늑대 1 이 쫓다가 시야 반경 밖에서 놓침 → range, 도망 2·쫓긴 1
    # 4: FLEE 중 잡힘 → caught (그 스텝에 닫음), 2 스텝 / 5: 판이 끝날 때 열린 도망 → truncated
    _tick(w, [0, 1, 2, 4], tgt=_t(M, w0=0, w1=2))
    assert w.flight_stats()["started"] == 4 and w._fl_contact[0] == 1 and w._fl_contact[1] == 0
    blk = no.copy()
    blk[0, 0] = True
    rng_ = yes.copy()
    rng_[1, 2] = False
    _tick(w, [0, 1, 2, 4], tgt=_t(M, w0=0), pred=(np.ones(M, dtype=bool), rng_, rng_.copy(), no.copy(), no.copy()), in_cov=[1])   # 늑대 1 이 반경 밖으로 놓침
    assert w._fl_why[2] == FL_DROP_RANGE and w._fl_contact[0] == 2 and w._fl_contact[2] == 1
    _tick(w, [0, 4, 5], pred=(np.ones(M, dtype=bool), yes, yes, blk, no.copy()), done=[4], caught=[4])   # 0 원판에 놓침, 1·2 지난 스텝에 끝, 4 잡힘
    assert w._fl_why[0] == FL_DROP_OBSTACLE and w._fl_len[0] == 3 and w._fl_len[4] == 0
    f = w.flight_stats()
    assert f["n"]["unchased"] == 1 and f["n"]["range"] == 1 and f["n"]["caught"] == 1 and f["shelter_end"] == 1
    assert f["n"]["truncated"] == 2                                     # 0·5 가 열려 있다 (세계는 그대로)
    _tick(w, [5])                                                       # 0 끝(obstacle), 5 계속
    f = w.flight_stats()
    assert f["started"] == 5 == sum(f["n"].values())
    assert {c: v for c, v in f["n"].items() if v} == dict(obstacle=1, range=1, unchased=1, caught=1, truncated=1)
    assert f["steps"]["obstacle"] == 3 and f["contact"]["obstacle"] == 2 and f["steps"]["range"] == 2 and f["contact"]["range"] == 1
    assert f["steps"]["unchased"] == 2 and f["contact"]["unchased"] == 0 and f["steps"]["caught"] == 3 and f["contact"]["caught"] == 0
    assert f["own_n"] == 2 and f["own_contact"] == 3 and f["own_steps"] == 5 and f["hist"][0] == 2
    assert f["steps"]["truncated"] == 2 and f["flee_steps"] == 12 == f["reflex_steps"] and f["live_steps"] == 4 * N
    assert w.flight_stats() == f                                        # 부르는 것으로는 아무것도 바뀌지 않는다


def test_cover_held_switch_stop_and_own_flee():
    w = _scene(4)
    M, N = w.M, w.N
    no = np.zeros((M, N), dtype=bool)
    yes = np.ones((M, N), dtype=bool)
    # 0: 표적인 채 은신처 원 안에서 끝 → cover (쫓긴 = 도망 길이), 1: 표적인 채 은신처 밖에서 끝(두뇌 FLEE 를 그만둠) → held
    _tick(w, [0, 1], tgt=_t(M, w0=0, w1=1), reflex=[0], in_cov=[0])
    _tick(w, [])
    f = w.flight_stats()
    assert f["n"]["cover"] == 1 and f["n"]["held"] == 1 and f["contact"]["cover"] == 1 and f["shelter_end"] == 1
    assert f["flee_steps"] == 2 and f["reflex_steps"] == 1                # 1 은 두뇌가 고른 FLEE (반사 아님)
    # 은신처 안이라 표적에서 빠짐(untargetable) → cover, 보이는데 다른 사슴으로 바꿈 → switch
    _tick(w, [2, 3], tgt=_t(M, w0=2, w1=3))
    cov = no.copy()
    cov[0, 2] = True
    _tick(w, [2, 3], tgt=_t(M, w1=0), pred=(np.ones(M, dtype=bool), yes, yes, no.copy(), cov))
    assert w._fl_why[2] == FL_DROP_COVER and w._fl_why[3] == FL_DROP_SWITCH
    _tick(w, [])
    f = w.flight_stats()
    assert f["n"]["cover"] == 2 and f["n"]["switch"] == 1 and f["contact"]["switch"] == 1
    # 같은 스텝에 다른 사슴을 잡아 먹기 시작한 늑대(스텝 끝 쿨다운): 표적이 남아도 표적이 아니다 → 놓침 까닭 그만둠 → stop (끝까지 쫓김 held 가 아니다)
    _tick(w, [0], tgt=_t(M, w0=0))
    _tick(w, [0], tgt=_t(M, w0=0), idle=[0], done=[1], caught=[1])
    assert w._fl_why[0] == FL_DROP_STOP and not w._fl_end_now[0] and w._fl_contact[0] == 1
    _tick(w, [])
    f = w.flight_stats()
    assert f["n"]["stop"] == 1 and f["n"]["held"] == 1
    # 사냥 그만둠은 반경 밖보다 앞선다, 시야각 밖(반경 안·원판 아님) → fov
    _tick(w, [2], tgt=_t(M, w0=2))
    hunt = np.ones(M, dtype=bool)
    hunt[0] = False
    _tick(w, [2], pred=(hunt, no.copy(), no.copy(), no.copy(), no.copy()))
    assert w._fl_why[2] == FL_DROP_STOP
    _tick(w, [3], tgt=_t(M, w0=3))
    _tick(w, [2, 3], pred=(np.ones(M, dtype=bool), yes, no.copy(), no.copy(), no.copy()))
    assert w._fl_why[3] == FL_DROP_FOV
    _tick(w, [])
    f = w.flight_stats()
    assert f["n"]["stop"] == 2 and f["n"]["fov"] == 1 and f["started"] == sum(f["n"].values())
    assert (FL_DROP_RANGE, FL_DROP_SWITCH, FL_DROP_FOV, FL_DROP_STOP, FL_DROP_OBSTACLE, FL_DROP_COVER) == (1, 2, 3, 4, 5, 6)
    assert set(FL_DROP_CAUSE.values()) == {"switch", "range", "fov", "stop", "obstacle", "cover"} and set(FLIGHT_OWN) <= set(FLIGHT_CAUSES)


def test_drop_priority_last_drop_and_respawn():
    w = _scene(4)
    M, N = w.M, w.N
    no = np.zeros((M, N), dtype=bool)
    yes = np.ones((M, N), dtype=bool)
    # 같은 스텝에 둘이 놓치면 큰 번호(원판 > 반경), 다시 쫓긴 뒤 마지막 놓침(반경)이 정한다 → range, 쫓긴 = 마지막 표적 스텝
    _tick(w, [0], tgt=_t(M, w0=0, w1=0))
    rng_ = yes.copy()
    rng_[1, 0] = False
    blk = no.copy()
    blk[0, 0] = True
    _tick(w, [0], pred=(np.ones(M, dtype=bool), rng_, rng_.copy(), blk, no.copy()))
    assert w._fl_why[0] == FL_DROP_OBSTACLE
    _tick(w, [0], tgt=_t(M, w0=0))                                       # 다시 쫓김 (3 스텝째)
    rng_ = yes.copy()
    rng_[0, 0] = False
    _tick(w, [0], pred=(np.ones(M, dtype=bool), rng_, rng_.copy(), no.copy(), no.copy()))
    _tick(w, [])
    f = w.flight_stats()
    assert f["n"]["range"] == 1 and f["n"]["obstacle"] == 0 and f["contact"]["range"] == 3 and f["steps"]["range"] == 4
    # 도망 시작 바로 앞 스텝에만 표적(첫 FLEE 스텝에 놓침): 쫓긴 도망, 쫓긴 시간 0
    _tick(w, [], tgt=_t(M, w0=3))
    _tick(w, [3], pred=(np.ones(M, dtype=bool), yes, yes, blk[:, [3, 1, 2, 0]], no.copy()))
    _tick(w, [])
    f = w.flight_stats()
    assert f["n"]["obstacle"] == 1 and f["contact"]["obstacle"] == 0 and f["hist"][0] == 2
    # 다시 남(학습 세계 꼴): FLEE 중 죽은 칸 → caught, 같은 칸 새 개체가 곧바로 FLEE 하면 새 도망(옛 표적을 잇지 않는다)
    _tick(w, [1], tgt=_t(M, w0=1))
    _tick(w, [1], tgt=_t(M, w0=1), done=[1], caught=[1])
    assert w._fl_len[1] == 0 and w._fl_tgt[0] == -1
    _tick(w, [1])
    _tick(w, [])
    f = w.flight_stats()
    assert f["n"]["caught"] == 1 and f["n"]["unchased"] == 1 and f["started"] == sum(f["n"].values())
    assert w._fl_why[1] == 0 and not w._fl_chased.any() and not w._fl_len.any()


def test_reset_clears_and_reflex_tests_untouched():
    """reset 은 기록을 비운다. 덮기를 직접 정하는 기존 장면(`_wf_update` 직접 부르기)은 기록이 꺼져 있으면 아무것도 세지 않는다."""
    w = _scene(4)
    _tick(w, [0])
    w.reset()
    f = w.flight_stats()
    assert f["started"] == 0 and sum(f["n"].values()) == 0 and f["live_steps"] == 0 and w.track_flight
    w2 = World(load_v2_config(OBS).replace(N=4), seeds=[32087])
    w2.wf_mode[:] = WF_PANIC
    w2._wf_update(np.zeros(4, dtype=bool))
    assert int(w2._fl_len.sum()) == 0 and w2._fl_started == 0


# --------------------------------------------------------------------- #
# 학습 전용 도주 비용 flight_cost
# --------------------------------------------------------------------- #


def test_flight_cost_off_identity_and_sign():
    base = load_v2_config(TRAIN).replace(N=24)
    a, _, _, _ = _run(base, 32002, 600, False, acts_seed=3)
    z, _, _, _ = _run(_with(base, wild_flight=dict(flight_cost=0.0)), 32002, 600, False, acts_seed=3)
    _same(a, z)                                                             # 끔 값 0 = 키 없음 (비트 동일)
    fc = 0.005
    w = World(_with(base, wild_flight=dict(flight_cost=fc)), seeds=[32002])
    assert w._wf["flight_cost"] == fc
    rng = np.random.default_rng(3)
    n_flee = n_own = 0
    for t in range(600):
        pan = w.wf_mode == WF_PANIC
        o, r, d, _ = w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        x = a[t]
        np.testing.assert_array_equal(o, x[0])                              # 궤적 그대로 (보상은 동역학에 들어가지 않는다)
        flee = w._rs.behavior == rep.FLEE                                   # 실행한 FLEE (죽은 칸은 리스폰이 지웠다)
        np.testing.assert_allclose(r[~d], (x[1] - fc * flee)[~d], rtol=0, atol=1e-15)    # FLEE 를 실행한 사슴만 −flight_cost (반사·두뇌 FLEE 모두)
        assert np.all(np.isclose(r[d], x[1][d]) | np.isclose(r[d], x[1][d] - fc))
        n_flee += int((flee & ~d).sum())
        n_own += int((flee & ~d & ~pan).sum())
    assert n_flee > n_own > 0                                               # 두뇌가 고른 FLEE 도 비용을 낸다
    with pytest.raises(ValueError, match="flight_cost"):
        World(_with(base, wild_flight=dict(flight_cost=-0.1)), seeds=[32002])
