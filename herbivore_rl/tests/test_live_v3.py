"""실시간 적응 고리 results/v3/live/live.py (10-21 사용자 '게임 중 실시간 두뇌 교체').

- 환경 지문·건너뛰기: 같은 환경(먹이 남은 양·시각만 다름)은 같은 지문, 원판·날씨·용량·은신처가 바뀌면 다른 지문. 열쇠 = 지문 + 두뇌 가중치.
- 기록·상태 파일: os.replace 로 바꿔 넣고(잠김이면 다시), 임시 파일을 남기지 않는다. 시도·판 번호, 처리한 열쇠, 깨진 기록.
- 세계 셋: G(게임) 늑대 포만 켬, N(판정) 끔, T(학습) 끔. 시작 모델: R1b-F(관측 18) → 관측 21 + 0 열, 관측 21 두뇌 파일 → 그 zip, 그 밖은 거부.
- 관문: 짜 맞춘 판정 판으로 통과·1차 기각·지킴 기각·재현 확인. 10-21 (3) 1차 = 쫓긴 시간(스스로 벗어난 도망): 짧으면 통과, 같거나 길면 기각, 최소 차이 δ,
  덜 잡혀도 1차는 쫓긴 시간, 더 잡히면 GN_caught, 도망을 잘게 쪼개면 GF, 더 오래 달리면 GV, 잡힘·잘림으로 끝난 도망이 늘면 GC, 게임 세계 쫓긴 시간 GG_chase,
  스스로 벗어난 도망이 없는 시드는 짝에서 빠짐(기록), 옛 꼴 기록 거부. 도주 반사를 끈 스냅숏 거부, 크기 확정 전 실제 폴더 거부.
  예비 측정 쫓긴 시간 짝·도주 비용 사본·기준 크기 재기.
  두뇌 파일 adapt 블록·이름·다시 읽기. 그만둠: 가짜 판 프로세스 나무를 끝낸다.
- 감시 정리: 두뇌 파일을 쓴 뒤 끝난 판은 내보냄(판 번호·두 열쇠), 오류는 같은 스냅숏으로 ERROR_RETRY 번까지, 폴더마다 잠금 하나, 남은 학습 프로세스 끝내기.
  관문은 시드 하나면 기각. state.json 은 잠깐 잠기면 다시 읽는다. 예비 측정 f_dec 는 스냅숏 먹이 지도(T 세계 그대로).
- 관문 상수 = LIVE_GATE.md.
학습·판정 세계를 돌리지 않는다(내보내기 골든 600 스텝, 도주 비용 기준 크기 T 세계 셋 × 20 스텝만). 시드는 관문 범위 이름만 쓰고 세계를 돌리지 않는다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import json
import math
import os
import subprocess
import sys
import time
from argparse import Namespace
from pathlib import Path

import numpy as np
import pytest

from env.config import ROOT

LIVE_DIR = ROOT / "results" / "v3" / "live"
SNAP = ROOT / "results" / "v3" / "adapt" / "unreal" / "eco_v3_snapshot_s20003_240s.json"
ECOBRAINS = ROOT.parent / "AdaptiveEcosystem" / "EcoBrains"
OBS21_FILE = ECOBRAINS / "v3_r1_g995_s3_obs21zero.json"
R4_FILE = ECOBRAINS / "v3_r4_g995_s0_20m.json"

pytestmark = [pytest.mark.filterwarnings("ignore:You have specified a mini-batch size"),
              pytest.mark.skipif(not (ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip").exists(), reason="관측 21 시작 모델 zip 이 없다 (저장소 밖 ckpt)")]

if str(LIVE_DIR) not in sys.path:
    sys.path.insert(0, str(LIVE_DIR))


@pytest.fixture(scope="module")
def lv():
    import live

    return live


@pytest.fixture(scope="module")
def snap(lv):
    return lv.read_snapshot(SNAP)


@pytest.fixture(scope="module")
def prepared(lv, snap, tmp_path_factory):
    rd = tmp_path_factory.mktemp("round") / "a1_test_e0"
    return lv.prepare(SNAP, snap, rd, lv.BRAIN_FOLDERS)


# --------------------------------------------------------------------- #
# 작은 도구·지문·건너뛰기
# --------------------------------------------------------------------- #


def test_t_crit(lv):
    assert lv.t_crit(99) == pytest.approx(1.984, abs=5e-4)
    assert lv.t_crit(39) == pytest.approx(2.0227, abs=5e-4)
    assert lv.t_crit(2) == pytest.approx(4.303, abs=5e-4)
    assert math.isinf(lv.t_crit(0))
    for df in (2, 5, 10, 19, 25, 39, 45, 99, 150, 1000):
        assert lv.t_crit_table(df) == pytest.approx(lv.t_crit(df), abs=2e-3)       # scipy 가 없을 때의 표


def test_env_digest(lv, snap):
    d0, k0 = lv.env_digest(snap), lv.pair_key(snap)
    s = copy.deepcopy(snap)
    s["global_step"], s["sim_seconds"] = 9000, 1200.0
    for r in s["regions"]:
        r["food"]["food"] = [0.0] * len(r["food"]["food"])               # 먹이 남은 양·사슴 수는 환경이 아니다
        r["deer"]["caught"] += 5
    assert lv.env_digest(s) == d0 and lv.pair_key(s) == k0
    edits = [lambda s: s["regions"][1]["obstacles"]["discs"].append([10.0, 10.0, 0.4]),          # 메마른 땅 나무 하나
             lambda s: s["regions"][0]["world"]["weather"].update(kind="snow"),
             lambda s: s["regions"][2]["world"]["weather"].update(intensity=0.5),
             lambda s: s["regions"][0]["food"]["cap"].__setitem__(5, 0.123),
             lambda s: s["regions"][0]["covers"][0].__setitem__(2, 5.0)]
    for e in edits:
        s = copy.deepcopy(snap)
        e(s)
        assert lv.env_digest(s) != d0
    s = copy.deepcopy(snap)
    s["brain"]["weights_sha256"] = "11" * 32
    assert lv.env_digest(s) == d0 and lv.pair_key(s) != k0                # 두뇌만 다르면 열쇠가 다르다
    s2 = json.loads(json.dumps(snap))
    s2["play_id"] = "p20261021T062000_0badcafe"
    assert lv.env_digest(s2) == d0 and lv.pair_key(s2) != k0 and lv.pair_key(s2).endswith("|p20261021T062000_0badcafe")   # 새 Play = 새 판


def test_decide_and_dedup(lv):
    st = lv.new_state()
    assert lv.decide("k1", None, st) == "start"
    assert lv.decide("k1", "k1", st) == "keep"
    assert lv.decide("k2", "k1", st) == "supersede"
    st["processed"].append(dict(key="k1", state="rejected"))
    assert lv.decide("k1", None, st) == "skip"
    st["processed"].append(dict(key="k3", state="error"))
    assert lv.decide("k3", None, st) == "start"                            # 오류 한 번은 다시 한다
    st["processed"].append(dict(key="k3", state="error"))
    assert lv.decide("k3", None, st) == "skip"
    st["processed"].append(dict(key="k4", state="adopted"))                # 내보낸 두뇌 + 같은 환경
    assert lv.decide("k4", None, st) == "skip"


def test_state_and_status_files(lv, tmp_path, monkeypatch):
    root = tmp_path / "EcoAdapt"
    assert lv.begin_attempt(root) == 1 and lv.begin_attempt(root) == 2
    lv.finish_attempt(root, dict(state="rejected", attempt=1, key="kA", snapshot="a.json", last_result="기각: 1차 t −0.5 (문턱 −2.02)"))
    st = lv.finish_attempt(root, dict(state="exported", attempt=2, key="kB", round=1, env_digest="dB", exported_weights_sha256="ff" * 32,
                                      snapshot="b.json", last_result="통과: 판 1"))
    assert st["round"] == 1 and st["attempt"] == 2
    keys = [p["key"] for p in st["processed"]]
    assert keys == ["kA", "kB", lv.pair_key_of("dB", "ff" * 32)]
    lv.finish_attempt(root, dict(state="superseded", attempt=3, key="kC"))
    st = lv.load_state(root)
    assert "kC" not in [p["key"] for p in st["processed"]] and [h["state"] for h in st["history"]] == ["rejected", "exported", "superseded"]
    assert st["last_result"] == "통과: 판 1"

    s = lv.Status(root)
    s.set(state="training", provider=lambda: ("학습 중 0.4M/1M (모델 1개)", 0.4))
    d = json.loads((root / "status.json").read_text(encoding="utf-8"))
    assert d["format"] == "eco_v3_live_status" and d["version"] == 1 and d["state"] == "training" and d["round"] == 1
    assert d["message"] == "학습 중 0.4M/1M (모델 1개)" and d["progress"] == 0.4 and abs(d["updated_unix"] - time.time()) < 60
    assert set(d) >= {"format", "version", "updated_unix", "pid", "state", "attempt", "round", "snapshot", "env", "message", "progress", "last_result"}
    assert not list(root.rglob("*.tmp"))

    real, calls = os.replace, [0]

    def flaky(a, b):                                                       # 언리얼이 잠깐 열고 있다
        calls[0] += 1
        if calls[0] <= 2:
            raise PermissionError("잠김")
        return real(a, b)

    monkeypatch.setattr(lv.os, "replace", flaky)
    lv.atomic_write_json(root / "x.json", {"a": 1})
    monkeypatch.setattr(lv.os, "replace", real)
    assert calls[0] == 3 and json.loads((root / "x.json").read_text(encoding="utf-8")) == {"a": 1} and not list(root.rglob("*.tmp"))

    sp, real_rt, n = lv.state_path(root), lv.Path.read_text, [0]

    def flaky_read(self, *a, **kw):                                          # 다른 프로세스가 os.replace 하는 순간 (잠김)
        if self == sp and n[0] > 0:
            n[0] -= 1
            raise PermissionError("잠김")
        return real_rt(self, *a, **kw)

    monkeypatch.setattr(lv.Path, "read_text", flaky_read)
    monkeypatch.setattr(lv.time, "sleep", lambda s: None)
    n[0] = 2
    assert lv.load_state(root)["round"] == 1 and n[0] == 0                   # 다시 읽는다 — 새로 시작하지 않는다
    n[0] = 10 ** 6
    with pytest.raises(PermissionError):                                     # 끝내 못 읽으면 오류 (기록을 지우지 않는다)
        lv.load_state(root)
    monkeypatch.setattr(lv.Path, "read_text", real_rt)
    assert not list((root / "live").glob("state.json.bad_*")) and lv.load_state(root)["round"] == 1

    lv.state_path(root).write_text("{깨짐", encoding="utf-8")
    assert lv.load_state(root)["attempt"] == 0
    assert list((root / "live").glob("state.json.bad_*"))


def test_snapshot_reading(lv, tmp_path, snap):
    p = tmp_path / "eco_v3_snapshot_s1_t2_e0.json"
    text = json.dumps(snap)
    p.write_text(text[: len(text) // 2], encoding="utf-8")                # 덜 쓰인 파일
    with pytest.raises(ValueError):
        lv.read_snapshot(p)
    p.write_text(json.dumps(dict(snap, version=2)), encoding="utf-8")
    with pytest.raises(lv.ad.Refused):
        lv.read_snapshot(p)
    p.write_text(text, encoding="utf-8")
    assert lv.pair_key(lv.read_snapshot(p)) == lv.pair_key(snap)
    (tmp_path / "x.json.tmp").write_text("{}", encoding="utf-8")
    os.utime(tmp_path / "x.json.tmp", (time.time() + 60, time.time() + 60))
    assert lv.newest_snapshot(tmp_path) == p                               # *.tmp 는 보지 않는다


def test_env_summary_and_r(lv, snap):
    assert lv.env_summary(snap) == "환경 그대로"
    ok, why = lv.r_applicable(snap)
    assert ok and why == ""
    s = copy.deepcopy(snap)
    s["env"] = dict(watch=True, revision=2, changed_step=1530, first_changed_step=900, trigger="env_change", changes=[
        dict(revision=1, step=900, seconds=120.0, region="Barren", kind="trees", detail="나무 0→12 (+12 −0)", source="level"),
        dict(revision=2, step=1530, seconds=204.0, region="Barren", kind="trees", detail="나무 12→20 (+8 −0)", source="level"),
        dict(revision=2, step=1530, seconds=204.0, region="Forest", kind="weather", detail="비 1.00→눈 1.00", source="cvar:eco.IntegratedV3.WeatherForest")])
    next(r for r in s["regions"] if r["region"] == "Forest")["world"]["weather"].update(kind="snow", intensity=1.0)
    assert lv.env_summary(s) == "Barren 나무 0→20 · Forest 눈 1.0"
    ok, why = lv.r_applicable(s)
    assert not ok and why.startswith("중간 변화로 재현 확인 없음")
    s = copy.deepcopy(snap)
    s["brain"]["last_swap_step"] = 900
    assert lv.r_applicable(s)[0] is False
    assert lv.make_run_id(5, s).startswith("a5_") and lv.make_run_id(5, s).endswith("_e0")


# --------------------------------------------------------------------- #
# 시작 모델·세계 셋
# --------------------------------------------------------------------- #


def test_start_resolution(lv, snap, tmp_path):
    r = lv.resolve_start(snap, lv.BRAIN_FOLDERS)                          # 내장 R1b-F (관측 18, 옛 스냅숏 — brain.contract_hash 없음)
    assert r["zip"] == lv.OBS21ZERO and r["current_model"] == lv.ad.R1BF and r["obs_dim"] == 18
    assert r["brain_contract"] == lv.CONTRACT_OBS18 and r["start_contract"] == lv.CONTRACT_OBS21
    obs21 = json.loads(OBS21_FILE.read_text(encoding="utf-8"))
    s = copy.deepcopy(snap)
    s["brain"].update(id=obs21["id"], weights_sha256=obs21["weights_sha256"], obs_dim=21, contract_hash=lv.CONTRACT_OBS21, builtin=False)
    r = lv.resolve_start(s, lv.BRAIN_FOLDERS)                             # 관측 21 두뇌 파일 → 그 zip
    assert r["zip"].resolve() == lv.OBS21ZERO.resolve() and r["obs_dim"] == 21
    folder = tmp_path / "brains"
    folder.mkdir()
    (folder / "x.json").write_text(json.dumps(dict(weights_sha256=obs21["weights_sha256"], model=dict(path=lv.OBS21ZERO.resolve().as_posix()))),
                                   encoding="utf-8")
    assert lv.find_brain_zip(obs21["weights_sha256"], [folder]).resolve() == lv.OBS21ZERO.resolve()     # 절대 경로 model.path
    bad = copy.deepcopy(s)
    bad["brain"]["contract_hash"] = lv.CONTRACT_OBS18
    with pytest.raises(lv.ad.Refused, match="계약 해시"):
        lv.resolve_start(bad, lv.BRAIN_FOLDERS)
    bad = copy.deepcopy(s)
    bad["brain"]["weights_sha256"] = "00" * 32
    with pytest.raises(lv.ad.Refused, match="찾지 못했다"):
        lv.resolve_start(bad, lv.BRAIN_FOLDERS)
    if R4_FILE.exists():
        r4 = json.loads(R4_FILE.read_text(encoding="utf-8"))
        bad = copy.deepcopy(snap)
        bad["brain"].update(weights_sha256=r4["weights_sha256"], builtin=False, obs_dim=18)
        with pytest.raises(lv.ad.Refused, match="R1b-F 가 아닌"):
            lv.resolve_start(bad, lv.BRAIN_FOLDERS)


def test_worlds_satiation(lv, prepared):
    import yaml

    from env_v2.config import load_v2_config
    from env_v2.rep_policy import rep_params

    rd = prepared["dir"]
    world = yaml.safe_load((rd / "world.yaml").read_text(encoding="utf-8"))
    train = yaml.safe_load((rd / "train.yaml").read_text(encoding="utf-8"))
    assert world["features"]["wild_satiation"]["enabled"] is True          # G: 게임 그대로
    assert train["features"]["wild_satiation"]["enabled"] is False         # T: 학습할 때는 끈다
    assert world["features"]["obstacle_obs"]["enabled"] is True            # 관측 21 거울
    assert "flight_cost" not in train["features"]["wild_flight"]           # 도주 비용 끔(LIVE train_flight_cost 0) = train.yaml 그대로
    assert world["features"]["integrated_stage"]["respawn"] is False and train["features"]["integrated_stage"]["respawn"] is True
    assert train["overrides"]["train_seeds"] == [32000, 32050]
    mix = train["train"]["region_mix"]
    assert "random_forest" not in mix and mix["regions"] == ["Forest", "Barren", "Highland"]
    assert mix["obstacles"]["Forest"] == prepared["regions"]["Forest"]["discs"]
    rep = rep_params(load_v2_config(rd / "train.yaml"))
    assert rep["f_dec"] == pytest.approx(0.858922) and rep["cat_ent_coef"] == pytest.approx(0.01)
    rec = json.loads((rd / "convert.json").read_text(encoding="utf-8"))
    assert rec["anchor"] == "ckpt/v3/v3_r1_g995_s3_obs21zero.zip" and rec["template"] == "configs/v3_wild3_obs_mirror.yaml"
    assert rec["live"]["satiation_game"] is True and rec["live"]["env"]["revision"] == 0
    info = dict(record=rec, regions=prepared["regions"], dir=rd)
    g = lv.eval_items(info, "current", lv.OBS21ZERO, [35000], 10, "G")
    n = lv.eval_items(info, "current", lv.OBS21ZERO, [35000], 10, "N")
    assert len(g) == len(n) == 3 and all(k == "world" for k, _, _ in g + n)
    assert all(j["cfg"]["v2"]["features"]["wild_satiation"]["enabled"] is True for _, _, j in g)
    assert all(j["cfg"]["v2"]["features"]["wild_satiation"]["enabled"] is False for _, _, j in n)   # N: 포만 없는 세계
    assert [t for _, t, _ in n] == ["current:N"] * 3
    st = lv.stuck_items(info, "current", lv.OBS21ZERO, [35000], 10)
    assert all("diag" not in j and "log_every" not in j and j["cfg"]["v2"]["features"]["wild_satiation"]["enabled"] for _, _, j in st)


def test_refuse_without_wild_flight(lv, snap, tmp_path):
    """도주 반사(wild_flight)를 끈 스냅숏은 학습 전에 거부한다 — 관문 1차·지킴이 도망 기록을 쓴다(학습·판정을 헛돌지 않는다)."""
    s2 = copy.deepcopy(snap)
    for r in s2["regions"]:
        r["world"]["wild_flight"]["enabled"] = False
    with pytest.raises(lv.ad.Refused, match="도주 반사"):
        lv.prepare(SNAP, s2, tmp_path / "a_nf", lv.BRAIN_FOLDERS)
    assert not (tmp_path / "a_nf" / "train.yaml").exists()


def test_flight_cost_variant_and_scale(lv, prepared, snap, tmp_path):
    """도주 비용: prepare(flight_cost) 와 예비 측정 사본 train_fc<값>.yaml 은 T 세계에 wild_flight.flight_cost 만 더한다(0 이면 뺀다). 기준 크기 재기
    (scale)는 T 세계 지역마다 그 지역 스냅숏 먹이 지도로 돈다."""
    import yaml

    from env_v2.config import load_v2_config
    from env_v2.world import World

    rd = prepared["dir"]
    base = yaml.safe_load((rd / "train.yaml").read_text(encoding="utf-8"))
    p = lv.train_variant(rd, 0.005)
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert p.name == "train_fc0.005.yaml" and d["features"]["wild_flight"]["flight_cost"] == 0.005
    d["features"]["wild_flight"].pop("flight_cost")
    assert d == base                                                       # 다른 칸은 그대로
    assert World(load_v2_config(p).replace(N=8), seeds=[32000])._wf["flight_cost"] == 0.005
    assert "flight_cost" not in yaml.safe_load(lv.train_variant(rd, 0.0).read_text(encoding="utf-8"))["features"]["wild_flight"]
    with pytest.raises(ValueError):
        lv.train_variant(rd, -1.0)
    rd2 = tmp_path / "a2_fc"
    info2 = lv.prepare(SNAP, snap, rd2, lv.BRAIN_FOLDERS, flight_cost=0.01)
    t2 = yaml.safe_load((rd2 / "train.yaml").read_text(encoding="utf-8"))
    assert t2["features"]["wild_flight"]["flight_cost"] == 0.01 and info2["record"]["live"]["flight_cost"] == 0.01
    assert (rd2 / "train.yaml").read_text(encoding="utf-8").splitlines()[2].endswith("도주 비용 wild_flight.flight_cost 0.01")
    items = lv.scale_items(prepared, lv.OBS21ZERO, [32000], 20)
    assert sorted(j["region"] for _, _, j in items) == sorted(prepared["regions"]) and all(k == "scale" for k, _, _ in items)
    rows = [lv._job(it)[1] for it in items]
    s = lv.scale_summary(rows, rd / "train.yaml")
    assert s["worlds"] == 3 and s["deer_steps"] == sum(r["steps"] for r in rows) > 0
    assert s["metabolic"]["run"] == pytest.approx(0.002 * 2.5) and s["metabolic"]["walk"] == pytest.approx(0.002)   # 뛰기 대사 2.5 배, 걷기 = v1
    assert s["run_extra_over_stop"] == pytest.approx(0.002 * (2.5 - 15 / 21))


def test_plan_guard(lv, tmp_path, monkeypatch):
    def ns(**kw):
        base = dict(root=str(tmp_path), workers=4, ckpt=None, steps=None, model_seeds=None, horizon=None, judge_seeds=None, select_seeds=None,
                    stuck_seeds=None, check_seeds=None, skip_check=False, force_export=False, horizon_g=None, judge_seeds_g=None, flight_cost=None)
        return Namespace(**(base | kw))

    pl = lv.plan_from_args(ns())
    assert not pl["test"] and pl["judge"] == lv.LIVE["judge_seeds"] and pl["steps"] == lv.LIVE["train_steps"]
    assert pl["flight_cost"] == lv.LIVE["train_flight_cost"] == 0.0 and "--flight-cost" not in lv.plan_args(pl)
    pl = lv.plan_from_args(ns(flight_cost=0.005))                           # 도주 비용은 관문 상수와 다르면 시험 크기
    assert pl["test"] and pl["flight_cost"] == 0.005 and lv.plan_args(pl)[-2:] == ["--flight-cost", "0.005"]
    with pytest.raises(SystemExit):
        lv.plan_from_args(ns(flight_cost=-0.1))
    pl = lv.plan_from_args(ns(steps=20000, judge_seeds="35000-35002", horizon=300))
    assert pl["test"] and pl["judge"] == (35000, 35002)
    assert "--steps" in lv.plan_args(pl) and "--judge-seeds" in lv.plan_args(pl)
    pl = lv.plan_from_args(ns(judge_seeds_g="35000-35002", horizon_g=300))     # G 세계 크기는 따로 (10-21 확정)
    assert pl["test"] and pl["judge_g"] == (35000, 35002) and pl["horizon_g"] == 300 and pl["judge"] == lv.LIVE["judge_seeds"]
    assert "--judge-seeds-g" in lv.plan_args(pl) and "--horizon-g" in lv.plan_args(pl) and "--judge-seeds" not in lv.plan_args(pl)
    with pytest.raises(SystemExit):
        lv.plan_from_args(ns(root=str(lv.DEFAULT_ROOT), steps=20000))     # 시험 크기는 실제 폴더에서 받지 않는다
    assert lv.LIVE["flight_sizes_confirmed"] is False                      # 10-21 (3) 쫓긴 시간 기준의 크기는 예비 측정 뒤 확정
    with pytest.raises(SystemExit, match="예비 측정으로 확정하지 않았다"):
        lv.plan_from_args(ns(root=str(lv.DEFAULT_ROOT)))                   # 확정 전에는 관문 크기여도 실제 폴더에서 판·감시를 돌리지 않는다
    monkeypatch.setitem(lv.LIVE, "flight_sizes_confirmed", True)
    assert not lv.plan_from_args(ns(root=str(lv.DEFAULT_ROOT)))["test"]
    monkeypatch.setitem(lv.LIVE, "flight_sizes_confirmed", False)
    with pytest.raises(SystemExit):
        lv.plan_from_args(ns(judge_seeds="34900-34902"))                   # 예비 측정 시드는 관문에 쓰지 않는다
    for kw in (dict(judge_seeds="35000"), dict(judge_seeds_g="35000-35000"), dict(select_seeds="35100-35100")):
        with pytest.raises(SystemExit, match="2개 이상"):                   # 시드 하나로는 짝 t 를 셀 수 없다
            lv.plan_from_args(ns(**kw))
    assert lv.inside((34900, 34999), lv.PILOT_SEEDS) and not lv.inside((34990, 35001), lv.PILOT_SEEDS)


# --------------------------------------------------------------------- #
# 관문
# --------------------------------------------------------------------- #


def _flight(chase_s, own, started, step_s, live=100000, flee=0.08, unsafe=2):
    """세계 하나의 도망 기록(짜 맞춤, World.flight_stats 꼴): 스스로 벗어난 도망 own 개(은신처 ½·원판 ¼·반경 나머지)의 쫓긴 시간 평균 chase_s 초,
    잡힘 unsafe − 1·잘림 1, 나머지 시작은 바꿈(쫓긴 3 스텝)·안 쫓김 반반(시작 = 까닭 수 합). 산 사슴-스텝 live, 실행 FLEE 몫 flee(반사 = 그 ¾)."""
    tot = int(round(chase_s / step_s * own))
    cv, ob = own // 2, own // 4
    rest = max(started - own - unsafe, 0)
    sw = rest // 2
    n = dict(cover=cv, obstacle=ob, fov=0, range=own - cv - ob, switch=sw, stop=0, held=0, unchased=rest - sw, caught=unsafe - 1, starved=0, truncated=1)
    c_cv, c_ob = tot * cv // max(own, 1), tot * ob // max(own, 1)
    contact = dict(cover=c_cv, obstacle=c_ob, fov=0, range=tot - c_cv - c_ob, switch=3 * sw, stop=0, held=0, unchased=0, caught=30 * n["caught"], starved=0,
                   truncated=2)
    steps = {k: contact[k] + 5 * n[k] for k in n}
    fs = int(flee * live)
    return dict(started=sum(n.values()), live_steps=live, flee_steps=fs, reflex_steps=fs * 3 // 4, n=n, steps=steps, contact=contact,
                own_n=own, own_steps=sum(steps[c] for c in ("cover", "obstacle", "fov", "range")), own_contact=tot, shelter_end=cv,
                hist=[own, 0, 0, 0, 0, 0, 0, 0], hist_edges=[8, 15, 38, 75, 150, 300, 600])


def _fake(seeds, caught, starved=lambda s, r: 10, shelter=0.06, beh=(0.88, 0.08, 0.04, 0, 0), cover=0, regions=("A", "B"),
          chase=lambda s, r: 6.0, own=lambda s, r: 20, started=lambda s, r: 40, flee=lambda s, r: 0.08, unsafe=lambda s, r: 2):
    W = []
    for s in seeds:
        for r in regions:
            c, st, live = int(caught(s, r)), int(starved(s, r)), 100000
            W.append(dict(seed=s, region=r, n=128, caught=c, starved=st, alive=128 - c - st, shelter_steps=int(shelter * live), live_steps=live,
                          beh_steps=[int(b * live) for b in beh], catch_cover=cover, hunt=dict(ends=10, success=6),
                          flight=_flight(chase(s, r), int(own(s, r)), int(started(s, r)), 2.0 / 15.0, live, flee(s, r), int(unsafe(s, r)))))
    return dict(meta={}, worlds=W)


def test_gate_decisions(lv, monkeypatch):
    rng = np.random.default_rng(34900)
    seeds = list(range(35000, 35040))
    base = {(s, r): int(rng.integers(25, 30)) for s in seeds for r in ("A", "B")}
    fl = {(s, r): float(rng.uniform(4.0, 8.0)) for s in seeds for r in ("A", "B")}
    cb = lambda s, r: base[(s, r)]                                                        # noqa: E731
    cf = lambda s, r: fl[(s, r)]                                                          # noqa: E731
    shorter = (lambda s, r: fl[(s, r)] - (0.5 if (s + (r == "A")) % 2 else 1.5))         # 쫓긴 시간이 0.5~1.5 초 짧다
    cur = _fake(seeds, cb, chase=cf)
    stuck0 = dict(summary=dict(deer_stuck=0, wolf_stuck=1, wolf_wall_stuck=3, worlds=15))
    stuck = dict(current=stuck0, candidate=stuck0)
    skip = dict(ok=None, why="중간 변화로 재현 확인 없음 (환경 #1)")

    def ev(n_cand, g_cand, n_cur=cur, g_cur=cur):
        return dict(N=dict(current=n_cur, candidate=n_cand), G=dict(current=g_cur, candidate=g_cand))

    good = _fake(seeds, cb, chase=shorter)
    g = lv.gate_live(ev(good, cur), stuck, skip)
    assert g["verdict"] == "통과" and g["passed"] and g["n"] == 40 and g["n_flight"] == 40 and g["t_crit_flight"] == pytest.approx(2.0227, abs=5e-4)
    p1 = g["criteria"]["P1_N_chase"]
    assert p1["ok"] and p1["diff"] == pytest.approx(-1.0, abs=0.02) and p1["dropped"] == [] and "P1_N_caught" not in g["criteria"]
    assert all(g["criteria"][k]["ok"] for k in ("GN_caught", "GF_flight_starts", "GV_flee_time", "GC_flight_unsafe", "GG_chase"))
    assert g["criteria"]["R_check"]["skipped"]
    assert g["summary"].startswith("포만 없는 세계 쫓긴 시간 ") and "초 (t −" in g["summary"] and g["summary"].endswith(", 잡힘·도망 나빠짐 없음")
    rep = g["report"]
    fN = rep["flight"]["N"]
    assert set(rep["flight"]) == {"N", "G"} and fN["candidate"]["own_contact_s"] < fN["current"]["own_contact_s"]
    assert fN["current"]["share"]["cover"] == pytest.approx(10 / 40) and fN["current"]["truncated_share"] == pytest.approx(1 / 40)
    assert fN["current"]["own_share"] == pytest.approx(20 / 40) and fN["current"]["unsafe_share"] == pytest.approx(2 / 40)
    assert fN["current"]["starts_per_1k"] == pytest.approx(0.4) and fN["current"]["shelter_end_share"] == pytest.approx(10 / 38)
    assert fN["candidate"]["flee_share"] == pytest.approx(0.08) and fN["candidate"]["self_flee_share"] == pytest.approx(0.02)
    assert "flee_share" not in rep and "flight_G" not in rep
    md = lv.fmt_flight(g)
    assert "쫓긴 시간 초 (스스로 벗어남, 전체 합)" in md and "1차 P1 (시드마다 평균을 낸 뒤 평균" in md and "짝 시드 40 (빠진 시드 0)" in md
    assert "실행 FLEE 몫 (반사 포함)" in md and "스스로 고른 FLEE 몫" in md and "G 쫓긴 시간 (지킴 GG_chase" in md
    # 같은 두뇌 = 쫓긴 시간이 짧아지지 않음 → 1차 기각 (잡힘이 같아도)
    g = lv.gate_live(ev(cur, cur), stuck, skip)
    assert g["verdict"] == "기각" and "P1" in g["why"] and g["brief"].startswith("1차 쫓긴 시간 ") and "(문턱 −2.02)" in g["brief"]
    # 더 긴 쫓긴 시간 → 1차 기각
    g = lv.gate_live(ev(_fake(seeds, cb, chase=lambda s, r: fl[(s, r)] + 1.0), cur), stuck, skip)
    assert g["verdict"] == "기각" and not g["criteria"]["P1_N_chase"]["ok"] and g["criteria"]["P1_N_chase"]["t"] > 0
    # 최소 차이 δ: 평균 1 초 짧아도 δ 1.5 초를 못 넘으면 1차 기각
    monkeypatch.setitem(lv.LIVE, "flight_min_effect_s", 1.5)
    g = lv.gate_live(ev(good, cur), stuck, skip)
    assert g["verdict"] == "기각" and "최소 차이 −1.5초" in g["why"] and "≤ −1.5초" in g["criteria"]["P1_N_chase"]["rule"]
    monkeypatch.setitem(lv.LIVE, "flight_min_effect_s", 0.5)
    assert lv.gate_live(ev(good, cur), stuck, skip)["verdict"] == "통과"
    monkeypatch.setitem(lv.LIVE, "flight_min_effect_s", 0.0)
    # 쫓긴 시간은 짧지만 더 잡힘 (옛 1차가 이제 지킴) → GN_caught 기각
    more = lambda s, r: base[(s, r)] + (1 if (s + (r == "A")) % 2 else 2)                # noqa: E731
    g = lv.gate_live(ev(_fake(seeds, more, chase=shorter), cur), stuck, skip)
    assert g["verdict"] == "기각" and "GN_caught" in g["why"] and g["criteria"]["P1_N_chase"]["ok"]
    assert g["brief"].startswith("지킴 GN_caught (t +")
    # 덜 잡혀도 1차는 쫓긴 시간이다
    less = lambda s, r: base[(s, r)] - (1 if (s + (r == "A")) % 2 else 0)                # noqa: E731
    g = lv.gate_live(ev(_fake(seeds, less, chase=cf), cur), stuck, skip)
    assert g["verdict"] == "기각" and "P1" in g["why"] and g["criteria"]["GN_caught"]["ok"]
    # 짧게 자주 도망 (1000 산 사슴-스텝당 시작이 유의하게 많다) → GF 기각
    g = lv.gate_live(ev(_fake(seeds, cb, chase=shorter, started=lambda s, r: 50 + (s % 3)), cur), stuck, skip)
    assert g["verdict"] == "기각" and "GF_flight_starts" in g["why"] and g["criteria"]["P1_N_chase"]["ok"]
    # 더 오래·일찍 달림 (실행 FLEE 몫이 유의하게 많다 — 두뇌가 반사 전에 스스로 달아나도 센다) → GV 기각
    g = lv.gate_live(ev(_fake(seeds, cb, chase=shorter, flee=lambda s, r: 0.10 + 0.01 * (s % 2)), cur), stuck, skip)
    assert g["verdict"] == "기각" and g["why"] == "지킴 기준 실패: GV_flee_time" and g["criteria"]["P1_N_chase"]["ok"]
    # 긴 추격이 잡힘·잘림으로 끝나 1차 평균에서 빠짐 (잡힘·굶음·잘림으로 끝난 도망 몫이 유의하게 많다) → GC 기각
    g = lv.gate_live(ev(_fake(seeds, cb, chase=shorter, unsafe=lambda s, r: 4 + (s % 2)), cur), stuck, skip)
    assert g["verdict"] == "기각" and "GC_flight_unsafe" in g["why"] and g["criteria"]["P1_N_chase"]["ok"]
    # 게임 세계 G 에서 쫓긴 시간이 길어짐 → GG_chase 기각
    g = lv.gate_live(ev(good, _fake(seeds, cb, chase=lambda s, r: fl[(s, r)] + 1.0)), stuck, skip)
    assert g["verdict"] == "기각" and g["why"] == "지킴 기준 실패: GG_chase"
    # 스스로 벗어난 도망이 없는 시드는 짝에서 빠진다 (빠진 수를 적는다) — 남은 시드로 판단
    some = lambda s, r: 0 if s in (35001, 35002, 35003) else 20                           # noqa: E731
    g = lv.gate_live(ev(_fake(seeds, cb, chase=shorter, own=some), cur), stuck, skip)
    assert g["n_flight"] == 37 and g["dropped_flight"] == [35001, 35002, 35003] and g["n"] == 40
    assert g["t_crit_flight"] == pytest.approx(lv.t_crit(36)) and g["criteria"]["P1_N_chase"]["n"] == 37
    assert "빠진 시드 3" in g["criteria"]["P1_N_chase"]["rule"] and "빠진 시드 3: 35001, 35002, 35003" in lv.fmt_flight(g)
    # 한 시드만 남으면 짝 t 를 셀 수 없다 — 기각
    one_left = lambda s, r: 20 if s == 35000 else 0                                       # noqa: E731
    g = lv.gate_live(ev(_fake(seeds, cb, chase=shorter, own=one_left), cur), stuck, skip)
    assert g["verdict"] == "기각" and "쫓긴 시간을 잴 시드 1개" in g["why"] and g["brief"] == "쫓긴 시간 잴 시드 1개 (2개 이상)"
    # 지킴은 그대로
    g = lv.gate_live(ev(good, _fake(seeds, cb, starved=lambda s, r: 14, chase=cf)), stuck, skip)
    assert g["verdict"] == "기각" and "GG_starved" in g["why"]                 # 게임 세계에서 더 굶는다
    g = lv.gate_live(ev(_fake(seeds, cb, starved=lambda s, r: 14, chase=shorter), cur), stuck, skip)
    assert g["verdict"] == "기각" and "GN_starved" in g["why"]
    g = lv.gate_live(ev(good, _fake(seeds, cb, cover=1, chase=cf)), stuck, skip)
    assert "G4_catch_in_shelter" in g["why"]
    stuck_bad = dict(summary=dict(deer_stuck=2, wolf_stuck=1, wolf_wall_stuck=3, worlds=15))
    g = lv.gate_live(ev(good, cur), dict(current=stuck0, candidate=stuck_bad), skip)
    assert "G5_stuck" in g["why"]
    g = lv.gate_live(ev(good, cur), None, skip)
    assert g["verdict"] == "기각" and "G5_stuck" in g["why"]                   # 끼임 세기가 없으면 통과가 아니다
    g = lv.gate_live(ev(good, _fake(seeds, cb, shelter=0.2, chase=cf)), stuck, skip)
    assert "G6_no_exploit" in g["why"]
    g = lv.gate_live(ev(good, cur), stuck, dict(ok=False, steps=1800))
    assert g["verdict"] == "기각" and "재현 확인" in g["why"]
    g = lv.gate_live(ev(good, cur), stuck, dict(ok=True, steps=1800))
    assert g["verdict"] == "통과" and g["criteria"]["R_check"]["ok"] is True
    few = seeds[:3]
    g = lv.gate_live(dict(N=dict(current=_fake(few, cb, chase=cf), candidate=_fake(few, cb, chase=shorter)),
                          G=dict(current=_fake(few, cb, chase=cf), candidate=_fake(few, cb, chase=cf))), stuck, skip)
    assert g["n"] == 3 and g["t_crit"] == pytest.approx(4.303, abs=1e-3) and g["t_crit_flight"] == pytest.approx(4.303, abs=1e-3)   # 문턱은 시드 수에서
    one = seeds[:1]                                                           # 시드 하나: 짝 t 를 셀 수 없다 — 기각
    g = lv.gate_live(dict(N=dict(current=_fake(one, cb, chase=cf), candidate=_fake(one, cb, chase=shorter)),
                          G=dict(current=_fake(one, cb, chase=cf), candidate=_fake(one, cb, chase=cf))), stuck, skip)
    assert g["n"] == 1 and g["criteria"]["P1_N_chase"]["t"] == -math.inf
    assert g["verdict"] == "기각" and not g["passed"] and "판정 시드 1개" in g["why"] and not g["criteria"]["P1_N_chase"]["ok"]
    assert not any(v["ok"] for k, v in g["criteria"].items() if k.startswith(("GN_", "GF_", "GV_", "GC_", "GG_")))
    # 도망 기록이 없는 판(옛 실행기)·옛 꼴 기록(쫓긴 시간 없음)은 받지 않는다
    bare = _fake(seeds, cb)
    for w in bare["worlds"]:
        w.pop("flight")
    with pytest.raises(ValueError, match="도망 기록"):
        lv.gate_live(ev(good, cur, n_cur=bare), stuck, skip)
    old = _fake(seeds, cb)
    for w in old["worlds"]:
        w["flight"].pop("contact")
    with pytest.raises(ValueError, match="옛 꼴"):
        lv.gate_live(ev(good, cur, n_cur=old), stuck, skip)


def test_pilot_flight_pair(lv):
    """예비 측정의 쫓긴 시간 짝 = 관문 1차와 같은 셈 (판정 길이마다 끊은 기록 at[h].flight), 0.25·0.5·1 초 가를 시드 수, 지킴 GF·GV·GC 차이."""
    seeds = list(range(34900, 34920))
    rng = np.random.default_rng(34901)
    fl = {(s, r): float(rng.uniform(4.0, 8.0)) for s in seeds for r in ("A", "B")}

    def multi(shift):
        res = _fake(seeds, lambda s, r: 10, chase=lambda s, r: fl[(s, r)] + shift(s, r))
        for w in res["worlds"]:
            w["at"] = {"1800": dict(caught=w["caught"], starved=w["starved"], alive=w["alive"], flight=w["flight"])}
        return res

    a, b = multi(lambda s, r: -0.5 - 0.5 * (s % 2)), multi(lambda s, r: 0.0)
    p = lv.pilot_flight_pair(a, b, 1800)
    assert p["n"] == 20 and p["diff"] == pytest.approx(-0.75, abs=0.02) and p["sd"] > 0 and p["t"] < -2
    assert set(p["n_needed"]) == {"0.25s", "0.5s", "1s"} and p["n_needed"]["0.25s"] >= p["n_needed"]["0.5s"] >= p["n_needed"]["1s"]
    assert p["starts"]["diff"] == 0.0 and p["flee"]["diff"] == 0.0 and p["unsafe"]["diff"] == 0.0
    fp = lv.flight_pooled(lv.at_horizon(a, 1800))
    assert fp["started"] == 40 * 40 and fp["own_n"] == 20 * 40 and fp["started_per_seed"] == pytest.approx(80)
    text = lv.fmt_pilot(dict(pilot="p_t", seeds=[34900, 34919], snapshot="s.json", workers=2, times={}, flight_costs=[0.0],
                             vs_current={"r5": {"N": {"1800": dict(flight=p, caught=lv.pilot_pair(a, b, 1800))}}},
                             flight_pooled={"r5": {"N": {"1800": fp}}}))
    assert "두뇌 − 지금 두뇌" in text and "도망 끝 까닭" in text and "쫓긴 시간 지금 초" in text and "GF 시작/1000" in text


# --------------------------------------------------------------------- #
# 내보내기
# --------------------------------------------------------------------- #


def test_export_adapt_block(lv, tmp_path):
    brains = tmp_path / "brains"
    gate = "포만 없는 세계 쫓긴 시간 6.3→5.1초 (t −2.4), 잡힘·도망 나빠짐 없음"
    x = lv.export_brain(lv.OBS21ZERO, brains, 3, 5, "a5_20261021T153200_e2", "eco_v3_snapshot_s20003_t1800_e2.json", "Barren 나무 0→20", gate,
                        play_id="p20261021T150000_0badcafe")
    assert x["ok"] and x["name"] == "live_r3_a5_20261021T153200_e2"
    f = brains / "live_r3_a5_20261021T153200_e2.json"
    assert Path(x["file"]) == f and sorted(p.name for p in brains.iterdir()) == [f.name]          # 임시 파일이 남지 않는다
    d = json.loads(f.read_text(encoding="utf-8"))
    assert d["model"]["name"] == x["name"] and d["id"] == f"{x['name']}@{d['weights_sha256'][:8]}"
    assert d["model"]["path"] == "ckpt/v3/v3_r1_g995_s3_obs21zero.zip"
    assert d["contract_hash"] == lv.CONTRACT_OBS21 and d["obs_dim"] == 21
    a = d["adapt"]
    assert set(a) == {"round", "attempt", "run", "snapshot", "env", "gate", "created_utc", "play_id"}
    assert (a["round"], a["attempt"], a["run"], a["snapshot"], a["env"], a["gate"], a["play_id"]) == (
        3, 5, "a5_20261021T153200_e2", "eco_v3_snapshot_s20003_t1800_e2.json", "Barren 나무 0→20", gate, "p20261021T150000_0badcafe")
    assert a["created_utc"].endswith("Z")
    assert d["weights_sha256"] == json.loads(OBS21_FILE.read_text(encoding="utf-8"))["weights_sha256"]
    v = lv.ad.verify_brain_file(f)
    assert v["ok"] and x["verify"]["contract_ok"] and x["verify"]["adapt_ok"]
    with pytest.raises(FileExistsError):                                     # 같은 이름은 덮지 않는다
        lv.export_brain(lv.OBS21ZERO, brains, 3, 6, "a5_20261021T153200_e2", "s.json", "", "")
    assert lv.find_brain_zip(d["weights_sha256"], [brains]).resolve() == lv.OBS21ZERO.resolve()   # 다음 판의 시작점


# --------------------------------------------------------------------- #
# 그만둠 (가짜 판 프로세스 나무)
# --------------------------------------------------------------------- #


def _gone(pid: int, timeout: float = 15.0) -> bool:
    import psutil

    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            p = psutil.Process(pid)
            if p.status() == psutil.STATUS_ZOMBIE:
                return True
        except psutil.NoSuchProcess:
            return True
        time.sleep(0.1)
    return False


def _wait_file(p: Path, timeout: float = 30.0) -> int:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if p.exists() and p.read_text(encoding="utf-8").strip():
            return int(p.read_text(encoding="utf-8"))
        time.sleep(0.1)
    raise AssertionError(f"{p} 가 생기지 않았다")


def _fake_child(pid_file: Path, fh=None) -> subprocess.Popen:
    """손주 프로세스(학습·워커 대신)를 띄우고 그 pid 를 적은 뒤 잠자는 가짜 판."""
    code = ("import subprocess, sys, time\n"
            "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
            f"open(r'{pid_file}', 'w').write(str(g.pid))\n"
            "time.sleep(120)\n")
    return subprocess.Popen([sys.executable, "-c", code], stdout=fh or subprocess.DEVNULL, stderr=subprocess.STDOUT)


def test_kill_tree(lv, tmp_path):
    pytest.importorskip("psutil")
    p = _fake_child(tmp_path / "g.txt")
    gpid = _wait_file(tmp_path / "g.txt")
    lv.kill_tree(p)
    assert p.poll() is not None and _gone(gpid)


def _fake_snap(discs, wsha="ab" * 32):
    return dict(format="eco_v3_snapshot", version=1, session_seed=1, global_step=100, sim_seconds=13.3, contract_hash=lv_contract18(),
                brain=dict(id="x@abababab", weights_sha256=wsha, builtin=False, last_swap_step=-1), env=dict(revision=len(discs), changes=[]),
                regions=[dict(region="Barren", world=dict(weather=dict(kind="clear", intensity=0)), obstacles=dict(discs=discs),
                              food=dict(cap=[0.5] * 4, food=[0.5] * 4), covers=[[15.0, 15.0, 6.0]])])


def lv_contract18():
    return "0x7eea0107339be4ce"


def _write_snap(folder: Path, name: str, d: dict, t: float) -> Path:
    p = folder / name
    p.write_text(json.dumps(d), encoding="utf-8")
    os.utime(p, (t, t))
    return p


def test_watcher_supersede_and_skip(lv, tmp_path):
    pytest.importorskip("psutil")
    root = tmp_path / "EcoAdapt"
    launched = []

    def launcher(cmd, fh):
        assert cmd[2] == "round" and "--child" in cmd
        pf = tmp_path / f"g{len(launched) + 1}.txt"
        p = _fake_child(pf, fh)
        launched.append((p, pf, cmd))
        return p

    logs = []
    w = lv.Watcher(root, lv.default_plan(workers=2), launcher=launcher, log=logs.append)
    now = time.time()
    try:
        _write_snap(w.snapdir, "eco_v3_snapshot_s1_t100_e1.json", _fake_snap([[1.0, 1.0, 0.4]]), now - 10)
        w.tick()
        assert len(launched) == 1 and w.child is not None
        g1 = _wait_file(launched[0][1])
        _write_snap(w.snapdir, "eco_v3_snapshot_s1_t200_e2.json", _fake_snap([[1.0, 1.0, 0.4], [2.0, 2.0, 0.4]]), now - 5)   # 다른 환경
        w.tick()
        assert launched[0][0].poll() is not None and _gone(g1)              # 돌던 판의 나무를 끝냈다
        assert len(launched) == 2 and w.child["attempt"] == 2
        st = lv.load_state(root)
        assert st["attempt"] == 2 and st["history"][-1]["state"] == "superseded" and st["history"][-1]["attempt"] == 1
        assert not st["processed"]                                           # 그만둔 환경은 처리한 것이 아니다
        r1 = json.loads((lv.rounds_dir(root) / launched[0][2][launched[0][2].index("--run-id") + 1] / "result.json").read_text(encoding="utf-8"))
        assert r1["state"] == "superseded"
        d = json.loads((root / "status.json").read_text(encoding="utf-8"))
        assert d["state"] == "converting" and d["attempt"] == 2
        _write_snap(w.snapdir, "eco_v3_snapshot_s1_t300_e2.json", _fake_snap([[1.0, 1.0, 0.4], [2.0, 2.0, 0.4]]), now)   # 같은 환경의 주기 스냅숏
        w.tick()
        assert len(launched) == 2 and launched[1][0].poll() is None          # 그대로 돈다
        g2 = _wait_file(launched[1][1])
    finally:
        w.stop()
    assert launched[1][0].poll() is not None and _gone(g2)
    assert json.loads((root / "status.json").read_text(encoding="utf-8"))["state"] == "idle"

    # 이미 끝낸 환경 → 건너뜀 (판을 띄우지 않는다)
    key = lv.pair_key(_fake_snap([[5.0, 5.0, 0.4]]))
    lv.finish_attempt(root, dict(state="rejected", attempt=9, key=key, last_result="기각: 1차 t +0.3 (문턱 −2.02)"))
    w2 = lv.Watcher(root, lv.default_plan(workers=2), launcher=launcher, log=logs.append)
    _write_snap(w2.snapdir, "eco_v3_snapshot_s1_t400_e1.json", _fake_snap([[5.0, 5.0, 0.4]]), now + 5)
    w2.tick()
    assert len(launched) == 2 and w2.child is None
    d = json.loads((root / "status.json").read_text(encoding="utf-8"))
    assert d["state"] == "waiting" and d["message"] == "환경 같음 — 건너뜀"
    _write_snap(w2.snapdir, "eco_v3_snapshot_s1_t500_e1.json.tmp", _fake_snap([[6.0, 6.0, 0.4]]), now + 10)   # 임시 이름은 보지 않는다
    w2.tick()
    assert len(launched) == 2


def test_watcher_supersede_after_export(lv, tmp_path):
    """판이 두뇌 파일을 os.replace 한 뒤 state.json 에 적기 전에 끝났다(언리얼이 바꿔 끼우고 새 두뇌의 스냅숏을 썼다) → 그만둠이 아니라 내보냄으로 적는다."""
    pytest.importorskip("psutil")
    root = tmp_path / "EcoAdapt"
    launched = []

    def launcher(cmd, fh):
        pf = tmp_path / f"g{len(launched) + 1}.txt"
        p = _fake_child(pf, fh)
        launched.append((p, pf))
        return p

    w = lv.Watcher(root, lv.default_plan(workers=2), launcher=launcher, log=lambda s: None)
    now = time.time()
    s1, new_sha = _fake_snap([[1.0, 1.0, 0.4]]), "cd" * 32
    s2 = _fake_snap([[1.0, 1.0, 0.4]], wsha=new_sha)                          # 같은 환경 + 새 두뇌
    try:
        _write_snap(w.snapdir, "eco_v3_snapshot_s1_t100_e1.json", s1, now - 10)
        w.tick()
        rid = w.child["rid"]
        g1 = _wait_file(launched[0][1])
        brains = root / "brains"
        (brains / f"live_r1_{rid}.json").write_text(json.dumps(dict(id=f"live_r1_{rid}@cdcdcdcd", weights_sha256=new_sha, adapt=dict(
            round=1, attempt=1, run=rid, snapshot="eco_v3_snapshot_s1_t100_e1.json", env="환경 그대로", gate="포만 없는 세계 잡힘 30.0→28.0% (t −2.5)",
            created_utc="2026-10-21T00:00:00Z"))), encoding="utf-8")
        (brains / f"live_r2_{rid}.json.tmp").write_text("{}", encoding="utf-8")   # 다시 읽기 전에 끝난 임시 파일은 치운다
        _write_snap(w.snapdir, "eco_v3_snapshot_s1_t200_e1.json", s2, now - 5)
        w.tick()
        assert launched[0][0].poll() is not None and _gone(g1)
        assert w.child is None and len(launched) == 1                          # 새 두뇌 + 같은 환경 = 처리함 → 같은 환경을 다시 배우지 않는다
        st = lv.load_state(root)
        assert st["round"] == 1 and [h["state"] for h in st["history"]] == ["exported"] and st["history"][0]["round"] == 1
        assert [p["key"] for p in st["processed"]] == [lv.pair_key(s1), lv.pair_key(s2)]
        res = json.loads((lv.rounds_dir(root) / rid / "result.json").read_text(encoding="utf-8"))
        assert res["state"] == "exported" and res["round"] == 1 and res["brain_file"].endswith(f"live_r1_{rid}.json")
        assert not list(brains.glob("*.tmp"))
        d = json.loads((root / "status.json").read_text(encoding="utf-8"))
        assert d["state"] == "waiting" and d["round"] == 1
    finally:
        w.stop()
    assert len(lv.load_state(root)["history"]) == 1                          # 멈춤이 같은 시도를 두 번 적지 않는다


def test_watcher_error_retry(lv, tmp_path):
    """결과 없이 끝난 판(오류)은 같은 스냅숏으로 ERROR_RETRY 번까지 다시 하고 멈춘다 (환경마다 스냅숏은 하나뿐이다)."""
    root = tmp_path / "EcoAdapt"
    launched = []

    def launcher(cmd, fh):
        p = subprocess.Popen([sys.executable, "-c", "raise SystemExit(3)"], stdout=fh, stderr=subprocess.STDOUT)
        launched.append(p)
        return p

    w = lv.Watcher(root, lv.default_plan(workers=2), launcher=launcher, log=lambda s: None)
    snap1 = _fake_snap([[1.0, 1.0, 0.4]])
    _write_snap(w.snapdir, "eco_v3_snapshot_s1_t100_e1.json", snap1, time.time())
    w.tick()
    for _ in range(4):
        launched[-1].wait(30)
        w.tick()
    assert len(launched) == lv.ERROR_RETRY and w.child is None
    st = lv.load_state(root)
    assert [h["state"] for h in st["history"]] == ["error"] * lv.ERROR_RETRY and lv.is_processed(st, lv.pair_key(snap1))


def test_lock(lv, tmp_path):
    pytest.importorskip("psutil")
    root = tmp_path / "EcoAdapt"
    p = lv.acquire_lock(root, "watch")
    with pytest.raises(SystemExit, match="다른 실시간 고리"):                 # 같은 폴더에 고리 하나만
        lv.acquire_lock(root, "round")
    lv.release_lock(p)
    assert not p.exists()
    p.write_text(json.dumps(dict(pid=os.getpid(), create_time=1.0, what="watch")), encoding="utf-8")   # 주인이 죽은 잠금 (pid 재사용 — 시작 시각이 다르다)
    q = lv.acquire_lock(root, "watch")
    assert json.loads(q.read_text(encoding="utf-8"))["pid"] == os.getpid()
    lv.release_lock(q)
    p.write_text("", encoding="utf-8")                                        # 막 만들어 아직 안 쓴 잠금
    with pytest.raises(SystemExit, match="막 잡았다"):
        lv.acquire_lock(root, "watch")
    os.utime(p, (time.time() - 60, time.time() - 60))
    lv.release_lock(lv.acquire_lock(root, "watch"))


def test_kill_recorded(lv, tmp_path):
    pytest.importorskip("psutil")
    rd = tmp_path / "rd"
    a = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    b = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        lv.record_pids(rd, [dict(proc=a, seed=0), dict(proc=b, seed=1)])
        f = rd / "logs" / "pids.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        assert [r["pid"] for r in d["procs"]] == [a.pid, b.pid] and all(r["create_time"] for r in d["procs"])
        d["procs"][1]["create_time"] = 1.0                                     # 시작 시각이 다르면(pid 재사용) 건드리지 않는다
        f.write_text(json.dumps(d), encoding="utf-8")
        assert lv.kill_recorded(rd) == 1
        assert a.wait(15) is not None and b.poll() is None
        assert lv.kill_recorded(rd) == 0
    finally:
        for p in (a, b):
            p.kill()
            p.wait()


def test_measure_fdec_snapshot_food(lv, prepared):
    """예비 측정 f_dec 는 T 세계 그대로 — 세계마다 그 지역 스냅숏 먹이 지도 (학습 train-one 과 같은 덮기)."""
    from env_v2.config import load_v2_config
    from env_v2.vec_env import region_configs, region_mix_params
    from env_v2.world import World

    cfg = load_v2_config(prepared["dir"] / "train.yaml")
    cfgs = region_configs(cfg, region_mix_params(cfg.v2["train"]["region_mix"], cfg))
    food = {n: r["cap"] for n, r in prepared["regions"].items()}
    assert sorted(cfgs) == sorted(food)
    W = lv.snapshot_food_world(World, food)
    for region, c in cfgs.items():
        w = W(c, seeds=[32000])
        assert np.array_equal(w.food_cap.ravel(), np.asarray(food[region], dtype=np.float64)) and np.array_equal(w.food, w.food_cap)
    with pytest.raises(SystemExit):
        lv.snapshot_food_world(World, {})(next(iter(cfgs.values())), seeds=[32000])


# --------------------------------------------------------------------- #
# 관문 상수 = LIVE_GATE.md
# --------------------------------------------------------------------- #


def test_constants_match_md(lv):
    md = lv.LIVE_GATE_MD.read_text(encoding="utf-8")
    L = lv.LIVE
    n = L["judge_seeds"][1] - L["judge_seeds"][0] + 1
    ng = L["judge_seeds_g"][1] - L["judge_seeds_g"][0] + 1
    tc, tg = lv.t_crit(n - 1), lv.t_crit(ng - 1)
    for key in ("judge_seeds", "judge_seeds_g", "select_seeds", "stuck_seeds", "check_seeds"):
        assert f"{L[key][0]}~{L[key][1]}" in md, key
    assert f"(n = {n})" in md and f"자유도 n − 1 = {n - 1}" in md and f"(n_G = {ng}" in md and f"자유도 {ng - 1}" in md
    assert f"t_crit = {tc:.3f}" in md and f"| 문턱 t_crit(n − 1) | {tc:.3f} |" in md and f"t ≤ −{tc:.3f}" in md and f"t < +{tc:.3f}" in md
    assert f"t_crit_G = {tg:.3f}" in md and f"| 문턱 t_crit_G(n_G − 1) | {tg:.3f} |" in md and f"t < +{tg:.3f}" in md
    assert f"| N 판정 길이 H_N | {L['horizon']} 스텝 |" in md and f"H_N = {L['horizon']} 스텝" in md
    assert f"| G 판정 길이 H_G | {L['horizon_g']} 스텝 |" in md and f"H_G = {L['horizon_g']} 스텝" in md
    assert f"| 학습 스텝 S | {L['train_steps'] // 1_000_000}M |" in md and f"S = {L['train_steps'] // 1_000_000}M 스텝" in md
    assert f"| 모델 수 K | {len(L['model_seeds'])} (모델 시드 {', '.join(str(s) for s in L['model_seeds'])}) |" in md
    assert f"{lv.PILOT_SEEDS[0]}~{lv.PILOT_SEEDS[1]}" in md and f"{lv.GATE_SEEDS[0]}~{lv.GATE_SEEDS[1]}" in md
    assert L["shelter_x"] == 2.0 and L["use_min"] == 0.01 and "2배" in md and "1% 넘게" in md
    assert L["f_dec"] is None and "R5 값 0.858922 그대로" in md
    assert lv.CONTRACT_OBS21 in md and "예비 측정 뒤 크기 확정" in md
    assert lv.TEMPLATE_OBS.exists() and lv.R5_TRAIN.exists() and lv.R5S3.name in md
    # 10-21 (3) 1차 = 도망 시간(쫓긴 시간): 사용자 말 그대로, 스스로 벗어남·잡힘·굶음·잘림 = 세계의 정의와 같은 끝 까닭, 크기는 예비 측정 뒤 확정
    from env_v2.world import FLIGHT_CAUSES, FLIGHT_OWN, FLIGHT_UNSAFE

    assert "(3) 사용자 10-21 기준 바꿈 — 1차 = 도망 시간" in md
    assert "똑같이 도망을 가도 숲속으로 잘 숨어서 늑대 시야에 잘 벗어나기 때문에 도망가는 시간이 더 짧은 사슴이 똑똑한걸로 기준을 잡아봐" in md
    assert tuple(L["flight_own"]) == FLIGHT_OWN and "스스로 벗어난 도망(cover · obstacle · fov · range)" in md
    assert tuple(L["flight_unsafe"]) == FLIGHT_UNSAFE and "(caught · starved · truncated)" in md
    assert L["flight_min_episodes"] == 1 and "스스로 벗어난 도망 1개 이상" in md
    assert L["flight_min_effect_s"] == 0.0 and "| P1 최소 차이 δ | 0 초 (유의성만) | 예비 측정 뒤 확정" in md
    assert L["train_flight_cost"] == 0.0 and "| T 세계 도주 비용 flight_cost | 0 (끔) | 예비 측정 뒤 확정" in md
    assert L["flight_sizes_confirmed"] is False and "| 크기 확정 표시 flight_sizes_confirmed | 거짓 |" in md
    assert md.count("도망 시간 기준은 예비 측정 뒤 확정") >= 6 and all(k in md for k in ("GF", "GV", "GC", "GG_chase", "GN_caught", "P1_N_chase"))
    assert all(f"`{c}`" in md for c in FLIGHT_CAUSES)
    assert lv.STEP_S == pytest.approx(2.0 / 15.0) and "× 2/15 초" in md
