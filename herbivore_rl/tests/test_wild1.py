"""야생 1단계 — 기능 wild_reserve(27)·wild_satiation(28)·wild_flight(29)와 설정 configs/v3_wild1_mirror.yaml (10-15 사용자 '야생 생태계 규칙',
'사슴이 굶어도 좀 버티도록'. 명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md, 정의·식은 env_v2/world.py 모듈 docstring '야생 1단계').

비트 동일: 직전 커밋(d118c23 을 git archive 로 푼 사본)의 코드와 기존 설정(v3_unreal_mirror·v3_r3_on·v3_r1_on)의 궤적·통계·v1 난수 상태·기능 스트림이
같고(R1b 롤아웃 포함), 야생 설정에서 새 블록 셋을 끄고 R3 시야·청각 두 블록을 빼면 직전 코드의 거울 설정과 같다.
규칙 단위 시험: 비축 계산(모자람·바닥·채움, 굶음까지 스텝 수), 중립 값(시작 비축 0·채움 0·약함 1 = 끈 세계), 포만 시간(먹기 뒤 정확히 sat 스텝),
도주 반사는 사냥 중인 늑대만 도주를 일으킨다(먹는·쉬는 늑대 = 경계, 자는 늑대 = 없음), 경계 중에도 먹는다, 도주 덮기는 FLEE 로 들어간다.
시드는 탐색 32084~32099 만 쓴다.
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
from env_v2 import features as F
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import (GAIT_WALK, WF_ALERT, WF_NONE, WF_PANIC, WF_SHELTER, World, wild_days_to_steps)

CFG = ROOT / "configs"
MIRROR = CFG / "v3_unreal_mirror.yaml"
WILD = CFG / "v3_wild1_mirror.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "d118c23"              # 야생 1단계 직전 커밋(언리얼 거울) — 비트 동일 기준
WILD_NAMES = ("wild_reserve", "wild_satiation", "wild_flight")
EXTRA = ("realism_vision", "realism_hearing")

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _tum():
    spec = importlib.util.spec_from_file_location("_tum_for_wild1", ROOT / "tests" / "test_unreal_mirror.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _only(*names, n=16):
    """야생 설정에서 names 만 켠(나머지 wild_* 끔) 작은 세계 설정."""
    cfg = load_v2_config(WILD).replace(N=n)
    return _with(cfg, **{k: dict(enabled=k in names) for k in WILD_NAMES})


def _graze(w):
    return np.full((w.N, 1), float(rep.GRAZE))


# --------------------------------------------------------------------- #
# 등록부·설정
# --------------------------------------------------------------------- #


def test_registry_and_config():
    assert [F.FEATURE_IDS[k] for k in WILD_NAMES] == [27, 28, 29]
    assert set(WILD_NAMES) <= F.IMPLEMENTED
    raw_w = yaml.safe_load(WILD.read_text(encoding="utf-8"))
    raw_m = yaml.safe_load(MIRROR.read_text(encoding="utf-8"))
    # 야생 설정 = 거울 설정 + 다섯 블록(나머지 키는 모두 같다)
    fw = dict(raw_w["features"])
    for k in WILD_NAMES + EXTRA:
        assert fw.pop(k)["enabled"] is True
    assert fw == raw_m["features"]
    assert {k: v for k, v in raw_w.items() if k not in ("features", "version")} == \
        {k: v for k, v in raw_m.items() if k not in ("features", "version")}
    # R3 세계의 시야·청각 값 그대로
    raw_r3 = yaml.safe_load((CFG / "v3_r3.yaml").read_text(encoding="utf-8"))
    for k in EXTRA:
        assert raw_w["features"][k] == raw_r3["features"][k]
    w = World(load_v2_config(WILD).replace(N=16), seeds=[32084])
    assert w.features.active[-3:] == WILD_NAMES and set(EXTRA) <= set(w.features.active)
    assert w.obs_dim == 18 and w.alive is not None          # 관측 18칸 그대로, 부활 없음
    assert w._wr_cap == pytest.approx(3.0 * 900 * 0.002) and w._ws_sat_steps == 450
    assert wild_days_to_steps(0.5, 900) == 450 and wild_days_to_steps(0.5, 9000) == 4500
    assert wild_days_to_steps(3.0, 900) == 2700


def test_params_validation():
    base = load_v2_config(WILD).replace(N=8)
    bad = [("wild_reserve", dict(reserve_days=0.0)), ("wild_reserve", dict(init=1.5)), ("wild_reserve", dict(weak_speed=1.2)),
           ("wild_satiation", dict(sat_days=-1.0)), ("wild_satiation", dict(rest_speed=2.0)),
           ("wild_flight", dict(flight_r=16.0)), ("wild_flight", dict(crouch=1)), ("wild_flight", dict(alert_r=25.0))]
    for name, kw in bad:
        with pytest.raises(ValueError):
            World(_with(base, **{name: kw}), seeds=[32084])
    with pytest.raises(ValueError, match="repertoire"):
        World(_with(base, repertoire=dict(enabled=False), integrated_stage=dict(enabled=False), wild_reserve=dict(enabled=False),
                    wild_satiation=dict(enabled=False), realism_vision=dict(enabled=False),
                    realism_hearing=dict(enabled=False), realism_night=dict(enabled=False)), seeds=[32084])


def test_vec_env_refuses_wild1():
    from env_v2.vec_env import MultiWorldVecEnv

    with pytest.raises(ValueError, match="respawn false"):
        MultiWorldVecEnv(load_v2_config(WILD), num_worlds=1)


# --------------------------------------------------------------------- #
# 비트 동일
# --------------------------------------------------------------------- #


def test_flags_off_bit_identical_to_head(tmp_path):
    """직전 코드(d118c23)와: 기존 설정 셋은 그대로, 야생 설정에서 wild_* 를 끄고 시야·청각을 뺀 세계는 거울 설정과 궤적·통계·난수가 같다."""
    tum = _tum()
    old_root = tum._archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(tum.TRACE_SRC % dict(keys=tum.KEYS, stats=tum.STATS), encoding="utf-8")
    small = {"N": 16, "rand": dict(load_v2_config(CFG / "v3_r1_on.yaml").rand, world_size=[60.0, 60.0])}
    jobs = [dict(config="configs/v3_r1_on.yaml", seed=32085, steps=250, policy="rand", v1=small),
            dict(config="configs/v3_r3_on.yaml", seed=32086, steps=250, policy="rand"),
            dict(config="configs/v3_unreal_mirror.yaml", seed=32087, steps=300, policy="rand")]
    if R1_MODEL.exists():
        jobs.append(dict(config="configs/v3_unreal_mirror.yaml", seed=32088, steps=300, policy="model", model=str(R1_MODEL)))
    old = [dict(j) for j in jobs]
    new = [dict(j) for j in jobs]
    off = {k: {"enabled": False} for k in WILD_NAMES}
    for seed, pol in ((32089, "rand"), (32090, "model")):
        if pol == "model" and not R1_MODEL.exists():
            continue
        j = dict(seed=seed, steps=300, policy=pol, model=str(R1_MODEL))
        old.append(dict(j, config="configs/v3_unreal_mirror.yaml"))
        new.append(dict(j, config="configs/v3_wild1_mirror.yaml", drop=list(EXTRA), set=off))
    procs = []
    for root, js, tag in ((old_root, old, "old"), (ROOT, new, "new")):
        jp, op = tmp_path / f"jobs_{tag}.json", tmp_path / f"out_{tag}.json"
        jp.write_text(json.dumps(js), encoding="utf-8")
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


def _trace(w, steps):
    out = []
    for _ in range(steps):
        o = w.observe()
        res = w.step(_graze(w) if w.t % 7 else np.full((w.N, 1), float(rep.FLEE)))
        out.append((o.copy(),) + tuple(np.copy(x) for x in res) + (w.pos.copy(), w.pred_pos.copy(), w.energy.copy()))
    return out


def test_neutral_reserve_equals_off():
    """비축 중립 값(시작 비축 0, 채움 0, 약함 1)은 비축을 끈 세계와 같다 — 모자람은 그대로 E < 0 이고 굶음 판정이 같다."""
    on = _with(_only("wild_reserve"), wild_reserve=dict(init=0.0, refill_frac=0.0, weak_speed=1.0))
    a, b = World(on, seeds=[32091]), World(_only(), seeds=[32091])
    for x, y in zip(_trace(a, 400), _trace(b, 400)):
        for u, v in zip(x, y):
            np.testing.assert_array_equal(u, v)
    assert a._starve_deaths == b._starve_deaths and a._pred_deaths == b._pred_deaths


# --------------------------------------------------------------------- #
# (w1) 지방 비축
# --------------------------------------------------------------------- #


def test_reserve_math():
    w = World(_only("wild_reserve", n=4), seeds=[32092])
    cap = w._wr_cap
    w.reserve = np.array([1.0, 0.001, 0.5, 1.0])
    w.weak = np.zeros(4, dtype=bool)
    e = w._wild_reserve_step(np.array([-0.01, -0.01, 0.8, 0.8]), np.array([0.0, 0.0, 0.02, 0.02]), None)
    # 0: 모자람을 다 채움 → E 0, R − 0.01/C.  1: 비축이 모자람 → R 0, E = 남은 모자람(< 0).  2: E ≥ 0.7 이고 먹음 → 1/4 을 비축으로.  3: 비축 가득 → 그대로
    np.testing.assert_allclose(e, [0.0, -0.01 + 0.001 * cap, 0.8 - 0.25 * 0.02, 0.8])
    np.testing.assert_allclose(w.reserve, [1.0 - 0.01 / cap, 0.0, 0.5 + 0.25 * 0.02 / cap, 1.0])
    # 굶음까지: E 0.5 에서 걷기 대사 0.002 만 쓰면 250 스텝 뒤 E 가 바닥나고 비축 3일(2700 스텝)을 더 버틴다
    w.reserve = np.array([1.0])
    w.N = 1
    w.weak = np.zeros(1, dtype=bool)
    e, t = np.array([0.5]), 0
    while not (e[0] <= 0.0 and w.reserve[0] <= 0.0):
        e = w._wild_reserve_step(e - 0.002, np.zeros(1), None)
        t += 1
    assert abs(t - (250 + 2700)) <= 1


def test_reserve_in_world_starvation_needs_empty_reserve():
    """먹이 없는 세계: 비축을 켜면 E 가 0 이 돼도 죽지 않고(약해져 느리다), 끈 세계는 E ≤ 0 에서 굶어 죽는다."""
    def starve_world(cfg):
        w = World(cfg, seeds=[32093])
        w.food[:] = 0.0
        w.food_cap[:] = 0.0
        w.regen_field[:] = 0.0
        w.pred_cd[:] = 10 ** 6          # 늑대가 사냥하지 않게(내내 먹는 중)
        w._g = w._geometry()
        w._obs = w._obs_from(w._g)
        return w
    on, off = starve_world(_only("wild_reserve")), starve_world(_only())
    for _ in range(400):
        on.step(_graze(on))
        off.step(_graze(off))
    assert off._starve_deaths > 0 and on._starve_deaths == 0
    assert (on.energy[on.alive] <= 0.0).all() and (on.reserve < 1.0).all() and (on.reserve > 0.0).all()
    assert on.weak.all()
    # 약한 사슴은 이동 속력 × 0.75 (걷기 0.24 → 0.18)
    sp = np.linalg.norm(on.vel, axis=1)
    moving = sp > 1e-9
    assert moving.any()
    np.testing.assert_allclose(sp[moving], 0.6 * 0.4 * 0.75)


# --------------------------------------------------------------------- #
# (w2) 늑대 포만
# --------------------------------------------------------------------- #


def test_satiation_timing():
    """먹기(38스텝 쿨다운 — 포획 스텝 뒤 37스텝)가 끝난 뒤 정확히 sat 스텝 동안 배불러 사냥하지 않고(표적 없음), 그다음 다시 사냥할 수 있다."""
    w = World(_only("wild_satiation"), seeds=[32094])
    w.pred_cd[0] = 38
    w.pred_sat[0] = w._ws_sat_steps
    sated, cd_steps = [], 0
    for _ in range(38 + 450 + 5):
        w.step(_graze(w))
        cd_steps += int(w.pred_cd[0] > 0)
        sated.append(bool(w.pred_sated[0]))
        if w.pred_sated[0]:
            assert w.pred_target[0] == -1
    assert cd_steps == 37 and sum(sated) == 450
    first = sated.index(True)
    assert first == 37 and not any(sated[first + 450:])
    assert w.pred_sat[0] == 0


def test_catch_sets_satiation():
    w = World(_only("wild_satiation", n=64), seeds=[32095])
    for _ in range(1800):
        k0 = w._ws_kills_n
        w.step(_graze(w))
        if w._ws_kills_n > k0:
            m = int(np.flatnonzero(w.pred_cd == w.cfg.pred_eat_cd)[0])
            assert w.pred_sat[m] == 450
            break
    else:
        pytest.fail("1800 스텝 안에 포획이 없다")
    st = w.wild_stats()
    assert st["wolf_kills_n"] >= 1 and 0.0 <= st["sated_frac"] <= 1.0


# --------------------------------------------------------------------- #
# (w3) 도주 반사 거리
# --------------------------------------------------------------------- #


def _reflex_world(seed=32096):
    w = World(_only("wild_flight", "wild_satiation", n=4), seeds=[seed])
    w.pred_asleep[:] = False
    w.pred_cd[:] = 0
    w.pred_vel[:] = 0.0
    w.pred_target = np.full(w.M, -1, dtype=np.int64)
    # 사슴 4마리를 무대 가운데 줄에, 모두 +x 를 본다. 늑대 1 은 멀리
    w.pos[:] = [[30.0, 10.0], [30.0, 20.0], [30.0, 30.0], [30.0, 40.0]]
    w.head[:] = [1.0, 0.0]
    w.pred_pos[1] = [-500.0, -500.0]
    w.cov_c = np.array([[0.0, 0.0]])
    w.cov_r = np.array([0.5])
    return w


def _mode_with_wolf(w, deer, d, **state):
    w.pred_pos[0] = w.pos[deer] + [d, 0.0]
    for k, v in state.items():
        getattr(w, k)[0] = v
    w._g = w._geometry()
    w.wf_mode[:] = WF_NONE
    w._wf_update(np.zeros(w.N, dtype=bool))
    return int(w.wf_mode[deer])


def test_reflex_triggers_only_on_hunting_wolves():
    w = _reflex_world()
    assert _mode_with_wolf(w, 2, 5.0) == WF_PANIC                     # 사냥 중, 도주 거리 7.5 안
    assert _mode_with_wolf(w, 2, 8.5) == WF_ALERT                     # 사냥 중, 경계 거리 안·도주 거리 밖, 다가오지 않음
    assert _mode_with_wolf(w, 2, 5.0, pred_cd=10) == WF_ALERT         # 먹는 늑대 = 경계만
    assert _mode_with_wolf(w, 2, 5.0, pred_cd=0, pred_sat=100) == WF_ALERT    # 배부른 늑대 = 경계만
    w.pred_sat[0] = 0
    assert _mode_with_wolf(w, 2, 5.0, pred_asleep=True) == WF_NONE    # 자는 늑대는 보이지 않는다
    w.pred_asleep[0] = False
    w.pred_target[0] = 2                                               # 이 사슴을 쫓음 = 다가옴 → 경계 거리 안이면 도주
    assert _mode_with_wolf(w, 2, 8.5) == WF_PANIC
    w.pred_target[0] = -1
    # 도주 방향 = 늑대 반대(-x)
    _mode_with_wolf(w, 2, 5.0)
    np.testing.assert_allclose(w.wf_dir[2], [-1.0, 0.0], atol=1e-12)
    # 쉬는 늑대 경계는 rest_alert false 면 없다
    w._wf = dict(w._wf, rest_alert=False)
    assert _mode_with_wolf(w, 2, 5.0, pred_cd=10) == WF_NONE
    # 은신처 안에서 사냥 중인 늑대를 알아채면 웅크림
    w.pred_cd[0] = 0
    w.cov_c = np.array([[30.0, 30.0]])
    w.cov_r = np.array([3.0])
    assert _mode_with_wolf(w, 2, 5.0) == WF_SHELTER


def test_panic_continues_until_safe_and_prefers_shelter():
    w = _reflex_world()
    assert _mode_with_wolf(w, 2, 5.0) == WF_PANIC
    # 지난 도주: 사냥 중인 늑대가 안전 거리 20 안이면(보이지 않아도) 계속, 밖이면 풀림
    w.pred_pos[0] = w.pos[2] + [-15.0, 0.0]                           # 바로 뒤(사각) 15
    w._g = w._geometry()
    w.wf_mode[2] = WF_PANIC
    w._wf_update(np.zeros(w.N, dtype=bool))
    assert w.wf_mode[2] == WF_PANIC
    w.pred_pos[0] = w.pos[2] + [-21.0, 0.0]
    w._g = w._geometry()
    w._rs.lock_left[2] = 5
    w._wf_update(np.zeros(w.N, dtype=bool))
    assert w.wf_mode[2] == WF_NONE and w._rs.lock_left[2] == 0        # 풀리면 두뇌가 곧바로 고른다
    # 늑대 반대쪽(±60°) 은신처가 있으면 그쪽으로: 늑대 +x, 은신처 (-x, +y 쪽 45°)
    w.cov_c = np.array([[25.0, 35.0]])
    w.cov_r = np.array([2.0])
    assert _mode_with_wolf(w, 2, 5.0) == WF_PANIC
    np.testing.assert_allclose(w.wf_dir[2], [-np.sqrt(0.5), np.sqrt(0.5)], atol=1e-12)


def test_alert_keeps_grazing_and_panic_enters_flee():
    w = World(_only("wild_flight", n=8), seeds=[32097])
    w._wf = dict(w._wf, alert_w=100.0)          # 멀어지는 항이 GRAZE 조향보다 훨씬 크게(방향 확인용)
    for _ in range(3):
        w.step(_graze(w))
    w.wf_mode[:] = WF_NONE
    w.wf_mode[0], w.wf_dir[0] = WF_ALERT, [0.0, 1.0]
    w.wf_mode[1], w.wf_dir[1] = WF_PANIC, [1.0, 0.0]
    assert w._rs.behavior[0] == rep.GRAZE and w._rs.behavior[1] == rep.GRAZE
    w.step(_graze(w))
    assert w._rs.behavior[0] == rep.GRAZE and w.gait[0] == GAIT_WALK
    assert w._rep_eat[0] == pytest.approx(0.5) and w._rep_see[0] == 1.0      # 걸으며 먹고 고개를 든다
    assert w.vel[0] @ np.array([0.0, 1.0]) > 0.99 * 0.24 and np.linalg.norm(w.vel[0]) == pytest.approx(0.24)
    assert w._rs.behavior[1] == rep.FLEE                                    # 두뇌 요청(GRAZE) 대신 도주
