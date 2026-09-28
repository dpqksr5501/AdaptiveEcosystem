"""§3.3 조향 수식 검증. 이 테스트가 언리얼 C++ 이식(§9.5)의 기준이다."""

import numpy as np
import pytest

from env.config import load_config
from env.steering import clamp_magnitude, normalize, steer


@pytest.fixture
def cfg():
    return load_config()


def zero_geo(n):
    return dict(
        food_grad=np.zeros((n, 2)),
        to_centroid=np.zeros((n, 2)),
        to_cover=np.zeros((n, 2)),
        separation=np.zeros((n, 2)),
        d_pred_min=np.full(n, np.inf),
        away_from_pred=np.zeros((n, 2)),
    )


def test_normalize_leaves_zero_vectors_alone():
    v = np.array([[3.0, 4.0], [0.0, 0.0], [-1.0, 0.0]])
    out = normalize(v)
    assert np.allclose(out[0], [0.6, 0.8])
    assert np.allclose(out[1], [0.0, 0.0])      # C++ GetSafeNormal()과 같은 규약
    assert np.allclose(out[2], [-1.0, 0.0])


def test_clamp_magnitude_only_shrinks():
    v = np.array([[3.0, 4.0], [0.3, 0.4]])
    out = clamp_magnitude(v, 1.0)
    assert np.isclose(np.linalg.norm(out[0]), 1.0)
    assert np.allclose(out[1], v[1])            # 이미 1보다 작으면 그대로


def test_output_speed_is_always_herb_speed(cfg):
    """§3.3은 normalize(v) * herb_speed로 끝난다. 속도 조절 수단이 없다."""
    g = zero_geo(3)
    g["food_grad"][:] = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    a = np.full((3, 4), 0.2)
    v = steer(g, a, cfg)
    assert np.allclose(np.linalg.norm(v, axis=1), cfg.herb_speed)


def test_all_zero_input_gives_zero_velocity(cfg):
    v = steer(zero_geo(4), np.zeros((4, 4)), cfg)
    assert np.allclose(v, 0.0)


def test_each_weight_selects_its_own_geometry_term(cfg):
    """a[0]→food_grad, a[1]→to_centroid, a[3]→to_cover. 인덱스가 §3.2와 맞는가."""
    dirs = {"food_grad": 0, "to_centroid": 1, "to_cover": 3}
    for key, col in dirs.items():
        g = zero_geo(1)
        g[key][:] = [1.0, 0.0]
        a = np.zeros((1, 4))
        a[0, col] = 1.0
        assert np.allclose(steer(g, a, cfg)[0], [cfg.herb_speed, 0.0]), key
        # 다른 열을 켜도 이 항은 안 움직여야 한다
        for other in range(4):
            if other == col or other == 2:   # 2는 도주 개시 거리라 방향항이 아니다
                continue
            a2 = np.zeros((1, 4))
            a2[0, other] = 1.0
            assert np.allclose(steer(g, a2, cfg)[0], 0.0), (key, other)


def test_separation_uses_fixed_weight_not_an_action(cfg):
    """separation은 행동 가중치가 아니라 상수 1.35로 항상 들어간다 (§3.3)."""
    g = zero_geo(1)
    g["separation"][:] = [1.0, 0.0]
    v = steer(g, np.zeros((1, 4)), cfg)
    assert np.allclose(v[0], [cfg.herb_speed, 0.0])
    assert cfg.sep_weight == 1.35


def test_flee_triggers_below_threshold_distance(cfg):
    """도주 개시 조건: d_pred_min < flee_dist * see_r (§3.3)."""
    g = zero_geo(2)
    g["away_from_pred"][:] = [1.0, 0.0]
    g["d_pred_min"][:] = [0.4 * cfg.see_r - 0.01, 0.4 * cfg.see_r + 0.01]
    a = np.zeros((2, 4))
    a[:, 2] = 0.4
    v = steer(g, a, cfg)
    assert np.allclose(v[0], [cfg.herb_speed, 0.0])   # 임계 안 → 도주
    assert np.allclose(v[1], 0.0)                      # 임계 밖 → 항 없음


def test_flee_adds_and_does_not_replace(cfg):
    """§12 하지 말 것: 도주 항으로 다른 항을 대체하기. 반드시 더해야 한다."""
    g = zero_geo(1)
    g["to_centroid"][:] = [0.0, 1.0]          # 무리는 +y
    g["away_from_pred"][:] = [1.0, 0.0]       # 도주는 +x
    g["d_pred_min"][:] = 0.0
    a = np.array([[0.0, 1.0, 1.0, 0.0]])
    v = steer(g, a, cfg)[0]
    # 대체였다면 v는 정확히 +x. 가산이므로 y 성분이 살아 있어야 한다.
    assert v[1] > 0.0, "도주가 cohesion을 대체해버렸다"
    assert v[0] > v[1], "도주 가중치 3.0이 cohesion 1.0보다 커야 한다"
    expected = np.array([1.0 * cfg.flee_weight, 1.0])
    assert np.allclose(v, expected / np.linalg.norm(expected) * cfg.herb_speed)


def test_matches_literal_spec_formula(cfg):
    """§3.3 수식을 그대로 다시 써서 대조한다. 계수가 바뀌면 여기서 걸린다."""
    rng = np.random.default_rng(0)
    n = 32
    g = dict(
        food_grad=normalize(rng.normal(size=(n, 2))),
        to_centroid=normalize(rng.normal(size=(n, 2))),
        to_cover=normalize(rng.normal(size=(n, 2))),
        separation=clamp_magnitude(rng.normal(size=(n, 2)), 1.0),
        d_pred_min=rng.uniform(0, 2 * cfg.see_r, n),
        away_from_pred=normalize(rng.normal(size=(n, 2))),
    )
    a = rng.random((n, 4))

    ref = a[:, 0:1] * g["food_grad"]
    ref = ref + a[:, 1:2] * g["to_centroid"]
    ref = ref + a[:, 3:4] * g["to_cover"]
    ref = ref + 1.35 * g["separation"]
    fleeing = g["d_pred_min"] < a[:, 2] * cfg.see_r
    ref[fleeing] += g["away_from_pred"][fleeing] * 3.0
    ref = normalize(ref) * cfg.herb_speed

    assert fleeing.any() and not fleeing.all(), "두 분기가 다 밟혀야 의미 있는 테스트다"
    assert np.allclose(steer(g, a, cfg), ref, atol=1e-12)
