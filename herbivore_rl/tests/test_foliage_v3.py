"""숲 시야 obstacles.foliage (10-21 사용자 '숲 안 시야 줄이기 → 다시 잼' — env_v2/world.py 모듈 docstring '야생 2단계' 3 의 7), 측정 도구
results/v3/route/route_rules.py·oracle.py --world-set).

- 기하(`foliage_chord`): 비낌·스침·꿰뚫음·끝점 안·둘 다 안·여러 원·겹친 원(합집합 — 한 번만)·길이 0, 넓은 거르기 = 거르지 않은 셈, 촘촘한 표본
  적분과 같음, a ↔ b 비트 동일. 덩어리 숲(겹친 잎 수십 겹)에서도 block 보다 짧은 눈길은 가리지 않는다(길이 ≤ 눈길 길이).
- 가림(`foliage_blocked`·`sight_blocked(…, foliage)`): 잎 안 길이 ≥ block 이면 가림, 줄기 ∨ 잎.
- 나무 표: trees 'all' 은 나무 원판만(무작위 배치의 바위는 잎이 없다, fixed 는 모두), 0/1 목록이면 그 표.
- 세계에서 양쪽 같게: 잎 뒤 늑대를 사슴이 못 보고(서 있으면), 늑대도 그 사슴을 표적으로 고르지 못한다. 발소리는 잎이 막지 않고, 그때 관측 threat_hidden
  = 1(늑대가 나를 못 본다). 끄면 보고 표적으로 고른다.
- 끔(키 없음·enabled false) = HEAD(01e8d90, git archive 로 돌린 같은 셈 — 10-22 동족 차례 합 두 줄을 넣은 사본) 궤적·기록 해시 — 거울 G·N(숲·고지, COVER 길 고정 포함)·학습 세계(부활 있음).
- 옛 설정의 config digest 그대로 (선택 키는 features.OPTIONAL_KEYS 끔 값).
- 도망길 COVER 그늘: 잎이 있으면 H 가 늘고(같은 눈길 판정 — `sight_blocked` 와 같은 값), 끄면 그대로.
- 도망 기록: 잎 놓침은 obstacle(스스로 벗어남) 안의 lost_foliage, 끈 세계에는 칸이 없다. 평가기(ceval)는 숲 시야 세계를 받는다(10-22 C++ 에 옮김 —
  FoliageGoldenVectorsV3.h·Policy.V3.Foliage.*, 도망길 COVER 그늘의 잎은 파이썬 전용이라 route_fixed 거부는 그대로).
- 측정 도구 --world-set: 점 경로 덮기, 덮기 없음 RUN 팔, 덮기 효과 표, '원판 놓침 가운데 잎 때문' 칸(÷ 원판 놓침, 끈 팔 —), 끊긴 측정을 이어 돌릴
  때 raw 파일의 덮기로 섞기를 막음(meta.json 이 없어도), report 의 부분끼리·meta 덮기 검사.
- 측정 도구 셈 길 지문(10-22 code_tag): 지문이 다른(옛 판 포함) raw 는 이어 돌리지 않고, 부분 중간에 바뀌면 지문 없이 적고 멈추며, report 는 부분끼리
  다르면 멈추고 세계 지문이 다른 오라클을 판단표에 쓰지 않는다.
시드는 탐색 32083~32099·학습 32000~32049 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import hashlib
import importlib.util
import json
import math
import sys

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import features as F
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import (FLIGHT_CAUSES, FLIGHT_OWN, World, _route_seg_foliage, flight_route_geometry, foliage_blocked, foliage_chord,
                          obstacle_layout, sight_blocked)

CFG = ROOT / "configs"
OBS = CFG / "v3_wild3_obs_mirror.yaml"          # 거울 (부활 없음, 장애물·늑대 4, 관측 21 — threat_hidden)
TRAIN = CFG / "v3_r5_train.yaml"                # 학습 세계 (부활 있음)
FOL = dict(enabled=True, r=3.0, block=2.0, trees="all")

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")

# HEAD(01e8d90) 를 git archive 로 풀어 같은 `_traj_hash` 로 잰 값 (숲 시야 코드를 넣기 전).
# 10-22 다시 잼: world.py 가 동족 무리 중심·분리를 C++ 과 같은 j 차례 합으로 더하게 되어(`_seq_sum`) 끝 비트가 달라졌다 — 사본의 그 두 줄만 같은
# 차례 합으로 바꾼 HEAD(tests/kin_seq.py patch_tree)로 잰 값이고 지금 코드(끔)와 같다. 옛 값(행렬곱 HEAD): G_Forest 99daf5ae…·N_Forest 7c36653a…·
# N_Forest_cover d1d446f4…·G_Highland 7c07576d…·N_Highland 324eeef3…·N_Highland_cover de490a34…·train_respawn b67d202b…
HEAD_HASH = {
    "G_Forest": "f640c25d1b0981e2c249b9a6f3f4ef329ee284ba894ed40c66474d56e4913023",
    "N_Forest": "cf260c57bcf1e1e4fe629924e8aeb8a4a39befa3f796cec9cb750787f2396399",
    "N_Forest_cover": "c84ade66094356acffed5d6375d3555124ee65a762398e10b097372d5ca8f823",
    "G_Highland": "edaa93bd38f0cbec50d07c3e1a1f9b8e200014863531be33f41013db23b91935",
    "N_Highland": "a9de3b28df21ecea5854124b2252e752d3e40a9fb2fceea1efb09f7cf19fdbf9",
    "N_Highland_cover": "0603d1a34611498ea2fe4bf230e6df6a452d7683d3c82b0ce04bf8674dde80cb",
    "train_respawn": "65984ff6834440bbf8d2bd60ca5d38e39ff246034aa3b2d92d14302024ee0ca1",
}
# HEAD 의 config digest (results/v3/mirror/run_mirror.config_digest — obstacles 를 켠 설정 전부)
HEAD_DIGEST = {
    "v3_r4_train.yaml": "a0d95473e1c7", "v3_r5_train.yaml": "a119c35118d8", "v3_wild2_obstacle_mirror.yaml": "53bf911063a0",
    "v3_wild2_trees_mirror.yaml": "558f558fe050", "v3_wild3_mirror.yaml": "18457cffb2c8", "v3_wild3_obs_mirror.yaml": "d3fb12aa4ea8",
}


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


@pytest.fixture(scope="module")
def discs():
    return _module("_r4_for_foliage", ROOT / "results" / "v3" / "r4" / "r4_eval.py").region_discs()


def _H(*arrs):
    h = hashlib.sha256()
    for a in arrs:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h


def _traj_hash(cfg, seed, steps, acts_seed=7):
    """무작위 행동(먹기·도망·숨기) 궤적·관측·늑대 표적·도망 기록(길 칸 포함)·야생·사냥·장애물 통계·v1 난수의 해시 (HEAD 값을 잰 셈과 같다)."""
    w = World(cfg, seeds=[seed])
    w.track_flight = True
    rng = np.random.default_rng(acts_seed)
    h = hashlib.sha256()
    for _ in range(steps):
        o, r, d, to = w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        h.update(_H(o, r, d, to, w.pos, w.pred_pos, w.energy, w.wf_mode, w.wf_dir, w.pred_target).digest())
    f = w.flight_stats()
    f.pop("hide", None)                 # 10-23 숨은 뒤 지켜보기 칸 (HEAD 뒤에 더한 통계 전용 칸 — 궤적과 옛 칸은 그대로)
    f.pop("episode", None)              # 10-24 쫓김 사건 칸 (HEAD 뒤에 더한 통계 전용 칸 — 궤적과 옛 칸은 그대로)
    st = dict(flight=f, wild=w.wild_stats(), hunt=w.hunt_stats(), ob=w.obstacle_stats(), rng=str(w.rng.bit_generator.state))
    h.update(json.dumps(st, sort_keys=True, default=str).encode())
    return h.hexdigest()


# --------------------------------------------------------------------- #
# 기하
# --------------------------------------------------------------------- #

C0 = np.array([[0.0, 0.0]])


def _ch(a, b, centers=C0, r=2.0):
    return float(foliage_chord(np.array([a], dtype=np.float64), np.array([b], dtype=np.float64), np.asarray(centers, dtype=np.float64), r)[0])


def test_chord_cases():
    """비낌 0, 스침 0(Δ = 0), 꿰뚫음 2r, 중심에서 h 떨어진 줄 2√(r² − h²), 끝점 안이면 안쪽 몫만, 둘 다 안이면 선분 전체, 원에 닿기 전에 끝나면 0,
    길이 0 선분 0, 떨어진 원은 더하고 겹친 원은 합집합(겹친 몫은 한 번), 같은 원 둘도 한 번."""
    assert _ch([-5.0, 3.0], [5.0, 3.0]) == 0.0                                      # 비낌
    assert _ch([-5.0, 2.0], [5.0, 2.0]) == 0.0                                      # 스침 (y = r)
    assert _ch([-5.0, 0.0], [5.0, 0.0]) == pytest.approx(4.0, abs=1e-12)            # 꿰뚫음
    assert _ch([-5.0, 1.0], [5.0, 1.0]) == pytest.approx(2.0 * math.sqrt(3.0), abs=1e-12)
    assert _ch([0.0, 0.0], [5.0, 0.0]) == pytest.approx(2.0, abs=1e-12)             # 끝점이 중심
    assert _ch([1.0, 0.0], [5.0, 0.0]) == pytest.approx(1.0, abs=1e-12)             # 끝점이 원 안
    assert _ch([-0.5, 0.0], [0.5, 0.3]) == pytest.approx(math.hypot(1.0, 0.3), abs=1e-12)   # 둘 다 안
    assert _ch([-9.0, 0.0], [-3.0, 0.0]) == 0.0                                     # 원에 닿기 전에 끝남
    assert _ch([1.0, 1.0], [1.0, 1.0]) == 0.0                                       # 길이 0 (원 안이어도)
    two = np.array([[0.0, 0.0], [10.0, 0.0]])
    assert _ch([-5.0, 0.0], [15.0, 0.0], two) == pytest.approx(8.0, abs=1e-12)     # 원 둘
    lap = np.array([[0.0, 0.0], [1.0, 0.0]])
    assert _ch([-5.0, 0.0], [15.0, 0.0], lap) == pytest.approx(5.0, abs=1e-12)     # 겹친 원: [−2, 3] 한 번
    assert _ch([-5.0, 0.0], [15.0, 0.0], np.array([[1.0, 0.0], [0.0, 0.0]])) == _ch([-5.0, 0.0], [15.0, 0.0], lap)   # 원 순서와 무관
    assert _ch([-5.0, 0.0], [15.0, 0.0], np.array([[0.0, 0.0], [0.0, 0.0]])) == pytest.approx(4.0, abs=1e-12)        # 같은 원 둘
    assert _ch([-5.0, 0.0], [15.0, 0.0], np.array([[0.0, 0.0], [10.0, 0.0], [0.5, 0.0], [10.5, 0.0]])) == pytest.approx(9.0, abs=1e-12)
    assert _ch([1.0, 0.0], [2.0, 0.0], lap) == pytest.approx(1.0, abs=1e-12)        # 둘 다 안 (겹친 곳): 선분 길이 그대로
    assert foliage_chord(np.zeros((0, 2)), np.zeros((0, 2)), C0, 2.0).shape == (0,)
    assert (foliage_chord(np.array([[-5.0, 0.0]]), np.array([[5.0, 0.0]]), np.zeros((0, 2)), 2.0) == 0.0).all()


def _chord_dense(a, b, centers, r):
    """넓은 거르기 없이 모든 쌍 × 원을 같은 식으로 구간을 내고 선분마다 파이썬으로 합집합 길이 (대조용)."""
    sw = (a[:, 0] > b[:, 0]) | ((a[:, 0] == b[:, 0]) & (a[:, 1] > b[:, 1]))
    p0 = np.where(sw[:, None], b, a)
    p1 = np.where(sw[:, None], a, b)
    d = p1 - p0
    dd = (d * d).sum(1)[:, None]
    f = p0[:, None, :] - centers[None, :, :]
    beta = (f * d[:, None, :]).sum(2)
    gam = (f * f).sum(2) - r * r
    dsc = beta * beta - dd * gam
    ok = (dd > 0.0) & (dsc > 0.0)
    s = np.sqrt(np.where(ok, dsc, 0.0))
    den = np.where(ok, dd, 1.0)
    t0 = np.maximum((-beta - s) / den, 0.0)
    t1 = np.minimum((-beta + s) / den, 1.0)
    out = np.zeros(len(a))
    for i in range(len(a)):
        iv = sorted((t0[i, k], t1[i, k]) for k in range(len(centers)) if ok[i, k] and t1[i, k] > t0[i, k])
        cov, e = 0.0, 0.0
        for lo, hi in iv:
            cov += max(hi - max(lo, e), 0.0)
            e = max(e, hi)
        out[i] = cov * math.sqrt(dd[i, 0])
    return out


def test_chord_random_matches_dense_sampling_and_is_symmetric():
    """무작위 선분·원 50 개(겹침 있음): 넓은 거르기 = 거르지 않은 합집합 셈, 촘촘한 표본(선분 위 2 만 점 — 어느 원 안이든 한 번) 적분과 1e-3 안,
    a → b 와 b → a 가 비트 단위로 같고, 길이 ≤ 선분 길이."""
    g = np.random.default_rng(32090)
    a = g.uniform(0.0, 60.0, (400, 2))
    b = a + g.normal(0.0, 8.0, (400, 2))
    centers = g.uniform(0.0, 60.0, (50, 2))
    r = 3.0
    got = foliage_chord(a, b, centers, r)
    assert np.allclose(got, _chord_dense(a, b, centers, r), rtol=1e-12, atol=1e-12)
    assert np.array_equal(got, foliage_chord(b, a, centers, r))
    assert (got > 0).sum() > 50 and (got <= np.linalg.norm(b - a, axis=1) * (1.0 + 1e-12)).all()
    u = (np.arange(20000) + 0.5) / 20000
    for i in range(0, 400, 20):
        pts = a[i][None, :] + u[:, None] * (b[i] - a[i])[None, :]
        inside = (((pts[:, None, :] - centers[None, :, :]) ** 2).sum(2) < r * r).any(1)
        assert got[i] == pytest.approx(inside.mean() * np.linalg.norm(b[i] - a[i]), abs=1e-3 * max(1.0, np.linalg.norm(b[i] - a[i])))


def test_dense_clump_short_sight_never_blocked():
    """덩어리 숲(route_rules.clump_discs 꼴 — 반지름 5 안 줄기 30 그루, 잎 수십 겹): 잎 안 길이는 눈길 길이를 넘지 않으므로 block 보다 짧은 눈길은
    가리지 않고(몸 하나 거리의 개체는 서로 본다), block 보다 조금 길게 잎 속을 지나면 가린다. r 3·block 2 와 r 1.5·block 1 둘 다."""
    g = np.random.default_rng(32092)
    ang, rad = g.uniform(0.0, 2.0 * math.pi, 30), 5.0 * np.sqrt(g.uniform(0.0, 1.0, 30))
    clump = np.c_[30.0 + rad * np.cos(ang), 30.0 + rad * np.sin(ang)]
    for r, block in ((3.0, 2.0), (1.5, 1.0)):
        th = g.uniform(0.0, 2.0 * math.pi, 500)
        a = 30.0 + g.uniform(-2.0, 2.0, (500, 2))
        for L in (0.2, 0.5, 0.99 * block):
            b = a + L * np.c_[np.cos(th), np.sin(th)]
            c = foliage_chord(a, b, clump, r)
            assert (c <= L * (1.0 + 1e-12)).all() and not foliage_blocked(a, b, clump, r, block).any(), (r, L)
        b = a + 1.01 * block * np.c_[np.cos(th), np.sin(th)]                       # 잎 속 block 보다 조금 긴 눈길: 거의 다 가림 (r 3 은 모두)
        c = foliage_chord(a, b, clump, r)
        assert np.allclose(c, _chord_dense(a, b, clump, r), rtol=1e-12, atol=1e-12)
        fb = foliage_blocked(a, b, clump, r, block)
        assert fb.all() if r == 3.0 else fb.mean() > 0.5, r


def test_blocked_threshold_and_sight_blocked():
    """가림 = 길이 합 ≥ block (같으면 가림). sight_blocked(…, foliage) = 줄기 ∨ 잎, foliage None 이면 줄기만(그대로)."""
    a, b = np.array([[-5.0, 0.0]]), np.array([[5.0, 0.0]])
    c = float(foliage_chord(a, b, C0, 2.0)[0])
    assert c == pytest.approx(4.0, abs=1e-12)
    assert foliage_blocked(a, b, C0, 2.0, c)[0] and not foliage_blocked(a, b, C0, 2.0, np.nextafter(c, np.inf))[0]
    assert foliage_blocked(a, b, C0, 2.0, 3.9)[0] and not foliage_blocked(a, b, C0, 2.0, 4.1)[0]
    g = np.random.default_rng(32091)
    A, B = g.uniform(0.0, 60.0, (30, 2)), g.uniform(0.0, 60.0, (20, 2))
    trunks = np.c_[g.uniform(0.0, 60.0, (24, 2)), g.uniform(0.3, 0.45, 24)]
    fol = (trunks[:, :2], 3.0, 2.0)
    base = sight_blocked(A, B, trunks)
    both = sight_blocked(A, B, trunks, fol)
    aa, bb = np.repeat(A, len(B), 0), np.tile(B, (len(A), 1))
    want = base | foliage_blocked(aa, bb, *fol).reshape(len(A), len(B))
    assert np.array_equal(both, want) and both.sum() > base.sum()
    assert np.array_equal(sight_blocked(A, B, trunks, None), base)
    none = np.zeros((0, 3))
    fa, fb = sight_blocked(A, B, none, fol), sight_blocked(B, A, none, fol)        # 잎 몫만: a ↔ b 비트 동일
    assert np.array_equal(fa, fb.T) and fa.any()


# --------------------------------------------------------------------- #
# 세계에서 양쪽 같게 (사슴 → 늑대 눈, 늑대 → 사슴 표적), 발소리, 관측
# --------------------------------------------------------------------- #

TRUNK = [[30.0, 31.0, 0.15]]       # 줄기는 눈길(y = 30)에서 1 떨어져 줄기는 가리지 않는다. 잎(r 3)은 눈길 2√8 ≈ 5.66 단위를 덮는다


def _scene(fol, run=False):
    ob = dict(fixed=TRUNK) if fol is None else dict(fixed=TRUNK, foliage=fol)
    w = World(_with(load_v2_config(OBS).replace(N=8), wild_weather=dict(region="Barren"), obstacles=ob), seeds=[32083])
    w.pos[:] = [5.0, 5.0]
    w.pos[0] = [27.0, 30.0]
    w.head[:] = [-1.0, 0.0]
    w.head[0] = [1.0, 0.0]
    w.pred_pos[:] = [55.0, 55.0]
    w.pred_pos[0] = [33.0, 30.0]
    w.pred_head[:] = [1.0, 0.0]
    w.pred_head[0] = [-1.0, 0.0]
    w.pred_asleep[:] = False
    w.pred_vel[:] = 0.0
    w.pred_running[:] = False
    if run:
        w.pred_vel[0] = [-0.6, 0.0]
        w.pred_running[0] = True
    return w


def test_world_sight_symmetric_and_hearing_unaffected():
    """잎 뒤 서 있는 늑대: 숲 시야를 켜면 사슴이 못 보고(pred_count 0) 늑대도 그 사슴을 표적으로 고르지 못한다(같은 눈길). 끄면 둘 다 본다.
    달려오면 발소리로 알아채고(잎은 소리를 막지 않는다), 그때 threat_hidden = 1 (늑대가 나를 못 본다) — 끈 세계는 0."""
    off, on = _scene(None)._geometry(), _scene(FOL)._geometry()
    assert off["pred_count"][0] == 1 and on["pred_count"][0] == 0
    off_r, on_r = _scene(None, run=True)._geometry(), _scene(FOL, run=True)._geometry()
    assert off_r["pred_count"][0] == 1 and on_r["pred_count"][0] == 1
    assert not off_r["ob_hidden"][0] and on_r["ob_hidden"][0]
    for fol, want in ((None, 0), (FOL, -1)):
        w = _scene(fol)
        w.step(np.full((w.N, 1), float(rep.GRAZE)))
        assert w.pred_target[0] == want
    w = _scene(FOL)
    w.step(np.full((w.N, 1), float(rep.GRAZE)))
    st = w.obstacle_stats()["foliage"]
    assert st["tgt_only"] >= 1 and st["eye_only"] >= 1 and st["n"] == 1 and (st["r"], st["block"]) == (3.0, 2.0)
    # 같은 쌍을 양쪽에서 잰다 (_ob_occlude: 사슴 → 늑대, 늑대 → 사슴)
    w = _scene(FOL)
    vis = np.ones((w.N, w.M), dtype=bool)
    v1, _, _, f1 = w._ob_occlude(vis, w.pos, w.pred_pos)
    v2, _, _, f2 = w._ob_occlude(vis.T.copy(), w.pred_pos, w.pos)
    assert np.array_equal(v1, v2.T) and np.array_equal(f1, f2.T) and f1[0, 0]
    # 끈 세계의 _ob_occlude 는 잎 칸이 None
    assert _scene(None)._ob_occlude(vis, w.pos, w.pred_pos)[3] is None


def test_trees_mask_and_validation():
    """trees: 'all' = 모든 원판, 0/1 목록 = 그 원판만(길이는 원판 수). 잘못된 값은 멈춘다. block_sight 를 꺼도 멈춘다."""
    w = _scene(dict(FOL, trees=[0]))
    assert w._geometry()["pred_count"][0] == 1 and len(w._fol_centers()) == 0       # 나무가 아니면 잎이 없다
    w = _scene(dict(FOL, trees=[True]))
    assert w._geometry()["pred_count"][0] == 0
    base = _with(load_v2_config(OBS).replace(N=8), wild_weather=dict(region="Barren"))
    for bad in (dict(FOL, r=0.0), dict(FOL, block=-1.0), dict(FOL, r="3.0"), dict(FOL, enabled=1), dict(FOL, trees="some"),
                dict(FOL, trees=[2]), dict(FOL, rr=1.0), [1, 2]):
        with pytest.raises(ValueError, match="foliage"):
            World(_with(base, obstacles=dict(fixed=TRUNK, foliage=bad)), seeds=[32083])
    with pytest.raises(ValueError, match="foliage.trees"):
        World(_with(base, obstacles=dict(fixed=TRUNK, foliage=dict(FOL, trees=[1, 0]))), seeds=[32083])
    with pytest.raises(ValueError, match="block_sight"):
        World(_with(base, obstacles=dict(fixed=TRUNK, block_sight=False, foliage=FOL)), seeds=[32083])
    # 꺼진 블록(enabled false)은 다른 칸과 상관없이 검사하지 않는다 — 끈 세계
    World(_with(base, obstacles=dict(fixed=TRUNK, block_sight=False, foliage=dict(enabled=False, r=-1.0))), seeds=[32083])
    assert dict(F.OPTIONAL_KEYS["obstacles"])["foliage"] == {"enabled": False, "r": 3.0, "block": 2.0, "trees": "all"}


def test_trees_all_skips_rocks_in_random_layout():
    """무작위 배치(fixed 없음, 바위 있음): trees 'all' 은 줄기 고리 원판만 잎 원 중심이고 바위는 빠진다. kinds 를 물어도 원판·난수는 그대로이고
    나무 표는 앞쪽(줄기)부터다. fixed 는 모두 나무다."""
    base = _with(load_v2_config(CFG / "v3_wild2_obstacle_mirror.yaml").replace(N=8), obstacles=dict(foliage=FOL))
    w = World(base, seeds=[32096])
    op = w._ob
    d0, t0 = obstacle_layout(np.random.default_rng(32096), w.size, w.cov_c, w.cov_r, op, kinds=True)
    assert np.array_equal(d0, obstacle_layout(np.random.default_rng(32096), w.size, w.cov_c, w.cov_r, op)) and t0.dtype == bool
    d, tree = w.obstacles, w.obstacle_tree
    k = int(tree.sum())
    assert 0 < k < len(d) and tree[:k].all() and not tree[k:].any()                 # 줄기 먼저, 바위 뒤
    lo, hi = op["rock_r"]
    assert ((d[~tree, 2] >= lo) & (d[~tree, 2] <= hi)).all()
    fc = w._fol_centers()
    assert len(fc) == k and np.array_equal(fc, d[tree, :2])
    w2 = _scene(FOL)
    assert w2.obstacle_tree.tolist() == [True] and len(w2._fol_centers()) == 1        # fixed = 모두 나무


# --------------------------------------------------------------------- #
# 끔 = HEAD (비트 동일), config digest
# --------------------------------------------------------------------- #


def test_off_matches_head(discs):
    """키 없음(끔)은 HEAD 궤적·기록 해시와 같다 — 거울 G·N(숲·고지, N 은 COVER 길 고정 + quiet_end 15 도), 학습 세계(부활 있음). enabled false 를 적은
    블록(다른 칸은 아무 값)도 같다. 끈 세계의 기록에는 숲 시야 칸이 없다."""
    base = load_v2_config(OBS).replace(N=32)
    for reg in ("Forest", "Highland"):
        g = _with(base, wild_weather=dict(region=reg), obstacles=dict(fixed=discs[reg]))
        assert _traj_hash(g, 32084, 900) == HEAD_HASH[f"G_{reg}"], reg
        n = _with(g, wild_satiation=dict(enabled=False))
        assert _traj_hash(n, 32085, 900) == HEAD_HASH[f"N_{reg}"], reg
        assert _traj_hash(_with(n, wild_flight=dict(route_fixed="cover", quiet_end=15)), 32086, 900) == HEAD_HASH[f"N_{reg}_cover"], reg
    assert _traj_hash(load_v2_config(TRAIN).replace(N=24), 32001, 900, 5) == HEAD_HASH["train_respawn"]
    g = _with(base, wild_weather=dict(region="Forest"), obstacles=dict(fixed=discs["Forest"], foliage=dict(enabled=False, r=1.5, block=1.0)))
    assert _traj_hash(g, 32084, 900) == HEAD_HASH["G_Forest"]
    w = World(g, seeds=[32084])
    w.track_flight = True
    w.step(np.zeros((w.N, 1)))
    assert "lost_foliage" not in w.flight_stats() and "foliage" not in w.obstacle_stats() and w._fol_args() is None


def test_config_digests_unchanged():
    """옛 설정(obstacles 를 켠 설정 전부)의 config digest 가 HEAD 와 같다 — 새 키는 OPTIONAL_KEYS 끔 값이라 설정 파일·dict 가 그대로다."""
    rm = _module("_rm_for_foliage", ROOT / "results" / "v3" / "mirror" / "run_mirror.py")
    for name, want in HEAD_DIGEST.items():
        cfg = load_v2_config(CFG / name)
        assert rm.config_digest(cfg) == want, name
        assert "foliage" not in cfg.v2["features"]["obstacles"]


# --------------------------------------------------------------------- #
# 도망길 COVER 그늘
# --------------------------------------------------------------------- #


def test_cover_shading_increases_with_foliage():
    """사슴 (30, 30) 이 남쪽 늑대 (30, 18) 를 피해 북쪽(a₀ = (0, 1))으로: 북서쪽 가는 줄기(r 0.15) 하나는 거의 가리지 않지만 그 잎(r 3)은 북서 후보의 표본점
    눈길을 가려 H 가 는다. 모든 후보에서 잎 H ≥ 줄기만 H, H* 가 커지고 COVER 가 가능해진다. 그늘 판정은 늑대 표적 고르기와 같은 눈길 판정
    (`_route_seg_foliage` = `sight_blocked(…, foliage)`)."""
    p, a0, q = np.array([[30.0, 30.0]]), np.array([[0.0, 1.0]]), np.array([[30.0, 18.0]])
    S, d = np.array([[True]]), np.array([[12.0]])
    trunk = np.array([[24.0, 37.0, 0.15]])
    fol = (trunk[:, :2], 3.0, 2.0)
    args = (p, a0, q, S, d, np.zeros((0, 2)), np.zeros(0), trunk, 60.0, 2.0, 0.0)
    g0 = flight_route_geometry(*args)
    g1 = flight_route_geometry(*args, foliage=fol)
    g_none = flight_route_geometry(*args, foliage=None)
    for k in ("cover_h", "cover_dir", "cover_j", "cover_best_h", "open_dir", "shelter_k"):
        assert np.array_equal(g0[k], g_none[k], equal_nan=True), k
    v = g0["cover_valid"][0]
    assert np.array_equal(v, g1["cover_valid"][0])
    h0, h1 = g0["cover_h"][0][v], g1["cover_h"][0][v]
    assert (h1 >= h0).all() and (h1 > h0).any()
    assert g1["cover_best_h"][0] > g0["cover_best_h"][0] and g1["cover_ok"][0] and not g0["cover_ok"][0]
    assert g1["cover_dir"][0, 0] < 0.0                                               # 북서쪽(잎 쪽)으로
    # 같은 눈길 판정: 늑대 → 표본점
    xs = np.array([[1.0, 5.0, 20.0], [24.0, 25.0, 30.0]])
    ys = np.array([[35.0, 37.0, 38.0], [40.0, 33.0, 37.0]])
    got = _route_seg_foliage(q, xs, ys, fol)
    want = sight_blocked(q, np.c_[xs.ravel(), ys.ravel()], np.zeros((0, 3)), fol).T.reshape(2, 3, 1)
    assert np.array_equal(got, want) and got.any() and not got.all()


# --------------------------------------------------------------------- #
# 도망 기록 (lost_foliage), 평가기 거부
# --------------------------------------------------------------------- #


def test_flight_record_lost_foliage(discs):
    """숲 시야 켬: 잎 놓침은 끝 까닭 obstacle(FLIGHT_OWN) 안의 lost_foliage — lost_foliage.n ≤ n['obstacle'], 쫓긴 스텝도 그 안, 시작 = 끝 까닭 합,
    길 기록에 drop_foliage ≤ drop_obstacle. 끈 세계에는 그 칸이 없다."""
    base = _with(load_v2_config(OBS).replace(N=32), wild_weather=dict(region="Forest"), wild_satiation=dict(enabled=False),
                 wild_flight=dict(route_fixed="cover"))
    tot_lf = 0
    for seed in (32087, 32088):
        w = World(_with(base, obstacles=dict(fixed=discs["Forest"], foliage=FOL)), seeds=[seed])
        w.track_flight = True
        rng = np.random.default_rng(3)
        for _ in range(900):
            w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        f = w.flight_stats()
        lf = f["lost_foliage"]
        assert "obstacle" in FLIGHT_OWN and f["started"] == sum(f["n"][c] for c in FLIGHT_CAUSES)
        assert 0 <= lf["n"] <= f["n"]["obstacle"] and lf["steps"] <= f["steps"]["obstacle"] and lf["contact"] <= f["contact"]["obstacle"]
        r = f["route"]
        assert all(r["drop_foliage"][k] <= r["drop_obstacle"][k] for k in r["drop_obstacle"])
        tot_lf += lf["n"]
        ob = w.obstacle_stats()["foliage"]
        assert ob["tgt_only"] > 0 and ob["eye_only"] > 0 and ob["eye_only"] <= w.obstacle_stats()["eye_blocked"]
    assert tot_lf > 0
    w = World(_with(base, obstacles=dict(fixed=discs["Forest"])), seeds=[32087])
    w.track_flight = True
    w.step(np.zeros((w.N, 1)))
    f = w.flight_stats()
    assert "lost_foliage" not in f and "drop_foliage" not in f["route"]


def test_ceval_accepts_foliage_world():
    """평가기(C++)에 숲 시야를 옮겼다 (10-22, EcoThreatModel.h FoliageChord·FoliageBlocked): 켠 설정도 허용 목록 검사(unsupported_settings)를 지나고,
    enabled false 를 적은 블록은 끈 세계로 본다. 도망길(route_fixed — COVER 그늘의 잎 포함, 파이썬 전용) 거부는 그대로다."""
    live_dir = ROOT / "results" / "v3" / "live"
    if str(live_dir) not in sys.path:
        sys.path.insert(0, str(live_dir))
    ce = pytest.importorskip("ceval")
    ref = load_v2_config(ce.REF_CFG)
    on = _with(ref, obstacles=dict(foliage=dict(enabled=True))).to_dict()
    off = _with(ref, obstacles=dict(foliage=dict(enabled=False, r=1.0))).to_dict()
    assert not ce.unsupported_settings(on)
    assert not ce.unsupported_settings(off)
    src = (live_dir / "ceval.py").read_text(encoding="utf-8")
    assert 'w._ob.get("foliage") is not None' not in src and 'route_fixed' in src


# --------------------------------------------------------------------- #
# 측정 도구 --world-set (results/v3/route/route_rules.py)
# --------------------------------------------------------------------- #


def _rr():
    d = ROOT / "results" / "v3" / "route"
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))
    import route_rules

    return route_rules


def test_world_set_parse_and_apply():
    rr = _rr()
    ws = rr.parse_world_set(["features.obstacles.foliage.enabled=true", "features.obstacles.foliage.r=1.5", "pred_view_r=12.0",
                             "v2.train.x=null"])
    assert ws == {"features.obstacles.foliage.enabled": True, "features.obstacles.foliage.r": 1.5, "pred_view_r": 12.0, "v2.train.x": None}
    cfg = {"pred_view_r": 10.0, "v2": {"features": {"obstacles": {"enabled": True, "fixed": [[1.0, 1.0, 0.2]]}}, "train": {}}}
    rr.apply_world_set(cfg, ws)
    assert cfg["v2"]["features"]["obstacles"]["foliage"] == {"enabled": True, "r": 1.5} and cfg["pred_view_r"] == 12.0
    assert cfg["v2"]["train"]["x"] is None and cfg["v2"]["features"]["obstacles"]["fixed"] == [[1.0, 1.0, 0.2]]
    for bad in (["noequals"], ["a=1", "a=2"], ["=1"], ["features..x=1"]):
        with pytest.raises(SystemExit):
            rr.parse_world_set(bad)
    with pytest.raises(SystemExit):
        rr.apply_world_set({"v2": {"features": {"obstacles": {"fixed": 3}}}}, {"features.obstacles.fixed.x": 1})
    assert rr.world_set_text({}) == "없음"


def test_world_set_arms_and_effect_table():
    """덮기가 있으면 RUN 팔마다 덮기 없음 팔(plain_…)을 더하고, 요약은 비교(길 − RUN)에 plain 을 넣지 않으며 덮기 효과 표(RUN − plain RUN)를 낸다."""
    rr = _rr()
    arms = rr.arms_of("rules", plain=True)
    assert len(arms) == 10 and [a for a in arms if a[4]] == [("run", 0, False, "N", True), ("run", 15, False, "N", True)]
    assert len(rr.arms_of("rules")) == 8 and rr.arms_of("g", "shelter", 0, True)[-1] == ("run", 0, False, "G", True)
    assert rr.arm_name("run", 0, False, "G", True) == "plain_run_q0_G"

    def row(tag, seed, reg, own_c, lf):
        n = {c: 0 for c in FLIGHT_CAUSES}
        n.update(obstacle=3, cover=2, switch=5)
        flight = dict(started=10, live_steps=1000, flee_steps=100, reflex_steps=80, shelter_end=1, n=n, steps={c: 10 * v for c, v in n.items()},
                      contact={c: own_c * v for c, v in n.items()}, own_n=5, own_steps=50, own_contact=5 * own_c)
        if lf is not None:                                                           # 숲 시야 켬 세계만 lost_foliage 칸이 있다
            flight["lost_foliage"] = dict(n=lf, steps=0, contact=0)
        return dict(tag=tag, seed=seed, region=reg, n=32, caught=1, starved=0, alive=31, shelter_steps=10, flight=flight, wall_s=1.0)

    arms = [("run", 0, False, "N", False), ("cover", 0, False, "N", False), ("run", 0, False, "N", True)]
    worlds = []
    for s in (1, 2, 3):
        for reg in ("A", "B"):
            worlds.append(row("run_q0:N", s, reg, 6 + s, 1))
            worlds.append(row("cover_q0:N", s, reg, 5 + s, 2))
            worlds.append(row("plain_run_q0:N", s, reg, 8 + 2 * s, None))
    d = dict(part="rules", seeds=[1, 2, 3], steps=100, world_set={"features.obstacles.foliage.enabled": True},
             arms=[dict(route=r, quiet_end=q, clump=c, world=wn, plain=pl, name=rr.arm_name(r, q, c, wn, pl)) for r, q, c, wn, pl in arms],
             worlds=worlds)
    s = rr.summarize_part(d)
    assert list(s["compare"]) == ["cover_q0"] and list(s["set_effect"]) == ["run_q0"]
    eff = s["set_effect"]["run_q0"]["all"]["p1"]
    assert eff["n"] == 3 and eff["diff"] < 0                                         # 덮기 RUN 쫓긴 시간이 덮기 없음보다 짧다(가짜 값)
    # 원판 놓침 가운데 잎 때문 = lost_foliage ÷ 원판 놓침 (1 ÷ 3, 2 ÷ 3) — 시작 대비가 아니다. 덮기 없음 팔(lost_foliage 칸 없음)은 —
    assert s["pooled"]["run_q0"]["all"]["foliage_of_obstacle"] == pytest.approx(1.0 / 3.0)
    assert s["pooled"]["cover_q0"]["all"]["foliage_of_obstacle"] == pytest.approx(2.0 / 3.0)
    assert math.isnan(s["pooled"]["plain_run_q0"]["all"]["foliage_of_obstacle"])
    assert s["compare"]["cover_q0"]["all"]["foliage_of_obstacle"]["diff"] == pytest.approx(1.0 / 3.0)
    text = "\n".join(rr.fmt_part(s, "t"))
    assert "숲 시야 효과" in text and "plain_run_q0" in text and "원판 놓침 가운데 잎 때문" in text
    rows = {ln.split("|")[1].strip(): ln for ln in text.splitlines() if ln.startswith("| ") and " / " in ln}
    assert "| 33.3% |" in rows["run_q0"] and "| 66.7% |" in rows["cover_q0"] and "| — |" in rows["plain_run_q0"]


def _fake_raw(rr, part, world_set, seeds=(1, 2, 3), code=None):
    """요약할 수 있는 작은 raw_<부분>.json 내용 (run 팔 둘·cover 팔 하나, 지역 하나). code = 셈 길 지문 (None = 옛 판 — 칸 없음)."""
    def flight(c):
        n = {k: 0 for k in FLIGHT_CAUSES}
        n.update(obstacle=3, cover=2, switch=5)
        return dict(started=10, live_steps=1000, flee_steps=100, reflex_steps=80, shelter_end=1, n=n, steps={k: 10 * v for k, v in n.items()},
                    contact={k: c * v for k, v in n.items()}, own_n=5, own_steps=50, own_contact=5 * c)

    arms = [("run", 0, False, "N", False), ("cover", 0, False, "N", False)]
    worlds = [dict(tag=f"{rr.arm_name(r, q, c, wn, pl)}:{wn}", seed=s, region="A", n=32, caught=1, starved=0, alive=31, shelter_steps=10,
                   flight=flight(6 + s + (r == "cover")), wall_s=1.0) for s in seeds for r, q, c, wn, pl in arms]
    d = dict(part=part, seeds=list(seeds), steps=100, world_set=world_set, workers=1, wall_s=1.0, world_wall_mean_s=1.0, sec_per_world_step=0.01,
             arms=[dict(route=r, quiet_end=q, clump=c, world=wn, plain=pl, name=rr.arm_name(r, q, c, wn, pl)) for r, q, c, wn, pl in arms],
             worlds=worlds)
    if code is not None:
        d["code"] = code
    return d


class _Ran(Exception):
    pass


_NOW = dict(world="w-now", tool="t-now")                                             # 시험용 셈 길 지문


def test_world_set_resume_uses_raw_files(tmp_path, monkeypatch):
    """끊긴 측정(rules 만 끝나 raw_rules.json 은 덮기 있음, meta.json 없음)을 이어 돌릴 때: 같은 덮기면 rules 를 건너뛰고 다음 부분을 돌리며 meta.json 을
    부분 전에 먼저 쓴다. 덮기 없이 g 만 돌리면 멈춘다(잎 켠 rules 와 잎 없는 G 를 섞지 않는다). --force 로 그 부분을 다시 잴 때만 다른 덮기를 받는다."""
    rr = _rr()
    W = {"features.obstacles.foliage.enabled": True, "features.obstacles.foliage.r": 3.0}
    args = ["--world-set", "features.obstacles.foliage.enabled=true", "--world-set", "features.obstacles.foliage.r=3.0"]
    (tmp_path / "raw_rules.json").write_text(json.dumps(_fake_raw(rr, "rules", W, code=_NOW)), encoding="utf-8")
    monkeypatch.setattr(rr, "prepare_info", lambda out, snap: dict(start=dict(zip="x.zip"), regions={}))
    monkeypatch.setattr(rr, "route_items", lambda *a, **k: [])
    monkeypatch.setattr(rr, "code_tag", lambda *a, **k: dict(_NOW))                 # 셈 길 지문은 같다 (지문 검사는 아래 시험)
    seen = []

    def run_items(items, workers, label):
        seen.append(label)
        raise _Ran(label)

    monkeypatch.setattr(rr, "run_items", run_items)
    out = ["run", "--out", str(tmp_path), "--workers", "1"]
    # (a) 같은 덮기로 이어 돌림: rules 건너뜀 → g 를 돈다, meta.json 은 그 전에 덮기와 함께 쓰였다
    with pytest.raises(_Ran):
        rr.main(out + ["--parts", "rules,g", "--g-route", "shelter"] + args)
    assert seen == ["g"] and json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))["world_set"] == W
    # (b) 덮기 없이 g 만: raw_rules 의 덮기와 달라 멈춘다 (meta.json 이 없어도 — 지운 뒤 다시)
    (tmp_path / "meta.json").unlink()
    with pytest.raises(SystemExit, match="rules"):
        rr.main(out + ["--parts", "g", "--g-route", "shelter"])
    with pytest.raises(SystemExit, match="rules"):
        rr.main(out + ["--parts", "g", "--g-route", "shelter", "--force"])         # --force 여도 rules 를 다시 재지 않으면 멈춘다
    assert seen == ["g"]
    # (c) --force 와 rules 를 --parts 에: 다시 재므로 받는다
    with pytest.raises(_Ran):
        rr.main(out + ["--parts", "rules", "--force"])
    assert seen == ["g", "rules"]


def test_world_set_report_checks_parts_and_meta(tmp_path):
    """report: 세계 덮기는 부분 raw 파일의 기록이다 — meta.json 이 없어도 그 덮기로 오라클을 견주고(같으면 판단표에 쓴다), 부분끼리 다르거나 meta.json 의
    덮기가 다르면 멈춘다. 옛 판(덮기 칸 없음)은 덮기 없음."""
    rr = _rr()
    W = {"features.obstacles.foliage.enabled": True}
    (tmp_path / "raw_rules.json").write_text(json.dumps(_fake_raw(rr, "rules", W)), encoding="utf-8")
    (tmp_path / "oracle.json").write_text(json.dumps(dict(meta=dict(world_set=W))), encoding="utf-8")
    rr.main(["report", "--out", str(tmp_path)])
    text = (tmp_path / "rules.md").read_text(encoding="utf-8")
    assert "세계 덮기 (--world-set, 모든 팔·비교 기준 RUN 에 같게): features.obstacles.foliage.enabled=true" in text and "오라클을 판단표에 쓰지 않는다" not in text
    (tmp_path / "oracle.json").write_text(json.dumps(dict(meta={})), encoding="utf-8")
    rr.main(["report", "--out", str(tmp_path)])
    assert "오라클을 판단표에 쓰지 않는다" in (tmp_path / "rules.md").read_text(encoding="utf-8")
    (tmp_path / "meta.json").write_text(json.dumps(dict(world_set={})), encoding="utf-8")
    with pytest.raises(SystemExit, match="meta.json"):
        rr.main(["report", "--out", str(tmp_path)])
    (tmp_path / "meta.json").write_text(json.dumps(dict(world_set=W)), encoding="utf-8")
    old = _fake_raw(rr, "clump", None)
    old.pop("world_set")                                                             # 옛 판 = 덮기 없음
    (tmp_path / "raw_clump.json").write_text(json.dumps(old), encoding="utf-8")
    with pytest.raises(SystemExit, match="부분끼리"):
        rr.main(["report", "--out", str(tmp_path)])


# --------------------------------------------------------------------- #
# 측정 도구 셈 길 지문 (10-22 — route_rules.code_tag: 다른 셈 길로 잰 부분을 이어 돌리거나 한 보고에 섞지 않는다)
# --------------------------------------------------------------------- #


def test_route_code_guards_resume(tmp_path, monkeypatch):
    """이미 있는 raw 의 지문이 지금과 다르면(옛 판 — 칸 없음, 세계·측정 지문 하나라도) 이어 돌리지 않는다 — g 만 돌리면 옛 rules 로 규칙을 고르게 되므로
    --force 여도 rules 를 다시 재지 않으면 멈춘다(meta.json 도 쓰지 않는다). --force 와 rules 면 다시 잰다(부분은 늘 rules → g 차례). 같은 지문이면 건너뛴다."""
    rr = _rr()
    monkeypatch.setattr(rr, "prepare_info", lambda out, snap: dict(start=dict(zip="x.zip"), regions={}))
    monkeypatch.setattr(rr, "route_items", lambda *a, **k: [])
    monkeypatch.setattr(rr, "code_tag", lambda *a, **k: dict(_NOW))
    seen = []

    def run_items(items, workers, label):
        seen.append(label)
        raise _Ran(label)

    monkeypatch.setattr(rr, "run_items", run_items)
    out = ["run", "--out", str(tmp_path), "--workers", "1"]
    for old in (None, dict(_NOW, world="w-old"), dict(_NOW, tool="t-old")):
        (tmp_path / "raw_rules.json").write_text(json.dumps(_fake_raw(rr, "rules", {}, code=old)), encoding="utf-8")
        for extra in ([], ["--force"]):
            with pytest.raises(SystemExit, match="셈 길"):
                rr.main(out + ["--parts", "g", "--g-route", "shelter"] + extra)
        assert seen == [] and not (tmp_path / "meta.json").exists()
    with pytest.raises(_Ran):
        rr.main(out + ["--parts", "g,rules", "--force", "--g-route", "shelter"])
    assert seen == ["rules"] and json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))["code"] == _NOW
    (tmp_path / "raw_rules.json").write_text(json.dumps(_fake_raw(rr, "rules", {}, code=_NOW)), encoding="utf-8")
    with pytest.raises(_Ran):
        rr.main(out + ["--parts", "rules,g", "--g-route", "shelter"])
    assert seen == ["rules", "g"]


def test_route_code_change_during_part(tmp_path, monkeypatch):
    """부분 중간에 셈 길이 바뀌면 그 부분을 지문 없이(code None·code_changed) 적고 멈춘다 — 다음 부분을 돌리지 않고, 이어 돌리기도 받지 않으며, 보고 머리에 적는다."""
    rr = _rr()
    monkeypatch.setattr(rr, "prepare_info", lambda out, snap: dict(start=dict(zip="x.zip"), regions={}))
    monkeypatch.setattr(rr, "route_items", lambda *a, **k: [])
    edit = dict(_NOW, world="w-edit")
    tags = iter([dict(_NOW), dict(edit)])
    monkeypatch.setattr(rr, "code_tag", lambda *a, **k: next(tags))
    fake = _fake_raw(rr, "rules", {})
    monkeypatch.setattr(rr, "arms_of", lambda part, *a, **k: [("run", 0, False, "N", False), ("cover", 0, False, "N", False)])   # _fake_raw 의 팔
    monkeypatch.setattr(rr, "run_items", lambda items, workers, label: [(w["tag"], {k: v for k, v in w.items() if k != "tag"}) for w in fake["worlds"]])
    out = ["run", "--out", str(tmp_path), "--workers", "1"]
    with pytest.raises(SystemExit, match="바뀌었다"):
        rr.main(out + ["--parts", "rules,g", "--g-route", "shelter"])
    raw = json.loads((tmp_path / "raw_rules.json").read_text(encoding="utf-8"))
    assert raw["code"] is None and raw["code_changed"] == dict(start=_NOW, end=edit) and not (tmp_path / "raw_g.json").exists()
    assert json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))["times"]["rules"]["code"] is None
    monkeypatch.setattr(rr, "code_tag", lambda *a, **k: dict(edit))
    with pytest.raises(SystemExit, match="셈 길"):
        rr.main(out + ["--parts", "g", "--g-route", "shelter"])
    rr.main(["report", "--out", str(tmp_path)])
    text = (tmp_path / "rules.md").read_text(encoding="utf-8")
    assert "rules 측정 중 셈 길이 바뀌었다" in text and "지문을 적기 전 판" not in text


def test_route_code_report_checks(tmp_path):
    """report: 부분끼리 셈 길 지문이 다르면(옛 판 지문 없음과 새 판 포함) 멈춘다. 오라클은 세계 지문이 같을 때만 판단표에 쓴다(측정 지문은 도구가 달라
    견주지 않는다). 지문 없는 옛 폴더는 보고를 다시 내되 머리에 '새 폴더에서 처음부터 다시 잰다'를 적는다."""
    rr = _rr()
    (tmp_path / "raw_rules.json").write_text(json.dumps(_fake_raw(rr, "rules", {}, code=_NOW)), encoding="utf-8")
    (tmp_path / "oracle.json").write_text(json.dumps(dict(meta=dict(world_set={}, code=dict(world="w-now", tool="t-oracle")))), encoding="utf-8")
    rr.main(["report", "--out", str(tmp_path)])
    text = (tmp_path / "rules.md").read_text(encoding="utf-8")
    assert "세계 w-now · 측정 t-now" in text and "오라클을 판단표에 쓰지 않는다" not in text and "지문을 적기 전 판" not in text
    for o_code in (None, dict(world="w-old", tool="t-oracle")):
        (tmp_path / "oracle.json").write_text(json.dumps(dict(meta=dict(world_set={}, code=o_code))), encoding="utf-8")
        rr.main(["report", "--out", str(tmp_path)])
        text = (tmp_path / "rules.md").read_text(encoding="utf-8")
        assert "오라클 세계 셈 길" in text and "오라클을 판단표에 쓰지 않는다" in text
    (tmp_path / "raw_g.json").write_text(json.dumps(_fake_raw(rr, "g", {})), encoding="utf-8")            # 옛 판 g 와 새 판 rules
    with pytest.raises(SystemExit, match="셈 길 지문이 다르다"):
        rr.main(["report", "--out", str(tmp_path)])
    (tmp_path / "raw_rules.json").write_text(json.dumps(_fake_raw(rr, "rules", {})), encoding="utf-8")     # 둘 다 옛 판
    (tmp_path / "oracle.json").write_text(json.dumps(dict(meta=dict(world_set={}))), encoding="utf-8")
    rr.main(["report", "--out", str(tmp_path)])
    text = (tmp_path / "rules.md").read_text(encoding="utf-8")
    assert "지문을 적기 전 판" in text and "새 폴더에서 처음부터" in text and "오라클을 판단표에 쓰지 않는다" not in text


def test_route_code_tag_tracks_files(tmp_path, monkeypatch):
    """code_tag: 세계 = live.eval_code_tag('python')(실시간 판정 저장 열쇠와 같은 지문 — 매번 새로 재서 측정 중 파일이 바뀌면 다르다), 측정 = 함수 원문·
    상수. 오라클의 세계 지문은 규칙 측정과 같고 측정 지문은 다르다. 오라클 run 은 지문을 raw·oracle.json 에 적고, 측정 중 바뀌면 지문 없이 적는다."""
    rr = _rr()
    import oracle as orc

    lv = rr.lv
    monkeypatch.setattr(lv, "_CODE", {})
    now = rr.code_tag()
    assert now["world"] == lv.eval_code_tag("python") and len(now["tool"]) == 16
    o = orc.code_tag()
    assert o["world"] == now["world"] and o["tool"] != now["tool"]
    assert rr.code_tag(consts=dict(x=1))["tool"] != rr.code_tag(consts=dict(x=2))["tool"]
    monkeypatch.setattr(lv, "ROOT", tmp_path)
    monkeypatch.setattr(lv, "EVAL_CODE_FILES", ("w.py",))
    (tmp_path / "w.py").write_text("a = 1\n", encoding="utf-8")
    a = rr.code_tag()
    (tmp_path / "w.py").write_text("a = 2\n", encoding="utf-8")
    b = rr.code_tag()
    assert a["world"] != b["world"] and a["tool"] == b["tool"]

    od = tmp_path / "oracle"
    monkeypatch.setattr(rr, "prepare_info", lambda out, snap: dict(start=dict(zip="x.zip"), regions={}))
    monkeypatch.setattr(orc.ad, "make_jobs", lambda *a, **k: [])
    monkeypatch.setattr(orc, "code_tag", lambda: dict(_NOW))
    orc.main(["run", "--out", str(od), "--workers", "1"])
    assert json.loads((od / "oracle_raw.json").read_text(encoding="utf-8"))["code"] == _NOW
    assert json.loads((od / "oracle.json").read_text(encoding="utf-8"))["meta"]["code"] == _NOW
    tags = iter([dict(_NOW), dict(_NOW, world="w-edit")])
    monkeypatch.setattr(orc, "code_tag", lambda: next(tags))
    orc.main(["run", "--out", str(od), "--workers", "1"])
    raw = json.loads((od / "oracle_raw.json").read_text(encoding="utf-8"))
    assert raw["code"] is None and raw["code_changed"]["end"]["world"] == "w-edit"
    assert json.loads((od / "oracle.json").read_text(encoding="utf-8"))["meta"]["code"] is None
