"""R9 평가 시험 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 12절 24·25 + 평가 명령 끝까지 돌기).

24 지표 대본: 답을 아는 손 궤적으로 다가감 구간(걷기·뛰기)·죽임 귀속·새끼 고르기 지수·막힘 몫·공존 세계 판정.
25 판정 시드 잠금: 첫 판정이 잠금 파일을 쓰고 다른 두뇌·설정이면 거부, 학습·점검·보정 코드는 판정 시드에서 오류.
그 밖: 세계 묶음 크기(chunk)와 무관한 평가 결과, 되뽑기 재현, J1 해시 배정 균형, 하위 명령이 작은 크기로 끝까지 돈다(규칙 두뇌·작은 무작위 npz).
시드: 44350~44399 만 (10절). 판정 시드는 세계를 돌리지 않고 잠금·거부 경로만 본다.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import r9_body as B
from env_v2 import r9_brains as BR
from env_v2 import r9_life as L
from env_v2.r9_world import R9World

EVAL_DIR = ROOT / "results" / "v3" / "r9"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import eval_r9 as EV  # noqa: E402
import r9_eval_core as C  # noqa: E402

CFG = ROOT / "configs" / "v3_r9.yaml"
JCFG = ROOT / "configs" / "v3_r9_judge.yaml"
D_, W_, R_ = B.DEER, B.WOLF, B.BOAR


@pytest.fixture(scope="module")
def cfg():
    return B.load_r9_config(CFG)


@pytest.fixture(scope="module")
def jcfg():
    return B.load_r9_config(JCFG)


@pytest.fixture(scope="module")
def brains_dir(tmp_path_factory, cfg):
    """Six small random npz brains (A·B × three species) with the right contract hashes."""
    d = tmp_path_factory.mktemp("r9_brains")
    for bi, br in enumerate("AB"):
        for sp in B.SPECIES:
            rng = np.random.default_rng([44399, bi, B.SPECIES_INDEX[sp]])
            w = {k: (rng.standard_normal(s) * 0.3).astype(np.float32) for k, s in BR.NPZ_SHAPES.items()}
            BR.save_brain(d / f"{br}_{sp}.npz", w, BR.brain_meta(cfg, sp, br, 0, 0, None))
    return d


def brain_args(d: Path, branches="AB") -> list[str]:
    return [f"{b}:{s}={d / f'{b}_{s}.npz'}" for b in branches for s in B.SPECIES]


def scene(cfg, counts, shelters=((55.0, 55.0, 4.0),), seed=44360):
    """One world, fixed shelter, given counts; everybody stopped, adult, genome (1, 1), full stamina/HP, no breeding, no food."""
    c = B.override(cfg, {"world": {"shelters": {"fixed": [list(s) for s in shelters]}}})
    w = R9World(c, [seed], counts=np.asarray([counts], dtype=np.int64), record=True)
    a = w.alive
    w.vel[:] = 0.0
    w.disp[:] = 0.0
    w.g_size[a] = 1.0
    w.g_speed[a] = 1.0
    w.hp[:] = 1.0
    w.stam[:] = 1.0
    w.E[a] = 0.6
    w.R[a] = 0.5
    w.born[:] = -3.0 * w.sb["maturity"]
    w.next_birth[:] = 1e9
    for n in ("grass", "root", "grass_cap", "root_cap"):
        getattr(w, n)[:] = 0.0
    w.refresh()
    return w


def put(w, s, xy, head=(1.0, 0.0)):
    w.pos[0, s] = xy
    w.head[0, s] = head
    w.vel[0, s] = 0.0


def drive(w, rec, act_fn, n_dec):
    for _ in range(n_dec):
        a = act_fn(w)
        rec.before(w, a)
        obs, rew, done, info = w.step(a)
        rec.after(w, a, rew, done, info)
    return rec.finish(w)


# --------------------------------------------------------------------------- 24 지표 대본


def test_24_hunt_segments_hand_trajectory():
    """다가감 구간·죽임 귀속 (8-2): 같은 표적 구간 우선, 열린 구간 없으면 길이 미달 구간 하나로 성공, 끝난 구간에는 안 붙임."""
    H = [dict(k=0, wolf_uid=1, target_uid=10, target_sp=0, t0=100, t1=120, n_close=6, ran=True, end="kill"),
         dict(k=0, wolf_uid=1, target_uid=11, target_sp=0, t0=100, t1=124, n_close=7, ran=True, end="gap"),
         dict(k=0, wolf_uid=1, target_uid=12, target_sp=0, t0=200, t1=220, n_close=5, ran=False, end="gap"),
         dict(k=0, wolf_uid=1, target_uid=13, target_sp=0, t0=300, t1=306, n_close=3, ran=False, end="kill"),   # 4 결정 이하
         dict(k=1, wolf_uid=2, target_uid=20, target_sp=2, t0=400, t1=430, n_close=10, ran=False, end="gap")]
    K = [dict(k=0, t=118, wolf_uid=1, prey_uid=10, prey_sp=0, wolf_act=B.RUN_FIRST),
         dict(k=0, t=305, wolf_uid=1, prey_uid=13, prey_sp=0, wolf_act=B.WALK_FIRST),      # 열린 '자격' 구간 없음 → 짧은 구간 성공
         dict(k=0, t=500, wolf_uid=1, prey_uid=14, prey_sp=0, wolf_act=B.WATCH),           # 220 에 끝난 구간에는 안 붙임
         dict(k=1, t=420, wolf_uid=2, prey_uid=21, prey_sp=0, wolf_act=B.WALK_FIRST + 2),  # 다른 표적, 열린 구간 E 성공
         dict(k=1, t=900, wolf_uid=3, prey_uid=22, prey_sp=2, wolf_act=B.RUN_FIRST)]       # 구간이 하나도 없는 늑대
    h = C.hunt_stats(H, K, 2)
    assert h["qualifying"].tolist() == [3, 1]
    assert h["short_kills"].tolist() == [2, 1]
    assert h["segments"].tolist() == [5, 2] and h["successes"].tolist() == [3, 2]
    assert h["kills"].tolist() == [3, 2] and h["walk_kills"].tolist() == [2, 1]
    # 같은 구간에 두 번 죽여도 성공은 한 번
    h2 = C.hunt_stats(H[:1], [K[0], dict(K[0], t=119, prey_uid=99)], 1)
    assert h2["successes"].tolist() == [1] and h2["segments"].tolist() == [1]
    # 덧붙임(보고만): 같은 늑대의 겹친 구간을 하나로
    e = C.hunt_episodes(H, K, 2)
    assert e["episodes"].tolist() == [2 + 2, 1 + 1] and e["successes"].tolist() == [1 + 2, 1 + 1]


def test_24_world_walk_approach_kill(cfg):
    """손 궤적: 늑대가 서 있는 사슴에게 걸어 다가가 문다 → 다가감 구간 하나 (걷기), 죽임이 그 구간의 성공, 걸어서 문 죽임 몫 1."""
    w = scene(cfg, [1, 1, 0])
    d, wf = int(w.sp_lo[D_]), int(w.sp_lo[W_])
    put(w, d, (30.0, 30.0))
    put(w, wf, (24.0, 30.0))
    w.refresh()
    rec = C.Recorder(w, scenes=False)

    def act(w):
        a = np.full((w.K, w.S), B.WATCH, dtype=np.int64)
        a[0, wf] = B.WALK_FIRST                       # 머리 그대로 앞으로 걷기
        return a
    r = drive(w, rec, act, 24)
    j = C.j3_metrics(r)
    assert j["kills"] == 1 and j["segments"] == 1 and j["successes"] == 1 and j["short_kills"] == 0
    assert j["success_rate"] == 1.0 and j["walk_kill_share"] == 1.0
    seg = [h for h in r["hunts"] if h["n_close"] > 4]
    assert len(seg) == 1 and seg[0]["end"] == "kill" and not seg[0]["ran"]


def test_24_boar_juvenile_index_from_world(cfg):
    """새끼 고르기 지수 (8-2): 잡힐 때 그 사분면 멧돼지 3 마리 가운데 새끼 1 (몫 1/3), 잡힌 것이 새끼 → 지수 3."""
    w = scene(cfg, [0, 1, 3])
    wf, b0 = int(w.sp_lo[W_]), int(w.sp_lo[R_])
    put(w, wf, (30.0, 30.0))
    put(w, b0, (30.8, 30.0), head=(1.0, 0.0))        # 늑대가 등 뒤 → 반격 없음, 갓난 몸이라 한 번에 죽음
    w.born[0, b0] = -0.1 * w.sb["maturity"][0, b0]
    put(w, b0 + 1, (10.0, 10.0))
    put(w, b0 + 2, (12.0, 48.0))
    w.refresh()
    rec = C.Recorder(w, scenes=False)

    def act(w):
        a = np.full((w.K, w.S), B.WATCH, dtype=np.int64)
        a[0, wf] = B.WALK_FIRST
        return a
    r = drive(w, rec, act, 2)
    assert len(r["kills"]) == 1
    e = r["kills"][0]
    assert e["prey_sp"] == R_ and e["prey_af"] < 1.0 and abs(e["juv_share"] - 1.0 / 3.0) < 1e-12
    j = C.juvenile_index(r["kills"], 1)
    assert j["young"].sum() / j["share"].sum() == pytest.approx(3.0)
    hand = [dict(k=0, prey_sp=R_, prey_af=0.5, juv_share=0.2), dict(k=0, prey_sp=R_, prey_af=1.0, juv_share=0.25),
            dict(k=1, prey_sp=R_, prey_af=0.3, juv_share=0.2), dict(k=1, prey_sp=D_, prey_af=0.1, juv_share=float("nan"))]
    jj = C.juvenile_index(hand, 2)
    assert jj["n"].tolist() == [2, 1] and jj["young"].sum() / jj["share"].sum() == pytest.approx(2.0 / 0.65)


def test_24_block_share_hand():
    """막힘 몫 = 콘텐츠 상한(늑대 예산·멧돼지 상한·대기 1 건·배열 상한) 막힘 ÷ (그것 + 맺은 짝), 먹이 예산은 따로."""
    K, Q = 2, 4
    bl = np.zeros((K, Q, 3, L.N_BLOCK), np.int64)
    bl[0, 0, D_, L.BLOCK_ONE_PENDING] = 6
    bl[0, 1, W_, L.BLOCK_WOLF_BUDGET] = 2
    bl[1, 2, R_, L.BLOCK_BOAR_CAP] = 1
    bl[1, 3, D_, L.BLOCK_FOOD] = 5
    paired = np.zeros((K, Q, 3), np.int64)
    paired[0, 0, D_] = 3
    paired[1, 2, R_] = 2
    life = dict(blocked=bl, paired=paired)
    bs = C.block_share(life)
    assert bs["content"].sum() == 9 and bs["paired"].sum() == 5 and bs["food"].sum() == 5
    assert C.ratio(bs["content"].sum(1), bs["content"].sum(1) + bs["paired"].sum(1)) == pytest.approx(9.0 / 14.0)
    assert bs["by_reason"][D_, L.BLOCK_FOOD] == 5


def test_24_breedable_pair_rules():
    """공존 판정의 '번식할 수 있는 쌍': 성숙·성별 맞음(늑대는 아무 둘)·근친 아님(부모-자식·부모 하나 공유)."""
    F, M, N = B.SEX_FEMALE, B.SEX_MALE, B.SEX_NONE
    t = np.ones(2, bool)
    assert C.breedable_pair(t, [F, M], [1, 2], [0, 0], [0, 0])
    assert not C.breedable_pair(t, [F, F], [1, 2], [0, 0], [0, 0])
    assert C.breedable_pair(t, [F, M], [1, 2], [7, 0], [8, 9])                        # 부모가 모두 다름 → 근친 아님
    assert not C.breedable_pair(t, [F, M], [1, 2], [7, 7], [8, 9])                    # 같은 부모 7 → 형제
    assert not C.breedable_pair(t, [F, M], [1, 2], [0, 1], [0, 5])                    # 2 의 부모가 1 → 부모-자식
    assert not C.breedable_pair(np.array([True, False]), [F, M], [1, 2], [0, 0], [0, 0])   # 성숙 하나뿐
    assert C.breedable_pair(t, [N, N], [3, 4], [0, 0], [0, 0])
    assert not C.breedable_pair(np.array([True]), [N], [3], [0], [0])
    assert not C.breedable_pair(t, [N, N], [3, 4], [9, 9], [0, 0])
    assert C.breedable_pair(np.ones(3, bool), [N, N, N], [3, 4, 5], [9, 9, 0], [0, 0, 0])   # 3·5 는 근친 아님


def _fake_rec(K, T=6, steps=12):
    """Minimal record for population_metrics (judge-like, Q = 4)."""
    Q = 4
    pop = np.zeros((T, K, Q, 3), np.int16)
    pop[..., 0, :] = [10, 2, 4]
    st = dict(deaths=np.zeros((K, 3, 4), np.int64), newborns=np.zeros((K, 3), np.int64), near_ties=np.zeros((K, 3), np.int64),
              alive_steps=np.ones((K, 3), np.int64))
    life = dict(blocked=np.zeros((K, Q, 3, L.N_BLOCK), np.int64), paired=np.zeros((K, Q, 3), np.int64),
                opportunities=np.zeros((K, Q, 3), np.int64), failed=np.zeros((K, Q, 3), np.int64), cancelled=np.zeros((K, Q, 3), np.int64))
    return dict(K=K, pop=pop, pop_t=np.arange(1, T + 1) * 2, steps=steps, final_pair=np.ones((K, 3), bool),
                start_counts=np.tile([10, 2, 4], (K, 1)), pair_hist=np.ones((2, K, 3), bool), st=st, life=life, births=[], deaths=[],
                food_end=np.zeros((K, 4)))


def test_24_coexistence_judgement():
    """공존 세계 몫 = 끝에 세 종 모두 번식할 수 있는 쌍, 준멸종 = 도중 쌍이 없어짐 또는 시작의 10% 아래, 첫 멸종은 중도 절단 중앙값."""
    r = _fake_rec(4)
    r["final_pair"][1, W_] = False                     # 짝 없는 늑대 한 마리만 남은 세계는 공존 아님
    r["pop"][3:, 2, 0, R_] = 0                          # 세계 2: 멧돼지가 결정 4 (스텝 8) 에 멸종
    r["final_pair"][2, R_] = False
    r["pair_hist"][0, 3, D_] = False                    # 세계 3: 도중에 사슴 쌍이 없던 때 → 준멸종 (끝은 공존)
    r["births"] = [dict(k=0, uid=50, t=0, sp=D_), dict(k=0, uid=51, t=0, sp=D_)]
    r["deaths"] = [dict(k=0, uid=50, t=100, cause="starve")]
    r["steps"] = 400
    p = C.population_metrics(r)
    assert p["coexist_worlds"] == [1, 0, 0, 1] and p["coexist_share"] == 0.5
    assert p["quasi_extinct_share"] == 0.75
    assert p["extinct_share"]["boar"] == 0.25 and p["first_extinction_median"]["boar"] == float("inf")
    assert p["newborn_300"]["deer"]["n"] == 2 and p["newborn_300"]["deer"]["starve"] == 0.5
    t = np.array([5.0, 8.0, 8.0, 20.0])
    assert C.km_median(t, np.array([True, True, True, False])) == 8.0
    assert C.km_median(t, np.zeros(4, bool)) == float("inf")


# --------------------------------------------------------------------------- 25 판정 시드 잠금


def test_25_judge_lock(tmp_path, brains_dir, cfg, jcfg):
    lock = tmp_path / "JUDGE_LOCK.json"
    paths = {f"{b}:{s}": str(brains_dir / f"{b}_{s}.npz") for b in "AB" for s in B.SPECIES}
    with pytest.raises(C.JudgeLockError):                       # 최종 두뇌 6 개를 다 적어야 한다
        C.judge_gate(lock, {k: v for k, v in paths.items() if k.startswith("A")}, cfg, jcfg, "judge", [44900])
    assert not lock.exists()
    L1 = C.judge_gate(lock, paths, cfg, jcfg, "judge", [44900, 44999])
    assert lock.exists() and len(L1["runs"]) == 1 and set(L1["brains"]) == set(C.BRAIN_KEYS)
    L2 = C.judge_gate(lock, paths, cfg, jcfg, "mixed", [44800, 44899])          # 같은 두뇌·설정 → 받고 기록
    assert len(L2["runs"]) == 2
    other = dict(paths)
    other["B:wolf"] = str(brains_dir / "A_wolf.npz")
    with pytest.raises(C.JudgeLockError):
        C.judge_gate(lock, other, cfg, jcfg, "judge", [44900])
    with pytest.raises(C.JudgeLockError):
        C.judge_gate(lock, paths, B.override(cfg, {"food": {"grass": {"regen_base": 0.0025}}}), jcfg, "judge", [44900])
    assert len(json.loads(lock.read_text(encoding="utf-8"))["runs"]) == 2


def test_25_lock_code_digest_mutex_and_brain_first(tmp_path, brains_dir, cfg, jcfg, monkeypatch):
    """Fix 단계: 잠금에 세계 코드 digest(줄 끝 정규화)가 들고 다르면 거부, 잠금 읽고-쓰기는 뮤텍스 파일 안에서(끝나면 지움),
    몸 해시 확인(두뇌 싣기)에 실패한 판정 실행은 잠금을 쓰지 않는다."""
    lock = tmp_path / "JUDGE_LOCK.json"
    paths = {f"{b}:{s}": str(brains_dir / f"{b}_{s}.npz") for b in "AB" for s in B.SPECIES}
    L1 = C.judge_gate(lock, paths, cfg, jcfg, "judge", [44900, 44999])
    assert L1["code_digest"] == C.code_digest() and len(L1["code_digest"]) == 64
    assert not lock.with_suffix(".lck").exists()
    monkeypatch.setattr(C, "code_digest", lambda: "0" * 64)
    with pytest.raises(C.JudgeLockError, match="world code"):
        C.judge_gate(lock, paths, cfg, jcfg, "judge", [44900])
    monkeypatch.undo()
    lock.with_suffix(".lck").write_text("held", encoding="utf-8")       # another judge part holds the mutex
    t0 = __import__("time").time()
    monkeypatch.setattr(C.time, "sleep", lambda s: (_ for _ in ()).throw(RuntimeError("waited")))
    with pytest.raises(RuntimeError, match="waited"):
        C.judge_gate(lock, paths, cfg, jcfg, "judge", [44900])
    monkeypatch.undo()
    lock.with_suffix(".lck").unlink()
    assert __import__("time").time() - t0 < 30
    # brain refused (load_brains raises) → no lock written
    lk2 = tmp_path / "L2.json"

    def refuse(*a, **k):
        raise ValueError("body hash differs")
    monkeypatch.setattr(C, "load_brains", refuse)
    with pytest.raises(ValueError, match="body hash"):
        EV.main(["judge", "--seeds", "44900", "44999", "--brain", *brain_args(brains_dir), "--lock", str(lk2), "--out", str(tmp_path)])
    assert not lk2.exists()


def test_c0_state_must_be_in_the_yaml(tmp_path, cfg, jcfg):
    """Fix 단계 검토 low: 보정 값(C0_STATE values·f_enabled)이 YAML 에 없으면 judge·mixed·check·league 가 거부한다."""
    sp = tmp_path / "C0_STATE.json"
    assert EV.check_c0_state(cfg, jcfg, "t", sp) is None                                # 보정 전 = 시운전
    # S′ 11-12: C0-6 은 보고만(고칠 값 없음) → 정하는 관문 C0-5 (땅속 재생 q) 로 본다
    sp.write_text(json.dumps(dict(values={"C0-5": 1.0, "C0-2": [0.90, 1.05]}, f_enabled=False)), encoding="utf-8")
    assert EV.check_c0_state(cfg, jcfg, "t", sp)["values"]["C0-5"] == 1.0
    sp.write_text(json.dumps(dict(values={"C0-5": 0.5}, f_enabled=False)), encoding="utf-8")
    with pytest.raises(SystemExit, match="C0-5"):
        EV.check_c0_state(cfg, jcfg, "t", sp)
    sp.write_text(json.dumps(dict(values={}, f_enabled=True)), encoding="utf-8")
    with pytest.raises(SystemExit, match="대비책 F"):
        EV.check_c0_state(cfg, jcfg, "t", sp)
    on = B.override(cfg, {"reward": {"fallback_f": {"enabled": True}}})
    assert EV.check_c0_state(on, on, "t", sp) is not None


def test_summary_tri_state_and_sentences():
    """Fix 단계 검토 low: J2 를 안 잰 것(2 시간 판 없음)은 실패가 아니라 '미판정', J1·J2 통과·J3 만 실패에도 문장이 있다."""
    assert EV._tri({"A": True, "B": True}) is True and EV._tri({"A": True, "B": False}) is False
    assert EV._tri({"A": True, "B": None}) is None and EV._tri({"A": False, "B": None}) is False and EV._tri({}) is None
    assert "J2 미판정" in EV.sentence(True, None, True, False, None)
    assert "함께 살지 못했다" in EV.sentence(True, False, None, False, None)
    assert "현실 범위 밖" in EV.sentence(True, True, False, False, None)
    assert EV.sentence(True, True, True, False, None).startswith("세 종이 각자 배운 두뇌로")
    assert EV.sentence(False, True, True, False, None).startswith("J1 실패")


def test_metric_definitions_switch():
    """Fix 단계 (검토 medium 둘) → 11-12 정함: 기본 사냥 시도 = strict (STATUS 0절 2 — test_r9_eval_s 가 셈을 본다). --hunt-def pair /
    episode / --block-def once 로 바꾸면 게이트 값이 그 정의를 쓴다. 다른 정의는 늘 함께 보고한다. (S′ 11-12: 기본값만 바뀜)"""
    hunts = [dict(k=0, wolf_uid=9, target_uid=t, target_sp=D_, t0=10, t1=40, n_close=8, ran=False, end="gap") for t in (1, 2, 3, 4)]
    kills = [dict(k=0, wolf_uid=9, prey_uid=2, t=30, prey_sp=D_, wolf_act=B.WALK_FIRST, prey_af=1.0, juv_share=0.0)]
    rec = dict(K=1, hunts=hunts, kills=kills, st=dict(alive_steps=np.array([[0, 900, 0]])), att=np.zeros((1, 2)))
    assert C.DEFS == {"hunt": "strict", "block": "scan"}
    try:
        j = C.j3_metrics(rec)
        assert j["hunt_def"] == "strict" and j["strict_attempts"] == 1                  # 구간에 hunting 표시가 없으면 사냥 구간 아님 → 구간 밖 걷기 죽임 1
        C.DEFS["hunt"] = "pair"
        j = C.j3_metrics(rec)
        assert j["hunt_def"] == "pair" and j["success_rate"] == pytest.approx(0.25) and j["attempts"] == 4
        assert j["success_rate_episode"] == pytest.approx(1.0) and j["episodes"] == 1
        C.DEFS["hunt"] = "episode"
        j = C.j3_metrics(rec)
        assert j["hunt_def"] == "episode" and j["success_rate"] == pytest.approx(1.0) and j["attempts"] == 1
        assert j["success_rate_pair"] == pytest.approx(0.25)
        K, Q = 1, 4
        bl = np.zeros((K, Q, 3, L.N_BLOCK), np.int64)
        bo = np.zeros_like(bl)
        bl[0, 0, D_, L.BLOCK_ONE_PENDING], bo[0, 0, D_, L.BLOCK_ONE_PENDING] = 6, 1
        life = dict(blocked=bl, blocked_once=bo, paired=np.full((K, Q, 3), 0, np.int64))
        life["paired"][0, 0, D_] = 3
        assert C.block_share(life)["content"].sum() == 6
        C.DEFS["block"] = "once"
        assert C.block_share(life)["content"].sum() == 1 and C.block_share(life, "scan")["content"].sum() == 6
    finally:
        C.DEFS.update(hunt="strict", block="scan")


def test_blocked_once_counts_a_pending_pair_once(jcfg):
    """r9_life blocked_once ≤ blocked; a scan-time one-pending block is counted at most once per pending pair (≤ pairs made);
    delivery-time reasons are counted the same in both (실제 판정 세계, 규칙 사슴·멧돼지, 늑대 없음)."""
    c = B.override(jcfg, {"judge": {"wolf_packs": {"per_pack": 0}}})
    w = R9World(c, [44379])
    for k in range(w.K):
        for sp, n in ((D_, "RULE_DEER"), (W_, "RULE_WOLF"), (R_, "RULE_BOAR")):
            w.set_controller(k, sp, BR.Controller(BR.make_rule(n, c), stochastic=False, label=n))
    for _ in range(900):
        w.step(w.decide())
    lf = L.life_stats(w.life)
    bl, bo = lf["blocked"], lf["blocked_once"]
    assert (bo <= bl).all()
    op = L.BLOCK_ONE_PENDING
    assert bl[..., op].sum() > bo[..., op].sum() > 0                     # the literal count repeats, the once count does not
    assert (bo[..., op] <= lf["paired"]).all()
    for r in (L.BLOCK_WOLF_BUDGET, L.BLOCK_FOOD, L.BLOCK_SLOT_CAP):
        assert (bo[..., r] == bl[..., r]).all()


def test_25_judge_seed_guards(tmp_path, brains_dir):
    with pytest.raises(C.JudgeSeedError):
        C.assert_not_judge_seeds([44200, 44850], "check")
    C.assert_not_judge_seeds([44799, 45000, 44350], "check")
    assert C.judge_seed_mode([44900, 44901], C.SEED_RANGES["judge_j2"], "judge") is True
    assert C.judge_seed_mode([44350], C.SEED_RANGES["judge_j2"], "judge") is False
    with pytest.raises(C.JudgeSeedError):
        C.judge_seed_mode([44899, 44900], C.SEED_RANGES["judge_j2"], "judge")
    with pytest.raises(C.JudgeSeedError):
        C.judge_seed_mode([44850], C.SEED_RANGES["judge_j2"], "judge")         # J1 범위는 judge 가 못 씀
    o = ["--out", str(tmp_path)]
    for argv in (["check", "--round", "2", "--seeds", "44850", "44851"] + o,
                 ["check", "--round", "2", "--preview-seeds", "44900", "44901"] + o,
                 ["calibrate", "--gates", "C0-6", "--seeds-train", "44800", "44801", "--no-state"] + o,
                 ["calibrate", "--gates", "C0-7", "--seeds-judge", "44990", "44991", "--no-state"] + o,
                 ["leak", "--seeds", "44805", "44806"] + o,
                 ["scenes", "--seeds", "44901", "44902"] + o,
                 ["anomaly", "--seeds", "44801", "44802"] + o):
        with pytest.raises(C.JudgeSeedError):
            EV.main(argv)
    # judge·mixed 는 판정 시드에서 등록한 크기를 줄이거나 --set 을 받지 않는다 (잠금 전에 거부 — 세계를 돌리지 않음)
    lk = ["--lock", str(tmp_path / "L.json")]
    with pytest.raises(C.JudgeSeedError):
        EV.main(["judge", "--seeds", "44900", "44999", "--steps", "100", "--brain", *brain_args(brains_dir)] + o + lk)
    with pytest.raises(C.JudgeSeedError):
        EV.main(["judge", "--seeds", "44900", "44909", "--brain", *brain_args(brains_dir)] + o + lk)
    with pytest.raises(C.JudgeSeedError):
        EV.main(["mixed", "--seeds", "44800", "44899", "--set", "food.grass.regen_base=0.003", "--brain", *brain_args(brains_dir)]
                + o + lk)
    assert not (tmp_path / "L.json").exists()
    # Fix 단계: judge·mixed 는 --seeds 를 꼭 적는다 (기본값이 판정 시드라 시운전이 잠금을 쓰던 길), 판정 시드에서 --lock 을 임시
    # 폴더 밖으로 바꾸지 못한다 (다른 잠금 파일로 같은 시드를 다시 쓰던 길) — 둘 다 세계를 돌리기 전에 거부
    for cmd in ("judge", "mixed"):
        with pytest.raises(SystemExit):
            EV.main([cmd, "--brain", *brain_args(brains_dir)] + o)
    outside = EVAL_DIR / "eval" / "_test_other_lock.json"
    with pytest.raises(C.JudgeSeedError):
        EV.main(["judge", "--seeds", "44900", "44999", "--brain", *brain_args(brains_dir), "--lock", str(outside)] + o)
    assert not outside.exists()
    import r9_replay as RP
    if not (EVAL_DIR / "eval" / "judge.json").exists():
        with pytest.raises(C.JudgeSeedError):
            RP.guard_seed(44950)
    try:                                                       # 학습 코드(학습 줄기 에이전트 것)도 판정 시드를 거부한다
        from env_v2.r9_vec_env import check_train_seeds
    except ImportError:
        return
    with pytest.raises(ValueError):
        check_train_seeds([44000, 44999])


# --------------------------------------------------------------------------- 평가 도구 성질


def test_eval_chunk_independent(cfg, jcfg):
    """세계를 몇 개씩 묶어 돌려도 평가 기록이 같다 (세계 난수·평가 난수가 세계마다, 고정 두뇌는 세계마다 같은 모양 블록)."""
    for c, seeds in ((cfg, [44370, 44371, 44372]), (jcfg, [44373, 44374])):
        fn = EV.spec_fn(c, EV.rule_specs(), {})
        a = C.run(c, seeds, 160, fn, scenes=True, chunk=None)
        b = C.run(c, seeds, 160, fn, scenes=True, chunk=1)
        def js(x):                                   # NaN == NaN in the text form; event order differs between batch layouts
            return sorted(json.dumps(C.to_jsonable(e), sort_keys=True) for e in x)
        assert np.array_equal(a["pop"], b["pop"]) and js(a["kills"]) == js(b["kills"]) and js(a["hunts"]) == js(b["hunts"])
        assert len(a["hunts"]) > 0 and (len(a["kills"]) > 0 or c is jcfg)
        for k in a["st"]:
            assert np.array_equal(a["st"][k], b["st"][k]), k
        for k in ("an_shield", "sc_sated", "sc_disp", "ehist", "elig", "final_pair"):
            assert np.array_equal(a[k], b[k]), k


def test_bootstrap_and_split_assignment():
    x = np.array([0.0, 1.0, 1.0, 0.0, 1.0])
    assert C.boot_mean(x) == C.boot_mean(x) and C.boot_mean(x)[0] == 0.6
    lo, hi = C.boot_ratio(np.array([1.0, 2.0, 3.0]), np.array([2.0, 2.0, 2.0]))[1]
    assert lo <= 1.0 <= hi
    # 8-1 배정: 층(성별 × 어린/성체)마다 반반, 전체도 |차| ≤ 1
    rng = np.random.default_rng(44380)
    for seed in range(44380, 44390):
        n = int(rng.integers(2, 30))
        strata = rng.integers(0, 4, n)
        side = C.founder_split(np.arange(1, n + 1), strata, seed)
        assert abs(int(side.sum()) - int((~side).sum())) <= 1
        for s in range(4):
            m = strata == s
            assert abs(int(side[m].sum()) - int((~side[m]).sum())) <= 1
    for seed in range(44390, 44399):
        side = C.founder_split([1, 2], [3, 1], seed)                       # 늑대 2 마리, 다른 층이어도 하나씩
        assert side.sum() == 1
    assert C.respawn_side((2, 3), (5, 5), 0.9) is True and C.respawn_side((3, 3), (6, 5), 0.1) is False
    assert C.respawn_side((3, 3), (5, 5), 0.2) is True


def test_split_brain_mixed_herd(cfg):
    """J1 섞인 무리: 두 두뇌가 칸마다 갈리고, 다시 난 개체도 층 균형으로 배정되며, 개체당 보상 셈이 세계 보상과 맞는다."""
    seeds = [44375, 44376]
    rec = C.run(B.override(cfg, EV.EVAL_FACING), seeds, 600, EV.spec_fn(cfg, EV.rule_specs(), {}), scenes=False,
                split=dict(sp=D_, first=C.rule_brain("ALWAYS_EAT", cfg, D_), second=C.rule_brain("RULE_DEER", cfg, D_)))
    s = C.split_metrics(rec)
    assert s["steps"][0] > 0 and s["steps"][1] > 0
    assert abs(s["steps"][0] - s["steps"][1]) / (s["steps"][0] + s["steps"][1]) < 0.1
    # F 꺼짐: 전체 = 번식 뺀 것 + 10 × 출산
    F = {n: i for i, n in enumerate(C.Recorder.ACC_FIELDS)}
    A = rec["acc"][:, D_]
    assert np.allclose(A[..., F["r_off"]], A[..., F["r_nb"]] + 10.0 * A[..., F["births"]])
    assert np.allclose(rec["rew_sp"][:, D_], A[..., F["r_off"]].sum(1))
    # ALWAYS_EAT 쪽은 은신처로 안 간다 → 규칙 쪽보다 먹은 E 가 많거나 같다(먹기만 함)
    assert s["eaten"]["first"] >= 0.0


# --------------------------------------------------------------------------- 하위 명령이 작은 크기로 끝까지


def test_subcommands_small(tmp_path, brains_dir, monkeypatch):
    monkeypatch.setattr(EV, "OUT_CALIB", tmp_path / "calib")      # hermetic: a repo C0_STATE.json must not change this test
    o = str(tmp_path)
    br = brain_args(brains_dir)
    assert EV.main(["calibrate", "--phase", "pick", "--gates", "C0-6", "--cands", "0.012", "--seeds-train", "44380", "44381",
                    "--steps-train", "200", "--out", o]) in (0, 2)
    st = json.loads((tmp_path / "C0_STATE.json").read_text(encoding="utf-8"))
    assert st["history"][-1]["gates"] == ["C0-6"]
    assert (tmp_path / "C0_STATUS_append.md").exists()
    assert EV.main(["calibrate", "--phase", "pick", "--gates", "C0-4", "C0-11", "--seeds-train", "44382", "44383", "--steps-train", "200",
                    "--steps-c011", "200", "--out", o, "--tag", "_b", "--state", str(tmp_path / "S2.json")]) in (0, 2)
    r = json.loads((tmp_path / "C0_pick_b.json").read_text(encoding="utf-8"))
    assert [x["gate"] for x in r["results"]][0] == "C0-4"
    assert EV.main(["calibrate", "--phase", "confirm", "--gates", "C0-7b", "--seeds-judge", "44384", "44384", "--steps-judge", "200",
                    "--out", o, "--state", str(tmp_path / "S3.json")]) in (0, 2)
    assert EV.main(["calibrate", "--gates", "C0-10", "--c010-commands", "--out", o]) == 0
    assert EV.main(["leak", "--seeds", "44385", "44388", "--steps", "200", "--out", o]) == 0
    leak = json.loads((tmp_path / "leak.json").read_text(encoding="utf-8"))
    assert leak["invariance"]["sp_poison_same"] and leak["invariance"]["kin_perm_same"] and leak["invariance"]["refresh_same"]
    assert EV.main(["mixed", "--seeds", "44386", "44387", "--steps", "200", "--brain", *br, "--out", o]) == 0
    mx = json.loads((tmp_path / "mixed.json").read_text(encoding="utf-8"))
    assert mx["judged"] is False and set(mx["branches"]) == {"A", "B"} and mx["J1"]["complete"]
    assert EV.main(["judge", "--seeds", "44389", "44390", "--steps", "200", "--steps-long", "200", "--long", "--batches", "L_A", "L_B",
                    "RULE", "--variants", "L0", "LS", "--brain", *br, "--out", o, "--chunk", "1"]) == 0
    jd = json.loads((tmp_path / "judge.json").read_text(encoding="utf-8"))
    assert jd["judged"] is False and set(jd["batches"]) == {"L_A", "L_B", "RULE"} and set(jd["long"]) == {"L_A", "L_B"}
    assert set(jd["variants"]) == {"L0", "LS"} and "paired_coexist_diff" in jd["variants"]["L0"]["L_A"]
    assert set(jd["verdict"]["branches"]) == {"A", "B"}
    assert (tmp_path / "judge_pop.npz").exists()
    assert jd["metric_defs"] == {"hunt": "strict", "block": "scan"}
    assert "success_rate_strict" in jd["batches"]["L_A"]["j3"] and "end_worlds" in jd["batches"]["L_A"]["population"]
    assert jd["verdict"]["branches"]["A"]["rule_backed"] in (True, False)        # L0 판이 있으면 L0 짝 비교 (11-12)
    assert "block_share_once" in jd["batches"]["L_A"]["population"] and "success_rate_pair" in jd["batches"]["L_A"]["j3"]
    assert EV.main(["summary", "--out", o]) == 0
    sm = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert sm["judged"] is False and "sentence" in sm
    # judge parts in separate processes (STATUS 판정 계획) → judge-merge
    jargs = ["judge", "--seeds", "44389", "44390", "--steps", "200", "--brain", *br, "--out", o, "--chunk", "2"]
    assert EV.main(jargs + ["--batches", "RULE", "--tag", "_p1"]) == 0
    assert EV.main(jargs + ["--batches", "L_A", "--tag", "_p2"]) == 0
    assert EV.main(jargs + ["--long-only", "--long", "--steps-long", "200", "--for-branches", "A", "--variants", "L0", "--tag", "_p3"]) == 0
    p3 = json.loads((tmp_path / "judge_p3.json").read_text(encoding="utf-8"))
    assert p3["batches"] == {} and set(p3["long"]) == {"L_A"} and set(p3["variants"]["L0"]) == {"L_A"}
    assert EV.main(["judge-merge", "--parts", "_p1", "_p2", "_p3", "--out", o, "--tag", "_m"]) == 0
    jm = json.loads((tmp_path / "judge_m.json").read_text(encoding="utf-8"))
    assert set(jm["batches"]) == {"RULE", "L_A"} and set(jm["long"]) == {"L_A"} and "A" in jm["verdict"]["branches"]
    assert "paired_coexist_diff" in jm["variants"]["L0"]["L_A"] and jm["verdict"]["branches"]["A"]["J2"] is not None
    assert jm["batches"]["RULE"]["population"]["coexist_worlds"] == jd["batches"]["RULE"]["population"]["coexist_worlds"]
    with pytest.raises(SystemExit):
        EV.main(["judge-merge", "--parts", "_p1", "_p1", "--out", o, "--tag", "_bad"])
    for nm in ("scenes", "anomaly"):
        assert EV.main([nm, "--form", "train", "--seeds", "44391", "44392", "--steps", "200", "--out", o]) == 0
    an = json.loads((tmp_path / "anomaly_train.json").read_text(encoding="utf-8"))
    assert set(an["anomaly"]["flags"]) >= {"corner", "wall_drive", "shield", "arena", "no_hunt"}
    ck = ["--seeds", "44393", "44394", "--steps", "160", "--cross-seeds", "44395", "44396", "--steps-cross", "160",
          "--preview-seeds", "44397", "44397", "--steps-preview", "160", "--branches", "A", "--brain", *br, "--out", o]
    assert EV.main(["check", "--round", "2", *ck]) == 0
    assert EV.main(["check", "--round", "4", *ck]) == 0                   # 직전 점검(2 바퀴)을 점검 폴더에서 찾는다
    c4 = json.loads((tmp_path / "round04_A.json").read_text(encoding="utf-8"))
    sig = c4["branches"]["A"]["signals"]
    assert sig["forgetting"] and sig["stability"] is not None and "prev|now" in c4["branches"]["A"]["cross"]
    assert c4["stop"]["stop"] is False


def test_plot_and_replay_files(tmp_path, cfg):
    import plot_r9
    import r9_replay as RP

    rec = RP.record(B.override(cfg, EV.EVAL_FACING), 44398, 200, EV.rule_specs(), {})
    out = RP.draw(rec, tmp_path / "r.png", "시험")
    assert out.exists() and out.stat().st_size > 1000
    logs = tmp_path / "logs"
    logs.mkdir()
    rows = [dict(species=sp, branch=b, round=r_, timesteps=t * 1000, bite_per_1k=0.1, E_median=0.5)
            for b in "AB" for sp in B.SPECIES for r_ in (0, 1) for t in (1, 2)]
    (logs / "x.log.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", encoding="utf-8")
    assert plot_r9.main(["curves", "--logs", str(logs), "--out", str(tmp_path / "c.png")]) == 0
    x, bounds = plot_r9.cumulative_x([r for r in rows if r["branch"] == "A" and r["species"] == "deer"])
    assert x.tolist() == [1000.0, 2000.0, 3000.0, 4000.0] and bounds == [2000.0]
    np.savez(tmp_path / "p.npz", L_A=np.ones((5, 2, 3)), L_A__t=np.arange(5) * 2)
    assert plot_r9.main(["pop", "--npz", str(tmp_path / "p.npz"), "--out", str(tmp_path / "p.png")]) == 0
