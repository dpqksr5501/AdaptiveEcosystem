"""v3 R5 학습 세계 시험 (10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 사전 등록 results/v3/r5/PREREG.md).

- 학습 설정 configs/v3_r5_train.yaml = 관측 21 거울 + 바꾼 곳 넷, 생성기 최신
- 무작위 숲 섞기(env_v2/vec_env.py 'v3 R5 무작위 숲 섞기'): 키 검사, 원판 수·자리·결정성, VecEnv 세계 꼴·날씨·차례 결정성
- 키가 없으면 직전 코드와 비트 단위로 같다(R4·R3 학습 설정 VecEnv)
- 시작 모델(R1b-F + 새 세 열 0)의 행동 = R1b-F 의 행동(무작위 관측, 세계 롤아웃)
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import json
import subprocess
import sys

import numpy as np
import pytest
import yaml

from env.config import ROOT
from env_v2.config import load_v2_config
from env_v2.vec_env import (RANDOM_FOREST_KEYS, MultiWorldVecEnv, random_forest_discs, random_forest_params, region_configs,
                            region_mix_params)
from env_v2.world import World

CFG = ROOT / "configs"
OBS = CFG / "v3_wild3_obs_mirror.yaml"
WILD3 = CFG / "v3_wild3_mirror.yaml"
R5 = CFG / "v3_r5_train.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
ZERO_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip"
BASE_COMMIT = "51b7507"              # R5 학습 세계 직전 커밋(R5 언리얼 확인) — 비트 동일 기준

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rf(**kw):
    d = dict(share=0.5, density=[0.0, 1.0], tree_per_ha=250.0, tree_r=[0.05, 0.15], rock_per_ha=5.0, rock_r=[0.25, 0.75],
             brush_share=0.5, brush_per_ha=150.0, brush_r=[0.5, 1.0])
    d.update(kw)
    return d


def test_r5_config_is_obs_mirror_plus_four_changes():
    """v3_r5_train.yaml = v3_wild3_obs_mirror.yaml + 넷(version·train_seeds·학습 보충·train 블록). 관측 21·장애물 관측 켬·허용 먹기·도망·숨기."""
    gen = _module("_make_r5", ROOT / "results" / "v3" / "r5" / "make_r5_config.py")
    assert gen.main(["--check"]) == 0
    a, b = yaml.safe_load(OBS.read_text(encoding="utf-8")), yaml.safe_load(R5.read_text(encoding="utf-8"))
    assert (a["version"], b["version"]) == ("3.wild3obs", "3.r5")
    assert b["overrides"].pop("train_seeds") == [32000, 32050]
    ist = b["features"]["integrated_stage"]
    assert (ist.pop("respawn"), ist.pop("respawn_safe_r"), ist.pop("respawn_tries")) == (True, 20.0, 64)
    assert a["features"]["integrated_stage"].pop("respawn") is False
    tr = b.pop("train")
    a.pop("train")
    for d in (a, b):
        d.pop("version")
    assert a == b
    assert b["features"]["obstacle_obs"]["enabled"] is True
    assert tr["repertoire"]["allowed"] == ["graze", "flee", "hide"]
    assert tr["repertoire"]["ent_coef_base"] == pytest.approx(0.01 * tr["repertoire"]["f_dec"], rel=1e-9)
    lay = json.loads((ROOT / "results" / "v3" / "wild2" / "trees" / "tree_layout.json").read_text(encoding="utf-8"))
    rm = tr["region_mix"]
    assert rm["obstacles"] == {r["region"]: r["discs"] for r in lay["regions"]}
    assert rm["random_forest"] == _rf()
    cfg = load_v2_config(R5)
    assert tuple(cfg.train_seeds) == (32000, 32050)
    assert World(cfg.replace(N=8), seeds=[32000]).obs_dim == 21


def test_random_forest_params_checked():
    assert random_forest_params(None) is None
    assert random_forest_params(_rf())["density"] == (0.0, 1.0)
    bad = [dict(_rf(), extra=1), {k: v for k, v in _rf().items() if k != "share"}, _rf(share=1.5), _rf(share=True),
           _rf(density=[0.5, 0.2]), _rf(density=[0.0, 1.5]), _rf(tree_r=[0.0, 0.1]), _rf(brush_r=[1.0]), _rf(tree_per_ha=-1.0),
           _rf(brush_share=float("nan"))]
    for raw in bad:
        with pytest.raises(ValueError):
            random_forest_params(raw)
    assert set(_rf()) == RANDOM_FOREST_KEYS
    cfg = load_v2_config(R5)
    raw = dict(cfg.v2["train"]["region_mix"])
    assert region_mix_params(raw, cfg)["random_forest"]["share"] == 0.5
    raw.pop("random_forest")
    assert "random_forest" not in region_mix_params(raw, cfg)
    with pytest.raises(ValueError):
        region_mix_params(dict(raw, other=1), cfg)


def test_random_forest_discs():
    """밀도 0 = 나무 없음, 1 = 줄기 360·바위 7(무대 1.44 ha, 자리를 못 찾으면 건너뜀) + 덤불 216. 은신처 원·벽 가장자리 밖, 같은 씨앗이면 같은 원판."""
    w = World(load_v2_config(R5).replace(N=8), seeds=[32000])
    size, cc, cr, body = float(w.size), np.asarray(w.cov_c), np.asarray(w.cov_r), 0.15
    rf = random_forest_params(_rf())
    assert random_forest_discs(rf, 0.0, False, 1, size, cc, cr, body) == []
    assert random_forest_discs(rf, 0.0, True, 1, size, cc, cr, body) == []
    full = random_forest_discs(rf, 1.0, False, 1, size, cc, cr, body)
    brush = random_forest_discs(rf, 1.0, True, 1, size, cc, cr, body)
    assert 340 <= len(full) <= 367 and 540 <= len(brush) <= 583
    assert brush[:len(full)] == full                      # 덤불은 줄기·바위 뒤에 이어서 뽑는다
    assert random_forest_discs(rf, 1.0, True, 1, size, cc, cr, body) == brush
    assert random_forest_discs(rf, 1.0, True, 2, size, cc, cr, body) != brush
    a = np.asarray(brush)
    r_trunk = a[:len(full) - 7, 2]
    assert r_trunk.min() >= 0.05 and r_trunk.max() <= 0.15 and a[len(full):, 2].min() >= 0.5 and a[len(full):, 2].max() <= 1.0
    for (cx, cy), rr in zip(cc, cr):
        if rr > 0:
            assert np.all((a[:, 0] - cx) ** 2 + (a[:, 1] - cy) ** 2 > rr * rr)
    e = a[:, 2] + 2 * body - 1e-9
    assert np.all((a[:, 0] >= e - 1e-6) & (a[:, 0] <= size - e + 1e-6))


def _rand_steps(v, steps, seed):
    rng = np.random.default_rng(seed)
    outs = []
    for _ in range(steps):
        m = v.current_masks()
        a = (rng.random(m.shape) * m).argmax(1)
        obs, rew, done, info = v.step(a)
        outs.append((obs.copy(), rew.copy(), done.copy()))
    return outs


def test_random_forest_worlds():
    """새 세계마다 지역 + 꼴: 'unreal' 이면 지역 나무 원판, 'rand' 면 적힌 수의 무작위 원판(날씨는 지역 그대로). 같은 메타 시드면 차례·관측이 같다."""
    cfg = load_v2_config(R5).replace(N=16)
    v1 = MultiWorldVecEnv(cfg, num_worlds=4, reset_interval=8, meta_seed=11)
    v2 = MultiWorldVecEnv(cfg, num_worlds=4, reset_interval=8, meta_seed=11)
    v1.reset()
    v2.reset()
    for a, b in zip(_rand_steps(v1, 48, 5), _rand_steps(v2, 48, 5)):
        for x, y in zip(a, b):
            np.testing.assert_array_equal(x, y)
    assert v1.forest_history == v2.forest_history and v1.region_history == v2.region_history
    assert [len(h) for h in v1.forest_history] == [len(h) for h in v1.region_history] and v1.num_resets >= 12
    assert v1.obs_dim == 21
    trees = {"Barren": 0, "Forest": 24, "Highland": 9}
    kind = {"Barren": "clear", "Forest": "rain", "Highland": "snow"}
    for k, w in enumerate(v1.worlds):
        r, tag = v1.region_history[k][-1], v1.forest_history[k][-1]
        assert w.weather_stats()["region"] == r and w.weather_stats()["kind"] == kind[r]
        if tag == "unreal":
            assert len(w.obstacles) == trees[r]
        else:
            assert tag.startswith("rand ") and len(w.obstacles) == int(tag.rsplit("n=", 1)[1])
    tags = [t for h in v1.forest_history for t in h]
    assert any(t == "unreal" for t in tags) and any(t.startswith("rand") for t in tags)


def test_random_forest_share_about_half():
    """세계 꼴 몫 ≈ share (메타 난수 400 세계)·밀도 고름. 학습 시작 비용이 큰 세계 생성 없이 꼴 뽑기만 센다."""
    cfg = load_v2_config(R5).replace(N=8)
    v = MultiWorldVecEnv(cfg, num_worlds=1, reset_interval=10 ** 9, meta_seed=0)
    v._rm_cfgs = {r: v._rm_cfgs[r] for r in v._rm_cfgs}
    n_rand, us = 0, []
    for _ in range(400):
        _, tag = v._forest_cfg(v._pick_region())
        if tag != "unreal":
            n_rand += 1
            us.append(float(tag.split("u=")[1].split()[0]))
    assert 160 <= n_rand <= 240
    assert 0.0 <= min(us) < 0.1 and 0.9 < max(us) <= 1.0


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
    return dict(hashes=hs, seeds=venv.seed_history, regions=venv.region_history, resets=venv.num_resets, counts=cnt)


jobs = json.loads(open(sys.argv[1], encoding="utf-8").read())
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps([run(j) for j in jobs]))
'''


def test_without_random_forest_bit_identical_to_head(tmp_path):
    """random_forest 키가 없는 설정(R4·R3 학습)의 VecEnv: 관측·보상·끝·terminal_obs·교체 시드·지역 차례·학습 기록 수가 직전 코드(51b7507)와 같다."""
    tum = _module("_tum_for_r5", ROOT / "tests" / "test_unreal_mirror.py")
    old_root = tum._archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    vec = tmp_path / "vec.py"
    vec.write_text(VEC_SRC, encoding="utf-8")
    jobs = [dict(config="configs/v3_r4_train.yaml", N=16, K=3, T=30, meta=5, steps=100),
            dict(config="configs/v3_r3.yaml", N=16, K=2, T=40, meta=3, steps=80)]
    procs = []
    for root, tag in ((old_root, "old"), (ROOT, "new")):
        jp, op = tmp_path / f"jobs_{tag}.json", tmp_path / f"out_{tag}.json"
        jp.write_text(json.dumps(jobs), encoding="utf-8")
        procs.append((tag, subprocess.Popen([sys.executable, str(vec), str(jp), str(op)], cwd=root), op))
    outs = {}
    for tag, p, op in procs:
        assert p.wait(timeout=900) == 0, tag
        outs[tag] = json.loads(op.read_text(encoding="utf-8"))
    for j, a, b in zip(jobs, outs["old"], outs["new"]):
        assert a == b, j


@pytest.mark.skipif(not (R1_MODEL.exists() and ZERO_MODEL.exists()), reason="ckpt 가 없다(저장소 밖)")
def test_warm_start_acts_like_r1bf():
    """시작 모델(새 세 열 0)의 행동 = R1b-F: 무작위 관측(마스크 여러 꼴)에서 로짓·masked argmax 가 같고, 관측 21 세계 롤아웃이 관측 18 세계 롤아웃과
    스텝마다 행동·자리가 같다(두 세계는 관측 말고 같다)."""
    from stable_baselines3 import PPO

    import torch as th
    from env_v2 import rollout as ro

    from env_v2.rep_policy import is_rep_file

    assert is_rep_file(R1_MODEL) and is_rep_file(ZERO_MODEL)            # 설명 칸을 뺀 zip 도 --init-from-model 이 받는다
    m18, m21 = PPO.load(str(R1_MODEL), device="cpu"), PPO.load(str(ZERO_MODEL), device="cpu")
    rng = np.random.default_rng(32097)
    obs = rng.random((2048, 21), dtype=np.float32)
    obs[:512, 18:] = rng.integers(0, 2, (512, 3)).astype(np.float32)     # 끝값(0·1) 섞기
    mask = (rng.random((2048, 5)) < 0.6).astype(np.float32)
    mask[:, 0] = 1.0
    with th.no_grad():
        outs = []
        for m, x in ((m18, obs[:, :18]), (m21, obs)):
            t, _ = m.policy.obs_to_tensor(np.concatenate([x, mask], 1))
            lat = m.policy.mlp_extractor(m.policy.extract_features(t))
            outs.append(m.policy.action_net(lat[0]).numpy())
    np.testing.assert_array_equal(outs[0], outs[1])
    big = -1e9
    np.testing.assert_array_equal(np.where(mask > 0, outs[0], big).argmax(1), np.where(mask > 0, outs[1], big).argmax(1))

    def world(path, model):
        c = load_v2_config(path).replace(N=48)
        w = World(c, seeds=[32096])
        pol = ro.build_policy({"kind": "rep_learned", "path": str(model)}, 32096)
        ro.forward_bind(pol, w)
        return w, pol

    (w18, p18), (w21, p21) = world(WILD3, R1_MODEL), world(OBS, ZERO_MODEL)
    assert (w18.obs_dim, w21.obs_dim) == (18, 21)
    for _ in range(400):
        o18, o21 = w18.observe(), w21.observe()
        np.testing.assert_array_equal(o18, o21[:, :18])
        a18, a21 = np.asarray(p18(o18)), np.asarray(p21(o21))
        np.testing.assert_array_equal(a18, a21)
        w18.step(a18.astype(np.float64))
        w21.step(a21.astype(np.float64))
        np.testing.assert_array_equal(w18.pos, w21.pos)
