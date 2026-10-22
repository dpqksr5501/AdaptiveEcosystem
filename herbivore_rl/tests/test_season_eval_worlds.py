"""판정 세계(G·Ge·B)와 평가 묶음·캐시 (season/eval_worlds.py, season/common.py, SEASON 4.1·4.2)."""

import json

import numpy as np
import pytest
import yaml

from diagnose_v2 import check_disjoint
from env_v2.world import World
from season import eval_worlds as ew
from season.common import EVAL_SEEDS, HOLDOUT_SEEDS, SEASONS, check_season_yaml, load_base, load_season


@pytest.fixture(scope="module")
def cfgs():
    return ew.world_configs("a")


def test_ge_override_keys(cfgs):
    """Ge 는 G 에서 세 키만 바꾼다. 나머지(무작위화 범위 포함)는 G 그대로다."""
    g, ge, b = cfgs["G"].to_dict(), cfgs["Ge"].to_dict(), cfgs["B"].to_dict()
    assert {k for k in g if g[k] != ge[k]} == set(ew.GE_OVERRIDE)
    assert ge["energy_drain"] == 0.0 and ge["food_energy_per_unit"] == 0.0 and ge["repro_threshold"] == 2.0
    assert ge["repro_threshold"] > ge["max_energy"]
    assert ge["rand"] == g["rand"] and g["rand"]["predator_count"] == [10, 12]
    assert b["rand"]["predator_count"] == [2, 12]
    assert cfgs["G"].v2["features"] == {} and cfgs["B"].v2["features"] == {}


def test_ge_world_energy_fixed_no_starve_no_repro(cfgs):
    """Ge 세계: 에너지가 init_energy 에 머물고 아사·번식이 없다. 같은 시드의 G 는 에너지가 바뀐다."""
    act = np.full((128, 4), 0.5)
    with np.errstate(divide="ignore"):
        w = World(cfgs["Ge"], seeds=[10000])
        for _ in range(300):
            w.step(act)
    assert np.all(w.energy == cfgs["Ge"].init_energy)
    assert w._starve_deaths == 0 and w._repro_total == 0
    assert w._pred_deaths > 0                    # 포식은 그대로 일어난다
    g = World(cfgs["G"], seeds=[10000])
    for _ in range(300):
        g.step(act)
    assert not np.all(g.energy == cfgs["G"].init_energy)


def test_season_yamls_follow_rules(tmp_path):
    expect = {"a": ([10, 12], [1.15, 1.2]), "b": ([2, 4], [0.8, 0.85])}
    for tag, path in SEASONS.items():
        raw = check_season_yaml(path)
        cfg = load_season(path)
        assert cfg.v2["version"] == f"2.0-season-{tag}"
        if tag in expect:
            assert (cfg.rand["predator_count"], cfg.rand["pred_speed_mult"]) == tuple(expect[tag])
        assert set(raw["overrides"]) == {"rand"}
    c = load_season(SEASONS["c"])
    assert c.rand["world_size"] == [100.0, 110.0] and c.rand["ranged_frac"] == [0.4, 0.5]
    base = yaml.safe_load(SEASONS["a"].read_text(encoding="utf-8"))

    def bad(mut):
        d = yaml.safe_load(yaml.safe_dump(base))
        mut(d)
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.safe_dump(d), encoding="utf-8")
        with pytest.raises(ValueError):
            check_season_yaml(p)

    bad(lambda d: d["overrides"].update(see_r=10.0))                       # 컴파일 상수 키
    bad(lambda d: d["overrides"]["rand"].pop("cover_frac"))                # rand 키 빠짐
    bad(lambda d: d["overrides"]["rand"].update(pred_speed_mult=[1.1, 1.4]))   # 기본 범위 밖
    bad(lambda d: d.update(features={"speed": {"enabled": True}}))         # 기능 켜기
    bad(lambda d: d["overrides"]["rand"].update(herd_size=[1, 2]))         # 기본 설정에 없는 rand 키
    bad(lambda d: d["train"].update(reset_interval=2000))                  # train 블록이 B 와 다르다
    bad(lambda d: d.pop("train"))                                          # train 블록 빠짐


def test_seed_sets_disjoint():
    assert not set(EVAL_SEEDS) & set(HOLDOUT_SEEDS) and len(EVAL_SEEDS) == len(HOLDOUT_SEEDS) == 20
    for cfg in (load_season(SEASONS["a"]), load_base()):
        check_disjoint("학습 세계 시드", range(*cfg.train_seeds), EVAL_SEEDS + HOLDOUT_SEEDS, None)


def test_gate_bundle_layout(tmp_path):
    cand, cur, k2b, anc2 = (str(tmp_path / f"{n}.zip") for n in ("cand", "cur", "k2b", "anc2"))
    b = ew.gate_bundle(cand, cur, k2b)
    assert {w: sorted(s) for w, s in b.items()} == {
        "G": ["cand", "cand_P", "cur", "cur_P"], "Ge": ["cand", "cur", "k2b"], "B": ["anchor", "cand"]}
    assert b["G"]["cand_P"]["wrap"] == [{"kind": "act_permute", "salt": 0}]
    assert b["G"]["cand_P"]["policy"] == b["G"]["cand"] == ew.learned(cand)
    assert b["B"]["anchor"] == ew.learned(cur)       # SR1: 현재 = 앵커
    b2 = ew.gate_bundle(cand, cur, k2b, anchor=anc2)
    assert "anchor" in b2["G"] and "anchor_P" in b2["G"] and b2["B"]["anchor"] == ew.learned(anc2)
    assert sorted(ew.holdout_bundle(cand, cur, k2b)["Ge"]) == ["cand", "cur", "k2b"]
    # 평가 잡 수: 판정 묶음 9사양 중 후보 4·앵커 4·K2-B 1 (SEASON 5.4 의 "후보당 4, K2-B 당 1, 앵커당 4")
    roles = [(w, r) for w, s in b.items() for r in s]
    assert len(roles) == 9


def test_cache_and_slim_rows(cfgs, tmp_path, monkeypatch):
    """고정 정책 하나를 짧게 재고, 같은 조건의 두 번째 호출은 캐시에서 읽는다. 행동 통계 열을 확인한다."""
    cache = ew.EvalCache(tmp_path / "cache")
    spec = {"kind": "fixed", "action": [0.5, 0.5, 0.5, 0.5]}
    assert cache.key(cfgs["G"], ew.learned(tmp_path / "없음.zip"), [1], 10, 0.99) is None
    k_g = cache.key(cfgs["G"], spec, [10000], 60, 0.99)
    assert k_g == cache.key(cfgs["G"], spec, [10000], 60, 0.99) != cache.key(cfgs["Ge"], spec, [10000], 60, 0.99)
    other = ew.EvalCache(tmp_path / "cache")
    other.code = "0" * 12                               # 시뮬레이터 코드가 바뀌면 키가 달라진다
    assert other.key(cfgs["G"], spec, [10000], 60, 0.99) != k_g and len(cache.code) == 12
    assert ew.missing_jobs(cfgs["G"], {"x": spec}, [10000], 60, 0.99, cache) == 1
    rows = ew.evaluate(cfgs["G"], {"x": spec}, [10000], 60, 0.99, workers=1, cache=cache)["x"]
    assert len(rows) == 1 and rows[0]["seed"] == 10000
    assert rows[0]["act_mean"] == pytest.approx([0.5] * 4) and rows[0]["act_m2"] == pytest.approx([0.25] * 4)
    assert not any(k.startswith("_") for k in rows[0])
    assert ew.missing_jobs(cfgs["G"], {"x": spec}, [10000], 60, 0.99, cache) == 0

    def boom(*a, **k):
        raise AssertionError("캐시가 있는데 다시 쟀다")

    monkeypatch.setattr(ew, "run_specs", boom)
    again = ew.evaluate(cfgs["G"], {"x": spec}, [10000], 60, 0.99, workers=1, cache=cache)["x"]
    assert json.dumps(again) == json.dumps(rows)         # g_gamma 는 nan(60 스텝 < 꼬리)이라 문자열로 비교한다
    with pytest.raises(FileNotFoundError):
        ew.evaluate(cfgs["G"], {"y": ew.learned(tmp_path / "없음.zip")}, [10000], 60, 0.99, cache=cache)


def test_ge_sanity():
    ok = ew.ge_sanity([[{"starve_rate": 0.0, "repro": 0.0}]])
    bad = ew.ge_sanity([[{"starve_rate": 0.0, "repro": 0.0}], [{"starve_rate": 1e-5, "repro": 0.0}]])
    assert ok["ok"] and not bad["ok"] and bad["max_starve_rate"] == 1e-5
