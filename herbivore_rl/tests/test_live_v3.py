"""실시간 적응 고리 results/v3/live/live.py (10-21 사용자 '게임 중 실시간 두뇌 교체').

- 환경 지문·건너뛰기: 같은 환경(먹이 남은 양·시각만 다름)은 같은 지문, 원판·날씨·용량·은신처가 바뀌면 다른 지문. 열쇠 = 지문 + 두뇌 가중치.
- 기록·상태 파일: os.replace 로 바꿔 넣고(잠김이면 다시), 임시 파일을 남기지 않는다. 시도·판 번호, 처리한 열쇠, 깨진 기록.
- 세계 셋: G(게임) 늑대 포만 켬, N(판정) 끔, T(학습) 끔. 시작 모델: R1b-F(관측 18) → 관측 21 + 0 열, 관측 21 두뇌 파일 → 그 zip, 그 밖은 거부.
- 관문: 짜 맞춘 판정 판으로 통과·1차 기각·지킴 기각·재현 확인. 10-23 (변경 기록 (6)) 1차 = 숨음 비율(쫓긴 도망 가운데 은신처에 들어 끝나고 10 초 안에
  안 잡힌 몫, 시드마다 지역 합): 크면 통과, 같거나 작으면 기각, 최소 차이 δ_H, 쫓긴 시간은 보고만(짧아져도 숨음 비율이 같으면 기각, 길어져도 숨음 비율이
  크면 통과), 쫓긴 도망 가운데 잡힘 몫이 늘면 GH(새 지킴 — GC 와 따로), 더 잡히면 GN_caught, 도망을 잘게 쪼개면 GF, 더 오래 달리면 GV, 잡힘·잘림으로
  끝난 도망이 늘면 GC, 게임 세계 쫓긴 시간 GG_chase, 쫓긴 도망이 없는 시드는 짝에서 빠짐(기록), 옛 꼴 기록·숨은 뒤 지켜보기 없는 기록 거부. 도주 반사를 끈
  스냅숏 거부, 크기 확정 전 실제 폴더 거부. 판정 실행기 기본 'python', 숨은 뒤 지켜보기를 세지 못하는 C++ 평가기 'ceval' 은 판정에서 거부.
  예비 측정 숨음 비율·잡힘 비율·쫓긴 시간 짝·도주 비용 사본·기준 크기 재기.
  두뇌 파일 adapt 블록·이름·다시 읽기. 그만둠: 가짜 판 프로세스 나무를 끝낸다.
- 감시 정리: 두뇌 파일을 쓴 뒤 끝난 판은 내보냄(판 번호·두 열쇠), 오류는 같은 스냅숏으로 ERROR_RETRY 번까지, 폴더마다 잠금 하나, 남은 학습 프로세스 끝내기.
  관문은 시드 하나면 기각. state.json 은 잠깐 잠기면 다시 읽는다. 예비 측정 f_dec 는 스냅숏 먹이 지도(T 세계 그대로).
- 10-21 (4) 두 번 보기(중간 판정): 경계 셈(끈 기본 = 옛 문턱, 켰을 때 두 몫 합 = α, 같은 간격 두 번의 알려진 z 값, 실제 자유도 t, scipy 없이도 같음,
  흉내 내기로 우연 통과 몫 ≤ 2.5%), 중간 기각(나아지지 않음 — 10-23 숨음 비율 짝 t ≤ 0)은 G·끼임·뒤 절반을 돌리지 않음(가짜 실행기), 앞서 통과(켰을 때 —
  짝 t ≥ +b₁)도 뒤 절반·G·끼임을 돌려 지킴을 전체로 봄(검토 사례: 뒤 절반 은신처 안 잡힘·더 잡힘 → 기각), 끝 판정 = 옛 한 번 보기. 지금 두뇌 판정 저장:
  맞음·틀림·열쇠 무효(10-23 저장 판 2·기준 판 — 옛 저장을 쓰지 않음), 임시 파일 → os.replace, 저장 실패 기록. 판정 실행기 갈림(결과의 시드·지역 확인).
- 관문 상수 = LIVE_GATE.md.
- 10-24 (8) 두 길·판 5 두뇌: 묶음 표(계약 = 바탕 설정·학습 조리법 세계의 관측·마스크 판으로 다시 셈한 해시, 판 5 = 판 5 거울·R7 조리법·λ 0.98), R7e 지금 두뇌
  → 그 zip·판 5 세계(G·N·T, 평가기 일 포함), 판 4·마스크 판·지역 두 길 칸 어긋남 거부, 판 5 두뇌 파일 A5(계약·골든 세계), 길 보고 GT·GTr·GR = r6_eval 셈
  (보고만 — 관문 판정 그대로, 관측 21 판은 보고 없음, 중간 기각이면 앞 절반 짝).
- 10-27 (10) 실제 폴더 잠금 풀기: 판 5 예비 측정(pilot_mask5)으로 정한 상수(S 1M·δ_H 1 %p·flight_sizes_confirmed 참) = LIVE_GATE.md, 묶음 잠금(임시 폴더를
  실제 폴더로 놓고 감시 → 판 명령 → 판: 판 5 R7e 는 변환·학습 시작까지, 관측 18 내장 R1b-F 는 변환 전에 거부·처리함, 진짜 Saved/EcoAdapt 그대로),
  예비 측정 pilot.md f_dec 머리 줄(묶음 조리법 값).
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
    assert lv.LIVE["flight_sizes_confirmed"] is True                       # 10-27 (10) 판 5 예비 측정으로 확정 (그 전 10-21 (3)~ 거짓)
    assert not lv.plan_from_args(ns(root=str(lv.DEFAULT_ROOT)))["test"]   # 관문 크기면 실제 폴더에서 판·감시를 시작한다 (묶음 잠금은 판에서 — test_real_root_profile_lock)
    monkeypatch.setitem(lv.LIVE, "flight_sizes_confirmed", False)
    with pytest.raises(SystemExit, match="예비 측정으로 확정하지 않았다"):
        lv.plan_from_args(ns(root=str(lv.DEFAULT_ROOT)))                   # 확정 전에는 관문 크기여도 실제 폴더에서 판·감시를 돌리지 않는다 (전역 잠금 그대로)
    assert not lv.plan_from_args(ns())["test"]                             # 시험 폴더는 잠금과 상관없다
    with pytest.raises(SystemExit):
        lv.plan_from_args(ns(judge_seeds="34900-34902"))                   # 예비 측정 시드는 관문에 쓰지 않는다
    for kw in (dict(judge_seeds="35000"), dict(judge_seeds_g="35000-35000"), dict(select_seeds="35100-35100")):
        with pytest.raises(SystemExit, match="2개 이상"):                   # 시드 하나로는 짝 t 를 셀 수 없다
            lv.plan_from_args(ns(**kw))
    assert lv.inside((34900, 34999), lv.PILOT_SEEDS) and not lv.inside((34990, 35001), lv.PILOT_SEEDS)


# --------------------------------------------------------------------- #
# 관문
# --------------------------------------------------------------------- #


def _flight(chase_s, own, started, step_s, live=100000, flee=0.08, unsafe=2, hidden=None, trunc=1, watching=0, ep=None):
    """세계 하나의 도망 기록(짜 맞춤, World.flight_stats 꼴): 스스로 벗어난 도망 own 개(은신처 ½·원판 ¼·반경 나머지)의 쫓긴 시간 평균 chase_s 초,
    잡힘 unsafe − trunc·잘림 trunc, 나머지 시작은 바꿈(쫓긴 3 스텝)·안 쫓김 반반(시작 = 까닭 수 합). 산 사슴-스텝 live, 실행 FLEE 몫 flee(반사 = 그 ¾).
    10-23 숨은 뒤 지켜보기 hide: 은신처 끝 도망 가운데 hidden 개(없으면 모두)가 10 초 안에 잡히지 않음(나머지는 cover_then_caught), 쫓긴 도망 =
    시작 − 안 쫓김 − 잘림 (own 20·started 40·unsafe 2 이면 30 — 은신처 끝 10).
    10-24 쫓김 사건 episode: 기본은 도망마다 사건 하나(이어진 도망 없음 — 사건 숨음 = hidden, 사건 잡힘 = 잡힘 + cover_then_caught, 잘림 = trunc,
    쫓긴 사건 = 쫓긴 도망). ep = {started·chased·hidden·caught·starved·truncated} 덮기 — other·other_chased 는 합이 맞게 다시 셈한다."""
    tot = int(round(chase_s / step_s * own))
    cv, ob = own // 2, own // 4
    rest = max(started - own - unsafe, 0)
    sw = rest // 2
    n = dict(cover=cv, obstacle=ob, fov=0, range=own - cv - ob, switch=sw, stop=0, held=0, unchased=rest - sw, caught=unsafe - trunc, starved=0,
             truncated=trunc)
    c_cv, c_ob = tot * cv // max(own, 1), tot * ob // max(own, 1)
    contact = dict(cover=c_cv, obstacle=c_ob, fov=0, range=tot - c_cv - c_ob, switch=3 * sw, stop=0, held=0, unchased=0, caught=30 * n["caught"], starved=0,
                   truncated=2)
    steps = {k: contact[k] + 5 * n[k] for k in n}
    fs = int(flee * live)
    hd = cv if hidden is None else int(hidden)
    assert 0 <= hd <= cv and n["caught"] >= 0
    hide = dict(chased=sum(n.values()) - n["unchased"] - n["truncated"], hidden=hd, watching=min(int(watching), hd), cover_then_caught=cv - hd,
                cover_then_starved=0, watch_steps=75)
    e = dict(started=sum(n.values()), chased=hide["chased"], hidden=hd, caught=n["caught"] + cv - hd, starved=0, truncated=n["truncated"])
    e.update(ep or {})
    e["other"] = e["started"] - e["hidden"] - e["caught"] - e["starved"] - e["truncated"]
    e["other_chased"] = e["chased"] - e["hidden"] - e["caught"] - e["starved"]
    assert 0 <= e["other_chased"] <= e["other"], e
    jo = max(sum(n.values()) - e["started"], 0)
    episode = dict(e, watching=min(int(watching), e["hidden"]), joined=jo, joined_cover=0, joined_other=jo, window_caught=0, window_starved=0,
                   link_cover_steps=75, link_other_steps=38)
    return dict(started=sum(n.values()), live_steps=live, flee_steps=fs, reflex_steps=fs * 3 // 4, n=n, steps=steps, contact=contact,
                own_n=own, own_steps=sum(steps[c] for c in ("cover", "obstacle", "fov", "range")), own_contact=tot, shelter_end=cv,
                hist=[own, 0, 0, 0, 0, 0, 0, 0], hist_edges=[8, 15, 38, 75, 150, 300, 600], hide=hide, episode=episode)


def _fake(seeds, caught, starved=lambda s, r: 10, shelter=0.06, beh=(0.88, 0.08, 0.04, 0, 0), cover=0, regions=("A", "B"),
          chase=lambda s, r: 6.0, own=lambda s, r: 20, started=lambda s, r: 40, flee=lambda s, r: 0.08, unsafe=lambda s, r: 2,
          hidden=lambda s, r: None, trunc=lambda s, r: 1, ep=lambda s, r: None):
    W = []
    for s in seeds:
        for r in regions:
            c, st, live = int(caught(s, r)), int(starved(s, r)), 100000
            W.append(dict(seed=s, region=r, n=128, caught=c, starved=st, alive=128 - c - st, shelter_steps=int(shelter * live), live_steps=live,
                          beh_steps=[int(b * live) for b in beh], catch_cover=cover, hunt=dict(ends=10, success=6),
                          flight=_flight(chase(s, r), int(own(s, r)), int(started(s, r)), 2.0 / 15.0, live, flee(s, r), int(unsafe(s, r)), hidden(s, r),
                                         int(trunc(s, r)), ep=ep(s, r))))
    return dict(meta={}, worlds=W)


def test_gate_decisions(lv, monkeypatch):
    rng = np.random.default_rng(34900)
    seeds = list(range(35000, 35040))
    base = {(s, r): int(rng.integers(25, 30)) for s in seeds for r in ("A", "B")}
    fl = {(s, r): float(rng.uniform(4.0, 8.0)) for s in seeds for r in ("A", "B")}
    hb = {(s, r): int(rng.integers(3, 8)) for s in seeds for r in ("A", "B")}                   # 지금 두뇌: 쫓긴 도망 30 가운데 숨어 살아남음 3~7
    cb = lambda s, r: base[(s, r)]                                                        # noqa: E731
    cf = lambda s, r: fl[(s, r)]                                                          # noqa: E731
    ch = lambda s, r: hb[(s, r)]                                                          # noqa: E731
    better = (lambda s, r: hb[(s, r)] + (1 if (s + (r == "A")) % 2 else 3))               # 숨음 비율이 1~3 개(÷30) 크다 — 평균 +2/30
    shorter = (lambda s, r: fl[(s, r)] - (0.5 if (s + (r == "A")) % 2 else 1.5))         # 쫓긴 시간이 0.5~1.5 초 짧다
    cur = _fake(seeds, cb, chase=cf, hidden=ch)
    stuck0 = dict(summary=dict(deer_stuck=0, wolf_stuck=1, wolf_wall_stuck=3, worlds=15))
    stuck = dict(current=stuck0, candidate=stuck0)
    skip = dict(ok=None, why="중간 변화로 재현 확인 없음 (환경 #1)")

    def ev(n_cand, g_cand, n_cur=cur, g_cur=cur):
        return dict(N=dict(current=n_cur, candidate=n_cand), G=dict(current=g_cur, candidate=g_cand))

    good = _fake(seeds, cb, chase=cf, hidden=better)
    g = lv.gate_live(ev(good, cur), stuck, skip)
    assert g["verdict"] == "통과" and g["passed"] and g["n"] == 40 and g["n_flight"] == 40 and g["t_crit_flight"] == pytest.approx(2.0227, abs=5e-4)
    p1 = g["criteria"]["P1_N_hide"]
    assert p1["ok"] and p1["key"] == "hide" and p1["unit"] == "episode" and p1["diff"] == pytest.approx(2.0 / 30.0, abs=0.003) and p1["dropped"] == []
    assert p1["t"] >= 2.0227 and "쫓긴 사건 가운데 숨음 사건 몫" in p1["rule"] and g["unit"] == "episode"
    assert "P1_N_chase" not in g["criteria"] and "P1_N_caught" not in g["criteria"] and g["criterion"] == lv.GATE_CRITERION == "hide-episode-v1"
    assert all(g["criteria"][k]["ok"] for k in ("GH_flight_caught", "GN_caught", "GF_flight_starts", "GE_episode_starts", "GV_flee_time", "GC_flight_unsafe",
                                                "GG_chase"))
    assert g["criteria"]["GH_flight_caught"]["unit"] == "episode" and "쫓긴 사건 가운데 잡힘 사건 몫" in g["criteria"]["GH_flight_caught"]["rule"]
    ge = g["criteria"]["GE_episode_starts"]
    assert ge["diff"] == 0.0 and ge["a"] == pytest.approx(0.4) and "GR 자리" in ge["rule"]                 # 사건 시작 40 ÷ 산 사슴-스텝 100000 × 1000
    rc = g["criteria"]["REPORT_N_chase"]                                                   # 옛 1차 쫓긴 시간은 보고만 (ok None — 판정에 쓰지 않는다)
    assert rc["ok"] is None and rc["diff"] == 0.0 and "보고만" in rc["rule"]
    for k in ("REPORT_N_flight_hide", "REPORT_N_flight_caught"):                           # 10-24: 옛 도망 단위 숨음·잡힘 비율도 보고만
        assert g["criteria"][k]["ok"] is None and g["criteria"][k]["unit"] == "flight" and "보고만" in g["criteria"][k]["rule"]
    assert g["criteria"]["REPORT_N_flight_hide"]["diff"] == pytest.approx(p1["diff"])          # 도망마다 사건 하나인 기록 — 두 셈이 같다
    assert g["criteria"]["R_check"]["skipped"]
    assert g["summary"].startswith("포만 없는 세계 사건 숨음 비율 ") and "% (t +" in g["summary"] and g["summary"].endswith(", 잡힘·도망 나빠짐 없음")
    rep = g["report"]
    fN = rep["flight"]["N"]
    assert set(rep["flight"]) == {"N", "G"} and fN["candidate"]["hide_share"] > fN["current"]["hide_share"]
    assert fN["current"]["chased"] == 30 * 80 and fN["current"]["hidden"] == sum(hb.values())
    assert fN["current"]["hide_share"] == pytest.approx(sum(hb.values()) / 2400) and fN["current"]["caught_share_chased"] == pytest.approx(1 / 30)
    assert fN["current"]["cover_share_chased"] == pytest.approx(10 / 30) and fN["current"]["cover_then_caught"] == 10 * 80 - sum(hb.values())
    assert fN["current"]["share"]["cover"] == pytest.approx(10 / 40) and fN["current"]["truncated_share"] == pytest.approx(1 / 40)
    assert fN["current"]["own_share"] == pytest.approx(20 / 40) and fN["current"]["unsafe_share"] == pytest.approx(2 / 40)
    assert fN["current"]["starts_per_1k"] == pytest.approx(0.4) and fN["current"]["shelter_end_share"] == pytest.approx(10 / 38)
    assert fN["candidate"]["flee_share"] == pytest.approx(0.08) and fN["candidate"]["self_flee_share"] == pytest.approx(0.02)
    assert "flee_share" not in rep and "flight_G" not in rep
    assert fN["current"]["ep_chased"] == 30 * 80 and fN["current"]["ep_hidden"] == sum(hb.values()) and fN["current"]["ep_started"] == 40 * 80
    assert fN["current"]["ep_hide_share"] == pytest.approx(sum(hb.values()) / 2400) and fN["current"]["ep_per_1k"] == pytest.approx(0.4)
    assert fN["current"]["flights_per_episode"] == 1.0 and fN["current"]["ep_truncated"] == 80
    md = lv.fmt_flight(g)
    assert "## 쫓김 사건 (10-24" in md and "사건 숨음 비율 (쫓긴 사건 가운데, 전체 합)" in md and "숨음 비율 (도망 단위, 쫓긴 도망 가운데, 전체 합)" in md
    assert "1차 P1 사건 숨음 비율 (시드마다 지역 셋 합으로 낸 몫의 평균" in md and "짝 시드 40 (빠진 시드 0)" in md
    assert "쫓긴 시간 초 (보고만" in md and "실행 FLEE 몫 (반사 포함)" in md and "스스로 고른 FLEE 몫" in md and "G 쫓긴 시간 (지킴 GG_chase" in md
    assert "사건 잡힘 비율 (지킴 GH, 같은 셈)" in md and "쫓긴 시간 (보고만 — 10-21 (3) 의 옛 1차" in md and "사건 시작 (지킴 GE" in md
    assert "도망 단위 숨음 비율 (보고만" in md and "도망 단위 잡힘 비율 (보고만" in md
    tbl = lv.fmt_gate_live(g)
    assert "| REPORT_N_chase |" in tbl and "— (보고만) |" in tbl and "| P1_N_hide | " in tbl and " %p ± " in tbl and "| GE_episode_starts | " in tbl
    assert "| REPORT_N_flight_hide | " in tbl and "| REPORT_N_flight_caught | " in tbl
    # 같은 두뇌 = 숨음 비율이 크지 않음 → 1차 기각 (잡힘이 같아도)
    g = lv.gate_live(ev(cur, cur), stuck, skip)
    assert g["verdict"] == "기각" and "P1" in g["why"] and g["brief"].startswith("1차 사건 숨음 비율 ") and "(문턱 +2.02)" in g["brief"]
    # 더 작은 숨음 비율 → 1차 기각
    g = lv.gate_live(ev(_fake(seeds, cb, chase=cf, hidden=lambda s, r: hb[(s, r)] - 1 - (s % 2)), cur), stuck, skip)
    assert g["verdict"] == "기각" and not g["criteria"]["P1_N_hide"]["ok"] and g["criteria"]["P1_N_hide"]["t"] < 0
    # 쫓긴 시간은 보고만: 쫓긴 시간이 짧아져도 숨음 비율이 같으면 1차 기각, 쫓긴 시간이 길어져도 숨음 비율이 크면 통과
    g = lv.gate_live(ev(_fake(seeds, cb, chase=shorter, hidden=ch), cur), stuck, skip)
    assert g["verdict"] == "기각" and "1차 P1 실패" in g["why"] and g["criteria"]["REPORT_N_chase"]["diff"] < 0
    g = lv.gate_live(ev(_fake(seeds, cb, chase=lambda s, r: fl[(s, r)] + 1.0, hidden=better), cur), stuck, skip)
    assert g["verdict"] == "통과" and g["criteria"]["REPORT_N_chase"]["t"] > 0 and g["criteria"]["REPORT_N_chase"]["ok"] is None
    # 최소 차이 δ_H: 평균 +6.7%p 커도 δ_H 10%p 를 못 넘으면 1차 기각
    monkeypatch.setitem(lv.LIVE, "hide_min_effect", 0.10)
    g = lv.gate_live(ev(good, cur), stuck, skip)
    assert g["verdict"] == "기각" and "최소 차이 +10%p" in g["why"] and "≥ +10%p" in g["criteria"]["P1_N_hide"]["rule"]
    monkeypatch.setitem(lv.LIVE, "hide_min_effect", 0.05)
    assert lv.gate_live(ev(good, cur), stuck, skip)["verdict"] == "통과"
    # 인자로 준 δ 가 LIVE 값보다 앞선다 (오프라인 PREREG 판정은 0 을 넘긴다 — 10-27 (10) 뒤 LIVE 값 0.01)
    monkeypatch.setitem(lv.LIVE, "hide_min_effect", 0.10)
    g = lv.gate_live(ev(good, cur), stuck, skip, hide_min_effect=0.0)
    assert g["verdict"] == "통과" and "최소 차이" not in g["criteria"]["P1_N_hide"]["rule"]
    assert lv.gate_live(ev(good, cur), stuck, skip, hide_min_effect=0.10)["verdict"] == "기각"
    monkeypatch.setitem(lv.LIVE, "hide_min_effect", 0.0)
    # 지킴 GH (10-24 사건 단위): 사건 숨음 비율은 크지만 쫓긴 사건 가운데 잡힘 사건 몫이 늘어남(도망 단위 잡힘 비율·GC 는 그대로 — 예: 은신처 들락날락
    # 끝에 잡힘) → GH 기각
    worse_c = _fake(seeds, cb, chase=cf, hidden=better, ep=lambda s, r: dict(hidden=better(s, r), caught=11 - hb[(s, r)] + 1 + (s % 2)))
    g = lv.gate_live(ev(worse_c, cur), stuck, skip)
    assert g["verdict"] == "기각" and g["why"] == "지킴 기준 실패: GH_flight_caught" and g["criteria"]["P1_N_hide"]["ok"]
    assert g["criteria"]["GC_flight_unsafe"]["ok"] and g["criteria"]["GC_flight_unsafe"]["diff"] == 0.0 and g["brief"].startswith("지킴 GH_flight_caught (t +")
    assert g["criteria"]["REPORT_N_flight_caught"]["diff"] == 0.0 and g["criteria"]["GH_flight_caught"]["diff"] > 0
    # 10-24 두 번 세기: 도망 단위 숨음 비율만 크고(은신처 들락날락 — 같은 사건 안 숨음 여럿) 사건 숨음 비율은 같음 → 1차 기각 (옛 칸은 보고만)
    twice = _fake(seeds, cb, chase=cf, hidden=better, ep=lambda s, r: dict(hidden=hb[(s, r)], caught=11 - hb[(s, r)]))
    g = lv.gate_live(ev(twice, cur), stuck, skip)
    assert g["verdict"] == "기각" and "1차 P1 실패" in g["why"] and g["criteria"]["P1_N_hide"]["diff"] == 0.0
    assert g["criteria"]["REPORT_N_flight_hide"]["diff"] > 0 and g["criteria"]["REPORT_N_flight_hide"]["t"] > 2.0227
    # 지킴 GE (GR 자리): 사건 숨음 비율은 크지만 1000 산 사슴-스텝당 사건 시작이 유의하게 많다 (도망 시작 GF 는 그대로) → GE 기각
    more_ep = _fake(seeds, cb, chase=cf, hidden=better, started=lambda s, r: 48,
                    ep=lambda s, r: dict(started=44 + (s % 3), chased=30, hidden=better(s, r), caught=11 - better(s, r), truncated=1))
    more_fl = _fake(seeds, cb, chase=cf, hidden=ch, started=lambda s, r: 48, ep=lambda s, r: dict(started=40, chased=30))
    g = lv.gate_live(ev(more_ep, more_fl, n_cur=more_fl, g_cur=more_fl), stuck, skip)
    assert g["verdict"] == "기각" and g["why"] == "지킴 기준 실패: GE_episode_starts" and g["criteria"]["P1_N_hide"]["ok"]
    assert g["criteria"]["GF_flight_starts"]["diff"] == 0.0 and g["criteria"]["GE_episode_starts"]["t"] > 2.0227
    assert g["brief"].startswith("지킴 GE_episode_starts (t +")
    # 숨음 비율은 크지만 더 잡힘 (세계 잡힘 몫) → GN_caught 기각
    more = lambda s, r: base[(s, r)] + (1 if (s + (r == "A")) % 2 else 2)                # noqa: E731
    g = lv.gate_live(ev(_fake(seeds, more, chase=cf, hidden=better), cur), stuck, skip)
    assert g["verdict"] == "기각" and "GN_caught" in g["why"] and g["criteria"]["P1_N_hide"]["ok"]
    assert g["brief"].startswith("지킴 GN_caught (t +")
    # 덜 잡혀도 1차는 숨음 비율이다
    less = lambda s, r: base[(s, r)] - (1 if (s + (r == "A")) % 2 else 0)                # noqa: E731
    g = lv.gate_live(ev(_fake(seeds, less, chase=cf, hidden=ch), cur), stuck, skip)
    assert g["verdict"] == "기각" and "P1" in g["why"] and g["criteria"]["GN_caught"]["ok"]
    # 짧게 자주 도망 (1000 산 사슴-스텝당 시작이 유의하게 많다) → GF 기각
    g = lv.gate_live(ev(_fake(seeds, cb, chase=cf, hidden=better, started=lambda s, r: 50 + (s % 3)), cur), stuck, skip)
    assert g["verdict"] == "기각" and "GF_flight_starts" in g["why"] and g["criteria"]["P1_N_hide"]["ok"]
    # 더 오래·일찍 달림 (실행 FLEE 몫이 유의하게 많다 — 두뇌가 반사 전에 스스로 달아나도 센다) → GV 기각
    g = lv.gate_live(ev(_fake(seeds, cb, chase=cf, hidden=better, flee=lambda s, r: 0.10 + 0.01 * (s % 2)), cur), stuck, skip)
    assert g["verdict"] == "기각" and g["why"] == "지킴 기준 실패: GV_flee_time" and g["criteria"]["P1_N_hide"]["ok"]
    # 긴 추격이 잡힘·잘림으로 끝남 (잡힘·굶음·잘림으로 끝난 도망 몫이 유의하게 많다) → GC 기각 (잡힘이 늘면 GH 도)
    g = lv.gate_live(ev(_fake(seeds, cb, chase=cf, hidden=better, unsafe=lambda s, r: 4 + (s % 2)), cur), stuck, skip)
    assert g["verdict"] == "기각" and "GC_flight_unsafe" in g["why"] and g["criteria"]["P1_N_hide"]["ok"]
    # 게임 세계 G 에서 쫓긴 시간이 길어짐 → GG_chase 기각 (G 지킴은 그대로)
    g = lv.gate_live(ev(good, _fake(seeds, cb, chase=lambda s, r: fl[(s, r)] + 1.0, hidden=ch)), stuck, skip)
    assert g["verdict"] == "기각" and g["why"] == "지킴 기준 실패: GG_chase"
    # 쫓긴 도망이 없는 시드(쫓긴 도망 C = 0 — 그 시드 값 없음)는 짝에서 빠진다 (빠진 수를 적는다) — 남은 시드로 판단
    none3 = dict(own=lambda s, r: 0 if s in (35001, 35002, 35003) else 20, started=lambda s, r: 1 if s in (35001, 35002, 35003) else 40,
                 unsafe=lambda s, r: 1 if s in (35001, 35002, 35003) else 2)
    g = lv.gate_live(ev(_fake(seeds, cb, chase=cf, hidden=lambda s, r: 0 if s in (35001, 35002, 35003) else better(s, r), **none3), cur), stuck, skip)
    assert g["n_flight"] == 37 and g["dropped_flight"] == [35001, 35002, 35003] and g["n"] == 40
    assert g["t_crit_flight"] == pytest.approx(lv.t_crit(36)) and g["criteria"]["P1_N_hide"]["n"] == 37 and g["criteria"]["GH_flight_caught"]["n"] == 37
    assert "빠진 시드 3" in g["criteria"]["P1_N_hide"]["rule"] and "빠진 시드 3: 35001, 35002, 35003" in lv.fmt_flight(g)
    # 한 시드만 남으면 짝 t 를 셀 수 없다 — 기각
    one_left = dict(own=lambda s, r: 20 if s == 35000 else 0, started=lambda s, r: 40 if s == 35000 else 1, unsafe=lambda s, r: 2 if s == 35000 else 1)
    g = lv.gate_live(ev(_fake(seeds, cb, chase=cf, hidden=lambda s, r: better(s, r) if s == 35000 else 0, **one_left), cur), stuck, skip)
    assert g["verdict"] == "기각" and "숨음 비율을 잴 시드 1개" in g["why"] and g["brief"] == "숨음 비율 잴 시드 1개 (2개 이상)"
    # 지킴은 그대로
    g = lv.gate_live(ev(good, _fake(seeds, cb, starved=lambda s, r: 14, chase=cf, hidden=ch)), stuck, skip)
    assert g["verdict"] == "기각" and "GG_starved" in g["why"]                 # 게임 세계에서 더 굶는다
    g = lv.gate_live(ev(_fake(seeds, cb, starved=lambda s, r: 14, chase=cf, hidden=better), cur), stuck, skip)
    assert g["verdict"] == "기각" and "GN_starved" in g["why"]
    g = lv.gate_live(ev(good, _fake(seeds, cb, cover=1, chase=cf, hidden=ch)), stuck, skip)
    assert "G4_catch_in_shelter" in g["why"]
    stuck_bad = dict(summary=dict(deer_stuck=2, wolf_stuck=1, wolf_wall_stuck=3, worlds=15))
    g = lv.gate_live(ev(good, cur), dict(current=stuck0, candidate=stuck_bad), skip)
    assert "G5_stuck" in g["why"]
    g = lv.gate_live(ev(good, cur), None, skip)
    assert g["verdict"] == "기각" and "G5_stuck" in g["why"]                   # 끼임 세기가 없으면 통과가 아니다
    g = lv.gate_live(ev(good, _fake(seeds, cb, shelter=0.2, chase=cf, hidden=ch)), stuck, skip)
    assert "G6_no_exploit" in g["why"]
    g = lv.gate_live(ev(good, cur), stuck, dict(ok=False, steps=1800))
    assert g["verdict"] == "기각" and "재현 확인" in g["why"]
    g = lv.gate_live(ev(good, cur), stuck, dict(ok=True, steps=1800))
    assert g["verdict"] == "통과" and g["criteria"]["R_check"]["ok"] is True
    few = seeds[:3]
    g = lv.gate_live(dict(N=dict(current=_fake(few, cb, chase=cf, hidden=ch), candidate=_fake(few, cb, chase=cf, hidden=better)),
                          G=dict(current=_fake(few, cb, chase=cf, hidden=ch), candidate=_fake(few, cb, chase=cf, hidden=ch))), stuck, skip)
    assert g["n"] == 3 and g["t_crit"] == pytest.approx(4.303, abs=1e-3) and g["t_crit_flight"] == pytest.approx(4.303, abs=1e-3)   # 문턱은 시드 수에서
    one = seeds[:1]                                                           # 시드 하나: 짝 t 를 셀 수 없다 — 기각
    g = lv.gate_live(dict(N=dict(current=_fake(one, cb, chase=cf, hidden=ch), candidate=_fake(one, cb, chase=cf, hidden=better)),
                          G=dict(current=_fake(one, cb, chase=cf, hidden=ch), candidate=_fake(one, cb, chase=cf, hidden=ch))), stuck, skip)
    assert g["n"] == 1 and g["criteria"]["P1_N_hide"]["t"] == math.inf
    assert g["verdict"] == "기각" and not g["passed"] and "판정 시드 1개" in g["why"] and not g["criteria"]["P1_N_hide"]["ok"]
    assert not any(v["ok"] for k, v in g["criteria"].items() if k.startswith(("GH_", "GN_", "GF_", "GE_", "GV_", "GC_", "GG_")))
    # 도망 기록이 없는 판(옛 실행기)·옛 꼴 기록(쫓긴 시간 없음)·숨은 뒤 지켜보기가 없는 기록(옛 저장·C++ 평가기)은 받지 않는다
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
    nohide = _fake(seeds, cb)
    for w in nohide["worlds"]:
        w["flight"].pop("hide")
    with pytest.raises(ValueError, match="숨은 뒤 지켜보기"):
        lv.gate_live(ev(good, cur, n_cur=nohide), stuck, skip)
    noep = _fake(seeds, cb)                                                   # 10-24: 쫓김 사건이 없는 기록(옛 저장·이식 전 C++ 평가기)도 받지 않는다
    for w in noep["worlds"]:
        w["flight"].pop("episode")
    with pytest.raises(ValueError, match="쫓김 사건"):
        lv.gate_live(ev(good, cur, n_cur=noep), stuck, skip)
    assert lv.hide_pair(noep, cur)["n"] == 40 and math.isnan(lv.flight_pooled(noep)["ep_hide_share"]) and lv.flight_pooled(noep)["ep_chased"] == 0
    assert lv.flight_pair(nohide, cur)["n"] == 40                             # 쫓긴 시간 셈(보고·도망길 측정의 옛 기록)은 hide 없이도 읽는다
    assert math.isnan(lv.flight_pooled(nohide)["hide_share"]) and lv.flight_pooled(nohide)["chased"] == 0


def test_pilot_flight_pair(lv):
    """예비 측정의 짝 = 관문과 같은 셈 (판정 길이마다 끊은 기록 at[h].flight): 쫓긴 시간(보고)·0.25·0.5·1 초 가를 시드 수, 지킴 GF·GV·GC 차이,
    10-23 숨음 비율(1차)·잡힘 비율(GH) 짝과 2·5·10 %p 가를 시드 수."""
    seeds = list(range(34900, 34920))
    rng = np.random.default_rng(34901)
    fl = {(s, r): float(rng.uniform(4.0, 8.0)) for s in seeds for r in ("A", "B")}
    hb = {(s, r): int(rng.integers(3, 8)) for s in seeds for r in ("A", "B")}

    def multi(shift, hshift):
        res = _fake(seeds, lambda s, r: 10, chase=lambda s, r: fl[(s, r)] + shift(s, r), hidden=lambda s, r: hb[(s, r)] + hshift(s, r))
        for w in res["worlds"]:
            w["at"] = {"1800": dict(caught=w["caught"], starved=w["starved"], alive=w["alive"], flight=w["flight"])}
        return res

    a, b = multi(lambda s, r: -0.5 - 0.5 * (s % 2), lambda s, r: 1 + (s % 2)), multi(lambda s, r: 0.0, lambda s, r: 0)
    p = lv.pilot_flight_pair(a, b, 1800)
    assert p["n"] == 20 and p["diff"] == pytest.approx(-0.75, abs=0.02) and p["sd"] > 0 and p["t"] < -2
    assert set(p["n_needed"]) == {"0.25s", "0.5s", "1s"} and p["n_needed"]["0.25s"] >= p["n_needed"]["0.5s"] >= p["n_needed"]["1s"]
    assert p["starts"]["diff"] == 0.0 and p["flee"]["diff"] == 0.0 and p["unsafe"]["diff"] == 0.0
    assert p["hide"]["n"] == 20 and p["hide"]["diff"] == pytest.approx(1.5 / 30, abs=1e-9) and p["hide"]["t"] > 2 and p["hide"]["dropped"] == []
    assert set(p["hide"]["n_needed"]) == {"2%p", "5%p", "10%p"} and p["hide"]["n_needed"]["2%p"] >= p["hide"]["n_needed"]["10%p"]
    assert p["hide_caught"]["diff"] == 0.0 and p["hide_caught"]["n"] == 20
    # 10-24 쫓김 사건 짝 (1차 사건 숨음 비율·GH·GE — 이 짜 맞춘 기록은 도망마다 사건 하나라 숨음 비율은 도망 단위와 같다)
    assert p["ep_hide"]["diff"] == pytest.approx(p["hide"]["diff"]) and p["ep_hide"]["n"] == 20 and set(p["ep_hide"]["n_needed"]) == {"2%p", "5%p", "10%p"}
    assert p["ep_caught"]["diff"] == pytest.approx(-1.5 / 30, abs=1e-9) and p["ep_starts"]["diff"] == 0.0     # 지켜보기 안 잡힘이 숨음으로 바뀐 만큼
    fp = lv.flight_pooled(lv.at_horizon(a, 1800))
    assert fp["started"] == 40 * 40 and fp["own_n"] == 20 * 40 and fp["started_per_seed"] == pytest.approx(80) and fp["chased"] == 30 * 40
    text = lv.fmt_pilot(dict(pilot="p_t", seeds=[34900, 34919], snapshot="s.json", workers=2, times={}, flight_costs=[0.0],
                             vs_current={"r5": {"N": {"1800": dict(flight=p, caught=lv.pilot_pair(a, b, 1800))}}},
                             flight_pooled={"r5": {"N": {"1800": fp}}}))
    assert "두뇌 − 지금 두뇌" in text and "도망 끝 까닭" in text and "쫓긴 시간 지금 초" in text and "GF 시작/1000" in text
    assert "숨음 비율 지금" in text and "2·5·10 %p 가를 시드 수" in text and "숨음 비율 (쫓긴 도망 가운데, 전체 합)" in text
    assert "1차 사건 숨음 비율·지킴 GH·GE" in text and "사건 숨음 비율 지금" in text and "도망 단위 숨음 비율·잡힘 비율" in text
    assert "f_dec = None (R5 조리법 값 0.858922)" in text                    # 옛 기록(조리법 값 없음)은 옛 글 그대로
    text = lv.fmt_pilot(dict(pilot="p_t", seeds=[34900, 34919], snapshot="s.json", workers=2, times={}, flight_costs=[0.0], f_dec_T=0.680748,
                             f_dec_recipe=0.714694, profile="route5"))
    assert "f_dec = 0.680748 (학습에 쓴 조리법 값 0.714694 — 두뇌 묶음 route5)" in text and "R5 조리법 값" not in text   # 10-27 (10): 판 5 묶음 글 고침


# --------------------------------------------------------------------- #
# 10-21 (4) 두 번 보기(중간 판정)·지금 두뇌 판정 저장·판정 실행기 갈림
# --------------------------------------------------------------------- #


def test_seq_boundaries(lv, monkeypatch):
    """경계 셈: Lan–DeMets O'Brien–Fleming 꼴 쓰기, 같은 간격 두 번의 알려진 z 값(2.963·1.969), 쓴 α 합 ≤ α, 실제 자유도 t 문턱, scipy 없이도 같은 값,
    앞서 통과를 끄면(기본 — 중간에 α 를 쓰지 않으면) 끝 문턱 = 옛 한 번 보기 t_crit. 켜면 끝 문턱 = t_{α − α₁} (합집합 상한 — 두 번 합이 t 분포에서 정확히 α)."""
    a = lv.LIVE["seq_alpha"]
    assert a == 0.025 and lv.LIVE["seq_spending"] == "obf" and lv.LIVE["seq_efficacy"] is False
    assert lv.seq_interim_bound(40, 80)["alpha1"] == 0.0 and lv.seq_final_bound(80, dict(lv.seq_interim_bound(40, 80), n1=40))["bound"] == lv.t_crit(79)
    monkeypatch.setitem(lv.LIVE, "seq_efficacy", True)
    assert lv.obf_spend(0.5, a) == pytest.approx(0.0015253, abs=1e-7) and lv.obf_spend(1.0, a) == pytest.approx(a, abs=1e-12) and lv.obf_spend(0.0, a) == 0.0
    i = lv.seq_interim_bound(40, 80)
    f = lv.seq_final_bound(80, dict(i, n1=40))
    c1, c2 = lv.SEQ_OBF_REF[0.5]
    assert i["c1"] == pytest.approx(c1, abs=5e-4) and f["c2"] == pytest.approx(c2, abs=5e-4) and f["rho"] == pytest.approx(math.sqrt(0.5))
    assert i["bound"] == pytest.approx(3.1595, abs=1e-3) and f["bound"] == pytest.approx(2.0183, abs=1e-3)      # n₁ 40 · 80 의 t 문턱
    assert f["bound_z"] == pytest.approx(1.9994, abs=1e-3) and f["bound"] > f["bound_z"] > lv.t_crit(79)   # z 경계를 옮긴 값(참고)보다 엄격
    from scipy.stats import t as st_t0

    assert float(st_t0.sf(i["bound"], 39)) == pytest.approx(i["alpha1"], abs=1e-12)                       # 중간 몫 = α₁ (t 분포에서 정확)
    assert float(st_t0.sf(f["bound"], 79)) == pytest.approx(a - i["alpha1"], abs=1e-12) and f["alpha2"] == pytest.approx(a - i["alpha1"])
    for n_int, n_fin in ((40, 80), (37, 74), (20, 80), (5, 10)):                                           # 두 번 합 = α (합집합 상한)
        bi = lv.seq_interim_bound(n_int, 80)
        bf = lv.seq_final_bound(n_fin, dict(bi, n1=n_int))
        tot = float(st_t0.sf(bi["bound"], n_int - 1) + st_t0.sf(bf["bound"], n_fin - 1))
        assert tot <= a + 1e-12 and tot == pytest.approx(a, abs=1e-9)
    for frac in (0.2, 0.3, 0.5, 0.7, 0.9):                                                                  # 쓴 α 합 ≤ α (끝은 나머지를 다 쓴다)
        a1 = lv.obf_spend(frac, a)
        cc1 = lv.norm_isf(a1)
        cc2 = lv.seq_final_z(cc1, math.sqrt(frac), a, a1)
        tot = a1 + lv.bvn_below_above(cc1, cc2, math.sqrt(frac))
        assert tot <= a + 1e-9 and tot == pytest.approx(a, abs=1e-7) and a1 < a * frac
    from scipy.stats import multivariate_normal, norm

    for c1_, c2_, r in ((2.96, 1.97, 0.707), (2.0, 2.5, 0.3), (3.5, 1.5, 0.9)):                          # 이변량 정규 적분 = scipy
        ref = norm.cdf(c1_) - multivariate_normal.cdf([c1_, c2_], mean=[0, 0], cov=[[1, r], [r, 1]], abseps=1e-10, releps=1e-10)
        assert lv.bvn_below_above(c1_, c2_, r) == pytest.approx(ref, abs=1e-7)
    assert lv.bvn_below_above(math.inf, 1.96, 0.5) == pytest.approx(0.025, abs=1e-4)
    assert lv.bvn_below_above(2.0, 1.0, 1.0) == pytest.approx(norm.sf(1.0) - norm.sf(2.0))              # 상관 1 (빠진 뒤 시드가 없음)
    # 앞서 통과를 끄거나 중간에 보지 못하면 끝 문턱 = 옛 문턱 (비트 단위)
    for n in (2, 10, 37, 80, 100):
        assert lv.seq_final_bound(n, None)["bound"] == lv.t_crit(n - 1)
        assert lv.seq_final_bound(n, dict(alpha1=0.0, n1=5, c1=math.inf))["bound"] == lv.t_crit(n - 1)
    monkeypatch.setitem(lv.LIVE, "seq_efficacy", False)
    assert lv.seq_interim_bound(40, 80)["alpha1"] == 0.0 and lv.seq_interim_bound(40, 80)["bound"] == math.inf
    monkeypatch.setitem(lv.LIVE, "seq_efficacy", True)
    assert lv.seq_interim_bound(1, 80)["bound"] == math.inf                                                  # 짝 t 를 셀 수 없으면 보지 않는다
    # 빠진 시드: 정보 몫·상관을 실제 수에서
    i37 = lv.seq_interim_bound(37, 80)
    assert i37["frac"] == pytest.approx(37 / 80) and i37["alpha1"] < i["alpha1"] and i37["bound"] > i["bound"]
    assert lv.seq_final_bound(74, dict(i37, n1=37))["rho"] == pytest.approx(math.sqrt(37 / 74))
    # scipy 없이 (정수 자유도 닫힌 식) 같은 값
    from scipy.stats import t as st_t

    for df in (1, 2, 3, 4, 7, 39, 79, 120):
        for p in (0.025, 0.0015, 1e-6, 0.4):
            assert lv.t_isf_math(p, df) == pytest.approx(float(st_t.isf(p, df)), rel=1e-8)
            assert lv.t_sf_math(-1.3, df) == pytest.approx(float(st_t.sf(-1.3, df)), abs=1e-12)
    want = (i["bound"], f["bound"], f["bound_z"])
    monkeypatch.setitem(sys.modules, "scipy.stats", None)                                                  # scipy 를 못 가져온다
    i2 = lv.seq_interim_bound(40, 80)
    f2 = lv.seq_final_bound(80, dict(i2, n1=40))
    assert (i2["bound"], f2["bound"], f2["bound_z"]) == pytest.approx(want, abs=1e-9)
    # 시점: n 80 → 앞 40, 시드가 적으면 한 번 보기
    assert lv.seq_sizes(80) == 40 and lv.seq_sizes(10) == 5 and lv.seq_sizes(3) == 2 and lv.seq_sizes(2) is None
    assert lv.seq_sizes(80, 0.25) == 20
    monkeypatch.setitem(lv.LIVE, "seq_interim_frac", None)
    assert lv.seq_sizes(80) is None
    with pytest.raises(ValueError):
        lv.seq_sizes(80, 1.0)


def test_seq_type1_simulation(lv, monkeypatch):
    """흉내 내기 (앞서 통과를 켠 때): 나아지지 않은 두뇌(짝 차이 평균 0)가 두 번 보기에서 우연히 통과할 몫 ≤ 2.5% (중간 경계 + 끝 문턱, 중간 기각은
    구속력 없음 — 빼고 셈). 문턱은 합집합 상한(두 몫의 합 = α 를 t 분포에서 정확히 — test_seq_boundaries)이라 흉내 내기는 그보다 조금 작아야 한다.
    중간에 쓴 몫 ≈ α₁, 중간 기각은 절반쯤. 끈 기본은 통과 쪽이 옛 한 번 보기와 같다(중간 기각은 통과를 늘리지 않는다).
    10-23: 1차 숨음 비율은 클수록 좋다 — 통과 = 짝 t ≥ +문턱, 중간 기각 = 짝 t ≤ −seq_futility_t (쫓긴 시간 때와 부호만 뒤집음)."""
    monkeypatch.setitem(lv.LIVE, "seq_efficacy", True)
    n, k = 80, lv.seq_sizes(80)
    b1 = lv.seq_interim_bound(k, n)
    b2 = lv.seq_final_bound(n, dict(b1, n1=k))["bound"]
    b2z = lv.seq_final_bound(n, dict(b1, n1=k))["bound_z"]
    fut_t = -lv.LIVE["seq_futility_t"]
    rng = np.random.default_rng(35123)
    rej = rej_z = early = fut = tot = off = single = 0
    for _ in range(4):
        x = rng.standard_normal((50000, n))
        t1 = x[:, :k].mean(1) / (x[:, :k].std(1, ddof=1) / math.sqrt(k))
        t2 = x.mean(1) / (x.std(1, ddof=1) / math.sqrt(n))
        rej += int(((t1 >= b1["bound"]) | (t2 >= b2)).sum())
        rej_z += int(((t1 >= b1["bound"]) | (t2 >= b2z)).sum())
        early += int((t1 >= b1["bound"]).sum())
        fut += int((t1 <= fut_t).sum())
        off += int(((t1 > fut_t) & (t2 >= lv.t_crit(n - 1))).sum())       # 끈 기본: 중간 기각을 넘긴 것만 끝 문턱(옛 것)으로
        single += int((t2 >= lv.t_crit(n - 1)).sum())                     # 옛 한 번 보기
        tot += len(x)
    se = math.sqrt(0.025 * 0.975 / tot)
    assert rej / tot <= 0.025 and rej < rej_z                                                    # 합집합 상한: 넘지 않는다 (z 를 옮긴 문턱보다 엄격)
    assert off <= single and single / tot == pytest.approx(0.025, abs=3 * se)                  # 끈 기본은 옛 한 번 보기보다 통과가 늘지 않는다
    assert early / tot == pytest.approx(b1["alpha1"], abs=4 * math.sqrt(b1["alpha1"] / tot))
    assert fut / tot == pytest.approx(0.5, abs=0.01)


def _row(seed, region, *, caught=27, starved=10, chase=6.0, cover=0, shelter=0.06, hidden=5):
    return _fake([seed], lambda s, r: caught, starved=lambda s, r: starved, chase=lambda s, r: chase, cover=cover, shelter=shelter,
                 hidden=lambda s, r: hidden, regions=(region,))["worlds"][0]


def _stuck_row(seed, region):
    return dict(seed=seed, region=region, wolf_events=[], deer_events=[], old_wolf=[], old_deer=[], wall_events=[], stuck_w=0, win_w=10, stuck_wall=0,
                stuck_d=0, win_d=10)


def _fake_runner(scen: dict, log: list):
    """가짜 판정 실행기: 꼬리표(두뇌:세계)·시드·지역으로 짜 맞춘 결과. scen[(두뇌, 세계)] = 결과 칸 함수(seed, region) → _row 인자."""
    def run(items, on_done=None):
        log.append([(t, int(j["seed"])) for _, t, j in items])
        out = []
        for _, tag, j in items:
            brain, world = tag.rsplit(":", 1)
            s, r = int(j["seed"]), str(j["region"])
            out.append((tag, _stuck_row(s, r) if world == "stuck" else _row(s, r, **scen.get((brain, world), lambda s_, r_: {})(s, r))))
            if on_done:
                on_done()
        return out
    return run


@pytest.fixture(scope="module")
def seq_setup(lv, prepared):
    """작은 판 (N 시드 10 → 앞 5, G 시드 5, 끼임 2 — 세계는 돌리지 않는다)과 지금 두뇌 판(가짜). 지금 두뇌의 숨어 살아남은 도망 hb(쫓긴 도망 30 가운데
    3~7 — 은신처 끝 10)·쫓긴 시간 base."""
    plan = lv.default_plan(judge=(35000, 35009), judge_g=(35000, 35004), stuck=(35000, 35001), horizon=20, horizon_g=30, workers=1)
    rng = np.random.default_rng(35124)
    base = {(s, r): float(rng.uniform(4.0, 8.0)) for s in range(35000, 35010) for r in prepared["regions"]}
    hb = {(s, r): int(rng.integers(3, 8)) for s in range(35000, 35010) for r in prepared["regions"]}
    log: list = []
    cur_row = lambda s, r: dict(chase=base[(s, r)], hidden=hb[(s, r)])                     # noqa: E731
    run = _fake_runner({("current", "N"): cur_row, ("current", "G"): cur_row}, log)
    its = (lv.eval_items(prepared, "current", lv.OBS21ZERO, lv.seeds_of(plan["judge"]), 20, "N")
           + lv.eval_items(prepared, "current", lv.OBS21ZERO, lv.seeds_of(plan["judge_g"]), 30, "G")
           + lv.stuck_items(prepared, "current", lv.OBS21ZERO, lv.seeds_of(plan["stuck"]), 30))
    cur = lv.gather(run(its), {"current": lv.OBS21ZERO}, {"current:N": 20, "current:G": 30})
    return dict(plan=plan, base=base, hb=hb, cur=cur)


def _judge(lv, prepared, seq_setup, scen, tmp_path=None):
    log: list = []
    st = lv.Status(tmp_path) if tmp_path is not None else None
    base, hb = seq_setup["base"], seq_setup["hb"]
    scen = {("candidate", "G"): lambda s, r: dict(chase=base[(s, r)], hidden=hb[(s, r)])} | scen
    jc = lv.judge_candidate(prepared, lv.OBS21ZERO, seq_setup["cur"], seq_setup["plan"], dict(ok=None, why="시험"), st, runner=_fake_runner(scen, log))
    return jc, log


def test_seq_interim_futility(lv, prepared, seq_setup, tmp_path):
    """중간 판정 기각(나아지지 않음): 앞 절반 숨음 비율 짝 t ≤ 0 → 기각, 후보 G·끼임·뒤 절반은 돌리지 않는다. 상태 줄 '중간 판정: 기각(나아지지 않음)'.
    쫓긴 시간이 짧아져도(보고만) 숨음 비율이 줄면 기각이다."""
    base, hb = seq_setup["base"], seq_setup["hb"]
    jc, log = _judge(lv, prepared, seq_setup, {("candidate", "N"): lambda s, r: dict(chase=base[(s, r)] - 1.0, hidden=hb[(s, r)] - 1 - (s % 3) // 2)},
                     tmp_path)
    assert len(log) == 1 and {t for t, _ in log[0]} == {"candidate:N"} and sorted({s for _, s in log[0]}) == list(range(35000, 35005))
    g = jc["gate"]
    assert jc["stage"] == g["stage"] == "interim_futility" and not jc["complete"] and g["verdict"] == "기각" and not g["passed"]
    s = g["seq"]
    assert s["action"] == "futility" and s["n_int"] == 5 and s["n_total"] == 10 and s["t"] < 0 and s["seeds_int"] == [35000, 35004]
    assert set(g["criteria"]) == {"R_check", "P1_N_hide", "GH_flight_caught", "REPORT_N_flight_hide", "REPORT_N_flight_caught", "REPORT_N_chase"}
    assert not g["criteria"]["P1_N_hide"]["ok"] and g["criteria"]["P1_N_hide"]["unit"] == "episode" and g["unit"] == "episode"
    assert all(g["criteria"][k]["ok"] is None for k in ("GH_flight_caught", "REPORT_N_flight_hide", "REPORT_N_flight_caught", "REPORT_N_chase"))
    assert "G" not in g["report"]["flight"]
    assert g["brief"].startswith("중간 판정 — 1차 사건 숨음 비율 ") and g["brief"].endswith("(나아지지 않음)") and "뒤 절반·게임 세계·끼임은 돌리지 않았다" in g["why"]
    d = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert d["state"] == "gating" and d["message"].startswith("중간 판정: 기각(나아지지 않음) — 사건 숨음 비율 ")
    g.update(candidate="c.zip", current="k.zip", profile="시험")
    assert math.isnan(g["t_crit_flight"]) and g["t_futility_flight"] == 0.0                     # 판정을 정한 것은 중간 기각 경계 (통과 문턱 아님)
    md = lv.gate_md("a1_x", g, "- 지금 두뇌 시험: 저장된 결과 다시 씀")
    assert "## 중간 판정" in md and "기각(나아지지 않음)" in md and "G 돌리지 않음" in md and "저장된 결과 다시 씀" in md
    head = md.split("\n")[2]
    assert "중간 기각 경계 t ≤ 0" in head and "문턱 inf" not in md and "문턱 nan" not in head and "문턱 +3." not in head
    assert "- 경계: 기각(나아지지 않음) 짝 t ≤ 0 · 앞서 통과 끔" in md and "숨음 비율 짝 t −" in g["criteria"]["P1_N_hide"]["rule"]
    st = lv.Status(tmp_path)
    lv.final_status(st, dict(state="rejected", stage="interim_futility", stage_note=g["note"], last_result=f"기각: {g['brief']}"), 0)
    assert json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))["message"].startswith("중간 판정: 기각(나아지지 않음) — 게임 두뇌 그대로")
    # 같은 두뇌(짝 차이 0 → t 0) 도 나아지지 않음
    jc, log = _judge(lv, prepared, seq_setup, {("candidate", "N"): lambda s, r: dict(chase=base[(s, r)], hidden=hb[(s, r)])})
    assert jc["stage"] == "interim_futility" and len(log) == 1 and jc["gate"]["seq"]["t"] == 0.0
    # 숨음 비율이 커지는 쪽이면(짝 t > 0) 중간에 끝내지 않는다 — 쫓긴 시간이 길어져도(보고만)
    jc, log = _judge(lv, prepared, seq_setup, {("candidate", "N"): lambda s, r: dict(chase=base[(s, r)] + 1.0, hidden=hb[(s, r)] + 1 + (s % 2))})
    assert jc["stage"] == "final" and len(log) == 2 and jc["gate"]["seq"]["t"] > 0 and jc["gate"]["seq"]["action"] == "continue"


def test_seq_interim_efficacy_checks_full_guards(lv, prepared, seq_setup, tmp_path, monkeypatch):
    """앞서 통과(켰을 때 — 기본 끔): 앞 절반 숨음 비율 짝 t ≥ +b₁ 이면 1차는 통과로 정하지만, 지킴은 뒤 절반까지 N 전체·G 전체·끼임으로 본다(10-21 검토 —
    앞 절반만 보면 뒤 절반의 은신처 안 잡힘·더 잡힘을 놓쳐 관문이 느슨해진다). 전체 차이가 커지는 쪽이 아니면 1차도 통과가 아니다. 끈 기본은 끝 문턱으로만 본다."""
    base, hb = seq_setup["base"], seq_setup["hb"]
    much_n = lambda s, r: dict(chase=base[(s, r)], hidden=hb[(s, r)] + 2 + (s % 2))      # noqa: E731
    much = {("candidate", "N"): much_n}
    jc, log = _judge(lv, prepared, seq_setup, much, tmp_path)                         # 끈 기본: 같은 자료, 끝 판정 (옛 한 번 보기 문턱)
    g = jc["gate"]
    assert jc["stage"] == "final" and g["passed"] and g["seq"]["alpha1"] == 0.0 and g["t_crit_flight"] == lv.t_crit(g["n_flight"] - 1)
    assert "interim" not in g["criteria"]["P1_N_hide"] and len(log) == 2
    monkeypatch.setitem(lv.LIVE, "seq_efficacy", True)
    jc, log = _judge(lv, prepared, seq_setup, much, tmp_path)
    g = jc["gate"]
    assert jc["stage"] == g["stage"] == "interim_efficacy" and jc["complete"] and g["passed"] and g["verdict"] == "통과"
    assert g["summary"].endswith(" — 1차 중간 판정 (시드 5)") and "1차는 중간 판정 앞서 통과 경계로" in g["why"]
    assert len(log) == 2 and {t for t, _ in log[0]} == {"candidate:N"} and {t for t, _ in log[1]} == {"candidate:N", "candidate:G", "candidate:stuck"}
    assert sorted({s for t, s in log[1] if t == "candidate:N"}) == list(range(35005, 35010))      # 뒤 절반도 돌린다
    s = g["seq"]
    assert s["action"] == "efficacy" and s["t"] >= s["bound"] and s["alpha1"] > 0 and s["final"]["bound"] == pytest.approx(g["t_crit_flight"])
    p1 = g["criteria"]["P1_N_hide"]
    assert p1["ok"] and p1["ok_final"] and p1["interim"]["bound"] == pytest.approx(s["bound"]) and "중간에 넘음" in p1["rule"]
    assert g["n"] == 10 and g["n_g"] == 5 and g["t_crit_flight"] > lv.t_crit(g["n_flight"] - 1)                          # 지킴은 N 전체 · G 전체
    d = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert d["message"].startswith("후보 판정 뒤 절반·게임 세계") and "1차 앞서 통과" in d["message"]
    g.update(candidate="c.zip", current="k.zip", profile="시험")
    md = lv.gate_md("a1_x", g)
    assert "중간 앞서 통과 경계 +" in md.split("\n")[2] and "지킴은 뒤 절반까지 N 전체" in md

    st = lv.Status(tmp_path)
    lv.final_status(st, dict(state="exported", round=1, stage="interim_efficacy"), 1)
    assert "(1차 중간 판정 앞서 통과)" in json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))["message"]

    def rejected(scen, *want):
        jc_, log_ = _judge(lv, prepared, seq_setup, scen)
        g_ = jc_["gate"]
        assert jc_["stage"] == "interim_efficacy" and jc_["complete"] and len(log_) == 2 and g_["verdict"] == "기각", g_["why"]
        assert all(w in g_["why"] for w in want), g_["why"]
        return g_

    # 검토 사례 1: 뒤 절반 시드 35007 에서 은신처 안 잡힘 — 앞 절반만 보면 놓친다 (G4 N 몫은 N 전체)
    g = rejected({("candidate", "N"): lambda s, r: dict(much_n(s, r), cover=1 if s == 35007 else 0)}, "G4_catch_in_shelter")
    assert g["criteria"]["P1_N_hide"]["ok"] and g["criteria"]["G4_catch_in_shelter"]["N"] >= 1
    # 검토 사례 2: 뒤 절반에서 더 잡힌다 (잡힘 33~34 대 27) — GN_caught·GN_alive 는 N 전체로
    g = rejected({("candidate", "N"): lambda s, r: dict(much_n(s, r), caught=27 if s < 35005 else 33 + s % 2)}, "GN_caught", "GN_alive")
    assert g["criteria"]["GN_caught"]["t"] > lv.t_crit(9)
    # 게임 세계에서 더 굶는다 (G 지킴)
    rejected(much | {("candidate", "G"): lambda s, r: dict(chase=base[(s, r)], hidden=hb[(s, r)], starved=13 + (s % 2))}, "GG_starved")
    # 중간에는 넘었지만 뒤 절반이 크게 나빠져 전체 차이가 줄어드는 쪽 → 1차도 통과가 아니다
    g = rejected({("candidate", "N"): lambda s, r: dict(chase=base[(s, r)], hidden=hb[(s, r)] + (2 + (s % 2) if s < 35005 else -3))}, "1차 P1 실패")
    p1 = g["criteria"]["P1_N_hide"]
    assert p1["diff"] < 0 and not p1["ok"] and not p1["ok_final"] and p1["interim"]["t"] >= p1["interim"]["bound"]


def test_seq_final_equals_single_look(lv, prepared, seq_setup, monkeypatch):
    """앞서 통과를 끄면(중간에 α 를 쓰지 않음) 끝 판정 = 옛 한 번 보기 관문(같은 자료로 gate_live) — 문턱·판정·칸 모두. 중간 판정을 끄면 한 번에 돌려 옛 순서 그대로.
    켜면 끝 문턱만 조금 엄격하다(그 사이의 t 는 한 번 보기 통과·두 번 보기 기각)."""
    base, hb = seq_setup["base"], seq_setup["hb"]
    noise = dict(zip(range(35000, 35010), (1, 0, 1, 0, 2, 1, 0, 1, -1, 1)))               # 앞 절반 짝 t 약 +2 — 중간에 끝나지 않는다
    mild = {("candidate", "N"): lambda s, r: dict(chase=base[(s, r)], hidden=hb[(s, r)] + noise[s])}

    def single(jc):
        cnd, cur = jc["cand"], seq_setup["cur"]
        return lv.gate_live({w: dict(current=cur[f"current:{w}"], candidate=cnd[f"candidate:{w}"]) for w in ("N", "G")},
                            dict(current=cur["current:stuck"], candidate=cnd["candidate:stuck"]), dict(ok=None, why="시험"))

    def same(a, b):
        assert a["verdict"] == b["verdict"] and a["why"] == b["why"] and a["t_crit_flight"] == b["t_crit_flight"] and a["n_flight"] == b["n_flight"]
        assert {k: v["ok"] for k, v in a["criteria"].items()} == {k: v["ok"] for k, v in b["criteria"].items()}
        assert a["criteria"]["P1_N_hide"]["t"] == b["criteria"]["P1_N_hide"]["t"]

    monkeypatch.setitem(lv.LIVE, "seq_efficacy", False)
    monkeypatch.setitem(lv.LIVE, "seq_futility_t", None)
    jc, log = _judge(lv, prepared, seq_setup, mild)
    assert jc["stage"] == "final" and len(log) == 2 and jc["gate"]["seq"]["alpha1"] == 0.0
    same(jc["gate"], single(jc))
    assert jc["gate"]["t_crit_flight"] == lv.t_crit(jc["gate"]["n_flight"] - 1)
    monkeypatch.setitem(lv.LIVE, "seq_futility_t", 0.0)                                  # 중간 기각만 켜도 (나아지는 쪽이면) 끝 문턱은 옛 것
    jc2, _ = _judge(lv, prepared, seq_setup, mild)
    assert jc2["stage"] == "final" and jc2["gate"]["seq"]["t"] > 0
    same(jc2["gate"], single(jc2))
    monkeypatch.setitem(lv.LIVE, "seq_interim_frac", None)                                # 중간 판정 끔 → 한 번에 (옛 순서)
    jc3, log3 = _judge(lv, prepared, seq_setup, mild)
    assert jc3["stage"] == "single" and len(log3) == 1 and {t for t, _ in log3[0]} == {"candidate:N", "candidate:G", "candidate:stuck"}
    same(jc3["gate"], single(jc3))
    assert jc3["gate"]["seq"] is None and "한 번 보기" in lv.fmt_seq(jc3["gate"])
    monkeypatch.setitem(lv.LIVE, "seq_interim_frac", 0.5)
    monkeypatch.setitem(lv.LIVE, "seq_efficacy", True)                                    # 앞서 통과를 켜면 끝 문턱만 바뀐다 (판정 칸 셈은 같다)
    jc4, _ = _judge(lv, prepared, seq_setup, mild)
    assert jc4["stage"] == "final" and jc4["gate"]["seq"]["alpha1"] > 0
    assert jc4["gate"]["t_crit_flight"] > jc["gate"]["t_crit_flight"] and jc4["gate"]["criteria"]["P1_N_hide"]["t"] == jc["gate"]["criteria"]["P1_N_hide"]["t"]


def test_eval_runner_switch(lv, tmp_path, monkeypatch):
    """판정 실행기 갈림: 'python' 은 워커 풀(일이 없으면 빈 목록), 모르는 실행기는 멈춤, 등록한 실행기는 꼬리표·순서를 맞춰 봐야 받는다.
    live.py 옆 <이름>.py 의 run_items·version·HIDE_WATCH 는 LIVE evaluator 이름만으로 불러 등록한다(네이티브 판정기를 끼울 자리).
    10-23 (변경 기록 (6)): 숨은 뒤 10 초 지켜보기를 세지 못하는 실행기(hide_watch 거짓)는 분명한 말로 거부한다."""
    assert lv.LIVE["evaluator"] == "ceval" and lv.eval_runner([], 4, "python") == []         # 10-24 (7) 덧붙임: 기본 실행기 = C++ 평가기 (쫓김 사건 이식 뒤)
    with pytest.raises(ValueError, match="모르는 판정 실행기"):
        lv.eval_runner([("world", "x:N", {})], 2, "native")
    calls = []
    lv.EVALUATORS["fake"] = dict(run=lambda items, w, on_done: calls.append(w) or [(t, dict(seed=j["seed"])) for _, t, j in items], version=lambda: "f1",
                                 hide_watch=True, episode=True)
    try:
        items = [("world", "a:N", dict(seed=1)), ("world", "a:N", dict(seed=2))]
        assert lv.eval_runner(items, 3, "fake") == [("a:N", dict(seed=1)), ("a:N", dict(seed=2))] and calls == [3]
        lv.EVALUATORS["fake"]["run"] = lambda items, w, on_done: [("b:N", {})] * len(items)
        with pytest.raises(ValueError, match="꼬리표·순서"):
            lv.eval_runner(items, 3, "fake")
        # 한 묶음은 꼬리표가 같다 — 시드·지역이 일마다 맞아야 받는다 (뒤섞임·다른 지역·겹침·빠진 칸)
        its = [("world", "cur:N", dict(seed=s_, region=r_)) for s_ in (1, 2) for r_ in ("A", "B")]
        rows = [dict(seed=j["seed"], region=j["region"]) for _, _, j in its]
        for name, bad in (("지역 순 정렬", sorted(rows, key=lambda r: (r["region"], r["seed"]))), ("다른 지역", rows[:1] + [dict(rows[1], region="C")] + rows[2:]),
                          ("겹침", rows[:3] + rows[2:3]), ("시드 없음", rows[:3] + [dict(region="B")]), ("글자 시드", rows[:3] + [dict(seed="x", region="B")])):
            lv.EVALUATORS["fake"]["run"] = lambda items, w, on_done, bad=bad: [(t, r) for (_, t, _), r in zip(items, bad)]
            with pytest.raises(ValueError, match="일과 다른 세계"):
                lv.eval_runner(its, 3, "fake")
            assert name
        lv.EVALUATORS["fake"]["run"] = lambda items, w, on_done: [(t, dict(seed=str(j["seed"]), region=j["region"], x=1)) for _, t, j in items]
        assert [r["x"] for _, r in lv.eval_runner(its, 3, "fake")] == [1] * 4                                # 글자 숫자 시드는 같은 시드
        assert lv.eval_code_tag("fake") != lv.eval_code_tag("python")
        lv.EVALUATORS["fake"]["hide_watch"] = False                                          # 숨은 뒤 지켜보기를 세지 못하는 실행기 — 돌리기 전에 거부
        calls.clear()
        with pytest.raises(ValueError, match="10 초 지켜보기"):
            lv.eval_runner(items, 3, "fake")
        assert calls == []
        lv.EVALUATORS["fake"].update(hide_watch=True, episode=False)                         # 10-24: 쫓김 사건을 세지 못하는 실행기 — 돌리기 전에 거부
        with pytest.raises(ValueError, match="쫓김 사건"):
            lv.eval_runner(items, 3, "fake")
        assert calls == []
    finally:
        lv.EVALUATORS.pop("fake", None)
        lv._CODE.pop("fake", None)
    with lv.open_pool(2, "native") as p:
        assert p is None
    (tmp_path / "fakeev.py").write_text("\n".join(["HIDE_WATCH = True", "EPISODE = True",
                                                   "def run_items(items, workers, on_done=None):",
                                                   "    return [(t, dict(seed=j['seed'], w=workers)) for _, t, j in items]",
                                                   "def version():",
                                                   "    return 'fakeev-1'", ""]), encoding="utf-8")
    monkeypatch.setattr(lv, "HERE", tmp_path / "live.py")
    try:
        assert lv.eval_runner([("world", "a:G", dict(seed=7))], 5, "fakeev") == [("a:G", dict(seed=7, w=5))] and "fakeev" in lv.EVALUATORS
        assert lv.eval_code_tag("fakeev") != lv.eval_code_tag("python")
    finally:
        lv.EVALUATORS.pop("fakeev", None)
        lv._CODE.pop("fakeev", None)
    with pytest.raises(ValueError, match="모르는 판정 실행기"):
        lv.eval_runner([("world", "x:N", {})], 2, "os")                                             # 옆 파일이 아닌 모듈 이름은 불러오지 않는다


def test_hide_watch_gate_evaluators(lv, monkeypatch):
    """10-23 (변경 기록 (6)·같은 날 덧붙임): 1차 숨음 비율·지킴 GH 는 숨은 뒤 10 초 지켜보기(flight.hide — cover_then_caught)를 세는 실행기만 쓴다.
    C++ 평가기(results/v3/live/ceval.py — HIDE_WATCH 참: EcoWorldV3.h 도망 기록에 같은 정의로 옮겼다)는 받는다(기본 LIVE evaluator). 세지 못하는
    실행기(hide_watch 거짓)는 분명한 말로 거부한다(eval_runner·require_hide_watch, 판·감시 시작 전 plan_from_args). 평가기 빌드와 무관(ceval.py 를
    불러오기만 한다). 'python' 은 늘 받는다."""
    lv.require_hide_watch("python")
    ev = lv.evaluator("ceval")
    assert ev["hide_watch"] is True and callable(ev["run"])
    lv.require_hide_watch("ceval")
    assert lv.LIVE["evaluator"] == "ceval"                                                          # 10-24 (7) 덧붙임: 쫓김 사건도 C++ 에 옮겨 다시 ceval
    lv.require_hide_watch()
    lv.require_gate_records()                                                                       # 기본 = LIVE evaluator 'ceval' — 숨은 뒤 지켜보기·쫓김 사건 모두
    lv.EVALUATORS["nohide"] = dict(run=lambda items, w, on_done: [], version=lambda: "n1", hide_watch=False, episode=True)
    try:
        for call in (lambda: lv.require_hide_watch("nohide"), lambda: lv.eval_runner([("world", "x:N", dict(seed=1, region="A"))], 2, "nohide")):
            with pytest.raises(ValueError) as ei:
                call()
            msg = str(ei.value)
            assert "판정 실행기 'nohide'" in msg and "cover_then_caught" in msg and "숨음 비율" in msg and "'ceval'" in msg and "'python'" in msg
        monkeypatch.setitem(lv.LIVE, "evaluator", "nohide")
        with pytest.raises(ValueError, match="10 초 지켜보기"):
            lv.require_hide_watch()                                                                 # 기본 = LIVE evaluator
        a = Namespace(root=str(ROOT / "results" / "v3" / "live" / "_never"), workers=4, ckpt=None, steps=None, model_seeds=None, horizon=None,
                      judge_seeds=None, select_seeds=None, stuck_seeds=None, check_seeds=None, skip_check=False, force_export=False, horizon_g=None,
                      judge_seeds_g=None, flight_cost=None)
        with pytest.raises(SystemExit, match="10 초 지켜보기"):
            lv.plan_from_args(a)                                                                     # 판·감시를 시작하지 않는다
        assert not (ROOT / "results" / "v3" / "live" / "_never").exists()
    finally:
        lv.EVALUATORS.pop("nohide", None)
        lv._CODE.pop("nohide", None)


def test_episode_gate_evaluators(lv, monkeypatch):
    """10-24 (변경 기록 (7)·같은 날 덧붙임): 1차 사건 숨음 비율·GH·GE 는 쫓김 사건(flight.episode)을 세는 실행기만 쓴다. C++ 평가기(ceval.py EPISODE 참 —
    EcoWorldV3.h 도망 기록에 같은 정의로 옮겼다)는 받는다(기본 LIVE evaluator). 세지 못하는 실행기(episode 거짓)는 분명한 말로 거부한다
    (require_episode·eval_runner — 돌리기 전, 판·감시 시작 전 plan_from_args). 평가기 빌드와 무관(ceval.py 를 불러오기만 한다). 'python' 은 늘 센다."""
    ev = lv.evaluator("ceval")
    assert ev["episode"] is True and ev["hide_watch"] is True and lv.LIVE["evaluator"] == "ceval"
    lv.require_episode("python")
    lv.require_episode("ceval")
    lv.require_gate_records("ceval")
    lv.require_episode()                                                                            # 기본 = LIVE evaluator 'ceval'
    calls = []
    lv.EVALUATORS["noep"] = dict(run=lambda items, w, on_done: calls.append(w) or [], version=lambda: "e1", hide_watch=True, episode=False)
    try:
        for call in (lambda: lv.require_episode("noep"), lambda: lv.require_gate_records("noep"),
                     lambda: lv.eval_runner([("world", "x:N", dict(seed=1, region="A"))], 2, "noep")):
            with pytest.raises(ValueError) as ei:
                call()
            msg = str(ei.value)
            assert ("판정 실행기 'noep'" in msg and "쫓김 사건" in msg and "flight.episode" in msg and "'ceval'" in msg and "'python'" in msg
                    and "변경 기록 (7)" in msg)
        assert calls == []
        monkeypatch.setitem(lv.LIVE, "evaluator", "noep")
        a = Namespace(root=str(ROOT / "results" / "v3" / "live" / "_never"), workers=4, ckpt=None, steps=None, model_seeds=None, horizon=None,
                      judge_seeds=None, select_seeds=None, stuck_seeds=None, check_seeds=None, skip_check=False, force_export=False, horizon_g=None,
                      judge_seeds_g=None, flight_cost=None)
        with pytest.raises(SystemExit, match="쫓김 사건"):
            lv.plan_from_args(a)                                                                     # 판·감시를 시작하지 않는다
        assert not (ROOT / "results" / "v3" / "live" / "_never").exists()
    finally:
        lv.EVALUATORS.pop("noep", None)
        lv._CODE.pop("noep", None)


def test_cache_save_state(lv, prepared, tmp_path, monkeypatch):
    """지금 두뇌 판정 저장 기록 (gate.md '지금 두뇌 시험'): 실제로 쓴 것만 '저장함'·파일 이름, 쓰기 실패(os.replace)·결과가 일과 안 맞음은 '저장 실패'와 까닭 —
    없는 파일 이름을 적지 않는다."""
    root = tmp_path / "EcoAdapt"
    its = lv.eval_items(prepared, "current", lv.OBS21ZERO, [35000, 35001], 20, "N")
    rows = [_row(int(j["seed"]), j["region"]) for _, _, j in its]
    key = lv.eval_cache_key(prepared, its, lv.OBS21ZERO, "N")
    ok = lv.cache_save(root, key, its, rows, "시험", "N")
    assert ok == dict(state="saved", file=lv.cache_path(root, key).name, why=None) and lv.cache_path(root, key).exists()
    bad = lv.cache_save(root, key, its, rows[:-1], "시험", "N")
    assert bad["state"] == "save_failed" and bad["file"] is None and "맞지 않음" in bad["why"]
    lv.cache_path(root, key).unlink()
    monkeypatch.setattr(lv.time, "sleep", lambda s: None)
    monkeypatch.setattr(lv.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError("잠김")))
    fail = lv.cache_save(root, key, its, rows, "시험", "N")
    monkeypatch.undo()
    assert fail["state"] == "save_failed" and fail["file"] is None and "PermissionError" in fail["why"] and not lv.cache_path(root, key).exists()
    rows_ = dict(N=dict(state="hit", file="N_a.json"), G=dict(fail), stuck=dict(state="off", file=None))
    md = lv.cache_note_md(rows_, "지금 두뇌 시험: 일부 저장된 결과 (N)")
    assert md.startswith("- 지금 두뇌 시험: 일부 저장된 결과 (N) — N 저장된 결과 다시 씀 (`live/cache/N_a.json`)")
    assert "G 새로 잼(저장 실패) — PermissionError" in md and "끼임 새로 잼(저장 끔)" in md and "저장함" not in md
    assert "N 새로 잼(저장함) (`live/cache/" in lv.cache_note_md(dict(N=ok))


def test_eval_cache(lv, prepared, tmp_path, monkeypatch, request):
    """지금 두뇌 판정 저장: 없으면 None, 쓰면 같은 꼬리표·순서로 다시 읽음, 열쇠(환경·세계·두뇌·시드·길이·실행기·셈 길 판·저장 판·1차 기준 판)가 하나라도
    다르면 None, 깨진·바뀐 파일·옛 저장 판(10-23 전 판 1 — 숨은 뒤 지켜보기 없음, 10-24 전 판 2 — 쫓김 사건 없음)은 None, 쓰기는 임시 파일 →
    os.replace (실패해도 반쯤 쓴 파일·임시 파일이 남지 않는다), 오래된 것부터 지움."""
    root = tmp_path / "EcoAdapt"
    seeds = [35000, 35001]
    its = lv.eval_items(prepared, "current", lv.OBS21ZERO, seeds, 20, "N")
    rows = [dict(_row(int(j["seed"]), j["region"]), wall_s=np.float64(1.5), beh_steps=tuple(int(x) for x in (5, 1, 1, 0, 0))) for _, _, j in its]
    ev0 = lv.LIVE["evaluator"]                                                                  # 저장 열쇠 시험은 파이썬 실행기 판으로 (평가기 빌드와 무관하게 —
    lv.LIVE["evaluator"] = "python"                                                             # 아래 monkeypatch.undo() 가 되돌리지 않게 따로 둔다)
    request.addfinalizer(lambda: lv.LIVE.__setitem__("evaluator", ev0))
    key = lv.eval_cache_key(prepared, its, lv.OBS21ZERO, "N")
    assert key["env_digest"] == prepared["record"]["live"]["env_digest"] and key["seeds"] == seeds and key["horizon"] == [20]
    assert key["brain_weights_sha256"] == lv.zip_weights_sha(lv.OBS21ZERO) and key["brain_contract"] == lv.CONTRACT_OBS21 and key["evaluator"] == "python"
    assert key["brain_allowed"] == ["graze", "flee", "hide", "freeze", "sleep"][: len(key["brain_allowed"])] and len(key["brain_allowed"]) >= 3
    assert key["version"] == lv.CACHE_VERSION == 3 and key["criterion"] == lv.GATE_CRITERION == "hide-episode-v1" and lv.EVAL_CODE_TAG == "live-eval-3"
    assert lv.cache_get(root, key, its) is None                                                     # 처음 — 없음
    p = lv.cache_put(root, key, its, list(reversed(rows)), source="시험")                          # 어느 순서든 시드·지역 순으로
    assert p == lv.cache_path(root, key) and p.parent == root / "live" / "cache" and not list(root.rglob("*.tmp"))
    got = lv.cache_get(root, key, its)
    assert [t for t, _ in got] == ["current:N"] * len(its) and [r for _, r in got] == lv.jsonable(rows)
    assert isinstance(got[0][1]["wall_s"], float) and got[0][1]["beh_steps"] == [5, 1, 1, 0, 0]
    cand_its = lv.eval_items(prepared, "candidate", lv.OBS21ZERO, seeds, 20, "N")                  # 꼬리표·두뇌 경로는 열쇠가 아니다 (같은 두뇌 가중치)
    assert lv.eval_cache_key(prepared, cand_its, lv.OBS21ZERO, "N") == key and [t for t, _ in lv.cache_get(root, key, cand_its)] == ["candidate:N"] * len(its)
    # 열쇠가 하나라도 다르면 다른 파일 — 새로 잰다
    info2 = copy.deepcopy(prepared)
    info2["record"]["live"]["env_digest"] = "0" * 16
    its_disc = copy.deepcopy(its)
    its_disc[0][2]["cfg"]["v2"]["features"]["obstacles"]["fixed"].append([1.0, 2.0, 0.4])
    variants = {"환경": lv.eval_cache_key(info2, its, lv.OBS21ZERO, "N"),
                "세계": lv.eval_cache_key(prepared, its_disc, lv.OBS21ZERO, "N"),
                "세계 G": lv.eval_cache_key(prepared, lv.eval_items(prepared, "current", lv.OBS21ZERO, seeds, 20, "G"), lv.OBS21ZERO, "N"),
                "시드": lv.eval_cache_key(prepared, lv.eval_items(prepared, "current", lv.OBS21ZERO, [35000, 35002], 20, "N"), lv.OBS21ZERO, "N"),
                "길이": lv.eval_cache_key(prepared, lv.eval_items(prepared, "current", lv.OBS21ZERO, seeds, 21, "N"), lv.OBS21ZERO, "N")}
    monkeypatch.setitem(lv._SHA, lv._zkey(lv.OBS21ZERO), "ab" * 32)                                # 두뇌 가중치가 다르다
    variants["두뇌"] = lv.eval_cache_key(prepared, its, lv.OBS21ZERO, "N")
    monkeypatch.undo()
    monkeypatch.setitem(lv._ALLOWED, lv._zkey(lv.OBS21ZERO), ["graze", "flee"])                     # 허용 행동이 다르다 (계약 해시 밖)
    variants["허용 행동"] = lv.eval_cache_key(prepared, its, lv.OBS21ZERO, "N")
    monkeypatch.undo()
    lv.EVALUATORS["fake"] = dict(run=None, version=lambda: "f1")
    try:
        variants["실행기"] = lv.eval_cache_key(prepared, its, lv.OBS21ZERO, "N", "fake")
    finally:
        lv.EVALUATORS.pop("fake", None)
        lv._CODE.pop("fake", None)
    old = lv._CODE.pop("python")
    monkeypatch.setattr(lv, "EVAL_CODE_TAG", "live-eval-test")                                      # 셈 길 판이 다르다
    variants["셈 길"] = lv.eval_cache_key(prepared, its, lv.OBS21ZERO, "N")
    monkeypatch.undo()
    lv._CODE["python"] = old
    monkeypatch.setattr(lv, "GATE_CRITERION", "chase-v0")                                          # 1차 기준 판이 다르다 (10-23 — 기준이 바뀌면 새로 잰다)
    variants["1차 기준"] = lv.eval_cache_key(prepared, its, lv.OBS21ZERO, "N")
    monkeypatch.undo()
    assert lv.eval_cache_key(prepared, its, lv.OBS21ZERO, "N") == key
    for name, k2 in variants.items():
        assert k2 != key and lv.cache_path(root, k2) != p and lv.cache_get(root, k2, its) is None, name
    # 깨진 파일·바뀐 열쇠·다른 일 순서
    d = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(json.dumps(dict(d, key=dict(d["key"], seeds=[1]))), encoding="utf-8")
    assert lv.cache_get(root, key, its) is None
    p.write_text(json.dumps(d)[:100], encoding="utf-8")
    assert lv.cache_get(root, key, its) is None
    p.write_text(json.dumps(dict(d, rows=list(reversed(d["rows"])))), encoding="utf-8")
    assert lv.cache_get(root, key, its) is None
    p.write_text(json.dumps(dict(d, version=1)), encoding="utf-8")                                   # 옛 저장 판 (10-23 전) — 쓰지 않는다
    assert lv.cache_get(root, key, its) is None
    p.write_text(json.dumps(dict(d, version=2)), encoding="utf-8")                                   # 옛 저장 판 2 (10-24 전 — 쫓김 사건 없음) — 쓰지 않는다
    assert lv.cache_get(root, key, its) is None
    old_key = dict(key, version=2, criterion="hide-10s-v1")
    assert lv.cache_path(root, old_key) != lv.cache_path(root, key)                                   # 옛 기준 판 열쇠는 다른 파일이다
    p.write_text(json.dumps(d), encoding="utf-8")
    assert lv.cache_get(root, key, its) is not None
    assert lv.cache_put(root, key, its, rows[:-1]) is None                                           # 일과 맞지 않는 결과는 쓰지 않는다
    # 쓰기: 임시 파일 → os.replace. 잠깐 잠기면 다시, 끝내 안 되면 오류 — 반쯤 쓴 파일·임시 파일이 남지 않는다
    p.unlink()
    real, calls = os.replace, [0]

    def flaky(a, b):
        calls[0] += 1
        if calls[0] <= 2:
            raise PermissionError("잠김")
        return real(a, b)

    monkeypatch.setattr(lv.time, "sleep", lambda s: None)
    monkeypatch.setattr(lv.os, "replace", flaky)
    lv.cache_put(root, key, its, rows)
    assert calls[0] == 3 and lv.cache_get(root, key, its) is not None and not list(root.rglob("*.tmp"))
    p.unlink()

    def broken(a, b):
        assert Path(a).name.endswith(".tmp") and Path(a).read_text(encoding="utf-8").endswith("\n")      # 다 쓴 임시 파일을 바꿔 넣으려 한다
        raise PermissionError("잠김")

    monkeypatch.setattr(lv.os, "replace", broken)
    with pytest.raises(PermissionError):
        lv.cache_put(root, key, its, rows)
    monkeypatch.setattr(lv.os, "replace", real)
    assert not p.exists() and not list(root.rglob("*.tmp")) and lv.cache_get(root, key, its) is None
    # 오래된 것부터 지움
    monkeypatch.setattr(lv, "CACHE_KEEP", 2)
    for i, k2 in enumerate(list(variants.values())[:3]):
        q = lv.cache_put(root, k2, its, rows)
        os.utime(q, (time.time() - 100 + i, time.time() - 100 + i))
    lv.cache_put(root, key, its, rows)
    assert len(list((root / "live" / "cache").glob("*.json"))) == 2 and lv.cache_get(root, key, its) is not None
    want = dict(a=3, b=[0.5], c=[0, 1], d="x/y", e={"1": None})
    assert lv.jsonable(dict(a=np.int64(3), b=(np.float32(0.5),), c=np.arange(2), d=Path("x/y"), e={1: None})) == want
    with pytest.raises(TypeError):
        lv.jsonable(dict(a=object()))


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
# 10-24 (LIVE_GATE.md 변경 기록 (8)) 두 길·판 5 두뇌 — 지금 두뇌로 받아 판 5 세계에서 판정·이어 배우기, 길 지킴은 보고만
# --------------------------------------------------------------------- #

R7E_FILE = ECOBRAINS / "v3_r7_g995_s1_20m.json"
ROUTE0_FILE = ECOBRAINS / "v3_r1_g995_s3_obs24route0.json"
R7E_ZIP = ROOT / "ckpt" / "v3" / "v3_r7_g995_s1_20m.zip"
need_r7e = pytest.mark.skipif(not (R7E_FILE.exists() and R7E_ZIP.exists()), reason="R7e 두뇌 파일·모델 zip 이 없다 (저장소 밖 ckpt)")


def _route_snap(snap: dict, brain_file: Path = R7E_FILE, world_route=True) -> dict:
    """스냅숏의 지금 두뇌를 두뇌 파일의 것으로 바꾼 사본 (10-24 이식 2/2 스냅숏 꼴 — brain.mask_version·route·flee_gate, 지역 world.wild_flight.route·
    brain_flee_outside_reflex). world_route None 이면 지역 칸을 적지 않는다(이식 전 스냅숏 꼴)."""
    b = json.loads(Path(brain_file).read_text(encoding="utf-8"))
    s = copy.deepcopy(snap)
    mv = int(b["mask_version"])
    s["brain"].update(id=b["id"], weights_sha256=b["weights_sha256"], obs_dim=int(b["obs_dim"]), contract_hash=b["contract_hash"], builtin=False,
                      mask_version=mv, route=mv in (4, 5), flee_gate=mv == 5)
    if world_route is not None:
        for r in s["regions"]:
            r["world"]["wild_flight"].update(route=bool(world_route), brain_flee_outside_reflex=not (bool(world_route) and mv == 5))
    return s


@pytest.fixture(scope="module")
def r7e_prepared(lv, snap, tmp_path_factory):
    if not (R7E_FILE.exists() and R7E_ZIP.exists()):
        pytest.skip("R7e 두뇌 파일·모델 zip 이 없다")
    rd = tmp_path_factory.mktemp("round_r5") / "a1_route5_e0"
    return lv.prepare(SNAP, _route_snap(snap), rd, lv.BRAIN_FOLDERS)


def test_profiles_match_contracts(lv):
    """두뇌 묶음 표(PROFILES)의 계약 해시 = 그 바탕 설정(G·N)·학습 조리법(T) 세계의 관측 이름·마스크 판으로 다시 셈한 해시, 판 5 묶음은 R7 학습 조리법·
    λ 0.98 PPO, 관측 21 묶음은 옛것 그대로. 판 4(route0·R6)는 표에 없다."""
    import yaml

    import export_weights_v3 as ex
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import world_mask_version
    from env_v2.world import World

    assert set(lv.PROFILES) == {lv.CONTRACT_OBS21, lv.CONTRACT_OBS24_M5} and lv.CONTRACT_OBS24_M4 not in lv.PROFILES
    o21, r5 = lv.PROFILES[lv.CONTRACT_OBS21], lv.PROFILES[lv.CONTRACT_OBS24_M5]
    assert (o21["template"], o21["recipe"], o21["ppo"]) == (lv.TEMPLATE_OBS, lv.R5_TRAIN, lv.PPO_CONFIG)       # 관측 21 고리 그대로
    assert (r5["template"], r5["recipe"], r5["ppo"]) == (lv.TEMPLATE_ROUTE5, lv.R7_TRAIN, lv.PPO_ROUTE5)
    assert yaml.safe_load(lv.PPO_ROUTE5.read_text(encoding="utf-8"))["params"]["gae_lambda"] == 0.98
    assert "gae_lambda" not in yaml.safe_load(lv.PPO_CONFIG.read_text(encoding="utf-8"))["params"]
    for contract, prof in lv.PROFILES.items():
        for cfg_path in (prof["template"], prof["recipe"]):
            w = World(load_v2_config(cfg_path), seeds=[35000])
            mv = int(world_mask_version(w))
            assert mv == prof["mask_version"] and len(w.obs_names) == prof["obs_dim"], (contract, cfg_path)
            assert f"0x{ex.contract_hash(tuple(w.obs_names), mv):016x}" == contract, (contract, cfg_path)
        wf = load_v2_config(prof["template"]).v2["features"]["wild_flight"]
        assert bool(wf.get("route", False)) == prof["route"] and (not bool(wf.get("brain_flee_outside_reflex", True))) == prof["flee_gate"]


@need_r7e
def test_route5_start_resolution(lv, snap, tmp_path):
    """판 5 두뇌(R7e)가 지금 두뇌면 그 두뇌 파일의 zip 이 시작 모델(묶음 route5), 판 4 두뇌(route0)·마스크 판이 어긋난 스냅숏·지역 두 길 칸이 어긋난
    스냅숏은 거부. 옛 스냅숏(지역 두 길 칸 없음)은 받는다."""
    s = _route_snap(snap)
    r = lv.resolve_start(s, lv.BRAIN_FOLDERS)
    assert r["zip"].resolve() == R7E_ZIP.resolve() and r["current_model"].resolve() == R7E_ZIP.resolve()
    assert r["obs_dim"] == 24 and r["start_contract"] == r["brain_contract"] == lv.CONTRACT_OBS24_M5 and r["profile"] == "route5"
    assert lv.resolve_start(snap, lv.BRAIN_FOLDERS)["profile"] == "obs21"                       # 내장 R1b-F → 관측 21 그대로
    if ROUTE0_FILE.exists():
        with pytest.raises(lv.ad.Refused, match="판 4"):
            lv.resolve_start(_route_snap(snap, ROUTE0_FILE), lv.BRAIN_FOLDERS)
    bad = copy.deepcopy(s)
    bad["brain"]["mask_version"] = 4
    with pytest.raises(lv.ad.Refused, match="마스크 판"):
        lv.resolve_start(bad, lv.BRAIN_FOLDERS)
    bad = copy.deepcopy(s)
    bad["brain"]["contract_hash"] = lv.CONTRACT_OBS21                                          # 관측 24 인데 관측 21 계약이라 적힌 스냅숏
    with pytest.raises(lv.ad.Refused, match="계약 해시"):
        lv.resolve_start(bad, lv.BRAIN_FOLDERS)
    bad = copy.deepcopy(s)
    bad["brain"]["obs_dim"] = 30
    with pytest.raises(lv.ad.Refused, match="관측 18·21·24"):
        lv.resolve_start(bad, lv.BRAIN_FOLDERS)
    # 지역 세계 두 길 칸 (게임이 실제로 건 값) — 묶음과 다르면 거부, 없으면(이식 전 스냅숏) 보지 않는다
    lv.check_snapshot_route(s, lv.PROFILES[lv.CONTRACT_OBS24_M5])
    lv.check_snapshot_route(_route_snap(snap, world_route=None), lv.PROFILES[lv.CONTRACT_OBS24_M5])
    lv.check_snapshot_route(snap, lv.PROFILES[lv.CONTRACT_OBS21])
    with pytest.raises(lv.ad.Refused, match="두 길"):
        lv.check_snapshot_route(_route_snap(snap, world_route=False), lv.PROFILES[lv.CONTRACT_OBS24_M5])
    with pytest.raises(lv.ad.Refused, match="두 길"):
        lv.check_snapshot_route(s, lv.PROFILES[lv.CONTRACT_OBS21])                             # 관측 21 두뇌인데 지역 세계는 두 길 켬
    gate_only = copy.deepcopy(s)
    for r_ in gate_only["regions"]:
        r_["world"]["wild_flight"]["brain_flee_outside_reflex"] = True
    with pytest.raises(lv.ad.Refused, match="반사 밖 도망 막음"):
        lv.check_snapshot_route(gate_only, lv.PROFILES[lv.CONTRACT_OBS24_M5])
    with pytest.raises(lv.ad.Refused, match="두 길"):
        lv.prepare(SNAP, _route_snap(snap, world_route=False), tmp_path / "a_r5_bad", lv.BRAIN_FOLDERS)
    assert not (tmp_path / "a_r5_bad").exists()                                                 # 변환 전에 거부 — 판 폴더를 만들지 않는다


@need_r7e
def test_route5_worlds(lv, r7e_prepared):
    """판 5 묶음: G·N·T 모두 두 길·반사 밖 FLEE 막음(마스크 판 5·관측 24) 세계, T 는 늑대 포만 끔 + R7 조리법(f_dec 0.714694)·부활, PPO λ 0.98.
    판정 일(N·G·끼임)과 C++ 평가기 일(native_job)이 판 5 세계를 그대로 싣는다(평가기가 받는 칸 — unsupported_settings 빈 목록)."""
    import yaml

    import ceval
    from env_v2.config import load_v2_config
    from env_v2.rep_policy import check_mask_version, rep_params, world_mask_version
    from env_v2.world import World

    rd = r7e_prepared["dir"]
    world = yaml.safe_load((rd / "world.yaml").read_text(encoding="utf-8"))
    train = yaml.safe_load((rd / "train.yaml").read_text(encoding="utf-8"))
    for d in (world, train):
        assert d["features"]["wild_flight"]["route"] is True and d["features"]["wild_flight"]["brain_flee_outside_reflex"] is False
        assert d["features"]["obstacle_obs"]["enabled"] is True
    assert world["features"]["wild_satiation"]["enabled"] is True and train["features"]["wild_satiation"]["enabled"] is False
    assert "flight_cost" not in train["features"]["wild_flight"]
    assert world["features"]["integrated_stage"]["respawn"] is False and train["features"]["integrated_stage"]["respawn"] is True
    mix = train["train"]["region_mix"]
    assert "random_forest" not in mix and mix["obstacles"]["Forest"] == r7e_prepared["regions"]["Forest"]["discs"]
    rep = rep_params(load_v2_config(rd / "train.yaml"))
    assert rep["f_dec"] == pytest.approx(0.714694) and rep["cat_ent_coef"] == pytest.approx(0.01)
    assert "configs/v3_r7_train.yaml" in (rd / "train.yaml").read_text(encoding="utf-8").splitlines()[2]
    rec = json.loads((rd / "convert.json").read_text(encoding="utf-8"))
    assert rec["anchor"] == "ckpt/v3/v3_r7_g995_s1_20m.zip" and rec["template"] == "configs/v3_wild3_route5_mirror.yaml"
    lvr = rec["live"]
    assert (lvr["profile"], lvr["start_contract"], lvr["recipe"], lvr["ppo_config"]) == (
        "route5", lv.CONTRACT_OBS24_M5, "configs/v3_r7_train.yaml", "configs/ppo_r6_lam098.yaml")
    assert lv.ppo_config_of(r7e_prepared) == lv.PPO_ROUTE5 and lv.ppo_config_of(dict(record={})) == lv.PPO_CONFIG
    from stable_baselines3 import PPO

    pol = PPO.load(str(R7E_ZIP), device="cpu").policy
    for f in ("world.yaml", "train.yaml"):
        w = World(load_v2_config(rd / f), seeds=[35000])
        assert world_mask_version(w) == 5 and len(w.obs_names) == 24
        check_mask_version(pol.rep_mask_version, w.obs_names, w.brain_flee_outside_reflex)   # R7e 를 그 세계에 걸 수 있다
    n = lv.eval_items(r7e_prepared, "current", R7E_ZIP, [35000], 10, "N")
    g = lv.eval_items(r7e_prepared, "current", R7E_ZIP, [35000], 10, "G")
    st = lv.stuck_items(r7e_prepared, "current", R7E_ZIP, [35000], 10)
    for _, _, j in n + g + st:
        wf = j["cfg"]["v2"]["features"]["wild_flight"]
        assert wf["route"] is True and wf["brain_flee_outside_reflex"] is False
    assert all(j["cfg"]["v2"]["features"]["wild_satiation"]["enabled"] is False for _, _, j in n)
    for _, _, j in (n[0], g[0]):
        assert ceval.unsupported_settings(j["cfg"]) == []
        nj = ceval.native_job(j, 0, brain_mask_version=5)
        assert nj["world"]["wild_flight"]["route"] is True and nj["world"]["wild_flight"]["brain_flee_outside_reflex"] is False
        with pytest.raises(ValueError, match="마스크 판"):
            ceval.native_job(j, 0, brain_mask_version=2)                                     # 관측 21 두뇌 파일로는 판 5 세계 일을 만들지 않는다


@need_r7e
def test_route5_export(lv, tmp_path):
    """판 5 후보의 두뇌 파일: 계약 0xad7bad5e1acaf071·관측 24·판 5, 골든 세계 = 판 5 거울, 다시 읽기(A5) 통과, 다음 판의 시작점으로 찾힌다. 판 4 모델은
    두뇌 묶음에 없어 내보내지 않는다."""
    brains = tmp_path / "brains"
    gate = "시험 내보내기(--force-export) — 관문 기각: 1차 사건 숨음 비율 12.0%→12.4% t +0.5 (문턱 +12.71)"
    x = lv.export_brain(R7E_ZIP, brains, 1, 1, "a1_20261024T190000_e1", "eco_v3_snapshot_s20004_t480_e1.json", "Barren 나무 0→20, 비 1.0", gate,
                        play_id="p20261024T100000_0badcafe")
    assert x["ok"] and x["verify"]["contract_ok"] and x["verify"]["adapt_ok"]
    v = x["verify"]
    assert (v["contract_hash"], v["obs_dim"], v["mask_version"], v["profile"], v["golden_world"]) == (
        lv.CONTRACT_OBS24_M5, 24, 5, "route5", "configs/v3_wild3_route5_mirror.yaml")
    d = json.loads(Path(x["file"]).read_text(encoding="utf-8"))
    r7 = json.loads(R7E_FILE.read_text(encoding="utf-8"))
    assert d["weights_sha256"] == r7["weights_sha256"] and d["contract"] == r7["contract"] and d["allowed"] == r7["allowed"]
    assert d["model"]["path"] == "ckpt/v3/v3_r7_g995_s1_20m.zip" and d["adapt"]["gate"] == gate
    assert lv.ad.verify_brain_file(Path(x["file"]))["ok"]
    assert lv.find_brain_zip(d["weights_sha256"], [brains]).resolve() == R7E_ZIP.resolve()
    route0_zip = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs24route0.zip"
    if route0_zip.exists():
        with pytest.raises(ValueError, match="두뇌 묶음"):
            lv.export_brain(route0_zip, brains, 2, 2, "a2_x_e1", "s.json", "", "")
        assert sorted(p.name for p in brains.iterdir()) == [Path(x["file"]).name]               # 임시 파일이 남지 않는다


class _LazyProc:
    """감시가 띄운 판을 이 프로세스에서 돌리는 프로세스 꼴 (poll·wait·kill·returncode·pid — 감시가 쓰는 것만). 판은 감시가 처음 poll 할 때 끝까지 돈다 —
    진짜 판 프로세스처럼 감시가 상태 줄 '시작'을 쓴 뒤에 판이 상태 줄을 쓴다."""

    def __init__(self, fn):
        self._fn, self.returncode, self.pid = fn, None, os.getpid()

    def poll(self):
        if self.returncode is None:
            self.returncode = int(self._fn())
        return self.returncode

    def wait(self, timeout=None):
        return self.poll()

    def kill(self):
        pass


def _tree(p: Path) -> dict:
    return {str(q.relative_to(p)): (q.stat().st_mtime_ns, q.stat().st_size) for q in p.rglob("*")} if p.exists() else {}


@need_r7e
def test_real_root_profile_lock(lv, snap, tmp_path, monkeypatch):
    """10-27 (변경 기록 (10)) 실제 폴더 잠금 풀기 — 임시 폴더를 실제 폴더(DEFAULT_ROOT)로 놓고 본다(진짜 Saved/EcoAdapt 에는 쓰지 않는다): 관문 크기 plan 이
    시작되고, 감시가 띄우는 판 명령은 시험 깃발 없이 그 폴더를 쓴다. 그 명령(이 프로세스에서 live.main 으로 돌림)으로 판 5 두뇌(R7e) 스냅숏은 묶음 잠금을
    지나 변환·학습 시작까지 가고(학습은 가짜로 멈춘다), 관측 18 내장 R1b-F 스냅숏(묶음 obs21 — 크기 미확정)은 변환 전에 거부된다(refused·처리함·상태 줄
    '거부 — …'). 시험 폴더(real_root 거짓)는 관측 21 묶음도 그대로 받는다."""
    real = Path(lv.DEFAULT_ROOT)
    before = _tree(real)
    fake = tmp_path / "Saved" / "EcoAdapt"
    monkeypatch.setattr(lv, "DEFAULT_ROOT", fake)
    assert lv.is_real_root(fake) and not lv.is_real_root(real) and not lv.is_real_root(tmp_path / "other")
    # 묶음 잠금은 변환 전에 (판 폴더를 만들지 않는다). 시험 폴더는 그대로 받는다
    with pytest.raises(lv.ad.Refused, match="obs21 은 실제 폴더 관문 크기 미확정"):
        lv.prepare(SNAP, snap, tmp_path / "a_o21", lv.BRAIN_FOLDERS, real_root=True)
    assert not (tmp_path / "a_o21").exists()
    assert lv.prepare(SNAP, snap, tmp_path / "a_o21_test", lv.BRAIN_FOLDERS)["record"]["live"]["profile"] == "obs21"
    lv.check_profile_sizes(lv.PROFILES[lv.CONTRACT_OBS24_M5])                                     # 판 5 묶음은 확정

    # 감시 → 판 명령 → 판 (실제 폴더 꼴). 재현 확인·학습은 돌리지 않는다 (세계를 돌리지 않는 시험)
    monkeypatch.setattr(lv, "r_applicable", lambda s: (False, "시험 — 재현 확인 건너뜀"))

    def stop_training(*a, **k):
        raise RuntimeError("시험: 학습 앞에서 멈춤")

    monkeypatch.setattr(lv, "launch_training", stop_training)
    ran = []

    def launcher(cmd, fh):
        assert cmd[2] == "round" and cmd[cmd.index("--root") + 1] == str(fake) and "--child" in cmd
        assert not any(f in cmd for f in ("--steps", "--model-seeds", "--horizon", "--horizon-g", "--judge-seeds", "--judge-seeds-g", "--skip-check",
                                          "--force-export", "--flight-cost"))                    # 관문 크기 그대로 (시험 깃발 없음)
        def run():
            rc = lv.main(cmd[2:])
            ran.append((cmd[cmd.index("--run-id") + 1], rc))
            return rc

        return _LazyProc(run)

    a = Namespace(root=str(fake), workers=2, ckpt=str(tmp_path / "ckpt"), steps=None, model_seeds=None, horizon=None, judge_seeds=None, select_seeds=None,
                  stuck_seeds=None, check_seeds=None, skip_check=False, force_export=False, horizon_g=None, judge_seeds_g=None, flight_cost=None)
    pl = lv.plan_from_args(a)                                                                     # 실제 폴더에서 관문 크기 plan 이 시작된다 (잠금 풀림)
    assert not pl["test"] and pl["steps"] == lv.LIVE["train_steps"] == 1_000_000 and pl["horizon"] == 1800 and pl["judge"] == (35000, 35079)
    w = lv.Watcher(fake, pl, launcher=launcher, log=lambda s: None)
    now = time.time()
    r7e = _route_snap(snap)
    _write_snap(w.snapdir, "eco_v3_snapshot_s20003_t1800_e1.json", r7e, now - 10)
    w.tick()                                                                                      # 판 5 → 판 띄움
    assert w.child is not None and not ran
    _write_snap(w.snapdir, "eco_v3_snapshot_s20003_t1900_e1.json", snap, now - 5)                # 관측 18 내장 R1b-F (게임 기본)
    w.tick()                                                                                      # 판 5 판이 돌고(가짜 학습에서 멈춤) 정리 → 관측 18 판 띄움
    assert len(ran) == 1 and w.child is not None
    w.tick()                                                                                      # 관측 18 판 → 변환 전에 거부 → 정리
    assert w.child is None and len(ran) == 2
    w.tick()
    assert len(ran) == 2                                                                          # 거부한 환경을 다시 띄우지 않는다
    rid5, rid18 = ran[0][0], ran[1][0]
    r5 = json.loads((lv.rounds_dir(fake) / rid5 / "result.json").read_text(encoding="utf-8"))
    assert r5["state"] == "error" and "시험: 학습 앞에서 멈춤" in r5["why"] and r5["brain_profile"] == "route5" and not r5["plan_test"]
    assert r5["plan"]["steps"] == 1_000_000 and r5["start"] == "ckpt/v3/v3_r7_g995_s1_20m.zip"
    cv = json.loads((lv.rounds_dir(fake) / rid5 / "convert.json").read_text(encoding="utf-8"))
    assert cv["live"]["profile"] == "route5" and cv["live"]["f_dec"] == pytest.approx(0.714694)
    r18 = json.loads((lv.rounds_dir(fake) / rid18 / "result.json").read_text(encoding="utf-8"))
    assert r18["state"] == "refused" and "obs21 은 실제 폴더 관문 크기 미확정" in r18["why"] and ran[1][1] == 0
    assert not (lv.rounds_dir(fake) / rid18 / "world.yaml").exists()                              # 변환 전에 거부
    st = lv.load_state(fake)
    assert lv.is_processed(st, lv.pair_key(snap)) and not lv.is_processed(st, lv.pair_key(r7e))   # 거부 = 처리함 (같은 환경을 다시 하지 않는다)
    assert [h["state"] for h in st["history"]] == ["error", "refused"] and st["round"] == 0
    d = json.loads((fake / "status.json").read_text(encoding="utf-8"))
    assert d["state"] == "refused" and d["message"].startswith("거부 — 지금 두뇌 묶음 obs21 은 실제 폴더 관문 크기 미확정")
    assert not list((fake / "brains").glob("*.json"))                                           # 두뇌 파일은 쓰지 않았다
    w.stop()
    assert _tree(real) == before                                                                  # 진짜 실제 폴더는 그대로


def _route_block(refled: int, run: int, shelter: int, decisions: int = 40, choice: int = 20, pick_shelter: int = 12) -> dict:
    """세계 하나의 길 기록 (짜 맞춤 — World.flight_stats 의 route 꼴에서 보고가 읽는 칸만)."""
    z = dict(run=0, cover=0, shelter=0, open=0)
    return dict(brain=True, steps=dict(z, run=run, shelter=shelter), onsets=30, onset_cover=0, onset_shelter=14, onset_both=0, decisions=decisions,
                redecide_feas=3, switches=2, fallback=0, invalid=dict(z, shelter=1), picked=dict(z, run=decisions - pick_shelter, shelter=pick_shelter),
                choice=choice, bad_shelter=0, refled=refled, refled_steps=38)


def test_route_report(lv, monkeypatch):
    """10-24 (8) 길 보고: 설계 12절 길 지킴 GT·GTr·GR 을 r6_eval.route_guards 와 같은 셈으로 짝 차이만 적고(ok None — 관문 칸이 아니다), 관문
    판정(gate_live)은 길 기록이 있어도 없어도 같다. 길 기록이 없는 판(관측 21)은 보고 없음 — gate.md 그대로."""
    sys.path.insert(0, str(ROOT / "results" / "v3" / "r6"))
    import r6_eval

    seeds = range(35000, 35010)
    rng = np.random.default_rng(35208)
    cand = _fake(seeds, lambda s, r: 20, hidden=lambda s, r: 9, flee=lambda s, r: 0.08 + 0.001 * (s % 3), trunc=lambda s, r: 1 + s % 2)
    cur = _fake(seeds, lambda s, r: 20, hidden=lambda s, r: 7)
    plain = copy.deepcopy(cand), copy.deepcopy(cur)
    for res, k in ((cand, 0), (cur, 1)):
        for w in res["worlds"]:
            w["flight"]["route"] = _route_block(int(rng.integers(5, 15)) + 3 * (1 - k), 400, 300 + 50 * (1 - k))
    rr = lv.route_report(cand, cur)
    ref = r6_eval.route_guards(cand, cur)
    assert set(rr["criteria"]) == set(lv.ROUTE_REPORT_KEYS) == set(ref)
    for key in lv.ROUTE_REPORT_KEYS:
        got, want = rr["criteria"][key], ref[key]
        assert got["ok"] is None and "보고만" in got["rule"]
        assert all(got[f] == pytest.approx(want[f]) for f in ("a", "b", "diff", "se", "t", "n")), key
    gv = lv.flight_rate_pair(cand, cur, "flee")
    assert rr["criteria"]["GT_flight_time"]["t"] == pytest.approx(gv["t"])                    # GT = 60 × GV — 짝 t 가 같다
    p = rr["pooled"]["candidate"]
    assert (p["run_steps"], p["shelter_steps"], p["decisions"], p["choice"], p["picked_shelter"]) == (400 * 20, 350 * 20, 800, 400, 240)
    assert p["shelter_step_share"] == pytest.approx(350 / 750)
    assert lv.route_report(*plain) is None and lv.route_report(cand, plain[1]) is None          # 길 기록이 없는 판(관측 21) — 보고 없음
    text = lv.fmt_route_report(rr)
    assert "## 길 기록 (보고만" in text and all(k in text for k in lv.ROUTE_REPORT_KEYS) and lv.fmt_route_report(None) == ""
    # 관문 판정은 길 기록과 무관하다 (칸·값 그대로)
    monkeypatch.setitem(lv.LIVE, "hide_min_effect", 0.0)
    G = _fake(range(35000, 35005), lambda s, r: 10)
    stk = dict(current=dict(summary=dict(deer=0, wolf=0)), candidate=dict(summary=dict(deer=0, wolf=0)))
    import r4_eval

    monkeypatch.setattr(r4_eval, "stuck_counts", lambda s: dict(deer=0, wolf=0))
    ga = lv.gate_live(dict(N=dict(candidate=cand, current=cur), G=dict(candidate=G, current=G)), stk, None)
    gb = lv.gate_live(dict(N=dict(candidate=plain[0], current=plain[1]), G=dict(candidate=G, current=G)), stk, None)
    assert ga["verdict"] == gb["verdict"] and list(ga["criteria"]) == list(gb["criteria"])
    assert not any(k in ga["criteria"] for k in lv.ROUTE_REPORT_KEYS)
    for k in ga["criteria"]:
        assert {f: ga["criteria"][k].get(f) for f in ("ok", "t")} == {f: gb["criteria"][k].get(f) for f in ("ok", "t")}, k


def test_route_report_in_judge(lv, prepared, seq_setup):
    """judge_candidate 가 두 길 판(N 세계 기록에 flight.route)이면 gate 에 route_report 를 붙이고 gate.md 에 '길 기록' 절을 쓴다. 중간 기각이면 앞 절반
    짝으로 적는다. 길 기록이 없는 판(관측 21 — 옛 판)은 붙이지 않는다."""
    base, hb = seq_setup["base"], seq_setup["hb"]
    jc, _ = _judge(lv, prepared, seq_setup, {("candidate", "N"): lambda s, r: dict(chase=base[(s, r)], hidden=hb[(s, r)] - 2)})
    assert jc["stage"] == "interim_futility" and "route_report" not in jc["gate"]
    assert "## 길 기록" not in lv.gate_md("a1_t", dict(jc["gate"], candidate="c", current="k", profile="시험"))
    cur = copy.deepcopy(seq_setup["cur"])
    for w in cur["current:N"]["worlds"]:
        w["flight"]["route"] = _route_block(10, 400, 300)
    rows = dict(seq_setup, cur=cur)
    log: list = []

    def runner(items, on_done=None):
        out = _fake_runner({("candidate", "N"): lambda s, r: dict(chase=base[(s, r)], hidden=hb[(s, r)] - 2),
                            ("candidate", "G"): lambda s, r: dict(chase=base[(s, r)], hidden=hb[(s, r)])}, log)(items, on_done)
        for tag, row in out:
            if "flight" in row:
                row["flight"]["route"] = _route_block(14, 400, 360)
        return out

    jc = lv.judge_candidate(prepared, lv.OBS21ZERO, rows["cur"], rows["plan"], dict(ok=None, why="시험"), None, runner=runner)
    assert jc["stage"] == "interim_futility"
    rr = jc["gate"]["route_report"]
    assert rr["criteria"]["GR_reflee"]["n"] == jc["gate"]["seq"]["n_int"] and rr["criteria"]["GR_reflee"]["diff"] == pytest.approx(4 * len(prepared["regions"]))
    text = lv.gate_md("a1_t", dict(jc["gate"], candidate="c", current="k", profile="시험"))
    assert "## 길 기록 (보고만" in text and text.index("## 길 기록") < text.index("## 중간 판정")


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
    assert f"t_crit = {tc:.3f}" in md and f"| 문턱 t_crit(n − 1) | {tc:.3f} |" in md and f"t ≥ +{tc:.3f}" in md and f"t < +{tc:.3f}" in md
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
    # 10-21 (3) 쫓긴 시간 (10-23 (6) 부터 보고만·GG_chase): 사용자 말 그대로, 스스로 벗어남·잡힘·굶음·잘림 = 세계의 정의와 같은 끝 까닭
    from env_v2.world import FLIGHT_CAUSES, FLIGHT_HIDE_WATCH_STEPS, FLIGHT_NOT_CHASED, FLIGHT_OWN, FLIGHT_STEP_S, FLIGHT_UNSAFE

    assert "(3) 사용자 10-21 기준 바꿈 — 1차 = 도망 시간" in md
    assert "똑같이 도망을 가도 숲속으로 잘 숨어서 늑대 시야에 잘 벗어나기 때문에 도망가는 시간이 더 짧은 사슴이 똑똑한걸로 기준을 잡아봐" in md
    assert tuple(L["flight_own"]) == FLIGHT_OWN and "스스로 벗어난 도망(cover · obstacle · fov · range)" in md
    assert tuple(L["flight_unsafe"]) == FLIGHT_UNSAFE and "(caught · starved · truncated)" in md
    assert L["flight_min_episodes"] == 1 and "스스로 벗어난 도망 1개 이상" in md
    assert "flight_min_effect_s" not in L                                                          # 10-23 (6): 쫓긴 시간 δ(초)는 δ_H 로 바꿨다
    assert L["train_flight_cost"] == 0.0 and "| T 세계 도주 비용 flight_cost | 0 (끔) | 확정 (10-27 (10) 판 5 예비 측정" in md
    # 10-27 (10) 사람 결정 '실제 폴더 잠금 풀자' — 판 5 묶음 예비 측정 pilot_mask5 로 크기 확정, 관측 21 묶음은 실제 폴더 잠금 유지
    assert "### 2026-10-27 (10) 사람 결정 '실제 폴더 잠금 풀자'" in md and "'실제 폴더 잠금 풀자'" in md and "'두뇌를 다시 배우는 건" in md
    assert L["flight_sizes_confirmed"] is True and "| 크기 확정 표시 flight_sizes_confirmed | 참 |" in md
    assert md.count("사건 숨음 비율 기준도 그대로 확정 (10-27 (10) 판 5 예비 측정 `pilot_mask5`)") == 5          # H_N·n·H_G·n_G·K
    assert L["train_steps"] == 1_000_000 and "| 학습 스텝 S | 1M | 확정 (10-27 (10) 판 5 예비 측정" in md and "**S = 1M 스텝**(10-27 (10) — 그 전 2M)" in md
    conf = {p_["name"]: p_["sizes_confirmed"] for p_ in lv.PROFILES.values()}
    assert conf == {"obs21": False, "route5": True} and all(p_["sizes_basis"] for p_ in lv.PROFILES.values())
    assert "| 크기를 확정한 두뇌 묶음 (`live.PROFILES` `sizes_confirmed`) | 판 5 `route5`" in md and "관측 21 `obs21`(관측 18 R1b-F·관측 21 지금 두뇌) 거짓" in md
    assert (LIVE_DIR / "pilot_mask5" / "README.md").exists() and "`pilot_mask5/`" in md
    assert all(k in md for k in ("GF", "GV", "GC", "GG_chase", "GN_caught", "P1_N_hide", "GH_flight_caught", "REPORT_N_chase"))
    assert all(f"`{c}`" in md for c in FLIGHT_CAUSES)
    assert lv.STEP_S == pytest.approx(2.0 / 15.0) == FLIGHT_STEP_S and "× 2/15 초" in md
    # 10-23 (6) 1차 = 숨음 비율·지킴 GH·쫓긴 시간 보고만·판정 실행기 python: 사용자 말 그대로, 정의 칸, 상수
    assert "### 2026-10-23 (6) 사람 결정 — 1차를 숨음 비율로, 잡힘 비율 지킴 추가, 쫓긴 시간은 보고만, evaluator python (C++ 이식 전)" in md
    assert ("그럼 더 나아졌다고 보는 기준을 거기에 더해서 전체 사냥률보다 사슴 하나가 늑대에게 쫓겼을 때 잡히는지 아니면 살아서 은신처에 잘\n  숨는지 이걸 "
            "관측하게 해서 비율로 판정") in md
    assert FLIGHT_HIDE_WATCH_STEPS == 75 and "| 지켜보는 길이 | 75 스텝 (10 초 ÷ 1 스텝 2/15 초 — 코드 `FLIGHT_HIDE_WATCH_STEPS`) |" in md
    assert FLIGHT_NOT_CHASED == ("unchased", "truncated") and "`unchased`·`truncated`(코드 `FLIGHT_NOT_CHASED`)" in md
    assert L["hide_min_chased"] == 1 and "| P1·GH 짝 시드 조건 | 두 두뇌 모두 쫓긴 사건 1개 이상 (`hide_min_chased`" in md
    assert L["hide_min_effect"] == 0.01 and "| P1 최소 차이 δ_H | 1 %p (`hide_min_effect` 0.01" in md and "≥ δ_H(`LIVE.hide_min_effect` 0.01 = **1 %p**" in md
    assert "9.48 % 대 9.50 %" in md and "12.73 % → 21.19 %" in md and "13.25 % → 21.89 %" in md and "10 초 지켜보기 전 값" in md
    assert "10-23 덧붙임 — 숨은 뒤 10 초 지켜보기를 C++ 에 옮김" in md
    # 10-24 (7) 쫓김 사건: 사람 결정·까닭(R7 결과를 본 뒤 — 두 번 세기)·정의·이음 창 상수·GE·판정 실행기 python·저장 판
    from env_v2.world import EPISODE_LINK_COVER_STEPS, EPISODE_LINK_OTHER_STEPS, FLIGHT_REFLEE_STEPS

    assert "### 2026-10-24 (7) 사람 결정 — '쫓김 사건' 단위로 셈" in md and "\"'쫓김 사건' 단위로 셈\"" in md and "R7 결과를 본 뒤" in md and "두 번" in md
    assert EPISODE_LINK_COVER_STEPS == FLIGHT_HIDE_WATCH_STEPS == 75 and EPISODE_LINK_OTHER_STEPS == FLIGHT_REFLEE_STEPS == 38
    assert "`EPISODE_LINK_COVER_STEPS`" in md and "`EPISODE_LINK_OTHER_STEPS`" in md and "| 쫓김 사건 이음 창 | 앞 도망이 cover 로 끝났으면 75 스텝" in md
    assert all(k in md for k in ("GE_episode_starts", "REPORT_N_flight_hide", "REPORT_N_flight_caught", "| GE 재료 | 1000 산 사슴-스텝당 시작한 쫓김 사건"))
    assert "- **통과 = R(잰 때), P1, GH, GN, GF, GE, GV, GC, GG, G4, G5, G6, A5 모두.**" in md and "약 26%" in md
    assert L["evaluator"] == "ceval" and "| 판정 실행기 evaluator | ceval (" in md and "10-24 덧붙임 — 쫓김 사건 셈을 C++ 에 옮김" in md
    assert lv.CACHE_VERSION == 3 and lv.GATE_CRITERION == "hide-episode-v1" and lv.GATE_CRITERION in md and lv.EVAL_CODE_TAG == "live-eval-3"
    assert lv.EVAL_CODE_TAG in md and "저장 판 3" in md
    # 10-21 (4) 중간 판정 (두 번 보기)·지금 두뇌 판정 다시 쓰기·판정 실행기 — 시점·기각 경계는 예비 측정 뒤 확정 (10-23 (6) 부호 뒤집음)
    assert "### 2026-10-21 (4) 중간 판정" in md and "### 5-3. 중간 판정 (두 번 보기" in md
    k = lv.seq_sizes(n)
    assert L["seq_interim_frac"] == 0.5 and k == 40 and f"| 중간 판정 시점 seq_interim_frac | N 판정 시드 앞 1/2 (n {n} 이면 35000~{35000 + k - 1}, {k}개) | 확정 (10-27 (10)" in md
    assert L["seq_alpha"] == 0.025 and "| 1차 한쪽 α seq_alpha | 0.025" in md and L["seq_spending"] == "obf" and "| α 쓰기 함수 seq_spending | obf" in md
    assert L["seq_efficacy"] is False and lv.seq_final_bound(n, dict(lv.seq_interim_bound(k, n), n1=k))["bound"] == tc     # 끈 기본: 끝 문턱 = 옛 것
    old = L["seq_efficacy"]
    L["seq_efficacy"] = True                                                                            # 켰을 때의 값 (문서 표)
    try:
        b1 = lv.seq_interim_bound(k, n)
        b2 = lv.seq_final_bound(n, dict(b1, n1=k))
    finally:
        L["seq_efficacy"] = old
    assert f"| 중간 앞서 통과 seq_efficacy · 경계 b₁ | 끔 (켜면 짝 t ≥ +{b1['bound']:.3f} — n₁ {k}, 쓴 α₁ {b1['alpha1']:.5f} — 1차만 통과로 정하고 지킴은 전체)" in md
    assert f"| 끝 문턱 b₂ (두 번 보기) | 끈 기본: 짝 t ≥ +{tc:.3f} (옛 한 번 보기 그대로). 앞서 통과를 켜면 +{b2['bound']:.3f} (n₁ {n}, t_{{α − α₁}})" in md
    assert f"앞서 통과를 켜면 끝 문턱 b₂ = +{b2['bound']:.3f} (n₁ {n}), 중간 b₁ = +{b1['bound']:.3f} (n₁ {k})" in md                  # 5절 P1 줄
    assert f"중간 c₁ = {b1['c1']:.3f}" in md and f"참고 c₂ = {b2['c2']:.3f}" in md and f"+{b2['bound_z']:.3f}" in md
    assert L["seq_futility_t"] == 0.0 and "| 중간 기각 경계 seq_futility_t | 짝 t ≤ 0 (나아지는 쪽도 아님) — 구속력 없음 | 확정 (10-27 (10)" in md
    assert lv.fut_bound_text(L["seq_futility_t"]) == "t ≤ 0" and "`gate.md` 머리 `중간 기각 경계 t ≤ 0`" in md
    assert "### 2026-10-21 (5)" in md
    assert L["cache_current"] is True and "| 지금 두뇌 판정 다시 쓰기 cache_current | 켬" in md
    # 10-24 (8) 두 길·판 5 두뇌: 묶음 표(계약·바탕·조리법·PPO)·판 4 거부·길 지킴 GT·GTr·GR 은 보고만·관문 표 그대로·실제 폴더 잠금 그대로
    assert "### 2026-10-24 (8)" in md and "10-24 (8) 두 길·판 5 두뇌를 고리에 받음" in md
    assert all(c in md for c in (lv.CONTRACT_OBS21, lv.CONTRACT_OBS24_M5, lv.CONTRACT_OBS24_M4))
    assert all(p.exists() and p.name in md for p in (lv.TEMPLATE_ROUTE5, lv.R7_TRAIN, lv.PPO_ROUTE5, lv.TEMPLATE_OBS, lv.R5_TRAIN, lv.PPO_CONFIG))
    assert "f_dec 0.714694" in md and "λ 0.98" in md and "| 이어 배우는 두뇌 묶음 (`live.PROFILES`" in md
    assert "| 길 지킴 GT·GTr·GR (설계 12절·16-11) | 보고만" in md and all(f"`{k}`" in md for k in lv.ROUTE_REPORT_KEYS)
    assert "GT = 60 × GV" in md and "GR 자리 = GE" in md
    assert not any(k.startswith(("GT", "GR")) for k in lv.GUARD_PREFIXES)                         # 관문 지킴 칸은 그대로 (GE 를 쓰는 표)
