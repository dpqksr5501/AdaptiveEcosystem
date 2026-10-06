"""SR1 경로 전체를 아주 짧게 한 번 돈다: final.zip 에서 두 롤아웃 이어 학습 → K2-B 한 롤아웃 → 평가 시드 하나·짧은 롤아웃
판정 → 실행기 --dry-run. 수치 판정은 시드가 하나라 의미가 없다(모든 t 가 nan 이라 A1 은 실패한다). 형식과 연결만 본다.
"""

import json

import pytest

from env_v2.rollout import model_gamma
from season import gate as gt
from season import sr1
from season import train_season as ts
from season.common import ANCHORS
from season.eval_worlds import EvalCache

ROLLOUT = 32_768            # 세계 8 × 슬롯 128 × 세계당 32스텝


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    d = tmp_path_factory.mktemp("season_smoke")
    cand, k2b = d / "cand.zip", d / "k2b.zip"
    common = ["--anchor", "v1", "--method", "M3", "--kl-coef", "0.1", "--warmup-rollouts", "1", "--seed", "0",
              "--threads", "2"]
    assert ts.main(common + ["--season", "a", "--steps", str(2 * ROLLOUT), "--out", str(cand)]) == 0
    assert ts.main(common + ["--k2b", "--steps", str(ROLLOUT), "--out", str(k2b)]) == 0
    return d, cand, k2b


def test_train_outputs(trained):
    d, cand, k2b = trained
    meta = json.loads(cand.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["actual_timesteps"] == 2 * ROLLOUT and meta["gamma"] == model_gamma(ANCHORS["v1"])
    assert meta["anchor"]["sha1"] == "2f4d57e33107" and meta["season"]["tag"] == "a" and not meta["k2b"]
    assert [h["mode"] for h in meta["history"]] == ["warmup", "ppo+kl"]
    assert meta["history"][0]["anchor_kl_before"] == 0.0 == meta["history"][1]["anchor_kl_before"]
    assert {"reward_0G", "reward_1B"} <= set(meta["history"][0])
    assert meta["worlds"]["per_part"] == {"0G": 4, "1B": 4} and meta["ppo"]["n_steps"] == 32
    assert meta["method"]["clip_range"] == 0.1 and meta["rng"] == "reseed(seed)"
    km = json.loads(k2b.with_suffix(".json").read_text(encoding="utf-8"))
    assert km["k2b"] and km["season"] is None and km["parts"] == ["B", "B"]
    with pytest.raises(SystemExit):              # 있는 출력은 --force 없이 덮지 않는다
        ts.main(["--anchor", "v1", "--k2b", "--method", "M1", "--steps", "1", "--out", str(k2b)])
    with pytest.raises(SystemExit):              # ckpt/ 아래로는 쓰지 않는다
        ts.main(["--anchor", "v1", "--k2b", "--method", "M1", "--steps", "1", "--out",
                 str(ANCHORS["v1"].parent / "season_smoke_never.zip")])


def test_gate_one_seed(trained):
    d, cand, k2b = trained
    res = gt.run_gate(cand, ANCHORS["v1"], k2b, ANCHORS["v1"], "a", workers=1, cache=EvalCache(d / "cache"),
                      seeds=(10000,), holdout_seeds=(10020,), steps=700)
    assert set(res) >= {"A1", "A2", "A3", "A4", "A5", "pass", "reasons", "ge_sanity", "brief"}
    assert res["A5"]["pass"] and res["A5"]["max_err"] <= gt.PARITY_TOL
    assert res["ge_sanity"]["ok"]                # Ge: 아사 0·번식 0
    assert not res["pass"] and "A1 이득 없음" in res["reasons"]     # 시드 하나라 t 가 없다
    json.dumps(gt.clean(res))


def test_sr1_dry_run(capsys):
    assert sr1.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "후보 8개, K2-B 8개" in out and "평가 잡(캐시 밖)" in out
    jobs = sr1.train_jobs(sr1.plan(1, [], sr1.SR1_STEPS))
    assert len(jobs) == 16 and sum(j.is_k2b for j in jobs) == 8
    assert {(j.anchor, j.mtag) for j in jobs if not j.is_k2b} == {
        (a, m) for a in ("v1", "v20") for m in ("m1", "m2", "m3k0p1", "m3k0p5")}
    r2 = sr1.plan(2, ["M3k0.5@v20"], sr1.SR1_STEPS)
    assert {(j.season, j.seed) for j in r2} == {(s, x) for s in "abc" for x in (0, 1)}
    assert r2[0].kl == 0.5 and r2[0].k2b().season is None
    est = sr1.estimate(16, sr1.SR1_STEPS, 3, 960, 5000, 10)
    assert round(est["train_min"]) == 6 and round(est["eval_min"]) == 17     # SEASON 5.4 의 약 6분·17분
