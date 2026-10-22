"""언리얼 통합 무대 거울 — 기능 integrated_stage(26)·설정 configs/v3_unreal_mirror.yaml·실행기 results/v3/mirror (10-15 사용자 '언리얼에서 돌리는 게
파이썬에서 돌리는 것과 얼마나 비슷한지 확인'. 정의·식·C++ 출처는 env_v2/world.py 모듈 docstring '통합 무대').

비트 동일: 이 단계 직전 커밋(1d388af 를 git archive 로 푼 사본)의 코드와 기존 설정(v3_r1_on·v3_real1_night_on·v3_real1_on·v3_r3_on)의 궤적·통계·
v1 난수 상태·기능 스트림이 같다(출시 두뇌 R1b 롤아웃 포함 — 리스폰을 `_spawn_slots` 로 떼어 낸 뒤에도 같다). 거울 설정의 integrated_stage 블록을
끔 값(respawn true, 나머지 null)으로 켜면 직전 코드의 '블록이 없는 거울 설정'과 같다.
규칙 단위 시험: 부활 없음 — 죽은 슬롯은 돌아오지 않고(위치·방향·에너지가 멈춘다) 다음 스텝부터 동족·늑대 표적·포획·먹이 수요·번식·밤잠 '사슴
근처'에서 빠진다, 굶음은 잡히지 않은 산 개체만 한 번 센다, 학습(vec_env)은 이 세계를 받지 않는다. 시작 위상·은신처 quad·늑대 구성·무대 시작 배치·
시작 방향·피식 EMA 분모. 실행기 연기 시험(세계 2개 × 30스텝)과 견주기 도구의 읽기. 시드는 탐색 32070~32089 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import importlib.util
import io
import json
import math
import subprocess
import sys
import tarfile

import numpy as np
import pytest
import yaml

from env.config import ROOT
from env_v2 import features as F
from env_v2 import rep_policy as rp
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import PT_CHASER, PT_STALKER, World

CFG = ROOT / "configs"
MIRROR = CFG / "v3_unreal_mirror.yaml"
BASE = CFG / "v3_real1_night_on.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "1d388af"              # 통합 무대 거울 직전 커밋(R3 관문 보정 1 문서) — 비트 동일 기준
MIRROR_DIR = ROOT / "results" / "v3" / "mirror"
OFF = dict(enabled=True, respawn=True, ema_den=None, day_offset=None, cover_layout=None, cover_count=None, cover_r_frac=None,
           wolf_kinds=None, start_layout=None, wolf_corner_frac=None, wolf_gap=None, deer_wolf_gap=None, deer_margin=None,
           deer_spacing=None, head_layout=None)
KEYS = ("pos", "head", "energy", "pred_pos", "pred_head", "food", "food_cap", "regen_field", "vel", "pred_cd", "pred_vel",
        "behavior", "beh_phase", "beh_steps", "beh_seq", "stalk_state", "player_mode", "pred_asleep", "cov_c", "cov_r")
STATS = ("stats", "gait_stats", "daynight_stats", "pred_sleep_stats", "repertoire_stats", "threats_stats", "realism_stats",
         "r3_stats")

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _raw(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _without(cfg, name):
    f = {k: dict(v) for k, v in cfg.v2["features"].items() if k != name}
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _mirror(**ist):
    cfg = load_v2_config(MIRROR)
    return _with(cfg, integrated_stage=ist) if ist else cfg


def _masked_rand(w, seed):
    """세계 설정의 허용 목록 마스크 안에서 고르게 뽑는 정책(판정·학습 경로와 같은 마스크)."""
    params = rp.rep_params(w.cfg)
    rng = np.random.default_rng([seed, 7])

    def pol(obs):
        m = rp.action_mask(w, obs, params)
        return rp.sample_masked(np.ones(m.shape), m, rng.random(len(obs))).astype(np.float64)[:, None]
    return pol


def _graze(w):
    return np.full((w.N, 1), float(rep.GRAZE))


def _run_pair(wa, wb, pa, pb, steps):
    for _ in range(steps):
        oa, ob = wa.observe(), wb.observe()
        np.testing.assert_array_equal(oa, ob)
        for x, y in zip(wa.step(pa(oa)), wb.step(pb(ob))):
            np.testing.assert_array_equal(x, y)
    for name in STATS:
        try:
            sa = getattr(wa, name)()
        except (ValueError, AttributeError):
            continue
        sb = getattr(wb, name)()
        assert sa.keys() == sb.keys()
        for k in sa:
            assert sa[k] == sb[k] or (isinstance(sa[k], float) and math.isnan(sa[k]) and math.isnan(sb[k])), (name, k)
    for k in KEYS:
        if hasattr(wa, k):
            np.testing.assert_array_equal(getattr(wa, k), getattr(wb, k), err_msg=k)
    assert wa.rng.bit_generator.state == wb.rng.bit_generator.state
    assert {n for n, _ in wa._feature_rngs} == {n for n, _ in wb._feature_rngs}


# --------------------------------------------------------------------- #
# 등록부·설정
# --------------------------------------------------------------------- #


def test_registry_and_config():
    assert F.FEATURE_IDS["integrated_stage"] == 26 and "integrated_stage" in F.IMPLEMENTED
    # 새 기능이라 계수는 모두 적는다. 선택 키는 10-18 R4 학습 보충 둘뿐이다(끔 값 = 지금까지 그대로, 거울 설정에는 없다 — tests/test_r4_train.py)
    assert dict(F.OPTIONAL_KEYS["integrated_stage"]) == {"respawn_safe_r": None, "respawn_tries": 64}
    block = _raw(MIRROR)["features"]["integrated_stage"]
    assert not set(F.OPTIONAL_KEYS["integrated_stage"]) & set(block)
    assert F.PARAM_KEYS["integrated_stage"] == frozenset(block) - {"enabled"}
    assert set(OFF) == set(block)
    cfg = load_v2_config(MIRROR)
    assert cfg.N == 128 and cfg.pred_eat_cd == 38
    assert cfg.rand["world_size"] == [60.0, 60.0] and cfg.rand["predator_count"] == [2, 2]
    assert cfg.rand["pred_speed_mult"] == [0.8, 0.8] and cfg.rand["ranged_frac"] == [0.0, 0.0]
    assert cfg.rand["food_regen_mult"] == [1.0, 1.0]
    f = cfg.v2["features"]
    assert f["daynight"]["periods"] == [900] and f["daynight"]["fixed_day_frac"] == 0.0
    assert f["pred_sleep"]["nocturnal_frac"] == [0.0, 0.0]
    assert f["threats"]["player_frac"] == 0.0 and f["threats"]["eat_in_place"] is True
    assert f["realism_night"]["enabled"] is True
    assert rp.rep_params(cfg)["allowed"] == ("graze", "flee", "hide")
    # 거울 설정의 나머지 블록은 v3_real1_night_on 과 같다(바꾼 키만 다르다)
    base, mir = _raw(BASE)["features"], _raw(MIRROR)["features"]
    assert set(mir) - set(base) == {"integrated_stage"} and set(base) <= set(mir)
    changed = {("daynight", "periods"), ("pred_sleep", "nocturnal_frac"), ("threats", "player_frac"), ("threats", "eat_in_place")}
    for name, b in base.items():
        for k in set(b) | set(mir[name]):
            if (name, k) not in changed:
                assert mir[name][k] == b[k], (name, k)


def test_params_validation():
    with pytest.raises(ValueError, match="repertoire·threats"):
        World(_with(_mirror(), threats=dict(enabled=False), integrated_stage=dict(wolf_kinds=None)), seeds=[32070])
    for key, bad in (("respawn", 0), ("cover_layout", "hex"), ("wolf_kinds", "random"), ("start_layout", "map"),
                     ("head_layout", "north"), ("ema_den", 0), ("day_offset", -1), ("cover_count", 0), ("cover_r_frac", 0.0),
                     ("wolf_corner_frac", 0.6), ("deer_spacing", -1.0)):
        with pytest.raises(ValueError):
            World(_mirror(**{key: bad}), seeds=[32070])
    with pytest.raises(ValueError, match="계수"):
        F.parse_features({"integrated_stage": {k: v for k, v in OFF.items() if k != "head_layout"}})
    with pytest.raises(ValueError, match="오타"):
        F.parse_features({"integrated_stage": dict(OFF, respwan=False)})
    # 부활 없음은 죽은 개체를 빼는 규칙이 없는 경보·노려보기와 함께 켜지 못한다
    r2 = load_v2_config(CFG / "v3_r2_on.yaml")
    with pytest.raises(ValueError, match="alarm|stare_down"):
        World(_with(r2, integrated_stage=dict(OFF, respawn=False)), seeds=[32070])
    # 부활 있는 세계(끔 값)는 경보 세계에도 얹을 수 있다
    World(_with(r2, integrated_stage=OFF), seeds=[32070])


# --------------------------------------------------------------------- #
# 비트 동일
# --------------------------------------------------------------------- #


def test_all_off_block_equals_no_block():
    """같은 프로세스: 거울 설정의 블록을 끔 값으로 켜면 블록을 지운 거울 설정과 비트 동일이다(R1b 세계·무작위 마스크 정책)."""
    a = _without(load_v2_config(MIRROR), "integrated_stage")
    b = _with(a, integrated_stage=OFF)
    wa, wb = World(a, seeds=[32071]), World(b, seeds=[32071])
    assert wa._ist is None and wb._ist is not None and wb.alive is None
    _run_pair(wa, wb, _masked_rand(wa, 1), _masked_rand(wb, 1), 400)


TRACE_SRC = r'''
import hashlib, json, sys
sys.path.insert(0, ".")
import env.torch_init
import numpy as np
from env_v2 import rollout as ro
from env_v2.config import load_v2_config
from env_v2.world import World
KEYS = %(keys)r
STATS = %(stats)r


def run(job):
    cfg = load_v2_config(job["config"])
    if job.get("v1"):
        cfg = cfg.replace(**job["v1"])
    f = {k: dict(v) for k, v in cfg.v2["features"].items() if k not in job.get("drop", [])}
    for n, kw in (job.get("set") or {}).items():
        f[n] = dict(f.get(n, {}), **kw)
    cfg = cfg.replace(v2=dict(cfg.v2, features=f))
    w = World(cfg, seeds=[job["seed"]])
    if job["policy"] == "rand":
        rng = np.random.default_rng(job["seed"] + 7)
        pol = lambda o: rng.integers(0, 5, (len(o), 1)).astype(np.float64)
    elif job["policy"] == "rbase":
        import repertoire_rules as rr
        pol = ro.build_policy(rr.rule_spec(cfg, 4.0, 0.9), job["seed"])
    else:
        pol = ro.build_policy({"kind": "rep_learned", "path": job["model"]}, job["seed"])
    ro.forward_bind(pol, w)
    hs = []
    for _ in range(job["steps"]):
        obs = w.observe()
        a = np.asarray(pol(obs), dtype=np.float64)
        res = w.step(a)
        h = hashlib.sha1()
        for x in (obs, a) + tuple(res):
            h.update(np.ascontiguousarray(x).tobytes())
        for k in KEYS:
            if hasattr(w, k):
                h.update(np.ascontiguousarray(getattr(w, k)).tobytes())
        hs.append(h.hexdigest()[:16])
    st = {}
    for n in STATS:
        try:
            st[n] = {k: (None if v != v else v) for k, v in getattr(w, n)().items()}
        except (ValueError, AttributeError):
            pass
    return dict(hashes=hs, stats=st, rng=str(w.rng.bit_generator.state), obs_names=list(w.obs_names),
                streams=sorted(map(str, w._feature_rngs)))


jobs = json.loads(open(sys.argv[1], encoding="utf-8").read())
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps([run(j) for j in jobs]))
'''


def _archive(tmp_path, commit=BASE_COMMIT):
    """커밋 commit 의 herbivore_rl 일부를 tmp 에 푼다. git 이나 커밋이 없으면 None.
    10-22: 사본의 env_v2/world.py 동족 무리 중심·분리 두 줄만 지금 코드와 같은 j 차례 합으로 바꾼다(tests/kin_seq.py — 옛 행렬곱은 끝 비트가 달라
    수백 스텝 뒤 궤적이 갈린다). 이 파일을 함께 쓰는 비트 동일 시험(야생·장애물·R4·R5 등)이 모두 같은 사본을 받는다."""
    import kin_seq

    paths = [f"herbivore_rl/{p}" for p in ("env", "env_v2", "policies", "configs", "repertoire_rules.py")]
    try:
        out = subprocess.run(["git", "archive", commit] + paths, cwd=ROOT.parent, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    with tarfile.open(fileobj=io.BytesIO(out.stdout)) as tf:
        tf.extractall(tmp_path / "base", **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return kin_seq.patch_tree(tmp_path / "base" / "herbivore_rl")


def test_bit_identical_to_pre_mirror_code(tmp_path):
    """기존 세계(v3_r1_on·v3_real1_night_on·v3_real1_on·v3_r3_on, 리스폰이 잦은 N 16·맵 60 판 포함)는 직전 코드와 궤적(스텝마다 관측·행동·
    보상·사망·terminal_obs·상태 지문)·통계·v1 난수 상태·관측 이름·기능 스트림이 같다(R1b 롤아웃 포함). 거울 설정의 블록을 끔 값으로 켠 세계는 직전
    코드의 블록 없는 거울 설정과 같다(직전 코드는 integrated_stage 를 모른다 — 블록을 지워 돌린다)."""
    old_root = _archive(tmp_path)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    raw = _raw(MIRROR)
    del raw["features"]["integrated_stage"]               # 직전 코드는 이 기능 이름을 모른다 — 블록을 뺀 같은 설정을 놓는다
    (old_root / "configs" / "v3_unreal_mirror.yaml").write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    script = tmp_path / "trace.py"
    script.write_text(TRACE_SRC % dict(keys=KEYS, stats=STATS), encoding="utf-8")
    small = {"N": 16, "rand": dict(load_v2_config(CFG / "v3_r1_on.yaml").rand, world_size=[60.0, 60.0])}
    jobs = [dict(config="configs/v3_r1_on.yaml", seed=32072, steps=250, policy="rand"),
            dict(config="configs/v3_real1_night_on.yaml", seed=32073, steps=250, policy="rbase"),
            dict(config="configs/v3_real1_on.yaml", seed=32074, steps=250, policy="rand"),
            dict(config="configs/v3_r3_on.yaml", seed=32075, steps=250, policy="rand"),
            dict(config="configs/v3_r3_on.yaml", seed=32076, steps=300, policy="rand", v1=small)]
    if R1_MODEL.exists():
        jobs.append(dict(config="configs/v3_real1_night_on.yaml", seed=32077, steps=200, policy="model", model=str(R1_MODEL)))
        jobs.append(dict(config="configs/v3_r3_on.yaml", seed=32078, steps=200, policy="model", model=str(R1_MODEL)))
    old = [dict(j) for j in jobs]
    new = [dict(j) for j in jobs]
    for seed, pol in ((32079, "rand"), (32080, "model")):
        if pol == "model" and not R1_MODEL.exists():
            continue
        j = dict(config="configs/v3_unreal_mirror.yaml", seed=seed, steps=300, policy=pol, model=str(R1_MODEL))
        old.append(dict(j))
        new.append(dict(j, set={"integrated_stage": OFF}))
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
# 무대 배치·위상·은신처·늑대 구성
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("seed,n", [(32081, 128), (32082, 64), (32083, 16)])
def test_stage_layout(seed, n):
    w = World(load_v2_config(MIRROR).replace(N=n), seeds=[seed])
    assert w.size == 60.0 and w.M == 2 and w.N == n and not w.pred_is_player.any() and not w.pred_ranged.any()
    # (o) 늑대 구성: 슬롯 0 잠행, 1 추격, 모두 주행성·같은 속력(사슴 뛰기 × 0.8)·근접 포획 거리
    assert w.pred_type.tolist() == [PT_STALKER, PT_CHASER] and not w.pred_nocturnal.any()
    np.testing.assert_allclose(w.pred_speed, w.cfg.herb_speed * 0.8)
    assert (w.pred_catch_r == w.cfg.pred_melee_catch_r).all() and w.threat_p_stalk == 0.5
    # (m) 시작 위상: t = 0 이 새벽 전환 d = 0.5, 하루 900, 박명 45. 주행성 늑대는 자고 시작한다
    assert (w.dn_period, w.dn_offset, w.dn_tw, w.dark) == (900, 0, 45, 0.5) and w.pred_asleep.all()
    # (n) 은신처 quad: 1/4·3/4 지점, 반경 6, 은신처 셀 = 셀 중심이 원 안, 재생 0.3 배
    np.testing.assert_allclose(w.cov_c, [[45, 45], [15, 45], [15, 15], [45, 15]], atol=1e-9)
    assert (w.cov_r == 6.0).all()
    cc = np.zeros_like(w.cover_cell)
    for (x, y), r in zip(w.cov_c, w.cov_r):
        cc |= (w._cell_x - x) ** 2 + (w._cell_y - y) ** 2 <= r * r
    assert (w.cover_cell == cc).all() and abs(w.cover_frac_actual - cc.mean()) < 1e-15
    np.testing.assert_array_equal(w.regen_field, w.cfg.food_regen_base * np.where(cc, w.cfg.food_cover_regen_mult, 1.0))
    # (p) 시작 배치: 늑대 (54, 54)·(6, 6), 사슴 [1.5, 58.5]², 늑대에게서 14.5 이상, 서로 0.75 이상
    assert w.stage_complete is True
    np.testing.assert_allclose(w.pred_pos, [[54.0, 54.0], [6.0, 6.0]])
    assert w.pos.min() >= 1.5 and w.pos.max() <= 58.5
    d_w = np.sqrt(((w.pos[:, None] - w.pred_pos[None]) ** 2).sum(-1))
    assert d_w.min() >= 14.5
    d = np.sqrt(((w.pos[:, None] - w.pos[None]) ** 2).sum(-1))
    d[np.arange(n), np.arange(n)] = np.inf
    assert d.min() >= 0.75
    # (q) 시작 방향: 순번 × 2.399963, 늑대는 + 2
    a = np.arange(n) * 2.399963
    np.testing.assert_allclose(w.head, np.c_[np.cos(a), np.sin(a)])
    b = (np.arange(2) + 2) * 2.399963
    np.testing.assert_allclose(w.pred_head, np.c_[np.cos(b), np.sin(b)])
    # 자기 스트림 part 0 만 쓴다(늑대는 모서리라 후보를 뽑지 않고 사슴 후보만 뽑는다)
    assert [k for k in w._feature_rngs if k[0] == "integrated_stage"] == [("integrated_stage", 0)]
    assert w.alive.all() and (w.death_t == -1).all() and (w.death_cause == 0).all()


def test_stage_layout_is_seeded_and_falls_back():
    """같은 시드는 같은 배치, 다른 시드는 다른 배치. 늑대가 많아 무대를 다 못 채우면 남은 개체는 v1 자리이고 stage_complete 가 거짓이다."""
    a, b, c = (World(load_v2_config(MIRROR), seeds=[s]) for s in (32084, 32084, 32085))
    np.testing.assert_array_equal(a.pos, b.pos)
    assert not np.array_equal(a.pos, c.pos)
    many = load_v2_config(MIRROR)
    many = many.replace(rand=dict(many.rand, predator_count=[12, 12]))
    w = World(many, seeds=[32084])
    v1 = World(_with(many, integrated_stage=dict(start_layout=None, head_layout=None)), seeds=[32084])
    assert w.stage_complete is False and w.M == 12
    placed = ~np.isclose(w.pred_pos, v1.pred_pos).all(1)
    assert placed[:4].all()                                        # 네 모서리는 서로 21 단위 넘게 떨어져 모두 놓인다
    assert np.isclose(w.pred_pos[~placed], v1.pred_pos[~placed]).all()


def test_ema_denominator():
    """(l) 피식 EMA 분모: null 이면 N, 값을 주면 그 값. 한 스텝에 k 마리 잡히면 ema ← decay·ema + (1 − decay)·(k/분모)·gain."""
    for den in (None, 200):
        w = World(_mirror(ema_den=den), seeds=[32086])
        w.day_fixed = True                          # 늑대가 깨어 있게(어둠 0) — 단위 시험용 덮기
        w._zn_fresh = True
        w._daynight_update()
        assert not w.pred_asleep.any()
        # 늑대 0 바로 앞(0.5)에 사슴 0 을 둔다 — 잠행형 체감 거리 ≤ 6 이라 이번 스텝에 돌진·포획
        w.pos[0] = w.pred_pos[0] + 0.5 * w.pred_head[0]
        w._g = w._geometry()
        w._obs = w._obs_from(w._g)
        e0 = w.pred_ema
        _, _, done, _ = w.step(_graze(w))
        k = w._pred_deaths
        assert k >= 1 and done[0]
        c = w.cfg
        want = c.predation_ema_decay * e0 + (1.0 - c.predation_ema_decay) * (k / (w.N if den is None else den)) * c.predation_ema_gain
        assert w.pred_ema == want


# --------------------------------------------------------------------- #
# 부활 없음
# --------------------------------------------------------------------- #


def test_no_respawn_rollout_invariants():
    """R1b 로 900스텝: 죽음은 슬롯마다 한 번(done 이 다시 서지 않는다), 시체의 위치·방향·에너지가 멈춘다, 산 수 + 포획 + 굶음 = N,
    늑대 표적은 지난 스텝까지 죽은 슬롯을 가리키지 않는다, 리스폰 난수를 뽑지 않는다(v1 스트림 = 배회 선회뿐)."""
    if not R1_MODEL.exists():
        pytest.skip("R1b 모델이 없다")
    from env_v2 import rollout as ro

    w = World(load_v2_config(MIRROR).replace(N=64), seeds=[32087])
    pol = ro.build_policy({"kind": "rep_learned", "path": str(R1_MODEL)}, 32087)
    ro.forward_bind(pol, w)
    assert pol.allowed == ("graze", "flee", "hide")
    ever = np.zeros(w.N, dtype=bool)
    frozen = {}
    turns = 0
    for _ in range(900):
        before = w.alive.copy()
        _, rew, done, _ = w.step(np.asarray(pol(w.observe()), dtype=np.float64))
        turns += w.M_base
        assert not (done & ever).any()                            # 죽은 슬롯은 다시 죽지 않는다(돌아오지 않는다)
        assert (rew[~before] == 0.0).all()
        tgt = w.pred_target[w.pred_target >= 0]
        assert before[tgt].all()                                   # 표적은 스텝 첫머리의 산 슬롯뿐
        for i in np.flatnonzero(ever):
            p, h, e = frozen[i]
            assert (w.pos[i] == p).all() and (w.head[i] == h).all() and w.energy[i] == e
        for i in np.flatnonzero(done):
            frozen[i] = (w.pos[i].copy(), w.head[i].copy(), w.energy[i])
        ever |= done
        np.testing.assert_array_equal(w.alive, ~ever)
        assert int(w.alive.sum()) + w._pred_deaths + w._starve_deaths == w.N
    assert ever.any() and (w.death_cause[ever] > 0).all() and (w.death_t[ever] > 0).all()
    assert (w.death_cause == 1).sum() == w._pred_deaths and (w.death_cause == 2).sum() == w._starve_deaths
    assert (w.energy[w.death_cause == 2] <= 0.0).all()
    # v1 스트림: 배회 선회(늑대마다 스텝당 하나)만 뽑았다 — 같은 시드의 새 생성기를 reset 뽑기 뒤 그만큼 돌린 상태와 같다
    ref = World(load_v2_config(MIRROR).replace(N=64), seeds=[32087]).rng
    ref.uniform(-1.0, 1.0, turns)
    assert ref.bit_generator.state == w.rng.bit_generator.state


def test_dead_are_not_kin():
    """관측 기하: 산 개체 0 앞의 개체 1 이 시체가 되면 동족 수·무리 중심·분리·kin_alarm 에서 빠진다."""
    w = World(load_v2_config(MIRROR), seeds=[32088])
    w.pos[:] = [59.0, 59.0]
    w.pos[0], w.pos[1] = [30.0, 30.0], [32.0, 30.0]
    w.head[0] = [1.0, 0.0]
    g = w._geometry()
    assert g["kin_count"][0] == 1 and np.abs(g["separation"][0]).sum() > 0 and (g["to_centroid"][0] == [1.0, 0.0]).all()
    w._ist_bury(np.array([1]), np.zeros(w.N, dtype=bool))
    g = w._geometry()
    assert g["kin_count"][0] == 0 and (g["separation"][0] == 0).all() and (g["to_centroid"][0] == 0).all()
    assert w.death_cause[1] == 2 and not w.alive[1]


def _awake_day(w):
    """단위 시험용: 늑대가 깨어 있는 낮(어둠 0)으로 덮는다."""
    w.day_fixed = True
    w._zn_fresh = True
    w._daynight_update()
    assert not w.pred_asleep.any()


@pytest.mark.parametrize("dead", [False, True])
def test_dead_are_not_targets_or_food(dead):
    """늑대 0 바로 앞(0.5)의 사슴 1: 살아 있으면 표적이 되어 잡히고, 시체면 표적·포획에서 빠지고 먹이 수요도 0 이다(그 셀의 먹이가 줄지 않는다)."""
    w = World(load_v2_config(MIRROR), seeds=[32089])
    _awake_day(w)
    w.pos[:] = [59.0, 1.0]                                         # 나머지 사슴은 늑대 시야 밖 구석
    w.pred_pos[1] = [1.0, 59.0]
    w.pos[1] = w.pred_pos[0] + 0.5 * w.pred_head[0]
    ix, iy = w._cell_index(w.pos[1:2])
    w.food[iy[0], ix[0]] = w.food_cap[iy[0], ix[0]] = 1.0          # 사슴 1 의 셀에 먹이를 가득
    w.regen_field[iy[0], ix[0]] = 0.0                              # 재생 없음 — 줄었는지만 본다
    if dead:
        w.energy[1] = 0.95                                         # 번식 문턱 위 — 시체는 번식하지 않는다
        w._ist_bury(np.array([1]), np.zeros(w.N, dtype=bool))
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)
    seen = {}
    eat = w._eat
    w._eat = lambda e, mult=None: (seen.setdefault("mult", None if mult is None else mult.copy()), eat(e, mult))[1]
    repro0 = w._repro_total
    _, _, done, _ = w.step(_graze(w))
    if dead:
        assert w.pred_target[0] != 1 and not done[1] and w._pred_deaths == 0
        assert seen["mult"][1] == 0.0 and w.food[iy[0], ix[0]] == 1.0
        assert w.energy[1] == 0.95 and w._repro_total == repro0 and not w.alive[1]
    else:
        assert w.pred_target[0] == 1 and done[1] and w.death_cause[1] == 1
        assert w.food[iy[0], ix[0]] < 1.0


@pytest.mark.parametrize("dead", [False, True])
def test_dead_do_not_block_wolf_sleep(dead):
    """realism_night: 어둠에 깨어 있는 늑대의 settle_r 안에 사슴 하나 — 살아 있으면 눕지 못하고(사슴 곁), 시체면 눕기 시작한다."""
    w = World(load_v2_config(MIRROR), seeds=[32070])
    _awake_day(w)
    w.pos[:] = [59.0, 1.0]
    w.pred_pos[:] = [[30.0, 30.0], [1.0, 59.0]]
    w.pos[1] = [32.0, 30.0]
    if dead:
        w._ist_bury(np.array([1]), np.zeros(w.N, dtype=bool))
    w._zn_dark_k[:] = 100
    w._zn_hunt[:] = False
    w._rz_night_update(1.0, ~w.pred_nocturnal)
    assert w._zn_settle[0] == dead and w._zn_settle[1]


def test_vec_env_refuses_no_respawn():
    from env_v2.vec_env import MultiWorldVecEnv

    with pytest.raises(ValueError, match="respawn false"):
        MultiWorldVecEnv(load_v2_config(MIRROR), num_worlds=1)


# --------------------------------------------------------------------- #
# 실행기·견주기 도구
# --------------------------------------------------------------------- #


def _load(name):
    spec = importlib.util.spec_from_file_location(f"_mirror_{name}", MIRROR_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runner_smoke(tmp_path):
    """세계 2개 × 30스텝(15스텝마다 줄): 줄 정의(산 수 + 포획 + 굶음 = N, 먹이 %·에너지 % 범위), JSON·CSV, 같은 인자 = 같은 결과(벽시계 빼고)."""
    if not R1_MODEL.exists():
        pytest.skip("R1b 모델이 없다")
    rm = _load("run_mirror")
    assert rm.parse_seeds("32000-32002,33005") == [32000, 32001, 32002, 33005]
    for bad in ("10000", "32098-32101", "32000,32000"):
        with pytest.raises(ValueError):
            rm.parse_seeds(bad)
    assert (rm.eat_steps_of_seconds(5.0), rm.eat_steps_of_seconds(30.0), rm.eat_steps_of_seconds(60.0)) == (38, 225, 450)
    res = rm.run(32, 38, [32070, 32071], steps=30, workers=1, log_every=15)
    assert res["meta"]["deer"] == 32 and res["meta"]["eat_steps"] == 38 and len(res["worlds"]) == 2
    for wd in res["worlds"]:
        m = wd["meta"]
        assert m["n"] == 32 and m["wolf_kinds"] == ["stalker", "chaser"] and m["stage_complete"] is True
        assert m["allowed"] == ["graze", "flee", "hide"] and m["dark0"] == 0.5 and m["asleep0"] == 2
        assert [r["step"] for r in wd["rows"]] == [15, 30] and [r["t_s"] for r in wd["rows"]] == [2.0, 4.0]
        for r in wd["rows"]:
            assert set(r) == set(rm.ROW_KEYS)
            assert r["alive_end"] + r["caught"] + r["starved"] == r["n"] and r["alive"] >= r["alive_end"]
            assert 0.0 <= r["food_pct"] <= 100.0 and 0.0 <= r["energy_pct"] <= 100.0 and 0 <= r["hungry"] <= r["alive_end"]
    jp, cp = rm.write(res, "smoke", tmp_path)
    lines = cp.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == ["seed", *rm.ROW_KEYS] and len(lines) == 1 + 4
    again = rm.run(32, 38, [32070, 32071], steps=30, workers=1, log_every=15)
    for a, b in zip(res["worlds"], again["worlds"]):
        assert a["rows"] == b["rows"] and {k: v for k, v in a["meta"].items() if k != "wall_s"} == \
            {k: v for k, v in b["meta"].items() if k != "wall_s"}
    # 견주기 도구가 이 JSON 을 세션(3개씩)으로 읽는다 — 세계 2개면 세션이 없다. 세 번 이어 붙이면 세션 2개
    cu = _load("compare_unreal")
    assert cu.load_python([jp]) == {}
    res3 = dict(res, worlds=res["worlds"] * 3)
    jp3 = tmp_path / "smoke3.json"
    jp3.write_text(json.dumps(res3), encoding="utf-8")
    py = cu.load_python([jp3])
    assert list(py) == [(32, 38)] and len(py[(32, 38)]) == 2
    s = cu.summarize(py[(32, 38)], 4.0)
    assert s["n_sessions"] == 2 and s["n_regions"] == 6
    assert s["alive"]["mean"] + s["caught"]["mean"] + s["starved"]["mean"] >= 1.0 - 1e-12    # 산 수는 스텝 첫머리 값(늦다)


def test_compare_reads_unreal_log_lines(tmp_path):
    """언리얼 기록 줄(EcoPolicyV3IntegratedSubsystem.cpp LogContext 꼴)을 읽어 세션(지역 3개 합)으로 모은다. 파일 이름의 _e 가 식사 초다."""
    cu = _load("compare_unreal")
    line = ("[2026.10.15-09.28.03:844][608]LogEcoPolicyV3I: [EcoV3I] {r} | 60.0초 낮 d=0.00 (팀 시계 낮 59.9/60초) | 사슴 산 {a}/64 | "
            "지금 행동: 먹기 1 도망 0 숨기 0 얼기 0 잠 0 | 구간 사용(개체·스텝): 먹기 1 도망 0 숨기 0 얼기 0 잠 0 | 늑대 2: 배회 0 | "
            "포획 1 (누적 {c}) 굶음 0 (누적 {s}) | 먹이: 구간 먹은 양 1.00 (먹이 단위, 셀 하나 최대 1) · 먹은 사슴 3 · 먹기 중 실제로 먹은 비율 "
            "50% (1/2 개체·스텝) · 무대 먹이 처음의 81.5% · 사슴 에너지 평균 42.0% · 굶주림(15% 아래) 2 · 번식(에너지 0.5 로) 0 | 지형 검사 이동 0, "
            "막힘 사슴 0 늑대 0 | 피식EMA 0.010 | 마스크 위반 0 | 허용 행동(먹기·도망·숨기) 모두 씀=예")
    body = "\n".join(line.format(r=r, a=a, c=c, s=s) for r, a, c, s in (("Forest", 50, 10, 4), ("Barren", 60, 4, 0),
                                                                          ("Highland", 40, 8, 16)))
    (tmp_path / "eat").mkdir()
    (tmp_path / "eat" / "d64_s20000_k0_e30.log").write_text(body, encoding="utf-8")
    (tmp_path / "d64_s20000_k1.log").write_text(body, encoding="utf-8")          # 경계 거리 켬 — 기본으로 읽지 않는다
    u = cu.load_unreal(tmp_path)
    assert list(u) == [(64, 225)] and len(u[(64, 225)]) == 1
    s = cu.summarize(u[(64, 225)], 60.0)
    assert s["n_sessions"] == 1 and s["alive"]["mean"] == 150 / 192 and s["caught"]["mean"] == 22 / 192
    assert s["starved"]["mean"] == 20 / 192 and s["collapse"] == 0.0 and s["food"]["mean"] == 81.5
    assert "| 64 | 30초(225) | 60 |" in cu.table(u, {})
    um = cu.load_unreal_maps(tmp_path)
    assert set(um[(64, 225)]) == {(20000, "Barren"), (20000, "Forest"), (20000, "Highland")}


def _splitmix_ref(seed, stream, n):
    """C++ FRng 의 순수 파이썬 판(정수 연산, EcoWorldV3.h FRng·EcoRepertoire.h Mix64·HashChain3 그대로)."""
    mask = (1 << 64) - 1

    def mix(z):
        z ^= z >> 30
        z = (z * 0xBF58476D1CE4E5B9) & mask
        z ^= z >> 27
        z = (z * 0x94D049BB133111EB) & mask
        return z ^ (z >> 31)

    h = 0
    for x in (0x57335247, seed, stream):
        h = mix(((h ^ x) + 0x9E3779B97F4A7C15) & mask)
    out = []
    for _ in range(n):
        h = (h + 0x9E3779B97F4A7C15) & mask
        out.append((mix(h) >> 11) * (1.0 / 9007199254740992.0))
    return np.array(out)


def test_unreal_map_port():
    """짝 비교의 C++ 먹이 지도: 잡음은 C++ FRng 와 같은 정수 연산의 값이고, 지도는 v1 식(블러·정규화·문턱)으로 만든다. 언리얼 128마리 기록에서
    첫 60초에 무너진 두 지역(Highland@20000·Forest@20002)이 아홉 장 가운데 가장 가난한 두 지도다(굶음은 지도 운이 정한다 — 이 옮김이 맞다는
    정황). 시드 20000~20002 는 언리얼 기록의 세션 시드다(같은 지도를 만들 때만 쓴다)."""
    rm = _load("run_mirror")
    for seed, stream in ((20000, 1), (20002, 3), (20019, 2)):
        np.testing.assert_array_equal(rm.cpp_food_noise(seed, stream, 64), _splitmix_ref(seed, stream, 64))
    assert rm.parse_unreal_maps("20000-20002") == [20000, 20001, 20002]
    for bad in ("19999", "20018-20020", "32000", "20000,20000"):
        with pytest.raises(ValueError):
            rm.parse_unreal_maps(bad)
    cfg = rm.mirror_cfg(128, 38)
    tot = {}
    for s in (20000, 20001, 20002):
        for r in ("Barren", "Forest", "Highland"):
            w = World(cfg, seeds=[32072])
            rm.apply_unreal_map(w, s, r)
            assert (w.food == w.food_cap).all() and w.food_cap.min() == 0.0 and w.food_cap.max() == 1.0
            np.testing.assert_array_equal(w.observe(), w._obs_from(w._geometry()))     # 관측도 새 지도로 만들었다
            tot[(s, r)] = float(w.food_cap.sum())
    assert sorted(tot, key=tot.get)[:2] == [(20002, "Forest"), (20000, "Highland")]
    assert round(tot[(20000, "Forest")], 1) == 153.6 and round(tot[(20002, "Forest")], 1) == 20.5


def test_runner_paired_smoke(tmp_path):
    """짝 비교 연기 시험: 언리얼 세션 하나(지도 3장) × 반복 1 = 세계 3개 × 15스텝. 세계마다 지도 메타, 처음 먹이 = 그 지도의 용량 합, 견주기 도구가
    (세션 시드, 반복)으로 묶어 세션 하나로 읽고 독립 지도 읽기에서는 뺀다."""
    if not R1_MODEL.exists():
        pytest.skip("R1b 모델이 없다")
    rm, cu = _load("run_mirror"), _load("compare_unreal")
    with pytest.raises(ValueError, match="짝 비교"):
        rm.run(16, 38, [32073, 32074], steps=15, workers=1, unreal_maps=[20000], replicates=1)
    res = rm.run(16, 38, [32073, 32074, 32075], steps=15, workers=1, log_every=15, unreal_maps=[20000], replicates=1)
    assert res["meta"]["unreal_maps"] == [20000] and res["meta"]["replicates"] == 1
    regions = [wd["meta"]["unreal_map"]["region"] for wd in res["worlds"]]
    assert regions == ["Barren", "Forest", "Highland"]
    for wd in res["worlds"]:
        w = World(rm.mirror_cfg(16, 38), seeds=[wd["meta"]["seed"]])
        rm.apply_unreal_map(w, 20000, wd["meta"]["unreal_map"]["region"])
        assert wd["meta"]["food0"] == float(w.food.sum())
    jp, _ = rm.write(res, "pair", tmp_path)
    assert cu.load_python([jp]) == {}
    py = cu.load_python([jp], paired=True)
    assert len(py[(16, 38)]) == 1 and len(py[(16, 38)][0]) == 3
    pm = cu.load_python_maps([jp])
    assert set(pm[(16, 38)]) == {(20000, "Barren"), (20000, "Forest"), (20000, "Highland")}
    um = {(16, 38): {k: v[0] for k, v in pm[(16, 38)].items()}}
    assert "| 16 | 5초 | 20000 Barren | 2 |" in cu.map_table(um, pm, times=(2.0,))
