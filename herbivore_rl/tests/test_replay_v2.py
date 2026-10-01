"""V2 리플레이 도구(0-4) — 보행 판정, 리스폰 흐림, 프레임 수집, 렌더, 대조군 C1′. 계획서 6.4."""

import env.torch_init  # noqa: F401  ← torch보다 먼저

from types import SimpleNamespace

import matplotlib.pyplot as plt
import numpy as np
import pytest

import replay_v2 as R
from env.rollout import STAT_COLUMNS
from env_v2.config import load_v2_config
from env_v2.rollout import build_policy, rollout
from env_v2.world import World
from policies.registry import make_policy

FIXED = {"kind": "fixed", "action": [0.3, 0.8, 0.4, 0.1]}


@pytest.fixture
def tiny_cfg():
    """아주 작은 세계: 초식 16, 포식자 2, 한 변 30."""
    cfg = load_v2_config()
    rand = dict(cfg.rand, world_size=[30.0, 30.0], predator_count=[2, 2])
    return cfg.replace(N=16, rand=rand)


def _run(cfg, steps=6, stride=2, label="t", world=None):
    w = world or World(cfg, seeds=[10000])
    frames = R.collect(w, make_policy(FIXED), steps, stride)
    return R.Run(label, w, frames, w.stats())


# --------------------------------------------------------------------- #
# 판정 · 시간
# --------------------------------------------------------------------- #


def test_gait_state_thresholds():
    hs = 0.6
    speed = np.array([0.0, 1e-9, 0.1 * hs, 0.6 * hs, 0.61 * hs, hs, 2 * hs])
    np.testing.assert_array_equal(R.gait_state(speed, hs), [0, 0, 1, 1, 2, 2, 2])


def test_gait_fractions_sum_to_one():
    f = R.gait_fractions(np.array([0, 1, 1, 2], dtype=np.int8))
    np.testing.assert_allclose(f, [0.25, 0.5, 0.25])


def test_v1_world_is_always_running(tiny_cfg):
    """v1·v2.0 은 항상 최고 속력이다. 보행 색은 주황 하나뿐이어야 한다."""
    run = _run(tiny_cfg, steps=20, stride=1)
    gait = np.concatenate([f["gait"] for f in run.frames])
    assert (gait == R.GAIT_RUN).mean() > 0.99


def test_clock_and_step_seconds(tiny_cfg):
    assert R.step_seconds(tiny_cfg) == pytest.approx(8 / 60)
    assert R.fmt_clock(1800 * R.step_seconds(tiny_cfg)) == "04:00"
    assert R.fmt_clock(59.9) == "00:59"
    assert R.clock_tick(240) == 30 and R.clock_tick(80) == 10 and R.clock_tick(1e6) == 3600


def test_parse_spec():
    assert R.parse_spec("fixed:0.1,0.2,0.3,0.4") == {"kind": "fixed", "action": [0.1, 0.2, 0.3, 0.4]}
    assert R.parse_spec("utility") == {"kind": "utility"}
    assert R.parse_spec("utility:default") == {"kind": "utility", "params": "default"}
    assert R.parse_spec("random:3") == {"kind": "random", "seed": 3}
    assert R.parse_spec("learned:x.zip")["kind"] == "learned"
    assert R.parse_spec('{"kind": "random", "seed": 1}') == {"kind": "random", "seed": 1}
    with pytest.raises(ValueError):
        R.parse_spec("fixed:0.1,0.2")
    with pytest.raises(ValueError):
        R.parse_spec("nope")


def test_parse_spec_perm_and_wrapper_json():
    """C1′ 짧은 꼴 `perm:<바탕>` 은 diagnose_v2 의 C1′ 과 같은 래퍼 스펙이 된다."""
    fixed = {"kind": "fixed", "action": [0.1, 0.2, 0.3, 0.4]}
    perm = {"kind": "act_permute", "salt": 0}
    assert R.parse_spec("perm:fixed:0.1,0.2,0.3,0.4") == {"policy": fixed, "wrap": [perm]}
    assert R.parse_spec("perm:learned:x.zip")["policy"]["kind"] == "learned"
    js = '{"policy": {"kind": "utility"}, "wrap": [{"kind": "act_permute"}]}'
    assert R.parse_spec(js) == {"policy": {"kind": "utility"}, "wrap": [{"kind": "act_permute"}]}
    with pytest.raises(ValueError):
        R.parse_spec("perm:")
    assert R.spec_label(R.parse_spec("perm:utility")) == "행동 순열 · Utility"


def test_fov_slots():
    assert R.fov_slots(5, 2) == [0, 1]
    assert R.fov_slots(3, 9) == [0, 1, 2]
    bold = np.array([0.5, 0.9, 0.1, 0.5])
    assert R.fov_slots(4, 2, bold) == [1, 2]                 # 궤적 두 개체 먼저
    assert R.fov_slots(4, 3, bold) == [1, 2, 0]
    assert R.fov_slots(4, 1, bold) == [1]
    assert R.fov_slots(4, 2, np.zeros(4)) == [0, 1]          # 최대=최소면 겹치지 않게 채운다
    assert R.fov_slots(4, 0, bold) == []


def test_applied_gait_priority():
    """gait 훅 → vel 훅 → 조향식 재계산 순서."""
    cfg = SimpleNamespace(herb_speed=1.0)
    v_pre = np.array([[1.0, 0.0], [0.0, 0.0]])
    w = SimpleNamespace(cfg=cfg, gait=np.array([1, 1]), vel=np.zeros((2, 2)))
    np.testing.assert_array_equal(R.applied_gait(w, v_pre), [1, 1])
    w.gait = None
    np.testing.assert_array_equal(R.applied_gait(w, v_pre), [0, 0])
    w.vel = None
    np.testing.assert_array_equal(R.applied_gait(w, v_pre), [2, 0])
    with pytest.raises(ValueError):
        R.applied_gait(w, None)


# --------------------------------------------------------------------- #
# 리스폰 흐림
# --------------------------------------------------------------------- #


def test_respawn_tracker_fades_back():
    tr = R.RespawnTracker(3, fade_steps=4)
    np.testing.assert_array_equal(tr.alpha(), 1.0)          # 시작 개체는 리스폰이 아니다
    tr.update(np.array([False, True, False]))
    a = tr.alpha()
    assert a[1] == pytest.approx(R.DIM_ALPHA) and a[0] == a[2] == 1.0
    assert tr.life.tolist() == [0, 1, 0]
    for _ in range(4):
        tr.update(np.zeros(3, dtype=bool))
    np.testing.assert_array_equal(tr.alpha(), 1.0)


def test_collect_dims_respawned_slot(tiny_cfg):
    """done 슬롯은 다음 프레임부터 흐리게, 생애 번호가 오른다."""
    w = World(tiny_cfg, seeds=[10000])
    real_step = w.step

    def step(a):
        obs, rew, done, term = real_step(a)
        if w.t == 4:                                        # 루프 t=3 의 스텝
            done = done.copy()
            done[0] = True
        return obs, rew, done, term

    w.step = step
    frames = R.collect(w, make_policy(FIXED), steps=8, stride=1, fade_frames=3)
    assert frames[3]["life"][0] == 0 and frames[3]["alpha"][0] == 1.0
    assert frames[4]["life"][0] == 1 and frames[4]["alpha"][0] == pytest.approx(R.DIM_ALPHA)
    assert frames[7]["alpha"][0] == 1.0                       # 3스텝 뒤 회복


def test_trail_stops_at_respawn():
    frames = [dict(pos=np.full((2, 2), float(k)), life=np.array([0, 0 if k < 3 else 1]))
              for k in range(6)]
    assert len(R._trail(frames, 5, 0, 100)) == 6
    assert len(R._trail(frames, 5, 1, 100)) == 3              # 리스폰 뒤 프레임만
    assert len(R._trail(frames, 5, 0, 2)) == 2


# --------------------------------------------------------------------- #
# 수집 · 렌더
# --------------------------------------------------------------------- #


def test_collect_frames_by_stride(tiny_cfg):
    run = _run(tiny_cfg, steps=7, stride=2)
    assert [f["t"] for f in run.frames] == [0, 2, 4, 6]
    f = run.frames[0]
    assert f["pos"].shape == (16, 2) and f["gait"].shape == (16,)
    assert f["vig"] is None and f["mem"] is None and f["bold"] is None
    s = R.series(run.frames)
    assert s["gait"].shape == (4, 3) and np.isnan(s["vig"]).all()


def test_collect_reads_step_hooks_after_step(tiny_cfg, monkeypatch):
    """gait·vigilant·gaze 는 world.step 뒤에 같은 스텝 값으로 읽는다. gait 훅이 있으면 조향식을 안 부른다."""
    w = World(tiny_cfg, seeds=[10000])
    w.gait = np.zeros(w.N, dtype=np.int8)
    real_step = w.step

    def step(a):
        out = real_step(a)
        w.gait = np.full(w.N, w.t % 3, dtype=np.int8)       # 이번 스텝(t → t+1)에 적용된 값
        w.vigilant = np.full(w.N, w.t % 2 == 1)
        w.gaze = np.tile([0.0, float(w.t)], (w.N, 1))
        return out

    def boom(*_a, **_k):
        raise AssertionError("gait 훅이 있으면 조향식을 다시 계산하지 않는다")

    w.step = step
    monkeypatch.setattr(R, "steer", boom)
    frames = R.collect(w, make_policy(FIXED), steps=5, stride=1)
    for f in frames:
        t1 = f["t"] + 1
        assert (f["gait"] == t1 % 3).all()
        assert (f["vig"] == (t1 % 2 == 1)).all()
        assert (f["gaze"][:, 1] == t1).all()


def test_collect_uses_vel_hook(tiny_cfg):
    """gait 훅이 없고 vel 훅이 있으면 vel 의 속력으로 판정한다."""
    w = World(tiny_cfg, seeds=[10000])
    hs = tiny_cfg.herb_speed
    w.vel = np.zeros((w.N, 2))
    w.vel[: w.N // 2, 0] = 0.4 * hs
    frames = R.collect(w, make_policy(FIXED), steps=2, stride=1)
    half = w.N // 2
    assert (frames[0]["gait"][:half] == R.GAIT_WALK).all()
    assert (frames[0]["gait"][half:] == R.GAIT_STOP).all()


def test_run_policy_perm_matches_rollout(tiny_cfg):
    """C1′ 리플레이는 env_v2.rollout 의 같은 시드 롤아웃과 같은 세계·같은 순열이다."""
    spec = R.parse_spec("perm:utility:default")
    run = R.run_policy(tiny_cfg, spec, 10000, steps=12, stride=3)
    ref = rollout(tiny_cfg, build_policy(spec, 10000), 10000, 12)
    for k in STAT_COLUMNS:
        np.testing.assert_equal(run.stats[k], ref[k])
    c0 = R.run_policy(tiny_cfg, R.parse_spec("utility:default"), 10000, steps=12, stride=3)
    np.testing.assert_array_equal(run.frames[0]["pos"], c0.frames[0]["pos"])    # 같은 시작 세계
    assert not np.array_equal(run.frames[-1]["pos"], c0.frames[-1]["pos"])     # 순열이 행동을 바꾼다
    assert run.label == "행동 순열 · Utility (기본값)"


def _hooked_run(cfg):
    """v2.2~2.4 훅 속성을 붙인 세계로 4스텝."""
    w = World(cfg, seeds=[10000])
    w.vigilant = np.arange(w.N) % 4 == 0
    w.boldness = np.linspace(0.0, 1.0, w.N)
    w.region_mem = np.array([0.7, 0.1])
    w.region_id = (w._cell_x > w.size / 2).astype(int)
    return _run(cfg, steps=4, stride=2, label="hooked", world=w)


def test_collect_reads_hooks(tiny_cfg):
    """훅 속성이 있으면 프레임에 담긴다."""
    s = R.series(_hooked_run(tiny_cfg).frames)
    np.testing.assert_allclose(s["vig"], 0.25)
    assert s["mem"].shape == (2, 2)


def test_render_writes_gif(tiny_cfg, tmp_path):
    out = R.render([_run(tiny_cfg)], tmp_path / "r.gif", fps=10, dpi=30)
    assert out.suffix == ".gif" and out.stat().st_size > 0
    assert R.video_info(out)["frames"] == 3


def test_render_mp4_or_gif_fallback(tiny_cfg, tmp_path):
    out = R.render([_run(tiny_cfg)], tmp_path / "r.mp4", fps=10, dpi=30)
    assert out.suffix in (".mp4", ".gif") and out.exists() and out.stat().st_size > 0


def test_render_compare_with_hooks(tiny_cfg, tmp_path):
    """나란히 그리기 + 훅 표시(경계, 궤적, 지역 기억)가 예외 없이 돈다."""
    hooked = _hooked_run(tiny_cfg)
    plain = _run(tiny_cfg, steps=4, stride=2, label="plain")
    out = R.render([hooked, plain], tmp_path / "c.gif", fps=10, dpi=30)
    assert out.exists() and R.video_info(out)["frames"] == 2


def test_render_compare_c0_c1prime(tiny_cfg, tmp_path):
    """계획서 6.4: C0 과 C1′ 을 같은 시드·카메라로 나란히 그린다."""
    runs = [R.run_policy(tiny_cfg, R.parse_spec(s), 10000, steps=6, stride=2, label=lb)
            for s, lb in (("utility:default", "C0"), ("perm:utility:default", "C1′"))]
    out = R.render(runs, tmp_path / "c01.gif", fps=10, dpi=30)
    assert out.exists() and R.video_info(out)["frames"] == 3


def _with_caught(run, caught):
    frames = [dict(f, caught=int(c)) for f, c in zip(run.frames, caught)]
    return R.Run(run.label, run.world, frames, run.stats)


def test_compare_panels_share_axes(tiny_cfg):
    """포획 수가 다른 칸도 포획 누적 축과 x축을 함께 쓴다."""
    base = _run(tiny_cfg, steps=6, stride=2)
    runs = [_with_caught(base, [0, 2, 5]), _with_caught(base, [0, 10, 40])]
    fig, _, _, panels = R.build_figure(runs, dpi=30)
    try:
        lims = {p.caught_ax.get_ylim() for p in panels}
        assert lims == {(0.0, R.caught_ylim(40))}
        assert len({p.ser_ax.get_xlim() for p in panels}) == 1
    finally:
        plt.close(fig)


def test_herb_fov_wedges_widen_when_vigilant(tiny_cfg):
    """초식 부채꼴은 반경 see_r, 각 fov_deg 이고 경계 중이면 360° 원이다. 대담함 훅이 있으면 궤적 개체를 고른다."""
    run = _hooked_run(tiny_cfg)                               # 경계 = 슬롯 0,4,8,12, 대담 = 슬롯 번호 순
    fig, update, _, panels = R.build_figure([run], dpi=30, fov_herbs=2)
    try:
        update(0)
        wd_bold, wd_timid = panels[0].herb_wedges                # 슬롯 15(경계 아님), 슬롯 0(경계)
        pos = run.frames[0]["pos"]
        assert wd_bold.r == tiny_cfg.see_r
        assert wd_bold.theta2 - wd_bold.theta1 == pytest.approx(tiny_cfg.fov_deg)
        assert wd_bold.center == pytest.approx(tuple(pos[15]))
        assert wd_timid.theta2 - wd_timid.theta1 == pytest.approx(360.0)
        assert wd_timid.center == pytest.approx(tuple(pos[0]))
    finally:
        plt.close(fig)


def test_legend_lists_vigilance_and_each_region(tiny_cfg):
    labels = [h.get_label() for h in R._legend_handles([_hooked_run(tiny_cfg)], 2, 2)]
    for want in ("경계 비율(하단)", "지역 기억 m_A(하단)", "지역 기억 m_B(하단)",
                 "초식 시야(경계 시 360°)", "포식자 시야"):
        assert want in labels
    plain = [h.get_label() for h in R._legend_handles([_run(tiny_cfg)], 0, 0)]
    assert not any(("경계" in x) or ("지역 기억" in x) or ("시야" in x) for x in plain)


def test_main_rejects_conflicting_sources_and_extra_labels(capsys):
    """--model·--policy·--compare 는 하나만. 라벨이 스펙보다 많으면 무엇을 돌리기 전에 멈춘다."""
    for argv in (["--model", "x.zip", "--policy", "utility"],
                 ["--policy", "utility", "--compare", "utility", "random:1"],
                 ["--policy", "utility", "--labels", "a", "b"],
                 ["--policy", "perm:"]):
        with pytest.raises(SystemExit) as e:
            R.main(argv)
        assert e.value.code == 2
    p = R.build_parser()
    args = p.parse_args(["--compare", "utility", "perm:utility", "--labels", "C0"])
    specs, labels = R.specs_and_labels(p, args)
    assert len(specs) == 2 and labels == ["C0", None]
