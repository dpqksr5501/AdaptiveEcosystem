"""v3 R4 학습 세계 — 학습 보충(integrated_stage.respawn_safe_r)·지역 섞기(train.region_mix)·설정 configs/v3_r4_train.yaml (10-18 사용자 '그 날씨와 장애물들을
바탕으로 만들어진 세계를 파이썬에 고대로 옮겨서 학습시킬 거야', 사람 결정 RL_V2_PLAN.md 10-18 (15), 사전 등록 results/v3/r4/PREREG.md).

비트 동일: 새 선택 키를 쓰지 않는 세계·VecEnv 는 직전 커밋(77b3484)의 코드와 궤적·통계·v1 난수 상태·기능 스트림이 같다(R3 학습 세계·날씨 거울·부활을 켠 날씨
거울·R1b 롤아웃, R3·R1 학습 VecEnv 의 관측·보상·끝·교체 시드). 규칙 시험: 안전 자리(모든 늑대에게서 20 단위 이상·원판 밖·은신처 밖·무대 여유 안), 후보가 없을
때 가장 먼 후보, 계수 검사, 지역 섞기(지역마다 날씨·나무 수, 같은 메타 시드면 같은 차례), f_dec 측정의 지역 셋, 설정 생성기 최신·거울과 다른 곳 넷.
시드는 탐색 32080~32099 만 쓴다(학습 풀 32000~32049·점검 32050~32059·고르기 32060~32079 는 쓰지 않는다).
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import json
import subprocess
import sys

import numpy as np
import pytest
import yaml

from env.config import ROOT
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.vec_env import MultiWorldVecEnv, region_configs, region_mix_params
from env_v2.world import World, obstacle_inside

CFG = ROOT / "configs"
WILD3 = CFG / "v3_wild3_mirror.yaml"
R4 = CFG / "v3_r4_train.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "77b3484"              # R4 학습 세계 직전 커밋(지역 날씨 독립 확인 문서) — 비트 동일 기준

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


def _region_cfg(region, n=32, **ist):
    cfg = load_v2_config(R4).replace(N=n)
    if ist:
        cfg = _with(cfg, integrated_stage=ist)
    return region_configs(cfg, region_mix_params(cfg.v2["train"]["region_mix"], cfg))[region]


def _check_spots(w, pts, safe):
    ist = w._ist
    lo, hi = ist["deer_margin"], w.size - ist["deer_margin"]
    assert ((pts >= lo) & (pts <= hi)).all()
    d = np.sqrt(((pts[:, None, :] - w.pred_pos[None, :, :]) ** 2).sum(-1)).min(1)
    assert (d >= safe).all(), d.min()
    if len(w.obstacles):
        assert not obstacle_inside(pts, w.obstacles, w._ob["body_r"]).any()
    assert not w._in_cover(pts).any()


# --------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------- #


def test_r4_config_is_mirror_plus_four_changes():
    """v3_r4_train.yaml = v3_wild3_mirror.yaml + 넷(version·overrides.train_seeds·integrated_stage 학습 보충·train 블록). 생성기가 최신이다."""
    gen = _module("_make_r4", ROOT / "results" / "v3" / "r4" / "make_r4_config.py")
    assert gen.main(["--check"]) == 0
    a, b = yaml.safe_load(WILD3.read_text(encoding="utf-8")), yaml.safe_load(R4.read_text(encoding="utf-8"))
    assert (a["version"], b["version"]) == ("3.wild3", "3.r4")
    assert b["overrides"].pop("train_seeds") == [32000, 32050]
    ist = b["features"]["integrated_stage"]
    assert (ist.pop("respawn"), ist.pop("respawn_safe_r"), ist.pop("respawn_tries")) == (True, 20.0, 64)
    assert a["features"]["integrated_stage"].pop("respawn") is False
    tr = b.pop("train")
    a.pop("train")
    a.pop("version")
    b.pop("version")
    assert a == b
    assert tr["repertoire"]["allowed"] == ["graze", "flee", "hide"]
    assert tr["repertoire"]["ent_coef_base"] == pytest.approx(0.01 * tr["repertoire"]["f_dec"], rel=1e-9)
    lay = json.loads((ROOT / "results" / "v3" / "wild2" / "trees" / "tree_layout.json").read_text(encoding="utf-8"))
    assert tr["region_mix"]["obstacles"] == {r["region"]: r["discs"] for r in lay["regions"]}
    assert [len(tr["region_mix"]["obstacles"][r]) for r in ("Barren", "Forest", "Highland")] == [0, 24, 9]
    cfg = load_v2_config(R4)
    assert tuple(cfg.train_seeds) == (32000, 32050)


def test_respawn_safe_params_checked():
    base = load_v2_config(WILD3).replace(N=8)
    with pytest.raises(ValueError, match="respawn true"):
        World(_with(base, integrated_stage=dict(respawn_safe_r=20.0)), seeds=[32080])
    with pytest.raises(ValueError, match="start_layout"):
        World(_with(base, integrated_stage=dict(respawn=True, respawn_safe_r=20.0, start_layout=None)), seeds=[32080])
    with pytest.raises(ValueError, match="respawn_safe_r"):
        World(_with(base, integrated_stage=dict(respawn=True, respawn_safe_r=0.0)), seeds=[32080])
    with pytest.raises(ValueError, match="respawn_tries"):
        World(_with(base, integrated_stage=dict(respawn=True, respawn_safe_r=20.0, respawn_tries=0)), seeds=[32080])
    w = World(_with(base, integrated_stage=dict(respawn=True)), seeds=[32080])
    with pytest.raises(ValueError, match="respawn_stats"):
        w.respawn_stats()


def test_region_mix_params_checked():
    cfg = load_v2_config(R4)
    good = cfg.v2["train"]["region_mix"]
    assert region_mix_params(None, cfg) is None
    for bad in (dict(good, weights=[1, 1]), dict(good, weights=[1, 0, 1]), dict(good, regions=["Barren", "Forest", "Moon"]),
                {k: v for k, v in good.items() if k != "weights"}, dict(good, obstacles=dict(good["obstacles"], Forest=[[1.0, 2.0]]))):
        with pytest.raises(ValueError):
            region_mix_params(bad, cfg)
    off = _with(cfg, wild_weather=dict(enabled=False))
    with pytest.raises(ValueError, match="wild_weather"):
        region_mix_params(good, off)


# --------------------------------------------------------------------- #
# 학습 보충
# --------------------------------------------------------------------- #


def test_safe_spawn_spots_and_fallback():
    """후보 자리 = 모든 늑대에게서 20 단위 이상·원판 밖·은신처 밖·무대 여유 안. 맞는 후보가 없으면(안전 거리 1000) 원판·은신처 밖 후보 가운데 가장 먼 것."""
    for region in ("Highland", "Forest", "Barren"):
        w = World(_region_cfg(region), seeds=[32081])
        pts = w._ist_safe_spawn(40)
        _check_spots(w, pts, 20.0)
        assert w.respawn_stats()["respawns"] == 40 and w.respawn_stats()["fallback"] == 0
    w = World(_region_cfg("Forest", respawn_safe_r=1000.0), seeds=[32081])
    pts = w._ist_safe_spawn(10)
    assert w.respawn_stats()["fallback"] == 10
    assert not obstacle_inside(pts, w.obstacles, w._ob["body_r"]).any() and not w._in_cover(pts).any()
    # 같은 스트림을 다시 만들어 후보를 되짚으면 고른 자리는 원판·은신처 밖 후보 가운데 가장 먼 것이다
    from env_v2.features import feature_stream

    g = feature_stream(w.seed, "integrated_stage", 1)
    c, room = 0.5 * w.size, 0.5 * w.size - w._ist["deer_margin"]
    cand = (c + g.uniform(-room, room, (10, 64, 2)))
    for i in range(10):
        q = cand[i]
        free = ~obstacle_inside(q, w.obstacles, w._ob["body_r"]) & ~w._in_cover(q)
        d = np.sqrt(((q[:, None, :] - w.pred_pos[None, :, :]) ** 2).sum(-1)).min(1)
        np.testing.assert_array_equal(pts[i], q[int(np.argmax(np.where(free, d, -np.inf)))])


def test_dead_deer_respawn_far_from_wolves():
    """학습 보충 세계: 죽은 사슴은 그 스텝 끝에 다시 나고(사슴 수가 늘 N) 자리는 안전 규칙을 지킨다. 각·에너지·비축은 v1 리스폰과 같다(새 개체)."""
    w = World(_region_cfg("Barren", n=64), seeds=[32082])
    assert w.alive is None
    deaths = 0
    for _ in range(600):
        obs, rew, done, term = w.step(np.full((w.N, 1), float(rep.GRAZE)))
        dead = np.flatnonzero(done)
        if len(dead):
            deaths += len(dead)
            _check_spots(w, w.pos[dead], 20.0)
            np.testing.assert_array_equal(w.energy[dead], w.cfg.init_energy)
            np.testing.assert_array_equal(w.reserve[dead], w._wr["init"])
    st = w.respawn_stats()
    assert deaths > 0 and st["respawns"] == deaths and st["fallback"] == 0 and st["mean_wolf_d"] >= 20.0


def test_safe_off_equals_v1_respawn():
    """respawn_safe_r null 이면 v1 리스폰 그대로: R4 설정(안전 거리 끔) = 날씨 거울 + 부활 켬(궤적·통계)."""
    a = _with(load_v2_config(WILD3).replace(N=32), integrated_stage=dict(respawn=True))
    b = _with(load_v2_config(R4).replace(N=32), integrated_stage=dict(respawn_safe_r=None))
    w1, w2 = World(a, seeds=[32083]), World(b, seeds=[32083])
    rng = np.random.default_rng(5)
    for _ in range(300):
        act = rng.integers(0, 3, (w1.N, 1)).astype(np.float64)
        for x, y in zip(w1.step(act), w2.step(act)):
            np.testing.assert_array_equal(x, y)
    assert json.dumps(w1.stats()) == json.dumps(w2.stats())
    assert w1._pred_deaths > 0


# --------------------------------------------------------------------- #
# 지역 섞기
# --------------------------------------------------------------------- #


def _rand_steps(v, steps, seed):
    rng = np.random.default_rng(seed)
    outs = []
    for _ in range(steps):
        m = v.current_masks()
        a = (rng.random(m.shape) * m).argmax(1)
        obs, rew, done, info = v.step(a)
        outs.append((obs.copy(), rew.copy(), done.copy()))
    return outs


def test_region_mix_worlds():
    """새 세계마다 지역 하나: 그 세계의 날씨 지역·나무 수가 지역과 맞고, 같은 메타 시드면 차례·관측이 같다. 학습 보충 세계라 VecEnv 가 받는다."""
    cfg = load_v2_config(R4).replace(N=16)
    v1 = MultiWorldVecEnv(cfg, num_worlds=3, reset_interval=12, meta_seed=7)
    v2 = MultiWorldVecEnv(cfg, num_worlds=3, reset_interval=12, meta_seed=7)
    v1.reset()
    v2.reset()
    o1, o2 = _rand_steps(v1, 40, 3), _rand_steps(v2, 40, 3)
    for a, b in zip(o1, o2):
        for x, y in zip(a, b):
            np.testing.assert_array_equal(x, y)
    assert v1.region_history == v2.region_history and v1.seed_history == v2.seed_history
    assert [len(h) for h in v1.region_history] == [len(h) for h in v1.seed_history] and v1.num_resets >= 6
    trees = {"Barren": 0, "Forest": 24, "Highland": 9}
    kind = {"Barren": "clear", "Forest": "rain", "Highland": "snow"}
    for k, w in enumerate(v1.worlds):
        r = v1.region_history[k][-1]
        assert w.weather_stats()["region"] == r and w.weather_stats()["kind"] == kind[r] and len(w.obstacles) == trees[r]
        assert w.alive is None and w.seed in range(32000, 32050)
    seen = {r for h in v1.region_history for r in h}
    assert seen == {"Barren", "Forest", "Highland"}


def test_measure_fdec_runs_every_region():
    import train_v3

    res = train_v3.measure_fdec(load_v2_config(R4).replace(N=16), seeds=(32084,), steps=5)
    assert [r["region"] for r in res["per_seed"]] == ["Barren", "Forest", "Highland"]
    res0 = train_v3.measure_fdec(load_v2_config(CFG / "v3_r3.yaml").replace(N=16), seeds=(32084,), steps=5)
    assert len(res0["per_seed"]) == 1 and "region" not in res0["per_seed"][0]


# --------------------------------------------------------------------- #
# 직전 코드와 비트 동일
# --------------------------------------------------------------------- #

VEC_SRC = r'''
import hashlib, json, sys
sys.path.insert(0, ".")
import env.torch_init
import numpy as np
from env_v2.config import load_v2_config
from env_v2.vec_env import MultiWorldVecEnv


def run(job):
    cfg = load_v2_config(job["config"]).replace(N=job["N"])
    venv = MultiWorldVecEnv(cfg, num_worlds=job["K"], reset_interval=job["T"], meta_seed=job["meta"])
    rng = np.random.default_rng(job["meta"] + 11)
    obs = venv.reset()
    hs = [hashlib.sha1(np.ascontiguousarray(obs).tobytes()).hexdigest()[:16]]
    for _ in range(job["steps"]):
        m = venv.current_masks()
        a = (rng.random(m.shape) * m).argmax(1)
        obs, rew, done, info = venv.step(a)
        h = hashlib.sha1()
        for x in (obs, rew, done, a):
            h.update(np.ascontiguousarray(x).tobytes())
        for i, d in enumerate(info):
            if d:
                h.update(json.dumps([i, sorted(d)]).encode())
                h.update(np.ascontiguousarray(d["terminal_observation"]).tobytes())
        hs.append(h.hexdigest()[:16])
    cnt = {k: (x.tolist() if hasattr(x, "tolist") else x) for k, x in venv.rep_counts.items()}
    return dict(hashes=hs, seeds=venv.seed_history, resets=venv.num_resets, counts=cnt)


jobs = json.loads(open(sys.argv[1], encoding="utf-8").read())
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps([run(j) for j in jobs]))
'''


def test_bit_identical_to_head(tmp_path):
    """직전 코드(77b3484)와: 세계(R3 판정 세계·날씨 거울·부활을 켠 날씨 거울, R1b 롤아웃 포함)의 궤적·통계·난수·기능 스트림, VecEnv(R3·R1 학습 설정)의
    관측·보상·끝·terminal_obs·교체 시드·학습 기록 수가 같다."""
    tum = _module("_tum_for_r4", ROOT / "tests" / "test_unreal_mirror.py")
    old_root = tum._archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    trace = tmp_path / "trace.py"
    trace.write_text(tum.TRACE_SRC % dict(keys=tum.KEYS, stats=tum.STATS), encoding="utf-8")
    vec = tmp_path / "vec.py"
    vec.write_text(VEC_SRC, encoding="utf-8")
    wjobs = [dict(config="configs/v3_r3_on.yaml", seed=32085, steps=250, policy="rand"),
             dict(config=str(WILD3), seed=32086, steps=300, policy="rand"),
             dict(config=str(WILD3), seed=32087, steps=300, policy="rand", set={"integrated_stage": {"respawn": True}})]
    if R1_MODEL.exists():
        wjobs.append(dict(config=str(WILD3), seed=32088, steps=300, policy="model", model=str(R1_MODEL),
                          set={"integrated_stage": {"respawn": True}}))
    vjobs = [dict(config="configs/v3_r3.yaml", N=16, K=2, T=40, meta=3, steps=100),
             dict(config="configs/v3_r1.yaml", N=16, K=3, T=30, meta=4, steps=90)]
    procs = []
    for root, tag in ((old_root, "old"), (ROOT, "new")):
        for script, js, kind in ((trace, wjobs, "w"), (vec, vjobs, "v")):
            jp, op = tmp_path / f"jobs_{kind}_{tag}.json", tmp_path / f"out_{kind}_{tag}.json"
            jp.write_text(json.dumps(js), encoding="utf-8")
            procs.append(((kind, tag), subprocess.Popen([sys.executable, str(script), str(jp), str(op)], cwd=root), op))
    outs = {}
    for key, p, op in procs:
        assert p.wait(timeout=900) == 0, key
        outs[key] = json.loads(op.read_text(encoding="utf-8"))
    for j, a, b in zip(wjobs, outs[("w", "old")], outs[("w", "new")]):
        first = next((i for i, (x, y) in enumerate(zip(a["hashes"], b["hashes"])) if x != y), None)
        assert first is None and len(a["hashes"]) == len(b["hashes"]), (j, first)
        for k in ("stats", "rng", "obs_names", "streams"):
            assert a[k] == b[k], (j, k)
    for j, a, b in zip(vjobs, outs[("v", "old")], outs[("v", "new")]):
        assert a == b, j
