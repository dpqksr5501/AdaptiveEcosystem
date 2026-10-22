"""야생 (w3) 두뇌 길 '두 길' (10-22 사용자 결정 '두 길 두뇌로 진행' — 설계 Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 16절, 선택 키 wild_flight.route,
관측 24·마스크 판 4 — env_v2/world.py 모듈 docstring '야생 1단계' (w3) 두뇌 길, env_v2/rep_policy.py '마스크 판 4').

- 끔 = HEAD: 거울·학습 세계 궤적 해시(test_route_v3 와 같은 값), 판 2·3 학습 경로(VecEnv 관측·마스크·읽음·보상) 해시, 측정 전용 route_fixed 궤적 해시가 HEAD 와 같다.
- 켬 + 늘 RUN(결정 줄에서 칸 1 — 무작위 행동 0..2 도 RUN 으로 읽는다) = 끔: 궤적·관측 앞 21 칸·보상·난수·도망 기록이 비트 단위로 같다.
- route0(results/v3/route/route_extend.py): 길 켬 세계의 배포(argmax) 궤적 = 길 끔 세계의 obs21zero 궤적, 길 결정 표본 확률 RUN 0.881·SHELTER 0.119.
- 마스크 줄(도주 결정 {1, 4 (관측 22 > 0)}·도주 비결정 지금 길 한 칸·웅크림 HIDE 한 칸·그 밖 판 2), 덮기 스텝은 결정이 아니다(판 4 만).
- 관측 21~23 값(in_panic·shelter_reach·shelter_edge — 도주 밖·reset·죽은 사슴의 terminal_obs 는 0), 계약 해시(옛 셋 고정·새 판 4 해시 안정),
  config digest 그대로, 결정 때(시작·늑대가 은신처 경주에서 이김 = 무효·RUN 길에서 2 초 잠금 뒤 SHELTER 가능 바뀜만 — SHELTER 는 무효까지 잇는다).
- 결정 셈(World.repertoire_stats decide_frac·_rep_decide)은 rep_peek 의 reads 와 같다. 학습은 칸 3(COVER 자리) 출력 줄을 움직이지 않는다.
시드는 탐색 32080~32099·학습 32000~32049 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import hashlib
import importlib.util
import json

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import features as F
from env_v2.config import load_v2_config
from env_v2.rep_policy import (MASK_VERSION_ROUTE, action_mask, allowed_mask_of, check_route_allowed, feasible_mask, mask_version_of,
                               rep_params, sample_masked)
from env_v2.repertoire import FLEE, FREEZE, HIDE, N_BEHAVIORS, SLEEP
from env_v2.world import (ROUTE_FEAS_SHELTER, ROUTE_NONE, ROUTE_OBS_NAMES, ROUTE_RUN, ROUTE_SHELTER, WF_NONE, WF_PANIC, WF_SHELTER, World,
                          obs_names)

CFG = ROOT / "configs"
OBS = CFG / "v3_wild3_obs_mirror.yaml"          # 관측 21 거울 (길 끔)
ROUTE = CFG / "v3_wild3_route_mirror.yaml"      # 관측 24 거울 (길 켬)
TRAIN = CFG / "v3_r5_train.yaml"
R6 = CFG / "v3_r6_train.yaml"                   # R6 학습 세계 (N + R5 조리법(무작위 숲 섞기 포함), 길 켬)
ROUTE0 = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs24route0.zip"
OBS21ZERO = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip"
BRAIN = ROOT / "results" / "v3" / "route" / "brains" / "v3_r1_g995_s3_obs24route0.json"
VERIFY = ROOT / "results" / "v3" / "route" / "brains" / "v3_r1_g995_s3_obs24route0.verify.json"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")

# HEAD(31728a7, 두뇌 길 코드를 넣기 전) 에서 같은 셈으로 잰 값. 거울·학습 세계 궤적은 test_route_v3.HEAD_HASH 와 같은 값이다
HEAD_HASH = {
    "obs_Forest_sat0": "a1d6cde8248821e73fb379f7196f461f0ec8ba9f0e80a4a0e0b18968a308c343",
    "train_respawn": "3f6c580f9cc3147dcb93ef5fe7bf050d44daf4b846b9ca860ddcdbf606f77692",
    # 판 2(R5 학습 세계)·판 3(경보 세계 v3_r2) 이산 학습 경로: VecEnv 관측(마스크 칸 포함)·보상·죽음·읽음·끊긴 관측·누적 수
    "vec_r5_train": "562f9e4af6a49f7213cb52f3841a86839a9017f5380a3e0f1902ba07d89db73a",
    "vec_r2_alarm": "c3f79ce447be9062add24635802eb8ef528ed889fed689242c54298e32921745",
    # 측정 전용 route_fixed (거울 숲 N, 시드 32086 × 600) — 도망 기록(길 칸 포함) 전부
    "fixed_shelter": "555fa49d1a857a446e7bd5007eb4848f91fe9591d0bf0274ffaefefe3dd7c2ee",
    "fixed_cover": "5b2f8ad067f363062558992d0f99eb441860abc9f94b4f79823e5fda78637ed9",
    "fixed_run": "d6580dfd4ac9ea4febeee66c409c4cee5ff3d0d1a0c18d5677f472bebc0dd4e1",
}
# 계약 해시: 옛 셋(관측 18·판 2, 관측 19·판 3, 관측 21·판 2)은 바뀌면 안 되고, 새 판 4(관측 24)는 이 값으로 박는다(C++ kContractHashObs24Mask4 — 다음 단계)
CONTRACT_OLD = {18: 0x7EEA0107339BE4CE, 19: 0xF8C26C7D02542FAE, 21: 0xBC4FC2D45C47C5FD}
CONTRACT_OBS24 = 0xE302DEE198197444
# HEAD 의 config digest (results/v3/mirror/run_mirror.config_digest — wild_flight 를 켠 옛 설정 전부, test_route_v3 와 같은 값)
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
def discs():
    return _module("_r4_for_route2", ROOT / "results" / "v3" / "r4" / "r4_eval.py").region_discs()


@pytest.fixture(scope="module")
def forest(discs):
    """관측 21 거울 숲 지역 N 세계(늑대 포만 끔), 사슴 32 — 길 끔."""
    return _with(load_v2_config(OBS).replace(N=32), wild_weather=dict(region="Forest"), obstacles=dict(fixed=discs["Forest"]),
                 wild_satiation=dict(enabled=False))


@pytest.fixture(scope="module")
def forest_on(discs):
    """같은 세계, 길 켬(관측 24 거울 설정)."""
    return _with(load_v2_config(ROUTE).replace(N=32), wild_weather=dict(region="Forest"), obstacles=dict(fixed=discs["Forest"]),
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
    """test_route_v3._traj_hash 와 같은 셈(무작위 행동 0..2, 도망 기록의 길 칸 뺌)."""
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
    ws = w.wild_stats()
    ws.pop("panic_quiet_ends", None)
    st = json.dumps(dict(flight=f, wild=ws, hunt=w.hunt_stats(), rng=str(w.rng.bit_generator.state)), sort_keys=True, default=str)
    h.update(st.encode())
    return h.hexdigest()


def _full_hash(cfg, seed, steps, acts_seed=7):
    """route_fixed 세계 해시: 궤적 + 도망 기록 전부(길 칸 포함)."""
    w = World(cfg, seeds=[seed])
    w.track_flight = True
    rng = np.random.default_rng(acts_seed)
    h = hashlib.sha256()
    for _ in range(steps):
        o, r, d, to = w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        h.update(_H(o, r, d, to, w.pos, w.pred_pos, w.energy, w.wf_mode, w.wf_dir).digest())
    st = json.dumps(dict(flight=w.flight_stats(), wild=w.wild_stats(), hunt=w.hunt_stats(), rng=str(w.rng.bit_generator.state)),
                    sort_keys=True, default=str)
    h.update(st.encode())
    return h.hexdigest()


def _vec_hash(cfg, K, steps, seed):
    """이산 학습 경로(VecEnv): 마스크 위 균등 표본으로 돌린 관측(마스크 칸 포함)·보상·죽음·읽음·끊긴 관측·누적 수의 해시."""
    from env_v2.vec_env import MultiWorldVecEnv

    def upd(h, *arrs):                  # HEAD 값을 잰 셈 그대로(배열마다 dtype·모양·바이트를 한 해시에 이어 넣는다)
        for x in arrs:
            x = np.ascontiguousarray(x)
            h.update(str(x.dtype).encode())
            h.update(str(x.shape).encode())
            h.update(x.tobytes())

    v = MultiWorldVecEnv(cfg, num_worlds=K, meta_seed=seed)
    o = v.reset()
    rng = np.random.default_rng(seed)
    h = hashlib.sha256()
    upd(h, o)
    for _ in range(steps):
        m = v.current_masks()
        a = sample_masked(np.ones(m.shape), m, rng.random(len(m)))
        v.step_async(a)
        o, r, d, info = v.step_wait()
        upd(h, o, r, d, v.last_reads)
        for i, inf in enumerate(info):
            if "terminal_observation" in inf:
                upd(h, np.array([i]), inf["terminal_observation"], np.array([inf.get("TimeLimit.truncated", False)]))
    c = v.rep_counts
    h.update(json.dumps({k: (x.tolist() if hasattr(x, "tolist") else x) for k, x in c.items()}, sort_keys=True).encode())
    return h.hexdigest(), v


def _run(cfg, seed, steps, policy=None, acts_seed=7):
    """무작위 행동 0..2(policy 가 있으면 policy(w, a) 로 바꾼 행동)로 돌린 스텝별 기록과 세계."""
    w = World(cfg, seeds=[seed])
    w.track_flight = True
    rng = np.random.default_rng(acts_seed)
    out = []
    for _ in range(steps):
        a = rng.integers(0, 3, (w.N, 1)).astype(np.float64)
        if policy is not None:
            a = policy(w, a)
        o, r, d, to = w.step(a)
        out.append(dict(o=o.copy(), r=r.copy(), d=d.copy(), to=to.copy(), pos=w.pos.copy(), pred=w.pred_pos.copy(), e=w.energy.copy(),
                        mode=w.wf_mode.copy(), dir=w.wf_dir.copy(), beh=w.behavior.copy()))
    return out, w


def _same_as_off(on, off, n=21):
    assert len(on) == len(off)
    for t, (x, y) in enumerate(zip(on, off)):
        assert x["o"].shape[1] == n + len(ROUTE_OBS_NAMES) and y["o"].shape[1] == n
        assert np.array_equal(x["o"][:, :n], y["o"]), t
        assert np.array_equal(x["to"][:, :n], y["to"]), t
        for k in ("r", "d", "pos", "pred", "e", "mode", "dir", "beh"):
            assert np.array_equal(x[k], y[k]), (t, k)


def _route_policy(choose_shelter: bool):
    """길 결정 줄에서 칸 1(RUN) 또는 칸 4(SHELTER — 마스크가 열었을 때만)를 내는 두뇌. 다른 사슴은 무작위 행동 그대로."""
    def pol(w, a):
        pk = w.rep_peek()
        m = action_mask(pk, w.observe(), rep_params(w.cfg), obs_names=w.obs_names)
        a = a.copy()
        rd = np.asarray(pk["route_decide"], dtype=bool)
        a[rd, 0] = float(FLEE)
        if choose_shelter:
            a[rd & m[:, SLEEP], 0] = float(SLEEP)
        return a
    return pol


# --------------------------------------------------------------------- #
# 끔 = HEAD (비트 동일)
# --------------------------------------------------------------------- #


def test_off_matches_head(forest):
    """키 없음·route false = HEAD: 거울 숲 N·학습 세계 궤적, 판 2·3 이산 학습 경로, 측정 전용 route_fixed 길 셋."""
    assert _traj_hash(forest, 32084, 900) == HEAD_HASH["obs_Forest_sat0"]
    assert _traj_hash(_with(forest, wild_flight=dict(route=False)), 32084, 900) == HEAD_HASH["obs_Forest_sat0"]
    assert _traj_hash(load_v2_config(TRAIN).replace(N=24), 32001, 900, 5) == HEAD_HASH["train_respawn"]
    h, v = _vec_hash(load_v2_config(TRAIN).replace(N=12), 2, 300, 3)
    assert h == HEAD_HASH["vec_r5_train"], "판 2 학습 경로"
    assert all("override" not in w.rep_peek() for w in v.worlds), "판 2 세계의 미리 보기에는 길 칸이 없다"
    assert _vec_hash(load_v2_config(CFG / "v3_r2.yaml").replace(N=12), 2, 300, 4)[0] == HEAD_HASH["vec_r2_alarm"], "판 3 학습 경로"
    for rf in ("shelter", "cover", "run"):
        assert _full_hash(_with(forest, wild_flight=dict(route_fixed=rf)), 32086, 600) == HEAD_HASH[f"fixed_{rf}"], rf
    w = World(forest, seeds=[32084])
    assert not w._route_brain and not hasattr(w, "route_obs") and w.obs_dim == 21 and w._obs_rt is None


def test_route_on_always_run_equals_off(forest, forest_on):
    """켬 + 늘 RUN = 끔: 무작위 행동 0..2(결정 줄의 0·2 는 RUN 으로 읽는다)와 결정 줄에서 칸 1 을 내는 두뇌 모두 — 관측 앞 21 칸·끊긴 관측·보상·
    위치·덮기·실행 행동·난수·도망 기록이 같다. 학습 세계(부활, 다시 난 사슴)도 같다. 길 기록은 결정이 있고 SHELTER 를 고르지 않았다."""
    off, w_off = _run(forest, 32085, 900)
    for pol in (None, _route_policy(False)):
        on, w_on = _run(forest_on, 32085, 900, pol)
        _same_as_off(on, off)
        assert w_on.rng.bit_generator.state == w_off.rng.bit_generator.state
        fa, fb = w_off.flight_stats(), w_on.flight_stats()
        rt = fb.pop("route")
        assert fa == fb and w_off.wild_stats() == w_on.wild_stats() and w_off.hunt_stats() == w_on.hunt_stats()
        assert rt["brain"] and rt["fixed"] is None and rt["decisions"] > 0 and rt["choice"] > 0
        assert rt["picked"]["shelter"] == 0 and rt["picked"]["run"] == rt["decisions"] and rt["switches"] == 0
        assert rt["steps"]["run"] == fb["reflex_steps"] > 0 and rt["steps"]["cover"] == rt["steps"]["shelter"] == rt["steps"]["open"] == 0
        assert rt["onset_cover"] == 0 and rt["invalid"]["cover"] == 0 and rt["bad_shelter"] == 0
    r6 = load_v2_config(R6).replace(N=24)
    on, _ = _run(r6, 32001, 900, _route_policy(False), acts_seed=5)
    off, _ = _run(_with(r6, wild_flight=dict(route=False)), 32001, 900, None, acts_seed=5)
    _same_as_off(on, off)
    assert sum(int(x["d"].sum()) for x in on) > 0, "죽음·다시 남이 있는 세계"


def test_shelter_choice_changes_world(forest_on):
    """두뇌가 SHELTER 를 고르면 길이 바뀐다: 고른 사슴은 다음 스텝 덮기 방향 = 결정 때 k* 쪽 후보 방향, 길 상태 SHELTER·은신처 k* (고른 뒤 유지 중에는
    그 은신처). 실행 행동은 늘 FLEE, 막힌 칸 3 은 고르지 않는다. 궤적은 늘 RUN 과 다르다."""
    base, _ = _run(forest_on, 32085, 600, _route_policy(False))
    w = World(forest_on, seeds=[32085])
    w.track_flight = True
    rng = np.random.default_rng(7)
    pol = _route_policy(True)
    seen = 0
    out = []
    for _ in range(600):
        a = pol(w, rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        rd = w.route_decide & (w.wf_mode == WF_PANIC)
        sh = rd & (a[:, 0] == SLEEP)
        cand_k, cand_dir = w.route_cand_k.copy(), w.route_cand_dir[:, ROUTE_SHELTER].copy()
        pan0 = w.wf_mode == WF_PANIC
        w._route_apply(a[:, 0])                       # `step` 첫머리와 같은 호출 — 같은 스텝에 두 번 불러도 같은 값이다(멱등)
        if sh.any():
            seen += int(sh.sum())
            assert (w.flight_route[sh] == ROUTE_SHELTER).all() and np.array_equal(w.route_k[sh], cand_k[sh])
            assert np.array_equal(w.wf_dir[sh], cand_dir[sh])
        assert (w.flight_route[rd & ~sh] == ROUTE_RUN).all()
        o, r, d, to = w.step(a)
        assert (w.behavior[pan0 & ~d] == FLEE).all(), "도주 중 실행 행동은 FLEE"
        out.append(w.pos.copy())
    rt = w.flight_stats()["route"]
    assert seen > 0 and rt["picked"]["shelter"] > 0 and rt["steps"]["shelter"] > 0 and rt["bad_shelter"] == 0
    assert rt["picked"]["shelter"] + rt["picked"]["run"] == rt["decisions"]
    assert any(not np.array_equal(p, b["pos"]) for p, b in zip(out, base))


# --------------------------------------------------------------------- #
# 마스크 줄·관측 세 칸
# --------------------------------------------------------------------- #


def test_mask_rows(forest_on):
    """판 4 마스크 줄: 도주 결정 = {1, 4 (관측 shelter_reach > 0)}, 도주 비결정 = 지금 길 한 칸(1 또는 4), 웅크림 = HIDE 한 칸, 그 밖 = 판 2 규칙
    (허용 ∧ 가능 ∧ reads — 덮기 스텝은 reads 가 아니다). 칸 3 은 늘 막힘. 결정 줄의 SHELTER 칸 ⇔ 세계의 SHELTER 가능."""
    w = World(forest_on, seeds=[32087])
    rp = rep_params(forest_on)
    rng = np.random.default_rng(11)
    pol = _route_policy(True)
    names = list(w.obs_names)
    n = dict(dec2=0, dec1=0, keep_run=0, keep_sh=0, crouch=0, other=0)
    for _ in range(900):
        obs = w.observe()
        pk = w.rep_peek()
        m = action_mask(pk, obs, rp, obs_names=w.obs_names)
        live = np.ones(w.N, dtype=bool) if w.alive is None else w.alive
        pan = (w.wf_mode == WF_PANIC) & live
        cr = (w.wf_mode == WF_SHELTER) & live
        assert np.array_equal(pk["override"], np.where(pan, WF_PANIC, np.where(cr, WF_SHELTER, WF_NONE)))
        rd = pk["route_decide"]
        assert np.array_equal(rd, w.route_decide & pan) and not (rd & ~pan).any()
        assert not m[:, FREEZE].any(), "칸 3 은 늘 막힘"
        one = lambda j: np.eye(N_BEHAVIORS, dtype=bool)[j]   # noqa: E731
        sok = obs[:, names.index("shelter_reach")] > 0.0
        for i in np.flatnonzero(pan):
            if rd[i]:
                assert np.array_equal(m[i], np.array([0, 1, 0, 0, sok[i]], dtype=bool)), i
                assert sok[i] == w.route_cand_ok[i, ROUTE_SHELTER]
                n["dec2" if sok[i] else "dec1"] += 1
            else:
                sh = pk["route_now"][i] == ROUTE_SHELTER
                assert np.array_equal(m[i], one(SLEEP if sh else FLEE)), i
                n["keep_sh" if sh else "keep_run"] += 1
        for i in np.flatnonzero(cr):
            assert np.array_equal(m[i], one(HIDE))
            n["crouch"] += 1
        # 덮기 스텝은 결정이 아니다: reads = (arbitrate ∧ ¬덮기) ∨ 길 결정
        assert np.array_equal(pk["reads"] & (pan | cr), rd) and not (pk["wake_decide"] & (pan | cr)).any()
        assert (pk["route_now"][pan] >= 0).all() and (pk["route_now"][~pan] == ROUTE_NONE).all()
        # 그 밖 줄 = 판 2 규칙
        rest = ~(pan | cr)
        m2 = rp["allowed_mask"][None, :] & feasible_mask(obs, w.obs_names)
        m2[:, SLEEP] &= ~pk["wake_decide"]
        o2 = np.eye(N_BEHAVIORS, dtype=bool)[pk["behavior"]]
        m2 = np.where(pk["reads"][:, None], m2, o2)
        assert np.array_equal(m[rest], m2[rest])
        n["other"] += int(rest.sum())
        a = pol(w, sample_masked(np.ones(m.shape), m, rng.random(w.N)).astype(np.float64)[:, None])
        assert m[np.arange(w.N), a[:, 0].astype(int)].all()
        w.step(a)
    assert all(v > 0 for v in n.values()), n


def test_mask_version_and_allowed():
    """판 4 = 관측 in_panic. 경보 칸과 함께면 멈춤. 판 4 는 얼기·잠 허용이면 멈춘다(로더 검사 — 판 2·3 은 그대로)."""
    n21 = obs_names(load_v2_config(OBS))
    n24 = obs_names(load_v2_config(ROUTE))
    assert n24 == tuple(n21) + ROUTE_OBS_NAMES and len(n24) == 24
    assert mask_version_of(n24) == MASK_VERSION_ROUTE == 4 and mask_version_of(n21) == 2
    assert mask_version_of(obs_names(load_v2_config(CFG / "v3_r2_on.yaml"))) == 3
    with pytest.raises(ValueError, match="섞지"):
        mask_version_of(tuple(n24) + ("alarm_heard",))
    check_route_allowed(("graze", "flee", "hide", "freeze"), 2)
    check_route_allowed(("graze", "flee", "hide"), 4)
    for bad in (("graze", "flee", "hide", "freeze"), ("graze", "flee", "sleep")):
        with pytest.raises(ValueError, match="얼기·잠"):
            check_route_allowed(bad, 4)
    w = World(load_v2_config(ROUTE).replace(N=8), seeds=[32088])
    with pytest.raises(ValueError, match="얼기·잠"):
        action_mask(w, w.observe(), {"allowed_mask": allowed_mask_of(("graze", "flee", "hide", "freeze"))})
    raw = load_v2_config(ROUTE)
    tr = dict(raw.v2["train"], repertoire=dict(raw.v2["train"]["repertoire"], allowed=["graze", "flee", "hide", "freeze"]))
    with pytest.raises(ValueError, match="얼기·잠"):
        rep_params(raw.replace(v2=dict(raw.v2, train=tr)))
    # 검사는 실제 허용(모델 목록 ∧ 세계 목록 — 계약 freeze_sleep_must_be_blocked = "effective_allowed")에 건다: 세계 목록이 잠까지 허용해도
    # (train 블록 없음 = 다섯 모두 — 언리얼 통합 세계 WorldAllowed 잠 1 과 같은 꼴) 모델 목록이 얼기·잠을 막으면 받는다
    import export_weights_v3 as ex
    from env_v2.rep_policy import effective_allowed

    open_world = raw.replace(v2={k: v for k, v in raw.v2.items() if k != "train"})
    assert rep_params(open_world) is None
    eff = effective_allowed(("graze", "flee", "hide"), open_world)
    assert eff == ("graze", "flee", "hide")
    check_route_allowed(eff, 4)
    with pytest.raises(ValueError, match="얼기·잠"):
        check_route_allowed(effective_allowed(("graze", "flee", "hide", "sleep"), open_world), 4)
    assert ex.contract_dict(n24, 4)["flight_route"]["freeze_sleep_must_be_blocked"] == "effective_allowed"


def test_route_key_validation(forest_on):
    """선택 키 route: 기본 false(OPTIONAL_KEYS), bool 이 아니면·route_fixed 와 함께·관측 21 이 아닌 세계·경보 세계면 멈춘다."""
    assert F.OPTIONAL_KEYS["wild_flight"]["route"] is False and F.with_optional("wild_flight", {})["route"] is False
    for bad, why in ((dict(route=1), "true/false"), (dict(route=True, route_fixed="run"), "route_fixed")):
        with pytest.raises(ValueError, match=why):
            World(_with(forest_on, wild_flight=bad), seeds=[32084])
    with pytest.raises(ValueError, match="obstacle_obs"):
        World(_with(forest_on, obstacle_obs=dict(enabled=False)), seeds=[32084])


def test_obs_values(forest_on):
    """관측 21~23: in_panic = 다음 스텝 덮기가 도주, shelter_reach = SHELTER 가 가능하면 clip(μ*/10, 0, 1)(≥ 0.2), shelter_edge = 가능하면
    clip(e*/20, 0, 1)(e* = k* 의 가장자리 거리 — 따로 다시 잰 값과 같다), 그 밖 0. reset 직후 0. 산 사슴의 terminal_obs = 관측, 죽은 사슴은 0.
    관측 앞 21 칸은 길 끈 세계와 같다(위 시험)."""
    w = World(forest_on, seeds=[32089])
    k = w.obs_names.index("in_panic")
    assert k == 21 and not w.observe()[:, k:].any(), "reset 직후 0"
    rng = np.random.default_rng(13)
    pol = _route_policy(True)
    n_pan = n_sok = n_dead = 0
    for _ in range(900):
        o, r, d, to = w.step(pol(w, rng.integers(0, 3, (w.N, 1)).astype(np.float64)))
        live = np.ones(w.N, dtype=bool) if w.alive is None else w.alive
        pan = (w.wf_mode == WF_PANIC) & live
        v = o[:, k:k + 3]
        assert np.array_equal(v[:, 0], pan.astype(np.float32))
        assert not v[~pan].any()
        sok = pan & w.route_cand_ok[:, ROUTE_SHELTER]
        assert np.array_equal(v[:, 1] > 0.0, sok) and (v[sok, 1] >= np.float32(0.2)).all() and (v[sok, 1] <= 1.0).all()
        assert not v[pan & ~sok, 1:].any()
        mu = w.route_shelter_mu
        assert np.array_equal(v[sok, 1], np.minimum(np.maximum(mu[sok] / 10.0, 0.0), 1.0).astype(np.float32))
        kk = w.route_cand_k[sok]
        e = np.sqrt(((w.cov_c[kk] - w.pos[sok]) ** 2).sum(1)) - w.cov_r[kk]
        assert np.allclose(w.route_shelter_e[sok], e, rtol=0, atol=1e-12) and (e > 0).all() and (e <= 20.0).all()
        assert np.array_equal(v[sok, 2], np.minimum(np.maximum(w.route_shelter_e[sok] / 20.0, 0.0), 1.0).astype(np.float32))
        assert np.array_equal(to[~d], o[~d]) and not to[d, k:].any()
        n_pan += int(pan.sum())
        n_sok += int(sok.sum())
        n_dead += int(d.sum())
    assert n_pan > 0 and 0 < n_sok < n_pan and n_dead > 0


def test_obs_respawn_world():
    """학습 세계(부활): 죽은 사슴의 terminal_obs 세 칸 0, 다시 난 사슴의 관측은 `_wf_update` 가 정한 값(route_obs), 도주 밖 0."""
    w = World(load_v2_config(R6).replace(N=24), seeds=[32002])
    k = w.obs_names.index("in_panic")
    rng = np.random.default_rng(17)
    pol = _route_policy(True)
    dead = 0
    for _ in range(900):
        o, r, d, to = w.step(pol(w, rng.integers(0, 3, (w.N, 1)).astype(np.float64)))
        assert np.array_equal(o[:, k:], w.route_obs) and np.array_equal(w.observe(), o)
        assert not to[d, k:].any() and np.array_equal(to[~d], o[~d])
        assert np.array_equal(o[:, k], (w.wf_mode == WF_PANIC).astype(np.float32))
        dead += int(d.sum())
    assert dead > 0


# --------------------------------------------------------------------- #
# 결정 때 (설계 16-3)
# --------------------------------------------------------------------- #


class _Scene:
    """`_route_step` 한 번(스텝 끝 H)을 손으로 놓은 장면에서 부른다: 사슴 0 은 은신처 0 동쪽 가장자리 5 단위, 늑대 0 은 위치 q0, 다른 늑대는 멀리
    (안전 거리 밖). 다른 사슴은 도주가 아니다."""

    def __init__(self, cfg):
        self.w = w = World(cfg, seeds=[32093])
        c, r = w.cov_c[0], w.cov_r[0]
        self.p = np.array([c[0] + r + 5.0, c[1]])
        self.door = np.array([c[0] + r, c[1]])

    def step(self, q0, prev_mode, cur, k=-1, age=0, feas=0):
        w = self.w
        N, M = w.N, w.M
        w.pos = w.pos.copy()
        w.pos[0] = self.p
        far = np.array([[w.size - 1.0, w.size - 1.0], [1.0, w.size - 1.0], [w.size - 1.0, w.size - 2.0], [2.0, w.size - 1.0]])
        q = far[:M].copy()
        q[0] = q0
        w.pred_pos = q
        w.flight_route = w.flight_route.copy()
        w.flight_route[0] = cur
        w.route_k[0] = k
        w.route_age[0] = age
        w.route_feas[0] = feas
        prev = np.full(N, WF_NONE, dtype=np.int8)
        prev[0] = prev_mode
        nxt = np.full(N, WF_NONE, dtype=np.int8)
        nxt[0] = WF_PANIC
        ex = q[:, 0][None, :] - w.pos[:, 0:1]
        ey = q[:, 1][None, :] - w.pos[:, 1:2]
        pd = np.sqrt(ex * ex + ey * ey)
        near_h = pd <= w._wf["safe_r"]
        a0 = np.zeros((N, 2))
        a0[0] = (self.p - q0) / np.linalg.norm(self.p - q0)
        dirs = a0.copy()
        out = w._route_step(prev, nxt, dirs, a0, near_h, pd, np.ones(N, dtype=bool), np.full(N, ROUTE_NONE, dtype=np.int64))
        w.wf_mode, w.wf_dir = nxt, out
        return dict(decide=bool(w.route_decide[0]), route=int(w.flight_route[0]), age=int(w.route_age[0]), feas=int(w.route_feas[0]),
                    sok=bool(w.route_cand_ok[0, ROUTE_SHELTER]), k=int(w.route_cand_k[0]), obs=w.route_obs[0].copy(), dir=out[0].copy())


def test_decision_timing(forest_on):
    """결정 = 시작 ∨ 무효(지금 길 SHELTER 이고 늑대가 은신처 경주에서 이김 μ_k < 0) ∨ (age ≥ 15 ∧ SHELTER 가능 비트가 결정 때와 다름).
    RUN 은 무효가 없다. 잠금(15 스텝) 안에서는 가능 비트가 바뀌어도 다시 고르지 않고, 잠금 뒤에도 가능 비트가 같으면 다시 고르지 않는다."""
    s = _Scene(forest_on)
    q_far = s.p + np.array([5.0, 0.0])            # 동쪽 늑대 — 문까지 10, e = 5 → μ = 5 ≥ 2: SHELTER 가능
    q_door = s.door + np.array([1.0, 3.0])        # 문 옆 늑대 — μ = √10 − 5 < 0 이고 은신처가 늑대 쪽: SHELTER 불가
    # 시작: 결정, 길은 RUN(두뇌가 다음 스텝에 고른다), 결정 때 가능 비트 기록, 관측 세 칸
    r = s.step(q_far, WF_NONE, ROUTE_NONE)
    assert r["decide"] and r["route"] == ROUTE_RUN and r["age"] == 0 and r["sok"] and r["feas"] == ROUTE_FEAS_SHELTER and r["k"] == 0
    assert r["obs"][0] == 1.0 and r["obs"][1] == np.float32(0.5) and r["obs"][2] == np.float32(0.25)
    # 두뇌가 SHELTER 를 고름 → 길 SHELTER, 은신처 0, 방향 = 은신처 쪽(서쪽)
    s.w._route_apply(np.where(np.arange(s.w.N) == 0, float(SLEEP), 1.0))
    assert s.w.flight_route[0] == ROUTE_SHELTER and s.w.route_k[0] == 0 and np.allclose(s.w.wf_dir[0], [-1.0, 0.0])
    # 결정 아님(같은 장면): 길·은신처 유지, age + 1
    r = s.step(q_far, WF_PANIC, ROUTE_SHELTER, k=0, age=0, feas=ROUTE_FEAS_SHELTER)
    assert not r["decide"] and r["route"] == ROUTE_SHELTER and r["age"] == 1 and np.allclose(r["dir"], [-1.0, 0.0])
    # 무효: 늑대가 문 옆(경주에서 이김) — 잠금 안(age 2)이어도 다시 고른다. 이제 SHELTER 불가라 관측 22·23 은 0, 마스크는 RUN 한 칸
    r = s.step(q_door, WF_PANIC, ROUTE_SHELTER, k=0, age=1, feas=ROUTE_FEAS_SHELTER)
    assert r["decide"] and r["route"] == ROUTE_RUN and r["age"] == 0 and not r["sok"] and r["feas"] == 0
    assert r["obs"][0] == 1.0 and not r["obs"][1:].any()
    # RUN 은 무효가 없다: 잠금 안(age 13 → 14)에서 가능 비트가 바뀌어도(0 → SHELTER) 다시 고르지 않는다
    r = s.step(q_far, WF_PANIC, ROUTE_RUN, age=13, feas=0)
    assert not r["decide"] and r["age"] == 14 and r["sok"] and r["feas"] == 0
    # 잠금 뒤(age 14 → 15) 가능 비트가 바뀌었으면 다시 고른다
    r = s.step(q_far, WF_PANIC, ROUTE_RUN, age=14, feas=0)
    assert r["decide"] and r["age"] == 0 and r["feas"] == ROUTE_FEAS_SHELTER
    # 잠금 뒤라도 가능 비트가 같으면 다시 고르지 않는다(SHELTER 가능 그대로, SHELTER 불가 그대로)
    r = s.step(q_far, WF_PANIC, ROUTE_RUN, age=40, feas=ROUTE_FEAS_SHELTER)
    assert not r["decide"] and r["age"] == 41
    r = s.step(q_door, WF_PANIC, ROUTE_RUN, age=40, feas=0)
    assert not r["decide"] and r["age"] == 41
    # SHELTER 를 고른 뒤 잠금 안에서 μ_k ≥ 0 인 채 가능 비트만 바뀌면 유지 — 늑대가 문에서 6(μ = 1: 유지 문턱 0 위, 들어갈 때 문턱 2 밑)
    q6 = np.array([s.door[0] + 2.0, s.door[1] + np.sqrt(6.0 ** 2 - 2.0 ** 2)])
    r = s.step(q6, WF_PANIC, ROUTE_SHELTER, k=0, age=3, feas=ROUTE_FEAS_SHELTER)
    assert not r["decide"] and r["route"] == ROUTE_SHELTER and r["k"] == -1 and not r["sok"] and r["age"] == 4
    assert np.isclose(s.w.route_k[0], 0)
    # 잠금 뒤에도 같다: SHELTER 는 무효(μ_k < 0)까지 잇는다 — 가능 바뀜으로 다시 고르는 것은 RUN 길만(그때 열린 칸이 RUN 하나라 SHELTER 를 버리게 된다)
    r = s.step(q6, WF_PANIC, ROUTE_SHELTER, k=0, age=40, feas=ROUTE_FEAS_SHELTER)
    assert not r["decide"] and r["route"] == ROUTE_SHELTER and not r["sok"] and r["age"] == 41 and r["feas"] == ROUTE_FEAS_SHELTER
    assert s.w.route_k[0] == 0 and np.allclose(r["dir"], [-1.0, 0.0]) and r["obs"][0] == 1.0 and not r["obs"][1:].any()
    # RUN 길은 잠금 뒤 가능 비트가 1 → 0 으로 바뀌면 다시 고른다(열린 칸 RUN 하나)
    r = s.step(q6, WF_PANIC, ROUTE_RUN, age=40, feas=ROUTE_FEAS_SHELTER)
    assert r["decide"] and r["route"] == ROUTE_RUN and r["age"] == 0 and r["feas"] == 0
    # 칸 4 인데 SHELTER 가 가능하지 않은 결정은 RUN 으로 읽고 센다(마스크 밖)
    r = s.step(q_door, WF_NONE, ROUTE_NONE)
    bad0 = s.w._rt_bad_shelter
    s.w._route_apply(np.where(np.arange(s.w.N) == 0, float(SLEEP), 1.0))
    assert s.w.flight_route[0] == ROUTE_RUN and s.w._rt_bad_shelter == bad0 + 1


def test_decision_timing_rollout(forest_on):
    """실제 판(부활 없음 거울 숲 N, 두뇌가 가능하면 늘 SHELTER)에서 결정 규칙: 시작이면 결정, 결정이면 age 0, 아니면 age + 1·길·가능 비트 유지.
    시작이 아닌 결정은 (지금 길 SHELTER 이고 지금 μ_k < 0 — 따로 다시 잰 값) 또는 (지금 길 RUN ∧ age ≥ 15 ∧ 가능 비트가 바뀜)뿐이다.
    SHELTER 는 잠금 뒤 가능 비트가 바뀌어도 유지가 이어지면 다시 고르지 않는다(hold)."""
    w = World(forest_on, seeds=[32094])
    rng = np.random.default_rng(19)
    pol = _route_policy(True)
    prev = None
    n = dict(onset=0, invalid=0, refeas=0, keep=0, hold=0)
    for _ in range(1200):
        a = pol(w, rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        w._route_apply(a[:, 0])
        snap = dict(mode=w.wf_mode.copy(), route=w.flight_route.copy(), k=w.route_k.copy(), age=w.route_age.copy(), feas=w.route_feas.copy())
        o, r, d, to = w.step(a)
        live = w.alive
        pan = (w.wf_mode == WF_PANIC) & live
        for i in np.flatnonzero(pan):
            if snap["mode"][i] != WF_PANIC:
                assert w.route_decide[i] and w.route_age[i] == 0, i
                n["onset"] += 1
                continue
            if not w.route_decide[i]:
                assert w.route_age[i] == snap["age"][i] + 1 and w.route_feas[i] == snap["feas"][i] and w.flight_route[i] == snap["route"][i]
                n["keep"] += 1
                sok_now = ROUTE_FEAS_SHELTER if w.route_cand_ok[i, ROUTE_SHELTER] else 0
                if snap["route"][i] == ROUTE_SHELTER and snap["age"][i] + 1 >= 15 and sok_now != snap["feas"][i]:
                    n["hold"] += 1          # 잠금 뒤 가능 비트가 바뀌었지만 SHELTER 유지가 이어져 다시 고르지 않음
                continue
            assert w.route_age[i] == 0
            inval = False
            if snap["route"][i] == ROUTE_SHELTER:
                k = snap["k"][i]
                awake = ~w.pred_asleep
                q = w.pred_pos[awake & (np.sqrt(((w.pred_pos - w.pos[i]) ** 2).sum(1)) <= w._wf["safe_r"])]
                v = w.cov_c[k] - w.pos[i]
                dc = np.sqrt((v * v).sum())
                ed = dc - w.cov_r[k]
                door = w.pos[i] + ed * v / dc
                mu = np.sqrt(((q - door) ** 2).sum(1)).min() - ed
                inval = mu < 0.0
            refeas = snap["route"][i] == ROUTE_RUN and snap["age"][i] + 1 >= 15 and w.route_feas[i] != snap["feas"][i]
            assert inval or refeas, (i, snap["route"][i], snap["age"][i], snap["feas"][i], w.route_feas[i])
            assert snap["route"][i] != ROUTE_SHELTER or inval, "SHELTER 는 무효로만 다시 고른다"
            n["invalid" if inval else "refeas"] += 1
    assert n["onset"] > 0 and n["keep"] > 0 and n["invalid"] > 0 and n["refeas"] > 0 and n["hold"] > 0, n


# --------------------------------------------------------------------- #
# 학습 경로 (판 4)
# --------------------------------------------------------------------- #


def test_vec_env_route_training_path():
    """R6 학습 세계 VecEnv: 관측 24 + 마스크 5, 판 4 마스크 안 표본만, 길 결정이 읽음에 들고 덮기 스텝은 읽음이 아니다. 끊긴 관측도 29 칸."""
    from env_v2.vec_env import MultiWorldVecEnv

    cfg = load_v2_config(R6).replace(N=12)
    v = MultiWorldVecEnv(cfg, num_worlds=2, reset_interval=200, meta_seed=1)
    assert v.obs_dim == 24 and v.policy_obs_dim == 29 and mask_version_of(v.obs_names) == 4
    v.reset()
    rng = np.random.default_rng(23)
    route_reads = over_reads = term = 0
    for _ in range(400):
        pks = [w.rep_peek() for w in v.worlds]
        m = v.current_masks()
        a = sample_masked(np.ones(m.shape), m, rng.random(len(m)))
        v.step_async(a)
        o, r, d, info = v.step_wait()
        rd = np.concatenate([pk["route_decide"] for pk in pks])
        ov = np.concatenate([pk["override"] for pk in pks]) != WF_NONE
        route_reads += int((v.last_reads & rd).sum())
        over_reads += int((v.last_reads & ov & ~rd).sum())
        assert o.shape[1] == 29 and not m[:, FREEZE].any()
        for inf in info:
            if "terminal_observation" in inf:
                assert inf["terminal_observation"].shape == (29,)
                term += 1
    assert route_reads > 0 and over_reads == 0 and term > 0 and v.num_resets > 0


def test_decide_count_matches_reads(forest, forest_on):
    """세계의 결정 셈(_rep_decide — repertoire_stats decide_frac·eval_v3 결정 비율)은 rep_peek 의 reads 합과 같다(train_v3 measure-fdec 의 f_dec 와 같은
    셈). 판 4 는 덮기(도주·웅크림) 스텝을 빼고 길 결정을 더한 값이다 — 판 2(길 끔)는 arbitrate 의 decide 그대로(그때도 reads 와 같다)."""
    for cfg, n_route in ((forest, None), (forest_on, 0)):
        w = World(cfg, seeds=[32096])
        rp = rep_params(cfg)
        rng = np.random.default_rng(29)
        reads = over = 0
        for _ in range(900):
            obs = w.observe()
            pk = w.rep_peek()
            m = action_mask(pk, obs, rp, obs_names=w.obs_names)
            reads += int(pk["reads"].sum())
            if n_route is not None:
                n_route += int(pk["route_decide"].sum())
                over += int((pk["override"] != WF_NONE).sum())
            w.step(sample_masked(np.ones(m.shape), m, rng.random(w.N)).astype(np.float64)[:, None])
        assert w._rep_decide == reads, (cfg is forest_on, w._rep_decide, reads)
        assert w.repertoire_stats()["decide_frac"] == reads / (900 * w.N)
        if n_route is not None:
            assert n_route > 0 and over > n_route


@pytest.mark.skipif(not ROUTE0.exists(), reason="ckpt 는 저장소에 없다 (route_extend.py 로 만든다)")
def test_training_keeps_reserved_row():
    """설계 16-2 의 2: 칸 3(COVER 자리 — 판 4 에서 늘 막힘) 출력 줄 W2[3]·B2[3] 은 학습이 움직이지 않는다. route0 에서 R6 학습 세계(세계 둘)로 PPO 두 롤아웃
    (train_v3 main 과 같은 조립 — 튜닝값·γ 0.995·범주 엔트로피 배율) 뒤 칸 3 줄은 비트 단위로 같고, 칸 4(SHELTER — 길 결정이 기울기를 받는다)·칸 1 줄은 바뀐다."""
    import torch

    import train_v3 as tv
    from env_v2.vec_env import MultiWorldVecEnv
    from train import load_tuned
    from train_v2 import apply_lr_schedule, resolve_gamma

    cfg = load_v2_config(R6)
    rep = rep_params(cfg)
    venv = MultiWorldVecEnv(cfg, num_worlds=2, meta_seed=0)
    n_steps = 64
    tuned, gamma, _ = resolve_gamma(load_tuned(ROOT / "configs" / "ppo_best.yaml"), tv.S1A_GAMMA)
    tuned, _ = apply_lr_schedule(tuned, "constant")
    model = tv.make_model_rep(venv, rep, None, n_steps=n_steps, seed=0, **tuned)
    tv.init_from_model(model, ROUTE0, "시험 — route0 (tests/test_route2_v3.py)")
    W0 = model.policy.action_net.weight.detach().clone()
    B0 = model.policy.action_net.bias.detach().clone()
    model.learn(total_timesteps=2 * n_steps * venv.num_envs, progress_bar=False)
    assert model.num_timesteps >= 2 * n_steps * venv.num_envs
    W, B = model.policy.action_net.weight.detach(), model.policy.action_net.bias.detach()
    assert torch.equal(W[FREEZE], W0[FREEZE]) and torch.equal(B[FREEZE], B0[FREEZE]), "칸 3(COVER 자리) 줄은 학습이 움직이지 않는다"
    assert not torch.equal(W[SLEEP], W0[SLEEP]) and not torch.equal(W[FLEE], W0[FLEE]), "칸 4·1 줄은 배운다(길 결정이 롤아웃에 있다)"


# --------------------------------------------------------------------- #
# 계약 해시·digest
# --------------------------------------------------------------------- #


def test_contract_hashes():
    """옛 계약 해시 셋은 그대로(조건부 키 — 판 2·3 dict 에 flight_route 가 없다), 새 판 4 해시는 박은 값이고 dict 에 flight_route 가 있다."""
    import export_weights_v3 as ex

    names = {18: obs_names(load_v2_config(CFG / "v3_wild3_mirror.yaml")), 19: obs_names(load_v2_config(CFG / "v3_r2_on.yaml")),
             21: obs_names(load_v2_config(OBS))}
    for n, want in CONTRACT_OLD.items():
        v = 3 if n == 19 else 2
        assert len(names[n]) == n and ex.contract_hash(names[n], v) == want, n
        assert "flight_route" not in ex.contract_dict(names[n], v)
    n24 = obs_names(load_v2_config(ROUTE))
    assert ex.contract_hash(n24, 4) == CONTRACT_OBS24 == ex.contract_hash(list(n24), 4)
    d = ex.contract_dict(n24, 4)
    assert d["flight_route"] == {
        "slots": {"run": 1, "shelter": 4, "reserved_masked": [3]},
        "obs": ["in_panic", "shelter_reach", "shelter_edge"],
        "decide": {"lock_steps": 15, "on": ["onset", "invalid", "lock_and_feasible_changed"], "feasible": ["shelter"], "refeas_from": ["run"]},
        "shelter": {"max_edge_u": 20.0, "cos_min": 0.0, "enter_margin_u": 2.0, "exit_margin_u": 0.0, "reach_norm_u": 10.0, "edge_norm_u": 20.0},
        "freeze_sleep_must_be_blocked": "effective_allowed",
    }
    assert d["mask"]["version"] == 4 and d["mask"]["alarm_mask_obs"] is None
    assert ex.contract_hash(n24, 2) != CONTRACT_OBS24, "같은 이름이라도 판이 다르면 다른 계약"
    assert ex.brain_golden_config_for(n24) == ex.BRAIN_GOLDEN_CONFIG_ROUTE == ROUTE
    assert ex.brain_golden_config_for(names[21]) == ex.BRAIN_GOLDEN_CONFIG_OBS21


def test_config_digests_unchanged():
    """옛 설정(wild_flight 를 켠 설정 전부)의 config digest·관측 이름이 HEAD 와 같다 — route 는 OPTIONAL_KEYS 끔 값이라 설정 파일·dict 가 그대로다.
    새 설정 둘은 생성기(make_route_configs.py)로 만든 그대로다."""
    rm = _module("_rm_for_route2", ROOT / "results" / "v3" / "mirror" / "run_mirror.py")
    for name, want in HEAD_DIGEST.items():
        cfg = load_v2_config(CFG / name)
        assert rm.config_digest(cfg) == want, name
        assert "route" not in cfg.v2["features"]["wild_flight"]
        assert "in_panic" not in obs_names(cfg)
    mk = _module("_mk_for_route2", ROOT / "results" / "v3" / "route" / "make_route_configs.py")
    assert mk.main(["--check"]) == 0
    r6 = load_v2_config(R6)
    f = r6.v2["features"]
    assert f["wild_flight"]["route"] is True and f["wild_flight"]["flight_cost"] == 0.0 and f["wild_satiation"]["enabled"] is False
    # R5 학습 조리법 그대로(설계 8-2·16-8): 무작위 숲 섞기·지역 나무 원판·부활이 R5 와 같다
    r5 = load_v2_config(TRAIN)
    assert r6.v2["train"]["region_mix"] == r5.v2["train"]["region_mix"] and "random_forest" in r6.v2["train"]["region_mix"]
    assert f["integrated_stage"] == r5.v2["features"]["integrated_stage"] and f["integrated_stage"]["respawn"] is True
    assert r6.v2["train"]["repertoire"]["allowed"] == ["graze", "flee", "hide"]
    assert abs(rep_params(r6)["cat_ent_coef"] - 0.01) < 1e-9
    mir = load_v2_config(ROUTE)
    assert mir.v2["features"]["wild_flight"]["route"] is True and "foliage" not in mir.v2["features"]["obstacles"]
    assert mir.v2["features"]["integrated_stage"]["respawn"] is False


# --------------------------------------------------------------------- #
# route0 (results/v3/route/route_extend.py)
# --------------------------------------------------------------------- #


@pytest.mark.skipif(not (ROUTE0.exists() and OBS21ZERO.exists()), reason="ckpt 는 저장소에 없다 (route_extend.py 로 만든다)")
def test_route0_deployment_identity(discs):
    """route0 의 배포(argmax) 궤적(길 켬, 관측 24) = obs21zero 의 궤적(길 끔, 관측 21) — 숲 N·고지 G 600 스텝. 길 결정은 늘 RUN.
    확인 기록(route_extend.py — 지역 셋 × G·N × 시드 둘 × 1800 스텝)도 모두 같고, 두 칸 결정의 π 는 (0.881, 0.119)·π′ 는 (0.862, 0.138)."""
    from stable_baselines3 import PPO

    rx = _module("_route_extend_for_test", ROOT / "results" / "v3" / "route" / "route_extend.py")
    on, off = PPO.load(str(ROUTE0), device="cpu"), PPO.load(str(OBS21ZERO), device="cpu")
    assert on.policy.rep_mask_version == 4 and tuple(on.policy.rep_obs_names) == obs_names(load_v2_config(ROUTE))
    assert tuple(on.policy.rep_allowed) == ("graze", "flee", "hide")
    for sat, reg in ((False, "Forest"), (True, "Highland")):
        a = rx.run_deploy(on, rx.region_configs(load_v2_config(ROUTE), sat)[reg], 32095, 600, 21)
        b = rx.run_deploy(off, rx.region_configs(load_v2_config(OBS), sat)[reg], 32095, 600)
        assert a["step_hash"] == b["step_hash"] and a["hash"] == b["hash"], (sat, reg)
        assert a["n_dec"] > 0 and set(a["picked"]) == {1}
        if len(a["pi"]):
            assert np.allclose(a["pi"][:, 4], 1.0 / (1.0 + np.exp(2.0)), atol=1e-5)
    v = json.loads(VERIFY.read_text(encoding="utf-8"))
    assert v["all_same"] and len(v["runs"]) == 12 and v["steps"] >= 1800 and v["route_choice"] > 100
    assert abs(v["pi_shelter"] - 0.1192) < 1e-3 and abs(v["pi_run"] - 0.8808) < 1e-3
    assert abs(v["pi_eps_shelter"] - 0.1382) < 1e-3 and abs(v["pi_eps_run"] - 0.8618) < 1e-3 and v["pi_other_max"] == 0.0


@pytest.mark.skipif(not (ROUTE0.exists() and OBS21ZERO.exists()), reason="ckpt 는 저장소에 없다 (route_extend.py 로 만든다)")
def test_route0_weights_and_brain_file(tmp_path):
    """route0 가중치: 첫 층(정책·가치) 앞 21 열 = obs21zero, 새 세 열 = +0.0, 출력 칸 4 = 칸 1 줄 + 편향 −2, 칸 3 = 원 줄. 다시 만들어도 zip 바이트가 같다.
    두뇌 파일(results/v3/route/brains): 계약 판 4 해시, 골든에 도주 길 결정(두 칸·문턱 근처·한 칸)이 있고 로짓 차 2·argmax RUN."""
    import base64

    import export_weights_v3 as ex
    from stable_baselines3 import PPO

    rx = _module("_route_extend_for_test2", ROOT / "results" / "v3" / "route" / "route_extend.py")
    a = rx.route_extend(out_model=tmp_path / "a" / "v3_r1_g995_s3_obs24route0.zip")
    b = rx.route_extend(out_model=tmp_path / "b" / "v3_r1_g995_s3_obs24route0.zip")
    import hashlib as _h

    assert a["sha256"] == b["sha256"] == _h.sha256(ROUTE0.read_bytes()).hexdigest(), "같은 원 모델이면 같은 zip 바이트"
    assert a["err_logit"] == 0.0 and a["err_value"] == 0.0
    new, old = PPO.load(str(ROUTE0), device="cpu").policy, PPO.load(str(OBS21ZERO), device="cpu").policy
    for net in ("policy_net", "value_net"):
        wn = getattr(new.mlp_extractor, net)[0].weight.detach().numpy()
        wo = getattr(old.mlp_extractor, net)[0].weight.detach().numpy()
        assert wn.shape == (64, 24) and np.array_equal(wn[:, :21], wo) and not wn[:, 21:].view(np.uint32).any()
    an, ao = new.action_net.weight.detach().numpy(), old.action_net.weight.detach().numpy()
    bn, bo = new.action_net.bias.detach().numpy(), old.action_net.bias.detach().numpy()
    assert np.array_equal(an[:4], ao[:4]) and np.array_equal(an[4], ao[1]) and np.array_equal(bn[:4], bo[:4])
    assert bn[4] == np.float32(bo[1] - np.float32(2.0))
    d = json.loads(BRAIN.read_text(encoding="utf-8"))
    assert d["contract_hash"] == f"0x{CONTRACT_OBS24:016x}" and d["mask_version"] == 4 and d["obs_dim"] == 24
    assert d["contract"]["flight_route"]["slots"] == {"run": 1, "shelter": 4, "reserved_masked": [3]}
    assert d["model"]["sha256"] == a["sha256"] and d["allowed"] == ["graze", "flee", "hide"]
    assert d["golden"]["world_config"] == "configs/v3_wild3_route_mirror.yaml"
    cases = d["golden"]["cases"]
    kinds = [c["kind"] for c in cases]
    assert kinds.count("route") + kinds.count("route_edge") >= 2 and kinds.count("route_single") >= 1
    W = {}
    for L in d["layers"]:
        W[L["weight"]] = np.frombuffer(base64.b64decode(L["w_f32le_b64"]), dtype="<f4").reshape(L["out"], L["in"])
        W[L["bias"]] = np.frombuffer(base64.b64decode(L["b_f32le_b64"]), dtype="<f4")
    for c in cases:
        if not c["kind"].startswith("route"):
            continue
        o = np.array(c["obs"], dtype=np.float32)
        assert o[21] == 1.0 and c["mask"] == [0, 1, 0, 0, int(o[22] > 0.0)] and c["action"] == 1
        lg = ex.forward_np(o[None], W, np.float32)[0]
        assert np.allclose(lg, c["logits"], atol=1e-5) and abs((lg[1] - lg[4]) - 2.0) < 1e-5
    edge = [np.float32(c["obs"][22]) for c in cases if c["kind"] == "route_edge"]
    other = [np.float32(c["obs"][22]) for c in cases if c["kind"] == "route"]
    assert edge and (not other or max(edge) <= min(other)), "문턱 근처 = shelter_reach 가 가장 작은 두 칸 결정"
