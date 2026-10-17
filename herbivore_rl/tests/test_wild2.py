"""야생 2단계 1 — 은신처 먹이 부족(설정 configs/v3_wild2_mirror.yaml)과 사냥 성공률 통계 (10-17, 명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md,
정의는 env_v2/world.py 모듈 docstring '야생 2단계').

비트 동일: 사냥 통계는 동역학과 무관하다 — 직전 커밋(54b8456)의 코드와 기존 설정(v3_wild1_mirror·v3_r3_on)의 궤적·통계·v1 난수 상태·기능 스트림이
같다(R1b 롤아웃 포함). 야생 2단계 설정에서 2단계 블록(realism_cover_food)을 끄면 v3_wild1_mirror.yaml 과 같다.
규칙 단위 시험: hunt_update 의 셈(시작·이어짐·성공·실패·사냥 밖 포획), 롤아웃에서 성공 + 사냥 밖 = 늑대 포획 수·시작 − 끝 = 이어지는 사냥,
은신처 셀 용량·재생 배수, 짝 비교 지도 덮기가 은신처 먹이 부족을 지킨다. 시드는 탐색 32080~32083 만 쓴다.
현실 근거: 닫힌 숲 밑 사슴 먹이는 트인 곳의 약 12~14%(Lashley 외 2011), 늑대 사냥 한 번 성공률 10~49%(Mech & Peterson 2003).
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
from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import HUNT_KEYS, PT_CHASER, PT_STALKER, World, hunt_update

CFG = ROOT / "configs"
WILD1 = CFG / "v3_wild1_mirror.yaml"
WILD2 = CFG / "v3_wild2_mirror.yaml"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BASE_COMMIT = "54b8456"              # 야생 2단계 직전 커밋(늑대 몸 여유 C++) — 비트 동일 기준
STAGE2 = ("realism_cover_food",)     # 2단계에서 켠 블록

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _tum():
    spec = importlib.util.spec_from_file_location("_tum_for_wild2", ROOT / "tests" / "test_unreal_mirror.py")
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
# 설정
# --------------------------------------------------------------------- #


def test_wild2_config_is_wild1_plus_stage2():
    """v3_wild2_mirror.yaml = v3_wild1_mirror.yaml + 2단계 블록(version 만 다르다). 블록 값은 명세 값(0.15·0.15)이다."""
    a = yaml.safe_load(WILD1.read_text(encoding="utf-8"))
    b = yaml.safe_load(WILD2.read_text(encoding="utf-8"))
    assert a["version"] == "3.wild1" and b["version"] == "3.wild2"
    fa, fb = a.pop("features"), b.pop("features")
    a.pop("version"), b.pop("version")
    assert a == b
    assert set(fb) - set(fa) == set(STAGE2)
    assert all(fa[k] == fb[k] for k in fa)
    assert fb["realism_cover_food"] == dict(enabled=True, cap_frac=0.15, regen_frac=0.15)


def test_stage2_off_equals_wild1():
    """2단계 블록을 끈 야생 2단계 세계 = 야생 1단계 세계(궤적·통계·사냥 셈)."""
    c1 = load_v2_config(WILD1).replace(N=32)
    c2 = _with(load_v2_config(WILD2).replace(N=32), **{k: dict(enabled=False) for k in STAGE2})
    w1, w2 = World(c1, seeds=[32080]), World(c2, seeds=[32080])
    for _ in range(300):
        a = _graze(w1)
        o1, o2 = w1.step(a), w2.step(a)
        for x, y in zip(o1, o2):
            np.testing.assert_array_equal(x, y)
    for k in ("pos", "energy", "food", "food_cap", "regen_field", "pred_pos", "pred_cd"):
        np.testing.assert_array_equal(getattr(w1, k), getattr(w2, k))
    assert json.dumps(w1.hunt_stats()) == json.dumps(w2.hunt_stats())   # rate 가 nan 일 수 있어 글로 견준다


def test_shelter_food_cells():
    """은신처 원과 겹치는 셀(원 안 위치가 고르는 셀을 모두 포함)의 용량 = 1단계 용량 × 0.15, 재생률 = 밖 × 0.15. 밖 셀은 그대로다."""
    w1 = World(load_v2_config(WILD1).replace(N=8), seeds=[32081])
    w2 = World(load_v2_config(WILD2).replace(N=8), seeds=[32081])
    cell = w2.cover_food_cell
    np.testing.assert_array_equal(w1.cov_c, w2.cov_c)
    assert cell.any() and (cell | ~w2.cover_cell).all()            # 셀 중심이 원 안인 셀을 포함한다
    np.testing.assert_array_equal(w2.food_cap, np.where(cell, w1.food_cap * 0.15, w1.food_cap))
    base = w2.cfg.food_regen_base * w2.food_regen_mult
    np.testing.assert_array_equal(w2.regen_field, base * np.where(cell, 0.15, 1.0))
    # 원 안의 자리는 늘 은신처 셀 위다(가장자리까지): 원 둘레 바로 안쪽 점들
    ang = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)
    for (cx, cy), r in zip(w2.cov_c, w2.cov_r):
        p = np.stack([cx + (r - 1e-6) * np.cos(ang), cy + (r - 1e-6) * np.sin(ang)], 1)
        ix, iy = w2._cell_index(p)
        assert cell[iy, ix].all()


def test_unreal_map_keeps_shelter_food():
    """짝 비교 지도 덮기(run_mirror.apply_unreal_map)는 새 지도의 은신처 셀에도 배수를 건다."""
    spec = importlib.util.spec_from_file_location("_run_mirror_w2", ROOT / "results" / "v3" / "mirror" / "run_mirror.py")
    rm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rm)
    w1 = World(load_v2_config(WILD1).replace(N=8), seeds=[32081])
    w2 = World(load_v2_config(WILD2).replace(N=8), seeds=[32081])
    rm.apply_unreal_map(w1, 20000, "Forest")
    rm.apply_unreal_map(w2, 20000, "Forest")
    cell = w2.cover_food_cell
    np.testing.assert_array_equal(w2.food_cap, np.where(cell, w1.food_cap * 0.15, w1.food_cap))
    np.testing.assert_array_equal(w2.food, w2.food_cap)


# --------------------------------------------------------------------- #
# 사냥 성공률
# --------------------------------------------------------------------- #


def test_hunt_update_cases():
    """(지난 on, 전력 걸음, 잡음) 여덟 경우 → (새 on, 시작, 끝, 성공, 사냥 밖)."""
    cases = {
        (False, False, False): (False, False, False, False, False),
        (False, True, False): (True, True, False, False, False),      # 시작
        (False, True, True): (False, True, True, True, False),        # 시작한 스텝에 잡음
        (False, False, True): (False, False, False, False, True),     # 사냥 밖 포획
        (True, True, False): (True, False, False, False, False),      # 이어짐
        (True, True, True): (False, False, True, True, False),        # 성공
        (True, False, True): (False, False, True, True, False),       # 전력 걸음이 끊긴 첫 스텝에 잡음 = 성공
        (True, False, False): (False, False, True, False, False),     # 실패
    }
    keys = list(cases)
    on, run, got = (np.array([k[i] for k in keys]) for i in range(3))
    out = hunt_update(on, run, got)
    for j, k in enumerate(keys):
        assert tuple(bool(x[j]) for x in out) == cases[k], k


def test_hunt_update_sequence_counts():
    """임의 열: 시작 − 끝 = 이어지는 사냥, 끝 = 성공 + 실패, 잡음 = 성공 + 사냥 밖."""
    rng = np.random.default_rng(32082)
    M, T = 6, 2000
    on = np.zeros(M, dtype=bool)
    tot = np.zeros(4, dtype=np.int64)
    caught_n = 0
    for _ in range(T):
        run = rng.random(M) < 0.3
        got = rng.random(M) < 0.05
        on, *x = hunt_update(on, run, got)
        tot += [int(v.sum()) for v in x]
        caught_n += int(got.sum())
    starts, ends, success, outside = tot
    assert starts - ends == int(on.sum())
    assert success + outside == caught_n
    assert ends >= success


def test_hunt_stats_in_rollout():
    """야생 2단계 거울 세계 1800 스텝: 늑대 포획(쿨다운이 막 찬 늑대) 수 = 성공 + 사냥 밖, 시작 − 끝 = 이어지는 사냥, 유형별 합 = 전체."""
    w = World(load_v2_config(WILD2).replace(N=128), seeds=[32083])
    eat = int(w.cfg.pred_eat_cd)
    wolf_catches = 0
    run_steps = 0
    for _ in range(1800):
        w.step(_graze(w))
        wolf_catches += int(np.count_nonzero(w.pred_cd == eat))
        run_steps += int(np.count_nonzero(w.pred_running))
    h = w.hunt_stats()
    assert h["success"] + h["outside"] == wolf_catches
    assert h["starts"] - h["ends"] == h["ongoing"]
    for k in HUNT_KEYS:
        assert h[k] == h[f"chaser_{k}"] + h[f"stalker_{k}"]
    assert h["starts"] >= 1 and wolf_catches >= 1 and run_steps >= h["starts"]
    assert set(w.pred_type.tolist()) == {PT_CHASER, PT_STALKER}
    if h["ends"]:
        assert 0.0 <= h["rate"] <= 1.0


def test_hunt_stats_needs_v3_world():
    w = World(load_v2_config(CFG / "v2_4s.yaml").replace(N=8), seeds=[32080])
    with pytest.raises(ValueError, match="hunt_stats"):
        w.hunt_stats()


# --------------------------------------------------------------------- #
# 비트 동일
# --------------------------------------------------------------------- #


def test_hunt_metric_bit_identical_to_head(tmp_path):
    """직전 코드(54b8456)와: 야생 1단계 거울·R3 설정의 궤적·통계·난수·관측 이름·기능 스트림이 같다(R1b 롤아웃 포함). 사냥 셈은 통계 전용이다."""
    tum = _tum()
    old_root = tum._archive(tmp_path, BASE_COMMIT)
    if old_root is None:
        pytest.skip(f"git archive {BASE_COMMIT} 를 할 수 없다")
    script = tmp_path / "trace.py"
    script.write_text(tum.TRACE_SRC % dict(keys=tum.KEYS, stats=tum.STATS), encoding="utf-8")
    jobs = [dict(config="configs/v3_r3_on.yaml", seed=32080, steps=250, policy="rand"),
            dict(config="configs/v3_wild1_mirror.yaml", seed=32081, steps=400, policy="rand")]
    if R1_MODEL.exists():
        jobs.append(dict(config="configs/v3_wild1_mirror.yaml", seed=32082, steps=400, policy="model", model=str(R1_MODEL)))
    procs = []
    for root, tag in ((old_root, "old"), (ROOT, "new")):
        jp, op = tmp_path / f"jobs_{tag}.json", tmp_path / f"out_{tag}.json"
        jp.write_text(json.dumps(jobs), encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, str(script), str(jp), str(op)], cwd=root), op))
    outs = []
    for p, op in procs:
        assert p.wait(timeout=900) == 0
        outs.append(json.loads(op.read_text(encoding="utf-8")))
    for j, a, b in zip(jobs, *outs):
        first = next((i for i, (x, y) in enumerate(zip(a["hashes"], b["hashes"])) if x != y), None)
        assert first is None and len(a["hashes"]) == len(b["hashes"]), (j, first)
        for k in ("stats", "rng", "obs_names", "streams"):
            assert a[k] == b[k], (j, k)
