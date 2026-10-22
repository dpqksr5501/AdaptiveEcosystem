"""v3 현실성 1단계 — realism_vision(19)·realism_hearing(20)·realism_shelter(21)·realism_night(22)·realism_cover_food(23)
(10-14 사용자 방향, 정의·식·현실 근거는 env_v2/world.py 모듈 docstring 'realism_*').

비트 동일: 이 단계 직전 커밋(626693c 를 git archive 로 푼 사본)의 코드와 v3_r1_on·v3_r1·v3_r2_on 궤적·통계·config digest 가 같고,
realism 블록을 끈 설정 = 블록이 없는 설정, 규칙마다 중립 값 = 끈 세계, 기능 스트림 없음, deepcopy·pickle.
규칙 단위 시험: (a) 등 뒤 늑대는 300° 에서 보이고 120° 에서 안 보인다(바로 뒤 사각은 둘 다 안 보인다), (b) 달리는 늑대는 등 뒤에서
들리고 잠행·배회하는 늑대는 작은 반경 밖에서 안 들리며 서 있거나 자는 늑대는 안 들린다, (c) 은신처 안 사슴은 행동과 무관하게 잡히지
않는다, (e) 은신처 셀 먹이는 줄인 용량·재생을 따르고 밖은 그대로다, (d) 사슴이 가까운 늑대·사냥 중인 늑대는 해가 져도 눕지 않고,
속력은 해 질 녘·눕기·새벽에 단조롭게 바뀐다. 세로 장애물 확장 지점(구현 없음). 시드는 보정 20000~20019·탐색 32000~32099 만 쓴다.
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
from env_v2.world import (OBSTACLE_COLUMNS, PM_CHARGE, PM_STALK, PM_WANDER, PT_CHASER, PT_PLAYER, PT_STALKER,
                          REALISM_STAT_COLUMNS, ST_POUNCE, ST_ROAM, World, daynight_phase, hearing_radius, night_delays)

CFG = ROOT / "configs"
R1_ON = CFG / "v3_r1_on.yaml"
R2_ON = CFG / "v3_r2_on.yaml"
REAL = {"all": CFG / "v3_real1_on.yaml", "vision": CFG / "v3_real1_vision_on.yaml",
        "hearing": CFG / "v3_real1_hearing_on.yaml", "shelter": CFG / "v3_real1_shelter_on.yaml",
        "night": CFG / "v3_real1_night_on.yaml"}
VERSIONS = {"all": "3.real1", "vision": "3.real1v", "hearing": "3.real1h", "shelter": "3.real1s", "night": "3.real1n"}
RULES = ("realism_vision", "realism_hearing", "realism_shelter", "realism_night", "realism_cover_food")
BLOCKS_OF = {"all": RULES, "vision": ("realism_vision",), "hearing": ("realism_hearing",),
             "shelter": ("realism_shelter", "realism_cover_food"), "night": ("realism_night",)}
BASE_COMMIT = "626693c"              # 현실성 1단계 직전 커밋(main 의 v3 두뇌 통합 레벨 스위치) — 비트 동일 기준
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
R2_MODEL = ROOT / "ckpt" / "v3" / "v3_r2_g995_s3_20m.zip"
G, FL, H, Z, S = rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP
KEYS = ("pos", "head", "energy", "pred_pos", "pred_head", "food", "food_cap", "regen_field", "vel", "pred_cd", "pred_vel",
        "behavior", "beh_phase", "beh_steps", "beh_seq", "stalk_state", "player_mode", "pred_asleep")
STATS = ("stats", "gait_stats", "daynight_stats", "pred_sleep_stats", "repertoire_stats", "threats_stats", "alarm_stats")

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _raw(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _blocks():
    """v3_real1_on.yaml 의 realism 블록 다섯(켬)."""
    return {n: dict(_raw(REAL["all"])["features"][n]) for n in RULES}


def _with(cfg, **blocks):
    """설정의 features 에 블록을 더하거나 덮는다(키 = 기능 이름, 값 = 블록 dict 또는 덮을 키 dict)."""
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _rules_cfg(*names, base=R1_ON, **over):
    """base 설정 + realism 블록(names, v3_real1_on 의 값). over = {기능: {키: 값}} 으로 덮는다."""
    b = _blocks()
    add = {n: b[n] for n in names}
    cfg = _with(load_v2_config(base), **add)
    return _with(cfg, **over) if over else cfg


def _same(d1, d2):
    assert d1.keys() == d2.keys()
    for k in d1:
        a, b = d1[k], d2[k]
        assert a == b or (isinstance(a, float) and math.isnan(a) and math.isnan(b)), k


def _rand(seed):
    rng = np.random.default_rng(seed)
    return lambda obs: rng.integers(0, 5, (len(obs), 1)).astype(np.float64)


def _run_pair(wa, wb, pa, pb, steps=300):
    for _ in range(steps):
        oa, ob = wa.observe(), wb.observe()
        np.testing.assert_array_equal(oa, ob)
        for x, y in zip(wa.step(pa(oa)), wb.step(pb(ob))):
            np.testing.assert_array_equal(x, y)
    for name in STATS:
        try:
            sa = getattr(wa, name)()
        except (ValueError, AttributeError):
            continue
        _same(sa, getattr(wb, name)())
    for k in KEYS:
        if hasattr(wb, k):
            np.testing.assert_array_equal(getattr(wa, k), getattr(wb, k), err_msg=k)
    assert wa.rng.bit_generator.state == wb.rng.bit_generator.state


# --------------------------------------------------------------------- #
# 등록부·설정
# --------------------------------------------------------------------- #


def test_registry_and_param_keys():
    assert (F.FEATURE_IDS["realism_vision"], F.FEATURE_IDS["realism_hearing"], F.FEATURE_IDS["realism_shelter"],
            F.FEATURE_IDS["realism_night"], F.FEATURE_IDS["realism_cover_food"]) == (19, 20, 21, 22, 23)
    assert set(RULES) <= F.IMPLEMENTED   # obstacles(12) 는 야생 2단계 3(10-17)에서 구현했다 — tests/test_wild2_obstacle.py
    b = _blocks()
    for n in RULES:
        assert F.PARAM_KEYS[n] == frozenset(b[n]) - {"enabled"}, n
        assert b[n]["enabled"] is True


@pytest.mark.parametrize("kind", list(REAL))
def test_configs_are_r1_on_plus_blocks(kind):
    """현실성 세계 = v3_r1_on + 그 규칙 블록(+ 전체 세계는 장애물 자리 블록, 끔) + version. 그 밖의 키는 그대로다. 블록 값은 다섯
    파일에서 같다. 관측 이름(18칸)·마스크 판(2)은 v3_r1_on 과 같다."""
    a, b = _raw(REAL[kind]), _raw(R1_ON)
    assert a["version"] == VERSIONS[kind] and b["version"] == "3.r1"
    assert {k: v for k, v in a.items() if k not in ("version", "features")} == \
        {k: v for k, v in b.items() if k not in ("version", "features")}
    extra = set(BLOCKS_OF[kind]) | ({"obstacles"} if kind == "all" else set())
    assert set(a["features"]) - set(b["features"]) == extra
    assert {k: v for k, v in a["features"].items() if k not in extra} == b["features"]
    full = _blocks()
    for n in BLOCKS_OF[kind]:
        assert a["features"][n] == full[n], (kind, n)
    if kind == "all":
        assert a["features"]["obstacles"] == {"enabled": False}
    w, w1 = World(load_v2_config(REAL[kind]), seeds=[32000]), World(load_v2_config(R1_ON), seeds=[32000])
    assert w.obs_names == w1.obs_names and w.obs_dim == 18
    assert rp.mask_version_of(w.obs_names) == 2
    assert {n for n in w.features.active if n.startswith("realism_")} == set(BLOCKS_OF[kind])
    text = REAL[kind].read_text(encoding="utf-8")
    assert chr(0xA7) not in text and "현실 근거" in text


@pytest.mark.parametrize("name, kw, match", [
    ("realism_vision", dict(threat_fov_deg=100.0), "threat_fov_deg"),
    ("realism_vision", dict(threat_fov_deg=361.0), "threat_fov_deg"),
    ("realism_vision", dict(kin_fov_deg=90.0), "kin_fov_deg"),
    ("realism_hearing", dict(r_quiet=30.0), "r_quiet"),
    ("realism_hearing", dict(s_silent=0.0), "s_silent"),
    ("realism_hearing", dict(s_quiet=1.0), "s_quiet"),
    ("realism_hearing", dict(roam_quiet=1), "roam_quiet"),
    ("realism_hearing", dict(cap_to_sight="yes"), "cap_to_sight"),
    ("realism_shelter", dict(untargetable=1), "untargetable"),
    ("realism_shelter", dict(player_too=None), "player_too"),
    ("realism_cover_food", dict(cap_frac=1.5), "cap_frac"),
    ("realism_cover_food", dict(regen_frac=-0.1), "regen_frac"),
    ("realism_night", dict(settle_r=-1.0), "settle_r"),
    ("realism_night", dict(hunt_dark=0.5), "hunt_dark"),
    ("realism_night", dict(hunt_dark=1.2), "hunt_dark"),
    ("realism_night", dict(night_floor=1.5), "night_floor"),
    ("realism_night", dict(night_floor=0.6), "night_floor"),     # > 1 − sleep_dark: 해 질 녘 감속까지 덮는다
    ("realism_night", dict(spread=-0.1), "spread"),
    ("realism_night", dict(ramp_steps=2.5), "ramp_steps"),
    ("realism_night", dict(ramp_steps=True), "ramp_steps"),
])
def test_params_are_checked(name, kw, match):
    with pytest.raises(ValueError, match=match):
        World(_rules_cfg(name, **{name: kw}), seeds=[32000])


def test_prerequisites_and_keys():
    with pytest.raises(ValueError, match="repertoire"):
        World(_rules_cfg("realism_vision", repertoire=dict(enabled=False), threats=dict(enabled=False)), seeds=[32009])
    with pytest.raises(ValueError, match="pred_sleep"):
        World(_rules_cfg("realism_night", pred_sleep=dict(enabled=False)), seeds=[32009])
    b = _blocks()["realism_night"]
    with pytest.raises(ValueError, match="계수"):
        F.parse_features({"realism_night": {k: v for k, v in b.items() if k != "ramp_steps"}})
    with pytest.raises(ValueError, match="모르는 키"):
        F.parse_features({"realism_night": dict(b, late_dark=1.0)})


# --------------------------------------------------------------------- #
# 비트 동일
# --------------------------------------------------------------------- #

TRACE_SRC = r'''
import hashlib, json, sys
sys.path.insert(0, ".")
import env.torch_init
import numpy as np
import yaml
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.world import World
KEYS = %(keys)r
STATS = %(stats)r


def digest(cfg):
    return hashlib.sha1(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]


def run(job):
    cfg = load_v2_config(job["config"])
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for n in job.get("off") or []:
        f[n] = dict(f[n], enabled=False)
    for n, block in (job.get("add_off") or {}).items():
        f[n] = dict(block, enabled=False)
    if job.get("off") or job.get("add_off"):
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


def _archive(tmp_path):
    """현실성 1단계 직전 코드(BASE_COMMIT)의 herbivore_rl 일부를 tmp 에 푼다. git 이나 커밋이 없으면 None.
    10-22: 사본의 동족 무리 중심·분리 두 줄만 지금 코드와 같은 j 차례 합으로 바꾼다 (tests/kin_seq.py)."""
    import kin_seq

    paths = [f"herbivore_rl/{p}" for p in ("env", "env_v2", "policies", "configs", "repertoire_rules.py")]
    try:
        out = subprocess.run(["git", "archive", BASE_COMMIT] + paths, cwd=ROOT.parent, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    with tarfile.open(fileobj=io.BytesIO(out.stdout)) as tf:
        tf.extractall(tmp_path / "base", **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return kin_seq.patch_tree(tmp_path / "base" / "herbivore_rl")


def test_bit_identical_to_pre_realism_code(tmp_path):
    """기존 세계(v3_r1_on·v3_r1·v3_r2_on)는 이 단계 직전 코드와 궤적(스텝마다 관측·행동·보상·사망·terminal_obs·상태 지문)·통계·v1 난수
    상태·관측 이름·기능 스트림·config digest 가 같다. 현실성 세계의 realism 블록을 모두 끈 설정(v3_real1_on, 장애물 자리 블록 포함)과
    v3_r2_on 에 끈 realism 블록을 더한 설정도 직전 코드의 v3_r1_on·v3_r2_on 과 같다. 출시 두뇌 R1b·R2 모델의 롤아웃도 같다."""
    old_root = _archive(tmp_path)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(TRACE_SRC % dict(keys=KEYS, stats=STATS), encoding="utf-8")
    old, new = [], []
    for cfg, seed in (("configs/v3_r1_on.yaml", 32010), ("configs/v3_r1.yaml", 32011), ("configs/v3_r2_on.yaml", 32012)):
        for pol in ("rand", "rbase"):
            j = dict(config=cfg, seed=seed, steps=250, policy=pol)
            old.append(j)
            new.append(j)
    off_blocks = _blocks()
    for kind, pol, seed in (("all", "rand", 32013), ("all", "rbase", 32014), ("shelter", "rand", 32015),
                            ("night", "rbase", 32016)):
        old.append(dict(config="configs/v3_r1_on.yaml", seed=seed, steps=250, policy=pol))
        new.append(dict(config=f"configs/{REAL[kind].name}", off=list(BLOCKS_OF[kind]), seed=seed, steps=250, policy=pol))
    for pol, seed in (("rand", 32017), ("rbase", 32018)):
        old.append(dict(config="configs/v3_r2_on.yaml", seed=seed, steps=250, policy=pol))
        new.append(dict(config="configs/v3_r2_on.yaml", add_off=off_blocks, seed=seed, steps=250, policy=pol))
    if R1_MODEL.exists():
        for cfg, off in (("configs/v3_r1_on.yaml", None), ("configs/v3_real1_on.yaml", list(RULES))):
            old.append(dict(config="configs/v3_r1_on.yaml", seed=32019, steps=200, policy="model", model=str(R1_MODEL)))
            new.append(dict(config=cfg, off=off, seed=32019, steps=200, policy="model", model=str(R1_MODEL)))
    if R2_MODEL.exists():
        j = dict(config="configs/v3_r2_on.yaml", seed=32020, steps=200, policy="model", model=str(R2_MODEL))
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
        if not j.get("off") and not j.get("add_off"):
            assert a["digest"] == b["digest"], j                   # 기존 yaml 의 config digest 는 그대로다


@pytest.mark.parametrize("kind", ["all", "shelter", "night"])
@pytest.mark.parametrize("pol", ["rand", "rbase"])
def test_blocks_off_equal_r1_on(kind, pol):
    """같은 프로세스: 현실성 세계에서 그 규칙 블록을 끄면 v3_r1_on 과 비트 동일이다(장애물 자리 블록이 있어도)."""
    c1 = load_v2_config(R1_ON)
    off = _with(load_v2_config(REAL[kind]), **{n: dict(enabled=False) for n in BLOCKS_OF[kind]})
    wa, wb = World(off, seeds=[32021]), World(c1, seeds=[32021])
    assert not wa._rz and wa.obs_names == wb.obs_names
    pa, pb = (_rand(3), _rand(3)) if pol == "rand" else (ro.build_policy(rr.rule_spec(c, 4.0, 0.9), 0) for c in (off, c1))
    _run_pair(wa, wb, pa, pb, 250)


@pytest.mark.parametrize("name, kw", [
    ("realism_vision", dict(threat_fov_deg=120.0, kin_fov_deg=120.0)),
    ("realism_hearing", dict(r_quiet=0.0, r_loud=0.0)),
], ids=["vision_120", "hearing_r0"])
def test_neutral_values_equal_off(name, kw):
    """중립 값 = 끈 세계: 시야 120°·120°, 소리 반경 0. 통계 칸만 생긴다. (은신처 먹이 부족은 원 가장자리 셀까지 바꾸므로 중립 값이
    없다 — test_cover_food_capacity_and_regen 이 밖 셀이 v1 그대로인지 본다.)"""
    on = _rules_cfg(name, **{name: kw})
    off = load_v2_config(R1_ON)
    wa, wb = World(on, seeds=[32022]), World(off, seeds=[32022])
    assert wa._rz and not wb._rz
    _run_pair(wa, wb, _rand(4), _rand(4), 300)


def test_realism_makes_no_streams(monkeypatch):
    """현실성 규칙은 기능 스트림을 만들지 않는다(난수 없음). daynight·pred_sleep·threats 스트림만 생긴다."""
    import env_v2.world as wm

    seen = []
    real = wm.feature_stream

    def spy(seed, name, part=0):
        seen.append((name, int(part)))
        return real(seed, name, part)

    monkeypatch.setattr(wm, "feature_stream", spy)
    for kind in ("all", "shelter"):
        w = World(_with(load_v2_config(REAL[kind]), threats=dict(player_frac=1.0)), seeds=[32023])
        pol = _rand(5)
        for _ in range(300):
            w.step(pol(w.observe()))
    assert {n for n, _ in seen} <= {"daynight", "pred_sleep", "threats"}


def test_deterministic_and_copyable():
    cfg = _with(load_v2_config(REAL["all"]), threats=dict(player_frac=1.0))
    a, b = World(cfg, seeds=[32024]), World(cfg, seeds=[32024])
    pa, pb = _rand(6), _rand(6)
    for _ in range(200):
        for x, y in zip(a.step(pa(a.observe())), b.step(pb(b.observe()))):
            np.testing.assert_array_equal(x, y)
    clones = [pickle.loads(pickle.dumps(a)), copy.deepcopy(a)]
    rng = np.random.default_rng(7)
    for _ in range(150):
        act = rng.integers(0, 5, (a.N, 1)).astype(np.float64)
        ra = a.step(act)
        for c in clones:
            for x, y in zip(c.step(act), ra):
                np.testing.assert_array_equal(x, y)
    for c in clones:
        _same(c.realism_stats(), a.realism_stats())


# --------------------------------------------------------------------- #
# 단위 시험 하네스 — 개체 0 과 위협 하나
# --------------------------------------------------------------------- #


def _solo(cfg, kind="chaser", d0=8.0, ang=180.0, beh0=FL, seed=32030, cover=False, crouch=False):
    """개체 0 은 맵 가운데에서 +x 를 본다. 위협은 개체 0 에서 각 ang 도(+x 기준 반시계) 쪽 실거리 d0 에 있고 개체 0 을 본다. 나머지
    개체는 구석 (1, 1). cover 면 개체 0 자리에 반지름 3 의 은신처 하나, 아니면 은신처 없음. 낮 고정(d = 0). 위협의 지난 이동은 0."""
    w = World(cfg, seeds=[seed])
    w.day_fixed = True
    w._daynight_update()
    c = np.array([w.size / 2, w.size / 2])
    if cover:
        w.cov_c, w.cov_r = np.array([c]), np.array([3.0])
    else:
        w.cov_c, w.cov_r = np.zeros((0, 2)), np.zeros(0)
    w.food[:] = 1.0
    w.food_cap[:] = 1.0
    w.pos[:] = [1.0, 1.0]
    w.pos[0] = c
    w.head[:] = [1.0, 0.0]
    a = math.radians(ang)
    q = c + d0 * np.array([math.cos(a), math.sin(a)])
    player = kind == "player"
    w.M, w.M_base = 1, 0 if player else 1
    w.pred_pos = np.array([q])
    v = c - q
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
    if w._sd is not None:
        w._stare_reset()
    if w._zn is not None:
        w._rz_night_reset()
        w._zn_fresh = False
    rs, rp_ = w._rs, w._rp
    rs.behavior[:] = G
    rs.behavior[0] = beh0
    rs.arrived[:] = False
    rs.arrived[0] = beh0 == H and crouch
    rs.lock_left[:] = 0
    rs.jitter[:] = 0
    see = {G: rp_["graze_head_down"], S: rp_["sleep_sight"]}
    w._rep_see[:] = rp_["graze_head_down"]
    w._rep_see[0] = w._rep_see_last[0] = see.get(beh0, 1.0)
    w._rep_still[:] = False
    w._rep_still[0] = beh0 in (Z, S) or (beh0 == H and crouch)
    w._rep_crouch[:] = False
    w._rep_crouch[0] = beh0 == H and crouch
    w._rep_cover = rep.cover_mult(rp_, rs.behavior, w._rep_crouch)
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)
    return w, c


def _moving(w, speed, running):
    """위협의 지난 스텝 이동 = 개체 0 쪽으로 speed × herb_speed, 걸음새 running."""
    v = w.pos[0] - w.pred_pos[0]
    w.pred_vel = np.array([v / np.linalg.norm(v) * speed * w.cfg.herb_speed])
    w.pred_running = np.array([running])
    w._g = w._geometry()
    return w._g


# --------------------------------------------------------------------- #
# (a) 시야
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("ang, seen120, seen300", [(30.0, True, True), (135.0, False, True), (148.0, False, True),
                                                   (155.0, False, False), (180.0, False, False)])
def test_vision_behind_the_back(ang, seen120, seen300):
    """등 뒤(135°·150°)의 늑대는 300° 에서 보이고 120° 에서 안 보인다. 바로 뒤 ±30° 사각(165°·180°)은 둘 다 안 보인다."""
    for cfg, want in ((load_v2_config(R1_ON), seen120), (_rules_cfg("realism_vision"), seen300)):
        w, _ = _solo(cfg, "chaser", 10.0, ang, FL)
        assert bool(w._g["pred_count"][0] > 0) == want, ang
        if want:
            np.testing.assert_allclose(w._obs[0, 2], 10.0 / w.cfg.see_r, rtol=1e-6)


def test_vision_radius_and_kin_unchanged():
    """넓힌 시야각도 반경은 그대로(FLEE 20, GRAZE 12). 동족 시야는 kin_fov_deg 120 이면 바뀌지 않는다."""
    cfg = _rules_cfg("realism_vision")
    w, _ = _solo(cfg, "chaser", 21.0, 135.0, FL)
    assert w._g["pred_count"][0] == 0
    w, _ = _solo(cfg, "chaser", 13.0, 135.0, G)
    assert w._g["pred_count"][0] == 0
    w, _ = _solo(cfg, "chaser", 11.0, 135.0, G)
    assert w._g["pred_count"][0] == 1
    a, b = World(cfg, seeds=[32031]), World(load_v2_config(R1_ON), seeds=[32031])
    np.testing.assert_array_equal(a._g["kin_count"], b._g["kin_count"])


# --------------------------------------------------------------------- #
# (b) 청각
# --------------------------------------------------------------------- #


def test_hearing_radius_formula():
    zh = dict(_blocks()["realism_hearing"])
    s = np.array([0.0, 0.04, 0.2, 0.3, 0.6, 0.95, 1.0, 1.5])
    np.testing.assert_allclose(hearing_radius(zh, s, np.ones(8, dtype=bool)),
                               [0.0, 0.0, 2.0, 2.0, 2.0 + 18.0 * 3 / 7, 2.0 + 18.0 * 0.65 / 0.7, 20.0, 20.0])
    np.testing.assert_allclose(hearing_radius(zh, s, np.zeros(8, dtype=bool)), [0.0, 0.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0])
    np.testing.assert_allclose(hearing_radius(dict(zh, roam_quiet=False), s, np.zeros(8, dtype=bool)),
                               hearing_radius(zh, s, np.ones(8, dtype=bool)))


def test_running_wolf_heard_behind():
    """표적을 쫓아 달리는 늑대(× 0.9)는 바로 뒤(시야 사각) 8 에서 들린다 — 관측 pred_count·pred_dist·접근·recency 에 들어간다.
    청각을 끈 세계와 300° 시야만 켠 세계에서는 감지되지 않는다."""
    for cfg in (load_v2_config(R1_ON), _rules_cfg("realism_vision")):
        w, _ = _solo(cfg, "chaser", 8.0, 180.0, FL)
        w.pred_vel = np.array([[-0.9 * w.cfg.herb_speed, 0.0]])
        assert w._geometry()["pred_count"][0] == 0
    w, _ = _solo(_rules_cfg("realism_vision", "realism_hearing"), "chaser", 8.0, 180.0, FL)
    g = _moving(w, 0.9, True)
    assert g["pred_count"][0] == 1 and g["pred_approach"][0] > 0.9
    o = w._obs_from(g)
    np.testing.assert_allclose(o[0, 1], 1.0 / w.cfg.obs_pred_count_norm)
    np.testing.assert_allclose(o[0, 2], 8.0 / w.cfg.see_r, rtol=1e-6)
    w._rs.recency[0] = 0.0
    rep.perceive(w._rs, w._rp, g)
    assert w._rs.recency[0] == 1.0 and w._rs.away[0, 0] > 0.99          # 위협 반대 = +x


@pytest.mark.parametrize("kind, speed, running, d0, heard", [
    ("stalker", 0.3, False, 5.0, False),       # 잠행: 반경 2 밖
    ("stalker", 0.3, False, 1.5, True),        # 잠행: 반경 2 안
    ("chaser", 0.9, False, 8.0, False),        # 배회(전력 걸음 아님): roam_quiet 로 반경 2
    ("chaser", 0.9, False, 1.5, True),
    ("chaser", 0.0, False, 1.0, False),        # 서 있음: 소리 없음
    ("chaser", 0.04, True, 1.0, False),        # s_silent 아래
    ("stalker", 1.5, True, 19.0, True),        # 돌진: 반경 20
    ("player", 1.3, True, 19.0, True),         # 플레이어 돌진
    ("player", 0.4, False, 5.0, False),        # 플레이어 배회
])
def test_hearing_by_gait(kind, speed, running, d0, heard):
    w, _ = _solo(_rules_cfg("realism_hearing"), kind, d0, 180.0, FL)
    assert bool(_moving(w, speed, running)["pred_count"][0] > 0) == heard


def test_hearing_options_and_limits():
    """roam_quiet false 면 배회 속력 그대로, 자는 위협은 안 들린다, cap_to_sight 는 들리는 반경을 그 사슴의 탐지 반경(GRAZE 12)에서
    자른다(끄면 R 그대로 — 학습 범위 밖)."""
    w, _ = _solo(_rules_cfg("realism_hearing", realism_hearing=dict(roam_quiet=False)), "chaser", 8.0, 180.0, FL)
    assert _moving(w, 0.9, False)["pred_count"][0] == 1
    w, _ = _solo(_rules_cfg("realism_hearing"), "chaser", 3.0, 180.0, FL)
    w.pred_asleep[:] = True
    assert _moving(w, 1.5, True)["pred_count"][0] == 0
    for d0, cap, heard in ((15.0, True, False), (11.0, True, True), (15.0, False, True)):
        w, _ = _solo(_rules_cfg("realism_hearing", realism_hearing=dict(cap_to_sight=cap)), "stalker", d0, 180.0, G)
        assert bool(_moving(w, 1.5, True)["pred_count"][0] > 0) == heard, (d0, cap)


def test_pred_running_hook_from_threat_step():
    """훅 pred_running 은 위협 스텝이 정한다: 표적을 쫓는 추격형·돌진하는 잠행형·돌진 모드 플레이어만 참."""
    cfg = _rules_cfg("realism_hearing")
    w, _ = _solo(cfg, "chaser", 6.0, 0.0, G)
    w._step_predators_v3()
    assert w.pred_running[0]
    w, _ = _solo(cfg, "chaser", 6.0, 0.0, G)
    w.pred_head[:] = [1.0, 0.0]                         # 개체 0 을 등지고 있다(포식자 시야각 밖) → 배회
    w._step_predators_v3()
    assert not w.pred_running[0]
    w, _ = _solo(cfg, "stalker", 10.0, 0.0, G)           # 체감 거리 10 > 6: 잠행
    w._step_predators_v3()
    assert w.stalk_state[0] == ST_ROAM and not w.pred_running[0]
    w, _ = _solo(cfg, "stalker", 5.0, 0.0, G)            # ≤ 6: 돌진 시작
    w._step_predators_v3()
    assert w.stalk_state[0] == ST_POUNCE and w.pred_running[0]
    w, _ = _solo(cfg, "player", 5.0, 0.0, G)
    w._step_predators_v3()
    assert w.player_mode[0] == PM_CHARGE and w.pred_running[0]
    w, _ = _solo(cfg, "player", 5.0, 0.0, G)
    w.player_mode[:] = PM_WANDER
    w._step_predators_v3()
    assert not w.pred_running[0]


# --------------------------------------------------------------------- #
# (c) 은신처 안전
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("beh, crouch", [(G, False), (FL, False), (H, False), (H, True), (Z, False), (S, False)],
                         ids=["graze", "flee", "hide_going", "hide_crouch", "freeze", "sleep"])
@pytest.mark.parametrize("kind", ["chaser", "stalker", "player"])
def test_inside_shelter_never_caught(beh, crouch, kind):
    """은신처 원 안의 사슴은 행동과 무관하게 잡히지 않는다(실거리 0.3, 포획 거리 1). 표적에서도 빠진다(untargetable)."""
    w, _ = _solo(_rules_cfg("realism_shelter"), kind, 0.3, 0.0, beh, cover=True, crouch=crouch)
    if kind == "stalker":
        w.stalk_state[:] = ST_POUNCE
        w.stalk_left[:] = 5
    if kind == "player":
        w.player_mode[:] = PM_CHARGE
        w.player_left[:] = 5
    assert not w._step_predators_v3()[0]
    # 은신 배수만으로도 못 잡는 웅크림(0.3 × 4.0 > 1)을 빼면 '잡힐 거리'였는데 규칙이 막은 것이다
    assert w._zs_saved_n == (0 if crouch else 1)
    assert w.realism_stats()["safe_frac"] > 0.0


@pytest.mark.parametrize("beh", [G, FL])
def test_shelter_control_cases(beh):
    """대조: 규칙이 없으면 은신처 안 GRAZE·FLEE(은신 배수 1.5·1)는 실거리 0.3 에서 잡힌다. 규칙이 있어도 은신처 밖이면 잡힌다."""
    w, _ = _solo(load_v2_config(R1_ON), "chaser", 0.3, 0.0, beh, cover=True)
    assert w._step_predators_v3()[0]
    w, _ = _solo(_rules_cfg("realism_shelter"), "chaser", 0.3, 0.0, beh, cover=False)
    assert w._step_predators_v3()[0]


def test_shelter_options():
    """untargetable: 은신처 안 사슴만 보이면 늑대는 표적이 없어 배회한다(false 면 쫓지만 잡지 못한다). player_too false 면 플레이어는
    은신처 안 GRAZE 를 잡는다."""
    # 표적 유무는 청각 훅 pred_running(표적을 쫓는 추격형 = 참)으로 본다
    for shelter, cover, targeted in ((dict(), True, False), (dict(untargetable=False), True, True), (dict(), False, True)):
        cfg = _rules_cfg("realism_shelter", "realism_hearing", realism_shelter=shelter)
        w, _ = _solo(cfg, "chaser", 5.0, 0.0, G, cover=cover)
        w._step_predators_v3()
        assert bool(w.pred_running[0]) == targeted, (shelter, cover)
    w, _ = _solo(_rules_cfg("realism_shelter", realism_shelter=dict(untargetable=False)), "chaser", 0.3, 0.0, G, cover=True)
    assert not w._step_predators_v3()[0]
    w, _ = _solo(_rules_cfg("realism_shelter", realism_shelter=dict(player_too=False)), "player", 0.3, 0.0, G, cover=True)
    w.player_mode[:] = PM_CHARGE
    w.player_left[:] = 5
    assert w._step_predators_v3()[0]


def test_shelter_drops_stare_lock():
    """stare_down 세계: 잠긴 표적이 은신처 안이면(행동 FREEZE — 원래는 추적 가능) 잠금을 지운다. 규칙이 없으면 남는다."""
    w7 = CFG / "v3_r2_w7_on.yaml"
    for cfg, kept in ((load_v2_config(w7), True), (_rules_cfg("realism_shelter", base=w7), False)):
        w, _ = _solo(cfg, "stalker", 9.0, 0.0, Z, cover=True)
        w.pred_lock[0] = 0
        w._step_predators_v3()
        assert (w.pred_lock[0] == 0) == kept


class _CatchSpy(World):
    def _step_predators_v3(self):
        inc = self._in_cover(self.pos)
        c = super()._step_predators_v3()
        self.in_cover_caught = getattr(self, "in_cover_caught", 0) + int((c & inc).sum())
        self.caught_n = getattr(self, "caught_n", 0) + int(c.sum())
        self.cd_seen = getattr(self, "cd_seen", set()) | set(self.pred_cd[~self.pred_is_player].tolist())
        return c


@pytest.mark.parametrize("kind", ["r1_on", "shelter", "all"])
def test_no_catch_inside_shelter_in_runs(kind):
    """세계 롤아웃(무작위 요청, 탐색 시드): 규칙을 켠 세계에서 은신처 안 포획은 0 이다(끈 세계에서는 생긴다). 늑대 식욕은 그대로다 —
    포획 뒤 쿨다운은 pred_eat_cd(5) 그대로이고 그보다 길지 않다."""
    cfg = load_v2_config(R1_ON if kind == "r1_on" else REAL[kind])
    inside = caught = 0
    cds = set()
    for seed in (32000, 32001):
        w = _CatchSpy(cfg, seeds=[seed])
        pol = _rand(seed)
        for _ in range(1500):
            w.step(pol(w.observe()))
        inside += w.in_cover_caught
        caught += w.caught_n
        cds |= w.cd_seen
    assert caught > 100
    assert (inside > 0) if kind == "r1_on" else (inside == 0)
    assert int(cfg.pred_eat_cd) == 5 and max(cds) == 5


# --------------------------------------------------------------------- #
# (e) 은신처 먹이 부족
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("seed", range(20000, 20020))
def test_cover_food_capacity_and_regen(seed):
    """은신처 셀(cover_food_cell = 은신처 원과 겹치는 셀, v1 cover_cell 을 포함)의 용량 = cap_frac × v1 용량, 재생률 = 밖 × regen_frac.
    밖 셀은 v1 그대로이고 풍부한 패치(용량 ≥ 0.9)가 밖에 남는다. 보정 시드 20 개 모두."""
    on, off = World(_rules_cfg("realism_cover_food"), seeds=[seed]), World(load_v2_config(R1_ON), seeds=[seed])
    zf, cell = on._zf, on.cover_food_cell
    np.testing.assert_array_equal(on.cover_cell, off.cover_cell)            # v1 의 은신처 셀 정의는 그대로다
    assert (cell | ~on.cover_cell).all() and cell.sum() > on.cover_cell.sum()
    np.testing.assert_array_equal(on.food_cap[~cell], off.food_cap[~cell])
    np.testing.assert_allclose(on.food_cap[cell], zf["cap_frac"] * off.food_cap[cell], rtol=0, atol=1e-15)
    open_rate = off.regen_field[~off.cover_cell].max()
    np.testing.assert_array_equal(on.regen_field[~cell], off.regen_field[~cell])
    np.testing.assert_allclose(on.regen_field[cell], open_rate * zf["regen_frac"], rtol=1e-12)
    assert (on.food <= on.food_cap).all() and on.food_cap[~cell].max() >= 0.9
    kept = on.realism_stats()["food_cap_kept"]
    assert 0.4 < kept <= 1.0
    np.testing.assert_allclose(kept, on.food_cap.sum() / off.food_cap.sum())


@pytest.mark.parametrize("seed", range(20000, 20020))
def test_cover_food_covers_every_safe_position(seed):
    """원 안(안전한 자리, `_in_cover`)의 모든 위치는 먹이가 줄어든 셀 위에 있다 — 원 가장자리의 안전한 자리가 v1 그대로의 풍부한 셀에
    남지 않는다(셀 중심만 보는 cover_cell 로는 원 넓이의 약 6% 가 그런 자리였다). 원마다 원판 균등 표본 + 원둘레 바로 안쪽 표본."""
    w = World(_rules_cfg("realism_cover_food"), seeds=[seed])
    rng = np.random.default_rng(seed)
    pts = []
    for c, r in zip(w.cov_c, w.cov_r):
        th = rng.random(3000) * 2.0 * np.pi
        rad = np.concatenate([r * np.sqrt(rng.random(2000)), r * (1.0 - 1e-12 * rng.random(1000))])
        pts.append(c + np.stack([rad * np.cos(th), rad * np.sin(th)], 1))
    p = np.clip(np.concatenate(pts), 0.0, w.size)
    p = p[w._in_cover(p)]
    ix, iy = w._cell_index(p)
    assert len(p) > 1000 and w.cover_food_cell[iy, ix].all()
    rim = ~w.cover_cell[iy, ix]
    assert rim.any()                                         # v1 cover_cell 만으로는 빠지는 자리가 실제로 있다


class _EatSpy(World):
    def _eat(self, e_drained, mult=None):
        g = super()._eat(e_drained, mult)
        inc = self._in_cover(self.pos)
        ix, iy = self._cell_index(self.pos)
        self.rich_safe = getattr(self, "rich_safe", 0) + int(np.count_nonzero(inc & ~self.cover_food_cell[iy, ix]))
        self.safe_n = getattr(self, "safe_n", 0) + int(np.count_nonzero(inc))
        return g


def test_no_rich_food_inside_shelter_in_runs():
    """세계 롤아웃(무작위 요청, 탐색 시드): 원 안에서 먹는 개체는 늘 먹이가 줄어든 셀에서 먹는다."""
    safe = 0
    for seed in (32041, 32042):
        w = _EatSpy(load_v2_config(REAL["shelter"]), seeds=[seed])
        pol = _rand(seed)
        for _ in range(600):
            w.step(pol(w.observe()))
        assert w.rich_safe == 0
        safe += w.safe_n
    assert safe > 0


def test_cover_food_follows_reduced_dynamics():
    """은신처 셀의 먹이는 줄인 용량을 넘지 않고, 비운 셀은 줄인 재생률로 줄인 용량을 향해 다시 찬다(먹지 않는 셀 한 스텝)."""
    w = World(_rules_cfg("realism_cover_food"), seeds=[20004])
    cell = w.cover_food_cell
    pol = _rand(8)
    for _ in range(200):
        w.step(pol(w.observe()))
        assert (w.food[cell] <= w.food_cap[cell] + 1e-12).all()
    w.food[:] = 0.0                                         # 먹이가 없으면 아무도 먹지 못한다 — 한 스텝은 재생뿐이다
    w.step(np.zeros((w.N, 1)))
    np.testing.assert_allclose(w.food, w.regen_field * w.food_cap, rtol=1e-12, atol=0)
    open_rate = w.regen_field[~cell].max()
    assert (w.food[cell] <= w._zf["cap_frac"] * w._zf["regen_frac"] * open_rate + 1e-15).all()


def test_grazing_inside_shelter_is_allowed():
    """'숨으면 못 먹음' 규칙은 없다: 은신처 안 GRAZE 는 먹고(섭식 배수 > 0) 잡히지 않는다. 롤아웃에서 은신처 안 섭취가 있다."""
    w, _ = _solo(_rules_cfg("realism_shelter", "realism_cover_food"), "chaser", 0.3, 0.0, G, cover=True)
    w.energy[0] = 0.5 * w.cfg.max_energy
    _, _, done, _ = w.step(np.full((w.N, 1), float(G)))
    assert w._rep_eat[0] > 0.0 and w.behavior[0] == G and not done[0]
    w = World(load_v2_config(REAL["shelter"]), seeds=[32002])
    pol = _rand(9)
    for _ in range(600):
        w.step(pol(w.observe()))
    assert w.realism_stats()["cover_intake_share"] > 0.0


# --------------------------------------------------------------------- #
# (d) 늑대 밤잠 점진화
# --------------------------------------------------------------------- #


def _night_solo(deer_d=None, delay=3, seed=32040, cfg=None):
    """주행성 늑대 하나, 하루 600 스텝·박명 30(offset 0: 낮 s < 300, 해 짐 s = 300, 새벽 s = 600). 사슴은 구석, deer_d 를 주면 개체 0 이
    늑대에서 그 실거리. 늑대 지연 δ = delay 로 고정. 반환한 세계를 _tick 으로 한 업데이트씩 민다."""
    w = World(cfg if cfg is not None else load_v2_config(REAL["night"]), seeds=[seed])
    w.day_fixed = False
    w.dn_period, w.dn_offset, w.dn_tw = 600, 0, 30
    w.M = w.M_base = 1
    c = np.array([w.size / 2, w.size / 2])
    w.pred_pos = np.array([c])
    w.pred_nocturnal = np.zeros(1, dtype=bool)
    w.pred_asleep = np.zeros(1, dtype=bool)
    w._pred_speed_mult = np.ones(1)
    w.pos[:] = [1.0, 1.0]
    if deer_d is not None:
        w.pos[0] = c + [deer_d, 0.0]
    w.t = 250
    if w._zn is not None:
        w._rz_night_reset()
    w._daynight_update()
    if w._zn is not None:
        w._zn_delay[:] = delay
        w._zn_hunt = np.zeros(1, dtype=bool)
    return w


def _tick(w):
    w.t += 1
    w._daynight_update()
    return bool(w.pred_asleep[0]), float(w._pred_speed_mult[0]), float(w.dark)


def test_night_calm_wolf_settles_gradually():
    """사슴도 사냥도 없으면 해 진 뒤 δ 업데이트를 넘겨 눕기 시작하고 ramp_steps 동안 속력이 0 으로 내려간 뒤 잠든다. 해 질 녘부터 잠까지
    속력은 단조 감소이고 한 스텝에 많이 떨어지지 않는다(pred_sleep 만 켠 세계는 해 지는 스텝에 0.5 → 0 으로 떨어진다)."""
    w = _night_solo(delay=3)
    R = w._zn["ramp_steps"]
    trace = [_tick(w) for _ in range(150)]          # t = 251..400
    t_sleep = 251 + next(i for i, x in enumerate(trace) if x[0])
    assert 300 + 3 <= t_sleep <= 300 + 3 + R
    sp = [x[1] for x in trace[:t_sleep - 251 + 1]]
    assert all(b <= a + 1e-12 for a, b in zip(sp, sp[1:]))
    assert max(a - b for a, b in zip(sp, sp[1:])) <= 0.5 / R + 1e-9
    assert all(x[0] for x in trace[t_sleep - 251:])          # 밤 동안 그대로 잔다
    old = _night_solo(cfg=load_v2_config(R1_ON))
    tr = [_tick(old) for _ in range(150)]
    drops = [a[1] - b[1] for a, b in zip(tr, tr[1:])]
    assert max(drops) >= 0.49                                 # 지금 세계: 해 지는 스텝에 한 번에 멈춘다


@pytest.mark.parametrize("deer_d, asleep_ever", [(5.0, False), (7.9, False), (8.5, True)])
def test_wolf_with_deer_near_does_not_sleep(deer_d, asleep_ever):
    """settle_r(8) 안에 사슴이 있으면 해가 져도(밤새) 눕지 않고 속력 하한 night_floor(0.5)로 깨어 있다."""
    w = _night_solo(deer_d=deer_d)
    trace = [_tick(w) for _ in range(340)]          # t = 251..590 (밤 300~599)
    assert any(x[0] for x in trace) == asleep_ever
    if not asleep_ever:
        night = [x[1] for x in trace if x[2] >= 0.999]
        assert night and all(abs(v - w._zn["night_floor"]) < 1e-12 for v in night)
        assert w.realism_stats()["block_deer_n"] > 0


def test_hunting_wolf_does_not_sleep_and_settle_aborts():
    """사냥 중(지난 포식자 스텝에 표적·돌진·대치)이면 눕지 않는다. 눕는 중에 사냥이 시작되면 다시 일어나 활동도가 오른다."""
    w = _night_solo()
    w._zn_hunt[:] = True
    trace = [_tick(w) for _ in range(300)]
    assert not any(x[0] for x in trace)
    w = _night_solo(delay=0)
    for _ in range(60):                              # t = 251..310: 눕기 시작
        _tick(w)
    assert w._zn_settle[0] and not w.pred_asleep[0]
    a0 = int(w._zn_act[0])
    w._zn_hunt[:] = True
    _tick(w)
    assert not w._zn_settle[0] and int(w._zn_act[0]) == a0 + 1
    _tick(w)
    assert not w._zn_settle[0] and int(w._zn_act[0]) == a0 + 2
    st = w.realism_stats()
    assert st["settle_n"] == 1.0 and st["settle_abort_n"] == 1.0 and st["block_hunt_n"] > 0
    w._zn_hunt[:] = False
    trace = [_tick(w) for _ in range(60)]
    assert any(x[0] for x in trace)


def test_no_new_hunt_in_full_dark():
    """깜깜하면(d ≥ hunt_dark 1.0) 깨어 있는 주행성 늑대는 새 사냥을 시작하지 않는다(표적도 포획도 없다). 지난 스텝에 사냥 중이던
    늑대는 계속 쫓아 잡는다. 덜 어두우면(d 0.7) 새 사냥을 한다. 야행성 늑대는 늘 사냥한다. 표적 유무는 청각 훅 pred_running 으로 본다."""
    cfg = _rules_cfg("realism_night", "realism_hearing")
    for dark, noct, hunted, can in ((1.0, False, False, False), (1.0, False, True, True), (0.7, False, False, True),
                                    (1.0, True, False, True)):
        w, _ = _solo(cfg, "chaser", 0.3, 0.0, G)
        w.pred_nocturnal[:] = noct
        w.dark = dark
        w._zn_hunt[:] = hunted
        caught = w._step_predators_v3()
        assert bool(caught[0]) == can and bool(w.pred_running[0]) == can, (dark, noct, hunted)
    w, _ = _solo(load_v2_config(R1_ON), "chaser", 0.3, 0.0, G)        # 규칙이 없는 세계: 어둠과 무관(깨어 있으면 사냥)
    w.pred_nocturnal[:] = False
    w.dark = 1.0
    assert w._step_predators_v3()[0]


def test_dawn_wake_taper_and_fresh_state():
    """새벽: d < sleep_dark 가 된 뒤 δ 업데이트를 기다렸다가 깨고 속력이 0 에서 ramp_steps 에 걸쳐 단조 증가한다. reset 때 밤이면 자고
    있고(활동도 0), 낮이면 깨어 있다(활동도 R). 늑대 지연은 세계 시드·슬롯 해시이고 [0, ⌊spread·τ⌋] 이다."""
    w = _night_solo(delay=4)
    for _ in range(200):                             # t = 251..450: 잠들었다
        _tick(w)
    assert w.pred_asleep[0]
    w.t = 590
    trace = [_tick(w) for _ in range(60)]            # t = 591..650 (새벽 s = 600, d < 0.5 는 s ≥ 601)
    t_wake = 591 + next(i for i, x in enumerate(trace) if not x[0])
    assert t_wake == 601 + 4
    sp = [x[1] for x in trace[t_wake - 591:]]
    assert sp[0] > 0.0 and all(b >= a - 1e-12 for a, b in zip(sp, sp[1:]))
    R = w._zn["ramp_steps"]
    d_end = daynight_phase(t_wake + R, 600, 0, 30)[0]
    np.testing.assert_allclose(sp[R], 1.0 - d_end)
    assert w.realism_stats()["wake_n"] == 1.0
    cfg = load_v2_config(REAL["night"])
    for seed in range(32000, 32040):
        x = World(cfg, seeds=[seed])
        diurnal = ~x.pred_nocturnal
        if x.dark >= x._ps["sleep_dark"]:
            assert (x.pred_asleep == diurnal).all() and (x._zn_act[diurnal] == 0).all()
        else:
            assert not x.pred_asleep.any()
        assert (0 <= x._zn_delay).all() and (x._zn_delay <= math.floor(x._zn["spread"] * x.dn_tw)).all()
    d = night_delays(32000, 13, 22)
    np.testing.assert_array_equal(d, night_delays(32000, 13, 22))
    assert d.min() >= 0 and d.max() <= 22 and len(set(d.tolist())) > 3


class _NightSpy(World):
    def _rz_night_update(self, d, diurnal):
        before = self.pred_asleep.copy() if hasattr(self, "_zn_act") and not self._zn_fresh else None
        hunt = self._zn_hunt.copy()
        super()._rz_night_update(d, diurnal)
        if before is not None and self.N:
            onset = ~before & self.pred_asleep
            if onset.any():
                dx = self.pos[:, 0][None, :] - self.pred_pos[:, 0:1]
                dy = self.pos[:, 1][None, :] - self.pred_pos[:, 1:2]
                near = (np.sqrt(dx * dx + dy * dy) <= self._zn["settle_r"]).any(1)
                self.bad_onsets = getattr(self, "bad_onsets", 0) + int(np.count_nonzero(onset & (near | hunt)))
                self.onsets = getattr(self, "onsets", 0) + int(np.count_nonzero(onset))


def test_night_rule_in_runs():
    """세계 롤아웃(무작위 요청, 탐색 시드): 잠드는 순간마다 settle_r 안 사슴이 없고 사냥 중이 아니었다. 실제로 잠들고 깬다."""
    cfg = _with(load_v2_config(REAL["night"]), daynight=dict(periods=[600]))
    onsets = 0
    for seed in (32003, 32004):
        w = _NightSpy(cfg, seeds=[seed])
        pol = _rand(seed)
        for _ in range(1300):
            w.step(pol(w.observe()))
        assert getattr(w, "bad_onsets", 0) == 0
        onsets += getattr(w, "onsets", 0)
        st = w.realism_stats()
        assert 0.0 <= st["dark_awake_frac"] <= 1.0
    assert onsets > 0


class _HuntSpy(World):
    def _step_predators_v3(self):
        blocked = None
        if self.M and self.dark >= self._zn["hunt_dark"]:
            blocked = ~self.pred_nocturnal & ~self.pred_asleep & ~self._zn_hunt
        c = super()._step_predators_v3()
        if blocked is not None:
            self.blocked_n = getattr(self, "blocked_n", 0) + int(np.count_nonzero(blocked))
            self.blocked_hunt = getattr(self, "blocked_hunt", 0) + int(np.count_nonzero(blocked & self._zn_hunt))
            self.blocked_catch = getattr(self, "blocked_catch", 0) + int(np.count_nonzero(
                blocked & (self.pred_cd == int(self.cfg.pred_eat_cd))))
        return c


def test_no_new_hunt_in_full_dark_in_runs():
    """세계 롤아웃(무작위 요청, 탐색 시드): 깜깜할 때(d ≥ hunt_dark) 직전 스텝에 사냥 중이 아니던 깨어 있는 주행성 늑대는 표적도 돌진도
    포획도 없다(새 사냥을 시작하지 않는다)."""
    cfg = _with(load_v2_config(REAL["night"]), daynight=dict(periods=[600]))
    blocked = 0
    for seed in (32043, 32044):
        w = _HuntSpy(cfg, seeds=[seed])
        pol = _rand(seed)
        for _ in range(1300):
            w.step(pol(w.observe()))
        assert getattr(w, "blocked_hunt", 0) == 0 and getattr(w, "blocked_catch", 0) == 0
        blocked += getattr(w, "blocked_n", 0)
    assert blocked > 0


# --------------------------------------------------------------------- #
# 관측 범위·롤아웃·도구
# --------------------------------------------------------------------- #


def test_obs_stay_in_training_ranges():
    """모두 켠 세계(R_base 손 규칙, 탐색 시드): 관측은 [0, 1], 감지된 위협의 실거리 ≤ 그 사슴의 탐지 반경(see_r × visibility × 행동
    배수) — 학습 때의 결합 범위(cap_to_sight)가 지켜진다."""
    cfg = load_v2_config(REAL["all"])
    w = World(cfg, seeds=[32005])
    pol = ro.build_policy(rr.rule_spec(cfg, 4.0, 0.9), 0)
    ro.forward_bind(pol, w)
    names = list(w.obs_names)
    heard = 0
    for _ in range(600):
        o = w.observe()
        assert o.min() >= 0.0 and o.max() <= 1.0
        seen = o[:, names.index("pred_count")] > 0
        lim = w._see_pred * w._rep_see
        assert (w._g["d_pred_min"][seen] <= lim[seen] + 1e-9).all()
        w.step(np.asarray(pol(o), dtype=np.float64))
        heard += int(np.count_nonzero(w._g["rz_heard"]))
    assert heard > 0


def test_rollout_rows_carry_realism_columns_only_when_on():
    spec = {"kind": "fixed", "action": [0.0]}
    r_on = ro.rollout(load_v2_config(REAL["all"]), ro.build_policy(spec), 32006, 120)
    r_off = ro.rollout(load_v2_config(R1_ON), ro.build_policy(spec), 32006, 120)
    assert set(ro.REALISM_COLUMNS) <= set(r_on) and not set(ro.REALISM_COLUMNS) & set(r_off)
    assert tuple(ro.REALISM_COLUMNS) == REALISM_STAT_COLUMNS
    json.dumps(ro.public_row(r_on))
    with pytest.raises(ValueError, match="realism"):
        World(load_v2_config(R1_ON), seeds=[32009]).realism_stats()


def test_r1_model_binds_to_realism_world():
    """관측 18칸·마스크 판 2 가 그대로라 출시 두뇌 R1b 를 재학습 없이 현실성 세계에 얹을 수 있다(판정은 아직 하지 않았다)."""
    if not R1_MODEL.exists():
        pytest.skip("R1b 모델 없음")
    pol = ro.build_policy({"kind": "rep_learned", "path": str(R1_MODEL)}, 0)
    w = World(load_v2_config(REAL["all"]), seeds=[32007])
    ro.forward_bind(pol, w)
    for _ in range(20):
        w.step(np.asarray(pol(w.observe()), dtype=np.float64))


def test_golden_exporters_refuse_realism_worlds(tmp_path):
    """C++ 골든 도구는 현실성 세계를 받지 않는다(C++ 에 아직 없는 규칙이다)."""
    import export_golden_v3_threat as egt

    with pytest.raises(SystemExit, match="realism"):
        egt.cfg_constants(load_v2_config(REAL["all"]))
    egt.cfg_constants(load_v2_config(R1_ON))
    if R1_MODEL.exists():
        import export_golden_v3_world as egw

        with pytest.raises(SystemExit, match="realism"):
            egw.export(R1_MODEL, REAL["night"], tmp_path)


# --------------------------------------------------------------------- #
# 세로 장애물 확장 지점 (구현 없음)
# --------------------------------------------------------------------- #


def test_obstacle_extension_point_is_empty():
    """현실성 1단계 세계에는 세로 장애물이 없다: World.obstacles 는 늘 (0, 3) [x, y, r], 끈 블록은 받아들인다(v3_real1_on 에 자리 블록이 있다).
    기능 obstacles 는 야생 2단계 3(10-17)에서 구현했다 — 계수 없이 켜면 읽을 때 실패한다(정의·시험은 tests/test_wild2_obstacle.py)."""
    assert OBSTACLE_COLUMNS == ("x", "y", "r") and F.FEATURE_IDS["obstacles"] == 12
    for path in (R1_ON, R2_ON, REAL["all"]):
        w = World(load_v2_config(path), seeds=[32008])
        assert w.obstacles.shape == (0, 3) and w.obstacles.dtype == np.float64
        w.step(np.zeros((w.N, 1)))
        w.reset()
        assert w.obstacles.shape == (0, 3)
    with pytest.raises(ValueError, match="계수"):
        F.parse_features({"obstacles": {"enabled": True}})
    assert not F.parse_features({"obstacles": {"enabled": False}}).enabled("obstacles")
    assert load_v2_config(REAL["all"]).v2["features"]["obstacles"] == {"enabled": False}
