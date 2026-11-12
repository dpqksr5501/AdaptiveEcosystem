"""R9 동물 세계 1 단계 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md 7-1 F-1~F-13).

F-1 은 손대기 전 HEAD(76950dfb 의 R9 파이썬) 에서 잰 S′ 세 종 세계 기준값이다(설계 9-1 B5). 옛 설정(`v3_r9.yaml`·`v3_r9_judge.yaml`)
으로 아홉 장면의 sha256 과 입출력·몸·몸 표 해시가 모두 같아야 한다 — 새 종·새 몸 규칙은 `body_common.fauna` 가 있을 때만 켜진다.
시드: 스모크·속도 범위 44180~44199 만 쓴다(설계 7-3).
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
from env_v2.r9_world import R9World

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")

# 손대기 전 HEAD 기준값 (SP/species/bench/golden_sprime_baseline.py, 2026-11-13 다시 돌려 설계 9-3 값과 같음을 확인)
GOLDEN = {
    "train_random19": "226d9fb484bccc24db18ed3bad5cefcb6511ddef0fca652f54dbfb5e7bc41e34",
    "train_rules400": "8ce1907953265e59ae599850e00e3c84317ee55eb89876c959c69932348c6183",
    "train_rules400_bites": [[6, 0, 0], [0, 0, 0], [2, 4, 7]],
    "train_rules400_deaths": [[0, 6, 0, 4], [0, 0, 0, 0], [0, 2, 0, 0]],
    "judge_L1_rules700": "30ae6875e878a11b17faf1c5080188380d1cb48d8d542cdc45cf9de50d1437a4",
    "judge_L1_births": [5, 2, 0],
    "vecenv_deer": "5cebf5dcbaa6971a055e5b5d163de0ab72ce48edd740ee90d9d6c1f451e18fcf",
    "vecenv_wolf": "65c1f860dc66504d2ae68f1758f7728624aa92980e65aa84bc69e6eb6179016e",
    "vecenv_boar": "f7793af1e66cbbf76d0c3f1c3a1c28f3cdff97e175e3ed29b8d3afd13c02636a",
    "io_hash": "0x0fa76480fe9465e0",
    "body_hash": {"deer": "0x0d04b5447e42a2c0", "wolf": "0x6ce9605c7a90224a", "boar": "0x8af5915146034953"},
    "body_table_hash": "0xf6e81fcbe4e7c24d",
}

STATE = ("pos", "head", "vel", "E", "R", "stam", "hp", "alive", "uid", "kin_id", "next_birth", "mating", "bite_cd",
         "carc_ok", "carc_meat", "grass", "root", "mem")
RULE3 = {0: "RULE_DEER", 1: "RULE_WOLF", 2: "RULE_BOAR"}


def _upd(h, *xs):
    for x in xs:
        h.update(np.ascontiguousarray(np.asarray(x)).tobytes())


def _world_hash(w, h):
    for n in STATE:
        _upd(h, getattr(w, n))


def sprime_golden(cfg: dict, jcfg: dict) -> dict:
    """The nine S′ scenes of the baseline script (same order, same seeds, same hashing)."""
    out = {}
    w = R9World(cfg, [44180, 44181, 44182])
    rng = np.random.default_rng(44183)
    h = hashlib.sha256()
    _upd(h, w.obs())
    for _ in range(150):
        o, r, d, info = w.step(rng.integers(0, B.N_ACTIONS, (w.K, w.S)))
        _upd(h, o, r, d, info["dead_cause"], info["births"], info["respawned"])
    _world_hash(w, h)
    for k, v in sorted(w.stats_snapshot().items()):
        _upd(h, v)
    out["train_random19"] = h.hexdigest()

    w = R9World(cfg, [44184, 44185])
    for k in range(w.K):
        for s in range(B.N_SPECIES):
            w.set_controller(k, s, BR.Controller(BR.make_rule(RULE3[s], cfg, s), True, "rule"))
    h = hashlib.sha256()
    _upd(h, w.obs())
    for _ in range(400):
        a = w.decide()
        o, r, d, info = w.step(a)
        _upd(h, a, o, r, d, info["dead_cause"], info["killer"], info["births"])
    _world_hash(w, h)
    for k, v in sorted(w.stats_snapshot().items()):
        _upd(h, v)
    out["train_rules400"] = h.hexdigest()
    out["train_rules400_bites"] = w.st["bites"].sum(0).tolist()
    out["train_rules400_deaths"] = w.st["deaths"].sum(0).tolist()

    jc = B.override(jcfg, jcfg["judge"]["variants"]["L1"])
    w = R9World(jc, [44186, 44187])
    for k in range(w.K):
        for s in range(B.N_SPECIES):
            w.set_controller(k, s, BR.Controller(BR.make_rule(RULE3[s], jc, s), False, "rule"))
    h = hashlib.sha256()
    _upd(h, w.obs())
    for _ in range(700):
        a = w.decide()
        o, r, d, info = w.step(a)
        _upd(h, a, o, r, d, info["dead_cause"], info["newborn"])
    _world_hash(w, h)
    ls = L.life_stats(w.life)
    for k in ("opportunities", "paired", "births", "blocked", "failed", "cancelled"):
        _upd(h, ls[k])
    out["judge_L1_rules700"] = h.hexdigest()
    out["judge_L1_births"] = ls["births"].sum((0, 1)).tolist()

    from env_v2.r9_vec_env import R9VecEnv
    for sp in B.SPECIES:
        v = R9VecEnv(cfg, sp, model_seed=0, round_=0, seeds=range(44188, 44199), num_worlds=4, reset_steps=20, shards=1,
                     online_stats=False)
        h = hashlib.sha256()
        _upd(h, v.reset())
        r_ = np.random.default_rng(44199)
        for _ in range(35):
            v.step_async(r_.integers(0, B.N_ACTIONS, v.num_envs))
            o, r, d, infos = v.step_wait()
            _upd(h, o, r, d)
        h.update(json.dumps(v.history, sort_keys=True, default=str).encode())
        h.update(json.dumps(v.seed_history).encode())
        v.close()
        out[f"vecenv_{sp}"] = h.hexdigest()

    out["io_hash"] = B.hash_hex(B.io_hash())
    out["body_hash"] = {n: B.hash_hex(B.body_hash(cfg, n)) for n in B.SPECIES}
    out["body_table_hash"] = B.hash_hex(B.body_table_hash(cfg))
    return out


def test_f1_sprime_bit_identical():
    """F-1: 옛 설정의 S′ 세 종 세계가 손대기 전 HEAD 와 비트까지 같다."""
    got = sprime_golden(B.load_r9_config(CFG), B.load_r9_config(JCFG))
    for k, v in GOLDEN.items():
        assert got[k] == v, f"{k}: {got[k]} != {v}"
