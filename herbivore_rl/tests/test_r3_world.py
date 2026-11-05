"""v3 R3 세계 — 추격 고정 realism_chase(24), 늑대 은신처 진입 금지 realism_shelter.block_predators, 은신처 먹이 배수 뽑기
realism_cover_food.frac_range, 지형 구역 realism_terrain(25), 얼기를 뺀 허용 목록 (10-14 사람 결정, 명세 Docs/RL_Policy/RL_V3_R3_SPEC.md
14절. 정의·식·현실 근거는 env_v2/world.py 모듈 docstring 'R3 세계').

비트 동일: 이 단계 직전 커밋(8292856 을 git archive 로 푼 사본)의 코드와 기존 설정(v3_r1_on·v3_r1·v3_r2_on·v3_real1_* 다섯)의 궤적·통계·
v1 난수 상태·기능 스트림·config digest 가 같다(출시 두뇌 R1b·R2 모델 롤아웃 포함). 새 블록·선택 키를 끈 설정 = 끄기 전 세계, 폭 0 먹이
배수 범위 = 1단계 고정 값, 넓이 0 지형 = 지형 없음, 배수 1 지형 = 지형 없음(배치 난수는 자기 스트림만 쓴다).
규칙 단위 시험: 고정한 표적은 보이는 동안 더 가까운 개체가 나타나도 바뀌지 않는다(얼어도 그대로), 은신처에 들어가면·시야 밖이 lost_steps
를 넘으면·잡으면·죽으면·쥘 수 없는 상태가 되면 놓는다, 잠행형은 돌진부터·플레이어는 돌진에서 고정한다. 늑대는 어떤 스텝 뒤에도 은신처
원 안에 없고(reset 포함), 원 둘레를 따라 미끄러질 때 둘레 방향 성분이 남는다, 사슴은 드나든다. 지형 배수는 이동 전 셀의 값이고 밤잠 배수
다음에 곱하며 정확하다, 넓이 0 인 세계가 정확히 0 이다, 지형은 은신처와 독립이다. 얼기는 마스크·판정 롤아웃·학습 경로 어디서도 실행되지
않는다(R1b 를 얹어도), f_dec 측정·eval_v3 r1b 판정 경로가 얼기 없는 목록에서 돈다. 시드는 보정 20000~20019·탐색 32000~32099 만 쓴다.
(j) 늑대 먹는 시간(10-15 사람 결정, threats.eat_in_place 선택 키 + v1 pred_eat_cd): R3 설정은 38스텝(5초의 반올림)이고, 잡은 뒤 37스텝 동안
늑대는 그 자리에 서서 사냥하지 않고 38스텝째에 다시 잡는다(플레이어형 위협은 그대로). 끔 값이나 pred_eat_cd ≤ 1 이면 끈 세계와 비트 동일이고,
먹는 시간을 끔 값으로 되돌린 R3 세계는 (j) 직전 커밋 f6e8b6e 의 코드와 비트 동일이다. C++ 골든 도구는 제자리 먹기 세계를 거부한다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import io
import json
import math
import pickle
import subprocess
import sys
import tarfile

import numpy as np
import pytest
import yaml

import repertoire_rules as rr
from env.config import ROOT
from env_v2 import features as F
from env_v2 import rep_policy as rp
from env_v2 import repertoire as rep
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.world import (PM_CHARGE, PM_REST, PM_STALK, PM_WANDER, PT_CHASER, PT_PLAYER, PT_STALKER, R3_STAT_COLUMNS,
                          ST_POUNCE, ST_ROAM, TERRAIN_NAMES, WALL_EPS, World)

CFG = ROOT / "configs"
R1 = CFG / "v3_r1.yaml"
R1_ON = CFG / "v3_r1_on.yaml"
R2_ON = CFG / "v3_r2_on.yaml"
R3 = CFG / "v3_r3.yaml"
R3_ON = CFG / "v3_r3_on.yaml"
REAL = {"all": CFG / "v3_real1_on.yaml", "vision": CFG / "v3_real1_vision_on.yaml",
        "hearing": CFG / "v3_real1_hearing_on.yaml", "shelter": CFG / "v3_real1_shelter_on.yaml",
        "night": CFG / "v3_real1_night_on.yaml"}
REALISM5 = ("realism_vision", "realism_hearing", "realism_shelter", "realism_night", "realism_cover_food")
NEW = ("realism_chase", "realism_terrain")
BASE_COMMIT = "8292856"              # R3 세계 직전 커밋(R3 설계서 초안) — 비트 동일 기준
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
R2_MODEL = ROOT / "ckpt" / "v3" / "v3_r2_g995_s3_20m.zip"
G, FL, H, Z, S = rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP
KEYS = ("pos", "head", "energy", "pred_pos", "pred_head", "food", "food_cap", "regen_field", "vel", "pred_cd", "pred_vel",
        "behavior", "beh_phase", "beh_steps", "beh_seq", "stalk_state", "player_mode", "pred_asleep")
STATS = ("stats", "gait_stats", "daynight_stats", "pred_sleep_stats", "repertoire_stats", "threats_stats", "alarm_stats",
         "realism_stats")

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _raw(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _r3_blocks():
    """v3_r3_on.yaml 의 realism 블록(켬) — 다섯 규칙 + 추격 고정 + 지형."""
    return {n: dict(v) for n, v in _raw(R3_ON)["features"].items() if n.startswith("realism_")}


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _cfg(*names, base=R1_ON, **over):
    """base 설정 + R3 블록(names, v3_r3_on 의 값). over = {기능: {키: 값}} 으로 덮는다."""
    b = _r3_blocks()
    cfg = _with(load_v2_config(base), **{n: b[n] for n in names})
    return _with(cfg, **over) if over else cfg


def _same(d1, d2):
    assert d1.keys() == d2.keys()
    for k in d1:
        a, b = d1[k], d2[k]
        assert a == b or (isinstance(a, float) and math.isnan(a) and math.isnan(b)), k


def _masked_rand(w, seed, freeze_bias=False):
    """세계 설정의 허용 목록 마스크 안에서 고르게 뽑는 정책(학습·측정 경로와 같은 마스크). freeze_bias 면 FREEZE 칸에 큰 확률을 준다
    (막힌 칸이 정말 0 인지 보려고)."""
    params = rp.rep_params(w.cfg)
    rng = np.random.default_rng([seed, 7])
    probs = np.array([1.0, 1.0, 1.0, 50.0 if freeze_bias else 1.0, 1.0])

    def pol(obs):
        m = rp.action_mask(w, obs, params)
        pol.last_mask = m
        return rp.sample_masked(np.broadcast_to(probs, m.shape), m, rng.random(len(obs))).astype(np.float64)[:, None]
    return pol


def _run_pair(wa, wb, pa, pb, steps=300, stats=STATS):
    for _ in range(steps):
        oa, ob = wa.observe(), wb.observe()
        np.testing.assert_array_equal(oa, ob)
        for x, y in zip(wa.step(pa(oa)), wb.step(pb(ob))):
            np.testing.assert_array_equal(x, y)
    for name in stats:
        try:
            sa = getattr(wa, name)()
        except (ValueError, AttributeError):
            continue
        _same(sa, getattr(wb, name)())
    for k in KEYS:
        if hasattr(wb, k):
            np.testing.assert_array_equal(getattr(wa, k), getattr(wb, k), err_msg=k)
    assert wa.rng.bit_generator.state == wb.rng.bit_generator.state


def _rand(seed):
    rng = np.random.default_rng(seed)
    return lambda obs: rng.integers(0, 5, (len(obs), 1)).astype(np.float64)


# --------------------------------------------------------------------- #
# 등록부·설정
# --------------------------------------------------------------------- #


def test_registry_and_keys():
    assert F.FEATURE_IDS["realism_chase"] == 24 and F.FEATURE_IDS["realism_terrain"] == 25
    assert set(NEW) <= F.IMPLEMENTED
    b = _r3_blocks()
    for n in NEW:
        assert F.PARAM_KEYS[n] == frozenset(b[n]) - {"enabled"}, n
    # 선택 키(규칙 6): 1단계 설정에는 없고(끔 값으로 읽는다) R3 설정에는 적는다
    assert dict(F.OPTIONAL_KEYS["realism_shelter"]) == {"block_predators": False, "wolf_margin": 0.0}   # 늑대 몸 여유 10-17
    assert dict(F.OPTIONAL_KEYS["realism_cover_food"]) == {"frac_range": None}
    assert dict(F.OPTIONAL_KEYS["threats"]) == {"eat_in_place": False}           # (j) 늑대 먹는 시간, 10-15
    full = _raw(R3_ON)["features"]
    for n, opt in F.OPTIONAL_KEYS.items():
        if n.startswith("wild_") or n in ("obstacles", "integrated_stage", "repertoire"):
            continue                    # 야생 1단계 선택 키(10-16)·야생 2단계 3 obstacles.fixed(10-17)·R4 학습 보충 integrated_stage.respawn_safe_r(10-18)·
                                        # 10-27 먹기 걷기 고침 repertoire.graze_* 는 R3 설정에 없다 — tests/test_wild1.py·test_wild2_obstacle.py·test_r4_train.py·
                                        # test_calm_v3.py 가 본다
        opt = {k: v for k, v in opt.items() if (n, k) != ("realism_shelter", "wolf_margin")}   # 10-17 늑대 몸 여유도 R3 설정에 없다(test_wild1)
        assert set(opt) <= set(full[n]) and not set(opt) & F.PARAM_KEYS[n]
        for old in (REAL["all"], R1_ON, R1):                                     # 지난 설정 파일에는 선택 키가 없다(끔 값으로 읽는다)
            assert not set(opt) & set(_raw(old)["features"].get(n, {}))
    assert F.with_optional("realism_shelter", {"untargetable": True}) == {"block_predators": False, "wolf_margin": 0.0,
                                                                           "untargetable": True}
    with pytest.raises(ValueError, match="선택 키"):
        F.parse_features({"realism_shelter": dict(b["realism_shelter"], block_predator=True)})


def test_r3_configs_are_r1_plus_blocks():
    """v3_r3 = v3_r1 + 현실성 블록 다섯 + 추격 고정·지형 + 장애물 자리 블록 + version + 허용 목록(얼기 뺌)·f_dec·ent_coef_base + 늑대 먹는
    시간(overrides.pred_eat_cd 38, threats.eat_in_place true — 10-15). 판정 세계 v3_r3_on 은 v3_r3 에서 낮 고정 세계 비율만 0 이다. 블록 값은
    1단계와 같고 청각 자르기·먹이 배수만 다르다. 관측 18·마스크 판 2."""
    a, b, on = _raw(R3), _raw(R1), _raw(R3_ON)
    assert a["version"] == on["version"] == "3.r3"
    assert {k: v for k, v in a.items() if k not in ("version", "features", "train", "overrides")} == \
        {k: v for k, v in b.items() if k not in ("version", "features", "train", "overrides")}
    assert a["overrides"] == dict(b["overrides"], pred_eat_cd=38)                  # 10-15: 늑대 먹는 시간만 더했다
    extra = set(REALISM5) | set(NEW) | {"obstacles"}
    assert set(a["features"]) - set(b["features"]) == extra
    assert a["features"]["threats"] == dict(b["features"]["threats"], eat_in_place=True)
    assert {k: v for k, v in a["features"].items() if k not in extra | {"threats"}} == \
        {k: v for k, v in b["features"].items() if k != "threats"}
    assert a["features"]["obstacles"] == {"enabled": False}
    ta, tb = a["train"], b["train"]
    assert {k: v for k, v in ta.items() if k != "repertoire"} == {k: v for k, v in tb.items() if k != "repertoire"}
    ra, rb = ta["repertoire"], tb["repertoire"]
    assert ra["allowed"] == ["graze", "flee", "hide"] and rb["allowed"] == ["graze", "flee", "hide", "freeze"]
    assert {k: v for k, v in ra.items() if k not in ("allowed", "f_dec", "ent_coef_base")} == \
        {k: v for k, v in rb.items() if k not in ("allowed", "f_dec", "ent_coef_base")}
    assert math.isclose(ra["ent_coef_base"] / ra["f_dec"], 0.01, rel_tol=1e-12)
    # 1단계 값에서 바뀐 것은 둘(명세 3-2) + 진입 금지 선택 키
    real = _raw(REAL["all"])["features"]
    for n in REALISM5:
        diff = {k for k in set(a["features"][n]) | set(real[n]) if a["features"][n].get(k) != real[n].get(k)}
        want = {"realism_hearing": {"cap_to_sight"}, "realism_shelter": {"block_predators"},
                "realism_cover_food": {"cap_frac", "regen_frac", "frac_range"}}.get(n, set())
        assert diff == want, (n, diff)
    assert a["features"]["realism_hearing"]["cap_to_sight"] is False
    assert a["features"]["realism_shelter"]["block_predators"] is True
    assert a["features"]["realism_cover_food"]["frac_range"] == [0.1, 0.3]
    assert a["features"]["realism_night"]["hunt_dark"] == 1.0                      # H2: 둔다
    assert a["features"]["realism_vision"]["kin_fov_deg"] == 120.0                 # H4
    assert a["features"]["realism_chase"] == dict(enabled=True, lost_steps=0, stalk_phase=False, player_too=False)   # 명세 4-10
    assert a["features"]["realism_terrain"] == dict(
        enabled=True, snow_frac=[0.0, 0.25], rough_frac=[0.0, 0.15], zero_p=[0.25, 0.25], patch_r=[3.0, 10.0], max_patches=64,
        mult_herb=[1.0, 0.6, 0.8], mult_pred=[1.0, 0.85, 0.9], mult_player=[1.0, 0.85, 0.9])     # H18 명세 기본값
    # 판정 세계 = 학습 세계 − 낮 고정
    assert {k: v for k, v in on.items() if k != "features"} == {k: v for k, v in a.items() if k != "features"}
    fa = {k: dict(v) for k, v in a["features"].items()}
    fa["daynight"]["fixed_day_frac"] = 0.0
    assert on["features"] == fa
    for path in (R3, R3_ON):
        text = path.read_text(encoding="utf-8")
        assert chr(0xA7) not in text and "현실 근거" in text
        w, w1 = World(load_v2_config(path), seeds=[32000]), World(load_v2_config(R1_ON), seeds=[32000])
        assert w.obs_names == w1.obs_names and w.obs_dim == 18 and rp.mask_version_of(w.obs_names) == 2
        assert set(w.features.active) - set(w1.features.active) == set(REALISM5) | set(NEW)
        assert w._r3 and w._zw and w._zf_range and w._zc is not None and w._zt is not None
        assert w._eat_in_place and w.cfg.pred_eat_cd == 38 and not w1._eat_in_place and w1.cfg.pred_eat_cd == 5
        assert rp.rep_params(load_v2_config(path))["allowed"] == ("graze", "flee", "hide")


@pytest.mark.parametrize("name, kw, match", [
    ("realism_chase", dict(lost_steps=-1), "lost_steps"),
    ("realism_chase", dict(lost_steps=1.5), "lost_steps"),
    ("realism_chase", dict(stalk_phase=1), "stalk_phase"),
    ("realism_chase", dict(player_too=None), "player_too"),
    ("realism_terrain", dict(snow_frac=[0.3, 0.1]), "snow_frac"),
    ("realism_terrain", dict(rough_frac=[0.0, 1.2]), "rough_frac"),
    ("realism_terrain", dict(zero_p=[0.25]), "zero_p"),
    ("realism_terrain", dict(zero_p=[0.25, 1.5]), "zero_p"),
    ("realism_terrain", dict(patch_r=[0.0, 3.0]), "patch_r"),
    ("realism_terrain", dict(max_patches=-1), "max_patches"),
    ("realism_terrain", dict(mult_herb=[0.9, 0.6, 0.8]), "mult_herb"),            # 보통은 1
    ("realism_terrain", dict(mult_pred=[1.0, 1.2, 0.9]), "mult_pred"),            # 빠르게 하지 않는다
    ("realism_terrain", dict(mult_player=[1.0, 0.85]), "mult_player"),
    ("realism_shelter", dict(block_predators=1), "block_predators"),
    ("realism_cover_food", dict(frac_range=[0.3, 0.1]), "frac_range"),
    ("realism_cover_food", dict(frac_range=[0.1, 0.3], cap_frac=0.15), "null"),   # 둘 다 적으면 헷갈린다
    ("realism_cover_food", dict(frac_range=0.2), "frac_range"),
])
def test_params_are_checked(name, kw, match):
    with pytest.raises(ValueError, match=match):
        World(_cfg(name, **{name: kw}), seeds=[32000])


def test_prerequisites():
    with pytest.raises(ValueError, match="repertoire"):
        World(_cfg("realism_chase", repertoire=dict(enabled=False), threats=dict(enabled=False)), seeds=[32001])
    with pytest.raises(ValueError, match="repertoire"):
        World(_cfg("realism_terrain", repertoire=dict(enabled=False), threats=dict(enabled=False)), seeds=[32001])
    with pytest.raises(ValueError, match="stare_down"):
        World(_cfg("realism_chase", base=CFG / "v3_r2_w7_on.yaml"), seeds=[32001])
    b = _r3_blocks()["realism_terrain"]
    with pytest.raises(ValueError, match="계수"):
        F.parse_features({"realism_terrain": {k: v for k, v in b.items() if k != "mult_player"}})


# --------------------------------------------------------------------- #
# 비트 동일
# --------------------------------------------------------------------- #

TRACE_SRC = r'''
import hashlib, json, sys
sys.path.insert(0, ".")
import env.torch_init
import numpy as np
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.world import World
KEYS = %(keys)r
STATS = %(stats)r


def digest(cfg):
    return hashlib.sha1(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]


def run(job):
    cfg = load_v2_config(job["config"])
    if job.get("v1"):
        cfg = cfg.replace(**job["v1"])
    if job.get("set"):
        f = {k: dict(v) for k, v in cfg.v2["features"].items()}
        for n, kw in job["set"].items():
            f[n] = dict(f.get(n, {}), **kw)
        cfg = cfg.replace(v2=dict(cfg.v2, features=f))
    w = World(cfg, seeds=[job["seed"]])
    kind = job["policy"]
    if kind == "rand":
        rng = np.random.default_rng(job["seed"] + 7)
        pol = lambda o: rng.integers(0, 5, (len(o), 1)).astype(np.float64)
    elif kind == "rbase":
        import repertoire_rules as rr
        pol = ro.build_policy(rr.rule_spec(cfg, 4.0, 0.9), job["seed"])
    else:
        pol = ro.build_policy({"kind": "rep_learned", "path": job["model"]}, job["seed"])
    ro.forward_bind(pol, w)
    hs = []
    for _ in range(job["steps"]):
        obs = w.observe()
        a = np.asarray(pol(obs), dtype=np.float64)
        res = w.step(a)
        h = hashlib.sha1()
        for x in (obs, a) + tuple(res):
            h.update(np.ascontiguousarray(x).tobytes())
        for k in KEYS:
            if hasattr(w, k):
                h.update(np.ascontiguousarray(getattr(w, k)).tobytes())
        hs.append(h.hexdigest()[:16])
    st = {}
    for n in STATS:
        try:
            st[n] = {k: (None if v != v else v) for k, v in getattr(w, n)().items()}
        except (ValueError, AttributeError):
            pass
    return dict(hashes=hs, stats=st, rng=str(w.rng.bit_generator.state), obs_names=list(w.obs_names),
                streams=sorted(map(str, w._feature_rngs)), digest=digest(cfg))


jobs = json.loads(open(sys.argv[1], encoding="utf-8").read())
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps([run(j) for j in jobs]))
'''


def _archive(tmp_path, commit=BASE_COMMIT):
    """커밋 commit(기본: R3 세계 직전 코드 BASE_COMMIT)의 herbivore_rl 일부를 tmp 에 푼다. git 이나 커밋이 없으면 None.
    10-22: 사본의 동족 무리 중심·분리 두 줄만 지금 코드와 같은 j 차례 합으로 바꾼다 (tests/kin_seq.py)."""
    import kin_seq

    paths = [f"herbivore_rl/{p}" for p in ("env", "env_v2", "policies", "configs", "repertoire_rules.py")]
    try:
        out = subprocess.run(["git", "archive", commit] + paths, cwd=ROOT.parent, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    with tarfile.open(fileobj=io.BytesIO(out.stdout)) as tf:
        tf.extractall(tmp_path / "base", **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return kin_seq.patch_tree(tmp_path / "base" / "herbivore_rl")


# 새 블록·선택 키를 모두 끈 값(1단계 세계에 더해도 그 세계 그대로여야 한다)
OFF_SET = {"realism_chase": dict(_r3_blocks()["realism_chase"], enabled=False),
           "realism_terrain": dict(_r3_blocks()["realism_terrain"], enabled=False),
           "realism_shelter": {"block_predators": False}, "realism_cover_food": {"frac_range": None}}


def test_bit_identical_to_pre_r3_code(tmp_path):
    """기존 세계(v3_r1_on·v3_r1·v3_r2_on·v3_real1_* 다섯)는 R3 직전 코드와 궤적(스텝마다 관측·행동·보상·사망·terminal_obs·상태 지문)·
    통계(realism_stats 포함)·v1 난수 상태·관측 이름·기능 스트림·config digest 가 같다. 1단계 세계에 새 블록·선택 키를 끈 값으로 더한 설정도
    직전 코드의 그 세계와 같다. 출시 두뇌 R1b(1단계 세계·R1 세계)와 R2 모델의 롤아웃도 같다 — 판정 롤아웃의 허용 목록이 '모델 ∩ 세계'가
    되어도 두 목록이 같은 세계에서는 그대로다."""
    old_root = _archive(tmp_path)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(TRACE_SRC % dict(keys=KEYS, stats=STATS), encoding="utf-8")
    old, new = [], []
    plain = [("configs/v3_r1_on.yaml", 32050, "rand"), ("configs/v3_r1.yaml", 32051, "rbase"),
             ("configs/v3_r2_on.yaml", 32052, "rand"), ("configs/v3_real1_on.yaml", 32053, "rand"),
             ("configs/v3_real1_on.yaml", 32054, "rbase"), ("configs/v3_real1_vision_on.yaml", 32055, "rand"),
             ("configs/v3_real1_hearing_on.yaml", 32056, "rbase"), ("configs/v3_real1_shelter_on.yaml", 32057, "rand"),
             ("configs/v3_real1_night_on.yaml", 32058, "rbase")]
    for cfg, seed, pol in plain:
        j = dict(config=cfg, seed=seed, steps=250, policy=pol)
        old.append(j)
        new.append(j)
    for cfg, seed, pol in (("configs/v3_real1_on.yaml", 32059, "rand"), ("configs/v3_real1_shelter_on.yaml", 32060, "rbase")):
        old.append(dict(config=cfg, seed=seed, steps=250, policy=pol))
        new.append(dict(config=cfg, seed=seed, steps=250, policy=pol, set=OFF_SET))
    if R1_MODEL.exists():
        for cfg, seed in (("configs/v3_real1_on.yaml", 32061), ("configs/v3_r1_on.yaml", 32062)):
            j = dict(config=cfg, seed=seed, steps=200, policy="model", model=str(R1_MODEL))
            old.append(j)
            new.append(j)
    if R2_MODEL.exists():
        j = dict(config="configs/v3_r2_on.yaml", seed=32063, steps=200, policy="model", model=str(R2_MODEL))
        old.append(j)
        new.append(j)
    procs = []
    for root, jobs, tag in ((old_root, old, "old"), (ROOT, new, "new")):
        jp, op = tmp_path / f"jobs_{tag}.json", tmp_path / f"out_{tag}.json"
        jp.write_text(json.dumps(jobs), encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, str(script), str(jp), str(op)], cwd=root), op))
    outs = []
    for p, op in procs:
        assert p.wait(timeout=900) == 0
        outs.append(json.loads(op.read_text(encoding="utf-8")))
    for j, a, b in zip(new, *outs):
        first = next((i for i, (x, y) in enumerate(zip(a["hashes"], b["hashes"])) if x != y), None)
        assert first is None and len(a["hashes"]) == len(b["hashes"]), (j, first)
        for k in ("stats", "rng", "obs_names", "streams"):
            assert a[k] == b[k], (j, k)
        if not j.get("set"):
            assert a["digest"] == b["digest"], j                   # 기존 yaml 의 config digest 는 그대로다


@pytest.mark.parametrize("kind", ["all", "shelter"])
def test_new_blocks_off_equal_stage1(kind):
    """같은 프로세스: 1단계 세계에 추격 고정·지형 블록을 끈 채, 선택 키를 끔 값으로 적어 더해도 그 세계와 비트 동일이다(R3 통계 없음)."""
    a, b = load_v2_config(REAL[kind]), _with(load_v2_config(REAL[kind]), **OFF_SET)
    wa, wb = World(a, seeds=[32064]), World(b, seeds=[32064])
    assert not wa._r3 and not wb._r3 and wb._zs["block_predators"] is False
    _run_pair(wa, wb, _rand(11), _rand(11), 300)
    assert {n for n, _ in wb._feature_rngs} == {n for n, _ in wa._feature_rngs}


def test_cover_food_zero_width_range_equals_fixed():
    """먹이 배수 범위의 폭이 0 이면 f = 하 = 1단계 고정 값이다 — 자기 스트림을 하나 만들 뿐 궤적·상태·v1 난수가 같다."""
    a = load_v2_config(REAL["all"])
    b = _with(a, realism_cover_food=dict(cap_frac=None, regen_frac=None, frac_range=[0.15, 0.15]))
    wa, wb = World(a, seeds=[32065]), World(b, seeds=[32065])
    assert wb._r3 and wb.cover_food_cap == wb.cover_food_regen == 0.15
    _run_pair(wa, wb, _rand(12), _rand(12), 250)
    assert ("realism_cover_food", 0) in wb._feature_rngs and ("realism_cover_food", 0) not in wa._feature_rngs


@pytest.mark.parametrize("seed", [20000, 20003, 32066])
def test_cover_food_range_draw(seed):
    """frac_range 면 세계마다 f = 하 + (상 − 하)·u, u = 자기 스트림 part 0 의 첫 난수. 은신처 셀 용량·재생이 같은 f 를 쓴다."""
    w, w0 = World(load_v2_config(R3_ON), seeds=[seed]), World(load_v2_config(R1_ON), seeds=[seed])
    u = F.feature_stream(seed, "realism_cover_food", 0).random()
    f = 0.1 + (0.3 - 0.1) * u
    assert w.cover_food_cap == w.cover_food_regen == f and 0.1 <= f <= 0.3
    cell = w.cover_food_cell
    np.testing.assert_allclose(w.food_cap[cell], f * w0.food_cap[cell], rtol=0, atol=1e-15)
    np.testing.assert_array_equal(w.food_cap[~cell], w0.food_cap[~cell])
    assert w.r3_stats()["cover_food_cap"] == f


@pytest.mark.parametrize("variant", ["zero_p", "zero_range"])
def test_terrain_zero_coverage_equals_no_terrain(variant):
    """넓이 0 지형(눈·거친 땅이 둘 다 없음)은 지형이 없는 같은 R3 세계와 비트 동일이다 — 배수 1 을 곱할 뿐이고 자기 스트림만 쓴다."""
    kw = dict(zero_p=[1.0, 1.0]) if variant == "zero_p" else dict(snow_frac=[0.0, 0.0], rough_frac=[0.0, 0.0])
    on = _with(load_v2_config(R3_ON), realism_terrain=kw)
    off = _with(load_v2_config(R3_ON), realism_terrain=dict(enabled=False))
    wa, wb = World(on, seeds=[32067]), World(off, seeds=[32067])
    assert wa._zt is not None and wb._zt is None
    assert (wa.terrain_cell == 0).all() and wa.snow_frac_actual == 0.0 and wa.rough_frac_actual == 0.0
    assert len(wa.terrain_patches) == 0
    _run_pair(wa, wb, _masked_rand(wa, 1), _masked_rand(wb, 1), 300)
    sa, sb = wa.r3_stats(), wb.r3_stats()
    for k in R3_STAT_COLUMNS:
        if not (k.startswith(("deer_n_", "catch_", "pounce_", "snow_", "rough_"))):
            assert sa[k] == sb[k] or (math.isnan(sa[k]) and math.isnan(sb[k])), k
    assert sa["deer_n_normal"] == 300 * wa.N and sa["deer_n_snow"] == sa["deer_n_rough"] == 0
    assert math.isnan(sb["deer_n_normal"])


def test_terrain_unit_multipliers_equal_no_terrain():
    """넓이가 0 보다 커도 배수가 모두 1 이면 지형이 없는 세계와 비트 동일이다 — 배치 난수가 다른 스트림을 건드리지 않는다."""
    ones = [1.0, 1.0, 1.0]
    on = _with(load_v2_config(R3_ON), realism_terrain=dict(zero_p=[0.0, 0.0], snow_frac=[0.2, 0.25], rough_frac=[0.1, 0.15],
                                                            mult_herb=ones, mult_pred=ones, mult_player=ones))
    off = _with(load_v2_config(R3_ON), realism_terrain=dict(enabled=False))
    wa, wb = World(on, seeds=[32068]), World(off, seeds=[32068])
    assert wa.snow_frac_actual >= 0.2 and wa.rough_frac_actual >= 0.1
    _run_pair(wa, wb, _masked_rand(wa, 2), _masked_rand(wb, 2), 300)


def test_r3_streams_and_copy():
    """R3 세계가 만드는 기능 스트림은 daynight·pred_sleep·threats 와 자기 스트림(먹이 배수 part 0, 지형 part 0·1·2)뿐이다. 추격 고정·
    진입 금지는 난수가 없다. 세계는 결정적이고 pickle·deepcopy 한 사본이 같은 궤적·R3 통계를 낸다."""
    cfg = _with(load_v2_config(R3_ON), threats=dict(player_frac=1.0))
    a, b = World(cfg, seeds=[32069]), World(cfg, seeds=[32069])
    pa, pb = _masked_rand(a, 3), _masked_rand(b, 3)
    for _ in range(200):
        for x, y in zip(a.step(pa(a.observe())), b.step(pb(b.observe()))):
            np.testing.assert_array_equal(x, y)
    names = {n for n, _ in a._feature_rngs}
    assert names <= {"daynight", "pred_sleep", "threats", "realism_cover_food", "realism_terrain"}
    assert {p for n, p in a._feature_rngs if n == "realism_terrain"} <= {0, 1, 2}
    clones = [pickle.loads(pickle.dumps(a)), copy.deepcopy(a)]
    rng = np.random.default_rng(13)
    for _ in range(150):
        act = rng.choice([G, FL, H], (a.N, 1)).astype(np.float64)
        ra = a.step(act)
        for c in clones:
            for x, y in zip(c.step(act), ra):
                np.testing.assert_array_equal(x, y)
    for c in clones:
        _same(c.r3_stats(), a.r3_stats())
        np.testing.assert_array_equal(c.chase_tgt, a.chase_tgt)


# --------------------------------------------------------------------- #
# 단위 시험 하네스 — 사슴 몇 마리와 위협 하나
# --------------------------------------------------------------------- #


def _arena(cfg, kind="chaser", threat=(-8.0, 0.0), deer=((0.0, 0.0),), behs=None, cover=(), seed=32070):
    """맵 가운데 c 를 원점으로 한 상대 위치에 사슴(deer, 슬롯 0, 1, …)과 위협 하나(threat)를 놓는다. 위협은 사슴 0 을 본다. 나머지 사슴은
    구석 (1, 1)(위협 시야 밖). cover = [(dx, dy, r)] 은신처 원(없으면 은신처 없음). 낮 고정, 지형은 모두 보통. 위협 속력 0.5·포획 거리 1."""
    w = World(cfg, seeds=[seed])
    w.day_fixed = True
    w._daynight_update()
    c = np.array([w.size / 2, w.size / 2])
    if cover:
        w.cov_c = np.array([c + [dx, dy] for dx, dy, _ in cover])
        w.cov_r = np.array([r for _, _, r in cover], dtype=np.float64)
    else:
        w.cov_c, w.cov_r = np.zeros((0, 2)), np.zeros(0)
    if w._zt is not None:
        w.terrain_cell[:] = 0
    w.food[:] = 1.0
    w.food_cap[:] = 1.0
    w.pos[:] = [1.0, 1.0]
    for i, d in enumerate(deer):
        w.pos[i] = c + d
    w.head[:] = [1.0, 0.0]
    q = c + threat
    player = kind == "player"
    w.M, w.M_base = 1, 0 if player else 1
    w.pred_pos = np.array([q])
    v = w.pos[0] - q
    w.pred_head = np.array([v / max(np.linalg.norm(v), 1e-9)])
    w.pred_ranged = np.zeros(1, dtype=bool)
    w._pred_ranged_v1 = np.zeros(1, dtype=bool)
    w.pred_speed = np.full(1, 0.5)
    w.pred_catch_r = np.full(1, 1.0)
    w.pred_cd = np.zeros(1, dtype=np.int32)
    w.pred_type = np.array([PT_PLAYER if player else (PT_STALKER if kind == "stalker" else PT_CHASER)], dtype=np.int8)
    w.pred_is_player = w.pred_type == PT_PLAYER
    w.player_present = player
    w.stalk_state = np.zeros(1, dtype=np.int8)
    w.stalk_left = np.zeros(1, dtype=np.int64)
    w.player_mode = np.full(1, PM_STALK, dtype=np.int8)
    w.player_left = np.full(1, 10 ** 6, dtype=np.int64)
    w.pred_nocturnal = np.ones(1, dtype=bool)
    w.pred_asleep = np.zeros(1, dtype=bool)
    w._pred_speed_mult = np.ones(1)
    w.pred_vel = np.zeros((1, 2))
    if w._zh is not None:
        w.pred_running = np.zeros(1, dtype=bool)
    if w._zn is not None:
        w._rz_night_reset()
        w._zn_fresh = False
    if w._zc is not None:
        w._rz_chase_reset()
    if w._zw:
        w._zw_sel = np.array([not player or w._zs["player_too"]])
    rs, rp_ = w._rs, w._rp
    rs.behavior[:] = G
    for i, b in enumerate(behs or ()):
        rs.behavior[i] = b
    rs.arrived[:] = False
    rs.lock_left[:] = 0
    rs.jitter[:] = 0
    w._rep_see[:] = rp_["graze_head_down"]
    w._rep_see_last[:] = w._rep_see
    w._rep_still[:] = (rs.behavior == Z) | (rs.behavior == S)
    w._rep_crouch[:] = False
    w._rep_cover = rep.cover_mult(rp_, rs.behavior, w._rep_crouch)
    w._reset_stats()
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)
    return w, c


def _chase_cfg(**kw):
    """v3_r1_on + 은신처 안전(진입 금지 끔) + 추격 고정(kw 로 덮음). 은신처 안전을 켜야 `pred_target` 훅이 생기고 untargetable 이 있다."""
    over = dict(realism_shelter=dict(block_predators=False))
    if kw:
        over["realism_chase"] = kw
    return _cfg("realism_shelter", "realism_chase", **over)


def _plain_cfg():
    """대조: 추격 고정이 없는 같은 세계."""
    return _cfg("realism_shelter", realism_shelter=dict(block_predators=False))


# --------------------------------------------------------------------- #
# (f) 추격 고정
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("locked", [True, False])
def test_locked_target_not_switched_while_visible(locked):
    """쫓기 시작한 늑대는 더 가까운 사슴이 시야에 들어와도 처음 표적을 쫓는다. 추격 고정이 없으면 더 가까운 쪽으로 넘어간다."""
    w, c = _arena(_chase_cfg() if locked else _plain_cfg(), deer=((0.0, 0.0), (4.0, 2.0)))
    w._step_predators_v3()
    assert w.pred_target[0] == 0
    if locked:
        assert w.chase_tgt[0] == 0 and w.r3_stats()["chase_lock_n"] == 1.0
    w.pos[1] = w.pred_pos[0] + [2.0, 0.5]                  # 사슴 1 이 바로 앞 2 로(사슴 0 은 7.5)
    for _ in range(3):
        w._step_predators_v3()
        assert w.pred_target[0] == (0 if locked else 1)
    if locked:
        st = w.r3_stats()
        assert st["chase_held_n"] == 3.0 and st["chase_lost_n"] == 0.0


@pytest.mark.parametrize("locked", [True, False])
def test_frozen_locked_target_stays(locked):
    """고정한 표적에는 c_still(얼면 체감 거리 × 1.8)을 쓰지 않는다: 실거리 9 의 표적이 얼어 체감 거리가 16 > 14 가 되어도 계속 쫓는다.
    고정이 없으면 표적을 놓친다(얼기의 '옆 개체로 넘기기' 이득 — R3 는 얼기를 빼서 쓰이지 않지만 규칙은 이렇다)."""
    w, c = _arena(_chase_cfg() if locked else _plain_cfg(), threat=(-9.5, 0.0))
    w._step_predators_v3()
    assert w.pred_target[0] == 0
    w._rs.behavior[0] = Z
    w._rep_still[0] = True
    w._step_predators_v3()
    assert w.pred_target[0] == (0 if locked else -1)


def test_release_when_target_enters_shelter():
    """표적이 은신처 원에 들어가면 놓고, 보이는 다른 사슴이 있으면 그 사슴을 새로 고정한다. 은신처 안 표적은 잡히지 않는다."""
    w, c = _arena(_chase_cfg(), deer=((0.0, 0.0), (3.0, 3.0)))
    w._step_predators_v3()
    assert w.chase_tgt[0] == 0
    w.cov_c, w.cov_r = np.array([w.pos[0]]), np.array([2.0])
    w._step_predators_v3()
    assert w.chase_tgt[0] == 1 and w.pred_target[0] == 1
    st = w.r3_stats()
    assert st["chase_rel_cover_n"] == 1.0 and st["chase_lock_n"] == 2.0


def test_release_after_lost_steps():
    """lost_steps > 0 (여기서는 8): 표적이 늑대 시야 밖이면 그 스텝 수 동안은 놓지 않고 마지막으로 본 자리로 가며, 그동안 더 가까운
    사슴이 보여도 고르지 않는다. 시야 밖이 lost_steps 를 넘는 스텝에 놓고 보이는 사슴을 새로 고정한다. (R3 설정 값은 0 — 아래 시험)"""
    L = 8
    cfg = _chase_cfg(lost_steps=L)
    w, c = _arena(cfg, deer=((0.0, 0.0), (-20.0, 20.0)))
    w._step_predators_v3()
    assert w.chase_tgt[0] == 0
    seen_at = w.pos[0].copy()
    # 표적이 늑대 등 뒤(시야각 밖)로 — 늑대는 앞쪽의 마지막 자리로 가므로 다시 보이지 않는다. (앞쪽 14 밖으로 두면 마지막 자리로 가는
    # 동안 다시 시야에 들어와 chase_lost 가 0 이 된다 — 그것도 규칙대로다)
    w.pos[0] = w.pred_pos[0] + [-6.0, 2.0]
    w.pos[1] = w.pred_pos[0] + [9.0, -3.0]                 # 더 가까운 사슴이 앞에 보인다(지나가며 잡을 거리 밖)
    for k in range(1, L + 1):
        old = w.pred_pos[0].copy()
        w._step_predators_v3()
        assert w.chase_tgt[0] == 0 and w.chase_lost[0] == k and w.pred_target[0] == 0
        d = seen_at - old
        np.testing.assert_allclose(w.pred_pos[0] - old, d / np.linalg.norm(d) * 0.5, rtol=0, atol=1e-12)
    w._step_predators_v3()
    assert w.chase_tgt[0] == 1 and w.pred_target[0] == 1
    st = w.r3_stats()
    assert st["chase_rel_lost_n"] == 1.0 and st["chase_lost_n"] == float(L)


def test_lost_zero_releases_at_once():
    """R3 설정(lost_steps 0): 표적이 시야를 벗어난 스텝에 바로 놓는다 — '보이는 동안 계속 쫓음'."""
    assert _chase_cfg().v2["features"]["realism_chase"]["lost_steps"] == 0
    w, c = _arena(_chase_cfg(), deer=((0.0, 0.0), (-20.0, 20.0)))
    w._step_predators_v3()
    w.pos[0] = w.pred_pos[0] + [16.0, 0.0]                 # 시야 반경(14) 밖
    w._step_predators_v3()
    assert w.chase_tgt[0] == -1 and w.pred_target[0] == -1


def test_release_on_catch_and_death():
    """잡으면 놓는다(고정한 표적을 잡았는지도 센다). 표적이 다른 이유로 죽어 리스폰하면 놓는다(리스폰한 슬롯은 새 개체다)."""
    w, c = _arena(_chase_cfg(), threat=(-0.8, 0.0))
    caught = w._step_predators_v3()                         # 같은 스텝에 고정하고(표적 고르기 뒤) 잡는다(포획 판정)
    st = w.r3_stats()
    assert caught[0] and w.pred_target[0] == 0 and w.chase_tgt[0] == -1
    assert st["chase_lock_n"] == 1.0 and st["chase_rel_catch_n"] == 1.0 and st["chase_catch_own_n"] == 1.0
    w, c = _arena(_chase_cfg())
    w._step_predators_v3()
    assert w.chase_tgt[0] == 0
    w._respawn(np.array([0]))
    assert w.chase_tgt[0] == -1 and w.r3_stats()["chase_rel_dead_n"] == 1.0


def test_release_when_not_hunting():
    """쥘 수 없는 상태(쿨다운)가 되면 놓는다."""
    w, c = _arena(_chase_cfg())
    w._step_predators_v3()
    assert w.chase_tgt[0] == 0
    w.pred_cd[0] = 3
    w._step_predators_v3()
    assert w.chase_tgt[0] == -1 and w.r3_stats()["chase_rel_state_n"] == 1.0


@pytest.mark.parametrize("locked", [True, False])
def test_stalker_pounce_lock(locked):
    """잠행형은 돌진을 시작하면 돌진 표적을 고정한다 — 더 가까운 사슴이 나타나도 그 표적 쪽으로 돌진한다. 고정이 없으면 넘어간다."""
    w, c = _arena(_chase_cfg() if locked else _plain_cfg(), kind="stalker", threat=(-5.0, 0.0), deer=((0.0, 0.0), (6.0, 6.0)))
    w._step_predators_v3()
    assert w.stalk_state[0] == ST_POUNCE and w.pred_target[0] == 0
    if locked:
        assert w.chase_tgt[0] == 0
    w.pos[1] = w.pred_pos[0] + [1.5, 0.5]
    w._step_predators_v3()
    assert w.pred_target[0] == (0 if locked else 1)


@pytest.mark.parametrize("stalk_phase", [False, True])
def test_stalker_stalk_phase(stalk_phase):
    """잠행 접근(배회 상태, 체감 거리 > 6) 중에는 stalk_phase 일 때만 고정한다. 아니면 다가가는 동안 더 가까운 기회로 넘어간다."""
    w, c = _arena(_chase_cfg(stalk_phase=stalk_phase), kind="stalker", threat=(-10.0, 0.0), deer=((0.0, 0.0), (8.0, 8.0)))
    w._step_predators_v3()
    assert w.stalk_state[0] == ST_ROAM and w.pred_target[0] == 0
    assert w.chase_tgt[0] == (0 if stalk_phase else -1)
    w.pos[1] = w.pred_pos[0] + [7.0, 1.0]                  # 더 가깝지만 돌진 거리(6) 밖
    w._step_predators_v3()
    assert w.pred_target[0] == (0 if stalk_phase else 1)


@pytest.mark.parametrize("player_too", [True, False])
def test_player_charge_lock(player_too):
    """player_too 면 플레이어형 위협이 돌진을 시작할 때 그 표적을 고정한다(맵 전체를 보므로 시야 밖으로 놓치지 않는다). R3 설정은 false —
    사람 대역은 지금처럼 가장 가까운 개체로 넘어간다."""
    w, c = _arena(_chase_cfg(player_too=player_too), kind="player", threat=(-5.0, 0.0), deer=((0.0, 0.0), (9.0, 9.0)))
    w._step_predators_v3()
    assert w.player_mode[0] == PM_CHARGE and w.pred_target[0] == 0
    assert w.chase_tgt[0] == (0 if player_too else -1)
    w.pos[1] = w.pred_pos[0] + [1.5, 0.5]
    w._step_predators_v3()
    assert w.pred_target[0] == (0 if player_too else 1)


class _ChaseSpy(World):
    """포식자 스텝마다 고정 규칙을 확인한다: (1) 고정이 있으면 이번 표적이 그 고정 표적이다, (2) 고정 표적이 바뀐 위협 수는 그 스텝에
    놓은 수(은신처·시야 밖·상태)를 넘지 않는다 — 놓지 않고는 바꾸지 않는다, (3) 고정 표적은 은신처 밖이다(이 판정 때 위치)."""

    def _step_predators_v3(self):
        before = self.chase_tgt.copy()
        rel0 = self._zc_rel_cover + self._zc_rel_lost + self._zc_rel_state
        inc = self._in_cover(self.pos)
        caught = super()._step_predators_v3()
        after = self.chase_tgt
        rel = self._zc_rel_cover + self._zc_rel_lost + self._zc_rel_state - rel0
        locked = after >= 0
        self.bad_target = getattr(self, "bad_target", 0) + int(np.count_nonzero(locked & (self.pred_target != after)))
        switched = int(np.count_nonzero((before >= 0) & locked & (after != before)))
        self.bad_switch = getattr(self, "bad_switch", 0) + max(switched - rel, 0)
        self.kept = getattr(self, "kept", 0) + int(np.count_nonzero((before >= 0) & (after == before)))
        self.lock_in_cover = getattr(self, "lock_in_cover", 0) + int(np.count_nonzero(locked & inc[np.maximum(after, 0)]))
        return caught


def test_chase_rule_in_runs():
    """R3 판정 세계 롤아웃(허용 목록 안의 무작위 요청, 탐색 시드): 고정을 쥔 위협은 놓기 전까지 표적을 바꾸지 않고, 고정 표적을 쫓으며,
    은신처 안 표적을 쥐고 있지 않다. 고정·놓기가 실제로 일어난다."""
    kept = locks = 0
    for seed in (32071, 32072):
        w = _ChaseSpy(load_v2_config(R3_ON), seeds=[seed])
        pol = _masked_rand(w, seed)
        for _ in range(500):
            w.step(pol(w.observe()))
        assert w.bad_switch == 0 and w.bad_target == 0 and w.lock_in_cover == 0
        kept += w.kept
        st = w.r3_stats()
        locks += st["chase_lock_n"]
        assert st["chase_rel_catch_n"] + st["chase_rel_cover_n"] + st["chase_rel_state_n"] > 0
    assert kept > 100 and locks > 20


# --------------------------------------------------------------------- #
# (c′) 늑대 은신처 진입 금지
# --------------------------------------------------------------------- #


def _wall_cfg(**kw):
    return _cfg("realism_shelter", realism_shelter=dict(block_predators=True, **kw))


def test_wall_push_keeps_tangential_motion():
    """원 둘레의 늑대가 안쪽 + 둘레 방향으로 움직이면 원 밖(반지름 r + WALL_EPS)으로 밀려 둘레를 따라간다 — 둘레 방향 성분은 남고 안쪽
    성분은 없어진다. 둘레 방향으로만 움직이면 그대로다(접선은 원 밖이다). 중심 쪽으로 곧장 가면 제자리다."""
    w, c = _arena(_wall_cfg(), cover=((0.0, 0.0, 5.0),))
    r = 5.0
    p = np.array([c + [r + WALL_EPS, 0.0]])
    sel = np.array([True])
    q, pushed = w._rz_wall_push(p + [-0.3, 0.4], p, sel)
    assert pushed[0]
    rad = np.linalg.norm(q[0] - c)
    assert r < rad <= r + 2 * WALL_EPS
    d = q[0] - p[0]
    assert d[1] >= 0.4 * 0.99 and abs(d[0]) < 0.05                     # 둘레 방향(+y) 성분이 남고 안쪽(−x) 성분은 거의 없다
    q, pushed = w._rz_wall_push(p + [0.0, 0.4], p, sel)
    assert not pushed[0]
    np.testing.assert_array_equal(q, p + [0.0, 0.4])
    q, pushed = w._rz_wall_push(p + [-0.4, 0.0], p, sel)
    assert pushed[0] and np.linalg.norm(q[0] - p[0]) < 1e-9
    q, pushed = w._rz_wall_push(np.array([c]), p, sel)                 # 중심과 겹치면 이전 위치 쪽으로
    np.testing.assert_allclose(q[0], c + [r + WALL_EPS, 0.0], rtol=0, atol=1e-12)
    q, pushed = w._rz_wall_push(p + [-0.3, 0.4], p, np.array([False]))  # 막지 않는 위협은 그대로
    assert not pushed[0]


def test_wolf_slides_around_shelter_to_reach_deer():
    """원 건너편 사슴을 쫓는 늑대는 원을 뚫지 않고 둘레를 따라 돌아간다(모든 스텝 원 밖). 진입 금지가 없으면 원을 지나간다."""
    for block in (True, False):
        cfg = _wall_cfg() if block else _plain_cfg()
        w, c = _arena(cfg, threat=(-7.0, 0.0), deer=((6.0, 2.0),), cover=((0.0, 0.0, 4.0),))
        ever_in = False
        for _ in range(150):
            w._step_predators_v3()
            inside = np.linalg.norm(w.pred_pos[0] - c) < 4.0
            ever_in |= bool(inside)
            if block:
                assert not inside
            if np.linalg.norm(w.pred_pos[0] - w.pos[0]) < 1.0:
                break
        assert ever_in != block
        assert w.pred_pos[0, 0] > c[0]                                   # 건너편까지 갔다
        if block:
            assert w.r3_stats()["wall_push_n"] > 0 and w.r3_stats()["wall_inside_n"] == 0.0


def test_wall_corner_at_map_edge_turns_wolf_around():
    """원이 맵 아래 가장자리에 걸친 구석(원과 벽 사이 막다른 곳)으로 배회하는 늑대: 밀어낸 자리가 맵 밖이라 자르면 원 안이고, 접선으로도
    못 간다 → 그 스텝은 제자리에 남고 돌아선다(heading 이 반대). 그래서 구석에 오래 갇히지 않는다(돌아서기가 없으면 보정 시드 20001 에서
    한 늑대가 783스텝 멈췄다)."""
    w, c = _arena(_wall_cfg(), deer=((-30.0, 30.0),))
    cx = c[0]
    w.cov_c, w.cov_r = np.array([[cx, 6.0]]), np.array([8.0])
    x0 = cx - math.sqrt(64.0 - 36.0) - 0.3                   # 원이 아래 벽과 만나는 점 바로 왼쪽(원 밖)
    w.pred_pos = np.array([[x0, 0.05]])
    w.pred_head = np.array([[1.0, 0.0]])
    assert not w._rz_inside_disc(w.pred_pos).any()
    still, turned = 0, False
    for _ in range(30):
        old = w.pred_pos.copy()
        w._step_predators_v3()
        assert not w._rz_inside_disc(w.pred_pos).any()
        if np.array_equal(w.pred_pos, old):
            still += 1
            turned |= bool(w.pred_head[0, 0] < 0.0)
    st = w.r3_stats()
    assert st["wall_stuck_n"] >= 1 and turned and still <= 3
    assert w.pred_pos[0, 0] < x0                             # 돌아서 왼쪽으로 나갔다


def test_wall_dead_end_rules():
    """막다른 곳 판정(가려던 거리의 WALL_DEAD_FRAC 도 못 감)은 원 중심 쪽으로 곧장 부딪힌 늑대에게만 걸리고(돌아선다), 비스듬히 부딪혀
    둘레를 따라 미끄러지는 늑대에게는 걸리지 않는다(가려던 방향을 그대로 본다)."""
    for ang, dead in ((0.0, True), (30.0, False)):
        # 늑대는 원 왼쪽 둘레에서 실거리 12 의 사슴을 쫓는다(배회 선회 난수 없이 방향이 정해진다). 0° = 원 중심 너머의 사슴
        a = math.radians(ang)
        off = np.array([-(5.0 + WALL_EPS), 0.0])
        w, c = _arena(_wall_cfg(), threat=tuple(off), deer=(tuple(off + 12.0 * np.array([math.cos(a), math.sin(a)])),),
                      cover=((0.0, 0.0, 5.0),))
        assert not w._in_cover(w.pos[:1]).any()
        w._step_predators_v3()
        assert w.pred_target[0] == 0
        assert not w._rz_inside_disc(w.pred_pos).any()
        assert (w.pred_head[0, 0] < 0.0) == dead and w.r3_stats()["wall_stuck_n"] == (1.0 if dead else 0.0)


class _StuckSpy(World):
    def step(self, a):
        old = self.pred_pos.copy()
        # (j) 10-15: 잡은 뒤 서서 먹는 늑대(이 스텝 첫머리 감소 뒤에도 쿨다운이 남음)는 일부러 제자리다 — 끼임으로 세지 않는다
        eating = (self.pred_cd >= 2) if self._eat_in_place else np.zeros(self.M, dtype=bool)
        out = super().step(a)
        awake = ~self.pred_asleep & ~self.pred_is_player & ~eating
        still = awake & (np.linalg.norm(self.pred_pos - old, axis=1) == 0.0)
        self.run = np.where(still, getattr(self, "run", np.zeros(self.M, dtype=np.int64)) + 1, 0)
        self.max_run = max(getattr(self, "max_run", 0), int(self.run.max()))
        return out


@pytest.mark.parametrize("seed", [20000, 20001])
def test_no_long_wall_stuck_runs(seed):
    """보정 시드(원이 맵 가장자리에 걸치거나 서로 겹친 세계): R_base 사슴과 2000 스텝 돌려도 깨어 있는 늑대가 몇 스텝 넘게 제자리에
    멈추지 않는다(잡은 뒤 서서 먹는 늑대 — (j) — 는 뺀다). 막다른 곳 제자리 수도 적다."""
    cfg = load_v2_config(R3_ON)
    w = _StuckSpy(cfg, seeds=[seed])
    pol = ro.build_policy(rr.rule_spec(cfg, 4.0, 0.9), 0)
    ro.forward_bind(pol, w)
    for _ in range(2000):
        w.step(np.asarray(pol(w.observe()), dtype=np.float64))
    st = w.r3_stats()
    assert w.max_run <= 5 and st["wall_inside_n"] == 0.0
    assert st["wall_stuck_n"] <= 0.01 * 2000 * w.M and st["wall_push_n"] > 0


def test_player_blocked_only_with_player_too():
    for player_too in (True, False):
        w, c = _arena(_wall_cfg(player_too=player_too), kind="player", threat=(-7.0, 0.0), deer=((6.0, 0.5),),
                      cover=((0.0, 0.0, 4.0),))
        w.player_mode[:] = PM_CHARGE
        w.player_left[:] = 10 ** 6
        ever_in = False
        for _ in range(40):
            w._step_predators_v3()
            ever_in |= bool(np.linalg.norm(w.pred_pos[0] - c) < 4.0)
        assert ever_in != player_too


@pytest.mark.parametrize("mode", ["stalk", "charge"])
def test_player_gives_up_in_dead_end(mode):
    """플레이어형 위협은 맵 전체를 봐서 막다른 곳(겹친 두 원 사이 V 자 틈)에서 돌아서도 다음 스텝에 같은 사슴 쪽으로 되돌아온다. 그래서
    표적이 있는 플레이어가 막다른 곳에 닿으면 접근을 그만둔다: 잠행 모드는 배회 모드로(남은 모드 길이는 다시 뽑지 않는다), 돌진 모드는
    돌진을 끝내고 휴식으로 간다. 그 뒤 틈을 벗어난다(10-14 검토 — 고치기 전에는 탐색 시드 32018 에서 130스텝 넘게 멈췄다)."""
    w, c = _arena(_wall_cfg(), kind="player", threat=(-8.0, 0.0), deer=((8.0, 0.0),),
                  cover=((0.0, 3.0, 4.0), (0.0, -3.0, 4.0)))
    if mode == "charge":
        w.player_mode[:] = PM_CHARGE
    left0 = int(w.player_left[0])
    gave = None
    for n in range(1, 80):
        w._step_predators_v3()
        assert not w._rz_inside_disc(w.pred_pos).any()
        if w.r3_stats()["wall_giveup_n"] > 0:
            gave = n
            break
    assert gave is not None and w.r3_stats()["wall_stuck_n"] >= 1
    notch = c + [-math.sqrt(16.0 - 9.0), 0.0]
    assert np.linalg.norm(w.pred_pos[0] - notch) < 1.0                   # V 자 틈 꼭짓점 앞 한 걸음 안에서 막혔다
    if mode == "stalk":
        assert w.player_mode[0] == PM_WANDER and w.player_left[0] == left0 - gave     # 길이는 그대로(스텝마다 1 씩만 준다)
        for _ in range(30):
            w._step_predators_v3()
        assert w.player_mode[0] == PM_WANDER and np.linalg.norm(w.pred_pos[0] - notch) > 1.0      # 틈을 벗어났다
    else:
        assert w.player_mode[0] == PM_REST
    assert w.r3_stats()["wall_inside_n"] == 0.0


def test_no_long_player_stall_in_runs():
    """R3 판정 세계, 플레이어가 늘 있는 세계(탐색 시드 32018 — 고치기 전에 잠행 플레이어가 V 자 틈에서 130스텝 넘게 멈춘 세계): 쉬지
    않는 플레이어가 은신처 둘레에서 이어서 멈춘 스텝이 짧다."""
    cfg = _with(load_v2_config(R3_ON), threats=dict(player_frac=1.0))
    w = World(cfg, seeds=[32018])
    pol = ro.build_policy(rr.rule_spec(cfg, 4.0, 0.9), 32018)
    ro.forward_bind(pol, w)
    pl = np.flatnonzero(w.pred_is_player)
    assert len(pl) == 1
    run = best = 0
    for _ in range(1500):
        old = w.pred_pos[pl[0]].copy()
        w.step(np.asarray(pol(w.observe()), dtype=np.float64))
        p = w.pred_pos[pl[0]]
        edge = (np.sqrt(((p - w.cov_c) ** 2).sum(1)) - w.cov_r).min()
        stalled = edge < 1e-3 and np.linalg.norm(p - old) < 0.02 and w.player_mode[pl[0]] != PM_REST
        run = run + 1 if stalled else 0
        best = max(best, run)
    st = w.r3_stats()
    assert best <= 5 and st["wall_giveup_n"] > 0 and st["wall_inside_n"] == 0.0


class _WallSpy(World):
    def step(self, a):
        out = super().step(a)
        sel = self._zw_sel
        self.wolf_inside = getattr(self, "wolf_inside", 0) + int(np.count_nonzero(sel & self._rz_inside_disc(self.pred_pos)))
        self.deer_inside = getattr(self, "deer_inside", 0) + int(np.count_nonzero(self._in_cover(self.pos)))
        return out


def test_wolves_never_inside_shelter_after_any_step():
    """R3 판정 세계 롤아웃(탐색 시드): reset 뒤와 모든 스텝 뒤에 막는 위협(늑대·플레이어)은 어느 은신처 원 안에도 없다. 사슴은 원에
    드나든다(진입 금지는 포식자 전용이다)."""
    deer_in = 0
    for seed in (32073, 32074, 32075):
        w = _WallSpy(_with(load_v2_config(R3_ON), threats=dict(player_frac=1.0)), seeds=[seed])
        assert w._zw_sel.all() and not (w._zw_sel & w._rz_inside_disc(w.pred_pos)).any()
        pol = _masked_rand(w, seed)
        for _ in range(500):
            w.step(pol(w.observe()))
        assert w.wolf_inside == 0 and w.r3_stats()["wall_inside_n"] == 0.0
        deer_in += w.deer_inside
    assert deer_in > 0


def test_wall_reset_moves_wolves_out():
    """reset 때 원 안에 놓인 늑대는 가장 가까운 원 밖 자리로 옮긴다(난수 없음). 원 밖에 놓인 늑대와 v1 배치 난수는 그대로다."""
    moved = 0
    for seed in range(32000, 32030):
        on = World(load_v2_config(R3_ON), seeds=[seed])
        off = World(_with(load_v2_config(R3_ON), realism_shelter=dict(block_predators=False)), seeds=[seed])
        assert not (on._zw_sel & on._rz_inside_disc(on.pred_pos)).any()
        was_in = on._zw_sel & off._rz_inside_disc(off.pred_pos)
        np.testing.assert_array_equal(on.pred_pos[~was_in], off.pred_pos[~was_in])
        assert (np.linalg.norm(on.pred_pos[was_in] - off.pred_pos[was_in], axis=1) > 0).all()
        assert on.r3_stats()["wall_reset_n"] == float(was_in.sum())
        np.testing.assert_array_equal(on.pos, off.pos)
        moved += int(was_in.sum())
    assert moved > 0


# --------------------------------------------------------------------- #
# (h) 지형 구역
# --------------------------------------------------------------------- #


def test_terrain_multipliers_exact_and_order():
    """사슴: 적용 속도 = 지형을 뺀 같은 세계의 속도 × mult_herb[이동 전 셀] (정확히). 늑대: 이동 = 방향 × ((속력 × 밤 배수) × mult_pred[이동 전
    셀]) — 밤잠 배수 다음에 땅 배수를 곱한다(곱 순서까지 정확히)."""
    base = _cfg("realism_terrain")
    ones = _with(base, realism_terrain=dict(mult_herb=[1.0, 1.0, 1.0], mult_pred=[1.0, 1.0, 1.0]))
    out = {}
    for name, cfg in (("snow", base), ("ones", ones)):
        w, c = _arena(cfg, threat=(-8.0, 0.0), behs=(FL,))
        w._rs.away[0] = [1.0, 0.0]                           # 등 뒤 위협(120° 시야 밖)의 기억 방향으로 뛴다
        w.terrain_cell[:] = 1
        w.step(np.full((w.N, 1), float(FL)))
        out[name] = w
    a, b = out["snow"], out["ones"]
    np.testing.assert_array_equal(a.vel, b.vel * 0.6)
    assert np.linalg.norm(a.vel[0]) > 0.0
    # 늑대: 밤 배수 0.7 을 두고 포식자 스텝만
    w, c = _arena(base, threat=(-8.0, 0.0))
    w.terrain_cell[:] = 1
    w._pred_speed_mult[:] = 0.7
    old = w.pred_pos.copy()
    dx, dy = w.pos[0, 0] - old[0, 0], w.pos[0, 1] - old[0, 1]
    inv = 1.0 / max(math.sqrt(dx * dx + dy * dy), 1e-9)
    move = np.array([dx * inv, dy * inv])
    w._step_predators_v3()
    np.testing.assert_array_equal(w.pred_pos[0], old[0] + move * ((0.5 * 0.7) * 0.85))
    w2, _ = _arena(base, threat=(-8.0, 0.0))
    w2.terrain_cell[:] = 2                                               # 거친 땅
    w2._step_predators_v3()
    np.testing.assert_array_equal(w2.pred_pos[0], old[0] + move * (0.5 * 0.9))


def test_terrain_uses_pre_move_cell():
    """그 스텝 이동 전 위치 셀의 배수다: 보통 땅에서 눈으로 넘어가는 스텝은 다 빠르고, 눈 위에서 시작한 다음 스텝부터 느리다."""
    w, c = _arena(_cfg("realism_terrain"), threat=(-8.0, 0.0), behs=(FL,))
    cell = w.cfg.food_cell
    ix0 = int(w.pos[0, 0] // cell)
    w.terrain_cell[:, ix0 + 1:] = 1                                      # 사슴 셀 오른쪽부터 눈
    w.pos[0, 0] = (ix0 + 1) * cell - 0.1                                 # 경계 바로 왼쪽(보통 땅)
    w._rs.away[0] = [1.0, 0.0]                                           # +x 로 뛴다(등 뒤 위협의 기억 방향)
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)
    speeds = []
    for _ in range(3):
        w.step(np.full((w.N, 1), float(FL)))
        speeds.append(float(np.linalg.norm(w.vel[0])))
    run = w.cfg.herb_speed * 1.0
    np.testing.assert_allclose(speeds, [run, run * 0.6, run * 0.6], rtol=1e-12)


def test_terrain_draws():
    """세계마다 눈·거친 땅이 각각 zero_p(0.25)로 아예 없고(넓이 정확히 0, 원판 없음), 아니면 목표 넓이 이상을 칠한다. 거친 땅은 눈이 아닌
    셀만 칠한다. 지형은 자기 스트림에서만 뽑아 은신처 배치와 독립이다(은신처 넓이를 바꿔도 같은 지형). 탐색 시드 100개, 세계 생성만."""
    cfg = load_v2_config(R3_ON)
    nocov = _with(load_v2_config(R3_ON), realism_cover_food=dict(enabled=False))
    zs = zr = both = 0
    for seed in range(32000, 32100):
        w = World(cfg, seeds=[seed])
        snow, rough = w.terrain_cell == 1, w.terrain_cell == 2
        st = w.r3_stats()
        if w.snow_target == 0.0:
            zs += 1
            assert not snow.any() and st["snow_patches"] == 0.0 and st["snow_frac_actual"] == 0.0
        else:
            assert snow.mean() >= w.snow_target or st["snow_patches"] == 64.0
        if w.rough_target == 0.0:
            zr += 1
            assert not rough.any() and st["rough_patches"] == 0.0
        else:
            assert rough.mean() >= w.rough_target or st["rough_patches"] == 64.0
        both += int(w.snow_target == 0.0 and w.rough_target == 0.0)
        assert st["snow_frac_actual"] == snow.mean() and st["rough_frac_actual"] == rough.mean()
        assert 0.0 <= w.snow_target <= 0.25 and 0.0 <= w.rough_target <= 0.15
        if seed < 32010:                                     # 다른 현실성 블록을 꺼도 같은 지형(자기 스트림만)
            other = World(nocov, seeds=[seed])
            np.testing.assert_array_equal(other.terrain_cell, w.terrain_cell)
    assert 10 <= zs <= 40 and 10 <= zr <= 40 and both >= 1


def test_terrain_independent_of_shelters():
    """은신처 넓이(v1 rand.cover_frac)를 바꿔 은신처 원과 v1 난수열이 달라져도 같은 시드의 지형은 같다(맵 크기는 v1 첫 난수라 같다)."""
    for seed in (32080, 32081, 32082):
        a = World(load_v2_config(R3_ON), seeds=[seed])
        cfg = load_v2_config(R3_ON)
        cfg_b = cfg.replace(rand=dict(cfg.rand, cover_frac=[0.29, 0.30]))
        b = World(cfg_b, seeds=[seed])
        assert a.size == b.size and not np.array_equal(a.cover_cell, b.cover_cell)
        np.testing.assert_array_equal(a.terrain_cell, b.terrain_cell)
        np.testing.assert_array_equal(a.terrain_patches, b.terrain_patches)


def test_terrain_stats_in_runs():
    """롤아웃의 땅별 통계: 사슴-스텝 합 = 스텝 × N, 땅별 포획 합 = 피식 수, 잠행형 돌진 포획 ≤ 돌진 시작."""
    for seed in (32083, 32084):
        w = World(load_v2_config(R3_ON), seeds=[seed])
        pol = _masked_rand(w, seed)
        for _ in range(400):
            w.step(pol(w.observe()))
        st = w.r3_stats()
        assert sum(st[f"deer_n_{t}"] for t in TERRAIN_NAMES) == 400 * w.N
        assert sum(st[f"catch_{t}_n"] for t in TERRAIN_NAMES) == w._pred_deaths
        for t in TERRAIN_NAMES:
            assert st[f"pounce_hit_{t}_n"] <= st[f"pounce_{t}_n"]
            if st[f"deer_n_{t}"] > 0:
                assert st[f"catch_rate_{t}"] == st[f"catch_{t}_n"] / st[f"deer_n_{t}"]


# --------------------------------------------------------------------- #
# 얼기를 뺀 허용 목록 (사용자 '사슴 얼기를 없애')
# --------------------------------------------------------------------- #


def test_effective_allowed():
    cfg3, cfg1 = load_v2_config(R3_ON), load_v2_config(R1_ON)
    full = ("graze", "flee", "hide", "freeze")
    assert rp.effective_allowed(full, cfg3) == ("graze", "flee", "hide")
    assert rp.effective_allowed(full, cfg1) == full
    assert rp.effective_allowed(("graze", "flee", "hide"), cfg1) == ("graze", "flee", "hide")
    assert rp.effective_allowed(full, None) == full
    assert rp.effective_allowed(full, load_v2_config(CFG / "v3_r0_on.yaml")) == full         # 목록 블록이 없는 세계
    with pytest.raises(ValueError, match="graze"):
        rp.effective_allowed(("flee", "hide"), cfg3)


def test_freeze_never_executed_in_r3_runs():
    """R3 세계의 마스크(허용 ∧ 가능 ∧ 결정)는 FREEZE·SLEEP 을 늘 막는다 — FREEZE 에 큰 확률을 준 정책도 한 번도 얼지 않는다. 같은
    정책이 얼기가 든 목록(v3_real1_on)에서는 언다(대조)."""
    for path, want in ((R3_ON, False), (REAL["all"], True)):
        froze = 0
        for seed in (32085, 32086):
            w = World(load_v2_config(path), seeds=[seed])
            pol = _masked_rand(w, seed, freeze_bias=True)
            for _ in range(300):
                a = pol(w.observe())
                assert not (pol.last_mask[:, S]).any()
                if not want:
                    assert not pol.last_mask[:, Z].any() and not (a == Z).any()
                w.step(a)
                froze += int(np.count_nonzero(w.behavior == Z))
        assert (froze > 0) == want


def test_rule_policies_never_freeze_in_r3():
    """R3 세계의 손 규칙(R_base(4, 0.9)·eval_v3 FSM — 목록 행동의 니치만 얹는다)은 FREEZE 를 요청하지 않는다."""
    import eval_v3

    cfg = load_v2_config(R3_ON)
    allowed = rp.rep_params(cfg)["allowed"]
    for spec in (rr.rule_spec(cfg, 4.0, 0.9), eval_v3.fsm_spec(cfg, allowed, "near")):
        w = World(cfg, seeds=[32087])
        pol = ro.build_policy(spec, 0)
        ro.forward_bind(pol, w)
        for _ in range(300):
            a = np.asarray(pol(w.observe()), dtype=np.float64)
            assert not (a == Z).any() and not (a == S).any()
            w.step(a)
        assert not (w._rep_hist[..., Z]).any()
    with pytest.raises(ValueError, match="freeze"):
        eval_v3.policy_spec("c_freeze", "x.zip", cfg, allowed, "near")


def test_r1b_in_r3_world_never_freezes():
    """출시 두뇌 R1b(얼기가 든 목록, 마스크 판 2)는 관측·판이 같아 R3 세계에 그대로 얹힌다. 판정 롤아웃의 허용은 모델 ∩ 세계라 FREEZE 칸이
    막히고 한 번도 얼지 않는다. 같은 모델이 1단계 세계에서는 얼기를 고른다(대조 — 막는 것은 목록뿐이다)."""
    if not R1_MODEL.exists():
        pytest.skip("R1b 모델 없음")
    froze = {}
    for path in (R3_ON, REAL["all"]):
        pol = ro.build_policy({"kind": "rep_learned", "path": str(R1_MODEL)}, 0)
        n = 0
        for seed in (32088, 32089):
            w = World(load_v2_config(path), seeds=[seed])
            ro.forward_bind(pol, w)
            for _ in range(400):
                a = pol(w.observe())
                if path == R3_ON:
                    assert not pol.last_mask[:, Z].any() and not (a == Z).any()
                w.step(a)
                n += int(np.count_nonzero(w.behavior == Z))
        froze[path.name] = n
        assert pol.allowed == (("graze", "flee", "hide") if path == R3_ON else ("graze", "flee", "hide", "freeze"))
    assert froze[R3_ON.name] == 0 and froze[REAL["all"].name] > 0


def test_r1b_weights_load_into_r3_policy():
    """대응 1회(H13, R1b s3 가중치에서 다시 시작): R3 학습 설정으로 만든 정책(18 → 64 → 64 → 5, 마스크 판 2, 목록 graze·flee·hide)에
    R1b 의 state_dict 가 strict 로 실린다. FREEZE 로짓은 남지만 마스크가 늘 막아 확률이 정확히 0 이고, R1b 가 FREEZE 를 가장 크게 본
    결정에서는 남은 행동 가운데 로짓이 가장 큰 것이 나온다(로짓 순서는 그대로)."""
    if not R1_MODEL.exists():
        pytest.skip("R1b 모델 없음")
    from stable_baselines3 import PPO

    from env_v2.vec_env import MultiWorldVecEnv
    from train_v3 import make_model_rep

    cfg = load_v2_config(R3)
    venv = MultiWorldVecEnv(cfg, num_worlds=1, meta_seed=0)
    model = make_model_rep(venv, rp.rep_params(cfg), None, seed=0)
    r1b = PPO.load(str(R1_MODEL), device="cpu")
    model.policy.load_state_dict(r1b.policy.state_dict(), strict=True)
    assert model.policy.rep_mask_version == r1b.policy.rep_mask_version == 2
    assert tuple(model.policy.rep_allowed) == ("graze", "flee", "hide")
    w = World(cfg, seeds=[32090])
    params = rp.rep_params(cfg)
    params1 = {"allowed_mask": r1b.policy.rep_allowed_mask}
    picked_freeze = 0
    for _ in range(200):
        obs = w.observe()
        pk = w.rep_peek()
        m3 = rp.action_mask(pk, obs, params, obs_names=w.obs_names)
        m1 = rp.action_mask(pk, obs, params1, obs_names=w.obs_names)
        pi3, _, _ = rp.rep_distribution(model.policy, rp.policy_obs(obs, m3))
        a3 = rp.rep_argmax(model.policy, rp.policy_obs(obs, m3))
        a1 = rp.rep_argmax(r1b.policy, rp.policy_obs(obs, m1))
        assert (pi3[:, Z] == 0.0).all() and not (a3 == Z).any()
        same = a1 != Z
        np.testing.assert_array_equal(a3[same], a1[same])             # R1b 가 FREEZE 를 고르지 않은 곳은 같은 선택
        picked_freeze += int(np.count_nonzero(~same))
        w.step(a3.astype(np.float64)[:, None])
    assert picked_freeze > 0


def test_training_vecenv_masks_freeze():
    """학습 경로(MultiWorldVecEnv 이산 경로)의 마스크도 FREEZE·SLEEP 을 막는다."""
    from env_v2.vec_env import MultiWorldVecEnv

    venv = MultiWorldVecEnv(load_v2_config(R3), num_worlds=2, meta_seed=0)
    venv.reset()
    rng = np.random.default_rng(14)
    for _ in range(40):
        m = venv.current_masks()
        assert not m[:, Z].any() and not m[:, S].any()
        a = rp.sample_masked(np.full(m.shape, 0.2), m, rng.random(len(m)))
        venv.step_async(a)
        venv.step_wait()
    for w in venv.worlds:
        assert not (w._rep_hist[..., Z]).any()


def test_measure_fdec_path_without_freeze():
    """f_dec 측정 경로(train_v3 measure-fdec)가 얼기 없는 목록에서 돈다(짧게)."""
    from train_v3 import measure_fdec

    res = measure_fdec(load_v2_config(R3), seeds=(20000,), steps=40)
    assert res["allowed"] == ["graze", "flee", "hide"] and 0.0 < res["f_dec"] <= 1.0
    assert res["per_seed"][0]["f_dec"] == res["per_seed"][0]["decide_frac_world"]


def test_measure_pi_and_eval_v3_r1b_without_freeze(tmp_path):
    """니치 π 측정(measure-pi)과 eval_v3 r1b 판정 경로가 얼기 없는 R3 판정 세계에서 돈다(R1b 를 얹어 짧게): 허용 = graze·flee·hide,
    판정 U 는 U_ESC·U_HIDE′ 뿐(U_FREEZE′ 없음), 사용 비중도 목록 셋, RL 의 FREEZE 선택 0, 얼기 대조(c_freeze)는 없다."""
    if not R1_MODEL.exists():
        pytest.skip("R1b 모델 없음")
    import eval_v3
    from train_v3 import measure_pi

    res = measure_pi(load_v2_config(R3_ON), R1_MODEL, seeds=(20001,), steps=40, udef="r1b")
    assert res["allowed"] == ["graze", "flee", "hide"] and not any("freeze" in k for k in res["pooled"])
    out = eval_v3.judge(str(R1_MODEL), "smoke_r3", seeds=[20002], steps=40, out=tmp_path, config="configs/v3_r3_on.yaml",
                        udef="r1b")
    gate = out["gate"]
    assert set(gate["u"]["items"]) == {"esc", "hide"}
    assert set(gate["use"]["items"]) == {"graze", "flee", "hide"}
    assert out["meta"]["allowed"] == ["graze", "flee", "hide"] and "c_freeze" not in out["meta"]["policies"]
    assert out["pooled"]["rl"]["choice_freq"][Z] == 0.0 and out["pooled"]["rl"]["use"]["freeze"] == 0.0
    assert (tmp_path / "smoke_r3.md").exists()


# --------------------------------------------------------------------- #
# 롤아웃·도구
# --------------------------------------------------------------------- #


def test_rollout_rows_carry_r3_columns_only_when_on():
    spec = {"kind": "fixed", "action": [0.0]}
    r_on = ro.rollout(load_v2_config(R3_ON), ro.build_policy(spec), 32091, 120)
    r_off = ro.rollout(load_v2_config(REAL["all"]), ro.build_policy(spec), 32091, 120)
    assert set(ro.R3_COLUMNS) <= set(r_on) and not set(ro.R3_COLUMNS) & set(r_off)
    assert set(ro.REALISM_COLUMNS) <= set(r_on)
    assert tuple(ro.R3_COLUMNS) == R3_STAT_COLUMNS
    json.dumps(ro.public_row(r_on))
    with pytest.raises(ValueError, match="r3_stats"):
        World(load_v2_config(REAL["all"]), seeds=[32092]).r3_stats()


def test_golden_exporters_refuse_r3_world(tmp_path):
    """C++ 골든 도구는 R3 세계를 받지 않는다(C++ 에 아직 없는 규칙이다)."""
    import export_golden_v3_threat as egt

    with pytest.raises(SystemExit, match="realism"):
        egt.cfg_constants(load_v2_config(R3_ON))
    # 밤잠 세계(골든이 받는 유일한 현실성 규칙)에 R3 새 블록 하나만 더해도 거부한다
    egt.cfg_constants(load_v2_config(REAL["night"]))
    for name in NEW:
        with pytest.raises(SystemExit, match=name):
            egt.cfg_constants(_cfg(name, base=REAL["night"]))
    if R1_MODEL.exists():
        import export_golden_v3_world as egw

        with pytest.raises(SystemExit, match="realism"):
            egw.export(R1_MODEL, R3_ON, tmp_path)


# --------------------------------------------------------------------- #
# (j) 늑대 먹는 시간 — threats.eat_in_place (선택 키) + v1 pred_eat_cd (10-15 사람 결정 '먹는 시간 주기 (약 5초)')
# --------------------------------------------------------------------- #

EAT_BASE_COMMIT = "f6e8b6e"      # (j) 직전 커밋(사람 결정 10-14 반영 문서) — R3 세계를 먹는 시간 끔 값으로 되돌리면 이 코드와 비트 동일
EAT_SECONDS = 5.0                # 사람 결정 10-15 '먹는 시간 주기 (약 5초)'


def _eat_cfg(cd=38, on=True, base=R1_ON, names=(), **over):
    """base 설정 + R3 블록(names, v3_r3_on 의 값) + 늑대 먹는 시간: pred_eat_cd = cd(v1 키), threats.eat_in_place = on."""
    over = dict(over, threats=dict(over.get("threats", {}), eat_in_place=on))
    return _cfg(*names, base=base, **over).replace(pred_eat_cd=cd)


def test_eat_time_is_five_seconds():
    """R3 설정의 먹는 시간 38스텝 = 5초 ÷ 1스텝(policy_interval 8 ÷ 60 = 2/15초) = 37.5 를 반올림(0.5 는 올림)한 값이다. 지난 값 5스텝은
    0.67초(언리얼 CVar eco.IntegratedV3.WolfEatSeconds 의 옛 값)의 같은 반올림이다. 플레이어형 위협의 쿨다운은 그대로다."""
    for path in (R3, R3_ON):
        cfg = load_v2_config(path)
        step_s = cfg.policy_interval / 60.0
        assert math.isclose(step_s, 2.0 / 15.0) and EAT_SECONDS / step_s == 37.5
        assert cfg.pred_eat_cd == math.floor(EAT_SECONDS / step_s + 0.5) == 38
        assert cfg.v2["features"]["threats"]["eat_in_place"] is True
        assert cfg.v2["features"]["threats"]["player_cooldown"] == _raw(R1_ON)["features"]["threats"]["player_cooldown"]
    old = load_v2_config(R1_ON)
    assert old.pred_eat_cd == math.floor(0.67 / (old.policy_interval / 60.0) + 0.5) == 5
    for path in (R1_ON, R1, R2_ON, *REAL.values()):                # 지난 설정은 그대로다(키 없음 = 끔)
        cfg = load_v2_config(path)
        assert cfg.pred_eat_cd == 5 and not World(cfg, seeds=[32093])._eat_in_place


@pytest.mark.parametrize("kw, cd, match", [
    (dict(eat_in_place=1), 38, "eat_in_place"),
    (dict(eat_in_place="true"), 38, "eat_in_place"),
    (dict(eat_in_place=True), 37.5, "pred_eat_cd"),
    (dict(eat_in_place=True), -1, "pred_eat_cd"),
    (dict(eat_in_place=True), True, "pred_eat_cd"),
])
def test_eat_params_are_checked(kw, cd, match):
    with pytest.raises(ValueError, match=match):
        World(_with(load_v2_config(R1_ON), threats=kw).replace(pred_eat_cd=cd), seeds=[32093])
    with pytest.raises(ValueError, match="선택 키"):
        F.parse_features({"threats": dict(_raw(R1_ON)["features"]["threats"], eat_inplace=True)})


@pytest.mark.parametrize("cd, on", [(5, False), (1, True), (0, True)])
def test_eat_in_place_neutral_equals_off(cd, on):
    """끔 값(eat_in_place false)을 적은 세계는 키가 없는 세계와 비트 동일이다. 켜도 pred_eat_cd ≤ 1 이면 서서 먹는 스텝이 없어(잡은 다음
    스텝에 쿨다운이 0) 끈 세계와 같다."""
    base = load_v2_config(R1_ON).replace(pred_eat_cd=cd)
    wa, wb = World(base, seeds=[32094]), World(_with(base, threats=dict(eat_in_place=on)), seeds=[32094])
    assert not wa._eat_in_place and wb._eat_in_place is on
    _run_pair(wa, wb, _rand(13), _rand(13), 300)


@pytest.mark.parametrize("kind", ["chaser", "stalker"])
def test_eating_wolf_stands_in_place(kind):
    """잡은 스텝 t 에 쿨다운 38. t+1 ~ t+37 동안 늑대는 그 자리에 서서(위치·heading 그대로, 실제 이동 0) 사냥하지 않고(코앞의 사슴도
    잡지 않는다), t+38 에 다시 잡는다(포만 없음). 끄면 같은 동안 기본 속력으로 배회한다. 배회 선회 난수는 켜든 끄든 같은 수만큼 뽑는다."""
    rng_state = {}
    for on in (True, False):
        w, c = _arena(_eat_cfg(on=on), kind=kind, threat=(-0.8, 0.0), seed=32095)
        assert w._eat_in_place is on
        caught = w._step_predators_v3()
        assert caught[0] and w.pred_cd[0] == 38
        q0, h0 = w.pred_pos.copy(), w.pred_head.copy()
        for t in range(1, 38):
            w.pos[0] = w.pred_pos[0] + [0.3, 0.0]          # 사슴을 늘 코앞(포획 거리 안)에 둔다
            caught = w._step_predators_v3()
            assert not caught.any() and w.pred_cd[0] == 38 - t
            if on:
                np.testing.assert_array_equal(w.pred_pos, q0)
                np.testing.assert_array_equal(w.pred_head, h0)
                assert not w.pred_vel.any()
            else:
                assert np.linalg.norm(w.pred_vel[0]) == pytest.approx(0.5)
        rng_state[on] = str(w.rng.bit_generator.state)
        w.pos[0] = w.pred_pos[0] + [0.3, 0.0]
        caught = w._step_predators_v3()                     # t+38: 쿨다운 0 — 곧바로 다시 사냥해 잡는다
        assert caught[0] and w.pred_cd[0] == 38
    assert rng_state[True] == rng_state[False]


def test_player_threat_ignores_eat_in_place():
    """플레이어형 위협은 eat_in_place 와 무관하다: 잡은 뒤 휴식(player_rest_steps)·쿨다운(player_cooldown 30)이 지금 그대로이고, 켜든 끄든
    궤적이 같다."""
    tr = {}
    for on in (True, False):
        w, c = _arena(_eat_cfg(on=on), kind="player", threat=(-0.8, 0.0), seed=32096)
        assert w._step_predators_v3()[0] and w.pred_cd[0] == 30 and w.player_mode[0] == PM_REST
        tr[on] = [w.pred_pos.copy()]
        for _ in range(45):
            w._step_predators_v3()
            tr[on].append(w.pred_pos.copy())
    np.testing.assert_array_equal(np.array(tr[True]), np.array(tr[False]))


def test_eating_wolf_is_silent_and_releases_lock():
    """R3 블록 위에서: 먹는 늑대는 실제 이동이 0 이라 소리 반경이 0 이고(청각 (b)), 걸음새가 전력이 아니며, 추격 고정을 놓은 채다((f) 1·5)."""
    from env_v2.world import hearing_radius

    cfg = _eat_cfg(names=("realism_hearing", "realism_shelter", "realism_chase"), realism_shelter=dict(block_predators=False))
    w, c = _arena(cfg, threat=(-0.8, 0.0), seed=32097)
    assert w._step_predators_v3()[0] and w.chase_tgt[0] == -1
    for _ in range(5):
        w.pos[0] = w.pred_pos[0] + [3.0, 0.0]              # 늑대 시야 안, 포획 거리 밖
        w._step_predators_v3()
        assert w.chase_tgt[0] == -1 and w.pred_target[0] == -1 and not w.pred_running[0] and not w.pred_vel.any()
        s = np.sqrt((w.pred_vel * w.pred_vel).sum(1)) / w.cfg.herb_speed
        assert hearing_radius(w._zh, s, w.pred_running)[0] == 0.0


def test_eat_rule_in_runs():
    """R3 판정 세계 롤아웃(탐색 시드, R_base): 쿨다운이 남은 늑대(이 스텝 첫머리 감소 뒤 cd > 0, 플레이어형 위협 제외)는 그 스텝에 움직이지
    않는다. 같은 늑대의 두 포획 사이는 38스텝 이상이다. 서서 먹는 늑대-스텝과 포획이 실제로 나온다."""
    eat_n = catch_n = 0
    for seed in (32098, 32099):
        cfg = load_v2_config(R3_ON)
        w = World(cfg, seeds=[seed])
        pol = ro.build_policy(rr.rule_spec(cfg, 4.0, 0.9), seed)
        ro.forward_bind(pol, w)
        last = np.full(w.M, -10 ** 6)
        wolf = ~w.pred_is_player
        for t in range(800):
            cd0 = w.pred_cd.copy()
            w.step(np.asarray(pol(w.observe()), dtype=np.float64))
            eating = (cd0 >= 2) & wolf
            assert not w.pred_vel[eating].any(), t
            eat_n += int(eating.sum())
            got = (w.pred_cd == 38) & wolf
            if got.any():
                assert (t - last[got] >= 38).all(), t
                last[got] = t
                catch_n += int(got.sum())
    assert eat_n > 0 and catch_n > 0


def test_bit_identical_r3_to_pre_eat_code(tmp_path):
    """R3 설정에서 먹는 시간을 끔 값으로 되돌리면(pred_eat_cd 5, eat_in_place false) (j) 직전 코드(EAT_BASE_COMMIT)의 R3 세계와 궤적·통계
    (r3_stats 포함)·v1 난수 상태·기능 스트림이 같다(무작위·R_base·출시 두뇌 R1b)."""
    old_root = _archive(tmp_path, EAT_BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {EAT_BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(TRACE_SRC % dict(keys=KEYS, stats=STATS + ("r3_stats",)), encoding="utf-8")
    old = [dict(config="configs/v3_r3_on.yaml", seed=32096, steps=250, policy="rand"),
           dict(config="configs/v3_r3.yaml", seed=32097, steps=250, policy="rbase")]
    if R1_MODEL.exists():
        old.append(dict(config="configs/v3_r3_on.yaml", seed=32098, steps=200, policy="model", model=str(R1_MODEL)))
    new = [dict(j, v1={"pred_eat_cd": 5}, set={"threats": {"eat_in_place": False}}) for j in old]
    procs = []
    for root, jobs, tag in ((old_root, old, "old"), (ROOT, new, "new")):
        jp, op = tmp_path / f"jobs_{tag}.json", tmp_path / f"out_{tag}.json"
        jp.write_text(json.dumps(jobs), encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, str(script), str(jp), str(op)], cwd=root), op))
    outs = []
    for p, op in procs:
        assert p.wait(timeout=900) == 0
        outs.append(json.loads(op.read_text(encoding="utf-8")))
    for j, a, b in zip(new, *outs):
        first = next((i for i, (x, y) in enumerate(zip(a["hashes"], b["hashes"])) if x != y), None)
        assert first is None and len(a["hashes"]) == len(b["hashes"]), (j, first)
        assert "r3_stats" in a["stats"]
        for k in ("stats", "rng", "obs_names", "streams"):
            assert a[k] == b[k], (j, k)


def test_golden_exporters_refuse_eat_in_place(tmp_path):
    """C++ 골든 도구는 늑대가 서서 먹는 세계를 받지 않는다(C++ FThreatConfig 에는 PredEatCd 만 있고 제자리 규칙이 아직 없다). 먹는 시간만
    다른 세계(pred_eat_cd 38, 제자리 끔)는 C++ 에 이미 있는 계수라 받는다."""
    import export_golden_v3_threat as egt

    with pytest.raises(SystemExit, match="eat_in_place"):
        egt.cfg_constants(_eat_cfg())
    assert egt.cfg_constants(_eat_cfg(on=False))["PredEatCd"] == 38
    if R1_MODEL.exists():
        import export_golden_v3_world as egw

        raw = _raw(R1_ON)
        raw["features"]["threats"]["eat_in_place"] = True
        path = tmp_path / "r1_eat.yaml"
        path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
        with pytest.raises(SystemExit, match="eat_in_place"):
            egw.export(R1_MODEL, path, tmp_path / "out")
