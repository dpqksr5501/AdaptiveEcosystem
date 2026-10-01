"""v1 수치 회귀 — v1 World 가 조용히 바뀌지 않았는지 고정값으로 본다.

v1(관측 7·행동 4)은 언리얼에 연결된 계약의 원본이다. V2 작업은 별도 모듈(env_v2/)에서 하고
v1 파일은 바꾸지 않는다 (Docs/RL_Policy/RL_V2_PLAN.md 결정 3). 그 약속을 이 테스트가 지킨다.
값은 2026-10-01 에 v1 코드로 잰 것이다. 바뀌면 v1 을 누가 건드렸는지부터 본다.
"""

import pytest

from env.config import load_config
from env.world import World
from policies.registry import make_policy

PINNED = {
    "fixed": {
        "mean_return": 19.491469186394266,
        "survival": 229.59641255605382,
        "repro": 2.0625,
        "predation_rate": 0.00185546875,
        "cohesion_mean": 0.8000000000000057,
        "flee_dist_mean": 0.40000000000000285,
        "cover_frac": 0.1692578125,
        "_pos_sum": 13543.720024106395,
    },
    "utility": {
        "mean_return": 19.235249392349946,
        "survival": 249.7560975609756,
        "repro": 1.9140625,
        "predation_rate": 0.00142578125,
        "cohesion_mean": 0.5451149079203605,
        "flee_dist_mean": 0.39471272327005863,
        "flee_dist_std": 0.002726339564258778,
        "cover_frac": 0.15,
        "react_pred": 0.039151299046198774,
        "react_hunger": 0.326795925819642,
        "_pos_sum": 12723.40193382794,
    },
}
SPECS = {
    "fixed": {"kind": "fixed", "action": [0.3, 0.8, 0.4, 0.1]},
    "utility": {"kind": "utility"},
}


@pytest.mark.parametrize("name", sorted(PINNED))
def test_v1_world_matches_pinned_values(name):
    cfg = load_config()
    policy = make_policy(SPECS[name])
    w = World(cfg, seeds=[10000])
    for _ in range(400):
        w.step(policy(w.observe()))
    got = dict(w.stats())
    got["_pos_sum"] = float(w.pos.sum())
    for key, expected in PINNED[name].items():
        assert got[key] == pytest.approx(expected, rel=1e-9, abs=1e-12), key
