"""R9 몸 움직임 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_TURN_EFFORT_DESIGN.md 7-3 M-1~M-16).

M-1 은 손대기 전 HEAD(1b545095 의 R9 파이썬) 에서 잰 옛 설정 셋(`v3_r9.yaml`·`v3_r9_judge.yaml`·`v3_r9_fauna.yaml`) 의 궤적
sha256 기준값이다(특성 문서 B5 꼴). F-1 은 S′ 만 지키므로 동물 세계 기준이 따로 필요하다. 새 몸 규칙은 `body_common.motion` 이
있을 때만 켜지므로 고친 뒤에도 셋 모두 비트까지 같아야 한다.
시드: 스모크·속도 범위 44180~44199 만 쓴다(동물 설계 7-3 과 같음).
"""

import env.torch_init  # noqa: F401  ← torch 보다 먼저

import hashlib
import json

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import r9_body as B
from env_v2 import r9_brains as BR
from env_v2 import r9_life as L
from env_v2 import r9_vec_env as V
from env_v2.r9_world import R9World

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"
FCFG = ROOT / "configs" / "v3_r9_fauna.yaml"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")

# 손대기 전 HEAD 1b545095 기준값 (이 파일의 `old_golden()` 을 그 HEAD 에서 돌려 잼, 2026-11-13)
GOLDEN = {
    "sp_random": "98ee6d153e298eb906260379c4365aa3e585378073813163b56ab31a1bade301",
    "sp_rules": "7f409fc237b5e6b6c3cd522f40b51142c00c9dfd25066fdd9fadf287dc44362d",
    "sp_rules_deaths": [[0, 9, 0, 6], [0, 0, 0, 0], [0, 2, 0, 0]],
    "sp_vec_wolf": "e811b506da3408b4cccd21daf89a162570ef65d3ad103b513c32d3dbb73fee40",
    "sp_hash": {"io_hash": "0x0fa76480fe9465e0",
                "body_hash": {"deer": "0x0d04b5447e42a2c0", "wolf": "0x6ce9605c7a90224a", "boar": "0x8af5915146034953"},
                "body_table_hash": "0xf6e81fcbe4e7c24d"},
    "judge_rules": "131cc4a3bdbffa39ac42ba6f563fc6893f0f750c0fc0547799ee5133968f8ce3",
    "judge_L1_rules": "634325dbab98619f255f8f487d1f1d087f341847158251ce6d57b356fcf1f184",
    "judge_L1_deaths": [[0, 5, 0, 0], [0, 0, 0, 0], [0, 1, 0, 0]],
    "judge_hash": {"io_hash": "0x0fa76480fe9465e0",
                   "body_hash": {"deer": "0x0d04b5447e42a2c0", "wolf": "0x6ce9605c7a90224a", "boar": "0x8af5915146034953"},
                   "body_table_hash": "0xf6e81fcbe4e7c24d"},
    "fauna_random": "18281f0c299160ce0986789210c59075a4f75398ee45ee6c44a3745c97a7b424",
    "fauna_rules": "93c534dfe3ee6d7844b5f6f3c4dea84eed8eea7bde2693792c20848917754646",
    "fauna_rules_deaths": [[0, 8, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
    "fauna_rules_gore": 11,
    "fauna_rules_stoch": "34cfc4b58b6b9110a131a0db680babfc6721917e4a5d6a9b672a6c82418f3e8c",
    "fauna_vec_leopard": "e766d31336f3e71297c73845f7a417c2530349ab1f45e7c65c627dd2a3b26f6a",
    "fauna_hash": {"io_hash": "0x0fa76480fe9465e0",
                   "body_hash": {"deer": "0x2ffa857d6bb1b4b4", "wolf": "0x69532181ee44398b", "boar": "0xd68f2e620798ada3",
                                 "buffalo": "0x44e493d8cc7b39bf", "leopard": "0xc90ea238572238e3", "fox": "0xf8af612d4db1993b"},
                   "body_table_hash": "0x10021edf18997ee3"},
}

STATE = ("pos", "head", "vel", "disp", "E", "R", "stam", "stam_lock", "hp", "alive", "uid", "kin_id", "next_birth", "mating",
         "bite_cd", "gore_cd", "knock_left", "carc_ok", "carc_meat", "carc_places", "grass", "root", "mem")


def _upd(h, *xs):
    for x in xs:
        h.update(np.ascontiguousarray(np.asarray(x)).tobytes())


def _world_hash(w, h):
    for n in STATE:
        _upd(h, getattr(w, n))
    for k, v in sorted(w.stats_snapshot().items()):
        h.update(k.encode())
        _upd(h, v)


def _rules(w, cfg, stochastic=False):
    for k in range(w.K):
        for s in range(w.NS):
            n = V.RULE_OF[s]
            w.set_controller(k, s, BR.Controller(BR.make_rule(n, cfg, s), stochastic, n))


def _random_scene(cfg, seeds, n_dec, seed):
    w = R9World(cfg, seeds)
    rng = np.random.default_rng(seed)
    h = hashlib.sha256()
    _upd(h, w.obs())
    for _ in range(n_dec):
        o, r, d, info = w.step(rng.integers(0, B.N_ACTIONS, (w.K, w.S)))
        _upd(h, o, r, d, info["dead_cause"], info["killer"], info["births"], info["respawned"])
    _world_hash(w, h)
    return h.hexdigest()


def _rule_scene(cfg, seeds, n_dec, stochastic=False):
    w = R9World(cfg, seeds, record=True)
    _rules(w, cfg, stochastic)
    h = hashlib.sha256()
    _upd(h, w.obs())
    for _ in range(n_dec):
        a = w.decide()
        o, r, d, info = w.step(a)
        _upd(h, a, o, r, d, info["dead_cause"], info["killer"], info["births"], info["newborn"])
    w.flush_hunts()
    _world_hash(w, h)
    ls = L.life_stats(w.life)
    for k in ("opportunities", "paired", "births", "blocked", "failed", "cancelled"):
        _upd(h, ls[k])
    h.update(json.dumps({k: v for k, v in w.events.items()}, sort_keys=True, default=str).encode())
    return h.hexdigest(), w


def _vec_scene(cfg, sp, seeds, n_dec, seed):
    v = V.R9VecEnv(cfg, sp, model_seed=0, round_=0, seeds=seeds, num_worlds=4, reset_steps=20, shards=1, online_stats=False)
    try:
        h = hashlib.sha256()
        _upd(h, v.reset())
        r_ = np.random.default_rng(seed)
        for _ in range(n_dec):
            v.step_async(r_.integers(0, B.N_ACTIONS, v.num_envs))
            o, r, d, infos = v.step_wait()
            _upd(h, o, r, d)
        h.update(json.dumps(v.history, sort_keys=True, default=str).encode())
        h.update(json.dumps(v.seed_history).encode())
        return h.hexdigest()
    finally:
        v.close()


def _hashes(cfg) -> dict:
    names = B.species_of(cfg)
    return {"io_hash": B.hash_hex(B.io_hash()),
            "body_hash": {n: B.hash_hex(B.body_hash(cfg, n)) for n in names},
            "body_table_hash": B.hash_hex(B.body_table_hash(cfg))}


def old_golden(cfg: dict, jcfg: dict, fcfg: dict) -> dict:
    """The old-config scenes (same order, seeds and hashing at HEAD and after the change)."""
    out = {}
    # v3_r9.yaml (S′ 학습 세계)
    out["sp_random"] = _random_scene(cfg, [44180, 44181], 120, 44182)
    out["sp_rules"], w = _rule_scene(cfg, [44183, 44184], 300)
    out["sp_rules_deaths"] = w.st["deaths"].sum(0).tolist()
    out["sp_vec_wolf"] = _vec_scene(cfg, "wolf", range(44185, 44195), 30, 44195)
    out["sp_hash"] = _hashes(cfg)
    # v3_r9_judge.yaml (판정 세계 그대로 + L1)
    out["judge_rules"], w = _rule_scene(jcfg, [44186], 60)
    jc = B.override(jcfg, jcfg["judge"]["variants"]["L1"])
    out["judge_L1_rules"], w = _rule_scene(jc, [44187, 44188], 500)
    out["judge_L1_deaths"] = w.st["deaths"].sum(0).tolist()
    out["judge_hash"] = _hashes(jcfg)
    # v3_r9_fauna.yaml (동물 세계 6 종)
    out["fauna_random"] = _random_scene(fcfg, [44189, 44190], 120, 44191)
    out["fauna_rules"], w = _rule_scene(fcfg, [44192, 44193], 300)
    out["fauna_rules_deaths"] = w.st["deaths"].sum(0).tolist()
    out["fauna_rules_gore"] = int(w.st["gore"].sum())
    out["fauna_rules_stoch"], w = _rule_scene(fcfg, [44194], 200, stochastic=True)
    out["fauna_vec_leopard"] = _vec_scene(fcfg, "leopard", range(44180, 44199), 30, 44199)
    out["fauna_hash"] = _hashes(fcfg)
    return out


def test_m1_old_configs_bit_identical():
    """M-1: 옛 설정 셋의 궤적·해시가 손대기 전 HEAD 와 비트까지 같다 (motion 블록이 없으면 새 줄을 안 탄다)."""
    got = old_golden(B.load_r9_config(CFG), B.load_r9_config(JCFG), B.load_r9_config(FCFG))
    assert GOLDEN, "기준값 없음"
    for k, v in GOLDEN.items():
        assert got[k] == v, f"{k}: {got[k]} != {v}"
