"""R9 몸 표·입출력 계약 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 3-3·4·5·3-9·7-10·11절, 12절 6 의 표 부분).

1. 관측 115 칸 (S′ 2026-11-12): 4절 배치(자기 31 = 23 + food_dir 8 + 다른 종 6 × 11 + 동족 요약 4 + 가까운 동족 2 × 7), 슬라이스·칸 도움
   함수, 이름에 종 이름표가 없다. (예전 107 칸 시험의 뜻을 바꿈: 자기 칸 0~22 번호는 그대로, food_dir 23~30, 뒤 블록 8 칸 밀림)
2. 행동 19 칸: 5절 번호·이름, 걷기·뛰기 방향 번호, 묶음 마스크.
3. 8 방향·황금각 리터럴 표가 cos·sin 과 1e-15 안에서 같고 단위 벡터다. 표로 돌린 벡터 = 삼각함수로 돌린 벡터(1e-15).
4. 몸 표: 3-3 값과 파생 값(몸 크기·지방 용량·지구력 고리·시야각), (K, S) 펼치기.
5. 계약 해시: 같은 설정 → 같은 값, 키 차례·정수/실수 표기와 무관, 값이 바뀌면 그 종만 바뀜, 학습·판정 설정의 몸 해시가 같음, 입출력 해시 고정값.
6. 설정: 판정 설정이 학습 설정을 물려받고, 덧붙임 판(L0·L1·LS …)을 덮어쓸 수 있다.
"""

import copy
import math

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import r9_body as B

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"

# 입출력 계약 해시 고정값. 관측 이름·정규화·행동·결정 간격·망 모양 가운데 하나라도 바뀌면 이 값이 바뀐다 —
# 일부러 바꿨으면 여기를 고치고 계약 문서·두뇌 npz 를 함께 다시 만든다.
IO_HASH_PINNED = 0x0FA76480FE9465E0                # S′ 115 칸 (2026-11-12, 예전 107 칸 0xFFA0833A08D7A81A)


@pytest.fixture(scope="module")
def cfg():
    return B.load_r9_config(CFG)


@pytest.fixture(scope="module")
def jcfg():
    return B.load_r9_config(JCFG)


# --------------------------------------------------------------------------- 1


def test_obs_layout_115():
    assert B.OBS_DIM == 115 and len(B.OBS_NAMES) == 115 and len(set(B.OBS_NAMES)) == 115
    assert (B.N_SELF, B.N_OTHER, B.N_OF, len(B.OBS_KINSUM_NAMES), B.N_KIN, B.N_KF) == (31, 6, 11, 4, 2, 7)
    assert (B.OTHER0, B.KINSUM0, B.KIN0) == (31, 97, 101)
    assert B.OBS_NAMES[B.SL_FOOD_DIR] == tuple(f"food_dir_{j}" for j in range(8)) and B.O_FOOD_DIR0 == 23
    assert B.OBS_NAMES[B.SL_SELF] == B.OBS_SELF_NAMES
    assert all(n.startswith(f"o{j}_") for j in range(6) for n in B.OBS_NAMES[B.OTHER0 + 11 * j: B.OTHER0 + 11 * (j + 1)])
    assert B.OBS_NAMES[B.SL_KINSUM] == ("kin_count", "kin_run_frac", "kin_flow_x", "kin_flow_y")
    assert all(n.startswith(f"k{j}_") for j in range(2) for n in B.OBS_NAMES[B.KIN0 + 7 * j: B.KIN0 + 7 * (j + 1)])
    # 4-2 자기 칸 번호 (문서 표 그대로)
    want = {"energy": 0, "reserve": 1, "stamina": 2, "health": 3, "own_size": 4, "age_frac": 5, "birth_wait": 6, "food_density": 7,
            "food_here": 8, "in_shelter": 9, "shelter_x": 10, "shelter_y": 11, "shelter_edge": 12, "own_speed": 21, "mating": 22}
    for n, i in want.items():
        assert B.OBS_INDEX[n] == i
    assert [B.OBS_INDEX[f"free_{j}"] for j in range(8)] == list(range(13, 21))
    assert (B.O_FREE0, B.O_OWN_SPEED, B.O_MATING) == (13, 21, 22)
    for j in range(6):
        for f in B.OBS_OTHER_FIELDS:
            assert B.OBS_NAMES[B.other_col(j, f)] == f"o{j}_{f}"
    for j in range(2):
        for f in B.OBS_KIN_FIELDS:
            assert B.OBS_NAMES[B.kin_col(j, f)] == f"k{j}_{f}"
    # 종 이름표가 칸 이름에 없다 (4-5·4-6)
    bad = ("deer", "wolf", "boar", "pig", "pred", "prey", "threat", "species", "hunt")
    assert not any(b in n for n in B.OBS_NAMES for b in bad)


# --------------------------------------------------------------------------- 2


def test_actions_19():
    assert B.N_ACTIONS == 19 and len(B.ACTION_NAMES) == 19 and len(set(B.ACTION_NAMES)) == 19
    assert B.ACTION_NAMES[B.EAT] == "EAT" and B.ACTION_NAMES[B.SHELTER] == "SHELTER" and B.ACTION_NAMES[B.WATCH] == "WATCH"
    assert [B.ACTION_NAMES[a] for a in range(1, 9)] == [f"WALK_{45 * j}" for j in range(8)]
    assert [B.ACTION_NAMES[a] for a in range(9, 17)] == [f"RUN_{45 * j}" for j in range(8)]
    j = B.action_dir_index(np.arange(19))
    assert j.tolist() == [-1] + list(range(8)) + list(range(8)) + [-1, -1]
    assert B.action_mask(["run", "shelter"]).nonzero()[0].tolist() == list(range(9, 17)) + [17]
    assert B.action_mask([]).sum() == 0
    with pytest.raises(ValueError):
        B.action_mask(["fly"])


# --------------------------------------------------------------------------- 3


def test_direction_tables_match_trig():
    ang8 = np.arange(8) * (math.pi / 4.0)
    ref8 = np.stack([np.cos(ang8), np.sin(ang8)], -1)
    assert B.DIR8.shape == (8, 2) and B.DIR8.dtype == np.float64
    assert np.abs(B.DIR8 - ref8).max() <= 1e-15
    angg = np.arange(8) * B.GOLDEN_ANGLE_RAD
    refg = np.stack([np.cos(angg), np.sin(angg)], -1)
    assert B.GOLDEN8.shape == (8, 2)
    assert np.abs(B.GOLDEN8 - refg).max() <= 1e-15
    for t in (B.DIR8, B.GOLDEN8):
        assert np.abs(np.sqrt((t * t).sum(1)) - 1.0).max() <= 2e-16
        assert not t.flags.writeable
    # 표로 돌린 머리 = 삼각함수로 돌린 머리 (5절 'WALK_k/RUN_k = 머리에서 왼쪽으로 (k − 1) × 45°').
    # 표 값은 위에서 1e-15 로 맞췄다. 여기서는 각도 합(th + ang)과 곱 둘의 반올림이 겹쳐 1e-15 를 조금 넘을 수 있어 4e-15 로 본다.
    rng = np.random.default_rng(44350)
    th = rng.uniform(0.0, 2 * math.pi, 64)
    h = np.stack([np.cos(th), np.sin(th)], -1)                       # (64, 2)
    for jj in range(8):
        got = B.rotate(h, np.broadcast_to(B.DIR8[jj], h.shape))
        want = np.stack([np.cos(th + ang8[jj]), np.sin(th + ang8[jj])], -1)
        assert np.abs(got - want).max() <= 4e-15
    # 모든 행에 다른 방향 (8, 2) 브로드캐스트
    got = B.rotate(np.broadcast_to(h[:1], (8, 2)), B.DIR8)
    want = np.stack([np.cos(th[0] + ang8), np.sin(th[0] + ang8)], -1)
    assert np.abs(got - want).max() <= 4e-15


def test_hear_radius_and_quadrant():
    s = np.array([0.0, 0.029, 0.03, 0.18, 0.39, 0.6, 1.0, 0.087, 0.24])
    r = B.hear_radius(s)
    assert r[0] == 0.0 and r[1] == 0.0 and r[2] == 2.0 and r[3] == 2.0
    assert r[5] == 20.0 and r[6] == 20.0
    assert abs(r[8] - (2 + 18 * (0.24 - 0.18) / 0.42)) < 1e-12       # 걷는 사슴 4.6 (4-1)
    assert r[7] == 2.0                                               # 걷는 멧돼지 2
    P = np.array([[1.0, 1.0], [61.0, 1.0], [1.0, 61.0], [61.0, 61.0], [60.0, 59.999]])
    assert B.quadrant_of(P, 120.0, 4).tolist() == [0, 1, 2, 3, 1]
    assert B.quadrant_of(P, 120.0, 1).tolist() == [0, 0, 0, 0, 0]


# --------------------------------------------------------------------------- 4


def test_body_table_values(cfg):
    b = B.load_body(cfg)
    D, W, R = B.DEER, B.WOLF, B.BOAR
    assert B.SPECIES == ("deer", "wolf", "boar") and (D, W, R) == (0, 1, 2)
    assert np.allclose(b.size0, [1.0, (40 / 60) ** (1 / 3), (80 / 60) ** (1 / 3)], atol=1e-15)
    assert abs(b.size0[W] - 0.87) < 0.005 and abs(b.size0[R] - 1.10) < 0.005         # 3-3 표 0.87·1.10
    assert np.allclose(b.reserve_cap, [5.4, 0.81, 1.26], atol=1e-5)                    # 3 일 × 900 × 대사
    assert b.walk_speed.tolist() == [0.24, 0.18, 0.0866667] and b.run_speed.tolist() == [0.6, 0.6, 0.42]
    assert (b.run_mult_lo[W], b.run_mult_hi[W]) == (0.9, 1.05) and b.run_mult_lo[D] == b.run_mult_hi[D] == 1.0
    assert b.accel.tolist() == [0.12, 0.10, 0.06]
    # 지구력: 가득 → 잠김(0.15)까지 뛰기 스텝, 0.15 → 0.55 회복 스텝 (3-3). 멧돼지 = Fauna −0.09/초·+0.13/초
    assert np.allclose(b.stam_drain * b.stam_run_steps, 0.85) and np.allclose(b.stam_recover * b.stam_recover_steps, 0.40)
    assert abs(b.stam_drain[R] - 0.09 * B.STEP_S) < 1e-9 and abs(b.stam_recover[R] - 0.13 * B.STEP_S) < 1e-9
    assert b.stam_run_steps[D] == 90 and b.stam_run_steps[W] == 300
    assert np.allclose(b.fov_cos, [math.cos(math.radians(150)), math.cos(math.radians(125)), math.cos(math.radians(150))])
    assert b.see_r.tolist() == [20.0, 20.0, 8.0] and b.smell_r.tolist() == [3.0, 5.0, 6.0] and b.head_down.tolist() == [0.6] * 3
    assert b.drain.tolist() == [0.002, 0.0003, 0.000466667]
    # 식성·먹는 속도·에너지 (3-3)
    assert b.eats.tolist() == [[True, False, False], [False, False, True], [True, True, True]]
    assert b.diet_order == ((B.GRASS,), (B.MEAT,), (B.ROOT, B.MEAT, B.GRASS))
    assert np.allclose(b.eat_rate * b.e_per_unit, [[0.006, 0, 0], [0, 0, 0.016], [0.0018, 0.0027, 0.04 * B.STEP_S]], atol=1e-9)
    assert b.plant_eater.tolist() == [True, False, True]
    # 은신처·물기·반격·HP
    assert b.shelter_enter.tolist() == [True, False, True]
    assert b.bites[W].tolist() == [True, False, True] and not b.bites[D].any() and not b.bites[R].any()
    assert b.can_bite.tolist() == [False, True, False] and b.counter.tolist() == [False, False, True]
    assert b.has_hp.tolist() == [False, True, True]
    assert np.allclose(b.hp_regen, [0.0, 0.25 / 900, 0.25 / 900])
    # 생애 (3-7)
    assert b.maturity.tolist() == [2700, 1350, 900]
    assert b.sex_mode.tolist() == [B.SEXMODE_NATURAL, B.SEXMODE_NONE, B.SEXMODE_ALTERNATE]
    assert b.mate_r.tolist() == [10.0, 10.0, 5.0] and b.birth_r.tolist() == [15.0, 15.0, 7.5]
    assert b.birth_grace.tolist() == [0, 0, 150]
    assert b.pair_block[D].nonzero()[0].tolist() == list(range(9, 18))
    assert b.pair_block[R].nonzero()[0].tolist() == list(range(9, 17)) and not b.pair_block[W].any()
    assert not b.birth_block[D].any() and b.birth_block[R].nonzero()[0].tolist() == list(range(9, 17))
    assert b.pending_needs_parent.tolist() == [True, True, False]
    assert b.child_center.tolist() == [B.CHILD_AT_PARENT_A, B.CHILD_AT_PARENT_A, B.CHILD_AT_MIDPOINT]
    assert b.child_avoid_shelter.tolist() == [False, True, False]
    assert b.founder_kind.tolist() == [B.FOUNDER_NATURAL, B.FOUNDER_PLAIN, B.FOUNDER_PLAIN]
    assert b.founder_variation.tolist() == [0.08, 0.0, 0.0]
    assert b.growth_smooth.tolist() == [True, False, True]
    assert b.common["bite"]["cone_cos"] == 0.5 and b.common["counter"]["cone_cos"] == 0.25
    assert b.common["carcass"]["places"] == 3 and b.common["carcass"]["decay_steps"] == 1350


def test_expand_body_slots(cfg):
    b = B.load_body(cfg)
    sp = np.array([[0, 0, 1, 2, 2], [2, 1, 0, 0, 1]], dtype=np.int8)
    sb = B.expand_body(b, sp)
    assert set(sb) == set(B.SLOT_FIELDS) | set(B.SLOT_FOOD_FIELDS)
    for f in B.SLOT_FIELDS:
        assert sb[f].shape == sp.shape
        assert np.array_equal(sb[f], getattr(b, f)[sp.astype(np.int64)])
    for f in B.SLOT_FOOD_FIELDS:
        assert sb[f].shape == sp.shape + (B.N_FOODS,)
    assert sb["see_r"][0].tolist() == [20.0, 20.0, 20.0, 8.0, 8.0]
    assert sb["eats"][0, 2].tolist() == [False, False, True]


# --------------------------------------------------------------------------- 5


def test_contract_hashes_stable(cfg, jcfg):
    h = [B.body_hash(cfg, s) for s in range(3)]
    assert h == [B.body_hash(B.load_r9_config(CFG), s) for s in range(3)]
    assert h == [B.body_hash(cfg, n) for n in B.SPECIES]
    assert len(set(h)) == 3 and all(0 <= x < 2 ** 64 for x in h)
    # 판정 세계 설정이 몸 블록을 건드리지 않는다 (학습한 두뇌를 판정 세계가 받는다)
    assert h == [B.body_hash(jcfg, s) for s in range(3)]
    assert B.body_table_hash(cfg) == B.body_table_hash(jcfg)
    for name, patch in jcfg["judge"]["variants"].items():
        v = B.override(jcfg, patch)
        assert [B.body_hash(v, s) for s in range(3)] == h, name
    # 키 차례·정수/실수 표기와 무관
    c2 = copy.deepcopy(cfg)
    c2["species"] = {n: dict(reversed(list(cfg["species"][n].items()))) for n in reversed(B.SPECIES)}
    c2["body_common"] = dict(reversed(list(cfg["body_common"].items())))
    c2["species"]["deer"]["mass_kg"] = 60
    c2["species"]["wolf"]["stamina_run_steps"] = 300.0
    assert [B.body_hash(c2, s) for s in range(3)] == h and B.body_table_hash(c2) == B.body_table_hash(cfg)
    # 몸 값이 바뀌면 그 종만 바뀐다 (C0-6 사슴 먹는 속도)
    c3 = B.override(cfg, {"species": {"deer": {"eat_rate": {"grass": 0.009}}}})
    h3 = [B.body_hash(c3, s) for s in range(3)]
    assert h3[0] != h[0] and h3[1:] == h[1:] and B.body_table_hash(c3) != B.body_table_hash(cfg)
    # 공통 몸 규칙은 세 종 모두 (C0-3 반격 각도)
    c4 = B.override(cfg, {"body_common": {"counter": {"cone_cos": 0.5}}})
    assert all(B.body_hash(c4, s) != h[s] for s in range(3))
    # 세계 값(풀 재생·마릿수)은 몸 해시 밖
    c5 = B.override(cfg, {"food": {"grass": {"regen_base": 0.003}}, "counts": {"deer": [20, 40]}})
    assert [B.body_hash(c5, s) for s in range(3)] == h
    assert B.hash_hex(h[0]).startswith("0x") and len(B.hash_hex(h[0])) == 18


def test_io_hash_pinned():
    d = B.io_contract_dict()
    assert d["obs_names"] == list(B.OBS_NAMES) and d["actions"] == list(B.ACTION_NAMES)
    assert d["net"] == {"obs_dim": 115, "hidden": [64, 64], "activation": "tanh", "n_actions": 19, "head": "logits"}
    assert d["obs_names"][23:31] == [f"food_dir_{j}" for j in range(8)] and "food_dir" in d["obs_spec"]
    assert d["decision_steps"] == 2 and d["mask"] is None and "species" not in d
    assert B.io_hash() == B.io_hash()
    assert B.io_hash() == IO_HASH_PINNED, f"입출력 계약이 바뀌었다: {B.hash_hex(B.io_hash())}"


# --------------------------------------------------------------------------- 6


def test_config_inherit_and_checks(cfg, jcfg):
    assert cfg["world"]["mode"] == "train" and cfg["world"]["size"] == 60.0 and cfg["world"]["quadrants"] == 1
    assert jcfg["world"]["mode"] == "judge" and jcfg["world"]["size"] == 120.0 and jcfg["world"]["quadrants"] == 4
    assert jcfg["world"]["slots"] == {"deer": 400, "wolf": 24, "boar": 56}
    assert jcfg["food"]["quadrant_grass_total"] == 70.0 and cfg["food"]["quadrant_grass_total"] is None
    assert cfg["food"]["train_grass_total"] == 70.0 and jcfg["food"]["train_grass_total"] is None      # S′ N (학습 세계만)
    assert jcfg["train"] == cfg["train"] and jcfg["species"] == cfg["species"]
    # 대비책 F 는 스위치만 있고 기본 끔 (6-1, 사용자 답 11-10)
    assert cfg["reward"]["fallback_f"]["enabled"] is False
    assert cfg["train"]["ppo"]["gamma"] == 0.997 and cfg["train"]["ppo"]["gamma_candidates"] == [0.997, 0.99]
    # 학습 풀은 학습 코드 기본값으로만 (10절)
    assert cfg["train"]["seeds"] == [43000, 44000]
    l0 = B.override(jcfg, jcfg["judge"]["variants"]["L0"])
    assert l0["judge"]["limits"]["enabled"] is False and l0["world"]["slots"]["deer"] == 800
    l1 = B.override(jcfg, jcfg["judge"]["variants"]["L1"])
    assert l1["world"]["size"] == 60.0 and l1["world"]["quadrants"] == 1
    with pytest.raises(ValueError):
        B.override(cfg, {"world": {"decision_steps": 1}})
    with pytest.raises(ValueError):
        B.override(cfg, {"counts": {"wolf": [1, 7]}})                 # 칸 상한 6 을 넘음
    with pytest.raises(ValueError):
        B.override(cfg, {"species": {"deer": {"diet": ["bark"]}}})
    with pytest.raises(ValueError):
        B.override(cfg, {"world": {"mode": "judge"}})                 # 판정 블록 없음
    with pytest.raises(ValueError, match="here_r"):
        B.override(cfg, {"body_common": {"carcass": {"eat_r": 1.2}}})   # S′ 검토 low: 관측 '발밑' 경계 = EAT 가 사체를 먹는 거리


def test_fov_cos_literals_for_cpp(cfg, jcfg):
    """S′ 검토 low (C++ 옮김): 시야 cos 는 float64 리터럴 표 — 비트까지 고정 (늑대 250° · 사슴·멧돼지 300°), 표 = math.radians 꼴."""
    want = {"deer": "-0x1.bb67ae8584cabp-1", "wolf": "-0x1.25abcf87c4979p-1", "boar": "-0x1.bb67ae8584cabp-1"}
    for c in (cfg, jcfg):
        body = B.load_body(c)
        for i, sp in enumerate(B.SPECIES):
            assert float(body.fov_cos[i]).hex() == want[sp]
    for f, v in B.FOV_COS_LITERAL.items():
        assert v == math.cos(math.radians(f / 2.0))
