"""시즌 코드가 가져다 쓰는 함수의 서명을 고정한다 (SEASON 4.1 "서명을 시즌 테스트로 고정한다").

다른 작업이 `env_v2/rollout.py`, `diagnose_v2.py`, `export_weights.py`, `train.py` 를 고치고 있다. 시즌 코드가 쓰는 인자
이름·종류와 돌려주는 모양이 바뀌면 여기서 먼저 실패한다. 기본값이 있는 인자가 새로 붙는 것은 허용한다.
"""

import inspect

import numpy as np
import pytest

import diagnose_v2 as dg
import export_weights as ew
import train as tr
from env_v2 import rollout as ro

P, K = inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY

# (함수, [(인자 이름, 종류)]) — 시즌 코드가 이 이름·종류로 부른다
PINNED = [
    (ro.run_specs, [("cfg", P), ("specs", P), ("seeds", P), ("steps", P), ("workers", K), ("gamma", K),
                    ("executor", K)]),
    (ro.make_executor, [("workers", P)]),
    (ro.g_gamma, [("rew", P), ("done", P), ("gamma", P), ("tail", P), ("head", P)]),
    (ro.model_gamma, [("path", P)]),
    (ro.public_row, [("r", P)]),
    (dg.paired, [("a", P), ("b", P)]),
    (dg.iqm, [("x", P)]),
    (dg.stratified_bootstrap_ci, [("scores", P), ("stat", P), ("reps", P), ("alpha", P), ("seed", P)]),
    (dg.control_specs, [("base", P), ("mean_action", P), ("names", P)]),
    (dg.model_fingerprint, [("path", P)]),
    (dg.config_digest, [("cfg", P)]),
    (dg.check_disjoint, [("what", P), ("seeds", P), ("eval_seeds", P), ("args", P)]),
    (dg.nanmean, [("v", P)]),
    (ew.extract, [("model", P)]),
    (ew.forward, [("obs", P), ("w", P)]),
    (ew.sample_observations, [("n", P), ("seed", P)]),
    (tr.make_model, [("venv", P), ("tensorboard_log", P)]),
    (tr.load_tuned, [("path", P)]),
]


@pytest.mark.parametrize("fn,params", PINNED, ids=[f"{f.__module__}.{f.__name__}" for f, _ in PINNED])
def test_pinned_signature(fn, params):
    sig = inspect.signature(fn).parameters
    for name, kind in params:
        assert name in sig, f"{fn.__name__} 에 인자 {name} 가 없다"
        assert sig[name].kind == kind, f"{fn.__name__}.{name} 종류가 바뀌었다: {sig[name].kind}"
    pinned = {n for n, _ in params}
    extra_required = [n for n, p in sig.items() if n not in pinned and p.default is inspect.Parameter.empty
                      and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)]
    assert not extra_required, f"{fn.__name__} 에 기본값 없는 인자가 새로 붙었다: {extra_required}"


def test_return_shapes():
    """돌려주는 모양: paired 의 키, control_specs 의 C1′, public_row 의 원시 열 제외, iqm·CI."""
    r = dg.paired([1.0, 2.0, 3.0], [0.0, 0.0, 0.0])
    assert {"diff", "sd", "t", "sig"} <= set(r) and r["diff"] == pytest.approx(2.0)
    spec = dg.control_specs({"kind": "learned", "model": "x.zip"}, [0.0] * 4)["C1'"]
    assert spec == {"policy": {"kind": "learned", "model": "x.zip"}, "wrap": [{"kind": "act_permute", "salt": 0}]}
    assert ro.public_row({"seed": 3, "g_gamma": 1, "_act_sum": np.zeros(4)}) == {"seed": 3, "g_gamma": 1.0}
    assert dg.iqm([1, 2, 3, 4]) == pytest.approx(2.5)
    ci = dg.stratified_bootstrap_ci(np.ones((1, 5)), reps=10)
    assert ci["lo"] == ci["hi"] == ci["point"] == 1.0
    assert ro.g_gamma(np.ones((3, 1)), np.zeros((3, 1), bool), 0.5, tail=0) > 0
