"""10-27 고침 — 먹기 걷기 고침(features.repertoire 선택 키 graze_* — env_v2/repertoire.py `graze_calm_dir`)·거리 두기(쉬는 늑대, features.wild_flight 선택 키
rest_keep* — env_v2/world.py 모듈 docstring '거리 두기')와 설정 configs/v3_wild3_calm_mirror.yaml·v3_wild3_route5_calm_mirror.yaml·v3_r7_calm_train.yaml
(사용자 10-27 '평소 사슴이 갈 곳을 못 정하고 방향만 왔다갔다 하며 제자리에서 미친 듯이 돈다'·'늑대가 쉬고 있어도 아주 잘 보이는 데서 사슴이 멈춰 있는 게
이상하다 — 늑대 시야 밖까지 물러난 뒤 쉬게').

비트 동일: 직전 커밋(4e3afd7 을 git archive 로 푼 사본)의 코드와 기존 설정(v3_wild3_mirror — R1b 롤아웃 포함, v3_wild3_route5_mirror, v3_r7_train 부활 세계,
v3_wild1_mirror)의 궤적·통계·v1 난수 상태가 같고, 고침 설정에서 두 고침을 끔 값으로 적으면 직전 코드의 바탕 설정과 같다.
규칙 단위 시험: 선택 키 끔 값·검사, 설정 생성기, 벽에 붙은 먹기 걷기가 안쪽으로 돌아선다, 거리 두기는 걸어서 물러나고 도망 기록에 들지 않는다, 쉬는 늑대 경계를
대신한다, 띠는 쉬는 늑대 쪽 성분을 지운다, 덮기 줄(마스크)이 아니다, 통계 칸은 켠 세계만, 평가기 world 블록·적응 변환이 키를 옮긴다.
시드는 탐색 32081~32099 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
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
from env_v2.world import GAIT_STOP, GAIT_WALK, WF_ALERT, WF_NONE, WF_PANIC, WF_REST, World

CFG = ROOT / "configs"
MIRROR = CFG / "v3_wild3_mirror.yaml"
CALM = CFG / "v3_wild3_calm_mirror.yaml"
ROUTE5 = CFG / "v3_wild3_route5_mirror.yaml"
ROUTE5_CALM = CFG / "v3_wild3_route5_calm_mirror.yaml"
R7 = CFG / "v3_r7_train.yaml"
R7_CALM = CFG / "v3_r7_calm_train.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "4e3afd7"              # 10-27 고침 직전 커밋 — 비트 동일 기준
GRAZE_OFF = {k: 0.0 for k in rep.GRAZE_CALM_KEYS}
REST_OFF = {"rest_keep": False}

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


def _graze(w):
    return np.full((w.N, 1), float(rep.GRAZE))


# --------------------------------------------------------------------- #
# 등록부·설정
# --------------------------------------------------------------------- #


def test_optional_keys_default_off_and_validation():
    assert dict(F.OPTIONAL_KEYS["repertoire"]) == GRAZE_OFF
    ow = F.OPTIONAL_KEYS["wild_flight"]
    assert (ow["rest_keep"], ow["rest_keep_margin"], ow["rest_keep_band"], ow["rest_keep_asleep"]) == (False, 2.0, 0.0, False)
    w = World(load_v2_config(MIRROR).replace(N=8), seeds=[32081])
    assert w._rp["calm"] is False and w._wf["rest_keep"] is False and all(w._rp[k] == 0.0 for k in rep.GRAZE_CALM_KEYS)
    w = World(load_v2_config(CALM).replace(N=8), seeds=[32081])
    assert w._rp["calm"] is True and w._wf["rest_keep"] is True
    assert (w._rp["graze_edge_r"], w._rp["graze_edge_w"], w._rp["graze_inertia"], w._rp["graze_wall_margin"]) == (2.0, 2.5, 0.5, 1.0)
    assert (w._wf["rest_keep_margin"], w._wf["rest_keep_band"], w._wf["rest_keep_asleep"]) == (2.0, 4.0, False)
    # 가장자리 항은 거리·무게 둘 다 있어야 켠다 (하나만이면 끈 세계와 같다)
    assert World(_with(load_v2_config(MIRROR).replace(N=8), repertoire=dict(graze_edge_r=2.0)), seeds=[32081])._rp["calm"] is False
    for bad in (dict(repertoire=dict(graze_edge_r=-1.0)), dict(repertoire=dict(graze_inertia=float("inf"))), dict(repertoire=dict(graze_wall_margin=True)),
                dict(wild_flight=dict(rest_keep=1)), dict(wild_flight=dict(rest_keep_band=-0.1)), dict(wild_flight=dict(rest_keep_asleep=True)),
                dict(repertoire=dict(graze_edge_x=1.0))):
        with pytest.raises(ValueError):
            World(_with(load_v2_config(MIRROR).replace(N=8), **bad), seeds=[32081])


def test_calm_configs_fresh_and_only_new_keys():
    """설정 생성기 결과 = 올린 파일, 세 파일은 바탕과 version·두 블록의 새 칸만 다르다."""
    mk = _module("_make_calm_configs", ROOT / "results" / "v3" / "calm" / "make_calm_configs.py")
    for out_name, src_name, head, vo, vn in mk.SETS:
        assert (CFG / out_name).read_text(encoding="utf-8") == mk.build(src_name, head, vo, vn)
        a = yaml.safe_load((CFG / src_name).read_text(encoding="utf-8"))
        b = yaml.safe_load((CFG / out_name).read_text(encoding="utf-8"))
        assert b["version"] == a["version"] + "calm"
        assert {k: v for k, v in b["features"]["repertoire"].items() if k not in mk.GRAZE} == a["features"]["repertoire"]
        assert {k: b["features"]["repertoire"][k] for k in mk.GRAZE} == mk.GRAZE
        assert {k: v for k, v in b["features"]["wild_flight"].items() if k not in mk.REST} == a["features"]["wild_flight"]
        assert {k: b["features"]["wild_flight"][k] for k in mk.REST} == mk.REST
        fa = {k: v for k, v in a["features"].items() if k not in ("repertoire", "wild_flight")}
        fb = {k: v for k, v in b["features"].items() if k not in ("repertoire", "wild_flight")}
        assert fa == fb
        assert {k: v for k, v in a.items() if k not in ("features", "version")} == {k: v for k, v in b.items() if k not in ("features", "version")}


# --------------------------------------------------------------------- #
# 비트 동일 (직전 커밋)
# --------------------------------------------------------------------- #


def _archive(tmp_path, commit):
    """커밋 commit 의 herbivore_rl 일부를 tmp 에 그대로 푼다(그 커밋은 이미 동족 차례 합이라 tests/kin_seq.py 고치기가 없다). git 이 없으면 None."""
    import io
    import tarfile

    paths = [f"herbivore_rl/{q}" for q in ("env", "env_v2", "policies", "configs", "repertoire_rules.py")]
    try:
        out = subprocess.run(["git", "archive", commit] + paths, cwd=ROOT.parent, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    with tarfile.open(fileobj=io.BytesIO(out.stdout)) as tf:
        tf.extractall(tmp_path / "base", **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return tmp_path / "base" / "herbivore_rl"


def test_keys_off_bit_identical_to_head(tmp_path):
    """직전 코드(4e3afd7)와: 기존 설정 넷은 그대로, 고침 설정 둘에서 두 고침을 끔 값으로 적으면 직전 코드의 바탕 설정과 궤적·통계·난수가 같다."""
    tum = _module("_tum_for_calm", ROOT / "tests" / "test_unreal_mirror.py")
    old_root = _archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    keys = tuple(tum.KEYS) + ("wf_mode", "wf_dir", "gait", "reserve")
    stats = tuple(tum.STATS) + ("wild_stats",)
    script = tmp_path / "trace.py"
    script.write_text(tum.TRACE_SRC % dict(keys=keys, stats=stats), encoding="utf-8")
    off = {"repertoire": GRAZE_OFF, "wild_flight": REST_OFF}
    old, new = [], []
    pairs = [(dict(config="configs/v3_wild3_mirror.yaml", seed=32086, steps=300, policy="rand"), None),
             (dict(config="configs/v3_wild1_mirror.yaml", seed=32087, steps=250, policy="rand"), None),
             (dict(config="configs/v3_r7_train.yaml", seed=32088, steps=250, policy="rand", v1={"N": 32}), None),
             (dict(config="configs/v3_wild3_mirror.yaml", seed=32089, steps=300, policy="rand"),
              dict(config="configs/v3_wild3_calm_mirror.yaml", set=off)),
             (dict(config="configs/v3_wild3_route5_mirror.yaml", seed=32090, steps=250, policy="rand"),
              dict(config="configs/v3_wild3_route5_calm_mirror.yaml", set=off)),
             (dict(config="configs/v3_r7_train.yaml", seed=32091, steps=200, policy="rand", v1={"N": 32}),
              dict(config="configs/v3_r7_calm_train.yaml", set=off))]
    if R1_MODEL.exists():
        pairs.append((dict(config="configs/v3_wild3_mirror.yaml", seed=32092, steps=300, policy="model", model=str(R1_MODEL)),
                      dict(config="configs/v3_wild3_calm_mirror.yaml", set=off)))
    for o, n in pairs:
        old.append(o)
        new.append(dict(o, **(n or {})))
    procs = []
    for root, js, tag in ((old_root, old, "old"), (ROOT, new, "new")):
        jp, op = tmp_path / f"jobs_{tag}.json", tmp_path / f"out_{tag}.json"
        jp.write_text(json.dumps(js), encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, str(script), str(jp), str(op)], cwd=root), op))
    outs = []
    for p, op in procs:
        assert p.wait(timeout=1200) == 0
        outs.append(json.loads(op.read_text(encoding="utf-8")))
    for j, a, b in zip(new, *outs):
        first = next((i for i, (x, y) in enumerate(zip(a["hashes"], b["hashes"])) if x != y), None)
        assert first is None and len(a["hashes"]) == len(b["hashes"]), (j, first)
        for k in ("stats", "rng", "obs_names", "streams"):
            assert a[k] == b[k], (j, k)


# --------------------------------------------------------------------- #
# 먹기 걷기 고침
# --------------------------------------------------------------------- #


def _calm_p(R=2.0, W=2.5, inertia=0.5, M=1.0):
    p = {"graze_edge_r": R, "graze_edge_w": W, "graze_inertia": inertia, "graze_wall_margin": M}
    p["calm"] = (R > 0 and W > 0) or inertia > 0 or M > 0
    return p


def test_graze_calm_dir_turns_inward_and_keeps_heading():
    raw = np.array([[-0.83, 0.05]])                                  # 먹이 기울기가 왼쪽 벽 쪽
    base = raw / np.linalg.norm(raw)
    head = np.array([[-1.0, 0.0]])
    # 벽 0.1 앞: 되돌림이 이겨 안쪽(+x)으로
    d = rep.graze_calm_dir(raw, base, np.array([[0.1, 30.0]]), head, 60.0, _calm_p())
    assert d[0, 0] > 0.0 and abs(np.linalg.norm(d[0]) - 1.0) < 1e-12
    # 가운데: 가장자리 항 없음, 관성만 — 원래 방향과 heading 사이
    d = rep.graze_calm_dir(raw, base, np.array([[30.0, 30.0]]), np.array([[0.0, 1.0]]), 60.0, _calm_p())
    assert d[0, 0] < 0.0 and d[0, 1] > base[0, 1]
    # 끔 계수 = 원래 방향 그대로
    d = rep.graze_calm_dir(raw, base, np.array([[0.1, 30.0]]), head, 60.0, _calm_p(0.0, 0.0, 0.0, 0.0))
    np.testing.assert_array_equal(d, base)
    # 관성이 원래 합을 지워 0 이면 원래 방향
    d = rep.graze_calm_dir(np.array([[-0.25, 0.0]]), np.array([[-1.0, 0.0]]), np.array([[30.0, 30.0]]), np.array([[0.5, 0.0]]), 60.0,
                           _calm_p(0.0, 0.0, 0.5, 0.0))
    np.testing.assert_array_equal(d, [[-1.0, 0.0]])
    # 벽 여유가 두 성분을 다 지우면 원래 방향
    d = rep.graze_calm_dir(np.array([[-0.6, -0.8]]), np.array([[-0.6, -0.8]]), np.array([[0.5, 0.5]]), np.array([[-0.6, -0.8]]), 60.0,
                           _calm_p(0.0, 0.0, 0.0, 1.0))
    np.testing.assert_array_equal(d, [[-0.6, -0.8]])


def _wall_world(cfg_path):
    w = World(load_v2_config(cfg_path).replace(N=8), seeds=[32093])
    w.pred_pos[:] = [[-500.0, -500.0]] * w.M                          # 늑대는 멀리 (보이지 않는다)
    w.pos[0] = [0.1, 30.0]
    w.head[0] = [-1.0, 0.0]
    w.cov_c = np.array([[50.0, 50.0]])
    w.cov_r = np.array([1.0])
    w._g = w._geometry()
    w._g["food_grad"][0] = [-1.0, 0.0]                                 # 먹이 기울기가 벽 쪽, 무리·분리 없음
    w._g["to_centroid"][0] = 0.0
    w._g["separation"][0] = 0.0
    ix, iy = w._cell_index(w.pos[0:1])
    w.food[iy[0], ix[0]] = 0.0                                          # 먹이 모자람 → 걷기
    w.wf_mode[:] = WF_NONE
    return w


def test_wall_pinned_grazer_turns_inward_only_when_on():
    off = _wall_world(MIRROR)
    off.step(_graze(off))
    assert off._rs.behavior[0] == rep.GRAZE and off.gait[0] == GAIT_WALK and off.vel[0, 0] < 0.0     # 끈 세계: 벽으로 걸어 붙는다
    on = _wall_world(CALM)
    on.step(_graze(on))
    assert on._rs.behavior[0] == rep.GRAZE and on.gait[0] == GAIT_WALK and on.vel[0, 0] > 0.0        # 켠 세계: 안쪽으로 돌아선다
    assert np.linalg.norm(on.vel[0]) == pytest.approx(np.linalg.norm(off.vel[0]))                  # 속력은 그대로 걷기


# --------------------------------------------------------------------- #
# 거리 두기 (쉬는 늑대)
# --------------------------------------------------------------------- #


def _rest_world(cfg_path=CALM, n=8, **wf):
    cfg = load_v2_config(cfg_path).replace(N=n)
    if wf:
        cfg = _with(cfg, wild_flight=wf)
    w = World(cfg, seeds=[32094])
    w.track_flight = True
    w.pos[:] = [[45.0 + 0.5 * i, 50.0] for i in range(n)]
    w.pos[2] = [30.0, 30.0]
    w.head[:] = [1.0, 0.0]
    w.pred_pos[:] = [[-500.0, -500.0]] * w.M
    w.pred_vel[:] = 0.0
    w.pred_asleep[:] = False
    w.pred_cd[:] = 0
    w.pred_sat[:] = 0
    w.cov_c = np.array([[5.0, 5.0]])
    w.cov_r = np.array([1.0])
    w.obstacles = np.zeros((0, 3))
    # 낮(d = 0)의 탐지 반경 (world.py `_daynight_update` 의 식 — 날씨 배수는 지금 값)
    w.dark = 0.0
    w._vis = 1.0
    w._see_pred = w.cfg.see_r * (w._vis * w._wx_sight)
    return w


def _mode(w, dx=8.0, dy=0.0, prev=WF_NONE, sat=100, cd=0):
    w.pred_pos[0] = w.pos[2] + [dx, dy]
    w.pred_sat[0], w.pred_cd[0] = sat, cd
    w._g = w._geometry()
    w.wf_mode[:] = WF_NONE
    w.wf_mode[2] = prev
    w._wf_update(np.zeros(w.N, dtype=bool))
    return int(w.wf_mode[2])


def test_rest_keep_replaces_rest_alert_and_respects_priority():
    old = _rest_world(MIRROR)
    assert _mode(old, 8.0) == WF_ALERT                                  # 끈 세계: 쉬는 늑대(배부름) = 경계(rest_alert)
    w = _rest_world()
    assert _mode(w, 8.0) == WF_REST                                     # 켠 세계: 거리 두기가 그 자리를 맡는다
    np.testing.assert_allclose(w.wf_dir[2], [-1.0, 0.0], atol=1e-12)
    assert _mode(w, 8.0, cd=10, sat=0) == WF_REST                       # 먹는 늑대도
    assert _mode(w, 8.0, sat=0) == WF_ALERT                             # 사냥 중인 늑대 = 경계 그대로 (거리 두기보다 앞)
    assert _mode(w, 5.0, sat=0) == WF_PANIC                             # 도주 거리 안 = 도주
    w.pred_asleep[0] = True
    assert _mode(w, 8.0) == WF_NONE                                     # 자는 늑대는 굴에 있어 안 보인다
    w.pred_asleep[0] = False
    V = w._wf_view()
    assert _mode(w, -(V - 1.0)) == WF_NONE                              # 바로 뒤(사각) — 알아채지 못함
    assert _mode(w, -(V + 1.0), prev=WF_REST) == WF_REST                # 지난 거리 두기 = 기억으로 V + 여유까지 이어짐
    assert _mode(w, -(V + w._wf["rest_keep_margin"] + 0.5), prev=WF_REST) == WF_NONE
    w.cov_c = np.array([[30.0, 30.0]])
    w.cov_r = np.array([3.0])
    assert _mode(w, 8.0) == WF_NONE                                     # 은신처 안 = 거리 두기 없음


def test_rest_keep_walks_away_and_is_not_flight():
    w = _rest_world()
    for _ in range(2):
        w.step(_graze(w))
    _mode(w, 8.0)
    assert w.wf_mode[2] == WF_REST
    started = w.flight_stats()["started"]
    w.step(_graze(w))
    assert w._rs.behavior[2] == rep.GRAZE and w.gait[2] == GAIT_WALK                      # 두뇌 행동 그대로(먹기) — 걸으며
    assert w.vel[2] @ np.array([1.0, 0.0]) < 0.0 and w._rep_see[2] == 1.0                 # 늑대(+x) 반대로, 고개를 든다
    assert w._rep_eat[2] == pytest.approx(0.5)                                             # 걸으며 먹는다
    f = w.flight_stats()
    assert f["started"] == started                                                         # 도망 기록·쫓김 사건에 들지 않는다 (FLEE 가 아님)
    ws = w.wild_stats()
    assert ws["rest_starts"] >= 1 and ws["mode_rest_frac"] > 0.0


def test_band_removes_component_toward_resting_wolf():
    w = _rest_world()
    w.pred_pos[0] = w.pos[2] + [w._wf_view() + 4.0, 0.0]               # 거리 두기 밖·띠 안
    w.pred_sat[0] = 100
    w.wf_mode[:] = WF_NONE
    w._rs.behavior[:] = rep.GRAZE
    sp, cfg = w._sp, w.cfg
    spd = cfg.herb_speed * sp["speed"][GAIT_WALK]
    vel = np.zeros((w.N, 2))
    vel[2] = np.array([np.sqrt(0.5), np.sqrt(0.5)]) * spd              # 늑대 쪽 비스듬히
    out = dict(vel=vel.copy(), gait=np.full(w.N, GAIT_WALK, dtype=np.int8), eat=np.full(w.N, 0.5), drain=np.ones(w.N), see=np.full(w.N, 0.6))
    w._wf_rest_band(out)
    assert out["vel"][2, 0] == pytest.approx(0.0, abs=1e-15) and out["vel"][2, 1] == pytest.approx(spd)
    out = dict(vel=np.tile([spd, 0.0], (w.N, 1)), gait=np.full(w.N, GAIT_WALK, dtype=np.int8), eat=np.full(w.N, 0.5), drain=np.ones(w.N),
               see=np.full(w.N, 0.6))
    w._wf_rest_band(out)
    assert out["gait"][2] == GAIT_STOP and not out["vel"][2].any() and out["eat"][2] == 1.0          # 곧장 늑대 쪽 = 멈춤
    out = dict(vel=np.tile([-spd, 0.0], (w.N, 1)), gait=np.full(w.N, GAIT_WALK, dtype=np.int8), eat=np.full(w.N, 0.5), drain=np.ones(w.N),
               see=np.full(w.N, 0.6))
    w._wf_rest_band(out)
    np.testing.assert_array_equal(out["vel"][2], [-spd, 0.0])                                        # 멀어지는 걸음은 그대로


def _rest_ctl(w, sep, dirv, pos=None):
    """사슴 2 를 덮기 REST·두뇌 GRAZE 로 두고 `_wf_rest_control` 만 돌린 속도 (2,)."""
    if pos is not None:
        w.pos[2] = pos
    w.wf_mode[:] = WF_NONE
    w.wf_mode[2] = WF_REST
    w.wf_dir = np.zeros((w.N, 2))
    w.wf_dir[2] = dirv
    w._rs.behavior[:] = rep.GRAZE
    sp = np.zeros((w.N, 2))
    sp[2] = sep
    out = dict(vel=np.zeros((w.N, 2)), gait=np.zeros(w.N, dtype=np.int8), eat=np.zeros(w.N), drain=np.ones(w.N), see=np.full(w.N, 0.6))
    w._wf_rest_control(out, dict(separation=sp))
    assert out["gait"][2] == GAIT_WALK and out["see"][2] == 1.0
    return out["vel"][2]


def test_rest_control_separation_never_pulls_back_or_into_wall():
    """10-27 적대적 검토: 거리 두기 걸음의 분리는 옆으로 비켜 가게만 한다 — 앞을 막은 동료의 분리가 덮기 방향을 지워 걸음이 앞뒤로 뒤집히거나(제자리 빙빙),
    벽을 따라 물러나는 사슴을 벽으로 밀어 붙잡지 않는다."""
    w = _rest_world()
    spd = w.cfg.herb_speed * w._sp["speed"][GAIT_WALK]
    v = _rest_ctl(w, [0.9, 0.0], [-1.0, 0.0])                          # 분리가 정면으로 덮기 방향 반대(1.35·0.9 > 1) — 처음 판은 늑대 쪽으로 걸었다
    np.testing.assert_allclose(v, [-spd, 0.0], atol=1e-15)
    v = _rest_ctl(w, [0.6, 0.8], [-1.0, 0.0])                          # 비스듬히 뒤 — 옆 성분만 남는다
    assert v[0] < 0.0 < v[1]
    v = _rest_ctl(w, [-0.5, 0.0], [-1.0, 0.0])                         # 앞으로 미는 분리는 그대로 (더 빨리 가지는 않는다 — 걷기 속력)
    np.testing.assert_allclose(v, [-spd, 0.0], atol=1e-15)
    v = _rest_ctl(w, [0.8, 0.1], [0.0, 1.0], pos=[w.size - 0.3, 30.0])   # 오른쪽 벽 앞, 벽을 따라 +y 로 물러나는데 분리가 벽 쪽
    assert v[0] == 0.0 and v[1] == pytest.approx(spd)
    w2 = _rest_world()
    v = _rest_ctl(w2, [0.8, 0.1], [0.0, 1.0], pos=[w2.size / 2, 30.0])  # 벽에서 멀면 벽 여유가 걸리지 않는다
    assert v[0] > 0.0


def test_rest_direction_inertia_only_when_continuing():
    """10-27 적대적 검토: 이어지는 거리 두기는 지난 덮기 방향을 이어받는다(n(반대 + 1·지난), 합 0 이면 반대 그대로). 시작·지난 경계는 잇지 않는다.
    벽 앞 정면 늑대에서는 벽을 따라 굽히는 쪽이 지난 쪽을 따른다(처음 판은 작은 좌우 차로 스텝마다 뒤집혔다)."""
    w = _rest_world()
    h = np.sqrt(0.5)

    def keep(prev, pdir, dx=8.0, dy=0.0):
        w.wf_dir = np.zeros((w.N, 2))
        w.wf_dir[2] = pdir
        return _mode(w, dx, dy, prev=prev), w.wf_dir[2].copy()

    m, d = keep(WF_REST, [0.0, 1.0])
    assert m == WF_REST
    np.testing.assert_allclose(d, [-h, h], atol=1e-15)
    for prev, pdir in ((WF_NONE, [0.0, 1.0]), (WF_ALERT, [0.0, 1.0]), (WF_REST, [1.0, 0.0]), (WF_REST, [0.0, 0.0])):
        m, d = keep(prev, pdir)
        assert m == WF_REST and d.tolist() == [-1.0, -0.0], (prev, pdir)
    w.pos[2] = [30.0, 1.5]                                              # 아래 벽 앞, 늑대는 바로 위(+y)
    w.head[2] = [0.0, 1.0]
    for side in (-1.0, 1.0):
        m, d = keep(WF_REST, [side, 0.0], dx=0.0, dy=10.0)
        assert m == WF_REST and np.sign(d[0]) == side and d[1] <= 0.0


def test_alert_walk_is_not_bent_by_graze_calm():
    """10-27 적대적 검토: 경계(사냥 늑대) 걷기에는 먹기 걷기 고침을 쓰지 않는다 — 켠 세계의 경계 속도가 끈 세계 식 n(G·0.83 + C·0.71 + 1.35·분리 + alert_w·덮기
    방향)과 같다. 처음 판은 가장자리 되돌림(2.5)이 alert_w(1.5)를 이겨 가장자리에서 사냥 늑대 쪽(안쪽)으로 걸었다."""
    w = _rest_world()
    assert w._rp["calm"]
    w.pos[2] = [0.5, 30.0]                                              # 왼쪽 벽 앞 (가장자리 되돌림·벽 여유 안)
    w.head[2] = [1.0, 0.0]
    w.wf_mode[:] = WF_NONE
    w.wf_mode[2] = WF_ALERT
    w.wf_dir = np.zeros((w.N, 2))
    w.wf_dir[2] = [0.0, 1.0]                                            # 늑대는 안쪽(+x) 아래 — 벽을 따라 +y 로 멀어진다
    w._rs.behavior[:] = rep.GRAZE
    g = np.zeros((w.N, 2))
    g[2] = [-1.0, 0.0]
    inp = dict(food_grad=g, to_centroid=np.zeros((w.N, 2)), separation=np.zeros((w.N, 2)))
    out = dict(vel=np.zeros((w.N, 2)), gait=np.zeros(w.N, dtype=np.int8), eat=np.zeros(w.N), drain=np.ones(w.N), see=np.full(w.N, 0.6))
    w._wf_alert_control(out, inp)
    want = np.array([-0.83, 1.5]) / np.hypot(0.83, 1.5) * (w.cfg.herb_speed * w._sp["speed"][GAIT_WALK])
    np.testing.assert_allclose(out["vel"][2], want, rtol=0, atol=1e-15)


def test_rest_keep_is_not_an_override_row():
    """거리 두기는 덮기 줄(도주·웅크림)이 아니다 — 두 길 판 5 세계의 rep_peek override 는 없음, 두뇌가 그대로 결정한다."""
    w = _rest_world(ROUTE5_CALM, n=8)
    _mode(w, 8.0)
    assert w.wf_mode[2] == WF_REST
    pk = w.rep_peek()
    assert int(pk["override"][2]) == WF_NONE


def test_wild_stats_rest_keys_only_when_on():
    w = World(load_v2_config(MIRROR).replace(N=8), seeds=[32095])
    w.step(_graze(w))
    ws = w.wild_stats()
    assert "mode_rest_frac" not in ws and "rest_starts" not in ws
    w = World(load_v2_config(CALM).replace(N=8), seeds=[32095])
    w.step(_graze(w))
    ws = w.wild_stats()
    assert {"mode_rest_frac", "rest_starts", "rest_steps", "rest_ends", "rest_reentry", "band_turn_steps", "band_stop_steps"} <= set(ws)


# --------------------------------------------------------------------- #
# 평가기 world 블록·적응 변환
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def ceval():
    return _module("_ceval_for_calm", ROOT / "results" / "v3" / "live" / "ceval.py")


def test_ceval_world_block_carries_calm_only_when_on(ceval):
    def wb(path):
        w = World(load_v2_config(path).replace(N=8), seeds=[32096])
        return ceval.world_block(w), ceval.unsupported_settings(w.cfg.to_dict())

    off, bad_off = wb(MIRROR)
    assert "graze_calm" not in off and not {"rest_keep", "rest_keep_margin", "rest_keep_band", "rest_keep_asleep"} & set(off["wild_flight"])
    on, bad_on = wb(CALM)
    assert on["graze_calm"] == {"graze_edge_r": 2.0, "graze_edge_w": 2.5, "graze_inertia": 0.5, "graze_wall_margin": 1.0}
    assert on["wild_flight"]["rest_keep"] is True and on["wild_flight"]["rest_keep_band"] == 4.0 and "rest_keep_margin" not in on["wild_flight"]
    assert bad_off == [] and bad_on == []


@pytest.mark.skipif(not R1_MODEL.exists(), reason="R1b s3 모델 zip 이 없다 (저장소 밖 ckpt)")
def test_adapt_maps_calm_keys():
    ad = _module("_adapt_for_calm", ROOT / "results" / "v3" / "adapt" / "adapt.py")
    snap = ad.load_snapshot(ROOT / "results" / "v3" / "adapt" / "unreal" / "eco_v3_snapshot_s20003_240s.json")
    ref = json.loads((ROOT / "results" / "v3" / "adapt" / "reference_snapshot.json").read_text(encoding="utf-8"))
    s = copy.deepcopy(snap)
    for r in s["regions"]:
        r["world"]["graze_calm"] = {"graze_edge_r": 2.0, "graze_edge_w": 2.5, "graze_inertia": 0.5, "graze_wall_margin": 1.0}
        r["world"]["wild_flight"].update(rest_keep=True, rest_keep_margin=2.0, rest_keep_band=4.0, rest_keep_asleep=False)
    s["settings"].update(rest_keep=True, graze_calm=True)
    out = ad.convert(s, ref)
    keys = {c["key"]: c["snapshot"] for c in out["record"]["changed"]}
    assert keys["features.repertoire.graze_edge_r"] == 2.0 and keys["features.repertoire.graze_inertia"] == 0.5
    assert keys["features.wild_flight.rest_keep"] is True and keys["features.wild_flight.rest_keep_band"] == 4.0
    assert "features.wild_flight.rest_keep_margin" not in keys                          # 끔 값과 같은 칸은 바꾸지 않는다
    f = out["world"]["features"]
    assert f["repertoire"]["graze_wall_margin"] == 1.0 and f["wild_flight"]["rest_keep"] is True
    w = World(load_v2_config(CALM).replace(N=8), seeds=[32097])
    assert w._rp["calm"] and w._wf["rest_keep"]
