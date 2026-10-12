"""v3 R2 — 노려보기 대치(stare_down, 기능 17, M7)와 동족 경보 전염(alarm, 기능 18, M8) (명세 Docs/RL_Policy/RL_V3_R2_SPEC.md 8절,
사전 등록 results/v3/r2/PREREG.md).

비트 동일과 결정성(B1~B8): R2 이전 코드(커밋 7bb474a 를 git archive 로 푼 사본)와 같은 궤적·통계·config digest, 두 기능을 끈 관문
설정 = v3_r1_on, 중립 값 = 끈 세계, FREEZE 없는 집단 = 끈 세계, 기능 스트림 없음, rep_peek 순수성, deepcopy·pickle, 마스크 판.
M7 단위 시험(잠금 대상·추적 가능·S 조건표·대치 → 물러남·깨지면 같은 스텝에 돌진·물러남 방향과 벽·대치·물러남은 잡지 않음·플레이어
들킴과 들킨 돌진). M8 단위 시험(방출 조건·사전식 선택·ttl·약한 경보 무시·E7·방향·비명·리스폰·alarm_heard·마스크 판 3·소문이
꺼짐). 통계·롤아웃 열, 손 규칙(stare·look·보조 규칙·FSM_R2), 관문 도구 smoke(시드 31000~31001 × 200스텝, 판정 시드가 아니다),
결정적 확인표 도구.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import importlib.util
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
from env_v2.world import (ALARM_STAT_COLUMNS, PM_CHARGE, PM_REST, PM_STALK, PM_WANDER, PT_CHASER, PT_PLAYER, PT_STALKER,
                          ST_BALK, ST_EXHAUST, ST_POUNCE, ST_ROAM, ST_STANDOFF, STARE_STAT_COLUMNS, World, obs_names)

V3R1 = ROOT / "configs" / "v3_r1.yaml"
V3R1_ON = ROOT / "configs" / "v3_r1_on.yaml"
W7 = ROOT / "configs" / "v3_r2_w7_on.yaml"
W8 = ROOT / "configs" / "v3_r2_w8_on.yaml"
BASE_COMMIT = "7bb474a"              # R2 구현 직전 커밋(사람 확인 10-12 기록) — 비트 동일 기준
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
G, F_, H, Z, S = rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP
STARE_BLOCK = dict(enabled=True, target_lock=True, spot_r=10.0, spot_cos=0.866, spot_steps=6, balk_steps=45, balk_speed=0.6,
                   spotted_steps=45, spotted_charge_speed=0.9)
ALARM_BLOCK = dict(enabled=True, alarm_r=8.0, alarm_steps=15, max_hop=2, hop_gain=0.6, relay_window=30, event_alarm=0.4,
                   on_catch=True)
KEYS = ("pos", "head", "energy", "pred_pos", "pred_head", "food", "vel", "pred_cd", "behavior", "beh_phase", "beh_steps",
        "beh_seq", "stalk_state", "player_mode")
STATS = ("stats", "gait_stats", "daynight_stats", "pred_sleep_stats", "repertoire_stats", "threats_stats")

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


@pytest.fixture(scope="module")
def c7():
    return load_v2_config(W7)


@pytest.fixture(scope="module")
def c8():
    return load_v2_config(W8)


@pytest.fixture(scope="module")
def c1():
    return load_v2_config(V3R1_ON)


def _feat(cfg, name, **kw):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    f[name] = dict(f[name], **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _same(d1, d2):
    assert d1.keys() == d2.keys()
    for k in d1:
        a, b = d1[k], d2[k]
        assert a == b or (isinstance(a, float) and math.isnan(a) and math.isnan(b)), k


def _rand(seed):
    rng = np.random.default_rng(seed)
    return lambda obs: rng.integers(0, 5, (len(obs), 1)).astype(np.float64)


def _run_pair(wa, wb, pa, pb, steps=300, obs_cols=None):
    for _ in range(steps):
        oa, ob = wa.observe(), wb.observe()
        np.testing.assert_array_equal(oa if obs_cols is None else oa[:, :obs_cols], ob)
        ra, rb = wa.step(pa(oa if obs_cols is None else oa[:, :obs_cols])), wb.step(pb(ob))
        for i, (x, y) in enumerate(zip(ra, rb)):
            np.testing.assert_array_equal(x if (obs_cols is None or i in (1, 2)) else x[:, :obs_cols], y)
    for name in STATS:
        _same(getattr(wa, name)(), getattr(wb, name)())
    for k in KEYS:
        np.testing.assert_array_equal(getattr(wa, k), getattr(wb, k), err_msg=k)
    assert wa.rng.bit_generator.state == wb.rng.bit_generator.state


# --------------------------------------------------------------------- #
# 설정·등록부
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("path, name, block, version", [(W7, "stare_down", STARE_BLOCK, "3.r2w7"),
                                                        (W8, "alarm", ALARM_BLOCK, "3.r2w8")], ids=["w7", "w8"])
def test_gate_configs_are_r1_on_plus_one_block(path, name, block, version):
    """관문 세계 = v3_r1_on + 장치 하나(명세 2-4·3-5 값) + version. 그 밖의 키는 그대로다(사전 등록 1절)."""
    a = yaml.safe_load(path.read_text(encoding="utf-8"))
    b = yaml.safe_load(V3R1_ON.read_text(encoding="utf-8"))
    assert a["version"] == version and b["version"] == "3.r1"
    assert {k: v for k, v in a.items() if k not in ("version", "features")} == \
        {k: v for k, v in b.items() if k not in ("version", "features")}
    assert {k: v for k, v in a["features"].items() if k != name} == b["features"]
    assert a["features"][name] == block
    w = World(load_v2_config(path), seeds=[31000])
    assert w.features.active[-1] == name
    want = obs_names(load_v2_config(V3R1_ON)) + (("alarm_heard",) if name == "alarm" else ())
    assert w.obs_names == want and w.obs_dim == len(want)


def test_registry():
    assert F.FEATURE_IDS["stare_down"] == 17 and F.FEATURE_IDS["alarm"] == 18
    assert {"stare_down", "alarm"} <= F.IMPLEMENTED
    assert F.PARAM_KEYS["stare_down"] == frozenset(STARE_BLOCK) - {"enabled"}
    assert F.PARAM_KEYS["alarm"] == frozenset(ALARM_BLOCK) - {"enabled"}


@pytest.mark.parametrize("name, kw, match", [
    ("stare_down", dict(target_lock=1), "target_lock"),
    ("stare_down", dict(spot_r=-1.0), "spot_r"),
    ("stare_down", dict(spot_cos=0.0), "spot_cos"),
    ("stare_down", dict(spot_cos=1.5), "spot_cos"),
    ("stare_down", dict(spot_steps=0), "spot_steps"),
    ("stare_down", dict(spot_steps=2.5), "spot_steps"),
    ("stare_down", dict(balk_steps=-1), "balk_steps"),
    ("stare_down", dict(balk_speed=-0.1), "balk_speed"),
    ("stare_down", dict(spotted_steps=-1), "spotted_steps"),
    ("stare_down", dict(spotted_charge_speed=-0.1), "spotted_charge_speed"),
    ("alarm", dict(alarm_r=-1.0), "alarm_r"),
    ("alarm", dict(alarm_steps=0), "alarm_steps"),
    ("alarm", dict(max_hop=-1), "max_hop"),
    ("alarm", dict(max_hop=255), "max_hop"),
    ("alarm", dict(relay_window=-1), "relay_window"),
    ("alarm", dict(hop_gain=0.0), "hop_gain"),
    ("alarm", dict(hop_gain=1.5), "hop_gain"),
    ("alarm", dict(event_alarm=1.5), "event_alarm"),
    ("alarm", dict(on_catch=1), "on_catch"),
])
def test_params_are_checked(c7, c8, name, kw, match):
    cfg = c7 if name == "stare_down" else c8
    with pytest.raises(ValueError, match=match):
        World(_feat(cfg, name, **kw), seeds=[0])


def test_prerequisites_and_missing_coefficients(c7, c8, tmp_path):
    with pytest.raises(ValueError, match="repertoire·threats"):
        World(_feat(c7, "threats", enabled=False), seeds=[0])
    with pytest.raises(ValueError, match="repertoire"):
        World(_feat(_feat(c8, "repertoire", enabled=False), "threats", enabled=True), seeds=[0])
    for path, name, key in ((W7, "stare_down", "spot_steps"), (W8, "alarm", "relay_window")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        del raw["features"][name][key]
        p = tmp_path / f"{name}_missing.yaml"
        p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
        with pytest.raises(ValueError, match=key):
            load_v2_config(p)
    raw = yaml.safe_load(W8.read_text(encoding="utf-8"))
    raw["features"]["alarm"]["typo_key"] = 1.0
    p = tmp_path / "alarm_typo.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="typo_key"):
        load_v2_config(p)
    # 관측 칸은 obs_extra 가 true 일 때만 붙는다
    w = World(_feat(c8, "repertoire", obs_extra=False), seeds=[0])
    assert "alarm_heard" not in w.obs_names and w._al is not None and w.obs_dim == 9


# --------------------------------------------------------------------- #
# 비트 동일 (B1~B5)
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
    if job.get("off"):
        f = {k: dict(v) for k, v in cfg.v2["features"].items()}
        for n in job["off"]:
            f[n] = dict(f[n], enabled=False)
        cfg = cfg.replace(v2=dict(cfg.v2, features=f))
    w = World(cfg, seeds=[job["seed"]])
    kind = job["policy"]
    if kind == "rand":
        rng = np.random.default_rng(job["seed"] + 7)
        pol = lambda o: rng.integers(0, 5, (len(o), 1)).astype(np.float64)
    elif kind == "urand":                   # 연속 행동 세계(v2): [0, 1) 균등
        rng = np.random.default_rng(job["seed"] + 7)
        pol = lambda o: rng.random((len(o), w.act_dim))
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
    """R2 이전 코드(BASE_COMMIT)의 herbivore_rl 일부를 tmp 에 푼다. git 이나 커밋이 없으면 None."""
    paths = [f"herbivore_rl/{p}" for p in ("env", "env_v2", "policies", "configs", "repertoire_rules.py")]
    try:
        out = subprocess.run(["git", "archive", BASE_COMMIT] + paths, cwd=ROOT.parent, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    with tarfile.open(fileobj=io.BytesIO(out.stdout)) as tf:
        tf.extractall(tmp_path / "base", **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return tmp_path / "base" / "herbivore_rl"


def test_bit_identical_to_pre_r2_code(tmp_path):
    """B1: 기존 세계(v3_r1_on·v3_r1·v3_r0_on·v2_4s_on·v2)와 두 기능을 끈 관문 설정은 R2 이전 코드와 궤적(스텝마다 관측·행동·보상·
    사망·terminal_obs·상태 지문)·통계·v1 난수 상태·관측 이름·기능 스트림·config digest 가 같다. R1 모델(판 2)의 판정 롤아웃도 같다."""
    old_root = _archive(tmp_path)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(TRACE_SRC % dict(keys=KEYS, stats=STATS), encoding="utf-8")
    old, new = [], []
    for cfg in ("configs/v3_r1_on.yaml", "configs/v3_r1.yaml", "configs/v3_r0_on.yaml", "configs/v2_4s_on.yaml", "configs/v2.yaml"):
        pols = ("rand", "rbase") if "r1" in cfg else (("rand",) if "v3_" in cfg else ("urand",))
        for pol in pols:
            j = dict(config=cfg, seed=31000, steps=250, policy=pol)
            old.append(j)
            new.append(j)
    for name, off in (("w7", ["stare_down"]), ("w8", ["alarm"])):
        for pol, seed in (("rand", 31001), ("rbase", 31002)):
            old.append(dict(config="configs/v3_r1_on.yaml", seed=seed, steps=250, policy=pol))
            new.append(dict(config=f"configs/v3_r2_{name}_on.yaml", off=off, seed=seed, steps=250, policy=pol))
    if R1_MODEL.exists():
        for cfg, off in (("configs/v3_r1_on.yaml", None), ("configs/v3_r2_w8_on.yaml", ["alarm"])):
            old.append(dict(config="configs/v3_r1_on.yaml", seed=31003, steps=200, policy="model", model=str(R1_MODEL)))
            new.append(dict(config=cfg, off=off, seed=31003, steps=200, policy="model", model=str(R1_MODEL)))
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
        if not j.get("off"):
            assert a["digest"] == b["digest"], j                   # v3_r1·v3_r0 yaml 의 config digest 는 그대로다


@pytest.mark.parametrize("path, name", [(W7, "stare_down"), (W8, "alarm")], ids=["w7", "w8"])
@pytest.mark.parametrize("pol", ["rand", "rbase"])
def test_feature_off_equals_r1_on(c1, path, name, pol):
    """B1 (같은 프로세스): 관문 설정에서 그 장치만 끄면 v3_r1_on 과 비트 동일이고 그 기능의 스트림이 없다."""
    off = _feat(load_v2_config(path), name, enabled=False)
    wa, wb = World(off, seeds=[31004]), World(c1, seeds=[31004])
    assert wa._sd is None and wa._al is None and wa.obs_names == wb.obs_names
    if pol == "rand":
        pa, pb = _rand(3), _rand(3)
    else:
        pa, pb = (ro.build_policy(rr.rule_spec(c, 4.0, 0.9), 0) for c in (off, c1))
    _run_pair(wa, wb, pa, pb, 250)


def test_m7_neutral_equals_off(c7):
    """B2: M7 중립(spot_r 0, target_lock false) = M7 끔 — FREEZE 를 많이 쓰는 무작위 요청에서도 비트 동일."""
    neutral = _feat(c7, "stare_down", spot_r=0.0, target_lock=False)
    wa, wb = World(neutral, seeds=[31005]), World(_feat(c7, "stare_down", enabled=False), seeds=[31005])
    _run_pair(wa, wb, _rand(5), _rand(5), 300)
    assert wa.stare_stats()["standoff_n"] == 0.0 and wa._sd_lock_n > 0       # 잠금 기록은 했다(동역학 무관)


def test_m7_without_freeze_equals_off(c7):
    """B3: M7(target_lock false, spot_r 10)에서 FREEZE 를 쓰지 않는 집단(R_base) = M7 끔. 장치는 FREEZE 없이 아무것도 바꾸지 않는다."""
    cfg = _feat(c7, "stare_down", target_lock=False)
    off = _feat(c7, "stare_down", enabled=False)
    wa, wb = World(cfg, seeds=[31006]), World(off, seeds=[31006])
    pa, pb = (ro.build_policy(rr.rule_spec(c, 4.0, 0.9), 0) for c in (cfg, off))
    _run_pair(wa, wb, pa, pb, 300)
    assert (wa.behavior != Z).all()


def test_m8_neutral_equals_off_dynamics(c8):
    """B4: M8 중립(alarm_r 0, on_catch false) = M8 끔의 동역학 — 관측 앞 18칸이 같고 alarm_heard 칸은 0, E7 0회, 마스크도 같다."""
    neutral = _feat(c8, "alarm", alarm_r=0.0, on_catch=False)
    off = _feat(c8, "alarm", enabled=False)
    wa, wb = World(neutral, seeds=[31007]), World(off, seeds=[31007])
    assert wa.obs_dim == 19 and wb.obs_dim == 18 and not wa._al["active"]
    ra, rb = _rand(8), _rand(8)
    for _ in range(300):
        oa, ob = wa.observe(), wb.observe()
        np.testing.assert_array_equal(oa[:, :18], ob)
        assert (oa[:, 18] == 0.0).all()
        np.testing.assert_array_equal(rp.feasible_mask(oa, wa.obs_names), rp.feasible_mask(ob, wb.obs_names))
        xa, xb = wa.step(ra(oa)), wb.step(rb(ob))
        for i in (1, 2):
            np.testing.assert_array_equal(xa[i], xb[i])
    for k in KEYS:
        np.testing.assert_array_equal(getattr(wa, k), getattr(wb, k), err_msg=k)
    s = wa.alarm_stats()
    assert s["e7_n"] == 0.0 and s["emit_h0"] == 0.0 and not wa.alarm_e7.any()


def test_features_make_no_streams(c7, c8, monkeypatch):
    """B5: stare_down·alarm 은 기능 스트림을 만들지 않는다(스트림 생성을 직접 기록). threats·daynight·pred_sleep 스트림만 생긴다."""
    import env_v2.world as wm

    seen = []
    real = wm.feature_stream

    def spy(seed, name, part=0):
        seen.append((name, int(part)))
        return real(seed, name, part)

    monkeypatch.setattr(wm, "feature_stream", spy)
    for cfg in (c7, c8, _feat(c7, "threats", player_frac=1.0)):
        w = World(cfg, seeds=[31008])
        pol = _rand(9)
        for _ in range(300):
            w.step(pol(w.observe()))
    assert {n for n, _ in seen} <= {"daynight", "pred_sleep", "threats"}


def test_v1_stream_shape_with_stare(c7):
    """B5: M7 이 대치·물러남을 일으키는 세계에서도 _step_predators_v3 의 v1 스트림 소비는 v2.4s 모양이다(선회 M_base 개 + 원거리
    판정 (M_base, N) 개)."""
    cfg = _feat(c7, "threats", player_frac=1.0, stalk_frac=[0.7, 0.7])
    hit = 0
    for seed in (31009, 31010):
        w = World(cfg, seeds=[seed])
        rng = np.random.default_rng(seed)
        for t in range(300):
            if t % 25 == 24:
                probe = copy.deepcopy(w.rng)
                probe.uniform(-w.cfg.pred_wander_turn, w.cfg.pred_wander_turn, w.M_base)
                if w._pred_ranged_v1[:w.M_base].any():
                    probe.random((w.M_base, w.N))
                w._step_predators_v3()
                assert w.rng.bit_generator.state == probe.bit_generator.state, (seed, t)
            req = np.where(rng.random((w.N, 1)) < 0.5, float(Z), float(G))
            w.step(req)
            hit += int(np.isin(w.stalk_state, (ST_STANDOFF, ST_BALK)).any())
    assert hit > 0                                                          # 대치·물러남이 실제로 지나갔다


# --------------------------------------------------------------------- #
# B6·B7·B8 — 미리 보기, 복제, 마스크 판
# --------------------------------------------------------------------- #


class _Capture(World):
    def _rep_step(self, a):
        v, out = super()._rep_step(a)
        self.last_decide = out["decide"].copy()
        return v, out


def test_rep_peek_pure_with_alarm_new(c8):
    """B6: alarm_new 가 있는 상태에서도 rep_peek 의 reads = 실제 arbitrate 의 decide 이고, peek 을 부르든 부르지 않든 궤적이 같다."""
    wa, wb = _Capture(c8, seeds=[31011]), World(c8, seeds=[31011])
    ra, rb = _rand(11), _rand(11)
    n_new = 0
    for _ in range(300):
        n_new += int(wa._rs.alarm_new.sum())
        st = {k: np.array(v, copy=True) for k, v in vars(wa._rs).items()}
        pk = wa.rep_peek()
        for k, v in vars(wa._rs).items():
            np.testing.assert_array_equal(v, st[k], err_msg=k)
        oa, ob = wa.observe(), wb.observe()
        np.testing.assert_array_equal(oa, ob)
        xa, xb = wa.step(ra(oa)), wb.step(rb(ob))
        for x, y in zip(xa, xb):
            np.testing.assert_array_equal(x, y)
        np.testing.assert_array_equal(pk["reads"], wa.last_decide)
    assert n_new > 0 and wa.alarm_stats()["e7_n"] > 0


@pytest.mark.parametrize("path", [W7, W8], ids=["w7", "w8"])
def test_deterministic_and_copyable(path):
    """B7: 같은 시드·요청이면 같은 궤적, deepcopy·pickle 한 세계도 같은 궤적·통계를 낸다."""
    cfg = _feat(load_v2_config(path), "threats", player_frac=1.0)
    a, b = World(cfg, seeds=[31012]), World(cfg, seeds=[31012])
    pa, pb = _rand(12), _rand(12)
    for _ in range(200):
        xa, xb = a.step(pa(a.observe())), b.step(pb(b.observe()))
        for x, y in zip(xa, xb):
            np.testing.assert_array_equal(x, y)
    clones = [pickle.loads(pickle.dumps(a)), copy.deepcopy(a)]
    rng = np.random.default_rng(13)
    for _ in range(150):
        act = rng.integers(0, 5, (a.N, 1)).astype(np.float64)
        ra = a.step(act)
        for c in clones:
            for x, y in zip(c.step(act), ra):
                np.testing.assert_array_equal(x, y)
    name = "stare_stats" if a._sd is not None else "alarm_stats"
    for c in clones:
        _same(getattr(c, name)(), getattr(a, name)())
        _same(c.threats_stats(), a.threats_stats())


def test_mask_version_by_obs_names(c1, c8):
    """마스크 판은 관측 이름으로 정한다: alarm_heard 가 있으면 3, 없으면 2. 판 2 세계의 마스크는 그대로다."""
    assert rp.MASK_VERSION == 2 and rp.MASK_VERSION_ALARM == 3 and rp.ALARM_MASK_OBS == 0.4
    assert rp.mask_version_of(World(c1, seeds=[0]).obs_names) == 2
    assert rp.mask_version_of(World(c8, seeds=[0]).obs_names) == 3
    assert rp.mask_version_of(World(load_v2_config(W7), seeds=[0]).obs_names) == 2
    assert rep.OWN_RECENCY == rp.THREAT_RECENCY_OBS
    with pytest.raises(ValueError, match="마스크 판"):
        rp.check_mask_version(2, World(c8, seeds=[0]).obs_names)
    with pytest.raises(ValueError, match="마스크 판"):
        rp.check_mask_version(3, World(c1, seeds=[0]).obs_names)


def test_r1_model_refused_on_alarm_world(c1, c8):
    """B8: 판 2 모델(R1)은 v3_r1_on 에서 판정되고 경보 세계(판 3)에서는 거부된다. 경보 세계에서 만든 모델은 판 3 을 저장하고
    경보가 없는 세계에서 거부된다."""
    import train_v3
    from env_v2.vec_env import MultiWorldVecEnv

    v1 = MultiWorldVecEnv(load_v2_config(V3R1), num_worlds=1, seeds=range(100, 104), meta_seed=0)
    m1 = train_v3.make_model_rep(v1, rp.rep_params(load_v2_config(V3R1)), None, n_steps=8, seed=0, batch_size=128)
    v1.close()
    assert m1.policy.rep_mask_version == 2
    ro.RepLearned(m1).bind_world(World(c1, seeds=[0]))
    with pytest.raises(ValueError, match="마스크 판 2 이 이 세계의 마스크 판 3"):
        ro.RepLearned(m1).bind_world(World(c8, seeds=[0]))
    v8 = MultiWorldVecEnv(c8, num_worlds=1, seeds=range(100, 104), meta_seed=0)
    assert v8.obs_dim == 19 and v8.policy_obs_dim == 24
    m8 = train_v3.make_model_rep(v8, rp.rep_params(c8), None, n_steps=8, seed=0, batch_size=128)
    v8.close()
    assert m8.policy.rep_mask_version == 3
    ro.RepLearned(m8).bind_world(World(c8, seeds=[0]))
    with pytest.raises(ValueError, match="마스크 판 3"):
        ro.RepLearned(m8).bind_world(World(c1, seeds=[0]))
    if R1_MODEL.exists():
        pol = ro.build_policy({"kind": "rep_learned", "path": str(R1_MODEL)}, 0)
        with pytest.raises(ValueError, match="R1 모델"):
            ro.forward_bind(pol, World(c8, seeds=[0]))


# --------------------------------------------------------------------- #
# M7 단위 시험 — 개체 0 과 위협 하나 하네스
# --------------------------------------------------------------------- #


def _solo(cfg, kind="stalker", d0=8.0, beh0=Z, prelock=True, seed=12000, angle=0.0, night=False):
    """개체 0 은 맵 가운데, 위협은 −x 쪽 실거리 d0 에서 +x 를 본다. 개체 0 은 위협 쪽에서 angle 도 돌린 쪽을 본다. 나머지는 구석.
    잠행 위협은 개체 0 을 잠근 채로 시작한다(prelock). 위협의 지난 이동은 0, 사건 기준값은 지금 상태."""
    w = World(cfg, seeds=[seed])
    if night:
        w.day_fixed = False
        w.dn_period, w.dn_offset = 600, 450
    else:
        w.day_fixed = True
    w._daynight_update()
    w.cov_c, w.cov_r = np.zeros((0, 2)), np.zeros(0)
    w.food[:] = 1.0
    w.food_cap[:] = 1.0
    c = np.array([w.size / 2, w.size / 2])
    w.pos[:] = [1.0, 1.0]
    w.pos[0] = c
    a = math.radians(180.0 + angle)
    w.head[0] = [math.cos(a), math.sin(a)]
    player = kind == "player"
    w.M, w.M_base = 1, 0 if player else 1
    w.pred_pos = np.array([c + [-d0, 0.0]])
    w.pred_head = np.array([[1.0, 0.0]])
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
    w._stare_reset()
    if prelock and kind in ("stalker", "player"):
        w.pred_lock[0] = 0
    rs, rp_ = w._rs, w._rp
    rs.behavior[:] = G
    rs.behavior[0] = beh0
    rs.lock_left[:] = 0
    rs.jitter[:] = 0
    rs.prev_pc[:] = 0
    rs.prev_near[:] = False
    rs.prev_fast[:] = False
    rs.prev_dark[:] = w.dark >= rp_["event_dark"]
    w._rep_see[:] = rp_["graze_head_down"]
    w._rep_see[0] = w._rep_see_last[0] = rp_["graze_head_down"] if beh0 == G else 1.0
    w._rep_still[:] = False
    w._rep_still[0] = beh0 in (Z, S)
    w._rep_cover[:] = 1.0
    w._rep_crouch[:] = False
    w._g = w._geometry()
    rep.perceive(rs, rp_, w._g)
    w._obs = w._obs_from(w._g)
    return w, c


def _req(w, b0):
    r = np.full((w.N, 1), float(G))
    r[0, 0] = b0
    return r


def _pred_only(w):
    """위협 스텝만(_step_predators_v3) 한 번. 초식 행동·위치는 하네스가 정한 그대로다."""
    return w._step_predators_v3()


def test_lock_targets_only_creeping_threats(c7):
    """잠그는 위협은 잠행형의 잠행 단계와 플레이어의 잠행 모드뿐이다. 추격형·돌진·탈진·배회 모드는 잠그지 않는다."""
    w, _ = _solo(c7, "stalker", 8.0, G, prelock=False)
    _pred_only(w)
    assert w.pred_lock[0] == 0 and w.stalk_state[0] == ST_ROAM
    w, _ = _solo(c7, "chaser", 8.0, G, prelock=False)
    _pred_only(w)
    assert w.pred_lock[0] == -1
    w, _ = _solo(c7, "stalker", 8.0, G, prelock=False)
    w.stalk_state[0], w.stalk_left[0] = ST_POUNCE, 5
    _pred_only(w)
    assert w.pred_lock[0] == -1
    w, _ = _solo(c7, "stalker", 8.0, G, prelock=True)
    w.stalk_state[0], w.stalk_left[0] = ST_EXHAUST, 5
    _pred_only(w)
    assert w.pred_lock[0] == -1                                             # 잠행이 아니면 잠금을 지운다
    w, _ = _solo(c7, "player", 8.0, G, prelock=False)
    w.player_mode[0] = PM_WANDER
    _pred_only(w)
    assert w.pred_lock[0] == -1
    w, _ = _solo(c7, "player", 8.0, G, prelock=False)
    _pred_only(w)
    assert w.pred_lock[0] == 0
    w, _ = _solo(c7, "stalker", 5.0, G, prelock=False)                     # 돌진 시작은 잠금을 지운다
    _pred_only(w)
    assert w.stalk_state[0] == ST_POUNCE and w.pred_lock[0] == -1


@pytest.mark.parametrize("case, kept", [
    ("near", True), ("far", False), ("fov_in", True), ("fov_out", False),
    ("crouch", False), ("sleep", False), ("freeze_cover", True), ("graze_cover", True),
])
def test_trackable(c7, case, kept):
    """추적 가능: 잠행형 실거리 ≤ 14 & 시야각 150° 안, 표적이 웅크림·SLEEP 이 아니다. 은신처 안 FREEZE·GRAZE 는 끊지 않는다.
    (끊긴 뒤 다시 고르지 못하는 배치라 잠금 −1 이 '끊김'이다.)"""
    d = {"far": 14.05}.get(case, 7.9)
    beh = {"sleep": S, "freeze_cover": Z, "crouch": H, "graze_cover": G}.get(case, Z)
    w, c = _solo(c7, "stalker", d, beh)
    if case.startswith("fov"):
        ang = math.radians(70.0 if case == "fov_in" else 80.0)
        w.pred_head[0] = [math.cos(ang), math.sin(ang)]                    # 위협 → 개체 방향(+x)에서 70°·80°
    if case == "crouch":
        w._rs.arrived[0] = True
        w._rep_crouch[0] = True
        w._rep_still[0] = True
    if case in ("crouch", "freeze_cover", "graze_cover"):
        w.cov_c, w.cov_r = np.array([c]), np.array([1.5])
        w._rep_cover[0] = rep.cover_mult(w._rp, np.array([beh]), np.array([case == "crouch"]))[0]
    if case == "sleep":
        w._rep_still[0] = True
    _pred_only(w)
    if kept:                                # 끊기지 않았다(다시 잠근 것도 아니다 — 새 잠금 수 0)
        assert w.pred_lock[0] == 0 and w._sd_lock_n == 0, case
    else:                                   # 끊겼다(다시 고르지 못하는 배치라 −1, 또는 새로 잠금)
        assert w.pred_lock[0] == -1 or w._sd_lock_n == 1, case


def test_respawn_clears_lock_and_standoff(c7):
    w, _ = _solo(c7, "stalker", 8.0, Z)
    _pred_only(w)
    assert w.stalk_state[0] == ST_STANDOFF and w.pred_lock[0] == 0 and w.spot_cnt[0] == 1
    w._respawn(np.array([0]))
    assert w.pred_lock[0] == -1 and w.stalk_state[0] == ST_ROAM and w.spot_cnt[0] == 0


@pytest.mark.parametrize("case, standoff", [
    ("freeze", True), ("graze", False), ("hide", False), ("cos_in", True), ("cos_out", False),
    ("r_in", True), ("r_out", False), ("pounce_range", False), ("past_pounce", True),
    ("cooldown", False), ("asleep", False), ("night_r", False), ("day_r", True),
])
def test_stare_condition_table(c7, case, standoff):
    """S 조건표 (명세 2-2): FREEZE 만, 눈맞춤 cos ≥ 0.866(±30°), 실거리 ≤ min(spot_r, 표적의 지금 탐지 반경), 체감 거리 >
    돌진 거리(얼어 있으면 실거리 > 3.33), 쿨다운 0·깨어 있음. 밤 탐지 반경 10 은 spot_r 12 에서도 묶는다."""
    cfg = c7
    d, angle, beh, night = 8.0, 0.0, Z, False
    if case == "graze":
        beh = G
    elif case == "hide":
        beh = H
    elif case in ("cos_in", "cos_out"):
        angle = 29.5 if case == "cos_in" else 30.5
    elif case in ("r_in", "r_out"):
        d = 9.99 if case == "r_in" else 10.01
    elif case == "pounce_range":
        d = 3.3
    elif case == "past_pounce":
        d = 3.4
    elif case in ("night_r", "day_r"):
        cfg, d, night = _feat(c7, "stare_down", spot_r=12.0), 11.0, case == "night_r"
    w, _ = _solo(cfg, "stalker", d, beh, angle=angle, night=night)
    if case == "cooldown":
        w.pred_cd[0] = 3
    if case == "asleep":
        w.pred_nocturnal[0] = False
        w.pred_asleep[0] = True
    _pred_only(w)
    assert bool(w.stalk_state[0] == ST_STANDOFF) is standoff, (case, w.stalk_state[0])
    assert bool(w.stare_by[0] == 0) is standoff
    if case == "pounce_range":
        assert w.stalk_state[0] == ST_POUNCE                                # 돌진 거리 안: 노려보기로 멈출 수 없다


def test_standoff_then_balk_then_roam(c7):
    """정확히 spot_steps(6)째 스텝에 물러남: 멈춤 5스텝(속력 0, 표적 쪽), 6스텝째부터 balk_speed × herb_speed 로 포식자 − 표적 쪽.
    balk_steps(45) 동안 걸어 나간 뒤 배회. 물러남은 잠금을 지운다."""
    w, c = _solo(c7, "stalker", 8.0, Z)
    hs = w.cfg.herb_speed
    states, speeds = [], []
    for _ in range(60):
        w.step(_req(w, Z))
        states.append(int(w.stalk_state[0]))
        speeds.append(float(np.linalg.norm(w.pred_vel[0])))
    assert states[:5] == [ST_STANDOFF] * 5 and speeds[:5] == [0.0] * 5
    assert states[5] == ST_BALK and speeds[5] == pytest.approx(0.6 * hs)
    # 물러남 이동 45스텝(스텝 5~49) — 마지막 이동 스텝 끝에 배회로 돌아온다
    assert states[5:49] == [ST_BALK] * 44 and states[49] == ST_ROAM
    assert all(v == pytest.approx(0.6 * hs) for v in speeds[5:50])
    assert np.allclose(w.balk_dir[0], [-1.0, 0.0]) and w.pred_lock[0] in (-1, 0)
    s = w.stare_stats()
    assert s["standoff_n"] == 1.0 and s["balk_n"] == 1.0 and s["standoff_break_n"] == 0.0
    assert s["balk_share"] == 1.0 and 0.0 < s["stare_frac"]


def test_standoff_and_balk_do_not_hunt(c7):
    """대치·물러남인 잠행형은 사냥하지 않는다 — 옆에 다른 개체가 포획 거리 안에 있어도 잡지 않는다."""
    w, c = _solo(c7, "stalker", 8.0, Z)
    w.step(_req(w, Z))
    assert w.stalk_state[0] == ST_STANDOFF
    w.pos[1] = w.pred_pos[0] + [0.3, 0.3]
    assert not w._step_predators_v3()[1] and w.stalk_state[0] == ST_STANDOFF
    w.stalk_state[0], w.stalk_left[0], w.balk_dir[0] = ST_BALK, 10, [-1.0, 0.0]
    w.pred_lock[0] = -1
    w.pos[1] = w.pred_pos[0] + [-0.3, 0.0]
    assert not w._step_predators_v3()[1]


@pytest.mark.parametrize("d0, pounce_now", [(5.0, True), (8.0, False)])
def test_break_pounces_same_step_inside_pounce_range(c7, d0, pounce_now):
    """대치가 깨지면(먼저 눈을 돌림) 그 스텝의 C0 에서 배회가 되어 같은 스텝의 표적 선택·돌진 판정을 탄다: 실거리 ≤ 6 이면 그 스텝에
    돌진, > 6 이면 잠행을 다시 시작한다(잠금은 남는다)."""
    w, _ = _solo(c7, "stalker", d0, Z)
    w.step(_req(w, Z))
    w.step(_req(w, Z))
    assert w.stalk_state[0] == ST_STANDOFF and w.spot_cnt[0] == 2
    w._rs.lock_left[0] = 0                                                  # 먹기로 돌아간다(결정 강제)
    w.step(_req(w, G))
    assert w.behavior[0] == G
    assert bool(w.stalk_state[0] == ST_POUNCE) is pounce_now
    if not pounce_now:
        assert w.stalk_state[0] == ST_ROAM and w.pred_lock[0] == 0
        assert np.linalg.norm(w.pred_vel[0]) == pytest.approx(w._th["stalk_speed"] * w.cfg.herb_speed)
    assert w.stare_stats()["standoff_break_n"] == 1.0


def test_balk_reflects_at_wall(c7):
    """물러남 방향이 벽을 넘으면 그 축의 이동과 balk_dir 를 함께 뒤집는다."""
    w, c = _solo(c7, "stalker", 8.0, Z)
    w.pos[0] = [8.1, c[1]]
    w.pred_pos[0] = [0.1, c[1]]
    w._g = w._geometry()
    rep.perceive(w._rs, w._rp, w._g)
    for _ in range(6):
        w.step(_req(w, Z))
    assert w.stalk_state[0] == ST_BALK
    assert w.balk_dir[0, 0] > 0.0 and 0.0 <= w.pred_pos[0, 0] <= w.size


def test_player_spotted_and_capped_charge(c7):
    """플레이어는 멈추지 않는다: 잠긴 표적이 6스텝 이어 노려보면 들킴(45스텝). 들킴 중 시작한 돌진은 min(1.3, 0.9) × herb_speed 로
    전체가 느리고, 돌진이 끝나면 표시를 지운다. 들키지 않은 돌진은 1.3 × herb_speed 그대로다."""
    w, c = _solo(c7, "player", 8.0, Z)
    hs = w.cfg.herb_speed
    for k in range(6):
        w.step(_req(w, Z))
        assert np.linalg.norm(w.pred_vel[0]) == pytest.approx(w._th["player_speeds"][1] * hs)   # 멈추지 않는다
    assert w.spotted_left[0] == 44 and w.spot_cnt[0] == 0 and w.stare_stats()["spotted_n"] == 1.0
    w.pred_pos[0] = w.pos[0] + [-4.0, 0.0]
    w._rs.lock_left[0] = 0
    w.step(_req(w, G))                                                     # 먹기로 돌아가면 체감 거리 4 ≤ 6 → 돌진
    assert w.player_mode[0] == PM_CHARGE and w.spotted_charge[0]
    assert np.linalg.norm(w.pred_vel[0]) == pytest.approx(0.9 * hs)
    for _ in range(40):
        if w.player_mode[0] != PM_CHARGE:
            break
        w.step(_req(w, F_))
    assert w.player_mode[0] == PM_REST and not w.spotted_charge[0]
    s = w.stare_stats()
    assert s["spotted_charge_n"] == 1.0
    w, c = _solo(c7, "player", 4.0, G)                                     # 들키지 않은 돌진
    w.step(_req(w, G))
    assert w.player_mode[0] == PM_CHARGE and not w.spotted_charge[0]
    assert np.linalg.norm(w.pred_vel[0]) == pytest.approx(w._th["player_speeds"][2] * hs)


def test_chasers_are_unaffected(c7):
    """추격형은 노려봐도 대치·잠금이 없다."""
    w, _ = _solo(c7, "chaser", 6.0, Z)
    for _ in range(20):
        w.step(_req(w, Z))
        assert w.pred_lock[0] == -1 and w.stalk_state[0] == ST_ROAM


def test_target_lock_false_records_last_target(c7):
    """target_lock false: 잠금 = 지난 스텝 표적 기록. 얼어 있는 표적이 실거리 > 7.8 이면(체감 거리 × 1.8 > 14) 표적을 잃는다."""
    cfg = _feat(c7, "stare_down", target_lock=False)
    w, _ = _solo(cfg, "stalker", 12.0, Z)
    _pred_only(w)
    assert w.pred_lock[0] == -1 and w.stalk_state[0] == ST_ROAM
    w, _ = _solo(_feat(c7, "stare_down"), "stalker", 12.0, Z)
    _pred_only(w)
    assert w.pred_lock[0] == 0                                              # 잠금이 있으면 놓치지 않는다


# --------------------------------------------------------------------- #
# M8 단위 시험 — 순수 함수
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def AP(c8):
    return World(c8, seeds=[0])._al


@pytest.fixture(scope="module")
def P8(c8):
    return World(c8, seeds=[0])._rp


def _rs(P8, n):
    rs = rep.RepState(n, P8, np.full(n, 0.8), 0.0, 0, alarm=True)
    assert rs.has_alarm
    return rs


def _em(n, emit=(), hop=(), pt=(), t0=()):
    e = dict(emit=np.zeros(n, dtype=bool), hop=np.full(n, rep.AL_NONE, dtype=np.int64), pt=np.zeros((n, 2)),
             t0=np.zeros(n, dtype=np.int64), cry=np.zeros(n, dtype=bool))
    for i, h, p, t in zip(emit, hop, pt, t0):
        e["emit"][i], e["hop"][i], e["pt"][i], e["t0"][i] = True, h, p, t
    return e


def test_alarm_emit_conditions(P8, AP):
    """방출: 전환 & FLEE·FREEZE·HIDE 진입만. 보이면 홉 0(점 = 결정 위치 − away × 거리 = 위협 위치, t0 = t), 안 보이면 쥔 경보를
    중계(ttl > 0 & hop < max_hop & t − t0 ≤ relay_window), 그 밖은 조용하다(앎 없는 FREEZE 포함)."""
    n = 9
    rs = _rs(P8, n)
    rs.behavior[:] = [F_, Z, H, G, Z, Z, Z, Z, Z]
    sw = np.array([1, 1, 1, 1, 0, 1, 1, 1, 1], dtype=bool)
    pc = np.array([1, 1, 1, 1, 1, 0, 0, 0, 0])
    pos = np.tile([10.0, 10.0], (n, 1))
    away = np.tile([1.0, 0.0], (n, 1))
    d = np.array([3.0, 4.0, 5.0, 3.0, 3.0, np.inf, np.inf, np.inf, np.inf])
    rs.al_ttl[6:] = 5
    rs.al_hop[6:] = [0, 2, 1]
    rs.al_t0[6:] = [90, 90, 60]
    rs.al_pt[6:] = [[1.0, 2.0]] * 3
    rs.alarm_new[:] = True
    em = rep.alarm_emit(rs, AP, sw, pc, pos, away, d, t=100)
    np.testing.assert_array_equal(em["emit"], [1, 1, 1, 0, 0, 0, 1, 0, 0])
    np.testing.assert_array_equal(em["hop"][[0, 1, 2, 6]], [0, 0, 0, 1])
    np.testing.assert_allclose(em["pt"][:3], [[7.0, 10.0], [6.0, 10.0], [5.0, 10.0]])
    np.testing.assert_array_equal(em["pt"][6], [1.0, 2.0])
    assert em["t0"][0] == 100 and em["t0"][6] == 90
    assert not rs.alarm_new.any()                                           # A′ 뒤 alarm_new ← False
    np.testing.assert_array_equal(rs.entry_cause[[0, 5, 6]], [rep.ENTRY_SEEN, rep.ENTRY_OTHER, rep.ENTRY_HEARD])
    assert rs.entry_cause[3] == 0 and rs.entry_cause[4] == 0


def test_alarm_receive_lexicographic_choice(P8, AP):
    """가장 좋은 후보 = (홉, 거리², AgentKey) 사전식 최소, 자기 제외, 실거리 ≤ alarm_r 만."""
    n = 6
    rs = _rs(P8, n)
    pos = np.array([[0.0, 0.0], [3.0, 0.0], [-2.0, 0.0], [0.0, 2.0], [8.5, 0.0], [5.0, 0.0]])
    em = _em(n, emit=(1, 2, 3, 4), hop=(1, 1, 1, 0), pt=([1, 1], [2, 2], [3, 3], [4, 4]), t0=(5, 6, 7, 8))
    keys = rep.agent_keys(np.arange(n), np.array([0, 0, 0, 0, 0, 0]))
    res = rep.alarm_receive(rs, AP, em, pos, keys, np.zeros(n))
    assert res["best"][0] == 2              # 4(홉 0)는 8.5 > 8 이라 후보가 아니다. 1·2·3 은 홉 1, 거리² 4 인 2·3 중 키가 작은 2
    assert res["best"][5] == 4                                              # 홉 0 이 가장 세다(거리 3.5)
    assert res["best"][1] == 4 and res["accept"][1]                        # 낸 개체도 더 센 경보(홉 0 < 자기 1)는 받는다
    assert not res["new"][1]                                                # 스스로 냈으면 E7 아님
    assert res["best"][4] == 1 and not res["accept"][4]                    # 자기 제외, 더 약한 경보는 받지 않는다
    np.testing.assert_array_equal(rs.al_pt[5], [4, 4])
    assert rs.al_t0[5] == 8 and rs.al_ttl[5] == 15 and rs.al_hop[5] == 0


def test_alarm_receive_tie_breaks_by_key(P8, AP):
    """홉·거리²가 같으면 AgentKey 가 작은 쪽."""
    n = 3
    rs = _rs(P8, n)
    pos = np.array([[0.0, 0.0], [3.0, 0.0], [-3.0, 0.0]])
    em = _em(n, emit=(1, 2), hop=(0, 0), pt=([1, 0], [2, 0]), t0=(0, 0))
    keys = rep.agent_keys(np.arange(n), np.array([0, 5, 1]))
    res = rep.alarm_receive(rs, AP, em, pos, keys, np.zeros(n))
    assert res["best"][0] == 1                                              # 1·2^32 + 5 < 2·2^32 + 1
    rs = _rs(P8, n)
    keys = rep.agent_keys(np.array([0, 9, 2]), np.zeros(3, dtype=np.int64))
    res = rep.alarm_receive(rs, AP, em, pos, keys, np.zeros(n))
    assert res["best"][0] == 2


def test_ttl_refresh_weaker_ignored_and_e7(P8, AP):
    """ttl ← max(ttl − 1, 0). 같거나 더 센 경보만 받아 ttl 을 새로 하고, 더 약한 경보는 무시한다. E7(alarm_new) = 새 경보이거나
    더 센 경보 & 세기 ≥ event_alarm & 스스로 내지 않음 — 홉 2(0.36)는 E7 이 아니다."""
    n = 2
    pos = np.array([[0.0, 0.0], [3.0, 0.0]])
    keys = rep.agent_keys(np.arange(n), np.zeros(n, dtype=np.int64))
    cases = [  # (지금 ttl, 지금 홉, 들은 홉) → (받음, ttl, 홉, E7)
        (5, 0, 1, (False, 4, 0, False)), (5, 1, 1, (True, 15, 1, False)), (5, 1, 0, (True, 15, 0, True)),
        (1, 0, 1, (True, 15, 1, True)), (0, rep.AL_NONE, 0, (True, 15, 0, True)), (0, rep.AL_NONE, 2, (True, 15, 2, False)),
        (5, 2, 1, (True, 15, 1, True)),
    ]
    for ttl, hop, heard, (acc, ttl2, hop2, e7) in cases:
        rs = _rs(P8, n)
        rs.al_ttl[0], rs.al_hop[0] = ttl, hop
        res = rep.alarm_receive(rs, AP, _em(n, emit=(1,), hop=(heard,), pt=([9, 9],), t0=(0,)), pos, keys, np.zeros(n))
        assert (bool(res["accept"][0]), int(rs.al_ttl[0]), int(rs.al_hop[0]), bool(rs.alarm_new[0])) == \
            (acc, ttl2, hop2, e7), (ttl, hop, heard)


def test_e7_only_for_graze_and_sleep(P8):
    """arbitrate 의 E7 = alarm_new & 지금 행동 GRAZE·SLEEP. FREEZE·FLEE·HIDE 잠금은 열지 않는다."""
    for beh, ev in ((G, True), (S, True), (Z, False), (F_, False), (H, False)):
        rs = _rs(P8, 1)
        rs.behavior[0] = beh
        rs.lock_left[0] = 50
        rs.jitter[0] = 0
        obs = dict(pred_count=np.array([0]), d_pred_min=np.array([np.inf]), pred_approach=np.array([0.5]),
                   energy=np.array([0.8]), dark=0.0, in_cover=np.array([False]), cover_k=np.array([-1]),
                   alarm_new=np.array([True]))
        res = rep.arbitrate(rs, P8, np.array([Z]), obs)
        assert bool(res["e7"][0]) is ev and bool(res["event"][0]) is ev and bool(res["decide"][0]) is ev, beh


def test_direction_only_without_own_info(P8, AP):
    """받았고 자기 정보가 없으면(pred_count 0 & recency < 0.2) away ← 단위(자기 위치 − 점). 본 개체·기억이 있는 개체는 그대로."""
    n = 4
    pos = np.array([[0.0, 0.0], [0.0, 3.0], [3.0, 0.0], [-3.0, 0.0]])
    keys = rep.agent_keys(np.arange(n), np.zeros(n, dtype=np.int64))
    rs = _rs(P8, n)
    rs.away[:] = [0.0, -1.0]
    rs.recency[:] = [0.0, 0.0, 0.5, 0.0]
    pc = np.array([0, 1, 0, 0])
    rep.alarm_receive(rs, AP, _em(n, emit=(3,), hop=(0,), pt=([-10.0, 0.0],), t0=(0,)), pos, keys, pc)
    np.testing.assert_allclose(rs.away[0], [1.0, 0.0])
    np.testing.assert_allclose(rs.away[1], [0.0, -1.0])
    np.testing.assert_allclose(rs.away[2], [0.0, -1.0])
    np.testing.assert_allclose(rs.away[3], [0.0, -1.0])                    # 낸 개체는 자기 방향


def test_alarm_level_and_mask_v3(P8, AP, c8):
    """alarm_heard = hop_gain^hop × ttl ÷ alarm_steps. 마스크 판 3 은 0.4 이상에서 FLEE·FREEZE 를 연다 — 홉 0 은 받은 뒤 10스텝,
    홉 1 은 6스텝, 홉 2(0.36)는 열지 않는다."""
    names = list(World(c8, seeds=[0]).obs_names)
    for hop, opens in ((0, 10), (1, 6), (2, 0)):
        rs = _rs(P8, 1)
        rs.al_hop[0], rs.al_ttl[0] = hop, AP["alarm_steps"]
        levels = []
        while rs.al_ttl[0] > 0:
            levels.append(float(rep.alarm_level(rs, AP)[0]))
            rs.al_ttl[0] -= 1
        assert levels[0] == pytest.approx(AP["gain"][hop]) and len(levels) == 15
        o = np.zeros((len(levels), len(names)), dtype=np.float32)
        o[:, names.index("cover_dist")] = 1.0
        o[:, names.index("alarm_heard")] = levels
        m = rp.feasible_mask(o, names)
        assert int(m[:, Z].sum()) == opens and int(m[:, F_].sum()) == opens and not m[:, H].any(), hop
    assert rep.alarm_level(_rs(P8, 1), AP)[0] == 0.0


# --------------------------------------------------------------------- #
# M8 — 세계에서
# --------------------------------------------------------------------- #


def _wave_module():
    spec = importlib.util.spec_from_file_location("wave_r2", ROOT / "results" / "v3" / "r2" / "wave_r2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def wave():
    return _wave_module()


@pytest.mark.parametrize("j", [0, 3])
def test_alarm_wave_line(wave, j):
    """줄 간격 6, max_hop 2: 개체 1 은 홉 0(1.0), 개체 2 는 홉 1(0.6)을 받고 얼며, 개체 3 은 0.36 을 받기만 한다(E7 없음, 마스크
    닫힘). 홉 하나에 1 + 지연 스텝. 점 방식 시선 오차 0. 메아리(개체 0 이 홉 1 을 돌려받음)는 받아들이지 않고 E7 도 없다."""
    r = wave.scene("line", 6.0, "look", j, 2)["agents"]
    assert [r[i]["recv_hop"] for i in (1, 2, 3)] == [0, 1, 2]
    assert [r[i]["recv_level"] for i in (1, 2, 3)] == [1.0, 0.6, 0.36]
    assert [r[i]["recv_t"] for i in (1, 2, 3)] == [0, 1 + j, 2 * (1 + j)]
    assert r[1]["freeze_t"] == 1 + j and r[2]["freeze_t"] == 2 * (1 + j) and r[3]["freeze_t"] is None
    assert r[3]["e7_t"] is None and r[3]["mask_freeze_at_recv"] is False and r[2]["mask_freeze_at_recv"] is True
    assert all(r[i]["err_pt"] == 0.0 for i in (1, 2, 3))
    assert r[4]["recv_t"] is None
    echo = wave.scene("line", 6.0, "look", j, 2)["echo"]
    assert not echo["hop1_heard"] and not echo["e7"]


def test_alarm_wave_variants(wave):
    """간격 9 면 아무도 받지 않는다, max_hop 1 이면 홉 1 너머로 퍼지지 않는다, R_base(무시) 줄은 중계가 없다, 격자에서 점 방식
    시선 오차가 평행 복사보다 작다, relay_window 가 지나면 중계가 멈춘다."""
    r9 = wave.scene("line", 9.0, "look", 0, 2)["agents"]
    assert all(r9[i]["recv_t"] is None for i in range(1, 10))
    r1 = wave.scene("line", 6.0, "look", 0, 1)["agents"]
    assert [i for i in r1 if r1[i]["recv_t"] is not None] == [1, 2] and r1[2]["emit"] == []
    rb = wave.scene("line", 6.0, "rbase", 0, 2)["agents"]
    assert [i for i in rb if rb[i]["recv_t"] is not None] == [1] and rb[1]["emit"] == [] and rb[1]["freeze_t"] is None
    g = wave.scene("grid", 6.0, "look", 0, 2)["agents"]
    ep = [g[i]["err_pt"] for i in g if g[i]["err_pt"] is not None]
    ec = [g[i]["err_copy"] for i in g if g[i]["err_copy"] is not None]
    assert len(ep) >= 5 and max(ep) < 1e-6 and np.mean(ec) > 5.0
    full, short = wave.scene("line", 6.0, "look", 3, 2), wave.scene("line", 6.0, "look", 3, 2, relay_window=5)
    assert max(h for e in full["emits"] for h in e["hop"]) == 2
    assert max(h for e in short["emits"] for h in e["hop"]) == 1             # 홉 2 중계는 t − t0 = 8 > 5 라 없다


def test_cry_point_and_respawn_reset(wave):
    """비명: 잡힌 개체는 홉 0 을 내고 점 = 잡은 위협의 위치다. 리스폰한 슬롯의 경보 상태는 0 이다(관측 alarm_heard 0)."""
    c = wave.scene("line", 6.0, "look", 0, 2, threat="chaser")["cry"]
    assert c is not None and c["hop"] == 0 and c["receivers"]
    for pt in c["pt_of_receivers"]:
        assert pt == c["pred_pos"]
    assert c["victim_state_after_respawn"] == dict(ttl=0, hop=rep.AL_NONE, seq=0, alarm_new=False, obs_alarm_heard=0.0)


def test_rumor_dies_out_without_threats(wave):
    """포식자가 0마리인 세계에 소문 하나를 심으면 relay_window + alarm_steps(45) 안에 꺼진다."""
    r = wave.scene("line", 6.0, "look", 0, 2, threat="none", plant=True)
    assert r["emits"] and r["last_alarm_t"] is not None and r["last_alarm_t"] < 45
    r = wave.scene("line", 4.0, "look", 3, 2, threat="none", plant=True)
    assert r["last_alarm_t"] < 45


def test_alarm_world_hooks_and_stats(c8):
    """경보 세계 훅(alarm_level = 관측 alarm_heard, alarm_hop, alarm_seq, alarm_pt, alarm_emit, entry_cause, alarm_e7, alarm_from)과
    통계 열. 리스폰은 훅을 바꾸지 않는다(죽은 슬롯의 마지막 프레임)."""
    w = World(_feat(c8, "threats", player_frac=1.0), seeds=[31013])
    pol = ro.build_policy(rr.rule_spec(w.cfg, 4.0, 0.9, x="look", mode="niche"), 0)
    seen_emit = seen_e7 = 0
    for _ in range(400):
        o, _, done, term = w.step(pol(w.observe()))
        lv = w.alarm_level.astype(np.float32)
        np.testing.assert_array_equal(term[:, w._obs_alarm], lv)            # terminal 관측 = 리스폰 전 훅
        alive = ~done
        np.testing.assert_array_equal(o[alive, w._obs_alarm], lv[alive])
        assert (o[done, w._obs_alarm] == 0.0).all()                         # 리스폰 관측은 0
        assert ((w.alarm_hop >= 0) == (w._rs.al_ttl > 0))[alive].all()
        seen_emit += int((w.alarm_emit >= 0).sum())
        seen_e7 += int(w.alarm_e7.sum())
    s = w.alarm_stats()
    assert tuple(s) == ALARM_STAT_COLUMNS
    assert seen_emit == s["emit_h0"] + s["emit_h1"] + s["emit_h2"] and seen_e7 == s["e7_n"]
    assert s["emit_h1"] > 0 and 0.0 < s["alarm_frac"] < 1.0 and s["dir_n"] > 0 and s["wave_size_mean"] > 0.0


def test_rollout_rows_carry_r2_columns_only_when_on(c1, c7, c8):
    spec = {"kind": "fixed", "action": [0.0]}
    r7, r8, r1 = (ro.rollout(c, ro.build_policy(spec), 31014, 120) for c in (c7, c8, c1))
    assert set(ro.STARE_COLUMNS) <= set(r7) and not set(ro.ALARM_COLUMNS) & set(r7)
    assert set(ro.ALARM_COLUMNS) <= set(r8) and not set(ro.STARE_COLUMNS) & set(r8)
    assert not (set(ro.STARE_COLUMNS) | set(ro.ALARM_COLUMNS)) & set(r1)
    assert tuple(ro.STARE_COLUMNS) == STARE_STAT_COLUMNS
    json.dumps(ro.public_row(r7))
    json.dumps(ro.public_row(r8))


# --------------------------------------------------------------------- #
# 손 규칙 (repertoire_rules.py)
# --------------------------------------------------------------------- #


def _rule_obs(cfg, rows):
    names = list(obs_names(cfg))
    o = np.zeros((len(rows), len(names)), dtype=np.float32)
    for i, r in enumerate(rows):
        o[i, names.index("pred_count")] = r.get("pc", 0) / 8.0
        o[i, names.index("pred_dist")] = r.get("dist", 20.0) / cfg.see_r
        o[i, names.index("pred_approach")] = r.get("app", 0.5)
        o[i, names.index("cover_dist")] = r.get("cover", 20.0) / cfg.obs_cover_norm
        o[i, names.index("energy")] = 0.8
        o[i, names.index("visibility")] = 1.0
        if "alarm_heard" in names:
            o[i, names.index("alarm_heard")] = r.get("alarm", 0.0)
            o[i, names.index("threat_recency")] = r.get("rec", 0.0)
    return o


def test_stare_and_look_rules(c7, c8):
    """NICHES stare(G7)·look(G8)과 보조 규칙의 조건(사전 등록 3·5절). look 은 alarm_heard 칸이 있는 설정에서만 쓴다."""
    rows7 = [dict(pc=1, dist=8.0, app=0.65), dict(pc=1, dist=3.5, app=0.65), dict(pc=1, dist=10.5, app=0.65),
             dict(pc=1, dist=8.0, app=0.7), dict(pc=1, dist=9.0, app=0.5), dict(), dict(pc=1, dist=6.0, app=0.5),
             dict(pc=1, dist=11.0, app=0.62), dict(pc=1, dist=6.0, app=0.8)]
    o = _rule_obs(c7, rows7)

    def pol(cfg, x, mode="niche", obs=o):
        return ro.build_policy(rr.rule_spec(cfg, 4.0, 0.9, x=x, mode=mode), 0)(obs)[:, 0].astype(int).tolist()
    assert pol(c7, "stare") == [Z, F_, G, G, G, G, G, G, G]                # 4 < 거리 ≤ 10 & 0.63 ≤ 접근 < 0.67
    assert pol(c7, "stare", "out") == [G, F_, G, G, G, Z, G, G, G]
    assert pol(c7, "stare", "cross") == [G, F_, G, G, Z, G, G, G, G]       # 거리 ≥ 8 & 접근 < 0.6
    assert pol(c7, "stare_still") == [G, F_, G, G, Z, G, Z, G, G]
    assert pol(c7, "stare_far") == [G, F_, Z, G, G, G, G, Z, G]
    assert pol(c7, "stare_chase") == [G, F_, G, G, G, G, G, G, Z]
    with pytest.raises(ValueError, match="alarm_heard"):
        rr.rule_spec(c7, 4.0, 0.9, x="look")
    with pytest.raises(ValueError, match="niche"):
        rr.rule_spec(c7, 4.0, 0.9, x="stare_far", mode="out")
    rows8 = [dict(alarm=0.5), dict(alarm=0.5, cover=3.0), dict(alarm=0.3), dict(), dict(rec=0.5), dict(pc=1, dist=9.0,
                                                                                                        alarm=0.9)]
    o8 = _rule_obs(c8, rows8)
    assert pol(c8, "look", obs=o8) == [Z, G, G, G, G, G]
    assert pol(c8, "look", "out", obs=o8) == [G, G, G, Z, G, G]
    assert pol(c8, "look", "cross", obs=o8) == [G, G, Z, G, G, G]
    assert pol(c8, "look_hide", obs=o8) == [G, H, G, G, G, G]
    assert pol(c8, "look_flee", obs=o8) == [F_, F_, G, G, G, G]
    # 경보가 없는 설정의 규칙 스펙(칸 번호)은 R2 전과 같다
    assert set(rr._geom(c7)["cols"]) == set(rr._COLS) and set(rr._geom(c8)["cols"]) == set(rr._COLS) | {"alarm_heard",
                                                                                                         "threat_recency"}


def test_fsm_r2_priority(c8, c7):
    """FSM_R2 = R_base → look → stare → FREEZE 가까운 판 → HIDE (뒤가 앞을 덮는다, 우선순위는 그 반대). 통과한 장치의 줄만."""
    spec = rr.fsm_r2_spec(c8)
    assert [w.get("x") for w in spec["wrap"]] == [None, "look", "stare", "freeze", "hide"]
    assert [w.get("mode") for w in spec["wrap"][1:]] == ["niche", "niche", "cross", "niche"]
    assert [w.get("x") for w in rr.fsm_r2_spec(c7, look=False)["wrap"]] == [None, "stare", "freeze", "hide"]
    with pytest.raises(ValueError, match="alarm_heard"):
        rr.fsm_r2_spec(c7)
    rows = [dict(pc=1, dist=8.0, app=0.65, cover=3.0), dict(pc=1, dist=8.0, app=0.65), dict(pc=1, dist=3.0),
            dict(alarm=0.5), dict(pc=1, dist=8.0, app=0.95)]
    out = ro.build_policy(spec, 0)(_rule_obs(c8, rows))[:, 0].astype(int).tolist()
    assert out == [H, Z, Z, Z, Z]


# --------------------------------------------------------------------- #
# 관문 도구·결정적 확인표 도구 smoke (시드 31000~31001 — 판정 시드가 아니다)
# --------------------------------------------------------------------- #


def _inv_module():
    spec = importlib.util.spec_from_file_location("invasion_r2", ROOT / "results" / "v3" / "r2" / "invasion_r2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_invasion_r2_smoke(tmp_path):
    """시드 31000~31001 × 200스텝 · 칸 1개 smoke: 탐색 캐시, w7·w8 침입 요약·판정 파일, w8 무리 확인·역침입·H1. 값은 보지 않는다."""
    inv = _inv_module()
    assert inv.SEEDS == list(range(12160, 12200)) and inv.STEPS == 3000
    cell = "ps0.7_pl_T600"
    seeds = [31000, 31001]
    res = inv.search(seeds, 60, 1, tmp_path / "w7", inv.WORLDS["w7"]["config"], grid_theta=[4.0, 8.0],
                     grid_approach=[0.9], cells=[cell])
    assert set(res["table"]) == {"4|0.9", "8|0.9"}
    o7 = inv.run("w7", seeds, 200, 1, tmp_path / "w7", 4.0, 0.9, cells=[cell])
    assert {f"stare|{m}|{cell}" for m in inv.MODES} <= set(o7["summary"])
    assert {f"{x}|niche|{cell}" for x in inv.WORLDS["w7"]["aux"]} <= set(o7["summary"])
    v = o7["summary"][f"stare|out|{cell}"]
    assert v["use_focal"] > 0.2 and v["use_res"] == 0.0 and v["rew"]["n"] == 2
    o8 = inv.run("w8", seeds, 200, 1, tmp_path / "w8", 4.0, 0.9, cells=[cell])
    assert o8["gate"]["look"]["complete"] and f"look_minus_flee|niche|{cell}" in o8["summary"]
    p8 = inv.pop("w8", seeds, 200, 1, tmp_path / "w8", 4.0, 0.9, cells=[cell])
    assert set(p8["summary"]) == {"pop", "rev", "base_off"} and p8["h1"]["complete"]
    assert "alarm" in p8["visible"]["pop"] and p8["visible"]["pop"]["alarm"]["emit_h1"] > 0
    g = json.loads((tmp_path / "w8" / "gate.json").read_text(encoding="utf-8"))
    assert g["h1"]["verdict"] in ("pass", "fail", "low_power", "conditional_pass")
    for name in ("invasion.json", "invasion.md", "gate.json", "pop.json", "pop.md"):
        assert (tmp_path / "w8" / name).exists()
    assert "smoke" in (tmp_path / "w8" / "invasion.md").read_text(encoding="utf-8")


def test_invasion_r2_h1_rule():
    """H1 조건부 통과(사전 등록 4절): (1)·(2) 통과 & (3) 실패·판정 불능 & 무리 유의 음수 0 & 평균 > 0 & 역침입 R_base 승 0."""
    inv = _inv_module()
    g = dict(complete=True, c1=True, c2=True, c3=False, verdict="fail")
    ok = dict(sig_neg=0, mean8=0.001, rev_rbase_wins=0)
    assert inv.h1_verdict(g, ok)["verdict"] == "conditional_pass"
    assert inv.h1_verdict(dict(g, verdict="low_power"), ok)["verdict"] == "conditional_pass"
    assert inv.h1_verdict(g, dict(ok, sig_neg=1))["verdict"] == "fail"
    assert inv.h1_verdict(g, dict(ok, mean8=-0.001))["verdict"] == "fail"
    assert inv.h1_verdict(g, dict(ok, rev_rbase_wins=1))["verdict"] == "fail"
    assert inv.h1_verdict(dict(g, c1=False), ok)["verdict"] == "fail"
    assert inv.h1_verdict(dict(g, c3=True, verdict="pass"), ok)["verdict"] == "pass"


def test_invasion_r2_guards(tmp_path):
    """사전 등록 폴더(results/v3/r2/<world>/)에는 PREREG 조건만 쓴다 — 다른 시드·스텝·칸·설정·wr2 의 --passed 없음은 시작 전에
    멈춘다. 조건이 다른 탐색 캐시는 --force 없이 덮지 않는다."""
    inv = _inv_module()
    for argv in (["run", "--world", "w7", "--steps", "30"], ["search", "--world", "w8", "--seeds", "31000"],
                 ["run", "--world", "w7", "--cells", "ps0.3_np_T600"],
                 ["pop", "--world", "w8", "--config", "configs/v3_r1_on.yaml"],
                 ["run", "--world", "w7", "--theta", "4", "--approach", "0.9", "--seeds", "31000"]):
        with pytest.raises(SystemExit):
            inv.main(argv)
    with pytest.raises(SystemExit):
        inv.main(["run", "--world", "wr2"])                                 # 설정이 아직 없다(관문 뒤에 만든다)
    kw = dict(grid_theta=[8.0], grid_approach=[0.9], cells=["ps0.3_np_T600"])
    inv.search([31000, 31001], 20, 1, tmp_path, inv.WORLDS["w7"]["config"], **kw)
    with pytest.raises(inv.StaleCache, match="force"):
        inv.search([31000, 31001], 21, 1, tmp_path, inv.WORLDS["w7"]["config"], **kw)


def _standoff_module():
    spec = importlib.util.spec_from_file_location("standoff_r2", ROOT / "results" / "v3" / "r2" / "standoff_r2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_standoff_table_rows():
    """결정적 확인표 T7 의 몇 행(명세 9절): 잠행형 × (b) 먹다가 D0 12 → 잡힘 0·물러남, D0 6 → 첫 스텝 돌진, heading 25° 대치·35°
    없음, 플레이어 × (f) 얼어서 D0 4.5 → 들킴·들킨 돌진·잡힘 0, 근접 추격형은 대치 없음."""
    T = _standoff_module()
    r = T.trial(("stalker", "graze", "stare", "free", False, 12000, 12.0))
    assert not r["caught"] and r["balk"] and r["standoff_d"] == pytest.approx(9.84, abs=0.01)
    r = T.trial(("stalker", "graze", "stare", "free", False, 12000, 6.0))
    assert r["caught"] and r["attack_t"] == 0
    assert T.trial(("stalker", "freeze", "head+25", "free", False, 12000, 8.0))["standoff"] == 1
    r = T.trial(("stalker", "freeze", "head+35", "free", False, 12000, 8.0))
    assert r["standoff"] == 0 and r["caught"] and r["attack_d"] <= 3.34
    r = T.trial(("player", "freeze", "zflee", "locked3", False, 12000, 4.5))
    assert r["spotted"] and r["spotted_charge"] and not r["caught"]
    assert T.trial(("chaser095", "freeze", "stare", "free", False, 12000, 8.0))["standoff"] == 0


# --------------------------------------------------------------------- #
# 구현 검토 10-12 반영 (사전 등록 변경 기록 10-12 (2))
# --------------------------------------------------------------------- #


def test_stare_hold_clause(c7, c8):
    """X7 유지 줄: 지금 FREEZE(관측 beh_freeze)이고 보이는 위협이 4 < 거리 ≤ 10 & 0.45 ≤ 접근 < 0.67 이면 FREEZE 를 잇는다(멈춘 대치
    0.5). 먹는 중이면(beh_freeze 0) 옛 니치 띠만 본다. 물러남(0.2)·빠른 위협(≥ 0.67)·거리 밖은 잇지 않는다. FSM_R2 도 같다.
    stare 래퍼만 beh_freeze 칸을 더 갖고, 다른 규칙의 스펙(칸 번호)은 그대로다."""
    names = list(obs_names(c7))
    rows = [dict(pc=1, dist=8.0, app=0.5), dict(pc=1, dist=8.0, app=0.5), dict(pc=1, dist=8.0, app=0.2),
            dict(pc=1, dist=8.0, app=0.7), dict(pc=1, dist=11.0, app=0.5), dict(pc=1, dist=3.9, app=0.5),
            dict(pc=1, dist=8.0, app=0.46), dict(pc=1, dist=8.0, app=0.65)]
    o = _rule_obs(c7, rows)
    fz = [False, True, True, True, True, True, True, False]
    o[:, names.index("beh_freeze")] = np.array(fz, dtype=np.float32)
    o[:, names.index("beh_graze")] = 1.0 - np.array(fz, dtype=np.float32)
    out = ro.build_policy(rr.rule_spec(c7, 4.0, 0.9, x="stare"), 0)(o)[:, 0].astype(int).tolist()
    assert out == [G, Z, G, G, G, F_, Z, Z]
    w = rr.rule_spec(c7, 4.0, 0.9, x="stare")["wrap"][1]
    assert w["cols"]["beh_freeze"] == names.index("beh_freeze") and w["hold_lo"] == 0.45
    assert "beh_freeze" not in rr.rule_spec(c7, 4.0, 0.9, x="freeze")["wrap"][1]["cols"]
    assert "beh_freeze" not in rr.rule_spec(c7, 4.0, 0.9)["wrap"][0]["cols"]
    fs = rr.fsm_r2_spec(c8)
    assert [("beh_freeze" in w_["cols"]) for w_ in fs["wrap"]] == [False, False, True, False, False]
    o8 = _rule_obs(c8, rows[:2])
    n8 = list(obs_names(c8))
    o8[:, n8.index("beh_freeze")] = [0.0, 1.0]
    assert ro.build_policy(fs, 0)(o8)[:, 0].astype(int).tolist() == [G, Z]


def test_new_visible_stats(c7, c8):
    """보이는 지표 추가(보고만): stare_stats 의 standoff_break_beh_n·spotted_charge_catch_frac·unspotted_charge_catch_frac, alarm_stats 의
    e7_decide_frac(글자 그대로 판)·heads_up_1s_r16(16단위). 동역학과 무관하다(뜻은 world.py 열 주석)."""
    w7 = World(c7, seeds=[31020])
    pol = ro.build_policy(rr.rule_spec(rr.with_obs_extra(c7), 4.0, 0.9, x="stare"), 0)
    for _ in range(300):
        w7.step(pol(w7.observe()))
    s = w7.stare_stats()
    assert tuple(s) == STARE_STAT_COLUMNS and s["standoff_break_beh_n"] <= s["standoff_break_n"]
    for k in ("spotted_charge_catch_frac", "unspotted_charge_catch_frac"):
        assert s[k] != s[k] or 0.0 <= s[k] <= 1.0
    w8 = World(c8, seeds=[31021])
    pol8 = ro.build_policy(rr.rule_spec(c8, 4.0, 0.9, x="look"), 0)
    for _ in range(300):
        w8.step(pol8(w8.observe()))
    a = w8.alarm_stats()
    assert tuple(a) == ALARM_STAT_COLUMNS and a["e7_n"] > 0
    assert 0.0 <= a["e7_decide_frac"] <= 1.0 and 0.0 <= a["heads_up_1s_r16"] <= 1.0
    assert w8._al_heads16_n >= w8._al_heads_n > 0                      # 반경 16 ⊇ 반경 alarm_r(8)


def test_invasion_r2_guard_no_aux_and_passed():
    """사전 등록 폴더 실행은 --no-aux(5절 보조 규칙은 보고한다)와 w7·w8 의 --passed 를 받지 않는다. 판정 실행을 띄우지 않게
    main 대신 조건 검사 함수만 부른다."""
    import argparse

    inv = _inv_module()

    def ns(**kw):
        base = dict(cmd="run", steps=inv.STEPS, cells=None, grid_theta=list(inv.GRID_THETA),
                    grid_approach=list(inv.GRID_APPROACH), config=None, passed=[], theta=None, approach=None,
                    out=str(inv.PREREG_DIR / "__none__"), no_aux=False)
        return argparse.Namespace(**dict(base, **kw))
    assert inv.prereg_problems(ns(), inv.SEEDS, "w7") == []
    assert any("--no-aux" in b for b in inv.prereg_problems(ns(no_aux=True), inv.SEEDS, "w7"))
    assert any("--no-aux" in b for b in inv.prereg_problems(ns(no_aux=True), inv.SEEDS, "w8"))
    assert any("--passed" in b for b in inv.prereg_problems(ns(passed=["stare"]), inv.SEEDS, "w8"))
    assert inv.prereg_problems(ns(cmd="pop", no_aux=True), inv.SEEDS, "w7") == []    # pop 은 보조 규칙을 돌리지 않는다


def test_standoff_review_rows():
    """T7 추가 행: (h) 대치 2스텝째 결정 시점 — 유지 줄이 있으면 대치가 물러남까지 가고, 옛 X7 정의는 멈춘 대치에서 먹기를 요청해
    스스로 깬 뒤 잡힌다. (g) 끈적이지 않는 R_base 식 도망은 들킨 돌진에서도 잡힌다(H4 상한의 실제 효과 — 사람 확인 안건).
    포획 판정 때 간격(min_gap_c)을 함께 낸다."""
    T = _standoff_module()
    r = T.trial(("stalker", "freeze", "evt2", "free", False, 12000, 8.0))
    assert r["balk"] and not r["caught"] and r["break_t"] is None
    r = T.trial(("stalker", "freeze", "evt2_old", "free", False, 12000, 8.0))
    assert r["break_t"] is not None and r["caught"] and not r["balk"]
    r = T.trial(("player", "graze", "stare_ns", "free", False, 12000, 8.0))
    assert r["spotted_charge"] and r["caught"] and r["min_gap_c"] is not None
    ev = T._edge_vals()
    assert T.edges(("stalker", "freeze", "stare", "free", False), 10.0, ev) == ["spot_r"]
    assert "돌진 거리" in T.edges(("stalker", "graze", "stare", "free", False), 6.0, ev)
    assert T.edges(("stalker", "graze", "stare", "free", False), 8.0, ev) == []


def test_wave_line_edge(wave):
    """T8 문턱 일치: 줄 간격 8(이웃)·4(두 칸 건너)는 두 개체의 거리가 alarm_r 8 과 같다. 6·9 는 아니다. 옮긴 판 7.99 는 이웃이
    듣고 8.01 은 듣지 않는다."""
    assert wave.line_edge(8.0, 8.0) and wave.line_edge(4.0, 8.0)
    assert not wave.line_edge(6.0, 8.0) and not wave.line_edge(9.0, 8.0)
    lo = wave.scene("line", 7.99, "look", 0, 2)["agents"]
    hi = wave.scene("line", 8.01, "look", 0, 2)["agents"]
    assert lo[1]["recv_t"] is not None and hi[1]["recv_t"] is None
