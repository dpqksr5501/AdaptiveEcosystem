"""야생 (w3) 도망길 1단계 (10-21 사용자 '도망 방향을 두뇌가 고름' — 설계 Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 6·7·9-0절, 측정 전용 선택 키
wild_flight.route_fixed·quiet_end — env_v2/world.py 모듈 docstring '야생 1단계' (w3) 도망길).

- 끔(키 없음 = route_fixed null·quiet_end 0)은 HEAD(c44d37e, git archive 로 돌린 같은 셈 — 10-22 동족 차례 합 두 줄을 넣은 사본)와 궤적 해시가 같다. 'run' 은 끔과 비트 단위로 같고 길 기록만 더한다.
- 기하(`flight_route_geometry`): COVER 는 늑대 눈길이 줄기에 더 가리는 쪽을 고르고, 늑대가 먼저 닿는 길·벽 여유 밖 길을 뺀다. SHELTER 는 늑대보다 먼저 닿는
  은신처만(뒤쪽·너무 먼 은신처는 빼고, 같으면 낮은 번호). OPEN 은 a₀ 에 가장자리 굽히기·벽 여유만.
- quiet_end: 붙잡는 늑대를 Q 스텝 이어 알아채지 못하면(눈·발소리 모두) 도주가 끝난다. 쫓는(뛰는) 늑대의 발소리는 줄기가 막지 않아 도주가 이어진다.
- 길 고정 세계의 불변식(길별 실행 스텝 합 = 반사 스텝, 시작 = 도주 시작, 도망의 길별 끝 까닭 합 = 시작), 오라클의 다시 고르기(route_redecide).
- 옛 설정의 config digest 그대로 (선택 키는 features.OPTIONAL_KEYS 기본값).
- 9-4 판단표(route_rules.decide): 위에서부터 처음으로 '아니오'가 아닌 줄에서 멈춘다(모르는 줄을 건너뛰지 않는다). 오라클(oracle.summarize)도 P1 과 같은
  쫓긴 시간으로 판단한다(도망 길이는 보조).
시드는 탐색 32084~32099·학습 32000~32049 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import hashlib
import importlib.util
import json

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import features as F
from env_v2.config import load_v2_config
from env_v2.world import (FLIGHT_CAUSES, ROUTE_COVER, ROUTE_NAMES, ROUTE_NONE, ROUTE_OPEN, ROUTE_RUN, ROUTE_SHELTER, WF_PANIC, World,
                          flight_route_geometry, wf_edge_steer, wf_wall_keep)

CFG = ROOT / "configs"
OBS = CFG / "v3_wild3_obs_mirror.yaml"          # 거울 (부활 없음, 장애물·늑대 4)
TRAIN = CFG / "v3_r5_train.yaml"                # 학습 세계 (부활 있음)

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")

# HEAD(c44d37e) 를 git archive 로 풀어 같은 `_traj_hash` 로 잰 값 (도망길 코드를 넣기 전).
# 10-22 다시 잼: world.py 가 동족 무리 중심·분리를 C++ 과 같은 j 차례 합으로 더하게 되어(`_seq_sum`) 끝 비트가 달라졌다 — 사본의 그 두 줄만 같은
# 차례 합으로 바꾼 HEAD(tests/kin_seq.py patch_tree)로 잰 값이고 지금 코드(끔)와 같다. 옛 값(행렬곱 HEAD): obs_Forest_sat0 c7a7b4cd…·train_respawn 6d99c93d…
HEAD_HASH = {
    "obs_Forest_sat0": "a1d6cde8248821e73fb379f7196f461f0ec8ba9f0e80a4a0e0b18968a308c343",
    "train_respawn": "3f6c580f9cc3147dcb93ef5fe7bf050d44daf4b846b9ca860ddcdbf606f77692",
}
# HEAD 의 config digest (results/v3/mirror/run_mirror.config_digest — wild_flight 를 켠 설정 전부)
HEAD_DIGEST = {
    "v3_r4_train.yaml": "a0d95473e1c7", "v3_r5_train.yaml": "a119c35118d8", "v3_wild1_mirror.yaml": "38c890558a46",
    "v3_wild2_mirror.yaml": "23c0214c3525", "v3_wild2_obstacle_mirror.yaml": "53bf911063a0", "v3_wild2_pack_mirror.yaml": "71b077d98e5e",
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
def forest():
    """거울 숲 지역(나무 원판이 늑대 눈길을 가림, 늑대 포만 끔 — N 세계), 사슴 32."""
    r4 = _module("_r4_for_route", ROOT / "results" / "v3" / "r4" / "r4_eval.py")
    return _with(load_v2_config(OBS).replace(N=32), wild_weather=dict(region="Forest"), obstacles=dict(fixed=r4.region_discs()["Forest"]),
                 wild_satiation=dict(enabled=False))


def _H(*arrs):
    h = hashlib.sha256()
    for a in arrs:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h


def _traj_hash(cfg, seed, steps, acts_seed=7):
    """무작위 행동(먹기·도망·숨기) 궤적·덮기·도망 기록(길 칸 뺌)·야생·사냥 통계·v1 난수의 해시 (HEAD 값을 잰 셈과 같다)."""
    w = World(cfg, seeds=[seed])
    w.track_flight = True
    rng = np.random.default_rng(acts_seed)
    h = hashlib.sha256()
    for _ in range(steps):
        o, r, d, to = w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        h.update(_H(o, r, d, to, w.pos, w.pred_pos, w.energy, w.wf_mode, w.wf_dir).digest())
    f = w.flight_stats()
    f.pop("route", None)
    f.pop("quiet_ends", None)
    f.pop("hide", None)                 # 10-23 숨은 뒤 지켜보기 칸 (HEAD 뒤에 더한 통계 전용 칸 — 궤적과 옛 칸은 그대로)
    f.pop("episode", None)              # 10-24 쫓김 사건 칸 (HEAD 뒤에 더한 통계 전용 칸 — 궤적과 옛 칸은 그대로)
    ws = w.wild_stats()
    ws.pop("panic_quiet_ends", None)
    st = json.dumps(dict(flight=f, wild=ws, hunt=w.hunt_stats(), rng=str(w.rng.bit_generator.state)), sort_keys=True, default=str)
    h.update(st.encode())
    return h.hexdigest(), w


def _run(cfg, seed, steps, acts_seed=7):
    w = World(cfg, seeds=[seed])
    w.track_flight = True
    rng = np.random.default_rng(acts_seed)
    out = []
    for _ in range(steps):
        o, r, d, _ = w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        out.append((o.copy(), r.copy(), d.copy(), w.pos.copy(), w.pred_pos.copy(), w.energy.copy(), w.wf_dir.copy()))
    return out, w


def _same(a, b):
    assert len(a) == len(b)
    for t, (x, y) in enumerate(zip(a, b)):
        for k, (u, v) in enumerate(zip(x, y)):
            assert np.array_equal(u, v), (t, k)


# --------------------------------------------------------------------- #
# 끔 = HEAD, 'run' = 끔 (비트 동일)
# --------------------------------------------------------------------- #


def test_off_matches_head(forest):
    """키 없음(끔)은 HEAD 궤적 해시와 같다 — 거울 숲 N 세계 900 스텝·학습 세계(부활 있음) 900 스텝. 끈 세계의 도망 기록에는 길 칸이 없다."""
    h, w = _traj_hash(forest, 32084, 900)
    assert h == HEAD_HASH["obs_Forest_sat0"]
    assert "route" not in w.flight_stats() and "quiet_ends" not in w.flight_stats() and "panic_quiet_ends" not in w.wild_stats()
    assert not hasattr(w, "flight_route") and not hasattr(w, "wf_quiet")
    h2, _ = _traj_hash(load_v2_config(TRAIN).replace(N=24), 32001, 900, 5)
    assert h2 == HEAD_HASH["train_respawn"]


def test_explicit_off_values_equal_missing_keys(forest):
    """route_fixed null·quiet_end 0 을 적은 세계 = 키가 없는 세계 (같은 해시)."""
    h, _ = _traj_hash(_with(forest, wild_flight=dict(route_fixed=None, quiet_end=0)), 32084, 900)
    assert h == HEAD_HASH["obs_Forest_sat0"]


def test_route_run_equals_off(forest):
    """'run' 고정 = 끔: 궤적·관측·보상·난수가 비트 단위로 같고, 도망 기록은 route 칸만 더한다. 길 기록 불변식."""
    a, wa = _run(forest, 32085, 900)
    b, wb = _run(_with(forest, wild_flight=dict(route_fixed="run")), 32085, 900)
    _same(a, b)
    assert wa.rng.bit_generator.state == wb.rng.bit_generator.state
    fa, fb = wa.flight_stats(), wb.flight_stats()
    r = fb.pop("route")
    assert fa == fb
    assert r["fixed"] == "run" and r["quiet_end"] == 0
    assert r["steps"]["run"] == fb["reflex_steps"] > 0 and r["steps"]["cover"] == r["steps"]["shelter"] == r["steps"]["open"] == 0
    assert r["onsets"] == wb.wild_stats()["panic_starts"] > 0
    assert r["fallback"] == 0 and r["switches"] == 0 and sum(r["invalid"].values()) == 0
    assert r["onset_cover"] + r["onset_shelter"] - r["onset_both"] <= r["onsets"]
    assert sum(sum(v["n"].values()) for v in r["by_route"].values()) == fb["started"]
    assert sum(r["chased_steps"].values()) >= sum(r["hidden_steps"].values())


@pytest.mark.parametrize("route", ["cover", "shelter", "open"])
def test_route_fixed_variants(forest, route):
    """고정 길 세계: 길별 실행 스텝은 RUN 과 그 길에만 있고 합 = 반사 스텝, 시작 = 도주 시작, 길 상태는 도주 중에만 있고 방향 = 그 길의 후보 방향
    (SHELTER 는 결정 스텝만 — 유지 중에는 결정 때 고른 은신처 쪽). 궤적은 끔과 다르다."""
    cfg = _with(forest, wild_flight=dict(route_fixed=route))
    a, _ = _run(forest, 32086, 600)
    w = World(cfg, seeds=[32086])
    w.track_flight = True
    rng = np.random.default_rng(7)
    out, seen = [], set()
    k = ROUTE_NAMES.index(route)
    for _ in range(600):
        o, r, d, _ = w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        out.append((o.copy(), r.copy(), d.copy(), w.pos.copy(), w.pred_pos.copy(), w.energy.copy(), w.wf_dir.copy()))
        pan = w.wf_mode == WF_PANIC
        assert (w.flight_route[~pan] == ROUTE_NONE).all() and (w.flight_route[pan] >= 0).all()
        assert set(np.unique(w.flight_route[pan]).tolist()) <= {ROUTE_RUN, k}
        on = pan & (w.flight_route == k)
        if route != "shelter":
            assert np.array_equal(w.wf_dir[on], w.route_cand_dir[on, k])
        else:
            dec = on & w.route_decide
            assert np.array_equal(w.wf_dir[dec], w.route_cand_dir[dec, k]) and (w.route_k[on] >= 0).all()
        runm = pan & (w.flight_route == ROUTE_RUN)
        assert np.array_equal(w.wf_dir[runm], w.route_cand_dir[runm, ROUTE_RUN])
        seen |= set(np.unique(w.flight_route[pan]).tolist())
    f = w.flight_stats()
    rt = f["route"]
    assert k in seen and rt["steps"][route] > 0
    assert sum(rt["steps"].values()) == f["reflex_steps"]
    assert rt["onsets"] == w.wild_stats()["panic_starts"]
    assert all(v == 0 for nm, v in rt["steps"].items() if nm not in ("run", route))
    assert sum(sum(v["n"].values()) for v in rt["by_route"].values()) == f["started"]
    assert rt["picked"][route] + rt["picked"]["run"] == rt["decisions"]
    if route == "open":
        assert rt["steps"]["run"] == 0 and rt["fallback"] == 0
    else:
        assert rt["fallback"] > 0                   # 가능하지 않을 때는 RUN
    with pytest.raises(AssertionError):
        _same(a, out)


def test_route_respawn_world_clears_state():
    """학습 세계(부활 있음)에서도 길 상태는 도주 중에만 있다(죽어 다시 난 칸은 지운다), 도망 기록 불변식."""
    cfg = _with(load_v2_config(TRAIN).replace(N=24), wild_flight=dict(route_fixed="cover"))
    w = World(cfg, seeds=[32002])
    w.track_flight = True
    rng = np.random.default_rng(5)
    dead_n = 0
    for _ in range(900):
        _, _, d, _ = w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        dead_n += int(d.sum())
        pan = w.wf_mode == WF_PANIC
        assert (w.flight_route[~pan] == ROUTE_NONE).all() and (w.route_force == ROUTE_NONE).all()
    f = w.flight_stats()
    assert dead_n > 0 and sum(f["route"]["steps"].values()) == f["reflex_steps"]
    assert sum(sum(v["n"].values()) for v in f["route"]["by_route"].values()) == f["started"]


# --------------------------------------------------------------------- #
# 기하 (flight_route_geometry)
# --------------------------------------------------------------------- #

P0, A0, Q0 = np.array([[30.0, 30.0]]), np.array([[0.0, 1.0]]), np.array([[30.0, 18.0]])
WEST = [[28.0, 24.0, 0.8], [26.5, 26.0, 0.8], [25.0, 28.0, 0.8]]       # 사슴 서쪽(왼쪽 뒤)에 늘어선 줄기 — 북서로 달리면 늑대 눈길이 가린다


def _geo(p=P0, a0=A0, q=Q0, S=None, discs=(), cov=(), size=60.0, mg=1.0, edge=5.0, prev=None, keep=None):
    q = np.asarray(q, dtype=np.float64).reshape(-1, 2)
    p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
    S = np.ones((len(p), len(q)), dtype=bool) if S is None else np.asarray(S, dtype=bool)
    d = np.sqrt(((p[:, None, :] - q[None, :, :]) ** 2).sum(-1))
    cov = np.asarray(cov, dtype=np.float64).reshape(-1, 3)
    return flight_route_geometry(p, a0, q, S, d, cov[:, :2], cov[:, 2], np.asarray(discs, dtype=np.float64).reshape(-1, 3), size, mg, edge,
                                 prev, keep)


def test_cover_picks_more_shadowed_side():
    """COVER: 줄기가 없으면 불가(H* 0). 서쪽 줄기 → 반시계(+45°, 북서) 쪽을 고르고 H* ≥ 1/3, 거울로 옮긴 동쪽 줄기 → 시계(−45°) 쪽.
    점수 = H + 0.1·cos θ 라 같은 H 면 곧은 쪽, 지난 방향은 +0.15."""
    g = _geo()
    assert not g["cover_ok"][0] and g["cover_best_h"][0] == 0.0 and g["cover_j"][0] == 0 and np.allclose(g["cover_dir"], A0)
    g = _geo(discs=WEST)
    h = g["cover_h"][0]
    assert g["cover_ok"][0] and g["cover_keep"][0] and g["cover_j"][0] == 3 and h[3] > h[0] and g["cover_best_h"][0] >= 1.0 / 3.0
    assert g["cover_dir"][0, 0] < 0.0 < g["cover_dir"][0, 1] and np.allclose(g["cover_raw"][0], [-np.sqrt(0.5), np.sqrt(0.5)])
    east = [[60.0 - x, y, r] for x, y, r in WEST]
    g2 = _geo(discs=east)
    assert g2["cover_j"][0] == 4 and g2["cover_dir"][0, 0] > 0.0 and np.isclose(g2["cover_best_h"][0], g["cover_best_h"][0])
    # 지난 방향 가산: 줄기가 없어 H 가 모두 0 이면 곧은 쪽(0.1·cos 0 = 0.1)보다 지난 방향(+22.5°: 0.1·cos 22.5 + 0.15)을 이어 간다
    prev = np.array([[-0.3826834323650898, 0.9238795325112867]])
    g3 = _geo(prev=prev)
    assert g3["cover_valid"][0, 7] and g3["cover_j"][0] == 7 and np.allclose(g3["cover_raw"][0], prev[0]) and not g3["cover_ok"][0]
    # 지난 방향이 a₀ 와 반대(e_prev·a₀ < 0)면 후보에서 빠진다
    g4 = _geo(discs=WEST, prev=np.array([[0.0, -1.0]]))
    assert not g4["cover_valid"][0, 7] and g4["cover_j"][0] == 3


def test_cover_race_and_wall_exclusion():
    """COVER: 옆 늑대(같은 집합 S)가 길 위 점에 사슴보다 먼저 닿으면 그 방향을 뺀다(가려도). 끝 표본점이 벽 여유 밖이면 뺀다."""
    g = _geo(q=[[30.0, 18.0], [22.0, 34.0]], discs=WEST)
    assert not g["cover_valid"][0, 3] and not g["cover_valid"][0, 5] and g["cover_j"][0] != 3
    # S 밖(반사가 보지 않는 늑대)이면 경주에 넣지 않는다
    g = _geo(q=[[30.0, 18.0], [22.0, 34.0]], S=[[True, False]], discs=WEST)
    assert g["cover_valid"][0, 3] and g["cover_j"][0] == 3
    # 북쪽 벽 가까이: 곧은 길의 끝점(12 단위 앞)이 벽 여유 밖
    g = _geo(p=[[30.0, 50.0]], q=[[30.0, 38.0]])
    assert not g["cover_valid"][0, :3].any() and g["cover_valid"][0, 3:7].all()     # 0·±22.5° 는 12 단위 앞이 벽 여유 밖, ±45·±67.5° 는 안
    g = _geo(p=[[30.0, 55.0]], q=[[30.0, 43.0]])
    assert not g["cover_valid"][0].any() and g["cover_j"][0] == -1 and not g["cover_ok"][0] and np.allclose(g["cover_dir"], 0.0)


def test_shelter_reachability():
    """SHELTER: 앞(v·a₀ ≥ 0)·가장자리 0 < e ≤ 20·늑대보다 2 단위 먼저 닿는 문만. k* = 가장 가까운(같으면 낮은 번호), μ* = 그 여유, 방향 = 중심 쪽.
    유지는 μ_k ≥ 0 — 늑대가 문 쪽으로 오면 무효."""
    north = [30.0, 45.0, 6.0]
    g = _geo(cov=[north])
    assert g["shelter_ok"][0] and g["shelter_k"][0] == 0 and np.isclose(g["shelter_mu"][0], 21.0 - 9.0) and np.allclose(g["shelter_dir"], [[0.0, 1.0]])
    # 문 앞을 지키는 늑대 → 불가
    g = _geo(q=[[30.0, 18.0], [30.0, 42.0]], cov=[north])
    assert not g["shelter_ok"][0] and g["shelter_k"][0] == -1 and g["shelter_mu"][0] == 0.0
    # 뒤쪽(늑대 쪽) 은신처·너무 먼 은신처는 후보가 아니다
    assert not _geo(cov=[[30.0, 14.0, 3.0]])["shelter_ok"][0]
    assert not _geo(cov=[[30.0, 57.0, 1.0]])["shelter_ok"][0]                     # e = 26 > 20
    # 같은 거리면 낮은 번호, 더 가까운 것이 먼저
    g = _geo(cov=[[40.0, 40.0, 4.0], [20.0, 40.0, 4.0]])
    assert g["shelter_k"][0] == 0
    g = _geo(cov=[[40.0, 40.0, 4.0], [20.0, 40.0, 5.0]])
    assert g["shelter_k"][0] == 1
    # 유지: 고른 은신처의 μ ≥ 0 이면 유지, 늑대가 문에 가까우면 무효 (들어갈 때 문턱 2 와 다르다)
    g = _geo(q=[[30.0, 18.0], [30.0, 49.0]], cov=[north], keep=np.array([0]), S=[[True, True]])
    assert not g["shelter_ok"][0] and g["keep_ok"][0] and 0.0 <= g["keep_mu"][0] < 2.0
    g = _geo(q=[[30.0, 18.0], [30.0, 43.0]], cov=[north], keep=np.array([0]))
    assert not g["keep_ok"][0]
    g = _geo(cov=[north], keep=np.array([-1]))
    assert g["keep_mu"][0] == -np.inf and not g["keep_ok"][0]


def test_open_is_a0_with_edge_and_wall():
    """OPEN = a₀ → 가장자리 굽히기 → 벽 여유 (은신처 굽히기 없음)."""
    g = _geo(cov=[[30.0, 45.0, 6.0]])
    assert np.array_equal(g["open_dir"], A0)
    p, a0 = np.array([[2.0, 30.0]]), np.array([[-1.0, 0.0]])
    g = _geo(p=p, a0=a0, q=[[12.0, 30.0]])
    assert np.array_equal(g["open_dir"], wf_wall_keep(p, wf_edge_steer(p, a0, 60.0, 5.0), 60.0, 1.0))
    assert g["open_dir"][0, 0] >= 0.0 or abs(g["open_dir"][0, 1]) > 0.5


def test_route_geometry_has_no_side_effects(forest):
    """길 기하는 세계 통계(원판 눈길 셈)를 건드리지 않는다 — 'run' 세계의 장애물 통계가 끔과 같다."""
    _, wa = _run(forest, 32087, 300)
    _, wb = _run(_with(forest, wild_flight=dict(route_fixed="run")), 32087, 300)
    assert wa.obstacle_stats() == wb.obstacle_stats()


# --------------------------------------------------------------------- #
# quiet_end (설계 7절)
# --------------------------------------------------------------------- #


def _quiet_scene(qe, running):
    """사슴 0 이 (30, 30)에서 도주 중, 사냥 중인 늑대 0 이 남쪽 9 단위(줄기 하나가 눈길을 가림, 붙잡는 거리 safe_r 안), 다른 늑대는 모서리(safe_r 밖).
    running 이면 늑대 0 이 이 사슴 쪽으로 뛰는 걸음(발소리 반경 r_loud × 날씨 > 9)."""
    cfg = _with(load_v2_config(OBS).replace(N=4), wild_satiation=dict(enabled=False), obstacles=dict(fixed=[[30.0, 25.5, 1.0]]),
                wild_flight=dict(quiet_end=qe))
    w = World(cfg, seeds=[32090])
    w.pos = np.array([[30.0, 30.0], [30.0, 55.0], [55.0, 30.0], [5.0, 30.0]])
    w.head = np.array([[0.0, -1.0]] + [[1.0, 0.0]] * 3)
    w.pred_pos = np.array([[30.0, 21.0], [2.0, 2.0], [58.0, 58.0], [2.0, 58.0]])
    w.pred_vel = np.zeros((w.M, 2))
    if running:
        w.pred_vel[0] = (0.0, w.cfg.herb_speed)
    w.pred_running = np.zeros(w.M, dtype=bool)
    w.pred_running[0] = running
    w.pred_cd[:] = 0
    w.pred_asleep[:] = False
    w.pred_target = np.full(w.M, -1)
    w.wf_mode[:] = 0
    w.wf_mode[0] = WF_PANIC
    w._g = w._geometry()
    return w


@pytest.mark.parametrize("qe", [15, 4])
def test_quiet_end_ends_after_q_unnoticed_steps(qe):
    """눈(줄기가 가림)·귀(서 있는 늑대는 소리 없음) 모두 알아채지 못한 도주는 정확히 quiet_end 번째 갱신에서 끝난다(Q = 1..qe). 끝난 수를 센다."""
    w = _quiet_scene(qe, running=False)
    assert not w._g["wf_pvis"][0].any() and not w._g["in_cover"][0]
    for k in range(1, qe + 1):
        w._wf_update(np.zeros(w.N, dtype=bool))
        if k < qe:
            assert w.wf_mode[0] == WF_PANIC and w.wf_quiet[0] == k
    assert w.wf_mode[0] != WF_PANIC and w.wf_quiet[0] == 0
    assert w.wild_stats()["panic_quiet_ends"] == 1


def test_quiet_end_off_and_footsteps_keep_flight():
    """quiet_end 0(끔)이면 늑대가 safe_r 안에 있는 한 도주가 이어진다. 켜도 쫓는 늑대의 발소리(줄기가 막지 않음)를 들으면 Q = 0 이라 이어진다."""
    w = _quiet_scene(0, running=False)
    for _ in range(40):
        w._wf_update(np.zeros(w.N, dtype=bool))
        assert w.wf_mode[0] == WF_PANIC
    w = _quiet_scene(15, running=True)
    assert w._g["wf_pvis"][0, 0]                         # 눈은 가려도 발소리로 안다
    for _ in range(40):
        w._wf_update(np.zeros(w.N, dtype=bool))
        assert w.wf_mode[0] == WF_PANIC and w.wf_quiet[0] == 0
    assert w.wild_stats()["panic_quiet_ends"] == 0


def test_quiet_end_world(forest):
    """quiet_end 15 세계: 끝 규칙으로 끝난 도주가 있고(도망 기록·야생 통계 같은 값) 궤적이 끔과 다르다. 'run' 과 함께 켜도 같은 세계다."""
    a, _ = _run(forest, 32088, 600)
    b, wb = _run(_with(forest, wild_flight=dict(quiet_end=15)), 32088, 600)
    c, wc = _run(_with(forest, wild_flight=dict(quiet_end=15, route_fixed="run")), 32088, 600)
    _same(b, c)
    with pytest.raises(AssertionError):
        _same(a, b)
    q = wb.flight_stats()["quiet_ends"]
    assert q > 0 and q == wb.wild_stats()["panic_quiet_ends"] == wc.flight_stats()["quiet_ends"]
    assert wc.flight_stats()["route"]["quiet_end"] == 15


# --------------------------------------------------------------------- #
# 오라클 다시 고르기·설정
# --------------------------------------------------------------------- #


def test_route_redecide_for_oracle(forest):
    """route_redecide: 시작한 도주의 길을 바꿔 고른다 — RUN 으로 다시 고르면 그대로(비트 동일), SHELTER 는 후보 방향·은신처를 쓴다. 복제는 원래 세계를 바꾸지 않는다."""
    w = World(_with(forest, wild_flight=dict(route_fixed="run")), seeds=[32089])
    rng = np.random.default_rng(3)
    i = None
    for _ in range(1500):
        w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        on = np.flatnonzero(w.route_onset & w.route_cand_ok[:, ROUTE_SHELTER] & ~np.isclose(w.route_cand_dir[:, ROUTE_SHELTER], w.wf_dir).all(1))
        if len(on):
            i = int(on[0])
            break
    assert i is not None
    acts = np.random.default_rng(11).integers(0, 3, (30, w.N, 1)).astype(np.float64)
    a, b, c = copy.deepcopy(w), copy.deepcopy(w), copy.deepcopy(w)
    assert b.route_redecide(i, ROUTE_RUN) == ROUTE_RUN
    assert c.route_redecide(i, ROUTE_SHELTER) == ROUTE_SHELTER
    assert c.flight_route[i] == ROUTE_SHELTER and c.route_k[i] == c.route_cand_k[i] >= 0 and c.route_force[i] == ROUTE_SHELTER
    assert np.array_equal(c.wf_dir[i], c.route_cand_dir[i, ROUTE_SHELTER]) and not np.array_equal(w.wf_dir[i], c.wf_dir[i])
    pa, pb, pc = [], [], []
    for t in range(30):
        for x, out in ((a, pa), (b, pb), (c, pc)):
            x.step(acts[t])
            out.append(x.pos.copy())
    assert all(np.array_equal(u, v) for u, v in zip(pa, pb))
    assert not all(np.array_equal(u, v) for u, v in zip(pa, pc))
    assert w.route_force[i] == ROUTE_NONE                   # 원래 세계는 그대로
    # 가능하지 않은 길은 RUN 으로
    w2 = copy.deepcopy(w)
    j = np.flatnonzero((w2.wf_mode == WF_PANIC) & ~w2.route_cand_ok[:, ROUTE_COVER])
    if len(j):
        assert w2.route_redecide(int(j[0]), ROUTE_COVER) == ROUTE_RUN
    with pytest.raises(ValueError):
        w2.route_redecide(int(np.flatnonzero(w2.wf_mode != WF_PANIC)[0]), ROUTE_OPEN)


def test_optional_keys_and_validation(forest):
    """선택 키 기본값은 끔(null·0), 잘못된 값은 멈춘다."""
    assert dict(F.OPTIONAL_KEYS["wild_flight"]) == {"hold_awake": False, "edge_r": 0.0, "flight_cost": 0.0, "route_fixed": None, "quiet_end": 0,
                                                    "route": False,      # 10-22 두뇌 길(tests/test_route2_v3.py)
                                                    "brain_flee_outside_reflex": True}   # 10-23 R7 반사 밖 FLEE 막음(tests/test_r7_mask5.py)
    assert F.with_optional("wild_flight", {})["route_fixed"] is None and F.with_optional("wild_flight", {})["quiet_end"] == 0
    for bad in (dict(route_fixed="forest"), dict(route_fixed=1), dict(quiet_end=-1), dict(quiet_end=1.5), dict(quiet_end=True)):
        with pytest.raises(ValueError, match="route_fixed|quiet_end"):
            World(_with(forest, wild_flight=bad), seeds=[32084])
    with pytest.raises(ValueError, match="route_redecide"):
        World(forest, seeds=[32084]).route_redecide(0, ROUTE_RUN)
    with pytest.raises(ValueError, match="route_stats"):
        World(forest, seeds=[32084]).route_stats()
    assert FLIGHT_CAUSES[-1] == "truncated"


def test_config_digests_unchanged():
    """옛 설정(wild_flight 를 켠 설정 전부)의 config digest 가 HEAD 와 같다 — 새 키는 OPTIONAL_KEYS 기본값이라 설정 파일·dict 가 그대로다."""
    rm = _module("_rm_for_route", ROOT / "results" / "v3" / "mirror" / "run_mirror.py")
    for name, want in HEAD_DIGEST.items():
        cfg = load_v2_config(CFG / name)
        assert rm.config_digest(cfg) == want, name
        wf = cfg.v2["features"]["wild_flight"]
        assert "route_fixed" not in wf and "quiet_end" not in wf


# --------------------------------------------------------------------- #
# 9-4 판단표 (results/v3/route/route_rules.py decide · oracle.py summarize) — 10-21 검토 뒤 고침
# --------------------------------------------------------------------- #


def _route_tools():
    import sys

    d = ROOT / "results" / "v3" / "route"
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))
    import oracle as orc

    return orc.rr, orc


def _cmp(**useful):
    """route_rules 비교 꼴 (decide 가 읽는 칸만): 팔 이름 → 지역 → useful (쓸모 있음, 까닭)."""
    return {"compare": {name: {"A": {"useful": (bool(u), "x" if u else "")}, "all": {"useful": (False, "")}} for name, u in useful.items()}}


def test_decide_stops_at_first_unknown_row():
    """판단표는 위에서부터 읽어 처음으로 '아니오'가 아닌 줄에서 멈춘다 — 모르는 줄(오라클·배울 수 있나·덩어리 숲 결과 없음)을 건너뛰고 아래 줄로
    판단하지 않는다. 오라클이 옛 잣대(도망 길이)면 모름. 모든 줄이 '아니오'면 줄 0."""
    rr, _ = _route_tools()
    rules = _cmp(cover_q0=True, cover_q15=False, shelter_q0=False, shelter_q15=False, open_q0=True)
    clump = _cmp(clump_cover_q0=False, clump_cover_q15=False)
    good = dict(measure="contact", decision=dict(no_gain=False, learnable=True, no_gain_why="이득 있음", learnable_why="배움"))
    d = rr.decide(rules, clump, None)                                                   # 오라클 없음: 줄 3 이 '예'여도 판단하지 않는다
    assert d["verdict"] is None and d["pending"] == 1 and any("오라클" in m for m in d["missing"]) and d["rows"][2]["hit"] is True
    d = rr.decide(rules, clump, dict(decision=good["decision"]))                          # 옛 잣대(measure 없음 — 도망 길이)
    assert d["verdict"] is None and d["pending"] == 1 and "쫓긴 시간으로 다시 셈" in d["missing"][0]
    d = rr.decide(rules, clump, dict(good, decision=dict(good["decision"], learnable=None, learnable_why="RUN 손해 없음")))
    assert d["verdict"] is None and d["pending"] == 2 and "배울 수 있나 판단 (RUN 손해 없음)" in d["missing"]
    assert rr.decide(rules, clump, good)["verdict"]["row"] == 3
    assert rr.decide(rules, clump, dict(good, decision=dict(good["decision"], no_gain=True)))["verdict"]["row"] == 1
    d = rr.decide(None, clump, good)                                                    # 규칙 측정 없음 → 줄 3 에서 멈춤
    assert d["verdict"] is None and d["pending"] == 3 and len(d["missing"]) == 1 and "rules" in d["missing"][0]
    none_rules = _cmp(cover_q0=False, cover_q15=False, shelter_q0=False, shelter_q15=False)
    d = rr.decide(none_rules, None, good)                                               # 덩어리 숲 없음 → 줄 5 에서 멈춤 (줄 6 의 SHELTER 를 보지 않는다)
    assert d["verdict"] is None and d["pending"] == 5 and "clump" in d["missing"][0]
    assert rr.decide(none_rules, clump, good)["verdict"]["row"] == 0                   # 모두 '아니오' → 쓸모 있는 길 없음
    assert rr.decide(_cmp(cover_q0=False, cover_q15=False, shelter_q0=True), clump, good)["verdict"]["row"] == 6


def _roll(len_, contact, cause="cover"):
    return dict(len=int(len_), contact=int(contact), cause=cause, closed=True, n=int(len_), got=0)


def _onset(orc, run, cover):
    """도주 시작 하나 (oracle._oracle_world 꼴): run·cover = (도망 길이 스텝, 쫓긴 스텝). SHELTER 는 불가능, OPEN·가짜는 RUN 과 같다."""
    arms = {"real0": [_roll(*run)] * 3, "real1": [_roll(*cover)] * 3, "real2": [_roll(*run)] * 3, "real3": [_roll(*run)] * 3}
    arms.update({f"fake{a}": [_roll(*run)] * 3 for a in (1, 2, 3)})
    return dict(t=1, deer=0, ok=[True, True, False, True], feats={f: 0.0 for f in orc.FEATS}, L0=0, arms=arms)


def test_oracle_decides_on_chase_time():
    """오라클의 9-4 첫 두 줄은 route_rules P1·관문 1차와 같은 잣대(쫓긴 시간)로 판단한다. 도망 길이만 줄이는 길(쫓긴 시간 그대로 — 예: 늑대가 놓친 뒤의
    달리기만 짧아짐)은 '이득 없음', 쫓긴 시간을 줄이는 길은 '이득 있음'. 도망 길이는 보조 표(gain_len)로만."""
    rr, orc = _route_tools()
    assert orc.MEASURE == rr.ORACLE_MEASURE == "contact"

    def raw(run, cover):
        return dict(max_steps=300, streams=3, fit_seeds=[34960, 34989], test_seeds=[34990, 34999],
                    worlds=[dict(seed=s, region=r, quiet_end=0, onsets=[_onset(orc, run, cover)]) for s in (34960, 34961, 34990) for r in ("A", "B")])

    s = orc.summarize(raw(run=(150, 40), cover=(90, 40)))                              # 길이만 8 초 짧아짐, 쫓긴 시간 같음
    assert s["measure"] == "contact" and s["decision"]["no_gain"] is True
    assert s["gain"]["q0:A"]["brain"]["corrected"] == pytest.approx(0.0) and s["gain_len"]["q0:A"]["brain"]["corrected"] == pytest.approx(-60 * orc.STEP_S)
    s = orc.summarize(raw(run=(150, 60), cover=(150, 20)))                             # 쫓긴 시간 40 스텝 짧아짐, 길이 같음
    assert s["decision"]["no_gain"] is False and s["gain"]["q0:all"]["brain"]["corrected"] == pytest.approx(-40 * orc.STEP_S)
    assert s["gain_len"]["q0:all"]["brain"]["corrected"] == pytest.approx(0.0) and s["learn"]["q0"]["label_fit"]["cover"] == 4
    d = rr.decide(_cmp(cover_q0=True), _cmp(clump_cover_q0=False), dict(s))
    assert d["rows"][0]["hit"] is False and d["measure"] == "contact"
    empty = orc.summarize(dict(raw(run=(150, 60), cover=(150, 20)), worlds=[]))        # 잴 값이 없으면 판단하지 않는다
    assert empty["decision"]["no_gain"] is None
