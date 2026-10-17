"""늑대 몸 여유 — realism_shelter.wolf_margin (10-17, 정의는 env_v2/world.py 모듈 docstring (c″), 명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md 12절).

막는 위협(늑대)은 은신처 원 둘레가 아니라 반지름 r + wolf_margin 둘레를 따라 미끄러진다. 사슴 쪽(원 안 안전·표적 제외)은 원 반지름 r 그대로다.
비트 동일: 여유 0(키 없음·0)은 직전 커밋(495be23)의 코드와 궤적·통계·v1 난수 상태·기능 스트림이 같다.
규칙 단위 시험: 밀어내기·접선·reset 옮기기가 r + 여유를 쓴다, 여유 m 세계 = 여유 0 세계에 반지름 r + m 을 준 것, 늑대 중심은 어느 스텝에도 r + 여유
안에 없다, 원 안 사슴은 그대로 안전하고 원 밖(여유 띠 안) 사슴은 그대로 잡힌다. 시드는 탐색 32094~32099 만 쓴다.
현실 근거: 늑대는 몸길이 약 1~1.5 m 인 동물이라(어림) 빽빽한 덤불·바위 테두리에 몸을 밀어 넣지 못한다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import json
import subprocess
import sys

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import features as F
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import WALL_EPS, World

CFG = ROOT / "configs"
WILD = CFG / "v3_wild1_mirror.yaml"
R3_ON = CFG / "v3_r3_on.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "495be23"              # 늑대 몸 여유 직전 커밋 — 비트 동일 기준
MARGIN = 0.5                         # 거울 설정 값(1 m)

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _tum():
    spec = importlib.util.spec_from_file_location("_tum_for_margin", ROOT / "tests" / "test_unreal_mirror.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _wild(n=16, margin=None):
    cfg = load_v2_config(WILD).replace(N=n)
    return cfg if margin is None else _with(cfg, realism_shelter=dict(wolf_margin=margin))


def _graze(w):
    return np.full((w.N, 1), float(rep.GRAZE))


def _edge_gap(w):
    """늑대마다 가장 가까운 은신처 둘레(원 반지름 r)까지 중심 거리 − r (원 안이면 음수)."""
    d = np.sqrt(((w.pred_pos[:, None, :] - w.cov_c[None, :, :]) ** 2).sum(-1))
    return (d - w.cov_r[None, :]).min(1)


# --------------------------------------------------------------------- #
# 설정·검사
# --------------------------------------------------------------------- #


def test_default_and_validation():
    assert F.with_optional("realism_shelter", {})["wolf_margin"] == 0.0
    assert World(load_v2_config(R3_ON).replace(N=8), seeds=[32094])._zw_m == 0.0      # R3 설정에는 키가 없다 → 0
    w = World(_wild(8), seeds=[32094])
    assert w._zw and w._zw_m == MARGIN and w._zs["wolf_margin"] == MARGIN
    np.testing.assert_array_equal(w._rz_wall_r(), w.cov_r + MARGIN)
    np.testing.assert_array_equal(World(_wild(8, 0.0), seeds=[32094])._rz_wall_r(), w.cov_r)
    for bad in (-0.1, True, "0.5", float("inf"), float("nan"), None):
        with pytest.raises(ValueError, match="wolf_margin"):
            World(_with(load_v2_config(WILD).replace(N=8), realism_shelter=dict(wolf_margin=bad)), seeds=[32094])
    # 진입 금지를 끈 세계에서 여유만 주면 뜻이 없다
    with pytest.raises(ValueError, match="block_predators"):
        World(_with(load_v2_config(WILD).replace(N=8), realism_shelter=dict(block_predators=False)), seeds=[32094])
    w0 = World(_with(load_v2_config(WILD).replace(N=8), realism_shelter=dict(block_predators=False, wolf_margin=0.0)), seeds=[32094])
    assert not w0._zw and w0._zw_m == 0.0


# --------------------------------------------------------------------- #
# 비트 동일
# --------------------------------------------------------------------- #


def test_margin_off_bit_identical_to_head(tmp_path):
    """직전 코드(495be23)와: R3 설정(진입 금지 켬, 키 없음)은 그대로, 거울 설정에서 여유를 0 으로 둔 세계는 직전 코드의 거울 설정(키 없음)과
    궤적·통계·난수·관측 이름·기능 스트림이 같다(R1b 롤아웃 포함)."""
    tum = _tum()
    old_root = tum._archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(tum.TRACE_SRC % dict(keys=tum.KEYS, stats=tum.STATS), encoding="utf-8")
    jobs = [dict(config="configs/v3_r3_on.yaml", seed=32095, steps=250, policy="rand"),
            dict(config="configs/v3_wild1_mirror.yaml", seed=32096, steps=400, policy="rand")]
    if R1_MODEL.exists():
        jobs.append(dict(config="configs/v3_wild1_mirror.yaml", seed=32097, steps=400, policy="model", model=str(R1_MODEL)))
    old = [dict(j) for j in jobs]
    new = [dict(j, set={"realism_shelter": {"wolf_margin": 0.0}}) if "wild1" in j["config"] else dict(j) for j in jobs]
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
    # 여유 0.5 는 같은 시드에서 궤적이 달라진다(규칙이 실제로 돈다)
    w_on, w_off = World(_wild(64), seeds=[32096]), World(_wild(64, 0.0), seeds=[32096])
    moved = False
    for _ in range(400):
        w_on.step(_graze(w_on))
        w_off.step(_graze(w_off))
        moved |= not np.array_equal(w_on.pred_pos, w_off.pred_pos)
    assert moved


# --------------------------------------------------------------------- #
# 규칙 단위
# --------------------------------------------------------------------- #


def _disc_world(margin):
    w = World(_wild(4, margin), seeds=[32098])
    w.cov_c = np.array([[15.0, 15.0], [45.0, 15.0], [15.0, 45.0], [45.0, 45.0], [20.0, 15.0]])
    w.cov_r = np.array([6.0, 6.0, 6.0, 6.0, 3.0])
    return w


def test_push_tangent_and_reset_use_margin():
    w = _disc_world(MARGIN)
    c, r, R = w.cov_c[1], 6.0, 6.0 + MARGIN
    sel = np.array([True])
    p = np.array([c + [R + WALL_EPS, 0.0]])
    # 여유 띠 안(r 과 R 사이)으로 들어가면 R 밖으로 밀린다 — 둘레 방향 성분은 남는다
    q, pushed = w._rz_wall_push(p + [-0.3, 0.4], p, sel)
    rad = np.linalg.norm(q[0] - c)
    assert pushed[0] and R < rad <= R + 2 * WALL_EPS and rad > r + MARGIN
    assert (q[0] - p[0])[1] >= 0.4 * 0.99
    # 접선 미끄러짐: R 둘레 위에서 중심 쪽 성분을 뺀다 → R 원 안으로 들지 않는다
    t = w._rz_wall_tangent(p, np.array([[-0.4, 0.3]]))
    assert np.linalg.norm(t[0] - c) >= R and not w._rz_inside_disc(t)[0]
    np.testing.assert_allclose(t[0], p[0] + [0.0, 0.3], rtol=0, atol=1e-12)
    # 원 판정: r 과 R 사이는 늑대에게 원 안, 여유 0 세계에서는 밖
    ring = np.array([c + [r + 0.2, 0.0]])
    assert w._rz_inside_disc(ring)[0] and not _disc_world(0.0)._rz_inside_disc(ring)[0]
    # reset 옮기기: 여유 띠 안에 놓인 늑대는 R 둘레 밖으로 옮긴다(여유 0 이면 그대로)
    for margin, want_moved in ((MARGIN, True), (0.0, False)):
        w = _disc_world(margin)
        w.pred_pos[:] = [c + [r + 0.2, 0.0], [30.0, 30.0]][: w.M]
        w._rz_wall_reset()
        assert (w._zw_reset_moved == 1) is want_moved
        assert np.linalg.norm(w.pred_pos[0] - c) >= (R if margin else r)
        assert not w._rz_inside_disc(w.pred_pos).any()


def test_margin_equals_bigger_discs():
    """여유 m 세계의 밀어내기·접선·원 판정 = 여유 0 세계에 반지름 r + m 원을 준 것 (언리얼은 원 목록 반지름에 더한다 — 골든과 같은 꼴)."""
    a, b = _disc_world(MARGIN), _disc_world(0.0)
    b.cov_r = a.cov_r + MARGIN
    rng = np.random.default_rng(32098)
    n = 400
    k = rng.integers(0, len(a.cov_r), n)
    ang = rng.uniform(0.0, 2.0 * np.pi, n)
    u = np.stack([np.cos(ang), np.sin(ang)], 1)
    p = a.cov_c[k] + (a.cov_r[k] + MARGIN + rng.uniform(0.01, 1.5, n))[:, None] * u
    v = rng.uniform(-1.0, 1.0, (n, 2))
    sel = np.ones(n, dtype=bool)
    qa, pa = a._rz_wall_push(p + v, p, sel)
    qb, pb = b._rz_wall_push(p + v, p, sel)
    np.testing.assert_array_equal(qa, qb)
    np.testing.assert_array_equal(pa, pb)
    np.testing.assert_array_equal(a._rz_wall_tangent(p, v), b._rz_wall_tangent(p, v))
    np.testing.assert_array_equal(a._rz_inside_disc(p + v), b._rz_inside_disc(p + v))
    assert pa.any() and not pa.all()


def test_wolves_never_inside_margin_and_deer_rules_unchanged():
    # 긴 판(먹기만, 사슴 64): 늑대 중심은 어느 스텝에도 r + 여유 안에 없다. 원 안에서 잡힌 사슴 0
    w = World(_wild(64), seeds=[32099])
    gap_min = np.inf
    for _ in range(900):
        w.step(_graze(w))
        gap_min = min(gap_min, float(_edge_gap(w).min()))
        assert (_edge_gap(w) >= MARGIN).all()
    dead = np.flatnonzero(w.death_cause == 1)
    assert len(dead) > 0 and not w._in_cover(w.pos[dead]).any()
    assert w.r3_stats()["wall_inside_n"] == 0.0 and w.r3_stats()["wall_push_n"] > 0
    assert gap_min < MARGIN + 0.05                       # 늑대가 실제로 여유 둘레에 붙어 돌았다
    # 같은 세계를 여유 0 으로: 늑대가 여유 띠 안까지 들어온다(원 안에는 아니다)
    w0 = World(_wild(64, 0.0), seeds=[32099])
    gap0 = np.inf
    for _ in range(900):
        w0.step(_graze(w0))
        gap0 = min(gap0, float(_edge_gap(w0).min()))
    assert 0.0 <= gap0 < MARGIN


def _scene(w, deer_off, wolf_off):
    """사슴 0 과 사냥 중인 늑대 0 을 은신처 0 의 +x 쪽 반지름 위에 둔다(늑대 1 은 멀리). 사슴은 그 자리에 고정해 둔다."""
    c = w.cov_c[0]
    w.pred_asleep[:] = False
    w.pred_cd[:] = 0
    if w._ws is not None:
        w.pred_sat[:] = 0
    w.pos[0] = c + [deer_off, 0.0]
    w.pred_pos[0] = c + [wolf_off, 0.0]
    w.pred_head[0] = [-1.0, 0.0]
    w.pred_pos[1] = [-400.0, -400.0]
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)
    return c


def test_deer_inside_safe_and_deer_in_margin_ring_still_caught():
    # 원 안(r − 0.3) 사슴: 여유가 있어도 그대로 안전, 늑대는 r + 여유 밖
    w = World(_wild(16), seeds=[32094])
    r = float(w.cov_r[0])
    c = _scene(w, r - 0.3, r + MARGIN + 0.4)
    for _ in range(20):
        w.pos[0] = c + [r - 0.3, 0.0]
        w.step(_graze(w))
        assert w.alive[0]
        assert (_edge_gap(w) >= MARGIN).all()
    # 원 밖이지만 여유 띠 안(r + 0.2) 사슴: 원 밖이라 표적·포획 대상 그대로 — 늑대는 R 둘레에서 포획 거리(1) 안이라 잡는다
    w = World(_wild(16), seeds=[32094])
    c = _scene(w, r + 0.2, r + MARGIN + 0.6)
    caught = False
    for _ in range(10):
        if not w.alive[0]:
            caught = True
            break
        w.pos[0] = c + [r + 0.2, 0.0]
        w.step(_graze(w))
        assert (_edge_gap(w) >= MARGIN).all()
    caught |= not w.alive[0]
    assert caught and w.death_cause[0] == 1
