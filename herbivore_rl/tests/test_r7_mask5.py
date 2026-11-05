"""R7 반사 밖 두뇌 FLEE 막음 — 마스크 판 5(= 판 4 + 막기)·판 6(대조 '길 끔' = 판 2 + 막기 + 덮기 줄 한 칸) (10-23 사람 결정 '짧게 진단 후 R7',
설계 Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 17절, 선택 키 wild_flight.brain_flee_outside_reflex — env_v2/world.py 모듈 docstring '반사 밖 두뇌 FLEE 막음',
env_v2/rep_policy.py '마스크 판 5·6').

- 끔 = HEAD(fc0662f — 이 기능을 넣기 전): 키 없음·true 세계의 궤적, 판 2·4 학습 경로(VecEnv), 판 4·판 2 거울의 마스크 안 표본 궤적(미리 보기·마스크 포함),
  measure-fdec 짧은 값이 HEAD 와 같다. 옛 계약 해시 넷(관측 18·19·21·24)은 그대로다.
- 판 5 마스크 줄 = 판 4 마스크 줄에서 덮기 밖 결정 행(reads ∧ override 없음)의 칸 1 만 끈 것. 도주 길 결정 {1, 4}·비결정 지금 길·웅크림 HIDE 는 그대로.
- 판 6 마스크 줄: 도주 = FLEE 한 칸, 웅크림 = HIDE 한 칸, 덮기 밖 결정 = 판 2 − FLEE, reads 는 덮기 스텝을 뺀다.
- 세계는 막지 않는다: 같은 행동이면 판 5 세계 = 판 4 세계, 판 6 세계 = 판 2 세계(궤적 비트 단위 — 결정 셈만 판 6 이 덮기 스텝을 뺀다). 막음 통계는
  마스크 밖 FLEE 를 센다(마스크 안 표본이면 0).
- 판 번호(관측 이름 + 세계 키), 판이 다른 모델 거부, 계약 해시(판 5·6 새 값 박음 — 판 5 dict = 판 4 dict + 키 brain_flee_outside_reflex false),
  설정 생성기·f_dec 기록, 학습 경로(VecEnv 막음 칸 0), 시작 두뇌(route0m5 — 가중치 route0 그대로)·짧은 학습 스모크(반사 밖 FLEE 0).
시드는 탐색 32080~32099·학습 32000~32049 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import hashlib
import importlib.util
import json
import math
import re

import numpy as np
import pytest
import yaml

from env.config import ROOT
from env_v2 import features as F
from env_v2.config import load_v2_config
from env_v2.rep_policy import (FLEE_GATE_KEY, MASK_VERSION_GATE, MASK_VERSION_ROUTE, MASK_VERSION_ROUTE_GATE, action_mask, allowed_mask_of,
                               check_mask_version, check_model_mask_version, check_route_allowed, feasible_mask, flee_gated, mask_version_of,
                               rep_params, sample_masked, world_mask_version)
from env_v2.repertoire import FLEE, FREEZE, GRAZE, HIDE, N_BEHAVIORS, SLEEP
from env_v2.world import ROUTE_NONE, WF_NONE, WF_PANIC, WF_SHELTER, World, obs_names

CFG = ROOT / "configs"
OBS = CFG / "v3_wild3_obs_mirror.yaml"            # 관측 21 거울 (판 2)
ROUTE = CFG / "v3_wild3_route_mirror.yaml"        # 관측 24 거울 (판 4)
ROUTE5 = CFG / "v3_wild3_route5_mirror.yaml"      # 관측 24 거울 + 막음 (판 5)
R6 = CFG / "v3_r6_train.yaml"
R6OFF = CFG / "v3_r6off_train.yaml"
R7 = CFG / "v3_r7_train.yaml"
R7OFF = CFG / "v3_r7off_train.yaml"
R7_DIR = ROOT / "results" / "v3" / "r7"
ROUTE0 = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs24route0.zip"
OBS21ZERO = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip"
ROUTE0M5 = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs24route0m5.zip"
OBS21M6 = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero_m6.zip"
BRAIN5 = R7_DIR / "brains" / "v3_r1_g995_s3_obs24route0m5.json"
VERIFY5 = R7_DIR / "brains" / "v3_r1_g995_s3_obs24route0m5.verify.json"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")

# HEAD(fc0662f, 이 기능을 넣기 전)에서 같은 셈으로 잰 값. obs_Forest_sat0·vec_r5_train 은 tests/test_route2_v3.HEAD_HASH 와 같은 값이다
HEAD_HASH = {
    "obs_Forest_sat0": "a1d6cde8248821e73fb379f7196f461f0ec8ba9f0e80a4a0e0b18968a308c343",
    "vec_r5_train": "562f9e4af6a49f7213cb52f3841a86839a9017f5380a3e0f1902ba07d89db73a",
    "vec_r6": "910325dafd252b585574a4a521190d9a34c0b61b3d233019f0677febc527a0ff",          # 판 4 학습 경로 (R6 학습 세계)
    "vec_r6off": "0bf45183fac6d3e1b8efd949b1b6f247e8aaefbc523b835b4dc20293b505a610",       # 판 2 학습 경로 (R6 대조 세계)
    "masked_route_Forest": ("a5f8bc10d39f70ae87a19aecbc269c90cf9af76e740e3a25e8491e65e8c22807", 20115),   # 판 4 거울, 마스크 안 표본 (해시, 결정 셈)
    "masked_obs_Forest": ("dbb4cf0470998578aca122c12bae973b966b5ba6dd89b4348c227d726facb6b1", 24291),     # 판 2 거울
}
HEAD_FDEC_R6 = 0.42809027777777775          # measure_fdec(R6 학습 세계, 시드 32080 × 300 스텝)
HEAD_FDEC_R6OFF = 0.6963194444444445
# 계약 해시: 옛 넷은 바뀌면 안 되고(판 4 는 tests/test_route2_v3.CONTRACT_OBS24), 새 판 5(관측 24)·판 6(관측 21) 은 이 값으로 박는다
CONTRACT_OLD = {(18, 2): 0x7EEA0107339BE4CE, (19, 3): 0xF8C26C7D02542FAE, (21, 2): 0xBC4FC2D45C47C5FD, (24, 4): 0xE302DEE198197444}
CONTRACT_OBS24_MASK5 = 0xAD7BAD5E1ACAF071
CONTRACT_OBS21_MASK6 = 0xE4B66AC546DA1D77


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


GATE = dict(brain_flee_outside_reflex=False)


@pytest.fixture(scope="module")
def discs():
    return _module("_r4_for_r7", ROOT / "results" / "v3" / "r4" / "r4_eval.py").region_discs()


def _forest(path, discs, n=32, **wf):
    c = _with(load_v2_config(path).replace(N=n), wild_weather=dict(region="Forest"), obstacles=dict(fixed=discs["Forest"]),
              wild_satiation=dict(enabled=False))
    return _with(c, wild_flight=wf) if wf else c


@pytest.fixture(scope="module")
def forest(discs):
    return _forest(OBS, discs)


@pytest.fixture(scope="module")
def forest_on(discs):
    return _forest(ROUTE, discs)


def _H(*arrs):
    h = hashlib.sha256()
    for a in arrs:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h


def _traj_hash(cfg, seed, steps, acts_seed=7):
    """tests/test_route2_v3._traj_hash 와 같은 셈(무작위 행동 0..2, 도망 기록의 길·지켜보기 칸 뺌)."""
    w = World(cfg, seeds=[seed])
    w.track_flight = True
    rng = np.random.default_rng(acts_seed)
    h = hashlib.sha256()
    for _ in range(steps):
        o, r, d, to = w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        h.update(_H(o, r, d, to, w.pos, w.pred_pos, w.energy, w.wf_mode, w.wf_dir).digest())
    f = w.flight_stats()
    for k in ("route", "quiet_ends", "hide", "episode"):        # episode = 10-24 쫓김 사건 칸 (HEAD 뒤에 더한 통계 전용 칸)
        f.pop(k, None)
    ws = w.wild_stats()
    ws.pop("panic_quiet_ends", None)
    h.update(json.dumps(dict(flight=f, wild=ws, hunt=w.hunt_stats(), rng=str(w.rng.bit_generator.state)), sort_keys=True, default=str).encode())
    return h.hexdigest()


def _vec_hash(cfg, K, steps, seed):
    """tests/test_route2_v3._vec_hash 와 같은 셈: 마스크 위 균등 표본으로 돌린 VecEnv 관측(마스크 칸 포함)·보상·죽음·읽음·끊긴 관측·누적 수."""
    from env_v2.vec_env import MultiWorldVecEnv

    def upd(h, *arrs):
        for x in arrs:
            x = np.ascontiguousarray(x)
            h.update(str(x.dtype).encode())
            h.update(str(x.shape).encode())
            h.update(x.tobytes())

    v = MultiWorldVecEnv(cfg, num_worlds=K, meta_seed=seed)
    o = v.reset()
    rng = np.random.default_rng(seed)
    h = hashlib.sha256()
    upd(h, o)
    for _ in range(steps):
        m = v.current_masks()
        a = sample_masked(np.ones(m.shape), m, rng.random(len(m)))
        v.step_async(a)
        o, r, d, info = v.step_wait()
        upd(h, o, r, d, v.last_reads)
        for i, inf in enumerate(info):
            if "terminal_observation" in inf:
                upd(h, np.array([i]), inf["terminal_observation"], np.array([inf.get("TimeLimit.truncated", False)]))
    c = v.rep_counts
    h.update(json.dumps({k: (x.tolist() if hasattr(x, "tolist") else x) for k, x in c.items()}, sort_keys=True).encode())
    return h.hexdigest(), v


def _peek_hash(pk):
    h = hashlib.sha256()
    for k in sorted(pk):
        h.update(k.encode())
        a = np.ascontiguousarray(pk[k])
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h.digest()


def _masked_hash(cfg, seed, steps, rs):
    """마스크 안 균등 표본으로 돈 한 판: 스텝마다 미리 보기·마스크·관측·보상·위치·늑대·에너지·덮기·실행 행동 + 끝 통계(도망·야생·사냥·레퍼토리·난수)."""
    w = World(cfg, seeds=[seed])
    w.track_flight = True
    rp = rep_params(cfg)
    rng = np.random.default_rng(rs)
    h = hashlib.sha256()
    for _ in range(steps):
        obs = w.observe()
        pk = w.rep_peek()
        m = action_mask(pk, obs, rp, obs_names=w.obs_names)
        h.update(_peek_hash(pk))
        h.update(_H(m).digest())
        a = sample_masked(np.ones(m.shape), m, rng.random(w.N)).astype(np.float64)[:, None]
        o, r, d, to = w.step(a)
        h.update(_H(o, r, d, to, w.pos, w.pred_pos, w.energy, w.wf_mode, w.wf_dir, w.behavior).digest())
    f = w.flight_stats()
    f.pop("episode", None)              # 10-24 쫓김 사건 칸 (HEAD 뒤에 더한 통계 전용 칸 — 궤적과 옛 칸은 그대로)
    st = json.dumps(dict(flight=f, wild=w.wild_stats(), hunt=w.hunt_stats(), rep=w.repertoire_stats(),
                         rng=str(w.rng.bit_generator.state)), sort_keys=True, default=str)
    h.update(st.encode())
    return h.hexdigest(), w._rep_decide


def _same(w0, w1):
    for k in ("pos", "pred_pos", "energy", "wf_mode", "wf_dir", "behavior"):
        assert np.array_equal(getattr(w0, k), getattr(w1, k)), k


# --------------------------------------------------------------------- #
# 끔 = HEAD (비트 동일)
# --------------------------------------------------------------------- #


def test_gate_off_matches_head(forest, forest_on):
    """키 없음·true = HEAD: 거울 숲 궤적, 판 2·4 학습 경로, 판 4·2 거울의 마스크 안 표본 궤적(미리 보기 dict·마스크 포함), measure-fdec 짧은 값."""
    import train_v3 as tv

    assert F.OPTIONAL_KEYS["wild_flight"]["brain_flee_outside_reflex"] is True
    assert F.with_optional("wild_flight", {})["brain_flee_outside_reflex"] is True
    assert _traj_hash(forest, 32084, 900) == HEAD_HASH["obs_Forest_sat0"]
    assert _traj_hash(_with(forest, wild_flight=dict(brain_flee_outside_reflex=True)), 32084, 900) == HEAD_HASH["obs_Forest_sat0"]
    assert _vec_hash(load_v2_config(CFG / "v3_r5_train.yaml").replace(N=12), 2, 300, 3)[0] == HEAD_HASH["vec_r5_train"]
    h, v = _vec_hash(load_v2_config(R6).replace(N=12), 2, 300, 3)
    assert h == HEAD_HASH["vec_r6"], "판 4 학습 경로"
    assert "gate_flee" not in v.rep_counts and all(FLEE_GATE_KEY not in w.rep_peek() for w in v.worlds)
    assert _vec_hash(load_v2_config(R6OFF).replace(N=12), 2, 300, 3)[0] == HEAD_HASH["vec_r6off"], "판 2 학습 경로"
    assert _masked_hash(forest_on, 32093, 900, 41) == HEAD_HASH["masked_route_Forest"]
    assert _masked_hash(forest, 32093, 900, 41) == HEAD_HASH["masked_obs_Forest"]
    assert tv.measure_fdec(load_v2_config(R6), seeds=(32080,), steps=300)["f_dec"] == HEAD_FDEC_R6
    assert tv.measure_fdec(load_v2_config(R6OFF), seeds=(32080,), steps=300)["f_dec"] == HEAD_FDEC_R6OFF
    for cfg in (forest, forest_on):
        w = World(cfg, seeds=[32084])
        assert w.brain_flee_outside_reflex is True and not w._fb and not hasattr(w, "_fb_free")
        with pytest.raises(ValueError, match="flee_gate_stats"):
            w.flee_gate_stats()


# --------------------------------------------------------------------- #
# 마스크 줄
# --------------------------------------------------------------------- #


def test_mask5_rows(forest_on):
    """판 5 = 판 4 에서 덮기 밖 결정 행(reads ∧ override 없음)의 칸 1 만 끈 마스크. 같은 행동(판 5 마스크 안 표본)이면 판 4 세계와 궤적·미리 보기가 같다.
    도주 길 결정·도주 비결정·웅크림 행은 판 4 그대로. 막음 통계는 덮기 밖 결정(산 사슴)과 두뇌 FLEE 0."""
    c5 = _with(forest_on, wild_flight=GATE)
    w4, w5 = World(forest_on, seeds=[32087]), World(c5, seeds=[32087])
    w4.track_flight = w5.track_flight = True
    assert (world_mask_version(w4), world_mask_version(w5)) == (4, 5) and w5.obs_names == w4.obs_names
    rp = rep_params(c5)
    rng = np.random.default_rng(11)
    n = dict(blocked=0, free=0, route2=0, crouch=0, keep=0)
    free_live = 0
    for _ in range(900):
        o4, o5 = w4.observe(), w5.observe()
        assert np.array_equal(o4, o5)
        pk4, pk5 = w4.rep_peek(), w5.rep_peek()
        assert pk5.pop(FLEE_GATE_KEY) is False and FLEE_GATE_KEY not in pk4
        assert set(pk4) == set(pk5) and all(np.array_equal(pk4[k], pk5[k]) for k in pk4)
        m4 = action_mask(pk4, o4, rp, obs_names=w4.obs_names)
        m5 = action_mask(w5, o5, rp)
        free = pk4["reads"] & (pk4["override"] == WF_NONE)
        want = m4.copy()
        want[free, FLEE] = False
        assert np.array_equal(m5, want)
        assert not m5[free, FLEE].any() and m5.any(1).all() and not m5[:, FREEZE].any()
        pan, cr = pk4["override"] == WF_PANIC, pk4["override"] == WF_SHELTER
        n["blocked"] += int((free & m4[:, FLEE]).sum())
        n["free"] += int(free.sum())
        n["route2"] += int((pk4["route_decide"] & m5[:, FLEE] & m5[:, SLEEP]).sum())
        n["crouch"] += int(cr.sum())
        n["keep"] += int((pan & ~pk4["route_decide"]).sum())
        live = np.ones(w5.N, dtype=bool) if w5.alive is None else w5.alive
        free_live += int((free & live).sum())
        a = sample_masked(np.ones(m5.shape), m5, rng.random(w5.N)).astype(np.float64)[:, None]
        r4, r5 = w4.step(a), w5.step(a)
        for x, y in zip(r4, r5):
            assert np.array_equal(x, y)
        _same(w4, w5)
    assert all(v > 0 for v in n.values()), n
    assert w4.flight_stats() == w5.flight_stats() and w4.rng.bit_generator.state == w5.rng.bit_generator.state
    assert w4._rep_decide == w5._rep_decide, "판 4·5 는 같은 결정 셈(덮기 스텝 뺌)"
    assert w5.flee_gate_stats() == dict(free_decisions=free_live, brain_flee=0)


def test_mask6_rows(forest):
    """판 6(대조 '길 끔'): 도주 행 = FLEE 한 칸, 웅크림 행 = HIDE 한 칸, 덮기 밖 결정 = 판 2 − FLEE, 비결정 = 지금 행동 한 칸, reads 는 덮기 스텝을 뺀다.
    같은 행동이면 판 2 세계와 궤적이 같다(결정 셈만 판 6 이 덮기 스텝을 뺀 값 — rep_peek reads 합과 같다)."""
    c6 = _with(forest, wild_flight=GATE)
    w2, w6 = World(forest, seeds=[32088]), World(c6, seeds=[32088])
    w2.track_flight = w6.track_flight = True
    assert (world_mask_version(w2), world_mask_version(w6)) == (2, 6) and w6.obs_dim == 21
    rp = rep_params(c6)
    rng = np.random.default_rng(13)
    one = np.eye(N_BEHAVIORS, dtype=bool)
    n = dict(pan=0, crouch=0, blocked=0, free=0)
    reads6 = 0
    for _ in range(900):
        o2, o6 = w2.observe(), w6.observe()
        assert np.array_equal(o2, o6)
        pk2, pk6 = w2.rep_peek(), w6.rep_peek()
        assert "override" not in pk2 and pk6[FLEE_GATE_KEY] is False and "route_decide" not in pk6
        live = np.ones(w6.N, dtype=bool) if w6.alive is None else w6.alive
        pan, cr = (w6.wf_mode == WF_PANIC) & live, (w6.wf_mode == WF_SHELTER) & live
        assert np.array_equal(pk6["override"], np.where(pan, WF_PANIC, np.where(cr, WF_SHELTER, WF_NONE)))
        assert np.array_equal(pk6["reads"], pk2["reads"] & ~(pan | cr)), "덮기 스텝은 결정이 아니다"
        assert np.array_equal(pk6["wake_decide"], pk2["wake_decide"] & ~(pan | cr))
        m2 = action_mask(pk2, o2, rp, obs_names=w2.obs_names)
        m6 = action_mask(pk6, o6, rp, obs_names=w6.obs_names)
        assert np.array_equal(m6[pan], np.tile(one[FLEE], (int(pan.sum()), 1))) and np.array_equal(m6[cr], np.tile(one[HIDE], (int(cr.sum()), 1)))
        free = pk6["reads"] & (pk6["override"] == WF_NONE)
        want = m2.copy()
        want[free, FLEE] = False
        rest = ~(pan | cr)
        assert np.array_equal(m6[rest], want[rest]), "덮기 밖 행 = 판 2 − (결정 행의 FLEE)"
        n["pan"] += int(pan.sum())
        n["crouch"] += int(cr.sum())
        n["blocked"] += int((free & m2[:, FLEE]).sum())
        n["free"] += int(free.sum())
        reads6 += int(pk6["reads"].sum())
        a = sample_masked(np.ones(m6.shape), m6, rng.random(w6.N)).astype(np.float64)[:, None]
        r2, r6 = w2.step(a), w6.step(a)
        for x, y in zip(r2, r6):
            assert np.array_equal(x, y)
        _same(w2, w6)
    assert all(v > 0 for v in n.values()), n
    assert w2.flight_stats() == w6.flight_stats() and w2.wild_stats() == w6.wild_stats()
    assert w6._rep_decide == reads6 and w6.repertoire_stats()["decide_frac"] == reads6 / (900 * w6.N)
    assert w6.flee_gate_stats()["brain_flee"] == 0


def test_world_does_not_block(forest_on):
    """세계는 막지 않고 센다: 마스크를 지키지 않는 무작위 행동 0..2 를 넣으면 판 5 세계 궤적 = 판 4 세계 궤적이고, 막음 통계가 덮기 밖 두뇌 FLEE 를 센다
    (그 수 = 덮기 밖 결정(산 사슴) 가운데 행동 1 을 낸 수)."""
    w4, w5 = World(forest_on, seeds=[32089]), World(_with(forest_on, wild_flight=GATE), seeds=[32089])
    w4.track_flight = w5.track_flight = True
    rng = np.random.default_rng(17)
    flee = 0
    for _ in range(600):
        pk = w5.rep_peek()
        a = rng.integers(0, 3, (w5.N, 1)).astype(np.float64)
        live = np.ones(w5.N, dtype=bool) if w5.alive is None else w5.alive
        flee += int((pk["reads"] & (pk["override"] == WF_NONE) & live & (a[:, 0] == FLEE)).sum())
        r4, r5 = w4.step(a), w5.step(a)
        for x, y in zip(r4, r5):
            assert np.array_equal(x, y)
    _same(w4, w5)
    assert w4.flight_stats() == w5.flight_stats()
    g = w5.flee_gate_stats()
    assert g["brain_flee"] == flee > 0 and g["free_decisions"] > g["brain_flee"]


def test_decide_count_matches_reads(forest, forest_on):
    """판 5·6 세계의 결정 셈(_rep_decide·decide_frac)은 rep_peek 의 reads 합과 같다(f_dec 와 같은 셈)."""
    for cfg in (_with(forest_on, wild_flight=GATE), _with(forest, wild_flight=GATE)):
        w = World(cfg, seeds=[32096])
        rp = rep_params(cfg)
        rng = np.random.default_rng(29)
        reads = 0
        for _ in range(600):
            obs = w.observe()
            pk = w.rep_peek()
            m = action_mask(pk, obs, rp, obs_names=w.obs_names)
            reads += int(pk["reads"].sum())
            w.step(sample_masked(np.ones(m.shape), m, rng.random(w.N)).astype(np.float64)[:, None])
        assert w._rep_decide == reads and w.repertoire_stats()["decide_frac"] == reads / (600 * w.N)
        assert w.flee_gate_stats()["brain_flee"] == 0


# --------------------------------------------------------------------- #
# 판 번호·검사·계약
# --------------------------------------------------------------------- #


def test_mask_version_and_checks(forest, forest_on):
    """판 = 관측 이름 + 세계 키: 관측 24 → 4·5, 관측 21 → 2·6, 경보(판 3)와 막음은 섞지 않는다. 판이 다른 모델은 연결 때 멈춘다. 판 5 도 얼기·잠 허용이면 멈춘다.
    세계 키 검사(bool·obs_extra·경보)."""
    n21, n24 = obs_names(load_v2_config(OBS)), obs_names(load_v2_config(ROUTE))
    n19 = obs_names(load_v2_config(CFG / "v3_r2_on.yaml"))
    assert [mask_version_of(n24, b) for b in (True, False)] == [MASK_VERSION_ROUTE, MASK_VERSION_ROUTE_GATE] == [4, 5]
    assert [mask_version_of(n21, b) for b in (True, False)] == [2, MASK_VERSION_GATE] == [2, 6]
    assert mask_version_of(n24) == 4 and mask_version_of(n19) == 3
    with pytest.raises(ValueError, match="경보"):
        mask_version_of(n19, False)
    with pytest.raises(ValueError, match="bool"):
        mask_version_of(n24, 0)
    assert [flee_gated(v) for v in (2, 3, 4, 5, 6)] == [False, False, False, True, True]
    check_mask_version(5, n24, False)
    check_mask_version(6, n21, False)
    for got, names, flag in ((4, n24, False), (5, n24, True), (2, n21, False), (6, n21, True), (6, n24, False), (5, n21, False)):
        with pytest.raises(ValueError, match="마스크 판"):
            check_mask_version(got, names, flag)
    check_model_mask_version(5, n24)
    check_model_mask_version(6, n21)
    check_model_mask_version(4, n24)
    for got, names in ((5, n21), (6, n24), (4, n21)):
        with pytest.raises(ValueError):
            check_model_mask_version(got, names)
    check_route_allowed(("graze", "flee", "hide"), 5)
    check_route_allowed(("graze", "flee", "hide", "freeze"), 6)            # 판 6 은 칸 3·4 를 길로 다시 쓰지 않는다
    with pytest.raises(ValueError, match="얼기·잠"):
        check_route_allowed(("graze", "flee", "hide", "sleep"), 5)
    # 세계 키 검사
    for bad, why in ((dict(brain_flee_outside_reflex=0), "true/false"), (dict(brain_flee_outside_reflex="false"), "true/false")):
        with pytest.raises(ValueError, match=why):
            World(_with(forest_on, wild_flight=bad), seeds=[32084])
    # 경보(판 3)와 섞지 않는다: R7 대조 학습 세계(부활 — 경보는 부활 없는 세계를 받지 않는다)에 v3_r2_on 의 경보 블록을 켜면 키 false 만 멈춘다
    r7off = load_v2_config(R7OFF)
    alarm = r7off.replace(v2=dict(r7off.v2, features=dict(r7off.v2["features"], alarm=dict(load_v2_config(CFG / "v3_r2_on.yaml").v2["features"]["alarm"]))))
    with pytest.raises(ValueError, match="alarm"):
        World(alarm, seeds=[32001])
    assert World(_with(alarm, wild_flight=dict(brain_flee_outside_reflex=True)), seeds=[32001]).obs_dim == 22
    with pytest.raises(ValueError, match="obs_extra"):
        World(_with(forest, wild_flight=GATE, repertoire=dict(obs_extra=False)), seeds=[32084])


@pytest.mark.skipif(not ROUTE0.exists(), reason="ckpt 는 저장소에 없다 (route_extend.py 로 만든다)")
def test_model_world_mismatch_refused(forest_on):
    """판 4 두뇌(route0)는 판 5 세계에, 판 5 두뇌(route0m5)는 판 4 세계에 연결할 때 멈춘다(rollout.RepLearned.bind_world)."""
    from stable_baselines3 import PPO

    from env_v2.rollout import RepLearned

    w5 = World(_with(forest_on, wild_flight=GATE), seeds=[32084])
    with pytest.raises(ValueError, match="마스크 판 4 이 이 세계의 마스크 판 5"):
        RepLearned(PPO.load(str(ROUTE0), device="cpu")).bind_world(w5)
    if ROUTE0M5.exists():
        with pytest.raises(ValueError, match="마스크 판 5 이 이 세계의 마스크 판 4"):
            RepLearned(PPO.load(str(ROUTE0M5), device="cpu")).bind_world(World(forest_on, seeds=[32084]))
        RepLearned(PPO.load(str(ROUTE0M5), device="cpu")).bind_world(w5)


def test_contract_hashes():
    """옛 계약 해시 넷(관측 18·판 2, 19·판 3, 21·판 2, 24·판 4)은 그대로 — 그 dict 에 brain_flee_outside_reflex 키가 없다. 판 5 = 판 4 dict + 키(false),
    판 6 = 판 2 dict + 키. 새 해시 둘은 박은 값이다. 두뇌 골든 세계: 판 5 → 판 5 거울, 판 6 → 만들지 않음."""
    import export_weights_v3 as ex

    names = {18: obs_names(load_v2_config(CFG / "v3_wild3_mirror.yaml")), 19: obs_names(load_v2_config(CFG / "v3_r2_on.yaml")),
             21: obs_names(load_v2_config(OBS)), 24: obs_names(load_v2_config(ROUTE))}
    for (n, v), want in CONTRACT_OLD.items():
        assert len(names[n]) == n and ex.contract_hash(names[n], v) == want, (n, v)
        assert FLEE_GATE_KEY not in ex.contract_dict(names[n], v)
    d4, d5 = ex.contract_dict(names[24], 4), ex.contract_dict(names[24], 5)
    assert d5.pop(FLEE_GATE_KEY) is False and d5["mask"].pop("version") == 5 and d4["mask"].pop("version") == 4 and d5 == d4
    d2, d6 = ex.contract_dict(names[21], 2), ex.contract_dict(names[21], 6)
    assert d6.pop(FLEE_GATE_KEY) is False and "flight_route" not in d6 and d6["mask"].pop("version") == 6
    assert d2["mask"].pop("version") == 2 and d6 == d2
    assert ex.contract_hash(names[24], 5) == CONTRACT_OBS24_MASK5
    assert ex.contract_hash(names[21], 6) == CONTRACT_OBS21_MASK6
    assert ex.flight_route_contract(5) == ex.flight_route_contract(4) is not None and ex.flight_route_contract(6) is None
    assert ex.brain_golden_config_for(names[24], 5) == ex.BRAIN_GOLDEN_CONFIG_ROUTE5 == ROUTE5
    assert ex.brain_golden_config_for(names[24], 4) == ex.brain_golden_config_for(names[24]) == ROUTE
    with pytest.raises(SystemExit, match="판 6"):
        ex.brain_golden_config_for(names[21], 6)


def test_ceval_gate_world():
    """10-24 C++ 이식(R7e 판정 통과 뒤 — 이식 계획서 13절·14절): C++ 평가기(ceval)는 판 5 세계(route + 키 false)를 받는다 — 허용 목록을 지나고 world 블록이
    wild_flight.route·brain_flee_outside_reflex 를 넘긴다(평가기가 두뇌 판과 짝을 본다). 판 6 세계(route 끔 + 키 false — R7 학습 대조 전용)는 C++ 에 없어
    world_block 이 거부한다. (이식 전에는 키 false 를 '옮기지 않는 세계 칸'으로 거부했다.)"""
    cv = _module("_ceval_for_r7", ROOT / "results" / "v3" / "live" / "ceval.py")
    for cfg in (load_v2_config(ROUTE5), _with(load_v2_config(OBS), wild_flight=GATE), load_v2_config(OBS)):
        assert not any("brain_flee_outside_reflex" in x for x in cv.unsupported_settings(cfg.to_dict()))
    wb = cv.world_block(World(load_v2_config(ROUTE5).replace(N=8), seeds=[32091]))["wild_flight"]
    assert (wb["route"], wb["brain_flee_outside_reflex"]) == (True, False)
    with pytest.raises(ValueError, match="판 6"):
        cv.world_block(World(_with(load_v2_config(OBS), wild_flight=GATE).replace(N=8), seeds=[32091]))


# --------------------------------------------------------------------- #
# 설정·학습 경로
# --------------------------------------------------------------------- #


def _y(p):
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _fdec_of(log):
    m = re.search(r"^f_dec = ([0-9.]+) ", log.read_text(encoding="utf-8"), re.M)
    assert m, log
    return float(m.group(1))


def test_configs_generated_and_minimal():
    """생성기(results/v3/r7/make_r7_configs.py)와 같고, 바탕에서 적은 칸만 다르다: 판 5 거울 = 판 4 거울 + version·키, R7 = R6 + version·키·f_dec,
    대조 = R7 + version·route false·f_dec. f_dec 는 measure-fdec 기록과 같고(소수 6 자리) 범주 엔트로피 계수 0.01 그대로. λ 0.98 PPO 설정·도주 비용 0."""
    from diagnose_v2 import config_digest

    gen = _module("_make_r7_configs", R7_DIR / "make_r7_configs.py")
    assert gen.main(["--check"]) == 0
    assert config_digest(load_v2_config(R6)) == "8e60880fa2eb", "바탕(R6 학습 세계)은 그대로"
    mir, mir5 = _y(ROUTE), _y(ROUTE5)
    want = copy.deepcopy(mir)
    want["version"] = "3.wild3route5"
    want["features"]["wild_flight"]["brain_flee_outside_reflex"] = False
    assert mir5 == want
    r6, r7, r7off = _y(R6), _y(R7), _y(R7OFF)
    want = copy.deepcopy(r6)
    want["version"] = "3.r7"
    want["features"]["wild_flight"]["brain_flee_outside_reflex"] = False
    want["train"]["repertoire"].update(f_dec=gen.F_DEC, ent_coef_base=round(0.01 * gen.F_DEC, 8))
    assert r7 == want
    want = copy.deepcopy(r7)
    want["version"] = "3.r7off"
    want["features"]["wild_flight"]["route"] = False
    want["train"]["repertoire"].update(f_dec=gen.F_DEC_OFF, ent_coef_base=round(0.01 * gen.F_DEC_OFF, 8))
    assert r7off == want
    for d in (r7, r7off):
        rp = d["train"]["repertoire"]
        assert math.isclose(rp["ent_coef_base"] / rp["f_dec"], 0.01, rel_tol=1e-6)
        assert d["features"]["wild_flight"]["flight_cost"] == 0.0 and rp["allowed"] == ["graze", "flee", "hide"]
    assert round(_fdec_of(R7_DIR / "logs" / "measure_fdec_r7.log"), 6) == gen.F_DEC
    assert round(_fdec_of(R7_DIR / "logs" / "measure_fdec_r7off.log"), 6) == gen.F_DEC_OFF
    assert _y(gen.PPO_CONFIG)["params"]["gae_lambda"] == 0.98
    w5, w6, wm = World(load_v2_config(R7), seeds=[32001]), World(load_v2_config(R7OFF), seeds=[32001]), World(load_v2_config(ROUTE5), seeds=[32001])
    assert [(w.obs_dim, world_mask_version(w)) for w in (w5, w6, wm)] == [(24, 5), (21, 6), (24, 5)]
    assert wm.alive is not None and w5.alive is None, "거울은 부활 없음, 학습 세계는 부활"


def test_vec_env_gate_training_path():
    """R7·대조 학습 세계 VecEnv: 덮기 밖 결정 행에서 칸 1 이 늘 막히고(마스크 안 표본), 누적 수 gate_flee = 0·gate_free > 0. 판 5 는 관측 24 + 마스크 5,
    도주 길 결정이 읽음에 들고 덮기 스텝은 읽음이 아니다. make_model_rep 이 판 5·6 을 모델에 적는다."""
    import train_v3 as tv
    from env_v2.vec_env import MultiWorldVecEnv

    for path, dim, ver in ((R7, 24, 5), (R7OFF, 21, 6)):
        cfg = load_v2_config(path).replace(N=12)
        v = MultiWorldVecEnv(cfg, num_worlds=2, reset_interval=200, meta_seed=1)
        assert v.obs_dim == dim and v.policy_obs_dim == dim + 5 and world_mask_version(v.worlds[0]) == ver
        v.reset()
        rng = np.random.default_rng(23)
        blocked = 0
        for _ in range(400):
            pks = [w.rep_peek() for w in v.worlds]
            m = v.current_masks()
            free = np.concatenate([pk["reads"] & (pk["override"] == WF_NONE) for pk in pks])
            assert not m[free, FLEE].any()
            ov = np.concatenate([pk["override"] for pk in pks]) != WF_NONE
            rd = np.concatenate([pk.get("route_decide", np.zeros(len(pk["reads"]), dtype=bool)) for pk in pks])
            assert not (np.concatenate([pk["reads"] for pk in pks]) & ov & ~rd).any(), "덮기 스텝은 읽음이 아니다(길 결정만)"
            blocked += int(free.sum())
            a = sample_masked(np.ones(m.shape), m, rng.random(len(m)))
            v.step_async(a)
            v.step_wait()
        c = v.rep_counts
        assert c["gate_flee"] == 0 and c["gate_free"] > 0 and blocked > 0 and v.num_resets > 0
        model = tv.make_model_rep(v, rep_params(cfg), None, seed=0)
        assert model.policy.rep_mask_version == ver


@pytest.mark.skipif(not ROUTE0M5.exists(), reason="ckpt 는 저장소에 없다 (results/v3/r7/r7_start.py 로 만든다)")
def test_training_smoke_no_flee_outside_reflex(discs):
    """짧은 학습 스모크: route0m5 에서 R7 학습 세계(세계 둘, λ 0.98 PPO 설정 — train_v3 main 과 같은 조립)로 PPO 두 롤아웃. 학습 중 덮기 밖 두뇌 FLEE 0,
    칸 3(COVER 자리) 줄은 그대로, 배운 두뇌의 배포(argmax)를 판 5 거울에서 돌려도 덮기 밖 두뇌 FLEE 0·두뇌 스스로 뛴 도망(길 none) 0.
    판 4 두뇌(route0)는 이 설정에 실리지 않는다(판이 다르다)."""
    import torch

    import train_v3 as tv
    from env_v2.rollout import RepLearned
    from env_v2.vec_env import MultiWorldVecEnv
    from train import load_tuned
    from train_v2 import apply_lr_schedule, resolve_gamma

    cfg = load_v2_config(R7)
    rep = rep_params(cfg)
    venv = MultiWorldVecEnv(cfg, num_worlds=2, meta_seed=0)
    n_steps = 64
    tuned, _, _ = resolve_gamma(load_tuned(CFG / "ppo_r6_lam098.yaml"), tv.S1A_GAMMA)
    tuned, _ = apply_lr_schedule(tuned, "constant")
    model = tv.make_model_rep(venv, rep, None, n_steps=n_steps, seed=0, **tuned)
    assert model.policy.rep_mask_version == 5 and model.gae_lambda == 0.98
    if ROUTE0.exists():
        with pytest.raises(SystemExit, match="마스크 판"):
            tv.init_from_model(model, ROUTE0, "시험 — route0 (판 4)")
    tv.init_from_model(model, ROUTE0M5, "시험 — route0m5 (tests/test_r7_mask5.py)")
    W0 = model.policy.action_net.weight.detach().clone()
    model.learn(total_timesteps=2 * n_steps * venv.num_envs, progress_bar=False)
    c = venv.rep_counts
    assert c["gate_flee"] == 0 and c["gate_free"] > 0
    W = model.policy.action_net.weight.detach()
    assert torch.equal(W[FREEZE], W0[FREEZE]) and not torch.equal(W[GRAZE], W0[GRAZE])
    w = World(_forest(ROUTE5, discs), seeds=[32094])
    w.track_flight = True
    pol = RepLearned(model)
    pol.bind_world(w)
    for _ in range(600):
        w.step(pol(w.observe()))
    assert w.flee_gate_stats()["brain_flee"] == 0 and w.flee_gate_stats()["free_decisions"] > 0
    rt = w.flight_stats()["route"]
    assert sum(rt["by_route"]["none"]["n"].values()) == 0 and w.flight_stats()["started"] > 0


# --------------------------------------------------------------------- #
# 시작 두뇌 (results/v3/r7/r7_start.py)
# --------------------------------------------------------------------- #


@pytest.mark.skipif(not (ROUTE0.exists() and OBS21ZERO.exists() and ROUTE0M5.exists() and OBS21M6.exists()),
                    reason="ckpt 는 저장소에 없다 (results/v3/r7/r7_start.py 로 만든다)")
def test_start_brains(tmp_path):
    """route0m5·obs21zero_m6: 가중치(state_dict)가 원 모델과 같고 판만 5·6. 다시 만들어도 zip 바이트가 같다. 판 5 두뇌 파일은 계약 관측 24·판 5 해시,
    골든 세계 판 5 거울, 가중치 바이트 = route0 두뇌 파일. 확인 기록: 산 사슴의 다른 결정이 없는 판은 궤적이 같고, 새 판 세계의 덮기 밖 두뇌 FLEE 0."""
    import torch
    from stable_baselines3 import PPO

    st = _module("_r7_start_for_test", R7_DIR / "r7_start.py")
    a = st.relabel(ROUTE0, tmp_path / "a.zip", 5, 4)
    b = st.relabel(ROUTE0, tmp_path / "b.zip", 5, 4)
    assert a["sha256"] == b["sha256"] == hashlib.sha256(ROUTE0M5.read_bytes()).hexdigest(), "같은 원 모델이면 같은 zip 바이트"
    assert a["weights_sha256"] == a["src_weights_sha256"] and a["policy_pth_same"]
    c = st.relabel(OBS21ZERO, tmp_path / "c.zip", 6, 2)
    assert c["sha256"] == hashlib.sha256(OBS21M6.read_bytes()).hexdigest() and c["weights_sha256"] == c["src_weights_sha256"]
    for new, old, ver in ((ROUTE0M5, ROUTE0, 5), (OBS21M6, OBS21ZERO, 6)):
        pn, po = PPO.load(str(new), device="cpu").policy, PPO.load(str(old), device="cpu").policy
        assert pn.rep_mask_version == ver and tuple(pn.rep_obs_names) == tuple(po.rep_obs_names) and tuple(pn.rep_allowed) == tuple(po.rep_allowed)
        sn, so = pn.state_dict(), po.state_dict()
        assert set(sn) == set(so) and all(torch.equal(sn[k], so[k]) for k in so)
    with pytest.raises(ValueError, match="마스크 판 6 이 이 세계의 마스크 판 5"):
        st.relabel(ROUTE0, tmp_path / "x.zip", 6, 4)                 # 판 6 은 관측 24 가 아니다(관측 24 + 막음 = 판 5)
    with pytest.raises(SystemExit, match="마스크 판"):
        st.relabel(ROUTE0M5, tmp_path / "y.zip", 5, 4)               # 원 판이 4 가 아니다
    d = json.loads(BRAIN5.read_text(encoding="utf-8"))
    d0 = json.loads((ROOT / "results" / "v3" / "route" / "brains" / "v3_r1_g995_s3_obs24route0.json").read_text(encoding="utf-8"))
    assert d["contract_hash"] == f"0x{CONTRACT_OBS24_MASK5:016x}" and d["mask_version"] == 5 and d["obs_dim"] == 24
    assert d["contract"][FLEE_GATE_KEY] is False and d["contract"]["flight_route"] == d0["contract"]["flight_route"]
    assert d["weights_sha256"] == d0["weights_sha256"] and [L["w_f32le_b64"] for L in d["layers"]] == [L["w_f32le_b64"] for L in d0["layers"]]
    assert d["golden"]["world_config"] == "configs/v3_wild3_route5_mirror.yaml" and d["model"]["sha256"] == a["sha256"]
    # 골든의 다중 칸 결정(rollout — 덮기 밖 결정 행, 웅크림은 한 칸이라 들지 않는다)은 판 5 마스크라 칸 1 이 늘 막혀 있다
    roll = [c for c in d["golden"]["cases"] if c["kind"] == "rollout"]
    assert roll and all(c["obs"][d["obs_names"].index("in_panic")] == 0.0 and c["mask"][FLEE] == 0 for c in roll)
    assert {c["action"] for c in roll} <= {GRAZE, HIDE}
    v = json.loads(VERIFY5.read_text(encoding="utf-8"))
    assert v["steps"] >= 1800 and v["models"]["route0m5"]["weights_same"] and v["models"]["obs21zero_m6"]["weights_same"]
    for name in ("route0m5", "obs21zero_m6"):
        x = v["pairs"][name]
        assert x["worlds"] == 12 and x["gate_flee_new"] == 0
        assert all(r["same"] for r in x["runs"] if r["argmax_diff"] == 0)
        assert x["argmax_diff"] == sum(r["argmax_diff"] for r in x["runs"]) and x["free_decisions"] > 0
