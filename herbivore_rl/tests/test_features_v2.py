"""V2 0-1b — 기능 스위치 블록 형식과 기능별 난수 스트림 (계획서 4.8, 5절 0단계).

완료 기준: 기능 하나를 켜고 꺼도 나머지 기능의 난수열이 그대로다. 기능 스트림을 써도 v1 스트림은
소비되지 않고, 기능을 모두 끈 env_v2 World 는 v1 과 같다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import pickle
from types import MappingProxyType

import numpy as np
import pytest
import yaml

import env_v2.features as F
from env.config import ROOT, load_config
from env.world import World as WorldV1
from env_v2.config import load_v2_config
from env_v2.rollout import _perm_rng, adapt_spec, build_policy
from env_v2.vec_env import MultiWorldVecEnv
from env_v2.world import ACT_DIM, World as WorldV2
from policies.registry import make_policy


@pytest.fixture
def cfg2():
    return load_v2_config()


@pytest.fixture
def blank_registry(monkeypatch):
    """형식·복제 테스트가 자리표시 계수를 쓸 수 있게 등록부를 비운다. 기능을 구현해도 깨지지 않는다."""
    monkeypatch.setattr(F, "IMPLEMENTED", frozenset())
    monkeypatch.setattr(F, "PARAM_KEYS", MappingProxyType({}))


# 버전 설정. 파일 이름 순이 버전 순이다(v2.yaml = v2.0 이 '.' < '_' 로 맨 앞, 그다음 v2_0b.yaml ...).
V2_CONFIGS = sorted((ROOT / "configs").glob("v2*.yaml"))


def _yaml_block(name):
    """그 기능을 처음 켜는 버전 설정(configs/v2*.yaml 중 블록이 켜진 첫 파일)의 블록.

    v2.yaml(v2.0)은 기능을 모두 끈 기록이라 구현한 기능의 계수는 그 기능의 버전 설정에 있다. 구현한 기능은
    켜는 버전 설정이 있어야 하고 계수를 모두 적어야 한다(계수는 yaml 이 유일한 원본)."""
    for path in V2_CONFIGS:
        block = dict(load_v2_config(path).v2["features"].get(name) or {})
        if block.get("enabled"):
            break
    else:
        pytest.fail(f"configs/v2*.yaml 중 features.{name} 을 켜는 버전 설정이 없다")
    missing = sorted(set(F.PARAM_KEYS.get(name, ())) - set(block))
    assert not missing, f"{path.name} 의 features.{name} 에 계수 {missing} 를 적는다"
    return block


def _with_features(cfg, features):
    v2 = dict(cfg.v2)
    v2["features"] = features
    return cfg.replace(v2=v2)


def _head(g, n=16):
    return g.random(n)


# --------------------------------------------------------------------- #
# 등록부
# --------------------------------------------------------------------- #


def test_feature_ids_are_pinned():
    """번호를 바꾸면 같은 시드의 세계가 조용히 달라진다. 바꿀 일이 생기면 이 테스트와 함께 바꾼다."""
    assert dict(F.FEATURE_IDS) == {
        "food_v": 1, "speed": 2, "vigilance": 3, "regions": 4, "daynight": 5, "region_env": 6,
        "migration": 7, "weather": 8, "boldness": 9, "water": 10, "boundary": 11, "obstacles": 12,
    }
    ids = list(F.FEATURE_IDS.values())
    assert len(set(ids)) == len(ids) and min(ids) >= 1    # 0 은 SeedSequence 끝 0 무시와 겹친다
    assert F.STREAM_DOMAIN == 2
    assert F.IMPLEMENTED <= set(F.FEATURE_IDS)
    assert set(F.PARAM_KEYS) <= F.IMPLEMENTED            # 계수 키는 구현한 기능에만 둔다


def test_feature_ids_cannot_be_mutated():
    with pytest.raises(TypeError):
        F.FEATURE_IDS["food_v"] = 99                      # type: ignore[index]


# --------------------------------------------------------------------- #
# 스트림
# --------------------------------------------------------------------- #


def test_part0_is_the_plan_formula():
    """계획서 4.8 의 default_rng([seed, 2, feature_id]) 와 같다 (SeedSequence 가 끝의 0 을 무시)."""
    for name, fid in F.FEATURE_IDS.items():
        for seed in (0, 636, 2**32 - 1):
            np.testing.assert_array_equal(
                _head(F.feature_stream(seed, name)), _head(np.random.default_rng([seed, 2, fid])))


@pytest.mark.parametrize("seed", [0, 5, 636, 10000])
def test_streams_are_pairwise_distinct(seed):
    """기능·part 마다, 그리고 v1 스트림·순열 대조군 스트림과 서로 다른 난수열이다."""
    heads = {("v1",): _head(np.random.default_rng(seed)),
             ("old_rng2",): _head(np.random.default_rng([seed, 2]))}
    for name in F.FEATURE_IDS:
        for part in (0, 1, 2):
            heads[(name, part)] = _head(F.feature_stream(seed, name, part))
    for kind in ("act_permute", "obs_permute"):
        for salt in (0, 1, 2, 5):
            heads[(kind, salt)] = _head(_perm_rng(kind, seed, salt))
    blobs = {k: v.tobytes() for k, v in heads.items()}
    assert len(set(blobs.values())) == len(blobs)


BAD_PARTS = (-1, -0.5, 0.7, 1.5, 1.9, True, False, "1", None, np.float64(1.0), 2**32)


def test_feature_rng_bad_arguments(cfg2):
    w = WorldV2(cfg2, seeds=[3])
    with pytest.raises(KeyError):
        w.feature_rng("food")                             # 오타
    for bad in BAD_PARTS:
        with pytest.raises(ValueError):
            w.feature_rng("food_v", part=bad)
    # 이미 만든 part 가 캐시에 있어도 같은 검사를 거친다 (True·1.0 은 키 1 과 같게 해시된다)
    w.feature_rng("food_v", 0)
    w.feature_rng("food_v", 1)
    for bad in BAD_PARTS:
        with pytest.raises(ValueError):
            w.feature_rng("food_v", part=bad)
    assert w.feature_rng("food_v", np.int64(1)) is w.feature_rng("food_v", 1)


def test_feature_stream_seed_range():
    """SeedSequence 는 2^32 이상을 단어 여러 개로 쪼갠다. 그 범위에서는 part 0 = [seed, 2, id] 가 깨지므로 막는다."""
    F.feature_stream(2**32 - 1, "food_v")
    F.feature_stream(np.int64(636), "food_v")
    for bad in (-1, 2**32, 1.0, True, "5"):
        with pytest.raises(ValueError):
            F.feature_stream(bad, "food_v")


def test_feature_rng_is_cached_within_a_world(cfg2):
    """같은 세계 안에서는 같은 스트림 객체를 이어 쓴다 (호출마다 처음부터 다시 뽑지 않는다)."""
    w = WorldV2(cfg2, seeds=[3])
    g = w.feature_rng("weather")
    assert w.feature_rng("weather") is g and w.feature_rng("weather", 0) is g
    assert w.feature_rng("weather", 1) is not g
    a = g.random(4)
    b = w.feature_rng("weather").random(4)
    ref = F.feature_stream(3, "weather").random(8)
    np.testing.assert_array_equal(np.concatenate([a, b]), ref)


def test_feature_streams_restart_when_world_renews(cfg2):
    """세계를 새로 뽑으면 스트림도 그 세계의 시드에서 처음부터 시작한다."""
    w = WorldV2(cfg2, seeds=[7])
    first = w.feature_rng("food_v").random(8)
    w.feature_rng("food_v").random(1000)
    w.reset()                                             # 시드 풀이 [7] 하나라 같은 세계
    np.testing.assert_array_equal(w.feature_rng("food_v").random(8), first)

    other = WorldV2(cfg2, seeds=[8])
    assert not np.array_equal(other.feature_rng("food_v").random(8), first)


def test_multiworld_worlds_have_their_own_streams(cfg2):
    venv = MultiWorldVecEnv(cfg2, num_worlds=3, meta_seed=0)
    heads = [w.feature_rng("daynight").random(8).tobytes() for w in venv.worlds]
    assert len(set(heads)) == 3
    for w in venv.worlds:                                 # 세계 시드에서 그대로 나온다
        np.testing.assert_array_equal(
            WorldV2(cfg2, seeds=[w.seed]).feature_rng("regions").random(8),
            w.feature_rng("regions").random(8))


# --------------------------------------------------------------------- #
# 0-1b 완료 기준 — 기능 하나를 켜고 꺼도 나머지 기능의 난수열이 그대로다
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("seed", [0, 636])
def test_toggling_one_feature_keeps_other_streams(cfg2, monkeypatch, seed):
    """food_v 를 켜고 끄고, 켠 쪽이 food_v 스트림을 마구 써도 daynight·weather 난수열은 같다.

    스트림 기반(번호·part·캐시)이 서로 격리되는지 본다. food_v 는 실제 구현(v2.0b 계수)으로 켜고,
    daynight·weather 는 계수 없는 가짜 기능으로 켠다. 세계(pos, stats)는 비교하지 않는다 — 켠 쪽 세계가
    바뀌는 게 정상이다. 기능 코드가 남의 스트림을 쓰지 않는지는
    test_implemented_features_use_only_their_own_streams 가 본다."""
    monkeypatch.setattr(F, "IMPLEMENTED", F.IMPLEMENTED | {"food_v", "daynight", "weather"})
    on = WorldV2(_with_features(cfg2, {"food_v": dict(_yaml_block("food_v"), enabled=True),
                                       "daynight": {"enabled": True},
                                       "weather": {"enabled": True}}), seeds=[seed])
    off = WorldV2(_with_features(cfg2, {"daynight": {"enabled": True},
                                        "weather": {"enabled": True}}), seeds=[seed])
    assert on.features.active == ("food_v", "daynight", "weather")
    assert off.features.active == ("daynight", "weather")

    act = np.full((on.N, ACT_DIM), 0.5)
    got_on, got_off = [], []
    for t in range(40):
        on.feature_rng("food_v").random(37 + t)          # 켠 쪽만 food_v 난수를 쓴다
        on.feature_rng("food_v", part=1).normal(size=5)
        for name in ("daynight", "weather"):
            for part in (0, 1):
                got_on.append(on.feature_rng(name, part).random(3))
                got_off.append(off.feature_rng(name, part).random(3))
        on.step(act)
        off.step(act)
    for x1, x0 in zip(got_on, got_off):
        np.testing.assert_array_equal(x1, x0)


def _implemented_cases():
    return [()] + [(name,) for name in sorted(F.IMPLEMENTED)]


@pytest.mark.parametrize("active", _implemented_cases(), ids=lambda a: "+".join(a) or "all_off")
def test_implemented_features_use_only_their_own_streams(cfg2, active):
    """규칙 1: 기능 코드는 자기 스트림에서만 뽑는다. 구현한 기능마다 그 기능만 켜고 돌린 뒤
    만들어진 스트림이 그 기능 것뿐인지 본다. 모두 끄면 기능 스트림이 하나도 생기지 않는다.

    켜는 계수는 그 기능의 버전 설정(configs/v2*.yaml) 블록에서 가져온다(계수는 yaml 이 유일한 원본)."""
    blocks = {}
    for name in active:
        blocks[name] = dict(_yaml_block(name), enabled=True)
    w = WorldV2(_with_features(cfg2, blocks), seeds=[636])
    assert w.features.active == active
    # 행동 수는 세계를 따른다(speed 를 켜면 5개). 4개면 make_policy random(seed 1) 과 같은 수열이다
    p = build_policy(adapt_spec({"kind": "random", "seed": 1}, w.act_dim))
    for _ in range(300):
        w.step(p(w.observe()))
    assert {name for name, _ in w._feature_rngs} <= set(active)


def test_disabled_blocks_keep_v1_world(cfg2):
    """등록된 기능 블록을 모두 적되 끈 설정은 v1 과 비트 단위로 같다 (계수가 적혀 있어도)."""
    blocks = {name: (dict(_yaml_block(name), enabled=False) if name in F.IMPLEMENTED
                     else {"enabled": False, "some_coeff": 0.5})
              for name in F.FEATURE_IDS}
    cfg = _with_features(cfg2, blocks)
    assert WorldV2(cfg, seeds=[0]).features.active == ()
    v1, v2 = WorldV1(load_config(), seeds=[10000]), WorldV2(cfg, seeds=[10000])
    p1, p2 = make_policy({"kind": "utility"}), make_policy({"kind": "utility"})
    for _ in range(200):
        o1, o2 = v1.observe(), v2.observe()
        np.testing.assert_array_equal(o1, o2)
        v1.step(p1(o1))
        v2.step(p2(o2))
    assert v1.stats() == v2.stats()


def test_world_pickles_and_deepcopies(cfg2, blank_registry):
    """세계를 워커로 넘기거나 같은 상태에서 갈라 돌릴 수 있어야 한다 (Features 의 MappingProxyType)."""
    w = WorldV2(_with_features(cfg2, {"food_v": {"enabled": False, "alpha": 0.5}}), seeds=[3])
    act = np.full((w.N, ACT_DIM), 0.5)
    for _ in range(5):
        w.step(act)
    w.feature_rng("weather").random(3)
    clones = [pickle.loads(pickle.dumps(w)), copy.deepcopy(w)]
    for c in clones:
        assert c.features.params("food_v") == {"alpha": 0.5}
        with pytest.raises(TypeError):
            c.features.blocks["food_v"]["alpha"] = 1.0    # type: ignore[index]
    nxt = [c.feature_rng("weather").random(4) for c in clones]
    ref = w.feature_rng("weather").random(4)              # 복제본은 스트림 위치도 이어받는다
    for x in nxt:
        np.testing.assert_array_equal(x, ref)
    for _ in range(20):
        w.step(act)
        for c in clones:
            c.step(act)
    for c in clones:
        np.testing.assert_array_equal(c.pos, w.pos)
        assert c.stats() == w.stats()


def test_world_accepts_v1_config_as_all_off():
    """v2 키가 없는 v1 Config 로 만든 env_v2 World 는 기능이 모두 꺼진 것으로 본다."""
    w = WorldV2(load_config(), seeds=[1])
    assert w.features.active == ()
    assert w.feature_rng("water").random() == F.feature_stream(1, "water").random()


# --------------------------------------------------------------------- #
# 블록 형식 검증
# --------------------------------------------------------------------- #


def test_parse_features_block_format():
    f = F.parse_features({"food_v": {"enabled": False, "alpha": 0.5, "rho": 0.001},
                          "regions": None,
                          "weather": {}}, implemented=frozenset(), param_keys={})
    assert f.enabled("food_v") is False and f.params("food_v") == {"alpha": 0.5, "rho": 0.001}
    assert f.enabled("regions") is False and f.params("regions") == {}
    assert f.enabled("water") is False and f.params("water") == {}     # 블록이 없으면 꺼짐
    assert f.active == ()
    with pytest.raises(KeyError):
        f.enabled("nope")
    with pytest.raises(TypeError):
        f.blocks["food_v"]["alpha"] = 1.0                 # type: ignore[index]

    g = F.parse_features({"weather": {"enabled": True}, "food_v": {"enabled": True}},
                         implemented=frozenset({"food_v", "weather"}), param_keys={})
    assert g.active == ("food_v", "weather")              # 번호 순
    assert F.parse_features(None, frozenset(), {}).active == ()
    assert F.parse_features({}, frozenset(), {}).active == ()


def test_parse_features_does_not_mutate_input_and_params_are_copies():
    raw = {"food_v": {"enabled": False, "alpha": 0.5, "halflives": [300, 700]}}
    f = F.parse_features(raw, implemented=frozenset(), param_keys={})
    assert raw == {"food_v": {"enabled": False, "alpha": 0.5, "halflives": [300, 700]}}
    f.params("food_v")["halflives"].append(9999)          # 꺼낸 계수를 고쳐도
    assert f.params("food_v")["halflives"] == [300, 700]  # 설정은 그대로


def test_param_keys_of_implemented_features():
    """구현한 기능은 계수 키가 정해져 있다. 모르는 키(오타)와 켤 때 빠진 계수는 실패한다."""
    imp, keys = frozenset({"food_v"}), {"food_v": frozenset({"alpha", "rho"})}
    ok = F.parse_features({"food_v": {"enabled": True, "alpha": 0.5, "rho": 1.0e-3}}, imp, keys)
    assert ok.params("food_v") == {"alpha": 0.5, "rho": 0.001}
    F.parse_features({"food_v": {"enabled": False, "alpha": 0.5}}, imp, keys)   # 끈 블록은 일부만 적어도 된다
    for bad in ({"food_v": {"enable": True, "alpha": 0.5, "rho": 0.1}},          # enabled 오타
                {"food_v": {"enabled": True, "alhpa": 0.5, "rho": 0.1}},         # 계수 오타
                {"food_v": {"enabled": True, "alpha": 0.5}},                     # 빠진 계수
                {"food_v": {"Enabled": False}}):
        with pytest.raises(ValueError):
            F.parse_features(bad, imp, keys)


@pytest.mark.parametrize("raw, err", [
    ({"food": {"enabled": False}}, KeyError),            # 등록부에 없는 이름(오타)
    ({"food_v": True}, ValueError),                      # 블록이 아니라 값 하나
    ({"food_v": "on"}, ValueError),
    ({"food_v": {"enabled": 1}}, ValueError),            # bool 이 아니다
    ({"food_v": {"enabled": "true"}}, ValueError),
    ({"food_v": {"enabled": True}}, ValueError),         # 아직 구현하지 않은 기능
    (["food_v"], ValueError),                            # features 가 dict 가 아니다
    ("food_v", ValueError),
    ({"food_v": {True: True}}, ValueError),              # YAML 1.1 의 on: true → 키가 bool
    ({"food_v": {"rho": "1e-3"}}, ValueError),           # PyYAML 은 1e-3 을 문자열로 읽는다
    ({"food_v": {"rho": "1.0e3"}}, ValueError),          # 지수 부호가 없어도 문자열이다
    ({"food_v": {"halflives": [300, "7e3"]}}, ValueError),
])
def test_parse_features_rejects(raw, err):
    with pytest.raises(err):
        F.parse_features(raw, implemented=frozenset(), param_keys={})


def _write_v2(tmp_path, features_yaml):
    p = tmp_path / "v2.yaml"
    p.write_text('version: "test"\noverrides: {}\n' + features_yaml
                 + "train:\n  num_worlds: 2\n  reset_interval: 100\n", encoding="utf-8")
    return p


def test_load_v2_config_validates_features(tmp_path, blank_registry):
    ok = load_v2_config(_write_v2(tmp_path, "features:\n  food_v: {enabled: false, alpha: 0.5}\n  daynight:\n"))
    assert ok.v2["features"]["food_v"] == {"enabled": False, "alpha": 0.5}
    assert WorldV2(ok, seeds=[0]).features.params("food_v") == {"alpha": 0.5}

    empty = load_v2_config(_write_v2(tmp_path, "features:\n"))
    assert empty.v2["features"] == {}

    with pytest.raises(KeyError):
        load_v2_config(_write_v2(tmp_path, "features:\n  daylight: {enabled: false}\n"))
    with pytest.raises(ValueError):
        load_v2_config(_write_v2(tmp_path, "features:\n  daynight: {enabled: true}\n"))
    with pytest.raises(ValueError):
        load_v2_config(_write_v2(tmp_path, "features:\n  daynight: true\n"))
    with pytest.raises(ValueError, match="dict"):
        load_v2_config(_write_v2(tmp_path, "features: [food_v]\n"))
    with pytest.raises(ValueError):
        load_v2_config(_write_v2(tmp_path, "features:\n  food_v: {rho: 1e-3}\n"))


@pytest.mark.parametrize("text, match", [
    ("features:\nfood_v: {enabled: false}\n", "들여쓴다"),          # features 아래 들여쓰기를 빠뜨림
    ("feature:\n  food_v: {enabled: false}\n", "최상위"),           # 오타
])
def test_load_v2_config_rejects_unknown_top_keys(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        load_v2_config(_write_v2(tmp_path, text))


def test_v2_yaml_example_block_is_valid(cfg2):
    """configs/v2.yaml 머리 주석의 `예) food_v: {...}` 를 그대로 옮겨 쓰면 읽히고 World 가 받는다.

    예전 예시 `{enabled: true, alpha: 0.5, rho: 1.0e-3}` 는 PARAM_KEYS 에 rho 가 없고 floor 등이 빠져 실패했다.
    """
    text = (ROOT / "configs" / "v2.yaml").read_text(encoding="utf-8")
    lines = [ln.lstrip("# ")[len("예) "):] for ln in text.splitlines() if ln.lstrip("# ").startswith("예) ")]
    assert len(lines) == 1, lines
    example = yaml.safe_load(lines[0])
    f = F.parse_features(example)                          # 지금 등록부(IMPLEMENTED·PARAM_KEYS)로 검사
    assert f.active, "예시는 기능 하나를 켠 블록이다"
    for name in f.active:
        assert set(f.params(name)) == set(F.PARAM_KEYS[name]), name
    w = WorldV2(_with_features(cfg2, example), seeds=[0])   # 계수 값 검사(_food_v_params)도 통과한다
    assert w.features.active == f.active


def test_load_v2_config_overrides_only_v1_keys(tmp_path):
    p = tmp_path / "v2.yaml"
    p.write_text("overrides: {see_r: 18.0}\n", encoding="utf-8")
    assert load_v2_config(p).see_r == 18.0
    for bad in ("overrides: {features: {food_v: {enabled: false}}}\n",   # features 를 overrides 안에 둠
                "overrides: {see_radius: 18.0}\n",                        # v1 에 없는 키
                "overrides: [see_r]\n"):
        p.write_text(bad, encoding="utf-8")
        with pytest.raises(ValueError, match="overrides"):
            load_v2_config(p)
