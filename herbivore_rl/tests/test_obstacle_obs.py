"""R5 장애물 관측 — 기능 obstacle_obs(32), 설정 configs/v3_wild3_obs_mirror.yaml (10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 계획서
RL_V2_PLAN.md 10-19 (16), 계약 POLICY_CONTRACT_V3.md 2-4, 정의는 env_v2/world.py 모듈 docstring 'R5 장애물 관측').

비트 동일: 새 기능을 끈 세계는 직전 커밋(6fdf86e)의 코드와 궤적·통계·v1 난수 상태·관측 이름·기능 스트림이 같다(날씨 거울·R4 학습 세계·R1 판정 세계, R1b 롤아웃 포함).
켠 세계는 끈 세계와 동역학이 같고 관측 앞 칸이 비트 단위로 같다(관측만 맨 끝 세 칸이 붙는다).
식 시험: 손 사례(벽·원판 앞·접함·뒤·안에서 시작·겹친 원판·원판 없음·방향 고르기·가림의 엄격한 <·끝점 뒤 원판·길이 0), 세계 관측 = C++ 꼴 스칼라 참조(비트 단위,
벽 위·둘레 위·원판 안 사슴 포함), 리스폰 행, 마스크·계약 해시, 계수 검사, 설정 생성기 최신. 시드는 탐색 32090~32094 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import json
import math
import subprocess
import sys

import numpy as np
import pytest
import yaml

import env_v2.features as F
from env.config import ROOT
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import OB_EPS, OBSTACLE_OBS_NAMES, World, obs_names, obstacle_obs_values

CFG = ROOT / "configs"
WILD3 = CFG / "v3_wild3_mirror.yaml"
OBS = CFG / "v3_wild3_obs_mirror.yaml"
R4 = CFG / "v3_r4_train.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "6fdf86e"              # R5 장애물 관측 직전 커밋(적응 고리 문서) — 비트 동일 기준
ON = dict(enabled=True, escape_norm=10.0, near_norm=5.0)
EPS = 1e-9
HASH21 = 0xbc4fc2d45c47c5fd          # 관측 21(18 + 세 칸)·마스크 판 2 입출력 계약 해시(POLICY_CONTRACT_V3.md 2-4)

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


def _rand_beh(rng, n):
    return rng.integers(0, 3, (n, 1)).astype(np.float64)       # 먹기·도망·숨기 (거울 세계 허용)


# --------------------------------------------------------------------- #
# C++ 꼴 스칼라 참조 (모듈 docstring 'R5 장애물 관측' — 사슴 하나, 원판 순서대로)
# --------------------------------------------------------------------- #


def _ref_one(x, y, hx, hy, seen, awx, awy, tx_, ty_, discs, body_r, size, block):
    if seen and math.sqrt(awx * awx + awy * awy) > EPS:
        wx, wy = awx, awy
    else:
        wx, wy = hx, hy
    nw = math.sqrt(wx * wx + wy * wy)
    ux, uy = (wx / nw, wy / nw) if nw > EPS else (1.0, 0.0)
    tx = (size - x) / ux if ux > 0.0 else (x / (-ux) if ux < 0.0 else math.inf)
    ty = (size - y) / uy if uy > 0.0 else (y / (-uy) if uy < 0.0 else math.inf)
    e = min(tx, ty)
    if not e > 0.0:
        e = 0.0
    near = math.inf
    for cx, cy, r in discs:
        fx, fy = x - cx, y - cy
        R = r + body_r
        cc = fx * fx + fy * fy - R * R
        b = fx * ux + fy * uy
        d = b * b - cc
        if cc >= 0.0 and b < 0.0 and d >= 0.0:
            e = min(e, -b - math.sqrt(d))
        near = min(near, math.sqrt(fx * fx + fy * fy) - R)
    hid = False
    if seen and block:
        dx, dy = x - tx_, y - ty_
        dd = dx * dx + dy * dy
        for cx, cy, r in discs:
            gx, gy = cx - tx_, cy - ty_
            t = (gx * dx + gy * dy) / dd if dd > 0.0 else 0.0
            t = min(max(t, 0.0), 1.0)
            qx = tx_ + t * dx - cx
            qy = ty_ + t * dy - cy
            if qx * qx + qy * qy < r * r:
                hid = True
                break
    return e, near, hid


def _ref_obs(e, near, hid, en, nn):
    o1 = min(max(e / en, 0.0), 1.0)
    o2 = min(max((near if near > 0.0 else 0.0) / nn, 0.0), 1.0)
    return np.float32(o1), np.float32(o2), np.float32(1.0 if hid else 0.0)


def _vals(p, h, seen, away, threat, discs, body_r=0.15, size=60.0, block=True):
    return obstacle_obs_values(np.asarray(p, float).reshape(-1, 2), np.asarray(h, float).reshape(-1, 2), np.asarray(seen, bool).reshape(-1),
                               np.asarray(away, float).reshape(-1, 2), np.asarray(threat, float).reshape(-1, 2),
                               np.asarray(discs, float).reshape(-1, 3), body_r, size, block)


# --------------------------------------------------------------------- #
# 설정·등록부
# --------------------------------------------------------------------- #


def test_registry_names_and_order():
    """번호 32, 구현됨, 계수 둘. 관측 맨 끝 세 칸(R1b 세계 18 → 21, 앞 칸 번호 그대로). 경보 세계는 alarm_heard 뒤, v1 세계도 맨 끝."""
    assert F.FEATURE_IDS["obstacle_obs"] == 32 and "obstacle_obs" in F.IMPLEMENTED
    assert F.PARAM_KEYS["obstacle_obs"] == frozenset({"escape_norm", "near_norm"})
    assert OBSTACLE_OBS_NAMES == ("escape_room", "obstacle_near", "threat_hidden")
    n18 = obs_names(load_v2_config(WILD3))
    n21 = obs_names(load_v2_config(OBS))
    assert len(n18) == 18 and n21 == n18 + OBSTACLE_OBS_NAMES
    n19 = obs_names(load_v2_config(CFG / "v3_r2_on.yaml"))
    assert obs_names(_with(load_v2_config(CFG / "v3_r2_on.yaml"), obstacle_obs=ON)) == n19 + OBSTACLE_OBS_NAMES
    v1 = load_v2_config()
    assert obs_names(_with(v1, obstacle_obs=ON)) == obs_names(v1) + OBSTACLE_OBS_NAMES
    w = World(load_v2_config(OBS).replace(N=8), seeds=[32090])
    assert w.obs_dim == 21 and w._obs_oo == 18


def test_params_checked():
    base = load_v2_config(WILD3).replace(N=8)
    for kw in (dict(escape_norm=0.0), dict(near_norm=-1.0), dict(escape_norm=True), dict(near_norm=float("inf")), dict(escape_norm="10")):
        with pytest.raises(ValueError, match="obstacle_obs"):
            World(_with(base, obstacle_obs=dict(ON, **kw)), seeds=[32090])
    with pytest.raises(ValueError, match="obstacle_obs"):
        World(_with(base, obstacle_obs=dict(enabled=True, escape_norm=10.0)), seeds=[32090])       # 빠진 계수
    with pytest.raises(ValueError, match="obstacle_obs"):
        World(_with(base, obstacle_obs=dict(ON, escape=10.0)), seeds=[32090])                        # 모르는 키


def test_obs_config_is_wild3_plus_block():
    """v3_wild3_obs_mirror.yaml = v3_wild3_mirror.yaml + obstacle_obs(version 만 다르다), 분모 10·5 단위, 생성기가 최신."""
    a = yaml.safe_load(WILD3.read_text(encoding="utf-8"))
    b = yaml.safe_load(OBS.read_text(encoding="utf-8"))
    assert (a["version"], b["version"]) == ("3.wild3", "3.wild3obs")
    fa, fb = a.pop("features"), b.pop("features")
    a.pop("version"), b.pop("version")
    assert a == b and set(fb) - set(fa) == {"obstacle_obs"} and all(fa[k] == fb[k] for k in fa)
    assert fb["obstacle_obs"] == ON
    gen = _module("_make_obs_config", ROOT / "results" / "v3" / "r5" / "make_obs_config.py")
    assert gen.render() == OBS.read_text(encoding="utf-8")


# --------------------------------------------------------------------- #
# 켜도 세계는 그대로
# --------------------------------------------------------------------- #


def _same_dynamics(c_off, c_on, seed, steps, pol=None):
    w0, w1 = World(c_off, seeds=[seed]), World(c_on, seeds=[seed])
    k = w0.obs_dim
    assert w1.obs_names[:k] == w0.obs_names and w1.obs_names[k:] == OBSTACLE_OBS_NAMES
    rng = np.random.default_rng(seed)
    if pol is not None:
        from env_v2 import rollout as ro
        p0 = ro.build_policy({"kind": "rep_learned", "path": str(pol)}, seed)
        ro.forward_bind(p0, w0)
    np.testing.assert_array_equal(w0.observe(), w1.observe()[:, :k])
    for _ in range(steps):
        a = _rand_beh(rng, w0.N) if pol is None else np.asarray(p0(w0.observe()), dtype=np.float64)
        r0, r1 = w0.step(a), w1.step(a)
        np.testing.assert_array_equal(r0[0], r1[0][:, :k])
        np.testing.assert_array_equal(r0[3], r1[3][:, :k])
        for x, y in zip(r0[1:3], r1[1:3]):
            np.testing.assert_array_equal(x, y)
        assert np.isfinite(r1[0]).all() and (r1[0][:, k:] >= 0.0).all() and (r1[0][:, k:] <= 1.0).all()
    for key in ("pos", "head", "energy", "food", "pred_pos", "pred_head", "pred_cd", "pred_vel"):
        np.testing.assert_array_equal(getattr(w0, key), getattr(w1, key))
    assert str(w0.rng.bit_generator.state) == str(w1.rng.bit_generator.state)
    assert sorted(map(str, w0._feature_rngs)) == sorted(map(str, w1._feature_rngs))
    assert json.dumps(w0.stats()) == json.dumps(w1.stats()) and json.dumps(w0.hunt_stats()) == json.dumps(w1.hunt_stats())


def test_on_keeps_dynamics():
    """켠 세계 = 끈 세계(궤적·보상·끝·v1 난수·기능 스트림·통계), 관측 앞 칸 비트 단위. 날씨 거울(숲)·무작위 줄기 숲·R4 학습 세계(부활)·관측 9 세계."""
    c = load_v2_config(WILD3).replace(N=48)
    _same_dynamics(c, _with(c, obstacle_obs=ON), 32090, 300)
    dense = _with(c, obstacles=dict(fixed=None))                     # 무작위 배치(1 ha 줄기 250 + 바위 5)
    _same_dynamics(dense, _with(dense, obstacle_obs=ON), 32091, 300)
    r4 = load_v2_config(R4).replace(N=32)
    _same_dynamics(r4, _with(r4, obstacle_obs=ON), 32092, 400)
    r0 = load_v2_config(CFG / "v3_r0_on.yaml").replace(N=24)        # 관측 9(추가 칸 없음) 세계 — 끝에 세 칸
    _same_dynamics(r0, _with(r0, obstacle_obs=ON), 32093, 200)
    if R1_MODEL.exists():
        _same_dynamics(c, _with(c, obstacle_obs=ON), 32094, 300, pol=R1_MODEL)


def test_off_bit_identical_to_head(tmp_path):
    """직전 코드(6fdf86e)와: 날씨 거울·R4 학습 세계·R1 판정 세계·관측 21 설정의 블록을 끈 판의 궤적·통계·난수·관측 이름·기능 스트림이 같다(R1b 롤아웃 포함)."""
    tum = _module("_tum_for_obsobs", ROOT / "tests" / "test_unreal_mirror.py")
    old_root = tum._archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(tum.TRACE_SRC % dict(keys=tum.KEYS, stats=tum.STATS), encoding="utf-8")
    old = [dict(config=str(WILD3), seed=32090, steps=300, policy="rand"),
           dict(config=str(R4), seed=32091, steps=300, policy="rand"),
           dict(config="configs/v3_r1_on.yaml", seed=32092, steps=250, policy="rand")]
    if R1_MODEL.exists():
        old.append(dict(config=str(WILD3), seed=32093, steps=300, policy="model", model=str(R1_MODEL)))
    new = [dict(j) for j in old]
    # 관측 21 설정의 블록을 끄면(새 코드만 안다) = 직전 코드의 날씨 거울
    old.append(dict(config=str(WILD3), seed=32094, steps=300, policy="rand"))
    new.append(dict(config=str(OBS), seed=32094, steps=300, policy="rand", set={"obstacle_obs": {"enabled": False}}))
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


# --------------------------------------------------------------------- #
# 식 — 손 사례
# --------------------------------------------------------------------- #


def test_escape_room_walls_and_direction():
    """벽 거리: ux > 0 이면 (S − x)/ux, < 0 이면 x/(−ux), 0 이면 ∞. 벽에 붙어 벽 쪽이면 0. 방향 = 위협을 알면 away, 모르면 heading, 둘 다 0 이면 (1, 0)."""
    none = np.zeros((0, 3))
    e, n, h = _vals([10, 20], [1, 0], False, [0, 0], [0, 0], none)
    assert e[0] == 50.0 and n[0] == math.inf and not h[0]
    e, _, _ = _vals([10, 20], [-1, 0], False, [0, 0], [0, 0], none)
    assert e[0] == 10.0
    e, _, _ = _vals([10, 20], [0, 1], False, [0, 0], [0, 0], none)              # ux = 0 → x 벽 없음
    assert e[0] == 40.0
    e, _, _ = _vals([0, 20], [-1, 0], False, [0, 0], [0, 0], none)              # 벽 위에서 벽 쪽
    assert e[0] == 0.0 and not np.signbit(e[0])
    e, _, _ = _vals([60, 60], [1, 1], False, [0, 0], [0, 0], none)              # 모서리
    assert e[0] == 0.0
    s = math.sqrt(0.5)
    e, _, _ = _vals([10, 20], [s, s], False, [0, 0], [0, 0], none)              # 대각선: 위쪽 벽이 먼저(40 ÷ uy)
    u = s / math.sqrt(s * s + s * s)
    assert e[0] == (60 - 20) / u and e[0] == _ref_one(10.0, 20.0, s, s, False, 0.0, 0.0, 0.0, 0.0, [], 0.15, 60.0, True)[0]
    # 위협을 알면 heading 이 아니라 away 쪽
    e, _, _ = _vals([10, 20], [1, 0], True, [-1, 0], [12, 20], none)
    assert e[0] == 10.0
    # 위협을 알아도 away 가 0 이면(위협이 같은 자리) heading
    e, _, _ = _vals([10, 20], [1, 0], True, [0, 0], [10, 20], none)
    assert e[0] == 50.0
    # heading 도 0 이면 (1, 0)
    e, _, _ = _vals([10, 20], [0, 0], False, [0, 0], [0, 0], none)
    assert e[0] == 50.0
    # 위협을 모르면 away 는 읽지 않는다
    e, _, _ = _vals([10, 20], [0, 1], False, [-1, 0], [12, 20], none)
    assert e[0] == 40.0


def test_escape_room_discs():
    """원판(R = r + 몸) 앞: t = −β − √Δ. 접함(Δ = 0)은 막음, 뒤(β ≥ 0)·옆으로 비낌(Δ < 0)·안에서 시작(cc < 0)은 막지 않음, 겹치면 가장 가까운 것."""
    body = 0.5
    e, n, _ = _vals([10, 10], [1, 0], False, [0, 0], [0, 0], [[20, 10, 1.0]], body)
    assert e[0] == 8.5 and n[0] == 8.5
    e, _, _ = _vals([10, 10], [1, 0], False, [0, 0], [0, 0], [[20, 11.5, 1.0]], body)    # 접함
    assert e[0] == 10.0
    e, _, _ = _vals([10, 10], [1, 0], False, [0, 0], [0, 0], [[20, 11.6, 1.0]], body)    # 비낌
    assert e[0] == 50.0
    e, _, _ = _vals([10, 10], [1, 0], False, [0, 0], [0, 0], [[0, 10, 1.0]], body)       # 뒤
    assert e[0] == 50.0
    e, n, _ = _vals([20.5, 10], [1, 0], False, [0, 0], [0, 0], [[20, 10, 1.0]], body)    # 원판 안에서 시작 — 건너뜀
    assert e[0] == 39.5 and n[0] == -1.0
    e, n, _ = _vals([10, 10], [1, 0], False, [0, 0], [0, 0], [[30, 10, 1.0], [20, 10, 1.0], [25, 10, 3.0]], body)
    assert e[0] == 8.5 and n[0] == 8.5
    # 둘레에 붙어 미끄러지는 사슴(R + OB_EPS): 원판 쪽이면 거의 0, 멀어지는 쪽이면 벽
    p = [20 - (1.0 + body) - OB_EPS, 10]
    e, _, _ = _vals(p, [1, 0], False, [0, 0], [0, 0], [[20, 10, 1.0]], body)
    assert 0.0 <= e[0] < 1e-5
    e, _, _ = _vals(p, [-1, 0], False, [0, 0], [0, 0], [[20, 10, 1.0]], body)
    assert e[0] == p[0]


def test_threat_hidden_cases():
    """가장 가까운 위협 → 나 선분이 줄기(반지름 r, 몸 없음)를 지나면(엄격한 <) 1. 끝점 뒤 원판·위협 뒤 원판·꼭 r 만큼 떨어진 원판은 0. 위협을 모르거나
    block_sight 거짓이면 0. 길이 0(같은 자리)은 위협 자리가 원판 안인지."""
    me, wolf = [10, 10], [0, 10]
    away = [1, 0]

    def hid(discs, seen=True, block=True, threat=wolf, pos=me):
        return bool(_vals(pos, [1, 0], seen, away, threat, discs, 0.15, 60.0, block)[2][0])

    assert hid([[5, 10, 0.5]])
    assert not hid([[5, 10.5, 0.5]])          # 꼭 r 만큼 — 엄격한 <
    assert hid([[5, 10.49, 0.5]])
    assert not hid([[12, 10, 0.5]])           # 사슴 뒤
    assert not hid([[-2, 10, 0.5]])           # 늑대 뒤
    assert not hid([[11.9, 10.2, 0.5]])       # 사슴 쪽 끝으로 잘린 t = 1 — 사슴에서 1.9 남짓
    assert hid([[10.3, 10, 0.5]])             # 사슴 자리 곁(사슴에서 0.3 < r) — 끝점도 선분이다
    assert not hid([[5, 10, 0.5]], seen=False)
    assert not hid([[5, 10, 0.5]], block=False)
    assert hid([[10.1, 10, 0.5]], threat=me)  # 길이 0: 위협 자리가 원판 안
    assert not hid([[11, 10, 0.5]], threat=me)
    assert not hid([])


def test_obs_normalisation_edges():
    """관측 = clip(E ÷ escape_norm, 0, 1), clip(max(N, 0) ÷ near_norm, 0, 1)(원판 없음 1, 원판 안 0), 가림 0/1. float32."""
    w = World(_with(load_v2_config(WILD3).replace(N=4), obstacles=dict(fixed=[[30.0, 30.0, 1.0]])), seeds=[32090])
    w2 = World(_with(w.cfg, obstacle_obs=ON), seeds=[32090])
    b = w2._ob["body_r"]
    w2.pos = np.array([[0.0, 5.0], [30.0 - 1.0 - b - 2.5, 30.0], [30.3, 30.0], [55.0, 55.0]])
    w2.head = np.array([[-1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
    w2.pred_pos[:] = 59.0
    w2._g = w2._geometry()
    o = w2._obs_from(w2._g)[:, 18:]
    assert o.dtype == np.float32
    g = w2._g
    assert o[0, 0] == 0.0                                       # 벽 위에서 벽 쪽
    assert o[1, 1] == np.float32(2.5 / 5.0)                     # 원판 가장자리까지 2.5 단위(몸 가장자리 기준)
    assert o[2, 1] == 0.0                                       # 원판 안
    assert o[3, 1] == np.float32(min(1.0, g["ob_near"][3] / 5.0))
    w3 = World(_with(load_v2_config().replace(N=4), obstacle_obs=ON), seeds=[32090])     # 원판 없는 세계(v1)
    o3 = w3.observe()[:, -3:]
    assert (o3[:, 1] == 1.0).all() and (o3[:, 2] == 0.0).all() and (o3[:, 0] > 0.0).all()


# --------------------------------------------------------------------- #
# 세계 관측 = C++ 꼴 스칼라 참조 (비트 단위)
# --------------------------------------------------------------------- #


def _scene(w, rng, n_wall=6, n_rim=6, n_in=3):
    """사슴·늑대 자리를 정한다: 무작위 + 벽 위 + 원판 둘레(R + OB_EPS) + 원판 안. 늑대는 깨어 있고 사슴 가까이(가림이 생기게)."""
    N, S = w.N, w.size
    pos = rng.uniform(0.0, S, (N, 2))
    ang = rng.uniform(0.0, 2 * np.pi, N)
    head = np.stack([np.cos(ang), np.sin(ang)], 1)
    D = w.obstacles
    b = w._ob["body_r"]
    for i in range(n_wall):
        pos[i, i % 2] = 0.0 if i % 4 < 2 else S
    for i in range(n_wall, n_wall + n_rim):
        k = rng.integers(len(D))
        a = rng.uniform(0, 2 * np.pi)
        pos[i] = D[k, :2] + (D[k, 2] + b + OB_EPS) * np.array([np.cos(a), np.sin(a)])
        head[i] = -np.array([np.cos(a), np.sin(a)])
    for i in range(n_wall + n_rim, n_wall + n_rim + n_in):
        k = rng.integers(len(D))
        pos[i] = D[k, :2] + 0.3 * D[k, 2]
    w.pos = np.clip(pos, 0.0, S)
    w.head = head
    w.pred_pos = np.clip(w.pos[rng.integers(0, N, w.M)] + rng.normal(0.0, 4.0, (w.M, 2)), 0.0, S)
    # 줄기를 사이에 둔 사슴·늑대 몇 쌍(뛰는 늑대 — 발소리로만 안다 → 가림 1)
    for m in range(min(w.M, 3)):
        k = rng.integers(len(D))
        a = rng.uniform(0, 2 * np.pi)
        u = np.array([np.cos(a), np.sin(a)])
        w.pos[N - 1 - m] = np.clip(D[k, :2] + (D[k, 2] + b + 3.0) * u, 0.0, S)
        w.pred_pos[m] = np.clip(D[k, :2] - (D[k, 2] + 3.0) * u, 0.0, S)
    w.pred_vel = np.tile([w.cfg.herb_speed, 0.0], (w.M, 1))
    if hasattr(w, "pred_running"):
        w.pred_running[:] = True
    if hasattr(w, "pred_asleep"):
        w.pred_asleep[:] = False


@pytest.mark.parametrize("dense", [False, True])
def test_world_obs_equal_scalar_reference(dense):
    """세계 _geometry → _obs_from 의 세 칸이 C++ 꼴 스칼라 참조와 비트 단위로 같다(원시 거리 float64 도). 위협 지각(seen·away·가장 가까운 위협)은 세계 값."""
    c = _with(load_v2_config(OBS).replace(N=96), wild_weather=dict(region="Barren"))
    if dense:
        c = _with(c, obstacles=dict(fixed=None, tree_per_ha=600.0, rock_per_ha=30.0))
    w = World(c, seeds=[32091 if dense else 32090])
    w.keep_pair_vis = True                  # 기하에 사슴 × 위협 보임 행렬(wf_pvis)을 남긴다 — 가장 가까운 보이는 위협을 세계와 같은 식으로 찾는다
    assert len(w.obstacles) > (500 if dense else 20)
    rng = np.random.default_rng(32092)
    en, nn = w._oo["escape_norm"], w._oo["near_norm"]
    hidden_n = 0
    for _ in range(8):
        _scene(w, rng)
        g = w._geometry()
        o = w._obs_from(g)
        seen = np.isfinite(g["d_pred_min"])
        assert (seen == (g["pred_count"] > 0)).all()
        P = w.pos
        ex = w.pred_pos[:, 0][None, :] - P[:, 0:1]
        ey = w.pred_pos[:, 1][None, :] - P[:, 1:2]
        pd = np.sqrt(ex * ex + ey * ey)
        j = np.where(g["wf_pvis"], pd, np.inf).argmin(1)
        for i in range(w.N):
            tx_, ty_ = w.pred_pos[j[i]]
            e, near, hid = _ref_one(float(P[i, 0]), float(P[i, 1]), float(w.head[i, 0]), float(w.head[i, 1]), bool(seen[i]),
                                    float(g["away_from_pred"][i, 0]), float(g["away_from_pred"][i, 1]), float(tx_), float(ty_),
                                    [tuple(map(float, d)) for d in w.obstacles], float(w._ob["body_r"]), float(w.size), True)
            assert g["ob_escape"][i] == e and g["ob_near"][i] == near and bool(g["ob_hidden"][i]) == hid, i
            r = _ref_obs(e, near, hid, en, nn)
            assert tuple(o[i, 18:21]) == r, (i, o[i, 18:21], r)
            hidden_n += hid
    assert hidden_n > 0


def test_respawn_rows_rebuilt():
    """부활 세계(R4 학습)에서 다시 난 행의 세 칸 = 그 자리에서 새로 만든 관측(리스폰 행만 다시 만드는 경로 `_observe_subset`)."""
    w = World(_with(load_v2_config(R4).replace(N=48), obstacle_obs=ON), seeds=[32093])
    rng = np.random.default_rng(32093)
    reborn = 0
    for _ in range(600):
        obs, _, done, _ = w.step(_rand_beh(rng, w.N))
        if done.any():
            reborn += int(done.sum())
            fresh = w._obs_from(w._geometry())
            np.testing.assert_array_equal(obs[:, 18:], fresh[:, 18:])
    assert reborn > 0


# --------------------------------------------------------------------- #
# 마스크·계약
# --------------------------------------------------------------------- #


def test_mask_and_contract_hash():
    """마스크 판은 2 그대로(칸 이름으로 찾는다 — 21 칸 관측의 가능 칸 = 앞 18 칸의 가능 칸). 입출력 계약 해시는 관측 21 판(문서 2-4 의 값), 18·19 판은 그대로."""
    import export_weights_v3 as ew
    from env_v2.rep_policy import feasible_mask, mask_version_of

    n18, n21 = obs_names(load_v2_config(WILD3)), obs_names(load_v2_config(OBS))
    assert mask_version_of(n21) == 2
    w = World(load_v2_config(OBS).replace(N=64), seeds=[32094])
    rng = np.random.default_rng(32094)
    for _ in range(100):
        w.step(_rand_beh(rng, w.N))
        o = w.observe()
        np.testing.assert_array_equal(feasible_mask(o, n21), feasible_mask(o[:, :18], n18))
    assert ew.contract_hash(n21, 2) == HASH21
    assert ew.contract_hash(n18, 2) == 0x7eea0107339be4ce
    doc = (ROOT.parent / "AdaptiveEcosystem" / "Docs" / "RL_Policy" / "POLICY_CONTRACT_V3.md").read_text(encoding="utf-8")
    assert f"0x{HASH21:016x}" in doc


def test_no_rep_world_slots():
    """다른 기능이 없는 세계(v1 세계 + 이 기능)도 칸을 만든다: 원판 없음 → obstacle_near 1·threat_hidden 0, escape_room 은 벽 거리(위협을 알면 위협 반대)."""
    w = World(_with(load_v2_config().replace(N=16), obstacle_obs=ON), seeds=[32090])
    for _ in range(50):
        w.step(np.full((w.N, w.act_dim), 0.5))
        o = w.observe()
        assert (o[:, -2] == 1.0).all() and (o[:, -1] == 0.0).all()
        assert ((o[:, -3] >= 0.0) & (o[:, -3] <= 1.0)).all()
    assert rep.GRAZE == 0
